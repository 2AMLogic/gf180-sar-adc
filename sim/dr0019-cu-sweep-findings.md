# What DR-0019's `C_u` resize cost the dynamic rows, and why

Issue #211. `spec/testbench-suite-memo.md` §11.2 blames the SFDR miss on the
acquisition's own signal-dependent nonlinearity, and says in the same breath
that this is *"a nine-point correlation, not an isolation … no experiment here
drives the acquisition bow independently and watches SFDR follow."*
`sim/dr0019-cu-sweep/` is that experiment. This page is its answer.

**Nothing here changes a ratified number, and nothing here re-decides
DR-0019.** `CLAUDE.md` forbids relaxing the ratified spec to make results
pass, and the C_u value is a ratified decision
([DR-0019](../spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md));
the design was not touched by this work. This is evidence, plus a
recommendation for a *separate* decision that this document deliberately does
not make.

**No sweep point is a measurement of this block.** Every record under
`sim/dr0019-cu-sweep/records/` except the `C_u = 35.6528 fF`, ratified-switch
one describes a converter that does not exist. `README.md`'s ENOB and SFDR
rows are claimed by `sim/adc-enob-fft/` at the ratified `C_u`, and a reader
must not cite a sweep point as this design's performance.

## 0. The result in four lines

1. **The regression tracks `C_u` continuously and keeps going past the
   ratified value.** Worst-corner SFDR falls 61.33 → 54.69 dB and worst-corner
   composed ENOB falls 9.163 → 8.367 bits as `C_u` goes 17.24 → 42.0 fF. It is
   a trend, not a step: the 42.0 fF probe past the ratified point is worse
   still, on both rows.
2. **The slope matches the acquisition-RC prediction quantitatively.** A
   distortion set by the signal-dependent acquisition lag
   `R_on(V_in)·C_arr·dV_in/dt` must cost **20 dB per decade of `C_u`**. Fitted
   against `log10(C_u)`, the worst corner gives **−19.00 dB/decade**
   (Pearson `r = −0.925`); the nine-corner mean is −17.69.
3. **The orthogonal control settles causation, and it is not the two
   confounds.** Holding `C_u` at the ratified 35.6528 fF and widening *only*
   the CDAC cell's fourth (input/acquisition) T-gate by 2.068× — leaving
   `V_REF` charge and the `C_arr/(C_arr + C_par)` divider at their resized
   values — recovers worst-corner SFDR 56.41 → **60.80 dB** (89 % of the loss)
   and worst-corner ENOB 8.507 → **9.170 bits** (101 % of the loss, back above
   the pre-resize 9.163). The mechanism is the acquisition time constant.
4. **A smaller admissible resize would not have bought the margin back.**
   DR-0019's own rejected exact-boundary sizing, `C_u = 33.00 fF`, measures
   **56.07 dB** worst-corner SFDR — no better than the ratified 35.6528 fF's
   56.41 dB. The entire admissible window (§4) sits at ≈ 56 dB. The lever that
   works is the switch, not a slightly smaller capacitor.

## 1. What was swept, and what makes "only `C_u` moved" checkable

Every point's netlist comes out of `design/adc-top/gen_adc_top.py` — the same
generator that emits the ratified deck — with the single module constant
`C_UNIT_FF` rebound (`sim/dr0019-cu-sweep/gen_cu_variant.py`). Nothing is
templated or patched on the `C_u` axis, so the nine per-block MiM square sides
and every derived comment are recomputed by the ratified code path.

That path at the ratified `C_u = 35.6528 fF` reproduces the committed
`sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice` **byte-for-byte**
(`gen_cu_variant.py --verify-baseline`, asserted in CI by
`sim/tests/test_cu_sweep_variant.py`). The measurement machinery —
`analyses` / `measure` / `checks`, the FFT metadata, the supply axis — is
copied byte-for-byte from the `sim/adc-enob-fft/` manifest and asserted equal
by the same test file. The grid is the same nine points
(3 process × 3 supply, all 125 °C) those records use.

So the comparisons below are point-for-point against the pre- and post-resize
captures issue #211 reports, and "everything else was held fixed" is a checked
statement rather than an assurance.

**The capture did not change across the sweep**, which is what lets the
spectra be compared at all: at the worst corner every point lands at
−0.582 … −0.589 dBFS with `code_max` = 990 and `code_min` = 33, and every
point's harness verdict is PASS on the coverage witnesses and the `V_REF`
process-spread floor.

### The fidelity cross-check, and the scatter it bounds

