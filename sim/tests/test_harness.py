#!/usr/bin/env python3
"""Unit tests for the PVT harness. No PDK and no ngspice required.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import corners, evidence, report, runner, testbench  # noqa: E402
from harness.pdk import MIM_STACK_BY_VARIANT, Pdk, UnknownVariant  # noqa: E402


def fake_pdk(root: Path, variant: str | None = None) -> Pdk:
    (root / "libs.tech" / "ngspice").mkdir(parents=True, exist_ok=True)
    (root / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    (root / "libs.tech" / "ngspice" / "design.ngspice").write_text("* fake\n")
    (root / "SOURCES").write_text("open_pdks deadbeef\n")
    return Pdk(path=root, variant=variant or root.name, source="test")


class CornerTests(unittest.TestCase):
    def test_pvt_axes_match_the_mandated_grid(self):
        self.assertEqual(corners.DEFAULT_TEMPERATURES_C, (-40.0, 27.0, 125.0))
        self.assertAlmostEqual(corners.DEFAULT_SUPPLY_TOLERANCE, 0.10)

    def test_supply_points_are_nominal_plus_minus_ten_percent(self):
        self.assertEqual(corners.supply_points(3.3, 0.10), [2.97, 3.3, 3.63])

    def test_zero_tolerance_collapses_the_voltage_axis(self):
        self.assertEqual(corners.supply_points(3.3, 0.0), [3.3])

    def test_every_corner_names_one_section_per_device_family(self):
        for name, corner in corners.CORNERS.items():
            with self.subTest(corner=name):
                self.assertEqual(len(corner.sections), len(corners.FAMILIES), corner.sections)
                self.assertEqual(len(set(corner.sections)), len(corners.FAMILIES), corner.sections)

    def test_corner_sets_expand_and_deduplicate(self):
        resolved = corners.resolve_corners(["mos", "tt"])
        self.assertEqual([c.name for c in resolved], ["tt", "ff", "ss", "fs", "sf"])

    def test_unknown_corner_is_rejected(self):
        with self.assertRaises(KeyError):
            corners.resolve_corners(["nope"])

    def test_grid_is_full_factorial_and_ordered(self):
        grid = corners.build_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), [2.97, 3.3, 3.63]
        )
        self.assertEqual(len(grid), 5 * 3 * 3)
        self.assertEqual(len({p.corner_id for p in grid}), 45)

    def test_corner_id_matches_the_ratified_naming(self):
        """sim/README.md: <corner-id> is <process>_<temp>c_<supply>v."""
        grid = corners.build_grid(
            corners.resolve_corners(["tt", "ss", "ff"]), (-40, 27, 125), [2.97, 3.3, 3.63]
        )
        ids = {p.corner_id for p in grid}
        self.assertIn("tt_27c_3.30v", ids)
        self.assertIn("ss_-40c_2.97v", ids)
        self.assertIn("ff_125c_3.63v", ids)

    # -- ADC-specific corner adaptation -------------------------------- #

    def test_capacitor_corners_exist_for_the_cdac(self):
        """A SAR ADC's accuracy rides on the CDAC, so the cap families must skew."""
        for name in ("cap_ff", "cap_ss", "mim_ff", "mim_ss", "moscap_ff", "moscap_ss"):
            self.assertIn(name, corners.CORNERS)
        mim_index = corners.FAMILIES.index("mimcap")
        moscap_index = corners.FAMILIES.index("moscap")
        self.assertEqual(corners.CORNERS["mim_ss"].sections[mim_index], "mimcap_ss")
        self.assertEqual(corners.CORNERS["moscap_ff"].sections[moscap_index], "moscap_ff")
        self.assertEqual(corners.CORNERS["cap_ss"].sections[mim_index], "mimcap_ss")
        self.assertEqual(corners.CORNERS["cap_ss"].sections[moscap_index], "moscap_ss")

    def test_mos_corners_leave_the_capacitors_typical(self):
        """Why the cdac corner set is necessary: MOS sweeps never move the caps."""
        mim_index = corners.FAMILIES.index("mimcap")
        for name in ("tt", "fs", "sf"):
            self.assertEqual(corners.CORNERS[name].sections[mim_index], "mimcap_typical")

    def test_cdac_corner_set_covers_both_capacitor_families(self):
        resolved = corners.resolve_corners(["cdac"])
        mim_index = corners.FAMILIES.index("mimcap")
        moscap_index = corners.FAMILIES.index("moscap")
        self.assertGreaterEqual(len({c.sections[mim_index] for c in resolved}), 3)
        self.assertGreaterEqual(len({c.sections[moscap_index] for c in resolved}), 3)

    def test_full_corner_set_covers_every_defined_corner(self):
        self.assertEqual(set(corners.CORNER_SETS["full"]), set(corners.CORNERS))

    def test_sabotage_keeps_the_names_and_flattens_the_sections(self):
        """The negative control must be indistinguishable by name, not by model."""
        original = corners.resolve_corners(["full"])
        sabotaged = corners.sabotage(original)
        self.assertEqual([c.name for c in sabotaged], [c.name for c in original])
        self.assertEqual(len({c.sections for c in sabotaged}), 1)
        self.assertEqual(sabotaged[0].sections, corners.CORNERS["tt"].sections)


class PdkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_mim_subckt_follows_the_variant_metal_stack(self):
        pdk = fake_pdk(self.root / "gf180mcuD")
        self.assertEqual(pdk.mim_stack, "m4m5")
        self.assertEqual(pdk.mim_subckt("2f0"), "cap_mim_2f0_m4m5_noshield")
        self.assertEqual(pdk.mim_subckt("1f0"), "cap_mim_1f0_m4m5_noshield")

    def test_every_known_variant_maps_to_a_stack(self):
        for variant in MIM_STACK_BY_VARIANT:
            with self.subTest(variant=variant):
                pdk = fake_pdk(self.root / variant)
                self.assertRegex(pdk.mim_subckt("1f5"), r"^cap_mim_1f5_m\dm\d_noshield$")

    def test_unknown_variant_is_a_loud_error_not_a_guess(self):
        pdk = fake_pdk(self.root / "gf180mcuZ")
        with self.assertRaises(UnknownVariant):
            pdk.mim_stack
        # ...and provenance degrades gracefully rather than exploding.
        self.assertEqual(pdk.provenance()["mim_stack"], "unknown")

    def test_unknown_density_is_rejected(self):
        pdk = fake_pdk(self.root / "gf180mcuD")
        with self.assertRaises(KeyError):
            pdk.mim_subckt("9f9")


class TestbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _write(self, netlist: str, manifest: dict | None = None) -> Path:
        """Lay out sim/<slug>/testbench/ the way sim/README.md specifies."""
        tb_dir = self.dir / "an-experiment" / "testbench"
        tb_dir.mkdir(parents=True, exist_ok=True)
        (tb_dir / "x.spice").write_text(netlist)
        base = {"name": "x", "netlist": "x.spice", "measure": {"vout": "v(out)"}}
        base.update(manifest or {})
        (tb_dir / "tb.json").write_text(json.dumps(base))
        return tb_dir

    def test_loads_a_valid_manifest(self):
        tb = testbench.load(self._write("v1 out 0 dc {vdd_val}\n"))
        self.assertEqual(tb.name, "x")
        self.assertEqual(tb.measure, {"vout": "v(out)"})
        self.assertEqual(tb.temperatures_c, (-40.0, 27.0, 125.0))

    def test_experiment_slug_comes_from_the_directory_layout(self):
        tb_dir = self._write("v1 out 0 dc {vdd_val}\n")
        for target in (tb_dir, tb_dir.parent):
            with self.subTest(target=target.name):
                tb = testbench.load(target)
                self.assertEqual(tb.experiment, "an-experiment")
                self.assertEqual(tb.experiment_dir.name, "an-experiment")

    def test_discover_finds_experiments_not_bare_manifest_dirs(self):
        self._write("v1 out 0 dc {vdd_val}\n")
        found = testbench.discover(self.dir)
        self.assertEqual([p.name for p in found], ["an-experiment"])

    def test_rejects_netlists_that_pin_the_temperature(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self._write("v1 out 0 dc 3.3\n.temp 27\n"))
        self.assertIn(".temp", str(ctx.exception))

    def test_rejects_netlists_that_include_models_themselves(self):
        with self.assertRaises(ValueError):
            testbench.load(self._write('.lib "models" typical\nv1 out 0 dc 3.3\n'))

    def test_rejects_a_manifest_without_measurements(self):
        with self.assertRaises(ValueError):
            testbench.load(self._write("v1 out 0 dc 3.3\n", {"measure": {}}))

    def test_rejects_a_check_on_an_unknown_measurement(self):
        with self.assertRaises(ValueError):
            testbench.load(
                self._write("v1 out 0 dc 3.3\n", {"checks": {"typo": {"min": 1}}})
            )

    def test_rejects_a_misspelled_check_key(self):
        """A silently-ignored min_spread_pct is the exact failure to avoid."""
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self._write("v1 out 0 dc 3.3\n", {"checks": {"vout": {"min_spread": 5}}})
            )
        self.assertIn("min_spread", str(ctx.exception))

    def test_rejects_an_unknown_sensitivity_axis(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self._write(
                    "v1 out 0 dc 3.3\n",
                    {"checks": {"vout": {"min_spread_pct_by_axis": {"pressure": 1.0}}}},
                )
            )
        self.assertIn("pressure", str(ctx.exception))

    def test_the_repo_testbenches_are_valid(self):
        found = {p.name for p in testbench.discover(SIM_DIR)}
        self.assertIn("smoke-sar-bias", found)
        self.assertIn("device-cdac-cap", found)
        for slug in sorted(found):
            with self.subTest(experiment=slug):
                tb = testbench.load(SIM_DIR / slug)
                self.assertEqual(tb.nominal_supply_v, 3.3)
                self.assertEqual(tb.experiment, slug)
                self.assertTrue(tb.measure)

    def test_the_acceptance_testbench_pins_every_pvt_axis(self):
        """The whole point of smoke-sar-bias: all three axes are asserted."""
        tb = testbench.load(SIM_DIR / "smoke-sar-bias")
        asserted = set()
        for spec in tb.checks.values():
            asserted |= set(spec.get("min_spread_pct_by_axis") or {})
        self.assertEqual(asserted, set(testbench.AXES))

    def test_the_cdac_testbench_asserts_capacitor_process_sensitivity(self):
        tb = testbench.load(SIM_DIR / "device-cdac-cap")
        self.assertIn("cdac", tb.corners)
        floors = [
            (spec.get("min_spread_pct_by_axis") or {}).get("process")
            for name, spec in tb.checks.items()
            if name.startswith("cmim")
        ]
        self.assertTrue(any(f for f in floors), "no MiM process-sensitivity floor")


class DeckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "tb").mkdir()
        (root / "tb" / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (root / "tb" / "tb.json").write_text(
            json.dumps(
                {
                    "name": "x",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)", "iq": "-i(v1)"},
                    "params": {"cload": "1p"},
                    "options": ["reltol=1e-5"],
                }
            )
        )
        self.tb = testbench.load(root / "tb")
        self.pdk = fake_pdk(root / "gf180mcuD")
        self.point = corners.build_grid(corners.resolve_corners(["ss"]), (125,), [3.63])[0]
        self.deck = runner.compose_deck(self.tb, self.pdk, self.point)

    def test_deck_sets_the_pvt_point(self):
        self.assertIn(".param vdd_val=3.63", self.deck)
        self.assertIn(".param vdd_nom=3.3", self.deck)
        self.assertIn(".temp 125", self.deck)

    def test_deck_includes_design_switches_before_model_sections(self):
        design_at = self.deck.index("design.ngspice")
        lib_at = self.deck.index("sm141064.ngspice")
        self.assertLess(design_at, lib_at)

    def test_deck_selects_every_section_of_the_corner(self):
        for section in self.point.corner.sections:
            self.assertIn(f'sm141064.ngspice" {section}', self.deck)

    def test_deck_carries_manifest_params_and_options(self):
        self.assertIn(".param cload=1p", self.deck)
        self.assertIn(".options reltol=1e-5", self.deck)

    def test_deck_emits_one_measurement_vector_per_measure_entry(self):
        self.assertIn("let m_vout = v(out)", self.deck)
        self.assertIn("let m_iq = -i(v1)", self.deck)
        self.assertIn("print m_vout", self.deck)
        self.assertTrue(self.deck.rstrip().endswith(".end"))

    def test_deck_binds_the_mim_aliases_to_the_variant_stack(self):
        self.assertIn(".subckt mim_cap_2f0 1 2", self.deck)
        self.assertIn("cap_mim_2f0_m4m5_noshield", self.deck)
        self.assertIn(".subckt mim_cap_1f0 1 2", self.deck)

    def test_a_sabotaged_deck_differs_from_the_real_one(self):
        """The negative control must change the models, not just a label."""
        sabotaged_corner = corners.sabotage([self.point.corner])[0]
        sabotaged_point = corners.PvtPoint(
            corner=sabotaged_corner, temp_c=self.point.temp_c, vdd=self.point.vdd
        )
        sabotaged = runner.compose_deck(self.tb, self.pdk, sabotaged_point)
        self.assertEqual(sabotaged_point.corner_id, self.point.corner_id)
        self.assertNotEqual(sabotaged, self.deck)
        self.assertIn('sm141064.ngspice" typical', sabotaged)
        self.assertNotIn('sm141064.ngspice" ss\n', sabotaged)


