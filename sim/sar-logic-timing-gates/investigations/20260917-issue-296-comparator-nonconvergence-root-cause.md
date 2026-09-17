# Investigation 20260917-issue-296-comparator-nonconvergence-root-cause

Not a `sim/run_corners.py` evidence record (no PVT grid is claimed here) — a
manual root-cause investigation of the ngspice `Timestep too small`
non-convergence that issue #296 was filed to explain, following the
"probe before you fix" method the issue itself specified. Kept in
`investigations/`, alongside (not inside) `records/`, so the append-only
`records/20260915-210638-912a8ec.md` this investigation explains is never
edited.

Everything below is re-runnable from the tree:

```
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --ideal-cmp --probe                     # A side: the pre-fix comparator
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 200n                            # B side: the fix
```

## Conclusion

**The hypothesis in #296 is CONFIRMED in its essentials and SHARPENED in its
mechanism.** #296 proposed that the ideal, zero-time behavioural comparator
B-sources were the cause, and speculated that ngspice "keeps halving the step
trying to resolve a discontinuity that never actually settles", possibly
related to the deliberately near-metastable `tie` loop. The first half is
right. The second half is not quite the mechanism, and the difference matters
for choosing a fix:

> The step-size controller is not failing to *resolve* a fast edge. It is
> being asked to step over a discontinuity whose size does not depend on the
> step at all. `b<tag>cmp` is an **ideal voltage source whose value is a step
> function of the solution**, driving a real synthesized standard cell's gate
> input, which is a **pure capacitance**. The current it must source is
> `i = C·dV/dt` with `dV` pinned at `vdd_val` regardless of `h`, so halving
> `h` makes the demanded current *larger*, never the discontinuity smaller.
> That is why the logs bottom out at `timestep = 6.25e-21` instead of
> recovering: there is no `h` small enough, and the solver's only strategy is
> to try a smaller one.

The `tie` loop is where this bites first and most often, but **not** because
of metastability in the circuit sense — because `tie`'s input is pinned on
the decision threshold, so its comparator differential approaches zero with a
near-zero slope and therefore *sits on* the discontinuity rather than sweeping
briskly through it. It is the loop most likely to land a timestep boundary on
the crossing, not the only loop that can.

## Evidence 1 — the abort is exactly at a comparator crossing

`--ideal-cmp --probe` at `tt_27c_3.30v` prints the `tie` loop's comparator
inputs right up to the abort:

```
Index   time            v(tie_topp)     v(tie_topn)     v(tie_cmpo)
6       1.1000000000e-11  1.6500000787   1.6500000811    0.0
7       1.1500000000e-11  1.6500000852   1.6500000858    0.0
8       1.1625000000e-11  1.6500000868   1.6500000870    0.0
9       1.1656250000e-11  1.6500000872   1.6500000873    0.0
10      1.1657226562e-11  1.6500000873   1.6500000873    0.0
...
17      1.1659339905e-11  1.6500000873   1.6500000873    0.0
RESULT  : ABORT at t = 1.16593e-11 s (timestep 6.25e-21), trouble node btiecmp#branch
```

The two inputs converge on each other and become equal to ten printed digits;
the source's own driving expression `v(tie_topp) > v(tie_topn)` is therefore
sitting precisely on its switching boundary, with `v(tie_cmpo)` still at 0 V
at the last accepted timepoint. Meanwhile the *upstream* nodes are already
resolved the other way (`v(tie_topip) - v(tie_topin) = +9.4 uV` at the same
instant), so the crossing is real and imminent, not numerical noise: the RC
settling network is simply carrying `topp` up through `topn` with a slope
near zero. The `ok` loop at the same instant sits at
`v(ok_topp) - v(ok_topn) = +15.3 mV` and its comparator is a clean, stable
3.3 V — an undisturbed comparator is not the problem.

Note also that `v(vdd_gate) = 3.3000000000` throughout, so this is not #282
recurring; that fix is working exactly as its own record claims.

## Evidence 2 — the loops that never fail are the loops with a resistive load

This needs no new simulation; it is already in the 45 committed logs under
`corners/20260915-210638-912a8ec/`. Of the 45 points, 37 abort with a named
trouble node and 8 hit the runner's 300 s cap. The named node is:

| trouble node | count | what that source drives |
|---|---:|---|
| `btiecmp#branch` | 14 | the `tie` loop's comparator → DUT `cmp` gate input, **directly** |
| `bokcmp#branch` | 14 | the `ok` loop's comparator → DUT `cmp` gate input, **directly** |
| `vtiemode#branch` | 8 | `tie`'s `mode` DC source → DUT gate input (collateral) |
| `vltmode#branch` | 1 | `lt`'s `mode` DC source → DUT gate input (collateral) |
| `bltcmp` / `bxlcmp` / `bbadcmp` | **0** | comparator → **50 Ω-terminated T-line** |

The three delayed loops (`lt` 40 ns, `xl` 50 ns, `bad` 70 ns) run the *same*
ideal hard-ternary comparator expression as `ok` and `tie`. The only
difference is what it drives: `t<tag>d ... z0=50` with `r<tag>term ... 50`,
i.e. a matched resistive load, where the branch current is bounded at
`vdd_val / 50` no matter how the value steps. They never appear as the
trouble node, in any corner, at any temperature, at any supply. That contrast
is what turns "the comparator is discontinuous" from a plausible story into a
diagnosis: discontinuity alone is tolerated, discontinuity into a pure
capacitance is not.

