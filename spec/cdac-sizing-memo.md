# CDAC sizing memo — unit cap from kT/C + matching budget

**Status**: design memo, feeds the pending ratified spec (#1). Not a decision
record (see `spec/decision-records/README.md` — this is derivation/analysis,
cited *from* decision records, not itself one).
**Issue**: #8. **Consumes**: DR-0006 (switching-scheme choice),
`sim/device-characterization-report.md` §1–§5.1 (measured/derated device
data), DR-0002 (reference-drive envelope).
**Feeds**: #9 (comparator CM budget — see DR-0006), #12 (settling budget,
§5), #14 (Monte Carlo mismatch model, §3), #15/#16 (array size, §5).

---

## 0. Scope and topology recap

DR-0006 fixes the switching scheme this memo sizes against: **MCS /
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

Both input modes use the same array:

- **Single-ended (pseudo-differential)**: one side samples `V_in` (0–3.3 V),
  the other is pinned to `V_cm`. Effective full-scale at the comparator is
  `V_REF` (3.3 V); `LSB_se = V_REF/1024 = 3.2227 mV`.
- **Differential**: both sides driven `±V_REF` about `V_cm`. Effective
  full-scale is `2·V_REF` (6.6 V); `LSB_diff = 2·V_REF/1024 = 6.4453 mV`.

(DR-0002's full-scale mapping, restated here because §1/§4 need the exact
LSB in each mode.)

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

### 1.4 Minimum `C_side` from kT/C, all four cases

Inverting §1.1: `C_side,min = 2·kT / budget²`, `kT = 4.14×10⁻²¹ J` (300 K):

| Mode | Target | Budget | `C_side,min` | `C_u,min` (÷512) |
|---|---|---|---|---|
| Single-ended | ENOB > 9.0 | 0.930 mV | **9.57 fF** | 0.019 fF |
| Single-ended | ENOB > 9.5 | 0.537 mV | **28.71 fF** | 0.056 fF |
| Differential | ENOB > 9.0 | 1.860 mV | **2.40 fF** | 0.0047 fF |
| Differential | ENOB > 9.5 | 1.074 mV | **7.19 fF** | 0.014 fF |

**The worst (largest) `C_side,min` across both modes and both targets is
28.71 fF** (single-ended, ENOB > 9.5 stretch) — tens of femtofarads, three
orders of magnitude below anything matching will require (§4). This
reproduces `spec/prior-art-survey.md` §1.2's headline finding
("kT/C is not the binding constraint at 3.3 V") *for this topology
specifically*, rather than carrying it over unchecked.

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
topology, and must be re-derived for the array DR-0006 actually chose.

### 3.1 The free MSB carries zero mismatch

Bit 1 is decided directly from the sampled charge at the end of acquisition
— **no capacitor switches** to make this decision. The two sides' *total*
array capacitances (`C_side,P` vs. `C_side,N`) could in principle differ
(a side-to-side mismatch), but the sampled *voltage* on each side's top
plate is set by the input source through a low-impedance switch, not by a
charge-division ratio — so a side-to-side capacitance mismatch does not
perturb this decision at all (it would only matter if this were a
charge-redistribution decision, which it is not). **Bit 1 is exactly the
kind of decision this scheme was chosen for (DR-0006): it carries no
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
`σ_u`** — a direct, quantified consequence of DR-0006's free-MSB property,
not a restatement of the survey's placeholder arithmetic.

This propagation is **mode-independent**: it is a property of the array
alone, in units of *that array's* LSB, which is the same physical quantity
regardless of whether the input is driven single-ended or differentially.
Only which LSB the result is compared against downstream (§0) differs, and
single-ended's tighter LSB is the conservative case to design to.

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
2× INL's (both derive from the same sub-array, and the DNL/INL ratio is
architecture-invariant at exactly 2 for a binary array), so **DNL is the
binding linearity constraint** at every target level; a design that meets
the DNL bound meets the INL bound with room to spare (`σ(INL)` at the
DNL-derived `σ_u` is exactly half the DNL bound).

---

## 4. Required unit-cap area and capacitance

