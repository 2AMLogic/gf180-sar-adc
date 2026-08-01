# DR-0009: No redundancy — strict binary weighting, 10 trials, no digital correction

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #11
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #3, #4, #8, #9, #11, #12, #13; DR-0003 (M = 16), DR-0005
  (parallel output register), DR-0006-cdac-switching-scheme (511 binary weights
  per side), DR-0007 (synchronous logic); `spec/prior-art-survey.md` §4.5
  (closing paragraph), `spec/cdac-sizing-memo.md`;
  `sim/` record `20260731-231537-1ee5578` (`sim/cdac-bit-settling/`)

## Context

`spec/prior-art-survey.md` §4.5 flags redundancy / non-binary weighting as
"cheap insurance against incomplete DAC settling and comparator metastability",
notes that *both* surveyed sky130 12-bit designs use it and that the sky130
10-bit reference gets it via MSB splitting into sub-caps with adder correction,
and then explicitly declines to decide: it is "orthogonal to sync-vs-async and
should be decided on its own merits", deferred to #8/#11. #8 landed
DR-0006-cdac-switching-scheme with a **strictly binary** 511-weight array per
side without ruling on redundancy, so the call is this issue's, and leaving it
unstated would mean the array topology had been fixed by default rather than by
decision.

Redundancy buys two distinct things, and they have to be assessed separately
because this block's evidence says opposite things about them:

1. **Tolerance of incomplete DAC settling** — an early bit trial decided before
   the array has settled produces a residue the later, overlapping trials can
   still correct.
2. **Tolerance of a near-metastable comparator decision** — a trial whose
   decision is wrong (not merely late) is recoverable if later trials overlap
   its weight.

## Decision

**No redundancy and no non-binary weighting.** The array stays strictly binary
(DR-0006-cdac-switching-scheme: weights `2^8..2^0` plus a terminating unit),
the conversion is exactly **10 trials in 10 clock cycles**, and the output word
is the **decisions themselves, MSB first** — there is no correction arithmetic
of any kind between the decision flip-flops and the parallel output register
(`design/sar-logic/sar_reference.py::code_of`, asserted in
`sim/tests/test_sar_logic.py::test_code_is_the_decisions_themselves`).

### Reason 1 — the settling motivation is measured to be absent

Redundancy against incomplete settling assumes there is settling error to
redistribute. On this array there is not. `sim/cdac-bit-settling/` record
`20260731-231537-1ee5578` probes the top plate at 62.5 ns (the 1 MS/s bit
cycle) and at 31.25 ns (the 2 MS/s stretch cycle) for bit trials spanning the
whole weight range (`w` = 1, 16, 64, 256, both switching directions at the
predicted-worst weight), over **all 117 PVT points**. The largest residual
error anywhere in that grid is **1 × 10⁻⁴ mV** (the deck's reporting
resolution; most points read exactly 0.0), at both probe times, against a
0.5 LSB bound of 1.61 mV — four orders of magnitude of margin, measured, not
budgeted. The array is many time constants
settled before the comparator is even clocked, at the slow corner, at the
stretch rate.

Adopting redundancy to protect against settling error would therefore be paying
its full cost against a measured zero. This is the specific case where the
survey's "cheap insurance" framing does not transfer: the insurance is cheap
relative to the risk *in general*, and the risk here has been measured out of
existence.

### Reason 2 — the metastability motivation is real, and the cost is not cheap here

Redundancy does help against a near-metastable decision, and that risk is **not**
zero (see Consequences). But "cheap" is a property of the design it is added to,
and in this design it is not:

- **It costs clock cycles, and `M` is not free.** DR-0003 ratifies `M = 16`, and
  DR-0007 shows `M = ACQUIRE_CYCLES + N_BITS` exactly: 16 = 6 + 10. Any
  redundant scheme needs ≥ 1 extra trial, so it either shortens the acquire
  window (6 cycles → 5, a 17 % cut to the track time #10 and DR-0001 budget
  against) or raises `M` to 17–20, which raises `f_clk` to 17–20 MHz at 1 MS/s
  and 34–40 MHz at the stretch. Either is a superseding change to a **ratified**
  record, not a local addition.
