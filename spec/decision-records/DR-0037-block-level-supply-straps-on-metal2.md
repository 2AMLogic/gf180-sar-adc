# DR-0037: `ADC_BLOCK`'s block-level `vdd`/`vss` straps are carried on Metal2, so the droop verdict is a property of the block and not of where a parent lands the supply

- **Status**: ratified
- **Date**: 2026-09-23
- **Decided by**: Builder agent, issue #378
- **Supersedes**: none — first record for this decision. It does **not**
  supersede [DR-0034](DR-0034-supply-droop-budget.md): that record sets the
  33 mV budget and the budget is unchanged. It retires one of DR-0034's
  *Consequences* (*"Where the supply is landed becomes a spec-relevant
  choice"*), which was a statement about the old geometry, and DR-0034 is
  annotated to say so.
- **Superseded by**: (none while this record stands)
- **Related**: #378 (the landing-site fragility this answers), #346 /
  [DR-0034](DR-0034-supply-droop-budget.md) (the read and the budget it is
  graded against), #356 / [DR-0035](DR-0035-well-taps-and-tie-straps.md)
  (the previous geometry move, whose "keep zero supply area above Metal1"
  choice this record reverses deliberately), #330 and `layout/erc/` (the
  structural run whose *no supply geometry above Metal1* finding this makes
  false), #379 (the transient/decoupling question this does **not**
  answer), #383 (the parasitic re-extraction this moves further out of
  date), `layout/power/records/20260923-084734-5f13cf9.md` (the measurement
  below), `layout/drc/records/20260923-084515-5f13cf9.md`,
  `layout/lvs/records/20260923-084536-5f13cf9.md`,
  `layout/erc/records/20260923-084733-5f13cf9.md`,
  `signoff/records/20260923-084903-5f13cf9.md`

## Context

`ADC_BLOCK` has **no supply pad**. It publishes four labelled sites — the
`Metal1_Label` texts in `ADC_DECODE_BANK_N`, `ADC_DECODE_BANK_P`,
`ADC_TOP_SW` and `COMPARATOR` — and a parent lands the supply at one of
them. Until this record, every ampere that crossed *between* those four
sub-blocks crossed a **Poly2** riser: the block-level straps were
`geo.stitch` corridors, poly at 7.3 Ω/sq nominal and 15.0 Ω/sq at the PDK's
high-resistance corner, tens of microns long.

The consequence, measured in `layout/power/` at the block's worst-corner
average current (40.12 µA, `ff_125c_3.63v`, `sim/adc-rail-current/`) and
graded against DR-0034's 33 mV combined budget
(record `20260923-070149-e84ad26`, geometry `ae4e8964…`):

| Supply landed at | R corner | Worst combined | vs 33 mV |
|---|---|---:|---|
| `COMPARATOR` | nominal | 5.722 mV | PASS, 5.8× |
| `ADC_DECODE_BANK_N` | nominal | 14.907 mV | PASS |
| `ADC_TOP_SW` | nominal | 21.390 mV | PASS |
| `ADC_DECODE_BANK_P` | nominal | **33.552 mV** | **FAIL** |
| `COMPARATOR` | pessimistic | 10.877 mV | PASS, 3.0× |
| `ADC_DECODE_BANK_P` | pessimistic | **58.552 mV** | **FAIL**, 1.77× over |

So the block was integrable only if the integrator happened to land on the
comparator's label. Nothing stated that requirement and nothing enforced
it — and the site that failed, `ADC_DECODE_BANK_P`, is the block's left
edge, an entirely reasonable choice. Issue #378 put the two available
answers side by side: carry the rails above Metal1, or ratify the
landing-site constraint as an integration requirement of this block.

## Decision

**Carry `ADC_BLOCK`'s block-level `vdd` and `vss` straps on Metal2, landing
on each sub-block's Metal1 trunk through a single Via1.** Concretely:

- `lib/geometry.stitch_metal2` is the Metal2 twin of `geo.stitch`: one
  `STRAP_W` (400 nm) Metal2 corridor spanning the trunks it ties, with one
  `VIA_SIDE` (260 nm) Via1 landed at each trunk's centre. It asserts the
  same *"x lies inside every trunk"* condition `geo.stitch` does (a via on
  bare substrate is silent — DRC-clean and unconnected), and additionally
  asserts `metal2.space.1` **clearance**, not mere non-intersection,
  against every existing Metal2 and Via1 shape.