The ratified sweep point and
[`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](adc-enob-fft/records/20260817-080939-afb1b3a.md)
are the same netlist run twice by two different campaigns — the snapshot this
sweep froze
(`sim/dr0019-cu-sweep/netlist-snapshots/20260817-144622-70a6345.spice`) is
byte-identical to the committed `tb_adc_enob_fft.spice`. Eight of the nine
corners agree to **0.0000 dB** of SFDR. The ninth, `ff_125c_2.97v`, differs by
**1.06 dB**, and the cause is legible in the raw logs: exactly one of the 64
samples lands on a decision boundary and comes out 283 instead of 282.

That is the useful number to carry into every comparison below: **one 1-LSB
code flip is worth about 1 dB of SFDR on a 64-sample FFT.** It is why the two
sub-doubling steps in §2 are reported as unresolvable rather than as
structure, and why the conclusions rest on the axis and on the control point
rather than on any single pair of adjacent points.

### Reproducing it

```bash
./sim/dr0019-cu-sweep/run_sweep.sh                    # all eight points
python3 sim/dr0019-cu-sweep/analyze_sweep.py --markdown
```

`analyze_sweep.py` reads the records' own raw per-corner logs and reuses
`sim/adc-enob-fft/testbench/analyze_fft.py`'s transform, so every figure below
is produced by exactly the code that produced the ratified campaign's figures.
Nothing on this page is hand-entered.

**One methodological deviation, stated because it moves numbers.** §4.3 of the
testbench memo composes ENOB from the measured distortion plus two terms the
transient cannot contain: the comparator's input-referred noise and the
sampling `kT/C`. The second is a function of `C_side = 512·C_u` — the very
quantity being swept — so the published `0.0488 LSB` is re-derived at each
point's own `C_side` rather than carried across (0.0488 → 0.0481 LSB over this
axis; as an arithmetic check the re-derivation reproduces `0.0488 LSB` exactly
at `C_u = 17.24 fF`). Carrying the published constant would have credited the
small-`C_u` points with noise they do not have.

## 2. The `C_u` axis

Worst corner is `ss_125c_2.97v` on both rows at every point but one (SFDR at
`C_u = 30 fF`, where `ss_125c_3.30v` is 0.25 dB worse — inside the
point-to-point scatter of a 64-sample FFT).

| `C_u` (fF) | `C_side` (pF) | worst SFDR (dB) | worst composed ENOB (bits) | worst-corner THD (dBc) | max `V_REF` droop (mV) | record |
|---|---|---|---|---|---|---|
| 17.24 (pre-resize) | 8.827 | **61.33** | **9.163** | −58.53 | 2.055 | `20260817-131658-9b8498f` |
| 22.0 | 11.264 | 61.46 | 9.259 | −58.62 | 2.562 | `20260817-133432-77fd05c` |
| 26.0 | 13.312 | 59.75 | 8.960 | −56.93 | 2.967 | `20260817-135204-7aea936` |
| 30.0 | 15.360 | 59.19 | 8.780 | −55.59 | 3.435 | `20260817-140653-692daba` |
| 33.0 (DR-0019's rejected floor) | 16.896 | 56.07 | 8.591 | −54.12 | 3.753 | `20260817-142130-1292176` |
| **35.6528 (ratified)** | 18.254 | **56.41** | **8.507** | −53.81 | 4.032 | `20260817-144622-70a6345` |
| 42.0 (probe, not admissible) | 21.504 | 54.69 | 8.367 | −52.46 | 4.732 | `20260817-150327-ccee900` |

The two endpoints of DR-0019 reproduce the published campaign at the corner
that matters: 61.33 dB / 9.163 bits at 17.24 fF is
`spec/testbench-suite-memo.md` §11.1's pre-resize row to the digit, and
56.41 dB / 8.507 bits at 35.6528 fF is
[`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](adc-enob-fft/records/20260817-080939-afb1b3a.md)'s
post-resize row to the digit. The sweep is anchored at both ends to campaigns
it did not run.

Two honest wrinkles, neither of which changes the conclusion:

- **The first step is flat or very slightly up** (17.24 → 22.0 fF: +0.13 dB
  SFDR, +0.096 bits). Over a 1.28× capacitance step the RC prediction is only
  −2.12 dB, and §1's cross-check puts a single 1-LSB code flip at ≈ 1 dB.
- **33.0 → 35.6528 fF is +0.34 dB rather than −0.67 dB.** Same reason: a 1.08×
  step predicts −0.67 dB, at the resolution floor. Neither adjacent pair is
  resolvable on its own; the *axis* is — 2.44× in `C_u` end to end, a 6.6 dB
  fall against a 7.7 dB prediction.

### The −20 dB/decade test

