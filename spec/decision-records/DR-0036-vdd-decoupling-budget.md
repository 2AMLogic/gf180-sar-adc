# DR-0036: the V_DD switching transient is budgeted as charge — ≥ 40 nF external, plus a required on-die term inside ADC_BLOCK

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-23
- **Decided by**: Builder agent, issue #379
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #379 (this issue), #346 and `layout/power/` (the static read
  that found the gap), [DR-0034](DR-0034-supply-droop-budget.md) (the static
  droop budget whose Consequences explicitly leave this open),
  [DR-0002](DR-0002-reference-source.md) and
  [DR-0026](DR-0026-vcm-drive-source.md) (the two charge-based decoupling
  derivations this record mirrors),
  `sim/adc-rail-current/records/20260923-002945-1cefe83.md` (the measured
  peak and average this record is derived from, and its per-corner raw log
  `corners/20260923-002945-1cefe83/ff_-40c_3.63v.log` for the peak's own
  `at=` timestamp), `layout/power/records/20260923-010407-d84c7b4.md` (the
  solved rail network this record reads an effective resistance off),
  `spec/prior-art-survey.md` §2.4 (the on-chip-decoupling area arithmetic
  reused here, and its 2 fF/µm² density),
  [DR-0003](DR-0003-clocking.md) (the 62.5 ns bit cycle / 1 µs conversion
  period), [DR-0011](DR-0011-cdac-switching-scheme.md) and
  [DR-0014](DR-0014-bottom-plate-sampling.md) (what actually switches),
  #378 (the supply geometry this record's on-die term lands on), #386 (the
  follow-up deck that would replace this record's charge *bound* with a
  measured event charge and width)

## Context

The ratified table carries an external decoupling allocation for `V_REF`
(≥ 40 nF, DR-0002) and for `V_CM` (≥ 40 nF, DR-0026), each with a derived
source-impedance budget behind it, and says **nothing** about `V_DD` — even
though the once-per-conversion CDAC event that loads the first two loads the
third as well, through the bottom-plate drivers. DR-0034 budgets the
*static* droop and says so in its own Consequences: *"This record does NOT
settle decoupling … A decoupling budget is separate work."*

That gap is now measurable rather than merely noted.
`sim/adc-rail-current/` (record `20260923-002945-1cefe83`, 27-point PVT
grid) measures what the `vdd` island is asked to deliver: a **34.383980 mA**
peak at `ff_-40c_3.63v`, at `t = 7.00286 µs`, against a **39.5421 µA**
average in that same corner — a factor of **869** — because the CDAC's 72
bottom-plate T-gate legs switch together. `layout/power/` then solved the
drawn resistive rail at that current as a DC load and reported
**17.987806 V** of combined droop on a 3.3 V rail. That number is not a
prediction and that flow does not present it as one: it is what a network
with no charge storage in it would develop, i.e. a statement that the DC
path alone cannot source the peak. Which is true of essentially every block,
and is exactly what decoupling is for. What was missing is the number that
makes the statement actionable.

## Decision

**The `V_DD` switching transient of one conversion is budgeted as charge, the
charge is provisioned off-die, and a local on-die term inside `ADC_BLOCK` is
required but is not sized here.** Three clauses, one decision — they answer
one question (*where does the charge for the CDAC switching event come
from?*) and are not separable: clause 2 is only sufficient because clause 1
bounds the charge, and clause 3 exists only because clause 2's charge cannot
arrive in time.

1. **Per-conversion transient charge budget.** The charge `V_DD` must supply
   for one conversion is bounded at **ΔQ_conv ≤ 40.120 pC** (grid-worst
   average), of which ≥ 99.7 % is the CDAC driver branch; the attributed
   bound is **9.319 pC**. The measured peak's equivalent rectangular width
   follows: **≤ 1.150 ns** (total bound), **≈ 0.272 ns** (attributed bound).
2. **External decoupling at the `V_DD` pin: ≥ 40 nF**, with an effective
   source impedance **≤ 3 Ω**, holding the per-conversion sag inside
   0.5 LSB = 1.611328 mV.
3. **On-die local decoupling inside `ADC_BLOCK`: required, and not sized by
   this record.** Required because the off-die charge cannot reach the
   drivers within the event (steps 7–8 below); unsized because the relation
   that sizes it, `C_local ≥ L·I_pk²/(2·ΔV_inst²)`, needs two inputs this
   repo does not have — a package loop inductance and a ratified
   instantaneous-excursion allowance.

