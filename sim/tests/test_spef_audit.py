#!/usr/bin/env python3
"""Unit tests for `design/sar-logic/flow/spef_audit.py` (issue #481).

`spef_audit` decides whether a SPEF-annotated `klt sta` corner is accepted,
so each check is exercised here on a tiny synthetic design. There is one
known-good SPEF, plus one variant per defect the audit exists to catch: wrong
unit, renamed (misnamed) net, dropped connection, and a top-level PIN whose
name differs from its NET (the klayout-tools#2880 mechanism). The gate is
tested both ways, so it is shown able to reject and able to accept. No
`klt`, OpenROAD or PDK needed:

    python3 -m unittest discover -s sim/tests -t sim/tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "design" / "sar-logic" / "flow"))

import spef_audit as a  # noqa: E402

# u2 (inverter) drives n1 into flop u1's D; u1.Q drives output y; clkload is a
# dummy load with a floating output (no net on Z).
DEF = """\
VERSION 5.8 ;
DIVIDERCHAR "/" ;
BUSBITCHARS "[]" ;
DESIGN top ;
UNITS DISTANCE MICRONS 1000 ;
COMPONENTS 4 ;
    - u1 dffq + PLACED ( 0 0 ) N ;
    - u2 inv + PLACED ( 0 0 ) N ;
    - clkload buf + PLACED ( 0 0 ) N ;
    - FILLER_1 fill + SOURCE DIST + PLACED ( 0 0 ) N ;
END COMPONENTS
PINS 5 ;
    - VDD + NET VDD + SPECIAL + DIRECTION INOUT + USE POWER ;
    - clk + NET clk + DIRECTION INPUT + USE SIGNAL ;
    - a + NET a + DIRECTION INPUT + USE SIGNAL ;
    - {ypin} + NET {ynet} + DIRECTION OUTPUT + USE SIGNAL ;
END PINS
SPECIALNETS 1 ;
    - VDD ( * VDD ) + USE POWER ;
END SPECIALNETS
NETS 4 ;
    - clk ( PIN clk ) ( u1 CLK ) ( clkload I ) + USE SIGNAL ;
    - a ( PIN a ) ( u2 I ) + USE SIGNAL
      + ROUTED Metal2 ( 0 0 ) ( 10 0 ) ;
    - n1 ( u2 ZN ) ( u1 D ) + USE SIGNAL ;
    - {ynet} ( PIN {ypin} ) ( u1 Q ) + USE SIGNAL ;
END NETS
END DESIGN
"""

VERILOG = """\
module top (clk, a, {ypin});
 input clk;
 input a;
 output {ypin};
 wire n1;
{ywire} dffq u1 (.D(n1),
    .CLK(clk),
    .Q({ynet}));
 inv u2 (.I(a),
    .ZN(n1));
 buf clkload (.I(clk));
{assign}endmodule
"""

LIBERTY = """\
library (x) {
  cell ("dffq") {
    ff ("IQ","IQN") { clocked_on : "CLK"; next_state : "D"; }
    pin ("CLK") { direction : input; clock : true; }
    pin ("D") { direction : input; }
    pin ("Q") { direction : output; }
    pg_pin ("VDD") { pg_type : primary_power; }
  }
  cell ("inv") {
    pin ("I") { direction : input; }
    pin ("ZN") { direction : output; }
  }
  cell ("buf") {
    pin ("I") { direction : input; }
    pin ("Z") { direction : output; }
  }
  cell ("unused") {
    pin ("A") { direction : input; }
  }
}
"""

SPEF = """\
*SPEF "IEEE 1481-1999"
*DESIGN "top"
*DIVIDER /
*DELIMITER :
*BUS_DELIMITER [ ]
*T_UNIT 1 PS
*C_UNIT {cunit}
*R_UNIT 1 OHM

*PORTS
VDD B
clk B
a B
{yport} B

*D_NET clk 1.0
*CONN
*P clk B
*I u1:CLK B
*I clkload:I B
*CAP
1 clk 1.0
*RES
1 clk u1:CLK 0.0
2 clk clkload:I 0.0
*END

