#!/usr/bin/env python3
"""Run `klt extract --parasitics` on the adc-top blocks and mint an
append-only evidence record.

This is issue #17's Scope item 1: parasitic extraction of the DRC/LVS-clean
`layout/adc-top/` block to a netlist, done reproducibly with the extraction
path (tool, command, version) recorded so an outside reader can re-run it and
reach the same numbers. It is the parasitic-extraction half of the flow
`layout/lvs/run_lvs.py` stood up for LVS (issue #51): the same `klt extract`
verb, the same commit-pinned toolchain (`../../toolchain.json`), the same
append-only evidence discipline -- with the `--parasitics` flag turned on, so
the written netlist additionally carries the first-order lumped RC the
schematic-equivalent LVS extraction deliberately omits.

The underlying commands are deliberately unremarkable -- run them by hand and
you get the same netlist:

    klt extract ../adc_top.gds   --deck gf180mcu --parasitics --top ADC_TOP   \
        -o <report>/adc_top.para.spice   --format json
    klt extract ../adc_block.gds --deck gf180mcu --parasitics --top ADC_BLOCK \
        -o <report>/adc_block.para.spice --format json

What this script adds is the part that makes a run *evidence* rather than a
screenful of output:

  * it runs `klt extract` live on every invocation, so a run proves the verb
    itself, not a previously-cached netlist;
  * it **asserts** each block's extraction summary -- device_count, net_count,
    pin_count, the per-class device tally, and crucially that the `parasitics`
    block populated with the expected R/C counts -- against `cells.json`, so a
    deck that silently stops extracting the CDAC MiM caps as devices, or whose
    parasitic table stops populating, fails instead of looking green;
  * it verifies each source GDS's sha256 against `cells.json`, so a record
    provably belongs to the committed geometry, not something that happened to
    be lying around;
  * it re-hashes the written netlist and checks it against the extractor's own
    reported `netlist_sha256`, so the committed `.para.spice` is provably the
    file the summary describes;
  * it probes `klt`'s capabilities against `../../toolchain.json`'s
    `klt_required_commands` before running anything -- see that file for why
    this is a capability probe and not a version-string comparison;
  * it stamps the toolchain (`klt` version and path, interpreter, platform)
    and the repo git sha into the record;
  * it writes into a fresh `<record-id>` directory and refuses to overwrite an
    existing one, per this repo's append-only evidence rule.

WHAT THIS DOES NOT DO -- and why #17 is only partly closed by it. Producing
the parasitic netlist is Scope item 1. Scope items 2-5 (re-running the #13
testbench suite, the #14 Monte Carlo, and the schematic-vs-extracted delta
summary against it) need the extracted netlist to be *simulatable* by the
sim/ harness, and it is not yet -- see README.md in this directory, section
"The simulation-integration gap", for the specific reason (the extractor
emits device-class model cards, `M ... nfet` / `C ... cap_mim_2f0_...`, but
the harness's gf180 models are subckts, `.subckt nfet_03v3 d g s b ...`) and
for what a follow-up adaptation layer has to do. This runner produces and
substantiates the netlist those follow-ups consume; it does not itself make a
spec-line claim.

Usage
-----
    python3 layout/adc-top/parasitics/run_extract_parasitics.py            # run, mint a record
    python3 layout/adc-top/parasitics/run_extract_parasitics.py --check    # run, assert, write nothing
    python3 layout/adc-top/parasitics/run_extract_parasitics.py --regen-manifest
                                                                           # rewrite cells.json's
                                                                           # counts + GDS hashes from a
                                                                           # live run (deliberate layout
                                                                           # change only)

Exit codes
----------
    0  every assertion matched (record written unless --check)
    1  tooling problem (klt missing/incomplete, klayout missing, bad manifest,
       GDS not found, ...)
    2  at least one assertion did not match (a summary field, a parasitic
       count, or a committed artifact's hash)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ADC_TOP_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
LAYOUT_DIR = os.path.abspath(os.path.join(ADC_TOP_DIR, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(LAYOUT_DIR, os.pardir))

# toolchain_pin.py lives in layout/ and is the single implementation of the
# capability check both other runners import; parasitic extraction is the same
# toolchain fact, so it imports the same module rather than re-deriving it.
sys.path.insert(0, LAYOUT_DIR)
import toolchain_pin  # noqa: E402

MANIFEST_PATH = os.path.join(HERE, "cells.json")
RECORDS_DIR = os.path.join(HERE, "records")
REPORTS_DIR = os.path.join(HERE, "reports")
DECK = "gf180mcu"


class ToolingError(Exception):
    """Exit 1: klt/klayout/manifest problem -- not an assertion failure."""


class AssertionFailure(Exception):
    """Exit 2: klt ran but reported something the manifest did not expect."""


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", REPO_ROOT, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def _klt_version(klt: str) -> str:
    try:
        out = subprocess.run([klt, "--version"], capture_output=True, text=True)
        return out.stdout.strip() or out.stderr.strip() or "unknown"
    except OSError:
        return "unknown"


def _load_manifest() -> dict:
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolingError(f"cannot read manifest {MANIFEST_PATH}: {exc}") from exc


def _require_klt() -> str:
    klt = shutil.which("klt")
    if klt is None:
        pin = toolchain_pin.load_toolchain_pin()
        raise ToolingError(
            "`klt` not found on PATH. Install the pinned build:\n"
            f"    uv tool install --force {pin['klt_install']}"
        )
    pin = toolchain_pin.load_toolchain_pin()
    msg = toolchain_pin.klt_capability_error(klt, pin)
    if msg:
        raise ToolingError(msg)
    return klt


def extract_block(klt: str, name: str, spec: dict, out_dir: str) -> dict:
    """Run `klt extract --parasitics` for one block; return its JSON summary.

    Writes `<out_dir>/<name>.para.spice` and `<out_dir>/<name>.extract.json`.
    """
    gds = os.path.normpath(os.path.join(HERE, spec["gds"]))
    if not os.path.isfile(gds):
        raise ToolingError(f"{name}: source GDS not found: {gds}")

    netlist_out = os.path.join(out_dir, f"{name}.para.spice")
    cmd = [
        klt,
        "extract",
        gds,
        "--deck",
        DECK,
        "--parasitics",
        "--top",
        spec["top"],
        "-o",
        netlist_out,
        "--format",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ToolingError(
            f"{name}: `klt extract` exited {proc.returncode}\n"
            f"  cmd: {' '.join(cmd)}\n  stderr: {proc.stderr.strip()}"
        )
    try:
        summary = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(f"{name}: klt did not emit JSON: {exc}") from exc
    if summary.get("error"):
        raise ToolingError(f"{name}: klt reported an error: {summary['error']}")

    # persist the summary next to the netlist
    with open(os.path.join(out_dir, f"{name}.extract.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    summary["_netlist_path"] = netlist_out
    summary["_gds_path"] = gds
    return summary


def check_block(name: str, spec: dict, summary: dict) -> list[str]:
    """Return a list of human-readable assertion failures for one block."""
    problems: list[str] = []
    expect = spec["expect"]

    gds = summary["_gds_path"]
    want_gds_sha = spec.get("gds_sha256")
    if want_gds_sha:
        got = _sha256(gds)
        if got != want_gds_sha:
            problems.append(
                f"{name}: source GDS sha256 {got} != manifest {want_gds_sha} "
                f"(the committed geometry changed; re-baseline with --regen-manifest)"
            )

    # the netlist klt wrote is the artifact we commit -- prove it is the file
    # the summary describes.
    netlist = summary["_netlist_path"]
    got_netlist_sha = _sha256(netlist)
    reported = summary.get("netlist_sha256")
    if reported and got_netlist_sha != reported:
        problems.append(
            f"{name}: written netlist sha256 {got_netlist_sha} != reported "
            f"netlist_sha256 {reported}"
        )

    for field in ("device_count", "net_count", "pin_count"):
        got = summary.get(field)
        want = expect.get(field)
        if got != want:
            problems.append(f"{name}: {field} = {got}, expected {want}")

    got_counts = summary.get("device_counts", {})
    for cls, want in expect.get("device_counts", {}).items():
        got = got_counts.get(cls)
        if got != want:
            problems.append(f"{name}: device_counts[{cls}] = {got}, expected {want}")
    extra = set(got_counts) - set(expect.get("device_counts", {}))
    if extra:
        problems.append(f"{name}: unexpected device classes extracted: {sorted(extra)}")

    para = summary.get("parasitics")
    if not isinstance(para, dict):
        problems.append(
            f"{name}: no `parasitics` block in the extraction summary -- "
            f"was --parasitics honored? (this is the whole point of this run)"
        )
    else:
        for field in ("r_count", "c_count"):
            got = para.get(field)
            want = expect.get("parasitics", {}).get(field)
            if got != want:
                problems.append(
                    f"{name}: parasitics.{field} = {got}, expected {want}"
                )
            elif not want:
                problems.append(
                    f"{name}: parasitics.{field} is {got} -- expected a "
                    f"nonzero count of extracted RC elements"
                )
    return problems


def _record_body(record_id: str, klt: str, manifest: dict, summaries: dict) -> str:
    lines: list[str] = []
    a = lines.append
    a(f"# Record {record_id}")
    a("")
    a(f"- **Record ID**: {record_id}")
    a(
        "- **Claim**: issue #17 Scope item 1 -- parasitic extraction of the "
        "DRC/LVS-clean `layout/adc-top/` block (DR-0014 four-leg bottom-plate "
        "topology) to a netlist, with the extraction path recorded for "
        "reproducibility. This record substantiates that the extracted "
        "netlist EXISTS and belongs to the committed geometry; it makes NO "
        "spec-line performance claim (that needs the netlist to be "
        "simulatable -- see ../README.md, 'The simulation-integration gap')."
    )
    a("- **Netlist provenance**: extracted (`klt extract --parasitics`)")
    a(f"- **Extraction deck**: `{DECK}`")
    a(
        "- **Toolchain**: "
        f"klt `{_klt_version(klt)}` at `{klt}`; "
        f"pin `{manifest.get('_pin_commit', 'see ../../toolchain.json')}`; "
        f"python {platform.python_version()}; {platform.platform()}"
    )
    a(f"- **Repo git sha**: `{_git_sha()}`")
    a("")
    a("## Extraction commands (reproducible)")
    a("")
    a("```")
    for name, spec in manifest["blocks"].items():
        a(
            f"klt extract {spec['gds']} --deck {DECK} --parasitics "
            f"--top {spec['top']} -o {name}.para.spice --format json"
        )
    a("```")
    a("")
    a(
        "Run through `run_extract_parasitics.py`, which additionally asserts "
        "every field below against `cells.json` and refuses to overwrite an "
        "existing record directory."
    )
    a("")
    a("## Extracted summary (asserted against `cells.json`)")
    a("")
    a(
        "| block | top | devices | nets | pins | MiM caps | nfet | pfet | "
        "para R | para C | total R (Ω) | total C (fF) |"
    )
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, summary in summaries.items():
        dc = summary.get("device_counts", {})
        para = summary.get("parasitics", {})
        a(
            f"| `{name}` | {summary.get('top')} | {summary.get('device_count')} "
            f"| {summary.get('net_count')} | {summary.get('pin_count')} "
            f"| {dc.get('cap_mim_2f0_m4m5_noshield')} | {dc.get('nfet')} "
            f"| {dc.get('pfet')} | {para.get('r_count')} | {para.get('c_count')} "
            f"| {para.get('total_resistance_ohm')} "
            f"| {para.get('total_capacitance_ff')} |"
        )
    a("")
    a("## Artifacts in this record")
    a("")
    for name in summaries:
        a(f"- `reports/{record_id}/{name}.para.spice` -- extracted netlist with RC parasitics")
        a(f"- `reports/{record_id}/{name}.extract.json` -- full structured extraction summary")
    a(f"- `reports/{record_id}/toolchain.json` -- the toolchain pin this run resolved against")
    a("")
    a(
        "Append-only per `sim/README.md`'s evidence rule: this record is never "
        "overwritten. A later extraction (new geometry, new deck) mints a new "
        "`<record-id>` beside it."
    )
    a("")
    return "\n".join(lines)


def run(check_only: bool) -> int:
    try:
        klt = _require_klt()
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        return 1

    manifest = _load_manifest()
    try:
        pin = toolchain_pin.load_toolchain_pin()
        manifest["_pin_commit"] = pin.get("klt_last_verified_commit", "unknown")
    except (OSError, json.JSONDecodeError):
        manifest["_pin_commit"] = "unknown"

    record_id = time.strftime("%Y%m%d-%H%M%S") + "-" + _git_sha()[:7]
    out_dir = os.path.join(REPORTS_DIR, record_id)
    # extract into a temp staging dir first so --check writes nothing
    stage = out_dir if not check_only else os.path.join("/tmp", f"para-check-{record_id}")
    os.makedirs(stage, exist_ok=True)

    summaries: dict = {}
    problems: list[str] = []
    try:
        for name, spec in manifest["blocks"].items():
            summary = extract_block(klt, name, spec, stage)
            summaries[name] = summary
            problems += check_block(name, spec, summary)
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        if check_only and os.path.isdir(stage):
            shutil.rmtree(stage, ignore_errors=True)
        return 1

    if problems:
        print("ASSERTION FAILURES:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if check_only:
            shutil.rmtree(stage, ignore_errors=True)
        else:
            shutil.rmtree(out_dir, ignore_errors=True)
        return 2

    if check_only:
        shutil.rmtree(stage, ignore_errors=True)
        print("OK: every extraction assertion matched (--check, nothing written).")
        return 0

    # snapshot the toolchain pin into the record
    shutil.copyfile(
        os.path.join(LAYOUT_DIR, "toolchain.json"),
        os.path.join(out_dir, "toolchain.json"),
    )
    os.makedirs(RECORDS_DIR, exist_ok=True)
    record_path = os.path.join(RECORDS_DIR, f"{record_id}.md")
    if os.path.exists(record_path):
        print(f"ERROR: record {record_path} already exists (append-only).", file=sys.stderr)
        return 1
    with open(record_path, "w", encoding="utf-8") as fh:
        fh.write(_record_body(record_id, klt, manifest, summaries))
    print(f"OK: minted record {record_id}")
    print(f"  record : {os.path.relpath(record_path, REPO_ROOT)}")
    print(f"  reports: {os.path.relpath(out_dir, REPO_ROOT)}/")
    return 0


def regen_manifest() -> int:
    """Rewrite cells.json's asserted counts + GDS hashes from a live run."""
    try:
        klt = _require_klt()
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        return 1
    manifest = _load_manifest()
    stage = os.path.join("/tmp", "para-regen")
    os.makedirs(stage, exist_ok=True)
    for name, spec in manifest["blocks"].items():
        summary = extract_block(klt, name, spec, stage)
        gds = os.path.normpath(os.path.join(HERE, spec["gds"]))
        spec["gds_sha256"] = _sha256(gds)
        spec["expect"] = {
            "device_count": summary["device_count"],
            "net_count": summary["net_count"],
            "pin_count": summary["pin_count"],
            "device_counts": summary["device_counts"],
            "parasitics": {
                "r_count": summary["parasitics"]["r_count"],
                "c_count": summary["parasitics"]["c_count"],
            },
        }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    shutil.rmtree(stage, ignore_errors=True)
    print(f"regenerated {os.path.relpath(MANIFEST_PATH, REPO_ROOT)} from a live run.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="run, assert, write nothing")
    ap.add_argument(
        "--regen-manifest",
        action="store_true",
        help="rewrite cells.json counts + hashes from a live run (deliberate layout change)",
    )
    args = ap.parse_args()
    if args.regen_manifest:
        return regen_manifest()
    return run(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
