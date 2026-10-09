# Issue #430 -- fleet path re-opened, then refused for capacity (2026-10-09)

- **Date**: 2026-10-09 (UTC)
- **Base commit**: `029777df` (main), clean worktree
- **Status**: **STILL PARTIAL -- ZERO of the 27 declared points have a banked record.** Follow-on to `20261008-issue-430-temperature-coverage-attempt.md` and `20261009-issue-430-preflight-recheck.md` (neither edited). This is an investigation note, not a `records/` entry and not a `sim/` measurement: no number below is a result.
- **Coverage statement**: unchanged. ENOB/SFDR remain hot-only (125 C); -40 C and 27 C coverage is unestablished. `README.md` and `spec/` untouched; FAIL verdicts untouched.

## 1. Tool state

- Host client: `klt 0.6.0+g1eb3e4bfd0f5` (earlier notes saw 0.7.0 on other workers). `KLT_SIM_BACKEND=batch`. Host ngspice 46.

## 2. The one allowed 2-point preflight -- PASSED (not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md)' --corners tt --temps 27 125 --supply-tol 0 --backend batch --no-write --timeout 3600`

| Item | Result |
|---|---|
| Start / end | 01:26 / 01:32 UTC |
| Fleet job | `klt-sim-6f2cb7260edf` (c7i.4xlarge spot, us-east-1f, AMI `ami-0e40e3245f1923ac8`, instance `i-0d33f9131e28f09cb`) |
| Outcome | `state done`, exit 0, 349 s on the fleet; `status PASS`, 2 of 2 points passed, 0 failed/errored |
| Input netlist sha256 (as generated) | `dfa76c61c7f22eb8b4e6119a90fee9099eb27d7b9337090676901a753fad6b49` (deck file `tb_adc_enob_fft_extracted.spice` sha256 `b0baf1325167d110677bf5f5d8ce4156c8b138ba9d6c9f64fe1846ef5c04ef75`) |
| PDK deck sha256 | `6edba54d23b38a2c60f8ffdbaa3eb75a7568c615e4820808969bd1121b77b1aa` (gf180mcuD, open_pdks c6d73a35) |

The two earlier blockers (`batch_runner_version_mismatch`, klayout-tools#2882 PDK include) did NOT reproduce with the 0.6.0 client against this runner state. Kept as `--no-write` debugging evidence only: it is not a record, no figure from it is used, and it does not reproduce the hot control (that needs the 9-point record).

(An initial invocation with a literal `<...>` provenance string was rejected client-side by `run_corners.py` before any submit; the corrected string is above.)

## 3. The 9-point cold request -- REFUSED for fleet capacity (not retried)

`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md ...)' --corners tt ss ff --temps -40 --backend batch --timeout 7200 --claim '...' --subset-reason '...'` (9 points: tt/ss/ff x -40 C x 2.97/3.30/3.63 V), ~02:30 UTC.

Result, verbatim from the client: `batch backend failed: batch-fleet-provision.sh launch failed (exit 1): error: no capacity in any of the 30 pools after 3 attempt(s)`, code `batch_no_capacity`. `run_corners.py`: "`klt sim` returned no corner report (exit 1); nothing was simulated locally ... nothing was recorded, and no point was run on this host."

(The first attempt at this request, ~01:33 UTC, was rejected client-side because `run_corners.py` requires `--subset-reason` for a non-full-matrix record; no submit occurred.)

Per host rules and the curator protocol there was no retry loop and NO local fallback: a local grid is ~1.2 h per point (the 9-point 125 C record took 7173.86 s).

## 4. Reconciliation (declared vs completed)

| Leg | Declared | Banked as a record |
|---|---|---|
| -40 C (tt/ss/ff x 3 supplies) | 9 | 0 (capacity refusal) |
| 27 C | 9 | 0 (not submitted) |
| 125 C | 9 | 0 new; the 9 pre-existing points in `records/20261007-072654-800bf53.md` remain the hot control |
| Total | 27 | 0 new / 9 historical hot |

## 5. To finish #430

The path is open; only capacity stopped it. On a worker/time with fleet capacity, from a clean tree:
`python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance 'extracted (as records/20261007-072654-800bf53.md)' --corners tt ss ff --temps -40 27 125 --backend batch --timeout 7200` (full matrix, so no `--subset-reason`; or the cold leg alone with `--subset-reason`), then `python3 -I sim/adc-enob-fft/testbench/compose_enob_by_corner.py sim/adc-enob-fft/corners/<new-record-id>`; reconcile the 125 C points against `records/20261007-072654-800bf53.md` before any coverage wording.
