#!/usr/bin/env python3
"""Exhaustive functional verification of the SAR control logic. No PDK, no ngspice.

    python3 -m unittest discover -s sim/tests -v

This is the cheap rung of the fidelity ladder DR-0008 ratifies, doing the job
only it can do: every one of the 2 x 1024 decision sequences the controller can
be handed, in both input modes, checked cycle by cycle against the reference
model in ``design/sar-logic/sar_reference.py``. The structure evaluated here is
the *same* element list ``design/sar-logic/sar_logic.spice`` is generated from,
and the last test in this file fails if the committed netlist has drifted from
it -- so "verified" and "laid out" cannot come apart.

The complementary rung lives in ``sim/sar-logic/``: the real gf180mcu
transistor netlist, four conversions, full PVT matrix, worst-corner delay.
Neither replaces the other. A transient long enough to cover 2048 conversions
would take days per corner; a gate-level sweep cannot see a hold-time failure
at ff/-40 C.
"""

from __future__ import annotations

import itertools
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DESIGN = REPO / "design" / "sar-logic"
sys.path.insert(0, str(DESIGN))

import sar_logic  # noqa: E402
import sar_reference  # noqa: E402


def snapshot(sim: sar_logic.GateSim) -> dict:
    return {
        "cells": sim.cell_states(),
        "samp": bool(sim.values["samp_n"]),
        "code": sim.code(),
        "eoc": bool(sim.values["eoc"]),
        "complements_ok": sim.complements_ok(),
    }


def drive_conversion(
    sim: sar_logic.GateSim, pattern: tuple[int, ...], mode_diff: bool
) -> list[dict]:
    """One conversion, sampled once per cycle just before the closing clock edge."""
    states = []
    mode = 1 if mode_diff else 0
    for cycle in range(sar_reference.CLOCK_MULTIPLIER):
        trial = None if cycle < sar_reference.ACQUIRE_CYCLES else cycle - sar_reference.ACQUIRE_CYCLES + 1
        # Outside a trial the comparator output is meaningless; hold it at the
        # value that would be most likely to corrupt state if it were being
        # captured when it should not be.
        decision = pattern[trial - 1] if trial else 1
        sim.settle(cmp=decision, mode=mode)
        states.append(snapshot(sim))
        sim.clock(cmp=decision, mode=mode)
    return states


def fresh_sim() -> sar_logic.GateSim:
    sim = sar_logic.GateSim(sar_logic.build())
    sim.settle(rstb=0, clk=0, cmp=0, mode=0)
    sim.settle(rstb=1)
    return sim


class ResetTests(unittest.TestCase):
    def test_reset_puts_the_sequencer_in_a_defined_acquire_state(self):
        sim = fresh_sim()
        self.assertEqual(sim.values["s0"], 1, "sequencer stage 0 must preset to 1")
        self.assertEqual(
            sum(sim.values[f"s{j}"] for j in range(sar_reference.CLOCK_MULTIPLIER)),
            1,
            "the ring must be one-hot after reset, or it never sequences",
        )
        self.assertTrue(snapshot(sim)["samp"], "reset must land in the acquire phase")
        self.assertEqual(sim.code(), 0)
        for state in sim.cell_states().values():
            self.assertEqual(state, sar_reference.REL)
        self.assertTrue(sim.complements_ok())

    def test_reset_is_asynchronous(self):
        """Reset asserted mid-conversion must take effect without a clock edge."""
        sim = fresh_sim()
        drive_conversion(sim, (1,) * sar_reference.N_BITS, mode_diff=True)
        sim.settle(cmp=1, mode=1)
        sim.clock(cmp=1, mode=1)
        sim.clock(cmp=1, mode=1)
        self.assertNotEqual(sim.code(), 0, "precondition: state is non-trivial")
        sim.settle(rstb=0)          # no clock edge here
        self.assertEqual(sim.values["s0"], 1)
        self.assertEqual(sim.code(), 0)
        for state in sim.cell_states().values():
            self.assertEqual(state, sar_reference.REL)


