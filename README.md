# gf180-sar-adc

A 10-bit SAR ADC for **gf180mcu**, GlobalFoundries' open 180 nm PDK, designed
end to end on the open-source analog flow: [xschem](https://xschem.sourceforge.io/)
for schematics, [ngspice](https://ngspice.sourceforge.io/) for simulation, and
[KLayout](https://www.klayout.de/) — driven by
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — for layout.

**This block is designed by AI agents.** Not agent-assisted: agents pick the
topology, write the testbenches, run the corners, argue about the trade-offs in
decision records, and file the tool bugs they hit along the way. Every artifact
in this repository — the prior-art survey, the device characterization, the
simulation harness, the evidence records — was produced that way. The repo is
public so the work can be checked, not admired: every number here is traceable
to a testbench you can re-run.

## Status

Pre-tapeout. The analog core is drawn end to end — sub-block schematics, a
transistor-level netlist, a DRC-clean and LVS-matched block layout, and a
PVT-cornered verification suite that has been re-run in full against
post-layout extracted parasitics — but it is not a converged design, and as of
the DR-0019 CDAC unit-cap resize it is **less** converged than it was:

- **The resize closed one row and opened two.** DR-0019 (#177) resized
  `C_u` from 17.24 fF to 35.6528 fF to close the `Gain error, mismatch` row's
  2.12σ-vs-3σ gap, and #196 built it. Re-running the transistor-level suite at
  the built design (#197 and its sub-issues) finds the **ENOB row newly FAILS
  at 2 of its 9 corners** (worst 8.5064 bits against a `> 9.0` target, was
  9.163 and all-PASS) and the **SFDR row's pre-existing miss widens from
  0.67 dB to 5.59 dB** (worst 56.41 dB against `≥ 62 dB`). Reported, not
  fixed, and no target was moved to absorb it — the mechanism is tracked in
  **#211**. Power grows 13.4 % and still passes with 2.4× stretch margin;
  bit settling, the top-plate `C_par` divider, the `Gain error, systematic`
  row, static INL/DNL (worst \|INL\| 0.1036 → 0.1100 LSB, worst \|DNL\|
  0.1036 → 0.0938 LSB) and the input drive contract (which *improves*, to
  +0.082…+0.370 LSB) are unchanged or better. **The schematic re-verification
  is now complete**, and the last two decks it reached add a third flagged
  result: the sampling switch's *own* SFDR contribution
  (`sim/track-switch-thd/`, a distortion term linear in the array
  capacitance) loses 4.96–5.77 dB at all 117 corners and falls below the
  ratified 62 dB at 11 of them, where none did before — the first measured
  mechanism that moves the same way, and by the same size, as the end-to-end
  SFDR regression #211 owns.
- **The post-layout (extracted) side has now been re-taken too, and it does
  not rescue those two rows** (**#218**). The #202 layout was re-extracted at
  the resized unit cap (1024 MiM caps at `c_f = 35.6528 fF`, against 17.245 fF
  before) and all five extracted campaigns re-run against it. Because the
  extracted result is the one this repo reports as *governing* where both
  exist, that settles a row that had been left with **no** valid governing
  result: **SFDR measures 60.40 dB worst post-layout — a FAIL by 1.60 dB at 4
  of 9 corners** (its pre-resize extracted PASS of 64.38 dB described an array
  that is no longer drawn), and **ENOB 8.857 bits — a FAIL at 2 of 9**. Power
  passes at 246.5 µW (+11.6 %), `Gain error, systematic` improves to ~1047×
  inside its bound, and the Input-structure `R_on` re-take is an exact null.
  One row lands in between and is flagged rather than absorbed: post-layout
  static INL/DNL still passes the ratified `< 1 LSB` row but now misses the
  `< 0.5 LSB` stretch (0.528 / 0.728 LSB). Per-campaign before/after:
  [`sim/extracted-delta-summary.md`](sim/extracted-delta-summary.md) §4.12.
- **The candidate fix for the ENOB/SFDR regression is measured and NOT
  adopted (#238/#249).** #211 isolated the mechanism (an acquisition-RC-
  limited distortion that scales with the array capacitance,
  [`sim/dr0019-cu-sweep-findings.md`](sim/dr0019-cu-sweep-findings.md)) and
  found an orthogonal control — widening the CDAC cell's acquisition-leg
  T-gate 2.068× — that recovers 89–101 % of the loss in a schematic-level,
  125 °C-only probe, but deferred five measurements before that recovery
  could be read as achievable margin. All five have landed (#238): charge
  injection, top-plate `C_par`, and clock-driver power all cost little, but
  the fifth — a genuine `klt`-verified re-layout of the candidate width — grows
  `adc_block` area **+17.00 %** (150,536.239 → 176,126.8006 µm²), pushing it
  **+76.1 %** over the still-ratified `< 0.1 mm²` Area target and **+10.1 %**
  over even the still-unratified `< 0.16 mm²` relaxation proposed below to
  reconcile the *current* geometry. Adopting the candidate would not close
  the ENOB/SFDR FAILs without opening a worse one on Area, which `CLAUDE.md`'s
  "do not relax the ratified spec to make results pass" rules out — so the
  candidate is **not adopted**, `CDAC_SW_WN`/`CDAC_SW_WP` remain `10u`/`20u`,
  and the ENOB/SFDR rows stand as a recorded, unresolved regression:
  [DR-0025](spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md).
  The extracted ENOB/SFDR campaign was re-taken on a clean tree against the
  unchanged, ratified design and reproduces the same governing FAIL figures
  exactly (8.857 bits / 60.40 dB worst-corner):
  [`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](sim/adc-enob-fft/records/20260825-061750-d00911a.md),
  superseding the dirty-tree `20260817-215657-076d545`.
- A comparator-inclusive extraction's statistical offset campaign has not been
  run yet (the functional defect that used to block `ADC_BLOCK` outright is
  fixed, #118), and there has been no silicon:

| Area | State |
|---|---|
| Target spec | Ratified 2026-07-31 (table below) — `spec/decision-records/DR-0006-spec-ratification.md` |
| Prior-art survey | Done — `spec/prior-art-survey.md` |
| Simulation harness | Working — PVT corner runner over gf180mcu, with a self-test |
| Device characterization | Done — CDAC caps, sampling switches, comparator input devices |
| Full-ADC characterization (aggregated) | Current as of 2026-08-17, re-taken at DR-0019's resized `C_u` on **both** sides — all six `C_u`-dependent schematic campaigns (#197 and sub-issues #203/#204/#205) and, against a re-extraction of the #202 layout, all five extracted campaigns (#218) — [`sim/characterization-summary.md`](sim/characterization-summary.md), one row per ratified spec line with a dated citation; the consolidated before/after adjudication of the resize is [`spec/testbench-suite-memo.md`](spec/testbench-suite-memo.md) §11.9 (§11.9.8 for the extracted half) |
| Schematics | Sub-blocks captured (CDAC array, comparator, track switch) and assembled into a transistor-level analog-core netlist — `design/adc-top/`; SAR control logic at DR-0010's rung-1 ideal-logic abstraction, pending a 3.3 V standard-cell library in the open PDK — `design/sar-logic/README.md` |
| Layout | Block layout drawn, DRC-clean, LVS-matched: 323-device `adc_block` at 0.15054 mm² (`layout/adc-top/area.json`, cross-checked by `klt economy` at utilization 0.4146 — `layout/adc-top/economy/records/20260817-185745-40cfeb8.md`). That is after issue #215's two-step recovery — a load-resistor fold plus a re-derivation of both top-level strap corridors — took 29,910 µm² (−16.57 %) off the 0.18045 mm² the DR-0019 unit-cap resize built. Over the ratified `< 0.1 mm²` budget (151 %) once the CDAC MiM stack is drawn at its legal geometry (#70) and the ratified `C_u` at DR-0019's resized plate: recovery to `< 0.1 mm²` is infeasible at the ratified unit-cap geometry, so a target revision was proposed for operator ratification (`spec/decision-records/DR-0017-adc-top-area-budget-overrun.md`, itself predating DR-0019 and now itself superseded by a current reconciliation). That reconciliation, using the current as-built 0.150536 mm² figure rather than DR-0017's stale one, is [DR-0024](spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md) (`< 0.16 mm²`, proposed, issue #198, pending operator ratification-via-PR) — `layout/adc-top/README.md` |
| Verification suite | **At the DR-0019-resized `C_u` the design is built at (#196/#202): the schematic-level 9-corner ADC suite now has TWO failing rows, not one** — ENOB 8.5064 bits worst (`ss_125c_2.97v`), below the `> 9.0` target at 2 of 9 points, and SFDR 56.41 dB worst, missing `≥ 62 dB` by 5.59 dB; power passes at 207.9 µW (2.4× stretch margin), bit settling passes 117/117, `Gain error, systematic` improves to 0.0021–0.0039 LSB and the array-path `R_on` is bit-identical. Consolidated before/after: `spec/testbench-suite-memo.md` §11.9; regression tracked in #211. INL/DNL's re-take is **done** (#203/PR #214: worst \|INL\| 0.1036 → 0.1100 LSB, worst \|DNL\| 0.1036 → 0.0938 LSB, 63/63 PASS), and so are the two input-path decks PR #202 could not reach because they model the array as one lumped capacitor: the drive contract *improves* to +0.082…+0.370 LSB (117/117 PASS) while the switch's own track-mode SFDR contribution loses 4.96–5.77 dB everywhere and drops below the ratified 62 dB at 11 of 117 points (§11.9.11/§11.9.12). **Everything that follows in this cell describes the pre-resize design at `C_u = 17.24 fF` and is retained as the record of it, not as a current claim.** Schematic-level, 9-corner ADC suite at that `C_u`: INL/DNL and ENOB pass; SFDR misses the ≥ 62 dB target by 0.67 dB at one corner of nine — `spec/testbench-suite-memo.md` §11.2. Post-layout extracted re-run **done** (#17/#89): every #13 spec-line bench — static linearity (27-point `mos` grid plus a 63-point `cdac` capacitor-corner-set isolation), ENOB/FFT/SFDR (9-point grid), power (27-point grid), and the DR-0012/13 systematic gain-error row — re-run against the parasitic-extracted CDAC core, plus the #14 Monte Carlo question answered for both halves (MOS local mismatch measured, σ = 2.0e-3 LSB at the worst carry with a null control; CDAC capacitor mismatch absent from the PDK on either netlist). Every row that passed schematic-level still passes extracted. The three spec-line decks were then re-run again (#123) on the **in-path** extraction the `875eac3` toolchain pin ratifies — the earlier capture used a superseded topology whose parasitic resistance carried no device current — and independently replicated by a second concurrent campaign, agreeing to ≥ 4 significant figures on all 5904 static and dynamic result cells (the 675 FFT-capture cells bit-identically) and on 26 of 27 power corners: INL 0.148 LSB, DNL 0.098 LSB, ENOB 9.31 bits, power 185–221 µW at 4.5–5.4× margin, all PASS — §4.10/§4.11. On that basis no corner of the 9-point grid falls below the SFDR row (worst 64.38 dB, at `ff_125c_3.63v`). The schematic baseline still misses it at `ss_125c_2.97v` (61.33 dB) — confirmed **not stale** by a fresh re-run against current sources (#151) — but the extracted grid's own worst corner relocates away from `ss_125c_2.97v` (which measures 64.93 dB extracted, independently replicated twice), a real, corner-dependent effect of the in-path CDAC parasitics on the acquisition's own sampling-bow nonlinearity rather than a testbench artifact: #151 rules out both baseline staleness and a schematic/extracted deck-comparability gap directly (`spec/testbench-suite-memo.md` §11.2). SFDR's escalation was reconciled on that basis: the extracted, independently-replicated result governed the row for the design *as then laid out*, and it passed. **That reconciliation does not survive the DR-0019 resize.** The extracted grid above was taken on the pre-resize layout; #218 re-extracted the #202 layout and re-ran all five extracted campaigns against it, and the row's first valid post-resize governing result is a **FAIL at 60.40 dB worst** (`ff_125c_3.63v`, 4 of 9 corners short of `≥ 62 dB`), alongside a schematic side that fails by 5.59 dB — so the extracted result no longer rescues the row, it confirms the miss (`sim/extracted-delta-summary.md` §4.12.2). Two findings are carried open rather than absorbed: the 2× comparator-current excursion at one power corner (#107), which the two campaigns show does not reproduce run-to-run and is therefore a marginal-decision artefact rather than a corner or layout property (§4.11.1), and a comparator-inclusive (`ADC_BLOCK`) extraction, on which the comparator-offset claim (the ratified `Offset ≤ 2 LSB` 3σ-mismatch Monte Carlo population) still depends — `ADC_BLOCK` itself converts (issue #118) and a comparator-inclusive regeneration-margin campaign against it has run, but the statistical offset population has not. **Rate (1 MS/s) closure is no longer one of the open items**: as of issue #116 (2026-08-14) all three of its post-layout inputs are measured and the row is PASS — `sim/extracted-delta-summary.md` §6.3/§6.4, `sim/issue-17-acceptance-review.md`. A separate, non-layout finding surfaced by issue #172's `klt yield` evidence: at the historical `C_u = 17.24 fF` this design no longer draws, the Gain error, mismatch row measured **2.12σ against its ratified 3σ condition** (0.708 LSB at 3σ vs the ≤ 0.5 LSB target) — a sizing gap in README note **[e]**'s ceiling assumption, not a layout effect (`sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`, **superseded**, `spec/testbench-suite-memo.md` §12 item 8c); issue #177 records and verifies the resizing decision that closes it ([DR-0019](spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md), `sigma_to_spec = 3.13`), and the physical implementation landed in #196/PR #202. The transistor-level PVT re-verification tracked separately as #197 — **all eight** of its schematic campaigns are now done (§11.9; the census grew from six when the scope sentence turned up two input-path decks that model the array as a lumped capacitor and so were never regenerated), and the post-layout half is done too (#218, §11.9.8) — covers the *other* `C_u`-dependent rows, not this one: the `Gain error, mismatch` row's own evidence is the standalone Monte Carlo mismatch model, evaluated at nominal PVT rather than corner-swept, which #177 already re-ran at the resized `sigma_u` (`sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`). With the resize now physically built, that re-run is governing and the row above quotes it: **3.13σ, `klt yield` status `pass`**. What #197 measured is the *cost* of the resize on the other rows, and it is not free. **See [`sim/characterization-summary.md`](sim/characterization-summary.md) for the single, dated, per-spec-row characterization status this paragraph summarizes.** All of the above is this repo's own hand-built extracted-core re-simulation methodology; `klayout-tools`' own single-command schematic-vs-extracted tool for this (`klt pex`, epic #709) was tried directly once it shipped (#173) and found blocked for every block this repo extracts — its DUT-swap mechanism requires the schematic and extracted netlists to share one identical top-level pin interface, which `klt extract`'s promoted body/tap/internal nets never do here — filed generically as [`klayout-tools#1030`](https://github.com/2AMLogic/klayout-tools/issues/1030); evidence in `sim/comparator-pex/`, `sim/extracted-delta-summary.md` §9. **The ENOB/SFDR regression's one measured candidate fix (#211's acquisition-leg widening) has since been evaluated end to end (#238/#249) and is NOT adopted** — [DR-0025](spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md): items 1/2/4 of five deferred measurements cost little, but item 5's `klt`-verified re-layout grows `adc_block` area +17.00 %, past both the ratified and the still-proposed Area targets; the clean-tree re-take of the governing ENOB/SFDR campaign at the unchanged, ratified design reproduces the same 8.857 bits / 60.40 dB worst-corner FAIL exactly ([`20260825-061750-d00911a`](sim/adc-enob-fft/records/20260825-061750-d00911a.md)) |
| Silicon | None |

## Target specification

Ratified 2026-07-31 ([DR-0006](spec/decision-records/DR-0006-spec-ratification.md), issue #1).

| Parameter | Target | Stretch | Binding corner / condition |
|---|---|---|---|
| Resolution | 10 bit | 12 bit variant | — (architectural) — note **[h]** |
| Rate | 1 MS/s | 2 MS/s | Settling at `ss_125c_2.97v`; distortion re-checked at `ss_-40c_2.97v` — worst R_on flatness, 3.29× ([devchar §2.1](sim/device-characterization-report.md)) |
| ENOB @ Nyquist | > 9.0 (non-quantization budget σ_total ≤ 1.61 mV rms) | > 9.5 (≤ 0.930 mV rms) | Settling at `ss_125c_2.97v`; mismatch tail at 3σ Monte Carlo. Reference noise is **user-supplied** — allocated, not guaranteed by this block: note **[b]** |
| SFDR @ Nyquist | ≥ 62 dB | ≥ 65 dB | `ss_125c_2.97v` (schematic, **56.41 dB at DR-0019's built `C_u`** — was 61.33 dB pre-resize) / `ff_125c_3.63v` (extracted, **60.40 dB at the resized `C_u`, re-taken post-layout under #218 — governing, and a FAIL**; re-confirmed on a clean tree by [`20260825-061750-d00911a`](sim/adc-enob-fft/records/20260825-061750-d00911a.md), issue #249; the 64.38 dB this cell used to quote was pre-resize) — the pre-resize diagnosis was acquisition sampling-bow nonlinearity, not R_on-modulation ([testbench-suite-memo.md §11.2](spec/testbench-suite-memo.md), reconciled by #151) — **at the resized `C_u` that diagnosis no longer covers the shift**: the bow *improves* at 8 of 9 corners while SFDR degrades (§11.9.7), while the R_on-modulated tracking lag, which is linear in the array capacitance, loses 4.96–5.77 dB and puts the switch's own contribution below 62 dB at 11 of 117 points (§11.9.11, `sim/track-switch-thd/`). Both are the worst of the **125 °C-only** nine-point FFT grid (3 process × 3 supply), i.e. the worst of a temperature-degenerate subgrid — not a corner shown to beat the −40 °C R_on-modulation point ([devchar §2.1](sim/device-characterization-report.md)) this row previously named, which the full-grid static decks still sweep; margin derivation in note **[a]**. The one measured candidate fix (acquisition-leg widening) is evaluated and **not adopted** — [DR-0025](spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md), issue #249 |
| INL / DNL | < 1 LSB | < 0.5 LSB | 3σ Monte Carlo mismatch (**not** a PVT corner); **untrimmed and uncalibrated** — note **[d]** |
| Offset error | ≤ 2 LSB, untrimmed | — | 3σ mismatch (not a PVT corner); no analog trim, digitally removable — note **[e]** |
| Gain error, mismatch | ≤ 0.5 LSB, untrimmed, **excluding** V_REF error | — | 3σ mismatch (**not** a PVT corner); full scale is ratiometric to V_REF — note **[e]**. **Measured 3.13σ against this target as built** (`C_u = 35.6528 fF`, `sigma_to_spec = 3.13`, `klt yield` status `pass`), the resizing decision — [DR-0019](spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md), issue #177 — now **physically built** into the generators and layout (issue #196). This row's own evidence is a nominal-PVT mismatch model, not a corner sweep, so the resize's governing evidence applies directly; the **superseded pre-resize** figure was 2.12σ (0.708 LSB at 3σ, `klt yield` status `fail`, issue #172, historical `C_u = 17.24 fF`) — see note [e]'s update and [`sim/characterization-summary.md`](sim/characterization-summary.md) |
| Gain error, systematic | ≤ 0.5 LSB, untrimmed, **excluding** V_REF error | — | Full PVT grid, zero mismatch, at the specified input drive network ([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)); adds to the row above — note **[g]** |
| CMRR (differential mode) | ≥ 60 dB, DC–Nyquist, over V_CM = V_REF/2 ± 100 mV | ≥ 65 dB | 3σ mismatch; margin derivation in note **[a]** |
| Input | 0–V_REF single-ended, ±V_REF differential about V_CM = V_REF/2 — **requires V_REF ≤ V_DD**; external `C_pin` of 100 pF–1 nF per input pin to analog ground, and total series source resistance meeting `R_source × (C_pin + C_in) ≤ 30 ns` (≤ 250 Ω at C_pin = 100 pF; ≤ 25 Ω at 1 nF), single-ended and per differential pin ([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md), superseding DR-0001) | — (drive budget not resolved at 2 MS/s, see DR-0013) | `ss_125c_2.97v` (worst R_on). Full scale is **ratiometric to V_REF**, not a fixed 0–3.3 V range — note **[c]** |
| Input structure | Track-mode C_in = 18.254 pF per side (512 · C_u at [DR-0019](spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md)'s resized C_u = 35.6528 fF; [DR-0011 CDAC switching scheme](spec/decision-records/DR-0011-cdac-switching-scheme.md), #8); series switch R_on 21.3–60.0 Ω over PVT, nine parallel bottom-plate cell T-gates per side ([DR-0016](spec/decision-records/DR-0016-input-structure-ron-repoint.md)); T/H −3 dB bandwidth ≥ 5.3 MHz (≥ 10.6 × Nyquist), set by the input time-constant budget ([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)) | — | R_on range over the 27-point grid, worst `ss_125c_2.97v` ([`sim/dr0014-sampling/`](sim/dr0014-sampling/records/20260802-141402-1224e11.md)); hold droop 0.136 LSB @ `ff_125c_3.63v` is a **lower bound** — note **[f]** |
| Reference | V_REF = 3.3 V, external pin; external decoupling ≥ 40 nF; effective source impedance ≤ 240 Ω in the switching band ([DR-0002](spec/decision-records/DR-0002-reference-source.md)) | Z_ref ≈ ≤ 120 Ω @ 2 MS/s (bit cycle halves; explicitly unresolved, DR-0002) | Bit-cycle settling at `ss_125c_2.97v`; 240 Ω is a conservative floor #8 may relax, never tighten. Reference **noise** allocation: note **[b]** |
| Clock | External pin, 16 × f_s → 16 MHz @ 1 MS/s; aperture jitter ≤ 250 ps rms ([DR-0003](spec/decision-records/DR-0003-clocking.md)) | 32 MHz @ 2 MS/s; ≤ 180 ps rms | Jitter budget evaluated at f_in = 500 kHz (Nyquist) with 6 dB margin (DR-0003) |
| Supply | V_DD = 3.3 V ±10 % (2.97 / 3.30 / 3.63 V grid), single supply, 3.3 V devices throughout ([DR-0004](spec/decision-records/DR-0004-device-flavor.md)) | — | Every performance row holds across 2.97–3.63 V **subject to V_REF ≤ V_DD**; 3.3 V full scale therefore requires V_DD ≥ 3.3 V — note **[c]** |
| Latency / conversion timing | One-conversion latency, no pipeline; M = 16 clocks per conversion = 1 µs @ 1 MS/s | 0.5 µs @ 2 MS/s (32 MHz) | Deterministic: 4 sample + 10 bit-trial + 2 reset/output cycles (`spec/prior-art-survey.md` §1.4, [DR-0003](spec/decision-records/DR-0003-clocking.md)) |
| Power @ 1 MS/s | < 1 mW | < 500 µW | `ff_125c_3.63v` (fast, hot, high supply) |
| Area | < 0.1 mm² | — | — (layout-bound) |
| Interface | SPI-readable + parallel (parallel/output-register in scope for simulation-complete; SPI deferred, [DR-0005](spec/decision-records/DR-0005-interface-scope.md)) | — | — |

These are targets, not results. Nothing here has been measured in silicon.

**[a] The distortion and common-mode margins are derived, not asserted.** Both
use the same "keep it a minority term" convention as DR-0003's jitter budget.
SFDR ≥ required SNDR + 6 dB: `55.94 + 6 ≈ 62 dB` at the ENOB > 9.0 target,
`58.95 + 6 ≈ 65 dB` at the > 9.5 stretch (SNDR figures from
`spec/prior-art-survey.md` §1.1). CMRR: a 100 mV common-mode disturbance
attenuated by 60 dB contributes 100 µV, under a tenth of the 1.61 mV rms
non-quantization budget of §1.1; the stretch's 0.930 mV budget needs ≥ 61 dB by
the same arithmetic, rounded up to 65 dB.

**[b] Reference noise is user-supplied and is not guaranteed by this block — but
it is allocated, not ignored.** `V_REF` is an external pin
([DR-0002](spec/decision-records/DR-0002-reference-source.md)), so its noise is
outside this block's control. `spec/prior-art-survey.md` §1.1 splits the
non-quantization budget into three equal-power shares (sampling `kT/C`,
comparator, reference + distortion), which allocates the reference term
**≤ 0.93 mV rms** at the ENOB > 9.0 target and **≤ 0.537 mV rms** at the > 9.5
stretch. A `V_REF` source noisier than its allocation invalidates the ENOB
claim; the ENOB row is specified with a reference that meets it.

**[c] Full scale is ratiometric to V_REF, and V_REF ≤ V_DD is a hard
condition.** The draft table's fixed "0–3.3 V" input range and the ±10 % supply
grid could not both hold: the T-gate R_on measurement
([devchar §2.1](sim/device-characterization-report.md)) shows that at the
2.97 V corner a 3.3 V input sits 330 mV above the rail, forward-biases the PMOS
source-body junction, and measures a diode — **a full-scale 0–3.3 V input is
not samplable at a drooped 2.97 V supply.** Resolution: the input range is
0–`V_REF`, not 0–3.3 V, so a 3.3 V full scale requires `V_DD ≥ 3.3 V`, and at a
drooped supply the user must reduce `V_REF` with it (every LSB-referred row
scales accordingly). This does not conflict with the Power row: power binds at
the **high**-supply corner (`ff_125c_3.63v`, where `V_REF = 3.3 V ≤ V_DD` holds
comfortably), while the full-scale condition binds at the **low**-supply corner.

**[d] INL/DNL are untrimmed, uncalibrated targets.** No capacitor trim and no
digital error correction is assumed; a calibration scheme (#14) may buy margin
above these numbers, but is not required to meet them. The array is sized
against `A_C = 2.0 %·µm` — a 2×-derated planning placeholder that **has no
verified citation in this repo** and is pending GlobalFoundries' own MiM
matching data ([devchar §5.1](sim/device-characterization-report.md)); a 2×
error in `A_C` is a 3.6× error in array capacitance. Two further terms are
budgeted **inside** these numbers rather than outside them: the MiM voltage
coefficient at the ≤ 5 µm unit sizes a 10-bit array actually wants (−81 ppm/V
datasheet value → ≈ 0.27 LSB over a full 3.3 V swing if it applied uniformly,
which it does not — so it is a genuine linearity term; devchar §1.5, and the
PDK's own deck has the bias-dependent instance line commented out, so no
simulated result in this repo contains it), and switch charge injection **after
compensation** — the raw T-gate input-dependent pedestal spread is 4.4 LSB, so
bottom-plate sampling, a dummy switch or bootstrapping is mandatory, not
optional (devchar §2.2). **Only part of that pedestal spread lands here**
([DR-0012](spec/decision-records/DR-0012-gain-error-deterministic-vs-mismatch.md)):
the spread is a term *linear* in `V_in` plus a residual, INL is evaluated
after offset and gain are removed, and the linear part is therefore budgeted
in the Gain error, systematic row rather than in these numbers. What lands in
INL/DNL is the endpoint-fit residual — measured 0.013–0.197 LSB for the
ratified switch and drive network
([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)).

**[e] Offset is bounded and digitally removable; gain is ratiometric to V_REF.**
No analog trim is in scope. Untrimmed offset is dominated by comparator
input-pair threshold mismatch: the measured `A_Vt = 7.208 mV·µm` gives
`σ(ΔV_th) = 1.92 mV` at the candidate 40/0.5 µm pair, i.e. 5.8 mV = **1.8 LSB**
at 3σ ([devchar §3.3](sim/device-characterization-report.md)) — which sets the
≤ 2 LSB bound and makes comparator offset cancellation (#9) a design
requirement rather than an option. A static offset consumes no INL/DNL or ENOB
budget and is removable by the user as a constant code subtraction; that is the
offset-handling policy, in place of a trim. Gain: full scale ≡ `V_REF` by
construction, so absolute gain accuracy is the accuracy of the user's reference
and is **excluded** from this spec. The on-chip term is the 3σ spread of the
total array — `3 × 0.52 % / √1024 = 0.049 %` of full scale = 0.5 LSB, using
§5.1's binding per-unit requirement `σ_u ≤ 0.52 %` — and a die-global
capacitance shift cancels exactly in the array ratio, contributing nothing
(devchar §5.1). **That derivation covers the Gain error, mismatch row only**:
it is one mechanism, and the row's value equals it, so there is no headroom in
it for a deterministic term. The deterministic, PVT-cornered part of gain error
is budgeted separately in note **[g]**
([DR-0012](spec/decision-records/DR-0012-gain-error-deterministic-vs-mismatch.md)).

**Update (issue #172, 2026-08-16): measured, and short of this derivation's own
3σ target.** The `3 × 0.52 % / √1024 = 0.049 %` derivation above uses devchar
§5.1's *ceiling* requirement `σ_u ≤ 0.52 %`, not the chosen design's actual
calibrated value. `sim/mc-cdac-mismatch/`'s `klt yield` evidence
(`sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`, N = 20 000, a
negative control at 3× `σ_u` correctly detected) measures the built design's
`σ_u = 0.7372 %` ([`spec/monte-carlo-methodology-memo.md`](spec/monte-carlo-methodology-memo.md)'s
`A_C/√A_unit`), which DR-0011's split-topology DNL relief (note [d]'s `√511`
benefit) does not reach, because gain error is a total-array-capacitance sum.
Substituting the measured `σ_u` into this note's own formula reproduces the
finding to within 0.3 %: **2.12σ at the ratified 3σ condition — 0.708 LSB
against the ≤ 0.5 LSB target, `klt yield` status `fail`.** No spec value is
relaxed and no testbench is retuned per CLAUDE.md; the resizing decision that
would close this gap is issue #177. Full evidence trail:
`spec/testbench-suite-memo.md` §12 item 8c,
[`sim/characterization-summary.md`](sim/characterization-summary.md).

**Update (issue #177, 2026-08-16; currency-corrected issue #239,
2026-08-24): resizing decision made and verified; generators and layout now
built at the resized `C_u` (issue #196).** This row's own governing evidence
is the resize's re-run itself (below), not the broader transistor-level PVT
suite (issue #197), which covers the *other* `C_u`-dependent rows — this row
is a nominal-PVT mismatch quantity, not a corner sweep, so it needs no PVT
re-verification of its own. `spec/cdac-sizing-memo.md` §3.6
re-derives the gain-error requirement directly (`σ(gain error) = 32·σ_u`,
tighter than DNL/INL's `22.61·σ_u`/`11.31·σ_u` by up to `2√2`) and finds `C_u`
was sized against the wrong (DNL) coefficient. Resizing the unit cap to
`C_u = 35.6528 fF` (4.0 µm square, `σ_u = 0.5000 %`,
[DR-0019](spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md))
clears the row with real margin — `klt yield` `status: pass`,
`sigma_to_spec = 3.13`
([`sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`](sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md)) —
and DNL/INL are re-confirmed (not merely assumed) to still clear their own
stretch target at the resized `σ_u`. **The resize is now physically built
(issue #196)**: `design/adc-top/gen_adc_top.py` (`C_UNIT_FF = 35.6528`) and
`layout/adc-top/` (4.0 µm plate, 6.4 µm array pitch) carry it, `klt drc` and
`klt lvs` are clean at the new geometry, and the regenerated netlist and
testbench decks publish `C_in = 18.254 pF`. **The "measured 2.12σ" verdict in
the row above has since been superseded**: the 3.13σ figure here is the
standalone behavioural mismatch model — the row's own evidence, which DR-0019
decided on, evaluated at nominal PVT rather than corner-swept — and with the
resize now physically built, this re-run is the row's governing, standing
result. The 2.12σ figure is retained as history of the historical
`C_u = 17.24 fF` design this repo no longer draws, not as a current
measurement. The full transistor-level PVT re-verification suite at the new
`C_u` is tracked separately as issue #197 and covers the *other*
`C_u`-dependent rows, not this one; its **eight** schematic campaigns have
now all been re-run. **What
they found is not free**: the ENOB row newly fails at 2 of 9 corners, the
SFDR miss widens from 0.67 dB to 5.59 dB (#211) and the sampling switch's own
SFDR contribution falls below 62 dB at 11 of 117 points, while power grows
13.4 % and still passes, settling and static INL/DNL do not move, and the
`Gain error, systematic` row, the top-plate divider and the input drive
contract *improve*. The post-layout side has since been re-extracted and re-run in
full (#218): it does not rescue ENOB or SFDR — 8.857 bits and 60.40 dB worst,
both FAIL — while power, the systematic gain-error row and the switch `R_on`
row hold. Consolidated before/after with
re-derivation commands: [`spec/testbench-suite-memo.md`](spec/testbench-suite-memo.md) §11.9. DR-0019 also quantifies
the resize's real area cost (+16.8 % over the current `adc_block` baseline,
re-runnable via `layout/adc-top/area_feasibility.py`) against the
already-pending DR-0017 area situation — surfaced, not absorbed, and later
reconciled by [DR-0024](spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md).
It further
establishes that the unit cap is bounded from **above** by DR-0013's ratified
drive contract (`C_in = C_side` enters `R_source × (C_pin + C_in) ≤ 30 ns`
directly): the usable window is `3.840 µm ≤ s ≤ 4.1975 µm`, and at the chosen
`s = 4.0 µm` the contract still holds with 1.5 % of headroom
(`spec/cdac-sizing-memo.md` §5.5). The Input-structure row's published `C_in`
has accordingly moved from `8.827 pF` to `18.254 pF` with this build. The
remaining half of DR-0019's Consequences — re-running the full transistor-level
PVT verification suite at the new `C_u` (issue #197 at the
schematic level and #218 for the post-layout half — both now done) and reconciling
the resize's area growth against DR-0017's budget (issue #198,
[DR-0024](spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md),
proposed, pending operator ratification-via-PR) — is tracked under issue #190.

**[f] The Input-structure row publishes the load side of DR-0013's drive
contract**, without which that source-impedance requirement is not auditable by
a user. T/H bandwidth is `derived` from the same time-constant budget the Input
row states: `τ_in = R_source × (C_pin + C_in) ≤ 30 ns` →
`f_−3dB ≥ 1/(2π × 30 ns) = 5.3 MHz`, ≥ 10.6× Nyquist. That bandwidth is a
function of the 30 ns budget alone, so it does **not** move with `C_in` and is
unchanged by DR-0019's resize (`spec/cdac-sizing-memo.md` §5.5). It is *lower*
than the ~17 MHz the bare 500 Ω network of
[DR-0001](spec/decision-records/DR-0001-input-drive.md) gave against the
pre-resize 8.827 pF array, and the loss is
deliberate: the pin capacitor that costs it is what pins the sampling switch's
turn-off charge split, without which the Gain error, systematic row cannot be
met at all ([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)).
`C_in` is 18.254 pF per side — 512 · `C_u` at DR-0019's resized
`C_u = 35.6528 fF`, built in issue #196 — superseding #8's pre-resize
8.827 pF, which had itself replaced the 34 pF planning value this row
previously carried. The R_on and hold-droop figures in this row's evidence
column were measured at the pre-resize array and have not been re-taken at the
new `C_u` (issue #197); `R_on` is a switch property and does not move with
`C_in`, but the acquisition time constant `R_on · C_in` roughly doubles
(`spec/cdac-sizing-memo.md` §5.5, "Not yet re-measured").
Hold droop of 0.136 LSB at `ff_125c_3.63v` (438 µV on the 2.5 pF
measurement array, [devchar §2.3](sim/device-characterization-report.md)) is a
**lower bound**: the gf180mcu FET cards carry no junction saturation-current
density, so every leakage figure in this repo is channel leakage only
(devchar §5.2) — junction leakage must be budgeted from foundry data.

**[g] Gain error has a deterministic half, and it is specified separately
rather than folded into the mismatch row.** The sampling switch's turn-off
charge injection is input-dependent, so it adds a term linear in `V_in` — a
gain error — that is identical on every die and moves only with process,
voltage and temperature. It is not a 3σ-mismatch quantity, so note **[e]**'s
derivation (which *equals* the array-mismatch term, with no headroom in it)
does not bound it; and it is not removed by the endpoint fit that INL is
evaluated against, so note **[d]** does not bound it either
([DR-0012](spec/decision-records/DR-0012-gain-error-deterministic-vs-mismatch.md)).
The target is set equal to the mismatch row's rather than looser, because a
deterministic term allowed to exceed the statistical one would make the
headline gain figure dominated by the mechanism the headline does not name;
the two are separate rows because they are separate mechanisms measured by
separate methods (a corner grid and a Monte Carlo run), and **they add — the
worst-case total gain error a user measures is ≤ 1.0 LSB**, 0.098 % of full
scale. Measured contribution of the input sampling switch, full 117-point PVT
grid at the [DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)
drive network, across both ends of the permitted `C_pin` range and the whole
permitted source impedance: **+0.082 … +0.370 LSB** (worst `ff_125c_3.63v`,
`sim/track-switch-sampling/records/20260817-142951-72d15de.md`), re-measured at
DR-0019's resized array (`C_in` = 18.254 pF). It was **−0.293 … +0.421 LSB** at
the pre-resize 8.827 pF array: a turn-off pedestal is `Q_inj/C_hold`, so
doubling the array divides this contribution by the same factor
(`spec/testbench-suite-memo.md` §11.9.12). This row is only verifiable with that drive
network specified — the same switch on a bare source measures −0.14 to
+2.80 LSB depending on nothing but the user's source impedance (it was −0.49 to
+5.38 LSB at the pre-resize array; the whole spread halves for the same
`Q_inj/C_hold` reason, and still spans more than five times the row's budget),
which is why DR-0013 makes the pin capacitor part of the contract.

**[h] Resolution is 10-bit as ratified; "8-bit" describes a reduced-precision
use case, not a different variant of this design.** The implemented,
verified, and ratified resolution of this converter is **10 bits**
([DR-0006](spec/decision-records/DR-0006-spec-ratification.md)); nothing in
this repository designs, verifies, or lays out an 8-bit variant. Where an
external listing of this block describes it as "8-bit," that is describing a
**use-case-adequate precision floor**, not the implemented resolution: 8 bits
is enough for supply-rail monitoring, coarse temperature gauging, or
threshold/comparator-class detection (≈ 20 mV/LSB on a generic 5 V rail; on
this converter's own `V_REF = 3.3 V` full scale that is 3.3 V / 256 ≈
12.9 mV/LSB at 8 bits, against 3.3 V / 1024 ≈ 3.22 mV/LSB at the ratified 10
bits). A user who only needs that coarser precision can take the top 8 bits
of this converter's 10-bit output directly — no separate design, mode, or
truncation logic is required or provided by this block; the conversion
result is simply read at reduced precision by the consumer. This block does
not offer, and is not verified as, a lower-resolution operating mode with its
own (faster or lower-power) timing — see the "Multi-channel / mux
integration" section below for what building a dedicated fast/coarse path
would cost.

## Multi-channel / mux integration

This ADC is a **single-channel** converter — one input pair, one CDAC array,
sampled and converted end to end by the timing DR-0003 ratifies. It is not a
muxed, multi-channel front end, and building one is out of scope for this
repository's deliverable: [DR-0020](spec/decision-records/DR-0020-mux-variant-and-fast-comparator-scope.md)
records that decision and its cost analysis in full; summarized here:

- **N-channel input mux**: not designed, verified, or laid out. Adding one
  costs area (N series switches at the existing input T-gates' R_on/settling
  class, [DR-0016](spec/decision-records/DR-0016-input-structure-ron-repoint.md),
  plus channel-select decode — on top of a block already over its
  `< 0.1 mm²` target, a reconciliation pending operator ratification
  ([DR-0024](spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md),
  superseding [DR-0017](spec/decision-records/DR-0017-adc-top-area-budget-overrun.md))),
  speed (each channel's own track-mode RC ahead of the existing 30 ns input
  time-constant budget, [DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)),
  and an as-yet-undefined **channel-to-channel crosstalk spec** — no
  isolation testbench exists, and per CLAUDE.md's "no claim without a
  testbench" rule none is asserted here.
- **Comparator-only fast threshold-detect path**: not a documented mode of
  this block. The comparator ([DR-0015](spec/decision-records/DR-0015-comparator-topology.md))
  is a sequential decision element clocked by, and consumed only by, the SAR
  sequencer — it is not brought out as an independently triggerable fast
  comparator, and its tier-0 offset cancellation is verified only for the
  SAR's own multi-strobe-per-conversion use pattern.
- **Analog-OCP-comparator use is explicitly out of scope for this block.** A
  continuous, asynchronous over-current-protection-class threshold detector
  is a different circuit with a different verification burden (continuous-
  time bandwidth and propagation delay, no SAR-cycle amortization) than
  anything designed or verified here. It belongs with whichever block
  switches the current being protected (for example a gate-driver-class
  block such as `2AMLogic/gf180-gate-driver`) or as its own standalone
  comparator IP — not as a repurposed tap of this ADC's internal comparator.
- **What is achievable without new design work on this repository's part**:
  a system-level analog mux **external** to this ADC, sized and
  characterized by the integrator, feeding the single input pair this block
  already specifies (the Input row, above). A multi-channel or fast-path
  *variant* of this block, if wanted, needs its own decision record, its own
  crosstalk/propagation-delay testbenches, and its own area/timing budget.

## Integration on a noisy, mixed-signal-with-power substrate

The verification suite behind every dynamic-performance row in the target
spec above (ENOB, SFDR, CMRR) assumes a **quiet, external, filtered** supply
and reference — [DR-0002](spec/decision-records/DR-0002-reference-source.md)'s
`V_REF` terms (≥ 40 nF decoupling, ≤ 240 Ω effective source impedance) and
[DR-0004](spec/decision-records/DR-0004-device-flavor.md)'s single 3.3 V
supply — with **no on-die switching-power aggressor modeled against any of
them.** [DR-0021](spec/decision-records/DR-0021-noisy-substrate-integration-assumptions.md)
records the following as explicit integration assumptions, each with its
evidence tier, for a user who wants to place this ADC on a die that also
carries switching power/driver structures:

- **Guard-ring / DNW guidance** — evidence tier: **design guidance, not
  testbench-verified.** `layout/adc-top/README.md` §2.4 already draws one
  contacted body-tie guard ring (`Comp`/`Contact`/`Metal1`) around the whole
  analog core plus a separately-ringed 20 µm gap around the reserved
  SAR-logic region, but that ring addresses **intra-block** digital/analog
  isolation, not coupling from an external switching-power aggressor. Adding
  a deep n-well (DNW) tub around the CDAC array, comparator, and input
  switches, tied to a dedicated quiet analog well/substrate contact separate
  from any switching-power ground return, is standard mixed-signal practice
  when the two share a die — but this repository has not drawn, DRC/LVS'd,
  or extracted a DNW-isolated variant, and no `sim/` evidence measures
  substrate coupling from a switching aggressor into this block.
- **Supply / reference isolation** — evidence tier: **derived from ratified
  rows, not independently tested against an aggressor.** `V_DD` and `V_REF`
  must each remain independent, filtered, external pins meeting DR-0002's
  terms with no coupled switching-power noise; sharing a rail or a return
  path with a switching-power driver directly violates that source model and
  invalidates every dynamic-performance row until re-verified with the
  aggressor present, which this repository has not done.
- **Timing assumption: sample outside switching edges** — evidence tier:
  **architectural, not testbench-verified against an aggressor.** This
  block's conversion timing (M = 16 clocks/conversion,
  [DR-0003](spec/decision-records/DR-0003-clocking.md)) has no
  synchronization interface to an external switching-power event; an
  integrator is responsible for scheduling the sample phase to avoid the
  aggressor's switching edges. The aperture-jitter budget and the sampling
  switch's own SFDR contribution (`sim/track-switch-thd/`) both assume a
  quiet sampling instant and have not been characterized against an injected
  switching transient.

No ratified target-spec value changes as a result of this section — the
conditions the existing rows were verified under are now stated explicitly
rather than left implicit.

## Verification is the product

The rule this repository is built around: **no claim without a testbench.**

- Every recorded result carries its PVT corners, its netlist provenance, and
  the toolchain versions that produced it.
- `sim/` is **append-only evidence**. Records are never edited or deleted; a
  superseded result is superseded by a new record that says so.
- The harness refuses to run when the toolchain drifts from its pinned
  versions, so a record cannot silently mean something different than it did
  last week.

The record format is documented in [`sim/README.md`](sim/README.md).

## Friction protocol

This block is also a forcing function for its own tooling. Every time
`klayout-tools` is awkward, missing a capability, or simply wrong for the job
at hand, that becomes an issue on the public tracker:

**[github.com/2AMLogic/klayout-tools/issues](https://github.com/2AMLogic/klayout-tools/issues)**

Friction issues describe the *tool gap* generically, not this design — so the
tool improves for everyone using the open gf180mcu flow, not just for us.

**Scope decisions (issue #7).** Five scope questions the draft table left
open are now resolved with decision records in `spec/decision-records/`
(all `ratified` on 2026-07-31 with the table itself, per #1 and
[DR-0006](spec/decision-records/DR-0006-spec-ratification.md)):

- Input drive: [DR-0001](spec/decision-records/DR-0001-input-drive.md) — external driver required, ≤ 500 Ω source impedance, 1 MS/s only. **Superseded by [DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)** (#39), which keeps the external-driver requirement and restates the source-impedance limit as a time-constant budget against a required per-pin capacitor.
- Reference source: [DR-0002](spec/decision-records/DR-0002-reference-source.md) — external `V_REF` pin (3.3 V), not internal/bandgap-derived; now the Reference row above.
- Clocking: [DR-0003](spec/decision-records/DR-0003-clocking.md) — external clock pin, 16 MHz @ 1 MS/s (32 MHz @ 2 MS/s stretch), ≤ 250 ps rms aperture jitter; now the Clock row above.
- Device flavor: [DR-0004](spec/decision-records/DR-0004-device-flavor.md) — 3.3 V devices throughout (`nfet_03v3`/`pfet_03v3`), single supply, no level shifters; the device choice is an implementation detail, but its supply and ±10 % tolerance are now the Supply row above.
- Interface scope: [DR-0005](spec/decision-records/DR-0005-interface-scope.md) — parallel output register in scope for simulation-complete, SPI deferred to a later maturity rung.

**Later scope clarifications (issue #226, 2026-08-17).** Two more scope
questions, raised by a chip-level integration exercise, are now resolved:

- Multi-channel / mux variant and comparator-only fast-path:
  [DR-0020](spec/decision-records/DR-0020-mux-variant-and-fast-comparator-scope.md)
  — both out of scope for this block; see "Multi-channel / mux integration" above.
- Noisy-substrate integration assumptions:
  [DR-0021](spec/decision-records/DR-0021-noisy-substrate-integration-assumptions.md)
  — guard-ring/DNW guidance, supply/reference isolation, and sampling-timing
  assumptions for a die shared with switching power structures, each with its
  evidence tier; see "Integration on a noisy, mixed-signal-with-power
  substrate" above.

## Chipalooza

This block is the program's Phase-1 entry for its block class in Open
Circuit Design's [Chipalooza Challenge #3](https://opencircuitdesign.com/chipalooza/challenge-3.html)
(GF180MCU test chip fabricated through Wafer.Space, proposal due 2026-08-31).
The submission-ready proposal — I/O list mapped onto the Challenge's pad
budget, a target-specification table re-derived from this repository's own
`sim/` evidence at the Challenge's rails, a test-plan outline for the
packaged part, and every currently-unmet row stated plainly rather than
absorbed — is [`docs/chipalooza/challenge-3-proposal.md`](docs/chipalooza/challenge-3-proposal.md).

## Repository layout

```
spec/          target spec, prior-art survey, decision records
design/        schematics / netlists (xschem)
sim/           testbenches, PVT corner harness, append-only result records
layout/        GDS + DRC/LVS flow and reports (klayout-tools driven);
               layout/adc-top/ is the drawn block
measurements/  silicon characterization (empty until tape-out)
docs/          environment bootstrap
```

## Running the simulations

```bash
# one-time environment bootstrap: docs/environment-setup.md
source sim/env.sh                            # export the resolved gf180mcu PDK
python3 sim/run_corners.py --check-env       # ngspice + PDK present?
python3 sim/run_corners.py --list            # available experiments and corners
python3 sim/run_corners.py <experiment>      # sweep the PVT grid, mint a record
bash sim/selftest.sh                         # prove the harness (and its corner
                                             # switching) actually works
```

### Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the headless half of
the above on every push and pull request: `sim/selftest.sh` stage 1 (the harness
unit tests), plus shell and Python syntax checks. It installs no PDK.

```bash
npm run check:ci    # exactly what CI runs — no ngspice, no PDK, seconds
npm run check:all   # the full sim/selftest.sh — needs ngspice + gf180mcu
npm run check:pdk   # what the nightly PDK workflow runs (--require-pdk: a
                    # missing PDK fails instead of skipping the sim stages)
```

`sim/selftest.sh` stages 2–4 (toolchain pin check, end-to-end PVT sweeps, and
the sabotaged-corner negative control) need a real PDK, so they run in
[`.github/workflows/nightly-pdk.yml`](.github/workflows/nightly-pdk.yml)
instead: nightly on a schedule, on demand, or on a pull request labelled
`ci:pdk`. That workflow builds the pinned ngspice and caches the gf180mcu
install at the pinned `open_pdks` hash, both keyed on
[`sim/toolchain.json`](sim/toolchain.json) — a pin bump re-installs rather than
reusing a stale cache. A nightly failure files (or comments on) a GitHub issue
rather than only turning the run red; a stage-4 regression — a *sabotaged*
corner sweep passing, meaning corner switching is not taking effect — is
escalated as urgent. Run stages 2–4 locally too, before recording evidence.

Neither workflow ever writes evidence: CI runs `sim/selftest.sh` without
`--record`, and asserts the working tree is unchanged afterwards. The workflow
files enumerate every self-check in the repo and where each one runs; keep that
list current when adding a check.

- [`docs/environment-setup.md`](docs/environment-setup.md) — xschem + ngspice +
  gf180mcu install, with pinned versions.
- [`sim/harness/README.md`](sim/harness/README.md) — corner runner reference:
  corners, testbench manifests, corner-sensitivity guarantees.
- [`sim/README.md`](sim/README.md) — the append-only evidence-record format
  every run writes into.
- [`sim/device-characterization-report.md`](sim/device-characterization-report.md)
  — measured-in-simulation **device**-level data (CDAC caps, switches,
  comparator input pair), with per-number provenance.
- [`sim/characterization-summary.md`](sim/characterization-summary.md) — the
  single, dated, aggregated **full-ADC** characterization artifact: every
  ratified target-spec row's latest verified value, verdict, and citation to
  its source record, superseding the need to cross-reference `README.md`,
  `spec/testbench-suite-memo.md`, `sim/extracted-delta-summary.md` and
  `sim/issue-17-acceptance-review.md` by hand.

## License

[Apache-2.0](LICENSE).
