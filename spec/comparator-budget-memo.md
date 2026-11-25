# Comparator offset / noise / metastability budget memo

**Status**: design memo, supporting DR-0015. Not a decision record (see
`spec/decision-records/README.md` — this is derivation and evidence, cited
*from* a decision record, not itself one).
**Issue**: #9. **Consumes**: `README.md#target-specification` (ratified, DR-0006-spec-ratification)
and its notes **[b]**, **[d]**, **[e]**; DR-0014-bottom-plate-sampling;
`spec/cdac-sizing-memo.md` §1.2; `sim/device-characterization-report.md` §3;
`spec/prior-art-survey.md` §1.1, §1.4, §3.
**Feeds**: #12 (regeneration margin, §6; power, §7), #13 (noise-verification
methodology and its cost, §8), #14 (offset distribution, §3), #16 (symmetry
requirement, §9).

Every number below is either derived from a ratified spec line or measured by a
committed testbench. Where a number is neither — the latch's own noise term is
the one such case — it is labelled as a bound with its assumptions written out
(§8.1), because this repo's rule is that a claim without a testbench is not a
claim.

---

## 0. Topology recap and what this memo does not decide

DR-0015 fixes the topology this memo budgets: **static differential
preamplifier → StrongARM latch → isolation inverters → NOR SR output latch**, NMOS input pair,
offset-cancellation **tier 0** (none + digital offset removal), noise closed by
`.noise` on the preamplifier. The netlist is
`design/comparator/comparator.spice`; this memo derives the sizing in it and
checks the result against the ratified spec. The isolation inverters between
the latch and the SR output stage are not cosmetic: without them the comparator
measures ~10 mV of hysteresis between successive decisions, which is a
code-dependent error digital offset removal cannot remove (DR-0015, Decision).

Two facts from DR-0014 (CDAC switching) are load-bearing throughout and are
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
| Input-referred noise `σ_comp` | **104.5 µV rms** | **153.2 µV rms** (`ff_125c_3.63v`) |
| Fraction of the stretch allocation (power) | 3.8 % | 8.1 % |
| Margin to the stretch allocation (amplitude) | 5.1× | 3.5× |

The comparator therefore spends **well under a tenth of its allocated noise
power** even at the worst corner. That is a large margin, and it is not
accidental: the preamplifier's 150 kΩ resistive loads and 10 µA tail were
chosen for gain and offset (§3), and the resulting noise bandwidth
(40 MHz nominal) is set by the same load resistance working into the
latch's input capacitance.

