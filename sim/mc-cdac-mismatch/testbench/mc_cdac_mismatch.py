#!/usr/bin/env python3
"""Behavioral Monte Carlo of CDAC unit-cap mismatch -> INL/DNL (issue #14).

WHY BEHAVIORAL, NOT TRANSISTOR/DEVICE-LEVEL ngspice. The gf180mcu open PDK
ships no local capacitor mismatch model: ``cap-local-mismatch`` and
``moscap-statistics`` are both ``ABSENT`` findings from
``sim/tools/pdk_mismatch_audit.py`` (recorded in
``sim/device-characterization-report.md`` S5.1). sigma(dC/C) for the unit
cap is therefore not obtainable from this PDK by simulation at all -- an
ngspice Monte Carlo of the CDAC array would report exactly zero mismatch
regardless of trial count, which would be a silent false pass, not a
conservative one. Issue #14 explicitly allows a "behavioral CDAC model
calibrated to extracted unit-cap sigma ... if the calibration is recorded"
for exactly this reason. This script IS that model; the calibration is
below (CALIBRATION) and is cited, not re-derived, from
``spec/cdac-sizing-memo.md``.

WHAT IS SIMULATED. ``spec/cdac-sizing-memo.md`` S0/S3 fixes the topology
this model must match: DR-0011's MCS/Vcm, differential, top-plate-sampling
array. Bit 1 (the free MSB) carries zero mismatch by construction (S3.1 --
it is a sampled-charge sign decision, not a charge-redistribution ratio) and
is NOT modelled here; there is nothing for a mismatch model to do at that
bit. The remaining 9 bits are a ``2^(N-1) = 512``-position sub-array: 511
REAL binary-weighted unit-capacitor positions (weights 256..1, i.e. 256 +
128 + ... + 1 = 511 individual physical unit capacitors grouped into 9
weight classes) plus one terminating dummy (weight 1, fixed to V_cm, never
switched). The dummy's own mismatch is a common term present identically in
the denominator for every code -- a gain error, not a DNL/INL error -- and
is correctly omitted from the switched-code model below (see
_simulate_side).

Each of the 511 real unit capacitors is modelled as an independent random
variable C_i = C_u * (1 + delta_i), delta_i ~ N(0, sigma_u), sigma_u the
Pelgrom-law relative mismatch sigma calibrated in CALIBRATION below. The
model directly evaluates the array's own 512-code transfer function (every
code 0..511, not a reduced/major-carry-only set) each trial, and extracts:

  - DNL/INL at code 256 (the sub-array's own MSB carry) -- the code
    spec/cdac-sizing-memo.md S3.2 derives as the worst-case transition
    for THIS topology (not the plain-binary 2^N array's).
  - The trial's actual argmax|DNL| / argmax|INL| code, empirically, as a
    validity check that code 256 really is the worst case in this
    simulation and not merely assumed from the closed-form derivation --
    the same "measure it, do not take it on faith" discipline
    sim/cdac-bit-settling/ used for its own worst-bit claim.

METHODOLOGY: fit-and-extrapolate, not empirical tail-counting (see
spec/monte-carlo-methodology-memo.md). A run of a few thousand trials
cannot observe a 3-sigma tail event directly (P ~ 1.3e-3 two-sided, so a
few trials would be expected at N ~ 2000 -- not the ~1000-per-tail-event
population a direct count would need to resolve 3-sigma cleanly, let alone
6-sigma). Instead this script (a) simulates enough trials to measure the
DNL(256)/INL(256) population's mean and sigma to good statistical
precision, (b) runs a goodness-of-fit check (Shapiro-Wilk) against the
Gaussian shape the analytical formula assumes, and (c) computes yield at
the target sigma level ANALYTICALLY from the fitted (measured, not
formula-only) sigma, via the normal CDF -- not by counting tail trials.

SEEDING. numpy's ``Generator(PCG64)`` seeded with a single fixed integer,
recorded in the evidence record and reproducible by re-running this script
with the same ``--seed``. This is a fresh, independent RNG stream from any
ngspice ``setseed`` used elsewhere in ``sim/`` -- there is no shared-state
hazard because this script never invokes ngspice.

Usage:
    python3 mc_cdac_mismatch.py --sigma-u 0.7372 --trials 2000 --seed 20260801 \\
        --out-csv <path/trials.csv> --out-json <path/summary.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# CALIBRATION -- cited, not re-derived, from spec/cdac-sizing-memo.md.
#
#   A_C = 2.0 %*um       Pelgrom area coefficient, 2x-derated
#                        (sim/device-characterization-report.md S5.1,
#                        `literature-assumption-with-derating`).
#   A_unit (chosen)      7.36 um^2 -- the ACTUAL chosen unit cap
#                        (C_u = 17.24 fF, 2.71 um square,
#                        spec/cdac-sizing-memo.md S4), sized to the
#                        stretch (< 0.5 LSB) target.
#   A_unit (baseline)    1.839 um^2 -- the SMALLER unit cap that would
#                        suffice for the baseline (< 1 LSB) target alone
#                        (S4); reported only for comparison, since #8 did
#                        NOT choose this geometry.
#
# sigma_u = A_C / sqrt(A_unit), the same Pelgrom law S2/S4 use.
# ---------------------------------------------------------------------------
A_C_PCT_UM = 2.0
A_UNIT_CHOSEN_UM2 = 7.36        # spec/cdac-sizing-memo.md S4, chosen design
A_UNIT_BASELINE_UM2 = 1.839     # spec/cdac-sizing-memo.md S4, comparison only

SIGMA_U_CHOSEN_PCT = A_C_PCT_UM / np.sqrt(A_UNIT_CHOSEN_UM2)
SIGMA_U_BASELINE_PCT = A_C_PCT_UM / np.sqrt(A_UNIT_BASELINE_UM2)

# Analytical closed-form coefficients this array topology derives
# (spec/cdac-sizing-memo.md S3.2), for the cross-check against direct
# simulation -- NOT used to compute the reported sigma, only to confirm the
# direct Monte Carlo agrees with the memo's algebra:
ANALYTIC_DNL_COEFF = np.sqrt(511.0)          # ~= 22.61
ANALYTIC_INL_COEFF = np.sqrt(512.0) / 2.0    # ~= 11.31

# Yield criterion consumed from #8 (spec/cdac-sizing-memo.md S3.3): 3-sigma,
# not independently chosen here.
YIELD_SIGMA = 3.0

# Ratified/aspirational spec lines this record tests against (consumed, not
# chosen): README.md#target-specification, < 1 LSB baseline / < 0.5 LSB
# stretch, untrimmed, at the 3-sigma criterion above.
SPEC_BASELINE_LSB = 1.0
SPEC_STRETCH_LSB = 0.5

# Sub-array group sizes: weight 2^k has 2^k physical unit capacitors,
# k = 0..8 (weights 1, 2, 4, ..., 256). Sum = 511.
GROUP_SIZES = [2**k for k in range(9)]
assert sum(GROUP_SIZES) == 511
N_CODES = 512  # codes 0..511, the sub-array's own 9-bit range
MSB_CODE = 256  # the sub-array's own MSB carry -- spec/cdac-sizing-memo.md S3.2


def _bits_matrix() -> np.ndarray:
    """(N_CODES, 9) matrix: column k is bit k (weight 2**k) of each code."""
    codes = np.arange(N_CODES)
    return ((codes[:, None] >> np.arange(9)[None, :]) & 1).astype(np.float64)


def simulate(sigma_u_pct: float, n_trials: int, seed: int) -> dict:
    """Run the Monte Carlo and return raw per-trial arrays + summary stats."""
    sigma_u = sigma_u_pct / 100.0
    rng = np.random.default_rng(seed)
    bits = _bits_matrix()  # (512, 9)
    codes = np.arange(N_CODES, dtype=np.float64)

    # Per-trial, per-group capacitor-mismatch sum: draw every one of the 511
    # PHYSICAL unit capacitors independently (not a shortcut group-level
    # draw), then sum within each weight group -- literally what the array
    # is built from.
    group_sum = np.empty((n_trials, 9))
    for k, size in enumerate(GROUP_SIZES):
        draws = rng.normal(0.0, sigma_u, size=(n_trials, size))
        group_sum[:, k] = draws.sum(axis=1)

    weights = np.array(GROUP_SIZES, dtype=np.float64)  # [1,2,4,...,256]
    actual = weights[None, :] + group_sum  # (n_trials, 9), actual group totals in C_u units

    # V[c] for every code, every trial: (n_trials, 512)
    V = actual @ bits.T
    V0 = V[:, 0]  # exactly 0 by construction (code 0 switches nothing)
    V_total = V[:, -1]  # code 511, everything on

    # INL(c) = [V(c)-V(0)] - c/511*[V(511)-V(0)], end-point-corrected per
    # the standard convention (removes the array's own total-capacitance
    # gain error from the linearity figure).
    INL = V - V0[:, None] - (codes[None, :] / (N_CODES - 1)) * (V_total - V0)[:, None]

    # DNL(c) = [V(c)-V(c-1)] - 1, for c = 1..511 (511 transitions).
    DNL = np.diff(V, axis=1) - 1.0  # (n_trials, 511); DNL[:, c-1] is code c

    dnl_at_256 = DNL[:, MSB_CODE - 1]  # transition INTO code 256
    inl_at_256 = INL[:, MSB_CODE]

    argmax_dnl_idx = np.argmax(np.abs(DNL), axis=1)  # 0-based -> code = idx+1
    argmax_dnl_code = argmax_dnl_idx + 1
    argmax_inl_code = np.argmax(np.abs(INL), axis=1)

    max_dnl = DNL[np.arange(n_trials), argmax_dnl_idx]
    max_inl = INL[np.arange(n_trials), argmax_inl_code]

    return {
        "sigma_u_pct": sigma_u_pct,
        "n_trials": n_trials,
        "seed": seed,
        "dnl_at_256": dnl_at_256,
        "inl_at_256": inl_at_256,
        "max_dnl": max_dnl,
        "max_inl": max_inl,
        "argmax_dnl_code": argmax_dnl_code,
        "argmax_inl_code": argmax_inl_code,
    }


def _gof(sample: np.ndarray) -> dict:
    """Shapiro-Wilk normality check + fitted-Gaussian yield inputs."""
    w_stat, p_value = stats.shapiro(sample)
    mu = float(np.mean(sample))
    sigma = float(np.std(sample, ddof=1))
    return {"shapiro_w": float(w_stat), "shapiro_p": float(p_value), "mean": mu, "sigma": sigma}


def yield_at_sigma_target(sigma_measured: float, spec_lsb: float, target_sigma: float) -> dict:
    """Analytic yield from the fitted Gaussian, evaluated at the target sigma.

    Two numbers are reported, deliberately: (1) whether the design's OWN
    stated criterion is met -- target_sigma * sigma_measured < spec_lsb,
    which is spec/cdac-sizing-memo.md S3.3's actual pass/fail rule -- and
    (2) the corresponding two-sided yield fraction the normal CDF gives at
    that ratio, for a probabilistic reading of the same result.
    """
    ratio = spec_lsb / sigma_measured if sigma_measured > 0 else float("inf")
    met = ratio >= target_sigma
    yield_frac = 2 * stats.norm.cdf(ratio) - 1  # P(|X| < spec_lsb), X ~ N(0, sigma_measured)
    return {
        "spec_lsb": spec_lsb,
        "sigma_measured": sigma_measured,
        "sigma_at_spec": ratio,
        "meets_target_sigma": bool(met),
        "yield_fraction": float(yield_frac),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sigma-u", type=float, default=SIGMA_U_CHOSEN_PCT,
                   help="unit-cap relative mismatch sigma, percent (default: calibrated chosen-design value)")
    p.add_argument("--trials", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260801)
    p.add_argument("--out-csv", type=Path, default=None, help="write per-trial raw samples")
    p.add_argument("--out-json", type=Path, default=None, help="write summary statistics")
    args = p.parse_args(argv)

    result = simulate(args.sigma_u, args.trials, args.seed)

    gof_dnl = _gof(result["dnl_at_256"])
    gof_inl = _gof(result["inl_at_256"])
    # Secondary GOF on the trial's TRUE max-over-all-codes statistic. This is
    # a maximum of many correlated, near-degenerate-variance Gaussians (the
    # variance profile Var(DNL(c)) / Var(INL(c)) is sharply / smoothly peaked
    # near c=256, so several codes compete for "worst" in any one trial --
    # see frac_trials_worst_*_at_code256 below) and is therefore an
    # order-statistic / extreme-value-type quantity, NOT itself Gaussian.
    # Shapiro-Wilk is expected, and required by this issue's edge-case
    # acceptance criterion, to FLAG that deviation rather than silently
    # extrapolate a Gaussian tail through it.
    gof_max_dnl = _gof(result["max_dnl"])
    gof_max_inl = _gof(result["max_inl"])

    frac_dnl_at_256 = float(np.mean(result["argmax_dnl_code"] == MSB_CODE))
    frac_inl_at_256 = float(np.mean(result["argmax_inl_code"] == MSB_CODE))

    analytic_sigma_dnl = ANALYTIC_DNL_COEFF * args.sigma_u / 100.0
    analytic_sigma_inl = ANALYTIC_INL_COEFF * args.sigma_u / 100.0

    yield_dnl_baseline = yield_at_sigma_target(gof_dnl["sigma"], SPEC_BASELINE_LSB, YIELD_SIGMA)
    yield_dnl_stretch = yield_at_sigma_target(gof_dnl["sigma"], SPEC_STRETCH_LSB, YIELD_SIGMA)
    yield_inl_baseline = yield_at_sigma_target(gof_inl["sigma"], SPEC_BASELINE_LSB, YIELD_SIGMA)
    yield_inl_stretch = yield_at_sigma_target(gof_inl["sigma"], SPEC_STRETCH_LSB, YIELD_SIGMA)

    summary = {
        "sigma_u_pct": args.sigma_u,
        "n_trials": args.trials,
        "seed": args.seed,
        "analytic_sigma_dnl_lsb": analytic_sigma_dnl,
        "analytic_sigma_inl_lsb": analytic_sigma_inl,
        "measured_sigma_dnl_at_256_lsb": gof_dnl["sigma"],
        "measured_sigma_inl_at_256_lsb": gof_inl["sigma"],
        "measured_mean_dnl_at_256_lsb": gof_dnl["mean"],
        "measured_mean_inl_at_256_lsb": gof_inl["mean"],
        "dnl_sigma_ratio_measured_over_analytic": gof_dnl["sigma"] / analytic_sigma_dnl,
        "inl_sigma_ratio_measured_over_analytic": gof_inl["sigma"] / analytic_sigma_inl,
        "gof_dnl_shapiro_w": gof_dnl["shapiro_w"],
        "gof_dnl_shapiro_p": gof_dnl["shapiro_p"],
        "gof_inl_shapiro_w": gof_inl["shapiro_w"],
        "gof_inl_shapiro_p": gof_inl["shapiro_p"],
        "frac_trials_worst_dnl_at_code256": frac_dnl_at_256,
        "frac_trials_worst_inl_at_code256": frac_inl_at_256,
        "yield_dnl_baseline_1p0_lsb": yield_dnl_baseline,
        "yield_dnl_stretch_0p5_lsb": yield_dnl_stretch,
        "yield_inl_baseline_1p0_lsb": yield_inl_baseline,
        "yield_inl_stretch_0p5_lsb": yield_inl_stretch,
        "max_dnl_over_codes_mean": float(np.mean(result["max_dnl"])),
        "max_dnl_over_codes_sigma": float(np.std(result["max_dnl"], ddof=1)),
        "max_inl_over_codes_mean": float(np.mean(result["max_inl"])),
        "max_inl_over_codes_sigma": float(np.std(result["max_inl"], ddof=1)),
        "gof_max_dnl_shapiro_w": gof_max_dnl["shapiro_w"],
        "gof_max_dnl_shapiro_p": gof_max_dnl["shapiro_p"],
        "gof_max_inl_shapiro_w": gof_max_inl["shapiro_w"],
        "gof_max_inl_shapiro_p": gof_max_inl["shapiro_p"],
        "max_dnl_empirical_3sigma_lsb": 3.0 * float(np.std(result["max_dnl"], ddof=1)),
        "max_inl_empirical_3sigma_lsb": 3.0 * float(np.std(result["max_inl"], ddof=1)),
        "max_dnl_empirical_worst_abs_lsb": float(np.max(np.abs(result["max_dnl"]))),
        "max_inl_empirical_worst_abs_lsb": float(np.max(np.abs(result["max_inl"]))),
    }

    print(json.dumps(summary, indent=2))

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(summary, indent=2) + "\n")

    if args.out_csv:
        args.out_csv.parent.mkdir(parents=True, exist_ok=True)
        import csv
        with args.out_csv.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "trial", "dnl_at_256_lsb", "inl_at_256_lsb",
                "max_dnl_lsb", "argmax_dnl_code", "max_inl_lsb", "argmax_inl_code",
            ])
            for i in range(args.trials):
                writer.writerow([
                    i,
                    result["dnl_at_256"][i],
                    result["inl_at_256"][i],
                    result["max_dnl"][i],
                    result["argmax_dnl_code"][i],
                    result["max_inl"][i],
                    result["argmax_inl_code"][i],
                ])

    return 0


if __name__ == "__main__":
    sys.exit(main())
