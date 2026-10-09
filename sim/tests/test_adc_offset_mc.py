#!/usr/bin/env python3
"""Tests for sim/adc-offset-mc: request generation is current, the estimator
reads a staircase correctly, and every qualification check has a negative control.

No ngspice, no klt, no network:

    python3 -m unittest discover -s sim/tests -p 'test_adc_offset_mc.py' -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TB = Path(__file__).resolve().parents[1] / "adc-offset-mc" / "testbench"
sys.path.insert(0, str(TB))

import analyze_pilot as A  # noqa: E402
import gen_pilot as G  # noqa: E402

N = len(G.diffs())


def corner(idx, flip_at, seed=None, status="pass", levels=None):
    """A klt corner dict whose staircase flips 1->0 between steps flip_at and flip_at+1."""
    if levels is None:
        levels = [3.3 if k <= flip_at else 0.0 for k in range(N)]
    return {
        "corner_id": f"tt/novdd/27C/mc{idx}", "status": status, "diagnostics": [],
        "monte_carlo": {"sample_index": idx, "seed": 1000 + idx if seed is None else seed},
        "measurements": [{"name": f"d{k:02d}", "value": v} for k, v in enumerate(levels)],
    }


def dump(tmp, name, corners):
    p = Path(tmp) / name
    p.write_text(json.dumps({"status": "pass", "corners": corners}))
    return p


class Generated(unittest.TestCase):
    def test_committed_files_match_generator(self):
        for name, text in G.outputs().items():
            self.assertEqual((TB / name).read_text(), text, f"{name} is stale: rerun gen_pilot.py")

    def test_requests_use_only_native_fields(self):
        req = json.loads((TB / "request_pilot.json").read_text())
        self.assertEqual(set(req["monte_carlo"]), {"n", "seed", "vary"})
        self.assertEqual(req["monte_carlo"]["vary"], "mismatch")
        self.assertEqual(len(req["measurements"]), N)

    def test_null_netlist_differs_only_in_mismatch_switch(self):
        a = (TB / G.ENABLED_NETLIST).read_text().replace("sw_stat_mismatch=1", "sw_stat_mismatch=0")
        b = (TB / G.NULL_NETLIST).read_text()
        self.assertEqual(a.split("\n", 1)[1].replace("(ON: per-instance MOS mismatch)", "(OFF: null control)"),
                         b.split("\n", 1)[1])

    def test_extracted_netlist_provenance_pinned(self):
        import hashlib
        p = (TB / G.EXTRACTED).resolve()
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),
                         "91c044dc66ce3e2fc3913abe634349e69a5838226a4f2691de81ae7ab5fcbaf0")


class Estimator(unittest.TestCase):
    def test_midpoint_between_last_one_and_first_zero(self):
        s = A.sample_from_corner(corner(0, 10))
        self.assertAlmostEqual(s["vos_v"], 0.5 * (G.diffs()[10] + G.diffs()[11]))

    def test_failed_draws_are_reported_not_dropped(self):
        self.assertIn("censored", A.sample_from_corner(corner(0, N))["failure"])
        self.assertIn("censored", A.sample_from_corner(corner(0, -1))["failure"])
        lv = [3.3] * N
        lv[5] = 0.0
        self.assertIn("non-monotone", A.sample_from_corner(corner(0, 0, levels=lv))["failure"])
        lv = [3.3] * 5 + [1.6] + [0.0] * (N - 6)
        self.assertIn("indeterminate", A.sample_from_corner(corner(0, 0, levels=lv))["failure"])
        self.assertIn("klt corner status", A.sample_from_corner(corner(0, 10, status="error"))["failure"])


class Checks(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)

    def run_eval(self, en, nu, rp=None, n=8, nn=4):
        f = lambda name, c: A.load(dump(self.t.name, name, c))
        return A.evaluate(f("e.json", en), f("n.json", nu), f("r.json", rp) if rp else None, n, nn)

    def good(self):
        flips = [8, 10, 12, 9, 14, 11, 7, 13]
        en = [corner(i, flips[i]) for i in range(8)]
        nu = [corner(i, 12, seed=500 + i) for i in range(4)]
        return en, nu

    def failed(self, res):
        return {c["check"] for c in res["checks"] if not c["pass"]}

    def test_good_population_passes(self):
        en, nu = self.good()
        res = self.run_eval(en, nu, en)
        self.assertTrue(res["all_checks_pass"], self.failed(res))

    def test_duplicated_draws_fail(self):
        en, nu = self.good()
        for c in en:
            c["monte_carlo"]["seed"] = 7
        res = self.run_eval(en, nu)
        self.assertTrue(any("seeds all distinct" in c for c in self.failed(res)))

    def test_no_variation_fails(self):
        en, nu = self.good()
        en = [corner(i, 10) for i in range(8)]
        res = self.run_eval(en, nu)
        self.assertTrue(any("spread above resolution" in c for c in self.failed(res)))

    def test_null_with_spread_fails(self):
        en, nu = self.good()
        nu = [corner(i, 8 + 2 * i, seed=500 + i) for i in range(4)]
        res = self.run_eval(en, nu)
        self.assertTrue(any("null: spread" in c for c in self.failed(res)))

    def test_repeat_mismatch_fails(self):
        en, nu = self.good()
        rp = [corner(c["monte_carlo"]["sample_index"], 3 + i, seed=c["monte_carlo"]["seed"]) for i, c in enumerate(en)]
        res = self.run_eval(en, nu, rp)
        self.assertTrue(any("reproduce" in c for c in self.failed(res)))

    def test_errored_submission_is_not_a_pilot(self):
        en, nu = self.good()
        en = [corner(i, 10, status="error") for i in range(8)]
        res = self.run_eval(en, nu)
        self.assertFalse(res["all_checks_pass"])

    def test_missing_draws_fail(self):
        en, nu = self.good()
        res = self.run_eval(en[:5], nu)
        self.assertTrue(any("all expected draws" in c for c in self.failed(res)))


if __name__ == "__main__":
    unittest.main()
