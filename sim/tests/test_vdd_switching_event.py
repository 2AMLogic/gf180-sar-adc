#!/usr/bin/env python3
"""sim/vdd-switching-event/ (issue #386): the committed requests are what the
generator says, and the event-charge derivation does what its record says.

    python3 -m unittest discover -s sim/tests -t sim/tests

Needs neither ngspice, the PDK nor `klt`, so it runs on the PDK-free CI path.

The checks are on the things that would silently corrupt the record:

- the committed request/wrapper files drift from ``gen_requests.py``;
- a request uses a measurement form the batch fleet's `klt` rejects (what
  sank this experiment's first submission -- every entry must be a plain
  `.meas` card);
- the wrapper body stops being "the shared netlist, unmodified" (it must
  ``.include`` exactly sim/adc-power's deck and set the supply only through
  ``vdd_val``);
- an event window reaches the next clock edge (it would integrate a second
  event into the first) or the baseline window overlaps array switching;
- the sign convention or the baseline subtraction in ``make_record.derive``
  goes wrong (checked against a hand-computed synthetic point).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
TB = SIM / "vdd-switching-event" / "testbench"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(TB))
G = _load("gen_requests", TB / "gen_requests.py")
R = _load("vdd_event_make_record", TB / "make_record.py")


class GeneratedFilesTests(unittest.TestCase):
    def test_committed_files_match_generator(self):
        for path, text in G.outputs().items():
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"{path.name} missing -- run gen_requests.py")
                self.assertEqual(path.read_text(), text, f"{path.name} stale -- run gen_requests.py")

    def test_every_measurement_is_a_plain_meas_card(self):
        for supply in G.SUPPLIES_V:
            req = G.request(supply)
            names = [m["name"] for m in req["measurements"]]
            self.assertEqual(len(names), len(set(names)))
            for m in req["measurements"]:
                with self.subTest(name=m["name"]):
                    self.assertNotIn("expr", m)
                    self.assertTrue(m["spice"].startswith(f".meas tran {m['name']} "))

    def test_wrapper_is_the_shared_netlist_plus_supply_only(self):
        for supply in G.SUPPLIES_V:
            body = G.wrapper_body(supply)
            includes = re.findall(r"^\.include\s+(\S+)", body, flags=re.M)
            self.assertEqual(includes, ["../../adc-power/testbench/tb_adc_power.spice"])
            self.assertTrue((TB / includes[0]).resolve().is_file())
            self.assertIn(f".param vdd_val={supply!r}", body)
            # no devices or sources of its own other than the MiM alias subckts
            for line in body.splitlines():
                if line and line[0] in "vVbBiIrRcCmMlL":
                    self.fail(f"wrapper adds an element: {line}")

    def test_analysis_changes_only_the_timestep_cap(self):
        rail = json.loads((SIM / "adc-rail-current/testbench/tb.json").read_text())
        old = rail["analyses"][0].split()          # tran 1n 17.000u 0 2n
        new = ["tran", *G.ANALYSIS_ARGS.split()]
        self.assertEqual(old[:2], new[:2])
        self.assertAlmostEqual(float(old[2].rstrip("u")), float(new[2].rstrip("u")))
        self.assertEqual(old[3], new[3])
        self.assertNotEqual(old[4], new[4])


class WindowTests(unittest.TestCase):
    def test_event_windows_stop_before_the_next_clock_edge(self):
        for e, (offset, _) in G.EVENTS.items():
            lo = offset - G.LEAD_NS
            hi = lo + G.BIT_NS
            with self.subTest(event=e):
                self.assertLess(hi, offset + G.BIT_NS)       # next edge
                self.assertGreater(lo, offset - G.BIT_NS)    # previous edge

    def test_baseline_avoids_every_event_window(self):
        blo = G.BASELINE_NS[0] - G.LEAD_NS
        bhi = G.BASELINE_NS[1] - G.LEAD_NS
        for e, (offset, _) in G.EVENTS.items():
            lo, hi = offset - G.LEAD_NS, offset - G.LEAD_NS + G.BIT_NS
            with self.subTest(event=e):
                self.assertTrue(bhi <= lo or blo >= hi)
        # the top-plate switch opens on the ph3 edge (187.5 ns): outside the baseline
        self.assertLess(bhi, 3 * G.BIT_NS)

    def test_all_windows_inside_the_run(self):
        last = max(G.CONVERSIONS) * 1000.0 + max(o for o, _ in G.EVENTS.values()) - G.LEAD_NS + G.BIT_NS
        self.assertLessEqual(last, 17000.0)


class DeriveTests(unittest.TestCase):
    def _synthetic(self):
        """Static 30 uA on vddc everywhere; one 4 pC vddd event at A7, a
        net-absorbing C5; a 34 mA peak at A7."""
        m = {"isum_min": -0.034, "isum_max": 0.0065, "vddm": 3.63}
        for b in G.BRANCHES:
            m[f"iavg_{b}"] = -30e-6 if b == "c" else 0.0
            m[f"imax_{b}"] = 0.0065 if b == "d" else -1e-6
        for k in G.CONVERSIONS:
            for b in G.BRANCHES:
                m[f"ib{b}_{k:02d}"] = -30e-6 if b == "c" else 0.0
            for e in G.EVENTS:
                for b in G.BRANCHES:
                    m[f"q{b}_{e}{k:02d}"] = -30e-6 * R.T_W if b == "c" else 0.0
                m[f"ipk_{e}{k:02d}"] = -1e-3
        m["qd_a07"] = -4e-12
        m["ipk_a07"] = -0.034
        m["qd_c05"] = +0.5e-12
        return m

    def test_baseline_subtraction_and_sign(self):
        d = R.derive(self._synthetic())
        self.assertEqual((d["peak"]["e"], d["peak"]["k"]), ("a", 7))
        self.assertAlmostEqual(d["peak"]["dq"], 4e-12, delta=1e-18)
        self.assertAlmostEqual(d["peak"]["dq_cdac"], 4e-12, delta=1e-18)
        self.assertAlmostEqual(d["peak"]["t_eq"], 4e-12 / 0.034, delta=1e-18)
        c5 = next(ev for ev in d["events"] if (ev["e"], ev["k"]) == ("c", 5))
        self.assertAlmostEqual(c5["dq"], -0.5e-12, delta=1e-18)
        self.assertAlmostEqual(d["i_pk"], 0.034)
        self.assertGreater(d["i_max"], 0)
        self.assertAlmostEqual(d["i_avg"], 30e-6)


if __name__ == "__main__":
    unittest.main()
