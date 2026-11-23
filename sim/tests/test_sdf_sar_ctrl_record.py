#!/usr/bin/env python3
"""Render tests for `design/sar-logic/flow/sdf_sar_ctrl.py` (issue #971).

The record text must not narrate findings its own audit data says are absent:
the per-corner table, the verdict line and the failing-corner list must track
the committed `sta_response.json` (mutated copies included), and the tool
versions must come from the call arguments, not from hardcoded prose.
`corner_ok()` gets a failing case per guarded field, and the
`check_qualified_inputs()` hash gate is exercised against the committed tree,
a missing input and a moved input. No `klt`, OpenROAD or PDK needed:

    python3 -m unittest discover -s sim/tests -t sim/tests
"""

from __future__ import annotations

import copy
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]
FLOW = REPO / "design" / "sar-logic" / "flow"

drv = load_module("sdf_sar_ctrl", FLOW / "sdf_sar_ctrl.py")

STA_RESPONSE = FLOW / "sar_ctrl" / "reports" / "20261121-074733-ccac27a2.mcu7t5v0.sta_sdf.sta_response.json"
RID = "20261121-074733-ccac27a2"
WHEN = datetime.datetime(2026, 11, 21, 7, 47, 33, tzinfo=datetime.timezone.utc)
KLT_V = "9.9.9.dev1+gfeedface"
SHA = "c0ffee0000000000000000000000000000000000"
PDK_VARIANT = "gf180mcuD"
PDK_VERSION = "open_pdks-unit-test"
PDK_SOURCE = "stub (no install searched)"


class _StubPdk:
    variant = PDK_VARIANT
    version = PDK_VERSION
    source = PDK_SOURCE


def _load() -> dict:
    return json.loads(STA_RESPONSE.read_text())


def _sdfs(response: dict) -> list[tuple[str, str]]:
    return [
        (e["corner"], f"design/sar-logic/flow/sar_ctrl/reports/{RID}.{drv.LIB_TAG}.sar_ctrl.{e['corner']}.sdf")
        for e in response["corners"]
    ]


def _render(response: dict, *, sdfs=None, dirty=False) -> str:
    return drv.render_record(
        rid=RID,
        when=WHEN,
        pdk=_StubPdk(),
        klt_v=KLT_V,
        response=response,
        sdfs=sdfs if sdfs is not None else _sdfs(response),
        dirty=dirty,
        sha=SHA,
    )


