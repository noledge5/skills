"""Analysis over the index: where the space goes and what is junk.

Duplicate detection reads the live filesystem (size groups → 64 KiB
head hash → full SHA-256) so it never flags false positives. Everything
else is pure SQL over the index and therefore instant.
"""

from __future__ import annotations

import hashlib
import os
import time

from .db import Database

_HEAD_BYTES = 64 * 1024


def _under_clause(under: str | None) -> tuple[str, list]:
    if not under:
        return "", []
    return " AND (path = ? OR path LIKE ?)", [
        under, under.rstrip("/\\") + os.sep + "%",
    ]


def largest_files(db: Database, under: str | None = None, limit: int = 50) -> list[dict]:
    clause, args = _under_clause(under)
    rows = db.connect().execute(
        "SELECT path, name, ext, size, mtime FROM files"
        f" WHERE is_dir = 0{clause} ORDER BY size DESC LIMIT ?",
        args + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def extension_stats(db: Database, under: str | None = None, limit: int = 30) -> list[dict]:
    clause, args = _under_clause(under)
    rows = db.connect().execute(
        "SELECT ext, COUNT(*) AS count, SUM(size) AS total_size FROM files"
        f" WHERE is_dir = 0{clause}"
        " GROUP BY ext ORDER BY total_size DESC LIMIT ?",
        args + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def tree_sizes(db: Database, path: str) -> list[dict]:
    """Direct children of *path* with their recursive sizes — the data
    behind a 'where does my space go' drill-down."""
    conn = db.connect()
    children = conn.execute(
        "SELECT path, name, size, is_dir FROM files WHERE parent = ?",
        (path,),
    ).fetchall()
    out = []
    for c in children:
        entry = dict(c)
        if c["is_dir"]:
            row = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS s"
                " FROM files WHERE is_dir = 0 AND"
                " (path LIKE ?)",
                (c["path"].rstrip("/\\") + os.sep + "%",),
            ).fetchone()
            entry["size"] = row["s"]
            entry["file_count"] = row["n"]
        out.append(entry)
    out.sort(key=lambda e: e["size"], reverse=True)
    return out


def empty_dirs(db: Database, under: str | None = None, limit: int = 500) -> list[str]:
    """Directories with no descendants in the index."""
    clause, args = _under_clause(under)
    rows = db.connect().execute(
        "SELECT d.path FROM files d WHERE d.is_dir = 1"
        f"{clause}"
        " AND NOT EXISTS (SELECT 1 FROM files c WHERE c.parent = d.path)"
        " ORDER BY d.path LIMIT ?",
        args + [limit],
    ).fetchall()
    return [r["path"] for r in rows]


def _hash_file(path: str, head_only: bool) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            if head_only:
                h.update(f.read(_HEAD_BYTES))
            else:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def duplicates(
    db: Database,
    under: str | None = None,
    min_size: int = 1024 * 1024,
    limit_groups: int = 200,
    progress: dict | None = None,
) -> list[dict]:
    """Groups of byte-identical files, largest waste first."""
    clause, args = _under_clause(under)
    rows = db.connect().execute(
        "SELECT path, size FROM files WHERE is_dir = 0 AND size >= ?"
        f"{clause}"
        " AND size IN (SELECT size FROM files WHERE is_dir = 0 AND size >= ?"
        f"{clause} GROUP BY size HAVING COUNT(*) > 1)"
        " ORDER BY size DESC",
        [min_size] + args + [min_size] + args,
    ).fetchall()

    by_size: dict[int, list[str]] = {}
    for r in rows:
        by_size.setdefault(r["size"], []).append(r["path"])

    groups: list[dict] = []
    done = 0
    for size, paths in by_size.items():
        if len(groups) >= limit_groups:
            break
        by_head: dict[str, list[str]] = {}
        for p in paths:
            h = _hash_file(p, head_only=True)
            if h:
                by_head.setdefault(h, []).append(p)
        for candidates in by_head.values():
            if len(candidates) < 2:
                continue
            by_full: dict[str, list[str]] = {}
            for p in candidates:
                h = _hash_file(p, head_only=False)
                if h:
                    by_full.setdefault(h, []).append(p)
            for digest, same in by_full.items():
                if len(same) >= 2:
                    groups.append({
                        "size": size,
                        "sha256": digest,
                        "paths": sorted(same),
                        "wasted_bytes": size * (len(same) - 1),
                    })
        done += len(paths)
        if progress is not None:
            progress["checked"] = done
            progress["total"] = len(rows)
            progress["groups"] = len(groups)

    groups.sort(key=lambda g: g["wasted_bytes"], reverse=True)
    return groups


# --- Junk detection ---------------------------------------------------

# (label, SQL condition, extra args factory). Conservative on purpose:
# everything here is either regenerated automatically or explicitly
# temporary. Deletion still goes through quarantine.
_NOW = time.time


def junk_candidates(db: Database, under: str | None = None, limit: int = 2000) -> list[dict]:
    clause, args = _under_clause(under)
    ninety_days_ago = _NOW() - 90 * 86400
    rules = [
        ("temp_file", "ext IN ('tmp','temp','~tmp') OR name LIKE '~$%'", []),
        ("backup_leftover", "ext IN ('bak','old','orig')", []),
        ("crash_dump", "ext IN ('dmp','mdmp','hdmp')", []),
        ("windows_thumbnail", "name IN ('Thumbs.db','ehthumbs.db')", []),
        ("macos_metadata", "name = '.DS_Store'", []),
        ("log_file_old", "ext = 'log' AND mtime < ? AND size > 1048576",
         [ninety_days_ago]),
        ("old_installer",
         "ext IN ('msi','exe') AND mtime < ?"
         " AND (parent LIKE '%Downloads%' OR parent LIKE '%downloads%')"
         " AND (name LIKE '%setup%' OR name LIKE '%install%'"
         "      OR name LIKE '%.msi')",
         [ninety_days_ago]),
        ("temp_dir_content",
         "(parent LIKE '%\\Temp\\%' OR parent LIKE '%\\Temp'"
         " OR parent LIKE '%/tmp/%')",
         []),
    ]
    conn = db.connect()
    # A file can satisfy several rules; count it once under the first
    # (most specific) rule that matches, so the reclaimable total never
    # double-counts.
    seen: set[str] = set()
    out: list[dict] = []
    for label, cond, extra in rules:
        rows = conn.execute(
            "SELECT path, name, size, mtime FROM files"
            f" WHERE is_dir = 0 AND ({cond}){clause}"
            " ORDER BY size DESC LIMIT ?",
            extra + args + [limit],
        ).fetchall()
        for r in rows:
            if r["path"] in seen:
                continue
            seen.add(r["path"])
            out.append({"category": label, **dict(r)})
    out.sort(key=lambda e: e["size"], reverse=True)
    return out[:limit]
