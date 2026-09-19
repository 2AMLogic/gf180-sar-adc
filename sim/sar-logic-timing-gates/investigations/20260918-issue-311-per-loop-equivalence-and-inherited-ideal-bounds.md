# Investigation 20260918-issue-311-per-loop-equivalence-and-inherited-ideal-bounds

Not a `sim/run_corners.py` evidence record — no PVT grid is scored *here*, and
nothing below is citable as a spec claim. These are the working notes behind
issue #311's decomposition of `sim/sar-logic-timing-gates/` into five
single-loop decks. Kept in `investigations/`, alongside (not inside)
`records/`, so the append-only `records/` tree is never edited.

The scored grid this session produced is an ordinary record under the new
`sim/sar-logic-timing-gates-ok/records/` directory. This note is the method,
the equivalence argument, the cost table, and the two design decisions
(evidence-tree shape, and what to do about two bounds that turn out not to
hold on the real gate netlist).

**Why it exists**: issue #311 asks for four things that are judgement calls
rather than code — which evidence-tree shape the split takes, whether the
split changed any measured number, what the decomposed shape actually costs,
and what to do when a carried-over bound fails. Each is answered below with
the measurement that settles it, so a reader can re-run and disagree.

## Summary of findings

1. **The split is a re-composition, not a re-modelling — and that is now
   enforced by tests, not asserted.** Each per-loop deck's loop block is
   byte-identical to the same loop's block in the five-loop deck, each
   per-loop manifest's `measure` expressions and numeric `checks` limits are
   byte-identical to the five-loop manifest's, and together the five
   manifests partition the five-loop manifest's nine measurements exactly.
   `sim/tests/test_sar_ctrl_gates_tb.py::PerLoopTimingDeckCompositionTests`
   and `::PerLoopManifestBoundsTests` fail if any of that stops being true.
   These run without a PDK, so they hold on the CI PR path.

2. **A direct five-loop vs one-loop comparison was run — over a 250 ns
   window, the longest the five-loop deck can actually finish here — and
   the two compositions agree.** See "Direct cross-check" below. A
   five-loop run over the *full* ratified 8.5 µs window at nominal PVT was
   not affordable and is **not** claimed; per issue #311 step 4 this note
   says so rather than asserting equivalence over a window nobody ran.

3. **Timestep resolution is not what moves these numbers.** Re-running the
   `ok` deck's own first scored conversion window at a 5x and a 20x finer
   maximum timestep leaves `acq_window_ns` unmoved to six significant
   figures and moves `iso_gap_ns` by 0.0075 ns — 0.6 % of the 1.2 ns by
   which it exceeds its bound. The finer steps a five-loop composition is
   *forced* into therefore cannot explain the overshoot either.

4. **`acq_window_ns` and `iso_gap_ns` do not hold on the real gate netlist,
   and their bounds were NOT relaxed to make the grid pass.** Both bounds
   were measured on, and inherited unchanged from, the **rung-1 ideal** deck
   `sim/sar-logic-timing/` (record `20260802-102758-d8a363d.md`: 187.625 ns
   and 62.4888 ns), whose `sar_ctrl_a` is an XSPICE model with fixed
   `T_CLK_Q`/`T_GATE` placeholders. Real `gf180mcu_fd_sc_mcu7t5v0` logic-path
   delay puts the same two duty-cycle integrals near 186.2 ns / 64.0 ns —
   outside bounds only 0.7 ns and 0.6 ns wide. This is a **pre-existing
   property of the gate-level DUT that #311's decomposition merely made
   visible**, because the five-loop deck never produced a scored point in
   which it could show up. Revising the bounds is a spec question with its
   own decision record; it is explicitly out of #311's scope and is filed as
   **issue #319** rather than done here.

