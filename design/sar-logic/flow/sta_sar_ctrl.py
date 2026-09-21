#!/usr/bin/env python3
"""Pre-route, per-corner static timing analysis driver for `sar_ctrl_a`
(DR-0023 follow-on (c), issue #275).

#272 (DR-0023 follow-on (a)) synthesized `sar_ctrl_a` against
`gf180mcu_fd_sc_mcu7t5v0` deliberately making **no** timing claim
(`constraints.clock_period_ns: null`): the only number on record was ABC's
own informational, NOT-signoff, wire-free pre-layout estimate (1847.28 ps,
`mcu9t5v0` build). This driver answers the real question DR-0003 poses: does
this gate netlist meet the 62.5 ns bit-cycle budget (`M = 16` at 1 MS/s), at
every corner in DR-0023's own ratified 3.3 V corner grid?

## Why this does not call `klt sta` (a disclosed tool-gap workaround)

The issue this driver implements asked for `klt sta` against an SDC-
constrained netlist. That command's own contract
(`docs/cli/sta.md`) requires a **routed DEF** as its `def` input --
verified directly against `klayout_tools.post_route_sta`'s own module
docstring ("this verb's `read_def` ... loads an already-complete,
already-routed design") -- and `klt place-and-route`'s `def_path` is `null`
at every `target_stage` short of `"route"` (`docs/cli/place-and-route.md`:
"Populated once `write_def` has run (i.e. `stage_reached` is `"route"`)").
Follow-on (b) (#274, place-and-route) has not produced a routed DEF as of
this run, and running P&R through the `"route"` stage ourselves here would
both duplicate #274's own deliverable-grade scope (footprint fit, DRC, GDS,
`layout/adc-top/README.md`) and risk a race with #274's own concurrent work
-- explicitly out of scope for this issue.

**There is no supported `klt` path from a bare gate-level netlist to a
clock-constrained (SDC-driven), slack-reporting STA result with no DEF at
all.** The only two STA-shaped surfaces `klt` ships are:

  - `klt synthesize`'s integrated `sta` field (`klt_statime_native`): takes
    a netlist directly, no DEF -- but models no clock whatsoever
    (`input_transition_ns`/`output_load_pf` boundary only) and reports raw
    path *delay*, never slack (`docs/cli/synthesize.md` "`sta`" section).
  - `klt sta` (`klt.sta.request/1`): models a real clock and reports real
    slack -- but requires an already-placed-or-routed `def`, which does not
    exist pre-#274.

This is a real, generically useful capability gap (filed per CLAUDE.md's
friction protocol, `2AMLogic/klayout-tools#<TBD>` -- see this driver's own
evidence record for the filed issue number), not a workaround this repo
should quietly paper over. Pending a fix, this driver uses the best tool
that actually exists for a pre-route, clock-constrained slack number:
`klt place-and-route` itself already runs a real OpenSTA session at every
stage from `"place"` onward and reports `worst_slack_ns` (setup WNS),
`total_negative_slack_ns` (setup TNS), `setup_violation_count`, and
`hold_violation_count` at `stage_reached` -- see
`docs/cli/place-and-route.md`'s Response table. Requesting
`target_stage: "place"` (global placement only -- **no** CTS, **no**
detailed routing, **no** antenna repair, **no** DEF/GDS/Verilog export) gets
a real, clock-constrained, OpenSTA-backed setup slack number without ever
reaching the stage that would make this driver's own output a P&R
deliverable.

**Disclosed limitations of this substitution (every one restated in the
evidence record, not just here):**

1. **Independently placed per corner, not one fixed geometry swept.**
   `klt sta`'s entire reason to exist (`docs/cli/sta.md` "Why this exists")
   is that re-running placement per corner produces a *different* placement
   each time, so a table built this way is "a sweep of N designs, not a
   characterization of one." This driver does exactly the thing `klt sta`
   exists to avoid, because there is currently no tool-supported way to
   avoid it pre-route (see the tool-gap paragraph above). Each corner run
   below is its own independent `global_placement` call.
2. **Setup slack in ns; hold is violation-count-only.** `worst_slack_ns` at
   `target_stage: "place"` is setup WNS (`report_worst_slack -max`
   under the hood) -- there is no equivalent hold-WNS-in-ns field before
   `stage_reached == "route"` (`worst_hold_slack_ns` is part of the
   route-stage-only corner-sweep aggregate). `hold_violation_count` is
   real and populated at `"place"`, so a hold *violation* is still caught
   and reported, just not as a slack number pre-route. This is the second
   half of the filed tool gap.
3. **Wire-free.** `target_stage: "place"` runs `global_placement`, which
   OpenROAD's built-in STA already accounts for via placement-based
   estimated RC -- but there is no CTS-built clock tree and no detailed
   route, so this is still meaningfully more optimistic than a routed,
   SPEF-annotated signoff number. Labeled PRE-ROUTE throughout.
4. **Not #274's deliverable.** The floorplan/utilization parameters below
   exist solely to give OpenROAD's placer *something* to place onto so it
   can run STA -- they are not a footprint-fit claim. Whether the routed
   macro fits the reserved footprint `layout/adc-top/README.md` documents
   is entirely #274's own finding, unaffected by anything in this file --
   see that file for the current, as-drawn figure rather than repeating a
   specific number here that would go stale the next time that figure
   changes (as the number this note once cited already did).

## Corners

DR-0023's own ratified 3.3 V corner set (`spec/decision-records/
DR-0023-digital-interface-device-flavor.md`: "Both libraries' Liberty
corner sets (`gf180mcu_fd_sc_mcu{7,9}t5v0__{tt_025C_3v30,ss_125C_3v00,
ff_n40C_3v60}.lib`, confirmed present)") plus the two remaining 3.3 V
corners the installed `gf180mcu_fd_sc_mcu7t5v0` library also ships
(`ss_n40C_3v00`, `ff_125C_3v60`) -- CLAUDE.md's "PVT corners on every
recorded result" and `gf180-tmds-tx`'s own `flow/sta_tmds_encoder.py`
precedent ("every 3.3 V corner the vendored library ships") both argue for
running the full shipped set, not just DR-0023's named three, at the
marginal cost of two more `klt place-and-route` calls.

## Floorplan / IO layer convention

`site: "GF018hv5v_mcu_sc7"`, `io.layer_h/.layer_v: "Metal3"/"Metal4"` --
`klayout-tools`' own `gf180mcu_fd_sc_mcu7t5v0` P&R test fixture
(`tests/test_place_and_route.py::_setup_gf180mcu_7t_success_env`, issue
#1649), which that fixture's own docstring states "match[es] ORFS's own
gf180 platform" (`platforms/gf180/config.mk`). `utilization_pct: 38`,
`aspect_ratio: 1.0`, `core_margin_um: 2.0` are the same fixture's floorplan
defaults. None of these shape the STA result in a way that matters here
(see limitation 4 above) -- they are reused rather than invented so this
driver's floorplan request is provably not an arbitrary guess.

## Cold-start invocation

Requires `klt`, `yosys`, and an `openroad` binary on `$PATH` (this repo's
`~/.local/bin/openroad` is a Docker wrapper around `openroad/orfs:latest`
-- see `docs/cli/place-and-route.md` "Installing OpenROAD" in
`klayout-tools`), and the gf180mcu PDK installed
(`docs/environment-setup.md`). The Docker wrapper only mounts `$PDK_ROOT`
into the container, so this driver explicitly sets `PDK_ROOT`/`PDK` in the
subprocess environment from its own resolved `find_pdk()` result --
independent of whatever the caller's shell happens to have exported --
rather than relying on the ambient environment matching.

    python3 design/sar-logic/flow/sta_sar_ctrl.py

Writes, for the `mcu7t5v0` library (the one `layout/adc-top/` actually
reserves footprint for -- see `design/sar-logic/rtl/README.md` "Library
choice"):

  - a documentation SDC (informational -- see "SDC is documentation, not a
    tool input" below): design/sar-logic/flow/sar_ctrl/sta/sar_ctrl.sdc
  - the exact `klt place-and-route` request/response per corner:
        design/sar-logic/flow/sar_ctrl/reports/<rid>.mcu7t5v0.sta_<corner>.pnr_request.json
        design/sar-logic/flow/sar_ctrl/reports/<rid>.mcu7t5v0.sta_<corner>.pnr_response.json
  - an append-only evidence record:
        design/sar-logic/flow/sar_ctrl/records/<rid>.mcu7t5v0.sta.md

## SDC is documentation, not a tool input

Neither `klt place-and-route`'s nor `klt sta`'s request schema parses a raw
`.sdc` file -- both take an inline JSON `constraints.clock_port`/
`.clock_period_ns` pair (`docs/cli/place-and-route.md`, `docs/cli/sta.md`),
and neither models an I/O boundary condition (no `set_input_delay`/
`set_driving_cell` equivalent in either contract) the way `gf180-tmds-tx`'s
own hand-written-OpenSTA-Tcl `flow/sta_tmds_encoder.py` does. The `.sdc`
file this driver writes restates the same `create_clock` constraint in SDC
syntax purely for human readability/reproducibility (matching
`gf180-tmds-tx`'s own `flow/tmds_encoder/sta/tmds_encoder.sdc` convention)
-- it is regenerated in place on every run, like the netlist, not
append-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "design" / "sar-logic" / "flow"))

from sim.harness.pdk import Pdk, PdkNotFound, find_pdk  # noqa: E402
import synth_sar_ctrl as synth  # noqa: E402  (reuses working_tree_dirty)

#: The git/`klt` provenance plumbing every driver in this directory
#: shares (issue #352) -- imported from the module that owns it rather
#: than reached through `synth.`, which only ever re-exported it.
from flow_env import git, klt_version, record_id  # noqa: E402

TOP = "sar_ctrl_a"
CELL_LIBRARY = "gf180mcu_fd_sc_mcu7t5v0"
LIB_TAG = "mcu7t5v0"

NETLIST = (
    REPO_ROOT / "design" / "sar-logic" / "flow" / "sar_ctrl" / "netlist" / f"sar_ctrl.{LIB_TAG}.synth.v"
)

OUT_DIR = REPO_ROOT / "design" / "sar-logic" / "flow" / "sar_ctrl"
STA_DIR = OUT_DIR / "sta"
REPORTS_DIR = OUT_DIR / "reports"
RECORDS_DIR = OUT_DIR / "records"
SDC = STA_DIR / "sar_ctrl.sdc"

# DR-0003: 16 MHz external clock (M = 16 at 1 MS/s) -> 62.5 ns bit-cycle period.
CLOCK_PORT = "clk"
CLOCK_PERIOD_NS = 62.5

# DR-0023's own ratified 3.3 V corner set (first 3) + the two remaining 3.3 V
# corners gf180mcu_fd_sc_mcu7t5v0 also ships (last 2) -- see module docstring.
CORNERS: list[tuple[str, str]] = [
    ("tt_025C_3v30", "typical process, 25 C, 3.30 V (DR-0023's own corner; #272's synthesis corner)"),
    ("ss_125C_3v00", "slow process, 125 C, 3.00 V (worst case for setup; DR-0023-named)"),
    ("ff_n40C_3v60", "fast process, -40 C, 3.60 V (worst case for hold; DR-0023-named)"),
    ("ss_n40C_3v00", "slow process, -40 C, 3.00 V (supplementary -- ships in the library, not named by DR-0023)"),
    ("ff_125C_3v60", "fast process, 125 C, 3.60 V (supplementary -- ships in the library, not named by DR-0023)"),
]

# klayout-tools tests/test_place_and_route.py::_setup_gf180mcu_7t_success_env
# (issue #1649) -- "match[es] ORFS's own gf180 platform" per that fixture's docstring.
FLOORPLAN_SITE = "GF018hv5v_mcu_sc7"
IO_LAYER_H = "Metal3"
IO_LAYER_V = "Metal4"
UTILIZATION_PCT = 38
ASPECT_RATIO = 1.0
CORE_MARGIN_UM = 2.0

TARGET_STAGE = "place"


class StaError(RuntimeError):
    pass


def build_sdc() -> str:
    return f"""\
