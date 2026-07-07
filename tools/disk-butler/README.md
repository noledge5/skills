# 💾 DiskButler

Fast local disk search, analysis, and **safe** cleanup — with a web GUI
and a REST API built for a Claude agent to drive.

Built for the "my drives are a mess" problem: find anything instantly
(faster than Windows Search), see where your space actually goes, and
clean up junk, duplicates, dead program leftovers, and unnecessary
Windows autostart entries / services — without ever losing a file by
accident.

- **Zero dependencies.** Pure Python standard library (3.9+). Nothing to
  `pip install`.
- **Instant search.** A SQLite + FTS5 index makes name search return in
  milliseconds across millions of files.
- **Safe by construction.** Nothing is ever deleted directly. "Cleaning"
  moves files into a restorable *quarantine*; space is only freed when
  you explicitly *purge* a batch.
- **Agent-ready.** `GET /api/agent/manifest` describes every endpoint so
  a Claude agent can plan and execute an organisation strategy.

## Quick start

```bash
cd tools/disk-butler

# 1. Index a drive or folder (Windows: a drive like C:\, or any folder)
python -m diskbutler index "C:\Users\You"

# 2. Start the GUI + API server, then open http://127.0.0.1:8177
python -m diskbutler serve
```

Or search straight from the terminal:

```bash
python -m diskbutler search "rechnung 2024"
python -m diskbutler search "" --ext iso --sort size   # all ISOs, biggest first
python -m diskbutler junk                               # what can be cleaned
```

## The GUI

Open `http://127.0.0.1:8177` after `serve`. Six tabs:

| Tab | What it does |
|-----|--------------|
| 🔎 **Suche** | Search-as-you-type over the index; filter by type, sort by size/date; kick off indexing of new drives. |
| 📊 **Analyse** | Space by file type, largest files, empty folders — the "where did my space go" view. |
| 🧬 **Duplikate** | Byte-exact duplicate finder (size → head hash → full SHA-256). Pre-selects all but one copy of each group for quarantine. |
| 🧹 **Junk** | Temp files, crash dumps, old installers, stale big logs, `Thumbs.db`/`.DS_Store`, backup leftovers. |
| 🪟 **Windows** | Installed programs, orphaned program folders, autostart entries, services, scheduled tasks — each with a plain-language assessment. |
| 📦 **Quarantäne** | Everything you cleaned. Restore a batch, or purge it to actually free the space. |

## Safety model

1. **Search & analysis are read-only.** They only ever read the index or
   hash files.
2. **Cleanup = quarantine.** `POST /api/quarantine` *moves* paths into
   `<data-dir>/quarantine/batch-N/` and records where each came from.
   The file is gone from its old spot (and the search index) but fully
   recoverable.
3. **Restore** puts a whole batch back where it came from.
4. **Purge** permanently deletes a batch and frees the space. It requires
   `confirm: true` and is the only irreversible operation.
5. **Protected paths.** Drive roots, the user home directory, and the
   Windows directory can never be quarantined.
6. **Windows services and scheduled tasks are report-only.** DiskButler
   never changes them; it shows you the exact `sc`/`schtasks` command an
   administrator can review and run. Only registry `Run` keys and
   Startup-folder items can be disabled from the app (with a backup).

## Data location

- Windows: `%LOCALAPPDATA%\DiskButler`
- macOS/Linux: `~/.diskbutler`

Holds `index.sqlite3` and the `quarantine/` folder. Override with
`--data-dir`.

## The agent API

Every capability is a JSON endpoint under `/api/`. Long jobs (indexing,
duplicate scans) return `{ "job_id": ... }`; poll `GET /api/jobs/<id>`
until `status` is `done`. Full, machine-readable list:

```bash
curl http://127.0.0.1:8177/api/agent/manifest
```

See [`AGENTS.md`](./AGENTS.md) for the recommended agent workflow, and the
[`organize-disk`](../../skills/productivity/organize-disk/SKILL.md) skill
for a ready-made Claude playbook.

## Tests

```bash
python -m unittest discover -s tests -v
```

Covers indexing, both search paths, all analyses, the quarantine
round-trip, protected-path refusal, and the HTTP API end to end.
