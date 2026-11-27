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

from collections.abc import Sequence
from dataclasses import dataclass

import klayout.db as kdb

from . import geometry as geo
from .netlist import SUBSTRATE_NET, Device


@dataclass(frozen=True)
class PendingTap:
    """One drawn n-well tap awaiting its route to the supply trunk.

    The tap's own geometry is drawn while the row is placed (it is part of
    the Nwell island), but the trunk it has to reach does not exist until
    `Channel.finish()` has packed the channel -- and the corridor it reaches
    through may not be clear until every LATER structure in the same cell is
    drawn (the comparator's load-resistor columns sit in exactly the gap the
    last group's right-hand corridor would use). So the route is deferred to
    :func:`finish_block`, which is the one point where both are true.
    """

    net: str
    #: The tap's own `Metal1` bar, as drawn over its diffusion.
    metal1: kdb.Box
    #: Candidate X columns for the Poly2 riser, in preference order. Each is
    #: the centre of an inter-group gap beside this group's PMOS columns.
    columns: list[int]


@dataclass
class PlacedBlock:
    """What :func:`draw_devices` drew."""

    channel: geo.Channel
    trunks: dict[str, kdb.Box]
    devices: list[tuple[Device, geo.Mosfet]]
    nwell: list[kdb.Box]
    #: One per Nwell island, routed to its supply by :func:`finish_block`.
    taps: list[PendingTap]
    #: Layout net each MOSFET's body terminal actually lands on -- the LVS
    #: reference has to say the same thing (see `lib/netlist.write_reference`).
    body_net: dict[str, str]
    row_x0: int
    row_x1: int
    row_y0: int
    #: The net every NMOS body lands on -- the substrate-tie strip
    #: :func:`finish_block` draws routes to this net's trunk.
    substrate_net: str = SUBSTRATE_NET
    #: The substrate-tie strip's `Metal1` bar, or None when the row drew no
    #: strip. The guard-ring strap lands on THIS (a plain Metal1-to-Metal1
    #: overlap): the strip is already stitched to the substrate trunk by its
    #: own in-cell riser, so the ring needs no Poly2 column of its own --
    #: and a Poly2 strap across the strip's diffusion would be a parasitic
    #: MOSFET, which is exactly the hazard a metal strap does not have.
    subtie_metal1: kdb.Box | None = None
    #: The substrate-tie strip's Poly2 stitch column, reserved during
    #: placement (see `_subtie_riser_column`) and always covered by the
    #: substrate trunk's own span; None for a row with no NMOS columns or
    #: when `subtie_via == "ring"` (the caller straps the strip's Metal1 to
    #: the guard ring itself, so no in-cell riser exists).
    subtie_riser_x: int | None = None
    #: How the strip reaches `vss`: `"trunk"` (a Poly2 riser to the
    #: substrate trunk, the default -- every cell this library LVSes
    #: stand-alone) or `"ring"` (the caller straps the strip's Metal1 bar to
    #: the guard ring at top level -- for cells whose rows are too dense in
    #: drop risers to admit a stitch corridor, which is every decode bank).
    subtie_via: str = "trunk"
    #: The left-of-row fallback stitch column (`geo.SUBTIE_FALLBACK_REACH`
    #: past `row_x0`), for a trunk-mode row whose risers leave no wide
    #: enough gap; None otherwise.
    subtie_fallback_x: int | None = None


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

assert NWELL_KEEPOUT - geo.NWELL_MARGIN - geo.SD_IMPLANT_MARGIN > 0, (
    "the NMOS source/drain Nplus reaches the Nwell island's edge -- raise "
    "NWELL_KEEPOUT or lower geometry.SD_IMPLANT_MARGIN"
)
assert NWELL_KEEPOUT - 2 * geo.SD_IMPLANT_MARGIN >= geo._IMPLANT_SPACE_MIN, (
    "the NMOS Nplus and PMOS Pplus of one group violate the deck's implant "
    "spacing families across the NFET/PFET boundary"
)

#: Widest PMOS a :func:`draw_devices` call with ``fold_shared_sd=True`` may
#: leave UN-paired, in nm (issue #936). The fold exists to cut the ROW
#: height, which the widest column sets; the decode banks' 10 um NMOS
#: columns put the floor at 10 um, so any PMOS wider than this that is not
#: folded into a shared-source/drain pair would silently keep the row (and
#: with it the whole block) tall while paying the pair's width cost anyway.
#: The pairing itself refuses nothing -- a row whose wide PMOS are not
#: consecutive identical twins fails loudly right here instead.
FOLD_ROW_MAX_W = 10000


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


