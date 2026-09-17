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


class ComparatorOutputSlewTests(unittest.TestCase):
    """Issue #296: the UNDELAYED comparators in the gate-level decks must not
    drive a real standard-cell gate input from a zero-time ideal step.

    This is the structural half of #296's fix and it is asserted here, on the
    committed artifacts, because the failure it prevents is silent in code
    review: reverting the network re-introduces an ngspice
    `Timestep too small ... trouble with node "b<tag>cmp#branch"` abort that
    only shows up hours into a corner run. No PDK needed -- this only reads
    files that are already committed.

    Three separate properties, each of which #296 depends on:

    1. Every undelayed gate-level comparator reaches the DUT through the
       first-order network (`b...cmp -> <tag>_cmpd`, `r...cmps`, `c...cmpl`),
       never straight onto `<tag>_cmpo`.
    2. The DECISION is still the original hard ternary. A soft/high-gain
       comparator was measured and rejected (it holds real cell inputs at
       mid-rail and aborts on `vvdd_gate#branch` instead) -- and it would also
       quietly invalidate the timing deck's `tie` loop, whose claim
       presupposes a comparator that always resolves to a rail.
    3. The rung-1 IDEAL decks are NOT changed: they drive an XSPICE bridge
       with no analog load, so they keep the original single-line form and
       stay byte-identical to their committed, already-ratified text.
    """

    GATE_DECKS = (
        ("sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice",
         ("se", "df")),
        ("sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice",
         ("ok", "tie")),
    )
    #: loops whose comparator drives a matched 50 ohm terminated T-line
    #: instead of a bare gate input -- deliberately left alone by #296.
    DELAYED_TAGS = ("lt", "xl", "bad")
    IDEAL_DECKS = (
        "design/sar-logic/sar_ctrl.spice",
        "sim/sar-logic-functional/testbench/tb_sar_logic_functional.spice",
        "sim/sar-logic-timing/testbench/tb_sar_logic_timing.spice",
    )

    @staticmethod
    def _decision(tag: str, out: str) -> str:
        return f"b{tag}cmp {out} 0 V = v({tag}_topp) > v({tag}_topn) ? vdd_val : 0"

    def test_undelayed_gate_level_comparators_drive_through_an_rc(self):
        for rel, tags in self.GATE_DECKS:
            lines = (REPO / rel).read_text().splitlines()
            for tag in tags:
                with self.subTest(deck=rel, tag=tag):
                    self.assertIn(
                        self._decision(tag, f"{tag}_cmpd"), lines,
                        f"{rel}: {tag} comparator decision line missing or altered",
                    )
                    self.assertNotIn(
                        self._decision(tag, f"{tag}_cmpo"), lines,
                        f"{rel}: {tag} comparator drives the DUT gate input directly "
                        "again -- issue #296's zero-time-step abort is back",
                    )
                    series = [l for l in lines if l.startswith(f"r{tag}cmps ")]
                    shunt = [l for l in lines if l.startswith(f"c{tag}cmpl ")]
                    self.assertEqual(len(series), 1, f"{rel}: {tag} series R missing")
                    self.assertEqual(len(shunt), 1, f"{rel}: {tag} shunt C missing")
                    self.assertTrue(
                        series[0].startswith(f"r{tag}cmps {tag}_cmpd {tag}_cmpo "),
                        f"{rel}: {tag} series R is not between the decision node and "
                        f"the DUT-facing net: {series[0]!r}",
                    )
                    self.assertTrue(
                        shunt[0].startswith(f"c{tag}cmpl {tag}_cmpo 0 "),
                        f"{rel}: {tag} shunt C is not on the DUT-facing net: {shunt[0]!r}",
                    )

    def test_delayed_timing_loops_are_untouched(self):
        rel = "sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice"
        lines = (REPO / rel).read_text().splitlines()
        for tag in self.DELAYED_TAGS:
            with self.subTest(tag=tag):
                self.assertIn(self._decision(tag, f"{tag}_cmpi"), lines)
                self.assertTrue(
                    any(l.startswith(f"t{tag}d {tag}_cmpi 0 {tag}_cmpo 0 z0=50 td=")
                        for l in lines),
                    f"{rel}: {tag}'s delay T-line changed -- the 50 ohm termination is "
                    "what makes this loop immune to #296 in the first place",
                )
                self.assertIn(f"r{tag}term {tag}_cmpo 0 50", lines)
                self.assertEqual(
                    [], [l for l in lines if l.startswith((f"r{tag}cmps ", f"c{tag}cmpl "))],
                    f"{rel}: {tag} gained a #296 output network it does not need",
                )

    def test_ideal_rung1_decks_keep_the_original_single_line_comparator(self):
        for rel in self.IDEAL_DECKS:
            path = REPO / rel
            if not path.is_file():
                self.skipTest(f"{rel} not present")
            text = path.read_text()
            with self.subTest(deck=rel):
                self.assertNotIn(
                    "cmps ", text,
                    f"{rel}: a #296 comparator output network leaked into a rung-1 "
                    "ideal deck, whose committed text must stay byte-identical",
                )
                self.assertNotIn("cmpl ", text)
                self.assertNotIn("_cmpd ", text)


if __name__ == "__main__":
    unittest.main()
