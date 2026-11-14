# Issue #800 -- Candidate ranking for the cold-corner ENOB/SFDR distortion shortfall (2026-11-14)

- **Date**: 2026-11-14 (UTC)
- **Base commit**: `362c3ae7` (`main`), clean tree. Every path and figure below
  was read at this commit; Sec 8 names the command that produces each one.
- **Provenance**: **no new simulation.** This record is a synthesis of
  already-committed evidence plus arithmetic on it. Every number is tagged
  **repo-stated** (read from a committed record, not re-derived), **derived**
  (arithmetic on repo-stated inputs, reproducible per Sec 8), or **inferred**
  (a mechanism argument, not independently measured). An inference is never
  promoted to a measurement.
- **Scope**: what #800 asks for -- a ranked candidate list, each candidate
  carrying its mechanism, bearing evidence by path, cost against the other
  ratified rows, spec-change status, and the single measurement that would
  decide it. **It adopts nothing, changes no schematic, layout or spec row, and
  is not a decision record.** A later DR would use this as input.
- **Verdict**: the candidate set is **not** the one the issue's framing assumed,
  for one dominant reason -- **the intermediate-width question DR-0025 left open
  has since been measured** (`sim/acq-leg-width-sweep/`, issue #429, six widths
  with both layout and spectral halves). That campaign, read against the
  **2026-11-01 re-floorplan**, puts a specific candidate -- **1.75x** -- in a
  materially better position than any record on file currently states. Three
  further findings (Sec 3) set the ranking.

## 1. The gap

| Row | Governing value | Target | Gap |
|---|---|---|---|
| ENOB @ Nyquist | **8.734 bits** (`ss_-40c_2.97v`, composed) | `> 9.0` | 0.266 bits = **~1.60 dB** of SNDR |
| SFDR @ Nyquist | **57.96 dB** (`ss_-40c_2.97v`) | `>= 62 dB` | **4.04 dB** |

Both **repo-stated**, from the 27-point extracted grid
[`records/20261105-125230-b281aa8.md`](../records/20261105-125230-b281aa8.md) as
composed in
[the 27-point investigation record](20261105-issue-430-27pt-temperature-coverage-result.md)
Sec 4. Cold noise is *lower* than hot (comparator 76.9 uV here vs 124-153 uV at
125 C), so this is a distortion shortfall, not a noise one (that record's Sec 6
conclusion 4).

**The ENOB gap is inside the testbench's own stated resolution.** That record's
Sec 6 conclusion 5 warns the 64-sample single-tone FFT resolves one bin pair per
harmonic, shows **1-3 dB** of point-to-point SFDR scatter, and that "no
single-point ranking within a temperature should be over-read." Sec 3.3 and 3.4
below show that warning is load-bearing, not boilerplate.

## 2. What the design actually is

Three **repo-stated** facts about the built path that the candidate set turns on
and that are easy to get wrong:

1. **The acquisition path is nine parallel `10u`/`20u` cell T-gates per side,
   not one dedicated switch.** `design/adc-top/gen_adc_top.py` sets
   `CDAC_SW_WN = "10u"` / `CDAC_SW_WP = "20u"` (lines 123-124) and instantiates
   the `Xsi` fourth (input/acquisition) leg at those widths (line 298). The
   deck's own comment at lines 2270-2274 says it outright: "The input no longer
   reaches the array through one dedicated 40u/80u dummy-compensated T-gate ...
   it reaches it through NINE `10u`/`20u` cell T-gates per side, one per weight,
   in parallel." `README.md`'s Input-structure row gives the result: **series
   switch `R_on` 21.3-60.0 ohm over PVT**.
2. **DR-0007's ratified choice is therefore not in the design.**
   [`DR-0007`](../../../spec/decision-records/DR-0007-track-switch-topology.md)
   (`Status: proposed`) chose a 4x T-gate (`40u`/`80u`) **with half-width dummy
   charge-injection compensation**; its own Consequences say it "does not yet
   replace the placeholder". DR-0014's built path superseded it
   architecturally. The widths were superseded favourably -- nine parallel legs
   are *lower* `R_on` than one 4x switch -- but **the dummy compensation was
   dropped and nothing replaced it** (candidate A4).
3. **`R_on` flatness is width-independent to first order.**
   `sim/device-characterization-report.md` Sec 2 preamble: "`R_on` scales as
   ~1/W and injected charge as ~W.L ... the flatness ratio is W-independent to
   first order." So no width change at any scale moves the flatness *ratio*.
   What width moves is the *absolute* `R_on` variation, and that is what sets
   lag distortion -- Sec 3.2 prices it against measured data.

## 3. Four findings that set the ranking

### 3.1 The intermediate-width question is measured, and 1.75x passes both rows on the hot subset

