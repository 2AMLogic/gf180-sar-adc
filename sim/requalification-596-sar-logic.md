# Re-qualification under open_pdks f6eeac7 — SAR-logic / extraction flow group (issue #596)

Part of #515 (grandparent #513). Old records stay untouched (append-only);
each new record names its `Supersedes` target and carries the fleet job ids in
its Environment section. Pinned PDK: open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`; fleet engine ngspice 47, `klt sim`
backend `aws-batch-fleet`, client klt 0.9.2.dev885.

This issue is landing in tranches. **Tranche 1** was PR #747; **tranche 2**
regenerated the decks but executed no gate-level grid; **tranche 3** is the PR
this paragraph lands in (#753). The remainder is tracked in #753 and #754.

## Tranche 2: the gate-level decks did not describe the pinned PDK

The re-pin (#514, merged as #517) did more than change which model file the
grids read. `gf180mcu_fd_sc_mcu7t5v0`'s **SPICE library** changed with it:

| | open_pdks `c6d73a3` | open_pdks `f6eeac7` |
|---|---|---|
| device the standard cells bind | `nfet_06v0` / `pfet_06v0` (4809 occurrences) | `nfet_05v0` / `pfet_05v0` (4810) |
| `__clkbuf_1`'s pull-up | two parallel `W=5.25e-07` pfets | one `W=1.05e-06` pfet (upstream fix, "to properly match the layout", 2025-11-03) |

The seven gate-level decks **inline that library text**, so every one of them
still described the *old* standard cells. Both device models exist in the new
`sm141064.ngspice`, so the stale decks still simulated — they simply simulated
the wrong transistors. A grid run against them is not a re-qualification
under `f6eeac7`, which is why tranche 1's gate-level attempt is not counted as
one below even where it produced numbers.

Regenerated with `python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py`.
The deck diff is **device-name-only**: all 1148 changed lines are a
`*fet_06v0` -> `*fet_05v0` swap, every `W`/`L` unchanged. The `__clkbuf_1`
geometry fix does not reach these decks — the synthesized `sar_ctrl` netlist
never instantiates that cell (0 occurrences in all seven decks).

**Consequence for the evidence tree**: the decks' sha256 moved, so every
record taken under `sim/sar-logic-*-gates*/records/` before this change stays
committed but is evidence for the **old** instrument — the same consequence
DR-0031 part 2 recorded for the previous deck change.

### How this went unnoticed for 29 days

`sim/tests/test_sar_ctrl_gates_tb.py`'s drift tests compare each committed
deck with a fresh generation. They `skipTest` when no gf180mcu PDK is
resolvable, which is the case on the PR CI runner (`.github/workflows/ci.yml`
installs no PDK) — so the PR path was green throughout. The nightly PDK job
(`.github/workflows/nightly-pdk.yml`, which does install the PDK) **did**
catch it and filed **#632**, open since the re-pin landed on 2026-10-15.
Regenerating the decks takes that suite from 9 failures to 916/916 passing and
closes #632.

T1 item 9 attests those decks' bytes, so its inventories, envelopes and
manifest pins moved with them (signoff record `20261113-093700-a699814d`,
18/22 met + 1 not applicable, row table byte-identical — no row moved). The
same pass corrected the open_pdks revision both item-9 inventories still
declared (`c6d73a3` -> `f6eeac7`), which is the `signoff/testbench-inventory.*.json`
line of this issue's scope.

## Re-qualified in tranche 1 (PR #747)

| experiment | new record | supersedes | old-vs-new |
|---|---|---|---|
| sar-logic-functional (rung-1 ideal XSPICE, 3 supplies) | `20261113-080421-3eed6a0` | `20260802-110241-131989b` | PASS. All 1023/0 codes, ±0 LSB error, conv_period 1000 ns, acq_window 187.522 ns unchanged; iso_gap 62.2133–62.2145 ns vs 62.2133–62.2137 ns (<0.001 ns); `sw_conflict` ~4.2e-14 vs ~4.2e-14 (limit 0.02). No metric moved beyond tolerance. |

`sar-logic-functional` and `sar-logic-timing` are rung-1 ideal-XSPICE decks
with no PDK device models, so the deck regeneration above does not touch them
and their records stand. `sar-logic-timing` already has a record under
`f6eeac7` (`20261031-191202-befcce4`, superseding `20260802-102758-d8a363d`).

## Re-qualified in tranche 2 (this PR)

Nothing. Both gate-level grids this tranche attempted were defeated by the
batch fleet, and per the no-local-fallback rule neither was re-run on the
dispatch host. The decks are now correct (above); what is missing is fleet
capacity to execute them.

| experiment | outcome | detail |
|---|---|---|
| sar-logic-functional-gates | **not launched** | `klt sim` accepted the per-supply set but none of `klt-sim-03fa4557dfd8` / `klt-sim-c33f3ce62b66` / `klt-sim-e40b2adc2814` left `pending` inside the 600 s `--wait-for-capacity` window. The harness recorded nothing; no point ran on this host. |
| sar-logic-timing-gates | **ran, no usable evidence** | All three jobs launched, then 45/45 points failed: 30 `batch_job_interrupted` (`klt-sim-fee52cb1f49f` and `klt-sim-752d46d96a11` were Spot-reclaimed and sat `interrupted` for 1821 s / 1817 s, past `batch.interrupted_grace_s=1800`, with no re-launch) and 15 `batch_job_timeout` (`klt-sim-204b1e17a0df` exceeded the 3600 s job ceiling). No point produced a result, so klt reported no engine identity and the pin check degraded to drift. |

**No record was committed for either.** `run_corners.py` writes the
`--supersedes` pointer even when every point errored, so committing the
`sar-logic-timing-gates` ERROR record would have put a measurement-free record
at the tip of that experiment's supersession chain, displacing
`20260915-210638-912a8ec` — the only record that has ever measured this deck.
The run's own output is reproduced above instead. That harness behaviour is
filed as **#755**; it already happened once, in tranche 1's
`20261113-080712-3eed6a0`, which declares `Supersedes: 20260917-044312-c7ff0ff`
even though every one of its 45 points timed out.

Both grids therefore remain open, alongside the five in #753.

## Re-qualified in tranche 3 (this PR, issue #753)

| experiment | new record | supersedes | old-vs-new |
|---|---|---|---|
| sar-logic-timing-gates-ok | `20261113-144745-9b2dea0` | `20260922-050206-81d166a` | PASS, 45/45 points, 548.27 s wall, on the regenerated `fet_05v0` deck (netlist sha256 `ed2615b4...`, against the old record's `191da09b...`). **No measurement moved.** All 45 points report `abs_err_delay_0ns` 0 and `ok_conv_period_ns` 1000 as before; comparing the two records point by point, `acq_window_ns` is identical at every one of the 45 corners to all printed digits, and `iso_gap_ns` differs by at most 1.0e-4 ns (at `tt_125c_2.97v`). Both ranges are unchanged: `acq_window_ns` 176.927 ns (`fs_125c_2.97v`) .. 197.182 ns (`sf_125c_2.97v`), `iso_gap_ns` 53.3054 ns (`sf_125c_2.97v`) .. 73.329 ns (`fs_125c_2.97v`). Every point is inside its DR-0028 bound and the worst slack is still 1.93 ns at `fs_125c_2.97v` on `acq_window_ns`'s 175.0 ns floor. |

This is the **first** gate-level grid of this issue to complete a full
45-point mos matrix under the pinned PDK, and the first on the regenerated
`fet_05v0` decks.

### What made it executable: splitting the grid across batch jobs

Tranche 2's gate-level grids were not defeated by the decks, by the deck cost,
or by bad luck. They were defeated by a **job shape** the harness could not
express. A 45-point mos grid exports as one `klt sim` request per supply, 15
corner units each, and `klt sim` bounds a batch job at
`options.timeout_s x units + 120 s`. The fleet kills anything past
`BATCH_MAX_JOB_SECONDS` (3600 s on 2am's default slice), so **any `--timeout`
above ~232 s already described a job that could not finish**: it was accepted,
it ran, and it was killed part-way with every one of its points reported
`batch_job_timeout`. That is exactly what `sar-logic-timing-gates` saw (15
`batch_job_timeout` on `klt-sim-204b1e17a0df`). The 30
`batch_job_interrupted` points on the other two jobs have the same root: a
15-unit job runs long enough that a Spot reclamation is likely, and `klt sim`
does not re-launch a reclaimed job.

`sim/run_corners.py` now passes the knobs klt already had
(`--max-units-per-job`, `--max-concurrent-jobs`, `--max-in-flight`,
`--capacity-retries`; see `sim/harness/README.md` § "Splitting a long grid
across batch jobs"). The run above used:

```
python3 sim/run_corners.py sar-logic-timing-gates-ok \
    --timeout 600 --max-units-per-job 5 --max-in-flight 1 \
    --max-concurrent-jobs 3 --capacity-retries 2 \
    --supersedes 20260922-050206-81d166a
