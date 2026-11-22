# Work Log

Merged pull requests and closed issues from the initial 30-day lookback (2026-09-07 onward). Earlier activity remains in GitHub history. Guide document maintenance PRs are excluded.

## Archives

- [2026-09](work_log/WORK_LOG_2026-09.md)

### 2026-11-22

- **PR #962**: refactor(flow): finish migrating unpinned sar-logic scripts onto flow_env
- **PR #959**: Route remaining parasitics stragglers through gen_extracted_core_tb helpers
- **PR #957**: refactor(layout): finish migrating run_extract_parasitics to klt_env
- **PR #956**: evidence(sim): re-qualify adc-inl-dnl V_cm-network arm under f6eeac7; close out #594
- **PR #953**: feat(sim): re-qualify adc-power V_cm-network and acq-leg candidate decks under open_pdks f6eeac7
- **PR #942**: feat(sim): carry adc-rail-current's summed-rail current to the batch fleet and re-mint its record on f6eeac7
- **Issue #960** (closed): Finish migrating unpinned sar-logic flow scripts onto flow_env and remove sta_postroute_spef.check_capabilities
- **Issue #955** (closed): Finish migrating run_extract_parasitics.py onto klt_env and remove its dead pdk=None path
- **Issue #954** (closed): Consolidate remaining pvt_preamble, meas, and shadow_dac_and_error stragglers onto gen_extracted_core_tb
- **Issue #939** (closed): sim/adc-rail-current: replace the 'let isum' analysis step with measurements[].expr so the summed supply current runs on the batch fleet
- **Issue #594** (closed): Re-qualify ADC-level records (INL/DNL, ENOB, power, offset MC) under open_pdks f6eeac7 (part of #515)

### 2026-11-21

- **PR #941**: feat(layout): decode-bank shared-S/D fold candidate + current-floorplan area accounting (issue #936)
- **Issue #936** (closed): layout: next area iteration toward the ratified < 0.1 mm^2 - re-take the per-sub-block area accounting on the current floorplan and build one decode-bank lever as a measured candidate

### 2026-11-20

- **Issue #934** (closed): Reconcile the T1 tracker #640 and the stale park records on its row issues (#641, #645, #652, #594, #643)

### 2026-11-19

- **PR #929**: feat(sim): publish the block-PEX report for signoff item 7 without a stored duplicate
- **Issue #927** (closed): Block-PEX records over-count their own artifact manifest: the Stored-evidence table lists an object the manifest drops
- **PR #926**: Rebuild PR #851 on current main: regenerate the resistor-column-gap fix's whole evidence chain (issue #890)
- **Issue #890** (closed): Rebuild PR #851 (issue #838 resistor-column sab.space.1 fix) on current main: the fix applies cleanly, its evidence chain does not

### 2026-11-18

- **PR #921**: docs(economy): note the DR-0048 -> DR-0049 renumber behind record 20261117-203922-0986aeb's citation
- **Issue #922** (closed): No check validates that a bare DR-NNNN citation resolves to the record it means
- **Issue #920** (closed): Economy record 20261117-203922-0986aeb cites DR-0048 for the tap lattice, which now resolves to an unrelated record
- **PR #897**: feat(layout): draw the latch-up tap lattice — per-row substrate ties and extra well taps (DR-0048)
- **Issue #885** (closed): layout: draw the substrate-tap / well-tap lattice the 0.8.0 deck's DF.13/DF.14 tap-distance rules demand
- **PR #918**: feat(sim): make the issue-910 E1 T-gate load-swap probe re-runnable via --tgate-load
- **Issue #913** (closed): Make the issue-910 E1 extracted-T-gate load-swap probe deck re-runnable (headline benign-demo number is a prose-described hand edit)
- **PR #915**: fix: diagnose unresolvable --nodes names per-table in code readout probe
- **Issue #911** (closed): probe_code_readout.py: subcircuit-internal node vectors are unreachable from the ngspice control block
- **PR #912**: docs(sim): root-cause above-rail ringing (sel_hi_n legs, cmpo), demonstrate benign into the extracted T-gate load
- **Issue #910** (closed): Analog: standard-cell outputs ring above VDD at slow-NMOS cold corners (sel_hi_n legs, cmpo) — root-cause, then demonstrate benign into a real T-gate load or fix
- **PR #908**: fix: declare parasitics' pre-convention record names by exact file in check:layout-pins
- **Issue #905** (closed): check:layout-pins: the declared pre-convention slug shape can still mask a newest FAIL within one date in layout/adc-top/parasitics/records

### 2026-11-17

