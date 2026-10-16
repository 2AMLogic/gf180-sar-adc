#!/usr/bin/env python3
"""Render tests for `design/sar-logic/flow/sta_postroute_spef_record.py` (issue #533).

The record text must not narrate findings its own audit data says are absent,
nor hardcode a klt build other than the one recorded in `ev`. Inputs are the
committed `*.sta_postroute_spef.audit.json` files (read only): one with
rejected nets, and a copy of it with the findings emptied and every corner
accepted. No `klt`, OpenROAD or PDK needed:

    python3 -m unittest discover -s sim/tests -t sim/tests
"""

from __future__ import annotations

import copy
import datetime
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FLOW = REPO / "design" / "sar-logic" / "flow"
sys.path.insert(0, str(FLOW))

import sta_postroute_spef_record as rec  # noqa: E402

REPORTS = FLOW / "sar_ctrl" / "reports"
REJECTED_JSON = REPORTS / "20261009-131918-bf22e71c.mcu7t5v0.sta_postroute_spef.audit.json"
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


if __name__ == "__main__":
    unittest.main()