DR-0025's "Alternatives considered" rejected a smaller scale factor "for lack of
evidence, not on principle", and its Consequences named it a defensible
follow-up. **That follow-up ran.** `sim/acq-leg-width-sweep/` (issue #429) has
both halves, all **repo-stated**:

- Layout, [`findings-20261008.md`](../../acq-leg-width-sweep/findings-20261008.md)
  Sec 2 -- six widths, each a real `klt` run, **DRC-clean and LVS-matched on
  both `ADC_TOP` and `ADC_BLOCK` at every width**, with the regenerated 1x
  control byte-identical to production.
- Spectral, [`findings-20261031.md`](../../acq-leg-width-sweep/findings-20261031.md)
  Sec 2 -- a nine-point (3 process x 3 supply, 125 C) schematic FFT record per
  width. Formally superseded point-for-point by the 2026-11-08 pinned-PDK
  re-qualification (open_pdks `f6eeac7`,
  [`sim/requalification-616-cu-width-vcm.md`](../../requalification-616-cu-width-vcm.md))
  with **0/75 measurements changed per width**, so every spectral figure cited
  below is unchanged at the current PDK pin.

| scale | `Xsi` wn/wp (um) | block (um) | `ADC_BLOCK` mm2 | worst SFDR dB | worst ENOB b | SFDR >= 62 | ENOB > 9.0 |
|---|---|---|---|---|---|---|---|
| 1.000 (control) | 10 / 20 | 599.35 x 253.32 | 0.151827 | 56.41 | 8.507 | 5/9 | 7/9 |
| 1.100 | 11 / 22 | 599.35 x 257.32 | 0.154225 | 56.89 | 8.625 | 5/9 | 7/9 |
| 1.250 | 12.5 / 25 | 599.35 x 263.32 | 0.157821 | 59.62 | 8.879 | 6/9 | 8/9 |
| 1.500 | 15 / 30 | 599.35 x 273.32 | 0.163814 | 60.58 | 9.041 | 8/9 | **9/9** |
| **1.750** | **17.5 / 35** | 599.35 x 283.32 | 0.169808 | **63.02** | **9.240** | **9/9** | **9/9** |
| 2.068 (DR-0025's) | 20.68 / 41.36 | 599.35 x 296.04 | 0.177432 | 60.80 | 9.170 | 8/9 | 9/9 |

All worst-corner figures are at `ss_125c_2.97v`. **1.75x is the only width that
passes both ratified rows at all nine schematic hot corners**, and it does so
with margin (+1.02 dB SFDR, +0.240 bits ENOB). `findings-20261031.md` Sec 4
already recommends 1.5x and 1.75x for extracted full-temperature
characterization -- but conditions it: "Both exceed the proposed `< 0.16 mm^2`
area limit, so any adoption also needs the area decision (DR-0024) to go that
way." **That condition is what Sec 3.2 revisits.**

### 3.2 The area cost was measured on a floorplan the design has since left

Every area figure above -- and DR-0025's own -- predates the **2026-11-01**
re-floorplan. **Repo-stated**, from `layout/adc-top/area.json`:

| | width-sweep / DR-0025 era | HEAD (`362c3ae7`) |
|---|---|---|
| `block_total` | 0.151827 mm2 (sweep 1x) / 150,536.239 um2 (DR-0025) | **128,764.886 um2** |
| block dimensions | 599.35 x 253.32 um (sweep 1x) / 599.03 x 251.3 um (DR-0025) | **670.93 x 191.92 um** |

The reduction landed in `16282205`, *"layout(adc-top): place SAR reserve in a
top-right notch with an L-shaped analog guard ring"*, dated **2026-11-01** --
after both DR-0025 (2026-08-25) and the sweep's layout half (2026-10-08). The
intermediate area-limit record
[`20261030-210500-be1c350.md`](../../../layout/adc-top/economy/records/20261030-210500-be1c350.md)
still reads 0.151827 mm2, so the whole reduction is that one commit.

The sweep's own table makes the cost mechanism exact and checkable: **block
width is constant at 599.35 um across all six widths; only the height grows**
(253.32 -> 296.04 um). The 1x row cross-checks to the micron --
599.35 x 253.32 = 151,827 um2 = 0.151827 mm2 **exactly**. Carrying those
**measured absolute height deltas** onto HEAD's floorplan gives (**derived**;
the delta is a device-geometry property, the floorplan supplies `w` and `h`):

| scale | measured dh (um) | as measured | vs `< 0.16` | **projected on HEAD** | vs `< 0.16` | vs ratified `< 0.10` |
|---|---:|---:|---:|---:|---:|---:|
| 1.000 | 0.00 | 0.151827 | -5.1% | 0.128765 | -19.5% | +28.8% |
| 1.100 | 4.00 | 0.154225 | -3.6% | 0.131449 | -17.8% | +31.4% |
| 1.250 | 10.00 | 0.157821 | -1.4% | 0.135474 | -15.3% | +35.5% |
| 1.500 | 20.00 | 0.163814 | **+2.4%** | 0.142183 | **-11.1%** | +42.2% |
| **1.750** | 30.00 | 0.169808 | **+6.1%** | **0.148893** | **-6.9%** | +48.9% |
| 2.068 | 42.72 | 0.177432 | +10.9% | 0.157427 | -1.6% | +57.4% |

**So `findings-20261031.md` Sec 4's blocking condition plausibly no longer
applies to 1.5x or 1.75x.** Both were measured *over* DR-0024's proposed
`< 0.16 mm2`; both project *comfortably under* it on the current floorplan
(-11.1% and -6.9%). An independent cross-check: applying DR-0025's separately
stated mechanism (decode-bank row +69.69%, two banks, width held) to its own
baseline reproduces its measured 176,126.8006 um2 to **-0.000%**, and projects
2.068x onto HEAD at 158,222 um2 -- within 0.5% of the 157,427 um2 the
measured-delta method gives. Two independent models agree.

**Three things still bind, and none of them is temperature:**

- **This is a projection, not a re-layout.** The 2026-11-01 commit added an
  L-shaped guard ring and a top-right SAR notch -- exactly the features that
  could break "height-additive, width-constant", which held exactly on the old
  rectangular floorplan. **Inferred**, and the reason A2's deciding measurement
  is a placer re-run rather than an argument.
- **Every width still fails the ratified row**, 1.75x by +48.9%, and the
  **operator ruling of 2026-10-30** recorded in the economy record's Purpose is
  explicit: "DR-0024 is **not** ratified, the `< 0.1 mm^2` row stands and stays
  a disclosed FAIL." The ratified row is the primary reading; `< 0.16 mm2` is
  secondary. The 1x baseline already fails it by +28.8%, so no width *newly*
  requires a relaxation -- but none removes the need for one either.
- **DR-0025's second argument is untouched.** Its asymmetric-evidence point --
  a schematic 125 C-only 9-point benefit against a DRC-clean LVS-matched area
  cost -- applies to the whole sweep: the spectral half is still schematic,
  still 125 C-only. **No width has been measured at cold, on either deck.**

What changes is the disposition of DR-0025's Area leg: it is no longer
*decisive on the current tree*, it is *unestablished on the current tree*. And
DR-0025 rejected **2.068x specifically**, which the sweep now shows is
**dominated** -- 1.75x is cheaper in area *and* better on worst-corner SFDR.

### 3.3 The width series is non-monotonic, and the repeat capture cannot resolve it

`findings-20261031.md` Sec 3 flags it: SFDR rises with width to 1.75x, then
**2.068x is 2.22 dB worse than 1.75x** (60.80 vs 63.02), and per-corner SFDR
scatters by several dB between neighbouring widths. Its own Sec 3 warns "the
curve must not be interpolated or read as a smooth law", and Sec 4 recommends
"a repeat capture (different seed/phase or more samples) at 1.5x, 1.75x and
2.068x ... to separate real ordering from scatter."

Fitting the two-term model `D(k) = D_acq/k^2 + D_other` -- the `1/W` scaling of
lag amplitude plus a non-scaling residual -- across **all six** widths at
`ss_125c_2.97v` (**derived**, Sec 8):

| scale | SFDR measured | fit | residual |
|---|---:|---:|---:|
| 1.000 | 56.41 | 56.52 | -0.11 |
| 1.100 | 56.89 | 57.36 | -0.47 |
| 1.250 | 59.62 | 58.50 | +1.12 |
| 1.500 | 60.58 | 60.15 | +0.43 |
| 1.750 | 63.02 | 61.56 | +1.46 |
| 2.068 | 60.80 | 63.12 | **-2.32** |

Residual RMS **1.24 dB**, max **2.32 dB** -- squarely inside the record's own
1-3 dB scatter band, and the largest residual is the anomalous 2.068x point.
The fit puts the acquisition-lag share at `a = 1.02`, i.e. **no detectable
non-scaling distortion floor**, and `k = 1.84x` to reach 62 dB. Two
consequences:

- **There is no evidence of a widening "ceiling".** A two-point fit using only
  1x and 2.068x -- the only data DR-0025 had -- yields a spurious `a = 0.830`
  and an apparent 64.1 dB ceiling, purely because 2.068x is the low outlier.
  With six widths that artefact disappears. Any ceiling argument against the
  width class is unsupported.
- **The 1.75x-vs-2.068x ordering is unresolved**, so 1.75x's 9/9 pass may be a
  favourable capture rather than a real optimum.

**And the recommended scatter test has not actually been performed.** Five
records dated **2026-11-08** (`20261108-221350`, `-221813`, `-222405`,
`-222856`, `-223322`) re-run widths 1.1 through 2.068 -- but at **N = 64
samples, 484375.0 Hz, bin 31**, identical to the 2026-10-31 set, and their
per-corner code rows are **bit-identical at all nine corners at every width**
(**derived**, Sec 8; the 1x control was not re-run). The set is not an
uninterpreted repeat: it is the pinned-PDK re-qualification under #616
([`sim/requalification-616-cu-width-vcm.md`](../../requalification-616-cu-width-vcm.md)),
which supersedes the 2026-10-31 records point-for-point with **0/75
measurements changed per width** (open_pdks `f6eeac7`, runner klt 0.9.0,
ngspice 46). It confirms the simulation is reproducible under the current PDK
pin; it supplies neither the different phase nor the longer capture Sec 4 asked
for, so it cannot separate ordering from scatter. **This is the cheapest open
item on the whole list.**

### 3.4 No `R_on`-derived proxy explains the measured per-corner distortion

Every class-A and class-B candidate targets `R_on(V_in)`. So: does
`R_on(V_in)` predict the measured per-corner distortion at all? Four proxies
were computed from the committed 7-point `R_on` ladder and correlated against
the 27 composed SFDR / THD figures (**derived**, Sec 8): the flatness ratio,
the absolute variation `dR_on`, and an exact-bin DFT of the lag error
`R_on(V(t)) * dV/dt` in both absolute and shape-only form.

**None correlates** (n = 27, Spearman against SFDR rho = -0.25...-0.16, all
p >= 0.21; against THD rho = +0.04...+0.29, all p >= 0.14). Unchanged across
all four `R_on` records -- the schematic pair `20260731-191216-5f5288b` /
`20260806-140624-4f71285` and the extracted pair `20260814-191138-f613571` /
`20260923-102440-904af96` -- and insensitive to device width, because a uniform
width scale shifts every corner's absolute proxy by the same `20log10(k)` and
leaves the shape proxy exactly invariant. So Sec 2.1's nine-parallel-leg
geometry does not explain the null.

Two specific contradictions, not just a weak fit:

- **Process axis, wrong direction.** Pooled over temperature and supply, the
  proxy puts `ff` ~7-8 dB *cleaner* than `ss` (absolute proxy -22.1 vs
  -30.4 dB re 1 ohm). Measured, `ff` is **worse** than `ss` on mean SFDR
  (61.24 vs 61.86 dB). An 8 dB predicted spread appears as -0.6 dB the other
  way.
- **Temperature axis, flat.** Pooled mean SFDR is 62.34 / 61.45 / 62.17 dB at
  -40 / 27 / 125 C -- a **0.89 dB** spread, inside the 1-3 dB scatter band --
  while the flatness ratio varies 2.21 -> 1.80 over the same axis. **"Cold
  governs" is carried by one point**, not by a temperature trend.

What survives: the flatness ratio is the only proxy that picks
`ss_-40c_2.97v` as the single worst point, on both decks (schematic 3.289,
extracted **2.357** -- extraction's series parasitic resistance dilutes the
ratio well below the 3.29 that `README.md`'s Rate row and
`sim/device-characterization-report.md` Sec 2.1 cite). `dR_on` picks
`ss_27c_2.97v` instead (schematic 351.7 vs cold's 330.2 ohm; extracted 343.5 vs
328.8). The two scalars disagree about which point governs, and the aggregate
orderings match neither.

This does **not** say the mechanism is wrong --
`sim/dr0019-cu-sweep-findings.md` Sec 2's -20 dB/decade test (measured mean
-17.69 dB/decade against a predicted -20.00, fitting best at the slow low-supply
corners where `R_on` is largest) is good evidence for it on the `C_u` axis, and
Sec 3.1's six-width series is good evidence on the `R_on` axis. It says the
**per-corner attribution** on this grid is not resolved well enough to aim a fix
at `ss_-40c_2.97v` specifically, nor to read back a 1-4 dB improvement as a
success. Every class-A/B deciding measurement inherits that problem, which is
why Sec 5 ranks the measurement first.

