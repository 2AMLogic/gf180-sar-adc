#!/usr/bin/env python3
"""Unit tests for sim/dr0014-sampling/requal_delta.py (issue #1127).

    python3 -m unittest discover -s sim/tests -v

`requal_delta.py` pairs two DR-0014 records corner by corner and reports, per
measurement, the largest |new - old|. It used to carry its own table reader,
which stopped at the first non-table line after a corner; a record whose
ERROR verdict spans several lines of simulator output (the harness appends the
closing pipe after the simulator's last line) therefore lost every corner after
its first error row -- 12 of 27 on the committed FFT record
`20261123-071902-3703e3a`. The tool now reads through
`sim/tools/corner_table.py` (issue #1053). These tests pin that, the handling
of cells that are not numbers on both sides, the CLI diagnostic for malformed
input, and that the published re-qualification tables still reproduce.

No PDK and no ngspice required: the tool reads committed markdown.
"""

from __future__ import annotations

import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loadmod import load_module

SIM_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SIM_DIR / "dr0014-sampling" / "requal_delta.py"
rd = load_module("requal_delta", SCRIPT)

FFT_RECORDS = SIM_DIR / "adc-enob-fft" / "records"
MULTILINE = "20261123-071902-3703e3a"


def run(old: str, new: str, records: Path) -> str:
    """The command's stdout for one pair, read from `records` instead of the
    DR-0014 records directory the script hardcodes."""
    out = io.StringIO()
    with (
        mock.patch.object(rd, "RECORDS", records),
        mock.patch.object(sys, "argv", ["requal_delta.py", old, new]),
        contextlib.redirect_stdout(out),
    ):
        rd.main()
    return out.getvalue()


def record(rows: list[str]) -> str:
    """A minimal record with the same table shape report.render_record emits."""
    return "\n".join(
        [
            "# Record fake",
            "",
            "- **Result**:",
            "",
            "  | corner-id | m_lsb | pass/fail |",
            "  |---|---|---|",
            *rows,
            "",
        ]
    )


def metric_names(out: str) -> list[str]:
    """The metric of each data row, in the order the command printed them."""
    return [
        r.split(" | ")[0].removeprefix("| `").removesuffix("`")
        for r in out.splitlines()
        if r.startswith("| `")
    ]


class MultilineErrorRecordTests(unittest.TestCase):
    """The committed FFT record has two ERROR verdicts that carry eleven lines
    of ngspice banner inside the per-corner table, with twelve more corners
    after them."""

    LAST = "ff_125c_3.63v"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.records = Path(self._tmp.name)
        self.text = (FFT_RECORDS / f"{MULTILINE}.md").read_text(encoding="utf-8")
        self.write(MULTILINE, self.text)
        header = next(
            line
            for line in self.text.splitlines()
            if line.lstrip().startswith("| corner-id |")
        )
        self.measurements = [c.strip() for c in header.strip().strip("|").split("|")[1:]]

    @property
    def numeric(self) -> list[str]:
        return [m for m in self.measurements if m != "pass/fail"]

    def write(self, record_id: str, text: str) -> None:
        (self.records / f"{record_id}.md").write_text(text, encoding="utf-8")

    def test_the_record_really_has_corners_after_its_last_error_row(self):
        """Guards the fixture choice: if the ERROR rows were ever the last
        rows of this table, the tests below would pass without exercising the
        continuation at all."""
        lines = self.text.splitlines()
        errors = [i for i, line in enumerate(lines) if " | ERROR" in line]
        self.assertEqual(len(errors), 2)
        last = next(
            i for i, line in enumerate(lines) if line.startswith(f"  | `{self.LAST}` |")
        )
        self.assertGreater(last, errors[-1] + 10)
        self.assertEqual(len(re.findall(r"^  \| `(?:tt|ss|ff)_", "\n".join(lines), re.M)), 27)
        self.assertEqual(len(self.measurements), 76)

    def test_self_pairing_pairs_all_27_corners(self):
        out = run(MULTILINE, MULTILINE, self.records)
        self.assertIn("paired 27", out.splitlines()[0])
        self.assertEqual(metric_names(out), self.numeric)
        self.assertIn("0 of the paired measurements moved beyond tolerance.", out)

    def test_a_moved_measurement_at_the_last_fast_corner_is_reported(self):
        """`ff_125c_3.63v` is the 27th and last corner, after both ERROR rows
        and their banner lines. The old local reader ended the table at corner
        15, so a measurement that moved only here was silently absent."""
        old_line = next(
            line
            for line in self.text.splitlines()
            if line.startswith(f"  | `{self.LAST}` |")
        )
        self.assertTrue(old_line.endswith("| 4.10179 | PASS |"), old_line)
        self.write("moved", self.text.replace(old_line, old_line.replace("4.10179", "5.10179")))

        out = run(MULTILINE, "moved", self.records)
        self.assertIn("paired 27", out.splitlines()[0])
        self.assertEqual(metric_names(out), self.numeric)
        row = next(r for r in out.splitlines() if r.startswith("| `vref_droop_mv` |"))
        self.assertEqual(
            row,
            "| `vref_droop_mv` | `ff_125c_3.63v` | 4.10179 | 5.10179 | +1 | 0.051 | yes |",
        )
        self.assertIn("1 of the paired measurements moved beyond tolerance.", out)


