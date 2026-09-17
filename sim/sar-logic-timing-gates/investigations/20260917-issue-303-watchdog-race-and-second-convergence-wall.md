# Investigation 20260917-issue-303-watchdog-race-and-second-convergence-wall

Not a `sim/run_corners.py` evidence record — a root-cause writeup for two
things discovered while trying to land issue #303's nominal-point run after
`20260917-issue-303-transient-cost-and-retention.md` (this directory) handed
off with that run still in flight. Kept alongside, not inside, `records/`, so
the append-only `records/` tree is never edited.

**Why a separate doc from the cost/retention one**: that investigation is
about *why the grid is expensive*. This one is about two things that are not
cost at all — (1) why a run that actually finished still left no committed
record, and (2) a new, distinct ngspice non-convergence found only because
that run finally ran far enough to hit it. Neither belongs under a
"cost and retention" heading.

## Summary

1. **The detached run PR #307 left in flight did not get killed by systemd
   or its cgroup.** The earlier hypothesis in this worktree's hand-off notes
   — `setsid` survives session exit but the scope's `KillMode=control-group`
   later reaps the orphan after a grace period — is **wrong** and is
   retracted here with the evidence that disproves it.
2. **The actual reason no record survived: `loom-daemon`'s mid-build-death
   watchdog raced the simulation's own natural completion and deleted the
   evidence 21–40 seconds after it was written, via `git reset --hard` +
   `git clean -fd`.** This is a Loom infrastructure race, not anything wrong
   with the simulation or the harness.
3. **The simulation itself did not need killing — it aborted on its own**,
   45 min after ngspice's build-in output, with `Timestep too small; time =
   3.84657e-07, timestep = 6.25e-21: trouble with node "vvdd_gate#branch"`.
   This is **past the 200 ns horizon #296's own A/B validated** and reports
   the same node name previously seen only from the *rejected* soft-comparator
   prototype (`design/sar-logic/rtl/README.md` line ~219). It is a second,
   distinct non-convergence and needs its own issue and instrumentation per
   #303's own explicit scoping — filed as issue #310 (Part 3, below).

## Part 1 — the process-survival hypothesis is wrong; here is what actually happened

### What the hand-off notes claimed

A `.no-changes-needed` marker left in this worktree at 2026-09-17T20:54Z
recorded PID 3718211 (the real `ngspice` binary, launched via `setsid` from a
prior session) still running and healthy, and speculated that a *later*
session would find it killed by systemd: `setsid` detaches from the
controlling terminal/session but not from the cgroup, and a
`loom-agent-*.scope` systemd unit defaults to `KillMode=control-group`, which
(the note guessed) kills every process in the cgroup — including orphaned
`setsid` descendants — some `TimeoutStopSec`-style grace period after the
spawning session's own scope is stopped.

### What actually happened, checked directly on this host

`journalctl` shows the scope that launched the run,
`loom-agent-3596460-1966824229.scope` (started 2026-09-17T20:01:49Z for
`claude-wrapper.sh -p "/loom:sweep 303 --claim-owned 303"`), logged:

```
Sep 17 20:59:14 ip-172-31-74-176 systemd[862]: loom-agent-3596460-1966824229.scope: Consumed 48min 11.112s CPU time.
```

`systemctl`'s "Consumed ... CPU time" line for a scope is emitted when the
scope transitions to `stopped` — i.e. when its cgroup finally empties, not
when systemd forcibly kills it. **The scope survived from 20:01:49Z (launch)
to 20:59:14Z (57m 25s wall) — its own controlling `claude` session almost
certainly exited well before that (the earlier hand-off's own probe found
its process gone by around 20:47Z) — and only finalized the instant its last
member process, the orphaned `ngspice`, exited on its own.** There is no
`TimeoutStopSec`-triggered kill: `journalctl --since "2026-09-17 20:00"
--until "2026-09-17 21:10" | grep -iE "oom|kill"` returns nothing implicating
this PID, and no core file or ngspice-side "killed" message exists anywhere
in the work tree. A `setsid`'d background job on this host **does** survive
its launching session's exit, for as long as it keeps running, exactly as
intended — the earlier worry was unfounded.

### What actually ended the run

`sim/.work/issue303-run.log` (the harness's own captured stdout, written by
the run that was in flight — recovered from this worktree's `sim/.work/`
scratch area, which the destructive cleanup in Part 2 could not touch because
`sim/.work/` is gitignored) shows the run completed normally:

```
[  1/1] FAIL tt_27c_3.30v               doAnalyses: TRAN:  Timestep too small; time = 3.84657e-07, timestep = 6.25e-21: trouble with node "vvdd_gate#branch"

