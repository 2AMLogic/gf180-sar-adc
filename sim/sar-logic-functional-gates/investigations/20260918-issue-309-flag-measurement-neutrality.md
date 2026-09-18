# Investigation 20260918-issue-309-flag-measurement-neutrality

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
every run below was taken `--no-write`) — a measurement-neutrality A/B of two
harness knobs, `--save-measured-vectors` and `--ngspice-threads`, on a
**gate-level deck with real synthesized standard cells**. Kept in
`investigations/`, alongside (not inside) `records/`, so the append-only
`records/` tree is never edited.

**Why it exists**: issue #309. Both knobs are documented as changing *how* a
point runs and not *what* it measures. On the two small reference decks
(`sim/sar-logic-timing`, ideal XSPICE; `sim/cdac-bit-settling`, real PDK
devices) that is well evidenced — a full A/B gives identical values *and*
identical accepted-timepoint counts. On the gate-level class it was
**unestablished in either direction**: #303 measured that both knobs move the
accepted-timestep sequence on `sim/sar-logic-timing-gates/` (2574 → 2039 for
the save list; 2039 → 4311 for `num_threads=1` → `4`), but the only A/B
available there was truncated at 0.25 µs — before every measurement window in
that manifest — so both sides printed all-zero `m_*` values and four `meas`
lines failed `out of interval`. Two identical vacuous outputs are not evidence
of agreement.

