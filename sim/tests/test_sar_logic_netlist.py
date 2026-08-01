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
        """DR-0006: 2^(N-1) array, MSB resolved with no array switching, so
        nine binary weights 256..1 remain to be switched, not ten."""
        self.assertEqual(gen.WEIGHTS, [256, 128, 64, 32, 16, 8, 4, 2, 1])
        self.assertEqual(sum(gen.WEIGHTS), 511)

    def test_controller_drives_one_control_bus_not_two(self):
        """54 active-high controls leave the controller (3 per cell x 9
        weights x 2 sides); the complementary PMOS gate is made locally by
        sar_tgate_drv, so the array control bus is 54 wires wide, not 108."""
        ports = gen._ports_ctrl_analog()
        controls = [p for p in ports if p.startswith(("rel_", "sel_"))]
        self.assertEqual(len(controls), 54)
        self.assertEqual([p for p in controls if "_p_" in p], [])
        self.assertIn("sel_hi_n_256p", controls)
        self.assertIn("sel_lo_n_1n", controls)

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


if __name__ == "__main__":
    unittest.main()