def _tap_columns(pfet_actives: list[kdb.Box], has_left_gap: bool) -> list[int]:
    """Candidate Poly2-riser columns for one group's well tap, best first.

    A group's PMOS columns are bounded on the right by
    `COLUMN_GAP + NWELL_KEEPOUT` of clear space before the next group's
    first active (or by open row past the last group), and on the left by
    the same distance whenever anything precedes them -- this group's own
    NMOS columns, or the previous group. The gap centre is therefore
    `(COLUMN_GAP + NWELL_KEEPOUT) // 2` = 650 nm outside the well's active
    span: 450 nm clear of the nearest `Comp` and 570 nm clear of the nearest
    Poly2 riser at `RISER_W`, both comfortably over `poly2.space.1`.

    The right-hand column is preferred only because the left-hand one does
    not always exist; where both do, either is equally clear, and
    :func:`finish_block` falls through to the second when a later-drawn
    structure has taken the first (the comparator's load-resistor columns
    start `NWELL_KEEPOUT` past the row's right edge, which is inside the
    last group's right-hand gap).
    """
    left = min(a.left for a in pfet_actives)
    right = max(a.right for a in pfet_actives)
    half = (geo.COLUMN_GAP + NWELL_KEEPOUT) // 2
    columns = [right + half]
    if has_left_gap:
        columns.append(left - half)
    return columns


