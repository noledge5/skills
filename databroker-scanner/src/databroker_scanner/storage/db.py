"""SQLite persistence.

A thin repository over ``sqlite3`` — no ORM for v1. All personal data lives in
this single file; keep it out of version control (see .gitignore).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ..models import Match, Person, ScanRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acknowledged_at TEXT NOT NULL,
    statement_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    firstname TEXT, lastname TEXT, middlename TEXT,
    phone TEXT, email TEXT, city TEXT, state TEXT, country TEXT, zipcode TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    config_snapshot TEXT
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id INTEGER NOT NULL REFERENCES scan_runs(id),
    broker_slug TEXT NOT NULL,
    broker_name TEXT NOT NULL,
    status TEXT NOT NULL,
    profile_name TEXT,
    profile_url TEXT,
    search_term TEXT,
    screenshot_path TEXT,
    optout_url TEXT,
    optout_type TEXT,
    confidence INTEGER NOT NULL DEFAULT 0,
    confidence_band TEXT,
    found_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_matches_run ON matches(scan_run_id);
"""


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    """Owns the SQLite connection and exposes typed repository operations."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- consent -------------------------------------------------------------
    def record_consent(self, statement_version: str) -> None:
        self.conn.execute(
            "INSERT INTO consent (acknowledged_at, statement_version) VALUES (?, ?)",
            (_utcnow_iso(), statement_version),
        )
        self.conn.commit()

    def has_consent(self, statement_version: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM consent WHERE statement_version = ? LIMIT 1",
            (statement_version,),
        ).fetchone()
        return row is not None

    # --- persons / runs ------------------------------------------------------
    def add_person(self, person: Person) -> int:
        cur = self.conn.execute(
            """INSERT INTO persons
               (firstname, lastname, middlename, phone, email, city, state,
                country, zipcode, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                person.firstname, person.lastname, person.middlename, person.phone,
                person.email, person.city, person.state, person.country,
                person.zipcode, _utcnow_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def start_run(self, person_id: int, config_snapshot: str) -> int:
        cur = self.conn.execute(
            """INSERT INTO scan_runs (person_id, started_at, status, config_snapshot)
               VALUES (?,?,?,?)""",
            (person_id, _utcnow_iso(), "running", config_snapshot),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str = "done") -> None:
        self.conn.execute(
            "UPDATE scan_runs SET finished_at = ?, status = ? WHERE id = ?",
            (_utcnow_iso(), status, run_id),
        )
        self.conn.commit()

    def latest_run_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM scan_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row["id"]) if row else None

    # --- matches -------------------------------------------------------------
    def add_match(self, run_id: int, match: Match) -> None:
        self.conn.execute(
            """INSERT INTO matches
               (scan_run_id, broker_slug, broker_name, status, profile_name,
                profile_url, search_term, screenshot_path, optout_url, optout_type,
                confidence, confidence_band, found_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, match.broker_slug, match.broker_name, match.status.value,
                match.profile_name, match.profile_url, match.search_term,
                match.screenshot_path, match.optout_url,
                match.optout_type.value if match.optout_type else None,
                match.confidence, match.confidence_band.value,
                match.found_at.isoformat(),
            ),
        )
        self.conn.commit()

    def matches_for_run(self, run_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM matches WHERE scan_run_id = ? ORDER BY confidence DESC, broker_name",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def scanned_slugs(self, run_id: int) -> set[str]:
        """Broker slugs already recorded for a run — used for resume."""
        rows = self.conn.execute(
            "SELECT DISTINCT broker_slug FROM matches WHERE scan_run_id = ?",
            (run_id,),
        ).fetchall()
        return {r["broker_slug"] for r in rows}

    def run_person(self, run_id: int) -> ScanRun | None:
        row = self.conn.execute(
            """SELECT s.*, p.firstname, p.lastname, p.middlename, p.phone, p.email,
                      p.city, p.state, p.country, p.zipcode
               FROM scan_runs s JOIN persons p ON p.id = s.person_id
               WHERE s.id = ?""",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        person = Person(
            firstname=row["firstname"], lastname=row["lastname"],
            middlename=row["middlename"], phone=row["phone"], email=row["email"],
            city=row["city"], state=row["state"], country=row["country"],
            zipcode=row["zipcode"],
        )
        return ScanRun(id=row["id"], person=person, status=row["status"])
