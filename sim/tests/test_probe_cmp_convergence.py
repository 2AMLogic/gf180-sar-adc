#!/usr/bin/env python3
"""The #296/#310 convergence probe's deck-rewriting must keep doing exactly
what the investigations claim it does.

    python3 -m unittest discover -s sim/tests -v

`design/sar-logic/flow/probe_cmp_convergence.py` is not a simulator wrapper
that can be eyeballed -- it *rewrites the committed testbench* before handing
it to ngspice, and two investigation documents
(`sim/sar-logic-timing-gates/investigations/20260917-issue-296-...` and
`...20260918-issue-310-...`) cite its output as evidence. If one of those
rewrites silently stops matching the committed deck -- because the generator
renames a node, drops the `* ---- loop <tag> ----` banners, or changes the
comparator output network -- the probe does not crash: it composes a deck
that is quietly *not* the A/B the document describes, and the evidence
becomes wrong rather than absent. These tests are the structural guard
against that, in the same spirit as
`test_sar_ctrl_gates_tb.py::ComparatorOutputSlewTests`.

No PDK and no ngspice needed: every assertion below reads the committed
testbench text and exercises pure-Python rewriting.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "design" / "sar-logic" / "flow" / "probe_cmp_convergence.py"
TIMING_GATES = (REPO / "sim" / "sar-logic-timing-gates" / "testbench"
                / "tb_sar_logic_timing_gates.spice")

_spec = importlib.util.spec_from_file_location("probe_cmp_convergence", PROBE)
probe = importlib.util.module_from_spec(_spec)
sys.modules["probe_cmp_convergence"] = probe
_spec.loader.exec_module(probe)


class LoopSectionTests(unittest.TestCase):
    """`--only-loops` (issue #310) is the A/B that isolates which loop carries
    the `vvdd_gate#branch` mechanism, and it works by cutting the composed
    testbench at its `* ---- loop <tag> ----` banners. If those banners move
    or the DUT `.subckt` stops following the last one, the cut silently takes
    the wrong text."""

    ALL_TAGS = ("ok", "lt", "xl", "bad", "tie")

    def setUp(self) -> None:
        self.text = TIMING_GATES.read_text()

    def test_every_timing_loop_is_a_recognisable_section(self):
        spans = probe._loop_sections(self.text)
        self.assertEqual(tuple(spans), self.ALL_TAGS,
                         "the timing deck's loop banners changed -- "
                         "--only-loops would cut the wrong text")
        # contiguous, in order, and none empty
        last_end = None
        for tag in self.ALL_TAGS:
            start, end = spans[tag]
            self.assertLess(start, end, f"{tag} section is empty")
            if last_end is not None:
                self.assertEqual(start, last_end,
                                 f"{tag} section is not contiguous with the "
                                 "previous one")
            last_end = end

    def test_shared_dut_and_library_survive_the_cut(self):
        """The loops are what gets dropped; the DUT definition, the supply
        declaration and the PDK cell library are shared and must not be."""
        only_tie = probe._only_loops(self.text, ("tie",))
        for shared in (".global vdd_gate", ".subckt sar_ctrl_a",
                       "vclk clk 0 pulse(", ".model sarl_sw"):
            self.assertIn(shared, only_tie,
                          f"--only-loops dropped shared deck text: {shared!r}")

    def test_dropped_loops_leave_no_references_behind(self):
        """A subset deck that still mentions a dropped loop's nets would be a
        different circuit than the one the investigation describes."""
        for keep in ("tie", "ok"):
            with self.subTest(keep=keep):
                cut = probe._only_loops(self.text, (keep,))
                banners = re.findall(r"^\* ---- loop (\w+) ----$", cut,
                                     re.MULTILINE)
                self.assertEqual(banners, [keep])
                dropped = [t for t in self.ALL_TAGS if t != keep]
                # the deck's own instance/source lines are all `<prefix><tag>`
                leaked = [
                    line for line in cut.splitlines()
                    if re.match(rf"^[a-z]+({'|'.join(dropped)})_", line)
                    or re.match(rf"^[a-z]+({'|'.join(dropped)}) ", line)
                ]
                self.assertEqual([], leaked[:5],
                                 f"--only-loops {keep} left dropped-loop lines")

    def test_unknown_tag_is_rejected_rather_than_silently_ignored(self):
        with self.assertRaises(SystemExit):
            probe._only_loops(self.text, ("nosuchloop",))


class ComparatorRewriteTests(unittest.TestCase):
    """`--ideal-cmp` (the #296 A side) and `--cmp-rc` (#310's tau sweep) both
    have to find the committed comparator output network. Each raises rather
    than composing a deck that does not carry the rewrite it promised."""

    def setUp(self) -> None:
        self.text = TIMING_GATES.read_text()

    def test_ideal_cmp_collapses_both_undelayed_networks(self):
        reverted, n = probe._ideal_cmp(self.text)
        self.assertEqual(n, 2, "expected exactly the ok and tie networks")
        for tag in ("ok", "tie"):
            self.assertIn(
                f"b{tag}cmp {tag}_cmpo 0 V = "
                f"v({tag}_topp) > v({tag}_topn) ? vdd_val : 0",
                reverted.splitlines(),
            )
            self.assertNotIn(f"r{tag}cmps ", reverted)
            self.assertNotIn(f"c{tag}cmpl ", reverted)

    def test_cmp_rc_retunes_values_and_nothing_else(self):
        tuned, n = probe._set_cmp_rc(self.text, "1k", "10f")
        self.assertEqual(n, 2)
        lines = tuned.splitlines()
        for tag in ("ok", "tie"):
            # the DECISION line is untouched -- #310 forbids relaxing it
            self.assertIn(
                f"b{tag}cmp {tag}_cmpd 0 V = "
                f"v({tag}_topp) > v({tag}_topn) ? vdd_val : 0", lines)
            self.assertIn(f"r{tag}cmps {tag}_cmpd {tag}_cmpo 1k", lines)
            self.assertIn(f"c{tag}cmpl {tag}_cmpo 0 10f", lines)
        # the delayed loops have no such network and must not gain one
        for tag in ("lt", "xl", "bad"):
            self.assertNotIn(f"r{tag}cmps ", tuned)

    def test_rewrites_raise_when_the_deck_no_longer_matches(self):
        """Neither rewrite may fall through to "composed the committed deck
        unchanged" -- that is the failure mode that produces a document
        citing an A/B which never happened."""
        stale = self.text.replace("cmps ", "cmpsX ")
        with self.assertRaises(SystemExit):
            probe._set_cmp_rc(stale, "1k", "10f")
        collapsed, _ = probe._ideal_cmp(self.text)
        with self.assertRaises(SystemExit):
            probe._ideal_cmp(collapsed)

    def test_a_partial_rewrite_is_reported_in_the_count(self):
        """Both undelayed loops must be rewritten together. The helpers return
        the count so the CLI prints it -- an asymmetric deck (one loop
        retuned, one not) is visible as `1` rather than `2`."""
        half = self.text.replace("rtiecmps tie_cmpd tie_cmpo",
                                 "rtiecmpsX tie_cmpd tie_cmpo")
        _, n = probe._set_cmp_rc(half, "1k", "10f")
        self.assertEqual(n, 1)


class ProbeNodeTests(unittest.TestCase):
    """The #310 readout is `cmpd` (the hard decision) NEXT TO `cmpo` (what the
    DUT sees). Printing the wrong pair is how a chattering decision would be
    mistaken for a soft one, or vice versa."""

    def setUp(self) -> None:
        self.text = TIMING_GATES.read_text()

    def test_undelayed_loops_report_decision_and_dut_facing_node(self):
        for tag in ("ok", "tie"):
            with self.subTest(tag=tag):
                groups = probe._probe_nodes(self.text, tag)
                self.assertEqual(groups[0],
                                 f"v({tag}_topp) v({tag}_topn)")
                self.assertEqual(groups[1],
                                 f"v({tag}_cmpd) v({tag}_cmpo)")

    def test_delayed_loops_report_their_pre_line_node(self):
        for tag in ("lt", "xl", "bad"):
            with self.subTest(tag=tag):
                self.assertEqual(probe._probe_nodes(self.text, tag)[1],
                                 f"v({tag}_cmpi) v({tag}_cmpo)")

    def test_ideal_cmp_deck_falls_back_to_the_single_node(self):
        reverted, _ = probe._ideal_cmp(self.text)
        self.assertEqual(probe._probe_nodes(reverted, "tie")[1],
                         "v(tie_cmpo)")


class ProbeOutputTailTests(unittest.TestCase):
    """`--tail` must keep the rows NEXT TO the abort (the last ones) and keep
    each table's own banner, or a quoted excerpt would be of the wrong table.
    `--tail 0` must stay the pre-#310 behaviour: every row."""

    LOG = "\n".join([
        "---PROBE tie.0 v(tie_topp) v(tie_topn)",
        "Index   time            v(tie_topp)     v(tie_topn)",
        "1\t1.0e-09\t1.0\t2.0",
        "2\t2.0e-09\t1.1\t2.1",
        "3\t3.0e-09\t1.2\t2.2",
        "---PROBE supply v(vdd_gate) i(vvdd_gate)",
        "Index   time            v(vdd_gate)     i(vvdd_gate)",
        "1\t1.0e-09\t3.3\t-1.0e-06",
        "2\t2.0e-09\t3.3\t-2.0e-06",
    ])

    def _emit(self, tail: int) -> list[str]:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            probe._emit_probe(self.LOG, tail)
        return buf.getvalue().splitlines()

    def test_tail_keeps_the_last_rows_of_each_table(self):
        out = self._emit(1)
        self.assertEqual(
            out,
            ["---PROBE tie.0 v(tie_topp) v(tie_topn)",
             "Index   time            v(tie_topp)     v(tie_topn)",
             "3\t3.0e-09\t1.2\t2.2",
             "---PROBE supply v(vdd_gate) i(vvdd_gate)",
             "Index   time            v(vdd_gate)     i(vvdd_gate)",
             "2\t2.0e-09\t3.3\t-2.0e-06"],
        )

    def test_tail_zero_prints_every_row(self):
        self.assertEqual(len(self._emit(0)), len(self.LOG.splitlines()))


class ControlBlockPrecisionTests(unittest.TestCase):
    """`--numdgt` (issue #332) widens the probe tables' print precision.

    It exists because at the `sf`/27 C/2.97 V abort the comparator's two input
    nodes print IDENTICALLY at the default 10 digits, so the default tables
    cannot say whether the hard sign test is reading a differential at the
    solver's `vntol` (1e-6 V) or at the floating-point ulp of a ~1.5 V node
    (~2e-16 V) -- and those two readings support opposite conclusions about
    whether any tolerance change could retire the abort.

    Two properties have to hold for that to be evidence rather than decoration:
    the default must stay byte-identical to what #296/#310 read (or every table
    those documents transcribe stops reproducing), and an out-of-range request
    must fail loudly rather than compose a deck whose precision is not what the
    reader thinks it is.
    """

    class _Tb:
        analyses = ["tran 5n 8.5u 0 5n", "meas tran dev_tie MAX v(tie_dev)"]

    def _control(self, **kw) -> list[str]:
        return probe._control(self._Tb(), None, ("tie",), False, "", **kw)

    def test_default_control_block_is_unchanged(self):
        """The #296/#310 evidence tables were read at `numdgt=10`; passing
        nothing must still emit exactly that."""
        self.assertIn("set numdgt=10", self._control())
        self.assertEqual(self._control(), self._control(numdgt=10))

    def test_requested_precision_reaches_the_control_block(self):
        self.assertIn("set numdgt=17", self._control(numdgt=17))

    def test_out_of_range_precision_is_rejected_not_clamped(self):
        """A clamped value would silently answer a different question than the
        one asked -- the same failure mode `--spice-option`'s bare-name check
        exists to prevent."""
        for bad in (9, 0, -1, 18, 64):
            with self.subTest(numdgt=bad):
                with self.assertRaises(SystemExit):
                    self._control(numdgt=bad)

    def test_precision_is_the_only_thing_the_flag_moves(self):
        """`--numdgt` must not become a second way to change the analysis or
        the probe's node list."""
        base = self._control()
        wide = self._control(numdgt=17)
        self.assertEqual(
            [ln for ln in base if not ln.startswith("set numdgt")],
            [ln for ln in wide if not ln.startswith("set numdgt")],
        )


class SaveProbedOnlyTests(unittest.TestCase):
    """`--save-probed-only` (issue #343) is a MEMORY knob, not a measurement
    one. Two properties keep it honest: off by default (so every invocation
    #296/#310/#332 recorded still composes the same deck), and when on it
    must save every vector the probe tables then read back -- a `save` list
    missing one of them would print an empty table, which `--chatter` would
    report as `(no decision/output table)` rather than as an error."""

    class _Tb:
        analyses = ["tran 5n 8.5u 0 5n", "meas tran aerr_lt MAX v(lt_aerr)"]

    LT_DECK = (REPO / "sim" / "sar-logic-timing-gates-lt" / "testbench"
               / "tb_sar_logic_timing_gates_lt.spice")

    def _control(self, **kw) -> list[str]:
        return probe._control(self._Tb(), "1.5u", ("lt",), True,
                              self.LT_DECK.read_text(), **kw)

    def test_off_by_default(self):
        self.assertEqual(self._control(), self._control(save_probed_only=False))
        self.assertFalse(any(ln.strip().startswith("save ")
                             for ln in self._control()))

    def test_save_list_covers_every_printed_vector(self):
        lines = self._control(save_probed_only=True)
        saved = next(ln for ln in lines if ln.strip().startswith("save "))
        saved_set = set(saved.split()[1:])
        printed = {v for ln in lines if ln.strip().startswith("print ")
                   for v in ln.split()[1:]}
        printed.discard("n")          # the timepoint count, not a vector
        self.assertTrue(printed, "the probe printed nothing to check against")
        self.assertEqual(printed - saved_set, set(),
                         "a printed vector is missing from the save list")

    def test_save_precedes_the_analysis(self):
        """ngspice's `save` only takes effect for an analysis that has not
        run yet."""
        lines = self._control(save_probed_only=True)
        self.assertLess(next(i for i, ln in enumerate(lines)
                             if ln.strip().startswith("save ")),
                        next(i for i, ln in enumerate(lines)
                             if ln.strip().startswith("tran ")))

    def test_it_changes_nothing_else(self):
        base = self._control()
        saved = [ln for ln in self._control(save_probed_only=True)
                 if not ln.strip().startswith("save ")]
        self.assertEqual(base, saved)


class ChatterSummaryTests(unittest.TestCase):
    """`--chatter` turns the investigation's two hand-computed figures into
    something a reader re-derives. It is therefore load-bearing evidence code:
    an off-by-one in the reversal count or a dwell that silently integrates the
    wrong column would make a *wrong* number look re-derived. Pin both against
    hand-checkable logs."""

    VDD = 3.3

    @staticmethod
    def _log(rows: list[tuple[float, float, float]], tag: str = "tie") -> str:
        """A synthetic probe log: one `<tag>.1` table of (t, cmpd, cmpo)."""
        lines = [f"---PROBE {tag}.1 v({tag}_cmpd) v({tag}_cmpo)",
                 f"Index\ttime\tv({tag}_cmpd)\tv({tag}_cmpo)"]
        lines += [f"{i}\t{t:g}\t{d:g}\t{o:g}"
                  for i, (t, d, o) in enumerate(rows)]
        return "\n".join(lines)

    def test_reversals_count_decision_changes_not_edges(self):
        # 0 -> 3.3 -> 0 -> 3.3 is three reversals across four timepoints.
        log = self._log([(0e-9, 0.0, 0.0), (1e-9, 3.3, 3.3),
                         (2e-9, 0.0, 0.0), (3e-9, 3.3, 3.3)])
        out = "\n".join(probe._chatter_summary(log, ("tie",), self.VDD))
        self.assertRegex(out, r"tie\s+4\s+3\s")

    def test_a_decision_that_never_moves_reports_zero(self):
        log = self._log([(t * 1e-9, 3.3, 3.3) for t in range(5)])
        out = "\n".join(probe._chatter_summary(log, ("tie",), self.VDD))
        self.assertRegex(out, r"tie\s+5\s+0\s")

    def test_dwell_integrates_the_dut_facing_column_in_band(self):
        # cmpo sits at 1.5 V (in the 0.8-2.5 V band) for the middle 2 ns of a
        # 4 ns run, with rails either side. Trapezoid over the indicator:
        # 0->1.5 half in (0.5 ns), 1.5->1.5 fully in (1 ns), 1.5->3.3 half
        # in (0.5 ns) = 2.000 ns.
        log = self._log([(0e-9, 0.0, 0.0), (1e-9, 0.0, 1.5),
                         (2e-9, 0.0, 1.5), (3e-9, 0.0, 3.3)])
        out = "\n".join(probe._chatter_summary(log, ("tie",), self.VDD))
        self.assertRegex(out, r"tie\s+4\s+0\s+2\.000 ns")

    def test_dwell_ignores_the_decision_node_even_when_it_is_mid_band(self):
        """`cmpd` is a hard ternary and is never legitimately mid-rail; if the
        columns were swapped, a run with a rail-clean `cmpo` would report a
        large dwell. Feed a mid-band DECISION and a railed output."""
        log = self._log([(0e-9, 1.5, 3.3), (1e-9, 1.5, 3.3),
                         (2e-9, 1.5, 3.3)])
        out = "\n".join(probe._chatter_summary(log, ("tie",), self.VDD))
        self.assertRegex(out, r"tie\s+3\s+0\s+0\.000 ns")

    def test_tail_does_not_truncate_the_summary(self):
        """`--tail` limits printing only. `_chatter_summary` parses the raw log
        itself, so the two cannot drift apart."""
        rows = [(t * 1e-9, 3.3 if t % 2 else 0.0, 0.0) for t in range(20)]
        out = "\n".join(probe._chatter_summary(self._log(rows), ("tie",),
                                               self.VDD))
        self.assertRegex(out, r"tie\s+20\s+19\s")

    def test_supply_table_is_summarised_when_present(self):
        log = self._log([(0e-9, 3.3, 3.3), (1e-9, 3.3, 3.3)]) + "\n" + "\n".join([
            "---PROBE supply v(vdd_gate) i(vvdd_gate)",
            "Index\ttime\tv(vdd_gate)\ti(vvdd_gate)",
            "0\t0\t3.3\t-5e-06",
            "1\t1e-09\t3.3\t-1.32e-03",
        ])
        out = "\n".join(probe._chatter_summary(log, ("tie",), self.VDD))
        self.assertIn("peak |i(vvdd_gate)| = 1.320 mA", out)

    def test_a_loop_with_no_table_is_reported_not_silently_skipped(self):
        out = "\n".join(probe._chatter_summary("", ("tie",), self.VDD))
        self.assertIn("no decision/output table", out)


class SpiceOptionTests(unittest.TestCase):
    """`--spice-option` (issue #310) is how the investigation separates "the
    solver cannot resolve a near-zero shared-supply branch current" from "the
    circuit did something". That distinction only holds if the flag does
    exactly two things: emit the `.options` lines it was given, and refuse
    anything it cannot emit faithfully. A silently-dropped option would read
    as "moving the tolerance changed nothing", which is the opposite
    conclusion from the one the measurement supports."""

    HEAD = "* deck\n.temp 27.0\n"

    def test_no_options_leaves_the_preamble_byte_identical(self):
        self.assertEqual(probe._with_options(self.HEAD, []), self.HEAD)

    def test_each_option_becomes_one_dot_options_line(self):
        out = probe._with_options(self.HEAD, ["abstol=1e-10", "reltol=1e-4"])
        self.assertTrue(out.startswith(self.HEAD))
        self.assertEqual(
            [ln for ln in out.splitlines() if ln.startswith(".options")],
            [".options abstol=1e-10", ".options reltol=1e-4"],
        )

    def test_a_bare_option_name_is_rejected_not_silently_emitted(self):
        """`--spice-option klu` would compose a deck ngspice accepts and then
        ignores. Rejecting it keeps a typo from being read as a null result."""
        for bad in ("klu", "", "=1e-10"):
            with self.subTest(option=bad):
                with self.assertRaises(SystemExit):
                    probe._with_options(self.HEAD, [bad])

    def test_options_land_ahead_of_the_control_block(self):
        """ngspice only honours `.options` in the deck body, so the flag has to
        append to the preamble the probe keeps, not to the control block it
        replaces."""
        out = probe._with_options(self.HEAD, ["abstol=1e-10"])
        self.assertNotIn(".control", out)
        self.assertTrue(out.rstrip().endswith(".options abstol=1e-10"))


class TieOffsetRewriteTests(unittest.TestCase):
    """`--tie-offset` (issue #322 / DR-0029) is the one rewrite in this script
    that touches the STIMULUS rather than the solver's job, so it is the one
    that could change what the deck claims if it landed on the wrong line.

    `DR-0029-tie-loop-decision-chatter.md` rejects the sub-LSB-offset
    candidate on this flag's own measured sweep, so a rewrite that quietly
    stopped offsetting the `tie` input -- or that offset the `_vinn`
    reference too, moving the common mode and leaving the differential at
    zero -- would turn that record's table into evidence of nothing."""

    TIE_DECK = (REPO / "sim" / "sar-logic-timing-gates-tie" / "testbench"
                / "tb_sar_logic_timing_gates_tie.spice")
    OK_DECK = (REPO / "sim" / "sar-logic-timing-gates-ok" / "testbench"
               / "tb_sar_logic_timing_gates_ok.spice")

    def test_only_the_tie_input_moves_on_the_five_loop_parent(self):
        text = TIMING_GATES.read_text()
        offset, n = probe._set_tie_offset(text, "1u")
        self.assertEqual(n, 1, "exactly one pinned-on-threshold input expected")
        lines = offset.splitlines()
        self.assertIn("vtiein tie_vinp 0 dc {vcm+1u}", lines)
        # the differential REFERENCE must not move with it
        self.assertIn("vtiecm tie_vinn 0 dc {vcm}", lines)
        # and no ramped loop's stimulus is touched
        for tag in ("ok", "lt", "xl", "bad"):
            self.assertIn(
                f"v{tag}in {tag}_vinp 0 pwl(0 {{vcm-4.75*lsbse}} 8u"
                f" {{vcm+3.25*lsbse}})", lines)
            self.assertIn(f"v{tag}cm {tag}_vinn 0 dc {{vcm}}", lines)

    def test_the_committed_per_loop_tie_deck_is_rewritable(self):
        """DR-0029's sweep is run on this deck, not on the parent."""
        offset, n = probe._set_tie_offset(self.TIE_DECK.read_text(), "1m")
        self.assertEqual(n, 1)
        self.assertIn("vtiein tie_vinp 0 dc {vcm+1m}", offset.splitlines())

    def test_a_deck_with_no_pinned_input_raises_rather_than_passing_through(self):
        """The failure mode worth pinning: `--tie-offset` on a deck that has
        no exact-tie loop must NOT compose the committed deck unchanged and
        report a measurement that never happened."""
        with self.assertRaises(SystemExit):
            probe._set_tie_offset(self.OK_DECK.read_text(), "1u")

    def test_the_rewrite_is_the_only_difference(self):
        text = self.TIE_DECK.read_text()
        offset, _ = probe._set_tie_offset(text, "1u")
        before = [ln for ln in text.splitlines()
                  if ln != "vtiein tie_vinp 0 dc {vcm}"]
        after = [ln for ln in offset.splitlines()
                 if ln != "vtiein tie_vinp 0 dc {vcm+1u}"]
        self.assertEqual(before, after,
                         "--tie-offset changed a line other than the pinned "
                         "input's own")


class ResultClassificationTests(unittest.TestCase):
    """A run that ngspice killed for a reason OTHER than `Timestep too small`
    must not be reported as "completed".

    Found while running issue #343's A/B: the `lossy` arm died with
    `Error: memory required (608134128 Bytes) is more than memory available`
    at t = 3.82e-07 s of a 1.5 us transient, and the probe printed
    `RESULT  : completed, no 'Timestep too small' abort` -- because the only
    failure test was the abort regex. That is the same defect class as issue
    #341 in `sim/harness/runner.py` (a measurement that parses is not a run
    that finished), in the instrument instead of the runner, and it is worse
    here: an investigation would have recorded "the lossy line converges"
    from a run that never reached a third of the window."""

    ABORT = (
        "doAnalyses: TRAN:  Timestep too small; time = 1.28656e-06, "
        'timestep = 6.25e-21: trouble with node "vvdd_gate#branch"\n'
    )
    OOM = ("Error: memory required (608134128 Bytes)\n"
           "       is more than memory available (607293440 Bytes)!\n"
           "\nERROR: fatal error in ngspice, exit(1)\n")
    DONE = "n = 3.339000e+03\n"

    def test_a_clean_run_is_completed(self):
        label, code = probe._classify("...\n" + self.DONE)
        self.assertEqual(code, 0)
        self.assertIn("completed", label)
        self.assertIn("3339", label)

    def test_a_timestep_abort_is_reported_as_an_abort(self):
        label, code = probe._classify("...\n" + self.ABORT)
        self.assertEqual(code, 1)
        self.assertIn("ABORT", label)
        self.assertIn("1.28656e-06", label)
        self.assertIn("vvdd_gate#branch", label)

    def test_an_out_of_memory_death_is_not_completed(self):
        label, code = probe._classify("...\n" + self.OOM)
        self.assertEqual(code, 3, "an OOM kill must not read as success")
        self.assertIn("FAILED", label)
        self.assertIn("memory required", label)

    def test_a_run_that_printed_no_timepoint_count_is_not_completed(self):
        """Belt and braces for a death this script has not seen yet: no
        abort, no recognised fatal line, and also no `n = <count>` -- the
        control block never reached its last statement, so the transient did
        not finish either."""
        label, code = probe._classify("Circuit: whatever\n")
        self.assertEqual(code, 3)
        self.assertIn("FAILED", label)

    def test_the_abort_wins_over_a_trailing_fatal_line(self):
        """ngspice prints its own `fatal error` banner after some aborts.
        The abort is the more specific, more useful diagnosis."""
        _, code = probe._classify(self.ABORT + "ERROR: fatal error in ngspice")
        self.assertEqual(code, 1)


class DelayLineRewriteTests(unittest.TestCase):
    """`--delay-line` / `--delay-line-rc` (issue #343) are the A/B that says
    whether the ideal lossless transmission line is the mechanism behind the
    `lt`/`xl`/`bad` `Timestep too small` aborts.

    The whole value of that A/B is that ONE thing moves between the runs. A
    rewrite that silently also moved the comparator decision, the stimulus,
    the supply or the DUT would make the investigation's table evidence for
    something other than what it says -- exactly the failure
    `ComparatorRewriteTests` guards for `--ideal-cmp`/`--cmp-rc`."""

    LT_DECK = (REPO / "sim" / "sar-logic-timing-gates-lt" / "testbench"
               / "tb_sar_logic_timing_gates_lt.spice")
    OK_DECK = (REPO / "sim" / "sar-logic-timing-gates-ok" / "testbench"
               / "tb_sar_logic_timing_gates_ok.spice")

    #: The committed `lt` delay element, verbatim.
    COMMITTED = ("tltd lt_cmpi 0 lt_cmpo 0 z0=50 td=40n",
                 "rltterm lt_cmpo 0 50")

    def setUp(self) -> None:
        self.text = self.LT_DECK.read_text()

    def test_ideal_mode_is_a_byte_identical_no_op(self):
        """The control arm has to be the committed deck itself -- if `ideal`
        reformatted `td=40n` into `td=4e-08` the A side would be a different
        file from the one the grid record was produced from."""
        same, n = probe._set_delay_line(self.text, "ideal")
        self.assertEqual(n, 1)
        self.assertEqual(same, self.text)

    def test_every_mode_keeps_the_decision_and_the_dut_facing_node(self):
        decision = ("bltcmp lt_cmpi 0 V = "
                    "v(lt_topp) > v(lt_topn) ? vdd_val : 0")
        for mode in probe.DELAY_LINE_MODES:
            with self.subTest(mode=mode):
                out, n = probe._set_delay_line(self.text, mode)
                self.assertEqual(n, 1)
                lines = out.splitlines()
                # the comparator's own hard decision is never touched
                self.assertIn(decision, lines)
                # and the DUT still reads the same node name
                self.assertIn("+ sar_ctrl_a", lines)
                self.assertTrue(
                    any(" lt_cmpo" in ln or "lt_cmpo " in ln for ln in lines))
                # nothing outside the two delay-element lines moved
                untouched = [ln for ln in lines
                             if not ln.startswith(("tltd ", "rltterm ", "oltd ",
                                                   "eltd ", "rltzs ", "lltl",
                                                   "cltl", "rltcmps ",
                                                   "cltcmpl ", ".model ltra_"))]
                self.assertEqual(
                    untouched,
                    [ln for ln in self.text.splitlines()
                     if ln not in self.COMMITTED],
                    f"--delay-line {mode} moved a line outside the delay "
                    "element")

    def test_lumped_carries_the_same_z0_and_total_delay(self):
        out, _ = probe._set_delay_line(self.text, "lumped")
        ls = [float(ln.split()[-1]) for ln in out.splitlines()
              if ln.startswith("lltl")]
        cs = [float(ln.split()[-1]) for ln in out.splitlines()
              if ln.startswith("cltl")]
        self.assertEqual(len(ls), probe.LADDER_SECTIONS)
        self.assertEqual(len(cs), probe.LADDER_SECTIONS)
        l_tot, c_tot = sum(ls), sum(cs)
        self.assertAlmostEqual((l_tot * c_tot) ** 0.5, 40e-9, places=12,
                               msg="the lumped line must carry the SAME td")
        self.assertAlmostEqual((l_tot / c_tot) ** 0.5, 50.0, places=6,
                               msg="the lumped line must carry the SAME Z0")

    def test_lossy_is_distributed_and_actually_lossy(self):
        out, _ = probe._set_delay_line(self.text, "lossy")
        model = next(ln for ln in out.splitlines()
                     if ln.startswith(".model ltra_lt"))
        self.assertIn("l=2.000000e-06", model)     # Z0*td
        self.assertIn("c=8.000000e-10", model)     # td/Z0
        self.assertIn("r=5", model)                # 0.1*Z0, the whole point
        self.assertIn("oltd lt_cmpi 0 lt_cmpo 0 ltra_lt", out.splitlines())

    def test_series_is_the_far_end_thevenin_equivalent(self):
        """Z0/2 = 50||50, and NO shunt termination: a matched line's far end
        delivers the full step, so re-adding the shunt here would divide the
        amplitude and change the logic level rather than the variable."""
        out, _ = probe._set_delay_line(self.text, "series")
        lines = out.splitlines()
        self.assertIn("rltzs lt_cmpx lt_cmpo 25", lines)
        self.assertNotIn("rltterm lt_cmpo 0 50", lines)

    def test_rc_interposes_without_moving_the_line(self):
        out, _ = probe._set_delay_line(self.text, "ideal", ("1k", "100f"))
        lines = out.splitlines()
        # the line keeps its z0/td and its matched termination ...
        self.assertIn("tltd lt_cmpi 0 lt_cmpt 0 z0=50 td=40n", lines)
        self.assertIn("rltterm lt_cmpt 0 50", lines)
        # ... and the DUT now reaches it through #296's own network
        self.assertIn("rltcmps lt_cmpt lt_cmpo 1k", lines)
        self.assertIn("cltcmpl lt_cmpo 0 100f", lines)

    def test_probe_reads_the_same_two_nodes_across_every_mode(self):
        """`--chatter` reads column 1 as the decision and column 2 as the
        DUT-facing node. If a substitution silently dropped the loop to the
        single-node fallback, the summary would report `(no decision/output
        table)` and the A/B would compare a number against a blank."""
        for mode in ("ideal", "lumped", "lossy", "series"):
            with self.subTest(mode=mode):
                out, _ = probe._set_delay_line(self.text, mode)
                self.assertEqual(probe._probe_nodes(out, "lt")[1],
                                 "v(lt_cmpi) v(lt_cmpo)")

    def test_all_three_delayed_loops_move_together_on_the_parent(self):
        out, n = probe._set_delay_line(TIMING_GATES.read_text(), "lumped")
        self.assertEqual(n, 3, "lt, xl and bad all carry a delay element")
        for tag in ("ok", "tie"):     # the undelayed loops keep #296's network
            self.assertIn(f"r{tag}cmps {tag}_cmpd {tag}_cmpo 1k",
                          out.splitlines())

    def test_a_deck_with_no_delay_element_raises_rather_than_passing_through(self):
        with self.assertRaises(SystemExit):
            probe._set_delay_line(self.OK_DECK.read_text(), "lossy")

    def test_an_unknown_mode_is_rejected(self):
        with self.assertRaises(SystemExit):
            probe._set_delay_line(self.text, "lossless-ish")

    def test_spice_suffixes_round_trip(self):
        self.assertEqual(probe._spice_float("40n"), 40e-9)
        self.assertEqual(probe._spice_float("50"), 50.0)
        self.assertEqual(probe._spice_float("1k"), 1e3)
        self.assertEqual(probe._spice_float("2meg"), 2e6)
        with self.assertRaises(SystemExit):
            probe._spice_float("fifty")


class PerLoopExperimentTests(unittest.TestCase):
    """#310's conclusion is read on the COMMITTED per-loop decks (#311/PR
    #321), not only on this script's own `--only-loops` cut of the five-loop
    parent. That only stays re-runnable while every such deck is a probe
    `choices` value AND still carries the one loop banner the probe reads its
    node names from. If #311's decomposition grows or renames a loop and this
    list is not updated, the probe rejects the new slug at the argument parser
    -- the investigation's commands stop running rather than quietly probing
    the wrong deck, which is the failure mode worth pinning."""

    SIM = REPO / "sim"

    def _committed_per_loop_slugs(self) -> list[str]:
        return sorted(
            d.name for d in self.SIM.glob("sar-logic-timing-gates-*")
            if (d / "testbench" / "tb.json").is_file()
        )

    def test_every_committed_per_loop_deck_is_probeable(self):
        slugs = self._committed_per_loop_slugs()
        self.assertTrue(slugs, "no per-loop decks found -- did #311's "
                               "decomposition move?")
        missing = [s for s in slugs if s not in probe.EXPERIMENTS]
        self.assertEqual(missing, [], f"probe EXPERIMENTS is missing {missing}; "
                                      "the #310 A/B commands would be rejected "
                                      "by argparse")

    def test_listed_per_loop_slugs_all_exist(self):
        """The converse: no stale entry naming a deck that is not committed."""
        for slug in probe.EXPERIMENTS:
            with self.subTest(slug=slug):
                self.assertTrue((self.SIM / slug / "testbench" / "tb.json").is_file(),
                                f"probe lists {slug} but sim/{slug} has no manifest")

    def test_each_per_loop_deck_carries_exactly_its_own_loop(self):
        """`main()` derives the probe's node names from the deck's own loop
        banners (`tags = tuple(_loop_sections(netlist)) or EXPERIMENTS[...]`),
        so a per-loop deck must expose exactly one banner, and it must be the
        tag its slug names."""
        for slug in self._committed_per_loop_slugs():
            tag = slug.rsplit("-", 1)[1]
            with self.subTest(slug=slug):
                deck = next((self.SIM / slug / "testbench").glob("tb_*.spice"))
                spans = probe._loop_sections(deck.read_text())
                self.assertEqual(tuple(spans), (tag,),
                                 f"sim/{slug} should hold exactly the {tag!r} "
                                 f"loop, found {tuple(spans)}")
                # and the fallback tuple agrees with what the deck says, so a
                # bannerless deck would not probe a different loop's nodes
                self.assertEqual(probe.EXPERIMENTS[slug], (tag,))

    @staticmethod
    def _circuit_lines(text: str) -> list[str]:
        """SPICE lines only -- comments and blanks carry the per-deck prose
        (#311's decomposition note vs the five-loop family note) and are not
        part of what either deck simulates."""
        return [ln for ln in text.splitlines()
                if ln.strip() and not ln.startswith("*")]

    def test_only_loops_cut_equals_the_committed_per_loop_deck(self):
        """The load-bearing one for #310's conclusion.

        The `--only-loops <tag>` rows in
        `investigations/20260918-issue-310-tie-loop-decision-chatter.md` are
        cited as measurements OF the committed per-loop decks -- i.e. as
        evidence about what `sim/run_corners.py` scores, not merely about an
        ad-hoc cut of the parent. That citation is only honest while cutting
        the five-loop parent down to one loop yields the same circuit the
        generator emits for that loop's own slug. Pin it, so a future change
        to either `_only_loops` or `gen_sar_logic._timing_body`'s `loop_tags`
        cannot silently decouple the A/B from the scored decks."""
        parent = TIMING_GATES.read_text()
        for slug in self._committed_per_loop_slugs():
            tag = slug.rsplit("-", 1)[1]
            with self.subTest(tag=tag):
                committed = next(
                    (self.SIM / slug / "testbench").glob("tb_*.spice")
                ).read_text()
                self.assertEqual(
                    self._circuit_lines(probe._only_loops(parent, (tag,))),
                    self._circuit_lines(committed),
                    f"--only-loops {tag} no longer reproduces sim/{slug}'s "
                    f"deck -- #310's per-loop A/B rows would stop being "
                    f"measurements of the deck that gets scored",
                )


if __name__ == "__main__":
    unittest.main()
