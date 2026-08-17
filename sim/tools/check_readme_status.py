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

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
GEN_ADC_TOP = REPO_ROOT / "design" / "adc-top" / "gen_adc_top.py"

#: The CDAC unit cap as ratified *before* DR-0019, in fF. Used only to decide
#: whether the DR-0019 resize is physically built -- see `_unit_cap_resized`.
PRE_DR0019_C_UNIT_FF = 17.24


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


def _normalized(text: str) -> str:
    """Collapse all runs of whitespace to a single space.

    Forbidden phrases are prose, and prose in this README is hard-wrapped, so a
    phrase that is one sentence in the source can be split across a newline at
    any point. Matching against the normalized text makes an assertion depend on
    the words rather than on where the wrap happens to fall -- otherwise a
    reflow silently disarms the guard, which is the same class of failure the
    guard exists to catch.
    """
    return " ".join(text.split())


def _unit_cap_resized() -> bool:
    """True once the generator carries a CDAC unit cap other than DR-0011's.

    Deliberately phrased as "not the pre-DR-0019 value" rather than "== 35.6528":
    the assertions below are about the README describing a *superseded* design,
    and that is true of any resize, not only of this one.
    """
    if not GEN_ADC_TOP.exists():
        return False
    m = re.search(
        r"^C_UNIT_FF\s*=\s*([0-9.]+)", GEN_ADC_TOP.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not m:
        return False
    return abs(float(m.group(1)) - PRE_DR0019_C_UNIT_FF) > 1e-9


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
    # --- DR-0019 resize drift (issue #197) --------------------------------
    # The resize landed in the generator and the layout (#196/PR #202) while
    # the Status section still described the pre-resize design: it named SFDR
    # as the *only* failing row (ENOB now fails at 2 of 9 corners too) and
    # still presented the extracted result as governing that row (that
    # extraction predates the resize). Both statements had gone from "true" to
    # "false" without a single character of the README changing, which is
    # exactly issue #71's failure mode a second time.
    (
        _unit_cap_resized,
        "the SFDR row still fails at one corner",
        "design/adc-top/gen_adc_top.py carries a resized CDAC unit cap, and "
        "re-running the suite at it (issue #197) put a second row -- ENOB -- "
        "outside its target, so the Status section can no longer say SFDR is "
        "the one failing row.",
    ),
    (
        _unit_cap_resized,
        "the extracted, independently-replicated result governs the row "
        "for the design as laid out, and it **passes**",
        "design/adc-top/gen_adc_top.py carries a resized CDAC unit cap, so "
        "every extracted result was taken on a layout that no longer matches "
        "the design; an extracted figure cannot be reported as *governing* a "
        "row until the extraction is re-taken (issue #218).",
    ),
]


def main() -> int:
    section = _normalized(_status_table_text())
    failures = []
    for artifact_present, phrase, explanation in CHECKS:
        if artifact_present() and _normalized(phrase) in section:
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
