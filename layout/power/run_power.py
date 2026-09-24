#!/usr/bin/env python3
"""Run `klt power` over ADC_BLOCK's supply geometry and mint an append-only
IR-drop / electromigration evidence record.

This is the reproducible invocation of `klt power` for this repository --
the *analysis* half of the power-delivery question, the half T1 item 11 and
`layout/erc/` deliberately leave alone (issue #346). The underlying command
is unremarkable --

    klt power layout/adc-top/adc_block.gds \\
      layout/power/<composed-spec>.json --format json

-- and the composed spec every case was run with is committed beside its
report, so you can always run that by hand. What this script adds is the
part that makes a run *evidence* rather than a screenful of output:

  * it **composes** each case's spec from one committed base spec
    (`adc_block.power-spec.json`, geometry + PDK numbers) plus one named set
    of assumptions from `cases.json` (which resistance corner, where the
    supply is landed, what each sub-block draws). Assumptions never hide
    inside the geometry spec, and the composed result is committed so an
    outside reader re-runs exactly what was run;
  * it **asserts** each case against its expected network shape, per-site
    droop, EM roll-up and budget verdict, so a case that silently stops
    solving -- or starts solving differently -- fails instead of looking
    green;
  * it reports what `klt power` cannot: the solved **current density in the
    Poly2 risers**, in A/um, by recovering each segment's drawn width from
    its own reported resistance and endpoint nodes (see `poly_width_um`
    below and README.md's "What klt power does not report");
  * it verifies the committed GDS hash against `cases.json` AND against each
    report's own `provenance.input.content_hash`;
  * it refuses to run under a `klt` that is not the build `toolchain.json`
    pins, because two 2026-09-22 `klt power` fixes are load-bearing for this
    block specifically (klayout-tools#2259/#2260 -- see that file);
  * it stamps the toolchain and the repo's git sha into the record, and
    writes into a fresh `<record-id>` directory it refuses to overwrite.

Usage
-----
    python3 layout/power/run_power.py            # run, assert, mint a record
    python3 layout/power/run_power.py --check    # run, assert, write nothing
    python3 layout/power/run_power.py --verify   # re-derive the COMMITTED
                                                 # reports, stdlib only, no klt

Exit codes
----------
    0  every case matched its expectation
    1  tooling problem (klt missing or not the pinned build, bad manifest)
    2  at least one case did not match its expectation, or a hash mismatch

Exit 0 does NOT mean "the supply geometry is adequate". Several cases are
*expected* to exceed the DR-0034 budget: that is the finding, and the
expectations encode it. It means "`klt power` reported exactly what it was
supposed to report". `klt power`'s own exit code (0 pass, 3 a `fail`
status, 4 nothing checked) is recorded per case but is not this script's
exit code.

`--verify` is the stdlib-only half, for CI: it re-composes every case's
spec from the committed inputs, checks it against the composed spec
committed beside that case's report, re-reads the report and re-asserts
every expectation -- network shape, per-site droop, the EM roll-up, the
Poly2 current density, and the DR-0034 verdict -- plus the committed GDS
hash. It cannot re-run the tool, so it cannot catch an upstream behaviour
change; it does catch a committed verdict drifting away from the geometry,
the PDK numbers, the current model or the budget it claims to rest on. Same
division of labour `layout/erc/run_erc.py --verify` and
`signoff/run_signoff.py --check` draw.

Requirements
------------
`klt` (2AMLogic/klayout-tools) on PATH at the exact release `toolchain.json`
pins. Headless: neither the KLayout GUI application nor the gf180mcu PDK
install is needed. See ./README.md.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "cases.json")
TOOLCHAIN = os.path.join(HERE, "toolchain.json")
REPORTS_DIR = os.path.join(HERE, "reports")
RECORDS_DIR = os.path.join(HERE, "records")
LAYOUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(LAYOUT_DIR, os.pardir))

# `layout/` is a plain directory, not an installed package, and this script
# is run as `python3 layout/power/run_power.py` (sys.path[0] is
# layout/power), so the shared helper module has to be put on the path
# explicitly -- the same two lines layout/erc/run_erc.py uses.
if LAYOUT_DIR not in sys.path:
    sys.path.insert(0, LAYOUT_DIR)

from klt_env import (  # noqa: E402  (import follows the sys.path setup above)
    EXIT_MISMATCH,
    EXIT_OK,
    EXIT_TOOLING,
    ToolingError,
    git,
    klt_identity,
    load_manifest,
    record_id,
    reserve_record_slot,
    sha256,
)

# `klt power`'s exit codes on a run that produced a report at all: 0 a
# `pass`/`pass_partial` envelope, 3 a `fail` one, 4 nothing was checked
# (extraction-only). 1 and 2 mean the tool could not answer.
POWER_REPORT_EXITS = (0, 3, 4)

# Droop/current comparisons are floats out of an iterative solve. The solver
# is deterministic for a given build+network (Jacobi-preconditioned CG to a
# 1e-6 relative residual, ties in node ordering resolved by extraction
# order), so these tolerances are a round-off budget, not slack: 1e-6
# RELATIVE is six orders looser than the solver's own convergence criterion
# and many orders tighter than any difference that could change a verdict.
# The absolute floor exists only so a quantity that is exactly zero by
# construction (a pad node's own droop) does not demand bit equality; it is
# deliberately far below the smallest number this flow reports (the smallest
# non-zero droop in the committed set is 1.3e-2 mV, the smallest edge
# current 1e-7 A). It is NOT unit-aware, which is why it is this small --
# the same function compares millivolts and amperes.
ABS_FLOOR = 1e-9
REL_TOL = 1e-6


def close(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return abs(actual - expected) <= max(ABS_FLOOR, REL_TOL * abs(expected))


# --------------------------------------------------------------------------- #
# toolchain
# --------------------------------------------------------------------------- #


def resolve_klt(pin: dict, override: str | None) -> tuple[str, dict]:
    """Locate a `klt` and refuse one that is not the pinned build.

    Unlike layout/erc/run_erc.py this also asserts the pip `klayout`
    version, because `klt power`'s network IS klayout's LayoutToNetlist
    output and this flow's committed numbers are solved on that network --
    see toolchain.json's `_comment`.
    """
    found = override or shutil.which("klt")
    if not found:
        raise ToolingError(
            "no `klt` on PATH. Install the pinned build:\n"
            f"    pip install '{pin['klt_install']}'\n"
            "(or pass --klt /path/to/klt)"
        )
    identity = klt_identity(found)
    problems = [
        f"  {field}: {identity.get(field)!r} != pinned {pinned!r}"
        for field, pinned in (
            ("git_commit", pin["klt_git_commit"]),
            ("version", pin["klt_version"]),
            ("klayout_version", pin["klayout_package"]),
        )
        if identity.get(field) != pinned
    ]
    if problems:
        raise ToolingError(
            "`klt` is not the build layout/power/toolchain.json pins:\n"
            + "\n".join(problems)
            + "\nInstall the pinned build:\n"
            f"    pip install '{pin['klt_install']}'\n"
            f"    pip install 'klayout=={pin['klayout_package']}'\n"
            "See that file's _comment for why an older `klt` -- including "
            "the one layout/erc/toolchain.json pins -- produces a WRONG "
            "droop number on this block rather than no number."
        )
    return found, identity


# --------------------------------------------------------------------------- #
# spec composition: base geometry + one case's named assumptions
# --------------------------------------------------------------------------- #


def compose_spec(base: dict, manifest: dict, case: dict) -> dict:
    """Return the full `klt power` spec for one case.

    Deterministic and stdlib-only on purpose: `--verify` re-runs exactly
    this function against the committed inputs and compares the result to
    the composed spec committed beside the report, so an edit to the base
    spec, a resistance corner or a current model cannot leave a stale
    verdict standing.
    """
    spec = copy.deepcopy(base)
    spec.pop("_comment", None)

    corner_name = case["resistance_corner"]
    corner = manifest["resistance_corners"][corner_name]
    for entry in spec["stackup"]:
        if entry["name"] not in corner["sheet_resistance_ohm_per_sq"]:
            raise ToolingError(
                f"resistance corner {corner_name!r} declares no sheet "
                f"resistance for stackup role {entry['name']!r}"
            )
        entry["sheet_resistance_ohm_per_sq"] = corner[
            "sheet_resistance_ohm_per_sq"
        ][entry["name"]]
    for entry in spec["vias"]:
        if entry["name"] not in corner["via_resistance_ohm"]:
            raise ToolingError(
                f"resistance corner {corner_name!r} declares no resistance "
                f"for via role {entry['name']!r}"
            )
        entry["resistance_ohm"] = corner["via_resistance_ohm"][entry["name"]]

    sites = manifest["sites"]
    pad_site = sites[case["pad_site"]]
    supply_v = manifest["supply"]["pad_voltage_v"]
    spec["pads"] = [
        {
            "name": f"pad_vdd_{case['pad_site']}",
            "net": "vdd",
            "x_um": pad_site["vdd"][0],
            "y_um": pad_site["vdd"][1],
            "voltage_v": supply_v,
        },
        {
            "name": f"pad_vss_{case['pad_site']}",
            "net": "vss",
            "x_um": pad_site["vss"][0],
            "y_um": pad_site["vss"][1],
            "voltage_v": 0.0,
        },
    ]

    model = manifest["current_models"][case["current_model"]]
    spec["current_model"] = {
        "supply_net": "vdd",
        "ground_net": "vss",
        # Every instance sits at its own sub-block's `vdd` LABEL, the only
        # place this block declares its supply is reachable. `klt power`
        # snaps an instance to the nearest node on each of its nets
        # independently, so the vss return attaches at the nearest vss node
        # to that same point -- which is where that sub-block's own ground
        # current actually leaves.
        "instances": [
            {
                "name": name,
                "x_um": sites[name]["vdd"][0],
                "y_um": sites[name]["vdd"][1],
                "current_a": model["instance_current_a"][name],
            }
            for name in sorted(model["instance_current_a"])
        ],
    }
    return spec


# --------------------------------------------------------------------------- #
# deriving the numbers this flow reports
# --------------------------------------------------------------------------- #


def node_index(report: dict, net: str) -> dict:
    """`{node_id: (x_um, y_um)}` for `net`'s single island."""
    network = next(n for n in report["networks"] if n["net"] == net)
    islands = network["islands"]
    if len(islands) != 1:
        raise ToolingError(
            f"net {net!r} resolved to {len(islands)} islands, not 1 -- the "
            "whole premise of this flow (one island per rail, per "
            "layout/erc/) no longer holds; re-check the geometry before "
            "trusting any droop number"
        )
    return {n["id"]: (n["x_um"], n["y_um"]) for n in islands[0]["nodes"]}


