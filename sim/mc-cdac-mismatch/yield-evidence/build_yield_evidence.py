#!/usr/bin/env python3
"""Build the `klt yield` sample-set + spec-limits documents for the CDAC
mismatch campaign's DNL/INL rows (2AMLogic/klayout-tools#818, Phase 1c of
epic #710) and Gain-error row (README.md#target-specification line 50, issue
#172, T1 item 6).

This is a pure reformatting step -- it invents no numbers. It reads real,
already-committed artifacts this experiment produced:

  - the DNL/INL rows' nominal N=20000 campaign and negative control, both
    at the **DR-0019-resized** unit cap (`sigma_u = 0.5000 %`, `C_u =
    35.6528 fF` -- `spec/decision-records/
    DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`), from record
    `sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`:
    `sim/mc-cdac-mismatch/runs/20260816-125421-737d16e/trials_n20000.csv`
    (nominal) and `.../trials_n2000_3xsigma.csv` (negative control, `sigma_u
    = 3 * 0.5000 % = 1.5000 %`, N=2000, seed=99109901). This PR originally
    re-derived the pre-resize campaign (`sigma_u = 0.7372097807744856 %`,
    with its own negative-control run under
    `sim/mc-cdac-mismatch/runs/20260812-132011-f613571/`); it was repointed
    at the resized data once DR-0019 landed on `main` so this evidence
    certifies the design that is actually ratified, not a superseded
    geometry -- see `sim/mc-cdac-mismatch/records/20260812-132011-f613571.md`
    for the updated claim. This record now reuses record `737d16e`'s
    nominal and negative-control runs entirely (both already exist on
    `main`) rather than running its own; the PR's original
    `runs/20260812-132011-f613571/` negative-control CSV/JSON, calibrated to
    the now-superseded pre-resize `sigma_u`, is removed rather than left
    committed-but-unread;
  - the gain-error row's nominal N=20000 campaign and its own
    negative-control run, unchanged from the already-merged #182
    (`sim/mc-cdac-mismatch/runs/20260816-044942-56fbe50/trials_n20000.csv`
    and `.../trials_n2000_3xsigma.csv`, record
    `sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md` -- still the
    pre-resize `sigma_u = 0.7372097807744856 %`; re-deriving that row
    against the resized design is out of this PR's scope).

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

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import yield_evidence as ye  # noqa: E402

HERE = Path(__file__).resolve().parent
MC_DIR = HERE.parent

# DNL/INL: DR-0019-resized design (sigma_u = 0.5000%, C_u = 35.6528 fF),
# record 20260816-125421-737d16e -- both nominal and negative control are
# this record's own run.
DNL_INL_RECORD_ID = "20260816-125421-737d16e"
DNL_INL_NOMINAL_CSV = MC_DIR / "runs" / DNL_INL_RECORD_ID / "trials_n20000.csv"
DNL_INL_NEG_CONTROL_CSV = (
    MC_DIR / "runs" / DNL_INL_RECORD_ID / "trials_n2000_3xsigma.csv"
)
DNL_INL_NEG_CONTROL_SUMMARY = (
    MC_DIR / "runs" / DNL_INL_RECORD_ID / "summary_n2000_3xsigma.json"
)

# Gain-error: pre-resize design (sigma_u = 0.7372097807744856%), record
# 20260816-044942-56fbe50, unchanged from the already-merged #182 -- out of
# this PR's scope to re-derive against the resized design.
GAIN_RECORD_ID = "20260816-044942-56fbe50"
GAIN_NOMINAL_CSV = MC_DIR / "runs" / GAIN_RECORD_ID / "trials_n20000.csv"
GAIN_NEG_CONTROL_CSV = MC_DIR / "runs" / GAIN_RECORD_ID / "trials_n2000_3xsigma.csv"
GAIN_NEG_CONTROL_SUMMARY = MC_DIR / "runs" / GAIN_RECORD_ID / "summary_n2000_3xsigma.json"

# Analytic (closed-form) sigma predictions at each row's own calibrated
# sigma_u -- read directly from the nominal campaign's own summary JSON
# (`.../summary_n20000.json`), not re-derived here.
ANALYTIC_SIGMA_DNL_LSB = 0.11302654555457314
ANALYTIC_SIGMA_INL_LSB = 0.0565685424949238
ANALYTIC_SIGMA_GAIN_LSB = 0.2359071298478354

# Each row's nominal sigma_u as the record cites it, stated literally rather
# than re-read from the nominal summary JSON (which this script does not
# open) -- the DNL/INL rows at the DR-0019-resized value, the gain-error row
# still at the pre-resize value.
DNL_INL_NOMINAL_PCT = "0.5000"
GAIN_NOMINAL_PCT = "0.7372097807744856"


def main() -> None:
    dnl_samples = ye.read_column(DNL_INL_NOMINAL_CSV, "dnl_at_256_lsb")
    inl_samples = ye.read_column(DNL_INL_NOMINAL_CSV, "inl_at_256_lsb")
    gain_samples = ye.read_column(GAIN_NOMINAL_CSV, "gain_error_lsb")
    dnl_neg = ye.read_column(DNL_INL_NEG_CONTROL_CSV, "dnl_at_256_lsb")
    inl_neg = ye.read_column(DNL_INL_NEG_CONTROL_CSV, "inl_at_256_lsb")
    gain_neg = ye.read_column(GAIN_NEG_CONTROL_CSV, "gain_error_lsb")

    def neg_control_desc(summary_path, record_id, nominal_pct):
        return ye.negative_control_description(
            json.loads(summary_path.read_text()),
            record_id,
            basis="the chosen design's calibrated value",
            nominal_pct=nominal_pct,
        )

    dnl_inl_neg_control_desc = neg_control_desc(
        DNL_INL_NEG_CONTROL_SUMMARY, DNL_INL_RECORD_ID, DNL_INL_NOMINAL_PCT
    )
    gain_neg_control_desc = neg_control_desc(
        GAIN_NEG_CONTROL_SUMMARY, GAIN_RECORD_ID, GAIN_NOMINAL_PCT
    )

    def mismatch_measurement(name, samples, neg_samples, neg_desc, analytic_sigma):
        return ye.measurement(
            name,
            "LSB",
            samples,
            negative_control=ye.negative_control(neg_samples, neg_desc),
            analytic_cross_check=ye.analytic_cross_check(analytic_sigma),
        )

    measurements = [
        mismatch_measurement(
            "dnl_at_256_lsb_baseline", dnl_samples, dnl_neg,
            dnl_inl_neg_control_desc, ANALYTIC_SIGMA_DNL_LSB,
        ),
        mismatch_measurement(
            "dnl_at_256_lsb_stretch", dnl_samples, dnl_neg,
            dnl_inl_neg_control_desc, ANALYTIC_SIGMA_DNL_LSB,
        ),
        mismatch_measurement(
            "inl_at_256_lsb_baseline", inl_samples, inl_neg,
            dnl_inl_neg_control_desc, ANALYTIC_SIGMA_INL_LSB,
        ),
        mismatch_measurement(
            "inl_at_256_lsb_stretch", inl_samples, inl_neg,
            dnl_inl_neg_control_desc, ANALYTIC_SIGMA_INL_LSB,
        ),
        mismatch_measurement(
            "gain_error_mismatch_lsb", gain_samples, gain_neg,
            gain_neg_control_desc, ANALYTIC_SIGMA_GAIN_LSB,
        ),
    ]

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
    limits = {
        "dnl_at_256_lsb_baseline": ye.symmetric_limit(1.0),
        "dnl_at_256_lsb_stretch": ye.symmetric_limit(0.5),
        "inl_at_256_lsb_baseline": ye.symmetric_limit(1.0),
        "inl_at_256_lsb_stretch": ye.symmetric_limit(0.5),
        "gain_error_mismatch_lsb": ye.symmetric_limit(0.5),
    }

    ye.write_bundle(
        HERE,
        measurements,
        limits,
        [
            DNL_INL_NOMINAL_CSV,
            DNL_INL_NEG_CONTROL_CSV,
            DNL_INL_NEG_CONTROL_SUMMARY,
            GAIN_NOMINAL_CSV,
            GAIN_NEG_CONTROL_CSV,
            GAIN_NEG_CONTROL_SUMMARY,
        ],
        rel_to=MC_DIR,
    )
    print(f"  dnl samples: {len(dnl_samples)}  inl samples: {len(inl_samples)}"
          f"  gain-error samples: {len(gain_samples)}")
    print(f"  negative-control samples: {len(dnl_neg)}")


if __name__ == "__main__":
    main()
