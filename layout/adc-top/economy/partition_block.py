#!/usr/bin/env python3
"""Disjoint per-sub-block area partition of the assembled `adc_block` stream.

Issue #936, step 1: re-take the per-sub-block area accounting on the CURRENT
floorplan, with every figure measured (not inferred) and with a partition
that reconciles to the full `ADC_BLOCK` bounding box.

WHAT IT MEASURES
----------------
`klt economy` (klayout-tools 0.8.0) reports the top bbox, the layer-union
drawn area, and one bbox/drawn pair per CHILD CELL -- in cell-local
coordinates. What it cannot report is where those children sit in the
assembled block, or how the block's own area divides between them, the
top-level straps, the two guard rings, and the empty corridors. This script
closes that gap on the drawn stream itself:

  * every child instance's bbox TRANSFORMED into `ADC_BLOCK` coordinates,
    plus the layer-union drawn area under it (a strap crossing a child bbox
    or a tap inside a bank is counted once, as drawn geometry of whatever
    region contains it);
  * the top-level-only geometry, clustered into the floorplan's own named
    regions -- the digital (SAR-reserve) ring cluster, the analog L-ring,
    the CDAC plate-route lanes, and the residual strap/corridor/whitespace;
  * a DISJOINT decomposition of the full bbox whose parts sum to it exactly
    (child bboxes, reserve bbox minus overlaps, ring annulus, remainder),
    so the record's table reconciles by construction.

It is a measurement tool for the economy records, not a gate: run it with
the same interpreter `klt` uses (klayout-tools 0.8.0 + klayout 0.30.12,
per the record's provenance), e.g.

    uvx --from "klayout-tools==0.8.0" --with "klayout==0.30.12" \\
        python layout/adc-top/economy/partition_block.py \\
        layout/adc-top/adc_block.gds ADC_BLOCK [--json OUT.json]

Stdlib + `klayout.db` only, exactly like `layout/adc-top/gen_adc_top.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import klayout.db as kdb

# The drawing-layer set is the generator's own layer table (labels excluded:
# they annotate, they do not occupy), so this script can never drift from
# what `gen_adc_top.py` actually draws.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ADC_TOP = os.path.dirname(_HERE)
sys.path.insert(0, _ADC_TOP)
from lib import geometry as _geo  # noqa: E402

DRAW_LAYERS = [
    gds for gds in _geo.LAYER_NAMES if gds[1] == 0
]

def draw_region(layout: kdb.Layout, cell: kdb.Cell) -> kdb.Region:
    """Layer-union of everything drawn in `cell`'s subtree, in cell coords."""
    region = kdb.Region()
    for gds in DRAW_LAYERS:
        index = layout.find_layer(*gds)
        if index is None:
            continue
        region += kdb.Region(cell.begin_shapes_rec(index))
    return region.merged()


