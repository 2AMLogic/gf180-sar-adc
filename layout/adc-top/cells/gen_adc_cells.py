#!/usr/bin/env python3
"""Generate every leaf cell of the `design/adc-top/` block layout, plus the
flat SPICE reference and `klt lvs` request document for each.

Run with no arguments (which is how `layout/lvs/run_lvs.py --regen` and
`layout/drc/run_drc.py --regen` invoke it) and it writes, beside this file:

    adc_drv.gds / .ref.spice / .lvs.json          local T-gate driver
    adc_tgate.gds / .ref.spice / .lvs.json        CDAC bottom-plate T-gate
    adc_tgate_dum.gds / .ref.spice / .lvs.json    superseded input sampling
                                                   switch (standalone only)
    adc_cdac_cell.gds / .ref.spice / .lvs.json    one weighted CDAC cell
    adc_tp_sw.gds / .ref.spice / .lvs.json        top-plate V_cm switch
                                                   (DR-0014)

Every device, every W/L, and every net comes from
`design/adc-top/adc_top.spice`, parsed and flattened by `../lib/netlist.py`
-- nothing here re-types the design. See that module's docstring for what
that does and does not let LVS prove.

The `adc_cdac_cell` here is drawn at the array's *unit* weight (`cw`/`cl` =
2.7136 um, `C_u` = 17.24 fF), and it is the ONE cell in this repo where the
MiM capacitor is drawn as a fully-wired, extraction-recognised device: both
plates are connected (Via4 up to a Metal5 pin, Via3/Via2/Via1 down onto the
`bp` trunk) and `CAP_MK`/`MIM_L_MK` are drawn, so `klt extract` reports a
`cap_mim_2f0_m4m5_noshield` and `klt lvs` compares it (issue #70). The tiled
arrays in `gen_adc_top.py` are NOT yet in that state -- their per-weight
bottom-plate interconnect is still undrawn -- see ../README.md.

The weighted positions the real array needs
are NOT drawn as one big capacitor per weight: `gen_adc_top.py` tiles `m`
unit capacitors per weight in a common-centroid pattern, which is what
`layout/floorplan-matching-plan.md` Sec 1.3 requires and what the
schematic's own `m=`-multiplicity note (`spec/cdac-sizing-memo.md` Sec 5.4)
says the drawn array implements.

`adc_tp_sw` (DR-0014, issue #66) is drawn here too, standalone: it is the
per-side top-plate `V_cm` switch `gen_adc_top.py`'s block composes two of,
but the leaf cell itself -- one `adc_drv` + one `adc_tgate` -- is exercised
and LVS-matched on its own like every other cell in this file.
`adc_tgate_dum` (the superseded dedicated input sampling switch) stays here
too even though `gen_adc_top.py`'s `adc_top`/`adc_block` composition no
longer instantiates it: the CELL DEFINITION is still standalone-drawable and
LVS-matchable against `design/adc-top/adc_top.spice`'s own (still-present,
DR-0014 comment-marked) `.subckt adc_tgate_dum`, and this repo keeps proving
what it still defines.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lib import geometry as geo  # noqa: E402
from lib import netlist as nl  # noqa: E402
from lib import place  # noqa: E402

#: `C_u` unit capacitor, `spec/cdac-sizing-memo.md` Sec 4 / DR-0019 / the
#: density law quoted in `design/adc-top/adc_top.spice`: 35.6528 fF at
#: 4.0 um square (was 17.24 fF at 2.7136 um before DR-0019).
UNIT_CAP_NM = 4000  # 4.0 um, on the 1 nm database grid

#: Cells this script builds: the subcircuit to flatten out of
#: `adc_top.spice`, how its ports map onto layout net names, and which nets
#: carry a Metal1 (34/10) pin label.
LEAF_CELLS: dict[str, dict] = {
    "adc_drv": {
        "cell": "ADC_DRV",
        "subckt": "adc_drv",
        "ports": {"a": "a", "y": "y", "vdd": "vdd", "vss": "vss"},
        "pins": ["a", "y", "vdd", "vss"],
        "role": "local T-gate driver (adc_drv): the CMOS inverter that makes "
        "each decode leg's complementary PMOS gate",
    },
    "adc_tgate": {
        "cell": "ADC_TGATE",
        "subckt": "adc_tgate",
        "ports": {
            "vin": "vin", "vout": "vout", "gn": "gn", "gp": "gp", "vdd": "vdd"
        },
        "pins": ["vin", "vout", "gn", "gp"],
        "role": "CDAC bottom-plate decode T-gate (adc_tgate, 10u/20u)",
    },
    "adc_tgate_dum": {
        "cell": "ADC_TGATE_DUM",
        "subckt": "adc_tgate_dum",
        "ports": {
            "vin": "vin", "vout": "vout", "clk": "clk", "clkb": "clkb", "vdd": "vdd"
        },
        "pins": ["vin", "vout", "clk", "clkb"],
        "role": "input sampling switch (adc_tgate_dum, 40u/80u main + 7/16 "
        "charge-injection-compensation dummies -- DR-0007 / DR-0013)",
        # DR-0013 requires the dummy to sit symmetrically about the main
        # device it compensates. `device_order` below is what enforces that
        # in the drawn row: dummy, main, main, dummy, so each dummy abuts
        # its own main device and the pair is mirror-symmetric about the
        # NMOS/PMOS boundary. See ../README.md.
        "device_order": ["XDN", "XN", "XP", "XDP"],
    },
    "adc_cdac_cell": {
        "cell": "ADC_CDAC_CELL",
        "subckt": "adc_cdac_cell",
        "ports": {
            "top": "top", "vin": "vin", "vref": "vref", "vcm": "vcm", "vss": "vss",
            "vdd": "vdd", "gn_in": "gn_in", "gn_rel": "gn_rel", "gn_hi": "gn_hi",
            "gn_lo": "gn_lo",
        },
        "params": {"cw": UNIT_CAP_NM * 1e-9, "cl": UNIT_CAP_NM * 1e-9},
        "pins": [
            "bp", "vin", "vcm", "vref", "vss", "vdd",
            "gn_in", "gn_rel", "gn_hi", "gn_lo",
        ],
        #: The MiM top plate is reached on Metal5, not Metal1, so its pin
        #: label is drawn separately from the channel's Metal1 pins -- but it
        #: is a pin of the extracted cell exactly like the other ten.
        "metal5_pins": ["top"],
        "role": "one CDAC weighted-position cell (adc_cdac_cell): FOUR "
        "bottom-plate decode T-gates (DR-0014's fourth, one-hot leg to "
        "`vin` included), their four local drivers, and one unit MiM "
        "capacitor -- drawn as a RECOGNISED device (CAP_MK/MIM_L_MK) with "
        "both plates wired, so `klt extract` reports it and `klt lvs` "
        "checks it",
        "draw_cap": True,
    },
    "adc_tp_sw": {
        "cell": "ADC_TP_SW",
        "subckt": "adc_tp_sw",
        "ports": {
            "top": "top", "vcm": "vcm", "gn": "gn", "vdd": "vdd", "vss": "vss",
        },
        "pins": ["top", "vcm", "gn", "vdd", "vss"],
        "role": "top-plate V_cm switch (adc_tp_sw, DR-0014): one local "
        "driver (adc_drv) plus one CDAC-geometry T-gate (adc_tgate) that "
        "opens on the edge into ph3 to release the array's top plate at "
        "the sampling instant. Deliberately NOT dummy-compensated -- see "
        "design/adc-top/adc_top.spice's own comment on this subckt.",
    },
}


def build(spec: dict, subckts: dict) -> tuple[object, dict]:
    """Draw one leaf cell. Returns `(layout, info)`."""
    layout, layers = geo.make_layout()
    top = layout.create_cell(spec["cell"])

    devices = nl.flatten(
        subckts, spec["subckt"], spec["ports"], spec.get("params"), prefix=""
    )
    order = spec.get("device_order")
    if order is not None:
        by_name = {d.path: d for d in devices}
        missing = set(order) ^ set(by_name)
        if missing:
            raise ValueError(f"device_order does not cover {sorted(missing)}")
        devices = [by_name[name] for name in order]

    block = place.draw_devices(
        top, layers, [("nw", devices)], spec["pins"], row_y0=0
    )

    if spec.get("draw_cap"):
        # The unit MiM capacitor sits directly above its own cell's device
        # row (the decode switches for a weighted position follow that
        # position's place in the array tiling -- floorplan plan Sec 1.6),
        # centred on the row so the cell has a single, symmetric footprint.
        caps = [d for d in devices if d.kind == "cap"]
        if len(caps) != 1:
            raise ValueError(f"expected exactly one capacitor, got {len(caps)}")
        cw, cl = caps[0].cap_plate_nm
        foot_w, _foot_h = geo.mim_footprint(cw, cl)
        row_h = max(d.w_nm for d in devices if d.is_mos)
        cap = geo.draw_mim_cap(
            top,
            layers,
            (block.row_x0 + block.row_x1) // 2 - foot_w // 2,
            block.row_y0 + row_h + 1000,
            cw,
            cl,
            device=True,
        )
        # Both plates wired, which is what makes the drawn stack a checkable
        # device rather than decoration: the top plate up through Via4 to a
        # Metal5 pin, the bottom plate down through Via3/Via2/Via1 onto the
        # `bp` trunk the four decode T-gates already share.
        top_net, bottom_net = caps[0].nets[0], caps[0].nets[1]
        geo.label_metal5(top, layers, cap.top_pad, top_net)
        geo.draw_mim_bottom_riser(top, layers, cap, block.trunks[bottom_net])

    info = {
        "cell": spec["cell"],
        "devices": devices,
        "block": block,
        "layers": layers,
    }
    return layout, info


def write_reference(path: str, spec: dict, info: dict) -> list[str]:
    """Write the flat LVS reference for a leaf cell; returns its pin list."""
    block = info["block"]
    include_caps = bool(spec.get("draw_cap"))
    kept = [
        d for d in info["devices"] if d.is_mos or (include_caps and d.kind == "cap")
    ]
    pins = sorted(
        {*spec["pins"], *spec.get("metal5_pins", ()), nl.SUBSTRATE_NET}, key=str.lower
    )
    header = [
        f"* Flat LVS reference for {spec['cell']}.",
        "*",
        "* GENERATED by layout/adc-top/cells/gen_adc_cells.py from",
        f"* design/adc-top/adc_top.spice's `.subckt {spec['subckt']}` -- do not",
        "* edit. See layout/adc-top/lib/netlist.py for why the layout and this",
        "* reference are derived from the same parsed design netlist, and what",
        "* that does and does not let LVS prove.",
        "*",
        "* Deliberate, documented differences from the schematic, each forced by",
        "* `klt extract`'s gf180mcu ExtractionDeck and restated in",
        "* layout/adc-top/README.md:",
        "*   - every NMOS body is on the deck's `vsubs` global, not on the",
        "*     schematic's `0`/`vss`: the curated deck has no tap layer, so a",
        "*     drawn substrate tie cannot name that net;",
        "*   - every PMOS body is on the Nwell island's own (unnamed) net, not",
        "*     on `vdd`: the deck never connects `nwell` to `contact`;",
    ]
    if include_caps:
        header += [
            "*   - the MiM capacitor's value is the EXTRACTION DECK's model of",
            "*     the drawn plate (2.0 fF/um^2 x area) and not the PDK model",
            "*     card's own geometry law, which adds a perimeter/fringe term",
            "*     the deck does not model -- 14.73 fF here vs 17.24 fF in",
            "*     design/adc-top/adc_top.spice, 14.6 % apart, for a plate this",
            "*     layout draws at the ratified 2.7136 um. See",
            "*     layout/adc-top/lib/netlist.py's DECK_MIM_AREA_CAP_F_UM2 and",
            "*     the LVS record: the delta is reported, not tuned away.",
        ]
    else:
        header += [
            "*   - the MiM capacitors are absent: they are drawn without the",
            "*     CAP_MK/MIM_L_MK marker layers the deck recognises a device",
            "*     by, so `klt extract` reports none (layout/adc-top/README.md).",
        ]
    header += [
        "*",
        f"* Runnable by hand:  klt lvs layout/adc-top/cells/{spec['cell'].lower()}"
        ".lvs.json --format json",
    ]
    nl.write_reference(
        path,
        spec["cell"],
        kept,
        pins,
        block.body_net,
        header,
        include_caps=include_caps,
    )
    return pins


def write_request(path: str, spec: dict) -> None:
    name = spec["cell"]
    request = {
        "_comment": [
            f"klt lvs request for {name} -- the extracted layout netlist against",
            "the flat reference generated from design/adc-top/adc_top.spice.",
            "",
            "Both sides are pre-extracted / generated SPICE files rather than klt",
            "lvs's inline-extraction {file, deck} shape, for the reason",
            "layout/lvs/cells/lvs_request_match.json already records: inline",
            "extraction hands the comparer a native-object netlist on one side",
            "and a NetlistSpiceReader-parsed one on the other, which splits the",
            "device class names by case and reports a spurious topology",
            "mismatch. Paths resolve against THIS file's directory.",
            "",
            f"    klt lvs layout/adc-top/cells/{name.lower()}.lvs.json --format json",
        ],
        "layout": {"netlist": f"{name.lower()}.spice", "top": name},
        "reference": {"netlist": f"{name.lower()}.ref.spice", "top": name},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(request, fh, indent=2)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--outdir", default=HERE, help="directory to write the cells into"
    )
    args = parser.parse_args()

    design = nl.design_dir(HERE)
    subckts = nl.parse(os.path.join(design, "adc-top", "adc_top.spice"))

    for key, spec in LEAF_CELLS.items():
        layout, info = build(spec, subckts)
        assert layout.dbu == geo.DBU_UM, f"dbu drifted to {layout.dbu}"
        gds = os.path.join(args.outdir, f"{key}.gds")
        layout.write(gds, geo.save_options())
        pins = write_reference(
            os.path.join(args.outdir, f"{key}.ref.spice"), spec, info
        )
        write_request(os.path.join(args.outdir, f"{key}.lvs.json"), spec)
        box = layout.top_cell().bbox()
        print(
            f"wrote {os.path.basename(gds):<22} "
            f"devices={len([d for d in info['devices'] if d.is_mos]):>3}  "
            f"pins={len(pins)}  "
            f"{box.width() * geo.DBU_UM:.2f} x {box.height() * geo.DBU_UM:.2f} um"
        )


if __name__ == "__main__":
    main()
