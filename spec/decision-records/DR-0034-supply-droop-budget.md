# DR-0034: on-die supply droop is budgeted at 33 mV combined, a tenth of the ratified ±10 % supply window

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-22
- **Decided by**: Builder agent, issue #346
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #346 (the IR/EM read that needed a budget to be graded
  against), #330 and `layout/erc/` (the structural run that found the
  geometry this prices), `layout/power/` (the flow this budget grades),
  `sim/adc-rail-current/` (the measured rail current the read is driven
  from), [DR-0006](DR-0006-spec-ratification.md) (the ratification this
  budget is derived from) and
  [DR-0004](DR-0004-device-flavor.md) (the Supply row itself),
  `README.md#target-specification` note **[a]** (the minority-term
  convention this reuses),
  [DR-0037](DR-0037-block-level-supply-straps-on-metal2.md) (issue #378 —
  moved the block-level straps to Metal2, which retires one of this
  record's Consequences; the budget is unchanged)

## Context

`layout/erc/`'s `klt erc` run (issue #330, record
`20260921-105407-3922180`) established that `ADC_BLOCK`'s `vdd` and `vss`
each resolve to exactly one electrical island — and that **neither rail has
any geometry above Metal1**: block-level continuity runs through Metal1
trunks stitched by Poly2 risers. Item 11 grades the *structural* question
and stops there. Issue #346 asks the analysis question: is that rail
electrically adequate?

It is not gradeable, because **this repo has no supply-droop budget**. A
`git grep` of `spec/` for droop/IR-drop finds a common-mode droop remark in
`prior-art-survey.md` and per-block supply-axis sweeps, and nothing that
says how much on-die droop is acceptable. Without one, an IR-drop number is
a number, not a verdict — and CLAUDE.md is explicit that agents do not
invent or relax the ratified spec to make a result pass. So the budget has
to be *derived* from something already ratified, and recorded, before the
read means anything.

## Decision

**The combined on-die supply degradation — `vdd` droop plus `vss` bounce,
measured at any one of `ADC_BLOCK`'s four labelled sub-block sites
(`ADC_DECODE_BANK_N`, `ADC_DECODE_BANK_P`, `ADC_TOP_SW`, `COMPARATOR`) —
is budgeted at 33 mV**, evaluated as a static (DC) drop at the block's
worst-corner *average* supply current.

The derivation is two steps, both from already-ratified material:

1. **What the droop eats into.** The ratified Supply row
   (`README.md#target-specification`, [DR-0004](DR-0004-device-flavor.md),
   ratified by [DR-0006](DR-0006-spec-ratification.md)) is `V_DD = 3.3 V
   ±10 %`, i.e. the 2.97 / 3.30 / 3.63 V grid, and the row's own binding
   condition is that *"every performance row holds across 2.97–3.63 V"*.
   That grid is the voltage at the block's supply **pin**. On-die droop is
   subtracted from it: a sub-block sitting behind `Δ` of droop sees
   `V_pin − Δ`. At the ratified worst-case pin voltage of 2.97 V, any
   droop at all puts that sub-block **below** the floor every ratified
   performance row is evidenced at. The ±10 % window is therefore what the
   droop consumes, and the full 330 mV of it is already spoken for by the
   supply tolerance itself.

2. **How much of it droop may have.** `README.md`'s note **[a]** states
   this repo's own convention for exactly this situation — *"the same
   'keep it a minority term' convention as DR-0003's jitter budget"* — and
   applies it twice: the CMRR row is set so a 100 mV common-mode
   disturbance contributes *"under a tenth of the 1.61 mV rms
   non-quantization budget"*, and the SFDR row is set 6 dB above the
   required SNDR on the same reasoning. Applying the same one-tenth to the
   window droop shares: **0.10 × 330 mV = 33 mV**.

The budget is stated as `vdd` droop **plus** `vss` bounce because both
subtract from the same quantity — the voltage difference a sub-block's
devices actually see between their own rails — and this block's ground
return runs through the same Poly2 risers its supply does, so the two are
the same order of magnitude rather than one dominating.

It is evaluated at the **average** current, not the peak, because it is a
budget on a *static* drop. A static solve fed a switching peak reports the
drop a purely resistive network with no charge storage would develop, which
is an upper bound rather than a prediction; what the block needs at the
peak is decoupling, which is a separate question this record does not
settle (see Consequences).

## Alternatives considered

