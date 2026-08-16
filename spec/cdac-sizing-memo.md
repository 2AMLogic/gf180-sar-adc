# CDAC sizing memo — unit cap from kT/C + matching budget

**Status**: design memo, feeds the pending ratified spec (#1). Not a decision
record (see `spec/decision-records/README.md` — this is derivation/analysis,
cited *from* decision records, not itself one).
**Issue**: #8. **Consumes**: DR-0011 (switching-scheme choice),
`sim/device-characterization-report.md` §1–§5.1 (measured/derated device
data), DR-0002 (reference-drive envelope).
**Feeds**: #9 (comparator CM budget — see DR-0011), #12 (settling budget,
§5), #14 (Monte Carlo mismatch model, §3), #15/#16 (array size, §5).

---

## 0. Scope and topology recap

DR-0011 fixes the switching scheme this memo sizes against: **MCS /
Vcm-based, differential, top-plate sampling**, `N = 10` bits, `2^(N-1) = 512`
unit-capacitor positions per side. Top-plate sampling resolves bit 1 (the
MSB) with **no array switching** — the comparator's first decision is the
sign of the sampled differential charge — so the array implements only bits
2..10: 511 binary-weighted positions (weights `2^8..2^0` = 256..1) plus one
terminating unit (weight 1, fixed to `V_cm`, never switched), summing to the
full `2^(N-1)` capacitance.

This matters for *every* section below: `C_sample` (§1), the matching
worst-case transition (§2), and the settling load (§5) are all different
numbers here than they would be for the plain-binary conventional array the
prior-art survey's placeholder arithmetic used (`spec/prior-art-survey.md`
§1.2–§1.4) — each is re-derived for this topology, not carried over.

Both input modes use the same array, the same unit cap, and the same
per-side `V_REF/2` bottom-plate step — but **not** the same switching
sequence:

- **Single-ended (pseudo-differential)**: one side samples `V_in` (0–3.3 V),
  the other is pinned to `V_cm`. Effective full-scale at the comparator is
  `V_REF` (3.3 V); `LSB_se = V_REF/1024 = 3.2227 mV`. **Only the side that
  sampled `V_in` switches per trial**, so the per-trial differential step is
  `(V_REF/2)·(w/512) = V_REF·w/1024` — exactly `LSB_se` at `w = 1`.
- **Differential**: both sides driven `±V_REF` about `V_cm`. Effective
  full-scale is `2·V_REF` (6.6 V); `LSB_diff = 2·V_REF/1024 = 6.4453 mV`.
  **Both sides switch per trial** (decided block to `V_REF`, mirror block to
  `GND`), so the per-trial differential step is `V_REF·w/512` — exactly
  `LSB_diff` at `w = 1`.

(DR-0002's full-scale mapping, restated here because §1/§4 need the exact
LSB in each mode.) The mode-dependence of the sequence is not optional:
switching both sides in single-ended mode would double every step and
resolve 9 bits, not 10, across the 3.3 V span. DR-0011's Decision states the
full sequence, its per-mode step sizes, and the correction-range check.

**No derivation in §1–§5 below changes with the mode**, because the array
does not: the sampling event is identical (§1.1), the matching propagation is in
units of the array's own LSB and both the step and the LSB scale together
between modes (§3.2), and the per-trial settling network is one side's
charge divider either way (§5.3). Where a mode-specific *number* is needed
(the LSB the budget is compared against), both modes are carried explicitly
and the binding one is identified.

---

## 1. kT/C noise-limited sizing

### 1.1 Effective sampling capacitance for THIS topology

Top-plate sampling means the input is sampled directly onto each side's
**entire per-side array**, `C_side = 2^(N-1)·C_u = 512·C_u`, through that
side's sampling switch. When the switch opens, the sampled thermal noise
variance is `kT/C_side` **per side**. The two sides sample independently
(separate switches, uncorrelated noise), so the differential-referred
sampled noise variance is the sum:

```
v_n,rms = sqrt(kT/C_side + kT/C_side) = sqrt(2·kT/C_side)
```

This is the same expression in both input modes (the physical sampling
event is identical); only the LSB it is compared against differs (§0).

### 1.2 ENOB headroom allocation — kT/C gets a stated fraction, not the whole budget

