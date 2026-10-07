# Work Log

Merged pull requests and closed issues from the initial 30-day lookback (2026-09-07 onward). Earlier activity remains in GitHub history. Guide document maintenance PRs are excluded.

### 2026-09-24

- **PR #402**: signoff: extend the current-record check to the repo-root README.md
- **PR #401**: refactor(layout): dedupe klt_identity() into klt_env.py
- **PR #398**: signoff: check README.md's current-record pointer instead of hand-maintaining it
- **PR #396**: fix(sim): correct the V_cm ammeter polarity and withdraw the sign-flipped p_total figure
- **Issue #400** (closed): Dedupe klt_identity() between layout/erc/run_erc.py and layout/power/run_power.py
- **Issue #399** (closed): signoff: repo-root README.md names the same two-re-grades-stale record, outside #397's new check
- **Issue #397** (closed): signoff: README.md's "Current verdict" block names a record two re-grades stale
- **Issue #395** (closed): sim(vcm): the #358 power pair's ammeter flipped i(vcms)'s sign between its arms -- p_total in the vcmnet arm is understated by 2x|p_vcm|
- **Issue #382** (closed): layout(adc-top): contacts fail the PDK runset's CO.1 exact-size rule and MOSFETs fail DF.6/PL.4/PL.5, and the PDK runset has no committed runner

### 2026-09-23

- **PR #394**: docs(sim): reconcile the characterization summary's Supply row with DR-0036's proposed V_DD decoupling budget
- **PR #391**: sim(vcm): re-run the ratified decks against a real V_cm network at full PVT (#358)
- **PR #390**: extract(parasitics): re-extract against the tapped Metal2-strapped GDS, retire the body-tie rewrite, and re-run all five post-layout campaigns
- **PR #388**: layout,power: carry ADC_BLOCK's block-level supply straps on Metal2, making the droop verdict landing-site independent
- **PR #387**: spec(DR-0036): budget the V_DD switching transient as charge, and require an on-die term inside ADC_BLOCK
- **PR #385**: sim/harness: reserve record-id atomically to stop same-second collisions
- **PR #384**: layout(adc-top): draw and route 25 n-well taps, close and strap both substrate-tie rings
- **PR #380**: power: measure ADC_BLOCK's Poly2-stitched supply rails for IR drop and EM, and budget the droop (#346)
- **Issue #389** (closed): docs(sim): reconcile characterization-summary's Supply row with DR-0036's post-#387 ratified budget
- **Issue #383** (closed): sim(parasitics): re-extract and re-run the five extracted campaigns against #356's tapped geometry
- **Issue #381** (closed): layout(adc-top): re-extract parasitics and re-run the post-layout campaigns against the tapped GDS (post-#356)
- **Issue #379** (closed): No V_DD decoupling budget exists, and the measured CDAC switching peak is 860x the average supply current
- **Issue #378** (closed): ADC_BLOCK's supply droop verdict depends on where the parent lands the supply: carry the rails above Metal1, or ratify the landing-site constraint
- **Issue #377** (closed): sim/harness: concurrent run_corners.py runs of one experiment in the same second collide on record id
- **Issue #358** (closed): Re-run the three ADC-level decks against a real V_cm network at full PVT (DR-0026's named follow-up)
- **Issue #356** (closed): layout(adc-top): no n-well tap is drawn in any of ADC_BLOCK's 25 wells, and both substrate-tie rings reach no supply
- **Issue #346** (closed): No supply geometry above Metal1: both rails are stitched block-to-block through Poly2 risers, and no IR/EM read exists

### 2026-09-22

