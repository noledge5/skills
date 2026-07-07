"""Safe deletion via quarantine.

Nothing in DiskButler ever unlinks user data directly. "Cleaning"
moves files into a quarantine folder inside the data directory and
records where they came from, so every batch can be restored with one
call. Disk space is only really freed by purging a batch — an explicit,
separate step.
"""

from __future__ import annotations

import os
import shutil
import time

from .db import Database

# Paths that must never be quarantined, even if asked.
_FORBIDDEN = [
    os.path.expanduser("~"),
]
if os.name == "nt":  # drive roots and Windows itself
    _FORBIDDEN += [os.environ.get("SystemRoot", r"C:\Windows")]


def _is_forbidden(path: str) -> bool:
    norm = os.path.normcase(os.path.abspath(path))
    if os.path.splitdrive(norm)[1] in (os.sep, ""):
        return True  # a drive root or empty path
    for f in _FORBIDDEN:
        if norm == os.path.normcase(os.path.abspath(f)):
            return True
    return False


class Quarantine:
    def __init__(self, db: Database):
        self.db = db
        self.dir = os.path.join(db.data_dir, "quarantine")
        os.makedirs(self.dir, exist_ok=True)

    def quarantine(self, paths: list[str], reason: str = "") -> dict:
        conn = self.db.connect()
        cur = conn.execute(
            "INSERT INTO quarantine_batches (created_at, reason) VALUES (?, ?)",
            (time.time(), reason),
        )
        batch_id = cur.lastrowid
        batch_dir = os.path.join(self.dir, f"batch-{batch_id}")
        os.makedirs(batch_dir, exist_ok=True)

        moved, errors = [], []
        for i, path in enumerate(paths):
            path = os.path.abspath(path)
            if _is_forbidden(path):
                errors.append({"path": path, "error": "protected path"})
                continue
            if not os.path.lexists(path):
                errors.append({"path": path, "error": "not found"})
                continue
            is_dir = os.path.isdir(path) and not os.path.islink(path)
            try:
                size = 0 if is_dir else os.path.getsize(path)
            except OSError:
                size = 0
            stored = os.path.join(batch_dir, f"{i:05d}-{os.path.basename(path)}")
            try:
                shutil.move(path, stored)
            except OSError as e:
                errors.append({"path": path, "error": str(e)})
                continue
            conn.execute(
                "INSERT INTO quarantine_items"
                " (batch_id, original_path, stored_path, size, is_dir)"
                " VALUES (?,?,?,?,?)",
                (batch_id, path, stored, size, 1 if is_dir else 0),
            )
            # Drop from the search index too (FTS mirror follows via triggers).
            prefix = path.rstrip("/\\") + os.sep + "%"
            conn.execute(
                "DELETE FROM files WHERE path = ? OR path LIKE ?",
                (path, prefix),
            )
            moved.append({"path": path, "stored": stored, "size": size})
        conn.commit()
        return {"batch_id": batch_id, "moved": moved, "errors": errors}

    def list_batches(self) -> list[dict]:
        conn = self.db.connect()
        batches = conn.execute(
            "SELECT b.*, COUNT(i.id) AS item_count,"
            " COALESCE(SUM(i.size), 0) AS total_size"
            " FROM quarantine_batches b"
            " LEFT JOIN quarantine_items i ON i.batch_id = b.id"
            " GROUP BY b.id ORDER BY b.created_at DESC"
        ).fetchall()
        return [dict(b) for b in batches]

    def list_items(self, batch_id: int) -> list[dict]:
        rows = self.db.connect().execute(
            "SELECT * FROM quarantine_items WHERE batch_id = ?", (batch_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def restore(self, batch_id: int) -> dict:
        conn = self.db.connect()
        items = self.list_items(batch_id)
        restored, errors = [], []
        for item in items:
            if not os.path.lexists(item["stored_path"]):
                errors.append({"path": item["original_path"],
                               "error": "missing from quarantine"})
                continue
            os.makedirs(os.path.dirname(item["original_path"]), exist_ok=True)
            try:
                shutil.move(item["stored_path"], item["original_path"])
                restored.append(item["original_path"])
                conn.execute(
                    "DELETE FROM quarantine_items WHERE id = ?", (item["id"],)
                )
            except OSError as e:
                errors.append({"path": item["original_path"], "error": str(e)})
        conn.execute(
            "UPDATE quarantine_batches SET status = 'restored' WHERE id = ?"
            " AND NOT EXISTS (SELECT 1 FROM quarantine_items WHERE batch_id = ?)",
            (batch_id, batch_id),
        )
        conn.commit()
        self._cleanup_batch_dir(batch_id)
        return {"restored": restored, "errors": errors}

    def purge(self, batch_id: int) -> dict:
        """Permanently delete a quarantined batch. Irreversible."""
        conn = self.db.connect()
        items = self.list_items(batch_id)
        purged, errors = [], []
        for item in items:
            try:
                if os.path.isdir(item["stored_path"]) and not os.path.islink(
                    item["stored_path"]
                ):
                    shutil.rmtree(item["stored_path"])
                elif os.path.lexists(item["stored_path"]):
                    os.remove(item["stored_path"])
                purged.append(item["original_path"])
                conn.execute(
                    "DELETE FROM quarantine_items WHERE id = ?", (item["id"],)
                )
            except OSError as e:
                errors.append({"path": item["stored_path"], "error": str(e)})
        conn.execute(
            "UPDATE quarantine_batches SET status = 'purged' WHERE id = ?",
            (batch_id,),
        )
        conn.commit()
        self._cleanup_batch_dir(batch_id)
        return {"purged": purged, "errors": errors}

    def _cleanup_batch_dir(self, batch_id: int) -> None:
        batch_dir = os.path.join(self.dir, f"batch-{batch_id}")
        try:
            if os.path.isdir(batch_dir) and not os.listdir(batch_dir):
                os.rmdir(batch_dir)
        except OSError:
            pass
