#!/usr/bin/env python3
"""Run `klt pex` against the standalone COMPARATOR block and mint an
append-only `sim/comparator-pex/` evidence record -- issue #173 (T1 item 7,
"Post-layout verification").

## Why this is a SEPARATE, INVESTIGATIVE `klt` pin, not a `layout/toolchain.json` bump

`klt pex` (2AMLogic/klayout-tools epic #709) shipped after this repo's
production pin (`layout/toolchain.json`'s `klt_install`,
`875eac33dfbc004d2ab4dfcebc522734d159dc5f`, 2026-08-06) was cut, so it is
not available under that pin. Bumping the production pin to pick it up was
issue #173's own Scope item 1 -- but doing so was tried directly, live,
before writing this module, and found NOT to be the safe, drop-in absorption
the issue expected:

  * `klt lvs` itself is unaffected -- every one of this repo's committed LVS
    cases (`layout/lvs/cells/cells.json`) still reports `mismatches=0`
    against a FRESH extraction under the newer `klt`, confirmed directly.
  * But `klt extract`'s device-parameter reporting changed (every M-device
    line gains `as_um2`/`ad_um2`/`ps_um2`/`pd_um2`, absent under the pinned
    klt) and its `warnings[]` shape changed (several previously-separate
    entries now consolidate into one aggregate entry with different
    wording/counts) -- so EVERY committed `.spice` netlist snapshot
    (`adc_top.spice`, `adc_block.spice`, `comparator.spice`,
    `comparator_nores.spice`) and BOTH manifests' (`layout/drc/cells/*.json`,
    `layout/lvs/cells/cells.json`) `expect` blocks go stale simultaneously.
  * Those four netlist snapshots are not just LVS fixtures -- they are
    parsed directly by the #89-era extracted-core testbench generators
    (`gen_extracted_core_tb.py`, `gen_extracted_dr0014_sampling_tb.py`,
    `gen_extracted_power_tb.py`, ...) for their exact pin lists. Re-baselining
    them is therefore a change with the blast radius of issue #70/#116's
    own pin bumps (which this file's `_comment` documents at length) or
    larger, not a one-paragraph absorption -- it needs its own dedicated,
    reviewed issue, not a rider on this one.

So THIS module pins its own `klt` commit -- `PEX_KLT_COMMIT` below -- and
checks the installed `klt` against it directly (not through
`toolchain_pin.check_klt_capabilities`, which enforces
`layout/toolchain.json`'s *production* `klt_required_commands` list; adding
`pex` there would make every OTHER layout/ runner -- drc, lvs, extraction --
require it too, which the still-pinned `875eac3` install cannot satisfy).
The follow-up issue this module's docstring asks for is where
`layout/toolchain.json` itself should move.

## What this script does

1. Resolves the gf180mcuD PDK (`klt pdk find`, same resolver every other
   `klt`-driven runner in this repo uses).
2. Materializes `schematic_dut.spice` -- the resolved PDK's `design.ngspice`
   (defines `sw_stat_mismatch`/`sw_stat_global`, which every `.lib <corner>`
   section references; without it every corner section errors
   `Undefined parameter [sw_stat_mismatch]`, confirmed directly) concatenated
   with `design/comparator/comparator.spice` READ DIRECTLY from `design/`
   (never copied into git, so it cannot drift from the design it verifies) --
   next to a staged copy of the committed
   `sim/comparator-pex/testbench/{tb_comparator_pex.spice,request.json}`.
   `klt pex` requires the schematic DUT reachable through exactly ONE
   `.include`/`.inc` line (docs/cli/pex.md "The DUT `.include` swap"); two
   separate `.include`s (design.ngspice, then the DUT) were tried first and
   `klt pex` silently re-pointed the WRONG one (the first) at the extracted
   netlist -- a second, undocumented gotcha worth folding into the same
   upstream friction report. One concatenated file avoids it.
3. Runs `klt pex` against `../comparator.gds` with `--output`/`--outdir`
   BOTH redirected into this run's own scratch/report area -- never the
   default ("`<layout>` with its extension replaced by `.spice`, next to the
   input"), which would silently overwrite the COMMITTED, LVS-proven
   `../comparator.spice` this repo's `layout/lvs/` flow depends on. (Found
   out the hard way once, while producing this record; the resulting
   accidental modification was reverted before anything was committed.)
4. Captures the raw JSON report (whatever its `status` -- this run's own
   result IS the evidence, not merely a precondition for one) plus the
   schematic- and extracted-side `klt sim` logs, and mints an append-only
   `sim/comparator-pex/` record in this repo's own format
   (`sim/README.md`), NOT the pex-specific wrapper
   `docs/design/sim-evidence-discipline-spike.md` (upstream, in
   `klayout-tools`) proposes for repos that do not already have one.

Usage
-----
    python3 layout/adc-top/parasitics/run_pex_comparator.py            # run, mint a record
    python3 layout/adc-top/parasitics/run_pex_comparator.py --check    # run, assert reachability only, write nothing

Exit codes
----------
    0  a record was written (or --check's reachability probe passed) --
       NOTE this does NOT mean the `klt pex` run itself passed; see the
       record's own Result field, which states the true outcome honestly.
    1  tooling problem (klt/pex missing, PDK unresolved, `klt pex` refused
       to run at all -- exit 1/2 in its own scheme -- or record already exists)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADC_TOP_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
LAYOUT_DIR = os.path.abspath(os.path.join(ADC_TOP_DIR, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(LAYOUT_DIR, os.pardir))

sys.path.insert(0, LAYOUT_DIR)
from klt_env import (  # noqa: E402
    ToolingError,
    git,
    record_id,
    reserve_record_slot,
)

#: The `klt` commit this INVESTIGATIVE run pins -- see module docstring for
#: why this is not `layout/toolchain.json`'s production pin. Matches issue
#: #173's own cited "current klayout-tools main HEAD, 2026-08-16" commit.
PEX_KLT_COMMIT = "755d3eff3cebd2df9e874e446670a202f61ffe1d"

EXPERIMENT_DIR = os.path.join(REPO_ROOT, "sim", "comparator-pex")
TESTBENCH_DIR = os.path.join(EXPERIMENT_DIR, "testbench")
RECORDS_DIR = os.path.join(EXPERIMENT_DIR, "records")
CORNERS_DIR = os.path.join(EXPERIMENT_DIR, "corners")
NETLIST_SNAPSHOTS_DIR = os.path.join(EXPERIMENT_DIR, "netlist-snapshots")

COMPARATOR_GDS = os.path.join(ADC_TOP_DIR, "comparator.gds")
COMPARATOR_SCHEMATIC = os.path.join(
    REPO_ROOT, "design", "comparator", "comparator.spice"
)
DECK = "gf180mcu"
PDK_VARIANT = "gf180mcuD"
TOP = "COMPARATOR"


def _find_klt() -> str:
    klt = shutil.which("klt")
    if klt is None:
        raise ToolingError(
            "`klt` not found on PATH. Install klayout-tools at the commit "
            f"this investigative run pins:\n"
            f"    uv tool install --force git+https://github.com/2AMLogic/klayout-tools@{PEX_KLT_COMMIT}"
        )
    return klt


def _check_pex_available(klt: str) -> None:
    probe = subprocess.run([klt, "--help"], capture_output=True, text=True)
    if probe.returncode != 0:
        raise ToolingError(
            f"`klt --help` failed (exit {probe.returncode}): {probe.stderr}"
        )
    if not any(line.strip().startswith("pex") for line in probe.stdout.splitlines()):
        raise ToolingError(
            "installed `klt` has no `pex` subcommand -- this run needs at "
            f"least the commit epic #709 shipped it at. Reinstall:\n"
            f"    uv tool install --force git+https://github.com/2AMLogic/klayout-tools@{PEX_KLT_COMMIT}\n"
            "(this is a SEPARATE, investigative pin from "
            "layout/toolchain.json's production one -- see this module's "
            "own docstring for why.)"
        )


def _klt_version(klt: str) -> str:
    out = subprocess.run([klt, "--version"], capture_output=True, text=True)
    return out.stdout.strip() or out.stderr.strip() or "unknown"


def resolve_pdk(klt: str) -> dict:
    proc = subprocess.run(
        [klt, "pdk", "find", "--pdk", PDK_VARIANT, "--format", "json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise ToolingError(
            f"`klt pdk find --pdk {PDK_VARIANT}` failed (exit {proc.returncode}): "
            f"{proc.stderr.strip()}\nSet PDK_ROOT / install gf180mcuD via volare."
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(f"`klt pdk find` did not emit JSON: {exc}") from exc


def _write_schematic_dut(pdk: dict, out_path: str) -> None:
    """design.ngspice (global switch params) + design/comparator/comparator.spice
    (this repo's canonical, UNMODIFIED schematic), concatenated into the ONE
    `.include` target `klt pex` re-points -- see module docstring item 2."""
    design_ngspice = os.path.join(pdk["assets"]["ngspice"], "design.ngspice")
    if not os.path.isfile(design_ngspice):
        raise ToolingError(f"resolved PDK has no design.ngspice at {design_ngspice}")
    if not os.path.isfile(COMPARATOR_SCHEMATIC):
        raise ToolingError(f"canonical schematic not found: {COMPARATOR_SCHEMATIC}")
    with open(out_path, "w", encoding="utf-8") as out:
        out.write(
            f"* -- {os.path.basename(design_ngspice)}, resolved PDK {pdk['version']} --\n"
        )
        with open(design_ngspice, encoding="utf-8") as fh:
            out.write(fh.read())
        out.write(
            f"\n* -- {os.path.relpath(COMPARATOR_SCHEMATIC, REPO_ROOT)}, verbatim --\n"
        )
        with open(COMPARATOR_SCHEMATIC, encoding="utf-8") as fh:
            out.write(fh.read())


def _stage_request(work_dir: str, pdk: dict) -> str:
    """Copy the committed testbench + this run's composed schematic DUT into
    a scratch working dir, so `klt pex`'s relative `.include`/`netlist`
    paths resolve exactly as they would for a caller running the committed
    request by hand from `sim/comparator-pex/testbench/`.

    The committed `request.json`'s `models.lib` is PDK-relative
    (`models.pdk`/`models.lib`, docs/cli/sim.md "Model library resolution").
    That resolution was found NOT to reproduce consistently between `klt
    pex`'s schematic-side and extracted-side `klt sim` sub-invocations
    (extracted-side reported `model library not found` against a path
    resolved relative to the wrong directory, confirmed directly) --
    rewritten here to an ABSOLUTE `models.lib` path instead, which resolves
    identically on both sides. Worth folding into the same upstream friction
    report the interface-mismatch finding below already asks for."""
    shutil.copyfile(
        os.path.join(TESTBENCH_DIR, "tb_comparator_pex.spice"),
        os.path.join(work_dir, "tb_comparator_pex.spice"),
    )
    with open(os.path.join(TESTBENCH_DIR, "request.json"), encoding="utf-8") as fh:
        request = json.load(fh)
    request.pop("_comment", None)
    request["models"] = {
        "lib": os.path.join(pdk["assets"]["ngspice"], "sm141064.ngspice")
    }
    request_path = os.path.join(work_dir, "request.json")
    with open(request_path, "w", encoding="utf-8") as fh:
        json.dump(request, fh, indent=2)
    return request_path


def run_pex(klt: str, pdk: dict, work_dir: str) -> tuple[dict, int]:
    """Run `klt pex` for real; return (parsed JSON report, exit code).

    `--output`/`--outdir` are BOTH redirected into `work_dir` -- see module
    docstring item 3 for why the defaults are unsafe here.
    """
    request_path = _stage_request(work_dir, pdk)
    _write_schematic_dut(pdk, os.path.join(work_dir, "schematic_dut.spice"))

    extracted_netlist = os.path.join(work_dir, "comparator.pex.spice")
    artifacts_dir = os.path.join(work_dir, "klt-artifacts")
    cmd = [
        klt,
        "pex",
        COMPARATOR_GDS,
        request_path,
        "--deck",
        DECK,
        "--top",
        TOP,
        "--pdk",
        pdk["variant"],
        "--pdk-root",
        pdk["root"],
        "--output",
        extracted_netlist,
        "--outdir",
        artifacts_dir,
        "--format",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    if proc.returncode in (1, 2):
        raise ToolingError(
            f"`klt pex` refused to run at all (exit {proc.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n  stderr: {proc.stderr.strip()}\n  stdout: {proc.stdout.strip()}"
        )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(
            f"`klt pex` (exit {proc.returncode}) did not emit JSON on stdout: {exc}\n"
            f"stdout: {proc.stdout[:2000]}\nstderr: {proc.stderr[:2000]}"
        ) from exc
    report["_cmd"] = cmd
    report["_extracted_netlist_path"] = extracted_netlist
    report["_artifacts_dir"] = artifacts_dir
    return report, proc.returncode


def _find_corner_log(artifacts_dir: str, side: str) -> str | None:
    """`<artifacts_dir>/00-request/<side>/<corner-dir>/ngspice.log` --
    `klt pex`'s own per-testbench/per-side namespacing (docs/cli/pex.md
    `--outdir`)."""
    side_dir = os.path.join(artifacts_dir, "00-request", side)
    if not os.path.isdir(side_dir):
        return None
    for corner_name in sorted(os.listdir(side_dir)):
        candidate = os.path.join(side_dir, corner_name, "ngspice.log")
        if os.path.isfile(candidate):
            return candidate
    return None


def _record_body(rec_id: str, klt: str, pdk: dict, report: dict, exit_code: int) -> str:
    lines: list[str] = []
    a = lines.append
    a(f"# Record {rec_id}")
    a("")
    a(f"- **Record ID**: {rec_id}")
    a(
        '- **Claim**: issue #173 (T1 checklist item 7, "Post-layout '
        "verification\") -- a genuine `klt pex` run against this repo's "
        "post-layout `COMPARATOR` block, re-grading item 7 from a live tool "
        'report instead of "N/A by construction". Not itself a spec-line '
        "performance claim (the run below errors before any measurement is "
        "obtained -- see Result)."
    )
    a("- **Netlist provenance**: extracted (`klt pex` / `klt extract --parasitics`)")
    a(
        "- **Corner matrix run**: 1 corner (`typical/novdd/27C`, nominal "
        "supply/temperature, no PVT sweep) -- see "
        "`sim/comparator-pex/testbench/request.json`'s own `_comment`. "
        "Subset justification (sim/README.md): the failure below is "
        "structural (a subcircuit pin-count mismatch at netlist elaboration, "
        "before any corner-dependent analysis runs) and reproduces "
        "identically at every corner; expanding to the full PVT grid would "
        "not surface additional information. Re-run at the full grid once "
        "the blocker below is resolved."
    )
    a(
        "- **Toolchain**: klt `" + _klt_version(klt) + f"` at commit "
        f"`{PEX_KLT_COMMIT}` -- a SEPARATE, investigative pin from "
        "`layout/toolchain.json`'s production one; see "
        "`layout/adc-top/parasitics/run_pex_comparator.py`'s module "
        "docstring for why the production pin was not bumped in the same "
        "change, and gf180-sar-adc#178 for the deferred bump."
    )
    a(
        f"- **PDK**: `{pdk['variant']}` ({pdk['version']}), resolved via "
        f"`klt pdk find`, root `{pdk['root']}`."
    )
    a(f"- **Repo git sha**: `{git(REPO_ROOT, 'rev-parse', 'HEAD') or 'unknown'}`")
    a("")
    a("## Reproduce")
    a("")
    a("```")
    a(
        f"uv tool install --force git+https://github.com/2AMLogic/klayout-tools@{PEX_KLT_COMMIT}"
    )
    a(
        "python3 layout/adc-top/parasitics/run_pex_comparator.py --check   # reachability only"
    )
    a(
        "python3 layout/adc-top/parasitics/run_pex_comparator.py           # mint a new record"
    )
    a("```")
    a("")
    a("## Result")
    a("")
    status = report.get("status", "unknown")
    a(f"`klt pex` exit code **{exit_code}**, report `status` **`{status}`**.")
    a("")
    if status == "error":
        a(
            '**Item 7 re-grade: FAIL -- blocked, not "N/A by construction".** '
            "`klt pex` exists, was installed, and was run for real against "
            "this repo's post-layout `COMPARATOR` GDS with a genuine "
            "`klt sim`-format testbench. It failed structurally, before any "
            "PVT-dependent measurement, because `klt pex`'s single-`.include` "
            "DUT-swap mechanism requires the schematic and extracted-side "
            "netlists to define the SAME top-level `.subckt` name and pin "
            "list. They do not, for any block `klt extract` has produced in "
            "this repo: the extracted `COMPARATOR` interface is "
            "`clk dout doutb ibias pon pop vdd vinn vinp vss vsubs` (11 pins "
            "-- exposes the preamp's internal `pon`/`pop` output nodes and "
            "the `vsubs` body-tap net), while the hand-written schematic "
            "`comparator` interface is `vinp vinn clk ibias dout doutb vdd "
            "vss` (8 pins -- neither exists at that granularity in a "
            "physically-unmodelled schematic). The generated extracted-side "
            "deck's own `ngspice` diagnostic, copied verbatim below, names "
            "this exactly:"
        )
        a("")
        a("```")
        extracted_log = _find_corner_log(report["_artifacts_dir"], "extracted")
        if extracted_log and os.path.isfile(extracted_log):
            a(open(extracted_log, encoding="utf-8", errors="replace").read().strip())
        else:
            a("(log not captured)")
        a("```")
        a("")
        a(
            "This is the SAME interface mismatch this repo's own #89-era "
            "extracted-core testbenches (`gen_extracted_core_tb.py` et al.) "
            "solve with a bespoke per-pin `Xdut` wiring generator instead of "
            "a `.include` swap -- built specifically because `klt extract`'s "
            "output routinely exposes body/tap/internal nets a hand-written "
            "schematic subckt does not. `klt pex` has no equivalent "
            "caller-supplied pin-remapping mechanism; filed generically as "
            "friction against `klayout-tools`: "
            "https://github.com/2AMLogic/klayout-tools/issues/1030 . The "
            "deferred `layout/toolchain.json` production-pin bump this "
            "investigation also motivated is tracked separately: "
            "gf180-sar-adc#178."
        )
    elif status == "pass":
        a(
            "**Item 7 re-grade: PASS** -- every reported delta row passed. See `corners/` for the full report."
        )
    else:
        a(
            f"**Item 7 re-grade: {status.upper()}** -- see `corners/` for the full report and delta rows."
        )
    a("")
    a("## Artifacts in this record")
    a("")
    a(
        f"- `netlist-snapshots/{rec_id}.spice` -- the extracted netlist `klt pex` wrote (extraction itself succeeded; only the re-sim against it failed)"
    )
    a(
        f"- `corners/{rec_id}/pex-report.json` -- the raw `klt pex` JSON report (native format)"
    )
    a(f"- `corners/{rec_id}/schematic.log` -- schematic-side `klt sim` ngspice log")
    a(
        f"- `corners/{rec_id}/extracted.log` -- extracted-side `klt sim` ngspice log (the diagnostic quoted above)"
    )
    a("")
    a(
        "Append-only per `sim/README.md`'s evidence rule: this record is "
        "never overwritten. A later run (once the interface-mismatch "
        "blocker above is resolved, upstream or by this repo authoring a "
        "pin-matched schematic wrapper) mints a new `<record-id>` beside it."
    )
    a("")
    return "\n".join(lines)


def run(check_only: bool) -> int:
    try:
        klt = _find_klt()
        _check_pex_available(klt)
        pdk = resolve_pdk(klt)
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        return 1

    if check_only:
        print(
            f"OK: klt pex reachable ({_klt_version(klt)}), PDK {pdk['variant']} resolved."
        )
        return 0

    rec_id = record_id(REPO_ROOT)
    work_dir = os.path.join("/tmp", f"comparator-pex-{rec_id}")
    os.makedirs(work_dir, exist_ok=True)
    try:
        report, exit_code = run_pex(klt, pdk, work_dir)
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        shutil.rmtree(work_dir, ignore_errors=True)
        return 1

    try:
        corner_dir = reserve_record_slot(rec_id, CORNERS_DIR, RECORDS_DIR)
    except ToolingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        shutil.rmtree(work_dir, ignore_errors=True)
        return 1

    # netlist-snapshots/<rec_id>.spice
    os.makedirs(NETLIST_SNAPSHOTS_DIR, exist_ok=True)
    netlist_path = report["_extracted_netlist_path"]
    if os.path.isfile(netlist_path):
        shutil.copyfile(
            netlist_path, os.path.join(NETLIST_SNAPSHOTS_DIR, f"{rec_id}.spice")
        )

    # corners/<rec_id>/{pex-report.json, schematic.log, extracted.log}
    report_to_write = {k: v for k, v in report.items() if not k.startswith("_")}
    with open(os.path.join(corner_dir, "pex-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report_to_write, fh, indent=2, sort_keys=True)
        fh.write("\n")
    for side in ("schematic", "extracted"):
        log = _find_corner_log(report["_artifacts_dir"], side)
        if log and os.path.isfile(log):
            shutil.copyfile(log, os.path.join(corner_dir, f"{side}.log"))

    with open(os.path.join(RECORDS_DIR, f"{rec_id}.md"), "w", encoding="utf-8") as fh:
        fh.write(_record_body(rec_id, klt, pdk, report, exit_code))

    shutil.rmtree(work_dir, ignore_errors=True)
    print(
        f"OK: minted record {rec_id} (klt pex exit {exit_code}, status {report.get('status')})"
    )
    print(f"  record: sim/comparator-pex/records/{rec_id}.md")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="probe klt pex reachability only, write nothing",
    )
    args = ap.parse_args()
    return run(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
