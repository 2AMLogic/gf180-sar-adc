# DR-0029: The `tie` loop's comparator decision chatter is a property of the near-metastable model, recorded and left unchanged

- **Status**: proposed — requires operator sign-off; supersession proposed by
  [DR-0033](DR-0033-tie-loop-nonconvergence-coverage-hole.md), which is also
  `proposed`. **This record governs until both are signed off.**
- **Date**: 2026-09-19
- **Decided by**: Builder agent, issue #322
- **Supersedes**: none — first record on this question
- **Superseded by**:
  [DR-0033](DR-0033-tie-loop-nonconvergence-coverage-hole.md) — **proposed,
  not yet in force** (issue #345, on the measurement in
  `sim/sar-logic-timing-gates-tie/investigations/20260921-issue-332-quiescent-supply-row-nonconvergence.md`
  that this record's own Consequences name as its supersede trigger). DR-0033
  carries this record's Decision items 1–4 forward unchanged and replaces its
  account of the chatter regime (the differential reaches the floating-point
  ulp, not `vntol`), its statement of where the chatter's exposure lies (the
  solver's supply-row conditioning, not the DUT's `cmp` port), and its
  "#303's remaining `tie` coverage can be scheduled against the decks exactly
  as they stand" consequence.
- **Related**: #322 (this record's own issue), #310 (the investigation that
  measured the chatter and deliberately declined to act on it), #296 (the
  `cmp_out_rc` output network this record pins, and the *soft* comparator
  that was prototyped and rejected there), #311 (the per-loop decomposition
  that made the `tie` deck runnable), #303 (the remaining PVT coverage for
  this deck),
  [DR-0008](DR-0008-sar-logic-synchronous.md) (the record that defines the
  `tie` loop and the near-metastable claim it carries — **not** superseded,
  see Spec lines affected),
  [DR-0010](DR-0010-mixed-signal-sim-strategy.md) (the bisected 50 ns / 52 ns
  `cmp_delay` boundary that candidate 1 would invalidate),
  `sim/sar-logic-timing-gates/investigations/20260918-issue-310-tie-loop-decision-chatter.md`
  (the measurement this record decides from),
  `sim/sar-logic-timing-gates-tie/testbench/tb.json` (the manifest whose
  claim and bounds this record leaves **unchanged**)

## Context

`sim/sar-logic-timing-gates-tie/` pins its input **exactly** on the free-MSB
decision threshold (`vtiein tie_vinp 0 dc {vcm}`), which is what makes it
the near-metastable case DR-0008 promises to measure. Issue #310's
instrumentation found the consequence nobody had recorded: with the input on
an exact tie, `v(tie_topp) − v(tie_topn)` sits at ~1e-7 V — the solver's own
noise floor — for the whole of a bit trial's settling window, and the
comparator model is a hard ternary on the **sign** of that quantity, so the
decision reverses from accepted timepoint to accepted timepoint. Measured at
`tt`/27 °C/3.30 V on the committed `tie` deck over 400 ns: **32 reversals and
2.523 ns of mid-rail dwell**, against **2 reversals and 0.204 ns** for the
`ok` deck running the *identical* comparator and the *identical*
`cmp_out_rc`, differing only in stimulus (both reproduced in this record's
own runs, below).