Combining §3.4's `σ_u` requirement with the Pelgrom law
(`A_unit = (A_C/σ_u)²`, `A_C = 2.0 %·µm`, §2) and the *measured* density law
from `sim/device-characterization-report.md` §1.2
(`C(W,L) = 1.99·W·L + 0.4766·(W+L)` fF, `W,L` in µm, square unit `W=L=s` so
`C(s) = 1.99·s² + 0.9532·s`):

| Target | `σ_u` | `A_unit` | Unit side `s` | `C_u` (measured density law) |
|---|---|---|---|---|
| < 1 LSB (baseline) | 1.474 % | 1.839 µm² | 1.356 µm | **4.95 fF** |
| < 0.5 LSB (stretch) | 0.737 % | 7.36 µm² | 2.713 µm | **17.24 fF** |

**Chosen unit cap: `C_u = 17.24 fF` (2.0 fF/µm² MiM flavor,
2.71 µm × 2.71 µm drawn)** — sized to the **stretch** (< 0.5 LSB, 3σ)
target. This is a deliberate choice, not a requirement: meeting only the
baseline (< 1 LSB) target would need `C_u ≈ 4.95 fF`, roughly 3.5× smaller.
Sizing to the stretch target instead costs a negligible amount of array
area (§5) and buys margin toward the ENOB > 9.5 / 12-bit-stretch
aspirations noted in the original issue, so there is no reason not to take
it given §5's area/settling numbers stay comfortably inside budget either
way.

Note on `sim/device-characterization-report.md` §1.5: unit caps at or below
5 µm on a side (both rows above qualify) carry a **−81 ppm/V** datasheet
voltage coefficient — 9× larger and opposite sign to the 10×10 µm device,
and **not present in the simulated path** (the PDK's ngspice deck has the
bias-dependent `c_cap` line commented out, §1.5). This is a real linearity
term future work must apply by hand; no simulated CDAC result in this repo
contains it.

---

## 5. Dominant constraint, total array capacitance, and settling

### 5.1 Dominant constraint: matching, not noise — by three orders of magnitude

| Constraint | Minimum `C_u` (worst case across modes/targets) |
|---|---|
| kT/C noise (§1.4) | 0.056 fF (single-ended, ENOB > 9.5) |
| Matching (§4) | 17.24 fF (chosen, stretch target) |

**Matching dominates by a factor of ~307×.** This is the memo's central
finding: the unit cap is set entirely by the matching/linearity budget: if
`sim/device-characterization-report.md` §5.1's `A_C` assumption later comes
in worse than the 2.0 %·µm derated planning value used here, **all** of the
resulting margin should be spent re-checking §3–§4, not §1 — kT/C has ~300×
of headroom to give before it would become relevant even in the worst case
this memo shows.

### 5.2 Total array capacitance — flagged for #12

```
C_side  = 512 · C_u = 512 · 17.24 fF = 8.827 pF   (per side)
C_total = 2 · C_side              = 17.65 pF      (both sides, differential)
```

**`C_total ≈ 17.7 pF` is the number #12's settling/timing budget and #15/#16's
array layout must plan against.** For contrast: DR-0002 derived its
reference-drive envelope (`Z_ref ≤ 240 Ω`, `C_dec ≥ 40 nF`) conservatively
against a **34 pF "whole planning array"** figure (the plain-binary
`2^N`-unit example in `sim/device-characterization-report.md` §5.1, at the
same `C_u`-derivation policy) — almost exactly double this scheme's real
`C_total`, because MCS's `2^(N-1)`-per-side array needs half the total unit
count of a plain-binary `2^N` single-sided array for the same `C_u`. §5.3
shows this scheme's real per-step burden is smaller still.

### 5.3 Settling: per-bit simulation, and DR-0002 cross-check

**Simulated** (not merely estimated): `sim/cdac-bit-settling/` sizes each
trial's switching cap and its fixed sub-array load directly from this memo's
`C_u` (§4) via the measured density law, and drives them through real
gf180mcu T-gate switches (same sizing as `sim/device-switch-ron/`).

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

See `sim/cdac-bit-settling/records/` for the append-only evidence record
(this memo does not duplicate the 117-row per-corner table).

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
(weight-256 block, `ΔV = V_REF/2 = 1.65 V`):