(The two `mode` sources are collateral. They are ideal DC sources on gate
inputs in the same block; when the matrix is being driven by an unbounded
capacitive current, Newton's largest-residual node can land on any ideal
source's branch in the neighbourhood. No `mode` net is itself discontinuous.)

## Evidence 3 — the A/B, five process corners, nominal T and V

`--ideal-cmp` restores the committed testbench's comparator to its exact
pre-#296 form and changes nothing else. Every A-side abort below reproduces
the committed `corners/20260915-210638-912a8ec/*.log` value **digit for
digit**, which is also a check that the probe composes the same deck the
corner runner does:

| corner (27 C, 3.30 V) | A: pre-#296 comparator | matches committed log | B: with the fix, `--until 200n` |
|---|---|---|---|
| `tt` | ABORT @ 1.16593e-11 s, `btiecmp#branch` | yes | completes, 9562 timepoints |
| `ff` | ABORT @ 1.05372e-10 s, `vtiemode#branch` | yes | completes, 7989 timepoints |
| `ss` | ABORT @ 1.40722e-11 s, `bokcmp#branch` | yes | completes, 9459 timepoints |
| `fs` | ABORT @ 1.26095e-11 s, `btiecmp#branch` | yes | completes, 9754 timepoints |
| `sf` | ABORT @ 6.75249e-11 s, `btiecmp#branch` | yes | completes, 8331 timepoints |

Five for five on the process axis, and the A side aborts on three different
trouble nodes (`btiecmp`, `bokcmp`, `vtiemode`) — so the fix is not addressing
one corner's accident.

200 ns is not an arbitrary B-side horizon: **the latest abort anywhere in the
45-point grid is t = 1.566e-7 s** (`fs_125c_3.30v`), so a deck that reaches
200 ns has passed every point in simulated time at which any of the 45
baseline points died.

## What was tried and rejected

**A soft (high-gain / `tanh`) comparator band**, replacing the hard ternary
with a continuous transition of width ~10 uV. Measured, not argued: it moves
the `tt` abort from t = 11.66 ps to t = 112.6 ps — a 10,000x improvement, so
the diagnosis is right — and then aborts anyway, now with
`trouble with node "vvdd_gate#branch"`. The reason is visible in the model: a
soft comparator whose input is pinned on threshold parks its output
*statically* near mid-rail, which holds real `aoi21_1`/`nor2_1` inputs in
their linear region and turns a numerical problem into a physical one
(static crowbar current through the whole DUT, hence the supply branch as the
trouble node).

It would also have been wrong even if it had converged. The `tie` loop exists
to show that a near-metastable comparator input still produces a conversion
that *completes on schedule* — a claim that presupposes a comparator which
always resolves to a rail. Replacing the always-resolving decision with one
that can sit at mid-rail indefinitely changes what the loop is measuring
while appearing only to "help convergence". That is precisely the
mask-the-measurement failure #296's own acceptance criteria warn against.

## The fix

`gen_sar_logic._loop` gains `cmp_out_rc`, default `None` (so every rung-1
ideal deck stays byte-identical — `python3 design/sar-logic/gen_sar_logic.py
--check` passes untouched), and `gen_sar_ctrl_gates_tb.py` sets
`CMP_OUT_RC = ("1k", "100f")` for the two gate-level decks only:

```
b<tag>cmp <tag>_cmpd 0 V = v(<tag>_topp) > v(<tag>_topn) ? vdd_val : 0
r<tag>cmps <tag>_cmpd <tag>_cmpo 1k
c<tag>cmpl <tag>_cmpo 0 100f
```

The **decision is untouched**: same hard ternary, no hysteresis, no gain
band, always a rail. What changes is that its value lands on its own node and
reaches the DUT through a 100 ps first-order network, so the source's branch
current is bounded (`vdd_val / 1k = 3.3 mA`) and the DUT-facing node is
continuous in time. 100 ps is a ~220 ps 10–90 % edge — the same order as a
gf180mcu 5 V standard cell's own output transition, and 0.35 % of the 62.5 ns
bit cycle these decks measure margins in. The three delayed loops are left
exactly as they were, because they were never affected.

`sim/tests/test_sar_ctrl_gates_tb.py::ComparatorOutputSlewTests` asserts all
of this structurally, so a later edit that quietly reverts the network, or
quietly softens the decision, fails a test instead of failing a corner run
several hours in.

## What this investigation does NOT establish

- **It is not a scored PVT result.** `--until` runs answer "does the solver
  survive", not "what does the deck measure". Only `sim/run_corners.py`
  writes evidence. See `records/` for what has actually been scored.
- **The full 45-point grid is not re-run here.** With the fix this deck
  *converges*, and a converging point costs what a non-converging one never
  did: instrumented on `tt_27c_3.30v`, **9562 accepted timepoints per 200 ns**
  of simulated time (of which only 3085 fall in the first 125 ns; the
  post-seeding rate is ~86 timepoints/ns), i.e. of order 7e5 timepoints and
  ~10 CPU-hours for one ratified 8.5 us point — ~450 CPU-hours for the full
  grid. That is a pure-execution undertaking, tracked separately, exactly the
  split `#282 -> #289` already used for this deck family.
- **The cost is not caused by the fix.** Of the 9561 steps measured above,
  2509 are shorter than 1 ps, and their median distance to the nearest
  comparator output transition is 15 ns — they are the synthesized netlist's
  own switching, in five DUT instances sharing one clock, which
  `testbench/tb.json`'s own "COMPUTATIONAL COST, MEASURED" note already
  documents as up to two orders of magnitude slower per simulated nanosecond
  than a single loop in isolation.

## Environment

- PDK: gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
- ngspice: `ngspice-46 : Circuit level simulation program`
- Deck: `sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice`,
  regenerated by `design/sar-logic/flow/gen_sar_ctrl_gates_tb.py`
- Host was shared with other concurrent simulation workloads throughout, so
  wall-clock figures are not quoted anywhere above; every cost number is
  either a timepoint count or CPU time.
