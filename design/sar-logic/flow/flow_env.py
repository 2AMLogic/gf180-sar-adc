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
import subprocess
from pathlib import Path


def run(repo_root: Path, cmd: list[str]) -> subprocess.CompletedProcess:
    """Run `cmd` from `repo_root`, capturing both streams; never raises on a
    non-zero exit -- every caller here inspects `returncode` itself and
    reports the tool's own stdout/stderr in the failure it raises."""
    return subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)


def git(repo_root: Path, *args: str) -> str:
    """`git <args...>` from `repo_root`; stripped stdout, or `""` on failure.

    The empty string covers both "git exited non-zero" and "there is no git
    binary at all" (the `OSError` guard), so a caller minting a record in an
    exported tarball degrades to `nogit`/`unknown` instead of crashing.
    """
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


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
    """`klt --version` as the evidence records stamp it.

    Reads stderr when stdout is empty because `klt` has reported its version
    on either stream across the builds this repo has run against.
    """
    result = run(repo_root, ["klt", "--version"])
    return (result.stdout or result.stderr).strip()


def record_id(repo_root: Path, when: _dt.datetime) -> str:
    """``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``, matching sim/README.md's grammar.

    `when` is passed in, not read from the clock here, so that one driver run
    naming several artifacts (`synth_sar_ctrl.py` synthesizes two libraries
    under a single record ID) stamps them all with the same instant.
    """
    sha = git(repo_root, "rev-parse", "--short", "HEAD") or "nogit"
    return f"{when.strftime('%Y%m%d-%H%M%S')}-{sha}"
