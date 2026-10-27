#!/usr/bin/env python3
"""Tests for the 5.digital evidence behind issue #642.

1. The committed `klt functional-verification` envelope (and the mutation run
   beside it) shows no failed test and no surviving mutant.
2. The multi-corner STA verdict rule: a negative-slack corner, or one that is
   not `constrained`, fails -- it is never dropped.
3. The manifest cites both parts as `5.digital`.

No PDK, no `klt`, no simulator needed:

    python3 -m unittest sim.tests.test_sar_ctrl_5digital -v
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]


def _cited_fv_envelope() -> Path:
    manifest = json.loads((REPO / "signoff" / "gf180-sar-adc.manifest.json").read_text())
    (fv,) = [p["file"] for p in manifest["evidence"]["5.digital"] if "fv_response" in p["file"]]
    return REPO / fv


class CommittedFunctionalEnvelope(unittest.TestCase):
    def test_no_failed_tests(self):
        env = json.loads(_cited_fv_envelope().read_text())
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["failed_count"], 0)
        self.assertEqual(env["skipped_count"], 0)
        self.assertGreater(env["passed_count"], 0)
        self.assertEqual([t["name"] for t in env["tests"] if t["status"] != "passed"], [])

    def test_every_mutant_killed(self):
        mut = json.loads((_cited_fv_envelope().parent / "mutation_response.json").read_text())
        mt = mut["mutation_testing"]
        self.assertEqual(mt["rejected_count"], 0)
        self.assertEqual(mt["survived_count"], 0)
        self.assertEqual(mt["killed_count"], mt["valid_count"])


class CornerVerdict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mod = load_module("sta_postroute_5dig", REPO / "design" / "sar-logic" / "flow" / "sta_sar_ctrl_postroute.py")
        cls.ok = staticmethod(mod._corner_ok)

    def entry(self, **kw):
        base = {"timing_status": "constrained", "worst_slack_ns": 1.0, "worst_hold_slack_ns": 0.1}
        return {**base, **kw}

    def test_passing_corner(self):
        self.assertTrue(self.ok(self.entry()))

    def test_negative_setup_fails(self):
        self.assertFalse(self.ok(self.entry(worst_slack_ns=-0.01)))

    def test_negative_hold_fails(self):
        self.assertFalse(self.ok(self.entry(worst_hold_slack_ns=-0.01)))

    def test_unconstrained_fails(self):
        self.assertFalse(self.ok(self.entry(timing_status="unconstrained")))
        self.assertFalse(self.ok({"worst_slack_ns": 1.0, "worst_hold_slack_ns": 0.1}))


class CommittedStaCitation(unittest.TestCase):
    def test_all_five_corners_pass_the_rule(self):
        manifest = json.loads((REPO / "signoff" / "gf180-sar-adc.manifest.json").read_text())
        (sta,) = [p["file"] for p in manifest["evidence"]["5.digital"] if "sta_response" in p["file"]]
        resp = json.loads((REPO / sta).read_text())
        self.assertEqual(len(resp["corners"]), 5)
        self.assertEqual(resp["geometry_source"], "routed")
        self.assertIsNone(resp["spef_path"])
        for c in resp["corners"]:
            self.assertEqual(c["timing_status"], "constrained", c["corner"])
            self.assertGreaterEqual(c["worst_slack_ns"], 0, c["corner"])
            self.assertGreaterEqual(c["worst_hold_slack_ns"], 0, c["corner"])


if __name__ == "__main__":
    unittest.main()
