# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

- **#413**: spec(DR-0033): ratify DR-0033 and supersede DR-0029 (#363 Part B gate)

## Operator Priority

Issues the operator starred (`loom:operator-priority`); land these first.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off
- **#392**: sim(vcm): re-take the extracted V_cm pair against the post-#381 re-extraction
- **#420**: Dedupe resolve_klt()/latest_record() from run_erc.py and run_power.py into klt_env.py

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#413**: spec(DR-0033): ratify DR-0033 and supersede DR-0029 (#363 Part B gate)

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)*
- **#392**: sim(vcm): re-take the extracted V_cm pair against the post-#381 re-extraction *(curated)*

## Proposed (Architect / Hermit)

- **#421**: README: relocate the over-long State-table cells (Schematics/Layout/Verification suite) to docs/ and check the Layout area figure *(architect)*

## Epics

_None._

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Operator priority | 1 |
| Ready (`loom:issue`) | 4 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 3 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