summary (0/1 points ok, 2989.8s):
...
record    : .../sim/sar-logic-timing-gates/records/20260917-200902-83ab3a7.md
snapshot  : .../sim/sar-logic-timing-gates/netlist-snapshots/20260917-200902-83ab3a7.spice
raw logs  : .../sim/sar-logic-timing-gates/corners/20260917-200902-83ab3a7
work dir  : .../sim/.work/sar-logic-timing-gates/20260917-200902-83ab3a7
status    : ERROR
```

`2989.8s` is 49m50s — matching the wall time from launch (~20:09) to the
progress sampler's own `ENDED` line at `2026-09-17T20:59:14Z`
(`sim/.work/issue303-progress.txt`). `run_point()`
(`sim/harness/runner.py`) calls `subprocess.run(..., capture_output=True)`
and only returns once the child has actually exited; the message above is
ngspice's *own* stderr text, and the harness went on to compute measurements,
call `report.write_netlist_snapshot()` / `report.write_record()`, and print
the full summary table — none of which happens after an external
`SIGKILL` (that shows up as a negative/signalled `returncode`, not a parsed
ngspice error string). **ngspice aborted on its own; nothing killed it.**

## Part 2 — what actually destroyed the evidence

`~/.loom/daemon.log` (the always-on `loom-daemon` process, PID 3659979,
running independently of any per-issue session) has the exact sequence:

```
[2026-09-17T20:57:35.444] [WARN] midbuild-watchdog: issue #303 (sweep-issue-303-1789675303) matches the mid-build-death signature (terminal, no PR, dirty worktree) but its worktree at .../worktrees/issue-303 is STILL IN USE by a live session the daemon does not track — live process(es) with cwd inside the worktree: [74550, 3718166, 3718169, 3718209, 3718211, 3718212, 3735106, 3735114]. REFUSING to `git reset --hard` it: ...

[2026-09-17T20:59:35.907] [WARN] midbuild-watchdog: issue #303 (sweep-issue-303-1789675303) matches the mid-build-death signature, but issue #303's freshest lease record names sweep `sweep-issue-303-1789678033` on host `host-e1d4c843` (renewed 7.2m ago, within the 15.0m TTL) — a DIFFERENT, still-live owner ... REFUSING to `git reset --hard` its worktree ...

