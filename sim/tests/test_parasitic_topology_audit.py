#!/usr/bin/env python3
"""Unit tests for the two pieces of extraction plumbing the
`sim/extracted-delta-summary.md` SS6.3 R_on re-take added -- no PDK, no
ngspice, no `klt` required (both read text):

  * `layout/adc-top/parasitics/audit_parasitic_topology.py` -- classifies each
    extracted parasitic R as in-path or stub, in either of the two topologies
    `klt extract --parasitics` has emitted over this repo's life (the
    shunt-stub form up to the `af5791b` pin; the star-split form since
    `875eac3`, issue #116 / upstream `klayout-tools#593`).

    Both directions are controlled, because a classifier stuck on ONE answer
    would have agreed with the whole repo at one pin or the other: the
    hand-written `STUB_NETLIST`/`IN_PATH_NETLIST` pair pins the shunt-stub
    form's two answers, `STAR_NETLIST` pins the star-split form's, and
    `test_committed_extractions_are_all_in_path_topology` re-derives the
    current finding from the committed netlists while
    `test_a_pre_bump_extraction_still_reads_as_stub` re-derives the OLD one
    from a pre-bump committed netlist that is still in `reports/` -- so the
    append-only evidence keeps meaning what it meant when it was minted.
    `test_latest_tgate_extraction_puts_every_fet_terminal_on_a_leg` then pins
    the stronger per-terminal condition on the `adc_tgate` leaf specifically,
    because that condition is what retired `gen_extracted_switch_ron_tb.py`'s
    `--in-path-control` positive control (issue #789).

  * `remediate_extracted.remediate_leaf()` -- promotes a leaf cell's anonymous
    PMOS-body net to a pin instead of tying it to `vdd` inside the cell.

    python3 -m unittest discover -s sim/tests -t sim/tests -v
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "layout" / "adc-top" / "parasitics"))

import audit_parasitic_topology as apt  # noqa: E402
import remediate_extracted as R  # noqa: E402

#: The leaf cell `gen_extracted_switch_ron_tb.py` splices into its deck -- the
#: one whose in-path topology retired that generator's positive control.
TOP = "ADC_TGATE"


#: A two-device cell whose parasitic R/C pairs are stubs: every device
#: terminal is on the net itself, and `<net>__par` is reached only by the C.
#: This is the shape `klt extract --parasitics` emits for gf180mcu today.
STUB_NETLIST = """\
* cell FAKE
.SUBCKT FAKE gn vin vout vsubs
X$1 vin gn vout vsubs nfet_03v3 L=0.28U W=10U
Rvin vin vin__par 120.0
Cvin vin__par vsubs 4.2e-15
Rvout vout vout__par 76.5
Cvout vout__par vsubs 3.8e-15
.ENDS FAKE
"""

#: The same cell with the device moved onto the internal node, i.e. the
#: series R now carries the channel current. Nothing in this repo's committed
#: extractions looks like this -- it exists so the classifier's "stub" answer
#: is a measurement rather than a constant.
IN_PATH_NETLIST = STUB_NETLIST.replace(
    "X$1 vin gn vout vsubs", "X$1 vin__par gn vout__par vsubs"
)

#: The SAME two-net cell in the star-split form the `875eac3` pin emits: one
#: leg per device terminal, each with a series R back to the hub, and the
#: net's C on the hub. This is what "in-path by construction" looks like.
STAR_NETLIST = """\
* cell FAKE
.SUBCKT FAKE gn vin vout vsubs
X$1 vin__t0 gn vout__t0 vsubs nfet_03v3 L=0.28U W=10U
X$2 vin__t1 gn vout__t1 vsubs nfet_03v3 L=0.28U W=10U
Rvin_t0 vin__t0 vin 60.0
Rvin_t1 vin__t1 vin 60.0
Cvin vin vsubs 4.2e-15
Rvout_t0 vout__t0 vout 38.25
Rvout_t1 vout__t1 vout 38.25
Cvout vout vsubs 3.8e-15
.ENDS FAKE
"""


class TestParasiticTopologyAudit(unittest.TestCase):
    def test_stub_topology_is_reported_as_stub(self):
        got = apt.audit(STUB_NETLIST, "stub.spice")
        self.assertEqual(got["parasitic_nets"], 2)
        self.assertEqual(got["stub_nets"], 2)
        self.assertEqual(got["in_path_nets"], 0)
        self.assertFalse(got["series_resistance_in_signal_path"])
        self.assertEqual({n["topology"] for n in got["nets"]}, {"stub"})

    def test_in_path_topology_is_reported_as_in_path(self):
        """NEGATIVE CONTROL -- see this module's docstring."""
        got = apt.audit(IN_PATH_NETLIST, "in_path.spice")
        self.assertEqual(got["parasitic_nets"], 2)
        self.assertEqual(got["in_path_nets"], 2)
        self.assertEqual(got["stub_nets"], 0)
        self.assertTrue(got["series_resistance_in_signal_path"])

    def test_totals_are_summed_over_the_parasitic_nets(self):
        got = apt.audit(STUB_NETLIST, "stub.spice")
        self.assertAlmostEqual(got["total_resistance_ohm"], 196.5, places=6)
        self.assertAlmostEqual(got["max_resistance_ohm"], 120.0, places=6)
        self.assertAlmostEqual(got["total_capacitance_f"], 8.0e-15, places=18)

    def test_star_topology_is_reported_as_in_path(self):
        """The `875eac3` form: a leg per terminal, so every net is in-path."""
        got = apt.audit(STAR_NETLIST, "star.spice")
        self.assertEqual(got["topology_form"], "star-split")
        self.assertEqual(got["parasitic_nets"], 2)
        self.assertEqual(got["in_path_nets"], 2)
        self.assertEqual(got["stub_nets"], 0)
        self.assertTrue(got["series_resistance_in_signal_path"])
        by_net = {n["net"]: n for n in got["nets"]}
        # the net's resistance is the SUM over its legs, and each leg is
        # separately reported so a consumer can see the per-terminal value
        self.assertEqual(by_net["vin"]["leg_count"], 2)
        self.assertAlmostEqual(by_net["vin"]["resistance_ohm"], 120.0, places=6)
        self.assertAlmostEqual(by_net["vin"]["max_leg_resistance_ohm"], 60.0, places=6)
        self.assertAlmostEqual(by_net["vin"]["capacitance_f"], 4.2e-15, places=18)
        # both terminals of both devices land on legs
        self.assertEqual(by_net["vin"]["device_terminals_on_internal_node"], 2)

    def test_committed_extractions_are_all_in_path_topology(self):
        """RE-STATED at issue #116, not silently kept.

        Until the `875eac3` toolchain pin this asserted the opposite --
        `in_path_nets == 0` for every committed extraction, which is the
        finding `sim/extracted-delta-summary.md` SS6.3 rested on ("no series
        resistance is extracted, so no resistance-sensitive post-layout
        question can read back different from the schematic"). Upstream
        `klayout-tools#593` closed that gap; the finding is therefore
        inverted here rather than deleted, so the next regression in either
        direction is caught.
        """
        paths = apt._committed_netlists()
        self.assertTrue(paths, "no committed --pdk extraction found under reports/")
        for path in paths:
            with self.subTest(netlist=path.name):
                got = apt.audit(path.read_text(), path.name)
                self.assertGreater(got["parasitic_nets"], 0)
                self.assertEqual(got["topology_form"], "star-split", path.name)
                self.assertEqual(
                    got["stub_nets"],
                    0,
                    f"{path.name} has {got['stub_nets']} STUB parasitic "
                    "resistors at a toolchain pin that is supposed to emit "
                    "in-path resistance for every net -- either the pin "
                    "regressed or this extraction is stale.",
                )

    def test_latest_tgate_extraction_puts_every_fet_terminal_on_a_leg(self):
        """Guards what RETIRED the `--in-path-control` control (issue #789).

        `gen_extracted_switch_ron_tb.py` used to carry a positive control that
        moved each device terminal onto its net's `__par` node, because at the
        `af5791b` pin every parasitic R was a dangling shunt stub and the
        resulting `+0` R_on delta needed separate proof of sensitivity. The
        control was removed because the star-split extraction since `875eac3`
        is in-path BY CONSTRUCTION -- so that construction is what has to be
        asserted now, or the retirement rests on nothing.

        `test_committed_extractions_are_all_in_path_topology` above is NOT
        enough for this. Its `stub_nets == 0` only requires that each parasitic
        net have *some* device terminal on *some* leg: move one FET source off
        its leg back onto the net hub and that net still classifies `in-path`
        (`leg_count=2`, `device_terminals_on_internal_node=1`), so the suite
        stays green while a terminal has escaped its series R. This test pins
        the stronger per-terminal condition on the deck's own leaf cell.
        """
        src = R._latest_report(TOP)
        core, _ = R.remediate_leaf(src.read_text(), TOP)

        # No shunt-stub R survives: the retired control's scan target is gone.
        self.assertEqual(
            core.count(apt.PAR_SUFFIX),
            0,
            f"{src.name} still carries {apt.PAR_SUFFIX} shunt-stub nodes -- the "
            "extraction regressed to the pre-`875eac3` topology, and the "
            "in-path-by-construction basis for retiring the positive control "
            "(issue #789) no longer holds.",
        )

        # Every leg node the parasitic Rs define, by hub net.
        legs: dict[str, set[str]] = {}
        for tok in apt._cards(core):
            if tok[0][0].upper() != "R" or len(tok) < 4:
                continue
            m = apt._LEG_RE.match(tok[1])
            if m and m.group("hub") == tok[2]:
                legs.setdefault(tok[2], set()).add(tok[1])
        self.assertTrue(legs, f"no star-split parasitic legs found in {src.name}")

        # Every FET source/drain terminal must be ON a leg, never on a hub.
        hubs = set(legs)
        fets = 0
        for tok in apt._cards(core):
            if tok[0][0].upper() != "X" or not any("fet_03v3" in t for t in tok):
                continue
            fets += 1
            terminals = tok[1 : 1 + apt._terminal_count(tok)]
            # source and drain are terminals 0 and 2 of a 4-terminal MOS card
            for which, node in (("source", terminals[0]), ("drain", terminals[2])):
                if node in hubs:
                    self.fail(
                        f"{src.name}: {tok[0]} {which} sits on hub net {node!r} "
                        f"instead of one of its leg nodes {sorted(legs[node])} "
                        "-- that terminal's parasitic R carries no channel "
                        "current, so the extraction is no longer in-path by "
                        "construction and issue #789's retirement of the "
                        "positive control would need revisiting."
                    )
        self.assertEqual(fets, 2, f"expected the two {TOP} FETs in {src.name}")

    def test_a_pre_bump_extraction_still_reads_as_stub(self):
        """`reports/` is append-only: an older record must keep its meaning.

        Picks the oldest committed `adc_tgate` extraction, which predates the
        `875eac3` pin, and re-derives the stub verdict its own record states.
        """
        candidates = sorted(apt.REPORTS.glob("*/adc_tgate.para.spice"))
        self.assertTrue(candidates, "no committed adc_tgate extraction found")
        pre_bump = [
            p
            for p in candidates
            if apt.audit(p.read_text(), p.name)["topology_form"] == "shunt-stub"
        ]
        self.assertTrue(
            pre_bump,
            "no pre-`875eac3` extraction left under reports/ -- if one was "
            "deleted, sim/README.md's append-only evidence rule was broken",
        )
        got = apt.audit(pre_bump[0].read_text(), pre_bump[0].name)
        self.assertEqual(got["in_path_nets"], 0)
        self.assertGreater(got["stub_nets"], 0)
        self.assertFalse(got["series_resistance_in_signal_path"])