- It does **not** have to clear `Comp` or `Poly2`, and that asymmetry is
  the reason the change is cheap: a Poly2 strap over diffusion is a
  parasitic MOSFET and a Poly2 strap over poly is a short, whereas Metal2
  carries no connectivity to anything below it without a drawn via.
- Three straps use it — the comparator's own `vdd`/`vss` corridor in
  `SWITCH_CMP_GAP`, and both hops of the switch-cell bridge (near column at
  the switch cell, far column at the decode banks).
- **`vcm` stays on Poly2.** It is a reference, not a supply: nothing in the
  measured current model draws standing current from it, `klt power` solves
  only `vdd`/`vss`, and leaving it alone keeps the change to the geometry
  the droop verdict depends on.
- `CMP_SUPPLY_PITCH` moves the comparator's two supply columns from a
  700 nm pitch to 900, because `metal2.space.1` (280 nm) is wider than
  `poly2.space.1` (240). At 900 the two straps keep 500 nm of space; at 700
  they would keep 300 — legal, but 20 nm over the rule instead of 220.

## Alternatives considered

- **Ratify the landing-site constraint instead** (#378's other branch) —
  not chosen. It is cheaper by exactly one geometry change and it is
  strictly worse: it exports a requirement no tool in this repo can check
  at the parent level, on a block whose own read already says the measured
  current is a *lower* bound (the DR-0010 rung-1 sequencer and output
  register draw nothing in the deck, and the deck's 2 ns maximum timestep
  averages shorter events). A constraint that costs the integrator a
  correct choice, and that the evidence cannot enforce, is the option to
  take only when the geometry cannot move. It could.
- **Route the straps over the CDAC arrays** — the shape #346 anticipated,
  not chosen. The arrays' Metal2 is not free: each of the 1024 unit caps
  carries a Metal2 bottom-plate riser (`draw_mim_bottom_riser`), so a
  horizontal Metal2 bar across an array would short every one it crossed.
  The corridors this record uses are the ones the straps already ran in —
  proven Comp-free by the geometry that placed them — which makes this a
  layer change rather than a floorplan change.
- **Widen the Poly2 straps instead** — not chosen. Poly2 is ~81× Metal1
  nominal and ~144× at the high-resistance corner; matching a 400 nm Metal2
  strap would take tens of microns of poly width in corridors that are
  6 µm wide in total.
- **Move every Poly2 riser in the block to metal** — not chosen, and it is
  worth stating why the EM verdict therefore cannot improve to `pass`: the
  in-sub-block terminal risers *are* the channel router
  (`lib/place.Channel`), one per device terminal. Replacing them is a
  rewrite of the library, not a strap change, and they carry one device's
  own current over a few microns — the term this record's own measurement
  shows is no longer material (below).

## Consequences

**Measured, not asserted** — `layout/power/records/20260923-084734-5f13cf9.md`,
same budget, same current model, same tool (`klt 0.6.0`), new geometry
(`adc_block.gds` `ae4e8964…` → `501f3985…`):

| Supply landed at | R corner | Was | Now | vs 33 mV |
|---|---|---:|---:|---|
| `ADC_DECODE_BANK_P` | nominal | 33.552 **FAIL** | **13.227** | PASS, 2.5× |
| `ADC_DECODE_BANK_N` | nominal | 14.907 | **12.770** | PASS, 2.6× |
| `ADC_TOP_SW` | nominal | 21.390 | **5.962** | PASS, 5.5× |
| `COMPARATOR` | nominal | 5.722 | **1.703** | PASS, 19× |
| `ADC_DECODE_BANK_P` | pessimistic | 58.552 **FAIL** | **17.184** | PASS, 1.9× |
| `ADC_DECODE_BANK_N` | pessimistic | (not run) | **16.697** | PASS, 2.0× |
| `ADC_TOP_SW` | pessimistic | (not run) | **11.485** | PASS, 2.9× |
| `COMPARATOR` | pessimistic | 10.877 | **2.767** | PASS, 12× |

- **The verdict stops depending on the landing site.** All four labelled
  sites now meet DR-0034 at both the nominal and the pessimistic resistance
  corner, the worst of the eight at 17.184 mV (1.9× inside budget). The two
  pessimistic-corner cases that did not exist before (`ADC_DECODE_BANK_N`,
  `ADC_TOP_SW`) were added for exactly this reason: "at every labelled
  site" is a claim about four sites, so four sites are run.
- **The droop still varies by site — the *verdict* does not.** 13.227 mV at
  the worst landing vs 1.703 mV at the best is still a factor of 7.8. This
  record does not claim a flat rail; it claims that no labelled landing
  site misses the budget.
- **The improvement is attributable, by its own control.**
  `control.metal2-as-poly2` re-solves the new geometry with Metal2 given
  Poly2's sheet resistance and returns **33.177 mV, FAIL**, at the same
  site and corner that read 33.552 mV before the change. If it had not, the
  improvement would be coming from something other than the straps.
- **The poly term is no longer the story.** `control.poly-as-metal1` — the
  counterfactual that attributed ~71 % of the block-level droop to Poly2 on
  the old geometry — now moves the `COMPARATOR` landing from 1.703 mV to
  1.574 mV, i.e. **~8 %**. What remains is Metal1 trunk and Contact.
- **Electromigration stays `pass_partial`, and this record does not claim
  otherwise.** Checked edges rise 353 → 375 and unchecked fall 737 → 715 as
  the strap edges move onto roles gf180mcuD publishes a DC limit for, with
  zero failing edges. It cannot become `pass`: every in-sub-block terminal
  riser is still Poly2, and gf180mcuD publishes no current-density limit
  for Poly2 or Contact. #378's acceptance criterion hoped this would clear;
  it does not, and the reason is structural rather than a re-run away.
- **The peak-current case still fails, unchanged in meaning.** 18 341 mV →
  4 934 mV of combined droop on a 3.3 V rail solved statically at the
  34.38 mA switching peak: still not a prediction, still the statement that
  a DC path with no charge storage cannot source that transient. That is
  #379's question, and this record does not touch it.
- **`layout/erc/`'s "no supply geometry above Metal1" finding is now
  false**, deliberately. Both rails still resolve to exactly one electrical
  island each (`klt erc` re-run, `20260923-084733-5f13cf9`), which is all
  T1 item 11 asks; `layout/erc/README.md` is re-taken to say what is true.
- **Every pinned artifact was re-minted, in dependency order**: DRC
  (`clean` on `adc_top` and `adc_block`), LVS (`match`, 0 mismatches — the
  extracted netlists are **byte-identical**, because this moves conductors
  and not connectivity), ERC (all five cases), IR/EM, then `klt signoff`.
  **No T1 row changed status**: 7/22 met, `tier: null`, before and after.
- **`layout/adc-top/parasitics/` falls further out of date.** It was
  already stale against #356 (disclosed there, tracked as **#383**); this
  moves the same two streams again. No T1 row cites it, the runner refuses
  to mint evidence over mismatched bytes, and the disclosure is updated.
- **Area is effectively unchanged.** The block's bounding box does not
  move; the decode banks grow 15 057.0 → 15 069.6 µm² per side (+0.08 %)
  because their trunks reach 200 nm further into the wider strap corridor.
  DR-0024's block-level budget is untouched.

## Spec lines affected

- None. DR-0034's 33 mV budget, its derivation and its `proposed —
  requires operator sign-off` status are all unchanged; this record changes
  the geometry graded against it, not the grading. The one thing it retires
  is DR-0034's Consequences bullet *"Where the supply is landed becomes a
  spec-relevant choice, not a layout detail"* — true of `ae4e8964…`, false
  of `501f3985…`, and annotated in place there because that record is still
  `proposed` rather than ratified.

## Revisit triggers

- **A parent adds loads to a labelled site, or the sequencer/output
  register stop being DR-0010 rung-1 primitives.** Every number above rests
  on a measured current that is a *lower* bound for exactly that reason;
  1.9× at the worst site/corner is margin against a current smaller than
  the real one.
- **gf180mcuD (or the curated deck) publishes a Poly2 or Contact
  current-density limit.** The EM verdict becomes gradeable rather than
  `pass_partial`, and the in-sub-block risers — untouched here — become the
  thing to check.
- **#379 concludes on-die decoupling is required.** Decap is geometry, and
  it lands on the same rails these straps now carry.
- **The floorplan moves `SWITCH_CMP_GAP` or the bridge's column plan.**
  Both strap corridors are derived from that plan;
  `geo.stitch_metal2`'s own clearance assertion fails loudly rather than
  drawing a short, but the pitch choice above would need re-deriving.
