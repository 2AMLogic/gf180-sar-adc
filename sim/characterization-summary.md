# Full-ADC characterization summary — one row per ratified spec line

Issue #174 (T1 item 8, `2AMLogic/gf180-sar-adc#169`'s closing verdict row 8).
This is the single aggregated, current answer to "what is this converter's
measured performance, right now, against the ratified target spec" — every
row of `README.md#target-specification` (DR-0006), its **latest** verified
value, its verdict, and a dated citation to the record that produced it.

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

**As of commit `607d6e6` (2026-08-16).** This is not merely a statement that
the five source documents below exist — it is a re-read of each of them
against that exact commit, done for this document:

| Source document | Re-read against | What changed since the #169 snapshot (2026-08-15) this issue was curated from |
|---|---|---|
| `README.md` | `607d6e6` | Status paragraph and Verification-suite row updated by this same change (issue #174) — the stale "rate closure … still depend[s]" sync lag #169 flagged is fixed here |
| `spec/testbench-suite-memo.md` | `607d6e6` | §12 item 8c (Gain error, mismatch 2.12σ finding) and the coverage-map citations for Offset error / Gain error, mismatch / CMRR added by PR #182 (issue #172, T1 item 6) |
| `sim/extracted-delta-summary.md` | `607d6e6` | §9 (`klt pex`, T1 item 7) added by PR #184 (issue #173); no change to §3–§8 since the 2026-08-14 rate-closure closure |
| `sim/issue-17-acceptance-review.md` | `607d6e6` | Unchanged since its 2026-08-14 "8 of 8 AC PASS" disposition update — re-verified current, not stale |
| `sim/device-characterization-report.md` | `607d6e6` | Unchanged since 2026-07-31 — device-level scope, explicitly not full-ADC; this document is the full-ADC companion, not a replacement |

**PRs incorporated that postdate this issue's 2026-08-15 curation** (per the
Builder dispatch note — main moved after curation and this document reflects
current `main`, not the curator's snapshot):

- **PR #182** (issue #172, T1 item 6): `klt yield`-format statistical evidence
  for the Gain error, mismatch / Offset error / CMRR rows —
  `sim/mc-cdac-mismatch/yield-evidence/`, `sim/comparator-offset-mc/yield-evidence/`.
  This is where the **Gain error, mismatch 2.12σ FAIL** finding in the table
  below comes from — a real, newly-quantified, non-layout finding, not
  previously reflected in `README.md`.
- **PR #184** (issue #173, T1 item 7): a genuine `klt pex` run against the
  post-layout comparator — `sim/comparator-pex/`. It fails structurally (a
  DUT-interface mismatch `klt pex` cannot bridge), re-grading item 7 from
  "N/A by construction" to "tried, blocked, filed upstream" — see the Rate /
  comparator-inclusive-extraction row's Notes below.

**Known incompleteness, stated rather than silently absorbed**: the INL/DNL
row's own `klt yield` reformat is a separate, still-open PR (**#149**,
`feature/klt-yield-evidence-818`) that predates issue #172's Gain-error/
Offset/CMRR work and has not landed as of this commit — INL/DNL below is
therefore reported from its underlying `sim/mc-cdac-mismatch/` record
directly (fit-and-extrapolate yield, not the `klt yield` tool's own report
format), exactly as `spec/testbench-suite-memo.md` §2's coverage map states.
This is a format gap, not a measurement gap: the number and verdict are not
in question, only which tool formatted them.

## Per-spec-row status