*D_NET a 1.0
*CONN
*P a B
*I u2:I B
*CAP
1 a 1.0
*RES
1 a u2:I 0.0
*END

*D_NET {n1} 2.0
*CONN
*I u2:ZN B
*I u1:D B
*CAP
1 {n1}:1 2.0
2 {n1}:1 a 0.01
*RES
1 {n1}:1 {n1}:2 5.0
2 {n1}:1 u2:ZN 0.0
3 {n1}:1 u1:D 0.0
*END

*D_NET {ynet} 3.0
*CONN
*P {yport} B
*I u1:Q B
*CAP
1 {yhub} 3.0
*RES
1 {yhub} u1:Q 0.0
*END

*D_NET $7 0.5
*CAP
1 $7:1 0.5
*END
"""


def build(*, cunit="1 FF", n1="n1", mismatch=False, drop_conn=False):
    """Synthetic (spef, def, verilog, liberty). `mismatch` makes the output
    PIN `y` sit on NET `y_r`, with the SPEF naming the port and hub `y_r`
    (the klayout-tools#2880 gap-1 shape). Otherwise PIN and NET are both `y`,
    with an internal hub."""
    ypin = "y"
    ynet = "y_r" if mismatch else "y"
    spef = SPEF.format(
        cunit=cunit, n1=n1, ynet=ynet, yport=ynet if mismatch else "y", yhub=ynet if mismatch else "y:1",
    )
    if drop_conn:
        spef = spef.replace("*I u1:D B\n", "")
    def_ = DEF.format(ypin=ypin, ynet=ynet)
    ver = VERILOG.format(
        ypin=ypin, ynet=ynet,
        ywire=" wire y_r;\n" if mismatch else "",
        assign=" assign y = y_r;\n" if mismatch else "",
    )
    return a.parse_spef(spef), a.parse_def(def_), a.parse_verilog(ver), a.parse_liberty_pins(LIBERTY)


def checks(result):
    return sorted({e["check"] for e in result["errors"]})


class TestParsers(unittest.TestCase):
    def test_spef_def_verilog_liberty(self):
        spef, def_, ver, lib = build()
        self.assertEqual(spef.header["C_UNIT"], "1 FF")
        self.assertEqual(spef.ports, ["VDD", "clk", "a", "y"])
        self.assertEqual(spef.net_names, ["clk", "a", "n1", "y", "$7"])
        n1 = spef.nets[2]
        self.assertEqual(n1.insts, [("u2", "ZN"), ("u1", "D")])
        self.assertIn("n1:1", n1.nodes)
        self.assertEqual(def_.pins["y"], "y")
        self.assertEqual(def_.nets["clk"], [("PIN", "clk"), ("u1", "CLK"), ("clkload", "I")])
        self.assertEqual(def_.special_nets, ["VDD"])
        self.assertEqual(def_.components["FILLER_1"], "fill")
        self.assertEqual(ver.instances["u1"], ("dffq", {"D": "n1", "CLK": "clk", "Q": "y"}))
        self.assertEqual(ver.ports, {"clk": "input", "a": "input", "y": "output"})
        self.assertEqual(lib["dffq"]["CLK"], "input:clock")
        self.assertEqual(lib["dffq"]["__sequential__"], "true")
        self.assertNotIn("VDD", lib["dffq"])  # pg_pin excluded
        self.assertNotIn("__sequential__", lib["inv"])

    def test_escaped_and_bus_names(self):
        self.assertEqual(a.unescape(r"ph\[15\]"), "ph[15]")
        spef = a.parse_spef("*C_UNIT 1 FF\n*D_NET ph\\[1\\] 1.0\n*CONN\n*I u\\/x:Q B\n*CAP\n1 ph\\[1\\]:1 1.0\n*END\n")
        self.assertEqual(spef.net_names, ["ph[1]"])
        self.assertEqual(spef.nets[0].insts, [("u/x", "Q")])

    def test_verilog_vector_wires(self):
        v = a.parse_verilog("module m (a);\n input a;\n wire [2:0] w;\n inv u (.I(a), .ZN(w[1]));\nendmodule\n")
        self.assertEqual(v.wires, {"w[0]", "w[1]", "w[2]"})

    def test_liberty_restricted_to_cells(self):
        lib = a.parse_liberty_pins(LIBERTY, {"inv"})
        self.assertEqual(set(lib), {"inv"})


class TestAgreementAudit(unittest.TestCase):
    def test_good_spef_has_no_errors(self):
        r = a.audit_agreement(*build())
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["conn_sets_all_match"])
        info = {i["check"]: i for i in r["info"]}
        self.assertEqual(info["non_design_spef_nets"]["anonymous_count"], 1)
        self.assertEqual(info["floating_outputs"]["pins"], ["clkload/Z"])

    def test_wrong_unit_is_an_error(self):
        r = a.audit_agreement(*build(cunit="1 PF"))
        self.assertEqual(checks(r), ["units"])

    def test_renamed_net_is_missing(self):
        r = a.audit_agreement(*build(n1="n1_renamed"))
        self.assertIn("net_missing_in_spef", checks(r))
        self.assertIn("n1", r["nets_with_errors"])
        extras = next(i for i in r["info"] if i["check"] == "non_design_spef_nets")
        self.assertIn("n1_renamed", extras["labelled"])

    def test_dropped_connection_is_a_conn_mismatch(self):
        r = a.audit_agreement(*build(drop_conn=True))
        e = next(e for e in r["errors"] if e["check"] == "conn_mismatch")
        self.assertEqual((e["net"], e["missing_in_spef"]), ("n1", ["u1:D"]))
        self.assertFalse(r["conn_sets_all_match"])

    def test_pin_name_differs_from_net_name(self):
        r = a.audit_agreement(*build(mismatch=True))
        e = next(e for e in r["errors"] if e["check"] == "port_name_mismatch")
        self.assertEqual(e["net"], "y_r")
        self.assertEqual(e["spef_ports"], ["y_r"])
        self.assertEqual(e["def_pins_on_net"], ["y"])
        # the Verilog `assign y = y_r` explains the DEF aliasing, so that part is fine
        self.assertNotIn("def_pin_net_alias_unexplained", checks(r))

    def test_coupling_reference_to_a_real_port_is_fine(self):
        # n1's coupling cap names the bare node `a`, which IS a top-level port
        r = a.audit_agreement(*build())
        self.assertNotIn("a", r["nets_with_errors"])

    def test_timed_path_witness(self):
        spef, def_, ver, lib = build()
        self.assertEqual(a.timed_path_witness(ver, lib, "a"), "a -> u2/I -> u1/D (dffq)")
        self.assertIsNone(a.timed_path_witness(ver, lib, "y"))  # output port only: no register


class TestReaderWarnings(unittest.TestCase):
    LOG = (
        "[WARNING STA-1650] f.spef line 3, net $106 not found.\n"
        "[WARNING STA-1650] f.spef line 9, net Z not found.\n"
        "[WARNING STA-1656] f.spef line 12, pin y_r not found.\n"
        "[WARNING STA-1656] f.spef line 13, pin y_r not found.\n"
        "[WARNING STA-1648] f.spef line 20, instance u9:A not found.\n"
        "[WARNING ODB-0220] unrelated.\n"
    )

    def test_classification(self):
        w = a.classify_reader_warnings(self.LOG, {"y_r", "n1"}, {"u1"})
        self.assertEqual(w["total"], 5)
        self.assertEqual(w["by_code"], {"STA-1650": 2, "STA-1656": 2, "STA-1648": 1})
        self.assertEqual(w["touching_design"], {"y_r": 2})
        self.assertEqual(w["touching_design_records"], 2)
        self.assertEqual(w["non_design"], {"$<n> (anonymous intra-cell net)": 1, "Z": 1, "u9": 1})


GOOD_ANN = {
    "nets_annotated": 4, "nets_total": 5, "design_nets_annotated": 5, "design_nets_total": 5,
    "design_nets_missing_sample": [], "reader_warning_count": 0, "unannotated_driver_count": 0,
    "delay_changed": True, "annotation_complete": True, "annotation_warning": None,
}
CLEAN_WARN = {"total": 0, "by_code": {}, "touching_design": {}, "touching_design_records": 0, "non_design": {}}


class TestGate(unittest.TestCase):
    def resp(self, **ann):
        return {"timing_status": "constrained", "spef_annotation": {**GOOD_ANN, **ann}}

    def test_accepts_a_clean_corner(self):
        self.assertEqual(a.gate(self.resp(), {"ok": True}, CLEAN_WARN), [])

    def test_rejects_without_spef_annotation(self):
        self.assertTrue(a.gate({"timing_status": "constrained", "spef_annotation": None}, {"ok": True}, CLEAN_WARN))

    def test_rejects_incomplete_annotation(self):
        r = a.gate(self.resp(annotation_complete=False, annotation_warning="x"), {"ok": True}, CLEAN_WARN)
        self.assertTrue(any("annotation_complete" in x for x in r))

    def test_rejects_missing_design_net(self):
        r = a.gate(self.resp(design_nets_annotated=4, design_nets_missing_sample=["n1"]), {"ok": True}, CLEAN_WARN)
        self.assertTrue(any("['n1']" in x for x in r))

    def test_rejects_unchanged_delays(self):
        r = a.gate(self.resp(delay_changed=False), {"ok": True}, CLEAN_WARN)
        self.assertTrue(any("delay_changed" in x for x in r))

    def test_rejects_unannotated_drivers(self):
        self.assertTrue(a.gate(self.resp(unannotated_driver_count=2), {"ok": True}, CLEAN_WARN))

    def test_rejects_unclassifiable_log(self):
        self.assertTrue(any("not retained" in x for x in a.gate(self.resp(), {"ok": True}, None)))

    def test_rejects_warnings_on_design_nets_even_if_klt_says_complete(self):
        w = {**CLEAN_WARN, "touching_design": {"y_r": 3}, "touching_design_records": 3}
        self.assertTrue(any("y_r" in x for x in a.gate(self.resp(), {"ok": True}, w)))

    def test_rejects_static_audit_errors(self):
        r = a.gate(self.resp(), {"ok": False, "nets_with_errors": ["y_r"]}, CLEAN_WARN)
        self.assertTrue(any("y_r" in x for x in r))

    def test_rejects_unconstrained(self):
        resp = self.resp()
        resp["timing_status"] = "unconstrained"
        self.assertTrue(a.gate(resp, {"ok": True}, CLEAN_WARN))


class TestNegativeControls(unittest.TestCase):
    def text(self):
        return SPEF.format(cunit="1 FF", n1="n1", ynet="y", yport="y", yhub="y:1")

    def test_drop_removes_the_whole_block(self):
        out = a.derive_negative_control(self.text(), "n1", "drop")
        s = a.parse_spef(out)
        self.assertNotIn("n1", s.net_names)
        self.assertEqual(len(s.nets), 4)

    def test_rename_renames_every_reference_only(self):
        out = a.derive_negative_control(self.text(), "n1", "rename")
        s = a.parse_spef(out)
        self.assertIn("n1_negctl", s.net_names)
        self.assertNotIn("n1", s.net_names)
        self.assertIn("n1_negctl:2", s.nets[2].nodes)
        self.assertIn("*I u1:D B", out)  # instance pins untouched

    def test_controls_are_caught_by_the_audit(self):
        _, def_, ver, lib = build()
        for mode in ("drop", "rename"):
            spef = a.parse_spef(a.derive_negative_control(self.text(), "n1", mode))
            r = a.audit_agreement(spef, def_, ver, lib)
            self.assertIn("n1", r["nets_with_errors"], mode)

    def test_unknown_net_or_mode_raises(self):
        with self.assertRaises(ValueError):
            a.derive_negative_control(self.text(), "nope", "drop")
        with self.assertRaises(ValueError):
            a.derive_negative_control(self.text(), "n1", "shuffle")


if __name__ == "__main__":
    unittest.main()
