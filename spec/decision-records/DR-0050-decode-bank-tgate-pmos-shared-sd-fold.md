# DR-0050: Fold the decode-bank T-gate PMOS into a shared-source/drain pair (`adc_tgate_f`)

- **Status**: ratified
- **Date**: 2026-11-21
- **Decided by**: Builder agent, issue #940 (adoption of the issue #936 measured candidate)
- **Supersedes**: none — first record on the decode-bank T-gate's layout
  topology. It does not reopen [DR-0011](DR-0011-cdac-switching-scheme.md),
  [DR-0014](DR-0014-bottom-plate-sampling.md) or [DR-0016](DR-0016-input-structure-ron-repoint.md):
  the four-leg cell, the sampling phase and the published R_on row all
  stand unchanged.
- **Superseded by**: (none while this record stands)
- **Related**: #936 (the measured candidate and its evidence),
  `layout/adc-top/candidates/records/20261120-191014-2dd7403e.md`,
  `layout/adc-top/economy/records/20261120-191014-2dd7403e.md`,
  [DR-0017](DR-0017-adc-top-area-budget-overrun.md) (the Area row),
  [DR-0034](DR-0034-supply-droop-budget.md) (the droop budget this
  record's Consequences move).

## Context

The ratified Area row (`< 0.1 mm²` for `adc_block`) is FAIL at the current
topology: 130,848.134 µm² as committed, and the economy record's
lower-bound sum shows the row is not reachable without a topology change —
the binding terms are the array pair width at the ratified unit cap and the
199.21 µm `sar_ctrl` column. Issue #936 ranked the decode-bank levers and
measured the rank-1 candidate (`layout/adc-top/candidates/bank-fold-2x/`):
every decode-bank T-gate PMOS — the `wp=20u` device whose column sets the
bank row height at 21.3 µm, double the 11.3 µm the 10 µm NMOS + tap strip
force — drawn as TWO abutting, mirrored `wp=10u` fingers sharing one
source/drain diffusion. Measured: **−13,434.100 µm² (−10.26 %)** on
`ADC_BLOCK` (130,848.134 → 117,414.034 µm², height 194.8 → 174.8 µm at
unchanged width), DRC clean at the pinned 0.6.0 deck, 28 baseline-identical
`poly2.enclosing.sab.1` markers at the 0.8.0 deck (the known #851/#838
comparator-resistor markers, zero new findings), LVS match on both streams.
The Area row still FAILs after adoption (0.117414 mm² > 0.1 mm²) — that
remaining gap is the sequencer block's / a future area iteration's, not
this record's.

Until adopted, the repo's committed area figure and every PEX-based result
describe the unfolded bank, while the best measured layout sits in a
candidate directory. This record adopts it into the ratified design
netlist, so the schematic deck and the extracted deck are one netlist
again.

## Decision

The decode-bank T-gate — the `Xsi`/`Xsr`/`Xsh`/`Xsl` instances of
`adc_cdac_cell` — is ratified as the folded `adc_tgate_f`: same ports,
same NMOS (`w=10u l=0.28u`), PMOS stated as **two parallel `wp=10u`
devices** (unchanged parallel W, `20u = 2 × 10u`), at fixed literal widths.
`design/adc-top/gen_adc_top.py` emits it and `design/adc-top/adc_top.spice`
states it. The layout draws the same thing (`lib/place.draw_devices(...,
fold_shared_sd=True)`): consecutive identical PMOS twins as one abutting
mirrored island whose shared diffusion carries the same net on both sides —
real shared source/drain, which is what saves the area (the island census:
36 single 4,960 nm islands per bank replacing 36 separate 2,480 nm ones).

Two scope rulings, both inherited from the measured candidate:

- The **top-plate switch's own `adc_tgate` is NOT folded** (`adc_tp_sw`
  keeps the parametrised single-PMOS subckt). Its row is not
  height-critical — it sits beside the 114 µm arrays — so folding it would
  only push the comparator, and with it the analog core's right edge,
  rightward for nothing. The unfolded `adc_tgate` stays defined for it and
  for the testbench replicas that must match `sim/device-switch-ron/` and
  `sim/cdac-bit-settling/`'s characterised geometry.
- The **`bank_fold_shared_sd` generator flag is retired**, not left
  default-off: with the folded netlist the flag-off path can only fail the
  generator's transistor-count assertion (296 vs 368 MOS flattened), i.e.
  the unfolded stream no longer has a netlist. Advertising that choice with
  a flag would be a lie; the assertion is the honest replacement.
  `candidates/gen_bank_fold_candidate.py` remains runnable as the evidence
  generator its records cite (its substitution step becomes a detected
  no-op against this netlist).

