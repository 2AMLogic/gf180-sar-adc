#!/usr/bin/env python3
"""Environment probing shared by the `layout/` evidence runners.

`layout/drc/run_drc.py` and `layout/lvs/run_lvs.py` each need to locate the
`klt` (2AMLogic/klayout-tools) binary, verify it against this repo's
toolchain pin, and -- only for `--regen` -- locate a Python interpreter with
the pip `klayout` package. This module is the single implementation of that
probing, imported by **both** runners, so a `klt`/interpreter problem is
diagnosed and reported identically regardless of which runner hit it first.

Why it lives here and not in either runner: `find_klt`/`find_klayout_python`
are environment facts, not a DRC fact or an LVS fact, and a copy in one
runner is a claim about that runner only -- exactly the argument
`toolchain_pin.py` (beside this file) already makes for the capability
probe itself. Before this module existed, both runners carried
byte-identical copies of `ToolingError`, the exit-code constants, and these
two functions, admitted in their own docstrings as forks of each other; one
implementation is what keeps them from silently drifting apart on the next
edit.

`check_klt_capabilities` here is a thin, `ToolingError`-raising wrapper
around `toolchain_pin.klt_capability_error` -- the probe itself already
lived in `toolchain_pin.py`, shared by both runners; this only adds the
`ToolingError`/exit-1 discipline both runners use around it.

This module is import-only -- it runs no tool at import time and has no
side effects, so `python3 -m compileall layout` (this repo's CI) covers it
without needing `klt` installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import toolchain_pin

EXIT_OK = 0
EXIT_TOOLING = 1
EXIT_MISMATCH = 2


class ToolingError(Exception):
    """Something about the environment, not the design under test, is
    wrong."""


def find_klt() -> str:
    klt = shutil.which("klt")
    if klt is None:
        raise ToolingError(
            "`klt` not found on PATH. Install klayout-tools "
            "(https://github.com/2AMLogic/klayout-tools), e.g.\n"
            "    uv tool install git+https://github.com/2AMLogic/klayout-tools"
        )
    return klt


def check_klt_capabilities(klt: str, pin: dict) -> None:
    """Fail unless the installed `klt` has every command in `pin`'s
    `klt_required_commands` -- the drift-detectable check for this toolchain
    pin (see `toolchain.json`'s `_comment` for why a version string cannot
    do this job: `klt --version` reports a static string that does not
    change between a release that has the verbs a caller needs and one that
    does not).

    The probe itself lives in `toolchain_pin.py`, shared by both
    `layout/drc/run_drc.py` and `layout/lvs/run_lvs.py`; this wrapper only
    adapts its message to this module's own `ToolingError`/exit-1
    discipline, which both runners share.
    """
    problem = toolchain_pin.klt_capability_error(klt, pin)
    if problem:
        raise ToolingError(problem)


def find_klayout_python() -> str:
    """Return an interpreter that can `import klayout.db`.

    Tries this interpreter first, then the one `klt` itself runs under --
    klayout-tools depends on the pip `klayout` package, so its environment
    always has it, and reusing it means the GDS is regenerated against the
    same KLayout build that will then check it.
    """
    candidates = [sys.executable]

    klt = shutil.which("klt")
    if klt is not None:
        try:
            with open(os.path.realpath(klt), "rb") as fh:
                first = fh.readline().decode("utf-8", "replace").strip()
            if first.startswith("#!"):
                candidates.append(first[2:].strip().split()[0])
        except OSError:
            pass

    for candidate in candidates:
        if not candidate:
            continue
        probe = subprocess.run(
            [candidate, "-c", "import klayout.db"],
            capture_output=True,
        )
        if probe.returncode == 0:
            return candidate

    raise ToolingError(
        "no interpreter with the pip `klayout` package found "
        f"(tried: {', '.join(c for c in candidates if c)}). "
        "Install it with `pip install klayout`, or drop --regen and use the "
        "committed GDS."
    )
