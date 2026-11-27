#!/usr/bin/env python3
"""Draw a CDAC layout candidate with a scaled acquisition-leg T-gate.

In `design/adc-top/adc_top.spice`, the candidate replaces the folded
`adc_tgate_f` on the fourth leg (`Xsi`) with an unfolded `adc_tgate`.
`--scale` multiplies the ratified NMOS/PMOS widths of 10u/20u. Using
one PMOS in place of two parallel PMOS devices in each of 18 cells
gives the builder its `expected_mos=350` (368 ratified minus 18).

Run with the Python interpreter used by `klt` for access to `klayout.db`.
This example draws a narrowed candidate (5u/10u). Use a fresh output
directory to protect committed evidence.

DR-0050 status: the decode bank now folds every T-gate PMOS into a
shared-source/drain pair, and `lib/place.draw_devices` refuses an unpaired
PMOS wider than `place.FOLD_ROW_MAX_W` (10 um). The widened `Xsi` here is a
single unfolded PMOS, so only scales whose drawn PMOS width (the emitted
`wp=` token, as placement reads it) is at most that limit build; `--scale`
0.5 is a working example, not the only buildable scale. The six width-sweep scales (1, 1.1, 1.25, 1.5,
1.75, 2.068) are NETLIST-ONLY after DR-0050: `main` exits with a DR-0050
message for them before any layout work. Their committed
`candidates/acq-leg-*` directories and records are historical evidence and
are not regenerable.

    KP="$(dirname "$(readlink -f "$(command -v klt)")")/python"
    "$KP" layout/adc-top/candidates/gen_acq_leg_candidate.py \\
        --scale 0.5 --outdir layout/adc-top/candidates/acq-leg-0.5x-example

For the original 2.068x layout, see `records/20260825-030447-4e220d1.md`
for device counts, verification commands and outputs. The intermediate
width sweep is documented in `sim/acq-leg-width-sweep/README.md`.
"""

from __future__ import annotations

import ast
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


def fold_row_max_w_nm() -> int:
    """`FOLD_ROW_MAX_W` read from `layout/adc-top/lib/place.py` by parsing its
    source: the module needs `klayout.db` and a package context to import, and
    this guard must run (and be unit-tested) without either."""
    path = os.path.join(ADC_TOP_DIR, "lib", "place.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "FOLD_ROW_MAX_W" for t in node.targets)
        ):
            return int(ast.literal_eval(node.value))
    raise SystemExit(f"error: FOLD_ROW_MAX_W not found in {path}")


def emitted_wp_nm(scale: float) -> int:
    """The PMOS width placement sees for `scale`, in nm: the `wp=` token
    `candidate_line` emits (`_fmt_um`, 6-decimal rounding), converted exactly
    as `lib/netlist.py` does (`Device.w_nm`: metres from the engineering
    suffix, then `round(w * 1e9)`). Rounding the raw product instead can
    disagree with the placed width by 1 nm at the boundary."""
    token = _fmt_um(RATIFIED_WP_UM * scale)
    return int(round(float(token[:-1]) * 1e-6 * 1e9))


def layout_buildable_error(scale: float) -> str | None:
    """Why the layout for `scale` cannot be drawn post-DR-0050, or None.

    `place.draw_devices` rejects an unpaired PMOS wider than
    `FOLD_ROW_MAX_W` nm; the widened `Xsi` PMOS is one such device. The
    comparison is `>`, so a PMOS exactly at the limit is allowed.
    """
    limit_nm = fold_row_max_w_nm()
    wp_nm = emitted_wp_nm(scale)
    if wp_nm <= limit_nm:
        return None
    return (
        f"error: --scale {scale:g} widens the Xsi PMOS to {wp_nm} nm, above the "
        f"{limit_nm} nm FOLD_ROW_MAX_W; DR-0050 folds every decode-bank T-gate "
        "PMOS into a shared-source/drain pair and this candidate's unfolded "
        "device cannot be paired, so its layout cannot be built. This scale is "
        "netlist-only after DR-0050 (see sim/acq-leg-width-sweep/README.md); the "
        "committed candidates/acq-leg-* evidence is historical."
    )


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
                         "rejected DR-0025 candidate, netlist-only after DR-0050; try 0.5)")
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
    unbuildable = layout_buildable_error(scale)
    if unbuildable:
        raise SystemExit(unbuildable)
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
            "(e.g. acq-leg-0.5x-regen) to regenerate."
        )
    g = _load_layout_generator()
    nl = g.nl

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

    # 368 ratified MOS - 18 = 350: the widened Xsi swaps one folded
    # `adc_tgate_f` (NMOS + 2 PMOS) per cell back to the parametrised
    # `adc_tgate` (NMOS + 1 PMOS), once per weighted cell on each of
    # the two sides (DR-0050 made the count check explicit per-form).
    tally_info = g.emit_deliverables(candidate_path, outdir, expected_mos=350)

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
