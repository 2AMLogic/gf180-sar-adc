#!/usr/bin/env python3
"""Unit tests for the two pieces of extraction plumbing the
`sim/extracted-delta-summary.md` SS6.3 R_on re-take added -- no PDK, no
ngspice, no `klt` required (both read text):

  * `layout/adc-top/parasitics/audit_parasitic_topology.py` -- classifies each
    extracted parasitic R as in-path or stub. The load-bearing test here is the
    NEGATIVE control: a classifier that always answered "stub" would agree with
    every committed extraction in this repo, so it is only worth anything if it
    demonstrably reports "in-path" when a device does sit on the internal node.

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

#: The star-split topology `klt` >= `875eac3` (issue #116, klayout-tools#593)
#: writes: every device terminal gets its own leg (`<net>__t<i>`) with its
#: own series R back to the net, and the C sits on the net directly. This is
#: what every committed extraction looks like as of issue #116 -- every net
#: with a device terminal is IN-PATH by construction.
STAR_NETLIST = """\
* cell FAKE
.SUBCKT FAKE gn vin vout vsubs
X$1 vin__t0 gn__t0 vout__t0 vsubs nfet_03v3 L=0.28U W=10U
Rgn_t0 gn__t0 gn 53.1
Cgn gn vsubs 5.9e-16
Rvin_t0 vin__t0 vin 60.0
Cvin vin vsubs 4.2e-15
Rvout_t0 vout__t0 vout 38.3
Cvout vout vsubs 3.9e-15
.ENDS FAKE
"""

#: The same star-split shape with every device terminal moved back onto the
#: bare net (no leg used at all) -- a net whose legs exist but are never
#: reached by a device is still a STUB even under the star topology. Nothing
#: in this repo's committed extractions looks like this either; it exists so
#: the star-topology parser's "stub" answer is also a measurement.
STAR_STUB_NETLIST = STAR_NETLIST.replace(
    "X$1 vin__t0 gn__t0 vout__t0 vsubs", "X$1 vin gn vout vsubs"
)


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

    def test_star_topology_terminal_on_leg_is_reported_as_in_path(self):
        got = apt.audit(STAR_NETLIST, "star.spice")
        self.assertEqual(got["parasitic_nets"], 3)
        self.assertEqual(got["in_path_nets"], 3)
        self.assertEqual(got["stub_nets"], 0)
        self.assertTrue(got["series_resistance_in_signal_path"])
        self.assertEqual({n["topology"] for n in got["nets"]}, {"in-path"})

    def test_star_topology_terminal_off_leg_is_reported_as_stub(self):
        """NEGATIVE CONTROL for the star-topology parser -- see this
        module's docstring."""
        got = apt.audit(STAR_STUB_NETLIST, "star_stub.spice")
        self.assertEqual(got["parasitic_nets"], 3)
        self.assertEqual(got["in_path_nets"], 0)
        self.assertEqual(got["stub_nets"], 3)
        self.assertFalse(got["series_resistance_in_signal_path"])

    def test_totals_are_summed_over_the_parasitic_nets(self):
        got = apt.audit(STUB_NETLIST, "stub.spice")
        self.assertAlmostEqual(got["total_resistance_ohm"], 196.5, places=6)
        self.assertAlmostEqual(got["max_resistance_ohm"], 120.0, places=6)
        self.assertAlmostEqual(got["total_capacitance_f"], 8.0e-15, places=18)

    def test_committed_extractions_are_all_in_path_topology(self):
        """The finding SS6.3 rests on, re-derived from the committed netlists.

        UPDATED at issue #116: `layout/toolchain.json`'s `klt` pin bump
        (af5791b -> 875eac3, klayout-tools#593) replaced the dead-end-stub
        `--parasitics` topology with a distance-weighted star split, so
        every committed extraction now genuinely carries in-path series
        resistance -- the opposite assertion from what this test checked
        before the bump. See sim/extracted-delta-summary.md SS6.3/SS1.4 for
        the full history; this test docstring is not the place to relitigate
        it, only to keep re-deriving the CURRENT finding mechanically."""
        paths = apt._committed_netlists()
        self.assertTrue(paths, "no committed --pdk extraction found under reports/")
        for path in paths:
            with self.subTest(netlist=path.name):
                got = apt.audit(path.read_text(), path.name)
                self.assertGreater(got["parasitic_nets"], 0)
                self.assertEqual(
                    got["stub_nets"],
                    0,
                    f"{path.name} has {got['stub_nets']} stub parasitic "
                    "resistors -- sim/extracted-delta-summary.md SS6.3's "
                    "post-#116 'series resistance is in the signal path' "
                    "finding no longer holds and must be re-stated, not "
                    "silently kept.",
                )


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