class TestRemediateLeaf(unittest.TestCase):
    LEAF = """\
* cell ADC_TGATE
.SUBCKT ADC_TGATE gn gp vin vout vsubs
X$1 vin gn vout vsubs nfet_03v3 L=0.28U W=10U
X$2 vin gp vout \\$5 pfet_03v3 L=0.28U W=20U
Rvin vin vin__par 120.0
Cvin vin__par vsubs 4.2e-15
.ENDS ADC_TGATE
"""

    def test_body_net_is_promoted_to_a_pin_not_tied_to_vdd(self):
        text, rem = R.remediate_leaf(self.LEAF, "ADC_TGATE")
        self.assertEqual(rem.n_pmos_rewritten, 1)
        self.assertIn(f".SUBCKT ADC_TGATE gn gp vin vout vsubs {R.NWELL_PIN}", text)
        self.assertIn(f"X$2 vin gp vout {R.NWELL_PIN} pfet_03v3", text)
        # the leaf must NOT gain a hardcoded vdd node
        body = [ln for ln in text.splitlines() if not ln.startswith("*")]
        self.assertNotIn("vdd", " ".join(body))

    def test_parasitics_and_nmos_are_untouched(self):
        text, _ = R.remediate_leaf(self.LEAF, "ADC_TGATE")
        self.assertIn("X$1 vin gn vout vsubs nfet_03v3 L=0.28U W=10U", text)
        self.assertIn("Rvin vin vin__par 120.0", text)
        self.assertIn("Cvin vin__par vsubs 4.2e-15", text)

    def test_refuses_when_there_is_no_body_gap_to_close(self):
        already_tied = self.LEAF.replace("vout \\$5 pfet", "vout vsubs pfet")
        with self.assertRaises(ValueError):
            R.remediate_leaf(already_tied, "ADC_TGATE")

    def test_refuses_to_shadow_an_existing_pin(self):
        with self.assertRaises(ValueError):
            R.remediate_leaf(self.LEAF, "ADC_TGATE", body_pin="vin")


