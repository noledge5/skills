"""End-to-end tests over a temporary directory tree.

Covers the cross-platform core: indexing, search, analysis,
quarantine round-trip, and the HTTP API. Windows-only modules are
covered by an import + NotSupported check on other platforms.

Run with:  python -m unittest discover -s tests -v
"""

import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from diskbutler import analyze, winclean  # noqa: E402
from diskbutler.db import Database  # noqa: E402
from diskbutler.indexer import Indexer, forget_root, list_roots  # noqa: E402
from diskbutler.quarantine import Quarantine  # noqa: E402
from diskbutler.search import search  # noqa: E402
from diskbutler.server import App, make_handler  # noqa: E402


def build_tree(base: str) -> None:
    docs = os.path.join(base, "Dokumente")
    pics = os.path.join(base, "Bilder", "Urlaub")
    dl = os.path.join(base, "Downloads")
    empty = os.path.join(base, "LeererOrdner")
    for d in (docs, pics, dl, empty):
        os.makedirs(d, exist_ok=True)

    def write(path: str, content: bytes, mtime: float | None = None) -> None:
        with open(path, "wb") as f:
            f.write(content)
        if mtime:
            os.utime(path, (mtime, mtime))

    write(os.path.join(docs, "Rechnung-2024.pdf"), b"pdf" * 1000)
    write(os.path.join(docs, "Notizen.txt"), b"hello")
    write(os.path.join(pics, "strand.jpg"), b"JPG" * 5000)
    write(os.path.join(pics, "strand-kopie.jpg"), b"JPG" * 5000)  # duplicate
    write(os.path.join(dl, "setup-oldapp.exe"), b"MZ" * 4000,
          mtime=time.time() - 200 * 86400)  # old installer
    write(os.path.join(base, "debug.tmp"), b"x" * 100)
    write(os.path.join(base, "Thumbs.db"), b"thumbs")


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dbutler-test-")
        self.tree = os.path.join(self.tmp, "tree")
        os.makedirs(self.tree)
        build_tree(self.tree)
        self.db = Database(os.path.join(self.tmp, "data"))
        Indexer(self.db).index(self.tree)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_index_counts(self):
        roots = list_roots(self.db)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["file_count"], 7)
        self.assertGreaterEqual(roots[0]["dir_count"], 5)

    def test_search_fts_prefix(self):
        result = search(self.db, q="rech")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["name"], "Rechnung-2024.pdf")

    def test_search_substring_fallback(self):
        result = search(self.db, q="nung-20")  # not a word prefix
        self.assertEqual(result["total"], 1)

    def test_search_filters(self):
        result = search(self.db, q="", ext="jpg", sort="size")
        self.assertEqual(result["total"], 2)
        result = search(self.db, q="", is_dir=True)
        self.assertTrue(all(r["is_dir"] for r in result["results"]))
        result = search(self.db, q="strand",
                        under=os.path.join(self.tree, "Bilder"))
        self.assertEqual(result["total"], 2)

    def test_reindex_no_duplicates(self):
        Indexer(self.db).index(self.tree)
        result = search(self.db, q="Rechnung")
        self.assertEqual(result["total"], 1)

    def test_forget_root(self):
        forget_root(self.db, self.tree)
        self.assertEqual(list_roots(self.db), [])
        self.assertEqual(search(self.db, q="")["total"], 0)

    def test_largest_and_extensions(self):
        largest = analyze.largest_files(self.db, limit=3)
        self.assertEqual(len(largest), 3)
        self.assertGreaterEqual(largest[0]["size"], largest[-1]["size"])
        exts = analyze.extension_stats(self.db)
        self.assertIn("jpg", [e["ext"] for e in exts])

    def test_empty_dirs(self):
        empty = analyze.empty_dirs(self.db)
        self.assertEqual(len(empty), 1)
        self.assertTrue(empty[0].endswith("LeererOrdner"))

    def test_duplicates(self):
        groups = analyze.duplicates(self.db, min_size=1)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["paths"]), 2)
        self.assertTrue(all("strand" in p for p in groups[0]["paths"]))

    def test_junk(self):
        items = analyze.junk_candidates(self.db)
        cats = {j["category"] for j in items}
        self.assertIn("temp_file", cats)
        self.assertIn("windows_thumbnail", cats)
        self.assertIn("old_installer", cats)
        # Each path must appear exactly once so the reclaimable total
        # never double-counts a file that matches several rules.
        paths = [j["path"] for j in items]
        self.assertEqual(len(paths), len(set(paths)))

    def test_quarantine_roundtrip(self):
        target = os.path.join(self.tree, "debug.tmp")
        q = Quarantine(self.db)
        result = q.quarantine([target], reason="test")
        self.assertEqual(len(result["moved"]), 1)
        self.assertFalse(os.path.exists(target))
        # gone from the index too
        self.assertEqual(search(self.db, q="debug.tmp")["total"], 0)

        restored = q.restore(result["batch_id"])
        self.assertEqual(restored["restored"], [target])
        self.assertTrue(os.path.exists(target))

    def test_quarantine_purge(self):
        target = os.path.join(self.tree, "Thumbs.db")
        q = Quarantine(self.db)
        result = q.quarantine([target])
        purge = q.purge(result["batch_id"])
        self.assertEqual(purge["purged"], [target])
        self.assertFalse(os.path.exists(target))
        batches = q.list_batches()
        self.assertEqual(batches[0]["status"], "purged")

    def test_quarantine_refuses_protected_paths(self):
        q = Quarantine(self.db)
        result = q.quarantine([os.path.expanduser("~")])
        self.assertEqual(result["moved"], [])
        self.assertEqual(result["errors"][0]["error"], "protected path")

    def test_winclean_guard(self):
        if sys.platform != "win32":
            with self.assertRaises(winclean.NotSupported):
                winclean.startup_entries()


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dbutler-api-")
        cls.tree = os.path.join(cls.tmp, "tree")
        os.makedirs(cls.tree)
        build_tree(cls.tree)
        cls.app = App(os.path.join(cls.tmp, "data"))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                        make_handler(cls.app))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def request(self, method: str, path: str, body: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        payload = json.dumps(body) if body is not None else None
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        return resp.status, data

    def wait_job(self, job_id: str) -> dict:
        for _ in range(100):
            status, job = self.request("GET", f"/api/jobs/{job_id}")
            self.assertEqual(status, 200)
            if job["status"] != "running":
                return job
            time.sleep(0.1)
        self.fail("job did not finish")

    def test_full_flow(self):
        status, data = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["app"], "DiskButler")

        # index via API (async job)
        status, data = self.request("POST", "/api/index", {"path": self.tree})
        self.assertEqual(status, 200)
        job = self.wait_job(data["job_id"])
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["files"], 7)

        # search
        status, data = self.request(
            "GET", "/api/search?q=strand&sort=size")
        self.assertEqual(data["total"], 2)

        # duplicates as async job
        status, data = self.request(
            "POST", "/api/analyze/duplicates", {"min_size": 1})
        job = self.wait_job(data["job_id"])
        self.assertEqual(job["status"], "done")
        self.assertEqual(len(job["result"]), 1)

        # junk
        status, data = self.request("GET", "/api/analyze/junk")
        self.assertGreaterEqual(len(data), 3)

        # quarantine one junk file and restore it
        victim = os.path.join(self.tree, "debug.tmp")
        status, data = self.request(
            "POST", "/api/quarantine", {"paths": [victim], "reason": "api"})
        self.assertEqual(len(data["moved"]), 1)
        batch_id = data["batch_id"]
        self.assertFalse(os.path.exists(victim))
        status, data = self.request(
            "POST", "/api/quarantine/restore", {"batch_id": batch_id})
        self.assertTrue(os.path.exists(victim))

        # purge requires confirm
        status, data = self.request(
            "POST", "/api/quarantine/purge", {"batch_id": batch_id})
        self.assertEqual(status, 428)

    def test_error_handling(self):
        status, data = self.request("GET", "/api/nonexistent")
        self.assertEqual(status, 404)
        status, data = self.request("POST", "/api/index", {"path": "/nope-x"})
        self.assertEqual(status, 400)
        status, data = self.request("GET", "/api/jobs/deadbeef")
        self.assertEqual(status, 404)
        if sys.platform != "win32":
            status, data = self.request("GET", "/api/windows/startup")
            self.assertEqual(status, 501)

    def test_agent_manifest_and_gui(self):
        status, data = self.request("GET", "/api/agent/manifest")
        self.assertEqual(status, 200)
        self.assertGreater(len(data["endpoints"]), 15)

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/")
        resp = conn.getresponse()
        html = resp.read().decode()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn("DiskButler", html)


if __name__ == "__main__":
    unittest.main()
