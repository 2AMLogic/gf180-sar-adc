#!/usr/bin/env python3
"""Issue #1087: `--regen` launches each distinct generator once per run.

Why this test exists: `run_drc.py --regen` and `run_lvs.py --regen` invoked a
Python generator for every manifest entry. The `adc-top` generators are
multi-output and take no cell name -- one launch of `gen_adc_cells.py` writes
all five leaf cells, one launch of `gen_adc_top.py` writes both `adc_top` and
`adc_block` -- so on the committed manifests DRC launched 10 generator
processes for 5 distinct scripts and LVS launched 9 for 4, rebuilding the same
bytes four and five times over. Nothing counted subprocesses, so the
redundancy was invisible; this pins the counts.

The contract under test, per runner:

  * each distinct generator script is launched once per `regenerate()` call,
    at its first occurrence in the order the runner walks the manifest;
  * the bookkeeping lives inside that one call -- a second `regenerate()`
    rebuilds everything rather than skipping what an earlier run launched;
  * a failed generator still raises `ToolingError`, which stops the run
    before any later entry is visited;
  * what is NOT deduplicated: every DRC cell still reaches its own `klt drc`
    run and every LVS netlist its own `klt extract`.

Nothing here runs `klt`, needs the PDK, or imports `klayout`: `subprocess.run`
is replaced by a recorder that writes the files a real generator/extractor
would, under a temporary `cells/` directory, so the runners' own existence
and sha256 checks run against them. Stdlib only.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LAYOUT = REPO / "layout"
sys.path.insert(0, str(HERE))
# run_drc/run_lvs do `from klt_env import ...` / `import toolchain_pin`; both live in layout/.
if str(LAYOUT) not in sys.path:
    sys.path.insert(0, str(LAYOUT))

from _loadmod import load_module  # noqa: E402

drc = load_module("run_drc_regen_under_test", LAYOUT / "drc" / "run_drc.py")
lvs = load_module("run_lvs_regen_under_test", LAYOUT / "lvs" / "run_lvs.py")

PYTHON = "/nonexistent/python-with-klayout"
KLT = "/nonexistent/klt"
DECK = "gf180mcu"

# Issue #1087's counts for the committed manifests, in launch order: the
# first occurrence of each generator as its runner walks the manifest.
DRC_GENERATORS = [
    "gen_sw_unit.py",
    "gen_uncovered_layer_probe.py",
    "gen_adc_cells.py",
    "gen_comparator.py",
    "gen_adc_top.py",
]
LVS_GENERATORS = [
    "gen_adc_cells.py",
    "gen_comparator.py",
    "gen_adc_top.py",
    "gen_lvs_unit.py",
]
LVS_EXTRACTIONS = 9


def _gds(name: str) -> str:
    return f"GDS bytes of {name}\n"


def _netlist(name: str) -> str:
    return f"* extracted netlist of {name}\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _drc_cell(name: str, generator: str) -> dict:
    return {
        "name": name,
        "generator": generator,
        "gds": f"{name}.gds",
        "sha256": _sha256(_gds(name)),
        "role": "fixture",
        "expect_status": "clean",
        "expect": {},
    }


def _lvs_cell(name: str, generator: str) -> dict:
    return {
        "name": name,
        "generator": generator,
        "gds": f"{name}.gds",
        "sha256": _sha256(_gds(name)),
        "netlist": f"{name}.spice",
        "netlist_sha256": _sha256(_netlist(name)),
    }


def _lvs_manifest(blocks: list[dict], unit_generator: str = "gen_unit.py") -> dict:
    return {
        "deck": DECK,
        "extract": _lvs_cell("unit", unit_generator),
        "block_extractions": blocks,
        "lvs_cases": [],
    }


class _Recorder:
    """A `subprocess.run` that launches nothing and logs every argv.

    A generator launch writes the GDS of every entry naming that script --
    the multi-output shape the real `adc-top` generators have -- and a
    `klt extract` launch writes its `-o` netlist, so a runner's own
    existence and sha256 checks see what a real run would leave on disk.
    `failing` maps a generator path to the nonzero exit it returns instead.
    """

    def __init__(self, entries, cells_dir: str, failing: dict | None = None):
        self._root = os.path.realpath(cells_dir)
        self._gds_of: dict[str, list[tuple[str, str]]] = {}
        for entry in entries:
            script = os.path.join(cells_dir, entry["generator"])
            self._gds_of.setdefault(script, []).append(
                (os.path.join(cells_dir, entry["gds"]), _gds(entry["name"]))
            )
        self._netlists = {
            os.path.join(cells_dir, entry["netlist"]): _netlist(entry["name"])
            for entry in entries
            if "netlist" in entry
        }
        self._failing = failing or {}
        self.calls: list[list[str]] = []

    def _write(self, path: str, text: str) -> None:
        # Manifest entries that reach outside cells/ (the adc-top ones)
        # resolve above the temporary root; nothing reads those here.
        if os.path.commonpath([os.path.realpath(path), self._root]) != self._root:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def __call__(self, cmd, *args, **kwargs):
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        if argv[0] == PYTHON:
            if argv[1] in self._failing:
                return subprocess.CompletedProcess(
                    argv, self._failing[argv[1]], "", "generator exploded"
                )
            for path, text in self._gds_of[argv[1]]:
                self._write(path, text)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == [KLT, "extract"]:
            netlist = argv[argv.index("-o") + 1]
            self._write(netlist, self._netlists[netlist])
            return subprocess.CompletedProcess(argv, 0, "{}", "")
        raise AssertionError(f"unexpected subprocess: {argv}")

    @property
    def generator_launches(self) -> list[str]:
        return [argv[1] for argv in self.calls if argv[0] == PYTHON]

    @property
    def extractions(self) -> list[tuple[str, str]]:
        """`(gds, netlist)` per `klt extract` launch."""
        return [
            (argv[2], argv[argv.index("-o") + 1])
            for argv in self.calls
            if argv[:2] == [KLT, "extract"]
        ]


class _RegenTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cells_dir = tmp.name

    def path(self, name: str) -> str:
        return os.path.join(self.cells_dir, name)

    def first_occurrences(self, walked: list[dict]) -> list[str]:
        """Script paths of `walked`, each once, in first-occurrence order."""
        return list(dict.fromkeys(self.path(e["generator"]) for e in walked))

    def regen(self, mod, manifest: dict, recorder: _Recorder, *args) -> None:
        with (
            redirect_stdout(io.StringIO()),
            mock.patch.object(mod, "CELLS_DIR", self.cells_dir),
            mock.patch.object(subprocess, "run", recorder),
        ):
            mod.regenerate(manifest, *args)

    def main_regen_check(self, mod, manifest: dict, recorder: _Recorder, stubs: dict):
        """Drive `mod.main()` as `--regen --check` on a fake toolchain."""
        with contextlib.ExitStack() as stack:
            for target, name, value in (
                (mod, "CELLS_DIR", self.cells_dir),
                (mod, "load_manifest", lambda path: manifest),
                (mod, "find_klt", lambda: KLT),
                (mod, "klt_version", lambda klt: "test"),
                (mod, "check_klt_capabilities", lambda klt, pin: None),
                (mod, "find_klayout_python", lambda: PYTHON),
                (
                    mod.toolchain_pin,
                    "load_toolchain_pin",
                    lambda: {"klt_required_commands": []},
                ),
                (subprocess, "run", recorder),
                (sys, "argv", ["runner.py", "--regen", "--check"]),
                *((mod, name, value) for name, value in stubs.items()),
            ):
                stack.enter_context(mock.patch.object(target, name, value))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return mod.main()


class DrcRegenTests(_RegenTestCase):
    def _run_check(self, manifest: dict, failing: dict | None = None):
        recorder = _Recorder(manifest["cells"], self.cells_dir, failing)
        verified: list[str] = []

        def run_cell(klt, gds_path, deck):
            verified.append(os.path.basename(gds_path))
            report = {
                "status": "clean", "rule_counts": {}, "violation_count": 0, "dbu_um": 0.001,
            }
            return report, "", 0

        code = self.main_regen_check(drc, manifest, recorder, {"run_cell": run_cell})
        return code, recorder, verified

    def test_cells_sharing_a_generator_reach_verification_after_one_launch(self):
        manifest = {
            "deck": DECK,
            "cells": [_drc_cell("cell_a", "gen_pair.py"), _drc_cell("cell_b", "gen_pair.py")],
        }
        code, recorder, verified = self._run_check(manifest)
        self.assertEqual(recorder.generator_launches, [self.path("gen_pair.py")])
        self.assertEqual(verified, ["cell_a.gds", "cell_b.gds"])
        self.assertEqual(code, drc.EXIT_OK)

    def test_committed_manifest_launches_its_five_generators_once_each(self):
        manifest = drc.load_manifest(drc.MANIFEST)
        recorder = _Recorder(manifest["cells"], self.cells_dir)
        self.regen(drc, manifest, recorder, PYTHON)
        self.assertEqual(
            [os.path.basename(p) for p in recorder.generator_launches],
            DRC_GENERATORS,
        )

    def test_a_second_regeneration_rebuilds_everything(self):
        manifest = drc.load_manifest(drc.MANIFEST)
        recorder = _Recorder(manifest["cells"], self.cells_dir)
        self.regen(drc, manifest, recorder, PYTHON)
        self.regen(drc, manifest, recorder, PYTHON)
        self.assertEqual(
            recorder.generator_launches,
            self.first_occurrences(manifest["cells"]) * 2,
        )

    def test_a_failed_generator_stops_the_run(self):
        cells = [
            _drc_cell("cell_a", "gen_pair.py"),
            _drc_cell("cell_b", "gen_pair.py"),
            _drc_cell("cell_c", "gen_other.py"),
        ]
        manifest = {"deck": DECK, "cells": cells}
        code, recorder, verified = self._run_check(
            manifest, {self.path("gen_pair.py"): 1}
        )
        self.assertEqual(code, drc.EXIT_TOOLING)
        self.assertEqual(recorder.generator_launches, [self.path("gen_pair.py")])
        self.assertEqual(verified, [])


class LvsRegenTests(_RegenTestCase):
    def _entries(self, manifest: dict) -> list[dict]:
        return [manifest["extract"], *manifest["block_extractions"]]

    def _run_check(self, manifest: dict, failing: dict | None = None):
        recorder = _Recorder(self._entries(manifest), self.cells_dir, failing)
        extracted: list[str] = []

        def run_block_extract(klt, deck, block):
            extracted.append(block["name"])
            return {}, "", []

        code = self.main_regen_check(
            lvs,
            manifest,
            recorder,
            {
                "run_extract": lambda klt, manifest: ({}, "", []),
                "run_block_extract": run_block_extract,
            },
        )
        return code, recorder, extracted

    def test_blocks_sharing_a_generator_are_each_extracted_after_one_launch(self):
        manifest = _lvs_manifest(
            [_lvs_cell("blk_a", "gen_pair.py"), _lvs_cell("blk_b", "gen_pair.py")]
        )
        code, recorder, extracted = self._run_check(manifest)
        self.assertEqual(
            recorder.generator_launches,
            [self.path("gen_pair.py"), self.path("gen_unit.py")],
        )
        self.assertEqual(
            recorder.extractions,
            [
                (self.path("blk_a.gds"), self.path("blk_a.spice")),
                (self.path("blk_b.gds"), self.path("blk_b.spice")),
                (self.path("unit.gds"), self.path("unit.spice")),
            ],
        )
        self.assertEqual(extracted, ["blk_a", "blk_b"])
        self.assertEqual(code, lvs.EXIT_OK)

    def test_a_generator_shared_by_a_block_and_the_proof_cell_is_launched_once(self):
        manifest = _lvs_manifest(
            [_lvs_cell("blk_a", "gen_shared.py")], unit_generator="gen_shared.py"
        )
        recorder = _Recorder(self._entries(manifest), self.cells_dir)
        self.regen(lvs, manifest, recorder, KLT, PYTHON)
        self.assertEqual(recorder.generator_launches, [self.path("gen_shared.py")])
        self.assertEqual(
            recorder.extractions,
            [
                (self.path("blk_a.gds"), self.path("blk_a.spice")),
                (self.path("unit.gds"), self.path("unit.spice")),
            ],
        )

    def test_committed_manifest_launches_four_generators_and_extracts_each_netlist(self):
        manifest = lvs.load_manifest(lvs.MANIFEST)
        walked = [*manifest["block_extractions"], manifest["extract"]]
        recorder = _Recorder(walked, self.cells_dir)
        self.regen(lvs, manifest, recorder, KLT, PYTHON)
        self.assertEqual(
            [os.path.basename(p) for p in recorder.generator_launches],
            LVS_GENERATORS,
        )
        self.assertEqual(len(recorder.extractions), LVS_EXTRACTIONS)
        self.assertEqual(
            recorder.extractions,
            [(self.path(e["gds"]), self.path(e["netlist"])) for e in walked],
        )

    def test_a_second_regeneration_rebuilds_everything(self):
        manifest = lvs.load_manifest(lvs.MANIFEST)
        recorder = _Recorder(self._entries(manifest), self.cells_dir)
        self.regen(lvs, manifest, recorder, KLT, PYTHON)
        self.regen(lvs, manifest, recorder, KLT, PYTHON)
        self.assertEqual(
            recorder.generator_launches,
            self.first_occurrences([*manifest["block_extractions"], manifest["extract"]]) * 2,
        )
        self.assertEqual(len(recorder.extractions), 2 * LVS_EXTRACTIONS)

    def test_a_failed_generator_stops_the_run(self):
        blocks = [
            _lvs_cell("blk_a", "gen_pair.py"),
            _lvs_cell("blk_b", "gen_pair.py"),
            _lvs_cell("blk_c", "gen_other.py"),
        ]
        for failing, launched, extracted in (
            ("gen_pair.py", ["gen_pair.py"], []),
            ("gen_other.py", ["gen_pair.py", "gen_other.py"], ["blk_a", "blk_b"]),
        ):
            with self.subTest(failing=failing):
                manifest = _lvs_manifest(blocks)
                code, recorder, checked = self._run_check(
                    manifest, {self.path(failing): 1}
                )
                self.assertEqual(code, lvs.EXIT_TOOLING)
                self.assertEqual(
                    [os.path.basename(p) for p in recorder.generator_launches],
                    launched,
                )
                self.assertEqual(
                    [os.path.basename(gds) for gds, _ in recorder.extractions],
                    [f"{name}.gds" for name in extracted],
                )
                self.assertEqual(checked, [])


if __name__ == "__main__":
    unittest.main()