class ParseTests(unittest.TestCase):
    def test_parses_print_output(self):
        text = "\n".join(
            [
                "Circuit: * x",
                "m_vout = 1.2003456789e+00",
                "m_iq = -4.5e-05",
                "v(other) = 9.9",
                "m_bad = not_a_number",
            ]
        )
        self.assertEqual(
            runner.parse_measurements(text), {"vout": 1.2003456789, "iq": -4.5e-05}
        )


class _StubPoint:
    def __init__(self, corner_id):
        self.corner_id = corner_id


class _StubResult:
    def __init__(self, corner_id, measurements, status="ok"):
        self.point = _StubPoint(corner_id)
        self.measurements = measurements
        self.status = status


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            _StubResult("a", {"v": 1.0}),
            _StubResult("b", {"v": 1.2}),
            _StubResult("c", {"v": 0.8}),
        ]
        self.summary = report.summarize(self.results, ["v"])

    def test_summary_finds_the_extremes(self):
        stats = self.summary["v"]
        self.assertEqual((stats["min"], stats["min_at"]), (0.8, "c"))
        self.assertEqual((stats["max"], stats["max_at"]), (1.2, "b"))
        self.assertAlmostEqual(stats["spread_pct"], 40.0)

    def test_min_max_violations_are_reported_with_their_corner(self):
        failures = report.evaluate_checks({"v": {"min": 0.9}}, self.results, self.summary)
        self.assertEqual(len(failures), 1)
        self.assertEqual((failures[0]["kind"], failures[0]["at"]), ("min", "c"))

    def test_max_spread_violation(self):
        failures = report.evaluate_checks(
            {"v": {"max_spread_pct": 10.0}}, self.results, self.summary
        )
        self.assertEqual(failures[0]["kind"], "max_spread_pct")

    def test_min_spread_catches_a_grid_that_never_moved(self):
        flat = [_StubResult("a", {"v": 1.0}), _StubResult("b", {"v": 1.0})]
        summary = report.summarize(flat, ["v"])
        failures = report.evaluate_checks({"v": {"min_spread_pct": 5.0}}, flat, summary)
        self.assertEqual(failures[0]["kind"], "min_spread_pct")

    def test_passing_checks_produce_no_failures(self):
        self.assertEqual(
            report.evaluate_checks(
                {"v": {"min": 0.5, "max": 1.5, "max_spread_pct": 50.0}},
                self.results,
                self.summary,
            ),
            [],
        )


def _grid_results(value_of) -> list[runner.PointResult]:
    """A full 3x3x3 grid whose measurement is ``value_of(corner, temp, vdd)``."""
    points = corners.build_grid(
        corners.resolve_corners(["tt", "ff", "ss"]),
        (-40.0, 27.0, 125.0),
        corners.supply_points(3.3, 0.10),
    )
    return [
        runner.PointResult(
            point=p,
            status="ok",
            measurements={"v": value_of(p.corner.name, p.temp_c, p.vdd)},
        )
        for p in points
    ]