5. **Cost: the decomposition works, but issue #311's own "~660 core-s per PVT
   point" projection is a lower bound that holds only for the cheapest
   loop.** That figure was 5 x the measured `ok` loop. Measured per tag, the
   loops are not alike — `tie` costs 3.3x `ok`, and the delay-line loops
   (`lt`/`xl`/`bad`, which insert an ideal lossless transmission line ahead
   of the gate logic) are more expensive still. See the cost table. The
   decisive property of the split is therefore *not* that every loop became
   cheap; it is that **each loop's grid is independently runnable,
   schedulable, timeout-able and parallelizable** instead of all five being
   hostage to one global timestep — which is what turned a grid that had
   failed three times into one that completes.

6. **Evidence-tree shape, decided explicitly: five experiment slugs.** Not a
   deck-variant axis on the existing manifest. Rationale below.

7. **The grid ran — 45 of 45 points — and immediately found something nobody
   had been able to see before.** Beyond the two inherited bounds of finding
   4, the `ok` loop's own correctness check `abs_err_delay_0ns` fails at **10
   of the 45 points**, by as much as 512 LSB, concentrated at 125 °C and at
   the slow-logic process corners. That is a real conversion failure of the
   synthesized netlist with *zero* added comparator-to-latch delay, and it is
   filed as **issue #320**. It is the point of the whole exercise: a deck that
   cannot be run cannot find defects, and this one had never produced a scored
   point in three attempts. See "What the grid found" below.

## Decision 1 — five slugs, not a deck-variant axis

Issue #311 asked for one of two shapes to be picked deliberately rather than
by accident:

| shape | what it would mean |
|---|---|
| **five slugs** (chosen) | `sim/sar-logic-timing-gates-{ok,lt,xl,bad,tie}/`, each with its own `testbench/tb.json`, `records/`, `corners/` |
| deck-variant axis | one slug whose manifest names several netlists and scores a measurement subset per variant |

**Chosen: five slugs**, because the manifest schema names exactly *one*
`netlist` per experiment and the corner runner scores exactly one deck per
PVT point. A deck-variant axis would mean teaching the shared harness a new
composition primitive that every other experiment in `sim/` would then
inherit — a harness-design decision with its own review, its own regression
surface, and no other caller asking for it. Five slugs need no harness change
at all: each is an ordinary experiment directory that `sim/run_corners.py
<slug>` already understands, and each can be run, scheduled, timed out and
recorded independently — which is precisely the property that makes the
decomposition worth doing.

The cost of that choice, stated plainly: the five loops' results no longer
live in one record, so a reader comparing `ok` against its `bad` negative
control has to open two records instead of one. The five manifests carry
cross-references to each other and to the five-loop parent for that reason,
and the parent `sim/sar-logic-timing-gates/` deck, manifest and its
append-only #289 record are kept **unmodified**, as the full-composition deck
this note cross-checks against.

The nine measurements partition exactly, with every numeric limit unchanged:

| slug | checks carried over | limits |
|---|---|---|
| `-ok` | `abs_err_delay_0ns`, `ok_conv_period_ns`, `acq_window_ns`, `iso_gap_ns` | max 0.5; 999.9…1000.1; 187.3…188.0; 62.2…62.8 |
| `-lt` | `abs_err_delay_40ns` | max 0.5 |
| `-xl` | `abs_err_delay_50ns` | max 0.5 |
| `-bad` | `abs_err_delay_70ns` | **min 0.9** — the negative control, asserting the conversion IS wrong |
| `-tie` | `tie_code_deviation`, `tie_conv_period_ns` | max 1; 999.9…1000.1 |

## Decision 2 — the two failing bounds are left alone

`CLAUDE.md` is explicit: *"agents do not relax the ratified spec to make
results pass"*. Two bounds carried over from the five-loop manifest fail on
the `ok` grid:

