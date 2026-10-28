#!/usr/bin/env python3
"""Build the `klt yield` sample-set + spec-limits documents for the INL/DNL
row of `README.md#target-specification` (line 77, ratified by
`spec/decision-records/DR-0006-spec-ratification.md`), issue #656 (split from
#654, T1 item 6).

Same pattern as `sim/mc-cdac-mismatch/yield-evidence-177/
build_yield_evidence.py` (gain-error row), deliberately a new directory:
`sim/` is append-only. No new simulation is run -- this reads only the
already-committed N=20000 campaign at the as-built `sigma_u = 0.5 %`
(`C_u = 35.6528 fF`) and its 3x-sigma negative control, both from record
`20260816-125421-737d16e`, and emits `mc-samples.json` + `spec-limits.json`
in this directory. The measured quantities are the worst-over-all-codes
`max_dnl_lsb` / `max_inl_lsb` (the quantity the `< 1 LSB` row bounds), not the
code-256 columns the older `yield-evidence/` bundle used.

Usage: `python3 build_yield_evidence.py` (paths resolve relative to this
file). Deterministic and idempotent. Input hashes are printed.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MC_DIR = HERE.parent

RECORD_ID = "20260816-125421-737d16e"
NOMINAL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n20000.csv"
NOMINAL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n20000.json"
NEG_CONTROL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n2000_3xsigma.csv"
NEG_CONTROL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n2000_3xsigma.json"

# 3-sigma two-sided normal yield, the same constant yield-evidence-177 uses.
TARGET_YIELD_3SIGMA = 0.9973002039367398

# Limit source: README.md#target-specification "INL / DNL" row (line 77),
# ratified by DR-0006. Baseline < 1 LSB; stretch < 0.5 LSB (informational).
LIMIT_SOURCE = (
    "README.md#target-specification INL / DNL row (< 1 LSB baseline, "
    "< 0.5 LSB stretch), ratified by "
    "spec/decision-records/DR-0006-spec-ratification.md"
)

# (name, csv column, limit in LSB, role)
MEASUREMENTS = [
    ("max_dnl_lsb_baseline", "max_dnl_lsb", 1.0, "baseline"),
    ("max_inl_lsb_baseline", "max_inl_lsb", 1.0, "baseline"),
    ("max_dnl_lsb_stretch", "max_dnl_lsb", 0.5, "stretch (informational)"),
    ("max_inl_lsb_stretch", "max_inl_lsb", 0.5, "stretch (informational)"),
]


def read_column(path: Path, column: str) -> list[float]:
    with path.open(newline="") as f:
        return [float(row[column]) for row in csv.DictReader(f)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    nominal_summary = json.loads(NOMINAL_SUMMARY.read_text())
    neg_summary = json.loads(NEG_CONTROL_SUMMARY.read_text())

    negative_control_desc = (
        f"CDAC unit-cap mismatch sigma forced to 3x the as-built value "
        f"(sigma_u={neg_summary['sigma_u_pct']:.6f}% vs "
        f"{nominal_summary['sigma_u_pct']:.6f}% nominal), "
        f"N={neg_summary['n_trials']}, seed={neg_summary['seed']} -- same "
        f"behavioral model (mc_cdac_mismatch.py) and methodology as the "
        f"nominal campaign, a real (re-runnable) simulation, not a "
        f"synthetic offset. See runs/{RECORD_ID}/summary_n2000_3xsigma.json."
    )

    measurements = []
    limits = {}
    for name, column, limit, _role in MEASUREMENTS:
        measurements.append({
            "name": name,
            "unit": "LSB",
            "samples": read_column(NOMINAL_CSV, column),
            "errored": 0,
            "negative_control": {
                "samples": read_column(NEG_CONTROL_CSV, column),
                "errored": 0,
                "description": negative_control_desc,
            },
        })
        limits[name] = {
            "min": -limit, "max": limit, "target_yield": TARGET_YIELD_3SIGMA,
        }

    (HERE / "mc-samples.json").write_text(
        json.dumps({"measurements": measurements}, indent=2) + "\n")
    (HERE / "spec-limits.json").write_text(json.dumps({
        "limit_source": LIMIT_SOURCE,
        "target_ci_halfwidth": 0.01,
        "measurements": limits,
    }, indent=2) + "\n")

    print(f"wrote {HERE / 'mc-samples.json'}")
    print(f"wrote {HERE / 'spec-limits.json'}")
    for p in (NOMINAL_CSV, NEG_CONTROL_CSV, NOMINAL_SUMMARY, NEG_CONTROL_SUMMARY):
        print(f"  input sha256 {sha256(p)}  {p.relative_to(MC_DIR)}")


if __name__ == "__main__":
    main()
