# Investigation 20260917-issue-303-five-loop-composition-cost

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — a cost investigation of the
ratified `tran 5n 8.5u 0 5n` transient on `sim/sar-logic-timing-gates/`,
run on a **second, independent class of host** from the one
`20260917-issue-303-transient-cost-and-retention.md` measured. Kept in
`investigations/`, alongside (not inside) `records/`, so the append-only
`records/` tree is never edited.

**Why it exists**: issue #303 asks for the 45-point `mos` grid to be *run*.
Three sessions have now started that run and none has produced a scored
point. The previous two attributed that to the host (a 15.7 GB, 1.0-CPU
cgroup scope). This session had a materially different machine — an 18-core
Apple M5 Max with 48 GB of RAM — reached the same wall, and so went looking
for where the cost actually *lives* rather than re-reporting that it is too
big. It turns out not to be the host, and not to be anything #296 introduced.

## Summary of findings

1. **The deck's five-loop composition, not the host, is what makes a point
   unaffordable.** Holding DUT, corner, solver, thread count and retention
   fixed and varying *only how many of the deck's five loops are
   instantiated*, the cost per simulated nanosecond differs by
   **about two orders of magnitude**. The `ok` loop alone completes the
   whole ratified 8.5 µs transient in **131.9 core-s** (8.5 µs reached,
   no `Timestep too small`, all five of its `meas` lines resolved); the
   ratified five-loop deck spent **276.3 core-s to reach 160.0 ns**, i.e.
   **1.9 %** of the same run before it was stopped. Per simulated
   nanosecond that is 0.0155 against 1.73 core-s — **112x** on whole-run
   averages, **102x** over the comparable first ~160–220 ns.
2. **Nothing in the measurement definitions requires the five loops to share
   one deck.** They are electrically independent: each has its own
   `sar_ctrl_a` instance, its own behavioural CDAC/comparator and its own
   stimulus. The only nets they share are `clk` (a stimulus source) and the
   `.global vdd_gate` supply. The 8.5 µs *duration* is genuinely fixed by
   `tie_conv_period_ns`'s `RISE=2`..`RISE=7`; the co-simulation is not.
3. **This host is throttled too, by a different mechanism than the cgroup
   quota**, and the difference inverts one piece of existing harness
   guidance (see "Calibrating a host" below). A bare CPU-bound busy loop
   gets **0.089–0.110 of a core** here while `top` reports a steady **61 %
   idle**; `taskpolicy -B`, `taskpolicy -t 0 -l 0` and `nice` do not move it.
   Unlike a fixed quota, aggregate throughput here **rises** with process
   count (4 concurrent ngspice: ~0.17 core each; 16: ~0.13 each).
4. **#307's untested KLU lead, measured**: `option klu` costs **72.27 core-s**
   against SPARSE 1.3's **85.44 core-s** for the identical 100 ns truncation
   — **15 % cheaper**, real but not the missing order of magnitude.
5. **Consequence for #303 as written**: extrapolating the five-loop deck's
   measured average rate over its first 160 ns (1.73 core-s per simulated
   ns) across the ratified 8500 ns puts one point at **≥ 4 core-hours** and
   the 45-point grid at **≥ 180 core-hours**. Both are *lower* bounds: the
   marginal rate is still rising where the sample ends (2.8–3.8 core-s/ns
   over 134–160 ns), matching the earlier investigation's finding that
   accepted-timepoint density is still rising at 250 ns. Decomposed into one
   deck per loop, the same 45-point coverage projects to **5 × 131.9 ≈ 660
   core-s per point, ~8 core-hours for the whole grid** — a number this
   host could deliver in a day even at 0.1 core per process.

## Method and provenance

All raw artifacts are under `/tmp/i303/` on the session host (scratch, not
part of the tree — the figures are transcribed here because that directory
does not survive). Every run below is the harness-composed deck for
`sar-logic-timing-gates` at `tt`/27 °C/3.30 V, taken verbatim from
`sim/.work/sar-logic-timing-gates/20260917-232144-93a93ed/tt_27c_3.30v.spice`
(i.e. `python3 sim/run_corners.py sar-logic-timing-gates --corners tt --temps
27 --supply-tol 0 --ngspice-threads 1 --save-measured-vectors`), differing
only in the line noted. `user` time is the process's own CPU time as reported
by `/usr/bin/time -p`; wall time is inflated by the host throttle in finding
3 and is not a cost figure.

