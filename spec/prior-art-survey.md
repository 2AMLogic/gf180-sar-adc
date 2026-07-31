# Prior-Art Survey: SAR ADC Architectures for gf180mcu

**Status:** survey / research deliverable. Not a decision record.
**Issue:** #3. **Feeds:** #1 (spec ratification), #7 (scope decisions), #8 (CDAC),
#9 (comparator), #10 (sample switch), #11 (SAR logic), #13 (testbench suite).
**Compiled:** 2026-07-30.
**Confidentiality:** Tier 2. Stays in this repo. Do not copy into public issues or repos.

---

## 0. Scope and how to read this document

### 0.1 What this is

A survey of published and open-source SAR ADC prior art, translated into the
context of *this* block: a 10-bit, 1 MS/s converter on **gf180mcu at 3.3 V**,
verified with an **ngspice-only** open-source flow. Three axes are covered in
depth because they gate everything downstream:

1. CDAC switching scheme (§2) — consumed by #8
2. Comparator topology and offset cancellation (§3) — consumed by #9
3. SAR logic: synchronous vs asynchronous (§4) — consumed by #11

Plus a shorter input-sampling prior-art note (§5, context for #10), an
open-source existence-proof and portability assessment (§6), and a consolidated
shortlist with spec traceability (§7).

### 0.2 What this is *not*

This survey **stops short of writing the architecture decision records**. Each
axis ends with a shortlist and the evidence behind it; the actual ratified
choices belong in `spec/` decision records written against the template from #6,
by the owning design issues. Where this document says "recommended," read it as
"recommended input to that decision," not "decided."

No testbenches are introduced here. Per repo policy the "no claim without a
testbench" rule maps, for a literature deliverable, to **"no quantitative claim
without a citation or an explicit estimate flag."**

### 0.3 Evidence markers

Every quantitative claim below carries one of these markers. This is load-bearing:
downstream issues should treat unmarked prose as qualitative only, and should not
promote an `[E4]` or `[V]` number into a decision record without discharging it.

| Marker | Meaning |
|---|---|
| `[P]` | Published figure, with a cited source in §9. |
| `[D]` | Derived in this document from `[P]` figures and/or the README spec targets. The arithmetic is shown inline so it can be checked. |
| `[E4]` | **Estimate on assumed device data.** Depends on gf180mcu parameters that have not been characterized. Blocked on **#4**; must be re-derived from #4's extracted data before it enters a decision record. |
| `[V]` | **Verify at source.** Believed correct but not confirmed against the primary document during this compilation. Confirm before citing in a decision record. |
| `[O]` | Open-source artifact (repository / tapeout record) inspected directly on 2026-07-30. Repo state is mutable — re-check before relying on it. |

### 0.4 Target spec recap (README DRAFT, pending #1)

| Parameter | Target | Stretch |
|---|---|---|
| Resolution | 10 bit | 12 bit variant |
| Rate | 1 MS/s | 2 MS/s |
| ENOB @ Nyquist | > 9.0 | > 9.5 |
| INL / DNL | < 1 LSB | < 0.5 LSB |
| Input | 0–3.3 V single-ended + diff mode | — |
| Power @ 1 MS/s | < 1 mW | < 500 µW |
| Area | < 0.1 mm² | — |
| Interface | SPI-readable + parallel | — |

### 0.5 The three context deltas from the literature

Almost every SAR ADC paper this survey draws on was built at 1.0–1.2 V in a
90 nm–28 nm node, and verified in a commercial simulator with PSS/pnoise and a
mature mixed-signal flow. None of those three conditions hold here. The deltas
propagate into every axis, so they are stated once, up front:

**Delta 1 — supply is 3.3 V, not 1.2 V.**
- CDAC switching energy scales as `V_ref²`. Going 1.2 V → 3.3 V multiplies
  switching energy by `(3.3/1.2)² = 7.56×` for the same unit capacitor `[D]`.
  Energy-efficient switching therefore matters *more* here than in the papers
  that invented it, not less.
- `kT/C` scales as `1/V_ref²` for a fixed number of bits. The sampling
  capacitance required for 10-bit noise performance at 3.3 V is ~7.6× smaller
  than at 1.2 V `[D]`, which as §1 shows removes `kT/C` as the array-sizing
  constraint entirely and hands that job to matching.
- Headroom stops being scarce. The stacked-device argument that motivated the
  double-tail comparator `[P: Schinkel 2007]` largely evaporates at 3.3 V with
  180 nm devices (`V_th` ≈ 0.7 V `[E4]`), which changes the comparator ranking.
- Conversely, the rail-to-rail sampling-switch problem that forces bootstrapping
  in 1.2 V designs also largely evaporates — while bootstrapping itself becomes
  *harder*, because a classic bootstrap generates `V_in + V_DD` ≈ 6.6 V on the
  gate node, above the 3.3 V device rating (§5).

**Delta 2 — 180 nm, not 28–90 nm.** Devices are slow relative to the cited work
but the target rate is also 25–600× slower. At 1 MS/s the design is
*settling-limited by choice, not by device speed*, which is why the sync-vs-async
argument (§4) resolves differently here than in Chen & Brodersen's 600 MS/s
converter `[P: Chen 2006]`. Matching is better than in deep-submicron; parasitic
capacitance ratios are worse.

**Delta 3 — ngspice only.** No PSS, no pnoise, no HB. Local install is
`ngspice-46` `[O]`. The consequences, verified against the installed binary and
code-model directory on 2026-07-30 `[O]`:
- `.noise` exists but is small-signal AC about a DC operating point. A clocked
  regenerative latch has no meaningful DC operating point, so `.noise` cannot
  characterize a StrongARM/double-tail comparator at all.
- Transient noise exists only as explicit `trnoise` / `trrandom` sources on
  independent sources (strings `trnoise`, `trrandom`, `notrnoise` present in the
  binary `[O]`). ngspice has **no automatic device-level transient noise** switch
  equivalent to Spectre's `noisefmax` `[V]` — noise must be injected deliberately.
  This makes comparator noise a *Monte-Carlo transient* exercise (§3.5).
- Mixed-signal is available and better than expected: `digital.cm` ships XSPICE
  digital primitives (`d_dff`, `d_process`), and `d_cosim` plus `ivlng.so` /
  `ivlng.vpi` (Icarus Verilog VPI bridge) are present in
  `/opt/homebrew/lib/ngspice/` `[O]`. Verilog co-simulation of the SAR controller
  against the analog core is therefore feasible in-flow (§4.4).

---

## 1. First-order budget: what the spec implies before any topology is chosen

This section derives the numbers that the three axis sections keep referring
back to. All of it is `[D]` on `[E4]` assumptions; the point is the *shape* of
the constraint set, not the specific values.

### 1.1 LSB and the ENOB budget

Take the single-ended full-scale range as `V_FS = 3.3 V` (conservative; a
differential architecture with ±V_ref gives 2× this and correspondingly relaxes
everything below).

- `LSB = 3.3 V / 1024 = 3.22 mV` `[D]`
- Quantization noise `= LSB/√12 = 0.930 mV rms` `[D]`
- Ideal 10-bit SNR `= 6.02·10 + 1.76 = 61.96 dB` `[D]`

For **ENOB > 9.0**, required SNDR `= 6.02·9 + 1.76 = 55.94 dB` `[D]`. The
allowable non-quantization error power is
`10^((61.96−55.94)/10) − 1 = 3.0×` the quantization noise power, so

> **σ_total(non-quantization) ≤ √3 × 0.930 mV = 1.61 mV rms** `[D]`

For the **ENOB > 9.5** stretch, required SNDR `= 58.95 dB`, allowable error power
`= 10^0.301 − 1 = 1.0×` quantization power, so

> **σ_total(non-quantization) ≤ 0.930 mV rms** `[D]`

Splitting the stretch budget three ways (sampling `kT/C`, comparator, reference
+ distortion) gives ≈ **0.537 mV rms** per term `[D]`.

### 1.2 kT/C is not the binding constraint at 3.3 V

`C_s = kT/σ²` with `kT = 1.381e-23 × 300 K = 4.14e-21 J`:

| Noise target | Required sampling C |
|---|---|
| 1.61 mV rms (ENOB > 9.0, whole budget) | **1.6 fF** `[D]` |
| 0.537 mV rms (ENOB > 9.5, 1/3 budget) | **14.4 fF** `[D]` |
| 12-bit stretch, 1/3 of a 0.233 mV budget | **≈ 190 fF** `[D]` |

**Conclusion:** at 3.3 V, a 10-bit converter needs on the order of *tens of
femtofarads* of sampling capacitance for noise. The CDAC array will be one to
three orders of magnitude larger than that, and it will be that large for
**matching** reasons and because of the PDK's minimum practical unit capacitor —
not for `kT/C`. This inverts the usual deep-submicron design pressure and is the
single most important consequence of the 3.3 V rail. It should be re-checked
against #4's extracted `kT/C` and matching data before #8 sizes anything.

### 1.3 Matching sets the array

For a binary-weighted CDAC the worst-case DNL occurs at the mid-scale transition,
with `σ(DNL)_max = √(2^N − 1) · (σ_u/C_u)` LSB `[P: Saberi 2011]`. For N = 10,
`√1023 = 31.98` `[D]`:

| DNL target (3σ) | Required σ_u/C_u |
|---|---|
| < 1 LSB | **1.04 %** `[D]` |
| < 0.5 LSB (stretch) | **0.52 %** `[D]` |

With a Pelgrom-style area law `σ_u/C_u = A_C/√A` `[P: Pelgrom 1989]` and an
assumed `A_C ≈ 1 %·µm` `[E4]`:

- baseline: `A ≈ 0.92 µm²` per unit cap `[D, E4]`
- stretch: `A ≈ 3.7 µm²` per unit cap `[D, E4]`

At an assumed MIM density of 2 fF/µm² `[E4, V — gf180mcu MIM flavors and density
must be confirmed in #4]`, that is `C_u ≈ 1.8–7.4 fF`. A 512-unit half-array is
then **1–4 pF per side** `[D, E4]`, occupying `2 × 512 × 3.7 µm² ≈ 3800 µm² =
0.0038 mm²` of capacitor area for the stretch case `[D, E4]` — roughly 4 % of the
0.1 mm² area budget before dummies, guard ring, and routing. Area is not the
tight constraint either.

**A working value of `C_u = 5 fF` is used for the estimates in §2.** It is a
placeholder for #4's answer, not a recommendation.

### 1.4 Timing budget at 1 MS/s

A 1 µs conversion period, split as 30 % acquisition / 70 % conversion:
300 ns acquire, 700 ns for 10 bit trials → **70 ns per bit trial** `[D]`.
With a 16× external clock (62.5 ns period), a plausible cycle allocation is
4 sample cycles + 10 bit cycles + 2 reset/output cycles = 16 `[D]`.

DAC settling to 0.5 LSB at 10 bits requires `t/τ > ln(2¹¹) = 7.62` `[D]`. With
`C_arr = 2.56 pF` and an assumed switch `R_on = 1 kΩ` `[E4]`, `τ = 2.56 ns` and
`t_settle ≈ 19.5 ns` `[D, E4]` — comfortably inside a 62.5 ns cycle, and still
inside the 31.25 ns cycle implied by the 2 MS/s stretch at the same 16× ratio.
**The 1 MS/s target has large timing margin in 180 nm.** This is the fact that
drives §4's recommendation.

---

## 2. Axis 1 — CDAC switching scheme

Consumed by **#8**. Three inputs are required: switching energy, common-mode
excursion at the comparator input, and total array capacitance vs reference-drive
burden.

### 2.1 Candidates

| Scheme | Sampling | Reference levels | Origin |
|---|---|---|---|
| **Conventional** ("reset-and-set" binary-weighted charge redistribution) | bottom-plate | `V_ref`, GND | classical; analyzed in `[P: Saberi 2011]` |
| **Split-capacitor** (MSB cap split, switched in two halves) | bottom-plate | `V_ref`, GND | `[P: Ginsburg 2005, 2007]` |
| **Monotonic / set-and-down** | top-plate | `V_ref`, GND | `[P: Liu 2010]` |
| **Merged-capacitor switching (MCS) / V_cm-based** | top-plate | `V_ref`, `V_cm`, GND | `[P: Hariprasath 2010]`, `[P: Zhu 2010]` |
| **Tri-level, charge-recycling, bypass, and later variants** | various | ≥3 | `[P: Yuan 2012]`, `[P: Ginsburg 2005]`, survey in `[P: Saberi 2011]` |

Two orthogonal choices are entangled in the table and are worth separating for
#8: **top-plate vs bottom-plate sampling**, and **which reference levels the
bottom plates are driven to**. Top-plate sampling is what buys the "one free
comparison" (the MSB is resolved with no switching at all) and hence the 50 %
array-size reduction; it is common to both monotonic and MCS. Bottom-plate
sampling is what makes the sampled charge independent of the switch's
signal-dependent charge injection.

### 2.2 Switching energy

Average switching energy over all output codes, in units of `C_u·V_ref²`, for
N = 10:

| Scheme | Energy (C_u·V_ref²) | vs conventional | Source |
|---|---|---|---|
| Conventional | **1363.3** | — | `[P: Liu 2010]`, `[P: Saberi 2011]` |
| Split-capacitor | 852.6 | −37 % | `[V]` — confirm against `[P: Ginsburg 2007]` |
| Monotonic / set-and-down | **255.5** | **−81.26 %** | `[P: Liu 2010]` |
| MCS / V_cm-based | **170.2** | **−87.5 %** | `[P: Hariprasath 2010]` |
| Tri-level and later variants | < 170 | > −87.5 % | `[V]` — `[P: Yuan 2012]` |

The three headline figures reproduce exactly from closed forms, which is a useful
cross-check that the numbers being carried forward are the ones the papers
actually claim `[D]`:

```
Conventional:  Σ_{i=1..N}   2^(N+1-2i) · (2^i − 1)          = 1363.334   (N=10)
Monotonic:     Σ_{i=1..N-1} 2^(N-2-i)                       =  255.5     (N=10)
MCS / Vcm:     ¼ · Σ_{i=1..N-1} 2^(N-2i) · (2^i − 1)        =  170.167   (N=10)
```

The MCS factor of ¼ is the physical story in one symbol: every bottom plate moves
by `V_ref/2` (from `V_cm` to either rail) instead of by `V_ref`, and switching
energy goes as the square of the step.

**Translated to this block** at `V_ref = 3.3 V`, `C_u = 5 fF` `[E4]`,
`f_s = 1 MS/s`, so that `C_u·V_ref² = 54.45 fJ` `[D]`:

| Scheme | Energy/conversion | Reference power @ 1 MS/s | Charge/conversion from V_ref |
|---|---|---|---|
| Conventional | 74.2 pJ `[D,E4]` | **74.2 µW** `[D,E4]` | 22.5 pC `[D,E4]` |
| Monotonic | 13.9 pJ `[D,E4]` | **13.9 µW** `[D,E4]` | 4.2 pC `[D,E4]` |
| MCS / V_cm | 9.3 pJ `[D,E4]` | **9.3 µW** `[D,E4]` | 2.8 pC `[D,E4]` |

Against the < 1 mW budget, even conventional switching costs only ~7 % — so
**switching energy alone does not decide this axis.** What it does decide is how
hard the reference is to build (§2.4). Note also that at 1.2 V these same numbers
would be 7.56× smaller `[D]`; the 3.3 V rail is what makes them worth tabulating
at all.

### 2.3 Common-mode excursion at the comparator input

This is the axis input that matters most, and it is where the low-voltage
literature's ranking inverts.

**Conventional and split-capacitor, differential:** both half-arrays switch
complementarily, so the comparator input common mode is nominally constant at
whatever the sampling phase established `[P: Saberi 2011]`. No CM problem.

**Monotonic / set-and-down:** at every bit trial, exactly one side's capacitor
steps from `V_ref` down to ground, and the other side does not move. The
common mode therefore falls monotonically. Per-side step magnitude at trial `i`
is `V_ref/2^i`, so the CM step is `V_ref/2^(i+1)`, and the total excursion over
an N-bit conversion is

```
ΔV_cm = Σ_{i=1..N-1} V_ref/2^(i+1) = V_ref·(1/2 − 2^-N) ≈ V_ref/2      [D]
```

For N = 10 this is `0.499 · V_ref = 1.65 V` `[D]`. **Sampling at mid-supply
(1.65 V), the comparator input common mode ends the conversion essentially at
ground.** Liu et al. addressed exactly this by using a PMOS-input dynamic
comparator, whose input CM range extends down toward ground `[P: Liu 2010]`
`[V — confirm the input-pair polarity at source]`.

At 1.2 V the excursion is 0.6 V and a PMOS pair copes. At 3.3 V with 180 nm
devices the excursion is 1.65 V, which is larger than the device `V_th` by more
than a factor of two `[E4]`. The consequence is not merely "the comparator gets
slower near the end of the conversion." It is that **the comparator's input-
referred offset becomes a function of the bit index**, i.e. an error that is
correlated with the code being converted. A static offset in a SAR loop is
benign (it is a whole-converter offset). An offset that *moves during the
conversion* is a **linearity** error and lands directly on INL/DNL. This is the
central argument of this axis.

**MCS / V_cm-based:** by construction, after each comparison one side's
capacitor moves `V_cm → V_ref` while the mirror capacitor on the other side moves
`V_cm → GND` (or vice versa). The two moves are equal and opposite, so
`ΔV_cm = 0` for every trial and the comparator input common mode is **constant at
`V_cm` for the entire conversion** `[D]`, `[P: Hariprasath 2010]`,
`[P: Zhu 2010]`. This is the property, not the energy figure, that makes MCS the
strong candidate here.

Summary of the axis input #8 needs:

| Scheme | CM at comparator input | Consequence at 3.3 V |
|---|---|---|
| Conventional (diff) | constant | none |
| Split-cap (diff) | constant | none |
| Monotonic | falls by ≈ `V_ref/2` = 1.65 V `[D]` | offset varies within a conversion → INL/DNL risk; forces PMOS input pair and an offset-vs-CM characterization |
| MCS / V_cm | **constant** `[D,P]` | none; comparator can be optimized at a single operating point |

### 2.4 Total array capacitance vs reference-drive burden

**Array size.** Conventional N-bit charge redistribution needs `2^N · C_u` per
side (binary caps plus terminating dummy). Top-plate sampling — used by both
monotonic and MCS — resolves the MSB with no switching, so the array only needs
`2^(N-1) · C_u` per side: a **50 % reduction**, claimed by both
`[P: Liu 2010]` and `[P: Hariprasath 2010]`.

At `C_u = 5 fF` `[E4]`: conventional 5.12 pF/side (10.2 pF total); monotonic and
MCS 2.56 pF/side (5.12 pF total) `[D,E4]`.

**Reference drive.** Two distinct requirements, and #8 should size for both:

*Per-conversion average current* — `I_ref,avg = E_sw · f_s / V_ref`:
22.5 µA conventional, 4.2 µA monotonic, 2.8 µA MCS at 1 MS/s `[D,E4]`.
All trivial for any reference buffer.

*Per-step charge and settling* — this is the real burden. The largest single
step must settle to within 0.5 LSB inside one bit cycle. For conventional
switching the MSB capacitor (`512·C_u = 2.56 pF`) moves by the full `V_ref`,
`ΔQ = 8.4 pC` `[D,E4]`. For MCS the largest cap is `256·C_u = 1.28 pF` moving by
`V_ref/2 = 1.65 V`, `ΔQ = 2.1 pC` `[D,E4]` — **4× smaller per step and ~8×
smaller per conversion.**

If that charge had to come from decoupling capacitance alone, holding `V_ref`
within 0.5 LSB (1.61 mV) would require `C_dec ≥ ΔQ / 1.61 mV` = **5.2 nF
conventional / 1.3 nF MCS** `[D,E4]`. At 2 fF/µm² that is 2.6 mm² / 0.65 mm² of
capacitor — **impossible on-chip inside a 0.1 mm² block** `[D,E4]`. The
conclusion for #7 (reference-source scope) is unavoidable and should be recorded
there: **the reference must be actively driven and settle within a bit cycle, or
be supplied off-chip with external decoupling.** On-chip decoupling can only
shave the transient, not supply it. The choice of switching scheme moves this
burden by ~4×, which is meaningful but does not change the conclusion.

Second-order but real: MCS needs a **third rail, `V_cm`**, with its own drive and
decoupling. The sky130 12-bit reference design solved this with an on-chip
switched-capacitor `V_cm` generator, and reports that removing it shrinks the
block from 0.178 mm² to 0.124 mm² — i.e. the `V_cm` generator is ~30 % of that
design's area `[O: jjbbff/SKY__ADC-2496]`. That is a direct, concrete cost to
weigh in #7/#8. `V_cm = V_ref/2` can alternatively come from a resistive divider
plus buffer, or from off-chip.

### 2.5 3.3 V and gf180mcu-specific caveats

- **Switch resistance on the bottom-plate drivers.** Bottom plates are driven by
  digital inverters; at 3.3 V with 180 nm devices these are strong, and `τ` is
  dominated by array capacitance, not driver strength `[E4]`. Confirm in #4.
- **Unit-capacitor flavor.** gf180mcu MIM density, minimum MIM geometry, and
  whether a MOM/finger alternative is worth building are open. `[E4 — #4]`
- **Parasitic top-plate capacitance** attenuates the DAC transfer and adds a gain
  error (benign) but also interacts with the split/segmented array choice. In
  180 nm the parasitic-to-unit ratio is more favorable than deep-submicron `[E4]`.
- **Segmentation.** The sky130 12-bit reference uses a 9-bit thermometer + 3-bit
  binary segmented array with a switchable sequential/symmetric thermometer
  decode explicitly "to decrease the integral nonlinearity error"
  `[O: jjbbff/SKY__ADC-2496]`. For a 10-bit array this is probably overkill, but
  it is a proven-in-this-flow technique worth carrying to #8 as an option.

### 2.6 Axis 1 shortlist (input to #8)

1. **MCS / V_cm-based switching, differential, top-plate sampling — primary.**
   - *Serves INL/DNL < 1 LSB (stretch 0.5 LSB):* constant comparator input CM
     `[D,P]` removes the CM-dependent-offset linearity error entirely, which is
     the dominant architectural linearity risk at a 1.65 V CM excursion.
   - *Serves ENOB > 9.0/9.5:* same mechanism — a CM-dependent offset shows up as
     harmonic distortion, not just offset.
   - *Serves power < 1 mW:* lowest switching energy of the candidates, 170.2 vs
     1363.3 `C_u·V_ref²` `[P]`; ≈ 9 µW of reference power `[D,E4]`.
   - *Serves area < 0.1 mm²:* half the array of conventional `[P]`.
   - *Cost:* a third rail (`V_cm`) with drive and decoupling; up to ~30 % area if
     generated on-chip the way the sky130 reference does `[O]`.

2. **Conventional differential with bottom-plate sampling — fallback.**
   - *Serves:* INL/DNL and ENOB equally well (CM is also constant), and needs no
     `V_cm` rail, so it de-risks #7. Simplest logic and the easiest to verify.
   - *Cost:* 8× switching energy (74 µW `[D,E4]` — still only ~7 % of the power
     budget) and 2× array capacitance and area (still ~8 % of the area budget
     `[D,E4]`). **Both costs fit the spec.** Take this if #7 rules out a `V_cm`
     rail or if schedule risk dominates.

3. **Monotonic / set-and-down — not recommended as primary at 3.3 V.**
   - Best-known simplicity/energy trade in the 1.0–1.2 V literature
     `[P: Liu 2010]`, and it would be the default choice at 1.2 V.
   - Ruled down here solely by the `≈1.65 V` CM droop `[D]`, which converts
     comparator offset into a code-correlated error and puts the INL/DNL < 1 LSB
     target at architectural risk. Would require a PMOS-input comparator plus an
     offset-vs-CM characterization campaign to retire the risk.
   - **Reconsider if** #4 shows a comparator whose offset is flat over a
     1.65 V CM range, or if #1 relaxes INL/DNL.

*Deferred to #8, not decided here:* segmentation (binary vs thermometer/binary
split), redundancy/non-binary weighting, split-cap variants, and the unit-cap
primitive.

