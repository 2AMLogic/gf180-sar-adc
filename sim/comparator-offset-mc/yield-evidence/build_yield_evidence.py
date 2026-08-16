#!/usr/bin/env python3
"""Build the `klt yield` sample-set + spec-limits documents for the
comparator-offset-mc Offset-error and CMRR rows (README.md#target-
specification lines 49/52, issue #172, T1 item 6).

This is a pure reformatting step -- it invents no numbers. It reads the
real per-draw `voa`/`ddc`/`dde` values `tb.json`'s dowhile loop now prints
into each PVT point's own log (see that file's "RAW SAMPLES" note, added
alongside this script -- mirroring `sim/comparator-offset-gof/testbench/
tb.json`'s established `print voa` pattern), from the clean-tree corner
sweep `sim/comparator-offset-mc/records/20260816-050001-d002e66.md` recorded.

Three measurements are emitted, each from the SINGLE PVT corner that is
this campaign's own worst case for that quantity (not pooled across
corners -- `klt yield` warns when a draw spans more than one originating
corner, because each corner is its own population; the record's own
"Spread across the grid" table is what identifies the worst corner in the
first place, so this script re-derives that same worst-corner choice from
the record's own already-committed numbers rather than re-deciding it):

  - `offset_error_worst_corner_lsb`: the ``Offset error`` row
    (<= 2 LSB, untrimmed, 3-sigma mismatch). Samples are the worst
    corner's (`sf_-40c_3.30v`, this record's own max `vos_3sig_lsb`) 150
    raw `voa` draws, converted V -> LSB_se (`3.2227 mV`,
    `spec/cdac-sizing-memo.md` S0). Carries an `analytic_cross_check`
    against the standalone `A_Vt = 7.208 mV*um` extraction
    (`sim/device-characterization-report.md` S3.3), the same closed-form
    prediction this campaign's own `avt_back_mv_um` check already compares
    against.
  - `cmrr_dvos_dn_uv_worst_corner` / `cmrr_dvos_up_uv_worst_corner`: the
    ``CMRR`` row (>= 60 dB, DC-Nyquist, over V_CM = V_REF/2 +/- 100 mV),
    reused per `spec/testbench-suite-memo.md` S10 from this campaign's own
    `ddc`/`dde` (the code-correlated common-mode-step offset delta), NOT a
    separate campaign. Samples are the worst corner's (`ss_-40c_3.63v`,
    this record's own max `sig_dvos_dn_uv`/`sig_dvos_up_uv`) 150 raw
    `ddc`/`dde` draws, in uV. Limits are the ratified 60 dB target
    (28.117 uV, or a passing "stretch" description, are all discussed
    in the record's own prose) LINEARLY EXTRAPOLATED from the ratified
    row's +/-100 mV condition down to this campaign's own measured
    +/-50 mV common-mode band -- `spec/testbench-suite-memo.md` S10's own
    stated limitation, carried forward here rather than glossed: a 60 dB
    ratio at a 100 mV step implies a 50 dB-equivalent ABSOLUTE voltage of
    100 mV / 10^(60/20) = 100 uV; at the HALVED +/-50 mV step this
    campaign actually measures, the equivalent absolute limit is likewise
    halved (50 uV) because CMRR is a ratio and a first-order (linear)
    common-mode sensitivity extrapolates unchanged (S10) -- so testing
    this campaign's real +/-50 mV samples against a 50 uV limit is
    identically the same pass/fail statement S10 makes about the ratified
    +/-100 mV row, not a loosened one.

Usage: `python3 build_yield_evidence.py` from this directory (or anywhere;
paths are resolved relative to this file). Deterministic and idempotent --
re-running overwrites `mc-samples.json`/`spec-limits.json` in place (they
are derived views, not evidence themselves; the append-only rule governs
`sim/comparator-offset-mc/corners/`/`records/`, not this derived
reformatting -- see `sim/mc-cdac-mismatch/yield-evidence/
build_yield_evidence.py` for the identical convention this script mirrors).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP_DIR = HERE.parent

RECORD_ID = "20260816-050001-d002e66"
CORNERS_DIR = EXP_DIR / "corners" / RECORD_ID

# Worst-corner choices, read directly from this record's own "Spread across
# the grid" table (sim/comparator-offset-mc/records/20260816-050001-d002e66.md)
# -- not re-decided here.
OFFSET_WORST_CORNER = "sf_-40c_3.30v"   # max vos_3sig_lsb = 1.19237
CMRR_WORST_CORNER = "ss_-40c_3.63v"     # max sig_dvos_dn_uv AND sig_dvos_up_uv

LSB_SE_MV = 3.2227  # spec/cdac-sizing-memo.md S0: LSB_se = V_REF/1024

# Standalone A_Vt extraction (sim/device-characterization-report.md S3.3),
# and the same effective-area rule this campaign's own `avt_back_mv_um`
# check already uses (devchar S3.3: L_eff = L - 0.15, W_eff = W + 0.1 at the
# 40/0.5 um candidate pair).
A_VT_STANDALONE_MV_UM = 7.208
W_EFF_UM = 40.1
L_EFF_UM = 0.85
ANALYTIC_SIGMA_VOS_LSB = (A_VT_STANDALONE_MV_UM / math.sqrt(W_EFF_UM * L_EFF_UM)) / LSB_SE_MV

# CMRR limit, linearly extrapolated from the ratified +/-100 mV / 60 dB
# condition down to this campaign's own measured +/-50 mV band -- see the
# module docstring above and spec/testbench-suite-memo.md S10.
CM_STEP_MEASURED_UV = 50000.0  # 50 mV
CMRR_TARGET_DB = 60.0
CMRR_LIMIT_UV = CM_STEP_MEASURED_UV / (10 ** (CMRR_TARGET_DB / 20.0))  # == 50.0

TARGET_YIELD_3SIGMA = 0.9973002039367398


def read_prints(corner_id: str, name: str) -> list[float]:
    """Every `print <name>` line's value from one corner's raw ngspice log,
    in the order printed (i.e. draw order)."""
    log_path = CORNERS_DIR / f"{corner_id}.log"
    pattern = re.compile(rf"^{re.escape(name)}\s*=\s*([-0-9.eE+]+)\s*$")
    values: list[float] = []
    with log_path.open() as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                values.append(float(m.group(1)))
    return values


def main() -> None:
    voa_v = read_prints(OFFSET_WORST_CORNER, "voa")
    ddc_v = read_prints(CMRR_WORST_CORNER, "ddc")
    dde_v = read_prints(CMRR_WORST_CORNER, "dde")

    assert len(voa_v) == 150, f"expected 150 voa draws at {OFFSET_WORST_CORNER}, got {len(voa_v)}"
    assert len(ddc_v) == 150, f"expected 150 ddc draws at {CMRR_WORST_CORNER}, got {len(ddc_v)}"
    assert len(dde_v) == 150, f"expected 150 dde draws at {CMRR_WORST_CORNER}, got {len(dde_v)}"

    offset_lsb = [v * 1000.0 / LSB_SE_MV for v in voa_v]  # V -> mV -> LSB_se
    ddc_uv = [v * 1e6 for v in ddc_v]  # V -> uV
    dde_uv = [v * 1e6 for v in dde_v]

    doc = {
        "measurements": [
            {
                "name": "offset_error_worst_corner_lsb",
                "unit": "LSB",
                "samples": offset_lsb,
                "errored": 0,
                "source_corners": [OFFSET_WORST_CORNER],
                "analytic_cross_check": {
                    "kind": "mismatch_offset",
                    "sigma": ANALYTIC_SIGMA_VOS_LSB,
                    "mean": 0.0,
                },
            },
            {
                "name": "cmrr_dvos_dn_uv_worst_corner",
                "unit": "uV",
                "samples": ddc_uv,
                "errored": 0,
                "source_corners": [CMRR_WORST_CORNER],
            },
            {
                "name": "cmrr_dvos_up_uv_worst_corner",
                "unit": "uV",
                "samples": dde_uv,
                "errored": 0,
                "source_corners": [CMRR_WORST_CORNER],
            },
        ]
    }

    (HERE / "mc-samples.json").write_text(json.dumps(doc, indent=2) + "\n")

    limits_doc = {
        "target_ci_halfwidth": 0.01,
        "measurements": {
            "offset_error_worst_corner_lsb": {
                "min": -2.0, "max": 2.0, "target_yield": TARGET_YIELD_3SIGMA,
            },
            "cmrr_dvos_dn_uv_worst_corner": {
                "min": -CMRR_LIMIT_UV, "max": CMRR_LIMIT_UV, "target_yield": TARGET_YIELD_3SIGMA,
            },
            "cmrr_dvos_up_uv_worst_corner": {
                "min": -CMRR_LIMIT_UV, "max": CMRR_LIMIT_UV, "target_yield": TARGET_YIELD_3SIGMA,
            },
        },
    }
    (HERE / "spec-limits.json").write_text(json.dumps(limits_doc, indent=2) + "\n")

    print(f"wrote {HERE / 'mc-samples.json'}")
    print(f"wrote {HERE / 'spec-limits.json'}")
    print(f"  offset ({OFFSET_WORST_CORNER}): {len(offset_lsb)} samples")
    print(f"  cmrr dn/up ({CMRR_WORST_CORNER}): {len(ddc_uv)}/{len(dde_uv)} samples")
    print(f"  cmrr limit at measured +/-50 mV band: +/-{CMRR_LIMIT_UV} uV (60 dB)")


if __name__ == "__main__":
    main()
