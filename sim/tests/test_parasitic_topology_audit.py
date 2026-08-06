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

  * `remediate_extracted.remediate_leaf()` -- promotes a leaf cell's anonymous
    PMOS-body net to a pin instead of tying it to `vdd` inside the cell.

    python3 -m unittest discover -s sim/tests -t sim/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "layout" / "adc-top" / "parasitics"))

import audit_parasitic_topology as apt  # noqa: E402
import remediate_extracted as R  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
