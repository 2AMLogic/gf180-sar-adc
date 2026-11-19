"""Issue #708: `run_pex_adc_block.py` stores its bytes through the artifact
store (DR-0041 / #636) and commits only a manifest + record. Fail closed.

Issue #927 adds the `--signoff` publication path: the per-corner report's
destination is decided BEFORE the record is minted. A signoff run commits the
report at `signoff/evidence/adc-block-pex-<record-id>.pex-report.json` (the
path the signoff manifest's `7.analog` cites) and stores only the remaining
objects, so the record's Stored-evidence table always matches its final
manifest and no fetch command names an entry a signoff step dropped. A
store-only run keeps publishing the report through its manifest.

Stdlib only; `klt artifact put` is emulated by the injected `put`/`run` of
`harness.evidence_store`, as in test_evidence_store.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "sim"))

from _loadmod import load_module  # noqa: E402
from test_evidence_store import fake_klt  # noqa: E402

mod = load_module("run_pex_adc_block_under_test",
                  REPO / "layout/adc-top/parasitics/run_pex_adc_block.py")
es = mod.store_mod

REPORT = {"status": "pass", "delta": [{"corner_id": "tt", "spec_row": "vres_diff",
                                       "schematic_value": 1.0, "extracted_value": 0.9,
                                       "delta_pct": -10.0, "status": "pass"}],
          "passed": 1, "failed": 0, "errored": 0, "corner_count": 1}


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.stage = self.root / "sim/.work/.stage/adc-block-pex"
        self.extracted = self.root / "adc_block.pex.spice"
        self.extracted.write_text(".SUBCKT ADC_BLOCK a b\n.ENDS\n")
        self.store = {}

    def files(self, stderr="warn\n"):
        return mod.stage_evidence("r1", REPORT, stderr, str(self.extracted), str(self.stage))

    def store_files(self, files, signoff_report=None, **kw):
        return es.store_files(
            files, repo_root=self.root, bench=mod.BENCH, rid="r1",
            summary_text=mod.record_body(
                "r1", {"version": "0.7.0"}, {"variant": "gf180mcuD", "version": "v"},
                REPORT, 0, ["klt"], 1.0, "local", [], nominal=True, subset_reason="x",
                manifest_rel="manifests/artifacts/adc-block-pex-r1.manifest.json",
                signoff_report=signoff_report),
            summary_path=self.root / "sim/adc-block-pex/records/r1.md",
            put=lambda f, r: es.put_files(f, r, run=fake_klt(self.store, **kw)))


class Store(Base):
    def test_logical_names_and_only_manifest_plus_record_in_tree(self):
        self.store_files(self.files())
        m = json.loads((self.root / "manifests/artifacts/adc-block-pex-r1.manifest.json").read_text())
        self.assertEqual([e["name"] for e in m["entries"]], [
            "sim/adc-block-pex/corners/r1/klt-pex.stderr.txt",
            "sim/adc-block-pex/corners/r1/pex-report.json",
            "sim/adc-block-pex/netlist-snapshots/r1.spice"])
        tracked = sorted(p.relative_to(self.root).as_posix()
                         for p in self.root.rglob("*")
                         if p.is_file() and ".work" not in p.parts and p != self.extracted)
        self.assertEqual(tracked, ["manifests/artifacts/adc-block-pex-r1.manifest.json",
                                   "sim/adc-block-pex/records/r1.md"])
        text = (self.root / "sim/adc-block-pex/records/r1.md").read_text()
        self.assertIn("(stored, not in git; manifest `manifests/artifacts/adc-block-pex-r1.manifest.json`)", text)
        self.assertIn("## Stored evidence", text)
        # Issue #927: the per-corner citation presents a name the manifest
        # resolves -- the fetch command in the record must never dangle.
        line = next(ln for ln in text.splitlines() if ln.startswith("Per-corner rows:"))
        cited = re.search(r"`(corners/[^`]+)`", line).group(1)
        self.assertIn(f"sim/adc-block-pex/{cited}", [e["name"] for e in m["entries"]])

    def test_blank_stderr_not_staged(self):
        names = [n for _, n in self.files(stderr="  \n")]
        self.assertNotIn("sim/adc-block-pex/corners/r1/klt-pex.stderr.txt", names)

    def test_failing_put_commits_nothing_and_keeps_stage(self):
        files = self.files()
        with self.assertRaises(es.StoreError):
            self.store_files(files, fail="broker_unreachable")
        self.assertFalse((self.root / "manifests").exists())
        self.assertFalse((self.root / "sim/adc-block-pex").exists())
        self.assertTrue(all(p.is_file() for p, _ in files))

    def test_same_record_id_refused(self):
        self.store_files(self.files())
        with self.assertRaises(es.StoreError):
            self.store_files(self.files())


class Signoff(Base):
    """Issue #927: the `--signoff` publication path. The report's bytes are
    committed at `signoff/evidence/` -- the path the signoff manifest's
    `7.analog` cites -- the record cites that git path with its sha256, and
    only the remaining objects go through the store, so the Stored-evidence
    table always matches the final manifest."""

    def publish(self):
        return mod.publish_signoff_report("r1", REPORT, repo_root=str(self.root))

    def signoff_files(self, stderr="warn\n"):
        return mod.stage_evidence("r1", REPORT, stderr, str(self.extracted),
                                  str(self.stage), store_report=False)

    def test_report_committed_exactly_once_at_the_signoff_path(self):
        rel, sha = self.publish()
        self.assertEqual(rel, "signoff/evidence/adc-block-pex-r1.pex-report.json")
        dest = self.root / rel
        self.assertEqual(dest.read_text(),
                         json.dumps(REPORT, indent=2, sort_keys=True) + "\n")
        self.assertEqual(sha, hashlib.sha256(dest.read_bytes()).hexdigest())
        with self.assertRaises(mod.ToolingError):
            self.publish()
        self.assertEqual(dest.read_text(),
                         json.dumps(REPORT, indent=2, sort_keys=True) + "\n")

    def test_stored_table_matches_manifest_and_citation_resolves_in_git(self):
        rel, sha = self.publish()
        self.store_files(self.signoff_files(), signoff_report=(rel, sha))
        m = json.loads(
            (self.root / "manifests/artifacts/adc-block-pex-r1.manifest.json").read_text())
        text = (self.root / "sim/adc-block-pex/records/r1.md").read_text()
        total = sum(e["size"] for e in m["entries"])
        self.assertIn(f"({len(m['entries'])} objects, {total} B)", text)
        for e in m["entries"]:
            self.assertIn(f"| `{e['name']}` | {e['size']} | `{e['sha256']}` |", text)
        # The per-corner citation names the committed copy with its sha256 --
        # and the report is nowhere presented as a stored object.
        line = next(ln for ln in text.splitlines() if ln.startswith("Per-corner rows:"))
        self.assertIn(f"`{rel}`", line)
        self.assertIn(f"`{sha}`", line)
        self.assertNotIn("corners/r1/pex-report.json", line)
        self.assertNotIn(sha, [e["sha256"] for e in m["entries"]])

    def test_signoff_run_with_blank_stderr_stores_one_object(self):
        rel, sha = self.publish()
        files = self.signoff_files(stderr="  \n")
        self.assertEqual([n for _, n in files],
                         ["sim/adc-block-pex/netlist-snapshots/r1.spice"])
        self.store_files(files, signoff_report=(rel, sha))
        m = json.loads(
            (self.root / "manifests/artifacts/adc-block-pex-r1.manifest.json").read_text())
        text = (self.root / "sim/adc-block-pex/records/r1.md").read_text()
        self.assertIn(f"(1 objects, {m['entries'][0]['size']} B)", text)


class RunSignoff(Base):
    """`--signoff` end to end through `run()`: the destination is decided
    before the record is minted, and a failed store leaves no partial
    signoff evidence (issue #927)."""

    def run_signoff(self, fail=None, **kw):
        args = dict(klt="klt", backend=None, capacity_wait=0, probe=False,
                    nominal=False, check=False, subset_reason=None,
                    supersedes=None, signoff=True, artifact_klt="klt",
                    keep_scratch=False)
        args.update(kw)
        real_put = es.put_files  # bind before the patch below shadows it
        put = es.StoreError("klt artifact put failed (exit 1)") if fail else \
            (lambda f, r, **kw: real_put(f, r, run=fake_klt(self.store)))
        with mock.patch.object(mod, "REPO_ROOT", str(self.root)), \
             mock.patch.object(mod, "STAGE_DIR", str(self.stage)), \
             mock.patch.object(mod, "RECORDS_DIR",
                               str(self.root / "sim/adc-block-pex/records")), \
             mock.patch.object(mod, "check_klt", return_value={"version": "0.9.0"}), \
             mock.patch.object(mod, "resolve_pdk",
                               return_value={"variant": "gf180mcuD", "version": "v"}), \
             mock.patch.object(mod.store_mod, "preflight"), \
             mock.patch.object(mod, "run_pex", return_value=(
                 REPORT, 0, ["klt"], "warn\n", 1.0, str(self.extracted))), \
             mock.patch.object(mod, "record_id", return_value="r1"), \
             mock.patch.object(mod.store_mod, "put_files", side_effect=put):
            rc = mod.run(argparse.Namespace(**args))
        return rc

    def test_signoff_run_mints_record_citing_the_committed_report(self):
        rc = self.run_signoff()
        self.assertEqual(rc, 0)
        dest = self.root / "signoff/evidence/adc-block-pex-r1.pex-report.json"
        self.assertTrue(dest.is_file())
        m = json.loads(
            (self.root / "manifests/artifacts/adc-block-pex-r1.manifest.json").read_text())
        names = [e["name"] for e in m["entries"]]
        self.assertNotIn("sim/adc-block-pex/corners/r1/pex-report.json", names)
        text = (self.root / "sim/adc-block-pex/records/r1.md").read_text()
        self.assertIn("signoff/evidence/adc-block-pex-r1.pex-report.json", text)
        self.assertNotIn("corners/r1/pex-report.json", text)

    def test_failed_put_removes_the_signoff_copy_and_commits_nothing(self):
        rc = self.run_signoff(fail="broker_unreachable")
        self.assertEqual(rc, mod.EXIT_NOT_STORED)
        self.assertFalse(
            (self.root / "signoff/evidence/adc-block-pex-r1.pex-report.json").exists())
        self.assertFalse((self.root / "manifests").exists())
        self.assertFalse((self.root / "sim/adc-block-pex").exists())
        self.assertTrue((self.stage / "r1").is_dir())

    def test_signoff_refused_with_probe(self):
        with mock.patch.object(mod, "publish_signoff_report") as publish, \
             redirect_stderr(StringIO()) as err:
            rc = self.run_signoff(probe=True)
        self.assertEqual(rc, 1)
        publish.assert_not_called()
        self.assertIn("--probe writes nothing", err.getvalue())


class Preflight(unittest.TestCase):
    def args(self, **kw):
        d = dict(klt="klt", backend=None, probe=False, nominal=True, check=False,
                 subset_reason="r", keep_scratch=False, artifact_klt="klt",
                 signoff=False)
        d.update(kw)
        return argparse.Namespace(**d)

    def test_preflight_failure_exits_before_klt_pex(self):
        with mock.patch.object(mod, "check_klt", return_value={"version": "0.7.0"}), \
             mock.patch.object(mod, "resolve_pdk", return_value={"variant": "x"}), \
             mock.patch.object(mod.store_mod, "preflight",
                               side_effect=es.StoreError("no artifact broker configured")), \
             mock.patch.object(mod, "run_pex") as run_pex, \
             redirect_stderr(StringIO()) as err:
            rc = mod.run(self.args())
        self.assertEqual(rc, mod.EXIT_NOT_STORED)
        run_pex.assert_not_called()
        self.assertIn("EVIDENCE STORE UNAVAILABLE", err.getvalue())

    def test_check_and_probe_need_no_store(self):
        with mock.patch.object(mod, "check_klt", return_value={"version": "0.7.0", "git_commit": "c" * 40}), \
             mock.patch.object(mod, "resolve_pdk", return_value={"variant": "x"}), \
             mock.patch.object(mod.store_mod, "preflight") as pf:
            self.assertEqual(mod.run(self.args(check=True, nominal=False)), 0)
            pf.assert_not_called()


if __name__ == "__main__":
    unittest.main()
