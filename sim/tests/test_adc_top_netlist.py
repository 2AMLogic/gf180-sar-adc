#!/usr/bin/env python3
"""The committed ADC-top netlist and issue #13's testbench suite must match
their generator.

    python3 -m unittest discover -s sim/tests -v

Same anti-drift argument as `test_sar_logic_netlist.py`, one level up:
`sim/harness/testbench.py` rejects `.include` in a testbench fragment, so each
of the three spec-line testbenches (`sim/adc-inl-dnl/`, `sim/adc-enob-fft/`,
`sim/adc-power/`) has to carry the whole converter inline. That is four copies
of the comparator, four of the SAR controller and four of the CDAC array. A
testbench that has quietly drifted from the design it claims to verify still
passes -- and certifies a circuit that is no longer in `design/`.

`design/adc-top/gen_adc_top.py` is the single source of truth and these tests
are the guard. They need neither ngspice nor the PDK, so they run on the
PDK-free CI path on every pull request.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "design" / "adc-top" / "gen_adc_top.py"

_spec = importlib.util.spec_from_file_location("gen_adc_top", GEN)
gen = importlib.util.module_from_spec(_spec)
sys.modules["gen_adc_top"] = gen
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

        for name in ("inl", "fft", "power"):
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

    def test_manifests_load_under_the_harness_loader(self):
        """A manifest the loader rejects is a testbench that cannot be run at
        all -- catch it here rather than at the start of a multi-hour sweep."""
        sys.path.insert(0, str(REPO / "sim"))
        from harness.testbench import load  # noqa: PLC0415

        for slug in ("adc-inl-dnl", "adc-enob-fft", "adc-power"):
            with self.subTest(experiment=slug):
                tb = load(REPO / "sim" / slug)
                self.assertEqual(tb.name, slug)
                self.assertTrue(tb.checks, f"{slug} asserts nothing")


class InlinedCopyTests(unittest.TestCase):
    """Every deck carries the SAME comparator, controller and array text."""

    def _decks(self) -> dict[str, str]:
        return {
            name: (REPO / gen.TARGETS[name][0]).read_text()
            for name in ("inl", "fft", "power")
        }

    def test_every_deck_carries_the_canonical_comparator(self):
        block = gen.comparator_block()
        for name, text in self._decks().items():
            with self.subTest(target=name):
                self.assertIn(block, text)

    def test_every_deck_carries_the_canonical_controller(self):
        block = gen.sar.library()
        for name, text in self._decks().items():
            with self.subTest(target=name):
                self.assertIn(block, text)

    def test_every_deck_carries_the_committed_adc_library(self):
        block = (REPO / "design" / "adc-top" / "adc_top.spice").read_text()
        for name, text in self._decks().items():
            with self.subTest(target=name):
                self.assertIn(block, text)


class ArraySizingTests(unittest.TestCase):
    """Sizing facts consumed from ratified records. A later edit to the
    generator must not silently move them."""

    def test_nine_switched_weights_and_a_terminating_unit(self):
        """DR-0011: 2^(N-1) = 512 unit positions per side, MSB free."""
        self.assertEqual(gen.WEIGHTS, [256, 128, 64, 32, 16, 8, 4, 2, 1])
        self.assertEqual(sum(gen.WEIGHTS) + 1, gen.N_UNIT_PER_SIDE)

    def test_track_mode_c_in_matches_the_ratified_input_structure_row(self):
        """README#target-specification Input-structure row: C_in = 8.827 pF
        per side, which is exactly 512 x C_u at spec/cdac-sizing-memo.md's
        C_u = 17.24 fF. If this drifts, the published drive contract
        (DR-0013's R_source x (C_pin + C_in) <= 30 ns) is wrong."""
        c_in_pf = gen.N_UNIT_PER_SIDE * gen.C_UNIT_FF / 1000.0
        self.assertAlmostEqual(c_in_pf, 8.827, places=3)

    def test_mim_density_law_inverts_correctly(self):
        """mim_side_um() must be the exact inverse of the measured density law
        C(s) = A s^2 + B s (devchar Sec 1.2) -- a sizing error here is a
        silent capacitance error in every weight of the array."""
        for c_ff in (gen.C_UNIT_FF, 16 * gen.C_UNIT_FF, 256 * gen.C_UNIT_FF):
            s = gen.mim_side_um(c_ff)
            self.assertAlmostEqual(gen.MIM_A * s * s + gen.MIM_B * s, c_ff, places=6)


class BottomPlateSamplingTests(unittest.TestCase):
    """DR-0014's topology, asserted on the generated text so that a later
    edit cannot revert the ratified sampling phase while every deck still
    simulates and every check still passes."""

    def _library(self) -> str:
        return gen.library()

    def test_each_cell_has_a_fourth_leg_driven_to_vin(self):
        """A fourth T-gate and its own local driver, alongside the existing
        V_cm / V_REF / GND legs -- DR-0014's Decision, per cell."""
        text = self._library()
        self.assertIn(
            ".subckt adc_cdac_cell top vin vref vcm vss vdd"
            " gn_in gn_rel gn_hi gn_lo",
            text,
        )
        cell = text.split(".subckt adc_cdac_cell")[1].split(".ends")[0]
        self.assertEqual(cell.count("adc_drv"), 4, cell)
        self.assertEqual(cell.count("adc_tgate wn="), 4, cell)
        self.assertIn("Xsi vin  bp gn_in  gp_in  vdd adc_tgate", cell)

    def test_the_array_side_carries_the_input_and_one_shared_leg_control(self):
        """`vin` and `sel_in` are ports of the side, and `sel_in` is ONE port
        rather than one per cell: all bottom plates sample together."""
        text = self._library()
        side = text.split(".subckt adc_cdac_side")[1].split(".ends")[0]
        self.assertIn("top vin vref vcm vss vdd sel_in", side.splitlines()[0])
        cells = [
            ln for ln in side.splitlines() if " adc_cdac_cell " in ln
        ]
        self.assertEqual(len(cells), len(gen.WEIGHTS))
        for ln in cells:
            self.assertEqual(ln.split().count("sel_in"), 1, ln)

    def test_a_top_plate_vcm_switch_exists_and_is_not_dummy_compensated(self):
        """DR-0014 adds one top-plate switch per side. It opens with its node
        at V_cm every time, so its injection is signal-independent and the
        DR-0013 dummies would only re-hang MOS capacitors on the node that
        record measured as 66 % of C_par."""
        text = self._library()
        self.assertIn(".subckt adc_tp_sw top vcm gn vdd vss", text)
        tp = text.split(".subckt adc_tp_sw")[1].split(".ends")[0]
        self.assertIn("adc_tgate ", tp)
        self.assertNotIn("adc_tgate_dum", tp)

    def test_the_converter_no_longer_carries_a_dedicated_sampling_switch(self):
        """The whole point: the input reaches the array through the cells'
        fourth legs, so no adc_tgate_dum is INSTANTIATED in any adc-* deck.
        The subckt stays defined because sim/top-plate-cpar/ still measures
        the superseded topology's load set."""
        for name in ("inl", "fft", "power"):
            text = (REPO / gen.TARGETS[name][0]).read_text()
            with self.subTest(target=name):
                instantiations = [
                    ln
                    for ln in text.splitlines()
                    if ln.lower().startswith("x") and "adc_tgate_dum" in ln
                ]
                self.assertEqual(instantiations, [])
                self.assertIn("adc_tp_sw", text)

    def test_both_sides_share_one_top_plate_switch_control(self):
        """Side-to-side skew of that switch is exactly the term bottom-plate
        sampling cannot cancel, so it must not be manufactured by routing two
        controls."""
        for name in ("inl", "fft", "power"):
            text = (REPO / gen.TARGETS[name][0]).read_text()
            with self.subTest(target=name):
                lines = [
                    ln
                    for ln in text.splitlines()
                    if ln.lower().startswith("x") and ln.endswith(" adc_tp_sw")
                ]
                self.assertEqual(len(lines), 2, lines)
                ctrl = {ln.split()[3] for ln in lines}
                self.assertEqual(len(ctrl), 1, lines)

    def test_the_error_node_stays_input_referred_under_the_inverted_residue(self):
        """DR-0014 makes d(top_p - top_n)/dV_in negative, so the input-referred
        error is (ideal - actual). If this silently flipped, every INL sign in
        the suite would flip with it and nothing would say so."""
        for name in ("inl", "fft", "power"):
            text = (REPO / gen.TARGETS[name][0]).read_text()
            with self.subTest(target=name):
                self.assertIn(
                    "bsee se_err 0 V = (v(se_di)-(v(se_topp)-v(se_topn)))/lsb",
                    text,
                )
                self.assertIn(
                    "bsedi se_di 0 V = v(se_vinn)-v(se_vinp)"
                    "+v(se_dacp)-v(se_dacn)",
                    text,
                )


class LinearityCodeSetTests(unittest.TestCase):
    """The INL/DNL code set must stay targeted at DR-0011's OWN array."""

    def test_probes_the_weight_256_sub_array_carry_from_both_sides(self):
        """The largest charge-division ratio this array forms is the weight-256
        sub-array MSB, i.e. transitions 255->256 and 767->768 -- NOT the
        mid-scale 511->512 a plain binary-weighted array would make worst.
        Both, and their immediate neighbours, must be probed."""
        for k in (255, 256, 257, 767, 768, 769):
            self.assertIn(k, gen.INL_TRANSITIONS)

    def test_probes_the_free_msb_transition_and_both_endpoints(self):
        for k in (511, 512, 513):
            self.assertIn(k, gen.INL_TRANSITIONS)
        self.assertEqual(gen.INL_TRANSITIONS[0], 1)
        self.assertEqual(gen.INL_TRANSITIONS[-1], 1023)

    def test_transitions_are_sorted_and_unique(self):
        self.assertEqual(
            gen.INL_TRANSITIONS, sorted(set(gen.INL_TRANSITIONS))
        )

    def test_dnl_pairs_are_adjacent_probed_transitions(self):
        for lo, hi in gen.INL_DNL_PAIRS:
            with self.subTest(pair=(lo, hi)):
                self.assertEqual(hi, lo + 1)
                self.assertIn(lo, gen.INL_TRANSITIONS)
                self.assertIn(hi, gen.INL_TRANSITIONS)

    def test_each_transition_is_read_at_the_trial_that_resolves_it(self):
        """Transition k is set by the first bit where k-1 and k differ. Trial 1
        is the free MSB (bit 9), trial 10 the LSB (bit 0)."""
        self.assertEqual(gen._inl_trial(512), 1)  # bit 9, the free MSB
        self.assertEqual(gen._inl_trial(256), 2)  # bit 8, weight 256
        self.assertEqual(gen._inl_trial(768), 2)  # bit 8 again, MSB = 1
        self.assertEqual(gen._inl_trial(128), 3)  # bit 7, weight 128
        self.assertEqual(gen._inl_trial(1), 10)  # bit 0, weight 1

    def test_manifest_declares_the_reduced_code_set_tag(self):
        ev = gen.inl_manifest()["evidence"]
        self.assertTrue(
            ev["linearity_method"].startswith("reduced-code-set-major-carry"),
            ev["linearity_method"],
        )

    def test_inl_and_dnl_claims_are_actually_checked(self):
        """`sim/README.md` requires the record to substantiate the spec line;
        that only happens if the manifest bounds the derived quantities."""
        checks = gen.inl_manifest()["checks"]
        for k in gen.INL_TRANSITIONS:
            self.assertIn(f"inl_t{k}_lsb", checks)
        for lo, hi in gen.INL_DNL_PAIRS:
            self.assertIn(f"dnl_t{lo}_t{hi}_lsb", checks)


class CoherentSamplingTests(unittest.TestCase):
    """The FFT deck's coherence is a property of two integers. Assert it,
    because `window = none` is only valid while it holds."""

    def test_cycle_count_is_coprime_to_the_record_length(self):
        self.assertEqual(math.gcd(gen.FFT_CYCLES, gen.FFT_N), 1)

    def test_record_length_is_a_power_of_two(self):
        self.assertEqual(gen.FFT_N & (gen.FFT_N - 1), 0)

    def test_input_is_near_nyquist(self):
        """The ratified ENOB/SFDR rows are specified at Nyquist; a
        comfortably-low-frequency input would not substantiate them."""
        f_in_over_nyquist = 2 * gen.FFT_CYCLES / gen.FFT_N
        self.assertGreater(f_in_over_nyquist, 0.9)
        self.assertLess(f_in_over_nyquist, 1.0)

    def test_input_frequency_equals_bin_times_fs_over_n(self):
        f_s = 1e9 / gen.CONV_NS
        self.assertAlmostEqual(
            gen.fft_input_hz(), gen.FFT_CYCLES * f_s / gen.FFT_N, places=6
        )

    def test_manifest_declares_window_none_and_the_matching_bin(self):
        ev = gen.fft_manifest()["evidence"]
        self.assertEqual(ev["fft_window"], "none")
        self.assertEqual(ev["fft_n"], gen.FFT_N)
        self.assertEqual(ev["fft_bin"], gen.FFT_CYCLES)
        self.assertAlmostEqual(ev["fft_fs_hz"], 1e9 / gen.CONV_NS, places=3)

    def test_one_sample_is_exported_per_conversion(self):
        m = gen.fft_manifest()["measure"]
        exported = [k for k in m if k.startswith("code_s")]
        self.assertEqual(len(exported), gen.FFT_N)


class PowerBreakdownTests(unittest.TestCase):
    """The power row is a per-block claim, not one lumped number."""

    def test_every_block_is_measured_separately(self):
        m = gen.power_manifest()["measure"]
        for blk in ("cmp", "cdac", "trk", "ref", "vcm"):
            with self.subTest(block=blk):
                self.assertTrue(
                    any(k.startswith(f"p_{blk}_") for k in m),
                    f"no per-block power measurement for {blk}",
                )

    def test_the_total_is_bounded_at_every_input_level(self):
        """MCS switching energy is code-dependent, so one level is one point of
        a curve -- the 1 mW claim has to hold at all of them."""
        checks = gen.power_manifest()["checks"]
        bounded = [k for k in checks if k.startswith("p_total_")]
        self.assertEqual(len(bounded), len(gen.PWR_LEVELS))
        for k in bounded:
            self.assertEqual(checks[k]["max"], 1000.0)


class EvidenceConformanceTests(unittest.TestCase):
    """`sim/README.md`'s ADC extension fields are validated by the harness;
    catch a non-conforming manifest here instead of after a long sweep."""

    def test_evidence_blocks_validate(self):
        sys.path.insert(0, str(REPO / "sim"))
        from harness.evidence import from_manifest  # noqa: PLC0415

        for name, manifest in (
            ("adc-inl-dnl", gen.inl_manifest()),
            ("adc-enob-fft", gen.fft_manifest()),
            ("adc-power", gen.power_manifest()),
        ):
            with self.subTest(experiment=name):
                from_manifest(manifest["evidence"]).validate()

    def test_committed_manifests_are_valid_json_and_name_themselves(self):
        for slug, target in (
            ("adc-inl-dnl", "inl-json"),
            ("adc-enob-fft", "fft-json"),
            ("adc-power", "power-json"),
        ):
            with self.subTest(experiment=slug):
                data = json.loads((REPO / gen.TARGETS[target][0]).read_text())
                self.assertEqual(data["name"], slug)

    def test_capacitor_corners_are_used_not_the_mos_default(self):
        """sim/harness/README.md: a MOS-only sweep leaves both capacitor
        families typical, and every claim in this suite rides on the CDAC."""
        for manifest in (
            gen.inl_manifest(),
            gen.fft_manifest(),
            gen.power_manifest(),
        ):
            with self.subTest(experiment=manifest["name"]):
                self.assertEqual(manifest["corners"], ["cdac"])


if __name__ == "__main__":
    unittest.main()
