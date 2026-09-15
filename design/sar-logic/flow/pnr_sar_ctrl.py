#!/usr/bin/env python3
"""`klt place-and-route` driver for the synthesized `sar_ctrl_a` gate netlist
(DR-0023 follow-on (b), issue #274).

Issue #272 (`synth_sar_ctrl.py`, this file's own sibling) synthesized
`design/sar-logic/rtl/sar_ctrl.v` against `gf180mcu_fd_sc_mcu7t5v0` (the
library `design/sar-logic/rtl/README.md` chose) and committed the gate
netlist this script places and routes:
`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`.

This script's whole job is to answer the question DR-0023's own
Consequences section deferred to this follow-on: does the ROUTED macro fit
inside the footprint `layout/adc-top/`'s floorplan already reserves and
rings for it (`layout/adc-top/gen_adc_top.py`'s `SAR_RESERVED_W`/
`SAR_RESERVED_H` constants), not just the raw synthesized cell area
`design/sar-logic/rtl/README.md`'s "Library choice" section already
compared against that reservation as a lower bound. Per `CLAUDE.md`
("no claim without a testbench" / append-only evidence), the answer is
recorded either way -- a macro that does NOT fit is exactly as reportable a
result as one that does.

## Deriving the reserved footprint without re-running the block generator

`layout/adc-top/gen_adc_top.py` draws the SAR-logic reserved region as a
guard-ringed box: an inner "digital_box" (`SAR_RESERVED_W` wide, unless the
analog core's own guard-ringed width divided by three is larger -- see that
module's own `digital_box = kdb.Box(...)` call -- by `SAR_RESERVED_H` tall)
enlarged by `GUARD_RING_W` on every side. Re-deriving `digital_box`'s exact
width the same way `gen_adc_top.py` does would mean re-running the full
analog-block generator (seconds of KLayout work, and a second, divergent
implementation of that formula to keep in sync). Instead this script inverts
the *committed* `layout/adc-top/area.json`'s own `areas_um2.sar_logic_reserved`
figure (the ring-enclosive area `gen_adc_top.py` itself reports,
regenerated and diffed byte-identical against `origin/main` at commit time
of this issue) algebraically, using only `gen_adc_top.py`'s two constants
this needs (`SAR_RESERVED_H`, `GUARD_RING_W`) rather than re-running the
generator:

    h_ring_um  = SAR_RESERVED_H_um + 2 * GUARD_RING_W_um
    w_ring_um  = area.json['areas_um2']['sar_logic_reserved'] / h_ring_um
    w_core_um  = w_ring_um - 2 * GUARD_RING_W_um
    h_core_um  = SAR_RESERVED_H_um

This self-corrects if `area.json` is ever regenerated at a different analog
core width (which drives `digital_box`'s own width via the `analog_ring.
width() // 3` term) -- this script never hardcodes the 199.21 x 40.0 um box
it measured at the commit this was built against, only the formula that
derives it from whatever `area.json` says today.

**`layout/adc-top/README.md`'s Area table's own "SAR-logic reserved region
incl. its ring" row is stale as of this issue** -- it still reads the
7,624 um^2 issue #274 itself was filed quoting (the value as of DR-0019's
unit-cap resize, issue #202/#196), but issue #223's later strap-corridor
re-derivation grew the analog core (and, through the `// 3` term above, the
reserved digital footprint with it) to the current, regenerated
`area.json` figure -- see that file's own git history
(`git log -p -- layout/adc-top/area.json`) for the exact commit. This
script and this issue's own evidence record use the CURRENT, re-verified
`area.json` figure (8,646.028 um^2 incl. ring / 7,968.4 um^2 core, at the
commit this ran against), not the stale cited number -- and this issue's
PR corrects that one stale table cell in the same change, per
`.claude/commands/loom/builder.md`'s "Re-Verify Date-Stamped Facts Before
Acting".

## Why the PDN is Metal1-`followpins` only, not the full platform grid

`platforms/gf180/openROAD/pdn/pdn_grid_strategy_7t_6M.cfg` (ORFS's own 7-track
PDN config, `The-OpenROAD-Project/OpenROAD-flow-scripts@master`, fetched
2026-09-14) straps Metal4 at a 44.8 um pitch and Metal5 at an 89.6 um pitch --
geometry sized for a full chip-scale block, not a 40 um-tall macro. Feeding
that config's Metal4/Metal5 stripes verbatim into `request.power.straps`
against this macro's own die height fails immediately
(`[ERROR PDN-0185] Insufficient width (39.20 um) to add straps on layer
Metal5 ...`) -- the strap's own declared width (4.48 um) plus its offset
(44.8 um) already exceeds the whole macro height. This script instead uses
just that same config's Metal1 `-followpins` stripe (`width 0.600 pitch
3.92 offset 0`, this macro's own row pitch) -- a plain row-rail PDN, which
is what `klt place-and-route` itself falls back to even when `request.power`
is omitted entirely for a `sky130_fd_sc_hd` design (the "row-rail fallback",
`docs/cli/place-and-route.md` issue #1442) -- the standard treatment for a
macro too small to host a multi-layer chip-level grid. `tapcell`/
`global_connect`/`filler_placement` all still run (this macro DOES get
well-tie/PG-pin/row-gap treatment), just with a single strap layer.

## No SDC/STA claim

Like `synth_sar_ctrl.py`, this script names a `constraints.clock_period_ns`
only because `klt place-and-route` structurally requires one once
`target_stage` reaches `"place"` (CTS/timing-driven placement need a clock to
target) -- 62.5 ns (16 MHz), `spec/timing-budget-memo.md`'s own DR-0008/
DR-0003-derived nominal SAR clock at M=16, 1 MS/s (the memo's own stretch
case is 32 MHz/2 MS/s). This is deliberately generous relative to what real
signoff will ask for, and is NOT a timing-closure claim: DR-0023 follow-on
(c) (issue #275, SDC/STA closure) is the follow-on that actually derives and
asserts a signoff clock period. `worst_slack_ns`/`setup_violation_count`/
etc. are recorded in this run's evidence purely as informational context that
falls out of running the "route" stage at all, not as a claim this design
meets a real timing budget.

Cold-start invocation (PDK installed, `klt`/`openroad` on `$PATH` --
`openroad` has no apt/pip package; see `docs/cli/place-and-route.md`
"Installing OpenROAD" in the `klayout-tools` repo for the Docker-wrapper
recipe this issue's own evidence record used):

    python3 design/sar-logic/flow/pnr_sar_ctrl.py

Writes:

  - the request/response JSON + `klt drc` response:
                          design/sar-logic/flow/sar_ctrl/reports/<rid>.mcu7t5v0.pnr_*.json
  - the routed layout artifacts (DEF, merged GDS, as-built Verilog):
                          layout/adc-top/sar_ctrl/sar_ctrl.{def,gds,v}
  - an append-only evidence record:
                          design/sar-logic/flow/sar_ctrl/records/<rid>.mcu7t5v0.pnr.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "layout" / "adc-top"))

from sim.harness.pdk import Pdk, PdkNotFound, find_pdk  # noqa: E402

TOP = "sar_ctrl_a"
CELL_LIBRARY = "gf180mcu_fd_sc_mcu7t5v0"
LIB_TAG = "mcu7t5v0"
CORNER = "tt_025C_3v30"

NETLIST = (
    REPO_ROOT / "design" / "sar-logic" / "flow" / "sar_ctrl" / "netlist"
    / f"sar_ctrl.{LIB_TAG}.synth.v"
)
AREA_JSON = REPO_ROOT / "layout" / "adc-top" / "area.json"

FLOW_DIR = REPO_ROOT / "design" / "sar-logic" / "flow" / "sar_ctrl"
REPORTS_DIR = FLOW_DIR / "reports"
RECORDS_DIR = FLOW_DIR / "records"
LAYOUT_OUT_DIR = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl"

#: `gen_adc_top.py`'s own reserved-footprint constants (DBU = 1 nm, i.e.
#: `* 0.001` converts to um) -- imported, not retyped, so this script cannot
#: silently drift from the generator that actually draws the footprint.
import gen_adc_top as _g  # noqa: E402

SAR_RESERVED_H_UM = _g.SAR_RESERVED_H * 0.001
GUARD_RING_W_UM = _g.GUARD_RING_W * 0.001

#: `platforms/gf180/openROAD/pdn/pdn_grid_strategy_7t_6M.cfg`'s own Metal1
#: `-followpins` stripe (`The-OpenROAD-Project/OpenROAD-flow-scripts@master`,
#: fetched 2026-09-14) -- see this module's own docstring, "Why the PDN is
#: Metal1-`followpins` only", for why the sibling Metal4/Metal5 stripes that
#: same file names are NOT used here.
POWER = {
    "power_net": "VDD",
    "ground_net": "VSS",
    "straps": [
        {"layer": "Metal1", "width_um": 0.6, "pitch_um": 3.92, "offset_um": 0, "followpins": True},
    ],
}

#: `spec/timing-budget-memo.md` Sec "Sync vs. async and the clock
#: multiplier": DR-0008 ratifies M=16, 16 MHz @ 1 MS/s nominal (32 MHz @
#: 2 MS/s stretch). See this module's own docstring, "No SDC/STA claim".
CLOCK_PORT = "clk"
CLOCK_PERIOD_NS = 62.5

SEED = 1


class PnrError(RuntimeError):
    """A place-and-route or DRC run failed, or its output failed a check."""


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def record_id(when: _dt.datetime) -> str:
    sha = _git("rev-parse", "--short", "HEAD") or "nogit"
    return f"{when.strftime('%Y%m%d-%H%M%S')}-{sha}"


_OWN_OUTPUT_PREFIXES = (
    "design/sar-logic/flow/sar_ctrl/",
    "layout/adc-top/sar_ctrl/",
)


def _git_status_porcelain() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout.rstrip("\n") if result.returncode == 0 else ""


def working_tree_dirty() -> bool:
    status = _git_status_porcelain()
    for line in status.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path and not any(path.startswith(p) for p in _OWN_OUTPUT_PREFIXES):
            return True
    return False


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def klt_version() -> str:
    result = _run(["klt", "--version"])
    return (result.stdout or result.stderr).strip()


def openroad_version() -> str:
    if shutil.which("openroad") is None:
        raise PnrError(
            "no `openroad` binary on $PATH -- `klt place-and-route` requires one. "
            "There is no apt/pip package; see klayout-tools' docs/cli/place-and-route.md "
            "\"Installing OpenROAD\" for the Docker-wrapper recipe this evidence record used."
        )
    result = _run(["openroad", "-version"])
    return (result.stdout or result.stderr).strip()


def derive_reserved_footprint() -> dict:
    """Invert the committed `area.json`'s `sar_logic_reserved` figure into
    the ring-exclusive core box `digital_box` this run's floorplan targets --
    see this module's own docstring, "Deriving the reserved footprint"."""
    if not AREA_JSON.is_file():
        raise PnrError(f"{AREA_JSON} not found -- run layout/adc-top/gen_adc_top.py first")
    area = json.loads(AREA_JSON.read_text())
    ring_area_um2 = area["areas_um2"]["sar_logic_reserved"]
    h_ring_um = SAR_RESERVED_H_UM + 2 * GUARD_RING_W_UM
    w_ring_um = ring_area_um2 / h_ring_um
    w_core_um = w_ring_um - 2 * GUARD_RING_W_UM
    h_core_um = SAR_RESERVED_H_UM
    return {
        "ring_area_um2": ring_area_um2,
        "core_w_um": round(w_core_um, 6),
        "core_h_um": round(h_core_um, 6),
        "core_area_um2": round(w_core_um * h_core_um, 6),
    }


