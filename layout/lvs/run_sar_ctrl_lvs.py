#!/usr/bin/env python3
"""Reproducible `klt extract` + `klt lvs` of the standalone routed SAR
sequencer macro (`layout/adc-top/sar_ctrl/`) against its golden circuit, with
an append-only evidence record (issue #480).

What is compared
----------------
LAYOUT  `layout/adc-top/sar_ctrl/sar_ctrl.gds`, extracted TRANSISTOR-LEVEL
        (no `--abstract-cells`, so no cell is a black box and the std-cell
        internals are real extracted devices) with the `gf180mcu` deck,
        `--def-net-names` and `--def-pins layout/adc-top/sar_ctrl/sar_ctrl.def`
        (the macro's own routed DEF supplies the net names and the declared
        pin set). No `--pdk`: the unbound `M ... nfet/pfet` card form is what
        `klt lvs` compares (docs/cli/lvs.md, "Netlist form").

GOLDEN  the committed routed gate netlist `layout/adc-top/sar_ctrl/sar_ctrl.v`
        translated by `design/sar-logic/flow/gate_netlist_to_spice.py` into a
        flat `.subckt sar_ctrl_a`, whose cells are the VERBATIM PDK
        `gf180mcu_fd_sc_mcu7t5v0.spice` `.SUBCKT` definitions (transistor
        level), converted by `klt lvs` (`reference.form: "subckt-call"`,
        `reference.deck: "gf180mcu"`) and flattened on both sides.

Port / supply mapping (explicit; nothing is left to name guessing)
------------------------------------------------------------------
* `VDD`  : every cell's `VDD` and `VNW` pin.   `VSS` : every cell's `VSS`
  and `VPW` pin. Both are PORTS of the golden `.subckt` (not `.global`).
  The PDK declares the cell power pins `VDD VNW VPW VSS`; the pin order is
  read from the PDK spice text, never from the Verilog blackbox header.
* The 10 outputs `c0..c9` are `assign c<k> = c<k>_r;` in the routed
  Verilog and `drdy` is `assign drdy = ph[15];`. In the routed DEF the PIN
  `c<k>` is bound to NET `c<k>_r` (and `drdy` to NET `ph[15]`), and
  `klt extract --def-pins` names each pin by its NET. The golden therefore
  exposes those 11 ports under the layout's pin names (`c<k>_r`,
  `ph[15]`); `klt lvs` `options.anchor_top_level_pins` then requires every
  top-level pin name to agree on both sides.
* A real, open output pin in the routed netlist (the CTS dummy load
  `clkload*` buffers' `Z`) is given its own private golden net
  (`nc_<inst>_<pin>`), stated explicitly, not dropped.
* Physical-only cells (`filltie`, `endcap`, `fill_*`) have no logical
  content and are not in the routed Verilog; they carry no extracted devices
  and contribute only tap/well connectivity to the layout, which is exactly
  what the compare checks.

Runs (all in one record)
------------------------
1. `committed`  the real compare. Its verdict is recorded AS IT COMES OUT.
2. `diagnostic` the same compare after the layout netlist's five `VDD` pins
   are TEXTUALLY shorted into one (a hypothetical strap). This is NOT an LVS
   result and never a pass: it isolates whether the `committed` mismatch is
   explained by the VDD split alone.
3. `negctrl_wire` / `negctrl_width`  the DIAGNOSTIC pair with one deliberate
   golden defect (one input pin rewired to `clk`; one pfet width changed in
   one cell type). Each must be reported as a mismatch, otherwise the
   compare is not sensitive and every clean verdict here is void.

Usage
-----
    python3 layout/lvs/run_sar_ctrl_lvs.py           # run, mint a new record
    python3 layout/lvs/run_sar_ctrl_lvs.py --check   # run + assert, write nothing

Exit codes: 0 controls behaved (the `committed` verdict is recorded, not
asserted); 1 tooling problem; 2 a control or the diagnostic misbehaved.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO_ROOT, "layout"))
sys.path.insert(0, os.path.join(REPO_ROOT, "design", "sar-logic", "flow"))

import gate_netlist_to_spice as g  # noqa: E402
import klt_env  # noqa: E402

MACRO_DIR = "layout/adc-top/sar_ctrl"
GDS = f"{MACRO_DIR}/sar_ctrl.gds"
DEF = f"{MACRO_DIR}/sar_ctrl.def"
VERILOG = f"{MACRO_DIR}/sar_ctrl.v"
TRANSLATOR = "design/sar-logic/flow/gate_netlist_to_spice.py"
LIBRARY = "gf180mcu_fd_sc_mcu7t5v0"
TOP = "sar_ctrl_a"
OUT_DIR = os.path.join(HERE, "sar_ctrl")
REPORTS_DIR = os.path.join(OUT_DIR, "reports")
RECORDS_DIR = os.path.join(OUT_DIR, "records")

#: golden port -> layout pin name (see module docstring)
PORT_MAP = {**{f"c{k}": f"c{k}_r" for k in range(10)}, "drdy": "ph[15]"}

LVS_OPTIONS = {
    "flatten_reference": True,
    "flatten_layout": True,
    "anchor_top_level_pins": True,
}


def run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def build_golden(pdk_spice: str) -> tuple[str, dict]:
    """Return `(spice_text, facts)`: PDK cell subckts + flat `.subckt`."""
    lib_text = open(pdk_spice, encoding="utf-8").read()
    net = g.parse_gate_verilog(open(os.path.join(REPO_ROOT, VERILOG)).read(), expected_top=TOP)
    verilog_ports = list(net.ports)
    ports = [PORT_MAP.get(p, p) for p in verilog_ports] + ["VDD", "VSS"]
    insts = [
        dataclasses.replace(
            i, connections={k: PORT_MAP.get(v, v) for k, v in i.connections.items()}
        )
        for i in net.instances
    ]
    net2 = dataclasses.replace(net, ports=ports, instances=insts)
    sub = g.build_spice_subckt(
        net2,
        g.parse_spice_subckt_pins(lib_text),
        subckt_name=TOP,
        supply_net="VDD",
        ground_net="VSS",
        unconnected_signal_pins=True,
    )
    sub = sub.replace("ph_15", "ph[15]")  # sanitizer maps '[15]' -> '_15'
    used = g.extract_used_subckts(lib_text, {i.cell_type for i in net.instances})
    cell_counts: dict[str, int] = {}
    for i in net.instances:
        cell_counts[i.cell_type] = cell_counts.get(i.cell_type, 0) + 1
    facts = {
        "verilog_ports": len(verilog_ports),
        "golden_ports": len(ports),
        "instances": len(net.instances),
        "cell_counts": dict(sorted(cell_counts.items())),
        "open_output_pins": sorted(re.findall(r"nc_\S+", sub)),
        "port_map": PORT_MAP,
    }
    return used + "\n" + sub, facts


def wrong_wire(golden: str) -> tuple[str, str]:
    """Rewire the first input (`A1`) of the first nor2_1 instance to `clk`."""
    lines = golden.split("\n")
    for n, ln in enumerate(lines):
        if ln.startswith("X") and ln.endswith(f"{LIBRARY}__nor2_1"):
            t = ln.split()
            old = t[1]
            if old == "clk":
                continue
            t[1] = "clk"
            lines[n] = " ".join(t)
            return "\n".join(lines), f"{t[0]}: pin A1 net {old} -> clk"
    raise RuntimeError("no nor2_1 instance to perturb")


def wrong_width(golden: str) -> tuple[str, str]:
    """Narrow the first pfet of the PDK nor2_1 definition (1.22u -> 1.00u)."""
    out, k = re.subn(
        rf"(\.SUBCKT {LIBRARY}__nor2_1 [^\n]*\n(?:[^\n]*\n)*?X_i_3 net_0 A2 VDD VNW pfet_06v0 W=)1\.22e-06",
        r"\g<1>1.00e-06",
        golden,
        count=1,
    )
    if k != 1:
        raise RuntimeError("nor2_1 pfet X_i_3 not found")
    return out, "nor2_1 X_i_3 pfet W 1.22u -> 1.00u (43 instances)"


def short_vdd(spice: str) -> str:
    """Diagnostic only: merge the extracted `VDD$<n>` pins into `VDD`."""
    s = re.sub(r"VDD\$\d+", "VDD", spice)
    out = []
    for ln in s.split("\n"):
        if ln.startswith(".SUBCKT"):
            seen, toks = set(), []
            for tk in ln.split():
                if tk in seen and tk == "VDD":
                    continue
                seen.add(tk)
                toks.append(tk)
            ln = " ".join(toks)
        out.append(ln)
    return re.sub(r"^\* pin VDD\n(?:\* pin VDD\n)+", "* pin VDD\n", "\n".join(out), flags=re.M)


def lvs_request(layout: str, reference: str) -> dict:
    return {
        "layout": {"netlist": layout, "top": TOP},
        "reference": {
            "netlist": reference,
            "top": TOP,
            "form": "subckt-call",
            "deck": "gf180mcu",
        },
        "options": dict(LVS_OPTIONS),
    }


def run_lvs(klt: str, wd: str, name: str, layout: str, reference: str) -> dict:
    req = f"{name}.lvs_request.json"
    with open(os.path.join(wd, req), "w") as fh:
        json.dump(lvs_request(layout, reference), fh, indent=2)
        fh.write("\n")
    proc = run([klt, "lvs", req, "--format", "json"], wd)
    if proc.returncode not in (0, 3):
        raise klt_env.ToolingError(f"klt lvs {name} failed ({proc.returncode}): {proc.stderr.strip()}")
    with open(os.path.join(wd, f"{name}.lvs.json"), "w") as fh:
        fh.write(proc.stdout)
    rep = json.loads(proc.stdout)
    rep["_exit"] = proc.returncode
    return rep


def summarize(rep: dict) -> dict:
    return {
        "status": rep["status"],
        "mismatch_count": rep["mismatch_count"],
        "category_counts": rep["category_counts"],
        "counts": rep["counts"],
    }


def execute(wd: str) -> dict:
    klt = klt_env.find_klt()
    pin = klt_env.load_manifest(os.path.join(REPO_ROOT, "layout", "toolchain.json"))
    klt_env.check_klt_capabilities(klt, pin)
    pdk = klt_env.resolve_pdk(klt)
    pdk_spice = os.path.join(pdk["assets"]["libs_ref"], LIBRARY, "spice", f"{LIBRARY}.spice")
    if not os.path.isfile(pdk_spice):
        raise klt_env.ToolingError(f"PDK std-cell spice not found: {LIBRARY}")

    golden, facts = build_golden(pdk_spice)
    open(os.path.join(wd, "sar_ctrl.golden.spice"), "w").write(golden)

    rel = os.path.relpath(REPO_ROOT, wd)
    ext = run(
        [klt, "extract", os.path.join(rel, GDS), "--deck", "gf180mcu", "--def-net-names",
         "--def-pins", os.path.join(rel, DEF), "-o", "sar_ctrl.extract.spice", "--format", "json"],
        wd,
    )
    if ext.returncode != 0:
        raise klt_env.ToolingError(f"klt extract failed: {ext.stderr.strip()}")
    open(os.path.join(wd, "sar_ctrl.extract.json"), "w").write(ext.stdout)
    extract = json.loads(ext.stdout)
    layout_spice = open(os.path.join(wd, "sar_ctrl.extract.spice")).read()
    open(os.path.join(wd, "sar_ctrl.extract.vddshorted.spice"), "w").write(short_vdd(layout_spice))

    res = {"klt": klt, "pdk": pdk, "pdk_spice": pdk_spice, "golden_facts": facts, "extract": extract}
    res["committed"] = run_lvs(klt, wd, "committed", "sar_ctrl.extract.spice", "sar_ctrl.golden.spice")
    res["diagnostic"] = run_lvs(
        klt, wd, "diagnostic", "sar_ctrl.extract.vddshorted.spice", "sar_ctrl.golden.spice"
    )
    w, w_desc = wrong_wire(golden)
    open(os.path.join(wd, "sar_ctrl.golden.wrongwire.spice"), "w").write(w)
    res["negctrl_wire"] = run_lvs(
        klt, wd, "negctrl_wire", "sar_ctrl.extract.vddshorted.spice", "sar_ctrl.golden.wrongwire.spice"
    )
    res["negctrl_wire_desc"] = w_desc
    ww, ww_desc = wrong_width(golden)
    open(os.path.join(wd, "sar_ctrl.golden.wrongwidth.spice"), "w").write(ww)
    res["negctrl_width"] = run_lvs(
        klt, wd, "negctrl_width", "sar_ctrl.extract.vddshorted.spice", "sar_ctrl.golden.wrongwidth.spice"
    )
    res["negctrl_width_desc"] = ww_desc
    return res


def assertions(res: dict) -> list[str]:
    bad = []
    if res["diagnostic"]["status"] != "match":
        bad.append(f"diagnostic (VDD-shorted layout) expected match, got {res['diagnostic']['status']}")
    for k in ("negctrl_wire", "negctrl_width"):
        if res[k]["status"] != "mismatch" or res[k]["mismatch_count"] < 1:
            bad.append(f"{k}: injected golden defect NOT detected ({res[k]['status']})")
    return bad


def unmatched_summary(rep: dict, limit: int = 12) -> list[str]:
    out = []
    for m in rep["mismatches"]:
        if m.get("severity") == "warning":
            continue
        d = m.get("device") or {}
        n = m.get("net") or {}
        out.append(f"{m['category']}: {d or n or m['description']}")
    return out[:limit]


def sha(path: str) -> str:
    return klt_env.sha256(os.path.join(REPO_ROOT, path))


def write_record(res: dict, rec_id: str, wd: str, dirty: bool) -> str:
    ident = klt_env.klt_identity(res["klt"])
    ex, c, d = res["extract"], res["committed"], res["diagnostic"]
    f = res["golden_facts"]
    pdk_spice_sha = klt_env.sha256(res["pdk_spice"])
    sha_head = klt_env.git(REPO_ROOT, "rev-parse", "HEAD")
    vdd_nets = [n for n in ex["nets"] if n["name"] == "VDD" and n.get("pin")]
    L = []
    L.append(f"# Record {rec_id} -- standalone routed `sar_ctrl` macro, transistor-level LVS vs golden\n")
    L.append("- **Verdict (committed GDS vs golden)**: "
             f"**`{c['status']}`** -- {c['mismatch_count']} mismatches "
             f"`{json.dumps(c['category_counts'])}`. This is **NOT an LVS pass** and is NOT signoff "
             "evidence (see \"What this does and does not establish\").")
    L.append(f"- **Repo commit**: `{sha_head}`{' (working tree had uncommitted changes)' if dirty else ''}")
    L.append(f"- **Runner**: `python3 layout/lvs/run_sar_ctrl_lvs.py`")
    L.append(f"- **klt**: `{ident.get('klt_version', ident)}` (`klt version`: {json.dumps(ident, sort_keys=True)})")
    L.append(f"- **KLayout**: `{c['environment']['engine_version']}`; engine `{c['engine']}`")
    L.append(f"- **PDK**: `{res['pdk']['variant']}`, {res['pdk']['version']}; deck `gf180mcu` "
             f"(`{ex['provenance']['deck']['content_hash']}`)")
    L.append("\n## Input hashes (sha256)\n")
    for label, p in (("layout GDS", GDS), ("routed DEF (pins/net names)", DEF),
                     ("routed gate netlist (golden source)", VERILOG), ("translator", TRANSLATOR)):
        L.append(f"- {label}: `{p}` `{sha(p)}`")
    L.append(f"- PDK std-cell circuits: `libs.ref/{LIBRARY}/spice/{LIBRARY}.spice` `{pdk_spice_sha}`")
    for n in ("sar_ctrl.extract.spice", "sar_ctrl.golden.spice"):
        L.append(f"- generated `{n}`: `{klt_env.sha256(os.path.join(wd, n))}`")
    L.append("\n## Device and net counts\n")
    L.append(f"- Extracted layout: {ex['device_count']} devices `{json.dumps(ex['device_counts'])}`, "
             f"{ex['net_count']} nets, {ex['pin_count']} pins.")
    cc = c["counts"]
    L.append(f"- Compare counts (committed): devices layout {cc['devices']['layout']} / reference "
             f"{cc['devices']['reference']} / matched {cc['devices']['matched']}; nets layout "
             f"{cc['nets']['layout']} / reference {cc['nets']['reference']} / matched {cc['nets']['matched']}; "
             f"pins layout {cc['pins']['layout']} / reference {cc['pins']['reference']} / matched "
             f"{cc['pins']['matched']}.")
    L.append(f"- Golden: {f['instances']} cell instances, {f['golden_ports']} ports "
             f"({f['verilog_ports']} Verilog ports + VDD + VSS): `{json.dumps(f['cell_counts'])}`.")
    L.append(f"- Layout `VDD` pins (disconnected nets carrying the `VDD` label): {len(vdd_nets)} "
             f"(devices on each: {[n['device_count'] for n in vdd_nets]}); golden has 1 `VDD` net.")
    L.append("\n## Port and supply mapping\n")
    L.append("- `VDD`/`VNW` -> golden `VDD`; `VSS`/`VPW` -> golden `VSS`; both golden ports; "
             "no `.global`, no black boxes (every std cell is its verbatim PDK transistor-level `.SUBCKT`).")
    L.append("- Golden ports renamed to the layout pin names (DEF PIN -> NET): "
             + ", ".join(f"`{k}`->`{v}`" for k, v in PORT_MAP.items()) + ".")
    L.append(f"- Open output pins given private nets: {f['open_output_pins']}.")
    L.append("- `options`: " + json.dumps(LVS_OPTIONS) + "; parameters compared are the klayout "
             "MOS defaults (W, L); AS/AD/PS/PD are not compared.")
    L.append("\n## Mismatches in the committed compare (first 12 of "
             f"{c['mismatch_count']}; full list in `committed.lvs.json`)\n")
    for s in unmatched_summary(c):
        L.append(f"- {s}")
    L.append("\n## Diagnostic (NOT an LVS result): committed layout with its VDD pins shorted\n")
    L.append(f"- The extracted layout netlist's {len(vdd_nets)} `VDD` pins are textually merged into one and "
             f"re-compared: `{d['status']}`, {d['mismatch_count']} entries, all severity warning "
             f"`{json.dumps(d['category_counts'])}`; devices {d['counts']['devices']}, nets "
             f"{d['counts']['nets']}, pins {d['counts']['pins']}.")
    L.append("- Reading: with that single connection added by hand, every one of the "
             f"{d['counts']['devices']['reference']} devices and {d['counts']['nets']['reference']} nets "
             "matches. The committed-GDS mismatch is therefore attributable to the VDD split "
             "(a cascade of `net.merged`/`net.split`/`device.unmatched` around it), not to a signal "
             "wiring or device difference. That is an inference from a hand-edited netlist, not a "
             "property of the GDS.")
    L.append("- Cause (from the committed P&R inputs): `design/sar-logic/flow/pnr_sar_ctrl.py` requests "
             "Metal1 `followpins` power only (see the P&R record), and the routed DEF `SPECIALNETS` "
             "holds five disjoint VDD rail segments and no vertical strap. The DEF has six VSS rail segments, yet "
             "extraction reports a single VSS pin (the substrate joins them); the VDD rails have no such path.")
    L.append("\n## Detection of intentional golden errors (run on the diagnostic pair)\n")
    for k, desc in (("negctrl_wire", res["negctrl_wire_desc"]), ("negctrl_width", res["negctrl_width_desc"])):
        r = res[k]
        L.append(f"- `{k}` ({desc}): `{r['status']}`, {r['mismatch_count']} mismatches "
                 f"`{json.dumps(r['category_counts'])}` -- detected: {r['status'] == 'mismatch'}.")
    L.append("\n## What this does and does not establish\n")
    L.append("- Established: `klt extract` + `klt lvs` at the pinned build can extract this macro and "
             "compare it transistor-level against a golden built from the routed netlist and the PDK "
             "circuits, and the compare detects a rewired pin and a changed device width.")
    L.append(f"- NOT established: LVS clean. The committed GDS is `{c['status']}` against its golden. "
             "No LVS citation is added to `signoff/gf180-sar-adc.manifest.json`; item 4.digital / "
             "11.digital stay uncited. The analog block's LVS is not substituted.")
    L.append("- The comparison is topological plus W/L; it does not check LVS of fill/tap physical-only "
             "cells beyond their extracted well/substrate connectivity, nor rail continuity/IR.")
    L.append("\n## Artifacts\n")
    L.append(f"`layout/lvs/sar_ctrl/reports/{rec_id}/`: extract (`.extract.json/.spice`), golden "
             "(`.golden*.spice`), requests (`*.lvs_request.json`) and reports (`*.lvs.json`) for "
             "`committed`, `diagnostic`, `negctrl_wire`, `negctrl_width`. Re-verify inputs/verdict with "
             f"`cd layout/lvs/sar_ctrl/reports/{rec_id} && klt lvs --check committed.lvs.json` (relative paths "
             "resolve against the current directory).")
    path = os.path.join(RECORDS_DIR, f"{rec_id}.md")
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="run and assert; write nothing")
    args = ap.parse_args()
    try:
        if args.check:
            with tempfile.TemporaryDirectory() as td:
                res = execute(td)
                for k in ("committed", "diagnostic", "negctrl_wire", "negctrl_width"):
                    print(k, json.dumps(summarize(res[k])))
                bad = assertions(res)
        else:
            rec_id = klt_env.record_id(REPO_ROOT)
            wd = klt_env.reserve_record_slot(rec_id, REPORTS_DIR, RECORDS_DIR)
            dirty = bool(klt_env.git(REPO_ROOT, "status", "--porcelain"))
            res = execute(wd)
            bad = assertions(res)
            path = write_record(res, rec_id, wd, dirty)
            print(f"wrote {os.path.relpath(path, REPO_ROOT)}")
            for k in ("committed", "diagnostic", "negctrl_wire", "negctrl_width"):
                print(k, json.dumps(summarize(res[k])))
    except klt_env.ToolingError as exc:
        print(f"tooling error: {exc}", file=sys.stderr)
        return klt_env.EXIT_TOOLING
    for b in bad:
        print(f"ASSERTION FAILED: {b}", file=sys.stderr)
    return klt_env.EXIT_MISMATCH if bad else klt_env.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
