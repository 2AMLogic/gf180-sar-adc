#!/usr/bin/env python3
"""Why does the comparator draw ~2x its usual current at ONE corner, ONE input
level, on the extracted-core power run?

The extracted-core #13 power re-run
(`sim/adc-power/records/20260806-083932-faebccc.md`) is 27/27 PASS, and 26 of
its 27 corners report a comparator supply term (`p_cmp_*`) within a few percent
of the schematic baseline `20260802-141402-1224e11`'s. One cell does not:

    corner tt_125c_3.63v, input level 1.00 x full scale
      schematic  p_cmp_f100_uw = 109.382   (i(vddc) avg ~ -30.1 uA)
      extracted  p_cmp_f100_uw = 224.952   (i(vddc) avg ~ -62.0 uA)

That is a 2.06x jump in a block that is **schematic-level in this wrapper**
(issue #89 Scope item 0 keeps the comparator, the SAR controller and the input
drive network schematic; only the CDAC analog core is extracted), at a single
corner, at a single input level, with no ngspice warning, no convergence
failure and no timeout in the raw log.

Left as a bare number it is unreadable: a reader cannot tell whether it is
(a) the extracted core loading the comparator differently, (b) a
measurement-window artefact of the 2 us `AVG` the manifest takes, or (c) a
simulator artefact of one point. This script separates those, and is built
able to say "not the layout":

1. It composes the SAME power deck at ONE corner against **either** core
   (`--core extracted` / `--core schematic`), changing nothing else -- the
   same control probe_gain_err_settling.py uses, and the reason that
   script's finding was conclusive rather than merely plausible.
2. It reports `i(vddc)` **per conversion** rather than the manifest's 2 us
   two-conversion average, so an excess confined to one conversion is
   distinguishable from a raised baseline across the level.
3. It reports, per conversion, the peak (most negative) `i(vddc)` and the
   decoded output code, so a comparator that is burning current *resolving*
   is distinguishable from one whose bias has shifted.

    python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core extracted
    python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core schematic
    python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py \\
        --corner ff --temp 125 --vdd 3.63 --json out.json

Diagnostic only: it mints no `sim/` record and makes no spec claim. Its output
is cited by `sim/extracted-delta-summary.md` as the reason the outlier is
reported the way it is.
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
sys.path.insert(0, str(HERE))

from harness import corners as C  # noqa: E402
from harness import pdk as PDK  # noqa: E402
from harness import runner as RUN  # noqa: E402

import gen_extracted_core_tb as G  # noqa: E402  (same directory)
import gen_extracted_power_tb as P  # noqa: E402  (same directory)

gtop = G.gtop
NGSPICE = "ngspice"


def n_conversions() -> int:
    """Conversions in the power deck's own schedule -- derived, not retyped."""
    return gtop.PWR_WARMUP_CONV + gtop.PWR_CONV_PER_LEVEL * len(gtop.PWR_LEVELS)


