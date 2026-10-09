# Issue #430 -- preflight refused by the fleet concurrency cap (2026-10-09, 08:20 UTC)

- **Date**: 2026-10-09 (UTC), 08:20:45-08:20:53
- **Base commit**: `d759e542` (main), clean worktree
- **Status**: **STILL PARTIAL -- ZERO of the 27 declared points have a banked record.** Follow-on to the four earlier 2026-10-08/09 notes (`20261008-issue-430-temperature-coverage-attempt.md`, `20261009-issue-430-preflight-recheck.md`, `20261009-issue-430-fleet-reopened-no-capacity.md`, `20261009-issue-430-0.7.0-client-mismatch-recurs.md`; none edited). This is an investigation note, not a `records/` entry: no number below is a result. Coverage statement unchanged (hot, 125 C only); `README.md`, `spec/`, hardware and targets untouched.

## 1. Tool state on this worker

- Host client `klt 0.7.0+g4cbdfa769875` (same build as the 03:48 UTC note), `KLT_SIM_BACKEND=batch`.
- Host ngspice reports `ngspice-42` on this worker (earlier notes saw 46 elsewhere). Irrelevant here: nothing ran locally.

## 2. The one preflight (not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md)' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`

| Item | Result |
|---|---|
| Fleet job | none -- refused at instance provisioning, before a job id was issued |
| Runner exit | `run_corners.py` exit 3, wall time 8 s |
| Error, verbatim | `batch backend failed: batch-fleet-provision.sh launch failed (exit 1): error: 8 instance(s) already running + 1 requested exceeds BATCH_MAX_CONCURRENT_INSTANCES=8` |
| `run_corners.py` | "`klt sim` returned no corner report (exit 1); nothing was simulated locally ... nothing was recorded, and no point was run on this host." |

## 3. Reading

This is a third, independent fleet failure mode, distinct from the runner version gate (03:48 UTC, job `klt-sim-81f4b2af5092`) and the Spot capacity refusal (02:30 UTC). The fleet-wide instance cap was saturated by other work, so the request never reached the runner; it therefore says nothing new about whether the 0.5.0 runner still rejects a 0.7.0 client (klayout-tools#2882 / #2851 state unchanged, so no comment was added there). The gap that the client fails fast rather than waiting out the cap is already filed as klayout-tools#2917; no new friction issue.

Per the host rules and the curator protocol there was no retry loop and no local fallback (a local grid is ~1.2 h per point; the 9-point 125 C record took 7173.86 s).

## 4. Declared vs completed

| Leg | Declared | Banked as a record |
|---|---|---|
| -40 C (tt/ss/ff x 3 supplies) | 9 | 0 (not submitted; preflight refused) |
| 27 C | 9 | 0 (not submitted) |
| 125 C | 9 | 0 new; the 9 points in `records/20261007-072654-800bf53.md` remain the hot control |
| Total | 27 | 0 new / 9 historical hot |

## 5. To finish #430

Unchanged from section 5 of `20261009-issue-430-fleet-reopened-no-capacity.md` and section 4 of `20261009-issue-430-0.7.0-client-mismatch-recurs.md`. Three conditions must hold at once: a client the runner accepts (0.6.0 passed at 01:26 UTC; `--klt-cmd 'uvx --from klayout-tools==0.6.0 klt'` gives one without changing the host tool), free slots under `BATCH_MAX_CONCURRENT_INSTANCES`, and Spot capacity. Then the full 27-point request (or the 9-point -40 C leg with `--subset-reason`) from a clean tree, `compose_enob_by_corner.py` on the new corner directory, and reconcile the 125 C points against `records/20261007-072654-800bf53.md` before any coverage wording changes.
