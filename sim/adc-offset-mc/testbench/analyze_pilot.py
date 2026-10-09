#!/usr/bin/env python3
"""Reduce `klt sim` pilot reports to per-sample ADC input-offset values and
apply the declared qualification checks (sim/adc-offset-mc/README.md section 4).

    analyze_pilot.py --enabled enabled.json --null null.json [--repeat enabled2.json] [--out summary.json]

Estimator. Each Monte Carlo sample is ONE transient = ONE mismatch draw
holding N back-to-back conversions of a differential-input staircase
d_k = D_START + k*STEP. dout is HIGH when V_inp - V_inn is below the block's
decision threshold, so a healthy sample reads 1...1 0...0 and the input-
referred offset is the midpoint between the last 1 and the first 0:
quantisation uncertainty is +/- STEP/2 (uniform, sigma STEP/sqrt(12)). A
sample that never flips (censored), flips more than once (non-monotone:
conversion-to-conversion memory or a readout fault) or has a dout level that
is not a clean rail (indeterminate) is a FAILED draw: reported, never dropped.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_pilot as G  # noqa: E402

LSB_SE_V = 3.2227e-3        # V_REF/1024 at 3.3 V, DR-0006 (same conversion as sim/comparator-offset-mc)
RAIL_FRAC = 0.1             # dout within 10 % of a rail is a clean logic level
DIFFS = G.diffs()
STEP = G.STEP_V


def _levels_to_bits(levels, vdd):
    bits = []
    for v in levels:
        if v > (1 - RAIL_FRAC) * vdd:
            bits.append(1)
        elif v < RAIL_FRAC * vdd:
            bits.append(0)
        else:
            return None, f"indeterminate dout level {v:.3f} V"
    return bits, None


def _threshold(bits, diffs):
    """`bits` ordered by ascending differential input. -> (midpoint V, failure text)."""
    flips = [k for k in range(len(bits) - 1) if bits[k] != bits[k + 1]]
    if len(flips) == 0:
        return None, "censored: no decision flip inside the input range"
    if len(flips) > 1 or bits[0] != 1:
        return None, "non-monotone decision sequence"
    j = flips[0]
    return 0.5 * (diffs[j] + diffs[j + 1]), None


def _supply_vdd(c: dict, default: float) -> float:
    sv = c.get("supply_v")
    if isinstance(sv, dict) and sv.get("Vdd") is not None:
        v = sv["Vdd"]
        return float(v[0] if isinstance(v, list) else v)
    return default


def sample_from_corner(c: dict, vdd: float | None = None) -> dict:
    """Pilot layout (d00.. ascending only) or screening layout (u00.. ascending, r00.. descending).

    Screening: `vos_up_v` / `vos_down_v` are the thresholds read from the ascending /
    descending staircase; `hysteresis_v` = up - down (signed; positive when the
    comparator switches later going up); `vos_v` stays the ascending threshold so it is
    comparable with the pilot and `vos_mid_v` is the up/down midpoint. A draw whose
    descending readout fails is a FAILED draw (reported, never dropped)."""
    vdd = _supply_vdd(c, G.VDD if vdd is None else vdd)
    mc = c.get("monte_carlo") or {}
    meas = {m["name"]: m.get("value") for m in c.get("measurements", [])}
    screening = "u00" in meas
    up_diffs = G.screen_up() if screening else DIFFS
    out = {
        "corner_id": c.get("corner_id"),
        "klt_status": c.get("status"),
        "sample_index": mc.get("sample_index"),
        "seed": mc.get("seed"),
        "mismatch_seed": mc.get("mismatch_seed"),
        "diagnostics": [d.get("code", d) if isinstance(d, dict) else d for d in c.get("diagnostics", [])],
        "vos_v": None,
        "failure": None,
    }
    up_names = [f"{'u' if screening else 'd'}{k:02d}" for k in range(len(up_diffs))]
    dn_names = [f"r{k:02d}" for k in range(len(up_diffs))] if screening else []
    levels = [meas.get(n) for n in up_names + dn_names]
    if any(v is None for v in levels):
        out["failure"] = "missing dout measurement(s)"
        return out
    up_bits, err = _levels_to_bits(levels[:len(up_names)], vdd)
    if err:
        out["failure"] = err
        return out
    out["bits"] = "".join(map(str, up_bits))
    dn_bits = None
    if screening:
        dn_bits, err = _levels_to_bits(levels[len(up_names):], vdd)
        if err:
            out["failure"] = "descending: " + err
            return out
        out["bits_down"] = "".join(map(str, dn_bits))
    if c.get("status") not in ("pass", "ok"):
        out["failure"] = f"klt corner status {c.get('status')}"
        return out
    vos, err = _threshold(up_bits, up_diffs)
    if err:
        out["failure"] = err
        return out
    if screening:
        # descending reads from the top level down: reverse to ascending-input order.
        vdn, err = _threshold(dn_bits[::-1], up_diffs)
        if err:
            out["failure"] = "descending: " + err
            return out
        h = vos - vdn
        out.update(vos_up_v=vos, vos_down_v=vdn, hysteresis_v=h, vos_mid_v=0.5 * (vos + vdn),
                   hysteresis_flag=abs(h) > STEP + 1e-12,
                   hysteresis_uncertainty_v=math.hypot(STEP / math.sqrt(12), 0.5 * abs(h)))
    out["vos_v"] = vos
    return out


def load(path: Path) -> dict:
    rep = json.loads(path.read_text())
    samples = [sample_from_corner(c) for c in rep.get("corners", [])]
    return {
        "report": str(path),
        "report_status": rep.get("status"),
        "environment_monte_carlo": rep.get("environment", {}).get("monte_carlo"),
        "samples": samples,
    }


def stats(vals: list[float]) -> dict:
    if not vals:
        return {"n_valid": 0}
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return {
        "n_valid": len(vals),
        "mean_mv": statistics.fmean(vals) * 1e3,
        "sd_mv": sd * 1e3,
        "sd_quantisation_corrected_mv": math.sqrt(max(sd * sd - STEP * STEP / 12, 0.0)) * 1e3,
        "min_mv": min(vals) * 1e3,
        "max_mv": max(vals) * 1e3,
        "spread_mv": (max(vals) - min(vals)) * 1e3,
        "distinct_values": len(set(round(v, 9) for v in vals)),
        "sd_lsb_se": sd / LSB_SE_V,
    }


def check(name: str, ok: bool, detail: str) -> dict:
    return {"check": name, "pass": bool(ok), "detail": detail}


def evaluate(enabled: dict, null: dict, repeat: dict | None, n_expected: int, n_null_expected: int) -> dict:
    ev = [s for s in enabled["samples"] if s["vos_v"] is not None]
    nv = [s for s in null["samples"] if s["vos_v"] is not None]
    es, ns_ = stats([s["vos_v"] for s in ev]), stats([s["vos_v"] for s in nv])
    seeds = [s["seed"] for s in enabled["samples"]]
    checks = [
        check("enabled: all expected draws returned",
              len(enabled["samples"]) == n_expected,
              f"{len(enabled['samples'])} returned of {n_expected} requested"),
        check("enabled: >= 75 % of draws valid (failed draws are listed, not dropped)",
              len(ev) >= 0.75 * n_expected, f"{len(ev)}/{n_expected} valid"),
        check("enabled: per-sample seeds all distinct (no duplicated draws)",
              len(set(seeds)) == len(seeds) and None not in seeds, f"{len(set(seeds))} distinct of {len(seeds)}"),
        check("enabled: spread above resolution (sd >= 1 step and >= 3 distinct values)",
              len(ev) > 1 and es["sd_mv"] >= STEP * 1e3 and es["distinct_values"] >= 3,
              f"sd {es.get('sd_mv', float('nan')):.3f} mV vs step {STEP*1e3:.3f} mV, "
              f"{es.get('distinct_values', 0)} distinct values"),
        check("null: all draws valid", len(nv) == n_null_expected and len(null["samples"]) == n_null_expected,
              f"{len(nv)}/{n_null_expected} valid"),
        check("null: spread within resolution (max-min <= 1 step)",
              len(nv) > 0 and ns_["spread_mv"] <= STEP * 1e3 + 1e-9,
              f"spread {ns_.get('spread_mv', float('nan')):.3f} mV vs step {STEP*1e3:.3f} mV"),
        check("null seeds differ across draws (control is seed-varying, mismatch-off)",
              len({s['seed'] for s in null['samples']}) == len(null['samples']) and len(null['samples']) > 1,
              f"{len({s['seed'] for s in null['samples']})} distinct seeds"),
    ]
    rep_out = None
    if repeat is not None:
        by = {s["sample_index"]: s for s in repeat["samples"]}
        diffs, same_seed = [], True
        for s in enabled["samples"]:
            r = by.get(s["sample_index"])
            if r is None or r["seed"] != s["seed"]:
                same_seed = False
                continue
            if s["vos_v"] is not None and r["vos_v"] is not None:
                diffs.append(abs(s["vos_v"] - r["vos_v"]))
            elif (s["vos_v"] is None) != (r["vos_v"] is None):
                diffs.append(float("inf"))
        rep_out = {"max_abs_diff_mv": max(diffs) * 1e3 if diffs else None, "pairs": len(diffs)}
        checks.append(check("repeat: identical seed schedule", same_seed, "per-sample seeds equal run to run"))
        checks.append(check("repeat: samples reproduce within 1 step",
                            bool(diffs) and max(diffs) <= STEP + 1e-12,
                            f"max |delta| {rep_out['max_abs_diff_mv']} mV over {len(diffs)} pairs"))
    return {
        "declared": {
            "step_mv": STEP * 1e3, "n_steps": len(DIFFS), "range_mv": [DIFFS[0] * 1e3, DIFFS[-1] * 1e3],
            "lsb_se_mv": LSB_SE_V * 1e3,
            "quantisation_sigma_mv": STEP / math.sqrt(12) * 1e3,
        },
        "enabled": {**enabled, "stats": es},
        "null": {**null, "stats": ns_},
        "repeat": ({**repeat, "vs_enabled": rep_out} if repeat else None),
        "checks": checks,
        "all_checks_pass": all(c["pass"] for c in checks),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--enabled", type=Path, required=True)
    ap.add_argument("--null", type=Path, required=True)
    ap.add_argument("--repeat", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-enabled", type=int, default=G.MC_N)
    ap.add_argument("--n-null", type=int, default=G.NULL_N)
    a = ap.parse_args(argv)
    res = evaluate(load(a.enabled), load(a.null), load(a.repeat) if a.repeat else None, a.n_enabled, a.n_null)
    text = json.dumps(res, indent=2, default=str) + "\n"
    if a.out:
        a.out.write_text(text)
    for c in res["checks"]:
        print(("PASS " if c["pass"] else "FAIL ") + c["check"] + " -- " + c["detail"])
    print("ENABLED", json.dumps(res["enabled"]["stats"]))
    print("NULL   ", json.dumps(res["null"]["stats"]))
    return 0 if res["all_checks_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