class AxisSensitivityTests(unittest.TestCase):
    """The guard against the silent failure: a grid that only *looks* swept."""

    def test_an_axis_that_moves_is_reported_per_axis(self):
        results = _grid_results(lambda c, t, v: {"tt": 1.0, "ff": 1.2, "ss": 0.8}[c])
        sensitivity = report.axis_sensitivity(results, ["v"])["v"]
        self.assertGreater(sensitivity["process"]["min_pct"], 30.0)
        self.assertEqual(sensitivity["temperature"]["min_pct"], 0.0)
        self.assertEqual(sensitivity["supply"]["min_pct"], 0.0)

    def test_grid_wide_min_spread_is_fooled_where_per_axis_is_not(self):
        """The precise reason this diverges from the upstream harness.

        Temperature moves; process is stuck on typical. The grid-wide
        min_spread_pct sees plenty of movement and passes. Only a per-axis
        floor notices that the process axis never moved.
        """
        results = _grid_results(lambda c, t, v: 1.0 + t / 1000.0)
        summary = report.summarize(results, ["v"])
        sensitivity = report.axis_sensitivity(results, ["v"])

        fooled = report.evaluate_checks(
            {"v": {"min_spread_pct": 5.0}}, results, summary, sensitivity
        )
        self.assertEqual(fooled, [], "grid-wide floor should be (misleadingly) satisfied")

        caught = report.evaluate_checks(
            {"v": {"min_spread_pct_by_axis": {"process": 5.0}}},
            results,
            summary,
            sensitivity,
        )
        self.assertEqual(len(caught), 1)
        self.assertEqual(caught[0]["kind"], "min_spread_pct_by_axis")
        self.assertEqual(caught[0]["axis"], "process")

    def test_a_single_stuck_slice_cannot_hide_behind_the_others(self):
        """min_pct is the weakest slice, so one dead slice still fails."""

        def value(corner, temp, vdd):
            if temp == 125.0:          # this temperature slice ignores process
                return 1.0
            return {"tt": 1.0, "ff": 1.3, "ss": 0.7}[corner]

        results = _grid_results(value)
        summary = report.summarize(results, ["v"])
        sensitivity = report.axis_sensitivity(results, ["v"])
        self.assertEqual(sensitivity["v"]["process"]["min_pct"], 0.0)
        self.assertGreater(sensitivity["v"]["process"]["max_pct"], 50.0)
        failures = report.evaluate_checks(
            {"v": {"min_spread_pct_by_axis": {"process": 5.0}}},
            results,
            summary,
            sensitivity,
        )
        self.assertEqual(len(failures), 1)

    def test_supply_and_temperature_axes_are_pinned_independently(self):
        results = _grid_results(lambda c, t, v: v * 2.0)
        summary = report.summarize(results, ["v"])
        sensitivity = report.axis_sensitivity(results, ["v"])
        failures = report.evaluate_checks(
            {
                "v": {
                    "min_spread_pct_by_axis": {
                        "process": 1.0,
                        "temperature": 1.0,
                        "supply": 1.0,
                    }
                }
            },
            results,
            summary,
            sensitivity,
        )
        axes = sorted(f["axis"] for f in failures)
        self.assertEqual(axes, ["process", "temperature"])

    def test_an_unswept_axis_is_a_failure_not_a_pass(self):
        points = corners.build_grid(corners.resolve_corners(["tt", "ff", "ss"]), (27.0,), [3.3])
        results = [
            runner.PointResult(point=p, status="ok", measurements={"v": 1.0 + i})
            for i, p in enumerate(points)
        ]
        summary = report.summarize(results, ["v"])
        sensitivity = report.axis_sensitivity(results, ["v"])
        spec = {"v": {"min_spread_pct_by_axis": {"temperature": 1.0}}}

        failures = report.evaluate_checks(spec, results, summary, sensitivity)
        self.assertEqual(len(failures), 1)
        self.assertIn("never swept", failures[0]["note"])

        allowed = report.evaluate_checks(
            spec, results, summary, sensitivity, allow_unswept_axes=True
        )
        self.assertEqual(allowed, [])

    def test_max_spread_by_axis_pins_an_invariant(self):
        results = _grid_results(lambda c, t, v: v * 0.5)
        summary = report.summarize(results, ["v"])
        sensitivity = report.axis_sensitivity(results, ["v"])
        failures = report.evaluate_checks(
            {"v": {"max_spread_pct_by_axis": {"supply": 1.0}}},
            results,
            summary,
            sensitivity,
        )
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kind"], "max_spread_pct_by_axis")


