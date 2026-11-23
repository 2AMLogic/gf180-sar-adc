#!/usr/bin/env python3
"""Re-run the `sar_ctrl` functional suite gate-level: the committed post-route
netlist plus back-annotated SDF timing per Liberty corner (issue #645, T1 item
7 digital).

    python3 design/sar-logic/tb/run_functional_gate.py [--sta-rid <rid>]

The SAME cocotb bench #642 certified (`test_sar_ctrl.py`, every code 0..1023
in both modes, every output checked every cycle, mutation sensitivity proven
on the RTL leg) runs unmodified against `layout/adc-top/sar_ctrl/sar_ctrl.v`
with the SDFs `design/sar-logic/flow/sdf_sar_ctrl.py` wrote from the
qualified post-route SPEF: one `klt functional-verification` run per corner,
`options.sdf` back-annotating that corner's file through Icarus
`$sdf_annotate` (`-gspecify -ginterconnect`), with klt's own transcript gate
failing the run on any SDF diagnostic. Cell models come from the PDK's
timing (non-`FUNCTIONAL`) branch via the request's `pdk` block.

Writes, under `design/sar-logic/tb/reports/<rid>/`:

  - `fv_request.<corner>.json`   the per-corner request (archived; re-run
                                  needs `--base-dir` or these exact relative
                                  paths, see klt functional-verification.md)
  - `fv_response.<corner>.json`  the unedited response
  - `results_icarus.<corner>.xml` cocotb's own results file
  - `record.md`                  the evidence record

Exits 1 unless every corner reports `status: pass` with
`environment.sdf.annotated: true` and a `provenance.sdf_sha256` equal to the
committed SDF it was given. Failures are recorded, never replaced.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "design" / "sar-logic" / "flow"))

from sim.harness.pdk import Pdk, PdkNotFound, find_pdk  # noqa: E402
from flow_env import CORNERS, git, klt_version, record_id, sha256, working_tree_dirty  # noqa: E402

TB_DIR = REPO_ROOT / "design" / "sar-logic" / "tb"
STA_REPORTS = REPO_ROOT / "design" / "sar-logic" / "flow" / "sar_ctrl" / "reports"
ROUTED_V = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.v"

#: The SDF-minting run this driver consumes (`sdf_sar_ctrl.py`'s record).
STA_SDF_RID = "20261121-074733-ccac27a2"

#: The post-route netlist's qualified hash (receipt `20261104-212437`, #486):
#: the replay must simulate the netlist that was routed, qualified and LVS'd.
ROUTED_V_SHA256 = "6d32ab0ed1cd1ccb4b1d2c953060afbe3e5947bf634398661c2a04423023304b"

OWN_OUTPUT_PREFIXES = ("design/sar-logic/tb/reports/",)

#: The iverilog `-T` selection is NOT cosmetic: ~10% of the annotated IOPATH
#: triplets differ across min:typ:max (worst spread 0.028-0.099 ns by corner).
#: `typ` is pinned; the verdict rests on the ~6.8 ns worst path vs the 31.25 ns
#: sampling edge, not on the triplets being uniform. The `max` leg is not run.
SDF_CORNER = "typ"

RANDOM_SEED = 645


class GateReplayError(RuntimeError):
    pass


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def build_request(out_dir: Path, corner: str, sta_rid: str) -> dict:
    """The per-corner request. Paths are relative to the request file's own
    directory (`tb/reports/<rid>/`): netlist at repo root, bench one level
    above `tb/`, SDF beside `sdf_sar_ctrl.py`'s committed output."""
    return {
        "schema": "klt.functional_verification.request/1",
        "engine": "icarus",
        "sources": ["../../../../../layout/adc-top/sar_ctrl/sar_ctrl.v"],
        "hdl_toplevel": "sar_ctrl_a",
        "testbench": {"module": "test_sar_ctrl", "search_path": "../.."},
        "pdk": {"variant": "gf180mcuD", "cell_library": "gf180mcu_fd_sc_mcu7t5v0"},
        "options": {
            "random_seed": RANDOM_SEED,
            "timescale": ["1ns", "1ps"],
            "sdf": {
                "file": f"../../../flow/sar_ctrl/reports/{sta_rid}.mcu7t5v0.sar_ctrl.{corner}.sdf",
                "corner": SDF_CORNER,
            },
        },
    }