The record's `enbw_mhz` column is a **derived consistency identity, not an
independent cross-check** of that headline: it is defined as
`onoise²/white²`, so `white_input_density × √ENBW` re-derives `σ_comp`
identically and cannot fail (checked: 265.904 nV/√Hz × √39.6082 MHz =
1673.5 µV = the reported `onoise`). Its value is as a **magnitude** bound —
~40 MHz is what a 150 kΩ load into the latch's input capacitance should give,
a comparison against the netlist rather than against this record — and its
per-corner spread. The genuinely independent checks on `σ_comp` are the DC gain
(`av_dc`, cross-checked against `sim/comparator-offset/`) and the white density
(`white_nv_rthz`, cross-checked against `sim/device-characterization-report.md`
§3.4's single-device thermal floor).

Three things this measurement does *not* say, all recorded on the record
itself:

- **`fnoicor` is at the PDK default (0, as-extracted).**
  `sim/device-characterization-report.md` §3.4 measured the worst-case flicker
  setting to raise flicker noise **power** by ~11×. The record reports the
  flicker fraction of the total (0.61 % nominal), so the worst-case
  number is `σ·√(1 + 10·f_flicker)` — 108 µV rms at nominal, still
  far inside the allocation. Flicker at this level is in any case *correlated*
  across the ten bit trials of one 1 µs conversion, so it behaves as a slowly
  drifting offset rather than as per-decision noise, and the offset budget (§3)
  is the one that absorbs it.
- **It is a schematic-level number.** Post-layout extraction (#17) adds
  capacitance at the preamp output, which *lowers* the noise bandwidth and
  therefore this figure. Conservative in the right direction.
- **It excludes the latch's own noise**, which no ngspice analysis can measure.
  See §8.1 for the bound and §8 for why no analysis can.

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

`sim/comparator-offset-mc/` — 150 mismatch draws per PVT point,
`sw_stat_mismatch = 1`, `sw_stat_global = 0`, common random numbers across the
grid. **38 of the 45 points completed**; seven (`ss_-40c_*`, `ss_27c_2.97v` and
neighbours) were killed by the host's OOM killer (`ngspice exit -9`) while four
other simulation campaigns shared the machine, and are recorded as `ERROR` rows
rather than omitted. That is a real gap, and here is why it does not move the
conclusion: the measured σ varies by only 1.3 % across the 38
points that did run, which is *expected* rather than lucky — `par_vth` lives in
the PDK's `fets_mm` subcircuit and not in any corner `.lib` section, so the
dominant term cannot move with process by construction, and
`sim/device-characterization-report.md` §3.3 measured the same invariance
independently over its own full 45-point grid (< 0.8 % movement). A clean-host
re-run should still mint a superseding record.

| | Value |
|---|---|
| σ(V_os), nominal | **1.195 mV** |
| Population mean offset (all corners, common random numbers) | +150 µV — 1.5 standard errors of the mean at N = 150, i.e. a property of this draw set, not a circuit asymmetry. `sim/comparator-offset/` measures the mismatch-free circuit's systematic offset as 2 × 10⁻⁹ V. |
| σ(V_os), worst corner | **1.195 mV** (`tt_27c_3.63v`) |
| 3σ, worst corner | 3.58 mV = **1.11 LSB** |
| `A_Vt` back-extracted from it | 6.97 mV·µm (vs 7.208 measured standalone) |
| Corner spread of σ (process axis) | 1.3 % |

The back-extracted `A_Vt` is **6.97 mV·µm against the 7.208 mV·µm**
`sim/device-mismatch-mc/` measured on an isolated pair — 3.2 % lower, not
higher. Two things about that, because the direction was not the one predicted:

- **It is inside the combined statistical error.** This record resolves each σ
  to 1/√(2N) = 5.8 % at N = 150 and #4's resolves its own to 4.1 %; 3.2 % is
  well within the quadrature sum. The two extractions agree.
- **The prediction that it would read *higher* was wrong, and that is
  informative.** The reasoning was that the preamp pair runs in moderate
  inversion, so current-factor (β) mismatch should add to threshold mismatch,
  while `sim/device-mismatch-mc/` deliberately biases in deep subthreshold to
  suppress it. The measurement says the β term is not resolvable at this bias —
  consistent with `sim/device-characterization-report.md` §5.3's warning that
  β mismatch is **not characterized** in this PDK. So the offset budget rests
  on threshold mismatch alone, and a foundry dataset that supplies a real β
  mismatch coefficient could still add to it. That is a stated gap, not a
  closed one.

The near-corner-invariance of σ is also expected and asserted as a ceiling
rather than merely observed: `par_vth` lives in the PDK's `fets_mm` subckt, not
in any corner `.lib` section, so the dominant term cannot move with process by
construction (`devchar` §3.3).

### 3.3 The latch's contribution, and the total

The StrongARM latch's own offset (input pair 8/0.5 µm plus its load and
regeneration-node mismatch) is referred to the comparator input **divided by
the preamp gain** `A_v`, measured at **16.03** nominal and **9.51**
at the worst corner (`sim/comparator-offset/`, `ff_125c_3.63v`). Taking the
latch input pair alone at the same `A_Vt`:

```
sqrt(W_eff·L_eff) = sqrt(8.1 × 0.35) = 1.684 µm
σ(ΔV_th)_latch    = 7.208 / 1.684    = 4.28 mV  (at the latch input)
referred to the comparator input, worst-corner gain: 4.28 / 9.51 = 0.450 mV
```

Combining in quadrature with the measured preamp term at the worst corner:

```
σ_os,total = sqrt(1.195² + 0.450²) = 1.277 mV
3σ         = 3.83 mV = 1.19 LSB   vs the ratified 2 LSB
```

**Margin to the ratified row: 0.81 LSB (41 % of the row unspent).**

The latch term is a *derived* number, not a measured one: it uses the same
measured `A_Vt` and the measured worst-corner gain, but it does not include the
latch's load/regeneration mismatch or its dynamic (timing-dependent) offset
component. Two things bound the error that introduces:

- The latch's additional terms enter the same way — divided by `A_v` — so
  doubling the assumed latch offset to 8.6 mV would move the total from
  1.19 LSB to 1.39 LSB, still inside the ratified
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

- (a) is **satisfied by DR-0014, not assumed**: MCS/Vcm switching holds the
  comparator's input common mode constant in differential mode, so the offset
  cannot vary from trial to trial. In single-ended mode the common mode moves
  by `residue/2` — so the requirement becomes "offset must be stable over the
  *late-trial* common-mode excursion", which is a few millivolts.
  `sim/comparator-offset-mc/` measures the code-correlated term directly: the
  1σ change in offset over a **±50 mV** common-mode band — about 5× wider than
  the late trials ever see — is **0.19 µV**, i.e. 0.00006 LSB. There
  is no measurable code-correlated offset.
- (b) is **satisfied by §3.3**: 1.19 LSB at 3σ against a 2 LSB row.

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
   moves within a conversion (the monotonic alternative recorded in DR-0011's
   Alternatives; DR-0011 is superseded by DR-0014 on sampling only, and
   DR-0014 does not restate this alternative), which would
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

The comparator's input is still the CDAC top plate — but since
[DR-0014](decision-records/DR-0014-bottom-plate-sampling.md)
(2026-08-02; supersedes DR-0011's top-plate sampling) it is no longer the
*sampled* node. During acquisition the per-side top-plate `V_cm` switch
(`adc_tp_sw`) holds the top plate at `V_cm`; it opens at the edge into ph3 —
the sampling instant, one bit cycle before the bottom plates leave `V_in`
(`design/adc-top/gen_adc_top.py`, traced by DR-0025 item 3) — and from that
edge to the next sample the top plate is a floating node of
`C_side = 512 · C_u = 512 · 35.6528 fF = 18.254 pF` per side
(`spec/cdac-sizing-memo.md` §5.2; the DR-0019 resize physically implemented
by `6dfb50bf`, #202) holding the sampled input plus every DAC step of the
conversion. Charge a comparator decision injects there has nowhere to go
before the next trial — it is added to the quantity being converted.
`spec/prior-art-survey.md` §3.6 notes that at 3.3 V the regeneration swing
makes kickback **2.75×** a 1.2 V design's for the same devices, and §3.7
names it the primary risk to retire.

**Charge bookkeeping under DR-0014.** DR-0014's own derivation gives, at any
point in the conversion,

```
V_top = V_cm + [ C_arr·(V_cm − V_in) + Σ_j w_j·C_u·ΔV_bottom,j ] / (C_arr + C_par)
```

so the comparator decides on `k · (V_dac − V_in)` with
`k = C_arr/(C_arr + C_par)`: the *same* factor divides the sampled input and
every DAC step, which is why the divider cancels from the decisions —
DR-0014's immunity result. Kickback is the term that does not cancel: an
injected `ΔQ` displaces the floating top plate by `ΔV ≈ ΔQ/(C_arr + C_par)`,
and the comparator reads it as residue. Input-referred, the displacement is
worth `1/k` LSB, and `C_par` is now measured on the topology as built:
**57.1–160.3 fF over the 63-point grid, divider error 0.284–0.968 %**
(`sim/top-plate-cpar/records/20261105-061018-e5489fc.md`, 2026-11-05, DR-0014
topology with DR-0013's dummies gone — not DR-0014's superseded Context
figures of 240.9–301.4 fF, which were the DR-0011 load set), so
`1/k = 1.003–1.010`. That record's decomposition also prices what DR-0014
added to the node: the `adc_tp_sw` off-state load (`c_sw`, 16.0–18.6 fF at
`V_cm`) is inside `C_par`, next to the comparator's own input capacitance
(`c_cmp`, the other half, which peaks at the balance point — DR-0014 finding
3).

**What the `V_cm` switch contributes.** Three things, none re-derived here:
(1) the off-state capacitance above, already inside the measured `C_par`;
(2) its charge injection at the sampling instant, which is
*signal-independent* because the switch always opens at `V_cm`
(`design/adc-top/gen_adc_top.py`) — a fixed common-mode offset that
differential operation and DR-0007's offset row absorb, measured with its
side-to-side mismatch by `sim/dr0014-sampling/` (cited, not duplicated);
(3) it defines the sampling instant, so during every bit trial the top plate
floats about `V_cm`.

**The worst-case residue point moves under DR-0014.** Under top-plate
sampling the top-plate common mode was the sampled input and slid across the
input range; under DR-0014 every trial's common mode sits at `V_cm` (the
input is differential about `V_cm` and the DAC legs move complementarily:
(`V_top,p/n = V_cm + k·(V_d,p/n − V_in,p/n)`). That removes the old reason
for calling the fixed-`V_cm` deck an approximation — the top plate no
longer slides with the input — but the deck still matches no single mode's
first-trial condition exactly, and this memo now says which is which. The
residue span it drives, `±V_REF/2 = ±1.65 V` differential at trial 1
shrinking to ±half-LSB, is the **single-ended** mode's first-trial span;
**differential** mode's first trial is `±V_REF = ±3.3 V`
(`spec/cdac-sizing-memo.md` §0), twice the largest driven point, at exactly
the deck's fixed `V_cm` — and single-ended mode's common mode moves by
`residue/2` (up to ±0.825 V at the free-MSB decision) where the deck holds
it fixed. The 1.65 V point therefore does **not** bound the differential
first trial by construction. §0's "met with 2× more room differentially"
presumes the kick scales ~linearly in residue, and this grid is the first
evidence against that presumption: fitting a local power law to the deck's
own two large points at the binding corner — `fs_-40c_2.97v`, 0.2585 µV
@100 mV → 97.3676 µV @1.65 V — gives n ≈ 2.1 (`ff_125c_3.63v` is
sublinear, n ≈ 0.64). Carried to a 3.3 V differential first trial, that
extrapolates to ≈ 420 µV ≈ 0.13 `LSB_se`, or 0.066 of the differential
budget once §0's 2× room is applied — inside the `≤ 0.1` check at ~1.5×
margin rather than the 3.3× below — but it is an extrapolation of a
corner-dependent mechanism outside the measured grid, not a measurement;
the differential first trial stays in the Missing-coverage list (§5.3).
The signal-dependent kick is the variation of the differential kick across
the driven residue range, and the mechanisms behind it pull in opposite
directions. DR-0014 finding 3 puts the comparator's input-capacitance peak
at `v_p = v_n` — exactly the common mode every DR-0014 trial sits at — so
the `C_in` route sits at an extremum and its residue-dependence is
second-order. But the kick also runs through the preamp's drain operating
points, which do move with the residue: at a 1.65 V differential one input
device of the pair is driven toward cutoff and its twin toward triode, and
the same record's second structure (input capacitance rising as a node
approaches the rail, "the input device pushed into triode") is the mirror
image of that. Whether the old 100 mV-vs-half-LSB pair was the worst pair
was therefore a measurement question, and the deck now answers it directly:
`tb_kickback.spice` drives a third instance at the single-ended first-trial
residue (`dv = 1.65 V`, the largest driven point), and `kick_sigdep` is the
spread of the differential kick across all three residue points. **The
worst case among the driven points moved**: the first-trial kick reaches
97.4 µV (`fs_-40c_2.97v`) — ~87× the superseded records' measured two-point
maximum (3.4868e-04 LSB_se, §5.2) — and the growth concentrates on the
−10 % supply axis: at 2.97 V the `tt`/`ss`/`fs` corners are elevated
(13.2–97.4 µV), `sf` is intermediate (1.1–11.0 µV), and `ff` is flat
(0.093–0.147 µV, 0.065–0.154 µV across all nine of its corners — no supply
dependence), while every 3.30 V and 3.63 V corner stays ≤ 3.7 µV at the
same residue (max 3.6979 µV, `ss_-40c_3.30v`). The near-triode input device
at a low rail remains a candidate mechanism for the corners that grow, but
the flat `ff` family is a counterexample to stating it as the mechanism
universally; no committed record traces it, and nothing here needs to while
the bound holds (§5.2).

What the deck still omits, and why that is priced: `C_par` itself (≤ 0.9 %
of the node, so omitting it makes the measured residual conservative by the
same ≤ 0.9 %, while the ≤ 1.0 % referral factor above is carried here rather
than in the deck); the sampling switch and bottom-plate dynamics
(`sim/cdac-bit-settling/` owns that separation); mismatch
(`sw_stat_mismatch = 0`; kickback and offset are budgeted separately); and
DR-0013's dummies are gone from the real converter, so nothing needs adding
back.

### 5.2 Measured

`sim/comparator-kickback/` drives three comparator instances from *floating*
18.254 pF top plates — the built DR-0019 array (`512 × 35.6528 fF`,
`spec/cdac-sizing-memo.md` §5.2; implemented by `6dfb50bf`) — biased through
1 GΩ (an ~18 ms time constant against a 62.5 ns bit cycle, so the bias network
observes rather than restores) at a half-LSB residue, a 100 mV residue, and
the single-ended first-trial residue (`dv = 1.65 V`, the largest driven
point; §5.1).

| Quantity | Worst over the grid | In LSB_se |
|---|---|---|
| Residual **differential** kick, half-LSB residue | 0.030 µV (`kick_diff_small_uv`, `ss_-40c_2.97v`) | ≤ 9.3e-06 |
| Residual **common-mode** kick, half-LSB residue | 3.1 µV (`kick_cm_small_uv`, `ss_-40c_3.63v`) | — |
| **Signal-dependent** part (spread across all three residue points) | 97.4 µV (`kick_sigdep_uv`, `fs_-40c_2.97v`) | ≤ **0.0302** |
| First-trial residual differential kick, for reference | 97.4 µV (`kick_diff_max_uv`, same corner) | 0.0302 |
| Peak transient excursion during the decide phase | 244 µV (`peak_dip_uv`, `ss_125c_3.63v`) | — |

**Every row is a resolved value, not a floor-limited bound.** The governing
record was taken on the batch fleet, whose ngspice reports sub-µV `meas`
results (`numdgt=10`); the smallest row above sits ~4 decades below the ~1 µV
quantisation floor the superseded local-run records were read against (see
*Numerical floor* below — that discussion now applies to those superseded
records; rewriting it in general is #605's deliverable). Table figures are
from `sim/comparator-kickback/records/20261116-050139-42785df.md` (git
`42785df4`, clean; testbench sha256
`d298cecec278a1e7ad8261b89be79874db4fd118b90fb54c224acaca1e85e759`, equal to
the current `tb_kickback.spice`; 2026-11-16; 45/45 completed; ngspice-47,
`klt sim` backend `aws-batch-fleet`, jobs `klt-sim-2277a73c11b8`,
`klt-sim-84ef8766175e`, `klt-sim-d6c840f8f462`). The deck's
corner-sensitivity anchor also still passes on the 2.07× larger plate:
`peak_dip_uv`'s per-axis spread floors hold (process 10.5–20.6 % against its
3.0 floor; temperature 2.84–10.8 % against the 2.0 recalibrated by #250).

**Historical, superseded:** the first run (`20260801-042959-dbb3ab5`, dirty tree) completed 43 of the 45 PVT points. `tt_27c_3.30v` and `tt_27c_3.63v` were
killed by the host's OOM killer (`ngspice exit -9`) while the machine was
running four other simulation campaigns; both are recorded as `ERROR` rows in
the record rather than quietly omitted. They are interior points of the grid —
the extremes of every quantity there land at `ss`/`ff` and at the temperature
limits — so the reported worst cases are not the missing points' to take. The
deck was unchanged and re-runnable, and the clean-host re-run is the
superseding record `20260825-044912-9fe3b68` (45 of 45 completed). That
record — and the tool/PDK requalification of the *same* excitation,
`20261020-180419-bc92f79` (identical testbench sha256, so not a DR-0014
re-derivation; its own Claim still read "DR-0006 top-plate sampling") — ran
the superseded premise: DR-0006 top-plate sampling, `ctop = 8.83 pF` (the
pre-DR-0019 array), and only two residue points. This record
(`20261116-050139-42785df`) supersedes both; every figure from them below is
historical.

**The signal-dependent part is the linearity term.** Per survey §3.1, a
kickback that is identical at every code is indistinguishable from comparator
offset and is removed by the same digital subtraction (§4); only the part that
varies with the residue is an INL/DNL error. At the worst grid corner the
three-point spread is **0.0302 LSB_se** (`fs_-40c_2.97v`, 97.4 µV): 6.0 % of
the < 0.5 LSB stretch DNL target, a **≥ 3.3× margin** to the
`kick_sigdep_lsb ≤ 0.1` check. That is a resolved worst case over the
driven points, not a bound, and ~49× the old two-point figure
(≤ 0.00062 LSB): the third residue point exposes the first-trial residue
the old pair never sampled (§5.1). The old
pair itself, re-measured on the built array, behaves exactly as the corrected
`ctop` predicts — its spread over the grid is ≤ 1.7e-4 LSB
(`kick_diff_big_uv` max 0.551 µV against a `kick_diff_small_uv` of ≤ 0.030
µV), the 2.07× shrink of the superseded records' ≤ 3.5e-4 LSB two-point
bound. The claim this record supports is "**signal-dependent kickback across
the driven trial range is ≤ 0.031 LSB_se at all 45 schematic corners**",
which is what the `kick_sigdep_lsb ≤ 0.1` check binds. Where the growth
comes from is pinned by the grid: it concentrates on the −10 % supply axis
at the first-trial residue and tracks process speed there — at 2.97 V the
`tt`/`ss`/`fs` corners are elevated (13.2–97.4 µV), `sf` is intermediate
(1.1–11.0 µV) and `ff` is flat (0.093–0.147 µV; 0.065–0.154 µV across all
nine of its corners, no supply dependence), while every 3.30 V and 3.63 V
corner stays ≤ 3.7 µV at the same residue (max 3.6979 µV, `ss_-40c_3.30v`)
(§5.1).

This is the measured consequence of the DR-0015 topology choice: the static
preamplifier is a unidirectional buffer between the CDAC top plate and the
regenerating nodes, so the 3.3 V latch swing never reaches the top plate
through an input pair's `C_gd`. The number is evidence for that choice, not an
assertion of it.

Two honest limitations. The second is stated on the record itself; the first is
a **correction** to what the record says about itself — `sim/` is append-only,
so `sim/comparator-kickback/records/20260801-042959-dbb3ab5.md` keeps its
original note verbatim, and the corrected statement lives here, in
`sim/comparator-kickback/testbench/tb.json` and in `sim/harness/README.md`. The
*measurements* in that record are unaffected; only the resolution claim made
about them was wrong.

- **Numerical floor — ±1 µV, and it is *not* removed by tightening `vntol`.**
  This deck's residual kickback is smaller than the resolution of the tool that
  reports it. The record is taken with `.options vntol = 1e-9, reltol = 1e-4`
  (they do reach the deck — `sim/harness/runner.py` emits them, and
  `sim/tests/test_harness.py` covers that), and an earlier draft of this section
  claimed those options put the numerical floor three decades below the reported
  values. **They do not.** The binding limit is downstream of the solver: an
  ngspice `meas` result is carried at ~6 significant digits, so a level read off
  a node sitting near 1.7 V is quantized to ~**1 µV** before any `measure`
  expression differences it. The corner logs show it directly
  (`bp0 = 1.70000e+00`, `bp1 = 1.70001e+00`), and it is why all 43 completed
  points of `sim/comparator-kickback/records/20260801-042959-dbb3ab5.md` report
  `kick_diff_*`, `kick_sigdep_uv` and `peak_dip_uv` as exact integer µV. Tighter
  `vntol` buys solver accuracy, not reported resolution. Consequence: every
  residual-kick figure in the **superseded** records named above is a
  **resolution-limited bound**, and their conclusion (≈3 decades of margin to
  the DNL target at the old two-point metric) survived, because the floor
  itself is ~3 decades below the target. The governing record
  (`20261116-050139-42785df`) no longer sits under this floor: the batch
  fleet's ngspice carries `numdgt=10`, so its rows resolve sub-µV (§5.2's
  table). Buying the extra decades would
  need a `meas` referenced to a node near 0 V — e.g. a behavioural differential
  node — not tighter tolerances. The general rule is recorded once, for every
  future deck, in `sim/harness/README.md` § *The `meas` result-precision floor*
  (its rewrite against the fleet backend is #605's deliverable).
- **No parasitics.** Post-layout extraction adds input capacitance and coupling,
  which moves kickback in the **wrong** direction (unlike noise, §2). A
  post-layout re-run of this deck is a required check for #17, not a formality.

### 5.3 Applicability of an input-pair cascode (assessment of issue #443)

**Question.** The standalone comparator repository's proposed
[DR-0004](https://github.com/2AMLogic/gf180-comparator/blob/main/spec/decision-records/DR-0004-preamp-input-cascode-kickback.md)
(issue [2AMLogic/gf180-comparator#102](https://github.com/2AMLogic/gf180-comparator/issues/102),
status *proposed*, schematic level only) cut kickback into a **1 kΩ source** from
4.53–10.01 mV to 0.049–0.085 mV at 45/45 corners by inserting an NMOS cascode
(L = 0.5 µm, W = 20 µm, gate at 0.6·V_DD from a resistive divider) between each
input-pair drain and its load. Does that address a limitation of *this* ADC?
This subsection is an assessment only: it changes no netlist, layout, target or
decision (DR-0015 stands as recorded), and ran no simulation.

**Same structure, different measurement.** `design/comparator/comparator.spice`
is a resistively loaded NMOS preamp (`Xmip`/`Xmin`, 40/1 µm; `Xrlp`/`Xrln`,
150 kΩ `ppolyf_u_1k`; 10 µA tail) driving the gates of a StrongARM latch
input pair (`Xmlp`/`Xmln`, 8/0.5 µm), with no cascode. That is the structure
the upstream finding describes, and the shared hypothesis is the same: the
latch's swinging input-side nodes reach the preamp output (`pop`/`pon`) and
couple back to the input through the preamp pair's `C_gd`. §5.2 calls the
preamp "unidirectional"; read that as "attenuating", not "isolating" — the
`C_gd` path through the preamp pair is the residual route. This is a hypothesis
shared by both designs; **this repository has not decomposed the path**, and no
committed record here separates `C_gd` from other routes. The two measurements
are not interchangeable:

| | Upstream DR-0004 | This repo (`sim/comparator-kickback/`) |
|---|---|---|
| Source seen by the input | 1 kΩ per input (restores charge during the event) | **floating** 18.254 pF per side (the built DR-0019 array), 1 GΩ bias (18 ms ≫ 62.5 ns), so injected charge stays on the plate |
| Headline metric | kickback into 1 kΩ, mV, bounded ≤ 5 mV (≤ 2 mV stretch) upstream | **signal-dependent residual** `kick_sigdep` (spread across the half-LSB / 100 mV / 1.65 V residue points), µV and LSB_se (3.2227 mV) |
| Governing bound | upstream kickback row | `kick_sigdep_lsb ≤ 0.1` and `kick_diff_small_lsb ≤ 0.25` (`tb.json`) |
| Level of evidence | schematic, 45 corners; post-layout not established | schematic, 45 corners; extracted not measured |

A 1 kΩ source converts injected charge into a *peak voltage* set by the source
resistance and the injection waveform; a floating plate converts the same
charge into a *residual* `ΔV = ΔQ / 18.254 pF` that nothing restores. The
upstream figure therefore cannot be scaled to this ADC's residual (or the
reverse) without the injection waveform, and 4.5–10 mV must **not** be read as
"the ADC kicks back 4.5–10 mV". In this deck the quantity closest to the
upstream one is the peak row, `peak_dip_uv` 153–244 µV, taken on a plate with
*no* series resistance (the record calls the lumped model optimistic for the
peak and conservative for the residual).

**Current ADC evidence, with provenance.** Governing record:
`sim/comparator-kickback/records/20261116-050139-42785df.md` (schematic; git
`42785df4d2d36e7baa655f32b0aa92ecae1b0773` on `feature/issue-833`, clean;
testbench sha256
`d298cecec278a1e7ad8261b89be79874db4fd118b90fb54c224acaca1e85e759`, equal to the
current `tb_kickback.spice`; 5 process corners × −40/27/125 °C ×
2.97/3.30/3.63 V, **45/45 completed**; mismatch off; `vntol = 1e-9`,
`reltol = 1e-4`; ngspice-47 via `klt sim` backend `aws-batch-fleet`;
2026-11-16). It supersedes `20261020-180419-bc92f79` (a tool/PDK
requalification of the same excitation, not a DR-0014 re-derivation) and
through it `20260825-044912-9fe3b68`, which superseded the clean-tree
`20260825-025943-4e220d1` (same result rows; only a harness self-check
threshold differed) and the dirty-tree, 43/45 `20260801-042959-dbb3ab5`, which
should not be cited; all four ran the superseded DR-0006 premise, the
pre-DR-0019 `ctop = 8.83 pF`, and only two residue points. Metric definitions
(`tb.json`): `kick_diff_small_uv` =
(V_diff at 72 ns − V_diff at 9.5 ns) at a 1.6113 mV (half-LSB) residue;
`kick_diff_max_uv` = the same at the 1.65 V first-trial residue;
`kick_sigdep_uv` = the spread of the differential kick across the three
residue points (half-LSB, 100 mV, 1.65 V) — superseding the old two-point
difference; `kick_cm_*` = common-mode shift of the two plates over the same
window; `peak_dip_uv` = V(tpa) at 9.5 ns minus its minimum over 10–42 ns.

| Quantity (45-point worst) | Value | Bound / budget | Margin |
|---|---|---|---|
| `kick_sigdep` (three-point spread) | 97.4 µV = 3.02e-2 LSB_se (`fs_-40c_2.97v`) | `kick_sigdep_lsb ≤ 0.1` (322 µV) | ≥ 3.3× |
| `kick_diff_small` | 0.030 µV = 9.3e-6 LSB_se (`ss_-40c_2.97v`) | `≤ 0.25` LSB_se | ≥ 2.7e4× |
| `kick_diff_max` (first trial) | 97.4 µV (`fs_-40c_2.97v`) | `kick_diff_max_lsb ≤ 0.25` LSB_se | ≥ 8× |
| `kick_cm_small` / `kick_cm_big` / `kick_cm_max` | 3.1 / 3.6 / 53.0 µV (`ss_-40c_3.63v`, same, `fs_-40c_2.97v`) | ±20 mV | ≥ 370× |
| `peak_dip_uv` | 153 (`ff_-40c_2.97v`) … 244 (`ss_125c_3.63v`) µV | ±200 mV (sanity band) | not a linearity term |
| `q_diff_small_fc` | ≤ 5.5e-4 fC (one LSB-se smallest-row step on 18.254 pF) | ±2000 fC | — |

**Numerical floor (retired for this record).** The rows above are resolved
values — the fleet backend's ngspice carries `numdgt=10`, so the smallest row
(2.3e-4 µV) is ~4 decades below the ~1 µV quantisation floor the superseded
records sat at (§5.2). Two consequences for this subsection. The historical
objection that this deck was too coarse to verify a residual improvement is
gone: a cascode-style change would show up in these rows if it moved the
residual. And the third residue point has made item 3 of the trigger list
below a live question rather than a hypothetical: the deck now reports a
*resolved* signal-dependent residual of 0.0302 LSB_se, within an order of
magnitude of the 0.1 LSB bound that item names. Whether that re-opens the
cascode question is #443's to re-run against this record; this subsection's
recommendation below still stands on its remaining reasons, and no new
cascode analysis is done here.

**Integrated ADC evidence.** The kickback deck is comparator-only and
schematic-level: no CDAC array, no switch resistance, no bottom-plate dynamics
(the record's own note; `sim/cdac-bit-settling/` owns those), and no extracted
variant. `sim/comparator-pex/records/20260815-230715-56fbe50.md` records the
post-layout comparator attempt as blocked structurally, before any
PVT-dependent measurement. No committed record measures kickback inside the
full ADC, and none measures a code-correlated error attributable to the
comparator. The current full-ADC shortfalls are attributed elsewhere in the
repository: worst extracted ENOB 8.855 bits (`tt_125c_3.63v`; target > 9.0,
below target at 2 of 9 points) and worst SFDR 60.41 dB (`ff_125c_2.97v`;
target ≥ 62 dB, below at 4 of 9 points) after the drawn-tap re-take
(`sim/extracted-delta-summary.md` §4.14.2, issue #381, record
`sim/adc-enob-fft/records/20260923-111149-904af96.md`), with the SFDR mechanism
isolated to the acquisition RC at the DR-0019 `C_u` (SFDR slope −19.00
dB/decade of `C_u` against −20 predicted; `sim/dr0019-cu-sweep-findings.md`;
`spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md`). Those
records neither test nor exclude a kickback contribution. The present evidence
**does not attribute any ENOB or SFDR shortfall to kickback**, and this memo
does not either. The extracted INL/DNL (0.5284 / 0.7278 LSB worst at
`ss_125c_2.97v`, `sim/extracted-delta-summary.md` §3) likewise has no kickback
attribution.

**Recommendation: retain the current comparator; do not open a cascode
experiment now.** Supported by: (1) the only kickback quantity that is a
linearity term, the signal-dependent residual, is bounded at ≤ 0.031 LSB_se
(97.4 µV) against a 322 µV check at all 45 schematic corners; (2) the upstream improvement is on a
metric (disturbance into 1 kΩ) that this ADC's budget does not contain, and
its size cannot be mapped onto a floating plate; (3) the superseded records
could not verify a residual improvement — their rows sat at a ~1 µV
quantisation floor — and the governing record resolves sub-µV, so that reason
has retired; an experiment on this deck would now falsify or verify a residual
change, but it would still be measuring the wrong quantity, per reason (2);
(4) the cascode is not free
upstream (offset σ 2.68–3.14 mV vs 2.80 mV, decision time +3 % worst case,
power +16–24 µW, one untuned bias ratio, noise at the nominal point only) and
needs a new headroom analysis against a 10 µA / 150 kΩ preamp whose drains sit
~0.75 V below V_DD at 5 µA per side; and (5) it modifies the DR-0015 topology,
which requires a decision record and layout/LVS/extraction work. Absence of
evidence of harm is not evidence of need: no record here shows kickback
limiting the ADC.

**Evidence that would change the recommendation** (any one):

1. An **extracted** comparator-in-ADC kickback measurement, routing coupling
   included, whose `kick_sigdep` exceeds 0.1 LSB_se (322 µV) or whose
   `kick_diff_small` exceeds 0.25 LSB_se at any PVT corner. (The extracted path
   is blocked today by `klt pex`'s DUT-interface limitation, per
   `sim/comparator-pex/`, so this needs a block-scoped route.)
2. A full-ADC test that **isolates** the comparator's contribution (for
   example the same extracted ADC, same codes and stimulus, with the
   comparator's injection path disabled or buffered) showing a code-correlated
   error that moves ENOB, SFDR, INL or DNL by more than that test's numerical
   floor.
3. A near-0 V-referenced deck (§5.2) showing a resolved signal-dependent
   residual within an order of magnitude of 0.1 LSB_se. (Status 2026-11-16,
   #833: the governing record's third residue point now reports a *resolved*
   0.0302 LSB_se at the worst corner — within that order of magnitude, on the
   standard deck rather than a near-0 V-referenced one; see the *Numerical
   floor* note above. Re-run this assessment in #443 against
   `20261116-050139-42785df`.)
4. A neighbour-coupling or floorplan finding (issue #16) that makes the *peak*
   excursion, not the residual, the binding quantity.

**Missing coverage** (none exists today): extracted kickback of any kind;
kickback with the real switched CDAC and its switch resistance; both residue
polarities and more than three residue levels (the deck samples +1.6113 mV,
+100 mV and +1.65 V, all one polarity); mismatch enabled; single-ended mode with its decaying
`residue/2` common mode; differential mode's ±3.3 V first-trial residue
(twice the largest driven point, covered only by an extrapolated scaling
law — §5.1); ADC-level code-correlated attribution; a path
decomposition of the `C_gd` hypothesis; a cascode
variant of this comparator at any level. (Resolution below ~1 µV was listed
here until the fleet backend retired it: the governing record resolves rows
down to 2.3e-4 µV — §5.2.)

**If a follow-up experiment is later justified**, it needs its own issue, a
proposed decision record and operator ratification before
`design/comparator/comparator.spice` or any layout is touched; the experiment
netlist lives outside the production design (as upstream did), and no
production file, target, or §5.2 bound changes on its basis. Minimum design,
with falsifiable hypotheses (none of these checks has been run):

- *Matched pair.* Control = unmodified `tb_kickback.spice` (sha256 above);
  candidate = the identical deck with only the cascode devices and their bias
  added. Same floating 18.254 pF plates and 1 GΩ bias, same 45-point `mos` grid,
  same clock, same `vntol`/`reltol`; mismatch off for kickback and on in a
  separate offset run.
- *Polarity and stimulus.* Both decision polarities, at the half-LSB and
  100 mV residues; `dout` correct in every case (`dout_*_end ≥ 0.9`).
- *Metrics.* Residual differential and common-mode kick, signal-dependent part,
  and peak excursion, at ≥ 10× finer resolution than the current ~1 µV
  (near-0 V-referenced `meas` or equivalent), so the control residual is
  resolved and a change is measurable.
- *H1 (benefit).* The candidate's resolved signal-dependent residual and peak
  are lower than the control's at each of 45/45 corners by more than the
  measurement resolution. H1 is falsified if the control residual stays
  unresolved or the candidate is not lower at any corner.
- *H2 (no regression), limits from existing specifications.* Offset 3σ ≤ 2 LSB
  (12.89 mV; comparator-only schematic currently 1.19 LSB worst corner);
  input-referred noise ≤ 537 µV rms at the ENOB-stretch allocation (153 µV
  worst now) over the full 45-point grid, not nominal only; worst decision
  delay against the 15.625 ns decide phase at 2 MS/s (863 ps schematic, 1.256 ns
  extracted now); power < 1 mW and < 500 µW stretch (108 µW now at
  `ff_125c_3.63v`); saturation margin (V_DS ≥ V_DS,sat) on the input pair and
  cascode at every corner including `ss_125c_2.97v`, with the cascode gate bias
  derived from that headroom analysis rather than copied from the upstream
  0.6·V_DD ratio.
- *H3 (ADC level).* Only on an extracted candidate: the extracted worst-corner
  ENOB (8.855 bits) and SFDR (60.41 dB) do not worsen, and any claimed
  improvement is demonstrated by the isolating test above. A cascode cannot be
  credited with fixing an ENOB/SFDR shortfall without it.
- *Layout and extraction obligations.* A cascode removes the device `C_gd`
  route, not wire-to-wire coupling, which upstream predicts as the dominant
  residual afterwards; the candidate therefore needs re-layout, DRC, LVS and
  extraction, with the kickback deck re-run on the extracted netlist, before
  any post-layout benefit is claimed.

**Cross-reference.** DR-0015 (Alternatives considered) points here and keeps
its decision unchanged.

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
| Decision delay at **half an LSB** overdrive | 504 ps | **863 ps** (`ss_125c_2.97v`) |
| Decision delay at 100 mV | 412 ps | 687 ps |
| Regeneration time constant `τ` (extracted) | 22.1 ps | 42.8 ps |
| Margin against the 31.25 ns decide phase | 30.75 ns | **30.39 ns** |

`τ` is extracted, not assumed, from the two measured overdrives:
`τ = (t(0.5 LSB) − t(100 mV)) / ln(100 mV / 1.6113 mV)`.

**Metastability.** A latch resolves an input `V_in` in
`t = t₀ + τ·ln(V_logic/(A_v·V_in))`, so in the time left after the half-LSB
decision the comparator could still resolve an input
`10^309` times smaller — 309 decades of headroom at the
worst corner. Stated as an error probability: a decision is unresolved at the
end of the decide phase only if the residue falls within
`0.5 LSB × 10^-309` of the decision point, which for a uniformly
distributed residue is a probability of order `10^-309` per trial —
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
| Static (mirror diode branch + tail, ~20 µA) | 19.6 µA nominal, 19.9 µA worst | **65 µW** nominal, 72 µW at `ff_125c_3.63v` |
| Dynamic, per decision | 2232 fJ nominal, 3247 fJ worst | 24.5 µW (11 decisions/conversion) |
| **Total** | | **89 µW** nominal, 108 µW worst |

Against the ratified **< 1 mW** row that is 10.8 %, and against the
**< 500 µW** stretch 22 %. The binding corner for power is
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
  the dynamic term is 28 % of the total. A future low-rate variant
  would gain nothing without power-gating the preamp, which DR-0015 explicitly
  does not design.

---

## 8. Noise-verification methodology — the ngspice decision

The issue's original text asks this to be a *stated decision*, and
`sim/README.md`'s **Noise methodology** field requires it on the record itself.

**Chosen path: `ac-based`** — ngspice `.noise` on the static preamplifier about
a real DC operating point, with the StrongARM latch instantiated in reset so
that its input capacitance loads the preamp, integrated 1 Hz…1 GHz at the
output and referred to the input by the measured DC gain (§2). Cost: **45 PVT
points in about five minutes of wall time** on a contended 8-core machine.

**This path exists only because of DR-0015.** `spec/prior-art-survey.md` §3.5
is explicit: `.noise` is a small-signal analysis about a DC operating point;
StrongARM, double-tail and dynamic-preamp topologies have none, and ngspice has
no PSS/pnoise and injects no device noise into a transient. For any of those,
the only valid path is an explicit `trnoise` source at the input, swept across
±3–4σ in steps below σ, with K independent transient trials per point fitted to
a Gaussian CDF.

**Cost of the path not taken, for #13 and #2.** Resolving σ to ~10 % needs
`K ≈ 10²–10³` trials at each of 10–20 input points — **10³–10⁴ transient runs
per corner**. On this repo's own measured throughput, one comparator transient over a
62.5 ns bit cycle costs of order **10 s of CPU** at a grid point
(measured: `sim/comparator-regeneration/` runs a 3-instance, 2-bit-cycle deck
across 45 PVT points in ~1800 s of wall time at 2–4 way parallelism). At the
low end of the survey's range — 10³ runs per corner × 45 corners × 10 s — that
is **~125 CPU-hours per noise record**, versus about five minutes for the
`.noise` path. Even with the multi-strobe amortization a careful implementation would use
(many decisions per transient), it remains three orders of magnitude more
expensive.

That ratio is the quantified form of the survey's schedule argument, and it is
**the reason the ~66 µW static preamp is worth its power**: it does not merely
lower the noise, it converts the noise claim from a Monte Carlo campaign into a
deterministic analysis this project can afford to re-run on every change.

**What remains open on this path.** ngspice cannot measure the latch's own
noise by *any* analysis (see the bound in §8.1 below), so the total
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
referred to the comparator input, ÷ A_v = 9.51: 7.6 µV
```

Combined in quadrature with the measured worst-corner preamp noise
(153.2 µV), the total moves to 153 µV rms — a change of
0.1 %, and still 3.5× inside the stretch allocation.
`C_int`, `gm_lat` and `Δt` above are **estimates**, not measurements; the
conclusion survives an order of magnitude of pessimism on `σ_latch,in`
(10× would take the total to 171 µV, still inside the allocation),
which is the property that makes it an acceptable bound rather than a gap.

---

## 9. Summary for downstream issues

- **#12 (timing)**: comparator decision delay is **863 ps worst-case
  at half an LSB**, against a 31.25 ns decide phase — 30.39 ns of
  margin at 1 MS/s and 14.76 ns at the 2 MS/s stretch. Do not
  carry the survey's "sub-nanosecond `[E4]`" estimate; use the measured number.
- **#13 (testbench suite)**: the noise methodology is `ac-based` (§8), costing
  ~1 minute per 45-point record. **The `trnoise` Monte Carlo campaign the
  survey budgeted (10³–10⁴ runs/corner, ~125 CPU-hours per record at the low end) is NOT
  needed for this topology** — but it returns in full if any record supersedes
  DR-0015 with a dynamic topology. #13 also inherits the §8.1 latch-noise bound
  as a stated assumption.
- **#14 (Monte Carlo)**: model comparator offset as a **per-instance constant**
  with σ = 1.277 mV input-referred (dominated by the preamp input pair's
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
- **#11 (SAR logic)**: the comparator presents a held level, not a pulse
  (**NOR** SR output latch, driven through isolation inverters — the NAND
  variant was built, measured to have ~10 mV of hysteresis, and rejected; see
  `design/comparator/comparator.spice`), and needs one clock phase. `dout` goes
  HIGH when `v(vinp) > v(vinn)` and stays valid through the next reset. The
  digital path must subtract a stored offset constant (tier 0, §4).
- **Open interface item**: the 10 µA `ibias` pin needs a source. Whether it is
  generated on-chip or supplied externally is not decided by DR-0015 and should
  be raised alongside the `V_cm` rail's identical question, which is no longer
  open: DR-0026-vcm-drive-source (2026-08-25) derives its drive-impedance and
  decoupling budget as the analogue of DR-0002's `V_REF` budget.

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
