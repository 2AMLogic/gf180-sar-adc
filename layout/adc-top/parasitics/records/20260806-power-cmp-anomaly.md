# Record 20260806-power-cmp-anomaly

- **Record ID**: 20260806-power-cmp-anomaly
- **Claim**: **diagnostic only, no spec-line claim.** The extracted-core #13
  power re-run (`sim/adc-power/records/20260806-083932-faebccc.md`) reports a
  comparator supply term (`p_cmp_f100_uw`) at ONE of its 27 corners that is
  **2.06x** the schematic baseline's, against ≤ 1.4 % at the other 26. This
  record localises that outlier and establishes whether it is attributable to
  the extracted analog core, to the measurement window, or to neither. It is
  the evidence `sim/extracted-delta-summary.md` §7.2 cites.
- **Netlist provenance**: **both**, deliberately — the same power deck is
  composed against the schematic core (`gen_adc_top.power_deck()`) and against
  the remediated extracted `ADC_TOP` core
  (`gen_extracted_power_tb.power_netlist_extracted()`), with everything else —
  stimulus, supply split, comparator, rung-1 controller, DR-0013 input drive,
  corner, temperature, supply — held identical. Without the schematic arm,
  "the extracted core does this" and "this deck does this at this corner" are
  indistinguishable, and only the first would be a post-layout finding.
- **Instrument**: `layout/adc-top/parasitics/probe_power_cmp_anomaly.py`
- **Corner**: `tt_125c_3.63v` (the single outlier corner), one point per core
- **PDK / toolchain**: gf180mcuD, open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, MiM stack `m4m5`, ngspice-46,
  resolved via `sim/harness/pdk.py`. Same pins as the record it diagnoses.

## What the recorded runs disagree about

| | schematic `20260802-141402-1224e11` | extracted `20260806-083932-faebccc` |
|---|---|---|
| `p_cmp_f100_uw` @ `tt_125c_3.63v` | 109.382 µW (`i(vddc)` ≈ −30.1 µA) | **224.952 µW** (≈ −62.0 µA) |
| `p_total_f100_uw` @ same corner | 147.875 µW | **267.309 µW** |
| the other 26 corners, `p_cmp_f100_uw` | — | **−1.33 % … +0.98 %** |
| the other 26 corners, `p_total_f100_uw` | — | **+2.17 % … +4.26 %** |

The raw log for that corner
(`sim/adc-power/corners/20260806-083932-faebccc/tt_125c_3.63v.log`) carries no
ngspice warning, no convergence failure, no timeout, and no non-convergent
point — the manifest's own five 2 µs `AVG i(vddc)` windows simply report that
number. The run is 27/27 PASS: `p_total_f100_uw = 267.309 µW` is well inside
the manifest's `max = 1000` check, so nothing failed. That is exactly why it
needs a record: a passing outlier is the kind that gets absorbed.

## Method

The manifest averages `i(vddc)` over a 2 µs window per input level, i.e. over
conversions 2 and 3 of that level's three. That is too coarse to tell a
raised baseline from a single anomalous conversion. The probe re-runs the same
deck with the same stimulus and instruments it **per conversion**:
`AVG i(vddc)`, `MIN i(vddc)` (the largest instantaneous draw — the current is
negative out of the source), `AVG i(vddd)` and the decoded output code
`v(se_code)`, over each of the 17 conversions the power deck's own schedule
runs (`PWR_WARMUP_CONV = 2` + `PWR_CONV_PER_LEVEL = 3` × 5 levels — derived
from `gen_adc_top`, not retyped).

```bash
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core extracted
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core schematic
```

## Result

Only the rows that differ are reproduced here; the full 17-row tables per core
are what the two commands above print. Conversions 0–13 agree between the two
cores on `i(vddc)` to **within 0.6 %** at every conversion, on the peak to
within 0.01 %, and on the decoded code exactly, except conversion 10 (see
below).

