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

`SignConventionTests` exists because of the *second* failure of the same kind
(issue #395): the ammeter that fix introduced was wired with its terminals
reversed relative to the source line it replaces, so `i(vcms)` came back
sign-flipped and every `p_total_*` in the patched arm was published understated
by `2 x |p_vcm|`. That one scored 27/27 PASS -- `p_vcm_*` carries no bound --
so only a cross-arm comparison caught it, weeks later. Keeping the measured
*quantity* meaningful, not just the vector name resolvable, is also something
CI can see in milliseconds.
"""

from __future__ import annotations

import hashlib
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
                    # the ammeter is a real circuit element, so adding one to
                    # a deck that does not need it would change that deck's
                    # netlist for no reason. This assertion checks only the
                    # ammeter's absence; the stronger byte-level invariant --
                    # that the decks issue #260 already minted records for
                    # regenerate to the sha256 those records pin -- is checked
                    # by `Issue260PinTests` below, which is where that claim
                    # belongs because it is a claim about exact bytes.
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
        self.assertIn("vcms vcmd vcmi dc 0", joined)
        self.assertIn("rvcm vcmd vcmn", joined)
        self.assertIn("lvcm vcmd vcmn", joined)
        # `vcmd` is used by exactly three elements: the ammeter and the R‖L.
        self.assertEqual(sum("vcmd" in ln for ln in lines), 3)


#: The deck whose sibling manifest measures `i(vcms)`, i.e. the one deck in
#: the campaign that gets the ammeter at all.
AMMETER_DECK = "sim/adc-power/testbench/tb_adc_power.spice"


def _element(deck_text: str, name: str) -> list[str]:
    """The tokens of the single SPICE element instance called `name`."""
    hits = [ln.split() for ln in deck_text.splitlines()
            if ln.split() and ln.split()[0] == name]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one {name!r} element, found {len(hits)}")
    return hits[0]


class SignConventionTests(unittest.TestCase):
    """The ammeter must preserve `i(vcms)`'s SIGN, not merely its name.

    Issue #395. `MeasuredInstanceSurvivalTests` above pins that the instance
    `vcms` survives the substitution -- that was the #358-era fix for
    ``no such vector as 'i(vcms)'``. It says nothing about which way round
    the surviving source is wired, and the first version of the ammeter was
    wired backwards:

        baseline  vcms vcmn 0    dc {vcm}    <- '+' on the ISLAND node
        ammeter   vcms vcmi vcmd dc 0        <- '+' on the SOURCE side  (WRONG)

    ngspice reports `i(vsrc)` as the current INTO the source's positive
    terminal (`sim/adc-rail-current/testbench/tb.json` states this in as many
    words: *"a source DELIVERING current reads negative"*), and
    `sim/adc-power/testbench/tb.json` derives `p_vcm = -ivcm*(vddm/2)*1e6`
    on exactly that convention. Reversing the terminals therefore reversed
    `i(vcms)`, which flipped `p_vcm`'s sign -- and because `p_total` sums the
    same `ivcm` term inside the same negation, understated every `p_total_*`
    in the patched arm by `2 x |p_vcm|` (~24-50 uW per point at f000).

    Nothing caught it: `p_vcm_*` carries no bound in the manifest, so all 27
    points still scored PASS while publishing wrong totals. These tests are
    the check that would have. They are structural -- the ammeter's polarity
    is derived from what its nodes are *connected to*, not compared against a
    hardcoded node name -- so they keep holding if the internal node is ever
    renamed.
    """

    def test_the_baseline_ideal_source_is_island_side_positive(self):
        """The orientation the ammeter has to match, read off the anchor line
        itself rather than asserted from memory."""
        name, plus, minus, kind, _value = variant.VCM_LINE.split()
        self.assertEqual(name, "vcms")
        self.assertEqual(kind, "dc")
        # '+' on the V_cm island the converter actually sees, '-' on ground:
        # the source DELIVERS into `vcmn`, so `i(vcms)` reads negative and
        # `p_vcm = -i*v` reads positive.
        self.assertEqual(plus, "vcmn")
        self.assertEqual(minus, "0")

    def test_the_ammeter_is_a_zero_volt_source_between_two_distinct_nodes(self):
        out = variant.variant_deck(
            Z_OHM, C_DEC_NF, deck=REPO / AMMETER_DECK)
        name, plus, minus, kind, value = _element(out, "vcms")
        self.assertEqual(name, "vcms")
        self.assertEqual((kind, value), ("dc", "0"))
        self.assertNotEqual(plus, minus)

    def test_the_ammeter_positive_terminal_faces_the_island_not_the_source(self):
        """The regression itself, derived from connectivity.

        The ammeter sits between the ideal source's node and the R‖L network
        that feeds the island node `vcmn`. Its '+' terminal must be the one on
        the ISLAND side -- the node `rvcm`/`lvcm` hang off -- matching the
        baseline line it replaces. Against the flipped orientation
        (`vcms vcmi vcmd dc 0`) this assertion fails.
        """
        out = variant.variant_deck(
            Z_OHM, C_DEC_NF, deck=REPO / AMMETER_DECK)
        _, plus, minus, _, _ = _element(out, "vcms")
        ideal_src = _element(out, "vcmi")          # vcmi <node> 0 dc {vcm}
        r_nodes = set(_element(out, "rvcm")[1:3])  # rvcm <a> <b> <ohms>
        l_nodes = set(_element(out, "lvcm")[1:3])
        island = set(_element(out, "cvcm")[1:3]) - {"0"}   # cvcm vcmn 0 <F>

        # The R and the L are the same two-node network, and it reaches the
        # island node the converter's V_cm pin actually is.
        self.assertEqual(r_nodes, l_nodes)
        self.assertTrue(island <= r_nodes, "R‖L does not reach the island node")

        drive_side = (r_nodes - island).pop()   # the node facing the ammeter
        source_side = ideal_src[1]              # the ideal source's own node

        self.assertEqual(
            plus, drive_side,
            "the ammeter's '+' terminal must face the drive network / island, "
            "the same way the ideal source line it replaces does -- otherwise "
            "i(vcms) comes back sign-flipped and p_vcm / p_total are wrong "
            "(issue #395)")
        self.assertEqual(minus, source_side)

    def test_the_manifest_still_derives_p_vcm_on_the_negating_convention(self):
        """Guards the test above against going vacuous.

        The polarity is only 'correct' relative to a stated convention. If
        `tb.json` ever stopped negating `ivcm`, the right ammeter orientation
        would be the other one, and this test says so out loud instead of
        letting the assertion above silently enforce a stale rule.
        """
        manifest = json.loads(
            (REPO / "sim/adc-power/testbench/tb.json").read_text())
        for level in ("f000", "f025", "f050", "f075", "f100"):
            with self.subTest(level=level):
                self.assertEqual(
                    manifest["measure"][f"p_vcm_{level}_uw"],
                    f"-ivcm{level}*(vddm/2)*1e6")
                self.assertTrue(
                    manifest["measure"][f"p_total_{level}_uw"].startswith("-("))
                self.assertIn(
                    f"ivcm{level}*(vddm/2)",
                    manifest["measure"][f"p_total_{level}_uw"])

    def test_the_repo_states_the_convention_this_polarity_is_derived_from(self):
        """The convention itself is not invented here: it is written down in
        `sim/adc-rail-current/testbench/tb.json`, and this is the citation."""
        rail = (REPO / "sim/adc-rail-current/testbench/tb.json").read_text()
        self.assertIn("current INTO the source's positive", rail)
        self.assertIn("a source DELIVERING current reads negative", rail)


class Issue260PinTests(unittest.TestCase):
    """The decks issue #260 already minted records for must keep regenerating
    to the sha256 those records pin.

    `sim/vcm-drive-impedance/testbench/` holds no committed `.spice` deck --
    the variants are generated at run time -- so a reader reproducing those
    three records has exactly two anchors: the frozen
    `netlist-snapshots/<record-id>.spice` copy, and the `Testbench netlist
    sha256` the record pins. Both are *bytes*, which means even a comment-only
    edit to the header this generator writes breaks them.

    That is not hypothetical: issue #358's `--deck` work reworded that header
    and added a `Source deck:` line, which moved the 220 ohm point from
    `b76e7c67...` to `a56faec6...` while the PR body asserted the pins were
    intact. Prose cannot hold this invariant; this test can.

    If you need to change the header text, you are changing a published
    artifact: re-mint those records (and the snapshots) rather than updating
    the constants below.
    """

    #: (Z_vcm in ohms, sha256) from the `Testbench netlist sha256` line of the
    #: record named alongside. C_dec = 40 nF for both.
    PINS = (
        # sim/vcm-drive-impedance/records/20260825-163251-cb36f0a.md
        (220.0, "b76e7c675ce76b13ed2c8e7ce46224c49263282445ea5b27dedbc648e8da5a05"),
        # sim/vcm-drive-impedance/records/20260825-163508-64203b5.md
        (1100.0, "9efd4111e1a814675263d0c06afaa321dde2c5e627a1751b171fa9fec539dcba"),
    )

    def test_issue_260_netlist_sha256_pins_still_reproduce(self):
        for z_ohm, want in self.PINS:
            with self.subTest(z_ohm=z_ohm):
                text = variant.variant_deck(z_ohm, C_DEC_NF)
                got = hashlib.sha256(text.encode()).hexdigest()
                self.assertEqual(
                    got, want,
                    f"the default-deck variant at Z_vcm = {z_ohm:g} ohm no "
                    f"longer reproduces the sha256 pinned in "
                    f"sim/vcm-drive-impedance/records/. Regenerating it and "
                    f"diffing against the matching netlist-snapshots/*.spice "
                    f"will show what moved.",
                )

    def test_the_pins_are_the_ones_the_records_actually_carry(self):
        """Guards the test above against drifting into a self-referential
        check if someone updates the constants without touching the records."""
        records = {
            220.0: "20260825-163251-cb36f0a",
            1100.0: "20260825-163508-64203b5",
        }
        for z_ohm, want in self.PINS:
            with self.subTest(z_ohm=z_ohm):
                body = (SWEEP / "records" / f"{records[z_ohm]}.md").read_text()
                self.assertIn(f"Testbench netlist sha256: `{want}`", body)

    def test_the_ideal_arm_is_the_unmodified_committed_deck(self):
        """Issue #260's Z_vcm = 0 record pins the baseline deck itself, not a
        generated variant, so that pin is checked directly against the file."""
        pin = "881bdef36aa084b84edbd267289652ad08fa7470fae6d37d1fed9c5dfa74c560"
        got = hashlib.sha256(variant.BASELINE_DECK.read_bytes()).hexdigest()
        self.assertEqual(got, pin)
        body = (SWEEP / "records" / "20260825-162620-e09a2d0.md").read_text()
        self.assertIn(f"Testbench netlist sha256: `{pin}`", body)


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
