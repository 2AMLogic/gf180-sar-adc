# Issue #935 -- C1 (256-sample capture) and C2 (solver tightening) deciding measurements (2026-11-21)

- **Date**: 2026-11-21 (UTC); tool gap filed as 2AMLogic/klayout-tools#7036; fleet jobs submitted 2026-11-21 03:15-03:55 UTC.
- **Base commit**: `ccac27a2` (main). Baseline record: [`records/20261105-125230-b281aa8.md`](../records/20261105-125230-b281aa8.md) (#430).
- **Scope**: the compute-only C1 + C2 measurements that [`20261114-issue-800-cold-distortion-candidate-ranking.md`](20261114-issue-800-cold-distortion-candidate-ranking.md) Sec 4 / Sec 5 ranked first. **Candidate / diagnostic outputs, not campaign records.** No `spec/` file, README row, ratified bound or existing `sim/` record is edited; #867/#886 still own the re-minted evidence.
- **Verdict (as found)**: C1 pass conditions **1 of 3 hold**. The cold `ss_-40c_2.97v` SFDR reproduces within 1.0 dB (+0.66 dB). The `ff_125c < ss_125c` ordering **fails** (flips by +3.22 dB), and the 1.75x-vs-2.068x ordering **flips sign** (+2.22 dB at N = 64, -0.95 dB at N = 256). C2: **4 of 4 points reproduce at 0.00 dB**. By the ranking record's own rule, the class-A/B deciding measurements are re-sized in Sec 6; follow-up issue linked there.

## 1. What ran

| Leg | Deck (what changed vs. the baseline) | Points | Capture |
|---|---|---|---|
| **C1-ext** | baseline-record extracted deck (`b281aa8`), **sole delta: the stimulus frequency line**, 484375 -> 488281.25 Hz | `ss` x {-40, 27, 125} C and `ff` 125 C, all 2.97 V (4) | N = 256, bin 125 |
| **C2** | baseline-record extracted deck **byte-for-byte**, plus `options.ngspice_options` | `tt`/`ff` x {-40, 27} C, 2.97 V (4) | N = 64, bin 31 (unchanged) |
| **C1-width** | schematic deck from `dr0019-cu-sweep/gen_cu_variant.py` at ratified `C_u` = 35.6528 fF, acquisition-leg x1.5 / x1.75 / x2.068, same re-toning | #429's nine 125 C corners (tt/ss/ff x 2.97/3.30/3.63 V) per width (27) | N = 256, bin 125 |

35 points, all **completed**; none missing, no sample missing (every log carries all 256 / 64 codes, checked by `analyze_fft.extract_codes`).

**Tone and coherence (C1).** Bin 125 at 1 MS/s = 488.28125 kHz, one 256-point bin above the original 484.375 kHz (bin 31 of 64 = bin 124 of 256). Bin 124 would repeat the 64 original phases four times; 125 is odd, so gcd(125, 256) = 1 and the 256 samples land on 256 distinct phases with `window = none` still valid. Amplitude (`vref/2 * 0.94`), initial phase, 2 us delay, 1 us sample pitch and the first-sample time are unchanged; the transient (`tran 1n 258.000u 0 2n`) and the coverage-witness windows extend through sample 255 (257950 ns).

**Solver options (C2).** `options.ngspice_options` = `reltol=1e-4 abstol=1e-13 vntol=1e-8 gminsteps=200 srcsteps=200 itl4=100`. Baseline = ngspice defaults (`reltol=1e-3 abstol=1e-12 vntol=1e-6 itl4=10`, `gminsteps`/`srcsteps` at their defaults). The runner echoed the map back in `environment.ngspice_options` for all four jobs and each `corner.cir` carries the `.options` card. (The first draft of this leg spelled the names `gmin_steps`/`src_steps`, which ngspice silently ignores; klt's allow-list names are `gminsteps`/`srcsteps` and the submitted requests use those.)

## 2. Provenance

| Item | Value |
|---|---|
| Baseline deck recovered from git | `git show b281aa8:sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice`, SHA-256 `b0baf1325167d110677bf5f5d8ce4156c8b138ba9d6c9f64fe1846ef5c04ef75` -- **equal to the hash record `20261105-125230-b281aa8` states** (asserted by `setup_variants.py`) |
| Baseline manifest | `git show b281aa8:sim/adc-enob-fft/testbench/tb.json`, SHA-256 `4be757c33797e8bc5d6553c2e5a8239d806382e5d2ca2729af34bc3042677961` (equal) |
| Current committed deck | SHA-256 `725bf7d9...` -- **differs** from the baseline (regenerated after #836/#837); it was not used |
| C2 netlist, extracted legs | parent deck bytes verbatim (`tb_extracted_c2.spice` = `b0baf132...`); **byte-identical to the baseline record's deck** |
| C1-ext netlist | `tb_extracted256.spice`, SHA-256 `541582aca616e78eed76cc20ae65bbf2ba9168c2ba97d7451c7f652c02ceda97` = parent with the one frequency line changed; **not** byte-identical to the baseline (by design -- the tone is the C1 variable) |
| Submitted body (what klt `.include`s) | C1: `5eaee96d3f59c6244f7a1e49736e14fc0592cd57a38cd8270109ac03fba99fe1`; C2: `1c9fad6c1562c2569f3f1677acf1cb2c192ccaa61a09c254aa9d55a7a8a3b35b` (harness-composed from the deck above, `.param vdd_val=2.97`); width bodies are in `points.json` |
| Model library | `libs.tech/ngspice/sm141064.ngspice`, SHA-256 `f6f4a96e18fc5ad11270ad3451aaecc7ac37fc81eb61e15b0d7d94c7bc594a24` (equals #430's) |
| PDK | gf180mcuD, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (runner stamp `4ca10280...`, comparison `match`) |
| Backend | `klt sim --backend batch --submit-only --wait-for-capacity 600`, one request (one corner unit) per job, collected with `--attach`; runner klt 0.9.0 (`runner_compatibility: match`), client klt `0.9.3.dev2575+g6bd18bbc8637`, **ngspice 47** on the runner (the baseline ran ngspice 46), c7i/m7i.4xlarge Spot |
| Job ids | per point in the tables below and in `20261121-issue-935-data/points.md` / `points.json` (with request SHA-256, runtime) |
| Raw evidence | `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/<leg>/<corner-id>.log` (stored, not in git; manifest `manifests/artifacts/adc-enob-fft-20261121-issue-935.manifest.json`), `requests/*.json`, `jobs/*.submit.json` |
| Re-run | `setup_variants.py` -> `build_requests.py` -> submit/attach as in `build_requests.py`'s header -> `collate.py`. `build_requests.py` was re-run after collection and reproduces all 17 submitted request/body pairs byte-for-byte |

klt status for the C1 and width jobs is `error` (exit 4), **solely** because the manifest's eight `decerr_c*_lsb` `expr` measurements produced no value on the 0.9.0 runner (klt diagnostic `expr_runner_may_predate`; runner klt 0.9.0 returned no value for them). Every `sNNN` sample, `cmax`/`cmin` and `vref` measure printed, and the FFT reads only the `sNNN` lines. These points therefore carry **no decoder-error columns and no coverage-witness verdict**; they are not capture-validity-graded like a campaign record. C2's four jobs report `pass`.

Runtime: one 256-sample extracted corner took 1144-1253 s on the fleet (peak RSS 18.7 GB on the `-40 C` point), against 611-625 s for the same corner at N = 64; each 256-sample schematic width job (3 corners) took 591-682 s. A per-corner `timeout_s` of 1100 s (the first attempt, by an earlier builder session on this issue) killed the extracted corners before they finished; 3300 s was used here.

## 3. C1 -- extracted, 2.97 V (N = 256, bin 125) vs #430 (N = 64, bin 31)

SFDR from `analyze_fft.py --n 256 --bin 125`; composed ENOB with the same-corner comparator noise record and same-temperature kT/C that `compose_enob_by_corner.py` uses (C_side 8.827 pF).

| corner-id | job id | SFDR dB (N=256) | SFDR dB (#430, N=64) | delta dB | composed ENOB (N=256) | composed ENOB (#430) |
|---|---|---:|---:|---:|---:|---:|
| `ss_-40c_2.97v` | `klt-sim-10cafe5f18e9` | 58.62 | 57.96 | **+0.66** | 8.781 | 8.734 |
| `ss_27c_2.97v` | `klt-sim-651bbdd67e9b` | 57.13 | 59.53 | -2.40 | 8.560 | 8.873 |
| `ss_125c_2.97v` | `klt-sim-0c53a86e779e` | 58.59 | 61.09 | -2.50 | 8.844 | 8.970 |
| `ff_125c_2.97v` | `klt-sim-d37b2c6bd689` | 61.81 | 60.41 | +1.40 | 9.114 | 9.247 |

| Pass condition (ranking record Sec 4, C1) | Measured | Verdict |
|---|---|---|
| `ss_-40c_2.97v` SFDR within 1.0 dB of 57.96 dB | 58.62 dB, +0.66 dB | **PASS** |
| `ff_125c_2.97v` stays below `ss_125c_2.97v` | 61.81 dB vs 58.59 dB: ff - ss = **+3.22 dB** (N = 64: -0.68 dB) | **FAIL** |
| 1.75x-vs-2.068x sign stable | see Sec 4 | **FAIL** |

Reading, without extending it: at N = 256 three of the four extracted points moved by 1.4-2.5 dB, which is the 1-3 dB scatter band the ranking record (Sec 3.3) said the 64-sample figures sit inside. Two of the three `ss` points move in the *same* direction (down) and the ordering of the four points changes: the lowest SFDR of the four is now `ss_27c_2.97v` (57.13 dB), not the cold point. "Cold governs" in #430 therefore rests on a capture whose ordering did not survive a change of N and bin. This measurement does **not** say which N is closer to the converter's true SFDR (a different 256-point bin is a different phase set as well as more samples; the two are not separable here), and it does **not** show the ENOB gap moved: the cold composed ENOB (8.781) is still below the 9.0 row. It is one point per corner at one extra tone; it does not replace the #430 record.

## 4. C1 -- acquisition-leg width ordering (schematic, 125 C, nine corners per width, N = 256)

Full per-corner values are in `20261121-issue-935-data/points.md`. All three widths' minimum falls at `ss_125c_2.97v` (as at N = 64 in #429).

| acquisition-leg width | min SFDR dB at N=256 | at | min SFDR dB at N=64 (#429) | delta dB | composed ENOB at that corner, N=256 | #429 worst composed ENOB |
|---|---:|---|---:|---:|---:|---:|
| x1.5 | 59.13 | `ss_125c_2.97v` | 60.58 | -1.45 | 8.949 | 9.041 |
| x1.75 | 60.82 | `ss_125c_2.97v` | 63.02 | -2.20 | 9.101 | 9.240 |
| x2.068 | **61.77** | `ss_125c_2.97v` | 60.80 | +0.97 | 9.211 | 9.170 |

- 1.75x minus 2.068x: **-0.95 dB** at N = 256 versus **+2.22 dB** at N = 64. **The sign flipped; the "1.75x beats 2.068x" finding of #429 / the ranking record Sec 3.1 does not survive N = 256 at this tone.** At N = 256 the series is monotonic in width (59.13 < 60.82 < 61.77); the ranking record's non-monotonicity (Sec 3.3) is not reproduced.
- No width reaches the 62 dB row's hot minimum at 2.97 V (best 61.77 dB at x2.068, 0.23 dB short). This is a schematic, 125 C measurement and says nothing about the extracted cold point.
- The `ff` columns at the wider widths sit 4-10 dB above the same width's `ss` (see `points.md`); the width legs do not test the extracted `ff`-vs-`ss` ordering, which is Sec 3's single extracted data point.

| Pass condition | Verdict |
|---|---|
| 1.75x-vs-2.068x sign is stable | **FAIL** (+2.22 dB -> -0.95 dB) |

## 5. C2 -- tightened solver on the four gmin-warning points (N = 64, bin 31, extracted)

| corner-id | job id | SFDR dB tightened | SFDR dB #430 | delta dB | gmin stepping failed (this run) | klt status |
|---|---|---:|---:|---:|---|---|
| `tt_-40c_2.97v` | `klt-sim-3f83c38f3430` | 64.37 | 64.37 | 0.00 | yes (`spice3 gmin stepping failed`, then source stepping) | pass |
| `tt_27c_2.97v` | `klt-sim-59c5621b094f` | 65.45 | 65.45 | 0.00 | yes | pass |
| `ff_-40c_2.97v` | `klt-sim-f81186646733` | 62.06 | 62.06 | 0.00 | yes | pass |
| `ff_27c_2.97v` | `klt-sim-8560595a6239` | 62.65 | 62.65 | 0.00 | yes | pass |

| Pass condition | Verdict |
|---|---|
| each C2 point reproduces within 1.0 dB | **PASS** (4 of 4, deltas 0.00 dB at two decimals) |

Reading: the tightened `.options` did not make the DC operating-point gmin stepping succeed (the warning persists in all four logs; source stepping recovers the point, as in the baseline), and the recovered operating point does not move the distortion figure. The result also incidentally reproduces #430's four SFDR values to two decimals on ngspice 47 (the baseline ran 46), so this runner change did not perturb them. It does not show *why* gmin stepping fails, and it does not test other solver settings or the two non-2.97 V sets that also carry the warning.

## 6. Consequence and follow-up

Per ranking record Sec 4 (C1): "If any leg fails, every class-A/B deciding measurement above is measuring noise and must be re-sized before it is run." Two of three C1 conditions failed, so the class-A/B deciding measurements (A2 at 1.75x / 1.5x, and the rest of Sec 4's class-A/B list) are **not** to be run at N = 64 / bin 31; the re-sizing, and the first candidate to run after it, are filed as #943 so the ENOB/SFDR rows keep an owner. Because the 1.75x-vs-2.068x ordering at schematic level has flipped, A2 is not selected here.

## 7. Not done / limits

- 4 extracted points at one extra tone (bin 125); the other 23 points of the 27-point grid were not re-captured. A second 256-point tone (e.g. another odd bin) would separate "more samples" from "different phase set"; not run, as the issue scopes C1 to the single re-derived bin.
- Extracted legs ran at 2.97 V only; the width legs are schematic and 125 C only.
- No decoder-error (`decerr_*`) columns or coverage-witness verdicts for the C1/width legs (runner `expr` gap above). The C2 `pass` verdict is klt's capture-validity status only.
- ngspice 47 on the runner vs 46 for the baseline; the C2 reproduction at 0.00 dB is the only direct evidence that this difference is immaterial, and only for those four points.
- `analyze_fft.py` requires explicit `--n 256 --bin 125` (it defaults to 64/31); `collate.py` passes them.

## Stored evidence

The bytes of this run are in the fleet artifact store, not in git (issue #636). Manifest: `manifests/artifacts/adc-enob-fft-20261121-issue-935.manifest.json` (35 objects, 2059335 B). Paths above are the manifest `name`s. Fetch one, hash-verified, with:

```
klt artifact get manifests/artifacts/adc-enob-fft-20261121-issue-935.manifest.json#<name> -o <out>
python3 scripts/check_artifact_manifests.py verify manifests/artifacts/adc-enob-fft-20261121-issue-935.manifest.json
```

| name | size (B) | sha256 |
|---|---:|---|
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c1/ff_125c_2.97v.log` | 176881 | `72adb625c20d1277115ebff34d99b43715406e22dd8bf8cadb15848f5262a2bd` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c1/ss_-40c_2.97v.log` | 176881 | `c23834021f7b9ac55faee7608e928fca2cb51b2a6a2825c9cbd893d708e933e0` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c1/ss_125c_2.97v.log` | 176881 | `0e02aadaa6e5ffc13884f0aa562257c4add01c89d0bd5dfdeefd1c31ef57be5b` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c1/ss_27c_2.97v.log` | 176880 | `4f67a7fa8505f962e376b3a7937f195cd8bd9087e0d490531f3e905d4f3705da` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c2/ff_-40c_2.97v.log` | 169201 | `0dfd71f0b70235e024e49ab93d584707c273104ff29c6b2533f880d455de8a31` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c2/ff_27c_2.97v.log` | 169300 | `aa4c7582a0f13ab6e0f768155e8c80d82493b5412b1a0a1fa9d3accee8c0136b` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c2/tt_-40c_2.97v.log` | 169201 | `6906d124b3ef91a75394c041b262d14c87114b05c8351ea1a946e796f776ab2c` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/c2/tt_27c_2.97v.log` | 169200 | `cdd2b010989ddd67fedd34d1fff17263e550fa21fe1e7e2a459de0c5c848b4d0` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/ff_125c_2.97v.log` | 25005 | `f5fdee452a49c91f3d23fd44eb1858c3d16273e53d15ddc4acdc03d28eed94a6` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/ff_125c_3.30v.log` | 25005 | `d9cbad9a1ba03e3385e1ac70d7bc183880dc83c257a5a2f2aa047459401d9454` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/ff_125c_3.63v.log` | 25005 | `9babf346450e92659baedb562c088818ea311631b05a8965887e60e456493d13` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/ss_125c_2.97v.log` | 25005 | `951e747614b1644ff71d8f7bb38e7a84717e4cbb1b26a48db76d755f005d2fc6` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/ss_125c_3.30v.log` | 25005 | `6a42381d24bdb147f1e7135d2fea2bc9a482279caa57f77aac6ec8f6f4108054` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/ss_125c_3.63v.log` | 24930 | `a6fe06dc344ed3026cdb0aebb89e49174d7514b85e1d3ad37a359c14766b6026` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/tt_125c_2.97v.log` | 25005 | `18f8dc8b907531c0536c95f86f1a65358fef5a0639466bdfde80d43b41fc32cf` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/tt_125c_3.30v.log` | 25005 | `4bdd1e12658f7eccfe862391e6e567f9f74ad5cd87a6d0f7d6265d957d28c8bf` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w15/tt_125c_3.63v.log` | 25005 | `3c7c0d6b3169916ade854c6626b551e90a38cf4eddaed76b48f3347e861ac30e` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/ff_125c_2.97v.log` | 25005 | `2888af0b64a92da90d3d8543e62446f742f9ebad4dacc9b6f9f6f418009f1828` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/ff_125c_3.30v.log` | 25005 | `f78a973fc22cfa0b880149931acb7770d25a41af8fa0018fb1d2c951b2f4766e` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/ff_125c_3.63v.log` | 25005 | `9d58fa50edb2427ff2efbeb42911579085a111892acd4921f1ed28739485f7ac` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/ss_125c_2.97v.log` | 25005 | `f75bbf4bcb447ea37e7d2b30127f5c7954b581ba5a81c700cca0a399dd3462a5` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/ss_125c_3.30v.log` | 25005 | `665b53cb5ce996ca65ff62159a694850140b81c44b7d0e5a8e31bc0160b6bb86` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/ss_125c_3.63v.log` | 24930 | `ee9c76526e8411c53f58637b2817e02a1272778f43b40f1d85856fe62b90ee1c` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/tt_125c_2.97v.log` | 25005 | `64b5119036e1ee662cb28e67c803f495f328ead3e948fa518753630d848898d1` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/tt_125c_3.30v.log` | 25005 | `eec5e9c9e8b93e0a7e59ae31958f64aeab65fb4e1bf35939dba4aaf81039bf04` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w175/tt_125c_3.63v.log` | 25005 | `93bc070ba871a603916a688de3b53cb7565b8ca5497955c322de778c859f34c0` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/ff_125c_2.97v.log` | 25005 | `01dec33ea969e4c088ede44e5c2e6dd42b79dd53ea462405550dd5d933b3c793` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/ff_125c_3.30v.log` | 25005 | `d934e37da06e417017f55da0bd717317ff3ffe4a0936befcd75379790e39b0a8` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/ff_125c_3.63v.log` | 25005 | `dec49c874899e542ee8f0ccd785d52438bb0065db61e01ccdb7380a3978a584b` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/ss_125c_2.97v.log` | 25005 | `e8e3009d2283455ab627554e49462cd59fc4c4c599fc61e8f3f7b64ac1856b4f` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/ss_125c_3.30v.log` | 25005 | `7a136476ea09af1f5f452271572fed175d7a2445fd232b7f79288f97dea5f1ba` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/ss_125c_3.63v.log` | 24930 | `da19f62cff7026f7f6711f72a9e7610d9ecd7793456e3920e19a0a46001f1423` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/tt_125c_2.97v.log` | 25005 | `76fbe3e023f83df039eb583425e9bfdae36bec87badc610b1a376293e6961327` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/tt_125c_3.30v.log` | 25005 | `6ce27a0329a3128b8014152a7c5352433636ad40960da2a2112aca08b3d027ab` |
| `sim/adc-enob-fft/investigations/20261121-issue-935-data/logs/w2068/tt_125c_3.63v.log` | 25005 | `345634f531fc07982d96532f64fa3fb36745d0cffa2b4768c7fbf97cff1b7982` |
