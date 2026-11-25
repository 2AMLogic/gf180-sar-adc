#!/usr/bin/env python3
"""Tests for the offset-MC screening requests, descending-staircase estimator and
append-only record writer (issue #454). Stdlib only; no ngspice, klt or network:

    python3 -m unittest discover -s sim/tests -p 'test_adc_offset_mc_record.py' -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TB = Path(__file__).resolve().parents[1] / "adc-offset-mc" / "testbench"
sys.path.insert(0, str(TB))

import analyze_pilot as A  # noqa: E402
import gen_pilot as G  # noqa: E402
import record_writer as W  # noqa: E402
import sample_size as S  # noqa: E402

CORNERS = TB.parent / "corners" / "20261009-042900-2a4b3fac"
FIXTURE = TB / "fixtures" / "dryrun-pilot-20261009-042900-2a4b3fac"
NU = G.SCR_N_UP


def screen_corner(idx, up_at, down_at=None, seed=None, status="pass", vdd=3.3):
    """Screening-layout klt corner. Up staircase flips 1->0 after step `up_at`; the
    descending staircase (read top to bottom) flips 0->1 so that the down threshold
    sits after step `down_at` of the ascending index (default: same as up)."""
    down_at = up_at if down_at is None else down_at
    up = [vdd if k <= up_at else 0.0 for k in range(NU)]
    dn_asc = [vdd if k <= down_at else 0.0 for k in range(NU)]   # ascending-order bits
    dn = dn_asc[::-1]                                              # read order: top level first
    meas = [{"name": f"u{k:02d}", "value": v} for k, v in enumerate(up)]
    meas += [{"name": f"r{k:02d}", "value": v} for k, v in enumerate(dn)]
    return {"corner_id": f"tt/v/27C/mc{idx}", "status": status, "diagnostics": [], "supply_v": {"Vdd": vdd},
            "monte_carlo": {"sample_index": idx, "seed": 5000 + idx if seed is None else seed,
                            "mismatch_seed": 9000 + idx},
            "measurements": meas}


def samples_from(values_mv, mismatch=True):
    out = []
    for i, v in enumerate(values_mv):
        s = {"sample_index": i, "seed": 100 + i, "mismatch_seed": 200 + i, "corner_id": f"c{i}",
             "vos_v": None if v is None else v * 1e-3, "failure": None if v is not None else "censored: no decision flip inside the input range"}
        out.append(s)
    return out


def population(label, values_mv, seeds=None, mismatch=True, n_req=None):
    smp = samples_from(values_mv)
    if seeds:
        for s, sd in zip(smp, seeds):
            s["seed"] = sd
    n_req = len(smp) if n_req is None else n_req
    return {"label": label, "mismatch_on": mismatch,
            "provenance": {"report_path": "x", "report_sha256": "0" * 64, "report_status": "pass", "netlist": {"path": "n"},
                           "netlist_sha256": "a" * 64, "netlist_closure": [], "models_lib_sha256": "b" * 64,
                           "klt_version": "0.7.0", "klayout_version": "0.30", "pdk": {}, "engine": "ngspice",
                           "engine_version": "46", "backend": "local", "job_id": None, "runner_klt_version": None,
                           "runner_compatibility": None, "elapsed_seconds": None,
                           "monte_carlo": {"n": n_req, "seed": 1, "vary": "mismatch"}, "corner_grid": [["tt", "{}", 27]]},
            "summary": W.population_summary(smp, mismatch, n_req)}


class ScreeningRequests(unittest.TestCase):
    def test_committed_screening_files_current(self):
        for name, text in G.screening_outputs().items():
            self.assertEqual((TB / name).read_text(), text, f"{name} is stale: rerun gen_pilot.py")

    def test_check_flag_passes_on_committed_tree(self):
        self.assertEqual(G.main(["--check"]), 0)

    def test_45_points_grid_per_section_6_3(self):
        pts = G.screen_points()
        self.assertEqual(len(pts), 45)
        self.assertEqual({p for p, _, _ in pts}, {"tt", "ff", "ss", "fs", "sf"})
        self.assertEqual({v for _, v, _ in pts}, {2.97, 3.3, 3.63})
        self.assertEqual({t for _, _, t in pts}, {-40, 27, 125})
        self.assertEqual(len(set(pts)), 45)

    def test_each_request_is_one_corner_n30_native_fields(self):
        for p, v, t in G.screen_points():
            r = json.loads((TB / f"request_screen_{G.point_name(p, v, t)}.json").read_text())
            self.assertEqual(len(r["corners"]["process"]), 1)
            self.assertEqual(r["corners"]["temperature_c"], [t])
            self.assertEqual(r["corners"]["supply_v"]["Vdd"], [v])
            self.assertEqual(r["corners"]["supply_v"]["Vref"], [v])
            self.assertAlmostEqual(r["corners"]["supply_v"]["Vcm"][0], v / 2, places=4)
            self.assertEqual(set(r["monte_carlo"]), {"n", "seed", "vary"})
            self.assertEqual(r["monte_carlo"]["n"], 30)
            self.assertEqual(len(r["measurements"]), 2 * NU)

    def test_seed_schedule_unique_and_distinct_from_pilot(self):
        seeds = [G.screen_request(*pt)["monte_carlo"]["seed"] for pt in G.screen_points()]
        self.assertEqual(len(set(seeds)), 45)
        self.assertNotIn(G.MC_SEED, seeds)
        self.assertEqual(G.check_screening_schedule(), [])

    def test_schedule_check_catches_a_collision(self):
        orig = G.point_seed
        try:
            G.point_seed = lambda name, base=G.SCR_BASE_SEED: 7
            self.assertTrue(any("seed 7 used by" in m for m in G.check_screening_schedule()))
        finally:
            G.point_seed = orig

    def test_range_widened_at_least_3_lsb_beyond_pilot_mean(self):
        up = G.screen_up()
        mean = 3.69e-3
        self.assertGreaterEqual(mean - up[0], 3 * A.LSB_SE_V)
        self.assertGreaterEqual(up[-1] - mean, 3 * A.LSB_SE_V)

    def test_screening_netlist_stacks_inputs_on_vcm_and_pilot_untouched(self):
        t = (TB / G.SCREEN_NETLIST).read_text()
        self.assertIn("Vinp  pinp vcm pwl(", t)
        self.assertIn("sw_stat_mismatch=1", t)
        self.assertIn("sw_stat_mismatch=0", (TB / G.SCREEN_NULL_NETLIST).read_text())
        self.assertIn("Vinp  pinp 0 pwl(", (TB / G.ENABLED_NETLIST).read_text())

    def test_descending_levels_are_ascending_reversed(self):
        seq = G.screen_seq()
        self.assertEqual(len(seq), 2 * NU)
        self.assertEqual(seq[NU:], seq[:NU][::-1])


class RuntimePlan(unittest.TestCase):
    def test_split_per_corner_beats_serial(self):
        p = S.runtime_plan()
        self.assertEqual(p["jobs"], 45)
        self.assertAlmostEqual(p["seconds_per_draw"], 2725 / 8 * 82 / 33)
        self.assertAlmostEqual(p["serial_hours_if_one_job"], p["hours_per_job"] * 45)
        self.assertEqual(p["waves"], 6)
        self.assertLess(p["wall_hours_split_per_corner"], p["serial_hours_if_one_job"] / 7)


class DescendingEstimator(unittest.TestCase):
    def test_no_hysteresis_reports_zero(self):
        s = A.sample_from_corner(screen_corner(0, 20))
        self.assertAlmostEqual(s["hysteresis_v"], 0.0)
        self.assertAlmostEqual(s["vos_up_v"], s["vos_down_v"])
        self.assertFalse(s["hysteresis_flag"])
        self.assertEqual(s["vos_v"], s["vos_up_v"])

    def test_hysteresis_is_up_minus_down(self):
        s = A.sample_from_corner(screen_corner(0, 22, down_at=20))
        self.assertAlmostEqual(s["hysteresis_v"], 2 * G.STEP_V)
        self.assertAlmostEqual(s["hysteresis_v"], s["vos_up_v"] - s["vos_down_v"])
        self.assertTrue(s["hysteresis_flag"])
        self.assertAlmostEqual(s["vos_mid_v"], 0.5 * (s["vos_up_v"] + s["vos_down_v"]))
        s2 = A.sample_from_corner(screen_corner(0, 20, down_at=21))
        self.assertAlmostEqual(s2["hysteresis_v"], -G.STEP_V)

    def test_up_threshold_matches_ascending_midpoint(self):
        s = A.sample_from_corner(screen_corner(0, 20))
        self.assertAlmostEqual(s["vos_up_v"], 0.5 * (G.screen_up()[20] + G.screen_up()[21]))

    def test_descending_failures_are_reported_not_dropped(self):
        c = screen_corner(0, 20)
        for m in c["measurements"]:
            if m["name"].startswith("r"):
                m["value"] = 0.0
        s = A.sample_from_corner(c)
        self.assertIsNone(s["vos_v"])
        self.assertIn("descending: censored", s["failure"])
        c = screen_corner(0, 20)
        c["measurements"][-1]["value"] = 1.6
        self.assertIn("descending: indeterminate", A.sample_from_corner(c)["failure"])

    def test_supply_from_corner_sets_rail_threshold(self):
        s = A.sample_from_corner(screen_corner(0, 20, vdd=2.97))
        self.assertIsNotNone(s["vos_v"])

    def test_pilot_layout_unchanged_no_hysteresis_keys(self):
        r = json.loads((CORNERS / "pilot-warn-report.json").read_text())
        s = A.sample_from_corner(r["corners"][0])
        self.assertNotIn("hysteresis_v", s)
        self.assertAlmostEqual(s["vos_v"], 2.75e-3)


class RecordWriterNegativeControls(unittest.TestCase):
    def test_duplicate_seeds_rejected(self):
        p = population("a", [2, 3, 4], seeds=[1, 2, 2])
        with self.assertRaisesRegex(W.RecordError, "duplicate seed 2"):
            W.build_record([p], "rid")

    def test_duplicate_seeds_across_populations_rejected(self):
        a = population("a", [2, 3], seeds=[1, 2])
        b = population("b", [2, 3], seeds=[2, 3])
        with self.assertRaisesRegex(W.RecordError, "duplicate seed"):
            W.build_record([a, b], "rid")

    def test_null_control_may_share_seed_schedule(self):
        a = population("a", [2, 3, 5], seeds=[1, 2, 3])
        n = population("n", [3, 3, 3], seeds=[1, 2, 3], mismatch=False)
        rec = W.build_record([a, n], "rid")
        self.assertEqual(rec["status"], "recorded")

    def test_missing_seed_rejected(self):
        p = population("a", [2, 3, 4])
        p["summary"]["draws"][1]["seed"] = None
        with self.assertRaisesRegex(W.RecordError, "no per-sample seed"):
            W.build_record([p], "rid")

    def test_all_identical_samples_flagged_path_failure(self):
        p = population("a", [3.25] * 6)
        self.assertIn("failure of the path", p["summary"]["path_failure"])
        rec = W.build_record([p], "rid")
        self.assertEqual(rec["status"], "path_failure")
        self.assertTrue(any("PATH FAILURE" in f for f in rec["flags"]))

    def test_identical_null_control_is_not_a_path_failure(self):
        self.assertIsNone(population("n", [3.25] * 4, mismatch=False)["summary"]["path_failure"])

    def test_failed_and_censored_draws_reported_not_dropped(self):
        p = population("a", [2.0, None, 4.0, 3.0, None], n_req=6)
        s = p["summary"]
        self.assertEqual((s["n_returned"], s["n_valid"], s["n_failed"], s["n_censored"], s["n_missing"]), (5, 3, 2, 2, 1))
        self.assertEqual({f["sample_index"] for f in s["failed"]}, {1, 4})
        self.assertTrue(all(f["seed"] is not None and f["reason"] for f in s["failed"]))
        self.assertEqual(len(s["draws"]), 5)
        rec = W.build_record([p], "rid")
        self.assertTrue(any("failure rate" in f for f in rec["flags"]))
        self.assertEqual(W.validate_record(rec), [])
        md = W.render_markdown(rec)
        self.assertIn("seed 101: censored", md)

    def test_validate_catches_a_dropped_draw(self):
        rec = W.build_record([population("a", [2, 3, 4])], "rid")
        rec["populations"][0]["summary"]["n_returned"] = 4
        self.assertTrue(any("dropped" in m for m in W.validate_record(rec)))

    def test_lag1_autocorrelation_reported(self):
        self.assertAlmostEqual(W.lag1_autocorrelation([1, 2, 3, 4, 5]), 0.4)
        self.assertLess(W.lag1_autocorrelation([1, -1, 1, -1, 1, -1]), -0.5)
        self.assertIsNone(W.lag1_autocorrelation([1, 2]))
        self.assertIsNone(W.lag1_autocorrelation([2, 2, 2]))
        s = population("a", list(range(1, 21)))["summary"]["lag1_autocorrelation"]
        self.assertGreater(s["r1"], s["bound_2_over_sqrt_n"])
        self.assertFalse(s["within_bound"])
        self.assertIn("Lag-1 autocorrelation", W.render_markdown(W.build_record([population("a", [1, 3, 2, 5])], "rid")))

    def test_hysteresis_summary_from_screening_draws(self):
        c = [A.sample_from_corner(screen_corner(i, 18 + i, down_at=18 + i - (i % 3))) for i in range(6)]
        s = W.population_summary(c, True, 6)
        self.assertEqual(s["hysteresis"]["n"], 6)
        self.assertIn("up_threshold - down_threshold", s["hysteresis"]["definition"])
        self.assertEqual(s["hysteresis"]["n_exceeding_one_step"], 2)  # i=2,5 -> 2 steps

    def test_append_only_never_overwrites(self):
        rec = W.build_record([population("a", [2, 3, 4])], "rid")
        with tempfile.TemporaryDirectory() as d:
            paths = W.write_record(rec, d)
            before = [p.read_text() for p in paths]
            with self.assertRaises(FileExistsError):
                W.write_record(rec, d)
            self.assertEqual(before, [p.read_text() for p in paths])

    def test_rejected_record_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(W.main(["--record-id", "r", "--out-dir", d, "--population",
                                     f"a={CORNERS / 'pilot-warn-report.json'}", "--population",
                                     f"b={CORNERS / 'pilot-warn-report.json'}"]), 2)
            self.assertEqual(list(Path(d).iterdir()), [])


class ProbeEvidence(unittest.TestCase):
    def test_probe_reproduces_pilot_sample0_and_reports_hysteresis(self):
        rep = json.loads((TB.parent / "corners" / "20261009-080236-c53a9b17" / "run3" / "screen-probe-report.json").read_text())
        s = A.sample_from_corner(rep["corners"][0])
        pilot = A.sample_from_corner(json.loads((CORNERS / "pilot-warn-report.json").read_text())["corners"][0])
        self.assertEqual(s["seed"], pilot["seed"])
        self.assertAlmostEqual(s["vos_up_v"], pilot["vos_v"])
        self.assertAlmostEqual(s["hysteresis_v"], s["vos_up_v"] - s["vos_down_v"])
        self.assertFalse(s["hysteresis_flag"])


class DryRunFixture(unittest.TestCase):
    def build(self):
        pops = [W.load_population("pilot-enabled", CORNERS / "pilot-warn-report.json"),
                W.load_population("pilot-null", CORNERS / "null-warn-report.json", mismatch_on=False)]
        return pops

    def test_fixture_is_schema_valid_qualification_not_a_claim(self):
        rec = json.loads(FIXTURE.with_suffix(".json").read_text())
        self.assertEqual(W.validate_record(rec), [])
        self.assertEqual(rec["kind"], "qualification")
        self.assertIsNone(rec["claim"])
        self.assertFalse(rec["offset_row_touched"])
        self.assertIn("NOT A CLAIM", rec["claim_note"])
        self.assertIn("NOT A CLAIM", FIXTURE.with_suffix(".md").read_text())

    def test_fixture_reproduces_from_committed_reports(self):
        rec = json.loads(FIXTURE.with_suffix(".json").read_text())
        fresh = W.build_record(self.build(), rec["record_id"], "qualification", rec["note"])
        self.assertEqual(json.loads(json.dumps(fresh, default=str)), rec)
        self.assertEqual(W.render_markdown(fresh), FIXTURE.with_suffix(".md").read_text())

    def test_fixture_numbers_match_readme_section_5(self):
        rec = json.loads(FIXTURE.with_suffix(".json").read_text())
        en = rec["populations"][0]["summary"]
        self.assertEqual((en["n_valid"], en["n_failed"]), (8, 0))
        self.assertAlmostEqual(en["stats"]["mean_mv"], 3.6875, places=3)
        self.assertAlmostEqual(en["stats"]["sd_mv"], 1.178, places=3)
        self.assertEqual(en["distinct_values"], 6)

    def test_fixture_provenance_complete(self):
        rec = json.loads(FIXTURE.with_suffix(".json").read_text())
        for p in rec["populations"]:
            pr = p["provenance"]
            self.assertEqual(len(pr["netlist_sha256"]), 64)
            self.assertEqual(len(pr["models_lib_sha256"]), 64)
            self.assertTrue(pr["klt_version"] and pr["engine_version"] and pr["job_id"])
            self.assertEqual(pr["monte_carlo"]["seed"], G.MC_SEED)


if __name__ == "__main__":
    unittest.main()
