"""Query layer over the file index.

Two strategies, picked automatically:

- FTS5 prefix match (`report*`) — instant even on millions of rows,
  used for queries that are plain words.
- LIKE substring fallback — used when the query contains characters
  FTS treats as syntax, so arbitrary substrings still work.
"""

from __future__ import annotations

import os
import re

from .db import Database

_SORTS = {
    "name": "name COLLATE NOCASE ASC",
    "size": "size DESC",
    "mtime": "mtime DESC",
    "path": "path ASC",
}

# A term is FTS-eligible only if it is a run of alphanumerics (unicode
# letters/digits, no underscore or punctuation). Anything else — a term
# with '-', '.', '_', or wildcards — is treated as a substring query and
# routed to LIKE, which matches inside tokens where FTS prefixes cannot.
_FTS_SAFE = re.compile(r"^[^\W_]+$", re.UNICODE)


def _fts_query(q: str) -> str | None:
    """Build an FTS5 prefix-match expression, or None if the query is
    better served by a LIKE substring search."""
    terms = q.split()
    if not terms or not all(_FTS_SAFE.match(t) for t in terms):
        return None
    return " ".join(f'"{t}"*' for t in terms)


def search(
    db: Database,
    q: str = "",
    ext: str | None = None,
    under: str | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    is_dir: bool | None = None,
    sort: str = "name",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    where: list[str] = []
    args: list = []

    fts = _fts_query(q) if q else None
    if fts is not None:
        where.append(
            "id IN (SELECT rowid FROM files_fts WHERE files_fts MATCH ?)"
        )
        args.append(fts)
    elif q:
        where.append("name LIKE ? ESCAPE '\\'")
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        args.append(f"%{escaped}%")

    if ext:
        where.append("ext = ?")
        args.append(ext.lower().lstrip("."))
    if under:
        where.append("(path = ? OR path LIKE ?)")
        args += [under, under.rstrip("/\\") + os.sep + "%"]
    if min_size is not None:
        where.append("size >= ?")
        args.append(min_size)
    if max_size is not None:
        where.append("size <= ?")
        args.append(max_size)
    if is_dir is not None:
        where.append("is_dir = ?")
        args.append(1 if is_dir else 0)

    sql = "SELECT path, name, ext, size, mtime, is_dir FROM files"
    count_sql = "SELECT COUNT(*) FROM files"
    if where:
        clause = " WHERE " + " AND ".join(where)
        sql += clause
        count_sql += clause
    sql += f" ORDER BY {_SORTS.get(sort, _SORTS['name'])} LIMIT ? OFFSET ?"

    conn = db.connect()
    total = conn.execute(count_sql, args).fetchone()[0]
    rows = conn.execute(sql, args + [limit, offset]).fetchall()
    return {
        "total": total,
        "results": [dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
    }
