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

Pre-tapeout, and not a converged design: no silicon, and several ratified
spec rows are failing or unmeasured (table below). The block is graded against
the [design-evidence ladder](signoff/README.md) by `klt signoff`; as of record
<!-- signoff:current-record -->
`20261009-170226-b6ca4338` the verdict is <!-- status:summary-begin -->
**`tier: none`**, **8 of 22 T1 evidence-checklist items met**
<!-- status:summary-end -->
([`signoff/README.md`](signoff/README.md)). Those counts grade whether
evidence exists and is fresh; they are **not** a count of passing
specification rows. Performance verdicts come from the per-spec-row table in
[`sim/characterization-summary.md`](sim/characterization-summary.md), which
also carries the PVT coverage, provenance and freshness limits (including its
dated full re-read and later partial updates) that this summary does not
repeat.

Spec rows that currently FAIL, are unmeasured, or pass only with a missed
stretch target, as listed by that summary's verdict column
(`sim/tools/check_readme_status.py` re-derives this set and fails on drift;
selection rule: a row whose verdict opens with **FAIL** or **Not measured**,
or whose verdict says its stretch target is still missed):

<!-- status:spec-rows-begin -->
| Spec row | Class | Governing value (worst corner) | Coverage limit |
|---|---|---|---|
| ENOB @ Nyquist | FAIL | 8.855 bits extracted (`tt_125c_3.63v`) against `> 9.0`; below target at 2 of 9 corners (schematic: 8.5064 bits) | 125 C-only 9-point FFT grid (3 process x 3 supply); post-layout extracted result governs. -40/27 C still unmeasured: the #430 27-point campaign was attempted and blocked on the batch fleet, 0 of 18 missing points completed ([attempt note](sim/adc-enob-fft/investigations/20261008-issue-430-temperature-coverage-attempt.md)) |
| SFDR @ Nyquist | FAIL | 60.41 dB extracted (`ff_125c_2.97v`) against `>= 62 dB`; short at 4 of 9 corners (schematic: 56.41 dB) | Same 125 C-only 9-point grid (-40/27 C unmeasured, see ENOB row); candidate fix not adopted ([DR-0025](spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md)) |
| Area | FAIL | 0.151827 mm^2 against the ratified `< 0.1 mm^2` (`layout/adc-top/area.json`); a `< 0.16 mm^2` revision is proposed, not ratified ([DR-0024](spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md)) | Single as-built layout figure, not a corner sweep |
| Offset error | Unmeasured | No comparator-inclusive (`ADC_BLOCK`) 3-sigma statistical population; comparator-only and deterministic extracted-core results clear the bound | Comparator-only `klt yield` at N = 150 is a sample-size artifact, not a 3-sigma claim |
| INL / DNL | PASS, stretch missed | Extracted worst \|INL\| 0.5175 LSB / \|DNL\| 0.6812 LSB: inside `< 1 LSB`, outside the `< 0.5 LSB` stretch | 27-point extracted grid; schematic 63/63 PASS |
<!-- status:spec-rows-end -->

Relocated history: the long DR-0019-era narrative that used to open this
section is kept verbatim, with a link reference map, in
[`docs/status-history-2026-10-08.md`](docs/status-history-2026-10-08.md). It
is a dated snapshot, not a current claim.

