#!/usr/bin/env python3
"""Draw the decode-bank shared-source/drain fold candidate (issue #936).

POST-ADOPTION NOTE (DR-0050, issue #940): the fold this script measured is
now the RATIFIED topology -- `design/adc-top/adc_top.spice` states
`adc_tgate_f` itself and `layout/adc-top/gen_adc_top.py` draws the fold
unconditionally. Re-running this script against the adopted netlist
regenerates streams byte-identical to the production ones (the substitution
step is a detected no-op); the script is kept as the evidence generator its
records cite, and as the recipe for the pre-adoption substitution at the
commits those records name. It no longer measures anything the production
generator does not.

WHAT THIS MEASURES
-------------------
#668's null result left the decode-bank levers untested: it folded bank
devices into multi-finger columns WITHOUT diffusion sharing and measured
every point LARGER ("folding divides height and multiplies X"), then named
what it did not test -- "a real shared source/drain fold". This candidate
is exactly that lever, at the one ratio the floorplan can absorb:

    every decode-bank T-gate PMOS (wp=20u, the device that sets the bank
    row height at 21.3 um) becomes two wp=10u fingers drawn as one ABUTTING
    shared-source/drain pair (`lib/place.draw_devices(...,
    fold_shared_sd=True)`), so the row height follows the bank's 10 um NMOS
    columns down to 11.3 um.

The trade is row WIDTH (+2.48 um per folded pair, 36 pairs per bank), which
this floorplan has measured slack for: the banks (480.7 um) end well left
of the analog core's right edge (587.8 um, set by the comparator), and the
BLOCK width is set by neither -- it is set by the SAR-reserve column at
662.2 um. The height, by contrast, is stack height (two banks below the
arrays), so every um of it crosses the full 671.7 um width. The economy
record (`../economy/records/`) ranks this lever first among the decode-bank
levers on that arithmetic; this script supplies the measured half.

THE CANDIDATE NETLIST
----------------------
Same technique `gen_acq_leg_candidate.py` uses: the ratified
`design/adc-top/adc_top.spice` with ONE local change -- the four bank
T-gate lines of `adc_cdac_cell` (Xsi/Xsr/Xsh/Xsl) call a new
`adc_tgate_f` subckt that states the PMOS as TWO parallel wp=10u devices.
The top-plate switch's own `adc_tgate` (line 97) is untouched: its row is
not height-critical (it sits beside the 114 um arrays), so folding it would
only push the comparator -- and with it the analog core's right edge --
rightward for nothing.

The layout side is `gen_adc_top.build(..., bank_fold_shared_sd=True)`,
which folds consecutive identical PMOS twins into abutting mirrored pairs.
The LVS reference is generated from the SAME candidate netlist, so LVS
proves the drawn geometry realises the folded design exactly as the
ratified flow's claim shape does -- and the production stream
(`main()`, flag off) stays byte-identical to the committed files.

OUTPUTS (layout/adc-top/candidates/bank-fold-2x/)
--------------------------------------------------
    adc_top.candidate.spice    candidate design netlist (provenance)
    adc_top.gds / adc_block.gds        candidate-geometry layout
    adc_top.ref.spice / adc_block.ref.spice   flat LVS reference
    adc_top.lvs.json / adc_block.lvs.json     `klt lvs` request documents
    area.json                  as-drawn area tally, same schema as production

Verification (run by hand against the PINNED toolchain, not by this script
-- it only draws; the commands and their results live in the records):

    klt drc   <outdir>/{adc_top,adc_block}.gds --deck gf180mcu --format json
    klt extract <outdir>/{adc_top,adc_block}.gds --deck gf180mcu \\
        -o <outdir>/{adc_top,adc_block}.spice --format json
    klt lvs   <outdir>/{adc_top,adc_block}.lvs.json --format json
    klt economy <outdir>/adc_block.gds --top ADC_BLOCK --format json
              (economy is 0.8.0+, a measurement not a gate -- see
               economy/records/ for the pinned-versus-measured split)

Usage::

    uvx --from "klayout-tools==0.6.0" --with "klayout==0.30.10" \\
        python layout/adc-top/candidates/gen_bank_fold_candidate.py \\
        [--outdir DIR] [--force]
"""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADC_TOP_DIR = os.path.dirname(HERE)  # layout/adc-top

