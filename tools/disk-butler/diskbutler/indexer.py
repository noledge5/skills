"""Filesystem indexer.

Walks a directory tree with os.scandir (the fastest portable option),
writes entries into SQLite in large batches, and keeps the FTS5 mirror
in sync. Re-indexing a root replaces its previous entries, so the
index never accumulates stale rows.
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass, field

from .db import Database

# Directories that are almost never interesting and hugely inflate
# scan time. Matched by name at any depth.
DEFAULT_EXCLUDES = {
    "$Recycle.Bin",
    "System Volume Information",
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}

BATCH_SIZE = 5000


@dataclass
class ScanProgress:
    root: str = ""
    files: int = 0
    dirs: int = 0
    total_size: int = 0
    errors: int = 0
    current_dir: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    running: bool = False

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["duration_s"] = round(
            (self.finished_at or time.time()) - self.started_at, 2
        ) if self.started_at else 0
        return d


@dataclass
class Indexer:
    db: Database
    excludes: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDES))
    follow_symlinks: bool = False
    progress: ScanProgress = field(default_factory=ScanProgress)

    def index(self, root: str) -> ScanProgress:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            raise NotADirectoryError(root)

        p = self.progress = ScanProgress(
            root=root, started_at=time.time(), running=True
        )
        conn = self.db.connect()
        # Replace any previous index of this root (or of subtrees of it).
        # The FTS mirror is kept in sync by triggers, so deleting from
        # files is enough.
        prefix = root.rstrip(os.sep) + os.sep
        conn.execute(
            "DELETE FROM files WHERE path = ? OR path LIKE ?",
            (root, prefix + "%"),
        )

        batch: list[tuple] = []

        def flush() -> None:
            if not batch:
                return
            conn.executemany(
                "INSERT OR REPLACE INTO files"
                " (path, parent, name, ext, size, mtime, is_dir)"
                " VALUES (?,?,?,?,?,?,?)",
                batch,
            )
            batch.clear()

        stack = [root]
        while stack:
            current = stack.pop()
            p.current_dir = current
            try:
                entries = os.scandir(current)
            except OSError:
                p.errors += 1
                continue
            with entries:
                for entry in entries:
                    try:
                        st = entry.stat(follow_symlinks=self.follow_symlinks)
                        is_dir = entry.is_dir(follow_symlinks=self.follow_symlinks)
                    except OSError:
                        p.errors += 1
                        continue
                    if is_dir and entry.name in self.excludes:
                        continue
                    name = entry.name
                    ext = (
                        ""
                        if is_dir
                        else os.path.splitext(name)[1].lower().lstrip(".")
                    )
                    size = 0 if is_dir else st.st_size
                    batch.append(
                        (entry.path, current, name, ext, size, st.st_mtime,
                         1 if is_dir else 0)
                    )
                    if is_dir:
                        p.dirs += 1
                        if not stat.S_ISLNK(st.st_mode):
                            stack.append(entry.path)
                    else:
                        p.files += 1
                        p.total_size += size
                    if len(batch) >= BATCH_SIZE:
                        flush()
        flush()

        p.finished_at = time.time()
        p.running = False
        conn.execute(
            "INSERT OR REPLACE INTO roots"
            " (path, scanned_at, file_count, dir_count, total_size, duration_s)"
            " VALUES (?,?,?,?,?,?)",
            (root, p.finished_at, p.files, p.dirs, p.total_size,
             p.finished_at - p.started_at),
        )
        conn.commit()
        return p


def list_roots(db: Database) -> list[dict]:
    rows = db.connect().execute(
        "SELECT * FROM roots ORDER BY scanned_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def forget_root(db: Database, root: str) -> int:
    """Remove a root and all of its entries from the index."""
    root = os.path.abspath(root)
    prefix = root.rstrip(os.sep) + os.sep
    conn = db.connect()
    cur = conn.execute(
        "DELETE FROM files WHERE path = ? OR path LIKE ?",
        (root, prefix + "%"),
    )
    conn.execute("DELETE FROM roots WHERE path = ?", (root,))
    conn.commit()
    return cur.rowcount