- **PR #375**: docs: re-point stale SAR-sequencer record citations (#357)
- **PR #374**: docs(sar-logic): replace the tie grid's "not yet attributable" 512 claim with #337's measured decode transient
- **PR #373**: chore(reuse): add reuse.lock.json recording the in-tree comparator as undecided against sibling gf180-comparator
- **PR #372**: sim: locate the delay-line decks' step-control collapse at the line's termination node
- **PR #371**: sim(sar-logic): gate the code-error measurement on a settled drdy and start it after the discarded first conversion
- **Issue #366** (closed): 2am: reuse rule 9 — in-tree comparator (preamp + StrongARM latch) duplicates sibling canary gf180-comparator — add reuse.lock.json in_tree entry (evaluate), then adopt or record
- **Issue #357** (closed): Stale SAR-sequencer record citations in testbench-suite-memo, timing-budget-memo and the Chipalooza proposal
- **Issue #343** (closed): sar-logic-timing-gates-{lt,xl,bad}: every point that reaches a verdict aborts with Timestep too small at 15-32% of the ratified transient, and the ideal lossless transmission line is the only structural difference from the deck that passes
- **Issue #327** (closed): Correct the gate-level code-error measurement: start after the discarded first conversion, and strobe after the output register settles (DR-0029 part 2)

### 2026-09-21

- **PR #369**: test: enforce spec/decision-records DR-NNNN one-number-one-record rule
- **PR #368**: signoff: teach run_signoff.py item 11's compound evidence list, then cite the klt erc report
- **PR #367**: refactor(sar-logic): one provenance implementation for the flow drivers (#352)
- **PR #365**: docs(erc): correct the Metal1 disjoint-polygon count for vdd/vss (3 -> 4) (#349)
- **PR #364**: spec(DR-0033): price sf_27c_2.97v's non-convergence as attributed coverage rather than change the tie loop
- **PR #362**: sim/harness: never score a mid-transient abort as a completed point (#341)
- **PR #361**: signoff: cite T1 item 8 on both partitions via generic evidence envelopes (#339)
- **PR #360**: fix(layout,signoff): bump klt to close T1 item 4's unpinned LVS citation
- **PR #359**: feat(erc): settle ADC_BLOCK's well-tie question from geometry (DR-0032)
- **PR #355**: sim(sar-logic-timing-gates-tie): root-cause tie_code_deviation=512 to the output register read mid-carry
- **PR #354**: spec: renumber the power-up first-conversion record DR-0029 -> DR-0031 (#335)
- **PR #351**: sim(sar-logic-functional{,-gates}): add iso_skew_ns cross-loop asymmetry check
- **PR #350**: sim(sar-logic-timing-gates-tie): root-cause the sf_27c_2.97v abort to a hard sign test at the floating-point ulp on a quiescent supply row
- **PR #348**: feat(erc): stand up klt erc and record ADC_BLOCK's structural supply read
- **PR #344**: sim(sar-logic-timing-gates-{lt,xl}): both 45-point grids ran, and neither completed a single ratified transient (#303)
- **PR #342**: feat(signoff): commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **Issue #353** (closed): spec/decision-records/: nothing enforces the README's one-number-one-record rule, so a DR-NNNN collision can only be caught by hand
- **Issue #352** (closed): Dedupe _run/_git/_git_status_porcelain/klt_version/record_id between synth_sar_ctrl.py and pnr_sar_ctrl.py
- **Issue #349** (closed): layout/erc/README.md: the "three disjoint polygons" Metal1 count for vdd does not reproduce (measures 4)
- **Issue #347** (closed): signoff: teach run_signoff.py item 11's compound evidence list, then cite the klt erc report
- **Issue #345** (closed): DR-0029's supersede trigger is met: write the successor record for the tie loop's near-metastable model
- **Issue #341** (closed): sim/harness: a point whose transient aborts mid-run is scored as a completed PASS when the manifest has one measurement
- **Issue #340** (closed): adc_block.gds draws no implant or tap geometry, so klt erc's erc.missing_tie is uncomputable (T1 item 11 residual gap)
- **Issue #339** (closed): T1 item 8: wrap sim/characterization-summary.md in a klt generic evidence envelope so the row is graded
- **Issue #338** (closed): T1 item 4's signoff citation cannot carry a content_hash: the committed LVS report predates klayout-tools#1969
- **Issue #337** (closed): sar-logic-timing-gates-tie: tie_code_deviation=512 (code lands on 0/1024) at 6/29 scored PVT corners — not confirmed as DR-0029 chatter
- **Issue #335** (closed): spec/decision-records/: two records both numbered DR-0029, which the directory's own README forbids and nothing enforces
- **Issue #334** (closed): sim/sar-logic-functional{,-gates}: no check sees a small cross-loop isolation-gap asymmetry now that both loops carry DR-0028's wide margin bounds
- **Issue #332** (closed): sar-logic-timing-gates-tie: sf_27c_2.97v aborts with Timestep too small (new, post-#296)
- **Issue #331** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **Issue #330** (closed): T1 item 11 (power delivery, structural): no klt erc supply spec or report in this repo

