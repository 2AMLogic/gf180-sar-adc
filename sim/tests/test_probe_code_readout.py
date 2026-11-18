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

import json
import re
import unittest
from pathlib import Path
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