# Timing constraint for {TOP} -- GENERATED by design/sar-logic/flow/sta_sar_ctrl.py
# (DR-0023 follow-on (c), issue #275). Regenerated in place on every run, like the
# netlist -- edit that driver, not this file.
#
# DOCUMENTATION ONLY: neither `klt place-and-route` nor `klt sta` parses a raw .sdc
# file -- both take this same constraint as inline JSON (`constraints.clock_port`/
# `.clock_period_ns`). This file restates it in SDC syntax purely for human
# readability/reproducibility, matching gf180-tmds-tx's own
# flow/tmds_encoder/sta/tmds_encoder.sdc convention. See the driver's own
# docstring ("SDC is documentation, not a tool input") for why there is no
# set_input_delay/set_output_delay/set_driving_cell/set_load here: neither tool
# contract models an I/O boundary condition.

# DR-0003: 16 MHz external clock, M = 16 phases per conversion at 1 MS/s.
create_clock -name clk -period {CLOCK_PERIOD_NS:.4f} [get_ports clk]
"""


def build_pnr_request(corner: str) -> dict:
    return {
        "schema": "klt.place_and_route.request/1",
        "engine": "openroad",
        "netlist": str(NETLIST),
        "hdl_toplevel": TOP,
        "pdk": {"cell_library": CELL_LIBRARY, "corner": corner},
        "floorplan": {
            "method": "utilization",
            "utilization_pct": UTILIZATION_PCT,
            "aspect_ratio": ASPECT_RATIO,
            "core_margin_um": CORE_MARGIN_UM,
            "site": FLOORPLAN_SITE,
        },
        "io": {"layer_h": IO_LAYER_H, "layer_v": IO_LAYER_V},
        "constraints": {"clock_port": CLOCK_PORT, "clock_period_ns": CLOCK_PERIOD_NS},
        "seed": 1,
        "target_stage": TARGET_STAGE,
    }


def run_pnr(pdk: Pdk, request: dict, request_path: Path) -> dict:
    """Invoke `klt place-and-route` for one corner, returning the parsed
    response. Explicitly sets PDK_ROOT/PDK in the subprocess environment
    (see module docstring's "Cold-start invocation") so the openroad Docker
    wrapper mounts the right install regardless of the caller's own shell.
    """
    import os
    import subprocess

    request_path.write_text(json.dumps(request, indent=2) + "\n")
    env = dict(os.environ)
    env["PDK_ROOT"] = str(pdk.path.parent)
    env["PDK"] = pdk.variant
    result = subprocess.run(
        ["klt", "place-and-route", str(request_path), "--pdk", pdk.variant, "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise StaError(
            f"klt place-and-route (corner {request['pdk']['corner']}) did not print JSON "
            f"(exit {result.returncode}): {exc}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        ) from exc
    if "error" in response:
        raise StaError(
            f"klt place-and-route (corner {request['pdk']['corner']}) failed: "
            f"{response['error'].get('message')}"
        )
    if result.returncode != 0:
        raise StaError(
            f"klt place-and-route (corner {request['pdk']['corner']}) exited "
            f"{result.returncode} with no error envelope:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return response


class CornerResult:
    def __init__(self, corner: str, desc: str, response: dict):
        self.corner = corner
        self.desc = desc
        self.response = response
        if response.get("stage_reached") != TARGET_STAGE:
            raise StaError(
                f"corner {corner}: expected stage_reached={TARGET_STAGE!r}, "
                f"got {response.get('stage_reached')!r}"
            )
        self.setup_slack_ns = response["worst_slack_ns"]
        self.setup_tns_ns = response["total_negative_slack_ns"]
        self.setup_violations = response["setup_violation_count"]
        self.hold_violations = response["hold_violation_count"]
        self.fmax_mhz = response.get("fmax_mhz")
        self.estimated_power_mw = response.get("estimated_power_mw")
        self.wirelength_um = response.get("wirelength_um")

    @property
    def setup_pass(self) -> bool:
        return self.setup_violations == 0 and self.setup_slack_ns is not None and self.setup_slack_ns >= 0

    @property
    def hold_pass(self) -> bool:
        return self.hold_violations == 0


def _verdict_table(results: list[CornerResult]) -> str:
    rows = [
        "| Corner | Setup slack (ns) | Setup TNS (ns) | Setup violators | Hold violators | Fmax (MHz) | Est. power (mW) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        rows.append(
            f"| `{r.corner}` "
            f"| {'PASS' if r.setup_pass else 'FAIL'} {r.setup_slack_ns:+.4f} "
            f"| {r.setup_tns_ns:+.4f} "
            f"| {r.setup_violations} "
            f"| {'PASS' if r.hold_pass else 'FAIL'} {r.hold_violations} "
            f"| {r.fmax_mhz:.2f} "
            f"| {r.estimated_power_mw:.4f} |"
        )
    return "\n".join(rows)


def render_record(
    *,
    rid: str,
    when,
    pdk: Pdk,
    klt_v: str,
    results: list[CornerResult],
    dirty: bool,
    sha: str,
    friction_issue: str,
) -> str:
    named = [r for r in results if r.corner in ("tt_025C_3v30", "ss_125C_3v00", "ff_n40C_3v60")]
    setup_fail = [r for r in results if not r.setup_pass]
    hold_fail = [r for r in results if not r.hold_pass]
    verdict = "FAIL" if (setup_fail or hold_fail) else "PASS"
    worst_setup = min(results, key=lambda r: r.setup_slack_ns)
    fmax_worst = min(r.fmax_mhz for r in results)

    return f"""\
# Record {rid} ({LIB_TAG})

- **Record ID**: {rid}.{LIB_TAG}.sta
- **Claim**: The `sar_ctrl_a` gate-level netlist synthesized against
  `{CELL_LIBRARY}` (#272, PR #276) meets DR-0003's 62.5 ns bit-cycle clock
  period ({1000 / CLOCK_PERIOD_NS:.1f} MHz) at every corner in DR-0023's own
  ratified 3.3 V corner grid plus the two remaining 3.3 V corners the
  library ships, **PRE-ROUTE** (see "Known limitations" below -- this is
  explicitly NOT a routed, signoff-grade STA result; #274, place-and-route,
  has not yet produced a routed DEF this driver could run real `klt sta`
  against). DR-0023 follow-on (c), issue #275, addressing item 5 (full
  corner verification) of the digital partition.
- **Verdict (setup, all corners)**: **{"FAIL" if setup_fail else "PASS"}** -- {
      f"setup violated at {len(setup_fail)} of {len(results)} corners ({', '.join(r.corner for r in setup_fail)})"
      if setup_fail else "setup met at every corner checked"}.
- **Verdict (hold, all corners)**: **{"FAIL" if hold_fail else "PASS"}** -- {
      f"hold violated at {len(hold_fail)} of {len(results)} corners ({', '.join(r.corner for r in hold_fail)})"
      if hold_fail else "hold met at every corner checked (violation-count basis -- see limitation 2 below)"}.
- **Overall**: **{verdict}**.
- **Worst setup slack (all corners)**: {worst_setup.setup_slack_ns:+.4f} ns at corner
  `{worst_setup.corner}`, against the {CLOCK_PERIOD_NS:.4f} ns budget ({
      abs(worst_setup.setup_slack_ns) / CLOCK_PERIOD_NS * 100:.1f}% of the period).
- **Worst-corner Fmax (informational, this run's own metric)**: {fmax_worst:.2f} MHz
  (budget: {1000 / CLOCK_PERIOD_NS:.2f} MHz).

## Results (PRE-ROUTE, `target_stage: "place"`, independently placed per corner)

{_verdict_table(results)}

DR-0023-named corners: {", ".join(r.corner for r in named)}. Supplementary
corners (ship in `{CELL_LIBRARY}`, not individually named by DR-0023): {
    ", ".join(r.corner for r in results if r not in named)}.

## Why this is not a `klt sta` result (tool gap, filed)

`klt sta` (the command this issue asked for) requires an already-placed-or-
routed DEF as its `def` input; `klt place-and-route`'s `def_path` stays
`null` at every stage short of `"route"`. Follow-on (b) (#274) has not
produced a routed DEF yet, and running P&R through `"route"` ourselves here
would duplicate #274's own deliverable-grade scope (footprint fit vs the
reserved footprint `layout/adc-top/README.md` documents, DRC, GDS) and
risk a race with #274's concurrent work -- out of scope for this issue. See
`design/sar-logic/flow/sta_sar_ctrl.py`'s own module docstring for the full
reasoning. Filed upstream per CLAUDE.md's friction protocol (describing the
tool gap generically, not this design): {friction_issue}

## Known limitations (disclosed, not silently worked around)

1. **Independently placed per corner, not one fixed geometry swept.**
   `klt sta`'s own stated reason to exist is exactly this: re-running
   placement per corner produces a *different* placement each time, so this
   table is a sweep of {len(results)} independently-placed designs, not a
   characterization of one fixed geometry at {len(results)} corners. There is
   currently no tool-supported way to avoid this pre-route (see the tool-gap
   section above) -- each row above ran its own `global_placement`.
2. **Setup slack is a real ns number; hold is violation-count-only.**
   `worst_slack_ns` at `target_stage: "place"` is setup WNS from a real
   OpenSTA session under the 62.5 ns clock; there is no equivalent
   hold-WNS-in-ns field before `stage_reached == "route"` (that lives in the
   route-stage-only per-corner `corners[]` sweep). `hold_violation_count` is
   real and does catch a hold violation, just not as a slack number here.
3. **Wire-free-ish.** `target_stage: "place"` runs global placement (with
   OpenROAD's own placement-based STA), but there is no clock-tree synthesis
   and no detailed route -- meaningfully more optimistic than a routed,
   SPEF-annotated signoff number. The margin at every corner above is wide
   enough ({abs(worst_setup.setup_slack_ns) / CLOCK_PERIOD_NS * 100:.0f}%+ of
   the period) that this gap is unlikely to flip the verdict, but that is an
   engineering judgment stated here, not a proof.
4. **Not #274's deliverable.** The floorplan/utilization parameters this
   driver used ({UTILIZATION_PCT}% utilization, `{FLOORPLAN_SITE}` site) exist
   solely to give the placer something to place onto so it can run STA -- they
   are not a footprint-fit claim, and this run touches nothing under
   `layout/adc-top/`. Whether the eventual routed macro fits the reserved
   footprint is entirely #274's own finding.
- **Tool versions**:
  - `klt`: `{klt_v}`
  - gf180mcu PDK: variant `{pdk.variant}`, open_pdks `{pdk.version}` (via {pdk.source})
- **Constraints applied** (`{SDC.relative_to(REPO_ROOT)}`, documentation copy;
  the tool input is the inline JSON `constraints` field in each per-corner
  request below): `create_clock -period {CLOCK_PERIOD_NS:.4f}` on port `{CLOCK_PORT}`
  (DR-0003: 16 MHz external clock, M = 16 at 1 MS/s). No input/output delay or
  driving-cell/load constraint -- neither `klt place-and-route` nor `klt sta`
  models an I/O boundary condition (see the driver's own docstring).
- **Netlist analyzed**: `{NETLIST.relative_to(REPO_ROOT)}` (from #272, PR #276,
  merged 2026-09-14T22:41:38Z).
- **Reproducibility**: working tree {"DIRTY (uncommitted changes outside design/sar-logic/flow/sar_ctrl/ at run time -- re-run against a clean checkout before trusting this record)" if dirty else "clean"} at commit `{sha}`.
- **Links**:
  - Netlist (input, unmodified): `{NETLIST.relative_to(REPO_ROOT)}`
  - Documentation SDC: `{SDC.relative_to(REPO_ROOT)}`
  - Per-corner `klt place-and-route` requests/responses:
    `design/sar-logic/flow/sar_ctrl/reports/{rid}.{LIB_TAG}.sta_<corner>.pnr_request.json` / `.pnr_response.json`
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/flow/sta_sar_ctrl.py` (agent-run)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument(
        "--friction-issue",
        default="2AMLogic/klayout-tools#<TBD, see PR description>",
        help="the filed friction-protocol issue reference to cite in the evidence record",
    )
    args = parser.parse_args()

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if not NETLIST.is_file():
        print(f"ERROR: netlist not found at {NETLIST} -- run design/sar-logic/flow/synth_sar_ctrl.py first", file=sys.stderr)
        return 1

    STA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SDC.write_text(build_sdc())

    when = synth._dt.datetime.now(synth._dt.timezone.utc)
    rid = record_id(REPO_ROOT, when)

    results: list[CornerResult] = []
    for corner, desc in CORNERS:
        request = build_pnr_request(corner)
        request_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_{corner}.pnr_request.json"
        response_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_{corner}.pnr_response.json"
        print(f"STA (pre-route, target_stage={TARGET_STAGE}): corner {corner} ...")
        try:
            response = run_pnr(pdk, request, request_path)
        except StaError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        response_path.write_text(json.dumps(response, indent=2) + "\n")
        try:
            result = CornerResult(corner, desc, response)
        except StaError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        results.append(result)
        print(
            f"  setup {'PASS' if result.setup_pass else 'FAIL'} "
            f"(worst {result.setup_slack_ns:+.4f} ns, {result.setup_violations} violating endpoints), "
            f"hold {'PASS' if result.hold_pass else 'FAIL'} ({result.hold_violations} violating endpoints), "
            f"Fmax {result.fmax_mhz:.2f} MHz"
        )

    if not args.no_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        record_path = RECORDS_DIR / f"{rid}.{LIB_TAG}.sta.md"
        if record_path.exists():
            print(f"ERROR: record {record_path} already exists -- refusing to overwrite", file=sys.stderr)
            return 1
        sha = git(REPO_ROOT, "rev-parse", "HEAD") or "unknown"
        dirty = synth.working_tree_dirty()
        record_path.write_text(
            render_record(
                rid=rid,
                when=when,
                pdk=pdk,
                klt_v=klt_version(REPO_ROOT),
                results=results,
                dirty=dirty,
                sha=sha,
                friction_issue=args.friction_issue,
            )
        )
        print(f"Evidence record written to {record_path}")

    bad = [r for r in results if not (r.setup_pass and r.hold_pass)]
    if bad:
        print(f"FAIL at corner(s): {', '.join(r.corner for r in bad)}", file=sys.stderr)
        return 1
    print("All corners: setup and hold met (pre-route -- see evidence record's Known Limitations).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
