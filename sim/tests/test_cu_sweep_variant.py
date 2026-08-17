#!/usr/bin/env python3
"""The DR-0019 `C_u` isolation sweep must really vary only `C_u` (issue #211).

    python3 -m unittest discover -s sim/tests -v

`sim/dr0019-cu-sweep/` exists to answer a causal question -- does the dynamic
regression DR-0019's resize introduced track the CDAC unit capacitance? -- and
that answer is worth nothing unless "everything else was held fixed" is a
*checked* statement rather than an assurance in a README. These tests are the
check, and they need neither ngspice nor the PDK, so they run on the PDK-free
CI path on every pull request:

- the variant generator at the ratified `C_u` must reproduce the committed
  `sim/adc-enob-fft/` deck **byte-for-byte** (so a sweep point differs from
  the ratified deck by exactly the parameter that was swept, and nothing
  else);
- at the pre-resize `C_u` it must reproduce the historical geometry and
  capacitance `spec/cdac-sizing-memo.md` §5.2 publishes;
- the orthogonal control must touch exactly one line of the deck;
- the sweep manifest must keep the `adc-enob-fft` manifest's measurement
  machinery byte-identical, since "point-for-point comparable with the
  ratified campaign" is the whole basis for reading the two together;
- the sweep's re-derived noise composition must reproduce the ratified
  `0.0488 LSB` at the `C_u` that number was published for;
- the `C_u` axis the runner actually executes must be the axis the README
  publishes, because the README is what a reader checks the findings against;
- and a re-run point must not be counted twice, since `sim/` records are
  append-only and a superseded point stays on disk forever.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SWEEP = REPO / "sim" / "dr0019-cu-sweep"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


variant = _load("gen_cu_variant", SWEEP / "gen_cu_variant.py")
sweep_analysis = _load("analyze_sweep", SWEEP / "analyze_sweep.py")


class VariantGeneratorTests(unittest.TestCase):
    def test_ratified_c_u_reproduces_the_committed_deck(self):
        """The load-bearing one. If this fails, no sweep point is comparable
        with sim/adc-enob-fft/'s records and the isolation is void."""
        self.assertEqual(
            variant.variant_deck(variant.C_UNIT_RATIFIED_FF),
            variant.BASELINE_DECK.read_text(),
        )

    def test_pre_resize_c_u_reproduces_the_published_historical_geometry(self):
        """spec/cdac-sizing-memo.md §5.2: C_u = 17.24 fF is a 2.7136 um square
        and C_side = 512*C_u = 8.827 pF. Both are printed by the generator, so
        a wrong rebinding of C_UNIT_FF shows up here rather than silently
        producing a sweep axis that is not the axis it claims to be."""
        deck = variant.variant_deck(variant.C_UNIT_PRE_RESIZE_FF)
        self.assertIn("C_u = 17.24 fF", deck)
        self.assertIn("512 * C_u = 8.827 pF", deck)
        self.assertIn("c_width=2.7136u c_length=2.7136u", deck)

    def test_c_u_is_the_only_axis_the_generator_path_moves(self):
        """Two decks at different C_u must differ ONLY in lines that carry a
        capacitance, a MiM square side, or the C_u value in a comment -- never
        in a switch geometry, a clock, the stimulus, or the shadow DAC."""
        ratified = variant.variant_deck(variant.C_UNIT_RATIFIED_FF).splitlines()
        pre = variant.variant_deck(variant.C_UNIT_PRE_RESIZE_FF).splitlines()
        self.assertEqual(len(ratified), len(pre))
        changed = [(a, b) for a, b in zip(ratified, pre) if a != b]
        self.assertTrue(changed, "the two decks are identical -- C_u did not take")
        for after, before in changed:
            with self.subTest(line=before):
                self.assertTrue(
                    "c_width=" in before
                    or "C_u" in before
                    or "cw=" in before
                    or before.lstrip("* ").startswith("w="),
                    f"unexpected non-capacitance difference: {before!r} -> {after!r}",
                )

    def test_acq_switch_scale_touches_exactly_one_line(self):
        """The orthogonal control is a text substitution, so its blast radius
        is asserted rather than trusted: one line, the CDAC cell's fourth
        (input) leg, with the other three legs left at 10u/20u."""
        base = variant.variant_deck(variant.C_UNIT_RATIFIED_FF).splitlines()
        wide = variant.variant_deck(
            variant.C_UNIT_RATIFIED_FF, acq_switch_scale=2.068
        ).splitlines()
        self.assertEqual(len(base), len(wide))
        changed = [(a, b) for a, b in zip(base, wide) if a != b]
        self.assertEqual(len(changed), 1, f"expected 1 changed line, got {changed}")
        before, after = changed[0]
        self.assertEqual(before, variant.ACQ_LEG_LINE)
        self.assertIn("wn=20.6800u wp=41.3600u", after)
        self.assertTrue(after.startswith("Xsi "))
        # the release / V_REF / GND legs are untouched
        for leg in ("Xsr ", "Xsh ", "Xsl "):
            self.assertTrue(
                any(line.startswith(leg) and "wn=10u wp=20u" in line for line in wide),
                f"{leg.strip()} lost its ratified geometry",
            )

    def test_scale_of_one_is_a_no_op(self):
        self.assertEqual(
            variant.variant_deck(22.0),
            variant.variant_deck(22.0, acq_switch_scale=1.0),
        )


