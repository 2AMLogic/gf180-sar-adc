#!/usr/bin/env python3
"""Place a flattened device list (`lib/netlist.py`) into a DRC-clean,
LVS-verifiable gf180mcu row + channel, using `lib/geometry.py`'s primitives.

One function does the work: :func:`draw_devices`. It is deliberately dumb
and uniform -- every device is drawn the same way, every terminal reaches
its net's trunk the same way -- because the thing this directory has to be
able to defend is that the drawn polygons *provably* realise
`design/adc-top/adc_top.spice`, not that they are compact. Where a
placement choice IS load-bearing for the design (common-centroid ordering,
dummy symmetry, guard-ring/supply separation), the caller expresses it by
choosing the device ORDER and the row/channel partitioning it hands to this
function -- see `gen_adc_top.py` and `../README.md` §"Matching plan
implementation".

ROW STRUCTURE
-------------
    +-------------------------------------------------+
    |  NMOS columns            |  PMOS columns (Nwell)|   device row
    |  gate heads point DOWN   |                      |
    +-------------------------------------------------+
    |  riser zone: Metal1 drop stubs -> Poly2 risers   |
    +-------------------------------------------------+
    |  Metal1 trunk (net 0)                            |
    |  Metal1 trunk (net 1)                            |   routing channel
    |  ...                                             |
    +-------------------------------------------------+

NMOS columns come first so that ONE Nwell island covers every PMOS in the
row (`nwell.space.1` then never applies inside a block at all, rather than
being satisfied per device), and so an NMOS active never sits under Nwell --
which would silently turn it into a PMOS, since `klt extract` splits the
two with `active - nwell` / `active & nwell`.
"""

from __future__ import annotations

from dataclasses import dataclass

import klayout.db as kdb

from . import geometry as geo
from .netlist import SUBSTRATE_NET, Device


@dataclass
class PlacedBlock:
    """What :func:`draw_devices` drew."""

    channel: geo.Channel
    trunks: dict[str, kdb.Box]
    devices: list[tuple[Device, geo.Mosfet]]
    nwell: list[kdb.Box]
    #: Layout net each MOSFET's body terminal actually lands on -- the LVS
    #: reference has to say the same thing (see `lib/netlist.write_reference`).
    body_net: dict[str, str]
    row_x0: int
    row_x1: int
    row_y0: int


#: Gap between the last NMOS active and the first PMOS active (and between
#: two placement groups), on top of the ordinary column gap.
#:
#: Sized from the rule it exists for: the Nwell edge reaches `NWELL_MARGIN`
#: past the PMOS active it covers, so an NMOS active on the other side of
#: the boundary clears that edge by `COLUMN_GAP + NWELL_KEEPOUT -
#: NWELL_MARGIN` = 800 nm, i.e. `nwell.space.1`'s own 600 nm threshold plus
#: 200 nm. The DRM's "Nwell to unrelated COMP" rule is not in the pinned
#: deck (see `geometry._NWELL_SPACE_MIN`), so that clearance is a
#: by-construction argument, not a checked result -- which is exactly why
#: :func:`draw_devices` asserts the drawn island-to-island spacing below
#: instead of trusting this constant to have been chosen well.
#:
#: Was 1600 nm, i.e. sized by nothing in particular; a decode bank crosses
#: this boundary 17 times per side, so the surplus was real bank width (see
#: `geometry.COLUMN_GAP` and issue #67).
NWELL_KEEPOUT = 900


def _assert_nwell_clearances(
    nwell_boxes: list[kdb.Box], nfet_actives: list[kdb.Box]
) -> None:
    """Fail if `NWELL_KEEPOUT` was not, in fact, big enough for this row.

    Two things have to hold and only one of them is checked by the pinned
    deck, which is why both are asserted here rather than argued for in a
    comment:

    1. **Island to island** -- two placement groups' Nwell islands must clear
       `nwell.space.1`. They normally do so by an enormous margin (a group's
       NMOS columns sit between them), but a row whose groups are all-PMOS
       has no such spacer and would land the two islands `COLUMN_GAP +
       NWELL_KEEPOUT - 2 * NWELL_MARGIN` apart. `klt drc` catches that one.
    2. **Island to a foreign NMOS active** -- the DRM's "Nwell to unrelated
       COMP" rule, which the pinned deck does NOT have (see
       `geometry._NWELL_SPACE_MIN`). Nothing downstream would catch a
       violation, so this is the only place it can be caught at all.

    Both are checked against `nwell.space.1`'s 600 nm. Raising rather than
    warning is deliberate: a row that cannot honour the keepout should not
    reach a GDS.
    """
    limit = geo._NWELL_SPACE_MIN
    ordered = sorted(nwell_boxes, key=lambda b: b.left)
    for a, b in zip(ordered, ordered[1:]):
        if b.left - a.right < limit:
            raise RuntimeError(
                f"Nwell islands at {a.right} and {b.left} are "
                f"{b.left - a.right} nm apart, under nwell.space.1 ({limit}) "
                "-- raise NWELL_KEEPOUT or COLUMN_GAP"
            )
    for well in nwell_boxes:
        for active in nfet_actives:
            gap = max(well.left - active.right, active.left - well.right)
            if gap < limit:
                raise RuntimeError(
                    f"Nwell island {well.left}..{well.right} is {gap} nm from "
                    f"an NMOS active at {active.left}..{active.right}, under "
                    f"the DRM's Nwell-to-unrelated-COMP spacing ({limit}) -- "
                    "raise NWELL_KEEPOUT or COLUMN_GAP"
                )


