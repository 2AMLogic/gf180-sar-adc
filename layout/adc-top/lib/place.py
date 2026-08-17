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

    a_x: int          # riser for the FIRST leg's terminal
    b_x: int          # riser for the LAST leg's terminal
    riser_y: int
    body: kdb.Region  # the merged (folded) marked body, as drawn
    width: int        # total X footprint of the column
    height: int       # Y footprint of the body above `row_y0`
    legs: int         # number of parallel vertical legs the body folds into


#: Column geometry for `draw_poly_resistor`.
_RES_HEAD = 700
_RES_PAD = 400
#: Gap between two adjacent legs of a FOLDED body (issue #215). Sized from
#: the rule it exists for plus stated headroom, the same discipline
#: `geometry.COLUMN_GAP` and `NWELL_KEEPOUT` follow -- but with MORE
#: headroom than either, on purpose: `poly2.space.1` (240 nm) is the only
#: spacing the pinned deck checks between two legs of the same body, and it
#: is a general-interconnect rule, not the dedicated unsalicided-poly-
#: resistor spacing the real DRM carries and this curated deck does not
#: transcribe. 600 nm is therefore 2.5x the checked rule, so the drawn
#: clearance stays defensible against the rule that ISN'T checked here --
#: the same argument `NWELL_KEEPOUT` makes for the unmodelled
#: Nwell-to-unrelated-COMP spacing. Dialling this to 400 nm (the
#: `COLUMN_GAP`-style "threshold + ~120 nm" choice) would buy ~300 um^2 of
#: block area and spend the margin on an unchecked clearance; measured and
#: rejected, see `gen_comparator.RESISTOR_LEGS`.
_RES_FOLD_SPACE = 600


def resistor_column_width(r_width: int, legs: int = 2) -> int:
    """The X footprint :func:`draw_poly_resistor` will occupy, without
    drawing it.

    A caller that has to reserve routing space PAST the resistor columns has
    to know their span before the row is placed -- `draw_devices`' escape
    margin is consumed during track packing, i.e. strictly before
    `draw_poly_resistor` is ever called (see `Channel.extend_drawn`). This
    keeps that reservation derived from the same expression the drawn
    geometry uses instead of a hand-tuned constant beside it (issue #215).
    """
    return (
        (legs - 1) * (r_width + _RES_FOLD_SPACE)
        + max(r_width, _RES_PAD)
        + geo.COLUMN_GAP
    )


