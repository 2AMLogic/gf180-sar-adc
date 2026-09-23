# Full-ADC characterization summary — one row per ratified spec line

Issue #174 (T1 item 8, `2AMLogic/gf180-sar-adc#169`'s closing verdict row 8).
This is the single aggregated, current answer to "what is this converter's
measured performance, right now, against the ratified target spec" — every
row of `README.md#target-specification` (DR-0006), its **latest** verified
value, its verdict, and a dated citation to the record that produced it.

**This block is mixed-signal, and so is this document.** The per-spec-row
table below is the **analog partition**'s characterization; the
[digital partition](#digital-partition-sar_ctrl_a--fmax-area-and-power-across-the-corner-set)
(the routed `sar_ctrl_a` SAR-sequencer macro) has its own section further
down carrying what T1 item 8 asks of a digital partition specifically —
Fmax, area and power across the corner set, not just functional pass/fail.
`signoff/gf180-sar-adc.manifest.json` cites this one document **twice**,
once per partition, through two separate generic evidence envelopes under
`signoff/evidence/` (issue #339); each envelope names the section it
asserts, so neither partition's row is graded on the other's evidence.

**This document creates no numbers of its own.** It is a pointer table, not a
re-derivation: every figure below is transcribed from an append-only `sim/`
record or from `spec/testbench-suite-memo.md` / `sim/extracted-delta-summary.md`
/ `sim/issue-17-acceptance-review.md`, and the citation in the "Source" column
is where a reader goes to see the full methodology, the whole PVT grid, and
the raw per-corner data — not just this row's headline number. Where
schematic-level and post-layout (extracted) results both exist, the extracted
result is the one this document reports as governing (the precedent
`sim/extracted-delta-summary.md` §7.1 states and `README.md`'s own Status
table already follows), with the schematic number carried alongside it.

## Freshness

**As of commit `93ddfe3` (2026-09-21).** This is not merely a statement that
the source documents below exist — it is a re-read of each of them against
that exact commit, done for this document. The re-read is the reason the
`signoff/` manifest may cite this file at all: a generic evidence envelope
asserting `status: "pass"` over a document nobody has re-read is a claim
about a date, not about a design (issue #339).

| Source document | Re-read against | What changed since the previous (2026-08-25, `ed74762`) re-read |
|---|---|---|
| `README.md#target-specification` | `93ddfe3` | **Exactly one change to the ratified table since the previous re-read: a new `V_CM` row** (PR #262, DR-0026) — the row this document was missing, added below. Every other target-spec row is byte-unchanged (`git diff ed74762..93ddfe3 -- README.md`); the one other table row that moved is the **Status** table's `Schematics` row (PR #276/#279, the digital partition's RTL → synthesis → P&R), which is not a spec row and is aggregated in the digital section instead |
| `spec/testbench-suite-memo.md` | `93ddfe3` | §12 item 3 rewritten by PR #262: "V_cm is an ideal source" is no longer *unbudgeted* (DR-0026 derives `Z_vcm ≤ 220 Ω` / `C_dec ≥ 40 nF`) and is no longer *assumed conservative* (`sim/vcm-drive-impedance/` measures a real ≈ 0.2 LSB shift at the budget). Every schematic-side number in the table below should be read accordingly — see the new `V_CM` row |
| `sim/extracted-delta-summary.md` | `93ddfe3` | Unchanged since `ed74762` (PR #258, DR-0025). §4.13's clean-tree re-takes remain the governing extracted vintage for all five extracted campaigns |
| `sim/issue-17-acceptance-review.md` | `93ddfe3` | Unchanged since its 2026-08-14 "8 of 8 AC PASS" disposition update — re-verified current, not stale |
| `sim/device-characterization-report.md` | `93ddfe3` | Unchanged since 2026-07-31 — device-level scope, explicitly not full-ADC; this document is the full-ADC companion, not a replacement |
| `design/sar-logic/flow/sar_ctrl/` + `sim/sar-logic-*` | `93ddfe3` | **Entirely new since the previous re-read**: RTL → synthesis → equivalence → P&R → post-route STA for the digital partition, plus seven gate-level SPICE-replay campaign directories (six with committed records; `sim/sar-logic-timing-gates-bad/` holds a testbench and no record yet). Aggregated in the new [digital-partition section](#digital-partition-sar_ctrl_a--fmax-area-and-power-across-the-corner-set) |

### Partial update — 2026-09-23, issue #381 (NOT a new full re-read)

**The full re-read above still stands at `93ddfe3` (2026-09-21); this is a
narrower, declared update on top of it, not a replacement for it.** Issue #381
re-extracted `layout/adc-top/parasitics/` against the post-DR-0035 /
post-DR-0037 geometry and re-ran all five extracted campaigns over the same
PVT grids they already covered. What this pass touched, and only this:

- **The five extracted-campaign rows** (ENOB, SFDR, INL/DNL, `Gain error,
  systematic`, `Input structure`'s post-layout `R_on`, `Power @ 1 MS/s`) now
  quote and cite the new governing records; each also retains the record it
  supersedes. Per-campaign before/after tables:
  [`sim/extracted-delta-summary.md`](extracted-delta-summary.md) §4.14.
- **The `Area` row** now quotes `layout/adc-top/area.json`'s current
  `block_total` (151,827.342 µm²), re-derived at build time, rather than the
  pre-#356 150,536.239 µm².
- **No verdict moves in either direction.** Every row that passed still
  passes; ENOB, SFDR and Area still FAIL, on the same rows and at the same
  worst corners.

**Currency gap this pass declares rather than closes**: PR #387 (DR-0036,
proposed) rewrote `README.md#target-specification`'s **Supply** row after the
`93ddfe3` re-read — it now carries a `≥ 40 nF` external decoupling figure, a
`≤ 3 Ω` source-impedance budget and a not-yet-sized on-die term. This
document's `Supply` row still reads as of `93ddfe3`. Reconciling it is
DR-0036's own work, not #381's, and is filed separately; it is named here so
the next full re-read starts from a known gap rather than rediscovering it.

### Currency defects found by the 2026-09-21 re-read, and their disposition

The 2026-08-25 hand re-read (`sim/t1-checklist-reread-20260825.md` §8) scored
this document PASS with **one named currency defect**. That defect and five
more found by this pass are settled here, so the `pass` the signoff envelope
asserts is a statement about the document's *current* contents rather than
about the date it was last touched:

1. **`Gain error, mismatch` still reported `FAIL` at 2.12σ for a reason this
   document itself falsified** (§8 of the 2026-08-25 re-read; filed as
   **#239**). **Settled before this pass**, by PR #241 and PR #243 — the row
   below reads `PASS as built` at `sigma_to_spec = 3.13` and cites the
   governing post-resize record. Re-verified against `93ddfe3`: the row's
   stated reason and its citation now agree with each other and with
   `README.md`. #239 is closed.
2. **The Freshness banner named `607d6e6` (2026-08-16)** while the table
   below cited records dated 2026-08-25 — the banner was falsified by the
   document's own contents, which is exactly the defect class (1) is.
   **Settled**: re-read and re-stamped against `93ddfe3` above.
3. **No `V_CM` row**, although `README.md#target-specification` grew one on
   2026-08-25 (DR-0026) and this document's stated contract is one row per
   ratified table row. **Settled**: row added below.
4. **The `Clock` row cited a superseded record.**
   `sim/sar-logic-timing/records/20260802-102758-d8a363d.md` carries
   `Supersedes: 20260801-033032-06bad60`, and `06bad60` was what this
   document cited — precisely the drift "How this document is kept in sync"
   below tells a reader to file. **Settled**: re-pointed, with the
   superseded record still named.
5. **The `Resolution` / `Latency` / `Interface` rows cited the pre-DR-0014
   controller's functional record.** `20260801-041242-96c2ea7` is not
   formally superseded (its successor's `Supersedes` chain runs through a
   different record), but it was taken on the DR-0006-era sequencer, and the
   controller this design now builds is DR-0011 + DR-0014's.
   **Settled**: the current controller's record is now the one quoted, with
   the original retained as the first proof.
6. **Three places still described PR #149 as unlanded.** It merged as
   `617de90` on 2026-08-17 — eight days *before* the previous re-read — so
   this document reported an open PR as open for a month after it closed.
   **Settled**, and sharpened: the format gap #149 closed has been replaced
   by a narrower currency gap (that envelope is at the pre-resize `C_u`),
   which is now what the three places say.

Two further things this pass found and **did not** absorb, because they are
outside an aggregation-and-assertion pass and are filed instead: the same
superseded `06bad60` / pre-DR-0014 `96c2ea7` citations also appear in
`spec/testbench-suite-memo.md`'s coverage map, `spec/timing-budget-memo.md`
and `docs/chipalooza/challenge-3-proposal.md` (**#357**), and the ADC-level
decks have not been re-run against a real V_cm network at full PVT, which
DR-0026 itself names as a follow-up (**#358**).

**#358 is closed as of 2026-09-23** and the `V_CM` row below now carries a
measured result rather than that gap: four decks re-run as paired
same-commit arms against a real V_cm network at DR-0026's budget, over their
own governing grids, including the **extracted** netlist the `INL / DNL` row
is actually cited from. **No ratified row moves outside its bound** — and the
governing row's remaining headroom (0.54× the perturbation) is now smaller
than the perturbation itself, which is a materially stronger statement than
the one this list recorded as missing. Two decks named there are still not
re-run (`ENOB`/`SFDR`, and the extracted power netlist); both are wired into
`sim/vcm-full-pvt/run_full_pvt.sh` and the reasons are recorded in
[`sim/vcm-full-pvt/README.md`](vcm-full-pvt/README.md) rather than left
implicit.

**Toolchain provenance of the analog partition's extracted numbers (issue
#189, 2026-08-21)**: every extracted row below
that cites a post-#215 (`…076d545`) or post-#228 (`…bbed59c`) record — i.e.
every extracted row currently marked governing in this table — was measured
against a deck generated from a `layout/toolchain.json` `klt` pin of
`85b8125fb012f6038883ab884490a3caa3d41db3` (superseding `875eac3`, PR #195),
which carries junction area/perimeter (`AS=`/`AD=`/`PS=`/`PD=`) on every
extracted MOS device — a real SPICE-model input, not cosmetic text. Full
accounting of how that pin bump reached every currently-governing extracted
number (and the one isolated, same-geometry delta it produced on its own):
`sim/extracted-delta-summary.md`'s "Toolchain provenance" banner, immediately
before its §1.

**Toolchain provenance of the digital partition's numbers**: `klt 0.4.0`
(`+g74af2bbbb2bd` for the post-route STA runs), OpenROAD
`26Q3-1510-g6cb3f2b704`, yosys `0.69+post`, gf180mcu `gf180mcuD` at
open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` — each response JSON
carries its own `provenance` block, and the digital section below names the
file behind every figure.

**PRs incorporated when this document was first written (2026-08-16),
retained as the record of where two of its rows came from** — not a
statement about what is current:

- **PR #182** (issue #172, T1 item 6): `klt yield`-format statistical evidence
  for the Gain error, mismatch / Offset error / CMRR rows —
  `sim/mc-cdac-mismatch/yield-evidence/`, `sim/comparator-offset-mc/yield-evidence/`.
  This is where the **Gain error, mismatch 2.12σ FAIL** finding came from —
  a real, newly-quantified, non-layout finding. **That finding is now
  superseded**: DR-0019's resize is built, and the row below reads
  `PASS as built` at 3.13σ (the currency defect #239 named, and settled).
- **PR #184** (issue #173, T1 item 7): a genuine `klt pex` run against the
  post-layout comparator — `sim/comparator-pex/`. It fails structurally (a
  DUT-interface mismatch `klt pex` cannot bridge), re-grading item 7 from
  "N/A by construction" to "tried, blocked, filed upstream" — see the Rate /
  comparator-inclusive-extraction row's Notes below.

**Known incompleteness, stated rather than silently absorbed**: the INL/DNL
row's own `klt yield` reformat (**PR #149**) **has landed** — `617de90`,
2026-08-17, `sim/mc-cdac-mismatch/yield-evidence/klt-yield-report.json`,
carrying `dnl_at_256_lsb_*` / `inl_at_256_lsb_*` measurements at N = 20 000
with a seeded negative control. So the *format* gap this document used to
report is closed. What replaces it is a **currency** gap, which is a
different and smaller thing: that envelope was built at the **pre-resize**
`C_u = 17.24 fF` this design no longer draws, so it is superseded evidence,
and **no post-resize `klt yield` envelope of the INL/DNL row exists**. The
INL/DNL figures below are therefore still reported from the post-resize
`sim/adc-inl-dnl/` records directly, and `signoff/`'s item 6 cites the
post-resize `yield-evidence-177/` envelope (the Gain-error-mismatch row)
rather than this one.

## Per-spec-row status

| Spec row (README target) | Target | Latest verified value | Verdict | Source (dated) |
|---|---|---|---|---|
| Resolution | 10 bit | 10 bits resolved (architectural, `sar-logic` decode proof), re-confirmed on the **current** DR-0011 + DR-0014 controller | **PASS** (rung-1 ideal sequencer model, DR-0010; the rung-2 gate-level re-check is in the digital-partition section below and is **not** closed) | [`sim/sar-logic-functional/records/20260802-110241-131989b.md`](sar-logic-functional/records/20260802-110241-131989b.md) (**current controller**, DR-0011 bit-trial switching + DR-0014 two-phase sample / four-leg one-hot; supersedes `20260802-094246-16ec0f1`); [`sim/sar-logic-functional/records/20260801-041242-96c2ea7.md`](sar-logic-functional/records/20260801-041242-96c2ea7.md) (first proof, DR-0006-era sequencer — retained, not superseded via a `Supersedes` chain, but predates DR-0014) |
| Rate (1 MS/s) closure | 1 MS/s (2 MS/s stretch) | Settling τ 1.258 → 1.560 ns; comparator delay 0.863 → 1.257 ns; all three post-layout inputs (`R_WORST_BIT_OHM` 648 Ω, `C_WORST_BIT_F` 2.40712 pF, `T_COMP_REGEN_NS` 1.257 ns) | **PASS — all three inputs post-layout** (2026-08-14, issue #116; closes the sync lag issue #174 fixes in `README.md`) | [`sim/timing-budget-closure/records/20260814-220124-f613571.md`](timing-budget-closure/records/20260814-220124-f613571.md); disposition: [`sim/issue-17-acceptance-review.md`](issue-17-acceptance-review.md) AC7 |
| ENOB @ Nyquist | > 9.0 (> 9.5 stretch) | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #204): schematic 8.5064 bits worst (`ss_125c_2.97v`)** — a regression from the pre-resize 9.163 bits, and now below the > 9.0 target at 2 of 9 grid points (`ss_125c_2.97v` 8.5064, `ss_125c_3.30v` 8.968). **The extracted (governing) side has now been re-taken at the same resize (issue #218): 8.857 bits worst (`tt_125c_3.63v`), below the > 9.0 target at 2 of 9 points (`tt_125c_3.63v` 8.857, `ss_125c_2.97v` 8.969)**, against the 9.103 bits the pre-resize extraction reported — all nine corners degrade, by 0.088–0.878 bits. The extracted grid's worst corner is *not* the schematic's: at `ss_125c_2.97v` the extracted core reads 8.969 against schematic 8.506 **Re-taken again after issue #215's comparator load-resistor fold and supply-corridor re-derivation (issue #224): 8.857 bits worst (`tt_125c_3.63v`) and 60.40 dB worst SFDR — byte-for-byte the same worst-corner figures as the pre-#215 vintage.** Only 2 of 9 corners move at all (`ss_125c_3.63v` +0.026 bits, `tt_125c_2.97v` +0.040 bits, both improving, neither a worst corner). **Re-taken again as a clean-tree re-take (issue #249): 8.857 bits worst (`tt_125c_3.63v`), byte-identical per-sample codes and figures at all nine corners** — the superseded `20260817-215657-076d545` was taken against a dirty working tree and was not citable as a clean-tree result; the design is unchanged, so this re-take confirms rather than moves the figure. **The candidate fix (#211's orthogonal control: the acquisition-leg T-gate widened 2.068×, cited at the end of this row) is evaluated and NOT adopted (issue #249, DR-0025)**: items 1/2/4 of the five deferred measurements cost little, but item 5's `klt`-verified re-layout shows the same width change grows `adc_block` area +17.00 % (150,536.239 → 176,126.8006 µm²), pushing it +76.1 % over the still-ratified `< 0.1 mm²` Area target and +10.1 % over even DR-0024's still-unratified proposed `< 0.16 mm²` relaxation — adopting it would trade this row's FAIL for a worse one on Area. `CDAC_SW_WN`/`CDAC_SW_WP` remain `10u`/`20u` **Re-taken again against the drawn-well-tap re-extraction (issue #381, DR-0035/#356 + DR-0037/#378): 8.855 bits worst (`tt_125c_3.63v`) — the same worst corner, −0.002 bits, still below `> 9.0` at the same 2 of 9 points.** Per-corner moves span −0.082 … +0.078 bits; two corners reproduce every figure exactly (no conversion code flips there). The geometry change does not move this row | **FAIL** (governing extracted result at the current design, and schematic; re-confirmed on a clean tree, issue #249) — regression flagged, not absorbed; #215's layout change does not move this row, and the one measured candidate fix is not adoptable (DR-0025) | [`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](adc-enob-fft/records/20260825-061750-d00911a.md) (extracted, clean-tree, pre-#356 geometry, issue #249, supersedes `20260817-215657-076d545`; `sim/extracted-delta-summary.md` §4.13.2); [`sim/adc-enob-fft/records/20260817-215657-076d545.md`](adc-enob-fft/records/20260817-215657-076d545.md) (extracted, dirty-tree, post-#215 layout, issue #224, supersedes `20260817-180617-c4693f9`); [`sim/adc-enob-fft/records/20260817-180617-c4693f9.md`](adc-enob-fft/records/20260817-180617-c4693f9.md) (extracted, pre-#215, resized `C_u`, issue #218, supersedes `20260807-054805-e8cd2b8`); [`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](adc-enob-fft/records/20260817-080939-afb1b3a.md) (schematic, resized `C_u`, issue #204, supersedes `20260814-193205-f613571`); `sim/extracted-delta-summary.md` §4.12.2/§4.13.2 ; [`sim/adc-enob-fft/records/20260923-111149-904af96.md`](adc-enob-fft/records/20260923-111149-904af96.md) (**extracted, GOVERNING, post-DR-0035/DR-0037 re-extraction**, issue #381, supersedes `20260825-061750-d00911a`; `sim/extracted-delta-summary.md` §4.14.2); **mechanism isolated (issue #211)**: [`sim/dr0019-cu-sweep-findings.md`](dr0019-cu-sweep-findings.md) — the loss tracks the acquisition time constant `R_on·C_arr`, and an orthogonal control at the ratified `C_u` with only the acquisition T-gate widened recovers 9.170 bits worst-corner (schematic, 125 °C subset), above the target at all nine points; **candidate NOT adopted, decision + full synthesis of all five deferred measurements**: [`spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md`](../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md) |
| SFDR @ Nyquist | ≥ 62 dB (≥ 65 stretch) | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #204): schematic 56.41 dB worst (`ss_125c_2.97v`)** — **FAIL by 5.59 dB, widened from the pre-resize 0.67 dB gap** (61.33 → 56.41 dB at the same worst corner; 8 of 9 grid points got worse, one — `ff_125c_3.30v` — improved by +0.43 dB). The **64.38 dB extracted** figure below is now **STALE**: measured against the historical `C_u = 17.24 fF` layout, before #196/#202 physically implemented the resize, and has not been re-taken against the current design. **The switch's own contribution to this row now fails it too** (issue #197): `sim/track-switch-thd/`, whose `R_on`-modulated tracking-lag distortion is *linear* in the array capacitance, loses 4.96–5.77 dB at all 117 points and drops below the ratified 62 dB at **11 of 117** where **0 of 117** did pre-resize (worst single-ended 64.81 → **59.04 dB** at `ss_27c_2.97v`; true-differential 66.04 → **60.09 dB**, below 62 dB at 3 of 117). The measured loss matches the 6.31 dB the `C_load` ratio predicts to within 0.3 dB on the `tg1` branch, which is what makes it a mechanism rather than a coincidence — a datum for #211 **The extracted (governing) side has now been re-taken at the same resize (issue #218): 60.40 dB worst (`ff_125c_3.63v`), missing ≥ 62 dB at 4 of 9 points** (60.40, 60.84, 60.98, 61.09), against the 64.38 dB the pre-resize extraction reported — all nine corners degrade, by 2.89–7.21 dB. This row therefore has a valid governing result again (it had none while the extracted side was pre-resize) **and that result is a FAIL, by 1.60 dB. Re-taken again after issue #215's layout recovery (issue #224): 60.40 dB worst (`ff_125c_3.63v`), the identical figure and corner** — 8 of 9 points delta exactly 0, the remaining 2 improve slightly (`ss_125c_3.63v` +0.96 dB, `tt_125c_2.97v` +0.10 dB), neither a worst corner. **Re-taken again as a clean-tree re-take (issue #249): 60.40 dB worst (`ff_125c_3.63v`), byte-identical per-sample codes and figures at all nine corners** — the superseded `20260817-215657-076d545` was taken against a dirty working tree and was not citable as a clean-tree result; the design is unchanged, so this re-take confirms rather than moves the figure. **The candidate fix (#211's orthogonal control, cited at the end of this row) is evaluated and NOT adopted (issue #249, DR-0025)**: items 1/2/4 of the five deferred measurements cost little, but item 5's `klt`-verified re-layout shows the same width change grows `adc_block` area +17.00 % (150,536.239 → 176,126.8006 µm²), pushing it +76.1 % over the still-ratified `< 0.1 mm²` Area target and +10.1 % over even DR-0024's still-unratified proposed `< 0.16 mm²` relaxation — adopting it would trade this row's FAIL for a worse one on Area. `CDAC_SW_WN`/`CDAC_SW_WP` remain `10u`/`20u` **Re-taken again against the drawn-well-tap re-extraction (issue #381, DR-0035/#356 + DR-0037/#378): 60.41 dB worst, the worst corner shifting from `ff_125c_3.63v` to `ff_125c_2.97v` on a 0.01 dB difference, still missing `>= 62 dB` at the same 4 of 9 points.** Per-corner moves span −0.97 … +0.68 dB. The geometry change does not move this row | **FAIL** (governing extracted result at the current design, and schematic; gap widened, not narrowed; the switch's own share of the row now fails independently; re-confirmed on a clean tree, issue #249) — the extracted side no longer rescues this row, as it did pre-resize; #215's layout change does not move it further, and the one measured candidate fix is not adoptable (DR-0025) | [`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](adc-enob-fft/records/20260825-061750-d00911a.md) (extracted, clean-tree, pre-#356 geometry, issue #249, supersedes `20260817-215657-076d545`; `sim/extracted-delta-summary.md` §4.13.2); [`sim/adc-enob-fft/records/20260817-215657-076d545.md`](adc-enob-fft/records/20260817-215657-076d545.md) (extracted, dirty-tree, post-#215 layout, issue #224, supersedes `20260817-180617-c4693f9`); [`sim/adc-enob-fft/records/20260817-180617-c4693f9.md`](adc-enob-fft/records/20260817-180617-c4693f9.md) (extracted, pre-#215, resized `C_u`, issue #218, supersedes `20260807-054805-e8cd2b8`); [`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](adc-enob-fft/records/20260817-080939-afb1b3a.md) (schematic, resized `C_u`, issue #204, supersedes `20260814-193205-f613571`); [`sim/adc-enob-fft/records/20260814-193205-f613571.md`](adc-enob-fft/records/20260814-193205-f613571.md) (schematic pre-resize baseline); [`sim/track-switch-thd/records/20260817-142956-72d15de.md`](track-switch-thd/records/20260817-142956-72d15de.md) (switch contribution at the resized `C_u`, issue #197, supersedes `20260801-020125-267871b`); `sim/extracted-delta-summary.md` §4.12.2/§4.13.2 (§7.1/§7.3 for the pre-resize baseline, §4.10 for the schematic-only interim reading); `spec/testbench-suite-memo.md` §11.2 item 8b, §11.9.11 ; [`sim/adc-enob-fft/records/20260923-111149-904af96.md`](adc-enob-fft/records/20260923-111149-904af96.md) (**extracted, GOVERNING, post-DR-0035/DR-0037 re-extraction**, issue #381, supersedes `20260825-061750-d00911a`; `sim/extracted-delta-summary.md` §4.14.2); **mechanism isolated (issue #211)**: [`sim/dr0019-cu-sweep-findings.md`](dr0019-cu-sweep-findings.md) — SFDR falls −19.00 dB/decade of `C_u` at the worst corner against the −20 dB/decade an acquisition-RC bow predicts, `V_REF` droop and the `C_arr/(C_arr+C_par)` divider excluded by an orthogonal control; DR-0019's rejected 33.00 fF sizing measures 56.07 dB, so no admissible smaller resize recovers the row; **candidate NOT adopted, decision + full synthesis of all five deferred measurements**: [`spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md`](../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md) |
| INL / DNL | < 1 LSB (< 0.5 stretch) | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #203): nominal PVT (schematic) INL 0.1100 LSB (`inl_t384_lsb`, `cap_ss_125c_2.97v`) / DNL 0.0938 LSB (`dnl_t128_t129_lsb`, `cap_ss_125c_2.97v`)** — essentially unchanged from the pre-resize schematic baseline (worst \|INL\| 0.1036 → 0.1100 LSB, +0.0064; worst \|DNL\| 0.1036 → 0.0938 LSB, −0.0098), both still ~4.5–5.3× inside the < 0.5 LSB stretch target, all 63/63 `cdac`-grid points PASS, nothing moved outside the ratified target. Cited from the **clean-tree** re-take `20260817-131106-abf9c75`; the first re-run of this campaign (`20260817-110133-54c6e96`) was taken against a dirty working tree and so is not citable as a clean-tree result (`sim/harness/README.md`) — it is retained as append-only evidence and superseded, and the clean re-take reproduces it to 5–6 significant digits on a different host and ngspice minor version (worst \|INL\| and worst \|DNL\| identical at the precision reported here). **The extracted (governing) side has now been re-taken at the same resize (issue #218): worst \|INL\| 0.5284 LSB (`inl_t896_lsb`, `ss_125c_2.97v`) and worst \|DNL\| 0.7278 LSB (`dnl_t767_t768_lsb`, same corner), against 0.148 / 0.098 LSB pre-resize** — 27/27 points still PASS the ratified `< 1 LSB` row, but **both now sit outside the `< 0.5 LSB` stretch target**, which the pre-resize extraction cleared by ≈ 3.4×. Flagged, not absorbed: the stretch is a target rather than a ratified bound, so the row's verdict does not flip, and the schematic side moved only 0.1036 → 0.1100 LSB, so this is a post-layout interaction (2.068× array charge through the same drawn in-path resistance), not the resize alone; 3σ mismatch: DNL PASS 5.96σ margin, INL PASS 11.9σ margin at the ratified baseline. **Re-taken again after issue #215's layout recovery (issue #224): worst \|INL\| 0.528287 LSB and worst \|DNL\| 0.727556 LSB, both at the identical corner and transition** — a noise-floor move of +0.03 % / −0.03 % on the pre-#215 figures, no verdict change. **Re-taken again against the drawn-well-tap re-extraction (issue #381, DR-0035/#356 + DR-0037/#378): worst \|INL\| 0.517546 LSB (−2.03 %) and worst \|DNL\| 0.681240 LSB (−6.37 %), both still at `ss_125c_2.97v`, 27/27 PASS** — a sub-percent-to-few-percent improvement, both still inside the ratified `< 1 LSB` row and both still outside the `< 0.5 LSB` stretch, so no verdict moves in either direction (`sim/extracted-delta-summary.md` §4.14.1) | **PASS on the ratified row** (governing extracted re-run at the current design, schematic, and 3σ mismatch) — **stretch target still missed post-layout**, flagged | [`sim/adc-inl-dnl/records/20260923-095400-904af96.md`](adc-inl-dnl/records/20260923-095400-904af96.md) (**extracted, GOVERNING, post-DR-0035/DR-0037 re-extraction**, issue #381, supersedes `20260817-214114-076d545`; `sim/extracted-delta-summary.md` §4.14.1); [`sim/adc-inl-dnl/records/20260817-214114-076d545.md`](adc-inl-dnl/records/20260817-214114-076d545.md) (extracted, pre-#356 geometry, post-#215 layout, issue #224, supersedes `20260817-162837-3a9afd2`; `sim/extracted-delta-summary.md` §4.13.1); [`sim/adc-inl-dnl/records/20260817-131106-abf9c75.md`](adc-inl-dnl/records/20260817-131106-abf9c75.md) (schematic, resized `C_u`, issue #203, **clean tree**, supersedes `20260817-110133-54c6e96`); [`sim/adc-inl-dnl/records/20260817-110133-54c6e96.md`](adc-inl-dnl/records/20260817-110133-54c6e96.md) (same campaign, **dirty tree — not citable**, superseded, supersedes `20260805-220405-bff6eaf`); [`sim/adc-inl-dnl/records/20260817-162837-3a9afd2.md`](adc-inl-dnl/records/20260817-162837-3a9afd2.md) (extracted, pre-#215, resized `C_u`, 27-point `tt`/`ss`/`ff` grid, issue #218, supersedes `20260807-081223-6bd9d80`; `sim/extracted-delta-summary.md` §4.12.1); [`sim/mc-cdac-mismatch/records/20260801-093800-c033611.md`](mc-cdac-mismatch/records/20260801-093800-c033611.md) (3σ mismatch); `klt yield` reformat of this row **landed** as PR #149 (`617de90`, [`sim/mc-cdac-mismatch/yield-evidence/klt-yield-report.json`](mc-cdac-mismatch/yield-evidence/klt-yield-report.json)) but is at the **pre-resize** `C_u = 17.24 fF`, so it is superseded and is *not* the source of the figures in this row |
| Offset error | ≤ 2 LSB, untrimmed | Comparator-only (schematic-level, not `ADC_BLOCK`-inclusive) 3σ-mismatch: worst-corner σ 0.398789 LSB, `cpk` 1.66, `sigma_to_spec` 4.99σ, zero samples outside limits at N = 150 (`klt yield` `status: fail` is a **sample-size artifact** — N = 150 cannot support a 3σ/99.73% claim at 95% CI; 1365 samples would). Deterministic (non-statistical) extracted-core systematic offset: −0.597…−4.357 mV across the 45-point grid, well inside the 12.89 mV (2 LSB) bound | **Not measured as a comparator-inclusive (`ADC_BLOCK`) 3σ statistical population** (issue #89 Scope item 2's remaining work); everything measured so far clears its bound with wide margin | [`sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md`](comparator-offset-mc/records/20260816-050504-66a0e2e.md) (`klt yield`, issue #172, clean-tree 45/45); [`sim/comparator-regeneration/records/20260814-215626-f613571.md`](comparator-regeneration/records/20260814-215626-f613571.md) (deterministic extracted-core offset, issue #116) |
| Gain error, mismatch | ≤ 0.5 LSB, untrimmed, excluding V_REF error | **As built (`C_u = 35.6528 fF`, the resize physically implemented by issue #196/PR #202): `sigma_to_spec = 3.13`, `klt yield` `status: pass`**, N = 20 000, negative control at 3× `σ_u` correctly detected, DNL/INL re-confirmed to still pass at this `σ_u`. This is a nominal-PVT mismatch quantity, not a corner sweep (`spec/testbench-suite-memo.md` §5.3/§6 "Subset-corner justification"), so it needs no PVT re-verification beyond the resize itself — it is governing at the current design. **Superseded pre-resize history**: at the historical `C_u = 17.24 fF` this design no longer draws, 2.12σ was measured against the ratified 3σ condition — 0.708 LSB at 3σ, `klt yield` `status: fail` (genuine, not a sample-size artifact: N = 20 000, negative control at 3× `σ_u` correctly detected) | **PASS as built** — the resize (issue #196/PR #202) closes the gap the pre-resize measurement reported; no spec value relaxed, no testbench retuned | [`sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`](mc-cdac-mismatch/records/20260816-125421-737d16e.md) (issue #177, **governing, as built**; `sim/mc-cdac-mismatch/yield-evidence-177/klt-yield-report.json`); [`sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`](mc-cdac-mismatch/records/20260816-044942-56fbe50.md) (issue #172, pre-resize `C_u = 17.24 fF`, **superseded**); `spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`; `spec/testbench-suite-memo.md` §12 item 8c |
| Gain error, systematic | ≤ 0.5 LSB, untrimmed, excluding V_REF error | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #197): schematic 0.0021–0.0039 LSB** (was 0.0045–0.0088 LSB pre-resize) — the row *improves* 2.26×, to ~127× inside the bound, because `C_par` does not scale with `C_u` while `C_arr` does. **The extracted (governing) side has now been re-taken at the same resize (issue #218): 0.00013–0.00048 LSB**, itself a −70.7 % improvement on the 0.00046–0.0016 LSB the pre-resize extraction reported, i.e. **~1047× inside the bound** (was ~307×). Both sides move the same way, for the same reason: `C_par` does not scale with `C_u`, so the injected charge is diluted into a 2.068× larger array. **Re-taken again after issue #215's layout recovery (issue #224): 0.0004845 LSB worst (`ff_-40c_3.63v`)**, a noise-floor +1.5 % move on the pre-#215 figure, **~1032× inside the bound** (was ~1047×) — the DR-0014 sampling mechanism lives entirely in the CDAC array and local drivers, which #215 did not touch. **Double-checked against the #238/#249 acquisition-leg-widening candidate (evaluated and NOT adopted, DR-0025)**: item 1 of that investigation's five deferred measurements ([`sim/dr0014-sampling/records/20260825-015032-446a3c4.md`](dr0014-sampling/records/20260825-015032-446a3c4.md)) found this row's own risk terms move by noise-floor amounts even at the candidate's 2.068× width (`samp_inl_worst_lsb` 0.30895 → 0.30915 LSB), so this row was never actually at material risk from that candidate — moot now that it is not adopted, since the ratified design (`CDAC_SW_WN`/`CDAC_SW_WP` = `10u`/`20u`) is unchanged. **Re-taken again against the drawn-well-tap re-extraction (issue #381, DR-0035/#356 + DR-0037/#378): 0.000981002 LSB worst (`ff_-40c_3.63v`), ~510× inside the bound** (was ~1032×) — the quantity doubles, off a floor a thousand times below its bound, because the sampling T-gates' bodies now sit on real drawn supplies instead of floating `Nwell` islands, so their junction charge is modelled where it previously was not. 27/27 PASS; the row stays deeply inside its bound at every corner (`sim/extracted-delta-summary.md` §4.14.4) | **PASS** (governing extracted re-run at the current design, and schematic; wider margin than before the DR-0019 resize on both sides) | [`sim/dr0014-sampling/records/20260923-104443-904af96.md`](dr0014-sampling/records/20260923-104443-904af96.md) (**extracted, GOVERNING, post-DR-0035/DR-0037 re-extraction**, issue #381, supersedes `20260817-204729-076d545`; `sim/extracted-delta-summary.md` §4.14.4); [`sim/dr0014-sampling/records/20260817-204729-076d545.md`](dr0014-sampling/records/20260817-204729-076d545.md) (extracted, pre-#356 geometry, post-#215 layout, issue #224, supersedes `20260817-172040-5c0f0cc`; `sim/extracted-delta-summary.md` §4.13.4); [`sim/dr0014-sampling/records/20260817-172040-5c0f0cc.md`](dr0014-sampling/records/20260817-172040-5c0f0cc.md) (extracted, pre-#215, resized `C_u`, issue #218, supersedes `20260807-091733-434dc37`); [`sim/dr0014-sampling/records/20260817-134517-cde979d.md`](dr0014-sampling/records/20260817-134517-cde979d.md) (schematic, resized `C_u`, issue #197, supersedes `20260802-141402-1224e11`); `spec/testbench-suite-memo.md` §11.9.6; `sim/extracted-delta-summary.md` §4.9/§4.12.4 |
| CMRR (differential) | ≥ 60 dB (≥ 65 stretch) | Worst-corner-of-45 (`ss_-40c_3.63v`), clean-tree re-run: systematic Δoffset over ±50 mV CM implies **118.2 dB**; 3σ-mismatch Δoffset implies **85.6 dB**. Both clear ≥ 60 dB by ≥ 25.6 dB. Direct ±100 mV measurement not performed — linear extrapolation from the ±50 mV band, stated as such | **PASS**, wide margin | [`sim/comparator-offset-mc/records/20260816-050001-d002e66.md`](comparator-offset-mc/records/20260816-050001-d002e66.md) + [`20260816-050504-66a0e2e.md`](comparator-offset-mc/records/20260816-050504-66a0e2e.md) (issue #172, 2026-08-16 — corrects the prior 99.0/117.5 dB citation, which never reached the true worst corner); `spec/testbench-suite-memo.md` §10 |
| Input (drive contract) | External driver, R_source/C_pin budget | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, 18.254 pF array, issue #197): full 117-point PVT grid at the DR-0013 network, sampling-switch gain-error contribution +0.082…+0.370 LSB** (worst `ff_125c_3.63v`, `gain_px500_lsb`), *improved* from the pre-resize −0.293…+0.421 LSB: every charge-injection term is `Q_inj/C_hold` and the resize took `C_hold` ×2.068, so pedestals, gain terms and nonlinear residuals all land at ×0.49–0.52. **Flagged, not absorbed**: the one quantity that moves the other way is acquisition settling at the 100 pF/250 Ω drive point (`acqerr_px250_lsb` 0.0021 → **0.0103 LSB** worst, ×5.0) — still ~49× inside the 0.5 LSB stretch, but it scales *with* the array and would grow again on a further resize. This deck carries no `checks` block, so its harness PASS means 117 points simulated, not that the row passes; the verdict here is stated against the ratified row | **PASS** (schematic, current design; wider margin than before the resize) | [`sim/track-switch-sampling/records/20260817-142951-72d15de.md`](track-switch-sampling/records/20260817-142951-72d15de.md) (resized `C_u`, issue #197, supersedes `20260802-141402-1224e11`); [`sim/track-switch-sampling/records/20260802-141402-1224e11.md`](track-switch-sampling/records/20260802-141402-1224e11.md) (pre-resize baseline); `spec/testbench-suite-memo.md` §11.9.12 |
| Input structure (C_in, R_on, T/H BW) | C_in **18.254 pF/side** (512 · C_u at DR-0019's resized `C_u = 35.6528 fF`, per `README.md#target-specification`; was 8.827 pF pre-resize); R_on 21.3–60.0 Ω (array); T/H BW ≥ 5.3 MHz | Schematic R_on (drawn `adc_tgate` leaf) 570.436 Ω (`ss_125c_2.97v`); extracted (in-path) **647.818 Ω**, +13.6 % — **re-taken against the post-#202 extraction (issue #218) and an exact null**: `adc_tgate.para.spice` is byte-identical across the two extraction vintages (DR-0019 resizes the CDAC unit cap only, not the switch leaf) and every one of 45 corners × 24 measurements reproduces, max per-corner delta 0 on 21 of 24 and 0.001 Ω on the rest. **Re-taken again after issue #215's layout recovery (issue #224): also an exact null** — `adc_tgate.para.spice` byte-identical to the pre-#215 vintage too (#215 touches the comparator load resistors and supply corridors, not the CDAC's fourth-leg switch cell), `ron_t_max`/`ron_t_min`/`ron_t_flatness` all delta 0. **Re-taken again against the drawn-well-tap re-extraction (issue #381, DR-0035/#356 + DR-0037/#378): still an exact null, and this time the leaf netlist DID change** — DR-0035 drew a tap in `adc_tgate`'s own `Nwell`, so the cell gained a `vdd` pin (5 -> 6), a parasitic R (6 -> 7) and more than doubled its ΣR (302.798 -> 759.5911 Ω), yet `ron_t_max`/`ron_t_min`/`ron_t_flatness` still delta **exactly 0** at their worst corners. The added resistance is in the well-tap path, not the switch's signal path, so the measured on-resistance cannot see it (`sim/extracted-delta-summary.md` §4.14.5) | **PASS**, both sides | [`sim/device-switch-ron/records/20260923-102440-904af96.md`](device-switch-ron/records/20260923-102440-904af96.md) (**extracted, GOVERNING, post-DR-0035/DR-0037 re-extraction**, issue #381, supersedes `20260817-204715-076d545`; same pre-existing `ron_t_max` supply-axis sensitivity witness, bit-identical at 9.71502 %; `sim/extracted-delta-summary.md` §4.14.5); [`sim/device-switch-ron/records/20260817-204715-076d545.md`](device-switch-ron/records/20260817-204715-076d545.md) (extracted, pre-#356 geometry, post-#215 layout, issue #224, supersedes `20260817-172213-5c0f0cc`; the record's own overall verdict is FAIL for the same pre-existing deck sensitivity witness as its predecessors — `ron_t_max` supply-axis spread 9.715 % vs a 10 % floor — not a spec check, `sim/extracted-delta-summary.md` §4.13.5); [`sim/device-switch-ron/records/20260817-172213-5c0f0cc.md`](device-switch-ron/records/20260817-172213-5c0f0cc.md) (extracted, pre-#215, post-resize extraction vintage, issue #218, supersedes `20260814-191138-f613571`); [`sim/dr0014-sampling/records/20260817-134517-cde979d.md`](dr0014-sampling/records/20260817-134517-cde979d.md) (array-path `R_on` re-measured at the resized `C_u`, issue #197: **21.329–60.022 Ω, bit-identical** to the pre-resize record at all 27 points — `spec/testbench-suite-memo.md` §11.9.6); `sim/extracted-delta-summary.md` §4.8 |
| Reference (Z_ref, C_dec) | V_REF = 3.3 V ext.; ≥ 40 nF decoupling; Z_ref ≤ 240 Ω | Bit-cycle settling **PASS at all 117 PVT points, re-run at the DR-0019-resized `C_u = 35.6528 fF`** (issue #197). The gating budget check `err_1msps_*` — top-plate settling error 62.5 ns after the bit trial, bound ±1.6113 mV (0.5 LSB) — is **unchanged at 0 mV** on the whole grid, i.e. the 2.068× array-capacitance increase costs this row nothing measurable. The 1.5 ns in-transient anchor does move: worst-corner (`ss_125c_2.97v`) residual lag rises 0.738 → 0.863 of the step (w=256) and the `lag_ord_256_64` ordering margin narrows 0.242 → 0.148 against its ≥ 0.05 floor (4.85× → 2.96×) — **still PASS, flagged as a margin trend, not absorbed**. Schematic; not re-taken post-layout — this row is off the extracted `ADC_TOP` boundary, so it has no extracted counterpart to go stale | **PASS** (schematic-level, at the resized `C_u`) | [`sim/cdac-bit-settling/records/20260817-121555-227c770.md`](cdac-bit-settling/records/20260817-121555-227c770.md) (issue #197, re-run at the resized `C_u`; supersedes [`20260731-231537-1ee5578`](cdac-bit-settling/records/20260731-231537-1ee5578.md), the pre-resize baseline) |
| V_CM (Z_vcm, C_dec) | V_cm = V_REF/2 = 1.65 V ext.; ≥ 40 nF decoupling; Z_vcm ≤ 220 Ω ([DR-0026](../spec/decision-records/DR-0026-vcm-drive-source.md), **proposed — not yet operator-ratified**) | **The budget is derived; the converter's sensitivity to a real V_cm network at that budget is now measured against the ratified rows themselves, at full PVT, on the governing netlists (issue #358).** Replacing the ideal, zero-impedance V_cm source every other ADC-level deck in this table uses with an R‖L + C_dec network at DR-0026's budget (Z_vcm = 220 Ω, C_dec = 40 nF, modelled exactly the way these decks already model V_REF, DR-0002) was run as **paired same-commit arms** — each deck taken twice, once with its ideal source and once with the network, so the difference carries the network and nothing else. Eight arms, every point PASS, every arm clean-tree; each ideal control arm reproduces the committed citation it controls for (extracted INL/DNL 0.528287 / 0.727556 LSB; schematic 0.1100 / 0.0938 LSB; Power 207.884 µW — same numbers, transitions and corners this table already publishes). **On the governing extracted netlist, worst INL moves 0.5283 → 0.6651 LSB and worst DNL 0.7276 → 0.7874 LSB**; the largest paired move is **0.6163 LSB** (`dnl_t1_t2_lsb`, `ss_27c_2.97v`), leaving 0.3326 LSB of headroom — **0.54× the move**, i.e. the budget consumes 65 % of the margin that row had. Points outside the < 0.5 LSB **stretch** target go from **1 of 27 to 20 of 27**. Schematic side: worst INL 0.1100 → 0.4834 LSB, worst DNL 0.0938 → 0.4856 LSB (63/63 points). Power: worst p_total 207.884 → 223.961 µW, margin 4.81× → 4.47× against the 1 mW target. `sim/dr0014-sampling/` is **insensitive** by more than three orders of magnitude (`samp_gain_err_lsb` 12.7674 → 12.7676 LSB), which is the mechanism DR-0026 derives showing up as data: that deck holds V_cm through one sampling event, while the converter deck releases the array onto V_cm twice per conversion. **The ≈ 0.2 LSB the exploratory sweep published is reproduced exactly at its own point** (`tt_27c_3.30v`: `gain_err_lsb` −2.00532 → −2.20527, `inl_t256_lsb` −0.01342 → −0.28053) and understates the effect ≈ 3× because of the transitions it quoted and its capacitor-only process axis — **not** because it held temperature and supply fixed (the worst move varies only 0.3765–0.4669 LSB across the whole 63-point grid). ENOB/SFDR and the extracted power deck were **not** re-run (both wired into `sim/vcm-full-pvt/run_full_pvt.sh`); see that README's findings for the margin arithmetic that deferred them | **PASS — no ratified row moves outside its bound under a real V_cm network meeting DR-0026's budget, at full PVT, on either the schematic or the governing extracted netlist.** This is now a measured result against the ratified rows, not a stated gap: the ideal-source assumption is **not conservative**, and the price is quantified — 65 % of the governing INL/DNL row's margin, with the remaining headroom (0.54×) smaller than the perturbation itself. **Flagged, not absorbed**: no bound, target or manifest was changed by this campaign. DR-0026 is still *proposed*, pending operator ratification, and the sign-off question it now carries is whether 220 Ω is the right ceiling given how much of that margin it spends | **Full-PVT paired campaign (issue #358)**: [`sim/adc-inl-dnl/records/20260923-095803-836a876.md`](adc-inl-dnl/records/20260923-095803-836a876.md) (**extracted, governing** — ideal-V_cm control) and [`20260923-100947-836a876.md`](adc-inl-dnl/records/20260923-100947-836a876.md) (extracted, V_cm network at budget); [`20260923-072117-664c8dc.md`](adc-inl-dnl/records/20260923-072117-664c8dc.md) / [`20260923-071835-664c8dc.md`](adc-inl-dnl/records/20260923-071835-664c8dc.md) (schematic, 63 pt, the pair); [`sim/adc-power/records/20260923-112459-836a876.md`](adc-power/records/20260923-112459-836a876.md) / [`20260923-114021-836a876.md`](adc-power/records/20260923-114021-836a876.md) (Power, the pair); [`sim/dr0014-sampling/records/20260923-085243-664c8dc.md`](dr0014-sampling/records/20260923-085243-664c8dc.md) / [`20260923-092849-664c8dc.md`](dr0014-sampling/records/20260923-092849-664c8dc.md) (sampling, the pair); [`sim/vcm-full-pvt/README.md`](vcm-full-pvt/README.md) (findings, method, and what was not run). **Prior exploratory sweep (issue #260, superseded as the citation for this row but retained):** [`sim/vcm-drive-impedance/records/20260825-162620-e09a2d0.md`](vcm-drive-impedance/records/20260825-162620-e09a2d0.md) (ideal, Z_vcm = 0); [`20260825-163251-cb36f0a.md`](vcm-drive-impedance/records/20260825-163251-cb36f0a.md) (at budget); [`20260825-163508-64203b5.md`](vcm-drive-impedance/records/20260825-163508-64203b5.md) (5× beyond); [`DR-0026`](../spec/decision-records/DR-0026-vcm-drive-source.md); `spec/testbench-suite-memo.md` §12 item 3 |
| Clock (M = 16, jitter) | 16 MHz @ 1 MS/s; jitter ≤ 250 ps rms (analytic, DR-0003) | 16-phase conversion completes deterministically | **PASS** on the sequencing claim; the **jitter** half is an analytic DR-0003 budget, not measured against a real clock source — stated, not folded into the PASS | [`sim/sar-logic-timing/records/20260802-102758-d8a363d.md`](sar-logic-timing/records/20260802-102758-d8a363d.md) (**current**; `Supersedes: 20260801-033032-06bad60`); [`20260801-033032-06bad60.md`](sar-logic-timing/records/20260801-033032-06bad60.md) (**superseded**, retained append-only) |
| Supply (±10 %) | 2.97–3.63 V | Spanned by the supply axis of every PVT sweep cited above | **PASS** (no dedicated record — it is the corner axis every other row already sweeps) | every record above |
| Latency / conversion timing | 1 conversion, M = 16 clocks = 1 µs @ 1 MS/s | Deterministic, as above | **PASS** (rung-1; the rung-2 gate-level re-check of this same row is open — digital-partition section below) | `sar-logic-functional` `20260802-110241-131989b` + `sar-logic-timing` `20260802-102758-d8a363d`, both cited in full in the Resolution and Clock rows above |
| Power @ 1 MS/s | < 1 mW (< 500 µW stretch) | **Schematic, DR-0019-resized `C_u = 35.6528 fF` (issue #205): 207.9 µW worst (`ff_-40c_3.63v`), +13.4 % vs. the pre-resize 183.3 µW** (worst-of-grid deltas per block, each at its own worst point: comparator −3.6 %, CDAC switch+driver essentially flat at −0.09 %, DR-0014 top-plate V_cm switch essentially flat at +0.26 %, V_REF +92.2 %, V_cm bias +38.9 %); **extracted (in-path, governing), re-taken at the same resize (issue #218): 246.5 µW worst (`ff_27c_3.63v`), +11.6 % on the 220.9 µW the pre-resize extraction reported and +18.6 % on the post-resize schematic number** — the growth lands on the two array-facing rails (`p_ref` +89.9 %, `p_cdac` +20.7 %) while the comparator term falls 16.6 %, the same decomposition consistency check the schematic side passes. The one-corner (`tt_125c_3.63v`) 2× comparator-current excursion does **not** reappear in this vintage, consistent with its diagnosis as a non-reproducible marginal-decision artefact rather than a corner/layout property. **Re-taken again after issue #215's comparator load-resistor fold and supply-corridor re-derivation (issue #224): 231.8 µW worst (`ff_27c_3.63v`, same corner), −6.0 % on the pre-#215 246.5 µW** — the one campaign where the layout change's effect is larger than `adc_top`'s aggregate −0.03 %/−0.21 % ΣR/ΣC move would suggest, because the comparator load-resistor fold changed a resistor the comparator's own dynamic switching current runs through directly (`p_cmp_f050_uw` −4.2 %); margins *widen* to 2.16× against the 500 µW stretch and 4.31× against the 1 mW primary target. **Re-taken again against the drawn-well-tap re-extraction (issue #381, DR-0035/#356 + DR-0037/#378): 218.6 µW worst (`ff_125c_3.63v`), −5.7 % on the pre-#356 231.8 µW, 27/27 PASS** — and that −5.7 % is not a broad improvement but the disappearance of one local comparator-current excursion the superseded record carried at `ff_27c_3.63v` (`p_cmp_f050_uw` 129.297 -> 114.715 µW, against ~111 µW at every other corner), the third time that class of excursion has failed to reproduce (`sim/extracted-delta-summary.md` §4.14.3). Margins widen to 2.29× against the 500 µW stretch and 4.57× against the 1 mW primary target | **PASS** (governing extracted result at the current design), 2.29× margin against the 500 µW stretch target and 4.57× against the 1 mW primary target; excursion tracked open (#107), not absorbed | [`sim/adc-power/records/20260923-102440-904af96.md`](adc-power/records/20260923-102440-904af96.md) (**extracted, GOVERNING, post-DR-0035/DR-0037 re-extraction**, issue #381, supersedes `20260817-211252-076d545`; `sim/extracted-delta-summary.md` §4.14.3); [`sim/adc-power/records/20260817-211252-076d545.md`](adc-power/records/20260817-211252-076d545.md) (extracted, pre-#356 geometry, post-#215 layout, issue #224, supersedes `20260817-174602-71b6844`; `sim/extracted-delta-summary.md` §4.13.3); [`sim/adc-power/records/20260817-174602-71b6844.md`](adc-power/records/20260817-174602-71b6844.md) (extracted, pre-#215, resized `C_u`, issue #218, supersedes `20260807-084749-290d003`); [`sim/adc-power/records/20260826-085142-155595d.md`](adc-power/records/20260826-085142-155595d.md) (**schematic, current** — clean-tree re-run through `sim/characterize.sh` after issue #266 restored that script's missing `--corners tt ss ff` MOS-corner override on the schematic-baseline branch; reads **207.884 µW** at the same `ff_-40c_3.63v` corner, i.e. it **reproduces** the schematic figure quoted here rather than moving it, and confirms DR-0018's 2 % process-axis floor is correct as written); [`sim/adc-power/records/20260817-081223-afb1b3a.md`](adc-power/records/20260817-081223-afb1b3a.md) (schematic, DR-0019 resized-`C_u` re-take, issue #205, supersedes [`20260802-141402-1224e11.md`](adc-power/records/20260802-141402-1224e11.md)); `sim/extracted-delta-summary.md` §4.12.3 (§4.7/§4.10/§4.11.1 for the pre-resize campaign), tracking issue **#107** |
| Area | < 0.1 mm² | **151,827.342 µm² = 0.151827 mm² (current, as-built — `layout/adc-top/area.json` `block_total`, re-derived at issue #381)** — 152 % of the ratified `< 0.1 mm²` budget, after the CDAC MiM stack legalization (#70), issue #118's comparator growth, the DR-0019 unit-cap resize, issue #215's corridor/comparator-bbox recovery (−29,910 µm², −16.57 %, off the resize's own 0.18045 mm²), and **DR-0035's drawn well taps and tie straps (#356, +1,291.103 µm², +0.86 % off the previous 150,536.239 µm²)**; DR-0037's Metal2 strap move (#378) widens two comparator supply columns but leaves `block_total` unchanged. Superseded intermediate figures (0.12100 mm² pre-#118, 0.15446 mm² pre-resize, 0.18045 mm² pre-#215, 0.150536 mm² pre-#356) are no longer current. **Double-checked against the #238/#249 acquisition-leg-widening candidate**: this figure is unaffected because that candidate is evaluated and NOT adopted (DR-0025) — its own item-5 measurement ([`layout/adc-top/candidates/records/20260825-030447-4e220d1.md`](../layout/adc-top/candidates/records/20260825-030447-4e220d1.md)) is precisely why: at the candidate width `block_total` would grow to 176,126.8006 µm² (+17.00 %), +76.1 % over this row's still-ratified `< 0.1 mm²` target and +10.1 % over even the `< 0.16 mm²` figure proposed below, which is exactly the regression that ruled the candidate out | **FAIL against the ratified `< 0.1 mm²` budget**; a `< 0.16 mm²` revision bounding the current as-built figure is proposed for operator ratification, superseding DR-0017's own stale (and never-ratified) `< 0.13 mm²` proposal — not yet ratified | [`spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md`](../spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md) (supersedes [`DR-0017`](../spec/decision-records/DR-0017-adc-top-area-budget-overrun.md)); `layout/adc-top/area.json`; `layout/adc-top/README.md`; candidate NOT adopted: [`spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md`](../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md) |
| Interface | Parallel register in scope; SPI deferred | Parallel output register verified functional on the current DR-0011 + DR-0014 controller | **PASS** (SPI explicitly out of scope, DR-0005; rung-1 — the rung-2 gate-level re-check is open, digital-partition section below) | [`sim/sar-logic-functional/records/20260802-110241-131989b.md`](sar-logic-functional/records/20260802-110241-131989b.md) (**current controller**); [`20260801-041242-96c2ea7.md`](sar-logic-functional/records/20260801-041242-96c2ea7.md) (first proof, pre-DR-0014) |

## What is not yet measured, stated rather than silently dropped

- **Comparator-inclusive (`ADC_BLOCK`) statistical Monte Carlo** — the
  ratified `Offset ≤ 2 LSB` row's own 3σ population through the extracted
  core. `ADC_BLOCK` converts (issue #118) and its regeneration-margin
  campaign has run (issue #116), but the statistical offset population has
  not — issue #89 Scope item 2's remaining half.
- **INL/DNL's own `klt yield` envelope at the *built* `C_u`** — PR #149
  landed the envelope (`617de90`, 2026-08-17), but at the pre-resize
  `C_u = 17.24 fF`. No `klt yield` reformat of the INL/DNL row exists at
  DR-0019's built `C_u = 35.6528 fF`. The underlying measurement and verdict
  (PASS on the ratified row) are not in question — they come from
  `sim/adc-inl-dnl/`'s own post-resize records — only the machine-checkable
  envelope is stale, which is why `signoff/` cites the Gain-error-mismatch
  row's post-resize envelope for item 6 instead.
- **`klt pex` (T1 item 7)** — tried directly against the post-layout
  comparator and found structurally blocked (a DUT-interface pin-count
  mismatch `klt pex`'s single-`.include` swap mechanism cannot bridge, filed
  generically as [`klayout-tools#1030`](https://github.com/2AMLogic/klayout-tools/issues/1030)).
  This repo's own hand-built extracted-core wiring (`gen_extracted_core_tb.py`
  et al.) remains the operative post-layout methodology for every row above
  that cites an "extracted" figure; `klt pex` is not a gap in *this*
  document's numbers, only in tooling this repo would rather have used.
  [`sim/comparator-pex/records/20260815-230715-56fbe50.md`](comparator-pex/records/20260815-230715-56fbe50.md)
- **The Gain error, mismatch resizing decision** — issue #177 /
  `spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`
  make and verify the sizing decision that closes the 2.12σ-vs-3σ gap the
  pre-resize measurement reported as FAIL (now the governing **PASS**,
  `sigma_to_spec = 3.13` at the resized `σ_u`,
  `sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`; superseded —
  see the Gain error, mismatch row above); per CLAUDE.md, no spec value is
  relaxed to close it. **Physically implementing the
  resize** — updating `design/adc-top/gen_adc_top.py` / `layout/adc-top/`'s
  unit-cap constants — is **DONE** (issue #196, merged PR #202).
  **Re-running the full transistor-level PVT verification suite at the new
  `C_u`** is issue #190/#197's decomposed follow-up. It is now **complete at
  the schematic level** — every campaign whose recorded result depends on
  `C_u` has been re-run and recorded (the eight-item list below); the
  **extracted** side is untouched and is issue #218. The
  schematic-level ENOB/FFT + SFDR slice (issue #204)
  surfaces a **new, unbudgeted regression** — worst schematic ENOB drops
  from 9.163 to 8.5064 bits (now FAILING the > 9.0 target at 2 of 9 grid
  points) and the pre-existing SFDR FAIL widens from a 0.67 dB to a 5.59 dB
  gap (see the ENOB @ Nyquist / SFDR @ Nyquist rows above). This is
  reported, not fixed, here — DR-0019's own sizing decision is not
  re-litigated by this document, but the dynamic-performance cost of that
  decision was not previously measured and is now on the record.
  **Per-campaign status of that re-verification, as of this revision**
  (**eight** schematic-level slices, one per campaign whose recorded result
  depends on `C_u` — #197's own scope named four; re-running them found two
  more decks PR #202 had regenerated without re-taking their records, and a
  further two that PR #202 could not have reached at all because they model
  the array as one lumped MiM capacitor rather than consuming generated
  `adc-top` output).
  The consolidated before/after adjudication for all of them, with the
  commands that re-derive each number, is
  `spec/testbench-suite-memo.md` §11.9:
  - ENOB/FFT + SFDR — **done** (issue #204, PR #210): regression, see above.
  - Power — **done** (issue #205, PR #212): +13.4 % total, still PASS with
    2.4× margin against the 500 µW stretch (Power row above).
  - CDAC bit-settling, 117-point grid — **done** (issue #197, this change):
    the gating `err_1msps_*` budget check does not move at all (0 mV on the
    whole grid); the 1.5 ns in-transient lag and the `lag_ord_256_64`
    ordering margin do move, both still PASS (Reference row above). This
    slice also had to fix the campaign's own testbench first: PR #202 resized
    the three sibling `adc-top`-derived decks but not
    `sim/cdac-bit-settling/testbench/tb_cdac_bit_settling.spice`, so a re-run
    without that fix would have re-certified the pre-resize array.
  - Top-plate `C_par` decomposition — **done** (issue #197): the array
    scales ×2.068 and the load on it does not, so the
    `C_arr/(C_arr + C_par)` divider loss *halves* (0.9951 → 0.4821 % mean);
    the top-plate `V_cm` switch term is **bit-identical** before and after
    (16.7721 fF mean). This slice also had to fix its own deck first, the
    same way the settling slice did: PR #202 regenerated
    `tb_top_plate_cpar.spice` at the new geometry but left the deck's
    `c_arr_v1p65_ff` window hard-coded around the pre-resize array, so all
    63 points failed a bound that is a sanity check on `512 × C_u`, not a
    ratified target. The window is now *computed* from `C_UNIT_FF`
    (§11.9.5).
  - DR-0014 mechanism deck (`sim/dr0014-sampling/`) — **done** (issue #197):
    27/27 PASS. The **Gain error, systematic** row improves 2.26×
    (0.0045–0.0088 → 0.0021–0.0039 LSB) and the **Input structure `R_on`**
    range is **bit-identical** at all 27 points — see both rows above and
    §11.9.6. Its re-take also complicates the mechanism story behind the
    ENOB/SFDR regression: the acquisition bow `spec/testbench-suite-memo.md`
    §11.2 argues from *improves* across the resize at 8 of 9 corners while
    SFDR degrades (§11.9.7) — a datum for #211, not a resolution of it.
  - Static INL/DNL — **done** (issue #203, PR #214): 63/63 PASS and the row
    the resize was *for* does not move — worst \|INL\| 0.1036 → 0.1100 LSB,
    worst \|DNL\| 0.1036 → 0.0938 LSB, both still 4.5–5.3× inside the
    < 0.5 LSB stretch (INL/DNL row above, §11.9.10). Per corner the movement
    is mixed rather than systematic, which is the expected null for a
    linearity set by *ratios* of units that all scaled together.
  - Track-mode THD, the switch's own SFDR share (`sim/track-switch-thd/`) —
    **done** (issue #197, this change): **a ratified-target miss, flagged**.
    All 117 points lose 4.96–5.77 dB and 11 of 117 fall below the ratified
    62 dB where none did before (SFDR row above, §11.9.11). This deck's
    distortion term is *linear* in the array capacitance, which makes it the
    first measured mechanism that moves the same way and by the same size as
    the end-to-end SFDR regression #211 owns.
  - Input drive contract (`sim/track-switch-sampling/`) — **done** (issue
    #197, this change): 117/117 PASS and the ratified row *improves*
    (+0.082…+0.370 LSB, was −0.293…+0.421), because every charge-injection
    term is `Q_inj/C_hold`. One quantity moves the other way and is recorded:
    acquisition settling at the 100 pF/250 Ω drive point ×5.0, to 0.0103 LSB
    (Input drive-contract row above, §11.9.12).
  - **Neither of the last two decks was regenerated by PR #202** — they do
    not consume `adc-top` generator output, so both still drew the pre-resize
    66.36 µm lumped array square (8.827 pF) and their standing records
    certified a load half the size of the array now drawn. The census of
    `C_u`-bearing decks is therefore eight, not six.
  - **Extracted (post-layout) re-verification of all of the above — done**
    (issue #218). The #202 layout was re-extracted (1024 MiM caps at
    `c_f = 35.6528 fF` / 16.0 µm², against 17.245 fF / 7.366 µm² before) and
    all five extracted campaigns re-run against it, each superseding its
    pre-resize record on the same deck, manifest and grid. Every extracted
    figure this document cites is now post-resize. Outcome, per
    `sim/extracted-delta-summary.md` §4.12: **ENOB and SFDR now FAIL on the
    governing side** (8.857 bits, 60.40 dB) — the SFDR row had *no* valid
    governing result while its extracted side was pre-resize, and its first
    valid one is a 1.60 dB miss; **INL/DNL still PASSes its ratified row but
    misses the `< 0.5 LSB` stretch** post-layout (0.528 / 0.728 LSB);
    **power PASSes** at 246.5 µW (+11.6 %); the **`Gain error, systematic`**
    row *improves* to ~1047× inside its bound; and the **Input structure
    `R_on`** row is an **exact null** (the switch leaf is not resized). The
    mechanism behind the ENOB/SFDR regression remains #211's, which has since
    isolated it to the acquisition `R_on·C_arr` time constant
    (`sim/dr0019-cu-sweep-findings.md`) — the post-layout re-take is
    consistent with that, since the drawn in-path resistance is exactly what
    the extraction adds.
- **CDAC capacitor mismatch under Monte Carlo** — not applicable: the PDK's
  MiM subckt has no local mismatch model on either netlist (`sim/tools/pdk_mismatch_audit.py`).
- **Direct CMRR at the ratified ±100 mV common-mode band** — measured at
  ±50 mV and linearly extrapolated (stated limitation, `spec/testbench-suite-memo.md`
  §10/§12 item 7).
- **A 2× comparator-current excursion at one power corner** (`tt_125c_3.63v`,
  #107) — investigated across two independent campaigns and found not to
  reproduce run-to-run; carried open as a marginal-decision artefact rather
  than absorbed into the passing Power row's margin statement.

## Digital partition (`sar_ctrl_a`) — Fmax, area and power across the corner set

**Why this section exists separately.** This block's `kind` is
`mixed-signal`, and T1 item 8 asks a *digital* partition for something the
analog table above does not carry: *"Fmax, area, and power across the corner
set, not just functional pass/fail"*
(`klayout-tools`' `docs/design-evidence-tiers.md`). The SAR sequencer is no
longer the rung-1 ideal XSPICE model the analog rows above are simulated
against — it is RTL, synthesized to `gf180mcu_fd_sc_mcu7t5v0` standard
cells, formally equivalence-checked, placed and routed into the footprint
`layout/adc-top/` reserves for it, DRC-clean, and timed post-route across a
corner set. This section aggregates that, from the committed `klt` response
JSONs, and states what it does **not** cover.

**Everything below is transcribed from a committed `klt` response, exactly
as the analog table is transcribed from `sim/` records.** This section
creates no numbers of its own.

### Implementation summary

| Quantity | Value | Source |
|---|---|---|
| RTL top | `sar_ctrl_a` | `design/sar-logic/rtl/` |
| Synthesis (`klt synthesize`, yosys `0.69+post`) | `status: ok`; **181 instances**, cell area **4961.152 µm²** (sequential 2864.736 µm²) on `gf180mcu_fd_sc_mcu7t5v0` | [`…2d1394f.mcu7t5v0.synthesize_response.json`](../design/sar-logic/flow/sar_ctrl/reports/20260910-224930-2d1394f.mcu7t5v0.synthesize_response.json), record [`20260910-224930-2d1394f.mcu7t5v0.md`](../design/sar-logic/flow/sar_ctrl/records/20260910-224930-2d1394f.mcu7t5v0.md) |
| Second library, synthesized but **not** carried forward | `gf180mcu_fd_sc_mcu9t5v0`: 187 instances, 6917.7024 µm² — the 7-track library is the one placed and routed | `…2d1394f.mcu9t5v0.synthesize_response.json` |
| Formal equivalence RTL ↔ gates (`klt equiv`, `yosys-sequential`) | **`status: equivalent`**, induction depth 4, zero counterexamples — on **both** libraries | `…2d1394f.{mcu7t5v0,mcu9t5v0}.equiv_response.json` |
| Place & route (`klt place-and-route`, OpenROAD `26Q3-1510-g6cb3f2b704`) | `status: ok`, `stage_reached: route`. **Die area 7968.400 µm²** (199.210 × 40.000 µm) = **exactly** the ring-exclusive core box `layout/adc-top/` reserves; core 7792.96 µm²; utilization **67.72 %**; wirelength 7274 µm; **0 route-DRC, 0 antenna** violations | [`…3a9a8ba.mcu7t5v0.pnr_response.json`](../design/sar-logic/flow/sar_ctrl/reports/20260915-000027-3a9a8ba.mcu7t5v0.pnr_response.json), record [`20260915-000027-3a9a8ba.mcu7t5v0.pnr.md`](../design/sar-logic/flow/sar_ctrl/records/20260915-000027-3a9a8ba.mcu7t5v0.pnr.md) |
| DRC of the merged routed GDS (`klt drc`, deck `gf180mcu`) | **`status: clean`**, 0 violations — this is the artifact `signoff/`'s item **3.digital** cites | `…3a9a8ba.mcu7t5v0.pnr_drc.json` |
| LVS of the routed macro | **Does not exist.** No golden SPICE reference for the merged GDS is generated in this repo — which is why `signoff/`'s item **4.digital** is uncited rather than borrowing the analog block's compare | `…pnr.md` §Scope |

The reserved-footprint claim is stronger than "the reported area matches":
the run used an **explicit** floorplan fixed at the reserved box with no
margin, so OpenROAD reaching `stage_reached: "route"` at all *is* the
fit evidence — a design that did not fit would have raised a
legalization/placement failure before any routed DEF was written.

### Fmax, timing and power across the corner set (post-route)

One fixed routed DEF (`layout/adc-top/sar_ctrl/sar_ctrl.def`,
`geometry_source: "routed"`), swept across corners by real `klt sta` — **not**
re-placed per corner. Budget: DR-0003's 62.5 ns bit-cycle period
(16.00 MHz, M = 16 at 1 MS/s).

| Corner | Setup slack (ns) | Setup TNS | Hold slack (ns) | Hold TNS | **Fmax (MHz)** | **Est. power (mW)** |
|---|---|---|---|---|---|---|
| `tt_025C_3v30` † | PASS +59.4791 | 0.0000 | PASS +1.1464 | 0.0000 | 331.02 | 0.2787 |
| `ss_125C_3v00` † | PASS +56.3650 | 0.0000 | PASS +2.3195 | 0.0000 | **163.00** | 0.2360 |
| `ss_n40C_3v00` | PASS +58.1701 | 0.0000 | PASS +1.6311 | 0.0000 | 230.95 | **0.2260** |
| `ff_125C_3v60` | PASS +60.0932 | 0.0000 | PASS +0.9096 | 0.0000 | 415.49 | **0.3476** |
| `ff_n40C_3v60` † | PASS +60.7878 | 0.0000 | PASS +0.6512 | 0.0000 | 584.03 | 0.3310 |

† named individually by DR-0023's ratified 3.3 V corner grid; the other two
are the remaining 3.3 V corners `gf180mcu_fd_sc_mcu7t5v0` ships, swept here
rather than left unasked.

- **Setup: PASS at every corner. Hold: PASS at every corner.** Worst setup
  slack **+56.3650 ns** against the 62.5000 ns budget (90.2 % of the period
  still unspent) at `ss_125C_3v00`; worst hold slack **+0.6512 ns** at
  `ff_n40C_3v60`.
- **Worst-corner Fmax 163.00 MHz against a 16.00 MHz requirement** — a
  10.2× margin. Fmax is `report_fmax_metric`'s own extrapolation, **not** a
  bisected search (`klt`'s own stated caveat for every `sta` run).
- **Estimated power 0.2260 – 0.3476 mW** across the corner set, worst at
  `ff_125C_3v60`. This is OpenSTA's estimate for the routed macro alone; it
  is **not** additive with the analog table's Power row without care — that
  row's 231.8 µW is the extracted **analog** core, and its records state
  plainly that the rung-1 sequencer contributes zero measured current
  because it contains no devices (DR-0010 rung 1). Summing the two is the
  obvious next step and is **not** done here, because nobody has run the
  combined measurement and this document transcribes rather than derives.
- Source: record
  [`20260915-093934-7ab8971.mcu7t5v0.sta_postroute.md`](../design/sar-logic/flow/sar_ctrl/records/20260915-093934-7ab8971.mcu7t5v0.sta_postroute.md)
  and the five per-corner `…sta_postroute_<corner>.sta_response.json` files
  beside it. It carries `Supersedes: 20260914-235615-7022eab.mcu7t5v0.sta`
  — the pre-route record, whose `klt place-and-route --target_stage place`
  substitution re-placed the design per corner (a sweep of N designs, not a
  characterization of one) and reported hold as a violation count only.

**Disclosed limitations of these timing numbers**, carried from the record
rather than dropped:

1. **No extracted SPEF.** No `klt extract --parasitics` run exists for
   `sar_ctrl_a`, so OpenSTA times this from its own LEF/DEF-geometry RC
   estimate. The clock tree, placement and routing are #279's real committed
   geometry — but this is not a SPEF-annotated signoff number. The margin at
   every corner is wide enough that the gap is unlikely to flip the verdict;
   that is an engineering judgment, stated, not a proof.
2. **Ideal SDC clock, not propagated; Fmax not bisected.** The same caveat
   `klt`'s `sta` documentation states for every run of that verb.
3. **Interconnect corner `nom` only** on the P&R run; the 15-corner liberty
   sweep the P&R response also reports (worst setup +41.0121 ns at
   `ss_125C_1v62`) spans the library's 1.62–5.50 V range, most of which is
   outside this block's ratified 2.97–3.63 V supply row and is therefore
   **not** quoted as this partition's corner set.

### Functional status of the digital partition — open, and deliberately a pointer

T1 item 8's digital sentence says Fmax/area/power is wanted *"not just"*
functional pass/fail, so the functional half belongs here too. It is
**not closed**, and this document deliberately states its status by pointer
rather than transcribing figures that are moving week to week:

- **Rung-1 (ideal XSPICE sequencer model, DR-0010)** — **PASS**. This is
  what the analog table's Resolution / Latency / Clock / Interface rows rest
  on: `sim/sar-logic-functional/records/20260802-110241-131989b.md` and
  `sim/sar-logic-timing/records/20260802-102758-d8a363d.md`.
- **Rung-2 (SPICE replay of the real synthesized gate netlist)** —
  **NOT PASSING, and under active root-causing.** Six campaigns
  have committed records (`sim/sar-logic-functional-gates/`,
  `sim/sar-logic-timing-gates{,-ok,-tie,-lt,-xl}/`; a seventh,
  `sim/sar-logic-timing-gates-bad/`, has a testbench and no record yet);
  as of `93ddfe3` each of those six's latest record reads `FAIL` or
  `ERROR`, with
  causes so far attributed to deck-composition and ngspice-convergence
  artifacts rather than to sequencer defects, plus two accepted findings
  already carried into decision records ([DR-0027](../spec/decision-records/DR-0027-gate-decode-one-hot-hazard-budget.md)'s
  bounded gate-decode one-hot hazard, [DR-0028](../spec/decision-records/DR-0028-gate-level-acquisition-isolation-bounds.md)/[DR-0030](../spec/decision-records/DR-0030-functional-deck-acquisition-isolation-bounds.md)'s
  acquisition/isolation bounds, [DR-0031](../spec/decision-records/DR-0031-power-up-first-conversion-validity.md)'s
  power-up first conversion). **Read each campaign's own latest record for
  its current state — not this paragraph.** This is a deliberate choice:
  transcribing a figure from a campaign that mints a new record every day or
  two would make this document stale on the day it is written, which is the
  exact defect the Freshness section above exists to prevent.
- **Consequence for `signoff/`**: this is also why the digital partition's
  item **5** ("Full corner verification vs a ratified spec") is uncited
  there. Item 8 grades whether an *aggregated, current characterization
  artifact* exists; it does not grade whether the partition passes. Those
  are different rows on purpose.

## How this document is kept in sync

This is a **snapshot table**, not a live query — it will drift the same way
`README.md`'s Status paragraph drifted before this issue. There is no
automated freshness check *of its contents* (a candidate for future tooling,
not built here). The discipline that keeps drift bounded: every PR that mints
a new `sim/` record superseding a citation in this table, or that changes a
verdict, is expected to update the corresponding row here in the same PR —
the same discipline `README.md`'s own Status table and
`spec/testbench-suite-memo.md`'s coverage map already follow. A reader who
finds a citation here that no longer matches its record's own `Supersedes`
chain has found a drift and should file it, the same way `README.md`'s own
one-PR lag was found and fixed by this issue — and the same way this
document's own four currency defects were found and fixed by the 2026-09-21
re-read recorded in the Freshness section.

**What *is* machine-checked, as of issue #339.** This file's bytes are
pinned. `signoff/evidence/characterization-summary.{analog,digital}.json`
are two generic evidence envelopes (`"kind": "generic"`, the only kind T1
item 8 accepts) that record this document's sha256 and assert
`status: "pass"` over it; `signoff/gf180-sar-adc.manifest.json` cites them
for `8.analog` / `8.digital`, and `python3 signoff/run_signoff.py --check`
re-hashes this file on every pull request. **That check proves the bytes
graded are the bytes committed — it cannot prove the bytes are still
true.** Editing this document without re-running
`python3 signoff/run_signoff.py --regen` turns CI red, which is the point:
a change here is a change to a signed claim, and it has to be re-asserted
deliberately rather than drift in unremarked. What still has to be done by a
human is the re-read itself.
