"""Issue #821: the control-cell generators must still reproduce their
committed GDS, and `klt_env.control_cells` must select exactly the cells the
manifests make that claim about.

Why this test exists: `layout/drc/cells/cells.json`,
`layout/lvs/cells/cells.json` and `layout/README.md` all assert the three
control cells are byte-reproducible, and nothing asserted it back -- every
other check reads the *committed* bytes, so a generator that drifted would
leave them all green. The new `--verify-generators` mode closes that gap
via `klt_env.control_cells()` (the selector) and
`klt_env.verify_generators()` (the regenerate-and-compare).

Nothing here runs `klt`, needs the PDK, or imports `klayout`: the selector
is pure manifest filtering, and the comparison is exercised through a fake
generator script (run with this interpreter) that reproduces or corrupts a
payload file. Stdlib only.
"""

from __future__ import annotations

import os
import shutil
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

# klt_env does `import toolchain_pin` at module level; both live in layout/.
if str(LAYOUT) not in sys.path:
    sys.path.insert(0, str(LAYOUT))

mod = load_module("klt_env_under_test", LAYOUT / "klt_env.py")


# --------------------------------------------------------------------------- #
# manifest fixtures -- the two real manifest shapes, minimally reproduced
# --------------------------------------------------------------------------- #

DRC_FIXTURE = {
    "cells": [
        {
            "name": "sw_unit",
            "generator": "gen_sw_unit.py",
            "gds": "sw_unit.gds",
        },
        {
            "name": "uncovered_layer_probe",
            "generator": "gen_uncovered_layer_probe.py",
            "gds": "uncovered_layer_probe.gds",
        },
        {
            "name": "adc_drv",
            "generator": "../../adc-top/cells/gen_adc_cells.py",
            "gds": "../../adc-top/cells/adc_drv.gds",
        },
        {
            "name": "adc_top",
            "generator": "../../adc-top/gen_adc_top.py",
            "gds": "../../adc-top/adc_top.gds",
        },
    ]
}

LVS_FIXTURE = {
    "extract": {
        "name": "lvs_unit",
        "generator": "gen_lvs_unit.py",
        "gds": "lvs_unit.gds",
    },
    "block_extractions": [
        {
            "name": "adc_cdac_cell",
            "generator": "../../adc-top/cells/gen_adc_cells.py",
            "gds": "../../adc-top/cells/adc_cdac_cell.gds",
        },
        {
            "name": "comparator",
            "generator": "../../adc-top/gen_comparator.py",
            "gds": "../../adc-top/comparator.gds",
        },
        {
            "name": "adc_block",
            "generator": "../../adc-top/gen_adc_top.py",
            "gds": "../../adc-top/adc_block.gds",
        },
    ],
}


class ControlCellsSelector(unittest.TestCase):
    """`control_cells` = manifest entries whose generator has no `..` path
    component -- the selector the runners must share rather than each
    hardcoding the generator->GDS mapping."""

    def test_drc_manifest_yields_exactly_the_two_control_cells(self):
        cells = mod.control_cells(DRC_FIXTURE["cells"])
        self.assertEqual(
            cells,
            [
                ("sw_unit", "gen_sw_unit.py", "sw_unit.gds"),
                (
                    "uncovered_layer_probe",
                    "gen_uncovered_layer_probe.py",
                    "uncovered_layer_probe.gds",
                ),
            ],
        )

    def test_lvs_manifest_yields_exactly_the_extract_cell(self):
        # run_lvs.py feeds control_cells() the extract dict *plus*
        # block_extractions; the no-`..` rule must still drop all nine
        # adc-top shapes (two here stand in for the nine).
        cells = mod.control_cells(
            [LVS_FIXTURE["extract"], *LVS_FIXTURE["block_extractions"]]
        )
        self.assertEqual(cells, [("lvs_unit", "gen_lvs_unit.py", "lvs_unit.gds")])

    def test_selector_reads_the_mapping_from_the_manifest_not_code(self):
        # The contract behind the selector: a *new* local control cell in a
        # manifest is picked up with no code change, and an entry without a
        # generator (e.g. a hand-committed-only artifact) is skipped.
        grown = {
            "cells": DRC_FIXTURE["cells"]
            + [
                {"name": "future_cell", "generator": "gen_future.py",
                 "gds": "future_cell.gds"},
                {"name": "no_generator", "gds": "hand_committed.gds"},
            ]
        }
        cells = mod.control_cells(grown["cells"])
        self.assertIn(("future_cell", "gen_future.py", "future_cell.gds"), cells)
        self.assertEqual(len(cells), 3)


# --------------------------------------------------------------------------- #
# verify_generators, through a fake generator driven by env vars
# --------------------------------------------------------------------------- #

