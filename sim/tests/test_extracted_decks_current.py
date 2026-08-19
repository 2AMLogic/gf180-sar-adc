#!/usr/bin/env python3
"""Every post-layout `gen_extracted_*_tb.py` generator and its committed
deck must agree -- issue #123, extended to the last two generators by #131.

    python3 -m unittest discover -s sim/tests -v

`layout/adc-top/parasitics/gen_extracted_{inl_dnl,enob_fft,power,
switch_ron,dr0014_sampling,timing_budget}_tb.py` each implement a `--check`
mode (mirroring
`design/adc-top/gen_adc_top.py --check`, guarded by
`test_adc_top_netlist.py`), but nothing wired those checks into CI: three of
the first four decks drifted a full extraction generation (158 -> 2938
parasitic R elements, i.e. the pre-`875eac3`-pin star-split topology vs the
`klayout-tools#593` in-path topology that pin bump landed) without anyone
noticing until issue #123 was filed, because no test or workflow ever called
`--check`.

Issue #123's fix covered four of the six generators in that directory;
`dr0014_sampling` and `timing_budget` were left uncovered, which is exactly
the "silent gap" the `GENERATORS` comment below warns about -- the next
`layout/toolchain.json` pin bump could have drifted them a full extraction
generation in silence. Issue #131 closes that: all six are guarded here.

Like `test_adc_top_netlist.py`, this needs neither ngspice nor the PDK --
each generator only re-derives its output text from
`layout/adc-top/parasitics/reports/` (committed) and diffs it against the
committed `sim/*/testbench/*.spice` file, so it runs on the PDK-free CI path
on every pull request (`sim/selftest.sh` stage 1 /
`python3 -m unittest discover -s sim/tests -t sim/tests`).
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PARASITICS_DIR = REPO / "layout" / "adc-top" / "parasitics"

#: (generator script, committed output it checks) -- kept explicit rather than
#: globbed, so a generator added to the directory without a matching entry
#: here is a silent gap, not a silently-covered one.
GENERATORS = {
    "inl_dnl": (
        "gen_extracted_inl_dnl_tb.py",
        "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice",
    ),
    "enob_fft": (
        "gen_extracted_enob_fft_tb.py",
        "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice",
    ),
    "power": (
        "gen_extracted_power_tb.py",
        "sim/adc-power/testbench/tb_adc_power_extracted.spice",
    ),
    "switch_ron": (
        "gen_extracted_switch_ron_tb.py",
        "sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice",
    ),
    # Writes into a SIBLING testbench directory (`testbench-extracted/`), not
    # `testbench/`, because its manifest is explicitly scoped to Groups A+C --
    # see gen_extracted_dr0014_sampling_tb.py's "Why a second testbench
    # directory" section. Same experiment directory either way.
    "dr0014_sampling": (
        "gen_extracted_dr0014_sampling_tb.py",
        "sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice",
    ),
    "timing_budget": (
        "gen_extracted_timing_budget_tb.py",
        "sim/timing-budget-closure/testbench/tb_timing_budget_closure_extracted.spice",
    ),
}


class ExtractedDecksCurrentTests(unittest.TestCase):
    """Anti-drift check: each generator's `--check` must exit 0 against the
    committed deck it targets. Regenerate (no flags) and diff, not just
    re-parse -- same discipline as `test_adc_top_netlist.py`."""

    def test_all_generator_scripts_exist(self):
        for name, (script, _out) in sorted(GENERATORS.items()):
            with self.subTest(target=name):
                self.assertTrue(
                    (PARASITICS_DIR / script).is_file(), f"missing {script}"
                )

    def test_committed_decks_match_their_generator(self):
        for name, (script, out_rel) in sorted(GENERATORS.items()):
            with self.subTest(target=name):
                out_path = REPO / out_rel
                self.assertTrue(out_path.is_file(), f"{out_rel} is missing")
                result = subprocess.run(
                    [sys.executable, str(PARASITICS_DIR / script), "--check"],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{out_rel} is stale -- run: python3 "
                    f"{(PARASITICS_DIR / script).relative_to(REPO)}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}",
                )


class DerivedSaveSetTests(unittest.TestCase):
    """`gen_extracted_core_tb.measured_vectors()` derives each deck's `.save`
    set from its manifest with a regex that matches only single-node `v(x)` /
    `i(x)`. A differential `v(a,b)` or a `par('<expr>')` entry would fall
    OUTSIDE that regex and simply not appear in the `.save` line -- so the
    deck would be generated, committed and `--check`-clean while quietly not
    retaining a vector the run measures, surfacing much later as ngspice's
    "no such vector" plus a missing measurement.

    Issue #131 made that refusal explicit rather than silent; these tests keep
    it that way, so a future manifest cannot reintroduce the silent drop by
    deleting a comment."""

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    def test_single_node_refs_are_derived(self):
        core = self._core()
        self.assertEqual(
            core.measured_vectors(
                {
                    "analyses": ["meas tran a MAX v(topp) FROM=1u", "tran 1n 1u"],
                    "measure": {"m": "i(vvdd)"},
                }
            ),
            ["i(vvdd)", "v(topp)"],
        )

    def test_differential_and_par_refs_raise(self):
        core = self._core()
        for text in ("meas tran d MAX v(topp,topn)", "meas tran d MAX par('v(a)*2')"):
            with self.subTest(form=text):
                with self.assertRaises(ValueError):
                    core.measured_vectors({"analyses": [text]})

    def test_every_guarded_deck_saves_its_manifests_vectors(self):
        """The committed `.save` line of each deck that carries one must name
        exactly the vectors that deck's own manifest reads -- the derivation
        actually reaching the committed artefact, not just the function."""
        core = self._core()
        pairs = {
            "dr0014_sampling": (
                "sim/dr0014-sampling/testbench-extracted/tb.json",
                GENERATORS["dr0014_sampling"][1],
            ),
            "timing_budget": (
                "sim/timing-budget-closure/testbench/tb.json",
                GENERATORS["timing_budget"][1],
            ),
        }
        for name, (manifest_rel, deck_rel) in sorted(pairs.items()):
            with self.subTest(target=name):
                manifest = json.loads((REPO / manifest_rel).read_text())
                saved = [
                    line
                    for line in (REPO / deck_rel).read_text().splitlines()
                    if line.startswith(".save ")
                ]
                self.assertEqual(len(saved), 1, f"{deck_rel}: expected one .save")
                self.assertEqual(
                    saved[0].split()[1:], core.measured_vectors(manifest)
                )


class SharedMeasHelperTests(unittest.TestCase):
    """`gen_extracted_core_tb.meas()` is the single copy of the ngspice
    result-scraper that `probe_gain_err_settling.py`,
    `probe_comparator_load_short.py` and `probe_power_cmp_anomaly.py` each
    used to define privately, byte-identically, as `_meas()` (issue #176).

    These tests pin the exact semantics those three probes were relying on,
    so the consolidation is demonstrably behaviour-preserving and a future
    tightening (anchoring to `^name = value$` the way
    `harness.runner.parse_measurements` does, accepting `inf` literals) has
    to change them deliberately rather than silently altering what three
    recorded PVT campaigns' numbers meant. Stdlib-only: no ngspice, no PDK,
    so it runs on the PDK-free CI path."""

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    def test_parses_the_forms_ngspice_actually_prints(self):
        meas = self._core().meas
        for text, name, want in (
            ("elo = 1.5", "elo", 1.5),
            ("elo=1.5", "elo", 1.5),  # no surrounding whitespace
            ("elo   =   -4.5e-05", "elo", -4.5e-05),  # padded, sci notation
            ("other = 1\nicmp00 = 2.5e-06\n", "icmp00", 2.5e-06),  # multiline
            ("  elo = 3 (trailing text)", "elo", 3.0),  # unanchored on both ends
            ("elo = 1.0\nelo = 2.0", "elo", 1.0),  # first match wins
        ):
            with self.subTest(text=text, name=name):
                self.assertEqual(meas(text, name), want)

    def test_absent_name_is_nan_not_an_exception(self):
        """A corner that did not converge prints no line at all. The probes
        propagate the `nan` through their arithmetic and report it as a
        failed point -- they do not catch an exception, so returning `nan`
        rather than raising is load-bearing."""
        value = self._core().meas("nothing here", "elo")
        self.assertNotEqual(value, value)  # nan != nan

    def test_name_must_start_on_a_word_boundary(self):
        """The leading `\\b` is what keeps `d1` from matching inside `xd1`.
        `probe_comparator_load_short.py` scrapes single-character-suffixed
        names (`d0`..`dN`, `p0`.., `n0`..) out of a log that also carries
        node names containing them, so this is not hypothetical."""
        value = self._core().meas("xelo = 9.0", "elo")
        self.assertNotEqual(value, value)  # nan != nan

    def test_probes_call_the_shared_helper_and_define_no_private_copy(self):
        """The point of #176: no probe may carry its own fork again."""
        for script in (
            "probe_gain_err_settling.py",
            "probe_comparator_load_short.py",
            "probe_power_cmp_anomaly.py",
        ):
            with self.subTest(script=script):
                text = (PARASITICS_DIR / script).read_text()
                self.assertNotIn("def _meas(", text)
                self.assertIn("G.meas(", text)
                self.assertIn("import gen_extracted_core_tb as G", text)


if __name__ == "__main__":
    unittest.main()