def level_of(conv: int) -> float | None:
    """The input level (fraction of full scale) conversion `conv` runs at.

    `None` for the warm-up conversions, which precede every level.
    """
    if conv < gtop.PWR_WARMUP_CONV:
        return None
    idx = (conv - gtop.PWR_WARMUP_CONV) // gtop.PWR_CONV_PER_LEVEL
    return gtop.PWR_LEVELS[idx] if idx < len(gtop.PWR_LEVELS) else None


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                 vdd: float, num_threads: int = 0,
                 core: str = "extracted") -> str:
    """The #13 power deck at one corner, instrumented per conversion.

    The body is the deck's own generator output -- `gen_adc_top.power_netlist()`
    for the schematic core, `gen_extracted_power_tb.power_netlist_extracted()`
    for the extracted one -- so the stimulus, the supply split and the wiring
    are byte-for-byte what the recorded runs used. Only the `.control` block
    differs from what `sim/run_corners.py` composes: per-conversion `meas`
    windows in place of the manifest's five 2 us level averages.
    """
    lines = [
        f"* {core}-core POWER per-conversion probe -- issue #89, diagnostic only",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        f".param vdd_val={vdd!r}",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    # The schematic core instantiates the `mim_cap_2f0` alias the harness binds
    # per PDK variant; this deck composes its own preamble, so it must bind it
    # too. Reused from the harness rather than restated.
    lines += RUN.mim_wrapper_subckts(pdk)
    lines.append(f".temp {temp_c!r}")
    lines.append("")

    if core == "schematic":
        lines.append(gtop.power_deck())
    else:
        lines.append(P.power_netlist_extracted(top))

    conv = gtop.CONV_NS
    n = n_conversions()
    lines += ["", ".control", "set numdgt=10", "set noaskquit"]
    if num_threads:
        lines.append(f"set num_threads={num_threads}")
    lines.append(f"tran 1n {n * conv / 1000:.3f}u 0 2n")
    for k in range(n):
        t0, t1 = k * conv, (k + 1) * conv
        lines.append(f"meas tran icmp{k:02d} AVG i(vddc) FROM={t0:.1f}n TO={t1:.1f}n")
        # i(vddc) is negative (current OUT of the source), so the largest
        # instantaneous draw is the MINIMUM, not the maximum.
        lines.append(f"meas tran ipk{k:02d} MIN i(vddc) FROM={t0:.1f}n TO={t1:.1f}n")
        lines.append(f"meas tran icdc{k:02d} AVG i(vddd) FROM={t0:.1f}n TO={t1:.1f}n")
        lines.append(f"meas tran code{k:02d} FIND v(se_code) AT={t1 - 5.0:.1f}n")
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n"


def _meas(out: str, name: str) -> float:
    m = re.search(rf"\b{name}\s*=\s*([-\d.eE+]+)", out)
    return float(m.group(1)) if m else float("nan")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP"])
    ap.add_argument("--core", default="extracted",
                    choices=["extracted", "schematic"],
                    help="which analog core the same deck runs against; run "
                         "BOTH before drawing a conclusion (see compose_deck)")
    ap.add_argument("--corner", default="tt")
    ap.add_argument("--temp", type=float, default=125.0)
    ap.add_argument("--vdd", type=float, default=3.63,
                    help="default tt_125c_3.63v: the one corner whose "
                         "p_cmp_f100_uw is the outlier")
    ap.add_argument("--ngspice-threads", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py).", file=sys.stderr)
        return 0
    pdk = PDK.find_pdk()
    corner = C.CORNERS[args.corner]
    deck = compose_deck(args.top, pdk, corner, args.temp, args.vdd,
                        args.ngspice_threads, args.core)

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        path = work / "power_cmp_anomaly.spice"
        path.write_text(deck)
        proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                              text=True, cwd=work, timeout=args.timeout,
                              check=False)
        out = proc.stdout + "\n" + proc.stderr
    wall = time.monotonic() - t0

    rows = []
    for k in range(n_conversions()):
        rows.append({
            "conversion": k,
            "level": level_of(k),
            "i_cmp_avg_ua": _meas(out, f"icmp{k:02d}") * 1e6,
            "i_cmp_peak_ua": _meas(out, f"ipk{k:02d}") * 1e6,
            "i_cdac_avg_ua": _meas(out, f"icdc{k:02d}") * 1e6,
            "code": _meas(out, f"code{k:02d}"),
        })

    corner_id = f"{args.corner}_{args.temp:g}c_{args.vdd:.2f}v"
    print(f"core {args.core}   corner {corner_id}   ({wall:.0f}s)")
    print()
    print("| conversion | input level | i(vddc) avg (uA) | i(vddc) peak (uA) "
          "| i(vddd) avg (uA) | decoded code |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        lvl = "warm-up" if r["level"] is None else f"{r['level']:.2f}"
        print(f"| {r['conversion']} | {lvl} | {r['i_cmp_avg_ua']:+.3f} "
              f"| {r['i_cmp_peak_ua']:+.3f} | {r['i_cdac_avg_ua']:+.3f} "
              f"| {r['code']:.0f} |")
    print()
    print("The manifest's own p_cmp_f<level> averages conversions 2 and 3 of "
          "each level (its 2 us window), so compare the last two rows of a "
          "level, not the first.")

    result = {
        "diagnostic": "issue #89: is the extracted-core power run's 2x "
                      "p_cmp_f100_uw outlier at tt_125c_3.63v a layout "
                      "effect, a measurement-window artefact, or neither?",
        "core": args.core,
        "corner_id": corner_id,
        "pdk": pdk.provenance(),
        "rows": rows,
        "wall_s": round(wall, 1),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")
    if any(r["i_cmp_avg_ua"] != r["i_cmp_avg_ua"] for r in rows):
        print("error: a measurement did not parse; see the ngspice output.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