```

Three jobs of 5 units per supply: a serial bound of `600 x 5 + 120 = 3120 s`,
inside the ceiling, and at most 3 instances occupied at a time. Measured, the
shards ran 94-130 s each — the fleet instance (`c7i.8xlarge` / `m6i.4xlarge`,
16-32 vCPU) is far faster per point than any host that produced the old
records, whose wall times were inflated by host contention (`-tie`'s own
record says so explicitly). **The old wall times are not a guide to fleet
cost**; the portable number is the per-point core-s each record states.

### Fleet concurrency is now the binding constraint, not job length

The first attempt at `-ok` this tranche asked for 9 instances (3 supplies x 3
shards, `--max-in-flight` left at klt's default 4) while a second experiment's
15 were also in flight. The fleet is vCPU-budgeted (`BATCH_MAX_VCPU=224`,
instances of 16-32 vCPU), so most of those jobs sat `pending` and came back
`not_launched` after the 600 s capacity wait: 15/45 points recorded, two whole
supplies lost. A concurrent read of the fleet during that window showed ~308
spot vCPU already running, i.e. the budget was oversubscribed by other work as
well as by this run.

The recipe that worked is therefore: **split to fit the ceiling, then bound
what you occupy**. `--max-in-flight x --max-concurrent-jobs` is the instance
count a run asks for; keeping it at 3 got every shard launched on a fleet busy
enough to refuse 9. Neither partial run was committed — a 15/45 record
carrying `Supersedes:` would have displaced a 45/45 one (the hazard #755
describes) — and nothing was re-run on the dispatch host.

### A split run's provenance had to be fixed to record it

`klt sim` reports a single batch job flat (`environment.remote` *is* the job
block) but reports a **split** request's jobs as a list under `remote.fleet`,
with no job identity at the top level. The harness knew only the flat shape,
so the first split run recorded ``fleet job `None` on None (None, None),
runner klt None [None], state None`` and an engine label naming no jobs at
all. The same blind spot silenced the runner/client skew check, which reads
`runner_compatibility` from that block. Both are fixed in this PR
(`harness.batch.fleet_blocks`), and the record above names each of its nine
shard jobs.

## Tranche 4 (issue #779): `sar-logic-functional-gates` — cost measured, grid still defeated by the fleet

**Nothing was recorded.** Both passes below were refused by the fleet before a
corner report existed, so `run_corners.py` wrote no record and no manifest, and
nothing was run on the dispatch host. `20261113-080712-3eed6a0` therefore
remains this experiment's chain tip, and its measurement-free `Supersedes:
20260917-044312-c7ff0ff` pointer is **still unrepaired** — the repair still
needs a measured successor naming `3eed6a0`, as `sim/README.md` says.

What this tranche *does* add is the number every previous tranche had to
guess: **this deck's per-point cost on a fleet instance.**

### Measured: 420.4 s per point at nominal; ~1223 s per unit at 2.97 V, 2 units in flight

A single-point batch probe (`--corners tt --temps 27 --supply-tol 0 --backend
batch --timeout 1700 --no-write`, fleet job `klt-sim-2487999b0924` on
`c7i.8xlarge`, us-east-1a spot):

| quantity | value |
|---|---|
| ngspice runtime for `tt_27c_3.30v` | **420.4 s** (`report.json` `corners[].runtime_s`) |
| fleet job launch → done | 467 s (15:33:24 → 15:41:11 UTC), i.e. ~47 s of provisioning |
| harness wall | 498.0 s |
| verdict | **PASS** |

The point also reproduces `20260917-044312-c7ff0ff`'s `tt` row on the
regenerated `fet_05v0` deck: `acq_window_ns` 186.186 vs 186.182, `iso_gap_ns`
64.0252 vs 64.0261, `iso_gap_df_ns` 64.0252 vs 64.0261, `err_se_*`/`err_df_*`
0, `code_se_max`/`code_df_max` 1013, `code_se_min`/`code_df_min` 0,
`conv_period_ns` 1000. That is a one-point result and not a re-qualification,
but it is direct evidence that the `fet_06v0` → `fet_05v0` deck regeneration
does not move this experiment's measurements at nominal.

A second figure came out of pass 1 below: shard `klt-sim-74f4498bc73a` ran
**2 units at 2.97 V, finishing in 1223 s**.

That 1223 s must **not** be divided by the unit count, because `klt` runs a
batch job's units *concurrently*. The job command the batch contract builds is
`klt sim ... --backend local-parallel --format json` with
`--max-workers "$EDA_PHYSICAL_CORES"` appended — "One ngspice per PHYSICAL core
on the job instance" (`klayout_tools/sim_batch_contract_jobspec.py:118`,
`:121`, `:131`) — and `--timeout` maps to `options.timeout_s`, which `klt`
documents as *per corner*, not per job (`klayout_tools/sim.py:2443`, `:2505`).
The only fully-serial quantity in the contract is `job.json`'s
`timeout_seconds`, and its own docstring says exactly that: "the fully-serial
worst case (every corner burns its own `options.timeout_s`, one after another)
... The job instance is concurrent (`$EDA_JOB_CONCURRENCY`), so a real run
finishes far inside this bound"
(`sim_batch_contract_jobspec.py:168`-`:177`). Every instance type this tranche
saw has at least 8 physical cores (`c7i.8xlarge` 16, `m6i.4xlarge` 8), so a 2-
or 3-unit shard holds all its units in flight at once. Toolchain for these
citations: `klt 0.9.2.dev1016+g606e5728939d`, the `which klt` copy under
`~/.local/share/uv/tools/klayout-tools`.

So the quantity `--timeout` is charged against is the **worst single unit's
wall — ~1223 s for that shard**, not a 610 s amortized figure, and that is
what the job shape below is sized from. Pass 1's own diagnosis already reads it
this way: what expired there was "the per-unit 1150 s budget on units that had
been running the whole ~1187 s".

Against the 420.4 s solo nominal point, ~1223 s is **~2.9x** — but the two are
not like-for-like, and that ratio must not be reused as a supply derate. The
1223 s carries the 2.97 V supply, 2-way concurrency on the instance, *and* an
instance type the shard records did not capture (the solo probe ran on
`c7i.8xlarge`), and this tranche cannot separate those three effects. Treat
~1223 s as an upper bound on a 2-up low-supply unit and 420.4 s as the only
clean single-unit measurement; a per-supply derate for this deck is still
unmeasured.

The grid total is independent of all of this, since instance-seconds =
wall x instances regardless of how units are packed: ~23 two-unit jobs at the
observed walls put the 45-point grid at about **21 000 instance-seconds**
(~5.9 instance-hours) of fleet compute — about 7000 s of wall at the three
instances the shared rule allows, before any provisioning or capacity wait.

### The job-shape window is narrower than the ceiling rule alone implies

A shape must satisfy **both** constraints, not just the documented first one:

* the fleet's whole-job ceiling — `job.json`'s `timeout_seconds` is
  `--timeout x N + 120` (`_BATCH_JOB_OVERHEAD_S = 120.0`) against
  `BATCH_MAX_JOB_SECONDS` (`DEFAULT_BATCH_MAX_JOB_SECONDS = 3600.0`, both in
  `klayout_tools/sim_batch_contract.py:228`, `:236`), so
  `--timeout <= 3480/N`; and
* `--timeout` is charged **per unit**, against units that run concurrently
  (previous section), so it must cover the *worst single unit's* wall under
  `N`-way concurrency — measured at **~1223 s** for this deck at 2.97 V with
  `N = 2`. It does **not** grow linearly in `N`: there is no serial queue to
  wait in while `N` stays under the instance's physical-core count.

Together `1223 <= 3480/N`, i.e. `N <= 2.8`, so **`--max-units-per-job <= 2`**
for this deck.

`--max-units-per-job 3` is outside that window, and that is a prediction this
model makes rather than a story fitted to the outcome: `N = 3` leaves only
`3480/3 = 1160 s` of per-unit budget, under the ~1223 s a low-supply unit of
this deck was measured to need. Pass 1 ran `N = 3` at `--timeout 1150` and
failed exactly there — accepted, launched, running, with the one unit slow
enough to exceed the budget truncated in each of the two shards that carried
one (`ss_novdd_n40C`, `fs_novdd_n40C`), while its two faster co-residents
completed; the `tt` shard's three units all fit and it returned 3/3. That the
casualty is the slowest *corner* and not a positional one is itself the
concurrency signature: units running at once have no "last" one to cut.

### Pass 1 — `--timeout 1150 --max-units-per-job 3` (stopped; mis-sized)

Three shards at 2.97 V ended at **1185 / 1187 / 1189 s**, a 4-second spread
against the 1150 s per-unit budget:

| shard | corners | outcome |
|---|---|---|
| `klt-sim-9d886ccfeea0` | tt, 3 temps | `done`, 3/3 units measured |
| `klt-sim-c4e7f220e13b` | ss, 3 temps | `failed`, 2/3 — `ss_novdd_n40C`'s `ngspice.log` truncated, no `.measure` output |
| `klt-sim-659a87f19761` | fs, 3 temps | `failed`, 2/3 — `fs_novdd_n40C` likewise |
| `klt-sim-641faf0fec7a` | — | launched 15:43:44, still `pending` 45 min later |
| `klt-sim-8efb707301fc` | — | not reached |

The jobs' requested `timeout_seconds` was `1150 x 3 + 120 = 3570 s`
(`klt`'s `_default_batch_job_timeout_s`, documented as "the fully-serial worst
case"), so nothing cut these jobs at the *job* level — what expired was the
**per-unit** 1150 s budget on units that had been running the whole ~1187 s.
This pass was stopped rather than recorded; it is listed because it is the
measurement behind the `N <= 2` result above.

### Pass 2 — `--timeout 1700 --max-units-per-job 2` (the sized shape; refused)

```
python3 sim/run_corners.py sar-logic-functional-gates \
    --timeout 1700 --max-units-per-job 2 --max-in-flight 1 \
    --max-concurrent-jobs 3 --capacity-retries 2 \
    --supersedes 20261113-080712-3eed6a0
