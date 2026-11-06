"""Issue #708: `run_pex_adc_block.py` stores its bytes through the artifact
store (DR-0041 / #636) and commits only a manifest + record. Fail closed.

Stdlib only; `klt artifact put` is emulated by the injected `put`/`run` of
`harness.evidence_store`, as in test_evidence_store.py.
"""

from __future__ import annotations

import argparse
import json
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

    def store_files(self, files, **kw):
        return es.store_files(
            files, repo_root=self.root, bench=mod.BENCH, rid="r1",
            summary_text=mod.record_body(
                "r1", {"version": "0.7.0"}, {"variant": "gf180mcuD", "version": "v"},
                REPORT, 0, ["klt"], 1.0, "local", [], nominal=True, subset_reason="x",
                manifest_rel="manifests/artifacts/adc-block-pex-r1.manifest.json"),
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


class Preflight(unittest.TestCase):
    def args(self, **kw):
        d = dict(klt="klt", backend=None, probe=False, nominal=True, check=False,
                 subset_reason="r", keep_scratch=False, artifact_klt="klt")
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
