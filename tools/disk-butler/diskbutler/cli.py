"""Command line interface: python -m diskbutler <command>."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, analyze
from .db import Database
from .indexer import Indexer, list_roots
from .search import search as do_search


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="diskbutler",
        description="Fast local disk search, analysis and safe cleanup.",
    )
    parser.add_argument("--data-dir", help="where index + quarantine live")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="start GUI + API server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8177)

    p = sub.add_parser("index", help="index a directory or drive")
    p.add_argument("path")

    p = sub.add_parser("search", help="search the index")
    p.add_argument("query")
    p.add_argument("--ext")
    p.add_argument("--under")
    p.add_argument("--sort", default="name",
                   choices=["name", "size", "mtime", "path"])
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--json", action="store_true")

    sub.add_parser("roots", help="list indexed roots")

    p = sub.add_parser("junk", help="list junk candidates")
    p.add_argument("--under")
    p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "serve":
        from .server import serve
        serve(host=args.host, port=args.port, data_dir=args.data_dir)
        return 0

    db = Database(args.data_dir)

    if args.command == "index":
        result = Indexer(db).index(args.path)
        print(f"Indexed {result.files} files / {result.dirs} dirs "
              f"({_fmt_size(result.total_size)}) in "
              f"{result.finished_at - result.started_at:.1f}s"
              + (f", {result.errors} unreadable" if result.errors else ""))
        return 0

    if args.command == "roots":
        for r in list_roots(db):
            print(f"{r['path']}  {r['file_count']} files, "
                  f"{_fmt_size(r['total_size'])}")
        return 0

    if args.command == "search":
        result = do_search(db, q=args.query, ext=args.ext, under=args.under,
                           sort=args.sort, limit=args.limit)
        if args.json:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            for r in result["results"]:
                print(f"{_fmt_size(r['size']):>10}  {r['path']}")
            print(f"-- {result['total']} matches")
        return 0

    if args.command == "junk":
        items = analyze.junk_candidates(db, under=args.under)
        if args.json:
            json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            for item in items[:50]:
                print(f"{_fmt_size(item['size']):>10}  "
                      f"[{item['category']}]  {item['path']}")
            total = sum(i["size"] for i in items)
            print(f"-- {len(items)} candidates, {_fmt_size(total)} reclaimable")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
