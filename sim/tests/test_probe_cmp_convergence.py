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