### Derivation (shown, not asserted)

**What the deck measures, and what it does not.** `sim/adc-rail-current/`
reports, per PVT point, the peak of `i(vddc)+i(vddd)+i(vddt)` and the average
of the same sum over one 14 µs window, plus the peak's own `at=` timestamp in
the raw log. It does **not** integrate the current over the switching event,
so the event's charge and its width are not directly measured. Both are
bounded **from above** out of what is measured, which is the conservative
direction for a decoupling budget: a looser bound provisions more
capacitance, never less.

**Step 1 — the charge, bounded from the measured average.** The converter
runs at 16 clocks × 62.5 ns = **1 µs per conversion** (DR-0003, the ratified
Latency row), and the deck's measure window (3 → 17 µs) is 14 µs, i.e. 14
conversion periods. Dividing the measured window average by the conversion
rate gives the charge per conversion exactly:

```
Q_conv (ff_-40c_3.63v, the peak's own corner)  = 39.5421 µA × 1 µs = 39.542 pC
Q_conv (ff_125c_3.63v, grid-worst average)     = 40.120  µA × 1 µs = 40.120 pC
Q_cdac (ff_-40c_3.63v, grid-worst CDAC branch) =  9.31892 µA × 1 µs =  9.319 pC
```

Each of these bounds `ΔQ_event`, the charge of the single switching event
that produced the peak, **provided the rail only ever delivers charge and
never absorbs it** — the deck measures `MIN` and `AVG` only, never `MAX`, so
that is a stated assumption of this record rather than a measurement. It is
the ordinary behaviour of a CMOS driver bank, and the follow-up in
Alternatives (integrating the event directly) is what would confirm it.
`40.120 pC` is the same grid point `layout/power/`'s `pvt_worst_average`
current model already uses, so the two flows are priced off the same corner.

