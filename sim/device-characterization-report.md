# gf180mcu device characterization for the SAR ADC

**Status**: complete for the devices this ADC's accuracy hangs on (CDAC
capacitor, sampling switch, comparator input pair), with four explicitly
recorded data gaps — see [Gaps and what they cost](#gaps-and-what-they-cost).

**Scope**: this report *summarizes*. It creates no numbers of its own. Every
value below cites the append-only evidence record it came from, and every
record cites the testbench, the frozen netlist snapshot and the raw per-corner
logs that produced it (`sim/README.md`). Where a number is **derived** from a
measured one by arithmetic, or **assumed** rather than measured, it is labelled
as such inline — a reader must never have to guess which of the three a figure
is.

**This report is device-level, not full-ADC.** It predates ratification and
post-layout extraction (dated 2026-07-31) and is deliberately kept scoped to
individual devices rather than refreshed to cover converter-level rows. For
the aggregated, dated, per-spec-row full-ADC characterization status, see
[`sim/characterization-summary.md`](characterization-summary.md).

**Corner conventions** (all records, per `CLAUDE.md`): process corners from the
harness's corner bundles, temperature −40 / 27 / 125 °C, supply 2.97 / 3.30 /
3.63 V (3.3 V ±10 %). "Nominal" below always means `tt_27c_3.30v`. Full-factorial
grids: 45 points on the `mos` corner set, 63 on the `cdac` set.

**PDK under test**: gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
ngspice-46, MIM metal stack `m4m5`. Pinned in `sim/toolchain.json` and checked
before every run; a drifted toolchain is a hard error, so no number here can
silently come from a different model set.

## Evidence index

| Experiment | Record | Grid | Answers |
|---|---|---|---|
| `sim/device-cdac-cap/` | [`20260731-191150-5f5288b`](device-cdac-cap/records/20260731-191150-5f5288b.md) | 7 × 3 × 3 = 63 | MiM/MOS-cap density, voltage coefficient, temperature coefficient |
| `sim/device-switch-ron/` | [`20260731-191216-5f5288b`](device-switch-ron/records/20260731-191216-5f5288b.md) | 5 × 3 × 3 = 45 | R_on vs input level, NMOS / PMOS / T-gate |
| `sim/device-switch-charge-injection/` | [`20260731-195006-5f5288b`](device-switch-charge-injection/records/20260731-195006-5f5288b.md) | 45 | pedestal and its input-dependence |
| `sim/device-switch-leakage/` | [`20260731-195001-5f5288b`](device-switch-leakage/records/20260731-195001-5f5288b.md) | 45 | off-state hold-node leakage |
| `sim/device-comparator-gm-id/` | [`20260731-191813-5f5288b`](device-comparator-gm-id/records/20260731-191813-5f5288b.md) | 45 | gm/Id, constant-current V_th |
| `sim/device-comparator-flicker-noise/` | [`20260731-191945-5f5288b`](device-comparator-flicker-noise/records/20260731-191945-5f5288b.md) | 45 | noise density, flicker corner, both `fnoicor` settings |
| `sim/device-mismatch-mc/` | [`20260731-195043-5f5288b`](device-mismatch-mc/records/20260731-195043-5f5288b.md) | 45 × 300 MC | Pelgrom A_Vt |
| `sim/tools/pdk_mismatch_audit.py` | (script, run it) | n/a | what the PDK does and does **not** model |

`sim/device-cdac-cap/records/20260731-155428-860c970.md` is the earlier
harness-bootstrap record for the same experiment. The record above
**supersedes** it: that run's `cmos_ff` value (224.6 fF) was taken at a
partially-charged bias, because the AC-probe nodes had no DC return path, the
operating point was singular, and ngspice silently fell back to a transient
op. The MiM columns are unaffected to every printed digit.

## Data-provenance legend

Every number carries one of these tags, per `sim/README.md` §
Characterization-record variant.

| Tag | Meaning |
|---|---|
| `simulated` | measured from the PDK's own ngspice device models by a committed testbench over a stated PVT grid |
| `model-card-monte-carlo` | derived from the PDK model card's statistical section, exercised by a real Monte Carlo run |
| `model-card-value` | read out of the model card, **not** exercised — usually because the model card defines a parameter the simulated deck does not apply |
| `literature-assumption-with-derating` | not in the PDK at all; a stated assumption with a stated derating, flagged for replacement by foundry data |
| `derived` | arithmetic on a number above, shown so the derivation is auditable |

---

## 1. CDAC capacitors — feeds #8, #14

Evidence: [`device-cdac-cap/records/20260731-191150-5f5288b.md`](device-cdac-cap/records/20260731-191150-5f5288b.md)
(63-point PVT grid on the `cdac` corner set: `tt`, `cap_ff/ss`, `mim_ff/ss`,
`moscap_ff/ss`).

### 1.1 Which capacitor devices exist

`simulated` + audit (`sim/tools/pdk_mismatch_audit.py`, finding
`mom-capacitor-model`).

The open gf180mcu PDK ships **three** MiM flavors (1.0 / 1.5 / 2.0 fF/µm²,
named after the metal pair they sit between — `m4m5` for the `gf180mcuD`
variant) and MOS capacitors. It ships **no MoM / lateral-flux / finger
capacitor model of any kind** — not in `sm141064.ngspice`, not in
`sm141064_mim.ngspice`. The only capacitor subckts defined across both files
are `cap`, `cap_nmos_03v3(_b)`, `cap_pmos_03v3(_b)`, `cap_nmos_06v0(_b)`,
`cap_pmos_06v0(_b)` and the MiM set.

**Consequence for #8**: the MoM alternative cannot be evaluated by simulation
at all in this PDK. A MoM-based CDAC would have to be substantiated by
parasitic extraction of a drawn structure, which is a different (and much
heavier) evidence path than a model corner. This is a PDK limitation, recorded
rather than papered over, and it is a live input to the CDAC topology
decision — not a reason to assume MoM is unavailable in silicon.

### 1.2 Effective density vs unit size — `simulated`

Effective density **rises** as the unit cap shrinks, because perimeter fringe
(`c_capsw`) is a larger fraction of a small plate. This is the opposite of the
intuition that a small cap loses density, and #8 needs it to convert a unit-cap
area budget into femtofarads.

2.0 fF/µm² flavor, square units, nominal corner (`tt_27c_3.30v`):

| Drawn unit | Area | C measured | Effective density |
|---|---|---|---|
| 2 × 2 µm | 4 µm² | 9.867 fF | **2.467 fF/µm²** |
| 5 × 5 µm | 25 µm² | 54.52 fF | 2.181 fF/µm² |
| 10 × 10 µm | 100 µm² | 208.54 fF | 2.085 fF/µm² |
| 20 × 20 µm | 400 µm² | 815.09 fF | 2.038 fF/µm² |

All three flavors at 10 × 10 µm, nominal: 2.0 fF/µm² → 208.54 fF; 1.5 fF/µm²
→ 162.17 fF; 1.0 fF/µm² → 111.90 fF.

Over the full 63-point grid the 2.0 and 1.0 flavors move **±10 %** (20 %
peak-to-peak, entirely on the process axis: `mimcap_ff` → `mimcap_ss`), and the
1.5 flavor moves **±15 %** (31 % peak-to-peak) — a wider process window that
#8 should weigh against its intermediate density. Supply has zero effect;
temperature contributes ~0.2 % (see 1.4).

`derived`: the measurements are reproduced to 4 significant figures by the
model card's own geometry law, C = 1.99 fF/µm² · W·L + 0.2383 fF/µm · 2(W+L)
(10 × 10: 199 + 9.53 = 208.53 fF vs 208.538 measured), so #8 can interpolate
to any unit size rather than being limited to the four measured points.

### 1.3 Matching — **the PDK has none.** See §5.1.

This is the single largest gap in this report and it is covered in full in
[Gaps and what they cost](#51-cdac-capacitor-matching-is-not-in-this-pdk),
including the requirement curve #8 can size against in the meantime.

### 1.4 Temperature coefficient — `simulated`

Measured *inside* every deck rather than differenced across the grid's
temperature axis: three instances of each flavor are pinned to absolute
−40 / 27 / 125 °C by a per-instance `dtemp` offset, so the tempco is a checked
quantity at all 63 PVT points instead of arithmetic a reader performs on the
record table. The grid's own temperature axis is the independent cross-check
and agrees to every printed digit.

| Device | TC over −40 → 125 °C | Model card |
|---|---|---|
| MiM 2.0 fF/µm² | **+12.66 ppm/K** | tc1 = 1.46e-5, tc2 = −5.55e-8 |
| MiM 1.0 fF/µm² | **+12.85 ppm/K** | tc1 = 1.302e-5, tc2 = −4.93e-9 |
| MiM 1.5 fF/µm² | **+38.19 ppm/K** | tc1 = 4.0604e-5, tc2 = −6.90e-8 |
| MOS cap 3.3 V | **exactly 0** | no temperature term in the model at all |

Two findings worth carrying forward:

- The **1.5 fF/µm² flavor is 3× worse thermally** than either of the other two
  — not something one would guess from its intermediate density. Combined with
  its wider ±15 % process window (§1.2), the middle flavor is the worst of the
  three on both axes.
- The tempco is a *ratio*, so the mimcap process multiplier cancels out of it
  exactly: it reads the same at `mimcap_ff` and `mimcap_ss`. That is asserted
  as a check (`max_spread_pct_by_axis[process] = 0.1`), not merely observed.
- For a CDAC, a tempco common to every unit cap in the array **cancels in the
  capacitor ratio** and does not by itself cause INL/DNL. It matters for
  absolute values (settling time constants, kT/C, reference loading), and it
  would matter for linearity only via a temperature *gradient* across the
  array, which is a layout question (#17), not a device question.

### 1.5 Voltage coefficient — a modelling gap, `simulated` + `model-card-value`

Measured VCC of the MiM cap over 0 → 3.3 V: **exactly zero**, at all 63 PVT
points.

That is not a property of the capacitor; it is a property of the deck. The
gf180mcu MiM model card defines `c_vcr1` / `c_vcr2` for every flavor, but
`sm141064_mim.ngspice` has the bias-dependent instance line

```
* c_cap 1 2 c='c_c0*(1+c_vcr1*v(1,2)+c_vcr2*v(1,2)*v(1,2))*(1+mc_c_cox_2p0fF)'
```

**commented out**, and instantiates a fixed `.MODEL C cap=c_c0` instead.
Independently audited by `sim/tools/pdk_mismatch_audit.py`
(finding `mim-voltage-coefficient-active`). The zero is asserted as a check
with a ±1 ppm/V band, so a future PDK revision that wires `c_vcr*` in fails
loudly here rather than silently changing every CDAC record.

The datasheet coefficients, `model-card-value` (**not** in the simulated
path — do not treat these as measured):

| Flavor | `c_vcr1` (1/V) | `c_vcr2` (1/V²) |
|---|---|---|
| MiM 2.0, plate side > 5 µm | +8.742e-6 | +9.188e-6 |
| MiM 2.0, plate side ≤ 5 µm | **−81e-6** | +16.7e-6 |
| MiM 1.5 | −4.5152e-5 | +9.748e-6 |
| MiM 1.0 | +6.079e-6 | +1.268e-6 |

**This is a real design input, not a footnote.** The 2.0 fF/µm² card makes
`c_vcr1` *geometry-dependent*, and the small unit caps a 10-bit array actually
wants (≤ 5 µm on a side) carry a coefficient **9× larger and of opposite
sign** to the 10 × 10 µm device. `derived`: at −81 ppm/V, a unit cap swinging
the full 3.3 V changes by 267 ppm — about 0.27 LSB of a 10-bit converter's
full-scale capacitance if it applied to the whole array, and it does not apply
uniformly, so it is a genuine linearity term. #8 must apply this by hand;
**no simulated CDAC linearity result in this repo contains it.**

### 1.6 MOS capacitor — the contrast case, `simulated`

The 3.3 V NMOS cap at 10 × 10 µm reads 2.45 fF at 0 V bias and 398.3 fF at
3.3 V: a voltage coefficient of **4.9e7 ppm/V**, i.e. a factor of 163, not a
part-per-million effect. Its C(V) is a `tanh` and is fully saturated above
~0.7 V, which is why the earlier corner record saw no supply sensitivity in
the 2.97–3.63 V window and why a supply-axis floor was the wrong way to probe
it.

This is the quantitative reason a MOS capacitor is not a CDAC unit element in
a converter whose input swings rail to rail. It remains usable as a decoupling
or fixed-bias element.

---

## 2. Sampling switches — feeds #10, #8

Device geometry pinned for all three switch experiments: NMOS W = 10 µm,
PMOS W = 20 µm (2:1 for the mobility ratio), both L = 0.28 µm (the 3.3 V
minimum). The transmission gate is exactly those two in parallel. R_on scales
as ~1/W and injected charge as ~W·L, so #10 can rescale; the flatness ratio is
W-independent to first order.

### 2.1 R_on vs input level, and the worst corner — `simulated`

Evidence: [`device-switch-ron/records/20260731-191216-5f5288b.md`](device-switch-ron/records/20260731-191216-5f5288b.md).
Method: source held at the input level, 10 mV forced across the channel, deep
triode, R_on = 10 mV / |I|. Seven input points from rail to rail.

**The input ladder tracks the supply** (f · V_dd, f = 0…1), not a fixed
0–3.3 V ladder. At the 2.97 V corner a 3.3 V input would sit 330 mV above the
rail, forward-bias the PMOS source-body junction, and measure a diode. The
corollary is itself a constraint for #1 and #10: **a full-scale 0–3.3 V input
is not samplable at a drooped 2.97 V supply.**

| Configuration | Nominal (`tt_27c_3.30v`) | Worst over 45 points |
|---|---|---|
| T-gate, best input point (0 V) | 156.9 Ω | 235.3 Ω @ `ss_125c_2.97v` |
| **T-gate, worst input point** | **299.4 Ω** (at 2/3 rail) | **570.4 Ω @ `ss_125c_2.97v`** |
| T-gate flatness (worst/best input) | 1.91 | **3.29 @ `ss_-40c_2.97v`** |
| NMOS-only, 0 V input | 156.9 Ω | 235.3 Ω @ `ss_125c_2.97v` |
| NMOS-only, above ~2/3 rail | > 10⁹ Ω | device is off — not usable |
| PMOS-only, full-rail input | 220.7 Ω | 323.3 Ω @ `ss_125c_2.97v` |
| PMOS-only, below ~1/3 rail | > 10⁹ Ω | device is off — not usable |

**There are two different worst corners and #10 needs both.**

- Worst *absolute* R_on is `ss / 125 °C / 2.97 V` — slow, hot, low supply.
  This is the settling-time corner: 570 Ω into a 2.5 pF array is τ = 1.43 ns,
  and 10-bit settling (7.6 τ) needs 10.8 ns, `derived`.
- Worst *flatness* is `ss / −40 °C / 2.97 V` — slow, **cold**, low supply,
  where V_th is highest and the mid-range overdrive collapses hardest. R_on
  varies 3.29× across the input range there. Since R_on modulation with input
  is a distortion mechanism, a design signed off only at the hot corner would
  miss this.

Neither single-device switch spans the rail: the NMOS dies above ~2/3 V_dd and
the PMOS below ~1/3 V_dd, both by 7+ orders of magnitude. A plain transmission
gate does span it, at a 1.9–3.3× flatness cost.

### 2.2 Charge injection and clock feedthrough — `simulated`

Evidence: [`device-switch-charge-injection/records/20260731-195006-5f5288b.md`](device-switch-charge-injection/records/20260731-195006-5f5288b.md).
Hold cap **2.5 pF** (a 10-bit array at C_u = 5 fF). Clock edge **1 ns** —
load-bearing, see below. The pedestal is measured *across the falling edge*
(V at 1.5 µs minus V at 0.9999 µs), so incomplete tracking during the on-phase
is excluded from the number by construction.

Nominal corner (`tt_27c_3.30v`), pedestal in mV onto 2.5 pF:

| Input level | NMOS-only | Transmission gate |
|---|---|---|
| 0 V | −6.26 | −3.68 |
| 1/4 rail | −6.31 | −2.87 |
| 1/2 rail | −5.36 | +1.56 |
| 3/4 rail | −3.87 | +7.40 |
| full rail | (device off) | +10.51 |
| **input-dependent spread** | **2.44 mV** | **14.19 mV** |
| spread over 45 PVT points | 1.94 – 3.29 mV | 11.88 – 16.86 mV |

Three results that matter to the topology choice:

1. **The transmission gate is 5.8× WORSE than the NMOS alone** on the term
   that actually hurts. A constant pedestal is an offset and is harmless; the
   *input-dependent* part becomes distortion and INL. At W_p = 2·W_n the PMOS
   injects more charge than the NMOS over most of the range and with the
   opposite sign, so the two do not cancel — they produce a pedestal that
   swings through zero and lands 14 mV away from where it started. Charge
   cancellation in a T-gate is a sizing problem, not a free property of the
   topology, and this record is the evidence for that at this sizing.
2. **`derived`, using an illustrative 3.3 V full scale (1 LSB = 3.22 mV;
   pending the ratified spec, #1)**: the NMOS-only input-dependent spread is
   **0.76 LSB** and the T-gate's is **4.4 LSB**. Both are far above ½ LSB.
   **Some compensation scheme is mandatory** — bottom-plate sampling, a dummy
   switch, or a bootstrapped switch. No raw switch of this size meets a 10-bit
   budget on a 2.5 pF array.
3. **Only ~30 % of the mid-scale NMOS pedestal is channel charge.** A control
   branch holds the input at V_dd so the NMOS never turns on and no channel
   exists; whatever pedestal it shows (−3.74 mV nominal) is pure gate-overlap
   clock feedthrough. Feedthrough and injection cannot be separated by
   observing one node, which is why that branch exists. **Compensation schemes
   that target channel charge only (dummy switches) address the smaller
   term.**

Two caveats #10 must respect:

- **The 1 ns clock edge is an assumption, not a measurement.** Injected charge
  splits between the driven source and the floating hold node in a ratio set
  by how fast the channel collapses relative to how fast charge escapes, so
  the pedestal is a function of clock slope. Re-run this at the real edge rate
  before committing to a topology.
- **1/C_hold scaling is measured, not assumed**: repeating one point at 250 fF
  gives a ratio of 8.47 (nominal; 7.58–9.20 over PVT), against the ideal 10.
  So the numbers rescale to a different array size approximately as 1/C_hold,
  with a ~15 % error from the on-resistance-dependent charge split and the
  overlap-cap divider. Use the measured ratio, not the ideal one.

No dummy switch, bootstrapping or bottom-plate sampling is modelled here.
These are the **raw device numbers a compensation scheme has to work
against**.

### 2.3 Off-state leakage at 125 °C — `simulated`, and a lower bound

Evidence: [`device-switch-leakage/records/20260731-195001-5f5288b.md`](device-switch-leakage/records/20260731-195001-5f5288b.md).

| Branch | 125 °C nominal (`tt_125c_3.30v`) | 125 °C worst (`ff_125c_3.63v`) |
|---|---|---|
| NMOS off, V_ds = 3.3 V | 2.31 nA | 28.98 nA |
| NMOS off, hold at mid-rail | 0.80 nA | 8.01 nA |
| **T-gate net into the hold node** | **88.8 pA** | **1.096 nA** |
| PMOS off | ≤ 10 fA (**at the numerical floor**) | ≤ 10 fA |
| MiM unit cap dielectric (10 × 10 µm) | 0.31 fA | 0.35 fA |

`derived` hold-droop, 2.5 pF array, 1 µs hold: **35.5 µV (0.011 LSB) at
nominal, 438 µV (0.136 LSB) at the worst corner** — using the same
illustrative 1 LSB = 3.22 mV. Comfortably inside ½ LSB, **but see the lower-bound
caveat immediately below before spending that margin.**

Also note the T-gate is **not** the sum of its halves: the NMOS and PMOS
leakages oppose, and at cold corners they cancel to sub-fA residuals. Those
residuals are the difference of two floor-level currents and are not
measurements of anything.

Two null controls make this record's limits provable rather than asserted:

- **Junction leakage is not modelled at all.** The same NMOS with 1000 µm² of
  declared source/drain junction area (~100× any plausible diffusion) leaks
  *identically* to the zero-area default, at every temperature and corner
  (ratio = 1.000000). The gf180mcu 3.3 V FET cards carry junction
  *capacitance* (Cj, Cjsw, Pb) but **no junction saturation current density**
  (no JS/JSW/JSWG). Independently audited by `pdk_mismatch_audit.py`
  (`mos-junction-leakage`). **Every figure above is channel leakage only, and
  the 125 °C column is therefore a LOWER BOUND.** Real drain-body junction
  leakage is strongly temperature-activated and matters most exactly where
  this budget is tightest. #8/#10 must budget it from foundry data, not from
  this PDK.
- **The deck's own numerical floor is measured, not assumed.** With
  `gmin = 1e-18` a ~10 fA residual remains. A 20/2 PMOS — 7× the channel
  length, so any real subthreshold current would collapse — reads the *same*
  current as the 20/0.28 device at every point (ratio = 1.000000). So the
  whole PMOS branch, and the −40 °C column generally, are **upper bounds of
  order 10 fA, not measurements**. The 125 °C NMOS and T-gate columns sit 4–5
  orders of magnitude above the floor and are real.

Gate leakage is not separately reported: these are thick-oxide 3.3 V devices
where tunnelling is negligible next to subthreshold and junction leakage, and
the PDK's BSIM cards do not enable a gate-current model.

---

## 3. Comparator input devices — feeds #9, #14

### 3.1 gm/Id — `simulated`

Evidence: [`device-comparator-gm-id/records/20260731-191813-5f5288b.md`](device-comparator-gm-id/records/20260731-191813-5f5288b.md).
gm is a **finite difference against a 1 mV-offset replica**, not ngspice's
internal `@m[gm]` vector: it is what a bench would measure, it survives changes
in how the simulator exposes internal device parameters, and it works on the
subckt-wrapped devices this PDK ships. 1 mV against ~26 mV of thermal voltage
puts the second-order error below 0.1 %. Bodies tied to sources (zero-V_sb
device parameters); all bias points diode-connected, i.e. at the edge of
saturation.

W/L = 10/1 µm, gm/Id in V⁻¹, nominal (min–max over the 45-point grid):

| I_d | NMOS | PMOS |
|---|---|---|
| 0.2 µA | 24.33 (18.53 – 30.56) | 21.34 (16.13 – 27.41) |
| 1 µA | 21.65 (16.98 – 26.17) | 16.95 (13.13 – 21.28) |
| 10 µA | 13.52 (10.84 – 16.42) | 7.50 (6.07 – 9.07) |
| 100 µA | 4.85 (3.68 – 6.20) | 2.21 (1.81 – 2.66) |

Candidate input-pair geometry, W/L = 40/0.5 µm at 10 µA per side:

| | gm/Id (V⁻¹) | gm (µS) | V_gs / V_sg (V) |
|---|---|---|---|
| NMOS | **20.71** (16.42 – 24.72) | **207.1** (164.2 – 247.2) | 0.657 (0.442 – 0.841) |
| PMOS | **16.78** (13.00 – 21.09) | **167.8** (130.0 – 210.9) | 0.824 (0.587 – 1.021) |

The gm/Id spread across the full PVT grid is **~40 %** for either candidate,
dominated by the temperature axis (36 % of it) rather than by process (4 %).
A comparator noise or speed budget written at 27 °C only will be optimistic by
roughly that factor at 125 °C.

### 3.2 Threshold voltage — `simulated`

Constant-current definition, V_th = V_gs at I_d = 100 nA · (W/L) — the
definition foundry datasheets quote, so these are directly comparable against
one. This is **not** the model's internal `vth0` and will differ from it.

| Device | Nominal | Min (`ff_125c_2.97v`) | Max (`ss_-40c_2.97v`) |
|---|---|---|---|
| NMOS, L = 1 µm | **0.635 V** | 0.420 V | 0.817 V |
| NMOS, L = 0.28 µm | 0.574 V | 0.365 V | 0.750 V |
| PMOS, |V_th|, L = 1 µm | **0.819 V** | 0.584 V | 1.014 V |
| PMOS, |V_th|, L = 0.28 µm | 0.747 V | 0.498 V | 0.951 V |

**This discharges the `V_th ≈ 0.7 V [E4]` assumption carried in
`spec/prior-art-survey.md`.** The nominal NMOS value is 0.635 V, but the
number a design must survive is 0.817 V at slow/cold — 17 % above the
assumption, and the same corner that produced the worst switch flatness in
§2.1. Short-channel roll-off is ~60 mV from L = 1 µm to L = 0.28 µm.

### 3.3 Threshold mismatch A_Vt — `model-card-monte-carlo`

Evidence: [`device-mismatch-mc/records/20260731-195043-5f5288b.md`](device-mismatch-mc/records/20260731-195043-5f5288b.md).

**Method** (stated because the method is where mismatch extractions go wrong):
each pair is two identically-sized diode-connected devices in **deep
subthreshold** (I_d/(W/L) = 1 nA), where
σ²(ΔV_gs) = σ²(ΔV_th) + (n·kT/q · σ(Δβ/β))² and the second term is ~0.08 mV
against ~2.4 mV — 0.1 % in quadrature. So σ(ΔV_gs) *is* σ(ΔV_th), well inside
the Monte Carlo's own statistical error. **N = 300** samples per PVT point,
`setseed 20260731`, `sw_stat_mismatch = 1`, `sw_stat_global = 0`
(mismatch-only). Statistical precision on each σ is 1/√(2N) = **4.1 %**.
Swept over all five MOS corners × 3 temperatures × 3 supplies.

| Pair | Geometry | √(W_eff·L_eff) | σ(ΔV_th) measured | **A_Vt back-extracted** | Model card |
|---|---|---|---|---|---|
| A | NMOS 10/1 | 2.930 µm | 2.460 mV | **7.208 mV·µm** | 7.148 |
| B | NMOS 2.5/1 | 1.487 µm | 4.665 mV | **6.934 mV·µm** | 7.148 |
| C | NMOS 10/4 | 6.236 µm | 1.148 mV | **7.158 mV·µm** | 7.148 |
| D | PMOS 10/1 | 2.930 µm | 2.372 mV | **6.949 mV·µm** | 6.660 |

All four land within 4.4 % of the card — i.e. within about one standard error.
Three NMOS areas spanning **17.6×** agree on one coefficient, which is the
Pelgrom 1/√area law *verified* rather than assumed; the measured area-scaling
ratios are 1.896 (predicted 1.971) and 0.4666 (predicted 0.4699).

Three things #9 and #14 must carry forward:

- **These are PAIR sigmas.** `fets_mm` applies
  `mis_vth = agauss(0, 0.7071·par_vth·1e-6/√(L_eff·W_eff), 1)` to each device
  independently; the 1/√2 means `par_vth` is A_Vt in the **pair** convention,
  σ(ΔV_th) = A_Vt/√(W_eff·L_eff). A single device's own sigma is
  A_Vt/√(2·W_eff·L_eff). Do not apply the pair number to a single device.
- **Use EFFECTIVE area, not drawn area.** L_eff = L − 0.15 µm and
  W_eff = W + 0.1 µm. At L = 0.28 µm the effective length is 0.13 µm — less
  than half the drawn value — so scaling A_Vt by drawn area understates
  mismatch by ~45 % at minimum length.
- **A_Vt is corner-independent in this PDK, and that is now measured.**
  `par_vth` lives in the `fets_mm` subckt, not in any corner `.lib` section, so
  the coefficient cannot move with process by construction. Sweeping all 45
  points with common random numbers confirms it: the measured σ moves **< 0.8 %**
  across the entire grid. #14 can therefore treat corner and mismatch as
  separable — asserted as a `max_spread_pct_by_axis[process] = 3 %` ceiling on
  the record, not merely observed.

`derived`, what this means for a comparator input pair: at the candidate
40/0.5 µm geometry, √(W_eff·L_eff) = √(40.1 × 0.35) = 3.746 µm, so
σ(ΔV_th) = 7.208/3.746 = **1.92 mV** for the pair. A 3σ input-referred offset
of 5.8 mV is **1.8 LSB** at the illustrative 1 LSB = 3.22 mV — i.e. offset
cancellation is required, and #9 should size L for area rather than for speed
if it wants that number down (area, not W alone, is what buys matching).

### 3.4 Noise and the flicker corner — `simulated`

Evidence: [`device-comparator-flicker-noise/records/20260731-191945-5f5288b.md`](device-comparator-flicker-noise/records/20260731-191945-5f5288b.md).
Method: `.noise` with a 0 V AC source in series with the gate of a
diode-connected device at fixed current, so `inoise_spectrum` is the
input-referred gate-voltage noise density directly, in V/√Hz. Units confirmed
independently against an ideal 1 kΩ resistor (ngspice: 4.069 nV/√Hz vs the
4kTR value 4.07 nV/√Hz).

**The flicker corner is extracted against a MEASURED thermal floor**, not
against the high-frequency end of the spectrum: the diode-connected node's own
pole distorts the density well before it settles, so a high-frequency asymptote
would be an artefact. Instead the whole sweep is repeated with every BSIM
flicker term zeroed, and `f_c = (V_n(1 Hz) / V_n,thermal)²`. That the zeroed
spectrum really is white is checked (1 Hz / 1 MHz ratio = 1.000000), and the
measured low-frequency power-law slope is **0.949 decades/decade** (checked
against a 0.85–1.1 band), which is what licenses the 1/f asymptote the
extraction assumes.

Nominal corner (`tt_27c_3.30v`), 40/0.5 µm at 10 µA:

| | V_n @ 1 Hz | V_n @ 1 kHz | thermal floor | **f_c** |
|---|---|---|---|---|
| NMOS, `fnoicor = 0` (as-extracted) | 2890 nV/√Hz | 108.9 nV/√Hz | 8.41 nV/√Hz | **118 kHz** |
| NMOS, `fnoicor = 1` (worst case) | 9557 nV/√Hz | — | 8.41 nV/√Hz | **1.29 MHz** |
| PMOS, `fnoicor = 0` | 2665 nV/√Hz | 56.4 nV/√Hz | 9.20 nV/√Hz | **83.8 kHz** |
| PMOS, `fnoicor = 1` | 9393 nV/√Hz | — | 9.20 nV/√Hz | **1.04 MHz** |
| NMOS 40/2.0 (4× area), `fnoicor = 0` | 1436 nV/√Hz | — | 9.70 nV/√Hz | **21.9 kHz** |

Over the 45-point grid: f_c(NMOS, `fnoicor=0`) 79.5 – 169 kHz; worst-case
setting 0.87 – 1.84 MHz. Thermal floor 7.01 – 10.70 nV/√Hz.

- **`fnoicor` is load-bearing and must be quoted with every flicker number.**
  gf180mcu ships a flicker-corner switch (`design.ngspice`): 0 = as-extracted
  (the default), 1 = worst case. Both settings are run at every PVT point via
  `alterparam` + `reset`, and the measured power ratio reproduces the model
  card's own `noia` ratio to 3 significant figures — 10.935 measured vs
  3.5e42/3.2e41 = 10.94 for the NMOS, 12.42 vs 4.0e42/3.2e41 = 12.5 for the
  PMOS. That agreement simultaneously proves the corner switch actually takes
  effect. **Worst case moves the flicker corner by ~11×; nothing in this repo
  should quote a flicker number without saying which setting it came from.**
- **Area scaling is measured, not cited**: 4× the gate area at identical
  current halves the noise amplitude — measured ratio **2.012** (1.99–2.07
  over the grid) against the ideal 2.000. #9 can trade input-pair area against
  flicker noise on measured evidence.
- **The PMOS advantage is modest here.** At 1 Hz the two are within 8 % of
  each other; the PMOS wins at 1 kHz and on f_c (84 kHz vs 118 kHz) because
  its spectrum falls faster, not because its 1/f floor is lower — the model
  card gives both devices the same `noia` at `fnoicor = 0` (3.2e41). Do not
  assume a PMOS input pair buys a large flicker advantage in this PDK.
- `derived` sanity check: at gm = 207 µS the measured 8.41 nV/√Hz thermal
  floor implies γ ≈ 0.88, against the long-channel 2/3 — plausible for
  L = 0.5 µm and a useful indication that the noise model is behaving.

This is a small-signal noise **density**, not a comparator noise budget.
Sampled-system noise folding, the regeneration-time-dependent noise bandwidth
of a dynamic latch, and kickback are all #9's job; what this record supplies is
the device-level input to that calculation.

---

## 4. What the PDK does and does not model

`sim/tools/pdk_mismatch_audit.py` reads the *installed* PDK's model files and
reports, per device class, which statistical constructs are present and which
are absent, quoting file and line. It exists because several findings in this
report are **negative**, and a negative claim about a model *library* cannot be
substantiated by a testbench — a simulation can only show that some effect did
not appear, never that the library does not contain it.

It is also a **regression guard**: each finding is asserted, so a PDK revision
that adds capacitor mismatch or junction leakage makes the script exit
non-zero and name the changed claim, rather than silently invalidating a report
that four downstream design issues have already consumed.

```
python3 sim/tools/pdk_mismatch_audit.py            # audit + assert (exit 1 if a finding changed)
python3 sim/tools/pdk_mismatch_audit.py --report   # audit, always exit 0
```

All eight findings hold against open_pdks `c6d73a35…`:

| Finding | State | Consequence |
|---|---|---|
| `mos-local-mismatch` | PRESENT | A_Vt is available — §3.3 |
| `resistor-local-mismatch` | PRESENT | contrast case: the PDK's authors *did* model local mismatch where they had data |
| `flicker-noise-corner-switch` | PRESENT | every flicker number must state its `fnoicor` — §3.4 |
| `cap-local-mismatch` | **ABSENT** | σ(ΔC/C) is not obtainable from this PDK — §5.1 |
| `moscap-statistics` | **ABSENT** | the MOS cap has corners but no statistical model of any kind |
| `mom-capacitor-model` | **ABSENT** | no MoM alternative can be simulated — §1.1 |
| `mim-voltage-coefficient-active` | **ABSENT** | simulated CDAC results contain no MiM VCC — §1.5 |
| `mos-junction-leakage` | **ABSENT** | hold-droop numbers are a lower bound — §2.3 |

The contrast between the first two rows and the fourth is what makes the
capacitor gap a real **data** gap rather than an oversight of the whole
statistical framework: this PDK models local mismatch wherever its authors had
data, and they did not have it for capacitors.

---

## 5. Gaps and what they cost

Four things this report could not measure. Each is stated with its
consequence and, where possible, a usable substitute — per the issue's
requirement that a missing number is a finding to record, not to omit.

### 5.1 CDAC capacitor matching is not in this PDK

**The gap.** The gf180mcu open PDK provides **no local (device-to-device)
mismatch data for any capacitor**. Its `mimcap_statistical` section defines
three `mc_c_cox_*` terms, and every one of them is gated on `sw_stat_global`
— a **die-global** multiplier. A die-global capacitance shift cancels exactly
in a capacitor *ratio*, and a CDAC's linearity is nothing but capacitor
ratios, so those terms contribute **zero** DNL/INL. There is no
`moscap_statistical` section at all. Audited: `pdk_mismatch_audit.py`,
findings `cap-local-mismatch` and `moscap-statistics`.

**Therefore σ(ΔC/C) for the CDAC unit cap cannot be obtained from this PDK by
any means**, and no Monte Carlo run against these models — however large —
will produce a non-zero CDAC mismatch distribution. #14 must know this before
it calibrates anything: a Monte Carlo CDAC result from this PDK that shows
mismatch-driven INL is measuring something other than capacitor mismatch.

**Working assumption**, tagged `literature-assumption-with-derating` and
flagged for replacement:

- The **functional form** is not in dispute: σ(ΔC/C) = A_C / √(A_unit), the
  Pelgrom area law, with A_C in %·µm.
- **A_C = 1.0 %·µm** as an order-of-magnitude planning value for MiM
  capacitors in a mature 0.18 µm-class process. **This value has no verified
  citation attached in this repo** — it is a planning placeholder, not a
  literature result this report can point you at, and it must not be treated
  as one.
- **Apply a 2× derating for budgeting: use A_C = 2.0 %·µm** until foundry data
  replaces it. The right source is GlobalFoundries' own 0.18 µm process design
  manual MiM matching data, which is not in the open PDK.

**What #8 should actually size against.** Rather than lean on that assumption,
#8 can invert the problem — the *requirement* is derivable from the
architecture alone and does not depend on A_C at all. `derived`, for a 10-bit
binary-weighted array of nominally identical unit caps with independent random
σ_u = σ(ΔC/C):

- worst-case DNL is at the MSB transition: σ(DNL)_max = √(2^N − 1)·σ_u = **32.0·σ_u** LSB
- worst-case INL is at mid-scale: σ(INL)_max = (√(2^N)/2)·σ_u = **16.0·σ_u** LSB
- for 3σ DNL ≤ 0.5 LSB: **σ_u ≤ 0.52 %** ← binding
- for 3σ INL ≤ 0.5 LSB: σ_u ≤ 1.04 %

Combining that requirement with the measured density law of §1.2 gives the
unit-cap size, and it is *extremely* sensitive to A_C — which is exactly why
obtaining the real number matters:

| Assumed A_C | Required unit area | Unit side | C_unit (measured density law) | 1024-unit array |
|---|---|---|---|---|
| 1.0 %·µm (planning) | 3.68 µm² | 1.92 µm | 9.2 fF | 9.4 pF |
| **2.0 %·µm (derated)** | **14.7 µm²** | **3.84 µm** | **33.0 fF** | **33.8 pF** |

A 2× error in A_C is a **3.6×** error in array capacitance, which propagates
straight into reference-driver sizing, settling time and area. #8 should
parameterize its sizing in A_C and commit to a number only when foundry data
lands.

Note also from §1.5: a unit cap at or below 5 µm on a side carries a
**−81 ppm/V** datasheet voltage coefficient, 9× larger and opposite in sign to
the 10 × 10 µm device — and both candidate sizes above are in that regime.

### 5.2 MOS junction leakage is not modelled

Covered in §2.3 with its null control. **All hold-droop figures in this report
are lower bounds.** The 125 °C worst-corner droop of 438 µV (0.136 LSB) has
unquantified headroom above it. #8/#10 must budget junction leakage from
foundry data.

### 5.3 Current-factor (β) mismatch is not characterized

`fets_mm` also carries `par_k` (0.007008 NMOS, 0.002833 PMOS), applied as
`mulu0 = 1 − mis_k·sw_stat_mismatch`. The A_Vt extraction in §3.3 biases
deliberately in deep subthreshold precisely so the β term is negligible and
the threshold term is clean — which means β mismatch is **not separable** from
that record and is not measured anywhere in this repo. Extracting it needs a
strong-inversion companion pair and a quadrature subtraction against §3.3's
numbers. Until then, #9 should treat `par_k` as `model-card-value` provenance,
not as something measured. For a comparator running its input pair at moderate
overdrive this is a second-order term next to A_Vt, but it is not zero.

### 5.4 Two smaller caveats

- **The PMOS flicker slope is unchecked.** `flicker_slope_pow_dec` is asserted
  for the NMOS (0.949) but not for the PMOS, whose 1 Hz → 1 kHz behaviour
  implies a steeper ~1.12 slope. The PMOS f_c values in §3.4 therefore rest on
  a 1/f asymptote that is measured for the NMOS and assumed for the PMOS. Treat
  f_c(PMOS) as indicative.
- **Everything here is schematic-level.** No parasitic extraction, no layout.
  Post-layout re-runs belong in the same experiment directories with
  `Netlist provenance: extracted` and a `Supersedes` delta (#17).

---

## 6. Verification of this report's own evidence

Everything above rests on the corner runner actually switching corners. That
failure is silent — a wrong model include or a mistyped bundle name produces
plausible numbers with no error — so it is tested rather than trusted:

- **All eight committed testbenches are in `sim/selftest.sh`'s negative-control
  stage.** Each is re-run with every model section forced to typical
  (`--sabotage-corners`) and **must fail** its per-axis sensitivity checks; a
  pass there means corner switching is not taking effect and every record from
  that testbench is worthless.
- **Three of the six new testbenches did not detect sabotage when first
  written**, because their per-axis floors sat on the temperature and supply
  axes — which sabotage leaves alone. Each now carries a **process**-axis floor.
  This is the single most valuable thing the negative control did during this
  work.
- **`device-mismatch-mc` is a documented exception in kind**: its headline
  result is corner-independent *by construction*, so no honest process floor
  exists for it. It instead measures a subthreshold V_th proxy purely as a
  corner-sensitivity anchor, and asserts the corner-*invariance* of its sigma
  with a ceiling.
- **The Monte Carlo seed mechanism was verified, not assumed.** Of the three
  plausible ngspice controls, only `setseed <n>` works. `set rndseed=<n>` is
  silently ignored (two identical runs gave A_Vt = 7.03 and 6.62 mV·µm), and
  `.options seed=<n>` is actively harmful — it freezes the draw so every
  `reset` returns the identical sample and the measured sigma collapses to
  ~6e-8 mV: a Monte Carlo record with no Monte Carlo in it, and nothing in the
  output says so. The `sig_n_a_mv` lower-bound check guards that failure mode.
- **A convergence bug in the prior CDAC record was found and corrected.** Its
  AC-probe nodes had no DC return path, so the operating point was singular and
  ngspice fell back to a transient op, measuring the MOS cap at a
  partially-charged bias (224.6 fF where the model gives 398.3 fF). Every probe
  node now returns to its DC reference through a 1 TΩ resistor.

---

## 7. Summary table

Nominal = `tt_27c_3.30v`. Ranges are over the full PVT grid of the cited
record. Every row's evidence is in the [index](#evidence-index).

| Quantity | Nominal | PVT range | Provenance | § |
|---|---|---|---|---|
| MiM 2.0 density, 2 × 2 µm unit | 2.467 fF/µm² | ±10 % (process) | `simulated` | 1.2 |
| MiM 2.0 density, 10 × 10 µm unit | 2.085 fF/µm² | ±10 % (process) | `simulated` | 1.2 |
| MiM 1.5 / 1.0 density, 10 × 10 µm | 1.622 / 1.119 fF/µm² | ±15 % / ±10 % | `simulated` | 1.2 |
| MiM tempco, 2.0 / 1.0 / 1.5 | +12.66 / +12.85 / +38.19 ppm/K | corner-invariant | `simulated` | 1.4 |
| MiM voltage coefficient, simulated | **0** | 0 everywhere | `simulated` | 1.5 |
| MiM voltage coefficient, datasheet, unit ≤ 5 µm | −81 ppm/V | — | `model-card-value` | 1.5 |
| MOS-cap voltage coefficient | 4.9e7 ppm/V | — | `simulated` | 1.6 |
| σ(ΔC/C) for the unit cap | **not obtainable** | — | see §5.1 | 5.1 |
| T-gate R_on, worst input | 299 Ω | 189 – **570 Ω** @ `ss_125c_2.97v` | `simulated` | 2.1 |
| T-gate R_on flatness | 1.91 | 1.43 – **3.29** @ `ss_-40c_2.97v` | `simulated` | 2.1 |
| NMOS pedestal, input-dependent part | 2.44 mV | 1.94 – 3.29 mV | `simulated` | 2.2 |
| T-gate pedestal, input-dependent part | 14.19 mV | 11.88 – 16.86 mV | `simulated` | 2.2 |
| Clock feedthrough alone (NMOS) | −3.74 mV | −3.01 – −4.55 mV | `simulated` | 2.2 |
| T-gate leakage @ 125 °C | 88.8 pA | up to 1.10 nA @ `ff_125c_3.63v` | `simulated`, **lower bound** | 2.3 |
| gm/Id, NMOS 40/0.5 @ 10 µA | 20.71 V⁻¹ | 16.42 – 24.72 | `simulated` | 3.1 |
| gm, NMOS 40/0.5 @ 10 µA | 207 µS | 164 – 247 µS | `simulated` | 3.1 |
| V_th NMOS, L = 1 µm | 0.635 V | 0.420 – 0.817 V | `simulated` | 3.2 |
| \|V_th\| PMOS, L = 1 µm | 0.819 V | 0.584 – 1.014 V | `simulated` | 3.2 |
| **A_Vt NMOS** | **7.21 mV·µm** | < 0.8 % across the grid | `model-card-monte-carlo`, N = 300 | 3.3 |
| **A_Vt PMOS** | **6.95 mV·µm** | < 0.8 % across the grid | `model-card-monte-carlo`, N = 300 | 3.3 |
| A_beta (current-factor) | not measured | — | `model-card-value` only | 5.3 |
| **f_c NMOS 40/0.5 @ 10 µA, `fnoicor=0`** | **118 kHz** | 79.5 – 169 kHz | `simulated` | 3.4 |
| f_c NMOS, `fnoicor=1` (worst case) | 1.29 MHz | 0.87 – 1.84 MHz | `simulated` | 3.4 |
| f_c PMOS 40/0.5, `fnoicor=0` | 83.8 kHz | see §5.4 caveat | `simulated` | 3.4 |
| Thermal floor, NMOS 40/0.5 @ 10 µA | 8.41 nV/√Hz | 7.01 – 10.70 nV/√Hz | `simulated` | 3.4 |
