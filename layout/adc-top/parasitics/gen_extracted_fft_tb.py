#!/usr/bin/env python3
"""The #13 dynamic-performance (coherent-sampling FFT) testbench, wired
against the PMOS-body-remediated, MiM-mapped **extracted** `ADC_TOP` core --
issue #89 Scope item 1 / delta-summary SS6.1 (ENOB/SFDR/THD, the last
un-ported #13 spec-line deck; power is separate and does not port
mechanically -- see `sim/extracted-delta-summary.md` SS6.2).

    python3 layout/adc-top/parasitics/gen_extracted_fft_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_fft_tb.py --check

Writes ONE file:

    sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice

into the SAME experiment directory as the schematic-level deck
(`sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice`), per sim/README.md
"Extracted vs schematic semantics": "a post-layout extracted re-run of an
existing claim lives in the *same* experiment directory ... The extracted
record appends alongside the schematic record". It deliberately does NOT
write a second `tb.json` -- same rationale `gen_extracted_inl_dnl_tb.py`
gives ("Why reuse the schematic manifest", below, ported verbatim).

## Why reuse the schematic manifest, not hand-duplicate it

`design/adc-top/gen_adc_top.py`'s `fft_netlist()` drives `_core("se", "0")`
with a coherently-sampled sine and reads the decoded output code
(`se_code`) plus the gated input-referred decision-error node (`se_aerrh`)
that `_core()`'s own "ideal shadow" section computes. `sim/adc-enob-fft/
testbench/tb.json`'s `analyses`/`measure`/`checks` are themselves tag-`se`-
specific text (`v(se_code)`, `v(se_aerrh)`, `v(vrefn)`, ...), not a template
-- so the only way to reuse that measurement methodology EXACTLY against a
different analog core is to make the alternate core's conversion chain use
the same `se_*` net names.

`gen_extracted_core_tb.py`'s `_core_extracted(tag, mode, pins, top)` is
already tag-parametrised for exactly this kind of reuse (built by
`gen_extracted_inl_dnl_tb.py`, PR #97), and its sibling
`shadow_dac_and_error(tag, gated=True)` emits the ideal shadow DAC, the
input-referred error node (`{tag}_err`) AND the strobe-gated `|err|` node
(`{tag}_aerrh`) this FFT manifest's `decerr_c*_lsb` measurements read --
the one piece `_core_extracted()` itself deliberately omits (its own
docstring: "a smoke test does not need it"). Calling both with `tag="se"`
produces a wired extracted core whose controller ports, input-drive-network
nodes, decoded code and gated error node are named IDENTICALLY to
`_core("se", "0")`'s schematic ones.

Unlike `gen_extracted_inl_dnl_tb.py`, this module does NOT carry its own
copy of the shadow-DAC formula: `gen_extracted_core_tb.shadow_dac_and_error`
already exists and is reused directly (that module's own docstring records
*why* the INL/DNL deck still carries a separate copy -- fixture-pinning
inertia predating this module's `gated=True` option -- and states plainly
that a new caller should call the shared emitter rather than add a third
copy of the formula. This is that new caller).

The result: `sim/run_corners.py adc-enob-fft --netlist <this file's output>
--netlist-provenance 'extracted (...)'` runs the UNMODIFIED
`sim/adc-enob-fft/testbench/tb.json` manifest -- same claim, same coherent-
sampling stimulus, same measure expressions, same checks -- against this
file instead of the schematic one. Any ENOB/SFDR/THD delta between the two
runs (computed downstream by `sim/adc-enob-fft/testbench/analyze_fft.py`
over each run's own raw per-corner logs) is therefore a delta in the ANALOG
CORE ALONE, not an artefact of two independently-written measurement decks
silently drifting apart.

## What this does NOT do

- Does not touch `sim/adc-enob-fft/testbench/tb.json` or
  `tb_adc_enob_fft.spice` (the schematic deck) -- append-only, per
  sim/README.md.
- Does not modify `design/adc-top/gen_adc_top.py` (same rationale
  `gen_extracted_core_tb.py`'s own docstring gives: its `TARGETS` are
  byte-for-byte guarded by `sim/tests/test_adc_top_netlist.py`).
- Does not run `analyze_fft.py` or compute ENOB/SFDR/THD itself -- those are
  computed from the raw per-corner logs this deck's run produces, the same
  post-processing step the schematic record uses, so no number is
  transcribed by hand.
- Does not re-run the #13 power deck against the extracted core, or the #14
  Monte Carlo re-run against this deck -- see `sim/extracted-delta-
  summary.md` SS6.2/SS5 for those.
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
    REPO / "sim" / "adc-enob-fft" / "testbench" / "tb_adc_enob_fft_extracted.spice"
)


def fft_netlist_extracted(top: str = "ADC_TOP") -> str:
    """The extracted-core counterpart of `gen_adc_top.fft_netlist()`.

    Same coherent-sampling sine (`FFT_N`, `FFT_CYCLES`, `FFT_AMP_FRAC`,
    `FFT_WARMUP_CONV`, `CONV_NS` -- all imported from `gtop`, not retyped),
    the extracted core wired by `gen_extracted_core_tb._core_extracted` in
    place of `_core()`'s two `adc_cdac_side` instances, and the same ideal
    shadow DAC / gated error node `_core()` itself emits internally.
    """
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_enob_fft_extracted -- dynamic performance (coherently")
    a("* sampled FFT) of the extracted, PMOS-body-remediated, MiM-mapped")
    a("* ADC_TOP core over the PVT grid (issue #89, delta-summary SS6.1).")
    a("* GENERATED by layout/adc-top/parasitics/gen_extracted_fft_tb.py --")
    a("* do not edit.")
    a("*")
    a("* Reuses sim/adc-enob-fft/testbench/tb.json UNMODIFIED (via")
    a("* `run_corners.py --netlist ... --netlist-provenance extracted`): the")
    a("* coherent-sampling sine and the ideal-shadow-DAC error/code nodes")
    a("* are byte-for-byte ports of design/adc-top/gen_adc_top.py's")
    a("* fft_netlist()/_core(), tagged `se_*` to match that manifest's")
    a("* measure/check expressions exactly. The ONLY thing that differs")
    a("* from the schematic deck is the analog core itself: one extracted")
    a("* ADC_TOP instance (both CDAC array sides + the per-side top-plate")
    a("* V_cm switch, PMOS-body-remediated to vdd, MiM-mapped to the native")
    a("* PDK subckt) in place of two adc_cdac_side instances + two")
    a("* adc_tp_sw instances. Comparator and rung-1 controller stay")
    a("* schematic-level (issue #89 Scope item 0). See")
    a("* gen_extracted_fft_tb.py's module docstring for the full rationale.")
    a("* ==================================================================")
    a("")
    L += gtop._preamble("{vdd_val/1024}")
    a("")
    a("* ---- near-full-scale sine -------------------------------------")
    a("* Identical to gen_adc_top.fft_netlist() -- same FFT_N/FFT_CYCLES")
    a("* coherent-sampling pair, same FFT_AMP_FRAC backoff, same tag.")
    a(
        f"vsein {TAG}_vinp 0 sin({{vcm}} {{vref/2*{gtop.FFT_AMP_FRAC}}}"
        f" {gtop.fft_input_hz():.6f}"
        f" {gtop.FFT_WARMUP_CONV * gtop.CONV_NS / 1e9:.9f} 0 0)"
    )
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
    L += G.shadow_dac_and_error(TAG, gated=True)
    a("")
    a("* Sample-and-hold on the output code, opened at the end of each")
    a("* conversion's drdy phase -- ported verbatim from fft_netlist();")
    a("* unused by tb.json's own measure expressions (which FIND v(se_code)")
    a("* directly), kept for parity with the schematic deck.")
    a(f"b{TAG}ph {TAG}ph 0 V = v({TAG}_drdy)")
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

    text = fft_netlist_extracted(args.top)
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
