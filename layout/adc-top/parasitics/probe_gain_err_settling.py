#!/usr/bin/env python3
"""Why do two extracted-core `gain_err_lsb` measurements disagree by 0.57 LSB?

Two records measure the SAME quantity on the SAME extracted core with the
SAME endpoint-extrapolation formula and disagree:

  * `sim/adc-inl-dnl/records/20260805-163000-e8017f2.md` (issue #89, PR #96,
    `measure_extracted_gain_err.py`) reports **-2.52 to -2.63 LSB**.
  * `sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md` (the full
    18-transition extracted-core re-run) reports **-1.99 to -2.01 LSB**,
    matching the schematic baseline's own -1.99 to -2.01 LSB.

The one structural difference between the two decks is **how transition 1023
is reached**. `measure_extracted_gain_err.py` drives a two-point ladder, so
the input jumps from transition 1 straight to transition 1023 -- a ~1022 LSB,
near-full-scale step -- and reads the error inside that single 1000 ns
conversion. The 18-transition deck always arrives at 1023 from 1022, i.e. by
a 1 LSB increment, after seventeen prior settling conversions.

This script tests that difference directly, and it is a **falsifiable**
test rather than a plausible story: it drives the very same two-point ladder,
then HOLDS the input at transition 1023 for `--hold` further conversions and
reads the same error node at each one's deciding trial. If the disagreement
is a settling artefact of the big step, `e1023` must walk from the
gain-error record's value toward the 18-transition record's value as the hold
lengthens. If instead `e1023` is flat across the hold, the step size is NOT
the explanation and the disagreement is something else -- which the script
will say.

    python3 layout/adc-top/parasitics/probe_gain_err_settling.py
    python3 layout/adc-top/parasitics/probe_gain_err_settling.py \\
        --corner ss --temp 125 --vdd 2.97 --hold 6 --json out.json

Diagnostic only: it mints no `sim/` record and makes no spec claim. Its
output is cited by the delta summary as the reason one of the two
`gain_err_lsb` numbers is preferred.
"""

from __future__ import annotations

import argparse
import json
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
from harness import runner as RUN  # noqa: E402

import gen_extracted_core_tb as G  # noqa: E402 (same directory)
import measure_extracted_gain_err as M  # noqa: E402 (same directory)