def nearest_node(index: dict, x: float, y: float) -> str:
    """The node `klt power` would snap a pad/instance at (x, y) to.

    Same rule the tool documents: nearest by straight-line distance, ties
    resolved by extraction order (which `index`, built from the report's own
    node array, preserves).
    """
    best, best_d2 = None, None
    for nid, (nx, ny) in index.items():
        d2 = (nx - x) ** 2 + (ny - y) ** 2
        if best_d2 is None or d2 < best_d2:
            best, best_d2 = nid, d2
    return best


def droop_index(report: dict, net: str) -> dict:
    island = next(
        n for n in report["ir_drop_map"]["nets"] if n["net"] == net
    )["islands"][0]
    return {n["id"]: n["droop_mv"] for n in island["nodes"]}


def poly_width_um(edge: dict, index: dict, sheet_r: float) -> float | None:
    """Recover a metal segment's own drawn cross-width, in um.

    `klt power` reports a segment's `resistance_ohm` and its two endpoint
    nodes but NOT the `length_um`/`cross_um` it computed them from, so a
    role whose PDK publishes no EM limit (Poly2 and Contact here) has no
    reported current density at all. The model is documented and invertible:
    the endpoints sit at the merged polygon's bounding-box ends along its
    longer axis, so `length_um` is their separation and
    `cross_um = sheet_r * length_um / resistance_ohm`.

    Validated on this very report rather than assumed: for every Metal1
    edge -- the role that DOES declare a limit -- this expression reproduces
    `current_limit_a / current_limit_a_per_um` exactly (see
    `check_case`'s width cross-check, which asserts it every run).

    Returns None for a zero-resistance edge (an ideal short, no width to
    recover). Reported upstream as a gap; see README.md.
    """
    if not edge.get("resistance_ohm"):
        return None
    length = math.dist(index[edge["from"]], index[edge["to"]])
    return sheet_r * length / edge["resistance_ohm"]


