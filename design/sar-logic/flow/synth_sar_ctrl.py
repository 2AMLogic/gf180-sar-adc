#!/usr/bin/env python3
"""Cold-start `klt synthesize` driver for `design/sar-logic/rtl/sar_ctrl.v`
(DR-0023 follow-on (a), issue #272).

DR-0023 (`spec/decision-records/DR-0023-digital-interface-device-flavor.md`)
adopted the PDK-shipped `gf180mcu_fd_sc_mcu7t5v0` / `mcu9t5v0` standard-cell
libraries at the block's 3.3 V digital rail, and explicitly deferred *which*
of the two to build against to this issue. This script synthesizes
`sar_ctrl_a` against **both**, at the `tt_025C_3v30` corner, so the choice in
`design/sar-logic/rtl/README.md` is made from real area/cell-count numbers
rather than a guess -- and commits both netlists so the choice is auditable
even though only one (see that README) is what `layout/adc-top/` actually
reserves footprint for.

Unlike `gf180-tmds-tx`'s `flow/synth_tmds_encoder.py` (this script's shape is
ported from it, per CLAUDE.md's "bootstrap from the sim-harness pattern"
rule, generalised to "port from a sibling repo's flow driver when one
exists"), this design carries **no SDC/STA claim** -- DR-0023's follow-on (a)
is scoped to RTL + synthesis + equivalence only; timing closure is follow-on
(c) (a fast-follow issue this script's own caller files, not this script).
So there is no ABC `-D` delay target here: `constraints.clock_period_ns` is
left `null`, and `klt synthesize` is asked for nothing beyond technology
mapping to each library's `tt_025C_3v30` liberty.

This script is a thin orchestrator over two already-general klayout-tools
verbs, not a reimplementation of either:

  - `klt synthesize` (Yosys + bundled ABC): RTL -> gate-level netlist,
    with its own `select -assert-none t:$_*` / re-parse "no unmapped cells"
    checks (see `docs/cli/synthesize.md`). This script re-parses the written
    netlist itself too (`cell_types`/`assert_fully_mapped` below),
    independent of and in addition to `klt synthesize`'s own check --
    the same "computed, not eyeballed" discipline `gf180-tmds-tx`'s driver
    documents.
  - `klt equiv` (`"yosys-sequential"` engine, register-correspondence
    sequential equivalence, klayout-tools#1313): `sar_ctrl.v` (gold) vs. each
    synthesized netlist (gate). The flat, no-submodule, un-renamed-register
    RTL structure (`sar_ctrl.v`'s own header comment) exists specifically so
    this engine's by-name register pairing has something to pair against --
    `"yosys"` (the default, combinational-only) engine is a hard scope error
    on a 45-flop design (`klt equiv --help`), which is exactly why this
    script asks for `"yosys-sequential"` explicitly rather than the default.

Cold-start invocation (PDK installed, `klt`/`yosys` on `$PATH` -- see
`docs/environment-setup.md`):

    python3 design/sar-logic/flow/synth_sar_ctrl.py

Writes, per library (`mcu7t5v0`/`mcu9t5v0`):

  - the gate netlist:    design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.<lib>.synth.v
  - the exact `klt synthesize` request/response and `klt equiv` request/response:
                          design/sar-logic/flow/sar_ctrl/reports/<rid>.<lib>.*.json
  - the generated Yosys script `klt synthesize` itself ran:
                          design/sar-logic/flow/sar_ctrl/reports/<rid>.<lib>.synth.ys
  - an append-only evidence record:
                          design/sar-logic/flow/sar_ctrl/records/<rid>.<lib>.md

PDK resolution reuses `sim/harness/pdk.py` (import, not a re-implementation --
see that module's own docstring), so the same `GF180_PDK_PATH`/`PDK_ROOT`/
`sim/pdk.json` resolution order this repo's whole `sim/` tree already uses
applies here too; `klt synthesize --pdk <variant>` is passed explicitly (see
"Why --pdk is passed explicitly" below) so `klt`'s own, independent PDK
discovery cannot silently resolve a different variant than the one this
script (and `sim/`) resolved.

## Why `--pdk` is passed explicitly

`klt`'s own `find_pdk()` and `sim/harness/pdk.py`'s `find_pdk()` are two
independent implementations of "search `~/.volare` for a gf180mcu variant"
(neither imports the other -- `klt` is an external tool), and they do not
necessarily agree: on the machine this script was developed on, with all
four gf180mcu variants (`gf180mcuA`..`D`) installed side by side,
`klt synthesize` with no `--pdk` flag resolved `gf180mcuA` while this
script's own `sim.harness.pdk.find_pdk()` (and every other tool in this
repo) resolves `gf180mcuD` (`sim/pdk.json`'s pinned default). Both variants
carry the *same* `open_pdks` commit (confirmed: identical `SOURCES` stamp),
so the standard-cell libraries synthesized are almost certainly byte-for-byte
identical either way here -- but "almost certainly the same by construction"
is exactly the kind of silent assumption CLAUDE.md's provenance rule exists
to rule out. Passing `--pdk {variant}` (this script's own resolved
`pdk.variant`) makes `klt`'s PDK resolution and this repo's PDK resolution
provably the same install, not just the same commit hash by coincidence.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from sim.harness.pdk import Pdk, PdkNotFound, find_pdk  # noqa: E402

TOP = "sar_ctrl_a"
RTL_SOURCE = REPO_ROOT / "design" / "sar-logic" / "rtl" / "sar_ctrl.v"

OUT_DIR = REPO_ROOT / "design" / "sar-logic" / "flow" / "sar_ctrl"
NETLIST_DIR = OUT_DIR / "netlist"
REPORTS_DIR = OUT_DIR / "reports"
RECORDS_DIR = OUT_DIR / "records"

#: Both libraries DR-0023 adopted, at the corner it names for the digital
#: partition. `design/sar-logic/rtl/README.md` records which one
#: `layout/adc-top/`'s reserved footprint actually gets built against and
#: why -- this script's job is only to produce the evidence that choice is
#: made from.
LIBRARIES = ("gf180mcu_fd_sc_mcu7t5v0", "gf180mcu_fd_sc_mcu9t5v0")
CORNER = "tt_025C_3v30"

_INSTANCE_RE = re.compile(r"^  (\S+) (\S+) \($", re.MULTILINE)


class SynthError(RuntimeError):
    """A synthesis or equivalence run failed, or its output failed a check."""


def _lib_tag(cell_library: str) -> str:
    """`gf180mcu_fd_sc_mcu7t5v0` -> `mcu7t5v0` (the short form used in every
    committed filename -- the full library name is redundant once it is
    already the containing directory/record's own subject)."""
    return cell_library.replace("gf180mcu_fd_sc_", "")


def _liberty_path(pdk: Pdk, cell_library: str, corner: str) -> Path:
    path = pdk.path / "libs.ref" / cell_library / "lib" / f"{cell_library}__{corner}.lib"
    if not path.is_file():
        raise SynthError(
            f"standard-cell liberty file not found at {path}\n"
            f"(expected the gf180mcu {cell_library} library's {corner} corner -- "
            "check the PDK install / variant)"
        )
    return path


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def record_id(when: _dt.datetime) -> str:
    """``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``, matching sim/README.md's grammar."""
    sha = _git("rev-parse", "--short", "HEAD") or "nogit"
    return f"{when.strftime('%Y%m%d-%H%M%S')}-{sha}"


def _git_status_porcelain() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout.rstrip("\n") if result.returncode == 0 else ""


#: This script's own output tree -- excluded from the "dirty working tree"
#: check the same way `gf180-tmds-tx`'s `synth.working_tree_dirty` excludes
#: its own `flow/<top>/` output, so a clean re-run of *this* script does not
#: report itself as evidence of an unclean checkout.
_OWN_OUTPUT_PREFIX = "design/sar-logic/flow/sar_ctrl/"


def working_tree_dirty() -> bool:
    status = _git_status_porcelain()
    for line in status.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path and not path.startswith(_OWN_OUTPUT_PREFIX):
            return True
    return False


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def klt_version() -> str:
    result = _run(["klt", "--version"])
    return (result.stdout or result.stderr).strip()


def yosys_version() -> str:
    result = subprocess.run(["yosys", "-V"], capture_output=True, text=True, check=True)
    return (result.stdout or result.stderr).strip()


def cell_types(netlist_path: Path) -> dict[str, int]:
    """Parse the written netlist and count instances by cell type --
    independent of, and a cross-check on, `klt synthesize`'s own
    `select -assert-none t:$_*` check (see this module's docstring)."""
    text = netlist_path.read_text()
    counts: dict[str, int] = {}
    for cell_type, _instance_name in _INSTANCE_RE.findall(text):
        counts[cell_type] = counts.get(cell_type, 0) + 1
    return counts


def assert_fully_mapped(counts: dict[str, int], cell_prefix: str) -> None:
    unmapped = sorted(t for t in counts if not t.startswith(cell_prefix))
    if unmapped:
        raise SynthError(
            "netlist contains non-standard-cell instances (unmapped): "
            + ", ".join(f"{t} x{counts[t]}" for t in unmapped)
        )
    if not counts:
        raise SynthError("netlist contains no cell instances at all -- synthesis produced nothing")


def run_synthesize(pdk: Pdk, cell_library: str, req_path: Path) -> dict:
    """Invoke `klt synthesize` for one library, returning the parsed response.

    Raises :class:`SynthError` on any non-zero exit -- `klt synthesize`'s own
    exit codes distinguish a clean run (0) from a run-time error (1) and a
    structural-defect failure (3, `structural.has_critical`); this driver
    treats both non-zero cases as fatal, since neither is a state this
    script should silently commit a netlist for.
    """
    req_path.write_text(
        json.dumps(
            {
                "schema": "klt.synthesize.request/1",
                "engine": "yosys",
                "sources": [str(RTL_SOURCE)],
                "hdl_toplevel": TOP,
                "pdk": {"cell_library": cell_library, "corner": CORNER},
                "constraints": {"clock_period_ns": None},
            },
            indent=2,
        )
        + "\n"
    )
    result = _run(["klt", "synthesize", str(req_path), "--pdk", pdk.variant, "--format", "json"])
    if result.returncode not in (0,):
        raise SynthError(
            f"klt synthesize ({cell_library}) exited {result.returncode}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SynthError(f"klt synthesize ({cell_library}) did not print JSON: {exc}\n{result.stdout}") from exc


def run_equiv(pdk: Pdk, cell_library: str, gate_netlist: Path, liberty: Path, req_path: Path) -> dict:
    """Invoke `klt equiv` (`"yosys-sequential"` engine) between the RTL and
    one synthesized netlist. Raises :class:`SynthError` only on a hard
    application error (exit 1/2) -- a `"counterexample"`/`"inconclusive"`
    verdict is returned to the caller as data (exit 3/4), not raised, so the
    caller can decide how to report a genuine non-equivalence rather than
    this function silently turning it into a crash.
    """
    req_path.write_text(
        json.dumps(
            {
                "gold": {"sources": [str(RTL_SOURCE)], "top": TOP},
                "gate": {"sources": [str(gate_netlist)], "top": TOP, "liberty": str(liberty)},
                "engine": "yosys-sequential",
                "timeout_s": 120,
            },
            indent=2,
        )
        + "\n"
    )
    result = _run(["klt", "equiv", str(req_path), "--format", "json"])
    if result.returncode not in (0, 3, 4):
        raise SynthError(
            f"klt equiv ({cell_library}) exited {result.returncode} (application error):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SynthError(f"klt equiv ({cell_library}) did not print JSON: {exc}\n{result.stdout}") from exc


def render_record(
    *,
    rid: str,
    when: _dt.datetime,
    cell_library: str,
    pdk: Pdk,
    liberty: Path,
    klt_v: str,
    yosys_v: str,
    synth_resp: dict,
    counts: dict[str, int],
    equiv_resp: dict,
    dirty: bool,
    netlist_rel: str,
    ys_rel: str,
    synth_req_rel: str,
    equiv_req_rel: str,
) -> str:
    lib_tag = _lib_tag(cell_library)
    total_cells = sum(counts.values())
    seq_cells = sum(n for t, n in counts.items() if "dff" in t or "lat" in t)
    comb_cells = total_cells - seq_cells
    breakdown = "\n".join(f"  - `{t}`: {n}" for t, n in sorted(counts.items()))
    structural = synth_resp.get("structural")
    structural_line = (
        f" `structural`: {json.dumps(structural)}."
        if structural is not None
        else " (this `klt` build's `synthesize` response carries no `structural` field --"
        " installed `klt --version` is below the issue #1588 baseline that field shipped in;"
        " this script's own `assert_fully_mapped` re-parse is the structural check that matters here.)"
    )
    sha = _git("rev-parse", "HEAD") or "unknown"
    equiv_status = equiv_resp.get("status", "unknown")
    equiv_line = {
        "equivalent": "**EQUIVALENT** -- `klt equiv` (`yosys-sequential` engine, register-correspondence) "
        f"proved this netlist's every state element and output functionally matches `sar_ctrl.v`'s "
        f"(`induction_depth={equiv_resp.get('induction_depth')}`, `elapsed_s={equiv_resp.get('elapsed_s')}`).",
        "counterexample": "**COUNTEREXAMPLE -- NOT EQUIVALENT.** `klt equiv` found, and independently "
        f"confirmed by simulation, a divergence between `sar_ctrl.v` and this netlist. "
        f"See `{equiv_req_rel}` / the raw response for the counterexample trace. THIS NETLIST IS SUSPECT.",
        "inconclusive": "**INCONCLUSIVE.** `klt equiv` could not prove or refute equivalence within its "
        f"timeout/induction bound. This is NOT a pass -- see `{equiv_req_rel}` / the raw response.",
    }.get(equiv_status, f"UNKNOWN STATUS {equiv_status!r} -- investigate before trusting this record.")
    return f"""\
# Record {rid} ({lib_tag})

- **Record ID**: {rid}.{lib_tag}
- **Claim**: A gate-level netlist for `sar_ctrl_a` exists, synthesized against the gf180mcu
  standard-cell library `{cell_library}` at the `{CORNER}` corner DR-0023
  (`spec/decision-records/DR-0023-digital-interface-device-flavor.md`) names for the block's
  digital partition, and is proven register-correspondence equivalent to `design/sar-logic/rtl/sar_ctrl.v`.
  DR-0023 follow-on (a) (issue #272). No SDC/STA claim is made here -- that is follow-on (c),
  a separate filed issue.
- **Scope**: Synthesis (technology mapping only, no timing target) + formal equivalence. No
  place-and-route, no STA/timing closure, no DRC/LVS of the digital region -- all explicitly
  deferred to follow-on issues (b)/(c) this issue's own PR files.
- **Tool versions**:
  - `klt`: `{klt_v}`
  - Yosys (via `klt synthesize`): `{synth_resp.get("engine_version")}`
  - Yosys (resolved on `$PATH`, `yosys -V`): `{yosys_v}`
  - gf180mcu PDK: variant `{pdk.variant}`, open_pdks `{pdk.version}` (via {pdk.source})
- **Standard-cell library**: `{liberty.relative_to(pdk.path)}` (`{cell_library}`, `{CORNER}` corner)
- **Synthesis constraints**: `klt synthesize` default recipe (`proc; opt; fsm; opt; memory; opt;
  techmap; opt; dfflibmap -liberty <lib>; abc -liberty <lib>[; -constr <driving-cell/load> when the
  library has a constraint-table entry]; opt_clean -purge; clean; stat -liberty <lib> -json; write_verilog`,
  `docs/cli/synthesize.md`), `constraints.clock_period_ns: null` (no ABC `-D` delay target --
  timing closure is out of scope for this issue). Exact request/response:
  `{synth_req_rel}` (request; `klt synthesize`'s own generated `.ys` script is `{ys_rel}`).
- **Result (synthesis)**: PASS -- {total_cells} cell instances ({seq_cells} sequential, {comb_cells}
  combinational), `area_um2` = {synth_resp.get("area_um2")}, `sequential_area_um2` = {synth_resp.get("sequential_area_um2")},
  0 unmapped cells (every instance is a `{cell_library}__*` standard cell; checked both by `klt synthesize`'s
  own `select -assert-none t:$_*` and by this script's independent re-parse of the written netlist --
  see `cell_types`/`assert_fully_mapped` in `design/sar-logic/flow/synth_sar_ctrl.py`).{structural_line} Cell
  breakdown:
{breakdown}
- **ABC pre-layout timing estimate** (informational only, NOT signoff, `docs/cli/synthesize.md`'s own
  caveats apply verbatim -- wire-free, combinational-cone-only): {json.dumps(synth_resp.get("timing")) if synth_resp.get("timing") is not None else "not reported (no ABC `-constr` entry for this library on the installed `klt`, or this `klt` build predates the `timing` field)"}
- **Result (equivalence)**: {equiv_line}
  Exact request/response: `{equiv_req_rel}`.
- **Reproducibility**: working tree {"DIRTY (uncommitted changes outside design/sar-logic/flow/sar_ctrl/ at run time -- re-run against a clean checkout before trusting this record)" if dirty else "clean"} at commit `{sha}`.
- **Links**:
  - RTL source: `design/sar-logic/rtl/sar_ctrl.v`
  - Netlist: `{netlist_rel}`
  - `klt synthesize` request: `{synth_req_rel}`
  - `klt synthesize`'s own Yosys script: `{ys_rel}`
  - `klt equiv` request: `{equiv_req_rel}`
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/flow/synth_sar_ctrl.py` (agent-run)
"""


def synthesize_one(pdk: Pdk, cell_library: str, rid: str, when: _dt.datetime, *, write_record: bool) -> dict:
    lib_tag = _lib_tag(cell_library)
    liberty = _liberty_path(pdk, cell_library, CORNER)

    NETLIST_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    synth_req_path = REPORTS_DIR / f"{rid}.{lib_tag}.synthesize_request.json"
    print(f"Synthesizing {TOP} against {cell_library} @ {CORNER} ...")
    synth_resp = run_synthesize(pdk, cell_library, synth_req_path)
    synth_resp_path = REPORTS_DIR / f"{rid}.{lib_tag}.synthesize_response.json"
    synth_resp_path.write_text(json.dumps(synth_resp, indent=2) + "\n")

    generated_netlist = Path(synth_resp["netlist_path"])
    generated_ys = Path(synth_resp["script_path"])
    netlist_path = NETLIST_DIR / f"sar_ctrl.{lib_tag}.synth.v"
    netlist_path.write_text(generated_netlist.read_text())
    ys_path = REPORTS_DIR / f"{rid}.{lib_tag}.synth.ys"
    ys_path.write_text(generated_ys.read_text())

    counts = cell_types(netlist_path)
    assert_fully_mapped(counts, f"{cell_library}__")
    total = sum(counts.values())
    print(f"  OK: {total} cell instances, 0 unmapped, area_um2={synth_resp.get('area_um2')}")

    equiv_req_path = REPORTS_DIR / f"{rid}.{lib_tag}.equiv_request.json"
    print(f"  Checking equivalence ({cell_library}) via klt equiv (yosys-sequential) ...")
    equiv_resp = run_equiv(pdk, cell_library, netlist_path, liberty, equiv_req_path)
    equiv_resp_path = REPORTS_DIR / f"{rid}.{lib_tag}.equiv_response.json"
    equiv_resp_path.write_text(json.dumps(equiv_resp, indent=2) + "\n")
    print(f"  equiv status: {equiv_resp.get('status')}")

    if write_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        record_path = RECORDS_DIR / f"{rid}.{lib_tag}.md"
        if record_path.exists():
            raise SynthError(f"record {record_path} already exists -- refusing to overwrite")
        record_path.write_text(
            render_record(
                rid=rid,
                when=when,
                cell_library=cell_library,
                pdk=pdk,
                liberty=liberty,
                klt_v=klt_version(),
                yosys_v=yosys_version(),
                synth_resp=synth_resp,
                counts=counts,
                equiv_resp=equiv_resp,
                dirty=working_tree_dirty(),
                netlist_rel=str(netlist_path.relative_to(REPO_ROOT)),
                ys_rel=str(ys_path.relative_to(REPO_ROOT)),
                synth_req_rel=str(synth_req_path.relative_to(REPO_ROOT)),
                equiv_req_rel=str(equiv_req_path.relative_to(REPO_ROOT)),
            )
        )
        print(f"  Evidence record written to {record_path}")

    return {
        "cell_library": cell_library,
        "counts": counts,
        "synth": synth_resp,
        "equiv": equiv_resp,
        "netlist_path": netlist_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        choices=[_lib_tag(l) for l in LIBRARIES] + ["both"],
        default="both",
        help="which library to synthesize (default: both)",
    )
    parser.add_argument("--no-record", action="store_true", help="skip minting evidence records")
    args = parser.parse_args()

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    libraries = LIBRARIES if args.library == "both" else [f"gf180mcu_fd_sc_{args.library}"]

    when = _dt.datetime.now(_dt.timezone.utc)
    rid = record_id(when)

    results = []
    try:
        for cell_library in libraries:
            results.append(
                synthesize_one(pdk, cell_library, rid, when, write_record=not args.no_record)
            )
    except SynthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    bad = [
        r["cell_library"]
        for r in results
        if r["equiv"].get("status") != "equivalent"
    ]
    if bad:
        print(f"ERROR: non-equivalent (or inconclusive) result for: {', '.join(bad)}", file=sys.stderr)
        return 1

    print("All libraries: fully mapped, proven equivalent to the RTL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
