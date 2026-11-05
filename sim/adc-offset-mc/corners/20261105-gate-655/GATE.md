# Batch-compatibility gate, issue #655: PASSED (gate only, not the population)

Append-only evidence. This is the pre-population gate of #655, not a qualification record and
not a claim. The Offset row stays Unmeasured.

| Item | Value |
|---|---|
| Run | 2026-11-05, `klt sim --backend batch -o <abs> --format json sim/adc-offset-mc/testbench/request_screen_qual_null.json` (mismatch-off screening deck, n = 4, seed 20261009, tt / 3.30 V / 27 C, default `enforce`, no `runner_version_check` override) |
| Fleet job | `klt-sim-d7d6086a261d`, c7i.8xlarge spot, us-east-1a, AMI `ami-04591566329422a44`, exit 0, 360 s, runner concurrency 2 |
| Compatibility | `runner_compatibility: match`; runner klt `0.9.0`, client klt `0.9.1.dev1+g08669432fef6`; `options.ngspice_init` supported |
| Engine | fleet ngspice 46 |
| Outcome | 4/4 draws `pass` (report `null-report.json`; this supersedes the refusal in `../20261009-123828-refusal-478/`, which is kept) |
| Measured cost | about 90 s wall per draw at concurrency 2 (4 draws, 360 s), versus the 846 s/draw extrapolation in README 6.7 item 3 |
| Not run | the population (>= 1365 draws), the enabled screening request, any local grid |

Why the population was not run in this session: see the PR / issue #655 comment (DR-0038 is
still `proposed`, and README 6.7 item 1 requires it before any population; the run is also
hours of fleet time).