class EvidenceExtensionTests(unittest.TestCase):
    """sim/README.md's ADC-specific extension groups, enforced not assumed."""

    def test_defaults_are_a_plain_corner_matrix_record(self):
        ext = evidence.Extensions()
        ext.validate()
        self.assertFalse(ext.is_characterization)
        self.assertEqual(ext.render_lines(), [])

    def test_characterization_record_requires_data_provenance(self):
        ext = evidence.Extensions(record_kind="characterization")
        with self.assertRaises(evidence.EvidenceFormatError):
            ext.validate()
        ext.data_provenance = "foundry-documentation — GF180MCU model card"
        ext.validate()

    def test_data_provenance_tag_must_be_ratified(self):
        ext = evidence.Extensions(
            record_kind="characterization", data_provenance="vibes — trust me"
        )
        with self.assertRaises(evidence.EvidenceFormatError):
            ext.validate()

    def test_linearity_method_tag_must_be_ratified(self):
        with self.assertRaises(evidence.EvidenceFormatError):
            evidence.Extensions(linearity_method="some-codes").validate()
        evidence.Extensions(linearity_method="code-density — 1e6 sine hits").validate()

    def test_transient_noise_needs_seed_and_duration_justification(self):
        ext = evidence.Extensions(noise_method="transient-noise")
        with self.assertRaises(evidence.EvidenceFormatError) as ctx:
            ext.validate()
        self.assertIn("seed", str(ctx.exception))
        ext.noise_seed = "1"
        ext.noise_duration_justification = "10x settling"
        ext.validate()

    def test_ac_based_noise_needs_neither(self):
        evidence.Extensions(noise_method="ac-based — 1 Hz..10 MHz integration").validate()

    def test_monte_carlo_needs_seed_scope_and_sigma(self):
        with self.assertRaises(evidence.EvidenceFormatError):
            evidence.Extensions(mc_seed="1-500").validate()
        evidence.Extensions(
            mc_seed="1-500", mc_scope="mismatch-only", mc_sigma="+/-3 sigma"
        ).validate()

    def test_monte_carlo_scope_is_constrained(self):
        with self.assertRaises(evidence.EvidenceFormatError):
            evidence.Extensions(
                mc_seed="1", mc_scope="everything", mc_sigma="3"
            ).validate()

    def test_fft_record_needs_the_whole_metadata_block(self):
        with self.assertRaises(evidence.EvidenceFormatError):
            evidence.Extensions(fft_n=4096).validate()
        evidence.Extensions(
            fft_n=4096, fft_input_hz=1.0e5, fft_bin=409, fft_window="none", fft_fs_hz=1e6
        ).validate()

    def test_a_windowed_fft_must_justify_abandoning_coherent_sampling(self):
        base = dict(fft_n=4096, fft_input_hz=1.0e5, fft_bin=409, fft_fs_hz=1e6)
        with self.assertRaises(evidence.EvidenceFormatError):
            evidence.Extensions(fft_window="hann", **base).validate()
        evidence.Extensions(
            fft_window="hann — source could not be made coherent", **base
        ).validate()

    def test_manifest_rejects_unknown_evidence_keys(self):
        with self.assertRaises(evidence.EvidenceFormatError):
            evidence.from_manifest({"lienarity_method": "code-density"})

    def test_manifest_round_trips_a_string_note(self):
        ext = evidence.from_manifest({"notes": "one note"})
        self.assertEqual(ext.notes, ["one note"])