```

`1700 x 2 + 120 = 3520 <= 3600`, inside the window above — but with only
**~1.39x** margin on the measured per-unit cost (`1700 / 1223`), which is
thinner than it looks: a unit more than ~39% slower than the 2.97 V shard's
worst would truncate silently. `3480/2 = 1740 s` is the most `--timeout` this
shape can carry, so the margin cannot be widened without dropping to
`N = 1`. 24 shards, 8 per supply. Final states:

| shard outcome | count | shards |
|---|---:|---|
| `collected` (units measured) | 8 | `74f4498bc73a`, `4cea4130ec6a`, `8fef5be7f3e3` (2.97 V); `351ea24dfbfb`, `26f6ff65af7d` (3.30 V); `ad1fc35a3dd2`, `f0c45f06e70c`, `c8cb6ed5cbff` (3.63 V) |
| Spot-reclaimed mid-run | 4 | `e2fa498edd34`, `68172462d31f` (2.97 V); `533925fa7f3e`, `78ea73ecbd97` (3.30 V) |
| never launched (`pending` past the 600 s wait) | 12 | `fec8a3bc1f9d`, `aefa6bc30208`, `d4ece335ccd0`; `2ca885a79744`, `e0b87802049b`, `8c798ac561e8`, `b1e60c14b520`; `823554f18fb1`, `54f427ec88af`, `fd77fe073a51`, `fd0b42b53307`, `feca65d47749` |

The four reclaimed shards were all `m6i.4xlarge` spot instances, in three
different AZs (us-east-1f, us-east-1d, us-east-1c), each reporting `spot
reclamation notice received; job did not complete — re-run it`. `klt sim` does
not re-launch a reclaimed job.

`run_corners.py` then exited 3 with

```
error: no request of the per-supply set produced a corner report;
nothing was simulated locally.
  vdd=2.97: not_launched: batch job klt-sim-fec8a3bc1f9d was accepted but did
            not launch within 600s (still pending)
  vdd=3.3:  not_launched: batch job klt-sim-2ca885a79744 ...
  vdd=3.63: not_launched: batch job klt-sim-823554f18fb1 ...
