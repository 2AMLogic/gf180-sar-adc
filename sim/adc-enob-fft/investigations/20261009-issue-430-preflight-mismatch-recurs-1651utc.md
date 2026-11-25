# Issue #430 -- batch preflight, version mismatch recurs (2026-10-09, 16:52 UTC)

- **Date**: 2026-10-09 (UTC), 16:51:58 to 16:52:53
- **Base commit**: `7e77d70a` (main), clean worktree
- **Status**: **STILL BLOCKED -- ZERO of the 27 declared points completed.** The 27-point grid (and the 9-point cold leg) was NOT launched. Coverage stays PARTIAL (hot, 125 C only). `README.md`, `spec/`, hardware, targets, FAIL verdicts and historical records untouched. This is an investigation note, not a measurement; no number here is a result.

## 1. The one preflight (not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md)' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`

| Item | Result |
|---|---|
| Host client | `klt 0.7.0+gb82427b30c96`, `KLT_SIM_BACKEND=batch`, ngspice 46 |
| Fleet job | `klt-sim-23fd959902ed` |
| Outcome | `batch_job_failed` / `batch_runner_version_mismatch`: runner klt `0.5.0` vs client `0.7.0+gb82427b30c96`; "the request was not run". `status ERROR`, 0 of 2 points passed. |

## 2. Reconciliation

| Leg | Declared | Completed |
|---|---|---|
| Preflight (tt, 27/125 C) | 2 | 0 (not run, version gate) |
| Cold leg (-40 C) | 9 | 0 (not submitted) |
| Full grid | 27 | 0 (not submitted) |

## 3. State relative to earlier notes

Same failure as `20261009-issue-430-preflight-recheck.md` and the 0.7.0 recurrence note. The earlier 0.6.0-client pass (job `klt-sim-6f2cb7260edf`) did not hold per klayout-tools#2882 (OPEN, last updated 2026-10-09 09:08 UTC, which already documents the 0.7.0 gate refusal and the 0.6.0 PDK include failure). State unchanged, so no new comment was posted there. No retry loop, no older-client attempt, no local fallback (local cost ~1.2 h per point).

## 4. To finish

When the runner image is updated (or #2882 fixed): repeat this preflight once, run the cold 9-point leg then the rest via `sim/run_corners.py adc-enob-fft ... --backend batch`, and analyse with `testbench/analyze_fft.py` and `testbench/compose_enob_by_corner.py`.