class SweepManifestTests(unittest.TestCase):
    def test_measurement_machinery_is_byte_identical_to_adc_enob_fft(self):
        """'Point-for-point comparable with the ratified campaign' is the
        premise of every comparison in the findings write-up. Drift in any of
        these four blocks would break it silently."""
        sweep = json.loads((SWEEP / "testbench" / "tb.json").read_text())
        ratified = json.loads(
            (REPO / "sim" / "adc-enob-fft" / "testbench" / "tb.json").read_text()
        )
        for block in ("analyses", "measure", "checks"):
            with self.subTest(block=block):
                self.assertEqual(sweep[block], ratified[block])
        for key in ("nominal_supply_v", "supply_tolerance", "temperatures_c"):
            with self.subTest(key=key):
                self.assertEqual(sweep[key], ratified[key])
        for key in ("fft_n", "fft_input_hz", "fft_bin", "fft_window", "fft_fs_hz"):
            with self.subTest(key=key):
                self.assertEqual(sweep["evidence"][key], ratified["evidence"][key])

    def test_manifest_netlist_points_at_the_ratified_deck(self):
        sweep = json.loads((SWEEP / "testbench" / "tb.json").read_text())
        named = (SWEEP / "testbench" / sweep["netlist"]).resolve()
        self.assertEqual(
            named,
            (REPO / "sim" / "adc-enob-fft" / "testbench" / "tb_adc_enob_fft.spice"),
        )
        self.assertTrue(named.is_file())

    def test_manifest_is_a_characterization_record_not_a_spec_verdict(self):
        """A sweep point at a non-ratified C_u is not a measurement of the
        ratified design, so these records must not be shaped like a pass/fail
        against README.md's ENOB or SFDR rows."""
        sweep = json.loads((SWEEP / "testbench" / "tb.json").read_text())
        self.assertEqual(sweep["evidence"]["record_kind"], "characterization")
        self.assertTrue(sweep["evidence"]["data_provenance"].startswith("simulated"))