- **PR #904**: fix: layout-pins record check fails closed on undeclared record names, reads sar_ctrl verdict
- **Issue #902** (closed): check:layout-pins part 2 silently stops verifying a records family when its newest .md is not a recognised verdict record
- **PR #900**: check: re-derive layout evidence manifests' hash pins in CI
- **Issue #898** (closed): check:ci does not verify the layout evidence manifests' own hash pins
- **Issue #896** (closed): DRC-clean claims are graded at the unreleased 0.6.0 deck; the released 0.8.0 deck reports 2694 violations on the pinned adc_block bytes (incl. 2308 contact.width.1, a core-rule re-score)
- **Issue #894** (closed): sim: re-run switch R_on (ADC_TGATE leaf) extracted campaign over the post-implant PEX netlist (#886)
- **PR #889**: fix(layout): draw source/drain implant regions so comp.coverage.1 clears under the klt 0.8.0 deck
- **Issue #836** (closed): layout: draw source/drain implants so comp.coverage.1 (DF.12) passes under the klt 0.8.0 deck
- **PR #892**: fix: alias EXIT_NOT_STORED in run_pex_adc_block.py to evidence_store's constant
- **Issue #891** (closed): run_pex_adc_block.py keeps a local EXIT_NOT_STORED literal instead of aliasing evidence_store's
- **PR #888**: evidence(sim): trace dropped committed duplicates in the record, unify the not-stored exit
- **Issue #884** (closed): evidence-store writer: untested git-absent branch, untested all-duplicates leg, and no record trace for dropped duplicates
- **PR #875**: evidence(sim): re-run vdd-switching-event and vdd-full-pvt schematic grids under open_pdks f6eeac7
- **PR #882**: sim/harness: retain the partial ngspice transcript on a timed-out point
- **Issue #879** (closed): sim/harness: a timed-out point discards ngspice's partial transcript, storing a 19-byte stub instead
- **PR #878**: sim: record tranche-7 sar-logic-timing-gates-tie re-qualification (39/45 ok)
- **Issue #777** (closed): Re-qualify sar-logic-timing-gates-tie on the regenerated deck under open_pdks f6eeac7 (part of #753)
- **Issue #518** (closed): nightly-pdk: confirm ciel -l gf180mcu_fd_pr install still provides libs.ref standard-cell SPICE for gate-level replay tests
- **PR #830**: layout: add --verify-generators control-cell reproducibility check
- **Issue #821** (closed): No automated check that the control-cell generators still reproduce their committed GDS
- **PR #871**: docs(sim): record the tranche-7 sar-logic-timing-gates-tie attempt (22/45 ok, capacity-voided, nothing committed)
- **PR #873**: docs(layout): re-anchor adc-top README Results' top-of-chain block on the #837 records and hashes
- **Issue #869** (closed): layout/adc-top/README.md § Results: the 'Latest records' block is now stale at the top of the chain (3 unlinked 20261116 records, wrong adc_top.gds hash)

### 2026-11-16

- **PR #866**: fix(layout): tile S/D contacts as CO.1 exact squares, shrink the riser cut to 220 nm
- **PR #865**: docs: link the two intervening DRC/LVS record pairs in adc-top README Results
- **Issue #853** (closed): layout/adc-top/README.md § Results: the "Previous records" line skips two intervening DRC/LVS record pairs
- **Issue #837** (closed): layout: replace source/drain contact bars with CO.1 exact-square arrays (contact.width.1 under klt 0.8.0)
- **Issue #833** (closed): Re-derive comparator-budget-memo §5 kickback under DR-0014 bottom-plate sampling
- **PR #849**: docs(sim): re-derive comparator-kickback under DR-0014 on the built 18.254 pF array
- **Issue #860** (closed): Issue #833's title and body carry literal uXXXX escapes instead of the characters (and they propagate into WORK_PLAN.md)
- **PR #841**: docs: re-point device-switch-ron citations to the clean-tree re-take
- **Issue #820** (closed): devchar §2.1 and the timing memo cite a superseded non-citable R_on record; repoint them at its bit-identical clean-tree re-take
- **PR #857**: test(flow): key the flow-side file-hasher guard on hashlib too, not just definition names
- **PR #855**: investigate cold-corner failures on sar-logic-functional-gates; move one-hot checks past the discarded first conversion (DR-0046)
- **PR #850**: docs: re-pin ROADMAP to 2026-11-16 main and reconcile Now to it
- **PR #845**: fix(layout): wire run_sar_ctrl_lvs record onto the shared klt_env helpers
- **PR #842**: fix(layout): snap adc_top guard-ring geometry to the 5 nm grid, assert on-grid at write
- **Issue #856** (closed): signoff/reports/: 10 consecutive records carry a byte-identical verdict payload (47 unique of 68)
- **Issue #847** (closed): test(flow): key the flow-side file-hasher guard on hashlib too, not just definition names
- **Issue #844** (closed): Investigate first-measured cold/hot failures on sar-logic-functional-gates (tt_-40c misconverts; nside_cells_df over bound at 3 corners)
- **Issue #839** (closed): layout: snap adc_top top-level geometry to the 5 nm manufacturing grid (*.ongrid.1 under klt 0.8.0)
- **Issue #835** (closed): docs/ROADMAP.md: advance the 2026-11-13 pin and reconcile the Now list to it (the half #818 placed out of scope)
- **Issue #823** (closed): layout/lvs/run_sar_ctrl_lvs.py is a fifth record minter outside the klt_env record plumbing (#795)
- **PR #846**: test(layout): guard layout/ against private hashlib use; hash GDS via klt_env
- **Issue #808** (closed): No anti-drift scan guards the layout/ tree against re-growing its own copy of a klt_env helper
- **PR #840**: docs(layout): adjudicate the klt 0.8.0 DRC --check deltas
- **Issue #797** (closed): Triage the ADC_BLOCK DRC delta under the klt release #652 targets (part of #652)
- **PR #832**: docs(roadmap): replace per-issue label claims with WORK_PLAN.md pointers
- **Issue #818** (closed): docs/ROADMAP.md: the Now section's per-issue label claims perish within hours — cite the live queue instead of enumerating labels
- **PR #843**: evidence(sar-logic-functional-gates): 14/15 scored at 3.30 V under f6eeac7; repairs the 3eed6a0 tip
- **Issue #779** (closed): Re-qualify sar-logic-functional-gates under open_pdks f6eeac7 and repair its supersession tip (part of #753)

