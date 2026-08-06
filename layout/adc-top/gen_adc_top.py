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
  Every real unit is a recognised `cap_mim_2f0_m4m5_noshield` with BOTH
  plates wired -- the within-array per-weight interconnect (issue #85) and
  the block-level route out to the decode banks, the `vcm` terminating tie
  and `topp`/`topn` (issue #86, `_route_cdac_plates`) -- so `klt lvs`
  compares all 1024 of them. The dummy ring stays unmarked and inert.
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
#: Simulation companion of `BLOCK_CELL_NAME`, not a deliverable: the same
#: assembled block with the comparator's two 150 kohm p+ poly load-resistor
#: BODIES omitted, so `pop`/`pon` survive `klt extract` as distinct nets
#: (issue #116; see `build()`'s `comparator_resistors` argument).
BLOCK_NORES_CELL_NAME = "ADC_BLOCK_NORES"

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

# --- per-weight bottom-plate interconnect (issue #85, Part 1 of #81) ------- #
#: Width (X-extent) of a per-weight Metal2 "spine". Sized at the same
#: via-landing pad width the risers use (`VIA_SIDE + 2*VIA_METAL_MARGIN` =
#: 540 nm): comfortably inside a `MIM_M4_SPACE` (1200 nm) inter-column gap and
#: >= `metal2.width.1` (280 nm). Verified by `klt drc` against the pinned deck.
SPINE_W = geo.VIA_SIDE + 2 * geo.VIA_METAL_MARGIN
#: Y of the shallowest ("track 0") row trunk, as a drop below a row's own
#: footprint bottom (`r * UNIT_PITCH`): 100 nm into the inter-row gap below the
#: row, because `geometry.draw_mim_bottom_riser` wires DOWN from the cap's
#: Metal4 bottom ring (`r*UNIT_PITCH + MIM_M4_ENCLOSURE//2`) and requires the
#: trunk to sit at/below that ring. Deeper tracks step down by `geo.TRUNK_PITCH`.
TRUNK_TRACK0_DROP = 100
#: Column index of the inter-column gap each weight's spine occupies, spread
#: every third column so no two spines share or neighbour a gap. Ten weights
#: (nine `WEIGHT_ORDER` + `term`), gaps after columns 1, 4, ... 28 -- all
#: interior to the 32-column array, clear of the dummy ring.
SPINE_GAP_STRIDE = 3
SPINE_GAP_BASE = 1
#: Y at which every per-weight spine leaves the array cell (issue #86, Part 2
#: of #81): the cell's OWN bottom edge, i.e. the dummy ring's footprint bottom
#: at `-UNIT_PITCH`.
#:
#: Part 1 (#85) stopped each spine at its own shallowest row trunk, which put
#: the ten exits at ten different, weight-dependent Y -- and left two of them
#: (`1` and `term`, one row each) stranded in the middle of the array with no
#: path out at all. Running every spine down to one common edge turns the
#: block-level route below into a straight Metal2 drop at a known Y instead of
#: ten special cases, and costs no area: the spine sits in an inter-column gap
#: it already occupies, and the array cell's bounding box is the dummy ring's.
SPINE_EXIT_Y = -UNIT_PITCH

# --- block-level plate routing (issue #86, Part 2 of #81) ------------------ #
#: Width of a top-level Metal2/Metal3 route. Same via-landing-pad width the
#: spines and risers use, so one number covers "wide enough for a via" and
#: ">= metal2.width.1 / metal3.width.1" (both 280 nm) at once.
ROUTE_W = geo.VIA_SIDE + 2 * geo.VIA_METAL_MARGIN
#: Minimum centre-to-centre spacing between two DIFFERENT nets' parallel
#: routes: the full width plus `metal2.space.1`/`metal3.space.1` (280 nm).
ROUTE_SEP = ROUTE_W + 280
#: Centre-to-centre pitch of the horizontal Metal3 lanes, one per routed net.
LANE_PITCH = ROUTE_W + 300
#: Vertical clearance between the shallowest lane and the arrays' own bottom
#: edge. The lanes run UNDER both arrays, so they have to clear the lowest
#: thing either array draws -- the dummy ring's Metal4 -- by more than
#: `mim.space.1` for the one lane that carries a Metal4 via pad (the top-plate
#: down-stack), which is asserted rather than assumed below.
LANE_CLEARANCE = 2000

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


def top_plate_exit_x() -> int:
    """Array-cell-local X of the Metal5 top-plate mesh's own centre spine --
    the array's single top-plate terminal, and where `_route_cdac_plates`
    continues it down out of the cell."""
    return (ARRAY_COLS * UNIT_PITCH - UNIT_CAP_GAP) // 2


def draw_cdac_array(
    layout: kdb.Layout,
    layers: dict[tuple[int, int], int],
    name: str,
) -> tuple[kdb.Cell, dict[tuple[int, int], str], dict[str, kdb.Box]]:
    """Draw one side's tiled unit-capacitor array plus its dummy ring, the
    Metal5 top-plate mesh, and the per-weight BOTTOM-plate interconnect that
    ties every real unit of a weight onto ONE physical net (issue #85, Part 1
    of #81).

    The top plate really is one node across the whole side (DR-0011's
    top-plate sampling); the mesh is that physical net. Every REAL unit is now
    drawn as a recognised MiM device (`device=True`), so `klt extract` sees it
    as a `cap_mim_2f0_m4m5_noshield`: its top plate joins the mesh through the
    Via4 `device=True` adds, and its bottom plate joins its weight's net
    through the interconnect below. The dummy ring stays `device=False` --
    inert, floating geometry for edge matching only.

    The interconnect, entirely inside this cell (no route out to the decode
    banks -- that is #86):

    1. **Row trunks (Metal1).** For each row, one full-width Metal1 bar per
       weight PRESENT in that row, placed just below the row and marching
       downward by `geo.TRUNK_PITCH` (a row uses at most six -- asserted -- of
       the ten weights, so the stack stays shallow and clears the row below).
       Metal1 does not interact with Metal4/FuseTop, so a trunk freely spans
       the full array width and runs under the row below's inert caps.
    2. **Per-unit risers.** `geo.draw_mim_bottom_riser` (unchanged) drops each
       real unit's Metal4 bottom plate onto its own (row, weight) trunk on
       Metal3/Metal2 with a Via3/Via2/Via1 stack.
    3. **Per-weight spines (Metal2).** One vertical Metal2 spine per weight, in
       a dedicated inter-column gap, landing a Via1 on every row's trunk for
       that weight -- which merges the per-row segments into ONE array-wide net
       -- and continuing down to `SPINE_EXIT_Y`, the cell's own bottom edge, so
       all ten present themselves at one known Y (issue #86).
    4. The ten spine boxes are RETURNED so the block-level routing can reach
       each weight's net without re-deriving geometry from the drawn cell.

    The top plate's own exit is the Metal5 mesh's centre spine, which reaches
    down to `-UNIT_CAP_GAP`; `_route_cdac_plates` continues it out of the cell
    to `topp`/`topn`.
    """
    cell = layout.create_cell(name)
    groups = [(str(w), w) for w in WEIGHT_ORDER] + [("term", 1)]
    assignment = centroid_tiling(ARRAY_COLS, ARRAY_ROWS, groups)
    group_order = [str(w) for w in WEIGHT_ORDER] + ["term"]
    group_index = {g: i for i, g in enumerate(group_order)}

    # Real units, drawn as recognised MiM devices. Keep each `MimCap` so its
    # riser can be wired onto the right trunk below.
    caps: dict[tuple[int, int], geo.MimCap] = {}
    plates: list[kdb.Box] = []
    for (c, r), _group in sorted(assignment.items()):
        cap = geo.draw_mim_cap(
            cell, layers, c * UNIT_PITCH, r * UNIT_PITCH,
            UNIT_CAP_NM, UNIT_CAP_NM, device=True,
        )
        caps[(c, r)] = cap
        plates.append(cap.plate)

    # Full dummy ring: one extra tile all the way round, identical drawn
    # geometry (same MiM stack, same size), electrically floating -- so an
    # edge unit sees the same local etch/stress environment as an interior
    # one (`layout/floorplan-matching-plan.md` Sec 1.3). Kept `device=False`:
    # unmarked, no Via4, no bottom-plate riser, so it is inert and unconnected.
    for c in range(-1, ARRAY_COLS + 1):
        for r in range(-1, ARRAY_ROWS + 1):
            if 0 <= c < ARRAY_COLS and 0 <= r < ARRAY_ROWS:
                continue
            geo.draw_mim_cap(
                cell, layers, c * UNIT_PITCH, r * UNIT_PITCH,
                UNIT_CAP_NM, UNIT_CAP_NM,
            )

    # -- per-weight bottom-plate interconnect ---------------------------- #
    metal1 = layers[geo.L_METAL1]
    metal2 = layers[geo.L_METAL2]
    via1 = layers[geo.L_VIA1]
    foot_w = geo.mim_footprint(UNIT_CAP_NM, UNIT_CAP_NM)[0]
    trunk_x0 = 0
    trunk_x1 = (ARRAY_COLS - 1) * UNIT_PITCH + foot_w

    # 1: one full-width Metal1 trunk per (row, weight present in that row).
    trunks: dict[tuple[int, str], kdb.Box] = {}
    for r in range(ARRAY_ROWS):
        present = sorted(
            {g for (c, rr), g in assignment.items() if rr == r},
            key=lambda g: group_index[g],
        )
        assert len(present) <= 6, (
            f"row {r} has {len(present)} weights; trunk stack budget is 6"
        )
        for track, g in enumerate(present):
            ty = r * UNIT_PITCH - TRUNK_TRACK0_DROP - track * geo.TRUNK_PITCH
            trunks[(r, g)] = kdb.Box(
                trunk_x0, ty - geo.TRUNK_H // 2, trunk_x1, ty + geo.TRUNK_H // 2
            )
            cell.shapes(metal1).insert(trunks[(r, g)])

    # 2: one riser per real unit, onto its own (row, weight) trunk.
    for (c, r), g in assignment.items():
        geo.draw_mim_bottom_riser(cell, layers, caps[(c, r)], trunks[(r, g)])

    # 3+4: one Metal2 spine per weight, tying every row's trunk onto one net,
    # and running on down to the cell's own bottom edge (`SPINE_EXIT_Y`) so all
    # ten leave at one known Y for the block-level route (issue #86).
    spines: dict[str, kdb.Box] = {}
    for g in group_order:
        rows_with_g = [r for r in range(ARRAY_ROWS) if (r, g) in trunks]
        gap_col = SPINE_GAP_BASE + SPINE_GAP_STRIDE * group_index[g]
        x = gap_col * UNIT_PITCH + foot_w + geo.MIM_M4_SPACE // 2
        y0 = min(trunks[(r, g)].bottom for r in rows_with_g)
        assert SPINE_EXIT_Y <= y0, (
            f"spine exit {SPINE_EXIT_Y} is above weight {g}'s own lowest trunk "
            f"at {y0} -- the spine would not reach the cell edge"
        )
        y0 = SPINE_EXIT_Y
        y1 = max(trunks[(r, g)].top for r in rows_with_g)
        spine = kdb.Box(x - SPINE_W // 2, y0, x + SPINE_W // 2, y1)
        cell.shapes(metal2).insert(spine)
        for r in rows_with_g:
            cy = trunks[(r, g)].center().y
            cell.shapes(via1).insert(
                kdb.Box(
                    x - geo.VIA_SIDE // 2, cy - geo.VIA_SIDE // 2,
                    x + geo.VIA_SIDE // 2, cy + geo.VIA_SIDE // 2,
                )
            )
        spines[g] = spine

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
    x_centre = top_plate_exit_x()
    cell.shapes(metal5).insert(
        kdb.Box(
            x_centre - strap,
            -UNIT_CAP_GAP,
            x_centre + strap,
            (ARRAY_ROWS - 1) * UNIT_PITCH + 2 * geo.MIM_M4_ENCLOSURE
            + UNIT_CAP_NM + UNIT_CAP_GAP,
        )
    )
    return cell, assignment, spines


# --------------------------------------------------------------------------- #
# block-level CDAC plate routing (issue #86, Part 2 of #81)
# --------------------------------------------------------------------------- #


def _pick_column(
    preferred: int,
    lo: int,
    hi: int,
    taken: list[int],
    sep: int = ROUTE_SEP,
    step: int = 100,
) -> int:
    """The X nearest `preferred`, inside `[lo, hi]`, at least `sep` from every
    column already in `taken`.

    Searched rather than hand-picked, for the same reason `_clear_offset` and
    the `bridge_y0` loop below search: a top-level route is drawn OUTSIDE any
    `Channel`, so nothing downstream would notice two differently-named nets'
    columns landing on top of each other -- and a Metal2-over-Metal2 touch is a
    merged net `klt lvs` reports, not a DRC violation. This file's own history
    has that failure twice already, one metal level down.
    """
    span = max(hi - lo, 0)
    for k in range(span // step + 2):
        for candidate in dict.fromkeys((preferred + k * step, preferred - k * step)):
            if not lo <= candidate <= hi:
                continue
            if all(abs(candidate - t) >= sep for t in taken):
                return candidate
    raise RuntimeError(
        f"no free route column near x={preferred} inside {lo}..{hi} "
        f"({len(taken)} columns already placed, {sep} nm apart minimum)"
    )


def _via(
    cell: kdb.Cell, layers: dict[tuple[int, int], int], layer: tuple[int, int],
    x: int, y: int,
) -> kdb.Box:
    """One square via of the block's standard `geo.VIA_SIDE`, centred at
    `(x, y)`."""
    half = geo.VIA_SIDE // 2
    box = kdb.Box(x - half, y - half, x + half, y + half)
    cell.shapes(layers[layer]).insert(box)
    return box


def _route_cdac_plates(
    top: kdb.Cell,
    layers: dict[tuple[int, int], int],
    array_cell: kdb.Cell,
    array_x: dict[str, int],
    array_spines: dict[str, dict[str, kdb.Box]],
    array_y: int,
    banks: dict[str, place.PlacedBlock],
    bank_y: dict[str, int],
    switch: place.PlacedBlock,
    switch_x: int,
    assignment: dict[tuple[int, int], str],
) -> list[nl.Device]:
    """Wire both CDAC arrays' plates to the rest of the block, and return the
    1024 unit capacitors as `nl.Device`s for the LVS reference.

    WHAT HAS TO BE JOINED
    ---------------------
    Issue #85 left each array electrically self-contained: 512 real units per
    side on ONE Metal5 top-plate mesh and TEN disjoint Metal2 bottom-plate
    spines, none of which reach anything outside the array cell. `klt extract`
    saw exactly that -- two unnamed 512-device top nets and twenty unnamed
    bottom nets. This joins all twenty-two to the nets the schematic names:

    * each weight's spine -> that side's decode-bank trunk for the SAME
      internal node the T-gates share (`XS<P|N>.X<w>.bp`);
    * each side's single terminating unit's spine -> the shared `vcm` rail
      (DR-0011's 512th position, fixed to V_cm and never switched);
    * each side's top-plate mesh -> `topp`/`topn`, the nets the top-plate
      `V_cm` switches already drive.

    WHY THIS IS A METAL2/METAL3 ROUTE AND NOT THE FILE'S USUAL METAL1/POLY2
    ----------------------------------------------------------------------
    Every other top-level tie in this file (`geo.stitch`, the `vdd`/`vss`/`vcm`
    bridge) is a Metal1 trunk plus a Poly2 strap, because when they were drawn
    the extraction deck exposed ONE metal level. That constraint is gone at
    this repo's pinned commit (Metal1-Metal5 / Via1-Via4, klayout-tools
    #220/#238) and `geometry.draw_mim_bottom_riser` already relies on its
    replacement: **Metal2 crosses Metal1 with no connectivity at all**, so a
    Metal2 route may run straight over a decode bank's device row and over
    every trunk in its channel, and touches exactly the one trunk it drops a
    Via1 onto.

    That turns what the two-layer model would make a hard floorplan problem
    (side P's array sits at the TOP of the block while side P's decode bank
    sits at the BOTTOM, with side N's full-width transistor row physically in
    between) into an ordinary two-layer channel route, and it costs no area:
    the whole band between the decode banks and the arrays carries no Metal2
    or Metal3 whatsoever, so the lanes are drawn into space the block already
    occupies. No `escape` corridor is widened and no region gap is grown.

    THE CONSTRUCTION
    ----------------
    Twenty-two nets, each drawn as one "Z":

    1. a **vertical Metal2 drop** at the source's own X -- the spine's, which
       `SPINE_EXIT_Y` has already brought to the array cell's bottom edge;
    2. a **horizontal Metal3 lane** at a Y unique to that net;
    3. a **vertical Metal2 rise/drop** at a landing X inside the target Metal1
       trunk, ending in one Via1.

    Lanes are Metal3 and verticals are Metal2, so a vertical crossing a foreign
    lane carries no connectivity and the twenty-two routes need no ordering
    argument at all: correctness reduces to two independent, checked conditions
    -- every lane has its own Y (`LANE_PITCH`), and every vertical has its own
    X (`_pick_column`, which searches and raises). The top plate's source end
    additionally steps Metal5 -> Via4 -> Metal4 -> Via3 -> Metal3 down onto its
    lane; its lone Metal4 pad is asserted clear of the arrays' own Metal4 by
    `mim.space.1`.
    """
    metal2 = layers[geo.L_METAL2]
    metal3 = layers[geo.L_METAL3]
    metal4 = layers[geo.L_METAL4]
    metal5 = layers[geo.L_METAL5]

    half = ROUTE_W // 2
    group_order = [str(w) for w in WEIGHT_ORDER] + ["term"]
    array_bottom = array_y + array_cell.bbox().bottom

    # One lane per routed net. The top-plate lane of each side is deliberately
    # LAST (deepest): it is the only one carrying a Metal4 via pad, and depth
    # is what buys that pad its `mim.space.1` clearance from the array above.
    wires = [(tag, g) for tag in ("p", "n") for g in [*group_order, "top"]]
    lane_top = array_bottom - LANE_CLEARANCE
    lane_y = {wire: lane_top - i * LANE_PITCH for i, wire in enumerate(wires)}

    # -- 1: the source columns, which are fixed by where the spines are ----- #
    columns: list[int] = []
    src_x: dict[tuple[str, str], int] = {}
    for tag in ("p", "n"):
        for g in group_order:
            x = array_x[tag] + array_spines[tag][g].center().x
            src_x[(tag, g)] = x
            columns.append(x)
        src_x[(tag, "top")] = array_x[tag] + top_plate_exit_x()
    ordered = sorted(columns)
    for a, b in zip(ordered, ordered[1:]):
        if b - a < ROUTE_SEP:
            raise RuntimeError(
                f"two array spines exit {b - a} nm apart at x={a}/{b}, under "
                f"the {ROUTE_SEP} nm route pitch -- widen SPINE_GAP_STRIDE"
            )

    # -- 2: the target trunks, in top-level coordinates -------------------- #
    target: dict[tuple[str, str], kdb.Box] = {}
    for tag in ("p", "n"):
        for weight in WEIGHT_ORDER:
            net = f"XS{tag.upper()}.X{weight}.bp"
            target[(tag, str(weight))] = banks[tag].trunks[net].moved(0, bank_y[tag])
        target[(tag, "term")] = banks[tag].trunks["vcm"].moved(0, bank_y[tag])
        target[(tag, "top")] = switch.trunks[f"top{tag}"].moved(switch_x, array_y)

    # -- 3: the landing columns, searched inside their own trunk ----------- #
    dst_x: dict[tuple[str, str], int] = {}
    for wire in wires:
        trunk = target[wire]
        tag, g = wire
        # The two sides' decode banks are drawn identically, so their trunks
        # sit at identical X: nudge the two sides' landings apart up front so
        # the search normally succeeds on its first candidate.
        bias = -6000 if tag == "p" else 6000
        preferred = trunk.center().x + (0 if g == "top" else bias)
        x = _pick_column(
            preferred, trunk.left + ROUTE_W, trunk.right - ROUTE_W, columns
        )
        dst_x[wire] = x
        columns.append(x)

    # -- 4: draw ------------------------------------------------------------ #
    for wire in wires:
        tag, g = wire
        y = lane_y[wire]
        x_a, x_b = src_x[wire], dst_x[wire]
        trunk = target[wire]

        if g == "top":
            # Metal5 down from the mesh's own centre spine, then the via stack
            # onto this net's Metal3 lane. The drop's top edge is `array_y`,
            # i.e. `UNIT_CAP_GAP` INSIDE the mesh spine's own bottom edge
            # rather than abutting it -- an overlap, not a shared edge.
            top.shapes(metal5).insert(
                kdb.Box(x_a - half, y - half, x_a + half, array_y)
            )
            _via(top, layers, geo.L_VIA4, x_a, y)
            top.shapes(metal4).insert(
                kdb.Box(x_a - half, y - half, x_a + half, y + half)
            )
            if array_bottom - (y + half) < geo.MIM_M4_SPACE:
                raise RuntimeError(
                    f"top-plate Metal4 via pad at y={y} is "
                    f"{array_bottom - (y + half)} nm from the array's own "
                    f"Metal4 at {array_bottom}, under mim.space.1 "
                    f"({geo.MIM_M4_SPACE}) -- deepen its lane"
                )
            _via(top, layers, geo.L_VIA3, x_a, y)
        else:
            # Straight Metal2 drop from the spine's exit at the array's own
            # bottom edge; overlap it by a full route width rather than abut.
            top.shapes(metal2).insert(
                kdb.Box(x_a - half, y - half, x_a + half, array_bottom + ROUTE_W)
            )
            _via(top, layers, geo.L_VIA2, x_a, y)

        top.shapes(metal3).insert(
            kdb.Box(min(x_a, x_b) - half, y - half, max(x_a, x_b) + half, y + half)
        )
        _via(top, layers, geo.L_VIA2, x_b, y)

        ty = trunk.center().y
        top.shapes(metal2).insert(
            kdb.Box(x_b - half, min(y, ty) - half, x_b + half, max(y, ty) + half)
        )
        landing = _via(top, layers, geo.L_VIA1, x_b, ty)
        if not trunk.contains(landing.p1) or not trunk.contains(landing.p2):
            raise RuntimeError(
                f"Via1 for {tag}/{g} at {landing} is not inside its own trunk "
                f"{trunk} -- it would land on whatever else is at that track"
            )

    # -- 5: the capacitors, as devices for the LVS reference ---------------- #
    # Constructed here, one per REAL drawn unit, NOT taken from the flattened
    # schematic: `adc_cdac_side` models each weight as ONE lumped capacitor of
    # the whole weight's area (its own comment says why -- 1022 unit cells
    # would multiply simulation cost and change no number), while the layout
    # draws `m` unit-size caps in parallel. Both are the same capacitance and
    # neither is the other's device list, so the reference has to state the
    # DRAWN one.
    caps: list[nl.Device] = []
    for tag in ("p", "n"):
        for (c, r), g in sorted(assignment.items()):
            caps.append(
                nl.Device(
                    kind="cap",
                    path=f"XS{tag.upper()}.CU{c}_{r}",
                    nets=(
                        f"top{tag}",
                        "vcm" if g == "term" else f"XS{tag.upper()}.X{g}.bp",
                    ),
                    params={"w": UNIT_CAP_NM * 1e-9, "l": UNIT_CAP_NM * 1e-9},
                )
            )
    return caps


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

    SAME-NET pairs are checked too (issue #116). They cannot short -- that is
    why they were originally skipped -- but two bars of one net that come
    within the Metal1 spacing rule WITHOUT touching are still a real
    `metal1.space.1` violation, and `klt drc` reports one. The skip was found
    by the `adc_block_nores` companion, whose comparator packs one track
    differently and so reached a `cmp_y` where its own `vdd`/`vss` strap sat
    170 nm from a decode bank's: electrically harmless, geometrically
    illegal, and invisible to every check this file ran before.
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
    comparator_resistors: bool = True,
) -> tuple[kdb.Layout, dict]:
    """Draw the block.

    With `comparator_subckts` given, the comparator cell from
    `gen_comparator.py` is assembled into the same stream (the `adc_block`
    deliverable) and its devices join the LVS reference. Without it, the
    stream is exactly what `design/adc-top/adc_top.spice` defines, which is
    what makes `adc_top.gds`'s LVS claim a claim against that file and
    nothing else.

    `comparator_resistors=False` draws the SAME assembled block with the
    comparator's two 150 kohm p+ poly load-resistor bodies omitted -- the
    block-level analogue of `gen_comparator.py`'s own `comparator_nores`
    companion cell, and for the same reason: the pinned `klt extract`
    gf180mcu deck has no resistor device class, so a drawn poly body
    extracts as a plain conductor and collapses `pop`/`pon` onto `vdd`. At
    LVS that only costs resolution; in a POST-LAYOUT TRANSIENT it is fatal
    -- with both preamp drains and both StrongARM latch input gates hard-
    tied to `vdd`, the comparator has no gain and no decision, which is the
    stuck-code defect issue #116 root-caused (`parasitics/records/
    20260806-adc-block-comparator-input-open.md`). This variant keeps
    `pop`/`pon` distinct so `parasitics/remediate_extracted.py` can put the
    two resistors back as the ideal devices `design/comparator/
    comparator.spice` specifies, leaving every other element post-layout.
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
    # DR-0014's fourth leg (`vin`, resolved by `block_subckt` to `pinp`/
    # `pinn` -- issue #91). UNLIKE `bank_shared`, this is NOT one net shared
    # by both sides: `pinp` lives only in the P bank, `pinn` only in the N
    # bank, exactly like each side's own `rel_*_p`/`_n` control pins below,
    # so it needs no cross-bank stitch (no entry in `escape`/the rail-tie
    # loop). It DOES need the ordinary within-bank treatment every other
    # decode-bank net gets: `Xsi`'s drain terminal already resolves to this
    # literal net name at every one of a side's nine weighted cells (`nl.
    # flatten` renames `vin` to `pin{tag}` one level up, in `block_subckt`,
    # before ever reaching `adc_cdac_cell`), so `place.draw_devices`'s
    # `Channel` already merges all nine drops into ONE trunk spanning the
    # whole row -- see `lib/geometry.Channel._spans`. The only thing missing
    # was the pin label itself: `Channel.finish()` draws every net's trunk
    # unconditionally but only labels (`mark_pin`) the nets named in `pins`,
    # so the net was already a real, correctly-routed, single-piece Metal1
    # trunk with no external name -- `klt extract` reported it as an
    # anonymous net (`$8`/`$91`), not floating and not merged with anything
    # else. Confirmed directly (not assumed) against
    # `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/
    # adc_top.para.spice`: every `nfet_03v3 L=0.28U W=10U` device gated by
    # `sel_in` shares one net on its drain, on both sides, matching the
    # description above exactly.
    input_pin = {"p": "pinp", "n": "pinn"}

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
            pins=bank_shared
            + [input_pin[tag]]
            + [p for p in control_pins if p.endswith(f"_{tag}")],
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
    # The per-weight spine boxes each array returns (issue #85) are the handle
    # `_route_cdac_plates` (issue #86) consumes to reach the decode banks,
    # without re-deriving any geometry from the drawn cells.
    array_cell_p, assignment, spines_p = draw_cdac_array(
        layout, layers, "ADC_CDAC_ARRAY_P"
    )
    array_cell_n, _, spines_n = draw_cdac_array(layout, layers, "ADC_CDAC_ARRAY_N")

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

    # -- tie both arrays' plates into the rest of the block ---------------- #
    cap_devices = _route_cdac_plates(
        top,
        layers,
        array_cell_p,
        {"p": 0, "n": array_w + REGION_GAP * 2},
        {"p": spines_p, "n": spines_n},
        array_y,
        banks,
        {"p": bank_p_y, "n": bank_n_y},
        switch,
        switch_x,
        assignment,
    )

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
            with_resistors=comparator_resistors,
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
        # The DECODE BANKS' own `vdd`/`vss` trunks belong in the fixed set
        # too, for exactly the reason the paragraph above gives about
        # `switch`: they are grown to the far corridor (see the `vdd`/`vss`
        # strap below), which runs PAST the comparator, so a `cmp_y` that
        # clears `switch` can still land the comparator's own trunk within
        # the Metal1 spacing rule of a bank trunk. Found by issue #116's
        # `adc_block_nores` companion, whose comparator packs one track
        # differently (no resistor-terminal drops) and so exercised a
        # `cmp_y` the deliverable block happens not to reach: `klt drc`
        # reported two `metal1.space.1` violations, a 170 nm gap between the
        # comparator's strap and a bank strap. A search told about only some
        # of the bars it has to clear is exactly the defect class this
        # search exists to rule out.
        bank_escaped = ("vdd", "vss")
        cmp_y = _clear_offset(
            [
                (net, switch.trunks[net].moved(switch_x, array_y))
                for net in switch_escaped
            ]
            + [
                (net, banks[tag].trunks[net].moved(0, bank_y))
                for tag, bank_y in (("p", bank_p_y), ("n", bank_n_y))
                for net in bank_escaped
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

    ref_devices = list(mos) + cap_devices
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
        "transistor_count": sum(1 for d in ref_devices if d.is_mos),
        "cap_count": sum(1 for d in ref_devices if d.kind == "cap"),
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
        "*   - the CDAC arrays' capacitors are stated as the layout DRAWS them,",
        f"*     not as the schematic writes them: {info['cap_count']} unit-size",
        "*     `cap_mim_2f0_m4m5_noshield` devices (512 real positions per side",
        "*     -- 511 weighted plus DR-0011's terminating unit), each 2.7136 um",
        "*     square, in parallel per weight. `adc_cdac_side` instead models",
        "*     each weight as ONE lumped capacitor of the whole weight's area",
        "*     (its own comment says why: drawing 1022 unit cells in the",
        "*     simulation deck would multiply cost and change no number). Same",
        "*     capacitance, different device list -- so the reference states the",
        "*     drawn one, which is what `klt extract` reports. Issues #85 (the",
        "*     within-array interconnect) and #86 (the route out to the decode",
        "*     banks, the `vcm` terminating tie and the top-plate mesh's tie to",
        "*     `topp`/`topn`) are what made these capacitors reachable at all;",
        "*     before them they were absent from this reference entirely.",
        "*   - each capacitance is the extraction deck's own two-term MiM model",
        "*     of the drawn plate (area + perimeter/fringe, ~17.24 fF), matching",
        "*     the PDK model card's own area+fringe value for the same plate",
        "*     (issue #116, klayout-tools#517: the deck's prior area-only model",
        "*     -- 14.7316 fF, 14.6% low -- is superseded as of the af5791b ->",
        "*     875eac3 pin bump). See lib/netlist.py's",
        "*     DECK_MIM_AREA_CAP_F_UM2/DECK_MIM_PERIM_CAP_F_UM.",
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
        path,
        cell_name,
        info["devices"],
        info["pins"],
        info["body_net"],
        header,
        # The array's unit caps are drawn as RECOGNISED devices (CAP_MK /
        # MIM_L_MK + Via4, issue #85) with both plates now wired (issue #86),
        # which is exactly the precondition `netlist.write_reference` documents
        # for this flag.
        include_caps=True,
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
            "",
            "options.parameter_tolerance (issue #116, klayout-tools#589/#591):",
            "both sides now state the same two-term MiM capacitance law",
            "(layout/adc-top/lib/netlist.py's DECK_MIM_AREA_CAP_F_UM2/",
            "DECK_MIM_PERIM_CAP_F_UM, matching klayout-tools' own gf180mcu",
            "CapacitorDevice coefficients as of the af5791b -> 875eac3 pin",
            "bump), but KLayout's dbu-grid-snapped polygon area/perimeter and",
            "this module's ideal plate_w_nm*plate_l_nm arithmetic differ by a",
            "few parts in 10^4 -- enough for the highly-symmetric CDAC array",
            "(1024 identically-shaped unit caps distinguished mostly by which",
            "decode net they land on) to lose exact-value disambiguation and",
            "cascade into device.unmatched/net.merged/net.split. 0.1% absorbs",
            "that residual without masking a real capacitance defect (a real",
            "short/open changes topology, not a device's own value).",
        ],
        "layout": {"netlist": f"{key}.spice", "top": cell_name},
        "reference": {"netlist": f"{key}.ref.spice", "top": cell_name},
        "options": {"parameter_tolerance": 0.001},
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
    for key, cell_name, cmp_subckts, cmp_res in (
        ("adc_top", CELL_NAME, None, True),
        ("adc_block", BLOCK_CELL_NAME, comparator_subckts, True),
        # Simulation companion, NOT a deliverable: the same assembled block
        # with the comparator's poly load-resistor bodies omitted, so
        # `pop`/`pon` survive extraction as distinct nets. See build()'s
        # `comparator_resistors` docstring and issue #116.
        ("adc_block_nores", BLOCK_NORES_CELL_NAME, comparator_subckts, False),
    ):
        layout, info = build(
            subckts, cmp_subckts, cell_name=cell_name,
            comparator_resistors=cmp_res,
        )
        assert layout.dbu == geo.DBU_UM, f"dbu drifted to {layout.dbu}"
        layout.write(os.path.join(args.outdir, f"{key}.gds"), geo.save_options())
        write_reference(
            os.path.join(args.outdir, f"{key}.ref.spice"), info, cell_name, key
        )
        write_request(os.path.join(args.outdir, f"{key}.lvs.json"), cell_name, key)
        box = layout.cell(cell_name).bbox()
        print(
            f"wrote {key}.gds  transistors={info['transistor_count']}  "
            f"caps={info['cap_count']}  "
            f"{box.width() * geo.DBU_UM:.1f} x {box.height() * geo.DBU_UM:.1f} um "
            f"= {geo.area_um2(box) / 1e6:.5f} mm^2"
        )
        # area.json states the DELIVERABLE block's tally. `adc_block_nores`
        # is a simulation companion whose comparator is deliberately
        # incomplete, so it must never be what the area row reports.
        if cell_name != BLOCK_NORES_CELL_NAME:
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
        "transistor_count": tally_info["transistor_count"],
        "unit_cap_device_count": tally_info["cap_count"],
        "unit_cap_positions_per_side": ARRAY_COLS * ARRAY_ROWS,
        "unit_cap_census_per_side": census,
    }
    with open(os.path.join(args.outdir, "area.json"), "w", encoding="utf-8") as fh:
        json.dump(tally, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"  unit-cap census per side: {census}")


if __name__ == "__main__":
    main()
