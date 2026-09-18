# Investigation 20260918-issue-308-klu-solver-evaluation

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here) — a
measured evaluation of the KLU-vs-SPARSE lead Finding 6 of
`20260917-issue-303-transient-cost-and-retention.md` left open. Kept in
`investigations/`, alongside (not inside) `records/`, so the append-only
`records/` tree is never edited.

**Why it exists**: `ngspice-46` on this host reports "Compiled with KLU
Direct Linear Solver", but every run of this deck reports "Using SPARSE 1.3
as Direct Linear Solver". KLU is normally the faster factorisation for
large, sparse, strongly asymmetric matrices — exactly the shape of a
five-instance synthesized standard-cell deck. Issue #308 asks whether that
banner line is a real lead or not, and — per its own explicit acceptance
criteria — a measured negative result is as valid an outcome as a shipped
flag.

## Conclusion

**KLU is measurement-neutral but does not show a solid win on this deck.
No harness flag is added.** Both measured A/Bs below say the same thing in
two different ways:

1. On the gate-level deck (where a win would matter), the wall-time gap
   between solvers is explained almost entirely by a *different number of
   accepted timesteps*, not a genuine per-step speed-up — the identical
   failure mode `sim/harness/README.md` already documents for
   `--save-measured-vectors` on this same deck. Per accepted timepoint, KLU
   and SPARSE cost the same to within 0.6%, which is inside the noise of a
   shared, contended host. Peak resident set is not better either (174 MB
   against 169 MB).
2. On two cheap decks that reach every measurement window, KLU and SPARSE
   pick *different* accepted-timestep sequences (as expected — they are
   different valid factorisations of the same tolerance-bounded problem) but
   land on **bit-identical printed measured values**, so switching solvers
   is safe. Safe-but-not-faster is not a reason to add API surface.

Adopting KLU repo-wide, or as an opt-in flag, would add a knob with a
measured effect of ~0.6% on the one deck this investigation exists to help
— indistinguishable from noise on a host shared with other agents' runs —
while the actual blocker on the 45-point grid (Findings 1/2/5 of the #303
investigation: retention, timepoint-density-not-yet-plateaued, and a 1.0–2.0
CPU quota) is untouched. This closes the KLU lead from Finding 6 as
evaluated and not worth adopting, not as unmeasured.

## Method and provenance

Raw artifacts generated under `/tmp/klu-probe/` (scratch, not part of this
repo — transcribed here because that directory does not survive). Every
deck below is generated the same way #303's probes were: the harness's own
`compose_deck()` (`sim/harness/runner.py`), called directly from a Python
one-liner against this worktree's checkout at commit `cad2417` — the same
`gf180mcuD@c6d73a35f524070e85faff4a6a9eef49553ebc2b` PDK and `ngspice-46`
pinned by `sim/toolchain.json` — then hand-edited for the one line each probe
tests:

- **KLU variant**: insert `  option klu` immediately after
  `set num_threads=1` in the generated `.control` block. Confirmed against
  the `ngspice-46` source (`src/frontend/com_option.c`,
  `src/spicelib/analysis/cktsopt.c`: `OPT_KLU` sets
  `task->TSKkluMODE`, copied into `ckt->CKTkluMODE` by `cktdojob.c` at
  analysis time) and empirically: every KLU-variant log below prints "Using
  KLU as Direct Linear Solver" and every unmodified log prints "Using SPARSE
  1.3 as Direct Linear Solver". `.options klu` at netlist scope was also
  tested and has the identical effect; `option klu` inside `.control` was
  used throughout for a smaller, more localised diff against the harness's
  existing generated-deck structure.
- **Gate-level truncation**: `tran 5n 0.25u 0 5n` in place of the ratified
  `tran 5n 8.5u 0 5n`, matching #303's `s025` probe exactly — same
  truncation, same `--ngspice-threads 1 --save-measured-vectors`-equivalent
  deck (the save list is baked into `compose_deck(..., save_measured_only=True)`),
  so the two solver runs differ from each other by exactly the `option klu`
  line and from #303's own `s025` probe by nothing at all in the deck text
  (`diff` confirms this — see below).
- **Full-length decks** (`sim/sar-logic-timing`, `sim/cdac-bit-settling`):
  unmodified ratified `tran`, `--ngspice-threads 1`, no save list (irrelevant
  to a solver-neutrality question).

All runs `tt`/27 °C/3.30 V, single-threaded (`num_threads=1`), run
back-to-back in the same session on the same host so the SPARSE/KLU pair in
each row is directly comparable even though the host is shared with other
agents' unrelated ngspice runs throughout (this repo's own #303/#309/#310
sessions and an unrelated `gf180-pll` session were all running concurrently
during both gate-level probes below).

## Part 1 — truncated A/B on `sim/sar-logic-timing-gates/` (the deck that needs a win)

| id | solver | wall | user CPU | accepted timepoints | max RSS |
|---|---|---|---|---|---|
| `s025-sparse` | SPARSE 1.3 (default) | 766.16 s (12:46.16) | 728.13 s | 2669 | 169068 KB |
| `s025-klu` | KLU (`option klu`) | 672.37 s (11:12.37) | 639.02 s | 2357 | 173796 KB |

Both runs reach `2.50000e-07` s exactly (same truncation point as #303's
`s025`); both print the same all-zero, partly `out of interval` `meas`
output as #303 already flagged as vacuous at this truncation (4 `meas` lines
fail — `tie_a`/`tie_b`/`ok_a`/`ok_b` — because the manifest's measurement
windows start well past 250 ns). This truncation exists to measure *cost*,
not to substitute for the full-length neutrality check in Part 2.

