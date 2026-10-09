# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Operator Priority

Issues the operator starred (`loom:operator-priority`); land these first.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off
- **#437**: sim: machine-check characterization-summary evidence citations against the newest campaign records
- **#438**: spec: generate and CI-check a deterministic decision-record status index

## In Progress

Issues currently being built (`loom:building`).

- **#427**: Qualify a faithful batch path for ADC_BLOCK offset Monte Carlo before the full population
- **#429**: Measure intermediate acquisition-leg widths before choosing an ENOB/SFDR recovery candidate
- **#430**: Establish extracted ENOB/SFDR temperature coverage beyond the hot-only FFT subset

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#448**: Issue #430: record 0.7.0-client batch preflight version mismatch (no points run)

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)*
- **#392**: sim(vcm): re-take the extracted V_cm pair against the post-#381 re-extraction *(curated)*
- **#427**: Qualify a faithful batch path for ADC_BLOCK offset Monte Carlo before the full population *(curated)*
- **#429**: Measure intermediate acquisition-leg widths before choosing an ENOB/SFDR recovery candidate *(curated)*
- **#430**: Establish extracted ENOB/SFDR temperature coverage beyond the hot-only FFT subset *(curated)*
- **#437**: sim: machine-check characterization-summary evidence citations against the newest campaign records *(curated)*
- **#438**: spec: generate and CI-check a deterministic decision-record status index *(curated)*

## Proposed (Architect / Hermit)

- **#439**: signoff: re-take T1 item 7 (block-scoped klt pex) across the committed 117-point grid once the batch fleet accepts the pinned klt *(architect)*

## Epics

_None._

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Operator priority | 1 |
| Ready (`loom:issue`) | 3 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 8 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
