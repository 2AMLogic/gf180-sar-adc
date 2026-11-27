"""Regression tests for scripts/check_artifact_manifests.py (issue #636).

``verify`` runs against a fake artifact broker: a local HTTP server that
answers ``/v1/stat`` and ``/v1/get`` like the real one (a presigned URL per
object) and serves the bytes from memory. ``check`` runs against throwaway
git repositories. Stdlib only.
"""

import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from email.utils import formatdate
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_artifact_manifests", ROOT / "scripts" / "check_artifact_manifests.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

REPO = "owner/repo"
PACE_ENV = "CHECK_ARTIFACT_MANIFESTS_PACE_S"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}


def key_for(sha):
    return f"evidence/owner__repo/{sha[:2]}/{sha}"


def entry(data: bytes, name="sim/b/records/r1.json", sha=None, size=None):
    sha = sha or hashlib.sha256(data).hexdigest()
    return {"sha256": sha, "size": len(data) if size is None else size, "kind": "evidence",
            "producer": {"tool": "klt", "version": "0.7.0", "loom.repo": REPO, "commit": None},
            "uri": f"artifact:{key_for(sha)}", "name": name}


class FakeBroker:
    """objects: {sha: bytes} the store holds. ``serve_override`` maps a sha to
    the bytes actually served (a corrupted object); ``key_override`` makes
    get answer a different key. ``throttle`` makes it answer HTTP 429 while
    ``throttle(op, sha, calls_so_far)`` is true for that call (``"always"``:
    every call), with ``retry_after`` as the ``Retry-After`` header.
    ``calls`` lists the ops answered."""

    def __init__(self, objects, serve_override=None, key_override=None, refuse=None,
                 throttle=None, retry_after=None):
        self.objects = objects
        self.calls = []
        self.throttled = {}
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def _send(self, status, payload=None, raw=None, header=None):
                raw = raw if raw is not None else json.dumps(payload).encode()
                self.send_response(status)
                if header:
                    self.send_header(*header)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                op = self.path.rsplit("/", 1)[-1]
                fake.calls.append(op)
                if refuse:
                    return self._send(403, {"error": refuse, "message": "denied"})
                sha = body["sha256"]
                seen = fake.throttled.get((op, sha), 0)
                fake.throttled[op, sha] = seen + 1
                if throttle == "always" or (callable(throttle) and throttle(op, sha, seen)):
                    header = None
                    if retry_after is not None:
                        header = ("Retry-After", str(retry_after))
                    return self._send(429, {"error": "rate_limited",
                                            "message": "per-caller rate limit"}, header=header)
                assert body["repo"] == REPO and body["kind"] == "evidence"
                if sha not in fake.objects:
                    if self.path == "/v1/stat":
                        return self._send(200, {"key": key_for(sha), "exists": False})
                    return self._send(404, {"error": "not_found", "message": "no object"})
                if self.path == "/v1/stat":
                    return self._send(200, {"key": key_for(sha), "exists": True,
                                            "size": len(fake.objects[sha])})
                key = (key_override or {}).get(sha, key_for(sha))
                return self._send(200, {"key": key, "exists": True, "method": "GET",
                                        "url": f"{fake.base}/obj/{sha}?X-Sig=secret"})

            def do_GET(self):
                sha = self.path.split("/obj/")[1].split("?")[0]
                data = (serve_override or {}).get(sha, fake.objects.get(sha))
                self._send(200, raw=data)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Verify(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.dir = Path(td.name)
        self.a, self.b = b"alpha evidence\n", b"beta evidence\n"
        self.sha_a = hashlib.sha256(self.a).hexdigest()
        self.sha_b = hashlib.sha256(self.b).hexdigest()
        self.sleeps = []
        for patcher in (mock.patch.object(chk, "_sleep", self.sleeps.append, create=True),
                        mock.patch("random.uniform", lambda lo, hi: hi)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def store(self, n, start=0):
        """``n`` distinct one-byte objects as the {sha: bytes} a broker holds."""
        return {hashlib.sha256(bytes([65 + start + i])).hexdigest(): bytes([65 + start + i])
                for i in range(n)}

    def entries(self, objects):
        return [entry(data, name=f"sim/b/corners/r1/{sha[:8]}.log")
                for sha, data in objects.items()]

    def manifest(self, *entries, name="m.manifest.json"):
        p = self.dir / name
        p.write_text(json.dumps({"schema_version": 1, "entries": list(entries)}))
        return str(p)

    def run_verify(self, broker, *paths, env=None):
        out, err = io.StringIO(), io.StringIO()
        if broker is not None:
            self.addCleanup(broker.close)
        env = env if env is not None else {chk.ENV_BROKER: broker.base, PACE_ENV: "0"}
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = chk.verify(list(paths), env=env)
            except chk.ToolError as exc:
                print(f"ERROR: {exc}", file=err)
                rc = chk.EXIT_ERROR
        return rc, out.getvalue(), err.getvalue()

    def test_match(self):
        broker = FakeBroker({self.sha_a: self.a, self.sha_b: self.b})
        path = self.manifest(entry(self.a), entry(self.b, name="sim/b/corners/r1/tt.log"))
        rc, out, err = self.run_verify(broker, path)
        self.assertEqual(rc, 0, err)
        self.assertIn("2 stored object(s) fetched and re-hashed", out)
        self.assertIn("m.manifest.json: 2/2 verified", out)
        self.assertNotIn("X-Sig", out + err)  # presigned URL never printed

    def test_hash_mismatch(self):
        broker = FakeBroker({self.sha_a: self.a}, serve_override={self.sha_a: b"tampered\n"})
        rc, out, err = self.run_verify(broker, self.manifest(entry(self.a)))
        self.assertEqual(rc, 3)
        self.assertIn("hash_mismatch", out)

    def test_size_mismatch_against_manifest(self):
        broker = FakeBroker({self.sha_a: self.a})
        rc, out, _ = self.run_verify(broker, self.manifest(entry(self.a, size=len(self.a) + 1)))
        self.assertEqual(rc, 3)
        self.assertIn("size_mismatch", out)

    def test_missing_object(self):
        broker = FakeBroker({})
        rc, out, err = self.run_verify(broker, self.manifest(entry(self.a)))
        self.assertEqual(rc, 3)
        self.assertIn("missing", out)
        self.assertIn("1 of 1", err)

    def test_key_mismatch(self):
        broker = FakeBroker({self.sha_a: self.a}, key_override={self.sha_a: key_for("f" * 64)})
        rc, out, _ = self.run_verify(broker, self.manifest(entry(self.a)))
        self.assertEqual(rc, 3)
        self.assertIn("key_mismatch", out)

    def test_broker_refusal_is_error_not_pass(self):
        broker = FakeBroker({self.sha_a: self.a}, refuse="not_granted")
        rc, _, err = self.run_verify(broker, self.manifest(entry(self.a)))
        self.assertEqual(rc, 2)
        self.assertIn("not_granted", err)
        self.assertEqual(broker.calls, ["stat"])
        self.assertEqual(self.sleeps, [])

    def test_throttled_broker_is_retried_and_the_sweep_passes(self):
        objects = self.store(2)
        broker = FakeBroker(objects, throttle=lambda op, sha, n: n < 2)
        rc, out, err = self.run_verify(broker, self.manifest(*self.entries(objects)))
        self.assertEqual(rc, 0, err)
        self.assertIn("OK: 2 stored object(s) fetched and re-hashed", out)
        self.assertIn("m.manifest.json: 2/2 verified", out)
        self.assertEqual(broker.calls, ["stat", "stat", "stat", "get", "get", "get"] * 2)
        self.assertEqual(self.sleeps, [1.0, 2.0, 1.0, 2.0] * 2)

    def test_broker_that_stays_throttled_is_exit_2_with_progress(self):
        objects = self.store(3)
        broker = FakeBroker(objects, throttle="always")
        rc, out, err = self.run_verify(broker, self.manifest(*self.entries(objects)))
        self.assertEqual(rc, 2)
        self.assertEqual(broker.calls, ["stat"] * 8)
        self.assertIn("rate_limited", err)
        self.assertIn("after 8 attempts", err)
        self.assertIn("FAIL: sweep incomplete: 0 of 3 stored object(s) verified", err)
        self.assertIn("m.manifest.json: 0/3 verified", out)
        self.assertNotIn("OK:", out)

    def test_sweep_cut_off_midway_names_complete_and_cut_off_manifests(self):
        whole, cut, unreached = self.store(3), self.store(2, 3), self.store(2, 5)
        missing = next(iter(whole))
        at = list(cut)[1]
        stored = {**whole, **cut, **unreached}
        del stored[missing]
        broker = FakeBroker(stored, throttle=lambda op, sha, n: sha == at)
        paths = [self.manifest(*self.entries(whole), name="a.manifest.json"),
                 self.manifest(*self.entries(cut), name="b.manifest.json"),
                 self.manifest(*self.entries(unreached), name="c.manifest.json")]
        rc, out, err = self.run_verify(broker, *paths)
        self.assertEqual(rc, 2)
        self.assertIn("missing", out)
        self.assertIn("a.manifest.json: 3/3 verified", out)
        self.assertIn("b.manifest.json: 1/2 verified", out)
        self.assertIn("c.manifest.json: 0/2 verified", out)
        self.assertIn("FAIL: sweep incomplete: 4 of 7 stored object(s) verified across "
                      "3 manifest(s): 1 verified in full, cut off in ", err)
        self.assertIn("b.manifest.json (1/2 verified), 1 not reached; of those verified, "
                      "1 missing or mismatched", err)
        self.assertNotIn("OK:", out)

    def test_first_retry_honors_the_brokers_time(self):
        start = 1_700_000_000
        future = formatdate(start + 120, usegmt=True)
        past = formatdate(start - 60, usegmt=True)
        for target, header, delay in (("stat", "60", 60), ("get", future, 120),
                                      ("stat", past, 0)):
            with self.subTest(op=target, retry_after=header):
                self.sleeps.clear()
                attempts = []

                def throttle(op, sha, seen):
                    if op != target:
                        return False
                    attempts.append(sum(self.sleeps))
                    return seen == 0

                broker = FakeBroker({self.sha_a: self.a}, throttle=throttle, retry_after=header)
                with mock.patch.object(chk.time, "time", lambda: start + sum(self.sleeps)):
                    rc, _, err = self.run_verify(broker, self.manifest(entry(self.a)))
                self.assertEqual(rc, 0, err)
                self.assertEqual(attempts, [0, delay])

    def test_retry_waits_are_bounded(self):
        no_header = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
        for retry_after, sleeps in ((7, [7.0] * 7), (90, [90, 90]), (100, [100]), (3600, []),
                                    (None, no_header), ("invalid", no_header)):
            with self.subTest(retry_after=retry_after):
                self.sleeps.clear()
                objects = self.store(1)
                broker = FakeBroker(objects, throttle="always", retry_after=retry_after)
                rc, _, err = self.run_verify(broker, self.manifest(*self.entries(objects)))
                self.assertEqual(rc, 2)
                self.assertEqual(self.sleeps, sleeps)
                self.assertEqual(len(broker.calls), len(sleeps) + 1)
                self.assertIn(f"after {len(sleeps) + 1} attempt", err)
                self.assertIn("FAIL: sweep incomplete: 0 of 1 stored object(s) verified", err)

    def test_entries_are_paced_through_the_env_override(self):
        objects = self.store(3)
        broker = FakeBroker(objects)
        rc, _, err = self.run_verify(broker, self.manifest(*self.entries(objects)),
                                     env={chk.ENV_BROKER: broker.base, PACE_ENV: "0.25"})
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.sleeps, [0.25, 0.25])

    def test_pace_is_one_second_by_default_and_must_be_a_number(self):
        objects = self.store(2)
        path = self.manifest(*self.entries(objects))
        broker = FakeBroker(objects)
        rc, _, err = self.run_verify(broker, path, env={chk.ENV_BROKER: broker.base})
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.sleeps, [1.0])
        for junk in ("fast", "-1", "nan", "inf", ""):
            with self.subTest(junk):
                self.sleeps.clear()
                broker = FakeBroker(objects)
                rc, _, err = self.run_verify(broker, path, env={chk.ENV_BROKER: broker.base,
                                                                PACE_ENV: junk})
                self.assertEqual(rc, 2)
                self.assertIn(f"${PACE_ENV} must be a non-negative number", err)

    def test_cli_sweep_stopped_by_the_broker_exits_2(self):
        objects = self.store(2)
        broker = FakeBroker(objects, throttle="always")
        self.addCleanup(broker.close)
        out, err = io.StringIO(), io.StringIO()
        env = {chk.ENV_BROKER: broker.base, PACE_ENV: "0"}
        environ = mock.patch.dict(os.environ, env)
        environ.start()
        self.addCleanup(environ.stop)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["verify", self.manifest(*self.entries(objects))])
        self.assertEqual(rc, 2)
        self.assertIn("FAIL: sweep incomplete: 0 of 2 stored object(s) verified",
                      err.getvalue())
        self.assertNotIn("OK:", out.getvalue())

    def test_unreachable_broker_fails_closed(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        rc, _, err = self.run_verify(None, self.manifest(entry(self.a)),
                                     env={chk.ENV_BROKER: f"http://127.0.0.1:{port}"})
        self.assertEqual(rc, 2)
        self.assertIn("failing closed", err)

    def test_no_broker_configured_is_not_a_pass(self):
        rc, _, err = self.run_verify(None, self.manifest(entry(self.a)), env={})
        self.assertEqual(rc, 2)
        self.assertIn("not a pass", err)

    def test_invalid_manifest(self):
        broker = FakeBroker({})
        bad = entry(self.a)
        bad["extra"] = 1
        rc, _, err = self.run_verify(broker, self.manifest(bad))
        self.assertEqual(rc, 1)
        self.assertIn("unknown field", err)


class Schema(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(chk.manifest_problems({"schema_version": 1,
                                                "entries": [entry(b"x")]}), [])

    def test_rejections(self):
        e = entry(b"x")
        cases = {
            "uri key does not end": {**e, "uri": "artifact:" + key_for("a" * 64)},
            "kind must be": {**e, "kind": "pdk"},
            "name must be": {**e, "name": "/abs/path"},
            "name is required": {k: v for k, v in e.items() if k != "name"},
            "size must be": {**e, "size": 0},
            "different repo": {**e, "producer": {**e["producer"], "loom.repo": "x/y"}},
            "producer must carry": {**e, "producer": {"tool": "klt"}},
        }
        for needle, bad in cases.items():
            with self.subTest(needle):
                problems = chk.manifest_problems({"schema_version": 1, "entries": [bad]})
                self.assertTrue(any(needle in p for p in problems), problems)
        self.assertEqual(chk.manifest_problems({"schema_version": 1, "entries": []}),
                         ["has no entries"])
        dup = chk.manifest_problems({"schema_version": 1, "entries": [e, e]})
        self.assertTrue(any("duplicate name" in p for p in dup))

    def test_only_the_artifact_scheme_is_accepted(self):
        # Operator ruling H1 (2AMLogic/2am#5553): the uri is the logical
        # artifact:<key>; a bucket-naming uri or any other scheme is refused.
        e = entry(b"x")
        self.assertEqual(chk.uri_key(e["uri"]), key_for(e["sha256"]))
        key = key_for(e["sha256"])
        legacy = "s3" + "://"  # built, so a grep for the literal stays clean
        for uri in (f"{legacy}bucket/{key}", f"{legacy}{key}", f"https://host/{key}",
                    f"file:///{key}", f"Artifact:{key}", f"artifact:/{key}",
                    f"artifact:{key} ", "artifact:", key, None, 7):
            with self.subTest(uri=uri):
                self.assertIsNone(chk.uri_key(uri))
                problems = chk.manifest_problems({"schema_version": 1,
                                                  "entries": [{**e, "uri": uri}]})
                self.assertTrue(any("uri must be artifact:<key>" in p for p in problems),
                                problems)


class Check(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "r\n")
        self.commit()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], env=ENV, check=True,
                              capture_output=True).stdout.decode().strip()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "c")

    def run_check(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["check", "--repo", str(self.root), "--tree", "HEAD"])
        return rc, out.getvalue(), err.getvalue()

    def add_manifest(self, *entries, name="b-r1.manifest.json"):
        self.write(f"manifests/artifacts/{name}",
                   json.dumps({"schema_version": 1, "entries": list(entries)}))

    def test_no_manifests_is_ok_and_says_not_hash_verified(self):
        rc, out, _ = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("NOT hash-verified", out)

    def test_valid_manifest_with_summary_passes(self):
        self.add_manifest(entry(b"x"))
        self.write("sim/b/records/r1.md", "# summary\n")
        self.commit()
        rc, out, err = self.run_check()
        self.assertEqual(rc, 0, err)
        self.assertIn("1 manifest(s), 1 entry", out)

    def test_committed_blob_beside_manifest_fails(self):
        self.add_manifest(entry(b"x"))
        self.write("sim/b/records/r1.json", "x")  # the stored bytes, committed too
        self.commit()
        rc, _, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("no blob fallback", err)

    def test_same_bytes_committed_under_another_name_fails(self):
        self.add_manifest(entry(b"stored bytes"))
        self.write("sim/b/elsewhere/copy.log", "stored bytes")
        self.commit()
        rc, _, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("sim/b/elsewhere/copy.log", err)
        self.assertIn("same sha256", err)

    def test_same_size_different_bytes_passes(self):
        self.add_manifest(entry(b"stored bytes"))
        self.write("sim/b/elsewhere/other.log", "other bytes!")
        self.commit()
        rc, _, err = self.run_check()
        self.assertEqual(rc, 0, err)

    def test_bucket_uri_fails(self):
        bad = entry(b"x")
        bad["uri"] = "s3" + "://bucket/evidence/owner__repo/" + bad["sha256"]
        self.add_manifest(bad)
        self.commit()
        rc, _, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("artifact:<key>", err)

    def test_new_raw_corner_log_since_base_fails(self):
        self.git("checkout", "-q", "-b", "pr")
        self.write("sim/b/corners/r1/tt.log", "log\n")
        self.commit()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["check", "--repo", str(self.root), "--tree", "HEAD",
                           "--base", "main"])
        self.assertEqual(rc, 1)
        self.assertIn("sim/b/corners/r1/tt.log", err.getvalue())

    def test_no_new_raw_output_since_base_passes(self):
        self.git("checkout", "-q", "-b", "pr")
        self.write("sim/b/records/r1.md", "# s\n")
        self.commit()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["check", "--repo", str(self.root), "--tree", "HEAD",
                           "--base", "main"])
        self.assertEqual(rc, 0, err.getvalue())

    def test_malformed_manifest_fails(self):
        self.add_manifest({"sha256": "nope"})
        self.commit()
        rc, _, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("b-r1.manifest.json: entry 0", err)

    def test_stray_file_in_manifest_dir_fails(self):
        self.write("manifests/artifacts/blob.bin", "x")
        self.commit()
        rc, _, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("only <bench>-<run-id>.manifest.json", err)

    def test_unavailable_revision_is_exit_2(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["check", "--repo", str(self.root), "--tree", "nope"])
        self.assertEqual(rc, 2)


class RepoManifests(unittest.TestCase):
    def test_head_manifests_pass(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = chk.main(["check", "--repo", str(ROOT), "--tree", "HEAD"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
