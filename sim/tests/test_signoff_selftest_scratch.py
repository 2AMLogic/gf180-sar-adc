#!/usr/bin/env python3
"""`--selftest` must release each scratch overlay once its check returns (issue #1121).

`signoff/run_signoff.py --selftest` is the negative control for `--check`: it
copies the inputs `--check` reads into a scratch repo root, once untouched (the
control) and once per tamper case, and runs `--check` on each. The cases run
one after another and each verdict is recorded before the next one starts, so
nothing needs an earlier overlay by the time the next check runs. Until #1121
every overlay lived under one outer temporary directory that was only removed
after the LAST case, so the peak scratch use grew with the case count: 39 live
copies, 517,317,454 file bytes on main at `338fd0dc`, against 13,264,580 for a
single copy -- and on a host whose temporary filesystem could not hold all 39
the self-test ran out of space before reaching its last case.

Nothing counted live overlays, so the growth was invisible to every existing
check: `--selftest` only reports whether each case was caught. This test pins
the lifetime instead of the verdict. `check` is replaced by a spy that, on
every call, lists the directories under a private scratch root that hold a
`signoff/freshness.json` -- one per live overlay. The control must be the
only live overlay while it is checked, each case must be the only one while
it is checked, and the scratch root must be empty once `selftest()` returns.

The real `_overlay` runs against the committed repo, because every tamper
case edits files at their real repo-relative paths; only `check` is replaced,
so the test costs the overlay copies and none of the re-derivation. Stdlib
only; no `klt` and no PDK.

    python3 -m unittest sim/tests/test_signoff_selftest_scratch.py
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402

mod = load_module("run_signoff_selftest_scratch_under_test",
                  REPO / "signoff" / "run_signoff.py")


class SelftestScratchLifetimeTests(unittest.TestCase):
    def live_overlays(self, scratch: str) -> list:
        """Real paths of every directory under `scratch` holding an overlay."""
        found = []
        for dirpath, _dirs, _files in os.walk(scratch):
            if os.path.exists(os.path.join(dirpath, "signoff", "freshness.json")):
                found.append(os.path.realpath(dirpath))
        return sorted(found)

    def test_only_the_overlay_being_checked_is_alive(self):
        scratch = tempfile.TemporaryDirectory(prefix="selftest-scratch-probe-")
        self.addCleanup(scratch.cleanup)
        seen = []

        def spy_check(root, verbose=True):
            seen.append((os.path.realpath(root), self.live_overlays(scratch.name)))
            # The first call is the untampered control; every later one is a
            # tamper case, which `selftest()` requires `check` to flag.
            return [] if len(seen) == 1 else ["tampered"]

        with mock.patch.object(tempfile, "tempdir", scratch.name), \
                mock.patch.object(mod, "check", spy_check), \
                contextlib.redirect_stdout(io.StringIO()):
            rc = mod.selftest(str(REPO))

        self.assertEqual(rc, mod.EXIT_OK)
        self.assertGreater(len(seen), 2, "the control and every case must be checked")
        alive_at_peak = max(len(alive) for _, alive in seen)
        self.assertEqual(
            alive_at_peak, 1,
            f"{alive_at_peak} scratch overlays were alive at once; each must be "
            "released once its check returns",
        )
        for root, alive in seen:
            self.assertEqual(alive, [root], "the overlay under check must be the only live one")
        self.assertEqual(os.listdir(scratch.name), [],
                         "no scratch directory may outlive selftest()")


if __name__ == "__main__":
    unittest.main()