## 4. Candidates

Grouped by mechanism class. Each carries mechanism; bearing records by path;
cost against the other ratified rows; whether it needs a spec change; and the
single deciding measurement (testbench, corner set, pass condition), sized to be
filed as one issue.

### Class A -- absolute-`R_on` levers (reduce `dR_on`; cannot move the flatness ratio, Sec 2.3)

**A2. Adopt an intermediate acquisition-leg width -- 1.75x, with 1.5x as the
cheaper fallback.** *(Listed first: it is the best-evidenced candidate on file.)*
- *Mechanism*: `dR_on` falls as `1/k`, lag distortion with it (Sec 3.3's fit:
  `a = 1.02`, no detectable non-scaling floor, `k = 1.84x` for 62 dB).
- *Evidence*: `sim/acq-leg-width-sweep/findings-20261008.md` Sec 2 (layout,
  DRC-clean + LVS-matched at every width) and `findings-20261031.md` Sec 2-4
  (spectral); `layout/adc-top/area.json` + commit `16282205` (the changed
  baseline, Sec 3.2); `sim/dr0019-cu-sweep-findings.md` Sec 2-3 (mechanism).
- *Cost*: **Area** -- 1.75x measured 0.169808 mm2 (+11.84%), **projected
  0.148893 mm2 on HEAD**: -6.9% under DR-0024's proposed `< 0.16 mm2`, +48.9%
  over the ratified `< 0.1 mm2`. 1.5x: 0.142183 mm2 projected, -11.1% / +42.2%.
  **Power** +0.41% grid-worst at 2.068x, so less at 1.75x; ratified `< 1 mW`
  keeps 4.79x margin (DR-0025's summary of
  `sim/adc-power/records/20260825-044700-9229d0d.md`).
  **Sampling/INL** noise-floor only at 2.068x, `samp_inl_worst_lsb`
  0.30895 -> 0.30915 against +-1 LSB (DR-0025's summary of
  `sim/dr0014-sampling/records/20260825-015032-446a3c4.md`). Top-plate `C_par`
  structurally invariant
  (`sim/top-plate-cpar/records/20260825-034455-4cf1ca4.md`). **V_REF droop**
  4.05-4.06 mV at every width, unchanged.