class NoiseCompositionTests(unittest.TestCase):
    def test_reproduces_the_ratified_composition_at_the_published_c_u(self):
        """spec/testbench-suite-memo.md §4.3 publishes 0.0488 LSB, composed at
        C_side = 8.827 pF. The sweep re-derives that term per point because
        its kT/C half moves with the swept quantity; this pins the arithmetic
        to the published value at the point it was published for."""
        self.assertAlmostEqual(
            sweep_analysis.sigma_extra_lsb(variant.C_UNIT_PRE_RESIZE_FF),
            0.0488,
            places=4,
        )

    def test_noise_term_shrinks_monotonically_as_c_u_grows(self):
        values = [
            sweep_analysis.sigma_extra_lsb(c) for c in (17.24, 22.0, 30.0, 35.6528, 42.0)
        ]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_slope_fit_recovers_a_known_line(self):
        """fit_slope is what turns the sweep into a −20 dB/decade test, so it
        gets its own arithmetic check rather than being trusted."""
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [10.0 - 20.0 * x for x in xs]
        m, b, r = sweep_analysis.fit_slope(xs, ys)
        self.assertAlmostEqual(m, -20.0)
        self.assertAlmostEqual(b, 10.0)
        self.assertAlmostEqual(r, -1.0)


_POINTS_BLOCK = re.compile(r"^POINTS=\(\n(.*?)^\)$", re.M | re.S)
_POINT_LINE = re.compile(r'^\s*"([0-9.]+) ([0-9.]+)"\s*$', re.M)
#: A `| 17.24 | 8.827 | why |` row of the README's C_u-axis table.
_README_ROW = re.compile(r"^\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|", re.M)


class SweepAxisTests(unittest.TestCase):
    """The published axis and the executed axis must be the same axis.

    The findings write-up is read against `sim/dr0019-cu-sweep/README.md`'s
    table, but the numbers come from whatever `run_sweep.sh` actually ran. An
    earlier draft of this directory published a seven-row table while the
    runner held six points -- a discrepancy invisible to every other check
    here, and one that would have silently dropped DR-0019's own rejected
    exact-boundary sizing from the experiment that exists to evaluate it.
    """

    def _runner_points(self) -> list[tuple[float, float]]:
        block = _POINTS_BLOCK.search((SWEEP / "run_sweep.sh").read_text())
        self.assertIsNotNone(block, "run_sweep.sh has no POINTS=( ... ) array")
        points = [
            (float(cu), float(scale)) for cu, scale in _POINT_LINE.findall(block.group(1))
        ]
        self.assertTrue(points, "POINTS parsed empty")
        return points

    def _readme_rows(self) -> list[tuple[float, float]]:
        text = (SWEEP / "README.md").read_text()
        start = text.index("### The C_u axis")
        end = text.index("### The orthogonal control")
        return [
            (float(cu), float(c_side))
            for cu, c_side in _README_ROW.findall(text[start:end])
        ]

    def test_readme_table_lists_exactly_the_swept_c_u_values(self):
        swept = sorted(cu for cu, scale in self._runner_points() if scale == 1.0)
        published = sorted(cu for cu, _ in self._readme_rows())
        self.assertEqual(published, swept)

    def test_readme_c_side_column_is_512_times_c_u(self):
        """C_side = 512·C_u is the quantity the acquisition-RC hypothesis is
        about, so a transcription slip in this column would misstate the very
        axis the findings reason over."""
        for c_unit_ff, c_side_pf in self._readme_rows():
            with self.subTest(c_unit_ff=c_unit_ff):
                self.assertAlmostEqual(
                    c_side_pf, 512 * c_unit_ff / 1000.0, places=3
                )

    def test_the_axis_spans_and_exceeds_both_dr0019_endpoints(self):
        """An isolation that only interpolates between the two known points
        cannot tell a trend from a coincidence: the axis must bracket both
        endpoints and continue past the ratified one."""
        swept = sorted(cu for cu, scale in self._runner_points() if scale == 1.0)
        self.assertIn(variant.C_UNIT_PRE_RESIZE_FF, swept)
        self.assertIn(variant.C_UNIT_RATIFIED_FF, swept)
        self.assertEqual(min(swept), variant.C_UNIT_PRE_RESIZE_FF)
        self.assertGreater(max(swept), variant.C_UNIT_RATIFIED_FF)
        self.assertGreaterEqual(len(swept), 5)

    def test_exactly_one_orthogonal_control_point_at_the_ratified_c_u(self):
        controls = [p for p in self._runner_points() if p[1] != 1.0]
        self.assertEqual(len(controls), 1)
        c_unit_ff, scale = controls[0]
        self.assertEqual(c_unit_ff, variant.C_UNIT_RATIFIED_FF)
        # The control exists to undo the C_u growth in R_on*C_arr, so its
        # width scaling must be that growth ratio and not a round number.
        self.assertAlmostEqual(
            scale,
            variant.C_UNIT_RATIFIED_FF / variant.C_UNIT_PRE_RESIZE_FF,
            places=2,
        )