#: The four bank T-gate lines inside `adc_cdac_cell`, exactly as
#: `design/adc-top/gen_adc_top.py` emits them. The top-plate switch's own
#: `adc_tgate` call (in `adc_tp_sw`) is textually distinct and untouched.
BANK_TGATE_LINES = [
    "Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn=10u wp=20u",
    "Xsr vcm  bp gn_rel gp_rel vdd adc_tgate wn=10u wp=20u",
    "Xsh vref bp gn_hi  gp_hi  vdd adc_tgate wn=10u wp=20u",
    "Xsl vss  bp gn_lo  gp_lo  vdd adc_tgate wn=10u wp=20u",
]

#: The folded T-gate: identical port list and NMOS, the PMOS stated as two
#: parallel half-width devices (20u -> 2 x 10u). Literal widths -- the
#: candidate is one specific ratio, not a parameterised sweep, so nothing
#: downstream depends on expression evaluation.
ADC_TGATE_F = """\
* Folded T-gate (issue #936 candidate): the PMOS as two parallel wp=10u
* fingers -- the netlist side of the shared-source/drain layout fold.
.subckt adc_tgate_f vin vout gn gp vdd
XN  vin gn vout 0   nfet_03v3 w=10u l=0.28u
XP1 vin gp vout vdd pfet_03v3 w=10u l=0.28u
XP2 vin gp vout vdd pfet_03v3 w=10u l=0.28u
.ends adc_tgate_f"""


def _folded_line(line: str) -> str:
    head = line.split(" adc_tgate ")[0]
    return f"{head} adc_tgate_f"


def candidate_netlist_text(nl) -> tuple[str, str]:
    """The ratified `design/adc-top/adc_top.spice` -- with the four bank
    T-gate calls pointed at the folded subckt if they are not already
    (DR-0050 adopted the fold into the design netlist itself, so the
    substitution is now normally a no-op). Returns `(text, source)`."""
    design = nl.design_dir(ADC_TOP_DIR)
    source = os.path.join(design, "adc-top", "adc_top.spice")
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    if ".subckt adc_tgate_f " in text:
        # DR-0050: the ratified design netlist already states the folded
        # bank T-gate. The candidate IS the production netlist now; there
        # is nothing to substitute and attempting it would fail the anchor
        # checks below on purpose.
        return text, source
    for anchor in BANK_TGATE_LINES:
        hits = text.count(anchor)
        if hits != 1:
            raise SystemExit(
                f"error: expected exactly one {anchor!r} in {source}, found "
                f"{hits} -- design/adc-top/gen_adc_top.py's cell emission "
                "has changed and this substitution is no longer anchored"
            )
        text = text.replace(anchor, _folded_line(anchor))
    # Insert the folded subckt right after the original adc_tgate block's
    # `.ends`, so the library keeps the two definitions adjacent.
    ends_anchor = ".ends adc_tgate\n"
    hits = text.count(ends_anchor)
    if hits != 1:
        raise SystemExit(
            f"error: expected exactly one {ends_anchor!r} in {source}, "
            f"found {hits}"
        )
    text = text.replace(ends_anchor, ends_anchor + "\n" + ADC_TGATE_F + "\n")
    return text, source


