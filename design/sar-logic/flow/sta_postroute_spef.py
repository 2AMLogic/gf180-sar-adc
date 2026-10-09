"""`sta_sar_ctrl_postroute.py --spef`: extracted-SPEF, five-corner STA of the
committed routed `sar_ctrl_a` macro, with an annotation gate and negative
controls (issue #481). See that driver's module docstring, "Extracted-SPEF
mode", for the contract. This module holds the orchestration; the pure
parsing/audit/gate logic is in `spef_audit.py` (unit-tested without tools).

Import-only: nothing runs at import time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import spef_audit as audit
import sta_sar_ctrl_postroute as base
import synth_sar_ctrl as synth
from flow_env import git, klt_version

REPO_ROOT = base.REPO_ROOT
REPORTS_DIR = base.REPORTS_DIR
RECORDS_DIR = base.RECORDS_DIR
LIB_TAG = base.LIB_TAG
ROUTED_DEF = base.ROUTED_DEF
ROUTED_GDS = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.gds"
ROUTED_V = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.v"

#: Scratch for the derived negative-control SPEFs and the extraction's SPICE
#: side output. `design/sar-logic/flow/**/.klt/` is gitignored, and it sits
#: under the request directory, which the `openroad` Docker wrapper mounts.
SCRATCH = REPORTS_DIR / ".klt" / "spef_481"

#: The committed estimated-RC/ideal-clock baseline this run is compared to.
BASELINE_RID = "20260915-093934-7ab8971"

#: The negative-control net. In the routed DEF, `_010_` is `( _219_ D ) (
#: _171_ Z )`: a flop D pin, i.e. a timed setup/hold endpoint, and it is fully
#: annotated in the real SPEF. `_check_negctl_net` asserts both properties
#: rather than trusting this comment.
NEGCTL_NET = "_010_"
NEGCTL_CORNER = "tt_025C_3v30"

#: `klt extract` flags this mode depends on. Checked against `klt extract
#: --help` first, so an install without them fails loudly up front.
REQUIRED_EXTRACT_FLAGS = ("--parasitics", "--spef", "--def-net-names", "--def-net-connections", "--def-pins")

#: Lists in the `klt extract` response longer than this are replaced by their
#: length in the committed copy (`devices`/`nets` are ~4 MB). The extraction
#: is deterministic and re-runnable, and the SPEF itself is committed in full.
TRIM_LIST_OVER = 200


class SpefModeError(RuntimeError):
    pass


def _env(pdk) -> dict:
    env = dict(os.environ)
    env["PDK_ROOT"] = str(pdk.path.parent)
    env["PDK"] = pdk.variant
    return env


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def check_capabilities() -> list[str]:
    """Missing capabilities, as human-readable strings (empty == all present)."""
    missing = []
    top = subprocess.run(["klt", "--help"], capture_output=True, text=True, check=False)
    for verb in ("extract", "sta"):
        if verb not in (top.stdout + top.stderr):
            missing.append(f"klt verb `{verb}`")
    ext = subprocess.run(["klt", "extract", "--help"], capture_output=True, text=True, check=False)
    for flag in REQUIRED_EXTRACT_FLAGS:
        if flag not in ext.stdout:
            missing.append(f"klt extract {flag}")
    return missing


def liberty_path(pdk, corner: str) -> Path:
    return pdk.path / "libs.ref" / base.CELL_LIBRARY / "lib" / f"{base.CELL_LIBRARY}__{corner}.lib"


def extract_argv(spef: Path, netlist: Path, *, def_pins: bool) -> list[str]:
    argv = [
        "klt", "extract", _rel(ROUTED_GDS),
        "--deck", "gf180mcu", "--top", base.TOP,
        "--parasitics", "--spef", _rel(spef),
        "--def-net-names", "--def-net-connections", _rel(ROUTED_DEF),
    ]
    if def_pins:
        argv += ["--def-pins", _rel(ROUTED_DEF)]
    return argv + ["-o", _rel(netlist), "--format", "json"]


def run_extract(pdk, argv: list[str]) -> dict:
    result = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True, env=_env(pdk), check=False)
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SpefModeError(f"klt extract printed no JSON (exit {result.returncode}): {result.stderr[-2000:]}") from exc
    if "error" in resp or result.returncode != 0:
        raise SpefModeError(f"klt extract failed (exit {result.returncode}): {resp.get('error')}")
    for w in resp.get("warnings") or []:
        if "found no DEF net-name" in w:
            raise SpefModeError(f"klt extract --def-net-names recovered no DEF net names: {w}")
    promo = resp.get("def_pin_promotion")
    if promo is not None and promo.get("unmatched"):
        raise SpefModeError(f"--def-pins: DEF PINS with no extracted net: {promo['unmatched']}")
    return resp


def trim(obj, path: str = "", trimmed: dict | None = None):
    """Copy of `obj` with long lists replaced by their length; `trimmed`
    collects `{json_path: original_length}`."""
    if isinstance(obj, dict):
        return {k: trim(v, f"{path}.{k}" if path else k, trimmed) for k, v in obj.items()}
    if isinstance(obj, list) and len(obj) > TRIM_LIST_OVER:
        if trimmed is not None:
            trimmed[path] = len(obj)
        return f"<trimmed: {len(obj)} entries>"
    if isinstance(obj, list):
        return [trim(v, path, trimmed) for v in obj]
    return obj


def build_request(corner: str, spef: Path | None) -> dict:
    """Same request as the baseline mode, but with paths relative to the
    request file's own directory (`docs/cli/sta.md`), so the committed JSON
    re-runs from any checkout rather than naming this host's paths."""
    req = {
        "schema": "klt.sta.request/1",
        "def": os.path.relpath(ROUTED_DEF, REPORTS_DIR),
        "hdl_toplevel": base.TOP,
        "pdk": {"cell_library": base.CELL_LIBRARY, "corner": corner},
        "constraints": {"clock_port": base.CLOCK_PORT, "clock_period_ns": base.CLOCK_PERIOD_NS},
        "geometry_source": "routed",
    }
    if spef is not None:
        req["spef"] = os.path.relpath(spef, REPORTS_DIR)
    return req


