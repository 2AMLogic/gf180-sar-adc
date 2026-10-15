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
1. `committed`  the real compare of the committed GDS. Its verdict is recorded
   AS IT COMES OUT and is asserted to be a match (issue #485 repaired the
   supply connectivity with Metal4 straps).
2. `gatelevel`  COMPLEMENTARY, signal-only: the macro extracted with
   `--abstract-cells` against `sar_ctrl.v` (`reference.form:
   "gate-level-verilog"`). Its top-level `status` is the signal-connectivity
   verdict only; the supply verdict is the separate `power_connectivity`
   block, recorded as such. Black-box cells: it does not replace run 1.
3. `negctrl_supply`  the same two compares on a copy of the committed GDS
   with the Metal4 supply straps deleted (geometry edit, not a netlist edit).
   Both must report the missing supply connectivity, otherwise the compare is
   not sensitive to supply continuity and a clean `committed` verdict is void.
4. `negctrl_wire` / `negctrl_width`  the DIAGNOSTIC pair with one deliberate
   golden defect (one input pin rewired to `clk`; one pfet width changed in
   one cell type). Each must be reported as a mismatch, otherwise the
   compare is not sensitive and every clean verdict here is void.

Usage
-----
    python3 layout/lvs/run_sar_ctrl_lvs.py           # run, mint a new record
    python3 layout/lvs/run_sar_ctrl_lvs.py --check   # run + assert, write nothing

Exit codes: 0 `committed` matched and the controls behaved; 1 tooling problem;
2 `committed` did not match or a control misbehaved.
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

#: GDS layer/datatype of Metal4 (gf180mcu)
METAL4 = (46, 0)

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


def strip_supply_straps(gds_in: str, gds_out: str) -> dict:
    """Negative control: write `gds_in` to `gds_out` minus the Metal4 supply
    straps (merged Metal4 shapes spanning the whole macro height). Geometry
    edit only -- the straps' vias are left in place, dangling."""
    import klayout.db as kdb

    ly = kdb.Layout()
    ly.read(gds_in)
    top = ly.top_cell()
    li = ly.layer(*METAL4)
    shapes = top.shapes(li)
    thresh = int(top.bbox().height() * 0.9)
    tall = [sh for sh in shapes.each() if sh.bbox().height() >= thresh]
    if not tall:
        raise klt_env.ToolingError("no full-height Metal4 straps found in the top cell to strip")
    boxes = [sh.bbox() for sh in tall]
    for sh in tall:
        shapes.erase(sh)
    ly.write(gds_out)
    return {"removed": len(boxes), "x_um": sorted(round(b.center().x * ly.dbu, 3) for b in boxes)}


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


def _scrub(text: str, pdk: dict) -> str:
    """Replace the host PDK install root with `<PDK_ROOT>` (a descriptive
    path klt echoes; the hash of the file it names is in the record)."""
    return text.replace(pdk["root"], "<PDK_ROOT>")


def summarize(rep: dict) -> dict:
    pc = rep.get("power_connectivity") or {}
    return {
        "power_connectivity": pc.get("status"),
        "status": rep["status"],
        "mismatch_count": rep["mismatch_count"],
        "category_counts": rep["category_counts"],
        "counts": rep["counts"],
    }


