# Issue #430 -- extracted ENOB/SFDR temperature coverage: attempt, block, and per-corner noise scope

- **Date**: 2026-10-08
- **Base commit**: `4b5693ef` (main), worktree clean at the start of every command below
- **Status**: **BLOCKED -- ZERO of the 27 declared points completed.** No cold or room-temperature ENOB/SFDR figure exists. The hot-only coverage limit in `README.md` is **unchanged**; this file does not relax it, and no FAIL verdict is touched.

This is an investigation note, not a `records/` entry: `sim/run_corners.py` writes a record only for a run that produced points, and none did. Every failed submission below is listed so the gap stays visible. Nothing here is a `sim/` measurement; the only numbers are re-derivations from existing records (marked as such).

## 1. Declared grid vs completed points

Declared (issue #430): `tt, ss, ff` x `-40, 27, 125 C` x `2.97, 3.30, 3.63 V` = **27 points**, drive/N/clock/extraction unchanged from `records/20261007-072654-800bf53.md` (N = 64, bin 31, 484.375 kHz, 1 MS/s, no window), deck `testbench/tb_adc_enob_fft_extracted.spice` (sha256 `b0baf1325167d110677bf5f5d8ce4156c8b138ba9d6c9f64fe1846ef5c04ef75`, byte-identical to the deck both 125 C records ran; manifest `testbench/tb.json` sha256 `4be757c33797e8bc5d6553c2e5a8239d806382e5d2ca2729af34bc3042677961`).

| Corner set | Declared | Completed in this issue | Source of any number |
|---|---|---|---|
| 125 C, 9 points | 9 | 0 new (9 pre-existing) | existing `records/20261007-072654-800bf53.md` (hot reproduction control, re-analysed below; not re-run) |
| 27 C, 9 points | 9 | **0** | -- |
| -40 C, 9 points | 9 | **0** | -- |
| **Total** | **27** | **0 new; 18 of 27 points have no data at all** | |

No hot reproduction control was re-run either (it needs the same fleet); the existing 125 C logs are re-analysed in Sec 4 only to prove the postprocessor and the per-corner noise composition reproduce the committed README figures.

## 2. Preflight against the actual batch fleet (as the champion comment required)

All requests were the intended deck, reduced to 2 points (`--corners tt --temps 27 125 --supply-tol 0`, i.e. tt / 3.30 V / {27, 125 C}) with `--no-write`, submitted by `sim/run_corners.py --backend batch` (never run locally). 2 points is the smallest request that `klt sim` sends off-host.

| # | Client | Result | Fleet job / detail |
|---|---|---|---|
| 1, 2 | host klt `0.7.0+g4cbdfa769875` | not submitted: `BATCH_MAX_CONCURRENT_INSTANCES=8` reached ("8 instance(s) already running + 1 requested") | capacity, 20:24:10Z and 20:27:00Z |
| 3 | host klt 0.7.0 | **`batch_job_failed`, exit 87, `batch_runner_version_mismatch`**: "the fleet runner runs klt 0.5.0 but the submitting client is 0.7.0 ... the request was not run" | `klt-sim-03c93d839a05` |
| 4 | `uvx --from klayout-tools==0.5.0 klt` (matching the runner) | `unsupported backend 'batch' (supported: local, local-parallel, remote)` | client-side, no job |
| 5 | 0.5.0 client, `--backend remote` | `backend 'remote' requires request.remote.ssh_key_path` | client-side, no job (no SSH key provisioned for this host) |
| 6 | `uvx --from klayout-tools==0.6.0 klt` | passes the version gate; job dies in ~5 s, exit_code 4: `Error: Could not find include file /home/ubuntu/.volare/gf180mcuD/libs.tech/ngspice/design.ngspice` on the runner; all points `measurement 's000' produced no value` | `klt-sim-cb1a8e594700` (m6i.4xlarge, us-east-1b) |
| 7 | 0.6.0 | same failure, reproduced | `klt-sim-2cc388427f2c` (c7i.8xlarge, us-east-1d) |
| 8 | 0.6.0, **different deck** (`sar-logic-timing`, the deck that smoke-ran on the fleet earlier today as `sim/sar-logic-timing/records/20261008-160023-8477a2e.md`, job `klt-sim-06a37517edf7`) | same `Could not find include file` failure -- so this is a fleet-side regression/PDK-location problem, not an adc-enob-fft deck problem | `klt-sim-2bb232e67bcb` |

Row 6-8 root cause as far as the evidence shows: the circuit body that `sim/harness/batch.py` generates `.include`s the submitting host's absolute PDK path; the runner image (`ami-0e40e3245f1923ac8`) has no such file. Filed generically as **2AMLogic/klayout-tools#2882**. The submission failures are fleet/tool conditions; nothing was retried on this host's cores.

## 3. Local single point: refused, and not forced

Host rules allow one local corner. The most informative single point (tt / -40 C / 3.30 V) was attempted with `--backend local`. The harness **refused it before simulating anything**: toolchain drift, host ngspice `42` against the pinned `>= 46` (`sim/toolchain.json`). This host's tools are provisioned from the worker spec and must not be changed from a sweep, and `--allow-toolchain-drift` would bank a record not comparable with the existing evidence. It was not used. The needed fix is a worker-spec change (ngspice >= 46 on loom workers) or a working fleet; both are outside this issue's remit. (A local point is also ~1.2 h wall: the 9-point 125 C record took 7173.86 s.)

## 4. What can be established without a simulation (re-derivation, not measurement)

### 4.1 Hot control re-analysed with per-corner noise

`python3 -I testbench/compose_enob_by_corner.py corners/20261007-072654-800bf53` (new script, this change) runs the existing `analyze_fft.py` on the committed raw 125 C logs and composes, **per corner**, the same-corner comparator noise (`vn_in_uv`, `sim/comparator-preamp-noise/records/20260801-123440-033b56b.md`, clean tree, 45/45) with kT/C at that corner's own temperature (`sqrt(2kT/C_side)`, C_side = 8.827 pF, ratified nominal). LSB = 3.3 V / 1024.

| corner-id | SFDR dB | distortion-only ENOB | comparator vn uV | kT/C uV | composed ENOB |
|---|---|---|---|---|---|
| `ff_125c_2.97v` | **60.41** | 9.256 | 151.6 | 35.3 | 9.247 |
| `ff_125c_3.30v` | 63.64 | 9.289 | 152.5 | 35.3 | 9.281 |
| `ff_125c_3.63v` | 60.48 | 9.255 | 153.2 | 35.3 | 9.247 |
| `ss_125c_2.97v` | 61.09 | 8.974 | 124.1 | 35.3 | 8.970 |
| `ss_125c_3.30v` | 62.96 | 9.180 | 125.2 | 35.3 | 9.175 |
| `ss_125c_3.63v` | 64.08 | 9.132 | 126.0 | 35.3 | 9.127 |
| `tt_125c_2.97v` | 62.58 | 9.125 | 135.6 | 35.3 | 9.120 |
| `tt_125c_3.30v` | 62.82 | 9.235 | 136.6 | 35.3 | 9.229 |
| `tt_125c_3.63v` | 61.47 | 8.860 | 137.3 | 35.3 | **8.856** |

Worst SFDR `ff_125c_2.97v` 60.41 dB; worst composed ENOB `tt_125c_3.63v` 8.856 bits. This reproduces the README's 60.41 dB / 8.855 bits (the 0.001-bit difference is the README's use of one hot constant, 0.0488 LSB, for all nine corners versus the per-corner sigma here). Both ratified rows stay **FAIL** on the hot subset, as before.

