#!/usr/bin/env python3
"""Build the `klt yield` sample-set + spec-limits documents for the CDAC
Gain error, mismatch row (README.md#target-specification line 50, issue
#172, T1 item 6).

This is a pure reformatting step -- it invents no numbers. It reads two
real, already-committed artifacts this experiment produced:

  - a re-derivation of the nominal N=20000 campaign
    (`sim/mc-cdac-mismatch/records/20260801-093800-c033611.md`'s own seed
    and calibrated `sigma_u`), extended with one new emitted column
    (`gain_error_lsb`) that the original committed CSV does not carry --
    `mc_cdac_mismatch.py` was extended to compute it (see that script's
    module docstring and the `simulate()` gain-error block), and the
    re-derivation was verified bit-for-bit identical to the original
    committed `dnl_at_256_lsb`/`inl_at_256_lsb`/`max_dnl_lsb`/`max_inl_lsb`
    columns before being trusted (see
    `sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`'s
    "Reproducibility check");
  - a new, deliberately-degraded negative-control run at 3x the calibrated
    unit-cap mismatch sigma (`sigma_u = 3 * 0.7372097807744856 % =
    2.211629342323457 %`), N=2000, seed=99109901 -- the exact same
    methodology PR #149 used for the DNL/INL negative control, run fresh
    here for the gain-error column specifically. See
    `sim/mc-cdac-mismatch/runs/20260816-044942-56fbe50/summary_n2000_3xsigma.json`
    for the full provenance of that run.

and emits `mc-samples.json` (one measurement: `gain_error_mismatch_lsb`,
carrying its own real samples, a real negative_control block built from the
3x-sigma run above, and a real analytic_cross_check built from this
experiment's own closed-form 1/sqrt(1024) total-array formula -- the same
`analytic_sigma_gain_lsb` value `mc_cdac_mismatch.py` already computes) and
`spec-limits.json` (the ratified README.md spec window, `<= 0.5 LSB`, no
stretch line for this row, read as a 3-sigma criterion per
`spec/cdac-sizing-memo.md` S3.3's adopted convention).

Usage: `python3 build_yield_evidence.py` from this directory (or anywhere;
paths are resolved relative to this file). Deterministic and idempotent --
re-running overwrites `mc-samples.json`/`spec-limits.json` in place (they are
derived views, not evidence themselves; the append-only rule governs the
underlying `runs/`/`records/` inputs, not this derived reformatting -- see
`sim/README.md`'s "Comparing two records" precedent, and PR #149's own
`build_yield_evidence.py` for the INL/DNL row, whose pattern this extends).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MC_DIR = HERE.parent

RECORD_ID = "20260816-044942-56fbe50"
NOMINAL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n20000.csv"
NEG_CONTROL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n2000_3xsigma.csv"
NEG_CONTROL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n2000_3xsigma.json"

# Analytic (closed-form) sigma prediction at the CHOSEN design's calibrated
# sigma_u -- read directly from the nominal re-derivation's own summary JSON
# (`sim/mc-cdac-mismatch/runs/20260816-044942-56fbe50/summary_n20000.json`),
# not re-derived here.
ANALYTIC_SIGMA_GAIN_LSB = 0.2359071298478354

# 3-sigma two-sided normal yield -- the "3 sigma" pass criterion
# `spec/cdac-sizing-memo.md` SS3.1-3.3 states, expressed as a target_yield
# fraction the way `klt yield --limits` wants it.
TARGET_YIELD_3SIGMA = 0.9973002039367398


def read_column(path: Path, column: str) -> list[float]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [float(row[column]) for row in reader]


def main() -> None:
    gain_samples = read_column(NOMINAL_CSV, "gain_error_lsb")
    gain_neg = read_column(NEG_CONTROL_CSV, "gain_error_lsb")

    neg_summary = json.loads(NEG_CONTROL_SUMMARY.read_text())
    neg_sigma_u = neg_summary["sigma_u_pct"]
    neg_n = neg_summary["n_trials"]
    neg_seed = neg_summary["seed"]

    negative_control_desc = (
        f"CDAC unit-cap mismatch sigma forced to 3x the chosen design's "
        f"calibrated value (sigma_u={neg_sigma_u:.6f}% vs 0.7372097807744856% "
        f"nominal), N={neg_n}, seed={neg_seed} -- same behavioral model "
        f"(mc_cdac_mismatch.py) and methodology as the nominal campaign, a "
        f"real (re-runnable) simulation, not a synthetic offset. See "
        f"runs/{RECORD_ID}/summary_n2000_3xsigma.json for full provenance."
    )

    doc = {
        "measurements": [
            {
                "name": "gain_error_mismatch_lsb",
                "unit": "LSB",
                "samples": gain_samples,
                "errored": 0,
                "negative_control": {
                    "samples": gain_neg,
                    "errored": 0,
                    "description": negative_control_desc,
                },
                "analytic_cross_check": {
                    "kind": "mismatch_offset",
                    "sigma": ANALYTIC_SIGMA_GAIN_LSB,
                    "mean": 0.0,
                },
            },
        ]
    }

    (HERE / "mc-samples.json").write_text(json.dumps(doc, indent=2) + "\n")

    # spec-limits.json -- the ratified README.md#target-specification window
    # (<= 0.5 LSB, no stretch line for this row -- DR-0012 clarifies the
    # value "equals, to the rounding, the single mechanism it names", i.e.
    # there is no separate baseline/stretch split as there is for INL/DNL),
    # read as this experiment's own 3-sigma pass criterion
    # (spec/cdac-sizing-memo.md SS3.1-3.3), kept separate from the raw
    # samples so the caller's explicit spec statement is its own reviewable
    # artifact -- matching docs/cli/yield.md's own `mc-samples.json` +
    # `spec-limits.json` worked example, and PR #149's identical split for
    # the DNL/INL rows.
    limits_doc = {
        "target_ci_halfwidth": 0.01,
        "measurements": {
            "gain_error_mismatch_lsb": {
                "min": -0.5, "max": 0.5, "target_yield": TARGET_YIELD_3SIGMA,
            },
        },
    }
    (HERE / "spec-limits.json").write_text(json.dumps(limits_doc, indent=2) + "\n")

    print(f"wrote {HERE / 'mc-samples.json'}")
    print(f"wrote {HERE / 'spec-limits.json'}")
    print(f"  gain-error samples: {len(gain_samples)}")
    print(f"  negative-control samples: {len(gain_neg)}")


if __name__ == "__main__":
    main()