def gatelevel_compare(klt: str, pdk: dict, wd: str, rel: str, name: str, gds: str) -> dict:
    """`--abstract-cells` extract of `gds` and signal/`power_connectivity`
    compare against the routed gate-level Verilog."""
    ex_spice = f"{name}.extract.spice"
    gx = run(
        [klt, "extract", gds, "--deck", "gf180mcu", "--pdk", klt_env.PDK_VARIANT,
         "--abstract-cells", f"{LIBRARY}__*", "--def-net-names", "--def-pins",
         os.path.join(rel, DEF), "-o", ex_spice, "--format", "json"],
        wd,
    )
    if gx.returncode != 0:
        raise klt_env.ToolingError(f"klt extract --abstract-cells ({name}) failed: {gx.stderr.strip()}")
    open(os.path.join(wd, f"{name}.extract.json"), "w").write(_scrub(gx.stdout, pdk))
    greq = {
        "layout": {"netlist": ex_spice, "top": TOP},
        "reference": {"netlist": os.path.join(rel, VERILOG), "top": TOP, "form": "gate-level-verilog",
                      "library": LIBRARY, "pdk": klt_env.PDK_VARIANT},
    }
    with open(os.path.join(wd, f"{name}.lvs_request.json"), "w") as fh:
        json.dump(greq, fh, indent=2)
        fh.write("\n")
    gp = run([klt, "lvs", f"{name}.lvs_request.json", "--format", "json"], wd)
    if gp.returncode not in (0, 3):
        raise klt_env.ToolingError(f"klt lvs {name} failed ({gp.returncode}): {gp.stderr.strip()}")
    open(os.path.join(wd, f"{name}.lvs.json"), "w").write(_scrub(gp.stdout, pdk))
    return json.loads(gp.stdout)


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

    res = {"klt": klt, "pdk": pdk, "pdk_spice": pdk_spice, "golden_facts": facts, "extract": extract}
    res["committed"] = run_lvs(klt, wd, "committed", "sar_ctrl.extract.spice", "sar_ctrl.golden.spice")
    res["gatelevel"] = gatelevel_compare(klt, pdk, wd, rel, "gatelevel", os.path.join(rel, GDS))

    stripped = os.path.join(wd, "sar_ctrl.nosupplystrap.gds")
    res["negctrl_supply_desc"] = strip_supply_straps(os.path.join(REPO_ROOT, GDS), stripped)
    sx = run(
        [klt, "extract", "sar_ctrl.nosupplystrap.gds", "--deck", "gf180mcu", "--def-net-names",
         "--def-pins", os.path.join(rel, DEF), "-o", "sar_ctrl.nosupplystrap.extract.spice",
         "--format", "json"],
        wd,
    )
    if sx.returncode != 0:
        raise klt_env.ToolingError(f"klt extract (no-strap control) failed: {sx.stderr.strip()}")
    open(os.path.join(wd, "sar_ctrl.nosupplystrap.extract.json"), "w").write(sx.stdout)
    res["negctrl_supply"] = run_lvs(
        klt, wd, "negctrl_supply", "sar_ctrl.nosupplystrap.extract.spice", "sar_ctrl.golden.spice"
    )
    res["negctrl_supply_extract"] = json.loads(sx.stdout)
    res["negctrl_supply_gatelevel"] = gatelevel_compare(
        klt, pdk, wd, rel, "negctrl_supply_gatelevel", "sar_ctrl.nosupplystrap.gds")
    w, w_desc = wrong_wire(golden)
    open(os.path.join(wd, "sar_ctrl.golden.wrongwire.spice"), "w").write(w)
    res["negctrl_wire"] = run_lvs(
        klt, wd, "negctrl_wire", "sar_ctrl.extract.spice", "sar_ctrl.golden.wrongwire.spice"
    )
    res["negctrl_wire_desc"] = w_desc
    ww, ww_desc = wrong_width(golden)
    open(os.path.join(wd, "sar_ctrl.golden.wrongwidth.spice"), "w").write(ww)
    res["negctrl_width"] = run_lvs(
        klt, wd, "negctrl_width", "sar_ctrl.extract.spice", "sar_ctrl.golden.wrongwidth.spice"
    )
    res["negctrl_width_desc"] = ww_desc
    return res


