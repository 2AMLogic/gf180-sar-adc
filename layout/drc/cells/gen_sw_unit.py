#!/usr/bin/env python3
"""Generate `sw_unit.gds` -- the trivial single-device proof cell for the
gf180mcu DRC bring-up (issue #15).

WHAT THIS IS
------------
One NMOS-style switch device drawn on the four layers the `klt drc`
gf180mcu deck actually checks (Comp 22/0, Poly2 30/0, Contact 33/0,
Metal1 34/0), plus **two deliberately seeded rule violations** so the
bring-up proves the report catches something rather than merely running.

It is a *DRC proof cell*, not a taped-out device: the geometry is chosen to
exercise the deck, not to be an optimal or even sensible switch. Nothing
downstream should treat it as the block's real switch layout.

WHY BUILT WITH klayout.db AND NOT A `klt` VERB
----------------------------------------------
`klt` has no layout-generation verb (the `klt gen` work is upstream epic
2AMLogic/klayout-tools#152 and is not in the pinned CLI this repo drives).
So the cell is built directly against the pip `klayout` package's batch
database API, following the pattern of klayout-tools' own
`examples/drc/generate.py` -- same idea, gf180mcu layers instead of sky130.

The generator is committed, not just the GDS, so the proof is reproducible
if the upstream deck's rule set changes: regenerate, re-run, mint a new
evidence record (see ../../README.md).

DATABASE UNIT
-------------
Written at the KLayout default dbu of 0.001 um (1 nm), so every integer
coordinate below is a nanometre. This matters: the `klt` release this
bring-up was run against authors its deck thresholds in nanometres and (in
that release) does *not* rescale them by the stream's dbu -- a dbu drift
would silently change what "passing" means. The generator asserts the dbu
rather than trusting the default.

Run:

    python3 gen_sw_unit.py [-o sw_unit.gds]

Needs the pip `klayout` package (`pip install klayout`); `run_drc.py`
resolves an interpreter that has it automatically.
"""

from __future__ import annotations

import argparse
import os

import klayout.db as kdb

DBU_UM = 0.001  # 1 nm; every coordinate below is in nanometres.

CELL_NAME = "SW_UNIT"

# gf180mcu drawn layers (layer/datatype), per the deck's own layer table.
L_COMP = (22, 0)
L_POLY2 = (30, 0)
L_CONTACT = (33, 0)
L_METAL1 = (34, 0)

LAYER_NAMES = {
    L_COMP: "Comp",
    L_POLY2: "Poly2",
    L_CONTACT: "Contact",
    L_METAL1: "Metal1",
}

# ---------------------------------------------------------------------------
# Seeded violations -- the point of the cell.
#
# Both are ordinary layout mistakes a real switch cell could plausibly carry,
# placed on the device itself rather than as free-floating scrap shapes, so
# the report's bbox actually points at a feature.
#
#   1. contact.space.1 (0.25 um min, DRM CO.2a): the source terminal is drawn
#      as a two-contact row on a 0.20 um gap instead of >= 0.25 um.
#   2. poly2.space.1   (0.24 um min, DRM PL.3a): a neighbouring poly2 stub
#      (the kind a routing channel or an abutted second device would bring)
#      sits 0.20 um from the gate's contact head instead of >= 0.24 um.
#
# `run_drc.py` asserts this exact rule->count mapping against the JSON
# report and fails the run if it does not match, so a deck change upstream
# that silently stops catching these cannot pass as a green bring-up.
# Keep in sync with cells.json.
# ---------------------------------------------------------------------------
SEEDED_VIOLATIONS = {
    "contact.space.1": 1,
    "poly2.space.1": 1,
}


def save_options() -> kdb.SaveLayoutOptions:
    """GDSII writer options that make the output byte-reproducible.

    KLayout stamps BGNLIB/BGNSTR with the current wall-clock time by
    default, so two runs of an otherwise identical generator produce two
    different files. Suppressing the timestamps makes the committed GDS
    hash a real integrity check: regenerate and `shasum -a 256` must match
    the value recorded alongside the DRC report.
    """
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


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

    # --- active island -----------------------------------------------------
    # 3.0 x 1.2 um; comfortably over comp.width.1 (0.22 um). Single shape, so
    # comp.space.1 has no pair to check.
    top.shapes(comp).insert(kdb.Box(0, 0, 3000, 1200))

    # --- gate ---------------------------------------------------------------
    # 0.28 um stripe (>= poly2.width.1 0.18 um) crossing the active island,
    # over-hanging it top and bottom, widening into a 0.50 um contact head
    # above the island so the gate contact gets its 0.07 um poly2 enclosure
    # (poly2.enclosing.contact.1, DRM CO.3).
    top.shapes(poly2).insert(kdb.Box(1400, -400, 1680, 1200))
    top.shapes(poly2).insert(kdb.Box(1290, 1200, 1790, 1800))

    # SEED 2: neighbouring poly2 stub 0.20 um from the contact head's right
    # edge -> violates poly2.space.1 (0.24 um). Placed above the active
    # island and clear of every contact, so it perturbs exactly one rule.
    top.shapes(poly2).insert(kdb.Box(1990, 1200, 2270, 1800))

    # --- contacts -----------------------------------------------------------
    # Every contact is the DRM's fixed 0.22 x 0.22 um square (contact.width.1)
    # and sits >= 0.07 um inside its comp/poly2 landing (comp.enclosing
    # .contact.1 / poly2.enclosing.contact.1).
    #
    # SEED 1: the source row's two contacts are 0.20 um apart -> violates
    # contact.space.1 (0.25 um).
    top.shapes(contact).insert(kdb.Box(200, 490, 420, 710))  # source, left
    top.shapes(contact).insert(kdb.Box(620, 490, 840, 710))  # source, right
    top.shapes(contact).insert(kdb.Box(2200, 490, 2420, 710))  # drain
    top.shapes(contact).insert(kdb.Box(1420, 1400, 1640, 1620))  # gate

    # --- metal1 straps ------------------------------------------------------
    # All three are well over metal1.width.1 (0.23 um) and pairwise well over
    # metal1.space.1 (0.23 um) -- this layer is the cell's clean control, the
    # counterpart of the clean met1 bar in klayout-tools' own sky130 example.
    top.shapes(metal1).insert(kdb.Box(100, 390, 940, 810))  # source
    top.shapes(metal1).insert(kdb.Box(2100, 390, 2520, 810))  # drain
    top.shapes(metal1).insert(kdb.Box(1330, 1330, 1750, 1690))  # gate

    return layout


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(here, "sw_unit.gds"),
        help="output GDSII path (default: sw_unit.gds beside this script)",
    )
    args = parser.parse_args()

    layout = build()
    assert layout.dbu == DBU_UM, f"dbu drifted to {layout.dbu}"
    layout.write(args.output, save_options())
    print(f"wrote {args.output} (dbu={layout.dbu} um, cell={CELL_NAME})")


if __name__ == "__main__":
    main()
