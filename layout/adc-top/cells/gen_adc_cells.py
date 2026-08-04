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
2.7136 um, `C_u` = 17.24 fF). The weighted positions the real array needs
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

#: `C_u` unit capacitor, `spec/cdac-sizing-memo.md` Sec 4 / the density law
#: quoted in `design/adc-top/adc_top.spice`: 17.24 fF at 2.7136 um square.
UNIT_CAP_NM = 2714  # 2.7136 um, rounded to the 1 nm database grid

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
        "role": "one CDAC weighted-position cell (adc_cdac_cell): FOUR "
        "bottom-plate decode T-gates (DR-0014's fourth, one-hot leg to "
        "`vin` included), their four local drivers, and one unit MiM "
        "capacitor footprint",
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
        cw = int(round(caps[0].params["w"] * 1e9))
        cl = int(round(caps[0].params["l"] * 1e9))
        row_h = max(d.w_nm for d in devices if d.is_mos)
        geo.draw_mim_cap(
            top,
            layers,
            (block.row_x0 + block.row_x1) // 2 - cw // 2,
            block.row_y0 + row_h + 1000,
            cw,
            cl,
        )

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
    mos = [d for d in info["devices"] if d.is_mos]
    pins = sorted({*spec["pins"], nl.SUBSTRATE_NET}, key=str.lower)
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
        "*   - the MiM capacitor is absent: the deck reads none of the MiM",
        "*     layers and has no capacitor device class at all.",
        "*",
        f"* Runnable by hand:  klt lvs layout/adc-top/cells/{spec['cell'].lower()}"
        ".lvs.json --format json",
    ]
    nl.write_reference(path, spec["cell"], mos, pins, block.body_net, header)
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
