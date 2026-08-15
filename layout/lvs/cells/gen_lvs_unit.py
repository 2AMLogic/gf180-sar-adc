#!/usr/bin/env python3
"""Generate `lvs_unit.gds` -- the trivial single-device proof cell for the
gf180mcu LVS bring-up (issue #51).

WHAT THIS IS
------------
One NMOS-style switch device drawn on the layers `klt extract`'s gf180mcu
`ExtractionDeck` reads (Comp 22/0, Poly2 30/0, Contact 33/0, Metal1 34/0),
**plus Metal1 pin labels on 34/10** ("S"/"D"/"G") -- the piece the DRC
bring-up's `sw_unit` cell does not carry, and gf180mcu's `EXTRACTION_DECK`
needs for net naming (`klayout_tools/decks/gf180mcu.py`,
`metal_labels=((34, 10),)`).

WHY A SIBLING CELL AND NOT AN EXTENSION OF `sw_unit`
-----------------------------------------------------
Issue #51 offered either option. `sw_unit` (`../../drc/cells/gen_sw_unit.py`)
carries two seeded DRC violations for the DRC bring-up (a too-tight
source-contact pitch and a free-floating poly2 stub near the gate head) --
neither is relevant to a connectivity proof, and the floating poly2 stub in
particular is actively unwelcome here: it is a poly shape that touches no
contact and no other poly, so `klt extract`'s connectivity graph turns it
into its own tiny disconnected net with no device terminals, which would
show up as a spurious, hard-to-explain extra net on the layout side of every
LVS comparison. Rather than have one cell's docstring carry two unrelated
purposes (DRC seeding vs. LVS pin labeling) and have to explain why a DRC
seed is inert for LVS, this is a separate, purpose-built cell: clean
geometry (no seeded DRC violations -- DRC is not what this cell proves),
plus the Metal1 pin labels the DRC cell never needed.

WHY BUILT WITH klayout.db AND NOT A `klt` VERB
----------------------------------------------
Same reason as `sw_unit`: `klt` has no layout-generation verb (`klt gen` is
scoped to PCells, upstream epic 2AMLogic/klayout-tools#152, and evaluated
against this exact need -- see ../../README.md's friction log). So the cell
is built directly against the pip `klayout` package's batch database API.

DATABASE UNIT
-------------
Written at the KLayout default dbu of 0.001 um (1 nm), same convention as
`sw_unit.gds` and for the same reason: `klt`'s decks (DRC and extraction
alike) author their thresholds/geometry assumptions in nanometres.

Run:

    python3 gen_lvs_unit.py [-o lvs_unit.gds]

Needs the pip `klayout` package (`pip install klayout`); `run_lvs.py`
resolves an interpreter that has it automatically.
"""

from __future__ import annotations

import argparse
import os
import sys

import klayout.db as kdb

# `layout/` is a plain directory, not an installed package, and this script
# is run as `python3 gen_lvs_unit.py` (sys.path[0] is this cell's own
# directory), so the shared `klt_env` module -- two directories up -- has to
# be put on the path explicitly, same pattern `run_lvs.py`/`run_drc.py` use.
_LAYOUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _LAYOUT_DIR not in sys.path:
    sys.path.insert(0, _LAYOUT_DIR)

from klt_env import save_options  # noqa: E402  (import follows the sys.path setup above)

DBU_UM = 0.001  # 1 nm; every coordinate below is in nanometres.

CELL_NAME = "LVS_UNIT"

# gf180mcu layers `ExtractionDeck` reads for this deck (layer/datatype), per
# `klayout_tools/decks/gf180mcu.py`'s `EXTRACTION_DECK`.
L_COMP = (22, 0)
L_POLY2 = (30, 0)
L_CONTACT = (33, 0)
L_METAL1 = (34, 0)
L_METAL1_LABEL = (34, 10)  # text/label purpose -- what EXTRACTION_DECK names nets from

LAYER_NAMES = {
    L_COMP: "Comp",
    L_POLY2: "Poly2",
    L_CONTACT: "Contact",
    L_METAL1: "Metal1",
    L_METAL1_LABEL: "Metal1.label",
}

