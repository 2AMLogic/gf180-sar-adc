#!/usr/bin/env python3
"""Issue #320's readout instrument, and the structural facts its conclusion
rests on.

    python3 -m unittest discover -s sim/tests -v

Two groups, for two different failure modes of the same investigation:

* **`ReadoutRewriteTests` / `SummaryTests`** guard
  `design/sar-logic/flow/probe_code_readout.py` the same way
  `test_probe_cmp_convergence.py` guards the convergence probe: it *rewrites
  the committed testbench's control block* before handing it to ngspice, and
  `sim/sar-logic-timing-gates-ok/investigations/20260919-issue-320-...`
  cites its output as evidence. If a rename in the generator silently
  desynchronises the rewrite, the probe does not crash -- it composes a deck
  that is quietly not the readout the document describes.

* **`ConstantReferenceCodeTests`** pins issue #337's addition: the `tie`
  loop has no `tie_exp` node, so the probe supplies the reference code its
  manifest measures against (the literal 512 inside `btiedev`) into its own
  throwaway deck. Both halves are asserted against the committed text — the
  constant and the tolerance must keep tracking `btiedev` and
  `tie_code_deviation`'s own bound, and a `tie_exp` node appearing later
  must stop the substitution rather than be shadowed by it.

* **`TgateLoadTests`** pins issue #913's `--tgate-load`: investigation
  #910's E1 arm (the benign-demonstration-into-the-real-load numbers
  DR-0048 leans on) was a hand edit to a composed probe deck kept only
  under `/tmp` on one host, so a reader had to re-invent its construction.
  The flag must rebuild that construction from the committed tree — 27
  extracted `ADC_TGATE` instances on the CDAC control legs — and must add
  nothing to the deck when absent.

* **`KeepWorkspaceTests` / `TruncatedRunTests`** pin issue #973's two drift
  fixes: the workspace/classifier plumbing this script forked from the
  convergence probe (pre-#343) now comes from `probe_common.py`, so a
  relative `--keep` resolves absolute before ngspice runs inside it, and a
  truncated / OOM / fatal run exits 3 instead of printing
  `RESULT  : completed`.

* **`ExtraNodesTests`** pins issue #911's outcome: cell-internal nets
  ARE reachable through `--nodes` -- the #910 investigation's
  `xdf.x204_.net4` failed only because the flop instance is `X_204_`
  (the underscore between `x` and `204` is part of the name), and one
  bad name on a grouped `print` silently emptied every table. The tests
  guard the per-name print isolation, the named diagnostic for an
  unresolvable name, and every component of the documented example
  path against the committed functional deck, so the help text cannot
  drift back into the ambiguity that caused the misdiagnosis.

* **`ResetStructureTests`** pins the *design* facts DR-0031 rests on, read
  off the committed RTL and the committed gate netlist rather than asserted
  in prose: `start` reaches the D-cone of every `ph`/`drdy` flop and of no
  `eng`/`q`/`c` flop, so a `start` pulse of any length re-establishes the
  phase ring but leaves the engaged-weight state at its power-up value.
  That asymmetry is the entire reason the first conversion after power-up is
  not valid. If someone later adds a reset (the follow-on DR-0031 routes to
  an issue rather than doing here), these tests fail and point at the record
  that has to be revisited -- which is the intended behaviour, not a bug.

No PDK and no ngspice needed: every assertion reads committed text and
exercises pure-Python rewriting.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "design" / "sar-logic" / "flow" / "probe_code_readout.py"
RTL = REPO / "design" / "sar-logic" / "rtl" / "sar_ctrl.v"
GATE_DECK = (REPO / "sim" / "sar-logic-timing-gates-ok" / "testbench"
             / "tb_sar_logic_timing_gates_ok.spice")
TIE_DECK = (REPO / "sim" / "sar-logic-timing-gates-tie" / "testbench"
            / "tb_sar_logic_timing_gates_tie.spice")
FUNC_DECK = (REPO / "sim" / "sar-logic-functional-gates" / "testbench"
             / "tb_sar_logic_functional_gates.spice")
#: The extracted leaf E1 instantiated verbatim (note #910 SS5): the
#: `20261117-165510-3a3d361` report's remediated T-gate cell.
PARA_SPICE = (REPO / "layout" / "adc-top" / "parasitics" / "reports"
              / "20261117-165510-3a3d361" / "adc_tgate.para.spice")

probe = load_module("probe_code_readout", PROBE)


class _Tb:
    """The two `Testbench` attributes `_control` reads, nothing else."""

    def __init__(self, analyses):
        self.analyses = analyses


TRAN = ["tran 5n 8.5u 0 5n", "meas tran aerr_ok MAX v(ok_aerr) FROM=0.1u"]


class ReadoutRewriteTests(unittest.TestCase):
    def test_control_block_replaces_the_manifest_measurements(self):
        lines = probe._control(_Tb(TRAN), "ok", None, False, False)
        text = "\n".join(lines)
        self.assertIn("tran 5n 8.5u 0 5n", text)
        self.assertNotIn("meas tran", text,
                         "the readout must not re-run the manifest's scored "
                         "measurements -- only run_corners.py writes evidence")

    def test_until_rewrites_only_the_stop_time(self):
        lines = probe._control(_Tb(TRAN), "ok", "1.3u", False, False)
        tran = next(l for l in lines if l.strip().startswith("tran "))
        self.assertEqual(tran.split(), ["tran", "5n", "1.3u", "0", "5n"])

    def test_core_readout_names_the_three_nodes_the_error_is_built_from(self):
        text = "\n".join(probe._control(_Tb(TRAN), "ok", None, False, False))
        for node in ("v(ok_drdy)", "v(ok_code)", "v(ok_exp)"):
            self.assertIn(node, text)

    def test_bits_and_analog_are_opt_in(self):
        plain = "\n".join(probe._control(_Tb(TRAN), "ok", None, False, False))
        self.assertNotIn("v(ok_c9)", plain)
        self.assertNotIn("v(ok_topp)", plain)
        full = "\n".join(probe._control(_Tb(TRAN), "ok", None, True, True))
        for b in probe.BITS:
            self.assertIn(f"v(ok_{b})", full)
        for node in ("v(clk)", "v(ok_topp)", "v(ok_topn)", "v(ok_cmpo)"):
            self.assertIn(node, full)

    def test_every_printed_vector_is_also_saved(self):
        """The `save` list is what keeps an 8.5 us run inside memory; a
        printed-but-unsaved vector is an empty column, not an error."""
        for bits, analog in ((False, False), (True, False), (True, True)):
            lines = probe._control(_Tb(TRAN), "ok", None, bits, analog)
            saved = set(next(l for l in lines
                             if l.strip().startswith("save ")).split()[1:])
            printed = set()
            for line in lines:
                if line.strip().startswith("print "):
                    printed.update(line.split()[1:])
            printed.discard("n")
            self.assertLessEqual(printed, saved,
                                 f"printed but not saved (bits={bits}, "
                                 f"analog={analog}): {printed - saved}")

    def test_the_readout_nodes_all_exist_in_the_committed_deck(self):
        text = GATE_DECK.read_text()
        for node in ["ok_drdy", "ok_code", "ok_exp", "ok_topp", "ok_topn",
                     "ok_cmpo", *(f"ok_{b}" for b in probe.BITS)]:
            self.assertRegex(text, rf"\b{re.escape(node)}\b",
                             f"{node} is gone from the committed deck -- the "
                             "readout would print an empty column")

    def test_eng_nodes_the_ab_knob_forces_exist_inside_the_dut(self):
        text = GATE_DECK.read_text()
        for eng in probe.ENG:
            self.assertRegex(text, rf"\b{eng}\b",
                             f"--ic-eng-zero would force a non-existent node "
                             f"{eng}")

    def test_every_per_loop_deck_is_readable(self):
        for slug in probe.EXPERIMENTS:
            self.assertTrue((REPO / "sim" / slug / "testbench" / "tb.json")
                            .is_file(), f"sim/{slug} has no manifest")


class ConstantReferenceCodeTests(unittest.TestCase):
    """Issue #337: the `tie` loop measures against the literal 512, not
    against a `tie_exp` node, so the readout supplies one for its own
    throwaway deck. If the generator ever gives `tie` a real `tie_exp`, the
    probe must read THAT and not shadow it with a constant -- these tests
    pin both directions of that switch."""

    def test_the_ramped_loop_drives_its_own_exp_node(self):
        self.assertTrue(probe._has_exp_node(GATE_DECK.read_text(), "ok"),
                        "ok_exp is gone from the committed deck -- the "
                        "readout would silently substitute a constant")

    def test_the_tie_loop_drives_no_exp_node(self):
        self.assertFalse(
            probe._has_exp_node(TIE_DECK.read_text(), "tie"),
            "the tie deck grew a tie_exp node -- drop the constant "
            "reference and read the node instead")

    def test_the_tie_constant_is_the_code_the_manifest_measures_against(self):
        """512 is not a probe preference: it is the literal in `btiedev`."""
        text = TIE_DECK.read_text()
        m = re.search(r"^btiedev tie_dev 0 V = .*abs\(v\(tie_code\)-(\d+)\)",
                      text, re.MULTILINE)
        self.assertIsNotNone(m, "btiedev's form changed -- the readout's "
                                "constant reference code has to follow it")
        self.assertEqual(float(m.group(1)), probe.EXP_CONST_BY_TAG["tie"])

    def test_the_tie_tolerance_is_the_manifest_bound(self):
        """`--tol`'s default for `tie` is `tie_code_deviation`'s own max,
        not a rounder number: on an exact tie either adjacent code is a
        correct answer, so 1 LSB is a PASS and only >1 is wrong."""
        manifest = json.loads(
            (REPO / "sim" / "sar-logic-timing-gates-tie" / "testbench"
             / "tb.json").read_text())
        bound = manifest["checks"]["tie_code_deviation"]["max"]
        self.assertEqual(bound, probe.TOL_BY_TAG["tie"])
        self.assertEqual(probe.DEFAULT_TOL, 0.5,
                         "every other code-error check is the +-0.5 LSB "
                         "abs_err_*/err_* family")

    def test_the_injected_source_names_the_node_the_readout_prints(self):
        line = probe._exp_source("tie", 512.0)
        self.assertRegex(line, r"(?m)^btieexp tie_exp 0 V = 512$")
        self.assertTrue(
            probe._has_exp_node(line, "tie"),
            "_has_exp_node must recognise the source _exp_source emits -- "
            "otherwise the detection and the injection have drifted apart")

    def test_the_injected_source_is_a_top_level_element(self):
        """It is appended after the deck's `.ends`, so it must not be a
        control-block or subckt-scoped line."""
        line = probe._exp_source("tie", 512.0).strip().splitlines()[-1]
        self.assertFalse(line.startswith("."), line)


class TgateLoadTests(unittest.TestCase):
    """Issue #913: `--tgate-load` rebuilds note #910's E1 deck text from
    the committed tree, and touches nothing when absent. Every structural
    fact the note's benign-demonstration numbers rest on is pinned here
    against committed text, so a rename in the generator that silently
    desynchronised the flag fails a test instead of quietly loading the
    wrong nets."""

    def _instances(self, tag: str) -> list[list[str]]:
        return [l.split()
                for l in probe._tgate_load(tag, PARA_SPICE).splitlines()
                if l.startswith("Xtg_")]

    def test_one_instance_per_family_and_weight(self):
        self.assertEqual(len(self._instances("df")), 27,
                         "E1 is rel/hi/lo x 9 weights -- one transmission "
                         "gate per control leg, each consuming the leg's "
                         "own _n and _p gate legs")

    def test_every_gate_net_exists_in_the_committed_functional_deck(self):
        """`gn`/`gp` must land on THIS deck's leg nets, for both loops the
        flag may target -- a net that has drifted would silently leave the
        T-gate gate on a floating 0-V node instead of loading the leg."""
        text = FUNC_DECK.read_text()
        for tag in ("df", "se"):
            for net in probe._tgate_nets(tag):
                self.assertRegex(
                    text, rf"\b{re.escape(net)}\b",
                    f"{net} is gone from the committed deck -- "
                    f"--tgate-load would not load the leg it names")

    def test_the_pin_wiring_matches_the_extracted_subckt(self):
        """Positional pin order against the leaf's own `.SUBCKT ADC_TGATE`
        line: gn<-<leg>n, gp<-<leg>p, vdd<-vdd_gate, vin/vout<-vcm_tg,
        vsubs<-vsubs."""
        subckt = next(l for l in PARA_SPICE.read_text().splitlines()
                      if l.lower().startswith(".subckt adc_tgate"))
        pins = subckt.split()[2:]
        self.assertEqual(pins,
                         ["gn", "gp", "vdd", "vin", "vout", "vsubs"],
                         "the extracted leaf's pin order changed -- "
                         "_tgate_load's positional wiring must follow it")
        for f in self._instances("df"):
            name, model, conns = f[0], f[-1], f[1:-1]
            self.assertEqual(model, "ADC_TGATE")
            leg = name[len("Xtg_df_"):]
            self.assertEqual(
                conns, [f"df_{leg}n", f"df_{leg}p",
                        "vdd_gate", "vcm_tg", "vcm_tg", "vsubs"],
                f"{name}: pin wiring diverged from the E1 construction")

    def test_channels_body_and_supply_are_tied_as_the_note_describes(self):
        """Channels on one mid-rail node the probe never switches, `vsubs`
        grounded the way the committed extracted bench grounds it, `vdd`
        on the DUT supply -- the three terminations a reconstruction
        differing in any one of which could land the other side of the
        8.9-9.1 bound (issue #913's 'why it matters')."""
        text = probe._tgate_load("df", PARA_SPICE)
        self.assertIn("vgcm vcm_tg 0 dc {vdd_val/2}", text)
        self.assertIn("vsubsrc vsubs 0 dc 0", text)
        deck = FUNC_DECK.read_text()
        self.assertRegex(
            deck, r"(?m)^\.global vdd_gate$",
            "the T-gate vdd pin ties to the DUT supply; without the .global "
            "declaration SPICE would scope vdd_gate locally and the pfet "
            "body would float")
        self.assertRegex(
            deck, r"(?m)^vvdd_gate vdd_gate 0 dc \{vdd_val\}$",
            "the deck's own supply for the T-gate vdd pin moved -- "
            "vdd_gate is where the legs' driver is powered, not a "
            "probe preference")

    def test_the_leaf_is_included_by_resolved_absolute_path(self):
        line = next(l for l in probe._tgate_load("df", PARA_SPICE)
                    .splitlines() if l.startswith(".include "))
        self.assertEqual(
            Path(line.split('"')[1]),
            PARA_SPICE.resolve(),
            "the include must name the leaf the flag was given, resolved "
            "against the CWD the probe was invoked from")

    def test_flag_is_rejected_for_a_missing_file(self):
        with self.assertRaises(SystemExit):
            probe.main(["sar-logic-functional-gates",
                        "--tgate-load", "/nonexistent/adc_tgate.spice"])

    def test_flag_absent_leaves_the_composed_deck_byte_identical(self):
        """Without `--tgate-load` the deck handed to ngspice is exactly
        the pre-#913 composition: composed head, probe control block,
        nothing between -- asserted end-to-end against a canned
        `compose_deck` result, no PDK and no ngspice needed."""
        canned = ("* canned composed deck\n"
                  ".param vdd_val=3.3\n"
                  '.include "tb.spice"\n'
                  ".control\n  tran 1n 1u 0 1n\n.endc\n.end\n")
        written: dict[str, str] = {}

        def fake_run(argv, **kw):
            written["deck"] = Path(argv[2]).read_text()
            return mock.Mock(stdout="", stderr="", returncode=0)

        tb = probe.T.load(REPO / "sim" / "sar-logic-functional-gates")
        expected = canned[:canned.index(".control")] + "\n".join(
            probe._control(tb, "df", None, False, False))
        with mock.patch.object(probe.R, "compose_deck",
                               return_value=canned), \
             mock.patch.object(probe.R, "NGSPICE", "ngspice"), \
             mock.patch.object(probe.P, "find_pdk", return_value=object()), \
             mock.patch.object(probe.subprocess, "run", fake_run):
            rc = probe.main(["sar-logic-functional-gates", "--tag", "df"])
        # issue #973: the empty fake log carries no `n = <count>` sentinel,
        # so the shared classifier rejects it as a run that never finished
        # (exit 3) instead of falling through to "no readout table" (1)
        self.assertEqual(rc, 3)
        self.assertEqual(written["deck"], expected,
                         "the flag-absent path must add nothing to the "
                         "composed deck -- E1's A/B baseline is whatever "
                         "the committed testbench composes to, byte for "
                         "byte")

    def test_flag_combines_with_until_analog_and_nodes(self):
        """The flag appends to the composed HEAD only; `--until`,
        `--analog` and `--nodes` keep rewriting the control block
        independently of it (the note's E1 invocations use all four)."""
        canned = ("* canned composed deck\n"
                  ".param vdd_val=3.3\n"
                  '.include "tb.spice"\n'
                  ".control\n  tran 1n 64.5u 0 5n\n.endc\n.end\n")
        written: dict[str, str] = {}

        def fake_run(argv, **kw):
            written["deck"] = Path(argv[2]).read_text()
            return mock.Mock(stdout="", stderr="", returncode=0)

        with mock.patch.object(probe.R, "compose_deck",
                               return_value=canned), \
             mock.patch.object(probe.R, "NGSPICE", "ngspice"), \
             mock.patch.object(probe.P, "find_pdk", return_value=object()), \
             mock.patch.object(probe.subprocess, "run", fake_run):
            probe.main(["sar-logic-functional-gates", "--tag", "df",
                        "--until", "4.2u", "--analog", "--nodes",
                        "v(df_nside),df_drdy",
                        "--tgate-load", str(PARA_SPICE)])
        deck = written["deck"]
        self.assertIn("\nXtg_df_rel_n_256 ", deck)
        self.assertLess(deck.index("Xtg_df_rel_n_256"),
                        deck.index(".control"),
                        "the load must be wired into the netlist, not the "
                        "control block")
        tb = probe.T.load(REPO / "sim" / "sar-logic-functional-gates")
        tran = next(a for a in tb.analyses if a.split()[0] == "tran")
        fields = tran.split()
        fields[2] = "4.2u"
        self.assertIn(" ".join(fields), deck,
                      "--until must keep rewriting the stop time exactly as "
                      "it does without the flag")
        self.assertIn("v(df_nside)", deck)
        self.assertIn("v(df_drdy)", deck)


class KeepWorkspaceTests(unittest.TestCase):
    """Issue #973 drift bug 1: this probe forked the convergence probe's
    workspace handling BEFORE #343 fixed the relative `--keep` bug there, so
    `--keep keepdir` wrote `keepdir/readout_<point>.spice` but launched
    ngspice with `cwd=keepdir` holding the same RELATIVE path -- which
    ngspice then resolved a second time against the keep directory itself:
    "No such file or directory", then `no readout table in the log`, with
    the deck sitting right where it was written. The workspace must be
    resolved absolute before anything is composed in it."""

    CANNED = ("* canned composed deck\n"
              ".param vdd_val=3.3\n"
              '.include "tb.spice"\n'
              ".control\n  tran 1n 1u 0 1n\n.endc\n.end\n")

    def test_relative_keep_hands_ngspice_an_absolute_deck_path(self):
        seen: dict[str, object] = {}

        def fake_run(argv, **kw):
            seen["argv"] = list(argv)
            seen["cwd"] = kw["cwd"]
            # recorded at invocation time: the tempdir below is gone by the
            # time the assertions run
            seen["deck_existed"] = Path(argv[2]).is_file()
            return mock.Mock(stdout="", stderr="", returncode=0)

        with tempfile.TemporaryDirectory() as td:
            self.addCleanup(os.chdir, os.getcwd())
            os.chdir(td)        # a relative --keep resolves against HERE
            with mock.patch.object(probe.R, "compose_deck",
                                   return_value=self.CANNED), \
                 mock.patch.object(probe.R, "NGSPICE", "ngspice"), \
                 mock.patch.object(probe.P, "find_pdk", return_value=object()), \
                 mock.patch.object(probe.subprocess, "run", fake_run):
                probe.main(["sar-logic-timing-gates-ok",
                            "--keep", "keepdir"])
        keep = Path(td).resolve() / "keepdir"
        deck = Path(seen["argv"][2])
        self.assertTrue(deck.is_absolute(),
                        "ngspice got a RELATIVE deck path -- with cwd=work "
                        "it resolves a second time against the keep "
                        "directory itself and the run dies with 'No such "
                        "file or directory'")
        self.assertEqual(deck, keep / "readout_tt_27c_3.30v.spice")
        self.assertEqual(Path(seen["cwd"]), keep,
                         "ngspice must run inside the (resolved) keep dir")
        self.assertTrue(seen["deck_existed"],
                        "the deck ngspice was pointed at did not exist at "
                        "invocation time")


class TruncatedRunTests(unittest.TestCase):
    """Issue #973 drift bug 2: this probe's fork never received #343's run
    classifier, so its only failure tests were the `Timestep too small`
    regex and `if not rows:`. An ngspice that died some other way AFTER
    printing its `core` table -- out of memory while printing
    `--bits`/`--analog`/`--nodes`, or a non-timestep `doAnalyses:` abort
    after the first conversion's `drdy` window -- reported
    `RESULT  : completed` and exited 0. A run that produced output is not a
    run that finished (issue #341's defect class, in the instrument)."""

    CANNED = ("* canned composed deck\n"
              ".param vdd_val=3.3\n"
              '.include "tb.spice"\n'
              ".control\n  tran 1n 1u 0 1n\n.endc\n.end\n")

    #: A log whose `core` table already carries rows -- exactly the shape
    #: that used to sail past `if not rows:` into "completed".
    CORE = "\n".join([
        "---READOUT core v(ok_drdy) v(ok_code) v(ok_exp)",
        "Index\ttime\tv(ok_drdy)\tv(ok_code)\tv(ok_exp)",
        "0\t0.000000e+00\t0.0\t0.0\t507.0",
        "1\t1.000000e-06\t3.3\t507.0\t507.0",
    ])
    OOM = ("\nError: memory required (608134128 Bytes)\n"
           "       is more than memory available (607293440 Bytes)!\n"
           "\nERROR: fatal error in ngspice, exit(1)\n")

    def _readout(self, log: str) -> tuple[int, str]:
        buf = io.StringIO()

        def fake_run(argv, **kw):
            return mock.Mock(stdout=log, stderr="", returncode=1)

        with mock.patch.object(probe.R, "compose_deck",
                               return_value=self.CANNED), \
             mock.patch.object(probe.R, "NGSPICE", "ngspice"), \
             mock.patch.object(probe.P, "find_pdk", return_value=object()), \
             mock.patch.object(probe.subprocess, "run", fake_run), \
             contextlib.redirect_stdout(buf):
            rc = probe.main(["sar-logic-timing-gates-ok"])
        return rc, buf.getvalue()

    def test_oom_after_the_core_table_is_failed_not_completed(self):
        rc, out = self._readout(self.CORE + self.OOM)
        self.assertEqual(rc, 3, "an OOM kill after the core table printed "
                                "must not read as a completed run")
        self.assertIn("RESULT  : FAILED", out)
        self.assertIn("memory required", out)
        self.assertNotIn("RESULT  : completed", out)

    def test_a_log_missing_the_timepoint_count_is_failed_not_completed(self):
        """No fatal line at all -- ngspice just never reached the control
        block's last statement, so the transient did not finish either."""
        rc, out = self._readout(self.CORE)
        self.assertEqual(rc, 3)
        self.assertIn("never reached the end of the control block", out)
        self.assertNotIn("RESULT  : completed", out)

    def test_a_non_timestep_abort_line_is_failed_not_completed(self):
        """`tran simulation(s) aborted` and a non-timestep `doAnalyses:`
        line are hard-analysis-failure markers in `sim/harness/runner.py`'s
        own net; the shared classifier rejects them here too instead of
        reading the already-printed rows as a verdict."""
        rc, out = self._readout(
            self.CORE + "\ndoAnalyses: TRAN: tran: internal timestep too "
            "small\ntran simulation(s) aborted\n")
        self.assertEqual(rc, 3)
        self.assertNotIn("RESULT  : completed", out)

    def test_a_completed_log_still_completes(self):
        """The guard must not over-reject: a log carrying the `n = <count>`
        end-of-control sentinel reports `completed` exactly as before."""
        rc, out = self._readout(self.CORE + "\nn = 2.000000e+00\n")
        self.assertEqual(rc, 0)
        self.assertIn("RESULT  : completed", out)


class SummaryTests(unittest.TestCase):
    """`_windows` is what separates "the conversion was wrong" from "the
    output register was caught mid-update"; getting it wrong silently
    reattributes one mechanism to the other."""

    def test_windows_finds_each_contiguous_drdy_high_run(self):
        rows = [(0.0, 0.0, 0, 0), (1.0, 3.3, 0, 0), (2.0, 3.3, 0, 0),
                (3.0, 0.0, 0, 0), (4.0, 3.3, 0, 0)]
        self.assertEqual(probe._windows(rows, 1.65), [(1, 2), (4, 4)])

    def test_a_window_open_at_the_end_of_the_run_is_still_reported(self):
        rows = [(0.0, 0.0, 0, 0), (1.0, 3.3, 0, 0)]
        self.assertEqual(probe._windows(rows, 1.65), [(1, 1)])

    def test_settle_time_is_the_last_bit_crossing_after_the_rise(self):
        # c9 crosses at t=1.2, c0 at t=1.5; nothing after.
        bits = [(1.0, 0.0, 0.0), (1.2, 3.3, 0.0), (1.5, 3.3, 3.3),
                (2.0, 3.3, 3.3)]
        self.assertAlmostEqual(
            probe._settle_time(bits, 1.0, 2.0, 1.65), 0.5)

    def test_settle_time_is_none_when_no_bit_moves(self):
        bits = [(1.0, 3.3, 0.0), (1.5, 3.3, 0.0), (2.0, 3.3, 0.0)]
        self.assertIsNone(probe._settle_time(bits, 1.0, 2.0, 1.65))

    def test_guard_sweep_starts_at_the_committed_gate(self):
        self.assertEqual(probe.GUARDS_NS[0], 0.0,
                         "the 0 ns row IS the committed b<tag>err gate -- "
                         "without it the table has no baseline")


class ExtraNodesTests(unittest.TestCase):
    """Issue #911: cell-internal nets ARE reachable through `--nodes`; the
    #910 name failed only because the instance is `X_204_`, and the probe
    then died silently -- one bad name on a grouped `print` empties the
    whole table while the run still reports success."""

    def test_each_extra_node_prints_its_own_table(self):
        lines = probe._control(_Tb(TRAN), "ok", None, False, False,
                               ["ok_drdy", "xok.x_204_.net4"])
        self.assertIn("  echo ---READOUT extra0 v(ok_drdy)", lines)
        self.assertIn("  echo ---READOUT extra1 v(xok.x_204_.net4)", lines)
        self.assertIn("  print v(xok.x_204_.net4)", lines)
        self.assertIn("  print v(ok_drdy)", lines)
        self.assertNotIn("  print v(ok_drdy) v(xok.x_204_.net4)", lines,
                         "ngspice kills a whole `print` when any one name "
                         "on it is unresolvable -- grouping the extra "
                         "nodes reintroduces issue #911's silent empty "
                         "table")

    def test_extra_nodes_are_saved_verbatim(self):
        lines = probe._control(_Tb(TRAN), "ok", None, False, False,
                               ["ok_drdy", "v(ok_cmpo)"])
        saved = next(l for l in lines if l.strip().startswith("save "))
        self.assertIn("v(ok_drdy)", saved)
        self.assertIn("v(ok_cmpo)", saved,
                      "a pre-wrapped v(...) expression must pass through "
                      "unchanged")

    def test_a_bad_name_is_diagnosed_and_the_good_one_still_prints(self):
        log = "\n".join([
            "---READOUT core v(df_drdy) v(df_code) v(df_exp)",
            "0\t0.000000e+00\t1.0\t2.0\t3.0",
            "---READOUT extra0 v(df_drdy)",
            "0\t0.000000e+00\t1.0",
            "---READOUT extra1 v(xdf.x204_.net4)",
            "Warning from checkvalid: vector xdf.x204_.net4 is not "
            "available or has zero length.",
        ])
        tables = probe._tables(log)
        self.assertEqual(len(tables["extra0"]), 1)
        lines, unresolved = probe._extra_report(
            tables, ["df_drdy", "xdf.x204_.net4"], log)
        self.assertEqual(unresolved, ["xdf.x204_.net4"])
        joined = "\n".join(lines)
        self.assertIn("v(df_drdy): 1 timepoints", joined,
                      "the resolvable name's table must still be reported")
        self.assertIn("v(xdf.x204_.net4): NO TABLE", joined)
        self.assertIn("vector xdf.x204_.net4 is not available", joined,
                      "the diagnostic must quote ngspice's own warning")
        self.assertIn("x_204_", joined,
                      "the diagnostic must state the naming rule the name "
                      "violated (the underscore in x_204_ is part of the "
                      "instance name)")

    def test_the_documented_example_path_exists_in_the_committed_deck(self):
        """The help/docstring example `xdf.x_204_.net4` is not invented:
        every path component is read off the committed functional deck,
        so a netlist regeneration that renames any of them fails here
        instead of leaving the docs teaching a wrong name."""
        text = FUNC_DECK.read_text()
        self.assertRegex(text, r"(?m)^xdf clk df_start ",
                         "the df DUT instance is no longer `xdf` -- the "
                         "--nodes example in the help/docstring is stale")
        self.assertRegex(
            text,
            r"(?m)^X_204_ _025_ clk q4 .*gf180mcu_fd_sc_mcu7t5v0__dffq_1",
            "the q4 flop is no longer instance `X_204_` of dffq_1 -- the "
            "documented example name xdf.x_204_.net4 is stale")
        dffq = text.split(".SUBCKT gf180mcu_fd_sc_mcu7t5v0__dffq_1")[1] \
                   .split(".ENDS")[0]
        self.assertRegex(dffq, r"\bnet4\b",
                         "dffq_1 no longer declares net4 -- the documented "
                         "example node is stale")

    def test_help_and_docstring_state_the_instance_path_rule(self):
        text = PROBE.read_text()
        for fragment in ("x_204_", "case-fold"):
            self.assertIn(fragment, text,
                          f"the --nodes naming guidance lost {fragment!r} "
                          "-- issue #911 was a wrong-name misdiagnosis; "
                          "the rule must stay in the help and docstring")


class ResetStructureTests(unittest.TestCase):
    """The facts DR-0031 is built on, read off the committed sources."""

    #: Flop output -> whether `start` must reach its D cone.
    START_REACHES = {"ph": True, "drdy": True,
                     "eng": False, "q": False, "c": False}

    def setUp(self) -> None:
        self.rtl = RTL.read_text()
        self.deck = GATE_DECK.read_text()

    # ---- RTL ----------------------------------------------------------
    def test_rtl_phase_ring_is_the_only_start_seeded_state(self):
        ph_block = self.rtl.split("reg [15:0] ph;")[1].split("endmodule")[0]
        ph_always = ph_block.split("always @(posedge clk) begin")[1] \
                            .split("end")[0]
        self.assertIn("ph[0] <= start | ph[15];", ph_always)
        self.assertEqual(ph_always.count("~start"), 15,
                         "every non-zero phase must be cleared by start")

    def test_rtl_engaged_flags_are_cleared_only_by_endconv(self):
        for i in range(1, 10):
            m = re.search(rf"eng{i} <= \(arm{i} \| eng{i}\) & ~endconv;",
                          self.rtl)
            self.assertIsNotNone(
                m, f"eng{i}'s update equation changed -- DR-0031's "
                   "first-conversion contract has to be revisited")
        self.assertIn("wire endconv = ph[13];", self.rtl,
                      "endconv moved; DR-0031 derives 'exactly one "
                      "conversion' from it being ph[13]")

    def test_rtl_bit_and_output_registers_carry_no_reset_term(self):
        body = self.rtl.split("reg eng9,")[1].split("// Switch decode")[0]
        self.assertNotIn("start", body,
                         "a reset term appeared on the eng/q slices -- "
                         "DR-0031 says there is none")
        out = self.rtl.split("reg c9_r,")[1].split("assign c9 =")[0]
        self.assertNotIn("start", out,
                         "a reset term appeared on the output register -- "
                         "DR-0031 says there is none")

    # ---- gate netlist -------------------------------------------------
    def _netlist(self):
        """(driver-inputs by output net, set of flop Q nets) for the DUT.

        Every instance line is `X_<id> <pins...> <subckt>`; a
        `gf180mcu_fd_sc_mcu7t5v0` combinational cell's last five pins are
        `Z VDD VNW VPW VSS`, and `dffq_1`'s pins are `D CLK Q VDD ...`.
        """
        body = self.deck.split(".subckt sar_ctrl_a")[1].split("\n.ends")[0]
        driver: dict[str, list[str]] = {}
        flop_q: set[str] = set()
        for line in body.splitlines():
            f = line.split()
            if not f or not f[0].startswith("X_"):
                continue
            pins, model = f[1:-1], f[-1]
            if "__dffq" in model:
                driver.setdefault(pins[2], [pins[0]])    # Q <- D
                flop_q.add(pins[2])
            else:
                driver.setdefault(pins[-5], pins[:-5])   # Z <- inputs
        return driver, flop_q

    def _d_cone(self, d_net):
        """Every net feeding `d_net` combinationally (stops at a flop Q)."""
        driver, flop_q = self._netlist()
        cone, stack = set(), [d_net]
        while stack:
            net = stack.pop()
            if net in cone:
                continue
            cone.add(net)
            if net in flop_q:
                continue
            stack.extend(driver.get(net, ()))
        return cone

    def test_start_reaches_the_phase_ring_and_nothing_else(self):
        body = self.deck.split(".subckt sar_ctrl_a")[1].split("\n.ends")[0]
        flops = []
        for line in body.splitlines():
            f = line.split()
            if f and f[0].startswith("X_") and "__dffq" in f[-1]:
                flops.append((f[1], f[3]))               # D net, Q net
        self.assertEqual(len(flops), 45,
                         "the DUT no longer has 45 flops -- klt equiv's "
                         "register correspondence (rtl/README.md) changed")
        seen = {k: 0 for k in self.START_REACHES}
        for d_net, q_net in flops:
            kind = ("ph" if q_net.startswith("ph_") else
                    "drdy" if q_net == "drdy" else
                    "eng" if q_net.startswith("eng") else
                    "q" if re.fullmatch(r"q\d", q_net) else
                    "c" if re.fullmatch(r"c\d", q_net) else None)
            self.assertIsNotNone(kind, f"unclassified flop output {q_net}")
            seen[kind] += 1
            reached = "start" in self._d_cone(d_net)
            self.assertEqual(
                reached, self.START_REACHES[kind],
                f"{q_net}: start {'reaches' if reached else 'does not reach'}"
                f" its D cone, DR-0031 expects the opposite. A reset was "
                f"added or removed -- revisit spec/decision-records/"
                f"DR-0031-power-up-first-conversion-validity.md")
        self.assertEqual(seen, {"ph": 15, "drdy": 1, "eng": 9, "q": 10,
                                "c": 10},
                         "the flop census changed")


if __name__ == "__main__":
    unittest.main()
