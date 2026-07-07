"""Command-line interface.

Phase 1 scope: a complete opt-out worklist without a browser. For every enabled
broker the tool records the opt-out link and a pre-filled search URL, so the
user gets an actionable checklist immediately. Browser-driven ``assisted`` and
``automated`` scanning arrives in later phases behind the ``[browser]`` extra.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Settings
from .consent import ConsentRequired, ensure_consent
from .core.broker import Broker
from .models import Match, MatchStatus, Person
from .registry import load_brokers
from .reporting import exporters, html
from .storage.db import Database

app = typer.Typer(add_completion=False, help="Personal privacy self-audit for data-broker sites.")
console = Console()


def _person_from_opts(**kwargs: str | None) -> Person:
    return Person(**{k: v for k, v in kwargs.items() if v})


def _worklist_match(broker: Broker, person: Person) -> Match:
    """Build the Phase-1 record for a broker: opt-out link + manual search URL."""
    if broker.meta.mode.value == "optout_only":
        return broker.optout_match(person)
    search_url = broker.build_search_url(person) or broker.meta.website
    return Match(
        broker_slug=broker.slug,
        broker_name=broker.name,
        status=MatchStatus.NEEDS_REVIEW,
        search_term=person.full_name() or None,
        profile_url=search_url,
        optout_url=broker.meta.optout_url,
        optout_type=broker.meta.optout_type,
    )


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"DataBrokerScanner {__version__}")


@app.command()
def brokers(
    country: str | None = typer.Option(None, help="Filter by country code, e.g. US or DE."),
) -> None:
    """List the configured brokers."""
    table = Table(title="Brokers")
    for col in ("Slug", "Name", "Country", "Mode", "Verified", "Opt-out URL"):
        table.add_column(col)
    for b in load_brokers():
        if country and b.meta.country.upper() != country.upper():
            continue
        table.add_row(
            b.slug, b.name, b.meta.country, b.meta.mode.value,
            "✓" if b.meta.verified else "?", b.meta.optout_url,
        )
    console.print(table)


@app.command()
def search(
    firstname: str | None = typer.Option(None),
    lastname: str | None = typer.Option(None),
    middlename: str | None = typer.Option(None),
    city: str | None = typer.Option(None),
    state: str | None = typer.Option(None),
    country: str | None = typer.Option(None),
    zipcode: str | None = typer.Option(None),
    phone: str | None = typer.Option(None),
    email: str | None = typer.Option(None),
    config: Path | None = typer.Option(None, help="Path to config.yaml."),
    yes: bool = typer.Option(
        False, "--yes", help="Accept the consent statement non-interactively."
    ),
) -> None:
    """Build an opt-out worklist for a person across all enabled brokers."""
    settings = Settings.load(config)
    person = _person_from_opts(
        firstname=firstname, lastname=lastname, middlename=middlename, city=city,
        state=state, country=country, zipcode=zipcode, phone=phone, email=email,
    )
    if not person.provided_fields():
        console.print("[red]Provide at least one field (e.g. --firstname/--lastname).[/red]")
        raise typer.Exit(2)

    with Database(settings.db_path) as db:
        try:
            ensure_consent(db, assume_yes=yes)
        except ConsentRequired as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        person_id = db.add_person(person)
        run_id = db.start_run(person_id, json.dumps(person.provided_fields()))
        broker_list = load_brokers()
        for broker in broker_list:
            db.add_match(run_id, _worklist_match(broker, person))
        db.finish_run(run_id)

    subject = person.full_name() or "subject"
    console.print(
        f"[green]Scan {run_id} complete[/green] for [bold]{subject}[/bold]: "
        f"{len(broker_list)} brokers recorded."
    )
    console.print(
        f"Next: [cyan]scanner report --run {run_id}[/cyan] "
        f"or [cyan]scanner export --run {run_id}[/cyan]"
    )


@app.command()
def report(
    run: int | None = typer.Option(None, help="Scan run id (default: latest)."),
    config: Path | None = typer.Option(None),
    output: Path | None = typer.Option(None, help="Output HTML path."),
) -> None:
    """Render the HTML dashboard for a scan run."""
    settings = Settings.load(config)
    with Database(settings.db_path) as db:
        run_id = run or db.latest_run_id()
        if run_id is None:
            console.print("[red]No scan runs found. Run 'scanner search' first.[/red]")
            raise typer.Exit(1)
        matches = db.matches_for_run(run_id)
        scan = db.run_person(run_id)
    name = scan.person.full_name() if scan else ""
    out = output or Path(settings.output_dir) / f"report_{run_id}.html"
    path = html.render_html(matches, name, out)
    console.print(f"[green]Report written:[/green] {path}")


@app.command()
def export(
    fmt: str = typer.Option("all", "--format", help="csv | json | md | all"),
    run: int | None = typer.Option(None),
    config: Path | None = typer.Option(None),
) -> None:
    """Export a scan run to CSV / JSON / Markdown."""
    settings = Settings.load(config)
    with Database(settings.db_path) as db:
        run_id = run or db.latest_run_id()
        if run_id is None:
            console.print("[red]No scan runs found.[/red]")
            raise typer.Exit(1)
        matches = db.matches_for_run(run_id)
    out_dir = Path(settings.output_dir)
    written = []
    if fmt in ("csv", "all"):
        written.append(exporters.to_csv(matches, out_dir / f"report_{run_id}.csv"))
    if fmt in ("json", "all"):
        written.append(exporters.to_json(matches, out_dir / f"report_{run_id}.json"))
    if fmt in ("md", "all"):
        written.append(exporters.to_markdown(matches, out_dir / f"report_{run_id}.md"))
    if not written:
        console.print(f"[red]Unknown format '{fmt}'.[/red]")
        raise typer.Exit(2)
    for p in written:
        console.print(f"[green]Wrote:[/green] {p}")


@app.command()
def resume() -> None:
    """Resume an interrupted browser scan (Phase 2+; not yet available)."""
    console.print(
        "[yellow]Resume requires the browser tier (Phase 2). Not yet implemented.[/yellow]"
    )


if __name__ == "__main__":
    app()
