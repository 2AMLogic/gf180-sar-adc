#!/usr/bin/env python3
"""Generate the comparator cell of the `design/adc-top/` block layout
(issue #57), from `design/comparator/comparator.spice`.

Writes, beside this file:

    comparator.gds / .ref.spice / .lvs.json
        the full cell: 27 transistors plus the two 150 kohm p+ poly load
        resistors, drawn common-centroid.
    comparator_nores.gds / .ref.spice / .lvs.json
        the same placement with the resistor bodies omitted.

WHY TWO CELLS, AND WHAT EACH ONE PROVES
---------------------------------------
`klt extract`'s gf180mcu deck has no resistor device class and no
silicide-block layer, so a drawn poly resistor extracts as a plain Poly2
**conductor** -- a short between its terminals. In the full cell that merges
`pop`, `pon` and `vdd` into one net, and its LVS reference has to say the
same thing (`lib/netlist.merge_nets`). The comparison then still checks all
27 transistors, but it can no longer tell `pop` from `pon`, so it could not
catch a swapped preamp output.

`comparator_nores` exists to close exactly that hole: identical device
placement and routing, resistor bodies not drawn, so `pop`/`pon` stay
distinct nets and LVS genuinely verifies the preamp-to-latch input
connectivity. Between the two runs, every transistor terminal in the cell is
checked against `comparator.spice`, and the resistor geometry is checked by
`klt drc` -- which is the most this toolchain can do. Stated plainly in
`README.md`; nothing here claims a resistance was verified.

MATCHING (floorplan plan Sec 2.1/2.3, `spec/comparator-budget-memo.md` Sec 9)
----------------------------------------------------------------------------
* **Load resistors: genuinely common-centroid.** Each 150 kohm resistor is
  split into two series segments and the four segments are placed A-B-B-A,
  so both resistors' centroids land on the same axis and a linear process
  gradient cancels to first order. Splitting is free here precisely because
  the resistors are not LVS-visible devices.
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

    aliases: list[tuple[str, str]] = []
    devices = nl.flatten(
        subckts,
        "comparator",
        port_nets,
        prefix=prefix,
        aliases=aliases,
    )
    devices = nl.resolve_aliases(devices, aliases)

    by_path = {d.path: d for d in devices}
    groups = [
        (f"{prefix}{nwell}", [by_path[f"{prefix}{path}"] for path in paths])
        for nwell, paths in GROUPS
    ]
    covered = {f"{prefix}{p}" for _, paths in GROUPS for p in paths}
    missing = {d.path for d in devices if d.is_mos} - covered
    if missing:
        raise RuntimeError(f"GROUPS does not place {sorted(missing)}")

    labelled = [port_nets[p] for p in PINS]
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

    ref_devices = nl.merge_nets(
        [d for d in devices if d.is_mos], merges, prefer=set(labelled)
    )
    body_net = block.body_net
    pins = sorted({*labelled, nl.SUBSTRATE_NET}, key=str.lower)
    return {
        "cell": top,
        "trunks": block.trunks,
        "channel": block.channel,
        "name": name,
        "devices": ref_devices,
        "body_net": body_net,
        "pins": pins,
        "merges": merges,
        "block": block,
    }


def draw_load_resistors(
    cell: kdb.Cell,
    layers: dict[tuple[int, int], int],
    devices: list[nl.Device],
    block: place.PlacedBlock,
    prefix: str = "",
) -> list[tuple[str, str]]:
    """Draw both preamp load resistors, each split into two series segments,
    the four segments placed A-B-B-A about a common axis.

    Returns the net merges the LVS reference must apply (see this module's
    docstring): the deck extracts each poly body as a conductor, so every
    segment shorts its two terminals.
    """
    resistors = [d for d in devices if d.kind == "res"]
    if len(resistors) != 2:
        raise RuntimeError(f"expected two load resistors, got {len(resistors)}")
    rlp, rln = resistors  # Xrlp -> pop, Xrln -> pon (comparator.spice order)

    r_width = int(round(rlp.params["w"] * 1e9))
    r_length = int(round(rlp.params["l"] * 1e9)) // 2  # two series segments

    # A B B A: segment 1 of P, segment 1 of N, segment 2 of N, segment 2 of P.
    # Both resistors' centroids then coincide with the group's own axis.
    order = [
        (rlp, 0, (rlp.nets[0], f"{prefix}res_mid_p")),
        (rln, 0, (rln.nets[0], f"{prefix}res_mid_n")),
        (rln, 1, (f"{prefix}res_mid_n", rln.nets[1])),
        (rlp, 1, (f"{prefix}res_mid_p", rlp.nets[1])),
    ]

    x = block.row_x1 + place.NWELL_KEEPOUT
    merges: list[tuple[str, str]] = []
    for _dev, _seg, (net_a, net_b) in order:
        column = place.draw_poly_resistor(
            cell, layers, x, block.row_y0, r_width, r_length
        )
        block.channel.drop(net_a, column.a_x, column.riser_y)
        block.channel.drop(net_b, column.b_x, column.riser_y)
        merges.append((net_a, net_b))
        x += column.width
    return merges


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
    if info["merges"]:
        header += [
            "*   - the two 150 kohm p+ poly load resistors are drawn but are NOT",
            "*     extractable devices: the deck has no resistor device class, so",
            "*     each body extracts as a Poly2 conductor and shorts its own",
            "*     terminals. This reference applies the same merge, which is why",
            "*     `pop`/`pon` do not appear -- they collapse onto `vdd`. The",
            "*     companion COMPARATOR_NORES case is what checks that the preamp",
            "*     outputs reach the right latch inputs.",
        ]
    else:
        header += [
            "*   - the load resistor bodies are NOT drawn in this cell, on",
            "*     purpose: with them drawn, the deck's lack of a resistor device",
            "*     class shorts `pop`/`pon` onto `vdd` and LVS stops being able to",
            "*     tell the two preamp outputs apart. This case keeps them",
            "*     distinct so the preamp-to-latch connectivity is genuinely",
            "*     verified. The full COMPARATOR cell carries the resistors.",
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
        print(
            f"wrote {key}.gds  transistors={len(info['devices'])}  "
            f"{box.width() * geo.DBU_UM:.1f} x {box.height() * geo.DBU_UM:.1f} um "
            f"= {geo.area_um2(box):.0f} um^2"
        )


if __name__ == "__main__":
    main()
