#!/usr/bin/env python3
"""The `layout/` toolchain pin, and the capability check that enforces it.

`toolchain.json` (beside this file) pins the exact `klt`
(2AMLogic/klayout-tools) commit this repo's layout flow runs against, and
lists in `klt_required_commands` every `klt <command>` the runners under
`layout/` invoke. This module is the single implementation of the check
that turns that list into something enforced rather than merely recorded --
imported by **both** `layout/drc/run_drc.py` and `layout/lvs/run_lvs.py`, so
the "checked before either runner does anything" claim in `toolchain.json`'s
own `_comment` is true of both of them, not just whichever one happened to
be written last.

Why it lives here and not in either runner: a copy in one runner is a claim
about that runner only. A missing `klt` verb is a *toolchain* fact, not a
DRC fact or an LVS fact, and both runners must fail the same loud,
actionable way when the installed `klt` drifts off the pin -- which is only
guaranteed if there is one implementation to drift.

The check is deliberately a **capability probe, not a version comparison**:
`klt --version` reports a static `0.1.0` from klayout-tools' own
`pyproject.toml` and does not change commit-to-commit, so a version string
compares equal against a `klt` that is missing a verb this repo needs. See
`toolchain.json`'s `_comment` for the full rationale and for why the install
is pinned to an exact commit rather than a floating branch.

This module is import-only -- it runs no tool at import time and has no
side effects, so `python3 -m compileall layout` (this repo's CI) covers it
without needing `klt` installed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
TOOLCHAIN_PIN_PATH = os.path.join(HERE, "toolchain.json")


def load_toolchain_pin(path: str = TOOLCHAIN_PIN_PATH) -> dict:
    """Load `layout/toolchain.json`. Raises OSError/JSONDecodeError on a
    missing or malformed pin -- callers treat either as a tooling error."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def klt_capability_error(klt: str, pin: dict) -> str | None:
    """Return an error message if the installed `klt` is missing any command
    in `pin`'s `klt_required_commands`, else None.

    Returns a message rather than raising so each runner can wrap it in its
    own `ToolingError` and keep its documented exit-code discipline (exit 1
    = tooling problem) without either runner having to import the other's
    exception type.

    A single `klt --help` call (not one probe per command): every `klt`
    invocation that touches `klayout.db` pays a real, multi-second
    process-lifecycle cost (importing the native module), so this avoids
    multiplying it for a check that a single top-level `--help` answers just
    as well -- the top-level parser lists every registered subcommand by
    name (see `klt --help`'s "positional arguments" section) without
    dispatching into any of them.

    Names *every* missing command plus the install command from the pin,
    rather than stopping at the first one, so a completely stale `klt`
    reports a complete, actionable picture at once.
    """
    probe = subprocess.run([klt, "--help"], capture_output=True, text=True)
    if probe.returncode != 0:
        return f"`klt --help` failed (exit {probe.returncode}): {probe.stderr}"

    listed = probe.stdout
    required = pin.get("klt_required_commands", [])
    missing = [
        command
        for command in required
        if not re.search(rf"(?m)^\s+{re.escape(command)}\s", listed)
    ]
    if not missing:
        return None

    return (
        f"installed `klt` is missing required command(s): {', '.join(missing)}. "
        f"This repo's layout/ pin ({os.path.relpath(TOOLCHAIN_PIN_PATH, REPO_ROOT)}) "
        f"needs all of {required!r}. Reinstall from source:\n"
        f"    uv tool install --force {pin['klt_install']}\n"
        "(`klt --version` will not change -- see the pin file's own note.)"
    )