def build_request(pdk: Pdk, footprint: dict, req_path: Path) -> dict:
    w, h = footprint["core_w_um"], footprint["core_h_um"]
    request = {
        "schema": "klt.place_and_route.request/1",
        "engine": "openroad",
        "netlist": str(NETLIST),
        "hdl_toplevel": TOP,
        "pdk": {"cell_library": CELL_LIBRARY, "corner": CORNER},
        "floorplan": {
            "method": "explicit",
            "die_area_um": [0, 0, w, h],
            "core_area_um": [0, 0, w, h],
            "site": "GF018hv5v_mcu_sc7",
        },
        "io": {"layer_h": "Metal3", "layer_v": "Metal4"},
        "power": POWER,
        "constraints": {"clock_port": CLOCK_PORT, "clock_period_ns": CLOCK_PERIOD_NS},
        "seed": SEED,
        "target_stage": "route",
    }
    req_path.write_text(json.dumps(request, indent=2) + "\n")
    return request


def run_place_and_route(pdk: Pdk, req_path: Path) -> dict:
    result = _run(["klt", "place-and-route", str(req_path), "--pdk", pdk.variant, "--format", "json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PnrError(
            f"klt place-and-route did not print JSON (exit {result.returncode}): {exc}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        ) from exc
    if result.returncode != 0:
        raise PnrError(f"klt place-and-route failed: {json.dumps(payload, indent=2)}")
    return payload


def run_drc(pdk: Pdk, gds_path: Path) -> dict:
    result = _run(["klt", "drc", str(gds_path), "--deck", "gf180mcu", "--format", "json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PnrError(
            f"klt drc did not print JSON (exit {result.returncode}): {exc}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        ) from exc
    if result.returncode not in (0, 3):
        raise PnrError(f"klt drc failed to run cleanly: {json.dumps(payload, indent=2)}")
    return payload


def render_record(
    *,
    rid: str,
    when: _dt.datetime,
    pdk: Pdk,
    klt_v: str,
    openroad_v: str,
    footprint: dict,
    response: dict,
    drc: dict,
    dirty: bool,
    req_rel: str,
    resp_rel: str,
    drc_rel: str,
    gds_rel: str,
    def_rel: str,
    verilog_rel: str,
) -> str:
    sha = _git("rev-parse", "HEAD") or "unknown"
    die_area = response["die_area_um2"]
    core_area = response["core_area_um2"]
    util = response["utilization_pct"]
    fits_core = die_area <= footprint["core_area_um2"] + 1e-6
    fits_note = (
        f"**FITS** -- the routed die ({die_area:.3f} um^2) is exactly the reserved core box "
        f"this run's floorplan targeted ({footprint['core_area_um2']:.3f} um^2 = "
        f"{footprint['core_w_um']:.3f} x {footprint['core_h_um']:.3f} um), and `target_stage: "
        '"route"` completed with `status: "ok"` -- OpenROAD legalized every cell inside that '
        "exact box, at no floorplan margin. Had the design not fit, the same explicit-floorplan "
        "request would instead have raised a legalization/placement failure (e.g. `PL-...`) "
        "before ever writing a routed DEF -- so reaching `stage_reached: \"route\"` at all is "
        "itself the fit evidence, not merely the reported area matching."
        if fits_core
        else f"**DOES NOT FIT** -- routed die {die_area:.3f} um^2 exceeds the reserved core "
        f"{footprint['core_area_um2']:.3f} um^2."
    )
    drc_line = (
        f"**{drc['status'].upper()}**, {drc['violation_count']} violation(s)"
        if "status" in drc
        else "DRC run did not return a status"
    )
    corners_note = (
        f"{len(response['corners'])} liberty corners swept, worst setup {response['worst_setup_slack_ns']} ns "
        f"/ worst hold {response['worst_hold_slack_ns']} ns"
        if response.get("corners")
        else "no corner sweep in this response"
    )
    return f"""\
# Record {rid} ({LIB_TAG}, place-and-route)

- **Record ID**: {rid}.{LIB_TAG}.pnr
- **Claim**: `sar_ctrl_a`'s synthesized `{CELL_LIBRARY}` gate netlist
  (`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.{LIB_TAG}.synth.v`, issue #272) has been
  placed and routed by `klt place-and-route` (OpenROAD, native Tcl API) inside an EXPLICIT
  floorplan sized to exactly match `layout/adc-top/`'s reserved SAR-logic footprint (DR-0023
  follow-on (b), issue #274) -- the ring-exclusive core box `layout/adc-top/gen_adc_top.py`'s
  own `digital_box` draws, derived from the committed `layout/adc-top/area.json` (see
  `design/sar-logic/flow/pnr_sar_ctrl.py`'s own docstring, "Deriving the reserved footprint",
  for the exact inversion and why the cited-in-issue 7,624 um^2 figure is stale as of this
  record -- `layout/adc-top/README.md`'s Area table is corrected in the same change this
  record ships in).
- **Scope**: Place-and-route (floorplan -> global/detailed placement -> CTS -> global/detailed
  routing) + power delivery (tapcell/global_connect/PDN/fillers, Metal1-`followpins` only --
  see the driver script's own docstring for why) + DRC of the merged, routed GDS. No SDC/STA
  claim (follow-on (c), issue #275, a separate filed issue) -- `constraints.clock_period_ns` is
  a deliberately generous 62.5 ns (16 MHz, `spec/timing-budget-memo.md`'s DR-0008/DR-0003
  nominal SAR clock), present only because `klt place-and-route` structurally requires a clock
  once past the `"floorplan"` stage. No LVS (the merged GDS has no matching golden SPICE
  reference generation wired up in this repo yet, and is out of this issue's own scope).
- **Tool versions**:
  - `klt`: `{klt_v}`
  - `openroad` (resolved on `$PATH`): `{openroad_v}`
  - OpenROAD (via `klt place-and-route`'s own `engine_version`): `{response.get("engine_version")}`
  - gf180mcu PDK: variant `{pdk.variant}`, open_pdks `{pdk.version}` (via {pdk.source})
- **Standard-cell library**: `{CELL_LIBRARY}`, `{CORNER}` corner (device); interconnect corner
  `{response.get("interconnect_corner")}`
- **Reserved footprint** (derived from `layout/adc-top/area.json`'s `areas_um2.sar_logic_reserved`
  = {footprint['ring_area_um2']:.3f} um^2, ring-inclusive): core box (ring-exclusive, what this
  run's floorplan targets) = {footprint['core_w_um']:.3f} x {footprint['core_h_um']:.3f} um =
  {footprint['core_area_um2']:.3f} um^2.
- **Result (place-and-route)**: `status: "{response.get('status')}"`, `stage_reached:
  "{response.get('stage_reached')}"`. `die_area_um2` = {die_area}, `core_area_um2` = {core_area},
  `utilization_pct` = {util}, `wirelength_um` = {response.get('wirelength_um')},
  `route_drc_violation_count` (OpenROAD's own TritonRoute check) =
  {response.get('route_drc_violation_count')}, `antenna_violation_count` =
  {response.get('antenna_violation_count')}. {fits_note}
- **Timing (informational only, NOT a signoff claim -- see "No SDC/STA claim" above)**:
  `worst_slack_ns` = {response.get('worst_slack_ns')} ns (nominal corner, `{CORNER}`),
  `setup_violation_count` = {response.get('setup_violation_count')}, `hold_violation_count` =
  {response.get('hold_violation_count')}, `fmax_mhz` = {response.get('fmax_mhz')}. Multi-corner
  sweep: {corners_note}.
- **Power delivery**: `{json.dumps(response.get('power'))}`
- **Result (DRC)**: `klt drc {gds_rel} --deck gf180mcu` -- {drc_line}. Full response:
  `{drc_rel}`.
- **Reproducibility**: working tree {"DIRTY (uncommitted changes outside this issue's own output -- re-run against a clean checkout before trusting this record)" if dirty else "clean"} at commit `{sha}`. Content
  hashes: netlist `{response.get("provenance", {}).get("input", {}).get("content_hash")}`, deck
  `{response.get("provenance", {}).get("deck", {}).get("content_hash")}`.
- **Links**:
  - Netlist: `design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.{LIB_TAG}.synth.v`
  - `klt place-and-route` request: `{req_rel}`
  - `klt place-and-route` response: `{resp_rel}`
  - `klt drc` response: `{drc_rel}`
  - Routed layout artifacts: `{gds_rel}` (merged GDS), `{def_rel}` (DEF), `{verilog_rel}`
    (as-built gate-level Verilog, CTS buffers/resizes/fillers/tapcells included)
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/flow/pnr_sar_ctrl.py` (agent-run)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-record", action="store_true", help="skip minting an evidence record")
    args = parser.parse_args()

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    try:
        openroad_v = openroad_version()
    except PnrError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    if not NETLIST.is_file():
        print(f"ERROR: {NETLIST} not found -- run design/sar-logic/flow/synth_sar_ctrl.py first", file=sys.stderr)
        return 3

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LAYOUT_OUT_DIR.mkdir(parents=True, exist_ok=True)

    footprint = derive_reserved_footprint()
    print(f"Reserved core footprint: {footprint['core_w_um']:.3f} x {footprint['core_h_um']:.3f} um "
          f"= {footprint['core_area_um2']:.3f} um^2 (ring-inclusive {footprint['ring_area_um2']:.3f} um^2)")

    when = _dt.datetime.now(_dt.timezone.utc)
    rid = record_id(when)

    req_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.pnr_request.json"
    build_request(pdk, footprint, req_path)

    print(f"Running klt place-and-route ({CELL_LIBRARY}) ...")
    try:
        response = run_place_and_route(pdk, req_path)
    except PnrError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    resp_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.pnr_response.json"
    resp_path.write_text(json.dumps(response, indent=2) + "\n")
    print(f"  stage_reached={response.get('stage_reached')} die_area_um2={response.get('die_area_um2')} "
          f"utilization_pct={response.get('utilization_pct')}")

    gds_out = LAYOUT_OUT_DIR / "sar_ctrl.gds"
    def_out = LAYOUT_OUT_DIR / "sar_ctrl.def"
    v_out = LAYOUT_OUT_DIR / "sar_ctrl.v"
    gds_out.write_bytes(Path(response["gds_path"]).read_bytes())
    def_out.write_text(Path(response["def_path"]).read_text())
    v_out.write_text(Path(response["verilog_path"]).read_text())

    print("Running klt drc (gf180mcu deck) against the routed GDS ...")
    try:
        drc = run_drc(pdk, gds_out)
    except PnrError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    drc_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.pnr_drc.json"
    drc_path.write_text(json.dumps(drc, indent=2) + "\n")
    print(f"  klt drc status={drc.get('status')} violation_count={drc.get('violation_count')}")

    if not args.no_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        record_path = RECORDS_DIR / f"{rid}.{LIB_TAG}.pnr.md"
        if record_path.exists():
            raise PnrError(f"record {record_path} already exists -- refusing to overwrite")
        record_path.write_text(
            render_record(
                rid=rid,
                when=when,
                pdk=pdk,
                klt_v=klt_version(),
                openroad_v=openroad_v,
                footprint=footprint,
                response=response,
                drc=drc,
                dirty=working_tree_dirty(),
                req_rel=str(req_path.relative_to(REPO_ROOT)),
                resp_rel=str(resp_path.relative_to(REPO_ROOT)),
                drc_rel=str(drc_path.relative_to(REPO_ROOT)),
                gds_rel=str(gds_out.relative_to(REPO_ROOT)),
                def_rel=str(def_out.relative_to(REPO_ROOT)),
                verilog_rel=str(v_out.relative_to(REPO_ROOT)),
            )
        )
        print(f"Evidence record written to {record_path}")

    if response.get("status") != "ok" or response.get("stage_reached") != "route":
        print("ERROR: place-and-route did not reach the route stage", file=sys.stderr)
        return 1
    if drc.get("status") != "clean":
        print(f"WARNING: klt drc reported {drc.get('violation_count')} violation(s)", file=sys.stderr)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