def draw_devices(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    groups: list[tuple[str, list[Device]]],
    pins: list[str],
    *,
    x0: int = 0,
    row_y0: int = 0,
    escape: list[str] | None = None,
    escape_left: list[str] | None = None,
    escape_margin: int = 6000,
    escape_left_margin: int | None = None,
    auto_finish: bool = True,
) -> PlacedBlock:
    """Draw every MOSFET in `groups` in one row and route every terminal into
    a left-edge-packed channel below the row.

    A **group** is a set of devices that shares one Nwell island and is
    placed contiguously: its NMOS columns first, then its PMOS columns. The
    group's name is the net every one of its PMOS bodies lands on in the
    extracted netlist (the curated gf180mcu deck never connects `nwell` to
    `contact`, so a well can only ever be an unnamed island net -- see
    `lib/netlist.write_reference`).

    Grouping is not cosmetic. Placing devices group-by-group is what keeps a
    net LOCAL in X: in the CDAC decode bank, one `adc_cdac_cell`'s seven
    internal nets then span twelve adjacent columns instead of reaching
    across the whole bank, which is what lets `geometry.Channel`'s left-edge
    packer put nine cells' worth of internal nets on the same seven tracks.
    Placing all NMOS first and all PMOS second (the obvious alternative,
    with one well island for the whole row) makes every cell-internal net
    span the full bank and costs ~35 um of channel height on this block --
    measured, not estimated.

    Non-MOS devices (capacitors, resistors) are skipped: neither is
    extractable by `klt extract`'s gf180mcu deck. Capacitor geometry is
    drawn separately by the caller (`geometry.draw_mim_cap`); resistor
    geometry likewise (`draw_poly_resistor`).

    `pins` are the nets that get a Metal1 (34/10) label, i.e. the ones that
    become named pins in the extracted netlist.

    `escape`/`escape_left` name the nets whose trunk must reach
    `escape_margin` past the last / before the first device column, into the
    Comp-free corridor a caller uses to stitch the same net between two
    separately-placed blocks (`geometry.stitch`). It has to be declared
    here rather than added afterwards, because a trunk's X extent is decided
    during track packing -- an extension requested after `Channel.finish()`
    would silently draw nothing, which is exactly the defect `klt extract`
    caught on this block's first assembled run (two `vdd` pins, two `vss`
    pins, ... -- one unconnected net per rail per bank).
    """
    placed: list[tuple[Device, geo.Mosfet]] = []
    body_net: dict[str, str] = {}
    nwell_boxes: list[kdb.Box] = []
    x = x0

    for group_index, (nwell_net, members) in enumerate(groups):
        mos = [d for d in members if d.is_mos]
        nfets = [d for d in mos if d.kind == "nfet"]
        pfets = [d for d in mos if d.kind == "pfet"]
        if group_index:
            x += NWELL_KEEPOUT
        pfet_actives: list[kdb.Box] = []
        for index, dev in enumerate(nfets + pfets):
            if index == len(nfets) and nfets and pfets:
                x += NWELL_KEEPOUT
            m = geo.draw_mosfet(
                cell, layers, x, row_y0,
                w=dev.w_nm, l=dev.l_nm, is_pmos=dev.kind == "pfet",
            )
            if dev.kind == "pfet":
                pfet_actives.append(m.active)
            placed.append((dev, m))
            body_net[dev.path] = (
                SUBSTRATE_NET if dev.kind == "nfet" else nwell_net
            )
            x += geo.column_pitch(dev.l_nm)
        box = geo.draw_shared_nwell(cell, layers, pfet_actives)
        if box is not None:
            nwell_boxes.append(box)
    row_x1 = x - geo.COLUMN_GAP
    _assert_nwell_clearances(
        nwell_boxes, [m.active for d, m in placed if d.kind == "nfet"]
    )

    riser_y = min(m.riser_y for _, m in placed) if placed else row_y0
    channel = geo.Channel(
        cell=cell, layers=layers, y_top=riser_y - geo.CHANNEL_TOP_GAP
    )

    for dev, m in placed:
        d_net, g_net, s_net, _b = dev.nets
        channel.drop(s_net, m.source_x, m.riser_y)
        channel.drop(g_net, m.gate_x, m.riser_y)
        channel.drop(d_net, m.drain_x, m.riser_y)

    for net in escape or ():
        channel.extend(net, row_x1 + escape_margin)
    for net in escape_left or ():
        channel.extend(net, x0 - (escape_left_margin or escape_margin))

    block = PlacedBlock(
        channel=channel,
        trunks={},
        devices=placed,
        nwell=nwell_boxes,
        body_net=body_net,
        row_x0=x0,
        row_x1=row_x1,
        row_y0=row_y0,
    )
    if auto_finish:
        finish_block(block, pins)
    return block


