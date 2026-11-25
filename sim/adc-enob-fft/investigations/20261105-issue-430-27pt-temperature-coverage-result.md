# Issue #430 -- 27-point extracted ENOB/SFDR temperature-coverage result (2026-11-05)

- **Date**: 2026-11-05 (UTC), submit 12:52, record minted 12:52:30, wall time 1004 s
- **Base commit**: `b281aa87` (main), clean tree at run time
- **Evidence record**: [`records/20261105-125230-b281aa8.md`](../records/20261105-125230-b281aa8.md) -- **27 of 27 declared points completed**, no aborts, no missing points. Raw logs and klt reports are in the artifact store (manifest `manifests/artifacts/adc-enob-fft-20261105-125230-b281aa8.manifest.json`, fetched hash-verified for this analysis).
- **Verdict**: both ratified rows (ENOB > 9.0, SFDR >= 62 dB) stay **FAIL**, and the governing worst point is now **cold**, not hot. No `spec/`, hardware or target change.

## 1. What ran

| Item | Value |
|---|---|
| Deck | `sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice`, provenance `extracted (as records/20261007-072654-800bf53.md)` (same extraction as the hot control) |
| Grid | tt/ss/ff x -40/27/125 C x 2.97/3.30/3.63 V = 27 |
| Backend | `klt sim` `aws-batch-fleet`, runner klt 0.9.0 [version match], 3 jobs (one per supply): `klt-sim-f032f71a6e94` (2.97 V), `klt-sim-d279ba6a9544` (3.30 V), `klt-sim-e5db247c5d67` (3.63 V), m7i.4xlarge spot, ngspice 46 |
| Preflight | one 2-point `--backend batch --no-write` request (tt, 27/125 C, 3.30 V) at 12:44 UTC returned status PASS; this clears the 2026-11-05 `batch_no_capacity` refusal and the earlier version-mismatch / PDK-include blockers on the 0.9.0 runner |
| Clean tree | record says `b281aa873d4b580ad426d10bc584a2c7621e21c6` on `feature/issue-430` (clean) |
| Analysis | `python3 -I sim/adc-enob-fft/testbench/compose_enob_by_corner.py <dir of the 27 fetched logs>` (default noise record `sim/comparator-preamp-noise/records/20260801-123440-033b56b.md`, C_side 8.827 pF, V_REF 3.3 V) |

## 2. Declared vs completed

| Leg | Declared | Completed |
|---|---:|---:|
| -40 C | 9 | 9 |
| 27 C | 9 | 9 |
| 125 C | 9 | 9 |
| **Total** | **27** | **27** |

