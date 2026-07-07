---
name: organize-disk
description: Drive DiskButler to search, analyse, and safely tidy a user's local drives — find files fast, reclaim space from junk and duplicates, and clean up Windows leftovers/autostart. Use when the user wants to organise their disk, clean up file chaos, find duplicates, free space, or find dead program remnants.
---

You are helping the user tidy their local disks with **DiskButler**, a
local search + cleanup tool in `tools/disk-butler`. It indexes files into
SQLite/FTS5 for instant search and exposes a JSON API. Your job is to plan
an organisation strategy and execute it through that API — safely.

## Golden rule

**Cleaning is reversible; purging is not.** Quarantining (moving files to
a restorable holding area) is safe to do on your own judgement once the
user has agreed to a plan. **Never purge (permanently delete) without the
user's explicit, specific confirmation.**

## Getting the server running

If it isn't already up, start it and use `http://127.0.0.1:8177`:

```bash
cd tools/disk-butler && python -m diskbutler serve
```

No dependencies are needed (pure standard library, Python 3.9+). Fetch
`GET /api/agent/manifest` once to confirm the API surface.

## Workflow

1. **Orient.** `GET /api/status` to see indexed roots. If the target
   drive/folder isn't indexed, `POST /api/index {"path": "..."}` and poll
   `GET /api/jobs/<job_id>` until `status: done`.
2. **Understand the mess before touching anything.**
   - `GET /api/analyze/extensions` — what file types eat the space
   - `GET /api/analyze/largest` — the biggest single offenders
   - `GET /api/analyze/tree?path=...` — drill into where space goes
   - `GET /api/search?q=...&ext=...&sort=size` — locate specific things
3. **Find reclaimable space.**
   - `GET /api/analyze/junk` — temp files, crash dumps, old installers,
     stale logs, `Thumbs.db`/`.DS_Store`, backup leftovers
   - `POST /api/analyze/duplicates {"min_size": 1048576}` — byte-exact
     duplicate groups (poll the job)
   - `GET /api/analyze/empty-dirs`
4. **Propose, don't surprise.** Summarise findings and present a concrete
   plan: a target folder structure and the exact list of items you intend
   to quarantine, with total space to reclaim. Get the user's agreement.
5. **Execute the tidy.** `POST /api/quarantine {"paths": [...],
   "reason": "..."}`. This moves the files to quarantine and removes them
   from the index; it is fully reversible via
   `POST /api/quarantine/restore {"batch_id": N}`.
6. **Windows hygiene (if on Windows).**
   - `GET /api/windows/leftovers` — folders no installed program claims
   - `GET /api/windows/startup` — autostart entries with an assessment;
     disable unwanted ones via `POST /api/windows/startup/disable
     {kind, location, name, confirm: true}` (a backup is kept)
   - `GET /api/windows/services` and `GET /api/windows/tasks` are
     **report-only**. Do not try to change them. Relay the provided
     `disable_command` and the assessment so the user can decide.
7. **Free the space — only on explicit go-ahead.** After the user has
   verified nothing important is missing from quarantine, and confirms in
   words, `POST /api/quarantine/purge {"batch_id": N, "confirm": true}`.

## Judgement notes

- Treat every `assessment` and junk `category` as a heuristic, not a
  verdict. When a file could plausibly matter (documents, media, anything
  under the user's home), surface it for review rather than auto-cleaning.
- For duplicates, keep the copy in the most sensible location (e.g. the
  organised library, not `Downloads`); the GUI pre-selects all but one.
- Sizes are bytes; times are Unix epoch seconds. Report human-readable
  figures back to the user.
- Prefer many small, clearly-labelled quarantine batches (by reason) over
  one giant batch — it makes selective restore trivial.

See `tools/disk-butler/AGENTS.md` for the full endpoint contract and error
conventions.
