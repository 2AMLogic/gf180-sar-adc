#!/usr/bin/env python3
"""Collate the DR-0019 C_u isolation sweep into one table (issue #211).

``sim/dr0019-cu-sweep/run_sweep.sh`` writes one append-only harness record per
sweep point.  This script reads those records -- and, like
``sim/adc-enob-fft/testbench/analyze_fft.py``, **the runner's own raw
per-corner logs**, never a hand-entered number -- and reports SFDR and ENOB as
a function of the CDAC unit capacitance.

It reuses ``analyze_fft.py``'s transform rather than re-implementing one, so
every figure here is produced by exactly the code that produced the figures in
``sim/adc-enob-fft/``'s records and in ``spec/testbench-suite-memo.md`` §11.

THE NOISE COMPOSITION IS RE-DERIVED PER SWEEP POINT, NOT COPIED.
``spec/testbench-suite-memo.md`` §4.3 composes the ENOB claim from this deck's
measured distortion plus two terms the transient cannot contain: the
comparator's input-referred noise (153.2 µV rms, ``sim/comparator-preamp-noise/``)
and the sampling ``kT/C`` (``√(2kT/C_side)``).  The second of those is a
function of ``C_side = 512·C_u`` -- the very quantity this sweep moves -- so
carrying the published ``0.0488 LSB`` across every point would silently
credit the small-``C_u`` points with noise they do not have.  ``sigma_extra_lsb``
below re-derives the term at each point's own ``C_side``; as a check on the
arithmetic it reproduces the ratified ``0.0488 LSB`` exactly at the historical
``C_u = 17.24 fF``.

Usage::

    python3 sim/dr0019-cu-sweep/analyze_sweep.py --markdown
    python3 sim/dr0019-cu-sweep/analyze_sweep.py --json

Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP_DIR = REPO_ROOT / "sim" / "dr0019-cu-sweep"
ANALYZE_FFT = REPO_ROOT / "sim" / "adc-enob-fft" / "testbench" / "analyze_fft.py"

#: spec/testbench-suite-memo.md §4.3 -- the one noise term that does NOT move
#: with C_u (sim/comparator-preamp-noise/, worst corner ff_125c_3.63v).
COMPARATOR_NOISE_V = 153.2e-6
#: Boltzmann, and the hot corner every point of this grid sits at.
K_BOLTZMANN = 1.380649e-23
T_KELVIN = 273.15 + 125.0
#: spec/cdac-sizing-memo.md §5.2 -- unit positions per side.
N_UNIT_PER_SIDE = 512
#: The LSB the ratified composition is expressed in (V_REF = V_DD = 3.3 V
#: nominal / 1024), kept fixed across the supply axis exactly as §4.3 does so
#: this sweep's composed ENOB is comparable with the published one.
LSB_V = 3.3 / 1024

#: Ratified targets, quoted for orientation only -- no point in this sweep is
#: a verdict on them (see the manifest's claim field).
ENOB_TARGET_BITS = 9.0
SFDR_TARGET_DB = 62.0


def load_analyze_fft():
    spec = importlib.util.spec_from_file_location("analyze_fft_for_sweep", ANALYZE_FFT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sigma_extra_lsb(c_unit_ff: float) -> float:
    """The §4.3 composed non-quantization noise, in LSB, at this ``C_u``."""
    c_side_f = N_UNIT_PER_SIDE * c_unit_ff * 1e-15
    ktc_v = math.sqrt(2.0 * K_BOLTZMANN * T_KELVIN / c_side_f)
    return math.hypot(COMPARATOR_NOISE_V, ktc_v) / LSB_V


_CU_RE = re.compile(r"C_u = ([0-9.]+) fF")
_SCALE_RE = re.compile(r"T-gate width scaled x([0-9.]+)")
_PROV_RE = re.compile(r"^- \*\*Netlist provenance\*\*: (.*)$", re.M)
_VERDICT_RE = re.compile(r"\*\*Overall: ([A-Z]+)\*\*")
_DROOP_RE = re.compile(r"^\s*\|\s*`vref_droop_mv`\s*\|\s*([0-9.]+)[^|]*\|\s*([0-9.]+)", re.M)


def read_points(records_dir: Path, corners_dir: Path) -> list[dict]:
    """One entry per recorded sweep point, newest record per point kept.

    ``sim/`` records are append-only, so a re-run of one sweep point (a
    timeout, a host that fell over mid-grid) leaves TWO records describing the
    same point and neither may be deleted.  Collating both would put the same
    ``C_u`` into the fit twice and weight it double, so the points are keyed by
    the axis they sit on -- ``(C_u, acquisition-leg scale)`` -- and the
    lexicographically-last record id wins.  Record ids lead with
    ``YYYYmmdd-HHMMSS`` (``sim/harness/report.py``'s ``format_record_id``), so
    that is the newest run, and the superseded record stays on disk as the
    evidence trail it is.
    """
    fft = load_analyze_fft()
    by_point: dict[tuple[float, float], dict] = {}
    for record in sorted(records_dir.glob("*.md")):
        text = record.read_text()
        prov = _PROV_RE.search(text)
        if not prov:
            continue
        cu = _CU_RE.search(prov.group(1))
        if not cu:
            continue
        scale = _SCALE_RE.search(prov.group(1))
        record_id = record.stem
        logs = sorted((corners_dir / record_id).glob("*.log"))
        if not logs:
            continue

        c_unit_ff = float(cu.group(1))
        sigma = sigma_extra_lsb(c_unit_ff)
        per_corner = {}
        for log in logs:
            per_corner[log.stem] = fft.analyze(
                fft.extract_codes(log.read_text(), fft.DEFAULT_N),
                fft.DEFAULT_BIN,
                sigma_extra_lsb=sigma,
            )
        verdict = _VERDICT_RE.search(text)
        droop = _DROOP_RE.search(text)
        worst_sfdr = min(per_corner.items(), key=lambda kv: kv[1]["sfdr_db"])
        worst_enob = min(per_corner.items(), key=lambda kv: kv[1]["enob_composed_bits"])
        acq_switch_scale = float(scale.group(1)) if scale else 1.0
        by_point[(c_unit_ff, acq_switch_scale)] = {
            "record_id": record_id,
            "c_unit_ff": c_unit_ff,
            "c_side_pf": N_UNIT_PER_SIDE * c_unit_ff / 1000.0,
            "acq_switch_scale": acq_switch_scale,
            "sigma_extra_lsb": sigma,
            "harness_verdict": verdict.group(1) if verdict else "?",
            "vref_droop_mv_max": float(droop.group(2)) if droop else None,
            "n_corners": len(per_corner),
            "worst_sfdr_corner": worst_sfdr[0],
            "worst_sfdr_db": worst_sfdr[1]["sfdr_db"],
            "worst_enob_corner": worst_enob[0],
            "worst_enob_bits": worst_enob[1]["enob_composed_bits"],
            "per_corner": per_corner,
        }
    points = list(by_point.values())
    points.sort(key=lambda p: (p["acq_switch_scale"], p["c_unit_ff"]))
    return points


def fit_slope(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Least-squares ``y = m*x + b`` plus Pearson r. Returns (m, b, r)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    m = sxy / sxx
    r = sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")
    return m, my - m * mx, r


def slopes(points: list[dict]) -> dict:
    """Per-corner fit of SFDR / ENOB against ``log10(C_u)``.

    The acquisition-RC hypothesis makes a *quantitative* prediction, not just
    a directional one.  If the limiting distortion is the signal-dependent
    acquisition lag ``R_on(V_in)·C_arr·dV_in/dt``, its amplitude is
    proportional to ``C_arr ∝ C_u`` while the signal is not, so SFDR must fall
    by **20 dB per decade of C_u** -- 6.02 dB per doubling.  A slope near
    −20 dB/decade with a tight fit supports it; a flat, wandering or
    step-shaped response refutes it.  Only the C_u axis is fitted; the
    orthogonal switch-width control is excluded (it moves R_on, not C_u).
    """
    axis = [p for p in points if p["acq_switch_scale"] == 1.0]
    out: dict = {"per_corner": {}}
    if len(axis) < 3:
        return out
    corners = sorted(axis[0]["per_corner"])
    xs = [math.log10(p["c_unit_ff"]) for p in axis]
    for corner in corners:
        ys = [p["per_corner"][corner]["sfdr_db"] for p in axis]
        m, b, r = fit_slope(xs, ys)
        ye = [p["per_corner"][corner]["enob_composed_bits"] for p in axis]
        me, _, re_ = fit_slope(xs, ye)
        out["per_corner"][corner] = {
            "sfdr_db_per_decade": m,
            "sfdr_intercept_db": b,
            "sfdr_r": r,
            "enob_bits_per_decade": me,
            "enob_r": re_,
        }
    ms = [v["sfdr_db_per_decade"] for v in out["per_corner"].values()]
    out["sfdr_db_per_decade_mean"] = sum(ms) / len(ms)
    out["sfdr_db_per_decade_min"] = min(ms)
    out["sfdr_db_per_decade_max"] = max(ms)
    me = [v["enob_bits_per_decade"] for v in out["per_corner"].values()]
    out["enob_bits_per_decade_mean"] = sum(me) / len(me)
    return out


def _md_matrix(points: list[dict], key: str, fmt: str) -> list[str]:
    corners = sorted(points[0]["per_corner"])
    head = [f"{p['c_unit_ff']:g}" + ("" if p["acq_switch_scale"] == 1.0 else f" (sw x{p['acq_switch_scale']:g})") for p in points]
    lines = ["| corner-id | " + " | ".join(head) + " |", "|---" * (len(head) + 1) + "|"]
    for corner in corners:
        cells = [format(p["per_corner"][corner][key], fmt) for p in points]
        lines.append(f"| `{corner}` | " + " | ".join(cells) + " |")
    return lines


def emit_markdown(points: list[dict], fits: dict) -> None:
    print("### Sweep points\n")
    print("| C_u (fF) | C_side = 512·C_u (pF) | acq-leg width | worst SFDR (dB) | at | worst composed ENOB (bits) | at | σ_extra (LSB) | harness | max V_REF droop (mV) | record |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for p in points:
        print(
            f"| {p['c_unit_ff']:g} | {p['c_side_pf']:.3f} | "
            f"x{p['acq_switch_scale']:g} | {p['worst_sfdr_db']:.2f} | "
            f"`{p['worst_sfdr_corner']}` | {p['worst_enob_bits']:.3f} | "
            f"`{p['worst_enob_corner']}` | {p['sigma_extra_lsb']:.4f} | "
            f"{p['harness_verdict']} | "
            f"{'—' if p['vref_droop_mv_max'] is None else format(p['vref_droop_mv_max'], '.3f')} | "
            f"`{p['record_id']}` |"
        )

    print("\n### SFDR (dB) per corner, per C_u (fF)\n")
    print("\n".join(_md_matrix(points, "sfdr_db", ".2f")))
    print("\n### Composed ENOB (bits) per corner, per C_u (fF)\n")
    print("\n".join(_md_matrix(points, "enob_composed_bits", ".3f")))

    if fits.get("per_corner"):
        print("\n### Fit against log10(C_u) -- the −20 dB/decade prediction\n")
        print("| corner-id | SFDR slope (dB/decade) | Pearson r | ENOB slope (bits/decade) |")
        print("|---|---|---|---|")
        for corner, v in sorted(fits["per_corner"].items()):
            print(
                f"| `{corner}` | {v['sfdr_db_per_decade']:.2f} | "
                f"{v['sfdr_r']:.4f} | {v['enob_bits_per_decade']:.3f} |"
            )
        print(
            f"\nMean SFDR slope: **{fits['sfdr_db_per_decade_mean']:.2f} dB/decade** "
            f"(range {fits['sfdr_db_per_decade_min']:.2f} … "
            f"{fits['sfdr_db_per_decade_max']:.2f}); the acquisition-RC "
            f"hypothesis predicts −20.00. Mean ENOB slope: "
            f"{fits['enob_bits_per_decade_mean']:.3f} bits/decade."
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--records", type=Path, default=SWEEP_DIR / "records")
    p.add_argument("--corners", type=Path, default=SWEEP_DIR / "corners")
    p.add_argument("--markdown", action="store_true")
    args = p.parse_args(argv)

    points = read_points(args.records, args.corners)
    if not points:
        print(f"error: no usable sweep records under {args.records}", file=sys.stderr)
        return 1
    fits = slopes(points)
    if args.markdown:
        emit_markdown(points, fits)
    else:
        print(json.dumps({"points": points, "fits": fits}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
