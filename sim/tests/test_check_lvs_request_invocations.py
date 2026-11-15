#!/usr/bin/env python3
"""Negative control for sim/tools/check_lvs_request_invocations.py.

Builds a throwaway git repo with request documents and output reports and
asserts the check's verdict, including the exact issue #804 shape: a
candidate request document that documents the PRODUCTION invocation. A
guard that cannot go red is not a guard.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import check_lvs_request_invocations as chk  # noqa: E402


def request_doc(invocation: str | None) -> dict:
    comment = ["klt lvs request for a cell: the extracted layout netlist", ""]
    if invocation is not None:
        comment.append(f"    klt lvs {invocation} --format json")
    return {
        "_comment": comment,
        "layout": {"netlist": "cell.spice", "top": "CELL"},
        "reference": {"netlist": "cell.ref.spice", "top": "CELL"},
    }


class LvsRequestInvocationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.write(
            "layout/adc-top/adc_top.lvs.json",
            json.dumps(request_doc("layout/adc-top/adc_top.lvs.json")),
        )
        self.write(
            "layout/lvs/reports/20260101-000000-abc/match.lvs.json",
            json.dumps({"match": True, "mismatch_count": 0}),
        )
        self.commit("base")

    def git(self, *args):
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t",
             "-c", "commit.gpgsign=false", *args],
            check=True, capture_output=True,
        )

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def run_check(self):
        return chk.main(["--repo", str(self.repo)])

    def test_self_documenting_request_passes(self):
        self.assertEqual(self.run_check(), 0)

    def test_output_report_without_comment_is_skipped(self):
        # A `klt lvs --format json` output report shares the *.lvs.json
        # suffix but documents no invocation; it must not be flagged.
        self.write(
            "layout/lvs/reports/20260101-000000-abc/adc_top.lvs.json",
            json.dumps({"match": True, "mismatch_count": 0}),
        )
        self.commit("report")
        self.assertEqual(self.run_check(), 0)

    def test_documenting_another_file_fails(self):
        # Issue #804's exact shape: a candidate request document whose
        # _comment tells the reader to run the PRODUCTION request.
        rel = "layout/adc-top/candidates/acq-leg-1x/adc_top.lvs.json"
        self.write(
            rel,
            json.dumps(request_doc("layout/adc-top/adc_top.lvs.json")),
        )
        self.commit("candidate")
        self.assertEqual(self.run_check(), 1)

    def test_request_without_invocation_line_fails(self):
        # A writer that silently drops the line is the same regression.
        self.write(
            "layout/adc-top/adc_block.lvs.json",
            json.dumps(request_doc(None)),
        )
        self.commit("silent")
        self.assertEqual(self.run_check(), 1)

    def test_untracked_scratch_output_is_not_checked(self):
        # ls-files reads the index: an untracked scratch outdir cannot fail
        # a local run the way a stale sibling worktree would.
        self.write(
            "layout/adc-top/candidates/acq-leg-9x/adc_top.lvs.json",
            json.dumps(request_doc("layout/adc-top/adc_top.lvs.json")),
        )
        self.assertEqual(self.run_check(), 0)


if __name__ == "__main__":
    unittest.main()
