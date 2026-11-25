#!/usr/bin/env python3
"""SAR-reserve placement fit check for the adc-top block (issue #667).

Asks whether the ringed SAR-logic reserve can sit in the empty right-column
region of the analog core instead of in a full-width band below it, and what
bounding box each placement would give. It reads the committed
`adc_block.gds` and `area.json`, draws nothing and writes nothing.

Run with the interpreter `klt` uses (it carries `klayout.db`):

    KP="$(dirname "$(readlink -f "$(command -v klt)")")/python"
    "$KP" layout/adc-top/candidates/sar_reserve_placement.py

Every figure it prints is arithmetic on instance bounding boxes, not a
drawn-and-extracted layout: no candidate GDS exists, so neither `klt economy`
nor DRC/LVS was run on any candidate. The DRC-sensitive inputs (ring width,
ring-to-device offset, the 20 um gap) are taken from the committed layout.
"""

from __future__ import annotations

import json
import os
import sys

import klayout.db as db

HERE = os.path.dirname(os.path.abspath(__file__))
ADC = os.path.dirname(HERE)
T_UM = 4.46  # ring outer edge to device bbox, worst side measured (left)
GAP_UM = 20.0  # gen_adc_top.ANALOG_DIGITAL_GAP, kept (DR-0008)


def main() -> None:
    gds = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ADC, "adc_block.gds")
    ly = db.Layout()
    ly.read(gds)
    top = ly.cell("ADC_BLOCK")
    dbu = ly.dbu

    def um(v: int) -> float:
        return v * dbu

    area = json.load(open(os.path.join(ADC, "area.json")))["areas_um2"]
    rw, rh = 202.0, area["sar_logic_reserved"] / 202.0  # ringed reserve, outer

    insts = [i.bbox() for i in top.each_inst()]
    dev = insts[0].dup()
    for b in insts[1:]:
        dev += b
    bbox = top.bbox()
    # Analog ring outer edge = block bbox on L/R/T; the reserve band is the
    # only thing below it, so the ring bottom is the lowest instance edge
    # minus the same offset.
    t = T_UM
    assert abs(um(dev.left - bbox.left) - T_UM) < 0.01
    print(f"block bbox        {um(bbox.width()):.2f} x {um(bbox.height()):.2f}  "
          f"= {um(bbox.width()) * um(bbox.height()):.1f} um2")
    print(f"device union      x {um(dev.left):.2f}..{um(dev.right):.2f}  "
          f"y {um(dev.bottom):.2f}..{um(dev.top):.2f}")
    print(f"ring offset t     {t:.3f} um (ring outer edge to device bbox, left side)")
    print(f"ringed reserve    {rw:.1f} x {rh:.1f} um (area.json sar_logic_reserved)")

    # Core ring outer box: L/R/T are the block bbox; its height comes from
    # area.json (the reserve band is everything below it).
    cw = um(bbox.width())
    ch = area["analog_core_with_guard_ring"] / cw
    core_left, core_right, core_top = um(bbox.left), um(bbox.right), um(bbox.top)
    print(f"analog core ring  {cw:.2f} x {ch:.2f} = {cw * ch:.1f} um2 (area.json)")

    # Hole walls, from instance bboxes: CDAC arrays (216.4 um wide) bound the
    # top-right hole on the left, the comparator bounds it below; the decode
    # banks (441 um wide) bound the bottom-right hole on the left.
    arrays = [b for b in insts if 200000 < b.width() < 230000]
    banks = [b for b in insts if b.width() > 400000]
    arrays_right = um(max(b.right for b in arrays))
    bank_right = um(max(b.right for b in banks))
    cmp_top = um(max(b.top for b in insts if b.width() < 100000 and b.height() < 100000))
    print(f"hole walls: arrays right {arrays_right:.2f}, banks right {bank_right:.2f}, "
          f"comparator top {cmp_top:.2f}")

    cands = [("current (band below)", cw, um(bbox.height()))]
    cands.append(("beside core, no notch", cw + GAP_UM + rw, max(ch, rh)))
    for name, xn in (("top-right notch", arrays_right), ("bottom-right notch", bank_right)):
        left = xn + T_UM + GAP_UM
        width = max(core_right, left + rw) - core_left
        cands.append((name, width, ch))
    # Vertical fit: top-right hole is 'comparator top .. core top'.
    floor = cmp_top + T_UM + GAP_UM
    print(f"top-right hole vertical: need {rh:.1f}, have {core_top - floor:.1f} um")

    print(f"\n{'candidate':44s} {'W um':>8s} {'H um':>8s} {'area um2':>10s}")
    for n, w, h in cands:
        print(f"{n:44s} {w:8.2f} {h:8.2f} {w * h:10.1f}")
    hole_w = core_right - arrays_right - 2 * t
    print(f"\nhole width inside ring (top-right): {hole_w:.1f} um; "
          f"needs {rw + GAP_UM + t:.1f} um (ring + gap + offset) to fit w/o overhang")


if __name__ == "__main__":
    main()