def _subtie_riser_column(
    placed: list[tuple[Device, geo.Mosfet]],
    avoid: Sequence[int] = (),
) -> int | None:
    """The substrate-tie strip's stitch column: the midpoint of the WIDEST
    gap between consecutive drop-riser edges in the row, or None for a row
    with no NMOS columns.

    `avoid` lists the well-tap riser columns: a tap riser is a Poly2 strip
    from a trunk all the way up to its tap, vertically ADJACENT to the
    strip's own corridor whenever both claim the same column, and two
    stacked corridors 80 nm apart are a `poly2.space.1` violation, not a
    merge. Any gap overlapping an avoided column's
    `geo.SUBTIE_RISER_COLUMN_CLEAR`-padded corridor is skipped.

    The corridor the strip's stitch draws must otherwise clear every
    existing Poly2 by `geometry.SUBTIE_RISER_COLUMN_CLEAR` (300 nm,
    `find_stitch_column`'s own demand, comfortably over `poly2.space.1`'s
    240). A device column's own source-to-gate gap is NOT reliably that
    wide -- it depends on the drawn geometry -- but the gap from one
    column's last riser to the next column's first riser is
    `COLUMN_GAP + 2 * _GATE_EDGE_TO_SD_RISER - RISER_W` for every pair of
    adjacent devices, so a row of two or more devices always has one. If
    even the widest gap is too narrow the row cannot host the strip and
    the generation fails loudly here rather than in DRC.
    """
    edges: list[tuple[int, int]] = sorted(
        (x - geo.RISER_W // 2, x + geo.RISER_W // 2)
        for _dev, m in placed
        for x in (m.source_x, m.gate_x, m.drain_x)
    )
    if not edges:
        return None
    need = geo.RISER_W + 2 * geo.SUBTIE_RISER_COLUMN_CLEAR
    best_lo = best_hi = None
    best = 0
    for (_lo0, hi0), (lo1, _hi1) in zip(edges, edges[1:]):
        mid = (hi0 + lo1) // 2
        if any(abs(mid - a) < geo.RISER_W + 2 * geo.SUBTIE_RISER_COLUMN_CLEAR
               for a in avoid):
            continue
        if lo1 - hi0 > best:
            best = lo1 - hi0
            best_lo, best_hi = hi0, lo1
    if best_lo is None or best < need:
        # No gap in the row: the caller falls back to the column left of
        # the row (`geo.SUBTIE_FALLBACK_REACH`), where nothing draws Poly2.
        return None
    # Snap to the manufacturing grid: the raw midpoint of two on-grid
    # edges can still be off it when their sum is odd.
    return (best_lo + best_hi) // 2 // geo.GRID_NM * geo.GRID_NM


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
    tap_net: str = "vdd",
    substrate_net: str = SUBSTRATE_NET,
    subtie_via: str = "trunk",
    fold_shared_sd: bool = False,
) -> PlacedBlock:
    """Draw every MOSFET in `groups` in one row and route every terminal into
    a left-edge-packed channel below the row.

    A **group** is a set of devices that shares one Nwell island and is
    placed contiguously: its NMOS columns first, then its PMOS columns. The
    group's name labels that island at the call site; it is not a net. The
    island is a physical well, and the curated gf180mcu deck never
    connects `nwell` to `contact` by itself -- what ties the island
    electrically is the n+ tap this function draws in it, which
    :func:`finish_block` routes to `tap_net`. Every PMOS body in every
    group therefore lands on `tap_net` in the extracted netlist, not on an
    unnamed per-island well net (see `lib/netlist.write_reference`).

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

    `tap_net` is the supply each group's Nwell island is biased at -- `vdd`
    for every PMOS body this repo draws. :func:`finish_block` routes each
    island's n+ tap to that net's trunk; a cell whose channel has no such
    trunk is a hard error there rather than a silently untapped well.

    `substrate_net` is the matching answer for the NMOS bodies, and it is
    the caller's to state: the tie is drawn here (`finish_block`), but a
    label decides what the deck calls the net it reaches. A `Pplus`-marked
    substrate tie that lands on a labelled net makes the NMOS bodies report
    that net (`vss` throughout this repo); a tie that reaches no labelled
    net leaves them on the deck's `vsubs` global (`SUBSTRATE_NET`). A ring
    is only one way to provide the tie. `gen_adc_top.py` rings both its
    regions in `Pplus`-marked diffusion strapped to `vss` and passes
    `"vss"`. The stand-alone comparator draws no ring and passes `"vss"` as
    well: the strip :func:`finish_block` draws under every row with NMOS
    columns (DR-0049) is `Pplus`-marked and routed to the cell's own
    labelled `vss` trunk. `SUBSTRATE_NET` is for a tie with no label to
    merge into -- the `adc_tgate` leaves have no `vss` port, so their strip
    lands on an unlabelled track and `vsubs` keeps its name. Both
    `substrate_net` and `tap_net` land in `body_net`, which is what
    generates the LVS reference -- so the reference states whichever one
    the geometry actually produces.

    Since #356 the group's own `nwell_net` name no longer appears in
    `body_net`: every island is tapped to `tap_net`, so a PMOS body reports
    that net rather than an anonymous per-island well net. The name is kept
    on the group because it is still what makes the grouping readable at the
    call sites, and because it is the placement unit's identity.

    SHARED-SOURCE/DRAIN FOLDING (``fold_shared_sd``, issue #936)
    ------------------------------------------------------------
    With the flag on, two CONSECUTIVE PMOS in one group that are identical
    twins -- same `w`, same `l`, same three terminal nets, i.e. two parallel
    fingers of one logical device as a folded netlist states them -- are
    drawn as one folded pair: the second finger's active island ABUTS the
    first's (no `COLUMN_GAP`), and it is MIRRORED in X so the diffusion the
    two islands share at the abutment carries the SAME net on both sides
    (finger A's drain-side against finger B's drain-side). That abutted
    diffusion is one continuous island after extraction -- a real shared
    source/drain, not two adjacent ones -- so the pair costs `2 * (2*SD_EXT
    + l) + COLUMN_GAP` of row width instead of two full column pitches,
    while each finger's own `w` is what sets the row height.

    This is the lever #668's null result named but did not test ("a real
    shared source/drain fold"): it trades row WIDTH for row HEIGHT, which
    this block's floorplan can absorb (the banks are narrower than the
    reserve column that sets the block width) where the height directly
    moves the block edge. A PMOS wider than `FOLD_ROW_MAX_W` that the row
    cannot pair fails the run loudly -- see that constant.
    """
    placed: list[tuple[Device, geo.Mosfet]] = []
    #: Paths of devices drawn as the MIRRORED second finger of a folded
    #: pair: their low-X terminal (`source_x`) carries the drain net, so the
    #: channel drops below have to swap. Everything else about a mirrored
    #: finger is drawn identically to a normal one.
    mirrored: set[str] = set()
    body_net: dict[str, str] = {}
    nwell_boxes: list[kdb.Box] = []
    taps: list[PendingTap] = []
    x = x0

    for group_index, (nwell_net, members) in enumerate(groups):
        mos = [d for d in members if d.is_mos]
        nfets = [d for d in mos if d.kind == "nfet"]
        pfets = [d for d in mos if d.kind == "pfet"]
        if group_index:
            x += NWELL_KEEPOUT
        nfet_actives: list[kdb.Box] = []
        pfet_actives: list[kdb.Box] = []
        for dev in nfets:
            m = geo.draw_mosfet(
                cell, layers, x, row_y0,
                w=dev.w_nm, l=dev.l_nm, is_pmos=False,
            )
            nfet_actives.append(m.active)
            placed.append((dev, m))
            body_net[dev.path] = substrate_net
            x += geo.column_pitch(dev.l_nm)
        if nfets and pfets:
            x += NWELL_KEEPOUT
        pfet_index = 0
        while pfet_index < len(pfets):
            dev = pfets[pfet_index]
            twin = (
                pfets[pfet_index + 1]
                if fold_shared_sd and pfet_index + 1 < len(pfets)
                else None
            )
            is_pair = twin is not None and (
                twin.w_nm == dev.w_nm
                and twin.l_nm == dev.l_nm
                and twin.nets == dev.nets
            )
            if fold_shared_sd and not is_pair and dev.w_nm > FOLD_ROW_MAX_W:
                raise RuntimeError(
                    f"fold_shared_sd row cannot pair the {dev.w_nm} nm PMOS "
                    f"at {dev.path!r} with an identical consecutive twin -- "
                    "an unpaired device this wide keeps the row height the "
                    "fold exists to cut (see FOLD_ROW_MAX_W)"
                )
            m = geo.draw_mosfet(
                cell, layers, x, row_y0,
                w=dev.w_nm, l=dev.l_nm, is_pmos=True,
            )
            pfet_actives.append(m.active)
            placed.append((dev, m))
            body_net[dev.path] = tap_net
            if is_pair:
                # The twin's island abuts A's (its x0 one island width on),
                # mirrored: the terminals facing the abutment carry the same
                # net, so the two diffusions merge into ONE shared island.
                island_w = 2 * geo.SD_EXT + dev.l_nm
                mt = geo.draw_mosfet(
                    cell, layers, x + island_w, row_y0,
                    w=twin.w_nm, l=twin.l_nm, is_pmos=True,
                )
                pfet_actives.append(mt.active)
                placed.append((twin, mt))
                mirrored.add(twin.path)
                body_net[twin.path] = tap_net
                # Step onto the twin's own column so the shared loop-end
                # advance lands one full pitch past IT (pair footprint:
                # 2 * island_w + COLUMN_GAP).
                x += island_w
                pfet_index += 1
            x += geo.column_pitch(dev.l_nm)
            pfet_index += 1
        well = geo.draw_shared_nwell(cell, layers, pfet_actives)
        # One merged implant region per polarity per group (DR-0047, issue
        # #836): NMOS S/D -> Nplus, PMOS S/D -> Pplus, drawn after the well
        # so the PMOS region can be checked against the tap strip it faces.
        geo.draw_sd_implants(
            cell, layers, nfet_actives, pfet_actives,
            well.tap_comp if well is not None else None,
        )
        if well is not None:
            nwell_boxes.append(well.box)
            columns = _tap_columns(
                pfet_actives, bool(nfets) or group_index > 0
            )
            # The extra DF.13 strips (DR-0049, issue #885) route on the same
            # inter-group gap columns, and they are queued FIRST -- list
            # order is `_route_well_taps`' routing order. An extra strip
            # sits at mid-island height, right beside live PMOS S/D rails,
            # so only some of the shared candidate columns can host its
            # grown Metal1 lead (the one it can reach without crossing a
            # rail -- checked explicitly in `_route_well_taps`); the top
            # strip floats ABOVE every column, where a lead grown toward
            # whichever column survives crosses nothing at all. Queuing the
            # unconstrained tap first would strand the constrained one on
            # the column whose lead is a short (`adc_tgate_dum`'s extra
            # strip drew exactly that short before this ordering existed:
            # extraction reported `vdd|vin|vout` as one net).
            for _extra_comp, extra_metal1, _extra_cuts in well.extra_taps:
                taps.append(
                    PendingTap(net=tap_net, metal1=extra_metal1, columns=columns)
                )
            taps.append(
                PendingTap(net=tap_net, metal1=well.tap_metal1, columns=columns)
            )
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
        if dev.path in mirrored:
            # Mirrored second finger of a folded pair: its low-X terminal
            # (`source_x`) faces the shared island and carries the DRAIN
            # net -- swap the two S/D drops, everything else is identical.
            channel.drop(d_net, m.source_x, m.riser_y)
            channel.drop(g_net, m.gate_x, m.riser_y)
            channel.drop(s_net, m.drain_x, m.riser_y)
        else:
            channel.drop(s_net, m.source_x, m.riser_y)
            channel.drop(g_net, m.gate_x, m.riser_y)
            channel.drop(d_net, m.drain_x, m.riser_y)

    # Reserve the substrate-tie strip's stitch column now, BEFORE track
    # packing, so the trunk it stitches to provably spans it (`Channel.extend`
    # grows the net's packed span; growing after `finish()` would be the
    # silent no-op the tap routing's own comment warns about). The column is
    # the midpoint of the WIDEST gap between consecutive drop-riser edges in
    # the row (`_subtie_riser_column`), skipping any gap that overlaps a
    # well-tap riser column, or None when no gap in the row is wide enough
    # -- a device column's own source-to-gate gap is NOT reliably that wide
    # -- in which case the strip's stitch falls back to the column one
    # `geo.SUBTIE_FALLBACK_REACH` left of the row, reserved alongside.
    gap_x = (
        _subtie_riser_column(placed, [c for t in taps for c in t.columns])
        if subtie_via == "trunk"
        else None
    )
    fallback_x = x0 - geo.SUBTIE_FALLBACK_REACH if subtie_via == "trunk" else None
    if subtie_via == "trunk":
        # BOTH candidate columns join the trunk's packed span: the strip's
        # stitch lands on whichever one survives `find_stitch_column`
        # against the finished channel's neighbours, and the trunk
        # provably covers it either way. Ring-mode rows draw no riser.
        channel.extend("vss", fallback_x)
        if gap_x is not None:
            channel.extend("vss", gap_x)
    subtie_riser_x = gap_x

    for net in escape or ():
        channel.extend(net, row_x1 + escape_margin)
    for net in escape_left or ():
        channel.extend(net, x0 - (escape_left_margin or escape_margin))
    # Force `tap_net`'s trunk to reach every candidate riser column BEFORE
    # packing. A trunk grown afterwards is either a hard error
    # (`Channel.extend_drawn` on a shared track) or a silent no-op (issue
    # #356's own first cut landed the well-tap contacts in empty substrate
    # for exactly the reason `geometry.stitch`'s docstring warns about).
    for tap in taps:
        for column in tap.columns:
            channel.extend(tap.net, column)

    block = PlacedBlock(
        channel=channel,
        trunks={},
        devices=placed,
        nwell=nwell_boxes,
        taps=taps,
        body_net=body_net,
        row_x0=x0,
        row_x1=row_x1,
        row_y0=row_y0,
        substrate_net=substrate_net,
        subtie_riser_x=subtie_riser_x,
        subtie_via=subtie_via,
        subtie_fallback_x=fallback_x,
    )
    if auto_finish:
        finish_block(block, pins)
    return block