def analyze(report: dict, manifest: dict, case: dict, spec: dict) -> dict:
    """Everything this flow claims, derived from one report.

    Pure and stdlib-only: `--check` and `--verify` call it on the same
    report and must get the same answer.
    """
    sites = manifest["sites"]
    sheet_r = {e["name"]: e["sheet_resistance_ohm_per_sq"] for e in spec["stackup"]}

    out: dict = {"nets": {}, "sites": {}}

    index = {net: node_index(report, net) for net in ("vdd", "vss")}
    droop = {net: droop_index(report, net) for net in ("vdd", "vss")}

    for net in ("vdd", "vss"):
        network = next(n for n in report["networks"] if n["net"] == net)
        island = network["islands"][0]
        kinds: dict = {}
        for edge in island["edges"]:
            kinds[edge["layer"]] = kinds.get(edge["layer"], 0) + 1
        solved = next(
            n for n in report["ir_drop_map"]["nets"] if n["net"] == net
        )["islands"][0]
        out["nets"][net] = {
            "island_count": len(network["islands"]),
            "node_count": len(island["nodes"]),
            "edge_count": len(island["edges"]),
            "edge_count_by_layer": kinds,
            "solved": solved["solved"],
            "pad_current_a": solved["pad_current_a"],
            # Aggregates over the WHOLE solved field, not just the handful
            # of nodes this flow reports. Without them `--verify` asserts
            # ~9 of 870 node voltages and an edit to any of the other 861
            # goes uncaught; a sum moves for any single-value edit and,
            # unlike a checksum, still compares with a tolerance, so it
            # cannot false-fail on a cross-platform round-off difference.
            "droop_sum_mv": sum(
                n["droop_mv"] for n in solved["nodes"] if n["droop_mv"] is not None
            ),
            "abs_current_sum_a": sum(
                abs(e["current_a"])
                for e in solved["edges"]
                if e.get("current_a") is not None
            ),
        }

    worst_site, worst_combined = None, -1.0
    for name in sorted(sites):
        # The sub-block's own load point: where its instance attaches, which
        # is its own `vdd` label on both nets (see compose_spec).
        x, y = sites[name]["vdd"]
        per = {}
        for net in ("vdd", "vss"):
            per[net] = droop[net][nearest_node(index[net], x, y)]
        per["combined_mv"] = per["vdd"] + per["vss"]
        out["sites"][name] = per
        if per["combined_mv"] > worst_combined:
            worst_site, worst_combined = name, per["combined_mv"]

    budget = manifest["budget"]["combined_droop_mv_max"]
    out["worst_site"] = worst_site
    out["worst_combined_mv"] = worst_combined
    out["budget_mv"] = budget
    out["budget_status"] = "pass" if worst_combined <= budget else "fail"

    em = report["em_verdict"]
    out["em"] = {
        "status": em["status"],
        "fail_count": em["fail_count"],
        "checked_edge_count": em["checked_edge_count"],
        "unchecked_edge_count": em["unchecked_edge_count"],
    }

    # The current density klt power cannot report: Poly2 has no published
    # limit, so its edges come back `unchecked`. Recover the width and do
    # the division here, per rail.
    worst_j, worst_j_edge = -1.0, None
    for net in ("vdd", "vss"):
        island = next(
            n for n in report["ir_drop_map"]["nets"] if n["net"] == net
        )["islands"][0]
        geo = next(n for n in report["networks"] if n["net"] == net)["islands"][0]
        by_id = {e["id"]: e for e in geo["edges"]}
        for edge in island["edges"]:
            shape = by_id[edge["id"]]
            if shape["layer"] != "Poly2" or edge.get("current_a") is None:
                continue
            width = poly_width_um(shape, index[net], sheet_r["Poly2"])
            if not width:
                continue
            j = abs(edge["current_a"]) / width
            if j > worst_j:
                worst_j, worst_j_edge = j, {
                    "net": net,
                    "edge_id": edge["id"],
                    "current_a": edge["current_a"],
                    "width_um": width,
                }
    out["poly2_worst_current_density_a_per_um"] = worst_j if worst_j >= 0 else None
    out["poly2_worst_edge"] = worst_j_edge
    return out


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def run_case(klt: str, layout_rel: str, spec_path: str) -> tuple[dict, str, int]:
    """Run `klt power` twice: JSON (the contract) and text (a courtesy view).

    Invoked from the repo root with a repo-relative layout path so the
    report's own `file` field is portable.
    """
    spec_rel = os.path.relpath(spec_path, REPO_ROOT)
    argv = [klt, "power", layout_rel, spec_rel, "--format", "json"]
    json_proc = subprocess.run(argv, capture_output=True, text=True, cwd=REPO_ROOT)
    if json_proc.returncode not in POWER_REPORT_EXITS:
        raise ToolingError(
            f"klt power failed on {spec_rel} (exit {json_proc.returncode}):\n"
            f"{json_proc.stderr}"
        )
    try:
        report = json.loads(json_proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(
            f"klt power emitted non-JSON for {spec_rel}: {exc}"
        ) from exc

    text_proc = subprocess.run(
        [klt, "power", layout_rel, spec_rel, "--format", "text"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "NO_COLOR": "1"},
    )
    return report, text_proc.stdout, json_proc.returncode


def check_case(
    case: dict,
    report: dict,
    exit_code: int,
    spec: dict,
    manifest: dict,
    layout_sha: str,
    previous: dict | None = None,
) -> tuple[list[str], dict]:
    """Return (failures, derived); an empty list means the case matched.

    `previous` maps already-checked case names to their `derived` blocks, so
    a case whose `expect` declares `scales_case` can be asserted against the
    case it is a seeded perturbation of.
    """
    failures: list[str] = []
    expect = case["expect"]
    derived = analyze(report, manifest, case, spec)

    def cmp(name: str, actual) -> None:
        if name in expect and actual != expect[name]:
            failures.append(f"{name}: expected {expect[name]!r}, got {actual!r}")

    def cmp_num(name: str, actual, expected) -> None:
        if not close(actual, expected):
            failures.append(f"{name}: expected {expected!r}, got {actual!r}")

    cmp("exit_code", exit_code)
    cmp("status", report.get("status"))
    cmp("budget_status", derived["budget_status"])
    cmp("worst_site", derived["worst_site"])
    if "em" in expect:
        cmp("em", derived["em"])
    if "worst_case_droop_mv" in expect:
        # klt power's OWN roll-up, asserted beside this runner's derived
        # figures so the two cannot drift apart silently.
        cmp_num(
            "report.worst_case_droop_mv",
            report.get("worst_case_droop_mv"),
            expect["worst_case_droop_mv"],
        )
    if "nets" in expect:
        float_keys = ("pad_current_a", "droop_sum_mv", "abs_current_sum_a")
        for net, want in expect["nets"].items():
            got = derived["nets"][net]
            for key, value in want.items():
                if key in float_keys:
                    cmp_num(f"nets.{net}.{key}", got.get(key), value)
                elif got.get(key) != value:
                    failures.append(
                        f"nets.{net}.{key}: expected {value!r}, got {got.get(key)!r}"
                    )
    if "worst_combined_mv" in expect:
        cmp_num("worst_combined_mv", derived["worst_combined_mv"],
                expect["worst_combined_mv"])
    for name, want in (expect.get("sites") or {}).items():
        got = derived["sites"].get(name)
        if got is None:
            failures.append(f"sites.{name}: absent from the solved report")
            continue
        for key, value in want.items():
            cmp_num(f"sites.{name}.{key}", got.get(key), value)
    if "poly2_worst_current_density_a_per_um" in expect:
        cmp_num(
            "poly2_worst_current_density_a_per_um",
            derived["poly2_worst_current_density_a_per_um"],
            expect["poly2_worst_current_density_a_per_um"],
        )

    # A seeded control's whole point is that it MUST move the answer, and
    # move it by a known factor. Asserting the factor -- not merely that the
    # number differs -- is what makes a solve that quietly stopped consuming
    # the current model fail here instead of looking plausible.
    scales = expect.get("scales_case")
    if scales:
        other = (previous or {}).get(scales["case"])
        if other is None:
            failures.append(
                f"scales_case: case {scales['case']!r} was not solved before "
                "this one -- order the cases so the reference comes first"
            )
        else:
            for site, per in derived["sites"].items():
                want = other["sites"][site]["combined_mv"] * scales["factor"]
                if not close(per["combined_mv"], want):
                    failures.append(
                        f"scales_case: sites.{site}.combined_mv "
                        f"{per['combined_mv']!r} != {scales['factor']}x "
                        f"{scales['case']}'s {other['sites'][site]['combined_mv']!r} "
                        f"(= {want!r}) -- this control no longer proves the "
                        "solve responds to the current model"
                    )

    # The width recovery poly2 current density rests on, asserted against
    # the one role that publishes a limit -- so a change in klt power's
    # segment model is caught here instead of silently rescaling a density.
    sheet_r = {e["name"]: e["sheet_resistance_ohm_per_sq"] for e in spec["stackup"]}
    limit_per_um = {
        e["name"]: e.get("current_limit_a_per_um") for e in spec["stackup"]
    }
    for net in ("vdd", "vss"):
        index = node_index(report, net)
        geo = next(n for n in report["networks"] if n["net"] == net)["islands"][0]
        for edge in geo["edges"]:
            role = edge["layer"]
            if edge["kind"] != "metal" or not limit_per_um.get(role):
                continue
            if not edge.get("current_limit_a"):
                continue
            recovered = poly_width_um(edge, index, sheet_r[role])
            reported = edge["current_limit_a"] / limit_per_um[role]
            if recovered is None or abs(recovered - reported) > 1e-6 * max(
                1.0, reported
            ):
                failures.append(
                    f"{net}/{edge['id']}: width recovered from resistance "
                    f"({recovered}) != width implied by the reported EM limit "
                    f"({reported}) -- klt power's segment model has moved, so "
                    "the Poly2 current density in this record is no longer "
                    "derivable the way README.md says it is"
                )
                break

    # The report must describe the committed geometry, not some other
    # stream. `klt power` emits NO provenance block at all -- unlike
    # `klt erc`, which carries `provenance.input.content_hash` and
    # `provenance.spec.content_hash` (klayout-tools#1968/#2036). Filed
    # upstream as klayout-tools#2349; until it lands, `run_power.py` hashes
    # the inputs itself and stamps `_layout_sha256` into the committed
    # report. That is this RUNNER's attestation, not the tool's, and it is
    # weaker for exactly that reason: it proves the committed report has
    # not been separated from the geometry it was minted against, not that
    # `klt power` read those bytes.
    if report.get("provenance") is not None:
        failures.append(
            "this report carries a `provenance` block -- klt power grew one "
            "(klayout-tools#2349). Assert it directly and drop the "
            "_layout_sha256 stand-in below."
        )
    stamped = report.get("_layout_sha256")
    if stamped != layout_sha:
        failures.append(
            f"_layout_sha256 {stamped!r} != committed layout {layout_sha!r}"
        )
    if report.get("file") != manifest["layout"]:
        failures.append(
            f"report `file` {report.get('file')!r} != {manifest['layout']!r}"
        )

    # ... and each declared device body must actually have bitten.
    want_areas = case.get("expect", {}).get("device_body_area_um2")
    if want_areas is not None:
        got = {d["name"]: d["body_area_um2"] for d in report.get("devices") or []}
        if got != want_areas:
            failures.append(
                f"device_body_area_um2: expected {want_areas}, got {got}"
            )

    return failures, derived


# --------------------------------------------------------------------------- #
# --verify (stdlib only: re-compose, re-read, re-assert)
# --------------------------------------------------------------------------- #


def latest_record() -> str:
    if not os.path.isdir(REPORTS_DIR):
        raise ToolingError(f"{REPORTS_DIR} does not exist -- nothing to verify")
    slots = sorted(
        name
        for name in os.listdir(REPORTS_DIR)
        if os.path.isdir(os.path.join(REPORTS_DIR, name))
    )
    if not slots:
        raise ToolingError(f"{REPORTS_DIR} is empty -- nothing to verify")
    return slots[-1]


def verify(manifest: dict, rec_id: str | None) -> int:
    rec_id = rec_id or latest_record()
    report_dir = os.path.join(REPORTS_DIR, rec_id)
    layout_path = os.path.join(REPO_ROOT, manifest["layout"])
    expected_sha = manifest["layout_sha256"]
    base = load_manifest(os.path.join(HERE, manifest["base_spec"]))

    print(f"verifying committed reports in reports/{rec_id} (no klt needed)")
    failures: list[str] = []
    previous: dict = {}

    actual_sha = sha256(layout_path)
    if actual_sha != expected_sha:
        failures.append(
            f"{manifest['layout']}: sha256 {actual_sha} != cases.json "
            f"{expected_sha} -- re-run layout/power/run_power.py"
        )
    else:
        print(f"  [ok] {manifest['layout']} sha256 matches cases.json")

    budget_path = os.path.join(REPO_ROOT, manifest["budget"]["record"])
    if not os.path.exists(budget_path):
        failures.append(
            f"budget record {manifest['budget']['record']} does not exist -- "
            "every case below is graded against a budget with no decision "
            "record behind it"
        )
    else:
        print(f"  [ok] budget record {manifest['budget']['record']} present")

    for case in manifest["cases"]:
        name = case["name"]
        path = os.path.join(report_dir, f"{name}.power.json")
        spec_path = os.path.join(report_dir, f"{name}.power-spec.json")
        if not os.path.exists(path) or not os.path.exists(spec_path):
            failures.append(f"{name}: no committed report/spec under {report_dir}")
            continue
        with open(path, encoding="utf-8") as fh:
            report = json.load(fh)
        with open(spec_path, encoding="utf-8") as fh:
            committed_spec = json.load(fh)

        case_failures: list[str] = []
        recomposed = compose_spec(base, manifest, case)
        if recomposed != committed_spec:
            case_failures.append(
                "the spec re-composed from the committed base spec + "
                "cases.json does not match the spec committed beside this "
                "report -- an input moved after the report was minted"
            )
        exit_code = report.pop("_klt_exit_code", None)
        more, derived = check_case(
            case,
            report,
            exit_code,
            committed_spec,
            manifest,
            expected_sha,
            previous,
        )
        previous[name] = derived
        case_failures.extend(more)

        if case_failures:
            failures.extend(f"{name}: {f}" for f in case_failures)
            print(f"  [FAIL] {name}")
            for failure in case_failures:
                print(f"      - {failure}")
        else:
            print(f"  [ok] {name}")

    if failures:
        print(f"\n{len(failures)} failure(s)", file=sys.stderr)
        return EXIT_MISMATCH
    print(
        "\nevery committed IR/EM report still describes the committed "
        "geometry, the committed PDK numbers and the committed current "
        "model, and still reaches the verdict cases.json records"
    )
    return EXIT_OK


# --------------------------------------------------------------------------- #
# the record
# --------------------------------------------------------------------------- #


def write_record(
    rec_id: str,
    report_dir: str,
    manifest: dict,
    results: list[dict],
    toolchain: dict,
    overall_ok: bool,
    issue: str | None = None,
) -> str:
    """Write the committed reports and the append-only summary record.

    `report_dir` is already reserved by `reserve_slot()` below -- unlike the
    other `layout/` runners, this flow writes each case's *composed spec*
    into the record slot before `klt power` runs (the spec is the tool's
    input), so the slot cannot be created here.
    """
    os.makedirs(RECORDS_DIR, exist_ok=True)
    record_path = os.path.join(RECORDS_DIR, f"{rec_id}.md")
    if os.path.exists(record_path):
        raise ToolingError(
            f"record {rec_id} already exists -- refusing to overwrite "
            "(layout/ evidence is append-only)."
        )

    for result in results:
        base = os.path.join(report_dir, result["name"])
        payload = dict(result["report"])
        payload["_klt_exit_code"] = result["exit_code"]
        with open(f"{base}.power.json", "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        with open(f"{base}.power.txt", "w", encoding="utf-8") as fh:
            fh.write(result["text"])

    with open(os.path.join(report_dir, "toolchain.json"), "w", encoding="utf-8") as fh:
        json.dump(toolchain, fh, indent=2)
        fh.write("\n")

    budget = manifest["budget"]
    lines = [
        f"# Power (IR drop / EM) record {rec_id}",
        "",
        "Append-only evidence record for the `klt power` IR-drop and "
        "electromigration flow (`layout/power/`). Generated by "
        "`layout/power/run_power.py`; never edited in place -- a re-run "
        "mints a new record.",
        "",
        f"- **Record ID** — `{rec_id}`",
        "- **Claim** — the worst-case static IR drop (`vdd` droop + `vss` "
        "bounce) at each of ADC_BLOCK's four labelled sub-block sites, and "
        "the current density in the Poly2 risers the rails still run on "
        "inside each sub-block (the block-level straps between them are "
        "Metal2 since issue #378), against the "
        f"{budget['combined_droop_mv_max']} mV combined budget "
        f"[`{os.path.basename(budget['record'])}`](../../../{budget['record']}) "
        f"sets. **That record's status is `{budget['status']}`** — every "
        "verdict below is graded against a budget that is not yet ratified.",
        "- **Not claimed** — anything transient. This is a **static** (DC) "
        "solve: it prices the average current the rail must deliver "
        "continuously. The peak-current case below is an upper bound on a "
        "network with no decoupling in it, not a prediction of the "
        "instantaneous rail voltage. See `layout/power/README.md`.",
        f"- **Geometry** — `{manifest['layout']}` "
        f"(sha256 `{manifest['layout_sha256']}`), top cell "
        f"`{manifest['layout_top']}`.",
        "- **Overall** — "
        + (
            "PASS (every case reported exactly what it was expected to)"
            if overall_ok
            else "FAIL (at least one case did not match its expectation)"
        ),
        "",
        "## Toolchain",
        "",
        "| Component | Value |",
        "|---|---|",
    ]
    for key, value in toolchain.items():
        lines.append(f"| `{key}` | `{value}` |")

    lines += [
        "",
        "## Current model",
        "",
        "| Model | Source | Corner | Total `vdd` current |",
        "|---|---|---|---|",
    ]
    for name in sorted(manifest["current_models"]):
        model = manifest["current_models"][name]
        total = sum(model["instance_current_a"].values())
        lines.append(
            f"| `{name}` | {model['source']} | `{model.get('corner', '-')}` | "
            f"{total * 1e6:.3f} µA |"
        )

    lines += [
        "",
        "## Result",
        "",
        f"Budget: **{budget['combined_droop_mv_max']} mV** combined "
        f"(`vdd` droop + `vss` bounce) at any labelled site — "
        f"{budget['record']} (`{budget['status']}`).",
        "",
        "| Case | Supply landed at | R corner | Current | Worst site | "
        "Worst combined | Budget | EM |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for result in results:
        case, derived = result["case"], result["derived"]
        lines.append(
            "| `{name}` | {pad} | {corner} | {model} | {site} | {mv:.3f} mV | "
            "{verdict} | `{em}` |".format(
                name=result["name"],
                pad=case["pad_site"],
                corner=case["resistance_corner"],
                model=case["current_model"],
                site=derived["worst_site"],
                mv=derived["worst_combined_mv"],
                verdict="**PASS**"
                if derived["budget_status"] == "pass"
                else "**FAIL**",
                em=derived["em"]["status"],
            )
        )

    lines += [
        "",
        "### Per-site droop, every case",
        "",
        "`vdd` droop / `vss` bounce / combined, in mV, at each sub-block's "
        "own load point (its `vdd` label, where `klt power` attaches that "
        "instance on both nets).",
        "",
    ]
    site_names = sorted(manifest["sites"])
    lines.append("| Case | " + " | ".join(f"`{s}`" for s in site_names) + " |")
    lines.append("|---|" + "---|" * len(site_names))
    for result in results:
        cells = []
        for site in site_names:
            per = result["derived"]["sites"][site]
            cells.append(
                f"{per['vdd']:.3f} / {per['vss']:.3f} / **{per['combined_mv']:.3f}**"
            )
        lines.append(f"| `{result['name']}` | " + " | ".join(cells) + " |")

    lines += [
        "",
        "### Poly2 riser current density",
        "",
        "`klt power` reports every Poly2 and Contact edge as **unchecked**: "
        "gf180mcuD publishes no current-density limit for either role (see "
        "`adc_block.power-spec.json`). The density below is derived by "
        "`run_power.py` from each segment's own reported resistance and "
        "endpoint nodes, and is reported **without** a pass/fail verdict, "
        "because there is no published limit to have a verdict against.",
        "",
        "| Case | Worst Poly2 edge | Current | Width | Density |",
        "|---|---|---:|---:|---:|",
    ]
    for result in results:
        worst = result["derived"]["poly2_worst_edge"]
        if worst is None:
            lines.append(f"| `{result['name']}` | (none solved) | — | — | — |")
            continue
        lines.append(
            "| `{name}` | `{net}`/`{eid}` | {i:.6g} A | {w:.3f} µm | "
            "{j:.6g} A/µm |".format(
                name=result["name"],
                net=worst["net"],
                eid=worst["edge_id"],
                i=abs(worst["current_a"]),
                w=worst["width_um"],
                j=result["derived"]["poly2_worst_current_density_a_per_um"],
            )
        )

    first = results[0]["derived"]
    lines += [
        "",
        "## The network that was solved",
        "",
        "| Net | Islands | Nodes | Edges | Poly2 | Metal1 | Contact | "
        "Metal2 | Via1 | other above Metal1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for net in ("vdd", "vss"):
        stats = first["nets"][net]
        by_layer = stats["edge_count_by_layer"]
        named = ("Poly2", "Metal1", "Contact", "Metal2", "Via1")
        other = sum(v for k, v in by_layer.items() if k not in named)
        lines.append(
            "| `{net}` | {isl} | {n} | {e} | {p} | {m1} | {c} | {m2} | "
            "{v1} | {up} |".format(
                net=net,
                isl=stats["island_count"],
                n=stats["node_count"],
                e=stats["edge_count"],
                p=by_layer.get("Poly2", 0),
                m1=by_layer.get("Metal1", 0),
                c=by_layer.get("Contact", 0),
                m2=by_layer.get("Metal2", 0),
                v1=by_layer.get("Via1", 0),
                up=other,
            )
        )

    lines += [
        "",
        "The `Metal2`/`Via1` columns are issue #378's change, restated by "
        "the tool that measures its consequence: the block-level straps "
        "between the four labelled sub-blocks run on Metal2 now, so the "
        "current that crosses from one sub-block to another no longer "
        "crosses Poly2. What is still Poly2 is every in-sub-block terminal "
        "riser -- which is why the EM verdict stays `pass_partial` (see "
        "`layout/power/README.md`). Issue #346's finding, which this "
        "column used to restate, was that there was NO supply geometry "
        "above Metal1 at all.",
        "",
        "## Artifacts",
        "",
        "| Case | Composed spec | JSON report | text report |",
        "|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| `{name}` | `reports/{rid}/{name}.power-spec.json` | "
            "`reports/{rid}/{name}.power.json` | "
            "`reports/{rid}/{name}.power.txt` |".format(name=result["name"], rid=rec_id)
        )

    failed = [r for r in results if r["failures"]]
    if failed:
        lines += ["", "## Failures", ""]
        for result in failed:
            for failure in result["failures"]:
                lines.append(f"- `{result['name']}`: {failure}")

    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        f"pip install '{toolchain['klt_install']}'",
        f"pip install 'klayout=={toolchain['klayout_package']}'",
        "python3 layout/power/run_power.py --check    # re-run and assert",
        "python3 layout/power/run_power.py --verify   # re-read this record, no klt",
        "```",
        "",
        "The JSON report is the stable contract; the `.txt` capture beside "
        "it is a courtesy view, not the source of truth. Each committed "
        "JSON carries two added keys that are **this runner's** record, not "
        "part of `klt power`'s own envelope: `_klt_exit_code` (the process "
        "exit status, which `--verify` strips before asserting) and "
        "`_layout_sha256`. The second exists because `klt power` emits no "
        "`provenance` block at all — unlike `klt erc`, whose "
        "`provenance.input.content_hash` is the tool's own attestation of "
        "the bytes it read (klayout-tools#1968/#2036). Filed upstream as "
        "klayout-tools#2349; until it lands, this digest proves only that "
        "the committed report has not been separated from the geometry it "
        "was minted against. The composed spec committed beside each report "
        "is the exact file `klt power` was handed, and `--verify` "
        "re-composes it from `adc_block.power-spec.json` + `cases.json` and "
        "compares it byte for byte.",
        "",
        f"- **Timestamp** — {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "- **Author** — Loom Builder agent"
        + (f" (issue {issue})" if issue else ""),
        "",
    ]

    with open(record_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return record_path


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the cases and assert expectations, but write no record",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="re-derive the committed reports with the stdlib only (no klt)",
    )
    parser.add_argument(
        "--record",
        help="with --verify: the reports/<record-id> to verify (default: latest)",
    )
    parser.add_argument("--klt", help="path to the pinned klt binary")
    parser.add_argument(
        "--issue",
        help="issue this run is minted for, stamped into the record's "
        "Author line (e.g. '#346'); omitted from the record when unset",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest(CASES)

        if args.verify:
            return verify(manifest, args.record)

        pin = load_manifest(TOOLCHAIN)
        klt, identity = resolve_klt(pin, args.klt)
        base = load_manifest(os.path.join(HERE, manifest["base_spec"]))

        layout_rel = manifest["layout"]
        layout_path = os.path.join(REPO_ROOT, layout_rel)
        layout_sha = sha256(layout_path)
        if layout_sha != manifest["layout_sha256"]:
            raise ToolingError(
                f"{layout_rel} sha256 {layout_sha} != cases.json "
                f"{manifest['layout_sha256']}. The geometry moved; update "
                "cases.json deliberately and mint a new record -- do not "
                "leave a droop verdict describing a GDS this repo no longer "
                "holds."
            )

        toolchain = {
            "klt_version": identity.get("version", "unknown"),
            "klt_git_commit": identity.get("git_commit", "unknown"),
            "klt_git_tag": identity.get("git_tag") or "none",
            "klt_install": pin["klt_install"],
            "klt_path": os.path.realpath(klt),
            "klayout_package": identity.get("klayout_version", "unknown"),
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "repo_git_sha": git(REPO_ROOT, "rev-parse", "HEAD") or "unknown",
            "repo_dirty": bool(git(REPO_ROOT, "status", "--porcelain")),
        }

        print(f"layout: {layout_rel}   klt: {toolchain['klt_version']}")

        # The composed specs have to live somewhere `klt power` can read and
        # the record can keep. Write them straight into the record slot when
        # minting; --check uses a scratch dir it removes.
        if args.check:
            spec_dir = os.path.join(HERE, ".check-specs")
            os.makedirs(spec_dir, exist_ok=True)
            rec_id = None
        else:
            rec_id = record_id(REPO_ROOT)
            spec_dir = reserve_record_slot(rec_id, REPORTS_DIR, RECORDS_DIR)

        results = []
        previous: dict = {}
        overall_ok = True
        try:
            for case in manifest["cases"]:
                spec = compose_spec(base, manifest, case)
                spec_path = os.path.join(spec_dir, f"{case['name']}.power-spec.json")
                with open(spec_path, "w", encoding="utf-8") as fh:
                    json.dump(spec, fh, indent=2)
                    fh.write("\n")

                report, text, exit_code = run_case(klt, layout_rel, spec_path)
                # klt power emits no provenance block (klayout-tools#2349);
                # stamp the geometry digest on so the committed report can
                # be tied to the bytes it was solved against.
                report["_layout_sha256"] = layout_sha
                failures, derived = check_case(
                    case, report, exit_code, spec, manifest, layout_sha, previous
                )
                previous[case["name"]] = derived
                if failures:
                    overall_ok = False

                results.append(
                    {
                        "name": case["name"],
                        "case": case,
                        "report": report,
                        "text": text,
                        "exit_code": exit_code,
                        "failures": failures,
                        "derived": derived,
                    }
                )
                print(
                    f"  {case['name']:<34} worst "
                    f"{derived['worst_combined_mv']:9.3f} mV @ "
                    f"{derived['worst_site']:<18} "
                    f"budget {derived['budget_status']:<5} "
                    f"em {derived['em']['status']:<13} "
                    f"[{'ok' if not failures else 'FAIL'}]"
                )
                for failure in failures:
                    print(f"      - {failure}")
        finally:
            if args.check:
                shutil.rmtree(os.path.join(HERE, ".check-specs"), ignore_errors=True)

        if args.check:
            print("--check: no record written")
        else:
            path = write_record(
                rec_id, spec_dir, manifest, results, toolchain, overall_ok, args.issue
            )
            print(f"wrote {os.path.relpath(path, REPO_ROOT)}")

        return EXIT_OK if overall_ok else EXIT_MISMATCH

    except ToolingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_TOOLING


if __name__ == "__main__":
    raise SystemExit(main())