---

## 3. Axis 2 — Comparator topology

Consumed by **#9**. Required inputs: offset, noise, speed, kickback; offset-
cancellation options with cost; and the noise-verification path each topology
implies given ngspice.

### 3.1 A framing point that changes the whole axis

**In a single-comparator SAR ADC, static comparator offset is a whole-converter
offset, not a linearity error.** The same comparator makes every decision in the
binary search, so a fixed input-referred offset shifts the entire transfer
function and is removed by a one-time digital offset subtraction (or simply
absorbed, if input range permits). Offset only becomes a *linearity* error when
it **varies within a conversion** — which happens when the comparator's input
common mode moves (§2.3), or when the comparator is reused at very different
speeds/settling states across bit trials.

Consequences:
- Given a CM-constant switching scheme (§2.6 item 1 or 2), the offset requirement
  is loose: it only needs to be small enough not to eat input range or push the
  input pair out of its operating region. A budget of, say, ±50 mV is
  unremarkable for an untrimmed dynamic latch `[E4]`.
- Given monotonic switching, offset cancellation stops being optional and has to
  track CM — a much harder problem.
- This is why §2 and §3 must be decided together, and why #8 and #9 should not be
  built in isolation.

### 3.2 Candidates

**StrongARM latch** (a.k.a. sense-amplifier-based latch). Origin
`[P: Kobayashi 1993]`; canonical tutorial treatment of operating phases, offset
sources, noise, and kickback in `[P: Razavi 2015a]`. Single clock phase, a
single tail current source, zero static power, minimal device count. Offset is
dominated by input-pair `V_th`/geometry mismatch and by load/latch mismatch
referred back through the input-stage gain `[P: Razavi 2015a]`. Its known
weakness is that the input devices, the integration nodes, and the regeneration
nodes are all stacked, which at low supply squeezes headroom and forces small
input-pair overdrive.