| Spec row (README target) | Target | Latest verified value | Verdict | Source (dated) |
|---|---|---|---|---|
| Resolution | 10 bit | 10 bits resolved (architectural, `sar-logic` decode proof) | **PASS** | [`sim/sar-logic-functional/records/20260801-041242-96c2ea7.md`](sar-logic-functional/records/20260801-041242-96c2ea7.md) |
| Rate (1 MS/s) closure | 1 MS/s (2 MS/s stretch) | Settling τ 1.258 → 1.560 ns; comparator delay 0.863 → 1.257 ns; all three post-layout inputs (`R_WORST_BIT_OHM` 648 Ω, `C_WORST_BIT_F` 2.40712 pF, `T_COMP_REGEN_NS` 1.257 ns) | **PASS — all three inputs post-layout** (2026-08-14, issue #116; closes the sync lag issue #174 fixes in `README.md`) | [`sim/timing-budget-closure/records/20260814-220124-f613571.md`](timing-budget-closure/records/20260814-220124-f613571.md); disposition: [`sim/issue-17-acceptance-review.md`](issue-17-acceptance-review.md) AC7 |
| ENOB @ Nyquist | > 9.0 (> 9.5 stretch) | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #204): schematic 8.507 bits worst (`ss_125c_2.97v`)** — a regression from the pre-resize 9.163 bits, and now below the > 9.0 target at 2 of 9 grid points (`ss_125c_2.97v` 8.507, `ss_125c_3.30v` 8.968). The **9.103 bits extracted** figure below is now **STALE**: it was measured against the historical `C_u = 17.24 fF` layout, before #196/#202 physically implemented the resize, and has not been re-taken against the current design | **FAIL** (schematic, current design) — regression flagged, not absorbed; extracted citation is stale and no longer trustworthy as governing until re-verified (tracked follow-up, see issue #204's PR) | [`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](adc-enob-fft/records/20260817-080939-afb1b3a.md) (schematic, resized `C_u`, issue #204, supersedes `20260814-193205-f613571`); [`sim/adc-enob-fft/records/20260807-054805-e8cd2b8.md`](adc-enob-fft/records/20260807-054805-e8cd2b8.md) (extracted, **stale**, pre-resize, issue #123); `sim/extracted-delta-summary.md` §4.6/§4.10 |
| SFDR @ Nyquist | ≥ 62 dB (≥ 65 stretch) | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #204): schematic 56.41 dB worst (`ss_125c_2.97v`)** — **FAIL by 5.59 dB, widened from the pre-resize 0.67 dB gap** (61.33 → 56.41 dB at the same worst corner; 8 of 9 grid points got worse, one — `ff_125c_3.30v` — improved by +0.43 dB). The **64.38 dB extracted** figure below is now **STALE**: measured against the historical `C_u = 17.24 fF` layout, before #196/#202 physically implemented the resize, and has not been re-taken against the current design | **FAIL** (schematic, current design; gap widened, not narrowed) — extracted citation is stale and no longer trustworthy as governing until re-verified | [`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](adc-enob-fft/records/20260817-080939-afb1b3a.md) (schematic, resized `C_u`, issue #204, supersedes `20260814-193205-f613571`); [`sim/adc-enob-fft/records/20260814-193205-f613571.md`](adc-enob-fft/records/20260814-193205-f613571.md) (schematic pre-resize baseline); `sim/extracted-delta-summary.md` §4.10/§7.3 (**stale**); `spec/testbench-suite-memo.md` §11.2 item 8b |
| INL / DNL | < 1 LSB (< 0.5 stretch) | **Re-run at the physically-implemented DR-0019 resize (`C_u = 35.6528 fF`, issue #203): nominal PVT (schematic) INL 0.1100 LSB (`inl_t384_lsb`, `cap_ss_125c_2.97v`) / DNL 0.0938 LSB (`dnl_t128_t129_lsb`, `cap_ss_125c_2.97v`)** — essentially unchanged from the pre-resize schematic baseline (worst \|INL\| 0.1036 → 0.1100 LSB, +0.0064; worst \|DNL\| 0.1036 → 0.0938 LSB, −0.0098), both still ~4.5–5.3× inside the < 0.5 LSB stretch target, all 63/63 `cdac`-grid points PASS, nothing moved outside the ratified target. The **0.148 LSB / 0.098 LSB extracted (`mos` grid)** figures below are now **STALE**: measured against the historical `C_u = 17.24 fF` layout, before #196/#202 physically implemented the resize, and not yet re-taken against the current design (tracked follow-up, out of scope for issue #203 per its Non-goals); 3σ mismatch: DNL PASS 5.96σ margin, INL PASS 11.9σ margin at the ratified baseline | **PASS** (nominal PVT schematic re-run at resized `C_u`, and 3σ mismatch) — extracted citation is stale and no longer trustworthy as governing until re-verified | [`sim/adc-inl-dnl/records/20260817-110133-54c6e96.md`](adc-inl-dnl/records/20260817-110133-54c6e96.md) (schematic, resized `C_u`, issue #203, supersedes `20260805-220405-bff6eaf`); [`sim/adc-inl-dnl/records/20260807-081223-6bd9d80.md`](adc-inl-dnl/records/20260807-081223-6bd9d80.md) (extracted, `mos` grid, issue #132, **stale pre-resize**); [`sim/mc-cdac-mismatch/records/20260801-093800-c033611.md`](mc-cdac-mismatch/records/20260801-093800-c033611.md) (3σ mismatch); `klt yield` reformat of this row is PR #149, **not yet landed** |
| Offset error | ≤ 2 LSB, untrimmed | Comparator-only (schematic-level, not `ADC_BLOCK`-inclusive) 3σ-mismatch: worst-corner σ 0.398789 LSB, `cpk` 1.66, `sigma_to_spec` 4.99σ, zero samples outside limits at N = 150 (`klt yield` `status: fail` is a **sample-size artifact** — N = 150 cannot support a 3σ/99.73% claim at 95% CI; 1365 samples would). Deterministic (non-statistical) extracted-core systematic offset: −0.597…−4.357 mV across the 45-point grid, well inside the 12.89 mV (2 LSB) bound | **Not measured as a comparator-inclusive (`ADC_BLOCK`) 3σ statistical population** (issue #89 Scope item 2's remaining work); everything measured so far clears its bound with wide margin | [`sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md`](comparator-offset-mc/records/20260816-050504-66a0e2e.md) (`klt yield`, issue #172, clean-tree 45/45); [`sim/comparator-regeneration/records/20260814-215626-f613571.md`](comparator-regeneration/records/20260814-215626-f613571.md) (deterministic extracted-core offset, issue #116) |
| Gain error, mismatch | ≤ 0.5 LSB, untrimmed, excluding V_REF error | **As built (`C_u = 17.24 fF`): 2.12σ measured against the ratified 3σ condition — 0.708 LSB at 3σ**, `klt yield` `status: fail` (genuine, not a sample-size artifact: N = 20 000, negative control at 3× `σ_u` correctly detected). **Resizing decision (`C_u = 35.6528 fF`, not yet physically implemented): `sigma_to_spec = 3.13`, `klt yield` `status: pass`**, N = 20 000, DNL/INL re-confirmed to still pass at the new `σ_u` | **FAIL as built** — reported, not absorbed; no spec value relaxed, no testbench retuned. **Sizing decision that closes it is made and verified; physical implementation pending** | [`sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`](mc-cdac-mismatch/records/20260816-044942-56fbe50.md) (issue #172, as-built); [`sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`](mc-cdac-mismatch/records/20260816-125421-737d16e.md) (issue #177, resizing decision); `spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`; `spec/testbench-suite-memo.md` §12 item 8c |
| Gain error, systematic | ≤ 0.5 LSB, untrimmed, excluding V_REF error | Schematic 0.0045–0.0088 LSB (`ff_-40c_2.97v`); extracted **0.00046–0.0016 LSB** (`ff_-40c_3.63v`), ~307× inside the bound | **PASS** | [`sim/dr0014-sampling/records/20260807-091733-434dc37.md`](dr0014-sampling/records/20260807-091733-434dc37.md) (in-path extraction, issue #131); `sim/extracted-delta-summary.md` §4.9 |
| CMRR (differential) | ≥ 60 dB (≥ 65 stretch) | Worst-corner-of-45 (`ss_-40c_3.63v`), clean-tree re-run: systematic Δoffset over ±50 mV CM implies **118.2 dB**; 3σ-mismatch Δoffset implies **85.6 dB**. Both clear ≥ 60 dB by ≥ 25.6 dB. Direct ±100 mV measurement not performed — linear extrapolation from the ±50 mV band, stated as such | **PASS**, wide margin | [`sim/comparator-offset-mc/records/20260816-050001-d002e66.md`](comparator-offset-mc/records/20260816-050001-d002e66.md) + [`20260816-050504-66a0e2e.md`](comparator-offset-mc/records/20260816-050504-66a0e2e.md) (issue #172, 2026-08-16 — corrects the prior 99.0/117.5 dB citation, which never reached the true worst corner); `spec/testbench-suite-memo.md` §10 |
| Input (drive contract) | External driver, R_source/C_pin budget | Full 117-point PVT grid at the DR-0013 network: sampling-switch gain-error contribution −0.293…+0.421 LSB (worst `ff_125c_3.63v`) | **PASS** | [`sim/track-switch-sampling/records/20260802-141402-1224e11.md`](track-switch-sampling/records/20260802-141402-1224e11.md) |
| Input structure (C_in, R_on, T/H BW) | C_in 8.827 pF/side; R_on 21.3–60.0 Ω (array); T/H BW ≥ 5.3 MHz | Schematic R_on (drawn `adc_tgate` leaf) 570.436 Ω (`ss_125c_2.97v`); extracted (in-path, `875eac3` pin) **647.818 Ω**, +13.6 % — clean-tree re-take, bit-identical to the dirty-tree original across all 45 corners × 25 columns | **PASS**, both sides | [`sim/device-switch-ron/records/20260814-191138-f613571.md`](device-switch-ron/records/20260814-191138-f613571.md) (clean-tree, issue #150, supersedes `20260806-194322-68ad582`); `sim/extracted-delta-summary.md` §4.8 |
| Reference (Z_ref, C_dec) | V_REF = 3.3 V ext.; ≥ 40 nF decoupling; Z_ref ≤ 240 Ω | Bit-cycle settling **PASS at all 117 PVT points, re-run at the DR-0019-resized `C_u = 35.6528 fF`** (issue #197). The gating budget check `err_1msps_*` — top-plate settling error 62.5 ns after the bit trial, bound ±1.6113 mV (0.5 LSB) — is **unchanged at 0 mV** on the whole grid, i.e. the 2.068× array-capacitance increase costs this row nothing measurable. The 1.5 ns in-transient anchor does move: worst-corner (`ss_125c_2.97v`) residual lag rises 0.738 → 0.863 of the step (w=256) and the `lag_ord_256_64` ordering margin narrows 0.242 → 0.148 against its ≥ 0.05 floor (4.85× → 2.96×) — **still PASS, flagged as a margin trend, not absorbed**. Schematic; not re-taken post-layout — this row is off the extracted `ADC_TOP` boundary, so it has no extracted counterpart to go stale | **PASS** (schematic-level, at the resized `C_u`) | [`sim/cdac-bit-settling/records/20260817-121555-227c770.md`](cdac-bit-settling/records/20260817-121555-227c770.md) (issue #197, re-run at the resized `C_u`; supersedes [`20260731-231537-1ee5578`](cdac-bit-settling/records/20260731-231537-1ee5578.md), the pre-resize baseline) |
| Clock (M = 16, jitter) | 16 MHz @ 1 MS/s; jitter ≤ 250 ps rms (analytic, DR-0003) | 16-phase conversion completes deterministically | **PASS** | [`sim/sar-logic-timing/records/20260801-033032-06bad60.md`](sar-logic-timing/records/20260801-033032-06bad60.md) |
| Supply (±10 %) | 2.97–3.63 V | Spanned by the supply axis of every PVT sweep cited above | **PASS** (no dedicated record — it is the corner axis every other row already sweeps) | every record above |
| Latency / conversion timing | 1 conversion, M = 16 clocks = 1 µs @ 1 MS/s | Deterministic, as above | **PASS** | `sar-logic-functional` + `sar-logic-timing` records above |
| Power @ 1 MS/s | < 1 mW (< 500 µW stretch) | **Schematic, DR-0019-resized `C_u = 35.6528 fF` (issue #205): 207.9 µW worst (`ff_-40c_3.63v`), +13.4 % vs. the pre-resize 183.3 µW** (worst-of-grid deltas per block, each at its own worst point: comparator −3.6 %, CDAC switch+driver essentially flat at −0.09 %, DR-0014 top-plate V_cm switch essentially flat at +0.26 %, V_REF +92.2 %, V_cm bias +38.9 %); extracted (in-path) **185–221 µW**, still the PRE-resize (`C_u = 17.24 fF`) layout — re-verifying the extracted number at the resized `C_u` is a further follow-up, not yet done (issue #205 non-goal), 4.5–5.4× margin over the pre-resize schematic number, 26/27 corners agreeing to ≥ 4 sig figs between two independent campaigns; one corner (`tt_125c_3.63v`) shows a 2× comparator-current excursion, investigated and found non-reproducible run-to-run (marginal-decision artefact, not a corner/layout property) | **PASS**, 2.4×+ margin against the 500 µW stretch target (4.8×+ against the 1 mW primary target) at the resized `C_u`; excursion tracked open, not absorbed | [`sim/adc-power/records/20260817-081223-afb1b3a.md`](adc-power/records/20260817-081223-afb1b3a.md) (DR-0019 resized-`C_u` re-take, issue #205, supersedes [`20260802-141402-1224e11.md`](adc-power/records/20260802-141402-1224e11.md)); [`sim/adc-power/records/20260807-084749-290d003.md`](adc-power/records/20260807-084749-290d003.md) (extracted, DR-0018-revised floor, still pre-resize); `sim/extracted-delta-summary.md` §4.7/§4.10/§4.11.1, tracking issue **#107** |
| Area | < 0.1 mm² | **0.12100 mm²** — 121 % of the ratified budget, once the CDAC MiM stack is drawn at its legal geometry | **FAIL against the ratified `< 0.1 mm²` budget**; a `< 0.13 mm²` revision is proposed for operator ratification, not yet ratified | [`spec/decision-records/DR-0017-adc-top-area-budget-overrun.md`](../spec/decision-records/DR-0017-adc-top-area-budget-overrun.md); `layout/adc-top/README.md` |
| Interface | Parallel register in scope; SPI deferred | Parallel output register verified functional | **PASS** (SPI explicitly out of scope, DR-0005) | [`sim/sar-logic-functional/records/20260801-041242-96c2ea7.md`](sar-logic-functional/records/20260801-041242-96c2ea7.md) |

## What is not yet measured, stated rather than silently dropped

- **Comparator-inclusive (`ADC_BLOCK`) statistical Monte Carlo** — the
  ratified `Offset ≤ 2 LSB` row's own 3σ population through the extracted
  core. `ADC_BLOCK` converts (issue #118) and its regeneration-margin
  campaign has run (issue #116), but the statistical offset population has
  not — issue #89 Scope item 2's remaining half.
- **INL/DNL's own `klt yield` reformat** — PR #149 (`feature/klt-yield-evidence-818`),
  mergeable and green as of this document's freshness date, but not yet
  landed. The underlying measurement and verdict (PASS) are not in question;
  only the machine-checkable evidence format is pending.
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
  make and verify the sizing decision that closes the 2.12σ-vs-3σ gap this
  document reports as FAIL (`sigma_to_spec = 3.13` at the resized `σ_u`,
  `sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`); per CLAUDE.md,
  no spec value is relaxed to close it. **Physically implementing the
  resize** — updating `design/adc-top/gen_adc_top.py` / `layout/adc-top/`'s
  unit-cap constants — is **DONE** (issue #196, merged PR #202).
  **Re-running the full transistor-level PVT verification suite at the new
  `C_u`** is issue #190/#197's decomposed follow-up, in progress: the
  schematic-level ENOB/FFT + SFDR slice is done here (issue #204) and
  surfaces a **new, unbudgeted regression** — worst schematic ENOB drops
  from 9.163 to 8.507 bits (now FAILING the > 9.0 target at 2 of 9 grid
  points) and the pre-existing SFDR FAIL widens from a 0.67 dB to a 5.59 dB
  gap (see the ENOB @ Nyquist / SFDR @ Nyquist rows above). This is
  reported, not fixed, here — DR-0019's own sizing decision is not
  re-litigated by this document, but the dynamic-performance cost of that
  decision was not previously measured and is now on the record.
  **Per-campaign status of that re-verification, as of this revision**
  (four schematic-level slices, one per campaign whose recorded result
  depends on `C_u`):
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
  - Static INL/DNL — **still open** (issue #203).
  - **Extracted (post-layout) re-verification of all of the above — still
    open, and not yet filed as an issue.** Every extracted figure this
    document cites was measured against the pre-resize layout; that is now
    flagged at the top of `sim/extracted-delta-summary.md` rather than left
    implicit.
- **CDAC capacitor mismatch under Monte Carlo** — not applicable: the PDK's
  MiM subckt has no local mismatch model on either netlist (`sim/tools/pdk_mismatch_audit.py`).
- **Direct CMRR at the ratified ±100 mV common-mode band** — measured at
  ±50 mV and linearly extrapolated (stated limitation, `spec/testbench-suite-memo.md`
  §10/§12 item 7).
- **A 2× comparator-current excursion at one power corner** (`tt_125c_3.63v`,
  #107) — investigated across two independent campaigns and found not to
  reproduce run-to-run; carried open as a marginal-decision artefact rather
  than absorbed into the passing Power row's margin statement.

## How this document is kept in sync

This is a **snapshot table**, not a live query — it will drift the same way
`README.md`'s Status paragraph drifted before this issue. There is no
automated freshness check (a candidate for future tooling, not built here).
The discipline that keeps drift bounded: every PR that mints a new `sim/`
record superseding a citation in this table, or that changes a verdict, is
expected to update the corresponding row here in the same PR — the same
discipline `README.md`'s own Status table and `spec/testbench-suite-memo.md`'s
coverage map already follow. A reader who finds a citation here that no
longer matches its record's own `Supersedes` chain has found a drift and
should file it, the same way `README.md`'s own one-PR lag was found and
fixed by this issue.
