# DR-0031: The first conversion after power-up is not valid — ratify the discard-one-conversion contract, and correct the code-error measurement rather than relaxing its bound

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-19
- **Decided by**: Builder agent, issue #320
- **Supersedes**: none — first record on this question
- **Superseded by**: (none while this record stands)
- **Related**: #320 (this record's own issue), #327 (part 2's execution:
  the measurement correction and the re-scoring it forces), #328 (the RTL
  reset alternative this record declines to decide), #311 (the per-loop
  decomposition that produced the first scored gate-level grid),
  #272 (the RTL and its synthesis), #274/#279 (P&R), #275 (post-route STA —
  the record whose slack this one cites to refute the setup hypothesis),
  #319 / [DR-0028](DR-0028-gate-level-acquisition-isolation-bounds.md) (the
  *other* failure in the same grid; independent of this one),
  [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md) (the same class of
  finding — a continuously-evaluated check reading a synthesized netlist's
  real sub-nanosecond switching window as a steady-state violation — with
  the opposite response; see Alternatives),
  [DR-0003](DR-0003-clocking.md) (`M = 16`, the 16-phase ring and 62.5 ns
  clock this record's "one conversion" is counted in),
  [DR-0005](DR-0005-interface-scope.md) (the 10-bit output register whose
  clk→Q window mechanism B is measured on),
  [DR-0008](DR-0008-sar-logic-synchronous.md) (synchronous SAR logic, one
  clock, no reset pin available in `dffq_1`),
  [DR-0014](DR-0014-bottom-plate-sampling.md) (the four-leg switch decode the
  engaged-weight flags drive),
  `sim/sar-logic-timing-gates-ok/records/20260918-233547-1d81aa1.md` (the
  grid this record disposes of),
  `sim/sar-logic-timing-gates-ok/investigations/20260919-issue-320-first-conversion-and-decode-transient.md`
  (the measurements every number below is taken from)

## Context

The first scored 45-point PVT grid for the gate-level SAR timing claim
reported `abs_err_delay_0ns` up to **512 LSB** at 10 of 45 points, with
`ok_conv_period_ns` at exactly 1000 ns everywhere. Issue #320 read the
pattern (125 °C, `sf`/`ss`) as a setup-time violation in the SAR register's
gate-level path. The investigation cited above measured it instead, and
found **two unrelated mechanisms, neither of them a timing path**:

**A. The first conversion after power-up is genuinely invalid** (8 of the 10
points; measured settled code errors of 252, 252, 252, 252, 5, 5, 1, 1 LSB —
first wrong bit 8, 8, 8, 8, 9, 9, 2, 2 respectively). `sar_ctrl.v`'s `start`
pulse seeds the 16-phase ring `ph[15:0]` and **nothing else**: the nine
engaged-weight flags `eng[9:1]` are cleared only by `endconv = ph[13]`,
which arrives *inside* the first conversion, after that conversion's own
sample and its first nine bit trials. So conversion 1 runs its binary search
against an arbitrary, PVT-dependent set of already-engaged CDAC weights.
Structurally confirmed on the committed gate netlist by walking all 45
flip-flops' D-cones: `start` reaches all 15 `ph_*` flops and `drdy`, and
**none** of the 9 `eng`, 10 `q`, 10 `c` flops
(`sim/tests/test_probe_code_readout.py::ResetStructureTests`). Across the
full grid the correlation is exact: all 10 failing points power up with
`eng != 0`, all 28 points that power up with `eng == 0` pass, zero
counterexamples. The A/B is causal — the same deck at `tt_125c_2.97v` and
`ss_125c_3.63v` goes from 252 LSB wrong to exactly right when the nine flags
alone are forced to their post-reset value. Two consequences follow from the
structure with no simulation: **no `start` pulse of any length clears `eng`**
(while `start` is high the ring is pinned at `ph[0]`, so `arm`/`endconv`
never fire), and **exactly one conversion is affected** (`endconv` clears all
nine on the edge leaving conversion 1's last bit trial). The second is also
measured: conversions #2–#8 are exact at all four points read out, including
the two worst.

**B. The measurement's own `drdy` gate opens while the output register is
still updating** (the 2 remaining points, both reporting the headline 512).
`b<tag>err` evaluates `v(drdy)>vth ? v(code)-v(exp) : 0` continuously, and
`drdy` and `c[9:0]` are loaded on the *same* rising clock edge. The ten code
bits take **0.186–0.199 ns** to settle; whichever accepted timepoints land
inside that window are decoded as a code. At the 511 → 512 major carry this
deck's stimulus deliberately crosses, all ten bits change at once, so the
mid-update word can read 0 — exactly 512 LSB against an expected 512. At
`sf_125c_3.30v`, conversion #6's **settled code is 512, exactly correct**,
and the measurement reports 512 LSB of error for it. Whether it does so at
all depends on where the solver's accepted timepoints fall: at
`tt_125c_2.97v` and `ss_125c_3.63v` they straddle the same transition and
nothing is reported.

**The setup hypothesis is refuted from three directions**: neither mechanism
is a max-delay path; the post-route STA record's worst setup slack is
+56.365 ns of a 62.5 ns budget (a ~6.1 ns data path — a **10.2x**
degradation would be needed to fail, against a 3.6x total `ff`→`ss` span);
and the direct SPICE readout at `sf`/125 °C shows the register settling in
0.186 ns with conversions #2–#8 all exact. The `sf`/`fs` STA coverage gap is
real but **not closeable with this PDK**: `gf180mcu_fd_sc_mcu7t5v0` and
`mcu9t5v0` each ship 15 Liberty files (3 `tt`, 6 `ss`, 6 `ff`) and **zero**
`sf`/`fs`, so `klt sta` has no view to run at those corners.

## Decision

**Three parts. None of them relaxes a bound.**

**1. Ratify the power-up contract.** `sar_ctrl_a` requires, after power-up,
*both*:

  (a) `start` asserted for ≥ 1 clock, to seed the one-hot phase ring — the
      requirement `design/sar-logic/rtl/README.md`'s "Real hardware note"
      already states; and
  (b) **exactly one conversion discarded thereafter.** The engaged-weight
      flags `eng[9:1]`, the trial registers `q[9:0]` and the output register
      `c[9:0]` have no reset (`dffq_1` has no reset pin, DR-0008), and clear
      or are overwritten only by a conversion's own `endconv = ph[13]` and
      `ph[14]` edges. Conversion 1's `drdy` word is therefore an arbitrary
      function of the power-up flop state and **must not be consumed**;
      conversion 2 onward is a function of the input alone.

  "Exactly one" is a derived quantity, not a margin: it follows from
  `endconv = ph[13]` clearing all nine flags in conversion 1's own trial
  sequence, and is measured as conversions #2–#8 being exact at all four
  points read out. It is **not** rounded up to a safety factor, because a
  reader who sees "discard two" cannot tell which is the derivation and
  which is the padding.

**2. Correct the code-error measurement family — window AND strobe — with
every bound unchanged.** The `abs_err_*` / `err_se_*` / `err_df_*` /
`tie_code_deviation` measurements must:

  (a) start their window **after the discarded conversion** (i.e. `FROM` at
      or after the second conversion's `drdy`), replacing today's
      `FROM=0.1u`, which was sized only to skip the pre-seeding garbage
      window at t ≈ 0 and stops ~963 ns short of the first valid conversion;
      and
  (b) hold the `drdy` gate off for a **settling guard of ≥ 0.25 ns** after
      each `drdy` rise, so the comparison reads a settled output register
      rather than its clk→Q window.

  The guard value is not tuned: 0.25, 0.5, 1, 2 and 5 ns all give the
  identical answer at every point measured (28 LSB / one wrong conversion at
  `sf_125c_3.30v`; 252 at `tt_125c_2.97v` and `ss_125c_3.63v`; 0 at
  `tt_27c_3.30v`), against 512 LSB / eight wrong conversions at the
  committed 0 ns. 0.25 ns is the smallest swept value that clears the
  measured 0.186–0.199 ns settling.

  **Every numeric bound is unchanged**: `abs_err_delay_0ns ≤ 0.5`,
  `abs_err_delay_40ns ≤ 0.5`, `abs_err_delay_50ns ≤ 0.5`,
  `abs_err_delay_70ns ≥ 0.9` (the negative control),
  `tie_code_deviation ≤ 1.0`, `err_se_max/min` and `err_df_max/min` at
  ±0.5 LSB. This record moves **no** limit; it corrects *when* the
  instrument looks.

  > **Execution (issue #327), recorded here because Alternative (f) left the
  > implementation to it and not to this record.**
  >
  > * **2(b), the strobe** — `design/sar-logic/gen_sar_logic.py` emits, per
  >   loop, a **buffered copy of `drdy` through a two-element RC**
  >   (`b<tag>drdyb` → `r<tag>drdyg`/`c<tag>drdyg`), and every code-error
  >   B-source is gated on `min(v(<tag>_drdy), v(<tag>_drdyg)) > vth` instead
  >   of on `v(<tag>_drdy) > vth`. The buffer steps rail-to-rail when `drdy`
  >   crosses `vth`, so the RC node crosses the *same* `vth`
  >   `tau·ln 2 = CODE_SETTLE_GUARD_NS` later; both ends are ratiometric in
  >   `vdd_val`, so the guard is the same number of picoseconds at every point
  >   of the supply axis. `CODE_SETTLE_GUARD_NS = 0.5` (R = 1 kΩ,
  >   C = 721.348 fF), **verified in ngspice at exactly 0.500000 ns** — 2× the
  >   ≥ 0.25 ns floor above, ~2.5× the measured 0.186–0.199 ns settling, and
  >   10× below the largest value this record measured to make no difference.
  >   Taking the `min` of the raw and the delayed copy (rather than the
  >   delayed copy alone) keeps the window a strict **subset** of the old one:
  >   it opens one guard late and still closes with `drdy` itself. A
  >   terminated delay line would give an exact delay instead of an RC one,
  >   and was rejected because it loads the DUT's own `drdy` driver — on the
  >   gate netlist that is a real standard-cell output, which a 50 Ω
  >   termination would clamp.
  > * **2(a), the window** — `FROM=0.1u` → **`FROM=1.5u`** in the gate-level
  >   manifests. Measured on the committed `ok` deck: `drdy` #1 rises at
  >   1.06305 µs and its window closes ≈ 1.1257 µs; `drdy` #2 rises at
  >   2.06305 µs. 1.5 µs is ≈ 375 ns clear of each, so the window drops
  >   conversion 1 and nothing else.
  > * **Scope of 2(a)**: the six `sim/sar-logic-timing-gates*/` manifests and
  >   `sim/sar-logic-functional-gates/`, i.e. exactly the list in "Spec lines
  >   affected" below. The three **rung-1 ideal** decks keep `FROM=0.1u`:
  >   their `sar_ctrl_a` is the XSPICE model, which seeds the ring with
  >   `ph15`'s `ic=1` and powers every other flop up at `ic=0`, so their first
  >   conversion is valid (this record's own Consequences say so) and
  >   discarding it would cost a conversion of coverage for nothing. They do
  >   take 2(b), because the ideal `dac_bridge` transition is a 0.3 ns window
  >   with the same exposure.
  > * **Not taken**: the `code_se_*` / `code_df_*` coverage witnesses and the
  >   `conf_*` / `nside_*` one-hot checks keep `FROM=0.1u` on every deck.
  >   They are not code-error measurements, they are not `drdy`-gated, and
  >   `code_se_lo` in particular *needs* conversion 1 — it is the witness that
  >   the sweep reached the bottom of the range.

**3. `design/sar-logic/rtl/sar_ctrl.v` is NOT changed by this record**, and
the reset question is routed to **issue #328** with its full cost stated
(see Alternatives (a) and Consequences). What *is* corrected here is
`design/sar-logic/rtl/README.md`'s "Real hardware note", whose remedy is
correct for the ring and silently insufficient for the conversion — the
sentence that made this contract look already-satisfied.

## Alternatives considered

- **(a) Add a synchronous clear to `eng`/`q`/`c` in `sar_ctrl.v`** (e.g.
  `eng<i> <= (arm<i> | eng<i>) & ~endconv & ~start;`). **This is the better
  end state and it is explicitly recommended, and filed as **issue #328** — it is not
  rejected on merit.** It is one extra term on nine already-existing gates,
  on a net (`start`) already routed to all 16 ring flops, and it would make
  the documented "assert `start` ≥ 1 clock" remedy actually sufficient
  instead of silently partial. It is not taken *here* because it changes the
  synthesized netlist, and that invalidates a merged chain: #272's synthesis
  and `klt equiv` records, #274/#279's placed-and-routed macro, #275's
  post-route STA, the LVS artifacts, and every gate-level deck and record
  built on `sar_ctrl.mcu7t5v0.synth.v`. Re-doing a landed P&R/STA chain is a
  scheduling and priority call with its own review, not a side effect of an
  investigation issue — the same trap issue #298 hit when an RTL-changing
  fix arrived after #274/#275 had already closed against the old netlist.
  Deciding it inside this record would also make the decision unfalsifiable
  in the one way that matters: part 1's contract is required *regardless* of
  whether the RTL is later fixed, because any already-fabricated or
  already-signed-off revision carries it.
- **(b) Widen `abs_err_delay_0ns` to admit the observed values**, as
  DR-0027 did for the one-hot `sw_conflict` checks. **Rejected.** DR-0027's
  budget works because the quantity it bounds is a real, physically bounded
  ~143–165 ps hazard whose worst value (13.0) sits under a ceiling (20) that
  a *further* regression would still break. Here the excursions are 252–512
  LSB on a 10-bit converter — the full output range. A bound that admits 512
  admits every possible wrong code, so it stops being a check at all. Worse,
  `sim/sar-logic-timing-gates-bad/`'s `abs_err_delay_70ns ≥ 0.9` negative
  control would then be satisfiable by a decode transient instead of by the
  late decision it exists to detect, which destroys the control rather than
  loosening it. Issue #320 forbade this explicitly, and the measurement
  agrees with the prohibition.
- **(c) Ratify the contract but leave the measurement as it is, and let
  readers subtract the first conversion by hand.** **Rejected.**
  `meas tran ... MAX` produces one scalar for an 8.5 µs run; a record cannot
  report "512 LSB, but 0 if you ignore two instants". The grid would keep
  scoring FAIL for a reason indistinguishable from a real one — which is
  exactly the state that cost this issue its investigation.
- **(d) Correct the window only (part 2a), not the strobe.** **Rejected.**
  It fixes mechanism A alone: `sf_125c_3.30v` would still report 512 LSB for
  conversion #6, whose settled code is exactly right, and whether it does
  would still depend on the solver's accepted-timepoint grid rather than on
  the circuit.
- **(e) Correct the strobe only (part 2b), not the window.** **Rejected**,
  for the mirror-image reason: the first conversion's 252 LSB is a *real*
  wrong code, and a settling guard does not and must not hide it. The two
  corrections address two mechanisms and neither substitutes for the other.
- **(f) Sample the code once per conversion in the testbench** (a strobed
  register in the deck) instead of gating a continuous comparison.
  **Not taken, but not ruled out for issue #327's implementation.** It is
  arguably the cleanest instrument — it is what a real digital consumer of
  `drdy`/`c[9:0]` does — but it is a larger change to a generator shared by
  eight decks, and the settling guard achieves the same separation with a
  two-element RC on a buffered copy of `drdy`. Issue #327 picks the
  implementation; this record fixes the requirement, not the circuit that
  meets it.

## Consequences

**Good:**

- The grid's headline failure is now attributable: of `abs_err_delay_0ns`'s
  ten failing points, **eight are one real defect** (an invalid first
  conversion, bounded to exactly one conversion) and **two are an artifact
  of the instrument**. Neither is a timing failure, so the merged P&R/STA
  chain is not in question.
- The `sf`/`fs` STA blind spot is answered on its own terms rather than left
  open: it cannot be closed with this PDK's Liberty set, and the SPICE
  readout at `sf`/125 °C supplies the direct measurement instead.
- The contract in part 1 is cheap at system level: one discarded conversion
  is 1 µs at the 1 MS/s target (DR-0003), and discarding the first
  conversion after power-up is ordinary practice for a SAR ADC.

**Bad — and these are the reasons this record is not a free win:**

- **Part 2 invalidates the current evidence for the measurements it
  corrects.** `b<tag>err` is emitted by one shared generator
  (`design/sar-logic/gen_sar_logic.py`), so correcting it changes the SPICE
  text — and therefore the netlist sha256 — of eight committed decks: the
  five `sim/sar-logic-timing-gates-{ok,lt,xl,bad,tie}/`, the five-loop
  `sim/sar-logic-timing-gates/`, `sim/sar-logic-functional-gates/`, and the
  rung-1 ideal `sim/sar-logic-functional/`, `sim/sar-logic-timing/`,
  `sim/timing-budget-closure/`. Every existing record on those decks stays
  (append-only) but **none of them is evidence for the corrected
  measurement**, and each needs a fresh grid to become one. That is real,
  unbudgeted re-run cost and it is why part 2 is specified here and executed
  in **issue #327**, not smuggled into this record's PR.
- **Until that lands, `sim/sar-logic-timing-gates-ok/`'s grid still reads
  FAIL on `abs_err_delay_0ns`**, and a reader who does not reach this record
  and its investigation cannot tell the 28 LSB that is real from the 512 LSB
  that is not. This record does not fix the tree's current failing state; it
  makes it legible.
- **`sim/sar-logic-timing-gates-bad/` has never been scored**, and its
  `≥ 0.9` negative control must not be scored before part 2 lands: a pass
  produced by a decode transient rather than by the late decision it is
  testing would be a false negative control, which is worse than no control.
- **The contract propagates.** Any deck, block-level testbench or
  system-level `start` driver that assumes every `drdy` word is valid
  inherits part 1(b). Nothing is invalidated *today* — the ENOB/INL-DNL/FFT
  decks run the rung-1 ideal `sar_ctrl_a`, which seeds its ring with `ic=1`
  and carries no such hazard — but a gate-level replay of any of them does.
- **The RTL defect stays in the tree** for as long as **#328** takes,
  with the contract as its only mitigation. If the design is ever taped out
  on the current netlist, part 1(b) is a *silicon* requirement, not a
  simulation convenience.

**Unchanged:** DR-0003 (`M = 16`, 62.5 ns), DR-0005 (the output register),
DR-0008 (synchronous logic, no reset pin), DR-0011, DR-0014 and DR-0027 are
all untouched; so are `sar_ctrl.v`, the synthesized netlist, the routed DEF,
the STA records, and every numeric bound in every `tb.json`.

## Spec lines affected

- `README.md#target-specification` — **none changed**. No row is added,
  widened, relaxed or removed; the power-up contract has no row in the
  ratified table today.
- `spec/<ratified-spec>.md#power-up-and-reset` (pending #1) — *Power-up
  contract: assert `start` ≥ 1 clock, then discard exactly one conversion* —
  **new**. Named here rather than given an invented anchor, per
  `spec/decision-records/README.md`'s `pending #1` rule.
- `design/sar-logic/rtl/README.md` § "Real hardware note: seeding the ring at
  power-up" — **clarified (no value change)**: the existing `start` remedy is
  correct for `ph[15:0]` and does not extend to `eng`/`q`/`c`; the first
  conversion after power-up must be discarded. Applied in this record's own
  PR, because the current wording is what makes the contract look satisfied.
- `sim/sar-logic-timing-gates-{ok,lt,xl,bad,tie}/testbench/tb.json`,
  `sim/sar-logic-timing-gates/testbench/tb.json`,
  `sim/sar-logic-functional-gates/testbench/tb.json` — `abs_err_delay_*`,
  `tie_code_deviation`, `err_se_*`, `err_df_*` — **measurement window
  changed, bounds unchanged** (`FROM=0.1u` → `FROM=1.5u`, after the discarded
  conversion; `drdy` gate → settled-`drdy` gate). Was deferred to issue #327;
  **applied there**, together with the deck regeneration and the `ok` deck's
  re-score. No manifest was edited by *this* record's own PR.
- `sim/sar-logic-functional/testbench/tb.json`,
  `sim/sar-logic-timing/testbench/tb.json`,
  `sim/timing-budget-closure/testbench/tb.json` — **windows unchanged**
  (`FROM=0.1u` stands; see the Execution note under Decision part 2 for why
  the rung-1 ideal decks have no conversion to discard). Their **netlists**
  change with everything else this generator emits, because 2(b)'s
  settled-`drdy` gate is emitted per loop by the shared
  `design/sar-logic/gen_sar_logic.py`.
- `spec/decision-records/DR-0027-gate-decode-one-hot-hazard-budget.md` —
  **not superseded**. Its `sw_conflict`/`nside_cells` budget stands exactly
  as ratified. This record answers a different question about a different
  measurement, and reaches the opposite disposition for the reason stated in
  Alternative (b).
