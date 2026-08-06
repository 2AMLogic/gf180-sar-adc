#!/usr/bin/env python3
"""The #13 power-breakdown testbench, wired against the PMOS-body-remediated,
MiM-mapped **extracted** `ADC_TOP` core -- issue #89 **Scope item 1** (the
power slice; static linearity is `gen_extracted_inl_dnl_tb.py`, dynamic
performance is `gen_extracted_enob_fft_tb.py`, both already landed).

    python3 layout/adc-top/parasitics/gen_extracted_power_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_power_tb.py --check

Writes ONE file:

    sim/adc-power/testbench/tb_adc_power_extracted.spice

into the SAME experiment directory as the schematic-level deck
(`sim/adc-power/testbench/tb_adc_power.spice`), per sim/README.md "Extracted
vs schematic semantics" -- the extracted record appends alongside the
schematic record, not a new experiment. Deliberately does NOT write a second
`tb.json`.

## The one thing that does NOT port mechanically, and what is done about it

`sim/extracted-delta-summary.md` §6.2 flagged this deck as the one #13 bench
that "does not port mechanically", because its claim is a **per-block supply
decomposition** and the core swap replaces exactly one of those blocks:

| rail | schematic deck (`gen_adc_top._core()`) | this deck |
|---|---|---|
| `vddc` | comparator (`X<tag>cmp ... comparator`) | **unchanged** -- comparator is schematic-level (Scope item 0) |
| `vddd` | the two `adc_cdac_side` instances: bottom-plate T-gates + local drivers | the extracted `ADC_TOP` instance's **single** `vdd` pin |
| `vddt` | the two `adc_tp_sw` instances: DR-0014 top-plate V_cm switch **and its `adc_drv`** | **structurally empty** -- see below |
| `vrefs` | DR-0002 reference network | **unchanged** |
| `vcms` | ideal V_cm source | **unchanged** |

The layout draws the per-side top-plate V_cm switch *inside* `ADC_TOP`'s own
boundary (`parasitics/README.md`, "What was extracted": 296 FETs = 288
switch/driver FETs + 8 top-plate-switch FETs), and `klt extract` gives that
block exactly **one** power pin, `vdd` -- there is no drawn boundary between
"the bottom-plate switch network" and "the top-plate switch" to attribute
current across. Splitting them post hoc would mean partitioning a flat
extracted device list by guessing which device belongs to which schematic
block, which is precisely the kind of silent apportionment this deck exists
to avoid (`tb.json`: "so the breakdown is measured rather than apportioned").

**Methodology choice, stated rather than absorbed** (issue #89's Test Plan
requires the extracted-side methodology choices to be documented with
provenance): the extracted `vdd` pin is wired to **`vddd`**, so

- `p_cdac_*` on the extracted side means **CDAC bottom-plate switches +
  local drivers + the top-plate V_cm switch and its driver** -- i.e. the
  schematic's `p_cdac_* + p_trk_*`, merged;
- `p_trk_*` on the extracted side is **structurally zero**, not a
  measurement of a block that got cheaper. `vddt` still exists (the
  unmodified manifest measures `i(vddt)`) but no device is connected to it,
  so a `0` in that column is the *absence of a separate rail*, not a
  reduction in top-plate-switch power;
- `p_total_*` -- **THE spec-line claim** (Power @ 1 MS/s < 1 mW) -- is
  conserved exactly, because it is the sum over all five rails and the merge
  moves current between two of its terms rather than out of it. So the
  headline row is directly, unambiguously comparable schematic vs extracted,
  and the per-block comparison is done against the schematic's `p_cdac +
  p_trk` sum. Both statements are re-derived in
  `sim/extracted-delta-summary.md` §4.7, not transcribed here.

This is the same choice `gen_extracted_core_tb._wire_pin()` already makes for
every other extracted-core deck (`vdd` -> `vddd`); what is new here is that
this deck is the first one whose *claim* is sensitive to it, so it is
documented rather than left as an electrically-irrelevant default.

## Why reuse the schematic manifest, not hand-duplicate it

Identical rationale to `gen_extracted_enob_fft_tb.py`: `tb.json`'s
`analyses`/`measure`/`checks` are `se`-tagged, rail-specific text
(`i(vddc)`, `i(vddd)`, `v(vddc)`, ...), not a template. Reusing it verbatim
via `run_corners.py --netlist ... --netlist-provenance extracted` is the only
way to get a transcription-error-free reuse of the measurement methodology
against a different analog core -- a delta between two independently-written
measurement decks is not a delta between two circuits.

Note that every rail name this manifest measures is emitted by
`gen_adc_top._preamble()`, which this deck calls unmodified -- so no rail is
renamed, added or dropped on the extracted side. The `vddt` source is still
declared and still measured; it simply has nothing on it.

## What this does NOT do

- Does not touch `sim/adc-power/testbench/tb.json` or `tb_adc_power.spice`
  (the schematic deck) -- append-only, per sim/README.md.
- Does not modify `design/adc-top/gen_adc_top.py` (same rationale
  `gen_extracted_core_tb.py`'s docstring gives: its `TARGETS` are
  byte-for-byte guarded by `sim/tests/test_adc_top_netlist.py`).
- Does not close the sequencer gap. The rung-1 SAR controller draws no
  supply current on EITHER netlist (XSPICE event-driven primitives, DR-0010
  rung 1) -- the schematic record already carries that as a stated gap, and
  swapping the analog core does not touch it. The extracted-side record must
  carry the same caveat, unweakened.
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
OUT_PATH = REPO / "sim" / "adc-power" / "testbench" / "tb_adc_power_extracted.spice"


def power_netlist_extracted(top: str = "ADC_TOP") -> str:
    """The extracted-core counterpart of `gen_adc_top.power_netlist()`.

    Same five-level input staircase (`PWR_LEVELS`, `PWR_CONV_PER_LEVEL`,
    `PWR_WARMUP_CONV`, `CONV_NS` -- all imported from `gtop`, not retyped) and
    the same per-block supply sources from `gtop._preamble()`, with the
    extracted core wired by `gen_extracted_core_tb._core_extracted` in place
    of `_core()`'s two `adc_cdac_side` + two `adc_tp_sw` instances.

    No ideal-shadow DAC: unlike the static-linearity and FFT decks, this
    manifest's measurements are supply currents and one supply voltage. It
    makes no claim referenced to an ideal conversion, so it needs no ideal
    conversion to reference against.
    """
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_power_extracted -- power at 1 MS/s, broken down by block,")
    a("* against the extracted, PMOS-body-remediated, MiM-mapped ADC_TOP core")
    a("* (issue #89 Scope item 1). GENERATED by")
    a("* layout/adc-top/parasitics/gen_extracted_power_tb.py -- do not edit.")
    a("*")
    a("* Reuses sim/adc-power/testbench/tb.json UNMODIFIED (via")
    a("* `run_corners.py --netlist ... --netlist-provenance extracted`): the")
    a("* same five input levels, the same per-rail `meas ... AVG i(...)`")
    a("* windows, the same < 1 mW check. The ONLY thing that differs from the")
    a("* schematic deck is the analog core itself.")
    a("*")
    a("* THE SUPPLY-ATTRIBUTION CONSEQUENCE, STATED PLAINLY. The extraction")
    a("* gives ADC_TOP exactly ONE power pin (`vdd`), and the layout draws")
    a("* DR-0014's per-side top-plate V_cm switch and its adc_drv INSIDE that")
    a("* same block. So on this netlist:")
    a("*")
    a("*   vddc   comparator            unchanged -- schematic-level here")
    a("*                                (issue #89 Scope item 0)")
    a("*   vddd   extracted ADC_TOP     bottom-plate T-gates + local drivers")
    a("*                                AND the top-plate V_cm switch + its")
    a("*                                driver: what the schematic deck")
    a("*                                reports as p_cdac + p_trk, MERGED,")
    a("*                                because no drawn boundary separates")
    a("*                                them in the extracted device list")
    a("*   vddt   (no devices)          STRUCTURALLY ZERO. The rail is still")
    a("*                                declared and still measured, so the")
    a("*                                manifest runs unmodified -- but a 0")
    a("*                                in p_trk_* is the absence of a")
    a("*                                separate rail, NOT a top-plate switch")
    a("*                                that got cheaper. Read p_cdac_* on")
    a("*                                this netlist against p_cdac_* +")
    a("*                                p_trk_* on the schematic one.")
    a("*   vrefs  reference             unchanged (DR-0002 network)")
    a("*   vcms   V_cm rail             unchanged (ideal source, DR-0011)")
    a("*")
    a("* p_total_* -- the ratified spec line -- is CONSERVED by that merge:")
    a("* it sums all five rails, and the merge moves current between two of")
    a("* its terms rather than out of it. The headline row is therefore")
    a("* directly comparable schematic vs extracted with no adjustment.")
    a("*")
    a("* WHAT IS STILL NOT MEASURED, unchanged from the schematic deck: the")
    a("* rung-1 SAR sequencer and output register draw no supply current on")
    a("* EITHER netlist (DR-0010 rung 1 -- ideal XSPICE event-driven")
    a("* primitives, no devices). Swapping the analog core does not close")
    a("* that gap and does not widen it; the extracted record carries the")
    a("* same stated caveat the schematic record does.")
    a("* ==================================================================")
    a("")
    L += gtop._preamble("{vdd_val/1024}")
    a("")
    a("* ---- input: staircase over the code range -------------------------")
    a("* Byte-for-byte the same PWL gen_adc_top.power_netlist() emits (same")
    a("* PWR_LEVELS / PWR_CONV_PER_LEVEL / PWR_WARMUP_CONV, imported not")
    a("* retyped): MCS switching energy is code-dependent, so five levels.")
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
    L += gtop.sar._wrap(f"v{TAG}inp {TAG}_vinp 0 pwl(", [" ".join(pts) + ")"])
    a(f"v{TAG}vinn {TAG}_vinn 0 dc {{vcm}}")
    a("")

    pins, core_text = G.core_pins(top)
    a("* ---- library: comparator + SAR controller + extracted core -------")
    L.append(gtop.comparator_block())
    L.append(gtop.sar.library())
    L.append(core_text)
    a("")
    L += G._core_extracted(TAG, "0", pins, top)
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    ap.add_argument(
        "--top", default="ADC_TOP", choices=["ADC_TOP"],
        help="ADC_TOP only -- see gen_extracted_core_tb.py's --top help. "
             "ADC_BLOCK would additionally merge the COMPARATOR's supply into "
             "the same single vdd pin, collapsing p_cmp_* as well, and is "
             "blocked on the functional defect recorded in "
             "records/20260806-adc-block-comparator-smoke.md.",
    )
    ap.add_argument("--stdout", action="store_true", help="write to stdout instead")
    args = ap.parse_args(argv)

    text = power_netlist_extracted(args.top)
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
