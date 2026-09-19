# DR-0028: Bound the gate-level acquisition window and isolation gap by the margin each protects, not by the value an idealised model happened to produce

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-19
- **Decided by**: Builder agent, issue #319
- **Supersedes**: none — first record on this question. The limits this
  record replaces were never in a `spec/` file or a decision record; see
  Context.
- **Superseded by**: (none while this record stands)
- **Related**: #319 (this record's own issue), #311 (the per-loop
  decomposition that produced the first scored gate-level grid),
  #320 (`abs_err_delay_0ns`, the *other* failure in the same record, which
  this record does not touch), #303/#289 (the earlier attempts at that
  grid), #58 (DR-0014's re-run, which this record sharpens),
  #274/#275 (P&R / STA — the post-layout re-check this record's limits are
  written to survive),
  [DR-0001](DR-0001-input-drive.md) (superseded input-drive contract, whose
  full-scale-step settling model this record deliberately does **not** use),
  [DR-0003](DR-0003-clocking.md) (`M = 16`, the 62.5 ns clock phase and the
  4-clock sample phase every limit below is expressed in),
  [DR-0013](DR-0013-input-pin-charge-split.md) (the in-force drive contract
  and the closed-form kick/recovery arithmetic the acquisition floor is
  derived from),
  [DR-0014](DR-0014-bottom-plate-sampling.md) (the two-phase sample these
  two measurements exist to check; **not** superseded — see Consequences),
  [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md) (the same
  standard-cell P/N-skew mechanism, root-caused there for `sw_conflict`),
  [DR-0023](DR-0023-digital-interface-device-flavor.md) (the synthesis flow
  that produced the netlist measured below),
  `sim/sar-logic-timing-gates-ok/records/20260918-233547-1d81aa1.md` (the
  45-point grid this record is decided from — left untouched),
  `sim/sar-logic-functional-gates/records/20260917-044312-c7ff0ff.md` (the
  independent cross-check),
  `sim/sar-logic-timing/records/20260802-102758-d8a363d.md` (the idealised
  single-point measurement the replaced limits were taken from),
  `sim/sar-logic-timing-gates/investigations/20260918-issue-311-per-loop-equivalence-and-inherited-ideal-bounds.md`
  (method, and the hypotheses ruled out)

## Context

`acq_window_ns` and `iso_gap_ns` are the two measurements that hold
[DR-0014](DR-0014-bottom-plate-sampling.md)'s two-phase sample to a number.
`acq_window_ns` is the duty cycle of `samp_tp_n` — how long per conversion
the input has to settle onto the bottom plates before the top-plate switch
opens, which *is* the sampling instant. `iso_gap_ns` is the mean of
`(sel_in_n − samp_tp_n)/vdd` — the lead of that opening over the bottom
plates leaving `V_in`, whose sign is the whole DR-0014 mechanism.

**Neither has ever had a derived bound.** The limits in force —
`acq_window_ns` 187.3 … 188.0 ns and `iso_gap_ns` 62.2 … 62.8 ns — appear
nowhere in `spec/`: not in `README.md#target-specification`, not in any
decision record, not in a memo. They entered the repo as manifest limits on
`sim/sar-logic-timing/`, set by rounding that deck's own single measurement
(187.625 ns / 62.4888 ns, `20260802-102758-d8a363d`) to roughly ±0.35 ns and
±0.3 ns, and were then copied unchanged into three further manifests. Two
properties of that origin matter:

1. **The source deck has no process axis at all.** Its `sar_ctrl_a` is an
   XSPICE behavioural model with fixed `T_CLK_Q`/`T_GATE` placeholders and
   no PDK device models, so it is run at `tt`/27 °C only. A single-corner
   measurement on a model that *cannot* move with process, temperature or
   supply was used to set a two-sided limit for a 45-point PVT grid.
2. **Sub-nanosecond logic-path delay is exactly what the model does not
   have.** These two integrals are pure control-path timing: they are the
   pulse width of one sequencer output and the skew between two of them.

