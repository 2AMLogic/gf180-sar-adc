#!/usr/bin/env python3
"""Post-route, per-corner static timing analysis driver for `sar_ctrl_a`
(DR-0023 follow-on (c) addendum, issue #275, Judge-requested on PR #278).

`sta_sar_ctrl.py` (this same issue's original driver) could not reach real
`klt sta` at the time it was written: #274 (place-and-route) had not yet
produced a routed DEF, so that driver used a disclosed `klt
place-and-route --target_stage place` substitution instead (see its own
module docstring). That gap is now closed -- #279 (DR-0023 follow-on (b))
merged a real, DRC-clean, routed macro at
`layout/adc-top/sar_ctrl/sar_ctrl.{def,gds,v}` -- so this driver runs the
real thing: `klt sta` against that routed DEF, per corner, with **no
re-placement and no re-routing** (`klt sta` never places or routes; see
`docs/cli/sta.md` "Why this exists" -- the whole point is one fixed
geometry swept across corners, not a fresh placement per corner).

This is a **new, additive** evidence record -- it does not edit or replace
`sta_sar_ctrl.py`'s own pre-route record
(`design/sar-logic/flow/sar_ctrl/records/20260914-235615-7022eab.mcu7t5v0.sta.md`).
Both remain readable, per this repo's append-only-records convention
(`sim/README.md` "Append-only rule"); this file's record is the
post-route, signoff-relevant one -- see `sim/README.md`'s digital-flow
section for which to cite going forward.

## Why the pre-route number is not signoff-grade (and this one is closer)

The pre-route driver's own disclosed limitations (repeated here only to
state which no longer apply):

1. **Independently placed per corner** -- does not apply here. `klt sta`
   loads the *same* routed DEF unmodified for every corner in the sweep
   below (`docs/cli/sta.md`: "the same DEF, unmodified, is loaded fresh for
   every corner run" -- this is exactly the corner-characterization gap
   `klt sta` exists to close).
2. **Hold reported as violation-count only, no ns figure** -- does not
   apply here. `klt sta`'s response carries a real `worst_hold_slack_ns`/
   `total_negative_hold_slack_ns` pair regardless of stage.
3. **Wire-free-ish (placement-based RC estimate, no CTS, no detailed
   route)** -- does not apply to the *geometry*: the DEF this driver reads
   is #279's fully routed, DRC-clean macro (real detailed route, real
   clock-tree cells already placed and routed as ordinary standard cells --
   `sar_ctrl_a` has no explicit CTS-inserted buffer tree beyond what
   synthesis/placement produced, consistent with a block this small).
   **Still not full-SPEF signoff**, though: no `klt extract --parasitics`
   SPEF was generated for this macro (out of scope for this issue -- that
   is its own deliverable), so this run's parasitics come from OpenSTA's
   own DEF/LEF-geometry-derived RC estimate (`spef` omitted from every
   request below), not routing-extracted SPEF RC. This is real,
   routed-geometry timing -- meaningfully more accurate than the pre-route
   placement estimate -- but a caller wanting parasitics traced through an
   actual extraction should treat this as "post-route, no SPEF" rather
   than "final signoff with extracted parasitics."
4. **Not #274's deliverable / stale reserved-footprint figure** -- does
   not apply here: this driver makes no footprint-fit claim at all (that
   remains entirely #274/#279's own finding, now committed at
   `layout/adc-top/sar_ctrl/` and `layout/adc-top/README.md`), and does not
   repeat any specific reserved-footprint number (`layout/adc-top/README.md`
   is the single place that number is allowed to live, per that file's own
   "supersede rather than edit in place" convention -- see the fix on
   `sta_sar_ctrl.py` made alongside this file, which stopped repeating a
   now-superseded 7,624 um^2 figure for the same reason).

## Corners, clock, and library

Identical to `sta_sar_ctrl.py`: DR-0023's own ratified 3.3 V corner set
plus the two remaining 3.3 V corners `gf180mcu_fd_sc_mcu7t5v0` ships, the
same DR-0003 62.5 ns (16 MHz) clock on port `clk`, the same
`gf180mcu_fd_sc_mcu7t5v0` library (the one `layout/adc-top/` reserves
footprint for). Only the geometry source and the `klt` verb change.

## Cold-start invocation

Same prerequisites as `sta_sar_ctrl.py` (`klt`, an `openroad` binary on
`$PATH`, the gf180mcu PDK installed) -- see that driver's own docstring for
detail. This driver additionally requires #279's routed DEF to already be
committed at `layout/adc-top/sar_ctrl/sar_ctrl.def`.

    python3 design/sar-logic/flow/sta_sar_ctrl_postroute.py

Writes, for the `mcu7t5v0` library:

  - the exact `klt sta` request/response per corner:
        design/sar-logic/flow/sar_ctrl/reports/<rid>.mcu7t5v0.sta_postroute_<corner>.sta_request.json
        design/sar-logic/flow/sar_ctrl/reports/<rid>.mcu7t5v0.sta_postroute_<corner>.sta_response.json
  - an append-only evidence record:
        design/sar-logic/flow/sar_ctrl/records/<rid>.mcu7t5v0.sta_postroute.md

## Single multi-corner request (`--multicorner`, issue #642)

    python3 design/sar-logic/flow/sta_sar_ctrl_postroute.py --multicorner

One `klt sta` request using `pdk.corners` with all five library corners on
the committed routed DEF, 62.5 ns clock, no SPEF (the extracted-SPEF case is
`--spef`'s, #486). Request `def` is relative to the request file, so the
committed JSON re-runs from any checkout. The record cites the response for
the manifest's `5.digital` row; a corner whose `timing_status` is not
`constrained`, or whose setup or hold slack is negative, is recorded as
failing and the driver exits 1. Writes
`<rid>.mcu7t5v0.sta_postroute_multicorner.sta_{request,response}.json` and
`records/<rid>.mcu7t5v0.sta_postroute_multicorner.md`.

## Extracted-SPEF mode (`--spef`, issue #481)

    python3 design/sar-logic/flow/sta_sar_ctrl_postroute.py --spef

Same five corners, same routed DEF, same 62.5 ns ideal clock, plus
interconnect parasitics extracted from the committed routed GDS by `klt
extract --parasitics --spef --def-net-names --def-net-connections <def>
--def-pins <def>` and fed to `klt sta` through its `spef` request field.
Nothing is re-placed or re-routed, and no constraint changes. Per corner it
runs the unannotated reference request (no `spef`) next to the SPEF request,
so the comparison uses one toolchain. It also checks that the reference
reproduces the committed 20260915 baseline.

A SPEF corner is accepted only if `klt sta`'s own `annotation_complete` is
true *and* `spef_audit.gate()` finds no other reason to reject it: a static
SPEF/DEF/Verilog/Liberty agreement audit, and a classification of every
OpenSTA SPEF-reader warning in the retained OpenROAD log. There is no
fallback to unannotated timing. A rejected corner is recorded as rejected
and the driver exits 1. Three negative controls run at `tt_025C_3v30` and
must be rejected. Two are derived from the real SPEF, with one timed net
dropped and with the same net renamed. The third is the tool-default
extraction without `--def-pins` (klayout-tools#2880). If any control is
accepted, the gate is broken and the driver exits 2.

The clock is ideal in every run: `klt sta` has no propagated-clock mode
(klayout-tools#2739). The driver checks this mechanically by reading each
retained generated script, hash-matched to `engine_log.script_sha256`, for
`set_propagated_clock`. It writes
`<rid>.mcu7t5v0.sar_ctrl.spef`, the trimmed `klt extract` response, the
per-corner `sta_postroute_ref_*`/`sta_postroute_spef_*` and
`sta_postroute_spef_negctl_*` request/response JSON, an
`<rid>.mcu7t5v0.sta_postroute_spef.audit.json`, and the record
`records/<rid>.mcu7t5v0.sta_postroute_spef.md`.
"""

