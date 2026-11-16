# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#830**: layout: add --verify-generators control-cell reproducibility check

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595)
- **#854**: Fix cold-corner sequencing failures on sar_ctrl_a (tt_-40c ring degeneration, sf_-40c stall, ss_-40c wrong decision + sel overshoot)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#518**: nightly-pdk: confirm ciel -l gf180mcu_fd_pr install still provides libs.ref standard-cell SPICE for gate-level replay tests
- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10)
- **#836**: layout: draw source/drain implants so comp.coverage.1 (DF.12) passes under the klt 0.8.0 deck
- **#854**: Fix cold-corner sequencing failures on sar_ctrl_a (tt_-40c ring degeneration, sf_-40c stall, ss_-40c wrong decision + sel overshoot)
- **#869**: layout/adc-top/README.md § Results: the 'Latest records' block is now stale at the top of the chain (3 unlinked 20261116 records, wrong adc_top.gds hash)

## In Progress

Issues currently being built (`loom:building`).

- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#830**: layout: add --verify-generators control-cell reproducibility check

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)*
- **#464**: Auditor Capability Request: Python 3 unavailable on audit host *(curated)*
- **#486**: Retry SAR extracted timing after SPEF alias and annotation capability fixes *(curated)*
- **#594**: Re-qualify ADC-level records (INL/DNL, ENOB, power, offset MC) under open_pdks f6eeac7 (part of #515) *(curated)*
- **#595**: Re-qualify timing/switching/sampling records under open_pdks f6eeac7 (part of #515) *(curated)*
- **#596**: Re-qualify sar-logic flow, parasitics and LVS reports under open_pdks f6eeac7 (part of #515) *(curated)*
- **#599**: Re-qualify device-* characterization records under open_pdks f6eeac7 (part of #593) *(curated)*
- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10) *(curated)*
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595) *(curated)*
- **#641**: T1 item 3 (DRC clean, digital): clear the 208 endcap/filltie markers on the sar_ctrl macro and re-mint a clean klt drc envelope *(curated)*
- **#652**: Bump klayout-tools pin 0.6.0, 0.7.0, 4 dev commits → 0.8.0 *(curated)*
- **#654**: T1 item 6 (Monte Carlo, analog): declare the statistical row set and run the comparator-inclusive ADC_BLOCK offset population *(curated)*
- **#655**: ADC_BLOCK comparator-inclusive offset 3σ Monte Carlo population + klt yield report (split from #654) *(curated)*
- **#659**: Consolidate duplicated klt JSON-run wrappers onto flow_env.run_klt_json *(curated)*
- **#753**: Re-qualify the seven gate-level SAR-logic grids under open_pdks f6eeac7 (part of #596) *(curated)*
- **#765**: DR-0023's 'no 3.3 V-device standard-cell library' premise does not reproduce at open_pdks f6eeac7 (OSU gp9t3v3 / gp12t3v3 ship) *(curated)*
- **#777**: Re-qualify sar-logic-timing-gates-tie on the regenerated deck under open_pdks f6eeac7 (part of #753) *(curated)*
- **#817**: Dedup: synth_sar_ctrl.py reimplements flow_env.working_tree_dirty *(curated)*
- **#821**: No automated check that the control-cell generators still reproduce their committed GDS *(curated)*
- **#836**: layout: draw source/drain implants so comp.coverage.1 (DF.12) passes under the klt 0.8.0 deck *(curated)*
- **#838**: layout: fix comparator resistor SAB markers for SB.10/SB.2 (poly2.enclosing.sab.1, sab.space.1 under klt 0.8.0) *(curated)*
- **#854**: Fix cold-corner sequencing failures on sar_ctrl_a (tt_-40c ring degeneration, sf_-40c stall, ss_-40c wrong decision + sel overshoot) *(curated)*
- **#863**: tb_kickback.spice header still calls the fixed-V_cm excitation the converter's 'actual operating condition' *(curated)*
- **#869**: layout/adc-top/README.md § Results: the 'Latest records' block is now stale at the top of the chain (3 unlinked 20261116 records, wrong adc_top.gds hash) *(curated)*

## Proposed (Architect / Hermit)

- **#748**: Remove sta_sar_ctrl.py: superseded pre-route STA driver *(hermit)*
- **#769**: Remove superseded adc_tgate_dum sampling switch: its stated consumer is gone, yet it is still drawn, DRC'd and LVS'd *(hermit)*
- **#774**: Remove comparator_nores layout variant: its LVS reference is a strict subset of the full comparator case *(hermit)*
- **#776**: Remove the always-empty merges plumbing from the LVS reference generators *(hermit)*
- **#810**: Remove the sim-harness's 15 never-used CLI evidence-override flags: one of them is why Monte Carlo records print "not a distribution claim" *(hermit)*
- **#817**: Dedup: synth_sar_ctrl.py reimplements flow_env.working_tree_dirty *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 3 |
| Ready (`loom:issue`) | 5 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 25 |
| Architect / Hermit proposals | 6 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