The attributed figure is the useful one physically. At the peak instant
(`t = 7.00286 µs`, where `i(vddd)` reaches its own window minimum too) the
CDAC branch carries 34.2987 mA of the 34.383980 mA total — **99.75 %** —
leaving the comparator and track branches 0.0853 mA between them at that
instant. The transient *is* the CDAC driver branch, which is the branch the
bottom-plate T-gate legs' local drivers sit on
(`sim/adc-power/testbench/tb_adc_power.spice`'s `vddd`).

**Step 2 — the duration, recovered as the peak's equivalent width.** A
measured peak and a measured charge bound imply a width: the width the peak
would have if it were a rectangular pulse carrying the whole bound.

```
t_eq (total bound)      = 39.542 pC / 34.38398 mA = 1.150 ns
t_eq (attributed bound) =  9.319 pC / 34.2987  mA = 0.272 ns
```

Both land **below the deck's own 2 ns maximum timestep** (`tran 1n 17.000u 0
2n`). That is the cross-check worth recording: the deck's manifest states
that a spike shorter than its timestep is averaged over the step it lands in
and that every peak is therefore resolution-limited and a lower bound — and
the measured numbers, independently of that caveat, say the event cannot
have been resolved. The event is sub-nanosecond. Everything downstream
follows from that, not from an assumed pulse width.

**Step 3 — the allowed instantaneous droop.** `0.5 LSB = 1.611328 mV` at the
ratified `V_REF = 3.3 V`, the same denominator DR-0002 and DR-0026 use. For
those two rails the denominator is exact: full scale is ratiometric to
`V_REF`, so a droop is a code error one-for-one. For `V_DD` it is
deliberately **conservative**. `V_DD` is not the reference — DR-0002
separates them precisely so that digital switching noise on the supply does
not land on the reference — and a `V_DD` droop reaches the conversion only
through the blocks' supply sensitivity, which this repo has never measured.
DR-0034's own Alternatives section records why: the comparator-offset deck
is a zero-mismatch deck and reports no sensitivity at all, and the one
sensitivity it does expose (preamp gain, 0.06 % across the whole ±330 mV
window) would imply a budget hundreds of millivolts loose. Using 0.5 LSB is
the safe floor in the absence of that deck, in exactly the sense DR-0002's
whole-array assumption is a safe floor: a future sensitivity deck can only
relax it, never tighten it.

**Step 4 — `C_dec,min`.** The same `C_dec ≥ ΔQ / ΔV_LSB` relation
`spec/prior-art-survey.md` §2.4 states and DR-0002 / DR-0026 both apply, by
both routes:

```
Route A (total bound)      C_dec ≥ 40.120 pC / 1.611328 mV = 24.90 nF
Route B (attributed bound) C_dec ≥  9.319 pC / 1.611328 mV =  5.783 nF
```

**Provisioned: ≥ 40 nF**, rounding route A up by the same convention DR-0002
(34 → 40 nF) and DR-0026 (37.4 → 40 nF) use, and landing on the value
already provisioned for both other rails so a single standard part serves
each pin. At 40 nF the per-conversion sag is `40.120 pC / 40 nF =
1.003 mV`, inside the 1.611 mV allowance. Unlike DR-0026's two routes, these
two do **not** agree: route B is 4.3× looser, and the gap is the price of
bounding an event by its whole conversion. Route A is provisioned against
because it is the one that rests on no attribution assumption.

**Step 5 — `Z_vdd,max`.** The sag model in step 4 is only valid if the
decoupling capacitor is fully recharged between conversions; otherwise the
sag stops being a bounded per-conversion term and becomes a DC offset.
Applying the settling convention DR-0002/DR-0026 apply to the bit cycle, to
the conversion period instead:

```
τ_max     = 1 µs / ln(2¹¹) = 1 µs / 7.6246 ≈ 131.2 ns
Z_vdd,max = τ_max / C_dec   = 131.2 ns / 40 nF ≈ 3.28 Ω  → provisioned ≤ 3 Ω
```

This looks tight beside `V_REF`'s 240 Ω and `V_CM`'s 220 Ω, and it is not a
burden: the rail's DC current is 40 µA, so 3 Ω costs 0.12 mV of DC drop, and
any real supply behind a board plane is milliohms. Nor is it a cliff — a
larger `Z` converts the sag into a DC pin-voltage drop of `I_avg · Z` (9.6 mV
at 240 Ω), which the ratified ±10 % supply window already governs, not a
per-conversion code error. 3 Ω is where the per-conversion model above stays
the right model.

**Step 6 — can the 40 nF be on-die? No, and the arithmetic is already in
this repo.** `spec/prior-art-survey.md` §2.4 rejects on-chip decoupling for
`V_REF` on exactly this ground: at 2 fF/µm², 5.2 nF is 2.6 mm² —
*"impossible on-chip inside a 0.1 mm² block."* The same density here:
24.90 nF is **12.45 mm²**, and even route B's 5.783 nF is **2.89 mm²**,
against a whole-block area budget of 0.1 mm² that DR-0017 and DR-0024 have
already had to re-budget twice. The charge is off-die. There is no other
answer.

**Step 7 — and yet on-die decoupling is required, for a different reason.**
Off-die charge reaches the die through a package loop inductance, which
limits `di/dt`. For the off-die path *alone* to supply the measured peak
inside the allowance:

```
L_max = ΔV / (I_pk / t_eq)
      = 1.611328 mV / (34.38398 mA / 1.150 ns) = 53.9 pH   (total bound)
      = 1.611328 mV / (34.2987  mA / 0.272 ns) = 12.8 pH   (attributed bound)
```

Even graded against DR-0034's far looser 33 mV static figure the ceiling is
only 1.10 nH / 0.26 nH. **This repo has no package model**, so these are
ceilings with no measured value to compare against — stated as a ceiling
deliberately, not dressed up as a comparison. For scale only, and not as a
repo number: a bond-wire loop is of order 1 nH per millimetre, i.e. one to
two orders of magnitude above the 13–54 pH this would need, and even a
flip-chip bump loop is tens of picohenries at best — so the conclusion below
does not turn on which package is eventually chosen, only on the absence of
one that reaches tens of picohenries. The sub-nanosecond leading edge has to be
supplied on-die. §2.4's own sentence, written about `V_REF`, is the exact
statement needed here: *"On-chip decoupling can only shave the transient, not
supply it"* — and shaving it is precisely the job.

**Step 8 — it has to be inside `ADC_BLOCK`, and the measured rail says so.**
`layout/power/`'s peak case, read as an **effective resistance** rather than
as a droop prediction, is the resistance between where a parent lands the
supply and where the CDAC drivers actually are:

```
R_eff (peak load distribution)    = 17.987806 V / 34.383980 mA = 523 Ω
R_eff (average load distribution) =  5.616 mV  / 40.120 µA     = 140 Ω
```

(both: supply landed at `COMPARATOR`, worst site `ADC_DECODE_BANK_P`,
nominal R corner, `20260923-010407-d84c7b4`. The two differ by 3.7× because
the average is comparator-dominated and the peak is CDAC-dominated, so the
two current models load different instances — which is itself the reason the
peak case cannot be read as a scaled version of the average case.)

Charge parked at the block's supply landing site is therefore behind
**hundreds of ohms of Poly2-stitched rail** from the drivers that need it,
and cannot serve a sub-nanosecond event through it at any capacitance. The
local decoupling must be drawn adjacent to the decode banks, **inside**
`ADC_BLOCK` — not at its boundary, and not in the parent.

**Step 9 — how much, and why this record does not say.** The on-die cap has
to carry the event for as long as the off-die path takes to ramp,
`t_L = L·I_pk/ΔV_inst`, over which it supplies at most `I_pk·t_L/2`:

```
C_local ≥ L · I_pk² / (2 · ΔV_inst²)
```

Both inputs are missing: there is no package model (step 7), and no ratified
instantaneous-excursion allowance `ΔV_inst` for `V_DD` — DR-0034's 33 mV is
a *static* figure derived from the supply window, and is already spent on
the static drop. The sensitivity below, at an illustrative **L = 1 nH (a
stand-in, not a repo measurement)**, is why picking a number anyway would be
irresponsible — the answer moves over four orders of magnitude across a plausible
range of `ΔV_inst`:

| `ΔV_inst` | `C_local` | Area @ 2 fF/µm² | vs the 0.1 mm² budget |
|---|---:|---:|---|
| 1.611 mV (0.5 LSB, step 3's allowance) | 228 nF | 114 mm² | impossible |
| 33 mV (DR-0034's static figure) | 543 pF | 0.271 mm² | impossible |
| 165 mV (half the ±10 % window) | 21.7 pF | 0.0109 mm² | 11 % of it |
| 330 mV (the whole ±10 % window) | 5.43 pF | 0.0027 mm² | 2.7 % of it |

So this record requires the on-die term, states the relation that sizes it,
and names the two missing inputs, rather than inventing a value that the
table shows is unconstrained.

## Alternatives considered

- **Size `C_dec` from the measured peak current and an assumed pulse
  width.** Not chosen: the width is not measured, and assuming one would
  make the whole budget rest on the assumption. Bounding the charge from the
  measured *average* and *deriving* the width from it (steps 1–2) inverts
  the dependency — the assumption-free quantity does the work, and the
  derived width is then checkable against the deck's own timestep cap, which
  it passes.
- **Budget against DR-0034's 33 mV rather than 0.5 LSB.** Not chosen. 33 mV
  is derived from the supply *window*, a DC quantity, and DR-0034 already
  spends all of it on the static drop (the worst landing case reports
  33.029 mV — a FAIL, with nothing left over). This repo's own convention,
  `README.md` note **[a]**, budgets *disturbances* against the 1.61 mV rms
  non-quantization budget (that is how the CMRR row is set) and DC operating
  shifts against the supply window. A transient synchronous with the CDAC
  switching is a disturbance, so it belongs against the first.
- **Pick an on-die decap value anyway — e.g. whatever fits in 1 % of the
  area budget.** Not chosen. Step 9's table shows the requirement spans over
  four orders of magnitude across the plausible input range, so any value picked
  today would be a number without a derivation dressed as a budget. "No
  claim without a testbench" applies to spec values as much as to measured
  ones.
- **Specify nothing on-die and declare the transient the integrator's
  problem.** Not chosen, and this is the status quo this record ends. Step 8
  shows the required term sits *inside* this block's own boundary, behind
  523 Ω of its own rail from the drivers that need it — a place no
  integrator can draw into.
- **Re-run `sim/adc-rail-current/` with a finer timestep and integrate the
  event directly.** Not chosen *for this record*, and it is the single change
  that would most improve it: it would replace route A's 4.3×-loose bound
  with a measured `ΔQ_event` and a measured width. It is a separate piece of
  work because that deck's manifest pins its timestep deliberately —
  changing it makes the run non-comparable with every committed
  `sim/adc-power/` record taken on the same netlist — so it needs its own
  experiment directory and its own decision about comparability, not an edit
  to an append-only record's deck. **Filed as #386.**

## Open questions

Stated explicitly rather than folded into the derivation, because each one
is a place where this record is bounded rather than exact:

1. **`ΔQ_event` is bounded, not measured.** Route A bounds one event by its
   whole conversion, and is 4.3× looser than the CDAC-branch attribution.
   The follow-up deck in the last alternative above closes it — **#386**,
   which also settles the never-absorbs assumption in step 1 by adding a
   `MAX` measure the existing deck does not take.
2. **No package model exists**, so step 7's inductance ceilings (13–54 pH)
   have no measured value to be compared against, and step 9's `L = 1 nH` is
   an illustration, not a repo number.
3. **No `V_DD` sensitivity deck exists**, so step 3's 0.5 LSB denominator is
   conservative by an unmeasured factor. DR-0034 already names the missing
   deck (supply sweep *with* mismatch); the same deck would relax this
   record.
4. **`ΔV_inst` — the instantaneous excursion `V_DD` may take during the
   event — is not ratified by this record or any other.** It is the input
   that would size clause 3, and it needs either (2) or (3) above to be
   derived rather than chosen.

## Consequences

- **`V_DD` joins `V_REF` and `V_CM` as a rail with a stated external drive
  requirement.** That is a third decoupled-pin requirement on whoever
  integrates this block — a real cost, in the same sense DR-0002 records for
  `V_REF`: one more thing a user of this catalog part must supply correctly.
- **The block as drawn has no on-die decoupling at all**, so clause 3 is
  **unmet today**, and this record makes that a stated FAIL-shaped gap
  rather than an unasked question. It is not a formality this block passes.
- **On-die decap is geometry, and it lands directly on #378.** #378 is
  deciding whether `ADC_BLOCK`'s supply rails are carried above Metal1 or
  whether the landing-site constraint is ratified as-is. The 523 Ω in step 8
  is a property of the Poly2-stitched rail #378 is about: if #378 lands
  higher-metal rails, the resistance between a decap and the decode banks
  drops and clause 3's placement constraint loosens; if #378 ratifies the
  rail as drawn, clause 3's decap must sit adjacent to the decode banks with
  no relief. **Whichever of #378 / this record is settled second must
  re-read the other** — this record deliberately does not resolve #378's
  question, and #378's own record should not assume this one's on-die term
  is absent.
- **The provisioned 40 nF is conservative by ~4.3× against the attributed
  bound**, and is provisioned that way on purpose (step 4). A future record
  citing a measured `ΔQ_event` could provision ~10 nF instead. In practice
  this costs nothing — the smallest standard ceramic part anyone would fit
  (100 nF) exceeds every figure here — so the conservatism buys margin for
  free, which is why route A was chosen over route B.
- **`layout/power/`'s static verdict is unchanged and remains sound on its
  own terms.** This record does not re-open DR-0034, does not touch that
  flow, and does not convert the 17.99 V figure into a prediction — it reads
  it as an effective resistance, which is the only thing a static solve at a
  transient current legitimately yields.
- **Two ratified rows move this budget if they ever change.** The charge
  bound is `I_avg × 1/f_s`, so a rate change rescales it (at the 2 MS/s
  stretch the per-conversion charge roughly halves while the peak does not,
  tightening `Z_vdd,max` to ≈ 1.6 Ω — not further resolved here, mirroring
  DR-0002's and DR-0026's own 2 MS/s notes); and the 0.5 LSB denominator is
  `V_REF/2048`, so a full-scale change rescales `C_dec,min`.
- **The `sim/adc-rail-current/` record is cited, not re-run.** Its numbers
  are used exactly as committed, including the two directions in which its
  own manifest says the peak is a *lower* bound (the ideal-XSPICE sequencer
  draws no current; the 2 ns timestep cannot resolve the spike). Both push
  the real requirement **up**, so every figure in this record is a floor.

## Spec lines affected

- `README.md#target-specification` — Supply — changed. The
  `V_DD = 3.3 V ±10 %` value is untouched; the row gains the drive
  requirement it did not carry: external decoupling ≥ 40 nF at the `V_DD`
  pin, effective source impedance ≤ 3 Ω in the switching band, and a
  required (unsized) on-die local decoupling term inside `ADC_BLOCK` —
  mirroring the Reference (DR-0002) and `V_CM` (DR-0026) rows, which already
  carry theirs.
- `spec/<supply-budget>.md#vdd-transient-decoupling` (pending #1's successor
  — no ratified `spec/` file carries supply budgets today; the ratified
  table lives in `README.md`, and DR-0034 names the same pending anchor for
  the static half) — `V_DD` transient decoupling — new (`—` -> `ΔQ_conv ≤
  40.120 pC; C_dec ≥ 40 nF external; Z_vdd ≤ 3 Ω; on-die local decoupling
  required inside ADC_BLOCK, unsized`).