### 2026-11-15

- **PR #834**: docs(spec): re-point stale bare-prose DR-0007/DR-0006 citations to records in force
- **Issue #829** (closed): spec/comparator-budget-memo.md cites a stale pre-renumbering DR-0007/DR-0006; its real referents are DR-0015 and DR-0011
- **PR #827**: docs: supersede DR-0007's dedicated-switch topology with DR-0045; annotate note [g] stale provenance
- **Issue #819** (closed): DR-0007's dummy charge-injection compensation is absent from the built acquisition path, with no superseding record
- **PR #826**: fix(layout): derive LVS request documents' own path, not the production one
- **Issue #804** (closed): Candidate LVS requests and reference netlists document the production request path, not their own
- **PR #825**: docs(sim): index the three mc-cdac-mismatch yield-evidence bundles
- **Issue #814** (closed): Decide whether to unify the drifted negative-control prose across the three CDAC yield-evidence bundles
- **PR #824**: docs(power): record what klt 0.8.0's power-spec schema requires of the committed specs
- **Issue #799** (closed): Record what the newer klt power schema requires of the committed power specs (part of #652)
- **PR #806**: refactor: consolidate the four layout/ runners' record plumbing onto klt_env
- **Issue #795** (closed): Consolidate the forked CLI/record-tail plumbing in the four layout/ evidence runners onto klt_env
- **PR #816**: chore(sim): re-baseline evidence-footprint ceilings to the measured state at 362c3ae7
- **Issue #805** (closed): Re-baseline or retire the evidence-footprint ceilings: all three are breached, so check:ci's last step signals nothing
- **PR #822**: docs(layout): adjudicate the klt 0.8.0 LVS and ERC --check deltas
- **Issue #798** (closed): Triage the LVS and ERC --check deltas under the klt release #652 targets (part of #652)
- **PR #813**: refactor(sim): share the klt yield emitter across all four yield-evidence bundles
- **Issue #794** (closed): Collapse four duplicated build_yield_evidence.py emitters onto one shared sim/tools helper
- **PR #815**: docs(sim): lt/xl cost measured >3400 core-s/point; no record reachable
- **Issue #778** (closed): Re-qualify sar-logic-timing-gates-lt and -xl on the regenerated decks under open_pdks f6eeac7 (part of #753)
- **PR #812**: refactor(layout): hoist the control-cell generators' main() onto klt_env
- **Issue #809** (closed): Finish the klt_env hoist: the control-cell generators' main() is a three-way fork that has already drifted
- **PR #796**: docs: roadmap as of 2026-11-13

### 2026-11-14

- **PR #802**: refactor: route every flow-tree file hash through the one shared sha256
- **Issue #801** (closed): Finish #589's hasher consolidation: remove spef_audit.sha256_file and run_extract_parasitics._sha256
- **PR #811**: docs(sim): rank cold-corner ENOB/SFDR distortion candidates by mechanism class
- **Issue #800** (closed): Rank candidate fixes for the cold-corner ENOB/SFDR distortion shortfall (investigation record)
- **PR #803**: refactor(parasitics): drop the zero-caller PMOS-body alias and re-point the docstring at the real guard
- **Issue #793** (closed): Remove _find_pmos_body_nets: dead back-compat alias with zero callers, and the docstring that still cites it
- **PR #788**: refactor: share one check-or-write tail across the extracted-deck generators
- **Issue #780** (closed): Dedupe the check-or-write main() tail copied across six extracted-testbench generators
- **PR #787**: evidence(sim): record #779's fleet refusal and the deck's measured per-point cost

### 2026-11-13

