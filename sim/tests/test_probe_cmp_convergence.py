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


if __name__ == "__main__":
    unittest.main()