All 27 corner statuses are `pass` (capture-validity verdict only; see the record's note). **13 of 27** points carry a klt `nonconvergence` warning, "Dynamic gmin stepping failed" (from the three `klt-report.vdd*.json`): at 2.97 V `tt_-40c`, `tt_27c`, `ff_-40c`, `ff_27c`; at 3.30 V `tt_-40c`, `tt_27c`, `ss_27c`, `ff_-40c`, `ff_27c`; at 3.63 V `tt_-40c`, `ss_-40c`, `ss_27c`, `ff_27c`. All are -40 C or 27 C points (none at 125 C), so the 125 C control is unaffected. The simulator recovered and finished all 64 samples in each, but these points are not clean convergence and are flagged rather than dropped. Whether the recovered operating point biases the cold/room distortion figures is not tested here.

## 3. Hot control reconciliation

The nine 125 C points of this fleet run reproduce `records/20261007-072654-800bf53.md` exactly in the composed table: worst SFDR `ff_125c_2.97v` 60.41 dB, worst composed ENOB `tt_125c_3.63v` 8.856 bits, and every per-corner SFDR / ENOB / sigma row identical to three decimals (compared against the committed 20261007 logs through the same script). The raw log bytes differ (klt-generated deck, different ngspice compatibility banner and measure formatting), but the extracted codes yield identical spectra. No discrepancy to record.

## 4. Per-corner table (distortion-only and composed ENOB are separate columns)

Noise scope, as printed by the script: comparator noise is the same-corner row of a **schematic** ac `.noise` record (not the extracted netlist); kT/C uses each corner's own temperature with nominal C_side = 8.827 pF (no capacitor corner); latch noise is bounded not measured (memo Sec 7.3); V_REF noise is user-supplied. No hot value is reused at another temperature.

| corner-id | SFDR dB | THD dB | distortion-only SNDR dB | distortion-only ENOB | comparator vn uV | kT/C uV | sigma LSB | composed ENOB | noise scope |
|---|---|---|---|---|---|---|---|---|---|
| `ff_-40c_2.97v` | 62.06 | -58.11 | 57.07 | 9.187 | 93.3 | 27.0 | 0.0301 | 9.184 | same-corner comparator + same-T kT/C |
| `ff_-40c_3.30v` | 60.75 | -57.68 | 56.35 | 9.069 | 93.6 | 27.0 | 0.0302 | 9.066 | same-corner comparator + same-T kT/C |
| `ff_-40c_3.63v` | 61.38 | -57.83 | 55.83 | 8.982 | 93.8 | 27.0 | 0.0303 | 8.980 | same-corner comparator + same-T kT/C |
| `ff_125c_2.97v` | 60.41 | -58.65 | 57.48 | 9.256 | 151.6 | 35.3 | 0.0483 | 9.247 | same-corner comparator + same-T kT/C |
| `ff_125c_3.30v` | 63.64 | -59.44 | 57.68 | 9.289 | 152.5 | 35.3 | 0.0486 | 9.281 | same-corner comparator + same-T kT/C |
| `ff_125c_3.63v` | 60.48 | -58.68 | 57.48 | 9.255 | 153.2 | 35.3 | 0.0488 | 9.247 | same-corner comparator + same-T kT/C |
| `ff_27c_2.97v` | 62.65 | -58.85 | 57.42 | 9.246 | 115.9 | 30.6 | 0.0372 | 9.241 | same-corner comparator + same-T kT/C |
| `ff_27c_3.30v` | 60.81 | -57.96 | 56.85 | 9.151 | 116.4 | 30.6 | 0.0374 | 9.147 | same-corner comparator + same-T kT/C |
| `ff_27c_3.63v` | 58.96 | -57.65 | 55.94 | 9.000 | 116.8 | 30.6 | 0.0375 | 8.997 | same-corner comparator + same-T kT/C |
| `ss_-40c_2.97v` | 57.96 | -55.51 | 54.35 | 8.735 | 76.9 | 27.0 | 0.0253 | 8.734 | same-corner comparator + same-T kT/C |
| `ss_-40c_3.30v` | 64.71 | -59.24 | 57.15 | 9.201 | 77.6 | 27.0 | 0.0255 | 9.198 | same-corner comparator + same-T kT/C |
| `ss_-40c_3.63v` | 63.48 | -58.20 | 55.58 | 8.939 | 77.9 | 27.0 | 0.0256 | 8.938 | same-corner comparator + same-T kT/C |
| `ss_125c_2.97v` | 61.09 | -56.85 | 55.78 | 8.974 | 124.1 | 35.3 | 0.0400 | 8.970 | same-corner comparator + same-T kT/C |
| `ss_125c_3.30v` | 62.96 | -58.27 | 57.02 | 9.180 | 125.2 | 35.3 | 0.0404 | 9.175 | same-corner comparator + same-T kT/C |
| `ss_125c_3.63v` | 64.08 | -58.40 | 56.74 | 9.132 | 126.0 | 35.3 | 0.0406 | 9.127 | same-corner comparator + same-T kT/C |
| `ss_27c_2.97v` | 59.53 | -56.56 | 55.19 | 8.875 | 94.7 | 30.6 | 0.0309 | 8.873 | same-corner comparator + same-T kT/C |
| `ss_27c_3.30v` | 61.28 | -57.48 | 56.20 | 9.044 | 95.5 | 30.6 | 0.0311 | 9.041 | same-corner comparator + same-T kT/C |
| `ss_27c_3.63v` | 61.63 | -58.26 | 56.86 | 9.152 | 96.0 | 30.6 | 0.0313 | 9.149 | same-corner comparator + same-T kT/C |
| `tt_-40c_2.97v` | 64.37 | -59.65 | 57.00 | 9.175 | 84.0 | 27.0 | 0.0274 | 9.173 | same-corner comparator + same-T kT/C |
| `tt_-40c_3.30v` | 63.27 | -57.52 | 56.09 | 9.025 | 84.5 | 27.0 | 0.0275 | 9.023 | same-corner comparator + same-T kT/C |
| `tt_-40c_3.63v` | 63.08 | -58.31 | 56.95 | 9.169 | 84.7 | 27.0 | 0.0276 | 9.166 | same-corner comparator + same-T kT/C |
| `tt_125c_2.97v` | 62.58 | -58.21 | 56.69 | 9.125 | 135.6 | 35.3 | 0.0435 | 9.120 | same-corner comparator + same-T kT/C |
| `tt_125c_3.30v` | 62.82 | -58.76 | 57.36 | 9.235 | 136.6 | 35.3 | 0.0438 | 9.229 | same-corner comparator + same-T kT/C |
| `tt_125c_3.63v` | 61.47 | -57.55 | 55.10 | 8.860 | 137.3 | 35.3 | 0.0440 | 8.856 | same-corner comparator + same-T kT/C |
| `tt_27c_2.97v` | 65.45 | -61.46 | 58.58 | 9.438 | 103.8 | 30.6 | 0.0336 | 9.433 | same-corner comparator + same-T kT/C |
| `tt_27c_3.30v` | 64.03 | -58.50 | 56.87 | 9.154 | 104.5 | 30.6 | 0.0338 | 9.151 | same-corner comparator + same-T kT/C |
| `tt_27c_3.63v` | 58.75 | -56.60 | 55.65 | 8.952 | 104.9 | 30.6 | 0.0339 | 8.949 | same-corner comparator + same-T kT/C |

SFDR-worst: `ss_-40c_2.97v` 57.96 dB
composed-ENOB-worst: `ss_-40c_2.97v` 8.734 bits

## 5. Temperature summary

| T | points | worst SFDR (dB) | worst distortion-only ENOB | worst composed ENOB | SFDR < 62 dB | composed ENOB <= 9.0 |
|---|---:|---|---|---|---:|---:|
| -40 C | 9 | `ss_-40c_2.97v` 57.96 | `ss_-40c_2.97v` 8.735 | `ss_-40c_2.97v` 8.734 | 3 | 3 |
| 27 C | 9 | `tt_27c_3.63v` 58.75 | `ss_27c_2.97v` 8.875 | `ss_27c_2.97v` 8.873 | 6 | 3 |
| 125 C | 9 | `ff_125c_2.97v` 60.41 | `tt_125c_3.63v` 8.860 | `tt_125c_3.63v` 8.856 | 4 | 2 |
| all | 27 | `ss_-40c_2.97v` 57.96 | `ss_-40c_2.97v` 8.735 | `ss_-40c_2.97v` 8.734 | 13 | 8 |

## 6. Conclusions

1. **Coverage is now established** for the extracted netlist over the full process x temperature x supply grid (27/27). The hot-only limitation in `README.md` is retired for this grid. It still excludes a capacitor corner and the real-V_cm campaign (#392).
2. **Cold is the governing temperature for both rows**: worst SFDR 57.96 dB (`ss_-40c_2.97v`, 4.04 dB short of 62; hot worst 60.41) and worst composed ENOB 8.734 bits (same point; hot worst 8.856). This is the same corner the acquisition-lag mechanism (R_on flatness, `ss_-40c_2.97v`) predicts. The mechanism is consistent with the result; this run does not isolate it.
3. 13 of 27 points are below 62 dB SFDR and 8 of 27 are at or below 9.0 composed ENOB. Both ratified rows remain **FAIL**; verdicts only worsen in margin.
4. Cold noise is lower than hot (comparator 77-94 uV vs 124-153 uV), so the cold ENOB shortfall is a distortion shortfall, as the 2026-10-08 note anticipated.
5. The 64-sample, single-tone FFT is coarse (one bin pair per harmonic); point-to-point SFDR scatter of 1-3 dB between adjacent supplies is within what this capture resolves poorly, and no single-point ranking within a temperature should be over-read.

## 7. Tooling change made for this analysis

`sim/adc-enob-fft/testbench/analyze_fft.py` only matched the local runner's `m_code_sNNN = x` log lines. A `klt sim --backend batch` ngspice log prints the same measure as `sNNN = x` (klt drops the `m_code_` prefix), so the first analysis attempt failed with "log is missing 64 of 64 samples". The sample regex now accepts both forms; the 12 existing `sim/tests/test_analyze_fft.py` tests still pass and the 125 C reproduction in Sec 3 is the cross-check that the new form parses to the same codes.

## 8. Not done / limits

- No capacitor-corner expansion, no real-V_cm run, no target or hardware change, no edit to a historical record or to `spec/`.
- Candidate evaluation (what to do about the cold distortion) is out of scope here; this result is its input.