| bound | limit | rung-1 ideal measured | this deck, `tt`/27 °C/3.30 V | sibling gate-level deck, same PVT point |
|---|---|---|---|---|
| `acq_window_ns` | 187.3 … 188.0 | 187.625 | 186.215 | 186.182 |
| `iso_gap_ns` | 62.2 … 62.8 | 62.4888 | 64.0043 | 64.0261 |

Sources, in order: `sim/sar-logic-timing/records/20260802-102758-d8a363d.md`;
this session's single-point calibration run of the `ok` deck; and
`sim/sar-logic-functional-gates/records/20260917-044312-c7ff0ff.md` row
`tt_27c_3.30v`.

Three hypotheses were considered and two were ruled out:

- **"the decomposition changed it"** — ruled out twice over. The sibling
  `sim/sar-logic-functional-gates/` deck is a *different* composition (two
  loops, 20 ns maximum timestep, 60-conversion averaging window) of the
  *same* synthesized DUT and lands on the same values (last column above);
  it has never been touched by #311. And the direct 250 ns five-loop vs
  one-loop cross-check below finds no divergence.
- **"a one-loop deck takes coarser timesteps, so the duty-cycle integral is
  under-resolved"** — ruled out by direct refinement (Method, below).
- **"the ideal XSPICE `sar_ctrl_a`'s fixed `T_CLK_Q`/`T_GATE` placeholders
  are not the real `gf180mcu_fd_sc_mcu7t5v0` logic-path delay"** — the
  surviving explanation. It is corroborated by the sibling deck's bounds for
  these same two measurements being materially wider (`acq_window_ns`
  185…190, `iso_gap_ns` 60…65, inherited from `sim/sar-logic-functional/`),
  wide enough that the gate-level values pass there while failing here. The
  two rung-1 decks disagree about how tight these bounds should be, and only
  the tighter pair was ever validated against an idealised model.

So the `ok` grid is committed **failing** those two checks, with the failure
diagnosed in advance in the record's own notes, and the spec question routed
to **issue #319**. That is the honest state of
the claim: the gate-level netlist meets the *cadence* and *conversion
correctness* bounds and does not meet two sub-nanosecond timing bounds that
were set on an idealised model of itself.

## What the grid found

Record `sim/sar-logic-timing-gates-ok/records/20260918-233547-1d81aa1.md`:
**45 of 45 points completed**, the first scored grid this claim has ever had.
3 points PASS (`tt_125c_3.63v`, `ff_125c_3.30v`, `ff_125c_3.63v`); 42 FAIL.

Two distinct failure families, which must not be conflated:

1. **`acq_window_ns` / `iso_gap_ns`** — fails at 42 of 45 points. This is
   Decision 2 above: bounds inherited from an idealised model. Routed to
   issue #319.
2. **`abs_err_delay_0ns`** — fails at **10 of 45 points**, measuring 1, 1, 5,
   5, 252, 252, 252, 252, 512 and 512 LSB against a `<= 0.5` bound. The
   remaining 35 points measure exactly 0. Routed to issue #320.

The second is the serious one and it is **new information, not an inherited
bound problem**. `abs_err_delay_0ns` is the `ok` loop's reference correctness
check — no added comparator-to-latch delay at all, the case that is supposed
to be comfortably correct. 512 LSB is exactly a flipped MSB on a 10-bit
converter and 252 is near a flipped bit 8. The failures concentrate at 125 °C
(6 of 10) and at the `sf`/`ss` process corners (6 of 10) — where the
standard-cell logic path is slowest, which is what a setup violation inside
the SAR register would look like. `ok_conv_period_ns` is 1000 ns at every one
of the 45 points including the failing ones, so the converter keeps cadence
and emits a wrong code rather than stalling.

`ok_conv_period_ns` passes 45 of 45. The cadence claim holds on the gate
netlist across the full PVT box; the correctness claim does not.

