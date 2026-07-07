"""SQLite storage layer.

One database file holds the file index (with an FTS5 mirror for
instant name search), the list of indexed roots, and the quarantine
manifest. All timestamps are Unix epoch seconds.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id     INTEGER PRIMARY KEY,
    path   TEXT NOT NULL UNIQUE,
    parent TEXT NOT NULL,
    name   TEXT NOT NULL,
    ext    TEXT NOT NULL DEFAULT '',
    size   INTEGER NOT NULL DEFAULT 0,
    mtime  REAL NOT NULL DEFAULT 0,
    is_dir INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent);
CREATE INDEX IF NOT EXISTS idx_files_ext    ON files(ext);
CREATE INDEX IF NOT EXISTS idx_files_size   ON files(size);

-- Default unicode61 tokenizer: punctuation (._-) splits tokens, so
-- "2024-invoice.pdf" indexes as [2024, invoice, pdf] and a prefix query
-- like "invo*" finds it. Substring-in-the-middle queries fall back to
-- LIKE in the search layer.
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    name,
    content='files',
    content_rowid='id'
);

-- Keep the FTS mirror in sync automatically. This is the canonical
-- external-content pattern from the SQLite docs, and it means no other
-- code ever has to touch files_fts by hand.
CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(rowid, name) VALUES (new.id, new.name);
END;
CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, name) VALUES('delete', old.id, old.name);
END;
CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, name) VALUES('delete', old.id, old.name);
    INSERT INTO files_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TABLE IF NOT EXISTS roots (
    path       TEXT PRIMARY KEY,
    scanned_at REAL NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    dir_count  INTEGER NOT NULL DEFAULT 0,
    total_size INTEGER NOT NULL DEFAULT 0,
    duration_s REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quarantine_batches (
    id         INTEGER PRIMARY KEY,
    created_at REAL NOT NULL,
    reason     TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'quarantined'
);

CREATE TABLE IF NOT EXISTS quarantine_items (
    id            INTEGER PRIMARY KEY,
    batch_id      INTEGER NOT NULL REFERENCES quarantine_batches(id),
    original_path TEXT NOT NULL,
    stored_path   TEXT NOT NULL,
    size          INTEGER NOT NULL DEFAULT 0,
    is_dir        INTEGER NOT NULL DEFAULT 0
);
"""


def default_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "DiskButler")
    return os.path.join(os.path.expanduser("~"), ".diskbutler")


class Database:
    """Thread-safe wrapper: one connection per thread, shared file."""

    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or default_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)
        self.path = os.path.join(self.data_dir, "index.sqlite3")
        self._local = threading.local()
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
