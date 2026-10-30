#!/usr/bin/env python3
"""CDAC array edge-margin analysis: where the bbox excess comes from, and what
trimming it would cost in matching (issue #669, child of #644).

Two parts, both read-only against the committed layout:

1. **Measured breakdown.** For each CDAC array cell in `adc_block.gds`, the
   per-layer bounding box, and the bbox width/height split into the real core
   grid, the dummy ring and "anything else". The Metal4 MiM footprints are
   classified by tile index (`round(x / UNIT_PITCH)`), so the split comes from
   the GDS and not from the generator's arithmetic. The script exits non-zero
   if the split does not sum to the cell bbox within 1 nm, or if any layer
   reaches outside the footprint bbox (i.e. "anything else" is non-zero).

2. **Analytical edge-sensitivity.** The gf180mcu PDK has no local capacitor
   mismatch model (`layout/floorplan-matching-plan.md` Sec 1.3), so a
   Monte Carlo cannot price an edge effect. Instead a deterministic edge bias
   `eps` (fractional change of a unit cap per side with no neighbouring tile)
   is applied to the units a trim would expose, in the generator's own
   `centroid_tiling` assignment, and pushed through the same transfer function
   `sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py` uses. Everything is
   linear in `eps`, so the output is LSB per 1 % of `eps` plus the break-even
   `eps` against the margin the random-mismatch campaign leaves.

`eps` itself is NOT known for this PDK; the result is therefore a tolerance
(how large an edge bias each option can absorb), not a prediction.

Run with the interpreter `klt` uses (it carries `klayout.db`), from the repo
root:

    KP="$(dirname "$(readlink -f "$(command -v klt)")")/python"
    PYTHONPATH=layout/adc-top "$KP" layout/adc-top/array_edge_margin.py \\
        --json layout/adc-top/economy/records/<record-id>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_adc_top as top  # noqa: E402
from lib import geometry as geo  # noqa: E402

GDS = os.path.join(HERE, "adc_block.gds")
ARRAYS = ("ADC_CDAC_ARRAY_N", "ADC_CDAC_ARRAY_P")
TOL_NM = 1

# Random-mismatch margin, from the committed `klt yield` campaign
# (sim/mc-cdac-mismatch/yield-evidence-656/klt-yield-report.txt, sigma_u =
# 0.5000 %, N = 20000): worst-over-codes stddev of DNL / INL in LSB.
SIGMA_MAX_DNL_LSB = 0.130515
SIGMA_MAX_INL_LSB = 0.0918591
SPEC_LSB = 0.5  # stretch limit, README target specification
SPEC_GAIN_LSB = 0.5
K_SIGMA = 3.0
# Gain error: 32 * sigma_u LSB (spec/cdac-sizing-memo.md Sec 3.6), sigma_u = 0.5 %.
SIGMA_GAIN_LSB = 32 * 0.005


def measure(layout: kdb.Layout, name: str) -> dict:
    cell = layout.cell(name)
    pitch = top.UNIT_PITCH
    m4 = layout.layer(*geo.L_METAL4)
    footprints = []
    for sh in cell.shapes(m4).each():
        b = sh.bbox()
        if b.width() == b.height() == top.UNIT_CAP_NM + 2 * geo.MIM_M4_ENCLOSURE:
            footprints.append(b)
    cols = sorted({round(b.left / pitch) for b in footprints})
    rows = sorted({round(b.bottom / pitch) for b in footprints})
    core_c = [c for c in cols if 0 <= c < top.ARRAY_COLS]
    core_r = [r for r in rows if 0 <= r < top.ARRAY_ROWS]
    assert len(footprints) == len(cols) * len(rows), "footprints are not a full grid"

    def span(idx_lo, idx_hi, axis):
        sel = [
            b for b in footprints
            if idx_lo <= round((b.left if axis == "x" else b.bottom) / pitch) <= idx_hi
        ]
        lo = min(b.left if axis == "x" else b.bottom for b in sel)
        hi = max(b.right if axis == "x" else b.top for b in sel)
        return lo, hi

    bbox = cell.bbox()
    out = {"cell": name, "bbox_nm": [bbox.left, bbox.bottom, bbox.right, bbox.top],
           "tiles": [len(cols), len(rows)], "layers": {}}
    for axis, core, all_idx, lo_b, hi_b in (
        ("x", core_c, cols, bbox.left, bbox.right),
        ("y", core_r, rows, bbox.bottom, bbox.top),
    ):
        c_lo, c_hi = span(core[0], core[-1], axis)
        f_lo, f_hi = span(all_idx[0], all_idx[-1], axis)
        parts = {
            "ring_low_nm": c_lo - lo_b,
            "core_nm": c_hi - c_lo,
            "ring_high_nm": hi_b - c_hi,
        }
        total = sum(parts.values())
        extra = (bbox.width() if axis == "x" else bbox.height()) - total
        out[axis] = {**parts, "sum_nm": total, "bbox_nm": total + extra,
                     "other_nm": (f_lo - lo_b) + (hi_b - f_hi)}
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        if cell.shapes(li).is_empty():
            continue
        b = cell.dbbox_per_layer(li)
        out["layers"][f"{info.layer}/{info.datatype}"] = [
            round(b.left, 3), round(b.bottom, 3), round(b.right, 3), round(b.top, 3)]
    return out


def edge_open_sides(removed: set[str]) -> dict[tuple[int, int], int]:
    """Per real unit, the number of cardinal sides with no neighbouring tile
    once the ring on the `removed` edges (subset of L,R,B,T) is gone."""
    n = {}
    for c in range(top.ARRAY_COLS):
        for r in range(top.ARRAY_ROWS):
            n[(c, r)] = (
                ("L" in removed and c == 0) + ("R" in removed and c == top.ARRAY_COLS - 1)
                + ("B" in removed and r == 0) + ("T" in removed and r == top.ARRAY_ROWS - 1)
            )
    return n


def transfer(open_sides: dict[tuple[int, int], int], assignment: dict) -> dict:
    """Systematic DNL/INL (LSB per +1 % of eps) and gain shift for one side."""
    group_sum = [0.0] * 9
    dummy = 0.0
    for pos, g in assignment.items():
        e = 0.01 * open_sides[pos]  # eps = 1 %
        if g == "term":
            dummy += e
        else:
            group_sum[top.WEIGHT_ORDER[::-1].index(int(g))] += e
    weights = [2.0**k for k in range(9)]
    v = [sum(((c >> k) & 1) * (weights[k] + group_sum[k]) for k in range(9)) for c in range(512)]
    inl = [v[c] - v[0] - c / 511.0 * (v[-1] - v[0]) for c in range(512)]
    dnl = [v[c] - v[c - 1] - 1.0 for c in range(1, 512)]
    return {"max_dnl": max(abs(d) for d in dnl), "max_inl": max(abs(i) for i in inl),
            "gain_lsb": sum(group_sum) + dummy}


def sensitivity(layout_area: dict) -> list[dict]:
    groups = [(str(w), w) for w in top.WEIGHT_ORDER] + [("term", 1)]
    assignment = top.centroid_tiling(top.ARRAY_COLS, top.ARRAY_ROWS, groups)
    dnl_room = SPEC_LSB - K_SIGMA * SIGMA_MAX_DNL_LSB
    inl_room = SPEC_LSB - K_SIGMA * SIGMA_MAX_INL_LSB
    gain_room = SPEC_GAIN_LSB - K_SIGMA * SIGMA_GAIN_LSB
    rows = []
    for label, removed in (("keep ring", set()), ("trim L+R", {"L", "R"}),
                           ("trim B+T", {"B", "T"}), ("trim all four", {"L", "R", "B", "T"})):
        t = transfer(edge_open_sides(removed), assignment)
        # Both sides carry the same bias; the gain error sums over 1024 units.
        gain = 2 * t["gain_lsb"]
        w = layout_area["core_w_nm"] + (0 if "L" in removed else layout_area["ring_nm"]) \
            + (0 if "R" in removed else layout_area["ring_nm"])
        h = layout_area["core_h_nm"] + (0 if "B" in removed else layout_area["ring_nm"]) \
            + (0 if "T" in removed else layout_area["ring_nm"])
        rows.append({
            "option": label,
            "bbox_um": [w / 1000, h / 1000],
            "area_um2_per_side": w * h / 1e6,
            "area_saved_um2_both_sides": 2 * (layout_area["full_nm2"] - w * h) / 1e6,
            "dnl_lsb_per_pct_eps": t["max_dnl"],
            "inl_lsb_per_pct_eps": t["max_inl"],
            "gain_lsb_per_pct_eps": gain,
            "breakeven_eps_pct": {
                "dnl": dnl_room / t["max_dnl"] if t["max_dnl"] else None,
                "inl": inl_room / t["max_inl"] if t["max_inl"] else None,
                "gain": gain_room / gain if gain else None,
            },
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="also write the full result here")
    args = ap.parse_args()

    layout = kdb.Layout()
    layout.read(GDS)
    meas = [measure(layout, n) for n in ARRAYS]
    failures = []
    for m in meas:
        for axis in "xy":
            if abs(m[axis]["sum_nm"] - m[axis]["bbox_nm"]) > TOL_NM or m[axis]["other_nm"]:
                failures.append(f"{m['cell']} {axis}: split does not sum to bbox / extra features")
        w = m["bbox_nm"][2] - m["bbox_nm"][0]
        h = m["bbox_nm"][3] - m["bbox_nm"][1]
        if (w, h) != (m["x"]["sum_nm"], m["y"]["sum_nm"]):
            failures.append(f"{m['cell']}: bbox {w}x{h} != split sum")

    x, y = meas[0]["x"], meas[0]["y"]
    area = {"core_w_nm": x["core_nm"], "core_h_nm": y["core_nm"], "ring_nm": x["ring_low_nm"],
            "full_nm2": (x["core_nm"] + 2 * x["ring_low_nm"]) * (y["core_nm"] + 2 * y["ring_low_nm"])}
    nominal_w = top.ARRAY_COLS * top.UNIT_PITCH
    nominal_h = top.ARRAY_ROWS * top.UNIT_PITCH
    full_w = x["core_nm"] + x["ring_low_nm"] + x["ring_high_nm"]
    full_h = y["core_nm"] + y["ring_low_nm"] + y["ring_high_nm"]
    result = {
        "gds": os.path.relpath(GDS), "gds_sha256": hashlib.sha256(open(GDS, "rb").read()).hexdigest(),
        "unit_pitch_nm": top.UNIT_PITCH, "nominal_grid_nm": [nominal_w, nominal_h],
        "excess_vs_nominal_grid_nm": [full_w - nominal_w, full_h - nominal_h],
        "excess_area_um2_per_side": (full_w * full_h - nominal_w * nominal_h) / 1e6,
        "arrays": meas, "options": sensitivity(area),
        "random_margin_lsb": {
            "dnl": SPEC_LSB - K_SIGMA * SIGMA_MAX_DNL_LSB,
            "inl": SPEC_LSB - K_SIGMA * SIGMA_MAX_INL_LSB,
            "gain": SPEC_GAIN_LSB - K_SIGMA * SIGMA_GAIN_LSB},
        "failures": failures,
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as fh:
            fh.write(text + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
