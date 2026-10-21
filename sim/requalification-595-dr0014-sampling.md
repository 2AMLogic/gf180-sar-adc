# Re-qualification under open_pdks f6eeac7 — dr0014-sampling (issue #615, part of #595)

Part of #515. Companion to `sim/requalification-595-timing-switching-sampling.md`
(PR #603), which deferred this experiment because the batch fleet refused
submits. Old records stay untouched (append-only); each new record names its
`Supersedes` target and carries the fleet job ids in its Environment section.

Pinned PDK: open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (old records:
`c6d73a3`). Fleet engine ngspice 46, runner klt 0.7.0 (`runner_compatibility:
match`), client klt `0.7.1.dev2379+g28c56ed58269`, `klt sim` backend
`aws-batch-fleet`. Every grid is the full 27-point PVT matrix (tt/ss/ff x
-40/27/125 C x 2.97/3.30/3.63 V), submitted as
`python3 sim/run_corners.py <testbench> --backend batch --supersedes <old-id>`
(one `klt sim --batch-set` request per supply). No grid ran on this host.

## Re-qualified (7 of 7 un-superseded records)

| # | netlist | old record | new record | fleet jobs (2.97 / 3.30 / 3.63 V) | result | measurements compared | moved beyond tolerance |
|---|---|---|---|---|---|---|---|
| 1 | schematic (plain) | `20260817-134517-cde979d` | `20261020-235635-0bf0747` | klt-sim-4271ae8dbc26, -b4b33d8999b5, -0b826a89f729 | 27/27 PASS | 59 | 0 |
| 2 | schematic, #238 acquisition leg x2.068 | `20260825-015032-446a3c4` | `20261021-000250-0bf0747` | klt-sim-919bfc87fecd, -325db5b60d94, -33fb9e9cca6b | 27/27 PASS | 59 | 0 |
| 3 | schematic (plain) | `20260923-085243-664c8dc` | `20261020-231040-0bf0747` | klt-sim-6b6032e974ac, -d159c440438c, -0dd40afc8105 | 27/27 PASS | 59 | 0 |
| 4 | schematic, V_cm network (Z_vcm 220 ohm) | `20260923-092849-664c8dc` | `20261020-235634-0bf0747` | klt-sim-7590d9501310, -37ae49c97eab, -657754ae26e4 | 27/27 PASS | 59 | 0 |
| 5 | extracted (star-split, drawn-tap bodies) | `20260923-104443-904af96` | `20261020-233008-0bf0747` | klt-sim-df05595848d6, -c8fd00b718be, -18258dc5151b | 27/27 PASS | 43 | 0 |
| 6 | extracted (star-split, drawn-tap bodies) | `20261007-071907-800bf53` | `20261020-231428-0bf0747` | klt-sim-840f3f34ab2a, -c9232f9e375d, -3c3f12742d69 | 27/27 PASS | 43 | 10 |
| 7 | extracted, V_DD network (Z_vdd 3 ohm) | `20261007-072143-800bf53` | `20261020-235636-0bf0747` | klt-sim-b637a4c1ae3d, -f303093e3e11, -d77c5c0be8da | 27/27 PASS | 43 | 10 |

Variant decks were regenerated from the tree and are byte-identical to the
decks the old records froze (sha256 of the regenerated deck equals the sha256 in
the old record; checked for #2, #4 and #7):

- #2: `python3 sim/dr0019-cu-sweep/gen_cu_variant.py --deck dr14 --c-unit-ff 35.6528 --acq-switch-scale 2.068` (`7e7f1746...`)
- #4: `python3 sim/vcm-drive-impedance/gen_vcm_variant.py --z-ohm 220 --c-dec-nf 40 --deck sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice` (`849d993d...`)
- #7: `python3 sim/vdd-drive-impedance/gen_vdd_variant.py --deck sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice --z-ohm 3 --c-dec-nf 40 --corner-hz 1e6` (`cc6d2b44...`)
- #5, #6: the checked-in `testbench-extracted/tb_dr0014_sampling_extracted.spice` (`4fea809d...`, the sha both old records recorded).

## Delta table

Method: `python3 sim/dr0014-sampling/requal_delta.py <old-id> <new-id>` pairs the
two per-corner result tables by corner id and, for each measurement, reports the
corner with the largest |new - old|. Tolerance: a measurement is "moved" when
|delta| > max(1e-3, 1 % of max(|old|, |new|)) in the measurement's own unit (the
absolute floor keeps values that are numerically zero from reading as 100 %
moves). The tolerance is this note's own reporting threshold; it relaxes no spec
value. The complete per-measurement tables for all seven pairs are in the
Appendix.

**Pairs 1-5: nothing moved.** All 59 (schematic) / 43 (extracted) measurements
agree within tolerance at every corner. The largest schematic differences are
~1e-3 LSB in `hold_*`/`res_*` and 1e-4 LSB in `samp_inl_*`, far inside the
tolerance; the spec-bearing quantities (`tp_inj_signal_dep_lsb`,
`bp_inj_mis_lsb`, `samp_gain_err_lsb`, `samp_inl_worst_lsb`, `ron_path_worst_ohm`)
agree to 4+ significant figures.

**Pairs 6 and 7: 10 measurements moved each — `tp_inj_p_l0..l4_lsb` and
`tp_inj_n_l0..l4_lsb` (top-plate V_cm switch injection per level), extracted
deck only.**

| pair | measurement | corner | old | new | delta |
|---|---|---|---|---|---|
| 6 | `tp_inj_p_l0_lsb` (worst of the 10) | `ff_-40c_3.63v` | 0.106386 | 0.113089 | +0.0067 |
| 6 | `tp_inj_n_l0_lsb` | `ff_-40c_3.63v` | 0.105739 | 0.112588 | +0.00685 |
| 7 | `tp_inj_p_l0_lsb` | `tt_-40c_3.63v` | 0.0630346 | 0.0711715 | +0.00814 |
| 7 | `tp_inj_n_l0_lsb` | `tt_-40c_3.63v` | 0.0618193 | 0.070205 | +0.00839 |

(the other 16 moved rows are the l1..l4 siblings, each within 0.0007 LSB of the
l0 delta; see the Appendix.)

These are not attributable to the PDK pin. Pair 5 re-ran the same extracted
deck bytes (`4fea809d...`) and moved nothing; the new record of pair 6
(`20261020-231428-0bf0747`) and of pair 5 (`20261020-233008-0bf0747`) agree on
every measurement (`requal_delta.py` reports 0 moved), whereas the *old* records
of pairs 5 and 6 — same deck bytes, `c6d73a3` — already disagree with each other
on the same 10 measurements (`requal_delta.py 20260923-104443-904af96
20261007-071907-800bf53`: 10 moved). `20261007-071907-800bf53` and
`20261007-072143-800bf53` were taken on a different host (PDK path under
`/Users/.../.volare`) than `20260923-104443-904af96`; whether that or an engine
build difference explains their ~0.007 LSB offset was not investigated here. The
V_DD-network arm's paired effect (new #7 minus new #6) matches the old pair's
(`20261007-072143-800bf53` minus `20261007-071907-800bf53`), e.g. `samp_gain_err_lsb`
-0.030 LSB at `tt_-40c_3.63v` in both.

None of the 10 measurements is a ratified-spec quantity: they are intermediate
per-level injection terms; the spec-bearing sums built from them
(`tp_inj_signal_dep_lsb` changed <= 3e-5 LSB, `bp_inj_mis_lsb`, `samp_gain_err_lsb`,
`samp_inl_worst_lsb`) did not move. The ratified spec is not relaxed. Follow-up
for the moved metrics: #623 asks for the host/engine cause of the 071907/072143
vs 104443 offset to be established. #622 tracks the signoff T1 item 8 re-pin that
the `sim/characterization-summary.md` citation updates in this PR require
(`signoff/run_signoff.py --check` fails items 8.analog/8.digital until then).

## Records worth knowing about

- `20261020-231430-0bf0747` is an **ERROR** record, kept as evidence (append-only):
  the first attempt at pair 5 lost its 3.30 V request to a Spot reclamation
  (`batch_job_interrupted`, past `batch.interrupted_grace_s=1800s`), so 9 of 27
  points are ERR and it carries no measurement table; the harness exited 2. The
  pair-5 comparison above uses the re-submission `20261020-233008-0bf0747`
  (27/27). The first attempt at pair 1 (id `...231427`) hit the same Spot reclamation
  on its 3.30 V request and recorded nothing (exit 3); it was re-submitted and
  landed as `20261020-235635-0bf0747`. Pairs 2, 4 and 7 were first submitted with
  the variant deck under `/tmp`, which the harness cannot record (the sims ran,
  nothing was written); they were re-submitted with the deck under `sim/.work/`.
- The new extracted records (#5, #6) inherit their **Netlist provenance** prose from
  `sim/dr0014-sampling/testbench-extracted/tb.json` (`netlist_provenance`, which
  names the older 20260805 extraction); the deck they actually ran is the
  checked-in `tb_dr0014_sampling_extracted.spice` (sha256 `4fea809d...`), the same
  bytes the old records recorded. Where prose and sha disagree, the sha governs.
- #2's new record states its provenance as "frozen snapshot authoritative" because
  the regeneration check was run after submit; the sha check passed (`7e7f1746...`).
- Six of the seven new records (all but `20261020-231040-0bf0747`) say `dirty` for
  the working tree: other new records and the delta script were uncommitted while
  they ran.
  The netlist sha256 and PDK pin, not the git state, are the provenance here.

## Not re-run

None. All seven un-superseded records were re-run, no fleet refusal remained
after re-submission.

## Appendix: complete old-vs-new tables

Generated by `sim/dr0014-sampling/requal_delta.py`.

### 1. `20260817-134517-cde979d` -> `20261020-235635-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `ff_125c_2.97v` | 0.125067 | 0.125066 | -1e-06 | 0.00125 | no |
| `tp_inj_n_l0_lsb` | `tt_27c_3.30v` | 0.0824696 | 0.0824697 | +1e-07 | 0.001 | no |
| `tp_inj_mis_l0_lsb` | `tt_125c_3.63v` | -0.0012537 | -0.00125362 | +8e-08 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `tt_-40c_2.97v` | 0.0593799 | 0.0593799 | +0 | 0.001 | no |
| `tp_inj_n_l1_lsb` | `ff_-40c_3.30v` | 0.113091 | 0.113092 | +1e-06 | 0.00113 | no |
| `tp_inj_mis_l1_lsb` | `ff_125c_2.97v` | -0.0014405 | -0.00144058 | -8e-08 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `ss_-40c_3.63v` | 0.0555845 | 0.0555844 | -1e-07 | 0.001 | no |
| `tp_inj_n_l2_lsb` | `ss_-40c_3.63v` | 0.0555845 | 0.0555844 | -1e-07 | 0.001 | no |
| `tp_inj_mis_l2_lsb` | `ss_-40c_3.30v` | -9.99016e-09 | -4.30428e-11 | +9.95e-09 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `ff_-40c_3.30v` | 0.113091 | 0.113092 | +1e-06 | 0.00113 | no |
| `tp_inj_n_l3_lsb` | `tt_-40c_2.97v` | 0.0593799 | 0.0593799 | +0 | 0.001 | no |
| `tp_inj_mis_l3_lsb` | `ff_125c_2.97v` | 0.0014405 | 0.00144058 | +8e-08 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `tt_27c_3.30v` | 0.0824696 | 0.0824697 | +1e-07 | 0.001 | no |
| `tp_inj_n_l4_lsb` | `ff_125c_2.97v` | 0.125067 | 0.125066 | -1e-06 | 0.00125 | no |
| `tp_inj_mis_l4_lsb` | `tt_125c_3.63v` | 0.0012537 | 0.00125362 | -8e-08 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `ff_125c_2.97v` | 0.0027504 | 0.00275047 | +7e-08 | 0.001 | no |
| `bp_inj_p_lsb` | `ff_125c_3.30v` | 0.0001971 | 0.000197198 | +9.8e-08 | 0.001 | no |
| `bp_inj_n_lsb` | `ff_125c_3.30v` | 0.0001971 | 0.000197198 | +9.8e-08 | 0.001 | no |
| `bp_inj_mis_lsb` | `tt_27c_2.97v` | -1e-08 | 1.74283e-11 | +1e-08 | 0.001 | no |
| `hold_l0_lsb` | `tt_125c_3.30v` | 915.876 | 915.877 | +0.001 | 9.16 | no |
| `res_l0_lsb` | `tt_-40c_2.97v` | 1290.14 | 1290.14 | +0 | 12.9 | no |
| `hold_l1_lsb` | `ff_125c_3.30v` | 457.983 | 457.984 | +0.001 | 4.58 | no |
| `res_l1_lsb` | `tt_-40c_2.97v` | 966.989 | 966.989 | +0 | 9.67 | no |
| `hold_l2_lsb` | `tt_27c_2.97v` | -6.76108e-10 | -6.76108e-10 | +4e-16 | 0.001 | no |
| `res_l2_lsb` | `ff_-40c_3.63v` | 509.959 | 509.958 | -0.001 | 5.1 | no |
| `hold_l3_lsb` | `ff_125c_3.30v` | -457.983 | -457.984 | -0.001 | 4.58 | no |
| `res_l3_lsb` | `tt_-40c_2.97v` | 51.6941 | 51.6941 | +0 | 0.517 | no |
| `hold_l4_lsb` | `tt_125c_3.30v` | -915.876 | -915.877 | -0.001 | 9.16 | no |
| `res_l4_lsb` | `tt_-40c_2.97v` | -406.04 | -406.04 | +0 | 4.06 | no |
| `samp_span_lsb` | `tt_-40c_2.97v` | -1830.8 | -1830.8 | +0 | 18.3 | no |
| `samp_gain_ratio` | `tt_27c_3.30v` | 0.993715 | 0.993714 | -1e-06 | 0.00994 | no |
| `samp_gain_err_lsb` | `tt_27c_3.63v` | 11.1518 | 11.1519 | +0.0001 | 0.112 | no |
| `samp_inl_l1_lsb` | `tt_27c_3.63v` | 0.06195 | 0.0620231 | +7.31e-05 | 0.001 | no |
| `samp_inl_l2_lsb` | `ss_125c_3.63v` | -1.66172e-11 | 1.77446e-10 | +1.94e-10 | 0.001 | no |
| `samp_inl_l3_lsb` | `tt_27c_3.63v` | -0.06195 | -0.0620231 | -7.31e-05 | 0.001 | no |
| `samp_inl_worst_lsb` | `tt_27c_3.63v` | 0.06195 | 0.0620231 | +7.31e-05 | 0.001 | no |
| `set_err_4leg_lsb` | `ss_27c_3.30v` | 0.0002 | 0.000112246 | -8.78e-05 | 0.001 | no |
| `set_err_3leg_lsb` | `ff_-40c_3.30v` | -0.0001 | -5.88272e-06 | +9.41e-05 | 0.001 | no |
| `set_err_delta_lsb` | `ss_27c_3.30v` | 0.0001 | -1.36841e-06 | -0.000101 | 0.001 | no |
| `step_4leg_lsb` | `tt_-40c_2.97v` | 255.012 | 255.012 | +0 | 2.55 | no |
| `step_3leg_lsb` | `ss_27c_3.30v` | 255.06 | 255.059 | -0.001 | 2.55 | no |
| `dhold_dc0_lsb` | `ss_27c_2.97v` | 0.1135 | 0.113425 | -7.5e-05 | 0.00114 | no |
| `dres_dc0_lsb` | `ff_-40c_2.97v` | -0.01585 | -0.0158427 | +7.3e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `ss_125c_3.30v` | 0.3397 | 0.339626 | -7.4e-05 | 0.0034 | no |
| `dres_dc1_lsb` | `ff_-40c_3.63v` | -0.04756 | -0.0475673 | -7.3e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `ss_27c_3.30v` | 1.1294 | 1.12933 | -7e-05 | 0.0113 | no |
| `dres_dc2_lsb` | `ss_27c_2.97v` | -0.12805 | -0.128043 | +7e-06 | 0.00128 | no |
| `dres_per_ff_lsb` | `ss_27c_2.97v` | -0.0012805 | -0.00128043 | +7e-08 | 0.001 | no |
| `ron_path_l0_ohm` | `tt_-40c_2.97v` | 15.2677 | 15.2677 | +0 | 0.153 | no |
| `ron_cell_l0_ohm` | `tt_-40c_2.97v` | 137.409 | 137.409 | +0 | 1.37 | no |
| `ron_path_l1_ohm` | `tt_-40c_2.97v` | 19.0333 | 19.0333 | +0 | 0.19 | no |
| `ron_cell_l1_ohm` | `tt_-40c_2.97v` | 171.3 | 171.3 | +0 | 1.71 | no |
| `ron_path_l2_ohm` | `tt_-40c_2.97v` | 25.4373 | 25.4373 | +0 | 0.254 | no |
| `ron_cell_l2_ohm` | `ff_27c_3.30v` | 179.871 | 179.872 | +0.001 | 1.8 | no |
| `ron_path_l3_ohm` | `tt_125c_3.30v` | 41.166 | 41.1659 | -0.0001 | 0.412 | no |
| `ron_cell_l3_ohm` | `ff_-40c_2.97v` | 260.488 | 260.489 | +0.001 | 2.6 | no |
| `ron_path_l4_ohm` | `tt_-40c_2.97v` | 23.6748 | 23.6748 | +0 | 0.237 | no |
| `ron_cell_l4_ohm` | `tt_-40c_2.97v` | 213.073 | 213.073 | +0 | 2.13 | no |
| `ron_path_worst_ohm` | `tt_125c_3.30v` | 41.166 | 41.1659 | -0.0001 | 0.412 | no |

0 of the paired measurements moved beyond tolerance.

### 2. `20260825-015032-446a3c4` -> `20261021-000250-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `tt_-40c_3.63v` | 0.079914 | 0.0799139 | -1e-07 | 0.001 | no |
| `tp_inj_n_l0_lsb` | `tt_-40c_2.97v` | 0.0572642 | 0.0572642 | +0 | 0.001 | no |
| `tp_inj_mis_l0_lsb` | `ff_27c_3.30v` | -0.0013758 | -0.00137586 | -6e-08 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `ff_-40c_3.63v` | 0.116408 | 0.116407 | -1e-06 | 0.00116 | no |
| `tp_inj_n_l1_lsb` | `tt_27c_3.30v` | 0.0802745 | 0.0802746 | +1e-07 | 0.001 | no |
| `tp_inj_mis_l1_lsb` | `ff_125c_3.63v` | -0.000723698 | -0.000723607 | +9.14e-08 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `ss_125c_3.30v` | 0.062539 | 0.0625389 | -1e-07 | 0.001 | no |
| `tp_inj_n_l2_lsb` | `ss_125c_3.30v` | 0.062539 | 0.0625389 | -1e-07 | 0.001 | no |
| `tp_inj_mis_l2_lsb` | `ss_-40c_2.97v` | 6.01776e-14 | -3.62729e-10 | -3.63e-10 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `tt_27c_3.30v` | 0.0802745 | 0.0802746 | +1e-07 | 0.001 | no |
| `tp_inj_n_l3_lsb` | `ff_-40c_3.63v` | 0.116408 | 0.116407 | -1e-06 | 0.00116 | no |
| `tp_inj_mis_l3_lsb` | `ff_125c_3.63v` | 0.000723698 | 0.000723606 | -9.24e-08 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `tt_-40c_2.97v` | 0.0572642 | 0.0572642 | +0 | 0.001 | no |
| `tp_inj_n_l4_lsb` | `tt_-40c_3.63v` | 0.079914 | 0.0799139 | -1e-07 | 0.001 | no |
| `tp_inj_mis_l4_lsb` | `ff_27c_3.30v` | 0.0013758 | 0.00137586 | +6e-08 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `tt_125c_3.63v` | 0.0018236 | 0.00182354 | -6e-08 | 0.001 | no |
| `bp_inj_p_lsb` | `ff_27c_3.30v` | -0.0001897 | -0.00018961 | +9e-08 | 0.001 | no |
| `bp_inj_n_lsb` | `ff_27c_3.30v` | -0.0001897 | -0.00018961 | +9e-08 | 0.001 | no |
| `bp_inj_mis_lsb` | `ff_-40c_3.63v` | 0 | 2.34461e-11 | +2.34e-11 | 0.001 | no |
| `hold_l0_lsb` | `ss_27c_3.30v` | 915.633 | 915.632 | -0.001 | 9.16 | no |
| `res_l0_lsb` | `ff_-40c_3.63v` | 1235.35 | 1235.34 | -0.01 | 12.4 | no |
| `hold_l1_lsb` | `ff_27c_2.97v` | 457.93 | 457.931 | +0.001 | 4.58 | no |
| `res_l1_lsb` | `tt_-40c_2.97v` | 966.989 | 966.989 | +0 | 9.67 | no |
| `hold_l2_lsb` | `ss_-40c_3.30v` | -3.10895e-10 | -3.10895e-10 | +5e-16 | 0.001 | no |
| `res_l2_lsb` | `ff_-40c_3.63v` | 509.959 | 509.958 | -0.001 | 5.1 | no |
| `hold_l3_lsb` | `ff_27c_2.97v` | -457.93 | -457.931 | -0.001 | 4.58 | no |
| `res_l3_lsb` | `tt_27c_3.63v` | 51.7525 | 51.7524 | -0.0001 | 0.518 | no |
| `hold_l4_lsb` | `ss_27c_3.30v` | -915.633 | -915.632 | +0.001 | 9.16 | no |
| `res_l4_lsb` | `tt_27c_3.63v` | -406.161 | -406.162 | -0.001 | 4.06 | no |
| `samp_span_lsb` | `ss_27c_3.30v` | -1831.27 | -1831.26 | +0.01 | 18.3 | no |
| `samp_gain_ratio` | `ff_125c_2.97v` | 0.993738 | 0.993739 | +1e-06 | 0.00994 | no |
| `samp_gain_err_lsb` | `ff_-40c_3.63v` | 10.933 | 10.9331 | +0.0001 | 0.109 | no |
| `samp_inl_l1_lsb` | `ff_27c_2.97v` | 0.02215 | 0.0222107 | +6.07e-05 | 0.001 | no |
| `samp_inl_l2_lsb` | `ss_-40c_3.63v` | -1.08632e-11 | 9.24781e-11 | +1.03e-10 | 0.001 | no |
| `samp_inl_l3_lsb` | `ff_27c_2.97v` | -0.02215 | -0.0222107 | -6.07e-05 | 0.001 | no |
| `samp_inl_worst_lsb` | `ff_27c_2.97v` | 0.02215 | 0.0222107 | +6.07e-05 | 0.001 | no |
| `set_err_4leg_lsb` | `tt_27c_2.97v` | -0.0001 | -1.49087e-05 | +8.51e-05 | 0.001 | no |
| `set_err_3leg_lsb` | `tt_27c_2.97v` | -0.0001 | -1.40471e-05 | +8.6e-05 | 0.001 | no |
| `set_err_delta_lsb` | `tt_-40c_2.97v` | 0.0001 | -8.78401e-07 | -0.000101 | 0.001 | no |
| `step_4leg_lsb` | `tt_-40c_2.97v` | 255.012 | 255.012 | +0 | 2.55 | no |
| `step_3leg_lsb` | `tt_-40c_2.97v` | 255.012 | 255.012 | +0 | 2.55 | no |
| `dhold_dc0_lsb` | `ss_-40c_2.97v` | 0.1137 | 0.113602 | -9.8e-05 | 0.00114 | no |
| `dres_dc0_lsb` | `ff_125c_3.30v` | -0.01577 | -0.0157771 | -7.1e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `ss_27c_3.30v` | 0.34 | 0.340084 | +8.4e-05 | 0.0034 | no |
| `dres_dc1_lsb` | `ss_125c_3.63v` | -0.03859 | -0.038581 | +9e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `tt_-40c_3.30v` | 1.2433 | 1.2432 | -0.0001 | 0.0124 | no |
| `dres_dc2_lsb` | `ss_125c_3.30v` | -0.12798 | -0.127986 | -6e-06 | 0.00128 | no |
| `dres_per_ff_lsb` | `ss_-40c_3.30v` | -0.0012809 | -0.00128096 | -6e-08 | 0.001 | no |
| `ron_path_l0_ohm` | `tt_27c_3.63v` | 8.34417 | 8.34418 | +1e-05 | 0.0834 | no |
| `ron_cell_l0_ohm` | `ff_27c_3.63v` | 69.7331 | 69.733 | -0.0001 | 0.697 | no |
| `ron_path_l1_ohm` | `ff_-40c_3.30v` | 7.7225 | 7.72251 | +1e-05 | 0.0772 | no |
| `ron_cell_l1_ohm` | `tt_-40c_3.30v` | 76.7853 | 76.7854 | +0.0001 | 0.768 | no |
| `ron_path_l2_ohm` | `tt_-40c_2.97v` | 12.2935 | 12.2935 | +0 | 0.123 | no |
| `ron_cell_l2_ohm` | `ss_27c_2.97v` | 187.792 | 187.791 | -0.001 | 1.88 | no |
| `ron_path_l3_ohm` | `tt_-40c_2.97v` | 17.2162 | 17.2162 | +0 | 0.172 | no |
| `ron_cell_l3_ohm` | `ff_-40c_3.63v` | 92.8725 | 92.8726 | +0.0001 | 0.929 | no |
| `ron_path_l4_ohm` | `ss_27c_3.30v` | 14.2192 | 14.2193 | +0.0001 | 0.142 | no |
| `ron_cell_l4_ohm` | `tt_-40c_2.97v` | 103.081 | 103.081 | +0 | 1.03 | no |
| `ron_path_worst_ohm` | `tt_-40c_2.97v` | 17.2162 | 17.2162 | +0 | 0.172 | no |

0 of the paired measurements moved beyond tolerance.

### 3. `20260923-085243-664c8dc` -> `20261020-231040-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `ff_125c_2.97v` | 0.125067 | 0.125066 | -1e-06 | 0.00125 | no |
| `tp_inj_n_l0_lsb` | `tt_27c_3.30v` | 0.0824696 | 0.0824697 | +1e-07 | 0.001 | no |
| `tp_inj_mis_l0_lsb` | `tt_125c_3.63v` | -0.0012537 | -0.00125362 | +8e-08 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `tt_-40c_2.97v` | 0.0593799 | 0.0593799 | +0 | 0.001 | no |
| `tp_inj_n_l1_lsb` | `ff_-40c_3.30v` | 0.113091 | 0.113092 | +1e-06 | 0.00113 | no |
| `tp_inj_mis_l1_lsb` | `ff_125c_2.97v` | -0.0014405 | -0.00144058 | -8e-08 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `ss_-40c_3.63v` | 0.0555845 | 0.0555844 | -1e-07 | 0.001 | no |
| `tp_inj_n_l2_lsb` | `ss_-40c_3.63v` | 0.0555845 | 0.0555844 | -1e-07 | 0.001 | no |
| `tp_inj_mis_l2_lsb` | `ss_-40c_3.30v` | -9.99016e-09 | -4.30428e-11 | +9.95e-09 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `ff_-40c_3.30v` | 0.113091 | 0.113092 | +1e-06 | 0.00113 | no |
| `tp_inj_n_l3_lsb` | `tt_-40c_2.97v` | 0.0593799 | 0.0593799 | +0 | 0.001 | no |
| `tp_inj_mis_l3_lsb` | `ff_125c_2.97v` | 0.0014405 | 0.00144058 | +8e-08 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `tt_27c_3.30v` | 0.0824696 | 0.0824697 | +1e-07 | 0.001 | no |
| `tp_inj_n_l4_lsb` | `ff_125c_2.97v` | 0.125067 | 0.125066 | -1e-06 | 0.00125 | no |
| `tp_inj_mis_l4_lsb` | `tt_125c_3.63v` | 0.0012537 | 0.00125362 | -8e-08 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `ff_125c_2.97v` | 0.0027504 | 0.00275047 | +7e-08 | 0.001 | no |
| `bp_inj_p_lsb` | `ff_125c_3.30v` | 0.0001971 | 0.000197198 | +9.8e-08 | 0.001 | no |
| `bp_inj_n_lsb` | `ff_125c_3.30v` | 0.0001971 | 0.000197198 | +9.8e-08 | 0.001 | no |
| `bp_inj_mis_lsb` | `tt_27c_2.97v` | -1e-08 | 1.74283e-11 | +1e-08 | 0.001 | no |
| `hold_l0_lsb` | `tt_125c_3.30v` | 915.876 | 915.877 | +0.001 | 9.16 | no |
| `res_l0_lsb` | `tt_-40c_2.97v` | 1290.14 | 1290.14 | +0 | 12.9 | no |
| `hold_l1_lsb` | `ff_125c_3.30v` | 457.983 | 457.984 | +0.001 | 4.58 | no |
| `res_l1_lsb` | `tt_-40c_2.97v` | 966.989 | 966.989 | +0 | 9.67 | no |
| `hold_l2_lsb` | `tt_27c_2.97v` | -6.76108e-10 | -6.76108e-10 | +4e-16 | 0.001 | no |
| `res_l2_lsb` | `ff_-40c_3.63v` | 509.959 | 509.958 | -0.001 | 5.1 | no |
| `hold_l3_lsb` | `ff_125c_3.30v` | -457.983 | -457.984 | -0.001 | 4.58 | no |
| `res_l3_lsb` | `tt_-40c_2.97v` | 51.6941 | 51.6941 | +0 | 0.517 | no |
| `hold_l4_lsb` | `tt_125c_3.30v` | -915.876 | -915.877 | -0.001 | 9.16 | no |
| `res_l4_lsb` | `tt_-40c_2.97v` | -406.04 | -406.04 | +0 | 4.06 | no |
| `samp_span_lsb` | `tt_-40c_2.97v` | -1830.8 | -1830.8 | +0 | 18.3 | no |
| `samp_gain_ratio` | `tt_27c_3.30v` | 0.993715 | 0.993714 | -1e-06 | 0.00994 | no |
| `samp_gain_err_lsb` | `tt_27c_3.63v` | 11.1518 | 11.1519 | +0.0001 | 0.112 | no |
| `samp_inl_l1_lsb` | `tt_27c_3.63v` | 0.06195 | 0.0620231 | +7.31e-05 | 0.001 | no |
| `samp_inl_l2_lsb` | `ss_125c_3.63v` | -1.66172e-11 | 1.77446e-10 | +1.94e-10 | 0.001 | no |
| `samp_inl_l3_lsb` | `tt_27c_3.63v` | -0.06195 | -0.0620231 | -7.31e-05 | 0.001 | no |
| `samp_inl_worst_lsb` | `tt_27c_3.63v` | 0.06195 | 0.0620231 | +7.31e-05 | 0.001 | no |
| `set_err_4leg_lsb` | `ss_27c_3.30v` | 0.0002 | 0.000112246 | -8.78e-05 | 0.001 | no |
| `set_err_3leg_lsb` | `ff_-40c_3.30v` | -0.0001 | -5.88272e-06 | +9.41e-05 | 0.001 | no |
| `set_err_delta_lsb` | `ss_27c_3.30v` | 0.0001 | -1.36841e-06 | -0.000101 | 0.001 | no |
| `step_4leg_lsb` | `tt_-40c_2.97v` | 255.012 | 255.012 | +0 | 2.55 | no |
| `step_3leg_lsb` | `ss_27c_3.30v` | 255.06 | 255.059 | -0.001 | 2.55 | no |
| `dhold_dc0_lsb` | `ss_27c_2.97v` | 0.1135 | 0.113425 | -7.5e-05 | 0.00114 | no |
| `dres_dc0_lsb` | `ff_-40c_2.97v` | -0.01585 | -0.0158427 | +7.3e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `ss_125c_3.30v` | 0.3397 | 0.339626 | -7.4e-05 | 0.0034 | no |
| `dres_dc1_lsb` | `ff_-40c_3.63v` | -0.04756 | -0.0475673 | -7.3e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `ss_27c_3.30v` | 1.1294 | 1.12933 | -7e-05 | 0.0113 | no |
| `dres_dc2_lsb` | `ss_27c_2.97v` | -0.12805 | -0.128043 | +7e-06 | 0.00128 | no |
| `dres_per_ff_lsb` | `ss_27c_2.97v` | -0.0012805 | -0.00128043 | +7e-08 | 0.001 | no |
| `ron_path_l0_ohm` | `tt_-40c_2.97v` | 15.2677 | 15.2677 | +0 | 0.153 | no |
| `ron_cell_l0_ohm` | `tt_-40c_2.97v` | 137.409 | 137.409 | +0 | 1.37 | no |
| `ron_path_l1_ohm` | `tt_-40c_2.97v` | 19.0333 | 19.0333 | +0 | 0.19 | no |
| `ron_cell_l1_ohm` | `tt_-40c_2.97v` | 171.3 | 171.3 | +0 | 1.71 | no |
| `ron_path_l2_ohm` | `tt_-40c_2.97v` | 25.4373 | 25.4373 | +0 | 0.254 | no |
| `ron_cell_l2_ohm` | `ff_27c_3.30v` | 179.871 | 179.872 | +0.001 | 1.8 | no |
| `ron_path_l3_ohm` | `tt_125c_3.30v` | 41.166 | 41.1659 | -0.0001 | 0.412 | no |
| `ron_cell_l3_ohm` | `ff_-40c_2.97v` | 260.488 | 260.489 | +0.001 | 2.6 | no |
| `ron_path_l4_ohm` | `tt_-40c_2.97v` | 23.6748 | 23.6748 | +0 | 0.237 | no |
| `ron_cell_l4_ohm` | `tt_-40c_2.97v` | 213.073 | 213.073 | +0 | 2.13 | no |
| `ron_path_worst_ohm` | `tt_125c_3.30v` | 41.166 | 41.1659 | -0.0001 | 0.412 | no |

0 of the paired measurements moved beyond tolerance.

### 4. `20260923-092849-664c8dc` -> `20261020-235634-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `tt_-40c_2.97v` | 0.0585696 | 0.0585697 | +1e-07 | 0.001 | no |
| `tp_inj_n_l0_lsb` | `tt_-40c_2.97v` | 0.0600355 | 0.0600355 | +0 | 0.001 | no |
| `tp_inj_mis_l0_lsb` | `tt_125c_3.63v` | -0.0012564 | -0.00125634 | +6e-08 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `ff_27c_3.30v` | 0.119804 | 0.119803 | -1e-06 | 0.0012 | no |
| `tp_inj_n_l1_lsb` | `ff_-40c_2.97v` | 0.10023 | 0.100229 | -1e-06 | 0.001 | no |
| `tp_inj_mis_l1_lsb` | `ff_27c_3.63v` | -0.0017622 | -0.00176228 | -8e-08 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `ff_125c_3.63v` | 0.143154 | 0.143153 | -1e-06 | 0.00143 | no |
| `tp_inj_n_l2_lsb` | `ff_125c_3.63v` | 0.143154 | 0.143153 | -1e-06 | 0.00143 | no |
| `tp_inj_mis_l2_lsb` | `ss_-40c_3.63v` | -4.4966e-12 | -8.03533e-10 | -7.99e-10 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `ff_-40c_2.97v` | 0.10023 | 0.100229 | -1e-06 | 0.001 | no |
| `tp_inj_n_l3_lsb` | `ff_27c_3.30v` | 0.119804 | 0.119803 | -1e-06 | 0.0012 | no |
| `tp_inj_mis_l3_lsb` | `ff_27c_3.63v` | 0.0017622 | 0.00176228 | +8e-08 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `tt_-40c_2.97v` | 0.0600355 | 0.0600355 | +0 | 0.001 | no |
| `tp_inj_n_l4_lsb` | `tt_-40c_2.97v` | 0.0585696 | 0.0585697 | +1e-07 | 0.001 | no |
| `tp_inj_mis_l4_lsb` | `tt_125c_3.63v` | 0.0012564 | 0.00125634 | -6e-08 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `ff_125c_2.97v` | 0.0027978 | 0.00279787 | +7e-08 | 0.001 | no |
| `bp_inj_p_lsb` | `ff_125c_3.30v` | 0.0021242 | 0.00212412 | -8e-08 | 0.001 | no |
| `bp_inj_n_lsb` | `ff_125c_3.30v` | 0.0021242 | 0.00212412 | -8e-08 | 0.001 | no |
| `bp_inj_mis_lsb` | `tt_125c_3.63v` | 0 | -2.58684e-11 | -2.59e-11 | 0.001 | no |
| `hold_l0_lsb` | `tt_125c_3.30v` | 915.876 | 915.877 | +0.001 | 9.16 | no |
| `res_l0_lsb` | `ss_125c_3.63v` | 1285.67 | 1285.68 | +0.01 | 12.9 | no |
| `hold_l1_lsb` | `tt_-40c_2.97v` | 457.943 | 457.943 | +0 | 4.58 | no |
| `res_l1_lsb` | `tt_-40c_3.30v` | 967.322 | 967.323 | +0.001 | 9.67 | no |
| `hold_l2_lsb` | `ss_-40c_3.63v` | -7.81142e-10 | -7.81142e-10 | +3e-16 | 0.001 | no |
| `res_l2_lsb` | `ff_-40c_3.63v` | 509.959 | 509.958 | -0.001 | 5.1 | no |
| `hold_l3_lsb` | `tt_-40c_2.97v` | -457.943 | -457.943 | +0 | 4.58 | no |
| `res_l3_lsb` | `ff_27c_3.30v` | 51.7642 | 51.7643 | +0.0001 | 0.518 | no |
| `hold_l4_lsb` | `tt_125c_3.30v` | -915.876 | -915.877 | -0.001 | 9.16 | no |
| `res_l4_lsb` | `ff_125c_3.30v` | -406.082 | -406.081 | +0.001 | 4.06 | no |
| `samp_span_lsb` | `tt_-40c_2.97v` | -1830.8 | -1830.8 | +0 | 18.3 | no |
| `samp_gain_ratio` | `tt_125c_2.97v` | 0.993507 | 0.993506 | -1e-06 | 0.00994 | no |
| `samp_gain_err_lsb` | `ff_125c_3.63v` | 10.8732 | 10.8731 | -0.0001 | 0.109 | no |
| `samp_inl_l1_lsb` | `ff_-40c_2.97v` | 0.0744 | 0.0743365 | -6.35e-05 | 0.001 | no |
| `samp_inl_l2_lsb` | `ss_125c_3.30v` | -5.06856e-11 | 5.16325e-11 | +1.02e-10 | 0.001 | no |
| `samp_inl_l3_lsb` | `ff_-40c_2.97v` | -0.0744 | -0.0743365 | +6.35e-05 | 0.001 | no |
| `samp_inl_worst_lsb` | `ff_-40c_2.97v` | 0.0744 | 0.0743365 | -6.35e-05 | 0.001 | no |
| `set_err_4leg_lsb` | `ff_125c_3.63v` | 0.0111 | 0.011181 | +8.1e-05 | 0.001 | no |
| `set_err_3leg_lsb` | `ff_-40c_3.63v` | 0.0115 | 0.0115834 | +8.34e-05 | 0.001 | no |
| `set_err_delta_lsb` | `ss_125c_3.63v` | 0.0001 | -2.69559e-06 | -0.000103 | 0.001 | no |
| `step_4leg_lsb` | `tt_-40c_2.97v` | 255.055 | 255.055 | +0 | 2.55 | no |
| `step_3leg_lsb` | `tt_-40c_2.97v` | 255.055 | 255.055 | +0 | 2.55 | no |
| `dhold_dc0_lsb` | `tt_-40c_3.30v` | 0.1248 | 0.124877 | +7.7e-05 | 0.00125 | no |
| `dres_dc0_lsb` | `ss_27c_3.63v` | -0.01296 | -0.0129515 | +8.5e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `tt_27c_2.97v` | 0.3738 | 0.373719 | -8.1e-05 | 0.00374 | no |
| `dres_dc1_lsb` | `tt_27c_3.30v` | -0.04272 | -0.0427127 | +7.3e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `ff_27c_3.63v` | 1.378 | 1.37792 | -8e-05 | 0.0138 | no |
| `dres_dc2_lsb` | `tt_125c_3.63v` | -0.14188 | -0.141887 | -7e-06 | 0.00142 | no |
| `dres_per_ff_lsb` | `tt_125c_3.63v` | -0.0014188 | -0.00141887 | -7e-08 | 0.001 | no |
| `ron_path_l0_ohm` | `tt_-40c_2.97v` | 15.2677 | 15.2677 | +0 | 0.153 | no |
| `ron_cell_l0_ohm` | `tt_-40c_2.97v` | 137.409 | 137.409 | +0 | 1.37 | no |
| `ron_path_l1_ohm` | `tt_-40c_2.97v` | 19.0333 | 19.0333 | +0 | 0.19 | no |
| `ron_cell_l1_ohm` | `tt_-40c_2.97v` | 171.3 | 171.3 | +0 | 1.71 | no |
| `ron_path_l2_ohm` | `tt_-40c_2.97v` | 25.4373 | 25.4373 | +0 | 0.254 | no |
| `ron_cell_l2_ohm` | `ff_27c_3.30v` | 179.871 | 179.872 | +0.001 | 1.8 | no |
| `ron_path_l3_ohm` | `tt_125c_3.30v` | 41.166 | 41.1659 | -0.0001 | 0.412 | no |
| `ron_cell_l3_ohm` | `ff_-40c_2.97v` | 260.488 | 260.489 | +0.001 | 2.6 | no |
| `ron_path_l4_ohm` | `tt_-40c_2.97v` | 23.6748 | 23.6748 | +0 | 0.237 | no |
| `ron_cell_l4_ohm` | `tt_-40c_2.97v` | 213.073 | 213.073 | +0 | 2.13 | no |
| `ron_path_worst_ohm` | `tt_125c_3.30v` | 41.166 | 41.1659 | -0.0001 | 0.412 | no |

0 of the paired measurements moved beyond tolerance.

### 5. `20260923-104443-904af96` -> `20261020-233008-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `tt_-40c_2.97v` | 0.0444209 | 0.0444209 | +0 | 0.001 | no |
| `tp_inj_n_l0_lsb` | `tt_-40c_2.97v` | 0.0438231 | 0.0438231 | +0 | 0.001 | no |
| `tp_inj_mis_l0_lsb` | `ff_125c_3.30v` | -2.72144e-05 | -2.72616e-05 | -4.72e-08 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `tt_-40c_2.97v` | 0.0446554 | 0.0446554 | +0 | 0.001 | no |
| `tp_inj_n_l1_lsb` | `tt_-40c_2.97v` | 0.0441797 | 0.0441797 | +0 | 0.001 | no |
| `tp_inj_mis_l1_lsb` | `ff_125c_3.30v` | 4.08256e-06 | 3.99459e-06 | -8.8e-08 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `ff_125c_2.97v` | 0.118874 | 0.118875 | +1e-06 | 0.00119 | no |
| `tp_inj_n_l2_lsb` | `tt_27c_3.30v` | 0.0688197 | 0.0688198 | +1e-07 | 0.001 | no |
| `tp_inj_mis_l2_lsb` | `ff_-40c_3.63v` | 0.00040785 | 0.000407801 | -4.87e-08 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `tt_-40c_2.97v` | 0.0448291 | 0.0448291 | +0 | 0.001 | no |
| `tp_inj_n_l3_lsb` | `tt_-40c_2.97v` | 0.0440701 | 0.0440701 | +0 | 0.001 | no |
| `tp_inj_mis_l3_lsb` | `ff_125c_3.30v` | -0.000225623 | -0.000225543 | +8.04e-08 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `tt_-40c_2.97v` | 0.0444706 | 0.0444706 | +0 | 0.001 | no |
| `tp_inj_n_l4_lsb` | `tt_-40c_3.30v` | 0.0542651 | 0.0542652 | +1e-07 | 0.001 | no |
| `tp_inj_mis_l4_lsb` | `ff_125c_3.30v` | -0.000217963 | -0.000218003 | -4e-08 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `ff_125c_3.63v` | 0.000597901 | 0.000597813 | -8.83e-08 | 0.001 | no |
| `bp_inj_p_lsb` | `ss_-40c_3.63v` | -0.0832036 | -0.0832035 | +1e-07 | 0.001 | no |
| `bp_inj_n_lsb` | `tt_125c_3.63v` | -0.0861799 | -0.0861798 | +1e-07 | 0.001 | no |
| `bp_inj_mis_lsb` | `ff_-40c_3.63v` | -0.00566623 | -0.00566619 | +4e-08 | 0.001 | no |
| `hold_l0_lsb` | `ff_-40c_3.30v` | 902.042 | 902.041 | -0.001 | 9.02 | no |
| `res_l0_lsb` | `tt_-40c_2.97v` | 1367.42 | 1367.42 | +0 | 13.7 | no |
| `hold_l1_lsb` | `tt_-40c_2.97v` | 451.651 | 451.651 | +0 | 4.52 | no |
| `res_l1_lsb` | `tt_27c_2.97v` | 953.898 | 953.897 | -0.001 | 9.54 | no |
| `hold_l2_lsb` | `tt_125c_3.63v` | -0.00483289 | -0.00483288 | +1e-08 | 0.001 | no |
| `res_l2_lsb` | `ss_27c_3.63v` | 503.623 | 503.624 | +0.001 | 5.04 | no |
| `hold_l3_lsb` | `tt_27c_2.97v` | -451.651 | -451.65 | +0.001 | 4.52 | no |
| `res_l3_lsb` | `tt_-40c_2.97v` | 50.9767 | 50.9767 | +0 | 0.51 | no |
| `hold_l4_lsb` | `ff_-40c_2.97v` | -901.798 | -901.797 | +0.001 | 9.02 | no |
| `res_l4_lsb` | `ff_125c_3.63v` | -399.957 | -399.958 | -0.001 | 4 | no |
| `samp_span_lsb` | `tt_-40c_2.97v` | -1805.69 | -1805.69 | +0 | 18.1 | no |
| `samp_gain_ratio` | `tt_-40c_2.97v` | 0.979647 | 0.979647 | +0 | 0.0098 | no |
| `samp_gain_err_lsb` | `ss_125c_3.30v` | 34.7249 | 34.725 | +0.0001 | 0.347 | no |
| `samp_inl_l1_lsb` | `ff_27c_3.30v` | -0.018 | -0.0179334 | +6.66e-05 | 0.001 | no |
| `samp_inl_l2_lsb` | `ff_125c_2.97v` | -0.000206622 | -0.000246987 | -4.04e-05 | 0.001 | no |
| `samp_inl_l3_lsb` | `tt_125c_3.63v` | -0.028725 | -0.0286637 | +6.13e-05 | 0.001 | no |
| `samp_inl_worst_lsb` | `ff_27c_3.30v` | 0.018 | 0.0179334 | -6.66e-05 | 0.001 | no |
| `dhold_dc0_lsb` | `ss_27c_2.97v` | 0.1101 | 0.110171 | +7.1e-05 | 0.0011 | no |
| `dres_dc0_lsb` | `ss_-40c_3.63v` | -0.01245 | -0.0124424 | +7.6e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `ff_27c_2.97v` | 0.4006 | 0.400509 | -9.1e-05 | 0.00401 | no |
| `dres_dc1_lsb` | `ff_27c_3.63v` | -0.04541 | -0.0454022 | +7.8e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `ff_27c_2.97v` | 1.3296 | 1.32951 | -9e-05 | 0.0133 | no |
| `dres_dc2_lsb` | `ss_-40c_2.97v` | -0.12338 | -0.123389 | -9e-06 | 0.00123 | no |
| `dres_per_ff_lsb` | `ss_-40c_2.97v` | -0.0012338 | -0.00123389 | -9e-08 | 0.001 | no |

0 of the paired measurements moved beyond tolerance.

### 6. `20261007-071907-800bf53` -> `20261020-231428-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `ff_-40c_3.63v` | 0.106386 | 0.113089 | +0.0067 | 0.00113 | yes |
| `tp_inj_n_l0_lsb` | `ff_-40c_3.63v` | 0.105739 | 0.112588 | +0.00685 | 0.00113 | yes |
| `tp_inj_mis_l0_lsb` | `ff_125c_3.63v` | -0.000275984 | -0.000543593 | -0.000268 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `ff_-40c_3.63v` | 0.106569 | 0.113261 | +0.00669 | 0.00113 | yes |
| `tp_inj_n_l1_lsb` | `ff_-40c_3.63v` | 0.10583 | 0.112669 | +0.00684 | 0.00113 | yes |
| `tp_inj_mis_l1_lsb` | `ff_125c_3.63v` | -0.000183487 | -0.000454227 | -0.000271 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `ff_-40c_3.63v` | 0.105563 | 0.11228 | +0.00672 | 0.00112 | yes |
| `tp_inj_n_l2_lsb` | `ff_-40c_3.63v` | 0.10501 | 0.111872 | +0.00686 | 0.00112 | yes |
| `tp_inj_mis_l2_lsb` | `ff_125c_3.63v` | -0.00038469 | -0.000654678 | -0.00027 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `ff_-40c_3.63v` | 0.106458 | 0.11315 | +0.00669 | 0.00113 | yes |
| `tp_inj_n_l3_lsb` | `ff_-40c_3.63v` | 0.106067 | 0.112901 | +0.00683 | 0.00113 | yes |
| `tp_inj_mis_l3_lsb` | `ff_125c_3.63v` | -0.000591993 | -0.000861406 | -0.000269 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `ff_-40c_3.63v` | 0.106363 | 0.113066 | +0.0067 | 0.00113 | yes |
| `tp_inj_n_l4_lsb` | `ff_-40c_3.63v` | 0.105904 | 0.112748 | +0.00684 | 0.00113 | yes |
| `tp_inj_mis_l4_lsb` | `ff_125c_3.63v` | -0.000524829 | -0.000799237 | -0.000274 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `ff_27c_2.97v` | 0.000594928 | 0.000567131 | -2.78e-05 | 0.001 | no |
| `bp_inj_p_lsb` | `ff_125c_2.97v` | -0.100841 | -0.100747 | +9.4e-05 | 0.00101 | no |
| `bp_inj_n_lsb` | `ff_125c_2.97v` | -0.0951735 | -0.0950834 | +9.01e-05 | 0.001 | no |
| `bp_inj_mis_lsb` | `ff_27c_3.30v` | -0.0056645 | -0.00567326 | -8.76e-06 | 0.001 | no |
| `hold_l0_lsb` | `ff_-40c_3.63v` | 902.225 | 902.224 | -0.001 | 9.02 | no |
| `res_l0_lsb` | `tt_-40c_2.97v` | 1367.42 | 1367.42 | +0 | 13.7 | no |
| `hold_l1_lsb` | `ff_125c_2.97v` | 450.909 | 450.908 | -0.001 | 4.51 | no |
| `res_l1_lsb` | `tt_27c_2.97v` | 953.898 | 953.897 | -0.001 | 9.54 | no |
| `hold_l2_lsb` | `ff_125c_3.63v` | -0.0060566 | -0.00632007 | -0.000263 | 0.001 | no |
| `res_l2_lsb` | `ff_125c_2.97v` | 502.006 | 502.005 | -0.001 | 5.02 | no |
| `hold_l3_lsb` | `ff_-40c_2.97v` | -450.966 | -450.965 | +0.001 | 4.51 | no |
| `res_l3_lsb` | `ff_-40c_2.97v` | 50.9446 | 50.9448 | +0.0002 | 0.509 | no |
| `hold_l4_lsb` | `ff_-40c_2.97v` | -901.798 | -901.797 | +0.001 | 9.02 | no |
| `res_l4_lsb` | `ff_-40c_2.97v` | -399.864 | -399.863 | +0.001 | 4 | no |
| `samp_span_lsb` | `ss_125c_3.30v` | -1808.47 | -1808.48 | -0.01 | 18.1 | no |
| `samp_gain_ratio` | `ss_125c_3.30v` | 0.98116 | 0.981161 | +1e-06 | 0.00981 | no |
| `samp_gain_err_lsb` | `ss_27c_3.63v` | 34.3622 | 34.3619 | -0.0003 | 0.344 | no |
| `samp_inl_l1_lsb` | `tt_27c_3.30v` | 0.10565 | 0.105741 | +9.1e-05 | 0.00106 | no |
| `samp_inl_l2_lsb` | `ff_-40c_2.97v` | -0.000438384 | -0.000492461 | -5.41e-05 | 0.001 | no |
| `samp_inl_l3_lsb` | `ff_-40c_2.97v` | -0.064125 | -0.0642483 | -0.000123 | 0.001 | no |
| `samp_inl_worst_lsb` | `ff_-40c_2.97v` | 0.064125 | 0.0642483 | +0.000123 | 0.001 | no |
| `dhold_dc0_lsb` | `tt_-40c_3.63v` | 0.1209 | 0.120983 | +8.3e-05 | 0.00121 | no |
| `dres_dc0_lsb` | `ff_27c_3.63v` | -0.01515 | -0.0151425 | +7.5e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `ss_125c_3.63v` | 0.3299 | 0.329965 | +6.5e-05 | 0.0033 | no |
| `dres_dc1_lsb` | `ff_27c_3.30v` | -0.04535 | -0.045342 | +8e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `ss_-40c_3.63v` | 1.0987 | 1.09862 | -8e-05 | 0.011 | no |
| `dres_dc2_lsb` | `ss_-40c_3.63v` | -0.12388 | -0.123896 | -1.6e-05 | 0.00124 | no |
| `dres_per_ff_lsb` | `ss_-40c_3.63v` | -0.0012388 | -0.00123896 | -1.6e-07 | 0.001 | no |

10 of the paired measurements moved beyond tolerance.

### 7. `20261007-072143-800bf53` -> `20261020-235636-0bf0747`

| metric | corner of max \|delta\| | old | new | delta | tolerance | moved |
|---|---|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `tt_-40c_3.63v` | 0.0630346 | 0.0711715 | +0.00814 | 0.001 | yes |
| `tp_inj_n_l0_lsb` | `tt_-40c_3.63v` | 0.0618193 | 0.070205 | +0.00839 | 0.001 | yes |
| `tp_inj_mis_l0_lsb` | `ss_-40c_3.30v` | 0.00113686 | 0.000714622 | -0.000422 | 0.001 | no |
| `tp_inj_p_l1_lsb` | `tt_-40c_3.63v` | 0.0632807 | 0.0714031 | +0.00812 | 0.001 | yes |
| `tp_inj_n_l1_lsb` | `tt_-40c_3.63v` | 0.0622835 | 0.0706523 | +0.00837 | 0.001 | yes |
| `tp_inj_mis_l1_lsb` | `ss_-40c_3.30v` | 0.0010133 | 0.000603364 | -0.00041 | 0.001 | no |
| `tp_inj_p_l2_lsb` | `tt_-40c_3.63v` | 0.0627266 | 0.0708678 | +0.00814 | 0.001 | yes |
| `tp_inj_n_l2_lsb` | `tt_-40c_3.63v` | 0.0618291 | 0.0702139 | +0.00838 | 0.001 | yes |
| `tp_inj_mis_l2_lsb` | `ss_-40c_3.30v` | 0.000964189 | 0.000534716 | -0.000429 | 0.001 | no |
| `tp_inj_p_l3_lsb` | `tt_-40c_3.63v` | 0.063248 | 0.0713687 | +0.00812 | 0.001 | yes |
| `tp_inj_n_l3_lsb` | `tt_-40c_3.63v` | 0.0624178 | 0.0707845 | +0.00837 | 0.001 | yes |
| `tp_inj_mis_l3_lsb` | `ss_-40c_3.30v` | 0.000921799 | 0.000471023 | -0.000451 | 0.001 | no |
| `tp_inj_p_l4_lsb` | `tt_-40c_3.63v` | 0.0627793 | 0.0709183 | +0.00814 | 0.001 | yes |
| `tp_inj_n_l4_lsb` | `tt_-40c_3.63v` | 0.0621863 | 0.0705662 | +0.00838 | 0.001 | yes |
| `tp_inj_mis_l4_lsb` | `ss_-40c_3.30v` | 0.000787827 | 0.000352565 | -0.000435 | 0.001 | no |
| `tp_inj_signal_dep_lsb` | `tt_-40c_3.63v` | 0.000554143 | 0.000535365 | -1.88e-05 | 0.001 | no |
| `bp_inj_p_lsb` | `ss_-40c_3.30v` | -0.0848047 | -0.0848574 | -5.27e-05 | 0.001 | no |
| `bp_inj_n_lsb` | `tt_-40c_3.30v` | -0.0884899 | -0.0885415 | -5.16e-05 | 0.001 | no |
| `bp_inj_mis_lsb` | `ff_125c_3.30v` | -0.00574537 | -0.00574985 | -4.48e-06 | 0.001 | no |
| `hold_l0_lsb` | `ff_-40c_3.30v` | 902.057 | 902.056 | -0.001 | 9.02 | no |
| `res_l0_lsb` | `tt_-40c_2.97v` | 1367.59 | 1367.59 | +0 | 13.7 | no |
| `hold_l1_lsb` | `ff_125c_3.30v` | 450.987 | 450.988 | +0.001 | 4.51 | no |
| `res_l1_lsb` | `ff_27c_2.97v` | 952.809 | 952.81 | +0.001 | 9.53 | no |
| `hold_l2_lsb` | `ss_-40c_3.30v` | -0.00373494 | -0.00416662 | -0.000432 | 0.001 | no |
| `res_l2_lsb` | `ff_27c_3.30v` | 502.119 | 502.118 | -0.001 | 5.02 | no |
| `hold_l3_lsb` | `ff_125c_3.30v` | -451 | -450.999 | +0.001 | 4.51 | no |
| `res_l3_lsb` | `ss_-40c_3.30v` | 51.0227 | 51.0222 | -0.0005 | 0.51 | no |
| `hold_l4_lsb` | `ss_-40c_3.30v` | -904.075 | -904.076 | -0.001 | 9.04 | no |
| `res_l4_lsb` | `ff_-40c_2.97v` | -399.863 | -399.864 | -0.001 | 4 | no |
| `samp_span_lsb` | `tt_125c_3.63v` | -1807.02 | -1807.01 | +0.01 | 18.1 | no |
| `samp_gain_ratio` | `ff_27c_3.30v` | 0.97882 | 0.978821 | +1e-06 | 0.00979 | no |
| `samp_gain_err_lsb` | `tt_-40c_2.97v` | 37.4944 | 37.494 | -0.0004 | 0.375 | no |
| `samp_inl_l1_lsb` | `ff_-40c_2.97v` | 0.0562 | 0.0560567 | -0.000143 | 0.001 | no |
| `samp_inl_l2_lsb` | `tt_27c_2.97v` | -0.000493441 | -0.000536173 | -4.27e-05 | 0.001 | no |
| `samp_inl_l3_lsb` | `ff_-40c_3.63v` | 0.01655 | 0.0166275 | +7.75e-05 | 0.001 | no |
| `samp_inl_worst_lsb` | `ff_125c_3.30v` | 0.02605 | 0.0261202 | +7.02e-05 | 0.001 | no |
| `dhold_dc0_lsb` | `tt_125c_3.63v` | 0.1208 | 0.120705 | -9.5e-05 | 0.00121 | no |
| `dres_dc0_lsb` | `ss_-40c_3.63v` | -0.01243 | -0.0124387 | -8.7e-06 | 0.001 | no |
| `dhold_dc1_lsb` | `ss_-40c_3.63v` | 0.3308 | 0.330717 | -8.3e-05 | 0.00331 | no |
| `dres_dc1_lsb` | `ss_-40c_3.30v` | -0.03722 | -0.0372101 | +9.9e-06 | 0.001 | no |
| `dhold_dc2_lsb` | `tt_125c_3.63v` | 1.2014 | 1.20131 | -9e-05 | 0.012 | no |
| `dres_dc2_lsb` | `ss_-40c_3.63v` | -0.12384 | -0.123859 | -1.9e-05 | 0.00124 | no |
| `dres_per_ff_lsb` | `tt_-40c_3.63v` | -0.0013604 | -0.0013606 | -2e-07 | 0.001 | no |

10 of the paired measurements moved beyond tolerance.