class ExhaustiveTests(unittest.TestCase):
    """Every decision sequence, both modes, cycle by cycle."""

    def _check_all(self, mode_diff: bool):
        sim = fresh_sim()
        previous_code = 0
        for pattern in itertools.product((0, 1), repeat=sar_reference.N_BITS):
            expected = sar_reference.conversion_cycles(pattern, mode_diff, previous_code)
            observed = drive_conversion(sim, pattern, mode_diff)
            for want, got in zip(expected, observed):
                self.assertTrue(
                    got["complements_ok"],
                    f"pattern {pattern} cycle {want.cycle}: a T-gate drive pair is not "
                    "complementary, so the gate would half-open",
                )
                self.assertEqual(
                    got["cells"], want.cells,
                    f"pattern {pattern} mode_diff={mode_diff} cycle {want.cycle}: "
                    "switch vector differs from the reference model",
                )
                self.assertEqual(got["samp"], want.samp,
                                 f"pattern {pattern} cycle {want.cycle}: sampling switch")
                self.assertEqual(got["code"], want.code,
                                 f"pattern {pattern} cycle {want.cycle}: output register "
                                 "must hold the PREVIOUS code for the whole conversion")
                self.assertEqual(got["eoc"], want.eoc)
            previous_code = sar_reference.code_of(pattern)
            self.assertEqual(sim.code(), previous_code,
                             f"pattern {pattern}: output register after the conversion")

    def test_every_decision_sequence_single_ended(self):
        self._check_all(mode_diff=False)

    def test_every_decision_sequence_differential(self):
        self._check_all(mode_diff=True)

    def test_single_ended_never_drives_the_reference_side(self):
        """DR-0006's load-bearing mode difference, stated as its own assertion.

        Driving the V_cm-pinned side in single-ended mode doubles every step and
        costs a bit of resolution. It is covered by the exhaustive sweep above,
        but a failure there would report as "switch vector differs"; this says
        what actually broke.
        """
        sim = fresh_sim()
        for pattern in itertools.product((0, 1), repeat=sar_reference.N_BITS):
            for state in drive_conversion(sim, pattern, mode_diff=False):
                for (side, weight), cell in state["cells"].items():
                    if side == "n":
                        self.assertEqual(
                            cell, sar_reference.REL,
                            f"weight {weight} on the V_cm-pinned side switched in "
                            f"single-ended mode (pattern {pattern})",
                        )


class RegisterTests(unittest.TestCase):
    def test_output_register_holds_for_a_full_sample_period(self):
        """DR-0005 scopes a register, not a strobe: the code must stay readable."""
        sim = fresh_sim()
        pattern = (1, 1, 0, 1, 0, 0, 1, 0, 1, 1)
        drive_conversion(sim, pattern, mode_diff=True)
        want = sar_reference.code_of(pattern)
        self.assertEqual(sim.code(), want)
        for cycle in range(sar_reference.CLOCK_MULTIPLIER):
            self.assertEqual(sim.code(), want, f"code changed during hold cycle {cycle}")
            sim.clock(cmp=0, mode=1)

    def test_code_is_the_decisions_themselves(self):
        """No redundancy (DR-0009) means no correction arithmetic anywhere."""
        sim = fresh_sim()
        for pattern in ((0,) * 10, (1,) * 10, (1, 0, 1, 0, 1, 0, 1, 0, 1, 0)):
            drive_conversion(sim, pattern, mode_diff=True)
            self.assertEqual(sim.code(), sar_reference.code_of(pattern))


class StructureTests(unittest.TestCase):
    def test_every_control_pin_is_a_port(self):
        netlist = sar_logic.build()
        ports = set(sar_logic.SUBCKT_PORTS)
        for side in sar_reference.SIDES:
            for weight in sar_reference.WEIGHTS:
                for kind in ("rel", "sel_hi", "sel_lo"):
                    for phase in ("n", "p"):
                        self.assertIn(sar_logic.control_net(kind, phase, weight, side), ports)
        driven = {out for e in netlist.elements for out in e.outs}
        for port in sar_logic.ports_out():
            self.assertIn(port, driven, f"output port {port} is not driven by anything")

    def test_flip_flop_count_matches_the_architecture(self):
        netlist = sar_logic.build()
        expected = (
            sar_reference.CLOCK_MULTIPLIER            # one-hot sequencer
            + sar_reference.N_BITS                    # decision register
            + len(sar_reference.WEIGHTS)              # engaged flags
            + sar_reference.N_BITS                    # parallel output register
        )
        self.assertEqual(len(netlist.flops), expected)

    def test_clock_multiplier_matches_the_ratified_clocking_record(self):
        """DR-0003 ratifies M = 16 (16 MHz at 1 MS/s, 32 MHz at the 2 MS/s stretch)."""
        self.assertEqual(sar_reference.CLOCK_MULTIPLIER, 16)
        self.assertEqual(
            sar_reference.ACQUIRE_CYCLES + sar_reference.N_BITS,
            sar_reference.CLOCK_MULTIPLIER,
            "one cycle per bit trial plus the acquire phase must fill the sample period",
        )
        self.assertAlmostEqual(sar_logic.T_CLK_NS, 1e3 / 16.0)

    def test_generated_artifacts_are_current(self):
        """The committed netlist, testbench and manifest must match the generator."""
        result = subprocess.run(
            [sys.executable, str(DESIGN / "generate.py"), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            "generated artifacts are stale -- run python3 design/sar-logic/generate.py\n"
            + result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