**Double-tail latch-type sense amplifier** `[P: Schinkel 2007]`. Splits the
circuit into a separate input/integration stage and a latch stage, each with its
own tail. The explicit design intent was operation at lower supply and faster
setup+hold (18 ps demonstrated at the time) `[P: Schinkel 2007]`. Because the
input stage is decoupled from the regenerating nodes, it also gives better
kickback isolation and a wider usable input CM range, at the cost of more
devices, more area, and either a second clock phase or an internally derived
delayed clock. The noise behaviour of this family is the subject of
`[P: Miyahara 2008]` and `[P: Nuzzo 2008]`.

**Multi-stage: preamplifier + latch.** The classical taxonomy is
`[P: Razavi & Wooley 1992]`. A gain stage ahead of the latch divides the latch's
offset and noise by the preamp gain and shields the input from the latch's
kickback. Two sub-variants matter here:
- *Static (continuous-time) preamp + StrongARM latch*: best noise/kickback, costs
  static current. At a < 1 mW budget a few tens of µA of static preamp current is
  affordable (10 µA × 3.3 V = 33 µW `[D]`), and it is the only variant whose
  noise `.noise` can actually analyze (§3.5).
- *Dynamic/integrating preamp + latch*: zero static power, the structure used in
  most modern low-energy SAR comparators; the double-tail is itself the
  degenerate two-stage case of this.

**Time-domain comparator** `[P: Agnes 2008]`. Converts the input difference into
a delay difference and resolves with digital gates; designed for ultra-low
voltage/power (3.8 µW at 1 V, 100 kS/s, 9.4 ENOB) `[P: Agnes 2008]`. Included
for completeness: it is a genuinely different point in the space and is friendly
to a digital-heavy flow, but its delay-based resolution scales badly with supply
in the wrong direction for 3.3 V and it is not a mainstream choice at 10 bits,
1 MS/s. Not shortlisted.

### 3.3 Comparison

| | StrongARM | Double-tail | Static preamp + latch | Dynamic preamp + latch |
|---|---|---|---|---|
| **Offset** | Highest of the four; set by input pair + latch mismatch referred through modest input-stage gain `[P: Razavi 2015a]` | Similar order; latch mismatch is divided by the input-stage gain, so typically somewhat better `[P: Schinkel 2007]` `[V]` | Lowest; latch offset divided by preamp gain `[P: Razavi & Wooley 1992]` | Between double-tail and static preamp |
| **Noise** | Set by input-pair thermal noise integrated onto the output nodes; models in `[P: Nuzzo 2008]`, `[P: Miyahara 2008]` | Comparable; the extra stage adds a noise contribution but the input stage can be biased for higher gm `[P: Miyahara 2008]` | Best; preamp gain suppresses all downstream noise, at the cost of the preamp's own broadband noise and static current `[P: Razavi & Wooley 1992]` | Good; integration time is a designable noise/power knob `[P: Harpe 2011]` |
| **Speed** | Fast; single phase, minimum latency `[P: Razavi 2015a]` | Fast; separate tails allow independent optimization of integration and regeneration `[P: Schinkel 2007]` | Slowest to reset; preamp bandwidth adds latency | Middle |
| **Kickback** | Worst — regenerating nodes couple back to the inputs through `C_gd`/`C_gs` of the input pair `[P: Figueiredo 2006]` | Better — input stage isolates the latch `[P: Schinkel 2007]` | Best — preamp is a unidirectional buffer | Good |
| **Static power** | zero | zero | non-zero (tens of µW `[D,E4]`) | zero |
| **Area / devices** | smallest | ~1.5–2× | largest | ~2× |
| **Clocking** | one phase | two phases or internal delay | one phase + bias | two phases |
| **3.3 V verdict** | Headroom objection **does not apply** — stack fits comfortably with `V_th ≈ 0.7 V` `[E4]` | Still wins on kickback and CM range, but its headline motivation is neutralized | Affordable within the power budget; the fallback if noise or kickback measurements disappoint | Reasonable middle; adds a clock phase |

**Kickback deserves specific attention here.** In a SAR ADC the comparator's
input *is* the CDAC top plate, a high-impedance node holding the residue.
Kickback charge injected into that node is not simply a disturbance to settle out
— it is charge added to the very node whose voltage encodes the remaining bits.
It is partly common-mode (rejected differentially) and partly signal-dependent
(not rejected). At 3.3 V the regenerating nodes swing 3.3 V, so kickback charge
through a given `C_gd` is 2.75× that of a 1.2 V design `[D]`. Mitigations are
catalogued in `[P: Figueiredo 2006]`: neutralization capacitors, a cascode or
buffer between input pair and regeneration nodes (i.e. the double-tail/preamp
structures), and switching the input pair off before regeneration.

### 3.4 Offset-cancellation options and their cost

Ordered from cheapest to most expensive. #9 should pick the *lowest* row that
meets the offset requirement implied by the §2 switching-scheme decision.