from __future__ import annotations

import argparse
import json
import os
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
from flow_env import (  # noqa: E402
    CELL_LIBRARY,
    CLOCK_PERIOD_NS,
    CLOCK_PORT,
    CORNERS,
    LIB_TAG,
    OUT_DIR,
    RECORDS_DIR,
    REPORTS_DIR,
    TOP,
    CornerResult as _BaseCornerResult,
    StaError,
    git,
    klt_version,
    record_id,
    run_klt_json,
    verdict_table,
)


ROUTED_DEF = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.def"


# DR-0003: 16 MHz external clock (M = 16 at 1 MS/s) -> 62.5 ns bit-cycle period.

# Same corner set as sta_sar_ctrl.py -- see that driver's module docstring
# for the DR-0023 provenance of this list.

TARGET = "postroute"


def build_sta_request(corner: str) -> dict:
    return {
        "schema": "klt.sta.request/1",
        "def": str(ROUTED_DEF),
        "hdl_toplevel": TOP,
        "pdk": {"cell_library": CELL_LIBRARY, "corner": corner},
        "constraints": {"clock_port": CLOCK_PORT, "clock_period_ns": CLOCK_PERIOD_NS},
        "geometry_source": "routed",
    }


def run_sta(pdk: Pdk, request: dict, request_path: Path) -> dict:
    """Invoke `klt sta` for one corner, returning the parsed response.
    `run_klt_json` sets PDK_ROOT/PDK in the subprocess environment (same
    rationale as `sta_sar_ctrl.py`'s `run_pnr`)."""
    request_path.write_text(json.dumps(request, indent=2) + "\n")
    return run_klt_json(
        REPO_ROOT,
        pdk,
        ["sta", str(request_path)],
        error_cls=StaError,
        label=f"klt sta (corner {request['pdk']['corner']})",
    )


