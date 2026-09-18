# Investigation 20260917-issue-303-transient-cost-and-retention

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here) — a
cost and feasibility investigation of the ratified `tran 5n 8.5u 0 5n`
transient on this deck, written while issue #303's execution run was in
flight. Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only `records/` tree is never edited.

**Why it exists**: issue #303 asks for the 45-point `mos` grid to be *run*.
Twice now a session has started that run and handed off before any point
finished. The reasons are measurable, and measuring them is worth more than
another undocumented hand-off — two of the three load-bearing numbers the
preceding attempt recorded turned out to be attributed to the wrong cause.

## Summary of findings

1. **The ratified 8.5 µs transient is not merely slow on this deck; at
   ngspice's default output retention it is memory-infeasible on a 16 GB
   host.** This is why #289's 0/45 and #296's fix could never have been
   turned into a scored record just by "running it on a bigger budget".
2. **The accepted-timepoint density is still rising at 250 ns** — 0.88
   points/ns over 0–25 ns against 20.6 points/ns over 200–250 ns — so any
   cost extrapolation from a short truncation is a *lower* bound, not an
   estimate. The honest statement of per-point cost is "tens of core-hours,
   bounded from below", not a single figure.
3. **The `--save-measured-vectors` speed-up previously attributed to
   retention overhead is not that.** The A/B runs took different numbers of
   accepted timepoints (2574 against 2039 to the same 250 ns); per accepted
   timepoint the two cost the same to within 2%. The knob's justification is
   memory, and only memory.
4. **This deck's accepted-timestep sequence is sensitive to settings that
   should not change it** — both the save list and ngspice's OpenMP thread
   count. Measured values were unaffected on two smaller reference decks,
   but on *this* deck that neutrality is untested, because the only A/B run
   here was truncated before every measurement window. Recorded as a caveat
   on the numbers, and as follow-on work, not papered over.
5. **`ngspice-46` on this host is compiled with the KLU direct linear
   solver, and this deck is not using it** (its own log says `Using SPARSE
   1.3 as Direct Linear Solver`). That is an untested lead on the cost
   problem, not a result.
6. **The agent scope these runs execute in is hard-capped at 1.0 CPU**, so
   `-j` is not merely unhelpful here, it is actively harmful: five
   concurrent points measured 0.17–0.18 of a core each. Any plan for this
   grid that assumes "throw cores at it" has to check that assumption
   against `cpu.max` first.

## Method and provenance

All raw artifacts are under `sim/.work/probe/` in the issue-303 worktree
(scratch, gitignored — the figures are transcribed here because that
directory does not survive). Each run below is the same generated deck at
`tt`/27 °C/3.30 V, differing only in the line noted:

| id | deck difference | wall (s) | accepted timepoints | reached |
|---|---|---|---|---|
| `p025` | default retention, `tran 5n 0.25u 0 5n`, `num_threads=1` | 708 | 2574 | 2.50000e-07 |
| `s025` | `+ save v(…)` (9 nodes), otherwise identical to `p025` | 549 | 2039 | 2.49778e-07 |
| `s025t4` | as `s025` but `num_threads=4` | 353 | 4311 | 2.50000e-07 |
| `p050` | as `p025` but `tran 5n 0.5u 0 5n`; stopped early | 691 | 2510 | 2.44684e-07 |

"Accepted timepoints" is a count of ngspice's own `Reference value :`
progress lines in each log. The `wall` column for `p025`/`s025`/`s025t4` is
the run's own recorded duration; the host was shared with other work in all
cases, so wall times are comparable to each other only loosely, while the
timepoint counts are exact.

**Provenance split.** The four probe runs above were executed by the
preceding session in this worktree; this investigation re-derived every
number in the table from the raw logs it left, and the three findings below
that contradict that session's own reading of them are the reason the
re-derivation was worth doing. The resident-set figures for *default*
retention (686 MB at 190 ns, 866 MB at 229 ns, from watching `p050`) are
inherited and were **not** re-measured here. The `--save-measured-vectors`
resident-set figure **was** re-measured first-hand: the five concurrent
points of the abandoned `-j 5` launch `20260917-185843-4801483` held
160–161 MiB each, flat, over their eight minutes of life.

## Finding 1 — the memory wall, not the clock, is what makes the ratified transient infeasible

ngspice's default is to keep *every* node voltage and branch current of the
deck, at every accepted timepoint, in RAM for the whole run, whether or not
any `meas` line reads it. This deck is five synthesized ~181-cell DUT
instances sharing one clock — about 6300 output vectors.