- *Spec change*: **Area needs an operator decision either way** -- it is a
  standing disclosed FAIL at the 1x baseline too, so this candidate does not
  newly require a relaxation, but it does not remove the need for one. Listed as
  such. **Not recommended for adoption ahead of its deciding measurements**,
  but it is the candidate those measurements are worth spending on.
- *Deciding measurement* -- two, in order, both already named by existing
  records: **(i)** extracted, **full-temperature** (-40/27/125 C) FFT at 1.5x
  and 1.75x -- `sim/dr0019-cu-sweep/gen_cu_variant.py --acq-switch-scale S` on
  the extracted deck, 2 widths x 9 points at 2.97 V, or the full 27 if budget
  allows. *Pass condition*: worst composed ENOB `> 9.0` **and** worst SFDR
  `>= 62 dB` at `ss_-40c_2.97v`, the governing point no width has yet seen.
  **(ii)** `"$KP" layout/adc-top/candidates/gen_acq_leg_candidate.py --scale
  1.75` against the HEAD floorplan + `klt` DRC/LVS. *Pass condition*:
  `block_total <= 160,000 um2`, DRC-clean, LVS-matched on both cells -- which
  converts Sec 3.2's projection into a measurement.

**A1. DR-0025's 2.068x widening.**
- *Mechanism*: as A2, at a larger factor.
- *Evidence*: as A2, plus
  `spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md` and
  `layout/adc-top/candidates/records/20260825-030447-4e220d1.md`.
