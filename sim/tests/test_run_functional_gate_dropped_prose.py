#!/usr/bin/env python3
"""Render tests for the dropped-class prose in `design/sar-logic/tb/run_functional_gate.py`
(issue #988).

The explanation below the record's corner table must agree with the table's own evidence
instead of quoting the archived run's counts: a `iopath_ifnone_edge_modpath` loss is claimed
only when the responses report drops, and a per-corner count is claimed only when every
corner reports the same one. All cases are in-memory mutations of the committed
`fv_response.*.json`; no `klt`, simulator, PDK install or replay run:

    python3 -m unittest discover -s sim/tests -t sim/tests
"""

from __future__ import annotations

import copy
import datetime
import json
import unittest
from pathlib import Path

from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]
TB = REPO / "design" / "sar-logic" / "tb"

gate = load_module("run_functional_gate", TB / "run_functional_gate.py")

FV_DIR = TB / "reports" / "20261121-074936-ccac27a2"
RID = "20261121-074936-ccac27a2"
WHEN = datetime.datetime(2026, 11, 21, 7, 49, 36, tzinfo=datetime.timezone.utc)
KLT_V = "9.9.9.dev1+gfeedface"
SHA = "c0ffee0000000000000000000000000000000000"

IFNONE = "iopath_ifnone_edge_modpath"


class _StubPdk:
    variant = "gf180mcuD"
    version = "open_pdks-unit-test"
    source = "stub (no install searched)"


def _sdf(corner: str) -> Path:
    return gate.STA_REPORTS / f"{gate.STA_SDF_RID}.mcu7t5v0.sar_ctrl.{corner}.sdf"


def _load(corner: str) -> dict:
    return json.loads((FV_DIR / f"fv_response.{corner}.json").read_text())


def _committed_corners() -> list[tuple[str, dict, Path, bool, list[str]]]:
    corners = []
    for corner, _ in gate.CORNERS:
        response = _load(corner)
        ok, problems = gate.corner_verdict(corner, response, _sdf(corner))
        corners.append((corner, response, _sdf(corner), ok, problems))
    return corners


def _render(corners) -> str:
    return gate.render_record(
        rid=RID,
        when=WHEN,
        pdk=_StubPdk(),
        klt_v=KLT_V,
        corners=corners,
        dirty=False,
        sha=SHA,
    )


def _row(text: str, corner: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| `{corner}` |"):
            return line
    raise AssertionError(f"no table row for corner {corner}")


def _flat(text: str) -> str:
    return " ".join(text.split())


class ArchivedCountsExplained(unittest.TestCase):
    def test_committed_evidence_keeps_count_and_lost_delay_explanation(self):
        corners = _committed_corners()
        text = _render(corners)
        counts = {}
        for corner, response, _, _, _ in corners:
            count = response["environment"]["sdf"]["dropped"][IFNONE]["count"]
            counts[corner] = count
            self.assertIn(f"{IFNONE}×{count}", _row(text, corner))
        flat = _flat(text)
        self.assertIn("Icarus discards at elaboration", flat)
        self.assertIn(
            "NO module-path delay at all (neither the SDF's nor the model's placeholder)",
            flat,
        )
        self.assertIn("not represented in this run", flat)
        for count in counts.values():
            self.assertIn(f"({count} entries per corner)", flat)


class UniformCountsFollowData(unittest.TestCase):
    def test_uniform_count_different_from_archived(self):
        corners = copy.deepcopy(_committed_corners())
        for i, (corner, response, sdf, _, _) in enumerate(corners):
            response["environment"]["sdf"]["dropped"][IFNONE]["count"] = 7
            corners[i] = (corner, response, sdf, True, [])
        text = _render(corners)
        flat = _flat(text)
        self.assertIn("not represented in this run (7 entries per corner)", flat)
        self.assertNotIn("(20 entries per corner)", flat)
        for corner, _, _, _, _ in corners:
            self.assertIn(f"{IFNONE}×7", _row(text, corner))


class AllEmptyDropMaps(unittest.TestCase):
    def test_rows_show_none_and_prose_claims_no_lost_module_path_delay(self):
        corners = copy.deepcopy(_committed_corners())
        for i, (corner, response, sdf, _, _) in enumerate(corners):
            response["environment"]["sdf"]["dropped"] = {}
            corners[i] = (corner, response, sdf, True, [])
        text = _render(corners)
        for corner, _, _, _, _ in corners:
            row = _row(text, corner)
            self.assertIn("| none |", row)
            self.assertNotIn(IFNONE, row)
        flat = _flat(text)
        self.assertNotIn("entries per corner", flat)
        self.assertNotIn("not represented in this run", flat)
        self.assertIn("this run dropped none", flat)


class MixedCountsAcrossCorners(unittest.TestCase):
    def test_each_row_reports_own_evidence_and_no_common_count_claimed(self):
        corners = copy.deepcopy(_committed_corners())
        counts = {}
        for i, (corner, response, sdf, _, _) in enumerate(corners):
            if i == 0:
                response["environment"]["sdf"]["dropped"] = {}
                counts[corner] = None
            else:
                response["environment"]["sdf"]["dropped"][IFNONE]["count"] = i
                counts[corner] = i
            corners[i] = (corner, response, sdf, True, [])
        text = _render(corners)
        for corner, _, _, _, _ in corners:
            row = _row(text, corner)
            if counts[corner] is None:
                self.assertIn("| none |", row)
                self.assertNotIn(IFNONE, row)
            else:
                self.assertIn(f"{IFNONE}×{counts[corner]}", row)
        flat = _flat(text)
        self.assertNotIn("entries per corner", flat)
        self.assertNotIn("not represented in this run", flat)
        self.assertIn("corners that dropped them", flat)
        self.assertIn("per-corner counts in the table", flat)


if __name__ == "__main__":
    unittest.main()