#: A stand-in control generator: honours the `-o` contract of
#: `klt_env.write_cell_gds_main`, copies REPRO_TEST_PAYLOAD to it, records
#: the output directory (so the test can assert the temp dir was removed),
#: and fails before writing when REPRO_TEST_FAIL is set -- which is how a
#: missing `klayout` package looks to the real generators.
FAKE_GENERATOR = """\
import os
import sys

out = sys.argv[sys.argv.index("-o") + 1]
with open(os.environ["REPRO_TEST_PAYLOAD"], "rb") as fh:
    payload = fh.read()
if os.environ.get("REPRO_TEST_FAIL"):
    sys.stderr.write(
        "ModuleNotFoundError: No module named "
        + repr(os.environ["REPRO_TEST_FAIL"]) + "\\n"
    )
    raise SystemExit(1)
with open(out, "wb") as fh:
    fh.write(payload)
with open(os.environ["REPRO_TEST_LOG"], "a") as fh:
    fh.write(os.path.dirname(os.path.abspath(out)) + "\\n")
print("wrote " + out)
"""

PAYLOAD = b"fake-but-deterministic GDSII bytes (timestamps suppressed)\x00\x01\x02"


class VerifyGenerators(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="repro-test-")
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.cells_dir = root / "cells"
        self.cells_dir.mkdir()
        (self.cells_dir / "gen_ok.py").write_text(FAKE_GENERATOR, encoding="utf-8")
        self.payload = root / "payload.bin"
        self.payload.write_bytes(PAYLOAD)
        self.committed = self.cells_dir / "sw_unit.gds"
        self.committed.write_bytes(PAYLOAD)
        self.log = root / "gen-runs.log"
        self.env = {
            "REPRO_TEST_PAYLOAD": str(self.payload),
            "REPRO_TEST_LOG": str(self.log),
        }

    def _recorded_dirs(self):
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text(encoding="utf-8").splitlines() if line]

    def _run(self, cells, env_extra=None):
        env = dict(self.env)
        env.update(env_extra or {})
        with mock.patch.dict(os.environ, env):
            mod.verify_generators(cells, str(self.cells_dir), sys.executable)

    def test_reproducing_generator_passes_and_writes_nothing_in_cells_dir(self):
        before = sorted(p.name for p in self.cells_dir.iterdir())
        self._run(
            [
                ("sw_unit", "gen_ok.py", "sw_unit.gds"),
            ]
        )
        self.assertEqual(sorted(p.name for p in self.cells_dir.iterdir()), before)
        # the temp dir the generator wrote into is gone (success path)
        self.assertTrue(self._recorded_dirs())
        for d in self._recorded_dirs():
            self.assertFalse(os.path.exists(d), d)

    def test_drifted_generator_raises_naming_cell_and_both_paths(self):
        self.payload.write_bytes(PAYLOAD + b"\xffdrifted")
        with self.assertRaises(mod.ToolingError) as ctx:
            self._run([("sw_unit", "gen_ok.py", "sw_unit.gds")])
        message = str(ctx.exception)
        self.assertIn("sw_unit", message)
        self.assertIn("gen_ok.py", message)
        self.assertIn(str(self.committed), message)  # committed path
        self.assertIn("klt-verify-gen-", message)  # regenerated path
        self.assertIn("sha256", message)

    def test_mismatch_temp_dir_removed_even_on_failure(self):
        self.payload.write_bytes(PAYLOAD + b"\xffdrifted")
        with self.assertRaises(mod.ToolingError):
            self._run([("sw_unit", "gen_ok.py", "sw_unit.gds")])
        for d in self._recorded_dirs():
            self.assertFalse(os.path.exists(d), d)

    def test_failing_generator_is_a_tooling_error_not_a_mismatch(self):
        # "klayout package absent" reaches verify_generators as a generator
        # that exits non-zero; it must be reported as a generator failure,
        # not as a reproducibility mismatch.
        with self.assertRaises(mod.ToolingError) as ctx:
            self._run(
                [("sw_unit", "gen_ok.py", "sw_unit.gds")],
                env_extra={"REPRO_TEST_FAIL": "klayout.db"},
            )
        message = str(ctx.exception)
        self.assertIn("failed", message)
        self.assertIn("klayout.db", message)
        self.assertNotIn("byte-for-byte", message)

    def test_missing_committed_gds_is_a_tooling_error(self):
        self.committed.unlink()
        with self.assertRaises(mod.ToolingError) as ctx:
            self._run([("sw_unit", "gen_ok.py", "sw_unit.gds")])
        self.assertIn("sw_unit.gds", str(ctx.exception))
        self.assertIn("--regen", str(ctx.exception))

    def test_missing_generator_script_is_a_tooling_error(self):
        with self.assertRaises(mod.ToolingError) as ctx:
            self._run([("sw_unit", "gen_absent.py", "sw_unit.gds")])
        self.assertIn("gen_absent.py", str(ctx.exception))


class FindKlayoutPythonAbsent(unittest.TestCase):
    def test_no_klayout_anywhere_is_a_clear_tooling_error(self):
        # The environment the unit suite runs in (no pip `klayout` in this
        # interpreter, no `klt` on PATH) must surface as ToolingError from
        # find_klayout_python(), not as a traceback later. Skipped where a
        # klayout *is* reachable -- those hosts exercise the happy path.
        probe = subprocess.run(
            [sys.executable, "-c", "import klayout.db"],
            capture_output=True,
        )
        if probe.returncode == 0 or shutil.which("klt") is not None:
            self.skipTest("a klayout-capable interpreter is present")
        with self.assertRaises(mod.ToolingError) as ctx:
            mod.find_klayout_python()
        self.assertIn("klayout", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
