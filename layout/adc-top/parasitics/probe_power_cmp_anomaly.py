#!/usr/bin/env python3
"""Where does the extra comparator current at `tt_125c_3.63v`, full scale,
actually go? -- diagnostic for the one outlier in the extracted-core power
grid.

The extracted-core power record
`sim/adc-power/records/20260806-093034-c9981fb.md` matches its schematic
baseline (`20260802-141402-1224e11`) on `p_cmp_*` to within ~1 % at **26 of
27** corners and at four of five input levels. At exactly one cell of that
grid -- corner `tt_125c_3.63v`, input level f100 (full scale) -- the
comparator's average supply power reads **224.95 uW against the schematic's
109.38 uW**, a 2.06x jump with no neighbour showing anything (the same corner
reads 106.76 uW at f075 and the adjacent supplies read ~109 uW at f100).

Both records PASS: `tb.json`'s only comparator bound is on `p_cmp_f050_uw`
(20-200 uW), and f050 is unaffected. So nothing in the harness would have
flagged this -- which is exactly why it gets a probe rather than a footnote
(CLAUDE.md: report and escalate, do not absorb).

## What this probe tests, and how it can say "no"

The comparator is a static preamp (10 uA bias by design, DR-0015) plus a
StrongARM latch whose dynamic current is paid per decision. Two mechanisms
would produce a doubled *average* over a 2-conversion window, and they are
distinguishable by WHERE in the window the current sits:

  * **Decision-localised** -- one or a few bit trials resolve slowly (a
    near-boundary residue holding the latch in its high-current regenerative
    phase, or re-triggering it), so the excess concentrates in a handful of
    the 32 bit cycles the window spans and the rest look normal.
  * **Static / bias-shift** -- the preamp's operating point moved (e.g. an
    input common mode pushed toward a rail by the full-scale code), so the
    excess is spread roughly uniformly across all 32 bit cycles.

The probe resolves `i(vddc)` per bit cycle (`CLK_PERIOD_NS`) across the f100
measurement window, with the f075 window measured the same way in the SAME
run as an in-deck control -- and reports the concentration ratio explicitly.
A uniform profile falsifies "decision-localised"; a spiky one falsifies
"bias-shift". It cannot come back "inconclusive by construction".

## The control that decides whether this is a post-layout finding at all

`--core schematic` swaps `gen_adc_top._core()` in for the extracted
`ADC_TOP`, changing nothing else -- the same PWL staircase, the same rails,
the same measurement windows. Without it, "the extracted core does this" and
"this deck does this at this corner on any core" are indistinguishable, and
only the first would be a post-layout finding. **Run both before drawing any
conclusion.**

    python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py
    python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core schematic
    python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py \\
        --corner ss --temp 125 --vdd 3.63 --json out.json

Diagnostic only: it mints no `sim/` record and makes no spec claim. Its
output is cited by `sim/extracted-delta-summary.md` §4.7 as the disposition
of the outlier.
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
from harness import runner as RUN  # noqa: E402

import gen_extracted_core_tb as G  # noqa: E402 (same directory)

NGSPICE = "ngspice"

#: Input levels this probe resolves per bit cycle: the anomalous one and the
#: adjacent one, measured in the same run so the comparison carries no
#: run-to-run variation at all.
PROBE_LEVEL_IDX = [3, 4]  # gtop.PWR_LEVELS[3] = 0.75, [4] = 1.0


def _windows(gtop) -> list[tuple[int, float, float, float]]:
    """`(level_idx, level_frac, window_start_ns, window_end_ns)` per probed
    level -- the SAME windows `gen_adc_top.power_manifest()` averages over
    (`_pwr_level_start_ns(idx) + CONV_NS` to the end of the level), so the
    per-bit-cycle profile below sums back to the record's own `p_cmp_*`.
    """
    out = []
    for idx in PROBE_LEVEL_IDX:
        t0 = gtop._pwr_level_start_ns(idx) + gtop.CONV_NS
        t1 = gtop._pwr_level_start_ns(idx) + gtop.PWR_CONV_PER_LEVEL * gtop.CONV_NS
        out.append((idx, gtop.PWR_LEVELS[idx], t0, t1))
    return out


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                 vdd: float, num_threads: int = 0,
                 core: str = "extracted") -> tuple[str, list[dict]]:
    """The power deck with `i(vddc)` additionally resolved per bit cycle.

    Returns `(deck, probes)`. Every `meas` the real manifest issues for the
    probed levels is reissued verbatim here (so the probe reproduces the
    record's own `p_cmp_*` and cannot be measuring a different window), plus
    one `AVG i(vddc)` per `CLK_PERIOD_NS` bit cycle inside it, plus the
    decoded code at the end of each conversion.
    """
    gtop = G.gtop
    tag = G.TAG
    lines = [
        f"* {core}-core POWER comparator-current probe -- issue #89, diagnostic only",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        "* i(vddc) resolved per bit cycle across the f075 and f100 windows",
        f".param vdd_val={vdd!r}",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    lines += RUN.mim_wrapper_subckts(pdk)
    lines.append(f".temp {temp_c!r}")
    lines.append("")
    lines += gtop._preamble("{vdd_val/1024}")
    lines.append("")

    # --- the SAME five-level PWL staircase gen_adc_top.power_netlist() emits
    lines.append("* ---- input: the power deck's own five-level staircase ----")
    pts: list[str] = []
    prev = "0"
    for idx, f in enumerate(gtop.PWR_LEVELS):
        t0 = gtop._pwr_level_start_ns(idx)
        lvl = f"{{{f!r}*vref}}" if f else "0"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
    pts.append(f"{gtop._pwr_end_ns():.1f}n {prev}")
    lines += gtop.sar._wrap(f"v{tag}inp {tag}_vinp 0 pwl(", [" ".join(pts) + ")"])
    lines.append(f"v{tag}vinn {tag}_vinn 0 dc {{vcm}}")
    lines.append("")

    lines.append(gtop.comparator_block())
    lines.append(gtop.sar.library())
    if core == "schematic":
        lines.append(gtop.library())
        lines += gtop._core(tag, "0")
    else:
        pins, core_text = G.core_pins(top)
        lines.append(core_text)
        lines += G._core_extracted(tag, "0", pins, top)

    probes: list[dict] = []
    meas: list[str] = []
    for lvl_idx, frac, t0, t1 in _windows(gtop):
        name = f"f{int(round(frac * 100)):03d}"
        meas.append(f"meas tran icmp{name} AVG i(vddc) FROM={t0:.1f}n TO={t1:.1f}n")
        n_cycles = int(round((t1 - t0) / gtop.CLK_PERIOD_NS))
        cells = []
        for b in range(n_cycles):
            a0 = t0 + b * gtop.CLK_PERIOD_NS
            a1 = a0 + gtop.CLK_PERIOD_NS
            mn = f"ic{name}b{b:02d}"
            meas.append(f"meas tran {mn} AVG i(vddc) FROM={a0:.3f}n TO={a1:.3f}n")
            # Same bit cycle, the comparator's own input excursion: the
            # per-cycle rails are what connect "this cycle burned the charge"
            # to "and here is what its inputs were doing while it did".
            rail_meas = {}
            for node in (f"{tag}_topp", f"{tag}_topn"):
                short = node.split("_")[-1]
                for fn in ("MIN", "MAX"):
                    rn = f"v{fn[:2].lower()}{name}{short}b{b:02d}"
                    meas.append(
                        f"meas tran {rn} {fn} v({node}) FROM={a0:.3f}n TO={a1:.3f}n"
                    )
                    rail_meas[f"{short}_{fn.lower()}"] = rn
            # The differential the comparator actually sees when the strobe
            # rises in this cycle. `_preamble()` runs `cmpclk` free at the bit
            # rate, so the latch fires in EVERY cycle including the
            # acquisition phases -- and how far the residue is from zero at
            # that instant is what sets how long the latch stays in its
            # high-current regenerative phase.
            t_dec = a0 + gtop.CMP_STROBE_NS + 1.0
            dp = f"vdp{name}b{b:02d}"
            dn = f"vdn{name}b{b:02d}"
            meas.append(f"meas tran {dp} FIND v({tag}_topp) AT={t_dec:.3f}n")
            meas.append(f"meas tran {dn} FIND v({tag}_topn) AT={t_dec:.3f}n")
            cells.append({"bit_cycle": b, "t0_ns": a0, "t1_ns": a1, "meas": mn,
                          "rail_meas": rail_meas, "t_dec_ns": t_dec,
                          "dec_meas": (dp, dn)})
        # decoded code at the end of each conversion in the window
        codes = []
        n_conv = int(round((t1 - t0) / gtop.CONV_NS))
        for c in range(n_conv):
            mn = f"code{name}c{c}"
            t = t0 + (c + 1) * gtop.CONV_NS - 1.0
            meas.append(f"meas tran {mn} FIND v({tag}_code) AT={t:.3f}n")
            codes.append({"conversion": c, "t_ns": t, "meas": mn})
        # Rail excursion of the comparator's own input nodes (= the CDAC top
        # plates) over the window. A comparator drawing hundreds of uA in a
        # single bit cycle while its inputs stay inside the rails is a
        # different mechanism from one whose inputs leave them; measuring both
        # rails on both nodes is what tells those apart, rather than inferring
        # it from the current alone.
        rails = []
        for node in (f"{tag}_topp", f"{tag}_topn"):
            for fn in ("MIN", "MAX"):
                mn = f"{fn.lower()}{name}{node.split('_')[-1]}"
                meas.append(
                    f"meas tran {mn} {fn} v({node}) FROM={t0:.1f}n TO={t1:.1f}n"
                )
                rails.append({"node": node, "fn": fn, "meas": mn})
        probes.append({
            "level_idx": lvl_idx, "level_frac": frac, "name": name,
            "t0_ns": t0, "t1_ns": t1, "window_meas": f"icmp{name}",
            "cells": cells, "codes": codes, "rails": rails,
        })

    lines += ["", ".control", "set numdgt=10", "set noaskquit"]
    if num_threads:
        lines.append(f"set num_threads={num_threads}")
    lines.append(f"tran 1n {gtop._pwr_end_ns() / 1000:.3f}u 0 2n")
    lines += meas
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n", probes


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
                    help="which analog core to profile; run BOTH before drawing "
                         "a conclusion (see the module docstring's control)")
    ap.add_argument("--corner", default="tt")
    ap.add_argument("--temp", type=float, default=125.0)
    ap.add_argument("--vdd", type=float, default=3.63,
                    help="default 3.63 V: the anomalous cell's own corner")
    ap.add_argument("--ngspice-threads", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py).", file=sys.stderr)
        return 0
    pdk = PDK.find_pdk()
    corner = C.CORNERS[args.corner]
    deck, probes = compose_deck(args.top, pdk, corner, args.temp, args.vdd,
                                args.ngspice_threads, args.core)

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        path = work / "power_cmp_probe.spice"
        path.write_text(deck)
        proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                              text=True, cwd=work, timeout=args.timeout,
                              check=False)
        out = proc.stdout + "\n" + proc.stderr
    wall = time.monotonic() - t0

    corner_id = f"{args.corner}_{args.temp:g}c_{args.vdd:.2f}v"
    print(f"core {args.core}   corner {corner_id}   ({wall:.0f}s)")
    print()

    results = []
    for p in probes:
        vddm = args.vdd
        i_win = _meas(out, p["window_meas"])
        cells = [
            {**c, "i_a": _meas(out, c["meas"]),
             "rails_v": {k: _meas(out, v) for k, v in c["rail_meas"].items()},
             "vdiff_at_strobe_v": (_meas(out, c["dec_meas"][0])
                                   - _meas(out, c["dec_meas"][1]))}
            for c in p["cells"]
        ]
        codes = [{**c, "code": _meas(out, c["meas"])} for c in p["codes"]]
        i_abs = [abs(c["i_a"]) for c in cells]
        mean_i = sum(i_abs) / len(i_abs)
        peak_i = max(i_abs)
        # Concentration: what fraction of the window's total charge sits in the
        # top 4 of its 32 bit cycles? Uniform => 4/32 = 12.5 %.
        top4 = sorted(i_abs, reverse=True)[:4]
        conc = sum(top4) / sum(i_abs) if sum(i_abs) else float("nan")
        rails = {r["meas"]: _meas(out, r["meas"]) for r in p["rails"]}
        results.append({
            "level_frac": p["level_frac"], "name": p["name"],
            "p_cmp_uw": abs(i_win) * vddm * 1e6,
            "mean_bitcycle_ua": mean_i * 1e6, "peak_bitcycle_ua": peak_i * 1e6,
            "peak_over_mean": (peak_i / mean_i) if mean_i else float("nan"),
            "top4_charge_fraction": conc,
            "peak_bit_cycle": max(cells, key=lambda c: abs(c["i_a"]))["bit_cycle"],
            "peak_cell_rails_v": max(cells, key=lambda c: abs(c["i_a"]))["rails_v"],
            "peak_cell_vdiff_at_strobe_v": max(
                cells, key=lambda c: abs(c["i_a"]))["vdiff_at_strobe_v"],
            "codes": [c["code"] for c in codes],
            "rails_v": rails,
            "topp_min_v": rails.get(f"min{p['name']}topp"),
            "topp_max_v": rails.get(f"max{p['name']}topp"),
            "topn_min_v": rails.get(f"min{p['name']}topn"),
            "topn_max_v": rails.get(f"max{p['name']}topn"),
            "cells": [{"bit_cycle": c["bit_cycle"], "i_ua": c["i_a"] * 1e6}
                      for c in cells],
        })

    print("| level | p_cmp (uW) | mean i(vddc) per bit cycle (uA) | peak (uA) "
          "| peak/mean | top-4-of-32 charge share | decoded codes |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        codes = ", ".join(f"{c:.0f}" for c in r["codes"])
        print(f"| f{int(round(r['level_frac'] * 100)):03d} | {r['p_cmp_uw']:.3f} "
              f"| {r['mean_bitcycle_ua']:.3f} | {r['peak_bitcycle_ua']:.3f} "
              f"| {r['peak_over_mean']:.2f}x | {r['top4_charge_fraction'] * 100:.1f} % "
              f"| {codes} |")
    print()
    print("Uniform profile => top-4-of-32 share is 12.5 %. A materially larger")
    print("share localises the excess to a few bit trials (decision-limited);")
    print("~12.5 % with an elevated mean is a static/bias shift instead.")
    print()
    print("Bit cycle b spans [b*CLK_PERIOD_NS, (b+1)*CLK_PERIOD_NS) from the")
    print("conversion start. Trial i decides in bit cycle 3+i (i = 1..10), so")
    print("bit cycles 0-3 are the ACQUISITION phases, not bit trials.")
    print()
    print("| level | peak bit cycle | phase | v(topp) in that cycle "
          "| v(topn) in that cycle | v(topp)-v(topn) at that cycle's strobe |")
    print("|---|---|---|---|---|---|")
    for r in results:
        b = r["peak_bit_cycle"]
        ph = b % 16
        phase = f"ph{ph} (acquisition)" if ph <= 3 else f"ph{ph} = trial {ph - 3}"
        rv = r["peak_cell_rails_v"]
        print(f"| f{int(round(r['level_frac'] * 100)):03d} | {b} (= conv "
              f"{b // 16}, {phase}) | {phase} "
              f"| {rv['topp_min']:.4f} .. {rv['topp_max']:.4f} V "
              f"| {rv['topn_min']:.4f} .. {rv['topn_max']:.4f} V "
              f"| {r['peak_cell_vdiff_at_strobe_v'] * 1e6:+.2f} uV |")
    print()
    print("V_cm is vdd/2. A top plate that leaves V_cm during an ACQUISITION")
    print("phase is not converting -- it is failing to be held by DR-0014's")
    print("top-plate V_cm switch while the bottom plates slew to V_in.")
    print()
    for r in results:
        print(f"f{int(round(r['level_frac'] * 100)):03d} per-bit-cycle i(vddc), uA:")
        print("  " + "  ".join(f"{c['i_ua']:.1f}" for c in r["cells"]))

    payload = {
        "diagnostic": "issue #89: where does the 2.06x comparator-power outlier "
                      "at tt_125c_3.63v / f100 in the extracted-core power grid "
                      "(record 20260806-093034-c9981fb) come from?",
        "core": args.core,
        "corner_id": corner_id,
        "pdk": pdk.provenance(),
        "levels": results,
        "wall_s": round(wall, 1),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2) + "\n")
    if any(r["p_cmp_uw"] != r["p_cmp_uw"] for r in results):
        print("error: a measurement did not parse; see the ngspice output.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
