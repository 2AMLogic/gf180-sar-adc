# DR-0033: `sf_27c_2.97v`'s non-convergence is an attributed coverage hole of the `tie` deck, not a reason to change its stimulus or its comparator

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-21
- **Decided by**: Builder agent, issue #345
- **Supersedes**: [DR-0029](DR-0029-tie-loop-decision-chatter.md) — same
  question (what the `tie` loop's decision chatter is, and what to do about
  it), decided on a strictly larger evidence base. DR-0029's disposition of
  the stimulus, the comparator and `CMP_OUT_RC` is carried forward unchanged;
  its characterisation of the chatter regime, its statement of where the
  chatter's exposure lies, and its "no evidence record is invalidated"
  consequence are replaced.
- **Superseded by**: (none while this record stands)
- **Related**: #345 (this record's own issue), #332 (the abort, root-caused),
  #337 (the sibling bound "failure", root-caused), #303 (the grid this
  decides the coverage of), #322 (DR-0029's own issue), #310, #296, #327
  (DR-0031 part 2's execution), #341 (the harness defect that lets an
  aborted point still print a number), #343 (`lt`/`xl`'s aborts — **not**
  this record's business), #363 (the citation reconciliation this record
  gates on its own sign-off),
  [DR-0008](DR-0008-sar-logic-synchronous.md) (the record that defines the
  `tie` loop and the near-metastable consequence it measures — **not**
  superseded, see Spec lines affected),
  [DR-0010](DR-0010-mixed-signal-sim-strategy.md) (the bisected 50 ns / 52 ns
  `cmp_delay` boundary candidate 2 would invalidate),
  [DR-0031](DR-0031-power-up-first-conversion-validity.md) (whose mechanism B
  explains #337, and whose part 2 is the correction #327 executes),
  `sim/sar-logic-timing-gates-tie/investigations/20260921-issue-332-quiescent-supply-row-nonconvergence.md`
  (the measurement this record decides from),
  `sim/sar-logic-timing-gates-tie/investigations/20260921-issue-337-tie-code-deviation-decode-transient.md`
  (the measurement that retires the other half of the trigger),
  `sim/sar-logic-timing-gates-tie/records/20260920-020802-2043286.md` (the
  45-point grid whose coverage this record scopes),
  `sim/sar-logic-timing-gates-tie/testbench/tb.json` (the manifest whose
  claim and bounds this record leaves **unchanged**)

## Ratification note

Both this record and DR-0029 are `proposed`. **DR-0029 governs until both are
signed off**; the `Superseded by` back-pointer added to it is prospective and
says so in its own text. Nothing downstream — `tb.json`'s notes,
`design/sar-logic/rtl/README.md`, the probe scripts — may cite this record as
in force before that, which is why this issue changes none of them (see Spec
lines affected).

## Context

DR-0029 nominated its own supersede trigger: *"If #303's remaining coverage
finds a corner where `tie_conv_period_ns` or `tie_code_deviation` actually
fails **and** the chatter is implicated, this record is the one to supersede —
with the measurement, not with a relaxation."* #303's `tie` grid ran, and two
candidate firings arrived. Only one of them is real, and saying which is the
first thing this record has to do.

**#337 does not fire the trigger, and this record records that as a finding
rather than passing over it.** Six of the 29 scored points report
`tie_code_deviation = 512` against a `max 1.0` bound. Measured
(`…-issue-337-tie-code-deviation-decode-transient.md`), the *settled* code at
every conversion of every one of the six is **511 or 512** — inside the bound,
and exactly the "either adjacent code answers an exact tie" behaviour the
bound exists for. The 512 is read at the single accepted timepoint where
`drdy` crosses mid-rail while the ten code bits are still moving; the word
decoded there is `0`, which is neither the code the register held nor the one
it is loading. That is DR-0031's mechanism B, and its correction is DR-0031
part 2, whose execution is #327. The chatter is implicated in the *carries*
(a loop pinned on the threshold latches 511 on one conversion and 512 on the
next, so `tie` sees up to 8 ten-bit carries in 8 conversions — more than any
other loop in the family) but not in the failure. **`tie_code_deviation` has
never failed on a settled code.**

**#332 fires it, on a reading that must be stated plainly rather than
assumed.** At `sf_27c_2.97v` the run does not *fail* a bound — it aborts
(`Timestep too small; time = 3.99655e-07, timestep = 6.25e-21: trouble with
node "vvdd_gate#branch"`) at 399.655 ns — before `tie_a`, the second `drdy`
rise that `tie_conv_period_ns` is defined from.
`tie_conv_period_ns` is therefore `n/a`, and the `tie_code_deviation = 0` the
grid prints at that point is not a measurement at all: `dev_tie` is an
unbounded-right `meas tran … MAX v(tie_dev) FROM=0.1u`, so ngspice emits a
number from a 400 ns truncated transient in which no conversion completed
(the harness defect is #341). An ERROR is not a FAIL, and DR-0029's trigger
says "actually fails". **What fires the trigger is the stronger condition the
trigger was written to catch**: a corner of the ratified box at which this
deck can deliver *neither* claim, with the chatter as the implicated
proximate driver. That is met, once — not, as #345 supposed, twice.

And the trigger fires on a fact DR-0029 did not have, which is why a new
record and not a re-reading is required. DR-0029 measured the `tie`
differential at "~1e-7 V — the solver's own noise floor", and built its whole
argument on the model's resolution being set by ngspice's node-voltage
tolerance `vntol` (1e-6 V). At this abort, `--numdgt 17` resolves what the
default probe could not: over the last 97 accepted timepoints the
differential is **0 … 3.8 × 10⁻¹³ V (0 … 1690 ulp of a 1.485 V node)**, median
3.4 × 10⁻¹⁴ V, with **two accepted timepoints at which the two nodes are
bit-identical**. That is seven orders of magnitude below `vntol` and at the
representation floor of the IEEE-754 double holding the node voltage. **There
is no tolerance left to tighten**, and the sign the comparator reads is the
rounding of the last LU update — for any timestep, forever.

## Decision

**The `tie` loop's stimulus, comparator model, output network and bounds all
stand unchanged; `sf_27c_2.97v`'s non-convergence is ratified as an
*attributed coverage hole* of this deck's PVT grid — a point the deck cannot
score, priced as lost coverage of a claim rather than engineered away.**
Concretely:

1. The `tie` loop's input stays `dc {vcm}` — pinned **exactly** on the
   threshold, with no offset of any magnitude. (DR-0029 item 1, carried;
   re-argued below on the new measurement, not merely restated.)
2. The comparator stays the continuous-time hard ternary
   `v(topp) > v(topn) ? vdd_val : 0`, evaluated at every accepted timepoint
   and **not** strobed, identically for all five loops and the rung-1 ideal
   decks. (DR-0029 item 2, carried unchanged.)
3. `CMP_OUT_RC` stays `("1k", "100f")` (tau = 100 ps), pinned from below by
   #296 and from above by DR-0029, and now also pinned against #332's three
   completing `--cmp-rc` rows at one corner. (DR-0029 item 3, carried.)
4. `sim/sar-logic-timing-gates-tie/testbench/tb.json`'s `claim`,
   `tie_code_deviation` and `tie_conv_period_ns` are unchanged, in wording
   and in value; no manifest gains a solver `.options` entry. (DR-0029
   item 4, carried.)
5. **New — an ngspice non-convergence on this deck is a coverage hole, not a
   result and not an accepted property, until it is attributed.** A point
   that ERRORs may be excluded from a `tie` claim's coverage only when a
   committed `investigations/` document names its mechanism on that point's
   own run. Until then it is an **open defect**, not a recorded property.
   `sf_27c_2.97v` is discharged by #332. The same grid's **15 timed-out
   points are not discharged**, and #332 explicitly declines to assume they
   are free of the same state.
6. **New — the `tie` claims are scoped to the points that scored.** DR-0008's
   near-metastable consequence is substantiated over **29 of 45** points of
   the ratified box, not over the box. Any signoff text, spec row or record
   citing `tie_conv_period_ns` or `tie_code_deviation` from
   `20260920-020802-2043286` must carry that `29/45` in the same breath as
   the number.

The reasoning, stated once: **DR-0029's disposition was right and its account
of why was wrong in the way that matters.** The chatter is not "at the
solver's noise floor"; it is at the floating-point floor, and it does not
endanger the DUT — it endangers the matrix. A model property that costs a
point of solver coverage is priced as coverage. It is not paid for with the
experiment's own definition.

## What this record rests on, and what it does not measure

**This record takes no new measurement, and that is a consequence of its own
decision, not an omission.** Candidates 1 and 2 would each have required a
fresh corner run to ratify (issue #345's acceptance criteria say so); this
record ratifies neither, and its own disposition changes no deck, so there is
nothing new to run. Every number above and below is re-derivable from a
committed document by the commands those documents publish:

| fact | source | re-run with |
|---|---|---|
| the abort, to every printed digit, by three independent paths (2446 accepted timepoints) | #332 Evidence 1 | `probe_cmp_convergence.py sar-logic-timing-gates-tie --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter` |
| differential 0 … 3.8e-13 V (0 … 1690 ulp), two bit-identical timepoints | #332 Evidence 3 | same, `--numdgt 17 --tail 25` |
| `v(tie_cmpo)` at 2.96980 V through all 481 reversals | #332 Evidence 2 | same, `--probe --chatter --tail 40` |
| 197.8 µA excursion, invariant to a 2× change in `h`, on a 4.8 nA row | #332 Evidence 4 | same, `--keep` + `_probe_tables` |
| `--tie-offset 100u` / `1m` complete at this corner | #332 Evidence 5 | same, `--tie-offset 100u` |
| settled code is 511 or 512 at every conversion of all six "failing" points | #337 Evidence 3 | `probe_code_readout.py sar-logic-timing-gates-tie --corner … --bits` |
| `tie_conv_period_ns` PASSES at **29 of 29** scored points (999.999 … 1000 ns against a 999.9 … 1000.1 bound) | `records/20260920-020802-2043286.md` Result table | `sim/run_corners.py sar-logic-timing-gates-tie` |

The last row is the one that decides this record, and it is worth stating on
its own: **the chatter has never falsified the claim the loop exists to
test.** DR-0008's consequence is that a near-metastable decision "corrupts at
most one bit and cannot stall the conversion". Measured: `drdy` arrives 16
clocks apart to within the ratified 999.9 … 1000.1 ns bound at every point
where the measurement was reached
(29/29), and the settled code is within 1 LSB of mid-scale at every
conversion of every point #337 examined. The chatter's entire measured cost
is one point of solver coverage and ~2.7× per-point runtime (DR-0029).

## Alternatives considered

### Candidate 1 — a sub-LSB `tie` offset at 100 µV (0.031 LSB at 3.30 V, 0.0345 LSB at 2.97 V) — **the strongest candidate, and rejected on three measured grounds**

This is no longer DR-0029's refuted 1 µV. At the aborting corner #332 measures
`--tie-offset 100u` to **complete** (481 accepted timepoints, 36 reversals,
2.748 ns mid-rail dwell, and **zero** accepted timepoints in the
"idle + sub-resolution" state that ends at the abort), against the committed
deck's 2446 / 481 / 8.416 ns / 0.1693 ns and its ABORT. It also clears
DR-0029's own decisive objection, which was that a 1 µV differential *is*
`vntol`: 100 µV is 100× `vntol` and ~4.5 × 10¹¹ ulp, so its sign is a fact
about the circuit. It is rejected anyway, and for reasons that are evidentiary
rather than preferential:

- **Two corners is not the evidence base for a stimulus change to a 45-point
  grid whose incidence is corner-dependent, on a knob whose own sweep is
  measurably non-monotone.** DR-0029 measured `{vcm+10u}` to be **4.4× worse**
  than committed on mid-rail dwell (11.118 ns against 2.523 ns) at
  `tt`/27 °C/3.30 V — a small offset can relocate reversal bursts into a
  worse-placed window rather than remove them. 100 µV is measured at exactly
  two of 45 points (`tt`/27 °C/3.30 V by DR-0029, `sf`/27 °C/2.97 V by #332),
  and #332's Evidence 5 states in its own words that the hazard-window
  coincidence is "necessary-looking but not sufficient" — its `--cmp-rc
  1k,10f` row has a **longer** such window and completes. **There is no rule
  by which a pass at `sf_27c_2.97v` predicts a pass at the other 44 points.**
  Adopting the offset trades one attributed ERROR for an unmeasured grid, and
  invalidates the 29 scored points in the bargain.
- **It costs the claim, and the claim is the deliverable.** `tb.json` and
  DR-0008 both turn on the input being pinned *exactly* on the threshold. At
  `{vcm+100u}` the deck measures a 0.034 LSB input, and DR-0008's consequence
  would have to be restated as "near-metastable, where *near* means within
  1/29 of an LSB". That is a defensible experiment — it is simply not the one
  DR-0008 promised, and an honest version of it is a **sixth loop placed
  beside `tie`**, not a quiet substitution inside it. DR-0029 anticipated
  exactly this and required the successor to "adopt a redesigned loop *with
  its own stated claim*"; this record declines to pretend a 0.034 LSB offset
  leaves the stated claim intact.
- **What it buys has not been shown to be needed.** The offset's entire
  measured benefit is convergence at one point plus a runtime saving DR-0029
  already priced at ~2.7×. Against that, `tie_conv_period_ns` passes at
  29/29 scored points and the settled code is within bound everywhere it has
  been measured. Paying the experiment's definition for one point of coverage
  is the wrong trade while the loop is still answering its own question
  everywhere it can be asked.

**What would license it later, stated so a future record does not have to
invent the bar.** A record adopting a `tie` offset should carry: (a) the full
45-point grid re-run at the proposed offset, scoring **at least** the 29
points the committed deck scores; (b) a measurement that the asymptotic
differential stays above `vntol` by a stated margin at every corner, not just
at the two measured here; (c) a restated `claim` and a restated DR-0008
consequence that say what "near" now means numerically; and (d) an explicit
disposition of whether the exact-tie loop is *replaced* or *joined*. None of
those exists today.

### Candidate 2 — strobe the comparator — **rejected on cost to the rest of the family, which #332 raises rather than lowers**

DR-0029 §Alternatives candidate 1 already enumerated the consequences, and
they are carried here rather than re-derived: `gen_sar_logic._loop` emits one
comparator for every loop of every deck in this family, so **strobing all
five** stops `lt`/`xl`/`bad` measuring what they exist to measure — the margin
between a *continuous-time* decision and the latching edge — forcing
re-derivation of the 40/50/70 ns `cmp_delay` brackets, **DR-0010's bisected
50 ns / 52 ns boundary**, the decks' own committed header text, and the
existing evidence in `sim/sar-logic-timing/`,
`sim/sar-logic-timing-gates-ok/`'s 45-point grid and the five-loop parent's
records. **Strobing only `tie`** destroys the `ok`-vs-`tie` control that let
#310 attribute the chatter to the stimulus in the first place — the two decks
run the identical comparator and identical `cmp_out_rc` and differ only in
stimulus. And a strobe instant has to come from somewhere: deriving it from
`clk` writes the bit-trial cadence into the stimulus of the loop whose sole
cadence claim is that the *DUT* keeps that cadence.

#332 changes the balance in two ways, one for and one against, and both are
recorded:

- **For (new, and the first affirmative argument this candidate has ever
  had)**: a strobed decision *would* remove this abort by construction, not
  merely reduce it. The lethal state is 6.6 ns of unbroken "DUT quiescent +
  differential below any resolvable scale" between clock edges; a decision
  that can only change at a clock-aligned strobe puts **zero** reversals in
  that window. DR-0029 was right that strobing does not make the tie decision
  deterministic — it stays a hard sign test on an unresolvable quantity,
  taken once per bit trial — but it does move every such test onto an instant
  when the supply row is not quiescent.
- **Against (new, and decisive)**: `lt` and `xl` currently have **zero**
  points that completed the ratified transient across two 45-point grids
  (#303, `20260920-182006-2422cac` / `20260921-021359-2422cac`), and their own
  aborts are unexplained (#343). The family cannot absorb a model change that
  re-dates `ok`'s and the parent's evidence at the same time as it is trying
  to obtain `lt`/`xl` evidence for the first time. A strobed model belongs to
  a deck designed around it, on a family that is measured.

### Candidate 3 as a bare "no change" — **not sufficient, and not what is ratified here**

Restating DR-0029 unchanged would leave three of its statements standing that
the measurement contradicts: that the differential sits at the solver's noise
floor (it reaches the floating-point floor); that the exposure is the DUT's
`cmp` port sitting in the standard cells' 0.8–2.5 V switching band (at the
corner that failed, `v(tie_cmpo)` never leaves 2.9698 ± 0.0001 V — each
reversal is 0.7–2.8 fs and the 100 ps network moves the node ~10 µV per flip,
so **the chatter reaches the solver, not the DUT's logic**); and that "#303's
remaining `tie` coverage can be scheduled against the decks exactly as they
stand" (it cannot — one point of 45 cannot produce a result on this deck at
all). Items 5 and 6 of the Decision exist because of those three.

### Candidate 4 — a solver `.options` entry — **measured to work, and forbidden**

#332 Evidence 6 measures `reltol=1e-2` to clear the abort with no circuit
change whatsoever. It is not landed and must not be: it is a relaxation
(CLAUDE.md — agents do not relax the ratified spec to make results pass), it
is asserted against by
`sim/tests/test_sar_ctrl_gates_tb.py::SharedSupplyRowTests::test_no_manifest_papers_over_the_abort_with_a_solver_option`,
and the same run reports **205.451 ns** of mid-rail dwell against the
committed 8.416 ns — a 25× coarser accepted-timepoint grid, i.e. it buys
convergence by degrading the grid the deck's own diagnostics are read from.

### Candidate 5 — move `CMP_OUT_RC` — **three values complete at this corner, and none of them is a licence**

`1k,1p`, `1k,10f` and `10k,10f` all complete at `sf_27c_2.97v` (#332
Evidence 5). Rejected: `1k,1p` costs **391.326 ns** of mid-rail dwell (46× the
committed), `1k,10f` has a **longer** hazard window than the aborting deck and
826 µA excursions, the value is pinned from below by #296's own abort, and one
corner cannot license a change that re-dates four other decks' evidence.

### Candidate 6 — relax or re-scope a `tb.json` bound — **not applicable and forbidden**

Neither bound is implicated: the run never reaches a measurement, so moving a
bound would hide the ERROR rather than change anything about convergence.

## Consequences

- **This record buys no convergence.** `sf_27c_2.97v` will abort again on the
  next run of this deck, at the same time, on the same node. A re-run is not a
  retry, and a future agent must not treat it as flaky.
- **The `tie` claims now carry an explicit 29/45**, and that is a reduction in
  what this block can say, not a bookkeeping note. `tie_conv_period_ns` is
  substantiated at 29 points of the ratified PVT box and unknown at 16.
  Correcting the text that presents the grid as full-PVT is **gated on
  ratification** and is not done here (see Spec lines affected).
- **Decision item 5 makes the grid's 15 timeouts an open state rather than a
  neutral one.** That is heavier than how the record currently reads, and it
  is deliberate: #332 says in its own words that those points "cannot be
  assumed free of it". The cost is that the `tie` deck cannot be signed off
  until each is attributed — potentially by a batch-fleet re-run (#303's
  operator direction), which is not scheduled here.
- **Bad consequence, stated plainly**: this record decides from one
  instrumented corner plus one 45-point grid, and establishes **no predictive
  rule** for which corners abort. #332 explicitly declines to claim one, on
  the strength of a ten-configuration table one of whose rows has a longer
  hazard window and completes. If a future grid returns several aborts, item 5
  forces each to be attributed individually, and nothing here makes that
  cheaper.
- **Bad consequence, stated plainly**: the strongest argument *against* this
  record is candidate 1's, and it is stronger than it was when DR-0029 refused
  it — 100 µV is not `vntol`, it completes at the corner that fails, and it
  costs 0.034 LSB of an already-synthetic stimulus. This record refuses it on
  the size of the evidence base and on the claim, not because the candidate is
  weak. A reader who thinks 29 measured points are worth less than a complete
  grid should re-open it with the four items listed under candidate 1.
- **`v(tie_cmpo)` mid-rail is still not #296's rejected soft comparator**, and
  this record sharpens the diagnostic rather than removing it: the decision on
  `v(tie_cmpd)` is hard and always at a rail, and at the aborting corner the
  DUT-facing node stays railed to within 10 µV for the entire terminal window.
  `probe_cmp_convergence.py --probe` prints both side by side.
- **`tie_code_deviation` remains a check that the code lands adjacent to
  mid-scale**, not a bit-wise reproducible number (DR-0029, carried) — and
  after #337, its *reported* value is additionally a function of the readout
  instant until DR-0031 part 2's settling guard lands (#327). A 512 in a
  `tie` grid taken before #327 is a decode transient, not a saturated code.
- **This record licenses nothing outside this loop.** A chattering decision in
  a loop whose input is *not* pinned on the decision threshold is a defect,
  not a model property. In particular it says nothing about `lt`/`xl`'s aborts
  on the same `vvdd_gate#branch` node (#343): those are on decks whose only
  structural difference from the converging `ok` deck is an ideal lossless
  transmission line, and their leading hypothesis is unrelated to this one.
- **What becomes easier**: nothing in the tree changes, so no evidence record
  is invalidated and no bound moves. The next `tie` investigation is pointed
  at the solver's conditioning of the DUT's supply row — an h-independent
  197.8 µA excursion on a row carrying 4.8 nA — rather than at the DUT's
  logic, which is where DR-0029's Consequences pointed it and where #332
  measured there is nothing to find.

## Spec lines affected

- [`DR-0029`](DR-0029-tie-loop-decision-chatter.md) — `Status` /
  `Superseded by` — **changed** (prospective back-pointer; both records are
  `proposed`, and DR-0029 governs until both are signed off). Its Context,
  Decision, Alternatives considered and Consequences are left exactly as
  written, per `README.md`'s append-only rule.
- [`DR-0008`](DR-0008-sar-logic-synchronous.md) — the near-metastable
  consequence ("corrupts at most one bit and cannot stall the conversion";
  "drdy keeps arriving every 16 clocks even with the comparator pinned on an
  exact tie") — **clarified (no value change)**, and **not** superseded. It is
  substantiated at 29 of 45 points and contradicted at none. An ngspice
  non-convergence is not the conversion stalling: it is the matrix failing to
  produce a transient, which is why item 5 prices it as coverage and not as a
  counterexample.
- [`DR-0031`](DR-0031-power-up-first-conversion-validity.md) — mechanism B and
  part 2 — **clarified (no value change)**; #337 extends its reach to the
  `tie` deck's own corners, and its execution stays #327.
- `sim/sar-logic-timing-gates-tie/testbench/tb.json` — `claim`,
  `tie_code_deviation`, `tie_conv_period_ns` — **unchanged** (no relaxation;
  listed so the record is explicit that it moves none of them). Its `Note`
  text still carries DR-0029's superseded "~1e-7 V … the solver's own noise
  floor" characterisation; correcting it is gated on this record's
  ratification and is **not** in issue #345's scope — filed as **#363**.
- `design/sar-logic/rtl/README.md` (the `#322` and `#303 (continued)` entries
  of *Verification performed*) — **unchanged**, same gating (#363). Its "not
  yet attributable to DR-0029's recorded decision-chatter property" text about
  the six 512 points was already overtaken by #337's merged investigation,
  independently of this record — #363 part A fixes that half now, ungated.
- `sim/sar-logic-timing-gates-tie/records/20260920-020802-2043286.md` — **not
  touched**: `sim/` records are append-only (`sim/README.md`), and a
  timestamped measurement stays true regardless of what supersedes the record
  that interprets it.
- `README.md#target-specification` — none. This record changes no target
  specification row.