def _load_layout_generator():
    """Import `layout/adc-top/gen_adc_top.py` by path (its directory name,
    `adc-top`, is not a legal package identifier)."""
    sys.path.insert(0, ADC_TOP_DIR)
    path = os.path.join(ADC_TOP_DIR, "gen_adc_top.py")
    spec = importlib.util.spec_from_file_location("gen_adc_top_bank_fold", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Draw the decode-bank shared-S/D fold candidate (#936)."
    )
    ap.add_argument(
        "--outdir", default=os.path.join(HERE, "bank-fold-2x"),
        help="output dir; must be a NEW or candidate-owned directory strictly "
             "under layout/adc-top/candidates/ (default bank-fold-2x)",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="allow writing into a directory that already holds klt extract "
             "evidence (adc_top.spice); never use on committed historical dirs",
    )
    args = ap.parse_args(argv)
    outdir = os.path.abspath(args.outdir)
    if (os.path.commonpath([outdir, HERE]) != HERE or outdir == HERE
            or os.path.basename(outdir) in ("records",)):
        raise SystemExit(
            f"error: outdir {outdir} must be a subdirectory of {HERE} "
            "(candidate outputs never overwrite production or historical "
            "evidence)"
        )
    if os.path.exists(os.path.join(outdir, "adc_top.spice")) and not args.force:
        raise SystemExit(
            f"error: {outdir} already holds committed klt-extract evidence "
            "(adc_top.spice); refusing to overwrite. Pass a fresh --outdir "
            "to regenerate."
        )

    g = _load_layout_generator()
    nl = g.nl
    geo = g.geo

    os.makedirs(outdir, exist_ok=True)
    text, source = candidate_netlist_text(nl)
    candidate_path = os.path.join(outdir, "adc_top.candidate.spice")
    with open(candidate_path, "w", encoding="utf-8") as fh:
        fh.write(
            "* GENERATED by layout/adc-top/candidates/gen_bank_fold_candidate.py\n"
            f"* from {os.path.relpath(source, ADC_TOP_DIR)}: the four BANK T-gate\n"
            "* lines (Xsi/Xsr/Xsh/Xsl of adc_cdac_cell) now call adc_tgate_f, whose\n"
            "* PMOS is two parallel wp=10u fingers -- the netlist side of the\n"
            "* shared-source/drain layout fold (issue #936). The top-plate switch's\n"
            "* adc_tgate is untouched. Not the ratified design netlist; do not edit.\n"
            "*\n" + text
        )

    subckts = nl.parse(candidate_path)
    g.block_subckt(subckts)
    comparator_subckts = nl.parse(
        os.path.join(nl.design_dir(ADC_TOP_DIR), "comparator", "comparator.spice")
    )

    for key, cell_name, cmp_subckts in (
        ("adc_top", g.CELL_NAME, None),
        ("adc_block", g.BLOCK_CELL_NAME, comparator_subckts),
    ):
        # No fold flag post-DR-0050: the layout generator draws the fold
        # unconditionally (the unfolded stream no longer has a netlist).
        layout, info = g.build(subckts, cmp_subckts, cell_name=cell_name)
        assert layout.dbu == geo.DBU_UM, f"dbu drifted to {layout.dbu}"
        geo.assert_on_grid(layout)
        geo.assert_contacts_exact(layout)
        layout.write(os.path.join(outdir, f"{key}.gds"), geo.save_options())
        g.write_reference(
            os.path.join(outdir, f"{key}.ref.spice"), info, cell_name, key
        )
        g.write_request(os.path.join(outdir, f"{key}.lvs.json"), cell_name, key)
        box = layout.cell(cell_name).bbox()
        print(
            f"wrote {key}.gds  transistors={info['transistor_count']}  "
            f"caps={info['cap_count']}  "
            f"{box.width() * geo.DBU_UM:.1f} x {box.height() * geo.DBU_UM:.1f} um "
            f"= {geo.area_um2(box) / 1e6:.5f} mm^2"
        )
        tally = {
            "_comment": [
                "As-drawn area tally for the bank-fold candidate layout,",
                "written by gen_bank_fold_candidate.py (same schema as",
                "layout/adc-top/area.json, which this does not replace).",
            ],
            "areas_um2": info["areas"],
            "dimensions_um": info["dimensions_um"],
            "transistor_count": info["transistor_count"],
            "unit_cap_device_count": info["cap_count"],
        }
        with open(os.path.join(outdir, "area.json"), "w", encoding="utf-8") as fh:
            import json

            json.dump(tally, fh, indent=2, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
