# Issue #430 -- preflight re-check: runner version mismatch persists (2026-10-09, 08:33 UTC)

- **Date**: 2026-10-09 (UTC), 08:33:27-08:34:36
- **Base commit**: `63069b85` (main), clean worktree
- **Status**: **STILL PARTIAL -- ZERO of the 27 declared points have a banked record.** Follow-on to the five earlier 2026-10-08/09 notes in this directory (none edited). This is an investigation note, not a `records/` entry: no number below is a result. Coverage statement unchanged (hot, 125 C only); `README.md`, `spec/`, hardware and targets untouched.

## 1. Tool state on this worker

- Host client `klt 0.7.0+g5c94de0ebbfe`, `KLT_SIM_BACKEND=batch`, klayout 0.30.12, PDK gf180mcuD (open_pdks f6eeac7d), deck sha256 `f6f4a96e...c594a24`.
- Netlist hashes: neither was recomputed during the 08:33 UTC preflight. Both are given here with their sources:
  - Deck file `sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice`: sha256 `b0baf1325167d110677bf5f5d8ce4156c8b138ba9d6c9f64fe1846ef5c04ef75`. This matches the testbench netlist sha256 in `records/20261007-072654-800bf53.md`. It was recomputed with `sha256sum` on the file at base `63069b85` when this note was revised after review, not during the run.
  - As-generated input netlist (the circuit body the harness builds for submission): sha256 `dfa76c61c7f22eb8b4e6119a90fee9099eb27d7b9337090676901a753fad6b49`. Copied from `20261009-issue-430-fleet-reopened-no-capacity.md`, not recomputed in this run. This is not the deck file's hash and not the record's hash.

## 2. The one preflight (not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md)' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`

| Item | Result |
|---|---|
| Fleet job | `klt-sim-e5d903779bb3` (spot m7i.4xlarge, us-east-1d, instance `i-0d3ac754a97d29e3e`) |
| Job state | `failed`, job command exit 87, 5 s elapsed |
| Diagnostic | `batch_job_failed` on both points: "the fleet runner runs klt 0.5.0 but the submitting client is 0.7.0+g5c94de0ebbfe -- the request was not run" |
| `run_corners.py` | exit 2, status ERROR, 0 passed / 0 failed / 2 errored; nothing recorded (`--no-write`); nothing simulated locally |

## 3. Reading

The fleet is reachable and has capacity this time (the 08:20 UTC concurrency cap cleared), but the runner image is still klt 0.5.0 and rejects a 0.7.0 client. This is the same mode as job `klt-sim-81f4b2af5092` (03:48 UTC); klayout-tools#2882 / #2851 state is unchanged, so no new comment was added there. Per the host rules and the issue protocol there was no retry loop and no local fallback (about 1.2 h per point locally).

## 4. Declared vs completed

| Leg | Declared | Banked as a record |
|---|---|---|
| -40 C (tt/ss/ff x 3 supplies) | 9 | 0 (not submitted) |
| 27 C | 9 | 0 (preflight point errored) |
| 125 C | 9 | 0 new; the 9 points in `records/20261007-072654-800bf53.md` remain the hot control |
| Total | 27 | 0 new / 9 historical hot |

## 5. To finish #430

The runner version gate was the only failure observed in this attempt. The preflight stopped at that gate, so later stages were not reached and this run says nothing about them. Those stages are the runner resolving the PDK include (klayout-tools#2882, still OPEN) and Spot capacity, plus the fleet concurrency cap seen at 08:20 UTC.

A client the runner accepts is needed. The only client on record that passed the gate is 0.6.0 (01:26 UTC, job `klt-sim-6f2cb7260edf`, per `20261009-issue-430-fleet-reopened-no-capacity.md`), and it is not a guaranteed fix. The same 0.6.0 client hit the #2882 PDK-include failure on 2026-10-08 (`20261008-issue-430-temperature-coverage-attempt.md`, rows 6-8) and only got past it on 2026-10-09. A 0.5.0 client is not an option: it has no `batch` backend (`20261009-issue-430-preflight-recheck.md`). No alternative client was tried here, because the issue protocol allows exactly one preflight. Once the runner accepts a client and the later stages pass, run the -40 C leg first, then the rest, from a clean tree, analyse with `analyze_fft.py` and `compose_enob_by_corner.py`, and reconcile 125 C against `records/20261007-072654-800bf53.md` before changing any coverage wording.
