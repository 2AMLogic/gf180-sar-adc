"""Render the `<rid>.mcu7t5v0.sta_postroute_spef.md` evidence record from the
`.audit.json` that `sta_postroute_spef.py` writes (issue #481). Pure
formatting: every number comes from that JSON, so the record and the JSON
cannot disagree. Import-only.
"""

from __future__ import annotations


def _f(x, fmt="+.4f"):
    return "n/a" if x is None else format(x, fmt)


def _ann_row(c: dict) -> str:
    a = c["spef_annotation"] or {}
    w = c["reader_warnings"] or {}
    return (
        f"| `{c['corner']}` | {c['clock_mode']} | {a.get('nets_annotated')}/{a.get('nets_total')} "
        f"| {a.get('design_nets_annotated')}/{a.get('design_nets_total')} "
        f"| {a.get('reader_warning_count')} ({w.get('touching_design_records', 'n/a')} on design nets) "
        f"| {a.get('unannotated_driver_count')} | {a.get('partially_unannotated_driver_count')} "
        f"| {a.get('delay_changed')} | {a.get('annotation_complete')} "
        f"| **{'ACCEPTED' if c['accepted'] else 'REJECTED'}** |"
    )


def _timing_row(c: dict) -> str:
    s, r, d = c["spef"], c["ref"], c["delta_spef_minus_ref"]
    return (
        f"| `{c['corner']}` | {s.get('timing_status')} "
        f"| {_f(r['worst_slack_ns'])} | {_f(s['worst_slack_ns'])} | {_f(d['worst_slack_ns'])} "
        f"| {_f(r['worst_hold_slack_ns'])} | {_f(s['worst_hold_slack_ns'])} | {_f(d['worst_hold_slack_ns'])} "
        f"| {s.get('setup_violation_count')}/{s.get('hold_violation_count')} "
        f"| {_f(r['fmax_mhz'], '.2f')} / {_f(s['fmax_mhz'], '.2f')} |"
    )


def _repro_row(c: dict) -> str:
    d = c["delta_ref_minus_baseline"]
    nonzero = {k: v for k, v in d.items() if v not in (0, 0.0, None)}
    return (
        f"| `{c['corner']}` | {_f(c['baseline']['worst_slack_ns'])} | {_f(c['ref']['worst_slack_ns'])} "
        f"| {_f(c['baseline']['worst_hold_slack_ns'])} | {_f(c['ref']['worst_hold_slack_ns'])} "
        f"| {'identical' if not nonzero else ', '.join(f'{k} {v:+g}' for k, v in nonzero.items())} |"
    )


def _static_lines(st: dict) -> str:
    out = []
    by: dict[str, list] = {}
    for e in st["errors"]:
        by.setdefault(e["check"], []).append(e)
    for check, es in sorted(by.items()):
        nets = [e.get("net") for e in es if e.get("net")]
        pins = sorted({p for e in es for p in e.get("def_pins_on_net", [])})
        extra = f" (DEF top-level pins on those nets: {', '.join(pins)})" if pins else ""
        ports = sorted({p for e in es for p in e.get("ports", [])})
        extra += f" (ports: {', '.join(ports)})" if ports else ""
        out.append(f"  - **error `{check}`** x{len(es)}" + (f": {', '.join(nets)}" if nets else "") + extra)
    for i in st["info"]:
        detail = {k: v for k, v in i.items() if k not in ("check", "detail")}
        out.append(f"  - info `{i['check']}`: {detail}" + (f" -- {i['detail']}" if i.get("detail") else ""))
    return "\n".join(out) if out else "  - none"


