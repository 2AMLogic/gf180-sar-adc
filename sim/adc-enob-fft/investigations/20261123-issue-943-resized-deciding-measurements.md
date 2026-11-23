# Issue #943 -- Re-sized class-A/B deciding measurements: the two-tone 256-sample capture (2026-11-23)

- **Date**: 2026-11-23 (UTC); fleet jobs submitted 03:29-03:34 UTC, collected 03:35-03:56 UTC.
- **Base commit**: `fb335590` (main; the #944 merge that put the #935 record and its data dir on `main`).
- **Scope**: the re-sizing the ranking record's Class C1 rule demands after #935's C1 leg failed two of three pass conditions: *"If any leg fails, every class-A/B deciding measurement above is measuring noise and must be re-sized before it is run."* This record re-sizes those measurements, runs the capture that fixes the re-sized protocol's parameters (a **second 256-point tone** on the four governing extracted points, plus a same-tone repeat), decides the 27-point #430 re-take question, and names the first candidate to run. **Evidence only**: no `spec/` file, README row, ratified bound or existing `sim/` record is edited; no candidate is run; the 27-point grid is not re-taken here.
- **Verdict (as measured)**:
  1. **The same-tone repeat is bit-identical.** All four bin-125 re-runs reproduce #935's logs **byte-for-byte** (log SHA-256 equal, SFDR delta 0.00 dB at two decimals) on a different fleet instance two days later. The solver/fleet path is deterministic; same-tone repeats carry no scatter.
  2. **The second tone moves SFDR by +1.85 to +4.64 dB** (mean +2.96 dB) at the same four corners, same N = 256. The tone-to-tone (phase-set) scatter at N = 256 **exceeds** the 1-3 dB band the ranking record (Sec 3.3) quoted for N = 64: more samples did **not** reduce the scatter, because the scatter was never sample-count-limited -- it is tone (phase-set) limited.
  3. **Every ordering inside the band flips with tone.** The lowest-SFDR corner of the four is `ss_-40c` at N = 64 and at bin 115, but `ss_27c` at bin 125. The `ff_125c`-vs-`ss_125c` sign is -0.68 dB (N = 64), +3.22 dB (bin 125), +0.50 dB (bin 115). The 62 dB row **flips pass/fail on tone choice alone** at `ss_125c_2.97v`: 58.59 dB (bin 125, FAIL) vs 63.24 dB (bin 115, PASS).
  4. **The composed-ENOB shortfall is tone-robust at the governing point; its per-corner pattern is not.** Cold `ss_-40c_2.97v` composed ENOB is below the 9.0 row at both tones (8.781 / 8.905); three of four points are below 9.0 at bin 125 (`ff_125c` is 9.114, above it), while two of four clear it at bin 115 (`ss_125c` 9.070, `ff_125c` 9.353); only `ss_125c` crosses the row with tone (8.844 -> 9.070), `ff_125c` passes at both tones and `ss_-40c` / `ss_27c` fail at both.

## 1. What ran

| Leg | Deck (what changed vs. the #430 baseline deck `b281aa8`) | Points | Capture |
|---|---|---|---|
| **c1** (repeat) | #935's C1 deck rebuilt: sole delta the stimulus frequency line, 484375 -> 488281.25 Hz. Deck SHA-256 `541582ac...` -- **equal to #935's recorded C1-ext netlist hash**; the four emitted requests are **byte-identical** to `20261121-issue-935-data/requests/c1-*.json` (verified with `cmp`) | `ss` x {-40, 27, 125} C and `ff` 125 C, all 2.97 V (4) | N = 256, **bin 125** |
| **t115** (second tone) | same base deck, sole delta the same one frequency line, 484375 -> **449218.75 Hz** (deck SHA-256 `7e209f47...`) | same four points (4) | N = 256, **bin 115** |

8 points, all **completed**; every log carries all 256 codes (checked by `analyze_fft.extract_codes`, which raises on a missing sample).

**Why bin 115 as the second tone.** The re-sized protocol needs "more samples" separated from "different phase set". Bin 115 is odd, `gcd(115, 256) = 1` (115 = 5 x 23, 256 = 2^8), so the 256 samples land on 256 distinct phases with `window = none` still valid, exactly like bin 125. Its **harmonic bins** `h x 115 mod 256` (h = 2..12: 230, 89, 204, 63, 178, 37, 152, 11, 126, 241, 100 and mirrors) are **disjoint from bin 125's** (250, 119, 244, 113, 238, 107, 232, 101, 226, 95, 220 and mirrors), checked through the 12th harmonic inclusive. Against the N = 64 tone's 256-point equivalent bin 124 (248, 116, 240, 108, 232, 100, 224, 92, 216, 84, 208) there is **one** overlap through the 12th harmonic: bin 100 (115's 12th, 124's 7th). It is the highest harmonic order checked, so it is not expected to dominate the comparison, but it is not disjoint and the N = 64 -> bin 115 comparison column carries it -- so the two tones' SFDR figures read *different* aliased distortion products instead of re-reading the same ones, and a tone-to-tone difference measures phase-set scatter rather than analyzer aliasing. Bin 115 = 449218.75 Hz sits 39 kHz below bin 125's 488281.25 Hz, inside the same input band (the original N = 64 tone was 484.375 kHz). The neighbouring odd bins are excluded for cause: 127's 3rd harmonic lands on bin 125's fundamental bin and its 6th on 125's 2nd; 123's 3rd lands on 125's 5th (113); 121's 3rd on 125's 7th (107); 117's 3rd on 125's 11th (95). Bins above 127 are above Nyquist.

Amplitude (`vref/2 * 0.94`), initial phase (0), 2 us stimulus delay, 1 us sample pitch, first-sample time and the transient (`tran 1n 258.000u 0 2n`) are unchanged from the baseline; the coverage-witness windows extend through sample 255.

## 2. Provenance

| Item | Value |
|---|---|
| Baseline deck / manifest | recovered from git `b281aa8` by `setup_variants.py`, SHA-256 `b0baf132...` / `4be757c3...` -- both asserted equal to the hashes the #935 record states (script refuses on mismatch) |
| c1 netlist | `541582aca616e78eed76cc20ae65bbf2ba9168c2ba97d7451c7f652c02ceda97` = #935's C1-ext netlist (the bin-125 leg is the same measurement, re-run) |
| t115 netlist | `7e209f47060d3893af748cf0f8c9e06f94c3af5909e0a2bdc708d901263fb646` = the same parent with the one frequency line changed |
| Requests | the four c1 requests are **byte-identical** to #935's committed `requests/c1-*.json` (`cmp`, all four); the four t115 requests are the same builder at bin 115 (`build_requests.py`, sorted-key serialization) |
| Submitted bodies | local body SHA-256 c1 `f8b6dec6...`, t115 `96e82560...`; these are the harness-composed bodies with **this host's** PDK include path -- klt rewrites the PDK include to the runner's `$PDK_ROOT` at submit, so the uploaded bytes differ from #935's only there (and in the request-normalization of the newer client, hence different `request_sha256` than #935's jobs) |
| Model library | `libs.tech/ngspice/sm141064.ngspice`, SHA-256 `f6f4a96e18fc5ad11270ad3451aaecc7ac37fc81eb61e15b0d7d94c7bc594a24` (runner stamp; equals #430's and #935's) |
| PDK | gf180mcuD, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` -- fetched to this worktree's git-ignored scratch with ciel at the repo pin; the runner image's copy is what ran |
| Backend | `klt sim --backend batch --submit-only --wait-for-capacity 600`, one request (one corner unit) per job, `timeout_s` 3300, collected with `--attach`; runner klt 0.9.0, client klt `0.9.3.dev3692+g719ab7426e77`, **ngspice 47** on the runner (as #935; the #430 baseline ran 46), c7i.4xlarge Spot, 8/8 jobs, runtimes 1138-1331 s |
| Job ids | per point in Sec 3 and in `20261123-issue-943-data/points.json` (with request SHA-256, runtime, log SHA-256) |
| Raw evidence | `20261123-issue-943-data/logs/<leg>/<corner-id>.log` (git-ignored per #636). **The artifact broker refused this host** (`klt artifact put` -> HTTP 403 `unknown_caller: this tailnet identity is not listed in the artifact-broker roster`), so no manifest was written; the full per-log SHA-256s in `points.json` pin the bytes, and storing them from a rostered identity is the open follow-up. The four c1 logs are byte-identical to objects already in the store under #935's manifest (`adc-enob-fft-20261121-issue-935.manifest.json`) |
| Re-run | `setup_variants.py` -> `build_requests.py` -> submit/attach as in `build_requests.py`'s header -> `collate.py` (re-run this session; reproduces the 8 points) |

klt status is `error` (exit 4) for all 8 jobs, **solely** the known runner gap #935 documented: the manifest's eight `decerr_c*_lsb` `expr` measurements produce no value on the 0.9.0 runner (`expr_runner_may_predate`); the only diagnostics in every report are those 8 `measurement` entries. Every `sNNN` sample printed; the FFT reads only the `sNNN` lines. No point carries the gmin-stepping warning (consistent with the flagged set: none of these four corners is in it).

## 3. Results -- extracted, 2.97 V, the four governing points

SFDR from `analyze_fft.py --n 256 --bin {125,115}`; composed ENOB with the same-corner comparator noise record and same-temperature kT/C that `compose_enob_by_corner.py` uses (C_side 8.827 pF), as in #935.

| leg | corner-id | N/bin | SFDR dB | composed ENOB | #935 bin125 | delta | #430 N=64 | delta | job id |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| c1 | `ss_-40c_2.97v` | 256/125 | 58.62 | 8.781 | 58.62 | **+0.00** | 57.96 | +0.66 | `klt-sim-1b1f8ae33aaf` |
| c1 | `ss_27c_2.97v` | 256/125 | 57.13 | 8.560 | 57.13 | **+0.00** | 59.53 | -2.40 | `klt-sim-467f46313667` |
| c1 | `ss_125c_2.97v` | 256/125 | 58.59 | 8.844 | 58.59 | **+0.00** | 61.09 | -2.50 | `klt-sim-6cf3ee9ecddc` |
| c1 | `ff_125c_2.97v` | 256/125 | 61.81 | 9.114 | 61.81 | **+0.00** | 60.41 | +1.40 | `klt-sim-e561c884cfdd` |
| t115 | `ss_-40c_2.97v` | 256/115 | 60.46 | 8.905 | 58.62 | **+1.85** | 57.96 | +2.50 | `klt-sim-e36287dd6a49` |
| t115 | `ss_27c_2.97v` | 256/115 | 60.55 | 8.936 | 57.13 | **+3.42** | 59.53 | +1.02 | `klt-sim-015f677e6091` |
| t115 | `ss_125c_2.97v` | 256/115 | 63.24 | 9.070 | 58.59 | **+4.64** | 61.09 | +2.15 | `klt-sim-9ef78987d5f8` |
| t115 | `ff_125c_2.97v` | 256/115 | 63.74 | 9.353 | 61.81 | **+1.93** | 60.41 | +3.33 | `klt-sim-ce88dc57614d` |

THD / distortion-only ENOB / full provenance columns are in `20261123-issue-943-data/points.{json,md}`.

## 4. The scatter figure

- **Repeat (same tone, same request bytes): 0.00 dB** on all four corners -- and stronger than that: the four c1 logs are **byte-identical** to #935's (`log_sha256` equal; the same objects already in the #935 manifest). This extends the 2026-11-08 N = 64 bit-identical repeat (ranking record Sec 3.3) to N = 256 and across fleet instances and days: the measurement pipeline has no run-to-run noise; all observed scatter is **capture-parameter** scatter.
- **Tone-to-tone at N = 256 (bin 115 minus bin 125): +1.85, +1.93, +3.42, +4.64 dB** (mean +2.96, all four positive at this pair). For comparison, the N = 64 -> N = 256 move (#430 -> bin 125) was -2.50 .. +1.40 dB: **inside** the tone band. "More samples" and "different phase set" are now separable, and the answer is that the N-dependence #935 measured is itself mostly phase-set dependence.
- **Consequences for orderings** (all three captures, same four corners):

| ordering question | N = 64, bin 31 (#430) | N = 256, bin 125 (#935 + repeat) | N = 256, bin 115 (this record) |
|---|---|---|---|
| lowest-SFDR corner of the four | `ss_-40c` (57.96) | `ss_27c` (57.13) | `ss_-40c` (60.46; `ss_27c` 0.09 dB above) |
| `ff_125c` - `ss_125c` | -0.68 dB | +3.22 dB | +0.50 dB |
| `ss_125c` vs the 62 dB row | 61.09 (pass) | 58.59 (**fail**) | 63.24 (pass) |
| cold composed ENOB vs 9.0 | 8.734 (fail) | 8.781 (fail) | 8.905 (fail) |

  Readings, without extending them: "cold governs" is tone-dependent (it is false at bin 125, true-but-by-0.09-dB at bin 115); the ff-vs-ss flip #935 measured is not a stable N = 256 property either (its sign holds at both 256-point tones but its magnitude swings 3.22 -> 0.50 dB, i.e. across zero-ish); a pass/fail on the 62 dB row is a coin-toss on tone at `ss_125c`. The composed-ENOB shortfall against 9.0 is tone-robust at the cold governing point and at `ss_27c` (below the row at both tones); only `ss_125c` crosses the row with tone (`ff_125c` is above it at both tones, 9.114 / 9.353).

## 5. The re-sized class-A/B deciding measurements

Per the ranking record Sec 4's rule, every spectral (FFT-read) deciding measurement in its Class A/B list is re-sized as follows; layout legs and non-spectral probes are untouched.

**Capture protocol (the re-sizing).** N = 256 on the extracted netlist, **tone set {bin 125, bin 115}** -- the two tones this record measured out to be necessary and sufficient to expose the scatter -- with:

- the per-corner figure reported as **min over the tone set** (the design-margin reading; the per-tone values and their spread travel with it), and
- a **resolution rule**: an ordering or pass/fail verdict is only claimed when it clears the measured tone band at the governing point (here +1.85..+4.64 dB; re-measured wherever the protocol runs). A verdict inside the band is recorded as **"unresolved by capture"**, not as pass or fail.

N = 512 is **not** indicated: both 256-point tones already sample 256 distinct phases and the repeat is bit-identical, so the scatter is not sample-count-limited; only the tone set bounds it. The cost of the protocol is 2 fleet jobs per corner (one corner per job, `timeout_s >= 3300`, ~19-22 min and up to 18.7 GB RSS each at -40 C).

**A2(i)** (extracted, full-temperature width FFT at 1.5x and 1.75x; the ranking's first-class deciding measurement): re-sized to **2 widths x 9 points at 2.97 V x 2 tones = 36 extracted corner-jobs (~12.6 fleet-hours)**, or 2 widths x 27 points x 2 tones = 108 (~37.5 h) at the full 27-point grid. Pass condition, unchanged in substance and now tone-aware: worst composed ENOB `> 9.0` **and** worst SFDR `>= 62 dB` at `ss_-40c_2.97v`, each evaluated as the min over the tone set, with the resolution rule above. **Not to be run at N = 64 / bin 31 / single tone** -- that is the regime this record just measured as unresolved.

**A2(ii)** (layout candidate + DRC/LVS) and **A3** (folded `Xsi` + DRC/LVS): no capture; no spectral figure; **unaffected and unblocked** by this re-sizing.

**B1** (bootstrap reliability gate: peak terminal-to-terminal voltage on every boost-network device, schematic, `ff_-40c_3.63v` + `ff_125c_3.63v`): a peak-voltage measurement, not an FFT figure -- **capture-size independent, unblocked**. What is scatter-limited is B1's *distortion payoff*, which this re-sizing does not change the disposition of.

**A1, B2, B3, A4**: dispositions unchanged (dominated / spec-decision-first / row-trading / out of scope); no re-sized measurement needed.

## 6. First candidate to run

**A2(i), re-sized as above -- confirmed first.** The #800 ranking (Sec 5) listed A2 first among the design candidates with C1 as the gate; C1 is now retired (this record), and the new scatter figure re-sizes A2's measurement rather than reordering the candidate list: A1 remains dominated, B2 needs a spec decision first, B3 trades one failing row for another and still misses the floor, A3 is the layout fallback that A2(ii)'s outcome informs, and B1's probe is unblocked but is a feasibility gate, not a distortion fix. Nothing in today's data promotes another class-A/B candidate above A2. Two things run **in parallel, unaffected by the scatter question**: A2(ii) (the layout/area leg) and, if the operator wants the class-B option probed, B1's terminal-voltage measurement. Explicitly, and per the issue: **A2 is not to be run at N = 64**, and #935's reason for not selecting it (a single-tone sign flip) is superseded by the protocol here -- under the two-tone protocol the 1.75x-vs-2.068x ordering is simply *unresolved until re-measured*, which is what A2(i) re-sized does for the widths it covers.

## 7. The 27-point #430 re-take decision

**Decision: yes -- the 27-point grid is re-taken at the re-sized capture (N = 256, tone set {125, 115}) before it is trusted as the baseline for #867/#886.** The measured scatter behind it:

- the per-corner structure the ranking record consumed (its Sec 3.3/3.4 "1-3 dB" consumptions) sits **inside** the measured tone band (+1.85..+4.64 dB at the four governing points);
- a ratified-row verdict (62 dB at `ss_125c_2.97v`) **flips with tone alone**;
- the N = 64 -> N = 256 deltas (-2.50..+1.40 dB) are inside the band, so the existing grid cannot be "upgraded" by a single-tone N = 256 re-run either -- bin 115 differs from bin 125 by more than bin 125 differs from N = 64.

Sized cost: 23 remaining points x 2 tones = **46 extracted corner-jobs (~16 fleet-hours)**; the four governing points are already done in both tones (#935's bin-125 x 4, re-confirmed bit-identical here, + this record's bin-115 x 4). Not run in this issue -- the issue owns the decision and its evidence, not the re-take.

## 8. Not done / limits

- One tone **pair**, on the **four 2.97 V governing points**, extracted only. The other 23 grid points, the width legs and the non-2.97 V sets were not re-captured (Sec 7 sizes that). Whether a third tone narrows the band further is unmeasured; the protocol accepts the two-tone band as the resolution limit and says so with every verdict.
- The two tones differ in frequency (449.2 vs 488.3 kHz) as well as phase set -- inherent to a coherent-bin change; the band therefore bounds "tone choice near this band", not a pure phase measure.
- No decoder-error (`decerr_*`) columns (the runner `expr` gap above); no coverage-witness verdicts; the `error`/exit-4 status is that gap only.
- ngspice 47 on the runner vs 46 for the #430 baseline; #935's C2 reproduction at 0.00 dB remains the only direct evidence that this difference is immaterial.
- The artifact-broker refusal (Sec 2) leaves the 8 raw logs unstored from this host; `points.json` carries their full SHA-256s.
- `analyze_fft.py` requires explicit `--n 256 --bin 125|--bin 115` (it defaults to 64/31); `collate.py` passes them per leg.

## Reproducing this record

```
export PDK_ROOT=<pdk-root with gf180mcuD at open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7>
python3 sim/adc-enob-fft/investigations/20261123-issue-943-data/setup_variants.py
python3 sim/adc-enob-fft/investigations/20261123-issue-943-data/build_requests.py
cmp sim/.work/issue-943/req/t125/c1-ss--40c-2p97v.json \
    sim/adc-enob-fft/investigations/20261121-issue-935-data/requests/c1-ss--40c-2p97v.json
# submit + attach per build_requests.py's header, then:
python3 sim/adc-enob-fft/investigations/20261123-issue-943-data/collate.py
```

`collate.py` re-reads the collected `out/` tree and the committed `20261121-issue-935-data/points.json` and regenerates `points.{json,md}`; the tables in Sec 3/4 are its output.