def draw_poly_resistor(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    x0: int,
    row_y0: int,
    r_width: int,
    r_length: int,
    legs: int = 2,
) -> ResistorColumn:
    """Draw one unsalicided p+ poly resistor as a column in a device row, at
    the caller's `r_width` x `r_length`, folded into `legs` parallel vertical
    legs joined alternately at the top and the bottom (a serpentine).

    **ONE connected body, whatever `legs` says** -- the fold is a shape
    change, not a series split. `klt extract` recognises the merged
    serpentine as a single `ppolyf_u_1k` device, so the device count against
    `design/comparator/comparator.spice` is unchanged and the split that
    issue #118 retired is NOT reintroduced. `legs` must be EVEN so both free
    ends land at the bottom of the column, at the row's own riser level,
    which is also what lets this routine drop the pre-fold high-Y terminal's
    Metal1 hop entirely.

    **Why the drawn area is asserted, not merely computed.** This deck's
    `DeviceExtractorResistorWithBulk` derives the device's resistance from
    the marked region's AREA divided by the port width, not from a
    centre-line length -- measured directly (issue #215): a two-leg fold of
    a nominal 150 um x 1 um body drawn with a 600 nm leg gap extracts as
    150600 ohm, i.e. exactly `sheet_rho * drawn_area / port_width`, the
    600 nm of extra corner metal included. The leg length below is therefore
    solved so the MERGED drawn area is exactly `r_width * r_length`, and
    that identity is asserted before the shapes are inserted -- so the
    extracted resistance is the schematic's `r_length / r_width * sheet_rho`
    exactly, and LVS compares clean on the device VALUE, not just its
    presence.

    **What the area model does not capture.** A right-angle corner carries
    roughly 0.56 of a square, not the full square its area contributes, so
    the PHYSICAL resistance of a folded body is a little under the extracted
    (area-derived) number: about 0.44 squares per corner, i.e. ~1.8 % low at
    `legs=4` (6 corners of 150 squares) for this cell's load resistors. That
    error is common-mode across the two identically-drawn loads, so the
    preamp's differential balance -- the thing the matching plan cares about
    -- is untouched; it moves the load pair's absolute value, which the
    design already treats as a process-spread quantity (poly sheet-rho
    spread is tens of percent). Stated here rather than compensated for:
    compensating would mean drawing MORE area than the schematic declares,
    which would make the extracted value disagree with the reference and
    trade a checked property for an unchecked one. See `../README.md`
    "Resistors, and why there are two comparator cells".

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
    sab = layers[geo.L_SAB]
    res_mk = layers[geo.L_RES_MK]
    resistor_mk = layers[geo.L_RESISTOR]

    if legs < 2 or legs % 2:
        raise ValueError(
            f"legs must be an even number >= 2, got {legs} -- an odd fold "
            "leaves the far terminal at the TOP of the body, which this "
            "routine no longer routes (see its docstring)"
        )

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
    # asked for.
    term_w = max(r_width, _RES_PAD)

    riser_y = row_y0 - geo.GATE_HEAD_H - geo.DROP_H
    # Both terminal leads are `term_w` wide, centred on `a_x`/`b_x` -- `a_x`
    # is offset from `x0` by exactly `term_w // 2` so the LEFT edge of the
    # first leg's lead lands flush on `x0` (the same invariant the
    # fixed-`_RES_PAD` version kept, generalised to a caller-chosen
    # `r_width`; `ResistorColumn.width` below keeps the matching invariant on
    # the right edge, so neighbouring columns packed by `x += column.width`
    # never close in on the wider terminal leads a large `r_width` now draws
    # -- issue #118 found this the hard way: a `term_w` widened from the old
    # `_RES_PAD` without a matching `width` update crowded two adjacent
    # columns into a real `poly2.space.1` / `metal1.space.1` violation).
    a_x = x0 + term_w // 2
    body_x0 = a_x - r_width // 2
    pitch = r_width + _RES_FOLD_SPACE

    # Solve the leg length from the AREA the extractor will measure, not
    # from a centre-line: `legs` legs of `leg_len` plus `legs - 1` corner
    # jogs, whose merged area is `r_width * (legs * leg_len + (legs - 1) *
    # _RES_FOLD_SPACE)`. Setting that equal to `r_width * r_length` is what
    # makes the extracted resistance land exactly on the schematic's.
    leg_len, remainder = divmod(
        r_length - (legs - 1) * _RES_FOLD_SPACE, legs
    )
    if remainder:
        raise ValueError(
            f"r_length={r_length} does not fold into {legs} legs at a "
            f"{_RES_FOLD_SPACE} nm leg gap without a sub-nanometre "
            f"remainder ({remainder} nm) -- the drawn area would not be "
            "exactly r_width * r_length and the extracted resistance would "
            "drift off the schematic's value"
        )
    if leg_len < 2 * r_width:
        raise ValueError(
            f"leg_len={leg_len} is under 2 * r_width={2 * r_width} at "
            f"legs={legs}: the top and bottom corner jogs would overlap and "
            "the folded body would stop being a serpentine"
        )

    y_a1 = row_y0 + _RES_HEAD
    boxes = []
    for index in range(legs):
        lx = body_x0 + index * pitch
        boxes.append(kdb.Box(lx, y_a1, lx + r_width, y_a1 + leg_len))
    for index in range(legs - 1):
        lx = body_x0 + index * pitch
        rx = lx + pitch + r_width
        if index % 2 == 0:  # join this pair at the TOP
            boxes.append(kdb.Box(lx, y_a1 + leg_len - r_width, rx, y_a1 + leg_len))
        else:               # ... and the next pair at the BOTTOM
            boxes.append(kdb.Box(lx, y_a1, rx, y_a1 + r_width))
    body = kdb.Region(boxes).merged()
    drawn = body.area()
    if drawn != r_width * r_length:
        raise AssertionError(
            f"folded body drew {drawn} nm^2, not r_width * r_length = "
            f"{r_width * r_length} nm^2 -- the extracted resistance would "
            "not be the schematic's"
        )
    if body.count() != 1:
        raise AssertionError(
            f"folded body is {body.count()} disjoint polygons, not one -- "
            "it would extract as that many series devices, exactly the "
            "device-count mismatch issue #118 retired"
        )
    for layer in (poly2, sab, res_mk, resistor_mk):
        cell.shapes(layer).insert(body)

    # Both terminals: `legs` is even, so the first and last leg both have a
    # free end at the BOTTOM of the body, and each one's poly landing pad
    # simply continues down to the riser level -- no contact at the device
    # end, the same trick a gate riser uses (see geometry.draw_mosfet). The
    # pre-fold straight body needed a Metal1 hop for its high-Y terminal;
    # the fold removes that piece of routing along with the height.
    b_x = a_x + (legs - 1) * pitch
    for terminal_x in (a_x, b_x):
        cell.shapes(poly2).insert(
            kdb.Box(terminal_x - term_w // 2, riser_y, terminal_x + term_w // 2, y_a1)
        )

    return ResistorColumn(
        a_x=a_x,
        b_x=b_x,
        riser_y=riser_y,
        body=body,
        # Mirrors `a_x`'s `term_w`-based left margin on the right edge: the
        # last leg's terminal lead reaches `b_x + term_w // 2`, so the next
        # column (placed at `x0 + width`) starts exactly `geo.COLUMN_GAP`
        # past it, whatever `r_width`/`term_w`/`legs` the caller asked for.
        width=(legs - 1) * pitch + term_w + geo.COLUMN_GAP,
        height=_RES_HEAD + leg_len,
        legs=legs,
    )
