# Monte Carlo methodology memo — CDAC mismatch and comparator offset

**Status**: verification memo, supporting the linearity/accuracy claims in
`README.md#target-specification`. Not a decision record (see
`spec/decision-records/README.md` — this derives a methodology and reports
measured/simulated results, cited *from*, not itself, a decision record).
**Issue**: #14. **Consumes**: `spec/cdac-sizing-memo.md` §0–§3 (topology,
matching-to-linearity propagation, yield criterion), §4 (chosen unit cap);
`spec/comparator-budget-memo.md` §3–§4 (offset budget, tier-0 cancellation);
`sim/device-characterization-report.md` §5.1 (unit-cap mismatch data
provenance); `sim/comparator-offset-mc/` (#9's per-corner offset MC).
**Feeds**: #16 (comparator offset distribution for floorplan symmetry
decision); #17 (post-layout re-run of both records below).

Every number below is either a direct measurement from one of the two new
records in `sim/` this memo summarizes, or a citation of a number #8/#9
already ratified. Nothing here re-derives a yield criterion or a
cancellation tier independently — see §1.

---

## 0. Scope: two independent Monte Carlo questions, one memo

The issue bundles two distinct linearity/accuracy risks that both require a
*distribution*, not a corner-matrix pass/fail, to substantiate:

1. **CDAC unit-cap mismatch → INL/DNL distribution and yield** (§2).
2. **Comparator offset → effective-offset distribution and its
   linearity impact** (§3).

They are unrelated circuits (a capacitor array vs. a differential
preamplifier) sharing only the fact that both are mismatch — not
PVT-corner — claims, so §4 states the shared methodology decision once
rather than twice.

---

## 1. Yield criteria consumed, not chosen

This issue's Monte Carlo tests against **#8's and #9's own stated
criteria**. Restated here so both are traceable to one place without
re-deriving either:

- **CDAC**: `spec/cdac-sizing-memo.md` §3.3 states the yield criterion is
  **3σ**, for two reasons given there (matches the convention already used
  elsewhere in this repo; buys no meaningful extra margin at negligible
  area cost). This memo tests against 3σ because #8 said so — not because
  3σ is picked here independently.
- **Comparator**: `spec/comparator-budget-memo.md` §4 selects **tier 0**
  (no analog cancellation + digital offset removal), admissible because (a)
  DR-0006's MCS/Vcm switching holds the input common mode constant in
  differential mode and (b) the residual fits the ratified ≤ 2 LSB row at
  3σ. This memo tests the offset distribution against that **already-closed**
  tier and that already-ratified row — it does not re-open the tier-0
  admissibility question (§3.1).

---

## 2. CDAC unit-cap mismatch → INL/DNL

### 2.1 Why behavioral, not transistor-level ngspice

`sim/device-characterization-report.md` §5.1 and
`sim/tools/pdk_mismatch_audit.py` both establish, as a **negative finding**,
that the open gf180mcu PDK ships no local capacitor mismatch model
(`cap-local-mismatch` / `moscap-statistics` are both `ABSENT`). An ngspice
Monte Carlo of the CDAC array under this PDK would therefore report exactly
zero mismatch at any trial count — a silent false pass, not a conservative
one. The issue's own text anticipates this gap and explicitly permits "a
behavioral CDAC model calibrated to extracted unit-cap sigma ... if the
calibration is recorded" — that is the path taken here.

**Tool**: `sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py`, a
standalone Python/NumPy/SciPy script (not invoked through
`sim/run_corners.py` — there is no ngspice deck to run, so the harness's
per-PVT-point ngspice runner does not apply). This is a real, stated
divergence from the rest of `sim/`, which is stdlib-only
(`docs/environment-setup.md` §1): reproducing this record needs
`pip install numpy scipy` in addition to the pinned toolchain. Neither
`sim/run_corners.py`'s harness nor CI import this script, so this does not
add a dependency to the existing pinned toolchain or to
`.github/workflows/ci.yml`'s headless checks — it is a new, self-contained
tool, and this is the calibration record its own header points to.

### 2.2 Calibration (cited from `spec/cdac-sizing-memo.md`, not re-derived)

