# Record 20260806-power-cmp-metastability

- **Record ID**: 20260806-power-cmp-metastability
- **Claim**: **diagnostic only, no spec-line claim.** Issue #107, closing the
  two items `20260806-power-cmp-anomaly.md` (issue #89's diagnostic) named as
  NOT established: (1) the device-level mechanism behind the extracted-core
  power run's one-corner, 2.06x `p_cmp_f100_uw` excursion, and (2) how close
  the other 26 PVT corners sit to the same boundary. Nothing here is a spec
  claim and nothing in `sim/` or the ratified spec is adjusted — the row this
  investigates already PASSES with 3.7x margin (§4.7.2 /
  `sim/extracted-delta-summary.md`).
- **Netlist provenance**: **both**, as its predecessor record does — the same
  extended probe composes the SAME power deck against the schematic core
  (`gen_adc_top.power_deck()`) and the remediated extracted `ADC_TOP` core
  (`gen_extracted_power_tb.power_netlist_extracted()`), everything else (
  stimulus, supply split, comparator, controller, corner, temperature,
  supply) held identical, so a difference between the two arms is
  attributable to the core and not to the deck.
- **Instrument**: `layout/adc-top/parasitics/probe_power_cmp_anomaly.py`,
  EXTENDED this issue (not rebuilt) with two new instruments the predecessor
  record's "What this record does NOT establish" section named as missing:
  - `--waveform`: dumps `v(se_cmp)`, `v(se_topp)`, `v(se_topn)`, `v(cmpclk)`
    and `i(vddc)` at the simulator's own adaptive time points (`wrdata`, no
    interpolation) and buckets them onto the deck's own bit-cycle grid (16
    bit cycles / 1000 ns conversion, `gtop.CLK_PERIOD_NS` = 62.5 ns), reporting
    per bit cycle: the comparator-output (`se_cmp`) transition count while
    the strobe is high, the top-plate differential and common-mode voltage
    at the decision instant, and the bit cycle's own peak `i(vddc)`.
  - `--levels`: overrides the power deck's fixed 5-point staircase with an
    arbitrary list of full-scale fractions, for a fine sweep around the top
    code (Acceptance Criteria item 2 below).
- **Corners**:
  - Mechanism (§1–§2): `tt_125c_3.63v` only — the one corner that tips.
  - Bound sweep (§3): `tt_125c_3.63v` (control), `tt_125c_3.30v` (its supply
    neighbor — same process/temperature, one step down the 3-point supply
    axis), `tt_27c_3.63v` (its temperature neighbor — same process/supply,
    one step down the 3-point temperature axis). Both are adjacent to the
    tipping corner in the PVT grid `sim/harness/corners.py` defines
    (temperatures −40/27/125 °C, supplies 2.97/3.30/3.63 V), satisfying the
    Test Plan's "at least one PVT-grid neighbor" requirement with two.
- **PDK / toolchain**: gf180mcuD, open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, MiM stack `m4m5`, ngspice-46,
  resolved via `sim/harness/pdk.py`. Extraction under test:
  `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`,
  remediated by `remediate_extracted.py`. Repo git sha `c796b39b3454b2eb79b7eadf565c92eb15f76fad`.

## 1. Reproduction check (Test Plan's own precondition)

The Test Plan requires confirming the extended probe still reproduces the
existing per-conversion current split before drawing new conclusions from
it. It does, to the printed digit, against both
`sim/adc-power/records/20260806-083932-faebccc.md` (extracted) /
`20260802-141402-1224e11` (schematic) and the predecessor record:

| conversion | level | `i(vddc)` avg, sch (µA) | code, sch | `i(vddc)` avg, **ext** (µA) | code, **ext** | peak, sch → **ext** (µA) |
|---|---|---|---|---|---|---|
| 14 | 1.00 | −29.5145 | 1022 | −29.508 | 1022 | −1838.39 → −1838.40 |
| 15 | 1.00 | −30.3219 | 1022 | **−61.926** | **1023** | −1838.39 → **−2545.72** |
| 16 | 1.00 | −29.9436 | 1023 | **−62.015** | 1023 | −1838.35 → **−2565.84** |

