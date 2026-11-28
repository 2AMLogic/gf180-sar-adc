#!/usr/bin/env python3
"""Old-vs-new delta table for a re-qualification pair of dr0014-sampling records.

    python3 sim/dr0014-sampling/requal_delta.py OLD_ID NEW_ID [--rel 0.01] [--abs 1e-3]

Reads the per-corner result table of each record (`records/<id>.md`, the first
table whose header starts with `corner-id`) through the shared reader
`sim/tools/corner_table.py`, pairs the two by corner id, and prints one row per
measurement: the corner with the largest |new - old|, the old and new value
there, the delta, and whether it exceeds the tolerance. The shared reader keeps
reading past an ERROR verdict that carries several lines of simulator output,
so every corner after such a row is paired too.

A measurement is "moved" when |delta| > max(--abs, --rel * max(|old|, |new|))
at any corner. Defaults: 1 % relative, 1e-3 absolute (in the measurement's own
unit) so a value that is numerically zero does not register as a 100 % move.
A cell that is not a number (`n/a`, a pass/fail verdict) has no delta: the two
sides are compared as text, and a measurement that one record has and the
other lacks, or a verdict that changed, counts as moved.
Stdlib only, like the rest of sim/.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from corner_table import parse_record

RECORDS = Path(__file__).resolve().parent / "records"


def load(record_id):
    """Return {corner: {col: float-or-str}}, or exit naming the record and the defect."""
    try:
        return parse_record(RECORDS / f"{record_id}.md")
    except (OSError, ValueError) as exc:
        sys.exit(f"{record_id}: {exc}")


def columns(rows):
    """Measurement names in the record's own column order."""
    return list(dict.fromkeys(name for row in rows.values() for name in row))


def as_text(value):
    """A cell compared as text, kept on one line; a number prints as the numeric rows do."""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).replace("\n", "\\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--rel", type=float, default=0.01)
    ap.add_argument("--abs", dest="abs_", type=float, default=1e-3)
    args = ap.parse_args()

    orows, nrows = load(args.old), load(args.new)
    ocols, ncols = columns(orows), columns(nrows)
    corners = [c for c in orows if c in nrows]
    print(f"old {args.old}: {len(orows)} corners; new {args.new}: {len(nrows)} corners; "
          f"paired {len(corners)}")
    print("| metric | corner of max \\|delta\\| | old | new | delta | tolerance | moved |")
    print("|---|---|---|---|---|---|---|")
    moved = 0
    only_old = [c for c in ocols if c not in ncols]
    for col in ocols:
        if col not in ncols:
            continue
        best = None
        for c in corners:
            o, n = orows[c][col], nrows[c][col]
            if isinstance(o, float) and isinstance(n, float):
                tol = max(args.abs_, args.rel * max(abs(o), abs(n)))
                score = abs(n - o) / tol
                if best is None or score > best[0]:
                    best = (score, c, o, n, tol)
                continue
            if o != n:
                best = (float("inf"), c, o, n, None)
                break
        if best is None:
            continue
        score, c, o, n, tol = best
        if isinstance(o, float) and isinstance(n, float):
            flag = "yes" if score > 1 else "no"
            moved += flag == "yes"
            print(f"| `{col}` | `{c}` | {o:.6g} | {n:.6g} | {n - o:+.3g} | {tol:.3g} | {flag} |")
        else:
            moved += 1
            print(f"| `{col}` | `{c}` | {as_text(o)} | {as_text(n)} | n/a | exact | yes |")
    print(f"\n{moved} of the paired measurements moved beyond tolerance.")
    if only_old:
        print("Columns only in the old record: " + ", ".join(only_old))
    only_new = [c for c in ncols if c not in ocols]
    if only_new:
        print("Columns only in the new record: " + ", ".join(only_new))


if __name__ == "__main__":
    main()
