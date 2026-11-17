#!/usr/bin/env python3
"""Negative controls for scripts/check_layout_pins.py (issues #898, #902).

Builds a throwaway tree with the three evidence manifests (LVS, DRC,
parasitics -- same object shapes as the real ones, pins computed from the
fixture bytes) plus layout record families, then asserts the check's verdict
on one sabotage at a time. A guard that cannot go red is not a guard.
Stdlib only.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_layout_pins", ROOT / "scripts" / "check_layout_pins.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

LVS = "layout/lvs/cells/cells.json"
DRC = "layout/drc/cells/cells.json"
PARA = "layout/adc-top/parasitics/cells.json"
RECORDS_DIR = "layout/x/records"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Fixture:
    """A minimal tree with every manifest the check reads, all pins valid."""

    def __init__(self, root: Path):
        self.root = root
        gds, sp = b"GDS", b".subckt unit S G D\n.ends\n"
        req, ref = b"{\"request\": true}\n", b".subckt ref S G D\n.ends\n"
        dgds = b"DRCGDS"
        top = b"TOPGDS"
        self.files = {
            "layout/lvs/cells/unit.gds": gds,
            "layout/lvs/cells/unit.spice": sp,
            "layout/lvs/cells/match.lvs.json": req,
            "layout/lvs/cells/match.ref.spice": ref,
            "layout/drc/cells/sw.gds": dgds,
            "layout/adc-top/top.gds": top,
        }
        self.manifests = {
            LVS: {
                "extract": {
                    "name": "unit", "gds": "unit.gds", "sha256": sha(gds),
                    "netlist": "unit.spice", "netlist_sha256": sha(sp),
                },
                "lvs_cases": [{
                    "name": "match",
                    "request": "match.lvs.json", "request_sha256": sha(req),
                    "reference": "match.ref.spice", "sha256": sha(ref),
                }],
            },
            DRC: {"cells": [{"name": "sw", "gds": "sw.gds", "sha256": sha(dgds)}]},
            PARA: {"blocks": {"top": {"gds": "../top.gds", "gds_sha256": sha(top)}}},
        }
        self.write_all()

    def write_all(self):
        for rel, data in self.files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        for rel, doc in self.manifests.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def manifest(self, rel):
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def save(self, rel, doc):
        (self.root / rel).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def record(self, name, status=None):
        p = self.root / RECORDS_DIR
        p.mkdir(parents=True, exist_ok=True)
        body = "# Record " + name + "\n"
        if status is not None:
            body += f"\n- **Overall** — {status} (fixture)\n"
        (p / name).write_text(body, encoding="utf-8")

    def run(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = chk.main(["--repo", str(self.root)])
        return rc, err.getvalue()


class PinTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fx = Fixture(Path(self._tmp.name))

    def mutate(self, rel, fn):
        doc = self.fx.manifest(rel)
        fn(doc)
        self.fx.save(rel, doc)

    def test_clean_tree_passes(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = chk.main(["--repo", str(self.fx.root)])
        self.assertEqual(rc, 0)
        self.assertEqual(err.getvalue(), "")
        self.assertIn("hash pin(s)", out.getvalue())
        self.assertIn("re-derived from the committed bytes", out.getvalue())

    def test_stale_pin_fails_naming_manifest_key_and_both_digests(self):
        self.mutate(LVS, lambda d: d["lvs_cases"][0].__setitem__(
            "sha256", ("0" if d["lvs_cases"][0]["sha256"][0] != "0" else "1")
            + d["lvs_cases"][0]["sha256"][1:]))
        rc, err = self.fx.run()
        self.assertEqual(rc, 1)
        self.assertIn(f"{LVS}: lvs_cases[0].sha256", err)
        self.assertIn("pinned sha256", err)
        self.assertIn("!= actual", err)
        self.assertIn("match.ref.spice", err)

    def test_missing_file_fails(self):
        (self.fx.root / "layout/lvs/cells/match.ref.spice").unlink()
        rc, err = self.fx.run()
        self.assertEqual(rc, 1)
        self.assertIn("missing from the tree", err)
        self.assertIn("match.ref.spice", err)

    def test_unknown_pin_key_fails_closed(self):
        self.mutate(DRC, lambda d: d["cells"][0].__setitem__("blob_sha256", sha(b"x")))
        rc, err = self.fx.run()
        self.assertEqual(rc, 1)
        self.assertIn("unrecognised pin key", err)

    def test_bare_sha_without_sibling_fails_closed(self):
        self.mutate(LVS, lambda d: d["lvs_cases"][0].pop("reference"))
        rc, err = self.fx.run()
        self.assertEqual(rc, 1)
        self.assertIn("no recognised sibling path", err)

    def test_path_escaping_repo_fails(self):
        outside = self.fx.root.parent / "outside.gds"
        outside.write_bytes(b"OUT")
        self.mutate(DRC, lambda d: d["cells"][0].__setitem__(
            "gds", "../../../../outside.gds"))
        try:
            rc, err = self.fx.run()
            self.assertEqual(rc, 1)
            self.assertIn("outside the repository", err)
        finally:
            outside.unlink()

    def test_malformed_pin_fails(self):
        self.mutate(DRC, lambda d: d["cells"][0].__setitem__("sha256", "ZZ"))
        rc, err = self.fx.run()
        self.assertEqual(rc, 1)
        self.assertIn("64 lowercase hex digits", err)

    def test_unreadable_manifest_fails_closed(self):
        (self.fx.root / LVS).unlink()
        rc, err = self.fx.run()
        self.assertEqual(rc, 2)
        self.assertIn("unreadable manifest", err)

    def test_invalid_json_fails_closed(self):
        (self.fx.root / LVS).write_text("{not json", encoding="utf-8")
        rc, err = self.fx.run()
        self.assertEqual(rc, 2)
        self.assertIn("unreadable manifest", err)


class RecordVerdictTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fx = Fixture(Path(self._tmp.name))

    def run_check(self):
        return self.fx.run()

    def run_full(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = chk.main(["--repo", str(self.fx.root)])
        return rc, out.getvalue(), err.getvalue()

    def write_raw(self, name, body):
        p = self.fx.root / RECORDS_DIR
        p.mkdir(parents=True, exist_ok=True)
        (p / name).write_text(body, encoding="utf-8")

    def gds_verdict_record(self, name, word):
        self.write_raw(name, "# Record " + name + "\n\n"
                       f"- **Verdict (committed GDS vs golden)**: "
                       f"**`{word}`** -- fixture entries\n")

    def test_newest_pass_record_passes(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        rc, err = self.run_check()
        self.assertEqual((rc, err), (0, ""))

    def test_newest_fail_record_fails(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.fx.record("20260102-000000-b.md", "FAIL")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("newest record asserts 'Overall — FAIL'", err)
        self.assertIn("20260102-000000-b.md", err)

    def test_newer_pass_supersedes_older_fail(self):
        self.fx.record("20260101-000000-a.md", "FAIL")
        self.fx.record("20260102-000000-b.md", "PASS")
        rc, err = self.run_check()
        self.assertEqual((rc, err), (0, ""))

    def test_later_adjudicated_supersedes_fail(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.fx.record("20260102-000000-b.md", "FAIL")
        self.fx.record("20260103-000000-c.md", "ADJUDICATED")
        rc, err = self.run_check()
        self.assertEqual((rc, err), (0, ""))

    def test_newest_record_without_overall_passes(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.fx.record("20260102-000000-b.md", None)
        rc, err = self.run_check()
        self.assertEqual((rc, err), (0, ""))

    def test_proven_and_other_statuses_pass(self):
        self.fx.record("20260101-000000-a.md", "PROVEN")
        rc, err = self.run_check()
        self.assertEqual((rc, err), (0, ""))

    # -- undeclared names fail closed (issue #902 case 1) -----------------

    def test_undeclared_readme_fails_closed(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.write_raw("README.md", "# Records\n")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("not a declared record name", err)
        self.assertIn("README.md", err)

    def test_undeclared_notes_file_named(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.write_raw("NOTES.md", "# Notes\n")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("NOTES.md", err)

    def test_undeclared_file_never_becomes_newest(self):
        # The measured trap: README sorts after every timestamped name, and
        # the family used to silently stop being verdict-checked. The FAIL
        # record must still be reported.
        self.fx.record("20260101-000000-a.md", "FAIL")
        self.write_raw("README.md", "# Records\n")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("newest record asserts 'Overall — FAIL'", err)

    def test_declared_nonrecord_is_exempt_and_never_newest(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.write_raw("README.md", "# Records\n")
        saved = chk.DECLARED_NONRECORD_NAMES
        chk.DECLARED_NONRECORD_NAMES = frozenset({"README.md"})
        try:
            rc, out, err = self.run_full()
        finally:
            chk.DECLARED_NONRECORD_NAMES = saved
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("newest=20260101-000000-a.md status=PASS", out)

    def test_slug_shape_declared_only_for_parasitics(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.write_raw("20260805-remediation-dc.md", "# other family\n")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("not a declared record name", err)
        self.assertIn("20260805-remediation-dc.md", err)

    def test_parasitics_slug_records_accepted(self):
        p = self.fx.root / "layout/adc-top/parasitics/records"
        p.mkdir(parents=True, exist_ok=True)
        (p / "20260805-remediation-dc.md").write_text("# older slug\n",
                                                      encoding="utf-8")
        (p / "20260806-140411-968d138.md").write_text("# newest ts\n",
                                                      encoding="utf-8")
        rc, out, err = self.run_full()
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("layout/adc-top/parasitics/records: "
                      "newest=20260806-140411-968d138.md status=none", out)

    # -- sar_ctrl GDS verdict schema (issue #902 case 2) -------------------

    def test_sar_ctrl_match_verdict_passes(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.gds_verdict_record("20260102-000000-b.md", "match")
        rc, out, err = self.run_full()
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("status=match", out)

    def test_sar_ctrl_no_match_fails(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.gds_verdict_record("20260102-000000-b.md", "no match")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("Verdict (committed GDS vs golden) — no match", err)
        self.assertIn("20260102-000000-b.md", err)

    def test_sar_ctrl_mismatch_fails(self):
        # the value the family's own older record uses
        self.fx.record("20260101-000000-a.md", "PASS")
        self.gds_verdict_record("20260102-000000-b.md", "mismatch")
        rc, err = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("Verdict (committed GDS vs golden) — mismatch", err)

    # -- OK-line report (issue #902 AC 3) ----------------------------------

    def test_ok_line_reports_newest_per_family(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.fx.record("20260102-000000-b.md", "PROVEN")
        rc, out, err = self.run_full()
        self.assertEqual((rc, err), (0, ""))
        self.assertIn(f"{RECORDS_DIR}: newest=20260102-000000-b.md "
                      "status=PROVEN", out)

    def test_verdict_less_newest_reported_as_none(self):
        self.fx.record("20260101-000000-a.md", "PASS")
        self.fx.record("20260102-000000-b.md", None)
        rc, out, err = self.run_full()
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("newest=20260102-000000-b.md status=none", out)


if __name__ == "__main__":
    unittest.main()