class CornerResult(_BaseCornerResult):
    def __init__(self, corner: str, desc: str, response: dict):
        super().__init__(corner, desc, response)
        self.hold_slack_ns = response["worst_hold_slack_ns"]
        self.hold_tns_ns = response["total_negative_hold_slack_ns"]


def _verdict_table(results: list[CornerResult]) -> str:
    return verdict_table(
        results,
        [
            ("Hold slack (ns)", lambda r: f"{'PASS' if r.hold_pass else 'FAIL'} {r.hold_slack_ns:+.4f}"),
            ("Hold TNS (ns)", lambda r: f"{r.hold_tns_ns:+.4f}"),
        ],
    )


def render_record(
    *,
    rid: str,
    when,
    pdk: Pdk,
    klt_v: str,
    results: list[CornerResult],
    dirty: bool,
    sha: str,
) -> str:
    named = [r for r in results if r.corner in ("tt_025C_3v30", "ss_125C_3v00", "ff_n40C_3v60")]
    setup_fail = [r for r in results if not r.setup_pass]
    hold_fail = [r for r in results if not r.hold_pass]
    verdict = "FAIL" if (setup_fail or hold_fail) else "PASS"
    worst_setup = min(results, key=lambda r: r.setup_slack_ns)
    worst_hold = min(results, key=lambda r: r.hold_slack_ns)
    fmax_worst = min(r.fmax_mhz for r in results)

    return f"""\
# Record {rid} ({LIB_TAG})

- **Record ID**: {rid}.{LIB_TAG}.sta_postroute
- **Claim**: The `sar_ctrl_a` gate-level netlist, as routed by #274/#279
  (`layout/adc-top/sar_ctrl/sar_ctrl.def`, DRC clean, 0 route/antenna
  violations), meets DR-0003's 62.5 ns bit-cycle clock period
  ({1000 / CLOCK_PERIOD_NS:.1f} MHz) at every corner in DR-0023's own
  ratified 3.3 V corner grid plus the two remaining 3.3 V corners the
  library ships, run via real `klt sta` against the one fixed routed DEF
  (not re-placed per corner). This is the **post-route** counterpart to
  `20260914-235615-7022eab.mcu7t5v0.sta.md` (pre-route, placement-estimate
  substitution) -- see "Known limitations" below for what is and is not
  signoff-grade about this run. DR-0023 follow-on (c), issue #275,
  addressing item 5 (full corner verification) of the digital partition,
  Judge-requested re-run against the routed DEF on PR #278.
- **Verdict (setup, all corners)**: **{"FAIL" if setup_fail else "PASS"}** -- {
      f"setup violated at {len(setup_fail)} of {len(results)} corners ({', '.join(r.corner for r in setup_fail)})"
      if setup_fail else "setup met at every corner checked"}.
- **Verdict (hold, all corners)**: **{"FAIL" if hold_fail else "PASS"}** -- {
      f"hold violated at {len(hold_fail)} of {len(results)} corners ({', '.join(r.corner for r in hold_fail)})"
      if hold_fail else "hold met at every corner checked"}.
- **Overall**: **{verdict}**.
- **Worst setup slack (all corners)**: {worst_setup.setup_slack_ns:+.4f} ns at corner
  `{worst_setup.corner}`, against the {CLOCK_PERIOD_NS:.4f} ns budget ({
      abs(worst_setup.setup_slack_ns) / CLOCK_PERIOD_NS * 100:.1f}% of the period).
- **Worst hold slack (all corners)**: {worst_hold.hold_slack_ns:+.4f} ns at corner
  `{worst_hold.corner}`.
- **Worst-corner Fmax (informational, this run's own metric)**: {fmax_worst:.2f} MHz
  (budget: {1000 / CLOCK_PERIOD_NS:.2f} MHz).

## Results (POST-ROUTE, one fixed routed DEF, swept across corners)

{_verdict_table(results)}

DR-0023-named corners: {", ".join(r.corner for r in named)}. Supplementary
corners (ship in `{CELL_LIBRARY}`, not individually named by DR-0023): {
    ", ".join(r.corner for r in results if r not in named)}.

## Relationship to the pre-route record

`sta_sar_ctrl.py`'s record (`20260914-235615-7022eab.mcu7t5v0.sta.md`) used
a disclosed `klt place-and-route --target_stage place` substitution because
#274 had not yet produced a routed DEF at that time; that substitution
independently re-placed the design per corner (a sweep of N designs, not a
characterization of one) and reported hold as violation-count only. #279
(DR-0023 follow-on (b)) has since merged a real, DRC-clean, routed macro,
closing that gap -- this record runs real `klt sta` (`docs/cli/sta.md`)
against that one fixed routed DEF, swept across the same corner set. **This
record is the signoff-relevant one going forward**; the pre-route record
remains readable as historical evidence per this repo's append-only-records
convention and is not edited or deleted.

## Known limitations (disclosed, not silently worked around)

1. **No extracted SPEF -- LEF/DEF-geometry RC estimate, not routing-derived
   parasitics.** No `klt extract --parasitics` SPEF exists yet for
   `sar_ctrl_a` (a separate deliverable, out of scope for this issue), so
   every request below omits `spef` and OpenSTA times this run from its own
   DEF-geometry RC estimate. This is real, routed-geometry timing -- the
   clock tree, cell placement, and all routing are #279's actual committed
   geometry, not an estimate -- but it is not the same as a SPEF-annotated
   signoff number. The margin at every corner below is wide enough that
   this gap is unlikely to flip the verdict, but that is an engineering
   judgment stated here, not a proof.
2. **Not corner-searched or propagated-clock timing.** Same caveat
   `docs/cli/sta.md` states for every `klt sta` run: `fmax_mhz` is
   `report_fmax_metric`'s own extrapolation (not bisected), and the clock
   is an ideal SDC clock, not a propagated one.
- **Tool versions**:
  - `klt`: `{klt_v}`
  - gf180mcu PDK: variant `{pdk.variant}`, open_pdks `{pdk.version}` (via {pdk.source})
- **Constraints applied**: `create_clock -period {CLOCK_PERIOD_NS:.4f}` on port
  `{CLOCK_PORT}` (DR-0003: 16 MHz external clock, M = 16 at 1 MS/s), inline JSON
  `constraints` field in each per-corner request below (`klt sta` does not
  parse a raw `.sdc` file -- see `sta_sar_ctrl.py`'s "SDC is documentation,
  not a tool input" for the shared convention; this driver reuses that same
  documentation SDC at `design/sar-logic/flow/sar_ctrl/sta/sar_ctrl.sdc`,
  unchanged).
- **DEF analyzed**: `{ROUTED_DEF.relative_to(REPO_ROOT)}` (from #274/#279, merged
  2026-09-15T00:21:25Z; `geometry_source: "routed"`).
- **Reproducibility**: working tree {"DIRTY (uncommitted changes outside design/sar-logic/flow/sar_ctrl/ at run time -- re-run against a clean checkout before trusting this record)" if dirty else "clean"} at commit `{sha}`.
- **Links**:
  - Routed DEF (input, unmodified): `{ROUTED_DEF.relative_to(REPO_ROOT)}`
  - Documentation SDC: `design/sar-logic/flow/sar_ctrl/sta/sar_ctrl.sdc`
  - Pre-route counterpart record: `design/sar-logic/flow/sar_ctrl/records/20260914-235615-7022eab.mcu7t5v0.sta.md`
  - Per-corner `klt sta` requests/responses:
    `design/sar-logic/flow/sar_ctrl/reports/{rid}.{LIB_TAG}.sta_{TARGET}_<corner>.sta_request.json` / `.sta_response.json`
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/flow/sta_sar_ctrl_postroute.py` (agent-run)
- **Supersedes**: `20260914-235615-7022eab.mcu7t5v0.sta` (a post-route,
  routed-DEF re-run of that record's own claim -- DR-0003 timing closure
  for `sar_ctrl_a` -- now that #279 has produced the routed DEF that record
  itself explains was unavailable at the time it was written; see
  "Relationship to the pre-route record" above for the delta. Per
  `sim/README.md`'s append-only rule, that record is left exactly as
  originally written, not edited.)
"""


