#!/usr/bin/env python3
"""Reproducible area-recovery feasibility sweep for the adc-top block (issue #80).

Issue #70 drew the CDAC unit capacitor at its ratified geometry
(`C_u` = 17.24 fF, 2.7136 um plate) with the two MiM enclosure/space rules the
pinned deck now checks (`MIMTM.1`/`MIMTM.3`), which forces the legal unit-tile
pitch to 5.1136 um and pushed the assembled `adc_block` bounding box to
0.12100 mm^2 -- 121 % of the ratified `< 0.1 mm^2` DR-0006 area target.

Issue #80 asks whether that overrun can be recovered by a *legal* floorplan
change -- i.e. without shrinking the MiM plate below its ratified device
geometry (a silent spec relaxation `CLAUDE.md` forbids) and without shrinking
the decode bank below the `comp.space.1` DRC floor issue #69 already took it
to. This script quantifies the two floorplan levers issue #80 names
(CDAC-array aspect ratio, and the block's own packing floor) so the conclusion
is checkable rather than asserted.

Issue #177 adds the *third* lever the other two deliberately hold fixed: the
unit-cap PLATE side itself. `spec/decision-records/
DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md` resizes `C_u` upward to
meet the gain-error matching constraint, and that resize has to have its area
cost stated in re-runnable form rather than asserted -- hence `unit_cap_sweep`
below. Note the direction: issue #80 forbids shrinking the plate below its
ratified geometry (a silent spec relaxation), and DR-0019 only ever grows it,
so nothing here relaxes anything -- it quantifies what growing it costs.

Run with the same interpreter `klt` uses (it carries the `klayout.db` module):

    KP="$(dirname "$(readlink -f "$(command -v klt)")")/python"
    PYTHONPATH=layout/adc-top "$KP" layout/adc-top/area_feasibility.py

Optional positional arguments override the unit-cap plate sides (in nm, on the
1 nm database grid) the third section sweeps -- e.g. `... area_feasibility.py
2714 4000` for just the as-drawn and DR-0019 geometries.

It draws nothing and writes nothing; it only rebuilds the block in-memory at
each candidate aspect ratio / plate size and reports the resulting bounding-box
area. It runs no DRC: a bounding box at a plate size the layout has not been
redrawn at is an area *estimate*, not a legality claim.
"""

from __future__ import annotations

import os
import sys

_PLATE_ARGV = sys.argv[1:]  # captured before the reset below
sys.argv = [sys.argv[0]]  # gen_adc_top.main() parses argv; keep it inert on import

import gen_adc_top as g  # noqa: E402
import lib.geometry as geo  # noqa: E402
import lib.netlist as nl  # noqa: E402

BUDGET_UM2 = 100_000.0  # DR-0006 ratified `< 0.1 mm^2` area target

#: CDAC unit-cap PLATE sides (nm) issue #177 / DR-0019 weighs against each
#: other. 2714 is the as-drawn geometry (`C_u` = 17.24 fF, sized to DNL/INL's
#: own matching coefficient); 3840 is the gain-error constraint's
#: exact-boundary sizing (`sigma_u` = 0.5208 %, `C_u` = 33.00 fF); 4000 is
#: DR-0019's chosen sizing (`sigma_u` = 0.5000 %, `C_u` = 35.6528 fF), taken
#: for margin over the boundary. See `spec/cdac-sizing-memo.md` Sec 3.6/Sec 4.
UNIT_CAP_CANDIDATES_NM = (2714, 3840, 4000)
AS_DRAWN_PLATE_NM = 2714


def _load() -> tuple[dict, dict]:
    design = nl.design_dir(g.HERE)
    subckts = nl.parse(os.path.join(design, "adc-top", "adc_top.spice"))
    g.block_subckt(subckts)
    comparator = nl.parse(os.path.join(design, "comparator", "comparator.spice"))
    return subckts, comparator


