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
        --pdk gf180mcuD --pdk-root <resolved via `klt pdk find`>             \
        -o <report>/adc_top.para.spice   --format json
    klt extract ../adc_block.gds --deck gf180mcu --parasitics --top ADC_BLOCK \
        --pdk gf180mcuD --pdk-root <resolved via `klt pdk find`>             \
        -o <report>/adc_block.para.spice --format json
    klt extract ../cells/adc_tgate.gds --deck gf180mcu --parasitics          \
        --top ADC_TGATE --pdk gf180mcuD --pdk-root <as above>                \
        -o <report>/adc_tgate.para.spice --format json

The block list is `cells.json`'s `blocks` map, not a constant here, so a new
target is a manifest entry plus its asserted counts. It carries whole blocks
(`adc_top`, `adc_block`) and drawn LEAF cells (`adc_tgate`) alike: the leaf is
there because `sim/extracted-delta-summary.md` SS6.3's post-layout
switch-R_on re-take needs a real extracted netlist of the drawn transmission
gate, and `layout/adc-top/cells/` is where the only standalone drawn cells
live.

`--pdk`/`--pdk-root` (added: this revision) bind every extracted MOS device to
the real PDK subcircuit (`X ... nfet_03v3`/`pfet_03v3` -- verified directly,
the exact syntax `design/adc-top/adc_top.spice`'s own `.subckt`s use) instead
of a bare `M ... nfet` device-class card that cannot bind to
`sm141064.ngspice` at all. This closes the *model-name* half of the
simulation-integration gap described below. `resolve_pdk()` calls `klt pdk
find` the same way `sim/harness/pdk.py` resolves `PDK_ROOT`/`PDK`, so this
script never hardcodes a PDK path; when no PDK resolves (`PDK_ROOT` unset),
extraction still runs and is still asserted, just without the PDK bind (the
record says so either way).

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
sim/ harness. The `--pdk` binding above closes the model-name half of that gap
(devices are `X ... nfet_03v3`/`pfet_03v3`, a drop-in against
`sm141064.ngspice`), but NOT all of it: every PMOS device's body (Nwell)
terminal still lands on an anonymous, un-biased net (gf180mcu's curated
extraction deck has no tap/well-label layer), not the `vdd` tie the schematic
assumes -- verified directly with a reproduced ngspice smoke test (a
one-PMOS-device extraction's anonymous body net settles to ~0 V against a
driven-low source, not 3.3 V). See README.md in this directory, section
"Extracted-netlist resimulation", for the full writeup and the filed upstream
issue (2AMLogic/klayout-tools#555). This runner produces and substantiates the
netlist that follow-up work (issue #89) consumes; it does not itself make a
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
from klt_env import (  # noqa: E402  (import follows the sys.path setup above)
    ToolingError,
    check_klt_capabilities,
    find_klt,
    klt_version,
)

MANIFEST_PATH = os.path.join(HERE, "cells.json")
RECORDS_DIR = os.path.join(HERE, "records")
REPORTS_DIR = os.path.join(HERE, "reports")
DECK = "gf180mcu"


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


def _load_manifest() -> dict:
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolingError(f"cannot read manifest {MANIFEST_PATH}: {exc}") from exc


def _require_klt() -> str:
    """`find_klt()` + `check_klt_capabilities()` -- the same two `klt_env`
    calls `layout/drc/run_drc.py` and `layout/lvs/run_lvs.py` make inline,
    wrapped here only because this runner calls them twice (`run()` and
    `regen_manifest()`)."""
    klt = find_klt()
    check_klt_capabilities(klt, toolchain_pin.load_toolchain_pin())
    return klt


def resolve_pdk(klt: str) -> dict | None:
    """Resolve the gf180mcu PDK install via `klt pdk find` -- the same
    resolver every other PDK-aware `klt` verb uses (and the same one
    `sim/harness/pdk.py` uses for its own PDK_ROOT/PDK resolution), so this
    script never hardcodes a PDK path.

    Returns None (not a ToolingError) when no PDK resolves: `--pdk`/`--pdk-root`
    are optional for `klt extract` (the JSON summary and device/net/pin fields
    this runner asserts are identical either way -- see "PDK resolution" in
    `klt`'s own docs/cli/extract.md), so a caller without PDK_ROOT set still
    gets a valid, asserted, schematic-parasitics extraction; it just gets bare
    `M ... nfet`/`M ... pfet` cards instead of `X ... nfet_03v3`/`pfet_03v3`
    subcircuit calls, and the record says so.
    """
    proc = subprocess.run(
        [klt, "pdk", "find", "--format", "json"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def extract_block(
    klt: str, name: str, spec: dict, out_dir: str, pdk: dict | None
) -> dict:
    """Run `klt extract --parasitics` for one block; return its JSON summary.

    Writes `<out_dir>/<name>.para.spice` and `<out_dir>/<name>.extract.json`.

    When `pdk` resolves (see `resolve_pdk`), also passes `--pdk`/`--pdk-root`,
    which makes `klt` bind every extracted MOS device to the real PDK
    subcircuit (`nfet_03v3`/`pfet_03v3` -- verified directly:
    `grep '^X' adc_top.para.spice` shows `X$1 ... nfet_03v3 L=... W=...`, the
    exact device syntax `design/adc-top/adc_top.spice`'s own `.subckt`s use)
    instead of the bare `M ... nfet` device-class card a `--deck`-only
    extraction writes. This closes the *model-name* half of the
    "simulation-integration gap" this directory's README describes -- see
    README.md's "Extracted-netlist resimulation" section for what it does
    *not* close (the open PMOS-body net, upstream
    2AMLogic/klayout-tools#555).
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
    if pdk is not None:
        cmd += ["--pdk", pdk["variant"], "--pdk-root", pdk["root"]]
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


def check_block(name: str, spec: dict, summary: dict, pdk: dict | None) -> list[str]:
    """Return a list of human-readable assertion failures for one block."""
    problems: list[str] = []
    expect = spec["expect"]

    # If a PDK resolved, `--pdk`/`--pdk-root` were passed (extract_block) --
    # confirm `klt` actually bound it (summary["pdk"] populated) rather than
    # silently falling back to bare device-class cards, which would make the
    # netlist unusable against sm141064.ngspice without anyone noticing.
    if pdk is not None and not summary.get("pdk"):
        problems.append(
            f"{name}: --pdk {pdk['variant']} was passed but the extraction "
            "summary's `pdk` field is empty -- the PDK binding did not take "
            "(netlist devices would be written as bare `M ... nfet` cards, "
            "not `X ... nfet_03v3`)"
        )

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
        # `r_count`/`c_count` only assert the NUMBER of extracted RC
        # elements, not their VALUES -- issue #178 found live that this is
        # not enough: upstream `klayout-tools#764` ("model vertical-overlap
        # (crossover) coupling capacitance for --parasitics") changed how
        # `adc_top`/`adc_block`'s total extracted capacitance is computed
        # (some net-to-ground fringe area is now correctly attributed as
        # net-to-net coupling instead) WITHOUT changing `c_count` -- the
        # element count stayed identical while `total_capacitance_ff` moved
        # (`adc_top`: 5215.82fF -> 5154.95fF, adc_block: 5622.31fF ->
        # 5561.44fF, ~1.1-1.2% down; `adc_tgate`, small enough that no net
        # has two coupled conductors, was unaffected). `total_resistance_ohm`
        # was unaffected by that change in this repo's blocks but is
        # asserted here for the same reason: a magnitude regression with an
        # unchanged element count is exactly the "new shape masks a real
        # behavior change" gap `r_count`/`c_count` alone cannot catch.
        for field in ("total_resistance_ohm", "total_capacitance_ff"):
            got = para.get(field)
            want = expect.get("parasitics", {}).get(field)
            if got != want:
                problems.append(
                    f"{name}: parasitics.{field} = {got}, expected {want}"
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
        "DRC/LVS-clean `layout/adc-top/` blocks (DR-0014 four-leg bottom-plate "
        "topology), plus every leaf cell `cells.json` names, to a netlist, "
        "with the extraction path recorded for "
        "reproducibility. This record substantiates that the extracted "
        "netlist EXISTS and belongs to the committed geometry; it makes NO "
        "spec-line performance claim (that needs the netlist to be "
        "simulatable -- see ../README.md, 'The simulation-integration gap')."
    )
    a("- **Netlist provenance**: extracted (`klt extract --parasitics`)")
    a(f"- **Extraction deck**: `{DECK}`")
    a(
        "- **Toolchain**: "
        f"klt `{klt_version(klt)}` at `{klt}`; "
        f"pin `{manifest.get('_pin_commit', 'see ../../toolchain.json')}`; "
        f"python {platform.python_version()}; {platform.platform()}"
    )
    pdk = manifest.get("_pdk")
    if pdk:
        a(
            f"- **PDK binding**: `--pdk {pdk['variant']}` resolved via "
            f"`klt pdk find` ({pdk['version']}, root `{pdk['root']}`) -- every "
            "extracted MOS device is written as `X ... nfet_03v3`/`pfet_03v3` "
            "(the real PDK subcircuit), not a bare `M ... nfet` class card. "
            "See ../README.md 'Extracted-netlist resimulation' for the one "
            "gap this does NOT close (the PMOS body/Nwell net)."
        )
    else:
        a(
            "- **PDK binding**: none -- `klt pdk find` did not resolve a "
            "gf180mcu PDK install in this environment (PDK_ROOT unset?). "
            "Devices are written as bare `M ... nfet`/`M ... pfet` class "
            "cards, which do not bind to `sm141064.ngspice`'s subcircuits; "
            "re-run with PDK_ROOT set to get simulatable `X ...` cards."
        )
    a(f"- **Repo git sha**: `{_git_sha()}`")
    a("")
    a("## Extraction commands (reproducible)")
    a("")
    a("```")
    for name, spec in manifest["blocks"].items():
        cmd = (
            f"klt extract {spec['gds']} --deck {DECK} --parasitics "
            f"--top {spec['top']} -o {name}.para.spice --format json"
        )
        if pdk:
            cmd += f" --pdk {pdk['variant']} --pdk-root {pdk['root']}"
        a(cmd)
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
        # A class the deck extracted NONE of is reported as 0, not `None`: the
        # leaf-cell target (`adc_tgate`) legitimately has no MiM capacitor, and
        # "0" is the honest reading of that row -- `None` reads like a missing
        # measurement.
        dc = summary.get("device_counts", {})
        para = summary.get("parasitics", {})
        a(
            f"| `{name}` | {summary.get('top')} | {summary.get('device_count')} "
            f"| {summary.get('net_count')} | {summary.get('pin_count')} "
            f"| {dc.get('cap_mim_2f0_m4m5_noshield', 0)} | {dc.get('nfet', 0)} "
            f"| {dc.get('pfet', 0)} | {para.get('r_count')} | {para.get('c_count')} "
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

    pdk = resolve_pdk(klt)
    manifest["_pdk"] = pdk

    record_id = time.strftime("%Y%m%d-%H%M%S") + "-" + _git_sha()[:7]
    out_dir = os.path.join(REPORTS_DIR, record_id)
    # extract into a temp staging dir first so --check writes nothing
    stage = out_dir if not check_only else os.path.join("/tmp", f"para-check-{record_id}")
    os.makedirs(stage, exist_ok=True)

    summaries: dict = {}
    problems: list[str] = []
    try:
        for name, spec in manifest["blocks"].items():
            summary = extract_block(klt, name, spec, stage, pdk)
            summaries[name] = summary
            problems += check_block(name, spec, summary, pdk)
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
    pdk = resolve_pdk(klt)
    stage = os.path.join("/tmp", "para-regen")
    os.makedirs(stage, exist_ok=True)
    for name, spec in manifest["blocks"].items():
        summary = extract_block(klt, name, spec, stage, pdk)
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
                "total_resistance_ohm": summary["parasitics"]["total_resistance_ohm"],
                "total_capacitance_ff": summary["parasitics"]["total_capacitance_ff"],
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