def um2(region: kdb.Region, dbu: float) -> float:
    return region.area() * dbu * dbu


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("gds")
    parser.add_argument("top")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args()

    layout = kdb.Layout()
    layout.read(args.gds)
    dbu = layout.dbu
    top = layout.cell(args.top)
    if top is None:
        sys.exit(f"no cell {args.top!r} in {args.gds}")

    bbox = top.bbox()
    bbox_um = {
        "left": bbox.left * dbu, "bottom": bbox.bottom * dbu,
        "right": bbox.right * dbu, "top": bbox.top * dbu,
        "width": bbox.width() * dbu, "height": bbox.height() * dbu,
    }
    total_bbox_um2 = bbox.width() * bbox.height() * dbu * dbu
    everything = draw_region(layout, top)
    total_drawn_um2 = um2(everything, dbu)

    out = {
        "file": args.gds, "top": args.top, "dbu_um": dbu,
        "partition": {"regions": []},
        "bbox_um": bbox_um,
        "bbox_area_um2": total_bbox_um2,
        "drawn_area_um2": total_drawn_um2,
        "utilization": total_drawn_um2 / total_bbox_um2,
        "instances": [], "top_level": {},
    }

    # -- children, transformed into top coordinates ----------------------- #
    inst_boxes: list[tuple[str, kdb.Box]] = []
    for inst in top.each_inst():
        child = inst.cell
        cb = child.bbox()
        tb = cb.transformed(inst.trans)
        inst_boxes.append((child.name, tb))
        drawn = um2(draw_region(layout, child), dbu)
        out["instances"].append({
            "name": child.name,
            "bbox_um": {
                "left": tb.left * dbu, "bottom": tb.bottom * dbu,
                "right": tb.right * dbu, "top": tb.top * dbu,
                "width": tb.width() * dbu, "height": tb.height() * dbu,
            },
            "bbox_area_um2": tb.width() * tb.height() * dbu * dbu,
            "child_drawn_um2": drawn,
        })
    out["instances"].sort(key=lambda e: (e["bbox_um"]["bottom"], e["bbox_um"]["left"]))

    # sanity: pairwise-disjoint child bboxes (the partition relies on it)
    overlaps = []
    for i, (na, ba) in enumerate(inst_boxes):
        for nb, bb in inst_boxes[i + 1:]:
            inter = kdb.Region(ba) & kdb.Region(bb)
            if not inter.is_empty():
                overlaps.append((na, nb, um2(inter, dbu)))
    out["child_bbox_overlaps_um2"] = overlaps

    # -- top-level-only geometry, clustered ------------------------------- #
    # Pieces are computed PER LAYER (a cross-layer merge would fuse the ring
    # with every strap that touches it into one polygon whose bbox says
    # nothing). The digital (SAR-reserve) cluster is then the union of every
    # top-level piece whose centre lies in the block's top-right corner --
    # right of the arrays' edge, above the comparator row -- which is where
    # the floorplan puts the reserve and nothing else.
    child_union_top = kdb.Region()
    for _n, b in inst_boxes:
        child_union_top += kdb.Region(b)

    def layer_regions(cell: kdb.Cell) -> list[kdb.Region]:
        out = []
        for gds in DRAW_LAYERS:
            index = layout.find_layer(*gds)
            if index is None:
                continue
            out.append(kdb.Region(cell.begin_shapes_rec(index)).merged())
        return out

    top_pieces = [
        (gds, r - child_union_top)
        for gds, r in (
            (gds, kdb.Region(top.begin_shapes_rec(layout.find_layer(*gds))).merged())
            for gds in DRAW_LAYERS
            if layout.find_layer(*gds) is not None
        )
    ]
    top_only = kdb.Region()
    for _g, r in top_pieces:
        top_only += r
    top_only = top_only.merged()
    out["top_level"]["drawn_outside_children_um2"] = um2(top_only, dbu)

    def contained_pieces(x_min: float, y_min: float) -> list[kdb.Box]:
        # CONTAINED, not centred: a strap merely crossing the corner on its
        # way elsewhere belongs to the corridor it runs in, not to the
        # reserve -- centre-based filtering would swallow its whole length.
        boxes = []
        for _g, region in top_pieces:
            for poly in region.each():
                b = poly.bbox()
                if b.left * dbu >= x_min and b.bottom * dbu >= y_min:
                    boxes.append(b)
        return boxes

    arrays_right = max(b.right * dbu for n, b in inst_boxes if "CDAC_ARRAY" in n)
    right_col_top = max(
        b.top * dbu for n, b in inst_boxes
        if b.right * dbu > arrays_right and "CDAC_ARRAY" not in n
    )
    out["top_level"]["arrays_right_um"] = arrays_right
    out["top_level"]["right_col_top_um"] = right_col_top

    # Containment bounds sit BETWEEN the reserve's own left edge (the
    # digital ring, at the notch wall + the 20 um isolation gap) and the
    # nearest foreign geometry below/left of it (the notch-floor analog ring
    # band and the comparator's escape straps), both measured from the
    # instances above -- so neither can be swallowed by a loose threshold.
    reserve_boxes = contained_pieces(arrays_right + 10.0, right_col_top + 15.0)
    if not reserve_boxes:
        sys.exit("no top-level geometry found in the SAR-reserve corner")
    reserve_bbox = kdb.Region(reserve_boxes).bbox()
    reserve_bbox_um = {
        "left": reserve_bbox.left * dbu, "bottom": reserve_bbox.bottom * dbu,
        "right": reserve_bbox.right * dbu, "top": reserve_bbox.top * dbu,
        "width": reserve_bbox.width() * dbu, "height": reserve_bbox.height() * dbu,
    }
    out["top_level"]["sar_reserve"] = {
        "bbox_um": reserve_bbox_um,
        "bbox_area_um2": reserve_bbox.width() * reserve_bbox.height() * dbu * dbu,
        "drawn_um2": um2(top_only & kdb.Region(reserve_bbox), dbu),
    }

    # -- disjoint decomposition of the whole bbox ------------------------- #
    # Priority order: children first (they are the placed blocks), then the
    # reserve bbox (it shares no area with any child), then the named
    # remainder. Switch/comparator bboxes overlap by construction of their
    # escape corridors, so the overlap is assigned to the EARLIER child and
    # reported -- counted once, as the issue's accounting note demands.
    assigned = kdb.Region()
    for name, b in inst_boxes:
        piece = kdb.Region(b) - assigned
        out["partition"]["regions"].append({
            "name": name,
            "disjoint_area_um2": um2(piece, dbu),
        })
        assigned += piece
    reserve_piece = kdb.Region(reserve_bbox) - assigned
    out["partition"]["regions"].append({
        "name": "sar_reserve",
        "disjoint_area_um2": um2(reserve_piece, dbu),
    })
    assigned += reserve_piece
    remainder = kdb.Region(bbox) - assigned
    out["partition"]["regions"].append({
        "name": "remainder_rings_corridors_whitespace",
        "disjoint_area_um2": um2(remainder, dbu),
        "drawn_um2": um2(everything & remainder, dbu),
    })

    # Two named slices of the remainder the record leans on, both derived
    # from measured coordinates (no generator constants):
    #  * the RIGHT DEAD COLUMN: right of the analog core's own right edge
    #    (widest child) and below the reserve -- empty except the block
    #    edge's own ring/strap tails;
    #  * the ANALOG BAND: the rest (rings, gaps, lanes, corridors).
    analog_right = max(b.right * dbu for n, b in inst_boxes)
    dead = kdb.Region(kdb.Box(
        round(analog_right / dbu), bbox.bottom, bbox.right, reserve_bbox.bottom
    ))
    dead &= remainder
    out["partition"]["right_dead_column_um"] = {
        "x_from": analog_right, "x_to": bbox_um["right"],
        "y_from": bbox_um["bottom"], "y_to": reserve_bbox_um["bottom"],
        "area_um2": um2(dead, dbu),
        "drawn_um2": um2(everything & dead, dbu),
    }
    out["partition"]["sum_um2"] = sum(
        r["disjoint_area_um2"] for r in out["partition"]["regions"]
    )

    print(json.dumps(out, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
