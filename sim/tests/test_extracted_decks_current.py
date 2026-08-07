#!/usr/bin/env python3
"""Every post-layout `gen_extracted_*_tb.py` generator and its committed
deck must agree -- issue #123, extended to the last two generators by #131.

    python3 -m unittest discover -s sim/tests -v

`layout/adc-top/parasitics/gen_extracted_{inl_dnl,enob_fft,power,
switch_ron,dr0014_sampling,timing_budget}_tb.py` each implement a `--check`
mode (mirroring
`design/adc-top/gen_adc_top.py --check`, guarded by
`test_adc_top_netlist.py`), but nothing wired those checks into CI: three of
the first four decks drifted a full extraction generation (158 -> 2938
parasitic R elements, i.e. the pre-`875eac3`-pin star-split topology vs the
`klayout-tools#593` in-path topology that pin bump landed) without anyone
noticing until issue #123 was filed, because no test or workflow ever called
`--check`.

Issue #123's fix covered four of the six generators in that directory;
`dr0014_sampling` and `timing_budget` were left uncovered, which is exactly
the "silent gap" the `GENERATORS` comment below warns about -- the next
`layout/toolchain.json` pin bump could have drifted them a full extraction
generation in silence. Issue #131 closes that: all six are guarded here.

Like `test_adc_top_netlist.py`, this needs neither ngspice nor the PDK --
each generator only re-derives its output text from
`layout/adc-top/parasitics/reports/` (committed) and diffs it against the
committed `sim/*/testbench/*.spice` file, so it runs on the PDK-free CI path
on every pull request (`sim/selftest.sh` stage 1 /
`python3 -m unittest discover -s sim/tests -t sim/tests`).
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PARASITICS_DIR = REPO / "layout" / "adc-top" / "parasitics"

#: (generator script, committed output it checks) -- kept explicit rather than
#: globbed, so a generator added to the directory without a matching entry
#: here is a silent gap, not a silently-covered one.
GENERATORS = {
    "inl_dnl": (
        "gen_extracted_inl_dnl_tb.py",
        "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice",
    ),
    "enob_fft": (
        "gen_extracted_enob_fft_tb.py",
        "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice",
    ),
    "power": (
        "gen_extracted_power_tb.py",
        "sim/adc-power/testbench/tb_adc_power_extracted.spice",
    ),
    "switch_ron": (
        "gen_extracted_switch_ron_tb.py",
        "sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice",
    ),
    # Writes into a SIBLING testbench directory (`testbench-extracted/`), not
    # `testbench/`, because its manifest is explicitly scoped to Groups A+C --
    # see gen_extracted_dr0014_sampling_tb.py's "Why a second testbench
    # directory" section. Same experiment directory either way.
    "dr0014_sampling": (
        "gen_extracted_dr0014_sampling_tb.py",
        "sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice",
    ),
    "timing_budget": (
        "gen_extracted_timing_budget_tb.py",
        "sim/timing-budget-closure/testbench/tb_timing_budget_closure_extracted.spice",
    ),
}


class ExtractedDecksCurrentTests(unittest.TestCase):
    """Anti-drift check: each generator's `--check` must exit 0 against the
    committed deck it targets. Regenerate (no flags) and diff, not just
    re-parse -- same discipline as `test_adc_top_netlist.py`."""

    def test_all_generator_scripts_exist(self):
        for name, (script, _out) in sorted(GENERATORS.items()):
            with self.subTest(target=name):
                self.assertTrue(
                    (PARASITICS_DIR / script).is_file(), f"missing {script}"
                )

    def test_committed_decks_match_their_generator(self):
        for name, (script, out_rel) in sorted(GENERATORS.items()):
            with self.subTest(target=name):
                out_path = REPO / out_rel
                self.assertTrue(out_path.is_file(), f"{out_rel} is missing")
                result = subprocess.run(
                    [sys.executable, str(PARASITICS_DIR / script), "--check"],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{out_rel} is stale -- run: python3 "
                    f"{(PARASITICS_DIR / script).relative_to(REPO)}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
