# Comparator offset / noise / metastability budget memo

**Status**: design memo, supporting DR-0007. Not a decision record (see
`spec/decision-records/README.md` — this is derivation and evidence, cited
*from* a decision record, not itself one).
**Issue**: #9. **Consumes**: `README.md#target-specification` (ratified, DR-0006-spec-ratification)
and its notes **[b]**, **[d]**, **[e]**; DR-0006-cdac-switching-scheme;
`spec/cdac-sizing-memo.md` §1.2; `sim/device-characterization-report.md` §3;
`spec/prior-art-survey.md` §1.1, §1.4, §3.
**Feeds**: #12 (regeneration margin, §6; power, §7), #13 (noise-verification
methodology and its cost, §8), #14 (offset distribution, §3), #16 (symmetry
requirement, §9).

Every number below is either derived from a ratified spec line or measured by a
committed testbench. Where a number is neither — the latch's own noise term is
the one such case — it is labelled as a bound with its assumptions written out
(§5.3), because this repo's rule is that a claim without a testbench is not a
claim.

---

## 0. Topology recap and what this memo does not decide

DR-0007 fixes the topology this memo budgets: **static differential
preamplifier → StrongARM latch → NAND SR output latch**, NMOS input pair,
offset-cancellation **tier 0** (none + digital offset removal), noise closed by
`.noise` on the preamplifier. The netlist is
`design/comparator/comparator.spice`; this memo derives the sizing in it and
checks the result against the ratified spec.

Two facts from DR-0006 (CDAC switching) are load-bearing throughout and are
*consumed*, not re-decided:

- `LSB_se = V_REF/1024 = 3.2227 mV`, `LSB_diff = 2·V_REF/1024 = 6.4453 mV`.
  Single-ended is the binding (smaller-LSB) case, so **every budget below is
  stated in `LSB_se`** and is met with 2× more room differentially.
- The comparator's input common mode is **constant at `V_cm = 1.65 V`** in
  differential mode, and moves by `residue/2` in single-ended mode — up to
  ±0.825 V at the free-MSB decision, halving at every trial, i.e. a few
  millivolts by the accuracy-critical late trials. This is the precondition for
  tier 0 (§4).

---

## 1. The shared budget, and why the comparator's share is not this memo's to pick

`README.md` note **[b]** — part of the ratified spec, not a working assumption —
splits the non-quantization error budget into **three equal-power shares**:
sampling `kT/C`, comparator, and reference + distortion.
`spec/cdac-sizing-memo.md` §1.2 already sized the CDAC against its third. The
comparator therefore takes:

| Target | `σ_total` (all terms) | **Comparator share (1/3 power)** |
|---|---|---|
| ENOB > 9.0 (ratified) | 1.6113 mV rms | **0.930 mV rms** |
| ENOB > 9.5 (stretch) | 0.930 mV rms | **0.537 mV rms** |

Two consequences worth stating explicitly, because both are places a budget
memo can quietly cheat:

- **This is not an independent choice.** The survey (§1.1) *suggested* an equal
  three-way split; the ratified spec's note [b] *fixed* it; #8 *took* its third.
  Had this memo picked a different split, #8's array would be sized against a
  budget that no longer exists. The one-third share is inherited, and the
  arithmetic above is reproducible from note [b] alone.
- **The shares add in power, not in amplitude.** Three terms at exactly their
  allocation give `√3 × 0.537 = 0.930 mV rms` total, which is the stretch
  budget — so meeting the allocation is sufficient, not merely necessary.

---

## 2. Noise allocation vs. measurement

**Allocation: ≤ 0.537 mV rms input-referred (stretch), ≤ 0.930 mV rms
(ratified target).**

**Measured**: `sim/comparator-preamp-noise/` — total integrated output noise
(1 Hz … 1 GHz) divided by the measured DC gain, at all 45 PVT points.

| | Nominal (`tt_27c_3.30v`) | Worst over the 45-point grid |
|---|---|---|
| Input-referred noise `σ_comp` | **104.5 µV rms** | **{{VN_MAX}} µV rms** ({{VN_MAX_CORNER}}) |
| Fraction of the stretch allocation (power) | 3.8 % | {{VN_MAX_FRAC}} % |
| Margin to the stretch allocation (amplitude) | 5.1× | {{VN_MAX_MARGIN}}× |

