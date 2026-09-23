#!/usr/bin/env python3
"""The V_cm drive-network variant must change the drive network and nothing else.

    python3 -m unittest discover -s sim/tests -t sim/tests

`sim/vcm-drive-impedance/gen_vcm_variant.py` patches one line of a ratified
testbench deck -- the ideal `vcms vcmn 0 dc {vcm}` source -- and replaces it
with DR-0026's real R‖L + `C_dec` network. Everything the campaign concludes
(issue #260's sensitivity sweep, issue #358's full-PVT re-run) rests on
"the two decks differ by exactly that network", which is a *checkable*
statement, not an assurance in a README. These tests are the check. They need
neither ngspice nor the PDK, so they run on the PDK-free CI path.

The last test here exists because of a real, expensive failure. The generator
replaces the *instance* `vcms`, and `sim/adc-power/testbench/tb.json` measures
the V_cm supply current as `meas tran ivcmf000 AVG i(vcms)`. The first version
of the generator therefore produced an `adc-power` variant in which every one
of the 27 PVT points failed with ``no such vector as 'i(vcms)'`` -- discovered
only after a half-hour corner sweep had run to completion and scored 0/27. A
generated deck that deletes a node or instance its own manifest measures is a
defect CI can see in milliseconds, and now does.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SWEEP = REPO / "sim" / "vcm-drive-impedance"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


variant = _load("gen_vcm_variant", SWEEP / "gen_vcm_variant.py")

#: Every deck in this repo that sources V_cm from an ideal supply. The
#: campaign in `sim/vcm-full-pvt/` targets these; a new one that grows the
#: anchor line should be added here so it is covered too.
TARGET_DECKS = (
    "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice",
    "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice",
    "sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice",
    "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice",
    "sim/adc-power/testbench/tb_adc_power.spice",
    "sim/adc-power/testbench/tb_adc_power_extracted.spice",
    "sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice",
)

Z_OHM = 220.0
C_DEC_NF = 40.0


class AnchorTests(unittest.TestCase):
    def test_every_target_deck_carries_exactly_one_anchor(self):
        """One hit, in every deck the campaign targets. A deck that grows a
        second V_cm source, or renames the first, must fail here rather than
        be silently half-patched."""
        for rel in TARGET_DECKS:
            with self.subTest(deck=rel):
                text = (REPO / rel).read_text()
                self.assertEqual(text.count(variant.VCM_LINE), 1)

    def test_a_deck_without_the_anchor_is_a_loud_failure(self):
        """Pointing --deck at a deck with no ideal V_cm source must raise,
        never return an unpatched copy that would run and look fine."""
        with self.assertRaises(SystemExit):
            variant.variant_deck(
                Z_OHM, C_DEC_NF,
                deck=REPO / "sim/comparator-offset-mc/testbench/tb_offset_mc.spice",
            )

    def test_a_missing_deck_is_a_loud_failure(self):
        with self.assertRaises(SystemExit):
            variant.variant_deck(Z_OHM, C_DEC_NF, deck=REPO / "sim/nope.spice")


class SubstitutionTests(unittest.TestCase):
    def test_the_variant_differs_from_its_source_only_at_the_anchor(self):
        """The isolation claim itself. Reconstructing the source deck by
        collapsing the generated block back to the one anchor line must give
        the source deck back byte-for-byte -- so no other line moved."""
        for rel in TARGET_DECKS:
            with self.subTest(deck=rel):
                src = (REPO / rel).read_text()
                out = variant.variant_deck(Z_OHM, C_DEC_NF, deck=REPO / rel)
                head, _, tail = src.partition(variant.VCM_LINE)
                self.assertTrue(out.startswith(head), rel)
                self.assertTrue(out.endswith(tail), rel)
                block = out[len(head):len(out) - len(tail)]
                # The replaced region is the generated network and nothing
                # else, and the ideal source line is gone from it.
                self.assertNotIn(variant.VCM_LINE, out, rel)
                self.assertIn("V_cm drive network", block)
                self.assertIn("cvcm vcmn 0 ", block)

    def test_the_network_carries_the_requested_values(self):
        out = variant.variant_deck(
            Z_OHM, C_DEC_NF, deck=REPO / TARGET_DECKS[0])
        self.assertIn(f"rvcm vcmi vcmn {Z_OHM:.6f}", out)
        self.assertIn(f"cvcm vcmn 0 {C_DEC_NF:.6f}n", out)
        # L is set so R‖L corners at the bit clock -- the same derivation
        # DR-0002's V_REF network uses, which --verify-vref-corner checks
        # against the committed deck.
        self.assertIn(f"lvcm vcmi vcmn {variant.l_for_corner(Z_OHM):.9e}", out)

    def test_zero_impedance_is_the_degenerate_ideal_case(self):
        """Z_vcm = 0 is the ideal-source control point the sweep's own
        `ideal` arm uses; L must not be computed from a zero R."""
        out = variant.variant_deck(0.0, C_DEC_NF, deck=REPO / TARGET_DECKS[0])
        self.assertIn("rvcm vcmi vcmn 0.000000", out)
        self.assertIn("lvcm vcmi vcmn 0.000000000e+00", out)


class MeasuredInstanceSurvivalTests(unittest.TestCase):
    """A generated deck must not delete an instance its own manifest measures.

    This is the regression test for the `adc-power` failure described in the
    module docstring: 27/27 points lost to ``no such vector as 'i(vcms)'``
    because the substitution removed the very instance `tb.json` measures
    through.
    """

    def test_manifest_measured_vcm_source_survives_the_substitution(self):
        for rel in TARGET_DECKS:
            manifest = (REPO / rel).parent / "tb.json"
            if not manifest.is_file():
                continue
            measured = "i(vcms)" in manifest.read_text()
            with self.subTest(deck=rel, measured=measured):
                out = variant.variant_deck(Z_OHM, C_DEC_NF, deck=REPO / rel)
                if measured:
                    # The name must still resolve, as a 0 V ammeter in series
                    # with the real network -- i.e. the current the external
                    # V_cm pin delivers.
                    self.assertIn("\nvcms ", out, rel)
                    self.assertIn(" dc 0\n", out, rel)
                else:
                    # And it must NOT be emitted where nothing measures it:
                    # every variant that predates the ammeter has to stay
                    # byte-identical, or the records it already minted stop
                    # being reproducible from this script.
                    self.assertNotIn("\nvcms ", out, rel)

    def test_adc_power_is_actually_one_of_the_measured_decks(self):
        """Guards the test above against silently becoming vacuous if the
        manifest stops measuring i(vcms)."""
        manifest = json.loads(
            (REPO / "sim/adc-power/testbench/tb.json").read_text())
        measures = json.dumps(manifest.get("measures", manifest))
        self.assertIn("i(vcms)", measures)

    def test_every_node_the_ammeter_introduces_is_connected(self):
        """The ammeter adds one internal node; a typo that leaves it dangling
        would float the whole V_cm drive and is not otherwise visible without
        running ngspice."""
        out = variant.variant_deck(
            Z_OHM, C_DEC_NF,
            deck=REPO / "sim/adc-power/testbench/tb_adc_power.spice")
        lines = [ln for ln in out.splitlines()
                 if ln.startswith(("vcmi ", "vcms ", "rvcm ", "lvcm ", "cvcm "))]
        joined = "\n".join(lines)
        self.assertIn("vcms vcmi vcmd dc 0", joined)
        self.assertIn("rvcm vcmd vcmn", joined)
        self.assertIn("lvcm vcmd vcmn", joined)
        # `vcmd` is used by exactly three elements: the ammeter and the R‖L.
        self.assertEqual(sum("vcmd" in ln for ln in lines), 3)


class VrefCornerTests(unittest.TestCase):
    def test_the_rl_corner_derivation_matches_the_committed_vref_network(self):
        """`--verify-vref-corner` in assertion form: the L this generator
        picks for a given R is the same rule DR-0002's committed V_REF
        network already uses, so the V_cm network is that pattern and not a
        new one invented here."""
        self.assertEqual(variant.main(["--verify-vref-corner"]), 0)


class CliTests(unittest.TestCase):
    def test_out_writes_the_same_text_the_api_returns(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "v.spice"
            rc = variant.main([
                "--deck", str(REPO / TARGET_DECKS[0]),
                "--z-ohm", str(Z_OHM), "--c-dec-nf", str(C_DEC_NF),
                "--out", str(out),
            ])
            self.assertEqual(rc, 0)
            self.assertEqual(
                out.read_text(),
                variant.variant_deck(Z_OHM, C_DEC_NF,
                                     deck=REPO / TARGET_DECKS[0]),
            )


if __name__ == "__main__":
    unittest.main()
