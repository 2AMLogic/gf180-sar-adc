#!/usr/bin/env python3
"""The committed SAR-sequencer gate-level netlists must match a fresh
`klt synthesize` run of `design/sar-logic/rtl/sar_ctrl.v` (issue #272,
DR-0023 follow-on (a)).

    python3 -m unittest discover -s sim/tests -v

This is the same "generator is the source of truth, diff a fresh run against
the committed artifact" discipline `test_sar_logic_netlist.py` already
enforces for the rung-1 ideal-XSPICE model, applied to the rung-3 gate-level
netlist `design/sar-logic/flow/synth_sar_ctrl.py` produces.

## Why this test SKIPS on the headless CI path, unlike its rung-1 sibling

Unlike `gen_sar_logic.py` (stdlib Python, no external tool), regenerating the
gate netlist needs `klt synthesize` (Yosys + bundled ABC) resolving a real
gf180mcu standard-cell liberty file -- i.e. `klt` on `$PATH` *and* an
installed PDK. `.github/workflows/ci.yml`'s own header is explicit that the
default PR path installs neither (`klt` has no PyPI release yet, same
constraint that already excludes `layout/drc/run_drc.py` and
`layout/lvs/run_lvs.py` from execution there), so this test's `setUpClass`
skips cleanly (not a failure) when either tool or the PDK is unavailable,
rather than either hanging the headless run or producing a false failure
that carries no signal about whether the netlist actually drifted.

Where it DOES run: any environment with `klt`, `yosys`, and the gf180mcu PDK
on `$PATH` / resolvable (a contributor's machine per
`docs/environment-setup.md`, or a future CI job that installs `klt` --
tracked by the same follow-on issue that owns the gate-level corner-grid
replay `design/sar-logic/rtl/README.md`'s "Verification performed" section
points at). `sim/selftest.sh`'s stage 1 (this discovery command) already runs
in both places, so no new wiring is needed once `klt` becomes CI-installable.

## Why re-running the driver script IS the check

`design/sar-logic/flow/synth_sar_ctrl.py` always writes its netlist to the
same committed path (`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.<lib>.
synth.v`) on every invocation -- there is no separate "scratch" output mode.
So the anti-drift check is exactly: snapshot the committed file, re-run the
driver with `--no-record` (so a passing run does not mint a spurious
timestamped evidence record), and diff. A real drift (RTL edited without
re-running the flow) shows up as a changed file; a clean run reproduces the
committed bytes exactly, because `klt synthesize`'s Yosys/ABC recipe and the
PDK's liberty file are both pinned inputs (see the committed records under
`design/sar-logic/flow/sar_ctrl/records/` for the exact tool/PDK versions
this was last generated against).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FLOW_SCRIPT = REPO / "design" / "sar-logic" / "flow" / "synth_sar_ctrl.py"
NETLIST_DIR = REPO / "design" / "sar-logic" / "flow" / "sar_ctrl" / "netlist"
NETLISTS = {
    "mcu7t5v0": NETLIST_DIR / "sar_ctrl.mcu7t5v0.synth.v",
    "mcu9t5v0": NETLIST_DIR / "sar_ctrl.mcu9t5v0.synth.v",
}


def _tool_available(name: str) -> bool:
    return shutil.which(name) is not None


class GateNetlistDriftTests(unittest.TestCase):
    """PDK/`klt`/`yosys`-dependent -- see module docstring for why this
    SKIPS (not fails) when the toolchain is unavailable."""

    @classmethod
    def setUpClass(cls):
        for tool in ("klt", "yosys"):
            if not _tool_available(tool):
                raise unittest.SkipTest(
                    f"{tool!r} not found on $PATH -- see "
                    "design/sar-logic/flow/synth_sar_ctrl.py's module docstring "
                    "and docs/environment-setup.md"
                )
        from sim.harness.pdk import PdkNotFound, find_pdk  # noqa: PLC0415

        try:
            find_pdk()
        except PdkNotFound as exc:
            raise unittest.SkipTest(str(exc)) from exc

        for lib, path in NETLISTS.items():
            if not path.is_file():
                raise AssertionError(f"committed netlist missing for {lib}: {path}")

    def test_committed_netlists_match_a_fresh_synthesis(self):
        before = {lib: path.read_text() for lib, path in NETLISTS.items()}
        result = subprocess.run(
            [sys.executable, str(FLOW_SCRIPT), "--no-record"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"synth_sar_ctrl.py exited {result.returncode}:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        for lib, path in NETLISTS.items():
            with self.subTest(library=lib):
                self.assertEqual(
                    path.read_text(),
                    before[lib],
                    f"{path} is stale relative to design/sar-logic/rtl/sar_ctrl.v -- "
                    f"run: python3 {FLOW_SCRIPT.relative_to(REPO)}",
                )


if __name__ == "__main__":
    unittest.main()
