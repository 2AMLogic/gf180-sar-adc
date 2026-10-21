#!/usr/bin/env python3
"""Old-vs-new delta table for a re-qualification pair of dr0014-sampling records.

    python3 sim/dr0014-sampling/requal_delta.py OLD_ID NEW_ID [--rel 0.01] [--abs 1e-3]

Reads the per-corner result table of each record (`records/<id>.md`, the first
table whose header starts with `corner-id`), pairs the two by corner id, and
prints one row per measurement: the corner with the largest |new - old|, the
old and new value there, the delta, and whether it exceeds the tolerance.

A measurement is "moved" when |delta| > max(--abs, --rel * max(|old|, |new|))
at any corner. Defaults: 1 % relative, 1e-3 absolute (in the measurement's own
unit) so a value that is numerically zero does not register as a 100 % move.
Stdlib only, like the rest of sim/.
"""

import argparse
import re
import sys
from pathlib import Path

RECORDS = Path(__file__).resolve().parent / "records"


def parse(record_id):
    """Return (columns, {corner: {col: value-or-str}}) from the first corner-id table."""
    lines = (RECORDS / f"{record_id}.md").read_text().splitlines()
    rows, cols = {}, None
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells[0] == "corner-id":
            cols = cells
        elif cols and not set(cells[0]) <= set("-"):
            rows[cells[0].strip("`")] = dict(zip(cols, cells))
    if cols is None:
        sys.exit(f"{record_id}: no corner-id table found")
    return cols, rows


def num(text):
    try:
        return float(text)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--rel", type=float, default=0.01)
    ap.add_argument("--abs", dest="abs_", type=float, default=1e-3)
    args = ap.parse_args()

    ocols, orows = parse(args.old)
    ncols, nrows = parse(args.new)
    corners = [c for c in orows if c in nrows]
    print(f"old {args.old}: {len(orows)} corners; new {args.new}: {len(nrows)} corners; "
          f"paired {len(corners)}")
    print("| metric | corner of max \\|delta\\| | old | new | delta | tolerance | moved |")
    print("|---|---|---|---|---|---|---|")
    moved = 0
    only_old = [c for c in ocols[1:] if c not in ncols]
    for col in ocols[1:]:
        if col not in ncols:
            continue
        best = None
        for c in corners:
            o, n = num(orows[c][col]), num(nrows[c][col])
            if o is None or n is None:
                if orows[c][col] != nrows[c][col]:
                    best = (float("inf"), c, orows[c][col], nrows[c][col])
                    break
                continue
            d = abs(n - o)
            tol = max(args.abs_, args.rel * max(abs(o), abs(n)))
            score = d / tol
            if best is None or score > best[0]:
                best = (score, c, o, n)
        if best is None:
            continue
        score, c, o, n = best
        if isinstance(o, str):
            print(f"| `{col}` | `{c}` | {o} | {n} | n/a | exact | yes |")
            moved += 1
            continue
        tol = max(args.abs_, args.rel * max(abs(o), abs(n)))
        flag = "yes" if score > 1 else "no"
        moved += flag == "yes"
        print(f"| `{col}` | `{c}` | {o:.6g} | {n:.6g} | {n - o:+.3g} | {tol:.3g} | {flag} |")
    print(f"\n{moved} of the paired measurements moved beyond tolerance.")
    if only_old:
        print("Columns only in the old record: " + ", ".join(only_old))
    only_new = [c for c in ncols[1:] if c not in ocols]
    if only_new:
        print("Columns only in the new record: " + ", ".join(only_new))


if __name__ == "__main__":
    main()
