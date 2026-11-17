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

---

# Re-run (2026-11-17, verified on `feature/issue-617` @ `70b241fb`)

The fleet had headroom this time; the grids went to it with the harness's own
`--wait-for-capacity 600` and no local fallback. Pinned PDK open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, fleet engine ngspice 47, runner
klt 0.9.0 `[match]`, submitting host `klt 0.9.3.dev234+g5ed4e55bffbd`,
`KLT_SIM_BACKEND=batch`. All bytes of the recorded runs are in the artifact
store (DR-0041); each record's Environment section carries the fleet job ids.

## Re-qualified

| experiment | new record(s) | supersedes | old-vs-new |
|---|---|---|---|
| vdd-switching-event | `sim/vdd-switching-event/records/20261117-013556-c98b55a.md` | `20261007-060000-7965f24` | 27/27 PASS both; 7 of 270 result-table cells differ — 6 are last-digit rounding; the one real move is `ss_-40c_2.97v` `i_max` (rail absorption excursion, a diagnostic with no spec row) 2.036 → 3.890 mA. The bounded sanity checks (`dq_event_pc`, `t_eq_ns`, `i_pk_ma`) pass at all 27 points as before; overall stays PASS |
| vdd-full-pvt, dr0014-sampling schematic pair (first measured — #393 ran extracted pairs only and deferred these) | `20261117-014804-70b241f` (ideal) / `20261117-015130-70b241f` (V_DD net) | none — first measured pair of this arm on this deck | 27+27 points; no manifest bound crossed under the network; `compare_vdd.py` bounded rows move ≤ 0.11 Ω against ≥ 556× margins. The ideal arm reproduces the committed #615 schematic citation `20261020-231040-0bf0747` exactly (0 of 1620 cells differ) |
| vdd-full-pvt, adc-inl-dnl schematic pair (first measured) | `20261117-015424-70b241f` / `20261117-015906-70b241f` | none — first measured | 63+63 points; no bound crossed; every bounded INL/DNL measure moves ≤ 0.00024 LSB (≥ 3800× inside its margin). Ideal arm vs the committed #594 schematic record `20261105-065009-758b973`: 5 of 93 grid-summary cells differ, all last-digit |
| vdd-full-pvt, adc-power schematic pair (first measured) | `20261117-020212-70b241f` / `20261117-020537-70b241f` | none — first measured | 27+27 points; no bound crossed; `p_total` moves ≤ 1.07 µW against the 1000 µW bound. Ideal arm vs `20261105-050939-bca53f9`: 4 of 34 summary cells differ, last-digit |
| vdd-full-pvt, adc-enob-fft schematic pair (first measured) | `20261117-020833-70b241f` / `20261117-021247-70b241f` | none — first measured | 9+9 points, compared with `analyze_fft.py` over both arms' store-fetched raw logs: 8 of 9 corners byte-identical; `tt_125c_3.30v` moves SFDR 62.94 → 62.38 dB and ENOB 9.402 → 9.347 bits — still above both ratified bounds (≥ 62 dB, > 9.0), row statuses unchanged (`ss_125c_2.97v` remains the FAIL worst at 8.506 bits / 56.41 dB in both arms). Ideal arm matches the #594 citation's worst figures at printed precision |

No metric left a ratified bound anywhere in this tranche, so no follow-up
decision record is needed from it. The ENOB `tt_125c_3.30v` SFDR move is
flagged, not absorbed: it is the only corner where the V_DD network changes a
bounded figure at all, and it keeps 0.38 dB of margin.

## Not re-qualified, with reason

| experiment | attempt | reason |
|---|---|---|
| vdd-full-pvt extracted pairs, adc-inl-dnl / adc-power / adc-enob-fft (`20261007-044826/044830`, `-072338/072514`, `-072654/072721`) | `run_full_pvt.sh adc-power-extracted` preflight, 2026-11-17 | **refused by the campaign's own preflight gate, not by the fleet**: #837 (PR #873, landed 2026-11-16) regenerated the five extracted decks over the new parasitics record, and no record pins the current bytes (`tb_adc_power_extracted.spice` sha256 `91c95d4c…` ≠ `85fbb272…` pinned by `20260923-102440-904af96`; same for the other two decks). The gate exists precisely to stop an "ideal arm reproduces the citation" claim from running different bytes, and its own remedy — "update the governing record in DECKS" — needs a fresh plain extracted record that only a post-#837 re-take can mint. That re-take is issue #867's scope (block PEX + the five extracted campaigns); re-run these three pairs after it lands, superseding the #393 records above |
| vdd-full-pvt extracted pair, dr0014-sampling | none needed here | already re-qualified by #615: `20261020-231428-0bf0747` supersedes the ideal arm `20261007-071907-800bf53` and `20261020-235636-0bf0747` supersedes the V_DD-network arm `20261007-072143-800bf53` (on the then-current remediated extraction; its own post-#837 re-take is likewise #867's) |
| vcm-full-pvt | none (README check only, as in the #620 section above) | unchanged: its governing records are `adc-inl-dnl`, `adc-power`, `dr0014-sampling`, `adc-enob-fft` records not yet re-qualified post-#837; re-running this campaign stays deferred until those are (#867 then this issue's remaining scope) |
| vdd-drive-impedance | none | unchanged: `gen_vdd_variant.py` is a deck generator, no records; `git grep c6d73a3` still has no hit in its directory. It WAS exercised for real: it generated the eight schematic V_DD-network decks this tranche ran |

## Tooling change (landed in the same PR)

`make_record.py` gained `--supersedes <record-id>` (with run_corners.py's
withholding rule: a run with no `ok` corner supersedes nothing), and signoff
item 9.analog was re-attested over the edit — report
`signoff/reports/20261117-005756-01e5d46f/`, record
`signoff/records/20261117-005756-01e5d46f.md`, no T1 row moved. This retires
the "Tooling change deferred" section above; the superseding
vdd-switching-event record's `Supersedes:` line is set by the tool, not by
hand.

## Follow-up

After #867 mints fresh governing records for the extracted decks, re-run the
three remaining vdd-full-pvt extracted pairs (`run_full_pvt.sh
<tag>-extracted` with `SUPERSEDES=<matching 20261007 record>`) — preflight
will pass once DECKS cites the new records. vcm-full-pvt follows after its
source decks are re-qualified post-#837. Issue #617 stays open for that
remainder; this section closes out items 1, 2 and the schematic half of
item 3 of its revised scope.