def aspect_sweep(subckts: dict, comparator: dict) -> None:
    """Rebuild `adc_block` at every factor pair of 512 = ARRAY_COLS x ARRAY_ROWS.

    The array is common-centroid tiled over `cols x rows == 512` unit positions;
    only the factor pairs are legal shapes. 32 x 16 is what the block ships.
    """
    print("CDAC-array aspect ratio sweep (adc_block bounding box):")
    print(f"  {'cols x rows':>11} | {'block WxH (um)':>18} | {'area (mm^2)':>11} | vs budget")
    saved = (g.ARRAY_COLS, g.ARRAY_ROWS)
    pairs = [(512 // r, r) for r in (16, 32, 8, 64, 4, 128, 2, 256)]
    for cols, rows in pairs:
        g.ARRAY_COLS, g.ARRAY_ROWS = cols, rows
        try:
            _, info = g.build(subckts, comparator, cell_name=g.BLOCK_CELL_NAME)
        except Exception as exc:  # noqa: BLE001 - report, do not abort the sweep
            print(f"  {cols:>4} x {rows:<4} | {'build failed':>18} | "
                  f"{type(exc).__name__}: {str(exc)[:40]}")
            continue
        w, h = info["dimensions_um"]["block"]
        area = info["areas"]["block_total"]
        flag = "SHIP" if (cols, rows) == (32, 16) else ""
        print(f"  {cols:>4} x {rows:<4} | {w:>8.1f} x {h:<7.1f} | {area/1e6:>11.5f} | "
              f"{100*area/BUDGET_UM2:>5.0f} % {flag}")
    g.ARRAY_COLS, g.ARRAY_ROWS = saved


def packing_floor(subckts: dict, comparator: dict) -> None:
    """The block's irreducible width x height product at the shipped aspect ratio.

    The decode bank is one row of 144 single-finger devices at the
    `comp.space.1`-floored column pitch issue #69 established, so its width is
    a DRC floor, not a choice. The block height is the analog stack (two decode
    banks + the DRM-floored CDAC array + region gaps + guard ring) plus the
    DR-0008/DR-0010 mandated analog/digital isolation gap and SAR-logic reserve.
    Their product bounds the block area from below independently of any
    whitespace, comparator overhang, or corridor packing -- so if it already
    exceeds the budget, no legal packing pass can get under it.
    """
    _, info = g.build(subckts, comparator, cell_name=g.BLOCK_CELL_NAME)
    bank_w = info["dimensions_um"]["decode_bank"][0]
    block_h = info["dimensions_um"]["block"][1]
    floor = bank_w * block_h
    print("\nIrreducible packing floor (shipped 32 x 16 aspect ratio):")
    print(f"  decode-bank width  (comp.space.1 DRC floor, issue #69): {bank_w:.2f} um")
    print(f"  block height       (analog stack + DR-0008/0010 reserve): {block_h:.2f} um")
    print(f"  width x height floor                                    : {floor:,.0f} um^2")
    print(f"  DR-0006 budget                                          : {BUDGET_UM2:,.0f} um^2")
    over = floor - BUDGET_UM2
    verdict = "OVER budget" if over > 0 else "within budget"
    print(f"  => floor is {verdict} by {abs(over):,.0f} um^2 "
          f"({100*floor/BUDGET_UM2:.0f} %), before any whitespace or comparator overhang")


def unit_cap_sweep(subckts: dict, comparator: dict, plates_nm=None) -> None:
    """Rebuild `adc_block` at each candidate CDAC unit-cap plate side (issue #177).

    The array's whole area cost is the DRM-set tile pitch, not the plate: a
    `s`-wide plate tiles at `s + 2 x MIMTM.3 + MIMTM.1` = `s + 2.4 um`
    (`lib.geometry.mim_pitch`). So the block area grows *sub*-quadratically in
    `C_u` -- which is exactly why DR-0019's resize costs far less area than the
    ~2x capacitance ratio would suggest, and why that has to be measured here
    rather than extrapolated from the capacitance.

    Only `g.UNIT_CAP_NM` / `g.UNIT_PITCH` are overridden (module state is
    restored afterwards); the parsed netlist is untouched, so this reports the
    *floorplan* cost of a larger unit cap, not a re-netlisted design.
    """
    plates = tuple(plates_nm or UNIT_CAP_CANDIDATES_NM)
    saved = (g.UNIT_CAP_NM, g.UNIT_PITCH)
    baseline_area = None
    print("\nCDAC unit-cap plate sweep (adc_block bounding box, issue #177/DR-0019):")
    print(f"  {'plate (um)':>10} | {'pitch (um)':>10} | {'block WxH (um)':>18} | "
          f"{'area (mm^2)':>11} | vs budget | vs as-drawn")
    for plate in plates:
        g.UNIT_CAP_NM = plate
        g.UNIT_PITCH = geo.mim_pitch(plate, plate)[0]
        try:
            _, info = g.build(subckts, comparator, cell_name=g.BLOCK_CELL_NAME)
        except Exception as exc:  # noqa: BLE001 - report, do not abort the sweep
            print(f"  {plate/1000:>10.4f} | {'-':>10} | {'build failed':>18} | "
                  f"{type(exc).__name__}: {str(exc)[:40]}")
            continue
        w, h = info["dimensions_um"]["block"]
        area = info["areas"]["block_total"]
        if plate == AS_DRAWN_PLATE_NM:
            baseline_area = area
        delta = "as-drawn" if baseline_area is not None and area == baseline_area else (
            f"{100*area/baseline_area - 100:+5.1f} %" if baseline_area else "n/a")
        print(f"  {plate/1000:>10.4f} | {g.UNIT_PITCH/1000:>10.4f} | "
              f"{w:>8.1f} x {h:<7.1f} | {area/1e6:>11.5f} | "
              f"{100*area/BUDGET_UM2:>5.0f} %    | {delta:>9}")
    g.UNIT_CAP_NM, g.UNIT_PITCH = saved
    print("  (bounding-box estimates only -- no DRC is run at any plate size "
          "the layout has not been redrawn at)")


def main() -> None:
    subckts, comparator = _load()
    aspect_sweep(subckts, comparator)
    packing_floor(subckts, comparator)
    unit_cap_sweep(subckts, comparator,
                   [int(a) for a in _PLATE_ARGV] or None)


if __name__ == "__main__":
    main()
