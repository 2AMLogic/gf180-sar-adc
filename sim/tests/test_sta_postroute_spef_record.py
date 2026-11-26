#!/usr/bin/env python3
"""Render tests for `design/sar-logic/flow/sta_postroute_spef_record.py` (issue #533).

The record text must not narrate findings its own audit data says are absent,
nor hardcode a klt build other than the one recorded in `ev`. Inputs are the
committed `*.sta_postroute_spef.audit.json` files (read only): one with
rejected nets, and a copy of it with the findings emptied and every corner
accepted. No `klt`, OpenROAD or PDK needed:

    python3 -m unittest discover -s sim/tests -t sim/tests

`SummaryMatchesExitStatus` (issue #1028) renders the two accepted November
receipts and checks the summary against the driver's exit status.
`TimedNetsReconciliation` (issue #1028) re-derives, from the committed DEF,
Verilog, SPEFs and receipts, every row of the AC 2 table in
`layout/adc-top/sar_ctrl/README.md`.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FLOW = REPO / "design" / "sar-logic" / "flow"
sys.path.insert(0, str(FLOW))

import spef_audit as audit  # noqa: E402
import sta_postroute_spef_record as rec  # noqa: E402

MACRO = REPO / "layout" / "adc-top" / "sar_ctrl"
SAR_CTRL = FLOW / "sar_ctrl"
REPORTS = SAR_CTRL / "reports"
RECORDS = SAR_CTRL / "records"
REJECTED_JSON = REPORTS / "20261009-131918-bf22e71c.mcu7t5v0.sta_postroute_spef.audit.json"
QUAL_JSON = REPORTS / "20261104-195336-b4950aa2.mcu7t5v0.sta_postroute_spef.audit.json"
CLEAN_JSON = REPORTS / "20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_spef.audit.json"
ACCEPTED_JSONS = (QUAL_JSON, CLEAN_JSON)
PROBE_ID = "20261126-070556-780bae77.mcu7t5v0.sar_ctrl.spef_reader_probe_tt"
PROBE_JSON = REPORTS / f"{PROBE_ID}.json"
PROBE_TCL = REPORTS / f"{PROBE_ID}.tcl"
ROUTED_DEF = MACRO / "sar_ctrl.def"
ROUTED_V = MACRO / "sar_ctrl.v"
MACRO_README = MACRO / "README.md"
SIGNOFF_README = REPO / "signoff" / "README.md"
FRESHNESS = REPO / "signoff" / "freshness.json"
WHEN = datetime.datetime(2026, 10, 16, tzinfo=datetime.timezone.utc)

FINDING_PHRASES = (
    "findings that matter",
    "Each is on a timed register path",
    "nothing on the",
    "partially annotated",
    "klayout-tools#2880 gap 1 (open)",
    "klayout-tools#2880 gaps 1 and 2",
)


def _load() -> dict:
    return json.loads(REJECTED_JSON.read_text())


def _complete(ev: dict) -> dict:
    ev = copy.deepcopy(ev)
    ev["static_audit"]["errors"] = []
    ev["static_audit"]["nets_with_errors"] = []
    ev["static_audit"]["timed_path_witness"] = {}
    ev["toolchain"]["klt"] = "9.9.9.dev1+gfeedface"
    return ev


class RejectedNetsShape(unittest.TestCase):
    def setUp(self):
        self.ev = _load()
        self.text = rec.render(self.ev, WHEN)

    def test_keeps_finding_text(self):
        for p in FINDING_PHRASES:
            self.assertIn(p, self.text)
        self.assertIn(f"nothing on the {len(self.ev['static_audit']['nets_with_errors'])} rejected nets", self.text)

    def test_klt_version_from_data(self):
        klt = self.ev["toolchain"]["klt"]
        self.assertIn(f"({klt} here,", self.text)
        self.assertIn(f"with the `{klt}` build recorded above first on `PATH`", self.text)
        self.assertNotIn("host-provisioned 0.7.0", self.text)

    def test_toolchain_pin_quotes_layout_toolchain_json(self):
        # "`layout/toolchain.json` pins `klayout-tools==0.6.0`" is hardcoded
        # prose, not render() data, so a layout pin bump would leave it stale
        # silently. The backticks make a version prefix fail to match. (The
        # "klt 0.4.0" in the same sentence is a historical fact, not a pin,
        # and is deliberately not tied to the file.)
        pin = json.loads((REPO / "layout" / "toolchain.json").read_text())["klt_install"]
        self.assertIn(f"`{pin}`", self.text)


class CompleteShape(unittest.TestCase):
    def _text(self, ev):
        return rec.render(ev, WHEN)

    def test_no_stale_findings_all_rejected_on_drivers(self):
        ev = _complete(_load())
        for c in ev["corners"]:
            c["gate_reasons"] = ["2 driver(s) with no parasitics after read_spef"]
        text = self._text(ev)
        for p in FINDING_PHRASES:
            self.assertNotIn(p, text)
        self.assertIn("2 driver(s) with no parasitics after read_spef", text.split("## What would close this")[1])

    def test_klt_version_from_data(self):
        text = self._text(_complete(_load()))
        self.assertIn("(9.9.9.dev1+gfeedface here,", text)
        self.assertIn("`9.9.9.dev1+gfeedface` build recorded above", text)
        self.assertNotIn("0.7.0", text.replace("0.7.0+g", ""))  # no hardcoded version prose
        self.assertNotIn("host-provisioned 0.7.0", text)

    def test_all_accepted(self):
        ev = _complete(_load())
        for c in ev["corners"]:
            c["accepted"] = True
            c["gate_reasons"] = []
        text = self._text(ev)
        for p in FINDING_PHRASES:
            self.assertNotIn(p, text)
        self.assertIn("every corner passed the annotation gate", text)

    def test_mixed_corners_dirty_tree(self):
        ev = _complete(_load())
        ev["working_tree_dirty"] = True
        ev["corners"][0]["accepted"] = True
        ev["corners"][0]["gate_reasons"] = []
        for c in ev["corners"][1:]:
            c["accepted"] = False
            c["gate_reasons"] = ["2 driver(s) with no parasitics after read_spef"]
        text = self._text(ev)
        self.assertIn("DIRTY at run time", text)
        self.assertNotIn("findings that matter", text)
        self.assertIn(f"{len(ev['corners']) - 1} of {len(ev['corners'])} corners", text.split("## Timing")[1])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SummaryMatchesExitStatus(unittest.TestCase):
    """The summary block states the exit status `sta_postroute_spef.py` returns
    for the evidence rendered: 0 when every corner is accepted and every
    negative control detected its own defect, 1 for a rejected corner, 2 for a
    broken control whichever way the corners went (issue #1028)."""

    @staticmethod
    def _summary(ev: dict) -> str:
        return rec.render(ev, WHEN).split("## Provenance")[0]

    @staticmethod
    def _why(summary: str) -> str:
        return summary.split("**Why rejected**")[1].split("**Negative controls**")[0]

    def test_accepted_receipts_render_success(self):
        for path in ACCEPTED_JSONS:
            with self.subTest(record=path.name[:15]):
                ev = json.loads(path.read_text())
                summary = self._summary(ev)
                self.assertIn("5 of 5 corners passed", summary)
                self.assertIn("(none rejected)", summary)
                self.assertIn("and exits 0.", summary)
                self.assertEqual(rec.exit_status(ev), 0)
                self.assertIn("no corner is rejected", self._why(summary))
                for stale in ("every corner is rejected", "exits 1", "exits 2", "GATE BROKEN", "(accepted)"):
                    self.assertNotIn(stale, summary)

    def test_only_a_clean_tree_receipt_supersedes_the_baseline(self):
        qual, clean = (json.loads(p.read_text()) for p in ACCEPTED_JSONS)
        self.assertTrue(qual["working_tree_dirty"])
        self.assertIn("does not supersede", self._summary(qual))
        self.assertIn("DIRTY at run time", self._summary(qual))
        self.assertFalse(clean["working_tree_dirty"])
        self.assertIn("This record supersedes", self._summary(clean))
        self.assertIn("not propagated-clock or RC closure", self._summary(clean))

    def test_rejected_corner_with_tt_accepted_exits_1(self):
        ev = _complete(_load())
        reason = "2 driver(s) with no parasitics after read_spef"
        self.assertEqual(ev["corners"][0]["corner"], rec.TT)
        ev["corners"][0].update({"accepted": True, "gate_reasons": []})
        for c in ev["corners"][1:]:
            c["accepted"] = False
            c["gate_reasons"] = [reason]
        summary = self._summary(ev)
        self.assertIn("and exits 1.", summary)
        self.assertIn("1 of 5 corners passed", summary)
        self.assertEqual(rec.exit_status(ev), 1)
        why = self._why(summary)
        self.assertIn(f"`{rec.TT}` is accepted", why)
        self.assertIn(reason, why)
        for c in ev["corners"][1:]:
            self.assertIn(f"`{c['corner']}`", why)
        self.assertNotIn("every corner is rejected", summary)

    def test_broken_negative_control_exits_2_whatever_the_corners_did(self):
        reason = "static SPEF/DEF/Verilog/Liberty audit has errors on nets: _010_"
        for rejected in (False, True):
            with self.subTest(rejected_corner=rejected):
                ev = json.loads(CLEAN_JSON.read_text())
                ctl = ev["negative_controls"][0]
                ctl.update({"rejected": False, "detected_specifically": False, "meaningful": False})
                ev["controls_verdict"] = "GATE BROKEN"
                if rejected:
                    ev["corners"][1].update({"accepted": False, "gate_reasons": [reason]})
                summary = self._summary(ev)
                self.assertIn("and exits 2.", summary)
                self.assertEqual(rec.exit_status(ev), 2)
                self.assertIn("GATE BROKEN", summary)
                self.assertNotIn("exits 0", summary)
                self.assertNotIn("exits 1", summary)
                if rejected:
                    self.assertIn(reason, self._why(summary))

    def test_rejected_corners_with_different_reasons_are_all_stated(self):
        ev = _complete(_load())
        self.assertEqual([c["corner"] for c in ev["corners"]][:2], [rec.TT, "ss_125C_3v00"])
        ev["corners"][0]["gate_reasons"] = ["driver A"]
        ev["corners"][1]["gate_reasons"] = ["driver B"]
        for c in ev["corners"][2:]:
            c["gate_reasons"] = ["driver A"]
        why = self._why(self._summary(ev))
        self.assertIn("other rejected corners' reasons differ and follow", why)
        self.assertIn("  - driver A\n", why)
        self.assertIn("- `ss_125C_3v00`:\n    - driver B", why)

    def test_rejected_receipt_renders_as_before(self):
        ev = _load()
        self.assertEqual(rec.exit_status(ev), 1)
        summary = self._summary(ev)
        self.assertIn("0 of 5 corners passed", summary)
        self.assertIn("every corner is rejected for these same reasons", summary)
        self.assertIn("and exits 1.", summary)
        self.assertIn("This record does not supersede", summary)

    def test_exit_status_follows_the_driver_s_own_order(self):
        tail = (FLOW / "sta_postroute_spef.py").read_text().split("    if not controls_ok:", 1)[1]
        self.assertLess(tail.index("return 2"), tail.index("if not all_ok:"))
        self.assertLess(tail.index("if not all_ok:"), tail.index("return 1"))
        self.assertLess(tail.index("return 1"), tail.rindex("return 0"))


class TimedNetsReconciliation(unittest.TestCase):
    """#486 AC 2: "the eleven aliased timed nets receive parasitics, audited
    pin mappings agree". Each row of the README's table is re-derived here from
    the committed artifacts, for both November receipts (issue #1028)."""

    #: net -> (DEF top-level PIN, driver pin, first timed load)
    TIMED_NETS = {
        "c0_r": ("c0", "_211_/Q", "_175_/I0"),
        "c1_r": ("c1", "_212_/Q", "_178_/I0"),
        "c2_r": ("c2", "_213_/Q", "_179_/I0"),
        "c3_r": ("c3", "_214_/Q", "_188_/I0"),
        "c4_r": ("c4", "_215_/Q", "_191_/I0"),
        "c5_r": ("c5", "_216_/Q", "_192_/I0"),
        "c6_r": ("c6", "_217_/Q", "_197_/I0"),
        "c7_r": ("c7", "_218_/Q", "_198_/I0"),
        "c8_r": ("c8", "_219_/Q", "_171_/I0"),
        "c9_r": ("c9", "_220_/Q", "_172_/I0"),
        "ph[15]": ("drdy", "_245_/Q", "_170_/A2"),
    }
    #: `*D_NET` total capacitance (fF), the README table's middle column.
    TOTAL_CAP_FF = {
        "c0_r": 4.296351, "c1_r": 3.577485, "c2_r": 4.084322, "c3_r": 6.215533, "c4_r": 5.268917,
        "c5_r": 3.756531, "c6_r": 4.056754, "c7_r": 4.718099, "c8_r": 4.324634, "c9_r": 3.913211,
        "ph[15]": 7.797649,
    }
    DFF = "gf180mcu_fd_sc_mcu7t5v0__dffq_1"
    DR0040 = ["clkload0/Z", "clkload1/ZN"]
    CORNERS = ("tt_025C_3v30", "ss_125C_3v00", "ff_n40C_3v60", "ss_n40C_3v00", "ff_125C_3v60")

    @classmethod
    def setUpClass(cls):
        cls.receipts = {p: json.loads(p.read_text()) for p in ACCEPTED_JSONS}
        cls.october = json.loads(REJECTED_JSON.read_text())
        cls.def_ = audit.parse_def(ROUTED_DEF.read_text())
        cls.verilog = audit.parse_verilog(ROUTED_V.read_text())

    def _spef(self, ev: dict) -> dict:
        path = REPORTS / Path(ev["extraction"]["spef"]).name
        self.assertEqual(_sha256(path), ev["extraction"]["spef_sha256"])
        return {n.name: n for n in audit.parse_spef(path.read_text()).nets}

    def test_eleven_nets_are_exactly_the_aliased_top_level_pins(self):
        nets = set(self.TIMED_NETS)
        self.assertEqual(set(self.october["static_audit"]["timed_path_witness"]), nets)
        self.assertEqual({p: n for p, n in self.def_.pins.items() if p != n},
                         {pin: net for net, (pin, _, _) in self.TIMED_NETS.items()})
        self.assertEqual(set(self.verilog.assigns),
                         {(pin, net) for net, (pin, _, _) in self.TIMED_NETS.items()})

    def test_each_net_reaches_a_register(self):
        witness = self.october["static_audit"]["timed_path_witness"]
        for net, (pin, driver, load) in self.TIMED_NETS.items():
            with self.subTest(net=net):
                self.assertTrue(witness[net].startswith(f"{net} -> {load} -> "), witness[net])
                self.assertTrue(witness[net].endswith(f"({self.DFF})"), witness[net])
                self.assertEqual(self.def_.pin_dirs[pin], "OUTPUT")

    def test_pin_mappings_agree_across_def_verilog_and_both_spefs(self):
        for path, ev in self.receipts.items():
            spef = self._spef(ev)
            for net, (pin, driver, load) in self.TIMED_NETS.items():
                with self.subTest(record=path.name[:15], net=net):
                    d, l = driver.split("/"), load.split("/")
                    self.assertEqual(sorted(self.def_.nets[net]), sorted([("PIN", pin), tuple(d), tuple(l)]))
                    self.assertEqual(self.def_.components[d[0]], self.DFF)
                    self.assertEqual(self.verilog.instances[d[0]][1]["Q"], net)
                    self.assertEqual(self.verilog.instances[l[0]][1][l[1]], net)
                    self.assertEqual(spef[net].ports, [pin])
                    self.assertCountEqual(spef[net].insts, [tuple(d), tuple(l)])

    def test_every_net_has_positive_extracted_capacitance(self):
        for path, ev in self.receipts.items():
            spef = self._spef(ev)
            self.assertEqual({n: spef[n].total_cap for n in self.TIMED_NETS}, self.TOTAL_CAP_FF,
                             msg=path.name)

    def test_reader_discarded_nothing_at_any_corner(self):
        for path, ev in self.receipts.items():
            self.assertEqual(ev["static_audit"]["errors"], [])
            self.assertEqual(ev["static_audit"]["nets_with_errors"], [])
            self.assertEqual(ev["static_audit"]["timed_path_witness"], {})
            for c in ev["corners"]:
                ann = c["spef_annotation"]
                with self.subTest(record=path.name[:15], corner=c["corner"]):
                    self.assertEqual((c["accepted"], c["gate_reasons"]), (True, []))
                    self.assertEqual((ann["design_nets_annotated"], ann["design_nets_total"]), (192, 192))
                    self.assertEqual(ann["design_nets_missing_sample"], [])
                    self.assertEqual(ann["reader_warning_count"], 0)
                    self.assertEqual(c["reader_warnings"]["touching_design"], {})
                    self.assertIs(ann["delay_changed"], True)
                    self.assertIs(ann["annotation_complete"], True)

    def test_sample_names_ten_drivers_with_their_alias_pin_and_cuts_the_eleventh(self):
        pairs = [(d, p) for net, (p, d, _) in self.TIMED_NETS.items() if net != "ph[15]"]
        expected = [x for pair in pairs for x in pair]
        self.assertEqual(len(expected), 20)
        for path, ev in self.receipts.items():
            for c in ev["corners"]:
                ann = c["spef_annotation"]
                with self.subTest(record=path.name[:15], corner=c["corner"]):
                    self.assertEqual(ann["partially_unannotated_driver_count"], 11)
                    self.assertEqual(ann["partially_unannotated_driver_sample"], expected)
        for name in ("_245_/Q", "drdy"):
            self.assertNotIn(name, expected)

    def test_dr0040_exceptions_are_separate_from_the_eleven(self):
        eleven = [d for _, (_, d, _) in self.TIMED_NETS.items()]
        for path, ev in self.receipts.items():
            proof = ev["no_net_proof"]
            self.assertEqual(proof["no_net"], self.DR0040)
            self.assertEqual(len(proof["outputs"]), proof["outputs_examined"])
            self.assertEqual(proof["inputs"]["def_sha256"], ev["inputs_sha256"]["layout/adc-top/sar_ctrl/sar_ctrl.def"])
            self.assertEqual(proof["inputs"]["verilog_sha256"], _sha256(ROUTED_V))
            for c in ev["corners"]:
                ann = c["spef_annotation"]
                with self.subTest(record=path.name[:15], corner=c["corner"]):
                    self.assertEqual(ann["unannotated_driver_count"], 2)
                    self.assertEqual(ann["floating_driver_sample"], self.DR0040)
                    self.assertEqual(ann["unannotated_driver_sample"], [])
                    self.assertFalse(set(eleven) & set(self.DR0040))

    def test_measured_timing_and_limits_at_five_corners(self):
        for path, ev in self.receipts.items():
            self.assertEqual([c["corner"] for c in ev["corners"]], list(self.CORNERS))
            for c in ev["corners"]:
                s, d = c["spef"], c["delta_spef_minus_ref"]
                with self.subTest(record=path.name[:15], corner=c["corner"]):
                    self.assertEqual((c["clock_mode"], c["ref_clock_mode"]), ("ideal", "ideal"))
                    self.assertEqual((s["setup_violation_count"], s["hold_violation_count"]), (0, 0))
                    self.assertEqual(s["timing_status"], "constrained")
                    self.assertGreater(s["worst_slack_ns"], 0)
                    self.assertGreater(s["worst_hold_slack_ns"], 0)
                    self.assertLess(d["worst_slack_ns"], 0)
                    self.assertGreater(d["worst_hold_slack_ns"], 0)
            setup = min((c["spef"]["worst_slack_ns"], c["corner"]) for c in ev["corners"])
            hold = min((c["spef"]["worst_hold_slack_ns"], c["corner"]) for c in ev["corners"])
            self.assertEqual(setup, (55.6796, "ss_125C_3v00"))
            self.assertEqual(hold, (0.72501, "ff_n40C_3v60"))
            outs = ev["output_ports_without_output_delay"]
            self.assertEqual(len(outs), 67)
            self.assertEqual(ev["input_ports_without_input_delay"], ["cmp", "mode", "start"])
            for pin, _, _ in self.TIMED_NETS.values():
                self.assertIn(pin, outs)

    def test_clean_tree_receipt_reproduces_the_qualification_run(self):
        qual, clean = (self.receipts[p] for p in ACCEPTED_JSONS)
        self.assertEqual((qual["working_tree_dirty"], clean["working_tree_dirty"]), (True, False))
        self.assertEqual(qual["extraction"]["spef_sha256"], clean["extraction"]["spef_sha256"])
        self.assertEqual(qual["inputs_sha256"], clean["inputs_sha256"])
        self.assertEqual(qual["liberty_sha256"], clean["liberty_sha256"])
        self.assertEqual(qual["toolchain"]["openroad"], clean["toolchain"]["openroad"])
        for q, c in zip(qual["corners"], clean["corners"]):
            for f in ("spef", "ref", "delta_spef_minus_ref", "spef_annotation"):
                self.assertEqual(q[f], c[f], f)
        self.assertEqual([m["meaningful"] for m in clean["negative_controls"]], [True] * 3)


def _reader_listing(text: str, begin: str, end: str) -> list:
    """The pin lines of a `report_parasitic_annotation -report_unannotated`
    block, in print order: one per unannotated driver, then one per partially
    unannotated driver each followed by the pins the reader flags on its net."""
    block = text.split(begin + "\n", 1)[1].split("\n" + end, 1)[0]
    return [line.strip() for line in block.splitlines() if not line.strip().startswith("Found ")]


class ReaderProbeEvidence(unittest.TestCase):
    """The single-corner reader probe: what OpenSTA kept for the eleven nets,
    which the receipts' 20-line sample cannot show in full."""

    def setUp(self):
        self.probe = json.loads(PROBE_JSON.read_text())
        self.receipt = json.loads(CLEAN_JSON.read_text())
        self.pairs = [[driver, [pin]] for pin, driver, _ in TimedNetsReconciliation.TIMED_NETS.values()]

    def test_probe_reads_the_receipt_s_inputs_on_the_receipt_s_engine(self):
        p, ev = self.probe, self.receipt
        ins = p["inputs_sha256"]
        self.assertEqual(ins["layout/adc-top/sar_ctrl/sar_ctrl.def"], ev["inputs_sha256"]["layout/adc-top/sar_ctrl/sar_ctrl.def"])
        self.assertEqual(ins["layout/adc-top/sar_ctrl/sar_ctrl.v"], ev["inputs_sha256"]["layout/adc-top/sar_ctrl/sar_ctrl.v"])
        spef = ev["extraction"]["spef"]
        self.assertEqual(ins[spef], ev["extraction"]["spef_sha256"])
        self.assertIn(spef, PROBE_TCL.read_text())
        self.assertEqual(ins[PROBE_TCL.relative_to(REPO).as_posix()], _sha256(PROBE_TCL))
        lib = "gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib"
        self.assertEqual(p["liberty_sha256"].removeprefix("sha256:"), ev["liberty_sha256"][lib])
        self.assertEqual(p["toolchain"]["openroad"], ev["toolchain"]["openroad"])
        self.assertEqual(p["toolchain"]["pdk"]["version"].split()[-1], ev["toolchain"]["pdk"]["open_pdks"])
        self.assertEqual(p["toolchain"]["pdk"]["name"], ev["toolchain"]["pdk"]["variant"])
        self.assertEqual(p["corner"], rec.TT)
        for field in ("openroad", "klt_sta_rerun"):
            text = p[f"{field}_stdout"]
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), p[f"{field}_stdout_sha256"])
        self.assertIn("OpenROAD " + ev["toolchain"]["openroad"], p["openroad_stdout"])

    def test_full_listing_is_the_eleven_nets_and_the_sample_cut_the_last_pair(self):
        p = self.probe
        flat = _reader_listing(p["openroad_stdout"], "===PROBE_PARASITIC_ANNOTATION_BEGIN===", "===PROBE_PARASITIC_ANNOTATION_END===")
        klt = _reader_listing(p["klt_sta_rerun_stdout"], "===KLT_STA_PARASITIC_ANNOTATION_BEGIN===", "===KLT_STA_PARASITIC_ANNOTATION_END===")
        self.assertEqual(klt, flat)
        self.assertEqual(p["parasitic_annotation"]["unannotated_drivers"], TimedNetsReconciliation.DR0040)
        self.assertEqual(p["parasitic_annotation"]["partially_unannotated_drivers"], self.pairs)
        self.assertEqual(flat[:2], TimedNetsReconciliation.DR0040)
        self.assertEqual(flat[2:], [x for pair in self.pairs for x in (pair[0], pair[1][0])])
        for path in ACCEPTED_JSONS:
            for c in json.loads(path.read_text())["corners"]:
                sample = c["spef_annotation"]["partially_unannotated_driver_sample"]
                with self.subTest(record=path.name[:15], corner=c["corner"]):
                    self.assertEqual(len(sample), 20)
                    self.assertEqual(flat[2:2 + len(sample)], sample)
        self.assertEqual(flat[-2:], ["_245_/Q", "drdy"])

    def test_klt_rerun_reproduces_the_receipt_s_tt_corner(self):
        p = self.probe
        tt = next(c for c in self.receipt["corners"] if c["corner"] == rec.TT)
        self.assertEqual(p["klt_sta_rerun"]["spef_annotation"], tt["spef_annotation"])
        t = p["klt_sta_rerun"]["timing"]
        self.assertEqual((t["worst_slack_ns"], t["worst_hold_slack_ns"]),
                         (tt["spef"]["worst_slack_ns"], tt["spef"]["worst_hold_slack_ns"]))
        self.assertEqual((t["setup_violation_count"], t["hold_violation_count"]), (0, 0))

    def test_reader_applied_the_extracted_capacitance_to_each_net(self):
        p = self.probe
        self.assertEqual(list(p["report_net"]), list(TimedNetsReconciliation.TIMED_NETS))
        for net, (pin, driver, load) in TimedNetsReconciliation.TIMED_NETS.items():
            with self.subTest(net=net):
                r = p["report_net"][net]
                self.assertEqual((r["driver"], r["port"], r["load"]["pin"]), (driver, pin, load))
                self.assertEqual(r["wire_capacitance_ff"], round(TimedNetsReconciliation.TOTAL_CAP_FF[net], 2))
                self.assertAlmostEqual(r["total_capacitance_ff"], r["wire_capacitance_ff"] + r["pin_capacitance_ff"], delta=0.011)
                self.assertEqual(r["load"]["pin_capacitance_ff"], r["pin_capacitance_ff"])
                self.assertEqual(r["driver_cell"], TimedNetsReconciliation.DFF)
        block = p["openroad_stdout"].split("===PROBE_REPORT_NET_BEGIN===\n", 1)[1]
        self.assertEqual(len(re.findall(r"^Net ", block, re.MULTILINE)), 11)
        for pin, _, _ in TimedNetsReconciliation.TIMED_NETS.values():
            self.assertRegex(block, rf"(?m)^ {re.escape(pin)} output port \(\d+, \d+\)$")


