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

import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

#: Every name the committed `ADC_BLOCK` extractions give the comparator's two
#: load-resistor pins, and the tag-less net each must land on: the dotted pair
#: of the older reports (issue #118) and the underscored pair of the newest,
#: which `_latest_report("ADC_BLOCK")` selects (issue #1044).
COMPARATOR_LOAD_PINS = {
    "XCMP.pon": "xcmp_pon",
    "XCMP.pop": "xcmp_pop",
    "XCMP_pon": "xcmp_pon",
    "XCMP_pop": "xcmp_pop",
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


class ComparatorLoadPinWiringTests(unittest.TestCase):
    """`gen_extracted_core_tb._wire_pin()` wires each extracted-core pin by
    exact name and raises on one it does not know, so a renamed pin is a loud
    failure rather than a silent misconnection (issue #118).

    Issue #1044 is that refusal firing: the newest committed `ADC_BLOCK`
    extractions name the comparator's two load-resistor pins
    `XCMP_pon`/`XCMP_pop`, without the dot, so both composition entry points
    for that core raised before any simulation ran -- and every test in this
    file stayed green throughout, because all six guarded decks are `ADC_TOP`
    decks, which expose neither pin. These tests compose both entry points
    against the committed extraction itself.

    Stdlib-only like the rest of this file: deck composition reads nothing but
    the committed report, so the `Pdk` is a path-only stand-in and nothing is
    simulated."""

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    @staticmethod
    def _harness():
        sys.path.insert(0, str(REPO / "sim"))
        from harness import corners, pdk  # noqa: PLC0415  (path-dependent import)

        return corners, pdk

    @staticmethod
    def _smoke_verifier():
        sys.path.insert(0, str(PARASITICS_DIR))
        import verify_extracted_core_conversion  # noqa: PLC0415  (path-dependent)

        return verify_extracted_core_conversion

    @staticmethod
    def _subckt_pins(deck: str, top: str) -> list[str]:
        """The pin list of the `.SUBCKT <top>` line, in order -- the positional
        reference its `Xdut` instance is wired against."""
        for line in deck.splitlines():
            tokens = line.split()
            if [t.upper() for t in tokens[:2]] == [".SUBCKT", top.upper()]:
                return tokens[2:]
        raise AssertionError(f"no .SUBCKT {top} line in the deck")

    def _instance(self, deck: str, name: str) -> list[str]:
        """`name`'s tokens: its own line plus the `+` continuation lines
        `gen_sar_logic._wrap()` splits a long instance over."""
        lines = deck.splitlines()
        starts = [i for i, line in enumerate(lines) if line.split()[:1] == [name]]
        self.assertEqual(len(starts), 1, f"expected one {name} instance")
        tokens = lines[starts[0]].split()
        for line in lines[starts[0] + 1 :]:
            if not line.startswith("+"):
                break
            tokens += line[1:].split()
        return tokens

    def assert_load_pins_wired(self, deck: str) -> None:
        """`Xdut ... ADC_BLOCK` connects each comparator load pin, at its own
        `.SUBCKT` position, to its dedicated net."""
        pins = self._subckt_pins(deck, "ADC_BLOCK")
        dut = self._instance(deck, "Xdut")
        self.assertEqual(dut[-1], "ADC_BLOCK")
        nets = dut[1:-1]
        self.assertEqual(len(nets), len(pins), "Xdut arity differs from .SUBCKT")
        self.assertEqual(
            {pin: net for pin, net in zip(pins, nets) if pin in COMPARATOR_LOAD_PINS},
            {"XCMP_pon": "ex_xcmp_pon", "XCMP_pop": "ex_xcmp_pop"},
        )

    def test_every_spelling_lands_on_its_own_dedicated_net(self):
        """The dotted spellings map to the same nets the underscored ones do."""
        core = self._core()
        for pin, net in COMPARATOR_LOAD_PINS.items():
            with self.subTest(pin=pin):
                self.assertEqual(core._wire_pin(pin, "t9"), f"t9_{net}")

    def test_unknown_comparator_pin_still_raises(self):
        """The branch stays an exact match: a near-miss falls through to the
        refuse-to-guess `ValueError` instead of being caught by it."""
        core = self._core()
        for pin in ("XCMP_pom", "XCMP.pom"):
            with self.subTest(pin=pin):
                with self.assertRaises(ValueError):
                    core._wire_pin(pin, "t9")

    def test_library_and_core_composes_the_committed_adc_block(self):
        """`gen_extracted_core_tb.library_and_core("ADC_BLOCK")` -- the deck
        behind that generator's own `--top ADC_BLOCK`."""
        text, _pins = self._core().library_and_core("ADC_BLOCK")
        self.assert_load_pins_wired(text)

    def test_conversion_smoke_deck_composes_the_committed_adc_block(self):
        """`verify_extracted_core_conversion.compose_deck("ADC_BLOCK", ...)` --
        the deck behind that script's `--top ADC_BLOCK`."""
        corners, pdk = self._harness()
        path_only = pdk.Pdk(
            path=Path("/nonexistent/gf180mcuD"), variant="gf180mcuD", source="test"
        )
        deck, _decode_ns = self._smoke_verifier().compose_deck(
            "ADC_BLOCK", path_only, corners.CORNERS["tt"], 27.0, 3.3
        )
        self.assert_load_pins_wired(deck)


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
    deleting a comment.

    Issue #1027 closed a second silent drop of the same shape: the `v(x)`
    half of that regex was a private copy of `harness.runner`'s, and the two
    disagreed on a node name beginning with a digit (`v(12)`). The harness
    now owns the one definition and this module imports it; the tests below
    keep the two save lists agreeing and keep the private copy gone."""

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    @staticmethod
    def _harness():
        sys.path.insert(0, str(REPO / "sim"))
        from harness import runner, testbench  # noqa: PLC0415  (path-dependent import)

        return runner, testbench

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
        for text in (
            "meas tran d MAX v(topp,topn)",
            "meas tran d MAX v(12,ref)",
            "meas tran d MAX par('v(a)*2')",
        ):
            with self.subTest(form=text):
                with self.assertRaises(ValueError):
                    core.measured_vectors({"analyses": [text]})

    def test_digit_leading_node_names_are_derived(self):
        """An extracted netlist can name a node `12`. The harness's save list
        already reads `v(12)`, but the private matcher this module used to
        keep required a leading letter or underscore -- so beside another
        recognised reference, `v(12)` dropped out of the derived `.save` set
        without a word and the deck failed at run time on "no such vector"
        (issue #1027)."""
        core = self._core()
        manifest = {
            "analyses": [
                "tran 1n 1u",
                "meas tran peak MAX v(out)",
                "meas tran extra MAX v(12)",
            ],
            "measure": {"delta": "extra-peak"},
        }
        self.assertEqual(core.measured_vectors(manifest), ["v(12)", "v(out)"])
        self.assertEqual(
            core.saved_vectors_lines(manifest)[-1], ".save v(12) v(out)"
        )

    def test_reads_the_same_node_voltages_as_the_harness_save_list(self):
        """The two save lists keep their own policies -- this one also saves
        `i(...)`, sorts, and raises `ValueError`; the harness refuses
        `i(...)`, keeps first-seen order, and raises `UnsupportedSaveList` --
        but they must not disagree about WHICH node voltages a manifest reads,
        nor about refusing a differential one (issue #1027)."""
        core = self._core()
        runner, testbench = self._harness()

        def both(form):
            analyses = ["tran 1n 1u", f"meas tran m MAX {form}"]
            tb = testbench.Testbench(
                directory=REPO, name="x", netlist=Path("x.spice"),
                analyses=tuple(analyses), measure={},
            )
            return analyses, tb

        for form in ("v(out)", "v(12)", "v(out)-v(12)", "V(out)", "v( 12 )"):
            with self.subTest(form=form):
                analyses, tb = both(form)
                self.assertEqual(
                    sorted(runner.measured_vectors(tb)),
                    core.measured_vectors({"analyses": analyses}),
                )
        for form in ("v(topp,topn)", "v(12,topn)", "v(out,12)"):
            with self.subTest(form=form):
                analyses, tb = both(form)
                with self.assertRaises(runner.UnsupportedSaveList):
                    runner.measured_vectors(tb)
                with self.assertRaises(ValueError):
                    core.measured_vectors({"analyses": analyses})

    def test_generator_owns_no_node_voltage_matcher_of_its_own(self):
        """`harness.runner.NODE_REF_RE` is the ONE definition of what a
        node-voltage reference looks like. Checked on behaviour rather than on
        a name -- a private matcher can be spelled anything, the lesson
        `test_probes_call_the_shared_helper_and_define_no_private_copy`
        records from #954 -- so any regex this module defines that recognises
        a single-node `v(...)` fails here, whatever it is called."""
        core = self._core()
        runner, _ = self._harness()
        # Distinct compiled patterns compare equal when their source and flags match.
        private = sorted(
            name
            for name, attr in vars(core).items()
            if isinstance(attr, re.Pattern)
            and attr is not runner.NODE_REF_RE
            and attr is not runner.DIFF_NODE_REF_RE
            and attr.search("v(out) v(12)")
        )
        self.assertEqual(
            private, [],
            "re-forked the node-voltage matcher; derive .save voltages from "
            "harness.runner.NODE_REF_RE",
        )

    def test_generator_derives_saved_voltages_with_the_harness_matcher(self):
        """A cached re.compile() can give a private definition the shared identity."""
        core = self._core()
        runner, _ = self._harness()
        manifest = {"analyses": ["meas tran m MAX v(out)-v(ref)"]}
        with patch.object(runner, "NODE_REF_RE", re.compile(r"v\((ref)\)")):
            self.assertEqual(core.saved_vectors_lines(manifest)[-1], ".save v(ref)")

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
        """The point of #176: no probe may carry its own fork again. #954
        extended this to the two scripts #176's `def _meas(` grep missed --
        they spelled the same unanchored regex `_CODE_RE_TMPL` /
        `_MEAS_RE_TMPL`, so a name-based grep alone could not flag them."""
        for script, private in (
            ("probe_gain_err_settling.py", ("def _meas(",)),
            ("probe_comparator_load_short.py", ("def _meas(",)),
            ("probe_power_cmp_anomaly.py", ("def _meas(",)),
            ("verify_extracted_core_conversion.py", ("_CODE_RE_TMPL",)),
            ("measure_extracted_gain_err.py", ("_MEAS_RE_TMPL",)),
        ):
            with self.subTest(script=script):
                text = (PARASITICS_DIR / script).read_text()
                for fragment in private:
                    self.assertNotIn(fragment, text)
                self.assertIn("G.meas(", text)
                self.assertIn("import gen_extracted_core_tb as G", text)


class SharedPvtPreambleTests(unittest.TestCase):
    """`gen_extracted_core_tb.pvt_preamble()` is the single emitter of the
    PVT-corner preamble (`.param`/`.include`/`.lib`/`.temp`) for this
    directory (issue #162) -- two earlier hand-typed copies silently omitted
    `.temp` and ran PVT sweeps at ngspice's default 27 C (see
    `pvt_temp_line`'s docstring), which is the failure mode centralising the
    block exists to make fixable once. Issue #954 removed the last private
    copy, `measure_extracted_regeneration.py`'s byte-identical
    `_common_head`; this keeps any script from growing a new one."""

    def test_no_parasitics_script_hand_emits_the_preamble(self):
        for path in sorted(PARASITICS_DIR.glob("*.py")):
            if path.name == "gen_extracted_core_tb.py":
                continue
            with self.subTest(script=path.name):
                text = path.read_text()
                self.assertNotIn(
                    "design_include", text,
                    "hand-emits the PDK include line; call "
                    "gen_extracted_core_tb.pvt_preamble()/pvt_includes()",
                )
                self.assertNotIn(
                    ".temp ", text,
                    "hand-emits the .temp directive; call "
                    "gen_extracted_core_tb.pvt_preamble()/pvt_temp_line()",
                )


class SharedEmitHelperTests(unittest.TestCase):
    """`gen_extracted_core_tb.emit_generated()` is the single copy of the
    check-or-write `main()` tail that all six generators in `GENERATORS` used
    to carry privately -- three byte-identically, one with an extra `OK:`
    print, and two as hand-rolled `MISSING`/`STALE`/`up to date` variants
    (issue #780, the same consolidation as `meas()` in #176 and `run_op()`
    in #180).

    These tests pin the three things the consolidation is allowed to decide,
    because `ExtractedDecksCurrentTests` above asserts on the return code
    alone and so cannot see them:

    1. the exit status of each mode (what CI actually gates on),
    2. that `--check` writes NOTHING, ever (the committed decks under `sim/`
       are append-only evidence, so a `--check` that wrote would be a bug no
       staleness test could catch), and
    3. that a plain run writes only when the bytes would change -- the
       behaviour two of the six did not have, and the reason a regeneration
       now leaves `git status` clean.

    Stdlib-only (`tempfile`, no ngspice, no PDK), so it runs on the PDK-free
    CI path with the rest of this file."""

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    def setUp(self):
        self.emit = self._core().emit_generated
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # A not-yet-created parent, so the write path's mkdir is exercised.
        self.out = self.tmp / "testbench" / "tb.spice"

    def test_check_on_a_missing_file_is_stale_and_writes_nothing(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            status = self.emit("deck\n", self.out, check=True)
        self.assertEqual(status, 1)
        self.assertIn("STALE:", err.getvalue())
        self.assertFalse(self.out.exists(), "--check must never write")
        self.assertFalse(self.out.parent.exists(), "--check must not mkdir")

    def test_check_on_a_differing_file_is_stale_and_leaves_it_alone(self):
        self.out.parent.mkdir(parents=True)
        self.out.write_text("stale deck\n")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            status = self.emit("deck\n", self.out, check=True)
        self.assertEqual(status, 1)
        self.assertIn("STALE:", err.getvalue())
        self.assertEqual(self.out.read_text(), "stale deck\n")

    def test_check_on_a_current_file_is_clean_and_silent(self):
        self.out.parent.mkdir(parents=True)
        self.out.write_text("deck\n")
        with contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            status = self.emit("deck\n", self.out, check=True)
        self.assertEqual(status, 0)
        self.assertEqual(out.getvalue(), "", "the majority behaviour is silent")
        self.assertEqual(err.getvalue(), "")

    def test_plain_run_creates_the_file_and_its_parent(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = self.emit("deck\n", self.out)
        self.assertEqual(status, 0)
        self.assertEqual(self.out.read_text(), "deck\n")
        self.assertIn("wrote", out.getvalue())

    def test_plain_run_does_not_rewrite_an_already_current_file(self):
        """Two of the six rewrote unconditionally. `sim/` is append-only
        evidence, so a no-op regeneration must not touch the file at all --
        asserted on mtime, not just on content, because content alone cannot
        tell a skipped write from an identical one."""
        self.out.parent.mkdir(parents=True)
        self.out.write_text("deck\n")
        before = self.out.stat().st_mtime_ns
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = self.emit("deck\n", self.out)
        self.assertEqual(status, 0)
        self.assertEqual(self.out.stat().st_mtime_ns, before)
        self.assertIn("unchanged", out.getvalue())

    def test_stdout_mode_prints_the_text_and_touches_no_file(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = self.emit("deck\n", self.out, check=True, stdout=True)
        self.assertEqual(status, 0)
        self.assertEqual(out.getvalue(), "deck\n")
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.parent.exists())

    def test_message_path_is_repo_relative_for_a_path_inside_the_repo(self):
        """The generators' own messages named the deck repo-relatively; the
        absolute-path fallback exists only for a path outside the repo (the
        tmpdirs above would otherwise raise instead of printing)."""
        core = self._core()
        deck_rel = GENERATORS["timing_budget"][1]
        self.assertEqual(core._repo_rel(REPO / deck_rel), deck_rel)
        self.assertEqual(core._repo_rel(self.out), str(self.out))

    def test_generators_call_the_shared_helper_and_define_no_private_tail(self):
        """The point of #780: no generator may carry its own fork again.

        `write_text` is the structural tell rather than a list of the removed
        message strings -- a generator that still decides for itself whether
        to write the deck has re-forked the tail no matter how it words the
        status line, and none of the six has any other reason to write a
        file (verified: zero `write_text` call sites across all six)."""
        for script, _out in sorted(GENERATORS.values()):
            with self.subTest(script=script):
                text = (PARASITICS_DIR / script).read_text()
                self.assertIn("G.emit_generated(", text)
                self.assertIn("import gen_extracted_core_tb as G", text)
                self.assertNotIn(
                    "write_text", text,
                    f"{script} writes its own deck -- re-forked the #780 tail",
                )


class SharedShadowReferenceTests(unittest.TestCase):
    """`gen_adc_top` holds the ONE definition of the ideal-shadow reference
    both benches measure converter error against: the two weighted DAC
    sources, the differential residue, the input-referred error and the
    strobe-gated |err| (issue #1043).

    `gen_extracted_core_tb.shadow_dac_and_error()` used to carry all five as a
    byte-identical copy. Byte-identical is not shared: the copy agreed because
    someone kept it in step by hand, so a change to the DAC weights, the
    residue sign or the strobe gate took two matching edits that nothing tied
    together -- and an extracted-vs-schematic comparison could have measured
    two different references with no check the wiser. The extracted emitter
    now calls the schematic generator's functions; these tests keep it that
    way, and keep the two emitters agreeing, whatever a copy is called."""

    #: The schematic generator's four emitters, and which of the five sources
    #: each one owns.
    SOURCES = (
        "shadow_dac",
        "shadow_residue",
        "shadow_error",
        "shadow_gated_error",
    )

    #: One source-level tell per B-source: a formula retyped under any
    #: function or variable name still carries its own.
    TELLS = (
        ("b{tag}dac<p|n>", (")*vcm+v(", "(1.0/512)*(")),
        ("b{tag}di", ("dacp)-v(",)),
        ("b{tag}e", ("di)-(v(",)),
        ("b{tag}ea", ("abs(v(",)),
    )

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    @staticmethod
    def _spice(lines) -> list[str]:
        return [ln for ln in lines if ln.strip() and not ln.startswith("*")]

    def test_extracted_block_follows_the_schematic_generator(self):
        """Replace one of the schematic generator's definitions and the
        extracted block must carry the replacement -- each of the four in
        turn, so the block keeps no private copy of any of the five sources."""

        def sentinel(_name):
            def emit(tag):
                return [f"sentinel {_name} {tag}"]

            return emit

        core = self._core()
        for name in self.SOURCES:
            with self.subTest(source=name), patch.object(
                core.gtop, name, sentinel(name)
            ):
                lines = self._spice(core.shadow_dac_and_error("ex", gated=True))
                self.assertIn(f"sentinel {name} ex", lines)

    def test_both_emitters_agree_for_the_same_tag(self):
        """The comparison contract: for one tag, the extracted block's SPICE
        lines are exactly the five B-sources `_core()` emits, comments aside.
        Only then are the extracted core and the schematic core measured
        against the same reference."""
        core = self._core()
        for tag in ("se", "ex"):
            with self.subTest(tag=tag):
                core_text = "\n".join(core.gtop._core(tag, "{vdd_val}")) + "\n"
                shadow = core_text.split("* ---- the ideal shadow", 1)[1]
                shadow = shadow.split("\n", 1)[1]
                schematic = self._spice(
                    shadow.split("* Decoded output code", 1)[0].splitlines()
                )
                extracted = self._spice(
                    core.shadow_dac_and_error(tag, gated=True)
                )
                self.assertEqual(extracted, schematic)
                self.assertEqual(
                    sum(line.startswith(f"b{tag}") for line in extracted), 5,
                    "expected the five shadow sources",
                )

    def test_no_parasitics_script_owns_a_copy_of_the_shadow_sources(self):
        """The next bench that needs the reference calls
        `shadow_dac_and_error()`; it does not retype the formula. A copy
        agrees on the day it is made and drifts after, which is the whole
        failure mode, so this reads the formula's own text: a copy survives it
        only by being a different formula."""
        for path in sorted(PARASITICS_DIR.glob("*.py")):
            with self.subTest(script=path.name):
                text = path.read_text()
                for source, tells in self.TELLS:
                    for tell in tells:
                        self.assertFalse(
                            tell in text,
                            f"{path.name} retypes {source}'s formula "
                            f"({tell!r}); call "
                            "gen_extracted_core_tb.shadow_dac_and_error()",
                        )


class SharedLibraryAndCoreTests(unittest.TestCase):
    """`gen_extracted_core_tb.library_and_core()` is the single emitter of the
    comparator + SAR-controller library, the extracted core's `.SUBCKT` and
    the wired conversion chain for the three `se`-tagged #13 decks (issue
    #1091).

    Each of the three generators assembled the four pieces itself, in the
    helper's order and with the helper's separators. They agreed because
    someone kept three copies in step by hand -- the failure mode behind the
    emit tail (#780) and the shadow sources (#1043). The helper now takes the
    caller's tag, and these tests keep the three generators on it.

    Scoped to those three on purpose: their manifests read `se_*` nets and
    their committed decks are byte-guarded above, which is what the second
    test compares against."""

    SE_DECKS = ("inl_dnl", "enob_fft", "power")

    FORK_TELLS = (
        "G.core_pins(",
        "G._core_extracted(",
        "gtop.comparator_block()",
        "gtop.sar.library()",
    )

    @staticmethod
    def _core():
        sys.path.insert(0, str(PARASITICS_DIR))
        import gen_extracted_core_tb  # noqa: PLC0415  (path-dependent import)

        return gen_extracted_core_tb

    def test_se_decks_assemble_the_library_through_the_shared_helper(self):
        """A generator that fetches the pins or the library pieces itself has
        re-forked the assembly, whatever order and separators it gives them;
        `--check` cannot see that while the copy still agrees."""
        for name in self.SE_DECKS:
            script, _out = GENERATORS[name]
            with self.subTest(deck=name):
                text = (PARASITICS_DIR / script).read_text()
                self.assertIn(
                    "G.library_and_core(",
                    text,
                    f"{script} does not call gen_extracted_core_tb.library_and_core()",
                )
                for fork in self.FORK_TELLS:
                    self.assertNotIn(
                        fork,
                        text,
                        f"{script} assembles the library or the chain itself "
                        f"({fork!r}); call "
                        "gen_extracted_core_tb.library_and_core(top, tag=TAG)",
                    )

    def test_each_se_deck_carries_the_helpers_se_text_once(self):
        """What the three decks are made of: `library_and_core(tag="se")`,
        inserted verbatim, single terminating newline included, so its
        library and chain occur once, under the `se` names the manifests
        read."""
        text, _pins = self._core().library_and_core("ADC_TOP", tag="se")
        for name in self.SE_DECKS:
            with self.subTest(deck=name):
                deck = (REPO / GENERATORS[name][1]).read_text()
                self.assertEqual(
                    deck.count(text),
                    1,
                    f"{GENERATORS[name][1]} does not carry the helper's `se` "
                    "text exactly once",
                )


if __name__ == "__main__":
    unittest.main()
