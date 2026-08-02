#!/usr/bin/env python3
"""The committed SAR-logic netlists must match their generator.

    python3 -m unittest discover -s sim/tests -v

`sim/harness/testbench.py` rejects `.include` in a testbench fragment, so a
testbench cannot reference the DUT -- it has to carry it inline. That leaves
`design/sar-logic/sar_ctrl.spice` and the two testbench fragments holding three
copies of the same 9-slice, 54-control decode, and a testbench that has quietly
drifted from the design it claims to verify is worse than no testbench: it
still passes, and it certifies something that is no longer in `design/`.

`design/sar-logic/gen_sar_logic.py` is the single source of truth and these
tests are the guard. They need neither ngspice nor the PDK, so they run on the
PDK-free CI path (`.github/workflows/ci.yml`) on every pull request.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "design" / "sar-logic" / "gen_sar_logic.py"

_spec = importlib.util.spec_from_file_location("gen_sar_logic", GEN)
gen = importlib.util.module_from_spec(_spec)
sys.modules["gen_sar_logic"] = gen
_spec.loader.exec_module(gen)


class GeneratedNetlistTests(unittest.TestCase):
    def test_committed_files_match_the_generator(self):
        """The anti-drift check. Regenerate and diff, do not just re-parse."""
        for name, (rel, fn) in sorted(gen.TARGETS.items()):
            with self.subTest(target=name):
                path = REPO / rel
                self.assertTrue(path.is_file(), f"{rel} is missing")
                self.assertEqual(
                    path.read_text(),
                    fn(),
                    f"{rel} is stale -- run: python3 {GEN.relative_to(REPO)}",
                )

    def test_check_mode_agrees(self):
        self.assertEqual(gen.main(["--check"]), 0)


class NetlistFragmentRuleTests(unittest.TestCase):
    """The generated testbenches must stay loadable by the corner runner."""

    def test_fragments_contain_no_forbidden_directives(self):
        sys.path.insert(0, str(REPO / "sim"))
        from harness.testbench import FORBIDDEN_DIRECTIVES  # noqa: PLC0415

        for name in ("functional", "timing"):
            rel, _ = gen.TARGETS[name]
            with self.subTest(target=name):
                for lineno, raw in enumerate(
                    (REPO / rel).read_text().splitlines(), start=1
                ):
                    directive = raw.strip().split()[0].lower() if raw.strip() else ""
                    self.assertNotIn(
                        directive,
                        FORBIDDEN_DIRECTIVES,
                        f"{rel}:{lineno} uses {directive}, which the harness rejects",
                    )


class ControllerStructureTests(unittest.TestCase):
    """Structural facts the decision records depend on, asserted here so a
    later edit to the generator cannot silently invalidate them."""

    def test_sixteen_phases_four_sample_ten_trials_two_tail(self):
        """README Latency row / DR-0003: M = 16 = 4 + 10 + 2."""
        self.assertEqual(len(gen.PH_SAMPLE), 4)
        n_trials = gen.PH_LAST_TRIAL - gen.PH_TRIAL0 + 1
        self.assertEqual(n_trials, 10)
        tail = 16 - len(gen.PH_SAMPLE) - n_trials
        self.assertEqual(tail, 2)
        self.assertEqual((gen.PH_LOAD, gen.PH_DRDY), (14, 15))

    def test_nine_switched_weights_free_msb(self):
        """DR-0011: 2^(N-1) array, MSB resolved with no array switching, so
        nine binary weights 256..1 remain to be switched, not ten."""
        self.assertEqual(gen.WEIGHTS, [256, 128, 64, 32, 16, 8, 4, 2, 1])
        self.assertEqual(sum(gen.WEIGHTS), 511)

    def test_controller_drives_one_control_bus_not_two(self):
        """55 active-high controls leave the controller: 3 per cell x 9
        weights x 2 sides, plus DR-0014's single broadcast V_in leg. The
        complementary PMOS gate is made locally by sar_tgate_drv, so the
        array control bus is 55 wires wide, not 110 -- and DR-0014's fourth
        leg costs ONE wire, not 18, because all bottom plates sample
        together."""
        ports = gen._ports_ctrl_analog()
        controls = [p for p in ports if p.startswith(("rel_", "sel_"))]
        self.assertEqual(len(controls), 55)
        self.assertEqual([p for p in controls if "_p_" in p], [])
        self.assertIn("sel_hi_n_256p", controls)
        self.assertIn("sel_lo_n_1n", controls)
        self.assertEqual(controls.count("sel_in_n"), 1)

    def test_library_defines_the_expected_subckts(self):
        text = gen.library()
        for sub in (
            "sar_bitreg",
            "sar_slice",
            "sar_seq",
            "sar_ctrl",
            "sar_ctrl_a",
            "sar_tgate_drv",
        ):
            with self.subTest(subckt=sub):
                self.assertIn(f".subckt {sub} ", text)


class BottomPlateSamplingTests(unittest.TestCase):
    """DR-0014's two structural consequences for the controller: a fourth
    one-hot leg per cell, and a two-phase sample in which the top-plate
    switch opens strictly BEFORE the bottom plates leave V_in. Both are
    asserted here so a later edit to the generator cannot quietly undo the
    decision record while leaving every simulation still passing."""

    def test_top_plate_switch_opens_before_the_bottom_plates_release(self):
        """The ordering IS the record. The top-plate control covers a strict
        prefix of the sample window and the bottom-plate control covers all
        of it, so samp_tp falls at least one whole clock before samp_bp."""
        self.assertEqual(
            tuple(gen.PH_SAMPLE_TOP), tuple(gen.PH_SAMPLE[: len(gen.PH_SAMPLE_TOP)])
        )
        self.assertLess(len(gen.PH_SAMPLE_TOP), len(gen.PH_SAMPLE))
        lead_clocks = len(gen.PH_SAMPLE) - len(gen.PH_SAMPLE_TOP)
        self.assertGreaterEqual(lead_clocks, 1)

    def test_the_two_phase_sample_costs_no_extra_clock(self):
        """DR-0014: 'Both fit inside DR-0003's existing 4-clock sample phase
        and M = 16'. The sample window is still four clocks and the trials
        still start at ph4."""
        self.assertEqual(len(gen.PH_SAMPLE), 4)
        self.assertEqual(gen.PH_SAMPLE[-1] + 1, gen.PH_TRIAL0)
        self.assertEqual(gen.CONV_NS, 16 * gen.CLK_PERIOD_NS)

    def test_both_sample_controls_are_ports_of_both_wrappers(self):
        self.assertIn("samp_tp", gen._ports_ctrl_digital())
        self.assertIn("samp_bp", gen._ports_ctrl_digital())
        self.assertIn("samp_tp_n", gen._ports_ctrl_analog())
        self.assertIn("sel_in_n", gen._ports_ctrl_analog())

    def test_the_comparator_is_inverted_exactly_once(self):
        """Bottom-plate sampling inverts the residue, so the controller takes
        the inversion at its own boundary and the slices consume `dec`. Two
        inversions would diverge; none would emit the one's complement."""
        text = gen.library()
        self.assertIn("a_dec cmp dec sarl_inv", text)
        self.assertEqual(text.count(" sarl_inv\na_dec"), 0)
        for w in gen.WEIGHTS:
            self.assertIn(f"xs{w} clk dec mode ", text)
        self.assertNotIn("xdir clk cmp arm", text)

    def test_the_cell_decode_has_four_one_hot_legs(self):
        """`in` and `rel` are complementary across the sample boundary, and
        the generator must emit them at the SAME logic depth -- otherwise
        every cell drives V_in and V_cm together for one gate delay, which is
        a real short and not a modelling artifact."""
        text = gen.library()
        self.assertIn("a_smpb samp4 smpb sarl_inv", text)
        self.assertIn("a_sampbp smpb samp_bp sarl_inv", text)
        self.assertIn("a_relp [engb smpb] rel_p sarl_and", text)
        self.assertIn("a_reln [engnb smpb] rel_n sarl_and", text)

    def test_no_gated_or_inverted_clock_in_the_sample_path(self):
        """DR-0008 is synchronous on one clock's rising edge. The two-phase
        sample is built from one-hot phase ORs, not from a half-clock gate --
        an earlier draft used `clk` combinationally and glitched the V_in leg
        back on after the top plate had been released."""
        text = gen.library()
        for line in text.splitlines():
            if line.startswith("a_") and " sarl_dff" in line:
                # d_dff arg order: <d> <clk> <set> <reset> <q> <qb> <model>
                self.assertEqual(line.split()[2], "clk", line)
        self.assertNotIn("clkb", text)

    def test_every_loop_carries_the_two_phase_sample_instrument(self):
        """The ordering claim is only checkable if the two duty-cycle nodes
        exist in every closed loop of every deck. They replaced a pair of
        `meas WHEN ... FALL=k` edge times that sim/sar-logic-functional/'s
        20 ns maximum timestep could not resolve (record
        20260802-094246-16ec0f1 read the same design as 61.28 ns and 63.30 ns
        on two different conversions), so a revert to the edge form would look
        like a simplification and would silently un-check the record."""
        for target in ("functional", "timing", "budget-closure"):
            text = gen.TARGETS[target][1]()
            tags = sorted(
                ln.split()[0][1:-3]
                for ln in text.splitlines()
                if ln.startswith("b") and ln.split()[0].endswith("iso")
            )
            with self.subTest(target=target):
                self.assertTrue(tags, text[:400])
                for tag in tags:
                    self.assertIn(
                        f"b{tag}acq {tag}_acq 0 V = v({tag}_samp_tp_n)/vdd_val",
                        text,
                    )
                    self.assertIn(
                        f"b{tag}iso {tag}_iso 0 V = (v({tag}_sel_in_n)"
                        f"-v({tag}_samp_tp_n))/vdd_val",
                        text,
                    )


