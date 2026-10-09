#!/usr/bin/env python3
"""Issue #459: do two committed records of the same deck bytes reproduce each other?

For each pair given, compares (1) the per-corner Result rows of the two
records and (2) their raw per-corner ngspice logs with ngspice's progress
lines ("Reference value : ...", which are emitted on a wall-clock cadence and
so differ between any two runs) removed. Also prints the environment each
record states and the ngspice compatibility-mode note its first log carries.
Reads committed evidence only; runs no simulation. From the repository root:

    python3 -I sim/dr0014-sampling/investigations/20261009-issue-459-record-pairs.py

With no arguments it runs the pair set the issue #459 investigation cites.
Otherwise pass pairs as  <experiment>/<record-id>:<record-id> ...
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SIM = Path("sim")

# (experiment, record A, record B) -- every pair shares the recorded
# "Testbench netlist sha256" and "Manifest sha256".
DEFAULT_PAIRS = [
    # same host family (/home/ubuntu, ngspice-46, no compatibility mode)
    ("dr0014-sampling", "20260817-134517-cde979d", "20260923-085243-664c8dc"),
    ("adc-inl-dnl", "20260817-214114-076d545", "20260923-095803-836a876"),
    ("adc-inl-dnl", "20260817-131106-abf9c75", "20260923-072117-664c8dc"),
    ("adc-power", "20260826-085142-155595d", "20260923-112459-836a876"),
    # same host family (/Users/rwalters, ngspice-46, compatibility mode "hs a")
    ("track-switch-sampling", "20260801-113511-c05043b", "20260802-141402-1224e11"),
    ("smoke-sar-bias", "20260731-155343-685ba01", "20260731-162251-1dcdf3a"),
    # across the two host families
    ("dr0014-sampling", "20260923-104443-904af96", "20261007-071907-800bf53"),
    ("adc-inl-dnl", "20260923-095400-904af96", "20261007-044826-800bf53"),
    ("adc-power", "20260923-102440-904af96", "20261007-072338-800bf53"),
    ("adc-enob-fft", "20260923-111149-904af96", "20261007-072654-800bf53"),
    ("device-switch-ron", "20260731-191216-5f5288b", "20260806-140624-4f71285"),
]
PROGRESS = re.compile(r"^\s*Reference value\s*:")
COMPAT = re.compile(r"^Note: (No compatibility mode selected!|Compatibility modes selected:.*)$", re.M)


def field(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.M)
    return m.group(1) if m else "n/a"


def rows(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    header = False
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("| corner-id |"):
            header = True
        elif header and line.startswith("| `"):
            out[line.split("|")[1].strip().strip("`")] = line
        elif header and out and not line.startswith("|"):
            break
    return out


def stripped_log(path: Path) -> list[str]:
    return [ln for ln in path.read_text().splitlines() if not PROGRESS.match(ln)]


def compare(exp: str, a: str, b: str) -> None:
    ra, rb = (SIM / exp / "records" / f"{r}.md" for r in (a, b))
    ta, tb = ra.read_text(), rb.read_text()
    print(f"== {exp}: {a} vs {b}")
    for tag, t, rid in (("A", ta, a), ("B", tb, b)):
        logs = sorted((SIM / exp / "corners" / rid).glob("*.log"))
        compat = COMPAT.search(logs[0].read_text()).group(1) if logs else "n/a"
        host = field(t, r"\((/[A-Za-z]+/[A-Za-z]+)/\.volare")
        ngspice = field(t, r"^- ngspice: (ngspice-\S*)")
        python = field(t, r"python (\d[\d.]*)")
        commit = field(t, r"^- git: `([0-9a-f]{7})")
        tree = field(t, r"^- git: .*\((dirty|clean)\)")
        print(f"  {tag}: host {host}, {ngspice}, python {python}, git {commit} {tree}, "
              f"ngspice note: {compat}")
    same_hash = all(field(ta, p) == field(tb, p) != "n/a" for p in
                    (r"Testbench netlist sha256: `([0-9a-f]+)`", r"Manifest sha256: `([0-9a-f]+)`"))
    print(f"  deck + manifest sha256 identical: {same_hash}")
    xa, xb = rows(ra), rows(rb)
    ident = sum(1 for k in xa if xb.get(k) == xa[k])
    print(f"  Result rows byte-identical: {ident}/{len(xa)}")
    la = {p.name: p for p in (SIM / exp / "corners" / a).glob("*.log")}
    lb = {p.name: p for p in (SIM / exp / "corners" / b).glob("*.log")}
    common = sorted(set(la) & set(lb))
    same = sum(1 for n in common if stripped_log(la[n]) == stripped_log(lb[n]))
    print(f"  raw logs identical except progress lines: {same}/{len(common)}")


def main(argv: list[str]) -> int:
    pairs = DEFAULT_PAIRS
    if argv:
        pairs = []
        for arg in argv:
            exp, ids = arg.split("/", 1)
            a, b = ids.split(":")
            pairs.append((exp, a, b))
    for p in pairs:
        compare(*p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
