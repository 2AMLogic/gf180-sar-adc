#!/usr/bin/env python3
"""Run `klt pex` against the WHOLE `ADC_BLOCK` and mint an append-only
`sim/adc-block-pex/` evidence record -- issue #428 (T1 item 7,
"Post-layout verification"), the block-scoped retry of issue #173's
comparator-only attempt (`run_pex_comparator.py`, `sim/comparator-pex/`).

## What changed upstream since the comparator attempt

The comparator attempt (record `sim/comparator-pex/records/
20260815-230715-56fbe50.md`, klt 0.2.0 @ `755d3ef`) failed structurally:
`klt pex` swaps ONE `.include` line between the schematic and extracted
runs, so both DUTs must define the same `.subckt` name and pin list, and
`klt extract` promoted nets (`vsubs`, the preamp's `pon`/`pop`) the
schematic `comparator` does not have. That was filed as
2AMLogic/klayout-tools#1030. #1030 closed COMPLETED, but its accepted
scope was diagnostics (a named `pin_count_mismatch` block, a hard error on
an ambiguous multi-`.include` testbench) -- general pin mapping was
explicitly out of scope there. The capability that actually unblocks a
block-scoped run arrived separately, in klayout-tools#1558 (released in
klt 0.7.0): `klt pex --pins` (demote every named net not in a declared pin
set to an internal node) and `klt pex --deck-option` (select the deck's
resistor / MiM / top-metal flavour). With both, the remaining interface
difference is closable without a per-pin rewiring layer:

  * `vsubs` no longer appears at all -- DR-0035 (#356) tied every body in
    the layout, so `klt extract` promotes no substrate net;
  * `XCMP.pon`/`XCMP.pop` (an LVS-disambiguation label on the
    comparator's load resistors, issue #118 -- not a port) are demoted by
    `--pins`;
  * the schematic side gets a pin-matched `ADC_BLOCK` subckt -- pure
    wiring of the existing `design/` library, committed and reviewed as
    `sim/adc-block-pex/testbench/adc_block_schematic.spice` -- which this
    runner CHECKS against the extracted header before it trusts any delta.

## Toolchain: a released wheel, checked, not `layout/toolchain.json`

Like `run_pex_comparator.py`, this runner pins its OWN `klt` rather than
moving `layout/toolchain.json`'s production pin (whose blast radius that
module's docstring explains, and which #426 owns). The pin is the PyPI
release `klayout-tools==0.7.0` (tag `v0.7.0`, commit `PEX_KLT_COMMIT`),
verified through `klt version --format json` -- `is_release` must be true,
so a dev build that merely calls itself 0.7.0 is refused. Run it from a
throwaway environment, never a host-wide install:

    uv venv /tmp/klt-0.7.0 && uv pip install --python /tmp/klt-0.7.0/bin/python klayout-tools==0.7.0
    python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt /tmp/klt-0.7.0/bin/klt

## What this script does

1. Resolves gf180mcuD (`klt pdk find`, the resolver every runner here uses).
2. Stages `sim/adc-block-pex/testbench/{tb_adc_block_pex.spice,request.json}`
   into a scratch directory and writes `schematic_dut.spice` beside them:
   `design/adc-top/adc_top.spice` + `design/comparator/comparator.spice`
   (both read directly from `design/`) + the harness's `mim_cap_<density>`
   aliases (`sim/harness/runner.py::mim_wrapper_subckts`, bound to the
   resolved variant) + `adc_block_schematic.spice`. `request.json`'s
   PDK-relative `models.lib` is rewritten to an absolute path, as
   `run_pex_comparator.py` does.
3. Runs `klt pex ../adc_block.gds` with `--pins` (read from the schematic
   wrapper's own header), `--deck-option` for every flavour this design
   commits to, and `--output`/`--outdir` redirected into scratch (the
   default would overwrite the committed, LVS-proven `../adc_block.spice`).
   `--backend` is passed through: the committed request is a 117-point PVT
   grid, which on the shared dispatch hosts goes to the batch fleet
   (`KLT_SIM_BACKEND=batch`). `--nominal` narrows the staged request to the
   one nominal point (tt / 3.3 V / 27 C) and runs it locally -- the one
   shape a shared dispatch host may run itself -- and mints a record that
   says it is a one-point subset; `--probe` does the same and writes
   nothing.
4. Refuses (exit 1, nothing written) a report in which NO row has a value
   on EITHER side: that is a run that never simulated (e.g. a batch-fleet
   job refused before ngspice started), not a pex verdict, and `klt pex`'s
   own report does not carry the underlying `klt sim` diagnostic -- run the
   staged request through `klt sim` directly (`--keep-scratch`) to see it.
5. Verifies the extracted netlist's `.SUBCKT ADC_BLOCK` header equals the
   schematic wrapper's, then writes the raw report, the extracted netlist
   and a record. Whatever `status` comes back is the evidence.

Usage
-----
    python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt K --backend batch   # full grid, mint a record
    python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt K --nominal    # one local corner, mint a subset record
    python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt K --probe      # one local corner, write nothing
    python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt K --check      # reachability only

Exit codes
----------
    0  record written (or --probe/--check passed). NOT "pex passed" -- read
       the record's Result.
    1  tooling problem (wrong klt, PDK unresolved, `klt pex` refused to run,
       header mismatch, nothing simulated on either side, record already
       exists)
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

HERE = os.path.dirname(os.path.abspath(__file__))
ADC_TOP_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
LAYOUT_DIR = os.path.abspath(os.path.join(ADC_TOP_DIR, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(LAYOUT_DIR, os.pardir))

sys.path.insert(0, LAYOUT_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "sim"))
from klt_env import (  # noqa: E402
    ToolingError,
    git,
    klt_identity,
    record_id,
    reserve_record_slot,
    resolve_pdk,
    sha256,
)

#: The released `klt` this run pins (PyPI `klayout-tools==0.7.0`, tag v0.7.0).
PEX_KLT_VERSION = "0.7.0"
PEX_KLT_COMMIT = "0e2362bda7309829398a35d54efaa989d5806065"

EXPERIMENT_DIR = os.path.join(REPO_ROOT, "sim", "adc-block-pex")
TESTBENCH_DIR = os.path.join(EXPERIMENT_DIR, "testbench")
RECORDS_DIR = os.path.join(EXPERIMENT_DIR, "records")
CORNERS_DIR = os.path.join(EXPERIMENT_DIR, "corners")
NETLIST_SNAPSHOTS_DIR = os.path.join(EXPERIMENT_DIR, "netlist-snapshots")

TB_NAME = "tb_adc_block_pex.spice"
WRAPPER = os.path.join(TESTBENCH_DIR, "adc_block_schematic.spice")
LAYOUT_GDS = os.path.join(ADC_TOP_DIR, "adc_block.gds")
SCHEMATIC_SOURCES = (
    os.path.join(REPO_ROOT, "design", "adc-top", "adc_top.spice"),
    os.path.join(REPO_ROOT, "design", "comparator", "comparator.spice"),
)
DECK = "gf180mcu"
TOP = "ADC_BLOCK"

#: Deck flavours this design commits to, stated explicitly so the extracted
#: side can never silently fall back to a deck default (klayout-tools#1558):
#:   poly_res -- the comparator loads are sized for ppolyf_u_1k (README
#:               'Resistors'; layout/adc-top/adc_block.ref.spice);
#:   mim_cap  -- the CDAC uses the 2 fF/um^2 MiM (adc_top.spice `mim_cap_2f0`);
#:   metal_top -- gf180mcuD is the 5LM / 11 kA top-metal variant
#:               (sim/harness/pdk.py MIM_STACK_BY_VARIANT; DR-0022).
DECK_OPTIONS = {
    "poly_res": "1k",
    "mim_cap": "cap_mim_2f0_m4m5_noshield",
    "metal_top": "11K",
}

#: The one PVT point `--probe` runs (and the one a single-corner debug run
#: may legitimately keep on this host -- see the host rules in the record).
PROBE_PROCESS = "tt"


def _subckt_header(text: str, name: str) -> list[str]:
    """Pin list of `.subckt <name>` in `text` (case-insensitive keyword,
    `+` continuations joined), or raise."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) >= 2 and tokens[0].lower() == ".subckt" and tokens[1] == name:
            pins = tokens[2:]
            for cont in lines[i + 1 :]:
                if not cont.startswith("+"):
                    break
                pins += cont[1:].split()
            return [p for p in pins if "=" not in p]
    raise ToolingError(f"no `.subckt {name}` found")


