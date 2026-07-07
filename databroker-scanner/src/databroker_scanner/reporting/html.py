"""Self-contained HTML report via Jinja2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_html(matches: list[dict], person_name: str, path: str | Path) -> Path:
    """Render the dashboard report to ``path`` and return it."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.j2")
    found = [m for m in matches if m["status"] == "found"]
    optout = [m for m in matches if m["status"] == "optout_only"]
    html = template.render(
        matches=matches,
        found=found,
        optout=optout,
        person_name=person_name or "(unnamed)",
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
