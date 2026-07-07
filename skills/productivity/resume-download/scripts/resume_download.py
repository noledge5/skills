#!/usr/bin/env python3
"""Resumable HTTP downloader for huge files.

Downloads to <output>.part and resumes from the existing byte offset via HTTP
Range requests, so interruptions (Ctrl+C, network drops, reboots) never lose
progress. Re-running the same command continues where the last run stopped.

Python 3.8+ standard library only — no dependencies to install.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30
BACKOFF_CAP = 60
META_SUFFIX = ".part.json"


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def load_meta(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_meta(path, meta):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f)


class Progress:
    def __init__(self, total):
        self.total = total
        self.last_time = 0.0
        self.window = []  # (timestamp, pos) samples for speed calculation

    def update(self, pos, force=False):
        now = time.monotonic()
        if not force and now - self.last_time < 0.5:
            return
        self.last_time = now
        self.window.append((now, pos))
        self.window = [(t, p) for t, p in self.window if now - t <= 20]
        speed = 0.0
        if len(self.window) >= 2:
            dt = self.window[-1][0] - self.window[0][0]
            db = self.window[-1][1] - self.window[0][1]
            speed = db / dt if dt > 0 else 0.0
        if self.total:
            pct = pos / self.total * 100
            eta = (self.total - pos) / speed if speed > 0 else 0
            eta_s = f"{int(eta // 3600)}h{int(eta % 3600 // 60):02d}m" if eta else "--"
            line = (
                f"\r{pct:5.1f}%  {human(pos)} / {human(self.total)}"
                f"  {human(speed)}/s  ETA {eta_s}   "
            )
        else:
            line = f"\r{human(pos)} downloaded  {human(speed)}/s   "
        sys.stderr.write(line)
        sys.stderr.flush()


def output_name_from(url, resp):
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        return os.path.basename(urllib.parse.unquote(m.group(1).strip()))
    path = urllib.parse.urlparse(url).path
    return os.path.basename(path) or "download.bin"


def open_stream(url, pos, meta, headers):
    """Open the response, requesting a resume from byte `pos` if pos > 0.

    Returns (response, start_pos, total). start_pos is 0 when the server
    ignored the Range header (or the remote file changed), meaning the
    existing partial data must be discarded.
    """
    req_headers = dict(headers)
    if pos:
        req_headers["Range"] = f"bytes={pos}-"
        validator = meta.get("etag") or meta.get("last_modified")
        if validator:
            # If the remote file changed, the server replies 200 with the
            # full body instead of a mismatched 206 slice.
            req_headers["If-Range"] = validator
    req = urllib.request.Request(url, headers=req_headers)
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)

    if pos and resp.status == 200:
        sys.stderr.write(
            "\nServer does not support resume (or remote file changed); "
            "restarting from 0.\n"
        )
        pos = 0
    if resp.status == 206:
        m = re.search(r"/(\d+)\s*$", resp.headers.get("Content-Range", ""))
        total = int(m.group(1)) if m else None
    else:
        cl = resp.headers.get("Content-Length")
        total = int(cl) if cl else None
    return resp, pos, total


def download(url, output, headers, chunk_size):
    part = output + ".part"
    meta_path = output + META_SUFFIX
    meta = load_meta(meta_path)
    pos = os.path.getsize(part) if os.path.exists(part) else 0

    try:
        resp, pos, total = open_stream(url, pos, meta, headers)
    except urllib.error.HTTPError as e:
        if e.code == 416:
            # Requested range starts at/after EOF — the .part is already
            # complete if its size matches what we recorded earlier.
            if meta.get("total") and pos >= meta["total"]:
                return meta["total"]
        raise

    with resp:
        meta = {
            "url": url,
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
            "total": total,
        }
        save_meta(meta_path, meta)

        if pos:
            sys.stderr.write(f"Resuming at {human(pos)}\n")
        progress = Progress(total)
        mode = "r+b" if pos else "wb"
        with open(part, mode) as f:
            f.seek(pos)
            f.truncate()
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                pos += len(chunk)
                progress.update(pos)
        progress.update(pos, force=True)
        sys.stderr.write("\n")

    if total is not None and pos < total:
        raise ConnectionError(f"connection closed at {human(pos)} of {human(total)}")
    return pos


def verify_sha256(path, expected):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected.lower():
        raise SystemExit(
            f"SHA256 mismatch!\n  expected {expected.lower()}\n  actual   {actual}"
        )
    print("SHA256 verified OK")


def main():
    ap = argparse.ArgumentParser(
        description="Download huge files with automatic resume. Interrupt any "
        "time with Ctrl+C; re-run the same command to continue.",
    )
    ap.add_argument("url")
    ap.add_argument("-o", "--output", help="output file (default: from URL/server)")
    ap.add_argument(
        "-H",
        "--header",
        action="append",
        default=[],
        metavar="'Name: value'",
        help="extra request header, repeatable (e.g. 'Authorization: Bearer TOKEN')",
    )
    ap.add_argument("--sha256", help="verify checksum after download")
    ap.add_argument(
        "--max-retries",
        type=int,
        default=100,
        help="consecutive failed attempts before giving up (default 100; the "
        "counter resets whenever an attempt makes progress)",
    )
    ap.add_argument(
        "--chunk-size", type=int, default=1024 * 1024, help="read size in bytes"
    )
    args = ap.parse_args()

    headers = {"User-Agent": "resume-download/1.0"}
    for h in args.header:
        name, _, value = h.partition(":")
        headers[name.strip()] = value.strip()

    output = args.output
    if not output:
        # One cheap request to learn the filename before committing to paths.
        req = urllib.request.Request(url=args.url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            output = output_name_from(args.url, resp)
        print(f"Saving to: {output}")

    if os.path.exists(output):
        print(f"{output} already exists — nothing to do.")
        if args.sha256:
            verify_sha256(output, args.sha256)
        return

    failures = 0
    while True:
        start_size = (
            os.path.getsize(output + ".part")
            if os.path.exists(output + ".part")
            else 0
        )
        try:
            size = download(args.url, output, headers, args.chunk_size)
            break
        except KeyboardInterrupt:
            sys.stderr.write("\nPaused. Re-run the same command to resume.\n")
            raise SystemExit(130)
        except urllib.error.HTTPError as e:
            if e.code in (408, 429) or e.code >= 500:
                pass  # transient — retry below
            else:
                raise SystemExit(f"HTTP {e.code} {e.reason} — not retryable.")
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            sys.stderr.write(f"\nError: {e}\n")

        end_size = (
            os.path.getsize(output + ".part")
            if os.path.exists(output + ".part")
            else 0
        )
        failures = 0 if end_size > start_size else failures + 1
        if failures > args.max_retries:
            raise SystemExit(
                f"Giving up after {args.max_retries} consecutive attempts "
                "without progress. Partial file kept; re-run to try again."
            )
        wait = min(2**min(failures, 6), BACKOFF_CAP)
        sys.stderr.write(f"Retrying in {wait}s...\n")
        time.sleep(wait)

    os.replace(output + ".part", output)
    try:
        os.remove(output + META_SUFFIX)
    except OSError:
        pass
    print(f"Done: {output} ({human(size)})")
    if args.sha256:
        verify_sha256(output, args.sha256)


if __name__ == "__main__":
    main()
