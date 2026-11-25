#!/usr/bin/env python3
"""Sample-size / confidence calculations for the full ADC_BLOCK offset campaign.

Standard library only (no scipy). Reproduces the tables in
sim/adc-offset-mc/README.md section 6:

    python3 -I sim/adc-offset-mc/testbench/sample_size.py

Two DIFFERENT claims need two different N:

  (A) normal-model 3-sigma bound:  3 * sigma_U <= B  where sigma_U is the one-sided
      (1-alpha) chi-square upper confidence bound on the population sigma. B is the
      ratified 2 LSB = 6.445 mV (LSB_se = 3.2227 mV). Valid only if the population
      is normal -- the campaign must test that, not assume it.
  (B) empirical tail yield: P(|offset| <= B) >= p_target with confidence 1-alpha,
      from k exceedances in n draws (Clopper-Pearson). No normality assumption,
      but needs far more draws: with k = 0, n >= ln(alpha) / ln(p_target).
"""
from __future__ import annotations

import math
import sys
from statistics import NormalDist

LSB_SE_MV = 3.2227
BOUND_LSB = 2.0
BOUND_MV = BOUND_LSB * LSB_SE_MV


def _gammainc_lower_reg(a: float, x: float) -> float:
    """Regularised lower incomplete gamma P(a, x) (series / continued fraction)."""
    if x <= 0:
        return 0.0
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        for _ in range(10000):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    tiny = 1e-300
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return 1 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_cdf(x: float, df: int) -> float:
    return _gammainc_lower_reg(df / 2, x / 2)


def chi2_ppf(p: float, df: int) -> float:
    lo, hi = 0.0, max(10.0, df * 10.0)
    while chi2_cdf(hi, df) < p:
        hi *= 2
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if chi2_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def sigma_upper_factor(n: int, alpha: float) -> float:
    """sigma_U / s for a one-sided (1-alpha) bound from n normal draws."""
    return math.sqrt((n - 1) / chi2_ppf(alpha, n - 1))


def pass_probability(n: int, ratio_true: float, alpha: float) -> float:
    """P(campaign demonstrates 3*sigma_U <= B) when the true 3*sigma = ratio_true * B.

    Pass iff s <= (B/3) * sqrt(chi2_alpha(n-1)/(n-1)), and (n-1) s^2/sigma^2 ~ chi2(n-1).
    """
    return chi2_cdf(chi2_ppf(alpha, n - 1) / ratio_true ** 2, n - 1)


def n_for_assurance(ratio_true: float, alpha: float, assurance: float) -> int:
    n = 3
    while pass_probability(n, ratio_true, alpha) < assurance:
        n += 1
        if n > 100000:
            raise ValueError("unreachable")
    return n


def n_zero_failure(p_target: float, alpha: float) -> int:
    return math.ceil(math.log(alpha) / math.log(p_target))


def _binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * math.log(p) + (n - i) * math.log1p(-p)) for i in range(k + 1)) if 0 < p < 1 else float(p >= 1)


def yield_lower_bound(n: int, k_fail: int, alpha: float) -> float:
    """One-sided Clopper-Pearson lower bound on P(pass) given k_fail failures in n draws."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        # P(X <= k_fail | pass-prob = mid) -> failures ~ Bin(n, 1-mid)
        if _binom_cdf(k_fail, n, 1 - mid) > alpha:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def tail_prob_normal(ratio_true: float) -> float:
    z = 3.0 / ratio_true
    return 2 * (1 - NormalDist().cdf(z))


def runtime_plan(draw_s: float = 2725 / 8, pilot_conv: int = 33, conv: int = 82, n: int = 30,
                 points: int = 45, cap: int = 8) -> dict:
    """Serial-runtime plan for the screening stage (README 6.7 item 3). `draw_s` is the
    measured fleet time per 33-conversion draw (pilot job klt-sim-1b1c9893bf86: 2,725 s / 8);
    cost is taken as proportional to conversions per draw. One request per PVT point so the
    fleet parallelizes; `cap` is BATCH_MAX_CONCURRENT_INSTANCES."""
    per_draw = draw_s * conv / pilot_conv
    job = per_draw * n
    waves = math.ceil(points / cap)
    return {"conversions_per_draw": conv, "seconds_per_draw": per_draw, "hours_per_job": job / 3600,
            "serial_hours_if_one_job": job * points / 3600, "jobs": points, "instance_cap": cap,
            "waves": waves, "wall_hours_split_per_corner": waves * job / 3600}


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    if "--runtime-plan" in argv:
        for k, v in runtime_plan().items():
            print(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}")
        return
    alpha = 0.05
    print(f"B = {BOUND_LSB} LSB_se = {BOUND_MV:.3f} mV  (3-sigma bound => sigma <= {BOUND_MV/3:.3f} mV)\n")
    print("(A) normal-model 3-sigma bound, one-sided 95 % chi-square upper bound on sigma")
    print("    sigma_U/s factor: " + ", ".join(f"n={n}: {sigma_upper_factor(n, alpha):.3f}" for n in (30, 50, 100, 150, 300, 1000)))
    print("    N needed so the campaign demonstrates 3*sigma_U <= B with the stated assurance,")
    print("    as a function of the TRUE 3*sigma / B:")
    print("    | true 3sigma/B | true 3sigma (LSB) | N (80 % assurance) | N (95 % assurance) | P(pass) at N=150 | true P(|x|>B) |")
    print("    |---|---|---|---|---|---|")
    for r in (0.5, 0.6, 0.7, 0.8, 0.9):
        print(f"    | {r:.2f} | {r*BOUND_LSB:.2f} | {n_for_assurance(r, alpha, 0.80)} | {n_for_assurance(r, alpha, 0.95)} | "
              f"{pass_probability(150, r, alpha):.3f} | {tail_prob_normal(r):.2e} |")
    print("\n(B) empirical tail yield, zero exceedances, one-sided Clopper-Pearson")
    print("    | yield target | N (90 %) | N (95 %) | N (99 %) |")
    print("    |---|---|---|---|")
    for p in (0.95, 0.99, 0.9973, 0.999):
        print(f"    | {p:.4f} | {n_zero_failure(p, 0.10)} | {n_zero_failure(p, 0.05)} | {n_zero_failure(p, 0.01)} |")
    print("\n    What N=150 with zero exceedances proves (lower bound on P(|x|<=B)):")
    for conf in (0.90, 0.95, 0.99):
        print(f"      {conf:.0%} confidence: >= {yield_lower_bound(150, 0, 1 - conf):.4f}")
    print(f"    What N=150 with 1 exceedance proves (95 pct): >= {yield_lower_bound(150, 1, 0.05):.4f}")


if __name__ == "__main__":
    main()
