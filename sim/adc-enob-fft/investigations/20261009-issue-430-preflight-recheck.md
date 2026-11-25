# Issue #430 -- batch-fleet preflight re-check (2026-10-09)

- **Date**: 2026-10-09
- **Base commit**: `a882e090` (main), clean worktree
- **Status**: **STILL BLOCKED -- ZERO of the 27 declared points completed.** The 27-point grid was NOT launched. Coverage stays PARTIAL (hot, 125 C only); `README.md` wording is unchanged and no FAIL verdict is touched. Follow-on to `20261008-issue-430-temperature-coverage-attempt.md` (not edited).

## 1. Preflight (one request, not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance '<extracted, as records/20261007-072654-800bf53.md>' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`
(tt / 3.30 V / {27, 125 C}; host client `klt 0.7.0+g060a613b25aa`; deck sha256 as in the 2026-10-08 note.)

| Item | Result |
|---|---|
| Capacity | accepted this time (no `BATCH_MAX_CONCURRENT_INSTANCES` refusal) |
| Fleet job | `klt-sim-6b66a0b8eff8` (c7i.4xlarge spot, us-east-1f, AMI `ami-0e40e3245f1923ac8`) |
| Outcome | `batch_job_failed`, exit 87, 5 s: runner klt `0.5.0` vs client `0.7.0+g060a613b25aa`, `runner_compatibility: mismatch`; "the request was not run". Both points errored, 0 passed. |

Same `batch_runner_version_mismatch` as 2026-10-08: the runner image has not been updated. Older clients were not re-tried (the 0.5.0 client has no `batch` backend; the 0.6.0 client hits klayout-tools#2882, still OPEN, per the previous note). No fallback to a local grid.

## 2. Change since the last note

- Host ngspice is now `ngspice-46` (`run_corners.py --check-env`: OK, pins OK), so the host-side drift refusal of the previous note's Sec 3 no longer applies. A single local comparable point is therefore now admissible. It was deliberately not run: it costs ~1.2 h of a shared 8-core worker (the 9-point 125 C record took 7173.86 s) and a lone point cannot establish the grid; the 27-point request belongs on the fleet.
- Fleet capacity ceiling: not hit in this attempt (one attempt only).

## 3. Conclusion

- Remaining blocker: fleet runner image klt 0.5.0 must match a released client (or klayout-tools#2882 fixed for a 0.6.0 client). Commented on #2882 rather than filing a new issue.
- Coverage of ENOB / SFDR over -40 and 27 C is **unestablished**; hot-only limit in `README.md` stands.
- To finish: when the runner is updated, repeat this preflight, then run the 27-point command in Sec 6 of the 2026-10-08 note and analyse with `testbench/compose_enob_by_corner.py`.