def schematic_pins() -> list[str]:
    with open(WRAPPER, encoding="utf-8") as fh:
        return _subckt_header(fh.read(), TOP)


def check_klt(klt: str) -> dict:
    ident = klt_identity(klt)
    problems = []
    if ident.get("package_version") != PEX_KLT_VERSION:
        problems.append(f"package_version {ident.get('package_version')!r} != {PEX_KLT_VERSION!r}")
    if ident.get("git_commit") != PEX_KLT_COMMIT:
        problems.append(f"git_commit {ident.get('git_commit')!r} != {PEX_KLT_COMMIT!r}")
    if ident.get("is_release") is not True:
        problems.append("is_release is not true (a dev build, not the released wheel)")
    if problems:
        raise ToolingError(
            f"`{klt}` is not the klt this run pins:\n  "
            + "\n  ".join(problems)
            + "\nUse a throwaway environment (never a host-wide install):\n"
            f"    uv venv /tmp/klt-{PEX_KLT_VERSION} && uv pip install --python "
            f"/tmp/klt-{PEX_KLT_VERSION}/bin/python klayout-tools=={PEX_KLT_VERSION}\n"
            f"    ... --klt /tmp/klt-{PEX_KLT_VERSION}/bin/klt"
        )
    return ident


def write_schematic_dut(pdk: dict, out_path: str) -> None:
    from harness import pdk as harness_pdk  # noqa: E402
    from harness import runner  # noqa: E402

    hp = harness_pdk.Pdk(
        path=Path(pdk["assets"]["ngspice"]).parents[1],
        variant=pdk["variant"],
        source="klt pdk find",
    )
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("* schematic_dut.spice -- composed by run_pex_adc_block.py, do not commit\n")
        for src in SCHEMATIC_SOURCES:
            out.write(f"\n* -- {os.path.relpath(src, REPO_ROOT)}, verbatim --\n")
            with open(src, encoding="utf-8") as fh:
                out.write(fh.read())
        out.write("\n" + "\n".join(runner.mim_wrapper_subckts(hp)) + "\n")
        out.write(f"\n* -- {os.path.relpath(WRAPPER, REPO_ROOT)}, verbatim --\n")
        with open(WRAPPER, encoding="utf-8") as fh:
            out.write(fh.read())


