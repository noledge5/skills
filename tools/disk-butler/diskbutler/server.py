"""Local HTTP server: JSON API + web GUI.

Standard library only (ThreadingHTTPServer), binds to 127.0.0.1 by
default. Long operations (indexing, duplicate scans) run as background
jobs polled via /api/jobs/<id>. GET /api/agent/manifest returns a
machine-readable description of every endpoint so an agent can drive
the API without reading the source.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__, analyze, winclean
from .db import Database
from .indexer import Indexer, forget_root, list_roots
from .quarantine import Quarantine
from .search import search

# Normalised so the path-traversal guard in _serve_static compares like
# with like even when the module is imported via a path containing '..'.
STATIC_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "static"))


class Jobs:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, fn) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id, "kind": kind, "status": "running",
            "started_at": time.time(), "progress": {}, "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job

        def run() -> None:
            try:
                job["result"] = fn(job["progress"])
                job["status"] = "done"
            except Exception as e:  # noqa: BLE001 — surfaced to the client
                job["status"] = "error"
                job["error"] = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            finally:
                job["finished_at"] = time.time()

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    def all(self) -> list[dict]:
        return sorted(self._jobs.values(),
                      key=lambda j: j["started_at"], reverse=True)


class App:
    def __init__(self, data_dir: str | None = None):
        self.db = Database(data_dir)
        self.quarantine = Quarantine(self.db)
        self.jobs = Jobs()

    # Each handler gets (query, body) and returns a JSON-serialisable
    # object. Registered in ROUTES below.

    def status(self, q, body):
        return {
            "app": "DiskButler",
            "version": __version__,
            "platform": os.name,
            "data_dir": self.db.data_dir,
            "roots": list_roots(self.db),
        }

    def index_start(self, q, body):
        path = body.get("path") or _one(q, "path")
        if not path:
            raise ApiError("missing 'path'")
        if not os.path.isdir(path):
            raise ApiError(f"not a directory: {path}")

        def run(progress: dict):
            indexer = Indexer(Database(self.db.data_dir))
            done = {}

            def poll():
                while not done:
                    progress.update(indexer.progress.as_dict())
                    time.sleep(0.5)
            t = threading.Thread(target=poll, daemon=True)
            t.start()
            try:
                result = indexer.index(path)
            finally:
                done["x"] = True
            progress.update(result.as_dict())
            return result.as_dict()

        return {"job_id": self.jobs.start("index", run)}

    def index_forget(self, q, body):
        path = body.get("path")
        if not path:
            raise ApiError("missing 'path'")
        removed = forget_root(self.db, path)
        return {"removed_entries": removed}

    def do_search(self, q, body):
        def as_int(name):
            v = _one(q, name)
            return int(v) if v else None
        is_dir = _one(q, "is_dir")
        return search(
            self.db,
            q=_one(q, "q") or "",
            ext=_one(q, "ext"),
            under=_one(q, "under"),
            min_size=as_int("min_size"),
            max_size=as_int("max_size"),
            is_dir=None if is_dir is None else is_dir in ("1", "true"),
            sort=_one(q, "sort") or "name",
            limit=min(as_int("limit") or 100, 1000),
            offset=as_int("offset") or 0,
        )

    def analyze_largest(self, q, body):
        return analyze.largest_files(
            self.db, under=_one(q, "under"),
            limit=min(int(_one(q, "limit") or 50), 500))

    def analyze_extensions(self, q, body):
        return analyze.extension_stats(self.db, under=_one(q, "under"))

    def analyze_tree(self, q, body):
        path = _one(q, "path")
        if not path:
            raise ApiError("missing 'path'")
        return analyze.tree_sizes(self.db, path)

    def analyze_empty_dirs(self, q, body):
        return analyze.empty_dirs(self.db, under=_one(q, "under"))

    def analyze_junk(self, q, body):
        return analyze.junk_candidates(self.db, under=_one(q, "under"))

    def analyze_duplicates(self, q, body):
        under = body.get("under")
        min_size = int(body.get("min_size") or 1024 * 1024)
        db_dir = self.db.data_dir

        def run(progress: dict):
            return analyze.duplicates(
                Database(db_dir), under=under, min_size=min_size,
                progress=progress)
        return {"job_id": self.jobs.start("duplicates", run)}

    def job_get(self, q, body, job_id: str = ""):
        job = self.jobs.get(job_id)
        if job is None:
            raise ApiError(f"unknown job: {job_id}", status=404)
        return job

    def jobs_list(self, q, body):
        return self.jobs.all()

    # Windows -----------------------------------------------------------

    def win_programs(self, q, body):
        return winclean.installed_programs()

    def win_leftovers(self, q, body):
        return winclean.leftover_dirs()

    def win_startup(self, q, body):
        return winclean.startup_entries()

    def win_services(self, q, body):
        return winclean.services()

    def win_tasks(self, q, body):
        return winclean.scheduled_tasks()

    def win_disable_startup(self, q, body):
        for field in ("kind", "location", "name"):
            if not body.get(field):
                raise ApiError(f"missing '{field}'")
        if not body.get("confirm"):
            raise ApiError(
                "This changes system autostart. Repeat the call with"
                " \"confirm\": true.", status=428)
        return winclean.disable_startup_entry(
            body["kind"], body["location"], body["name"],
            quarantine=self.quarantine)

    # Quarantine ----------------------------------------------------------

    def q_add(self, q, body):
        paths = body.get("paths")
        if not isinstance(paths, list) or not paths:
            raise ApiError("missing 'paths' (list)")
        return self.quarantine.quarantine(paths, reason=body.get("reason", ""))

    def q_list(self, q, body):
        return self.quarantine.list_batches()

    def q_items(self, q, body):
        return self.quarantine.list_items(int(_one(q, "batch_id") or 0))

    def q_restore(self, q, body):
        return self.quarantine.restore(int(body.get("batch_id") or 0))

    def q_purge(self, q, body):
        if not body.get("confirm"):
            raise ApiError(
                "Purging permanently deletes the batch. Repeat the call"
                " with \"confirm\": true.", status=428)
        return self.quarantine.purge(int(body.get("batch_id") or 0))

    def agent_manifest(self, q, body):
        return AGENT_MANIFEST


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _one(q: dict, name: str) -> str | None:
    v = q.get(name)
    return v[0] if v else None


# method, path → (handler name, description). Paths with a trailing
# "*" capture the remainder as an argument.
ROUTES: dict[tuple[str, str], tuple[str, str]] = {
    ("GET", "/api/status"): ("status", "App info + indexed roots"),
    ("POST", "/api/index"): ("index_start", "Start indexing. Body: {path}. Returns {job_id}"),
    ("POST", "/api/index/forget"): ("index_forget", "Remove a root from the index. Body: {path}"),
    ("GET", "/api/search"): ("do_search", "Search. Params: q, ext, under, min_size, max_size, is_dir, sort(name|size|mtime|path), limit, offset"),
    ("GET", "/api/analyze/largest"): ("analyze_largest", "Largest files. Params: under, limit"),
    ("GET", "/api/analyze/extensions"): ("analyze_extensions", "Size by file extension. Params: under"),
    ("GET", "/api/analyze/tree"): ("analyze_tree", "Children of 'path' with recursive sizes"),
    ("GET", "/api/analyze/empty-dirs"): ("analyze_empty_dirs", "Empty directories. Params: under"),
    ("GET", "/api/analyze/junk"): ("analyze_junk", "Junk candidates by category. Params: under"),
    ("POST", "/api/analyze/duplicates"): ("analyze_duplicates", "Start duplicate scan. Body: {under?, min_size?}. Returns {job_id}"),
    ("GET", "/api/jobs"): ("jobs_list", "All background jobs"),
    ("GET", "/api/jobs/*"): ("job_get", "One job: status, progress, result"),
    ("GET", "/api/windows/programs"): ("win_programs", "Installed programs (registry)"),
    ("GET", "/api/windows/leftovers"): ("win_leftovers", "Orphaned program folders"),
    ("GET", "/api/windows/startup"): ("win_startup", "Autostart entries with assessment"),
    ("GET", "/api/windows/services"): ("win_services", "Services with assessment (report-only)"),
    ("GET", "/api/windows/tasks"): ("win_tasks", "Non-Microsoft scheduled tasks (report-only)"),
    ("POST", "/api/windows/startup/disable"): ("win_disable_startup", "Disable an autostart entry. Body: {kind, location, name, confirm:true}"),
    ("POST", "/api/quarantine"): ("q_add", "Move paths to quarantine. Body: {paths:[], reason?}"),
    ("GET", "/api/quarantine"): ("q_list", "Quarantine batches"),
    ("GET", "/api/quarantine/items"): ("q_items", "Items of one batch. Params: batch_id"),
    ("POST", "/api/quarantine/restore"): ("q_restore", "Restore a batch. Body: {batch_id}"),
    ("POST", "/api/quarantine/purge"): ("q_purge", "Permanently delete a batch. Body: {batch_id, confirm:true}"),
    ("GET", "/api/agent/manifest"): ("agent_manifest", "This endpoint list, machine-readable"),
}

AGENT_MANIFEST = {
    "app": "DiskButler",
    "version": __version__,
    "purpose": "Fast local file search, disk analysis and safe cleanup. "
               "All destructive operations are two-step: files go to a "
               "restorable quarantine first; purge and autostart changes "
               "require confirm:true.",
    "conventions": {
        "encoding": "JSON request/response bodies; query params for GET",
        "jobs": "POST endpoints returning {job_id} are asynchronous — "
                "poll GET /api/jobs/<job_id> until status is done/error",
        "sizes": "bytes", "times": "unix epoch seconds",
    },
    "endpoints": [
        {"method": m, "path": p, "description": desc}
        for (m, p), (_, desc) in ROUTES.items()
    ],
    "recommended_workflow": [
        "GET /api/status to see indexed roots",
        "POST /api/index for each drive/folder to organise",
        "Use /api/search and /api/analyze/* to understand the data",
        "Propose a target folder structure to the user before moving anything",
        "Quarantine junk/duplicates via POST /api/quarantine (restorable)",
        "Only purge after the user confirms nothing is missing",
    ],
}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"DiskButler/{__version__}"

        def log_message(self, fmt, *args):  # quieter default logging
            pass

        def _send_json(self, obj, status: int = 200) -> None:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _serve_static(self, path: str) -> None:
            if path in ("/", "/index.html"):
                path = "/index.html"
            fs_path = os.path.realpath(
                os.path.join(STATIC_DIR, path.lstrip("/")))
            if os.path.commonpath([fs_path, STATIC_DIR]) != STATIC_DIR \
                    or not os.path.isfile(fs_path):
                self._send_json({"error": "not found"}, 404)
                return
            ctype = ("text/html; charset=utf-8" if fs_path.endswith(".html")
                     else "application/octet-stream")
            with open(fs_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _dispatch(self, method: str) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            body = {}
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    try:
                        body = json.loads(self.rfile.read(length))
                    except json.JSONDecodeError:
                        self._send_json({"error": "invalid JSON body"}, 400)
                        return

            route = ROUTES.get((method, url.path))
            arg = None
            if route is None:
                for (m, pattern), r in ROUTES.items():
                    if m == method and pattern.endswith("/*") and \
                            url.path.startswith(pattern[:-1]):
                        route, arg = r, url.path[len(pattern) - 1:]
                        break
            if route is None:
                if method == "GET" and not url.path.startswith("/api/"):
                    self._serve_static(url.path)
                    return
                self._send_json({"error": f"no route {method} {url.path}"}, 404)
                return

            handler = getattr(app, route[0])
            try:
                result = handler(query, body, arg) if arg is not None \
                    else handler(query, body)
                self._send_json(result)
            except ApiError as e:
                self._send_json({"error": str(e)}, e.status)
            except winclean.NotSupported as e:
                self._send_json({"error": str(e)}, 501)
            except Exception as e:  # noqa: BLE001 — surfaced to the client
                traceback.print_exc()
                self._send_json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8177,
          data_dir: str | None = None) -> None:
    app = App(data_dir)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"DiskButler {__version__} — http://{host}:{port}")
    print(f"GUI:        http://{host}:{port}/")
    print(f"Agent-API:  http://{host}:{port}/api/agent/manifest")
    print(f"Data dir:   {app.db.data_dir}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