| Area | State |
|---|---|
| Target spec | Ratified 2026-07-31 (table below) — `spec/decision-records/DR-0006-spec-ratification.md` |
| Prior-art survey | Done — `spec/prior-art-survey.md` |
| Simulation harness | Working — PVT corner runner over gf180mcu, with a self-test |
| Device characterization | Done — CDAC caps, sampling switches, comparator input devices |
| Full-ADC characterization (aggregated) | Current as of 2026-08-17, re-taken at DR-0019's resized `C_u` on **both** sides — all six `C_u`-dependent schematic campaigns (#197 and sub-issues #203/#204/#205) and, against a re-extraction of the #202 layout, all five extracted campaigns (#218) — [`sim/characterization-summary.md`](sim/characterization-summary.md), one row per ratified spec line with a dated citation; the consolidated before/after adjudication of the resize is [`spec/testbench-suite-memo.md`](spec/testbench-suite-memo.md) §11.9 (§11.9.8 for the extracted half) |
| Schematics | Captured and assembled: CDAC, comparator and track switch in a transistor-level analog-core netlist (`design/adc-top/`). SAR logic: DR-0023 RTL synthesized, equivalence-checked; standalone routed macro (`layout/adc-top/sar_ctrl/`), STA setup/hold PASS at 5 corners ([record](design/sar-logic/flow/sar_ctrl/records/20260915-093934-7ab8971.mcu7t5v0.sta_postroute.md): no SPEF, ideal clock). Not done: LVS, integration, gate-level replay (`design/sar-logic/rtl/README.md`). Dated history: [`docs/status-history-2026-10-08-state-table.md`](docs/status-history-2026-10-08-state-table.md) |
| Layout | Drawn, DRC-clean, LVS-matched: 323-device `adc_block` at 0.151827 mm² (`layout/adc-top/area.json`, machine-checked), over the ratified `< 0.1 mm²` budget; a `< 0.16 mm²` revision is proposed, not ratified ([DR-0024](spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md)). Details: [`layout/adc-top/README.md`](layout/adc-top/README.md); dated history: [`docs/status-history-2026-10-08-state-table.md`](docs/status-history-2026-10-08-state-table.md) |
| Verification suite | Post-resize (DR-0019) re-takes are done; two rows fail: ENOB 8.855 bits worst against `> 9.0` and SFDR 60.41 dB worst against `>= 62 dB` (extracted, 9-corner grid); other rows per [`sim/characterization-summary.md`](sim/characterization-summary.md), the dated per-spec-row status. Pre-resize and issue-by-issue narrative is retained, not current: [`docs/status-history-2026-10-08-state-table.md`](docs/status-history-2026-10-08-state-table.md) |
| Silicon | None |

## Target specification