- **It changes the ratified array.** Sub-radix-2 weighting or MSB splitting
  replaces DR-0006-cdac-switching-scheme's binary 511-weight array and the
  exact LSB arithmetic that record's table turns on
  (`w = 1` resolving exactly one LSB of each mode's own full scale). #8's
  `spec/cdac-sizing-memo.md` sizes against that array. A redundancy decision
  taken here would reopen both.
- **It costs digital correction hardware DR-0005 does not scope.** A sub-radix-2
  search needs an adder tree between the decisions and the output word. DR-0005
  scopes a 10-bit parallel *register*, and this design's output path is a
  register with no arithmetic in it at all — which is what makes the code check
  in `sim/sar-logic/` a direct assertion on the decisions rather than on a
  correction result.

Three ratified records reopened plus an adder tree, to insure against a risk the
same evidence base has not yet shown to exist, is not the cheap end of the
trade.

### Reason 3 — the timing margin that would otherwise force it is present

`spec/prior-art-survey.md` §4.2 budgets ~22 ns of the 62.5 ns bit cycle, leaving
~40 ns; DR-0007 records the measured version of both halves. Redundancy is the
standard answer when a design must decide *before* the analog has resolved. This
one does not have to.

## Alternatives considered

- **Sub-radix-2 (non-binary) weighting across the whole array** — not chosen.
  The most general scheme, and the one that would most cleanly absorb both a
  late settle and a wrong early decision. Rejected on cost, not on merit: it
  reopens DR-0003 (extra cycles), DR-0006-cdac-switching-scheme (array weights)
  and DR-0005 (correction arithmetic in the output path) simultaneously, against
  a settling error measured at the numeric floor.
- **MSB splitting with adder correction**, as the sky130 10-bit reference does
  `[O: UAH-IC-Design-Team/sky130-10-bit-SAR-ADC]` — not chosen. Cheaper than
  full sub-radix-2 (only the MSB block is split) and it is a proven
  open-source pattern, but it still adds trials, still needs the adder, and it
  splits precisely the block whose settling `sim/cdac-bit-settling/` measures as
  *worst* (`w = 256`) and still finds fully settled with margin. It buys
  protection where the measurement says protection is not needed.
- **One redundant LSB-side trial only** (a cheap partial: repeat the last trial
  at half weight) — not chosen. It is the smallest version, but it protects the
  *least* valuable bits: a near-metastable decision on an early, high-weight
  trial is the one that costs many LSB, and an LSB-side redundant trial cannot
  correct it. Protecting the MSB side is what costs real cycles.
- **Defer the decision to #13** — not chosen. Deferring is itself a decision
  here: DR-0006-cdac-switching-scheme already fixed a binary array and #11 is
  now fixing a 10-trial sequencer, so "defer" would mean shipping the no-
  redundancy design without ever writing down that it was chosen. The survey
  asked for a decision on the merits; this is it, with an explicit revisit
  trigger below instead of silence.

## Consequences

- **#8's array stays as DR-0006-cdac-switching-scheme ratified it** — strictly
  binary, 511 weights plus a terminating unit — and
  `spec/cdac-sizing-memo.md`'s sizing needs no revision.
- **#12's bit-cycle budget stays 10 trials in 10 cycles** at `M = 16`, with the
  acquire window intact at 6 cycles.
- **#13 verifies a converter with no digital correction path**: measured INL/DNL
  is the array's own linearity, undiluted by correction, which makes those
  numbers a more direct statement about the CDAC than they would otherwise be.
- **Bad consequence, stated plainly (1): a near-metastable comparator decision
  produces a permanent code error.** With no redundancy and no handshake
  (DR-0007), a decision that has not resolved by the capture edge is latched as
  whatever the flip-flop input happens to be, and nothing downstream corrects
  it. The mitigation is margin only. The probability is a comparator property
  this repo has not yet measured — #4/#9 own it — so **this record states a
  residual risk it does not quantify**, which is the honest position rather than
  a reassuring one.
- **Bad consequence, stated plainly (2): the design has no headroom for a slower
  DAC.** The settling evidence that removes reason 1 is a *schematic-level*
  result. Post-layout extraction (#17) adds routing resistance and parasitic
  capacitance to the bottom-plate drivers, and if extracted settling stops
  reading at the numeric floor, redundancy is one of the levers this record has
  just closed off. Reopening it after layout is the expensive moment to do it.
- **Bad consequence, stated plainly (3): this diverges from the surveyed
  open-source references.** All three 10–12-bit open-source SARs the survey
  examined use some form of redundancy. Being the odd one out is defensible only
  as long as the settling measurement above holds; if it stops holding, the
  divergence becomes a defect.

### Revisit trigger (write a superseding record if any of these fire)

1. **#4/#9 measure a comparator metastability window** that, at the 62.5 ns bit
   cycle, implies a code-error rate above the ENOB budget's noise allowance.
2. **#17's extracted settling** stops reading inside 0.5 LSB at the 62.5 ns
   probe at any PVT corner.
3. **The rate target moves above 2 MS/s**, shrinking the bit cycle below the
   point where reason 3 holds.

## Spec lines affected

- `README.md#target-specification` — Resolution row — clarified (no value
  change): 10 bits are resolved in exactly 10 bit trials with no redundant
  trials and no digital correction, so the output word width equals the trial
  count. The table's 10-bit value is unchanged; what this record fixes is that
  nothing stands between the decisions and the code.