def run_corner(pdk: Pdk, request_path: Path, run_dir: Path) -> dict:
    proc = subprocess.run(
        [
            "klt", "functional-verification", str(request_path),
            "-o", str(run_dir),
            "--pdk-root", str(pdk.path.parent),
            "--format", "json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise GateReplayError(
            f"klt functional-verification ({request_path.name}) printed no JSON (exit {proc.returncode}):\n{proc.stderr}"
        ) from None


def corner_verdict(corner: str, response: dict, sdf: Path) -> tuple[bool, list[str]]:
    """Pass iff the suite passed, the run was SDF-annotated, and the SDF the
    runner hashed is the committed file this driver pointed it at."""
    problems: list[str] = []
    if response.get("status") != "pass":
        problems.append(f"status {response.get('status')!r}")
    environment = response.get("environment") or {}
    sdf_meta = environment.get("sdf") or {}
    if sdf_meta.get("annotated") is not True:
        problems.append("environment.sdf.annotated is not true (zero-delay run?)")
    provenance = response.get("provenance") or {}
    want_sdf = sha256(sdf)  # provenance.sdf_sha256 is a bare hex digest
    if provenance.get("sdf_sha256") != want_sdf:
        problems.append(f"provenance.sdf_sha256 {provenance.get('sdf_sha256')} != committed {want_sdf}")
    sources = [
        s for s in environment.get("sources") or [] if s.get("path") == _rel(ROUTED_V)
    ]
    if len(sources) != 1 or sources[0].get("sha256") != ROUTED_V_SHA256:
        problems.append(f"netlist source pin {_rel(ROUTED_V)} absent or not {ROUTED_V_SHA256[:12]}...")
    return not problems, problems


def render_record(
    *,
    rid: str,
    when,
    pdk: Pdk,
    klt_v: str,
    corners: list[tuple[str, dict, Path, bool, list[str]]],
    dirty: bool,
    sha: str,
    sta_rid: str,
) -> str:
    rows = []
    for corner, response, sdf, ok, problems in corners:
        sdf_meta = (response.get("environment") or {}).get("sdf") or {}
        dropped = ", ".join(f"{k}×{v['count']}" for k, v in (sdf_meta.get("dropped") or {}).items())
        rows.append(
            f"| `{corner}` | {response.get('passed_count')}/{response.get('test_count')} | "
            f"`{sdf.name}` | {dropped or 'none'} | {'PASS' if ok else 'FAIL: ' + '; '.join(problems)} |"
        )
    verdict = "PASS" if all(ok for *_, ok, _ in corners) else "FAIL"
    bench = TB_DIR / "test_sar_ctrl.py"
    return f"""\
# Record {rid}.sar_ctrl.functional_verification_gate_sdf

- **Record ID**: {rid}.sar_ctrl.functional_verification_gate_sdf
- **Claim**: the post-route gate-level netlist `layout/adc-top/sar_ctrl/sar_ctrl.v` (the one LVS'd
  as `4.digital` and hash-pinned to the #486 receipt) returns the bit-exact expected code for every
  input code 0..1023 in differential and single-ended mode, with every output matching the
  cycle-accurate model every cycle, WHILE back-annotated with each Liberty corner's post-route SDF
  (written from the qualified SPEF by `sdf_sar_ctrl.py`, record `{sta_rid}.mcu7t5v0.sta_sdf`).
  Cited as `7.digital` in `signoff/gf180-sar-adc.manifest.json` (issue #645): the graded citation is
  the setup-binding slowest corner `ss_125C_3v00`; the other four corners are committed beside it.
- **Verdict**: **{verdict}** -- the bench is `test_sar_ctrl.py` UNMODIFIED from #642 (`5.digital`):
  swapping `sources` to the routed netlist and adding `options.sdf` is the only difference. The
  suite's sensitivity (nine RTL mutants killed) is #642's mutation record; mutation testing is not
  combinable with `options.sdf` (klt rejects the pair), so the gate-level leg carries no mutants of
  its own.

| Corner | Tests | SDF | Icarus-dropped SDF classes | Verdict |
| --- | --- | --- | --- | --- |
{chr(10).join(rows)}

- **What the dropped classes mean** (all machine-reported by klt, all Icarus limitations, not design
  facts): `timingcheck` -- Icarus implements SDF delays but not SDF timing checks, so no
  `$setup`/`$hold` violation *reporting* exists on this path (slack numbers remain OpenSTA's job,
  #486's receipt); `iopath_cond_expression` -- conditional-path
  IOPATHs whose condition shape Icarus's parser rejects; `iopath_ifnone_edge_modpath` -- arcs the
  cell's Verilog model declares only through `ifnone` edge-sensitive module paths (e.g. mux2_1
  `S -> Z`), which Icarus discards at elaboration: per klt, these arcs simulate with NO module-path
  delay at all (neither the SDF's nor the model's placeholder), so their characterised cell delay is
  not represented in this run (20 entries per corner); `zero_delay_*` -- zero-delay entries with
  nothing to annotate. A genuine timing failure still surfaces as a functional failure the bench
  catches, which is this leg's signal.
- **Sampling margin**: the bench drives and samples on falling edges (31.25 ns after the launching
  edge). #486's receipt times the worst reg-to-reg path at ~6.8 ns at the slowest corner (setup
  slack +55.7 ns of the 62.5 ns period; output ports carry no `set_output_delay`, so reg-to-output
  paths are not STA endpoints) -- the direct evidence the sampled outputs settle inside the
  half-cycle is the bench passing every cycle at every corner, which is what the verdict above is.
- **Inputs (sha256)**: netlist `{ROUTED_V_SHA256}` (equals the #486 receipt pin); bench
  `{sha256(bench)}`; SDFs as pinned per corner above and in `signoff/freshness.json`.
- **Tool versions**: `klt` `{klt_v}`; icarus `{(corners[0][1].get('environment') or {}).get('engine_version')}`;
  cocotb `{(corners[0][1].get('environment') or {}).get('cocotb_version')}`; PDK variant `{pdk.variant}`
  (open_pdks `{pdk.version}`, resolved via `{pdk.source}`; `--pdk-root` pinned because the install
  search is ambiguous on multi-install hosts). This klt is newer than the flow's `toolchain.json`
  pin (`0.8.0`): the `pdk` request block (klayout-tools #5782) postdates it.
- **Reproducibility**: working tree {"DIRTY at run time -- re-run against a clean checkout before trusting this record" if dirty else "clean"} at commit `{sha}`.
  Re-run: `python3 design/sar-logic/tb/run_functional_gate.py` with this record's `klt` build first
  on `PATH`. Archived requests resolve their relative paths from this directory (no `--base-dir`
  needed); `environment` paths inside a response are the run host's.
- **Links**: per-corner `fv_request.<corner>.json` / `fv_response.<corner>.json` /
  `results_icarus.<corner>.xml` beside this record; SDFs under
  `design/sar-logic/flow/sar_ctrl/reports/` (`{sta_rid}.*`).
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/tb/run_functional_gate.py` (agent-run)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sta-rid", default=STA_SDF_RID, help="record id of the sdf_sar_ctrl.py run to consume")
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args()

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if not ROUTED_V.is_file():
        print(f"ERROR: routed netlist not found at {ROUTED_V}", file=sys.stderr)
        return 1
    if sha256(ROUTED_V) != ROUTED_V_SHA256:
        print(
            f"ERROR: routed netlist hashes {sha256(ROUTED_V)}, not the #486 receipt pin {ROUTED_V_SHA256}",
            file=sys.stderr,
        )
        return 1

    sdfs = {}
    for corner, _ in CORNERS:
        sdf = STA_REPORTS / f"{args.sta_rid}.mcu7t5v0.sar_ctrl.{corner}.sdf"
        if not sdf.is_file():
            print(f"ERROR: SDF for corner {corner} not found at {_rel(sdf)} -- run sdf_sar_ctrl.py first", file=sys.stderr)
            return 1
        sdfs[corner] = sdf

    when = dt.datetime.now(dt.timezone.utc)
    rid = record_id(REPO_ROOT, when)
    out = TB_DIR / "reports" / rid
    if out.exists():
        print(f"ERROR: {out} exists -- refusing to overwrite append-only evidence", file=sys.stderr)
        return 1
    out.mkdir(parents=True)

    corners = []
    for corner, _ in CORNERS:
        request_path = out / f"fv_request.{corner}.json"
        request_path.write_text(json.dumps(build_request(out, corner, args.sta_rid), indent=2) + "\n")
        run_dir = out / f"run-{corner}"
        print(f"gate-level SDF replay: corner {corner} ...")
        try:
            response = run_corner(pdk, request_path, run_dir)
        except GateReplayError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        (out / f"fv_response.{corner}.json").write_text(json.dumps(response, indent=2) + "\n")
        results_xml = run_dir / "results_icarus.xml"
        if results_xml.is_file():
            shutil.copy(results_xml, out / f"results_icarus.{corner}.xml")
        shutil.rmtree(run_dir, ignore_errors=True)
        ok, problems = corner_verdict(corner, response, sdfs[corner])
        corners.append((corner, response, sdfs[corner], ok, problems))
        print(f"  {'PASS' if ok else 'FAIL'}: {response.get('passed_count')}/{response.get('test_count')} tests"
              + (f" -- {'; '.join(problems)}" if problems else ""))

    record = out / "record.md"
    if not args.no_record:
        record.write_text(
            render_record(
                rid=rid,
                when=when,
                pdk=pdk,
                klt_v=klt_version(REPO_ROOT),
                corners=corners,
                dirty=working_tree_dirty(REPO_ROOT, OWN_OUTPUT_PREFIXES),
                sha=git(REPO_ROOT, "rev-parse", "HEAD") or "unknown",
                sta_rid=args.sta_rid,
            )
        )
        print(f"Evidence record written to {record}")

    bad = [c for c, *_, ok, _ in corners if not ok]
    if bad:
        print(f"FAIL at corner(s): {', '.join(bad)}", file=sys.stderr)
        return 1
    print(f"All {len(corners)} corners: gate-level SDF replay of the functional suite passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
