# Driving DiskButler as an agent

DiskButler exposes every capability as a small JSON API so an agent can
search, analyse, and safely tidy a user's disks. This file is the
contract; `GET /api/agent/manifest` returns the same information
machine-readably at runtime.

## Ground rules

1. **Never purge without explicit user confirmation.** Quarantining is
   reversible and safe to do on your own judgement; purging is not.
2. **Propose structure before moving files.** Show the user the target
   layout and the list of moves, then act.
3. **Poll async jobs.** `POST /api/index` and `POST /api/analyze/duplicates`
   return `{job_id}`. Poll `GET /api/jobs/<job_id>` until `status` is
   `done` (or `error`).
4. **Sizes are bytes, times are Unix epoch seconds.**

## Recommended workflow

1. `GET /api/status` — see which roots are already indexed.
2. `POST /api/index {"path": "..."}` for each drive/folder to organise;
   wait for the job to finish.
3. Understand the data:
   - `GET /api/analyze/extensions` — space by file type
   - `GET /api/analyze/largest` — biggest files
   - `GET /api/analyze/tree?path=...` — drill into where space goes
   - `GET /api/search?q=...` — locate specific things
4. Find reclaimable space:
   - `GET /api/analyze/junk` — categorised junk candidates
   - `POST /api/analyze/duplicates` — byte-exact duplicate groups
   - `GET /api/analyze/empty-dirs` — empty folders
5. Propose a plan to the user (a target folder structure + which items to
   quarantine). Get agreement.
6. `POST /api/quarantine {"paths": [...], "reason": "..."}` to clean.
   This is reversible.
7. On Windows, review system hygiene:
   - `GET /api/windows/leftovers` — folders no installed program claims
   - `GET /api/windows/startup` — autostart entries with an assessment
   - `GET /api/windows/services`, `GET /api/windows/tasks` — report-only,
     each includes a `disable_command` for the user to run as admin
8. Only after the user confirms nothing is missing:
   `POST /api/quarantine/purge {"batch_id": N, "confirm": true}`.

## Endpoint reference

| Method & path | Purpose |
|---|---|
| `GET /api/status` | App info + indexed roots |
| `POST /api/index` | Start indexing `{path}` → `{job_id}` |
| `POST /api/index/forget` | Drop a root from the index `{path}` |
| `GET /api/search` | `q, ext, under, min_size, max_size, is_dir, sort, limit, offset` |
| `GET /api/analyze/largest` | Largest files (`under`, `limit`) |
| `GET /api/analyze/extensions` | Size grouped by extension (`under`) |
| `GET /api/analyze/tree` | Children of `path` with recursive sizes |
| `GET /api/analyze/empty-dirs` | Empty directories (`under`) |
| `GET /api/analyze/junk` | Junk candidates by category (`under`) |
| `POST /api/analyze/duplicates` | Duplicate scan `{under?, min_size?}` → `{job_id}` |
| `GET /api/jobs` / `GET /api/jobs/<id>` | Background job status/result |
| `GET /api/windows/programs` | Installed programs |
| `GET /api/windows/leftovers` | Orphaned program folders |
| `GET /api/windows/startup` | Autostart entries + assessment |
| `GET /api/windows/services` | Services + assessment (report-only) |
| `GET /api/windows/tasks` | Non-Microsoft scheduled tasks (report-only) |
| `POST /api/windows/startup/disable` | Disable one autostart entry `{kind, location, name, confirm:true}` |
| `POST /api/quarantine` | Move paths to quarantine `{paths, reason?}` |
| `GET /api/quarantine` | List quarantine batches |
| `GET /api/quarantine/items` | Items of a batch (`batch_id`) |
| `POST /api/quarantine/restore` | Restore a batch `{batch_id}` |
| `POST /api/quarantine/purge` | Permanently delete `{batch_id, confirm:true}` |
| `GET /api/agent/manifest` | This list, machine-readable |

## Error conventions

- `400` bad/missing parameters
- `404` unknown route or job
- `428` a confirmation flag is required (purge, autostart disable)
- `501` a Windows-only feature was called on a non-Windows host
- `500` unexpected server error (message in `{"error": ...}`)