| conversion | input level | code (sch) | `i(vddc)` avg, sch | code (**ext**) | `i(vddc)` avg, **ext** | peak, sch → **ext** |
|---|---|---|---|---|---|---|
| 10 | 0.50 | 511 | −31.964 µA | **512** | −31.819 µA | −1838.45 → **−1839.21** µA |
| 14 | 1.00 | 1022 | −29.515 µA | 1022 | −29.508 µA | −1838.39 → **−1838.40** µA |
| 15 | 1.00 | 1022 | −30.322 µA | **1023** | **−61.926 µA** | −1838.39 → **−2545.72** µA |
| 16 | 1.00 | 1023 | −29.944 µA | 1023 | **−62.015 µA** | −1838.35 → **−2565.84** µA |

Conversions 15 and 16 are exactly the two the manifest's `f100` window
averages: sch (−30.322 − 29.944)/2 = −30.13 µA → 109.4 µW, ext
(−61.926 − 62.015)/2 = −61.97 µA → 225.0 µW. The probe reproduces both
recorded numbers to the printed digits, so it is instrumenting the same thing
the manifest measured.

## Findings

1. **It is not a measurement-window artefact.** The excess is not one
   anomalous conversion diluted by an average — *both* conversions in the
   window carry it, at −61.9 and −62.0 µA, and the conversion immediately
   before (14, same input level) is normal at −29.5 µA. The step is a step,
   not a spike.

2. **It is not the static preamp bias.** DR-0007's preamp bias is a fixed
   `i vddc se_ibias dc 10u` source in both arms; a fixed current source cannot
   double. The excess is **dynamic**: the peak draw rises from −1838 µA to
   −2546/−2566 µA (+39 %), which is latch/output-stage switching current, not
   bias.

3. **It is attributable to the extracted core, and it is not simply "code
   1023 costs more".** The schematic arm *also* reaches code 1023 (conversion
   16) at this corner and draws a normal −29.944 µA there. So being at the top
   code is not sufficient. What differs is that the extracted core walks into
   1023 **one conversion earlier** (15 vs 16) and then stays there drawing
   2× — i.e. the two cores resolve the full-scale input differently, and the
   extracted core's resolution of it is the expensive one.

4. **It does not threaten the ratified row.** `Power @ 1 MS/s < 1 mW`: the
   worst `p_total_f100_uw` over the whole extracted grid is **267.309 µW** —
   3.7× inside the 1 mW bound, and still inside the < 500 µW stretch target.
   Every corner is PASS on both sides and no corner's verdict changed. **No
   spec line is adjusted here** (CLAUDE.md), and none needs to be; the outlier
   is reported because it is a 2× move in a measured block, not because it
   fails anything.

## What this record does NOT establish

The device-level mechanism inside the comparator. "The latch switches more at
this operating point" is what the peak/average split shows; *why* the
extracted core's full-scale residue puts the comparator there — a marginal
final trial that re-decides on successive strobes, a common-mode shift from
the extracted top-plate parasitic capacitance, or both — needs an instrument
this probe does not have (per-strobe comparator-output transition counting,
and the top-plate differential and common mode at each decision instant).
That is filed as a follow-up rather than guessed at here.

It is also a **one-corner, one-core-pair** measurement. It does not
establish how close the other 26 corners are to the same boundary, i.e. how
much of the grid would tip into this behaviour under a small further shift.

## Environment

- PDK: gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (`~/.volare/gf180mcuD`, via `search_root:~/.volare`), MiM stack `m4m5`
- ngspice: ngspice-46
- Extraction under test:
  `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`,
  remediated by `remediate_extracted.py` (PMOS body → `vdd`; input rails →
  pins; MiM untouched)
- Wall time: 364 s (extracted arm), 331 s (schematic arm), single-threaded
- Diagnoses: `sim/adc-power/records/20260806-083932-faebccc.md`
- Cited by: `sim/extracted-delta-summary.md` §4.7 / §7.2

---

Diagnostic record: it mints no `sim/` corner-matrix record and makes no
spec-line claim. Append-only like everything under `sim/` — a re-run or
correction mints a new record and points back here.
