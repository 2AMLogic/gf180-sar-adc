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

Early. There is no ADC yet — there is the substrate you need before there
honestly can be one:

| Area | State |
|---|---|
| Target spec | Ratified 2026-07-31 (table below) — `spec/decision-records/DR-0006-spec-ratification.md` |
| Prior-art survey | Done — `spec/prior-art-survey.md` |
| Simulation harness | Working — PVT corner runner over gf180mcu, with a self-test |
| Device characterization | Done — CDAC caps, sampling switches, comparator input devices |
| Schematics | Smoke-test only (`design/`) |
| Layout | Not started |
| Silicon | None |

## Target specification

Ratified 2026-07-31 ([DR-0006](spec/decision-records/DR-0006-spec-ratification.md), issue #1).

| Parameter | Target | Stretch | Binding corner / condition |
|---|---|---|---|
| Resolution | 10 bit | 12 bit variant | — (architectural) |
| Rate | 1 MS/s | 2 MS/s | Settling at `ss_125c_2.97v`; distortion re-checked at `ss_-40c_2.97v` — worst R_on flatness, 3.29× ([devchar §2.1](sim/device-characterization-report.md)) |
| ENOB @ Nyquist | > 9.0 (non-quantization budget σ_total ≤ 1.61 mV rms) | > 9.5 (≤ 0.930 mV rms) | Settling at `ss_125c_2.97v`; mismatch tail at 3σ Monte Carlo. Reference noise is **user-supplied** — allocated, not guaranteed by this block: note **[b]** |
| SFDR @ Nyquist | ≥ 62 dB | ≥ 65 dB | `ss_-40c_2.97v` — R_on-modulation distortion ([devchar §2.1](sim/device-characterization-report.md)); margin derivation in note **[a]** |
| INL / DNL | < 1 LSB | < 0.5 LSB | 3σ Monte Carlo mismatch (**not** a PVT corner); **untrimmed and uncalibrated** — note **[d]** |
| Offset error | ≤ 2 LSB, untrimmed | — | 3σ mismatch (not a PVT corner); no analog trim, digitally removable — note **[e]** |
| Gain error | ≤ 0.5 LSB, untrimmed, **excluding** V_REF error | — | 3σ mismatch; full scale is ratiometric to V_REF — note **[e]** |
| CMRR (differential mode) | ≥ 60 dB, DC–Nyquist, over V_CM = V_REF/2 ± 100 mV | ≥ 65 dB | 3σ mismatch; margin derivation in note **[a]** |
| Input | 0–V_REF single-ended, ±V_REF differential about V_CM = V_REF/2 — **requires V_REF ≤ V_DD**; ≤ 500 Ω source impedance, single-ended and per differential pin ([DR-0001](spec/decision-records/DR-0001-input-drive.md)) | — (source-impedance budget not resolved at this rate, see DR-0001) | `ss_125c_2.97v` (worst R_on). Full scale is **ratiometric to V_REF**, not a fixed 0–3.3 V range — note **[c]** |
| Input structure | Track-mode C_in ≈ 34 pF (planning value, pending #8); series switch R_on 156–570 Ω over PVT; implied T/H −3 dB bandwidth ≈ 4.4 MHz with a 500 Ω source ([DR-0001](spec/decision-records/DR-0001-input-drive.md)) | — | R_on range over the 45-point grid, worst `ss_125c_2.97v` ([devchar §2.1](sim/device-characterization-report.md)); hold droop 0.136 LSB @ `ff_125c_3.63v` is a **lower bound** — note **[f]** |
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
optional (devchar §2.2).

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
(devchar §5.1).

**[f] The Input-structure row publishes the load side of DR-0001's ≤ 500 Ω
contract**, without which that source-impedance requirement is not auditable by
a user. T/H bandwidth is `derived`: the worst-case series switch resistance
570 Ω (`ss_125c_2.97v`) plus a 500 Ω source into the 34 pF planning array is
`τ = 36 ns` → `f_−3dB ≈ 4.4 MHz`, about 9× Nyquist. `C_in` is a planning value
pending #8 and is deliberately conservative (the `A_C = 2.0 %·µm` derating of
note **[d]**). Hold droop of 0.136 LSB at `ff_125c_3.63v` (438 µV on the 2.5 pF
measurement array, [devchar §2.3](sim/device-characterization-report.md)) is a
**lower bound**: the gf180mcu FET cards carry no junction saturation-current
density, so every leakage figure in this repo is channel leakage only
(devchar §5.2) — junction leakage must be budgeted from foundry data.

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

- Input drive: [DR-0001](spec/decision-records/DR-0001-input-drive.md) — external driver required, ≤ 500 Ω source impedance, 1 MS/s only.
- Reference source: [DR-0002](spec/decision-records/DR-0002-reference-source.md) — external `V_REF` pin (3.3 V), not internal/bandgap-derived; now the Reference row above.
- Clocking: [DR-0003](spec/decision-records/DR-0003-clocking.md) — external clock pin, 16 MHz @ 1 MS/s (32 MHz @ 2 MS/s stretch), ≤ 250 ps rms aperture jitter; now the Clock row above.
- Device flavor: [DR-0004](spec/decision-records/DR-0004-device-flavor.md) — 3.3 V devices throughout (`nfet_03v3`/`pfet_03v3`), single supply, no level shifters; the device choice is an implementation detail, but its supply and ±10 % tolerance are now the Supply row above.
- Interface scope: [DR-0005](spec/decision-records/DR-0005-interface-scope.md) — parallel output register in scope for simulation-complete, SPI deferred to a later maturity rung.

## Layout

```
spec/          target spec, prior-art survey, decision records
design/        schematics / netlists (xschem)
sim/           testbenches, PVT corner harness, append-only result records
layout/        GDS + DRC/LVS reports (klayout-tools driven)
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
  — measured-in-simulation device data, with per-number provenance.

## License

[Apache-2.0](LICENSE).
