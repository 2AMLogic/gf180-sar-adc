# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

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

## In Progress

Issues currently being built (`loom:building`).

- **#576**: Drop the loom-ui result step from nightly-pdk (CI pushes nothing; no OIDC)
- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10)
- **#615**: Re-qualify dr0014-sampling records under open_pdks f6eeac7 (part of #595)
- **#616**: Re-qualify dr0019-cu-sweep, acq-leg-width-sweep (x1.1..x2.068), vcm-drive-impedance under open_pdks f6eeac7 (part of #595)
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#620**: docs: record #617 re-qualification refused by saturated batch fleet

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#577**: ci: drop loom-ui OIDC result step from nightly-pdk

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)*
- **#429**: Measure intermediate acquisition-leg widths before choosing an ENOB/SFDR recovery candidate *(curated)*
- **#430**: Establish extracted ENOB/SFDR temperature coverage beyond the hot-only FFT subset *(curated)*
- **#460**: sim(sar-logic-timing): re-take the Clock row's supply-axis grid on the #371-corrected deck *(curated)*
- **#468**: sim(harness): record platform, full ngspice banner and ngspice front-end mode in every record (follow-up to #459) *(curated)*
- **#518**: nightly-pdk: confirm ciel -l gf180mcu_fd_pr install still provides libs.ref standard-cell SPICE for gate-level replay tests *(curated)*
- **#576**: Drop the loom-ui result step from nightly-pdk (CI pushes nothing; no OIDC) *(curated)*
- **#594**: Re-qualify ADC-level records (INL/DNL, ENOB, power, offset MC) under open_pdks f6eeac7 (part of #515) *(curated)*
- **#595**: Re-qualify timing/switching/sampling records under open_pdks f6eeac7 (part of #515) *(curated)*
- **#596**: Re-qualify sar-logic flow, parasitics and LVS reports under open_pdks f6eeac7 (part of #515) *(curated)*
- **#599**: Re-qualify device-* characterization records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#601**: Re-qualify cdac-bit-settling, top-plate-cpar, smoke-sar-bias, adc-block-pex records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10) *(curated)*
- **#609**: Re-qualify comparator-offset-gof/-offset-mc/-preamp-noise records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#615**: Re-qualify dr0014-sampling records under open_pdks f6eeac7 (part of #595) *(curated)*
- **#616**: Re-qualify dr0019-cu-sweep, acq-leg-width-sweep (x1.1..x2.068), vcm-drive-impedance under open_pdks f6eeac7 (part of #595) *(curated)*
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595) *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 5 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 1 |
| Curated | 18 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
