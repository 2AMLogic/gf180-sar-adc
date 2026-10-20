# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#517**: feat(pdk): re-pin open_pdks to f6eeac7 and move PDK install/search to ciel
- **#577**: ci: drop loom-ui OIDC result step from nightly-pdk

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off
- **#550**: Remove or de-duplicate run_pex_comparator.py: superseded by run_pex_adc_block.py

## In Progress

Issues currently being built (`loom:building`).

- **#514**: Re-pin open_pdks to f6eeac7 and move PDK install/search to ciel (part of #513)
- **#576**: Drop the loom-ui result step from nightly-pdk (CI pushes nothing; no OIDC)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#517**: feat(pdk): re-pin open_pdks to f6eeac7 and move PDK install/search to ciel
- **#577**: ci: drop loom-ui OIDC result step from nightly-pdk

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)*
- **#429**: Measure intermediate acquisition-leg widths before choosing an ENOB/SFDR recovery candidate *(curated)*
- **#430**: Establish extracted ENOB/SFDR temperature coverage beyond the hot-only FFT subset *(curated)*
- **#460**: sim(sar-logic-timing): re-take the Clock row's supply-axis grid on the #371-corrected deck *(curated)*
- **#468**: sim(harness): record platform, full ngspice banner and ngspice front-end mode in every record (follow-up to #459) *(curated)*
- **#514**: Re-pin open_pdks to f6eeac7 and move PDK install/search to ciel (part of #513) *(curated)*
- **#576**: Drop the loom-ui result step from nightly-pdk (CI pushes nothing; no OIDC) *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 2 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 2 |
| Curated | 8 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