- **PR #791**: refactor: retire the dead --in-path-control positive control
- **Issue #789** (closed): gen_extracted_switch_ron_tb.py --in-path-control raises instead of emitting its positive control
- **PR #790**: fix: decide the body tie from the remediation partition, drop the dead raw probe
- **Issue #784** (closed): Remove the dead raw-body probe from verify_remediation_dc.py and fix its stale body-tie check
- **PR #785**: fix: skip the non-ok deck copy when the log dir is the workdir
- **Issue #783** (closed): bug: --no-write crashes with SameFileError when a batch point does not score ok
- **PR #775**: docs: name the OSU 3.3 V libraries in every ciel enable command
- **Issue #772** (closed): docs(environment-setup §3): the documented `ciel enable` command installs neither the OSU 3.3 V libraries nor mcu7t5v0
- **PR #773**: evidence(sar-logic-timing-gates-ok): 45/45 under f6eeac7, and the batch job-split that made it runnable
- **PR #766**: fix(sim/harness): scope the fleet pin check to members that banked points
- **Issue #760** (closed): sim/harness: a Spot-interrupted member discards every good point in the set as 'toolchain drift'
- **PR #768**: feat(signoff): re-hash the files an attestation envelope records in --check
- **Issue #764** (closed): signoff --check passes with a stale item-9/10 envelope; --regen does not re-attest them
- **PR #767**: test(signoff): fail CI when a testbench inventory's PDK pin drifts from sim/toolchain.json
- **Issue #762** (closed): signoff: add a CI test that the testbench-inventory PDK pin matches sim/toolchain.json
- **PR #763**: docs(spec): cite the standard-cell device by its f6eeac7 name; repair the LVS wrong-width control
- **Issue #757** (closed): Stale 6V-oxide standard-cell references after the f6eeac7 re-pin (tb.json note, DR-0023 evidence, LVS runner regex)
- **Issue #761** (closed): signoff: both testbench inventories still pin the pre-#517 open_pdks revision c6d73a3
- **PR #758**: fix(harness): withhold the Supersedes pointer when no point reached ok
- **Issue #755** (closed): run_corners.py writes a Supersedes pointer even when every point errored, letting a measurement-free record displace a measured one
- **PR #756**: sim(sar-logic): regenerate the gate-level decks under open_pdks f6eeac7 and re-pin T1 item 9
- **Issue #632** (closed): Nightly PDK check failed (sim/selftest.sh stages 2-4)
- **PR #752**: docs(signoff): replace per-re-pin chain narration with id-named row movers
- **Issue #750** (closed): signoff/README.md: prose after the current-record pointer describes an older record
- **PR #751**: docs(DR-0043): record that the deferred power/PEX/signoff re-baseline landed
- **Issue #692** (closed): Re-baseline klt power droop and re-run block PEX sims after the SAR-reserve notch layout (follow-up to #667)
- **PR #747**: sim: re-qualify sar-logic-functional under f6eeac7; wait for batch capacity

### 2026-11-12

- **PR #744**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-09

- **PR #740**: sim: re-qualify C_u, acquisition-width and V_cm drive sweeps under open_pdks f6eeac7
- **Issue #622** (closed): Re-pin signoff T1 item 8 evidence after dr0014-sampling re-qualification edited characterization-summary.md
- **Issue #616** (closed): Re-qualify dr0019-cu-sweep, acq-leg-width-sweep (x1.1..x2.068), vcm-drive-impedance under open_pdks f6eeac7 (part of #595)

### 2026-11-08

- **PR #737**: sim(comparator-preamp-noise): re-qualify noise grid under f6eeac7 on the batch fleet
- **Issue #609** (closed): Re-qualify comparator-offset-gof/-offset-mc/-preamp-noise records under open_pdks f6eeac7 (part of #593)
- **PR #736**: ci: run the headless check list from package.json only
- **Issue #734** (closed): Collapse duplicated CI check list: package.json check:ci and ci.yml have drifted
- **PR #733**: feat(sim): record platform, ngspice banner and observed front-end mode
- **Issue #468** (closed): sim(harness): record platform, full ngspice banner and ngspice front-end mode in every record (follow-up to #459)

### 2026-11-07

- **PR #730**: Bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #693**: layout(adc-top): SAR reserve in top-right notch with L-shaped analog guard ring
- **Issue #667** (closed): layout: place the SAR-logic reserve in or beside the analog core instead of a full-width stacked band
- **Issue #471** (closed): Auditor Capability Request: ngspice >=46 on audit host (installed 42 trips toolchain pin)
- **PR #725**: refactor(sim): share sweep point-loop driver across the three run_sweep.sh scripts
- **Issue #724** (closed): Simplify: share one sweep driver across the three sim run_sweep.sh scripts

### 2026-11-05