This is what the decomposition bought. The five-loop parent deck has been
asked for this grid three times (#289, #296/#307, #303) and has produced
zero scored points; on the first run of the decomposed deck the grid completed
and surfaced a conversion defect at a sixth of the PVT box.

## Method

### Direct cross-check — five-loop vs one-loop over 250 ns

Issue #311 step 4 asks the two compositions to be compared on the
measurements they share. The full 8.5 µs window is unaffordable for the
five-loop deck (that is the whole premise of this issue), so both decks were
run over the longest window the five-loop deck can actually finish here.

Identical stimulus, identical window, identical solver settings
(`tt`/27 °C/3.30 V, `ngspice-46`, `SPARSE 1.3`, `num_threads=1`,
`tran 5n 250n 0 5n`), comparing the two duty-cycle integrals
`acq_window_ns`/`iso_gap_ns` are built from, plus pointwise node values and
first edge times on the `ok` loop's own nodes. The one-loop deck's netlist
is `sim/sar-logic-timing-gates-ok/testbench/tb_sar_logic_timing_gates_ok.spice`;
the five-loop deck's is the unmodified
`sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice`.

Both runs completed. `ok`-loop quantities, one-loop deck vs five-loop deck:

| quantity (on the `ok` loop's own nodes) | one-loop | five-loop | deviation |
|---|---|---|---|
| mean `v(ok_acq)`, 0–250 ns | 0.938550 | 0.938670 | +1.2e-4 (+0.013 %) |
| mean `v(ok_iso)`, 0–250 ns | 0.0555119 | 0.0554616 | -5.0e-5 (-0.091 %) |
| mean `v(ok_acq)`, 130–250 ns | 0.999595 | 0.999604 | +9e-6 (+0.0009 %) |
| `v(ok_code)` at 140 / 200 / 249 ns | 0 / 0 / 0 | 0 / 0 / 0 | exact |
| `v(ok_shp)` / `v(ok_shn)` at 200 ns | 1.63534 / 1.65000 | 1.63534 / 1.65000 | exact |
| `v(ok_sel_in_n)` at 140 / 170 / 230 ns | 3.30000 / 3.30000 / 3.30000 | 3.29999 / 3.30000 / 3.30000 | <= 1e-5 V |
| `v(ok_cmpo)` at 170 / 230 ns | 3.30001 / 3.30000 | 3.30000 / 3.30000 | <= 1e-5 V |
| `v(ok_samp_tp_n)` at 140 / 170 / 230 ns | 3.29804 / 3.29948 / 3.29962 | 3.29799 / 3.29956 / 3.29969 | <= 8e-5 V |
| `v(ok_samp_tp_n)` at 200 ns | 3.31668 | 3.29860 | 0.018 V (0.55 %) |
| first rise of `v(ok_samp_tp_n)` through 1.65 V | 8.52334 ns | 8.50813 ns | 15.2 ps (0.18 %) |
| first rise of `v(ok_sel_in_n)` through 1.65 V | 1.40865 ns | 1.37995 ns | 28.7 ps (2.0 %) |

**The two compositions agree.** The duty-cycle integrals that `acq_window_ns`
and `iso_gap_ns` are built from agree to 1.2e-4 and 5.0e-5 of a volt-mean over
the window — 0.013 % and 0.091 % — i.e. 30 ps and 13 ps when expressed in the
nanoseconds the measurements report. Logic-state nodes (`ok_code`, `ok_shp`,
`ok_shn`) are bit-exact. Edge times differ by 15–29 ps, which is the accepted
timepoint grid, not a behavioural difference: the five-loop deck is *forced*
into a different (finer, differently-placed) timestep sequence by the other
four loops' switching, so the two runs sample the same waveform at different
instants. The one outlier, `v(ok_samp_tp_n)` at 200 ns (0.55 %), is a
pointwise sample taken on a transitioning node for the same reason — its
neighbours at 140/170/230 ns agree to 8e-5 V.

Nothing here suggests the split changed the circuit's behaviour, which is what
finding 1's byte-identity argument already implies structurally; this is the
numerical confirmation of it.

**And it measures the cost directly.** The same 250 ns window, same host, same
settings: **4.85 core-s** one-loop against **977.40 core-s** five-loop — a
factor of **201**. That is a larger ratio than the ~100x #303 measured on a
different host over a shorter window, and it is consistent with the density of
accepted timepoints still rising through the window (#303's finding). It is
also why the full 8.5 µs comparison is not affordable: at this rate the
five-loop deck would need roughly 33000 core-s (9 core-hours) for one PVT
point, against the 71 core-s the one-loop deck actually took.

Raw scratch: `/tmp/i311-s4/xchk250-{one,five}.{spice,log}` on the running
host — not committed, but the two decks and the `.control` block above fully
determine them.

### Timestep refinement (rules out an under-resolved integral)

The `ok` deck's own first scored conversion window, run unmodified except for
the transient's maximum-timestep argument, on this host, `tt`/27 °C/3.30 V,
`ngspice-46`, `num_threads=1`:

```
tran 5n 1.5u 0 <tmax>
meas tran acq_av AVG v(ok_acq) FROM=0.5u TO=1.5u
meas tran iso_av AVG v(ok_iso) FROM=0.5u TO=1.5u
```

| `tmax` | `acq_window_ns` | `iso_gap_ns` |
|---|---|---|
| **5 ns** (the ratified value) | 186.221 | 64.000016 |
| 1 ns | 186.221 | 64.000011 |
| 0.25 ns | 186.2207 | 63.99247 |

A 20x refinement of the maximum timestep does not move `acq_window_ns` in six
significant figures, and moves `iso_gap_ns` by 0.0075 ns — 0.6 % of the
1.2 ns by which it exceeds its 62.8 ns upper bound, and in the *wrong*
direction to rescue it. (An earlier draft of this note said "the same values
to six significant figures" for both; that was true of `acq_window_ns` only,
and is corrected here. The claim was caught and fixed *before* any record
citing it was minted, because `records/` is append-only.)

The finer steps a five-loop composition forces are therefore not capable of
moving these two measurements meaningfully — which is the whole of the "does
splitting the deck change the answer?" question for them.

Raw logs for the refinement runs are scratch, not evidence: they are
reproducible from the committed deck with the three lines above.

### Cost

All figures `/usr/bin/time -v` user time (core-seconds), `--ngspice-threads 1
--save-measured-vectors`, `tt`/27 °C/3.30 V, one PVT point, on this host.

**This host is throttled**, by the same mechanism the #303 cost investigation
measured on its own host: a CPU-bound `ngspice` process gets a fraction of a
core (0.03–0.38 here, varying with how many are running) while the box
reports itself mostly idle, and **aggregate throughput rises with process
count**. Core-seconds, not wall-clock, are therefore the comparable figure,
and a grid is best run with a high `-j`.

| deck | one PVT point at `tt`/27 °C/3.30 V | status |
|---|---|---|
| `sar-logic-timing-gates-ok` | **71.0 core-s** | completed |
| `sar-logic-timing-gates-tie` | **233.7 core-s** | completed |
| `sar-logic-timing-gates-lt` | **> 801 core-s** | did not complete |
| `sar-logic-timing-gates-xl` | **> 800 core-s** | did not complete |
| `sar-logic-timing-gates-bad` | **> 801 core-s** | did not complete |
| `sar-logic-timing-gates` (five-loop parent) | ~9 core-h, extrapolated from the 250 ns cross-check above; >= 4 core-h independently in #303, on a different host | never completed |
| `sar-logic-timing` (rung-1 ideal, for scale) | 4.8 core-s | completed |

The three `>` figures are from one concurrent probe run (all three tags
launched together on an otherwise idle host, `--timeout 14400`), terminated
after 2809 s of wall time with none of the three having completed its single
point. Each was past **11x** the `ok` loop's completed cost and past **3.4x**
`tie`'s, still advancing in lockstep. They are lower bounds, not costs. What they do establish rigorously
is the ordering: **the three delay-line loops are more expensive than `tie`,
which is more expensive than `ok`** — the ideal lossless transmission line
(`cmp_delay`) those three insert ahead of the gate logic forces its own small
timestep.

**The whole-grid figure, which is the one issue #311 actually asked for**: the
45-point `mos` grid for `sar-logic-timing-gates-ok` completed in **7195.7
core-s (2.0 core-h) / 2 h 16 m wall** at `-j 14 --ngspice-threads 1
--save-measured-vectors`, i.e. **159.9 core-s per point** averaged across the
grid. That is above the 71.0 core-s a single uncontended point costs, because
14 concurrent ngspice processes on 8 cores contend; wall-clock per point fell
from ~78 s to ~182 s while total throughput more than quadrupled. Both numbers
are real; the per-point figure to budget with is the one that matches the `-j`
you intend to use.

Set against issue #311's own projection — "~660 core-s per PVT point, ~8
core-hours for the 45-point grid, for all five loops" — the honest scorecard
is: **right about `ok` (the grid it unblocked cost 2.0 core-h, not 180), wrong
as a figure for all five loops.** `ok` and `tie` together already cost ~305
core-s per point, and the three delay-line loops each exceed 800 core-s per
point on their own, so all five loops at 45 points is comfortably above 8
core-hours. The projection's arithmetic assumed every loop cost what `ok`
costs; only `ok` does.

Two things this table is careful *not* to say. It does not claim a completed
cost for `lt`, `xl` or `bad`: the attempts at those are lower bounds and are
labelled as such. And it does not claim a *measured* full-window five-loop
cost — no such run has ever finished. Its "~9 core-h" is an extrapolation
from this session's own completed 250 ns cross-check (977.40 core-s for
250 ns of the 8500 ns window), which is an **under**-estimate if #303's
finding that accepted-timepoint density keeps rising through the window
holds; the independent "≥ 4 core-h" figure beside it is #303's, measured on a
different host, and is quoted only for scale.

The practical consequence for whoever runs the remaining four grids: give the
delay-line tags a per-point `--timeout` in the hours, not the harness default
of 300 s. Every one of this session's `lt`/`xl`/`bad` probes that used the
default died on that timeout rather than on cost.

## Provenance

- Repo: branch `feature/issue-311`, at the commit that introduced the
  per-loop decks (`1d81aa1`) and its follow-on.
- Simulator: `ngspice-46` (compiled with KLU; the decks use the default
  `SPARSE 1.3`, per
  `20260918-issue-308-klu-solver-evaluation.md` in this directory, which
  measured KLU and did not adopt it).
- PDK: `gf180mcuD` at the `open_pdks` commit pinned in `sim/toolchain.json`,
  checked by the harness before any point is simulated.
- DUT: `design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`,
  translated to SPICE by `design/sar-logic/flow/gate_netlist_to_spice.py` —
  pre-layout, no extracted parasitics, no P&R (DR-0023 follow-ons (b)/(c)).

## What this note does NOT claim

- It does **not** claim the five-loop and one-loop decks were compared over
  the full ratified 8.5 µs window. They were compared over 250 ns (finding 2).
- It does **not** propose new values for `acq_window_ns` / `iso_gap_ns`.
  Setting a gate-level bound for those is a spec question with its own
  decision record, filed as issue #319.
- It does **not** report completed per-point costs for the `lt`, `xl` and
  `bad` decks. Those are lower bounds from terminated runs.
- It does **not** re-open issue #296's convergence root cause; every run
  behind these numbers carries the `cmp_out_rc` fix and none hit
  `Timestep too small`.
- It is **not** evidence about place-and-route, STA, real CDAC settling or
  real comparator behaviour — unchanged from the parent deck's own
  disclosures.
