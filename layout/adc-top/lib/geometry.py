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
`klt extract`'s gf180mcu `ExtractionDeck` declares exactly ONE metal level
(`metals=((34, 0),)`) and no via layers, so the only interconnect the LVS
flow can see is **Metal1 plus Poly2** (poly is a registered, connected
region, joined to Metal1 only through Contact -- read directly from
`klayout_tools/extract.py`'s `_extract_netlist`, not assumed). Every net in
this block therefore has to close in a *two-layer planar* graph. That is
the single biggest shape driver in this directory, and it is a tool
limitation, not a design choice (filed generically upstream -- see
`../README.md`'s friction table).

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

# --- MiM capacitor stack (gf180mcu) --------------------------------------
# NOT read by the `klt drc` gf180mcu deck and NOT read by `klt extract`'s
# `ExtractionDeck` at all (see ../README.md "What is and is not verified"
# and klayout-tools#188/#189). Layer numbers per layout/README.md's own
# coverage table.
L_METAL4 = (46, 0)  # MiM bottom plate
L_FUSETOP = (75, 0)  # MiM capacitor mark
L_METAL5 = (81, 0)  # MiM top plate

LAYER_NAMES = {
    L_NWELL: "Nwell",
    L_COMP: "Comp",
    L_POLY2: "Poly2",
    L_CONTACT: "Contact",
    L_METAL1: "Metal1",
    L_METAL1_LABEL: "Metal1.label",
    L_METAL4: "Metal4",
    L_FUSETOP: "FuseTop",
    L_METAL5: "Metal5",
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
COLUMN_GAP = 900  # gap between adjacent device columns' active islands
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


def draw_mim_cap(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    x0: int,
    y0: int,
    cw: int,
    cl: int,
) -> tuple[kdb.Box, kdb.Box]:
    """Draw one `cap_mim_2f0fF` footprint, `cw` x `cl` at its bottom plate.

    **Drawn for placement/area bookkeeping and matching discipline only --
    it is neither DRC- nor LVS-verified, and cannot be with this toolchain**
    (the `klt drc` gf180mcu deck has no rule on any of these three layers,
    klayout-tools#188/#189; the `klt extract` deck reads none of them and
    has no capacitor device class at all -- see `../README.md`). Bottom
    plate on Metal4, capacitor mark on FuseTop, top plate on Metal5, inset
    in the PDK's usual bottom-plate-largest MIM construction. The Via4 ties
    and the Metal1->Metal4 stack are not drawn: no tool in this pinned
    toolchain could check them, and drawing unverifiable detail would
    misrepresent what this layout has actually proven.

    Returns `(bottom_plate_box, top_plate_box)`.
    """
    bottom = kdb.Box(x0, y0, x0 + cw, y0 + cl)
    cell.shapes(layers[L_METAL4]).insert(bottom)
    inset1 = max(1, min(300, cw // 8, cl // 8))
    cell.shapes(layers[L_FUSETOP]).insert(bottom.enlarged(-inset1, -inset1))
    inset2 = inset1 + max(1, min(300, cw // 8, cl // 8))
    top = bottom.enlarged(-inset2, -inset2)
    cell.shapes(layers[L_METAL5]).insert(top)
    return bottom, top


def label(
    cell: kdb.Cell, layers: dict[tuple[int, int], int], box: kdb.Box, name: str
) -> None:
    """A Metal1.label (34/10) text at `box`'s centre naming the net that box
    belongs to -- what `ExtractionDeck.metal_labels` reads (same convention
    as `layout/lvs/cells/gen_lvs_unit.py`)."""
    cell.shapes(layers[L_METAL1_LABEL]).insert(kdb.Text(name, kdb.Trans(box.center())))


def bbox_of(cell: kdb.Cell) -> kdb.Box:
    """The cell's bounding box over every layer (dbu units)."""
    return cell.bbox()


def area_um2(box: kdb.Box) -> float:
    """`box`'s area in um^2, from a dbu-unit box at this module's DBU_UM."""
    return box.width() * DBU_UM * box.height() * DBU_UM