`spec/prior-art-survey.md` §1.1 derives the total allowable non-quantization
error for **ENOB > 9.0** (single-ended, `V_FS = V_REF`) as
`σ_total ≤ √3 × (LSB_se/√12) = 1.6113 mV rms`, and for **ENOB > 9.5**
(stretch) as `σ_total ≤ 0.930 mV rms`. That total is a **shared** budget
across kT/C noise (this section), comparator noise (#9), and reference
noise/distortion (DR-0002) — consuming all of it here would leave nothing
for the other two.

**Allocation used**: an equal three-way split (kT/C : comparator :
reference+distortion), matching the split the survey already applies to the
stretch case. This is a policy choice stated here, not implied:

| Target | `σ_total` (whole budget) | kT/C share (1/3) |
|---|---|---|
| ENOB > 9.0 (baseline) | 1.6113 mV rms | **0.930 mV rms** |
| ENOB > 9.5 (stretch) | 0.930 mV rms | **0.537 mV rms** |

### 1.3 Differential mode's budget, sized separately

Differential mode's full-scale is `2×` single-ended, so its quantization
step and its ENOB-derived non-quantization budget scale by the same `2×`
(SNR/ENOB is defined relative to full-scale, and the *shape* of §1.1's
derivation is unchanged — only `LSB_diff` replaces `LSB_se`):

| Target | `σ_total` (differential, whole budget) | kT/C share (1/3) |
|---|---|---|
| ENOB > 9.0 (baseline) | 3.2227 mV rms | **1.860 mV rms** |
| ENOB > 9.5 (stretch) | 1.8606 mV rms | **1.074 mV rms** |

Differential mode's budget is **looser** than single-ended's at every
target, so single-ended is the binding case for kT/C sizing; differential is
reported to show it is met with more margin, per the issue's requirement
that both modes be sized, not merely asserted safe by similarity.

### 1.4 Minimum `C_side` from kT/C, all four cases, at both 300 K and the hot corner

Inverting §1.1: `C_side,min = 2·kT / budget²`. `kT` scales with absolute
temperature and this block is specified over **−40…125 °C**, so the binding
evaluation is the **hot corner**, `T = 125 °C` (398.15 K,
`kT = 5.50×10⁻²¹ J`) — 32.7 % more sampled noise power than the 300 K value
(`kT = 4.14×10⁻²¹ J`) that `spec/prior-art-survey.md` §1.2 and the rest of
this repo quote. Both columns are carried so the comparison with the survey
stays like-for-like, but **the 125 °C column is the one that binds**:

| Mode | Target | Budget | `C_side,min` @ 300 K | `C_side,min` @ 125 °C | `C_u,min` @ 125 °C (÷512) |
|---|---|---|---|---|---|
| Single-ended | ENOB > 9.0 | 0.930 mV | 9.57 fF | **12.71 fF** | 0.025 fF |
| Single-ended | ENOB > 9.5 | 0.537 mV | 28.71 fF | **38.1 fF** | 0.0745 fF |
| Differential | ENOB > 9.0 | 1.860 mV | 2.40 fF | **3.18 fF** | 0.0062 fF |
| Differential | ENOB > 9.5 | 1.074 mV | 7.19 fF | **9.53 fF** | 0.019 fF |

**The worst (largest) `C_side,min` across both modes, both targets and the
full temperature range is 38.1 fF** (single-ended, ENOB > 9.5 stretch,
125 °C; 28.71 fF at 300 K) — tens of femtofarads, ~230× below anything
matching will require (§4), i.e. two and a half orders of magnitude, not
three. This reproduces `spec/prior-art-survey.md` §1.2's headline finding
("kT/C is not the binding constraint at 3.3 V") *for this topology
specifically* and *over the specified temperature range*, rather than
carrying it over unchecked at a single temperature.

---

## 2. Matching data and its provenance

Per `sim/device-characterization-report.md` §5.1 (**gap, stated there**):
the gf180mcu open PDK has **no local capacitor mismatch model** —
`cap-local-mismatch` and `moscap-statistics` are both `ABSENT` findings from
`sim/tools/pdk_mismatch_audit.py`. `σ(ΔC/C)` for the unit cap is therefore
**not obtainable from this PDK by simulation**. The report supplies a
working substitute, tagged `literature-assumption-with-derating`:

- Functional form: Pelgrom area law, `σ(ΔC/C) = A_C / √A_unit`, `A_C` in
  `%·µm` — not in dispute.
- `A_C = 1.0 %·µm` planning value (no verified citation in this repo) —
  **2× derated to `A_C = 2.0 %·µm`** for budgeting, per the report's stated
  policy, until foundry data replaces it.

This memo uses **`A_C = 2.0 %·µm`, `literature-assumption-with-derating`**,
citing `sim/device-characterization-report.md` §5.1 directly, and inherits
its caveat: a 2× error in `A_C` is a 3.6× error in required area (§5.1), so
every unit-cap number below should be re-checked once foundry MiM matching
data replaces this placeholder.

---

## 3. Matching-to-linearity propagation — re-derived for THIS array, not plain binary

The issue's design guidance is explicit that the plain-binary
`σ(DNL) ≈ √(2^N−1)·σ_u` formula (`sim/device-characterization-report.md`
§5.1's own worked example) **does not directly apply** to a non-plain-binary
topology, and must be re-derived for the array DR-0011 actually chose.

### 3.1 The free MSB carries zero mismatch

Bit 1 is decided directly from the sampled charge at the end of acquisition
— **no capacitor switches** to make this decision. The two sides' *total*
array capacitances (`C_side,P` vs. `C_side,N`) could in principle differ
(a side-to-side mismatch), but the sampled *voltage* on each side's top
plate is set by the input source through a low-impedance switch, not by a
charge-division ratio — so a side-to-side capacitance mismatch does not
perturb this decision at all (it would only matter if this were a
charge-redistribution decision, which it is not). **Bit 1 is exactly the
kind of decision this scheme was chosen for (DR-0011): it carries no
code-correlated error from CDAC mismatch, full stop.**

### 3.2 The remaining 9 bits: a `2^(N-1)`-element binary sub-array

Bits 2..10 are resolved by the 512-position sub-array (§0): 511 real binary
weights `2^8..2^0` plus one terminating unit. The worst-case transition for
a binary-weighted array of `M = 2^(N-1)` positions occurs at *that
sub-array's own* MSB carry (weight 256 vs. the rest), by the same argument
`sim/device-characterization-report.md` §5.1 applies to the full array —
substituting `M = 2^(N-1)` for `2^N`:

```
σ(DNL)_max = √(2^(N-1) − 1) · σ_u = √511 · σ_u ≈ 22.61 · σ_u   LSB
σ(INL)_max = (√(2^(N-1))/2) · σ_u = (√512/2) · σ_u ≈ 11.31 · σ_u   LSB
```

against the plain-binary (§5.1) coefficients of `31.98·σ_u` (DNL) and
`16.00·σ_u` (INL) for a full `2^10` array. **This scheme's worst-case
mismatch sigma is √2 ≈ 1.414× smaller than the plain-binary case at the same
`σ_u`** — a direct, quantified consequence of DR-0011's free-MSB property,
not a restatement of the survey's placeholder arithmetic.

These coefficients are **per side**, in units of *that side's* own step, and
they hold in **both** input modes despite the mode-dependent switching
sequence (§0): in single-ended mode one side's array performs the whole
correction and its step *is* `LSB_se`, so the coefficients apply directly;
in differential mode both sides switch, and both the step and the LSB double
together, so the ratio — which is all DNL/INL-in-LSB depends on — is
unchanged. Single-ended is the case to design to: it is the tighter LSB, and
it is the mode in which a *single* array's mismatch sets the error with no
second, independently-mismatched side to average against. The coefficients
are therefore a bound in differential mode, not an equality.

### 3.3 Yield criterion

The spec's `< 1 LSB` target (`< 0.5 LSB` stretch) states no confidence
level. **This memo adopts 3σ**, for two stated reasons:

1. It matches the convention already in force elsewhere in this repo
   (`spec/prior-art-survey.md` §1.3's DNL table, and the requirement-inversion
   worked example in `sim/device-characterization-report.md` §5.1) — using a
   different criterion here would make this memo's numbers incomparable with
   both.
2. 3σ is standard capacitor-matching sizing practice, and — as §4 shows —
   the resulting unit cap costs negligible area against the 0.1 mm² budget,
   so there is no area/schedule pressure to relax to a looser (e.g. 2σ)
   criterion, nor is a 6σ criterion needed to buy meaningful additional
   margin at this cost.

### 3.4 Required `σ_u`

Inverting §3.2's DNL expression (the binding one, per §3.5) at 3σ:

| Target | `σ(DNL)` bound | Required `σ_u = σ(ΔC/C)` |
|---|---|---|
| < 1 LSB (baseline) | 1/3 LSB (1σ) | `1/(3·22.61)` = **1.474 %** |
| < 0.5 LSB (stretch) | 1/6 LSB (1σ) | `0.5/(3·22.61)` = **0.737 %** |

(For reference, the plain-binary coefficients from
`sim/device-characterization-report.md` §5.1 give 1.04 % / 0.52 % at the same
targets — this scheme relaxes both by exactly √2, as §3.2 predicts.)

### 3.5 DNL, not INL, is binding

`σ(INL)_max = 11.31·σ_u` vs. `σ(DNL)_max = 22.61·σ_u`: DNL's coefficient is
~2× INL's for any binary array — the ratio is `2·√(M−1)/√M`, which is
1.998 at `M = 512` and 1.999 at the plain-binary `M = 1024`, so the factor
is architecture-invariant to within 0.1 % and not an artifact of this
topology. **DNL is therefore the binding linearity constraint among
DNL/INL** at every target level; a design that meets the DNL bound meets
the INL bound with room to spare (`σ(INL)` at the DNL-derived `σ_u` is half
the DNL bound). §3.6 below shows a *third* matching-based row — gain error —
whose own coefficient is tighter still, and which §3.5's argument does not
cover because it is not a DNL/INL quantity at all.

### 3.6 Gain error, mismatch: a total-array sum, not a DNL/INL coefficient — issue #177

§3.1–§3.5 derive DNL/INL from the sub-array's own worst *transition*
(weight-256 carry). **Gain error is a different mechanism entirely**: it is
the 3σ spread of the array's *total* capacitance away from nominal —
`README.md#target-specification`'s **Gain error, mismatch** row (note
**[e]**), `≤ 0.5 LSB`, untrimmed, 3σ, no stretch line. Both DR-0011's free
MSB (§3.1) and the split topology's per-side sub-array structure (§3.2) are
irrelevant to this sum: `C_total = 2·C_side = 1024·C_u` (§5.2) is drawn from
**every** real physical unit cap in the design — both sides' 511 switched
positions plus both sides' terminating dummies, 1024 independent
`N(0, σ_u)` draws — with no free-MSB exemption and no benefit from the
`√511`-vs-`√1023` relief §3.2 derives for DNL/INL. A 1 LSB (single-ended)
step is exactly one unit-cap's nominal contribution to the array's total
(§0), so the total-array relative deviation *is* the sum of all 1024 unit
deltas, in LSB, directly — no separate scaling — and by the same
independent-sum argument §3.2 uses (just over `1024`, not `511`, positions
and with no `/2` INL-style averaging):

```
σ(gain error) = √1024 · σ_u = 32 · σ_u   LSB
```

This is `sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py`'s own
`ANALYTIC_GAIN_COEFF = √1024` and matches README note [e]'s
`3 × σ_u / √1024` formula exactly (the coefficient is the same
`√(array size)` either way of writing it).

**Required `σ_u` at 3σ**, inverting the above at the ratified `≤ 0.5 LSB`
target (no baseline/stretch split for this row, per DR-0012):

```
0.5 LSB = 3 · 32 · σ_u   =>   σ_u ≤ 0.5 / 96 = 0.520833 %
```

**This is tighter than either DNL/INL requirement in §3.4**
(`0.737 %` stretch, `1.474 %` baseline) by `32 / 22.61 ≈ 1.415 ≈ √2` and
`32 / 11.31 ≈ 2.83 ≈ 2√2` respectively — exactly the inverse of the
free-MSB relief §3.2 quantifies, because gain error is the one matching-based
row that does **not** receive that relief. **Gain error, not DNL, is
therefore the true binding constraint on `σ_u` for this array** — the
`C_u = 17.24 fF` chosen in §4 (sized to DNL/INL's own stretch target,
`σ_u ≤ 0.737 %`) satisfies DNL/INL comfortably but leaves gain error's
tighter `0.521 %` ceiling unmet: the calibrated `σ_u = 0.7372 %` that
geometry implies (§4) is **1.42× over** the `0.521 %` gain-error ceiling,
which is exactly the `√2` factor `sim/mc-cdac-mismatch/records/
20260816-044942-56fbe50.md`'s `2.12σ`-against-3σ finding (issue #172)
measures empirically (`3σ = 0.708 LSB` against the `0.5 LSB` target,
`0.708/0.5 = 1.42`, to rounding). This is a real, quantified consequence of
sizing `C_u` against the wrong one of the three matching coefficients, not a
testbench defect — see issue #177 and
`spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`
for the resizing decision this finding drives.

**Because gain error's `0.521 %` ceiling is the tightest of the three**
(gain `0.521 %` < DNL/INL stretch `0.737 %` < DNL/INL baseline `1.474 %`),
sizing `C_u` to satisfy it satisfies DNL/INL simultaneously, with the same
room-to-spare relationship §3.5 already establishes between DNL and INL —
this is a single binding-constraint resize, not a three-way trade between
rows.

---

## 4. Required unit-cap area and capacitance

Combining §3.4's `σ_u` requirement with the Pelgrom law
(`A_unit = (A_C/σ_u)²`, `A_C = 2.0 %·µm`, §2) and the *measured* density law
from `sim/device-characterization-report.md` §1.2
(`C(W,L) = 1.99·W·L + 0.4766·(W+L)` fF, `W,L` in µm, square unit `W=L=s` so
`C(s) = 1.99·s² + 0.9532·s`):

| Target | `σ_u` | `A_unit` | Unit side `s` | `C_u` (measured density law) |
|---|---|---|---|---|
| DNL/INL < 1 LSB (baseline) | 1.474 % | 1.839 µm² | 1.356 µm | **4.95 fF** |
| DNL/INL < 0.5 LSB (stretch) | 0.737 % | 7.36 µm² | 2.713 µm | **17.24 fF** |
| Gain error ≤ 0.5 LSB (§3.6, binding) | 0.5208 % | 14.75 µm² | 3.840 µm | **33.00 fF** (exact-boundary) |

**Historical sizing (superseded by issue #177 — kept here for provenance,
not the current chosen value): `C_u = 17.24 fF`** (2.0 fF/µm² MiM flavor,
2.71 µm × 2.71 µm drawn), sized to the DNL/INL **stretch** (< 0.5 LSB, 3σ)
target. This was a deliberate choice at the time — meeting only the DNL/INL
baseline (< 1 LSB) target would have needed `C_u ≈ 4.95 fF`, roughly 3.5×
smaller, and sizing to the DNL/INL stretch target was believed to cost only
a negligible amount of array area (§5) while buying margin toward the
ENOB > 9.5 / 12-bit-stretch aspirations. **This sizing did not check the
gain-error row's own (tighter) coefficient (§3.6)**, and `sim/mc-cdac-
mismatch/records/20260816-044942-56fbe50.md` (issue #172) measured the
consequence directly: the row clears only 2.12σ against the ratified 3σ
condition.

**Chosen unit cap (current, issue #177 / DR-0019): `C_u = 35.6528 fF`
(2.0 fF/µm² MiM flavor, 4.0 µm × 4.0 µm drawn, `σ_u = 0.5000 %`)** —
sized to the **gain-error** constraint (§3.6, the true binding one) with a
deliberate margin over its exact-boundary value (`33.00 fF` / `3.84 µm` /
`σ_u = 0.5208 %`, third row of the table above): the exact-boundary sizing
puts the gain-error row's *measured* (not merely analytic) 3σ margin at only
`3.009σ` against the 3σ target (`sim/mc-cdac-mismatch/runs/
20260816-125421-737d16e/` at `σ_u = 0.520833 %`, N = 20000) — indistinguishable
from a re-run of the exact failure mode issue #177 exists to close, since a
different seed or a small model-input change could push the same design back
under 3σ. The chosen `s = 4.0 µm` instead measures `3.13σ` (`sigma_to_spec`,
`klt yield`), a real, not-knife-edge margin, for a **negligible extra area
cost** over the exact-boundary point (`layout/adc-top/area_feasibility.py`:
0.18045 mm² at `s = 4.0 µm` vs. 0.17721 mm² at `s = 3.84 µm`, +1.8 %) — see
`spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`
for the full rationale, verification, and area-impact accounting.

**Why not size it larger still, for more margin?** Because the resize has a
*ceiling* as well as a floor: `C_in = C_side = 512·C_u` is a published,
ratified quantity that enters DR-0013's input drive contract directly, and
inverting that contract caps the unit cap at `C_u ≤ 39.06 fF`
(`s ≤ 4.1975 µm`) — §5.5. Together with §3.6's floor this leaves the narrow
window `3.840 µm ≤ s ≤ 4.1975 µm`; `s = 4.0 µm` is chosen from inside it,
with headroom against both bounds. Note on the third row of the table above:
its `σ_u = 0.5208 %` / `s = 3.840 µm` entry is the *floor* of that window,
not a candidate design.

**This value is not yet reflected in `design/adc-top/gen_adc_top.py` or
`layout/adc-top/`** (both still carry the historical `17.24 fF` pending the
physical-implementation follow-up DR-0019 names) — this memo records the
sizing *decision*, verified against the standalone Monte Carlo mismatch
model (the same evidentiary standard every other matching-based row in this
memo already relies on, since the PDK ships no local capacitor mismatch
model to simulate against directly, §2).

Note on `sim/device-characterization-report.md` §1.5: unit caps at or below
5 µm on a side (both rows above qualify) carry a **−81 ppm/V** datasheet
voltage coefficient — 9× larger and opposite sign to the 10×10 µm device,
and **not present in the simulated path** (the PDK's ngspice deck has the
bias-dependent `c_cap` line commented out, §1.5). This is a real linearity
term future work must apply by hand; no simulated CDAC result in this repo
contains it.

---

## 5. Dominant constraint, total array capacitance, and settling

### 5.1 Dominant constraint: matching, not noise — by ~230×, ~480× at the resized `C_u`

| Constraint | Minimum `C_u` (worst case across modes/targets) |
|---|---|
| kT/C noise (§1.4), worst case: 125 °C | 0.0745 fF (single-ended, ENOB > 9.5) |
| kT/C noise (§1.4), at 300 K for reference | 0.056 fF (single-ended, ENOB > 9.5) |
| Matching (§4), historical (superseded) | 17.24 fF (DNL/INL stretch target) |
| Matching (§4), current (issue #177 / DR-0019) | 35.65 fF (gain-error target, with margin) |

**Matching dominates by a factor of ~231× at the worst-case temperature**
(17.24 / 0.0745) at the historical sizing, and by ~231× × (35.65/17.24) ≈
**478×** at the resized `C_u` — kT/C noise only gets *more* margin as `C_u`
grows, never less. This is the memo's central finding, unchanged by the
resize: the unit cap is set entirely by the matching/linearity budget: if
`sim/device-characterization-report.md` §5.1's `A_C` assumption later comes
in worse than the 2.0 %·µm derated planning value used here, **all** of the
resulting margin should be spent re-checking §3–§4, not §1.

### 5.2 Total array capacitance — flagged for #12, revised by issue #177 / DR-0019

```
C_side  = 512 · C_u = 512 · 35.6528 fF = 18.254 pF   (per side)
C_total = 2 · C_side                   = 36.508 pF   (both sides, differential)
```

(Historical, superseded values at `C_u = 17.24 fF`: `C_side = 8.827 pF`,
`C_total = 17.65 pF` — still the numbers `design/adc-top/` and
`layout/adc-top/` currently draw, pending the physical-implementation
follow-up DR-0019 names; see §4's "Chosen unit cap" note.)

**`C_total ≈ 36.5 pF` (≈ 2.07×) is the number #12's settling/timing budget
and #15/#16's array layout must plan against once the resize is
implemented.** For contrast: DR-0002 derived its reference-drive envelope
(`Z_ref ≤ 240 Ω`, `C_dec ≥ 40 nF`) conservatively against a **34 pF "whole
planning array"** figure (the plain-binary `2^N`-unit example in
`sim/device-characterization-report.md` §5.1, at the same
`C_u`-derivation policy) — close to, but no longer comfortably double, this
scheme's real resized `C_total`. §5.3's cross-check re-states the margin at
the resized value: it still clears DR-0002's envelope, with less headroom
than the historical sizing had.

### 5.3 Settling: per-bit simulation, and DR-0002 cross-check

**Simulated** (not merely estimated): `sim/cdac-bit-settling/` sizes each
trial's switching cap and its fixed sub-array load directly from this memo's
`C_u` (§4) via the measured density law, and drives them through real
gf180mcu T-gate switches (same sizing as `sim/device-switch-ron/`). **This
simulation is at the historical `C_u = 17.24 fF`**, not yet re-taken at the
resized `35.6528 fF` (issue #177 / DR-0019) — the analytic re-derivation at
the end of this section shows the margin the resize leaves, but a
transistor-level re-run at the new `C_u` is tracked as follow-up work
(DR-0019's Consequences), not done here.

**Which step the testbench measures, in mode terms.** The testbench measures
the **per-side** top-plate step, `(V_REF/2)·(w/512)` — its `w = 1` row is
annotated `V_ref/1024 = 1 LSB`. Per §0/DR-0011 that is *exactly* the
single-ended mode's differential step (`V_REF·w/1024`, one side switching)
and *exactly half* the differential mode's (`V_REF·w/512`, both sides
switching). **The settling result is common to both modes**: the switched
network is one side's charge divider either way, and differential mode
simply performs the identical transient on the mirror side at the same
instant, into `GND` instead of `V_REF`. Single-ended is therefore the
measured case *and* the conservative one — the 0.5 LSB bound below is
evaluated against the tighter `LSB_se`.

The settling derivation predicts a specific worst bit:
`Ceq(w) = w·(2^(N-1)−w)·C_u / 2^(N-1)` is maximised at `w = 2^(N-2) = 256`,
the sub-array's own MSB. The testbench does **not** take that on faith — it
instantiates four of the nine switched trials spanning the whole weight
range (`w = 1, 16, 64, 256`, plus both switching directions at `w = 256`)
and measures each independently at every PVT point, so "w = 256 is the worst
bit" is a measured result rather than an assumption inherited from the
derivation.

Result, over the full 117-point PVT grid (`full` corner set × 3 temperatures
× 3 supplies), **117/117 PASS**:

- **Every** trial's top-plate settling error at the 1 MS/s bit-cycle budget
  (62.5 ns, `spec/prior-art-survey.md` §1.4) is at or below the simulator's
  numeric floor (`|err| ≤ 1×10⁻⁴ mV`) at every corner — four orders of
  magnitude inside the 0.5 LSB (1.6113 mV) bound. The same holds,
  informationally, at the 2 MS/s stretch budget (31.25 ns).
- The residual-lag probe at 1.5 ns (still inside the transient) confirms the
  predicted ordering at **every one of the 117 points**: `w = 256` lags most
  (0.42–0.74 of its own step), then `w = 64` (0.13–0.50), then `w = 16`
  (0.0005–0.069), then `w = 1` (0 to numeric precision). The `lag_ord_*`
  checks assert this ordering as a pass/fail criterion, so a wrong load model
  (e.g. the whole per-side array instead of the charge divider) would fail
  the run rather than pass silently.
- `w = 1`'s lag is legitimately zero: its `Ceq ≈ 17.2 fF` against the switch
  `R_on` gives `τ ≈ 10 ps`, two orders of magnitude below the 200 ps driving
  edge, so the LSB trial is edge-rate-limited and has no RC settling problem
  at all.
- The realized step per trial is `(V_REF/2)·(w/512)` to within the supply
  tolerance, with **zero process-axis spread** (`≤ 2×10⁻⁴ %`): a die-global
  capacitance shift (`mim_ff`/`mim_ss`) cancels exactly in the charge-division
  ratio. That is the measured confirmation of why §3's *local* mismatch — not
  the process corner — is what sets linearity, and hence why the PDK's
  missing local-mismatch model (§2) cannot be substituted for by a corner
  sweep.

Evidence record: `sim/cdac-bit-settling/records/20260731-231537-1ee5578.md`
(clean-tree, full 117-point matrix, append-only — this memo does not
duplicate its per-corner table).

This is a **much more comfortable margin than a naive whole-array estimate
would suggest**: reusing `spec/prior-art-survey.md` §1.4's own simplified
convention (`τ = R_on · C_arr`, treating the *entire* per-side array,
8.827 pF, as the settling load) with the worst measured switch `R_on`
(570 Ω, `sim/device-switch-ron/`) gives `τ ≈ 5.03 ns` and a required
`t ≥ 7.62τ ≈ 38.3 ns` — uncomfortably close to the 31.25 ns 2 MS/s stretch
budget. The **topology-correct** charge-divider load for the actual worst
trial is `Ceq = 256·256·C_u/512 = 128·C_u ≈ 2.207 pF`, four times smaller,
which is why the simulated result clears both budgets by such a wide
margin. **Lesson for #12: do not reuse the whole-array `τ` approximation for
this scheme's settling budget — it is needlessly pessimistic by ~4×.**

**DR-0002 cross-check**, using this scheme's real worst-step numbers
(weight-256 block, `ΔV = V_REF/2 = 1.65 V`), **at the resized `C_u`
(issue #177 / DR-0019, 35.6528 fF)**. These are **per-side numbers and
identical in both modes**: differential mode's mirror block steps toward
`GND`, so exactly one weight-`w` block loads the `V_REF` rail per trial in
either mode, and single-ended mode's idle reference side loads it not at
all:

```
ΔQ_max     = 256 · C_u · (V_REF/2) = 256 · 35.6528 fF · 1.65 V ≈ 15.06 pC
C_dec,min  = ΔQ_max / (0.5 LSB_se) = 15.06 pC / 1.6113 mV ≈ 9.35 nF
Z_ref,max  = τ_max / C_step_load,  τ_max = 62.5 ns / 7.62 ≈ 8.2 ns (from
             DR-0002's own 7.62-τ bit-cycle-settling convention, i.e. an
             upper bound on τ), C_step_load = 256·C_u ≈ 9.13 pF
           ≈ 8.2 ns / 9.13 pF ≈ 899 Ω
```

Both still fall **inside** DR-0002's envelope, with less headroom than the
historical sizing had (`C_dec,min ≈ 4.52 nF`, `Z_ref,max ≈ 1859 Ω`, §5.2):
`C_dec,min ≈ 9.35 nF` vs. the provisioned `≥ 40 nF` (~4.3× margin, was
~8.8×), and `Z_ref,max ≈ 899 Ω` vs. the provisioned `≤ 240 Ω` **ceiling**
(~3.7× looser, was ~7.7×) — this scheme still tolerates a *higher* reference
source impedance than DR-0002 provisioned, just by a smaller factor than
before the resize. This memo does not re-open DR-0002's provisioned values —
they remain the safe, ratified-pending numbers — it only shows the margin
DR-0002 left on the table for a future relaxation, should one become useful
(e.g. to ease the external reference buffer's design); the resize consumes
some of that margin but does not threaten DR-0002's own envelope.

### 5.4 Known limitation carried forward

`design/cdac/cdac_array.sch` represents each weighted block as a single
`cap_mim_2f0fF` instance (the PDK's stack-agnostic MiM subckt, which the
gf180mcu xschem symbol emits) carrying an `m=<weight>` multiplicity
parameter — a clean way to draw a binary-weighted array, and a faithful one,
since `m` parallel unit devices is exactly what the layout will be.

Two consequences a future testbench built *directly from this schematic*
must handle; neither affects the settling evidence recorded here, because
`sim/cdac-bit-settling/` uses a hand-written fragment that sidesteps both by
sizing one larger device per block instead of `m` parallel unit devices:

1. **`m` is not forwarded by the harness's MiM alias.** `sim/harness`'s
   `mim_cap_2f0` wrapper forwards only `c_width`, `c_length` and `dtemp`
   (`sim/harness/runner.py`), not `m`. Either extend the wrapper or emit `m`
   literal instances.
2. **The schematic names a PDK subckt directly.** `design/README.md`'s rule
   ("do not write a MIM capacitor's PDK subckt name into a fragment") exists
   because the *metal-pair* subckts (`cap_mim_2f0_m4m5_noshield`) encode a
   variant property. `cap_mim_2f0fF` carries no metal pair and so does not
   trip that specific hazard, but it is still a direct PDK name rather than
   the harness alias, so a netlist exported from this schematic is not a
   drop-in corner-runner fragment.

Flagged here for #12/#13. Not filed as a klayout-tools issue: this is an
ngspice/xschem-harness gap, not a layout-tool one.

### 5.5 The resize is bounded from *above* too — DR-0013's ratified drive contract

`C_side` is not only an internal number: it is published as `C_in` in
`README.md#target-specification`'s **Input structure** row, and it appears
directly in the **Input** row's *ratified* drive contract
([DR-0013](decision-records/DR-0013-input-pin-charge-split.md)):

```
τ_in = R_source · (C_pin + C_in) ≤ 30 ns,
       with the row's own worked ceilings ≤ 250 Ω at C_pin = 100 pF
                                          ≤ 25 Ω  at C_pin = 1 nF
```

Growing `C_u` grows `C_in = C_side = 512·C_u`, which **eats the ratified
source-impedance ceiling** — the `C_pin = 100 pF` end is the binding one,
because `C_in` is a larger fraction of the total there:

| `s` | `C_u` | `C_in = C_side` | `R_source` allowed at `C_pin = 100 pF` | vs. ratified ≤ 250 Ω |
|---|---|---|---|---|
| 2.7136 µm (as drawn) | 17.240 fF | 8.827 pF | 275.7 Ω | 10.3 % headroom |
| 3.840 µm (gain-error boundary) | 33.004 fF | 16.898 pF | 256.6 Ω | 2.6 % headroom |
| **4.000 µm (chosen)** | **35.653 fF** | **18.254 pF** | **253.7 Ω** | **1.5 % headroom** |
| 4.1975 µm | 39.063 fF | 20.000 pF | 250.0 Ω | **exactly nil** |
| 4.270 µm | 40.354 fF | 20.661 pF | 248.6 Ω | **violated** |

Inverting the contract at its ratified `250 Ω` / `100 pF` point gives a hard
ceiling on the resize:

```
C_in ≤ 30 ns / 250 Ω − 100 pF = 20.0 pF
     ⇒ C_u ≤ 39.06 fF   ⇒   s ≤ 4.1975 µm
```

**So the unit cap is now bounded on both sides, and the window is narrow:**

```
3.840 µm  ≤  s  ≤  4.1975 µm
  ^ gain-error matching (§3.6)   ^ DR-0013 drive contract (this section)
```

Two consequences worth stating plainly:

1. **The chosen `s = 4.0 µm` sits inside the window**, and is the only one of
   the candidates weighed in `spec/decision-records/
   DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md` that buys real
   gain-error margin (`3.13σ`, not a knife-edge `3.009σ`) *while* leaving the
   ratified drive contract satisfied.
2. **A "just add more margin" resize is not available.** A larger unit cap
   sized for, say, an analytic `3σ ≤ 0.45 LSB` (`s ≈ 4.27 µm`) would push the
   allowed `R_source` to 248.6 Ω — **below** the ratified 250 Ω the Input row
   publishes — i.e. it would silently invalidate a ratified spec line rather
   than merely cost area. That is a hard rejection, not a cost trade.

The `C_pin = 1 nF` end of the contract is unaffected in practice (29.46 Ω
allowed at `s = 4.0 µm` vs. the ratified ≤ 25 Ω, still 18 % of headroom), and
the row's derived T/H bandwidth (`f_−3dB ≥ 1/(2π·30 ns) = 5.3 MHz`) is a
function of the 30 ns budget alone, so it does not move with `C_in` at all.

**Not yet re-measured**: the *acquisition* time constant `R_on·C_in` roughly
doubles with `C_in` (21.3–60.0 Ω × 18.254 pF ≈ 1.10 ns worst-case, vs.
≈ 0.53 ns as drawn) — still two orders of magnitude inside the 1 MS/s track
window, but the transistor-level re-run that would turn that estimate into
evidence is part of DR-0019's tracked physical-implementation follow-up, not
this memo.

---

## 6. Summary for downstream issues

- **Chosen unit cap (current, issue #177 / DR-0019): `C_u = 35.6528 fF`**
  (2.0 fF/µm² MiM, 4.0 µm square, `σ_u = 0.5000 %`), sized to the ≤ 0.5 LSB
  **gain-error** matching target at 3σ (§3.6, the binding constraint), with a
  deliberate margin over the target's exact-boundary value (`33.00 fF` /
  `3.84 µm`). `A_C = 2.0 %·µm` derated (`literature-assumption-with-derating`,
  `sim/device-characterization-report.md` §5.1), unchanged by the resize.
  **Historical value, superseded (not yet updated in `design/`/`layout/`,
  pending a physical-implementation follow-up): `C_u = 17.24 fF`** (2.71 µm
  square), sized only to the DNL/INL stretch target — measured to clear the
  gain-error row at only 2.12σ (`sim/mc-cdac-mismatch/records/
  20260816-044942-56fbe50.md`, issue #172).
- **Dominant constraint**: matching, by ~231× over kT/C noise at the
  worst-case 125 °C corner at the historical sizing (~307× at 300 K); ~478×
  at the resized `C_u` (§5.1) — kT/C only gains headroom as `C_u` grows.
- **Array**: `2^(N-1) = 512` unit positions/side (511 weighted + 1 dummy).
  At the resized `C_u`: `C_side ≈ 18.25 pF`, `C_total ≈ 36.51 pF` (both
  sides) — **the current number for #12/#15/#16**, ~2.07× the historical
  `C_total ≈ 17.65 pF` (§5.2).
- **Switching sequence is mode-dependent** (§0, DR-0011 Decision —
  **the semantics for #11**): single-ended switches **one side per trial**
  (step `V_REF·w/1024`, = `LSB_se` at `w = 1`), differential switches
  **both** (step `V_REF·w/512`, = `LSB_diff` at `w = 1`). Same array, same
  unit cap, same per-side step; only the control sequence differs. Driving
  both sides in single-ended mode would cost a bit of resolution.
- **Matching formula for this topology**: `σ(DNL)_max ≈ 22.61·σ_u LSB`,
  `σ(INL)_max ≈ 11.31·σ_u LSB` — **the formula for #14**, not the
  plain-binary `31.98/16.00·σ_u`. **Gain error, mismatch is a separate,
  tighter-coefficient formula** (§3.6): `σ(gain error) = 32·σ_u LSB`, the
  binding constraint on `σ_u` (§4), not DNL.
- **Settling**: simulated per bit, not estimated (`sim/cdac-bit-settling/`,
  117/117 PVT points PASS); every trial clears both the 1 MS/s target and the
  2 MS/s stretch bit-cycle budget by four orders of magnitude at every PVT
  corner, contradicting a naive whole-array estimate that would have
  suggested a tight 2 MS/s margin (§5.3) — **use the simulated number, not
  the whole-array approximation, in #12**. The worst bit is *measured* to be
  the sub-array MSB (`w = 256`), matching the `Ceq(w)` derivation. **This
  simulation is at the historical `C_u`, not yet re-taken at the resized
  value** — tracked as DR-0019 follow-up work; analytically, a ~2.07× `Ceq`
  increase leaves ample margin against the four-orders-of-magnitude buffer
  measured at the historical sizing.
- **DR-0002 cross-check, at the resized `C_u`**: this scheme's real per-step
  reference-drive need (`C_dec,min ≈ 9.35 nF`, `Z_ref,max ≈ 899 Ω`) still
  sits inside DR-0002's provisioned `≥ 40 nF` / `≤ 240 Ω` envelope, with less
  headroom than the historical sizing left (`C_dec,min ≈ 4.52 nF`,
  `Z_ref,max ≈ 1859 Ω`); DR-0002's numbers stand unchanged, margin shown, not
  consumed.
- **`C_u` is now bounded on both sides, and the window is narrow** (§5.5):
  `3.840 µm ≤ s ≤ 4.1975 µm`, i.e. `33.00 fF ≤ C_u ≤ 39.06 fF`. The floor is
  §3.6's gain-error matching requirement; the **ceiling is DR-0013's ratified
  input drive contract**, which `C_in = C_side = 512·C_u` enters directly —
  at the chosen `s = 4.0 µm` the contract still holds (253.7 Ω allowed vs.
  the published `≤ 250 Ω` at `C_pin = 100 pF`) with only 1.5 % of headroom
  left. **Any future proposal to grow `C_u` further must re-open DR-0013
  first** — this is now the binding constraint, ahead of area.
- **Gain error, mismatch verification (issue #177)**: `sim/mc-cdac-mismatch/
  yield-evidence-177/` — `klt yield` at the resized `σ_u = 0.5000 %`
  (N = 20000): `status: pass`, `sigma_to_spec = 3.13`, empirical yield
  0.998100 [0.997393, 0.998655] against the ratified 0.9973 target; DNL/INL
  re-confirmed to still clear their own targets with wide margin at this
  `σ_u` (3σ DNL 0.340 LSB, 3σ INL 0.170 LSB, both well inside the 0.5/1.0 LSB
  bounds) — see `sim/mc-cdac-mismatch/records/
  20260816-125421-737d16e.md` and
  `spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`.