### 4.2 Per-corner noise scope for the 27 declared points

Corner-specific noise evidence **exists** for all 27 declared points (they are a subset of the 45-point clean-tree `comparator-preamp-noise` grid), so no hot value would have to be reused at other temperatures. Table for the later FFT results to be composed against (same method as 4.1; `sigma` is the comparator-plus-kT/C rms the composition would add):

| corner | vn uV | kT/C uV | sigma uV | sigma LSB |
|---|---|---|---|---|
| `tt_-40c_{2.97,3.30,3.63}v` | 84.0 / 84.5 / 84.7 | 27.0 | 88.3 / 88.7 / 88.9 | 0.0274 / 0.0275 / 0.0276 |
| `tt_27c_{2.97,3.30,3.63}v` | 103.8 / 104.5 / 104.9 | 30.6 | 108.3 / 108.9 / 109.3 | 0.0336 / 0.0338 / 0.0339 |
| `tt_125c_{2.97,3.30,3.63}v` | 135.6 / 136.6 / 137.3 | 35.3 | 140.1 / 141.0 / 141.7 | 0.0435 / 0.0438 / 0.0440 |
| `ss_-40c_{...}` | 76.9 / 77.6 / 77.9 | 27.0 | 81.5 / 82.2 / 82.5 | 0.0253 / 0.0255 / 0.0256 |
| `ss_27c_{...}` | 94.7 / 95.5 / 96.0 | 30.6 | 99.6 / 100.3 / 100.8 | 0.0309 / 0.0311 / 0.0313 |
| `ss_125c_{...}` | 124.1 / 125.2 / 126.0 | 35.3 | 129.0 / 130.1 / 130.8 | 0.0400 / 0.0404 / 0.0406 |
| `ff_-40c_{...}` | 93.3 / 93.6 / 93.8 | 27.0 | 97.2 / 97.5 / 97.6 | 0.0301 / 0.0302 / 0.0303 |
| `ff_27c_{...}` | 115.9 / 116.4 / 116.8 | 30.6 | 119.9 / 120.4 / 120.8 | 0.0372 / 0.0374 / 0.0375 |
| `ff_125c_{...}` | 151.6 / 152.5 / 153.2 | 35.3 | 155.6 / 156.5 / 157.2 | 0.0483 / 0.0486 / 0.0488 |

