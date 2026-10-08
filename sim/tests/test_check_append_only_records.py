#!/usr/bin/env python3
"""Negative control for sim/tools/check_append_only_records.py.

Builds a throwaway git repo, commits a record on `main`, branches, applies one
mutation, and asserts the check's verdict. A guard that cannot go red is not a
guard.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import check_append_only_records as chk  # noqa: E402

RECORD = "sim/exp/records/20260101-000000-abc.md"
OTHER_RECORD = "layout/adc-top/economy/records/r1.md"


class AppendOnlyRecordsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.write(RECORD, "original\n")
        self.write(OTHER_RECORD, "other\n")
        self.write("sim/exp/testbench/tb.spice", "* tb\n")
        self.commit("base")
        self.git("checkout", "-q", "-b", "pr")

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
        return chk.main(["--repo", str(self.repo), "--base", "main"])

    def test_added_record_passes(self):
        self.write("sim/exp/records/new.md", "new\n")
        self.commit("add")
        self.assertEqual(self.run_check(), 0)

    def test_non_record_change_passes(self):
        self.write("sim/exp/testbench/tb.spice", "* edited\n")
        self.commit("edit tb")
        self.assertEqual(self.run_check(), 0)

    def test_modified_record_fails(self):
        self.write(RECORD, "tampered\n")
        self.commit("edit")
        self.assertEqual(self.run_check(), 1)

    def test_deleted_record_fails(self):
        (self.repo / OTHER_RECORD).unlink()
        self.commit("rm")
        self.assertEqual(self.run_check(), 1)

    def test_renamed_record_fails(self):
        self.git("mv", RECORD, "sim/exp/records/renamed.md")
        self.commit("mv")
        self.assertEqual(self.run_check(), 1)

    def test_rename_out_of_records_fails(self):
        self.git("mv", RECORD, "sim/exp/elsewhere.md")
        self.commit("mv out")
        self.assertEqual(self.run_check(), 1)

    def test_allowlist_with_justification_exempts(self):
        self.write(RECORD, "tampered\n")
        self.write(chk.ALLOWLIST_REL, f"{RECORD}  # reviewed typo fix in #999\n")
        self.commit("edit + allow")
        self.assertEqual(self.run_check(), 0)

    def test_allowlist_without_justification_is_error(self):
        self.write(chk.ALLOWLIST_REL, f"{RECORD}\n")
        self.commit("bad allow")
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_merge_base_ignores_later_main_changes(self):
        self.git("checkout", "-q", "main")
        self.write(RECORD, "main moved on\n")
        self.commit("main edit")
        self.git("checkout", "-q", "pr")
        self.write("sim/exp/records/new.md", "new\n")
        self.commit("add")
        self.assertEqual(self.run_check(), 0)


if __name__ == "__main__":
    unittest.main()
