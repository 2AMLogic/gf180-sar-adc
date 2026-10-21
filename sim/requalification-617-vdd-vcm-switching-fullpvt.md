# Re-qualification under open_pdks f6eeac7 — V_DD switching / full-PVT group (issue #617)

Part of #595 / #515. Old records stay untouched (append-only). Pinned PDK:
open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`; submitting host
`klt 0.7.1.dev2379+g28c56ed58269`, `KLT_SIM_BACKEND=batch`.

**Outcome: nothing in this tranche could be re-qualified.** The Spot batch
fleet refused every submit on 2026-10-20 (`batch_concurrency_cap`:
`BATCH_MAX_CONCURRENT_INSTANCES=8` with 10–12 instances already running
fleet-wide, plus `no capacity in any of the 30 pools`). Per host policy no grid
was run on this host, and no error/partial record was minted. No new
measurement record exists, so there is no old-vs-new comparison and no moved
metric.

## Not re-qualified, with reason

| experiment | attempt | reason |
|---|---|---|
| vdd-switching-event (supersedes target `20261007-060000-7965f24`) | `klt sim request_{2v97,3v30,3v63}.json --backend batch --hosts 9`, two full rounds | round 1: 2v97 8/9 points done, 1 `lost_shard` (cap: 12 running); 3v30 4/9 done, 5 `lost_shard` (`no capacity in any of the 30 pools`); 3v63 0/9 (cap: 11 running). round 2: 0/27 (cap: 10 running). A rail with a lost shard is not a complete 9-point grid, so no record was minted from the partial rounds |
| vdd-full-pvt (4 extracted decks + 4 schematic decks, ideal and V_DD-network arms, 27/27/27/9 points per extracted deck) | preflight `PREFLIGHT_ONLY=1` passed (decks hash to their governing records); one 9-point probe (`adc-enob-fft` extracted, `--no-write`) | all three per-supply requests refused with `batch_concurrency_cap` (10 running + 1 requested > 8); no point simulated anywhere. The remaining 15 arm runs were not attempted: they are far heavier than the probe |
| vcm-full-pvt | README check only | the script wraps `run_corners.py` and mints into each target deck's `records/`; the README's ideal-arm controls and citations are the governing records of `adc-inl-dnl`, `adc-power`, `dr0014-sampling`, `adc-enob-fft`, which are themselves old-PDK records not yet re-qualified. Re-running this campaign under `f6eeac7` is only meaningful after those decks are. `git grep c6d73a3` finds no hit in its directory |
| vdd-drive-impedance | none | no records; `gen_vdd_variant.py` is a deck generator only |

## Tooling change deferred

`sim/vdd-switching-event/testbench/make_record.py` has no `--supersedes`
option yet. The file is pinned by the signoff testbench inventory (item
9.analog), so adding the option belongs in the PR that re-runs the experiments
and regenerates signoff. Until then the superseding record's "Supersedes:"
line is set by hand.

## Follow-up

Re-submit once the fleet has headroom (check the cap first), in this order:
vdd-switching-event (3 requests, then mint the record superseding
`20261007-060000-7965f24`), then vdd-full-pvt per deck (`run_full_pvt.sh <tag>`,
superseding the matching old record where one exists), then vcm-full-pvt
after its source decks are re-qualified.
