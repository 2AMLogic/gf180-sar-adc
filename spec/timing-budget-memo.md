# Conversion timing budget — worst-corner closure at 1 MS/s and the 2 MS/s stretch

**Status**: design memo, supporting the ratified Latency/conversion-timing row
in `README.md#target-specification` (not itself a decision record — see
`spec/decision-records/README.md`).
**Issue**: #12. **Consumes**: `spec/decision-records/DR-0003-clocking.md`
(#7, clock source/multiplier and jitter budget), `spec/cdac-sizing-memo.md`
§4/§5.3 (#8, unit cap and per-bit settling load), `spec/comparator-budget-memo.md`
§6 (#9, measured worst-case regeneration delay), `spec/decision-records/DR-0007-track-switch-topology.md`
(#10, track-window settling margin), `spec/decision-records/DR-0008-sar-logic-synchronous.md`,
`spec/decision-records/DR-0009-no-redundancy.md`, `spec/decision-records/DR-0010-mixed-signal-sim-strategy.md`
and `spec/decision-records/DR-0005-interface-scope.md` (#11, sync/async choice,
clock multiplier, cycle allocation, interface scope, and the still-open
transistor-level logic-delay gap).
**Does not re-derive**: DR-0003's aperture-jitter budget (cited, §5 below),
`spec/prior-art-survey.md` §1.4's placeholder cycle-allocation arithmetic
(superseded throughout by the closed dependencies' real numbers — see §1).

Every number below is either consumed from a closed, cited dependency, or
derived from those dependencies' own reported values using a convention this
repo has already established elsewhere (cited at the point of use). Nothing
here reuses `spec/prior-art-survey.md` §1.4's placeholder `C_u = 5 fF` /
`R_on = 1 kΩ` / `t_settle ≈ 19.5 ns` arithmetic.

---

## 0. What this memo does not decide

This memo consumes, and does not re-decide:

- **Sync vs. async and the clock multiplier** — DR-0008 ratifies synchronous
  SAR logic, `M = 16` (16 MHz @ 1 MS/s, 32 MHz @ 2 MS/s stretch). This memo
  budgets the resulting cycle count; it does not re-argue the choice.
- **The cycle allocation** — the ratified `README.md#target-specification`
  Latency row and DR-0003 already fix **4 sample cycles + 10 bit-trial
  cycles + 2 reset/output cycles = 16** at `M = 16`. This memo checks whether
  the physical processes that have to happen *inside* those allocated
  cycles actually fit, at the worst corner — it does not propose a different
  cycle count. (§3.4 below notes one place a *different, non-ratified*
  upstream draft number was used inconsistently — DR-0007's own settling
  margin used an unratified 300 ns acquisition estimate rather than the
  ratified 250 ns window — and corrects it without changing DR-0007's
  Decision.)
- **The interface scope** — DR-0005 ratifies a 10-bit parallel output
  register in scope for simulation-complete, with SPI deferred. This memo
  budgets that register's readout window; it does not reopen the scope
  question.
- **The aperture-jitter budget** — DR-0003 separately closes a budgeted rms
  aperture-jitter constraint (`≤ 250 ps rms` @ 1 MS/s, `≤ 180 ps rms` @
  2 MS/s stretch, evaluated at Nyquist with a 6 dB margin). That constraint
  bounds ENOB via sample-instant uncertainty; it is a **different closure
  condition** from this memo's conversion-*period* closure, and is cited,
  not re-derived, in §5.

---

## 1. Budget structure and worst-corner selection

Per the curator guidance on this issue, the budget is the explicit sum:

```
T_conversion ≤ 1 / f_s        (1000 ns @ 1 MS/s; 500 ns @ 2 MS/s stretch)

T_conversion = T_track (#10, worst-corner settling margin)
             + N × T_bitcycle,  N = 10
             + T_readout (#7/#11 interface scope)

T_bitcycle = T_CDAC_settle (#8, worst-corner)
           + T_comparator_regen (#9, worst-corner, measured)
           + T_logic_delay (#11, worst-corner — STILL OPEN, see §4)
```

**Worst corner: `ss_125c_2.97v`** (slow process **+** low supply **+** high
temperature, simultaneously, not evaluated independently) — the same
compounded corner `README.md#target-specification`'s Rate row already names
as binding for settling, and the corner every closed dependency this memo
cites (independently) measured as its own worst point over a full 45- or
117-point PVT grid:

- #9's comparator regeneration delay: worst at `ss_125c_2.97v`
  (`sim/comparator-regeneration/records/20260801-050155-109944e.md`).
- #10's/#4's T-gate `R_on`: worst at `ss_125c_2.97v`
  (`sim/device-switch-ron/records/20260731-191216-5f5288b.md`).
- #8's CDAC per-bit settling: error already at the simulator's numeric floor
  at every corner including `ss_125c_2.97v`
  (`sim/cdac-bit-settling/records/20260731-231537-1ee5578.md`).

**Both temperature extremes are represented, not assumed away.** Each of the
three full-grid sweeps above independently swept `-40/27/125 °C`; in every
one, the **hot** corner (`125 °C`, combined with slow process and low
supply) is the worst point, not the cold one — subthreshold mobility and
gain degradation at high temperature dominate over any cold-corner effect
for these particular quantities. This is stated because the acceptance
criteria for this issue explicitly calls out both extremes; the closed
dependencies already checked both, and hot wins in every term this memo
consumes.

---

## 2. `T_track` — the ratified 4-cycle track window

**Allocated** (ratified, `README.md#target-specification` Latency row,
DR-0003): 4 cycles = **250 ns @ 1 MS/s** (62.5 ns/cycle), **125 ns @ 2 MS/s**
(31.25 ns/cycle).

**Required**, re-derived from DR-0007's own worst-corner RC time constant
(`spec/decision-records/DR-0007-track-switch-topology.md`, Context):

```
tau_worst = (R_source,max + R_on,worst) * C_side
          = (500 ohm + 570.4 ohm) * 8.827 pF        [DR-0007, ss_125c_2.97v]
          ~= 9.45 ns

t_track,required = 7.62 * tau_worst                 [0.5 LSB @ effectively
                                                       11-bit settling
                                                       convention, the same
                                                       one DR-0002 and
                                                       spec/cdac-sizing-memo.md
                                                       Sec 5.3 already use]
                  ~= 72.0 ns
```

| | 1 MS/s | 2 MS/s stretch |
|---|---|---|
| Allocated | 250 ns | 125 ns |
| Required | 72.0 ns | 72.0 ns (RC time constant does not change with sample rate) |
| **Margin** | **178.0 ns (71.2 %)** | **53.0 ns (42.4 %)** |

Two things worth stating plainly rather than leaving implicit:

- **This is a conservative (pessimistic) bound.** DR-0007's `tau_worst`
  deliberately uses the **nominal** `10 µm/20 µm` T-gate geometry's
  `R_on` — DR-0007's own text calls this "the worst-case, smallest-device
  number" — even though the **actual chosen** switch is the 4× upsized
  T-gate with dummy compensation, whose `R_on` is proportionally lower
  (`R_on` scales ~1/W). The real margin with the as-chosen switch is larger
  still; this memo does not tighten the bound further because 42.4 % margin
  at the tighter (2 MS/s) rate already closes comfortably using the more
  conservative number.
- **A drafting inconsistency, corrected here.** DR-0007's own acquisition-
  margin narrative (`n_tau = t_track / tau_worst = 300 ns / 9.45 ns ~= 31.7
  tau`) used an **unratified** 300 ns acquisition-time estimate — carried
  over from `spec/prior-art-survey.md` §1.4's illustrative "30 % acquisition"
  split of the 1 µs period — rather than the **ratified** 4-cycle / 250 ns
  window the spec table and DR-0003 actually fix. Recomputed against the
  ratified 250 ns window above (26.5τ instead of 31.7τ), the conclusion is
  unchanged (both are astronomically more settling time than needed — `e^-26.5`
  residual vs. `e^-31.7`), but the number itself should read 250 ns, not
  300 ns, and this memo uses the ratified figure throughout. This does not
  reopen or change DR-0007's Decision (T-gate topology, 4× sizing, dummy
  compensation), which turned on the SFDR measurement, not on this margin.

---

## 3. `T_bitcycle` — the ten bit-trial cycles

### 3.0 No internal sub-cycle strobe — the whole cycle is the budget

`design/sar-logic/README.md` and DR-0008 both confirm the synchronous
controller has **one clock edge per bit-trial phase, no internal mid-cycle
strobe** splitting "settle" from "decide": the comparator's decision must be
valid and stable before the single clock edge that ends the phase and
advances the sequencer. So the three terms below are **additive against the
whole allocated bit-cycle** (62.5 ns @ 1 MS/s, 31.25 ns @ 2 MS/s), not
against independent sub-phase windows.

(`spec/comparator-budget-memo.md` §6/§9 separately reports comparator-regen
margin against a **self-imposed, more conservative** half-cycle "decide
phase" convention — 31.25 ns @ 1 MS/s / 15.625 ns @ 2 MS/s — as its own
budgeting choice, and hands `#12` the resulting margin (30.39 ns / 14.76 ns)
directly. That number is **consistent with, and strictly dominated by**, the
whole-cycle figure below: it is a stricter internal accounting `#9` chose
for its own closure, not evidence of an actual hardware sub-phase. Both
numbers are reported so neither convention is silently dropped.)

### 3.1 `T_CDAC_settle` — re-derived from #8's real array, not the survey placeholder

`spec/prior-art-survey.md` §1.4's placeholder used `C_u = 5 fF` and an
assumed switch `R_on = 1 kΩ` to get `t_settle ~= 19.5 ns`. #8 has since
closed with the real numbers (`spec/cdac-sizing-memo.md` §4, §5.2, §5.3):
`C_u = 17.24 fF`, and the worst bit trial (the sub-array's own MSB, `w =
256`, **measured** — not assumed — to be worst in
`sim/cdac-bit-settling/records/20260731-231537-1ee5578.md`) loads a
charge-divider `Ceq(256) = 128 * C_u = 2.20672 pF`, driven through the same
worst-case switch `R_on = 570 Ω` (`ss_125c_2.97v`,
`sim/device-switch-ron/records/20260731-191216-5f5288b.md`, the same figure
DR-0007 cites):

```
tau_worst        = R_on,worst * Ceq(256) = 570 ohm * 2.20672 pF ~= 1.258 ns
T_CDAC_settle    = 7.62 * tau_worst ~= 9.59 ns
```

**Measured cross-check**: `sim/cdac-bit-settling/records/20260731-231537-1ee5578.md`
measures the actual per-bit settling error at the **full** bit-cycle
checkpoint (62.5 ns @ 1 MS/s **and** 31.25 ns @ 2 MS/s) directly, at every
point of a 117-point PVT grid, and finds it already at the simulator's
numeric floor (`|err| <= 1e-4 mV`, four orders of magnitude inside the
0.5 LSB bound) at **every** corner and **every** weight measured — a
stronger (measured) result than the 9.59 ns analytical bound above requires.
Neither number reuses the survey's placeholder arithmetic.

### 3.2 `T_comparator_regen` — measured, #9, not re-derived

`sim/comparator-regeneration/records/20260801-050155-109944e.md` measures
decision delay at half-an-LSB overdrive across the full 45-point PVT grid:

```
T_comparator_regen,worst = 863 ps   (ss_125c_2.97v)
```

This is consumed as-is, per the issue's explicit instruction not to
re-derive it. One honest caveat carried forward from the record itself: it
states its netlist provenance was **"taken against a dirty working tree ...
not citable as a clean-tree result."** `spec/comparator-budget-memo.md`
(the closed #9 deliverable) already treats 863 ps as the authoritative
number and instructs `#12` to consume it directly (its own §9); this memo
does the same, and notes the caveat rather than silently dropping it.

### 3.3 `T_logic_delay` — STILL OPEN, flagged not silently absorbed

**This is the one term this budget cannot yet close with a transistor-level
number, and that gap is structural, not merely unmeasured:**

- DR-0008's own closed-loop rung-1 (ideal XSPICE digital) measurement
  (`sim/sar-logic-timing/records/20260801-033032-06bad60.md`) found the
  synchronous controller tolerates **up to 50 ns exact** of added
  comparator-decision delay within the 62.5 ns cycle before the conversion
  breaks (1 LSB over bound at 52 ns). DR-0008 itself is explicit that this
  is **"a rung-1 (ideal-digital) sanity-check figure, not a gf180mcu
  transistor-level worst-corner ... number"** — it is treated here exactly
  as instructed: a working sanity-check figure, not a substitute for a real
  measurement.
- The real number does not exist yet because **rung 3 of DR-0010's fidelity
  ladder (transistor-level SAR logic) is blocked on an unresolved PDK
  precondition, not merely un-scheduled**: the open gf180mcu PDK ships no
  3.3 V-device standard-cell library — both `gf180mcu_fd_sc_mcu7t5v0` and
  `gf180mcu_fd_sc_mcu9t5v0` are built entirely from `nfet_06v0`/`pfet_06v0`
  — while DR-0004 ratifies 3.3 V devices "throughout ... analog signal path
  **and** SAR logic / digital interface." Those two facts conflict, and
  DR-0010 states plainly that resolving the conflict (adopt the shipped
  6 V-oxide cells and supersede DR-0004's digital half, or hand-build 3.3 V
  cells with no existing GDS/LEF/Liberty) is **"a real decision that a
  future record has to make. It is not made here"** — nor is it made by
  this memo. `sim/sar-logic-cell-delay/`, the record that would carry this
  number, is named in `sim/sar-logic-functional/`'s own evidence notes but
  **does not exist** in this repository as of this memo.
- **This memo does not attempt to build a transistor-level SAR-logic
  implementation to manufacture this number.** That is #15's precondition
  to resolve (the DR-0004-vs-PDK conflict), not a gap a timing-budget memo
  can close by itself — doing so here would be exactly the kind of
  undisclosed scope expansion the Builder role's decomposition guidance
  warns against.

**What this memo does instead: state the margin that is actually available
for this still-open term**, given the two terms above are now real,
closed numbers:

```
margin_available_for_logic_delay = T_bitcycle,allocated
                                  - T_CDAC_settle,worst
                                  - T_comparator_regen,worst
```

| | 1 MS/s (62.5 ns cycle) | 2 MS/s stretch (31.25 ns cycle) |
|---|---|---|
| `T_CDAC_settle,worst` | 9.59 ns | 9.59 ns |
| `T_comparator_regen,worst` | 0.863 ns | 0.863 ns |
| Consumed so far | 10.45 ns | 10.45 ns |
| **Margin available for `T_logic_delay`** | **52.05 ns (83.3 %)** | **20.80 ns (66.6 %)** |

This is a materially healthier picture than a half-cycle framing would
suggest (see §3.0): even at the 2 MS/s stretch, roughly two-thirds of the
bit cycle remains unclaimed by the two now-closed terms. It is **not** a
substitute for the rung-3 measurement — it is the honest statement of how
much room that measurement has to land in before the budget stops closing.

**Testbench confirmation** (`sim/timing-budget-closure/`, this issue's
deliverable, §6 below): a closed rung-1 loop built from the real `T_CDAC_settle`
network and the real fixed 863 ps comparator delay, with a **swept**
candidate logic delay standing in for the still-open term, measures exactly
this margin structure: candidates of 0/10/25 ns close exactly at 1 MS/s
(well inside the 52.05 ns margin), 0/10 ns close exactly at 2 MS/s, but
**25 ns already produces a 2-code error at 2 MS/s** — a real, measured
crossing of the ~20.80 ns 2 MS/s margin by a candidate the 1 MS/s target
still absorbs without error. This is the measured form of this section's
headline finding, not merely the analytical one.

---

## 4. `T_readout` — the 2-cycle output-register window (#7/#11 scope)

**Allocated** (ratified cycle allocation): 2 cycles = **125 ns @ 1 MS/s**,
**62.5 ns @ 2 MS/s**.

**Scope, per DR-0005 (consumed, not re-decided)**: a 10-bit **parallel**
output register only, at full transistor level for simulation-complete; SPI
is explicitly deferred past this milestone. There is therefore **no serial
transfer time to budget** — the readout window only has to cover the
register's own load-and-settle time (`ph14`, per `design/sar-logic/README.md`)
plus the array's release back to `V_cm` (`ph15`).

**This term carries the identical structural gap as `T_logic_delay` (§3.3),
for the identical reason.** The parallel output register (`sar_bitreg`,
`design/sar-logic/sar_ctrl.spice`) is, at rung 1, built from the same ideal
XSPICE `d_dff` primitive (`T_CLK_Q = 0.5 ns` placeholder) as the rest of the
controller, and its transistor-level clk-to-Q and bus-settling delay is
gated behind the same DR-0010 rung-3 precondition (the DR-0004-vs-PDK
standard-cell conflict) as §3.3 — it is not a separate open question, it is
the same one applied to a different flip-flop bank. This memo does not
invent a number for it. Given the allocated window (125 ns / 62.5 ns) is
generous relative to the plausible order of magnitude of a single
register-stage delay (the same class of quantity as `T_logic_delay`, which
even a pessimistic multiple of the rung-1 ideal placeholder's 0.5–1 ns scale
would not approach), this term is unlikely to be the binding constraint —
but "unlikely" is not "closed," and it is flagged here on the same terms as
§3.3 rather than assumed benign.

---

## 5. Related, separately-closing constraint: aperture jitter (#7, cited not re-derived)

DR-0003 separately budgets **rms aperture jitter**, not conversion-period
closure: **≤ 250 ps rms** @ 1 MS/s target, **≤ 180 ps rms** @ 2 MS/s stretch,
evaluated at Nyquist (`f_in = 500 kHz`) with a 6 dB margin
(`SNR_jitter = -20*log10(2*pi*f_in*sigma_t)`). That constraint bounds ENOB
via sample-instant timing uncertainty on the *external* clock edge; it does
not bound how long a conversion takes once sampling occurs, which is this
memo's subject. The two constraints are independent and both apply; this
memo does not re-derive DR-0003's number and merely records that it exists
and is a distinct closure condition a real clock source must also satisfy.

---

## 6. Testbench: `sim/timing-budget-closure/`

**Deliverable, per this issue's acceptance criteria**: a testbench in `sim/`
demonstrating a complete conversion finishing within the period at the worst
PVT corner, run via the `#2` corner runner, with results appended per the
`#5` evidence format.

`sim/timing-budget-closure/` composes DR-0008's rung-1 synchronous
controller (`design/sar-logic/sar_ctrl.spice`, unmodified) with:

- a DAC-settling network sized from **real** worst-case component values
  (§3.1: `R = 570 Ω`, `C = 2.20672 pF`) instead of the survey's placeholder
  network `sim/sar-logic-timing/` uses (`R = 1 kΩ`, `C = 2.56 pF`) — the real
  network is **faster** (`tau = 1.258 ns` vs. `2.56 ns`), not slower, a
  finding worth stating because it runs opposite to the usual direction a
  "more realistic" correction moves a margin;
- a **fixed** 863 ps comparator transport delay (§3.2, measured, #9, not
  swept); and
- a **swept** candidate logic-propagation delay (§3.3, the still-open term:
  `+0/+10/+25/+55 ns`),

at **both** the 1 MS/s target (62.5 ns bit cycle) and the 2 MS/s stretch
(31.25 ns bit cycle), in one deck (`design/sar-logic/gen_sar_logic.py`'s new
`budget_closure()` target — the `_loop()` helper `#11` already built was
extended with optional `r_ohm`/`c_val`/`clk_net` parameters, defaulting to
the original placeholder values, so `functional()`/`timing()`'s committed
netlists are byte-identical to before this change).

**Same PVT-subset disclosure as `sim/sar-logic-timing/`**: this is rung-1
ideal-digital + behavioural analog, so process/temperature cannot move any
number in this deck — the worst-PVT-corner claim is carried by the injected
component *values*, each sourced from a closed, full-grid PVT sweep (#8/#9/#10),
not by sweeping this deck's own corners. The supply axis is swept in full.

**Result** (`sim/timing-budget-closure/records/20260801-091939-7aa8ed7.md`,
3/3 supply points, all `tt_27c`, clean tree — this is the fourth record in
the experiment's directory: the first run predates this memo's own commit
and is flagged "not citable as a clean-tree result" in the same way #9's own
regeneration record is; each subsequent run reproduces the identical result
and the final one carries a `Supersedes` chain back through all three prior
runs, per `sim/README.md`'s append-only convention):

| Bracket (candidate logic delay) | 1 MS/s error (LSB) | 2 MS/s error (LSB) |
|---|---|---|
| +0 ns | 0 (exact) | 0 (exact) |
| +10 ns | 0 (exact) | 0 (exact) |
| +25 ns | 0 (exact) | **2 (wrong)** |
| +55 ns | 255 (wrong, negative control) | 256 (wrong, negative control) |

This is exactly the margin structure §3.3 derives analytically: both rates
absorb a generous logic-delay allowance, the 2 MS/s stretch's margin is
measurably tighter and is the first to be exhausted, and both rates fail a
grossly over-budget candidate (the negative control that makes the other
results falsifiable, in the same spirit as `sim/sar-logic-timing/`'s `bad`
loop).

---

## 7. Summary — closure statement, both rates

| | 1 MS/s target | 2 MS/s stretch |
|---|---|---|
| `T_track`: required / allocated | 72.0 ns / 250 ns | 72.0 ns / 125 ns |
| `T_track` margin | **178.0 ns (71.2 %)** | **53.0 ns (42.4 %)** |
| `T_CDAC_settle` (worst, derived) | 9.59 ns | 9.59 ns |
| `T_comparator_regen` (worst, measured) | 0.863 ns | 0.863 ns |
| `T_bitcycle` allocated | 62.5 ns | 31.25 ns |
| Margin available for `T_logic_delay` (**open**) | **52.05 ns (83.3 %)** | **20.80 ns (66.6 %)** |
| `T_readout` allocated | 125 ns | 62.5 ns |
| `T_readout` actual | open (same rung-3 gap as `T_logic_delay`) | open (same rung-3 gap) |
| `T_conversion` (architectural identity, `16 * cycle`) | 1000 ns exact | 500 ns exact |

**The budget closes at the worst compounded corner (`ss_125c_2.97v`) for
every term this repo currently has a closed measurement for**, with large
stated margins (71.2 % / 42.4 % for tracking; 83.3 % / 66.6 % of the
bit-cycle still available for the open logic-delay term). **It does not yet
close on paper for `T_logic_delay` and `T_readout`'s register-stage delay**,
because no transistor-level gf180mcu number exists for either — a structural
gap (the DR-0004-vs-PDK standard-cell conflict, DR-0010) this memo surfaces
rather than silently absorbs, per this issue's explicit acceptance
criterion. The 2 MS/s stretch's margin for the open term (20.80 ns) is
materially tighter than the 1 MS/s target's (52.05 ns) and is demonstrated,
not merely predicted, to be the first to go negative as the real logic
delay grows (§3.3, §6) — this is reported as a real, stated finding, not
omitted because it is less favorable than the target case.

**Both rates are budgeted explicitly, as required**: the 1 MS/s target
closes with wide margin on every currently-measurable term; the 2 MS/s
stretch also closes on every currently-measurable term but with visibly
less headroom for the one term this repo cannot yet measure at the
transistor level.

## 8. Open items for follow-up (not resolved by this memo)

1. **`T_logic_delay` and the register-stage component of `T_readout`** need
   a gf180mcu transistor-level number, which needs the DR-0004-vs-PDK
   standard-cell conflict (DR-0010) resolved first — a precondition for #15,
   not a re-run this memo can perform.
2. **DR-0007's acquisition-margin narrative cites an unratified 300 ns
   acquisition estimate** (§2) rather than the ratified 250 ns window; a
   follow-up correcting that citation in DR-0007 itself is worth filing
   separately, consistent with DR-0007's own note that its SFDR-binding-
   corner citation likewise needs a follow-up record.
3. **`sim/comparator-regeneration/records/20260801-050155-109944e.md`** (#9's
   own closed deliverable) is flagged "taken against a dirty working tree,
   not citable as a clean-tree result" — upstream of this issue's scope to
   re-run. This memo's own `sim/timing-budget-closure/` experiment had the
   same issue on its first run and now carries a clean-tree, `Supersedes`-
   chained final record (`20260801-091939-7aa8ed7.md`, §6) minted as part of
   this issue's own PR.