One secondary geometry change is forced by the fold and rides this
decision: the bank row's right edge moves past the comparator's left edge
(row_x1 434.66 → 523.94 µm), so the `vcm` bridge's far hop — whose corridor
is derived from that edge — lands inside the comparator's Comp span, where
`geo.stitch` correctly refuses a Poly2 strap. `vcm`'s FAR hop therefore
joins `vdd`/`vss` on Metal2 (the property that made Metal2 the answer for
the supplies in #378: it crosses Comp without connecting); the near hop
stays Poly2. #378's reference-net argument for Poly2 was about strap
resistance, not correctness, and `vcm` sources no standing current.

## Alternatives considered

- **Keep the flag opt-in permanently (candidate stays a candidate)** —
  rejected: it leaves two diverging netlists, the schematic deck no longer
  matches the extracted deck, and every PEX-based number describes a
  layout the repo no longer holds as best. This is the status quo this
  record exists to end.
- **Fold the top-plate switch too** — rejected: measured no benefit (not
  height-critical) and it pushes the comparator rightward; explicitly out
  of #940's scope.
- **Parameterise the fold (`wn`/`wp`/fingers)** — rejected: the fold is
  one specific ratio the floorplan can absorb (+2.48 µm per pair × 36
  pairs per bank of row width, which the 55 µm of measured slack to the
  comparator's right edge covers). Literal widths keep nothing downstream
  dependent on expression evaluation, exactly as the measured candidate
  stated them.
- **Chase the remaining Area-row gap here** — rejected: the economy
  record's lower-bound sum (≥ 102,022 µm² union-based at the unfolded
  topology) shows the row needs the array pair width and/or a ~45 %
  narrower `sar_ctrl` column — a sequencer-block / future-iteration
  change, not a decode-bank one. This record does not relax the row.

## Consequences

- **Area**: `adc_block` 130,848.134 → **117,414.034 µm²** (−10.26 %);
  height 194.8 → 174.8 µm at unchanged 671.705 µm width; drawn area
  66,769.62 → 65,156.91 µm², utilization 0.510 → 0.555. The Area row
  **stays FAIL** (0.117414 mm² > 0.1 mm²), now with ~2,022 µm² of
  headroom above the ratified target's union-based lower bound — the gap
  the sequencer block owns.
- **Netlist/device count**: flattened MOS 296 → **368** (+72 = 2 sides ×
  9 cells × 4 T-gates × 1 extra PMOS device); extraction 1,320 → 1,392
  devices (`adc_top`), 1,349 → 1,421 (`adc_block`); pfet 148 → 220 / 160
  → 232. The `adc_tgate` subckt survives (top-plate switch, replicas);
  `adc_tgate_dum` untouched.
- **Parasitics move**: S/D junction area per pair preserved
  (2 × 1100×20000 → 2 × 1100×10000 + 2200×10000 nm²) while perimeter
  drops (the shared edge is interior); block R/C totals move (parasitics
  re-take: `layout/adc-top/parasitics/records/20261121-133413-c352cac.md`
  — `adc_top` total R 128,336.85 → 151,455.76 Ω, C 6,236.04 → 6,626.95
  fF). Every extracted-deck campaign that consumes the stream
  (INL/DNL, ENOB/FFT, cdac-bit-settling, device-switch-ron,
  adc-block-pex) is re-run by #940; the switch R_on rows are the named
  risk (parallel W unchanged, only junction parasitics move).
- **Power delivery margin drops (the bad consequence, stated plainly)**:
  the re-baselined `klt power` solve
  (`layout/power/records/20261121-134351-c352cac.md`) keeps every
  nominal-corner case inside DR-0034's **proposed** 33 mV budget (worst
  25.566 mV, 1.29× margin, was 1.9×) but the **pessimistic resistance
  corner now exceeds it at three of four landings** (39.889–46.772 mV,
  was 16.762–17.263 mV PASS): the wider rows move every supply-path X
  derived from the row's right edge and lengthen the paths to the
  comparator site. The `control.metal2-at-4x-poly2` negative control
  flips FAIL → PASS because the in-bank network (Poly2 risers, Contact,
  Metal1 trunk), not the 3 Metal2 bridge edges, now dominates. Recovery
  belongs to a future power-delivery iteration; this record trades that
  margin for the area knowingly and records the numbers rather than
  smoothing them.
- **Mismatch**: all 36 bank T-gates per side fold identically (the bank
  is unit-weighted, `m=`-devices); the matching-critical CDAC arrays and
  their dummy ring are untouched.
- **Stale `area.json` `dimensions_um` entries** (economy record Part 0's
  flag: `decode_bank` 441.17 vs the drawn 480.66, `tp_switches` 31.93 vs
  37.86) are fixed in the same adoption — the generator now reads the
  final cell bboxes for dimensions, so the file is self-consistent
  (`decode_bank` 532.77 × 22.46 = 11,966.0142 µm² = its own area entry).
- **ERC unchanged**: every `layout/erc/` case reported exactly what it
  reported on the unfolded stream
  (`layout/erc/records/20261121-133538-c352caca.md`) — structurally the
  same nodes connect through the same ties; only the GDS pin moved.

## Spec lines affected

- `README.md#target-specification` — Area row — **no value change**: the
  ratified `< 0.1 mm²` target stands and remains FAIL after adoption
  (0.117414 mm²); this record moves the measured figure the row is graded
  on, not the row. The row's remaining gap is owned by the sequencer
  block / a future area iteration, per the economy record's lower-bound
  sum.
- `README.md#target-specification` — Input structure row, series switch
  `R_on` — **evidence re-take pending**: the published 21.3–60.0 Ω was
  measured on the unfolded bank T-gate; parallel W per T-gate is
  unchanged (20u = 2 × 10u) so only junction parasitics can move it.
  #940's campaign re-runs own the re-measurement and any row update it
  forces.