[2026-09-17T20:59:36.427] [WARN] midbuild-watchdog: issue #303 (sweep-issue-303-1789678033) died mid-build with a dirty worktree and no PR — cleaning the worktree and re-dispatching once (#3895).
[2026-09-17T20:59:36.444] [WARN] clean-worktree: DISCARDING uncommitted state in .../worktrees/issue-303 (issue #303) via `git reset --hard` + `git clean -fd` — this is irreversible (#4449).
status --porcelain:
M sim/harness/runner.py
 M sim/tests/test_harness.py
?? sim/sar-logic-timing-gates/corners/20260917-200902-83ab3a7/tt_27c_3.30v.log
?? sim/sar-logic-timing-gates/netlist-snapshots/20260917-200902-83ab3a7.spice
?? sim/sar-logic-timing-gates/records/20260917-200902-83ab3a7.md
```

The `status --porcelain` the watchdog itself logged, one line before deleting
it, is direct proof the run's evidence (`records/20260917-200902-83ab3a7.md`,
its `netlist-snapshots/` companion, and its `corners/` raw log) **existed on
disk, complete, and untracked** at the moment the watchdog acted. `git reset
--hard` + `git clean -fd` discards tracked *and* untracked state; unlike
`worktree.sh`'s own bash-side stale-worktree reset
(`.loom/scripts/lib/worktree-race-rescue.sh`, added for #6334/#7463), which
deliberately never runs `git clean` and rescues tracked diffs to a patch
file first, this daemon-side path has no rescue step of either kind.

**Root cause, stated plainly**: the watchdog correctly deferred at 20:57:35
while `ngspice` was still alive (`STILL IN USE`, refused). ngspice exited on
its own (Part 1) around 20:58:5x–20:59:14. The watchdog's *next* tick,
20:59:35–36 — **21 to 40 seconds later** — found zero live processes with
`cwd` inside the worktree and treated that, correctly by its own design, as
"died mid-build" — but the worktree was not abandoned; it held the completed,
never-committed output of a run that had *just* finished. There was no
opportunity for any agent to `git add && git commit` in that ~21–40 second
window because no session was running at all at that instant — the
controlling session had already exited (that's what made the run "detached"
in the first place), and nothing was scheduled to wake up and commit the
moment the child process exited.

**This is a generic race, not specific to this repository or this
simulation**: any long-running background job that is launched, detaches
from (survives) its own controlling session's exit, and finishes at a moment
when no other live session happens to be using the worktree, will lose its
own output to this exact watchdog path. `~/.loom/daemon.log` shows the same
`clean-worktree: DISCARDING uncommitted state ... via git reset --hard + git
clean -fd` line fire for `gf180-trng` issue #254 one second after an
identical-shaped watchdog judgment
(`[2026-09-17T20:57:36.484]`), so this is not a one-off.

**Practical consequence for future long-running detached jobs in this
repo**: do not detach and walk away. Keep a live process with `cwd` inside
the worktree for the entire duration of any background run this watchdog
might see (the `STILL IN USE` refusal at 20:57:35 shows this genuinely works
as a defence), and — more importantly — be the one still attached the moment
the job finishes so the evidence can be committed within the same
uninterrupted session, before any watchdog tick has a chance to find the
worktree momentarily process-free. That is the approach this issue's own
re-run (below) uses: launched attached, in the foreground of a session that
stays resident until commit, specifically to close this race.

## Part 3 — a second, distinct non-convergence, past #296's own validated horizon

`design/sar-logic/rtl/README.md` (~line 220) already validated #296's fix
via `design/sar-logic/flow/probe_cmp_convergence.py --until 200n`, chosen
because "the latest abort anywhere in the 45-point grid is t = 1.566e-7 s" —
i.e. 200 ns comfortably covers every pre-#296 failure point. **The destroyed
run above reached t = 3.84657e-07 s (384.657 ns) before aborting — nearly 2x
past that validated horizon** — so #296's fix is confirmed correct for what
it was tested against, and this is new territory the 200 ns probe never
exercised.

The trouble node, `vvdd_gate#branch`, is the *same name* the #296
investigation reports for its **rejected** soft-comparator prototype
(`sim/sar-logic-timing-gates/investigations/20260917-issue-296-comparator-nonconvergence-root-cause.md`,
"What was tried and rejected"): a comparator parked statically near mid-rail
holds real `aoi21_1`/`nor2_1` gate inputs in their linear region, producing a
static crowbar current through the DUT with the supply branch as the
numerically troubled node. The **applied** fix is not that soft comparator —
it is a hard, always-resolves-to-a-rail decision reaching the DUT through a
100 ps `cmp_out_rc` first-order network — so this is not a regression to the
rejected design. But the same symptom (`vvdd_gate#branch`, "Timestep too
small") appearing from the applied fix, 384 ns in, is either coincidence or
evidence that the same crowbar-current mechanism can still occur later in a
long run under the RC-network implementation (for instance if some other
loop's comparator input sits close enough to its own crossing for long
enough that the RC-smoothed output lingers mid-rail through more than one
downstream gate's switching threshold). **This is a hypothesis, not a
finding** — distinguishing it needs the same kind of A/B instrumentation
`probe_cmp_convergence.py` already provides, extended well past 200 ns, which
is exactly the "new issue with its own instrumentation" #303's own
"explicitly NOT in scope" section calls for rather than revising #296.

Filed as a new issue rather than reopening #296 or #303: **issue #310**,
"sar-logic-timing-gates: second `Timestep too small` non-convergence past
200 ns, node `vvdd_gate#branch`, distinct from #296's fixed defect".

## What this means for issue #303

- The evidence-loss race (Part 2) is now understood and documented; the
  re-run this investigation accompanies was launched **attached** (no
  `setsid`/`nohup` detachment) specifically to close it for this one point.
- The per-point cost story from `20260917-issue-303-transient-cost-and-retention.md`
  is *not* what actually gated this point: it aborted at 384.657 ns, ~49m50s
  in, long before the tens-of-core-hours regime that investigation
  extrapolated for a *converging* point. The 45-point grid's true blocker,
  for at least the `tt`/27 C/3.30 V corner, is now a second correctness
  question (Part 3), not (only) a cost question.
- Whether the other 44 points hit the same wall, a different one, or
  actually converge past 384 ns is unmeasured and is exactly the follow-up
  issue's job, not this one's.
