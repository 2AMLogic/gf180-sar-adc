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

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import yield_evidence as ye  # noqa: E402

HERE = Path(__file__).resolve().parent
MC_DIR = HERE.parent

RECORD_ID = "20260816-125421-737d16e"
NOMINAL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n20000.csv"
NOMINAL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n20000.json"
NEG_CONTROL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n2000_3xsigma.csv"
NEG_CONTROL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n2000_3xsigma.json"

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


def main() -> None:
    nominal_summary = json.loads(NOMINAL_SUMMARY.read_text())
    neg_summary = json.loads(NEG_CONTROL_SUMMARY.read_text())

    negative_control_desc = ye.negative_control_description(
        neg_summary,
        RECORD_ID,
        basis="the as-built value",
        nominal_pct=nominal_summary["sigma_u_pct"],
        suffix=".",
    )

    measurements = []
    limits = {}
    for name, column, limit, _role in MEASUREMENTS:
        measurements.append(ye.measurement(
            name,
            "LSB",
            ye.read_column(NOMINAL_CSV, column),
            negative_control=ye.negative_control(
                ye.read_column(NEG_CONTROL_CSV, column), negative_control_desc,
            ),
        ))
        limits[name] = ye.symmetric_limit(limit)

    ye.write_bundle(
        HERE,
        measurements,
        limits,
        [NOMINAL_CSV, NEG_CONTROL_CSV, NOMINAL_SUMMARY, NEG_CONTROL_SUMMARY],
        rel_to=MC_DIR,
        limit_source=LIMIT_SOURCE,
    )


if __name__ == "__main__":
    main()
