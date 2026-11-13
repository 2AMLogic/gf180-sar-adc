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

## Not re-qualified, with reason

| scope | reason | tracked in |
|---|---|---|
| `sar-logic-functional-gates`, `sar-logic-timing-gates` | not attempted in tranche 3. The decks need no further change and the job-split recipe above applies unchanged; what is missing is a fleet window. | #753 |
| `sar-logic-timing-gates-tie` | attempted in tranche 3 and abandoned, not recorded: of its 15 shard jobs only 6 were ever started — the rest sat `pending` for over 1800 s (`klt sim` reported `never_started: it has a job.json but no status.json after 1815s`) while the fleet was oversubscribed. Nothing was run on the dispatch host. Re-run with `--timeout 900 --max-units-per-job 3 --max-in-flight 1 --max-concurrent-jobs 3`; its own record measures 233.7 core-s/point on an uncontended host, so the 15402 s wall of `20260920-020802-2043286` is host contention, not deck cost. | #753 |
| `sar-logic-timing-gates-lt`, `-xl` | not attempted in tranche 3. Each extrapolates to ~570 core-s/point at full-core speed (their own records' calibration probes), so `--timeout 900 --max-units-per-job 3` fits the ceiling with ~3x margin. | #753 |
| `sar-logic-timing-gates-bad` | **excluded by the fleet's whole-job ceiling, not by effort.** Its last record is 0/45 with every point timed out at `--timeout 3400`, so it needs a per-point budget above 3400 s. `BATCH_MAX_JOB_SECONDS=3600` bounds a *one-unit* job at `3600 - 120 = 3480 s`, so no amount of splitting buys more than 80 s over the budget that already failed. Either the deck's per-point cost on a fleet instance turns out to be well under 3400 s (plausible — that record's host was the contended one, and the fleet is several times faster per point; measure it before assuming), or this grid needs a fleet slice with a higher ceiling (`BATCH_HEAVY_MAX_JOB_SECONDS`/`BATCH_LEAN_MAX_JOB_SECONDS` are 7200 s, but `klt sim` cannot select a slice). Do not widen a bound to make it pass: `-bad` is a negative control and is *expected* to violate its limit — it just has to produce a number to do so. | #753 |
| `design/sar-logic/flow/**` (STA/synth/P&R), `layout/adc-top/parasitics/**`, `layout/lvs/**` | not `klt sim` flows; they need the heavy (OpenROAD) fleet slice, which does not exist yet — 2AMLogic/2am#6548 is open and itself blocked, its proof runs refused at launch for fleet capacity. LVS `--check` must record the klayout-tools#1063 net-numbering caveat when it does run. | #754 |

## Fleet capacity during this tranche

The batch fleet was saturated for part of the session. `klt sim` accepted the
`sar-logic-functional-gates` set but none of its three per-supply jobs
(`klt-sim-03fa4557dfd8`, `klt-sim-c33f3ce62b66`, `klt-sim-e40b2adc2814`)
launched within the 600 s `--wait-for-capacity` window; the harness recorded
nothing and nothing was run on this host, per the no-local-fallback rule.
2AMLogic/2am#6548 independently measured the same pressure the same day
(`240 vCPU already running ... exceeds BATCH_MAX_VCPU=64`).