def finish_block(block: PlacedBlock, pins: list[str]) -> dict[str, kdb.Box]:
    """Pack and draw `block`'s channel, then route every Nwell island's tap
    to its supply trunk and draw the row's substrate-tie strip.

    Split out of :func:`draw_devices` so a caller can add more drops first
    -- the comparator's load-resistor columns are placed after the
    transistor row, and a drop after `Channel.finish()` is a hard error
    rather than a silent no-op. The tap routing lives here for the same
    reason from the other side: it needs the packed trunk AND every shape
    the caller has drawn since, because the corridor it reaches through runs
    past both.
    """
    for net in pins:
        block.channel.mark_pin(net)
    block.trunks = block.channel.finish()
    _route_well_taps(block)
    _draw_substrate_tie_strip(block)
    return block.trunks


def _route_well_taps(block: PlacedBlock) -> None:
    """Wire each drawn n+ well tap down to its supply trunk.

    ONE Poly2 riser per island, in the inter-group gap beside it, contacting
    the tap's own `Metal1` bar at the top and the supply trunk at the
    bottom -- the same Metal1-trunk / Poly2-riser discipline every other
    terminal in this library uses, and for the same reason: the riser has to
    cross the whole device row and the whole channel, and Poly2 is the only
    layer this block routes on that carries no connectivity across those
    crossings (`geometry`'s module docstring).

    Poly2 is ~81x Metal1's sheet resistance (`layout/power/`'s measured
    table), and this riser is 20-60 um long -- which is irrelevant *here*
    and would not be on a rail: a well tie carries reverse-bias junction
    leakage, nanoamps, so even 1 kohm of riser puts microvolts on the body.
    Routing the taps on Poly2 rather than pushing supply geometry onto
    Metal2 is also what keeps issue #346's measured premise -- this block
    has ZERO supply area above Metal1 -- true of the tapped layout.
    """
    if not block.taps:
        return
    cell = block.channel.cell
    layers = block.channel.layers
    for tap in block.taps:
        trunk = block.trunks.get(tap.net)
        if trunk is None:
            raise RuntimeError(
                f"well tap wants net {tap.net!r}, which this block's channel "
                f"does not carry (it has {sorted(block.trunks)})"
            )
        reach = geo.RISER_W // 2 + 80
        y_lo, y_hi = trunk.bottom, tap.metal1.top
        usable = [
            x for x in tap.columns
            if trunk.left + reach <= x <= trunk.right - reach
        ]
        # The grown lead is Metal1 AT THE TAP'S OWN HEIGHT: on a top strip
        # that is above every column and crosses nothing, but an extra
        # DF.13 strip (DR-0049) sits at mid-island height, where a lead
        # grown across the island would land on the live S/D rails it
        # passes. `find_stitch_column` vets only the Poly2 riser's
        # corridor (Poly2 and Comp), so the lead is vetted here: a
        # candidate whose lead would touch or overlap any drawn Metal1
        # outside the tap's own bar is not routable. Computed per tap,
        # not hoisted: an earlier tap's own lead is exactly the kind of
        # drawn metal a later tap's lead must not cross.
        drawn_m1 = (
            kdb.Region(cell.begin_shapes_rec(layers[geo.L_METAL1])).merged()
        )
        foreign_m1 = drawn_m1 - kdb.Region([tap.metal1])
        routable = [
            x for x in usable
            if (
                foreign_m1
                & kdb.Region([
                    kdb.Box(
                        min(tap.metal1.left, x - reach),
                        tap.metal1.bottom,
                        max(tap.metal1.right, x + reach),
                        tap.metal1.top,
                    )
                ])
            ).is_empty()
        ]
        column = geo.find_stitch_column(cell, layers, routable, y_lo, y_hi)
        if column is None:
            raise RuntimeError(
                f"no clear Poly2 column for the well tap at {tap.metal1} "
                f"among {usable} (trunk {trunk.left}..{trunk.right}) -- "
                "widen NWELL_KEEPOUT or move whatever now occupies the gap"
            )
        # Grow the tap's own Metal1 bar sideways into the corridor, so the
        # riser's top contact lands on drawn metal rather than on substrate.
        lead = kdb.Box(
            min(tap.metal1.left, column - reach),
            tap.metal1.bottom,
            max(tap.metal1.right, column + reach),
            tap.metal1.top,
        )
        cell.shapes(layers[geo.L_METAL1]).insert(lead)
        geo.stitch(cell, layers, column, [lead, trunk])