If the limiting distortion is the acquisition lag `R_on(V_in)·C_arr·dV_in/dt`,
its amplitude is proportional to `C_arr ∝ C_u` while the signal is not, so
SFDR must fall by 20 dB per decade of `C_u` (6.02 dB per doubling). The
orthogonal control point is excluded from the fit (it moves `R_on`, not
`C_u`).

| corner-id | SFDR slope (dB/decade) | Pearson `r` | ENOB slope (bits/decade) |
|---|---|---|---|
| `ff_125c_2.97v` | −17.22 | −0.852 | −1.178 |
| `ff_125c_3.30v` | −7.68 | −0.566 | −0.570 |
| `ff_125c_3.63v` | −18.05 | −0.786 | −1.187 |
| **`ss_125c_2.97v`** | **−19.00** | **−0.925** | −2.421 |
| `ss_125c_3.30v` | −20.15 | −0.860 | −2.257 |
| `ss_125c_3.63v` | −15.83 | −0.969 | −1.204 |
| `tt_125c_2.97v` | −18.44 | −0.799 | −1.722 |
| `tt_125c_3.30v` | −25.43 | −0.885 | −1.874 |
| `tt_125c_3.63v` | −17.40 | −0.953 | −1.338 |

Mean −17.69 dB/decade, range −25.43 … −7.68, against a predicted −20.00. The
prediction is met most closely exactly where it should be — at the slow, low
supply corners, where `R_on` is largest and the acquisition term dominates
whatever else is in the spectrum — and worst at `ff_125c_3.30v`, the fastest
`R_on` on the grid, where the term is smallest and the fit is correspondingly
loose (`r = −0.566`). That pattern is itself evidence for the mechanism: a
confound that scaled with `C_u` for some other reason would have no reason to
fit best where `R_on` is largest.

## 3. The orthogonal control: which of the three consequences is doing it

Growing `C_u` moves three things at once, and a slope alone cannot separate
them:

1. the acquisition time constant `R_on(V_in)·C_arr` — the §11.2 hypothesis;
2. the charge the array draws from the DR-0002 reference network per
   conversion (`V_REF` droop);
3. the `C_arr/(C_arr + C_par)` divider the residue is scaled by.

The control point holds `C_u` at the ratified 35.6528 fF and widens **only**
the CDAC cell's fourth leg — the `Xsi` T-gate DR-0014 made the input's path
into the array — by 2.068×, from `10u/20u` to `20.68u/41.36u`. The release /
`V_REF` / GND legs keep the ratified geometry, so bit-trial drive strength is
untouched. `sim/tests/test_cu_sweep_variant.py` asserts that this changes
**exactly one line** of the emitted deck. That returns (1) to roughly its
pre-resize value and leaves (2) and (3) at their resized values.

| corner-id | pre-resize `C_u` = 17.24 | ratified `C_u` = 35.6528 | control: ratified `C_u`, acq leg ×2.068 | Δ from resize | Δ from control | recovered |
|---|---|---|---|---|---|---|
| `ff_125c_2.97v` | 70.45 | 65.11 | 70.23 | −5.35 | +5.12 | 96 % |
| `ff_125c_3.30v` | 67.32 | 67.75 | 69.61 | +0.42 | +1.86 | — (no loss) |
| `ff_125c_3.63v` | 69.98 | 65.93 | 71.66 | −4.05 | +5.74 | 142 % |
| **`ss_125c_2.97v`** | **61.33** | **56.41** | **60.80** | **−4.92** | **+4.39** | **89 %** |
| `ss_125c_3.30v` | 63.43 | 59.73 | 63.54 | −3.69 | +3.81 | 103 % |
| `ss_125c_3.63v` | 65.99 | 60.24 | 63.69 | −5.75 | +3.45 | 60 % |
| `tt_125c_2.97v` | 65.20 | 61.49 | 63.61 | −3.71 | +2.12 | 57 % |
| `tt_125c_3.30v` | 69.14 | 62.94 | 65.53 | −6.19 | +2.59 | 42 % |
| `tt_125c_3.63v` | 68.96 | 63.81 | 63.92 | −5.16 | +0.11 | 2 % |

*(SFDR in dB. Composed ENOB behaves the same way: at the worst corner
9.163 → 8.507 → 9.170 bits, and the control clears > 9.0 bits at **all nine**
grid points.)*

**Confounds (2) and (3) are ruled out, not argued away.** The control's
`V_REF` droop is 4.076 mV against the ratified point's 4.032 mV — the same
array, the same charge per conversion, within 1 % — and its `C_arr/(C_arr +
C_par)` divider is identical by construction. SFDR nonetheless recovers
4.39 dB and worst-corner THD recovers −53.81 → **−58.57 dBc**, back to the
pre-resize −58.53 dBc. A mechanism that did not move cannot explain a
distortion that did.

