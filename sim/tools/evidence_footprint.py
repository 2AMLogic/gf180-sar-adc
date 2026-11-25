#!/usr/bin/env python3
"""Report the tracked-byte footprint of `sim/` evidence (issue #476).

Sums the working-tree size of every file listed by `git ls-files sim/`, per
`sim/<experiment>/` and per record. A "record" is the `<record-id>` that names
a `corners/<record-id>/` directory or a `records/<record-id>.md` file; bytes
that belong to no record (testbench, scripts, READMEs) are reported under
`(other)`.

    python3 sim/tools/evidence_footprint.py            # per-experiment table
    python3 sim/tools/evidence_footprint.py --records  # also per-record rows
    python3 sim/tools/evidence_footprint.py --check    # compare to the budget

The budget lives in `sim/tools/evidence_footprint_budget.json`:
`{"total_bytes": N, "default_experiment_bytes": N, "experiments": {name: N}}`.
`--check` prints every over-budget line and exits 1 only with `--strict`;
without it the exit status is always 0 (report-only, as wired into check:ci).

This tool is purely observational: it never modifies, deletes or compresses
evidence. Stdlib-only; needs only `git`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_REL = "sim/tools/evidence_footprint_budget.json"
OTHER = "(other)"


def tracked_files(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", "sim"],
        capture_output=True, text=True, check=True,
    )
    return [p for p in proc.stdout.split("\0") if p]


def record_id(parts: list[str]) -> str:
    """`parts` is the path below sim/<experiment>/."""
    if len(parts) >= 3 and parts[0] == "corners":
        return parts[1]
    if len(parts) == 2 and parts[0] == "records" and parts[1].endswith(".md"):
        return parts[1][: -len(".md")]
    return OTHER


def measure(repo: Path, files: list[str] | None = None):
    """Return (per_experiment, per_record) byte dicts."""
    exp: dict[str, int] = defaultdict(int)
    rec: dict[tuple[str, str], int] = defaultdict(int)
    for rel in files if files is not None else tracked_files(repo):
        parts = rel.split("/")
        if len(parts) < 3 or parts[0] != "sim":
            continue  # files directly under sim/ are not an experiment
        path = repo / rel
        try:
            size = path.stat().st_size
        except OSError:
            continue  # tracked but deleted in the working tree
        exp[parts[1]] += size
        rec[(parts[1], record_id(parts[2:]))] += size
    return dict(exp), dict(rec)


def fmt(n: int) -> str:
    return f"{n:>12,d}  {n / 1048576:9.1f} MiB"


def load_budget(repo: Path) -> dict:
    return json.loads((repo / BUDGET_REL).read_text())


def check(exp: dict[str, int], budget: dict) -> list[str]:
    over = []
    total = sum(exp.values())
    if total > budget["total_bytes"]:
        over.append(f"TOTAL {total} > budget {budget['total_bytes']}")
    default = budget.get("default_experiment_bytes")
    per = budget.get("experiments", {})
    for name in sorted(exp):
        limit = per.get(name, default)
        if limit is not None and exp[name] > limit:
            over.append(f"{name} {exp[name]} > budget {limit}")
    return over


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", type=Path, default=REPO_ROOT)
    ap.add_argument("--records", action="store_true", help="also list per-record bytes")
    ap.add_argument("--check", action="store_true", help="compare against the budget file")
    ap.add_argument("--strict", action="store_true", help="with --check, exit 1 when over budget")
    args = ap.parse_args(argv)

    exp, rec = measure(args.repo)
    for name, n in sorted(exp.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{fmt(n)}  sim/{name}")
        if args.records:
            for (e, r), rn in sorted(rec.items(), key=lambda kv: (-kv[1], kv[0])):
                if e == name:
                    print(f"{fmt(rn)}      {r}")
    print(f"{fmt(sum(exp.values()))}  TOTAL (tracked files under sim/<experiment>/)")

    if args.check:
        over = check(exp, load_budget(args.repo))
        for line in over:
            print(f"over budget: {line}", file=sys.stderr)
        if over:
            print(f"evidence-footprint: {len(over)} over budget "
                  f"({'failing' if args.strict else 'report-only'})", file=sys.stderr)
            return 1 if args.strict else 0
        print("evidence-footprint: within budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