def assertions(res: dict) -> list[str]:
    bad = []
    c = res["committed"]
    if c["status"] != "match":
        bad.append(f"committed GDS expected match against its golden, got {c['status']}")
    gp = res["gatelevel"]["power_connectivity"]
    if gp["status"] != "match":
        bad.append(f"gatelevel power_connectivity on the committed GDS expected match, got {gp['status']}")
    ns = res["negctrl_supply"]
    if ns["status"] != "mismatch" or ns["mismatch_count"] < 1:
        bad.append(f"negctrl_supply: deleted supply straps NOT detected by the transistor-level compare ({ns['status']})")
    ng = res["negctrl_supply_gatelevel"]
    if ng["power_connectivity"]["status"] != "mismatch":
        bad.append("negctrl_supply: deleted supply straps NOT reported by gate-level power_connectivity "
                   f"({ng['power_connectivity']['status']})")
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
    ex, c = res["extract"], res["committed"]
    f = res["golden_facts"]
    pdk_spice_sha = klt_env.sha256(res["pdk_spice"])
    sha_head = klt_env.git(REPO_ROOT, "rev-parse", "HEAD")
    vdd_nets = [n for n in ex["nets"] if n["name"] == "VDD" and n.get("pin")]
    vss_nets = [n for n in ex["nets"] if n["name"] == "VSS" and n.get("pin")]
    L = []
    L.append(f"# Record {rec_id} -- standalone routed `sar_ctrl` macro, transistor-level LVS vs golden\n")
    L.append("- **Verdict (committed GDS vs golden)**: "
             f"**`{c['status']}`** -- {c['mismatch_count']} entries "
             f"`{json.dumps(c['category_counts'])}` (all severity warning when `match`). Transistor-level "
             "compare of the actual GDS, no netlist edits. Signoff status: see \"What this does and does "
             "not establish\".")
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
    L.append(f"- Layout `VDD` pin nets: {len(vdd_nets)} (devices on each: {[n['device_count'] for n in vdd_nets]}); "
             f"`VSS` pin nets: {len(vss_nets)} (devices: {[n['device_count'] for n in vss_nets]}); golden has 1 of each.")
    L.append("\n## Port and supply mapping\n")
    L.append("- `VDD`/`VNW` -> golden `VDD`; `VSS`/`VPW` -> golden `VSS`; both golden ports; "
             "no `.global`, no black boxes (every std cell is its verbatim PDK transistor-level `.SUBCKT`).")
    L.append("- Golden ports renamed to the layout pin names (DEF PIN -> NET): "
             + ", ".join(f"`{k}`->`{v}`" for k, v in PORT_MAP.items()) + ".")
    L.append(f"- Open output pins given private nets: {f['open_output_pins']}.")
    L.append("- `options`: " + json.dumps(LVS_OPTIONS) + "; parameters compared are the klayout "
             "MOS defaults (W, L); AS/AD/PS/PD are not compared.")
    L.append("\n## Non-warning entries in the committed compare (first 12; full list in `committed.lvs.json`)\n")
    um = unmatched_summary(c)
    for s_ in um:
        L.append(f"- {s_}")
    if not um:
        L.append("- none")
    gl = res["gatelevel"]
    pc = gl["power_connectivity"]
    L.append("\n## Complementary signal-only gate-level compare (`--abstract-cells`, black-box cells)\n")
    L.append(f"- Top-level `status`: `{gl['status']}` (signal connectivity only; "
             f"`{json.dumps(gl['category_counts'])}`). **Separate** `power_connectivity.status`: "
             f"`{pc['status']}` with {pc.get('finding_count', len(pc.get('findings', [])))} finding(s) "
             "(both `VDD` and `VSS` are single-net across all instances). The top-level `status` alone is "
             "never the supply verdict (docs/cli/lvs.md: `power_connectivity` is independent). Host PDK "
             "root is replaced by `<PDK_ROOT>` in the stored JSON.")
    L.append("- Tool friction filed generically: 2AMLogic/klayout-tools#2972 (`klt lvs` accepts a "
             "`--pdk`-bound X-card layout netlist and silently counts zero layout devices; this runner "
             "extracts without `--pdk` for the transistor-level compare).")
    ns, nd = res["negctrl_supply"], res["negctrl_supply_desc"]
    ng = res["negctrl_supply_gatelevel"]
    nx = res["negctrl_supply_extract"]
    nv = [n["device_count"] for n in nx["nets"] if n["name"] == "VDD" and n.get("pin")]
    nsv = [n["device_count"] for n in nx["nets"] if n["name"] == "VSS" and n.get("pin")]
    L.append("\n## Negative control: missing supply connection (geometry edit)\n")
    L.append(f"- The committed GDS is rewritten with the {nd['removed']} full-height Metal4 supply straps "
             f"(x = {nd['x_um']} um) deleted from the top cell (their vias stay, dangling), then extracted "
             "and compared exactly as `committed`.")
    L.append(f"- Transistor-level: `{ns['status']}`, {ns['mismatch_count']} entries "
             f"`{json.dumps(ns['category_counts'])}`; the extraction has {len(nv)} `VDD` pin nets "
             f"(devices {nv}) and {len(nsv)} `VSS` pin nets (devices {nsv}) -- detected: "
             f"{ns['status'] == 'mismatch'}.")
    ngp = ng["power_connectivity"]
    L.append(f"- Gate-level (`--abstract-cells`): top-level `{ng['status']}`, `power_connectivity` "
             f"`{ngp['status']}` with {ngp.get('finding_count', len(ngp.get('findings', [])))} finding(s)"
             + "".join(f" (`{fd['rule']}`: {fd['description'][:140]}...)" for fd in ngp.get("findings", [])[:2])
             + f" -- detected: {ngp['status'] == 'mismatch'}.")
    L.append("- Unresolved VSS observation, kept explicit: before the repair the committed GDS had six "
             "`VSS` rail segments that the gate-level mode counted as 6 nets while the transistor-level "
             "mode reported one `VSS` pin net (the substrate joined them); that discrepancy is filed as "
             "2AMLogic/klayout-tools#2971. With the repaired GDS both modes agree on one `VSS` net, so this "
             "GDS no longer exercises the discrepancy. This record does not establish whether the "
             "transistor-level single `VSS` net is carried by metal or by substrate; the no-strap control "
             "above reports its `VSS` pin-net count for reference.")
    L.append("\n## Detection of intentional golden errors\n")
    for k, desc in (("negctrl_wire", res["negctrl_wire_desc"]), ("negctrl_width", res["negctrl_width_desc"])):
        r = res[k]
        L.append(f"- `{k}` ({desc}): `{r['status']}`, {r['mismatch_count']} mismatches "
                 f"`{json.dumps(r['category_counts'])}` -- detected: {r['status'] == 'mismatch'}.")
    L.append("\n## What this does and does not establish\n")
    L.append("- Established: `klt extract` + `klt lvs` at the pinned build can extract this macro and "
             "compare it transistor-level against a golden built from the routed netlist and the PDK "
             "circuits, and the compare detects a rewired pin and a changed device width.")
    L.append("- Established: the committed GDS is `" + c["status"] + "` against its transistor-level golden "
             "(" + str(cc["devices"]["matched"]) + " devices, " + str(cc["nets"]["matched"]) + " nets) with "
             "one `VDD` and one `VSS` pin net, and deleting the Metal4 straps from the same GDS is detected.")
    L.append("- NOT established: signoff LVS. This is a standalone-macro compare against a golden derived "
             "from the macro's own routed netlist; no LVS citation is added to "
             "`signoff/gf180-sar-adc.manifest.json` (item 4.digital / 11.digital stay uncited), and the "
             "analog block's LVS is not substituted.")
    L.append("- Stale downstream evidence: the STA / SPEF records under "
             "`design/sar-logic/flow/sar_ctrl/records/` describe the PRE-repair geometry. Re-timing the "
             "regenerated DEF/GDS is separate work.")
    L.append("- The comparison is topological plus W/L; it does not check LVS of fill/tap physical-only "
             "cells beyond their extracted well/substrate connectivity, nor rail continuity/IR.")
    L.append("\n## Artifacts\n")
    L.append(f"`layout/lvs/sar_ctrl/reports/{rec_id}/`: extract (`.extract.json/.spice`), golden "
             "(`.golden*.spice`), requests (`*.lvs_request.json`) and reports (`*.lvs.json`) for "
             "`committed`, `gatelevel`, `negctrl_supply`, `negctrl_supply_gatelevel`, `negctrl_wire`, `negctrl_width`. Re-verify inputs/verdict with "
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
                for k in ("committed", "gatelevel", "negctrl_supply", "negctrl_supply_gatelevel", "negctrl_wire", "negctrl_width"):
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
            for k in ("committed", "gatelevel", "negctrl_supply", "negctrl_supply_gatelevel", "negctrl_wire", "negctrl_width"):
                print(k, json.dumps(summarize(res[k])))
    except klt_env.ToolingError as exc:
        print(f"tooling error: {exc}", file=sys.stderr)
        return klt_env.EXIT_TOOLING
    for b in bad:
        print(f"ASSERTION FAILED: {b}", file=sys.stderr)
    return klt_env.EXIT_MISMATCH if bad else klt_env.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
