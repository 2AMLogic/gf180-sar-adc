#!/usr/bin/env python3
"""Build the `klt yield` sample-set + spec-limits documents for the CDAC
mismatch campaign's DNL/INL rows (2AMLogic/klayout-tools#818, Phase 1c of
epic #710) and Gain-error row (README.md#target-specification line 50, issue
#172, T1 item 6).

This is a pure reformatting step -- it invents no numbers. It reads real,
already-committed artifacts this experiment produced:

  - the nominal N=20000 campaign
    (`sim/mc-cdac-mismatch/runs/20260816-044942-56fbe50/trials_n20000.csv`,
    record `sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`), which
    re-derives the original committed campaign
    (`sim/mc-cdac-mismatch/records/20260801-093800-c033611.md`) bit-for-bit
    on its `dnl_at_256_lsb`/`inl_at_256_lsb`/`max_dnl_lsb`/`max_inl_lsb`
    columns (see that record's "Reproducibility check") while adding one new
    emitted column (`gain_error_lsb`) the original CSV does not carry -- used
    for all five measurements' nominal samples;
  - the DNL/INL rows' own negative-control run, at 3x the calibrated
    unit-cap mismatch sigma (`sigma_u = 3 * 0.7372097807744856 % =
    2.211629342323457 %`), N=2000, seed=99109901
    (`sim/mc-cdac-mismatch/runs/20260812-132011-f613571/trials_n2000_3xsigma.csv`,
    record `sim/mc-cdac-mismatch/records/20260812-132011-f613571.md` -- *this*
    record's own negative control, not borrowed from the gain-error one below
    even though both share the same `sigma_u`/seed and are numerically
    identical on the DNL/INL columns);
  - the gain-error row's own negative-control run, same methodology and
    `sigma_u`/seed, run separately for the `gain_error_lsb` column the
    DNL/INL run does not carry
    (`sim/mc-cdac-mismatch/runs/20260816-044942-56fbe50/trials_n2000_3xsigma.csv`,
    the same `56fbe50` record above -- see its "Negative control" bullet:
    "run fresh here for the gain-error column").

and emits `mc-samples.json` (five measurements: DNL/INL x baseline/stretch
plus gain-error-mismatch, each carrying its own real samples, a real
negative_control block built from the appropriate run above, and a real
analytic_cross_check built from this experiment's own closed-form
Pelgrom-derived / 1/sqrt(1024) total-array sigma formulas -- the same
`analytic_sigma_dnl_lsb`/`analytic_sigma_inl_lsb`/`analytic_sigma_gain_lsb`
values `mc_cdac_mismatch.py` already computes and the record's own "Result"
table already cites) and `spec-limits.json` (the ratified README.md spec
window: `< 1 LSB` baseline / `< 0.5 LSB` stretch for DNL/INL,
`<= 0.5 LSB` with no stretch line for gain-error per DR-0012, all read as a
3-sigma criterion per `spec/cdac-sizing-memo.md` SS3.1-3.3).

Usage: `python3 build_yield_evidence.py` from this directory (or anywhere;
paths are resolved relative to this file). Deterministic and idempotent --
re-running overwrites `mc-samples.json`/`spec-limits.json` in place (they are
derived views, not evidence themselves; the append-only rule governs the
underlying `runs/`/`records/` inputs, not this derived reformatting -- see
`sim/README.md`'s "Comparing two records" precedent for `postlayout_delta.py`,
which is the same kind of regenerate-don't-edit view).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MC_DIR = HERE.parent

RECORD_ID = "20260816-044942-56fbe50"
NOMINAL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n20000.csv"

# DNL/INL negative control: this record's own run (record 20260812-132011-f613571).
DNL_INL_NEG_CONTROL_RECORD_ID = "20260812-132011-f613571"
DNL_INL_NEG_CONTROL_CSV = (
    MC_DIR / "runs" / DNL_INL_NEG_CONTROL_RECORD_ID / "trials_n2000_3xsigma.csv"
)
DNL_INL_NEG_CONTROL_SUMMARY = (
    MC_DIR / "runs" / DNL_INL_NEG_CONTROL_RECORD_ID / "summary_n2000_3xsigma.json"
)

# Gain-error negative control: run fresh under record 20260816-044942-56fbe50
# (its own `gain_error_lsb` column; the DNL/INL run above does not carry it).
GAIN_NEG_CONTROL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n2000_3xsigma.csv"
GAIN_NEG_CONTROL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n2000_3xsigma.json"

# Analytic (closed-form) sigma predictions at the CHOSEN design's calibrated
# sigma_u -- read directly from the nominal re-derivation's own summary JSON
# (`sim/mc-cdac-mismatch/runs/20260816-044942-56fbe50/summary_n20000.json`),
# not re-derived here.
ANALYTIC_SIGMA_DNL_LSB = 0.16664854973996857
ANALYTIC_SIGMA_INL_LSB = 0.0834057656228299
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
    dnl_samples = read_column(NOMINAL_CSV, "dnl_at_256_lsb")
    inl_samples = read_column(NOMINAL_CSV, "inl_at_256_lsb")
    gain_samples = read_column(NOMINAL_CSV, "gain_error_lsb")
    dnl_neg = read_column(DNL_INL_NEG_CONTROL_CSV, "dnl_at_256_lsb")
    inl_neg = read_column(DNL_INL_NEG_CONTROL_CSV, "inl_at_256_lsb")
    gain_neg = read_column(GAIN_NEG_CONTROL_CSV, "gain_error_lsb")

    def neg_control_desc(summary_path, record_id):
        summary = json.loads(summary_path.read_text())
        return (
            f"CDAC unit-cap mismatch sigma forced to 3x the chosen design's "
            f"calibrated value (sigma_u={summary['sigma_u_pct']:.6f}% vs "
            f"0.7372097807744856% nominal), N={summary['n_trials']}, "
            f"seed={summary['seed']} -- same behavioral model "
            f"(mc_cdac_mismatch.py) and methodology as the nominal campaign, a "
            f"real (re-runnable) simulation, not a synthetic offset. See "
            f"runs/{record_id}/summary_n2000_3xsigma.json for full provenance."
        )

    dnl_inl_neg_control_desc = neg_control_desc(
        DNL_INL_NEG_CONTROL_SUMMARY, DNL_INL_NEG_CONTROL_RECORD_ID
    )
    gain_neg_control_desc = neg_control_desc(GAIN_NEG_CONTROL_SUMMARY, RECORD_ID)

    def measurement(name, unit, samples, neg_samples, neg_desc, analytic_sigma):
        return {
            "name": name,
            "unit": unit,
            "samples": samples,
            "errored": 0,
            "negative_control": {
                "samples": neg_samples,
                "errored": 0,
                "description": neg_desc,
            },
            "analytic_cross_check": {
                "kind": "mismatch_offset",
                "sigma": analytic_sigma,
                "mean": 0.0,
            },
        }

    doc = {
        "measurements": [
            measurement(
                "dnl_at_256_lsb_baseline", "LSB", dnl_samples, dnl_neg,
                dnl_inl_neg_control_desc, ANALYTIC_SIGMA_DNL_LSB,
            ),
            measurement(
                "dnl_at_256_lsb_stretch", "LSB", dnl_samples, dnl_neg,
                dnl_inl_neg_control_desc, ANALYTIC_SIGMA_DNL_LSB,
            ),
            measurement(
                "inl_at_256_lsb_baseline", "LSB", inl_samples, inl_neg,
                dnl_inl_neg_control_desc, ANALYTIC_SIGMA_INL_LSB,
            ),
            measurement(
                "inl_at_256_lsb_stretch", "LSB", inl_samples, inl_neg,
                dnl_inl_neg_control_desc, ANALYTIC_SIGMA_INL_LSB,
            ),
            measurement(
                "gain_error_mismatch_lsb", "LSB", gain_samples, gain_neg,
                gain_neg_control_desc, ANALYTIC_SIGMA_GAIN_LSB,
            ),
        ]
    }

    (HERE / "mc-samples.json").write_text(json.dumps(doc, indent=2) + "\n")

    # spec-limits.json -- the ratified README.md#target-specification window
    # (DNL/INL: < 1 LSB baseline / < 0.5 LSB stretch; gain-error: <= 0.5 LSB,
    # no stretch line -- DR-0012 clarifies the value "equals, to the
    # rounding, the single mechanism it names", i.e. there is no separate
    # baseline/stretch split as there is for INL/DNL), read as this
    # experiment's own 3-sigma pass criterion (spec/cdac-sizing-memo.md
    # SS3.1-3.3), kept separate from the raw samples so the caller's
    # explicit spec statement is its own reviewable artifact -- matching
    # docs/cli/yield.md's own `mc-samples.json` + `spec-limits.json`
    # worked example.
    limits_doc = {
        "target_ci_halfwidth": 0.01,
        "measurements": {
            "dnl_at_256_lsb_baseline": {
                "min": -1.0, "max": 1.0, "target_yield": TARGET_YIELD_3SIGMA,
            },
            "dnl_at_256_lsb_stretch": {
                "min": -0.5, "max": 0.5, "target_yield": TARGET_YIELD_3SIGMA,
            },
            "inl_at_256_lsb_baseline": {
                "min": -1.0, "max": 1.0, "target_yield": TARGET_YIELD_3SIGMA,
            },
            "inl_at_256_lsb_stretch": {
                "min": -0.5, "max": 0.5, "target_yield": TARGET_YIELD_3SIGMA,
            },
            "gain_error_mismatch_lsb": {
                "min": -0.5, "max": 0.5, "target_yield": TARGET_YIELD_3SIGMA,
            },
        },
    }
    (HERE / "spec-limits.json").write_text(json.dumps(limits_doc, indent=2) + "\n")

    print(f"wrote {HERE / 'mc-samples.json'}")
    print(f"wrote {HERE / 'spec-limits.json'}")
    print(f"  dnl samples: {len(dnl_samples)}  inl samples: {len(inl_samples)}"
          f"  gain-error samples: {len(gain_samples)}")
    print(f"  negative-control samples: {len(dnl_neg)}")


if __name__ == "__main__":
    main()