def _row(text: str, corner: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| `{corner}` |"):
            return line
    raise AssertionError(f"no table row for corner {corner}")


class CornerOk(unittest.TestCase):
    def setUp(self):
        self.entry = _load()["corners"][0]

    def test_committed_response_all_pass(self):
        for entry in _load()["corners"]:
            self.assertTrue(drv.corner_ok(entry), entry["corner"])

    def test_pass(self):
        self.assertTrue(drv.corner_ok(self.entry))

    def test_timing_status_not_constrained(self):
        self.entry["timing_status"] = "unconstrained"
        self.assertFalse(drv.corner_ok(self.entry))

    def test_setup_slack_negative(self):
        self.entry["worst_slack_ns"] = -0.001
        self.assertFalse(drv.corner_ok(self.entry))

    def test_setup_slack_none(self):
        self.entry["worst_slack_ns"] = None
        self.assertFalse(drv.corner_ok(self.entry))

    def test_hold_slack_negative(self):
        self.entry["worst_hold_slack_ns"] = -1.0
        self.assertFalse(drv.corner_ok(self.entry))

    def test_hold_slack_none(self):
        self.entry["worst_hold_slack_ns"] = None
        self.assertFalse(drv.corner_ok(self.entry))

    def test_annotation_incomplete(self):
        self.entry["spef_annotation"]["annotation_complete"] = False
        self.assertFalse(drv.corner_ok(self.entry))

    def test_annotation_block_absent(self):
        del self.entry["spef_annotation"]
        self.assertFalse(drv.corner_ok(self.entry))


class RenderTracksData(unittest.TestCase):
    def setUp(self):
        self.response = _load()
        self.text = _render(self.response)

    def test_verdict_pass_with_happy_path_phrase(self):
        self.assertIn("**PASS**", self.text)
        self.assertIn("every corner `constrained`", self.text)
        self.assertNotIn("failing corner(s)", self.text)

    def test_rows_follow_committed_data(self):
        for entry in self.response["corners"]:
            corner = entry["corner"]
            row = _row(self.text, corner)
            self.assertIn(f"{entry['worst_slack_ns']:+.4f}", row)
            self.assertIn(f"{entry['worst_hold_slack_ns']:+.4f}", row)
            self.assertIn(f"{entry['fmax_mhz']:.2f}", row)
            self.assertIn(entry["sdf"]["content_hash"], row)
            self.assertTrue(row.endswith("| PASS |"), row)

    def test_committed_sdfs_listed(self):
        for _, rel in _sdfs(self.response):
            self.assertIn(rel, self.text)

    def test_tool_versions_from_arguments_and_response(self):
        self.assertIn(f"`klt` `{KLT_V}`", self.text)
        self.assertIn(f"PDK variant `{PDK_VARIANT}`", self.text)
        self.assertIn(f"open_pdks `{PDK_VERSION}`", self.text)
        self.assertIn(f"(via {PDK_SOURCE})", self.text)
        self.assertIn(f"engine `{self.response['engine']}` `{self.response['engine_version']}`", self.text)

    def test_toolchain_pin_quotes_flow_toolchain_json(self):
        # The pin in this sentence is hardcoded prose, not a `render_record()`
        # argument, so a `toolchain.json` bump would leave it stale silently.
        # Require the rendered quote to agree with the committed pin.
        pin = json.loads((FLOW / "toolchain.json").read_text())["klt_version"]
        self.assertIn(f"pin (`{pin}`)", self.text)

    def test_when_and_sha_from_arguments(self):
        self.assertIn(WHEN.strftime("%Y-%m-%d %H:%M:%S UTC"), self.text)
        self.assertIn(f"commit `{SHA}`", self.text)

    def test_clean_tree(self):
        self.assertIn("working tree clean", self.text)
        self.assertNotIn("DIRTY at run time", self.text)

    def test_dirty_tree(self):
        text = _render(self.response, dirty=True)
        self.assertIn("DIRTY at run time", text)
        self.assertNotIn("working tree clean", text)

    def test_flipped_corner_makes_fail_verdict(self):
        response = copy.deepcopy(self.response)
        bad = response["corners"][1]["corner"]
        response["corners"][1]["timing_status"] = "unconstrained"
        text = _render(response)
        self.assertIn("**FAIL**", text)
        self.assertNotIn("**PASS**", text)
        self.assertIn(f"failing corner(s): {bad}", text)
        self.assertNotIn("every corner `constrained`", text)
        self.assertTrue(_row(text, bad).endswith("| FAIL |"))
        for entry in response["corners"]:
            if entry["corner"] != bad:
                self.assertTrue(_row(text, entry["corner"]).endswith("| PASS |"))

    def test_negative_slack_also_fails(self):
        response = copy.deepcopy(self.response)
        response["corners"][2]["worst_slack_ns"] = -0.25
        text = _render(response)
        self.assertIn("**FAIL**", text)
        self.assertIn(f"failing corner(s): {response['corners'][2]['corner']}", text)

    def test_numbers_follow_mutation(self):
        response = copy.deepcopy(self.response)
        entry = response["corners"][0]
        corner = entry["corner"]
        old = (f"{entry['worst_slack_ns']:+.4f}", f"{entry['fmax_mhz']:.2f}")
        entry["worst_slack_ns"] = -1.2345
        entry["fmax_mhz"] = 111.11
        row = _row(_render(response), corner)
        self.assertIn("-1.2345", row)
        self.assertIn("111.11", row)
        for value in old:
            self.assertNotIn(value, row)

    def test_sdf_hash_follows_mutation(self):
        response = copy.deepcopy(self.response)
        entry = response["corners"][0]
        old_hash = entry["sdf"]["content_hash"]
        entry["sdf"]["content_hash"] = "sha256:" + "ab" * 32
        row = _row(_render(response), entry["corner"])
        self.assertIn("sha256:" + "ab" * 32, row)
        self.assertNotIn(old_hash, row)


class QualifiedInputGate(unittest.TestCase):
    def test_committed_tree_passes(self):
        drv.check_qualified_inputs()

    def test_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(drv, "REPO_ROOT", Path(tmp)):
                with self.assertRaises(drv.SdfModeError) as ctx:
                    drv.check_qualified_inputs()
            self.assertIn("qualified-receipt input missing", str(ctx.exception))

    def test_moved_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in drv.QUALIFIED_INPUT_SHA256:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"stale bytes: a P&R rerun regenerated this\n")
            with mock.patch.object(drv, "REPO_ROOT", root):
                with self.assertRaises(drv.SdfModeError) as ctx:
                    drv.check_qualified_inputs()
            self.assertIn("orphaned", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