- *Cost*: **strictly worse than A2 on both axes** -- 0.157427 mm2 projected vs
  1.75x's 0.148893, and 60.80 dB worst SFDR vs 63.02 (8/9 vs 9/9 corners).
- *Spec change*: as A2, larger.
- *Disposition*: **dominated -- listed, not recommended.** Its rejection should
  not be revisited on its own terms: DR-0025's Area leg is unestablished on the
  current tree (Sec 3.2), but the sweep has since produced a cheaper width that
  measures better, so the right successor question is A2's, not A1's. No
  separate deciding measurement; A2(ii) covers the area question for the class.

**A3. A folded / multi-finger `Xsi` at constant decode-bank height.**
- *Mechanism*: electrically identical to A2 at the same total W, but the width
  is reached by paralleling fingers rather than growing one device, so the
  decode-bank row's **tallest active does not grow** -- which Sec 3.2 shows is
  the entire area mechanism (width constant, height-only, across all six
  measured widths).
- *Evidence*: DR-0025's Consequences name exactly this as "an alternative
  acquisition-path redesign that does not cost decode-bank height ... open and
  unmeasured"; `findings-20261008.md` Sec 2's constant-599.35 um width column
  is the quantitative hook; `layout/adc-top/area.json`
  `dimensions_um.decode_bank` (440.94 x 31.50 um) is what it must hold.
- *Cost*: shifts area from height to width and routing congestion --
  **unmeasured**. Electrical costs are A2's.
- *Spec change*: **potentially none** -- this is the only candidate on the list
  that could hold the area budget flat, and so the only one bearing on the
  **ratified** `< 0.1 mm2` rather than just DR-0024's proposed figure.
- *Deciding measurement*: a multi-finger variant of the anchored `Xsi` line in
  `gen_acq_leg_candidate.py` at scale 1.75, then `klt` DRC/LVS.
  *Pass condition*: `block_total <= 130,000 um2` (within ~1% of HEAD's
  128,765) **and** DRC-clean **and** LVS-matched. **Ranked below A2** only
  because A2 already fits DR-0024's proposed figure without it; A3 is what to
  pursue if the operator holds the ratified row.

**A4. Restore DR-0007's dummy charge-injection compensation.**
- *Mechanism*: **not an ENOB/SFDR candidate -- listed to close it out.** Nine
  parallel `10u`/`20u` legs already give `R_on` 21.3-60.0 ohm, *lower* than
  DR-0007's 4x switch, so a dedicated switch would raise `R_on`. What the built
  path dropped is the **dummy compensation** (Sec 2.2), which bears on **Gain
  error**, not distortion.
- *Evidence*: `DR-0007` Context (gain-error table: nominal 2.04-2.92 LSB, 4x
  9.11-12.84, 4x+dummy 3.57-5.38, against `<= 0.5 LSB`) and its Consequences;
  `design/adc-top/gen_adc_top.py` lines 2270-2274.