def _draw_substrate_tie_strip(block: PlacedBlock) -> None:
    """Draw the row's p+ substrate-tie strip below the channel and stitch it
    to the substrate net's trunk (DR-0049, issue #885).

    WHY BELOW THE CHANNEL, AND WHY ONE STRIP PER ROW. The 0.8.0 deck's
    `comp.tap_distance.psub.lv.1` (DF.14_LV) flags a whole NMOS S/D polygon
    that comes no closer than `geo.TAP_DISTANCE_LV` to a PCOMP substrate
    tie; before this strip the only ties in most cells were the guard rings
    at the block's periphery, so every NMOS row deeper than 20 um into the
    block was flagged whole (84 markers on `adc_block`, measured in #836's
    DRC record). One strip below the channel covers the whole row at once,
    for the same whole-polygon reason: every S/D polygon in a row starts at
    that row's `row_y0`, and the strip reaches to within a couple of
    microns of it, so every polygon in the row intersects the strip's grown
    reach no matter how tall the row is. Between the row and the strip
    there is nothing but the channel's own metal -- the gate heads stop at
    `riser_y` and the Poly2 risers with them -- so the strip clears every
    Comp and Poly2 shape in the cell by more than a micron, and the rules
    it DOES sit under (`metal1.space.1` against the deepest trunk, via
    `geo.SUBTIE_M1_GAP`) are cleared by construction.

    THE STRIP IS A REAL TIE, NOT A DRC COUNTERMEASURE: `Comp` marked
    `Pplus`, tiled with CO.1 contact squares by the same `contact_array`
    the well taps use, `Metal1` over it, and one Poly2 riser -- the same
    Metal1-trunk/Poly2-riser discipline every terminal in this library
    uses -- down to the `substrate_net` trunk, so `klt extract` resolves
    the strip as part of the `vss` island exactly as it resolves the
    guard-ring straps. A Poly2 strap over the tie's own diffusion would be
    a parasitic MOSFET -- the same hazard `geo.stitch` refuses and the
    guard-ring strap's Metal1 tab avoids -- so the strip's Comp is drawn
    as TWO segments with the riser's column between them, each edge
    `geo.SUBTIE_RISER_COMP_CLEAR` clear of the corridor, while the strip's
    Metal1 runs unbroken under the riser and carries the connection across
    the gap.

    A row with no NMOS columns draws no strip: there is no NCOMP outside
    Nwell for it to serve, and a PCOMP structure no rule needs is exactly
    the "unverifiable geometry" DR-0032 declined to draw.
    """
    if not any(d.kind == "nfet" for d, _ in block.devices):
        return
    # `substrate_net` names what the NMOS BODIES land on in the LVS
    # reference: a drawn rail (`vss`, when the caller rings the substrate --
    # gen_adc_top passes "vss") or the extraction deck's ambient substrate
    # global (`vsubs`, the default -- a name no trunk ever carries, because
    # the substrate is not metal anywhere in this library). A tie strip is
    # `vss` metal by definition either way -- the same net both guard rings
    # strap to -- so the trunk it routes to is `substrate_net`'s when that
    # rail exists and `vss` otherwise.
    trunk = block.trunks.get(block.substrate_net) or block.trunks.get("vss")
    if trunk is None:
        raise RuntimeError(
            f"substrate tie strip wants net {block.substrate_net!r} (or "
            f"'vss'), which this block's channel does not carry (it has "
            f"{sorted(block.trunks)})"
        )
    cell = block.channel.cell
    layers = block.channel.layers
    strip_y1 = block.channel.y_bottom - geo.SUBTIE_M1_GAP
    strip_y0 = strip_y1 - geo.TAP_COMP_H
    # Pick the riser column FIRST, against the geometry that already exists
    # (the channel's own drop risers are Poly2, and a corridor landing on
    # one would short the tie to whatever net that riser carries). The Comp
    # is drawn only afterwards, as two segments ending
    # `SUBTIE_RISER_COMP_CLEAR` short of the column on each side, so the
    # probe above never saw it and the corridor `stitch` inserts still
    # clears the diffusion. The Metal1 bar, not the Comp, is what spans the
    # whole row: the segments are its contact lands, and the DF.14 reach is
    # measured from the PCOMP they form, not from the metal.
    if block.subtie_via == "ring":
        # The caller straps this strip's Metal1 bar to the guard ring
        # itself (`block.subtie_metal1` says where): no riser, so the Comp
        # needs no gap and spans the whole row.
        comp = kdb.Box(block.row_x0, strip_y0, block.row_x1, strip_y1)
        cell.shapes(layers[geo.L_COMP]).insert(comp)
        cell.shapes(layers[geo.L_PPLUS]).insert(
            comp.enlarged(geo.IMPLANT_MARGIN, geo.IMPLANT_MARGIN)
        )
        if geo.contact_array(cell, layers, comp, along_x=True) == 0:
            raise RuntimeError(
                f"substrate tie strip {comp} tiled 0 contact cuts"
            )
        metal = kdb.Box(block.row_x0, strip_y0, block.row_x1, strip_y1)
        cell.shapes(layers[geo.L_METAL1]).insert(metal)
        block.subtie_metal1 = metal
        return
    assert block.subtie_via == "trunk"  # ring mode returned above
    usable = [
        x
        for x in (block.subtie_riser_x, block.subtie_fallback_x)
        if x is not None
    ]
    assert usable, "trunk-mode row reserved no stitch column"
    x_col = geo.find_stitch_column(cell, layers, usable, strip_y0, trunk.top)
    if x_col is None:
        raise RuntimeError(
            f"no clear Poly2 column for the substrate tie strip of "
            f"{cell.name} at {usable} -- move whatever occupies the corridor"
        )
    # The Comp lands on each side of the riser column that is actually
    # inside the row; a column outside the row (the left-of-row fallback)
    # leaves ONE segment spanning the whole row. A segment shorter than one
    # contact with its enclosure would tile zero cuts; drop it rather than
    # draw an uncontactable diffusion.
    segments = [
        seg
        for seg in (
            (
                kdb.Box(block.row_x0, strip_y0,
                        min(x_col - geo.SUBTIE_RISER_COMP_CLEAR, block.row_x1),
                        strip_y1)
                if x_col - geo.SUBTIE_RISER_COMP_CLEAR > block.row_x0
                else None
            ),
            (
                kdb.Box(max(x_col + geo.SUBTIE_RISER_COMP_CLEAR, block.row_x0),
                        strip_y0, block.row_x1, strip_y1)
                if x_col + geo.SUBTIE_RISER_COMP_CLEAR < block.row_x1
                else None
            ),
        )
        if seg is not None
    ]
    if not segments:
        raise RuntimeError(
            f"substrate tie strip {block.row_x0}..{block.row_x1} has no "
            f"room for a contacted segment around the riser column "
            f"{x_col} -- the {block.substrate_net!r} trunk does not reach "
            "this row"
        )
    for seg in segments:
        cell.shapes(layers[geo.L_COMP]).insert(seg)
        cell.shapes(layers[geo.L_PPLUS]).insert(
            seg.enlarged(geo.IMPLANT_MARGIN, geo.IMPLANT_MARGIN)
        )
        cuts = geo.contact_array(cell, layers, seg, along_x=True)
        if cuts == 0:  # unreachable behind the width check above
            raise RuntimeError(
                f"substrate tie strip segment {seg} tiled 0 contact cuts"
            )
    # One Metal1 bar over BOTH segments and the riser gap, reaching `reach`
    # past the riser column when that sits outside the row (the left-of-row
    # fallback), so the stitch's bottom contact lands on drawn metal and
    # the two contact lands share one net -- the same lead-growth
    # `_route_well_taps` does for the well taps.
    reach = geo.RISER_W // 2 + 80
    metal = kdb.Box(
        min(block.row_x0, x_col - reach),
        strip_y0,
        max(block.row_x1, x_col + reach),
        strip_y1,
    )
    cell.shapes(layers[geo.L_METAL1]).insert(metal)
    if not (
        trunk.left + geo.RISER_W // 2 <= x_col <= trunk.right - geo.RISER_W // 2
    ):
        trunk = block.channel.extend_drawn("vss", x_col)
    geo.stitch(cell, layers, x_col, [metal, trunk])
    block.subtie_metal1 = metal


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
 #: rejected, see `gen_comparator.RESISTOR_LEGS`. (The 0.8.0 deck's SB.2
 #: `sab.space.1` does NOT bind the fold gap -- the notch between two legs is
 #: internal to ONE merged SAB region, and a space rule measures between
 #: distinct shapes; only the inter-column gap below carries SAB-to-SAB
 #: spacing. Issue #838 measured the 0.8.0 SB.10 alternative -- growing
 #: Poly2 220 nm beyond every SAB edge, which WOULD have forced this gap to
 #: 680 nm minimum -- and found it incompatible with the extraction deck's
 #: terminal derivation; see `../drc/records/` for the #838 measurement
 #: carried forward by the issue #890 record.)
