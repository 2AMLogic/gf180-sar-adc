# DR-0006: Target specification ratified, conditional on the #33 amendments

- **Status**: ratified
- **Date**: 2026-07-31
- **Decided by**: Robb (operator, engineering ratification authority per #1); recorded by Builder agent, issue #33
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #33, #7; the operator's ratification comment
  ([#1 comment, 2026-07-31T22:14:48Z](https://github.com/2AMLogic/gf180-sar-adc/issues/1#issuecomment-5147917026));
  the spec-review opinion it accepts
  ([#1 comment, 2026-07-31T21:59:49Z](https://github.com/2AMLogic/gf180-sar-adc/issues/1#issuecomment-5147826556),
  produced by the `klayout-tools` spec-review skill, `2AMLogic/klayout-tools` #124);
  the 2026-07-28 delegation and its layout-lock gate
  ([#1 comment](https://github.com/2AMLogic/gf180-sar-adc/issues/1#issuecomment-5112532667));
  DR-0001, DR-0002, DR-0003, DR-0004, DR-0005;
  `sim/device-characterization-report.md`, `spec/prior-art-survey.md` §1.1, §1.4

## Context

The target-specification table in `README.md` has carried a DRAFT marking since
the block was scaffolded: the 2026-07-28 delegation on #1 authorized agents to
work from it for harness, survey and schematic work, but made formal operator
ratification a hard gate before any layout work locks to it. On 2026-07-31 an
expert spec review of the draft table (the `klayout-tools` spec-review skill,
`2AMLogic/klayout-tools` #124) returned **ratify-with-amendments**, listing
eight amendments — most consequentially a missing Reference row (the canonical
SAR spec failure), a missing Clock row, and a direct contradiction between the
draft's fixed 0–3.3 V input range and the ±10 % supply grid, since
`sim/device-characterization-report.md` §2.1 shows a full-scale 0–3.3 V input is
not samplable at the 2.97 V corner. Those amendments were carried as issue #33.
The operator accepted the review and ratified on that condition, which is the
decision this record fixes.

## Decision

**The target-specification table in `README.md#target-specification`, as amended
by issue #33, is the ratified spec for this block.** Where the pre-amendment
draft and the #33 amendments conflict, **the amended values govern immediately**
— there is no transition period and no dual-status table.

Consequently:

- The DRAFT marking is removed from the `## Target specification` heading; the
  table is now normative, and a change to it requires a new decision record
  superseding this one (CLAUDE.md: agents do not relax the ratified spec to make
  results pass).
- DR-0001 through DR-0005, all of which were `proposed — requires operator
  sign-off`, are **ratified** by the same decision: each is either published as
  a row of the amended table (DR-0002 Reference, DR-0003 Clock, DR-0004 Supply)
  or is a condition on one (DR-0001 Input / Input structure, DR-0005 Interface).
  Their Status fields are updated to `ratified`; nothing else in them is touched.
- The table's targets remain **targets, not results**. Ratification fixes what
  must be proven; it asserts nothing about what has been measured.

## Alternatives considered

- **Ratify the draft table as-is, deferring the amendments to a later record** —
  not chosen. The review found the amendments load-bearing rather than cosmetic:
  a SAR spec with no Reference row omits the parameter that sets full scale,
  drive and decoupling, and the input-range/supply contradiction is a defect that
  would have been ratified *into* the normative spec and then budgeted against by
  #8/#9/#10/#12/#13. Ratifying a known-contradictory table to save one revision
  is the exact failure mode #1's own curation warned about — "a spec amended
  after those budgets close forces rework across the whole queue."
- **Defer ratification pending further analysis of the amendments** — not chosen.
  Every amendment is derivable from evidence already merged on `main`
  (DR-0001..0004, `sim/device-characterization-report.md`,
  `spec/prior-art-survey.md`); none required a new testbench or a new
  measurement. Deferring would have held the layout-lock gate closed for
  transcription work, at no gain in confidence.
- **Ratify only the uncontested rows and leave the amended ones DRAFT** — not
  chosen. A partially-ratified table gives downstream issues no single answer to
  the question "may I lock to this?", and the contested rows are precisely the
  ones layout-stage work needs (supply, reference, input structure).

## Consequences

- **The layout-lock gate of the 2026-07-28 delegation is satisfied** once the
  amended table is on `main`. Layout-stage issues (#15–#17) may unblock; they
  lock to the amended values, not to the draft.
- **#1 closes** with this record as its durable artifact. The ratification
  rationale now lives in `spec/`, not only in an issue comment thread.
- **The table is no longer freely editable.** Any subsequent change — including
  relaxing a target that a testbench fails — needs a new record superseding this
  one. That is a real cost: it makes correcting an error in the amended table
  slower than it was yesterday, deliberately.
- **Ratification does not convert placeholders into evidence.** Several ratified
  rows rest on values this repo has flagged as unverified — most importantly
  `A_C = 2.0 %·µm`, a derated planning placeholder with **no verified citation**
  pending foundry MiM matching data (`sim/device-characterization-report.md`
  §5.1), and the 34 pF planning array size that follows from it (pending #8).
  Ratifying the table fixes the *targets*; it does not promote those inputs, and
  a future foundry number may force a superseding record.
- **Hold-droop and leakage figures stay lower bounds.** The gf180mcu FET cards
  carry no junction saturation-current density (§5.2), so the ratified droop line
  is bounded below, not characterized. Budgeting junction leakage from foundry
  data remains open work for #8/#10.
- **The block is ratified as reference-, clock-, and driver-dependent** (DR-0001,
  DR-0002, DR-0003). Those integration requirements are now spec, so the eventual
  datasheet must publish them plainly rather than treat them as internal
  assumptions.

## Spec lines affected

- `README.md#target-specification` — table status — changed (`DRAFT — engineering
  to ratify, see issue #1` -> ratified; the amended table content is the diff in
  the PR that lands this record, per #33).
- `spec/decision-records/DR-0001-input-drive.md` — Status — changed (`proposed`
  -> `ratified`).
- `spec/decision-records/DR-0002-reference-source.md` — Status — changed
  (`proposed` -> `ratified`).
- `spec/decision-records/DR-0003-clocking.md` — Status — changed (`proposed` ->
  `ratified`).
- `spec/decision-records/DR-0004-device-flavor.md` — Status — changed (`proposed`
  -> `ratified`).
- `spec/decision-records/DR-0005-interface-scope.md` — Status — changed
  (`proposed` -> `ratified`).
