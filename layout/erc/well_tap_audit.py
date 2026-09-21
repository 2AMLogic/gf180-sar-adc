#!/usr/bin/env python3
"""Answer, from the geometry itself, whether ADC_BLOCK draws well or
substrate taps -- the question `klt erc`'s `erc.missing_tie` check cannot
answer on this stream.

WHY THIS EXISTS. `layout/erc/`'s supply spec declares no `ties[]`, so
`erc.missing_tie` is never computed (see `README.md`). The committed
`tie-narrowed` control *does* declare the real gf180mcu tap boolean
(`COMP n Nplus`, via `tap_requires`) and reports 25 `erc.missing_tie`
findings -- but that control cannot be read as evidence either way, because
the `Nplus` layer it narrows on is empty everywhere in this stream: it
would report those same 25 findings whether or not a tap were drawn. The
check is *vacuous*, not wrong.

A vacuous check leaves the underlying question open, and the question is
answerable directly from the drawn layers without any implant marking at
all. That is what this script does, and it is the evidence behind
`spec/decision-records/DR-0032-implant-layers-not-drawn.md`.

WHAT IT MEASURES. Two booleans, each reduced to a polygon count:

  * **Is any n-well tap drawn?** A well tap is a diffusion region inside a
    well that is not part of a transistor. So: take every `COMP` 22/0
    polygon interacting with `Nwell` 21/0, and drop every one that also
    interacts with `Poly2` 30/0 (those are MOS source/drain/channel). What
    survives is a tap candidate. **Zero survivors means no well tap is
    drawn** -- a conclusion that needs no implant layer, no extraction deck
    and no net model, only the drawn geometry.
  * **Is any substrate tie drawn, and does it reach a supply?** Same
    boolean outside the wells: `COMP` not interacting with `Nwell` and not
    interacting with `Poly2`. The survivors are the two guard rings
    `lib/geometry.py:draw_guard_ring` draws. For each, this records the
    contacted-ring geometry that makes it a real tie structure, the count
    of `Metal1_Label` 34/10 texts landing on it (a strap `klt erc` could
    see), and whether its four `Metal1` bars touch each other at all.

Every number this prints is compared against `well-tap-audit.json`, which
commits the measured values together with the sha256 of the GDS they
describe. A layout edit that adds a well tap, draws an implant layer, or
straps a ring makes this go red rather than silently invalidating the
decision record that rests on it.

Usage
-----
    python3 layout/erc/well_tap_audit.py           # measure, print, assert
    python3 layout/erc/well_tap_audit.py --verify  # stdlib only: re-hash
                                                   # the GDS against the
                                                   # committed audit
    python3 layout/erc/well_tap_audit.py --regen   # rewrite the committed
                                                   # expectations (a
                                                   # reviewed re-baseline)

Exit codes
----------
    0  the geometry still measures exactly what `well-tap-audit.json` says
    1  tooling problem (no pip `klayout`, unreadable manifest)
    2  a measurement drifted, or the GDS is not the one the audit describes

`--verify` is the stdlib-only half, for CI and for anyone without the pip
`klayout` package: it cannot re-measure, so it asserts only that the
committed GDS is still byte-identical to the one every measurement below
was taken on. That is the same division of labour `run_erc.py --verify` and
`signoff/run_signoff.py --check` draw, and it is what makes this audit fail
on geometry drift instead of rotting.

Requirements
------------
The pip `klayout` package (not the GUI application, not a PDK, not `klt`)
for the measuring path; nothing at all for `--verify`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "well-tap-audit.json")
LAYOUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(LAYOUT_DIR, os.pardir))

# `layout/` is a plain directory, not an installed package -- the same two
# lines run_erc.py / run_drc.py / run_lvs.py use to reach the shared helper.
if LAYOUT_DIR not in sys.path:
    sys.path.insert(0, LAYOUT_DIR)

from klt_env import (  # noqa: E402  (import follows the sys.path setup above)
    EXIT_MISMATCH,
    EXIT_OK,
    EXIT_TOOLING,
    ToolingError,
    load_manifest,
    sha256,
)

#: Areas are compared at this many decimal places. The layout is on a 1 nm
#: database grid, so every area below is exact to far more digits than this;
#: rounding only keeps the committed JSON readable and float-stable.
AREA_DP = 3


# --------------------------------------------------------------------------- #
# measurement
# --------------------------------------------------------------------------- #


def _layer(ly, spec: str):
    """`"21/0"` -> that layer's index in `ly`, or `None` if the stream does
    not carry the layer at all (which is itself a measured fact here)."""
    layer, datatype = (int(part) for part in spec.split("/"))
    return ly.find_layer(layer, datatype)


def measure(gds_path: str, manifest: dict) -> dict:
    """Re-derive every value in `manifest["measured"]` from `gds_path`."""
    try:
        import klayout.db as kdb
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise ToolingError(
            "the pip `klayout` package is required to measure "
            f"({exc}). Install it, or run with --verify for the "
            "stdlib-only geometry-freshness check."
        ) from exc

    ly = kdb.Layout()
    ly.read(gds_path)
    top = ly.top_cell()
    if top is None or top.name != manifest["layout_top"]:
        raise ToolingError(
            f"{gds_path}: top cell {top.name if top else None!r} != "
            f"{manifest['layout_top']!r}"
        )
    dbu = ly.dbu
    layers = manifest["layers"]

    def region(name: str):
        idx = _layer(ly, layers[name])
        if idx is None:
            return kdb.Region()
        reg = kdb.Region(top.begin_shapes_rec(idx))
        reg.merge()
        return reg

    def um2(reg) -> float:
        return round(reg.area() * dbu * dbu, AREA_DP)

    nwell = region("nwell")
    comp = region("comp")
    poly2 = region("poly2")
    contact = region("contact")
    metal1 = region("metal1")

    # -- the two questions ------------------------------------------------ #
    # A tap is diffusion that is NOT part of a transistor. `interacting`
    # (not `&`) is deliberate: it keeps whole COMP polygons rather than
    # clipped fragments, so "this polygon is a transistor terminal" stays a
    # property of the polygon rather than of the clip.
    comp_in_well = comp.interacting(nwell)
    comp_out_well = comp.not_interacting(nwell)
    well_taps = comp_in_well.not_interacting(poly2)
    substrate_ties = comp_out_well.not_interacting(poly2)

    # -- label texts ------------------------------------------------------ #
    label_idx = _layer(ly, layers["metal1_label"])
    label_positions = []
    if label_idx is not None:
        it = top.begin_shapes_rec(label_idx)
        while not it.at_end():
            shape = it.shape()
            if shape.is_text():
                label_positions.append(shape.text.transformed(it.trans()).position())
            it.next()

    def labels_on(reg) -> int:
        hit = 0
        for pos in label_positions:
            probe = kdb.Region(kdb.Box(pos, pos).enlarged(1, 1))
            if reg.interacting(probe).count():
                hit += 1
        return hit

    # -- per-ring detail -------------------------------------------------- #
    rings = []
    ordered = sorted(substrate_ties.each_merged(), key=lambda p: -p.area())
    for name, poly in zip(
        [r["name"] for r in manifest["measured"]["substrate_tie_rings"]], ordered
    ):
        pr = kdb.Region(poly)
        ring_contacts = contact.interacting(pr)
        ring_metal1 = metal1.interacting(pr)
        bars = list(ring_metal1.each_merged())
        touching = 0
        for i, a in enumerate(bars):
            for b in bars[i + 1:]:
                if kdb.Region(a).interacting(kdb.Region(b)).count():
                    touching += 1
        dims = []
        for shape in ring_contacts.each_merged():
            box = shape.bbox()
            dims += [box.width(), box.height()]
        bbox = poly.bbox()
        rings.append(
            {
                "name": name,
                "comp_area_um2": round(poly.area() * dbu * dbu, AREA_DP),
                "bbox_dbu": [bbox.left, bbox.bottom, bbox.right, bbox.top],
                "contact_polygons": ring_contacts.count(),
                "contact_min_dim_um": round(min(dims) * dbu, AREA_DP),
                "contact_max_dim_um": round(max(dims) * dbu, AREA_DP),
                "metal1_bars": len(bars),
                "metal1_bar_pairs_touching": touching,
                "metal1_area_um2": um2(ring_metal1),
                "metal1_label_texts": labels_on(ring_metal1),
            }
        )

    return {
        "implant_layers_present": {
            spec: _layer(ly, spec) is not None
            for spec in (layers["pplus"], layers["nplus"])
        },
        "nwell_islands": nwell.count(),
        "nwell_area_um2": um2(nwell),
        "comp_polygons": comp.count(),
        "comp_interacting_nwell": comp_in_well.count(),
        "comp_not_interacting_nwell": comp_out_well.count(),
        "well_tap_candidates": well_taps.count(),
        "substrate_tie_candidates": substrate_ties.count(),
        "substrate_tie_comp_area_um2": um2(substrate_ties),
        "metal1_label_texts_total": len(label_positions),
        "substrate_tie_rings": rings,
    }


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #


def render(measured: dict) -> None:
    implants = measured["implant_layers_present"]
    print("ADC_BLOCK well/substrate tap audit")
    print(
        "  implant layers drawn:      "
        + ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in implants.items())
    )
    print(
        f"  Nwell islands:             {measured['nwell_islands']} "
        f"({measured['nwell_area_um2']} um2)"
    )
    print(
        f"  COMP polygons:             {measured['comp_polygons']} "
        f"({measured['comp_interacting_nwell']} interacting Nwell, "
        f"{measured['comp_not_interacting_nwell']} not)"
    )
    print(
        f"  WELL TAPS drawn:           {measured['well_tap_candidates']}"
        "   (COMP inside Nwell that is not transistor active)"
    )
    print(
        f"  SUBSTRATE TIES drawn:      {measured['substrate_tie_candidates']}"
        f"   ({measured['substrate_tie_comp_area_um2']} um2 of COMP)"
    )
    for ring in measured["substrate_tie_rings"]:
        print(f"    - {ring['name']}:")
        print(
            f"        COMP ring {ring['comp_area_um2']} um2, "
            f"{ring['contact_polygons']} Contact shapes "
            f"({ring['contact_min_dim_um']} x {ring['contact_max_dim_um']} um), "
            f"{ring['metal1_bars']} Metal1 bars ({ring['metal1_area_um2']} um2)"
        )
        print(
            f"        Metal1 bar pairs touching: "
            f"{ring['metal1_bar_pairs_touching']}   "
            f"Metal1_Label texts on it: {ring['metal1_label_texts']}"
        )


def compare(expected: dict, actual: dict) -> list[str]:
    """Every path where `actual` differs from `expected`, deepest first."""
    diffs: list[str] = []

    def walk(path: str, exp, act) -> None:
        if isinstance(exp, dict) and isinstance(act, dict):
            for key in sorted(set(exp) | set(act)):
                walk(f"{path}.{key}" if path else key, exp.get(key), act.get(key))
        elif isinstance(exp, list) and isinstance(act, list):
            if len(exp) != len(act):
                diffs.append(f"{path}: {len(exp)} entries expected, {len(act)} found")
                return
            for i, (e, a) in enumerate(zip(exp, act)):
                walk(f"{path}[{i}]", e, a)
        elif exp != act:
            diffs.append(f"{path}: expected {exp!r}, measured {act!r}")

    walk("", expected, actual)
    return diffs


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify",
        action="store_true",
        help="stdlib only: assert the committed GDS still hashes to the "
        "sha256 this audit's measurements were taken on",
    )
    mode.add_argument(
        "--regen",
        action="store_true",
        help="rewrite well-tap-audit.json from the current geometry "
        "(a reviewed re-baseline, not a routine step)",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(AUDIT)
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        print(f"FAIL: {AUDIT}: {exc}", file=sys.stderr)
        return EXIT_TOOLING

    gds_path = os.path.join(REPO_ROOT, manifest["layout"])
    if not os.path.exists(gds_path):
        print(f"FAIL: {manifest['layout']} not found", file=sys.stderr)
        return EXIT_TOOLING

    actual_sha = sha256(gds_path)
    if args.verify:
        if actual_sha != manifest["layout_sha256"]:
            print(
                f"FAIL: {manifest['layout']} sha256 {actual_sha} != "
                f"well-tap-audit.json {manifest['layout_sha256']}. The "
                "geometry moved; re-run this script (without --verify) and "
                "re-read DR-0032 before re-baselining.",
                file=sys.stderr,
            )
            return EXIT_MISMATCH
        print(
            f"[ok] {manifest['layout']} sha256 matches well-tap-audit.json -- "
            "every measurement in it still describes the committed geometry"
        )
        return EXIT_OK

    try:
        measured = measure(gds_path, manifest)
    except ToolingError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return EXIT_TOOLING

    render(measured)

    if args.regen:
        manifest["layout_sha256"] = actual_sha
        manifest["measured"] = measured
        with open(AUDIT, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {os.path.relpath(AUDIT, REPO_ROOT)}")
        return EXIT_OK

    problems: list[str] = []
    if actual_sha != manifest["layout_sha256"]:
        problems.append(
            f"layout sha256: expected {manifest['layout_sha256']}, "
            f"found {actual_sha}"
        )
    problems += compare(manifest["measured"], measured)

    if problems:
        print("\nFAIL: the geometry no longer measures what this audit says:")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nIf the layout changed on purpose, re-run with --regen and "
            "revisit spec/decision-records/DR-0032-implant-layers-not-drawn.md "
            "-- its decision rests on these numbers."
        )
        return EXIT_MISMATCH

    print("\nall measurements match well-tap-audit.json")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