class TestRemediateLeafNamesTheGuardItPromises(unittest.TestCase):
    """#793 removed `_find_pmos_body_nets`, a zero-caller back-compatible
    alias around `_partition_pmos_body_nets` that `96a8546a` left behind when
    the DR-0035 rework split the old function into the `(anonymous,
    already_tied)` partition. Its only other occurrence anywhere in the
    repository was the `remediate_leaf()` docstring, which credited the alias
    with the exclusivity assertion -- the check that stops a body-net rewrite
    from clobbering a real connection -- that is in fact raised by the
    partition. A reader following that name landed on code no caller ever
    executed, so these pin the attribution rather than the three deleted
    lines: delete the alias again and nothing fails, but move the assertion
    and leave the docstring behind and `test_docstring_names_the_function...`
    goes red.

    Structural, so no PDK/ngspice/`klt` -- it parses the module (and uses the
    parsed docstring, not a substring scan over the file, so a *mention* of
    the retired name in a comment or an evidence citation stays legal)."""

    MODULE = (
        REPO_ROOT / "layout" / "adc-top" / "parasitics" / "remediate_extracted.py"
    )

    #: Substring of the exclusivity assertion's message, matched against the
    #: unparsed `raise` so the f-string's implicit concatenation is resolved.
    GUARD_MSG = "would corrupt a real connection"

    def setUp(self):
        tree = ast.parse(self.MODULE.read_text())
        self.funcs = {
            n.name: n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_alias_is_gone_and_the_function_it_wrapped_remains(self):
        self.assertNotIn("_find_pmos_body_nets", self.funcs)
        self.assertIn(
            "_partition_pmos_body_nets", self.funcs, "the function it aliased"
        )

    def test_docstring_names_the_function_that_raises_the_guard(self):
        raising = {
            name
            for name, node in self.funcs.items()
            if any(
                self.GUARD_MSG in ast.unparse(r)
                for r in ast.walk(node)
                if isinstance(r, ast.Raise)
            )
        }
        self.assertEqual(
            raising,
            {"_partition_pmos_body_nets"},
            "the exclusivity assertion moved; re-point the remediate_leaf() "
            "docstring at whichever function raises it now",
        )

        doc = ast.get_docstring(self.funcs["remediate_leaf"]) or ""
        self.assertIn(
            "`_partition_pmos_body_nets` supplies the same exclusivity "
            "assertion",
            " ".join(doc.split()),
        )
        self.assertNotIn("_find_pmos_body_nets", doc)


if __name__ == "__main__":
    unittest.main()