def build_multicorner_request(request_dir: Path) -> dict:
    """One `pdk.corners` request over every CORNERS entry; `def` is relative
    to the request file's directory (what `klt sta` resolves it against)."""
    return {
        "schema": "klt.sta.request/1",
        "def": os.path.relpath(ROUTED_DEF, request_dir),
        "hdl_toplevel": TOP,
        "pdk": {"cell_library": CELL_LIBRARY, "corners": [c for c, _ in CORNERS]},
        "constraints": {"clock_port": CLOCK_PORT, "clock_period_ns": CLOCK_PERIOD_NS},
        "geometry_source": "routed",
    }


def _corner_ok(entry: dict) -> bool:
    return (
        entry.get("timing_status") == "constrained"
        and entry["worst_slack_ns"] >= 0
        and entry["worst_hold_slack_ns"] >= 0
    )


def render_multicorner_record(*, rid: str, when, pdk: Pdk, klt_v: str, response: dict, dirty: bool, sha: str) -> str:
    rows = []
    failing = [e["corner"] for e in response["corners"] if not _corner_ok(e)]
    for entry in response["corners"]:
        status = entry.get("timing_status")
        setup, hold = entry["worst_slack_ns"], entry["worst_hold_slack_ns"]
        ok = _corner_ok(entry)
        rows.append(
            f"| `{entry['corner']}` | {status} | {setup:+.4f} | {hold:+.4f} | "
            f"{entry['setup_violation_count']} / {entry['hold_violation_count']} | {'PASS' if ok else 'FAIL'} |"
        )
    verdict = "FAIL" if failing else "PASS"
    stem = f"{rid}.{LIB_TAG}.sta_{TARGET}_multicorner"
    return f"""\
# Record {rid} ({LIB_TAG})

- **Record ID**: {rid}.{LIB_TAG}.sta_postroute_multicorner
- **Claim**: `sar_ctrl_a`, as routed in `{ROUTED_DEF.relative_to(REPO_ROOT)}`, is timed at all
  {len(CORNERS)} `{CELL_LIBRARY}` corners in ONE `klt sta` request (`pdk.corners`) against
  one geometry (`provenance.input.content_hash` is hoisted once), {CLOCK_PERIOD_NS} ns ideal clock on `{CLOCK_PORT}`.
  Cited as `5.digital` in `signoff/gf180-sar-adc.manifest.json` (issue #642).
- **Overall**: **{verdict}**{f" -- failing corner(s): {', '.join(failing)}" if failing else " -- every corner `constrained` with non-negative setup and hold slack"}.
- **No SPEF**: parasitics are OpenSTA's DEF/LEF estimate; the extracted-SPEF case is
  tracked separately (#486, `--spef` mode). The clock is ideal (`clock_mode: {response.get("clock_mode")}`).

| Corner | timing_status | Setup slack (ns) | Hold slack (ns) | Setup / hold violations | Verdict |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

- **Tool versions**: `klt` `{klt_v}`; gf180mcu PDK variant `{pdk.variant}`, open_pdks `{pdk.version}` (via {pdk.source}); engine `{response.get("engine")}` `{response.get("engine_version")}`
- **Reproducibility**: working tree {"DIRTY at run time -- re-run against a clean checkout before trusting this record" if dirty else "clean"} at commit `{sha}`.
- **Links**: `design/sar-logic/flow/sar_ctrl/reports/{stem}.sta_request.json` / `.sta_response.json`
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/flow/sta_sar_ctrl_postroute.py --multicorner` (agent-run)
"""