### Reconciling with §11.9.7: the proxy failed, the mechanism did not

`spec/testbench-suite-memo.md` §11.9.7 — landed while this sweep was running —
re-took `samp_inl_worst_lsb`, the endpoint-fitted bow of the *held sample*
measured on `sim/dr0014-sampling/`, and found it **improving** at eight of nine
corners across the resize while SFDR degraded. It concludes, correctly on its
own evidence, that issue #211's stated hypothesis "is not supported by the bow
this deck measures", and asks for exactly the sweep on this page.

Both results stand, and they are not in tension:

- **`samp_inl_worst_lsb` is a static endpoint bow.** It fits the *held* value
  against a straight line over the input range. A first-order acquisition lag
  with the input parked is a *settling* error that decays away, and
  `sim/dr0014-sampling/` measures exactly that: `set_err_4leg_lsb` is
  0.0000 LSB at every 125 °C point before the resize and −0.0003 … 0.0000 LSB
  after it (`20260817-134517-cde979d`) — i.e. the static residue this
  mechanism leaves behind is at the deck's resolution floor at both `C_u`
  values, which is precisely why a static metric cannot see the term.
- **The term this sweep moves is `R_on(V_in)·C_arr·dV_in/dt`** — proportional
  to the input's *slew*, which is zero in the deck that measures the bow and
  maximal at the near-Nyquist input the FFT deck drives. Nothing about the
  static bow improving predicts what that term does.

So §11.9.7 refutes the **proxy** §11.2 reasoned through, and this page measures
the **mechanism** directly, by moving each factor of `R_on·C_arr` in turn and
watching SFDR and THD follow. §11.2's nine-point ordering of SFDR against
`samp_inl_worst_lsb` should now be read as a pre-resize coincidence between two
quantities that happen to co-vary at fixed `C_u` — both are largest where
`R_on` is largest — rather than as a causal chain.

**Read the per-corner recovery as a gradient, not as noise.** Recovery is
near-total at the slow and fast low-supply corners where `R_on` is largest,
and small at `tt_125c_3.63v` (2 %) where it is smallest and something else
sets the worst spur. That is the same ordering as the slope table, and the
same ordering §11.2's `samp_inl_worst_lsb` column already had.

**The `V_REF` droop row deserves one more sentence, because it is the thing a
reader will expect to be the culprit.** It does grow monotonically with `C_u`
(2.055 → 4.732 mV — 2.30× more droop for 2.44× more capacitance, near enough
to proportional, exactly as charge conservation says it must), and it is
therefore *correlated* with the SFDR loss all the way along the `C_u` axis. It
is not *causal*: the control point breaks the correlation, and the distortion
follows `R_on·C_arr`. Droop also never approaches its 50 mV check limit — the
worst point on the whole sweep uses 9.5 % of it.

## 4. What this says about the sizing, and what it does not

DR-0019's admissible window for `C_u` is bounded below by the gain-error
matching constraint (`33.00 fF`, its own rejected exact-boundary sizing) and
above by DR-0013's ratified input-drive contract (`39.06 fF`). Issue #211 asks
whether a smaller resize inside that window would have traded away less
dynamic margin. **Measured: no.**

| candidate | worst SFDR | vs. ≥ 62 dB | worst ENOB | vs. > 9.0 |
|---|---|---|---|---|
| `C_u = 33.00 fF` (matching floor) | 56.07 dB | −5.93 | 8.591 | −0.409 |
| `C_u = 35.6528 fF` (ratified) | 56.41 dB | −5.59 | 8.507 | −0.493 |

The two are indistinguishable at this deck's resolution. Moving to the bottom
of the admissible window would give up DR-0019's deliberate gain-error margin
(`3.13σ` → the `σ_u = 0.5208 %` exact boundary) and buy back **nothing**
measurable on either dynamic row. The dynamic cost is not a consequence of
DR-0019 having chosen 35.6528 fF over 33.00 fF; it is a consequence of the
matching constraint requiring ≈ 2× the array at all, which the acquisition
switch was never resized against.

### Recommendation — for a separate issue and its own decision record

**The acquisition leg is the lever, and it is not a spec quantity.** The
control point is not a proposed design and this document does not propose
one; what it establishes is that the cheapest place to look is the CDAC
cell's fourth-leg T-gate width, which no ratified row constrains, rather than
the ratified `C_u` that three matching rows do.