| # | Technique | Mechanism | Area | Power | Complexity | Notes |
|---|---|---|---|---|---|---|
| 0 | **None + digital offset removal** | Exploit §3.1: a static offset is a whole-converter offset; subtract it in the digital domain or in the readback | zero | zero | trivial | **The default given a CM-constant switching scheme.** Costs only input range. Does *not* work if CM moves. |
| 1 | **Input-pair upsizing** | Pelgrom: `σ_Vth ∝ 1/√(WL)` `[P: Pelgrom 1989]` | grows as 1/σ² | zero | trivial | Cheap at first; hits diminishing returns and slows the comparator via added `C_gs` |
| 2 | **Capacitive latch-load trim** | Digitally programmable capacitor imbalance on the regeneration nodes; one-time foreground calibration `[P: Miyahara 2008]` | small | zero static | moderate (cal FSM, trim register) | **Best cost/benefit for this block.** Demonstrated in this exact open-source flow: the sky130 12-bit reference implements comparator offset self-calibration enabled by a pin `[O: rnunes2311/SAR_ADC_12bit]` |
| 3 | **Body/bulk-bias trim of the input pair** | Shift `V_th` differentially via body terminals | small | small | moderate | Requires isolated wells; gf180mcu deep-nwell availability and body-effect coefficient at 3.3 V unknown `[E4 — #4]` |
| 4 | **Current-DAC injection at the latch nodes** | Trim by unbalancing currents | small | **static** | moderate | Burns static power continuously; avoid unless #4 rules out #2 |
| 5 | **Input-offset storage / output-offset storage (auto-zero)** | Sample the offset onto series/parallel capacitors in a dedicated phase `[P: Razavi & Wooley 1992]` | large (aux caps) | zero static | high | Costs a clock phase per conversion, injects its own `kT/C` noise, and the aux caps load the CDAC top plate. Poor fit for a SAR whose input node is the CDAC. |
| 6 | **Chopping / conversion averaging** | Alternate polarity across conversions; offset averages out | small | 2× conversions | moderate | Converts offset to a rate penalty. Viable at 1 MS/s if throughput margin is spent; conflicts with the 2 MS/s stretch. |
| 7 | **Redundancy + digital error correction** | Non-binary weights absorb *dynamic* decision errors `[P: Kuttner 2002]`, `[P: Liu 2011]` | moderate (extra cycles + caps) | small | high | **Does not fix static offset.** Listed because it is the standard companion technique and both surveyed sky130 12-bit designs use it `[O]`; it buys tolerance to incomplete settling and comparator metastability, which is a different problem. |

### 3.5 Noise verification path per topology — the ngspice constraint

This is the part of the axis that ngspice actually changes, and #9/#13 should
budget for it explicitly.

**What ngspice cannot do.** `.noise` is a small-signal AC analysis about a DC
operating point. A StrongARM or double-tail comparator has no meaningful DC
operating point (both are reset-and-regenerate structures with no static bias),
so `.noise` returns nothing usable for them. There is no PSS/pnoise to fall back
on, and ngspice provides no automatic device-level transient noise switch — noise
enters a transient simulation only through explicit `trnoise` / `trrandom`
sources on independent sources `[O, V]`.

**The path that does work, for every dynamic topology:**

1. Insert a `trnoise` voltage source in series with one comparator input,
   parameterized to represent the input-referred noise of the devices (or, more
   defensibly, insert `trnoise` sources representing each dominant device's
   channel noise).
2. Sweep the applied differential input across ±3–4 σ of the expected noise, in
   steps well below σ.
3. At each input point, run K independent transient conversions (different noise
   seeds) and record the decision.
4. Fit the resulting decision-probability curve to a Gaussian CDF; its slope at
   the 50 % point yields σ, the input-referred noise.

Cost: resolving σ to ~10 % needs of order 10²–10³ trials per input point, and
10–20 input points — i.e. **10³–10⁴ transient runs per corner** `[D]`. Times PVT
corners, this becomes the single most expensive item in the verification suite.
It must be budgeted in #13 and it wants a parallel batch runner. (Note: the UAH
sky130 SAR team hit exactly this and built a dedicated batched ngspice runner for
AWS `[O: UAH-IC-Design-Team/ngspice-batch-runner]` — worth studying for #2.)

**Per-topology implications:**

| Topology | `.noise` usable? | Verification path | Relative cost |
|---|---|---|---|
| StrongARM | **No** — no DC operating point | Transient `trnoise` Monte Carlo only | Highest |
| Double-tail | **No** | Transient `trnoise` Monte Carlo only | Highest |
| Dynamic preamp + latch | **No** | Transient `trnoise` Monte Carlo only | Highest |
| **Static preamp + latch** | **Partially yes** — the preamp has a valid DC OP, so `.noise` gives its input-referred noise directly and cheaply | `.noise` on the preamp for the dominant term + a *smaller* transient MC to confirm the latch contribution is negligible after preamp gain | **Lowest** |

This is a genuine, non-obvious argument in favour of the static-preamp variant
that would not appear in a paper written against a commercial simulator: **it is
the only topology whose noise can be closed with a cheap, deterministic analysis
in this flow.** It should be weighed against its static-power cost, not dismissed.

A second, independent consideration: a `trnoise`-based methodology requires
knowing the device noise parameters to inject. Those come from #4. Until #4
lands, the comparator noise number for this block is unknown, and any figure
quoted before then is `[E4]`.

### 3.6 3.3 V-specific notes

- The headroom argument for double-tail is neutralized (§0.5, Delta 1). Choose
  double-tail here for **kickback and CM range**, not for supply.
- Kickback charge scales with the regeneration swing → 2.75× worse than a 1.2 V
  design for the same devices `[D]`.
- Input-pair polarity must be chosen to match the CDAC's CM: with a CM-constant
  scheme at `V_cm = 1.65 V`, either polarity works comfortably with
  `V_th ≈ 0.7 V` `[E4]`. With monotonic switching, PMOS is forced.
- Dynamic comparator energy per decision goes as `C·V_DD²` → 7.6× a 1.2 V design
  for the same node capacitance `[D]`. At 11 decisions × 1 MS/s this is still
  small (e.g. 50 fF × 3.3² × 11 × 1e6 = 6 µW `[D,E4]`) but it is no longer free.

### 3.7 Axis 2 shortlist (input to #9)

1. **StrongARM latch, single stage, input-pair polarity matched to a constant
   `V_cm` — primary.**
   - *Serves power < 1 mW / < 500 µW stretch:* zero static power; ~6 µW dynamic
     `[D,E4]`.
   - *Serves area < 0.1 mm²:* smallest device count of the candidates.
   - *Serves rate 1 MS/s (2 MS/s stretch):* single clock phase, minimum latency;
     §1.4 shows the per-bit budget is 62.5 ns against a sub-nanosecond
     regeneration time `[E4]` — enormous margin.
   - *Serves ENOB > 9.0:* §1.1 allows ~1.6 mV rms total non-quantization noise,
     of which a comparator can be allocated ~0.5–0.9 mV rms `[D]` — loose for a
     dynamic latch.
   - *Offset:* row 0 (none) by default, row 2 (capacitive latch-load trim) if #4
     shows σ_os large enough to eat input range.
   - *Risk to retire in #9:* kickback into the CDAC top plate at 3.3 V `[D]`, and
     the cost of the transient-noise MC campaign (§3.5).

2. **Double-tail — alternate, take it if kickback bites.**
   - Same spec traceability as (1), plus explicit kickback isolation
     `[P: Schinkel 2007]`, `[P: Figueiredo 2006]`, and a wider CM range that
     would also make monotonic switching survivable if §2 is revisited.
   - *Cost:* second clock phase or internal delay, ~1.5–2× area.

3. **Static preamp + StrongARM latch — alternate, take it for the 12-bit stretch
   or if noise verification cost dominates.**
   - *Serves ENOB > 9.5 and the 12-bit variant:* lowest noise and lowest offset
     `[P: Razavi & Wooley 1992]`.
   - *Serves the verification schedule:* the only shortlisted topology whose
     noise is analyzable with `.noise` in this flow (§3.5) — a real, quantifiable
     schedule benefit.
   - *Cost:* static current (~33 µW at 10 µA `[D]`), against a < 500 µW stretch
     budget; largest area.

*Not shortlisted:* time-domain comparator `[P: Agnes 2008]` — wrong supply
regime and unnecessary at this resolution/rate.

---

## 4. Axis 3 — SAR logic: synchronous vs asynchronous

Consumed by **#11**. Required inputs: speed margin at 1 MS/s (2 MS/s stretch),
clocking burden, and simulability in an ngspice flow.

### 4.1 Candidates

**Synchronous.** An external clock at `M × f_s` steps a shift register / FSM
through sample → N bit trials → output. Every phase is a fixed number of clock
cycles, sized for the *worst-case* comparator decision time and DAC settling.

**Asynchronous / self-timed.** Introduced for SAR by `[P: Chen 2006]` (6-bit,
600 MS/s, 5.3 mW, 0.13 µm). Only `f_s` is supplied externally; a "ready" signal
derived from the comparator outputs triggers the next bit trial through an
internal delay loop. The payoff is twofold: no high-frequency external clock, and
the loop runs at the comparator's *average* decision time rather than its worst
case — the comparator resolves large residues fast and only the near-metastable
decisions take long.

**Hybrid.** Synchronous bit-cycle boundaries with an asynchronous comparator-ready
handshake *inside* each cycle (i.e. the logic advances on comparator-done but the
sample boundary stays clocked). Mentioned because it captures part of the async
benefit without a free-running self-timed loop.

### 4.2 Speed margin at 1 MS/s (and the 2 MS/s stretch)

From §1.4: at 1 MS/s with a 16× clock, each bit trial gets **62.5 ns**. The
budget inside that cycle `[D,E4]`:

| Item | Estimate | Notes |
|---|---|---|
| DAC settle to 0.5 LSB | 19.5 ns `[D,E4]` | `7.62 τ`, `τ = 1 kΩ × 2.56 pF` |
| Comparator decision (typical) | < 1 ns `[E4]` | regeneration `τ` ~100 ps, ~9 τ to resolve |
| Comparator decision (near-metastable) | can be arbitrarily long | the reason redundancy exists |
| SAR logic propagation | ~1 ns `[E4]` | 180 nm standard cells at 3.3 V |
| **Total (typical)** | **≈ 22 ns** | **~40 ns of margin per cycle** |

At the **2 MS/s stretch** with the same 16× ratio, the cycle shrinks to 31.25 ns
and the same 22 ns still fits, with ~9 ns margin `[D,E4]`. Even at 20× (25 ns
cycle at 2 MS/s) it is close but plausible.

**Therefore: asynchronous operation buys nothing this block needs.** Its entire
speed advantage is recovering the difference between worst-case and average
comparator decision time, which at 40 ns of slack per cycle is slack the design
does not need. `[P: Chen 2006]` was solving a 600 MS/s problem — 600× faster than
this block's target — in a node 1.4× finer. The argument does not transfer.

### 4.3 Clocking burden