- **PR #723**: refactor(sim): share full-PVT campaign driver between vcm and vdd
- **Issue #722** (closed): Consolidate vcm/vdd run_full_pvt.sh campaign drivers (parallel drift: vdd lacks KLT_CMD/SUPERSEDES hooks)
- **PR #718**: feat(sim): re-qualify adc-offset-mc pilot under open_pdks f6eeac7 on the batch fleet
- **PR #717**: feat(sim): 27-point extracted ENOB/SFDR temperature grid; cold corner governs both rows
- **Issue #430** (closed): Establish extracted ENOB/SFDR temperature coverage beyond the hot-only FFT subset
- **PR #714**: feat(sim): re-qualify adc-enob-fft schematic 9-point grid under open_pdks f6eeac7 on the batch fleet
- **PR #715**: feat(sim): re-qualify track-switch sampling and THD on the batch fleet
- **Issue #618** (closed): Re-qualify track-switch-sampling and track-switch-thd under open_pdks f6eeac7 (part of #595; blocked on klt sim control steps)
- **PR #713**: docs(sim): record #430 preflight on 0.9.0 runner refused by fleet vCPU budget
- **PR #711**: feat(sim): re-qualify adc-inl-dnl schematic grid under open_pdks f6eeac7 (batch fleet)
- **PR #704**: feat(sim): re-qualify adc-power grid under open_pdks f6eeac7 (batch fleet)
- **PR #706**: sim: re-qualify four device/comparator experiments under open_pdks f6eeac7 on the batch fleet
- **Issue #601** (closed): Re-qualify cdac-bit-settling, top-plate-cpar, smoke-sar-bias, adc-block-pex records under open_pdks f6eeac7 (part of #593)
- **PR #709**: fix(pex): store adc-block-pex evidence via the artifact store
- **Issue #708** (closed): run_pex_adc_block.py commits raw per-corner PEX output; store it via the artifact store (DR-0041)
- **PR #705**: docs(adc-offset-mc): record passing batch-compatibility gate on rebaked runner

### 2026-11-04

- **PR #702**: docs(sta): record clean-tree re-run of the 0.8.0 gated SPEF qualification
- **PR #701**: docs(sar_ctrl): note the 0.8.0 gated SPEF run and its limits in the macro README
- **PR #698**: feat(sta): pin klt for the extracted-SPEF STA flow and record a 0.8.0 qualification run
- **PR #697**: sim: re-qualify device-comparator-gm-id under open_pdks f6eeac7 (1 of 7)

### 2026-11-01

- **PR #688**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-31

- **PR #686**: sim: measure intermediate acquisition-leg width spectral points (1.1x-2.068x)
- **Issue #429** (closed): Measure intermediate acquisition-leg widths before choosing an ENOB/SFDR recovery candidate
- **PR #684**: sim: re-take sar-logic-timing supply grid on corrected deck
- **Issue #460** (closed): sim(sar-logic-timing): re-take the Clock row's supply-axis grid on the #371-corrected deck
- **PR #680**: docs: index superseded evidence records outside records/
- **Issue #679** (closed): Follow-on from PR #676: list superseding records next to the record they supersede
- **PR #676**: docs: append correction for ADC_TOP 10 µm fold-point area (+5.3 %, not +7 %)
- **Issue #674** (closed): Correct '+7 %' ADC_TOP figure in decode-bank folding record 20261030-223000-be1c350

### 2026-10-30

- **PR #670**: docs(layout): area-limit analysis of adc_block per sub-block
- **Issue #644** (closed): T1 item 5 (analog, Area row): resolve adc_block 0.151827 mm^2 against the ratified < 0.1 mm^2 (DR-0024 is proposed, not ratified)
- **PR #673**: docs(layout): record decode-bank folding as a null area result
- **PR #672**: analysis(layout): CDAC array edge margin is the dummy ring; keep it
- **PR #671**: docs: SAR-reserve right-column placement analysis and DR-0042
- **Issue #669** (closed): layout: quantify the CDAC array edge-margin area against its matching role
- **Issue #668** (closed): layout: fold the decode banks to recover their non-drawn bbox area

### 2026-10-28

- **PR #663**: refactor(flow): route synth_sar_ctrl klt calls through run_klt_json
- **PR #661**: refactor(flow): route sar_ctrl klt calls through run_klt_json
- **PR #657**: sim: add post-resize klt yield evidence for INL/DNL 3σ row
- **Issue #656** (closed): INL/DNL 3σ Monte Carlo klt yield evidence for T1 item 6 (split from #654)

### 2026-10-27

- **PR #649**: refactor: share liberty_path and working_tree_dirty via flow_env
- **PR #648**: feat(signoff): cite multi-corner STA and cocotb suite as 5.digital
- **Issue #646** (closed): Consolidate duplicated liberty_path/working_tree_dirty helpers into flow_env.py
- **Issue #642** (closed): T1 item 5 (corner verification, digital): one multi-corner klt sta citation and a klt functional-verification envelope for sar_ctrl

### 2026-10-23

- **PR #637**: feat(sim): store new run evidence in the artifact store, commit manifests
- **Issue #636** (closed): Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)

### 2026-10-21

- **PR #630**: Bump Repo Skills 0.24.3 -> 0.24.7
- **PR #577**: ci: drop loom-ui OIDC result step from nightly-pdk
- **Issue #576** (closed): Drop the loom-ui result step from nightly-pdk (CI pushes nothing; no OIDC)
- **PR #626**: sim(dr0014-sampling): narrow the Linux-vs-macOS tp_inj offset to the host ngspice environment
- **Issue #623** (closed): Explain ~0.007 LSB tp_inj offset between extracted dr0014-sampling records 20261007-0719/0721 and 20260923-1044 (same deck bytes)
- **PR #624**: sim(dr0014-sampling): re-qualify the 7 live records under open_pdks f6eeac7 on the batch fleet
- **Issue #615** (closed): Re-qualify dr0014-sampling records under open_pdks f6eeac7 (part of #595)
- **PR #620**: docs: record #617 re-qualification refused by saturated batch fleet

