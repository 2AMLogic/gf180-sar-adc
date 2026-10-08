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

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
GEN_ADC_TOP = REPO_ROOT / "design" / "adc-top" / "gen_adc_top.py"
FRESHNESS = REPO_ROOT / "signoff" / "freshness.json"
CHAR_SUMMARY = REPO_ROOT / "sim" / "characterization-summary.md"
AREA_JSON = REPO_ROOT / "layout" / "adc-top" / "area.json"

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


# --- Issue #415: the Status summary is tied to the signoff grader ----------
#
# The Status section opens with a displayed summary (tier + T1 met/total +
# record id) and a compact table of non-passing spec rows. Neither is a new
# independently maintained fact: the first must equal the report that
# `signoff/freshness.json` selects, the second must equal the set of rows the
# characterization summary's own verdict column marks FAIL / not measured /
# stretch-missed. Only the displayed text is parsed, so a summary that is
# deleted or malformed fails rather than passing vacuously.

SUMMARY_BEGIN = "<!-- status:summary-begin -->"
SUMMARY_END = "<!-- status:summary-end -->"
ROWS_BEGIN = "<!-- status:spec-rows-begin -->"
ROWS_END = "<!-- status:spec-rows-end -->"
ROW_SECTION = "## Per-spec-row status"


def _selected_report(root: Path = REPO_ROOT) -> dict:
    """The report JSON selected by freshness.json (never a hardcoded id)."""
    fresh = json.loads((root / "signoff" / "freshness.json").read_text(encoding="utf-8"))
    rel = fresh["report"]["json"]
    report = json.loads((root / rel).read_text(encoding="utf-8"))
    report["_record_id"] = fresh["report"]["record_id"]
    return report


def _between(text: str, begin: str, end: str) -> str | None:
    i = text.find(begin)
    j = text.find(end, i + len(begin)) if i != -1 else -1
    return None if i == -1 or j == -1 else text[i + len(begin):j]


def _verdict_class(verdict: str) -> str | None:
    """Classify a characterization-summary verdict cell, or None if it passes
    without a caveat this guard tracks."""
    v = verdict.strip().lstrip("*").strip()
    if v.startswith("FAIL"):
        return "FAIL"
    if v.startswith("Not measured"):
        return "Unmeasured"
    if "stretch target still missed" in verdict:
        return "PASS, stretch missed"
    return None


def char_summary_rows(text: str) -> dict[str, str]:
    """{row name: class} for the rows the compact Status table must list."""
    start = text.find(ROW_SECTION)
    if start == -1:
        raise ValueError(f"no '{ROW_SECTION}' section in the characterization summary")
    rest = text[start + len(ROW_SECTION):]
    end = rest.find("\n## ")
    rows: dict[str, str] = {}
    for line in (rest if end == -1 else rest[:end]).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) != 5 or cells[0] in ("Spec row (README target)",) or set(cells[0]) <= {"-"}:
            continue
        cls = _verdict_class(cells[3])
        if cls:
            rows[cells[0]] = cls
    return rows


def check_summary(status: str, report: dict, char_text: str) -> list[str]:
    """Return a list of problems with the Status summary (empty == ok)."""
    errs: list[str] = []
    summ = _between(status, SUMMARY_BEGIN, SUMMARY_END)
    if summ is None:
        errs.append(f"Status summary markers {SUMMARY_BEGIN} ... {SUMMARY_END} missing")
    else:
        flat = _normalized(summ)
        tier = report.get("tier")
        want_tier = "none" if tier is None else str(tier)
        m = re.search(r"`tier: ([^`]+)`", flat)
        if not m:
            errs.append("summary has no displayed `tier: <tier>`")
        elif m.group(1) != want_tier:
            errs.append(f"summary tier {m.group(1)!r} != report tier {want_tier!r}")
        m = re.search(r"\b(\d+) of (\d+) T1\b", flat)
        if not m:
            errs.append("summary has no displayed '<met> of <total> T1' counts")
        else:
            got = (int(m.group(1)), int(m.group(2)))
            want = (report.get("t1_met_count"), report.get("t1_item_count"))
            if got != want:
                errs.append(f"summary counts {got[0]} of {got[1]} != report {want[0]} of {want[1]}")
    rid = report.get("_record_id")
    if rid and rid not in status:
        errs.append(f"Status does not cite the selected record {rid}")

    table = _between(status, ROWS_BEGIN, ROWS_END)
    if table is None:
        errs.append(f"spec-row table markers {ROWS_BEGIN} ... {ROWS_END} missing")
    else:
        shown: dict[str, str] = {}
        for line in table.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            if line.startswith("|") and len(cells) >= 2 and cells[0] != "Spec row" \
                    and not set(cells[0]) <= {"-"}:
                shown[cells[0]] = cells[1]
        try:
            want_rows = char_summary_rows(char_text)
        except ValueError as exc:
            errs.append(str(exc))
        else:
            for name in sorted(set(want_rows) - set(shown)):
                errs.append(f"spec row {name!r} ({want_rows[name]}) missing from Status table")
            for name in sorted(set(shown) - set(want_rows)):
                errs.append(f"Status table lists {name!r}, which the characterization summary does not mark non-passing")
            for name in sorted(set(shown) & set(want_rows)):
                if shown[name] != want_rows[name]:
                    errs.append(f"spec row {name!r}: Status says {shown[name]!r}, characterization summary says {want_rows[name]!r}")
    return errs


# --- Issue #421: the State table's Layout row is tied to area.json ---------

def check_layout_area(status: str, area: dict) -> list[str]:
    """The `adc_block at X mm^2` figure in the Layout row must equal
    layout/adc-top/area.json's block_total (um^2 -> mm^2, 6 decimals)."""
    row = next((l for l in status.splitlines() if l.startswith("| Layout | ")), None)
    if row is None:
        return ["State table has no 'Layout' row"]
    m = re.search(r"`adc_block` at ([0-9.]+) mm", row)
    if not m:
        return ["Layout row quotes no '`adc_block` at <X> mm²' area figure"]
    want = f"{area['areas_um2']['block_total'] / 1e6:.6f}"
    if m.group(1) != want:
        return [f"Layout row quotes {m.group(1)} mm² but area.json block_total is {want} mm²"]
    return []


def main() -> int:
    status_raw = _status_table_text()
    section = _normalized(status_raw)
    failures = []
    for artifact_present, phrase, explanation in CHECKS:
        if artifact_present() and _normalized(phrase) in section:
            failures.append((phrase, explanation))

    summary_errs = check_summary(
        status_raw, _selected_report(), CHAR_SUMMARY.read_text(encoding="utf-8")
    )
    summary_errs += check_layout_area(
        status_raw, json.loads(AREA_JSON.read_text(encoding="utf-8"))
    )
    if summary_errs:
        print("README.md's Status summary disagrees with its sources (issue #415):\n")
        for e in summary_errs:
            print(f"  - {e}")
        return 1

    if failures:
        print("README.md's Status section is stale relative to the tree:\n")
        for phrase, explanation in failures:
            print(f"  - still contains {phrase!r}: {explanation}")
        print(
            f"\nUpdate the '## Status' section in {README.name} "
            "to match the tree (see issue #71)."
        )
        return 1

    print(f"ok: {README.name}'s Status section has no known-stale phrases and its summary matches the selected signoff report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
