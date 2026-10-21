#!/usr/bin/env python3
"""Issue #623: how big is the Linux-vs-macOS offset on identical deck bytes?

For each (experiment, record A, record B) pair -- every pair shares the
recorded testbench and manifest sha256 and crosses the /home/ubuntu and
/Users/rwalters host families -- pairs the two records' per-corner Result
rows by corner id and prints, per measurement, the corner with the largest
|B - A|, both values there, and the delta in the measurement's own unit.
Measurements whose values are byte-identical in every corner are counted,
not listed. Reads committed evidence only; runs no simulation. From the
repository root:

    python3 -I sim/dr0014-sampling/investigations/20261021-issue-623-cross-host-deltas.py
"""
from __future__ import annotations

import sys
from pathlib import Path

SIM = Path("sim")

PAIRS = [
    ("dr0014-sampling", "20260923-104443-904af96", "20261007-071907-800bf53"),
    ("adc-inl-dnl", "20260923-095400-904af96", "20261007-044826-800bf53"),
    ("adc-power", "20260923-102440-904af96", "20261007-072338-800bf53"),
    ("adc-enob-fft", "20260923-111149-904af96", "20261007-072654-800bf53"),
    ("device-switch-ron", "20260731-191216-5f5288b", "20260806-140624-4f71285"),
]


def table(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    cols: list[str] = []
    rows: dict[str, list[str]] = {}
    for line in path.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.strip().startswith("|"):
            if rows:
                break
        elif cells[0] == "corner-id":
            cols = cells
        elif cols and not set(cells[0]) <= set("-"):
            rows[cells[0].strip("`")] = cells
    return cols, rows


def num(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def compare(exp: str, a: str, b: str) -> None:
    ca, ra = table(SIM / exp / "records" / f"{a}.md")
    cb, rb = table(SIM / exp / "records" / f"{b}.md")
    print(f"== {exp}: A {a} (Linux) vs B {b} (macOS)")
    common = sorted(set(ra) & set(rb))
    print(f"  corners paired: {len(common)} of {len(ra)} / {len(rb)}")
    moved = []
    same = 0
    for i, col in enumerate(ca[1:], start=1):
        if col not in cb:
            continue
        j = cb.index(col)
        worst = None
        for k in common:
            va, vb = num(ra[k][i]), num(rb[k][j])
            if va is None or vb is None:
                continue
            d = vb - va
            if d != 0 and (worst is None or abs(d) > abs(worst[3])):
                worst = (k, va, vb, d)
        if worst is None:
            same += 1
        else:
            moved.append((col, worst))
    print(f"  measurements byte-identical at every paired corner: {same}")
    print(f"  measurements with any difference: {len(moved)}")
    for col, (k, va, vb, d) in sorted(moved, key=lambda m: -abs(m[1][3])):
        print(f"    {col:28s} {k:16s} A {va:<14.6g} B {vb:<14.6g} delta {d:+.3g}")


def main() -> int:
    for p in PAIRS:
        compare(*p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
