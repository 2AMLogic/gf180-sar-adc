#!/usr/bin/env python3
"""Full 18-transition static-linearity (INL/DNL) sweep against the
extracted-core testbench -- issue #89 **Scope item 1 / 3 / 8** (the piece
`measure_extracted_gain_err.py`'s own docstring named as still deferred:
"the full INL/DNL claim (needs all 18 transitions -- `inl_t<k>_lsb` /
`dnl_t<a>_t<b>_lsb`)").

This is the SAME two endpoints (transitions 1, 1023) `measure_extracted_gain_err.py`
already reports `gain_err_lsb` from, plus the sixteen interior probed
transitions `design/adc-top/gen_adc_top.py`'s own `INL_TRANSITIONS` ladder
names -- same input schedule, same shadow-DAC/error-node formula (copied
verbatim, not re-derived), same `inl_manifest()` endpoint-correction and
DNL-pair-difference formulas, so every number this script reports is directly
comparable, corner-for-corner, to `sim/adc-inl-dnl/`'s own schematic columns.

    python3 layout/adc-top/parasitics/measure_extracted_inl_dnl.py
    python3 layout/adc-top/parasitics/measure_extracted_inl_dnl.py \
        --corners tt ss ff --temps -40 27 125 --vdd 2.97 3.30 3.63 \
        --json out.json

What this substantiates, and how narrowly:

- **The full `inl_t<k>_lsb` / `dnl_t<a>_t<b>_lsb` / `gain_err_lsb` set** of the
  extracted `ADC_TOP` core, wired exactly as `gen_extracted_core_tb.py` wires
  it (schematic comparator + rung-1 controller + DR-0013 input network,
  extracted CDAC core), at the SAME 18 transitions and the SAME formulas
  `sim/adc-inl-dnl/`'s `inl_manifest()` uses.
- **What this explicitly is NOT**: the ENOB/FFT/SFDR or power re-run (Scope
  item 1's other two spec-line benches), or the #14 Monte Carlo re-run (Scope
  item 2). Those remain deferred, tracked in #89.
- **Compute cost is real**: one point is the full 20 us / 20-transition
  transient this deck's schematic counterpart runs, against a ~1300-device
  RC-laden extracted netlist -- `layout/adc-top/parasitics/README.md`'s
  "material multi-hour campaign" warning is about exactly this script.
  Measured wall time is reported per point and in the record's own
  "Subset-corner justification", per `sim/README.md`.

The PDK is discovered through `sim/harness/pdk.py`; with no PDK installed the
script skips with a clear message rather than fabricating a result.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness import corners as C  # noqa: E402
from harness import pdk as PDK  # noqa: E402

import gen_extracted_core_tb as G  # noqa: E402 (same directory)

NGSPICE = "ngspice"

#: The full 18-transition ladder -- literally gen_adc_top.INL_TRANSITIONS, not
#: a re-typed copy, so this script cannot silently drift from the schematic
#: bench's own transition set if that list is ever edited.
TRANSITIONS = G.gtop.INL_TRANSITIONS
DNL_PAIRS = G.gtop.INL_DNL_PAIRS
GAIN_LO, GAIN_HI = TRANSITIONS[0], TRANSITIONS[-1]
assert (GAIN_LO, GAIN_HI) == (1, 1023), (
    "gen_adc_top.INL_TRANSITIONS endpoints changed -- this script derives "
    "GAIN_LO/GAIN_HI from that list directly, so no separate update should "
    "be needed; this assertion exists to catch a silent shape change."
)


def _shadow_dac_and_error(tag: str) -> list[str]:
    """Ideal shadow DAC + input-referred error node + the decision-gated
    |error| node `aerrh` (`decerr_t<k>_lsb`'s source) -- copied verbatim (same
    variable names, same formula) from `gen_adc_top._core()`. See that
    function's own comments for the full charge-conservation derivation and
    `measure_extracted_gain_err.py`'s module docstring for why this is safe
    to reuse unmodified: `gen_extracted_core_tb.py`'s `_wire_pin()` already
    drives the extracted core's `.SUBCKT` pins onto the SAME net names this
    formula expects.
    """
    L: list[str] = []
    a = L.append
    a("* ---- ideal shadow DAC + error node (issue #89 Scope items 1/3/8) ----")
    a("* Verbatim formula from gen_adc_top._core() -- see that function for")
    a("* the charge-conservation derivation. Wired onto the SAME per-weight")
    a("* nets gen_extracted_core_tb._wire_pin() already drives.")
    for s in ("p", "n"):
        terms = [
            f"{w}*((v({tag}_rel_n_{w}{s})*vcm+v({tag}_sel_hi_n_{w}{s})*vref"
            f"+v({tag}_sel_in_n)*v({tag}_vin{s}))/vdd_val-vcm)"
            for w in G.gtop.WEIGHTS
        ]
        L += G.gtop.sar._wrap(
            f"b{tag}dac{s} {tag}_dac{s} 0 V = (1.0/512)*(",
            [" + ".join(terms) + " )"],
        )
    a(
        f"b{tag}di {tag}_di 0 V = v({tag}_vinn)-v({tag}_vinp)"
        f"+v({tag}_dacp)-v({tag}_dacn)"
    )
    a(
        f"b{tag}e {tag}_err 0 V = (v({tag}_di)-(v({tag}_topp)-v({tag}_topn)))"
        f"/lsb"
    )
    a(f"b{tag}ea {tag}_aerrh 0 V = abs(v({tag}_err))*(v(cmpclk)>vth ? 1 : 0)")
    return L


def _end_ns() -> float:
    return (G.gtop.INL_WARMUP_CONV + G.gtop.INL_CONV_PER_POINT * len(TRANSITIONS)) * G.gtop.CONV_NS


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                  vdd: float) -> str:
    """The complete ngspice deck for one PVT point -- the full 18-transition
    ladder, same input schedule/timing `gen_adc_top.inl_netlist()` uses.
    """
    tag = G.TAG
    lines = [
        "* extracted-core full INL/DNL sweep -- issue #89 Scope items 1/3/8",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        f".param vdd_val={vdd!r}",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    lines.append(f".temp {temp_c!r}")
    lines.append("")

    lines += G.gtop._preamble("{vdd_val/1024}")
    lines.append("")
    lines.append(
        "* ---- input: piecewise-constant ladder of the 18 probed transitions ----"
    )
    pts: list[str] = []
    prev = ""
    for idx, k in enumerate(TRANSITIONS):
        t0 = (G.gtop.INL_WARMUP_CONV + G.gtop.INL_CONV_PER_POINT * idx) * G.gtop.CONV_NS
        lvl = f"{{({k}+0.25)*lsb}}"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
    pts.append(f"{_end_ns():.1f}n {prev}")
    lines += G.gtop.sar._wrap(f"v{tag}vinp {tag}_vinp 0 pwl(", [" ".join(pts) + ")"])
    lines.append(f"v{tag}vinn {tag}_vinn 0 dc {{vcm}}")
    lines.append("")

    pins, core_text = G.core_pins(top)
    lines.append(G.gtop.comparator_block())
    lines.append(G.gtop.sar.library())
    lines.append(core_text)
    lines += G._core_extracted(tag, "0", pins, top)
    lines += _shadow_dac_and_error(tag)

    lines.append("")
    lines.append(".control")
    lines.append("set numdgt=8")
    lines.append("set noaskquit")
    lines.append(f"tran 1n {_end_ns() / 1000:.3f}u 0 2n")
    for idx, k in enumerate(TRANSITIONS):
        t0 = (
            G.gtop.INL_WARMUP_CONV + G.gtop.INL_CONV_PER_POINT * idx
            + G.gtop.INL_CONV_PER_POINT - 1
        ) * G.gtop.CONV_NS
        tdec = t0 + G.gtop.trial_decision_ns(G.gtop._inl_trial(k)) - 0.05
        lines.append(f"meas tran e{k} FIND v({tag}_err) AT={tdec:.3f}n")
        lines.append(
            f"meas tran x{k} MAX v({tag}_aerrh) FROM={t0 + 280:.1f}n"
            f" TO={t0 + 880:.1f}n"
        )
        lines.append(f"meas tran cd{k} FIND v({tag}_code) AT={t0 + 950:.1f}n")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n"


_MEAS_RE = re.compile(r"\b([a-z]+)(\d+)\s*=\s*([-\d.eE+]+)")


def _parse(out: str) -> dict[str, float]:
    """`{'e1': ..., 'x1': ..., 'cd1': ..., ...}` from raw ngspice stdout."""
    vals: dict[str, float] = {}
    for m in _MEAS_RE.finditer(out):
        prefix, num, val = m.group(1), m.group(2), m.group(3)
        if prefix in ("e", "x", "cd"):
            vals[f"{prefix}{num}"] = float(val)
    return vals


def run(deck: str, workdir: Path) -> tuple[dict[str, float], str]:
    path = workdir / "extracted_core_inl_dnl.spice"
    path.write_text(deck)
    proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                          text=True, cwd=workdir, timeout=1800, check=False)
    out = proc.stdout + "\n" + proc.stderr
    vals: dict[str, float] = {}
    for k in TRANSITIONS:
        for prefix in ("e", "x", "cd"):
            key = f"{prefix}{k}"
            m = re.search(rf"\b{key}\s*=\s*([-\d.eE+]+)", out)
            vals[key] = float(m.group(1)) if m else float("nan")
    return vals, out


def _derive(vals: dict[str, float]) -> dict[str, float]:
    """`inl_t<k>_lsb` / `dnl_t<a>_t<b>_lsb` / `gain_err_lsb`, same formulas as
    `gen_adc_top.inl_manifest()` -- endpoint-corrected against GAIN_LO/GAIN_HI.
    """
    out: dict[str, float] = {}
    lo, hi = GAIN_LO, GAIN_HI
    e_lo, e_hi = vals[f"e{lo}"], vals[f"e{hi}"]
    for k in TRANSITIONS:
        frac = (k - lo) / (hi - lo)
        out[f"inl_t{k}_lsb"] = vals[f"e{k}"] - (e_lo + frac * (e_hi - e_lo))
    for a_, b_ in DNL_PAIRS:
        out[f"dnl_t{a_}_t{b_}_lsb"] = vals[f"e{b_}"] - vals[f"e{a_}"]
    out["gain_err_lsb"] = (e_hi - e_lo) * (1023.0 / (hi - lo))
    return out


def measure_point(top: str, pdk: PDK.Pdk, corner_name: str, temp_c: float,
                   vdd: float, log_dir: Path | None = None,
                   snapshot_path: Path | None = None) -> dict:
    corner = C.CORNERS[corner_name]
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        deck = compose_deck(top, pdk, corner, temp_c, vdd)
        if snapshot_path is not None:
            snapshot_path.write_text(deck)
        vals, log = run(deck, work)
    dt = time.monotonic() - t0
    corner_id = f"{corner_name}_{temp_c:g}c_{vdd:.2f}v"
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{corner_id}.log").write_text(log)
    any_nan = any(v != v for v in vals.values())
    derived = {} if any_nan else _derive(vals)
    point = {
        "corner_id": corner_id,
        "corner": corner_name,
        "temp_c": temp_c,
        "vdd": vdd,
        "sim_wall_s": round(dt, 2),
        "converged": not any_nan,
    }
    for k in TRANSITIONS:
        point[f"terr_t{k}_lsb"] = vals[f"e{k}"]
        point[f"decerr_t{k}_lsb"] = vals[f"x{k}"]
        point[f"code_t{k}"] = vals[f"cd{k}"]
    point.update(derived)
    return point


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP"])
    ap.add_argument("--corners", nargs="+", default=["tt"],
                    help="corner name(s) or corner-set name from sim/harness/corners.py")
    ap.add_argument("--temps", nargs="+", type=float, default=[27.0],
                    help="temperatures in C (default: nominal only)")
    ap.add_argument("--vdd", nargs="+", type=float, default=[3.3],
                    help="supply voltage(s) (default: nominal only)")
    ap.add_argument("--json", help="write the full result JSON here")
    ap.add_argument("--log-dir", help="write raw per-corner ngspice logs here "
                    "(sim/README.md corners/<record-id>/<corner-id>.log convention)")
    ap.add_argument("--snapshot", help="write the FIRST point's composed deck here "
                    "(sim/README.md netlist-snapshots/<record-id>.spice convention)")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py). "
              "This measurement needs the PDK to run ngspice.", file=sys.stderr)
        return 0

    pdk = PDK.find_pdk()
    corner_names: list[str] = []
    for name in args.corners:
        corner_names += list(C.CORNER_SETS.get(name, (name,)))
    seen: set[str] = set()
    corner_names = [c for c in corner_names if not (c in seen or seen.add(c))]

    log_dir = Path(args.log_dir) if args.log_dir else None
    snapshot_path = Path(args.snapshot) if args.snapshot else None

    points = []
    t_all0 = time.monotonic()
    for corner_name in corner_names:
        for temp_c in args.temps:
            for vdd in args.vdd:
                this_snapshot = snapshot_path if (snapshot_path and not points) else None
                pt = measure_point(args.top, pdk, corner_name, temp_c, vdd,
                                   log_dir=log_dir, snapshot_path=this_snapshot)
                points.append(pt)
                tag = "OK" if pt["converged"] else "NaN"
                print(
                    f"{pt['corner_id']:>20}  gain_err={pt.get('gain_err_lsb', float('nan')):+.4f}"
                    f"  [{tag}]  ({pt['sim_wall_s']:.1f}s)"
                )

    total_s = time.monotonic() - t_all0

    result = {
        "top": args.top,
        "claim": "issue #89 Scope items 1/3/8: full 18-transition INL/DNL "
                 "(inl_t<k>_lsb, dnl_t<a>_t<b>_lsb) and gain_err_lsb of the "
                 "extracted ADC_TOP core (schematic comparator + rung-1 "
                 "controller + DR-0013 input network, extracted CDAC core), "
                 "same methodology as sim/adc-inl-dnl/'s inl_manifest().",
        "netlist_provenance": "extracted (remediated: PMOS-body->vdd local "
                              "remediation of klayout-tools#555; input rails "
                              "promoted to vinp/vinn) wired to the schematic "
                              "comparator + rung-1 SAR controller + DR-0013 "
                              "input drive network",
        "pdk": pdk.provenance(),
        "transitions": TRANSITIONS,
        "dnl_pairs": DNL_PAIRS,
        "points": points,
        "total_wall_s": round(total_s, 2),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")
    n_ok = sum(1 for p in points if p["converged"])
    print(f"TOTAL: {n_ok}/{len(points)} converged in {total_s:.1f}s "
          f"({total_s / max(len(points), 1):.1f}s/point)")
    return 0 if n_ok == len(points) else 2


if __name__ == "__main__":
    raise SystemExit(main())