```
ΔQ_max     = 256 · C_u · (V_REF/2) = 256 · 17.24 fF · 1.65 V ≈ 7.28 pC
C_dec,min  = ΔQ_max / (0.5 LSB_se) = 7.28 pC / 1.6113 mV ≈ 4.52 nF
Z_ref,max  = τ_max / C_step_load,  τ_max = 62.5 ns / 7.62 ≈ 8.2 ns (DR-0002's
             own bit-cycle-settling floor), C_step_load = 256·C_u ≈ 4.41 pF
           ≈ 8.2 ns / 4.41 pF ≈ 1859 Ω
```

Both fall **inside** DR-0002's envelope with large margin:
`C_dec,min ≈ 4.52 nF` vs. the provisioned `≥ 40 nF` (~8.8× margin), and
`Z_ref,max ≈ 1859 Ω` vs. the provisioned `≤ 240 Ω` floor (~7.7× looser, i.e.
DR-0002's floor may be relaxed by up to ~7.7× once this scheme's real
per-step behavior is the input, exactly as DR-0002 anticipated: "#8's actual
per-step switched capacitance ... may relax `Z_ref`/`C_dec`, but never
tighten them"). This memo does not re-open DR-0002's provisioned values —
they remain the safe, ratified-pending numbers — it only shows the margin
DR-0002 left on the table for a future relaxation, should one become
useful (e.g. to ease the external reference buffer's design).

### 5.4 Known limitation carried forward

`design/cdac/cdac_array.sch` represents each weighted block as a single
`mim_cap_2f0fF` instance with an `m=<weight>` multiplicity parameter
(§0/DR-0006 Consequences), which is a clean way to draw a binary-weighted
array but is **not yet proven compatible with `sim/harness`'s
`mim_cap_2f0` wrapper alias**, which currently forwards only `c_width`,
`c_length` and `dtemp` (`sim/harness/runner.py`) — not `m`. A future
testbench built directly from this schematic (rather than the hand-built
lumped-capacitance fragment `sim/cdac-bit-settling/` uses, which sidesteps
this by sizing one bigger device instead of `m` parallel unit devices) must
either extend the harness wrapper to forward `m`, or replicate `m` literal
instances. Flagged here for #12/#13, not filed as a klayout-tools issue
(this is an ngspice/xschem-harness gap, not a layout-tool one).

---

## 6. Summary for downstream issues

- **Chosen unit cap**: `C_u = 17.24 fF` (2.0 fF/µm² MiM, 2.71 µm square),
  sized to the < 0.5 LSB (stretch) matching target at 3σ, `A_C = 2.0 %·µm`
  derated (`literature-assumption-with-derating`,
  `sim/device-characterization-report.md` §5.1).
- **Dominant constraint**: matching, by ~300× over kT/C noise (§5.1).
- **Array**: `2^(N-1) = 512` unit positions/side (511 weighted + 1 dummy),
  `C_side ≈ 8.83 pF`, `C_total ≈ 17.65 pF` (both sides) — **the number for
  #12/#15/#16**.
- **Matching formula for this topology**: `σ(DNL)_max ≈ 22.61·σ_u LSB`,
  `σ(INL)_max ≈ 11.31·σ_u LSB` — **the formula for #14**, not the
  plain-binary `31.98/16.00·σ_u`.
- **Settling**: simulated per bit, not estimated (`sim/cdac-bit-settling/`,
  117/117 PVT points PASS); every trial clears both the 1 MS/s target and the
  2 MS/s stretch bit-cycle budget by four orders of magnitude at every PVT
  corner, contradicting a naive whole-array estimate that would have
  suggested a tight 2 MS/s margin (§5.3) — **use the simulated number, not
  the whole-array approximation, in #12**. The worst bit is *measured* to be
  the sub-array MSB (`w = 256`), matching the `Ceq(w)` derivation.
- **DR-0002 cross-check**: this scheme's real per-step reference-drive need
  (`C_dec,min ≈ 4.52 nF`, `Z_ref,max ≈ 1859 Ω`) sits well inside DR-0002's
  provisioned `≥ 40 nF` / `≤ 240 Ω` envelope; DR-0002's numbers stand
  unchanged, with headroom shown, not consumed.
