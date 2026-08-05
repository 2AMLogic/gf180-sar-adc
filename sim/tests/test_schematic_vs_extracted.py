#!/usr/bin/env python3
"""Unit tests for sim/tools/schematic_vs_extracted.py (issue #89 Scope
item 3). No PDK and no ngspice required — the tool reads committed markdown.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR / "tools"))

import schematic_vs_extracted as svx  # noqa: E402

REPO_ROOT = SIM_DIR.parent


def record_text(rows: list[str]) -> str:
    """A minimal record with the same table shape report.render_record emits."""
    return "\n".join(
        [
            "# Record fake",
            "",
            "- **Record ID**: fake",
            "- **Result**:",
            "",
            "  | corner-id | inl_t1_lsb | inl_t2_lsb | dnl_t1_t2_lsb | gain_err_lsb | pass/fail |",
            "  |---|---|---|---|---|---|",
        ]
        + rows
        + [
            "",
            "  Spread across the grid:",
            "",
            "  | measurement | min | max | mean | spread % | limits |",
            "  |---|---|---|---|---|---|",
            "  | `inl_t1_lsb` | 0 (`tt_27c_3.30v`) | 0 (`tt_27c_3.30v`) | 0 | 0 | — |",
        ]
    )


class ParseTests(unittest.TestCase):
    def _write(self, name: str, rows: list[str]) -> Path:
        path = Path(self.tmp) / f"{name}.md"
        path.write_text(record_text(rows), encoding="utf-8")
        return path

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def test_parses_only_the_per_corner_table_not_the_spread_table(self):
        """The spread table that follows has a different first column and must
        not be swept into the per-corner rows — otherwise every measurement's
        'worst' would be computed over a mix of corners and summary rows."""
        path = self._write(
            "r", ["  | `tt_27c_3.30v` | 0 | -0.04 | -0.04 | -1.99 | PASS |"]
        )
        rows = svx.parse_record(path)
        self.assertEqual(list(rows), ["tt_27c_3.30v"])
        self.assertAlmostEqual(rows["tt_27c_3.30v"]["gain_err_lsb"], -1.99)
        self.assertEqual(rows["tt_27c_3.30v"]["pass/fail"], "PASS")

    def test_a_row_whose_width_disagrees_with_the_header_is_an_error(self):
        path = self._write("r", ["  | `tt_27c_3.30v` | 0 | -0.04 | PASS |"])
        with self.assertRaises(ValueError):
            svx.parse_record(path)

    def test_a_record_with_no_per_corner_table_is_an_error(self):
        path = Path(self.tmp) / "empty.md"
        path.write_text("# Record fake\n\nno table here\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            svx.parse_record(path)

    def test_derived_worst_columns_rank_on_magnitude_and_keep_the_sign(self):
        path = self._write(
            "r", ["  | `tt_27c_3.30v` | 0.2 | -0.5 | -0.04 | -1.99 | PASS |"]
        )
        rows = svx.parse_record(path)
        svx.add_derived(rows)
        self.assertEqual(rows["tt_27c_3.30v"]["inl_worst_lsb"], -0.5)
        self.assertEqual(rows["tt_27c_3.30v"]["dnl_worst_lsb"], -0.04)


class DeltaTests(unittest.TestCase):
    def setUp(self):
        self.schematic = {
            "tt_27c_3.30v": {"gain_err_lsb": -2.0, "pass/fail": "PASS"},
            "ss_125c_2.97v": {"gain_err_lsb": -2.5, "pass/fail": "PASS"},
        }
        self.extracted = {
            "tt_27c_3.30v": {"gain_err_lsb": -3.0, "pass/fail": "PASS"},
            "ss_125c_2.97v": {"gain_err_lsb": -2.4, "pass/fail": "FAIL — x"},
            "ff_-40c_3.63v": {"gain_err_lsb": -9.0, "pass/fail": "PASS"},
        }

    def test_only_shared_corners_are_compared(self):
        """The extracted run may cover corners the schematic baseline never
        ran (here the `cdac` capacitor corners). Including them would make
        the 'worst' columns incomparable — the delta must be taken over the
        intersection only."""
        table, shared = svx.build_table(self.schematic, self.extracted)
        self.assertEqual(shared, ["ss_125c_2.97v", "tt_27c_3.30v"])
        self.assertNotIn("ff_-40c_3.63v", "\n".join(table))
        row = [r for r in table if "gain_err_lsb" in r][0]
        # worst = largest magnitude over the shared corners
        self.assertIn("-2.5 (`ss_125c_2.97v`)", row)
        self.assertIn("-3 (`tt_27c_3.30v`)", row)

    def test_max_per_corner_delta_is_reported_separately_from_worst_vs_worst(self):
        """worst-vs-worst is -3.0 - (-2.5) = -0.5, but the largest single-corner
        move is |-3.0 - (-2.0)| = 1.0 at tt. Reporting only the former would
        understate the layout-induced change by 2x."""
        table, _ = svx.build_table(self.schematic, self.extracted)
        row = [r for r in table if "gain_err_lsb" in r][0]
        self.assertIn("-0.5", row)
        self.assertTrue(row.rstrip().endswith("| 1 |"), row)

    def test_no_shared_corner_is_a_hard_error(self):
        with self.assertRaises(SystemExit):
            svx.build_table(self.schematic, {"xx_0c_1.00v": {"gain_err_lsb": 1.0}})

    def test_verdicts_are_reduced_to_the_leading_token(self):
        v = svx.verdicts(self.extracted, ["ss_125c_2.97v", "tt_27c_3.30v"])
        self.assertEqual(v, {"ss_125c_2.97v": "FAIL", "tt_27c_3.30v": "PASS"})


class CommittedRecordTests(unittest.TestCase):
    """Runs against the real committed records, so a change to the record
    format that breaks this tool is caught on the headless CI path rather
    than the next time someone builds a delta summary."""

    EXPERIMENT = REPO_ROOT / "sim" / "adc-inl-dnl" / "records"

    def test_every_committed_inl_dnl_record_parses(self):
        """Every record under `sim/adc-inl-dnl/records/` must parse, and the
        derived `inl_worst_lsb`/`dnl_worst_lsb` columns must appear wherever
        their source `inl_t*_lsb`/`dnl_t*_t*_lsb` columns do. Not every
        record in this experiment directory carries the full 18-transition
        sweep those derive from -- e.g. `20260805-163000-e8017f2.md` (issue
        #89 Scope items 3/8) is a narrower `gain_err_lsb`-only endpoint
        measurement, per its own "Subset-corner justification" -- so this
        only requires the derived column where the source columns exist,
        rather than assuming every record is a full INL/DNL sweep."""
        records = sorted(self.EXPERIMENT.glob("*.md"))
        self.assertGreaterEqual(len(records), 2, "expected committed records")
        for path in records:
            with self.subTest(record=path.name):
                rows = svx.parse_record(path)
                self.assertTrue(rows)
                svx.add_derived(rows)
                for corner, row in rows.items():
                    for derived, (pattern, _) in svx.DERIVED.items():
                        has_source = any(pattern.match(k) for k in row)
                        if has_source:
                            self.assertIn(derived, row, corner)

    def test_cli_on_two_committed_records(self):
        ids = sorted(p.stem for p in self.EXPERIMENT.glob("*.md"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = svx.main(
                [
                    "adc-inl-dnl",
                    "--schematic",
                    ids[0],
                    "--extracted",
                    ids[1],
                    "--only",
                    "gain_err_lsb",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("| `gain_err_lsb` |", buf.getvalue())

    def test_unknown_record_id_exits_nonzero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = svx.main(
                ["adc-inl-dnl", "--schematic", "nope", "--extracted", "nope"]
            )
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
