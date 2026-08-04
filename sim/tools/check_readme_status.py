#!/usr/bin/env python3
"""Guard against issue #71's failure mode: root README.md's Status table
understating what the tree actually contains.

This is deliberately narrow, not a general "docs match reality" framework.
It encodes a short list of (artifact exists on disk) -> (README must not
still say the old, now-false thing) assertions, one per prior drift incident.
When the next artifact lands and makes another Status row stale, add one more
assertion here rather than generalizing speculatively -- see the PR that
introduced this file (issue #71) for the rationale.

Stdlib-only, no PDK / ngspice / klt required, so it belongs on the headless
CI path (.github/workflows/ci.yml).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"


def _status_table_text() -> str:
    """Return the '## Status' section's text (up to the next '## ' heading)."""
    text = README.read_text(encoding="utf-8")
    marker = "## Status"
    start = text.find(marker)
    if start == -1:
        raise SystemExit(f"error: {README} has no '## Status' section")
    rest = text[start + len(marker):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


# Each entry: (artifact_present, forbidden_phrase, explanation).
# `artifact_present` is a callable so the checks stay lazy and cheap.
CHECKS = [
    (
        lambda: (REPO_ROOT / "design" / "adc-top" / "adc_top.spice").exists(),
        "Smoke-test only",
        "design/adc-top/adc_top.spice exists (a generated transistor-level "
        "netlist), so the Schematics row can no longer say schematics are "
        "smoke-test only.",
    ),
    (
        lambda: any((REPO_ROOT / "layout" / "adc-top").glob("*.gds")),
        "No block layout yet",
        "layout/adc-top/ contains drawn GDS, so the Layout row can no longer "
        "say there is no block layout.",
    ),
    (
        lambda: any((REPO_ROOT / "layout" / "adc-top").glob("*.lvs.json")),
        "LVS deferred",
        "layout/adc-top/ contains LVS request documents (*.lvs.json), so the "
        "Layout row can no longer say LVS is deferred.",
    ),
]


def main() -> int:
    section = _status_table_text()
    failures = []
    for artifact_present, phrase, explanation in CHECKS:
        if artifact_present() and phrase in section:
            failures.append((phrase, explanation))

    if failures:
        print("README.md's Status section is stale relative to the tree:\n")
        for phrase, explanation in failures:
            print(f"  - still contains {phrase!r}: {explanation}")
        print(
            f"\nUpdate the '## Status' section in {README.relative_to(REPO_ROOT)} "
            "to match the tree (see issue #71)."
        )
        return 1

    print(f"ok: {README.relative_to(REPO_ROOT)}'s Status section has no known-stale phrases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