def render(ev: dict, when) -> str:
    cs = ev["corners"]
    tc = ev["toolchain"]
    ex = ev["extraction"]
    st = ev["static_audit"]
    accepted = [c for c in cs if c["accepted"]]
    rejected = [c for c in cs if not c["accepted"]]
    reasons_tt = next(c for c in cs if c["corner"] == "tt_025C_3v30")["gate_reasons"]
    same_reasons = (
        "every corner is rejected for these same reasons"
        if all(c["gate_reasons"] == reasons_tt for c in cs)
        else "other corners' reasons differ: see the audit JSON"
    )
    witness = st.get("timed_path_witness") or {}
    witness_lines = "\n".join(f"  - `{w}`" if w else f"  - `{n}`: no register reached" for n, w in witness.items())
    conn_sentence = (
        f"All {st['counts']['def_signal_nets']} DEF signal nets have a `*D_NET` whose `*I` set equals the DEF's own `NETS` connections."
        if st.get("conn_sets_all_match")
        else "Some DEF signal nets' `*I` sets differ from the DEF's `NETS` connections (`conn_mismatch` above)."
    )
    tt_w = (next(c for c in cs if c["corner"] == "tt_025C_3v30")["reader_warnings"]) or {}
    ctl_rows = "\n".join(
        f"| `{c['name']}` | {c['derivation']} | `{c['spef_sha256'][:16]}...` "
        f"| {(c['spef_annotation'] or {}).get('design_nets_annotated')}/{(c['spef_annotation'] or {}).get('design_nets_total')}, "
        f"missing sample {(c['spef_annotation'] or {}).get('design_nets_missing_sample')}, "
        f"delay_changed {(c['spef_annotation'] or {}).get('delay_changed')} "
        f"| {'REJECTED' if c['rejected'] else 'ACCEPTED'} | {'yes' if c['detected_specifically'] else 'NO'} |"
        for c in ev["negative_controls"]
    )
    lib_rows = "\n".join(f"  - `{name}`: `{h}`" for name, h in ev["liberty_sha256"].items())
    in_rows = "\n".join(f"  - `{p}`: `{h}`" for p, h in ev["inputs_sha256"].items())
    deck = tc.get("extract_deck") or {}
    totals = ex["totals"]
    outs = ev["output_ports_without_output_delay"]
    ins = ev["input_ports_without_input_delay"]

    return f"""\
# Record {ev['record_id']}

- **Record ID**: {ev['record_id']}
- **Claim under test**: the committed routed `sar_ctrl_a` macro (#274/#279), with
  interconnect parasitics extracted from its own routed GDS by `klt extract`
  and annotated into `klt sta` through the `spef` request field, meets
  DR-0003's 62.5 ns clock at the same five `gf180mcu_fd_sc_mcu7t5v0` corners
  as the baseline record `{_baseline(ev)}`. Issue #481.
- **Verdict**: **{ev['verdict']}**. {len(accepted)} of {len(cs)} corners passed the annotation
  gate ({', '.join(c['corner'] for c in rejected) or 'none'} rejected). A rejected corner's slack is
  **not** a real-parasitics measurement and is not quoted as one. The driver
  does not fall back to the unannotated timing, and exits 1.
- **Why rejected** (`tt_025C_3v30`; {same_reasons}):
{chr(10).join('  - ' + r for r in reasons_tt) or '  - (accepted)'}
- **Negative controls**: {ev['controls_verdict']}.
- **Clock mode (every run, both SPEF and reference)**: ideal SDC clock, read from
  each retained generated script (hash-matched to `engine_log.script_sha256`).
  It contains `create_clock` and no `set_propagated_clock`. `klt sta` has no
  propagated-clock mode: klayout-tools#2739 (open). The propagated-clock half of
  #481 was **not run**.
- **Interconnect corner**: one nominal extraction, used at all five Liberty
  corners. No RC-corner sweep is claimed (klayout-tools#2858, open).
- **This record does not supersede** `{_baseline(ev)}`. That record stays the
  cited bounded timing evidence (no SPEF, ideal clock) until a SPEF run passes
  this gate.

## Provenance

- **Inputs (sha256)**: the fixed routed macro, read only and unchanged.
{in_rows}
  - The DEF hash equals the baseline responses' `provenance.input.content_hash`.
    The GDS hash equals `klt extract`'s own `provenance.input.content_hash` and
    the P&R record's DRC report (`20260915-000027-3a9a8ba.mcu7t5v0.pnr_drc.json`).
- **SPEF**: `{ex['spef']}`, sha256 `{ex['spef_sha256']}`
  (`*DATE` is a fixed placeholder, klayout-tools#1627, so a re-run on the same
  inputs and toolchain should reproduce these bytes). SPICE side-output
  sha256 `{ex['netlist_sha256']}` (not committed).
- **Extraction command** (run from the repo root, with `PDK_ROOT`/`PDK` set):
  `{' '.join(ex['argv'])}`
- **Liberty (sha256)**, each equal to `klt sta`'s per-corner `provenance.deck.content_hash`:
{lib_rows}
- **Toolchain**: `{tc['klt']}`; KLayout `{tc['klayout']}`; OpenROAD `{tc['openroad']}`;
  PDK `{tc['pdk']['variant']}`, open_pdks `{tc['pdk']['open_pdks']}` (via {tc['pdk']['source']});
  extraction deck `{deck.get('name')}` `{deck.get('content_hash')}` (options `{deck.get('options')}`).
  The baseline record ran on klt 0.4.0. `layout/toolchain.json` pins
  `klayout-tools==0.6.0` for the `layout/` DRC/LVS flow. This run used the
  host-provisioned 0.7.0 build, which provides every flag this mode checks for.
- **Reproducibility**: working tree {'DIRTY at run time: re-run against a clean checkout before trusting this record' if ev['working_tree_dirty'] else 'clean'} at commit
  `{ev['commit']}`. Re-run: `python3 design/sar-logic/flow/sta_sar_ctrl_postroute.py --spef`.
- **Timestamp / author**: {when.strftime('%Y-%m-%d %H:%M:%S UTC')}, `design/sar-logic/flow/sta_postroute_spef.py` (agent-run)

## Extraction model (what the SPEF is, and is not)

`klt extract --parasitics` on the `gf180mcu` deck, which is a curated starter
subset (not foundry RCX). It extracted {totals['r_count']} R, {totals['c_count']} ground C and {totals['cc_count']}
coupling C: total {_f(totals['total_capacitance_ff'], '.1f')} fF ground and {_f(totals['total_coupling_capacitance_ff'], '.2f')} fF
coupling. The model is a lumped star per net. Each `*I inst:pin` hangs off
the net's hub through a 0-ohm leg (klayout-tools `docs/cli/extract.md`,
`--def-net-connections`), so OpenSTA sees each net as a lumped capacitance
with **no wire resistance between driver and loads** (klayout-tools#2880 gap
3). Lateral same-layer coupling is modelled only for `--critical-net` nets,
and none were named. Even a fully accepted run of this model would be
evidence about wire *capacitance*, not signoff-grade RCX.

Extraction warnings, verbatim:
{chr(10).join('- ' + w for w in ex['warnings'] or [])}

`--def-pins` is the documented automatic port-set source for a
DEF-to-GDS-merged layout (`docs/cli/extract.md`, "Pair `--spef` with
`--pins`"). Without it, every routed net is declared a top-level port.
OpenSTA then resolves each bare hub node as a missing port and drops every
RC element, which control `nodefpins` below demonstrates.

## Static SPEF / DEF / Verilog / Liberty agreement audit

`spef_audit.audit_agreement`. It runs before STA, needs no tool, and names
what OpenSTA's counts only total.

- Units/delimiters: SPEF `*C_UNIT {st['spef_header'].get('C_UNIT')}`, `*R_UNIT {st['spef_header'].get('R_UNIT')}`,
  `*T_UNIT {st['spef_header'].get('T_UNIT')}`, `*DIVIDER {st['spef_header'].get('DIVIDER')}`, `*DELIMITER {st['spef_header'].get('DELIMITER')}`,
  `*BUS_DELIMITER {st['spef_header'].get('BUS_DELIMITER')}`. These are checked against FF/OHM and the DEF's
  `DIVIDERCHAR`/`BUSBITCHARS`.
- Counts: {st['counts']}
- Liberty signal-pin sets identical across the five corners: {ev['liberty_signal_pins_identical_across_corners']}
- Findings:
{_static_lines(st)}

How to read this: {conn_sentence} The `port_name_mismatch`
nets are the findings that matter. On each of them the DEF attaches a
top-level PIN with a *different* name (e.g. PIN `c0` on NET `c0_r`; Verilog
`assign c0 = c0_r`). The SPEF declares `*P <net>` and writes the net's hub as
the bare net name, which OpenSTA resolves as a non-existent port. This is
klayout-tools#2880 gap 1 (open). The floating-output pins are CTS dummy-load
outputs with no net (gap 2). They are not on any timed path, but OpenSTA
counts them as unannotated drivers, which by itself keeps
`annotation_complete` false on this macro.

## Annotation evidence per corner (SPEF runs)

| Corner | Clock | SPEF nets named in design | Design nets named by SPEF | Reader warnings discarded | Unannotated drivers | Partially unannotated drivers | delay_changed | klt annotation_complete | Gate |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(_ann_row(c) for c in cs)}

Reader-warning classification (`tt_025C_3v30`, from the retained OpenROAD
log): {tt_w.get('by_code')}. Records on design nets: {tt_w.get('touching_design')}.
Non-design: {tt_w.get('non_design')}. The STA-1650 records are SPEF nets the
design does not have (flat extraction's intra-cell `$N` nets and the
sub-cell labels `Z`/`ZN`). They are expected and not timed. The STA-1656
records are every RC element on the `port_name_mismatch` nets, so those
nets carry **no** parasitics in the SPEF runs. Each is on a timed register path
(computed by `spef_audit.timed_path_witness` from the Verilog and Liberty
pin directions):

{witness_lines}

## Timing, SPEF run vs. same-toolchain unannotated reference

These SPEF numbers are **partially annotated**: real lumped C on the
accepted nets, nothing on the {len(st['nets_with_errors'])} rejected nets. They are shown so that the
measured movement is visible. They are not a timing-closure result.

| Corner | timing_status | Setup ref (ns) | Setup SPEF (ns) | delta | Hold ref (ns) | Hold SPEF (ns) | delta | SPEF setup/hold violators | Fmax ref / SPEF (MHz) |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(_timing_row(c) for c in cs)}

## Reference reproduces the committed baseline

The reference request is the baseline's request with relative paths, run on
this record's toolchain:

| Corner | Baseline setup | Reference setup | Baseline hold | Reference hold | Other field deltas |
|---|---|---|---|---|---|
{chr(10).join(_repro_row(c) for c in cs)}

**Correction to how the baseline is described.** The baseline record and
`layout/adc-top/sar_ctrl/README.md` say OpenSTA "estimated RC from the DEF
geometry". The generated `klt sta` script (0.7.0 here, and `post_route_sta.py`
at klt v0.4.0) has no `estimate_parasitics`/`set_wire_rc` step. `docs/cli/sta.md`
describes the no-`spef` case as "unannotated, LEF-capacitance-only". The
`nodefpins` control below also shows that a SPEF which annotates nothing
leaves every path byte-identical to the reference. The baseline numbers
therefore include **no wire parasitics at all**, only Liberty pin
capacitance. The 20260915 record is append-only and is not edited. This
record and the macro README carry the correction.

## Unconstrained endpoints

`timing_status` is `constrained` at every corner (table above). `klt sta`
reports no count of unconstrained endpoints (klayout-tools#2780, open).
Structurally, the request sets no `input_delay_ns`/`output_delay_ns`, which is
the same as the baseline. So the {len(outs)} output ports ({', '.join(outs[:6])}, ...) are unconstrained
endpoints and the {len(ins)} non-clock inputs are unconstrained startpoints,
by construction, in both this run and the baseline. Only register-to-register
paths are timed. This is unchanged from the baseline and not a regression.

## Negative controls (`tt_025C_3v30`)

Each control must be rejected by the same gate, *for its own defect*: the
specific net is reported missing, or `delay_changed` goes false while the
real SPEF's is true. Control SPEFs are scratch files under the gitignored
`design/sar-logic/flow/sar_ctrl/reports/.klt/spef_481/`, re-derived by the
driver. Their hashes are listed, and their `klt sta` request/response JSON is
committed as `{ev['record_id'].rsplit('.', 1)[0]}.sta_postroute_spef_negctl_<name>.sta_{{request,response}}.json`.
They are never the real SPEF.

| Control | Derivation | SPEF sha256 | klt annotation evidence | Gate | Detected its own defect |
|---|---|---|---|---|---|
{ctl_rows}

## What would close this

1. klayout-tools#2880 gaps 1 and 2: `*P` under the DEF PIN name with an
   internal hub, and no `*D_NET` for floating cell outputs. Then a re-run of
   this driver, unchanged. The gate and controls are already in place.
2. klayout-tools#2739 for a propagated clock, and #2858 for interconnect
   corners. Until then the "ideal clock" and "nominal extraction" limits
   stand.

## Links

- Driver: `design/sar-logic/flow/sta_sar_ctrl_postroute.py --spef` (`sta_postroute_spef.py`, `spef_audit.py`)
- Machine-readable evidence: `design/sar-logic/flow/sar_ctrl/reports/{ev['record_id']}.audit.json`
- Per-corner requests/responses: `.../reports/{ev['record_id'].rsplit('.', 1)[0]}.sta_postroute_{{ref,spef}}_<corner>.sta_{{request,response}}.json`
- `klt extract` response (long lists trimmed to their length): `.../reports/{ev['record_id'].rsplit('.', 1)[0]}.sar_ctrl.extract_response.json`
- Baseline: `design/sar-logic/flow/sar_ctrl/records/{_baseline(ev)}.md`
"""


def _baseline(ev: dict) -> str:
    return "20260915-093934-7ab8971.mcu7t5v0.sta_postroute"
