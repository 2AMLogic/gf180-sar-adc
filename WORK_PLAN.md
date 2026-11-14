# Work Plan

Current queue from GitHub labels. Updated through Guide document maintenance.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#800**: Rank candidate fixes for the cold-corner ENOB/SFDR distortion shortfall (investigation record)

## Important

`loom:important`; taken before unlabelled work.

- **#363**: Reconcile the tie deck's DR-0029 citations: one stale claim to fix now (#337), one gated on DR-0033's sign-off
- **#778**: Re-qualify sar-logic-timing-gates-lt and -xl on the regenerated decks under open_pdks f6eeac7 (part of #753)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#778**: Re-qualify sar-logic-timing-gates-lt and -xl on the regenerated decks under open_pdks f6eeac7 (part of #753)
- **#794**: Collapse four duplicated build_yield_evidence.py emitters onto one shared sim/tools helper

## In Progress

Issues currently being built (`loom:building`).

- **#605**: comparator-kickback tb.json note: ~1 uV meas floor claim is stale under batch fleet (numdgt=10)
- **#793**: Remove _find_pmos_body_nets: dead back-compat alias with zero callers, and the docstring that still cites it
- **#795**: Consolidate the forked CLI/record-tail plumbing in the four layout/ evidence runners onto klt_env
- **#801**: Finish #589's hasher consolidation: remove spef_audit.sha256_file and run_extract_parasitics._sha256

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#796**: docs: roadmap as of 2026-11-13
- **#802**: refactor: route every flow-tree file hash through the one shared sha256
- **#803**: refactor(parasitics): drop the zero-caller PMOS-body alias and re-point the docstring at the real guard
- **#806**: refactor: consolidate the four layout/ runners' record plumbing onto klt_env

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

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
- **#778**: Re-qualify sar-logic-timing-gates-lt and -xl on the regenerated decks under open_pdks f6eeac7 (part of #753) *(curated)*
- **#779**: Re-qualify sar-logic-functional-gates under open_pdks f6eeac7 and repair its supersession tip (part of #753) *(curated)*
- **#798**: Triage the LVS and ERC --check deltas under the klt release #652 targets (part of #652) *(curated)*
- **#799**: Record what the newer klt power schema requires of the committed power specs (part of #652) *(curated)*

## Proposed (Architect / Hermit)

- **#748**: Remove sta_sar_ctrl.py: superseded pre-route STA driver *(hermit)*
- **#769**: Remove superseded adc_tgate_dum sampling switch: its stated consumer is gone, yet it is still drawn, DRC'd and LVS'd *(hermit)*
- **#774**: Remove comparator_nores layout variant: its LVS reference is a strict subset of the full comparator case *(hermit)*
- **#776**: Remove the always-empty merges plumbing from the LVS reference generators *(hermit)*
- **#804**: Candidate LVS requests and reference netlists document the production request path, not their own *(hermit)*
- **#805**: Re-baseline or retire the evidence-footprint ceilings: all three are breached, so check:ci's last step signals nothing *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 2 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 4 |
| Approved PRs awaiting merge | 0 |
| Curated | 22 |
| Architect / Hermit proposals | 6 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