Byte-for-byte the predecessor record's own numbers (`20260806-power-cmp-anomaly.md`
§"Result"). The base per-conversion table (no `--waveform`, no `--levels`) is
unchanged code from that record's probe — this match is a regression check on
the extension, not a new result.

```
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core extracted --waveform --json ...
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core schematic --waveform --json ...
```
(both default to `--corner tt --temp 125 --vdd 3.63`, the anomalous cell's own
corner; wall time 452 s / 182 s respectively, single-threaded.)

## 2. The mechanism

**Structural fact, from the deck's own design comments**
(`design/adc-top/gen_adc_top.py`):

- `cmpclk` (`_preamble()`) is a free-running pulse at the bit rate — it
  strobes the StrongARM latch **every** bit cycle, including the three
  acquisition cycles (bit cycles 0–2, the 187.5 ns DR-0014 window) and bit
  cycle 3, not only the ten real decide phases the SAR controller actually
  samples.
- The DR-0014 top-plate V_cm switch (`adc_tp_sw`, wired per side in `_core()`)
  is **closed for bit cycles 0–2 and opens on the edge into bit cycle 3** —
  that edge is the sampling instant. So bit cycles 0–2 hold `v(se_topp)` /
  `v(se_topn)` at a low-impedance node actively clamped toward `vcm`
  (`R_on * (C_arr + C_par)` ≈ 5.2 ns nominal, the file's own sizing note);
  bit cycle 3 is the **first cycle the top plates are a floating,
  high-impedance, freshly-released node**.

**What the new per-bit-cycle instrument measures, at `tt_125c_3.63v`, side by
side, same corner, same conversions, extracted vs. schematic** (conversion
14 is the un-anomalous control at the same input level; 15/16 are the two
anomalous conversions both records already agree on):

| conv | bit | EXTRACTED diff (mV) | EXTRACTED cm (mV) | trans | EXTRACTED peak (µA) | SCHEMATIC diff (mV) | SCHEMATIC cm (mV) | trans | SCHEMATIC peak (µA) |
|---|---|---|---|---|---|---|---|---|---|
| 14 | 2 | +0.0484 | +1815.0265 | 0 | −1831.413 | +0.0479 | +1815.0262 | 0 | −1831.411 |
| 14 | 3 | +0.4213 | +1815.6510 | 0 | −1831.370 | +0.4163 | +1815.6546 | 0 | −1831.368 |
| **15** | **2** | +0.0020 | +1815.0023 | **0** | −1831.365 | +0.0003 | +1815.0025 | **1** | −1831.363 |
| **15** | **3** | +0.0015 | +1815.4761 | **1** | **−2545.720** | +0.0002 | +1815.4447 | **0** | −1831.511 |
| **16** | **2** | −0.0043 | +1815.0022 | **0** | −1831.365 | +0.0003 | +1815.0024 | **1** | −1831.363 |
| **16** | **3** | +0.0014 | +1815.4761 | **1** | **−2565.841** | +0.0003 | +1815.4453 | **0** | −1831.511 |

(Full 16-bit-cycle × 17-conversion tables for both cores are in the probe's
own `--json` output; only the rows that matter are reproduced here, per
`sim/README.md`'s own convention.)

**Reading it**: at the control conversion (14), neither core's free-running
acquisition strobe ever gets close enough to `vcm` to flip `se_cmp` — bit
cycles 2 and 3 both carry a sub-millivolt but non-tiny residual (~0.42–0.57
mV) and 0 transitions, and current is the normal ~1831 µA baseline
everywhere. At the two anomalous conversions, **both cores' residuals decay
to the microvolt floor and DO take a free, spurious "decision" during
acquisition** — but they take it on **different bit cycles**: the
**schematic core resolves at bit cycle 2** (still switch-damped,
transitions there, current stays at the ~1831 µA baseline), while the
**extracted core's crossing is delayed to bit cycle 3** (the first
undamped, floating cycle) — and it is specifically that delayed, undamped
decision that costs +39–40% peak current (−2545.72 / −2565.84 µA against
−1831 µA baseline).

**Common mode is ruled out as the driver.** At every matching bit cycle
above, `topp_topn_cm_mv` agrees between the two cores to within 0.03 mV (out
of ≈1815 mV, i.e. ≤ 2×10⁻⁵ of full scale) — a common-mode SHIFT from the
extracted top-plate parasitic capacitance (one of the two candidate
mechanisms the predecessor record named) is not what is happening here.

**This is metastable regeneration on an undamped node, not a bias shift or a
measurement artefact** — consistent with, and sharpening, candidate 1 from
the predecessor record ("a marginal final trial that re-decides on
successive strobes"): the comparator's free-running strobe on bit cycle 3 is
not a real SAR bit trial (the controller does not sample it — the four-leg
array has not yet taken a single real decision at that point in the
schedule), but the StrongARM latch does not know that; a strobe landing on a
near-zero, *undamped* differential regenerates slowly and draws the extra
current regardless of whether anything downstream uses the result.

**Correction to the record.** Issue #107's own thread carries a ported,
UNVERIFIED comment (from a closed, never-merged PR branch) attributing the
anomalous cycle to "bit cycle 2 (`ph2`, acquisition)". This record's own
direct, reproducible measurement — independently, both in §1's standard
5-level staircase and in §3's fine sweep below — places it at **bit cycle
3**, the first cycle after the DR-0014 switch releases the top plate, one
cycle later than that comment claimed. The distinction matters: bit cycle 2
is switch-damped on both cores and never shows an excursion in any run in
this record: it is specifically the switch-open cycle that costs the extra
current.

## 3. What remains open, stated plainly, and the instrument that would close it

**Closed by this record**: it is not a measurement-window artefact and not
the static preamp bias (both already ruled out by the predecessor record,
reconfirmed here); it is not a common-mode shift (§2); it IS a metastable,
free-running comparator decision on the one bit cycle per conversion where
the top plate is undamped, and it lands on that cycle for the extracted core
but one cycle earlier (still damped, harmless) for the schematic core, at
this one corner and input level.

**Not closed**: *why* the extracted core's crossing is delayed by exactly
one bit cycle relative to the schematic core's. The best-supported candidate
is the extracted core's real top-plate parasitic capacitance (against the
schematic's implicit, near-ideal one) slowing the bit-cycle 0–2 RC decay of
the previous conversion's residual kickback just enough that, at this one
corner and input level, the crossing that would otherwise land safely inside
the damped window (like it does at every other corner and level tested)
lands one cycle late instead. This record does not carry a direct,
net-by-net `v(se_topp)`/`v(se_topn)` capacitance comparison to prove that
quantitatively — the instrument that would close it is a targeted query of
the extracted `se_topp`/`se_topn` net capacitance against
`layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.extract.json`
/ `adc_top.para.spice`, compared against the schematic core's implicit
top-plate parasitic (DR-0007's own preamp input capacitance, the only
explicit term on the schematic side). That is a bounded follow-up, not a
prerequisite for this issue's own acceptance criteria, which ask this record
to name the mechanism or state what remains ambiguous — both are done above.

## 4. Bound: how close are the other corners (Acceptance Criteria item 2)

A fine sweep of the full-scale input level (`--levels
0.75,0.990,0.994,0.997,0.999,0.9995,0.9999,1.0000`, overriding the deck's
own 5-point staircase — see the probe's `_levels_override()`) at the tipping
corner and its two nearest PVT-grid neighbors, extracted core only (the
mechanism, §2, is a property of the extracted core; the schematic core never
shows it at any level or corner tested in either this or the predecessor
record):

| level | `i(vddc)` peak, `tt_125c_3.63v` (µA) | `i(vddc)` peak, `tt_125c_3.30v` (µA) | `i(vddc)` peak, `tt_27c_3.63v` (µA) |
|---|---|---|---|
| 0.7500 | −1838.50 | −1589.70 | −1981.88 |
| 0.9900 | −1838.40 | −1589.62 | −1981.76 |
| 0.9940 | −1838.40 | −1589.62 | −1981.76 |
| 0.9970 | −1838.40 | −1589.57 | −1981.75 |
| 0.9990 | −1838.40 | −1589.62 | −1981.75 |
| 0.9995 | −1838.40 | −1589.62 | −1981.75 |
| 0.9999 | −1838.40 | −1589.62 | −1981.75 |
| **1.0000 (conv 24)** | **−2565.61** | −1589.62 | −1981.75 |
| **1.0000 (conv 25)** | **−2565.80** | −1589.57 | −1981.75 |

**Result**: only `tt_125c_3.63v` ever shows the excursion, and only at input
level **exactly** 1.0000 — 0.9999 (≈1×10⁻⁴ below full scale, under one LSB
of 1/1024 ≈ 9.77×10⁻⁴) already shows zero excess, at −1838.40 µA, identical
to every lower level. **Neither of the two tested PVT-grid neighbors shows
any trace of the excursion at any tested level, including exactly 1.0000.**
The bit-cycle detail explains why, mechanistically (not just "the current
didn't move"): at `tt_125c_3.30v` (level 1.0, conversions 24/25) the
free-running acquisition decision resolves at bit cycle 2 — switch-damped,
like the schematic control at the tipping corner — and at `tt_27c_3.63v` it
does not resolve inside the acquisition window at all (0 transitions through
bit cycle 3; the first real transition is the genuine bit-4 trial). Neither
neighbor's residual ever gets close enough to the undamped-node knife-edge
for it to matter.

**Reading for "how much of the grid is near this boundary"**: this is a
single-corner, single-exact-code coincidence, not a wide region of the PVT ×
input-level space sitting near the same edge. The two nearest neighbors
tested (one on each independent axis — supply and temperature — of the
corner that tips) show zero measurable proximity to it, and even the tipping
corner itself has no margin below the exact top code: one part in 10⁴ of
input level is already enough to clear it. This is evidence against
extrapolating "1/27 corners" to "1/27 of operating space" — the predecessor
record's own stated caution — though it remains a 2-of-26 sample, not an
exhaustive one; a full 27-corner × fine-level sweep would close that
completely and is named as a possible further increment, not required by
this issue's Acceptance Criteria (2–3 corners, at least one PVT-grid
neighbor).

```
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core extracted --waveform \
    --levels 0.75,0.990,0.994,0.997,0.999,0.9995,0.9999,1.0000 \
    --corner tt --temp 125 --vdd 3.63 --json ...
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core extracted --waveform \
    --levels 0.75,0.990,0.994,0.997,0.999,0.9995,0.9999,1.0000 \
    --corner tt --temp 125 --vdd 3.30 --json ...
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core extracted --waveform \
    --levels 0.75,0.990,0.994,0.997,0.999,0.9995,0.9999,1.0000 \
    --corner tt --temp 27 --vdd 3.63 --json ...
```
Wall time: 272 s / 266 s / 281 s respectively, single-threaded.

## 5. Disposition

Unchanged from the predecessor record: `Power @ 1 MS/s < 1 mW` PASSES at
267.3 µW worst — 3.7x inside the ratified bound, inside the < 500 µW stretch
target — and no corner's verdict moves. **No spec line is adjusted here**
(CLAUDE.md). The mechanism is now named (§2) and the grid-proximity question
is now bounded (§4); neither finding changes the row's verdict.

**If this is worth a design change** (gating `cmpclk` to the ten real decide
phases, so the comparator never strobes on an undamped, undecided node at
all): that is a real candidate, but it touches
`design/adc-top/gen_adc_top.py::_preamble()`, which every committed `sim/`
record in this repository was taken against — out of scope for a
diagnostic-only issue, and not done here. It is left as an explicit
follow-up for whoever next touches the comparator strobe topology, rather
than filed as a fait accompli in this record.

## Environment

- PDK: gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (`~/.volare/gf180mcuD`), MiM stack `m4m5`
- ngspice: ngspice-46
- Extraction under test:
  `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`,
  remediated by `remediate_extracted.py` (PMOS body → `vdd`; input rails →
  pins; MiM untouched)
- Repo git sha: `c796b39b3454b2eb79b7eadf565c92eb15f76fad`
- Wall time: §1 452 s (extracted) + 182 s (schematic); §4 272 s + 266 s +
  281 s (extracted only, three corners) — all single-threaded
- Diagnoses (both): `sim/adc-power/records/20260806-083932-faebccc.md`
- Extends: `layout/adc-top/parasitics/records/20260806-power-cmp-anomaly.md`
- Cited by: `sim/extracted-delta-summary.md` §4.7 / §7.2

---

Diagnostic record: it mints no `sim/` corner-matrix record and makes no
spec-line claim. Append-only like everything under `sim/` — a re-run or
correction mints a new record and points back here.
