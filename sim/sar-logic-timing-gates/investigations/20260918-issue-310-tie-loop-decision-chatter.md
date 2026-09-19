# Investigation 20260918-issue-310: the second convergence wall is a composition artifact, not a comparator defect

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — a root-cause investigation of the
**second** ngspice `Timestep too small` non-convergence on
`sim/sar-logic-timing-gates/`: the one issue #303 found past the 200 ns horizon
issue #296's own A/B validated, with `trouble with node "vvdd_gate#branch"`.
Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only `records/` tree is never edited.

Everything below is re-runnable from the tree, through the same instrument #296
used, with four flags this investigation adds to it:

```
# the full committed five-loop deck, to the abort -- the run every conclusion
# below is finally read on (~65k accepted timepoints, hours of core time)
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 400n --chatter --tail 40 --keep /tmp/i310-fulldeck

# per-loop A/B -- seconds to minutes each, against hours for the five-loop deck
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 400n --chatter --only-loops ok
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 400n --chatter --only-loops tie
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 400n --chatter --tail 45 --probe --only-loops ok,tie

# tau sweep -- does the mechanism depend on the #296 network's time constant?
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 400n --chatter --only-loops tie --cmp-rc 1k,1p

# solver-tolerance sweep -- is the abort a circuit event at all?
python3 design/sar-logic/flow/probe_cmp_convergence.py sar-logic-timing-gates \
    --until 400n --chatter --only-loops ok,tie --spice-option reltol=1e-9

# the committed per-loop deck, over its own unmodified 8.5 us window
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --timeout 86400
```

## Correction to issue #310's own premise: the abort is at 374.657 ns

Issue #310's body quotes the abort as `time = 3.84657e-07`. **Measured twice
here, it is `time = 3.74657e-07` — 374.657 ns, not 384.657 ns.** Both the
corner runner and the probe agree to every printed digit:

| path | result |
|---|---|
| `sim/run_corners.py sar-logic-timing-gates --corners tt --temps 27 --supply-tol 0 -j 1 --ngspice-threads 1 --save-measured-vectors --timeout 604800` | `[1/1] FAIL tt_27c_3.30v  doAnalyses: TRAN: Timestep too small; time = 3.74657e-07, timestep = 6.25e-21: trouble with node "vvdd_gate#branch"` (37515.9 s wall, 0/1 points ok) |
| `probe_cmp_convergence.py sar-logic-timing-gates --until 400n --probe` | `RESULT : ABORT at t = 3.74657e-07 s (timestep 6.25e-21), trouble node vvdd_gate#branch` |

That agreement is itself a result. `20260917-issue-303-transient-cost-and-retention.md`
measured this deck's accepted-timestep sequence to be sensitive to output
retention and to thread count, and the probe replaces the manifest's control
block with its own (no `save` line), so the two paths were only ever expected
to agree "to the solver's tolerance". At this point they agree exactly — so
**the ~hours-long probe run below is a faithful stand-in for the ~10 h corner
run**, and the conclusions do not rest on the cheaper path alone.

The 10 ns discrepancy against #310's body is not chased further: it is
plausibly a transcription slip in the original #303 report, and nothing below
depends on which of the two numbers is the historical one — the mechanism is
read from the deck's own state at *its* abort, measured here.

## Conclusion

**The chatter is real, it is the `tie` loop's alone, and it is NOT what
aborts the run.** Both halves of that sentence are measured, and the second
half is the part that matters, because it is the opposite of what the obvious
reading of the trouble-node name suggests.

