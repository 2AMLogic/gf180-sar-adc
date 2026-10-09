# ADC_BLOCK offset Monte Carlo: batch-path qualification (issue #427)

**Status of the ratified row: unchanged.** README.md target specification
"Offset error <= 2 LSB untrimmed (3-sigma mismatch)" stays **Unmeasured**.
This directory qualifies a *measurement path*. It contains a small pilot, not
a population, and nothing here is a pass/fail verdict on the spec. The pilot
spread must not be translated into a spec verdict (section 6 says why and says
what a verdict needs).

Outcome delivered: **(a) a reproducible off-host batch pilot**, with the
limitations in section 7 stated up front rather than buried: the pilot ran only
under `batch.runner_version_check = "warn"` on a fleet runner older than the
client, and the committed null/repeat evidence is described in section 5
exactly as obtained.

## 1. What was inspected (versions)

| Item | Value |
|---|---|
| Client `klt` | `0.7.0+g4cbdfa769875` (host tool; git rev `4cbdfa7698752b720c0e627163867de1e23475f3`, `released: false` in the report). Not modified. |
| Fleet runner `klt` | `0.5.0` (reported by the runner: `environment.remote.runner_klt_version`) |
| ngspice | fleet runner: `46`; this host (single local probe only): `42` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`; model deck `sm141064.ngspice` sha256 `6edba54d...1b77b1aa` |
| KLayout | `0.30.12` |

`klt sim` request fields used, all documented in the pinned client
(`klayout_tools/sim.py`, `_validate_monte_carlo_spec`, `_expand_monte_carlo`,
`_write_corner_deck`). No field was invented and no control step was stripped:

* `monte_carlo: {"n": int>=1, "seed": int, "vary": "mismatch"|"process"|"both"}`.
  Optional `quantiles` / `k_sigma` statistics are not used (per-sample values
  are read directly).
* **Seed semantics.** For each corner point and `sample_index`, klt derives
  `process_seed`, `mismatch_seed` and a combined `rndseed` as
  `sha256("<seed>:<label>:<corner_index>:<sample or 'fixed'>")[:4] mod 2^31`.
  With `vary: "mismatch"` only `mismatch_seed` (and so `rndseed`) changes with
  the sample index; `process_seed` is fixed. The deck gets `.options seed=<rndseed>`
  before the `.lib` cards, plus `.param mc_sample_index/mc_process_seed/mc_mismatch_seed`.
  The same base seed reproduces the same schedule. Because `corner_index` is in
  the derivation, the same sample index is a *different* device realization at
  each corner (paired draws across corners are not available; upstream
  [klayout-tools#2929](https://github.com/2AMLogic/klayout-tools/issues/2929)).
* **Mismatch model inclusion.** klt does not turn mismatch on for gf180mcu; the
  PDK's own switch does. `tb_adc_offset_mc.spice` sets `sw_stat_mismatch=1`,
  `sw_stat_global=0` (mismatch-only population) after the model includes, the
  same mechanism `sim/comparator-offset-mc` uses; `tb_adc_offset_null.spice` is
  byte-identical except `sw_stat_mismatch=0`. In this PDK that switch drives the
  MOS `fets_mm` per-instance terms; poly-resistor and MIM-capacitor mismatch is
  **not** modelled (`sim/comparator-offset-mc` null control; klt's own
  `family_mismatch` table says the same). klt's `family_mismatch` report is no
  help here: it scans only the top-level netlist file, so for this wrapper
  testbench it lists `other / active: null` and omits the MOS devices that
  live in the `.include`d extracted deck (upstream
  [klayout-tools#2928](https://github.com/2AMLogic/klayout-tools/issues/2928)).
  The evidence that mismatch reached the devices is therefore the null control
  (section 5), not that field.
* **Per-draw scalar.** klt runs one analysis per unit and reads `.meas` cards. A
  Monte Carlo *unit* is one `ngspice -b` process = one mismatch draw. There is
  no cross-unit reduction inside one draw and no in-process `dowhile`/`reset`
  loop (that is why `sim/comparator-offset-mc/testbench/tb.json`, whose first
  control step is `setseed` followed by `dowhile`/`reset`, still cannot go
  through `sim/harness/batch.py`; `check_exportable` keeps refusing it and
  is deliberately unchanged). The scalar per draw is therefore recovered
  *inside one transient* (section 3).

### Reproducing the export/validation check

```
python3 -I -m unittest discover -s sim/tests -p 'test_batch.py'      # unsupported control steps still refused
python3 -I -m unittest discover -s sim/tests -p 'test_adc_offset_mc.py'
python3 -I sim/adc-offset-mc/testbench/gen_pilot.py --check          # committed netlists/requests are current
```

`test_batch.py` includes the negative controls that `setseed`/`let`/`dowhile`/
`reset` manifests raise `NotExportable`; they pass unchanged, which is the
documented evidence that this issue did not loosen the exporter.

## 2. Netlist provenance

The DUT is the existing extracted `ADC_BLOCK` (both CDAC sides, four-leg bottom
plate switch networks and drivers, the two top-plate V_cm switches, the
comparator), reused from the committed record
`sim/adc-block-pex/records/20261008-185501-c618a90d.md`:

| File | sha256 |
|---|---|
| `sim/adc-block-pex/netlist-snapshots/20261008-185501-c618a90d.spice` (extracted, 1349 devices, 172 nets) | `91c044dc66ce3e2fc3913abe634349e69a5838226a4f2691de81ae7ab5fcbaf0` |
| `testbench/tb_adc_offset_mc.spice` | `1b03ce18f18050fec9cdf684a4db720ec3052211db7f6860222f181bc301952c` |
| `testbench/tb_adc_offset_null.spice` | `20ef4ccf5acf795782f7c84415ef09554e9d8f431df811eafba6b286b5206237` |
| `testbench/request_pilot_warn.json` (run) | `3a6a8e942fe4adf69d8dc0e05f110c8f08948a113af7f28785099ae0a5d6abea` |
| `testbench/request_null_warn.json` (run) | `f2dc96e4c4e104c02f94d97fb1160c3065acbd83872532ed95ac95d39eca95fe` |

The extracted netlist is `.include`d unchanged; klt's `environment.netlist_closure`
in every report records both files and their hashes. One modelling choice is
added by the testbench: the extracted deck's parasitic capacitors reference the
global net `vsubs`, which the testbench ties to ground with a 0 V source (all
bodies are already tied inside the extracted netlist, DR-0035). This is the
only thing the testbench adds to the block. The comparator preamp DC estimator
of `sim/comparator-offset-mc` is *not* reused: it measures the preamp alone
and excludes the CDAC, switches, charge injection and the latch.

## 3. The ADC_BLOCK-inclusive offset estimator

**Definition.** The input-referred offset is the differential input
`d = V_inp - V_inn` (common mode held at V_cm = 1.65 V) at which the whole
sample / redistribute / decide chain, as built, balances. With `V_inp > V_inn`
the DR-0014 residue is negative and the comparator resolves `dout` LOW
(`sim/adc-block-pex` record), so `dout` is HIGH for `d` below the threshold and
LOW above it. The offset is that threshold. Sign convention: positive offset
means the block needs `d > 0` to balance; sigma and the bound care only about
magnitude.

**Stimulus (one transient = one mismatch draw).** 33 back-to-back DR-0014
conversions of a differential-input staircase `d_k = -4.0 mV + k * 0.5 mV`,
k = 0..32 (range -4.0 .. +12.0 mV), 200 ns per conversion with the pex-record
timing: acquisition with every bottom plate on its input leg and both top
plates at V_cm, `tp_gn` falls at 100 ns (the sampling instant), input legs open
at 110 ns, all bottom plates to V_cm at 115 ns, comparator strobe 150..180 ns,
`dout` read at 178 ns. Controls return to acquisition between conversions
(rel off 182 ns, `tp_gn` on 185 ns, `sel_in` on 188 ns) and the input steps
while the input legs are on (192 ns). Hi/lo reference legs stay off, as in the
pex record (no bit trial: this measures the sample-and-decide offset, not the
DAC levels). The range was centred after a single local probe of the
mismatch-off block (threshold between +3.0 and +3.5 mV).

**Estimator.** A healthy draw reads `1...1 0...0`. The offset is the midpoint
between the last 1 and the first 0 (`analyze_pilot.py`). Because every
conversion within a draw sees the same netlist instance, device mismatch is
preserved across all 33 conversions: a single `ngspice` process parses the
`agauss`/`fets_mm` expressions once, so no re-draw can happen between
conversions (this is the property `sim/comparator-offset-mc` had to check with
its `av_sigma_pct` self-check; here it is structural, and a re-draw would show
up as a non-monotone decision sequence, a failed draw).

**Separating input offset from quantization and conversion/readout error.**

* *Quantization.* The threshold is known to +/- 0.25 mV (half the 0.5 mV step),
  uniform, sigma_q = 0.5/sqrt(12) = 0.144 mV. The reported sample standard
  deviation is also given with Sheppard's correction
  `sqrt(max(s^2 - step^2/12, 0))`. This is not the ADC's own 10-bit
  quantization (3.2227 mV LSB_se), which is not in this measurement at all:
  the staircase is applied to the *comparison*, so the ADC quantizer never
  smears it. The step is 6.5x finer than an LSB, so the resolution budget is
  0.5 mV = 0.155 LSB_se per bin.
* *Conversion / readout error.* A draw fails (is reported, never dropped) when
  `dout` is not a clean rail (within 10 % of V_dd of 0 or V_dd), when the
  sequence has more than one flip or does not start high (conversion-to-
  conversion memory, hysteresis or a readout fault), when it never flips inside
  the range (censored: the offset is outside -4..+12 mV), or when klt reports
  the corner as anything but `pass`. Conversion-to-conversion memory is only
  detectable as non-monotonicity, not as a bias when monotone; the pilot
  tested one sweep direction. The full campaign must add the descending
  staircase (section 6) to put a number on hysteresis.
* *Gain / residue error.* Does not enter: the decision is a sign, taken at the
  residue zero crossing, so a gain error (C_arr/(C_arr+C_par) attenuation,
  record 20261008-185501-c618a90d) scales the *residue* at the comparator but
  not the input value at which it crosses zero, to first order.

**LSB conversion.** `LSB_se = V_REF/1024 = 3.2227 mV` at V_dd = V_REF = 3.3 V
(DR-0006), the same conversion `sim/comparator-offset-mc` uses, so numbers are
comparable with its 1.75 LSB preamp-only 3-sigma budget line. The bound
`<= 2 LSB` is `6.445 mV`, i.e. `sigma <= 2.148 mV` under a normal model.

**Declared pilot parameters.** Single corner `tt`, 27 C, V_dd = V_REF = 3.3 V,
V_cm = 1.65 V; mismatch only (`vary: mismatch`, `sw_stat_global=0`); enabled
population `n = 8`, base seed `20261009`; null control `n = 4`, same seed
schedule, `sw_stat_mismatch=0`. These numbers qualify the *path*; they are
deliberately not a campaign size.

**Declared acceptance checks** (`analyze_pilot.py`, each with a negative control
in `sim/tests/test_adc_offset_mc.py`):

| Check | Criterion |
|---|---|
| draws returned | all 8 requested |
| valid draws | at least 75 % of requested; failed draws listed |
| independent seeds | 8 distinct per-sample seeds (a duplicated draw is not an independent sample) |
| variation above resolution | sample sd >= 1 step (0.5 mV) and >= 3 distinct threshold values |
| null | all 4 valid; spread (max - min) <= 1 step; seeds distinct (the control varies the seed, only mismatch is off) |
| repeat | identical seed schedule; per-sample thresholds agree within 1 step (0.5 mV) |

## 4. Reproducible command (batch)

```
python3 -I sim/adc-offset-mc/testbench/gen_pilot.py --check
klt sim --backend batch -o <outdir> --format json sim/adc-offset-mc/testbench/request_pilot_warn.json   > <outdir>-report.json
klt sim --backend batch -o <outdir> --format json sim/adc-offset-mc/testbench/request_null_warn.json    > <outdir>-null-report.json
klt sim --backend batch -o <outdir> --format json sim/adc-offset-mc/testbench/request_pilot_warn.json   > <outdir>-repeat-report.json
python3 -I sim/adc-offset-mc/testbench/analyze_pilot.py --enabled <report> --null <null-report> --repeat <repeat-report> --out summary.json
```

(use `uvx --from "klayout-tools==X.Y.Z" klt ...` to pin a different client; do
not install into the host tool.) `request_pilot.json` / `request_null.json` are
the same requests without the `batch.runner_version_check` override; they are
what a fleet whose runner matches the client runs, and they are the committed
refusal evidence below.

## 5. Results (pilot, `tt` / 27 C / 3.3 V, mismatch only)

Evidence directory `corners/20261009-042900-2a4b3fac/` (append-only; never
edited). Everything below is read from the committed klt reports and
re-derivable with `analyze_pilot.py`; the machine summary is
`pilot-summary.json`.

| Run | Request | Backend / job | Result |
|---|---|---|---|
| enabled | `request_pilot_warn.json` | batch `klt-sim-1b1c9893bf86`, runner klt 0.5.0, ngspice 46, 2,725 s | 8/8 draws `pass` |
| null (mismatch off) | `request_null_warn.json` | batch `klt-sim-9399bbbf5e83`, 965 s | 4/4 draws `pass` |
| repeat of enabled | `request_pilot_warn.json` | batch `klt-sim-113f9cf46838`, 2,797 s | 8/8 draws `pass` |
| cross-host probe, sample 0 | `request_probe_sample0.json` (n=1; run from the same request with `n` edited, plus one comment line added here) | local single unit, ngspice 42 | same decision pattern as fleet sample 0 |

Per-sample thresholds (enabled run; `sample_index` : seed : offset):

| idx | seed | decision pattern k=0..32 | offset (mV) | offset (LSB_se) |
|---|---|---|---|---|
| 0 | 1189634286 | `1`x14 `0`x19 | 2.75 | 0.853 |
| 1 | 328376976 | `1`x17 `0`x16 | 4.25 | 1.319 |
| 2 | 1668344203 | `1`x12 `0`x21 | 1.75 | 0.543 |
| 3 | 754629558 | `1`x14 `0`x19 | 2.75 | 0.853 |
| 4 | 1279124369 | `1`x16 `0`x17 | 3.75 | 1.164 |
| 5 | 1287598088 | `1`x17 `0`x16 | 4.25 | 1.319 |
| 6 | 17532503 | `1`x18 `0`x15 | 4.75 | 1.474 |
| 7 | 1648114447 | `1`x19 `0`x14 | 5.25 | 1.629 |

Samples 0 and 3 landing in the same 0.5 mV bin, and 1 and 5, are distinct seeds
with distinct device draws that quantize to the same bin, not duplicated draws
(their seeds and mismatch seeds differ; `analyze_pilot.py` checks seeds, not
values, for duplication).

Checks (all declared in section 3 before the runs, all passed):

| Check | Observed |
|---|---|
| draws returned / valid | 8 of 8 / 8 of 8; no failed, censored or non-monotone draw |
| independent seeds | 8 distinct |
| variation above resolution | sd 1.178 mV (0.366 LSB_se) vs step 0.5 mV; 6 distinct bins; range 1.75 .. 5.25 mV |
| null | 4/4 valid, all at 3.25 mV, spread 0.000 mV (<= 0.5 mV); the 4 null seeds are the same schedule as enabled samples 0..3, so only the mismatch switch differs |
| repeat | identical seed schedule; max per-sample difference 0.0 mV over 8 pairs (<= 0.5 mV) |

Reading it. The mismatch-off block has a systematic threshold at +3.25 mV, so
nonzero spread in the enabled run is not an artefact of the stimulus or of a
numerically noisy comparator: with identical seeds and netlist, switching the
PDK's mismatch term off collapses it to one bin, and switching it on gives
sd 1.18 mV. Sample standard deviation after Sheppard correction is 1.169 mV.
The enabled mean is 3.69 mV, 0.44 mV above the null value; with n = 8 the
standard error of the mean is 0.42 mV, so that is not distinguishable from
zero shift. **None of this is the spec's number.** Eight draws at one PVT
point, one scan direction, bin-midpoint thresholds. The naive `3 * 1.18 mV =
3.5 mV = 1.1 LSB_se` is reported here only because a reader will compute it;
it is not a verdict, it has a 95 % upper confidence bound near 1.8x that value
at n = 8 (section 6), and the systematic +3.25 mV (1.0 LSB_se) offset is a
separate matter (6.2).

## 6. Full-campaign protocol (follow-on, not run here)

The pilot qualifies a path; it does not support a verdict. Eight draws give a
standard-deviation estimate with a one-sided 95 % upper bound about 1.8x the
sample value (chi-square, 7 d.o.f.), and the pilot is at one PVT point. The
campaign below is what a verdict needs. `testbench/sample_size.py`
(standard library only) reproduces every number in this section.

**6.1 What is claimed.** Two different claims need two different sample sizes
and must not be conflated. Both are about the *mismatch-only* population
(`sw_stat_global=0`); the global-process axis is covered by the corner set, not
by sampling.

* **Claim A, normal-model 3-sigma bound.** `3 * sigma_U <= 2 LSB = 6.445 mV`,
  where `sigma_U` is the one-sided 95 % chi-square upper confidence bound on the
  population standard deviation, `sigma_U = s * sqrt((n-1) / chi2_{0.05, n-1})`.
  This is the spec's own wording ("3-sigma mismatch") and is only meaningful if
  the population is close to normal. The campaign must *test* that (6.4), not
  assume it.
* **Claim B, empirical tail yield.** `P(|offset| <= 2 LSB) >= p` at stated
  confidence, from the count of exceedances (one-sided Clopper-Pearson). No
  normality assumption, but a normal 3-sigma tail is `p = 0.9973`, which needs
  roughly a thousand draws with zero exceedances.

Claim A alone is acceptable only with a passing normality gate; Claim B is the
fallback when the gate fails, and the stronger statement either way.

**6.2 The offset-vs-total question must be decided first.** The mismatch-off
null control sits at a nonzero systematic threshold (about +3.25 mV = 1.0 LSB_se
in the local probe, and the enabled pilot mean is +3.69 mV); the spec row says
"untrimmed offset (3-sigma mismatch)" and does not say whether the systematic
mean counts. Which of `3*sigma` (spread about the mean), `|mean| + 3*sigma`, or a
quantile of `|offset|` is compared with 2 LSB changes the verdict, so it needs a
recorded decision (a `spec/` decision record, not this PR) before any
population is run. The decision is drafted as
[DR-0038](../../spec/decision-records/DR-0038-offset-error-definition.md)
(proposed, pending ratification by the operator; it compares the three
definitions on the numbers of section 5 and recommends `3*sigma` about the
mean). This PR leaves the row Unmeasured and does not choose. The
campaign records mean, sigma and `|offset|` quantiles so all three can be read
off the same data.

**6.3 PVT coverage.** Mismatch sigma moves with process, supply and temperature
(threshold-voltage mismatch and bias currents), so a typical-corner population
is not a bound. Coverage:

* Screening stage, 45 points: the five MOS corners (tt, ff, ss, fs, sf) x
  V_dd {2.97, 3.3, 3.63} V (V_ref, V_cm and the input common mode following,
  as in `sim/adc-block-pex/testbench/request.json`) x T {-40, 27, 125} C, with
  `n = 30` draws each (about 1,350 simulations at roughly 200 s of fleet
  ngspice each). The capacitor and resistor skews are held typical: this
  population has no cap/resistor mismatch (section 1) and they move the
  residue gain, not the decision threshold, to first order. If the
  screening step reveals sensitivity to them, they are added.
* Decision stage: the corner with the largest `sigma_U` (and the corner with
  the largest `|mean| + 3 s`, if different) is rerun at the full N of 6.5. A
  claim is made per corner, then the maximum over corners is the block result;
  corners are never pooled into one sample (pooling mixes populations with
  different sigma and hides the worst one).
* The seed derivation includes the corner index, so corners are independent
  populations, which suits per-corner bounds; same-die corner deltas would need
  paired draws (upstream klayout-tools#2929).

**6.4 Independent-draw unit and seed independence.** The independent unit is
one transient: one die-level mismatch realization of every MOS in the extracted
`ADC_BLOCK`. The 33 conversions inside a draw are *not* independent samples
(same instances), they are one measurement of one sample. Requirements before a
draw counts: its `seed` is unique within the corner and across the campaign
(duplicates are rejected, not averaged); the per-corner `mismatch_seed`
schedule comes from one declared base seed per campaign recorded in the
request; the lag-1 sample autocorrelation of the ordered offsets is reported
(expected within +/- 2/sqrt(n)) as a sanity check on the seed generator. A run
whose per-sample values are all identical is a failure of the path, not a
tight distribution.

**6.5 Sample size.** Normal-model planning table, 95 % one-sided, the chosen N
being the smallest that gives the stated probability of demonstrating
`3*sigma_U <= B` when the true `3*sigma` is `r * B`:

| true 3 sigma / B | true 3 sigma (LSB) | N at 80 % assurance | N at 95 % assurance | P(pass) at N=150 | true P(abs > B) |
|---|---|---|---|---|---|
| 0.50 | 1.00 | 10 | 14 | 1.000 | 1.97e-09 |
| 0.60 | 1.20 | 15 | 23 | 1.000 | 5.73e-07 |
| 0.70 | 1.40 | 28 | 45 | 1.000 | 1.82e-05 |
| 0.80 | 1.60 | 67 | 111 | 0.987 | 1.77e-04 |
| 0.90 | 1.80 | 287 | 490 | 0.546 | 8.58e-04 |

`sigma_U / s` falls from 1.28 (n=30) to 1.11 (n=150) and 1.04 (n=1000), so the
confidence penalty is paid in margin, not in N alone.

Empirical tail, zero exceedances, one-sided Clopper-Pearson:

| yield target | N (90 %) | N (95 %) | N (99 %) |
|---|---|---|---|
| 0.9500 | 45 | 59 | 90 |
| 0.9900 | 230 | 299 | 459 |
| 0.9973 | 852 | 1109 | 1704 |
| 0.9990 | 2302 | 2995 | 4603 |

**N = 150 by itself is not signoff.** With zero exceedances it proves only
`P(pass) >= 0.980` at 95 % confidence (0.970 at 99 %), and one exceedance drops
that to 0.969. It supports Claim A at 95 % confidence only when the true
`3*sigma` is below about 0.8 B and the normality gate passes. The campaign N is
chosen *from* the claim:

* Claim A: the decision-stage N is set from the screening-stage `s` at the
  worst corner, using the table row for `r = 3 s_U / B` (rounded up, and not
  below 150 so the normality test has power). Whatever N is chosen is written
  into the campaign request before it runs.
* Claim B (required if normality fails or the margin is small): N >= 1109 per
  decision corner for `p = 0.9973` at 95 % with zero exceedances. Each
  exceedance raises the needed N; the stopping rule is fixed in advance, not
  tuned to the result.

**6.6 Estimator assumptions and how they are checked.**

* Normality gate on the decision-stage sample: Anderson-Darling at 5 %, plus
  skewness and excess kurtosis within the sampling error of a normal of that
  N, plus the ratio of the empirical 99.5th percentile of `|x - mean|` to
  `3*s`. Failing the gate switches the claim to B and the estimator to
  empirical quantiles; a normal-model sigma is still reported but not used for
  the verdict. A mixture-like or heavy-tailed result (for example a population
  with a bimodal threshold from a latch metastability branch) is reported
  and investigated, never trimmed.
* Quantization: each threshold is a bin midpoint with +/- 0.25 mV
  uncertainty. For Claim A the variance is Sheppard-corrected for reporting
  but the *bound* uses the uncorrected `s` (conservative). For Claim B an
  exceedance is judged on `|offset| + 0.25 mV` (the worse edge of the bin), so
  quantization can only add exceedances, never hide them.
* Hysteresis / conversion memory: each draw carries an ascending and a
  descending staircase; the half-difference of the two thresholds is
  reported per draw and added in quadrature to the bin uncertainty. A draw
  where it exceeds one step is flagged.
* Range censoring: the pilot range (-4 .. +12 mV) is wide for a mean near
  3.7 mV and sigma near 1.2 mV, but a tail draw outside it has no threshold.
  The campaign range is widened symmetrically about the measured mean to at
  least 3 LSB_se beyond it. A censored draw is counted as an exceedance for
  Claim B, and excluded from (and reported beside) the sigma estimate for
  Claim A together with the worst-case imputation of its bound.
* Failed simulations (klt corner `error`/`fail`, no convergence, indeterminate
  `dout`, non-monotone staircase): rerun once with the identical seed to
  separate transient infrastructure failure (spot interruption) from a
  deterministic circuit failure. A deterministic failure is a real outcome of
  that mismatch realization: it counts as an exceedance for Claim B and
  is reported with its seed. The campaign verdict may not be given with a
  failure rate above 1 %, and the failure count and seeds are in the record
  regardless.

**6.7 Remaining prerequisites before the population can run.**

1. The offset-vs-total decision of 6.2 (a recorded decision, then the row can
   be evaluated against it): drafted as DR-0038, pending ratification.
2. A fleet runner whose `klt` equals the client's, or an agreed pinned client:
   the pilot ran under `runner_version_check = "warn"` on `klt 0.5.0`
   (section 7). A 1,350-simulation campaign should not depend on an override,
   and the fleet instance cap (`BATCH_MAX_CONCURRENT_INSTANCES = 8`, hit
   repeatedly during this pilot, section 7) must accommodate the screening
   stage. An old runner may also ignore `options.ngspice_init`
   (klayout-tools#2917); this pilot reads only rail-level `dout` values, so it
   is insensitive to print precision, a campaign that reads analog values is not.
3. A serial-runtime plan: the batch job ran its 8 draws serially on one
   instance (`concurrency: 1`, 2,725 s). 1,350 draws at roughly 340 s each
   (fleet ngspice 46, 33 conversions with 1349 devices) is about 127 serial
   hours unless klt shards the unit list across instances. The campaign request
   should be split per corner (45 jobs) so the fleet parallelizes it, or the
   staircase shortened by a coarse-to-fine two-pass design.
4. Descending-staircase readout added to the testbench (6.6), and the range
   widened per 6.6.
5. A harness-level record writer for this estimator, so the campaign is
   recorded as an append-only `sim/adc-offset-mc/records/<record-id>.md` with
   netlist hash, corners, toolchain versions and seeds like every other
   record. This PR commits the raw klt reports and a machine summary, not a
   `records/` entry: a record is a claim, and this is a qualification.
6. Upstream: klayout-tools#2928 (mismatch report must cover the `.include`
   closure) so the report itself can carry the evidence that is now carried by
   the null control; klayout-tools#2929 if paired corner deltas are wanted.

## 7. Limitations and what was not achieved

* **The first submission, in the default `enforce` mode, did not run.**
  `request_pilot.json` to the fleet: all 8 draws `error`, `batch_job_failed`,
  `runner_code: batch_runner_version_mismatch` (job `klt-sim-a330aa5096bf`,
  exit 87): the fleet runner image runs klt 0.5.0 and refuses the 0.7.0+g4cbdfa769875
  client ("the request was not run"). Report committed as
  `corners/20261009-042900-2a4b3fac/pilot-report.json`. This is the same skew
  `sim/adc-block-pex/records/20261008-185501-c618a90d.md` hit; it is a runner-image
  update, not a change here. Upstream: klayout-tools#2851, #2877, #2901.
* **The pilot ran only because the request sets `batch.runner_version_check =
  "warn"`** (a documented klt request field), and therefore on a runner that is
  older than the client. The report stamps `runner_compatibility: mismatch`.
  Whether a 0.5.0 runner honours the per-sample seeds was not assumed: it is
  exactly what the null/repeat/duplicate checks test, and the draws are distinct,
  seed-reproducible, and match a local ngspice-42 run of sample 0 bit for bit
  at the decision level. That bounds the risk for this request; it does not
  make the skew acceptable for a campaign (6.7 item 2).
* **Fleet capacity.** The null and repeat submissions were refused client-side
  several times (`9 instance(s) already running + 1 requested exceeds
  BATCH_MAX_CONCURRENT_INSTANCES=8`; log: `submit-attempts.log`) and resubmitted
  unchanged by a bounded retry loop. No run fell back to local execution; the one
  local run is the single-unit cross-host probe, which is not counted toward any
  pilot check.
* **Serial execution.** Each batch job ran its draws serially on one instance
  (`concurrency: 1`), about 340 s per draw. See 6.7 item 3.
* **Scope.** One PVT point; MOS mismatch only (no resistor, MIM or global
  process variation); one scan direction (hysteresis not quantified);
  `family_mismatch` not usable as evidence (klayout-tools#2928).
* **The ratified row is unchanged and Unmeasured.** No record under `records/`
  is written, `README.md` / `spec/` / `sim/characterization-summary.md` are not
  touched, and no completed-population or yield claim is made.

## 8. Files

| Path | What |
|---|---|
| `testbench/gen_pilot.py` | deterministic generator for the netlists and requests; `--check` verifies the committed files |
| `testbench/tb_adc_offset_mc.spice`, `tb_adc_offset_null.spice` | generated testbenches (mismatch on / off) |
| `testbench/request_pilot_warn.json`, `request_null_warn.json` | the requests that ran on the batch fleet |
| `testbench/request_pilot.json`, `request_null.json` | same requests in default `enforce` mode (refused, see section 7) |
| `testbench/request_probe_sample0.json` | n=1 local cross-host probe |
| `testbench/analyze_pilot.py` | estimator and declared checks |
| `testbench/sample_size.py` | the section 6 sample-size tables |
| `corners/20261009-042900-2a4b3fac/` | klt reports (`*-report.json`), per-draw decks (`*/*/corner.cir`), refusal evidence, `pilot-summary.json`, `submit-attempts.log` |
| `../tests/test_adc_offset_mc.py` | generator-currency test and negative controls for every check |

Upstream issues (generic tool gaps, filed under the friction protocol):
klayout-tools#2928 (mismatch family report ignores the `.include` closure),
klayout-tools#2929 (no shared mismatch-seed schedule across corners). Existing
and relevant: #2898, #2851, #2877, #2901, #2917.
