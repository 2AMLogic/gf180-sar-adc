#!/usr/bin/env python3
"""The #13 power testbench, wired against the PMOS-body-remediated,
MiM-mapped **extracted** `ADC_TOP` core -- issue #89 **Scope item 1** (the
power slice; static linearity is `gen_extracted_inl_dnl_tb.py` and dynamic
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

## The one thing that does not port mechanically, and what is done about it

`sim/extracted-delta-summary.md` §6.2 named this deck as the one #13 bench
that "does not port mechanically", because its claim is a **per-block supply
decomposition** and the core swap replaces exactly one of those blocks. That
statement was correct, and this module does not pretend otherwise -- it
resolves it, structurally and in the open:

The schematic deck brings out five separately-measured sources
(`gen_adc_top._preamble()` / `_core()`):

| source  | schematic block                                                |
|---------|----------------------------------------------------------------|
| `vddc`  | comparator (static preamp bias + latch dynamic)                |
| `vddd`  | CDAC bottom-plate four-leg T-gates **and their local drivers** |
| `vddt`  | DR-0014's per-side top-plate V_cm switch **and its driver**    |
| `vrefs` | charge drawn from V_REF through DR-0002's network              |
| `vcms`  | charge drawn from V_cm                                         |

The **drawn layout has one supply rail**. The extracted `.SUBCKT ADC_TOP`
exposes a single `vdd` pin (see the pin list at the head of
`reports/*/adc_top.para.spice`), and the parasitic network on it is a single
pin-stub `Rvdd`/`Cvdd` pair with every device hung directly off the pin node
-- there is no internal segmentation of `vdd` that could be tapped to
re-derive the split, and inserting an ammeter *inside* the extracted subckt
would mean editing extraction output, which §1.1's methodology rule forbids
without saying so.

So the honest post-layout decomposition is **four-way, not five-way**:

- `vddc` / `vrefs` / `vcms` are untouched -- the comparator is schematic-level
  in this wrapper (Scope item 0) and the two reference sources are external to
  the core on both sides.
- `vddd` and `vddt` **merge**. `gen_extracted_core_tb._wire_pin()` already
  maps the extracted core's `vdd` pin to `vddd` (its own comment says so, and
  defers the attribution question to "the #13 power deck's job" -- this is
  that deck). The consequence, stated rather than left to be discovered:

      p_trk_*  reads EXACTLY 0 on the extracted side, by construction --
               nothing but its own source is connected to `vddt`.
      p_cdac_* carries the merged CDAC + top-plate-switch supply current.

  The like-for-like comparison against the schematic record is therefore
  `p_cdac_extracted` vs `p_cdac_schematic + p_trk_schematic`, and
  `p_total_*` -- **the spec-line row** -- is unaffected by the merge, because
  the manifest's `p_total_*` expression already sums all five sources.

This is a coarsening of the *reported breakdown*, not of the claim: every
microamp the schematic deck attributed to `vddt` is still measured, still
inside `p_total_*`, and still inside the < 1 mW check. `sim/adc-power/`'s own
`tb.json` runs UNMODIFIED against this deck (`run_corners.py --netlist ...
--netlist-provenance extracted`), so no measure expression, no check bound and
no claim string differs between the two runs.

## Why reuse the schematic manifest, not hand-duplicate it

Same reason `gen_extracted_inl_dnl_tb.py` and `gen_extracted_enob_fft_tb.py`
give: `sim/adc-power/testbench/tb.json`'s `analyses`/`measure`/`checks` are
`se`-tagged, source-name-specific text (`i(vddc)`, `i(vddd)`, `v(vddc)`),
not a template. Calling `gen_extracted_core_tb._core_extracted(tag="se", ...)`
produces an extracted-core conversion chain whose controller ports, input
drive network and comparator wiring carry exactly the net and source names
that manifest reads, so the two runs measure the same quantity the same way.

The five-level staircase stimulus (`PWR_LEVELS`, `PWR_CONV_PER_LEVEL`,
`PWR_WARMUP_CONV`, `CONV_NS`) is imported from `gtop`, not retyped -- the
code-dependence of MCS switching energy is a property of the claim, not of
the core, so it must not drift between the two decks.

## What this does NOT do

- Does not touch `sim/adc-power/testbench/tb.json` or `tb_adc_power.spice`
  (the schematic deck) -- append-only, per sim/README.md.
- Does not modify `design/adc-top/gen_adc_top.py` (its `TARGETS` are
  byte-for-byte guarded by `sim/tests/test_adc_top_netlist.py`).
- Does not close the rung-1 sequencer gap. The SAR sequencer and output
  register are XSPICE event-driven primitives on **both** sides and draw no
  supply current on either; that gap is stated in the schematic record and
  is unchanged here (it is a property of DR-0010 rung 1, not of the layout).
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

    Same five-level staircase (`PWR_LEVELS`, `PWR_CONV_PER_LEVEL`,
    `PWR_WARMUP_CONV`, `CONV_NS` -- all imported from `gtop`, not retyped)
    and the same five supply/reference sources `_preamble()` declares, with
    the extracted core wired by `gen_extracted_core_tb._core_extracted` in
    place of `_core()`'s two `adc_cdac_side` instances plus its two
    `adc_tp_sw` instances.
    """
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_power_extracted -- power at 1 MS/s, broken down by block, of")
    a("* the extracted, PMOS-body-remediated, MiM-mapped ADC_TOP core over")
    a("* the PVT grid (issue #89 Scope item 1). GENERATED by")
    a("* layout/adc-top/parasitics/gen_extracted_power_tb.py -- do not edit.")
    a("*")
    a("* Reuses sim/adc-power/testbench/tb.json UNMODIFIED (via")
    a("* `run_corners.py --netlist ... --netlist-provenance extracted`): the")
    a("* five-level staircase, the per-block `meas tran ... AVG i(...)`")
    a("* expressions and the < 1 mW p_total_* checks are byte-for-byte the")
    a("* schematic deck's own, tagged `se_*` to match. The ONLY thing that")
    a("* differs is the analog core: one extracted ADC_TOP instance in place")
    a("* of two adc_cdac_side + two adc_tp_sw instances. Comparator and")
    a("* rung-1 controller stay schematic-level (Scope item 0).")
    a("*")
    a("* PER-BLOCK ATTRIBUTION POST-LAYOUT, STATED PLAINLY. The drawn layout")
    a("* has ONE supply rail: the extracted .SUBCKT ADC_TOP exposes a single")
    a("* `vdd` pin, and its parasitic network is a single pin stub with every")
    a("* device on the pin node -- there is no internal vdd segmentation to")
    a("* tap, and instrumenting inside the extracted subckt would mean")
    a("* editing extraction output. So the schematic deck's FIVE-way split")
    a("* becomes a FOUR-way split here:")
    a("*")
    a("*   vddc   comparator          unchanged (schematic-level block)")
    a("*   vddd   CDAC + top-plate    MERGED. The extracted core's single vdd")
    a("*          V_cm switch         pin is wired here, so this rail carries")
    a("*                              BOTH the bottom-plate four-leg T-gate")
    a("*                              drivers AND DR-0014's top-plate V_cm")
    a("*                              switch and its driver.")
    a("*   vddt   (empty)             reads EXACTLY 0 by construction --")
    a("*                              nothing but its own source is on this")
    a("*                              node. p_trk_* is therefore 0 on the")
    a("*                              extracted side and its schematic")
    a("*                              counterpart must be compared against")
    a("*                              p_cdac_extracted, not against 0.")
    a("*   vrefs  reference           unchanged (external to the core)")
    a("*   vcms   reference           unchanged (external to the core)")
    a("*")
    a("* p_total_* -- THE SPEC-LINE ROW -- is unaffected by the merge: the")
    a("* manifest's expression already sums all five sources, so every")
    a("* microamp the schematic deck attributed to vddt is still measured and")
    a("* still inside the < 1 mW check. See gen_extracted_power_tb.py's")
    a("* module docstring for the full rationale.")
    a("*")
    a("* WHAT IS NOT MEASURED HERE, unchanged from the schematic deck: the")
    a("* rung-1 SAR sequencer and output register are XSPICE event-driven")
    a("* primitives on BOTH sides and draw no supply current on either. That")
    a("* is a DR-0010 rung-1 property, not a layout one, so it is neither")
    a("* closed nor worsened by this run. The dominant digital term -- the")
    a("* array's switch-gate drive -- IS measured, on vddd, on both sides.")
    a("* ==================================================================")
    a("")
    L += gtop._preamble("{vdd_val/1024}")
    a("")
    a("* ---- input: staircase over the code range -------------------------")
    a("* Identical to gen_adc_top.power_netlist() -- same PWR_LEVELS, same")
    a("* PWR_CONV_PER_LEVEL/PWR_WARMUP_CONV schedule, same tag. Switching")
    a("* energy in an MCS array is code-dependent, so both decks convert at")
    a("* five input levels rather than reporting one point of a curve.")
    pts: list[str] = []
    prev = ""
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
    a("")
    a("* ---- vddt topology tie ---------------------------------------------")
    a("* The extracted core merges the top-plate switch onto its single vdd")
    a("* pin (see the header), so NO device is left on vddt -- `_preamble()`'s")
    a("* `vddt` source would otherwise be the node's only connection, which")
    a("* ngspice flags as a topology warning. vddt is therefore tied to vddd")
    a("* through 1 Gohm. Both rails are driven by ideal sources at the SAME")
    a("* {vdd_val}, so this tie carries identically 0 A at every corner and")
    a("* every timepoint: p_trk_* is exactly 0 on the extracted side, and")
    a("* that 0 means 'this block is inside p_cdac_*', not 'this block draws")
    a("* no power'. Disclosed here rather than left as an unexplained zero.")
    a("Rsetrktie vddt vddd 1G")
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