_RES_FOLD_SPACE = 600

#: Gap between the two resistor columns (NOT `geometry.COLUMN_GAP`, which
#: is shared repo-wide with asserts at `geometry.py`'s import and moves
#: every other column in the layout if raised -- issue #838 keeps this
#: resistor-local). Sized from the rule that binds it: the two SAB markers
#: sit body-sized in their columns, so the SAB-to-SAB gap IS the column
#: gap, and the 0.8.0 deck's `sab.space.1` (DRM SB.2, 420 nm minimum SAB
#: spacing) fired on the previous 400 nm value -- the one `sab.space.1`
#: marker on `adc_block`, re-measured on the committed stream while
#: rebuilding #838 for issue #890 (comparator and adc_block each carry
#: exactly one; every other 0.8.0 count on both cells is main's
#: pre-existing state). The house sizing would say 420 + ~120 = 540, and
#: issue #838 chose 550 instead because a +140 nm delta landed
#: `gen_adc_top`'s strap- and guard-ring-derived coordinates off the 5 nm
#: manufacturing grid -- measured then: 3708 `*.ongrid.1` markers on
#: `adc_block` at gaps 600 and 800, zero at 550/700/1000. Issue #890's
#: rebuild re-ran that sweep on the post-#839, post-DR-0049 geometry:
#: 540, 550 and 600 now ALL measure grid-clean (zero `*.ongrid.1` on
#: `adc_block`) and SB.2-clean, so the grid no longer discriminates -- 550
#: is retained as this issue's pinned value, keeping 130 nm of drawn
#: headroom over SB.2's 420 nm minimum (540 keeps 120), and the 540
#: house-value option is recorded operator-reviewable in the issue #890
#: DRC record. Both
#: `resistor_column_width` and `ResistorColumn.width` consume this, so the
#: drawn clearance and the placement reservation stay one expression
#: (issue #118 found the cost of letting them drift).
_RES_COLUMN_GAP = 550


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
        + _RES_COLUMN_GAP
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
    "Resistors, and why there is one comparator cell".

    **What this does and does not verify.** The stripe sits on a layer the
    `klt drc` gf180mcu deck DOES check (`poly2.width.1`/`poly2.space.1`/
    `poly2.enclosing.contact.1`), so its geometry is genuinely rule-checked.
    The body is also covered by `SAB` (49/0) + `RES_MK` (110/5) + `Resistor`
    (62/0), which is what makes `klt extract`'s gf180mcu deck recognise it as
    a real `ppolyf_u_1k` device (1000 ohm/sq, klayout-tools#222/#299) instead
    of an ordinary Poly2 *conductor* -- issue #118. The three marker layers
    are drawn exactly the size of `body` and stay that way: the 0.8.0 deck
    (`klayout-tools` 0.8.0, which added the whole `SB` section the pinned
    0.6.0 deck never had) carries TWO rules keyed on them, and only one of
    them is satisfiable together with the extraction this function exists
    for. `sab.space.1` (DRM SB.2, 420 nm minimum SAB spacing) IS satisfied
    as of issue #838 -- it fires on the gap between the two load resistors'
    SAB markers, which this module's resistor-local `_RES_COLUMN_GAP` now
    carries at 420 + 130 nm, and the pins stay exact-body copies because a
    space rule between distinct shapes never looks inside one. But
    `poly2.enclosing.sab.1` (DRM SB.10, 220 nm minimum Poly2 extension
    beyond related SAB) is NOT satisfiable here: an enclosure rule forces
    Poly2 to surround the marked body with an unmarked 220 nm band, the
    extraction deck derives the device's terminals from Poly2 minus the
    recognised body, and that band merges both terminal leads into ONE
    contact region touching the wire on every side -- measured (issue #838,
    carried forward by issue #890's rebuild, see `../drc/records/`): with
    the band drawn, the marked regions are
    still exactly two 150000 nm x 1000 nm serpentines, but each is touched
    by one contact component instead of two, `klt extract` reports 27
    devices instead of 29, and both resistors disappear from the netlist.
    There is no deck-legal marked shape that escapes the band, so exact-body
    coverage -- and with it the extracted `150000 ohm L=150U W=1U` the
    ratified design pins -- and SB.10 cannot both hold; that trade is
    routed, not taken unilaterally.


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
        # column (placed at `x0 + width`) starts exactly `_RES_COLUMN_GAP`
        # past it, whatever `r_width`/`term_w`/`legs` the caller asked for.
        width=(legs - 1) * pitch + term_w + _RES_COLUMN_GAP,
        height=_RES_HEAD + leg_len,
        legs=legs,
    )
