# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
_Generated: 2026-11-20T18:55:00Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#854**: Fix cold-corner sequencing failures on sar_ctrl_a (tt_-40c ring degeneration, sf_-40c stall, ss_-40c wrong decision + sel overshoot) *(held)*

## Important

`loom:important`; taken before unlabelled work.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(held)*
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595) *(held)*
- **#652**: Bump klayout-tools pin 0.6.0, 0.7.0, 4 dev commits → 0.8.0 *(held)*
- **#838**: layout: clear SB.10 on the comparator load resistors with the fixed extraction deck *(held)*
- **#867**: Re-take the block PEX and the five extracted campaigns after the 0.8.0 layout family (T1 item 7 reports input: CHANGED) *(held)*

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#934**: Reconcile the T1 tracker #640 and the stale park records on its row issues (#641, #645, #652, #594, #643)
- **#935**: ENOB/SFDR: run the C1 measurement the #800 ranking put first (256-sample extracted re-capture at the cold governing corner on the baseline netlist, C2 folded in)

## In Progress

Issues currently being built (`loom:building`).

- **#936**: layout: next area iteration toward the ratified < 0.1 mm^2 - re-take the per-sub-block area accounting on the current floorplan and build one decode-bank lever as a measured candidate

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)* *(held)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)* *(held)*
- **#464**: Auditor Capability Request: Python 3 unavailable on audit host *(curated)* *(held)*
- **#486**: Retry SAR extracted timing after SPEF alias and annotation capability fixes *(curated)* *(held)*
- **#594**: Re-qualify ADC-level records (INL/DNL, ENOB, power, offset MC) under open_pdks f6eeac7 (part of #515) *(curated)* *(held)*
- **#595**: Re-qualify timing/switching/sampling records under open_pdks f6eeac7 (part of #515) *(curated)* *(held)*
- **#596**: Re-qualify sar-logic flow, parasitics and LVS reports under open_pdks f6eeac7 (part of #515) *(curated)* *(held)*
- **#599**: Re-qualify device-* characterization records under open_pdks f6eeac7 (part of #593) *(curated)* *(held)*
- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10) *(curated)* *(held)*
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595) *(curated)* *(held)*
- **#641**: T1 item 3 (DRC clean, digital): clear the 208 endcap/filltie markers on the sar_ctrl macro and re-mint a clean klt drc envelope *(curated)* *(held)*
- **#652**: Bump klayout-tools pin 0.6.0, 0.7.0, 4 dev commits → 0.8.0 *(curated)* *(held)*
- **#654**: T1 item 6 (Monte Carlo, analog): declare the statistical row set and run the comparator-inclusive ADC_BLOCK offset population *(curated)* *(held)*
- **#655**: ADC_BLOCK comparator-inclusive offset 3σ Monte Carlo population + klt yield report (split from #654) *(curated)* *(held)*
- **#659**: Consolidate duplicated klt JSON-run wrappers onto flow_env.run_klt_json *(curated)* *(held)*
- **#753**: Re-qualify the seven gate-level SAR-logic grids under open_pdks f6eeac7 (part of #596) *(curated)* *(held)*
- **#765**: DR-0023's 'no 3.3 V-device standard-cell library' premise does not reproduce at open_pdks f6eeac7 (OSU gp9t3v3 / gp12t3v3 ship) *(curated)* *(held)*
- **#817**: Dedup: synth_sar_ctrl.py reimplements flow_env.working_tree_dirty *(curated)* *(held)*
- **#838**: layout: clear SB.10 on the comparator load resistors with the fixed extraction deck *(curated)* *(held)*
- **#854**: Fix cold-corner sequencing failures on sar_ctrl_a (tt_-40c ring degeneration, sf_-40c stall, ss_-40c wrong decision + sel overshoot) *(curated)* *(held)*
- **#863**: tb_kickback.spice header still calls the fixed-V_cm excitation the converter's 'actual operating condition' *(curated)* *(held)*
- **#934**: Reconcile the T1 tracker #640 and the stale park records on its row issues (#641, #645, #652, #594, #643) *(curated)*
- **#935**: ENOB/SFDR: run the C1 measurement the #800 ranking put first (256-sample extracted re-capture at the cold governing corner on the baseline netlist, C2 folded in) *(curated)*
- **#936**: layout: next area iteration toward the ratified < 0.1 mm^2 - re-take the per-sub-block area accounting on the current floorplan and build one decode-bank lever as a measured candidate *(curated)*
- **#937**: T1 item 5 (analog), first increment of #643: cite the klt sim envelopes that already exist for campaigns re-qualified under open_pdks f6eeac7, declare every other ratified row a gap *(curated)* *(held)*

## Proposed (Architect / Hermit)

- **#748**: Remove sta_sar_ctrl.py: superseded pre-route STA driver *(hermit)* *(held)*
- **#769**: Remove superseded adc_tgate_dum sampling switch: its stated consumer is gone, yet it is still drawn, DRC'd and LVS'd *(hermit)* *(held)*
- **#774**: Remove comparator_nores layout variant: its LVS reference is a strict subset of the full comparator case *(hermit)* *(held)*
- **#776**: Remove the always-empty merges plumbing from the LVS reference generators *(hermit)* *(held)*
- **#810**: Remove the sim-harness's 15 never-used CLI evidence-override flags: one of them is why Monte Carlo records print "not a distribution claim" *(hermit)* *(held)*
- **#817**: Dedup: synth_sar_ctrl.py reimplements flow_env.working_tree_dirty *(hermit)* *(held)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 5 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 2 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 25 |
| Architect / Hermit proposals | 6 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
