# DR-0014: Sample on the bottom plate — top-plate parasitic loading divides the DAC step but not the sampled input, and only moving the sampling phase removes it

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-02
- **Decided by**: Builder agent, issue #53
- **Supersedes**: [DR-0011](DR-0011-cdac-switching-scheme.md) — same question
  (where the input is sampled, and what switching scheme runs on the array).
  Everything DR-0011 decided **except the sampling phase** is re-ratified
  unchanged by this record and is restated in the Decision so a reader needs
  one record, not two, to know what is in force.
- **Superseded by**: (none while this record stands)
- **Related**: #13, #17, #53, #58 (the implementation and re-run this record
  requires; nothing here is verified until it lands),
  [DR-0006](DR-0006-spec-ratification.md),
  [DR-0007 (comparator)](DR-0007-comparator-topology.md),
  [DR-0007 (track switch)](DR-0007-track-switch-topology.md),
  [DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md),
  [DR-0013](DR-0013-input-pin-charge-split.md),
  `spec/testbench-suite-memo.md` §3.5/§11,
  `sim/top-plate-cpar/records/20260802-033948-75497e8.md` (the mechanism,
  measured), `sim/adc-inl-dnl/records/20260801-144717-d407dfe.md` (the
  converter-level consequence), `sim/adc-enob-fft/records/20260801-180501-845f76e.md`,
  `sim/adc-power/records/20260801-134035-7d48a44.md`

## Context

