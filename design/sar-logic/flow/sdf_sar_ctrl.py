#!/usr/bin/env python3
"""Write one post-route SDF per Liberty corner of the routed `sar_ctrl_a`
macro, from the SAME committed DEF + qualified SPEF the #486 STA receipt
annotated (issue #645, T1 item 7 digital).

    python3 design/sar-logic/flow/sdf_sar_ctrl.py

One `klt sta` request (`sdf: true`, klayout-tools #2886) over all five
`gf180mcu_fd_sc_mcu7t5v0` corners: the geometry and parasitics are the
committed routed DEF plus the qualified extraction SPEF, so each corner's
OpenSTA session runs `write_sdf -divider . -include_typ` immediately after
`read_spef` and reports the file it wrote as that corner's `sdf` block
(`{path, scope, content_hash}`).

The SPEF is NOT re-extracted and NOT re-qualified here: #486's accepted
receipt (qualification `20261104-195336-b4950aa2`, clean-tree re-run
`20261104-212437-9cde5a64`) is the only input, and this driver refuses to
run if any of the four inputs that receipt hash-pinned (DEF, GDS, gate-level
netlist, SPEF) has moved -- a moved input means the receipt is orphaned and
the SDF would describe geometry nobody qualified.

A corner passes only if `timing_status` is `constrained`, setup and hold
slack are non-negative, `spef_annotation.annotation_complete` is true, and
the committed SDF copy hashes to the `content_hash` the response reports.
Writes `<rid>.mcu7t5v0.sta_sdf.sta_{request,response}.json`, five
`<rid>.mcu7t5v0.sar_ctrl.<corner>.sdf` files, and the record
`records/<rid>.mcu7t5v0.sta_sdf.md`. Exit 1 on any failure; nothing is
dropped or retried at another corner.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "design" / "sar-logic" / "flow"))

from sim.harness.pdk import Pdk, PdkNotFound, find_pdk  # noqa: E402
from flow_env import (  # noqa: E402
    CELL_LIBRARY,
    CLOCK_PERIOD_NS,
    CLOCK_PORT,
    CORNERS,
    LIB_TAG,
    RECORDS_DIR,
    REPORTS_DIR,
    TOP,
    StaError,
    git,
    klt_version,
    record_id,
    run_klt_json,
    sha256,
    working_tree_dirty,
)

OWN_OUTPUT_PREFIXES = ("design/sar-logic/flow/sar_ctrl/",)

ROUTED_DEF = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.def"
ROUTED_GDS = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.gds"
ROUTED_V = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.v"

#: The qualified SPEF receipt this run consumes (#486, clean-tree re-run).
#: Hashes re-verified against `main` by issue #645's dependency decision
#: (2026-11-20); the driver re-checks them before every run so a P&R rerun
#: (#641) or a touched SPEF orphans the receipt loudly, not silently.
QUALIFIED_SPEF = REPORTS_DIR / "20261104-212437-9cde5a64.mcu7t5v0.sar_ctrl.spef"
QUALIFIED_INPUT_SHA256 = {
    "layout/adc-top/sar_ctrl/sar_ctrl.def": "96c8e30acde436cbcbf6f700f057f3eba68983b16acce69611ccc970cd87e53f",
    "layout/adc-top/sar_ctrl/sar_ctrl.gds": "b261719520ff0c769bd76c0851718ee4269e2ca27834dd263d4b0ebed205081a",
    "layout/adc-top/sar_ctrl/sar_ctrl.v": "6d32ab0ed1cd1ccb4b1d2c953060afbe3e5947bf634398661c2a04423023304b",
    "design/sar-logic/flow/sar_ctrl/reports/20261104-212437-9cde5a64.mcu7t5v0.sar_ctrl.spef": (
        "9167446e52f74f398fd5a22852d51857ded80aab4aed5a812a97af91559da9af"
    ),
}


class SdfModeError(RuntimeError):
    pass


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def check_qualified_inputs() -> None:
    """Refuse to run unless the four inputs of the #486 receipt still hash
    to what this driver's pinned table (and that record) say they did."""
    for rel, want in QUALIFIED_INPUT_SHA256.items():
        p = REPO_ROOT / rel
        if not p.is_file():
            raise SdfModeError(f"qualified-receipt input missing: {rel}")
        got = sha256(p)
        if got != want:
            raise SdfModeError(
                f"qualified-receipt input {rel} hashes {got}, receipt pins {want} -- "
                "the #486 qualification is orphaned (a P&R rerun regenerates these); "
                "re-qualify before minting SDF evidence from it"
            )