def run_multicorner_mode(*, pdk: Pdk, rid: str, when, write_record: bool) -> int:
    request_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_{TARGET}_multicorner.sta_request.json"
    response_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_{TARGET}_multicorner.sta_response.json"
    request = build_multicorner_request(REPORTS_DIR)
    request_path.write_text(json.dumps(request, indent=2) + "\n")
    try:
        response = run_klt_json(
            REPO_ROOT, pdk, ["sta", str(request_path)], error_cls=StaError, label="klt sta (pdk.corners)"
        )
    except StaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    response_path.write_text(json.dumps(response, indent=2) + "\n")
    sha = git(REPO_ROOT, "rev-parse", "HEAD") or "unknown"
    text = render_multicorner_record(
        rid=rid,
        when=when,
        pdk=pdk,
        klt_v=klt_version(REPO_ROOT),
        response=response,
        dirty=synth.working_tree_dirty(),
        sha=sha,
    )
    if write_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        record_path = RECORDS_DIR / f"{rid}.{LIB_TAG}.sta_{TARGET}_multicorner.md"
        if record_path.exists():
            print(f"ERROR: record {record_path} already exists -- refusing to overwrite", file=sys.stderr)
            return 1
        record_path.write_text(text)
        print(f"Evidence record written to {record_path}")
    bad = [c["corner"] for c in response["corners"] if not _corner_ok(c)]
    if bad:
        print(f"FAIL at corner(s): {', '.join(bad)}", file=sys.stderr)
        return 1
    print("All corners constrained, setup and hold met (post-route, no extracted SPEF).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument(
        "--spef",
        action="store_true",
        help="extracted-SPEF mode (issue #481): extract the routed GDS, gate on annotation, run negative controls",
    )
    parser.add_argument(
        "--multicorner",
        action="store_true",
        help="one `pdk.corners` klt sta request over all five corners (issue #642, manifest 5.digital)",
    )
    args = parser.parse_args()

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if not ROUTED_DEF.is_file():
        print(f"ERROR: routed DEF not found at {ROUTED_DEF} -- #274/#279 has not landed it yet", file=sys.stderr)
        return 1

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    when = synth._dt.datetime.now(synth._dt.timezone.utc)
    rid = record_id(REPO_ROOT, when)

    if args.multicorner:
        return run_multicorner_mode(pdk=pdk, rid=rid, when=when, write_record=not args.no_record)

    if args.spef:
        import sta_postroute_spef  # the --spef mode lives beside this driver (issue #481)

        return sta_postroute_spef.run_spef_mode(pdk=pdk, rid=rid, when=when, write_record=not args.no_record)

    results: list[CornerResult] = []
    for corner, desc in CORNERS:
        request = build_sta_request(corner)
        request_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_{TARGET}_{corner}.sta_request.json"
        response_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_{TARGET}_{corner}.sta_response.json"
        print(f"STA (post-route, routed DEF): corner {corner} ...")
        try:
            response = run_sta(pdk, request, request_path)
        except StaError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        response_path.write_text(json.dumps(response, indent=2) + "\n")
        try:
            result = CornerResult(corner, desc, response)
        except KeyError as exc:
            print(f"ERROR: corner {corner}: response missing field {exc}", file=sys.stderr)
            return 1
        results.append(result)
        print(
            f"  setup {'PASS' if result.setup_pass else 'FAIL'} "
            f"(worst {result.setup_slack_ns:+.4f} ns, {result.setup_violations} violating endpoints), "
            f"hold {'PASS' if result.hold_pass else 'FAIL'} "
            f"(worst {result.hold_slack_ns:+.4f} ns, {result.hold_violations} violating endpoints), "
            f"Fmax {result.fmax_mhz:.2f} MHz"
        )

    if not args.no_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        record_path = RECORDS_DIR / f"{rid}.{LIB_TAG}.sta_{TARGET}.md"
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
            )
        )
        print(f"Evidence record written to {record_path}")

    bad = [r for r in results if not (r.setup_pass and r.hold_pass)]
    if bad:
        print(f"FAIL at corner(s): {', '.join(r.corner for r in bad)}", file=sys.stderr)
        return 1
    print("All corners: setup and hold met (post-route, no extracted SPEF -- see evidence record's Known Limitations).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
