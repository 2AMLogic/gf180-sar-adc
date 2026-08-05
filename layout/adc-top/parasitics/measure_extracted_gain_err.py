#!/usr/bin/env python3
"""First real spec-line measurement against the extracted-core testbench --
issue #89 **Scope items 3 / 8**: "the extracted-netlist systematic gain-error
term (`gain_err_lsb`, per corner, per #53's measurement methodology in
`sim/adc-inl-dnl/`)".

`gen_extracted_core_tb.py` deliberately OMITS the ideal shadow DAC / error
node its own docstring calls out: "Those exist to support an INL/DNL CLAIM
(Scope item 1, deferred); this harness's own claim is narrower." This module
is that deferred piece's first real increment -- narrowly scoped to
`gain_err_lsb` only (the two endpoint transitions, 1 and 1023, the same pair
`design/adc-top/gen_adc_top.py`'s own `inl_manifest()` extrapolates to full
scale), NOT the full 18-transition INL/DNL sweep (Scope item 1 remains
deferred, tracked in #89 -- that needs the whole ladder times the full PVT
grid, the "material multi-hour simulation campaign" `parasitics/README.md`'s
Compute note warns about).

Why only two transitions can be added without re-deriving anything: the
shadow-DAC formula below is copied VERBATIM from `gen_adc_top._core()`
(design/adc-top/gen_adc_top.py) -- not re-derived -- because it references
nets `_wire_pin()` (`gen_extracted_core_tb.py`) ALREADY drives onto the
extracted core's own `.SUBCKT` pins: `{tag}_rel_n_<w><s>`,
`{tag}_sel_hi_n_<w><s>`, `{tag}_sel_in_n`, `{tag}_vin<s>`. No new wiring
convention is introduced; this only reconnects a formula that was already
true of the wires already present.

    python3 layout/adc-top/parasitics/measure_extracted_gain_err.py
    python3 layout/adc-top/parasitics/measure_extracted_gain_err.py \
        --corners cdac --temps 27 --vdd 3.3 --json out.json

What this substantiates, and how narrowly:

- **`gain_err_lsb` of the extracted `ADC_TOP` core**, wired exactly as
  `gen_extracted_core_tb.py` wires it (schematic comparator + rung-1
  controller + DR-0013 input network, extracted CDAC core), at the SAME two
  endpoint transitions (1, 1023) and the SAME extrapolation formula
  `sim/adc-inl-dnl/`'s `inl_manifest()` uses -- so the number this script
  reports is directly comparable to that experiment's own `gain_err_lsb`
  column, corner-for-corner.
- **What this explicitly is NOT**: the full INL/DNL claim (needs all 18
  transitions -- `inl_t<k>_lsb` / `dnl_t<a>_t<b>_lsb`), the ENOB/power suite
  re-run, or the #14 Monte Carlo re-run. Those remain deferred, tracked in
  #89.
- **Corner coverage is a documented subset, not the full 63-point grid**: see
  `--corners` / `--temps` / `--vdd` defaults and the record this script's
  caller mints -- CLAUDE.md requires PVT corners on every recorded result,
  and `sim/README.md`'s "Subset-corner justification" requires an unexplained
  subset never be recorded as evidence, so the caller states explicitly which
  points were run and why the rest were deferred.

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

#: The two endpoint transitions `sim/adc-inl-dnl/`'s own `gain_err_lsb`
#: extrapolates from -- literally `gtop.INL_TRANSITIONS[0]` /
#: `gtop.INL_TRANSITIONS[-1]`, asserted below rather than copied blind, so
#: this script cannot silently drift from the schematic bench's own endpoint
#: choice if that list is ever edited.
assert G.gtop.INL_TRANSITIONS[0] == 1 and G.gtop.INL_TRANSITIONS[-1] == 1023, (
    "gen_adc_top.INL_TRANSITIONS endpoints changed -- update GAIN_LO/GAIN_HI "
    "below to match, do not silently keep 1/1023"
)
GAIN_LO = G.gtop.INL_TRANSITIONS[0]
GAIN_HI = G.gtop.INL_TRANSITIONS[-1]


def _shadow_dac_and_error(tag: str) -> list[str]:
    """Ideal shadow DAC + input-referred error node.

    Copied verbatim (same variable names, same formula) from the shadow-DAC
    block inside `gen_adc_top._core()` -- see that function's own comments
    for the full charge-conservation derivation. Not re-derived here: the
    only reason this is possible at all is that `gen_extracted_core_tb.py`'s
    `_wire_pin()` already drives the extracted core's `.SUBCKT` pins onto
    THE SAME net names `_core()`'s formula expects
    (`{tag}_rel_n_<w><s>`, `{tag}_sel_hi_n_<w><s>`, `{tag}_sel_in_n`,
    `{tag}_vin<s>`, `{tag}_topp`/`{tag}_topn`).
    """
    L: list[str] = []
    a = L.append
    a(f"* ---- ideal shadow DAC + error node (issue #89 Scope items 3/8) ----")
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
    return L


def _end_ns() -> float:
    # Two probed points (idx 0, 1) after INL_WARMUP_CONV(2) warm-up
    # conversions -- same timing convention as gen_adc_top._inl_end_ns(),
    # restricted to the 2-point ladder this script actually drives.
    return (G.gtop.INL_WARMUP_CONV + G.gtop.INL_CONV_PER_POINT * 2) * G.gtop.CONV_NS


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                  vdd: float) -> tuple[str, dict[int, float]]:
    """The complete ngspice deck plus `{transition: decision_time_ns}`."""
    tag = G.TAG
    lines = [
        f"* extracted-core gain-error measurement -- issue #89 Scope items 3/8",
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
        "* ---- input: the two endpoint transitions gain_err_lsb "
        "extrapolates from ------"
    )
    transitions = [GAIN_LO, GAIN_HI]
    pts: list[str] = []
    tdec_ns: dict[int, float] = {}
    prev = ""
    for idx, k in enumerate(transitions):
        t0 = (G.gtop.INL_WARMUP_CONV + G.gtop.INL_CONV_PER_POINT * idx) * G.gtop.CONV_NS
        lvl = f"{{({k}+0.25)*lsb}}"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
        trial = G.gtop._inl_trial(k)
        tdec_ns[k] = t0 + G.gtop.trial_decision_ns(trial) - 0.05
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
    for k, t_ns in tdec_ns.items():
        lines.append(f"meas tran e{k} FIND v({tag}_err) AT={t_ns:.3f}n")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n", tdec_ns


_MEAS_RE_TMPL = r"\be{k}\s*=\s*([-\d.eE+]+)"


def run(deck: str, workdir: Path) -> tuple[dict[int, float], str]:
    path = workdir / "extracted_core_gain_err.spice"
    path.write_text(deck)
    proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                          text=True, cwd=workdir, timeout=900, check=False)
    out = proc.stdout + "\n" + proc.stderr
    errs: dict[int, float] = {}
    for k in (GAIN_LO, GAIN_HI):
        m = re.search(_MEAS_RE_TMPL.format(k=k), out)
        errs[k] = float(m.group(1)) if m else float("nan")
    return errs, out


def measure_point(top: str, pdk: PDK.Pdk, corner_name: str, temp_c: float,
                   vdd: float, log_dir: Path | None = None,
                   snapshot_path: Path | None = None) -> dict:
    corner = C.CORNERS[corner_name]
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        deck, _ = compose_deck(top, pdk, corner, temp_c, vdd)
        if snapshot_path is not None:
            snapshot_path.write_text(deck)
        errs, log = run(deck, work)
    dt = time.monotonic() - t0
    corner_id = f"{corner_name}_{temp_c:g}c_{vdd:.2f}v"
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{corner_id}.log").write_text(log)
    e_lo, e_hi = errs[GAIN_LO], errs[GAIN_HI]
    gain_err_lsb = (
        float("nan") if (e_lo != e_lo or e_hi != e_hi)
        else (e_hi - e_lo) * (1023.0 / (GAIN_HI - GAIN_LO))
    )
    return {
        "corner_id": corner_id,
        "corner": corner_name,
        "temp_c": temp_c,
        "vdd": vdd,
        f"e{GAIN_LO}_lsb": e_lo,
        f"e{GAIN_HI}_lsb": e_hi,
        "gain_err_lsb": gain_err_lsb,
        "sim_wall_s": round(dt, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP"])
    ap.add_argument("--corners", nargs="+", default=["cdac"],
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
    # de-dup, keep order
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
                print(
                    f"{pt['corner_id']:>20}  e{GAIN_LO}={pt[f'e{GAIN_LO}_lsb']:+.4f}"
                    f"  e{GAIN_HI}={pt[f'e{GAIN_HI}_lsb']:+.4f}"
                    f"  gain_err_lsb={pt['gain_err_lsb']:+.5f}"
                    f"  ({pt['sim_wall_s']:.1f}s)"
                )
    total_s = time.monotonic() - t_all0

    result = {
        "top": args.top,
        "claim": "issue #89 Scope items 3/8: gain_err_lsb of the extracted "
                 "ADC_TOP core (schematic comparator + rung-1 controller + "
                 "DR-0013 input network, extracted CDAC core), same "
                 "endpoint-extrapolation methodology as "
                 "sim/adc-inl-dnl/'s inl_manifest(). NOT the full INL/DNL "
                 "claim (Scope item 1, deferred).",
        "netlist_provenance": "extracted (remediated: PMOS-body->vdd local "
                              "remediation of klayout-tools#555; input rails "
                              "promoted to vinp/vinn) wired to the schematic "
                              "comparator + rung-1 SAR controller + DR-0013 "
                              "input drive network",
        "pdk": pdk.provenance(),
        "gain_lo_transition": GAIN_LO,
        "gain_hi_transition": GAIN_HI,
        "points": points,
        "total_wall_s": round(total_s, 2),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")
    print(f"TOTAL: {len(points)} point(s) in {total_s:.1f}s "
          f"({total_s / max(len(points), 1):.1f}s/point)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
