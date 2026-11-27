# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
_Generated: 2026-11-27T02:17:00Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#413**: spec(DR-0033): ratify DR-0033 and supersede DR-0029 (#363 Part B gate)
- **#961**: ci(nightly-pdk): add a klt-parasitics job for run_extract_parasitics.py --check
- **#1026**: spec: ratify DR-0038 option 1 — offset graded as 3σ about the mean (#655)
- **#1030**: fix: derive SPEF timing record exit status; reconcile aliased nets

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#854**: Fix cold-corner sequencing failures on sar_ctrl_a (tt_-40c ring degeneration, sf_-40c stall, ss_-40c wrong decision + sel overshoot) *(held)*

## Important

`loom:important`; taken before unlabelled work.

- **#593**: Re-qualify device/comparator characterization records under open_pdks f6eeac7 (part of #515) *(held)*
- **#617**: Re-qualify vdd-switching-event, vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance under open_pdks f6eeac7 (part of #595) *(held)*
- **#652**: Bump klayout-tools pin 0.6.0, 0.7.0, 4 dev commits → 0.8.0 *(held)*
- **#838**: layout: clear SB.10 on the comparator load resistors with the fixed extraction deck *(held)*
- **#867**: Re-take the block PEX and the five extracted campaigns after the 0.8.0 layout family (T1 item 7 reports input: CHANGED) *(held)*

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#958**: No CI job exercises layout/adc-top/parasitics/run_extract_parasitics.py against real klt
- **#1028**: sar_ctrl SPEF timing: reconcile AC 2's 11 drivers, bounded README/signoff claim, fix renderer contradiction (part of #486)
- **#1036**: mc_extracted_core: a one-draw null control is vacuous but passes
- **#1066**: Re-take the governing extracted device-switch-ron record on a clean tree with installer provenance and repoint its summary citation

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#413**: spec(DR-0033): ratify DR-0033 and supersede DR-0029 (#363 Part B gate) *(held)*
- **#961**: ci(nightly-pdk): add a klt-parasitics job for run_extract_parasitics.py --check *(held)*
- **#1026**: spec: ratify DR-0038 option 1 — offset graded as 3σ about the mean (#655) *(held)*
- **#1030**: fix: derive SPEF timing record exit status; reconcile aliased nets *(held)*
- **#1039**: fix: require two parsed draws for the Monte Carlo null control

## Proposed

Issues carrying `loom:curated`.

- **#303**: Execute the full 45-point mos grid for sim/sar-logic-timing-gates/ now that #296's convergence fix has landed *(curated)* *(held)*
- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off *(curated)* *(held)*
- **#464**: Auditor Capability Request: Python 3 unavailable on audit host *(curated)* *(held)*
- **#486**: Retry SAR extracted timing after SPEF alias and annotation capability fixes *(curated)* *(held)*
- **#593**: Re-qualify device/comparator characterization records under open_pdks f6eeac7 (part of #515) *(curated)* *(held)*
- **#595**: Re-qualify timing/switching/sampling records under open_pdks f6eeac7 (part of #515) *(curated)* *(held)*
- **#596**: Re-qualify sar-logic flow, parasitics and LVS reports under open_pdks f6eeac7 (part of #515) *(curated)* *(held)*
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
- **#937**: T1 item 5 (analog), first increment of #643: cite the klt sim envelopes that already exist for campaigns re-qualified under open_pdks f6eeac7, declare every other ratified row a gap *(curated)* *(held)*
- **#958**: No CI job exercises layout/adc-top/parasitics/run_extract_parasitics.py against real klt *(curated)*
- **#1028**: sar_ctrl SPEF timing: reconcile AC 2's 11 drivers, bounded README/signoff claim, fix renderer contradiction (part of #486) *(curated)*
- **#1036**: mc_extracted_core: a one-draw null control is vacuous but passes *(curated)*
- **#1066**: Re-take the governing extracted device-switch-ron record on a clean tree with installer provenance and repoint its summary citation *(curated)*
- **#1067**: check_artifact_manifests.py verify stops at the artifact broker's per-caller rate limit after about 69 objects *(curated)* *(held)*

## Proposed (Architect / Hermit)

- **#817**: Dedup: synth_sar_ctrl.py reimplements flow_env.working_tree_dirty *(hermit)* *(held)*
- **#1050**: Remove the unused report.write_record helper and move its overwrite test to the artifact store *(hermit)* *(held)*
- **#1079**: Remove the stale DRC expectations from the proof-cell generators *(hermit)* *(held)*
- **#1087**: Run each layout generator once per DRC or LVS regeneration *(hermit)*
- **#1088**: Remove the obsolete SciPy pin follow-up from the README prerequisites *(hermit)*
- **#1089**: Remove the unused runner_expr helper from the batch exporter *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 4 |
| Very important | 1 |
| Important | 5 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 0 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 5 |
| Curated | 26 |
| Architect / Hermit proposals | 6 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