Noise falls monotonically toward cold, so the hot noise constant is conservative for composed ENOB at -40 / 27 C; the cold/room question is therefore a **distortion** question, and the composed ENOB at cold can only be read off the FFT that was not obtained. Scope limits the composition carries (the script prints them): the comparator figure is a *schematic* ac `.noise` result, not an extracted-netlist one; C_side is nominal (no capacitor corner); the latch's own noise is bounded not measured (`spec/testbench-suite-memo.md` Sec 7.3); V_REF noise is user-supplied (README note [b]). A corner with no noise-record row is labelled `noise-unavailable` by the script and given no composed ENOB.

## 5. Conclusion

- **Coverage: PARTIAL, and unchanged.** Only the nine 125 C points exist. The -40 C and 27 C temperature coverage of the ENOB and SFDR rows remains **unestablished**; the cold-distortion/acquisition-lag comparison the issue asked for cannot be made without those points.
- Blocks, all external to the design: (a) fleet runner klt 0.5.0 refuses the host's 0.7.0 client; (b) with a 0.6.0 client the fleet cannot resolve the PDK include (klayout-tools#2882); (c) fleet capacity ceiling intermittently reached; (d) host ngspice 42 < pinned 46 forbids even one comparable local point.
- No hardware, target or spec change was made; ENOB and SFDR rows stay FAIL; no history was edited.

## 6. To finish #430 (when a path opens)

1. Fleet: a runner whose klt matches a released client **and** a runner PDK the generated body can include (or klayout-tools#2882 fixed). Preflight with the 2-point request in Sec 2.
2. Run the 27-point grid as one `klt sim` request:
   `python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --netlist-provenance '<as in records/20261007-072654-800bf53.md>' --corners tt ss ff --temps -40 27 125 --backend batch --timeout 7200` (clean tree, plus the 125 C subset reproduces the control).
3. `python3 -I sim/adc-enob-fft/testbench/compose_enob_by_corner.py sim/adc-enob-fft/corners/<new-record-id>` for the per-corner table; reconcile completed points against the 27 declared before any "full coverage" wording.