| | Synchronous | Asynchronous |
|---|---|---|
| External clock | `M × f_s`: **16 MHz @ 1 MS/s, 32 MHz @ 2 MS/s** (M = 16) `[D]` | `f_s` only: 1–2 MHz |
| Internal timing elements | none beyond the FSM | a delay loop, matched across PVT; typically needs a **custom high-delay standard cell** |
| Metastability handling | a stalled decision corrupts one bit; needs redundancy or a long cycle | a stalled decision **stalls the whole conversion**; needs a timeout/watchdog |
| PVT sensitivity of the timing | none (external clock is the reference) | high — the loop delay tracks process/voltage/temperature |
| Interface implication | needs a clean 16–32 MHz clock at the block boundary; feeds #7 and #12 | simpler pin interface |

Two concrete open-source data points on `M`:
- The sky130 10-bit SAR from UAH uses **M = 32** (external clock 32 MHz for
  1 MS/s) and its own "points of improvement" notes that "the comparator proved
  to resolve much faster than originally expected so the controller may be
  reconfigured to operate at only a 16 clock cycle over sample rate"
  `[O: UAH-IC-Design-Team/sky130-10-bit-SAR-ADC]`. **M = 16 is achievable in
  practice for a 10-bit synchronous SAR in an open-source flow.**
- The sky130 12-bit self-clocked SAR from JKU IIC needed a **custom high-delay
  standard cell**, `sky130_mm_sc__hd_dlyPoly5ns`, fitted to the
  `sky130_fd_sc__hd_` cell grid, to build its clock loop
  `[O: jjbbff/SKY__ADC-2496]`. That is a direct, measured statement of the async
  tax: **going asynchronous means building and characterizing a custom cell in
  the target PDK.** On gf180mcu that cell does not exist and would have to be
  created, characterized, and DRC/LVS-signed-off — new work outside the ADC
  itself, and a strong candidate to generate klayout-tools friction.

A 16–32 MHz external clock on a 180 nm block is unremarkable and is almost
certainly already required for the SPI interface. The clocking burden of the
synchronous option is close to zero *for this block*.

### 4.4 Simulability in an ngspice flow

This is where the two options separate most sharply, and it is the input #11
should weigh heaviest.

**What the flow provides** (verified against the local `ngspice-46` install,
2026-07-30 `[O]`):
- `digital.cm` — XSPICE event-driven digital primitives, including `d_dff` and
  `d_process`, with `adc_bridge` / `dac_bridge` to cross the analog boundary.
- `d_cosim` — an XSPICE code model that loads a co-simulation shared object,
  i.e. a Verilator- or Icarus-generated model of the RTL.
- `ivlng.so` / `ivlng.vpi` — an Icarus Verilog VPI bridge shipped with ngspice.

There is a working open-source existence proof of exactly this loop on an open
PDK: a 3-bit SAR ADC built in xschem with a **Verilog SAR controller compiled
through Verilator and co-simulated in ngspice against transistor-level analog**
`[O: Vaticori/3bit_sar_adc]`. Small, but it demonstrates the toolchain path end
to end, and it is worth reproducing early in #2/#11 as a smoke test.

**Synchronous logic simulates well:**
- The controller can be modeled at three fidelity levels — ideal XSPICE
  primitives, RTL via `d_cosim`/`ivlng`, and full transistor-level — and results
  compared. Fast levels are used for the long PVT/Monte-Carlo campaigns; the slow
  level is used once for sign-off.
- Crucially, **the analog core can be verified standalone.** Drive the CDAC
  bottom plates from an ideal clocked bit-pattern source and the comparator from
  an ideal clock; the analog block then has no feedback dependency on the digital
  block. This is what makes the #13 testbench matrix (INL/DNL × PVT × Monte
  Carlo) tractable at all: the expensive analog runs do not have to carry a
  digital model.
- Clock is an ideal `pulse` source. Deterministic, repeatable, no convergence risk.

**Asynchronous logic simulates badly:**
- The self-timed loop's behaviour *is* its gate delays, so idealized XSPICE
  primitives with lumped delays do not represent it. Verifying an async loop
  requires **transistor-level (or delay-back-annotated) simulation of the entire
  comparator → logic → DAC loop, together**, for every corner.
- The loop cannot be decomposed. Every analog Monte-Carlo run must carry the full
  digital loop, multiplying the cost of the campaign that §3.5 already identified
  as the most expensive item.
- The async handshake plus a near-metastable comparator is a classic transient
  convergence hazard: very small node voltages, long regeneration times, and
  timestep control fighting an event-driven boundary.
- The delay loop must be shown to track across PVT. Demonstrating that in ngspice
  means many more corner runs, and gf180mcu standard-cell delay data would have to
  be trusted or characterized (`[E4 — #4]`).

**Verdict:** in an ngspice-only flow, synchronous is not merely easier — it is
what makes the verification plan in #13 affordable. Asynchronous is a
verification-cost multiplier applied to the most expensive part of the campaign,
purchased for a speed benefit this block does not need (§4.2).

### 4.5 Axis 3 shortlist (input to #11)