class CellKindTests(unittest.TestCase):
    """The shared reader hands back floats for numbers and strings for
    everything else (`n/a`, a verdict, a multiline ERROR diagnostic)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.records = Path(self._tmp.name)

    def write(self, record_id: str, rows: list[str]) -> None:
        (self.records / f"{record_id}.md").write_text(record(rows), encoding="utf-8")

    def test_a_measurement_missing_on_either_side_is_a_move(self):
        """A value that vanished, or appeared, has no delta to compare against
        a tolerance; skipping the corner would hide it, so it is reported."""
        self.write("number", ["  | `a` | 1.5 | PASS |"])
        self.write("gap", ["  | `a` | n/a | PASS |"])
        for old, new, row in (
            ("number", "gap", "| `m_lsb` | `a` | 1.5 | n/a | n/a | exact | yes |"),
            ("gap", "number", "| `m_lsb` | `a` | n/a | 1.5 | n/a | exact | yes |"),
        ):
            with self.subTest(old=old, new=new):
                out = run(old, new, self.records)
                self.assertEqual(metric_names(out), ["m_lsb"])
                self.assertEqual(
                    [r for r in out.splitlines() if r.startswith("| `m_lsb` |")], [row]
                )
                self.assertIn("1 of the paired measurements moved beyond tolerance.", out)

    def test_a_measurement_missing_on_both_sides_is_not_a_move(self):
        self.write("old", ["  | `a` | n/a | PASS |"])
        self.write("new", ["  | `a` | n/a | PASS |"])
        out = run("old", "new", self.records)
        self.assertNotIn("| `m_lsb` |", out)
        self.assertIn("0 of the paired measurements moved beyond tolerance.", out)

    def test_a_multiline_error_verdict_is_compared_as_text_and_printed_on_one_row(self):
        """The row must not be broken across the verdict's embedded newlines:
        one measurement, one table row."""
        self.write("old", ["  | `a` | 1 | PASS |"])
        self.write(
            "new",
            [
                "  | `a` | 1 | ERROR — engine_killed: last output:",
                "******",
                "Batch mode",
                "Comments and warnings go to log-file: /x/ngspice.log |",
            ],
        )
        out = run("old", "new", self.records)
        rows = [r for r in out.splitlines() if r.startswith("| `")]
        self.assertEqual(
            rows,
            [
                "| `m_lsb` | `a` | 1 | 1 | +0 | 0.01 | no |",
                "| `pass/fail` | `a` | PASS | ERROR — engine_killed: last output:"
                "\\n******\\nBatch mode\\n"
                "Comments and warnings go to log-file: /x/ngspice.log | n/a | exact | yes |",
            ],
        )
        self.assertIn("1 of the paired measurements moved beyond tolerance.", out)


class MalformedInputTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.records = Path(self._tmp.name)
        self.write("good", record(["  | `a` | 1 | PASS |"]))

    def write(self, record_id: str, text: str) -> None:
        (self.records / f"{record_id}.md").write_text(text, encoding="utf-8")

    def diagnostic(self, old: str, new: str) -> str:
        with self.assertRaises(SystemExit) as caught:
            run(old, new, self.records)
        return caught.exception.code

    def test_a_row_that_disagrees_with_the_header_names_the_record_and_row(self):
        self.write("ragged", record(["  | `a` | 1 | PASS | extra |"]))
        self.assertRegex(
            self.diagnostic("ragged", "good"),
            r"^ragged: .*ragged\.md: row 7 has 4 cells, header has 3$",
        )

    def test_an_unterminated_error_verdict_is_reported_not_hung_on(self):
        self.write("open", record(["  | `a` | 1 | ERROR — killed: last output:"]))
        self.assertRegex(
            self.diagnostic("open", "good"),
            r"^open: .*unterminated ERROR verdict in row 7$",
        )

    def test_a_record_without_a_corner_table_is_reported(self):
        self.write("notes", "# Record fake\n\nno table here\n")
        self.assertRegex(
            self.diagnostic("notes", "good"), r"^notes: .*no per-corner Result table found$"
        )

    def test_a_missing_record_is_reported_without_a_traceback(self):
        self.assertRegex(self.diagnostic("nosuch", "good"), r"^nosuch: .*No such file or directory")


class PublishedRequalificationTests(unittest.TestCase):
    """The seven tables in the Appendix of `sim/requalification-595-dr0014-sampling.md`
    were generated by this command. That note is historical evidence and stays
    as written, so the command must keep reproducing them from the records."""

    NOTE = SIM_DIR / "requalification-595-dr0014-sampling.md"

    def test_every_published_pair_still_reproduces_its_appendix_table(self):
        note = self.NOTE.read_text(encoding="utf-8")
        pairs = re.findall(r"^### (\d+)\. `([0-9a-f-]+)` -> `([0-9a-f-]+)`$", note, re.M)
        self.assertEqual(len(pairs), 7)
        for number, old, new in pairs:
            with self.subTest(pair=number):
                appendix = re.search(
                    rf"^### {number}\. `{old}` -> `{new}`\n(.*?)(?=^### |\Z)",
                    note,
                    re.S | re.M,
                ).group(1)
                out = subprocess.check_output(
                    [sys.executable, "-I", SCRIPT, old, new], text=True
                )
                self.assertIn("paired 27", out.splitlines()[0])
                body = "".join(out.splitlines(True)[1:])
                self.assertEqual(body.strip("\n"), appendix.strip("\n"))


if __name__ == "__main__":
    unittest.main()