- *Disposition*: **out of scope here, and a real gap worth its own issue** -- a
  chosen topology element the built design does not implement, against a row
  DR-0007 already flagged open (filed as #39 then). No deciding measurement
  proposed here.

### Class B -- flatness levers (the only class that moves the ratio, Sec 2.3)

**B1. A bootstrapped / input-level-independent track switch.**
- *Mechanism*: holding `V_gs` constant makes `R_on` input-independent, attacking
  the flatness ratio directly instead of scaling `dR_on`.
- *Evidence*: `DR-0007` Context measures, on the 117-point track-switch THD
  grid, worst single-ended SFDR **53.76 dB** (nominal 1x), **64.81 dB** (4x),
  **76.39 dB** (ideal bootstrap; 94.54 dB differential) -- the largest headroom
  on file by ~12 dB.
- *DR-0007's rejection, re-read*: two independent reasons. **Reason 1, "not
  needed" -- falsified.** It rests on "the 4x upsized T-gate already clears the
  SFDR floor with margin"; the governing extracted number is 57.96 dB, a FAIL.
  **Reason 2, device reliability -- still binds, and is categorical.** A classic
  bootstrap drives the boosted node to `V_in + V_DD`, up to **6.6 V** at
  `V_DD = 3.63 V`, ~2x the rating of the `nfet_03v3`/`pfet_03v3` flavor DR-0004
  ratifies -- "a categorical overstress by construction, not a marginal design
  risk to be verified away." Temperature is irrelevant to both legs; what
  changed is reason 1's premise. DR-0007 names the three mitigations: an
  `nfet_05v0`/`pfet_05v0` boost network (a second flavor, against DR-0004),
  active clamping, or a topology capping the boost above a mid-rail node.
- *Cost*: a second device flavor and its characterization burden, or new clamp
  circuitry; area and power unquantified. DR-0007's finding that 4x upsizing
  quadrupled charge-injection gain error warns that any switch-path change must
  be re-scored against **Gain error**.
- *Spec change*: **yes** -- DR-0004 would have to admit a second flavor, or the
  mitigation must avoid it. **Not recommended as a first move**: it is the
  largest design change on the list, and its own feasibility question was never
  measured -- DR-0007's 76.39 dB is an *ideal* bootstrap, explicitly "an upper
  bound on what bootstrapping could buy here, not a claim about a real circuit's
  terminal-voltage safety."
- *Deciding measurement*: re-enable `sim/track-switch-sampling`'s disabled
  `bs10`/`bs20` branches (DR-0007's Consequences record they were cut for
  runtime, `boot` subckt retained) and measure **peak terminal-to-terminal
  voltage** on every boost-network device at `ff_-40c_3.63v` and
  `ff_125c_3.63v`, schematic. *Pass condition*: every terminal pair within the
  3.3 V flavor rating. A fail routes to the `05v0`/clamped variants rather than
  killing the class. Cheap, and independent of the distortion question.

**B2. Reduce the input modulation depth (restrict full-scale range).**
- *Mechanism*: distortion scales with `dV_in/dt`; a smaller swing traverses less
  of the `R_on(V_in)` curve.
- *Evidence*: `sim/device-characterization-report.md` Sec 2.1 -- the `R_on` peak
  sits at ~2/3 rail at every corner; also its standing constraint that a
  full-scale 0-3.3 V input is not samplable at a drooped 2.97 V supply.
- *Cost*: reduces signal power, so it trades SFDR against SNR/ENOB -- the two
  failing rows move in opposite directions.
- *Spec change*: **yes** -- it relaxes the ratified Input row. **Listed as such,
  and not recommended**: it is the "relax the ratified spec to make results
  pass" pattern `CLAUDE.md` forbids and DR-0025 explicitly refused.
- *Deciding measurement*: none proposed; it needs a spec decision first.

**B3. Reverse DR-0019's `C_u` resize.**
- *Mechanism*: lag distortion amplitude is proportional to `C_arr`, so halving
  `C_u` buys ~6 dB.
- *Evidence*: `sim/dr0019-cu-sweep-findings.md` Sec 2's -20 dB/decade test
  (measured mean **-17.69 dB/decade**, `r = -0.925` at the governing corner
  `ss_125c_2.97v`, spanning -0.566 to -0.969 across the nine); Sec 3's
  pre-resize column
  (worst **61.33 dB**, vs 56.41 at the ratified `C_u`).
- *Cost*: **Gain error, mismatch** -- DR-0019 exists to buy that row's margin
  and moved it 2.12-sigma -> 3.13-sigma (`README.md`). Reversing re-breaks the
  row it fixed, and recovers only to 61.33 dB -- **still below the floor**.
  Also moves `C_in` (18.254 pF per side) and the DR-0002 reference-droop budget.
- *Spec change*: DR-0019 is `Status: proposed`, so reversal is lighter than its
  prominence suggests -- but it trades one failing row for another and does not
  reach 62 dB. **Listed; not recommended.**
- *Deciding measurement*: none proposed -- the pre-resize figure already shows
  the recovery lands below the floor, so no measurement changes the disposition.

### Class C -- measurement-validity candidates

**C1. Separate real width ordering from capture scatter, and test the cold
attribution.**
- *Mechanism*: not a circuit change. A different input phase and/or a longer
  capture reduces the 1-3 dB scatter that currently exceeds the ENOB gap,
  consumes the whole per-corner structure (Sec 3.4), and leaves 1.75x vs 2.068x
  unresolved (Sec 3.3).
- *Evidence*: the 27-point record's Sec 6 conclusion 5;
  `findings-20261031.md` Sec 3 and its Sec 4 recommendation, **which is still
  outstanding** -- the 2026-11-08 repeat is bit-identical at N = 64 and the same
  bin (Sec 3.3), so it supplies neither a new phase nor more samples.
- *Cost*: **compute only** -- no design, spec, area or power impact.
- *Spec change*: **no.**
- *Deciding measurement*: re-run `tb_adc_enob_fft_extracted.spice` at **256
  samples** (4x, with the coherent bin re-derived for N = 256) on the 2.97 V
  `ss` temperature leg plus `ff_125c_2.97v` -- 4 points, the minimum that tests
  both the scatter and Sec 3.4's one proxy contradiction; and the same at 1.5x /
  1.75x / 2.068x on the schematic hot subset to settle the ordering.
  *Pass condition*: `ss_-40c_2.97v` SFDR reproduces within **1.0 dB** of
  57.96 dB, `ff_125c_2.97v` stays below `ss_125c_2.97v`, and the
  1.75x-vs-2.068x sign is stable. If any leg fails, every class-A/B deciding
  measurement above is measuring noise and must be re-sized before it is run.

**C2. The gmin-stepping recovered operating point.**
- *Mechanism*: 13 of 27 points carry a klt `nonconvergence` / "Dynamic gmin
  stepping failed" warning; the record states "whether the recovered operating
  point biases the cold/room distortion figures is not tested here."
- *Evidence*: the 27-point record's Sec 2. **The governing point is not among
  them**: at 2.97 V the flagged set is `tt_-40c`, `tt_27c`, `ff_-40c`,
  `ff_27c`; `ss_-40c` is flagged only at 3.63 V.
- *Cost*: compute only. *Spec change*: **no.**
- *Deciding measurement*: re-run the four flagged 2.97 V points with tightened
  solver options, 4 points. *Pass condition*: each reproduces within 1.0 dB.
  **Ranked below C1** -- it cannot explain the governing number, which converged
  cleanly -- but three of those four points are ones Sec 3.4 finds anomalous, so
  it bears on the ordering C1 tests. Worth folding into C1 as one issue.

## 5. Ranking

Worst-first by *what should be done next*, not by expected benefit:

1. **C1 -- resolve the measurement (fold C2 in).** Cheapest item on the list,
   no design or spec risk, and it gates the credibility of every other
   candidate's deciding measurement. Sec 3.3 and 3.4 are the argument: the
   mechanism every class-A/B candidate targets does not predict the per-corner
   distortion; the ENOB gap is inside the testbench's own scatter; "cold
   governs" rests on one point; the width series is non-monotonic; and the
   repeat capture that was supposed to settle that is bit-identical, so the
   recommended test is still undone.
2. **A2 -- 1.75x (fallback 1.5x), extracted and full-temperature.** The
   best-evidenced candidate on file: the only width measured to pass **both**
   ratified rows at all nine schematic hot corners, DRC-clean and LVS-matched,
   and -- on the current floorplan -- projecting **6.9% under** DR-0024's
   proposed area figure where it was measured 6.1% over. Its two open
   questions are both one run each: cold behaviour, and the area projection.
3. **A3 -- folded `Xsi`.** The only candidate that could hold area flat, hence
   the only one bearing on the **ratified** `< 0.1 mm2`. Pursue if the operator
   declines to move the Area row; otherwise A2 does not need it.
4. **B1's reliability gate** -- the terminal-voltage measurement only. Class B
   has ~12 dB more headroom than any width lever and DR-0007's reason 1 is
   falsified, so the class deserves a cheap feasibility probe. The full
   bootstrap redesign is **not recommended** now.
5. **A1 -- 2.068x. Dominated; listed, not recommended.** Cheaper *and* better is
   available at 1.75x. DR-0025's Area leg is unestablished on the current tree,
   but that reopens the *class*, not this width.
6. **B3, B2, A4 -- listed, not recommended.** B3 trades the Gain-error row and
   still misses the floor; B2 relaxes a ratified row; A4 is a real but separate
   gap against Gain error, not a distortion candidate.

**One candidate now has a credible path to closing both rows** -- A2 at 1.75x,
which passes both on the schematic hot subset and, on the current floorplan,
plausibly within the proposed area budget. **That is not a pass**: it has never
been measured at the governing cold corner or on the extracted netlist, its
area advantage is a projection, and its 9/9 result sits inside a scatter band
that the one test able to resolve it has not yet been run with. The ranking
above is ordered to retire those three unknowns in increasing cost.

## 6. What is not known

1. **Any width's behaviour at cold, on either deck.** The entire width sweep is
   125 C-only and schematic; the governing point is `ss_-40c_2.97v` on the
   extracted netlist. This is the single largest gap, and A2(i) closes it.
2. **Whether the 1.75x > 2.068x ordering is real** or a favourable 64-sample
   capture. The 2026-11-08 repeat cannot answer it (Sec 3.3).
3. **Whether `ss_-40c_2.97v` genuinely governs.** Temperature-pooled means are
   flat to 0.89 dB and no `R_on` proxy reproduces the ordering (Sec 3.4).
4. **Whether the height-additive area model transfers to HEAD's floorplan.** It
   reproduces the old floorplan exactly (to the micron at 1x, to -0.000% for
   DR-0025's candidate), but the 2026-11-01 L-shaped guard ring and SAR notch
   are exactly what would break it. Every HEAD column in Sec 3.2 is a projection.
5. **A3's routing and width cost** -- nothing on file measures it.
6. **Whether a real bootstrap is implementable at 3.63 V** in this flavor.
   DR-0007's 76.39 dB is an *ideal* bootstrap; no real boost network has been
   simulated here.
7. **Secondary effects at 1.5x/1.75x** -- charge injection, kickback, leakage,
   sampling-switch non-linearity and Monte Carlo mismatch are measured at
   2.068x only; `findings-20261031.md` Sec 4 names them as prerequisites.
8. **The extracted-vs-schematic flatness discrepancy.** Extraction dilutes the
   `ss_-40c_2.97v` flatness ratio from 3.289 to 2.357, yet `README.md`'s Rate
   row and `sim/device-characterization-report.md` Sec 2.1 cite 3.29 -- sourced
   from `20260731-191216-5f5288b`, which self-declares "taken against a dirty
   working tree ... not citable as a clean-tree result". Not acted on here;
   worth a follow-up.

## 7. Correcting one thing this record got wrong first time

Recorded so the next reader does not repeat it. An earlier draft of this
analysis concluded, from the only two width points DR-0025 had (1x and 2.068x),
that widening carried a **hard ceiling of ~64.1 dB** and needed `k ~ 2.80x` to
reach 62 dB -- i.e. that the whole width class was ceiling-limited and a
narrower factor went "the wrong way". **Both claims were artefacts of the
two-point fit**: 2.068x is the low outlier of the six-width series (-2.32 dB
residual, Sec 3.3), and fitting all six widths instead gives `a = 1.02` -- no
detectable non-scaling floor -- and `k = 1.84x`. The lesson is the one
`findings-20261031.md` Sec 3 states directly: do not read a law off two points
of a series whose own scatter is 1-3 dB.

## 8. Reproducing this record's arithmetic

All inputs are committed; no simulation was run. At `362c3ae7`:

```bash
# Measured figures, read directly:
sed -n '/^## 4\./,/^## 5\./p' \
  sim/adc-enob-fft/investigations/20261105-issue-430-27pt-temperature-coverage-result.md
sed -n '/^## 2\./,/^## 3\./p' sim/acq-leg-width-sweep/findings-20261008.md   # layout
sed -n '/^## 2\./,/^## 3\./p' sim/acq-leg-width-sweep/findings-20261031.md   # spectral
sed -n '/^## 3\. The orthogonal control/,/^### Reconciling/p' sim/dr0019-cu-sweep-findings.md
grep -n 'ron_t_f\|ron_t_flatness' sim/device-switch-ron/records/20260731-191216-5f5288b.md

# Sec 3.2 -- the changed area baseline:
git show 076d5457:layout/adc-top/area.json | python3 -I -c \
  "import json,sys;print(json.load(sys.stdin)['areas_um2']['block_total'])"   # 150536.239
python3 -I -c "import json;d=json.load(open('layout/adc-top/area.json'));\
print(d['areas_um2']['block_total'], d['dimensions_um']['block'])"            # HEAD
git log -1 --format='%H %ad %s' --date=short 16282205

# Sec 3.3 -- the 2026-11-08 repeat is bit-identical (per width, per corner):
for c in tt ss ff; do for v in 2.97 3.30 3.63; do
  n="${c}_125c_${v}v"
  a=$(grep -E "^\s*\|\s*\`$n\`" sim/acq-leg-width-sweep/records/20261031-204610-51e89c5.md | md5sum)
  b=$(grep -E "^\s*\|\s*\`$n\`" sim/acq-leg-width-sweep/records/20261108-222856-3b60e1b.md | md5sum)
  [ "$a" = "$b" ] && echo "$n identical" || echo "$n DIFFERS"
done; done
```

The three derived tables are arithmetic on exactly those inputs:

- **Sec 3.2 area projection**: carry each width's *measured* absolute height
  delta `dh(S)` (from `findings-20261008.md` Sec 2's block column, width
  constant at 599.35 um) onto HEAD's floorplan:
  `A(S) = 670.93 * (191.92 + dh(S))`. Cross-check at `S = 1`:
  `599.35 * 253.32 = 151,827 um^2`, matching the record exactly. Independent
  cross-check via DR-0025's stated mechanism:
  `A = w * (h + 2*(bank_h*1.6969 - bank_h))`, which reproduces DR-0025's
  measured 176,126.8006 um2 from its own baseline to -0.000%.
- **Sec 3.3 fit**: least squares of `10^(-S_k/10) = D_acq/k^2 + D_other` over
  the six `(k, SFDR)` pairs at `ss_125c_2.97v`; `a = D_acq/(D_acq + D_other)`;
  `k_62 = sqrt(D_acq/(10^(-62/10) - D_other))`.
- **Sec 3.4 proxies**: `e(t) = R_on(V(t)) * sin(2*pi*t)` with
  `V(t) = (1 - cos(2*pi*t))/2` mapped onto the 7-point ladder by linear
  interpolation, `N = 4096`, unwindowed real DFT over exactly one period (so
  harmonic `k` lands in bin `k` with no leakage); absolute proxy
  `= -20log10(rms of bins 2..9)`, shape proxy `= 20log10(bin1 / that rms)`;
  Spearman and Pearson against the 27 composed SFDR / THD figures.

No file under `sim/`, `spec/`, `layout/`, `design/` or `README.md` was modified
to produce any of it.

## 9. Not done / limits

- **No simulation of any kind was run** -- no grid, no single-corner probe, no
  `ngspice` invocation. Every figure is read from a committed record or is
  arithmetic on committed records, tagged accordingly.
- **Nothing is adopted.** No schematic, layout, generator, spec row, decision
  record, README row or existing `sim/` record is changed. The dispositions here
  are inputs to a future DR, not decisions.
- **DR-0025 is neither reopened nor amended.** Decision records are superseded
  by new ones, never edited. Sec 3.2 records that one leg of its argument no
  longer holds on the current tree; acting on that requires a new record.
- Sec 3.3's model is first-order (`lag amplitude ~ 1/W`, one non-scaling
  residual) fitted to six points at one corner, with a 1.24 dB residual RMS. It
  is used to bound and to rank, never as a prediction.
- Sec 3.4's proxies use the 7-point `R_on` ladder, coarse for harmonic analysis;
  the *orderings* are method-consistent across corners and across all four
  `R_on` records, but the absolute values are not SFDR predictions.
- Capacitor-corner expansion, the real-`V_cm` campaign (#392) and the Offset
  row's missing `ADC_BLOCK` statistical population are out of scope, as in the
  record this one builds on.
