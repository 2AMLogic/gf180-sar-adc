# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#659**: Consolidate duplicated klt JSON-run wrappers onto flow_env.run_klt_json

## In Progress

Issues currently being built (`loom:building`).

- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)*
- **#429**: Measure intermediate acquisition-leg widths before choosing an ENOB/SFDR recovery candidate *(curated)*
- **#430**: Establish extracted ENOB/SFDR temperature coverage beyond the hot-only FFT subset *(curated)*
- **#460**: sim(sar-logic-timing): re-take the Clock row's supply-axis grid on the #371-corrected deck *(curated)*
- **#468**: sim(harness): record platform, full ngspice banner and ngspice front-end mode in every record (follow-up to #459) *(curated)*
- **#594**: Re-qualify ADC-level records (INL/DNL, ENOB, power, offset MC) under open_pdks f6eeac7 (part of #515) *(curated)*
- **#595**: Re-qualify timing/switching/sampling records under open_pdks f6eeac7 (part of #515) *(curated)*
- **#596**: Re-qualify sar-logic flow, parasitics and LVS reports under open_pdks f6eeac7 (part of #515) *(curated)*
- **#599**: Re-qualify device-* characterization records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#601**: Re-qualify cdac-bit-settling, top-plate-cpar, smoke-sar-bias, adc-block-pex records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10) *(curated)*
- **#609**: Re-qualify comparator-offset-gof/-offset-mc/-preamp-noise records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#616**: Re-qualify dr0019-cu-sweep, acq-leg-width-sweep (x1.1..x2.068), vcm-drive-impedance under open_pdks f6eeac7 (part of #595) *(curated)*
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595) *(curated)*
- **#632**: Nightly PDK check failed (sim/selftest.sh stages 2-4) *(curated)*
- **#641**: T1 item 3 (DRC clean, digital): clear the 208 endcap/filltie markers on the sar_ctrl macro and re-mint a clean klt drc envelope *(curated)*
- **#652**: Bump klayout-tools pin 0.6.0, 0.7.0, 4 dev commits → 0.8.0 *(curated)*
- **#654**: T1 item 6 (Monte Carlo, analog): declare the statistical row set and run the comparator-inclusive ADC_BLOCK offset population *(curated)*
- **#659**: Consolidate duplicated klt JSON-run wrappers onto flow_env.run_klt_json *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 20 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