Ratified 2026-07-31 ([DR-0006](spec/decision-records/DR-0006-spec-ratification.md), issue #1).

| Parameter | Target | Stretch | Binding corner / condition |
|---|---|---|---|
| Resolution | 10 bit | 12 bit variant | — (architectural) — note **[h]** |
| Rate | 1 MS/s | 2 MS/s | Settling at `ss_125c_2.97v`; distortion re-checked at `ss_-40c_2.97v` — worst R_on flatness, 3.29× ([devchar §2.1](sim/device-characterization-report.md)) |
| ENOB @ Nyquist | > 9.0 (non-quantization budget σ_total ≤ 1.61 mV rms) | > 9.5 (≤ 0.930 mV rms) | Settling at `ss_125c_2.97v`; mismatch tail at 3σ Monte Carlo. Reference noise is **user-supplied** — allocated, not guaranteed by this block: note **[b]** |
| SFDR @ Nyquist | ≥ 62 dB | ≥ 65 dB | `ff_125c_3.63v` (extracted): **60.40 dB at the resized `C_u`** (re-taken post-layout, #218) — governing, and a **FAIL**; schematic `ss_125c_2.97v`: 56.41 dB. Worst of the 125 °C-only nine-point FFT grid. Margin: note **[a]**. Fix not adopted: [DR-0025](spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md). Diagnosis history: [memo §14.1](spec/testbench-suite-memo.md) |
| INL / DNL | < 1 LSB | < 0.5 LSB | 3σ Monte Carlo mismatch (**not** a PVT corner); **untrimmed and uncalibrated** — note **[d]** |
| Offset error | ≤ 2 LSB, untrimmed | — | 3σ mismatch (not a PVT corner); no analog trim, digitally removable — note **[e]** |
| Gain error, mismatch | ≤ 0.5 LSB, untrimmed, **excluding** V_REF error | — | 3σ mismatch (**not** a PVT corner); ratiometric to V_REF — note **[e]**. **Measured 3.13σ** as built (`C_u = 35.6528 fF`, `klt yield` status `pass`), after [DR-0019](spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md); the superseded pre-resize figure was 2.12σ. Details: [memo §14.2](spec/testbench-suite-memo.md), [`sim/characterization-summary.md`](sim/characterization-summary.md) |
| Gain error, systematic | ≤ 0.5 LSB, untrimmed, **excluding** V_REF error | — | Full PVT grid, zero mismatch, at the specified input drive network ([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md)); adds to the row above — note **[g]** |
| CMRR (differential mode) | ≥ 60 dB, DC–Nyquist, over V_CM = V_REF/2 ± 100 mV | ≥ 65 dB | 3σ mismatch; margin derivation in note **[a]** |
| Input | 0–V_REF single-ended, ±V_REF differential about V_CM = V_REF/2 — **requires V_REF ≤ V_DD**; external `C_pin` of 100 pF–1 nF per input pin to analog ground, and total series source resistance meeting `R_source × (C_pin + C_in) ≤ 30 ns` (≤ 250 Ω at C_pin = 100 pF; ≤ 25 Ω at 1 nF), single-ended and per differential pin ([DR-0013](spec/decision-records/DR-0013-input-pin-charge-split.md), superseding DR-0001) | — (drive budget not resolved at 2 MS/s, see DR-0013) | `ss_125c_2.97v` (worst R_on). Full scale is **ratiometric to V_REF**, not a fixed 0–3.3 V range — note **[c]** |
| Input structure | Track-mode C_in = 18.254 pF per side (512 · C_u, C_u = 35.6528 fF, [DR-0019](spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md)); series switch R_on 21.3–60.0 Ω over PVT; T/H −3 dB bandwidth ≥ 5.3 MHz (≥ 10.6 × Nyquist) | — | R_on over the 27-point grid, worst `ss_125c_2.97v`; hold droop 0.136 LSB @ `ff_125c_3.63v` is a **lower bound** — note **[f]**. Details and links: [memo §14.3](spec/testbench-suite-memo.md) |
| Reference | V_REF = 3.3 V, external pin; external decoupling ≥ 40 nF; effective source impedance ≤ 240 Ω in the switching band ([DR-0002](spec/decision-records/DR-0002-reference-source.md)) | Z_ref ≈ ≤ 120 Ω @ 2 MS/s (bit cycle halves; explicitly unresolved, DR-0002) | Bit-cycle settling at `ss_125c_2.97v`; 240 Ω is a conservative floor #8 may relax, never tighten. Reference **noise** allocation: note **[b]** |
| V_CM | V_cm = V_REF/2 = 1.65 V, external pin; external decoupling ≥ 40 nF; effective source impedance ≤ 220 Ω in the switching band ([DR-0026](spec/decision-records/DR-0026-vcm-drive-source.md)) | Z_vcm ≈ ≤ 112 Ω @ 2 MS/s | Bit-cycle settling on the array's release-phase transient. ADC-level testbenches use an ideal V_cm source; ≈ 0.2 LSB `gain_err_lsb` shift measured at the derived budget. Details: [memo §14.4](spec/testbench-suite-memo.md) |
| Clock | External pin, 16 × f_s → 16 MHz @ 1 MS/s; aperture jitter ≤ 250 ps rms ([DR-0003](spec/decision-records/DR-0003-clocking.md)) | 32 MHz @ 2 MS/s; ≤ 180 ps rms | Jitter budget evaluated at f_in = 500 kHz (Nyquist) with 6 dB margin (DR-0003) |
| Supply | V_DD = 3.3 V ±10 % (2.97 / 3.30 / 3.63 V), single supply, 3.3 V devices ([DR-0004](spec/decision-records/DR-0004-device-flavor.md)); external decoupling ≥ 40 nF; source impedance ≤ 3 Ω in the switching band; plus required on-die decoupling, not yet sized ([DR-0036](spec/decision-records/DR-0036-vdd-decoupling-budget.md), proposed) | Z_vdd ≈ ≤ 1.6 Ω @ 2 MS/s | Holds 2.97–3.63 V **subject to V_REF ≤ V_DD** — note **[c]**. Decoupling binds at `ff_-40c_3.63v` (34.38 mA CDAC peak). Details: [memo §14.5](spec/testbench-suite-memo.md) |
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

### Evidence tier: where this block stands

This block's position on `klayout-tools`'
[design-evidence ladder](https://github.com/2AMLogic/klayout-tools/blob/main/docs/design-evidence-tiers.md)
is **graded, not asserted**: [`signoff/`](signoff/) holds the block manifest
`klt signoff --manifest` reads, the grader's own committed output, and a
repo-side check that re-derives every input behind it on each pull request. As
of record <!-- signoff:current-record -->
`20261009-170226-b6ca4338` the verdict is `kind: mixed-signal`,
`tier: none`, **8 of 22 T1 rows met** — read
[`signoff/README.md`](signoff/README.md) for what each unmet row does and does
not mean, since several are structural rather than missing work.

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

## Independent verification (Chipalooza)

Written for a reviewer who has never seen this repository, per the
Chipalooza organizer's stated bar for the schematic review (Tim Edwards,
2026-08-21, quoted in issue #263): *"It must be possible for me to
independently run simulations to verify the performance of the circuit ...
in the form of a shell script or a Makefile target such that full
characterization can be done from a single command-line command."* This
section is that documentation; `docs/chipalooza/challenge-3-proposal.md`
Sec 4 links back here and states, per spec row, what this section's targets
produce for it.

### Prerequisites

| Tool | Version this repo is pinned to | Install |
|---|---|---|
| `ngspice` | ≥ 46 (`sim/toolchain.json`'s `ngspice_min_major` — newer is accepted and recorded) | `apt-get install ngspice` / `brew install ngspice`, or build from the upstream release tarball if your distribution ships an older one (Ubuntu `noble` ships 42; `.github/workflows/nightly-pdk.yml` builds from source for exactly this reason) |
| gf180mcu PDK | open_pdks commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (`sim/toolchain.json`'s `open_pdks` pin — an **exact** match, not a floor) | [volare](https://github.com/efabless/volare) `fetch` + `enable`, or any environment exporting a compatible `PDK_ROOT`/`PDK` for this hash; commands in [`docs/environment-setup.md`](docs/environment-setup.md) §4 |
| `python3` | ≥ 3.9 (`sim/toolchain.json`'s `python_min`) | stdlib only for the harness itself (`sim/run_corners.py`) — no venv, no `requirements.txt` |
| `scipy` | any recent release (unpinned) | `pip install scipy` — needed only by `sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py` (the Gain error, mismatch row's Monte Carlo model) and `sim/comparator-offset-gof/testbench/analyze_gof.py`; the `run_corners.py` harness itself has no third-party dependency. **This pin is not yet recorded in `docs/environment-setup.md`/`sim/toolchain.json` — a real gap this section surfaces rather than papers over; see the follow-up filed alongside this section.** |

**Not required for `make check` / `make smoke` / `make characterize`**:
`xschem` (only needed to regenerate a `.spice` netlist from a `.sch`
schematic, or to run `sim/smoke_test/`'s separate xschem install check —
every netlist these three targets simulate is already a checked-in
`.spice` file) and `klt`/KLayout (only needed to regenerate the post-layout
*extracted* netlist fragments the "extracted, GOVERNING" campaigns below
read — those fragments are themselves checked-in artifacts of a pinned
`klt` run, `layout/toolchain.json`; these targets read them, they do not
regenerate them from GDS).

Export the PDK environment once per shell (or `source sim/env.sh`, which
derives the same exports from whatever the harness itself resolves):

```bash
export PDK_ROOT="$(volare path)"   # -> ~/.volare
export PDK="gf180mcuD"             # the 3.3 V metal-stack variant this repo targets
```

Full install walkthrough, including a worked from-source `ngspice`/PDK
install for a bare Linux host: [`docs/environment-setup.md`](docs/environment-setup.md).

### The three targets

```bash
make check         # unit tests + syntax checks + toolchain/PDK env check.
                    # No PDK required to run -- reports whether one is
                    # installed rather than failing without one. Seconds.
make smoke          # one nominal PVT corner (tt / 27 C / nominal supply)
                    # across every campaign below, writes no evidence.
                    # Needs ngspice + the gf180mcu PDK. Minutes, not hours.
make characterize    # the full PVT/corner campaign behind every spec row
                    # in docs/chipalooza/challenge-3-proposal.md Sec 4,
                    # minting a new, dated sim/<experiment>/records/ entry
                    # per campaign (append-only, sim/README.md's format).
                    # Needs ngspice + the gf180mcu PDK. Hours.
```

All three exit non-zero on any failure. `make characterize` is a thin
wrapper (`sim/characterize.sh`) over the same `sim/run_corners.py` harness
`sim/selftest.sh` uses to prove the harness itself — see
`sim/harness/README.md` for why `sim/smoke_test/` (xschem/ngspice install
check), `sim/selftest.sh` (harness acceptance test) and
`sim/characterize.sh` (this section's full-ADC characterization campaign)
are three different things answering three different questions.

### Wall-clock and core count

Measured on a Linux CI-class host (8 logical cores), toolchain and PDK as
pinned above:

| Target | Measured wall-clock | Notes |
|---|---|---|
| `make check` | ~1.6–2.6 s, fresh clone | No PDK needed; the env check step reports PDK presence without requiring one |
| `make smoke` | ~22–27 min, fresh clone (three independent clean measurements: 21m45s, 22m58s, 27m18s) | One nominal-corner point per campaign (~20 `run_corners.py`/script invocations); the two heaviest single points (the extracted FFT decks) dominate; the range reflects host contention, not run-to-run variance in the campaign itself |
| `make characterize` | **199m59s (~3h20m), fresh clone, full end-to-end measurement** — see the PR description for the exact run this timed and the fixes it drove | The full PVT grid, every campaign. `JOBS=<n> make characterize` to override parallelism (defaults to `nproc`); a shared/contended host will run longer |

That 199m59s measurement is real (see the PR description for the log), but
it is honest to say exactly what state of this PR's own branch it was taken
against, because this dry run itself *found* three of this PR's fixes
while it ran: it was cloned and started **before** two of those fixes
existed. Specifically:

- The four `--timeout` fixes for the full-`ADC_BLOCK`-core **extracted**
  campaigns (`dr0014-sampling`, `adc-enob-fft`, `adc-inl-dnl`, `adc-power`)
  *were* present, and all four ran to completion and PASSed in this same
  199m59s measurement — directly verified, not inferred.
- The fifth `--timeout` fix, for `adc-enob-fft`'s **schematic** baseline,
  and the `--subset-reason` fix for the three DR-0010 rung-1-ideal
  manifests (`sar-logic-functional`, `sar-logic-timing`,
  `timing-budget-closure`), were both found *during* this measurement but
  landed in commits pushed after it started. They are each individually
  verified correct (the schematic fix is mechanically identical to the
  four already-proven extracted fixes on the same class of failure; the
  subset-reason fix was independently re-run standalone to a `PASS`,
  `exit 0`), but neither was re-validated inside a second complete,
  re-timed 199-minute run, given the cost of repeating it — so the true
  full-grid time with every fix applied is this measurement plus a modest
  addition for the three previously-instant-erroring manifests actually
  simulating, not separately re-measured end to end.

On an uncontended multi-core host, expect **on the order of 2–4 hours**; a
shared host runs longer, as the `make smoke` range above already shows for
a much smaller campaign.

### Where results land

- Every `run_corners.py`-driven campaign mints a new, dated
  `sim/<experiment>/records/<record-id>.md` file — the same directory the
  citations in `docs/chipalooza/challenge-3-proposal.md` Sec 4 point at.
  Your run's record ID will differ from the committed one (it is minted
  fresh, from your own commit/timestamp); compare the **numbers**, not the
  filename.
- `mc-cdac-mismatch` (Gain error, mismatch) and the extracted,
  `ADC_BLOCK`-inclusive comparator-regeneration measurement are driven by
  bespoke scripts rather than the generic manifest runner, and write their
  raw CSV/JSON output under `sim/.work/characterize/` (git-ignored, not
  committed evidence) instead of minting a narrative record — writing that
  narrative record is a manual documentation step in this repo's own
  convention for these two, the same way the committed
  `sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md` record was
  itself written up from a prior run of the same script.
- `sim/.work/` (git-ignored throughout) also holds the generated ngspice
  decks and raw per-corner logs for every run, kept only for the duration
  of that run's own debugging.

**`make characterize`'s overall exit status is expected to be non-zero even
on a correct run**, because of a bench-level corner-sensitivity sanity
check, not a spec check, on one campaign:

- The `device-switch-ron` extracted campaign's `ron_t_max`
  `min_spread_pct_by_axis` check on the supply axis reads 9.71502% against
  its 10%-floor sanity threshold, reproducing (bit-identically) the
  committed
  [`sim/device-switch-ron/records/20260817-204715-076d545.md`](sim/device-switch-ron/records/20260817-204715-076d545.md)
  verdict — "PRE-EXISTING HARNESS FAIL, reproduced rather than repaired" per
  that record's own note.
The `adc-power` schematic baseline is no longer an expected failure. When
this section was first written, its `p_cmp_f050_uw`
`min_spread_pct_by_axis` check on the process axis read 0.0606826% against
its 2% floor (DR-0018). Issue #266 traced this to the wrong axis being
swept, not to a real flat corner. `sim/characterize.sh` passed no
`--corners` to that stage, so `run_corners.py` fell back to the manifest
default (`cdac`), a capacitor-only corner set that leaves the MOS models at
`typical`. PR #268 fixed `sim/characterize.sh`: in `characterize` mode the
schematic-baseline `adc-power` stage now passes `--corners tt ss ff`, the
same MOS corner set its extracted stage already used. The clean-tree
re-run at the fix commit,
[`sim/adc-power/records/20260826-085142-155595d.md`](sim/adc-power/records/20260826-085142-155595d.md),
reads a weakest process-axis slice of 3.19972% for `p_cmp_f050_uw`, above
the unchanged 2% floor, and reports Overall PASS. That record is the #266
resolution evidence. It is not a new timing of a full `make characterize`
run.

The remaining `device-switch-ron` failure is not caused by this Makefile
and is not a spec-row failure (the `Input structure R_on` row's PASS
verdict rests on `sim/dr0014-sampling/records/`). This repo's convention
(CLAUDE.md: "agents do not relax the ratified spec to make results pass")
is to document a marginal, deck-level sensitivity check like this one
rather than relax it. `sim/characterize.sh`'s printed summary still
reports every OTHER campaign's own pass/fail individually, so this
expected contribution to a non-zero overall exit does not hide a genuine
regression elsewhere.

### Spec row → output mapping

`docs/chipalooza/challenge-3-proposal.md` Sec 4 names, for every spec row,
which of this section's campaigns backs it and what `make characterize`
produces for it — see that table's "Reproducing this table" subsection
immediately after the spec table itself, so the mapping lives next to the
citations it explains rather than duplicated (and liable to drift) here.

## Repository layout

```
spec/          target spec, prior-art survey, decision records
design/        schematics / netlists (xschem)
sim/           testbenches, PVT corner harness, append-only result records
layout/        GDS + DRC/LVS flow and reports (klayout-tools driven);
               layout/adc-top/ is the drawn block
signoff/       the block manifest `klt signoff` grades, and this block's
               machine-graded gap to T1 (verdict of record)
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
unit tests), the T1 signoff-verdict freshness check
([`signoff/`](signoff/)) and its negative control, plus shell and Python syntax
checks. It installs no PDK.

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