class TwoPhaseSampleManifestTests(unittest.TestCase):
    """The manifests that consume the instrument above. The tight bound must
    live in the deck whose timestep can carry it, and the coarse deck must
    not quietly re-acquire one."""

    def _manifest(self, slug: str) -> dict:
        import json

        return json.loads(
            (REPO / "sim" / slug / "testbench" / "tb.json").read_text()
        )

    def test_the_tight_bound_lives_in_the_fine_timestep_deck(self):
        fine = self._manifest("sar-logic-timing")
        coarse = self._manifest("sar-logic-functional")
        # 5 ns vs 20 ns maximum timestep -- the reason for the split.
        self.assertIn("tran 5n 8.5u 0 5n", fine["analyses"])
        self.assertIn("tran 20n 1024.5u 0 20n", coarse["analyses"])
        for key, nominal in (("iso_gap_ns", 62.5), ("acq_window_ns", 187.5)):
            with self.subTest(key=key):
                f = fine["checks"][key]
                c = coarse["checks"][key]
                f_width = f["max"] - f["min"]
                c_width = c["max"] - c["min"]
                self.assertLess(f_width, c_width, (f, c))
                self.assertLessEqual(f_width, 1.0, f)
                for w in (f, c):
                    self.assertLess(w["min"], nominal)
                    self.assertGreater(w["max"], nominal)

    def test_the_isolation_gap_is_required_to_be_positive(self):
        """The sign IS the ordering claim: a swapped pair reads about -62.5
        and a dropped second phase reads 0. Both bounds must exclude them."""
        for slug in ("sar-logic-timing", "sar-logic-functional"):
            checks = self._manifest(slug)["checks"]
            for key in [k for k in checks if k.startswith("iso_gap")]:
                with self.subTest(slug=slug, key=key):
                    self.assertGreater(checks[key]["min"], 0.0)

    def test_both_modes_are_checked_in_the_exhaustive_deck(self):
        """DR-0014's fourth leg is deliberately not mode-gated, so the gap has
        to be measured on both loops -- otherwise gating it by mode later
        would pass."""
        checks = self._manifest("sar-logic-functional")["checks"]
        self.assertIn("iso_gap_ns", checks)
        self.assertIn("iso_gap_df_ns", checks)


if __name__ == "__main__":
    unittest.main()