At the inherited growth rate of ~4.6 MB per simulated nanosecond, the
ratified 8.5 µs stop time lands at **~39 GB for one point** on a host with
15.7 GB. That is not a slow run; it is a run that cannot finish, and a
*grid* of concurrent points exhausts RAM within the first simulated
microsecond. With `--save-measured-vectors` — an ngspice `save` line naming
only the nine node voltages this manifest's own `meas` lines read — the same
point holds a flat ~160 MB, measured on the in-flight run.

This reframes #289's 0/45 result. That record's 8 timeouts and 37
`Timestep too small` aborts were correctly root-caused to the comparator
model at #296, but even with #296's fix in hand, the ratified transient
would not have completed on this class of host at default retention. The
convergence fix was necessary and is not sufficient.

## Finding 2 — cost is bounded from below, because the timepoint density is still climbing

Accepted-timepoint density against simulated time, from the two 1-thread
runs:

| window | `p025` (default) | `s025` (save list) |
|---|---|---|
| 0–25 ns | 0.88 points/ns | 0.84 points/ns |
| 25–50 ns | 1.32 | 1.16 |
| 50–100 ns | 3.28 | 2.80 |
| 100–150 ns | 7.52 | 5.78 |
| 150–200 ns | 14.42 | 10.62 |
| 200–250 ns | 25.14 | 20.58 |

The density roughly doubles every 50 ns across the whole probe and has not
turned over at the truncation point, which is where the testbench's five
loops are still starting up. It must plateau once all five DUTs are in
steady clocked operation — but *where* it plateaus is unmeasured, and the
whole cost of the 8.5 µs run is in the 8250 ns this probe never reached.

Per-accepted-timepoint cost is the stable quantity: **0.275 s** (`p025`),
**0.269 s** (`s025`), **0.082 s** (`s025t4`, 4 threads) on one core of this
host. Quoting a single per-point wall figure for the ratified transient
would require the plateau density, so this investigation does not quote one:
the defensible statement is *tens of core-hours per point, and of order
10³ core-hours for the full 45-point grid*.

For the same reason, issue #303's own premise figure — "9562 accepted
timepoints per 200 ns … of order 7e5 timepoints, ~10 CPU-hours for ONE
point" — should be read as an order-of-magnitude bound too, not a schedule.

## Finding 3 — the retention knob's measured speed-up is a timepoint-count difference, not saved retention work

`s025` finished 159 s (22%) faster than `p025`, and the preceding session
attributed that to retention overhead. It is not: `s025` also took **21%
fewer accepted timepoints** (2039 against 2574). Normalised per accepted
timepoint the two runs cost 0.269 s and 0.275 s — the same to within 2%.

So `--save-measured-vectors` buys memory, essentially not CPU. The flag's
documentation says so now. The interesting question is the other half:

## Finding 4 — the accepted-timestep sequence on this deck is sensitive to settings that are supposed to be neutral

The `p025`/`s025` decks differ by exactly one line — the `save` list. Their
accepted-timepoint sequences agree for five points and then diverge (the
6th accepted point is 8.17503e-11 without the save list and 1.00000e-10
with it), ending 26% apart in count. The same happens for the OpenMP thread
count alone: `s025` and `s025t4` are the same deck with the same save list
and differ only in `set num_threads=1` against `4`, and take **2039 against
4311** accepted timepoints.

Neither knob changes the network being solved, so both sequences are valid
solutions of the same system within the solver's own tolerance — but
"different accepted steps" is not the same claim as "identical measured
values", and this deck's own A/B cannot distinguish them:

- On `sim/sar-logic-timing` (ideal XSPICE) and `sim/cdac-bit-settling` (real
  PDK devices), a **full** A/B at `tt`/27 °C/3.30 V with and without the
  flag gives measured values identical to all ten printed digits *and*
  identical accepted-timepoint counts (19/19 and 13/13). That is real
  evidence, and it is the evidence the flag's own documentation rests on.
- On **this** deck, the only A/B available is the 0.25 µs truncation above,
  which stops before every measurement window in the manifest: every `m_*`
  value printed by both sides is `0`, and four `meas` lines fail outright
  with `out of interval`. Two identical all-zero outputs are not evidence of
  agreement. Any claim that the flag is measurement-neutral *on this deck*
  is currently unsupported in both directions.

Consequence for record `20260917-185843-4801483` and any successor: treat
its values as accurate to the solver's own tolerance, not as bit-reproducible
across retention or thread settings. It is run at `--ngspice-threads 1`
specifically so the configuration another reader would reach for first is
the one that was measured.

