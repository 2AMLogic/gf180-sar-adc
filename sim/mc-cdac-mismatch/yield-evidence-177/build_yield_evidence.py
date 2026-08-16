#!/usr/bin/env python3
"""Build the `klt yield` sample-set + spec-limits documents for issue #177's
resized-`C_u` gain-error verification (README.md#target-specification line
50).

Same pattern as `sim/mc-cdac-mismatch/yield-evidence/build_yield_evidence.py`
(issue #172, T1 item 6), deliberately NOT reused in place: that directory's
`mc-samples.json`/`spec-limits.json` are the *built* design's own evidence
(`sigma_u = 0.7372097807744856 %`, the design as currently drawn in
`design/adc-top/` and `layout/adc-top/`). This directory instead verifies
the RESIZING DECISION issue #177 makes (`spec/decision-records/
DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`): `sigma_u = 0.5 %`,
the value the resized `C_u = 35.6528 fF` (`s = 4.0 um`) calibrates to. It is
a separate, real Monte Carlo run (not the built design's own), kept in its
own directory so it does not overwrite or get confused with #172's
already-cited evidence for the pre-resize design.

Reads two real, already-committed artifacts this run produced:

  - the nominal N=20000 campaign at the resized sigma_u
    (`sim/mc-cdac-mismatch/runs/<RECORD_ID>/trials_n20000.csv` /
    `summary_n20000.json`);
  - a negative-control run at 3x the resized sigma_u, N=2000
    (`sim/mc-cdac-mismatch/runs/<RECORD_ID>/trials_n2000_3xsigma.csv` /
    `summary_n2000_3xsigma.json`), the same negative-control convention PR
    #149 / issue #172 established.

and emits `mc-samples.json` + `spec-limits.json` in this directory. Usage:
`python3 build_yield_evidence.py` from this directory (or anywhere; paths
are resolved relative to this file). Deterministic and idempotent.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MC_DIR = HERE.parent

RECORD_ID = "20260816-125421-737d16e"
NOMINAL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n20000.csv"
NOMINAL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n20000.json"
NEG_CONTROL_CSV = MC_DIR / "runs" / RECORD_ID / "trials_n2000_3xsigma.csv"
NEG_CONTROL_SUMMARY = MC_DIR / "runs" / RECORD_ID / "summary_n2000_3xsigma.json"

# 3-sigma two-sided normal yield -- the "3 sigma" pass criterion
# `spec/cdac-sizing-memo.md` SS3.1-3.3 states, expressed as a target_yield
# fraction the way `klt yield --limits` wants it. Same constant PR #149 /
# issue #172 used.
TARGET_YIELD_3SIGMA = 0.9973002039367398


def read_column(path: Path, column: str) -> list[float]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [float(row[column]) for row in reader]


def main() -> None:
    nominal_summary = json.loads(NOMINAL_SUMMARY.read_text())
    analytic_sigma_gain_lsb = nominal_summary["analytic_sigma_gain_lsb"]

    gain_samples = read_column(NOMINAL_CSV, "gain_error_lsb")
    gain_neg = read_column(NEG_CONTROL_CSV, "gain_error_lsb")

    neg_summary = json.loads(NEG_CONTROL_SUMMARY.read_text())
    neg_sigma_u = neg_summary["sigma_u_pct"]
    neg_n = neg_summary["n_trials"]
    neg_seed = neg_summary["seed"]

    negative_control_desc = (
        f"CDAC unit-cap mismatch sigma forced to 3x the RESIZED design's "
        f"calibrated value (sigma_u={neg_sigma_u:.6f}% vs "
        f"{nominal_summary['sigma_u_pct']:.6f}% nominal), N={neg_n}, "
        f"seed={neg_seed} -- same behavioral model (mc_cdac_mismatch.py) "
        f"and methodology as the nominal campaign, a real (re-runnable) "
        f"simulation, not a synthetic offset. See "
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
                    "sigma": analytic_sigma_gain_lsb,
                    "mean": 0.0,
                },
            },
        ]
    }

    (HERE / "mc-samples.json").write_text(json.dumps(doc, indent=2) + "\n")

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
