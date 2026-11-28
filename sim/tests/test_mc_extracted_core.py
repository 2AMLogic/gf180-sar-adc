#!/usr/bin/env python3
"""Null-control verdict of `layout/adc-top/parasitics/mc_extracted_core.py`,
including empty controls -- issue #1029. No PDK, no ngspice, no `klt`:

    python3 -m unittest discover -s sim/tests -t sim/tests -v

The null control is the only thing standing between a collapsed Monte Carlo
(every draw identical, sigma ~ 0, a plausible mean) and a record, so its
verdict is driven here through `main()` itself, with PDK discovery, the PDK
statistical audit and the simulation stubbed. The runner parses synthetic
ngspice logs and computes both populations' statistics from the parsed draws.

Exit code, `--json` verdict and the printed verdict are asserted together:
the exit code is what whoever re-runs the record reads, the JSON is what
whoever reads the record gets, the printed line is what the log shows.

Before the fix the verdict was the on/off sigma ratio alone, and a frozen
control (sigma 0) made that ratio unbounded for ANY mismatch-on sigma: two
frozen populations printed PASS and exited 0.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
PARASITICS_DIR = REPO / "layout" / "adc-top" / "parasitics"
sys.path.insert(0, str(PARASITICS_DIR))

import mc_extracted_core as MC  # noqa: E402

#: The committed record this runner produced
#: (`records/20260805-extracted-core-mc.md`): 120 distinct mismatch-on draws
#: against a 12-draw frozen control.
RECORD_JSON = (PARASITICS_DIR / "reports" / "20260805-extracted-core-mc"
               / "mc_extracted_core.json")

#: The record's mismatch-on mean and its null-control draw. A frozen
#: population's two-pass sigma is exactly 0 only when the common draw averages
#: back to itself: twelve copies of the control draw do, forty copies of the
#: mismatch-on mean do NOT (`sum/n` lands one ulp away), so the latter carries
#: a sigma of 5.6e-17. A rule asking only `sigma > 0` would read that frozen
#: population as "varying over a frozen control" -- the same false pass, one
#: floating-point ulp narrower.
RECORDED_ON_MEAN = 0.48655595
RECORDED_OFF_DRAW = 0.4865934

#: Two LSB-scale draws an exact 1/256 LSB apart, so their population sigma is
#: exact: 0.00390625 LSB.
VARYING = [0.484375, 0.4921875] * 20


class NullControlVerdict(unittest.TestCase):
    def run_main(self, on_draws, off_draws, *extra_args, control_samples=None):
        """Return the exit code, stdout, stderr and JSON for two synthetic logs."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        json_path = Path(tmp.name) / "mc.json"
        if control_samples is None:
            control_samples = len(off_draws)
        logs = ["\n".join(f"esamp = {v}" for v in draws)
                for draws in (on_draws, off_draws)]

        pdk = mock.Mock()
        pdk.variant = "gf180mcuD"
        pdk.provenance.return_value = {"stub": True}
        audit = {
            "mos_local_mismatch_present": True,
            "mos_finding_holds": True,
            "cap_local_mismatch_present": False,
            "cap_finding_holds": True,
        }
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(MC.PDK, "pdk_available", return_value=True), \
                mock.patch.object(MC.PDK, "find_pdk", return_value=pdk), \
                mock.patch.object(MC, "audit_cap_finding", return_value=audit), \
                mock.patch.object(MC, "compose_deck", return_value=""), \
                mock.patch.object(MC.G, "run_ngspice", side_effect=logs), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = MC.main(["--samples", str(len(on_draws)),
                            "--control-samples", str(control_samples),
                            "--json", str(json_path), *extra_args])

        result = json.loads(json_path.read_text())
        self.assertEqual([(p["mismatch"], p["n_requested"], p["n_parsed"])
                          for p in result["populations"]],
                         [(True, len(on_draws), len(on_draws)),
                          (False, control_samples, len(off_draws))])
        return code, out.getvalue(), err.getvalue(), result

    def test_empty_control_fails(self):
        for requested in (0, 6):
            with self.subTest(control_samples=requested):
                code, out, err, res = self.run_main(
                    VARYING, [], control_samples=requested
                )
                self.assertEqual(res["populations_complete"], requested == 0)
                self.assertGreater(res["populations"][0]["sigma_lsb"], 0.0)
                self.assertTrue(math.isnan(res["populations"][1]["sigma_lsb"]))
                self.assertEqual(code, 1)
                self.assertFalse(res["null_control_passed"])
                self.assertTrue(math.isnan(res["sigma_ratio_on_off"]))
                self.assertNotIn("PASS", out)
                self.assertIn("FAIL: no null-control samples were parsed", err)

    def test_single_control_draw_fails(self):
        for requested in (1, 6):
            with self.subTest(control_samples=requested):
                code, out, err, res = self.run_main(
                    VARYING, [RECORDED_OFF_DRAW], control_samples=requested
                )
                self.assertEqual(res["populations_complete"], requested == 1)
                self.assertFalse(res["null_control_passed"])
                self.assertTrue(math.isnan(res["sigma_ratio_on_off"]))
                self.assertEqual(code, 1)
                self.assertNotIn("PASS", out)
                self.assertIn("FAIL: only one null-control sample was parsed", err)
                self.assertIn("at least two", err)

    def test_two_identical_control_draws_can_pass(self):
        code, out, err, res = self.run_main(VARYING, [RECORDED_OFF_DRAW] * 2)
        self.assertTrue(res["populations_complete"])
        self.assertTrue(res["null_control_passed"])
        self.assertEqual(res["sigma_ratio_on_off"], float("inf"))
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)
        self.assertEqual(err, "")

    def test_two_frozen_populations_fail(self):
        """The reported failure: both sigmas exactly 0, the ratio reported as
        unbounded, PASS, exit 0."""
        code, out, err, res = self.run_main([0.5] * 40, [0.5] * 6)
        self.assertEqual([p["sigma_lsb"] for p in res["populations"]], [0.0, 0.0])
        self.assertEqual(code, 1)
        self.assertTrue(res["populations_complete"])
        self.assertFalse(res["null_control_passed"])
        self.assertTrue(
            math.isnan(res["sigma_ratio_on_off"]),
            "zero spread over a frozen control is 0/0 -- undefined, and must "
            "not be reported with the unbounded ratio a varying population "
            "earns",
        )
        self.assertNotIn("PASS", out)
        self.assertIn("FAIL: the mismatch-on population is not varying", err)

    def test_frozen_mismatch_on_population_with_rounding_residue_fails(self):
        """A frozen mismatch-on population whose common draw does not average
        back to itself still fails, against a control whose draw does."""
        code, out, err, res = self.run_main([RECORDED_ON_MEAN] * 40,
                                            [RECORDED_OFF_DRAW] * 12)
        self.assertEqual([p["sigma_lsb"] for p in res["populations"]], [0.0, 0.0])
        self.assertEqual(code, 1)
        self.assertFalse(res["null_control_passed"])
        self.assertTrue(math.isnan(res["sigma_ratio_on_off"]))
        self.assertNotIn("PASS", out)
        self.assertIn("FAIL: the mismatch-on population is not varying", err)

    def test_varying_population_against_a_frozen_control_passes(self):
        """The control doing its job: spread over a frozen draw is an
        unbounded ratio, and that alone is allowed to be unbounded."""
        code, out, err, res = self.run_main(VARYING, [RECORDED_OFF_DRAW] * 12)
        self.assertEqual([p["sigma_lsb"] for p in res["populations"]],
                         [0.00390625, 0.0])
        self.assertEqual(code, 0)
        self.assertTrue(res["null_control_passed"])
        self.assertEqual(res["sigma_ratio_on_off"], float("inf"))
        self.assertIn("PASS", out)
        self.assertEqual(err, "")

    def test_frozen_population_against_a_varying_control_fails(self):
        """No spread over positive control spread is a ratio of 0."""
        code, out, err, res = self.run_main([0.5] * 40, [0.0] * 3 + [0.0625] * 3)
        self.assertEqual(res["sigma_ratio_on_off"], 0.0)
        self.assertEqual(code, 1)
        self.assertFalse(res["null_control_passed"])
        self.assertNotIn("PASS", out)

    def test_ratio_below_the_configured_threshold_fails(self):
        """Positive spread in BOTH populations: 1.5625 LSB over 0.03125 LSB
        is exactly 50x, under the default threshold and under a configured
        one just above it."""
        on = [0.0] * 20 + [3.125] * 20
        off = [0.0] * 3 + [0.0625] * 3
        for extra_args, threshold in (((), 100.0),
                                      (("--min-sigma-ratio", "50.5"), 50.5)):
            with self.subTest(min_sigma_ratio=threshold):
                code, out, err, res = self.run_main(on, off, *extra_args)
                self.assertEqual([p["sigma_lsb"] for p in res["populations"]],
                                 [1.5625, 0.03125])
                self.assertEqual(res["sigma_ratio_on_off"], 50.0)
                self.assertEqual(code, 1)
                self.assertFalse(res["null_control_passed"])
                self.assertNotIn("PASS", out)
                self.assertIn("FAIL", err)

    def test_ratio_exactly_at_the_configured_threshold_passes(self):
        """The rule is "at least this factor": a ratio equal to the threshold
        passes, at the default and at a configured one."""
        off = [0.0] * 3 + [0.0625] * 3
        cases = (((), 100.0, 6.25),
                 (("--min-sigma-ratio", "50"), 50.0, 3.125))
        for extra_args, threshold, on_high in cases:
            with self.subTest(min_sigma_ratio=threshold):
                on = [0.0] * 20 + [on_high] * 20
                code, out, err, res = self.run_main(on, off, *extra_args)
                self.assertEqual([p["sigma_lsb"] for p in res["populations"]],
                                 [on_high / 2, 0.03125])
                self.assertEqual(res["sigma_ratio_on_off"], threshold)
                self.assertEqual(code, 0)
                self.assertTrue(res["null_control_passed"])
                self.assertIn("PASS", out)
                self.assertEqual(err, "")

    def test_recorded_populations_still_pass(self):
        """The committed record's own populations -- 120 distinct
        mismatch-on draws against a 12-draw frozen control -- keep the
        verdict the record states, under the corrected rule."""
        recorded = json.loads(RECORD_JSON.read_text())
        on, off = (pop["terr_lsb"] for pop in recorded["populations"])
        self.assertEqual((len(set(on)), len(set(off))), (120, 1))
        code, out, err, res = self.run_main(on, off)
        self.assertEqual([p["sigma_lsb"] for p in res["populations"]],
                         [recorded["populations"][0]["sigma_lsb"], 0.0])
        self.assertEqual((res["null_control_passed"], res["sigma_ratio_on_off"]),
                         (recorded["null_control_passed"],
                          recorded["sigma_ratio_on_off"]))
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)


class PopulationStats(unittest.TestCase):
    """`sigma > 0` is the verdict rule's whole definition of "genuinely
    varying", so a frozen population must carry no rounding residue."""

    def test_bit_identical_draws_have_exactly_zero_spread(self):
        """Whether or not the common draw averages back to itself."""
        for value, n in ((0.5, 40), (RECORDED_OFF_DRAW, 12), (0.1, 6),
                         (RECORDED_ON_MEAN, 40)):
            with self.subTest(value=value, n=n):
                self.assertEqual(MC.population_stats([value] * n)[1], 0.0)

    def test_distinct_draws_keep_positive_spread(self):
        for draws, sigma in (([0.0] * 3 + [0.0625] * 3, 0.03125),
                             (VARYING, 0.00390625)):
            with self.subTest(sigma=sigma):
                self.assertEqual(MC.population_stats(draws)[1], sigma)


if __name__ == "__main__":
    unittest.main()