Settling this honestly needs one full-length A/B of this deck with and
without the flag — two points of the very cost this investigation is about,
which is why it is filed as follow-on work rather than done here.

> **Update (issue #309, 2026-09-18)** — that follow-on was run, on the
> cheaper deck of the same class: `sim/sar-logic-functional-gates`, the same
> synthesized `gf180mcu_fd_sc_mcu7t5v0` `sar_ctrl_a` subckt at full length
> (`tran 20n 64500n`, every measurement window reached, zero `out of
> interval`). **Both knobs are measurement-neutral there**: all 16 `m_*`
> values identical to all ten printed digits across `--save-measured-vectors`
> on/off and `--ngspice-threads` 1/4, while the accepted-timestep sequences
> diverge at the 3rd and 2nd accepted timepoint respectively. So the two
> claims this finding separates are both correct, and only the *sequence* one
> is deck-dependent. This deck's own full-length A/B is still unrun, and the
> consequence stated above for record `20260917-185843-4801483` is unchanged
> as a matter of strict provenance — but the balance of evidence now favours
> neutrality here too. Derivation:
> `sim/sar-logic-functional-gates/investigations/20260918-issue-309-flag-measurement-neutrality.md`.

## Finding 5 — there is 1.0 CPU to spend, so `-j` makes things strictly worse

The cgroup v2 scope an agent session's processes run in on this host reports

```
$ cat /sys/fs/cgroup/<…>/loom-agents.slice/loom-agent-<pid>-<id>.scope/cpu.max
100000 100000
```

— a hard quota of **one CPU** for everything that session launches, however
many cores `nproc` reports. Measured directly against it: the `-j 5`
process-axis launch `20260917-185843-4801483` gave its five ngspice
processes 78–79 s of CPU each over 456 s of wall time, i.e. **0.17–0.18 of
a core per point**, summing to the quota.

This inverts the usual grid-running advice. `-j N` normally costs nothing
per point and buys N-way throughput; under a fixed quota it buys nothing at
all and divides each point's progress by N, so a subset of N points is not
"N points for the price of one" but "N points that each take N times as
long" — and with a per-point cost already in the tens of core-hours, five
points at a fifth speed is five points that never finish.

The consequence for this deck is stark and worth stating in one line: **the
only configuration in which a scored point for `sar-logic-timing-gates` can
exist at all on this host is one point at `-j 1`, spending the whole quota.**
That is what the run left in flight does.

## Finding 6 — an untested lead: KLU is available and unused

`ngspice-46` on this host reports `Compiled with KLU Direct Linear Solver`
in its banner, while every run of this deck reports `Using SPARSE 1.3 as
Direct Linear Solver`. KLU is normally the faster factorisation for large,
sparse, strongly asymmetric netlists — which is what a five-instance
synthesized standard-cell deck is.

This is a lead, not a result: nothing here measures KLU on this deck, and
switching solvers would need the same measured-values A/B that Finding 4
asks for. Recorded so the next session does not have to re-notice it.

## What this means for issue #303

The 45-point grid is not executable in one session, and not because of any
choice a session makes: per-point cost is bounded below at tens of
core-hours (Finding 2), and there is 1.0 CPU to spend (Finding 5). `-j`
cannot help, and nothing in scope may make the transient shorter — the 8.5 µs
stop time and the five-loop structure are fixed by the measurement
definitions themselves (`tie_conv_period_ns` needs `RISE=2`…`RISE=7` on
`tie_drdy`, i.e. seven whole conversions).

The run left in flight by this investigation is therefore the **nominal
point only** — `tt`/27 °C/3.30 V, record id `20260917-190817-4801483`,
`-j 1 --ngspice-threads 1 --save-measured-vectors --timeout 604800`,
superseding `20260915-210638-912a8ec`. That corner is the one #296
instrumented and the one whose pre-fix abort is documented to ten digits, so
it is the sharpest available before/after.

**The process axis (`ff`, `ss`, `fs`, `sf`), the temperature axis (−40 °C,
125 °C) and the supply axis (2.97 V, 3.63 V) are unmeasured for this deck and
stay unmeasured after that record.** It is 1 point of 45, not a stand-in for
the grid, and no statement anywhere should read it as one. The sibling deck
`sim/sar-logic-functional-gates/` does have its 5-point process-axis subset
(`records/20260917-044312-c7ff0ff.md`, 5 of 5) — the two gate-level decks are
*not* comparable point-for-point until this one's process axis is run.

Two things would change that, and both are follow-on work rather than
effort: a host or scope with more than 1.0 CPU of quota, and/or the KLU lead
in Finding 6 if it proves out under a measured-values A/B.
