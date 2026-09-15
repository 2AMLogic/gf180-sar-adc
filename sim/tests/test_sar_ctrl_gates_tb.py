#!/usr/bin/env python3
"""The committed gate-level SAR-sequencer replay testbenches must match a
fresh run of `design/sar-logic/flow/gen_sar_ctrl_gates_tb.py` (issue #273).

    python3 -m unittest discover -s sim/tests -v

Same "generator is the source of truth, diff a fresh run against the
committed artifact" discipline as `test_sar_logic_netlist.py` (rung-1 ideal
model) and `test_sar_ctrl_gate_netlist.py` (the gate netlist itself, issue
#272), applied to the gate-level replay testbenches this issue adds.

## Why this test SKIPS (not fails) without a PDK, but does NOT need `klt`

`gen_sar_ctrl_gates_tb.py` translates the already-committed gate netlist
(`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`) into
SPICE via `gate_netlist_to_spice.py` -- pure Python, no external tool. It
DOES need the gf180mcu PDK's own standard-cell SPICE library text
(`libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice`) as
an input, which `.github/workflows/ci.yml`'s default PR path does not
install (same constraint `test_sar_ctrl_gate_netlist.py`'s own docstring
explains). Unlike that sibling test, this one does NOT need `klt`/Yosys at
all -- so it is one step closer to running on the headless PR path than the
netlist-synthesis check is, and should move there first if/when the PDK
itself becomes CI-installable independently of `klt`.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "design" / "sar-logic" / "flow" / "gen_sar_ctrl_gates_tb.py"

_spec = importlib.util.spec_from_file_location("gen_sar_ctrl_gates_tb", GEN)
gen_gates = importlib.util.module_from_spec(_spec)
sys.modules["gen_sar_ctrl_gates_tb"] = gen_gates


def _pdk_available() -> bool:
    sys.path.insert(0, str(REPO))
    from sim.harness.pdk import PdkNotFound, find_pdk  # noqa: PLC0415

    try:
        find_pdk()
    except PdkNotFound:
        return False
    return True


class GateTbDriftTests(unittest.TestCase):
    """PDK-dependent -- see module docstring for why this SKIPS (not fails)
    without one."""

    @classmethod
    def setUpClass(cls):
        if not REPO.joinpath(
            "design", "sar-logic", "flow", "sar_ctrl", "netlist", "sar_ctrl.mcu7t5v0.synth.v"
        ).is_file():
            raise unittest.SkipTest("committed gate netlist missing -- run synth_sar_ctrl.py (issue #272)")
        if not _pdk_available():
            raise unittest.SkipTest(
                "gf180mcu PDK not resolvable -- see sim/harness/pdk.py and docs/environment-setup.md"
            )
        _spec.loader.exec_module(gen_gates)
        for name, (rel, _fn) in gen_gates.TARGETS.items():
            if not (REPO / rel).is_file():
                raise AssertionError(f"committed gate-level testbench missing for {name}: {rel}")

    def test_committed_testbenches_match_a_fresh_generation(self):
        for name, (rel, fn) in sorted(gen_gates.TARGETS.items()):
            with self.subTest(target=name):
                path = REPO / rel
                self.assertEqual(
                    path.read_text(),
                    fn(),
                    f"{rel} is stale -- run: python3 {GEN.relative_to(REPO)}",
                )

    def test_check_mode_agrees(self):
        self.assertEqual(gen_gates.main(["--check"]), 0)


class GateTbFragmentRuleTests(unittest.TestCase):
    """The generated fragments must stay loadable by the corner runner --
    same guard `test_sar_logic_netlist.py`'s `NetlistFragmentRuleTests`
    applies to the rung-1 fragments, applied here to the gate-level ones.
    This half needs no PDK: it only inspects the already-committed files."""

    def test_fragments_contain_no_forbidden_directives(self):
        sys.path.insert(0, str(REPO / "sim"))
        from harness.testbench import FORBIDDEN_DIRECTIVES  # noqa: PLC0415

        for rel in (
            "sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice",
            "sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice",
        ):
            path = REPO / rel
            if not path.is_file():
                self.skipTest(f"{rel} not committed yet")
            with self.subTest(target=rel):
                for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
                    directive = raw.strip().split()[0].lower() if raw.strip() else ""
                    self.assertNotIn(
                        directive,
                        FORBIDDEN_DIRECTIVES,
                        f"{rel}:{lineno} uses {directive}, which the harness rejects",
                    )

    def test_manifests_load_cleanly(self):
        sys.path.insert(0, str(REPO))
        from sim.harness.testbench import load  # noqa: PLC0415

        for slug in ("sar-logic-functional-gates", "sar-logic-timing-gates"):
            with self.subTest(slug=slug):
                tb = load(REPO / "sim" / slug)
                self.assertEqual(tb.corners, ("mos",))
                self.assertEqual(tb.temperatures_c, (-40.0, 27.0, 125.0))


if __name__ == "__main__":
    unittest.main()