### 2026-10-20

- **PR #619**: test: collect qualification-request seed-schedule test under unittest
- **Issue #613** (closed): Fix inert test: qualification-request test in test_adc_offset_mc.py is never collected
- **PR #612**: sim(harness): export klt_sim analysis steps; record blocked fleet re-run of comparator noise/offset decks
- **PR #611**: sim(comparator): re-qualify offset and regeneration under f6eeac7 on the batch fleet
- **Issue #600** (closed): Re-qualify comparator-* characterization records under open_pdks f6eeac7 (part of #593)
- **PR #604**: sim(comparator-kickback): re-qualify under open_pdks f6eeac7 via batch fleet
- **PR #603**: sim: re-qualify timing-budget-closure and acq-leg-width-sweep x1.0 under open_pdks f6eeac7 (partial)
- **PR #602**: fix(signoff): re-pin T1 evidence after #517 changed pinned files
- **Issue #598** (closed): main CI red: signoff freshness check fails with 4 stale evidence pins
- **PR #597**: ci: request standard-cell library in ciel enable and guard its SPICE file
- **PR #517**: feat(pdk): re-pin open_pdks to f6eeac7 and move PDK install/search to ciel
- **Issue #514** (closed): Re-pin open_pdks to f6eeac7 and move PDK install/search to ciel (part of #513)
- **PR #590**: refactor: consolidate evidence-record helpers into layout/klt_env
- **Issue #589** (closed): Dedupe git()/record_id()/klt_version()/sha256() between layout/klt_env.py and design/sar-logic/flow/flow_env.py
- **PR #587**: fix(sim): surface ngspice abort on error corners and retain non-ok decks
- **Issue #585** (closed): sim/harness/batch.py: abort scan is unreachable for klt error corners, and the generated corner deck is not kept as evidence
- **PR #586**: docs(sim): reconcile the bad-loop grid with its raw logs and plan a capped one-point pilot
- **Issue #584** (closed): Diagnose #303 bad-loop aborts from existing evidence and prepare a costed one-point pilot
- **PR #582**: sim(sar-logic-timing-gates-bad): batch-fleet 45-point grid ran, 0 of 45 scored
- **PR #581**: refactor(layout): retire comparator-only klt pex runner with verified recovery recipe
- **Issue #550** (closed): Remove or de-duplicate run_pex_comparator.py: superseded by run_pex_adc_block.py

### 2026-10-17

- **PR #573**: refactor: import sar_ctrl flow constants from flow_env in signoff-pinned drivers
- **Issue #572** (closed): Finish hoisting sar_ctrl constants into flow_env.py for signoff-pinned drivers
- **PR #570**: refactor: hoist shared sar_ctrl flow constants into flow_env.py
- **Issue #569** (closed): Consolidate duplicated sar_ctrl flow constants into flow_env.py
- **PR #568**: docs(signoff): drop hard-coded tampered-input count from prose
- **Issue #567** (closed): signoff: selftest control count in docs drifts from run_signoff.py --selftest
- **PR #566**: signoff: record T1 item 6 not applicable for the digital partition
- **Issue #562** (closed): signoff: record T1 item 6 as not applicable for the digital partition, with every digital row classified
- **PR #565**: feat(signoff): attest T1 items 9 and 10 with klt signoff --attest
- **Issue #561** (closed): signoff: attest T1 items 9 and 10 for both partitions with klt signoff --attest envelopes
- **PR #564**: feat(signoff): attest T1 items 1 and 2 for both partitions, bump grader pin
- **Issue #560** (closed): signoff: attest T1 items 1 and 2 for both partitions with artifact-anchored envelopes
- **PR #563**: signoff: cite sar_ctrl gate-level LVS and ERC supply run for digital items 4 and 11
- **Issue #559** (closed): signoff: cite the routed sar_ctrl gate-level LVS and add its klt erc supply run (T1 items 4 and 11, digital)
- **PR #547**: refactor(sim/tests): share one import-by-path helper across tests
- **Issue #544** (closed): Remove 17 copies of the importlib load-by-path boilerplate in sim/tests: share one helper
- **PR #553**: refactor: share one stair-PWL stimulus helper across extracted-core deck generators
- **Issue #552** (closed): Consolidate copy-pasted stair-PWL stimulus loop across five extracted-core deck generators
- **PR #546**: refactor(layout): share klt JSON+text report runner in klt_env
- **Issue #542** (closed): Dedupe run_case() klt-report runner between run_erc.py and run_power.py into klt_env.py
- **PR #551**: feat(spef-audit): record and regression-test no-net prover on committed sar_ctrl
- **PR #545**: refactor(parasitics): share one ngspice -b runner across extraction scripts
- **Issue #548** (closed): Record and regression-test the no-net prover on the committed sar_ctrl inputs
- **Issue #541** (closed): Dedupe NGSPICE constant and ngspice -b wrapper across parasitics scripts
- **PR #543**: feat(spef-audit): exempt unannotated outputs only with an independent no-net proof
- **PR #539**: refactor(signoff): import klt provenance helpers from klt_env instead of forking them
- **Issue #538** (closed): Dedupe klt_env helpers still forked in signoff/run_signoff.py
- **PR #540**: refactor(flow): share klt JSON runner and STA result classes in flow_env
- **Issue #537** (closed): Consolidate duplicated klt runner and CornerResult in sar_ctrl flow drivers

