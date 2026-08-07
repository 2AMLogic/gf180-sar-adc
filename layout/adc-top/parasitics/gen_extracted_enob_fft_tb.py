#!/usr/bin/env python3
"""The #13 dynamic-performance (ENOB/FFT) testbench, wired against the
PMOS-body-remediated, MiM-mapped **extracted** `ADC_TOP` core -- issue #89
**Scope item 1** (the ENOB/FFT/SFDR slice; static linearity is
`gen_extracted_inl_dnl_tb.py`, already landed -- see this module's own "What
this does NOT do" below).

    python3 layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py --check

Writes ONE file:

    sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice

into the SAME experiment directory as the schematic-level deck
(`sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice`), per sim/README.md
"Extracted vs schematic semantics" -- the extracted record appends alongside
the schematic record, not a new experiment. Deliberately does NOT write a
second `tb.json` -- see "Why reuse the schematic manifest" below (same
rationale `gen_extracted_inl_dnl_tb.py` gives for the static-linearity deck).

## Why reuse the schematic manifest, not hand-duplicate it

`design/adc-top/gen_adc_top.py`'s `fft_netlist()`/`_core()` drive a coherent
64-sample sine into the converter and export the decoded code as one `meas`
per conversion, tagged `se_*`. `sim/adc-enob-fft/testbench/tb.json`'s
`analyses`/`measure`/`checks` are `se`-tag-specific text (`v(se_code)`,
`v(se_aerrh)`, `v(vrefn)`, ...), not a template -- so the only way to get an
EXACT, transcription-error-free reuse of that measurement methodology
against a different analog core is to make the alternate core's conversion
chain use the exact same `se_*` net names.

`gen_extracted_core_tb.py`'s `_core_extracted(tag, mode, pins, top)` already
wires the controller's `drdy`/`samp_tp_n`/`sel_in_n` ports and the decoded
`se_code` node onto those same names (built for exactly this kind of reuse --
`gen_extracted_inl_dnl_tb.py` already relies on the same fact for the
static-linearity deck). The ONE piece this FFT deck needs that
`_core_extracted()` deliberately omits is the ideal-shadow error node, gated
to the comparator strobe (`se_aerrh` -- the per-conversion worst-decision-
error witness `tb.json`'s `decerr_c*_lsb` checks read). That already exists,
ready to call: `gen_extracted_core_tb.shadow_dac_and_error(tag, gated=True)`
-- unlike the static-linearity deck (which carries its own pinned copy
because its committed fixture predates this shared emitter and a collapse
would have to regenerate that fixture), this module calls it directly rather
than duplicating the formula a third time.

The result: `sim/run_corners.py adc-enob-fft --netlist <this file's output>
--netlist-provenance 'extracted (...)'` runs the UNMODIFIED
`sim/adc-enob-fft/testbench/tb.json` manifest -- same claim, same coherent-
sampling stimulus, same per-sample `meas`, same coverage-witness/vref-droop
checks -- against this file instead of the schematic one. The post-processing
(`analyze_fft.py`, which computes SNDR/ENOB/SFDR/THD from the harness's own
raw per-corner logs) is unmodified too: it reads whichever corner directory
is pointed at it, schematic or extracted, without caring which core produced
the logs.

## What this does NOT do

- Does not touch `sim/adc-enob-fft/testbench/tb.json` or
  `tb_adc_enob_fft.spice` (the schematic deck) -- append-only, per
  sim/README.md.
- Does not modify `design/adc-top/gen_adc_top.py` (same rationale
  `gen_extracted_core_tb.py`'s own docstring gives: its `TARGETS` are
  byte-for-byte guarded by `sim/tests/test_adc_top_netlist.py`).
- Does not re-run the #13 power deck against the extracted core, or the #14
  Monte Carlo re-run -- those remain separate, still-deferred slices of
  issue #89's scope (power does not port mechanically at all -- see
  `sim/extracted-delta-summary.md` §6.2).
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
    place of `_core()`'s two `adc_cdac_side` instances, and the gated ideal
    shadow error node from `gen_extracted_core_tb.shadow_dac_and_error`.
    """
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_enob_fft_extracted -- dynamic performance (coherent-sampling")
    a("* FFT) of the extracted, PMOS-body-remediated, MiM-mapped ADC_TOP core")
    a("* over the PVT grid (issue #89 Scope item 1). GENERATED by")
    a("* layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py -- do not")
    a("* edit.")
    a("*")
    a("* Reuses sim/adc-enob-fft/testbench/tb.json UNMODIFIED (via")
    a("* `run_corners.py --netlist ... --netlist-provenance extracted`): the")
    a("* coherent sine, the per-sample `meas`, and the coverage-witness /")
    a("* vref-droop checks are byte-for-byte ports of")
    a("* design/adc-top/gen_adc_top.py's fft_netlist()/_core(), tagged")
    a("* `se_*` to match that manifest's measure expressions exactly. The")
    a("* ONLY thing that differs from the schematic deck is the analog core")
    a("* itself: one extracted ADC_TOP instance (both CDAC array sides +")
    a("* the per-side top-plate V_cm switch, PMOS-body-remediated to vdd,")
    a("* MiM-mapped to the native PDK subckt) in place of two adc_cdac_side")
    a("* instances + two adc_tp_sw instances. Comparator and rung-1")
    a("* controller stay schematic-level (issue #89 Scope item 0). See")
    a("* gen_extracted_enob_fft_tb.py's module docstring for the full")
    a("* rationale.")
    a("* ==================================================================")
    a("")
    L += G.saved_vectors_lines(gtop.fft_manifest())
    a("")
    L += gtop._preamble("{vdd_val/1024}")
    a("")
    a("* ---- near-full-scale sine -- identical to gen_adc_top.fft_netlist()")
    a("* Amplitude and coherence rationale are unchanged by which core sits")
    a("* behind the input drive network; see fft_netlist()'s own comments")
    a("* for the full derivation.")
    a(
        f"v{TAG}in {TAG}_vinp 0 sin({{vcm}} {{vref/2*{gtop.FFT_AMP_FRAC}}}"
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
    a("* conversion's drdy phase -- identical to fft_netlist(), kept for")
    a("* parity even though tb.json's own `meas ... FIND` reads v(se_code)")
    a("* directly rather than this node.")
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
