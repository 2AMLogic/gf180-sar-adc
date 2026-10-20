#!/usr/bin/env python3
"""Provenance plumbing shared by the `design/sar-logic/flow/` drivers.

Every driver in this directory -- `synth_sar_ctrl.py` (issue #272),
`pnr_sar_ctrl.py` (#274), `sta_sar_ctrl.py` / `sta_sar_ctrl_postroute.py`
(#275) -- mints append-only evidence records under
`design/sar-logic/flow/sar_ctrl/records/`, and every one of those records
names the commit it was minted from, the `klt` build that produced it, and a
record ID in `sim/README.md`'s ratified `<YYYYMMDD>-<HHMMSS>-<short-sha>`
grammar. This module is the single implementation of that plumbing.

Why it lives here rather than in either driver (issue #352): `_git`,
`_git_status_porcelain`, `_run`, and `klt_version` were **byte-identical**
copies in `synth_sar_ctrl.py` and `pnr_sar_ctrl.py`, and `record_id` differed
only by a docstring line. These helpers decide what a recorded number
*means* -- which commit a record claims, whether the working tree that
produced it was clean, which `klt` stamped it -- so two forks of them would
let one driver's provenance drift from the other's under the same repo state,
silently, on the next edit to either. That is the same argument
`layout/klt_env.py` (issues #194/#253) makes for the `layout/` runners, and
this module deliberately mirrors its shape.

`repo_root` is a parameter on every function rather than a module constant
even though this file sits beside its callers (so it *could* compute
`parents[3]` for itself). Two reasons: each driver already computes its own
`REPO_ROOT` and stays the single source of truth for it, and a parameter
makes these functions exercisable against a throwaway checkout --
`sim/tests/test_flow_env.py` runs `git`/`git_status_porcelain`/`record_id`
against a temp-directory git repo, which a module-level constant pinned to
this working copy would make impossible.

This module is import-only -- it runs no tool at import time and has no side
effects, so `python3 -m compileall design` (this repo's CI) covers it without
`klt` installed.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

# `layout/` is a plain directory, so its shared `klt_env` helper module has to
# be put on the path explicitly (this file is also loaded by path from tests).
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "layout"))

import klt_env  # noqa: E402  (import follows the sys.path setup above)

# --- sar_ctrl design-point constants (issue #569) ---------------------------
# Previously retyped in each driver and kept in sync by hand; one driver
# drifting would silently stamp its evidence records with a different clock
# budget or corner set than the others.

TOP = "sar_ctrl_a"
CELL_LIBRARY = "gf180mcu_fd_sc_mcu7t5v0"
LIB_TAG = "mcu7t5v0"

# DR-0003: 16 MHz external clock (M = 16 at 1 MS/s) -> 62.5 ns bit-cycle period.
CLOCK_PORT = "clk"
CLOCK_PERIOD_NS = 62.5

# DR-0023's own ratified 3.3 V corner set (first 3) + the two remaining 3.3 V
# corners gf180mcu_fd_sc_mcu7t5v0 also ships (last 2).
CORNERS: list[tuple[str, str]] = [
    ("tt_025C_3v30", "typical process, 25 C, 3.30 V (DR-0023's own corner; #272's synthesis corner)"),
    ("ss_125C_3v00", "slow process, 125 C, 3.00 V (worst case for setup; DR-0023-named)"),
    ("ff_n40C_3v60", "fast process, -40 C, 3.60 V (worst case for hold; DR-0023-named)"),
    ("ss_n40C_3v00", "slow process, -40 C, 3.00 V (supplementary -- ships in the library, not named by DR-0023)"),
    ("ff_125C_3v60", "fast process, 125 C, 3.60 V (supplementary -- ships in the library, not named by DR-0023)"),
]

OUT_DIR = Path(__file__).resolve().parent / "sar_ctrl"
REPORTS_DIR = OUT_DIR / "reports"
RECORDS_DIR = OUT_DIR / "records"


def run(repo_root: Path, cmd: list[str]) -> subprocess.CompletedProcess:
    """Run `cmd` from `repo_root`, capturing both streams; never raises on a
    non-zero exit -- every caller here inspects `returncode` itself and
    reports the tool's own stdout/stderr in the failure it raises."""
    return subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)


def git(repo_root: Path, *args: str) -> str:
    """`git <args...>` from `repo_root`; stripped stdout, or `""` on failure.

    One implementation, shared with the `layout/` runners: `klt_env.git`.
    """
    return klt_env.git(repo_root, *args)


