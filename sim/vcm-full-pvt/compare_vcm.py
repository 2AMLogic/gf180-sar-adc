#!/usr/bin/env python3
"""Paired difference between two `sim/` corner-matrix records.

Issue #358 re-runs each ratified-row-owning ADC-level deck twice at the same
commit -- once with the ideal, zero-impedance `V_cm` source every existing
record in this suite assumes, once with DR-0026's real drive network -- so the
difference between the two is attributable to the `V_cm` network and to
nothing else. This script computes that difference.

It creates no numbers of its own beyond the subtraction: every value it prints
is read out of the two records' own per-point measurement tables, and every
bound it compares against is read out of the deck's own `testbench/tb.json`
`checks` block. Nothing is hardcoded here, so a bound that moves in the
manifest moves here too.

    python3 sim/vcm-full-pvt/compare_vcm.py \\
        --experiment adc-inl-dnl \\
        --ideal   sim/adc-inl-dnl/records/<ideal-id>.md \\
        --vcmnet  sim/adc-inl-dnl/records/<vcmnet-id>.md

Stdlib only, like the rest of ``sim/``.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_ROW = re.compile(r"^\s*\|(.+)\|\s*$")


def _cells(line: str) -> list[str]:
    m = _ROW.match(line)
    if not m:
        return []
    return [c.strip() for c in m.group(1).split("|")]


def _num(text: str) -> float | None:
    text = text.strip().strip("`")
    if not text or text == "—":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_points(record: Path) -> dict[str, dict[str, float]]:
    """`{corner-id: {measurement: value}}` from a record's per-point table.

    The table is the one under ``- **Result**:`` whose header's first cell is
    ``corner-id``; everything after the first blank line that follows it is a
    different table (the spread / per-axis ones) and is ignored.
    """
    header: list[str] | None = None
    out: dict[str, dict[str, float]] = {}
    for line in record.read_text().splitlines():
        cells = _cells(line)
        if header is None:
            if cells and cells[0] == "corner-id":
                header = cells
            continue
        if not cells:
            if out:
                break          # table ended
            continue
        if set("".join(cells)) <= {"-", ":"}:
            continue           # the |---|---| separator
        corner = cells[0].strip("`")
        row: dict[str, float] = {}
        for name, cell in zip(header[1:], cells[1:]):
            value = _num(cell)
            if value is not None:
                row[name] = value
        out[corner] = row
    if header is None:
        raise SystemExit(f"{record}: no per-point measurement table found")
    return out


def read_meta(record: Path) -> dict[str, str]:
    text = record.read_text()
    meta: dict[str, str] = {}
    for key in ("Record ID", "Netlist provenance"):
        m = re.search(rf"^- \*\*{re.escape(key)}\*\*: (.*)$", text, re.M)
        if m:
            meta[key] = m.group(1)
    m = re.search(r"^- git: `(\w+)` on `(\S+)` \((\w+)\)$", text, re.M)
    if m:
        meta["commit"] = m.group(1)[:7]
        meta["tree"] = m.group(3)
    m = re.search(r"^  - \*\*Overall: (\w+)\*\*$", text, re.M)
    if m:
        meta["verdict"] = m.group(1)
    return meta


def read_checks(experiment: str) -> dict[str, dict]:
    manifest = REPO_ROOT / "sim" / experiment / "testbench" / "tb.json"
    return json.loads(manifest.read_text()).get("checks", {})


def _fmt(x: float | None) -> str:
    if x is None:
        return "—"
    if x == 0:
        return "0"
    if abs(x) >= 1e4 or abs(x) < 1e-3:
        return f"{x:.6g}"
    return f"{x:.6g}"


def compare(experiment: str, ideal: Path, vcmnet: Path) -> int:
    a, b = read_points(ideal), read_points(vcmnet)
    checks = read_checks(experiment)

    shared_corners = [c for c in a if c in b]
    missing = sorted(set(a) ^ set(b))
    names = [n for n in (list(a[shared_corners[0]]) if shared_corners else []) if
             all(n in a[c] and n in b[c] for c in shared_corners)]

    ma, mb = read_meta(ideal), read_meta(vcmnet)
    print(f"# Paired V_cm-network delta — `{experiment}`")
    print()
    print(f"- ideal-source control: `{ma.get('Record ID', ideal.stem)}` "
          f"(git `{ma.get('commit', '?')}`, {ma.get('tree', '?')}, "
          f"overall {ma.get('verdict', '?')})")
    print(f"- V_cm network at budget: `{mb.get('Record ID', vcmnet.stem)}` "
          f"(git `{mb.get('commit', '?')}`, {mb.get('tree', '?')}, "
          f"overall {mb.get('verdict', '?')})")
    print(f"- paired points: {len(shared_corners)}"
          + (f"  (UNPAIRED: {', '.join(missing)})" if missing else ""))
    print()

    if not shared_corners:
        print("**No paired points — the two records share no corner-id.**")
        return 1

    print("| measurement | bound | ideal worst | V_cm-net worst | worst |Δ| "
          "| at corner | Δ vs bound | verdict |")
    print("|---|---|---|---|---|---|---|---|")

    any_breach = False
    for name in names:
        lo = checks.get(name, {}).get("min")
        hi = checks.get(name, {}).get("max")
        bound = "—"
        if lo is not None and hi is not None:
            bound = f"{_fmt(lo)} … {_fmt(hi)}"
        elif hi is not None:
            bound = f"≤ {_fmt(hi)}"
        elif lo is not None:
            bound = f"≥ {_fmt(lo)}"

        # "worst" = the value furthest outside (or closest to) the bound. With
        # a two-sided bound that is the largest |value|; with a one-sided max
        # it is the largest value; with a one-sided min the smallest. With no
        # bound at all, report the largest |value| so the column is defined.
        def worst(points: dict[str, dict[str, float]]) -> tuple[str, float]:
            if lo is not None and hi is None:
                c = min(shared_corners, key=lambda c: points[c][name])
            elif hi is not None and lo is None:
                c = max(shared_corners, key=lambda c: points[c][name])
            else:
                c = max(shared_corners, key=lambda c: abs(points[c][name]))
            return c, points[c][name]

        ca, va = worst(a)
        cb, vb = worst(b)
        cd = max(shared_corners, key=lambda c: abs(b[c][name] - a[c][name]))
        delta = b[cd][name] - a[cd][name]

        # Headroom the V_cm-network arm has left against the deck's own bound,
        # measured in units of the worst paired move -- i.e. "how many more
        # moves this size would it take to breach?"
        margin = None
        if hi is not None and lo is not None:
            margin = min(hi - vb, vb - lo)
        elif hi is not None:
            margin = hi - vb
        elif lo is not None:
            margin = vb - lo

        if margin is None:
            verdict = "no bound"
            ratio = "—"
        elif margin < 0:
            verdict = "**BREACH**"
            ratio = f"{_fmt(margin)}"
            any_breach = True
        else:
            verdict = "inside"
            ratio = (f"{margin / abs(delta):.4g}× the move"
                     if delta and not math.isclose(delta, 0.0) else "∞ (Δ=0)")

        print(f"| `{name}` | {bound} | {_fmt(va)} (`{ca}`) | {_fmt(vb)} "
              f"(`{cb}`) | {_fmt(abs(delta))} | `{cd}` | {ratio} | {verdict} |")

    print()
    if any_breach:
        print("**At least one measurement leaves its manifest bound under the "
              "V_cm network.** Read the BREACH rows against the deck's own "
              "check descriptions before attributing them to `V_cm`: this "
              "table reports the paired move, not a root cause.")
    else:
        print("**No measurement leaves its manifest bound under the V_cm "
              "network at DR-0026's budget on this grid.**")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment", required=True,
                   help="experiment slug (reads sim/<slug>/testbench/tb.json "
                        "for the bounds)")
    p.add_argument("--ideal", type=Path, required=True,
                   help="record from the ideal-V_cm-source control arm")
    p.add_argument("--vcmnet", type=Path, required=True,
                   help="record from the V_cm-drive-network arm")
    args = p.parse_args(argv)
    return compare(args.experiment, args.ideal, args.vcmnet)


if __name__ == "__main__":
    raise SystemExit(main())