> **What #310 hypothesised** — "some other loop's comparator output lingers
> mid-rail (through the RC network's own settling)", reproducing the static
> crowbar current that killed #296's *rejected* soft-comparator prototype on
> this same node name. **Half of that is confirmed and half is refuted.**
>
> *Confirmed (Evidence 1–3):* the `tie` loop's hard decision **chatters**.
> With `tie`'s input pinned on an exact tie, `v(tie_topp) - v(tie_topn)` is
> ~1e-7 V — the solver's own noise floor — for the whole of a bit trial's
> settling window, and the comparator's hard ternary is a function of the
> *sign* of that quantity, so from accepted timepoint to accepted timepoint
> the decision reverses. On the committed five-loop deck `v(tie_cmpd)`
> reverses **42 times** against **2** for every one of the other four loops,
> and each reversal restarts the 100 ps `cmp_out_rc` network, so
> `v(tie_cmpo)` — the net the DUT's `cmp` port binds — spends 1.52 ns parked
> in the linear region of real `aoi21_1`/`nor2_1` inputs. That is decision
> **chatter**, not a soft decision; the decision itself is the hard,
> always-resolves-to-a-rail ternary, unchanged.
>
> *Refuted (Evidence 4):* **at the abort, nothing is mid-rail and there is no
> crowbar current.** All five loops' comparator outputs are at a rail
> (`ok`/`lt`/`xl`/`bad` = 3.300 V, `tie` = 0.000 V). `i(vvdd_gate)` is
> **−98 nA** — five orders of magnitude below the 17.0 mA peak the same run
> draws, and below its own 0.32 µA median. Every comparator differential is
> static. The last time the supply carried even 1 µA was 13.1 ns earlier; the
> last time it carried 1 mA was 30.4 ns earlier. The last `tie` decision
> reversal was at t = 344.127 ns — **30.5 ns before the abort** — and the
> solver recovered fully from it, and from all 41 others, reaching
> dt = 3.6e-10 s as late as the last nanosecond before the abort.
>
> **The deck aborts while it is quiescent and idle.**

What is left, once the comparator is excluded by its own measured state, is
the node the abort actually names. `vvdd_gate#branch` is not a loop's node and
not a comparator's node: it is the **one row in the matrix that couples all
five otherwise-independent DUT instances** — the branch current of the single
voltage source feeding `.global vdd_gate`, i.e. the sum of the supply currents
of 5 × 181 = 905 standard cells. At the abort that sum is ~1e-7 A, and the
timestep collapses in a halve/double sawtooth (Evidence 4) with nothing in the
circuit moving — the signature of a residual that is **not** a discretization
error, which is why halving `h` never retires it and the run bottoms out at
6.25e-21 s.

Against #310's own three candidate explanations:

- **(a) a property of the RC-network fix itself under long-run conditions** —
  **no.** The tau dependence is real for the *chatter* (Evidence 3: at
  tau = 1 ns the mid-rail dwell is 74.8 ns against 2.5 ns at the committed
  100 ps), but at the abort `v(tie_cmpo)` is at 0.000 V and has been for
  30 ns. The network is not implicated in the abort in any measured way.
- **(b) specific to the `tie` loop's near-metastable-input scenario
  compounding over many cycles** — **for the chatter, yes; for the abort,
  no.** Evidence 2 isolates the chatter to `tie` on the committed deck
  (42 reversals against 2, 2, 2, 2). And "compounding over many cycles" is
  the right instinct for a reason worth recording: an exact tie at mid-scale
  leaves an exactly-zero residue, so **every** subsequent bit trial of that
  conversion is also an exact tie, not just the free-MSB one — which is why
  the reversals arrive in bursts on a ~31.2 ns cadence (Evidence 2). But the
  solver survives every burst.
- **(c) something else entirely** — **this one, and it is a composition
  artifact.** The abort requires the five-loop composition. Measured
  (Evidence 5): every cut of the same deck with one or two loops completes
  400 ns; the committed `tie` per-loop deck runs the full ratified 8.5 µs; and
  the same abort — same node, zero chatter, zero mid-rail dwell — is reachable
  on a two-loop deck by tightening `reltol` alone, with no circuit change at
  all. Only the five-loop parent aborts on its own.

### The answer to acceptance criterion 3

#310 asks for "either a fix (with the same 'decision untouched, only
propagation changed' discipline #296 used) or a documented decision that the
`tie` loop's own design cannot reach 8.5 µs on this deck without further
redesign".

**Neither, because the premise no longer holds: the `tie` loop DOES reach
8.5 µs, measured, and the fix already landed from a different direction.**
Issue #311 / PR #321 decomposed this deck into five single-loop decks
(`sim/sar-logic-timing-gates-{ok,lt,xl,bad,tie}/`) for cost reasons, before
this investigation existed. That decomposition **removes the shared
`vvdd_gate` row by construction** — each per-loop deck has exactly one DUT
instance on its own supply source — and with it the abort. Measured here
(Evidence 5b): `sim/sar-logic-timing-gates-tie`, carrying the *same*
chattering comparator, the same `cmp_out_rc` and the same pinned-on-threshold
stimulus, **runs its whole unmodified `tran 5n 8.5u 0 5n` to completion** in
9216 accepted timepoints, against the five-loop parent's 65319 timepoints spent
failing to get past 374.657 ns. So:

- **Nothing here needs relaxing, and nothing was relaxed.** `cmp_out_rc`'s
  time constant, the comparator's hard ternary, the `tie` loop's stimulus, and
  every `tb.json` bound are **unchanged in the tree**. `--cmp-rc` and
  `--spice-option` exist so that the tau and tolerance questions could be
  *measured* rather than argued, and neither writes anything.
- **The five-loop parent deck is the thing that cannot converge**, and it is
  already superseded for exactly this reason plus the ~201x composition cost
  penalty `20260918-issue-311-per-loop-equivalence-and-inherited-ideal-bounds.md`
  measured. It is kept unmodified in the tree as the historical deck its #289
  record belongs to.
- **The chatter remains a real, unretired finding about the `tie` loop** — it
  is not a defect in the DUT (the decision is hard and the conversion still
  completes), but it is a cost driver and it *is* a state in which real
  standard-cell inputs sit in their high-gain linear region for nanoseconds at
  a time. It is filed as **issue #322** rather than smuggled in here,
  because every candidate response to it changes what the `tie` loop *claims*
  and that is a `spec/` decision record's business (see "The candidate
  redesigns" below).

## Evidence 1 — at the same instant, `ok` decides and `tie` chatters

Both undelayed loops, same deck (`--only-loops ok,tie`), same corner, same
timepoints. Columns are `v(<tag>_cmpd)` (the hard decision, on its own node)
and `v(<tag>_cmpo)` (the node the DUT's `cmp` port actually binds). Re-run
with `--probe --tail 45`:

| t (s) | `ok` diff | `ok_cmpd` | `ok_cmpo` | `tie` diff | `tie_cmpd` | `tie_cmpo` |
|---|---:|---:|---:|---:|---:|---:|
| 3.7515088e-07 | +198.16 µV | 3.300 | 3.300 | **+0.001 µV** | 3.300 | 1.069 |
| 3.7517352e-07 | +198.05 µV | 3.300 | 3.300 | **−0.130 µV** | **0.000** | 1.167 |
| 3.7521801e-07 | +197.92 µV | 3.300 | 3.300 | −0.367 µV | 0.000 | 0.798 |
| 3.7529787e-07 | +198.57 µV | 3.300 | 3.300 | −0.001 µV | 0.000 | 0.397 |
| 3.7534999e-07 | +198.82 µV | 3.300 | 3.300 | **+0.028 µV** | **3.300** | 0.859 |
| 3.7539716e-07 | +198.84 µV | 3.300 | 3.300 | **−0.060 µV** | **0.000** | 1.121 |
| 3.7547233e-07 | +198.98 µV | 3.300 | 3.300 | −0.205 µV | 0.000 | 0.586 |
| 3.7558360e-07 | +199.82 µV | 3.300 | 3.300 | −0.085 µV | 0.000 | 0.218 |
| 3.7565444e-07 | +202.06 µV | 3.300 | 3.300 | **+1.794 µV** | **3.300** | 0.891 |
| 3.7572245e-07 | +205.60 µV | 3.300 | 3.300 | +5.378 µV | 3.300 | 1.957 |
| 3.7586087e-07 | +184.54 µV | 3.300 | 3.302 | **−14.103 µV** | **0.000** | 2.013 |
| 3.7605983e-07 | +192.62 µV | 3.300 | 3.300 | −9.267 µV | 0.000 | 0.361 |
| 3.7649491e-07 | +558.79 µV | 3.300 | 3.300 | −5.191 µV | 0.000 | 0.008 |
| 3.7660737e-07 | +889.75 µV | 3.300 | 3.300 | **+99.178 µV** | **3.300** | 1.076 |
| 3.7682784e-07 | +5.416 mV | 3.300 | 3.300 | +4.030 mV | 3.300 | 2.978 |
| 3.7731612e-07 | +23.440 mV | 3.300 | 3.300 | +20.244 mV | 3.300 | 3.299 |

`ok` and `tie` run the *identical* comparator expression and the *identical*
`cmp_out_rc` network. The only difference is the stimulus: `ok`'s input ramps
one LSB per conversion, so its differential during this settling window is
~199 µV — three orders of magnitude above the solver's own noise — and its
decision never moves. `tie`'s input is pinned on the threshold, so its
differential is **tenths of a microvolt**, its sign is not a physical fact at
that resolution, and the decision reverses **five times inside 0.69 ns**
(375.173, 375.350, 375.397, 375.654, 375.861 ns) with a sixth at 376.607 ns.
Over that whole window `v(tie_cmpo)` is between 0.008 V and 2.42 V — never at a
rail, and for most of it inside the switching band of the gf180mcu 5 V cells it
drives. It only resolves once the real differential grows past the noise
(+4.0 mV at 376.8 ns), after which `tie_cmpo` reaches 3.299 V and stays.

## Evidence 2 — the reversals are `tie`'s alone, measured on the committed deck

Computed by `--chatter`, so a reader re-derives these rather than trusting
transcribed rows. A "reversal" is an accepted-timepoint-to-accepted-timepoint
sign change of `v(<tag>_cmpd)` about mid-rail; "mid-rail dwell" is the total
time `v(<tag>_cmpo)` spends in 0.8–2.5 V (the switching band the
`gf180mcu_fd_sc_mcu7t5v0` `aoi21_1`/`nor2_1` inputs present at a 3.30 V rail),
trapezoid-summed over accepted timepoints. Counts are over the **whole run**,
independent of `--tail`.

**The committed five-loop deck**, `tt`/27 °C/3.30 V, `tran 5n 400n 0 5n`,
committed `cmp_out_rc` (`1k`/`100f`, tau = 100 ps), all five loops, 65319
accepted timepoints to the abort at 374.657 ns:

| loop | reversals (0–374.657 ns) | mid-rail dwell | comparator drives |
|---|---:|---:|---|
| `ok` | 2 | 0.784 ns | DUT gate input via `cmp_out_rc` |
| `lt` | 2 | 0.388 ns | 50 Ω terminated T-line (`cmp_delay`) |
| `xl` | 2 | 0.419 ns | 50 Ω terminated T-line |
| `bad` | 2 | 0.417 ns | 50 Ω terminated T-line |
| **`tie`** | **42** | **1.522 ns** | DUT gate input via `cmp_out_rc` |

Shared supply over the same run: peak `|i(vvdd_gate)|` = 17.049 mA,
median = 0.32 µA.

That is the loop isolation #310 asked for, and it is unambiguous: one loop
reverses 21x as often as any other, and it is the one whose input is pinned on
the decision threshold. The other four all reverse exactly twice, both inside
the first 20 ns — during the `START_PULSE_CLOCKS` seeding window, before the
`ph` ring's one-hot invariant is established.

The 42 reversals are not uniformly spread. They arrive in bursts on the
conversion cadence — 0.01–1.18 ns (seeding), then 94.07, 156.55, 219.03,
250.11, 281.53, 312.61, 344.02 ns — i.e. one burst per ~31.2 ns after seeding,
which is the bit-trial period. This is the measured form of #310's
"compounding over many cycles": an exact tie at mid-scale leaves an
exactly-zero residue, so every subsequent bit trial of that conversion is also
an exact tie.

**And the last burst ends 30.5 ns before the abort** (last reversal
t = 344.127 ns, abort t = 374.657 ns). That is the fact that removes chatter
from the list of candidate abort mechanisms — see Evidence 4.

**The `--only-loops` cuts**, same corner, same window, same RC:

| deck | accepted timepoints | loop | reversals | mid-rail dwell | reaches 400 ns? |
|---|---:|---|---:|---:|---|
| `--only-loops ok` | 354 | `ok` | 2 | 0.204 ns | **yes** |
| `--only-loops tie` | 477 | `tie` | 32 | 2.523 ns | **yes** |
| `--only-loops ok,tie` | 482 | `ok` | 2 | 0.784 ns | **yes** |
| | | `tie` | 30 | 2.373 ns | |
| *committed, all five* | 65319 | `tie` | 42 | 1.522 ns | **no — aborts at 374.657 ns** |

> **Read the subset rows as a mechanism probe, not as equivalent circuits.**
> `--only-loops` deliberately removes the dropped loops' load on `vdd_gate`
> and `clk`; the flag prints that caveat on every run. For a **single** tag the
> cut is stronger than a proxy — its circuit lines are byte-for-byte the
> committed `sim/sar-logic-timing-gates-<tag>/` deck #311 landed, pinned by
> `sim/tests/test_probe_cmp_convergence.py::PerLoopExperimentTests` — but the
> two-loop row is a deck that exists nowhere else.

Two things this table settles. **The chatter is not created by composition**:
`tie` reverses 32 times alone and 42 times with four other loops, so
composition makes it somewhat worse (more loops ⇒ finer global timestep ⇒ more
samples of a sign that is noise) but does not cause it. **The abort is created
by composition**: the same `tie` loop, chattering, completes 400 ns alone and
completes it with `ok` added, and only the five-loop deck aborts.

### What the supply branch does, and what it does NOT prove

`vvdd_gate#branch` is the trouble node #310 names, so the obvious move is to
point at a current spike there and call it crowbar. **That does not survive
measurement, and it is worth recording why**, because it is the trap this deck
sets for the next reader. Peak `|i(vvdd_gate)|` over the same 400 ns window:

| deck | peak `\|i(vvdd_gate)\|` | median `\|i(vvdd_gate)\|` | is any `cmpo` mid-rail at the peak? |
|---|---:|---:|---|
| `--only-loops ok` | **3.141 mA** | 237.04 µA | **no** — `ok_cmpo` = 3.300 V throughout |
| `--only-loops tie` | 3.324 mA | 224.24 µA | yes |
| `--only-loops ok,tie` | 6.647 mA | 428.75 µA | yes |
| *committed, all five* | 17.049 mA | 0.32 µA | yes, in bursts |

The `ok`-only deck — which never chatters after seeding and whose comparator
output sits at a rail for the entire window — draws a peak supply current of
the same order as the `tie`-only deck that does chatter. That current is
ordinary standard-cell switching in a 181-cell instance, and it swamps any
crowbar term. **So supply-current magnitude does not isolate this mechanism
and is not used as evidence for it here.** What the supply branch tells you is
only *where* the solver's largest residual lands: it is the node every cell in
every DUT instance binds, so it is where an ill-conditioned row shows up — the
same reason #296's rejected soft comparator reported it, arrived at by a
completely different route.

## Evidence 3 — the mid-rail dwell scales with the output network's time constant

`--cmp-rc` retunes the #296 network for one run only and writes nothing.
`--only-loops tie`, same corner, same 400 ns:

| `cmp_out_rc` | tau | accepted timepoints | reaches 400 ns? | reversals | mid-rail dwell |
|---|---:|---:|---|---:|---:|
| `1k,1p` | 1 ns | 401 | yes | **84** | **74.829 ns** |
| `1k,100f` *(committed)* | 100 ps | 477 | yes | 32 | 2.523 ns |

At tau = 1 ns the decision reverses faster than the network can slew, and
`v(tie_cmpo)` spends **30x longer** in the standard cells' linear region —
the rejected soft comparator's static mid-rail parking, reproduced with the
hard ternary still in place and untouched.

This is the measurement #310 required *before* anyone touches `cmp_out_rc`,
and it cuts against relaxing it: **making tau larger makes the chatter's
consequence much worse**, and making tau smaller walks back toward #296's own
`b<tag>cmp#branch` abort (where tau = 0 exactly). The committed 100 ps is not
obviously improvable in either direction.

Note what this row does **not** show, and what the draft of this document
wrongly concluded before the full-deck run was read: **neither tau completes
or fails differently at the abort, because neither `tie`-only deck aborts at
all.** Both complete 400 ns. The tau axis moves the chatter's severity; it
does not move the abort, because the abort is not the chatter.

## Evidence 4 — what is actually true at the abort

This is the section the whole investigation turns on, and it is the one the
draft of this document was missing. Read from the committed five-loop deck's
own probe log at its own abort (`--keep`, 65319 accepted timepoints, all five
loops' `cmpd`/`cmpo` and the shared supply).

**State at the abort, t = 3.74657e-07 s:**

| quantity | value at the abort | interpretation |
|---|---|---|
| `v(ok_cmpo)` | 3.300 V | at a rail |
| `v(lt_cmpo)` | 3.300 V | at a rail |
| `v(xl_cmpo)` | 3.300 V | at a rail |
| `v(bad_cmpo)` | 3.300 V | at a rail |
| `v(tie_cmpo)` | **0.000 V** | at a rail |
| `v(tie_cmpd)` | 0.000 V | decision resolved, and static |
| `v(tie_topp) − v(tie_topn)` | **−0.104 µV, constant to 3 digits for the last 2.3 ns** | not moving |
| `v(ok_topp) − v(ok_topn)` | +195.86 µV, creeping monotonically at ~3 µV/ns | not switching |
| `v(vdd_gate)` | 3.300 V exactly | supply healthy |
| `i(vvdd_gate)` | **−98 nA** | **quiescent** |

**Nothing is mid-rail. There is no crowbar current. Nothing is switching.**
The DUT has finished a conversion and is idle, and the solver aborts anyway.

**How long the circuit had been idle:**

| last accepted timepoint at which… | t | before the abort |
|---|---:|---:|
| `\|i(vvdd_gate)\| ≥ 1 mA` (real switching) | 344.233 ns | **30.4 ns** |
| `\|i(vvdd_gate)\| ≥ 1 µA` | 361.527 ns | **13.1 ns** |
| `v(tie_cmpd)` last reversed (last chatter) | 344.127 ns | **30.5 ns** |

**And the solver recovered completely in between.** Maximum accepted timestep
per 1 ns bin over the last 30 ns never falls below 2.8e-11 s, and in the very
last bin before the abort — `[373.657, 374.657)` ns — it still reaches
**3.617e-10 s**. A solver that has been damaged by a chatter episode does not
take 361 ps steps 30 ns later. Selected bins:

| bin (ns) | accepted points | max dt | min dt |
|---|---:|---:|---:|
| [344.657, 345.657) | 552 | 1.609e-10 | 4.0e-16 |
| [353.657, 354.657) | 83 | 3.649e-10 | 4.0e-17 |
| [361.657, 362.657) | 594 | 9.221e-11 | 1.9e-15 |
| [371.657, 372.657) | 51 | 2.748e-10 | 1.2e-13 |
| **[373.657, 374.657)** | **665** | **3.617e-10** | **1.0e-17** |

**The terminal collapse, and why no timestep can retire it.** The last 40
accepted timepoints (`--tail 40`) show the classic halve/double sawtooth, each
cycle restarting from a smaller base, with every printed node value identical
across the whole window:

```
dt: 1.2095e-12  1.2095e-12  6.898e-14  1.3795e-13  2.4142e-13  2.4142e-13
    4.829e-14   9.657e-14   1.9313e-13 2.0013e-13  2.0013e-13  1.8770e-14
    3.754e-14   6.570e-14   6.569e-14  1.3140e-14  2.6280e-14  5.2560e-14
    1.0511e-13  2.1023e-13  2.4143e-13 2.4142e-13  2.5000e-16  4.900e-16
    8.500e-16   8.600e-16   1.7000e-16 3.5000e-16  6.800e-16   1.0700e-15
    1.0800e-15  1.0000e-17  2.0000e-17 5.0000e-17  4.0000e-17  → 6.25e-21
```

That pattern — accept, double, double, reject, halve from a lower base, with
the solution *not changing* — is the signature of a residual that is not a
discretization error. A local truncation error shrinks with `h`; a
rounding-noise residual on a matrix row does not. Which is why the run bottoms
out at `timestep = 6.25e-21` rather than recovering, exactly as #296's own
investigation observed for a different reason (there, a step discontinuity of
fixed height `vdd_val` independent of `h`).

**What row is it, and why five loops and not one.** `vvdd_gate#branch` is the
branch current of the single voltage source feeding `.global vdd_gate`. It is
the only quantity in the deck that sums contributions from *all five* DUT
instances: 5 × 181 = 905 standard cells (asserted on the committed text by
`sim/tests/test_sar_ctrl_gates_tb.py::SharedSupplyRowTests`). In the quiescent
state that sum is ~1e-7 A of near-cancelling leakage terms, and ngspice's
convergence test on a branch current is `reltol·|I| + abstol` =
1e-3 × 1e-7 + 1e-12 ≈ 1.01e-10 A at the defaults this deck runs (neither
manifest sets `.options`). **Four fifths of the terms in that sum belong to
loops that are not coupled to the one you are looking at** — the five loops
share only `clk` and this supply — which is what makes an abort here a
*composition* property rather than a circuit one.

> **Stated as inference, flagged as such.** The step from "the row is
> ill-conditioned against its tolerance" to "because a ~900-term sum of
> independently-evaluated nonlinear device currents is not reproducible to
> 0.1 nA between Newton iterations" is a **plausible mechanism, not a
> measurement**: nothing here instruments ngspice's per-iteration residual, and
> the probe cannot (it reads accepted timepoints, not iterations). What *is*
> measured is everything the inference has to explain — the quiescent, railed,
> static state at the abort; the non-LTE sawtooth; the dependence on loop
> count; and the fact that a tolerance change alone reproduces the same abort
> on the same node with no circuit change (Evidence 5a). A reader who wants the
> residual itself will need an ngspice built with iteration-level
> instrumentation, which is out of scope here.

Evidence 5 tests the reading by moving the tolerance and by removing the row.

## Evidence 5 — the abort is a solver-conditioning failure, and decomposition retires it

### 5a. A tolerance change alone reaches the same abort, with zero chatter

`--spice-option` appends `.options` to one run's deck and writes nothing. A
solver tolerance is not a spec bound and not a `tb.json` check, so sweeping one
is a measurement rather than a relaxation. All rows are the **two-loop cut**
(`--only-loops ok,tie`), which completes 400 ns unmodified — chosen because it
is the cheapest deck that carries both undelayed comparators, so a tolerance
sweep on it costs minutes rather than the parent's hours:

| `.options` | accepted timepoints | `tie` reversals | `tie` mid-rail dwell | result |
|---|---:|---:|---:|---|
| *(none — ngspice defaults)* | 482 | 30 | 2.373 ns | completes 400 ns |
| `abstol=1e-15` | 482 | 30 | 2.373 ns | completes 400 ns |
| `abstol=1e-18` | 482 | 30 | 2.373 ns | completes 400 ns |
| **`reltol=1e-9`** | **68** | **0** | **0.000 ns** | **ABORT at t = 1.15899e-11 s, trouble node `vvdd_gate#branch`** |

Two results, and the second is the one that closes the argument.

**The `abstol` rows are a deliberate null result, reported rather than
dropped.** Tightening `abstol` by three and six orders of magnitude changes
*nothing* — not the timepoint count, not the reversal count, not the dwell, not
the supply figures (peak 6.647 mA / median 428.75 µA in all three). That is
consistent with the arithmetic and is why it is worth recording: ngspice's
convergence test on a branch current is `reltol·|I| + abstol`, and at the
0.4 mA median current this deck carries, `reltol·|I|` = 1e-3 × 4e-4 = 4e-7 A
dominates `abstol` = 1e-12 A by five orders of magnitude. `abstol` is simply
not the binding term here, so moving it cannot be expected to do anything. A
first pass at this section reached for `abstol` because #310's abort happens at
a ~1e-7 A current; the measurement said the knob was the wrong one.

**The `reltol` row is the positive confirmation.** The identical deck, with the
identical circuit, aborts **on the identical node** — `vvdd_gate#branch` — when
only `reltol` is tightened. And it does so with:

- **zero decision reversals** — the comparator's decision never moves at all,
  so there is no chatter of any kind;
- **zero mid-rail dwell** — `v(tie_cmpo)` never enters the cells' switching
  band;
- at **t = 11.59 ps**, before the DUT has done anything (compare #296's own
  pre-fix abort at t = 11.66 ps — both are "the first hard step the solver must
  take").

**So a `vvdd_gate#branch` abort is reachable with no circuit change, no
comparator involvement, no crowbar current and no chatter whatsoever.** The
node name carries no information about a comparator mechanism: it identifies
the deck's worst-conditioned row — the one every cell in every DUT instance
binds — and an abort there is a statement about *conditioning against a
tolerance*, not about what the circuit was doing. That is exactly what
Evidence 4 observed directly at the committed deck's own abort, arrived at here
from the opposite direction.

**What this row is NOT.** It is not a claim that the committed deck's abort
would clear at some looser tolerance (that run is separate — see "What this
investigation does NOT establish"), and it is emphatically not a proposal to
set `reltol` or `abstol` anywhere in the tree.
`test_sar_ctrl_gates_tb.py::SharedSupplyRowTests` asserts that no
timing-gates manifest has gained a solver `options` entry, precisely so this
measurement cannot quietly become a fix.

### 5b. The per-loop decks reach the full ratified 8.5 µs

The prediction that follows from Evidence 4 is that removing the shared row —
without changing any circuit — retires the abort. #311 / PR #321 did exactly
that, for unrelated (cost) reasons, before this investigation existed, so the
measurement already exists in the tree:

| deck | DUT instances on `vvdd_gate` | window reached | accepted timepoints | evidence |
|---|---:|---|---:|---|
| `sim/sar-logic-timing-gates` (parent) | **5** | **aborts at 374.657 ns** (4.4 % of the window) | 65319 | this document, Evidence 4 |
| `sim/sar-logic-timing-gates-tie` | 1 | **full 8.5 µs, completes** | **9216** | measured here (below) |
| `sim/sar-logic-timing-gates-ok` | 1 | **full 8.5 µs, 45 of 45 points scored** | — | `sim/sar-logic-timing-gates-ok/records/20260918-233547-1d81aa1.md` |
| `--only-loops ok` (cut of the parent) | 1 | 400 ns, completes | 354 | Evidence 2 |
| `--only-loops tie` (cut of the parent) | 1 | 400 ns, completes | 477 | Evidence 2 |
| `--only-loops ok,tie` (cut of the parent) | 2 | 400 ns, completes | 482 | Evidence 2 |

**The `tie` row is the one #310's acceptance criterion 3 turns on, and it was
run here, over the manifest's own unmodified window:**

```
python3 design/sar-logic/flow/probe_cmp_convergence.py \
    sar-logic-timing-gates-tie --timeout 86400
# no --until: the deck's own `tran 5n 8.5u 0 5n`
-> RESULT : completed, no 'Timestep too small' abort (9216 timepoints)
   539.44 user (core-s), 4168.74 s wall, 169 MB max RSS
```

**The same `tie` loop, with the same chattering comparator, the same
`cmp_out_rc`, the same stimulus and the same DUT, runs the entire ratified
8.5 µs transient to completion** — the run #310 asked whether the loop's design
could reach at all. It can. Only the five-loop composition cannot.

The timepoint counts in the table are the quantitative form of the same point:
the `tie` deck needs **9216** accepted timepoints for the whole 8.5 µs, while
the five-loop parent burned **65319** to reach 374.657 ns — 7.1x the timepoints
for 4.4 % of the window, i.e. **~160x the timepoint density**, before failing.
That is the timestep coupling `20260917-issue-303-five-loop-composition-cost.md`
measured as a cost factor, seen here as the mechanism that also destroys
convergence.

The instance-count column is the whole mechanism, and it is asserted on the
committed text rather than left to this table:
`sim/tests/test_sar_ctrl_gates_tb.py::SharedSupplyRowTests` pins that the
parent carries exactly five `sar_ctrl_a` instances on one `vvdd_gate` source
and each per-loop deck exactly one.

**This is the answer to #310's acceptance criterion 3, and it is the good
answer rather than the resigned one**: the `tie` loop's design is *not* shown
to be unable to reach 8.5 µs. It reaches it on the deck that gets scored. What
cannot reach it is the five-loop composition, which is already superseded.

> **What the `tie` row does and does not say.** It says the solver survives the
> whole ratified window — which is exactly and only what a probe run can say.
> It does **not** say the loop passes: the probe replaces the manifest's
> measurement block, so `tie_code_deviation` and `tie_conv_period_ns` are not
> evaluated, and `sim/sar-logic-timing-gates-tie/records/` is still **empty**.
> Scoring that deck across the ratified grid is #303's remaining coverage, not
> this investigation's. The 539 core-s cost figure above is also not a
> comparable cost measurement — it was taken on a host carrying other agents'
> concurrent ngspice work throughout; #311's 233.7 core-s for the same deck via
> `sim/run_corners.py` is the figure to budget with.

## The candidate redesigns for the chatter, and why none of them is a Builder's call

The chatter is not retired by any of the above, and it should not be quietly
left un-filed. Each of these leaves #296's fix intact and addresses the
*decision* rather than its propagation. Each also changes what the `tie` loop
*claims*, which is a `spec/` decision record's business, not a testbench
edit's — DR-0008 defines this loop and `tb.json`'s `tie_conv_period_ns` /
`tie_code_deviation` are ratified bounds:

1. **Strobe the comparator** — decide once per bit trial and hold, instead of
   evaluating continuously. Keeps "always resolves to a rail"; removes chatter
   by construction, because the decision is only taken at instants when the
   differential is not being fed back. It is arguably *more* physical than the
   continuous-time model (a real SAR comparator is strobed). But it changes
   what "near-metastable" means for this loop, and it would have to be
   reconciled with the `lt`/`xl`/`bad` loops' `cmp_delay` model, which measures
   margin between a decision and the latching edge.
2. **Give the `tie` input a deterministic sub-LSB offset** — e.g.
   `vcm + 1 µV`, which is 0.0003 LSB (1 LSB = 3.223 mV at 3.30 V), so the loop
   is still pinned on the threshold to a thousandth of an LSB and
   `tie_code_deviation`'s "511 or 512" check is untouched. This gives the
   differential a sign that is a physical fact rather than a feedback artifact.
   But `tb.json` says the input is pinned **exactly** on the threshold, and
   "exactly" is the word doing the work in that claim.

Both are testbench-*definition* changes and are filed as **issue #322** rather
than smuggled in here, the same split
`20260917-issue-303-five-loop-composition-cost.md` used when it found the
five-loop composition was not required by any measurement.

Note what is **not** on this list any more: "decompose the deck per loop"
(#311) was the third candidate in the draft of this document, and it has since
landed (PR #321). It is no longer a candidate — it is Evidence 5b.

## What this investigation does NOT establish

- **It is not a scored PVT result.** `--until`/`--only-loops`/`--spice-option`
  runs answer "does the solver survive", not "what does the deck measure".
  Only `sim/run_corners.py` writes evidence, and the **five-loop parent deck
  still has no scored point** — unchanged from what
  `20260917-issue-303-five-loop-composition-cost.md` records. What changed
  since is that its per-loop successors do: `sim/sar-logic-timing-gates-ok/`
  has a full 45-point grid.
- **It does not claim the five-loop deck would converge with a different
  tolerance across the whole 8.5 µs window.** Evidence 5a is measured at one
  corner over 400 ns. Clearing one abort is not a completed transient, and no
  `.options` entry is proposed for any manifest on the strength of it — the
  deck is superseded, so the right response to its non-convergence is not to
  retune it.
- **The subset decks are not the committed deck.** See the callout in
  Evidence 2. For a single tag they *are* the committed per-loop deck; the
  two-loop row is neither.
- **The probe's retention is not always the corner runner's.** The probe
  replaces the manifest's control block and does not emit
  `run_corners.py --save-measured-vectors`' `save` line, and
  `20260917-issue-303-transient-cost-and-retention.md` measured this deck's
  accepted-timestep sequence to be sensitive to retention *and* to thread
  count. They happen to agree exactly at this abort (see "Correction" above),
  which is a result about this abort, not a general guarantee.
- **It does not reopen #296.** Every run above carries #296's fix, unmodified;
  `--cmp-rc` is a measurement knob that writes nothing, and the committed
  `CMP_OUT_RC = ("1k", "100f")` is unchanged in the tree.
- **It does not settle the cost question.** That is #303's and #311's, and
  this abort arrives long before that regime.
- **It does not retire the chatter.** That is issue #322 -- see "The candidate
  redesigns" above.

## Environment

- PDK: `gf180mcuD` @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
- ngspice: `ngspice-46`, compiled with the KLU direct linear solver — this deck
  still runs on SPARSE 1.3 (`option klu` is not set; see
  `20260918-issue-308-klu-solver-evaluation.md`)
- Deck: `sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice`
  as committed, composed through `sim/harness`'s own `compose_deck`, so the PVT
  preamble, corner sections and `sar_ctrl_a` subckt are the ones
  `sim/run_corners.py` uses
- Host: 28 cores, 96 GiB, shared with other agents' concurrent ngspice
  workloads throughout (load average > 25 for the whole session). **No
  wall-clock figure anywhere above is a cost figure**; every quantitative claim
  is a voltage, a current, an accepted-timestep, or an accepted-timepoint
  count.