def engine_evidence(response: dict) -> tuple[str | None, str]:
    """(retained OpenROAD log text or None, clock mode). The clock mode is
    read from the generated script itself, accepted only if its hash matches
    the response's own `engine_log.script_sha256`."""
    el = response.get("engine_log") or {}
    klt_dir = REPORTS_DIR / ".klt" / "sta"
    log = None
    inv = el.get("invocation_id")
    if inv:
        d = klt_dir / "openroad-logs" / inv
        parts = [d / "stdout.log", d / "stderr.log"]
        if all(p.is_file() for p in parts):
            log = "\n".join(p.read_text(errors="replace") for p in parts)
    clock = "unverified (generated script not retained or hash mismatch)"
    script = klt_dir / (el.get("script_name") or "")
    if el.get("script_name") and script.is_file() and audit.sha256_file(script) == el.get("script_sha256"):
        text = script.read_text()
        if "create_clock" not in text:
            clock = "none (no create_clock in generated script)"
        elif "set_propagated_clock" in text:
            clock = "propagated"
        else:
            clock = "ideal"
    return log, clock


def sta(pdk, name: str, request: dict) -> dict:
    req_path = REPORTS_DIR / f"{name}.sta_request.json"
    resp_path = REPORTS_DIR / f"{name}.sta_response.json"
    response = base.run_sta(pdk, request, req_path)
    log, clock = engine_evidence(response)
    resp_path.write_text(json.dumps(response, indent=2) + "\n")
    return {"name": name, "response": response, "log": log, "clock_mode": clock}


_FIELDS = (
    "worst_slack_ns", "total_negative_slack_ns", "worst_hold_slack_ns", "total_negative_hold_slack_ns",
    "setup_violation_count", "hold_violation_count", "fmax_mhz", "clock_skew_ns", "estimated_power_mw",
)


def _delta(a: dict, b: dict) -> dict:
    out = {}
    for f in _FIELDS:
        x, y = a.get(f), b.get(f)
        out[f] = None if x is None or y is None else round(y - x, 6)
    return out


