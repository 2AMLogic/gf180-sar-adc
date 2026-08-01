#!/usr/bin/env python3
"""Goodness-of-fit check on the raw comparator-offset-gof sample (issue #14).

Extracts every ``voa = <value>`` line ``tb_offset_gof.spice``'s manifest
prints per Monte Carlo draw (see ``testbench/tb.json``'s ``analyses``) from a
run's raw ngspice log, and runs a Shapiro-Wilk normality check against it --
the check `sim/comparator-offset-mc/`'s aggregate-sums-only manifest cannot
support (see this experiment's own header comment).

Usage:
    python3 analyze_gof.py <path/to/corners/<record-id>/tt_27c_3.30v.log> \\
        [--out-json <path>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy import stats

_VOA_RE = re.compile(r"^voa\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)\s*$")


def extract_samples(log_text: str) -> np.ndarray:
    values = [float(m.group(1)) for line in log_text.splitlines() if (m := _VOA_RE.match(line.strip()))]
    return np.array(values, dtype=np.float64)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path)
    p.add_argument("--out-json", type=Path, default=None)
    args = p.parse_args(argv)

    samples_v = extract_samples(args.log.read_text())
    if samples_v.size == 0:
        print(f"error: no 'voa = ...' lines found in {args.log}", file=sys.stderr)
        return 1

    samples_mv = samples_v * 1e3
    w_stat, p_value = stats.shapiro(samples_mv)
    mean_mv = float(np.mean(samples_mv))
    sigma_mv = float(np.std(samples_mv, ddof=1))

    # Anderson-Darling as a second, complementary GOF check (more sensitive
    # to tail deviations than Shapiro-Wilk, which is what a yield claim at
    # 3 sigma actually needs).
    ad = stats.anderson(samples_mv, dist="norm")
    ad_critical_5pct = float(ad.critical_values[list(ad.significance_level).index(5.0)])

    summary = {
        "log": str(args.log),
        "n_samples": int(samples_mv.size),
        "mean_vos_mv": mean_mv,
        "sigma_vos_mv": sigma_mv,
        "vos_3sig_mv": 3.0 * sigma_mv,
        "vos_3sig_lsb": 3.0 * sigma_mv / 3.2227,
        "shapiro_w": float(w_stat),
        "shapiro_p": float(p_value),
        "anderson_darling_statistic": float(ad.statistic),
        "anderson_darling_critical_5pct": ad_critical_5pct,
        "anderson_darling_rejects_normality_5pct": bool(ad.statistic > ad_critical_5pct),
    }
    print(json.dumps(summary, indent=2))
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