**Per-accepted-timepoint cost** (the stable quantity per #303's own
methodology — see its Finding 3):

- SPARSE: 728.13 s / 2669 = **0.2728 s/point** (user CPU)
- KLU: 639.02 s / 2357 = **0.2711 s/point** (user CPU)
- Difference: **0.6%** — indistinguishable from host-contention noise on a
  shared box running several other agents' simulations throughout both runs.

**Wall-time delta is a timepoint-count artifact, not a solver speed-up**,
exactly the shape #303 documented for `--save-measured-vectors`:

- Wall time dropped 12.2% (766.16 s → 672.37 s).
- Accepted timepoint count dropped 11.7% (2669 → 2357).
- Those two numbers are the same story, not two independent effects.

This session's own SPARSE baseline (2669 accepted points to 250 ns) does
**not** match #303's own recorded `s025` figure (2039 accepted points to the
same 250 ns) even though the generated deck text is byte-identical (`diff`
against the `s025`-equivalent deck confirms this — the only difference is
the `.include` path, which does not change what is solved). The deck,
toolchain pin, and PDK hash are unchanged (verified: `git log` shows no
commits touching `tb_sar_logic_timing_gates.spice` since #296/#304, and
`sim/toolchain.json`'s pins are unchanged and satisfied). The most likely
explanation is host-to-host floating-point or ngspice-build variance in the
adaptive-timestep sequence this class of deck is already known to be
sensitive to (Finding 4 of the #303 investigation, which showed the same
deck's accepted-step sequence changing under `num_threads` alone). This does
**not** undermine the SPARSE-vs-KLU comparison above, because both sides of
that comparison were run back-to-back on the *same* host in the *same*
session — but it is a reason not to treat any single-host accepted-timepoint
count on this deck as portable evidence, and a candidate follow-on if
cross-host reproducibility of this deck's numerics ever needs to be a claim
in its own right.

Memory is not a reason to prefer KLU either: KLU's peak resident set (174
MB) was very slightly **higher** than SPARSE's (169 MB) at this truncation.

## Part 2 — full-length measured-values A/B (measurement neutrality)

Per the acceptance criteria, run to completion (not truncated) on two decks
whose measurement windows are all reached, comparing every printed `m_*`
digit.

### `sim/sar-logic-timing` (ideal XSPICE, same `tran 5n 8.5u 0 5n` shape as the gate-level deck)

18/18 accepted timepoints both sides. The accepted times themselves
**differ** between solvers (as expected — SPARSE and KLU are different valid
factorisations, free to pick different steps within the same LTE tolerance):

```
SPARSE: 1.56415e-07 6.20556e-07 1.00744e-06 1.53142e-06 1.97073e-06 ...
KLU:    3.32350e-08 4.37530e-07 9.49104e-07 1.40647e-06 1.93800e-06 ...
```

But every printed measured value is identical to all ten printed digits:

| measurement | SPARSE | KLU |
|---|---|---|
| `m_abs_err_delay_0ns` | 0.0000000000e+00 | 0.0000000000e+00 |
| `m_abs_err_delay_40ns` | 0.0000000000e+00 | 0.0000000000e+00 |
| `m_abs_err_delay_50ns` | 0.0000000000e+00 | 0.0000000000e+00 |
| `m_abs_err_delay_70ns` | 2.5600000000e+02 | 2.5600000000e+02 |
| `m_tie_code_deviation` | 0.0000000000e+00 | 0.0000000000e+00 |
| `m_tie_conv_period_ns` | 1.0000000000e+03 | 1.0000000000e+03 |
| `m_ok_conv_period_ns` | 1.0000000000e+03 | 1.0000000000e+03 |
| `m_acq_window_ns` | 1.8762480000e+02 | 1.8762480000e+02 |
| `m_iso_gap_ns` | 6.2488810000e+01 | 6.2488810000e+01 |

9/9 measured values agree exactly. Both runs completed in ~5 s wall (this
deck is cheap, as #303 already established), so this A/B cost nothing to
settle.

### `sim/cdac-bit-settling` (real gf180mcu PDK devices, `tran 25p 500n 0 10p`)

11/11 accepted timepoints both sides. All 24 printed `m_*` values (settling
steps, 1/2 Msps errors, ordering lags across the four unit-weight taps)
agree exactly to all ten printed digits between SPARSE and KLU. Included
because it is a real-device deck, not ideal XSPICE, and the issue asks for
"at least one" — this is the second, strengthening the neutrality claim
across both deck classes already used for the `--save-measured-vectors`
precedent.

**Conclusion of Part 2**: KLU is safe to use on this repo's testbenches —
switching solvers changes *which* adaptive timesteps are taken but not the
measured answer, to the precision this repo already reports results at.
Nothing here contradicts that; it just isn't a reason to add the knob on its
own; see the top-level Conclusion.

## What this means for issue #303 and the untried KLU lead

Finding 6 of `20260917-issue-303-transient-cost-and-retention.md` is now
evaluated, not merely noted: KLU is not the answer to this deck's cost
problem. The two limits that investigation actually identified — output
retention (Finding 1, solved by `--save-measured-vectors`) and a
timepoint-density that has not plateaued by 250 ns against a CPU quota of
1.0–2.0 cores (Findings 2 and 5) — are unaffected by which direct linear
solver factors the Jacobian, because per-step cost was never the binding
constraint on either axis. The 45-point grid's path forward is still the one
#303/#307 already state: a host or scope with materially more CPU quota
than this fleet currently hands an agent session, or a plateau density this
investigation did not have budget to measure.
