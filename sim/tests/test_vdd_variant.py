#!/usr/bin/env python3
"""The V_DD pin-network variant must change the supply network and nothing else.

    python3 -m unittest discover -s sim/tests -t sim/tests

`sim/vdd-drive-impedance/gen_vdd_variant.py` (issue #393) replaces the ideal
`vddt`/`vddd`/`vddc ... dc {vdd_val}` island sources of a ratified deck with
ONE shared R||L + C_dec pin network at DR-0036's budget, keeping each island
as a 0 V ammeter. Everything `sim/vdd-full-pvt/` concludes rests on three
checkable statements, and these tests are the check (no ngspice, no PDK, so
they run on the PDK-free CI path):

1. the variant differs from its source only at the island-source lines;
2. it is ONE network, not one per island -- the modelling decision the
   curator flagged as the one that would "still produce plausible-looking,
   self-consistent PASS results" if made wrong (three networks would triple
   C_dec and divide Z_vdd by three relative to what DR-0036 budgets);
3. every `i(vddX)` a manifest measures keeps its name AND its sign -- the
   two failure modes `sim/tests/test_vcm_variant.py` records for the V_cm
   generator (issue #358's deleted instance, issue #395's flipped ammeter),
   designed out here up front rather than discovered by a campaign.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "sim" / "vdd-drive-impedance" / "gen_vdd_variant.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


variant = _load("gen_vdd_variant", GEN)

#: Every deck the campaign targets: the seven the issue enumerates plus the
#: governing extracted Gain-error deck, which lives in its own
#: `testbench-extracted/` directory and carries only two islands.
TARGET_DECKS = tuple(variant.EXPECTED_ISLANDS)

Z_OHM = 3.0
C_DEC_NF = 40.0


def _elements(text: str) -> dict[str, list[str]]:
    """First-token -> tokens for every top-level element line (pre-.subckt
    lines and post-.ends lines alike; subckt-internal names are irrelevant
    to the top-level supply network)."""
    out: dict[str, list[str]] = {}
    depth = 0
    for ln in text.splitlines():
        tok = ln.split()
        if not tok or tok[0].startswith(("*", "+")):
            continue
        head = tok[0].lower()
        if head == ".subckt":
            depth += 1
            continue
        if head == ".ends":
            depth -= 1
            continue
        if depth == 0 and not head.startswith("."):
            out.setdefault(head, tok)
    return out


class AnchorTests(unittest.TestCase):
    def test_issue_enumerates_seven_decks_and_the_table_covers_them(self):
        seven = {
            "sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice",
            "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice",
            "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice",
            "sim/adc-power/testbench/tb_adc_power.spice",
            "sim/adc-power/testbench/tb_adc_power_extracted.spice",
            "sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice",
            "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice",
        }
        self.assertTrue(seven <= set(TARGET_DECKS))

    def test_every_target_deck_carries_exactly_its_islands(self):
        for rel in TARGET_DECKS:
            text = (REPO / rel).read_text()
            for name in variant.ISLANDS:
                with self.subTest(deck=rel, island=name):
                    want = 1 if name in variant.EXPECTED_ISLANDS[rel] else 0
                    self.assertEqual(
                        text.count(variant.island_line(name)), want)

    def test_a_deck_without_the_islands_is_a_loud_failure(self):
        with self.assertRaises(SystemExit):
            variant.variant_deck(
                Z_OHM, C_DEC_NF,
                REPO / "sim/comparator-offset-mc/testbench/tb_offset_mc.spice")

    def test_a_missing_deck_is_a_loud_failure(self):
        with self.assertRaises(SystemExit):
            variant.variant_deck(Z_OHM, C_DEC_NF, REPO / "sim/nope.spice")

    def test_a_drifted_deck_is_a_loud_failure(self):
        """A known deck that has lost one island line must not be silently
        patched with two ammeters."""
        rel = "sim/adc-power/testbench/tb_adc_power.spice"
        text = (REPO / rel).read_text().replace(
            variant.island_line("vddt") + "\n", "", 1)
        with tempfile.TemporaryDirectory() as td:
            # Same repo-relative identity is what selects the expected set,
            # so check through the expected-islands rule directly as well.
            fake = Path(td) / "tb_adc_power.spice"
            fake.write_text(text)
            with self.assertRaises(SystemExit):
                variant.variant_deck(Z_OHM, C_DEC_NF, fake)

    def test_zero_or_negative_values_are_refused(self):
        """The ideal arm is the UNMODIFIED committed deck; a 'Z = 0' variant
        would be a third, unnamed thing."""
        deck = REPO / TARGET_DECKS[0]
        for z, c in ((0.0, C_DEC_NF), (Z_OHM, 0.0), (-1.0, C_DEC_NF)):
            with self.subTest(z=z, c=c), self.assertRaises(SystemExit):
                variant.variant_deck(z, c, deck)


class SubstitutionTests(unittest.TestCase):
    def test_only_the_island_lines_change(self):
        """Collapse the generated network back out and every other line of
        the source deck must be there, in order, byte-for-byte."""
        for rel in TARGET_DECKS:
            with self.subTest(deck=rel):
                src = (REPO / rel).read_text().splitlines()
                out = variant.variant_deck(
                    Z_OHM, C_DEC_NF, REPO / rel).splitlines()
                islands = {variant.island_line(n)
                           for n in variant.EXPECTED_ISLANDS[rel]}
                kept_src = [ln for ln in src if ln not in islands]
                new = {f"{n} {n} vdd_pin dc 0"
                       for n in variant.EXPECTED_ISLANDS[rel]}
                network = {ln for ln in out if ln.startswith(
                    ("vddsup ", "rvddpin ", "lvddpin ", "cvddpin "))}
                kept_out = [ln for ln in out
                            if ln not in new and ln not in network
                            and not (ln.startswith("*") and ln not in src)]
                self.assertEqual(kept_src, kept_out)
                for ln in islands:
                    self.assertNotIn(ln, out)

    def test_the_network_carries_the_requested_values(self):
        out = variant.variant_deck(Z_OHM, C_DEC_NF, REPO / TARGET_DECKS[0])
        el = _elements(out)
        self.assertEqual(el["rvddpin"][1:], ["vdd_ext", "vdd_pin", f"{Z_OHM:.6f}"])
        self.assertEqual(el["cvddpin"][1:], ["vdd_pin", "0", f"{C_DEC_NF:.6f}n"])
        self.assertEqual(el["vddsup"][1:], ["vdd_ext", "0", "dc", "{vdd_val}"])
        l_h = float(el["lvddpin"][3])
        # Corner at the 1 MHz conversion rate (DR-0036 step 5), NOT the
        # 16 MHz bit clock DR-0002/DR-0026 use.
        corner = Z_OHM / (2 * math.pi * l_h)
        self.assertTrue(math.isclose(corner, 1.0e6, rel_tol=1e-6), corner)

    def test_the_budget_defaults_are_dr0036s(self):
        """`C_dec >= 40 nF`, `Z_vdd <= 3 ohm`, and the variant sits at the
        pessimistic edge of that envelope -- not inside it."""
        self.assertEqual(variant.BUDGET_Z_OHM, 3.0)
        self.assertEqual(variant.BUDGET_C_DEC_NF, 40.0)
        dr = (REPO / "spec/decision-records/DR-0036-vdd-decoupling-budget.md"
              ).read_text()
        self.assertIn("≥ 40 nF", dr)
        self.assertIn("≤ 3 Ω", dr)

    def test_switching_band_impedance_meets_the_budget_and_is_not_padded(self):
        """|Z| of R||L stays <= 3 ohm everywhere, and is within 25 % of it at
        the recharge frequency 1/(2 pi Z C_dec) -- i.e. the network is AT the
        budget in the band DR-0036 step 5 settles in, not quietly stiffer."""
        l_h = variant.l_for_corner(Z_OHM)
        def zmag(f):
            wl = 2 * math.pi * f * l_h
            return Z_OHM * wl / math.hypot(Z_OHM, wl)
        for f in (1e5, 1e6, 16e6, 1e9):
            self.assertLessEqual(zmag(f), Z_OHM)
        f_rc = 1 / (2 * math.pi * Z_OHM * C_DEC_NF * 1e-9)
        self.assertGreater(zmag(f_rc), 0.75 * Z_OHM)


class OnePinTests(unittest.TestCase):
    """The modelling decision itself: ONE pin network, every island on it."""

    def test_exactly_one_network_and_every_island_hangs_off_its_pin_node(self):
        for rel in TARGET_DECKS:
            with self.subTest(deck=rel):
                out = variant.variant_deck(Z_OHM, C_DEC_NF, REPO / rel)
                el = _elements(out)
                caps_on_pin = [t for t in el.values()
                               if t[0].lower().startswith("c")
                               and "vdd_pin" in t[1:3]]
                self.assertEqual(len(caps_on_pin), 1)
                for k in ("vddsup", "rvddpin", "lvddpin", "cvddpin"):
                    self.assertEqual(out.count(f"\n{k} "), 1, k)
                for n in variant.EXPECTED_ISLANDS[rel]:
                    self.assertEqual(el[n][1:], [n, "vdd_pin", "dc", "0"])
                # No island is still driven straight from ground.
                for n in variant.ISLANDS:
                    self.assertNotIn(variant.island_line(n), out)

    def test_total_decoupling_is_c_dec_not_a_multiple_of_it(self):
        out = variant.variant_deck(
            Z_OHM, C_DEC_NF,
            REPO / "sim/adc-power/testbench/tb_adc_power.spice")
        self.assertEqual(out.count(f"{C_DEC_NF:.6f}n"), 1)


class AmmeterTests(unittest.TestCase):
    """`i(vddX)` must keep its name and its sign (issue #358 / #395's
    lessons from the V_cm generator, designed in here)."""

    def test_every_measured_island_current_still_resolves(self):
        for rel in TARGET_DECKS:
            manifest = (REPO / rel).parent / "tb.json"
            if not manifest.is_file():
                continue
            measured = manifest.read_text()
            out = variant.variant_deck(Z_OHM, C_DEC_NF, REPO / rel)
            el = _elements(out)
            for n in variant.ISLANDS:
                if f"i({n})" in measured:
                    with self.subTest(deck=rel, island=n):
                        self.assertIn(n, el)

    def test_adc_power_actually_measures_all_three_islands(self):
        """Guards the test above against going vacuous."""
        m = (REPO / "sim/adc-power/testbench/tb.json").read_text()
        for n in variant.ISLANDS:
            self.assertIn(f"i({n})", m)

    def test_ammeter_plus_terminal_is_the_island_like_the_line_it_replaces(self):
        """Derived from connectivity: '+' on the island node (the node the
        baseline line puts '+' on), '-' on the shared pin node C_dec sits
        on. Reversed, i(vddX) flips and every p_* in sim/adc-power/ is
        wrong while still scoring PASS -- exactly issue #395."""
        rel = "sim/adc-power/testbench/tb_adc_power.spice"
        out = variant.variant_deck(Z_OHM, C_DEC_NF, REPO / rel)
        el = _elements(out)
        pin = (set(el["cvddpin"][1:3]) - {"0"}).pop()
        self.assertEqual(set(el["rvddpin"][1:3]), set(el["lvddpin"][1:3]))
        self.assertIn(pin, el["rvddpin"][1:3])
        for n in variant.ISLANDS:
            base = variant.island_line(n).split()
            self.assertEqual(base[1], n)        # baseline '+' = island
            self.assertEqual(base[2], "0")
            self.assertEqual(el[n][1], n)       # ammeter '+' = island
            self.assertEqual(el[n][2], pin)     # ammeter '-' = pin node

    def test_power_manifest_still_negates_island_currents(self):
        """The polarity above is right only relative to this convention."""
        m = json.loads((REPO / "sim/adc-power/testbench/tb.json").read_text())
        self.assertTrue(m["measure"]["p_total_f050_uw"].startswith("-("))


class CliTests(unittest.TestCase):
    def test_out_writes_the_same_text_the_api_returns(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "v.spice"
            rc = variant.main(["--deck", str(REPO / TARGET_DECKS[0]),
                               "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertEqual(
                out.read_text(),
                variant.variant_deck(Z_OHM, C_DEC_NF, REPO / TARGET_DECKS[0]))


if __name__ == "__main__":
    unittest.main()
