"""Issue #968: every `klt extract` caller in `layout/lvs/run_lvs.py` must treat
a failed extract the same way -- a `ToolingError` naming the input GDS.

Why this test exists: `_regen_extract`, `run_extract` and `run_block_extract`
used to each carry their own copy of the `klt extract` invocation, exit check
and JSON decode. They disagreed: on exit 0 with malformed stdout, one raised
`ToolingError` and two let `json.JSONDecodeError` escape as a traceback, and
the nonzero-exit message was not uniformly GDS-naming. The three now share
`_run_extract_json`. Nothing else asserted the agreement, so a fourth
divergent call site -- or one caller reverting to a bare `json.loads` --
would pass CI silently. Regenerating committed block and proof-cell netlists
also requires a valid JSON report.

Nothing here runs `klt`, needs the PDK, or imports `klayout`: `subprocess.run`
inside the loaded module is replaced by a fake. Stdlib only.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
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

mod = load_module("run_lvs_under_test", LAYOUT / "lvs" / "run_lvs.py")

GDS_NAME = "probe_cell_968.gds"
DECK = "deck.lvs"

MANIFEST = {
    "deck": DECK,
    "extract": {"name": "probe_cell_968", "gds": GDS_NAME},
}
BLOCK = {"name": "probe_cell_968", "gds": GDS_NAME}


def _fake_run(returncode: int, stdout: str, stderr: str = ""):
    def fake(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    return fake


def _callers():
    """Consumers that extract into a temporary netlist."""
    return [
        ("_regen_extract", lambda: mod._regen_extract("klt", DECK, GDS_NAME)),
        ("run_extract", lambda: mod.run_extract("klt", MANIFEST)),
        ("run_block_extract", lambda: mod.run_block_extract("klt", DECK, BLOCK)),
    ]


class ExtractFailureAgreementTest(unittest.TestCase):
    def _assert_tooling_error_naming_gds(self, returncode, stdout, stderr=""):
        for label, call in _callers():
            with self.subTest(caller=label):
                with mock.patch.object(
                    mod.subprocess, "run", side_effect=_fake_run(returncode, stdout, stderr)
                ):
                    with self.assertRaises(mod.ToolingError) as ctx:
                        call()
                self.assertIn(os.path.basename(GDS_NAME), str(ctx.exception))

    def test_exit_zero_with_malformed_json_raises_tooling_error_naming_gds(self):
        self._assert_tooling_error_naming_gds(0, "invalid")

    def test_nonzero_exit_raises_tooling_error_naming_gds(self):
        self._assert_tooling_error_naming_gds(2, "", "boom")

    def test_nonzero_exit_message_carries_exit_code_and_stderr(self):
        for label, call in _callers():
            with self.subTest(caller=label):
                with mock.patch.object(
                    mod.subprocess, "run", side_effect=_fake_run(3, "", "klt exploded")
                ):
                    with self.assertRaises(mod.ToolingError) as ctx:
                        call()
                self.assertIn("exit 3", str(ctx.exception))
                self.assertIn("klt exploded", str(ctx.exception))

    def test_regenerate_validates_json_for_block_and_proof_cell_netlists(self):
        proof = {"generator": "proof.py", "gds": "proof.gds", "netlist": "proof.spice"}
        block = {"generator": "block.py", "gds": "block.gds", "netlist": "block.spice"}
        for blocks, cell in (([block], block), ([], proof)):
            manifest = {"deck": DECK, "extract": proof, "block_extractions": blocks}
            gds = os.path.join(mod.CELLS_DIR, cell["gds"])
            netlist = os.path.join(mod.CELLS_DIR, cell["netlist"])
            with (
                self.subTest(cell=cell["gds"]),
                mock.patch.object(
                    mod.subprocess, "run", side_effect=_fake_run(0, "invalid")
                ) as launch,
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(mod.ToolingError) as ctx:
                    mod.regenerate(manifest, "klt", "python")
                self.assertIn(
                    f"klt extract emitted non-JSON for {gds}", str(ctx.exception)
                )
                self.assertEqual(
                    launch.call_args.args[0],
                    [
                        "klt",
                        "extract",
                        gds,
                        "--deck",
                        DECK,
                        "-o",
                        netlist,
                        "--format",
                        "json",
                    ],
                )


if __name__ == "__main__":
    unittest.main()
