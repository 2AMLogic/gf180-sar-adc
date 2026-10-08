#!/usr/bin/env python3
"""Regression controls for `sim/tools/check_readme_status.py` (issue #415).

    python3 -m unittest discover -s sim/tests -v

The README Status summary must equal the report `signoff/freshness.json`
selects and the non-passing rows of `sim/characterization-summary.md`; the
historical phrase guards must still bite on README Status but not on the
archived narrative under `docs/`. Stdlib only.
"""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim" / "tools"))
import check_readme_status as C  # noqa: E402


class SummaryTests(unittest.TestCase):
    def setUp(self):
        text = C.README.read_text(encoding="utf-8")
        self.status = C._status_table_text()
        self.report = C._selected_report()
        self.char = C.CHAR_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("## Status", text)

    def errs(self, status=None, report=None, char=None):
        return C.check_summary(
            self.status if status is None else status,
            self.report if report is None else report,
            self.char if char is None else char,
        )

    def test_committed_state_is_clean(self):
        self.assertEqual(self.errs(), [])

    def test_wrong_met_count(self):
        r = dict(self.report, t1_met_count=self.report["t1_met_count"] + 1)
        self.assertTrue(any("counts" in e for e in self.errs(report=r)))

    def test_wrong_total_count(self):
        r = dict(self.report, t1_item_count=self.report["t1_item_count"] + 1)
        self.assertTrue(any("counts" in e for e in self.errs(report=r)))

    def test_wrong_tier(self):
        r = dict(self.report, tier="T1")
        self.assertTrue(any("tier" in e for e in self.errs(report=r)))

    def test_missing_or_malformed_summary(self):
        s = self.status.replace(C.SUMMARY_BEGIN, "")
        self.assertTrue(any("markers" in e for e in self.errs(status=s)))
        # Match whatever count the live README carries, so a re-grade that
        # moves the count does not silently turn this into a no-op control.
        s = re.sub(r"\*\*\d+ of \d+ T1", "**seven T1", self.status, count=1)
        self.assertNotEqual(s, self.status)
        self.assertTrue(any("counts" in e for e in self.errs(status=s)))
        s = self.status.replace("`tier: none`", "tier none")
        self.assertTrue(any("tier" in e for e in self.errs(status=s)))

    def test_report_selection_follows_freshness_not_a_hardcoded_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "signoff" / "reports" / "x").mkdir(parents=True)
            (root / "signoff" / "freshness.json").write_text(json.dumps(
                {"report": {"record_id": "19990101-000000-deadbee",
                            "json": "signoff/reports/x/signoff.json"}}))
            (root / "signoff" / "reports" / "x" / "signoff.json").write_text(
                json.dumps({"tier": "T1", "t1_met_count": 22, "t1_item_count": 22}))
            rep = C._selected_report(root)
            self.assertEqual((rep["tier"], rep["_record_id"]), ("T1", "19990101-000000-deadbee"))
            errs = C.check_summary(self.status, rep, self.char)
            self.assertTrue(any("19990101-000000-deadbee" in e for e in errs))

    def test_spec_row_projection_controls(self):
        rows = C.char_summary_rows(self.char)
        self.assertEqual(set(rows.values()) - {"FAIL", "Unmeasured", "PASS, stretch missed"}, set())
        self.assertEqual(rows["ENOB @ Nyquist"], "FAIL")
        # A source verdict flips: the stale README table must now fail.
        flipped = self.char.replace("| **FAIL** (governing extracted result at the current design, and schematic; re-confirmed on a clean tree, issue #249) — regression flagged", "| **PASS** (x) — regression flagged", 1)
        self.assertNotEqual(flipped, self.char)
        self.assertTrue(any("ENOB" in e for e in self.errs(char=flipped)))
        # An eligible row is omitted from the README table.
        lines = [l for l in self.status.splitlines() if not l.startswith("| Area |")]
        self.assertTrue(any("'Area'" in e and "missing" in e for e in self.errs(status="\n".join(lines))))


class LayoutAreaTests(unittest.TestCase):
    def test_layout_area_matches_and_drift_fails(self):
        status = C._status_table_text()
        area = json.loads(C.AREA_JSON.read_text(encoding="utf-8"))
        self.assertEqual(C.check_layout_area(status, area), [])
        # Negative control: area.json drifts from the README figure.
        area["areas_um2"]["block_total"] += 1000.0
        self.assertEqual(len(C.check_layout_area(status, area)), 1)
        # Negative control: README figure drifts / is removed.
        bad = status.replace("`adc_block` at 0.151827 mm", "`adc_block` at 0.150540 mm", 1)
        self.assertNotEqual(bad, status)
        self.assertEqual(len(C.check_layout_area(bad, area)), 1)
        gone = status.replace("`adc_block` at", "`adc_block` near", 1)
        self.assertEqual(len(C.check_layout_area(gone, area)), 1)

    def test_state_table_cells_are_short(self):
        rows = [l for l in C._status_table_text().splitlines()
                if l.startswith(("| Schematics", "| Layout", "| Verification suite"))]
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertLessEqual(len(r), 600, r[:30])


class HistoryGuardTests(unittest.TestCase):
    def _run_main(self, readme_text):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "README.md"
            tmp.write_text(readme_text, encoding="utf-8")
            old = C.README
            C.README = tmp
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    return C.main()
            finally:
                C.README = old

    def test_stale_phrase_in_readme_status_fails_but_archive_is_not_scanned(self):
        readme = C.README.read_text(encoding="utf-8")
        self.assertEqual(self._run_main(readme), 0)
        # Smoke-test-only is stale whenever adc_top.spice exists (it does).
        self.assertTrue((REPO / "design" / "adc-top" / "adc_top.spice").exists())
        bad = readme.replace("## Status\n\n", "## Status\n\nSmoke-test only.\n\n", 1)
        self.assertEqual(self._run_main(bad), 1)
        # The same phrase outside Status (as in the docs/ archive) is accepted.
        outside = readme + "\n## Elsewhere\n\nSmoke-test only.\n"
        self.assertEqual(self._run_main(outside), 0)

    def test_archive_matches_original_span(self):
        hist = (REPO / "docs" / "status-history-2026-10-08.md").read_text(encoding="utf-8")
        self.assertIn("Pre-tapeout. The analog core is drawn end to end", hist)
        self.assertIn("## Reference map", hist)


if __name__ == "__main__":
    unittest.main()
