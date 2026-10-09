#!/usr/bin/env python3
"""Fixture-tree test for sim/tools/evidence_footprint.py."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import evidence_footprint as ef  # noqa: E402


class EvidenceFootprintTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        self.add("sim/a/corners/r1/tt.log", 1000)
        self.add("sim/a/corners/r1/ss.log", 500)
        self.add("sim/a/corners/r2/tt.log", 200)
        self.add("sim/a/records/r1.md", 30)
        self.add("sim/a/README.md", 7)
        self.add("sim/b/corners/r9/tt.log", 40)
        self.add("sim/README.md", 99999)  # not an experiment: ignored
        (self.repo / "sim/a/untracked.log").write_bytes(b"x" * 5000)  # not tracked
        subprocess.run(["git", "-C", str(self.repo), "add", "-A", "sim/a/corners",
                        "sim/a/records", "sim/a/README.md", "sim/b", "sim/README.md"],
                       check=True)

    def add(self, rel, n):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * n)

    def test_per_experiment_and_record(self):
        exp, rec = ef.measure(self.repo)
        self.assertEqual(exp, {"a": 1737, "b": 40})
        self.assertEqual(rec[("a", "r1")], 1530)
        self.assertEqual(rec[("a", "r2")], 200)
        self.assertEqual(rec[("a", ef.OTHER)], 7)
        self.assertEqual(rec[("b", "r9")], 40)

    def run_cli(self, budget, *extra):
        (self.repo / "sim/tools").mkdir(parents=True, exist_ok=True)
        (self.repo / ef.BUDGET_REL).write_text(json.dumps(budget))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = ef.main(["--repo", str(self.repo), *extra])
        return rc, out.getvalue(), err.getvalue()

    def test_check_within_budget(self):
        rc, out, _ = self.run_cli({"total_bytes": 5000, "default_experiment_bytes": 5000},
                                  "--check")
        self.assertEqual(rc, 0)
        self.assertIn("within budget", out)

    def test_check_over_budget_is_report_only(self):
        budget = {"total_bytes": 5000, "default_experiment_bytes": 1000}
        rc, _, err = self.run_cli(budget, "--check")
        self.assertEqual(rc, 0)
        self.assertIn("a 1737 > budget 1000", err)
        rc, _, _ = self.run_cli(budget, "--check", "--strict")
        self.assertEqual(rc, 1)

    def test_per_experiment_override_and_total(self):
        rc, _, err = self.run_cli(
            {"total_bytes": 1000, "default_experiment_bytes": 10,
             "experiments": {"a": 2000, "b": 100}}, "--check", "--strict")
        self.assertEqual(rc, 1)
        self.assertIn("TOTAL 1777 > budget 1000", err)
        self.assertNotIn("a 1737", err)

    def test_records_listing(self):
        _, out, _ = self.run_cli({"total_bytes": 1}, "--records")
        self.assertIn("r1", out)
        self.assertIn("TOTAL", out)


if __name__ == "__main__":
    unittest.main()