Issue #311's decomposition produced the first scored gate-level grid for
this claim (`20260918-233547-1d81aa1`, 45 of 45 points). Over that grid:

| measurement | min | max | in-force limits |
|---|---|---|---|
| `acq_window_ns` | **176.927** (`fs_125c_2.97v`) | **197.177** (`sf_125c_2.97v`) | 187.3 … 188.0 |
| `iso_gap_ns` | **53.3104** (`sf_125c_2.97v`) | **73.3269** (`fs_125c_2.97v`) | 62.2 … 62.8 |

The real netlist's own PVT spread is **±10 ns**; the limit it is held to is
**±0.35 ns**. 42 of 45 points fail, and the 3 that pass do so by landing on
the ideal model's number by coincidence, not by being better points.

Four facts fix the diagnosis on the limits rather than on the design:

- **The measurement is reproducible to ~0.1 ns, across instruments.** The
  sibling `sim/sar-logic-functional-gates/` deck is a different composition
  of the same DUT (two loops, 20 ns maximum timestep, 60-conversion
  averaging window, never touched by #311). At 27 °C / 3.30 V, over the
  whole process axis, the two decks agree:

  | process | `acq_window_ns` functional / timing | Δ | `iso_gap_ns` functional / timing | Δ |
  |---|---|---|---|---|
  | `tt` | 186.182 / 186.215 | 0.033 | 64.0261 / 64.0043 | 0.022 |
  | `ff` | 186.742 / 186.707 | 0.035 | 63.4257 / 63.4666 | 0.041 |
  | `ss` | 185.525 / 185.608 | 0.083 | 64.7834 / 64.7114 | 0.072 |
  | `fs` | 179.743 / 179.754 | 0.011 | 70.3956 / 70.3865 | 0.009 |
  | `sf` | 192.972 / 192.990 | 0.018 | 57.3198 / 57.3145 | 0.005 |

  Worst disagreement **0.083 ns**, i.e. **24 % of the half-width of the
  limit it is scored against**. A bound only four times its own
  instrument's cross-deck reproducibility is a characterisation, not a
  specification. (Refining the timing deck's maximum timestep 20× moves
  these numbers by ≤ 0.0075 ns — the investigation note's finding 3 — so the
  0.083 ns is composition, not resolution.)

- **The two measurements are one degree of freedom, not two.** Over all 45
  points `acq_window_ns + iso_gap_ns` = **250.0946 … 250.5027 ns**: the
  `sel_in_n` pulse is DR-0003's 4-clock sample phase (4 × 62.5 = 250 ns) to
  within +0.50 / +0.09 ns *everywhere*, including at the skew corners. What
  moves over ±10 ns is only **where `samp_tp_n`'s falling edge sits inside
  that pulse** — the split between acquisition and isolation. Bounding both
  independently at ±0.35 ns was therefore bounding one quantity twice.

- **The mechanism is known and is already recorded elsewhere.** The spread
  is dominated by the P/N skew corners (`fs` shortest acquisition, `sf`
  longest), i.e. standard-cell rise/fall asymmetry along the two control
  paths — the same mechanism
  [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md) root-caused for
  `sw_conflict`, where `fs`/`sf` are likewise the worst corners. Per-axis
  sensitivity in the record agrees: process 4.7–10.8 % for `acq_window_ns`
  against 0.16–2.4 % for temperature and supply.

- **The obvious substitute is refuted by committed evidence.** The
  functional decks' wider pair (185 … 190 / 60 … 65) does **not** rescue
  this: `20260917-044312-c7ff0ff` fails it too, at `fs_27c_3.30v`
  (179.743 / 70.3956) and `sf_27c_3.30v` (192.972 / 57.3198). Issue #319's
  premise that the sibling deck "PASSES on the same measurements" holds only
  at the single `tt` point it quoted; over the process axis the sibling
  fails as well. That pair is the same kind of number — 187.5 ± 2.5 round
  window about the same ideal nominal — and inherits the same defect.

## Decision

**Bound both measurements by the margin each protects, derived from the
in-force drive contract and clock phase, and state that margin in the
manifest. The resulting limits are layout-independent: one limit, applying
unchanged pre- and post-layout.**

| check | in force | **ratified here** | derivation |
|---|---|---|---|
| `acq_window_ns` min | 187.3 | **175.0** | settling floor: `τ_max · ln(kick_max / 0.25 LSB)` = 30 ns × ln(83.06 / 0.25) = 174.17 ns, rounded **up** to the nanosecond |
| `acq_window_ns` max | 188.0 | **218.7** | 250 ns sample phase − 31.25 ns isolation floor = 218.75 ns, rounded **down** |
| `iso_gap_ns` min | 62.2 | **31.3** | ordering floor: half of one DR-0003 clock phase = 31.25 ns, rounded **up** |
| `iso_gap_ns` max | 62.8 | **75.0** | 250 ns sample phase − 175.0 ns acquisition floor |

Every rounding is toward the stricter side, so no ratified limit is ever
looser than the derivation behind it. The measurement *expressions* are
unchanged; only the limits move.

### The acquisition floor is a settling budget

The margin `acq_window_ns` protects is the un-recovered input-pin
redistribution kick at the sampling instant. That is DR-0013's own closed
form, evaluated over DR-0014's acquisition window instead of the 300 ns
track window DR-0013 assumed:

```
kick    = 1024 · C_in/(C_in + C_pin) = 1024 · 8.827/108.827 = 83.06 LSB   (C_pin = 100 pF, the worst permitted)
residual(W) = kick · exp(−W / τ_in),  τ_in ≤ 30 ns          (DR-0013's contract ceiling)
```

Allocating **0.25 LSB** to this term — half of the ½-LSB settling criterion,
so it stays *negligible rather than merely legal*, which is DR-0013's own
stated sizing rule applied one level up — gives
`W ≥ 30 × ln(83.06/0.25) = 174.17 ns`, ratified at **175.0 ns**.

| W | residual at `τ_in = 30 ns`, `C_pin = 100 pF` |
|---|---|
| 250 ns (whole sample phase) | 0.020 LSB |
| 218.7 ns (this record's upper limit) | 0.057 LSB |
| 187.5 ns (DR-0014 nominal, 3 clocks) | 0.160 LSB |
| **176.93 ns (worst corner measured)** | **0.228 LSB** |
| **175.0 ns (this record's floor)** | **0.243 LSB** |
| 153.38 ns | 0.500 LSB — the ½-LSB criterion itself |
| 125.0 ns (one clock phase dropped) | 1.288 LSB |

The floor is **not** DR-0001's `t/τ ≥ ln(2¹¹) = 7.62` full-scale-step rule,
which would demand 228.6 ns and which nothing in this architecture meets.
That rule is superseded: DR-0013 supersedes DR-0001 precisely by replacing
the full-scale-step model with the pinned-capacitor one, in which the pin
never takes a full-scale step and only the 83.06 LSB redistribution kick has
to be recovered. Using the superseded model here would be re-deriving a
requirement the spec has already retired.

### The isolation floor is an ordering margin

`iso_gap_ns` has exactly two real failure modes, and both are one clock
phase in size: the second phase **dropped** (gap → 0) and the two phases
**swapped** (gap → −62.5). Its physical requirement is that the top-plate
switch be fully off — a sub-nanosecond gate transition — before the bottom
plates move; everything above that is dead time. A floor at **half a clock
phase, 31.25 ns**, therefore:

- leaves **22.0 ns** of headroom beyond the worst PVT excursion measured
  (53.31 ns at `sf_125c_2.97v`, i.e. 9.19 ns below nominal) — **2.4×** the
  measured excursion itself, available for P&R interconnect skew, extracted
  parasitics and on-die mismatch, none of which is in this netlist;
- still fails decisively on both real modes (by 31.25 ns and 93.75 ns);
- is the largest round fraction of a phase that keeps ≥ 2× headroom while
  staying far clear of the 62.5 ns nominal, where the margin would be zero.

### Why the two upper limits are the other two floors

Because `acq_window_ns + iso_gap_ns` is the 250 ns sample phase to within
half a nanosecond (Context), an upper limit on either measurement *is* a
lower limit on the other. Deriving them that way is the only
self-consistent choice: it makes the four limits two independent
requirements rather than four unrelated numbers, and it is why the
acquisition side is tight (1.93 ns of slack at `fs_125c_2.97v`) while the
ordering side is loose (22.0 ns at `sf_125c_2.97v`). **That asymmetry is the
finding**: input settling is the binding constraint on the two-phase sample,
and the ordering claim is robust across the whole PVT box. The ±0.35 ns
fence could not say which side mattered, because it failed on both.

### Pre- or post-layout

**Neither — the limits are layout-independent, and that is deliberate.**
Every input to the four derivations above (DR-0013's `τ_in ≤ 30 ns` and
`C_pin ≥ 100 pF`, DR-0003's 62.5 ns clock phase, the ½-LSB criterion) is a
spec quantity that place-and-route does not change. So this record ratifies
**one** limit for both stages rather than a pre-layout limit to be
re-baselined later. What *is* pre-layout is the evidence, and therefore the
slack: 1.93 ns on the acquisition floor and 22.0 ns on the ordering floor,
measured on a netlist with no extracted parasitics and no interconnect delay
(`20260918-233547-1d81aa1`, netlist provenance). That makes #274/#275's
post-layout re-run a real test of this record rather than a formality — see
Consequences.

## Alternatives considered

- **Keep 187.3 … 188.0 / 62.2 … 62.8 and treat the netlist as failing —
  i.e. close it in the design.** Not chosen, and not because it is
  expensive: because it is not achievable and never was. Meeting a ±0.35 ns
  window means matching two standard-cell control paths' rise/fall
  asymmetry to **0.6 % of a clock phase** across `tt`/`ff`/`ss`/`fs`/`sf` ×
  −40…125 °C × ±10 %, on a flow that
  [DR-0023](DR-0023-digital-interface-device-flavor.md) gives no timing
  objective at all and where the skew corners alone move it by ±10 ns. No
  synthesis constraint reaches that; it would take a different control-path
  structure, and even a perfectly matched one still sees P/N skew. Filing it
  as design closure would park a permanent fake blocker on the project. It
  also has a measured cost already visible in the same record: 42 rows of
  known, diagnosed, non-defect FAIL buried the one real defect in that grid
  — `abs_err_delay_0ns` at 10 of 45 points, up to 512 LSB (#320). A check
  that cries wolf at 93 % of the grid is a check readers learn to skip.
- **Adopt the functional decks' pair, 185 … 190 / 60 … 65.** Not chosen:
  **refuted by committed measurement.** `20260917-044312-c7ff0ff` fails that
  pair at `fs_27c_3.30v` and `sf_27c_3.30v` on the same netlist (Context).
  It would move the failure, not resolve it — and it is the same species of
  number, a round window about an ideal nominal, with no margin behind it.
- **Re-baseline on the gate-level measurement itself** — e.g. 176 … 198 /
  53 … 74, the measured grid plus a little. Not chosen, and this is the
  option that most needs a stated why-not, because it is what "re-derive the
  bounds from the gate netlist" sounds like. It repeats the original
  mistake in a new place: a limit set from what one netlist measured, on one
  pre-layout snapshot, tells a future reader nothing about what is
  *required*, and guarantees a re-ratification at P&R, again at extraction,
  again at any netlist re-synthesis. The bound would track the design
  instead of constraining it. The measured grid is used here only to state
  the **slack**, never to set the limit.
- **Drop the two checks from the gate-level deck and keep them only on the
  ideal deck.** Not chosen. They are the only checks anywhere that can see
  DR-0014's two-phase sample at all — the behavioural decks' sample-and-hold
  is clocked by the top-plate control *by construction*, so a dropped or
  swapped isolation phase would leave every converted code correct. Deleting
  them would make the mechanism DR-0014 exists for unverifiable on the
  implementation that will be taped out.
- **Tighten the sum instead** (bound `acq + iso` at 250 ± ε and leave the
  split free). Not chosen, though the invariant is real and is used above.
  The sum is insensitive to the failure that matters: swapping the two
  phases leaves it unchanged, and a dropped isolation phase shows up in it
  only as one clock. The split is where the information is.

## Consequences

- **All 45 points of `20260918-233547-1d81aa1` meet these limits**
  (worst slack 1.93 ns / 1.67 ns, both at `fs_125c_2.97v`), and the record
  stays **FAIL overall** — `abs_err_delay_0ns` still fails at 10 points, by
  up to 512 LSB, which is #320's real conversion defect. This record does
  not make a failing grid pass; it removes 42 rows of inherited noise from
  in front of a defect. The record itself is untouched, as `sim/`
  append-only requires: it is *re-read against* this decision, and its own
  "EXPECTED FAIL … BOUNDS DELIBERATELY NOT RELAXED" note remains exactly
  true as written — it said the question was routed to #319, and this is
  #319's answer. Nothing is re-run and nothing is re-scored; the next run of
  either deck mints a new record under the new limits.
- **Real detection power is given up, and it should be named.** These decks
  can no longer see a ±10 ns shift in the sequencer's control-path timing —
  a regression that changes which corner is worst, or a synthesis change
  that adds a gate to one of the two paths. That is a genuine loss and it is
  accepted because the replaced bound could not distinguish such a shift
  from the netlist's own PVT spread anyway. What still catches the
  consequences: `sw_conflict_*` / `nside_cells_*` (DR-0027's hazard budget)
  sees decode-path skew directly, `abs_err_delay_*` sees any timing shift
  large enough to break a conversion, and `ok_conv_period_ns` (45/45 at
  1000 ns) sees any change in cadence.
- **The acquisition floor has 1.93 ns of pre-layout slack, and that is
  thin — stated first because it is the risk this record carries.** P&R adds
  interconnect delay to both control paths (#274/#275). If it lengthens the
  `samp_tp_n` path's fall relative to its rise by ~2 ns at the `fs` corner,
  this floor breaks — and that would be a **real** finding, not a bound
  problem, because at that point the acquisition residual genuinely exceeds
  the 0.25 LSB allocated to it. The correct response then is design closure
  (or an explicit re-allocation with its own record), not another widening.
- **A previously unstated consequence of DR-0014 is quantified here, and it
  lands on #58.** DR-0013 evaluated its residual over a 300 ns track window
  and got 0.0038 LSB. DR-0014's acquisition sub-phase is 3 of DR-0003's 4
  sample clocks — 187.5 ns nominal, 176.93 ns at the worst measured corner —
  over which the same closed form gives **0.160 LSB** and **0.228 LSB**: a
  **42–60× increase** in the worst-case in-contract acquisition residual, on
  a term DR-0013 called negligible. It is still inside the ½-LSB criterion,
  and it is no longer a minority term against DR-0012's ≤ 0.5 LSB row.
  DR-0014 already invalidated DR-0013's 0.421 LSB measurement and required
  #58 to re-take it; this record says by how much the budget moved and why,
  so #58 re-takes it knowing that. **No spec row and no DR-0013 value is
  changed here** — this is arithmetic on in-force numbers, not a new
  contract. (It also surfaces a reconciliation DR-0013's 300 ns and
  DR-0003's 250 ns sample phase have always needed; settling that is #58's,
  not this record's.)
- **The rung-1 ideal deck keeps its tight limits, deliberately.**
  `sim/sar-logic-timing/testbench/tb.json` is **not** changed: its DUT is a
  fixed-delay XSPICE model with no process axis, so 187.3 … 188.0 /
  62.2 … 62.8 is a correct and useful regression guard *there* — it pins the
  generator's output, where the value is deterministic and 187.625 /
  62.4888 is reproducible to the digit. The two decks measure the same
  expression for different purposes: one guards a generator, the other
  bounds a physical margin. This record is explicit that this is a
  divergence on purpose, not an oversight.
- **The functional decks are left divergent, and that is a debt.**
  `sim/sar-logic-functional/` and `sim/sar-logic-functional-gates/` keep
  185 … 190 / 60 … 65 (and `iso_gap_df_ns`), so the gate-level *functional*
  deck goes on failing at `fs`/`sf` for exactly the reason this record
  adjudicates, and is now held tighter than the gate-level *timing* deck
  that owns the tight claim. Harmonising it is out of #319's stated scope —
  it would re-interpret five committed records and touch a fourth
  measurement this record has no evidence for (`iso_gap_df_ns`, the
  differential loop). Filed as a follow-on issue so it is tracked, not
  forgotten.
- **[DR-0014](DR-0014-bottom-plate-sampling.md) is not superseded and not
  weakened.** Its decision — bottom-plate sampling, the top-plate switch
  opening first, the four-leg cell — is untouched. What changes is that its
  acquisition/isolation claim now has a numeric form with a derivation
  behind it, which it has never had. The sign requirement on `iso_gap_ns` —
  the entire mechanism — is strengthened in practice rather than relaxed:
  it is now enforced with 31.3 ns of required positive margin instead of
  being implied by a window that no corner could satisfy.
- **A reader can no longer conclude "the sequencer is sub-nanosecond
  accurate" from a passing grid.** They never could — that claim was only
  ever true of the XSPICE model — but the passing checks will now say so
  honestly, because each carries its derivation in its own description.

## Spec lines affected

- `README.md#target-specification` — **none changed**. No row is added,
  widened, relaxed or removed. The acquisition window and isolation gap have
  no row in the ratified table; their only operative form is the manifest
  limit revised below, which is why this record exists.
- `sim/sar-logic-timing-gates/testbench/tb.json` — `acq_window_ns` —
  **changed** (`min 187.3` → `175.0`, `max 188.0` → `218.7`); `iso_gap_ns` —
  **changed** (`min 62.2` → `31.3`, `max 62.8` → `75.0`). Measurement
  expressions unchanged.
- `sim/sar-logic-timing-gates-ok/testbench/tb.json` — same two checks,
  **changed identically**. The two manifests must not diverge;
  `sim/tests/test_sar_ctrl_gates_tb.py::PerLoopManifestBoundsTests`
  enforces that mechanically.
- `spec/decision-records/DR-0014-bottom-plate-sampling.md` — **not
  superseded, clarified**: the acquisition-window and isolation-gap claim it
  makes is given the bounded numeric form it never carried, with the margin
  each bound protects stated. No value in DR-0014 changes.
- `spec/decision-records/DR-0013-input-pin-charge-split.md` — **not
  superseded, no value changed; evidence re-read**: the drive contract
  (`C_pin ≥ 100 pF`, `R_source × (C_pin + C_in) ≤ 30 ns`) is used here
  exactly as ratified. Its residual *figure* (0.0038 LSB over 300 ns) is
  restated over DR-0014's actual acquisition window in Consequences; the
  re-measurement that follows is #58's, already required by DR-0014.
- `sim/sar-logic-timing/testbench/tb.json`,
  `sim/sar-logic-functional/testbench/tb.json`,
  `sim/sar-logic-functional-gates/testbench/tb.json` — **unchanged, by
  decision**: see Consequences for why the first is deliberate and the other
  two are a tracked follow-on.