### 2026-09-20

- **PR #336**: spec(DR-0030): bind the acquisition/isolation limits to the DUT's rung, not the deck (#324)
- **PR #333**: sim(sar-logic-timing-gates-tie): run the ratified 45-point mos grid; lt/xl/bad launched, in flight (#303)
- **Issue #324** (closed): sim/sar-logic-functional{,-gates}/ still carry the pre-DR-0028 acq_window_ns / iso_gap_ns bounds, and now hold the coarse deck tighter than the tight one

### 2026-09-19

- **PR #329**: sar-logic-timing-gates-ok: root-cause abs_err_delay_0ns to an unreset first conversion plus a mid-update decode transient, and record DR-0029 (#320)
- **PR #326**: spec(DR-0029): settle the tie loop's decision chatter as a recorded model property (#322)
- **PR #325**: spec(DR-0028): derive the gate-level acq_window_ns / iso_gap_ns bounds from the margin each protects (#319)
- **PR #323**: sar-logic-timing-gates: the second Timestep too small abort is a five-loop composition artifact, not a comparator defect (#310)
- **PR #321**: feat(sim): decompose the gate-level timing deck into per-loop decks and run the first scored 45-point grid (#311)
- **Issue #322** (closed): tie loop's hard comparator decision chatters on the exact-tie input (found under #310; needs a spec decision, not a testbench edit)
- **Issue #320** (closed): Gate-level sar_ctrl converts incorrectly at 10 of 45 PVT points with zero added delay (up to 512 LSB, concentrated at 125 C and slow-logic corners)
- **Issue #319** (closed): acq_window_ns / iso_gap_ns bounds on the gate-level timing deck were inherited from an idealised model and the real netlist does not meet them
- **Issue #311** (closed): Decompose sim/sar-logic-timing-gates into per-loop decks: its five-loop composition, not the host, is why the 45-point grid has never run
- **Issue #310** (closed): sar-logic-timing-gates: second Timestep too small non-convergence past 200 ns, node vvdd_gate#branch, distinct from #296's fixed defect

### 2026-09-18

- **PR #318**: test(sim): pin the gate-netlist byte check and add a version-independent drift guard
- **PR #317**: fix(sar-logic): derive klt synthesize artifact paths instead of reading them back (#314)
- **PR #315**: docs(sim): measure save-vectors/threads neutrality on a full-length gate-level deck
- **PR #313**: docs(sim): measure KLU vs SPARSE 1.3 on the gate-level decks; not adopted
- **PR #312**: docs(sim): measure that sar-logic-timing-gates' five-loop composition, not the host, is why its grid has never run (#303)
- **Issue #316** (closed): sim/tests: gate-netlist drift test has an undocumented hard pin on Yosys 0.69+post, and its failure text tells you to overwrite the goldens
- **Issue #314** (closed): sim/tests: gate-netlist drift test fails before it compares anything — klt synthesize returns a dict where synth_sar_ctrl.py expects a path
- **Issue #309** (closed): Settle whether --save-measured-vectors and --ngspice-threads are measurement-neutral on gate-level decks (they change the accepted-timestep sequence)
- **Issue #308** (closed): Evaluate ngspice's KLU solver for the gate-level decks: it is compiled in and unused, and per-point cost is what blocks the sar-logic-timing-gates grid

### 2026-09-17

