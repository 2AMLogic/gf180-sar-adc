#!/usr/bin/env python3
"""Tests for the 5.digital evidence behind issue #642.

1. The committed `klt functional-verification` envelope (and the mutation run
   beside it) shows no failed test and no surviving mutant.
2. The multi-corner STA verdict rule: a negative-slack corner, or one that is
   not `constrained`, fails -- it is never dropped.
3. The manifest cites both parts as `5.digital`.
4. (issue #1133) A corner whose setup or hold slack `klt sta` did not report
   is such a FAIL too: the record renders it as `n/a` and names it, and the
   command exits 1 instead of raising -- under `--no-record` as well.

No PDK, no `klt`, no simulator needed:

    python3 -m unittest sim.tests.test_sar_ctrl_5digital -v
"""

from __future__ import annotations

import contextlib
import copy
import datetime
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]

STA_DRIVER = REPO / "design" / "sar-logic" / "flow" / "sta_sar_ctrl_postroute.py"
STA_RID = "20261027-011416-812549af"
STA_WHEN = datetime.datetime(2026, 10, 27, 1, 14, 16, tzinfo=datetime.timezone.utc)
KLT_V = "9.9.9.dev1+gfeedface"
SHA = "c0ffee0000000000000000000000000000000000"
#: The committed corner every unreported-slack case mutates.
BAD_CORNER = "ss_125C_3v00"


class _StubPdk:
    variant = "gf180mcuD"
    version = "open_pdks-unit-test"
    source = "stub (no install searched)"


def _cited_fv_envelope() -> Path:
    manifest = json.loads((REPO / "signoff" / "gf180-sar-adc.manifest.json").read_text())
    (fv,) = [p["file"] for p in manifest["evidence"]["5.digital"] if "fv_response" in p["file"]]
    return REPO / fv


def _cited_sta_response() -> dict:
    manifest = json.loads((REPO / "signoff" / "gf180-sar-adc.manifest.json").read_text())
    (sta,) = [p["file"] for p in manifest["evidence"]["5.digital"] if "sta_response" in p["file"]]
    return json.loads((REPO / sta).read_text())


def _render(mod, response: dict) -> str:
    return mod.render_multicorner_record(
        rid=STA_RID, when=STA_WHEN, pdk=_StubPdk(), klt_v=KLT_V, response=response, dirty=False, sha=SHA
    )


def _row(text: str, corner: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| `{corner}` |"):
            return line
    raise AssertionError(f"no table row for corner {corner}")


class CommittedFunctionalEnvelope(unittest.TestCase):
    def test_no_failed_tests(self):
        env = json.loads(_cited_fv_envelope().read_text())
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["failed_count"], 0)
        self.assertEqual(env["skipped_count"], 0)
        self.assertGreater(env["passed_count"], 0)
        self.assertEqual([t["name"] for t in env["tests"] if t["status"] != "passed"], [])

    def test_every_mutant_killed(self):
        mut = json.loads((_cited_fv_envelope().parent / "mutation_response.json").read_text())
        mt = mut["mutation_testing"]
        self.assertEqual(mt["rejected_count"], 0)
        self.assertEqual(mt["survived_count"], 0)
        self.assertEqual(mt["killed_count"], mt["valid_count"])


class CornerVerdict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mod = load_module("sta_postroute_5dig", REPO / "design" / "sar-logic" / "flow" / "sta_sar_ctrl_postroute.py")
        cls.ok = staticmethod(mod._corner_ok)

    def entry(self, **kw):
        base = {"timing_status": "constrained", "worst_slack_ns": 1.0, "worst_hold_slack_ns": 0.1}
        return {**base, **kw}

    def test_passing_corner(self):
        self.assertTrue(self.ok(self.entry()))

    def test_negative_setup_fails(self):
        self.assertFalse(self.ok(self.entry(worst_slack_ns=-0.01)))

    def test_negative_hold_fails(self):
        self.assertFalse(self.ok(self.entry(worst_hold_slack_ns=-0.01)))

    def test_unconstrained_fails(self):
        self.assertFalse(self.ok(self.entry(timing_status="unconstrained")))
        self.assertFalse(self.ok({"worst_slack_ns": 1.0, "worst_hold_slack_ns": 0.1}))

    def test_unreported_slack_fails_without_raising(self):
        """Issue #1133: `_corner_ok` indexed the slacks directly, so a null
        slack raised TypeError and an absent one KeyError -- a crash, where
        the rule is a FAIL like any other corner that did not meet timing."""
        for field in ("worst_slack_ns", "worst_hold_slack_ns"):
            with self.subTest(field=field, slack=None):
                self.assertFalse(self.ok(self.entry(**{field: None})))
            entry = self.entry()
            del entry[field]
            with self.subTest(field=field, slack="absent"):
                self.assertFalse(self.ok(entry))
        self.assertFalse(self.ok({"timing_status": "constrained"}))
        self.assertFalse(self.ok(self.entry(timing_status="unconstrained", worst_slack_ns=None, worst_hold_slack_ns=None)))