| id | deck difference | analysis | reached | core-s | wall s |
|---|---|---|---|---|---|
| `t25` | none | `tran 5n 25n 0 5n` | 25 ns (complete) | 26.4 | 231 |
| `sparse100` | none | `tran 5n 100n 0 5n` | 100 ns (complete) | 85.4 | 576 |
| `klu100` | `+ option klu` | `tran 5n 100n 0 5n` | 100 ns (complete) | 72.3 | 498 |
| `full5` | none | `tran 5n 8.5u 0 5n` (ratified) | 160.0 ns, stopped | 276.3 | — |
| `ok85u` | **`ok` loop only** | `tran 5n 8.5u 0 5n` (ratified) | 8.5 µs (complete) | 131.9 | 866 |

`ok85u`'s deck is the committed testbench with the `lt`, `xl`, `bad` and
`tie` loop blocks removed and nothing else changed — the file is literally
lines 1–115 and 355–653 of
`testbench/tb_sar_logic_timing_gates.spice` (the `* ---- loop <tag> ----`
blocks are contiguous), with the `.control` block's `meas` lines reduced to
the five that read `ok_*` nodes. Its `sar_ctrl_a` subckt, PVT preamble,
comparator model, `cmp_out_rc` slew fix, clock and `tran` line are the
committed ones, byte for byte.

### The five-loop deck's marginal cost, measured

From `full5`, sampling `(Reference value, process CPU time)` pairs as it ran:

| interval (simulated) | Δ core-s | core-s per simulated ns |
|---|---|---|
| 0 → 50.1 ns | 43.8 | 0.87 |
| 50.1 → 70.8 ns | 25.3 | 1.22 |
| 70.8 → 83.9 ns | 22.1 | 1.69 |
| 83.9 → 102.7 ns | 28.5 | 1.52 |
| 102.7 → 119.5 ns | 17.1 | 1.02 |
| 119.5 → 125.4 ns | 36.5 | 6.2 |
| 125.4 → 134.3 ns | 12.2 | 1.36 |
| 134.3 → 152.2 ns | 68.7 | 3.84 |
| 152.2 → 160.0 ns | 22.2 | 2.85 |

The per-interval figures are noisy — the sampling is `ps`-granular CPU time
against ngspice's own progress prints, on a throttled host — but the trend
across the window is not: ~0.9 core-s per simulated ns over the first 50 ns,
1.0–1.7 over 50–120 ns, and 1.4–6.2 over 120–160 ns. The whole-run average
to 160 ns is **1.73 core-s per simulated ns**, and 160 ns is **1.9 %** of the
ratified run. Multiplying that average by the ratified 8500 ns gives
**~14 700 core-s ≈ 4 core-hours per point** as a **lower** bound — lower,
because the rate is still climbing where the sample ends and the earlier
investigation measured accepted-timepoint density still rising at 250 ns.

### The one-loop A/B

`ok85u` is the same solver on the same DUT at the same corner over the same
8.5 µs, and it **completed** — 131.9 core-s, 866 s wall, no `Timestep too
small`, every `meas` line resolved. Per simulated nanosecond it costs
**0.0155 core-s** against the five-loop deck's 1.73 (whole-run averages), or
0.0169 against 1.73 restricted to the comparable first ~160–220 ns: a factor
of **102–112**. Five loops are 5x the circuit; the cost is ~100x. Put the
other way round: the five-loop deck spends more CPU reaching 160 ns than one
loop spends completing all 8.5 µs. The excess is timestep coupling,
not arithmetic: ngspice advances **one** global timestep for the whole deck,
so the step is forced by the union of five clock-sharing DUT instances'
switching, and every loop pays for every other loop's edges. This is the
mechanism behind the `tb.json` "COMPUTATIONAL COST, MEASURED" note's "up to
two orders of magnitude slower per simulated ns than a single loop run in
isolation", now measured on the *gate-level* deck rather than inferred from
the rung-1 sibling.

What `ok85u` measured while it was at it (**not a record, not citable** — a
hand-cut probe deck, one corner, no PVT grid, not run through
`sim/run_corners.py`, and by construction missing every `tie_*` measurement):

