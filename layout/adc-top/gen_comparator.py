#!/usr/bin/env python3
"""Generate the comparator cell of the `design/adc-top/` block layout
(issue #57), from `design/comparator/comparator.spice`.

Writes, beside this file:

    comparator.gds / .ref.spice / .lvs.json
        the full cell: 27 transistors plus the two 150 kohm p+ poly load
        resistors, each a single drawn `ppolyf_u_1k` device (issue #118 --
        see "Load resistors" below for why they are no longer split).
    comparator_nores.gds / .ref.spice / .lvs.json
        the same placement with the resistor bodies omitted.

WHY TWO CELLS, AND WHAT EACH ONE PROVES
---------------------------------------
Issue #118 drew `SAB` (49/0) + `RES_MK` (110/5) + `Resistor` (62/0) over
each load-resistor body (`lib/place.draw_poly_resistor`), which makes `klt
extract`'s gf180mcu deck recognise it as a real `ppolyf_u_1k` device (1000
ohm/sq, klayout-tools#222/#299) instead of an ordinary Poly2 conductor. Both
`comparator` and `comparator_nores` now keep `pop`/`pon` genuinely distinct
nets and verify all 27 transistors AND both resistors (as real, LVS-checked
devices, not merely DRC-checked geometry). `comparator_nores` predates that
fix -- it existed to give LVS a case where `pop`/`pon` could not collapse
onto `vdd` through an unmodelled resistor short -- and is kept here as an
independent standalone check of the preamp-to-latch connectivity in
isolation from the resistor devices, not because the full `comparator` case
still needs it to keep `pop`/`pon` apart.

**Still not modelled: the schematic's `_2k` (2000 ohm/sq) sheet-rho.** The
PDK's `_1k`/`_2k`/`_3k` high-sheet-rho poly flavours share the identical
drawn marker geometry (selected only by a build-time deck option this
curated deck does not implement), so `_2k` is not reachable by drawing
anything different -- `2AMLogic/klayout-tools#595`, open upstream. The
design is sized for `ppolyf_u_1k` (`design/comparator/comparator.spice`'s
`r_length=150u` at `r_width=1u`, `150 * 1000 ohm/sq = 150 kohm`), not for the
original `_2k` assumption. See `README.md` "Resistors".

MATCHING (floorplan plan Sec 2.1/2.3, `spec/comparator-budget-memo.md` Sec 9)
----------------------------------------------------------------------------
* **Load resistors: one drawn body per resistor, NOT common-centroid.**
  Before issue #118, each 150 kohm resistor was split into two series
  segments placed A-B-B-A so both resistors' centroids landed on the same
  axis -- free to do because the resistors were not LVS-visible devices, so
  the reference could apply whatever net merge the split needed. Now that
  each resistor is a real, individually-recognised `ppolyf_u_1k` device, a
  two-segment split would extract as two 75 kohm devices in series where the
  schematic declares one lumped 150 kohm device -- a genuine device-count
  mismatch `klt lvs` has no way to resolve short of re-introducing exactly
  the kind of net merge issue #118 exists to retire. This is a **stated,
  deliberate deviation** from the matching plan's common-centroid
  recommendation for the resistors specifically (not for the transistors,
  see below): each resistor is now drawn as a single straight body, at the
  benefit of a genuinely LVS-verified resistance and topology.
* **Input pair and current mirror: symmetric, adjacent, NOT split.** The
  four preamp NMOS are placed `Xmb Xmip Xmin Xmt` -- the differential pair
  adjacent at the centre, the 1:1 mirror pair equidistant either side of the
  same axis, all four identically oriented in one row so they share a local
  environment. This is **mirror symmetry, not common centroid**: a true
  common-centroid device must be split into at least two interleaved
  segments, and the pinned `klt`'s LVS engine has no `combine_devices()`
  step, so a split device extracts as N parallel MOSFETs and reports
  `device.unmatched` against the schematic's single lumped device. That is a
  real, stated deviation from the plan's Sec 2.1 for the transistors (not
  for the resistors) -- see `README.md` and the friction filed upstream.
* **Kickback (plan Sec 2.3).** Placement order along the row is preamp ->
  StrongARM latch -> isolation inverters -> NOR SR latch, so the latch's
  regeneration nodes (`outp`/`outn`) and their trunks sit at the opposite
  end of the cell from the preamp inputs (`vinp`/`vinn`), which are the CDAC
  top plates. `clk` is likewise a latch-end net. Nothing routes a
  regeneration node or the clock alongside the top-plate trunks.
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

CELL_NAME = "COMPARATOR"
CELL_NAME_NORES = "COMPARATOR_NORES"

#: Placement order along the row, one Nwell island (and therefore one
#: unnamed PMOS-body net) per group. The order is the kickback constraint of
#: `layout/floorplan-matching-plan.md` Sec 2.3 made physical: the preamp,
#: whose inputs ARE the CDAC top plates, is at one end; the regenerating
#: latch is at the other.
GROUPS: list[tuple[str, list[str]]] = [
    ("nw_preamp", ["Xpre.Xmb", "Xpre.Xmip", "Xpre.Xmin", "Xpre.Xmt"]),
    (
        "nw_latch",
        [
            "Xlat.Xmlt", "Xlat.Xmlp", "Xlat.Xmln", "Xlat.Xmnp", "Xlat.Xmnn",
            "Xlat.Xmpp", "Xlat.Xmpn", "Xlat.Xmrp", "Xlat.Xmrn",
            "Xlat.Xmrd", "Xlat.Xmre",
        ],
    ),
    ("nw_isop", ["Xis.Xp", "Xis.Xn"]),
    ("nw_ison", ["Xir.Xp", "Xir.Xn"]),
    ("nw_nor1", ["Xno1.Xp1", "Xno1.Xp2", "Xno1.Xn1", "Xno1.Xn2"]),
    ("nw_nor2", ["Xno2.Xp1", "Xno2.Xp2", "Xno2.Xn1", "Xno2.Xn2"]),
]

PINS = ["vinp", "vinn", "clk", "ibias", "dout", "doutb", "vdd", "vss"]


def build(subckts: dict[str, nl.Subckt], with_resistors: bool):
    """Build a stand-alone comparator layout (its own `kdb.Layout`)."""
    layout, layers = geo.make_layout()
    name = CELL_NAME if with_resistors else CELL_NAME_NORES
    return layout, build_into(layout, layers, subckts, with_resistors, name)


def build_into(
    layout: kdb.Layout,
    layers: dict[tuple[int, int], int],
    subckts: dict[str, nl.Subckt],
    with_resistors: bool,
    name: str,
    port_nets: dict[str, str] | None = None,
    prefix: str = "",
    escape: list[str] | None = None,
    escape_left: list[str] | None = None,
    escape_margin: int = 6000,
    escape_left_margin: int | None = None,
) -> dict:
    """Draw the comparator as a cell inside an EXISTING layout.

    `gen_adc_top.py` uses this to assemble the comparator into the full
    block (`adc_block.gds`) from the same generator source that produces the
    stand-alone `comparator.gds`, rather than a second copy of it.
    """
    top = layout.create_cell(name)
    port_nets = port_nets or {p: p for p in PINS}

    #: The nets this cell exposes as pins -- computed BEFORE the alias merge
    #: below, because that merge needs them (see `prefer=` there).
    labelled = [port_nets[p] for p in PINS]

    aliases: list[tuple[str, str]] = []
    devices = nl.flatten(
        subckts,
        "comparator",
        port_nets,
        prefix=prefix,
        aliases=aliases,
    )
    # `prefer=set(labelled)` IS LOAD-BEARING, not cosmetic (issue #116).
    # `comparator.spice`'s `Vpp`/`Vpn` are zero-volt probe sources between
    # the `vinp`/`vinn` PORTS and the preamp's own `preamp_in1`/`preamp_in2`
    # gate nets, so `flatten()` hands them back as alias pairs. Without
    # `prefer`, `resolve_aliases()` falls back to "lexicographically
    # smallest name wins" -- and `preamp_in1` < `vinp`, `XCMP.preamp_in1` <
    # `topp` -- so the merged net was named after the INTERNAL node. The
    # cell then labelled/routed a `vinp`/`topp` trunk that no device sat on,
    # leaving the differential pair's gates on a net with exactly one
    # terminal: FLOATING. LVS could not see it, because the same merged
    # device list also generates the reference (`info["devices"]`), so both
    # sides agreed the comparator inputs were disconnected. The symptom was
    # a stuck SAR decision -- see
    # `parasitics/records/20260806-adc-block-comparator-input-float.md`.
    # This is exactly the failure mode `resolve_aliases`' own docstring
    # warns about for the supply node ("449 mismatches during this
    # bring-up"); the input pair is the same trap, one call site later.
    devices = nl.resolve_aliases(devices, aliases, prefer=set(labelled))

    by_path = {d.path: d for d in devices}
    groups = [
        (f"{prefix}{nwell}", [by_path[f"{prefix}{path}"] for path in paths])
        for nwell, paths in GROUPS
    ]
    covered = {f"{prefix}{p}" for _, paths in GROUPS for p in paths}
    missing = {d.path for d in devices if d.is_mos} - covered
    if missing:
        raise RuntimeError(f"GROUPS does not place {sorted(missing)}")

    block = place.draw_devices(
        top, layers, groups, labelled, row_y0=0, auto_finish=False,
        escape=[port_nets.get(n, n) for n in (escape or ())],
        escape_left=[port_nets.get(n, n) for n in (escape_left or ())],
        escape_margin=escape_margin,
        escape_left_margin=escape_left_margin,
    )

    merges: list[tuple[str, str]] = []
    if with_resistors:
        merges = draw_load_resistors(top, layers, devices, block, prefix)
    place.finish_block(block, labelled)

    # A resistor device is only in `ref_devices` when its body was actually
    # drawn (`with_resistors`) -- issue #118: the bodies now extract as real
    # `ppolyf_u_1k` devices, not a Poly2 short, so no net merge is needed for
    # them any more (`merges` stays `[]` either way, see
    # `draw_load_resistors`'s own docstring).
    kept = [d for d in devices if d.is_mos or (with_resistors and d.kind == "res")]
    ref_devices = nl.merge_nets(kept, merges, prefer=set(labelled))
    body_net = block.body_net
    # `pop`/`pon` (each resistor's non-`vdd` terminal) join `pins` alongside
    # the real, hierarchical ones -- see `draw_load_resistors`'s docstring
    # for why they need a Metal1 label at all: it is an LVS-disambiguation
    # device, not a hierarchical port declaration.
    resistor_pins = {d.nets[1] for d in devices if with_resistors and d.kind == "res"}
    pins = sorted({*labelled, *resistor_pins, nl.SUBSTRATE_NET}, key=str.lower)
    return {
        "cell": top,
        "trunks": block.trunks,
        "channel": block.channel,
        "name": name,
        "devices": ref_devices,
        "body_net": body_net,
        "pins": pins,
        "merges": merges,
        "with_resistors": with_resistors,
        "block": block,
    }


def draw_load_resistors(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    devices: list[nl.Device],
    block: place.PlacedBlock,
    prefix: str = "",
) -> list[tuple[str, str]]:
    """Draw both preamp load resistors, each as ONE single straight
    `ppolyf_u_1k` body (see this module's docstring -- issue #118 retired
    the two-series-segment common-centroid split once the resistors became
    real, individually-recognised devices: splitting would have extracted
    as two devices in series against the schematic's one lumped device).

    Returns `[]` -- unlike before issue #118, the drawn bodies now extract
    as real resistor devices, not a Poly2 short, so the LVS reference no
    longer needs a net merge for them (`lib/netlist.write_reference`'s
    `include_resistors=` writes the matching `R` device instead). The empty
    list is kept as the return type so `build_into`'s `merges` plumbing does
    not need a special case.

    Also `mark_pin()`s each resistor's `pop`/`pon` terminal -- NOT because it
    is a real hierarchical port anywhere else, but because `klt lvs`'s
    `NetlistComparer` needs it: empirically (issue #118), the comparator's
    `vdd` rail is a large hub (every PMOS source in the latch/inverters/NOR
    gates, plus both resistors) and with the resistors present as real,
    class-identical, value-identical devices, the comparer's topology-only
    matching cannot always deterministically resolve which of `pop`/`pon`
    is which -- `net.merged`/`device.unmatched` findings on exactly the
    devices that touch them, even though the drawn connectivity is correct
    (confirmed: an isolated differential-pair-plus-resistor-load reproduction
    compares clean; only the FULL circuit's much larger `vdd` fan-out trips
    it). A Metal1 LABEL on `pop`/`pon` gives both sides the same NET NAME, so
    the comparer's name-based matching resolves the pair directly instead of
    relying on topology alone -- confirmed empirically to turn a 9-mismatch
    `device.unmatched`/`net.merged`/`topology` compare into a clean 0. A
    label is a real, standard LVS disambiguation technique for a
    differential structure like this one, not a hack; the cost is two extra
    (internal-only) declared pins on `COMPARATOR`/`ADC_BLOCK`, which
    `build_into` folds into its own `pins`.
    """
    resistors = [d for d in devices if d.kind == "res"]
    if len(resistors) != 2:
        raise RuntimeError(f"expected two load resistors, got {len(resistors)}")
    rlp, rln = resistors  # Xrlp -> pop, Xrln -> pon (comparator.spice order)

    r_width = int(round(rlp.params["w"] * 1e9))
    r_length = int(round(rlp.params["l"] * 1e9))

    x = block.row_x1 + place.NWELL_KEEPOUT
    for dev in (rlp, rln):
        column = place.draw_poly_resistor(
            cell, layers, x, block.row_y0, r_width, r_length
        )
        block.channel.drop(dev.nets[0], column.a_x, column.riser_y)
        block.channel.drop(dev.nets[1], column.b_x, column.riser_y)
        block.channel.mark_pin(dev.nets[1])
        x += column.width
    return []


def write_outputs(outdir: str, layout, info: dict, key: str) -> None:
    name = info["name"]
    layout.write(os.path.join(outdir, f"{key}.gds"), geo.save_options())

    header = [
        f"* Flat LVS reference for {name}.",
        "*",
        "* GENERATED by layout/adc-top/gen_comparator.py from",
        "* design/comparator/comparator.spice's `.subckt comparator` -- do not",
        "* edit. See layout/adc-top/lib/netlist.py for why the layout and this",
        "* reference come from the same parsed design netlist.",
        "*",
        "* Deliberate, documented differences from the schematic, each forced by",
        "* `klt extract`'s gf180mcu ExtractionDeck (see layout/adc-top/README.md):",
        "*   - NMOS bodies on the deck's `vsubs` global (no tap layer);",
        "*   - PMOS bodies on their own Nwell island's net, one per placed",
        "*     group, not on `vdd` (the deck never connects `nwell` to",
        "*     `contact`);",
        "*   - `Vpp`/`Vpn`, the schematic's zero-volt top-plate current probes,",
        "*     are net aliases, not components.",
    ]
    if info["with_resistors"]:
        header += [
            "*   - the two 150 kohm p+ poly load resistors are drawn WITH `SAB`",
            "*     (49/0) + `RES_MK` (110/5) + `Resistor` (62/0) markers (issue",
            "*     #118), so `klt extract` recognises each body as a real",
            "*     `ppolyf_u_1k` device (1000 ohm/sq) instead of a Poly2 short.",
            "*     `pop`/`pon` stay distinct nets and each resistor is a genuine",
            "*     `R` device below -- NOT a net merge. The schematic's original",
            "*     `ppolyf_u_2k` (2000 ohm/sq) sheet-rho is not reachable at this",
            "*     repo's pinned klt commit (`2AMLogic/klayout-tools#595`, open);",
            "*     the design is sized for `_1k` instead (see ../README.md",
            "*     'Resistors').",
        ]
    else:
        header += [
            "*   - the load resistor bodies are NOT drawn in this cell, on",
            "*     purpose. This case keeps `pop`/`pon` on the preamp's own",
            "*     internal nodes so the preamp-to-latch connectivity is checked",
            "*     in isolation from the resistor devices. The full COMPARATOR",
            "*     cell carries the resistors (see above) and, since issue #118,",
            "*     also keeps `pop`/`pon` distinct.",
        ]
    header += [
        "*",
        f"* Runnable by hand:  klt lvs layout/adc-top/{key}.lvs.json --format json",
    ]
    nl.write_reference(
        os.path.join(outdir, f"{key}.ref.spice"),
        name,
        info["devices"],
        info["pins"],
        info["body_net"],
        header,
        include_resistors=info["with_resistors"],
    )

    request = {
        "_comment": [
            f"klt lvs request for {name} -- the extracted layout netlist against",
            "the flat reference generated from design/comparator/comparator.spice.",
            "Both sides are pre-extracted / generated SPICE, for the reason",
            "layout/lvs/cells/lvs_request_match.json records. Paths resolve",
            "against THIS file's directory.",
            "",
            f"    klt lvs layout/adc-top/{key}.lvs.json --format json",
        ],
        "layout": {"netlist": f"{key}.spice", "top": name},
        "reference": {"netlist": f"{key}.ref.spice", "top": name},
    }
    with open(os.path.join(outdir, f"{key}.lvs.json"), "w", encoding="utf-8") as fh:
        json.dump(request, fh, indent=2)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outdir", default=HERE)
    args = parser.parse_args()

    design = nl.design_dir(HERE)
    subckts = nl.parse(os.path.join(design, "comparator", "comparator.spice"))

    for key, with_resistors in (("comparator", True), ("comparator_nores", False)):
        layout, info = build(subckts, with_resistors)
        assert layout.dbu == geo.DBU_UM, f"dbu drifted to {layout.dbu}"
        write_outputs(args.outdir, layout, info, key)
        box = info["cell"].bbox()
        n_mos = sum(1 for d in info["devices"] if d.is_mos)
        n_res = sum(1 for d in info["devices"] if d.kind == "res")
        print(
            f"wrote {key}.gds  transistors={n_mos}  resistors={n_res}  "
            f"{box.width() * geo.DBU_UM:.1f} x {box.height() * geo.DBU_UM:.1f} um "
            f"= {geo.area_um2(box):.0f} um^2"
        )


if __name__ == "__main__":
    main()