NGSPICE = "ngspice"


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                 vdd: float, hold: int, num_threads: int = 0,
                 core: str = "extracted") -> tuple[str, list[float]]:
    """The gain-error deck with transition 1023 held for `hold` conversions.

    Returns `(deck, decision_times_ns)`, one decision time per held
    conversion -- index 0 being exactly the instant
    `measure_extracted_gain_err.py` reads.

    ``core="schematic"`` swaps in `gen_adc_top._core()` -- the very core the
    schematic bench uses -- and changes NOTHING else. That is the control the
    diagnostic needs: without it, "the deck reads an unsettled value one
    conversion after a full-scale step" and "the EXTRACTED core settles more
    slowly than the schematic one" are indistinguishable, and only the second
    would be a post-layout finding.
    """
    gtop = G.gtop
    tag = G.TAG
    lo, hi = M.GAIN_LO, M.GAIN_HI
    conv = gtop.CONV_NS
    # Same schedule as measure_extracted_gain_err.compose_deck: warm-up
    # conversions, transition `lo`, then one conversion later the step to
    # `hi`. Only the tail differs -- `hi` is held instead of ending.
    t_lo = gtop.INL_WARMUP_CONV * conv
    t_hi = (gtop.INL_WARMUP_CONV + gtop.INL_CONV_PER_POINT) * conv
    end_ns = t_hi + hold * conv

    lines = [
        f"* {core}-core gain-error SETTLING probe -- issue #89, diagnostic only",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        f"* transition {hi} held for {hold} conversion(s) after a {hi - lo} LSB step",
    ]
    lines += G.pvt_includes(pdk, corner, vdd)
    # The schematic core instantiates the stable `mim_cap_2f0` alias the
    # harness binds per PDK variant; this deck composes its own preamble, so
    # it has to bind it too. Reused from the harness rather than restated:
    # a second hand-written binding is a second place to get the metal stack
    # wrong.
    lines += RUN.mim_wrapper_subckts(pdk)
    lines.append(G.pvt_temp_line(temp_c))
    lines.append("")
    lines += gtop._preamble("{vdd_val/1024}")
    lines.append("")
    lines.append("* ---- input: transition 1, then a full-scale step to 1023 ----")
    pts = [
        f"0 {{({lo}+0.25)*lsb}}",
        f"{t_hi - 10:.1f}n {{({lo}+0.25)*lsb}}",
        f"{t_hi:.1f}n {{({hi}+0.25)*lsb}}",
        f"{end_ns:.1f}n {{({hi}+0.25)*lsb}}",
    ]
    lines += gtop.sar._wrap(f"v{tag}vinp {tag}_vinp 0 pwl(", [" ".join(pts) + ")"])
    lines.append(f"v{tag}vinn {tag}_vinn 0 dc {{vcm}}")
    lines.append("")

    # Both branches get the same three inlined libraries `gen_adc_top._deck()`
    # appends to every one of its testbenches; only the ARRAY differs.
    lines.append(gtop.comparator_block())
    lines.append(gtop.sar.library())
    if core == "schematic":
        # `gen_adc_top.library()` (the adc_top.spice copy) + `_core()`: the
        # very body `inl_netlist()` emits, including its own ideal shadow DAC
        # and `{tag}_err` node.
        lines.append(gtop.library())
        lines += gtop._core(tag, "0")
    else:
        pins, core_text = G.core_pins(top)
        lines.append(core_text)
        lines += G._core_extracted(tag, "0", pins, top)
        lines += G.shadow_dac_and_error(tag)

    trial_lo = gtop._inl_trial(lo)
    trial_hi = gtop._inl_trial(hi)
    t_dec_lo = t_lo + gtop.trial_decision_ns(trial_lo) - 0.05
    t_dec = [
        t_hi + j * conv + gtop.trial_decision_ns(trial_hi) - 0.05
        for j in range(hold)
    ]

    lines += ["", ".control", "set numdgt=10", "set noaskquit"]
    if num_threads:
        lines.append(f"set num_threads={num_threads}")
    lines.append(f"tran 1n {end_ns / 1000:.3f}u 0 2n")
    lines.append(f"meas tran elo FIND v({tag}_err) AT={t_dec_lo:.3f}n")
    for j, t in enumerate(t_dec):
        lines.append(f"meas tran ehi{j} FIND v({tag}_err) AT={t:.3f}n")
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n", t_dec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP"])
    ap.add_argument("--core", default="extracted",
                    choices=["extracted", "schematic"],
                    help="which analog core to hold the step against; run BOTH "
                         "before drawing a conclusion (see compose_deck)")
    ap.add_argument("--corner", default="tt")
    ap.add_argument("--temp", type=float, default=27.0)
    ap.add_argument("--vdd", type=float, default=2.97,
                    help="default 2.97 V: the corner both records quote in "
                         "their own worked comparison")
    ap.add_argument("--hold", type=int, default=8,
                    help="conversions to hold transition 1023 after the step")
    ap.add_argument("--ngspice-threads", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py).", file=sys.stderr)
        return 0
    pdk = PDK.find_pdk()
    corner = C.CORNERS[args.corner]
    deck, t_dec = compose_deck(args.top, pdk, corner, args.temp, args.vdd,
                               args.hold, args.ngspice_threads, args.core)

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        path = work / "gain_err_settling.spice"
        path.write_text(deck)
        proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                              text=True, cwd=work, timeout=args.timeout,
                              check=False)
        out = proc.stdout + "\n" + proc.stderr
    wall = time.monotonic() - t0

    e_lo = G.meas(out, "elo")
    rows = []
    for j in range(args.hold):
        e_hi = G.meas(out, f"ehi{j}")
        gain = (e_hi - e_lo) * (1023.0 / (M.GAIN_HI - M.GAIN_LO))
        rows.append({"conversions_after_step": j + 1, "t_ns": t_dec[j],
                     "e1023_lsb": e_hi, "gain_err_lsb": gain})

    corner_id = f"{args.corner}_{args.temp:g}c_{args.vdd:.2f}v"
    print(f"core {args.core}   corner {corner_id}   "
          f"e1_lsb = {e_lo:+.4f}   ({wall:.0f}s)")
    print()
    print("| conversions held after the 1022 LSB step | e1023_lsb | gain_err_lsb |")
    print("|---|---|---|")
    for r in rows:
        print(f"| {r['conversions_after_step']} | {r['e1023_lsb']:+.4f} "
              f"| {r['gain_err_lsb']:+.4f} |")
    print()
    print("Reference values at this corner:")
    print("  measure_extracted_gain_err.py (1 conversion after the step) : "
          "see row 1")
    print("  18-transition extracted-core re-run (1 LSB increment)       : "
          "sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md")

    result = {
        "diagnostic": "issue #89: is the 0.57 LSB gain_err_lsb disagreement "
                      "between the two extracted-core records a settling "
                      "artefact of the two-point deck's ~1022 LSB step?",
        "core": args.core,
        "corner_id": corner_id,
        "pdk": pdk.provenance(),
        "e1_lsb": e_lo,
        "hold_conversions": args.hold,
        "rows": rows,
        "wall_s": round(wall, 1),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")
    if any(r["e1023_lsb"] != r["e1023_lsb"] for r in rows):
        print("error: a measurement did not parse; see the ngspice output.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