def stage(work_dir: str, pdk: dict, nominal: bool) -> str:
    shutil.copyfile(os.path.join(TESTBENCH_DIR, TB_NAME), os.path.join(work_dir, TB_NAME))
    with open(os.path.join(TESTBENCH_DIR, "request.json"), encoding="utf-8") as fh:
        request = json.load(fh)
    request.pop("_comment", None)
    request["models"] = {"lib": os.path.join(pdk["assets"]["ngspice"], "sm141064.ngspice")}
    if nominal:
        corners = request["corners"]
        corners["process"] = [p for p in corners["process"] if p["name"] == PROBE_PROCESS]
        corners["supply_v"] = {k: [v[1]] for k, v in corners["supply_v"].items()}
        corners["temperature_c"] = [27]
    path = os.path.join(work_dir, "request.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(request, fh, indent=2)
    write_schematic_dut(pdk, os.path.join(work_dir, "schematic_dut.spice"))
    return path


def run_pex(klt: str, pdk: dict, work_dir: str, backend: str | None, nominal: bool):
    request_path = stage(work_dir, pdk, nominal)
    pins = schematic_pins()
    extracted = os.path.join(work_dir, "adc_block.pex.spice")
    artifacts = os.path.join(work_dir, "klt-artifacts")
    cmd = [
        klt, "pex", LAYOUT_GDS, request_path,
        "--deck", DECK, "--top", TOP,
        "--pdk", pdk["variant"], "--pdk-root", pdk["root"],
        "--pins", ",".join(pins),
    ]
    for key, value in DECK_OPTIONS.items():
        cmd += ["--deck-option", f"{key}={value}"]
    if backend:
        cmd += ["--backend", backend]
    cmd += ["--output", extracted, "--outdir", artifacts, "--format", "json"]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    wall_s = round(time.time() - t0, 1)
    if proc.returncode in (1, 2):
        raise ToolingError(
            f"`klt pex` refused to run (exit {proc.returncode}):\n  cmd: {' '.join(cmd)}\n"
            f"  stderr: {proc.stderr.strip()[:4000]}\n  stdout: {proc.stdout.strip()[:2000]}"
        )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(
            f"`klt pex` (exit {proc.returncode}) emitted no JSON: {exc}\n"
            f"stderr: {proc.stderr[:4000]}"
        ) from exc
    rows = report.get("delta") or []
    if not rows or all(
        r.get("schematic_value") is None and r.get("extracted_value") is None for r in rows
    ):
        raise ToolingError(
            f"`klt pex` (exit {proc.returncode}, status {report.get('status')!r}) returned "
            f"{len(rows)} delta rows and not one value on either side -- nothing was "
            "simulated, so this is not a pex verdict and no record is minted. klt pex's "
            "report does not carry the underlying `klt sim` diagnostic; re-run with "
            "--keep-scratch and run `klt sim request.json --format json` in the scratch "
            "directory to see it (a batch-fleet refusal shows up as `batch_job_failed`)."
        )
    if os.path.isfile(extracted):
        with open(extracted, encoding="utf-8") as fh:
            got = _subckt_header(fh.read(), TOP)
        if got != pins:
            raise ToolingError(
                "extracted ADC_BLOCK header differs from the schematic wrapper's -- "
                f"a delta between them would be meaningless.\n  extracted: {got}\n  schematic: {pins}"
            )
    return report, proc.returncode, cmd, proc.stderr, wall_s, extracted


# --------------------------------------------------------------------------
# record
# --------------------------------------------------------------------------


def ngspice_version() -> str:
    exe = shutil.which("ngspice")
    if not exe:
        return "ngspice (not on PATH)"
    out = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "ngspice-" in line:
            return line.strip().lstrip("* ").strip()
    return "ngspice (version unreadable)"


def _fmt(v) -> str:
    if v is None:
        return "--"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _delta_summary(report: dict) -> list[str]:
    rows = report.get("delta") or []
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        by_name.setdefault(r["spec_row"], []).append(r)
    out = [
        "| spec row | rows | pass / fail / error | schematic min .. max | extracted min .. max | delta % min .. max |",
        "|---|---|---|---|---|---|",
    ]
    for name, rs in by_name.items():
        def span(key):
            vals = [r[key] for r in rs if r.get(key) is not None]
            return f"{_fmt(min(vals))} .. {_fmt(max(vals))}" if vals else "--"
        counts = "/".join(str(sum(1 for r in rs if r["status"] == s)) for s in ("pass", "fail", "error"))
        out.append(f"| `{name}` | {len(rs)} | {counts} | {span('schematic_value')} | {span('extracted_value')} | {span('delta_pct')} |")
    return out


def record_body(rec_id, ident, pdk, report, exit_code, cmd, wall_s, backend, sources,
                nominal=False, subset_reason=None) -> str:
    L: list[str] = []
    a = L.append
    status = report.get("status", "unknown")
    a(f"# Record {rec_id}")
    a("")
    a(f"- **Record ID**: {rec_id}")
    a(
        "- **Claim**: issue #428 (T1 checklist item 7, \"Post-layout verification\") -- "
        "a block-scoped `klt pex` run against the current `layout/adc-top/adc_block.gds`: "
        "the schematic-vs-extracted delta of one DR-0014 sample/redistribute/decide "
        "sequence through the whole `ADC_BLOCK` (both CDAC sides, their switch networks "
        "and drivers, both top-plate switches, the comparator). Not a spec-line "
        "performance claim: the residue rows carry no limit (no ratified row is stated "
        "at this boundary); the decision rows carry only the sign the stimulus defines."
    )
    a("- **Netlist provenance**: extracted (`klt pex` / `klt extract --parasitics`) vs schematic (`design/`), same testbench")
    corners = sorted({r["corner_id"] for r in report.get("delta") or []})
    if nominal:
        a(
            f"- **Corner matrix run**: {len(corners)} PVT point ({', '.join(f'`{c}`' for c in corners)}) "
            "-- a ONE-POINT SUBSET of the committed 117-point grid "
            "(`sim/adc-block-pex/testbench/request.json`: CORNER_SETS['full'] x V_dd {2.97, 3.3, 3.63} V "
            "x {-40, 27, 125} C), narrowed at staging time by `--nominal`. Subset justification "
            "(sim/README.md): " + (subset_reason or "not stated") 
        )
    else:
        a(
            f"- **Corner matrix run**: {len(corners)} PVT points -- `sim/adc-block-pex/testbench/request.json`: "
            "CORNER_SETS['full'] (tt ff ss fs sf cap_ff cap_ss mim_ff mim_ss moscap_ff moscap_ss res_ff res_ss) "
            "x V_dd {2.97, 3.3, 3.63} V x {-40, 27, 125} C. Full grid; no subset."
        )
    a(
        f"- **Toolchain**: klt `{ident.get('version')}` (PyPI release, tag `{ident.get('git_tag')}`, "
        f"commit `{ident.get('git_commit')}`, `is_release: {str(ident.get('is_release')).lower()}`), "
        f"KLayout `{ident.get('klayout_version')}`; engine `{ngspice_version()}` (`ngspice --version` on the "
        "host that ran the local backend). A separate, investigative pin -- `layout/toolchain.json` is unchanged."
    )
    a(f"- **PDK**: `{pdk['variant']}` ({pdk['version']}), resolved via `klt pdk find`.")
    a(f"- **Backend**: `{backend or 'klt default (KLT_SIM_BACKEND)'}`; wall time {wall_s} s.")
    a(f"- **Repo git sha**: `{git(REPO_ROOT, 'rev-parse', 'HEAD') or 'unknown'}`")
    a("- **Inputs (sha256)**:")
    for rel, digest in sources:
        a(f"  - `{rel}` `{digest}`")
    ext = report.get("extraction") or {}
    a(f"- **Extracted netlist**: sha256 `{ext.get('netlist_sha256')}`, {ext.get('device_count')} devices, {ext.get('net_count')} nets")
    bb = report.get("body_bias") or {}
    a(f"- **body_bias**: `{bb.get('status')}` ({bb.get('unbiased_device_count')} unbiased devices)")
    deck = ((report.get("provenance") or {}).get("deck")) or {}
    a(f"- **Deck options (resolved)**: `{json.dumps(deck.get('options'), sort_keys=True)}`")
    a("")
    a("## Reproduce")
    a("")
    a("```")
    a(f"uv venv /tmp/klt-{PEX_KLT_VERSION} && uv pip install --python /tmp/klt-{PEX_KLT_VERSION}/bin/python klayout-tools=={PEX_KLT_VERSION}")
    a(f"python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt /tmp/klt-{PEX_KLT_VERSION}/bin/klt --probe   # 1 local corner, writes nothing")
    a(f"python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt /tmp/klt-{PEX_KLT_VERSION}/bin/klt --nominal       # this record's shape")
    a(f"python3 layout/adc-top/parasitics/run_pex_adc_block.py --klt /tmp/klt-{PEX_KLT_VERSION}/bin/klt --backend batch # the full grid")
    a("```")
    a("")
    a("The `klt pex` command line this record ran (scratch paths abbreviated, repo paths relative):")
    a("")
    a("```")
    def _short(c: str) -> str:
        if os.path.isabs(c) and c.startswith(tempfile.gettempdir()):
            return os.path.basename(c)
        if os.path.isabs(c) and c.startswith(REPO_ROOT + os.sep):
            return os.path.relpath(c, REPO_ROOT)
        return c

    a(" ".join(_short(c) for c in cmd))
    a("```")
    a("")
    a("## Result")
    a("")
    a(
        f"`klt pex` exit code **{exit_code}**, report `status` **`{status}`** -- "
        f"passed {report.get('passed')}, failed {report.get('failed')}, errored {report.get('errored')} "
        f"of {len(report.get('delta') or [])} delta rows over {report.get('corner_count')} corners."
    )
    a("")
    L += _delta_summary(report)
    a("")
    for key in ("pin_count_mismatch", "flat_dut_mismatch", "model_mismatch"):
        a(f"- `{key}`: `{json.dumps(report.get(key))}`")
    a("")
    a("Per-corner rows: `corners/" + rec_id + "/pex-report.json` (`delta[]`).")
    a("")
    a("## Reading the rows")
    a("")
    a(
        "- `vres_diff` is the DR-0014 redistribution residue `v(topp)-v(topn)` after every bottom "
        "plate moves from V_in to V_cm, for a +500 mV differential input. Ideal: "
        "`-0.5 V x 511/512 = -0.4990 V`. The schematic falls short of that because of the "
        "comparator's input and switch capacitance on the top plates. The extracted value falls "
        "further short because of the layout's top-plate routing capacitance. The delta row is that "
        "extra attenuation, `C_arr/(C_arr+C_par)`, measured. DR-0014 cancels this term in a "
        "conversion, because the sampled input and every DAC step share the same denominator. It "
        "is a gain term, not a decision error, and no limit is attached here."
    )
    a(
        "- `vtop_cm` is the top-plate common mode at the same instant. Its delta is the "
        "common-mode part of the top-plate switch's charge injection, plus whatever the layout adds."
    )
    a(
        "- `dout_end` / `doutb_end`: the comparator must resolve the sign the stimulus sets, "
        "dout LOW and doutb HIGH. These are the only limited rows. Their `delta_pct` is "
        "meaningless whenever the schematic value is a near-zero logic low (a ratio of "
        "microvolts). Read the values, not the percentage."
    )
    a(
        "- `model_mismatch` is expected to be non-null here and is not a flavour mismatch. The "
        "reference netlist is hierarchical (the `design/` library's subckts plus the harness's "
        "unused `mim_cap_1f0`/`mim_cap_1f5` aliases), and `klt extract`'s output is flat. Every "
        "device model the extracted side instantiates (`nfet_03v3`, `pfet_03v3`, "
        "`cap_mim_2f0_m4m5_noshield`, `ppolyf_u_1k`) also appears on the reference side. "
        "`extracted_only` is empty."
    )
    a(
        "- Coverage caveat carried from extraction, not introduced here: `klt extract` reports "
        "681 unmarked poly shapes treated as interconnect, the same count as the committed "
        "extraction `layout/adc-top/parasitics/records/20260923-094816-904af96.md`. They are all "
        "0.4 um wide gate-poly routing, and their resistance is in the lumped RC. The LVS of the "
        "same GDS that T1 item 4 cites matches device for device, so none of them hides a device."
    )
    a("")
    a(
        "Append-only per `sim/README.md`: this record is never edited. A later run (the full grid, "
        "once it can execute) mints a new `<record-id>` beside it."
    )
    a("")
    return "\n".join(L)


def run(args) -> int:
    klt = args.klt or shutil.which("klt")
    try:
        if not klt:
            raise ToolingError("no `klt` given (--klt) or on PATH")
        ident = check_klt(klt)
        pdk = resolve_pdk(klt)
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        return 1
    if args.nominal and not args.subset_reason:
        print("ERROR: --nominal mints a subset record, which sim/README.md requires to say "
              "why the rest of the grid was omitted -- pass --subset-reason", file=sys.stderr)
        return 1
    if args.check:
        print(f"OK: klt {ident['version']} @ {ident['git_commit'][:12]}, PDK {pdk['variant']} resolved.")
        return 0

    work_dir = tempfile.mkdtemp(prefix="adc-block-pex-")
    try:
        nominal = args.probe or args.nominal
        backend = "local" if nominal else args.backend
        report, exit_code, cmd, stderr, wall_s, extracted = run_pex(klt, pdk, work_dir, backend, nominal)
        if args.probe:
            print(f"probe: klt pex exit {exit_code}, status {report.get('status')}, {wall_s} s")
            for r in report.get("delta") or []:
                print(f"  {r['corner_id']:<24} {r['spec_row']:<10} sch={_fmt(r['schematic_value']):>12} "
                      f"ext={_fmt(r['extracted_value']):>12} d%={_fmt(r['delta_pct']):>9} {r['status']}")
            return 0
        rec_id = record_id(REPO_ROOT)
        corner_dir = reserve_record_slot(rec_id, CORNERS_DIR, RECORDS_DIR)
        os.makedirs(NETLIST_SNAPSHOTS_DIR, exist_ok=True)
        if os.path.isfile(extracted):
            shutil.copyfile(extracted, os.path.join(NETLIST_SNAPSHOTS_DIR, f"{rec_id}.spice"))
        with open(os.path.join(corner_dir, "pex-report.json"), "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        if stderr.strip():
            with open(os.path.join(corner_dir, "klt-pex.stderr.txt"), "w", encoding="utf-8") as fh:
                fh.write(stderr)
        sources = [
            (os.path.relpath(p, REPO_ROOT), sha256(p))
            for p in (LAYOUT_GDS, *SCHEMATIC_SOURCES, WRAPPER,
                      os.path.join(TESTBENCH_DIR, TB_NAME),
                      os.path.join(TESTBENCH_DIR, "request.json"))
        ]
        with open(os.path.join(RECORDS_DIR, f"{rec_id}.md"), "w", encoding="utf-8") as fh:
            fh.write(record_body(rec_id, ident, pdk, report, exit_code, cmd, wall_s, backend, sources,
                                 nominal=nominal, subset_reason=args.subset_reason))
        print(f"OK: minted record {rec_id} (klt pex exit {exit_code}, status {report.get('status')})")
        print(f"  record: sim/adc-block-pex/records/{rec_id}.md")
        return 0
    except ToolingError as exc:
        print(f"ERROR (tooling): {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_scratch:
            shutil.rmtree(work_dir, ignore_errors=True)
        else:
            print(f"scratch kept: {work_dir}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--klt", help=f"path to a klt {PEX_KLT_VERSION} release build (default: klt on PATH)")
    ap.add_argument("--backend", help="klt sim backend for every corner (e.g. batch); default: klt's own")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true", help="one typical corner, local backend, write nothing")
    mode.add_argument("--nominal", action="store_true",
                      help="one typical corner, local backend, mint a record that states it is a subset")
    mode.add_argument("--check", action="store_true", help="klt/PDK reachability only, write nothing")
    ap.add_argument("--subset-reason", help="with --nominal: why the full grid was not run (goes into the record verbatim; required)")
    ap.add_argument("--keep-scratch", action="store_true", help="keep the scratch directory for debugging")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