def build_request(request_dir: Path) -> dict:
    return {
        "schema": "klt.sta.request/1",
        "def": os.path.relpath(ROUTED_DEF, request_dir),
        "hdl_toplevel": TOP,
        "pdk": {"cell_library": CELL_LIBRARY, "corners": [c for c, _ in CORNERS]},
        "constraints": {"clock_port": CLOCK_PORT, "clock_period_ns": CLOCK_PERIOD_NS},
        "geometry_source": "routed",
        "spef": os.path.relpath(QUALIFIED_SPEF, request_dir),
        "sdf": True,
    }


def corner_ok(entry: dict) -> bool:
    annotation = entry.get("spef_annotation") or {}
    return (
        entry.get("timing_status") == "constrained"
        and entry.get("worst_slack_ns") is not None
        and entry["worst_slack_ns"] >= 0
        and entry.get("worst_hold_slack_ns") is not None
        and entry["worst_hold_slack_ns"] >= 0
        and annotation.get("annotation_complete") is True
    )


def commit_sdfs(rid: str, response: dict) -> list[tuple[str, str]]:
    """Copy each corner's SDF out of `.klt/sta/` to its committed name and
    verify the copy hashes to the `content_hash` the response reports.
    Returns `(corner, committed relpath)` pairs."""
    out = []
    for entry in response["corners"]:
        corner = entry["corner"]
        sdf = entry.get("sdf")
        if not (isinstance(sdf, dict) and sdf.get("path")):
            raise SdfModeError(f"corner {corner}: response reports no SDF (request needs `sdf: true`)")
        written = Path(sdf["path"])
        if not written.is_absolute():
            written = REPO_ROOT / written  # `scope: "repo"`: repo-relative
        if not written.is_file():
            raise SdfModeError(f"corner {corner}: SDF {written} not written")
        committed = REPORTS_DIR / f"{rid}.{LIB_TAG}.sar_ctrl.{corner}.sdf"
        shutil.copyfile(written, committed)
        got = f"sha256:{sha256(committed)}"
        if got != sdf.get("content_hash"):
            raise SdfModeError(f"corner {corner}: committed SDF hashes {got}, response pins {sdf.get('content_hash')}")
        out.append((corner, _rel(committed)))
    return out