def _fake_corner_log(dc_offset: float) -> str:
    """64 coherent samples in the `m_code_sNNN` form a corner log carries."""
    import math

    lines = []
    for i in range(64):
        code = 512 + 400 * math.sin(2 * math.pi * 31 * i / 64) + dc_offset
        lines.append(f"m_code_s{i:03d} = {code:.10e}")
    return "\n".join(lines) + "\n"


def _fake_record(c_unit_ff: float) -> str:
    return textwrap.dedent(
        f"""\
        # Record

        - **Netlist provenance**: schematic (DR-0019 C_u sweep point: C_u = {c_unit_ff:.4f} fF, ratified acquisition-leg T-gate geometry)
        - **Overall: PASS**
        """
    )


class RecordCollationTests(unittest.TestCase):
    def test_a_re_run_point_is_counted_once_and_the_newest_record_wins(self):
        """`sim/` records are append-only: a timed-out or superseded sweep
        point stays on disk forever. Collating both copies would put the same
        C_u into the −20 dB/decade fit twice and weight it double, so the
        newest record for a point must be the one that is read."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records, corners = root / "records", root / "corners"
            records.mkdir()
            for record_id, offset in (
                ("20260101-000000-aaaaaaa", 0.0),
                ("20260102-000000-bbbbbbb", 7.0),
            ):
                (records / f"{record_id}.md").write_text(_fake_record(22.0))
                (corners / record_id).mkdir(parents=True)
                (corners / record_id / "ss_125c_2.97v.log").write_text(
                    _fake_corner_log(offset)
                )
            points = sweep_analysis.read_points(records, corners)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["record_id"], "20260102-000000-bbbbbbb")
        self.assertEqual(points[0]["c_unit_ff"], 22.0)
        self.assertEqual(points[0]["n_corners"], 1)

    def test_the_c_u_axis_and_its_control_stay_separate_points(self):
        """Same C_u, different acquisition-leg width: keying the dedup on C_u
        alone would silently discard the orthogonal control -- the one point
        that can tell the RC hypothesis from its two confounds."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records, corners = root / "records", root / "corners"
            records.mkdir()
            plain = _fake_record(35.6528)
            control = (
                "# Record\n\n"
                "- **Netlist provenance**: schematic (DR-0019 C_u sweep ORTHOGONAL "
                "CONTROL: C_u = 35.6528 fF with the CDAC cell's fourth-leg "
                "(acquisition) T-gate width scaled x2.068)\n"
                "- **Overall: PASS**\n"
            )
            for record_id, text in (
                ("20260101-000000-aaaaaaa", plain),
                ("20260101-010000-aaaaaaa", control),
            ):
                (records / f"{record_id}.md").write_text(text)
                (corners / record_id).mkdir(parents=True)
                (corners / record_id / "ss_125c_2.97v.log").write_text(
                    _fake_corner_log(0.0)
                )
            points = sweep_analysis.read_points(records, corners)

        self.assertEqual(len(points), 2)
        self.assertEqual(
            sorted(p["acq_switch_scale"] for p in points), [1.0, 2.068]
        )


if __name__ == "__main__":
    unittest.main()