Per §2 there, unit-cap mismatch follows the Pelgrom area law
`σ(ΔC/C) = A_C / √A_unit`, `A_C = 2.0 %·µm`
(`literature-assumption-with-derating`, 2× derated per
`sim/device-characterization-report.md` §5.1). Per §4, the **chosen** unit
cap is `C_u = 17.24 fF`, `A_unit = 7.36 µm²` (2.71 µm square), sized to the
stretch (< 0.5 LSB) target:

```
σ_u (chosen design)  = 2.0 / sqrt(7.36)  = 0.7372 %
σ_u (baseline-only, for comparison, NOT the chosen design)
                     = 2.0 / sqrt(1.839) = 1.4748 %
```

The **chosen design's** `σ_u = 0.7372 %` is what this Monte Carlo
propagates; the baseline-only figure is reported in §2.5 for context only,
because #8 did not choose that geometry.

**Nominal transfer-function fidelity (why this idealization does not itself
inject error).** The model in §2.3 is, at zero mismatch (`δ_i = 0` for all
`i`), an exactly ideal ratiometric charge divider: `V(c) = c/511` in the
sub-array's own units, by construction — there is nothing else in the model
to deviate from that. The issue's calibrated-behavioral-model acceptance
criterion requires more than construction-by-definition, though: it
requires showing the **real,
transistor-level** array (switch resistances, transient settling, drive
non-idealities) actually reaches that same ideal step closely enough that
substituting the idealization for it does not itself inject error into the
reported INL/DNL distribution. That evidence already exists and is not
re-derived here: `spec/cdac-sizing-memo.md` §5.3, backed by
`sim/cdac-bit-settling/records/20260731-231537-1ee5578.md` (117/117 PVT
points, transistor-level T-gate switches at the actual measured `R_on`),
measures every trial's top-plate settling error against the ideal step
`(V_REF/2)·(w/512)` at the 1 MS/s bit-cycle budget and finds it **at or
below the simulator's numeric floor, `|err| ≤ 1×10⁻⁴ mV`, at every corner —
four orders of magnitude inside the 0.5 LSB (1.6113 mV) bound**, with zero
process-axis spread in the realized step (`≤ 2×10⁻⁴ %`). The real array
therefore reaches the ideal ratiometric step this behavioral model assumes
to a precision ~4 orders of magnitude finer than the mismatch effect being
measured, so the idealization is not the source of any of the σ_u = 0.7372 %
spread reported below — that spread is the calibrated mismatch injection
alone, not a settling artifact of the model.

### 2.3 Topology propagated — DR-0011's actual array, not plain binary

Per `spec/cdac-sizing-memo.md` §0/§3.1, bit 1 (the free MSB) carries **zero
mismatch by construction** — it is a sampled-charge sign decision, not a
charge-redistribution ratio — and is correctly excluded from this model.
The remaining 9 bits are the `2^(N-1) = 512`-position sub-array: **511 real
binary-weighted unit capacitors**, grouped into 9 weight classes (sizes
1, 2, 4, ..., 256 — the physical unit-capacitor count in each class, not a
scaling factor), plus one terminating dummy (weight 1, fixed to `V_cm`,
never switched, correctly omitted below since its own mismatch is a
common gain term identical for every code, not a DNL/INL term).

