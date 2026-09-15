#!/usr/bin/env python3
"""Place and route the SAR sequencer's gate netlist against the reserved
`layout/adc-top/` footprint (DR-0023 follow-on (b), issue #274).

    python3 layout/sar-logic/build.py           # run both attempts, write reports
    python3 layout/sar-logic/build.py --explicit-only   # skip the reference run
    python3 layout/sar-logic/build.py --reference-only  # skip the fit attempt

This drives the already-committed, already-synthesized
`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v` (issue
#272, 181 cell instances, `gf180mcu_fd_sc_mcu7t5v0`) through `klt
place-and-route` (OpenROAD under the hood) **twice**, each run answering a
different half of this issue's own question:

1. **`fit` -- does the netlist fit AS-SHAPED in the literal reserved
   rectangle `layout/adc-top/gen_adc_top.py` already carves out?** An
   `"explicit"` floorplan pinned to that rectangle's own as-drawn interior
   (read live from the generator below, not hand-copied -- see
   `_reserved_footprint_um()`), so a caller can tell "the shape itself
   cannot host this design" from "a squarer die of the same area could".
2. **`reference` -- how much area would a real, comfortably-routable
   place-and-route of this netlist actually need?** A generous
   `"utilization"` floorplan (50% target, square aspect ratio, a real margin)
   -- the same style `2AMLogic/gf180-trng`'s `layout/digital/build.py` (issue
   #111) uses for its own first P&R attempt, so this run's own achieved area
   is a real, comparable number rather than an estimate.

Per this issue's own scope and `CLAUDE.md` ("no claim without a testbench" /
append-only evidence): **an explicit, measured failure of run 1 is a
complete, documented outcome of this script, not a bug in it.** If the fit
attempt fails, that failure -- with `klt place-and-route`'s own error text --
is exactly the finding `reports/place_and_route_fit.json` records; this
script does not silently retry with a looser floorplan to make it pass, and
does not touch `layout/adc-top/gen_adc_top.py`'s own reserved-region
constants (`SAR_RESERVED_W`/`SAR_RESERVED_H`) -- a floorplan change is
explicitly out of scope for this issue.

Why one 3.3 V rail (`vdd`/`vss`), not a second digital-domain net name
-------------------------------------------------------------------------
`2AMLogic/gf180-trng`'s own `layout/digital/build.py` names its PDN
`vddd`/`vss` because that repo's digital section is a genuinely separate
power domain from its analog entropy source (`layout/floorplan/README.md`'s
four-domain star there). This block is different, and DR-0023 says so in the
same breath as adopting the 6 V-oxide standard-cell libraries: **"This isn't
a second domain -- it's one 3.3 V rail throughout"**
(`spec/decision-records/DR-0023-digital-interface-device-flavor.md`). This
run's own PDN therefore asks `klt place-and-route` for `vdd`/`vss` --
`layout/adc-top/gen_adc_top.py`'s own `rails = ["vdd", "vss", "vref",
"vcm"]` -- not a `vddd` this block has no ratified name for and no second
domain to justify.

Why `fit` and `reference` carry DIFFERENT PDN configs (`POWER_FIT`/`POWER`)
-------------------------------------------------------------------------
Both start from `pdn_grid_strategy_7t_6M.cfg`'s `Metal1` row rails; only
`reference` also carries its `Metal4`/`Metal5` straps. Measured live: that
upper-metal mesh's own `Metal5` strap needs 49.3 um of vertical room
(offset 44.8 um + strap width 4.48 um) and fails outright, in `pdngen`,
before placement is even attempted (`PDN-0185`), against the `fit`
attempt's 40 um-tall reserved box -- a PDN-config mismatch (the mesh is
sized for macros far larger than this one), not a finding about whether the
*netlist* fits. `fit`'s own `POWER_FIT` therefore carries row rails only --
the floor every standard-cell macro needs regardless of size, consistent
with a macro this small having its `vdd`/`vss` stitched into
`layout/adc-top/`'s own upper-metal rails at composition time (out of scope
here) rather than carrying an independent copy of that mesh.

Why the binding corner is `ss_125C_3v00`, not `klt`'s nominal pick
-------------------------------------------------------------------------
`sim/README.md`'s own ratified PVT grid is process ss/tt/ff x -40/27/125 C x
+-10% supply (2.97/3.30/3.63 V) -- so the slow/hot/low-supply corner is
`ss`/125 C/~2.97 V, and `ss_125C_3v00` is this library's closest shipped
deck to exactly that point (matching `2AMLogic/gf180-trng`'s own reasoning
for the identical corner choice). Implementing *at* the binding corner is
what makes this run's own (non-signoff, informational) slack numbers mean
something, rather than a synthesis-style typical-corner mapping pass.

Why the clock target is 16 MHz (62.5 ns), not an arbitrary loose value
-------------------------------------------------------------------------
`spec/decision-records/DR-0003-clocking.md` ratifies **16 MHz @ 1 MS/s**
(target) as this design's own real external clock rate -- not an estimate
this script invents headroom around. `constraints.clock_period_ns` is
therefore 62.5 ns, the literal ratified target rate, at `clk`
(`design/sar-logic/rtl/sar_ctrl.v`'s own clock port name).

What this is not
-------------------------------------------------------------------------
Not signoff timing (informational OpenROAD pre-signoff STA over an ideal,
SDC-only clock with global-routing-estimated parasitics -- no extraction, no
SPEF; that is a separate, explicitly out-of-scope follow-on, DR-0023's own
(c)). Not a floorplan change, and not DR-0024's pending area-budget
ratification -- both explicitly out of scope for this issue. Not a claim
about composing this macro into `layout/adc-top/adc_block` -- that
composition (wiring this macro's own `vdd`/`vss`/`clk`/... pins into the
block's existing rails) is not attempted here.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAYOUT_DIR = REPO_ROOT / "layout"
SAR_LOGIC_DIR = LAYOUT_DIR / "sar-logic"
REPORTS_DIR = SAR_LOGIC_DIR / "reports"

# `layout/` is a plain directory, not an installed package, and this script
# is run as `python3 layout/sar-logic/build.py` (sys.path[0] is
# layout/sar-logic), so the shared klt_env module has to be put on the path
# explicitly -- same convention `layout/drc/run_drc.py` /
# `layout/lvs/run_lvs.py` already use for `toolchain_pin`.
if str(LAYOUT_DIR) not in sys.path:
    sys.path.insert(0, str(LAYOUT_DIR))

import klt_env  # noqa: E402  (import follows the sys.path setup above)

sys.path.insert(0, str(REPO_ROOT))

#: `klt place-and-route`'s own scratch directory -- deliberately under
#: `layout/.work/`, gitignored, and (like `2AMLogic/gf180-trng`'s own
#: `WORK_DIR`) NOT the system tempdir: `layout/openroad_docker.sh` bind-mounts
#: `$(pwd)` (== REPO_ROOT, since `_run_klt` runs `klt` with `cwd=REPO_ROOT`)
#: into the container at the identical absolute path, so every absolute path
#: OpenROAD's generated Tcl scripts reference must resolve *inside* that
#: mount.
WORK_DIR = LAYOUT_DIR / ".work" / "sar-logic-pnr"

#: The already-committed, already-synthesized SAR-sequencer netlist (issue
#: #272, merged via PR #276) -- read-only input to this script.
NETLIST_PATH = (
    REPO_ROOT
    / "design"
    / "sar-logic"
    / "flow"
    / "sar_ctrl"
    / "netlist"
    / "sar_ctrl.mcu7t5v0.synth.v"
)
HDL_TOPLEVEL = "sar_ctrl_a"

#: The library `design/sar-logic/rtl/README.md` chose (issue #272) precisely
#: because it leaves the most headroom against this reserved footprint --
#: NOT `gf180mcu_fd_sc_mcu9t5v0`.
CELL_LIBRARY = "gf180mcu_fd_sc_mcu7t5v0"

#: This library's own ORFS platform site (verified against the installed
#: LEF's own `SITE GF018hv5v_mcu_sc7 ;` declaration, every MACRO, and against
#: `OpenROAD-flow-scripts`' `flow/platforms/gf180/config.mk`,
#: `TRACK_OPTION=7t` branch, `PLACE_SITE`).
SITE = "GF018hv5v_mcu_sc7"

#: The block's own ratified slow/hot/low-supply corner -- see module
#: docstring for the derivation from `sim/README.md`'s PVT grid.
CORNER = "ss_125C_3v00"

#: `OpenROAD-flow-scripts`' own gf180 platform IO layers -- identical for
#: both `TRACK_OPTION` values (`flow/platforms/gf180/config.mk`).
IO = {"layer_h": "Metal3", "layer_v": "Metal4"}

#: PDN straps -- this platform's own `pdn_grid_strategy_7t_6M.cfg` (fetched
#: from `The-OpenROAD-Project/OpenROAD-flow-scripts` @ `master`,
#: `flow/platforms/gf180/openROAD/pdn/`, read 2026-09-14), the 7-track
#: sibling of the 9-track config `2AMLogic/gf180-trng`'s own `POWER` cites.
#: `Metal1` follows the standard-cell rows at this site's own rail
#: pitch/width (3.92 um pitch, 0.6 um wide -- narrower than the 9-track
#: config's 5.04 um/0.9 um, since the 7-track row is itself shorter);
#: `Metal4`/`Metal5` straps are numerically identical between the two
#: configs (both platforms share the same upper-metal PDN mesh regardless of
#: row height). See module docstring for why the net names are `vdd`/`vss`,
#: not `vddd`/`vss`.
POWER = {
    "power_net": "vdd",
    "ground_net": "vss",
    "straps": [
        {"layer": "Metal1", "width_um": 0.6, "pitch_um": 3.92, "followpins": True},
        {"layer": "Metal4", "width_um": 4.48, "pitch_um": 44.8, "offset_um": 22.4},
        {"layer": "Metal5", "width_um": 4.48, "pitch_um": 89.6, "offset_um": 44.8},
    ],
}

#: The `fit` attempt's own PDN -- row-rail (`Metal1`/`followpins`) only, no
#: `Metal4`/`Metal5` straps. `pdn_grid_strategy_7t_6M.cfg`'s upper-metal mesh
#: above is sized for macros far larger than the 40 um-tall reserved region
#: this attempt targets: measured live, its own `Metal5` strap alone needs
#: 49.3 um of vertical room (offset 44.8 um + strap width 4.48 um) against
#: this box's ~31.36 um usable core height, and fails OpenROAD's own
#: `pdngen` outright (`PDN-0185`) before placement is even attempted -- a
#: PDN-config mismatch, not a finding about whether the *netlist* fits. Row
#: rails are the floor every standard-cell macro needs regardless of size;
#: a duplicate upper-metal mesh at this scale is not otherwise load-bearing
#: because this macro's own `vdd`/`vss` pins are meant to be stitched into
#: `layout/adc-top/`'s own analog-region rails at composition time (out of
#: scope here -- see module docstring), the same way any macro this small
#: inherits its parent block's upper-metal strapping rather than carrying
#: an independent copy of it.
POWER_FIT = {
    "power_net": "vdd",
    "ground_net": "vss",
    "straps": [
        {"layer": "Metal1", "width_um": 0.6, "pitch_um": 3.92, "followpins": True},
    ],
}

#: `sar_ctrl.v`'s own clock port name (`design/sar-logic/rtl/sar_ctrl.v`) and
#: DR-0003's ratified target rate -- see module docstring.
CONSTRAINTS = {"clock_port": "clk", "clock_period_ns": 62.5}
SEED = 1
TARGET_STAGE = "route"

DECK = "gf180mcu"

#: How far the merged GDS's own extent may differ from the DEF's own
#: `DIEAREA` before this being treated as a merge defect rather than the
#: standard cells' own well/implant overhang -- same tolerance and rationale
#: as `2AMLogic/gf180-trng`'s `GDS_EXTENT_TOLERANCE_PCT`.
GDS_EXTENT_TOLERANCE_PCT = 5.0

EXIT_OK = 0
EXIT_ENVIRONMENT = 3
EXIT_FLOW_FAILURE = 4


class PrError(RuntimeError):
    """A place-and-route run could not even be attempted."""


# --------------------------------------------------------------------------- #
# Reserved footprint -- read live from the generator, never hand-copied
# --------------------------------------------------------------------------- #


def _reserved_footprint_um() -> dict:
    """The SAR-logic reserved region's own as-drawn dimensions, read directly
    off `layout/adc-top/gen_adc_top.py`'s live constants and geometry --
    never a number copied from a README table, which can (and, as this run
    discovered, did) go stale relative to the generator that actually draws
    it.

    Returns the *interior* box (`digital_box` in that generator -- the area
    available to a placed macro, before its own guard ring) and the
    *as-drawn* box including the ring (`digital_ring` -- what
    `layout/adc-top/README.md`'s area table calls "SAR-logic reserved region
    incl. its ring"), both derived the same way that generator derives them:
    `max(SAR_RESERVED_W, analog_ring.width() // 3)` wide, `SAR_RESERVED_H`
    tall, enlarged by `GUARD_RING_W` on every side for the ring box. Building
    the real `adc_block` layout (importing `gen_adc_top.py` and calling its
    own `build()`) is deliberately avoided here -- that is a multi-second,
    heavier operation this script does not otherwise need, and re-deriving
    the two numbers this function needs from the generator's own *published*
    constants plus its one already-computed, already-committed result
    (`layout/adc-top/area.json`'s `sar_logic_reserved`) is enough to recover
    both boxes exactly, without re-running the generator.
    """
    import importlib.util

    gen_path = LAYOUT_DIR / "adc-top" / "gen_adc_top.py"
    spec = importlib.util.spec_from_file_location("gen_adc_top", gen_path)
    mod = importlib.util.module_from_spec(spec)
    # Importing (not running __main__) only defines constants/functions --
    # no layout is built and nothing is written.
    spec.loader.exec_module(mod)

    area_json = json.loads((LAYOUT_DIR / "adc-top" / "area.json").read_text())
    ring_area_um2 = area_json["areas_um2"]["sar_logic_reserved"]

    guard_w = mod.GUARD_RING_W * mod.geo.DBU_UM
    reserved_h = mod.SAR_RESERVED_H * mod.geo.DBU_UM
    ring_h = reserved_h + 2 * guard_w
    ring_w = ring_area_um2 / ring_h
    box_w = ring_w - 2 * guard_w

    return {
        "ring_area_um2": ring_area_um2,
        "ring_w_um": ring_w,
        "ring_h_um": ring_h,
        "box_w_um": box_w,
        "box_h_um": reserved_h,
        "box_area_um2": box_w * reserved_h,
        "guard_ring_w_um": guard_w,
        "source": "layout/adc-top/gen_adc_top.py + layout/adc-top/area.json (live, not hand-copied)",
    }


# --------------------------------------------------------------------------- #
# Environment
# --------------------------------------------------------------------------- #


def _openroad_on_path() -> bool:
    return shutil.which("openroad") is not None


def _ensure_openroad_reachable() -> list[str]:
    """Put a `layout/openroad_docker.sh`-backed `openroad` shim on `$PATH`
    when no native `openroad` is already there and `docker` is available --
    mirrors `2AMLogic/gf180-trng`'s own `_ensure_openroad_reachable`. Never
    overrides a native `openroad`."""
    if _openroad_on_path():
        return []
    if shutil.which("docker") is None:
        return [
            "openroad is not on PATH and docker is not on PATH either -- "
            "see layout/sar-logic/README.md's 'OpenROAD' section"
        ]
    shim_dir = Path(tempfile.mkdtemp(prefix="klt-openroad-shim-"))
    shim = shim_dir / "openroad"
    shim.symlink_to(LAYOUT_DIR / "openroad_docker.sh")
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    return []


def _check_environment() -> list[str]:
    missing = []
    klt = shutil.which("klt")
    if klt is None:
        missing.append("klayout-tools (`klt`) is not on PATH")
    if klt_env.resolve_pdk(klt) is None if klt else True:
        pass  # resolve_pdk raises ToolingError itself; caught by caller
    if not NETLIST_PATH.is_file():
        missing.append(
            f"{NETLIST_PATH.relative_to(REPO_ROOT)} is missing -- run "
            "`python3 design/sar-logic/flow/synth_sar_ctrl.py` first (#272)"
        )
    missing += _ensure_openroad_reachable()
    return missing


# --------------------------------------------------------------------------- #
# klt invocation
# --------------------------------------------------------------------------- #


def _run_klt(args: list[str], pdk_variant: str | None, timeout_s: int) -> dict:
    """Run `klt <args> --format json` from the repo root and parse the
    result. Raises `FlowError`-equivalent (`PrError`) with `klt`'s own error
    text on a non-zero exit -- see module docstring: a documented failure to
    reach `target_stage` is a normal outcome for this script's `fit`
    attempt, not a tooling problem, and is handled by the caller rather than
    here.
    """
    argv = ["klt", *args, "--format", "json"]
    if pdk_variant:
        argv += ["--pdk", pdk_variant]
    done = subprocess.run(
        argv, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=timeout_s
    )
    raw = done.stdout.strip() or done.stderr.strip()
    if not raw:
        raise PrError(f"`{' '.join(argv)}` produced no output (exit {done.returncode})")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        snippet = raw[:4000] + ("... [truncated]" if len(raw) > 4000 else "")
        raise PrError(
            f"`{' '.join(argv)}` emitted unparseable output (exit {done.returncode}): "
            f"{exc}\n{snippet}"
        ) from exc
    return payload


# --------------------------------------------------------------------------- #
# One P&R attempt
# --------------------------------------------------------------------------- #


def _write_request(request_path: Path, floorplan: dict, *, power: dict | None) -> None:
    request: dict = {
        "schema": "klt.place_and_route.request/1",
        "engine": "openroad",
        "netlist": str(NETLIST_PATH),
        "hdl_toplevel": HDL_TOPLEVEL,
        "pdk": {"cell_library": CELL_LIBRARY, "corner": CORNER},
        "floorplan": floorplan,
        "io": dict(IO),
        "constraints": dict(CONSTRAINTS),
        "seed": SEED,
        "target_stage": TARGET_STAGE,
    }
    if power is not None:
        request["power"] = {
            "power_net": power["power_net"],
            "ground_net": power["ground_net"],
            "straps": [dict(strap) for strap in power["straps"]],
        }
    request_path.write_text(json.dumps(request, indent=2) + "\n")


def attempt(
    name: str, floorplan: dict, *, power: dict | None, pdk_variant: str | None
) -> dict:
    """Run one `klt place-and-route` attempt. Always returns a dict with a
    `"outcome"` key (`"ok"` or `"failed"`) -- never raises for a documented
    engine failure to reach `target_stage`, since (per module docstring)
    that is this script's own valid outcome for the `fit` attempt. Raises
    `PrError` only for an environment problem (missing tool/PDK/input)."""
    work_dir = WORK_DIR / name
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    request_path = work_dir / "request.json"
    _write_request(request_path, floorplan, power=power)

    started = time.time()
    try:
        payload = _run_klt(
            ["place-and-route", str(request_path)], pdk_variant, timeout_s=3600
        )
    except PrError as exc:
        return {
            "outcome": "failed",
            "attempt": name,
            "request": json.loads(request_path.read_text()),
            "elapsed_s": round(time.time() - started, 1),
            "error": str(exc),
        }

    if "error" in payload:
        return {
            "outcome": "failed",
            "attempt": name,
            "request": json.loads(request_path.read_text()),
            "elapsed_s": round(time.time() - started, 1),
            "error": payload["error"].get("message", json.dumps(payload["error"])),
            "raw_error": payload["error"],
        }

    return {
        "outcome": "ok",
        "attempt": name,
        "request": json.loads(request_path.read_text()),
        "elapsed_s": round(time.time() - started, 1),
        "response": payload,
    }


# --------------------------------------------------------------------------- #
# Checks over a successful response (mirrors 2AMLogic/gf180-trng's build.py)
# --------------------------------------------------------------------------- #


def _gds_extent_um(gds_path: Path) -> tuple[float, float]:
    # `klt stats` (unlike `place-and-route`/`drc`) takes no `--pdk` -- it
    # reads geometry straight out of the GDS file and never resolves a PDK
    # install, so `_run_klt` is called with `pdk_variant=None` here
    # regardless of the caller's own resolved variant.
    box = _run_klt(
        ["stats", str(gds_path.relative_to(REPO_ROOT))], None, timeout_s=900
    )["bbox_um"]
    return (box["width"], box["height"])


def _gds_geometry_check(
    gds_path: Path, die_w_um: float, die_h_um: float
) -> dict:
    width_um, height_um = _gds_extent_um(gds_path)
    ratios = (width_um / die_w_um, height_um / die_h_um)
    worst = max(abs(ratio - 1.0) for ratio in ratios)
    return {
        "status": "ok" if worst * 100.0 <= GDS_EXTENT_TOLERANCE_PCT else "mismatch",
        "def_die_um": [die_w_um, die_h_um],
        "gds_extent_um": [round(width_um, 4), round(height_um, 4)],
        "gds_over_def_ratio": [round(ratios[0], 4), round(ratios[1], 4)],
        "tolerance_pct": GDS_EXTENT_TOLERANCE_PCT,
    }


def run_drc(pdk_variant: str | None, gds_path: Path) -> dict:
    """`klt drc` over the merged GDS -- the same deck and invocation shape
    `layout/drc/run_drc.py` exercises for every other cell in this
    repository (`klt drc <file> --deck gf180mcu --format json`)."""
    return _run_klt(
        ["drc", str(gds_path.relative_to(REPO_ROOT)), "--deck", DECK],
        pdk_variant,
        timeout_s=1800,
    )


def _drc_summary(payload: dict) -> dict:
    return {
        "status": payload.get("status"),
        "deck": payload.get("deck"),
        "violation_count": payload.get("violation_count"),
        "rule_counts": payload.get("rule_counts"),
    }


def finalize_success(
    result: dict, *, pdk_variant: str | None, commit_prefix: str
) -> dict:
    """For a successful attempt: copy artifacts to committed paths, run the
    geometry check and (if it passes) `klt drc`. Mutates nothing in
    `result`; returns a dict of what was written/checked."""
    response = result["response"]
    written: list[Path] = []
    checks: dict = {}
    warnings: list[str] = []

    verilog_path = response.get("verilog_path")
    def_path = response.get("def_path")
    gds_path = response.get("gds_path")

    pnr_v = SAR_LOGIC_DIR / f"{commit_prefix}.pnr.v"
    def_out = SAR_LOGIC_DIR / f"{commit_prefix}.def"
    gds_out = SAR_LOGIC_DIR / f"{commit_prefix}.gds"

    if verilog_path and Path(verilog_path).is_file():
        shutil.copyfile(verilog_path, pnr_v)
        written.append(pnr_v)

    if def_path and Path(def_path).is_file():
        shutil.copyfile(def_path, def_out)
        written.append(def_out)

    drc_summary = None
    if gds_path and Path(gds_path).is_file() and def_path:
        die_w = response.get("die_area_um2")
        # die_area_um2 is an AREA, not a width/height pair -- read the real
        # DIEAREA rectangle out of the DEF itself instead of assuming a
        # square die.
        die_w_um, die_h_um = _def_die_wh(Path(def_path))
        geometry = _gds_geometry_check(Path(gds_path), die_w_um, die_h_um)
        checks["gds_geometry"] = geometry
        if geometry["status"] == "ok":
            shutil.copyfile(gds_path, gds_out)
            written.append(gds_out)
            drc_summary = _drc_summary(run_drc(pdk_variant, gds_out))
            if drc_summary.get("status") != "clean":
                warnings.append(
                    f"klt drc over the merged GDS: {drc_summary.get('status')} "
                    f"({drc_summary.get('violation_count')} violations)"
                )
        else:
            warnings.append(
                "merged GDS extent does not match the DEF's own DIEAREA "
                f"(ratio {geometry['gds_over_def_ratio']}) -- GDS not committed"
            )
    else:
        checks["gds_geometry"] = {"status": "skipped", "reason": "no GDS/DEF returned"}

    return {
        "written": [str(p.relative_to(REPO_ROOT)) for p in written],
        "checks": checks,
        "drc": drc_summary,
        "warnings": warnings,
    }


def _def_die_wh(def_path: Path) -> tuple[float, float]:
    import re

    text = def_path.read_text(errors="replace")
    units = re.search(r"^UNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;", text, re.M)
    die = re.search(
        r"^DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*;",
        text,
        re.M,
    )
    if not units or not die:
        raise PrError(f"could not parse UNITS/DIEAREA out of {def_path}")
    dbu = int(units.group(1))
    x0, y0, x1, y1 = (int(v) for v in die.groups())
    return ((x1 - x0) / dbu, (y1 - y0) / dbu)


# --------------------------------------------------------------------------- #
# The two configurations
# --------------------------------------------------------------------------- #


def _fit_floorplan(reserved: dict) -> dict:
    """An `"explicit"` floorplan pinned to the reserved region's own live
    interior box (`reserved["box_w_um"]` x `reserved["box_h_um"]`), with a
    1 um core margin on every side -- enough for `pdngen`'s own ring-strap
    geometry and IO pin access, not a loosening of the question this attempt
    asks. The reserved region's own guard ring (drawn separately by
    `layout/adc-top/gen_adc_top.py`) is NOT part of this box -- it is
    clearance this attempt does not need to re-spend."""
    margin = 1.0
    die_w, die_h = reserved["box_w_um"], reserved["box_h_um"]
    return {
        "method": "explicit",
        "die_area_um": [0.0, 0.0, die_w, die_h],
        "core_area_um": [margin, margin, die_w - margin, die_h - margin],
        "site": SITE,
    }


def _reference_floorplan() -> dict:
    """A generous `"utilization"` floorplan -- the same style
    `2AMLogic/gf180-trng`'s own first P&R attempt uses (its own `FLOORPLAN`
    constant): a square aspect ratio and a real margin, chosen so this run
    answers "how much area does a comfortably-routable P&R of this netlist
    actually need", independent of whether that area is shaped like the
    reserved region. 50% (tighter than gf180-trng's own 40%, since this
    design is two orders of magnitude smaller and the reserved footprint is
    itself tight) leaves real routing headroom while still landing a
    meaningfully small die."""
    return {
        "method": "utilization",
        "utilization_pct": 50,
        "aspect_ratio": 1.0,
        "core_margin_um": 5.0,
        "site": SITE,
    }


def build(*, run_fit: bool, run_reference: bool) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    missing = _check_environment()
    if missing:
        for m in missing:
            print(f"ERROR  {m}", file=sys.stderr)
        return EXIT_ENVIRONMENT

    klt = shutil.which("klt")
    pdk_info = klt_env.resolve_pdk(klt)
    pdk_variant = pdk_info.get("variant")
    reserved = _reserved_footprint_um()

    print(f"klt: {klt_env.klt_version(klt)}")
    print(f"PDK: {pdk_variant} ({pdk_info.get('version')})")
    print(
        "reserved SAR-logic footprint (live, layout/adc-top/gen_adc_top.py): "
        f"interior {reserved['box_w_um']:.2f} x {reserved['box_h_um']:.2f} um "
        f"= {reserved['box_area_um2']:.2f} um^2; incl. guard ring "
        f"{reserved['ring_w_um']:.2f} x {reserved['ring_h_um']:.2f} um "
        f"= {reserved['ring_area_um2']:.2f} um^2"
    )

    overall_ok = True
    results: dict[str, dict] = {"reserved_footprint_um": reserved}

    if run_fit:
        print("\n=== attempt 1: fit -- explicit floorplan pinned to the reserved box ===")
        fit_result = attempt(
            "fit", _fit_floorplan(reserved), power=POWER_FIT, pdk_variant=pdk_variant
        )
        if fit_result["outcome"] == "ok":
            try:
                fit_result["post"] = finalize_success(
                    fit_result, pdk_variant=pdk_variant, commit_prefix="sar_ctrl_fit"
                )
            except PrError as exc:
                # A post-processing tooling problem (e.g. `klt stats`/`klt
                # drc` misbehaving) is still recorded rather than crashing
                # this script uncleanly mid-run -- the P&R engine result
                # itself already succeeded and is worth keeping.
                overall_ok = False
                fit_result["post"] = {"error": str(exc)}
                print(f"  P&R OK but post-processing FAILED: {exc}")
            print(
                f"  OK  stage_reached={fit_result['response'].get('stage_reached')} "
                f"die_area_um2={fit_result['response'].get('die_area_um2')} "
                f"utilization_pct={fit_result['response'].get('utilization_pct')}"
            )
        else:
            print(f"  FAILED (documented outcome): {fit_result['error']}")
        results["fit"] = fit_result
        (REPORTS_DIR / "place_and_route_fit.json").write_text(
            json.dumps(fit_result, indent=2) + "\n"
        )

    if run_reference:
        print("\n=== attempt 2: reference -- generous utilization floorplan ===")
        ref_result = attempt(
            "reference", _reference_floorplan(), power=POWER, pdk_variant=pdk_variant
        )
        if ref_result["outcome"] == "ok":
            try:
                ref_result["post"] = finalize_success(
                    ref_result, pdk_variant=pdk_variant, commit_prefix="sar_ctrl_reference"
                )
            except PrError as exc:
                overall_ok = False
                ref_result["post"] = {"error": str(exc)}
                print(f"  P&R OK but post-processing FAILED: {exc}")
            resp = ref_result["response"]
            print(
                f"  OK  stage_reached={resp.get('stage_reached')} "
                f"die_area_um2={resp.get('die_area_um2')} "
                f"core_area_um2={resp.get('core_area_um2')} "
                f"utilization_pct={resp.get('utilization_pct')}"
            )
            for w in ref_result["post"].get("warnings", []):
                print(f"  WARNING  {w}")
        else:
            overall_ok = False
            print(f"  FAILED: {ref_result['error']}")
        results["reference"] = ref_result
        (REPORTS_DIR / "place_and_route_reference.json").write_text(
            json.dumps(ref_result, indent=2) + "\n"
        )

    summary_path = REPORTS_DIR / "place_and_route_summary.json"
    summary_path.write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(f"\nwrote {summary_path.relative_to(REPO_ROOT)}")

    return EXIT_OK if overall_ok else EXIT_FLOW_FAILURE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--explicit-only",
        action="store_true",
        help="run only the 'fit' (explicit reserved-footprint) attempt",
    )
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="run only the 'reference' (generous utilization) attempt",
    )
    args = parser.parse_args(argv)
    if args.explicit_only and args.reference_only:
        parser.error("--explicit-only and --reference-only are mutually exclusive")

    return build(
        run_fit=not args.reference_only,
        run_reference=not args.explicit_only,
    )


if __name__ == "__main__":
    raise SystemExit(main())