- **PR #307**: docs(sim): measure the sar-logic-timing-gates grid cost wall and correct the retention-knob claims (#303)
- **PR #306**: docs(sim): correct stale 'no corner-grid run recorded' notes in gate-level tb.json
- **PR #304**: fix(sar-logic): slew the gate-level comparator output so ngspice can step over the decision (#296)
- **Issue #305** (closed): sim/sar-logic-functional-gates tb.json note claims no corner-grid run exists, and every record inherits it
- **Issue #296** (closed): ngspice non-convergence ('Timestep too small') in gate-level SAR replay, distinct from #282's fixed vdd_gate bug

### 2026-09-16

- **PR #302**: docs(DR-0027): fix garbled lead-in sentence mixing units
- **PR #300**: fix: accept bounded gate-decode one-hot hazard via decision record (DR-0027)
- **PR #299**: docs: root-cause the gate-level sw_conflict one-hot violation
- **Issue #301** (closed): docs(DR-0027): fix garbled lead-in sentence mixing ns-per-day / ps-per-conversion units
- **Issue #298** (closed): fix: real gate-delay hazard in sar_ctrl_a switch decode (rel_n races sel_in_n)
- **Issue #295** (closed): Gate-level SAR switch-decode one-hot invariant violated on every corner tested (sw_conflict_se/df, DR-0014)

### 2026-09-15

- **PR #297**: feat(sar-logic): execute and record the gate-level SPICE replay corner grid (#289)
- **PR #294**: fix(loom): break SIGPIPE/pipefail false-MISS in verify-proposal-refs.sh
- **PR #293**: fix(ci): stop pruning libs.ref from cached gf180mcu PDK in nightly-pdk.yml
- **PR #290**: fix(sar-logic): declare vdd_gate .global in translated gate netlists (#282)
- **PR #288**: fix: isolate gate-netlist drift test from committed synth output
- **PR #286**: layout(adc-top): refresh the stale "Area, as drawn" table against live area.json
- **PR #285**: refactor: remove unused label() function from geometry.py
- **PR #283**: Scaffold gate-level SAR-sequencer SPICE replay testbenches (#273)
- **PR #279**: DR-0023 follow-on (b): place-and-route the SAR sequencer gate netlist
- **PR #278**: feat: pre-route STA evidence for sar_ctrl_a vs DR-0003's 62.5 ns budget
- **Issue #292** (closed): verify-proposal-refs.sh false-flags real files as MISSING via SIGPIPE/pipefail bug
- **Issue #291** (closed): Nightly PDK check failed (sim/selftest.sh stages 2-4)
- **Issue #289** (closed): Execute and record the sar-logic gate-level SPICE replay corner-grid now that #282 unblocks it
- **Issue #287** (closed): check:ci's gate-netlist drift test mutates the working tree (yosys version drift, unrelated file changes land as a side effect)
- **Issue #284** (closed): Remove unused geometry.label() Metal1 helper
- **Issue #282** (closed): Gate-level SPICE replay of the SAR sequencer does not reach a valid digital operating point (blocks #273's corner-grid run)
- **Issue #280** (closed): layout/adc-top/README.md's 'Area, as drawn' table is stale against area.json
- **Issue #277** (closed): Complete the mos-corner-grid temperature/supply axes for sim/sar-logic-timing-gates/ (issue #273 follow-on)
- **Issue #275** (closed): DR-0023 follow-on (c): STA closure for the SAR sequencer gate netlist (klt sta)
- **Issue #274** (closed): DR-0023 follow-on (b): place-and-route the SAR sequencer gate netlist (klt place-and-route)
- **Issue #273** (closed): Gate-level functional/timing corner-grid replay for the SAR sequencer (issue #272 continuation)
- **Issue #272** (closed): Synthesize the SAR sequencer to a gf180mcu gate-level netlist (DR-0023 follow-on (a): RTL + `klt synthesize`, rung-1 replay as equivalence evidence)

### 2026-09-14

- **PR #276**: feat: synthesize the SAR sequencer RTL to a gf180mcu gate-level netlist