```

**16 of the 45 units did run and produce `ngspice.log` output**, but because
every per-supply member had at least one never-launched shard, `klt sim`
reported each member `not_launched` as a whole and emitted no corner report —
so those 16 measured points were discarded rather than banked as a partial
grid. That is the single biggest avoidable loss of this tranche.

### Fleet conditions

The fleet was carrying #778's calibration probes for `sar-logic-timing-gates-lt`
/ `-xl` and an unrelated repository's grid during both passes. Per the shared
rule the three children of #753 should not have grids in flight together; at
pass-2 submit time #777 was `loom:blocked` and #778 had only single-unit
`--no-write` probes running, which is why the window was taken.

One contributing factor is not a capacity shortage: **`--max-in-flight 1` did
not serialize the per-supply members.** All three were in flight at once
(2.97 V still had shards `submitted` when 3.30 V's launched at 17:01 and
3.63 V's at ~17:30), so the run asked for up to 9 instances rather than the 3
the shared rule intends — exactly the oversubscription that cost tranche 3 its
first `-ok` attempt. The flag is reaching `klt` on the command line; it is not
having the documented effect.

### Tool gaps filed

* **klayout-tools#5544** — `timeout_seconds` is computed as the fully-serial
  worst case (`per_corner_timeout x units + overhead`) while the runner charges
  `options.timeout_s` per unit against a job the fleet caps at 3600 s. This is
  what makes the window above `N <= 2`, and it fails silently as truncated
  units. The issue also asks for a loud submit-time refusal and per-unit wall
  times in the unit records.
* **#755** (a measurement-free record keeps its `Supersedes` pointer — the
  defect that put `3eed6a0` at the chain tip in the first place) is **closed**,
  fixed by #758: `build_record` now withholds the requested pointer when no
  point reached `ok` and records it as `supersedes_withheld` instead
  (`sim/harness/report.py:524`-`:531`). So the harness defect would not recur
  on a re-run; what still bites is the already-committed artifact — `3eed6a0`
  keeps the pointer it was written with, `sim/` is append-only, and only a
  measured successor naming it can repair the chain.

## Tranche 5 (issue #778): `sar-logic-timing-gates-lt` / `-xl` — cost measured above the fleet ceiling, nothing recorded

**Nothing was recorded, and the measurement below says no record is reachable
on this fleet slice at any legal job shape.** Everything here is a single-unit
`--no-write` batch probe — one ngspice per job, nothing written by the
harness, nothing run on the dispatch host. Probe points were chosen from the
old records' own scored rows (or, for row 1, a row they timed out on), so none
is a known-pathological corner.

| # | deck / point | old record said | `--timeout` | fleet job | instance | outcome |
|---|---|---|---:|---|---|---|
| 1 | `-lt` `tt_27c_3.30v` | ERROR (7200 s) | 900 | `klt-sim-04a1623057ab` | m6i.4xlarge, 8 phys. cores | **timeout** at 900.3 s |
| 2 | `-xl` `fs_-40c_3.30v` | FAIL (scored) | 900 | `klt-sim-0ad164c3f51c` | m7i.4xlarge, 8 phys. cores | **timeout** at 900.3 s |
| 3 | `-lt` `tt_27c_3.63v` | PASS (scored) | 3400 | `klt-sim-17867735ac6a` | c7i.8xlarge, 16 phys. cores | **timeout** at 3400.5 s (job elapsed 3456 s, exit 4) |
| 4 | `-xl` `fs_-40c_3.30v` | FAIL (scored) | 3400 | `klt-sim-6ed34855b358` | c7i.8xlarge, 16 phys. cores | Spot-reclaimed at 2501 s, unfinished |
| 5 | `-lt` `tt_27c_3.63v` | PASS (scored) | 3400 | `klt-sim-1b10b235c3c9` | m6i.4xlarge, 8 phys. cores | Spot-reclaimed at 779 s, unfinished |
| 6 | `-xl` `fs_-40c_3.30v` | FAIL (scored) | 3400 | `klt-sim-b912dcb9c099` | m7i.4xlarge spot, 8 phys. cores, concurrency 1 | **timeout** at 3400 s (state `failed`, exit 4; booted 14:30:11Z after ~4.6 h pending) |
| 7 | `-lt` `tt_27c_3.63v` | PASS (scored) | 3400 | `klt-sim-c82ec8daa10e` | never booted | `pending` 33 345 s+, no instance: `not_launched`, no datum |

Rows 3–7 pinned `num_threads=1` except rows 5 and 7 (default); with threads
pinned, wall seconds are core seconds.

**Measured per-point cost: > 3400 core-s on both decks** (rows 3 and 6) —
uncontended single-unit jobs, on the largest per-point budget any split can
carry (`3400 x 1 + 120 = 3520 <= 3600`), and ngspice was still integrating
when killed; row 3's log holds only the operating-point dump. That retires
this row's former "~570 core-s/point" extrapolation — wrong by at least 6x —
and is consistent with the #343 investigation's estimate that a point
surviving to the end of the ratified window needs of order 15 000–30 000 s.

**A record is unreachable for a second, independent reason.** #343
established that both old records' scored rows (10 and 6) are exactly their
mid-transient `Timestep too small` aborts — seven of `-lt`'s are false passes
— and the harness has since been fixed to score an aborted point `failed`
(issue #341; `harness/runner.py` applies the scan locally, `harness/batch.py`
to batch per-corner logs). Reaching `ok` therefore requires completing the
full `tran 5n 8.5u 0 5n`, which the 15 000–30 000 s estimate puts far beyond
the 3480 s per-point ceiling. The old "at least as many points" floor was
zero valid points all along. A `--timeout 900` pass (rows 1–2) measures
nothing at all, and its record would carry no `Supersedes:` pointer anyway
(#758 withholds it when no point reaches `ok`) — beside the shared rule
forbidding a record that scores below its predecessor. The attempt is
reported here instead of recorded, exactly as that rule prescribes.

**The common cost driver is the ideal lossless line.** `-lt` / `-xl` / `-bad`
are exactly the three per-loop decks carrying one (`z0=50`, `td=` 40/50/70 ns);
the two without one each completed a full 45-point grid (`-ok` ~132 core-s per
its record, `-tie` 233.7). `-lt` and `-xl` therefore join `-bad` in the
ceiling-excluded row below, and re-qualifying them needs a higher-ceiling
fleet slice or a deck-level decision — #303's territory, not a bigger budget
here.

The prescribed 15-job `--timeout 900` pass per deck was **not** submitted:
rows 1–2 already bound its every row as a timeout, and the queue it would
enter is the one that held row 6 pending for ~4.6 h and never booted row 7 at
all — the same pressure that produced tranche 4's `not_launched` majority.
Total probe spend: ~5 instance-hours for both decks' ceiling datums.

## Not re-qualified, with reason

| scope | reason | tracked in |
|---|---|---|
| `sar-logic-timing-gates` | not attempted in tranche 3 or 4. The deck needs no further change and the job-split recipe above applies unchanged; what is missing is a fleet window. | #753 |
| `sar-logic-functional-gates` | attempted in tranche 4 (#779) and **refused by the fleet**, not recorded — see the tranche-4 section above for the two passes, their 24 shard job ids and the Spot-reclamation / `not_launched` breakdown. Its per-point fleet cost is now measured rather than inferred (**420.4 s** solo at `tt_27c_3.30v`; a worst-unit wall of **~1223 s** at 2.97 V with 2 units concurrent), which fixes the job shape: `--max-units-per-job` must be **<= 2** for this deck, and `--timeout 1700 --max-units-per-job 2` is the sized pass to re-run unchanged when the fleet has capacity. The grid needs ~21 000 instance-seconds (~2 h of wall at three instances), so it wants a quiet fleet window rather than a different shape. | #779 |
| `sar-logic-timing-gates-tie` | attempted in tranche 3 and abandoned, not recorded: of its 15 shard jobs only 6 were ever started — the rest sat `pending` for over 1800 s (`klt sim` reported `never_started: it has a job.json but no status.json after 1815s`) while the fleet was oversubscribed. Nothing was run on the dispatch host. Re-run with `--timeout 900 --max-units-per-job 3 --max-in-flight 1 --max-concurrent-jobs 3`; its own record measures 233.7 core-s/point on an uncontended host, so the 15402 s wall of `20260920-020802-2043286` is host contention, not deck cost. This shape does survive the corrected concurrent model — `N = 3` allows `--timeout <= 1160`, and 900 s is ~3.85x the 233.7 s solo figure, so even tranche 4's confounded ~2.9x N-way inflation (~680 s) stays inside it — but the inflation itself is unmeasured for this deck. | #753 |
| `sar-logic-timing-gates-lt`, `-xl` | attempted in tranche 5 (#778) and **excluded by the fleet's per-point ceiling, like `-bad` below — measured, not inferred.** Single-unit `--no-write` fleet probes at `--timeout 3400` (the largest budget any split can carry) were still integrating when killed on both decks (`klt-sim-17867735ac6a` on `c7i.8xlarge`, `klt-sim-b912dcb9c099` on `m7i.4xlarge`, uncontended, `num_threads=1`), so the per-point cost is **> 3400 core-s** — at least 6x the ~570 core-s/point this row used to extrapolate from a 0.5 µs truncated calibration probe; that figure is retired. No record is reachable at any legal shape for a second reason: both old records' scored rows (10 / 6) are exactly their mid-transient `Timestep too small` aborts (#343 investigation; seven of `-lt`'s are false passes), the fixed harness (#341) scores an abort `failed`, and a full-window point needs ~15 000–30 000 s against the 3480 s ceiling — the old "at least as many points" floor was zero valid points all along. Both decks carry the ideal lossless line (`z0=50`, `td=` 40/50 ns) that `-ok` (~132 core-s) and `-tie` (233.7 core-s) lack and both ran full grids; see the tranche-5 section for all seven probe jobs and outcomes. Re-qualification needs a higher-ceiling fleet slice or a deck-level decision (#303 territory). | #778 |
| `sar-logic-timing-gates-bad` | **excluded by the fleet's whole-job ceiling, not by effort.** Its last record is 0/45 with every point timed out at `--timeout 3400`, so it needs a per-point budget above 3400 s. `BATCH_MAX_JOB_SECONDS=3600` bounds a *one-unit* job at `3600 - 120 = 3480 s`, so no amount of splitting buys more than 80 s over the budget that already failed. Either the deck's per-point cost on a fleet instance turns out to be well under 3400 s (plausible — that record's host was the contended one, and the fleet is several times faster per point; measure it before assuming), or this grid needs a fleet slice with a higher ceiling (`BATCH_HEAVY_MAX_JOB_SECONDS`/`BATCH_LEAN_MAX_JOB_SECONDS` are 7200 s, but `klt sim` cannot select a slice). Do not widen a bound to make it pass: `-bad` is a negative control and is *expected* to violate its limit — it just has to produce a number to do so. | #753 |
| `design/sar-logic/flow/**` (STA/synth/P&R), `layout/adc-top/parasitics/**`, `layout/lvs/**` | not `klt sim` flows; they need the heavy (OpenROAD) fleet slice, which does not exist yet — 2AMLogic/2am#6548 is open and itself blocked, its proof runs refused at launch for fleet capacity. LVS `--check` must record the klayout-tools#1063 net-numbering caveat when it does run. | #754 |

## Fleet capacity during tranche 3

The batch fleet was saturated for part of the session. `klt sim` accepted the
`sar-logic-functional-gates` set but none of its three per-supply jobs
(`klt-sim-03fa4557dfd8`, `klt-sim-c33f3ce62b66`, `klt-sim-e40b2adc2814`)
launched within the 600 s `--wait-for-capacity` window; the harness recorded
nothing and nothing was run on this host, per the no-local-fallback rule.
2AMLogic/2am#6548 independently measured the same pressure the same day
(`240 vCPU already running ... exceeds BATCH_MAX_VCPU=64`).