def render_record(
    *,
    rid: str,
    when,
    pdk: Pdk,
    klt_v: str,
    response: dict,
    sdfs: list[tuple[str, str]],
    dirty: bool,
    sha: str,
) -> str:
    rows = []
    failing = [e["corner"] for e in response["corners"] if not corner_ok(e)]
    for entry in response["corners"]:
        ok = corner_ok(entry)
        sdf_hash = (entry.get("sdf") or {}).get("content_hash")
        rows.append(
            f"| `{entry['corner']}` | {entry['worst_slack_ns']:+.4f} | {entry['worst_hold_slack_ns']:+.4f} | "
            f"{entry.get('fmax_mhz'):.2f} | `{sdf_hash}` | {'PASS' if ok else 'FAIL'} |"
        )
    verdict = "FAIL" if failing else "PASS"
    inputs = "\n".join(f"  - `{rel}`: `{h}`" for rel, h in QUALIFIED_INPUT_SHA256.items())
    spef_table = "\n".join(f"  - `{rel}`" for _, rel in sdfs)
    return f"""\
# Record {rid}.{LIB_TAG}.sta_sdf

- **Record ID**: {rid}.{LIB_TAG}.sta_sdf
- **Claim under test**: one IEEE-1497 SDF per `gf180mcu_fd_sc_mcu7t5v0` Liberty corner, written by
  `klt sta` (`sdf: true`, `write_sdf -divider . -include_typ` immediately after `read_spef`) from the
  committed routed DEF and the **qualified** extraction SPEF of receipt `20261104-212437-9cde5a64`
  (#486, 5/5 corners accepted). Consumed by the gate-level SDF replay of issue #645
  (`design/sar-logic/tb/run_functional_gate.py`), cited as `7.digital`.
- **Verdict**: **{verdict}**{f" -- failing corner(s): {', '.join(failing)}" if failing else " -- every corner `constrained`, non-negative setup and hold slack, `annotation_complete: true`, SDF hash-pinned"}.
- **Not re-qualified here**: the SPEF's extraction-model limits carry over unchanged from #486's
  record `20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_spef.md` (lumped-star, 0-ohm legs, no wire
  resistance; one nominal extraction used at all five Liberty corners; ideal clock). The SDF is only
  as good as that model -- this record adds annotation coverage, not extraction fidelity.
- **Input hashes** (all four re-checked against the #486 receipt before running):
{inputs}
- **Timing and SDF hashes per corner** (SDF sha256 is the committed file's):

| Corner | Setup slack (ns) | Hold slack (ns) | Fmax (MHz) | SDF sha256 | Verdict |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

- **Committed SDFs** (bytes are what the run wrote; OpenSTA stamps `(DATE ...)`, so a re-run writes
  different bytes -- cite the hash, not the bytes):
{spef_table}
- **Tool versions**: `klt` `{klt_v}`; gf180mcu PDK variant `{pdk.variant}`, open_pdks `{pdk.version}`
  (via {pdk.source}); engine `{response.get("engine")}` `{response.get("engine_version")}`. This
  build is newer than the digital flow's `toolchain.json` pin (`klt 0.8.0`) because `sdf: true`
  postdates it (klayout-tools #2886); the pin governs the #486 qualification flow, not this run.
- **Reproducibility**: working tree {"DIRTY at run time -- re-run against a clean checkout before trusting this record" if dirty else "clean"} at commit `{sha}`.
  Re-run: `python3 design/sar-logic/flow/sdf_sar_ctrl.py` with this record's `klt` build first on `PATH`.
- **Links**: `design/sar-logic/flow/sar_ctrl/reports/{rid}.{LIB_TAG}.sta_sdf.sta_request.json` /
  `.sta_response.json`; SPEF `design/sar-logic/flow/sar_ctrl/reports/{QUALIFIED_SPEF.name}`.
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/flow/sdf_sar_ctrl.py` (agent-run)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args()

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    for p in (ROUTED_DEF, QUALIFIED_SPEF):
        if not p.is_file():
            print(f"ERROR: input not found at {p}", file=sys.stderr)
            return 1

    try:
        check_qualified_inputs()
    except SdfModeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    when = _dt.datetime.now(_dt.timezone.utc)
    rid = record_id(REPO_ROOT, when)

    request_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_sdf.sta_request.json"
    response_path = REPORTS_DIR / f"{rid}.{LIB_TAG}.sta_sdf.sta_response.json"
    request_path.write_text(json.dumps(build_request(REPORTS_DIR), indent=2) + "\n")
    try:
        response = run_klt_json(
            REPO_ROOT, pdk, ["sta", str(request_path)], error_cls=StaError, label="klt sta (sdf, pdk.corners)"
        )
    except StaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    response_path.write_text(json.dumps(response, indent=2) + "\n")

    try:
        sdfs = commit_sdfs(rid, response)
    except SdfModeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    bad = [e["corner"] for e in response["corners"] if not corner_ok(e)]
    if bad:
        print(f"FAIL at corner(s): {', '.join(bad)}", file=sys.stderr)
        return 1

    if not args.no_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        record_path = RECORDS_DIR / f"{rid}.{LIB_TAG}.sta_sdf.md"
        if record_path.exists():
            print(f"ERROR: record {record_path} already exists -- refusing to overwrite", file=sys.stderr)
            return 1
        record_path.write_text(
            render_record(
                rid=rid,
                when=when,
                pdk=pdk,
                klt_v=klt_version(REPO_ROOT),
                response=response,
                sdfs=sdfs,
                dirty=working_tree_dirty(REPO_ROOT, OWN_OUTPUT_PREFIXES),
                sha=git(REPO_ROOT, "rev-parse", "HEAD") or "unknown",
            )
        )
        print(f"Evidence record written to {record_path}")

    print(f"All {len(response['corners'])} corners: timing met, annotation complete, SDF committed and hash-pinned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
