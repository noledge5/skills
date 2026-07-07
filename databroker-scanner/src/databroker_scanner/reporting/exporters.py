"""Structured exporters: CSV, JSON, Markdown."""

from __future__ import annotations

import csv
import json
from pathlib import Path

_CSV_COLUMNS = [
    "broker_name", "profile_name", "profile_url", "screenshot_path",
    "optout_url", "status", "confidence", "found_at",
]


def to_csv(matches: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(matches)
    return path


def to_json(matches: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(matches, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def to_markdown(matches: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# DataBrokerScanner report",
        "",
        "| Broker | Status | Confidence | Opt-out |",
        "|---|---|---|---|",
    ]
    for m in matches:
        optout = f"[link]({m['optout_url']})" if m.get("optout_url") else "—"
        lines.append(
            f"| {m['broker_name']} | {m['status']} | {m.get('confidence', 0)} | {optout} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
