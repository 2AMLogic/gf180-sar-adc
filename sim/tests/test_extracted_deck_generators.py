#!/usr/bin/env python3
"""Every committed **extracted** testbench deck must match the generator that
emits it -- the post-layout analogue of `test_adc_top_netlist.py`'s
`test_committed_files_match_the_generator`.

    python3 -m unittest discover -s sim/tests -t sim/tests -v

## Why this test exists

`design/adc-top/gen_adc_top.py`'s schematic decks have been guarded since #13
by `test_adc_top_netlist.py`, which regenerates them and diffs. The
`layout/adc-top/parasitics/gen_extracted_*_tb.py` family -- which splices a
committed `klt extract --parasitics` netlist into those same manifests -- each
implement the same `--check` contract, but **nothing ran it**. So when the
`layout/toolchain.json` `klt` pin moved to `875eac3` (issue #116, upstream
`klayout-tools#593`) and `run_extract_parasitics.py` committed a new,
star-split *in-path* extraction under `reports/`, three decks silently kept
the superseded pre-in-path extraction (156 lumped R, 0 leg nodes) while
`remediate_extracted._latest_report()` had already begun selecting the new one
(2936 in-path R, 514 leg nodes). Regenerating them would have swapped the DUT
of three headline post-layout claims -- INL/DNL, ENOB/FFT, power -- with no
test going red. That is issue #123.

Byte-identity is the right assertion here for the same reason it is in
`test_adc_top_netlist.py`: the committed deck is machine-generated evidence
input, so any difference at all -- including a `* Source:` provenance comment
naming a different extraction report, which is the *only* thing that moved in
`sim/device-switch-ron/`'s deck -- means the committed artefact no longer
describes what it was built from.

## What it does NOT do

It does not run ngspice, need the gf180mcu PDK, or need `klt`: every generator
reads committed text under `layout/adc-top/parasitics/reports/` and writes
SPICE text. That is deliberate -- it is what lets this guard live on the
PDK-free CI path (`.github/workflows/ci.yml`, "Harness unit tests"), where a
regression is caught on the pull request that causes it rather than on the
next nightly.

It also does not assert that a *stale* deck's numbers are wrong. Being current
with the generator and being re-run against the current DUT are two different
claims; the second one lives in `sim/<slug>/records/`. A green run here means
only "the committed deck is what the generator emits today".
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
PARASITICS = REPO_ROOT / "layout" / "adc-top" / "parasitics"

#: Generators that legitimately have no `--check` mode, with the reason. An
#: entry here is a claim that has to stay true: `test_every_exemption_is_real`
#: fails if the file is gone or if it grew a `--check` after all, so the
#: exemption cannot quietly become a hole.
NO_CHECK_MODE = {
    "gen_extracted_core_tb.py": (
        "emits an on-demand smoke deck to stdout (`--top ADC_TOP|ADC_BLOCK`) "
        "and commits nothing under sim/, so there is no committed artefact to "
        "diff against"
    ),
}

#: The four decks issue #123 is about, pinned by name so a future refactor of
#: the discovery glob below cannot silently stop covering them. Three of these
#: (`inl_dnl`, `enob_fft`, `power`) carried a pre-in-path extraction for the
#: whole of PRs #119..#121; the fourth (`switch_ron`) drifted in its `* Source:`
#: provenance line over the same window.
ISSUE_123_GENERATORS = (
    "gen_extracted_inl_dnl_tb.py",
    "gen_extracted_enob_fft_tb.py",
    "gen_extracted_power_tb.py",
    "gen_extracted_switch_ron_tb.py",
)


def _generators() -> list[Path]:
    return sorted(PARASITICS.glob("gen_extracted_*_tb.py"))


def _run(path: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke a generator the way a human does: from the repo root, so the
    relative paths it prints are the ones a reader can act on."""
    return subprocess.run(  # noqa: S603
        [sys.executable, str(path), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


class GeneratorDiscoveryTests(unittest.TestCase):
    """The glob is the mechanism; these keep it honest."""

    def test_the_glob_finds_generators_at_all(self):
        """A rename that emptied the glob would make every other test in this
        module vacuously pass."""
        self.assertGreaterEqual(len(_generators()), len(ISSUE_123_GENERATORS) + 1)

    def test_issue_123_generators_are_all_discovered(self):
        found = {p.name for p in _generators()}
        for name in ISSUE_123_GENERATORS:
            with self.subTest(generator=name):
                self.assertIn(name, found)

    def test_every_exemption_is_real(self):
        found = {p.name for p in _generators()}
        for name, reason in NO_CHECK_MODE.items():
            with self.subTest(generator=name):
                self.assertIn(
                    name,
                    found,
                    f"{name} is exempted from --check but no longer exists; "
                    "drop the NO_CHECK_MODE entry",
                )
                self.assertTrue(reason.strip(), "exemption needs a reason")
                proc = _run(PARASITICS / name, "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn(
                    "--check",
                    proc.stdout,
                    f"{name} now HAS a --check mode -- remove it from "
                    "NO_CHECK_MODE so it gets guarded",
                )

    def test_every_other_generator_exposes_check(self):
        """A new `gen_extracted_*_tb.py` is guarded the moment it lands, or it
        fails here -- it cannot be added unguarded and unnoticed."""
        for path in _generators():
            if path.name in NO_CHECK_MODE:
                continue
            with self.subTest(generator=path.name):
                proc = _run(path, "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(
                    "--check",
                    proc.stdout,
                    f"{path.name} has no --check mode; add one (see "
                    "gen_extracted_inl_dnl_tb.py) or add it to NO_CHECK_MODE "
                    "with a reason",
                )


class CommittedDeckFreshnessTests(unittest.TestCase):
    """The anti-drift check itself. Regenerate and diff, do not re-parse."""

    def test_every_committed_extracted_deck_matches_its_generator(self):
        for path in _generators():
            if path.name in NO_CHECK_MODE:
                continue
            rel = path.relative_to(REPO_ROOT)
            with self.subTest(generator=path.name):
                proc = _run(path, "--check")
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"{rel} reports a stale committed deck -- run:\n"
                    f"    python3 {rel}\n"
                    "and RE-RUN the affected bench (a regenerated deck with no "
                    "new record in sim/<slug>/records/ is an unsubstantiated "
                    "claim; see CLAUDE.md and issue #123).\n"
                    f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}",
                )

    def test_check_mode_writes_nothing(self):
        """`--check` is safe to run in CI only if it is read-only. Assert the
        committed decks are byte-identical across a --check invocation."""
        decks = sorted(
            p
            for p in (REPO_ROOT / "sim").glob("*/testbench*/*_extracted.spice")
            if p.is_file()
        )
        self.assertTrue(decks, "no committed *_extracted.spice decks found")
        before = {p: p.read_bytes() for p in decks}
        for path in _generators():
            if path.name in NO_CHECK_MODE:
                continue
            _run(path, "--check")
        for p, text in before.items():
            with self.subTest(deck=str(p.relative_to(REPO_ROOT))):
                self.assertEqual(p.read_bytes(), text)


if __name__ == "__main__":
    unittest.main()