- **Derive the budget from a measured supply sensitivity of a ratified
  performance row** (e.g. comparator offset or preamp gain vs `V_DD`) —
  not chosen, and this is the alternative that would have been *better* had
  the evidence supported it. The existing evidence does not: the comparator
  offset deck (`sim/comparator-offset/`, record
  `20260806-233045-56be937`) is a zero-mismatch deck, so its `sym_uv`
  offset is ~1e-9 V by construction at every supply and yields no
  sensitivity at all; its preamp gain `av_nom` moves only ~0.06 % across
  the whole ±330 mV window (15.7745 → 15.7654 at `tt_27c`), which would
  imply a budget of hundreds of millivolts — far looser than the one
  adopted here, and resting on one block's one parameter rather than on
  the whole ratified table. A sensitivity-derived budget is the right
  long-term form; it needs a deck that sweeps supply *with* mismatch, and
  that deck does not exist. Recording the loose number this route implies
  is useful anyway: it says the 33 mV adopted above is **conservative**
  with respect to the comparator, not optimistic.
- **Budget the droop at the switching peak rather than the average** — not
  chosen. The peak current `sim/adc-rail-current/` measures is a
  sub-nanosecond CDAC-switching event two to three orders of magnitude
  above the average. A static resistive solve at that current reports a
  drop larger than the supply itself, which is not a physical prediction
  but a statement that the DC path alone cannot source the peak — true of
  essentially every real block, and the reason decoupling exists. Budgeting
  against it would make the budget unfailable-or-always-failed depending on
  an arbitrary choice, and would hide the real question (how much
  decoupling) rather than pose it.
- **No budget; report the droop as a bare number** — not chosen. It is
  what the repo has today, and it is exactly why #346 could not be
  answered. "Verification is the product" means a recorded number has a
  verdict attached or it is not evidence.
- **A tighter budget — e.g. 1 % of `V_DD` (33 mV happens to be that too,
  by coincidence of arithmetic) or 10 mV** — not chosen as the *stated*
  derivation. 33 mV is adopted because it follows from the ratified supply
  window and this repo's own stated minority-term convention, not because
  it is a round fraction of the nominal rail. The distinction matters: if a
  future record changes the supply tolerance, this budget moves with it.

## Consequences

- **#346's read becomes gradeable.** `layout/power/cases.json` cites this
  record and grades every case against the 33 mV figure; a case that
  exceeds it is a recorded FAIL rather than an uninterpreted number.
- **The verdict is close to the line, and that is a real cost.** At the
  measured worst-corner average current the combined droop at the worst
  site is single-digit to low-tens of millivolts depending on *where the
  supply is landed* and on the resistance corner — i.e. this budget is not
  a formality this block passes by three orders of magnitude, and a
  pessimistic-corner or ill-chosen-landing-site case exceeds it. See
  `layout/power/records/` for the numbers and `layout/power/README.md` for
  what follows.
- **Where the supply is landed becomes a spec-relevant choice, not a
  layout detail.** `ADC_BLOCK` has no supply pad of its own; it has four
  labelled sites, and this budget is met or missed depending on which one
  a parent connects. That is now a stated constraint on integrating this
  block, and it did not exist before this record.
  > **Retired 2026-09-23 by [DR-0037](DR-0037-block-level-supply-straps-on-metal2.md)
  > (issue #378).** This bullet was true of `adc_block.gds` `ae4e8964…`,
  > whose block-level straps were Poly2. They are Metal2 now, and all four
  > labelled sites meet this budget at both the nominal and the pessimistic
  > resistance corner (worst 17.184 mV, 1.9× inside). The budget itself,
  > its derivation and its `proposed` status are unchanged — only this
  > consequence of the old geometry is. Annotated in place rather than
  > superseded because this record is still `proposed` (see
  > `README.md` § "Superseding a ratified record").
- **This record does NOT settle decoupling.** It deliberately budgets only
  the static drop. The peak-current behaviour of this rail is governed by
  on-die and package decoupling that this block neither draws nor
  specifies, and the `layout/power/` peak-current case is recorded as an
  upper bound with that stated. A decoupling budget is separate work.
- **It is proposed, not ratified.** It changes what the spec requires, so
  it needs operator sign-off like every other spec change here
  (DR-0006). Until then, `layout/power/`'s verdicts are graded against a
  *proposed* budget, and every record that cites it says so.
- **If the supply tolerance ever changes, this budget changes with it.**
  The 33 mV is `0.10 × (2 × 10 % × 3.3 V)`, not a constant; a record that
  supersedes the Supply row must supersede this one too.

## Spec lines affected

- `README.md#target-specification` — Supply — clarified (no value change).
  The `V_DD = 3.3 V ±10 %` row is unchanged; this record states what part
  of that window on-die droop may consume, which the row did not say.
- `spec/<supply-budget>.md#on-die-droop` (pending #1's successor — no
  ratified `spec/` file carries supply budgets today; the ratified table
  lives in `README.md`) — on-die supply droop, combined `vdd` + `vss` — new
  (`—` -> `≤ 33 mV at any labelled sub-block site, static, at the
  worst-corner average current`).
