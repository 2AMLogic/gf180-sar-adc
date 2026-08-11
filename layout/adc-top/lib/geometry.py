#!/usr/bin/env python3
"""Shared gf180mcu layout primitives for the `design/adc-top/` block layout
(issue #57).

WHAT THIS IS
------------
A small, hand-rolled cell library -- MOSFET generation, a two-layer
(Metal1 trunk / Poly2 riser) channel router, guard rings, and a MiM
capacitor footprint drawer -- built directly against the pip `klayout`
package's batch database API. Same API and same reason as
`layout/drc/cells/gen_sw_unit.py` and `layout/lvs/cells/gen_lvs_unit.py`
already use: `klt` has no layout-generation verb for arbitrary geometry
(`klt gen`'s PCell harness generates single parametrised primitives, not a
placed-and-routed block; the general capability is upstream epic
2AMLogic/klayout-tools#152). This module generalises that one-proof-device
pattern into the reusable devices and routing this block's schematic
(`design/adc-top/adc_top.spice`) actually instantiates -- see
`../README.md` for the full design-to-layout mapping and every stated
deviation.

THE ROUTING MODEL, AND WHY IT LOOKS LIKE THIS
---------------------------------------------
When this library was written, `klt extract`'s gf180mcu `ExtractionDeck`
declared exactly ONE metal level (`metals=((34, 0),)`) and no via layers, so
the only interconnect the LVS flow could see was **Metal1 plus Poly2** (poly
is a registered, connected region, joined to Metal1 only through Contact).
Every net therefore had to close in a *two-layer planar* graph, which is the
single biggest shape driver in this directory.

The pinned deck now carries the full Metal1-Metal5 / Via1-Via4 stack
(upstream klayout-tools#220/#238, picked up by the pin bump in issue #70),
so that constraint is no longer forced. The transistor-level routing below
is nevertheless left exactly as it was: it is drawn, DRC-clean and
LVS-matched, and re-routing 323 devices onto a five-level stack is a
distinct piece of work with its own evidence to produce -- not a free
side-effect of a toolchain bump. What DOES use the upper levels is the MiM
capacitor stack at the bottom of this file, which cannot be a recognised
device without them.

The construction that makes two layers sufficient, applied uniformly to
every cell here:

* **Devices sit in one row**, gate heads pointing DOWN, NMOS columns first
  then PMOS columns (so a single Nwell island covers every PMOS in the row
  and `nwell.space.1` never applies inside a cell at all).
* **Every net gets one horizontal Metal1 "trunk"**, stacked in a routing
  channel below the device row, one trunk per net, at its own Y slot.
* **Every device terminal drops to its trunk on a vertical Poly2 "riser"**
  at that terminal's own X. Poly2 passes *under* every foreign trunk
  without connecting to it (there is no poly<->metal1 connect in the deck;
  only Contact joins them), and touches its own trunk through exactly one
  Contact. A gate riser is simply the gate head's own poly extended
  downward -- no contact needed at the device end.

This is a real, if deliberately unclever, channel-routing discipline: it is
correct by construction for any net list, and every crossing it makes is a
Metal1-over-Poly2 crossing, which carries no connectivity. A first cut of
this library instead ran per-net Metal1 buses with Metal1 stubs; `klt
extract` caught it merging four nets into one (`"clk,clkb,vin,vout"`), which
is exactly the defect this scheme cannot express.

DEVICE CONSTRUCTION: single-finger, not classic interdigitated multi-finger
--------------------------------------------------------------------------
Every MOSFET below is drawn as ONE gate stripe crossing ONE active island at
its full drawn channel width `W` -- not as N parallel narrow fingers tied by
a shared source/drain bus, which is the layout style a real tapeout of a
40/80 um device would use. Deliberate and stated (see `../README.md`
"Deviation: single-finger devices"), driven by two independent facts:

1. `design/adc-top/adc_top.spice` itself models every switch leg as ONE
   lumped SPICE device at its full W -- that is this issue's literal LVS
   target.
2. `klt`'s LVS engine (`klayout_tools/lvs.py`, wrapping
   `klayout.db.NetlistComparer`) never calls `Netlist.combine_devices()` on
   either side. A finger-interleaved layout extracts as N parallel MOSFETs
   per leg, which the comparer reports as `device.unmatched` against a
   single-lumped-device reference -- confirmed by reading `lvs.py` in the
   pinned `klt`, not assumed.

CONTACT SIMPLIFICATION: bars, not discrete squares
--------------------------------------------------
The real gf180mcu DRM (`CO.1`) draws contacts as a fixed 0.22 x 0.22 um
square in an array. This deck's `contact.width.1` enforces only the
**minimum**-width half of that rule (see `decks/gf180mcu.py`'s own
docstring), so one wide contact **bar** spanning a source/drain's full
width is legal here though a real mask deck would reject it. A deliberate
use of an already-documented curated-deck approximation, to keep geometry
tractable at this block's device count (224 transistors) -- see
`../README.md`.

DATABASE UNIT
-------------
Written at the KLayout default dbu of 0.001 um (1 nm), same convention as
`layout/drc/cells/gen_sw_unit.py` / `layout/lvs/cells/gen_lvs_unit.py`, for
the same reason: `klt`'s decks author their thresholds in nanometres.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import klayout.db as kdb

DBU_UM = 0.001  # 1 nm; every coordinate in this module is in nanometres.

# --- gf180mcu drawn layers (layer/datatype) ------------------------------
# The five the `klt drc` / `klt extract` gf180mcu decks actually read, plus
# the Metal1 text purpose used for net naming.
L_NWELL = (21, 0)
L_COMP = (22, 0)
L_POLY2 = (30, 0)
L_CONTACT = (33, 0)
L_METAL1 = (34, 0)
L_METAL1_LABEL = (34, 10)  # text/label purpose -- EXTRACTION_DECK.metal_labels

# --- Upper routing stack (gf180mcu) --------------------------------------
# Metal1-Metal5 and Via1-Via4 are ALL part of `klt extract`'s gf180mcu
# `ExtractionDeck` connectivity at this repo's pinned commit (upstream
# klayout-tools#220/#238) -- `vias[i]` joins `metals[i]` to `metals[i+1]`.
# Anything drawn on them is real connectivity, not decoration.
L_VIA1 = (35, 0)
L_METAL2 = (36, 0)
L_VIA2 = (38, 0)
L_METAL3 = (42, 0)
L_VIA3 = (40, 0)

# --- MiM capacitor stack (gf180mcu, DRM 10.4.2 "MIM Option B") -----------
# The bottom plate is Metal4, the top plate is FuseTop, and Via4 lands on
# FuseTop to bring the top plate up to Metal5 -- the 5LM stack this repo's
# `gf180mcuD` variant is wired for (sim/harness/pdk.py's
# `MIM_STACK_BY_VARIANT`). `CAP_MK` + `MIM_L_MK` over the FuseTop plate are
# what make the stack a recognised `cap_mim_2f0_m4m5_noshield` DEVICE rather
# than three inert polygons: the gf180mcu extraction deck derives
# `fusetop.interacting(cap_mk).interacting(mim_l_mk)` exactly as the PDK's
# own KLayout LVS deck does. Both the DRC rules (`mim.enclosing.fusetop.1`,
# `mim.space.1`, `mim.enclosing.via4.1`) and the device recognition arrived
# upstream AFTER this directory was first written -- see ../toolchain.json.
L_METAL4 = (46, 0)  # MiM bottom plate
L_VIA4 = (41, 0)  # top-plate via, FuseTop -> Metal5
L_FUSETOP = (75, 0)  # MiM top plate
L_METAL5 = (81, 0)  # top-plate routing metal
L_METAL5_LABEL = (81, 10)  # text/label purpose -- EXTRACTION_DECK.metal_labels
L_CAP_MK = (117, 5)  # capacitor mark
L_MIM_L_MK = (117, 10)  # MiM-L mark

# --- Drawn-resistor markers (gf180mcu, issue #118) ------------------------
# `klt extract`'s gf180mcu `ResistorDevice` entries (klayout-tools#222/#299,
# see `../README.md` "Resistors" and `place.draw_poly_resistor`) recognise a
# marked Poly2 body as a real device instead of an ordinary conductor:
#   SAB (49/0) + RES_MK (110/5), no Resistor       -> `ppolyf_u`    350 ohm/sq
#   SAB (49/0) + RES_MK (110/5) + Resistor (62/0)  -> `ppolyf_u_1k` 1000 ohm/sq
# The PDK's own `_2k`/`_3k` high-sheet-rho flavours share the SAME drawn
# `Resistor`-marked geometry (selected only by a build-time deck option this
# curated deck does not model) and are therefore NOT reachable by drawing
# anything different -- `2AMLogic/klayout-tools#595`, open upstream.
L_SAB = (49, 0)  # salicide block -- REQUIRED, not optional, for either flavour
L_RES_MK = (110, 5)  # resistor mark
L_RESISTOR = (62, 0)  # high-sheet-rho selector -> ppolyf_u_1k (this deck's only wired flavour)

LAYER_NAMES = {
    L_NWELL: "Nwell",
    L_COMP: "Comp",
    L_POLY2: "Poly2",
    L_CONTACT: "Contact",
    L_METAL1: "Metal1",
    L_METAL1_LABEL: "Metal1.label",
    L_VIA1: "Via1",
    L_METAL2: "Metal2",
    L_VIA2: "Via2",
    L_METAL3: "Metal3",
    L_VIA3: "Via3",
    L_VIA4: "Via4",
    L_METAL4: "Metal4",
    L_FUSETOP: "FuseTop",
    L_METAL5: "Metal5",
    L_METAL5_LABEL: "Metal5.label",
    L_CAP_MK: "CAP_MK",
    L_MIM_L_MK: "MIM_L_MK",
    L_SAB: "SAB",
    L_RES_MK: "RES_MK",
    L_RESISTOR: "Resistor",
}

# --- Construction constants (nm; dbu = 1 nm) -----------------------------
# Every margin is chosen with headroom over the gf180mcu deck's own
# thresholds (poly2.width 180, poly2.space 240, comp.width 220,
# comp.space 280, contact.width 220, contact.space 250, metal1.width 230,
# metal1.space 230, *.enclosing.contact 70, nwell.space 600,
# nwell.enclosing.comp 120 -- read from `klayout_tools.decks.get_deck`,
# not from the DRM) so DRC-cleanliness is a property of the construction
# rather than a per-instance balancing act.
SD_EXT = 1100  # source/drain active extension beyond the gate edge, each side
GATE_TO_SD_CONTACT_GAP = 650  # gate edge -> near edge of the S/D contact bar
SD_CONTACT_THICKNESS = 260  # S/D contact bar thickness along the channel-length axis
SD_CONTACT_Y_MARGIN = 150  # inset from the active island's Y edges to the S/D contact
GATE_HEAD_H = 600  # poly2 head height below the active island
GATE_HEAD_MARGIN = 300  # poly2 head overhang beyond the gate stripe, each side
METAL_PAD_MARGIN = 60  # metal1 pad overhang beyond its contact bar, each side
#: Gap between adjacent device columns' active islands. This is the single
#: multiplier on every placed row's width -- a device row here is N columns
#: of `2 * SD_EXT + L` active plus N of these -- so it is the constant that
#: decides whether the assembled block fits its ratified area row (issue
#: #67). Set at `comp.space.1` (280) + 120 nm of headroom rather than at the
#: 900 nm this library was first written with: 900 was three times the rule
#: with no stated reason, and at 144 columns per decode bank it spent 72 um
#: of bank width on nothing. Every OTHER clearance across a column boundary
#: is looser than this one by construction and is asserted below, so
#: `comp.space.1` really is the binding rule here -- and it is a rule the
#: deck checks, so the choice is verified rather than argued.
COLUMN_GAP = 400
NWELL_MARGIN = 500  # Nwell overhang beyond the PMOS active it covers

RISER_W = 400  # Poly2 riser width (>= contact 240 + 2 x 70 enclosure)
RISER_CONTACT = 240  # square contact side, riser <-> Metal1
DROP_H = 600  # metal drop-stub reach below the gate head's bottom edge
RISER_CONTACT_TOP_OFF = 260  # head bottom -> top of the riser's upper contact
TRUNK_H = 340  # Metal1 trunk thickness
TRUNK_GAP = 280  # vertical gap between adjacent trunks (> metal1.space 230)
TRUNK_PITCH = TRUNK_H + TRUNK_GAP
CHANNEL_TOP_GAP = 500  # riser-zone height between DROP level and the first trunk

# Symbolic clearance checks, asserted at import so a future constant edit
# cannot quietly produce a DRC-dirty library. Each is independent of L and W.
_METAL1_SPACE_MIN = 230
_POLY2_SPACE_MIN = 240
_CONTACT_SPACE_MIN = 250
_COMP_SPACE_MIN = 280
#: `nwell.space.1`. Not used by anything in THIS module (a row draws one
#: Nwell island per placed group -- see `draw_shared_nwell`), but `place.py`
#: sizes its inter-group keepout against it and asserts the drawn result, so
#: the threshold lives here beside the other four rather than in two places.
_NWELL_SPACE_MIN = 600
# `nwell.enclosing.comp.1` is a *containment* rule (satisfied by
# `NWELL_MARGIN`); the DRM's separate "Nwell to unrelated COMP" rule is NOT
# in the pinned deck at all, so it cannot be verified here. `place.py` keeps
# its own keepout at `_NWELL_SPACE_MIN` + headroom anyway, which is the same
# by-construction discipline the MiM stack's spacing uses -- a design-time
# argument, stated as such, not a checked result.

#: X distance from the gate stripe's own edge to the centre of the nearest
#: source/drain riser, i.e. how far apart the gate poly (head) and an S/D
#: poly riser sit.
_GATE_EDGE_TO_SD_RISER = GATE_TO_SD_CONTACT_GAP + SD_CONTACT_THICKNESS // 2
assert _GATE_EDGE_TO_SD_RISER - GATE_HEAD_MARGIN - RISER_W // 2 >= _POLY2_SPACE_MIN, (
    "gate head / S-D poly riser clearance violates poly2.space.1"
)
#: Metal1 S/D drop stub (pad width) vs. the gate head's Metal1 -- there is
#: no Metal1 in the head in this construction (the gate riser is poly all
#: the way down), so the only Metal1-to-Metal1 clearance inside a device is
#: source stub vs. drain stub, which is 2 x _GATE_EDGE_TO_SD_RISER apart.
_SD_PAD_W = SD_CONTACT_THICKNESS + 2 * METAL_PAD_MARGIN
assert 2 * _GATE_EDGE_TO_SD_RISER - _SD_PAD_W >= _METAL1_SPACE_MIN, (
    "source/drain drop stubs violate metal1.space.1"
)
assert RISER_W - RISER_CONTACT >= 2 * 70, "riser too narrow for poly2.enclosing.contact.1"
assert TRUNK_GAP >= _METAL1_SPACE_MIN, "trunk pitch violates metal1.space.1"
assert TRUNK_H - RISER_CONTACT >= 0, "trunk too thin to hold a riser contact"
#: `comp.enclosing.contact.1` (70nm) on the source/drain contact bar's outer
#: edge: the bar's far edge sits `GATE_TO_SD_CONTACT_GAP + SD_CONTACT_THICKNESS`
#: past the gate edge, inside an active island that reaches `SD_EXT`.
assert SD_EXT - GATE_TO_SD_CONTACT_GAP - SD_CONTACT_THICKNESS >= 70 + 100, (
    "source/drain contact bar violates comp.enclosing.contact.1"
)

#: Everything that crosses a COLUMN boundary, so `COLUMN_GAP` can be set
#: from the one rule that actually binds it (`comp.space.1`) instead of from
#: a round number three times larger than any of them. Distance between the
#: nearest risers of two adjacent columns: A's drain riser to B's source
#: riser, both inset `SD_EXT - _GATE_EDGE_TO_SD_RISER` from their own active
#: island's outer edge.
_COLUMN_RISER_PITCH = 2 * SD_EXT + COLUMN_GAP - 2 * _GATE_EDGE_TO_SD_RISER
assert COLUMN_GAP >= _COMP_SPACE_MIN + 100, (
    "adjacent device columns' active islands violate comp.space.1"
)
assert _COLUMN_RISER_PITCH - RISER_W >= _POLY2_SPACE_MIN, (
    "adjacent device columns' S/D poly risers violate poly2.space.1"
)
assert _COLUMN_RISER_PITCH - _SD_PAD_W >= _METAL1_SPACE_MIN, (
    "adjacent device columns' S/D drop stubs violate metal1.space.1"
)
assert _COLUMN_RISER_PITCH - SD_CONTACT_THICKNESS >= _CONTACT_SPACE_MIN, (
    "adjacent device columns' S/D contact bars violate contact.space.1"
)
assert 2 * SD_EXT + COLUMN_GAP - 2 * GATE_HEAD_MARGIN >= _POLY2_SPACE_MIN, (
    "adjacent device columns' gate heads violate poly2.space.1"
)

# --- MiM capacitor construction (nm) -------------------------------------
# Unlike every constant above, these three are not "a threshold plus stated
# headroom": they are the DRM's own MiM numbers taken exactly, because the
# unit capacitor's PITCH is `plate + 2*MIM_M4_ENCLOSURE + MIM_M4_SPACE` and
# every nanometre of headroom here is multiplied by 1024 unit positions.
# Each is a rule the pinned deck CHECKS (`../toolchain.json`), so drawing at
# the threshold is a claim `klt drc` can falsify rather than an argument.
#: `mim.enclosing.fusetop.1` / DRM `MIMTM.3`: minimum MiM bottom-plate
#: (Metal4) overlap of the top plate (FuseTop), 0.6 um on every side.
MIM_M4_ENCLOSURE = 600
#: `mim.space.1` / DRM `MIMTM.1`: minimum MiM bottom-plate spacing to any
#: other bottom-plate metal, 1.2 um.
MIM_M4_SPACE = 1200
#: `mim.enclosing.via4.1` / DRM `MIMTM.2`: minimum MiM (virtual) bottom-plate
#: overlap of Via4, 0.4 um. The virtual bottom plate is `FuseTop` sized by
#: 1.06 um intersected with `Metal4`, which for this construction is exactly
#: the drawn Metal4 (it sits 0.6 um < 1.06 um outside FuseTop), so the drawn
#: rule is "Via4 at least 0.4 um inside the drawn Metal4".
MIM_VIA4_ENCLOSURE = 400
#: Via4 / Via3 / Via2 / Via1 side. No width or spacing rule in the pinned
#: deck covers any of the four (only `mim.enclosing.via4.1` mentions Via4 at
#: all), so this is sized from the DRM's own 0.26 um `Vn.1` square rather
#: than from anything the deck could check -- stated, not implied.
VIA_SIDE = 260
#: Metal enclosure of a via in the plate down-stack, each side.
VIA_METAL_MARGIN = 140
_METAL2_WIDTH_MIN = 280
_METAL2_SPACE_MIN = 280
_METAL3_WIDTH_MIN = 280
_METAL5_WIDTH_MIN = 280
assert VIA_SIDE + 2 * VIA_METAL_MARGIN >= _METAL2_WIDTH_MIN, (
    "via landing pad narrower than metal2.width.1/metal3.width.1"
)
assert VIA_SIDE + 2 * VIA_METAL_MARGIN >= _METAL5_WIDTH_MIN, (
    "top-plate Via4 landing pad narrower than metal5.width.1"
)
#: The down-stack's Via3 sits in the Metal4 ring OUTSIDE the FuseTop plate
#: (see `draw_mim_cap`), so the ring has to be wide enough to hold it with
#: `MIM_VIA4_ENCLOSURE`-equivalent margin on the outer edge.
assert MIM_M4_ENCLOSURE >= VIA_SIDE + 2 * VIA_METAL_MARGIN, (
    "Metal4 ring too narrow to hold the bottom-plate down-stack via"
)


def save_options() -> kdb.SaveLayoutOptions:
    """GDSII writer options that make the output byte-reproducible -- same
    rationale/setting as `gen_sw_unit.py`/`gen_lvs_unit.py`: suppress
    KLayout's default BGNLIB/BGNSTR wall-clock timestamps so a committed
    GDS hash is a real integrity check."""
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def make_layout() -> tuple[kdb.Layout, dict[tuple[int, int], int]]:
    """A fresh `Layout` at this module's `DBU_UM`, with every layer above
    registered and named. Returns `(layout, layer_index_by_spec)`."""
    layout = kdb.Layout()
    layout.dbu = DBU_UM
    layers: dict[tuple[int, int], int] = {}
    for spec, name in LAYER_NAMES.items():
        idx = layout.layer(*spec)
        layout.set_info(idx, kdb.LayerInfo(spec[0], spec[1], name))
        layers[spec] = idx
    return layout, layers


# --------------------------------------------------------------------------- #
# devices
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Mosfet:
    """One drawn single-finger MOSFET and the three riser X positions its
    terminals present to the channel router below it."""

    active: kdb.Box
    is_pmos: bool
    w: int
    l: int
    source_x: int
    gate_x: int
    drain_x: int
    #: Y at which every riser leaves this device (bottom of the Metal1 drop
    #: stubs / of the gate head's poly extension).
    riser_y: int

    def riser_x(self, terminal: str) -> int:
        return {"s": self.source_x, "g": self.gate_x, "d": self.drain_x}[terminal]


def column_pitch(l: int) -> int:
    """X pitch between adjacent device columns for gate length `l`."""
    return 2 * SD_EXT + l + COLUMN_GAP


def draw_mosfet(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    x0: int,
    y0: int,
    w: int,
    l: int,
    is_pmos: bool,
) -> Mosfet:
    """Draw one single-finger MOSFET with its gate head pointing DOWN and
    all three terminals dropped to a common riser level below the head.

    `x0`/`y0` are the active island's lower-left corner; current flows along
    +X (source low, drain high), channel width `w` runs along +Y, `l` is the
    drawn gate length. Nwell for a PMOS is the caller's job (see
    `draw_shared_nwell`) because a real row shares one well island rather
    than drawing one per device -- which sidesteps `nwell.space.1` entirely
    instead of satisfying it per device.

    Returns the `Mosfet` record the channel router consumes. Connectivity is
    purely geometric here; there is no separate net abstraction, exactly how
    `klt extract`'s `l2n.connect(...)` graph reads a stream.
    """
    comp = layers[L_COMP]
    poly2 = layers[L_POLY2]
    contact = layers[L_CONTACT]
    metal1 = layers[L_METAL1]

    total_l = 2 * SD_EXT + l
    active = kdb.Box(x0, y0, x0 + total_l, y0 + w)
    cell.shapes(comp).insert(active)

    gate_x0 = x0 + SD_EXT
    gate_x1 = gate_x0 + l
    cell.shapes(poly2).insert(kdb.Box(gate_x0, y0, gate_x1, y0 + w))

    head_y1 = y0
    head_y0 = y0 - GATE_HEAD_H
    cell.shapes(poly2).insert(
        kdb.Box(gate_x0 - GATE_HEAD_MARGIN, head_y0, gate_x1 + GATE_HEAD_MARGIN, head_y1)
    )

    riser_y = head_y0 - DROP_H

    # Gate riser: the head's own poly, continued down to the riser level.
    gate_x = (gate_x0 + gate_x1) // 2
    cell.shapes(poly2).insert(
        kdb.Box(gate_x - RISER_W // 2, riser_y, gate_x + RISER_W // 2, head_y0)
    )

    def sd(terminal_x: int) -> None:
        """Source/drain contact bar, Metal1 pad, Metal1 drop stub down to
        `riser_y`, the Poly2 riser stub, and the Contact joining them."""
        bar = kdb.Box(
            terminal_x - SD_CONTACT_THICKNESS // 2,
            y0 + SD_CONTACT_Y_MARGIN,
            terminal_x + SD_CONTACT_THICKNESS // 2,
            y0 + w - SD_CONTACT_Y_MARGIN,
        )
        cell.shapes(contact).insert(bar)
        pad = bar.enlarged(METAL_PAD_MARGIN, METAL_PAD_MARGIN)
        cell.shapes(metal1).insert(pad)
        # Drop stub: from the pad's bottom edge past the head, to riser_y.
        cell.shapes(metal1).insert(
            kdb.Box(pad.left, riser_y, pad.right, pad.bottom)
        )
        # Poly2 riser stub under it, plus the Contact that joins the two.
        cell.shapes(poly2).insert(
            kdb.Box(
                terminal_x - RISER_W // 2,
                riser_y,
                terminal_x + RISER_W // 2,
                head_y0 - RISER_CONTACT_TOP_OFF + RISER_CONTACT // 2,
            )
        )
        ctop = head_y0 - RISER_CONTACT_TOP_OFF
        cell.shapes(contact).insert(
            kdb.Box(
                terminal_x - RISER_CONTACT // 2,
                ctop - RISER_CONTACT,
                terminal_x + RISER_CONTACT // 2,
                ctop,
            )
        )

    source_x = gate_x0 - _GATE_EDGE_TO_SD_RISER
    drain_x = gate_x1 + _GATE_EDGE_TO_SD_RISER
    sd(source_x)
    sd(drain_x)

    return Mosfet(
        active=active,
        is_pmos=is_pmos,
        w=w,
        l=l,
        source_x=source_x,
        gate_x=gate_x,
        drain_x=drain_x,
        riser_y=riser_y,
    )


def draw_shared_nwell(
    cell: kdb.Cell, layers: dict[tuple[int, int], int], actives: list[kdb.Box]
) -> kdb.Box | None:
    """Draw ONE Nwell rectangle enclosing every PMOS active in `actives`
    (plus `NWELL_MARGIN`) instead of one per device.

    Correct as well as convenient: every PMOS in a row here sits on the same
    electrical well, so merging them into one island makes `nwell.space.1`
    inapplicable rather than merely satisfied. No-op (returns None) for an
    all-NMOS row.
    """
    if not actives:
        return None
    nwell = layers[L_NWELL]
    box = actives[0].enlarged(NWELL_MARGIN, NWELL_MARGIN)
    for a in actives[1:]:
        box = box + a.enlarged(NWELL_MARGIN, NWELL_MARGIN)
    cell.shapes(nwell).insert(box)
    return box

# --------------------------------------------------------------------------- #
# the channel router
# --------------------------------------------------------------------------- #

#: Minimum X gap between two different nets sharing one horizontal track.
#: Above `metal1.space.1` (230) with margin.
TRACK_SEP = 500

#: Extra X each trunk reaches past the outermost riser that lands on it, so a
#: riser contact is never at the trunk's own edge.
TRUNK_OVERHANG = RISER_W // 2 + 80


@dataclass
class _Drop:
    net: str
    x: int
    from_y: int
    riser_w: int


@dataclass
class Channel:
    """A left-edge-packed horizontal Metal1 routing channel fed by vertical
    Poly2 risers -- see this module's docstring for why the interconnect has
    to be exactly two layers.

    Usage: `drop()` every terminal, then `finish()`.

    **Track assignment is left-edge, not one-track-per-net.** Each net's
    horizontal span is only as wide as the risers that land on it, and two
    nets whose spans do not overlap share a track. That matters a lot here
    and not at all for a toy cell: in the CDAC decode bank, 63 of the 67
    nets are cell-local (a `gp_*` gate net spans two adjacent device
    columns), so one-track-per-net would spend ~40 um of channel height on
    nets that between them use a few percent of each track. Left-edge
    packing turns that into single-digit micrometres and is the difference
    between this block fitting its ratified area row and not.

    The packing is the classical left-edge algorithm restricted to the case
    this router actually has -- every connection is a vertical riser, so
    there are no vertical constraints between tracks and no dogleg is ever
    needed. It is therefore both optimal (it uses exactly the channel
    density, the maximum number of nets live at any X) and trivially
    correct.
    """

    cell: kdb.Cell
    layers: dict[tuple[int, int], int]
    #: Y of the top edge of the topmost track. Tracks stack downward.
    y_top: int
    _drops: list[_Drop] = field(default_factory=list, init=False)
    _forced: dict[str, list[int]] = field(default_factory=dict, init=False)
    _pins: set[str] = field(default_factory=set, init=False)
    _tracks: dict[str, int] = field(default_factory=dict, init=False)
    _boxes: dict[str, kdb.Box] = field(default_factory=dict, init=False)
    _finished: bool = field(default=False, init=False)

    # -- construction ----------------------------------------------------- #

    def drop(self, net: str, x: int, from_y: int, riser_w: int = RISER_W) -> None:
        """Record a Poly2 riser at `x`, running from `from_y` down to `net`'s
        track. Drawn by `finish()` (the track's Y is not known until every
        net's span is)."""
        if self._finished:
            raise RuntimeError("Channel.drop() after finish()")
        self._drops.append(_Drop(net=net, x=x, from_y=from_y, riser_w=riser_w))

    def extend(self, net: str, x: int) -> None:
        """Force `net`'s trunk to reach `x` even if no riser lands there --
        used to bring a trunk out to a cell's pin-escape column."""
        self._forced.setdefault(net, []).append(x)

    def mark_pin(self, net: str) -> None:
        """Emit a Metal1 (34/10) label on this net's trunk, i.e. make it a
        named pin in the extracted netlist."""
        self._pins.add(net)

    # -- geometry queries (valid after finish()) --------------------------- #

    def track_y(self, index: int) -> tuple[int, int]:
        y1 = self.y_top - index * TRUNK_PITCH
        return y1 - TRUNK_H, y1

    def trunk_box_y(self, net: str) -> tuple[int, int]:
        return self.track_y(self._tracks[net])

    @property
    def track_count(self) -> int:
        return (max(self._tracks.values()) + 1) if self._tracks else 0

    @property
    def y_bottom(self) -> int:
        return self.y_top - max(0, self.track_count - 1) * TRUNK_PITCH - TRUNK_H

    def height(self) -> int:
        return self.y_top - self.y_bottom

    def trunks(self) -> dict[str, kdb.Box]:
        return dict(self._boxes)

    # -- the pack-and-draw pass -------------------------------------------- #

    def _spans(self) -> dict[str, tuple[int, int]]:
        spans: dict[str, tuple[int, int]] = {}
        for drop in self._drops:
            lo, hi = drop.x - TRUNK_OVERHANG, drop.x + TRUNK_OVERHANG
            if drop.net in spans:
                a, b = spans[drop.net]
                spans[drop.net] = (min(a, lo), max(b, hi))
            else:
                spans[drop.net] = (lo, hi)
        for net, xs in self._forced.items():
            lo, hi = min(xs) - TRUNK_OVERHANG, max(xs) + TRUNK_OVERHANG
            if net in spans:
                a, b = spans[net]
                spans[net] = (min(a, lo), max(b, hi))
            else:
                spans[net] = (lo, hi)
        return spans

    def extend_drawn(self, net: str, x: int) -> kdb.Box:
        """Grow an already-drawn trunk out to `x` in Metal1, for a top-level
        strap corridor.

        **Asserts no other net shares the track over the new span.** Tracks
        here are left-edge packed, so one track usually carries several
        nets; growing a trunk along its own track without checking is a
        direct short to whichever net sits next along it. That is not
        hypothetical -- it produced `cmpclk,ibias,topn` in the extracted
        block netlist the first time this strap was drawn.
        """
        if not self._finished:
            raise RuntimeError("Channel.extend_drawn() before finish()")
        box = self._boxes[net]
        track = self._tracks[net]
        # Pad past `x` so a stitch corridor centred on `x` lands fully inside
        # the grown trunk rather than on its edge.
        pad = RISER_W // 2 + 100
        target = x - pad if x < box.left else x + pad
        lo, hi = min(target, box.left), max(target, box.right)
        for other, other_track in self._tracks.items():
            if other == net or other_track != track:
                continue
            ob = self._boxes[other]
            if ob.right >= lo - TRACK_SEP and ob.left <= hi + TRACK_SEP:
                raise RuntimeError(
                    f"cannot extend trunk {net!r} to x={x}: net {other!r} "
                    f"shares its track at {ob.left}..{ob.right}"
                )
        grown = kdb.Box(lo, box.bottom, hi, box.top)
        self.cell.shapes(self.layers[L_METAL1]).insert(grown)
        self._boxes[net] = grown
        return grown

    def finish(self) -> dict[str, kdb.Box]:
        """Pack every net onto a track, then draw the risers, their contacts,
        the trunks and the pin labels. Returns the trunk boxes by net."""
        if self._finished:
            raise RuntimeError("Channel.finish() called twice")
        self._finished = True

        spans = self._spans()
        # Left-edge: sweep nets by left edge, put each on the first track
        # whose current right edge clears it.
        track_right: list[int] = []
        for net, (lo, hi) in sorted(spans.items(), key=lambda kv: (kv[1][0], kv[0])):
            for index, right in enumerate(track_right):
                if lo - right >= TRACK_SEP:
                    self._tracks[net] = index
                    track_right[index] = hi
                    break
            else:
                self._tracks[net] = len(track_right)
                track_right.append(hi)

        poly2 = self.layers[L_POLY2]
        contact = self.layers[L_CONTACT]
        metal1 = self.layers[L_METAL1]
        label_layer = self.layers[L_METAL1_LABEL]

        for drop in self._drops:
            ty0, _ty1 = self.trunk_box_y(drop.net)
            riser_bottom = ty0 + (TRUNK_H - RISER_CONTACT) // 2 - 100
            self.cell.shapes(poly2).insert(
                kdb.Box(
                    drop.x - drop.riser_w // 2,
                    riser_bottom,
                    drop.x + drop.riser_w // 2,
                    drop.from_y,
                )
            )
            cy0 = ty0 + (TRUNK_H - RISER_CONTACT) // 2
            self.cell.shapes(contact).insert(
                kdb.Box(
                    drop.x - RISER_CONTACT // 2,
                    cy0,
                    drop.x + RISER_CONTACT // 2,
                    cy0 + RISER_CONTACT,
                )
            )

        for net, (lo, hi) in spans.items():
            ty0, ty1 = self.trunk_box_y(net)
            box = kdb.Box(lo, ty0, hi, ty1)
            self.cell.shapes(metal1).insert(box)
            self._boxes[net] = box
            if net in self._pins:
                self.cell.shapes(label_layer).insert(
                    kdb.Text(net, kdb.Trans(box.center()))
                )
        return dict(self._boxes)


# --------------------------------------------------------------------------- #
# guard rings, capacitors, labels
# --------------------------------------------------------------------------- #


def stitch(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    x: int,
    trunks: list[kdb.Box],
    riser_w: int = RISER_W,
) -> None:
    """Tie two or more separately-placed blocks' trunks for the SAME net
    together with one vertical Poly2 stitch at `x`, contacting each of them.

    The same Metal1-trunk / Poly2-riser discipline the in-block router uses,
    lifted to the top level -- and for the same reason: the extraction deck
    exposes one metal level, so a top-level strap has to cross every trunk
    between its endpoints on a layer that carries no connectivity across
    those crossings.

    Asserts three things rather than reasoning about them, because each has
    already been a real defect in this bring-up:

    1. `x` lies inside every trunk's own X range -- so the strap contacts
       drawn Metal1, not empty substrate (a contact in the air is silent:
       DRC-clean, and simply leaves the nets unconnected -- which is how two
       `vdd` pins first showed up in the extracted netlist);
    2. the corridor crosses no `Comp` -- a Poly2 strap over diffusion is a
       parasitic MOSFET;
    3. the corridor crosses no existing `Poly2` -- it would short this net to
       whatever riser already occupies that column.
    """
    if len(trunks) < 2:
        raise ValueError("stitch needs at least two trunks")
    for box in trunks:
        if not (box.left + riser_w // 2 <= x <= box.right - riser_w // 2):
            raise RuntimeError(
                f"stitch x={x} is outside trunk {box.left}..{box.right}; "
                "extend the trunk into the corridor first "
                "(Channel.extend_drawn / the placer's `escape` argument)"
            )

    y_lo = min(b.bottom for b in trunks)
    y_hi = max(b.top for b in trunks)
    corridor = kdb.Box(x - riser_w // 2, y_lo - 100, x + riser_w // 2, y_hi + 100)
    corridor_region = kdb.Region(corridor)
    for layer, name in ((L_COMP, "Comp"), (L_POLY2, "Poly2")):
        drawn = kdb.Region(cell.begin_shapes_rec(layers[layer]))
        if not (drawn & corridor_region).is_empty():
            raise RuntimeError(
                f"stitch corridor at x={x} crosses existing {name} -- a Poly2 "
                "strap there would create a parasitic device or a short"
            )

    cell.shapes(layers[L_POLY2]).insert(corridor)
    for box in trunks:
        cy = box.center().y
        cell.shapes(layers[L_CONTACT]).insert(
            kdb.Box(
                x - RISER_CONTACT // 2, cy - RISER_CONTACT // 2,
                x + RISER_CONTACT // 2, cy + RISER_CONTACT // 2,
            )
        )


def assert_no_bar_shorts(bars: list[tuple[str, kdb.Box]]) -> None:
    """Fail if two Metal1 extension bars belonging to DIFFERENT nets touch.

    Top-level straps run at whatever Y their own block's channel packer gave
    them, so two blocks placed at the same Y can hand two different nets the
    same track. Cheap to check, and the failure it prevents (a silent short
    between two top-level nets) is expensive to find any other way.
    """
    for i, (net_a, box_a) in enumerate(bars):
        for net_b, box_b in bars[i + 1:]:
            if net_a == net_b:
                continue
            if box_a.touches(box_b):
                raise RuntimeError(
                    f"top-level strap for {net_a!r} touches the strap for "
                    f"{net_b!r} at {box_a & box_b} -- shift one block's Y"
                )


def draw_guard_ring(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    box: kdb.Box,
    width: int = 1200,
    label_net: str | None = None,
) -> kdb.Box:
    """A contacted Comp/Contact/Metal1 substrate-tie ring around `box`.

    Drawn as a real, contacted diffusion ring on the same `Comp` layer this
    PDK uses for transistor active -- gf180mcu's curated deck has no
    distinct tap layer (`ExtractionDeck.tap is None`), which is exactly why
    a well tie cannot be *extracted* here even though it can be *drawn* (see
    `../README.md`). The ring is drawn outside `box`, so `box` must already
    include whatever clearance the enclosed geometry needs.

    Returns the ring's outer box.
    """
    comp = layers[L_COMP]
    contact = layers[L_CONTACT]
    metal1 = layers[L_METAL1]

    outer = box.enlarged(width, width)
    inner = box
    # Four Comp bars (a ring drawn as rectangles keeps every edge
    # axis-aligned and every corner a simple overlap).
    bars = [
        kdb.Box(outer.left, outer.bottom, outer.right, inner.bottom),  # bottom
        kdb.Box(outer.left, inner.top, outer.right, outer.top),  # top
        kdb.Box(outer.left, inner.bottom, inner.left, inner.top),  # left
        kdb.Box(inner.right, inner.bottom, outer.right, inner.top),  # right
    ]
    for bar in bars:
        cell.shapes(comp).insert(bar)
        c = bar.enlarged(-(width // 3), -(width // 3))
        if c.width() > 0 and c.height() > 0:
            cell.shapes(contact).insert(c)
        cell.shapes(metal1).insert(bar.enlarged(-(width // 4), -(width // 4)))
    if label_net is not None:
        strap = bars[0].enlarged(-(width // 4), -(width // 4))
        cell.shapes(layers[L_METAL1_LABEL]).insert(
            kdb.Text(label_net, kdb.Trans(strap.center()))
        )
    return outer


@dataclass(frozen=True)
class MimCap:
    """One drawn `cap_mim_2f0fF` MiM capacitor and the boxes a caller needs
    in order to wire it."""

    #: FuseTop. This IS the device: its width x length are the PDK subckt's
    #: own `c_width`/`c_length`, and the extraction deck computes
    #: `C = area_cap * area(plate)` from it.
    plate: kdb.Box
    #: Metal4 bottom plate, `MIM_M4_ENCLOSURE` outside `plate` on every side.
    bottom: kdb.Box
    #: Via4 on the plate centre, present only when the cap was drawn as a
    #: recognised device (`device=True`).
    top_via: kdb.Box | None
    #: Metal5 landing pad over `top_via` -- the top terminal's routing metal.
    top_pad: kdb.Box | None

    @property
    def footprint(self) -> kdb.Box:
        """The stack's own drawn extent (== `bottom`). What tiling pitches
        against, via `mim_pitch`."""
        return self.bottom


def mim_footprint(cw: int, cl: int) -> tuple[int, int]:
    """Drawn `(width, height)` of a `cw` x `cl`-plate MiM stack."""
    return cw + 2 * MIM_M4_ENCLOSURE, cl + 2 * MIM_M4_ENCLOSURE


def mim_pitch(cw: int, cl: int) -> tuple[int, int]:
    """Minimum legal tiling `(x_pitch, y_pitch)` for a `cw` x `cl`-plate MiM
    unit: the drawn footprint plus `mim.space.1`'s bottom-plate spacing.

    This is the whole area cost of a MiM array and it is set by the DRM, not
    by this layout: a 2.7136 um plate cannot be tiled tighter than
    2.7136 + 2 x 0.6 + 1.2 = 5.1136 um without violating `MIMTM.3` or
    `MIMTM.1`.
    """
    w, h = mim_footprint(cw, cl)
    return w + MIM_M4_SPACE, h + MIM_M4_SPACE


def draw_mim_cap(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    x0: int,
    y0: int,
    cw: int,
    cl: int,
    *,
    device: bool = False,
) -> MimCap:
    """Draw one `cap_mim_2f0fF` MiM capacitor whose PLATE is `cw` x `cl`,
    with the stack's drawn footprint starting at `(x0, y0)`.

    `cw`/`cl` are the PDK subcircuit's own `c_width`/`c_length` -- the
    FuseTop top plate -- NOT the drawn footprint. That distinction is the
    whole point of this function's current shape, and getting it backwards
    is exactly the defect this replaced (issue #70): the previous version
    took `cw`/`cl` as the *Metal4* size and derived FuseTop by insetting it,
    which (a) drew a plate 0.6 um smaller than the ratified device on every
    side and (b) could not satisfy `mim.enclosing.fusetop.1` at all, because
    its inset was capped at 0.3 um against a 0.6 um rule.

    The stack, outward from the plate:

    * **FuseTop** = the plate, `cw` x `cl`, at `(x0 + MIM_M4_ENCLOSURE,
      y0 + MIM_M4_ENCLOSURE)`;
    * **Metal4** = the bottom plate, `MIM_M4_ENCLOSURE` (`MIMTM.3`, 0.6 um)
      outside the plate on every side -- a *rule*, so the footprint is
      derived rather than chosen;
    * with `device=True`, **CAP_MK** (117/5) and **MIM_L_MK** (117/10) over
      the plate, plus a **Via4** on the plate centre and a **Metal5** landing
      pad over it.

    `device=True` is what makes `klt extract` recognise the stack as a
    `cap_mim_2f0_m4m5_noshield` device rather than inert geometry: the
    gf180mcu extraction deck derives its top plate as
    `fusetop.interacting(cap_mk).interacting(mim_l_mk)`, exactly as the PDK's
    own KLayout LVS deck does. It is deliberately opt-in: a marked cap whose
    two plates are not wired to anything extracts as a real device on two
    floating nets, which is an LVS mismatch, not a result. Draw the markers
    only where the caller also draws the connectivity (`../README.md`).

    Without `device=True` no Via4 is drawn either -- Via4 is an ordinary
    `metals[3] <-> metals[4]` via to the extraction deck unless it belongs to
    a *recognised* capacitor (upstream klayout-tools#368 excludes exactly
    that overlap), so a Via4 on an unmarked stack would short the bottom
    plate to the top-plate metal.
    """
    if cw <= 0 or cl <= 0:
        raise ValueError(f"MiM plate must be positive, got {cw} x {cl}")
    plate = kdb.Box(
        x0 + MIM_M4_ENCLOSURE,
        y0 + MIM_M4_ENCLOSURE,
        x0 + MIM_M4_ENCLOSURE + cw,
        y0 + MIM_M4_ENCLOSURE + cl,
    )
    bottom = plate.enlarged(MIM_M4_ENCLOSURE, MIM_M4_ENCLOSURE)
    cell.shapes(layers[L_METAL4]).insert(bottom)
    cell.shapes(layers[L_FUSETOP]).insert(plate)
    if not device:
        return MimCap(plate=plate, bottom=bottom, top_via=None, top_pad=None)

    cell.shapes(layers[L_CAP_MK]).insert(plate)
    cell.shapes(layers[L_MIM_L_MK]).insert(plate)
    via_half = VIA_SIDE // 2
    if min(cw, cl) < VIA_SIDE + 2 * VIA_METAL_MARGIN:
        raise ValueError(
            f"MiM plate {cw} x {cl} too small to land a top-plate Via4"
        )
    centre = plate.center()
    top_via = kdb.Box(
        centre.x - via_half, centre.y - via_half,
        centre.x + via_half, centre.y + via_half,
    )
    # `mim.enclosing.via4.1` (MIMTM.2, 0.4 um) is measured against the
    # virtual bottom plate, which for this construction is the drawn Metal4.
    assert top_via.left - bottom.left >= MIM_VIA4_ENCLOSURE, (
        "top-plate Via4 violates mim.enclosing.via4.1"
    )
    cell.shapes(layers[L_VIA4]).insert(top_via)
    top_pad = top_via.enlarged(VIA_METAL_MARGIN, VIA_METAL_MARGIN)
    cell.shapes(layers[L_METAL5]).insert(top_pad)
    return MimCap(plate=plate, bottom=bottom, top_via=top_via, top_pad=top_pad)


def draw_mim_bottom_riser(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    cap: MimCap,
    trunk: kdb.Box,
) -> None:
    """Wire `cap`'s Metal4 bottom plate down to the Metal1 `trunk` it belongs
    to, on Metal3/Metal2 with a Via3/Via2/Via1 stack.

    The riser runs on **Metal2** for its whole vertical span, because that
    span crosses the device row: Metal2 carries no connectivity to Metal1
    except through a Via1, so the crossing is free, whereas a Metal1 riser
    would short into every stub it passed. It lands on `trunk` with a single
    Via1 -- the same "exactly one contact per terminal" discipline the Poly2
    risers in `Channel` use.

    The Via3 that leaves the bottom plate is placed in the Metal4 ring
    *outside* the FuseTop plate, so nothing is drawn under the dielectric.
    """
    x = cap.bottom.center().x
    if not (trunk.left + VIA_SIDE <= x <= trunk.right - VIA_SIDE):
        raise ValueError(
            f"bottom-plate riser at x={x} does not land inside its trunk "
            f"({trunk.left}..{trunk.right}) -- the cap is not over its own net"
        )
    # Via3 centred in the Metal4 ring below the plate.
    y_top = (cap.bottom.bottom + cap.plate.bottom) // 2
    pad = VIA_SIDE // 2 + VIA_METAL_MARGIN
    for via_layer, y in ((L_VIA3, y_top), (L_VIA2, y_top)):
        cell.shapes(layers[via_layer]).insert(
            kdb.Box(x - VIA_SIDE // 2, y - VIA_SIDE // 2,
                    x + VIA_SIDE // 2, y + VIA_SIDE // 2)
        )
    cell.shapes(layers[L_METAL3]).insert(
        kdb.Box(x - pad, y_top - pad, x + pad, y_top + pad)
    )
    y_bot = trunk.center().y
    cell.shapes(layers[L_METAL2]).insert(
        kdb.Box(x - pad, y_bot - pad, x + pad, y_top + pad)
    )
    cell.shapes(layers[L_VIA1]).insert(
        kdb.Box(x - VIA_SIDE // 2, y_bot - VIA_SIDE // 2,
                x + VIA_SIDE // 2, y_bot + VIA_SIDE // 2)
    )


def label(
    cell: kdb.Cell, layers: dict[tuple[int, int], int], box: kdb.Box, name: str
) -> None:
    """A Metal1.label (34/10) text at `box`'s centre naming the net that box
    belongs to -- what `ExtractionDeck.metal_labels` reads (same convention
    as `layout/lvs/cells/gen_lvs_unit.py`)."""
    cell.shapes(layers[L_METAL1_LABEL]).insert(kdb.Text(name, kdb.Trans(box.center())))


def label_metal5(
    cell: kdb.Cell, layers: dict[tuple[int, int], int], box: kdb.Box, name: str
) -> None:
    """The Metal5 (81/10) sibling of :func:`label`. Every metal level in the
    pinned extraction deck has its own datatype-10 label purpose; the MiM
    top plate's terminal is reached on Metal5, so that is where its pin name
    has to be drawn."""
    cell.shapes(layers[L_METAL5_LABEL]).insert(kdb.Text(name, kdb.Trans(box.center())))


def area_um2(box: kdb.Box) -> float:
    """`box`'s area in um^2, from a dbu-unit box at this module's DBU_UM."""
    return box.width() * DBU_UM * box.height() * DBU_UM
