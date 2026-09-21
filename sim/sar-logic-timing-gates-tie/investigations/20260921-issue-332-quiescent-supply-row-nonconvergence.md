# Investigation 20260921-issue-332: the `sf`/27 °C/2.97 V abort is a hard sign test on a differential at the floating-point ulp, landing on a quiescent supply row

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — a root-cause investigation of the
one genuine ngspice non-convergence in `sim/sar-logic-timing-gates-tie/`'s
ratified 45-point `mos` grid
(`records/20260920-020802-2043286.md`, issue #303):

```
sf_27c_2.97v: doAnalyses: TRAN:  Timestep too small; time = 3.99655e-07,
timestep = 6.25e-21: trouble with node "vvdd_gate#branch"
```

Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only `records/` tree is never edited. Nothing in the tree's decks,
manifests or bounds is changed by this document; the only code change it
carries is one print-precision flag on the probe (`--numdgt`), which writes
nothing and is what makes its central measurement checkable at all.

## Conclusion

**The abort is a hard sign test being taken on a quantity that has decayed to
the floating-point representation floor of the node voltage, at a moment when
the DUT's supply branch is quiescent.** Both halves are measured, and both are
needed — neither one alone aborts anything.

> Over the last 25 accepted timepoints before the abort the `tie` loop's
> comparator inputs differ by **0 to 1690 ulp of a 1.485 V node** — that is
> **0 … 3.8 × 10⁻¹³ V**, with two
> accepted timepoints at which the two nodes are **bit-identical**
> (Evidence 3). ngspice's node-voltage tolerance `vntol` is 1 × 10⁻⁶ V, so the
> differential is **six to ten orders of magnitude below the smallest voltage
> difference the solver claims to resolve**. The comparator's hard ternary is
> a function of the *sign* of that quantity, so the decision flips on the last
> bits of the LU solve, at every accepted timepoint, **for any timestep**.
>
> Each flip puts a **197.8 µA** excursion on `i(vvdd_gate)` — repeatable to
> 0.03 % across accepted timesteps spanning 7 × 10⁻¹⁶ … 2.8 × 10⁻¹⁵ s, i.e.
> **its amplitude does not shrink with `h`** (Evidence 4). At that instant the
> DUT is between clock edges and idle, drawing **4.8 nA**, so the excursion is
> **4.2 × 10⁴ times the row's own scale**. `vvdd_gate#branch`'s convergence
> test is `reltol·|I| + abstol`; a fixed-amplitude perturbation four orders of
> magnitude above `|I|` cannot be retired by halving `h`, which is why the run
> bottoms out at `timestep = 6.25e-21` rather than recovering.

**Is it corner-specific numerical sensitivity or a new structural issue? It is
neither of the two answers the issue offers, and the distinction matters:
the *mechanism* is structural and present at every corner of this deck by
construction; the *incidence* is a corner-dependent race the deck happens to
lose at exactly one of 45 points.**

The race is between the CDAC top-plate network settling to the exact-tie
equilibrium and the next clock edge re-exciting it. Measured on the aborting
run (Evidence 5): the differential falls from 20.8 mV at 377 ns through every
decade to the ulp floor by 399.5 ns — a ~0.7 ns decay constant — and the next
`clk` edge is not due until 406.25 ns. That leaves **6.6 ns of unbroken
"quiescent DUT + sub-representable differential"**, and the solver does not
survive it. At `sf`/27 °C/**3.30 V**, which *completes* with **2.2× more
chatter** (1068 reversals against 481), the longest such stretch in the same
window is **0.0018 ns**. The abort is not caused by more chatter; it is caused
by chatter that is never interrupted.

**No fix is landed here, and none of the available knobs is a fix rather than
a relaxation** — see "The answer to the issue's acceptance criteria". What
this document does establish is the finding DR-0029 named as its own
supersede trigger, with the measurement in hand.

## How to re-run everything below

Every row in every table is produced by one of these commands. `--cmp-rc`,
`--tie-offset`, `--spice-option` and `--numdgt` all write nothing: the
committed deck, its stimulus, its comparator and its bounds are untouched by
any of them.

```bash
# the abort itself, with the probe tables at the abort (~40 min on a busy host)
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --corner sf --temp 27 --vdd 2.97 \
    --until 410n --probe --chatter --tail 40 --keep /tmp/i332

# the measurement this investigation turns on: what the sign test is reading
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --corner sf --temp 27 --vdd 2.97 \
    --until 410n --probe --numdgt 17 --tail 25

# the corner neighbourhood (each completes)
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --corner sf --temp 27 --vdd 3.30 --until 410n --probe --chatter
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --corner sf --temp 125 --vdd 2.97 --until 410n --probe --chatter
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --corner tt --temp 27 --vdd 2.97 --until 410n --probe --chatter
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-ok  --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter

# the knob sweeps (measurement only -- nothing is written)
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates-tie \
    --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --cmp-rc 1k,1p
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates-tie \
    --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --cmp-rc 1k,10f
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates-tie \
    --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --cmp-rc 10k,10f
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates-tie \
    --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --tie-offset 100u
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates-tie \
    --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --tie-offset 1m
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates-tie \
    --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --spice-option reltol=1e-2
```

The per-timepoint tables quoted below are recomputed from a `--keep` log with
`probe_cmp_convergence._probe_tables`, the same parser `--chatter` uses, so a
reader re-derives them rather than trusting a transcription.

## Evidence 1 — the abort reproduces exactly, by three independent paths

| path | accepted timepoints | result |
|---|---:|---|
| `sim/run_corners.py` (the #303 grid run, `--save-measured-vectors`, `--ngspice-threads 1`) | `No. of Data Rows : 2446` | ABORT `t = 3.99655e-07`, `timestep = 6.25e-21`, node `vvdd_gate#branch` |
| `probe_cmp_convergence.py … --until 410n --probe --chatter` | **2446** | **ABORT `t = 3.99655e-07 s (timestep 6.25e-21)`, node `vvdd_gate#branch`** |
| `probe_cmp_convergence.py … --until 450n --probe --chatter` | **2446** | **identical** |
| `probe_cmp_convergence.py … --until 410n --probe --numdgt 17` | **2446** | **identical** |

Three things this settles before any mechanism is proposed.

- **It is the corner runner's abort, not the probe's.** The probe replaces the
  manifest's control block with its own and emits no `save` line, and
  `sim/sar-logic-timing-gates/investigations/20260917-issue-303-transient-cost-and-retention.md`
  measured this deck family's accepted-timestep sequence to be sensitive to
  retention. Here the two paths agree on the accepted-timepoint count to the
  unit and on the abort time to every printed digit.
- **It does not depend on where the run was told to stop.** 410 ns and 450 ns
  give the same 2446 timepoints and the same abort, so nothing about the
  truncation is doing the work.
- **Printing more digits does not perturb it.** The `--numdgt 17` run is
  byte-identical in outcome, which is what licenses Evidence 3 to read the
  wide-precision table as the *same* run as the default-precision one.

The deck is also the one the record was written from: `sha256` of
`sim/sar-logic-timing-gates-tie/testbench/tb_sar_logic_timing_gates_tie.spice`
is `cd57d203850b1c88529f20eedfab3c75358ec33405965470cfee1d2cacc9f69d`, which is
the "Testbench netlist sha256" line of
`records/20260920-020802-2043286.md`.

## Evidence 2 — what is true at the abort

Read from the `--keep` log's own last accepted timepoints (`--tail`, and the
per-timepoint table recomputed from the kept log).

| quantity | value at the abort | interpretation |
|---|---|---|
| `v(vdd_gate)` | 2.970 V exactly | supply healthy |
| `i(vvdd_gate)` between reversals | **4.8 – 14 nA** | **quiescent** |
| `i(vvdd_gate)` at a reversal timepoint | **−197.8 µA** | 4.2 × 10⁴ × the quiescent scale |
| `v(tie_cmpd)` | 2.970 V, flipping to 0.000 V and back | hard decision, always at a rail |
| `v(tie_cmpo)` | **2.96980 V** | **at the rail — not mid-rail** |
| `v(tie_topp) − v(tie_topn)` | **0 … 3.8 × 10⁻¹³ V (0 … 1690 ulp)** | below every solver tolerance |
| last `clk` edge before the abort | 375.0 ns | 24.7 ns earlier |
| next `clk` edge | 406.25 ns | **6.6 ns after the abort** |

**`v(tie_cmpo)` is at a rail, and that is the first thing to record**, because
the trouble-node name invites the opposite reading. #296's *rejected* soft
comparator parked this node mid-rail and reported a supply-branch abort; #310
had to refute the same hypothesis on the five-loop parent. Here the DUT-facing
node never leaves 2.9698 ± 0.0001 V through the entire terminal window: the
reversals are so short (0.7 – 2.8 fs) that the 100 ps `cmp_out_rc` network
moves `v(tie_cmpo)` by ~10 µV per flip. **The chatter never reaches the DUT's
logic. It reaches the solver.**

The `--chatter` figures for the run confirm this is not a mid-rail problem:
**8.416 ns of mid-rail dwell over 400 ns**, against **391.326 ns** for the
`--cmp-rc 1k,1p` run in Evidence 5 — which *completes*.

## Evidence 3 — the differential is at the floating-point ulp, not at a solver tolerance

This is the measurement the investigation turns on, and it is the one the
default probe tables cannot make: at `numdgt=10` the two comparator inputs
print **identically**, so the default readout can only say "below 10⁻¹⁰ V".
`--numdgt 17` (added by this issue) resolves it. `ulp(1.485) = 2.2204e-16 V`.

| index | t (ns) | `v(tie_topp) − v(tie_topn)` | ulps | `v(tie_cmpd)` | `i(vvdd_gate)` |
|---:|---:|---:|---:|---:|---:|
| 2427 | 399.654501643 | 3.997e-15 | 18 | 2.970 | 4.77e-09 |
| 2428 | 399.654504434 | 8.882e-16 | 4 | 2.970 | 4.76e-09 |
| 2429 | 399.654504521 | 6.661e-16 | 3 | 2.970 | 4.79e-09 |
| 2430 | 399.654504696 | 4.441e-16 | 2 | 2.970 | 4.79e-09 |
| 2431 | 399.654505045 | 6.661e-16 | 3 | 2.970 | 4.76e-09 |
| **2432** | **399.654505742** | **0.000e+00** | **0** | **0.000** | **−1.9783e-04** |
| 2433 | 399.654507138 | 1.110e-15 | 5 | 2.970 | 1.41e-08 |
| 2434 | 399.654509929 | 6.883e-15 | 31 | 2.970 | 1.47e-08 |
| 2440 | 399.654861582 | 3.753e-13 | 1690 | 2.970 | 1.24e-08 |
| 2445 | 399.655488837 | 2.220e-16 | **1** | 2.970 | 8.33e-09 |

Over the terminal window (t ≥ 399.486 ns, 97 accepted timepoints) the median
differential is **3.4 × 10⁻¹⁴ V** and **two timepoints are bit-identical**.

Set against the tolerances the deck actually runs at (neither manifest sets
`.options`, so these are ngspice's defaults):

| quantity | value | ratio to the measured differential |
|---|---:|---:|
| measured differential (median, terminal window) | 3.4e-14 V | 1 |
| `vntol` (node-voltage absolute tolerance) | 1e-6 V | **3 × 10⁷ ×** |
| `reltol · v(tie_topp)` | 1.5e-3 V | 4 × 10¹⁰ × |
| `ulp(1.485)` | 2.2e-16 V | 0.0065 × |

**This is the fact that decides the issue's central question.** DR-0029's
finding — reproduced and unchallenged here — is that the `tie` differential
sits "at ~1e-7 V, the solver's own noise floor", and DR-0029's rejection of
the sub-LSB-offset candidate rests on 1 µV *being* `vntol`. At this abort the
differential is **seven orders of magnitude smaller than that**: it is at the
representation limit of the IEEE-754 double holding the node voltage. No
tolerance is involved, because there is no tolerance left to tighten — the two
numbers being compared are adjacent representable values, and at index 2432
they are the *same* value. The sign the comparator reads is the rounding of
the last LU update, and it will keep changing for any timestep, forever.

## Evidence 4 — the reversal current is h-independent

The four decision reversals inside the terminal quiescent window, with the
accepted timestep that reached them:

| t (ns) | `dt` (s) | `i(vvdd_gate)` at the flip |
|---:|---:|---:|
| 399.646567 | 1.395e-15 | −1.977788e-04 |
| 399.652162 | 1.395e-15 | −1.977698e-04 |
| 399.653693 | 6.977e-16 | −1.978209e-04 |
| 399.654506 | 6.977e-16 | −1.978308e-04 |

**The timestep varies by 2×; the current varies by 0.03 %.** That is the whole
argument, and it is the same argument #296 made in voltage: a perturbation
whose amplitude is independent of `h` is not a local truncation error, and
halving `h` cannot retire it. The reversals also *accelerate* into the abort —
5.6 ns, then 1.5 ns, then 0.8 ns apart — and then the timestep collapses to
6.25e-21 with every printed node value static.

The amplitude is set by the comparator's output network rather than by the
solver: the same flip measured with `--cmp-rc` retuned (all at this corner)
gives **826 µA** at tau = 10 ps (`1k,10f`), **197.8 µA** at the committed
tau = 100 ps (`1k,100f`), and **78 µA** at tau = 100 ps with a 10× higher
drive impedance (`10k,10f`). So it is a real circuit quantity — the
displacement current the restarting `cmp_out_rc` edge drives into the DUT's
supply through its input cells — not solver junk. What makes it lethal is not
its size but that its size **does not depend on `h`** while the row it lands on
carries 4.8 nA.

> **Stated as inference, flagged as such.** "The `vvdd_gate#branch` row cannot
> satisfy `reltol·|I| + abstol` against a fixed-amplitude 198 µA perturbation
> on a 4.8 nA baseline" is a reading of ngspice's convergence arithmetic, not
> an instrumented per-iteration residual; the probe reads accepted timepoints,
> not Newton iterations, and cannot see inside a step. What *is* measured is
> everything that reading has to explain: the railed, quiescent, static state
> at the abort; the h-independent current amplitude; the differential at the
> ulp; and Evidence 6's demonstration that moving `reltol` alone — with no
> circuit change at all — decides whether the run survives.

## Evidence 5 — the lethal coincidence, and why one corner of 45

The differential does not sit at the ulp all run. It **decays into it** after
the bit trial's decision resolves, and the next clock edge pulls it back out.
From the aborting run's own table, `max |topp − topn|` per 1 ns bin:

| bin (ns) | 377 | 380 | 383 | 388 | 391 | 394 | 395 | 396 | 397 | 398 | 399 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| max &#124;diff&#124; (V) | 2.1e-2 | 5.8e-3 | 1.6e-3 | 4.8e-5 | 1.9e-5 | 5.1e-6 | 1.6e-6 | 1.1e-7 | 2.7e-8 | 9.3e-9 | **2.1e-9 → 0** |

Fourteen decades in 22 ns — the CDAC top-plate network relaxing to the exact-tie
equilibrium with a ~0.7 ns decay constant. On the way down it passes through
`vntol` (10⁻⁶ V) at ~395 ns, which is where DR-0029's chatter regime begins,
and keeps going to the ulp by 399.5 ns. **The next `clk` edge, which would
have re-excited it, is at 406.25 ns.**

So the deck has to survive an unbroken window of "DUT idle **and** differential
below any resolvable scale". Counting accepted timepoints that satisfy both
(`|topp − topn| < 1e-9 V` **and** `|i(vvdd_gate)| < 1 µA`) and taking the
longest contiguous stretch:

| run (all `sf`/27 °C/2.97 V unless noted) | timepoints | reversals | mid-rail dwell | longest "idle + sub-resolution" stretch | result |
|---|---:|---:|---:|---:|---|
| **committed `tie` deck** | **2446** | **481** | **8.416 ns** | **0.1693 ns** (399.486 → **399.655 ns**) | **ABORT** |
| `tie`, `sf`/27 °C/**3.30 V** | 5320 | **1068** | 6.947 ns | 0.0018 ns | completes |
| `tie`, `sf`/**125 °C**/2.97 V | 340 | 0 | 0.000 ns | 0.0000 ns | completes |
| `tie`, **`tt`**/27 °C/2.97 V | 499 | 46 | 9.066 ns | 0.0000 ns | completes |
| `sar-logic-timing-gates-ok` deck | 345 | 0 | 0.000 ns | 0.0000 ns | completes |
| `tie`, `--cmp-rc 1k,1p` (tau 1 ns) | 372 | 226 | **391.326 ns** | 0.0000 ns | completes |
| `tie`, `--cmp-rc 1k,10f` (tau 10 ps) | 6611 | 1434 | 6.551 ns | 0.4485 ns | completes |
| `tie`, `--cmp-rc 10k,10f` (tau 100 ps) | 2663 | 602 | 57.232 ns | 0.0000 ns | completes |
| `tie`, `--tie-offset 100u` (0.034 LSB) | 481 | 36 | 2.748 ns | 0.0000 ns | completes |
| `tie`, `--tie-offset 1m` (0.34 LSB) | 355 | 4 | 0.443 ns | 0.0000 ns | completes |

Four readings, in decreasing order of confidence.

- **Chatter severity does not predict the abort.** The `sf`/3.30 V run has
  **2.2× the reversals** of the aborting run and completes; `--cmp-rc 1k,1p`
  has **46× the mid-rail dwell** and completes. Any explanation of the form
  "this corner chatters more" is refuted on its own numbers.
- **The aborting run's "idle + sub-resolution" stretch ends *at the abort
  time*.** 399.486 → 399.655 ns, 92 accepted timepoints, terminating exactly
  where ngspice gives up. Nothing else in the run looks like that.
- **It is ~100× longer than the same quantity at the neighbouring supply
  point**, and the two `sf` corners that pass at other temperatures do not
  enter the state at all (`sf`/125 °C never brings the differential below
  10⁻⁹ V at any timepoint).
- **It is necessary-looking but not, on these ten rows, sufficient.** The
  `--cmp-rc 1k,10f` run has a **longer** such stretch (0.4485 ns at 187.6 ns)
  and completes. Reported rather than dropped: that row says the coincidence
  is a *hazard window*, not a deterministic trigger, and whether a given
  window is fatal also depends on the amplitude of the excursion relative to
  the row (that deck's quiescent current differs) and on where the step
  controller happens to be. A rule that predicted every row would need more
  than ten points, and this document does not claim one.

**Why one corner of 45, then.** The hazard window exists on every run of this
deck — it is created by the stimulus DR-0029 ratifies. Its *length* is set by
a race between the top-plate decay constant (a function of process, supply and
temperature) and the fixed 31.25 ns clock half-period, and its *lethality* is
set by how far the reversal amplitude sits above the idle supply current.
Those are corner-dependent, continuous quantities; convergence is a
discontinuous outcome. **Corner-specific incidence, structural mechanism** —
which is also why the 15 `ERROR — ngspice timed out` points elsewhere in the
same record cannot be assumed free of it.

## Evidence 6 — a tolerance change alone retires the abort

`--spice-option` appends `.options` to one run's deck and writes nothing. A
solver tolerance is not a spec bound and not a `tb.json` check, so sweeping one
is a measurement; `sim/tests/test_sar_ctrl_gates_tb.py::SharedSupplyRowTests::
test_no_manifest_papers_over_the_abort_with_a_solver_option` exists precisely
so this measurement cannot quietly become a fix, and it still passes.

| `.options` | timepoints | reversals | mid-rail dwell | result |
|---|---:|---:|---:|---|
| *(none — ngspice defaults)* | 2446 | 481 | 8.416 ns | **ABORT at 399.655 ns** |
| `reltol=1e-2` (10× looser) | 848 | 254 | 205.451 ns | **completes 410 ns** |

**Loosening `reltol` alone, with no circuit change whatsoever, clears the
abort.** This is the mirror image of #310's Evidence 5a, which *created* a
`vvdd_gate#branch` abort on a converging deck by tightening `reltol` to 1e-9.
Taken together the two results say the same thing from opposite directions:
an abort on this node is a statement about **conditioning against a
tolerance**, not about the circuit doing something.

**What this row is NOT.** It is not a proposal to set `reltol` anywhere in the
tree, and it is not a claim that `reltol=1e-2` would give trustworthy
measurements — at 1e-2 the same run reports 205 ns of mid-rail dwell against
the committed 8.4 ns, i.e. the accepted-timepoint grid is coarse enough to
change what the deck's own diagnostics say. The row is here to identify the
mechanism, and the 25× coarser dwell figure is itself the reason the knob is
not a fix.

## What is ruled out, and by what

| hypothesis | status | ruled out by |
|---|---|---|
| #310's five-DUT shared-supply-row conditioning | **ruled out** | this deck has exactly **one** `sar_ctrl_a` instance on `vvdd_gate`, asserted on the committed text by `test_sar_ctrl_gates_tb.py::SharedSupplyRowTests::test_each_per_loop_deck_puts_exactly_one_dut_on_its_own_supply_row` |
| #296's rejected soft comparator returning by another route | **ruled out** | `v(tie_cmpo)` is at a rail (2.96980 V) for the entire terminal window; the decision on `v(tie_cmpd)` is hard and always at a rail (Evidence 2) |
| #296's fix (`cmp_out_rc`) having regressed or being absent | **ruled out** | the network is present and working — it is what holds `v(tie_cmpo)` within 10 µV of the rail through 481 reversals; the `ok` deck at this same corner completes with 0 reversals |
| a static crowbar current on the supply | **ruled out** | between reversals the supply carries **4.8 – 14 nA**; the excursions are transient and coincident with a decision flip (Evidence 2, 4) |
| "this corner just chatters more" | **refuted** | `sf`/3.30 V has 2.2× the reversals and completes (Evidence 5) |
| DR-0029's chatter regime being the whole story | **incomplete** | DR-0029's regime is a ~10⁻⁷ V differential at `vntol`; this abort is at 10⁻¹⁶ – 10⁻¹³ V, seven orders further down, and is reached by a *decay* the DR does not describe (Evidence 3, 5) |
| a harness/retention artifact of the probe | **ruled out** | the corner runner and three probe invocations agree on 2446 timepoints and on the abort time to every digit (Evidence 1) |

## The answer to the issue's acceptance criteria

The issue asks for "either a fix … or a decision doc explaining why no fix is
warranted". **No fix is landed, and the reason is that every knob that would
move this abort is either a relaxation or a ratified decision that this
document is not the place to reopen.** Enumerated, so a reader can check that
the list is exhaustive rather than convenient:

| knob | effect measured here | why it is not landed |
|---|---|---|
| `tb.json` bounds (`tie_code_deviation`, `tie_conv_period_ns`) | — | Neither bound is implicated: the run never reaches a measurement. Moving them would not change convergence, only hide the ERROR. Forbidden by CLAUDE.md and by the issue. |
| the `tie` stimulus (`dc {vcm}` → `dc {vcm+δ}`) | 0.034 LSB and 0.34 LSB both complete (Evidence 5) | **DR-0029 §Decision item 1** pins the input as pinned *exactly* on the threshold, after measuring and rejecting this candidate. A 100 µV offset is 31× DR-0029's own tested 1 µV and still 0.034 LSB — it may well be the cheapest way out, and it is exactly the change DR-0029 says must come from a **superseding record**, not a testbench edit. |
| the comparator model (strobe it) | not measured | **DR-0029 §Alternatives candidate 1**, rejected there on cost to the `lt`/`xl`/`bad` loops and DR-0010's bisected `cmp_delay` boundary. Unchanged by anything measured here. |
| `CMP_OUT_RC` | `1k,1p`, `1k,10f`, `10k,10f` all complete at this corner (Evidence 5) | **DR-0029 §Consequences** pins it "from both directions"; #296 pins it from below. And the passing rows are not evidence of a fix — `1k,1p` costs 391 ns of mid-rail dwell (46× the committed), `1k,10f` has a *longer* hazard window than the aborting deck. One corner cannot license a change that re-dates four other decks' evidence. |
| solver `.options` in the manifest | `reltol=1e-2` completes (Evidence 6) | Asserted against by `SharedSupplyRowTests::test_no_manifest_papers_over_the_abort_with_a_solver_option`, and the same run's 25× coarser dwell figure shows why: it buys convergence by degrading the grid the deck's own claim is measured on. |

**What follows from that is a supersede trigger, not a shrug.** DR-0029's own
Consequences say:

> If #303's remaining coverage finds a corner where `tie_conv_period_ns` or
> `tie_code_deviation` actually fails *and* the chatter is implicated, this
> record is the one to supersede — with the measurement, not with a
> relaxation.

At `sf_27c_2.97v` **both** bounds are unmeasurable because the run aborts, and
the chatter is implicated as the proximate driver (Evidence 3, 4). Together
with its sibling #337 (`tie_code_deviation = 512` at 6 of 29 scored points in
the same record) the trigger is met twice over. **The measurement asked for is
this document.** The superseding record itself is deliberately *not* written
here: every candidate it would choose between changes what the `tie` loop
claims, DR-0029 is explicit that such a change belongs to a record with "its
own stated claim", and DR-0029 is itself still `proposed — requires operator
sign-off`. That is filed as **issue #345** — with the three candidates it must
choose between, and this document's measurements against each — rather than
decided by a Builder mid-investigation.

(Both DR-0029s are `proposed` and share a number; the collision is issue
**#335**, not this document's to fix. "DR-0029" throughout here means
`spec/decision-records/DR-0029-tie-loop-decision-chatter.md`.)

## What this investigation does NOT establish

- **It is not a scored PVT result.** `--until`/`--numdgt`/`--cmp-rc`/
  `--tie-offset`/`--spice-option` runs answer "does the solver survive", not
  "what does the deck measure". Only `sim/run_corners.py` writes evidence, and
  `records/20260920-020802-2043286.md` is unchanged and unedited.
- **It does not predict which corners abort.** Evidence 5's coincidence is
  necessary-looking on ten configurations and demonstrably not sufficient on
  one of them. No rule is claimed, and in particular nothing here says the 15
  timed-out points of the same grid are or are not carrying the same state.
- **It does not instrument ngspice's per-iteration residual.** The step from
  "a fixed-amplitude 198 µA perturbation on a 4.8 nA row" to "the convergence
  test on that row cannot be satisfied at any `h`" is an inference from
  ngspice's documented `reltol·|I| + abstol` test, flagged as such in
  Evidence 4. A reader who wants the residual itself needs an ngspice built
  with iteration-level instrumentation.
- **It does not reopen #296 or #310.** Every run carries #296's `cmp_out_rc`
  unmodified, and #310's mechanism is excluded by instance count, not by
  analogy.
- **It does not retire DR-0029.** It supplies the measurement DR-0029 names as
  its own supersede trigger; choosing the successor is a decision record's
  business.
- **It is one corner.** `sf`/27 °C/2.97 V is where the grid found it. The
  neighbourhood rows in Evidence 5 are four points, not a sweep.

## Environment

- PDK: `gf180mcuD` @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (the pin in `sim/toolchain.json`, and the one
  `records/20260920-020802-2043286.md` was taken at)
- ngspice: `ngspice-46`, compiled with the KLU direct linear solver — this deck
  still runs on SPARSE 1.3 (`option klu` is not set; see
  `sim/sar-logic-timing-gates/investigations/20260918-issue-308-klu-solver-evaluation.md`)
- Python: 3.14.7
- Deck: `sim/sar-logic-timing-gates-tie/testbench/tb_sar_logic_timing_gates_tie.spice`
  as committed (`sha256 cd57d203…c69d`), composed through `sim/harness`'s
  `compose_deck`, so the PVT preamble, corner sections and `sar_ctrl_a` subckt
  are the ones `sim/run_corners.py` uses
- Tree: `2422cac5d507e00b9f3847ee0b8df1440d1db973`
- Host: 18 cores, shared with other agents' concurrent ngspice workloads
  throughout (load average > 20 for the whole session). **No wall-clock figure
  appears anywhere above**; every quantitative claim is a voltage, a current,
  an accepted timestep, an accepted-timepoint count or a ulp.