def _check_negctl_net(def_: audit.Def, real_resp: dict) -> None:
    conns = def_.nets.get(NEGCTL_NET)
    if not conns or not any(p == "D" for _, p in conns):
        raise SpefModeError(f"negative-control net {NEGCTL_NET} is not a flop-D net in the DEF: {conns}")
    missing = (real_resp.get("spef_annotation") or {}).get("design_nets_missing_sample") or []
    if NEGCTL_NET in missing:
        raise SpefModeError(f"negative-control net {NEGCTL_NET} is already missing from the real SPEF")


def run_spef_mode(*, pdk, rid: str, when, write_record: bool) -> int:
    missing = check_capabilities()
    if missing:
        print("ERROR: this klt install lacks: " + ", ".join(missing), file=sys.stderr)
        return 1
    SCRATCH.mkdir(parents=True, exist_ok=True)
    prefix = f"{rid}.{LIB_TAG}"

    inputs = {_rel(p): audit.sha256_file(p) for p in (ROUTED_DEF, ROUTED_GDS, ROUTED_V)}
    libs = {c: liberty_path(pdk, c) for c, _ in base.CORNERS}
    lib_hashes = {c: audit.sha256_file(p) for c, p in libs.items()}

    # 1. Extraction (the real SPEF, committed) ---------------------------------
    spef = REPORTS_DIR / f"{prefix}.sar_ctrl.spef"
    argv = extract_argv(spef, SCRATCH / f"{prefix}.sar_ctrl.spice", def_pins=True)
    print("extract: " + " ".join(argv))
    try:
        ext = run_extract(pdk, argv)
    except SpefModeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    trimmed: dict = {}
    slim = trim(ext, "", trimmed)
    (REPORTS_DIR / f"{prefix}.sar_ctrl.extract_response.json").write_text(
        json.dumps({"_trimmed_lists": trimmed, **slim}, indent=2) + "\n"
    )
    spef_sha = audit.sha256_file(spef)
    if ext.get("provenance", {}).get("input", {}).get("content_hash") != "sha256:" + inputs[_rel(ROUTED_GDS)]:
        print("ERROR: klt extract's input content_hash does not match the committed GDS", file=sys.stderr)
        return 1

    # 2. Static agreement audit ------------------------------------------------
    def_ = audit.parse_def(ROUTED_DEF.read_text())
    ver = audit.parse_verilog(ROUTED_V.read_text())
    cells = set(def_.components.values())
    lib_pins = {c: audit.parse_liberty_pins(p.read_text(), cells) for c, p in libs.items()}
    pinsets = {c: {k: sorted(v) for k, v in lp.items()} for c, lp in lib_pins.items()}
    lib_pins_agree = all(pinsets[c] == pinsets[base.CORNERS[0][0]] for c in pinsets)
    real_spef = audit.parse_spef(spef.read_text())
    static = audit.audit_agreement(real_spef, def_, ver, lib_pins[base.CORNERS[0][0]])
    design_nets = set(def_.nets) | set(def_.special_nets)
    design_insts = set(def_.components)
    print(f"static audit: {'OK' if static['ok'] else 'ERRORS'} on nets {static['nets_with_errors']}")

    # 3. Per-corner reference (no SPEF) and SPEF runs ---------------------------
    corners = []
    for corner, desc in base.CORNERS:
        print(f"STA corner {corner}: reference (no spef) ...")
        ref = sta(pdk, f"{prefix}.sta_postroute_ref_{corner}", build_request(corner, None))
        print(f"STA corner {corner}: extracted SPEF ...")
        sp = sta(pdk, f"{prefix}.sta_postroute_spef_{corner}", build_request(corner, spef))
        warns = audit.classify_reader_warnings(sp["log"], design_nets, design_insts) if sp["log"] is not None else None
        reasons = audit.gate(sp["response"], static, warns)
        deck_hash = (sp["response"].get("provenance", {}).get("deck") or {}).get("content_hash")
        if deck_hash != "sha256:" + lib_hashes[corner]:
            reasons.append(f"klt sta resolved Liberty {deck_hash}, not the hashed {libs[corner].name}")
        if sp["clock_mode"] != "ideal" or ref["clock_mode"] != "ideal":
            reasons.append(f"clock mode not verified ideal (spef: {sp['clock_mode']}, ref: {ref['clock_mode']})")
        bl_path = REPORTS_DIR / f"{BASELINE_RID}.{LIB_TAG}.sta_postroute_{corner}.sta_response.json"
        bl = json.loads(bl_path.read_text())
        corners.append({
            "corner": corner,
            "desc": desc,
            "liberty": libs[corner].name,
            "liberty_sha256": lib_hashes[corner],
            "clock_mode": sp["clock_mode"],
            "ref_clock_mode": ref["clock_mode"],
            "spef": {f: sp["response"].get(f) for f in _FIELDS + ("timing_status",)},
            "ref": {f: ref["response"].get(f) for f in _FIELDS + ("timing_status",)},
            "baseline": {f: bl.get(f) for f in _FIELDS},
            "delta_spef_minus_ref": _delta(ref["response"], sp["response"]),
            "delta_ref_minus_baseline": _delta(bl, ref["response"]),
            "spef_annotation": sp["response"].get("spef_annotation"),
            "reader_warnings": warns,
            "engine_version": sp["response"].get("engine_version"),
            "gate_reasons": reasons,
            "accepted": not reasons,
        })
        print(f"  {'ACCEPTED' if not reasons else 'REJECTED'}: setup {sp['response'].get('worst_slack_ns')} ns, "
              f"hold {sp['response'].get('worst_hold_slack_ns')} ns; {len(reasons)} rejection reason(s)")

    # 4. Negative controls at one corner ----------------------------------------
    tt_real = next(c for c in corners if c["corner"] == NEGCTL_CORNER)
    try:
        _check_negctl_net(def_, {"spef_annotation": tt_real["spef_annotation"]})
    except SpefModeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    real_text = spef.read_text()
    controls = []
    for mode in ("drop", "rename"):
        ctl_spef = SCRATCH / f"{prefix}.negctl_{mode}_{NEGCTL_NET}.spef"
        ctl_spef.write_text(audit.derive_negative_control(real_text, NEGCTL_NET, mode))
        controls.append({"name": f"{mode}_{NEGCTL_NET}", "spef": ctl_spef,
                         "derivation": f"real SPEF with net {NEGCTL_NET} "
                                       + ("removed (whole *D_NET block)" if mode == "drop"
                                          else f"renamed to {NEGCTL_NET}_negctl everywhere"),
                         "expect": "net_missing"})
    nodefpins = SCRATCH / f"{prefix}.negctl_nodefpins.spef"
    nd_argv = extract_argv(nodefpins, SCRATCH / f"{prefix}.negctl_nodefpins.spice", def_pins=False)
    try:
        run_extract(pdk, nd_argv)
    except SpefModeError as exc:
        print(f"ERROR: control extraction failed: {exc}", file=sys.stderr)
        return 1
    controls.append({"name": "nodefpins", "spef": nodefpins,
                     "derivation": "tool-default extraction without --def-pins: " + " ".join(nd_argv),
                     "expect": "delay_unchanged"})
    for ctl in controls:
        print(f"negative control {ctl['name']} ({NEGCTL_CORNER}) ...")
        r = sta(pdk, f"{prefix}.sta_postroute_spef_negctl_{ctl['name']}", build_request(NEGCTL_CORNER, ctl["spef"]))
        ctl_static = audit.audit_agreement(audit.parse_spef(ctl["spef"].read_text()), def_, ver, lib_pins[NEGCTL_CORNER])
        warns = audit.classify_reader_warnings(r["log"], design_nets, design_insts) if r["log"] is not None else None
        reasons = audit.gate(r["response"], ctl_static, warns)
        ann = r["response"].get("spef_annotation") or {}
        real_ann = tt_real["spef_annotation"] or {}
        if ctl["expect"] == "net_missing":
            specific = (
                NEGCTL_NET in (ann.get("design_nets_missing_sample") or [])
                and ann.get("design_nets_annotated") == (real_ann.get("design_nets_annotated") or 0) - 1
                and NEGCTL_NET in ctl_static["nets_with_errors"]
                and NEGCTL_NET not in static["nets_with_errors"]
            )
        else:
            specific = ann.get("delay_changed") is False and real_ann.get("delay_changed") is True
        ctl.update({
            "spef_sha256": audit.sha256_file(ctl["spef"]),
            "spef": _rel(ctl["spef"]),
            "spef_annotation": ann,
            "static_errors_on": ctl_static["nets_with_errors"],
            "reader_warnings": warns,
            "result": {f: r["response"].get(f) for f in ("worst_slack_ns", "worst_hold_slack_ns", "timing_status")},
            "gate_reasons": reasons,
            "rejected": bool(reasons),
            "detected_specifically": specific,
            "meaningful": bool(reasons) and specific,
        })
        print(f"  {'REJECTED' if reasons else 'ACCEPTED (gate broken!)'}; specific detection: {specific}")

    # 5. Evidence ---------------------------------------------------------------
    sha = git(REPO_ROOT, "rev-parse", "HEAD") or "unknown"
    dirty = synth.working_tree_dirty()
    ev = {
        "record_id": f"{prefix}.sta_postroute_spef",
        "issue": 481,
        "commit": sha,
        "working_tree_dirty": dirty,
        "toolchain": {
            "klt": klt_version(REPO_ROOT),
            "klayout": ext.get("provenance", {}).get("klayout_version"),
            "openroad": corners[0]["engine_version"],
            "pdk": {"variant": pdk.variant, "open_pdks": pdk.version, "source": pdk.source},
            "extract_deck": ext.get("provenance", {}).get("deck"),
        },
        "inputs_sha256": inputs,
        "liberty_sha256": {libs[c].name: h for c, h in lib_hashes.items()},
        "liberty_signal_pins_identical_across_corners": lib_pins_agree,
        "extraction": {
            "argv": argv,
            "spef": _rel(spef),
            "spef_sha256": spef_sha,
            "netlist_sha256": ext.get("netlist_sha256"),
            "warnings": ext.get("warnings"),
            "parasitics_model": (ext.get("parasitics") or {}).get("model"),
            "totals": {k: (ext.get("parasitics") or {}).get(k) for k in (
                "r_count", "c_count", "cc_count", "total_resistance_ohm", "total_capacitance_ff",
                "total_coupling_capacitance_ff")},
            "def_pin_promotion": ext.get("def_pin_promotion"),
        },
        "static_audit": static,
        "corners": corners,
        "negative_controls": controls,
        "output_ports_without_output_delay": sorted(p for p, d in def_.pin_dirs.items() if d == "OUTPUT"),
        "input_ports_without_input_delay": sorted(
            p for p, d in def_.pin_dirs.items() if d == "INPUT" and p != base.CLOCK_PORT),
    }
    all_ok = all(c["accepted"] for c in corners)
    controls_ok = all(c["meaningful"] for c in controls)
    ev["verdict"] = "ACCEPTED" if all_ok else "REJECTED"
    ev["controls_verdict"] = "all rejected, each for its specific defect" if controls_ok else "GATE BROKEN"
    (REPORTS_DIR / f"{prefix}.sta_postroute_spef.audit.json").write_text(json.dumps(ev, indent=2, default=str) + "\n")

    if write_record:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        rec = RECORDS_DIR / f"{prefix}.sta_postroute_spef.md"
        if rec.exists():
            print(f"ERROR: record {rec} already exists -- refusing to overwrite", file=sys.stderr)
            return 1
        import sta_postroute_spef_record as render

        rec.write_text(render.render(ev, when))
        print(f"Evidence record written to {rec}")

    if not controls_ok:
        print("GATE BROKEN: a negative control was not rejected for its specific defect", file=sys.stderr)
        return 2
    if not all_ok:
        print("REJECTED: SPEF annotation incomplete on timed nets at "
              + ", ".join(c["corner"] for c in corners if not c["accepted"])
              + " -- no fallback to unannotated timing; see the record.", file=sys.stderr)
        return 1
    print("All corners: SPEF annotation accepted; see the record for slack and limits.")
    return 0
