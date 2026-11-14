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


def main() -> None:
    nominal_summary = json.loads(NOMINAL_SUMMARY.read_text())
    analytic_sigma_gain_lsb = nominal_summary["analytic_sigma_gain_lsb"]

    gain_samples = ye.read_column(NOMINAL_CSV, "gain_error_lsb")
    gain_neg = ye.read_column(NEG_CONTROL_CSV, "gain_error_lsb")

    neg_summary = json.loads(NEG_CONTROL_SUMMARY.read_text())

    negative_control_desc = ye.negative_control_description(
        neg_summary,
        RECORD_ID,
        basis="the RESIZED design's calibrated value",
        nominal_pct=nominal_summary["sigma_u_pct"],
    )

    measurements = [
        ye.measurement(
            "gain_error_mismatch_lsb",
            "LSB",
            gain_samples,
            negative_control=ye.negative_control(gain_neg, negative_control_desc),
            analytic_cross_check=ye.analytic_cross_check(analytic_sigma_gain_lsb),
        ),
    ]

    limits = {
        "gain_error_mismatch_lsb": ye.symmetric_limit(0.5),
    }

    ye.write_bundle(
        HERE,
        measurements,
        limits,
        [NOMINAL_CSV, NEG_CONTROL_CSV, NOMINAL_SUMMARY, NEG_CONTROL_SUMMARY],
        rel_to=MC_DIR,
    )
    print(f"  gain-error samples: {len(gain_samples)}")
    print(f"  negative-control samples: {len(gain_neg)}")


if __name__ == "__main__":
    main()