class CommittedStaCitation(unittest.TestCase):
    def test_all_five_corners_pass_the_rule(self):
        manifest = json.loads((REPO / "signoff" / "gf180-sar-adc.manifest.json").read_text())
        (sta,) = [p["file"] for p in manifest["evidence"]["5.digital"] if "sta_response" in p["file"]]
        resp = json.loads((REPO / sta).read_text())
        self.assertEqual(len(resp["corners"]), 5)
        self.assertEqual(resp["geometry_source"], "routed")
        self.assertIsNone(resp["spef_path"])
        for c in resp["corners"]:
            self.assertEqual(c["timing_status"], "constrained", c["corner"])
            self.assertGreaterEqual(c["worst_slack_ns"], 0, c["corner"])
            self.assertGreaterEqual(c["worst_hold_slack_ns"], 0, c["corner"])


class MulticornerRecordNamesUnreportedSlack(unittest.TestCase):
    """Issue #1133: a corner whose setup or hold slack `klt sta` did not report
    reaches the record as `n/a` and FAIL, and is named on the Overall line.

    Before the fix the renderer applied `:+.4f` to `entry["worst_slack_ns"]`
    directly: a null slack raised TypeError and an absent key KeyError. The
    command renders before it looks for failing corners, so `--no-record`
    crashed the same way. Complete corners must render exactly as before: the
    pre-#1133 row expression, applied to the committed response, is the
    expectation for every untouched corner."""

    ABSENT = object()

    #: (case, change to the corner, expected setup cell, expected hold cell).
    #: A cell naming a field is that field's committed value as `+x.xxxx`.
    CASES = (
        ("null setup slack", {"worst_slack_ns": None}, "n/a", "worst_hold_slack_ns"),
        ("absent setup slack", {"worst_slack_ns": ABSENT}, "n/a", "worst_hold_slack_ns"),
        ("null hold slack", {"worst_hold_slack_ns": None}, "worst_slack_ns", "n/a"),
        ("absent hold slack", {"worst_hold_slack_ns": ABSENT}, "worst_slack_ns", "n/a"),
        ("both slacks absent", {"worst_slack_ns": ABSENT, "worst_hold_slack_ns": ABSENT}, "n/a", "n/a"),
        (
            "unconstrained corner with null slacks",
            {"timing_status": "unconstrained", "worst_slack_ns": None, "worst_hold_slack_ns": None},
            "n/a",
            "n/a",
        ),
    )

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module("sta_postroute_5dig_render", STA_DRIVER)
        cls.complete = _cited_sta_response()
        cls.complete_text = _render(cls.mod, cls.complete)
        (cls.bad_index,) = [i for i, c in enumerate(cls.complete["corners"]) if c["corner"] == BAD_CORNER]

    @staticmethod
    def _cell(intact: dict, expected: str) -> str:
        return expected if expected == "n/a" else f"{intact[expected]:+.4f}"

    def _mutated(self, **changes) -> dict:
        response = copy.deepcopy(self.complete)
        entry = response["corners"][self.bad_index]
        for field, value in changes.items():
            if value is self.ABSENT:
                del entry[field]
            else:
                entry[field] = value
        return response

    def test_complete_corners_render_as_they_always_did(self):
        self.assertIn(
            "- **Overall**: **PASS** -- every corner `constrained` with non-negative setup and hold slack.",
            self.complete_text,
        )
        self.assertNotIn("n/a", self.complete_text)
        for entry in self.complete["corners"]:
            with self.subTest(corner=entry["corner"]):
                self.assertEqual(
                    _row(self.complete_text, entry["corner"]),
                    f"| `{entry['corner']}` | constrained | {entry['worst_slack_ns']:+.4f} | "
                    f"{entry['worst_hold_slack_ns']:+.4f} | "
                    f"{entry['setup_violation_count']} / {entry['hold_violation_count']} | PASS |",
                )

    def test_unreported_slack_is_na_and_fail_and_named_on_the_overall_line(self):
        intact = self.complete["corners"][self.bad_index]
        for label, changes, setup, hold in self.CASES:
            with self.subTest(case=label):
                text = _render(self.mod, self._mutated(**changes))
                self.assertEqual(
                    _row(text, BAD_CORNER),
                    f"| `{BAD_CORNER}` | {changes.get('timing_status', intact['timing_status'])} | "
                    f"{self._cell(intact, setup)} | {self._cell(intact, hold)} | "
                    f"{intact['setup_violation_count']} / {intact['hold_violation_count']} | FAIL |",
                )
                self.assertIn(f"- **Overall**: **FAIL** -- failing corner(s): {BAD_CORNER}.", text)
                self.assertNotIn("**PASS**", text)
                for entry in self.complete["corners"]:
                    if entry["corner"] != BAD_CORNER:
                        self.assertEqual(_row(text, entry["corner"]), _row(self.complete_text, entry["corner"]))

    def test_every_unreported_corner_is_named_in_response_order(self):
        other = "ss_n40C_3v00"
        response = self._mutated(worst_slack_ns=None)
        (index,) = [i for i, c in enumerate(response["corners"]) if c["corner"] == other]
        del response["corners"][index]["worst_hold_slack_ns"]
        names = [c["corner"] for c in response["corners"] if c["corner"] in (BAD_CORNER, other)]
        self.assertEqual(names, [BAD_CORNER, other], "the fixture must mutate two distinct corners")
        text = _render(self.mod, response)
        self.assertIn(f"- **Overall**: **FAIL** -- failing corner(s): {', '.join(names)}.", text)
        for corner in names:
            self.assertTrue(_row(text, corner).endswith("| FAIL |"), corner)


