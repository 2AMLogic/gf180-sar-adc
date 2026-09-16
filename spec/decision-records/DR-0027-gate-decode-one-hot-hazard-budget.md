# DR-0027: Accept a bounded, disclosed real-hazard budget for the synthesized `sar_ctrl_a` switch-decode one-hot check, rather than a synthesis-level delay-balancing fix

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-16
- **Decided by**: Builder agent, issue #298
- **Supersedes**: none — first record for this question
- **Superseded by**: (none while this record stands)
- **Related**: #295 (root cause), #298 (this record's own issue), #289/#297
  (the corner-grid evidence this record's bound is set from,
  `sim/sar-logic-functional-gates/records/20260915-214338-912a8ec.md`),
  `sim/sar-logic-functional-gates/investigations/20260916-issue-295-sw-conflict-root-cause.md`
  (the disambiguation and sub-nanosecond crossing-time measurement this
  record's Context is taken from), [DR-0014](DR-0014-bottom-plate-sampling.md)
  (the four-leg one-hot invariant this record does **not** edit —
  see Decision), [DR-0011](DR-0011-cdac-switching-scheme.md),
  [DR-0016](DR-0016-input-structure-ron-repoint.md) (the switch `R_on`
  figures this record's order-of-magnitude argument cites),
  [DR-0023](DR-0023-digital-interface-device-flavor.md) (the synthesis flow
  whose lack of a timing methodology this record's Alternatives section
  relies on), #274/#275 (P&R/STA, already merged against the netlist this
  record leaves unchanged — see Consequences)

## Context

Issue #295's investigation
(`sim/sar-logic-functional-gates/investigations/20260916-issue-295-sw-conflict-root-cause.md`)
root-caused a severe, corner-independent violation of DR-0014's four-leg
switch-decode one-hot invariant (`sw_conflict_se`/`sw_conflict_df` measuring
7.7–13.0 against the `max=0.02` bound `sim/sar-logic-functional-gates/`
carries, unchanged from the ideal rung-1 sibling) to a genuine, measured
combinational hazard: `klt synthesize` (Yosys + ABC) folds
`design/sar-logic/rtl/sar_ctrl.v`'s shared `wire smpb = ~sel_in_n;`
intermediate directly into each of the 18 `rel_n_<weight><side>` cells via
De Morgan's law (e.g. `nor2_1(.A1(eng9), .A2(sel_in_n), .ZN(rel_n_256p))`),
so every cell reads the shared `sel_in_n` broadcast net directly instead of
through a shared inverter every cell would inherit equally. Direct
sub-nanosecond crossing-time measurement (`tt`/27&nbsp;C/3.30&nbsp;V) found the
mechanism precisely: `sel_in_n` falls at t=376.681 ns; all 9 p-side
`rel_n_<weight>p` legs rise together 143 ps later; all 9 n-side legs rise
together 163 ps later — a real, once-per-conversion, corner-independent
~143–165 ps window in which none of a cell's four one-hot legs
(`sel_in_n`/`rel_n`/`sel_hi_n`/`sel_lo_n`) is asserted, on all 18
switch-decode cells at once. The smaller `nside_cells_se` overshoot
(1.5–3×, DR-0011's mode rule) is the same mechanism at smaller magnitude
(a 1.2–1.7%-of-VDD transient glitch on the same edge). Issue #298 (this
record's own issue) was filed to choose and implement a fix direction: an
RTL/synthesis-constraint delay-balancing fix, or a decision record
documenting a disclosed, bounded real-hazard budget — explicitly *not* a
direct edit to DR-0014 or DR-0011 either way.

## Decision

**Accept the measured hazard as a disclosed, bounded real-hazard budget for
the synthesized-netlist regression check, and revise that check's bound
accordingly — leave `sar_ctrl.v`, the synthesized netlist, and the
already-merged `layout/adc-top/sar_ctrl/` P&R/STA artifacts unchanged.**
DR-0014's own decision (bottom-plate sampling, the four physical switch
legs, the fact that exactly one should be asserted) is untouched; what
changes is how tightly `sim/sar-logic-functional-gates/testbench/tb.json`'s
`sw_conflict_se`, `sw_conflict_df`, and `nside_cells_se` checks hold the
*synthesized-netlist* implementation of that invariant to an idealized,
zero-propagation-delay reading.

Revised bounds (from `max=0.02` to):

| Check | Old bound | New bound | Worst measured to date |
|---|---|---|---|
| `sw_conflict_se` | 0.02 | **15** | 9.99828 (`fs_27c_3.30v`) |
| `sw_conflict_df` | 0.02 | **20** | 13.0045 (`ss_27c_3.30v`) |
| `nside_cells_se` | 0.02 | **0.1** | 0.0644431 (`ff_27c_3.30v`) |

(all from the 5-point `mos`-process-axis subset at nominal 27&nbsp;C/3.30&nbsp;V,
`sim/sar-logic-functional-gates/records/20260915-214338-912a8ec.md`, plus
this record's own re-check at `tt_27c_3.30v` — see `sim/` evidence). Each
bound carries roughly 50% headroom over the worst value measured so far,
not zero margin — it is a real ceiling, not a rubber stamp: a *further*
regression (e.g. an actual overlap-type defect, or a second, independent
skew mechanism stacking on top of this one) would still fail the check.
`err_se_max/min`/`err_df_max/min` (the actual ±0.5 LSB conversion-correctness
check) are **unchanged** — they already read exactly 0 on every corner
tested and this record does not touch them.

### Why this is a real hazard budget, not a rubber stamp on an unverified assumption

The one-hot check's own design intent, as expressed in the executable
ideal-model specification (`design/sar-logic/gen_sar_logic.py`'s
`sar_slice`/top-level generator), is that a cell's `rel`/`sel_hi`/`sel_lo`
legs and the shared `sel_in` (`smpb`/`samp_bp`) leg reach the SAME logic
depth by construction: `samp_bp = INV(INV(samp4))` (two inverter stages)
matches `rel`'s own `INV(samp4) -> AND(engb, smpb)` (also two stages). The
generator's own comment on this exact structure is explicit: distributing
`samp_bp` through a matched two-inverter chain "is not cosmetic... a
one-gate depth difference [would open] a window in which a cell drives
V_in and Vcm at once — which is exactly what the one-hot invariant is
there to catch, and it would catch this generator" if it were built any
other way. `sar_ctrl.v`'s RTL replicates that same intent structurally
(`wire smpb = ~sel_in_n;` as an explicit shared node feeding every cell),
and it is Yosys/ABC's own De Morgan optimization during technology
mapping — not a defect in the RTL's own architecture — that discards the
shared node and re-introduces the very depth mismatch the RTL was written
to avoid. This record does not conclude the
same-depth architecture is unimportant in general; it concludes that, for
*this specific* implementation stage (technology-mapped standard cells with
no timing objective, see Alternatives), the resulting ~150 ns-per-day...
~150 ps-per-conversion hazard is physically bounded well below any
observable effect, for four independent, evidence-based reasons:

1. **It is a gap, not an overlap — confirmed, not assumed.** The
   investigation explicitly measured (Step 2b) that during the race window
   *neither* leg is asserted on the affected cell (`v(sel_in_n)+v(rel_n)+
   v(sel_hi_n)+v(sel_lo_n) reads 0, not vdd_val`), never that two legs are
   asserted together. Per `design/sar-logic/rtl/README.md`'s own port table,
   `rel_n_<weight><side>`/`sel_hi_n_<weight><side>`/`sel_lo_n_<weight><side>`
   and `sel_in_n` are literally the NMOS gate drives of the cell's four
   T-gate legs (`design/cdac/cdac_array.sch`'s own naming), with the
   complementary PMOS gate generated locally by `sar_tgate_drv`. A "gap"
   therefore means all four T-gate legs are simultaneously OFF for
   ~150–165 ps — the physical bottom-plate node is left floating
   (high-impedance) for that interval, not shorted between two different
   voltage rails. Break-before-make is the *safer* of the two possible
   hazards for a multiplexed switch network (it is, in fact, the standard
   defensive sequencing CMOS switch designs deliberately choose over
   make-before-break specifically to avoid shorting two different supplies
   together); this hazard lands on the safe side of that distinction by
   construction, not by luck.
2. **The window is short against every settling time constant this block
   already publishes.** DR-0014's own Alternatives section derives the
   array's worst bit-trial settling time constant as 570 Ω × 2.207 pF ≈
   1.258 ns (pre-DR-0019-resize figures; the post-resize array is larger,
   not smaller, so this remains a same-order-of-magnitude reference, not a
   stale one this record is trading on). `README.md`'s Input-structure row
   separately publishes 21.3–60.0 Ω series `R_on` over PVT for the
   bottom-plate T-gates. A ~150–165 ps window is roughly 12–15% of a single
   such τ — and that comparison is itself the *conservative* framing,
   because it treats the window as if the node were being actively driven
   toward a wrong rail for its whole duration (an RC-charging picture),
   which finding 1 above already rules out: the node is floating, not
   driven, for that interval, so no RC-charging error term even applies.
3. **A floating node's actual drift over 150 ps stays below one LSB at
   the leakage scale that actually applies — one to two orders of
   magnitude below it at sub-nA leakage.** With every leg's switch OFF,
   the only mechanism that can move charge on the node is reverse-biased
   junction/subthreshold leakage — sub-nA to low-nA scale for gf180mcu
   6 V-oxide devices at 3.3 V. The reference point is
   1 LSB = 3.3 V / 1024 ≈ 3.22 mV at 10 bits (`spec/prior-art-survey.md`).
   Draining a deliberately small ~1 fF node for the full 150 ps window
   gives `I·t/C`:
   - 100 pA → ≈15 µV ≈ 0.005 LSB (two orders below);
   - 1 nA → ≈150 µV ≈ 0.05 LSB (one to two orders below);
   - 5 nA (top of the low-nA range) → ≈750 µV ≈ 0.23 LSB — still below
     1 LSB, but by well under an order of magnitude.

   **The pessimistic 100 nA case is deliberately *not* what this record
   leans on, because by this same arithmetic it does not support a
   sub-LSB conclusion**: `100e-9·150e-12/1e-15 ≈ 15 mV`, which is ~4.7×
   1 LSB, not a fraction of it. Stated as a crossover instead: leakage
   would have to reach ≈21 nA (`3.22e-3·1e-15/150e-12`) for a 1 fF node
   to drift a full LSB in this window — one to two orders of magnitude
   above what OFF 6 V-oxide devices are expected to leak here, which is
   why the sub-nA branch above, not the 100 nA one, carries the
   conclusion. The realistic-leakage numbers are also before accounting
   for the fact that this is a single, non-repeating, sub-LSB-charge
   event per conversion rather than a steady-state offset. This is an
   order-of-magnitude argument, stated as one, not a claim of exact
   device-level leakage characterization — the direction (below 1 LSB,
   with one to two orders of margin at sub-nA leakage) is what this
   record relies on, not the last significant figure. It is also the
   weakest of the four pillars precisely because its leakage scale is
   assumed rather than measured; points 1 and 4 are the load-bearing
   ones.
4. **The functional evidence that actually matters already exists, and it
   is clean.** `err_se_max/min`/`err_df_max/min` — the real ±0.5 LSB
   conversion-correctness check, evaluated on the same closed-loop
   gate-level deck this hazard was measured on — read **exactly 0 on every
   one of the 5 `mos`-process corners already recorded**
   (`sim/sar-logic-functional-gates/records/20260915-214338-912a8ec.md`),
   including the corners where `sw_conflict_*` overshoots by 400–650×. The
   SAR converges to the bit-exact correct code every time, on the deck that
   is closest, in this repo, to modeling the real switch-decode legs'
   effect on conversion outcome.

None of the four points above is, alone, dispositive proof of zero real
risk at the transistor level (this repo's own `design/cdac/` is still a
schematic, not yet laid out with real T-gate sizing per cell/weight, and no
transistor-level closed-loop deck exercising the real CDAC against this
exact hazard exists yet) — which is why this record's bound carries real
margin rather than being set at "whatever the measured worst case is," and
why it is written as a decision record rather than silently widening
`tb.json`.

## Verification (issue #298's own replay against the revised bounds)

Issue #298's own acceptance criteria require replaying
`sim/sar-logic-functional-gates/` "at minimum the `tt`/27&nbsp;C/3.30&nbsp;V
point" and confirming `sw_conflict_se/df` (and `nside_cells_se`) read
within the *revised* bound above, with
`err_se_max/min`/`err_df_max/min` still exactly 0 — this is a check on the
revised bound actually holding, not a restatement of the evidence the bound
was chosen from (which is the pre-fix #289/#297 grid cited in the table
above).

- **`tt_27c_3.30v`** (record
  `sim/sar-logic-functional-gates/records/20260916-042719-e5440a0.md`):
  `sw_conflict_se=8.87556` (< 15), `sw_conflict_df=10.8095` (< 20),
  `nside_cells_se=0.0448873` (< 0.1), `err_se_max/min=0`,
  `err_df_max/min=0`. These values are numerically identical to the
  pre-fix `tt_27c_3.30v` point in `20260915-214338-912a8ec.md` — expected,
  since direction 3 makes no netlist change, so replaying the identical
  netlist reproduces the identical measurement. The run's overall status is
  `ERROR` (ngspice `Timestep too small` partway through the transient) —
  this is the **same pre-existing, already-tracked non-convergence defect**
  #289's own record documents at this exact corner (filed there as a
  separate follow-up, out of scope for both #289 and this issue), not a new
  failure this record introduces; the one-hot-invariant measurement itself
  is taken before the point of divergence and is unaffected by it.
- **`ff_27c_3.30v`** (record
  `sim/sar-logic-functional-gates/records/20260916-043850-e5440a0.md`):
  a fully-converging point (`status: PASS`), run as additional
  confirmatory evidence beyond the AC minimum. `sw_conflict_se=8.43144`
  (< 15), `sw_conflict_df=10.2862` (< 20), `nside_cells_se=0.0644431`
  (< 0.1), `err_se_max/min=0`, `err_df_max/min=0` — a clean
  complete-transient confirmation alongside the `tt` point above.

Both points satisfy this record's revised bounds and the AC's
`err_*` invariant. The AC's appended P&R/STA-re-run criterion does not
apply: direction 3 makes no netlist change, so the already-merged P&R
(#279) and STA (#278) sign-off against `layout/adc-top/sar_ctrl/` remain
valid as-is.

## Alternatives considered

- **Direction 2: an RTL delay-balancing fix (re-derive `rel_n` so it and
  `sel_hi_n`/`sel_lo_n` share the same combinational depth as `sel_in_n`,
  literally rebuilding the ideal model's `samp4 -> smpb -> samp_bp`
  two-inverter same-depth pattern in the RTL, e.g. via a `(* keep *)`
  attribute forcing Yosys to preserve a matching buffer chain instead of
  De Morgan-folding it away).** Not chosen. The mechanical piece (writing
  the RTL restructuring) is tractable, but it does not durably close the
  race in *this* flow: `design/sar-logic/flow/synth_sar_ctrl.py`
  (DR-0023 follow-on (a)) explicitly, deliberately carries **no SDC/STA
  claim** — `constraints.clock_period_ns` is left `null` and the script's
  own docstring states it "is asked for nothing beyond technology mapping."
  Yosys's generic `opt`/`techmap`/`abc` recipe has no delay objective at
  all to hold two paths equal; a `(* keep *)`-preserved buffer chain
  survives Yosys's own `opt` family (which honors `keep`) but is not
  proof against ABC's own boolean restructuring of the logic cone around
  it, and — critically — nothing in the existing automated flow would
  *notice* if a future re-synthesis (a different gf180mcu library corner,
  a Yosys/ABC version bump, or an unrelated RTL edit elsewhere in this flat,
  single-module design) silently re-broke the balance, short of manually
  repeating this exact investigation's own sub-nanosecond waveform probing
  by hand. A fix that only *looks* closed until the next resynthesis is a
  worse outcome than an honestly disclosed, evidence-bounded budget — this
  is precisely the risk issue #298's own curator flagged ("a wrong call
  could pass regression tests without actually closing the race"). A
  *durable* version of direction 2 would require extending the synthesis
  flow with a real timing methodology (an SDC `set_max_delay`/matching
  directive plus ongoing STA verification that it holds) — a materially
  larger scope than this issue's "delay-balancing exercise" framing, and a
  reasonable candidate for its own future issue if the physical case
  strengthens (see Consequences).
- **A synthesis-constraint fix via `synth_sar_ctrl.py`.** Not chosen for
  the same underlying reason: there is no delay-target/SDC input to this
  flow at all today (`constraints.clock_period_ns: null` by design, no
  ABC `-D`), so "add a constraint" is really "add a timing methodology,"
  not a small change to an existing lever.
- **Do nothing (leave the check bound at 0.02 and let it fail).** Not
  chosen — CLAUDE.md's "verification is the product" and "no claim without
  a testbench" both argue against leaving a check permanently red on a
  hazard this record has now investigated and bounded; a permanently
  failing regression check either gets ignored (worse than documenting the
  budget) or blocks unrelated work on this block indefinitely.
- **Widen `sw_conflict_se`/`sw_conflict_df`/`nside_cells_se` directly in
  `tb.json` with no decision record.** Not chosen — this is exactly the
  "agents do not relax the ratified spec to make results pass" pattern
  CLAUDE.md rules out; a `sim/` testbench bound is not itself a ratified
  spec row, but the discipline this record follows (a real decision,
  recorded, with evidence and alternatives) is the same one CLAUDE.md
  requires for spec changes, applied here because the check's own
  description already frames it as re-deriving a DR-0014 invariant.
- **Edit DR-0014 or DR-0011 directly to relax the one-hot invariant.** Not
  chosen, and explicitly out of scope per issue #298's own framing: neither
  record's underlying physical decision (bottom-plate sampling; the
  four-leg switch topology) is wrong or being revised here — only the
  *synthesized-netlist regression check's* tolerance for real, bounded gate
  delay is.

## Consequences

- **`layout/adc-top/sar_ctrl/`'s already-merged P&R (#279) and STA (#278)
  sign-off remain valid and are not touched by this record.** No netlist
  change means no re-run of `klt place-and-route` or `klt sta` is required
  — the gate-level netlist this record's evidence was measured against is
  bit-identical to what is already placed, routed, and timed.
- **The synthesized-netlist regression checks (`sw_conflict_se/df`,
  `nside_cells_se`) are now measurably weaker gates than their ideal
  rung-1 sibling's** (which stays at the tight, near-zero bound — it has no
  real gate delay to tolerate). A future defect that produces, say, a
  `sw_conflict_se` reading of 5 (a genuine new problem, five orders above
  the ideal floor but still inside this record's `max=15`) would now pass
  where the pre-#298 bound would have caught it. This is the real cost of
  this record's decision, stated plainly rather than left implicit.
- **This record's evidence base is a single-axis (`mos` process only),
  nominal-temperature/supply subset**, the same subset #289/#297 already
  disclosed as the tractable slice of the full 45-point grid (compute cost,
  not an oversight — `sim/sar-logic-functional-gates/records/
  20260915-214338-912a8ec.md`'s own notes). The revised bounds carry
  ~50% headroom specifically to absorb the temperature/supply axes this
  record has not yet measured, on the strength of the investigation's own
  finding that the mechanism is structural and corner-independent in
  magnitude across the axis actually swept — but the full grid replay,
  when it eventually runs (already an open item from #289, not newly
  created by this record), is the check on that assumption, not a
  formality.
- **If a future, more detailed transistor-level characterization of
  `design/cdac/`'s real per-cell T-gate sizing (not yet laid out) finds
  this record's order-of-magnitude argument was optimistic** — e.g. a real
  switch driver whose own response time is slow enough to matter at this
  scale, or a charge-injection interaction this record did not model —
  this record should be superseded, not patched, with the corrected
  evidence and (if warranted) a return to direction 2's durable
  timing-methodology fix.
- **No change to `err_se_max/min`/`err_df_max/min`, `code_se/df_max/min`,
  `conv_period_ns`, `acq_window_ns`, or `iso_gap_ns*`** — this record
  touches exactly the three checks named above and nothing else in
  `sim/sar-logic-functional-gates/testbench/tb.json`.

## Spec lines affected

- `README.md#target-specification` — none changed. No ratified spec row is
  added, widened, or relaxed by this record.
- `spec/decision-records/DR-0014-bottom-plate-sampling.md` — **not
  superseded, not edited**: the four-leg one-hot invariant it establishes
  stands unchanged; this record only revises how tightly a downstream
  *regression testbench* (`sim/sar-logic-functional-gates/`) checks a
  synthesized-netlist implementation of it.
- `sim/sar-logic-functional-gates/testbench/tb.json` — `sw_conflict_se`,
  `sw_conflict_df`, `nside_cells_se` checks — changed (`max=0.02` ->
  `max=15`/`max=20`/`max=0.1` respectively), citing this record.