The comparator therefore spends **well under a tenth of its allocated noise
power** even at the worst corner. That is a large margin, and it is not
accidental: the preamplifier's 150 kΩ resistive loads and 10 µA tail were
chosen for gain and offset (§3), and the resulting noise bandwidth
({{ENBW_NOM}} MHz nominal) is set by the same load resistance working into the
latch's input capacitance.

Three things this measurement does *not* say, all recorded on the record
itself:

- **`fnoicor` is at the PDK default (0, as-extracted).**
  `sim/device-characterization-report.md` §3.4 measured the worst-case flicker
  setting to raise flicker noise **power** by ~11×. The record reports the
  flicker fraction of the total ({{FLICKER_NOM}} % nominal), so the worst-case
  number is `σ·√(1 + 10·f_flicker)` — {{VN_FNOICOR}} µV rms at nominal, still
  far inside the allocation. Flicker at this level is in any case *correlated*
  across the ten bit trials of one 1 µs conversion, so it behaves as a slowly
  drifting offset rather than as per-decision noise, and the offset budget (§3)
  is the one that absorbs it.
- **It is a schematic-level number.** Post-layout extraction (#17) adds
  capacitance at the preamp output, which *lowers* the noise bandwidth and
  therefore this figure. Conservative in the right direction.
- **It excludes the latch's own noise**, which no ngspice analysis can measure.
  See §5.3 for the bound and §8 for why no analysis can.

### 2.1 The units trap this measurement walked into

ngspice reports `onoise_total` / `inoise_total` as **rms volts**, not as noise
power. An earlier draft of the noise manifest took their square root and
reported 21.8 mV rms of comparator noise — 200× the true value, 40× over the
budget ceiling, and syntactically unremarkable. It was caught by an independent
check against an ideal 1 kΩ resistor (4.0693 nV/√Hz over 1 Hz…1 GHz must give
`4.0693e-9 × √1e9 = 128.68 µV`, and ngspice returns exactly `1.2868e-4`).

The related trap, also live: ngspice's **input-referred** integral does not
converge for this circuit. Above the preamp's bandwidth the signal gain rolls
off while the input-referred density does not, so the answer depends on the
upper limit — 474 µV to 1 GHz, 643 µV to 10 GHz, 662 µV to 100 GHz, all for the
same circuit. A comparator *samples* its preamp output at the decision instant,
so the physical quantity is the total integrated **output** noise referred back
by the DC gain, which converges (0.8 % from 1 GHz to 100 GHz). Both traps are
recorded in the testbench manifest so the next reader does not re-enter them.

---

## 3. Offset budget

**Ratified requirement**: `README.md#target-specification` — offset error
**≤ 2 LSB, untrimmed**, at **3σ mismatch**, "no analog trim, digitally
removable" (note **[e]**). In single-ended units: `2 × 3.2227 mV = 6.445 mV` at
3σ, i.e. **σ_os ≤ 2.148 mV** input-referred.

### 3.1 Why the input pair is 40/1 µm and not 40/0.5 µm

`sim/device-characterization-report.md` §3.3 measured
`A_Vt = 7.208 mV·µm` (pair convention) and requires **effective** area
(`L_eff = L − 0.15 µm`, `W_eff = W + 0.1 µm`). For the survey's candidate
40/0.5 µm geometry:

```
sqrt(W_eff·L_eff) = sqrt(40.1 × 0.35) = 3.746 µm
σ(ΔV_th)         = 7.208 / 3.746      = 1.92 mV      → 3σ = 5.77 mV = 1.79 LSB
```

which is the number §3.3 itself quotes, and it consumes **90 % of the whole
2 LSB allowance with the input pair alone**. Lengthening to `L = 1 µm`:

```
sqrt(W_eff·L_eff) = sqrt(40.1 × 0.85) = 5.838 µm
σ(ΔV_th)         = 7.208 / 5.838      = 1.235 mV     → 3σ = 3.70 mV = 1.15 LSB
```

Area, not width, is what buys matching (§3.3's own warning), and the length is
where it is cheapest to buy: the preamp's speed is irrelevant against a 62.5 ns
bit cycle (§6), while `W` is already large enough that the input capacitance —
which is kickback (§5) and CDAC settling load — should not grow further.

### 3.2 Measured preamp offset

`sim/comparator-offset-mc/` — {{MC_N}} mismatch draws per PVT point, all 45
points, `sw_stat_mismatch = 1`, `sw_stat_global = 0`, common random numbers
across the grid.

| | Value |
|---|---|
| σ(V_os), nominal | **{{SIG_VOS_NOM}} mV** |
| σ(V_os), worst corner | **{{SIG_VOS_MAX}} mV** ({{SIG_VOS_MAX_CORNER}}) |
| 3σ, worst corner | {{VOS3_MAX}} mV = **{{VOS3_MAX_LSB}} LSB** |
| `A_Vt` back-extracted from it | {{AVT_BACK}} mV·µm (vs 7.208 measured standalone) |
| Corner spread of σ (process axis) | {{SIG_VOS_SPREAD}} % |

The back-extracted `A_Vt` lands **at or above** the standalone threshold-only
coefficient, which is the expected direction: the preamp pair runs in moderate
inversion, so its offset carries current-factor (β) mismatch on top of
threshold mismatch, whereas `sim/device-mismatch-mc/` deliberately biased in
deep subthreshold to isolate the threshold term. A value *below* 7.208 would
have meant offset was being under-counted somewhere.

The near-corner-invariance of σ is also expected and asserted as a ceiling
rather than merely observed: `par_vth` lives in the PDK's `fets_mm` subckt, not
in any corner `.lib` section, so the dominant term cannot move with process by
construction (`devchar` §3.3).

### 3.3 The latch's contribution, and the total

The StrongARM latch's own offset (input pair 8/0.5 µm plus its load and
regeneration-node mismatch) is referred to the comparator input **divided by
the preamp gain** `A_v`, measured at **{{AV_NOM}}** nominal and **{{AV_MIN}}**
at the worst corner (`sim/comparator-offset/`, {{AV_MIN_CORNER}}). Taking the
latch input pair alone at the same `A_Vt`:

```
sqrt(W_eff·L_eff) = sqrt(8.1 × 0.35) = 1.684 µm
σ(ΔV_th)_latch    = 7.208 / 1.684    = 4.28 mV  (at the latch input)
referred to the comparator input, worst-corner gain: 4.28 / {{AV_MIN}} = {{VOS_LATCH_IN}} mV
```

Combining in quadrature with the measured preamp term at the worst corner:

```
σ_os,total = sqrt({{SIG_VOS_MAX}}² + {{VOS_LATCH_IN}}²) = {{SIG_TOT}} mV
3σ         = {{VOS3_TOT}} mV = {{VOS3_TOT_LSB}} LSB   vs the ratified 2 LSB
```

**Margin to the ratified row: {{OS_MARGIN}}.**

The latch term is a *derived* number, not a measured one: it uses the same
measured `A_Vt` and the measured worst-corner gain, but it does not include the
latch's load/regeneration mismatch or its dynamic (timing-dependent) offset
component. Two things bound the error that introduces:

- The latch's additional terms enter the same way — divided by `A_v` — so
  doubling the assumed latch offset to 8.6 mV would move the total from
  {{VOS3_TOT_LSB}} LSB to {{VOS3_TOT_2X_LSB}} LSB, still inside the ratified
  row. The conclusion is not sensitive to the assumption at the factor-of-two
  level.
- `sim/comparator-regeneration/` measures the *mismatch-free* decision at
  ±0.5 LSB and gets the correct polarity at all 45 points, which is the null
  control: any systematic (non-mismatch) latch offset above half an LSB
  referred to the input would have shown up there as a wrong decision.

### 3.4 What is NOT in the offset number

- **Load-resistor mismatch.** This PDK models none: gf180mcu wires
  `*(1+mis_r*sw_stat_mismatch)` into every resistor subckt and then hard-sets
  `mis_r = 0`. `sim/comparator-offset-mc/` carries a two-resistor null control
  that measures exactly 0 to prove this is a model gap and not a deck error.
  A real 150 kΩ poly pair would contribute; with the preamp's `gm·R` structure,
  a fractional load mismatch `δ` contributes `δ·V_ov/2` to the input-referred
  offset, so a 0.5 % load mismatch at the measured overdrive would add roughly
  0.5 mV — **comparable to the input pair's own term.** This is the largest
  un-modelled term in the budget, it is the direct reason the load resistors
  need common-centroid layout (§9, #16), and it is why the margin in §3.3 is
  reported rather than spent.
- **Layout-induced systematic asymmetry**, which is #16's to control and #17's
  to verify.
- **Flicker-induced drift** between the calibration that measures the offset and
  the conversion that subtracts it. §2's flicker fraction bounds it.

---

## 4. Offset-cancellation tier, starting at tier 0

`spec/prior-art-survey.md` §3.4 ranks eight cancellation options by cost and
instructs picking the **lowest** row that meets the requirement. Working up
from the bottom:

**Tier 0 — none + digital offset removal.** Admissible only if (a) the offset
is *static within a conversion*, and (b) the residual fits the ratified row.

- (a) is **satisfied by DR-0006, not assumed**: MCS/Vcm switching holds the
  comparator's input common mode constant in differential mode, so the offset
  cannot vary from trial to trial. In single-ended mode the common mode moves
  by `residue/2` — so the requirement becomes "offset must be stable over the
  *late-trial* common-mode excursion", which is a few millivolts.
  `sim/comparator-offset-mc/` measures the code-correlated term directly: the
  1σ change in offset over a **±50 mV** common-mode band — about 5× wider than
  the late trials ever see — is **{{DVOS}} µV**, i.e. {{DVOS_LSB}} LSB. There
  is no measurable code-correlated offset.
- (b) is **satisfied by §3.3**: {{VOS3_TOT_LSB}} LSB at 3σ against a 2 LSB row.

**Tier 0 is therefore selected.** Cost: zero area, zero power, zero clock
phases; the price is that the digital readback path must subtract a stored
constant, which the ratified spec already anticipates ("digitally removable",
note [e]).

**Tier 1 — input-pair upsizing** is already partially spent: §3.1's move from
`L = 0.5 µm` to `L = 1 µm` *is* a tier-1 action, taken because it was cheaper
than any cancellation scheme. Further upsizing has diminishing returns
(`1/√area`) and grows the input capacitance that kickback and CDAC settling
pay for.

**Tier 2 — capacitive latch-load trim** (the survey's recommended escalation,
with a sky130 12-bit open-source precedent) is **not taken, and is named as the
fallback**. It would cost a calibration FSM, a trim register and a foreground
calibration mode — new scope for #11 — to buy margin the measurement says is
not needed. The escalation criteria, stated in advance so the decision is
falsifiable:

1. post-layout extraction (#17) or a foundry mismatch dataset pushes measured
   3σ offset above 2 LSB; **or**
2. the load-mismatch term of §3.4 turns out, once modelled or measured, to be
   large enough to do so; **or**
3. a superseding record changes the switching scheme to one whose common mode
   moves within a conversion (DR-0006's monotonic alternative), which would
   make cancellation mandatory rather than optional.

**Tiers 3+ (body-bias trim, current-DAC injection, auto-zero, chopping)** are
not reached for. Each costs static power, a clock phase, or auxiliary
capacitance hung on the CDAC top plate — the one node this design most needs
left alone (§5) — and tier 6 (chopping) is directly incompatible with the
2 MS/s stretch. Reaching for one of these before showing tier 0/2 insufficient
is precisely what the survey's ordering exists to prevent.

---

## 5. Kickback into the CDAC top plate

### 5.1 Why it is a first-class term here

DR-0006 ratifies **top-plate sampling**, so the comparator's input *is* the
CDAC top plate: a floating node of `C_side ≈ 8.83 pF` per side
(`spec/cdac-sizing-memo.md` §6) holding the residue for every remaining bit
trial. Charge injected there has nowhere to go before the next decision — it is
added to the quantity being converted. `spec/prior-art-survey.md` §3.6 notes
that at 3.3 V the regeneration swing makes kickback **2.75×** a 1.2 V design's
for the same devices, and §3.7 names it the primary risk to retire.

### 5.2 Measured

`sim/comparator-kickback/` drives two comparator instances from *floating*
8.83 pF top plates (biased through 1 GΩ, i.e. an 8.8 ms time constant against a
62.5 ns bit cycle, so the bias network observes rather than restores) at a
half-LSB residue and at a 100 mV residue.

| Quantity | Nominal | Worst over 45 points | In LSB_se |
|---|---|---|---|
| Residual **differential** kick, half-LSB residue | {{KICK_DIFF_NOM}} µV | {{KICK_DIFF_MAX}} µV | {{KICK_DIFF_MAX_LSB}} |
| Residual **common-mode** kick | {{KICK_CM_NOM}} µV | {{KICK_CM_MAX}} µV | — |
| **Signal-dependent** part (100 mV vs half-LSB) | {{KICK_SD_NOM}} µV | {{KICK_SD_MAX}} µV | **{{KICK_SD_MAX_LSB}}** |
| Peak transient excursion during the decide phase | {{KICK_PEAK_NOM}} µV | {{KICK_PEAK_MAX}} µV | — |

**The signal-dependent part is the linearity term.** Per survey §3.1, a
kickback that is identical at every code is indistinguishable from comparator
offset and is removed by the same digital subtraction (§4); only the part that
varies with the residue is an INL/DNL error. At {{KICK_SD_MAX_LSB}} LSB it is
{{KICK_SD_VS_DNL}} of the < 0.5 LSB stretch DNL target.

This is the measured consequence of the DR-0007 topology choice: the static
preamplifier is a unidirectional buffer between the CDAC top plate and the
regenerating nodes, so the 3.3 V latch swing never reaches the top plate
through an input pair's `C_gd`. The number is evidence for that choice, not an
assertion of it.

Two honest limitations, both on the record:

- **Numerical floor.** ngspice's default voltage tolerance (1 µV) is *coarser*
  than the effect: at defaults the deck reports differential kicks of exactly
  −1, 0 or +1 µV — the solver's granularity, not the circuit's. The record is
  taken with `vntol = 1 nV`, `reltol = 1e-4`, three decades below the reported
  values.
- **No parasitics.** Post-layout extraction adds input capacitance and coupling,
  which moves kickback in the **wrong** direction (unlike noise, §2). A
  post-layout re-run of this deck is a required check for #17, not a formality.

---

## 6. Metastability and regeneration margin

**Budget**: `spec/prior-art-survey.md` §1.4 and DR-0003 allocate a **62.5 ns**
bit cycle at 1 MS/s (16× clock), of which the decide phase is **31.25 ns** at
50 % duty; the 2 MS/s stretch halves both to 31.25 ns / **15.625 ns**.

**Measured** (`sim/comparator-regeneration/`, all 45 points, decision delay from
the clock's 50 % point to the output's 50 % point, both supply-normalized so the
±10 % supply axis cannot become a measurement artefact):

| | Nominal | Worst over 45 points |
|---|---|---|
| Decision delay at **half an LSB** overdrive | {{TD_HALF_NOM}} ps | **{{TD_HALF_MAX}} ps** ({{TD_HALF_MAX_CORNER}}) |
| Decision delay at 100 mV | {{TD_BIG_NOM}} ps | {{TD_BIG_MAX}} ps |
| Regeneration time constant `τ` (extracted) | {{TAU_NOM}} ps | {{TAU_MAX}} ps |
| Margin against the 31.25 ns decide phase | {{MARGIN_NOM}} ns | **{{MARGIN_MIN}} ns** |

`τ` is extracted, not assumed, from the two measured overdrives:
`τ = (t(0.5 LSB) − t(100 mV)) / ln(100 mV / 1.6113 mV)`.

**Metastability.** A latch resolves an input `V_in` in
`t = t₀ + τ·ln(V_logic/(A_v·V_in))`, so in the time left after the half-LSB
decision the comparator could still resolve an input
`10^{{DECADES_MIN}}` times smaller — {{DECADES_MIN}} decades of headroom at the
worst corner. Stated as an error probability: a decision is unresolved at the
end of the decide phase only if the residue falls within
`0.5 LSB × 10^-{{DECADES_MIN}}` of the decision point, which for a uniformly
distributed residue is a probability of order `10^-{{DECADES_MIN}}` per trial —
below any rate that matters at 10 bits, and below the numerical floor of the
simulation that measured it.

**The conclusion is that comparator regeneration is not a term in #12's timing
budget at either the ratified rate or the stretch.** That is the same
conclusion the survey reached from literature (`[E4]`, typical corner); the
difference is that it is now measured at slow/cold/low-supply, which is what the
issue's acceptance criterion asked for.

---

## 7. Power

| Term | Measured | At 1 MS/s |
|---|---|---|
| Static (mirror diode branch + tail, ~20 µA) | {{ISTAT_NOM}} µA nominal, {{ISTAT_MAX}} µA worst | **{{PSTAT_NOM}} µW** nominal, {{PSTAT_MAX}} µW at `ff_125c_3.63v` |
| Dynamic, per decision | {{EDEC_NOM}} fJ nominal, {{EDEC_MAX}} fJ worst | {{PDYN_NOM}} µW (11 decisions/conversion) |
| **Total** | | **{{PTOT_NOM}} µW** nominal, {{PTOT_MAX}} µW worst |

Against the ratified **< 1 mW** row that is {{POW_PCT}} %, and against the
**< 500 µW** stretch {{POW_PCT_STRETCH}} %. The binding corner for power is
`ff_125c_3.63v` per the ratified table, and that is the corner quoted.

Two things the table makes explicit rather than hiding:

- **The static term is ~2× the nominal bias current, not 1×.** The 1:1 mirror's
  diode branch sinks the forced 10 µA from the same supply as the mirrored
  tail. `sim/comparator-offset/` measures the *tail branch alone* (33 µW) from
  the load drop and cannot see the bias branch; `sim/comparator-regeneration/`
  measures the block's whole supply current directly, and that is the number
  used here. A budget built on the first measurement would have been optimistic
  by a factor of two.
- **The static term does not scale with sample rate.** At 1 MS/s it dominates;
  the dynamic term is {{PDYN_FRAC}} % of the total. A future low-rate variant
  would gain nothing without power-gating the preamp, which DR-0007 explicitly
  does not design.

---

## 8. Noise-verification methodology — the ngspice decision

The issue's original text asks this to be a *stated decision*, and
`sim/README.md`'s **Noise methodology** field requires it on the record itself.

**Chosen path: `ac-based`** — ngspice `.noise` on the static preamplifier about
a real DC operating point, with the StrongARM latch instantiated in reset so
that its input capacitance loads the preamp, integrated 1 Hz…1 GHz at the
output and referred to the input by the measured DC gain (§2). Cost: **45 PVT
points in about one minute.**

**This path exists only because of DR-0007.** `spec/prior-art-survey.md` §3.5
is explicit: `.noise` is a small-signal analysis about a DC operating point;
StrongARM, double-tail and dynamic-preamp topologies have none, and ngspice has
no PSS/pnoise and injects no device noise into a transient. For any of those,
the only valid path is an explicit `trnoise` source at the input, swept across
±3–4σ in steps below σ, with K independent transient trials per point fitted to
a Gaussian CDF.

**Cost of the path not taken, for #13 and #2.** Resolving σ to ~10 % needs
`K ≈ 10²–10³` trials at each of 10–20 input points — **10³–10⁴ transient runs
per corner**. On this repo's own measured throughput, one comparator transient
over a 62.5 ns bit cycle costs of order 20 s of CPU at the grid's PVT points
(`sim/comparator-regeneration/`: {{REG_SECONDS}} s for a 135 ns, 4-instance
deck). At the low end — 10³ runs per corner × 45 corners × 20 s — that is
**~250 CPU-hours per noise record**, versus about one minute for the `.noise`
path. Even with the multi-strobe amortization a careful implementation would
use (many decisions per transient), it remains three to four orders of
magnitude more expensive.

That ratio is the quantified form of the survey's schedule argument, and it is
**the reason the ~66 µW static preamp is worth its power**: it does not merely
lower the noise, it converts the noise claim from a Monte Carlo campaign into a
deterministic analysis this project can afford to re-run on every change.

**What remains open on this path.** ngspice cannot measure the latch's own
noise by *any* analysis (see §5.3 above and the bound below), so the total
input-referred noise is `σ_preamp` (measured) combined with `σ_latch/A_v`
(bounded). #13 inherits that bound as an assumption, not as a measurement, and
this memo states it as such.

### 8.1 The latch noise bound

The latch's input pair integrates its own thermal noise onto the regeneration
nodes during the integration phase. Bounding it by the `kT/C` noise of those
nodes referred through the integration gain, with the geometry in
`design/comparator/comparator.spice`:

```
C_int      ≈ 30 fF   (cross-coupled gate + drain capacitance, estimated)
σ_node      = sqrt(kT/C_int) = 371 µV per node, sqrt(2)× differential = 525 µV
A_int       = gm_lat·Δt/C_int ≈ 2.2 mA/V × 100 ps / 30 fF ≈ 7.3
σ_latch,in  ≈ 525 µV / 7.3 = 72 µV  (at the LATCH input)
referred to the comparator input, ÷ A_v = {{AV_MIN}}: {{SIG_LATCH_NOISE}} µV
```

Combined in quadrature with the measured worst-corner preamp noise
({{VN_MAX}} µV), the total moves to {{VN_TOT_MAX}} µV rms — a change of
{{VN_TOT_DELTA}} %, and still {{VN_TOT_MARGIN}}× inside the stretch allocation.
`C_int`, `gm_lat` and `Δt` above are **estimates**, not measurements; the
conclusion survives an order of magnitude of pessimism on `σ_latch,in`
(10× would take the total to {{VN_TOT_10X}} µV, still inside the allocation),
which is the property that makes it an acceptable bound rather than a gap.

---

## 9. Summary for downstream issues

- **#12 (timing)**: comparator decision delay is **{{TD_HALF_MAX}} ps worst-case
  at half an LSB**, against a 31.25 ns decide phase — {{MARGIN_MIN}} ns of
  margin at 1 MS/s and {{MARGIN_MIN_2MS}} ns at the 2 MS/s stretch. Do not
  carry the survey's "sub-nanosecond `[E4]`" estimate; use the measured number.
- **#13 (testbench suite)**: the noise methodology is `ac-based` (§8), costing
  ~1 minute per 45-point record. **The `trnoise` Monte Carlo campaign the
  survey budgeted (10³–10⁴ runs/corner, ~250 CPU-hours per record) is NOT
  needed for this topology** — but it returns in full if any record supersedes
  DR-0007 with a dynamic topology. #13 also inherits the §8.1 latch-noise bound
  as a stated assumption.
- **#14 (Monte Carlo)**: model comparator offset as a **per-instance constant**
  with σ = {{SIG_TOT}} mV input-referred (dominated by the preamp input pair's
  threshold mismatch, corner-invariant in this PDK), plus **zero**
  code-correlated component (measured, §4). Do not model it as zero-mean
  per-trial noise; it is an offset, and tier 0 assumes it is removed digitally.
- **#16 (floorplan)**: the two preamp branches — **including the 150 kΩ load
  resistors, not just the input pair** — need common-centroid treatment.
  Numerically: 0.4 mV of layout-induced systematic asymmetry costs as much
  budget as a 10 % increase in `A_Vt`, and the PDK models **no** resistor
  mismatch at all (§3.4), so layout is the only place that term can be
  controlled or even seen. The comparator's input is the CDAC top plate, so the
  kickback path (§5) is also a floorplan constraint: keep the latch's
  regeneration nodes away from top-plate routing.
- **#11 (SAR logic)**: the comparator presents a held level, not a pulse (NAND
  SR output latch), and needs one clock phase. The digital path must subtract a
  stored offset constant (tier 0, §4).
- **Open interface item**: the 10 µA `ibias` pin needs a source. Whether it is
  generated on-chip or supplied externally is not decided by DR-0007 and should
  be raised alongside DR-0006's identical open question about the `V_cm` rail.

---

## 10. Known limitations carried forward

1. **The latch's noise is bounded, not measured** (§8.1) — a limitation of
   ngspice, not of the testbench, and it applies to every comparator in this
   flow regardless of topology.
2. **Load-resistor mismatch is not modelled by this PDK** (§3.4) and is the
   largest un-modelled term in the offset budget. It is the reason the offset
   margin is reported rather than spent.
3. **Every number here is schematic-level.** Extraction (#17) moves noise the
   safe way and kickback the unsafe way (§5.2).
4. **The bias current is ideal in every deck.** A real bias generator's own
   noise and mismatch are not in this budget; the `ibias` pin is a contract.
5. **`fnoicor = 0`** (as-extracted flicker) throughout, with the worst-case
   rescaling given in §2 rather than re-run.