class MulticornerModeExitsOneOnUnreportedSlack(unittest.TestCase):
    """Issue #1133, the command half: `run_multicorner_mode` reports
    `FAIL at corner(s): <corner>` on stderr and returns 1 for a corner with an
    unreported slack instead of raising -- with `write_record=False` (the
    `--no-record` path), which reaches the renderer too."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module("sta_postroute_5dig_cmd", STA_DRIVER)

    def _run(self, response: dict) -> tuple[int, str, list[str], bool]:
        """`run_multicorner_mode(write_record=False)` against `response`, with
        every tool call stubbed and both output directories redirected to a
        temp dir. Returns (exit code, stderr, files written under the report
        directory, whether the record directory was left uncreated)."""
        mod = self.mod
        with tempfile.TemporaryDirectory() as tmp:
            reports, records = Path(tmp) / "reports", Path(tmp) / "records"
            reports.mkdir()
            out, err = io.StringIO(), io.StringIO()
            with (
                mock.patch.object(mod, "REPORTS_DIR", reports),
                mock.patch.object(mod, "RECORDS_DIR", records),
                mock.patch.object(mod, "run_klt_json", return_value=copy.deepcopy(response)),
                mock.patch.object(mod, "klt_version", return_value=KLT_V),
                mock.patch.object(mod, "git", return_value=SHA),
                mock.patch.object(mod, "working_tree_dirty", return_value=False),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                rc = mod.run_multicorner_mode(pdk=_StubPdk(), rid=STA_RID, when=STA_WHEN, write_record=False)
            return rc, err.getvalue(), sorted(p.name for p in reports.iterdir()), not records.exists()

    def test_complete_response_exits_zero(self):
        """The control: the same stubs, fed the committed response, pass."""
        rc, err, written, _ = self._run(_cited_sta_response())
        self.assertEqual((rc, err), (0, ""))
        stem = f"{STA_RID}.mcu7t5v0.sta_postroute_multicorner"
        self.assertEqual(written, [f"{stem}.sta_{part}.json" for part in ("request", "response")])

    def test_unreported_slack_exits_one_and_names_the_corner(self):
        for label, field in (("null", "worst_slack_ns"), ("absent", "worst_hold_slack_ns")):
            response = _cited_sta_response()
            (bad,) = [c for c in response["corners"] if c["corner"] == BAD_CORNER]
            if label == "null":
                bad[field] = None
            else:
                del bad[field]
            with self.subTest(slack=label):
                rc, err, written, no_record = self._run(response)
                self.assertEqual(rc, 1)
                self.assertEqual(err, f"FAIL at corner(s): {BAD_CORNER}\n")
                self.assertTrue(no_record, "--no-record must not create the record directory")
                self.assertEqual(len(written), 2, "the request and response JSON are still kept")


if __name__ == "__main__":
    unittest.main()