1. **Synchronous SAR logic, RTL-synthesized, `M = 16` (16 MHz @ 1 MS/s,
   32 MHz @ 2 MS/s) — primary, with high confidence.**
   - *Serves rate 1 MS/s and the 2 MS/s stretch:* ~40 ns of per-cycle slack at
     1 MS/s and ~9 ns at 2 MS/s `[D,E4]`; `M = 16` demonstrated adequate for a
     10-bit SAR in an open-source flow `[O: UAH]`.
   - *Serves ENOB > 9.0 and INL/DNL < 1 LSB:* deterministic per-bit settling time
     sized for worst case, no timing-dependent bit errors.
   - *Serves power < 1 mW:* digital dynamic power at 16 MHz over ~a few hundred
     gates at 3.3 V is small `[E4 — quantify in #11 against #4 cell data]`.
   - *Serves the verification plan (#13):* analog core verifiable standalone;
     controller verifiable at RTL speed via `d_cosim`/`ivlng` `[O]`.
   - *Cost:* a 16–32 MHz clock at the block boundary — an input to #7 and #12.

2. **Hybrid: synchronous cycle boundaries with a comparator-ready handshake
   inside the cycle — alternate, only if #4 shows a comparator far slower than
   estimated.**
   - Recovers most of the async timing benefit while keeping externally-referenced
     cycle boundaries and standalone analog simulability.
   - *Cost:* still needs a ready-detection path and a timeout; partially
     reintroduces the closed-loop simulation problem.

3. **Fully asynchronous / self-timed — deferred, not recommended for this block.**
   - Well-proven `[P: Chen 2006]` and used by the sky130 12-bit reference
     `[O: jjbbff/SKY__ADC-2496]`, so it is not risky in the abstract.
   - Ruled down on *this* block's evidence: no speed need (§4.2), a custom
     high-delay cell to build and characterize on gf180mcu `[O]`, and a
     verification-cost multiplier on the most expensive part of the campaign
     (§4.4).
   - **Reconsider if** #1/#7 adds a requirement for a low-frequency-only external
     clock interface, or if the rate target moves well above 2 MS/s.

*Related but separate, deferred to #11/#8:* **redundancy / non-binary weighting.**
It is cheap insurance against incomplete DAC settling and comparator metastability
`[P: Kuttner 2002]`, `[P: Liu 2011]`, and notably *both* surveyed sky130 12-bit
designs use it `[O]`, as does the UAH 10-bit (via MSB splitting into 9 sub-caps,
producing a sub-radix-2 search corrected by full adders)
`[O: UAH-IC-Design-Team/sky130-10-bit-SAR-ADC]`. It is orthogonal to sync-vs-async
and should be decided on its own merits.

---

## 5. Input sampling: prior-art note (context for #10)

Brief by design — the T-gate-vs-bootstrap decision belongs to #10. This section
supplies the prior-art context and the 3.3 V translation.

### 5.1 What the literature did, and why

Bootstrapped switches exist because at low supply a plain switch cannot pass a
rail-to-rail signal: an NMOS switch fails near `V_DD`, a PMOS near ground, and a
CMOS transmission gate develops a high-resistance (or fully open) region in the
middle when `V_DD < V_thn + |V_thp|`. The canonical low-voltage solutions:
`[P: Abo & Gray 1999]` (1.5 V pipeline ADC bootstrap), `[P: Steensgaard 1999]`,
`[P: Dessouky & Kaiser 1999]` (rail-to-rail switched-opamp input switch), and
`[P: Aksin 2005]` (sampling inputs beyond the supply). Tutorial treatment in
`[P: Razavi 2015b]`.

Open-source designs that needed one: the sky130 10-bit SAR uses a **bootstrapped
switch** for its ±1.8 V full-range input at 1.8 V supply, citing
`[P: Razavi 2015b]`, `[P: Tsai 2015]`, and `[P: Wei 2011]`
`[O: UAH-IC-Design-Team/sky130-10-bit-SAR-ADC]`.

### 5.2 The 3.3 V translation — and a warning

**The problem bootstrapping solves is mostly absent here.** With gf180mcu 3.3 V
devices, `V_thn + |V_thp| ≈ 1.45 V` `[E4]`, well below `V_DD = 3.3 V`, so a plain
CMOS transmission gate conducts across the entire 0–3.3 V input range with no
dead zone. What remains is *signal-dependent* `R_on` (roughly 2:1 modulation
across the range `[E4]`) and signal-dependent charge injection.

**And the acquisition budget is enormous.** From §1.4, ~300 ns of acquisition
against `τ = R_on·C_arr ≈ 2.6 ns` `[D,E4]` is **>100 τ**. Settling error is
`e^-100`, i.e. beyond any conceivable relevance; even a 4:1 `R_on` modulation
leaves >25 τ. The distortion mechanism that forces bootstrapping in fast
converters — incomplete, signal-dependent settling — is simply not active at
1 MS/s in this flow. A differential architecture additionally cancels even-order
distortion. Bottom-plate sampling with a delayed-turn-off ground switch removes
the first-order charge-injection dependence.

**The warning, and it is specific to 3.3 V:** a classic bootstrap holds
`V_gs = V_DD` on the sampling device, which drives the boosted gate node to
`V_in + V_DD` — up to **6.6 V** for a 3.3 V full-scale input `[D]`. That exceeds
the rating of gf180mcu's 3.3 V devices. At 1.2–1.8 V nodes the boosted node
(2.4–3.6 V) usually lands within the IO/thick-oxide device rating, which is why
the literature rarely flags this. Here, a bootstrap would require the 5 V/6 V
device flavor for the boost network, or clamping, or a different topology.
**Bootstrapping is therefore both less necessary and more expensive at 3.3 V than
in the surveyed designs** — a clean inversion that #10 should record.

### 5.3 Prior-art context handed to #10

- Default candidate: **CMOS transmission gate with dummy-switch charge-injection
  compensation, plus bottom-plate sampling (delayed ground-switch turn-off)** —
  no dead zone at 3.3 V `[E4]`, >100 τ of acquisition margin `[D,E4]`.
- Escalation path if #4/#10 measurements show THD limiting ENOB: (a) upsize the
  T-gate, (b) go bottom-plate-only with a fixed-CM ground switch, (c) bootstrap —
  but only after resolving the 6.6 V device-rating question `[D]`.
- The sky130 10-bit's bootstrapped switch is a portable *reference schematic*
  `[O]` but not a portable *decision* (its 1.8 V supply makes the boost node
  3.6 V, not 6.6 V).
- Open item for #4: `R_on(V_in)` for both device flavors at 3.3 V, and the actual
  `V_th` values used above `[E4]`.

---

## 6. Open-source existence proofs and portability assessment

### 6.1 sky130 SAR ADCs

Inspected 2026-07-30. All `[O]`.

| Project | Resolution / rate | Supply | Architecture | Status | Why it matters here |
|---|---|---|---|---|---|
| **UAH-IC-Design-Team/sky130-10-bit-SAR-ADC** (Apache-2.0) | 10-bit, up to 1.56 MS/s | 1.8 V | **Synchronous**, bootstrapped input switch, MSB-split sub-radix-2 array with correlated-reversed switching, `M = 32` clock ratio | Taped out via an SSCS-22 Caravan wrapper; simulated ENOB 9.31, SFDR 72.2 dB, SINAD 57.8 dB; 2.1 mW avg / 24.1 mW peak | **Closest match to this block's spec point.** Same resolution, same order of rate, synchronous logic, full open-source flow (xschem + magic + netgen + OpenLane for the controller). Also ships a batched ngspice runner. |
| **jjbbff/SKY__ADC-2496** (Apache-2.0; mirror of `efabless/SKY130_SAR-ADC1`; JKU IIC, M. Moser MSc 2023) | 12-bit non-binary, 7.4 kS/s–1.2 MS/s | 1.8 V | **Asynchronous / self-clocked**, segmented CDAC (9-bit thermometer + 3-bit binary), `C_u = 0.447 fF`, 1.83 pF/side, on-chip SC `V_cm` generator, oversampling + LSB averaging | Layout on the Open MPW-8 shuttle; post-layout 824 kS/s typ, 335 µW, area 0.178 mm² (0.124 mm² without `V_cm` gen) | Best-documented open-source SAR in this flow. Source of the concrete async cost data (custom `dlyPoly5ns` cell) and the `V_cm`-generator area cost. |
| Pretl group follow-on: *An 8.1-µW 12-bit Non-Binary Self-Clocked SAR-ADC in 130 nm Open-Source PDK* `[P: Olyanasab 2025]` | 12-bit, 2 kS/s typ (180 kS/s max) | — | Same lineage as above | **Measured silicon**: SNR 73.9 dB, SNDR 71.1 dB, **ENOB 11.5 bit**, 8.1 µW | **The strongest existence proof in the open-PDK world: measured >11 ENOB from an open-source SAR in an open PDK.** Proves the flow can reach the accuracy class this block targets. |
| **rnunes2311/SAR_ADC_12bit** (Apache-2.0) | 12-bit diff / 11-bit SE | 1.8 V (`V_ref` 1.2 V, `V_cm` 0.6 V) | **IMCS** (improved merged-capacitor switching), bottom-plate sampling, **comparator offset self-calibration** (pin-enabled) | Schematic + layout, DRC/LVS clean, 347.5 µW typ; verification incomplete per its own status table | Direct in-flow precedent for both §2's merged-cap recommendation and §3.4 row 2 (offset self-calibration). |
| **Vaticori/3bit_sar_adc** | 3-bit | 1.8 V + 3.3 V | Verilog SAR logic via **Verilator co-simulated in ngspice** against transistor-level analog, MIM-cap DAC | Simulation-only demo | Toolchain existence proof for §4.4's mixed-signal path. Small enough to reproduce as a #2/#11 smoke test. |
| **vyges-ip/sky130-sar-adc** | claims "silicon-proven 12-bit fully-differential" | — | — | No license, minimal documentation | `[V]` — unverified; do not cite without inspection. |

### 6.2 gf180mcu ADCs — the more directly relevant set

| Project | Spec | Status | Notes |
|---|---|---|---|
| **ISHI-KAI Chipathon-2023 ADC** | **6-bit SAR, 8 MHz clock, 3.3 V, gf180mcu** | Taped out on WaferSpace Run-1 `[O: egorxe/gf180mcu_ip_collection, ishi-kai/Chipathon2023_ADC]` | **The most directly relevant existence proof: a SAR ADC on gf180mcu at 3.3 V, in silicon.** Only 6-bit, so it proves the flow and the device usage, not the 10-bit accuracy class. Same team also taped out a 3.3 V PLL, BGR, current source, and LDO on gf180mcu — a useful reference set for #7's reference-source scope. |
| **OpenFASoC SAR ADC + capacitive DAC** | 14-bit SAR | Taped out on gf180mcu MPW-18h1; reported working at >30 MS/s but **ENOB 4.27 @ 20 MHz** `[O: egorxe/gf180mcu_ip_collection]` `[V]` | Cautionary data point: an automatically generated SAR on gf180mcu is *functional* but nowhere near its nominal resolution. Generator-produced gf180 SARs have **not** demonstrated 10-bit accuracy. |
| **arjun2000ananth/sar_adc_gf180** | "10-bit SAR ADC in GF180MCU Opensource PDK" | No README content, no license, no results `[O]` | `[V]` — existence of the repo only. Worth a look for schematic starting points; not evidence of anything. |
| **OpenSAR** `[P: Liu 2021]` | End-to-end SAR ADC compiler; redundant non-binary CDAC with an interleaved-row/column layout generator | Published ICCAD 2021, post-layout results only | `[V]` — target PDK not confirmed during this compilation. Relevant as a source of CDAC layout-generation ideas for #16 regardless. |
| **egorxe/gf180mcu_ip_collection** | Curated list of taped-out open-source gf180mcu analog IP | `[O]` | Useful index for #7 (reference/bias sourcing) and #15 (DRC/LVS flow precedent). |

### 6.3 Portability assessment: what transfers to gf180mcu 3.3 V

**Ports essentially unchanged (architecture and method):**
- Switching-scheme choice and its energy/CM analysis — technology-independent.
- SAR algorithm, redundancy/non-binary weighting, thermometer/binary segmentation,
  and the digital error-correction arithmetic (the UAH design's 13-raw-bit →
  10-bit reduction with a row of full adders is pure combinational logic `[O]`).
- CDAC layout strategy: common-centroid, dummy ring, interleaved rows/columns,
  symmetric-vs-sequential thermometer decode `[O]`, `[P: Liu 2021]`. Feeds #16.
- The SAR controller RTL and its OpenLane hardening flow.
- Verification methodology and testbench structure, including the batched
  ngspice runner pattern `[O: UAH]`. Feeds #2 and #13.
- The offset-cancellation taxonomy of §3.4 — the techniques and their relative
  costs are technology-independent; only the trim ranges change.

**Does not port — must be redone:**

| Item | Why it breaks | Owner |
|---|---|---|
| **All device sizing** | Different `V_th`, `µC_ox`, and a 3.3 V rather than 1.8 V operating point | #9, #10, #11 |
| **Unit capacitor** | JKU's `C_u = 0.447 fF` `[O]` depends on sky130's specific cap primitives. gf180mcu MIM flavors, density, and minimum geometry differ; §1.3 suggests `C_u ≈ 2–7 fF` here `[D,E4]`. The whole array must be re-sized from #4 data. | #4, #8 |
| **Bootstrapped switch** | sky130's 1.8 V bootstrap reaches 3.6 V on the boost node; a gf180mcu 3.3 V bootstrap reaches **6.6 V**, above the 3.3 V device rating (§5.2) `[D]` | #10 |
| **Custom high-delay standard cell** | `sky130_mm_sc__hd_dlyPoly5ns` `[O]` has no gf180mcu equivalent; the async option would require building and characterizing one | #11 (avoided if §4.5 item 1 is taken) |
| **Comparator input-pair polarity** | CM window differs; a 1.8 V design's NMOS/PMOS choice may invert at 3.3 V | #9 |
| **All absolute power numbers** | CDAC switching energy and digital dynamic power both scale as `V_DD²`. A sky130 1.8 V design's numbers multiply by `(3.3/1.8)² = 3.36×` on gf180mcu at equal capacitance `[D]`. The JKU design's 335 µW at 1.8 V `[O]` would be ~1.1 mW at 3.3 V for the same circuit — **above this block's 1 mW budget.** Power porting is not free. | #1, #8, #11 |
| **DRC/matching/gradient behaviour** | Different rules, different metal stack, different gradient statistics | #15, #16 |

**Net assessment.** Every architectural building block this block needs has been
demonstrated in an open-source flow on an open PDK, and the JKU line has measured
silicon at 11.5 ENOB `[P: Olyanasab 2025]` — so the *approach* carries no
existence risk. gf180mcu-specific SAR prior art is much thinner: one 6-bit 3.3 V
taped-out design `[O]` and one generator-produced 14-bit that only achieved 4.27
ENOB `[O,V]`. The gap between "sky130 open-source SARs reach 11.5 ENOB" and
"gf180mcu open-source SARs have demonstrated ~4 ENOB" is **exactly the canary
gap this block exists to close**, and it is concentrated in device-level
sizing, capacitor matching, and 3.3 V-specific circuit choices — i.e. in #4, #8,
#9, and #10, not in the architecture.

---

## 7. Consolidated shortlist and spec traceability

### 7.1 Recommended shortlist

| Axis | 1st (primary) | 2nd (alternate) | 3rd (deferred / conditional) |
|---|---|---|---|
| **CDAC switching** (#8) | MCS / `V_cm`-based, differential, top-plate sampling | Conventional differential, bottom-plate sampling | Monotonic / set-and-down — only with a PMOS-input comparator and an offset-vs-CM characterization |
| **Comparator** (#9) | StrongARM latch, polarity matched to constant `V_cm`; offset handled digitally, capacitive latch-load trim if needed | Double-tail — if kickback into the CDAC top plate proves limiting | Static preamp + latch — for the 12-bit stretch, or if the transient-noise MC cost dominates schedule |
| **SAR logic** (#11) | Synchronous, `M = 16` (16 MHz @ 1 MS/s) | Hybrid: clocked cycle boundaries + comparator-ready handshake | Fully asynchronous — deferred; revisit only if the rate target moves well above 2 MS/s |
| **Input sampling** (#10, context only) | CMOS transmission gate + dummy compensation + bottom-plate sampling | Upsized T-gate / fixed-CM ground switch | Bootstrap — only after resolving the 6.6 V device-rating question |

### 7.2 Traceability matrix

Every recommendation above, mapped to the README spec parameter it serves and the
evidence behind it.

| Spec parameter | Served by | Evidence |
|---|---|---|
| **Resolution 10 bit** | Constant-CM switching (MCS or conventional) — prevents CM-dependent comparator offset from consuming resolution | §2.3 `[D]`, `[P: Hariprasath 2010]`, `[P: Zhu 2010]` |
| | Unit cap sized by matching, not `kT/C` | §1.2–1.3 `[D]`, `[P: Pelgrom 1989]`, `[P: Saberi 2011]` |
| **Rate 1 MS/s (2 MS/s stretch)** | Synchronous logic at `M = 16` | §1.4, §4.2 `[D,E4]`; `M = 16` sufficiency `[O: UAH]` |
| | StrongARM latch — minimum-latency single-phase decision | §3.7 `[P: Razavi 2015a]` |
| | T-gate sampling — >100 τ acquisition margin | §5.2 `[D,E4]` |
| **ENOB > 9.0 (9.5 stretch)** | Constant-CM switching — removes the code-correlated offset error that appears as distortion | §2.3 `[D]` |
| | Comparator noise budget 0.5–0.9 mV rms, loose for a dynamic latch | §1.1 `[D]`, `[P: Nuzzo 2008]`, `[P: Miyahara 2008]` |
| | Static preamp + latch as the stretch/12-bit escalation | §3.7 `[P: Razavi & Wooley 1992]` |
| **INL / DNL < 1 LSB (0.5 stretch)** | Constant-CM switching — the dominant architectural linearity risk | §2.3, §3.1 `[D]` |
| | `σ_u/C_u` ≤ 1.04 % (0.52 % stretch) as the array-sizing rule | §1.3 `[D]`, `[P: Saberi 2011]` |
| | Redundancy / non-binary weighting (deferred option) against incomplete settling | §4.5 `[P: Kuttner 2002]`, `[P: Liu 2011]`, `[O]` |
| **Power < 1 mW (500 µW stretch)** | MCS switching: ~9 µW reference power vs 74 µW conventional | §2.2 `[D,E4]`, `[P: Hariprasath 2010]`, `[P: Liu 2010]` |
| | StrongARM: zero static power, ~6 µW dynamic | §3.6–3.7 `[D,E4]` |
| | Awareness that `V_DD²` scaling makes ported sky130 power numbers 3.36× larger | §6.3 `[D]` |
| **Area < 0.1 mm²** | MCS/monotonic top-plate sampling: 50 % array reduction | §2.4 `[P: Liu 2010]`, `[P: Hariprasath 2010]` |
| | Capacitor area ≈ 0.004 mm² at the stretch matching target | §1.3 `[D,E4]` |
| | StrongARM: smallest comparator | §3.3 |
| | Warning: an on-chip `V_cm` generator cost ~30 % of a comparable sky130 block's area | §2.4 `[O]` |
| **Interface (SPI + parallel)** | Synchronous logic — the 16–32 MHz clock the SAR needs is likely already present for SPI | §4.3 |
| **Verification cost (not a spec line, but a schedule constraint)** | Synchronous logic — analog core verifiable standalone | §4.4 `[O]` |
| | Static-preamp comparator — the only shortlisted topology whose noise `.noise` can analyze | §3.5 `[O]` |

### 7.3 The single most important finding

If only one thing carries forward from this survey: **at 3.3 V, comparator input
common-mode excursion — not switching energy — is what should decide the CDAC
switching scheme.** The 1.0–1.2 V literature ranks monotonic/set-and-down highly
because its energy and simplicity dominate at low supply and its ~0.6 V CM droop
is tolerable. At 3.3 V the same scheme droops ~1.65 V `[D]`, turning a benign
static comparator offset into a code-correlated linearity error, while the energy
advantage it buys is worth only ~5 µW against a 1 mW budget `[D,E4]`. The ranking
inverts. Constant-CM schemes (MCS, or plain conventional differential) win here
for a reason that the source papers were not optimizing for.

---

## 8. Open questions handed to downstream issues

None of these are answered here; they are the explicit hand-off list.

| # | Question | Blocking |
|---|---|---|
| **#4** | gf180mcu MIM cap flavors, density, minimum geometry, and matching coefficient `A_C` | §1.3, §2.4 — all array sizing |
| **#4** | `V_th`, `µC_ox`, and `R_on(V_in)` for 3.3 V (and 5/6 V) devices | §3.6, §5.3 |
| **#4** | Device noise parameters needed to parameterize `trnoise` injection | §3.5 — the whole comparator noise methodology |
| **#4** | Deep-nwell / isolated-body availability (for offset-trim option 3) | §3.4 |
| **#4** | Standard-cell delay data at 3.3 V across PVT | §4.2, §4.4 |
| **#7** | Is `V_cm` available (on-chip generator, divider+buffer, or external pin)? Decides between shortlist items 1 and 2 on the CDAC axis | §2.4, §2.6 |
| **#7** | Reference source: the §2.4 analysis shows on-chip decoupling alone cannot supply the per-step charge — active drive or off-chip decoupling is required | §2.4 `[D,E4]` |
| **#7 / #12** | Is a 16–32 MHz block-boundary clock acceptable? | §4.3 |
| **#8** | Segmentation (binary vs thermometer/binary), redundancy weighting, split-cap variants | §2.5, §4.5 |
| **#9** | Kickback magnitude into the CDAC top plate at 3.3 V, and whether it forces double-tail | §3.3 |
| **#10** | T-gate `R_on` modulation → THD, and the 6.6 V bootstrap device-rating question if bootstrapping is revisited | §5.2 `[D]` |
| **#13** | Budget for the transient-noise Monte-Carlo campaign: 10³–10⁴ transient runs per corner `[D]` | §3.5 |
| **#2** | Reproduce the Verilator/`d_cosim` mixed-signal path as a smoke test; consider the batched-ngspice-runner pattern | §4.4, §6.1 `[O]` |
| **#1** | Confirm whether the input range is genuinely 0–3.3 V single-ended (drives §1.1's LSB and everything downstream of it) | §1.1 |
| — | Confirm the `[V]`-marked figures against their primary sources before any of them enters a decision record | §0.3 |

**klayout-tools friction:** none encountered during this survey — it is a
documentation deliverable and touched no layout tooling. The layout-adjacent
items likely to generate friction are flagged for #15/#16 (CDAC common-centroid
generation, dummy rings, matched routing).

---

## 9. References

Cited works. DOIs and bibliographic details verified against Crossref on
2026-07-30; abstracts/full text were not retrieved for most entries, which is
why individual *figures* drawn from them carry their own markers above.

**CDAC switching**

- `[P: Liu 2010]` C.-C. Liu, S.-J. Chang, G.-Y. Huang, Y.-Z. Lin, "A 10-bit
  50-MS/s SAR ADC With a Monotonic Capacitor Switching Procedure," *IEEE JSSC*,
  vol. 45, no. 4, pp. 731–740, Apr. 2010. doi:10.1109/JSSC.2010.2042254
- `[P: Hariprasath 2010]` V. Hariprasath, J. Guerber, S.-H. Lee, U.-K. Moon,
  "Merged capacitor switching based SAR ADC with highest switching
  energy-efficiency," *Electronics Letters*, vol. 46, no. 9, pp. 620–621,
  Apr. 2010. doi:10.1049/el.2010.0706
- `[P: Zhu 2010]` Y. Zhu, C.-H. Chan, U-F. Chio, S.-W. Sin, S.-P. U, R. P.
  Martins, F. Maloberti, "A 10-bit 100-MS/s Reference-Free SAR ADC in 90 nm
  CMOS," *IEEE JSSC*, vol. 45, no. 6, pp. 1111–1121, Jun. 2010.
  doi:10.1109/JSSC.2010.2048498
- `[P: Ginsburg 2005]` B. P. Ginsburg, A. P. Chandrakasan, "An Energy-Efficient
  Charge Recycling Approach for a SAR Converter With Capacitive DAC," *ISCAS*,
  2005, pp. 184–187. doi:10.1109/ISCAS.2005.1464555
- `[P: Ginsburg 2007]` B. P. Ginsburg, A. P. Chandrakasan, "500-MS/s 5-bit ADC
  in 65-nm CMOS With Split Capacitor Array DAC," *IEEE JSSC*, vol. 42, no. 4,
  pp. 739–747, Apr. 2007. doi:10.1109/JSSC.2007.892169
- `[P: Yuan 2012]` C. Yuan, Y. Lam, "Low-energy and area-efficient tri-level
  switching scheme for SAR ADC," *Electronics Letters*, vol. 48, no. 9,
  pp. 482–483, Apr. 2012. doi:10.1049/el.2011.4001
- `[P: Saberi 2011]` M. Saberi, R. Lotfi, K. Mafinezhad, W. A. Serdijn,
  "Analysis of Power Consumption and Linearity in Capacitive Digital-to-Analog
  Converters Used in Successive Approximation ADCs," *IEEE TCAS-I*, vol. 58,
  no. 8, pp. 1736–1748, Aug. 2011. doi:10.1109/TCSI.2011.2107214
- `[P: Pelgrom 1989]` M. J. M. Pelgrom, A. C. J. Duinmaijer, A. P. G. Welbers,
  "Matching properties of MOS transistors," *IEEE JSSC*, vol. 24, no. 5,
  pp. 1433–1439, Oct. 1989. doi:10.1109/JSSC.1989.572629

**Comparators**

- `[P: Kobayashi 1993]` T. Kobayashi, K. Nogami, T. Shirotori, Y. Fujimoto, "A
  current-controlled latch sense amplifier and a static power-saving input buffer
  for low-power architecture," *IEEE JSSC*, vol. 28, no. 4, pp. 523–527,
  Apr. 1993. doi:10.1109/4.210039
- `[P: Razavi 2015a]` B. Razavi, "The StrongARM Latch [A Circuit for All
  Seasons]," *IEEE Solid-State Circuits Magazine*, vol. 7, no. 2, pp. 12–17,
  2015. doi:10.1109/MSSC.2015.2418155
- `[P: Schinkel 2007]` D. Schinkel, E. Mensink, E. Klumperink, E. van Tuijl,
  B. Nauta, "A Double-Tail Latch-Type Voltage Sense Amplifier with 18ps
  Setup+Hold Time," *ISSCC Dig. Tech. Papers*, 2007, pp. 314–605.
  doi:10.1109/ISSCC.2007.373420
- `[P: Razavi & Wooley 1992]` B. Razavi, B. A. Wooley, "Design techniques for
  high-speed, high-resolution comparators," *IEEE JSSC*, vol. 27, no. 12,
  pp. 1916–1926, Dec. 1992. doi:10.1109/4.173122
- `[P: Miyahara 2008]` M. Miyahara, Y. Asada, D. Paik, A. Matsuzawa, "A low-noise
  self-calibrating dynamic comparator for high-speed ADCs," *IEEE A-SSCC*, 2008,
  pp. 269–272. doi:10.1109/ASSCC.2008.4708780
- `[P: Nuzzo 2008]` P. Nuzzo, F. De Bernardinis, P. Terreni, G. Van der Plas,
  "Noise Analysis of Regenerative Comparators for Reconfigurable ADC
  Architectures," *IEEE TCAS-I*, vol. 55, no. 6, pp. 1441–1454, Jul. 2008.
  doi:10.1109/TCSI.2008.917991
- `[P: Figueiredo 2006]` P. M. Figueiredo, J. C. Vital, "Kickback noise reduction
  techniques for CMOS latched comparators," *IEEE TCAS-II*, vol. 53, no. 7,
  pp. 541–545, Jul. 2006. doi:10.1109/TCSII.2006.875308
- `[P: Agnes 2008]` A. Agnes, E. Bonizzoni, P. Malcovati, F. Maloberti, "A
  9.4-ENOB 1V 3.8 µW 100kS/s SAR ADC with Time-Domain Comparator," *ISSCC Dig.
  Tech. Papers*, 2008, pp. 246–610. doi:10.1109/ISSCC.2008.4523149

**SAR logic, redundancy, and system**

- `[P: Chen 2006]` S.-W. M. Chen, R. W. Brodersen, "A 6-bit 600-MS/s 5.3-mW
  Asynchronous ADC in 0.13-µm CMOS," *IEEE JSSC*, vol. 41, no. 12,
  pp. 2669–2680, Dec. 2006. doi:10.1109/JSSC.2006.884231
- `[P: Kuttner 2002]` F. Kuttner, "A 1.2V 10b 20MSample/s non-binary successive
  approximation ADC in 0.13 µm CMOS," *ISSCC Dig. Tech. Papers*, 2002,
  pp. 176–177. doi:10.1109/ISSCC.2002.992993
- `[P: Liu 2011]` W. Liu, P. Huang, Y. Chiu, "A 12-bit, 45-MS/s, 3-mW Redundant
  Successive-Approximation-Register Analog-to-Digital Converter With Digital
  Calibration," *IEEE JSSC*, vol. 46, no. 11, pp. 2661–2672, Nov. 2011.
  doi:10.1109/JSSC.2011.2163556
- `[P: Harpe 2011]` P. Harpe, C. Zhou, Y. Bi, N. van der Meijs, X. Wang et al.,
  "A 26 µW 8 bit 10 MS/s Asynchronous SAR ADC for Low Energy Radios," *IEEE
  JSSC*, vol. 46, no. 7, pp. 1585–1595, Jul. 2011. doi:10.1109/JSSC.2011.2143870
- `[P: van Elzakker 2010]` M. van Elzakker, E. van Tuijl, P. Geraedts,
  D. Schinkel, E. Klumperink et al., "A 10-bit Charge-Redistribution ADC
  Consuming 1.9 µW at 1 MS/s," *IEEE JSSC*, vol. 45, no. 5, pp. 1007–1015,
  May 2010. doi:10.1109/JSSC.2010.2043893 — *closest published spec match to this
  block (10-bit, 1 MS/s), though at 1.0 V in 65 nm.*
- `[P: Scott 2003]` M. D. Scott, B. E. Boser, K. S. J. Pister, "An ultralow-energy
  ADC for smart dust," *IEEE JSSC*, vol. 38, no. 7, pp. 1123–1129, Jul. 2003.
  doi:10.1109/JSSC.2003.813296
- `[P: Tsai 2015]` J.-H. Tsai, Y.-J. Wang, Y.-C. Yen, T.-Y. Lai et al., "A
  0.003 mm² 10b 240 MS/s 0.7 mW SAR ADC in 28 nm CMOS With Digital Error
  Correction and Correlated-Reversed Switching," *IEEE JSSC*, vol. 50, no. 6,
  pp. 1382–1398, Jun. 2015. doi:10.1109/JSSC.2015.2413850

**Input sampling**

- `[P: Abo & Gray 1999]` A. M. Abo, P. R. Gray, "A 1.5-V, 10-bit, 14.3-MS/s CMOS
  pipeline analog-to-digital converter," *IEEE JSSC*, vol. 34, no. 5,
  pp. 599–606, May 1999. doi:10.1109/4.760369
- `[P: Steensgaard 1999]` J. Steensgaard, "Bootstrapped low-voltage analog
  switches," *ISCAS*, 1999, vol. 2, pp. 29–32. doi:10.1109/ISCAS.1999.780611
- `[P: Dessouky & Kaiser 1999]` M. Dessouky, A. Kaiser, "Input switch
  configuration suitable for rail-to-rail operation of switched opamp circuits,"
  *Electronics Letters*, vol. 35, no. 1, pp. 8–10, Jan. 1999.
  doi:10.1049/el:19990028
- `[P: Aksin 2005]` D. Aksin, M. Al-Shyoukh, F. Maloberti, "A bootstrapped switch
  for precise sampling of inputs with signal range beyond supply voltage,"
  *IEEE CICC*, 2005, pp. 738–741. doi:10.1109/CICC.2005.1568775
- `[P: Razavi 2015b]` B. Razavi, "The Bootstrapped Switch [A Circuit for All
  Seasons]," *IEEE Solid-State Circuits Magazine*, vol. 7, no. 3, pp. 12–15,
  2015. doi:10.1109/MSSC.2015.2449714
- `[P: Wei 2011]` H. Wei, C.-H. Chan, U-F. Chio, S.-W. Sin et al., "A 0.024 mm²
  8b 400MS/s SAR ADC with 2b/cycle and resistive DAC in 65nm CMOS," *ISSCC Dig.
  Tech. Papers*, 2011, pp. 188–190. doi:10.1109/ISSCC.2011.5746276

**Open-source flow, open PDKs, and simulation methodology**

- `[P: Olyanasab 2025]` A. Olyanasab, M. Fath, T. Schreiner, C. Guger, H. Pretl,
  "An 8.1-µW 12-bit Non-Binary Self-Clocked SAR-ADC in 130 nm Open-Source PDK,"
  *Austrochip Workshop on Microelectronics*, 2025, pp. 45–48.
  doi:10.1109/AUSTROCHIP67945.2025.11183685
- `[P: Liu 2021]` J. Liu, H. Tang, Y. Zhu, Z. Chen, N. Sun, "OpenSAR: An Open
  Source Automated End-to-end SAR ADC Compiler," *IEEE/ACM ICCAD*, 2021,
  pp. 1–9. doi:10.1109/ICCAD51958.2021.9643494
- `[P: Jaramillo-Toral 2025]` J. Jaramillo-Toral, S. Ortega-Cisneros et al.,
  "Analog Blocks for 8-Bit SAR ADC: Rail-to-Rail Comparator and Two-Stage
  Operational Amplifier Designed with Open-Source Tools and Sky130 PDK,"
  *IEEE APCCAS*, 2025, pp. 1–5. doi:10.1109/APCCAS67402.2025.11378356
- `[P: Jaramillo-Toral 2024]` J. Jaramillo-Toral, S. Ortega-Cisneros et al.,
  "Automated IC Design Flow Using Open-Source Tools and 180 nm PDK," *IEEE
  MWSCAS*, 2024, pp. 1393–1397. doi:10.1109/MWSCAS60917.2024.10658750
- `[P: Murmann 2012]` B. Murmann, "Thermal Noise in Track-and-Hold Circuits:
  Analysis and Simulation Techniques," *IEEE Solid-State Circuits Magazine*,
  vol. 4, no. 2, pp. 46–54, 2012. doi:10.1109/MSSC.2012.2192190 — *methodology
  reference for the §3.5 sampled-noise simulation approach.*
- `[P: Chow 2007]` H. C. Chow, S. H. Lee, "Transient Noise Analysis for
  Comparator-Based Switched-Capacitor Circuits," *ISCAS*, 2007, pp. 953–956.
  doi:10.1109/ISCAS.2007.378084

**Open-source artifacts** (all `[O]`, inspected 2026-07-30; repository state is
mutable — re-verify before relying on any detail)

- `UAH-IC-Design-Team/sky130-10-bit-SAR-ADC` (Apache-2.0) — 10-bit synchronous
  sky130 SAR; also `UAH-IC-Design-Team/ngspice-batch-runner`.
- `jjbbff/SKY__ADC-2496` (Apache-2.0) — EuroCDP-packaged mirror of
  `efabless/SKY130_SAR-ADC1`; JKU IIC 12-bit non-binary self-clocked SAR
  (M. Moser, MSc thesis, JKU Linz 2023); layout on Open MPW-8 via
  `iic-jku/mpw8-submission`.
- `rnunes2311/SAR_ADC_12bit` (Apache-2.0) — 12-bit sky130 SAR with IMCS switching
  and comparator offset self-calibration.
- `Vaticori/3bit_sar_adc` — xschem + Verilator + ngspice mixed-signal SAR demo.
- `ishi-kai/Chipathon2023_ADC` — 6-bit 3.3 V gf180mcu SAR, SSCS Chipathon 2023,
  taped out on WaferSpace Run-1.
- `egorxe/gf180mcu_ip_collection` — index of taped-out open-source gf180mcu
  analog IP (ADC/DAC, PLL, BGR, LDO, current source, XTAL).
- `arjun2000ananth/sar_adc_gf180` — claimed 10-bit gf180mcu SAR; undocumented.
- `victorpreuss/analog_design_with_gf180mcu` — gf180mcu transistor
  characterization notebooks; potentially useful starting point for #4.
- Local `ngspice-46` install (`/opt/homebrew/`): `digital.cm` (`d_dff`,
  `d_process`), `d_cosim`, `ivlng.so` / `ivlng.vpi`, and `trnoise` / `trrandom` /
  `notrnoise` support — the basis for the §3.5 and §4.4 capability claims.
