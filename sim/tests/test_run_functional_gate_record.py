#!/usr/bin/env python3
"""Render tests for `design/sar-logic/tb/run_functional_gate.py` (issue #971).

The record text must not narrate findings its own audit data says are absent:
the per-corner rows (test counts, SDF names, Icarus-dropped class counts,
verdicts) must track the committed `fv_response.*.json` (mutated copies
included), and the tool versions must come from the call arguments and the
responses, not from hardcoded prose. `corner_verdict()` gets a failing case
per guarded field, against the committed SDFs it hashes. No `klt`, OpenROAD
or PDK needed:

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
TOOLCHAIN = REPO / "design" / "sar-logic" / "flow" / "toolchain.json"

gate = load_module("run_functional_gate", TB / "run_functional_gate.py")

FV_DIR = TB / "reports" / "20261121-074936-ccac27a2"
RID = "20261121-074936-ccac27a2"
WHEN = datetime.datetime(2026, 11, 21, 7, 49, 36, tzinfo=datetime.timezone.utc)
KLT_V = "9.9.9.dev1+gfeedface"
SHA = "c0ffee0000000000000000000000000000000000"
PDK_VARIANT = "gf180mcuD"
PDK_VERSION = "open_pdks-unit-test"
PDK_SOURCE = "stub (no install searched)"


class _StubPdk:
    variant = PDK_VARIANT
    version = PDK_VERSION
    source = PDK_SOURCE


def _sdf(corner: str) -> Path:
    return gate.STA_REPORTS / f"{gate.STA_SDF_RID}.mcu7t5v0.sar_ctrl.{corner}.sdf"


def _load(corner: str) -> dict:
    return json.loads((FV_DIR / f"fv_response.{corner}.json").read_text())


def _resp(corner: str) -> dict:
    return copy.deepcopy(_load(corner))


def _committed_corners() -> list[tuple[str, dict, Path, bool, list[str]]]:
    corners = []
    for corner, _ in gate.CORNERS:
        response = _load(corner)
        ok, problems = gate.corner_verdict(corner, response, _sdf(corner))
        corners.append((corner, response, _sdf(corner), ok, problems))
    return corners


def _render(corners, *, dirty=False) -> str:
    return gate.render_record(
        rid=RID,
        when=WHEN,
        pdk=_StubPdk(),
        klt_v=KLT_V,
        corners=corners,
        dirty=dirty,
        sha=SHA,
    )


def _row(text: str, corner: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| `{corner}` |"):
            return line
    raise AssertionError(f"no table row for corner {corner}")


class CornerVerdict(unittest.TestCase):
    def test_committed_evidence_passes_every_corner(self):
        for corner, response, sdf, ok, problems in _committed_corners():
            self.assertTrue(ok, f"{corner}: {problems}")
            self.assertEqual(problems, [])

    def test_status_not_pass(self):
        response = _resp("ss_125C_3v00")
        response["status"] = "fail"
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("status 'fail'" in p for p in problems), problems)

    def test_sdf_not_annotated(self):
        response = _resp("ss_125C_3v00")
        response["environment"]["sdf"]["annotated"] = False
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("environment.sdf.annotated is not true" in p for p in problems), problems)

    def test_sdf_block_absent(self):
        response = _resp("ss_125C_3v00")
        del response["environment"]["sdf"]
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("environment.sdf.annotated is not true" in p for p in problems), problems)

    def test_provenance_sdf_hash_wrong(self):
        response = _resp("ss_125C_3v00")
        response["provenance"]["sdf_sha256"] = "0" * 64
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("provenance.sdf_sha256" in p for p in problems), problems)

    def test_sdf_file_swapped(self):
        response = _resp("ss_125C_3v00")
        other = _sdf("tt_025C_3v30")
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, other)
        self.assertFalse(ok)
        self.assertTrue(any("!= committed" in p for p in problems), problems)

    def test_netlist_pin_absent(self):
        response = _resp("ss_125C_3v00")
        response["environment"]["sources"] = [
            s for s in response["environment"]["sources"]
            if s.get("path") != "layout/adc-top/sar_ctrl/sar_ctrl.v"
        ]
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("netlist source pin" in p for p in problems), problems)

    def test_netlist_pin_duplicated(self):
        response = _resp("ss_125C_3v00")
        pinned = [
            s for s in response["environment"]["sources"]
            if s.get("path") == "layout/adc-top/sar_ctrl/sar_ctrl.v"
        ]
        response["environment"]["sources"].append(copy.deepcopy(pinned[0]))
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("netlist source pin" in p for p in problems), problems)

    def test_netlist_pin_wrong_hash(self):
        response = _resp("ss_125C_3v00")
        for s in response["environment"]["sources"]:
            if s.get("path") == "layout/adc-top/sar_ctrl/sar_ctrl.v":
                s["sha256"] = "f" * 64
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("netlist source pin" in p for p in problems), problems)

    def test_none_path_source_does_not_satisfy_pin(self):
        response = _resp("ss_125C_3v00")
        for s in response["environment"]["sources"]:
            if s.get("path") == "layout/adc-top/sar_ctrl/sar_ctrl.v":
                s["path"] = None
        ok, problems = gate.corner_verdict("ss_125C_3v00", response, _sdf("ss_125C_3v00"))
        self.assertFalse(ok)
        self.assertTrue(any("netlist source pin" in p for p in problems), problems)


class RenderTracksData(unittest.TestCase):
    def setUp(self):
        self.corners = _committed_corners()
        self.text = _render(self.corners)

    def test_verdict_pass_with_rows_from_committed_data(self):
        self.assertIn("**PASS**", self.text)
        self.assertNotIn("FAIL", self.text.split("## What the dropped classes mean")[0].replace("| PASS |", ""))
        for corner, response, sdf, _, _ in self.corners:
            row = _row(self.text, corner)
            self.assertIn(f"{response['passed_count']}/{response['test_count']}", row)
            self.assertIn(sdf.name, row)
            dropped = ", ".join(f"{k}×{v['count']}" for k, v in response["environment"]["sdf"]["dropped"].items())
            self.assertIn(dropped, row)
            self.assertTrue(row.endswith("| PASS |"), row)

    def test_dropped_counts_emptied_to_none(self):
        corners = copy.deepcopy(self.corners)
        corner, response, sdf, _, _ = corners[0]
        response["environment"]["sdf"]["dropped"] = {}
        corners[0] = (corner, response, sdf, True, [])
        text = _render(corners)
        row = _row(text, corner)
        self.assertIn("| none |", row)
        committed = _load(corner)["environment"]["sdf"]["dropped"]
        for cls, meta in committed.items():
            self.assertNotIn(f"{cls}×{meta['count']}", row)

    def test_flipped_corner_makes_fail_verdict(self):
        corners = copy.deepcopy(self.corners)
        corner, response, sdf, _, _ = corners[2]
        response["status"] = "fail"
        ok, problems = gate.corner_verdict(corner, response, sdf)
        corners[2] = (corner, response, sdf, ok, problems)
        text = _render(corners)
        self.assertIn("**FAIL**", text)
        row = _row(text, corner)
        self.assertIn("FAIL: status 'fail'", row)
        for other, _, _, _, _ in corners:
            if other != corner:
                self.assertTrue(_row(text, other).endswith("| PASS |"))

    def test_counts_follow_mutation(self):
        corners = copy.deepcopy(self.corners)
        corner, response, sdf, _, _ = corners[1]
        response["passed_count"] = 3
        corners[1] = (corner, response, sdf, True, [])
        row = _row(_render(corners), corner)
        self.assertIn("3/4", row)
        self.assertNotIn("4/4", row)

    def test_tool_versions_from_arguments_and_response(self):
        first = self.corners[0][1]["environment"]
        self.assertIn(f"`klt` `{KLT_V}`", self.text)
        self.assertIn(f"icarus `{first['engine_version']}`", self.text)
        self.assertIn(f"cocotb `{first['cocotb_version']}`", self.text)
        self.assertIn(f"PDK variant `{PDK_VARIANT}`", self.text)
        self.assertIn(f"open_pdks `{PDK_VERSION}`", self.text)
        self.assertIn(f"resolved via `{PDK_SOURCE}`", self.text)

    def test_toolchain_pin_quotes_flow_toolchain_json(self):
        # Same class of check as the sdf driver's: the pin in this sentence is
        # hardcoded prose (here the bare version, `klt ` prefix stripped), so
        # require it to agree with the committed `toolchain.json` pin.
        pin = json.loads(TOOLCHAIN.read_text())["klt_version"]
        self.assertIn(f"pin (`{pin.removeprefix('klt ')}`)", self.text)

    def test_ifnone_modpath_explanation_matches_klt_report(self):
        # The dropped-arc prose is hand-written, so it can overclaim or underclaim
        # without any table row changing. klt reports `iopath_ifnone_edge_modpath`
        # arcs as simulating with NO module-path delay at all; an earlier revision
        # described them as a mere condition-parser limitation (it lumped them with
        # `iopath_cond_expression`), which understates what the run leaves
        # unrepresented. Pin the explanation, and the entry count it quotes.
        text = " ".join(self.text.split())
        self.assertIn("simulate with NO module-path delay at all", text)
        self.assertIn("not represented in this run", text)
        self.assertNotIn("`iopath_cond_expression` / `iopath_ifnone_edge_modpath`", text)
        for corner, response, _, _, _ in self.corners:
            count = response["environment"]["sdf"]["dropped"]["iopath_ifnone_edge_modpath"]["count"]
            self.assertIn(f"({count} entries per corner)", text, corner)

    def test_bench_hash_from_committed_bench(self):
        bench = TB / "test_sar_ctrl.py"
        self.assertIn(f"`{gate.sha256(bench)}`", self.text)

    def test_when_and_sha_from_arguments(self):
        self.assertIn(WHEN.strftime("%Y-%m-%d %H:%M:%S UTC"), self.text)
        self.assertIn(f"commit `{SHA}`", self.text)

    def test_clean_tree(self):
        self.assertIn("working tree clean", self.text)
        self.assertNotIn("DIRTY at run time", self.text)

    def test_dirty_tree(self):
        text = _render(self.corners, dirty=True)
        self.assertIn("DIRTY at run time", text)
        self.assertNotIn("working tree clean", text)


if __name__ == "__main__":
    unittest.main()