That is not a DUT defect (the decision is hard and always resolves to a rail,
and the conversion completes), and it is not what aborted the five-loop parent
deck (#310's Evidence 4 settles that). But it parks the net the DUT's `cmp`
port binds inside the 0.8–2.5 V switching band of real
`gf180mcu_fd_sc_mcu7t5v0` `aoi21_1`/`nor2_1` inputs for nanoseconds at a
time, and every candidate response to it changes what the loop *claims* —
`tb.json`'s claim says the input is pinned *exactly* on the threshold, and
"exactly" is the word doing the work. #310 therefore filed it rather than
acting on it. This record acts.

## Decision

**No change. The chatter is ratified as a documented property of the `tie`
loop's model, not as a defect to engineer away.** Concretely:

1. The `tie` loop's input stays `dc {vcm}` — pinned **exactly** on the
   threshold, with no offset of any magnitude.
2. The comparator stays the continuous-time hard ternary
   `v(topp) > v(topn) ? vdd_val : 0`, evaluated at every accepted timepoint
   and **not** strobed, identically for all five loops and for the rung-1
   ideal decks.
3. `CMP_OUT_RC` stays `("1k", "100f")` (tau = 100 ps) and is now pinned by
   this record as well as by #296 — see Consequences.
4. `sim/sar-logic-timing-gates-tie/testbench/tb.json`'s `claim`,
   `tie_code_deviation` and `tie_conv_period_ns` are unchanged, in wording
   and in value.

The reasoning, stated once: **for this comparator model, "the input is on the
decision threshold" and "the decision follows a sign that is below the
model's own resolution" are the same statement.** The model's resolution is
set by the solver's node-voltage tolerance, so any input offset large enough
to remove the chatter is large enough to remove the near-metastable condition
the loop exists to create — which is measured below, not assumed. The chatter
is the experiment, not an artifact of it.

## What this record verifies

All runs at `tt`/27 °C/3.30 V on the committed `sim/sar-logic-timing-gates-tie/`
deck, re-runnable from the tree. `--tie-offset` is a measurement flag added to
the probe by this issue; like `--cmp-rc` and `--spice-option` it writes
nothing.

**The ratified bounds pass with the chatter fully present** —
`python3 sim/run_corners.py sar-logic-timing-gates-tie --corners tt --temps 27
--supply-tol 0 -j 1 --ngspice-threads 1 --no-write`:

| measurement | bound | measured | result |
|---|---|---|---|
| `tie_code_deviation` | max 1.0 | **1** | PASS |
| `tie_conv_period_ns` | 999.9 … 1000.1 | **1000** | PASS |

(1 of 1 points ok, 181.4 s. `--no-write` deliberately: this is a check of an
existing bound, not a new evidence record — the `tie` deck's PVT grid is
#303's remaining coverage and is not claimed here.)

**Baseline and tau, re-derived rather than transcribed** —
`probe_cmp_convergence.py sar-logic-timing-gates-tie --until 400n --chatter`:

| deck / knob | timepoints | reversals | mid-rail dwell |
|---|---:|---:|---:|
| `sar-logic-timing-gates-ok`, committed | 354 | 2 | 0.204 ns |
| `sar-logic-timing-gates-tie`, committed (tau = 100 ps) | 477 | 32 | 2.523 ns |
| `…-tie`, `--cmp-rc 1k,1p` (tau = 1 ns) | 401 | 84 | 74.829 ns |

Both `tie` rows reproduce #310's Evidence 2 and Evidence 3 to every printed
digit.

## Alternatives considered

### Candidate 2 — a deterministic sub-LSB `tie` offset — **measured and refuted at its own proposed value**

The candidate's rationale is that `vcm + 1 µV` (0.00031 LSB; 1 LSB =
3.2227 mV at 3.30 V) would give the differential "a sign that is a physical
fact rather than a feedback artifact". Swept with `--tie-offset`, same corner
and window:

| `tie` input | LSB fraction | timepoints | reversals | mid-rail dwell |
|---|---:|---:|---:|---:|
| `{vcm}` *(committed)* | 0 | 477 | **32** | **2.523 ns** |
| `{vcm+1u}` *(the candidate's own value)* | 0.00031 | 566 | **50** | 2.248 ns |
| `{vcm+10u}` | 0.0031 | 526 | 44 | **11.118 ns** |
| `{vcm+100u}` | 0.031 | 397 | 14 | 1.083 ns |
| `{vcm+1m}` | 0.310 | 349 | 4 | 0.396 ns |
| `{vcm+1.6m}` | 0.497 | 349 | 4 | 0.396 ns |

Four things this settles, and the last is the decisive one:

- **At the proposed 1 µV the chatter is not removed — it gets worse** (50
  reversals against 32), and the DUT-facing dwell barely moves.
- **The sweep is not monotone.** At 10 µV the consequence that actually
  matters — how long real standard-cell inputs sit in their high-gain linear
  region — is **4.4x worse** than committed (11.118 ns against 2.523 ns). A
  small offset can relocate the reversal bursts into a worse-placed window
  rather than remove them. This is exactly the "gone rather than merely
  moved" test #322's acceptance criteria demand, and a small offset fails it.
- **Chatter only falls substantially at ~0.3 LSB**, a thousand times the
  proposed value, and then *saturates*: 1 mV and 1.6 mV (0.5 LSB) give the
  identical 4 reversals / 0.396 ns. The loop has not had its chatter
  engineered away at that point — it has left the near-metastable regime and
  become an ordinary sub-LSB input, i.e. a second `ok` loop. `tb.json`'s
  "pinned exactly on the threshold" could not survive it honestly.
- **The 1 µV sign is not a physical fact; it is the same artifact with an
  offset added.** ngspice's default node-voltage tolerance `vntol` is 1e-6 V,
  so a 1 µV differential *is* the solver's own resolution. Tightening it by
  three orders of magnitude separates the two configurations cleanly:

  | configuration | `vntol` | reversals | mid-rail dwell |
  |---|---|---:|---:|
  | committed (`{vcm}`) | 1e-6 *(default)* | 32 | 2.523 ns |
  | committed (`{vcm}`) | 1e-9 | **32** | **2.523 ns** |
  | `{vcm+1u}` | 1e-6 *(default)* | 50 | 2.248 ns |
  | `{vcm+1u}` | 1e-9 | **90** | 2.041 ns |

  The committed deck's chatter figures are **invariant** to a 1000x
  tolerance change; the 1 µV deck's reversal count nearly doubles. Whatever
  the 1 µV offset buys, it is not independence from the solver's tolerance,
  which was the whole of the candidate's stated rationale.

### Candidate 1 — strobe the comparator — **rejected on cost to the rest of the family, and on what it does not fix**

Not measured (it is a structural model change, not a knob), and rejected on
three grounds that do not need a measurement:

- **The comparator is emitted once.** `gen_sar_logic._loop` emits the same
  comparator for every loop of every deck in this family, so there are only
  two ways to strobe it. **Strobe all five**, and `lt`/`xl`/`bad` stop
  measuring what they were built to measure: their whole purpose is the
  margin between a *continuous-time* decision and the latching edge, so the
  40/50/70 ns `cmp_delay` brackets, the bisected 50 ns / 52 ns boundary
  DR-0010 records, the deck's own committed header text, and the existing
  evidence in `sim/sar-logic-timing/`, `sim/sar-logic-timing-gates-ok/`'s
  45-point grid and the five-loop parent's records would all have to be
  re-derived — to fix a property of one loop that endangers no bound.
- **Strobe only `tie`**, and the loop loses the control its interpretation
  rests on. Today `ok` and `tie` run the identical comparator and the
  identical `cmp_out_rc` and differ only in stimulus, which is precisely what
  let #310 attribute the chatter to the stimulus rather than to the model
  (its Evidence 1 is that side-by-side). A `tie` loop with a different
  comparator from `ok` can no longer make that attribution.
- **It would not make the tie decision deterministic anyway.** A strobed
  decision is still a hard sign test on a ~1e-7 V quantity; it would simply
  be taken once per bit trial instead of at every accepted timepoint, and its
  per-trial outcome would still be noise-determined — correctly so, because
  that is what a real comparator does on an exact tie. What strobing buys is
  fewer `cmp_out_rc` restarts, i.e. a *cost* improvement rather than a
  correctness one. That cost is real and is quantified below ("The cost the
  chatter actually carries") — it is just not a reason to make the loop stop
  measuring what it measures.

A fourth objection is worth recording because it would apply to any future
attempt: **a strobe instant has to come from somewhere**, and the only clocks
in this deck are `clk` and the DUT's own phase outputs. Deriving it from
`clk` writes the bit-trial cadence into the stimulus of the loop whose sole
ratified cadence claim (`tie_conv_period_ns` — "drdy exactly 16 clocks
apart") is that the *DUT* keeps that cadence. The candidate is not
unphysical — a real SAR comparator is strobed — but a strobed model belongs
to a deck designed around it, not retrofitted onto this one.

## The cost the chatter actually carries

#322 lists the chatter as a plausible part of why `tie` costs 3.3x `ok` per
PVT point (#311, measured). That is the only motivation for candidates 1 and 2
that survives the analysis above, so it is measured here rather than left as a
plausibility — and it turns out to be **more** than plausible.

Over the 400 ns probe window, removing the chatter entirely (the 1 mV row,
4 reversals) takes the `tie` deck from **477 to 349** accepted timepoints —
a **1.37x** factor, and 349 is within 1.5 % of the `ok` deck's own 354. So in
*that* window the chatter is essentially the whole of the `tie`-vs-`ok` gap.

Over the manifest's own unmodified `tran 5n 8.5u 0 5n`, the same A/B
(`probe_cmp_convergence.py sar-logic-timing-gates-tie --chatter` with and
without `--tie-offset 1m`) measures:

| 8.5 µs run | accepted timepoints | reversals | mid-rail dwell | core-s |
|---|---:|---:|---:|---:|
| committed (`{vcm}`) | 9216 | 651 | 124.183 ns | 209.07 |
| chatter-suppressed (`{vcm+1m}`) | 7183 | 49 | 3.830 ns | 76.71 |

(The committed row's 9216 accepted timepoints reproduce #310's Evidence 5b
exactly. Both runs were taken back to back on the same contended host, so the
*ratio* of the core-s figures is meaningful while neither absolute figure is a
budgeting number — use #311's 233.7 core-s via `sim/run_corners.py` for that.)

**So the cost motivation behind candidates 1 and 2 is real and larger than
the timepoint count suggests: suppressing the chatter would cut this deck's
per-point cost by ~2.7x** (209.07 → 76.71 core-s) for only a 1.28x drop in
accepted timepoints — the difference being that a chattering timepoint also
costs more Newton iterations than a quiet one. **That is stated here because
it is the strongest argument *against* this record's own decision**, and it
does not change it: a 2.7x saving is not worth buying with a loop that no
longer measures a near-metastable decision (candidate 2 at the magnitude that
delivers it, 0.3 LSB) or with re-deriving DR-0010's `cmp_delay` boundary and
four other decks' evidence (candidate 1). The cost is paid.

If #303's remaining `tie` coverage ever makes that cost binding, the correct
response is a **superseding** record that adopts a redesigned loop *with its
own stated claim* — not a quiet offset inside a loop whose manifest says
"exactly".

## Consequences

- **`sim/sar-logic-timing-gates-tie/` keeps a comparator whose output sits in
  the standard cells' high-gain linear region for ~2.5 ns per 400 ns**, and
  that is now the expected, recorded behaviour of this deck. A future reader
  who finds `v(tie_cmpo)` mid-rail must **not** read it as #296's rejected
  soft comparator returning by another route: the decision on `v(tie_cmpd)`
  is hard and always at a rail, and the two are distinguishable with
  `probe_cmp_convergence.py --probe`, which prints them side by side.
- **`CMP_OUT_RC` is now pinned from both directions.** #296 pinned it from
  below (tau = 0 is that issue's own `b<tag>cmp#branch` abort); this record
  pins it from above, because the chatter's *consequence* scales with tau —
  74.829 ns of mid-rail dwell at tau = 1 ns against 2.523 ns at the committed
  100 ps, 30x worse. The committed value is wedged between two failure modes.
  Loosening `cmp_out_rc` is a superseding decision record's business, not a
  testbench edit's.
- **`tie` stays the more expensive undelayed loop and this record does not
  make it cheaper.** Anyone budgeting the remaining PVT coverage (#303)
  should budget the measured `tie` cost, not `ok`'s.
- **This record licenses nothing outside this loop.** A chattering decision
  in a loop whose input is *not* pinned on the decision threshold is a
  defect, not a model property — the argument above turns entirely on the
  differential being below the model's own resolution *by construction of the
  stimulus*.
- **Bad consequence, stated plainly**: the `tie` loop's bit-by-bit code is
  decided by solver noise, so `tie_code_deviation` is a check that the code
  lands adjacent to mid-scale, **not** a reproducible number. It is
  reproducible to the solver's tolerance rather than bit-wise, exactly as
  `20260917-issue-303-transient-cost-and-retention.md` already established
  for this deck family's accepted-timestep sequence. Nobody should read a
  `tie_code_deviation` of 0 versus 1 across two runs, or across two hosts, as
  a change in the design.
- **Bad consequence, stated plainly**: this record decides the model on
  evidence from **one** PVT point (`tt`/27 °C/3.30 V). The chatter's
  magnitude at the corners of the ratified box is unmeasured. If #303's
  remaining coverage finds a corner where `tie_conv_period_ns` or
  `tie_code_deviation` actually fails *and* the chatter is implicated, this
  record is the one to supersede — with the measurement, not with a
  relaxation.
- **What becomes easier**: nothing in the tree changes, so no evidence record
  is invalidated, no bound moves, and #303's remaining `tie` coverage can be
  scheduled against the decks exactly as they stand.

## Spec lines affected

- [`DR-0008`](DR-0008-sar-logic-synchronous.md) — the `tie` near-metastable
  loop's stimulus and comparator definition (its Consequences' "A stalled or
  near-metastable comparator decision corrupts at most one bit ... the `tie`
  loop") — **clarified (no value change)**. DR-0008 is **not** superseded: its
  decision (synchronous logic, `M = 16`) is untouched, and so is the loop it
  defines. This record only states what "pinned on an exact tie" implies for
  the comparator model that reads it.
- `sim/sar-logic-timing-gates-tie/testbench/tb.json` — `tie_code_deviation`,
  `tie_conv_period_ns`, `claim` — **unchanged** (no relaxation; listed so the
  record is explicit that it changes none of them).
- `README.md#target-specification` — none. This record changes no target
  specification row.
