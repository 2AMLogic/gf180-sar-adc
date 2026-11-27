"""Issue #1092: `run_extract` (the LVS proof cell) and `run_block_extract`
(every block-level cell) in `layout/lvs/run_lvs.py` must report the same
diagnostic for the same defect in their shared verification core.

Why this test exists: both functions run `klt extract` into a scratch
directory, assert the same six scalar report fields plus
`status == "extracted"` against the manifest entry's `expect` block, and
compare the fresh netlist byte-for-byte with the committed one. Before
#1092 each carried its own copy of that core, and the copies had drifted:
the proof cell said ``extract dbu_um mismatch: expected ...`` while a block
said ``<name> extract dbu_um: expected ...``, and only the proof cell's
byte-mismatch message suggested ``--regen``. Nothing asserted the agreement,
so a fix to one copy could leave the other stale. They now share one private
helper, and this file pins both halves of that contract:

* **parity** -- given the same manifest entry and the same injected defect,
  both public entry points return the same failure list, byte for byte;
* **each entry point keeps only its own extra checks** -- the proof cell's
  ``devices[]``/``nets[]``/``device_classes``/any-warning assertions stay in
  `run_extract` and are not applied to a block, whose warning check is
  `_check_warnings`' substring/count match instead.

The block wording is also what committed `layout/lvs/records/*.md` carry, so
the byte-for-byte drift message is pinned literally (cell-name prefix and
the klayout-tools#1063 cross-platform net-numbering caveat).

Nothing here runs `klt`, needs the PDK, or imports `klayout`: the module's
`CELLS_DIR` is pointed at a temporary directory and `subprocess.run` is
replaced by a fake that writes the scratch netlist and returns a canned JSON
report, so the real `_run_extract_json`, scratch-directory and
committed-file paths are exercised. Stdlib only.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LAYOUT = REPO / "layout"
sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402

# run_lvs does `from klt_env import ...` / `import toolchain_pin`; both live in layout/.
if str(LAYOUT) not in sys.path:
    sys.path.insert(0, str(LAYOUT))

mod = load_module("run_lvs_shared_core_under_test", LAYOUT / "lvs" / "run_lvs.py")

KLT = "klt"
DECK = "deck.lvs"
NAME = "probe_cell_1092"
GDS = f"{NAME}.gds"
NETLIST_NAME = f"{NAME}.spice"

# A `klt extract` JSON report shaped like the live verb's: the six scalar
# fields, `status`, and the arrays only the proof cell asserts.
REPORT = {
    "status": "extracted",
    "top": "PROBE",
    "dbu_um": 0.001,
    "device_count": 1,
    "net_count": 2,
    "pin_count": 2,
    "device_counts": {"nfet": 1},
    "devices": [{"name": "M1", "model": "nfet", "nets": ["D", "G", "S", "vsubs"]}],
    "nets": [{"name": "D", "pin": True}, {"name": "G", "pin": True}],
    "warnings": [],
    "device_classes": ["nfet", "pfet"],
}

NETLIST_TEXT = "* probe netlist\n.subckt PROBE D G\n.ends\n"

SCALARS = ("top", "dbu_um", "device_count", "net_count", "pin_count", "device_counts")

# (defect label, report overrides) -- one shared-core defect per row.
SHARED_DEFECTS = (
    ("top", {"top": "OTHER"}),
    ("dbu_um", {"dbu_um": 0.005}),
    ("device_count", {"device_count": 2}),
    ("net_count", {"net_count": 3}),
    ("pin_count", {"pin_count": 3}),
    ("device_counts", {"device_counts": {"nfet": 1, "pfet": 1}}),
    ("status", {"status": "error"}),
)

# The four proof-cell-only defects, each of which must yield exactly one
# failure from `run_extract` carrying its distinctive phrase.
PROOF_ONLY_DEFECTS = (
    ("devices", {"devices": []}, "extract devices[] mismatch (this is the Metal1 pin-label proof)"),
    ("nets", {"nets": []}, "extract nets[] mismatch"),
    ("warnings", {"warnings": ["1 PMOS device ties its body ..."]},
     "extract reported unexpected warnings"),
    ("device_classes", {"device_classes": ["nfet"]}, "extract device_classes mismatch"),
)


def _entry() -> dict:
    """A manifest entry shaped like `cells.json`'s `extract` and
    `block_extractions[]` entries (`name`/`gds`/`netlist`/`expect`), whose
    `expect` carries every field either entry point reads."""
    pinned = (*SCALARS, "devices", "nets", "device_classes")
    expect = {field: copy.deepcopy(REPORT[field]) for field in pinned}
    return {"name": NAME, "gds": GDS, "netlist": NETLIST_NAME, "expect": expect}


def _as_proof_cell(entry: dict):
    return lambda: mod.run_extract(KLT, {"deck": DECK, "extract": entry})


def _as_block(entry: dict):
    return lambda: mod.run_block_extract(KLT, DECK, entry)


CALLERS = (("run_extract", _as_proof_cell), ("run_block_extract", _as_block))


class SharedExtractCoreTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cells = tmp.name
        patcher = mock.patch.object(mod, "CELLS_DIR", self.cells)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, as_caller, entry, report, netlist_text, committed_text):
        """Drive one entry point on `entry` against a canned `report` and a
        fresh `netlist_text`; `committed_text` is what the committed netlist
        holds (None: nothing is committed at all).

        Returns `(report, netlist_text, failures, argv)`.
        """
        if committed_text is not None:
            Path(self.cells, entry["netlist"]).write_bytes(committed_text.encode("utf-8"))
        argv_seen: list = []

        def fake(cmd, **kwargs):
            argv_seen.append(list(cmd))
            scratch = cmd[cmd.index("-o") + 1]
            Path(scratch).write_bytes(netlist_text.encode("utf-8"))
            return subprocess.CompletedProcess(cmd, 0, json.dumps(report), "")

        with mock.patch.object(mod.subprocess, "run", side_effect=fake):
            report_out, text_out, failures = as_caller(entry)()
        return report_out, text_out, failures, argv_seen[0]

    # -- the shared core -------------------------------------------------- #

    def test_clean_entry_passes_both_entry_points(self):
        for newline in ("\n", "\r\n"):
            netlist = NETLIST_TEXT.replace("\n", newline)
            for label, as_caller in CALLERS:
                with self.subTest(newline=newline, caller=label):
                    report, text, failures, _ = self._run(
                        as_caller, _entry(), REPORT, netlist, netlist)
                    self.assertEqual(failures, [])
                    self.assertEqual(report, REPORT)
                    self.assertEqual(text, NETLIST_TEXT)

    def test_each_entry_extracts_its_gds_into_a_vanishing_scratch_netlist(self):
        entry = _entry()
        for label, as_caller in CALLERS:
            with self.subTest(caller=label):
                _, _, failures, argv = self._run(
                    as_caller, entry, REPORT, NETLIST_TEXT, NETLIST_TEXT)
                self.assertEqual(failures, [])
                scratch = argv[argv.index("-o") + 1]
                self.assertEqual(
                    argv,
                    [KLT, "extract", os.path.join(self.cells, GDS), "--deck", DECK,
                     "-o", scratch, "--format", "json"],
                )
                self.assertEqual(os.path.basename(scratch), f"{NAME}.spice")
                self.assertTrue(
                    os.path.basename(os.path.dirname(scratch)).startswith("klt-extract-"),
                    scratch)
                self.assertFalse(os.path.exists(scratch))

    def test_every_shared_scalar_and_status_defect_is_reported_identically(self):
        for defect, overrides in SHARED_DEFECTS:
            with self.subTest(defect=defect):
                report = {**REPORT, **overrides}
                per_caller = [
                    self._run(as_caller, _entry(), report, NETLIST_TEXT, NETLIST_TEXT)[2]
                    for _, as_caller in CALLERS
                ]
                self.assertEqual(len(per_caller[0]), 1, per_caller[0])
                self.assertEqual(per_caller[0], per_caller[1])

    def test_scalar_and_status_diagnostics_name_the_cell(self):
        for defect, overrides, expected in (
            ("dbu_um", {"dbu_um": 0.005}, f"{NAME} extract dbu_um: expected 0.001, got 0.005"),
            ("top", {"top": "OTHER"}, f"{NAME} extract top: expected PROBE, got OTHER"),
            ("device_counts", {"device_counts": {"nfet": 1, "pfet": 1}},
             f"{NAME} extract device_counts: expected {{'nfet': 1}}, got "
             f"{{'nfet': 1, 'pfet': 1}}"),
            ("status", {"status": "error"},
             f"{NAME} extract status: expected 'extracted', got 'error'"),
        ):
            with self.subTest(defect=defect):
                report = {**REPORT, **overrides}
                for label, as_caller in CALLERS:
                    with self.subTest(caller=label):
                        failures = self._run(
                            as_caller, _entry(), report, NETLIST_TEXT, NETLIST_TEXT)[2]
                        self.assertEqual(failures, [expected])

    def test_netlist_byte_mismatch_is_reported_identically_with_the_caveat(self):
        entry = _entry()
        expected = [
            f"{NAME}: fresh `klt extract` output does not match the committed "
            f"{NETLIST_NAME} byte-for-byte (if only anonymous $NNN net labels "
            "differ and `klt lvs` mismatches=0, see toolchain.json's PR #195 "
            "caveat -- known cross-platform net-numbering drift, "
            "klayout-tools#1063)"
        ]
        for defect, fresh, committed in (
            ("extra line", NETLIST_TEXT, NETLIST_TEXT + "* drift\n"),
            ("CRLF vs LF", NETLIST_TEXT.replace("\n", "\r\n"), NETLIST_TEXT),
        ):
            for label, as_caller in CALLERS:
                with self.subTest(defect=defect, caller=label):
                    _, text, failures, _ = self._run(as_caller, entry, REPORT, fresh, committed)
                    self.assertEqual(failures, expected)
                    self.assertEqual(text, NETLIST_TEXT)

    def test_missing_committed_netlist_is_reported_identically(self):
        entry = _entry()
        expected = [
            f"committed netlist missing -- run --regen: "
            f"{os.path.join(self.cells, NETLIST_NAME)}"
        ]
        per_caller = [
            self._run(as_caller, entry, REPORT, NETLIST_TEXT, None)[2] for _, as_caller in CALLERS
        ]
        self.assertEqual(per_caller[0], expected)
        self.assertEqual(per_caller[0], per_caller[1])

    def test_every_shared_defect_at_once_is_reported_none_short_circuits(self):
        report = {**REPORT, "device_count": 2, "status": "error"}
        per_caller = [
            self._run(as_caller, _entry(), report, NETLIST_TEXT, NETLIST_TEXT + "* drift\n")[2]
            for _, as_caller in CALLERS
        ]
        self.assertEqual(len(per_caller[0]), 3, per_caller[0])
        self.assertEqual(per_caller[0], per_caller[1])
        self.assertIn(f"{NAME} extract device_count: expected 1, got 2", per_caller[0])
        self.assertIn(f"{NAME} extract status: expected 'extracted', got 'error'", per_caller[0])
        self.assertTrue(any("byte-for-byte" in failure for failure in per_caller[0]))

    # -- what stays exclusive to each entry point ------------------------- #

    def test_proof_cell_keeps_its_array_class_and_warning_assertions(self):
        for defect, overrides, phrase in PROOF_ONLY_DEFECTS:
            with self.subTest(defect=defect):
                report = {**REPORT, **overrides}
                failures = self._run(
                    _as_proof_cell, _entry(), report, NETLIST_TEXT, NETLIST_TEXT)[2]
                self.assertEqual(len(failures), 1, failures)
                self.assertIn(phrase, failures[0])

    def test_block_extract_stays_scalar_only(self):
        # `devices[]`, `nets[]` and `device_classes` are the proof cell's
        # proof, not a block's: run_block_extract's docstring makes the
        # per-terminal check the `klt lvs` case's job instead.
        for defect, overrides, _ in PROOF_ONLY_DEFECTS[:2] + PROOF_ONLY_DEFECTS[3:]:
            with self.subTest(defect=defect):
                report = {**REPORT, **overrides}
                failures = self._run(_as_block, _entry(), report, NETLIST_TEXT, NETLIST_TEXT)[2]
                self.assertEqual(failures, [])

    def test_block_warnings_follow_check_warnings_not_the_proof_cell_rule(self):
        report = {**REPORT, "warnings": ["2 drawn capacitor ..."]}
        sanctioned = _entry()
        sanctioned["expect"]["warnings"] = ["drawn capacitor"]

        failures = self._run(_as_block, _entry(), report, NETLIST_TEXT, NETLIST_TEXT)[2]
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(f"{NAME} extract: expected 0 warning(s), got 1", failures[0])

        failures = self._run(_as_block, sanctioned, report, NETLIST_TEXT, NETLIST_TEXT)[2]
        self.assertEqual(failures, [])

        # The proof cell rejects any warning, manifest-sanctioned or not.
        failures = self._run(_as_proof_cell, sanctioned, report, NETLIST_TEXT, NETLIST_TEXT)[2]
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("extract reported unexpected warnings", failures[0])

    def test_proof_cell_device_classes_is_checked_only_when_pinned(self):
        entry = _entry()
        del entry["expect"]["device_classes"]
        report = {**REPORT, "device_classes": ["nfet", "pfet", "bjt", "resistor"]}
        failures = self._run(_as_proof_cell, entry, report, NETLIST_TEXT, NETLIST_TEXT)[2]
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