def git_status_porcelain(repo_root: Path) -> str:
    """`git status --porcelain` from `repo_root`, trailing newline stripped.

    Returns `""` on any failure, same as :func:`git`. Kept separate from
    `git()` because it must NOT strip leading whitespace: porcelain status
    codes are column-significant (` M path` vs `M  path`), and each driver's
    own `working_tree_dirty()` slices `line[3:]` to get the path.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.rstrip("\n") if result.returncode == 0 else ""


def klt_version(repo_root: Path) -> str:
    """`klt --version` as the evidence records stamp it (`klt_env.klt_version`)."""
    return klt_env.klt_version("klt")


def record_id(repo_root: Path, when: _dt.datetime) -> str:
    """``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``, matching sim/README.md's grammar.

    `when` is passed in, not read from the clock here, so that one driver run
    naming several artifacts (`synth_sar_ctrl.py` synthesizes two libraries
    under a single record ID) stamps them all with the same instant.
    """
    return klt_env.record_id(repo_root, when)


def pdk_env(pdk) -> dict:
    """The process environment with `PDK_ROOT`/`PDK` pointed at `pdk`.

    The openroad Docker wrapper behind `klt place-and-route`/`klt sta`/
    `klt extract` mounts whichever install these name, regardless of the
    caller's own shell.
    """
    env = dict(os.environ)
    env["PDK_ROOT"] = str(pdk.path.parent)
    env["PDK"] = pdk.variant
    return env


def run_klt_json(repo_root: Path, pdk, argv: list[str], *, error_cls: type[Exception], label: str) -> dict:
    """`klt <argv...> --pdk <variant> --format json`; the parsed response.

    Raises `error_cls` (message prefixed with `label`, e.g. ``klt sta (corner
    tt_025C_3v30)``) when stdout is not JSON, the response carries an
    ``error`` envelope, or the exit code is non-zero.
    """
    result = subprocess.run(
        ["klt", *argv, "--pdk", pdk.variant, "--format", "json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=pdk_env(pdk),
        check=False,
    )
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise error_cls(
            f"{label} did not print JSON "
            f"(exit {result.returncode}): {exc}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        ) from exc
    if "error" in response:
        raise error_cls(f"{label} failed: {response['error'].get('message')}")
    if result.returncode != 0:
        raise error_cls(
            f"{label} exited "
            f"{result.returncode} with no error envelope:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return response


class StaError(RuntimeError):
    """A `klt place-and-route` / `klt sta` corner run that cannot be recorded."""


class CornerResult:
    """One corner's STA response, with the fields both STA drivers record.

    Each driver subclasses this to add what only its stage reports
    (pre-route: `wirelength_um`; post-route: hold slack/TNS).
    """

    def __init__(self, corner: str, desc: str, response: dict):
        self.corner = corner
        self.desc = desc
        self.response = response
        self.setup_slack_ns = response["worst_slack_ns"]
        self.setup_tns_ns = response["total_negative_slack_ns"]
        self.setup_violations = response["setup_violation_count"]
        self.hold_violations = response["hold_violation_count"]
        self.fmax_mhz = response.get("fmax_mhz")
        self.estimated_power_mw = response.get("estimated_power_mw")

    @property
    def setup_pass(self) -> bool:
        return self.setup_violations == 0 and self.setup_slack_ns is not None and self.setup_slack_ns >= 0

    @property
    def hold_pass(self) -> bool:
        return self.hold_violations == 0


def verdict_table(results: list[CornerResult], middle_columns: list[tuple[str, object]]) -> str:
    """Markdown per-corner table: Corner, setup slack/TNS, `middle_columns`,
    then Fmax and estimated power. Each middle column is a `(header, fn)`
    pair where `fn(result)` returns the cell text."""
    headers = [
        "Corner",
        "Setup slack (ns)",
        "Setup TNS (ns)",
        *(h for h, _ in middle_columns),
        "Fmax (MHz)",
        "Est. power (mW)",
    ]
    rows = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in results:
        cells = [
            f"`{r.corner}`",
            f"{'PASS' if r.setup_pass else 'FAIL'} {r.setup_slack_ns:+.4f}",
            f"{r.setup_tns_ns:+.4f}",
            *(fn(r) for _, fn in middle_columns),
            f"{r.fmax_mhz:.2f}",
            f"{r.estimated_power_mw:.4f}",
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)
