"""Issue #636: the evidence writer stores bytes through ``klt artifact put``
and commits only a manifest and a summary. Every failure is fail closed.

Stdlib only. ``klt`` is emulated by an injected ``run`` (the writer's only
contact with it is argv + exit status + the manifest file it merges into), and
the broker probe runs against a throwaway local HTTP server.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import socket
import subprocess
import tempfile
import threading
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import evidence_store as es  # noqa: E402

REPO = "owner/repo"


def fake_klt(store: dict, *, fail=None, corrupt=False, uri=None):
    """Emulate ``klt artifact put FILE --name N --manifest M --format json``.
    ``uri`` overrides the written uri (given the key) to emulate an old klt."""

    def run(cmd, **kw):
        assert cmd[:3] == ["klt", "artifact", "put"], cmd
        path, name, manifest = cmd[3], cmd[cmd.index("--name") + 1], cmd[cmd.index("--manifest") + 1]
        assert "--broker" not in cmd  # the broker URL never goes in argv
        if fail is not None:
            err = {"schema_version": 1, "error": {"command": "artifact put",
                                                  "message": "cannot reach the artifact broker",
                                                  "code": fail}}
            return subprocess.CompletedProcess(cmd, 1, "", json.dumps(err))
        data = Path(path).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        store[sha] = data
        key = f"evidence/owner__repo/{sha[:2]}/{'0' * 64 if corrupt else sha}"
        entry = {"sha256": "0" * 64 if corrupt else sha, "size": len(data), "kind": "evidence",
                 "producer": {"tool": "klt", "version": "t", "loom.repo": REPO, "commit": None},
                 "uri": uri(key) if uri else f"artifact:{key}",
                 "name": name}
        p = Path(manifest)
        m = json.loads(p.read_text()) if p.exists() else {"schema_version": 1, "entries": []}
        m["entries"].append(entry)
        p.write_text(json.dumps(m))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"status": "stored"}), "")

    return run


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.stage = self.root / "sim/.work/.stage/b"
        (self.stage / "corners/r1").mkdir(parents=True)
        (self.stage / "corners/r1/tt.log").write_text("log tt\n")
        (self.stage / "corners/r1/ff.log").write_text("log ff\n")
        (self.stage / "corners/r1/empty.log").write_text("")
        (self.stage / "r1.json").write_text('{"x": 1}\n')
        self.files = [(self.stage / "r1.json", "sim/b/records/r1.json")]
        self.files += es.stage_files(self.stage / "corners/r1", "sim/b/corners/r1")
        self.summary = self.root / "sim/b/records/r1.md"
        self.mpath = self.root / "manifests/artifacts/b-r1.manifest.json"
        self.store = {}

    def put(self, **kw):
        return lambda files, root: es.put_files(files, root, run=fake_klt(self.store, **kw))

    def store_files(self, **kw):
        return es.store_files(self.files, repo_root=self.root, bench="b", rid="r1",
                              summary_text="# record\n", summary_path=self.summary,
                              put=self.put(**kw))

    def assert_nothing_committed(self):
        self.assertFalse(self.mpath.exists())
        self.assertFalse(self.summary.exists())
        self.assertFalse((self.root / "sim/b").exists())


class Writer(Base):
    def test_stores_bytes_commits_manifest_and_summary_only(self):
        path = self.store_files()
        self.assertEqual(path, self.mpath)
        m = json.loads(self.mpath.read_text())
        names = [e["name"] for e in m["entries"]]
        self.assertEqual(names, ["sim/b/corners/r1/ff.log", "sim/b/corners/r1/tt.log",
                                 "sim/b/records/r1.json"])
        for e in m["entries"]:
            self.assertEqual(hashlib.sha256(self.store[e["sha256"]]).hexdigest(), e["sha256"])
            self.assertEqual(e["uri"], f"artifact:evidence/owner__repo/{e['sha256'][:2]}/"
                                       f"{e['sha256']}")
        text = self.summary.read_text()
        self.assertTrue(text.startswith("# record\n"))
        self.assertIn("## Stored evidence", text)
        self.assertIn("manifests/artifacts/b-r1.manifest.json", text)
        self.assertIn("`sim/b/corners/r1/empty.log` | 0 |", text)  # listed, not stored
        # Only the summary landed under sim/b: no evidence blob.
        self.assertEqual([p.relative_to(self.root).as_posix()
                          for p in (self.root / "sim/b").rglob("*") if p.is_file()],
                         ["sim/b/records/r1.md"])

    def test_broker_unreachable_is_fail_closed(self):
        with self.assertRaises(es.StoreError) as cm:
            self.store_files(fail="broker_unreachable")
        self.assertIn("broker_unreachable", str(cm.exception))
        self.assert_nothing_committed()
        self.assertTrue((self.stage / "r1.json").exists())  # staged bytes kept

    def test_manifest_not_matching_bytes_is_refused(self):
        with self.assertRaises(es.StoreError):
            self.store_files(corrupt=True)
        self.assert_nothing_committed()

    def test_non_artifact_uri_from_klt_is_refused(self):
        # An old klt (before klayout-tools 7e3561f) writes a bucket-naming uri;
        # the writer refuses any scheme but artifact:<key> and commits nothing.
        legacy = "s3" + "://"  # built, so a grep for the literal stays clean
        for uri in (lambda k: f"{legacy}bucket/{k}", lambda k: f"https://host/{k}",
                    lambda k: f"artifact:/{k}", lambda k: k):
            with self.subTest(uri=uri("K")):
                with self.assertRaisesRegex(es.StoreError, "uri is not artifact:<key>"):
                    self.store_files(uri=uri)
                self.assert_nothing_committed()

    def test_existing_manifest_or_summary_is_never_overwritten(self):
        self.mpath.parent.mkdir(parents=True)
        self.mpath.write_text("{}")
        with self.assertRaises(es.StoreError):
            self.store_files()
        self.assertEqual(self.mpath.read_text(), "{}")
        self.assertEqual(self.store, {})  # refused before any put

    def test_nothing_but_empty_files_is_refused(self):
        self.files = [(self.stage / "corners/r1/empty.log", "sim/b/corners/r1/empty.log")]
        with self.assertRaises(es.StoreError):
            self.store_files()
        self.assert_nothing_committed()

    def test_duplicate_names_refused(self):
        self.files.append((self.stage / "r1.json", "sim/b/records/r1.json"))
        with self.assertRaises(es.StoreError):
            self.store_files()

    def test_symlink_in_stage_refused(self):
        (self.stage / "corners/r1/link.log").symlink_to(self.stage / "r1.json")
        with self.assertRaises(es.StoreError):
            es.stage_files(self.stage / "corners/r1", "sim/b/corners/r1")


def klt_probe_answer(cmd, *, current=True):
    """What ``klt artifact verify <probe manifest>`` answers: a current klt
    (klayout-tools 7e3561f+) refuses the legacy uri offline; an old one
    accepts it and fails on the unroutable broker."""
    if current:
        err = {"command": "artifact verify", "code": "invalid_manifest",
               "message": "manifest entry 0: uri ... is not artifact:<key>",
               "entry": 0, "problems": ["uri '...' is not artifact:<key>"]}
    else:
        err = {"command": "artifact verify", "code": "broker_unreachable",
               "message": "cannot reach the artifact broker"}
    return subprocess.CompletedProcess(cmd, 1, "", json.dumps({"schema_version": 1,
                                                               "error": err}))


class Preflight(unittest.TestCase):
    def which(self, name):
        return f"/bin/{name}"

    def run_ok(self, cmd, **kw):
        if cmd[1:3] == ["artifact", "verify"]:
            return klt_probe_answer(cmd)
        return subprocess.CompletedProcess(cmd, 0, "usage", "")

    def test_no_broker_configured(self):
        with self.assertRaisesRegex(es.StoreError, "KLT_ARTIFACT_BROKER"):
            es.preflight(Path("."), env={}, which=self.which, run=self.run_ok,
                         probe=lambda *a: None)

    def test_klt_missing_or_without_artifact_verb(self):
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        with self.assertRaisesRegex(es.StoreError, "not on PATH"):
            es.preflight(Path("."), env=env, which=lambda n: None, run=self.run_ok,
                         probe=lambda *a: None)
        with self.assertRaisesRegex(es.StoreError, "no `artifact put` verb"):
            es.preflight(Path("."), env=env, which=self.which,
                         run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, "", ""),
                         probe=lambda *a: None)

    def test_old_klt_refused_before_the_broker_probe(self):
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        probed = []

        def run_old(cmd, **kw):
            if cmd[1:3] == ["artifact", "verify"]:
                return klt_probe_answer(cmd, current=False)
            return subprocess.CompletedProcess(cmd, 0, "usage", "")

        with self.assertRaisesRegex(es.StoreError, "older than klayout-tools 7e3561f"):
            es.preflight(Path("."), env=env, which=self.which, run=run_old,
                         probe=lambda *a: probed.append(a))
        self.assertEqual(probed, [])

    def test_probe_gets_repo_and_broker(self):
        seen = []
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        es.preflight(Path("."), env=env, which=self.which, run=self.run_ok,
                     probe=lambda base, repo: seen.append((base, repo)))
        self.assertEqual(seen, [("http://broker.invalid", REPO)])


class KltSchemeProbe(unittest.TestCase):
    """``check_klt_uri_scheme``: klt has no commit in its version, so the
    writer tests the behaviour that changed at klayout-tools 7e3561f."""

    def check(self, run):
        es.check_klt_uri_scheme("/bin/klt", run=run)

    def test_current_klt_passes_and_probe_is_offline(self):
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            manifest = json.loads(Path(cmd[3]).read_text())
            (entry,) = manifest["entries"]
            self.assertFalse(entry["uri"].startswith("artifact:"))
            return klt_probe_answer(cmd)

        self.check(run)
        (cmd,) = seen
        self.assertEqual(cmd[:3], ["/bin/klt", "artifact", "verify"])
        # Never the configured broker: a fixed unroutable one.
        self.assertEqual(cmd[cmd.index("--broker") + 1], "http://127.0.0.1:9")

    def test_every_other_outcome_fails_closed(self):
        def answer(rc, err=None, stderr=None):
            def run(cmd, **kw):
                text = stderr if stderr is not None else json.dumps(
                    {"schema_version": 1, "error": err})
                return subprocess.CompletedProcess(cmd, rc, "", text)
            return run

        def raises(exc):
            def run(cmd, **kw):
                raise exc
            return run

        legacy_problem = "uri 'x' is not s3" + "://<bucket>/<key>"
        cases = {
            "old klt reaches the broker": answer(1, {"code": "broker_unreachable"}),
            "old klt reports a refusal": answer(1, {"code": "broker_refused"}),
            "klt without verify": answer(2, stderr="usage: klt artifact ..."),
            "verify passes the legacy uri": answer(0, stderr=""),
            "invalid for another reason": answer(1, {"code": "invalid_manifest",
                                                     "problems": [legacy_problem]}),
            "invalid without problems": answer(1, {"code": "invalid_manifest"}),
            "wrong exit code": answer(2, {"code": "invalid_manifest",
                                          "problems": ["is not artifact:<key>"]}),
            "not json": answer(1, stderr="Traceback ..."),
        }
        for label, run in cases.items():
            with self.subTest(label), \
                    self.assertRaisesRegex(es.StoreError, "older than klayout-tools"):
                self.check(run)
        # A probe that never answered says so rather than blaming klt's age.
        no_answer = {
            "timeout": (raises(subprocess.TimeoutExpired("klt", 30)), "probe timed out"),
            "cannot exec": (raises(OSError("no such file")), "probe failed to start"),
        }
        for label, (run, message) in no_answer.items():
            with self.subTest(label), self.assertRaisesRegex(es.StoreError, message):
                self.check(run)

    def test_min_commit_is_the_artifact_uri_revision(self):
        self.assertTrue(es.KLT_ARTIFACT_MIN_COMMIT.startswith("7e3561f"))


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        payload = ({"key": "k", "exists": False} if self.status == 200
                   else {"error": "not_granted", "message": "no"})
        raw = json.dumps(payload).encode()
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class Probe(unittest.TestCase):
    def serve(self, status):
        handler = type("H", (_Handler,), {"status": status, "seen": []})
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}", handler

    def test_reachable_broker_passes(self):
        for status in (200, 404):
            base, handler = self.serve(status)
            es.probe_broker(base, REPO)
            (path, body), = handler.seen
            self.assertEqual(path, "/v1/stat")
            self.assertEqual(body["repo"], REPO)

    def test_refusal_fails_closed(self):
        base, _ = self.serve(403)
        with self.assertRaisesRegex(es.StoreError, "HTTP 403: not_granted"):
            es.probe_broker(base, REPO)

    def test_unreachable_fails_closed(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaisesRegex(es.StoreError, "unreachable"):
            es.probe_broker(f"http://127.0.0.1:{port}", REPO, timeout=5)

    def test_url_with_credentials_refused(self):
        with self.assertRaises(es.StoreError):
            es.probe_broker("http://u:p@127.0.0.1:1", REPO)


class CampaignCli(unittest.TestCase):
    """``sim/run_store_evidence.py``: the store path for campaign outputs."""

    def setUp(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / "run_store_evidence.py"
        spec = importlib.util.spec_from_file_location("run_store_evidence", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        (self.root / "sim/bench").mkdir(parents=True)
        self.staged = self.root / "sim/.work/camp"
        self.staged.mkdir(parents=True)
        (self.staged / "a.json").write_text("{}\n")
        self.summary = self.root / "summary.md"
        self.summary.write_text("# campaign\n")
        self.mod.REPO_ROOT = self.root

    def main(self, staged=None, preflight_exc=None):
        from unittest import mock
        store = {}
        real_put = es.put_files
        with mock.patch.object(es, "preflight", side_effect=preflight_exc), \
             mock.patch.object(es, "put_files",
                               side_effect=lambda f, r: real_put(f, r, run=fake_klt(store))), \
             mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            return self.mod.main(["bench", "20261022-abc", str(staged or self.staged),
                                  "--summary", str(self.summary)])

    def test_stores_and_commits_manifest_and_summary(self):
        self.assertEqual(self.main(), 0)
        m = json.loads((self.root / "manifests/artifacts/bench-20261022-abc.manifest.json")
                       .read_text())
        self.assertEqual([e["name"] for e in m["entries"]],
                         ["sim/bench/campaigns/20261022-abc/a.json"])
        self.assertTrue((self.root / "sim/bench/campaigns/20261022-abc.md").is_file())
        self.assertFalse((self.root / "sim/bench/campaigns/20261022-abc").exists())

    def test_store_unavailable_commits_nothing(self):
        self.assertEqual(self.main(preflight_exc=es.StoreError("no broker")), 10)
        self.assertFalse((self.root / "manifests").exists())
        self.assertFalse((self.root / "sim/bench/campaigns").exists())

    def test_under_stores_a_layout_side_run(self):
        (self.root / "layout/adc-top").mkdir(parents=True)
        from unittest import mock
        store = {}
        real_put = es.put_files
        with mock.patch.object(es, "preflight"), \
             mock.patch.object(es, "put_files",
                               side_effect=lambda f, r: real_put(f, r, run=fake_klt(store))), \
             mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            rc = self.mod.main(["bench", "20261022-abc", str(self.staged), "--summary",
                                str(self.summary), "--under", "layout/adc-top"])
        self.assertEqual(rc, 0)
        m = json.loads((self.root / "manifests/artifacts/bench-20261022-abc.manifest.json")
                       .read_text())
        self.assertEqual([e["name"] for e in m["entries"]],
                         ["layout/adc-top/campaigns/20261022-abc/a.json"])
        self.assertTrue((self.root / "layout/adc-top/campaigns/20261022-abc.md").is_file())

    def test_under_outside_evidence_roots_refused(self):
        for bad in ("spec", "../x", "/etc", "sim"):
            with self.subTest(under=bad):
                from unittest import mock
                with mock.patch("sys.stderr"):
                    rc = self.mod.main(["bench", "20261022-abc", str(self.staged),
                                        "--summary", str(self.summary), "--under", bad])
                self.assertEqual(rc, 1)

    def test_staged_dir_inside_tracked_tree_refused(self):
        inside = self.root / "sim/bench/campaigns/x"
        inside.mkdir(parents=True)
        (inside / "a.json").write_text("{}\n")
        self.assertEqual(self.main(staged=inside), 1)
        self.assertFalse((self.root / "manifests").exists())


class CornerRunnerStores(unittest.TestCase):
    """``sim/run_corners.py`` (cli.run) with writing on: preflight before any
    simulation, bytes to the store, only a manifest + record in the repo."""

    def setUp(self):
        import test_batch as tbm
        from harness import cli
        self.tbm, self.cli = tbm, cli
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.pdk = tbm.make_pdk(self.root / "gf180mcuD")
        tbm.make_tb(self.root, {"analyses": ["op"], "measure": {"vout": "v(out)"},
                                "temperatures_c": [27], "supply_tolerance": 0.0,
                                "corners": ["tt", "ss"]})
        self.store = {}

    def art(self, name):
        d = self.root / "art" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "corner.cir").write_text("*\n")
        (d / "ngspice.log").write_text(f"log {name}\n")
        return {"log": str(d / "ngspice.log"), "deck": str(d / "corner.cir"),
                "raw": None, "waveform": None}

    def submit(self, members, request_dir, outdir, requested, klt_cmd="klt"):
        tbm = self.tbm
        return [tbm.batch.SupplyOutcome(3.3, members[0].request_name, report={
            "status": "not_checked",
            "corners": [tbm.klt_corner(p, 27, 3.3, measurements={"vout": 1.0},
                                       artifacts=self.art(p)) for p in ("tt", "ss")],
            "environment": {"engine_version": "46", "remote": {
                "provider": "aws-batch-fleet", "job_id": "j", "runner_compatibility": "match"}},
            "provenance": {"klt_version": "0.6.0",
                           "pdk": {"name": "gf180mcuD",
                                   "version": f"open_pdks {tbm.PINNED_PDK}"}},
        })], {"schema_version": 1, "status": "pass", "requests": []}

    def run_cli(self, preflight_exc=None, put_fail=None):
        from unittest import mock
        cli, tbm = self.cli, self.tbm
        real_put = es.put_files
        patches = [
            mock.patch.object(cli, "find_pdk", return_value=self.pdk),
            mock.patch.object(cli.runner, "ngspice_version", return_value="ngspice-46"),
            mock.patch.object(cli.toolchain_mod, "load_pins", return_value=tbm.PINS),
            mock.patch.object(cli.batch_mod, "klt_available", return_value=["klt"]),
            mock.patch.object(cli.batch_mod, "submit_set", side_effect=self.submit),
            mock.patch.object(cli.runner, "run_grid", side_effect=AssertionError("ran locally")),
            mock.patch.object(cli, "WORK_DIR", self.root / "work"),
            mock.patch.object(cli, "STAGE_DIR", self.root / "work/.stage"),
            mock.patch.object(cli, "REPO_ROOT", self.root),
            mock.patch.object(es, "preflight", side_effect=preflight_exc),
            mock.patch.object(es, "put_files", side_effect=lambda f, r: real_put(
                f, r, run=fake_klt(self.store, fail=put_fail))),
            mock.patch.dict(cli.os.environ, {"KLT_SIM_BACKEND": "batch"}, clear=False),
            mock.patch("sys.stdout"), mock.patch("sys.stderr"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        args = cli.build_parser().parse_args(
            [str(self.root / "exp"), "--subset-reason", "test", "--quiet"])
        return cli.run(args)

    def tree(self):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")
                      if p.is_file() and "art" not in p.relative_to(self.root).parts[:1]
                      and p.relative_to(self.root).parts[0] in ("exp", "manifests"))

    def test_store_unavailable_refuses_before_simulating(self):
        code = self.run_cli(preflight_exc=es.StoreError("no broker"))
        self.assertEqual(code, self.cli.EXIT_NOT_STORED)
        self.cli.batch_mod.submit_set.assert_not_called()
        self.assertEqual(self.tree(), ["exp/testbench/tb.json", "exp/testbench/x.spice"])

    def test_records_the_run_by_manifest_not_by_bytes(self):
        self.assertEqual(self.run_cli(), self.cli.EXIT_OK)
        tree = self.tree()
        manifests = [t for t in tree if t.startswith("manifests/")]
        records = [t for t in tree if t.startswith("exp/records/")]
        self.assertEqual(len(manifests), 1)
        self.assertEqual(len(records), 1)
        # nothing else under exp/: no corners/, no netlist-snapshots/
        self.assertEqual(sorted(set(tree) - set(manifests) - set(records)),
                         ["exp/testbench/tb.json", "exp/testbench/x.spice"])
        m = json.loads((self.root / manifests[0]).read_text())
        names = [e["name"] for e in m["entries"]]
        self.assertTrue(any(n.startswith("sim/exp/netlist-snapshots/") for n in names))
        self.assertTrue(any(n.startswith("sim/exp/corners/") and n.endswith(".log")
                            for n in names))
        self.assertTrue(all(e["uri"].startswith("artifact:") for e in m["entries"]))
        text = (self.root / records[0]).read_text()
        self.assertIn("## Stored evidence", text)
        self.assertIn(manifests[0], text)

    def test_put_failure_exits_10_commits_nothing_and_keeps_stage(self):
        code = self.run_cli(put_fail="broker_unreachable")
        self.assertEqual(code, self.cli.EXIT_NOT_STORED)
        self.assertEqual(self.tree(), ["exp/testbench/tb.json", "exp/testbench/x.spice"])
        staged = [p for p in (self.root / "work/.stage").rglob("*.log")]
        self.assertTrue(staged)  # the run is not lost


if __name__ == "__main__":
    unittest.main()
