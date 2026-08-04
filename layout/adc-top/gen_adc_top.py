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
`adc_cdac_side` arrays and the two per-side `adc_tp_sw` top-plate `V_cm`
switches DR-0014 (issue #64/#66) added in place of the superseded dedicated
input sampling switch. Concretely, drawn:

* **The CDAC arrays** -- 512 unit-capacitor positions per side (1024 total),
  common-centroid-tiled and surrounded by a full dummy ring, per
  `layout/floorplan-matching-plan.md` Sec 1.3. NOT one lumped capacitor per
  binary weight: the tiling below assigns each weight's `m` unit positions
  to centro-symmetric position PAIRS spread across the array, which is the
  whole point of the plan's Sec 1.3 and what the schematic's own `m=`
  multiplicity means physically (`spec/cdac-sizing-memo.md` Sec 5.4).
* **The bottom-plate decode switches and their local drivers** -- 288
  transistors (9 weighted positions x 16 devices x 2 sides, DR-0014's
  fourth one-hot leg to `V_in` included), in two banks, one per array side,
  with the analog supply/reference rails (`vdd`, `vss`, `vref`, `vcm`) and
  the broadcast fourth-leg control (`sel_in`) tied between them.
* **The top-plate `V_cm` switches** -- 8 transistors, the two `adc_tp_sw`
  cells DR-0014 places beside the arrays, at the same "array's input edge,
  not inside the array" floorplan slot the superseded dedicated input
  sampling switch used to occupy. Each is one local driver plus one
  CDAC-geometry T-gate, deliberately NOT dummy-compensated (see
  `design/adc-top/adc_top.spice`'s own comment on `adc_tp_sw`), and both
  sides share one control net (`tp_gn`) -- their skew is the term this
  topology cannot cancel, so it is not manufactured here by routing two
  copies.
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

#: Unit capacitor PLATE: `C_u` = 17.24 fF at 2.7136 um square
#: (`spec/cdac-sizing-memo.md` Sec 4; the density law is quoted in
#: `design/adc-top/adc_top.spice`'s own comment). This is the PDK subckt's
#: `c_width`/`c_length`, i.e. the FuseTop top plate -- NOT the drawn
#: footprint, which `geometry.draw_mim_cap` derives from it.
UNIT_CAP_NM = 2714
#: Tiling pitch, **derived** from the two MiM rules the pinned deck checks
#: rather than chosen: the drawn footprint is the plate plus
#: `mim.enclosing.fusetop.1`'s 0.6 um Metal4 ring on every side (`MIMTM.3`),
#: and adjacent footprints must clear `mim.space.1`'s 1.2 um (`MIMTM.1`).
#: 2.7136 + 2 x 0.6 + 1.2 = 5.1136 um. This was 3.914 um before issue #70 --
#: the old construction took the plate as the *Metal4* size and shrank
#: FuseTop inside it, which drew neither the ratified device nor a legal
#: stack. The array is 1.31x larger in each direction as a result, and that
#: is the DRM's number, not a choice this layout makes.
UNIT_PITCH, _UNIT_PITCH_Y = geo.mim_pitch(UNIT_CAP_NM, UNIT_CAP_NM)
assert UNIT_PITCH == _UNIT_PITCH_Y == 5114, (
    f"unit pitch drifted to {UNIT_PITCH} x {_UNIT_PITCH_Y} nm"
)
#: Bottom-plate-to-bottom-plate gap between adjacent units (`mim.space.1`).
UNIT_CAP_GAP = geo.MIM_M4_SPACE

#: The tiled array's shape, per side: 32 x 16 = 512 unit positions.
ARRAY_COLS = 32
ARRAY_ROWS = 16

#: Clearances between the block's regions.
REGION_GAP = 2500
#: Gap between the top-plate switch cell and the comparator (`adc_block`
#: only), wider than `REGION_GAP` because FIVE top-level strap columns
#: (`topp`, `topn`, `vdd`, `vss`, `vcm`) have to fit in it side by side --
#: see the switch-cell rail tie's own docstring below for why the switch
#: cell's OWN `vdd`/`vss`/`vcm` are stitched to the decode banks in THIS
#: gap rather than in the far corridor past the comparator.
SWITCH_CMP_GAP = 6000
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
    `adc_cdac_side` and `adc_tp_sw` but never instantiates them, because the
    ADC-level testbenches under `sim/adc-*/` do that themselves. This builds
    the SAME composition `sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice`
    uses (DR-0014) -- two array sides and two per-side top-plate `V_cm`
    switches, both driven by ONE shared control net -- out of the parsed
    subcircuits' OWN port lists, so the block layout tracks the design file
    rather than a transcription of it.

    `sel_in` (each side's fourth-leg broadcast decode) and `tp_gn`
    (`adc_tp_sw`'s control) are each wired to the SAME single net across
    both `XSP`/`XSN` -- exactly like `vref`/`vcm`/`vss`/`vdd` -- because the
    testbench does (`se_sel_in_n`, `se_samp_tp_n`): both sides sample
    together by construction (`design/sar-logic/README.md`'s bus-width
    argument), and the whole point of DR-0014's shared-control top-plate
    switch is that side-to-side skew is a real, uncancellable term, not one
    manufactured here by routing two independent copies.
    """
    side = subckts["adc_cdac_side"]
    tp_sw = subckts["adc_tp_sw"]
    lines: list[list[str]] = []
    ports: list[str] = ["pinp", "pinn", "topp", "topn", "sel_in", "tp_gn",
                        "vref", "vcm", "vss", "vdd"]

    for tag in ("p", "n"):
        nets = []
        for port in side.ports:
            if port == "top":
                nets.append(f"top{tag}")
            elif port == "vin":
                nets.append(f"pin{tag}")
            elif port == "sel_in":
                nets.append("sel_in")
            elif port in ("vref", "vcm", "vss", "vdd"):
                nets.append(port)
            else:  # rel_256 / hi_256 / lo_256 / ...
                nets.append(f"{port}_{tag}")
                ports.append(f"{port}_{tag}")
        lines.append([f"XS{tag.upper()}", *nets, "adc_cdac_side"])

    for tag in ("p", "n"):
        nets = []
        for port in tp_sw.ports:
            if port == "top":
                nets.append(f"top{tag}")
            elif port == "gn":
                nets.append("tp_gn")
            else:  # vcm / vdd / vss
                nets.append(port)
        lines.append([f"XSW{tag.upper()}", *nets, "adc_tp_sw"])

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
       `(1, 8)`: each odd group sits (14.5, 0.5) pitches -- (74.2, 2.6) um
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

    **The unit caps here are drawn WITHOUT their `CAP_MK`/`MIM_L_MK` marker
    layers, i.e. as inert MiM geometry, so `klt extract` does not recognise
    them as devices** -- unlike `cells/gen_adc_cells.py`'s single wired unit,
    which does carry them. That is a consequence of the one thing this array
    still does not draw: the per-weight BOTTOM-plate interconnect that would
    tie a weight's `m` scattered units to their decode switch. Marking a cap
    whose bottom plate goes nowhere would not make the array more verified;
    it would produce 1224 extracted devices on 1224 floating nets and an LVS
    result that is worse than no result. The markers and the interconnect go
    in together, and until they do this stays stated, not silent
    (README.md's "Not verified, and not claimable"). No Via4 is drawn on an
    unmarked stack either: to the extraction deck a Via4 outside a
    *recognised* capacitor is an ordinary Metal4<->Metal5 via, which would
    short the two plates.
    """
    cell = layout.create_cell(name)
    groups = [(str(w), w) for w in WEIGHT_ORDER] + [("term", 1)]
    assignment = centroid_tiling(ARRAY_COLS, ARRAY_ROWS, groups)

    plates: list[kdb.Box] = []
    for (c, r), _group in sorted(assignment.items()):
        cap = geo.draw_mim_cap(
            cell, layers, c * UNIT_PITCH, r * UNIT_PITCH,
            UNIT_CAP_NM, UNIT_CAP_NM,
        )
        plates.append(cap.plate)

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
    x_lo = min(p.left for p in plates)
    x_hi = max(p.right for p in plates)
    for r in range(ARRAY_ROWS):
        y = r * UNIT_PITCH + geo.MIM_M4_ENCLOSURE + UNIT_CAP_NM // 2
        cell.shapes(metal5).insert(
            kdb.Box(x_lo, y - strap // 2, x_hi, y + strap // 2)
        )
    x_centre = (ARRAY_COLS * UNIT_PITCH - UNIT_CAP_GAP) // 2
    cell.shapes(metal5).insert(
        kdb.Box(
            x_centre - strap,
            -UNIT_CAP_GAP,
            x_centre + strap,
            (ARRAY_ROWS - 1) * UNIT_PITCH + 2 * geo.MIM_M4_ENCLOSURE
            + UNIT_CAP_NM + UNIT_CAP_GAP,
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
    if len(mos) != 296:
        raise RuntimeError(f"expected 296 transistors, flattened {len(mos)}")

    control_pins = [p for p in subckts["adc_top"].ports if p.startswith(("rel", "hi", "lo"))]
    rails = ["vdd", "vss", "vref", "vcm"]
    # `sel_in` is a decode bank net, not a rail -- but exactly like the
    # rails, both sides' decode banks carry the SAME single (broadcast)
    # net, so it needs the same pin-label / escape / cross-bank-stitch
    # treatment as `rails` gets, everywhere the bank itself is concerned.
    bank_shared = rails + ["sel_in"]

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
            pins=bank_shared + [p for p in control_pins if p.endswith(f"_{tag}")],
            escape=bank_shared,
        )
        banks[tag] = block
        bank_cells[tag] = cell
        body_net.update(block.body_net)

    # -- the top-plate V_cm switches (DR-0014) ---------------------------- #
    # One `adc_tp_sw` per side, in the same floorplan slot the superseded
    # dedicated input sampling switch used to occupy (`layout/
    # floorplan-matching-plan.md` Sec 1.5: "at the array's input edge, not
    # inside the array"). Each switch's own driver is placed immediately
    # beside its own T-gate -- one Nwell island per side. Unlike the
    # superseded switch, `adc_tp_sw` is deliberately NOT dummy-compensated
    # (`design/adc-top/adc_top.spice`'s own comment on the subckt), so there
    # is no injection-cancelling mirror ordering left to preserve between
    # the two sides.
    switch_order = {
        "p": ["XSWP.Xd.Xn", "XSWP.Xs.XN", "XSWP.Xd.Xp", "XSWP.Xs.XP"],
        "n": ["XSWN.Xd.Xn", "XSWN.Xs.XN", "XSWN.Xd.Xp", "XSWN.Xs.XP"],
    }
    by_path = {d.path: d for d in mos}
    switch_cell = layout.create_cell("ADC_TOP_SW")
    switch = place.draw_devices(
        switch_cell,
        layers,
        [
            (f"nw_sw{tag}", [by_path[p] for p in order])
            for tag, order in switch_order.items()
        ],
        pins=["topp", "topn", "tp_gn", "vcm", "vdd", "vss"],
        # `topp`/`topn` escape to stitch (when present) into the comparator;
        # `vcm`/`vdd`/`vss` escape so each lands on its OWN track during
        # packing -- they are genuinely routed nets here (the driver's real
        # supply, and the T-gate's released-side terminal), unlike the
        # superseded `adc_tgate_dum`'s body-only "vdd" -- and each is grown
        # further still, to its own stitch column, by `Channel.extend_drawn`
        # below. Declaring the escape here (rather than relying on that
        # later call alone) is what keeps them off any other net's track in
        # the first place. The margin covers every stitch column this cell
        # feeds (`topp`/`topn` plus `vdd`/`vss`/`vcm`, all inside
        # `SWITCH_CMP_GAP`).
        escape=["topp", "topn", "vcm", "vdd", "vss"],
        escape_margin=SWITCH_CMP_GAP - 2000,
    )
    body_net.update(switch.body_net)

    # -- the capacitor arrays --------------------------------------------- #
    array_cell_p, assignment = draw_cdac_array(layout, layers, "ADC_CDAC_ARRAY_P")
    array_cell_n, _ = draw_cdac_array(layout, layers, "ADC_CDAC_ARRAY_N")

    # -- floorplan: place the regions ------------------------------------- #
    # Bottom to top: the two decode banks (P below N, so their shared analog
    # rails abut across one stitch corridor), then the capacitor arrays with
    # the top-plate V_cm switches beside them. The switches sit between the
    # input pins (block edge, right) and the arrays' own top plates, which
    # is where `layout/floorplan-matching-plan.md` Sec 1.5 puts them: at the
    # array's input edge, NOT inside the tiled array.
    bank_h = bank_cells["p"].bbox().height()
    bank_w = bank_cells["p"].bbox().width()
    bank_p_y = 0
    bank_n_y = bank_p_y + bank_h + REGION_GAP
    top.insert(kdb.CellInstArray(bank_cells["p"], kdb.Vector(0, bank_p_y)))
    top.insert(kdb.CellInstArray(bank_cells["n"], kdb.Vector(0, bank_n_y)))

    array_h = array_cell_p.bbox().height()
    array_w = array_cell_p.bbox().width()
    switch_h = switch_cell.bbox().height()
    switch_w = switch_cell.bbox().width()
    array_y = bank_n_y + bank_h + REGION_GAP
    top.insert(kdb.CellInstArray(array_cell_p, kdb.Vector(0, array_y)))
    top.insert(
        kdb.CellInstArray(
            array_cell_n, kdb.Vector(array_w + REGION_GAP * 2, array_y)
        )
    )
    switch_x = 2 * array_w + REGION_GAP * 4
    top.insert(kdb.CellInstArray(switch_cell, kdb.Vector(switch_x, array_y)))

    # -- tie the analog rails + sel_in between the two decode banks ------- #
    # One Poly2 stitch per net, in the Comp-free escape corridor to the
    # right of both banks' device rows, contacting each bank's own trunk.
    # This is the same Metal1-trunk/Poly2-riser discipline the placer uses
    # inside a bank -- see lib/geometry.py's docstring for why the
    # interconnect has to be exactly two layers.
    stitch_x0 = banks["p"].row_x1 + 1500
    for index, net in enumerate(bank_shared):
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
        # the same nets the top-plate switches drive -- not to fresh pins.
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
        cmp_x = switch_x + switch_w + SWITCH_CMP_GAP

        # The comparator and the top-plate switches sit in the same row, so
        # their channel packers can hand two DIFFERENT nets the same track Y
        # -- and then their top-level straps, which all run to one corridor,
        # would short. No single Y offset avoids that for every net pair
        # (the track pitch is smaller than twice the bar-plus-space), so the
        # offset is SEARCHED over the nets actually strapped and the first
        # clear one is used. `geo.assert_no_bar_shorts` re-checks the drawn
        # result, so a search that found nothing fails loudly instead of
        # producing a short.
        #
        # EVERY net either side escapes toward this shared gap has to be
        # checked here, not just `topp`/`topn`: `switch` escapes
        # `topp`/`topn`/`vcm`/`vdd`/`vss` (all five, toward the comparator)
        # and `COMPARATOR` escapes `topp`/`topn` left and `vdd`/`vss` right
        # -- checking only `topp`/`topn` found a `cmp_y` where those two
        # cleared but `switch`'s own `vss` trunk still landed on the exact
        # track `COMPARATOR`'s own `topn` escape column uses, so the two
        # touched once both were grown toward this corridor (`klt lvs`
        # caught it as a `topn`/`vss` merge, not a DRC violation -- a
        # same-layer Metal1 touch between two DIFFERENTLY NAMED trunks is
        # exactly what this search exists to rule out, and it cannot do
        # that for a net it was never told about).
        switch_escaped = ("topp", "topn", "vcm", "vdd", "vss")
        comparator_escaped = ("topp", "topn", "vdd", "vss")
        cmp_y = _clear_offset(
            [
                (net, switch.trunks[net].moved(switch_x, array_y))
                for net in switch_escaped
            ],
            [(net, comparator_info["trunks"][net]) for net in comparator_escaped],
            array_y,
        )
        # Placed immediately beside the top-plate switches, i.e. at the
        # array edge nearest the top plates: the preamp end of the row faces
        # the arrays and the regenerating latch end faces away from them
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
        # top-plate switches drive. `vdd`/`vss` reach the comparator through
        # its OWN far corridor below (the decode banks are now WIDER than
        # this whole row -- DR-0014's fourth leg -- so that corridor sits
        # well past the comparator too; it is a short hop for the
        # comparator's own trunk, never crossing anything). `topp`/`topn`
        # stitch in the short corridor BETWEEN the top-plate switches and
        # the comparator. Each trunk is first grown into its corridor with
        # `Channel.extend_drawn`, which refuses to grow a trunk over a
        # track-mate (see that method).
        for index, net in enumerate(("topp", "topn")):
            x = switch_x + switch_w + 400 + index * 700
            geo.stitch(
                top,
                layers,
                x,
                [
                    switch.channel.extend_drawn(net, x - switch_x).moved(
                        switch_x, array_y
                    ),
                    comparator_info["channel"]
                    .extend_drawn(net, x - cmp_x)
                    .moved(cmp_x, cmp_y),
                ],
            )
        # `vdd`/`vss`: the comparator's own analog supply, strapped to the
        # decode banks' own analog rails in the corridor to the RIGHT of
        # EVERYTHING placed so far (comparator included) -- the only column
        # in this floorplan guaranteed clear, the same discipline the
        # switch-cell tie below uses at its own, much nearer, corridor.
        far_corridor = top.bbox().right + 2500
        for index, net in enumerate(("vdd", "vss")):
            x = far_corridor + index * 1500
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

    # -- tie vdd/vss/vcm to the top-plate switch cell ---------------------- #
    # `adc_tp_sw`'s own driver needs REAL vdd/vss -- its own inverter's
    # supply, not merely a body-only schematic reference the way the
    # superseded `adc_tgate_dum`'s "vdd" port was (see
    # `lib/place.draw_devices`'s body-terminal note) -- and its T-gate's
    # released-side terminal genuinely IS `vcm`. All three have to reach the
    # same physical net the decode banks already carry.
    #
    # NEITHER a straight reach at the switch cell's own trunk Y (it would
    # run through the comparator's row -- see below) NOR a straight drop at
    # any X inside the bank's own width (any X < the bank's row_x1 crosses
    # its OWN device columns -- there are 9 weighted cells across the FULL
    # bank width, not just at its right edge) works here. Two hops through
    # the REGION_GAP strip between bank_n's row and the array row instead,
    # which the floorplan already keeps genuinely empty (confirmed clear by
    # `geo.stitch`'s own Comp/Poly2 check on both hops below):
    #   1. straight down from the switch cell's own trunk, at an X still
    #      inside the switch cell's own escaped span (so still well before
    #      the comparator's reserved slot);
    #   2. across, in that empty strip, to X >= the bank's own row_x1 (the
    #      same "escape corridor to the right of every device column"
    #      discipline every other bank stitch in this file already uses);
    #   3. straight down from there into the bank's own trunk.
    # Steps 2+3 are exactly the shape `geo.stitch` draws for one corridor,
    # so each hop is one `geo.stitch` call joined by a plain drawn Metal1
    # "bridge" bar standing in for a third block's trunk.
    #
    # (Found during this bring-up: a first attempt grew the switch cell's
    # own trunk straight to the far corridor at its own Y, which is exactly
    # the comparator's row now that DR-0014's fourth leg makes the decode
    # banks wider than the whole array/switch/comparator row combined --
    # `klt lvs` caught it as a mass of merged nets, not a DRC violation,
    # because a Metal1-over-Metal1 short carries no Comp/Poly2 for
    # `geo.stitch`'s own check to catch. Restated in `../README.md`.)
    #
    # A SECOND instance of the same failure mode was found placing the
    # bridge itself: the REGION_GAP strip's own *midpoint* is not safe
    # either. `adc_tp_sw` and (when present) `COMPARATOR` are both placed at
    # `array_y`, but their own local bboxes dip BELOW their own row_y0=0 by
    # more than half of `REGION_GAP` -- `COMPARATOR`'s preamp/latch channel
    # in particular reaches `array_y - 7050` nm, well past the strip's
    # midpoint -- so a bridge centred there physically overlapped
    # `COMPARATOR`'s own Metal1 (a `dout`/`vcm` and `doutb`/`topn`/`vss`
    # merge in `klt lvs`, not a DRC violation, for the same Metal1-over-
    # Metal1 reason as the first instance).
    #
    # Rather than a second hand-picked constant (which the SAME class of
    # bug could silently outgrow the next time this floorplan's dimensions
    # move -- `cmp_y`'s own search above is exactly what moved them this
    # time), the bridge's Y is SEARCHED the same way `cmp_y` is: candidates
    # start hugging `bank_n`'s own row top (the shallowest offset that is
    # provably bank-free, since it IS that row's own top edge) and step
    # upward in whole `TRUNK_PITCH`s, and each candidate is accepted only
    # once every one of its three per-net boxes is checked, by construction
    # rather than assumption, against every Metal1 shape already drawn --
    # the same check `geo.stitch` already makes for Comp/Poly2, lifted to
    # Metal1 because a raw bar drawn outside a `Channel` carries no
    # Comp/Poly2 for that check to catch.
    #
    # The search is NOT bounded at `array_y`: `cmp_y`'s own search (above)
    # is free to move `COMPARATOR` far enough down that NO Y in the
    # REGION_GAP strip clears its footprint (observed directly during this
    # bring-up: `COMPARATOR`'s own bottom landed only ~640 nm above
    # `bank_row_top`, not enough for even one track). The bridge's own X
    # span (`bx`..`fx`) never crosses the CDAC arrays' own X range (the
    # arrays sit at X < `switch_x`, the bridge starts past `switch_x +
    # switch_w`), so there is nothing structural stopping the search from
    # continuing PAST `COMPARATOR`'s own top edge too, where nothing else
    # is drawn -- the same "asserted, not assumed" check just keeps
    # searching until it finds real clearance, wherever that turns out to
    # be for this run's actual placement.
    # `bank_n`'s own row top -- NOT `bank_n_y + bank_h`: `bank_h` is the
    # CELL's full bbox height (row height PLUS the channel's own depth
    # BELOW row_y0=0), so adding it to `bank_n_y` overshoots into the
    # channel-depth's worth of the array row above, not the genuinely empty
    # REGION_GAP strip below it.
    bank_row_top = bank_n_y + bank_cells["p"].bbox().top
    # The far stitch column has to sit in a Comp-free corridor to the RIGHT
    # of everything already placed -- `geo.stitch` refuses to draw a Poly2
    # strap over diffusion and is the check that catches this. It was
    # `bank_w + 6000`, i.e. it assumed the decode banks are the widest thing
    # in the block. That assumption was true only while the CDAC arrays were
    # drawn at an illegal MiM pitch: at the correct pitch (issue #70) the
    # arrays are 41 um wider per side, which pushes `switch_x` and with it
    # `COMPARATOR` right, past `bank_w`, and `adc_block` stopped building
    # with exactly that `stitch` error. Derived from what is actually drawn
    # rather than re-tuned to a new constant, so the next floorplan move
    # cannot resurrect the same bug.
    far_x = max(bank_w, top.bbox().right) + 6000
    bridge_nets = ("vdd", "vss", "vcm")
    bridge_geometry = {
        net: (
            switch_x + switch_w + 1800 + index * 900,  # bx
            far_x + index * 900,  # fx
        )
        for index, net in enumerate(bridge_nets)
    }
    stack_h = len(bridge_nets) * (geo.TRUNK_H + geo.TRUNK_GAP)
    search_top = array_y - stack_h
    if comparator_info is not None:
        search_top = max(
            search_top, cmp_y + comparator_info["cell"].bbox().top + 2000
        )

    def bridge_boxes(y0: int) -> dict[str, kdb.Box]:
        boxes = {}
        for index, net in enumerate(bridge_nets):
            bx, fx = bridge_geometry[net]
            by0 = y0 + index * (geo.TRUNK_H + geo.TRUNK_GAP)
            by1 = by0 + geo.TRUNK_H
            boxes[net] = kdb.Box(
                bx - geo.TRUNK_OVERHANG, by0, fx + geo.TRUNK_OVERHANG, by1
            )
        return boxes

    bridge_y0 = None
    for candidate in range(bank_row_top + 800, search_top, geo.TRUNK_PITCH):
        candidate_boxes = bridge_boxes(candidate)
        existing_metal1 = kdb.Region(top.begin_shapes_rec(layers[geo.L_METAL1]))
        if all(
            (existing_metal1 & kdb.Region(box)).is_empty()
            for box in candidate_boxes.values()
        ):
            bridge_y0 = candidate
            break
    if bridge_y0 is None:
        raise RuntimeError(
            "no collision-free Y offset found for the vdd/vss/vcm bridge "
            f"between bank_row_top={bank_row_top} and search_top={search_top}"
        )

    for net, bridge in bridge_boxes(bridge_y0).items():
        bx, fx = bridge_geometry[net]
        top.shapes(layers[geo.L_METAL1]).insert(bridge)
        geo.stitch(
            top, layers, bx,
            [
                switch.channel.extend_drawn(net, bx - switch_x).moved(
                    switch_x, array_y
                ),
                bridge,
            ],
        )
        geo.stitch(
            top, layers, fx,
            [
                bridge,
                banks["p"].channel.extend_drawn(net, fx).moved(0, bank_p_y),
                banks["n"].channel.extend_drawn(net, fx).moved(0, bank_n_y),
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
        "pinp", "pinn", "topp", "topn", "sel_in", "tp_gn", nl.SUBSTRATE_NET,
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
            "tp_switches": geo.area_um2(switch_cell.bbox()),
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
            "tp_switches": [switch_w * geo.DBU_UM, switch_h * geo.DBU_UM],
        },
    }
    return layout, info


def write_reference(path: str, info: dict, cell_name: str, key: str) -> None:
    header = [
        f"* Flat LVS reference for the {cell_name} block layout.",
        "*",
        "* GENERATED by layout/adc-top/gen_adc_top.py by flattening",
        "* design/adc-top/adc_top.spice's `adc_cdac_side` and `adc_tp_sw`",
        "* into the same composition the ADC-level testbenches use (DR-0014:",
        "* two array sides + two per-side top-plate V_cm switches) -- do not",
        "* edit. See layout/adc-top/lib/netlist.py for why the layout and this",
        "* reference are derived from the same parsed design netlist, and what",
        "* that does and does not let LVS prove.",
        "*",
        "* Deliberate, documented differences from the schematic, each forced by",
        "* `klt extract`'s gf180mcu ExtractionDeck and restated in",
        "* layout/adc-top/README.md:",
        "*   - NMOS bodies are on the deck's `vsubs` global (no tap layer);",
        "*   - PMOS bodies are on their own Nwell island's net -- one island per",
        "*     placed CDAC cell, one per top-plate switch side, and one per",
        "*     comparator group -- not on `vdd`: the deck never connects `nwell`",
        "*     to `contact`;",
        "*   - all 1024 unit MiM capacitors and the two terminating units are",
        "*     absent. The deck DOES model this device now (issue #70:",
        "*     `cap_mim_2f0_m4m5_noshield`, proven end-to-end on the",
        "*     cells/adc_cdac_cell case), but recognising a cap requires the",
        "*     CAP_MK/MIM_L_MK markers, and those are drawn only where the",
        "*     layout also wires both plates. The array's per-weight",
        "*     bottom-plate interconnect is still undrawn, so its units are",
        "*     drawn as inert MiM geometry and are absent from both sides of",
        "*     this comparison rather than present on one. See README.md.",
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