def finish_block(block: PlacedBlock, pins: list[str]) -> dict[str, kdb.Box]:
    """Pack and draw `block`'s channel. Split out of :func:`draw_devices` so
    a caller can add more drops first -- the comparator's load-resistor
    columns are placed after the transistor row, and a drop after
    `Channel.finish()` is a hard error rather than a silent no-op."""
    for net in pins:
        block.channel.mark_pin(net)
    block.trunks = block.channel.finish()
    return block.trunks


@dataclass(frozen=True)
class ResistorColumn:
    """One drawn poly-resistor segment and the two riser X positions it
    presents to the channel router, exactly like :class:`geometry.Mosfet`."""

    a_x: int          # riser for the LOW-Y terminal
    b_x: int          # riser for the HIGH-Y terminal
    riser_y: int
    body: kdb.Box
    width: int        # total X footprint of the column


#: Column geometry for `draw_poly_resistor`. The high-Y terminal has to
#: reach the riser level past its own body, so its Metal1 escapes sideways
#: to its own riser slot -- Metal1 crossing Poly2 carries no connectivity in
#: the gf180mcu extraction deck (only Contact joins them), which is what
#: makes that legal.
_RES_HEAD = 700
_RES_PAD = 400
_RES_B_OFFSET = 2000


def draw_poly_resistor(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    x0: int,
    row_y0: int,
    r_width: int,
    r_length: int,
) -> ResistorColumn:
    """Draw one unsalicided p+ poly resistor segment as a column in a device
    row, at the caller's `r_width` x `r_length`.

    **What this does and does not verify.** The stripe sits on a layer the
    `klt drc` gf180mcu deck DOES check (`poly2.width.1`/`poly2.space.1`/
    `poly2.enclosing.contact.1`), so its geometry is genuinely rule-checked.
    The body is also covered by `SAB` (49/0) + `RES_MK` (110/5) + `Resistor`
    (62/0), which is what makes `klt extract`'s gf180mcu deck recognise it as
    a real `ppolyf_u_1k` device (1000 ohm/sq, klayout-tools#222/#299) instead
    of an ordinary Poly2 *conductor* -- issue #118. The three marker layers
    are drawn exactly the size of `body`: this curated `klt drc` deck carries
    no width/space/enclosure rule keyed on any of them (checked directly
    against `klayout_tools.decks.gf180mcu.EXTRACTION_DECK`'s `DrcRule` list
    at this repo's pinned commit), so exact-body coverage is both DRC-safe
    and exactly what the extraction derivation
    (`poly2.and(sab).and(res_mk).and(resistor)`) needs to recognise the whole
    body and nothing but the body.

    **What is still NOT modelled.** The schematic's `ppolyf_u_2k` (2000
    ohm/sq) assumption is not reachable: the PDK's `_1k`/`_2k`/`_3k`
    high-sheet-rho flavours share this exact same drawn geometry (selected
    only by a build-time deck option this curated deck does not implement),
    so drawing more or different marker layers cannot select `_2k` --
    tracked upstream as `2AMLogic/klayout-tools#595`, open. The design
    (`design/comparator/comparator.spice`) is sized for `ppolyf_u_1k`
    (`r_length` chosen so `r_length / r_width * 1000 ohm/sq` hits the
    150 kohm target), not for the schematic's original `_2k` assumption --
    see `../README.md` "Resistors".
    """
    poly2 = layers[geo.L_POLY2]
    contact = layers[geo.L_CONTACT]
    metal1 = layers[geo.L_METAL1]
    sab = layers[geo.L_SAB]
    res_mk = layers[geo.L_RES_MK]
    resistor_mk = layers[geo.L_RESISTOR]

    # `klt extract`'s `DeviceExtractorResistorWithBulk` derives the device's
    # effective L/W from the marked region's actual polygon geometry (area
    # and the width of the edges where it abuts an UNMARKED, unmarked-poly
    # "port" conductor), not from `r_width` directly -- so a terminal lead
    # narrower than the body (the old fixed `_RES_PAD`, 400 nm) becomes the
    # effective port width and silently changes the extracted resistance
    # (confirmed empirically: at `r_width=1000` this deck reported
    # `w_um=0.4`, i.e. exactly the old `_RES_PAD`, 2.51x the intended
    # resistance). Both terminal leads immediately touching the body are
    # therefore drawn at (at least) `r_width` -- `term_w` below -- so the
    # port the extractor measures is the same width as the body, and `R`
    # comes out at the drawn `r_length / r_width * sheet_rho` the caller
    # asked for. `_RES_PAD` alone is still used for the FAR pieces (the
    # riser stub at `b_x`) that sit past the Metal1 hop out of the marked
    # region, where it no longer sets the device's electrical L/W.
    term_w = max(r_width, _RES_PAD)

    riser_y = row_y0 - geo.GATE_HEAD_H - geo.DROP_H
    # Both the low-Y terminal box and the high-Y pad are `term_w` wide,
    # centred on `a_x`/`b_x` -- `a_x` is offset from `x0` by exactly
    # `term_w // 2` so the LEFT edge of the low-Y terminal lands flush on
    # `x0` (the same invariant the fixed-`_RES_PAD` version kept, generalised
    # to a caller-chosen `r_width`; `ResistorColumn.width` below keeps the
    # matching invariant on the right edge, so neighbouring columns packed
    # by `x += column.width` never close in on the wider terminal leads a
    # large `r_width` now draws -- issue #118 found this the hard way: a
    # `term_w` widened from the old `_RES_PAD` without a matching `width`
    # update crowded two adjacent columns into a real `poly2.space.1` /
    # `metal1.space.1` violation).
    a_x = x0 + term_w // 2
    body_x0 = a_x - r_width // 2

    y_a1 = row_y0 + _RES_HEAD
    y_b0 = y_a1 + r_length
    body = kdb.Box(body_x0, y_a1, body_x0 + r_width, y_b0)
    cell.shapes(poly2).insert(body)
    cell.shapes(sab).insert(body)
    cell.shapes(res_mk).insert(body)
    cell.shapes(resistor_mk).insert(body)

    # Low-Y terminal: its poly landing pad simply continues down to the riser
    # level, so it needs no contact at the device end -- the same trick a
    # gate riser uses (see geometry.draw_mosfet).
    cell.shapes(poly2).insert(
        kdb.Box(a_x - term_w // 2, riser_y, a_x + term_w // 2, y_a1)
    )

    # High-Y terminal: poly pad, contact up to Metal1, a Metal1 run sideways
    # to its own riser slot, then down to the riser level and a contact into
    # a fresh poly riser there.
    b_x = a_x + _RES_B_OFFSET
    pad = kdb.Box(a_x - term_w // 2, y_b0, a_x + term_w // 2, y_b0 + _RES_HEAD)
    cell.shapes(poly2).insert(pad)
    c = pad.enlarged(-80, -180)  # clears contact.width.1 (220) at any term_w
    cell.shapes(contact).insert(c)
    cell.shapes(metal1).insert(
        kdb.Box(c.left - 60, c.bottom - 60, b_x + 190, c.top + 60)
    )
    cell.shapes(metal1).insert(kdb.Box(b_x - 190, riser_y, b_x + 190, c.top + 60))
    cell.shapes(poly2).insert(
        kdb.Box(b_x - _RES_PAD // 2, riser_y, b_x + _RES_PAD // 2, riser_y + 900)
    )
    cell.shapes(contact).insert(
        kdb.Box(b_x - 120, riser_y + 400, b_x + 120, riser_y + 640)
    )

    return ResistorColumn(
        a_x=a_x,
        b_x=b_x,
        riser_y=riser_y,
        body=body,
        # Mirrors `a_x`'s `term_w`-based left margin on the right edge: the
        # high-Y pad's rightmost edge is `b_x + term_w // 2`, so the next
        # column (placed at `x0 + width`) starts exactly `geo.COLUMN_GAP`
        # past it, whatever `r_width`/`term_w` the caller asked for.
        width=_RES_B_OFFSET + term_w + geo.COLUMN_GAP,
    )