# ---------------------------------------------------------------------------
# What this cell is expected to extract as, kept here (not just in
# cells.json) so the generator's own claim about its geometry is next to the
# geometry that makes it true. Keep in sync with cells.json.
# ---------------------------------------------------------------------------
EXPECTED_DEVICE_CLASS = "nfet"
EXPECTED_PIN_NAMES = {"S", "D", "G", "VSUBS"}


def build() -> kdb.Layout:
    layout = kdb.Layout()
    layout.dbu = DBU_UM
    top = layout.create_cell(CELL_NAME)

    def layer(spec: tuple[int, int]) -> int:
        idx = layout.layer(*spec)
        layout.set_info(idx, kdb.LayerInfo(spec[0], spec[1], LAYER_NAMES[spec]))
        return idx

    comp = layer(L_COMP)
    poly2 = layer(L_POLY2)
    contact = layer(L_CONTACT)
    metal1 = layer(L_METAL1)
    metal1_label = layer(L_METAL1_LABEL)

    # --- active island -------------------------------------------------
    # No Nwell anywhere in this cell, so the entire island is NMOS active
    # (`ExtractionDeck`: NMOS is `active - nwell`).
    top.shapes(comp).insert(kdb.Box(0, 0, 3000, 1200))

    # --- gate -------------------------------------------------------------
    # A clean 0.28 um stripe crossing the active island (no neighbouring
    # poly2 shape anywhere in this cell -- unlike `sw_unit`, nothing here is
    # a seeded DRC violation), widening into a contact head above the
    # island for the gate contact's poly2 enclosure.
    top.shapes(poly2).insert(kdb.Box(1400, -400, 1680, 1200))
    top.shapes(poly2).insert(kdb.Box(1290, 1200, 1790, 1800))

    # --- contacts -----------------------------------------------------------
    # One contact per terminal -- this cell proves connectivity, not DRC
    # spacing, so there is no reason to pack multiple contacts per net the
    # way `sw_unit` does to seed a spacing violation.
    top.shapes(contact).insert(kdb.Box(160, 490, 380, 710))  # source
    top.shapes(contact).insert(kdb.Box(2620, 490, 2840, 710))  # drain
    top.shapes(contact).insert(kdb.Box(1420, 1400, 1640, 1620))  # gate

    # --- metal1 pads + pin labels --------------------------------------
    # Each pad is named by a Metal1.label (34/10) text shape placed inside
    # its own pad footprint -- `EXTRACTION_DECK.metal_labels` reads exactly
    # this layer/purpose to name the net the pad's Metal1 shape belongs to.
    source_pad = kdb.Box(60, 390, 480, 810)
    drain_pad = kdb.Box(2520, 390, 2940, 810)
    gate_pad = kdb.Box(1330, 1330, 1750, 1690)
    top.shapes(metal1).insert(source_pad)
    top.shapes(metal1).insert(drain_pad)
    top.shapes(metal1).insert(gate_pad)

    top.shapes(metal1_label).insert(kdb.Text("S", kdb.Trans(source_pad.center())))
    top.shapes(metal1_label).insert(kdb.Text("D", kdb.Trans(drain_pad.center())))
    top.shapes(metal1_label).insert(kdb.Text("G", kdb.Trans(gate_pad.center())))

    # No geometry names the body terminal: this curated deck has no distinct
    # substrate-tap layer, so the NMOS body is tied to the deck's global
    # `substrate_net` ("vsubs") rather than derived from drawn geometry --
    # see ../../README.md "Documented gf180mcu extraction approximations".

    return layout


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(here, "lvs_unit.gds"),
        help="output GDSII path (default: lvs_unit.gds beside this script)",
    )
    args = parser.parse_args()

    layout = build()
    assert layout.dbu == DBU_UM, f"dbu drifted to {layout.dbu}"
    layout.write(args.output, save_options())
    print(f"wrote {args.output} (dbu={layout.dbu} um, cell={CELL_NAME})")


if __name__ == "__main__":
    main()