def _table(text: str, header: str) -> list:
    """Rows of the first markdown table whose header line is `header`, each
    cell stripped of padding and backticks."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    rows = []
    for line in lines[lines.index(header) + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip().strip("`") for c in line.strip().strip("|").split("|")])
    return rows


TIMING_HEADER = "| Corner | Setup slack (ns) | Hold slack (ns) | Setup/hold violators | Setup delta vs. no SPEF (ns) | Hold delta vs. no SPEF (ns) |"
TIMED_HEADER = "| Timed net | Port alias | Driver | Timed load | `*D_NET` cap (fF) | Reader wire cap (fF) | Pin the reader flags |"
CLAIM = ("SPEF-annotated, ideal clock, lumped no-R extraction, 5 corners met (setup/hold, 0 violators); "
         "not propagated-clock or RC closure")


class LiveClaimReadmes(unittest.TestCase):
    """The two README passages that carry the claim (issue #1028, scope 2)."""

    @classmethod
    def setUpClass(cls):
        cls.macro = MACRO_README.read_text()
        cls.signoff = SIGNOFF_README.read_text()
        cls.probe = json.loads(PROBE_JSON.read_text())

    def test_both_passages_link_both_receipts_and_state_the_bounded_claim(self):
        for path, text in ((MACRO_README, self.macro), (SIGNOFF_README, self.signoff)):
            flat = " ".join(text.split())
            with self.subTest(readme=path.relative_to(REPO).as_posix()):
                for p in ACCEPTED_JSONS:
                    target = RECORDS / (p.name.replace(".audit.json", ".md"))
                    self.assertTrue(target.is_file())
                    self.assertIn(f"]({os.path.relpath(target, path.parent)})", text)
                self.assertIn(CLAIM, flat)
                self.assertIn("+55.6796", flat)
                self.assertIn("+0.7250", flat)
                for limit in ("ideal clock", "lumped", "67 output ports", "3 inputs" if path is SIGNOFF_README else "3 non-clock inputs"):
                    self.assertIn(limit, flat.lower())

    def test_signoff_grade_still_rests_on_the_no_spef_inputs(self):
        flat = " ".join(self.signoff.split())
        self.assertIn("The grade rests on (1) and (2) and does not change.", flat)
        self.assertIn("not a graded input of this row", flat)
        self.assertIn("this is not timing closure", " ".join(self.macro.split()))
        sta = json.loads(FRESHNESS.read_text())["citations"]["5.digital"]
        self.assertIsNone(sta["parts"][0]["envelope_asserts"]["spef_path"])
        self.assertTrue(any("#1028" in line for line in sta["note"]))

    def test_macro_readme_timing_table_is_the_receipt_s_numbers(self):
        rows = _table(self.macro, TIMING_HEADER)
        ev = json.loads(CLEAN_JSON.read_text())
        self.assertEqual([r[0] for r in rows], [c["corner"] for c in ev["corners"]])
        for row, c in zip(rows, ev["corners"]):
            s, d = c["spef"], c["delta_spef_minus_ref"]
            self.assertEqual(row[1:], [rec._f(s["worst_slack_ns"]), rec._f(s["worst_hold_slack_ns"]),
                                       f"{s['setup_violation_count']}/{s['hold_violation_count']}",
                                       rec._f(d["worst_slack_ns"]), rec._f(d["worst_hold_slack_ns"])])

    def test_macro_readme_ac2_table_is_the_reader_s_accounting(self):
        rows = _table(self.macro, TIMED_HEADER)
        self.assertEqual([r[0] for r in rows], list(TimedNetsReconciliation.TIMED_NETS))
        for row, (net, (pin, driver, load)) in zip(rows, TimedNetsReconciliation.TIMED_NETS.items()):
            self.assertEqual(row, [net, pin, driver, load, f"{TimedNetsReconciliation.TOTAL_CAP_FF[net]:.3f}",
                                   f"{self.probe['report_net'][net]['wire_capacitance_ff']:.2f}", pin])
        self.assertIn(os.path.relpath(PROBE_JSON, MACRO_README.parent), MACRO_README.read_text())
        self.assertIn(os.path.relpath(PROBE_TCL, MACRO_README.parent), MACRO_README.read_text())


if __name__ == "__main__":
    unittest.main()
