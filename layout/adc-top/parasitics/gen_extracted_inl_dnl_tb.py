#!/usr/bin/env python3
"""The #13 static-linearity (INL/DNL) testbench, wired against the
PMOS-body-remediated, MiM-mapped **extracted** `ADC_TOP` core -- issue #89
**Scope item 1** (the static-linearity slice of it; ENOB/FFT and power are
separate decks, still deferred -- see this module's own docstring "What
this does NOT do" below).

    python3 layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py --check

Writes ONE file:

    sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice

into the SAME experiment directory as the schematic-level deck
(`sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice`), per sim/README.md
"Extracted vs schematic semantics": "a post-layout extracted re-run of an
existing claim lives in the *same* experiment directory ... The extracted
record appends alongside the schematic record". It deliberately does NOT
write a second `tb.json` -- see "Why reuse the schematic manifest" below.

## Why reuse the schematic manifest, not hand-duplicate it

`design/adc-top/gen_adc_top.py`'s `inl_netlist()`/`_core()` build the input
ladder AND an ideal shadow DAC (behavioural B-sources driven by the
controller's own switch-driver output nets) that computes an input-referred
error at every one of the 18 probed transitions, all tagged `se_*`. The
measure/check expressions that read that shadow DAC
(`sim/adc-inl-dnl/testbench/tb.json`'s `analyses`/`measure`/`checks`) are
themselves tag-`se`-specific text (`v(se_err)`, `v(se_code)`, ...), not a
template -- so the only way to get an EXACT, transcription-error-free reuse
of that measurement methodology against a different analog core is to make
the alternate core's conversion chain use the exact same `se_*` net names.

`gen_extracted_core_tb.py`'s `_core_extracted(tag, mode, pins, top)` and
`_wire_pin(pin, tag)` are already tag-parametrised (built for exactly this
kind of reuse, not just its own `TAG = "ex"` smoke-test constant) -- calling
them with `tag="se"` produces a wired extracted core whose controller ports,
input-drive-network nodes, and comparator inputs are named IDENTICALLY to
`_core("se", "0")`'s schematic ones. This module adds the one piece
`gen_extracted_core_tb.py` deliberately omits (its own docstring: "the
shadow DAC is not needed" for its narrower liveness claim) -- the ideal
shadow DAC and error/code nodes, replicated verbatim from `_core()`'s own
"ideal shadow" section (same formulas, same tag parametrisation, same
`WEIGHTS`) -- and the same 18-transition input ladder `inl_netlist()`
drives it with.

The result: `sim/run_corners.py adc-inl-dnl --netlist
<this file's output> --netlist-provenance 'extracted (...)'` runs the
UNMODIFIED `sim/adc-inl-dnl/testbench/tb.json` manifest -- same claim, same
analyses, same measure expressions, same checks (INL < 1 LSB, DNL < 1 LSB,
gain_err_lsb, no spec relaxation per CLAUDE.md) -- against this file instead
of the schematic one. Any INL/DNL/gain_err_lsb delta between the two runs is
therefore a delta in the ANALOG CORE ALONE, not an artefact of two
independently-written measurement decks silently drifting apart.

## What this does NOT do

- Does not touch `sim/adc-inl-dnl/testbench/tb.json` or
  `tb_adc_inl_dnl.spice` (the schematic deck) -- append-only, per
  sim/README.md.
- Does not modify `design/adc-top/gen_adc_top.py` (same rationale
  `gen_extracted_core_tb.py`'s own docstring gives: its `TARGETS` are
  byte-for-byte guarded by `sim/tests/test_adc_top_netlist.py`).
- Does not re-run the #13 ENOB/FFT or power decks against the extracted
  core, or the #14 Monte Carlo re-run -- those are separate, still-deferred
  slices of issue #89's Scope items 1-2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import gen_extracted_core_tb as G  # noqa: E402  (same directory)

gtop = G.gtop  # design/adc-top/gen_adc_top.py, already imported by G

TAG = "se"  # matches the schematic deck's tag exactly -- see module docstring
OUT_PATH = (
    REPO / "sim" / "adc-inl-dnl" / "testbench" / "tb_adc_inl_dnl_extracted.spice"
)


def _shadow_dac_lines(tag: str) -> list[str]:
    """The ideal shadow DAC + error/code nodes, replicated from
    `design/adc-top/gen_adc_top.py`'s `_core()` "ideal shadow" section
    verbatim (same formulas, same `WEIGHTS`) -- NOT re-derived here. See
    that function for the full derivation and rationale; this is
    deliberately a byte-for-byte port so the two decks measure the same
    quantity the same way.
    """
    L: list[str] = []
    a = L.append
    a("* ---- the ideal shadow (ported from gen_adc_top.py._core()) --------")
    a("* Ported, not re-derived: the reference this deck measures against is")
    a("* the exact charge-domain result of the decisions the REAL converter")
    a("* (the extracted core below) just made, computed from the")
    a("* controller's own switch-driver outputs -- identical to the")
    a("* schematic deck's shadow DAC, so the two runs' terr/INL/DNL/gain_err")
    a("* numbers are directly comparable.")
    for s in ("p", "n"):
        terms = [
            f"{w}*((v({tag}_rel_n_{w}{s})*vcm+v({tag}_sel_hi_n_{w}{s})*vref"
            f"+v({tag}_sel_in_n)*v({tag}_vin{s}))/vdd_val-vcm)"
            for w in gtop.WEIGHTS
        ]
        L += gtop.sar._wrap(
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
    a("* Decoded output code: NOT redefined here -- _core_extracted() (called")
    a("* before this function, same tag) already emits `b{tag}code`, and a")
    a("* second B-source on the same node is an ngspice 'device already")
    a("* exists' error, not a harmless override.")
    return L


def inl_netlist_extracted(top: str = "ADC_TOP") -> str:
    """The extracted-core counterpart of `gen_adc_top.inl_netlist()`.

    Same 18-transition input ladder (`INL_TRANSITIONS`, `INL_WARMUP_CONV`,
    `INL_CONV_PER_POINT`, `CONV_NS` -- all imported from `gtop`, not
    retyped), the extracted core wired by `gen_extracted_core_tb._core_extracted`
    in place of `_core()`'s two `adc_cdac_side` instances, and the ideal
    shadow DAC above.
    """
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_inl_dnl_extracted -- static linearity of the extracted,")
    a("* PMOS-body-remediated, MiM-mapped ADC_TOP core over the PVT grid")
    a("* (issue #89 Scope item 1). GENERATED by")
    a("* layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py -- do not edit.")
    a("*")
    a("* Reuses sim/adc-inl-dnl/testbench/tb.json UNMODIFIED (via")
    a("* `run_corners.py --netlist ... --netlist-provenance extracted`): the")
    a("* input ladder and the ideal-shadow-DAC error/code nodes are byte-for-")
    a("* byte ports of design/adc-top/gen_adc_top.py's inl_netlist()/_core(),")
    a("* tagged `se_*` to match that manifest's measure/check expressions")
    a("* exactly. The ONLY thing that differs from the schematic deck is the")
    a("* analog core itself: one extracted ADC_TOP instance (both CDAC array")
    a("* sides + the per-side top-plate V_cm switch, PMOS-body-remediated to")
    a("* vdd, MiM-mapped to the native PDK subckt) in place of two")
    a("* adc_cdac_side instances + two adc_tp_sw instances. Comparator and")
    a("* rung-1 controller stay schematic-level (issue #89 Scope item 0).")
    a("* See gen_extracted_inl_dnl_tb.py's module docstring for the full")
    a("* rationale.")
    a("* ==================================================================")
    a("")
    L += G.saved_vectors_lines(gtop.inl_manifest())
    a("")
    L += gtop._preamble("{vdd_val/1024}")
    a("")
    a("* ---- input: piecewise-constant ladder of probed transitions -------")
    a("* Identical to gen_adc_top.inl_netlist() -- same INL_TRANSITIONS,")
    a("* same schedule, same tag.")
    pts: list[str] = []
    prev = ""
    for idx, k in enumerate(gtop.INL_TRANSITIONS):
        t0 = (gtop.INL_WARMUP_CONV + gtop.INL_CONV_PER_POINT * idx) * gtop.CONV_NS
        lvl = f"{{({k}+0.25)*lsb}}"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
    pts.append(f"{gtop._inl_end_ns():.1f}n {prev}")
    L += gtop.sar._wrap(f"v{TAG}vinp {TAG}_vinp 0 pwl(", [" ".join(pts) + ")"])
    a(f"v{TAG}vinn {TAG}_vinn 0 dc {{vcm}}")
    a("")

    pins, core_text = G.core_pins(top)
    a("* ---- library: comparator + SAR controller + extracted core -------")
    L.append(gtop.comparator_block())
    L.append(gtop.sar.library())
    L.append(core_text)
    a("")
    L += G._core_extracted(TAG, "0", pins, top)
    a("")
    L += _shadow_dac_lines(TAG)
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    ap.add_argument(
        "--top", default="ADC_TOP", choices=["ADC_TOP"],
        help="ADC_TOP only -- see gen_extracted_core_tb.py's --top help",
    )
    ap.add_argument("--stdout", action="store_true", help="write to stdout instead")
    args = ap.parse_args(argv)

    text = inl_netlist_extracted(args.top)
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if args.check:
        if not OUT_PATH.is_file() or OUT_PATH.read_text() != text:
            print(f"STALE: {OUT_PATH.relative_to(REPO)}", file=sys.stderr)
            return 1
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.is_file() and OUT_PATH.read_text() == text:
        print(f"  unchanged  {OUT_PATH.relative_to(REPO)}")
        return 0
    OUT_PATH.write_text(text)
    print(f"  wrote      {OUT_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