The first transistor-level full-converter campaign (#13) fails **three**
ratified rows, and all three are one mechanism:

| Row | Target | Measured (nominal, schematic) |
|---|---|---|
| INL | < 1 LSB | **−4.494 LSB** (`ss_-40c_2.97v`, transition 384) |
| ENOB @ Nyquist | > 9.0 | **8.005 bits** (`ss_125c_2.97v`) |
| SFDR @ Nyquist | ≥ 62 dB | **52.01 dB** (`ss_125c_2.97v`) |

plus a converter-level systematic gain error of **29.2–33.8 LSB (2.85–3.30 %
of full scale)** that no row in `README.md#target-specification` covers at all.

**Why one mechanism.** [DR-0011](DR-0011-cdac-switching-scheme.md) samples the
input **onto the top plate**, so the sampled input arrives on that node
undivided while every subsequent DAC step is divided against everything else
hanging on it:

```
V_top = V_in + Σ_j w_j·C_u·ΔV_bottom,j / (C_arr + C_par)
```

The `C_par/(C_arr + C_par)` deficit applies to the second term and not the
first, so it is a gain error; and because `C_par` is made of MOS devices whose
capacitance moves with the node voltage, the deficit is **code-dependent**,
which is a linearity error the endpoint fit cannot remove. DNL passes at
0.483 LSB while INL fails by 4.5× — the signature of a smooth bow, not a
per-step error — and the FFT sees that bow as THD of −50.2 to −53.3 dBc, with
SFDR tracking it within ~2 dB. Composing the separately measured noise terms
into the spectrum moves ENOB by 0.002 bits (`spec/testbench-suite-memo.md`
§11.3): the block is distortion-limited, not noise-limited.

**The mechanism is now measured, not inferred.** Until this record, `C_par`
was a number *backed out of* the gain error and attributed by assumption to
"a preamplifier input pair plus routing". `sim/top-plate-cpar/` measures the
divider directly, by quasi-static C(V) extraction on the top-plate node over
the 63-point capacitor-corner grid, and decomposes it. Three findings, all of
which change the answer:

1. **The divider is confirmed independently.** `C_arr` measures 8827.13 fF —
   the ratified 8.827 pF to six figures — and `C_par` measures **240.9–301.4 fF**
   at V_cm, giving a divider error of **2.42–3.66 % (mean 2.94 %)**. The
   end-to-end converter measures 2.85–3.30 %. Two unrelated testbenches, the
   same number.
2. **The sampling switch, not the comparator, is the larger half of `C_par`.**
   At `tt_27c_3.30v` and V_cm: sampling switch **194.3 fF (66 %)**, comparator
   input **99.5 fF (34 %)**. In hold, [DR-0013](DR-0013-input-pin-charge-split.md)'s
   dummy-compensation devices sit with source and drain both tied to the top
   plate — i.e. the ratified charge-injection fix is a pair of permanently
   connected MOS capacitors on the sampling node. No analysis in this repo had
   attributed that before, and it is why the "shield the comparator" option
   below cannot work. (The deck's own control: the three loads measured
   separately sum to the fourth branch, where all three sit on one node, to
   within 3.2 × 10⁻⁵ %.)
3. **The voltage dependence is largest at balance — where the decisions are
   hardest, and in a form differential operation does not cancel.** The
   comparator's input capacitance measures 110.99 fF at `tt_-40c_3.30v` and
   52.76 fF at `tt_-40c_3.63v`, at the *same* 1.65 V probe: same process, same
   temperature, 2.1× the capacitance, and the only difference is that 1.65 V is
   `V_cm` at one supply and 165 mV off it at the other. The peak sits at
   `v_p = v_n`, so it is an **even** function of the residue: in differential
   mode both sides rise into it together and it appears in common, not
   differentially. (A second, smaller structure is visible in the same data —
   the input capacitance rises again as the node approaches the positive rail,
   e.g. 157.9 fF at 2.70 V on a 2.97 V supply, where the input device is pushed
   into triode. That one *is* odd in the node voltage and would cancel
   differentially. The balance peak, the larger of the two, does not.) Across
   the probed excursion the divider varies by **0.396–1.690 pp (mean 0.848)**.

**That variation is exactly the INL failure, in arithmetic taken straight from
the committed record.** At `tt_-40c_3.30v`, `terr_t1_lsb = −13.5686` and
`terr_t1023_lsb = +17.7497`. Referred to mid-scale, the lower half of the
transfer curve is short by 13.5686/511 = 2.655 % and the upper half by
17.7497/511 = 3.473 %: **the two halves have gains that differ by 0.818 pp**,
against the 0.85 pp mean divider variation `sim/top-plate-cpar/` measures over
the same excursion. A curve whose halves have different gains cannot be
straightened by any single scale factor, and what the endpoint fit leaves
behind is the measured bow.

## Decision

**Sample on the bottom plate. Keep everything else DR-0011 decided.**

The array, the switching scheme, the unit cap, the free MSB and the
mode-dependent bit-trial sequence are re-ratified unchanged. What changes is
the sampling phase, and one switch is added per side:

| Item | DR-0011 | This record |
|---|---|---|
| Switching scheme | MCS / V_cm-based, differential | **unchanged** |
| Unit positions per side | 2^(N−1) = 512 (511 switched + 1 terminating) | **unchanged** |
| `C_u`, `C_arr` | 17.24 fF, 8.827 pF/side | **unchanged** |
| Free MSB | yes | **yes** — see the derivation below |
| Bit-trial sequence, per mode | one side single-ended, both differential | **unchanged** |
| Rails | `V_REF`, `V_cm`, `GND` | **unchanged** |
| **Sampling** | **input onto the top plate through one switch per side** | **input onto the bottom plates through each cell's switch network; the top plate is held at `V_cm` by a new per-side switch, which opens FIRST** |

Concretely, per side: each bottom-plate cell gains a fourth leg to `V_in`
(a fourth T-gate and its local driver, alongside the existing `V_cm` /
`V_REF` / `GND` legs), and the top plate gains one switch to `V_cm`. The
sampling sequence becomes (1) top-plate switch closed, all bottom plates on
`V_in`; (2) **top-plate switch opens** — this is the sampling instant;
(3) bottom-plate switches move from `V_in` to `V_cm`; (4) trial 1 decides.
Step (3) fits inside DR-0003's existing 4-clock sample phase, so `M = 16` and
the 1 µs conversion are unchanged.

### Why this removes the term, structurally rather than by reduction

With the top plate held at `V_cm` during sampling and released first, charge
conservation on the top node gives, at any point in the conversion,

```
V_top = V_cm + [ C_arr·(V_cm − V_in) + Σ_j w_j·C_u·ΔV_bottom,j ] / (C_arr + C_par)
```

The sampled input and the DAC steps are now in the **same** numerator, over
the **same** denominator. Write it as `V_top = V_cm + f(X)`, where `X` is the
bracket and `f` is monotonic because a capacitance is positive. The comparator
decides `sign(V_top,p − V_top,n) = sign(f(X_p) − f(X_n)) = sign(X_p − X_n)`
for identical sides — and `sign(X_p)` in single-ended mode, where the pinned
side sits at `f(0) = 0`. **`C_par` cancels from the decision: its magnitude,
its voltage dependence and its PVT movement all drop out**, to the accuracy
with which the two sides match. This is not an attenuation of the error, it is
a cancellation, and it is the same reason `README.md` note **[d]** already
lists bottom-plate sampling as one of the three mandatory answers to switch
charge injection.

**The free MSB survives, and this is the load-bearing correction to #53's own
framing** (which listed re-opening DR-0011 as "likely the most expensive
option, since DR-0011's free MSB and its `C_in` figure both depend on it").
After step (3), `V_top,p − V_top,n = −k·(V_inp − V_inn)` with
`k = C_arr/(C_arr + C_par)`: the sign of the sampled differential input, with
no array switching, which is DR-0011's free MSB. Trials 2..10 then move
weights 256..1 exactly as DR-0011 specifies, each step carrying the same `k`,
so the correction range and the residue it must cover scale together and the
weight-1 trial still resolves exactly one LSB. **The array is not re-sized,
the switching energy per trial is not changed, and `C_in` stays at 8.827 pF
per side.** The free MSB is a property of sampling the differential input onto
the array and comparing before any switching — not of which plate it lands on.

## Alternatives considered

- **Compensate: upsize the array (or add a linear cap) until the divider is
  small enough.** Not chosen. It works arithmetically and fails on cost. The
  divider scales as `1/C_arr`, so bringing the −4.494 LSB bow under the 1 LSB
  row needs about **5× the array**: 44.1 pF per side. (a) **Area** — at the
  measured 2.0 fF/µm² MiM density that is 44.1 × 10³ µm² of plate area for the
  two sides, **44 % of the ratified < 0.1 mm² row on capacitor plate alone**,
  before switches, drivers, comparator, routing or the guard structures a
  matched array needs; DR-0011 chose MCS *for* a 2× array reduction, and this
  gives back five times what that bought. (b) **Rate** — the worst bit trial's
  settling time constant is 570 Ω × 2.207 pF = 1.258 ns, i.e. 24.8 τ inside the
  31.25 ns settling half of the bit cycle; 5× the capacitance makes it 4.97 τ,
  a 0.69 % residual on a 256 LSB step = 1.8 LSB of settling error, so the
  bottom-plate T-gates must be scaled ~5× too, and their gate-drive power with
  them. (c) **Power** — the three array-charge terms (CDAC + drivers 12.5 µW,
  V_REF 32.9 µW, V_cm 14.4 µW) scale with `C_arr`: 59.8 µW becomes ~299 µW, so
  the total goes from 157 µW to ~400 µW, still inside the < 1 mW row but at the
  edge of the < 500 µW stretch, and that is before the wider drivers. (d) And
  it **does not finish the job**: at 5× the residual gain error is still 0.66 %
  = 6.8 LSB, thirteen times either existing gain row, so a spec amendment is
  still needed on top of the area and power. Adding a *linear* compensating
  capacitor on the top plate is worse again: it dilutes the nonlinear fraction
  but **increases** the divider, trading gain error for linearity in the wrong
  direction.
- **Buffer or shield the top plate.** Not chosen, and the measurement is what
  rules it out rather than a preference. The comparator is **34 %** of `C_par`
  (99.5 fF of 293.8 fF at `tt_27c_3.30v`); the other 66 % is DR-0013's own
  dummy-compensation devices sitting on the same node. A perfect buffer with
  zero input capacitance would therefore take the divider from 3.22 % to
  2.13 % — a 34 % improvement against a term that needs an ~80 % one — while
  costing exactly what the block can least afford: a buffer in front of the
  comparator adds its own input-referred noise and offset to the block DR-0007
  identifies as the ENOB-dominant one, adds static current to the block already
  drawing 76 % of the power total, and presents its own voltage-dependent gate
  capacitance to the node it was supposed to unload. Removing the *switch's*
  share instead means removing the dummy compensation, which re-opens
  DR-0013's charge-injection split — the very row DR-0012 created.
- **Amend the spec: add a top-plate gain-error row, on the ratiometric
  argument.** Not chosen, and this is the option #53 flagged as "the cheapest
  and may well be the right one". Three reasons it is not. (a) **It does not
  reach the failures.** A pure gain error is invariant under the INL, ENOB and
  SFDR definitions this table uses; INL is evaluated after the endpoint fit
  removes gain, so a constant scale factor would leave INL at zero. The
  measured INL is −4.494 LSB. Amending the gain rows would leave three failing
  rows untouched, and widening *those* to fit is precisely what CLAUDE.md
  forbids. (b) **The ratiometric argument does not transfer.** Note **[e]**
  excludes reference accuracy because full scale is `V_REF` *by construction*
  and the user knows their own reference. `C_arr/(C_arr + C_par)` is not
  ratiometric to anything the user can see: it is a capacitance ratio that
  measures 2.42–3.66 % over PVT, so a user who calibrates the gain at one
  operating point is left with the **~1.2 pp of PVT spread**, ≈ 12 LSB, still
  uncalibrated — by itself larger than every other error row in the table
  combined. (c) A 3 % row would be **66× the two existing gain rows** and
  their published ≤ 1.0 LSB total; a table carrying both would not be a
  specification, it would be a disclosure.
- **Do nothing structural and re-measure in differential mode first.** Not
  chosen as the resolution, though it is worth running (see Consequences). The
  suite ran single-ended, and DR-0011's own title says *differential*, so the
  question is fair. But differential operation cancels only the **odd** part of
  `C_par(V)`, and finding 3 above shows the dominant variation — the
  comparator's balance peak — is **even** in the residue: both top plates
  approach `V_cm` together as the residue shrinks, so both input capacitances
  rise together and the divider moves in common. Nor does differential
  operation touch the constant 2.94 % divider at all. It is a diagnostic that
  will refine the split, not a fix.
- **Fall back to conventional bottom-plate charge redistribution** (DR-0011's
  own named fallback). Not chosen: it is bottom-plate sampling *plus* giving up
  MCS, at 2× the array (2^N units per side, 17.65 pF, doubling `C_in` and
  therefore re-opening DR-0013's drive contract) and 8× the switching energy.
  The evidence indicts the sampling phase, not the switching scheme, so paying
  for both is paying for a fault that was not found.

## Consequences

- **This record does not close the failing rows — it says how they will be
  closed, and it changes no ratified value to make anything pass.** INL, ENOB
  and SFDR stay at < 1 LSB, > 9.0 bits and ≥ 62 dB, and the converter as built
  today misses all three. That failure stands recorded in
  `sim/adc-inl-dnl/`, `sim/adc-enob-fft/` and `spec/testbench-suite-memo.md`
  §11 until a re-run says otherwise. No spec row is added, widened or
  relaxed by this record.
- **The immunity argument above is a derivation, not a measurement, and
  nothing in this repo has yet simulated the proposed sampling phase.** That
  is the largest risk this record carries and it is stated first among the
  consequences, not last. **#58** must implement the phase in
  `design/adc-top/` and re-run all three `sim/adc-*/` decks (new record ids,
  append-only) before any row is claimed closed, and must specifically measure
  the four things the derivation assumes away: the top-plate switch's own
  charge injection and its side-to-side mismatch, the bottom-plate input
  switches' injection after the top switch has already opened, the fourth
  leg's effect on bit-trial settling, and second-order residue from `C_par`
  mismatch between the two sides.
- **Comparator offset and noise are referred up by `1/k` ≈ 1.031**, because
  the residue now reaches the comparator attenuated where before the sampled
  input did not. The noise cost is nil against DR-0007's ~10× margin
  (0.0488 LSB composed). The **offset cost is real and tight**: note **[e]**'s
  3σ untrimmed offset of 1.8 LSB becomes ≈ 1.86 LSB against a 2 LSB row. It
  fits, with less margin than before, and #14's Monte Carlo re-run has to be
  read against the new figure rather than the old one.
- **[DR-0013](DR-0013-input-pin-charge-split.md) is not superseded, but its
  evidence is invalidated and its dummy ratio is probably obsolete.** The
  sampling instant is no longer defined by the input switch, so that switch's
  input-dependent charge injection — the whole subject of DR-0013 and of the
  `Gain error, systematic` row DR-0012 created — is absorbed by the bottom
  plates being driven immediately afterwards. The row's ≤ 0.5 LSB target does
  not change; the 0.421 LSB measurement behind it was taken on a different
  sampling phase and must be re-taken. Removing the dummy devices, if the
  re-measurement allows it, is what takes 194 fF off the top plate — which no
  longer matters for gain, but does matter for bit-trial settling.
- **Two published Input-structure numbers must be re-measured, and one must
  not change.** `C_in` stays 8.827 pF per side (the array is untouched), so
  DR-0013's `R_source × (C_pin + C_in) ≤ 30 ns` contract and the ≥ 5.3 MHz
  T/H bandwidth stand as published. The series switch `R_on` (156–570 Ω) does
  not: the input now reaches the array through nine parallel cell T-gates
  instead of one dedicated switch. Until it is re-measured the Input-structure
  row's `R_on` figure is stale, and this record says so rather than leaving a
  reader to infer it.
- **#11 (SAR logic) inherits a fourth control leg and a two-phase sample.**
  Each cell's decode grows from `rel`/`sel_hi`/`sel_lo` to four one-hot legs,
  and the sequencer must open the top-plate switch one sub-phase before the
  bottom plates leave `V_in`. Both fit inside DR-0003's existing 4-clock sample
  phase and `M = 16`; neither is free, and the one-hot invariant
  `sim/sar-logic-functional/` checks has to be re-derived for four legs.
- **Area goes up, modestly and in the switches rather than the capacitors.**
  Nine extra T-gates and nine extra local drivers per side, plus one top-plate
  switch per side, against an array whose plate area is unchanged. That is the
  price of this option and it is roughly a thirtieth of what the compensation
  option costs; it has not been floorplanned, and #16 owns that.
- **#17 (post-layout re-run) gets a sharper job.** Under top-plate sampling an
  extracted `C_par` would have moved the gain error and the bow directly;
  under bottom-plate sampling it should move **neither**, to first order. That
  makes #17's extracted `gain_err_lsb` a real test of this record rather than a
  number to record — if extraction still shows a percent-level gain error, this
  decision is wrong and should be superseded rather than patched.
- **`sim/top-plate-cpar/` outlives the decision it was written for.** It is the
  cheapest instrument in the repo for "what is on that node" — 63 PVT points in
  minutes, with an internal additivity control — and its numbers are a **lower
  bound**, since routing and MiM top-plate parasitics are absent at schematic
  level. #17 should re-run it on the extracted netlist first, before the
  expensive converter decks.

## Spec lines affected

- `README.md#target-specification` — **none changed**. No row is added, no
  target is widened, no condition is relaxed. This is deliberate and is the
  point of the record: the three failing rows are met by fixing the design, not
  by moving the line. Stated explicitly because #53's acceptance criteria make
  a README change conditional on the resolution chosen, and this resolution
  does not take it.
- `README.md#target-specification` — Input structure row — **evidence stale,
  value unchanged**: the published series-switch `R_on` of 156–570 Ω is
  measured on a dedicated top-plate sampling switch that this record removes.
  `C_in = 8.827 pF` per side and the ≥ 5.3 MHz T/H bandwidth are unaffected.
  Re-measurement rides with the design change, not with this record.
- `spec/decision-records/DR-0011-cdac-switching-scheme.md` — **superseded**:
  Status and Superseded-by back-pointer set to this record, per
  `spec/decision-records/README.md` § "Superseding a ratified record". Nothing
  else in DR-0011 is edited; its switching-scheme decision is carried forward
  verbatim in the Decision table above.
- `spec/decision-records/DR-0013-input-pin-charge-split.md` — **not
  superseded, evidence invalidated**: the drive contract stands; the
  0.421 LSB `Gain error, systematic` measurement behind it was taken on the
  superseded sampling phase and must be re-taken before that row is claimed
  again.
- `spec/testbench-suite-memo.md` §3.5, §11.2, §12.8 — **clarified**: the
  finding those sections defer to #53 is adjudicated here; the attribution of
  `C_par` to the comparator is corrected to the measured 34 % / 66 % split.
