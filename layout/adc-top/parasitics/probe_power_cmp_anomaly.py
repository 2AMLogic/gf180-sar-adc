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

issue #107 EXTENDS this with the two instruments the diagnostic record
`20260806-power-cmp-anomaly.md` named as missing (its own "What this record
does NOT establish" section): the *device-level* mechanism needs finer
granularity than "one number per 1000 ns conversion" gives.

4. `--waveform` dumps `v(se_topp)`, `v(se_topn)`, `v(se_cmp)` and `i(vddc)`
   at the simulator's own adaptive time points (`wrdata`, no interpolation)
   and, in Python, buckets them onto the deck's own bit-cycle grid
   (`gtop.CLK_PERIOD_NS` = 62.5 ns, 16 bit cycles/conversion; the comparator
   strobe is the back half of each, `gtop.CMP_STROBE_NS` = 31.25 ns -- see
   `design/adc-top/gen_adc_top.py::_preamble()`). Per bit cycle it reports:
     - **per-strobe comparator-output transition count**: how many times
       `v(se_cmp)` crosses `vdd/2` while the strobe is high -- a latch that
       resolves cleanly crosses once (or zero times, if the decision does
       not change); a latch trying and failing to resolve can sit near the
       threshold and show extra crossings or none inside the window.
     - the **top-plate differential and common-mode voltage** at the
       decision instant (the last sample before the strobe drops), i.e.
       `v(se_topp)-v(se_topn)` and `(v(se_topp)+v(se_topn))/2`.
     - the bit cycle's own peak (most negative) `i(vddc)`, so the SAME
       instrument that separates "one conversion" from "the whole level"
       above can separate "one bit cycle" from "the whole conversion".
   This is per-bit-cycle-instant Python bucketing, not new `.measure`
   statements -- `.measure ... WHEN ... CROSS=n` has no window upper bound
   in ngspice's classic syntax, so it cannot be scoped to one 62.5 ns bit
   cycle without risking a crossing several cycles later being misattributed
   to this one. A `wrdata` dump carries the simulator's own time points, so
   the bucketing is exact.
5. `--levels` overrides the deck's five-point staircase
   (`gtop.PWR_LEVELS = [0, 0.25, 0.5, 0.75, 1.0]`) with an arbitrary list of
   fractions of full scale (monkeypatching `gtop.PWR_LEVELS` for the
   duration of composition AND parsing, since `n_conversions()` /
   `level_of()` / `_pwr_level_start_ns()` all read it at call time) -- this
   is how issue #107's corner-sweep bound is produced: a fine staircase of
   levels approaching 1.0 instead of the five widely-spaced ones the power
   deck itself needs.

Diagnostic only: it mints no `sim/` record and makes no spec claim. Its output
is cited by `sim/extracted-delta-summary.md` as the reason the outlier is
reported the way it is, and by
`layout/adc-top/parasitics/records/20260806-power-cmp-anomaly.md` and its
issue-#107 successor record.
"""

from __future__ import annotations

import argparse
import contextlib
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
TAG = "se"  # matches gen_adc_top.power_netlist() / gen_extracted_power_tb.py
WAVEFILE = "cmp_wave.txt"
#: v(...)/i(...) traced by --waveform, in the order wrdata writes their
#: (time, value) column pairs -- see _read_wrdata().
WAVE_VARS = (f"v({TAG}_cmp)", f"v({TAG}_topp)", f"v({TAG}_topn)", "v(cmpclk)",
             "i(vddc)")


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


def n_bitcycles() -> int:
    """Comparator strobes per conversion -- CONV_NS / CLK_PERIOD_NS, 16 today."""
    n = gtop.CONV_NS / gtop.CLK_PERIOD_NS
    assert n == int(n), f"CONV_NS not an integer multiple of CLK_PERIOD_NS: {n}"
    return int(n)


@contextlib.contextmanager
def _levels_override(levels: list[float] | None):
    """Temporarily monkeypatch `gtop.PWR_LEVELS` for a fine, custom sweep.

    `gtop` is the SAME module object `gen_extracted_power_tb.py` imported as
    `G.gtop`, and every function that shapes the staircase
    (`n_conversions`/`level_of` above, `gtop._pwr_level_start_ns`,
    `gtop._pwr_end_ns`, and the deck bodies `gtop.power_deck()` /
    `P.power_netlist_extracted()` themselves) reads `gtop.PWR_LEVELS` at
    CALL time, not at import time -- so patching it here reshapes the
    staircase for both cores identically, and restoring it after leaves
    every other TARGET `design/adc-top/gen_adc_top.py` guards untouched.
    `None` is a no-op: default behaviour (the five ratified levels) is
    byte-for-byte what this script produced before issue #107.
    """
    if levels is None:
        yield
        return
    orig = gtop.PWR_LEVELS
    gtop.PWR_LEVELS = tuple(levels)
    try:
        yield
    finally:
        gtop.PWR_LEVELS = orig


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                 vdd: float, num_threads: int = 0,
                 core: str = "extracted", waveform: bool = False) -> str:
    """The #13 power deck at one corner, instrumented per conversion.

    The body is the deck's own generator output -- `gen_adc_top.power_netlist()`
    for the schematic core, `gen_extracted_power_tb.power_netlist_extracted()`
    for the extracted one -- so the stimulus, the supply split and the wiring
    are byte-for-byte what the recorded runs used. Only the `.control` block
    differs from what `sim/run_corners.py` composes: per-conversion `meas`
    windows in place of the manifest's five 2 us level averages, and (with
    `waveform=True`) a `wrdata` dump issue #107's bit-cycle-level analysis
    reads back in `main()`.
    """
    lines = [
        f"* {core}-core POWER per-conversion probe -- issue #89/#107, diagnostic only",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
    ]
    lines += G.pvt_includes(pdk, corner, vdd)
    # The schematic core instantiates the `mim_cap_2f0` alias the harness binds
    # per PDK variant; this deck composes its own preamble, so it must bind it
    # too. Reused from the harness rather than restated.
    lines += RUN.mim_wrapper_subckts(pdk)
    lines.append(G.pvt_temp_line(temp_c))
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
    if waveform:
        lines.append(f"wrdata {WAVEFILE} {' '.join(WAVE_VARS)}")
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n"


def _meas(out: str, name: str) -> float:
    m = re.search(rf"\b{name}\s*=\s*([-\d.eE+]+)", out)
    return float(m.group(1)) if m else float("nan")


def _read_wrdata(path: Path, nvars: int) -> list[list[float]]:
    """Parse ngspice `wrdata`'s (time, value) x N column layout.

    Each of the `nvars` traced quantities gets its OWN (time, value) column
    pair -- see the module docstring's item 4 -- but they share one
    simulator time base, so column `2*i` (`i` = 0..nvars-1) is redundant
    with column 0 to within float rounding. This keeps only column 0 as the
    time and columns `1, 3, 5, ...` as the values, in `WAVE_VARS` order.
    """
    rows: list[list[float]] = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 2 * nvars:
            continue  # blank / short line at EOF
        vals = [float(x) for x in parts]
        t = vals[0]
        row = [t] + [vals[2 * i + 1] for i in range(nvars)]
        rows.append(row)
    return rows


def bitcycle_rows(wave: list[list[float]], vdd: float) -> list[dict]:
    """Bucket a `_read_wrdata` waveform onto the deck's bit-cycle grid.

    One row per (conversion, bit cycle) that the waveform actually covers --
    NOT one row per `n_conversions() * n_bitcycles()`, so a `--waveform-conv`
    subset (fewer conversions simulated, e.g. issue #107's sweep decks) does
    not silently pad the table with empty buckets.
    """
    vth = vdd / 2.0
    conv_ns = gtop.CONV_NS
    bit_ns = gtop.CLK_PERIOD_NS
    strobe_ns = gtop.CMP_STROBE_NS
    nb = n_bitcycles()

    n_conv = n_conversions()
    buckets: dict[tuple[int, int], list[list[float]]] = {}
    for row in wave:
        t = row[0] * 1e9  # s -> ns, matches gtop's own ns-scale constants
        conv = int(t // conv_ns)
        if conv >= n_conv:
            continue  # the tran's own final timepoint, one tick past the
                      # last scheduled conversion -- not a real bit cycle
        local = t - conv * conv_ns
        bit = int(local // bit_ns)
        if bit >= nb:
            bit = nb - 1  # last sample can land exactly on the boundary
        buckets.setdefault((conv, bit), []).append(row)

    out: list[dict] = []
    for (conv, bit) in sorted(buckets):
        samples = buckets[(conv, bit)]
        bit_t0 = conv * conv_ns + bit * bit_ns
        strobe_t0 = bit_t0 + strobe_ns
        strobe = [s for s in samples if s[0] * 1e9 >= strobe_t0]
        # WAVE_VARS order: cmp, topp, topn, cmpclk, i(vddc) -> columns 1..5
        transitions = 0
        prev_hi = None
        for s in strobe:
            hi = s[1] > vth
            if prev_hi is not None and hi != prev_hi:
                transitions += 1
            prev_hi = hi
        if strobe:
            last = strobe[-1]
            diff_mv = (last[2] - last[3]) * 1000.0
            cm_mv = (last[2] + last[3]) / 2.0 * 1000.0
        else:
            diff_mv = cm_mv = float("nan")
        peak_ua = min((s[5] for s in samples), default=float("nan")) * 1e6
        out.append({
            "conversion": conv,
            "bitcycle": bit,
            "level": level_of(conv),
            "n_strobe_samples": len(strobe),
            "cmp_transitions": transitions,
            "topp_topn_diff_mv": diff_mv,
            "topp_topn_cm_mv": cm_mv,
            "i_vddc_peak_ua": peak_ua,
        })
    return out


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
    ap.add_argument("--waveform", action="store_true",
                    help="issue #107: dump v(se_topp)/v(se_topn)/v(se_cmp)/"
                         "i(vddc) and report per-bit-cycle comparator-output "
                         "transition counts + top-plate differential/common "
                         "mode at each decision instant. Off by default -- "
                         "the base per-conversion table is unchanged from "
                         "issue #89's probe, so a --waveform-less run stays "
                         "a byte-for-byte reproduction check.")
    ap.add_argument("--waveform-level", type=float, default=None,
                    help="which input level's bit-cycle rows to print to "
                         "stdout (all levels are still in --json); default "
                         "the deck's highest level (full scale)")
    ap.add_argument("--levels", default=None,
                    help="issue #107 Acceptance Criteria item 2: comma-"
                         "separated fractions of full scale, OVERRIDING the "
                         "power deck's own 5-point staircase for a fine "
                         "sweep around the top code, e.g. "
                         "'0.990,0.995,0.998,1.000'. Default: unchanged "
                         "(the ratified 5-point staircase).")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py).", file=sys.stderr)
        return 0
    pdk = PDK.find_pdk()
    corner = C.CORNERS[args.corner]
    levels = ([float(x) for x in args.levels.split(",")]
              if args.levels else None)

    with _levels_override(levels):
        deck = compose_deck(args.top, pdk, corner, args.temp, args.vdd,
                            args.ngspice_threads, args.core, args.waveform)

        t0 = time.monotonic()
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            path = work / "power_cmp_anomaly.spice"
            path.write_text(deck)
            proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                                  text=True, cwd=work, timeout=args.timeout,
                                  check=False)
            out = proc.stdout + "\n" + proc.stderr
            wave_path = work / WAVEFILE
            wave_rows = (_read_wrdata(wave_path, len(WAVE_VARS))
                        if args.waveform and wave_path.is_file() else [])
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

        bc_rows = bitcycle_rows(wave_rows, args.vdd) if wave_rows else []
        levels_now = list(gtop.PWR_LEVELS)

    corner_id = f"{args.corner}_{args.temp:g}c_{args.vdd:.2f}v"
    print(f"core {args.core}   corner {corner_id}   ({wall:.0f}s)")
    print()
    print("| conversion | input level | i(vddc) avg (uA) | i(vddc) peak (uA) "
          "| i(vddd) avg (uA) | decoded code |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        lvl = "warm-up" if r["level"] is None else f"{r['level']:.4f}"
        print(f"| {r['conversion']} | {lvl} | {r['i_cmp_avg_ua']:+.3f} "
              f"| {r['i_cmp_peak_ua']:+.3f} | {r['i_cdac_avg_ua']:+.3f} "
              f"| {r['code']:.0f} |")
    print()
    print("The manifest's own p_cmp_f<level> averages conversions 2 and 3 of "
          "each level (its 2 us window), so compare the last two rows of a "
          "level, not the first.")

    if bc_rows:
        target_level = (args.waveform_level if args.waveform_level is not None
                        else levels_now[-1])
        print()
        print(f"-- issue #107: per-bit-cycle detail, input level "
              f"{target_level:.4f} (all levels are in --json) --")
        print("| conversion | bit cycle | strobe samples | cmp transitions "
              "| topp-topn diff (mV) | topp/topn CM (mV) | i(vddc) peak (uA) |")
        print("|---|---|---|---|---|---|---|")
        for r in bc_rows:
            if r["level"] is None or abs(r["level"] - target_level) > 1e-9:
                continue
            print(f"| {r['conversion']} | {r['bitcycle']} "
                  f"| {r['n_strobe_samples']} | {r['cmp_transitions']} "
                  f"| {r['topp_topn_diff_mv']:+.4f} "
                  f"| {r['topp_topn_cm_mv']:+.4f} "
                  f"| {r['i_vddc_peak_ua']:+.3f} |")

    result = {
        "diagnostic": "issue #89/#107: is the extracted-core power run's 2x "
                      "p_cmp_f100_uw outlier at tt_125c_3.63v a layout "
                      "effect, a measurement-window artefact, or neither -- "
                      "and if attributable to the core, what is the "
                      "device-level mechanism?",
        "core": args.core,
        "corner_id": corner_id,
        "pdk": pdk.provenance(),
        "levels": levels_now,
        "rows": rows,
        "bitcycle_rows": bc_rows,
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