| manifest measurement | `ok85u` value | `tb.json` limits | inside? |
|---|---|---|---|
| `abs_err_delay_0ns` | 0 | max 0.5 | yes |
| `ok_conv_period_ns` | 1000.000 | 999.9 – 1000.1 | yes |
| `acq_window_ns` | 186.215 | **187.3 – 188.0** | **no** |
| `iso_gap_ns` | 64.004 | **62.2 – 62.8** | **no** |

Two of those land outside this manifest's bounds, and that is worth flagging
*before* someone finally affords the grid and reads it as a surprise: the
sibling `sim/sar-logic-functional-gates/`'s post-fix record
(`records/20260917-044312-c7ff0ff.md`) measures **186.182** and **64.026** at
the same `tt`/27 °C/3.30 V on the same synthesized DUT — agreeing with this
probe to ~0.03 ns, and also outside `sar-logic-timing-gates`'s tighter window.
That sibling's `tb.json` already carries the wider `185–190` / `60–65`
bounds; this deck's `187.3–188` / `62.2–62.8` are inherited from the *rung-1
ideal* timing deck, which has no PDK devices in its DUT at all.

Stated precisely, because it is a prediction and not a result: **nothing here
measures a violation** — a probe deck is not a record, `acq_window_ns` and
`iso_gap_ns` are ratified against the manifest's own five-loop deck, and only
a real `sim/run_corners.py` run can score them. But if and when this grid is
run, the likeliest outcome for those two measurements is a miss, and the
question it will raise is whether the rung-1 ideal deck's bounds are the right
ones for a gate-level netlist — a bounds question, already faced and answered
once on the sibling deck, and emphatically not a re-run of #296's convergence
question or of this document's cost question.

### Calibrating a host before sizing a grid

`sim/harness/README.md` says, from the cgroup host, that "under a fixed quota
`-j N` does not buy N-way throughput — it divides the same quota N ways". On
*this* host that is false: adding processes added aggregate throughput
(4 concurrent ngspice at ~0.17 core each → 16 at ~0.13 each, i.e. 0.7 → 2.1
cores of work), even though each individual process ran slower. The two
statements are not in conflict; they are two different throttle mechanisms,
and the guidance that generalizes is neither of them but the *calibration*:

```bash
# What fraction of a core does a CPU-bound process actually get here?
python3 - <<'PY'
import time, os
t0 = time.time(); c0 = os.times()
while time.time() - t0 < 10: pass
c1 = os.times()
print('cpu_frac %.3f' % ((c1.user - c0.user) / (time.time() - t0)))
PY
```

0.089–0.110 on this host, against `nproc` = 18 and 61 % idle. Neither
`nproc`, nor load average, nor `cpu.max` would have told you that. Do this
before deciding `-j`, and again with `-j` candidates running, because the
answer is a property of the host's scheduler policy, not of the deck.

## What this does and does not license

- It does **not** reopen #296. Nothing here contradicts the comparator-slew
  root cause or its fix; every run above includes the fix and none hit
  `Timestep too small`.
- It does **not** license changing the 8.5 µs duration, the `tran`
  parameters, any `tb.json` bound, or the comparator model. #303 rules those
  out and this investigation agrees with the ruling: the duration is pinned
  by the measurement definitions.
- It does **not** license treating the one-loop numbers as evidence for any
  spec claim. `ok85u` is a probe, not a record.
- It **does** say that the one structural assumption nobody has questioned —
  that all five loops must be solved in one deck — is where the cost is, and
  that it is not required by any measurement definition. Acting on that is a
  testbench-generator change with its own decision to make (five experiment
  slugs, or one manifest with a deck-variant axis?), which is why it is filed
  as its own issue rather than smuggled in here.

## Follow-on

- **Per-loop decomposition** — issue #311: the measured path from
  "45-point grid costs ≥ 180 core-hours and has never been run" to "45-point
  grid costs ~8 core-hours".
- **KLU**: worth ~15 % on this deck, measured above. Not worth a harness flag
  on its own; worth folding into any future harness work that touches deck
  composition.
- **The `acq_window_ns` / `iso_gap_ns` bounds question** flagged above is
  deliberately *not* filed as an issue: nothing has measured a violation, and
  filing against a prediction would put a bound under review before any
  evidence exists. It is written down here so whoever finally scores this
  grid recognises the result instead of re-deriving it under time pressure.
- **#303 itself** remains unexecuted: this deck still has **no** scored
  point, and its process, temperature and supply sensitivity is still
  **unmeasured**.