class RecordIdTests(unittest.TestCase):
    def test_record_id_matches_the_ratified_shape(self):
        """sim/README.md: <record-id> is <YYYYMMDD>-<HHMMSS>-<short-git-sha>."""
        when = datetime.datetime(2026, 7, 29, 15, 30, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(report.format_record_id("1a7ef75", when), "20260729-153000-1a7ef75")
        self.assertRegex(
            report.format_record_id("1a7ef75", when), r"^\d{8}-\d{6}-[0-9a-f]{7}$"
        )

    def test_allocation_never_reuses_an_existing_record_id(self):
        when = datetime.datetime(2026, 7, 29, 15, 30, 0, tzinfo=datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            records = Path(tmp)
            first = report.allocate_record_id(SIM_DIR, records, when)
            (records / f"{first}.md").write_text("# first\n")
            second = report.allocate_record_id(SIM_DIR, records, when)
            self.assertNotEqual(first, second)
            self.assertRegex(second, r"^\d{8}-\d{6}-")
            # the existing record was not touched
            self.assertEqual((records / f"{first}.md").read_text(), "# first\n")

    def test_write_record_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            experiment = Path(tmp) / "an-experiment"
            (experiment / report.RECORDS_DIR).mkdir(parents=True)
            (experiment / report.RECORDS_DIR / "20260729-153000-abc1234.md").write_text("keep\n")
            with self.assertRaises(report.RecordExists):
                report.write_record({"record_id": "20260729-153000-abc1234"}, experiment)
            self.assertEqual(
                (experiment / report.RECORDS_DIR / "20260729-153000-abc1234.md").read_text(),
                "keep\n",
            )


class MatrixConformanceTests(unittest.TestCase):
    """sim/README.md requires the full mandated matrix, or a stated reason."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tb_dir = Path(self.tmp.name) / "an-experiment" / "testbench"
        tb_dir.mkdir(parents=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(
            json.dumps({"name": "x", "netlist": "x.spice", "measure": {"vout": "v(out)"}})
        )
        self.tb = testbench.load(tb_dir)

    def _grid(self, corner_names, temps, supplies):
        return corners.build_grid(corners.resolve_corners(corner_names), temps, supplies)

    def test_full_matrix_is_recognised(self):
        grid = self._grid(["mos"], (-40, 27, 125), corners.supply_points(3.3, 0.10))
        self.assertEqual(report.matrix_conformance(self.tb, grid), {"full": True, "missing": []})

    def test_missing_temperature_is_flagged(self):
        grid = self._grid(["mos"], (27,), corners.supply_points(3.3, 0.10))
        result = report.matrix_conformance(self.tb, grid)
        self.assertFalse(result["full"])
        self.assertTrue(any("temperature" in m for m in result["missing"]))

    def test_missing_supply_and_process_are_flagged(self):
        grid = self._grid(["tt"], (-40, 27, 125), [3.3])
        result = report.matrix_conformance(self.tb, grid)
        self.assertFalse(result["full"])
        self.assertTrue(any("supply" in m for m in result["missing"]))
        self.assertTrue(any("process" in m for m in result["missing"]))


class RecordRenderingTests(unittest.TestCase):
    """The rendered record carries exactly the fields sim/README.md lists."""

    RATIFIED_FIELDS = (
        "Record ID",
        "Claim",
        "Netlist provenance",
        "Corner matrix run",
        "Statistical convention",
        "Result",
        "Links",
        "Timestamp / author",
        "Supersedes",
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        tb_dir = root / "smoke-sar-bias" / "testbench"
        tb_dir.mkdir(parents=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(
            json.dumps(
                {
                    "name": "smoke-sar-bias",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)"},
                    "checks": {"vout": {"min": 0.0, "max": 10.0}},
                }
            )
        )
        self.tb = testbench.load(tb_dir)
        self.pdk = fake_pdk(root / "gf180mcuD")
        self.points = corners.build_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), corners.supply_points(3.3, 0.10)
        )
        self.results = [
            runner.PointResult(point=p, status="ok", measurements={"vout": 1.0 + i * 0.01})
            for i, p in enumerate(self.points)
        ]
        self.record = self._build()

    def _build(self, **overrides):
        kwargs = dict(
            tb=self.tb,
            pdk=self.pdk,
            points=self.points,
            results=self.results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260729-153000-1a7ef75",
            started_utc="2026-07-29T15:30:00+00:00",
            wall_seconds=9.5,
            claim="spec/adc.md#example",
        )
        kwargs.update(overrides)
        return report.build_record(**kwargs)

    def test_every_ratified_field_is_present_and_in_order(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        positions = []
        for field in self.RATIFIED_FIELDS:
            marker = f"**{field}**"
            self.assertIn(marker, text, f"missing ratified field {field!r}")
            positions.append(text.index(marker))
        self.assertEqual(positions, sorted(positions), "fields are out of ratified order")

    def test_links_point_at_the_ratified_paths(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        self.assertIn("sim/smoke-sar-bias/testbench/x.spice", text)
        self.assertIn(
            "sim/smoke-sar-bias/netlist-snapshots/20260729-153000-1a7ef75.spice", text
        )
        self.assertIn("sim/smoke-sar-bias/corners/20260729-153000-1a7ef75/", text)

    def test_result_table_uses_corner_ids_and_reports_overall_verdict(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        self.assertIn("`tt_-40c_2.97v`", text)
        self.assertIn("`ff_125c_3.63v`", text)
        self.assertIn("**Overall: PASS**", text)

    def test_a_full_matrix_run_says_so(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        self.assertIn("Full PVT matrix per CLAUDE.md", text)

    def test_the_record_shows_per_axis_sensitivity(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        self.assertIn("Per-axis corner sensitivity", text)
        for axis in testbench.AXES:
            self.assertIn(axis, text)

    def test_environment_section_names_the_real_pdk_provenance(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        provenance = self.pdk.provenance()
        self.assertIn(str(provenance["open_pdks_version"]), text)
        self.assertIn(provenance["variant"], text)
        self.assertIn("m4m5", text)
        self.assertNotIn("open_pdks `None`", text)

    def test_environment_section_names_the_upstream_pattern_it_was_ported_from(self):
        text = report.render_record(self.record, "smoke-sar-bias")
        self.assertIn("gf180-bandgap@", text)

    def test_git_state_is_taken_from_the_caller_not_resampled(self):
        """The harness dirties the tree by writing logs; provenance is pre-run."""
        pre_run = {"commit": "f" * 40, "short": "fffffff", "branch": "main", "dirty": False}
        env = report.environment(self.pdk, "ngspice-46", SIM_DIR, pre_run)
        self.assertEqual(env["git"], pre_run)

    def test_a_dirty_tree_is_called_out_in_netlist_provenance(self):
        dirty = dict(self.record)
        dirty["environment"] = dict(self.record["environment"])
        dirty["environment"]["git"] = {
            "commit": "f" * 40, "short": "fffffff", "branch": "main", "dirty": True,
        }
        text = report.render_record(dirty, "smoke-sar-bias")
        self.assertIn("dirty working tree", text)

    def test_a_characterization_record_reports_measured_values(self):
        record = self._build(
            extensions=evidence.Extensions(
                record_kind="characterization",
                data_provenance="simulated — gf180mcu device models",
            )
        )
        text = report.render_record(record, "device-cdac-cap")
        self.assertIn("**Measured value(s)**", text)
        self.assertIn("**Data provenance**", text)
        self.assertNotIn("- **Result**", text)

    def test_adc_extension_fields_are_rendered_between_convention_and_result(self):
        record = self._build(
            extensions=evidence.Extensions(
                linearity_method="full-1024-code-ramp — all 1024 codes",
                fft_n=4096,
                fft_input_hz=1.0e5,
                fft_bin=409,
                fft_window="none",
                fft_fs_hz=1e6,
                mc_seed="1-500",
                mc_scope="mismatch-only",
                mc_sigma="+/-3 sigma",
            )
        )
        text = report.render_record(record, "smoke-sar-bias")
        for marker in (
            "**Dynamic-test (FFT) metadata**",
            "**Linearity methodology**",
            "**Seed handling**",
            "**Scope**",
            "**Sigma level**",
        ):
            self.assertIn(marker, text)
        self.assertLess(
            text.index("**Statistical convention**"), text.index("**Seed handling**")
        )
        self.assertLess(
            text.index("**Linearity methodology**"), text.index("- **Result**")
        )

    def test_netlist_snapshot_is_frozen_and_append_only(self):
        experiment = self.tb.experiment_dir
        path = report.write_netlist_snapshot(self.tb, experiment, "20260729-153000-1a7ef75")
        self.assertEqual(path.parent.name, report.SNAPSHOT_DIR)
        self.assertIn("v1 out 0 dc {vdd_val}", path.read_text())
        self.assertIn(self.tb.netlist_sha256, path.read_text())
        with self.assertRaises(report.RecordExists):
            report.write_netlist_snapshot(self.tb, experiment, "20260729-153000-1a7ef75")


if __name__ == "__main__":
    unittest.main()
