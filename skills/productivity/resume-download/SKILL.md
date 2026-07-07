---
name: resume-download
description: Download huge files (multi-GB model weights, datasets, ISOs) over HTTP with automatic resume after pauses, crashes, or network drops. Use when a download is too large or flaky for the browser, keeps aborting mid-transfer, or the user wants to pause and continue a download later — e.g. pulling 20+ GB transformer weights.
---

# Resume Download

Downloads via `scripts/resume_download.py` (Python 3.8+, stdlib only). Progress
is written to `<output>.part`; every interruption — Ctrl+C, network drop,
reboot — is resumable by re-running the exact same command. Transient errors
retry automatically with exponential backoff, so for flaky connections you can
start it and walk away.

## Quick start

```bash
python3 scripts/resume_download.py "https://example.com/model.safetensors"
```

Interrupted? Run the same command again — it continues from the last byte.

## Options

| Flag | Purpose |
| --- | --- |
| `-o FILE` | Output path (default: filename from URL or server) |
| `-H 'Name: value'` | Extra header, repeatable (auth tokens etc.) |
| `--sha256 HEX` | Verify checksum after download |
| `--max-retries N` | Consecutive no-progress attempts before giving up (default 100; resets whenever bytes arrive) |

## Recipes

Gated Hugging Face file (single weights file, not the whole repo):

```bash
python3 scripts/resume_download.py \
  "https://huggingface.co/ORG/MODEL/resolve/main/model-00001-of-00005.safetensors" \
  -H "Authorization: Bearer $HF_TOKEN"
```

Long download in the background, checking in later:

```bash
nohup python3 scripts/resume_download.py "$URL" -o model.bin > dl.log 2>&1 &
tail -f dl.log
```

## Behaviour worth knowing

- Requires the server to support HTTP Range requests (almost all CDNs,
  Hugging Face, GitHub releases do). If not, the script warns and restarts
  from zero rather than corrupting the file.
- An `If-Range` validator (ETag/Last-Modified, stored in `<output>.part.json`)
  guards against splicing two different versions of the remote file together.
- Permanent errors (403, 404, …) fail immediately; only timeouts, connection
  drops, 408/429, and 5xx are retried.
- The final file only appears under its real name once complete — a plain
  `test -f model.bin` tells you whether it's done.

## When to reach for something else

- Whole Hugging Face repos with many files: `hf download ORG/MODEL` (the
  official CLI also resumes).
- If `aria2c` is already installed, `aria2c -c -x8 "$URL"` adds segmented
  multi-connection downloading on top of resume.