A follow-up would have to measure what this sweep deliberately did **not**:

- charge injection and clock feedthrough from a 2× wider sampling device —
  DR-0012/DR-0013's `Gain error, systematic` row is scoped to exactly that,
  and `sim/dr0014-sampling/` is the deck that measures it;
- the top-plate `C_par` the wider device adds (`sim/top-plate-cpar/`), which
  feeds back into confound (3);
- comparator kickback and the DR-0014 sampling-instant definition;
- clock-driver load and power (`sim/adc-power/`);
- array area and routing in `layout/adc-top/`.

None of those is answered here, and the recovery measured above must not be
read as an achievable design margin until they are. Widening a sampling switch
to fix a sampling-bandwidth problem is a textbook trade against charge
injection, and this experiment measured only the half of it that helps.

**Follow-up status (issue #238).** The follow-up this section asks for is
filed as #238, decomposed into the five measurements above plus a decision
record and a re-run (`sim/dr0019-cu-sweep-findings.md` was itself cited as
the reason no earlier issue tracked the ENOB/SFDR governing FAILs). The first
of the five — charge injection and clock feedthrough from the candidate
2.068× acquisition-leg width, `sim/dr0014-sampling/` — is measured:
[`sim/dr0014-sampling/records/20260825-015032-446a3c4.md`](dr0014-sampling/records/20260825-015032-446a3c4.md),
full ratified 27-point PVT grid, clean-tree PASS, schematic (the candidate
geometry has not been laid out — item 5 is what would measure that). Headline:
every charge-injection/settling figure this deck reports moves by
**noise-floor amounts** at the candidate width (`samp_inl_worst_lsb`
0.30895 → 0.30915 LSB against the ± 1 LSB INL bound, `bp_inj_mis_lsb`
unchanged at the deck's own numerical floor, `set_err_4leg_lsb` and
`hold_l4_lsb` unchanged to 4 significant figures) while `ron_path_worst_ohm`
**halves** as R_on ∝ 1/width predicts (60.02 → 29.03 Ω, both far inside the
1–2000 Ω check). Read cautiously: this deck's DR-0014 two-phase top-plate
sample is architected to reject switch injection as a common-mode term
regardless of switch width (§0 above, and the deck's own header), which is a
plausible reason the candidate width costs so little here — but it is one
deck's evidence, not a verdict on the other four deferred quantities, and the
recovery this page measured must still not be read as achievable margin until
they are measured too.

**Item 2 — the top-plate `C_par` the wider device adds (`sim/top-plate-cpar/`,
issue #245) — is measured, and the finding is invariance: the candidate width
does not move the `C_arr/(C_arr + C_par)` divider at all.** Full run, this
deck's own 63-point `cdac` corner set (`tt, cap_ff, cap_ss, mim_ff, mim_ss,
moscap_ff, moscap_ss` × 3 temperatures × 3 supplies — the capacitor-corner
grid its `testbench/tb.json` declares, not the 27-point ADC-level grid item 1
uses, because the quantity here is a MiM/parasitic capacitance the `mos` grid
does not skew), clean-tree PASS at all 63 points, schematic:
[`sim/top-plate-cpar/records/20260825-034455-4cf1ca4.md`](top-plate-cpar/records/20260825-034455-4cf1ca4.md).
Against the ratified schematic baseline
[`20260817-133358-ee708e5`](top-plate-cpar/records/20260817-133358-ee708e5.md)
(same manifest, same grid, `acq_switch_scale = 1.0`): `c_arr_v1p65_ff` and
`c_sw_v1p65_ff` are **bit-identical on all 63 rows**, every `cpar_v*_ff`
column moves by at most **± 0.0033 fF (≤ 0.0056 %)** on values of 57–160 fF,
and `gain_err_v1p65_pct` — the fraction of a DAC step the divider swallows —
by at most **+ 2 × 10⁻⁵ percentage points** on 0.34–0.75 %. The residual
flips sign from corner to corner, which is what a solver residue looks like
and what a systematic width term does not.

*Why it is structural, read out of the netlist rather than asserted.* The
acquisition leg is not on the top plate: `adc_cdac_cell` binds it
`Xsi vin bp`, i.e. between the cell's `vin` port and the **bottom** plate. In
this deck the array's `vin` port is tied to `cpvcm` — an ideal DC source,
`vcpvcm cpvcm 0 dc {vcm}` — while `sel_in` is `cpoff` (0 V: the acquisition
leg is OFF) and every `rel_*` is `cprel` (`vdd`: the release leg `Xsr vcm bp`
is ON, holding `bp` at that same ideal `V_cm`). Both terminals of the widened
device therefore sit on nodes pinned by the same ideal source, and its
off-state junction/overlap capacitance contributes no displacement current to
the ramp source that measures the top plate. That is not a modelling
convenience: bottom plates released to `V_cm` with the acquisition leg open is
precisely the state a bit trial settles in, which is the state whose
capacitance divides the DAC step.

*The controls that make "invariant" different from "the substitution never
reached the circuit"* — the exact trap item 1 fell into with
`sim/dr0014-sampling/`'s unpatched Group D R_on replica. First, the emitted
deck differs from the ratified one on **exactly one line** (diffed against the
same generator at `--acq-switch-scale 1.0`, which reproduces the checked-in
`tb_top_plate_cpar.spice` byte-for-byte), and the record's own netlist
snapshot carries `Xsi ... wn=20.6800u wp=41.3600u` — while branch b's
top-plate `V_cm` switch (`Xs ... adc_tgate wn=10u wp=20u`, DR-0014's
`adc_tp_sw`, the device `c_sw_*` measures) correctly keeps the ratified
geometry. Second, an exaggerated scratch sweep at `tt`/27 °C/3.30 V
(`--no-write`) lands **back** on the 1× value at 4×: `cpar_v1p65_ff` =
115.693 fF at 1×, 115.690 fF at 2.068×, 115.693 fF at 4×. A real width
response would be monotonic; this is the transient solver's own last digit.
(10× is not runnable at all — `wp = 200 µm` is outside the gf180mcu FET
model's width range.) Third, one corner (`tt_27c_3.30v`) was re-simulated from
an independently assembled deck and all 33 measured columns recomputed in
Python from `testbench/tb.json`'s own `measure` expressions: every one
reproduces the recorded row to the record's 6-significant-figure precision.

*What this settles and what it does not.* It closes confound (3) of §3 above —
the divider — for the candidate width, and it is the second of the five
deferred items to come back cheap. It does **not** say the wider device adds
no capacitance anywhere: it adds it on the bottom plate and the input path,
which is DR-0013's input-drive contract's business and item 4's
(`sim/adc-power/`, clock-driver load and power), and whose injection into the
sample item 1 already measured. And this deck is schematic-only by
construction, so its `C_par` is a lower bound (#17): the topological argument
above survives extraction, but the routing a physically wider device needs is
not modelled here, and item 5's re-layout is where that shows up.

**Item 3 — comparator kickback and the DR-0014 sampling-instant definition
(`sim/comparator-kickback/`) — is measured, and the finding is structural
invariance, not a new number.** Unlike `sim/dr0014-sampling/`,
`sim/comparator-kickback/testbench/tb_kickback.spice` is **not** emitted by
`design/adc-top/gen_adc_top.py` and carries **no** acquisition-leg T-gate
device of any kind (confirmed by a full-file read): it drives the comparator
subckt from a lumped RC model of the CDAC top plate (`Cpa`/`Cpb` = 8.83 pF
through a 1 GΩ bias resistor) fed by hard-coded DC residue voltage sources
(a half-LSB residue and a +100 mV residue), so the candidate 2.068×
acquisition-leg width has no netlist parameter to vary here — consistent
with `sim/dr0019-cu-sweep/gen_cu_variant.py`'s `--deck` selector correctly
not listing a `kickback` entry.

Two coupling paths were traced (not just asserted) before accepting that:

- *Comparator kickback itself*: the charge kicked back onto the top plate
  originates entirely inside the `comparator` subckt — the StrongARM
  regeneration nodes' `C_gd` coupling through the isolation inverters and
  the preamp's own devices onto the fixed 8.83 pF top-plate model. None of
  that path touches a CDAC array switch, so there is no mechanism by which
  widening the acquisition-leg T-gate could change it. The deck's own
  header/evidence notes make this an explicit design choice, not an
  oversight: "SAMPLING-SWITCH AND BOTTOM-PLATE DYNAMICS ARE NOT MODELLED
  HERE ... combining them would confound kickback with settling" —
  `sim/cdac-bit-settling/` (issue #8) owns that coupling, not this deck.
- *The DR-0014 sampling-instant definition*: `spec/decision-records/DR-0014-
  bottom-plate-sampling.md` states the sequence explicitly — "(1) top-plate
  switch closed, all bottom plates on `V_in`; (2) **top-plate switch
  opens** — this is the sampling instant; (3) bottom-plate switches move
  from `V_in` to `V_cm`; (4) trial 1 decides" (line ~127) — and separately,
  "the sampling instant is no longer defined by the input switch" (line
  268). The instant is defined solely by the top-plate `V_cm` switch
  (`adc_tp_sw`) opening, a different device from the acquisition-leg
  (fourth-leg) T-gate #238's candidate widens; the derivation cites no
  dependency on that leg's `R_on` or width. The remaining risk this
  admits — the acquisition-leg switch's own charge injection/settling
  after the top-plate switch has already opened — is item 1's scope
  (`sim/dr0014-sampling/`), not this deck's, and item 1's own record shows
  `set_err_4leg_lsb` and `hold_l4_lsb` unchanged to the deck's numerical
  floor at the candidate width, so the residue the comparator sees at the
  strobe instant is not measurably altered by the width change either.

**Conclusion: no coupling found.** Comparator kickback and the DR-0014
sampling-instant definition are unaffected by the candidate acquisition-leg
width, for the structural reasons above, not because the effect was too
small to see. A fresh, clean-tree, full 45-point `mos`-corner-set PVT run
(this deck's own convention per its `testbench/tb.json`, not the 27-point
ADC-level grid) is recorded at
[`sim/comparator-kickback/records/20260825-044912-9fe3b68.md`](comparator-kickback/records/20260825-044912-9fe3b68.md),
superseding the prior dirty-tree/43-of-45 `20260801-042959-dbb3ab5` record and
the intermediate clean-tree/complete-but-FAIL `20260825-025943-4e220d1` record.
Every per-corner physical check (`kick_sigdep_lsb <= 0.1`, `kick_diff_small_lsb
<= 0.25`, common-mode and decision-correctness bounds) **passes at all 45
points** — the kickback numbers themselves are unchanged from the deck's
only geometry, and are bit-for-bit identical to `20260825-025943-4e220d1`
(there is nothing else to compare them against, and this run made no netlist
change of any kind). `20260825-025943-4e220d1`'s **Overall verdict was FAIL**,
but for a reason independent of #238 entirely: one grid-level sanity check
(`peak_dip_uv`'s required ≥ 3 % `min_spread_pct_by_axis` on the temperature
axis) measured 2.72502 % at its weakest slice (`ff`, 3.63 V — hand-verified
against the raw corner logs: 398 → 404 → 409 µV across −40/27/125 °C, spread
= 11/403.667 × 100 = 2.725 %). That FAIL was filed as its own follow-up issue,
[#250](https://github.com/2AMLogic/gf180-sar-adc/issues/250), rather than
patched here, since adjusting a harness sensitivity-check threshold without
its own investigation is exactly the kind of change that should not ride
along with an unrelated measurement. Issue #250's investigation found the
2.72502 % slice to be a real, monotonic, non-numerical-floor physical
sensitivity (temperature moves `peak_dip_uv` less than process does at this
deck's weakest corner, but it is not flat) that the 3.0 % floor was never
actually calibrated against on a clean tree — the only prior run was both
dirty-tree and incomplete, and its dirty-tree temperature minimum (4.14428 %)
cleared 3.0 by coincidence, not calibration — so the floor was recalibrated
to 2.0 % with a cited rationale (`sim/comparator-kickback/testbench/tb.json`'s
`peak_dip_uv` description), and this record's **Overall verdict is PASS**.

**Item 4 — clock-driver load and power at the candidate acquisition-leg
width (`sim/adc-power/`, issue #247) — is measured, and the ratified Power
row does not move.** `sim/adc-power/testbench/tb_adc_power.spice` carries
the acquisition-leg `Xsi` T-gate exactly once (`grep -c` confirmed before
starting; unlike item 1, this deck needed no second-replica patch), so
`sim/dr0019-cu-sweep/gen_cu_variant.py --deck power --c-unit-ff 35.6528
--acq-switch-scale 2.068` widens only that line, the same orthogonal
control the other four decks use. Full ratified 27-point `tt`/`ss`/`ff`
PVT grid (the deck's own established convention — its `tb.json` manifest
default of the wider 63-point `cdac` capacitor-corner set is a red herring
every one of its nine prior committed records overrides with an explicit
`tt ss ff` selection, confirmed against all nine before running), clean
tree, schematic, clean-tree PASS:
[`sim/adc-power/records/20260825-044700-9229d0d.md`](adc-power/records/20260825-044700-9229d0d.md).
Re-verified by hand: re-running the `tt_27c_3.30v` point alone against the
same emitted netlist reproduces every recorded figure at that corner
exactly.

The block the widened gate is driven from (`p_cdac_*_uw`, the CDAC
four-leg switches + local drivers on `vddd`) is where the cost shows up,
as expected: at the README-cited binding corner `ff_125c_3.63v` it grows
**+9.4 % to +15.1 %** across the deck's five input levels (30.9435 →
33.8736 µW at 0 % input, 34.8936 → 40.1526 µW at full scale), and the
worst point on the whole grid moves 36.4176 → 41.4832 µW (+13.9 %,
`ff_-40c_3.63v` at full scale). But that block is only ~15–20 % of total
converter power, so the sum every check actually gates on barely moves:
`p_total_*_uw`'s grid-worst point (`ff_-40c_3.63v`, mid-scale) goes
207.884 → 208.744 µW, **+0.41 %**, and the binding-corner total moves at
most +5.1 % (176.742 → 182.155 µW at 0 % input, the largest of the five
levels there). Every `p_total_*_uw` check (`max = 1000 µW`, i.e. the
ratified `< 1 mW` row) has over 4.5× headroom left at the candidate
geometry's worst point, and the `< 500 µW` stretch goal — not a hard
harness check, but README's own aspiration — still has 2.4× headroom
(208.744 µW vs. 500 µW). **The ratified Power row does not move into risk
at this geometry.** The DR-0014 top-plate `V_cm` switch block
(`p_trk_*_uw`, a different device from the acquisition leg) is
unaffected as expected (≤ 0.4 % at every level), and the comparator,
V_REF and V_cm blocks move by low-single-digit-percent amounts consistent
with the array's own timing shifting slightly, not with a new coupling
path. All of this deck's own checks (`p_cmp_*_uw`'s `[20, 200]` µW bounds
and 2 % process-axis sensitivity floor) still pass at the candidate
geometry.

**Item 5 — array area and routing in `layout/adc-top/` (issue #248) — is
measured, and it is the one deferred item that goes the wrong way.** Unlike
item 1, this is a genuine `klt`-verified re-layout, not a schematic-level
harness run: `layout/adc-top/candidates/gen_acq_leg_candidate.py` calls
`layout/adc-top/gen_adc_top.py`'s own `build()` unmodified against a
candidate netlist with ONLY the `Xsi` fourth-leg T-gate widened 2.068×
(`10u`/`20u` → `20.68u`/`41.36u`, the same isolation `--acq-switch-scale`
performs on the schematic side), confirmed to reach the placer genuinely
width-parametrically (`place.draw_devices`/`geometry.draw_mosfet` draw every
MOSFET at its own flattened `w`) rather than into a hardcoded pitch. Full
result, DRC-clean and LVS-matched on both `ADC_TOP` and `ADC_BLOCK`:
[`layout/adc-top/candidates/records/20260825-030447-4e220d1.md`](../layout/adc-top/candidates/records/20260825-030447-4e220d1.md).
Headline: `block_total` grows **150536.239 → 176126.8006 µm² (+17.00 %,
+0.150536 → +0.176127 mm²)** — a height-only growth of the decode-bank row
(the bank's tallest active is now the widened `Xsi`, not the ratified
10u/20u legs), diluted from a per-bank-row +69.69 % once amortised over the
CDAC arrays / comparator / SAR-logic reserve, none of which the candidate
touches. Against #237's two contested Area-row figures (open — DR-0024 is
`proposed`, not ratified): the candidate is **+76.1 % over** the
still-nominally-ratified `< 0.1 mm²` row (README.md line 98; the ratified
geometry alone is already +50.5 % over), and **+10.1 % over even the
proposed-but-unratified `< 0.16 mm²` DR-0024 figure** the ratified geometry
currently passes under (−5.9 % margin). This is the first of the five
deferred items whose measured evidence argues AGAINST the acquisition-leg
lever rather than merely leaving it unconfirmed: the same width change that
recovers 89–101 % of the dynamic-range loss (§0 item 3) also pushes the
block out of range of both readings of the Area row, not just the stricter
one it already missed.

## 5. Provenance

Eight recorded harness runs, one per sweep point, each nine corners
(3 process × 3 supply, 125 °C), all clean-tree, all harness verdict PASS,
under [`sim/dr0019-cu-sweep/records/`](dr0019-cu-sweep/records/) with their
raw ngspice logs under `corners/<record-id>/` and the exact netlist each ran
under `netlist-snapshots/<record-id>.spice`. ngspice-47, gf180mcuD
(`open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b`); the toolchain pin
block in each record carries the full set.

Methodology, the reason each `C_u` point is on the axis, and how to re-run a
single point: [`sim/dr0019-cu-sweep/README.md`](dr0019-cu-sweep/README.md).
The same result is adjudicated alongside the rest of the DR-0019 re-take in
[`spec/testbench-suite-memo.md`](../spec/testbench-suite-memo.md) §11.9.9.
