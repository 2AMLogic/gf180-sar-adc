#!/usr/bin/env python3
"""Generate `uncovered_layer_probe.gds` -- a negative control for the
gf180mcu DRC bring-up (issue #15).

WHAT THIS IS
------------
A deliberately, grossly illegal layout drawn **entirely on gf180mcu layers
the `klt drc` gf180mcu deck has no rules for**: the MiM capacitor stack
(Metal4 46/0 bottom plate, FuseTop 75/0 top plate, Via4 41/0, Metal5 81/0
strap) and two intermediate routing metals (Metal2 36/0, Metal3 42/0).

Running `klt drc --deck gf180mcu` against it reports **`"status": "clean",
"violation_count": 0`**. That "clean" is the finding, not a pass: the deck
is a curated starter subset (Comp 22/0, Poly2 30/0, Contact 33/0, Metal1
34/0 in the release this bring-up ran against), and a stream drawn only on
layers outside that subset is indistinguishable, in the report, from a
stream that genuinely has no errors.

This cell exists so that fact is *evidence* rather than an assertion, per
CLAUDE.md's "no claim without a testbench". `run_drc.py` asserts the clean
result and fails the run if it ever changes -- which is the useful failure
mode: the day upstream adds MiM/upper-metal coverage, this control goes red
and tells us the gap closed.

The gap is filed generically on the public tracker (tool gap only, no
design content) -- see ../../README.md for the issue links.

WHAT WOULD ACTUALLY BE FLAGGED
------------------------------
Against the gf180mcu PDK's own shipped KLayout deck
(`libs.tech/klayout/drc/rule_decks/mim_b.drc`, MIM option B) the geometry
below breaks at least:

  * MIMTM.1 -- min MiM bottom-plate spacing to bottom-plate metal, 1.2 um:
    drawn at 0.3 um.
  * MIMTM.2 -- min MiM bottom-plate overlap of Via(n-1), 0.4 um: the via
    straddles the bottom-plate edge (negative overlap).
  * MIMTM.3 -- min MiM bottom-plate overlap of top plate: the top plate
    hangs 1.0 um off the bottom plate entirely.

plus sub-minimum Metal2/Metal3 widths (0.05 um drawn against a 0.23 um
class minimum). None of that is reachable through `klt drc`'s gf180mcu
deck today.

Run:

    python3 gen_uncovered_layer_probe.py [-o uncovered_layer_probe.gds]

Needs the pip `klayout` package (`pip install klayout`); `run_drc.py`
resolves an interpreter that has it automatically.
"""

from __future__ import annotations

import argparse
import os
import sys

import klayout.db as kdb

# `layout/` is a plain directory, not an installed package, and this script
# is run as `python3 gen_uncovered_layer_probe.py` (sys.path[0] is this
# cell's own directory), so the shared `klt_env` module -- two directories
# up -- has to be put on the path explicitly, same pattern
# `run_lvs.py`/`run_drc.py` use.
_LAYOUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _LAYOUT_DIR not in sys.path:
    sys.path.insert(0, _LAYOUT_DIR)

from klt_env import save_options  # noqa: E402  (import follows the sys.path setup above)

DBU_UM = 0.001  # 1 nm; every coordinate below is in nanometres.

CELL_NAME = "UNCOVERED_LAYER_PROBE"

# gf180mcu drawn layers, all of them outside the curated `klt drc` deck.
# Numbers cross-checked against the PDK's own KLayout layer properties file
# (libs.tech/klayout/tech/gf180mcu.lyp).
L_VIA4 = (41, 0)
L_METAL4 = (46, 0)
L_FUSETOP = (75, 0)
L_METAL5 = (81, 0)
L_METAL2 = (36, 0)
L_METAL3 = (42, 0)

LAYER_NAMES = {
    L_VIA4: "Via4",
    L_METAL4: "Metal4",
    L_FUSETOP: "FuseTop",
    L_METAL5: "Metal5",
    L_METAL2: "Metal2",
    L_METAL3: "Metal3",
}

# What `klt drc --deck gf180mcu` is expected to report. Zero, on purpose:
# see the module docstring. `run_drc.py` enforces this. Keep in sync with
# cells.json.
SEEDED_VIOLATIONS: dict[str, int] = {}


def build() -> kdb.Layout:
    layout = kdb.Layout()
    layout.dbu = DBU_UM
    top = layout.create_cell(CELL_NAME)

    def layer(spec: tuple[int, int]) -> int:
        idx = layout.layer(*spec)
        layout.set_info(idx, kdb.LayerInfo(spec[0], spec[1], LAYER_NAMES[spec]))
        return idx

    via4 = layer(L_VIA4)
    metal4 = layer(L_METAL4)
    fusetop = layer(L_FUSETOP)
    metal5 = layer(L_METAL5)
    metal2 = layer(L_METAL2)
    metal3 = layer(L_METAL3)

    # --- MiM stack, drawn wrong on every axis that matters ------------------
    # Bottom plate.
    top.shapes(metal4).insert(kdb.Box(0, 0, 5000, 5000))
    # Neighbouring bottom-plate metal only 0.3 um away (MIMTM.1 wants 1.2 um).
    top.shapes(metal4).insert(kdb.Box(5300, 0, 7300, 5000))
    # Top plate hanging 1.0 um clear off the bottom plate (MIMTM.3 wants the
    # top plate enclosed by the virtual bottom plate).
    top.shapes(fusetop).insert(kdb.Box(4800, 200, 6000, 4800))
    # Via straddling the bottom-plate edge (MIMTM.2 wants 0.4 um overlap).
    top.shapes(via4).insert(kdb.Box(-100, 500, 100, 700))
    # Top-plate strap.
    top.shapes(metal5).insert(kdb.Box(4900, 2000, 7000, 3000))

    # --- intermediate routing metals, drawn at 0.05 um ----------------------
    # An order of magnitude under any real Metaln width rule.
    top.shapes(metal2).insert(kdb.Box(0, 6000, 4000, 6050))
    top.shapes(metal3).insert(kdb.Box(0, 6200, 4000, 6250))

    return layout


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(here, "uncovered_layer_probe.gds"),
        help="output GDSII path (default: beside this script)",
    )
    args = parser.parse_args()

    layout = build()
    assert layout.dbu == DBU_UM, f"dbu drifted to {layout.dbu}"
    layout.write(args.output, save_options())
    print(f"wrote {args.output} (dbu={layout.dbu} um, cell={CELL_NAME})")


if __name__ == "__main__":
    main()
