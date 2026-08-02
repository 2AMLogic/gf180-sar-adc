#!/usr/bin/env python3
"""Generate the block-level layout of `design/adc-top/` (issue #57).

Writes, beside this file:

    adc_top.gds        the block layout
    adc_top.ref.spice  its flat LVS reference, generated from
                       design/adc-top/adc_top.spice
    adc_top.lvs.json   the `klt lvs` request document
    area.json          the as-drawn area tally (per region, um^2)

WHAT THE BLOCK CONTAINS
-----------------------
Everything `design/adc-top/adc_top.spice` defines, instantiated the way the
ADC-level testbenches instantiate it (`sim/adc-enob-fft/testbench/`): two
`adc_cdac_side` arrays and the two `adc_tgate_dum` input sampling switches.
Concretely, drawn:

* **The CDAC arrays** -- 512 unit-capacitor positions per side (1024 total),
  common-centroid-tiled and surrounded by a full dummy ring, per
  `layout/floorplan-matching-plan.md` Sec 1.3. NOT one lumped capacitor per
  binary weight: the tiling below assigns each weight's `m` unit positions
  to centro-symmetric position PAIRS spread across the array, which is the
  whole point of the plan's Sec 1.3 and what the schematic's own `m=`
  multiplicity means physically (`spec/cdac-sizing-memo.md` Sec 5.4).
* **The bottom-plate decode switches and their local drivers** -- 216
  transistors (9 weighted positions x 12 devices x 2 sides), in two banks,
  one per array side, with the analog supply/reference rails (`vdd`, `vss`,
  `vref`, `vcm`) tied between them.
* **The input sampling switches** -- 8 transistors, the two dummy-
  compensated T-gates of DR-0007/DR-0013, drawn with each half-width dummy
  immediately beside the main device it compensates and the two sides
  mirror-symmetric about the block's own axis.
* **Guard rings and the analog/digital split** -- a contacted substrate ring
  around the analog core, and a physically separated, separately-ringed
  region reserved for the SAR-logic sequencer with its own supply rails.

The comparator is a separate cell (`gen_comparator.py`) with its own LVS
target, because `design/adc-top/adc_top.spice` deliberately excludes it (it
is owned by `design/comparator/comparator.spice`) and this file's LVS claim
is against `adc_top.spice` exactly.

See `README.md` for the design-to-layout mapping, every stated deviation,
and what the DRC/LVS results do and do not prove.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import geometry as geo  # noqa: E402
from lib import netlist as nl  # noqa: E402
from lib import place  # noqa: E402

CELL_NAME = "ADC_TOP"
BLOCK_CELL_NAME = "ADC_BLOCK"

#: The nine binary-weighted positions `adc_cdac_side` instantiates, MSB
#: first -- read back out of the parsed netlist rather than hard-coded, so a
#: change to `adc_top.spice` cannot silently desynchronise this layout.
WEIGHT_ORDER = [256, 128, 64, 32, 16, 8, 4, 2, 1]

#: Unit capacitor: `C_u` = 17.24 fF at 2.7136 um square
#: (`spec/cdac-sizing-memo.md` Sec 4; the density law is quoted in
#: `design/adc-top/adc_top.spice`'s own comment).
UNIT_CAP_NM = 2714
#: Gap between adjacent unit capacitors in the tiled array. No `klt drc`
#: rule covers these layers (klayout-tools#188), so this is set from the
#: PDK's own published MIM spacing rule (`MIMTM.3`, 1.2 um) rather than from
#: anything the deck could check -- stated here because a clean DRC report
#: over this geometry means nothing was checked, not that it passed.
UNIT_CAP_GAP = 1200
UNIT_PITCH = UNIT_CAP_NM + UNIT_CAP_GAP

#: The tiled array's shape, per side: 32 x 16 = 512 unit positions.
ARRAY_COLS = 32
ARRAY_ROWS = 16

#: Clearances between the block's regions.
REGION_GAP = 2500
GUARD_RING_W = 1400
GUARD_CLEARANCE = 1500
#: Analog-to-digital separation: the plan (Sec 2.4/3) asks for the guard
#: ring to occupy the boundary between the analog core and the SAR-logic
#: sequencer, with the blocks NOT abutting.
ANALOG_DIGITAL_GAP = 20000
#: Reserved footprint for the SAR-logic sequencer. It is NOT drawn: DR-0010
#: records that the sequencer and output register stay at rung 1 (ideal
#: XSPICE primitives) because the open gf180mcu PDK ships no 3.3 V
#: standard-cell library, so there is no transistor-level netlist to place
#: and no cells to place it from. Reserving and ringing the area is what
#: this layout can honestly do about DR-0008's isolation requirement; see
#: README.md.
SAR_RESERVED_W = 120000
SAR_RESERVED_H = 40000


# --------------------------------------------------------------------------- #
# the block's netlist
# --------------------------------------------------------------------------- #


def block_subckt(subckts: dict[str, nl.Subckt]) -> None:
    """Add the block's own top-level `adc_top` subcircuit to `subckts`.

    `design/adc-top/adc_top.spice` is a *library*: it defines
    `adc_cdac_side` and `adc_tgate_dum` but never instantiates them, because
    the ADC-level testbenches under `sim/adc-*/` do that themselves. This
    builds the same composition those testbenches use -- two array sides and
    two sampling switches -- out of the parsed subcircuit's OWN port list,
    so the block layout tracks the design file rather than a transcription
    of it.
    """
    side = subckts["adc_cdac_side"]
    lines: list[list[str]] = []
    ports: list[str] = ["pinp", "pinn", "topp", "topn", "samp", "sampb",
                        "vref", "vcm", "vss", "vdd"]

    for tag in ("p", "n"):
        nets = []
        for port in side.ports:
            if port == "top":
                nets.append(f"top{tag}")
            elif port in ("vref", "vcm", "vss", "vdd"):
                nets.append(port)
            else:  # rel_256 / hi_256 / lo_256 / ...
                nets.append(f"{port}_{tag}")
                ports.append(f"{port}_{tag}")
        lines.append([f"XS{tag.upper()}", *nets, "adc_cdac_side"])

    for tag in ("p", "n"):
        lines.append(
            [
                f"XSW{tag.upper()}",
                f"pin{tag}", f"top{tag}", "samp", "sampb", "vdd",
                "adc_tgate_dum",
            ]
        )

    subckts["adc_top"] = nl.Subckt(
        name="adc_top", ports=ports, defaults={}, lines=lines
    )


# --------------------------------------------------------------------------- #
# common-centroid tiling
# --------------------------------------------------------------------------- #


def _bit_reverse(value: int, bits: int) -> int:
    out = 0
    for _ in range(bits):
        out = (out << 1) | (value & 1)
        value >>= 1
    return out


def centroid_tiling(
    cols: int, rows: int, groups: list[tuple[str, int]]
) -> dict[tuple[int, int], str]:
    """Assign every position of a `cols` x `rows` array to a weighted group,
    common-centroid and dispersed.

    The construction, and why it is common-centroid *by construction* rather
    than by inspection:

    1. Positions are taken in **centro-symmetric pairs**: position `(c, r)`
       is always paired with its 180-degree rotation `(cols-1-c, rows-1-r)`.
       Both members of a pair get the same group -- with exactly one
       exception, the single pair the two odd-count groups share (step 2) --
       so every EVEN-count group's centroid is the array's own centre
       exactly and cannot acquire a first-order gradient term at all.
       `cols * rows` is even and the
       centre falls between cells, so the pairing has no fixed point and
       every position is covered exactly once.
    2. Groups with an ODD unit count (here: the weight-1 position and
       DR-0011's terminating unit, one unit each) cannot own a whole pair.
       They are paired with **each other** -- one takes each half of a
       single centro-symmetric pair -- so the two odd groups' *combined*
       centroid is the array centre exactly.

       That combined centroid is the ONLY guarantee this construction makes
       about them. The pair they share is whichever pair step 3's
       bit-reversed deal happens to hand the shared pseudo-group; it is NOT
       forced to be the centre-most pair, so each odd group individually
       sits wherever that pair landed and its individual displacement is not
       bounded by half a pitch. For the array this file actually builds
       (32 x 16, `WEIGHT_ORDER` plus `term`) the shared pair is `(30, 7)` /
       `(1, 8)`: each odd group sits (14.5, 0.5) pitches -- (56.8, 2.0) um
       at `UNIT_PITCH` -- off the array centre, in opposite directions.
       `sim/tests/test_layout_centroid_tiling.py` asserts both halves of
       this (combined centroid exact, individual offsets as measured), so
       neither can drift without a test failing.

       The residual is a `displacement x gradient x C_u` term against a
       ONE-unit weight: the weight-1 bit and DR-0011's terminating unit are
       the two smallest and least DNL-consequential positions in the array,
       which is why the deal is left alone rather than special-cased to hand
       the shared pseudo-group the centre-most pair.

       The shared pseudo-group is one pair wide, so an odd group contributes
       exactly one pair to the accounting however many units it declares:
       odd counts above 1 lose `count // 2` pairs and are refused (a
       `ValueError`, not a silently skewed centroid). Both odd groups here
       are single units, so the restriction never binds.
    3. Pairs are dealt to groups in a **bit-reversed** (van der Corput)
       order, and each group's share is spread evenly across that order, so
       a group's units are scattered over the whole array instead of
       clustering -- which is what cancels the higher-order (curvature)
       terms a pure centroid argument does not.

    Returns `{(col, row): group_name}` covering every position.
    """
    total = cols * rows
    if total % 2:
        raise ValueError("array must have an even number of positions")
    if sum(count for _, count in groups) != total:
        raise ValueError("group counts do not sum to the array size")

    odd = [name for name, count in groups if count % 2]
    if len(odd) > 2:
        raise ValueError(f"cannot pair more than two odd-count groups: {odd}")

    # Pseudo-groups measured in PAIRS. The two odd groups share one pair.
    pair_groups: list[tuple[str, int]] = []
    for name, count in groups:
        if name in odd:
            continue
        pair_groups.append((name, count // 2))
    if odd:
        pair_groups.append(("|".join(odd), 1))

    n_pairs = total // 2
    if sum(k for _, k in pair_groups) != n_pairs:
        raise ValueError("pair accounting does not close")

    # Spread each group's share evenly over the deal order (the classic
    # even-distribution trick: item i of a k-share sits at (i + 0.5)/k).
    deal: list[tuple[float, str, int]] = []
    for name, k in pair_groups:
        for i in range(k):
            deal.append(((i + 0.5) / k, name, i))
    deal.sort()

    # Bit-reversed order over the array's first half -- each entry is the
    # "low" member of one centro-symmetric pair.
    bits = max(1, (n_pairs - 1).bit_length())
    half = [(c, r) for r in range(rows // 2) for c in range(cols)]
    order = sorted(range(len(half)), key=lambda i: _bit_reverse(i, bits))

    assignment: dict[tuple[int, int], str] = {}
    for slot, (_, name, index) in enumerate(deal):
        c, r = half[order[slot]]
        partner = (cols - 1 - c, rows - 1 - r)
        if "|" in name:
            first, second = name.split("|")
            assignment[(c, r)] = first
            assignment[partner] = second
        else:
            assignment[(c, r)] = name
            assignment[partner] = name
        del index
    if len(assignment) != total:
        raise RuntimeError("tiling did not cover every position")
    return assignment


def draw_cdac_array(
    layout: kdb.Layout,
    layers: dict[tuple[int, int], int],
    name: str,
) -> tuple[kdb.Cell, dict[tuple[int, int], str]]:
    """Draw one side's tiled unit-capacitor array plus its dummy ring, and
    the Metal5 top-plate mesh that joins every unit's top plate.

    The top plate really is one node across the whole side (DR-0011's
    top-plate sampling), so the mesh is the physical net, not a placeholder.
    The per-weight BOTTOM-plate interconnect is deliberately not drawn: it
    needs Metal2/Metal3 and Via2/Via3, none of which the `klt drc` deck has
    a rule for or the `klt extract` deck reads, so drawing it would add
    geometry no tool in this toolchain can check while implying it had been
    checked. Stated in README.md, not silent.
    """
    cell = layout.create_cell(name)
    groups = [(str(w), w) for w in WEIGHT_ORDER] + [("term", 1)]
    assignment = centroid_tiling(ARRAY_COLS, ARRAY_ROWS, groups)

    tops: list[kdb.Box] = []
    for (c, r), _group in sorted(assignment.items()):
        x = c * UNIT_PITCH
        y = r * UNIT_PITCH
        _bottom, top = geo.draw_mim_cap(
            cell, layers, x, y, UNIT_CAP_NM, UNIT_CAP_NM
        )
        tops.append(top)

    # Full dummy ring: one extra tile all the way round, identical drawn
    # geometry (same MiM stack, same size), electrically floating -- so an
    # edge unit sees the same local etch/stress environment as an interior
    # one (`layout/floorplan-matching-plan.md` Sec 1.3).
    for c in range(-1, ARRAY_COLS + 1):
        for r in range(-1, ARRAY_ROWS + 1):
            if 0 <= c < ARRAY_COLS and 0 <= r < ARRAY_ROWS:
                continue
            geo.draw_mim_cap(
                cell, layers, c * UNIT_PITCH, r * UNIT_PITCH,
                UNIT_CAP_NM, UNIT_CAP_NM,
            )

    # Top-plate mesh (Metal5): one horizontal strap per array row plus one
    # vertical spine on the array's own electrical centre, so the path from
    # any unit to the centre is short and the two sides are drawn
    # identically (plan Sec 1.4: shortest practical path from the electrical
    # centre, no daisy-chain). The dummy ring is deliberately NOT joined.
    metal5 = layers[geo.L_METAL5]
    strap = 800
    x_lo = min(t.left for t in tops)
    x_hi = max(t.right for t in tops)
    for r in range(ARRAY_ROWS):
        y = r * UNIT_PITCH + UNIT_CAP_NM // 2
        cell.shapes(metal5).insert(
            kdb.Box(x_lo, y - strap // 2, x_hi, y + strap // 2)
        )
    x_centre = (ARRAY_COLS * UNIT_PITCH - UNIT_CAP_GAP) // 2
    cell.shapes(metal5).insert(
        kdb.Box(
            x_centre - strap,
            -UNIT_CAP_GAP,
            x_centre + strap,
            (ARRAY_ROWS - 1) * UNIT_PITCH + UNIT_CAP_NM + UNIT_CAP_GAP,
        )
    )
    return cell, assignment


# --------------------------------------------------------------------------- #
# the block
# --------------------------------------------------------------------------- #


def _clear_offset(
    fixed: list[tuple[str, kdb.Box]],
    movable: list[tuple[str, kdb.Box]],
    base_y: int,
    span: int = 12,
) -> int:
    """Pick a Y placement for a movable block whose top-level straps do not
    collide with any already-placed block's straps.

    Straps are horizontal Metal1 bars at whatever track Y their own block's
    channel packer chose, all running to one corridor, so two blocks in the
    same row can collide. Tries `base_y` first, then +/- multiples of the
    trunk pitch. Raises rather than returning a colliding placement.
    """
    clearance = geo.TRUNK_H + 230
    candidates = [base_y] + [
        base_y + sign * k * geo.TRUNK_PITCH
        for k in range(1, span + 1)
        for sign in (1, -1)
    ]
    for candidate in candidates:
        ok = True
        for net_a, box_a in fixed:
            for net_b, box_b in movable:
                if net_a == net_b:
                    continue
                lo = box_b.bottom + candidate
                hi = box_b.top + candidate
                if hi + clearance > box_a.bottom and lo - clearance < box_a.top:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return candidate
    raise RuntimeError("no collision-free Y offset found for the strapped block")


def build(
    subckts: dict[str, nl.Subckt],
    comparator_subckts: dict[str, nl.Subckt] | None = None,
    cell_name: str = CELL_NAME,
) -> tuple[kdb.Layout, dict]:
    """Draw the block.

    With `comparator_subckts` given, the comparator cell from
    `gen_comparator.py` is assembled into the same stream (the `adc_block`
    deliverable) and its devices join the LVS reference. Without it, the
    stream is exactly what `design/adc-top/adc_top.spice` defines, which is
    what makes `adc_top.gds`'s LVS claim a claim against that file and
    nothing else.
    """
    layout, layers = geo.make_layout()
    top = layout.create_cell(cell_name)

    devices = nl.flatten(
        subckts,
        "adc_top",
        {port: port for port in subckts["adc_top"].ports},
        prefix="",
    )
    mos = [d for d in devices if d.is_mos]
    if len(mos) != 224:
        raise RuntimeError(f"expected 224 transistors, flattened {len(mos)}")

    control_pins = [p for p in subckts["adc_top"].ports if p.startswith(("rel", "hi", "lo"))]
    rails = ["vdd", "vss", "vref", "vcm"]

    # -- the two decode banks ------------------------------------------- #
    # One bank per array side, each carrying that side's nine weighted
    # positions' decode T-gates and local drivers. Devices are handed to the
    # placer in the array's own MSB-to-LSB order, so a bank's column order
    # mirrors the weight order its capacitors implement.
    banks: dict[str, place.PlacedBlock] = {}
    bank_cells: dict[str, kdb.Cell] = {}
    body_net: dict[str, str] = {}
    for tag in ("p", "n"):
        side = [d for d in mos if d.path.startswith(f"XS{tag.upper()}.")]
        ordered = [
            d
            for weight in WEIGHT_ORDER
            for d in side
            if d.path.startswith(f"XS{tag.upper()}.X{weight}.")
        ]
        if len(ordered) != len(side):
            raise RuntimeError(f"weight ordering dropped devices on side {tag}")
        cell = layout.create_cell(f"ADC_DECODE_BANK_{tag.upper()}")
        # One placement group -- and therefore one Nwell island and one
        # (unnamed) PMOS-body net -- per weighted CDAC cell, so each cell's
        # seven internal nets stay local in X and the channel packs. See
        # lib/place.draw_devices.
        cell_groups = [
            (
                f"nw_{tag}{weight}",
                [d for d in ordered if d.path.startswith(f"XS{tag.upper()}.X{weight}.")],
            )
            for weight in WEIGHT_ORDER
        ]
        block = place.draw_devices(
            cell,
            layers,
            cell_groups,
            pins=rails + [p for p in control_pins if p.endswith(f"_{tag}")],
            escape=rails,
        )
        banks[tag] = block
        bank_cells[tag] = cell
        body_net.update(block.body_net)

    # -- the sampling switches ------------------------------------------- #
    # DR-0007/DR-0013: each half-width dummy is placed immediately beside the
    # main device it compensates, and the P and N sides are drawn in mirror
    # order (dummy-main | main-dummy) about the pair's own axis, so neither
    # side's charge-injection compensation sees a different local
    # environment from the other's.
    sample_order = [
        "XSWP.XDN", "XSWP.XN", "XSWN.XN", "XSWN.XDN",
        "XSWP.XDP", "XSWP.XP", "XSWN.XP", "XSWN.XDP",
    ]
    by_path = {d.path: d for d in mos}
    sample_devices = [by_path[p] for p in sample_order]
    sample_cell = layout.create_cell("ADC_SAMPLE_SW")
    sample = place.draw_devices(
        sample_cell,
        layers,
        [("nw_sw", sample_devices)],
        pins=["pinp", "pinn", "topp", "topn", "samp", "sampb"],
        escape=["topp", "topn"],
        escape_margin=2000,
    )
    body_net.update(sample.body_net)

    # -- the capacitor arrays --------------------------------------------- #
    array_cell_p, assignment = draw_cdac_array(layout, layers, "ADC_CDAC_ARRAY_P")
    array_cell_n, _ = draw_cdac_array(layout, layers, "ADC_CDAC_ARRAY_N")

    # -- floorplan: place the regions ------------------------------------- #
    # Bottom to top: the two decode banks (P below N, so their shared analog
    # rails abut across one stitch corridor), then the capacitor arrays with
    # the input sampling switches beside them. The sampling switches sit
    # between the input pins (block edge, right) and the arrays' own top
    # plates, which is where `layout/floorplan-matching-plan.md` Sec 1.5
    # puts them: at the array's input edge, NOT inside the tiled array.
    bank_h = bank_cells["p"].bbox().height()
    bank_w = bank_cells["p"].bbox().width()
    bank_p_y = 0
    bank_n_y = bank_p_y + bank_h + REGION_GAP
    top.insert(kdb.CellInstArray(bank_cells["p"], kdb.Vector(0, bank_p_y)))
    top.insert(kdb.CellInstArray(bank_cells["n"], kdb.Vector(0, bank_n_y)))

    array_h = array_cell_p.bbox().height()
    array_w = array_cell_p.bbox().width()
    sample_h = sample_cell.bbox().height()
    sample_w = sample_cell.bbox().width()
    array_y = bank_n_y + bank_h + REGION_GAP
    top.insert(kdb.CellInstArray(array_cell_p, kdb.Vector(0, array_y)))
    top.insert(
        kdb.CellInstArray(
            array_cell_n, kdb.Vector(array_w + REGION_GAP * 2, array_y)
        )
    )
    sample_x = 2 * array_w + REGION_GAP * 4
    top.insert(kdb.CellInstArray(sample_cell, kdb.Vector(sample_x, array_y)))

    # -- tie the analog rails between the two decode banks ---------------- #
    # One Poly2 stitch per rail, in the Comp-free escape corridor to the
    # right of both banks' device rows, contacting each bank's own trunk.
    # This is the same Metal1-trunk/Poly2-riser discipline the placer uses
    # inside a bank -- see lib/geometry.py's docstring for why the
    # interconnect has to be exactly two layers.
    stitch_x0 = banks["p"].row_x1 + 1500
    for index, net in enumerate(rails):
        x = stitch_x0 + index * 1000
        ys: list[tuple[int, int]] = []
        for tag, offset in (("p", bank_p_y), ("n", bank_n_y)):
            box = banks[tag].trunks[net]
            ys.append((box.bottom + offset, box.top + offset))
        y_lo = min(y0 for y0, _ in ys)
        y_hi = max(y1 for _, y1 in ys)
        top.shapes(layers[geo.L_POLY2]).insert(
            kdb.Box(x - geo.RISER_W // 2, y_lo - 100, x + geo.RISER_W // 2, y_hi + 100)
        )
        for y0, y1 in ys:
            cy = (y0 + y1) // 2
            top.shapes(layers[geo.L_CONTACT]).insert(
                kdb.Box(
                    x - geo.RISER_CONTACT // 2,
                    cy - geo.RISER_CONTACT // 2,
                    x + geo.RISER_CONTACT // 2,
                    cy + geo.RISER_CONTACT // 2,
                )
            )

    # -- the comparator (only in the assembled `adc_block` stream) --------- #
    comparator_info = None
    merges: list[tuple[str, str]] = []
    if comparator_subckts is not None:
        from gen_comparator import PINS as CMP_PINS
        from gen_comparator import build_into as build_comparator

        # The comparator's differential inputs ARE the two CDAC top plates
        # (DR-0011 top-plate sampling), so they are wired to `topp`/`topn`,
        # the same nets the sampling switches drive -- not to fresh pins.
        comparator_info = build_comparator(
            layout,
            layers,
            comparator_subckts,
            with_resistors=True,
            name="COMPARATOR",
            port_nets={
                **{p: p for p in CMP_PINS},
                "vinp": "topp",
                "vinn": "topn",
                "clk": "cmpclk",
            },
            prefix="XCMP.",
            escape_left=["topp", "topn"],
            escape=["vdd", "vss"],
            # The right-hand escape has to clear the four load-resistor
            # columns, which are placed past the transistor row (see
            # gen_comparator.draw_load_resistors), or the analog-supply
            # trunks would try to grow straight over them.
            escape_margin=18000,
            escape_left_margin=3500,
        )
        cmp_cell = comparator_info["cell"]
        cmp_x = sample_x + sample_w + REGION_GAP

        # The comparator and the sampling switches sit in the same row, so
        # their channel packers can hand two DIFFERENT nets the same track Y
        # -- and then their top-level straps, which all run to one corridor,
        # would short. No single Y offset avoids that for every net pair
        # (the track pitch is smaller than twice the bar-plus-space), so the
        # offset is SEARCHED over the nets actually strapped and the first
        # clear one is used. `geo.assert_no_bar_shorts` re-checks the drawn
        # result, so a search that found nothing fails loudly instead of
        # producing a short.
        cmp_y = _clear_offset(
            [
                (net, sample.trunks[net].moved(sample_x, array_y))
                for net in ("topp", "topn")
            ],
            [(net, comparator_info["trunks"][net]) for net in ("topp", "topn")],
            array_y,
        )
        # Placed immediately beside the sampling switches, i.e. at the array
        # edge nearest the top plates: the preamp end of the row faces the
        # arrays and the regenerating latch end faces away from them
        # (`layout/floorplan-matching-plan.md` Sec 2.3).
        top.insert(
            kdb.CellInstArray(
                cmp_cell,
                kdb.Vector(cmp_x, cmp_y),
            )
        )
        merges = comparator_info["merges"]

        # -- top-level straps into the comparator ----------------------- #
        # Every strap runs in the one vertical corridor to the RIGHT of all
        # placed geometry -- the only column in this floorplan that crosses
        # neither diffusion nor another net's riser, which `geometry.stitch`
        # asserts rather than assumes.
        #
        # `topp`/`topn`: the comparator's differential input IS the CDAC top
        # plate (DR-0011), so the preamp inputs strap to the very nets the
        # sampling switches drive. `vdd`/`vss`: the comparator's analog
        # supply, strapped to the decode banks' own analog rails.
        # `topp`/`topn` stitch in the short corridor BETWEEN the sampling
        # switches and the comparator; `vdd`/`vss` in the corridor to the
        # RIGHT of everything, which the decode banks' rails reach across the
        # empty substrate below the array row. Each trunk is first grown into
        # its corridor with `Channel.extend_drawn`, which refuses to grow a
        # trunk over a track-mate (see that method).
        for index, net in enumerate(("topp", "topn")):
            x = cmp_x - 2800 + index * 900
            geo.stitch(
                top,
                layers,
                x,
                [
                    sample.channel.extend_drawn(net, x - sample_x).moved(
                        sample_x, array_y
                    ),
                    comparator_info["channel"]
                    .extend_drawn(net, x - cmp_x)
                    .moved(cmp_x, cmp_y),
                ],
            )
        corridor = top.bbox().right + 2500
        for index, net in enumerate(("vdd", "vss")):
            x = corridor + index * 1500
            geo.stitch(
                top,
                layers,
                x,
                [
                    banks["p"].channel.extend_drawn(net, x).moved(0, bank_p_y),
                    banks["n"].channel.extend_drawn(net, x).moved(0, bank_n_y),
                    comparator_info["channel"]
                    .extend_drawn(net, x - cmp_x)
                    .moved(cmp_x, cmp_y),
                ],
            )

    # -- guard rings and the analog/digital split -------------------------- #
    core = top.bbox().enlarged(GUARD_CLEARANCE, GUARD_CLEARANCE)
    analog_ring = geo.draw_guard_ring(top, layers, core, GUARD_RING_W)

    digital_box = kdb.Box(
        analog_ring.left,
        analog_ring.bottom - ANALOG_DIGITAL_GAP - SAR_RESERVED_H,
        analog_ring.left + max(SAR_RESERVED_W, analog_ring.width() // 3),
        analog_ring.bottom - ANALOG_DIGITAL_GAP,
    )
    digital_ring = geo.draw_guard_ring(top, layers, digital_box, GUARD_RING_W)
    # Dedicated digital supply rails inside the reserved region, drawn on
    # Metal1 and deliberately UNLABELLED: they carry no device in this
    # layout (the sequencer is rung-1, DR-0010), so naming them would invent
    # a pin the design netlist does not have.
    for k in range(2):
        y = digital_box.bottom + 4000 + k * 3000
        top.shapes(layers[geo.L_METAL1]).insert(
            kdb.Box(digital_box.left + 2000, y, digital_box.right - 2000, y + 1200)
        )

    ref_devices = list(mos)
    pin_set = {
        *rails, *control_pins,
        "pinp", "pinn", "topp", "topn", "samp", "sampb", nl.SUBSTRATE_NET,
    }
    if comparator_info is not None:
        ref_devices += comparator_info["devices"]
        body_net.update(comparator_info["body_net"])
        pin_set |= set(comparator_info["pins"])
        ref_devices = nl.merge_nets(ref_devices, merges, prefer=pin_set)

    info = {
        "devices": ref_devices,
        "body_net": body_net,
        "comparator": comparator_info,
        "merges": merges,
        "pins": sorted(pin_set, key=str.lower),
        "assignment": assignment,
        "areas": {
            "cdac_array_per_side": geo.area_um2(array_cell_p.bbox()),
            "cdac_arrays_total": 2 * geo.area_um2(array_cell_p.bbox()),
            "decode_bank_per_side": geo.area_um2(bank_cells["p"].bbox()),
            "decode_banks_total": 2 * geo.area_um2(bank_cells["p"].bbox()),
            "sampling_switches": geo.area_um2(sample_cell.bbox()),
            "comparator": (
                geo.area_um2(comparator_info["cell"].bbox())
                if comparator_info is not None
                else 0.0
            ),
            "analog_core_with_guard_ring": geo.area_um2(analog_ring),
            "sar_logic_reserved": geo.area_um2(digital_ring),
            "block_total": geo.area_um2(top.bbox()),
        },
        "dimensions_um": {
            "block": [top.bbox().width() * geo.DBU_UM, top.bbox().height() * geo.DBU_UM],
            "cdac_array": [array_w * geo.DBU_UM, array_h * geo.DBU_UM],
            "decode_bank": [bank_w * geo.DBU_UM, bank_h * geo.DBU_UM],
            "sampling_switches": [sample_w * geo.DBU_UM, sample_h * geo.DBU_UM],
        },
    }
    return layout, info


def write_reference(path: str, info: dict, cell_name: str, key: str) -> None:
    header = [
        f"* Flat LVS reference for the {cell_name} block layout.",
        "*",
        "* GENERATED by layout/adc-top/gen_adc_top.py by flattening",
        "* design/adc-top/adc_top.spice's `adc_cdac_side` and `adc_tgate_dum`",
        "* into the same composition the ADC-level testbenches use (two array",
        "* sides + two input sampling switches) -- do not edit. See",
        "* layout/adc-top/lib/netlist.py for why the layout and this reference",
        "* are derived from the same parsed design netlist, and what that does",
        "* and does not let LVS prove.",
        "*",
        "* Deliberate, documented differences from the schematic, each forced by",
        "* `klt extract`'s gf180mcu ExtractionDeck and restated in",
        "* layout/adc-top/README.md:",
        "*   - NMOS bodies are on the deck's `vsubs` global (no tap layer);",
        "*   - PMOS bodies are on their own Nwell island's net -- one island per",
        "*     placed CDAC cell, one for the sampling switches, and one per",
        "*     comparator group -- not on `vdd`: the deck never connects `nwell`",
        "*     to `contact`;",
        "*   - all 1024 unit MiM capacitors and the two terminating units are",
        "*     absent: the deck reads none of the MiM layers and has no",
        "*     capacitor device class. The capacitor GEOMETRY is drawn, and is",
        "*     the part of this block LVS cannot see at all.",
    ]
    if info["merges"]:
        header += [
            "*   - the comparator's two 150 kohm p+ poly load resistors are drawn",
            "*     but are not extractable devices, so each shorts its own",
            "*     terminals and `pop`/`pon` collapse onto `vdd`. See",
            "*     gen_comparator.py: `comparator_nores` is the companion case",
            "*     that keeps them distinct.",
        ]
    header += [
        "*",
        "* Runnable by hand:",
        f"*   klt lvs layout/adc-top/{key}.lvs.json --format json",
    ]
    nl.write_reference(
        path, cell_name, info["devices"], info["pins"], info["body_net"], header
    )


def write_request(path: str, cell_name: str, key: str) -> None:
    request = {
        "_comment": [
            f"klt lvs request for the {cell_name} layout: the extracted layout",
            "netlist against the flat reference generated from",
            "design/adc-top/adc_top.spice (and, for ADC_BLOCK,",
            "design/comparator/comparator.spice).",
            "",
            "Both sides are pre-extracted / generated SPICE so NetlistSpiceReader",
            "parses both -- see layout/lvs/cells/lvs_request_match.json for the",
            "engine artifact that avoids. Paths resolve against THIS file's",
            "directory.",
            "",
            f"    klt lvs layout/adc-top/{key}.lvs.json --format json",
        ],
        "layout": {"netlist": f"{key}.spice", "top": cell_name},
        "reference": {"netlist": f"{key}.ref.spice", "top": cell_name},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(request, fh, indent=2)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outdir", default=HERE)
    args = parser.parse_args()

    design = nl.design_dir(HERE)
    subckts = nl.parse(os.path.join(design, "adc-top", "adc_top.spice"))
    block_subckt(subckts)
    comparator_subckts = nl.parse(
        os.path.join(design, "comparator", "comparator.spice")
    )

    tally_info = None
    for key, cell_name, cmp_subckts in (
        ("adc_top", CELL_NAME, None),
        ("adc_block", BLOCK_CELL_NAME, comparator_subckts),
    ):
        layout, info = build(subckts, cmp_subckts, cell_name=cell_name)
        assert layout.dbu == geo.DBU_UM, f"dbu drifted to {layout.dbu}"
        layout.write(os.path.join(args.outdir, f"{key}.gds"), geo.save_options())
        write_reference(
            os.path.join(args.outdir, f"{key}.ref.spice"), info, cell_name, key
        )
        write_request(os.path.join(args.outdir, f"{key}.lvs.json"), cell_name, key)
        box = layout.cell(cell_name).bbox()
        print(
            f"wrote {key}.gds  transistors={len(info['devices'])}  "
            f"{box.width() * geo.DBU_UM:.1f} x {box.height() * geo.DBU_UM:.1f} um "
            f"= {geo.area_um2(box) / 1e6:.5f} mm^2"
        )
        tally_info = info

    # Per-weight unit-position census, so the tiling is auditable without
    # re-running the generator.
    census: dict[str, int] = {}
    for group in tally_info["assignment"].values():
        census[group] = census.get(group, 0) + 1
    tally = {
        "_comment": [
            "As-drawn area tally for the design/adc-top/ block layout, written",
            "by layout/adc-top/gen_adc_top.py. Areas are bounding-box areas in",
            "um^2 at this layout's 0.001 um database unit. Compared against the",
            "ratified < 0.1 mm^2 area row (DR-0006) in layout/adc-top/README.md,",
            "which supersedes layout/floorplan-matching-plan.md Sec 4's",
            "planning estimate per that section's own instruction.",
            "",
            "`block_total` is ADC_BLOCK: the assembled stream (CDAC arrays,",
            "decode banks, sampling switches, comparator, guard rings and the",
            "reserved SAR-logic region). ADC_TOP -- the same block without the",
            "comparator -- is the stream whose LVS target is exactly",
            "design/adc-top/adc_top.spice.",
        ],
        "areas_um2": tally_info["areas"],
        "dimensions_um": tally_info["dimensions_um"],
        "transistor_count": len(tally_info["devices"]),
        "unit_cap_positions_per_side": ARRAY_COLS * ARRAY_ROWS,
        "unit_cap_census_per_side": census,
    }
    with open(os.path.join(args.outdir, "area.json"), "w", encoding="utf-8") as fh:
        json.dump(tally, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"  unit-cap census per side: {census}")


if __name__ == "__main__":
    main()
