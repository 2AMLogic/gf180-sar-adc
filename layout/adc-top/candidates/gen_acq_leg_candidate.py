#!/usr/bin/env python3
"""Draw the layout candidate for a widened CDAC acquisition-leg T-gate
(issue #248, item 5 of #238's deferred measurements; intermediate width
points: `sim/acq-leg-width-sweep/README.md`).

The candidate substitutes ONLY the fourth-leg (`Xsi`) acquisition T-gate
of the ratified `design/adc-top/adc_top.spice`: the folded `adc_tgate_f`
call (10u/20u) becomes the parametrised unfolded `adc_tgate` at scaled
total width (default 2.068x -> 20.68u/41.36u; `--scale` for other
points), swapping one folded switch (NMOS + 2 parallel PMOS) for one
unfolded switch (NMOS + 1 PMOS) in 18 cells -- hence the builder call's
`expected_mos=350` (368 ratified - 18; see the call-site comment).
`layout/adc-top/gen_adc_top.py`'s own `build()` then runs unmodified on
the substituted netlist; this script only draws.

Stdlib + `klayout.db` -- run it with the same Python interpreter `klt`
uses, into a fresh output directory (candidate outputs never overwrite
committed evidence)::

    KP="$(dirname "$(readlink -f "$(command -v klt)")")/python"
    "$KP" layout/adc-top/candidates/gen_acq_leg_candidate.py \\
        --outdir layout/adc-top/candidates/acq-leg-2.068x-example

The original 2.068x experiment's device counts, verification commands
(`klt drc`/`extract`/`lvs`) and outputs: `records/20260825-030447-4e220d1.md`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADC_TOP_DIR = os.path.dirname(HERE)  # layout/adc-top

#: The fourth-leg (`Xsi`) T-gate line, exactly as `design/adc-top/
#: gen_adc_top.py` emits it at the ratified geometry -- the SAME anchor
#: `sim/dr0019-cu-sweep/gen_cu_variant.py`'s `ACQ_LEG_LINE` uses, so this
#: script's candidate netlist isolates the identical device that record's
#: schematic-side evidence does. DR-0050 note: the ratified line is the
#: FOLDED `adc_tgate_f` call (PMOS as two parallel wp=10u fingers); the
#: widened `candidate_line` below substitutes the parametrised unfolded
#: `adc_tgate wn= wp=` at the scaled TOTAL widths -- parallel W is the
#: sweep's variable, and both sides (this script and gen_cu_variant.py)
#: emit the identical unfolded widened line so their widths stay
#: comparable scale-for-scale, exactly as before the fold.
ACQ_LEG_LINE = "Xsi vin  bp gn_in  gp_in  vdd adc_tgate_f"
#: Ratified widths (um) of the anchored line, and the #211/#238 candidate scale.
RATIFIED_WN_UM = 10.0
RATIFIED_WP_UM = 20.0
DEFAULT_SCALE = 2.068
#: #211/#238's literal candidate widths: 2.068x the ratified 10u/20u. Kept as
#: a constant so the default path is asserted to reproduce it exactly.
ACQ_LEG_CANDIDATE = "Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn=20.68u wp=41.36u"


def _fmt_um(value: float) -> str:
    return f"{round(value, 6):g}u"


def candidate_line(scale: float) -> str:
    """The `Xsi` line with wn/wp scaled by `scale` (issue #429 sweep)."""
    wn = _fmt_um(RATIFIED_WN_UM * scale)
    wp = _fmt_um(RATIFIED_WP_UM * scale)
    return f"Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn={wn} wp={wp}"


def default_outdir(scale: float) -> str:
    return os.path.join(HERE, f"acq-leg-{scale:g}x")


assert candidate_line(DEFAULT_SCALE) == ACQ_LEG_CANDIDATE


def _load_layout_generator():
    """Import `layout/adc-top/gen_adc_top.py` by path (its directory name,
    `adc-top`, is not a legal package identifier)."""
    sys.path.insert(0, ADC_TOP_DIR)
    path = os.path.join(ADC_TOP_DIR, "gen_adc_top.py")
    spec = importlib.util.spec_from_file_location("gen_adc_top_acq_leg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_netlist_text(nl, scale: float = DEFAULT_SCALE) -> tuple[str, str]:
    """The ratified `design/adc-top/adc_top.spice` text with ONLY the
    `Xsi` fourth-leg line widened. Returns `(text, source_path)`."""
    design = nl.design_dir(ADC_TOP_DIR)
    source_path = os.path.join(design, "adc-top", "adc_top.spice")
    with open(source_path, encoding="utf-8") as fh:
        text = fh.read()
    hits = text.count(ACQ_LEG_LINE)
    if hits != 1:
        raise SystemExit(
            f"error: expected exactly one {ACQ_LEG_LINE!r} in {source_path}, "
            f"found {hits} -- design/adc-top/gen_adc_top.py's cell emission "
            "has changed and this substitution is no longer anchored"
        )
    return text.replace(ACQ_LEG_LINE, candidate_line(scale)), source_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Draw an acquisition-leg width candidate.")
    ap.add_argument("--scale", type=float, default=DEFAULT_SCALE,
                    help="multiplier on the ratified Xsi 10u/20u (default 2.068, the "
                         "rejected DR-0025 candidate; 1.0 = regenerated control)")
    ap.add_argument("--force", action="store_true",
                    help="allow writing into a directory that already holds klt extract "
                         "evidence (adc_top.spice); never use on committed historical dirs")
    ap.add_argument("--outdir", default=None,
                    help="output dir; must be a NEW or candidate-owned directory strictly "
                         "under layout/adc-top/candidates/ (default acq-leg-<scale>x)")
    args = ap.parse_args(argv)
    scale = args.scale
    if scale <= 0:
        raise SystemExit("error: --scale must be positive")
    outdir = os.path.abspath(args.outdir) if args.outdir else default_outdir(scale)
    if os.path.commonpath([outdir, HERE]) != HERE or outdir == HERE or os.path.basename(
        outdir
    ) in ("records",):
        raise SystemExit(
            f"error: outdir {outdir} must be a subdirectory of {HERE} "
            "(candidate outputs never overwrite production or historical evidence)"
        )
    if os.path.exists(os.path.join(outdir, "adc_top.spice")) and not args.force:
        raise SystemExit(
            f"error: {outdir} already holds committed klt-extract evidence "
            "(adc_top.spice); refusing to overwrite. Pass a fresh --outdir "
            "(e.g. acq-leg-2.068x-regen) to regenerate."
        )
    g = _load_layout_generator()
    nl = g.nl
    geo = g.geo

    os.makedirs(outdir, exist_ok=True)
    text, source_path = candidate_netlist_text(nl, scale)
    candidate_path = os.path.join(outdir, "adc_top.candidate.spice")
    with open(candidate_path, "w", encoding="utf-8") as fh:
        fh.write(
            "* GENERATED by layout/adc-top/candidates/gen_acq_leg_candidate.py\n"
            f"* from {os.path.relpath(source_path, ADC_TOP_DIR)} with ONLY the\n"
            f"* Xsi (fourth-leg / acquisition) T-gate scaled {scale:g}x (10u/20u ->\n"
            f"* {candidate_line(scale).split('wn=')[1].replace(' wp=', '/')}), per issues #248/#429 -- do not edit; not the ratified\n"
            "* design/adc-top/adc_top.spice, which this file does not replace.\n"
            "*\n" + text
        )

    subckts = nl.parse(candidate_path)
    g.block_subckt(subckts)
    comparator_subckts = nl.parse(
        os.path.join(nl.design_dir(ADC_TOP_DIR), "comparator", "comparator.spice")
    )

    tally_info = None
    for key, cell_name, cmp_subckts in (
        ("adc_top", g.CELL_NAME, None),
        ("adc_block", g.BLOCK_CELL_NAME, comparator_subckts),
    ):
        # 368 ratified MOS - 18 = 350: the widened Xsi swaps one folded
        # `adc_tgate_f` (NMOS + 2 PMOS) per cell back to the parametrised
        # `adc_tgate` (NMOS + 1 PMOS), once per weighted cell on each of
        # the two sides (DR-0050 made the count check explicit per-form).
        layout, info = g.build(
            subckts, cmp_subckts, cell_name=cell_name, expected_mos=350
        )
        assert layout.dbu == geo.DBU_UM, f"dbu drifted to {layout.dbu}"
        layout.write(os.path.join(outdir, f"{key}.gds"), geo.save_options())
        g.write_reference(os.path.join(outdir, f"{key}.ref.spice"), info, cell_name, key)
        g.write_request(os.path.join(outdir, f"{key}.lvs.json"), cell_name, key)
        box = layout.cell(cell_name).bbox()
        print(
            f"wrote {key}.gds  transistors={info['transistor_count']}  "
            f"caps={info['cap_count']}  "
            f"{box.width() * geo.DBU_UM:.1f} x {box.height() * geo.DBU_UM:.1f} um "
            f"= {geo.area_um2(box) / 1e6:.5f} mm^2"
        )
        tally_info = info

    census: dict[str, int] = {}
    for group in tally_info["assignment"].values():
        census[group] = census.get(group, 0) + 1
    tally = {
        "_comment": [
            "As-drawn area tally for the candidate geometry #238 item 5 / issue",
            f"#248/#429 measures: the ratified design/adc-top/adc_top.spice with ONLY",
            f"the CDAC cell's fourth (input/acquisition) Xsi T-gate scaled {scale:g}x",
            f"(10u/20u -> {candidate_line(scale).split('wn=')[1].replace(' wp=', '/')}), release/V_REF/GND legs and the top-plate",
            "V_cm switch left at the ratified 10u/20u. Written by",
            "layout/adc-top/candidates/gen_acq_leg_candidate.py. Same schema as",
            "layout/adc-top/area.json (the ratified geometry's own tally) so the",
            "two are directly comparable field-for-field.",
            "",
            "NOT a replacement for layout/adc-top/area.json -- this is a",
            "candidate-geometry measurement, not the ratified block's own record.",
        ],
        "acq_leg_scale": scale,
        "acq_leg_line": candidate_line(scale),
        "areas_um2": tally_info["areas"],
        "dimensions_um": tally_info["dimensions_um"],
        "transistor_count": tally_info["transistor_count"],
        "unit_cap_device_count": tally_info["cap_count"],
        "unit_cap_positions_per_side": g.ARRAY_COLS * g.ARRAY_ROWS,
        "unit_cap_census_per_side": census,
    }
    with open(os.path.join(outdir, "area.json"), "w", encoding="utf-8") as fh:
        json.dump(tally, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"  unit-cap census per side: {census}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
