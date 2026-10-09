# Issue #430 -- batch-fleet preflight re-check #2 (2026-10-09)

- **Date**: 2026-10-09 (~13:56 UTC), base commit `52367d9c` (main), clean worktree
- **Status**: **STILL BLOCKED -- ZERO of the 27 declared points completed.** The 27-point (and 9-point cold) request was NOT launched. Coverage stays PARTIAL (hot, 125 C only); `README.md` and all FAIL verdicts are unchanged. Follow-on to `20261009-issue-430-preflight-recheck.md` (not edited).

## Preflight (one request, not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted, as records/20261007-072654-800bf53.md' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`

| Item | Result |
|---|---|
| Fleet job | `klt-sim-f1e6c476c885` |
| Outcome | `batch_job_failed`, exit 87: fleet runner klt `0.5.0` vs client `0.7.0+g4cbdfa769875`; "the request was not run". Both points errored, 0 passed. |
| klayout-tools#2882 | still OPEN (last updated 2026-10-09T09:08:56Z); state unchanged, so no new comment |

Identical `batch_runner_version_mismatch` to the earlier 2026-10-09 job `klt-sim-6b66a0b8eff8`. No local fallback grid was run (host rules). Raw run dir was under the git-ignored `sim/.work/`; no evidence was recorded (`--no-write`).

## Remaining

When the runner image matches a released client (or #2882 is fixed for the 0.6.0 client): repeat one preflight, run the 9 cold points (-40 C) as a batch request, then room and hot, analyse with `analyze_fft.py` and `compose_enob_by_corner.py` (Sec 6 of `20261008-issue-430-temperature-coverage-attempt.md`).
