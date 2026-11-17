# Roadmap

A 10-bit SAR ADC on gf180mcu, designed by AI agents on the open-source flow,
whose second job is to expose gaps in `klayout-tools` (`klt`).

Status as of 2026-11-16, `main` @ `6b8375f6`. `#N` is this repository's
tracker; `klayout-tools#N` is the tool's. This file is a map, not evidence: the
verdict of record is [`signoff/README.md`](../signoff/README.md), per-row
performance is [`sim/characterization-summary.md`](../sim/characterization-summary.md),
and the live queue is [`WORK_PLAN.md`](../WORK_PLAN.md).

## Where it stands

Pre-tapeout, not a converged design, no silicon. Signoff record
`20261115-200610-f6a87784` grades `tier: none`, **18 of 22 T1 items met**, one
not applicable (6, digital).

| T1 item | analog (`ADC_BLOCK`) | digital (`sar_ctrl`) |
|---|---|---|
| 1 sources, 2 layout, 4 LVS, 8 report, 9 testbenches, 10 hygiene, 11 power | met | met |
| 3 DRC clean | met | **unmet**: 208 markers on PDK endcap/filltie cells (#641) |
| 5 corner verification | **no evidence**: no `klt sim` envelope cited (#643) | met (#642; no extracted SPEF, ideal clock) |
| 6 Monte Carlo | met on one cited row only (#654) | not applicable (#562) |
| 7 post-layout | met, 117-corner `klt pex` grid (#439) | **no evidence**: no SDF-annotated run (#645) |

Ratified spec rows (DR-0006) that do not pass, from the README status table:

- **ENOB** 8.734 bits against `> 9.0` and **SFDR** 57.96 dB against `>= 62 dB`,
  both extracted, both governed by `ss_-40c_2.97v` on the 27-point grid
  ([record](../sim/adc-enob-fft/records/20261105-125230-b281aa8.md)). The one
  evaluated fix was not adopted
  ([DR-0025](../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md)).
- **Area** 0.128779 mm² against `< 0.1 mm²` (`layout/adc-top/area.json`);
  DR-0024's `< 0.16 mm²` revision is proposed, not ratified.
- **Offset error** has no comparator-inclusive 3σ population (#655); INL/DNL
  pass `< 1 LSB` and miss the `< 0.5 LSB` stretch.

Re-qualification under the re-pinned PDK (open_pdks `f6eeac7`, #513/#515) is
partly done; the per-family accounts are the `sim/requalification-*.md` files
(#595 twice, #596, #609, #616, #617). Separately — not one of those files —
the `sim/sar-logic-timing-gates-ok/` deck re-qualified at 45/45 under the
pinned PDK (PR #773). The T1 tracker #640 still describes record
`20261023-164912` (17/22, 5.digital open), one row behind the table above.

## Now

The previous snapshot's items 2 to 5 are complete on `main`, each closed by a
landed record: #797 — DRC delta adjudicated
([record](../layout/drc/records/20261115-215548-7760b9f1.md)); #798 — LVS and
ERC deltas adjudicated
([LVS](../layout/lvs/records/20261115-021029-784b4d3b.md),
[ERC](../layout/erc/records/20261115-021155-784b4d3b.md)); #799 — power schema
recorded
([record](../layout/power/records/20261115-035520-784b4d3b.md)); #800 —
candidate ranking
([investigation](../sim/adc-enob-fft/investigations/20261114-issue-800-cold-distortion-candidate-ranking.md)).
Item 2 below is the layout work that DRC adjudication filed as follow-ups,
under #652's umbrella. Which of it is dispatchable now is
[`WORK_PLAN.md`](../WORK_PLAN.md), cited rather than enumerated here so it
cannot drift.

1. **Land the live `klt synthesize` + `klt equiv` verification** behind the
   `flow_env.run_klt_json` consolidation (#659, **parked on PR #720**). The
   wrapper de-duplication this issue was filed for is already on `main` via
   merged PRs #661/#663, so "the duplicates are gone" is met; what remains is
   the live run, which is PR #720 on the same branch `feature/issue-659`. Done
   when that run's evidence lands.
2. **Land the four layout fixes the DRC adjudication filed** (#836, #837,
   #838, #839), one per firing rule family: source/drain implants for
   `comp.coverage.1` (#836), CO.1 exact-square contact arrays replacing the
   bars for `contact.width.1` (#837), resistor SAB markers for SB.10/SB.2
   (#838), and the 5 nm manufacturing-grid snap for `*.ongrid.1` (#839).
   Done when each issue's evidence shows the re-drawn geometry passing under
   the 0.8.0 deck.

Also carrying open work: #605 with PR #606. Its live state is
[`WORK_PLAN.md`](../WORK_PLAN.md)'s In Progress section, cited rather than
transcribed here so it cannot drift. #780's PR #788 merged at
2026-11-14T01:38Z (`e0ce4bef`), inside the `main` this snapshot pins; #778
and #779 closed between the pins (Next names what remains of that family).

## Next

- **Bump every `klt` pin and regenerate the evidence** (#652), unblocked now
  that its triage items #797/#798/#799 closed with adjudication records on
  `main` (cited in Now above; the regeneration also carries the `sw_unit`
  re-baseline the DRC record assigns to it). Done when every runner's
  `--check` passes at the new pin and a new signoff record is minted.
- **Declare the statistical row set for item 6** (#654), after #652. Expected
  honest outcome: 6.analog `unmet` with the gaps named.
- **Clear 3.digital** (#641). The newer deck drops the 208 markers and reports
  365 tap-distance ones; `power.tapcell.distance_um: 20` gave a clean `klt drc`
  in a Builder's trial. Needs place-and-route and gate-level LVS at the pinned
  PDK (#754), then re-minted digital pins for items 2, 3, 4 and 11. Check
  whether that re-run is the trigger #328 waits for.
- **SDF-annotated gate-level re-run for 7.digital** (#645), after #486 is
  closed out: its five-corner annotation gate now passes and what remains
  there is a judgement on the model's limits, not code.
- **Remaining gate-level grid** (#777, parent #753 — #778 and #779 closed
  between the pins): needs a batch-fleet window; `-bad` and the five-loop grid
  stay behind #303.
- **Remaining device and ADC-level re-qualification** (#599, #594, #617): #599
  waits on `klayout-tools#4902`; #594's rail-current deck needs its `let` step
  in a form `klt sim` accepts.
- **Cite `klt sim` envelopes as 5.analog** (#643). It will grade
  `check_failed`, not `met`, while ENOB, SFDR and Area fail.
- **Offset-error 3σ population** (#655): gate run passed; waits on DR-0038.

## Later

- **Close ENOB and SFDR.** Which admissible change removes the cold
  acquisition-lag distortion without a spec change? Now item 5 is the input.
- **Area.** Does a further layout reduction reach `< 0.1 mm²`, or is DR-0024
  ratified? Analysis: [economy record](../layout/adc-top/economy/records/20261030-210500-be1c350.md).
- **Standard-cell device flavour.** Does `sar_ctrl` stay on `mcu7t5v0` or
  re-target a 3.3 V library the pinned PDK now ships (#765, PR #771)?
- **Top-level integration** of routed `sar_ctrl` with `ADC_BLOCK`. Waits on the
  device-flavour answer and DR-0042/DR-0043 (reserve placement, proposed).
- **Silicon.** `measurements/` stays empty until there is a die to measure.

## Blocked and waiting

- **Operator decisions:** DR-0033 superseding DR-0029 (#363, PR #413); the
  device-flavour call (#765, PR #771, and #781 behind it); DR-0038 (gates
  #655); DR-0024 (Area); four removal proposals (#748, #769, #774, #776). In
  all, 24 of 45 decision records read `proposed`, per the generated tally in
  [`spec/decision-records/STATUS.md`](../spec/decision-records/STATUS.md) —
  cited rather than counted here so it cannot drift.
- **Batch-fleet capacity:** #777, #617. Grids are never run locally.
- **No runner for place-and-route, STA and extraction at the pinned PDK:**
  #754, and with it the rest of #596.
- **Upstream `klayout-tools`, all open:** `#4902` (derived measurements on
  batch), `#5544` (job timeout assumes serial units; excludes the `-bad` grid),
  `#5531` (no way to list in-flight fleet jobs).
- **Stage D diagnostic** (#303): approved, not launched (receipts unmet).
- **Housekeeping:** #518 has its nightly evidence and awaits closing; #464 is
  a host request, not repo work.

Everything that moves a T1 row is behind one of the waits above. Which work
is dispatchable at any given moment is [`WORK_PLAN.md`](../WORK_PLAN.md),
cited rather than enumerated here so it cannot drift.

## Not planned

- A mux variant or comparator-only fast path (DR-0020); an internal reference
  or clock (DR-0002, DR-0003); an SPI interface (deferred by DR-0005).
- Relaxing a ratified spec row so a result passes.
