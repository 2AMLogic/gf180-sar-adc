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

Run with the same interpreter `klt` uses (it carries the `klayout.db` module):

    KP="$(dirname "$(readlink -f "$(command -v klt)")")/python"
    PYTHONPATH=layout/adc-top "$KP" layout/adc-top/area_feasibility.py

It draws nothing and writes nothing; it only rebuilds the block in-memory at
each candidate aspect ratio and reports the resulting bounding-box area.
"""

from __future__ import annotations

import os
import sys

sys.argv = [sys.argv[0]]  # gen_adc_top.main() parses argv; keep it inert on import

import gen_adc_top as g  # noqa: E402
import lib.netlist as nl  # noqa: E402

BUDGET_UM2 = 100_000.0  # DR-0006 ratified `< 0.1 mm^2` area target


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


def main() -> None:
    subckts, comparator = _load()
    aspect_sweep(subckts, comparator)
    packing_floor(subckts, comparator)


if __name__ == "__main__":
    main()
