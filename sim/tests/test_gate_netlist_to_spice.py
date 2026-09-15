#!/usr/bin/env python3
"""Regression tests for `design/sar-logic/flow/gate_netlist_to_spice.py`
(issue #273 -- this module's own docstring notes it "has no automated
regression tests yet" and hands that gap to this issue).

No PDK and no ngspice needed -- every fixture below is a small, hand-built
Verilog/SPICE fragment, not the real gf180mcu library.

    python3 -m unittest discover -s sim/tests -v

Covers the four areas issue #273's acceptance criteria name explicitly:
`.SUBCKT` pin-order parsing, alias resolution (including the multi-hop
chain), power/ground pin wiring, and the sanitize-collision guard.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "design" / "sar-logic" / "flow" / "gate_netlist_to_spice.py"

_spec = importlib.util.spec_from_file_location("gate_netlist_to_spice", MODULE_PATH)
g2s = importlib.util.module_from_spec(_spec)
sys.modules["gate_netlist_to_spice"] = g2s
_spec.loader.exec_module(g2s)


class ParseSpiceSubcktPinsTests(unittest.TestCase):
    def test_single_line_subckt(self):
        text = ".SUBCKT mycell A B VDD VNW VPW VSS\n* body\n.ENDS\n"
        pins = g2s.parse_spice_subckt_pins(text)
        self.assertEqual(pins, {"mycell": ["A", "B", "VDD", "VNW", "VPW", "VSS"]})

    def test_continuation_lines_are_joined_in_declared_order(self):
        text = (
            ".SUBCKT widecell A B C\n"
            "+ D E\n"
            "+ VDD VNW VPW VSS\n"
            "* body\n"
            ".ENDS\n"
        )
        pins = g2s.parse_spice_subckt_pins(text)
        self.assertEqual(
            pins["widecell"], ["A", "B", "C", "D", "E", "VDD", "VNW", "VPW", "VSS"]
        )

    def test_multiple_subckts_in_one_file_each_keep_their_own_order(self):
        text = (
            ".SUBCKT first X Y VDD VNW VPW VSS\n.ENDS\n\n"
            ".SUBCKT second P Q R VDD VNW VPW VSS\n.ENDS\n"
        )
        pins = g2s.parse_spice_subckt_pins(text)
        self.assertEqual(pins["first"], ["X", "Y", "VDD", "VNW", "VPW", "VSS"])
        self.assertEqual(pins["second"], ["P", "Q", "R", "VDD", "VNW", "VPW", "VSS"])

    def test_pin_order_is_exactly_as_declared_not_sorted(self):
        """The whole point of reading pin order from the PDK's own SPICE text
        (this module's docstring) is that it is NOT alphabetical or otherwise
        inferrable -- assert the parser preserves the literal declared order."""
        text = ".SUBCKT z_first_alphabetically ZN A VDD VNW VPW VSS\n.ENDS\n"
        pins = g2s.parse_spice_subckt_pins(text)
        self.assertEqual(pins["z_first_alphabetically"], ["ZN", "A", "VDD", "VNW", "VPW", "VSS"])


class ResolveAliasesTests(unittest.TestCase):
    def test_no_assigns_gives_empty_map(self):
        aliases = g2s._resolve_aliases("module top(a, b);\nendmodule\n", ["a", "b"])
        self.assertEqual(aliases, {})

    def test_simple_pass_through_aliases_to_the_port(self):
        """`assign c9 = c9_r;` where c9 is a port -- the port is kept as
        canonical (a port cannot be renamed, per the module's own docstring)."""
        text = "assign c9 = c9_r;\n"
        aliases = g2s._resolve_aliases(text, ["c9"])
        self.assertEqual(aliases, {"c9_r": "c9"})

    def test_neither_side_a_port_keeps_the_right_hand_side(self):
        """`assign arm9 = ph[4];` -- neither is a port, so the RHS (the side
        with an independent driver, per the docstring) is kept canonical."""
        text = "assign arm9 = ph[4];\n"
        aliases = g2s._resolve_aliases(text, ["clk", "start"])
        self.assertEqual(aliases, {"arm9": "ph[4]"})

    def test_bus_bit_reference_is_accepted_as_a_simple_net(self):
        text = "assign drdy = ph[15];\n"
        aliases = g2s._resolve_aliases(text, ["drdy"])
        self.assertEqual(aliases, {"ph[15]": "drdy"})

    def test_multi_hop_chain_resolves_transitively(self):
        """`assign b = a; assign c = b;` -- not needed by this design's own
        netlist (the docstring says so explicitly) but must not silently
        mis-wire a future synthesis run that produces one."""
        text = "assign b = a;\nassign c = b;\n"
        aliases = g2s._resolve_aliases(text, ["a"])
        self.assertEqual(aliases, {"b": "a", "c": "a"})

    def test_aliasing_two_ports_together_is_an_error(self):
        text = "assign porta = portb;\n"
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s._resolve_aliases(text, ["porta", "portb"])

    def test_conflicting_alias_targets_is_an_error(self):
        text = "assign x = a;\nassign x = b;\n"
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s._resolve_aliases(text, ["a", "b"])

    def test_non_simple_expression_is_rejected_not_guessed(self):
        """This translator does not evaluate Verilog expressions -- a
        concatenation, constant, or operator on either side is a hard error.
        (No internal whitespace, matching Yosys `write_verilog`'s own
        concatenation style, so the outer `assign ... ;` regex itself
        matches -- what must reject this is the simple-net check inside
        `_resolve_aliases`, not the outer parse silently skipping the line.)
        """
        text = "assign y = {a,b};\n"
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s._resolve_aliases(text, ["a", "b"])


class SanitizeNetTests(unittest.TestCase):
    def test_bus_bit_suffix_is_rewritten_with_an_underscore(self):
        self.assertEqual(g2s._sanitize_net("ph[2]"), "ph_2")

    def test_scalar_names_are_unchanged(self):
        self.assertEqual(g2s._sanitize_net("drdy"), "drdy")
        self.assertEqual(g2s._sanitize_net("sel_hi_n_256p"), "sel_hi_n_256p")

    def test_multiple_bracket_groups_all_rewrite(self):
        self.assertEqual(g2s._sanitize_net("bus[1][2]"), "bus_1_2")


class AssertNoCollisionsTests(unittest.TestCase):
    def test_no_collision_passes_silently(self):
        g2s._assert_no_collisions(["ph[2]", "ph_2_real"], ["ph_2", "ph_2_real"], context="test")

    def test_genuine_collision_raises(self):
        """`ph_2` (already a real, distinct scalar net) and `ph[2]` (a bus
        bit that sanitizes to the same string) must not be silently merged."""
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s._assert_no_collisions(["ph[2]", "ph_2"], ["ph_2", "ph_2"], context="test")

    def test_same_original_name_appearing_twice_is_not_a_collision(self):
        """The same net listed twice (e.g. once as a port, once as an
        instance connection) sanitizing to the same string is fine -- it is
        not two DIFFERENT original names colliding."""
        g2s._assert_no_collisions(["drdy", "drdy"], ["drdy", "drdy"], context="test")


class ParseGateVerilogTests(unittest.TestCase):
    NETLIST = (
        "module top(clk, a, y);\n"
        "  input clk;\n"
        "  input a;\n"
        "  output y;\n"
        "  wire mid;\n"
        "  assign y = mid_r;\n"
        "  mycell _000_ (\n"
        "    .A(a),\n"
        "    .ZN(mid_r)\n"
        "  );\n"
        "endmodule\n"
    )

    def test_parses_top_ports_and_instances(self):
        netlist = g2s.parse_gate_verilog(self.NETLIST, expected_top="top")
        self.assertEqual(netlist.top, "top")
        self.assertEqual(netlist.ports, ["clk", "a", "y"])
        self.assertEqual(len(netlist.instances), 1)
        inst = netlist.instances[0]
        self.assertEqual(inst.cell_type, "mycell")
        self.assertEqual(inst.inst_name, "_000_")
        # mid_r is aliased to the port y via the trailing `assign`.
        self.assertEqual(inst.connections, {"A": "a", "ZN": "y"})

    def test_wrong_expected_top_is_an_error(self):
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.parse_gate_verilog(self.NETLIST, expected_top="not_top")

    def test_no_module_header_is_an_error(self):
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.parse_gate_verilog("// nothing here\n")

    def test_no_instances_is_an_error(self):
        text = "module top(a);\n  input a;\nendmodule\n"
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.parse_gate_verilog(text)


class BuildSpiceSubcktTests(unittest.TestCase):
    """Power/ground pin wiring -- the other half of issue #273's acceptance
    criteria for this module, alongside the sanitize-collision guard."""

    CELL_PINS = {"mycell": ["A", "ZN", "VDD", "VNW", "VPW", "VSS"]}

    def _netlist(self, ports, connections):
        inst = g2s.GateInstance(cell_type="mycell", inst_name="x0", connections=connections)
        return g2s.GateNetlist(top="top", ports=ports, instances=[inst])

    def test_power_and_ground_pins_are_wired_to_the_supplied_nets(self):
        netlist = self._netlist(["a", "y"], {"A": "a", "ZN": "y"})
        text = g2s.build_spice_subckt(
            netlist, self.CELL_PINS, subckt_name="top", supply_net="vdd_net", ground_net="0"
        )
        self.assertIn(".subckt top a y", text)
        # Pin order follows CELL_PINS exactly: A ZN VDD VNW VPW VSS.
        self.assertIn("Xx0 a y vdd_net vdd_net 0 0 mycell", text)
        self.assertTrue(text.rstrip().endswith(".ends"))

    def test_custom_ground_net_is_honoured(self):
        netlist = self._netlist(["a", "y"], {"A": "a", "ZN": "y"})
        text = g2s.build_spice_subckt(
            netlist, self.CELL_PINS, subckt_name="top", supply_net="vdd_net", ground_net="gnd"
        )
        self.assertIn("Xx0 a y vdd_net vdd_net gnd gnd mycell", text)

    def test_bus_bit_connections_are_sanitized_in_the_instance_line(self):
        netlist = self._netlist(["a", "y[0]"], {"A": "a", "ZN": "y[0]"})
        text = g2s.build_spice_subckt(
            netlist, self.CELL_PINS, subckt_name="top", supply_net="vdd_net", ground_net="0"
        )
        self.assertIn("Xx0 a y_0 vdd_net vdd_net 0 0 mycell", text)

    def test_unknown_cell_type_raises(self):
        inst = g2s.GateInstance(cell_type="nosuchcell", inst_name="x0", connections={})
        netlist = g2s.GateNetlist(top="top", ports=[], instances=[inst])
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.build_spice_subckt(netlist, self.CELL_PINS, subckt_name="top", supply_net="vdd_net")

    def test_missing_non_power_pin_connection_raises(self):
        """A real signal pin (not power/ground) with no named connection at
        all is a genuinely unconnected pin -- must error, not silently float."""
        netlist = self._netlist(["a"], {"A": "a"})  # ZN never connected
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.build_spice_subckt(netlist, self.CELL_PINS, subckt_name="top", supply_net="vdd_net")

    def test_net_name_collision_across_the_whole_design_is_caught(self):
        """`ph_2` (a real scalar net) and `ph[2]` (a bus bit that sanitizes to
        the same string) appearing anywhere in the design -- ports or
        instance connections -- must be refused, not silently merged."""
        cell_pins = {"mycell": ["A", "ZN", "VDD", "VNW", "VPW", "VSS"]}
        inst = g2s.GateInstance(
            cell_type="mycell", inst_name="x0", connections={"A": "ph[2]", "ZN": "ph_2"}
        )
        netlist = g2s.GateNetlist(top="top", ports=[], instances=[inst])
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.build_spice_subckt(netlist, cell_pins, subckt_name="top", supply_net="vdd_net")


class ExtractUsedSubcktsTests(unittest.TestCase):
    LIB_TEXT = (
        ".SUBCKT first X Y VDD VNW VPW VSS\n"
        "Xm first_body\n"
        ".ENDS\n\n"
        ".SUBCKT second P Q VDD VNW VPW VSS\n"
        "Xm second_body\n"
        ".ENDS\n\n"
        ".SUBCKT third R VDD VNW VPW VSS\n"
        "Xm third_body\n"
        ".ENDS\n"
    )

    def test_extracts_only_the_requested_cell_types_verbatim(self):
        text = g2s.extract_used_subckts(self.LIB_TEXT, {"first", "third"})
        self.assertIn(".SUBCKT first X Y VDD VNW VPW VSS", text)
        self.assertIn("first_body", text)
        self.assertIn(".SUBCKT third R VDD VNW VPW VSS", text)
        self.assertIn("third_body", text)
        self.assertNotIn("second_body", text)

    def test_missing_cell_type_raises(self):
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.extract_used_subckts(self.LIB_TEXT, {"first", "nosuchcell"})


class TranslateEndToEndTests(unittest.TestCase):
    """The full `translate()` pipeline against small, hand-built fixtures --
    not the real gf180mcu library, so this runs with no PDK installed."""

    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)

        self.netlist_path = root / "gate.v"
        self.netlist_path.write_text(
            "module top(clk, a, y);\n"
            "  input clk;\n"
            "  input a;\n"
            "  output y;\n"
            "  assign y = mid_r;\n"
            "  mycell _000_ (\n"
            "    .A(a),\n"
            "    .ZN(mid_r)\n"
            "  );\n"
            "endmodule\n"
        )
        self.spice_lib_path = root / "lib.spice"
        self.spice_lib_path.write_text(
            ".SUBCKT mycell A ZN VDD VNW VPW VSS\n"
            "Xm A ZN VDD VNW VPW VSS somefet\n"
            ".ENDS\n"
        )

    def test_translate_produces_a_wired_subckt_and_the_used_library_text(self):
        subckt_text, used_text = g2s.translate(
            self.netlist_path,
            self.spice_lib_path,
            subckt_name="top",
            supply_net="vdd_gate",
            ground_net="0",
            expected_top="top",
        )
        self.assertIn(".subckt top clk a y", subckt_text)
        self.assertIn("X_000_ a y vdd_gate vdd_gate 0 0 mycell", subckt_text)
        self.assertTrue(subckt_text.rstrip().endswith(".ends"))
        self.assertIn(".SUBCKT mycell A ZN VDD VNW VPW VSS", used_text)

    def test_wrong_expected_top_propagates_as_an_error(self):
        with self.assertRaises(g2s.NetlistTranslationError):
            g2s.translate(
                self.netlist_path,
                self.spice_lib_path,
                subckt_name="top",
                supply_net="vdd_gate",
                expected_top="not_top",
            )


if __name__ == "__main__":
    unittest.main()
