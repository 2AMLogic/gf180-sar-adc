#!/usr/bin/env python3
"""Unit tests for `verify_remediation_dc.body_tie_result()` -- the body-tie
invariant the DC verification script decides *by parsing*, so no PDK, no
ngspice and no `klt` are needed to re-derive it (issue #784).

    python3 -m unittest discover -s sim/tests -t sim/tests -v

The check these pin replaced a literal `pfet_bodies == {"vdd"}` string
comparison that was true only for the extraction era it was written in. Two
things have moved under it since:

  * **Parasitic legs** (`875eac3` toolchain pin, issue #116 / upstream
    `klayout-tools#593`). A device card's terminal net is a LEG of its hub --
    `vdd__t17`, not `vdd` -- so the literal comparison is false on every
    committed extraction that has legs, tapped or not.
  * **DR-0035's drawn n-well taps** (#356 / PR #384, issue #381). On a tapped
    extraction nothing is rewritten to `vdd`; the bodies arrive on it. The
    count that carries the invariant is therefore the *partition*
    (rewritten + already-tied), not the rewrite alone.

So both eras are controlled here rather than one: a check that answered
correctly for only one of them is exactly what went stale. Every committed
`--pdk` extraction under `layout/adc-top/parasitics/reports/` is run through
the real `remediate_extracted.remediate()` and must satisfy the invariant,
pre-tap and post-tap alike, and the negative tests show the invariant is
falsifiable rather than vacuously true.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
PARA_DIR = REPO_ROOT / "layout" / "adc-top" / "parasitics"
sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(PARA_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _loadmod import load_module  # noqa: E402

import remediate_extracted as R  # noqa: E402

V = load_module("verify_remediation_dc", PARA_DIR / "verify_remediation_dc.py")

#: The first extraction taken after DR-0035 drew the n-well taps. Everything
#: sorting before it is pre-tap (anonymous bodies, rewritten by the script);
#: everything from it on is post-tap (bodies already on the drawn `vdd` tie).
FIRST_TAPPED = "20260923-094816-904af96"


def _pdk_extractions(top: str) -> list[Path]:
    """Every committed `--pdk` extraction of `top` (the same `pfet_03v3`
    test `remediate_extracted._latest_report()` applies), oldest first."""
    return [
        p
        for p in sorted((PARA_DIR / "reports").glob(f"*/{top.lower()}.para.spice"))
        if "pfet_03v3" in p.read_text()
    ]


class BodyTieInvariantOnCommittedExtractions(unittest.TestCase):
    """The invariant holds on every committed extraction, in BOTH eras."""

    def test_both_eras_are_actually_present(self):
        """Guard the guard: if `reports/` ever held only one era, the
        two-era claim below would pass without testing anything."""
        for top in ("ADC_TOP", "ADC_BLOCK"):
            names = [p.parent.name for p in _pdk_extractions(top)]
            self.assertTrue([n for n in names if n < FIRST_TAPPED],
                            f"{top}: no pre-tap extraction committed")
            self.assertTrue([n for n in names if n >= FIRST_TAPPED],
                            f"{top}: no post-tap extraction committed")

    def test_invariant_holds_on_every_committed_extraction(self):
        for top in ("ADC_TOP", "ADC_BLOCK"):
            for src in _pdk_extractions(top):
                with self.subTest(top=top, report=src.parent.name):
                    core_text, rem = R.remediate(src.read_text(), top)
                    bt = V.body_tie_result(core_text, rem, top)
                    self.assertTrue(bt["holds"], bt)
                    # Count-complete: no PMOS body is left undispositioned.
                    self.assertEqual(
                        bt["pmos_bodies_rewritten_to_vdd"]
                        + bt["pmos_bodies_already_tied_in_layout"],
                        bt["pmos_body_terminals"],
                    )
                    self.assertEqual(bt["pmos_body_nets_after"], [R.VDD_NET])

    def test_each_era_takes_its_own_disposition(self):
        """Pre-tap reports are rewritten; tapped ones are tied in layout.

        This is what the retired string check could not express: the two eras
        reach the same invariant by different routes, and the script has to
        pass on both.
        """
        for top in ("ADC_TOP", "ADC_BLOCK"):
            for src in _pdk_extractions(top):
                tapped = src.parent.name >= FIRST_TAPPED
                with self.subTest(top=top, report=src.parent.name, tapped=tapped):
                    core_text, rem = R.remediate(src.read_text(), top)
                    bt = V.body_tie_result(core_text, rem, top)
                    if tapped:
                        self.assertEqual(bt["disposition"], "drawn-in-layout")
                        self.assertTrue(bt["gap_closed_in_layout"])
                        self.assertEqual(bt["pmos_bodies_rewritten_to_vdd"], 0)
                        self.assertGreater(
                            bt["pmos_bodies_already_tied_in_layout"], 0)
                    else:
                        self.assertEqual(bt["disposition"], "rewritten")
                        self.assertFalse(bt["gap_closed_in_layout"])
                        self.assertGreater(bt["pmos_bodies_rewritten_to_vdd"], 0)
                        self.assertEqual(
                            bt["pmos_bodies_already_tied_in_layout"], 0)

    def test_latest_extraction_passes(self):
        """The regression that motivated #784: on what `_latest_report()`
        returns today the retired `pfet_bodies == {"vdd"}` check was False,
        so the script reported FAIL before any simulation result mattered."""
        for top in ("ADC_TOP", "ADC_BLOCK"):
            src = R._latest_report(top)
            core_text, rem = R.remediate(src.read_text(), top)
            nl = R.parse(core_text, top)
            with self.subTest(top=top, report=src.parent.name):
                retired = {R._mos_terminals(c)[3]
                           for c in nl.cards if R._is_mos(c) == "pfet"}
                self.assertNotEqual(
                    retired, {R.VDD_NET},
                    "terminal nets are no longer bare hub names -- if this "
                    "ever holds again the regression this test pins is gone")
                self.assertTrue(V.body_tie_result(core_text, rem, top)["holds"])


class BodyTieInvariantIsFalsifiable(unittest.TestCase):
    """Negative controls: the invariant must be able to FAIL."""

    def _latest_core(self, top: str = "ADC_TOP"):
        src = R._latest_report(top)
        return R.remediate(src.read_text(), top)

    def test_a_body_moved_off_vdd_fails(self):
        """Move one PMOS body onto another net -- a deleted tap, a broken
        strap, a cell drawn without one -- and the invariant must fail."""
        core_text, rem = self._latest_core()
        nl = R.parse(core_text, "ADC_TOP")
        card = next(c for c in nl.cards if R._is_mos(c) == "pfet")
        d, g, s, b = R._mos_terminals(card)
        card.tokens = [card.tokens[0], d, g, s, "$999", *card.tokens[5:]]
        bt = V.body_tie_result(core_text, rem, "ADC_TOP", nl=nl)
        self.assertFalse(bt["holds"])
        self.assertIn("$999", bt["pmos_body_nets_after"])

    def test_an_undispositioned_body_fails(self):
        """A body on `vdd` that neither disposition counted still fails:
        the partition has to add up to the PMOS card count."""
        core_text, rem = self._latest_core()
        rem.n_pmos_already_tied -= 1
        bt = V.body_tie_result(core_text, rem, "ADC_TOP")
        self.assertFalse(bt["holds"])
        self.assertEqual(bt["pmos_body_nets_after"], [R.VDD_NET])

    def test_no_pmos_cards_at_all_fails(self):
        """An empty parse is not a pass. (`remediate()` raises on such a
        netlist; this pins the invariant's own answer, independently.)"""
        core_text, rem = self._latest_core()
        nl = R.parse(core_text, "ADC_TOP")
        nl.cards = [c for c in nl.cards if R._is_mos(c) != "pfet"]
        self.assertFalse(V.body_tie_result(core_text, rem, "ADC_TOP", nl=nl)["holds"])


class RawBodyProbeIsGone(unittest.TestCase):
    """#784 removed the RAW-core floating-body probe: on a tapped extraction
    it filtered for `$<n>` body nets that no longer exist, so it ran a
    600 s-budget ngspice op whose result was empty by construction."""

    def test_probe_and_its_only_imports_are_removed(self):
        """Checked against the parsed module, not a substring scan: the
        docstring still *cites* the retired probe and its committed JSON
        key, which is the point -- the evidence outlives the code."""
        src = (PARA_DIR / "verify_remediation_dc.py").read_text()
        tree = ast.parse(src)

        defined = {n.name for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertNotIn("raw_body_nodes", defined)
        self.assertIn("body_tie_result", defined, "the replacement check")

        imported = {a.name for n in ast.walk(tree)
                    if isinstance(n, ast.Import) for a in n.names}
        for only_used_by_the_probe in ("re", "struct"):
            self.assertNotIn(only_used_by_the_probe, imported)

        # No executable reference to the probe or its result key survives.
        body = src.replace(ast.get_docstring(tree) or "", "")
        self.assertNotIn("raw_body_nodes", body)
        self.assertNotIn("raw_floating_pmos_body_nodes_v", body)

    def test_no_committed_extraction_has_an_anonymous_body_left(self):
        """Why the probe was dead rather than merely unused: its `$<n>` id
        filter cannot match on a tapped extraction."""
        for top in ("ADC_TOP", "ADC_BLOCK"):
            src = R._latest_report(top)
            nl = R.parse(src.read_text(), top)
            bodies = {R._hub(R._mos_terminals(c)[3])
                      for c in nl.cards if R._is_mos(c) == "pfet"}
            with self.subTest(top=top, report=src.parent.name):
                self.assertEqual(bodies, {R.VDD_NET})
                self.assertFalse([b for b in bodies if "$" in b])


if __name__ == "__main__":
    unittest.main()
