# Chipalooza Challenge #3 (GF180MCU / Wafer.Space) — 10-bit SAR ADC proposal

Submission target: Open Circuit Design's [Chipalooza Challenge
#3](https://opencircuitdesign.com/chipalooza/challenge-3.html), GF180MCU test
chip fabricated through Wafer.Space. Proposal deadline **2026-08-31**. Gated
reviews: schematic week of Oct 5, layout week of Nov 2, final week of Nov 23;
tape-out 2026-12-14; packaged silicon on a test board back ~2027-05-31.

**Source repository**: `2AMLogic/gf180-sar-adc` (public, Apache-2.0 — see
§8). Every number in §4 is transcribed from this repository's own append-only
`sim/` evidence, with a dated citation to the record it came from — nothing
here is asserted without a re-runnable testbench. **Independent verification**:
every citation in §4 is re-runnable from a clean clone with the PDK
installed via a single `make characterize` (plus `make check` / `make smoke`
for faster partial checks) — see
[`README.md#independent-verification-chipalooza`](../../README.md#independent-verification-chipalooza)
for prerequisites and instructions, and §4's "Reproducing this table"
subsection for the row-by-row mapping.

This document is written to be emailed verbatim as the block's public
proposal. It contains no personal or institutional identifiers; designer CVs
and the test-equipment list are separate email attachments the submitting
operator supplies outside this repository.

---

## 1. Type of IP block

A 10-bit, single-channel, differential/single-ended-selectable,
bottom-plate-sampled Successive-Approximation-Register (SAR) analog-to-digital
converter, target 1 MS/s (2 MS/s stretch).

---

## 2. I/O list, including test ports

### 2.1 Rails: this block uses the Challenge's 3.3 V digital rail only

This design is ratified single-supply, **3.3 V devices throughout**
(`nfet_03v3`/`pfet_03v3`) for both the analog signal path and the digital
interface —
[DR-0004](../../spec/decision-records/DR-0004-device-flavor.md). A 3.3 V-oxide
device is not rated for a 5.0 V rail: gf180mcu's own device-flavor naming
convention (`03v3` vs. `05v0`/`06v0`) is an oxide-thickness/voltage-rating
distinction, not a nominal-operating-point label, and this repository has
never simulated, laid out, or characterized this block above 3.63 V (the
`V_DD` ±10 % ceiling). **Proposal: this block draws its single `V_DD`/`V_SS`
from the Challenge's 3.3 V digital rail, and does not use the 5.0 V analog
rail at all.** This is a scope choice stated plainly, not a gap silently
absorbed — see §4's note on rail coverage for what "at the challenge rails"
means for this design in practice.

### 2.2 Pad table, mapped to the Challenge #3 slot budget

| Signal | Dir | Challenge slot | Count used | Notes |
|---|---|---|---|---|
| `V_DD`, `V_SS` | supply | 3.3 V digital rail | — (rail, not a slot line item) | Single supply for the whole block, analog and digital ([DR-0004](../../spec/decision-records/DR-0004-device-flavor.md)) |
| `V_REF` | in, dedicated | bandgap-referenced bias voltage (budget: 1) | 1 | 3.3 V nominal, external pin, **driven from the harness bandgap instead of an internal one** — this block has never had an internal reference; [DR-0002](../../spec/decision-records/DR-0002-reference-source.md) already ratified an external `V_REF` pin, so sourcing it from the shared harness bandgap is a zero-cost substitution, not a new dependency. Requires ≥ 40 nF decoupling and ≤ 240 Ω effective source impedance in the switching band — **low-impedance, not shareable through a mux switch** (see "dedicated pads" below) |
| `IBIAS` | in, dedicated | bandgap-referenced current source (budget: up to 2) | 1 of 2 | 10 µA nominal static bias into the comparator preamp tail (`design/comparator/comparator.spice`'s `ibias` pin); bias generation was never in this block's own scope ([DR-0007](../../spec/decision-records/DR-0007-track-switch-topology.md) Consequences) — the harness bandgap current source is a direct, zero-redesign substitute for the bench current source this block's testbenches already assume |
| `PINP`, `PINN` | in, dedicated (2 pads) | dedicated pad (budget: up to 4) | 2 of 4 | Differential (or single-ended, `PINN` tied to `V_CM`) analog input, driven directly onto the CDAC's bottom-plate T-gates every sample phase. Needs a source impedance meeting `R_source × (C_pin + C_in) ≤ 30 ns` ([DR-0013](../../spec/decision-records/DR-0013-input-pin-charge-split.md)) — **a mux switch's added series R would eat directly into this budget, so these must be dedicated, not shared** |
| `V_CM` | in, dedicated | dedicated pad (budget: up to 4) | 1 of 4 | Common-mode bias, `V_REF/2` = 1.65 V nominal at `V_REF` = 3.3 V. Drives the same CDAC bottom-plate/top-plate switch network `V_REF` does every release phase, but **this repository has no measured or derived drive-impedance/decoupling budget for `V_CM`** the way [DR-0002](../../spec/decision-records/DR-0002-reference-source.md) derives one for `V_REF` — every existing testbench drives it from an ideal, zero-impedance source. Provisionally treated as dedicated (same reasoning as `V_REF`) pending the follow-up characterization noted in §7 |
| `CLK` | in | digital control input (budget: up to 24) | 1 of 24 | External clock, 16 MHz @ 1 MS/s target (32 MHz @ 2 MS/s stretch), ≤ 250 ps rms aperture jitter ([DR-0003](../../spec/decision-records/DR-0003-clocking.md)) — no on-chip oscillator |
| `START` | in | digital control input | 1 of 24 | Synchronous restart; tie low to free-run |
| `MODE` | in | digital control input | 1 of 24 | 1 = differential, 0 = single-ended ([DR-0011](../../spec/decision-records/DR-0011-cdac-switching-scheme.md)) |
| `DRDY` | out | digital test output (budget: up to 12) | 1 of 12 | Data-ready strobe, asserted the clock the 10-bit code is valid |
| `C9..C0` | out | digital test output | 10 of 12 | 10-bit parallel output register, `C9` = MSB. SPI is explicitly out of scope for this maturity rung ([DR-0005](../../spec/decision-records/DR-0005-interface-scope.md)) — parallel readout is the only interface this block offers today |

**Totals against the Challenge #3 budget**: 1 of 1 bandgap-referenced bias
voltage, 1 of ≤2 bandgap-referenced current sources, 3 of ≤24 digital control
inputs, 11 of ≤12 digital test outputs, **4 of ≤4 dedicated pads**, **0 of ≤4
shared (multiplexed) analog lines**. Every category fits inside budget, with
1 digital-test-output slot and the entire shared-analog-line allocation left
unused by this block (available to whatever else shares the die/harness).

### 2.3 What's dropped, multiplexed, or substituted relative to this repo's own port list

- **Nothing this block currently brings off-chip is dropped.** The port list
  above (`V_DD`/`V_SS`, `V_REF`, `IBIAS`, `PINP`/`PINN`, `V_CM`, `CLK`,
  `START`, `MODE`, `DRDY`, `C9..C0`) is exactly the set of external-facing
  nets `design/adc-top/adc_top.spice`, `design/comparator/comparator.spice`
  and `design/sar-logic/README.md`'s port table already define — nothing is
  cut to fit the slot budget, because the budget has headroom to spare (§2.2).
- **`V_REF` and `IBIAS` move from "external, bench-supplied" to "harness
  bandgap-referenced."** This is the one substitution: this block has never
  had an internal bandgap or bias generator (both were explicitly
  out-of-scope decisions, [DR-0002](../../spec/decision-records/DR-0002-reference-source.md),
  [DR-0007](../../spec/decision-records/DR-0007-track-switch-topology.md)),
  so the shared harness's bandgap-referenced bias voltage and current source
  are a direct substitute for what a bench supply was always going to provide
  — no redesign, no new verification claim.
- **No pins are shared/multiplexed for this block's core function.** The two
  signals with the tightest source-impedance requirements — `PINP`/`PINN`
  (the input pair, DR-0013) and `V_REF` — are kept dedicated rather than
  routed through the Challenge's shared analog mux, because a mux switch's
  series resistance would erode the budget those decision records derive.
  `V_CM` is provisionally held to the same standard pending the
  characterization gap noted in §2.2 and §7.
- **Internal control signals stay internal.** The 55 `rel_n_<w><s>` /
  `sel_hi_n_<w><s>` / `sel_lo_n_<w><s>` CDAC switch-driver nets, the
  `samp_tp_n`/`sel_in_n` sampling controls, and the comparator's
  `dout`/`doutb` decision pair are internal signals between the SAR sequencer
  and the analog core in every deck this repository has ever built — they
  were never external ports and are not proposed as any of the Challenge's
  shared or dedicated lines.

---

## 3. Functional description

The converter samples a differential (or single-ended, with the unused input
tied to `V_CM`) input onto a binary-weighted, 512-position-per-side
capacitive DAC (CDAC) array, then resolves 10 bits by successive
approximation against an internal comparator, using monotonic-capacitor
switching with a free MSB decision
([DR-0011](../../spec/decision-records/DR-0011-cdac-switching-scheme.md)).
Sampling is **bottom-plate**: the top plate is held at `V_CM` through a
dedicated switch during acquisition and released one clock before the bottom
plates leave the input, so every subsequent DAC step and the sampled input
land on the same numerator over the same denominator and the
`C_arr/(C_arr+C_par)` top-plate divider cancels from the comparator's decision
rather than attenuating the signal
([DR-0014](../../spec/decision-records/DR-0014-bottom-plate-sampling.md)).
The comparator is a static differential preamplifier followed by a StrongARM
latch and an SR output latch
([DR-0015](../../spec/decision-records/DR-0015-comparator-topology.md)). A
synchronous, non-redundant sequencer runs the conversion over `M = 16` clocks
— 4 sample-phase clocks, 10 bit-trial clocks (1 free MSB + 9 switched trials),
and 2 clocks to latch the 10-bit parallel output register and assert
data-ready
([DR-0008](../../spec/decision-records/DR-0008-sar-logic-synchronous.md),
[DR-0009](../../spec/decision-records/DR-0009-no-redundancy.md)). The
converter has one input channel; it is not a multiplexed or multi-channel
front end, and building one is explicitly out of this block's scope
([DR-0020](../../spec/decision-records/DR-0020-mux-variant-and-fast-comparator-scope.md)).

**A material, stated gap in physical readiness**: the SAR sequencer and the
10-bit output register exist today only as an ideal, event-driven behavioral
model (`design/sar-logic/sar_ctrl.spice`, DR-0010's "rung 1"), used to verify
sequencing and decode logic cheaply across every long PVT/Monte-Carlo
campaign. **No transistor-level netlist or layout for this digital partition
exists yet** — `layout/adc-top/`'s floorplan reserves and rings the area for
it but does not draw it, because the open gf180mcu PDK ships no 3.3 V-device
standard-cell library to build it from. The path to close this is already
drafted and is the single largest open item before the Challenge's schematic
review — see §7.

Everything else — the CDAC array, its bottom-plate switch network and local
T-gate drivers, the comparator, and their assembly into `ADC_TOP` /
`ADC_BLOCK` — is drawn at transistor level, DRC-clean, and LVS-matched
against the schematic (323 devices + 1024 unit MiM capacitors,
`layout/adc-top/README.md`).

---

## 4. Target specification at the Challenge rails

**What "at the challenge rails" means here**: per §2.1, this block runs its
single 3.3 V supply from the Challenge's 3.3 V digital rail and does not use
the 5.0 V analog rail. Every row below is therefore reported at this
repository's own ratified PVT grid — `V_DD` = `V_REF` = 2.97 / 3.30 / 3.63 V
(the 3.3 V ± 10 % supply grid, [DR-0006](../../spec/decision-records/DR-0006-spec-ratification.md)),
process corners `ss`/`tt`/`ff`, temperature −40 / 27 / 125 °C — which **is**
this design's full coverage of the Challenge's 3.3 V digital rail. No row
below has ever been measured at, or is claimed to hold at, a 5.0 V supply;
where that distinction matters it is called out explicitly.

The **governing** value for each row is the post-layout extracted result
where one exists (this repository's convention,
[`sim/extracted-delta-summary.md`](../../sim/extracted-delta-summary.md)
§7.1), with the schematic figure carried alongside it. Full per-corner data,
methodology, and re-derivation commands live at each citation; this table is
a pointer, not a re-derivation, mirroring
[`sim/characterization-summary.md`](../../sim/characterization-summary.md),
which is the primary source for every row below.

| Parameter | Target (min/typ/max) | Absolute limit | Measured (governing, 2.97–3.63 V grid) | Verdict at challenge rails | Source (dated) |
|---|---|---|---|---|---|
| Resolution | 10 bit (architectural) | — | 10 bits resolved, decode proof | **PASS** | [`sim/sar-logic-functional/records/20260801-041242-96c2ea7.md`](../../sim/sar-logic-functional/records/20260801-041242-96c2ea7.md) |
| Sample rate | 1 MS/s typ (2 MS/s stretch, not closed) | M=16 clocks/conversion, deterministic | All post-layout timing inputs closed (settling 1.258→1.560 ns, comparator delay 0.863→1.257 ns, R_WORST_BIT 648 Ω, C_WORST_BIT 2.40712 pF) | **PASS** (1 MS/s; 2 MS/s stretch not attempted) | [`sim/timing-budget-closure/records/20260814-220124-f613571.md`](../../sim/timing-budget-closure/records/20260814-220124-f613571.md) |
| ENOB @ Nyquist | min > 9.0 (stretch > 9.5) | quantization floor ~10 bit ideal | **8.857 bits worst** (`tt_125c_3.63v`), 2 of 9 grid points below 9.0 | **FAIL** — 0.143 bit short at worst corner, open regression (#211) | [`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](../../sim/adc-enob-fft/records/20260825-061750-d00911a.md) (extracted, governing, clean-tree) |
| SFDR @ Nyquist | min ≥ 62 dB (stretch ≥ 65 dB) | — | **60.40 dB worst** (`ff_125c_3.63v`), 4 of 9 grid points below 62 dB | **FAIL** — 1.60 dB short at worst corner, same open regression | same record; switch's own contribution also FAILs 11/117 points, [`sim/track-switch-thd/records/20260817-142956-72d15de.md`](../../sim/track-switch-thd/records/20260817-142956-72d15de.md) |
| INL | max < 1 LSB (stretch < 0.5 LSB) | — | worst \|INL\| 0.5284 LSB (`ss_125c_2.97v`) | **PASS** ratified row; **misses** the 0.5 LSB stretch | [`sim/adc-inl-dnl/records/20260817-214114-076d545.md`](../../sim/adc-inl-dnl/records/20260817-214114-076d545.md) (extracted, governing) |
| DNL | max < 1 LSB (stretch < 0.5 LSB) | — | worst \|DNL\| 0.7278 LSB (same corner) | **PASS** ratified row; **misses** the 0.5 LSB stretch | same record |
| Offset error | max ≤ 2 LSB, untrimmed | — | Comparator-only 3σ mismatch: worst σ 0.398789 LSB (`sigma_to_spec` 4.99σ); deterministic extracted-core offset −0.597…−4.357 mV | **Not fully measured** — comparator-inclusive (`ADC_BLOCK`) statistical 3σ population still open (tracked, not new: issue #89 remainder) | [`sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md`](../../sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md); [`sim/comparator-regeneration/records/20260814-215626-f613571.md`](../../sim/comparator-regeneration/records/20260814-215626-f613571.md) |
| Gain error, mismatch | max ≤ 0.5 LSB, untrimmed, excl. V_REF error | — | `sigma_to_spec = 3.13`, `klt yield` `status: pass`, N = 20 000 | **PASS** | [`sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`](../../sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md) |
| Gain error, systematic | max ≤ 0.5 LSB, untrimmed, excl. V_REF error | — | 0.0004845 LSB worst (`ff_-40c_3.63v`), ~1032× inside bound | **PASS**, wide margin | [`sim/dr0014-sampling/records/20260817-204729-076d545.md`](../../sim/dr0014-sampling/records/20260817-204729-076d545.md) |
| CMRR (differential) | min ≥ 60 dB (stretch ≥ 65 dB), ±100 mV about `V_CM` | — | 118.2 dB (systematic) / 85.6 dB (3σ mismatch), worst corner of 45, ±50 mV band measured and linearly extrapolated to ±100 mV | **PASS**, ≥ 25.6 dB margin (extrapolated, not directly measured at ±100 mV) | [`sim/comparator-offset-mc/records/20260816-050001-d002e66.md`](../../sim/comparator-offset-mc/records/20260816-050001-d002e66.md) |
| Input drive contribution | budgeted inside Gain error rows | — | Sampling-switch gain-error term +0.082…+0.370 LSB, worst `ff_125c_3.63v`, full 117-point grid at the DR-0013 drive network | **PASS** | [`sim/track-switch-sampling/records/20260817-142951-72d15de.md`](../../sim/track-switch-sampling/records/20260817-142951-72d15de.md) |
| Input structure `R_on` | 21.3–60.0 Ω over PVT (array path); T/H BW ≥ 5.3 MHz | — | Array-path `R_on` 21.329–60.022 Ω (27 pts, bit-identical schematic/extracted); T/H BW derived, unaffected by the resize | **PASS** | [`sim/dr0014-sampling/records/20260817-134517-cde979d.md`](../../sim/dr0014-sampling/records/20260817-134517-cde979d.md); [`sim/device-switch-ron/records/20260817-204715-076d545.md`](../../sim/device-switch-ron/records/20260817-204715-076d545.md) |
| Reference (`V_REF`) drive | ≥ 40 nF decoupling, `Z_ref` ≤ 240 Ω | `V_REF ≤ V_DD` (device-rating hard condition, note below) | Bit-cycle settling PASS at all 117 PVT points; gating budget error 0 mV on the whole grid | **PASS** | [`sim/cdac-bit-settling/records/20260817-121555-227c770.md`](../../sim/cdac-bit-settling/records/20260817-121555-227c770.md) |
| `V_CM` drive | not derived (gap) | same node class as `V_REF` electrically | Every existing testbench drives `V_CM` from an ideal, zero-impedance source | **Unmeasured / TBD** — no `Z_vcm`/`C_dec` budget exists in this repo, unlike `V_REF`'s DR-0002 derivation | none yet — see §7 |
| Clock | 16 MHz @ 1 MS/s, ≤ 250 ps rms aperture jitter (analytic budget) | 32 MHz / ≤ 180 ps rms stretch | 16-phase conversion completes deterministically; jitter budget is a closed-form derivation, not separately measured | **PASS** (sequencing); jitter budget is analytic, not measured against a real clock source | [`sim/sar-logic-timing/records/20260801-033032-06bad60.md`](../../sim/sar-logic-timing/records/20260801-033032-06bad60.md) |
| Supply | 2.97–3.63 V (3.3 V ± 10 %) | 3.3 V-device rating — **do not exceed ~3.63 V**; **never apply the 5.0 V analog rail to this block** (§2.1) | Spanned by every PVT sweep cited above | **PASS** | every record above |
| Latency | 1 conversion, M=16 clocks = 1 µs @ 1 MS/s | — | Deterministic | **PASS** | `sar-logic-functional` + `sar-logic-timing` records above |
| Power @ 1 MS/s | max < 1 mW (stretch < 500 µW) | — | 231.8 µW worst (`ff_27c_3.63v`) | **PASS**, 2.16× margin vs. stretch, 4.31× vs. primary target | [`sim/adc-power/records/20260817-211252-076d545.md`](../../sim/adc-power/records/20260817-211252-076d545.md) |
| Area | max < 0.1 mm² | — | 150,536.239 µm² = 0.150536 mm² (as-built, DRC-clean, LVS-matched) | **FAIL** — 151 % of ratified budget; a `< 0.16 mm²` revision is proposed ([DR-0024](../../spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md)), not yet ratified | `layout/adc-top/area.json`; `layout/adc-top/README.md` |
| Interface | Parallel output register (in scope); SPI (deferred) | — | Parallel register verified functional | **PASS** (as scoped, [DR-0005](../../spec/decision-records/DR-0005-interface-scope.md)) | [`sim/sar-logic-functional/records/20260801-041242-96c2ea7.md`](../../sim/sar-logic-functional/records/20260801-041242-96c2ea7.md) |
| Digital sequencer/output register — physical implementation | transistor-level netlist + layout | — | **None exists** — rung-1 ideal behavioral model only; layout area reserved, not drawn | **UNMET** — blocking item, see §7 | `design/sar-logic/README.md`; `layout/adc-top/README.md` |

### Reproducing this table

Every citation above is re-runnable from a clean clone with the PDK
installed via three `make` targets at the repository root — `make check`,
`make smoke`, `make characterize` — documented in
[`README.md#independent-verification-chipalooza`](../../README.md#independent-verification-chipalooza)
(prerequisites, exact `make` invocations, expected wall-clock and core
count, and where results land). This subsection is the row-by-row half of
that mapping: for each spec row above, which campaign inside
`make characterize` reproduces it, and where that campaign's output lands.
`make characterize` mints a **new**, dated record in the same directory
each citation above points at (`sim/README.md`'s append-only convention —
your run's record ID will differ from the one cited; compare the numbers,
not the filename).

| Spec row | `make characterize` output |
|---|---|
| Resolution | `sim/sar-logic-functional/records/` |
| Sample rate | `sim/timing-budget-closure/records/` (extracted, governing entry) |
| ENOB @ Nyquist | `sim/adc-enob-fft/records/` (extracted, governing entry) |
| SFDR @ Nyquist | `sim/adc-enob-fft/records/` (extracted, governing entry) + `sim/track-switch-thd/records/` |
| INL | `sim/adc-inl-dnl/records/` (extracted, governing entry) |
| DNL | `sim/adc-inl-dnl/records/` (extracted, governing entry) |
| Offset error | `sim/comparator-offset-mc/records/` + `sim/.work/characterize/comparator-regeneration-extracted/` (raw JSON, bespoke script — not an append-only record; compare against `sim/comparator-regeneration/records/20260814-215626-f613571.md`) |
| Gain error, mismatch | `sim/.work/characterize/mc-cdac-mismatch/` (raw CSV/JSON, bespoke script — not an append-only record; compare against `sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`) |
| Gain error, systematic | `sim/dr0014-sampling/testbench-extracted`'s records, alongside `sim/dr0014-sampling/records/` (extracted, governing entry) |
| CMRR (differential) | `sim/comparator-offset-mc/records/` |
| Input drive contribution | `sim/track-switch-sampling/records/` |
| Input structure `R_on` | `sim/dr0014-sampling/records/` (extracted) + `sim/device-switch-ron/records/` (extracted, governing entry) |
| Reference (`V_REF`) drive | `sim/cdac-bit-settling/records/` |
| `V_CM` drive | `sim/vcm-drive-impedance/records/` (all three sweep points — `make smoke` exercises only the `ideal` point, `--no-write`) |
| Clock | `sim/sar-logic-timing/records/` |
| Supply | spanned by every campaign above |
| Latency | `sim/sar-logic-functional/records/` + `sim/sar-logic-timing/records/` |
| Power @ 1 MS/s | `sim/adc-power/records/` (extracted, governing entry) |
| Area | **not produced by `make characterize`** — a layout artifact (`layout/adc-top/area.json`, `layout/adc-top/README.md`), not a simulation; `klt`-driven, out of this Makefile's scope (README.md's Prerequisites note) |
| Interface | `sim/sar-logic-functional/records/` |
| Digital sequencer/output register — physical implementation | **not produced by `make characterize`** — no campaign exists yet, because no transistor-level implementation exists yet (§7 item 1) |

**Rows currently unmet at these rails, and the plan to close them before the
Oct 5 schematic review**:

1. **ENOB @ Nyquist (FAIL, 8.857 bits worst vs. > 9.0 target)** and **SFDR @
   Nyquist (FAIL, 60.40 dB worst vs. ≥ 62 dB target)** — an open, measured
   regression from the DR-0019 CDAC unit-cap resize, root-caused to the
   acquisition `R_on·C_arr` time constant
   ([`sim/dr0019-cu-sweep-findings.md`](../../sim/dr0019-cu-sweep-findings.md)).
   The one measured candidate fix (widening the acquisition T-gate) is
   evaluated end to end and **not adopted** — it trades this FAIL for a worse
   one on Area
   ([DR-0025](../../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md)).
   Per CLAUDE.md, no target is relaxed to absorb this; it stands as a
   recorded, unresolved regression pending a design change not yet found.
2. **Area (FAIL, 151 % of the ratified `< 0.1 mm²` budget)** — a proposed
   `< 0.16 mm²` revision ([DR-0024](../../spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md))
   bounds the current as-built figure but is not yet ratified.
3. **Offset error (partially measured)** — the comparator-inclusive
   (`ADC_BLOCK`) statistical 3σ population is the one remaining piece of
   issue #89's original scope; everything measured so far clears the ≤ 2 LSB
   bound with wide margin.
4. **`V_CM` drive-impedance/decoupling budget (not derived at all)** — a
   genuinely new finding surfaced by writing this proposal, not a
   previously-tracked gap; see §7.
5. **Digital sequencer/output-register physical implementation (does not
   exist)** — the largest single item. [DR-0023](../../spec/decision-records/DR-0023-digital-interface-device-flavor.md)
   already proposes the path to close it (adopt the PDK's shipped 6 V-oxide
   standard-cell libraries at this block's existing 3.3 V rail — electrically
   sound, since a 6 V-oxide device run at 3.3 V is well within its rating,
   the reverse of the direction that would be unsafe) and is drafted and
   awaiting operator ratification; three follow-on buildable issues (RTL/
   synthesis, place-and-route, static timing closure) are specified to be
   filed once it ratifies. **This is the item that must close, or be
   explicitly re-scoped, before a schematic-review-ready gate-level netlist
   can exist.**

None of the above rows had any evidence at a 5.0 V rail to report as
"unmet" in the sense of a missed 5.0 V measurement, because — per §2.1 — this
block is proposed to run only on the Challenge's 3.3 V digital rail. Every
row's coverage gap is against this design's own ratified 2.97–3.63 V grid,
not against an unattempted 5.0 V point.

---

## 5. Test-plan outline (packaged part, QFN on a daughterboard + test board)

All measurements below use only the pads in §2.2 — the digital test outputs
(`DRDY`, `C9..C0`) and the dedicated analog pads (`PINP`/`PINN`, `V_REF`,
`V_CM`); none require the Challenge's shared analog mux lines, which this
block does not use.

1. **Bring-up / DC sanity.** Apply `V_DD` (3.3 V from the digital rail),
   `V_REF` (3.3 V from the harness bandgap), `V_CM` (1.65 V), `IBIAS`
   (10 µA from the harness current source). Confirm quiescent supply current
   is within the Power row's budget (§4) with no input applied, `CLK` free-
   running, `START` low.
2. **Functional / decode check.** Drive `PINP`/`PINN` to a small set of known
   DC levels spanning 0–`V_REF`, in both `MODE` settings. Capture `C9..C0`
   on each `DRDY` strobe and confirm monotonically increasing codes with
   increasing input — a coarse functional proof before any linearity claim.
3. **Static linearity (INL/DNL).** A code-density (histogram) test: drive
   `PINP` with a slow ramp or a low-distortion sine referenced to `V_CM`,
   capture `C9..C0` on every `DRDY` over many periods, and derive INL/DNL
   from the code histogram against the ideal transition levels. Compare
   against the ratified `< 1 LSB` bound and the `< 0.5 LSB` stretch (§4).
4. **Dynamic performance (ENOB, SFDR).** Drive a low-distortion, precisely
   known-frequency sine (near Nyquist, coherent with `CLK`) into `PINP`/
   `PINN`, capture a long, gap-free record of `C9..C0` via `DRDY`-strobed
   digital capture, and run an FFT to extract SNDR/ENOB and SFDR. Repeat
   across the supply corners the harness can reach on the daughterboard
   (2.97/3.30/3.63 V) to check against the simulated PVT grid in §4.
5. **Offset and gain.** Apply known DC differential inputs at several
   common-mode points; derive static offset and gain error from the
   resulting code, and compare against the ≤ 2 LSB / ≤ 0.5 LSB bounds.
6. **CMRR.** Sweep the common-mode input voltage at fixed differential
   input and measure the resulting code shift, extrapolating to the ratified
   ±100 mV band the way the simulated evidence already does (§4) — the
   silicon measurement is a chance to close the "extrapolated, not measured"
   caveat on that row.
7. **Power.** Measure `V_DD` supply current at 1 MS/s under a representative
   input, and compare against the simulated power budget (§4), across the
   available supply/temperature range.
8. **Clock margin.** Sweep `CLK` frequency up from 16 MHz toward the
   2 MS/s / 32 MHz stretch point and record where functional decode or
   linearity first degrades, since the stretch rate was never closed in
   simulation (§4).
9. **Digital sequencer/output-register verification, once built** (§7 item
   5): re-run steps 2–4 as a differential check against the same
   measurements taken with the rung-1 behavioral model in simulation, the
   same sign-off comparison DR-0010 already specifies for the transistor-
   level netlist once it exists.

---

## 6. Input interface note

- **Single-ended vs. differential**: selectable at run time via `MODE` (1 =
  differential, 0 = single-ended, tie the unused input pin to `V_CM` in
  single-ended mode) — [DR-0011](../../spec/decision-records/DR-0011-cdac-switching-scheme.md).
- **Full-scale range**: 0–`V_REF` single-ended; ±`V_REF` about `V_CM =
  V_REF/2` differential (differential peak-to-peak = 2×`V_REF`). At `V_REF` =
  3.3 V (the value this block has ever verified against), full scale is
  **0–3.3 V**, not 0–5.0 V — see §2.1/§4: this block's ratified device
  flavor is not rated for a 5.0 V rail, so its full-scale range does not, and
  is not proposed to, scale to the Challenge's 5.0 V analog rail.
- **Which pads carry the input and reference**: `PINP`/`PINN` (dedicated
  pads) carry the analog input; `V_REF` (bandgap-referenced bias voltage
  slot) sets the full-scale reference; `V_CM` (dedicated pad, provisional —
  see §7) sets the common-mode operating point. None of these three are
  proposed to run through the Challenge's shared/multiplexed analog lines
  (§2.2/§2.3), because each carries a source-impedance requirement a mux
  switch would directly erode.

---

## 7. Open items before the Oct 5 schematic review

1. **Digital sequencer/output-register physical implementation** (the
   largest gap, §3/§4 item 5). [DR-0023](../../spec/decision-records/DR-0023-digital-interface-device-flavor.md)
   (status: proposed, pending operator ratification) already specifies
   adopting the PDK's shipped 6 V-oxide standard-cell libraries at this
   block's existing 3.3 V rail as the path forward, and names the three
   follow-on issues (RTL/synthesis, place-and-route, static timing closure)
   to be filed once it ratifies. This is not new scope discovered by this
   proposal — it is a known, already-drafted decision waiting on the
   operator act that unblocks it.
2. **ENOB/SFDR regression** (§4 items 1) — open, tracked (issue #211,
   [DR-0025](../../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md)).
   No design fix is currently adopted; closing it needs a design change this
   proposal does not invent.
3. **Area over ratified budget** (§4 item 2) — needs operator ratification of
   [DR-0024](../../spec/decision-records/DR-0024-adc-top-area-budget-reconciliation.md)
   or a denser layout.
4. **Comparator-inclusive statistical offset population** (§4 item 3) — the
   remainder of issue #89's original scope, already tracked, not new.
5. **`V_CM` drive-impedance/decoupling budget** (§4 item 4) — genuinely new,
   surfaced while writing this proposal: this repository has a derived
   `Z_ref`/`C_dec` budget for `V_REF` ([DR-0002](../../spec/decision-records/DR-0002-reference-source.md))
   but none for `V_CM`, even though `V_CM` drives the same switch network
   every release phase and every existing testbench sources it ideally
   (zero impedance). A follow-up issue is filed for this
   (`2AMLogic/gf180-sar-adc`, filed alongside this proposal) rather than
   measured here, since it needs a small new derivation and testbench, not a
   documentation change.

None of the above blocks *submitting* this proposal by 2026-08-31 — the
proposal's own acceptance criteria are to state the design honestly at its
current maturity, not to have already closed every gap. Per the governing
2026-08-25 operator ruling recorded in the 2am Chipalooza epic, the goal is
to design against the Challenge #3 brief with this repository's own system,
not to force every row green by the deadline: if the document is ready in
time the operator submits it; if not, nothing here is rushed and no spec row
is relaxed to make the date.

---

## 8. Licensing and EDA flow

- **License**: this entire repository — schematics, generators, layout code,
  testbenches, and every evidence record cited above — is licensed
  [Apache-2.0](../../LICENSE), satisfying the Challenge's requirement for a
  standard open license with all modifiable sources public.
- **Flow**: fully open-source. Schematic capture and netlisting via
  [xschem](https://xschem.sourceforge.io/); simulation via
  [ngspice](https://ngspice.sourceforge.io/); layout, DRC, LVS, and parasitic
  extraction via [KLayout](https://www.klayout.de/) driven by
  [klayout-tools](https://github.com/2AMLogic/klayout-tools/) (`klt`); the
  gf180mcu PDK fetched and pinned via [volare](https://github.com/efabless/volare)
  under the standard `PDK_ROOT`/`PDK` environment convention this repository
  uses throughout (`docs/environment-setup.md`), the same convention
  IIC-OSIC-TOOLS/ciel-based flows use — this repository's toolchain is
  interoperable with, though not itself built on top of, either container.
  Every simulation record cites the exact pinned toolchain versions
  (`sim/toolchain.json`) that produced it, so any reviewer can re-run the
  evidence this proposal cites from a clean checkout.