### 2026-10-16

- **PR #536**: fix(sta): condition SPEF record prose on audit data
- **Issue #533** (closed): sta_postroute_spef record template emits stale/contradictory prose when annotation is complete
- **PR #532**: docs(sta): record third gated SPEF retry, rejected only by repo floating-driver gate
- **PR #530**: docs(sta): record second gated SPEF retry, still rejected on annotation
- **PR #528**: docs: record extracted-SPEF timing retry on fixed klt, still rejected on annotation_complete
- **Issue #376** (closed): README: embed the fleet burndown chart (one line)
- **PR #523**: Bump Repo Skills 0.24.1 -> 0.24.3

### 2026-10-15

- **PR #521**: docs: classify sar_ctrl macro DRC markers via isolated PDK-cell runs
- **PR #519**: fix: add Metal4 VDD/VSS straps to SAR macro PDN and verify with LVS supply control
- **Issue #520** (closed): sar_ctrl macro: 208 klt drc violations (nplus.space.pcomp.1 / pplus.enclosing.comp.1) from PDK endcap/filltie/fill cells
- **Issue #485** (closed): Repair disconnected SAR macro supply rails with a macro-sized PDN
- **PR #510**: signoff: re-take T1 item 7 (block-scoped klt pex) across the committed 117-point grid on the batch fleet
- **PR #508**: Bump Repo Skills 0.19.5 -> 0.24.1
- **Issue #439** (closed): signoff: re-take T1 item 7 (block-scoped klt pex) across the committed 117-point grid once the batch fleet accepts the pinned klt
- **PR #507**: sim(vcm): extracted V_cm pair re-taken on the post-#381 netlist (#392)
- **Issue #392** (closed): sim(vcm): re-take the extracted V_cm pair against the post-#381 re-extraction

### 2026-10-14

- **PR #506**: sim/harness: export the supply axis as one klt request per vdd_val (#505)
- **Issue #505** (closed): sim/harness: batch export keys corners.supply_v by .param, rejected by current klt

### 2026-10-13

- **PR #501**: ci(nightly-pdk): record selftest failures on loom-ui

### 2026-10-10

- **Issue #499** (closed): Check: extracted comparator netlists with bare M model cards bypass the PDK mismatch subckt (zero Monte-Carlo spread)

### 2026-10-09

- **Issue #494** (closed): Guard decision review: keep git clean -fd protected
- **PR #493**: signoff: correct sar_ctrl baseline STA parasitics wording (#484)
- **PR #492**: docs(readme): cap line length at 600 and relocate spec-table narrative
- **Issue #484** (closed): signoff: correct sar_ctrl STA parasitics wording in characterization-summary.digital.json (no RC estimate was applied)
- **Issue #475** (closed): docs: cap README spec-table cell length and machine-check it (longest line is 5,238 chars)
- **PR #490**: docs(sim): #430 batch preflight still blocked by runner version mismatch
- **Issue #480** (closed): Qualify standalone routed SAR macro LVS against its golden circuit
- **PR #488**: sim: fail characterization on incomplete or aborted V_CM sweeps
- **PR #487**: sim(adc-enob-fft): #430 preflight re-check 2 -- batch runner mismatch persists (0/27)
- **PR #483**: feat(sta): extracted-SPEF mode for routed sar_ctrl STA with annotation gate; SPEF rejected, limits retained
- **PR #482**: LVS qualification for standalone sar_ctrl macro: path works, committed GDS is mismatch (VDD split) (#480)
- **PR #479**: sim(adc-offset-mc): #478 screening qualification attempt (refused by fleet runner skew)
- **PR #477**: sim: evidence footprint report + DR-0039 retention proposal (#476)
- **PR #474**: ci: machine-check relative markdown links (#472)
- **Issue #481** (closed): Close routed SAR timing evidence gaps with extracted SPEF and propagated clock
- **Issue #478** (closed): sim(adc-offset-mc): qualify the bidirectional screening null and measured runtime before the population
- **Issue #476** (closed): sim: measure evidence footprint (~440 MB of tracked logs) and draft a retention decision record
- **Issue #472** (closed): ci: machine-check relative markdown links (18 currently broken)
- **Issue #456** (closed): sim: fail characterization on incomplete or aborted V_CM sweeps
- **PR #470**: Issue #429: second fleet probe of acq-leg width sweep (still blocked on PDK include)
- **PR #469**: sim(dr0014-sampling): isolate the #393 gain-error control-arm delta (#459)
- **PR #467**: docs: reconcile SAR routing/STA status and the fixed #266 power-corner warning
- **PR #466**: Issue #430: preflight re-check, both 0.7.0 and 0.6.0 clients blocked (no points run)
- **PR #465**: spec: assess input-pair cascode applicability vs ADC kickback evidence (#443)
- **PR #462**: sim: machine-check characterization-summary evidence citations (#437)
- **PR #463**: Issue #430: preflight re-check, runner version mismatch persists (partial)
- **PR #461**: Issue #430: batch preflight refused by fleet concurrency cap (no points run)
- **PR #458**: Issue #454: campaign-ready offset-MC estimator, per-corner requests, record writer
- **PR #455**: Issue #453: DR-0038 (proposed) offset-error definition
- **PR #452**: Issue #427: qualify batch path for ADC_BLOCK offset Monte Carlo (pilot + campaign protocol)
- **Issue #459** (closed): sim(dr0014-sampling): isolate why the #393 ideal-supply control arm reads 0.001006 LSB vs the governing 0.000981 LSB
- **Issue #457** (closed): docs: reconcile live SAR routing and STA status and the fixed power-corner reproduction warning
- **Issue #443** (closed): Assess input-pair cascode applicability against ADC kickback evidence and budget
- **Issue #437** (closed): sim: machine-check characterization-summary evidence citations against the newest campaign records
- **Issue #454** (closed): sim(adc-offset-mc): build the campaign-ready estimator, per-corner request split and record writer ahead of the screening population
- **Issue #453** (closed): Decide the ADC offset-error definition (spread vs. mean-plus-spread) before the comparator-inclusive population runs
- **Issue #427** (closed): Qualify a faithful batch path for ADC_BLOCK offset Monte Carlo before the full population

