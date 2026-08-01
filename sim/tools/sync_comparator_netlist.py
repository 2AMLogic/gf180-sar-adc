#!/usr/bin/env python3
"""Propagate the canonical comparator netlist into every testbench fragment.

The corner runner consumes SELF-CONTAINED netlist fragments -- a fragment may
not `.include` anything (sim/harness/README.md), because the harness owns every
include/lib/temp/control directive. So the comparator's devices have to be
physically duplicated into each `sim/comparator-*/testbench/*.spice`.

Duplication that drifts is worse than no duplication at all: a testbench
measuring a stale sizing would produce a record that looks valid and is not.
This script is one half of the guard (it writes the copies); the other half is
`sim/tests/test_comparator_netlist.py`, which fails the harness unit tests if
any copy differs from the canonical file.

    python3 sim/tools/sync_comparator_netlist.py            # rewrite copies
    python3 sim/tools/sync_comparator_netlist.py --check    # exit 1 if stale
"""

from __future__ import annotations

import argparse
import pathlib
import sys

BEGIN = "* --- COMPARATOR-NETLIST-BEGIN"
END = "* --- COMPARATOR-NETLIST-END ---"

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "design" / "comparator" / "comparator.spice"


def extract(text: str, where: pathlib.Path) -> str:
    """Return the marker-delimited block, markers included."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if ln.startswith(BEGIN)]
    ends = [i for i, ln in enumerate(lines) if ln.startswith(END)]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise SystemExit(
            f"{where}: expected exactly one {BEGIN}...{END} block, "
            f"found {len(starts)} begin / {len(ends)} end markers"
        )
    return "".join(lines[starts[0] : ends[0] + 1])


def targets() -> list[pathlib.Path]:
    found = sorted((REPO / "sim").glob("comparator-*/testbench/*.spice"))
    return [p for p in found if BEGIN in p.read_text()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="report stale copies and exit 1 instead of rewriting them",
    )
    args = ap.parse_args()

    block = extract(CANONICAL.read_text(), CANONICAL)
    stale: list[pathlib.Path] = []

    for path in targets():
        text = path.read_text()
        current = extract(text, path)
        if current == block:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(text.replace(current, block))

    rel = [str(p.relative_to(REPO)) for p in stale]
    if args.check:
        if stale:
            print("stale comparator-netlist copies:", file=sys.stderr)
            for r in rel:
                print(f"  {r}", file=sys.stderr)
            print(
                "run: python3 sim/tools/sync_comparator_netlist.py",
                file=sys.stderr,
            )
            return 1
        print(f"all {len(targets())} comparator-netlist copies are current")
        return 0

    if stale:
        print("refreshed:")
        for r in rel:
            print(f"  {r}")
    else:
        print(f"all {len(targets())} comparator-netlist copies were already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
