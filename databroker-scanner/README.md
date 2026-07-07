# DataBrokerScanner

A **consent-based personal privacy self-audit**. It helps you find where your
own publicly available data shows up on people-search and data-broker sites, and
gives you the direct **opt-out / data-access link** for each one.

> **What it does not do:** it does not automate logins, it does not solve
> CAPTCHAs, and it does not circumvent bot-protection. It only surfaces
> publicly accessible information and the corresponding removal process. Sites
> that disallow automation are handled in an **assisted** (human-in-the-loop)
> mode — you browse them yourself in a real, visible window and the tool records
> what you confirm.

## Why "assisted" instead of an evasion engine

Bot-protection on broker sites is aimed at bulk/automated scraping, not at a
person looking themselves up. As a human in a normal browser you can already see
your own public listing — so the assisted mode reaches everything you could
reach by hand, with **no evasion**. An anti-detection engine would not
meaningfully widen *your* coverage (and modern protections defeat it anyway),
but it *would* turn the project into a general-purpose tool for finding
**anyone** at scale. That trade-off isn't worth it, so the tool deliberately
doesn't ship one. See `PLAN.md` §2.2 for the full reasoning.

## Install

```bash
python -m pip install -e .            # core (opt-out worklist + reports)
python -m pip install -e ".[browser]" # adds the browser tier (later phases)
python -m pip install -e ".[dev]"     # tests, lint, typecheck
```

Python 3.11+.

## Quick start

```bash
# 1) Build an opt-out worklist for yourself across all brokers
scanner search --firstname Jane --lastname Doe --city Austin --state TX

# 2) See every broker and its opt-out link
scanner brokers --country US

# 3) Generate the HTML dashboard and structured exports
scanner report            # -> reports/report_<id>.html
scanner export --format all
```

On first run you must accept a short consent statement confirming you are
auditing **your own** data (or have a documented lawful basis). This is recorded
locally.

## CLI

| Command | Purpose |
|---|---|
| `scanner search` | Build an opt-out worklist for a person |
| `scanner brokers` | List configured brokers (filter with `--country`) |
| `scanner report` | Render the self-contained HTML dashboard |
| `scanner export` | Export CSV / JSON / Markdown (`--format`) |
| `scanner resume` | Resume an interrupted browser scan (Phase 2+) |

## Configuration

Copy `config.example.yaml` to `config.yaml` (gitignored) and adjust. Defaults are
deliberately conservative (`parallel: 2`, polite per-domain delay).

## Adding a broker

Add one entry to `src/databroker_scanner/brokers/registry.yaml`. That's it for
`assisted` / `optout_only` brokers — no code required. An `automated` broker
that needs custom HTML parsing additionally gets a small Python file under
`brokers/automated/` (a `Broker` subclass decorated with `@register`), which is
auto-discovered. The core never changes.

## Output

- **HTML** dashboard with filter/search and per-broker opt-out buttons.
- **CSV / JSON / Markdown** exports.
- **SQLite** database (`results/scanner.db`) with persons, scans, matches.

All of these contain personal data and are **gitignored** — do not commit them.

## Roadmap

See `PLAN.md`. Phase 1 (this release): opt-out worklist + reports, no browser.
Phase 2: assisted browser mode with screenshots, CAPTCHA-pause and resume.
Phase 3: `automated` brokers (only where robots.txt permits) with confidence
scoring. Phase 4: polish.

## FAQ

**Does this remove my data?** No — it finds listings and hands you the opt-out
link. Removal is a request you submit to each broker.

**Is scraping these sites legal?** It's a grey area and varies by jurisdiction
and each site's ToS. This tool is scoped to auditing *your own* data and respects
`robots.txt`; sites that disallow automation are only ever opened by you, by hand.

## Disclaimer

Provided for personal privacy self-defense. You are responsible for using it
lawfully and only for your own data (or with documented consent). Opt-out URLs
marked unverified in the registry should be checked before use. No warranty; see
`LICENSE`.

## License

MIT — see `LICENSE`.