- **PR #450**: Issue #438: deterministic decision-record status index
- **PR #448**: Issue #430: record 0.7.0-client batch preflight version mismatch (no points run)
- **Issue #438** (closed): spec: generate and CI-check a deterministic decision-record status index
- **Issue #441** (closed): Auditor guard review: retain git clean -fd protection
- **PR #447**: Issue #429: fleet re-check of x1.0 control still fails on PDK include (blocker evidence)
- **PR #446**: Issue #430: fleet re-opened (preflight passes), cold leg refused for capacity
- **PR #444**: adc-enob-fft: #430 preflight re-check, fleet still blocked (partial increment)

### 2026-10-08

- **PR #440**: Intermediate acquisition-leg widths: layout screened, spectral blocked (#429)
- **PR #436**: adc-enob-fft: #430 temperature-coverage campaign attempt (blocked; partial, 0/27 new points)
- **PR #435**: docs: bring klt pex statements current in the two summaries after #428; re-anchor signoff item 8
- **Issue #432** (closed): docs: characterization-summary and extracted-delta-summary section 9 still describe klt pex as blocked after #428
- **PR #433**: Reconcile klt pins (PyPI 0.6.0 where tested) and run layout runners nightly (#426)
- **PR #431**: signoff: block-scoped klt pex retry for T1 item 7, met on one PVT point (#428)
- **PR #425**: README: relocate over-long State-table cells to docs/, check Layout area (#421)
- **PR #424**: Dedupe resolve_klt()/latest_record() into klt_env.py
- **PR #423**: sim(vcm): extracted V_cm pair re-take blocked on fleet runner klt skew (Part of #392)
- **PR #419**: sim/harness: export run_corners.py grids as klt sim requests for the batch fleet
- **PR #418**: README: signoff-checked Status summary; archive DR-0019-era narrative (#415)
- **PR #417**: CI: enforce the 'sim/ results are append-only' rule mechanically
- **Issue #428** (closed): signoff: retry block-scoped klt pex for T1 item 7 now that klayout-tools#1030 is closed
- **Issue #426** (closed): Reconcile klt pins (docs say 0.4.0/no PyPI; layout and signoff pin different commits) and run the klt layout checks in nightly CI
- **Issue #421** (closed): README: relocate the over-long State-table cells (Schematics/Layout/Verification suite) to docs/ and check the Layout area figure
- **Issue #420** (closed): Dedupe resolve_klt()/latest_record() from run_erc.py and run_power.py into klt_env.py
- **Issue #412** (closed): sim/harness: export run_corners.py grids as klt sim requests so they run on the batch fleet
- **Issue #415** (closed): README: lead Status with a signoff-derived current summary; move the DR-0019-era narrative to docs/
- **Issue #414** (closed): CI: enforce the 'sim/ results are append-only' rule mechanically

### 2026-10-07

- **Issue #409** (closed): Auditor guard review: keep git clean -fd confirmation
- **PR #407**: sim(supply): measure the converter behind a real V_DD drive network at DR-0036's budget
- **Issue #393** (closed): sim(supply): measure the converter behind a real V_DD drive network at DR-0036's budget
- **PR #405**: sim: measure the V_DD switching-event charge and width (#386)
- **Issue #386** (closed): sim/adc-rail-current/ never integrates the CDAC switching event, so DR-0036's charge budget is bounded 4.3x loose

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

