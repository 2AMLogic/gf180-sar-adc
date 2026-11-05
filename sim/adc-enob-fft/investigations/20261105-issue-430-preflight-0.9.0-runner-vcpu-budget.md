# Issue #430 -- preflight on the klt 0.9.0 runner refused by the fleet vCPU budget (2026-11-05, 08:07 UTC)

- **Date**: 2026-11-05 (UTC), 08:07:35-08:07:42
- **Base commit**: `f3046d67` (main), clean worktree
- **Status**: **STILL PARTIAL -- ZERO of the 27 declared points have a banked record.** Follow-on to the eight 2026-10-08/09 notes in this directory (none edited). This is an investigation note, not a `records/` entry: no number below is a result. Coverage statement unchanged (hot, 125 C only); `README.md`, `spec/`, hardware and targets untouched.

## 1. Why this attempt was made

The operator's 2026-11-05T07:58Z comment on #430 reports the batch runner is now klt 0.9.0 (launch template `eda-batch-runner` v10) and klayout-tools#2882 is closed. The curator and champion protocol asks for exactly one 2-point `--backend batch --no-write` preflight to test that premise.

## 2. Tool state on this worker

- Host client `klt 0.9.1.dev17+gd76e6fe1cb7a`, `KLT_SIM_BACKEND=batch`.
- Nothing ran locally.

## 3. The one preflight (not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md)' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`

| Item | Result |
|---|---|
| Fleet job | none -- refused at instance provisioning, before a job id was issued |
| `run_corners.py` exit | 3, wall time 7 s |
| Error, verbatim | `vdd=3.3: batch_no_capacity: batch backend failed: batch-fleet-provision.sh launch failed (exit 1): error: 256 vCPU already running + 1 instance(s) of up to 32 vCPU exceeds BATCH_MAX_VCPU=224, and only 0 type(s) fit the -32 vCPU left (floor 3) -- the spot quota is shared with ci-spot (batch-fleet.md §vCPU budget)` |
| `run_corners.py` | "no request of the per-supply set produced a corner report; nothing was simulated locally ... nothing was recorded, and no point was run on this host." |

## 4. Reading

- The failure is `batch_no_capacity` (shared vCPU budget exhausted: 256 running against `BATCH_MAX_VCPU=224`). It is **not** `batch_runner_version_mismatch` and **not** the missing-PDK-include failure of klayout-tools#2882. Because the request was refused at provisioning, it never reached the runner. This preflight therefore does **not** confirm or refute that the 0.9.0 runner fixes the earlier gaps; the operator's premise is neither verified nor falsified.
- Same class as the 2026-10-09 concurrency-cap refusal (`20261009-issue-430-preflight-concurrency-cap.md`): a transient fleet-saturation refusal. The client-side fail-fast gap is already filed as klayout-tools#2917, so no new friction issue.
- Per the host rules and the curator protocol there was no retry loop and no local fallback (a local grid is about 1.2 h per point; the 9-point 125 C record took 7173.86 s).

## 5. Declared vs completed

| Leg | Declared | Banked as a record |
|---|---|---|
| -40 C (tt/ss/ff x 3 supplies) | 9 | 0 (not submitted; preflight refused) |
| 27 C | 9 | 0 (not submitted) |
| 125 C | 9 | 0 new; the 9 points in `records/20261007-072654-800bf53.md` remain the hot control |
| Total | 27 | 0 new / 9 historical hot |

## 6. To finish #430

Re-run the one 2-point preflight when the fleet has vCPU headroom (the budget is shared with `ci-spot`). If it passes, submit the 9-point -40 C leg first (`--subset-reason`), then the 27 C and 125 C legs or the full 27, from a clean tree; then run `compose_enob_by_corner.py` on the new corner directory and reconcile the 125 C points against `records/20261007-072654-800bf53.md` before any coverage wording changes.