Each of the 511 physical unit capacitors is modelled as an independent
`C_i = C_u·(1 + δ_i)`, `δ_i ~ N(0, σ_u)`. Every trial evaluates the
**full 512-code transfer function** (all 511 DNL transitions, all 512 INL
points) — not a reduced/major-carry-only code set — so within the
behavioral-model boundary this is a full-code-ramp Monte Carlo. The
end-point-corrected INL definition (deviation from the line through codes 0
and 511, removing the array's own total-capacitance gain error) is used, not
a raw deviation from the ideal ramp — see the script's derivation comments
for why the raw form under-reports by not removing that gain term.

### 2.4 Fit-and-extrapolate, not empirical tail-counting — and why

A literal brute-force count of 3σ (two-sided tail probability
`2·(1−Φ(3)) ≈ 2.7×10⁻³`) or 6σ (`≈ 2×10⁻⁹`) failures needs, respectively,
order-`10³` and order-`10⁹` trials to observe a handful of tail events
directly. The latter is intractable at any trial count this memo could run;
the former is borderline (a few thousand trials would show only a handful
of 3σ events, not enough to characterize the tail shape). **This memo
therefore fits the sampled distribution to a Gaussian, checks the fit, and
computes yield at the target σ analytically from the fitted σ** — not by
counting tail trials.

`N = 5000` trials, `seed = 20260801` (numpy `Generator(PCG64)`, recorded
here and reproducible with `python3 mc_cdac_mismatch.py --seed 20260801
--trials 5000`). 5000 is chosen, not 20000+, specifically because
`scipy.stats.shapiro` is documented as losing accuracy above `N = 5000` — a
run at `N = 20000` was also taken as a cross-check (§2.6) and agrees with
the `N = 5000` figures to within 0.4 %, but the `N = 5000` run is the one
whose Shapiro p-value is citable at face value.

**The worst-case code is tracked at its known location (code 256), not by
taking a per-trial maximum over all codes** — a maximum over many codes
with near-degenerate variance is an extreme-value-type statistic, not
Gaussian, and §2.6 shows exactly this empirically. `spec/cdac-sizing-memo.md`
§3.2 derives code 256 (the sub-array's own MSB carry) as the transition
with the analytically largest variance for both DNL and INL; this
methodology fits and extrapolates from the value **at that specific,
analytically-motivated code**, and separately reports the empirical
per-trial max-over-codes statistic as a secondary, more conservative,
explicitly non-Gaussian bound (§2.6).

### 2.5 Goodness-of-fit

At `N = 5000`, `σ_u = 0.7372 %` (chosen design):

| Quantity | Measured σ (LSB) | Analytic formula (`spec/cdac-sizing-memo.md` §3.2) | Ratio | Shapiro-Wilk W | Shapiro-Wilk p |
|---|---|---|---|---|---|
| DNL at code 256 | 0.16782 | `√511·σ_u` = 0.16665 | 1.0070 | 0.99967 | 0.623 |
| INL at code 256 | 0.08391 | `√512/2·σ_u` = 0.08341 | 1.0060 | 0.99967 | 0.626 |

Neither Shapiro-Wilk p-value gives any reason to reject normality (both
`p ≈ 0.62`, far from any conventional significance threshold), and the
directly-simulated array reproduces the closed-form coefficients to within
0.7 % — a genuine validation of the array-level formula against a
trial-by-trial simulation of the actual topology, not merely a re-check of
the algebra. **This is the goodness-of-fit check AC1 requires before the
3σ extrapolation below.**

### 2.6 The max-over-codes statistic is NOT Gaussian, and is reported as such

`spec/cdac-sizing-memo.md` §3.2's variance derivation, extended to every
code (not just 256), gives `Var(DNL(c)) ∝` a sharply peaked function of `c`
with its unique maximum at `c = 256`, and `Var(INL(c)) ∝ c·(511−c)/511`, a
**parabola so flat near its maximum** (at `c ≈ 255.5`) that many codes near
the center have almost indistinguishable variance. Both predictions are
borne out empirically:

| | Fraction of trials where the trial's true worst code is exactly 256 |
|---|---|
| DNL | 48.6 % |
| INL | 0.08 % (INL's argmax scatters across a wide band of central codes, per the flat-parabola prediction above) |

Taking the **actual per-trial maximum over all codes** therefore gives a
statistic that is a maximum of several near-degenerate, correlated
Gaussians — an extreme-value-type distribution, not itself Gaussian. This is
directly confirmed:

| Quantity | Shapiro-Wilk W | Shapiro-Wilk p |
|---|---|---|
| max\|DNL\| over all codes | 0.9628 | 5.2×10⁻³⁴ |
| max\|INL\| over all codes | 0.8969 | 1.0×10⁻⁴⁹ |

Both p-values overwhelmingly **reject** normality — exactly the "goodness-of-fit
check flagged if sampled distribution deviates from assumed shape in the
extrapolated tail region" this issue's test plan requires as an edge case.
**This memo does not extrapolate a Gaussian tail through the max-over-codes
statistic for that reason.** It is reported only as an empirical, no-fit
bound: at `N = 5000`, the empirical 3σ (`3×` sample σ, not extrapolated) of
max\|DNL\| is 0.577 LSB and of max\|INL\| is 0.409 LSB, and the single
worst trial observed reaches 0.634 LSB (DNL) / 0.360 LSB (INL) — all
consistent with, and slightly more conservative than, the code-256 figures
in §2.5, as expected from an order statistic over near-equal-variance
candidates.

### 2.7 Yield vs #8's ratified/aspirational lines, at #8's 3σ criterion

Using the Gaussian fit at code 256 (§2.5), analytically, at the chosen
design's `σ_u = 0.7372 %`:

| Target (from `README.md#target-specification` / `spec/cdac-sizing-memo.md`) | Bound | σ at spec (`spec/σ_measured`) | Meets 3σ? | Analytic yield (two-sided) |
|---|---|---|---|---|
| **< 1 LSB, baseline (ratified)** | DNL | 5.96σ | **YES** | > 0.999999997 |
| **< 1 LSB, baseline (ratified)** | INL | 11.9σ | **YES** | ≈ 1.0 |
| < 0.5 LSB, stretch (aspirational) | DNL | 2.98σ | **essentially at the line** (see caveat below) | 0.9971 |
| < 0.5 LSB, stretch (aspirational) | INL | 5.98σ | **YES** | > 0.999999997 |

**Overall: PASS against the ratified baseline (< 1 LSB), with ~6σ / ~12σ
margin on DNL/INL respectively.** DNL, not INL, is the binding constraint,
exactly as `spec/cdac-sizing-memo.md` §3.5 predicts.

**Honest caveat on the stretch target, not smoothed over.** `2.98σ` is
formally just short of the `3.0σ` line — but `spec/cdac-sizing-memo.md` §4
already states the chosen unit cap was sized by *inverting* the 3σ
condition against the stretch target exactly, i.e. **by design this
figure has ~zero margin**, not a comfortable one. This Monte Carlo's own
statistical precision at `N = 5000` (`1/√(2N) ≈ 1.0 %` on the sigma
estimate) is larger than the 0.7 % shortfall observed (2.98 vs 3.00), so
the correct reading is **statistically indistinguishable from exactly
meeting the stretch line**, not a real shortfall — confirmed by the
`N = 20000` cross-check (§2.4), which lands at 2.989σ, closer still to 3.0.
The stretch target is explicitly aspirational in this repo's own language
("< 0.5 LSB **stretch**"), not the ratified row the block must meet; the
ratified row (< 1 LSB) clears with wide, unambiguous margin. This is stated
plainly rather than rounded up to a clean PASS, per CLAUDE.md's rule against
relaxing a claim to make it look better than it measured.

### 2.8 Seed handling

`numpy.random.default_rng(seed)` (PCG64), `seed = 20260801`, `N = 5000`
trials (also cross-checked at `N = 20000`, same seed — see §2.4/§2.6).
Fully reproducible: `python3 sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py
--sigma-u 0.7372097807744856 --trials 5000 --seed 20260801`. This is an
independent RNG from any ngspice `setseed` used elsewhere in `sim/` — no
shared-state hazard, since this script never invokes ngspice.

### 2.9 Evidence record

`sim/mc-cdac-mismatch/records/20260801-093800-c033611.md` — see that record
for the full per-quantity table, links to the raw per-trial CSV
(`sim/mc-cdac-mismatch/runs/20260801-093800-c033611/trials_n5000.csv`,
`trials_n20000.csv`) and full summary JSON, and the "Netlist provenance:
behavioral" statement this memo's §2.1 explains.

---

## 3. Comparator offset → effective-offset distribution

### 3.1 What is reused, and what is new (stated explicitly, per the issue's design guidance)

**Reused as-is, not re-derived:** `sim/comparator-offset-mc/` (#9, closed
via PR #45) already measured the preamplifier's input-referred offset
Monte Carlo — `N = 150` mismatch draws per PVT point, `setseed 20260801`,
common random numbers across the grid, 38 of 45 points completed (7 lost to
host OOM, recorded as `ERROR` rows, not omitted). Its own figures:

| | Value |
|---|---|
| σ(V_os), across the 38 completed points | 1.17926 – 1.19477 mV (1.30 % spread) |
| 3σ, in `LSB_se` | 1.09777 – 1.11221 (1.30 % spread) |
| Code-correlated (common-mode-dependent) term | 0.19 µV / 0.00006 LSB — "no measurable code-correlated offset" |

None of this is re-derived here. It is cited, and `spec/comparator-budget-memo.md`
§3.3 already **combines** it with the StrongARM latch's own
gain-divided contribution (a *derived*, not measured, term — the latch has
no DC operating point for a `.noise`/DC-sweep method to reach) to the total
comparator offset the ratified spec line actually bounds:

```
σ_os,total (worst corner, ff_125c_3.63v) = sqrt(1.195² + 0.450²) mV = 1.277 mV
3σ_os,total                              = 3.83 mV = 1.19 LSB
Ratified row                             = 2 LSB
Margin                                   = 0.81 LSB (41 % of the row unspent)
```

**This total (1.19 LSB at 3σ, 0.81 LSB / 41 % margin) is the number #16
needs for its floorplan symmetry decision** — stated here explicitly, in
the units and against the exact reference (2 LSB row) #16 must consume
directly, so #16 does not have to re-derive it from §3.3 of a different
memo.

### 3.2 What is new: the goodness-of-fit check (`sim/comparator-offset-gof/`)

`sim/comparator-offset-mc/`'s manifest accumulates only running statistical
sums (`sva`, `svaq`, ...) inside its Monte Carlo loop — its records report
σ(V_os) per PVT point but never the raw per-draw population, so there is
nothing in its existing logs a normality check can run against. This
issue's AC1 requires a goodness-of-fit check before the offset distribution
is used to extrapolate a 3σ yield claim, so a small, **new**, separate
experiment (`sim/comparator-offset-gof/`) reruns the *same* measurement
(same preamp, same two-point DC-sweep method,
`design/comparator/comparator.spice`'s canonical netlist, kept in sync by
`sim/tools/sync_comparator_netlist.py` like every other comparator
testbench) but `print`s every draw's offset to the run's own log.

**Deliberately narrower scope than #9's campaign** (this is a shape check,
not a new sigma claim, so it does not need #9's full grid):

- **One PVT point** (nominal, `tt_27c_3.30v`) — #9 already measured < 1.3 %
  corner spread (`par_vth` lives in the PDK's `fets_mm` subckt, not any
  corner `.lib` section, so it is corner-invariant by construction).
- **One common mode** (`V_cm = 1.65 V`) — the code-correlated question is
  already closed (§3.1's 0.19 µV figure), not re-opened here.
- **N = 300** draws, same `setseed 20260801` mechanism as #9 and
  `sim/device-mismatch-mc/`.

**Result** (record: `sim/comparator-offset-gof/records/20260801-093644-c033611.md`;
goodness-of-fit statistics computed by `sim/comparator-offset-gof/testbench/analyze_gof.py`
from the raw printed samples in
`sim/comparator-offset-gof/corners/20260801-093644-c033611/tt_27c_3.30v.log`,
saved to `tt_27c_3.30v.gof.json` alongside that log):

| Quantity | Value |
|---|---|
| σ(V_os), this record's own ngspice running-sum measure (`sig_vos_mv`, nominal point, consistency check against #9's 1.18934–1.19477 mV) | 1.18934 mV |
| σ(V_os), recomputed from the raw printed per-draw samples (`analyze_gof.py`, independent draw sequence, single-V_cm circuit — the population the goodness-of-fit check below actually runs against) | 1.1913 mV |
| Shapiro-Wilk W / p | 0.9936 / 0.230 |
| Anderson-Darling statistic / 5 % critical value | 0.391 / 0.750 (does not reject normality) |

(The two σ(V_os) estimators differ in the 4th significant figure — ngspice's
`sqrt(svaq/nmax - (sva/nmax)^2)` running-sum accumulates over full-precision
internal values, while `analyze_gof.py` recomputes from the `print voa`
lines' limited output precision; both read the same underlying population
and the discrepancy is precision noise, not a second measurement.)

Neither test gives any reason to reject the Gaussian assumption
`spec/comparator-budget-memo.md` §3.3's quadrature combination and this
memo's 3σ arithmetic both rest on. **This is the goodness-of-fit check
AC1 requires for the comparator offset claim.**

### 3.3 Model, per `spec/comparator-budget-memo.md` §9

Per the budget memo's own summary for #14: model comparator offset as a
**per-instance constant** (σ = 1.277 mV input-referred, corner-invariant in
this PDK, dominated by the preamp input pair's threshold mismatch), **plus
zero code-correlated component** (measured, §3.1) — not as zero-mean
per-trial noise. Tier 0 assumes the constant is removed digitally; nothing
in this memo's Monte Carlo work changes that model, it only adds the
goodness-of-fit evidence that the constant's *distribution across
instances* is the Gaussian the 3σ arithmetic assumes.

### 3.4 Scope note: single-ended mode

Per the issue's design guidance, stated explicitly: this memo's offset work
covers the **differential** mode DR-0006/DR-0007 fix as the primary case
(constant common mode, tier-0 admissible per §3.1). Single-ended mode's
common-mode excursion (`residue/2`, up to ±0.825 V at the free-MSB decision)
is a **different, still-live case** — `sim/comparator-offset-mc/`'s
code-correlated measurement (§3.1) was taken over a ±50 mV band specifically
because that is ~5× the late-trial single-ended excursion, so the
"no measurable code-correlated offset" finding is informative for
single-ended mode too, but this memo does not re-run the full single-ended
early-trial excursion (residue/2 at the free-MSB decision itself, ±0.825 V)
as a distinct Monte Carlo campaign. That remains open if single-ended mode
becomes the shipped configuration.

---

## 4. Division of labor with #13

`sim/README.md`'s directory convention and #13's own testbench suite verify
the **nominal** design's transfer function against the full PVT corner
matrix (process/temperature/supply) — the question "does this exact,
nominal design meet spec across environmental conditions?" This issue
verifies a different question: "given that nominal design, how much does
device-to-device **mismatch** (not environmental corner) spread the same
figures?" The two are complementary, not overlapping: #13's corner sweep
holds mismatch off (`sw_stat_mismatch = 0`, the harness default) and moves
PVT; this issue's Monte Carlo (both parts) holds PVT at nominal and moves
mismatch. Neither record substitutes for the other, and — per
`sim/cdac-bit-settling/` §5.3's independent finding — global process
variation cancels exactly in the charge-division ratio DNL/INL depend on,
which is the quantitative reason a nominal-PVT-only mismatch sweep is a
valid substitute for a full mismatch-at-every-corner campaign here, not
merely a convenient shortcut.

---

## 5. Known limitations carried forward

1. **The CDAC model is behavioral, calibrated to a literature-derated
   Pelgrom coefficient** (`A_C = 2.0 %·µm`, 2× derated,
   `sim/device-characterization-report.md` §5.1), not measured directly —
   because the PDK has nothing to measure it against. A foundry MiM
   matching dataset replacing that assumption should re-run
   `sim/mc-cdac-mismatch/`.
2. **The stretch (< 0.5 LSB) DNL yield sits at the design's own zero-margin
   boundary** (§2.7) — not a defect in this memo's arithmetic, but a
   property of `spec/cdac-sizing-memo.md`'s sizing choice worth flagging for
   any future retargeting of the stretch goal.
3. **This memo's two new tools require `numpy`+`scipy`**, a real (stated,
   not silent) divergence from the rest of `sim/`'s stdlib-only harness
   (§2.1). Neither tool is invoked by `sim/run_corners.py` or CI.
4. **Comparator offset's latch contribution remains a derived, not
   measured, term** (`spec/comparator-budget-memo.md` §3.3/§8.1) — this
   memo's goodness-of-fit check is against the **measured preamp** term
   only; the combined total's distribution shape (preamp ⊕ latch in
   quadrature) inherits the preamp's confirmed-Gaussian shape and the
   latch's much smaller, bound-only contribution, but has not itself been
   independently fit.
5. **Single-ended mode's early-trial common-mode excursion is not covered**
   by a dedicated Monte Carlo campaign (§3.4) — open if single-ended
   becomes the shipped mode.
6. **Every number here is schematic-level / pre-layout.** Post-layout
   extraction (#17) is a required re-run for both records, per the same
   caveat every other pre-layout record in this repo carries.