This settles it on the **cheaper deck of the same class** that issue #309
explicitly offers as an acceptable substitute. `sim/sar-logic-functional-gates`
carries the same synthesized `gf180mcu_fd_sc_mcu7t5v0` `sar_ctrl` netlist —
the 181-standard-cell `sar_ctrl_a` subckt — instantiated **twice** (the `se`
and `df` measurement domains) off one clock, against
`sar-logic-timing-gates`'s five instances. It is cheaper not because it
simulates less time (its ratified `tran 20n 64500n 0 20n` is 7.6× *longer*
than timing-gates' `tran 5n 8.5u 0 5n`) but because it is far less stiff: it
accepts 11589 timepoints over the whole 64.5 µs — 0.18 per simulated ns —
where timing-gates is already taking 20.6 per ns at 250 ns and still climbing
(#303 Finding 2). One full-length point here costs hours; one there costs tens
of core-hours.

## Summary of findings

1. **Both knobs are measurement-neutral on this deck, at full length.** All
   **16** of the manifest's `m_*` values are identical to **all ten printed
   digits** across `--save-measured-vectors` on/off and `--ngspice-threads`
   1/4. The spread is not "small"; it is exactly zero in every printed digit
   of every measurement.
2. **They are neutral despite moving the accepted-timestep sequence, exactly
   as #303 predicted they would.** The sequences diverge at the **3rd**
   accepted timepoint (save list) and the **2nd** (thread count), and end
   11589 / 11590 / 11538 points apart — yet 64.5 µs later every measurement
   agrees digit-for-digit. This is the first full-length demonstration on this
   deck class that "different accepted steps" and "different measured values"
   are genuinely separate claims, and that on a real synthesized netlist only
   the first of them happens.
3. **The "scheduling only" language in the two flags' `--help` text and in
   `sim/harness/README.md` is therefore justified on the gate-level class too
   — but for a *measured* reason, not the one the original wording implied.**
   The original `--ngspice-threads` help says results are bit-identical
   "because it changes ngspice's internal scheduling, not the circuit or the
   analysis". The second half of that is true and is the load-bearing part;
   the first half is not a mechanism, because on a stiff deck a scheduling
   change *does* reach the timestep controller. The docs are updated to say
   what was measured.
4. **The settings are therefore NOT load-bearing provenance for measured
   values on this deck** — the third bullet of #309's acceptance criteria does
   not fire. They remain load-bearing provenance for *cost and feasibility*
   (`--save-measured-vectors` is a feasibility requirement on
   `sar-logic-timing-gates`, ~39 GB of retained output without it), and
   records should keep quoting them for that reason.
5. **Wall time could not be measured per-configuration on this host, and the
   reason is itself worth recording.** Under the contention this host was
   already carrying, the scheduler equalises CPU share across concurrent
   ngspice processes so precisely that all three runs finished within **27 s
   of each other after 2 h 27 min** — a coincidence that is not one. Wall
   time here measures the scheduler's fair share, not the flag. Corroborated
   live: see Finding 3.

## Method and provenance

Raw artifacts are under `sim/.work/sar-logic-functional-gates/` in the
issue-309 worktree (scratch, gitignored — the figures are transcribed here
because that directory does not survive). Deck: `sar-logic-functional-gates`
at `tt` / 27 °C / 3.30 V, the nominal point, run `-j 1 --no-write`.

| id | work dir | deck difference | accepted timepoints | last accepted `t` |
|---|---|---|---|---|
| `f0_t1` | `20260918-094403-c43ad02` | no save list, `set num_threads=1` | **11589** | 6.45000e-05 |
| `f1_t1` | `20260918-094406-c43ad02` | `+ save v(…)` (12 nodes), `set num_threads=1` | **11590** | 6.44897e-05 |
| `f1_t4` | `20260918-094410-c43ad02` | same save list, `set num_threads=4` | **11538** | 6.44811e-05 |

The two A/B pairs #309 asks for are `f0_t1` vs `f1_t1` (retention, same thread
count) and `f1_t1` vs `f1_t4` (thread count, same retention).

**The decks are the ground truth here, not the command lines.** The three
generated `.spice` decks were diffed against each other directly:
`f0_t1` → `f1_t1` differs by exactly one added line (the `save` list), and
`f1_t1` → `f1_t4` differs by exactly one changed line (`set num_threads=1` →
`4`). Nothing else — same `tran`, same `meas` lines, same netlist, same
`.temp`, same model cards. Whatever CLI produced them, that is what ngspice
solved.

"Accepted timepoints" is a count of ngspice's own `Reference value :`
progress lines in each log, the same definition #303 used, so the two
investigations' counts are directly comparable.

**Provenance split.** The three runs were executed by an earlier session in
this worktree (started 2026-09-18T02:44 local, all three concurrent, on
`c43ad02`); this investigation re-derived every number below first-hand from
the raw logs they left — the timepoint counts, the divergence indices, and
all 48 measured values were extracted and diffed here, not transcribed from
that session's notes, which do not exist. Toolchain: `ngspice-46`, SPARSE 1.3
direct linear solver (its own banner reports it is *compiled with* KLU, but
this deck does not use it — see #308, which measured KLU and did not adopt
it). A corroborating 2×2 batch (adding the fourth cell, no save list at
`num_threads=4`) was launched at 13:16 UTC on `a4bbb57` and was still in
flight when this was written; it is not needed for either A/B pair, both of
which are closed by the table above.

## Finding 1 — every measured digit is identical, across both pairs

All 16 `m_*` values, as printed by ngspice at `set numdgt=10`, with the
manifest's own bounds alongside. The **same single column** is the output of
all three runs — `diff` of the extracted `m_*` blocks is empty for `f0_t1` vs
`f1_t1` and for `f1_t1` vs `f1_t4`:

| measurement | value (all three runs) | manifest bound | |
|---|---|---|---|
| `m_err_se_max` | `0.0000000000e+00` | [−0.5, 0.5] | PASS |
| `m_err_se_min` | `0.0000000000e+00` | [−0.5, 0.5] | PASS |
| `m_code_se_max` | `1.0130000000e+03` | [990, 1023.5] | PASS |
| `m_code_se_min` | `0.0000000000e+00` | [−0.5, 15] | PASS |
| `m_sw_conflict_se` | `8.8871060000e+00` | ≤ 15 | PASS |
| `m_nside_cells_se` | `4.4827670000e-02` | ≤ 0.1 | PASS |
| `m_err_df_max` | `0.0000000000e+00` | [−0.5, 0.5] | PASS |
| `m_err_df_min` | `0.0000000000e+00` | [−0.5, 0.5] | PASS |
| `m_code_df_max` | `1.0130000000e+03` | [990, 1023.5] | PASS |
| `m_code_df_min` | `0.0000000000e+00` | [−0.5, 15] | PASS |
| `m_sw_conflict_df` | `1.1073330000e+01` | ≤ 20 | PASS |
| `m_nside_cells_df` | `9.0499660000e+00` | [8.9, 9.1] | PASS |
| `m_conv_period_ns` | `9.9999990909e+02` | [999.9, 1000.1] | PASS |
| `m_acq_window_ns` | `1.8618180000e+02` | [185.0, 190.0] | PASS |
| `m_iso_gap_ns` | `6.4026070000e+01` | [60.0, 65.0] | PASS |
| `m_iso_gap_df_ns` | `6.4026140000e+01` | [60.0, 65.0] | PASS |

**The A/B is not vacuous, which is the whole point of doing it at full
length.** Every run reached 6.448–6.450e-05 against the manifest's
`tran 20n 64500n` stop time; every `meas` line resolved; there are **zero**
`out of interval` failures in any of the three logs, against the four the
0.25 µs `sar-logic-timing-gates` truncation produced. The measurements are
also non-degenerate: `m_sw_conflict_se` = 8.887, `m_nside_cells_df` = 9.050
and the three timing measurements are live, sensitive, sub-nanosecond-resolved
quantities — `m_iso_gap_ns` and `m_iso_gap_df_ns` differ from *each other* in
their 6th digit, so the printed precision is genuinely carrying information
rather than rounding everything to the same number.

Because the spread is exactly zero, #309's "quantify the spread against the
manifest's own bounds" branch collapses: there is no spread to quantify. The
margin column is reported above for orientation only, not as a tolerance the
flags consume.

## Finding 2 — the timestep sequences diverge almost immediately and converge on the same answers

The divergence #303 found on `sar-logic-timing-gates` reproduces here, and
earlier:

| pair | first differing accepted timepoint | values there | end counts |
|---|---|---|---|
| `f0_t1` vs `f1_t1` (save list) | **3rd** | 1.44800e-10 vs 1.96000e-10 | 11589 vs 11590 |
| `f1_t1` vs `f1_t4` (thread count) | **2nd** | 3.20000e-11 vs 6.40000e-11 | 11590 vs 11538 |

So neither knob is neutral at the level of the solver's trajectory — the
thread count perturbs the *second* accepted step, before the circuit has done
anything. The spread in total count is nonetheless small on this deck (0.45 %
between the extremes, against 26 % and 111 % for the same two knobs on
`sar-logic-timing-gates`'s 0.25 µs probe), which is consistent with the
divergence being a startup-transient effect the timestep controller
re-converges out of once the DUT instances are in steady clocked operation —
precisely the regime that deck's truncated probe never reached, and the reason
its 26 % and 111 % count gaps should not be read as the steady-state figure
either.

The mechanism is unremarkable once stated: both knobs perturb floating-point
*scheduling*, not the network, and the timestep controller's accept/reject
decision is a thresholded comparison on a local truncation-error estimate. A
perturbation at the last bit can flip one such comparison, which shifts the
whole subsequent step sequence. Every resulting trajectory is a valid solution
of the same system within the solver's own tolerance, and the manifest's
measurements — maxima, minima, and averaged interval widths over windows tens
of microseconds long — are insensitive to which one is taken, at ten digits.

**What this does and does not license.** It licenses the existing
"scheduling only" claim on this deck class, with evidence behind it. It does
not license extending "identical accepted-timepoint counts" (true on the two
small reference decks) to gate-level decks — that is false here and was false
on `sar-logic-timing-gates`. The two claims are separate and only the
measurement-neutrality one generalises.

## Finding 3 — this host cannot measure the flags' wall-time cost, and says so clearly

#309 asks for wall time per side. It is reported, with the caveat that it does
not mean what the column heading suggests:

| id | start (local) | end (local) | wall |
|---|---|---|---|
| `f0_t1` | 02:44:04 | 05:12:00 | 8876 s |
| `f1_t1` | 02:44:08 | 05:11:55 | 8867 s |
| `f1_t4` | 02:44:12 | 05:11:33 | 8841 s |

Three CPU-bound runs of measurably different amounts of work (11589, 11590 and
11538 accepted timepoints, at `num_threads` 1, 1 and 4) finishing within 27 s
— 0.3 % — of each other after two and a half hours is not a measurement of the
flags. It is the scheduler dividing a fixed share three ways: each run is
rate-limited by its CPU allocation, so all three progress at the same rate and
land together regardless of configuration.

This was confirmed directly against the live corroborating batch rather than
inferred. Four concurrent ngspice processes of that batch, at 2 h 29 min
elapsed:

```
  PID  ELAPSED      TIME
12920 02:29:25  18:02.96     (no save list, num_threads=1)
13130 02:29:21  18:01.61     (save list,    num_threads=1)
13336 02:29:19  18:01.51     (save list,    num_threads=4)
13676 02:29:15  18:00.34     (no save list, num_threads=4)
```

Accrued CPU time is equal to within **2.6 seconds out of 1082** across all
four, i.e. ~12 % of a core each. Note especially that `num_threads=4` accrues
the *same total CPU* as `num_threads=1` — under a share this tight the OpenMP
thread count buys nothing at all, it only splits the same allocation four ways.
That is the same conclusion #303 reached about `-j` under a 1.0 CPU cgroup
quota, arriving here by a different route (macOS scheduler pressure on a
shared host, no cgroup involved).

**Consequence**: a per-configuration cost comparison for these flags needs an
uncontended host and cannot be extracted from this repo's shared agent hosts
at all. It is deliberately *not* estimated here. #303's per-accepted-timepoint
normalisation remains the only cost quantity on this deck class that survives
contention, and it already found the two retention settings equal to within
2 %.

## Consequence for the documentation

`sim/harness/README.md` § "When output *retention*, not CPU, is what stops a
long run" previously said of the gate-level class: "it is not established
either way". That is now settled in the affirmative for measured values, and
the section is updated to distinguish the two claims explicitly — values are
neutral, accepted-timepoint counts are not. Both flags' `--help` text is
updated the same way, and `--ngspice-threads`' "bit-identical because it
changes ngspice's internal scheduling" is corrected: bit-identical *measured
values* is what was measured; the deck's step sequence is not bit-identical on
a stiff deck, and claiming a mechanism the evidence does not show is how the
`--save-measured-vectors` speed-up got misattributed in the first place
(#303 Finding 3).

No `tb.json` bound, `tran` parameter, or comparator model was touched, per
#309's explicit scope exclusion. Neither flag is removed:
`--save-measured-vectors` remains a feasibility requirement on
`sar-logic-timing-gates`.

## Reproduction

On an **uncontended** host (see Finding 3 — do not run these concurrently if
the wall-time column is wanted for anything):

```bash
# pair 1: retention, same thread count
python3 sim/run_corners.py sar-logic-functional-gates \
    --corners tt --temps 27 --supply-tol 0 -j 1 --no-write --ngspice-threads 1
python3 sim/run_corners.py sar-logic-functional-gates \
    --corners tt --temps 27 --supply-tol 0 -j 1 --no-write --ngspice-threads 1 \
    --save-measured-vectors

# pair 2: thread count, same retention
python3 sim/run_corners.py sar-logic-functional-gates \
    --corners tt --temps 27 --supply-tol 0 -j 1 --no-write --ngspice-threads 4 \
    --save-measured-vectors
```

Then, against each run's `sim/.work/sar-logic-functional-gates/<stamp>/tt_27c_3.30v.log`:

```bash
grep -c 'Reference value :' "$LOG"          # accepted timepoints
grep -c 'out of interval'   "$LOG"          # must be 0 -- a nonzero count means
                                            # the A/B is vacuous, see #303 Finding 4
grep -E '^m_[a-z_]+ = ' "$LOG" | sort -u    # the 16 measured values; diff these
```

## Follow-on work not done here

- The result is established on `sar-logic-functional-gates` and is *evidence
  about*, not proof for, `sar-logic-timing-gates` — same synthesized cell
  library and the same `sar_ctrl_a` subckt, but five instances instead of two
  and a transient roughly two orders of magnitude stiffer per simulated ns. If
  a future session ever has the budget for two full-length
  `sar-logic-timing-gates` points, repeating this A/B there is the direct
  confirmation. It is no longer *needed* to justify the documentation, which
  is the change #309 asked for.
- A per-configuration wall/CPU cost comparison for either flag remains
  unmeasured for want of an uncontended host (Finding 3).
