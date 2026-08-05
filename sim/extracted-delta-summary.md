# Schematic vs extracted: the post-layout delta, spec line by spec line

Issue #89 Scope item 3. This is the project-level answer to "what did the
layout cost us?" — for every ratified spec line, the schematic-level result,
the extracted post-layout result, and the delta, with the corner each was
measured at.

It is deliberately **not** a summary of everything that has been extracted. It
is a status page with one row per spec line, and a row is either *measured*
(there is an extracted `sim/` record and a delta) or *not yet measured* (with
the specific reason and what closing it needs). No row is left implicit, and
nothing here is transcribed by hand — every number in the delta tables below is
reproduced by running the command printed above it.

**Nothing in this document adjusts a spec line.** Where an extracted result
misses a target the schematic passed, it is reported as a FAIL and escalated
(CLAUDE.md: agents do not relax the ratified spec to make results pass). As of
this revision there is no such case in the benches that have run.

---

## 1. What the extracted netlist is, and what was done to it

Every extracted number below comes from **one** netlist, produced and
substantiated in [`layout/adc-top/parasitics/`](../layout/adc-top/parasitics/):

- **Source**: `klt extract ../adc_top.gds --deck gf180mcu --parasitics --top
  ADC_TOP --pdk gf180mcuD --pdk-root <resolved>`, written to
  `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`
  — 1320 devices (148 nfet, 148 pfet, 1024 MiM), 177 nets, 156 parasitic R +
  156 parasitic C, ΣR 115 320 Ω, ΣC 3730 fF.
- **Toolchain, pinned** (`sim/toolchain.json`): open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, gf180mcuD, ngspice ≥ 46 (46 in
  every run below), `klt` at the `af5791b` pin.

Two methodology choices had to be made before this netlist could be simulated
at all. Issue #89's guidance section requires both to be **stated, not silently
absorbed**, because either one made differently moves every number below.

### 1.1 PMOS body terminals — local remediation of a known upstream gap

gf180mcu's curated `klt extract` deck has no tap/well-label layer, so every
PMOS device's body (Nwell) terminal lands on an anonymous, un-pinned internal
net rather than the `vdd` tie the schematic assumes. Measured, not assumed: a
single-PMOS leaf-cell extraction's anonymous body node sits at ≈ 0 V against a
driven-low source — a full supply-rail `V_sb` error on every PMOS device.

**Path taken: local remediation**, not waiting on upstream.
[`2AMLogic/klayout-tools#555`](https://github.com/2AMLogic/klayout-tools/issues/555)
was re-checked and is still `OPEN` (2026-08-05), so
`layout/adc-top/parasitics/remediate_extracted.py` rewrites every anonymous
PMOS-body net to `vdd`, after asserting structurally that each such net appears
*only* as a PMOS body terminal (148 devices across 20 nets for `ADC_TOP`).

**This is therefore not raw `klt extract` output**, and every record says so in
its `Netlist provenance` field. The remediation's own DC verification —
`verify_remediation_dc.py`, record
[`layout/adc-top/parasitics/records/20260805-remediation-dc.md`](../layout/adc-top/parasitics/records/20260805-remediation-dc.md)
— converges 63/63 on the `cdac` PVT grid with the bodies hard-tied, against a
raw extraction whose bodies float at 3.13–3.15 V.

### 1.2 MiM capacitors — the PDK subckt, unmodified

The `--pdk gf180mcuD` extraction emits
`X … cap_mim_2f0_m4m5_noshield c_length=… c_width=…` **subckt calls**, which
bind to `sm141064_mim.ngspice` — the same subckt `sim/harness/pdk.py` resolves
and the same one the schematic CDAC instantiates.

**Choice: use the PDK MiM subckt as extracted; no rewrite, no ideal-capacitor
substitution.** This is the fair comparison against the schematic's
subckt-instantiated MiM: both sides of every delta below are the same device
model, so the delta carries the layout's geometry and interconnect, not a model
swap. `remediate_extracted.py` asserts the binding (1024 caps) and leaves the
cards untouched.

The consequence for statistical work is stated in §5: `sm141064_mim.ngspice`
contains no mismatch term at all, so this choice neither adds nor removes
capacitor mismatch — there is none to have.

### 1.3 The wrapper: extracted core, schematic everything-else

The extracted `ADC_TOP` is the CDAC analog core. It is wired into a
**schematic-level** comparator, rung-1 SAR controller and DR-0013 input-drive
network by `layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py`, which ports
`design/adc-top/gen_adc_top.py`'s own input ladder and ideal shadow DAC
verbatim rather than restating them.

So each delta below isolates **the analog core**. It is not a full-chip
post-layout number, and this document does not claim it is.

---

## 2. How to re-derive every number here

```bash
# 1. Regenerate the extracted-core deck from the committed extraction (asserts
#    byte-identity with the committed fixture; writes nothing on --check).
python3 layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py --check

# 2. Re-run the SCHEMATIC manifest against the extracted netlist. -j 1 and the
#    raised timeout are load-bearing -- see sim/harness/README.md, "Run an
#    extracted deck at -j 1". ~41 min for 27 points on an 8-core host.
python3 sim/run_corners.py adc-inl-dnl \
    --netlist sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice \
    --netlist-provenance "extracted (remediated) -- ..." \
    --corners tt ss ff -j 1 --timeout 1200 \
    --supersedes 20260802-141402-1224e11

# 3. Derive the delta table from the two committed records.
python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
    --schematic 20260802-141402-1224e11 \
    --extracted  20260805-203322-3b6d7b7
```

Step 2 uses `sim/adc-inl-dnl/testbench/tb.json` **unmodified**: the same claim,
analyses, measure expressions and checks that produced the schematic record.
That is the point of `--netlist` — a delta between two independently-written
measurement decks is not a delta between two circuits.

Step 3 parses the two records' own per-corner Result tables. It does not
recompute a single pass/fail verdict; verdicts are read out of the records.

---

## 3. Spec-line status

| Ratified row | Schematic | Extracted | Delta | State |
|---|---|---|---|---|
| **INL** < 1 LSB (< 0.5 stretch) | −0.1082 LSB (`ss_-40c_2.97v`) | **−0.1109 LSB** (`ss_-40c_2.97v`) | −0.0027 LSB (−2.5 %) | **measured — PASS, stretch too** |
| **DNL** < 1 LSB (< 0.5 stretch) | 0.1003 LSB (`tt_27c_2.97v`) | **0.1003 LSB** (`tt_27c_3.30v`) | +0.0001 LSB (+0.1 %) | **measured — PASS, stretch too** |
| Gain error, converter-level (unbudgeted, no ratified row — §3.5 of the suite memo) | −2.0144 LSB (`ff_125c_3.63v`) | **−2.0081 LSB** (`ff_125c_3.63v`) | +0.0063 LSB (+0.3 %) | **measured** — see §4.3 |
| ENOB @ Nyquist > 9.0 | 9.163 bits (`ss_125c_2.97v`) | — | — | not yet run — §6.1 |
| SFDR @ Nyquist ≥ 62 dB | 61.33 dB (`ss_125c_2.97v`) — **already FAIL** | — | — | not yet run — §6.1, and read §7 first |
| Power @ 1 MS/s < 1 mW | 183.3 µW (`ff_-40c_3.63v`) | — | — | not yet run — §6.2 |
| Gain error, systematic (DR-0012/13 scope: sampling-switch injection) ≤ 0.5 LSB | 0.0045–0.0088 LSB | — | — | not yet run — §6.3 |
| Offset ≤ 2 LSB (3σ mismatch) | `sim/comparator-offset-mc/` | — | n/a | comparator is schematic-level in this wrapper — §5 |
| INL/DNL under 3σ CDAC mismatch | `sim/mc-cdac-mismatch/` | — | n/a | **not applicable** — §5 |
| Rate (1 MS/s) closure | #12's record | — | — | not yet run — §6.3 |

---

## 4. The static-linearity delta, in full

- schematic record: [`20260802-141402-1224e11`](adc-inl-dnl/records/20260802-141402-1224e11.md) (DR-0014 bottom-plate topology, #61 / PR #64)
- extracted record: [`20260805-203322-3b6d7b7`](adc-inl-dnl/records/20260805-203322-3b6d7b7.md)
- shared corners: **27** (`tt`/`ss`/`ff` × −40/27/125 °C × 2.97/3.30/3.63 V) — every corner in the extracted record has a schematic counterpart
- per-corner verdicts, read from the records: schematic **all PASS**, extracted **all PASS**
- corners whose verdict changed schematic → extracted: **none**

### 4.1 Headline

```
python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
    --schematic 20260802-141402-1224e11 --extracted 20260805-203322-3b6d7b7 \
    --only inl_worst_lsb dnl_worst_lsb gain_err_lsb vref_droop_mv
```

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `inl_worst_lsb` | -0.108233 (`ss_-40c_2.97v`) | -0.110911 (`ss_-40c_2.97v`) | -0.002678 | -2.474 | 0.00321 |
| `dnl_worst_lsb` | 0.100251 (`tt_27c_2.97v`) | 0.100348 (`tt_27c_3.30v`) | +9.7e-05 | +0.09676 | 0.0407528 |
| `gain_err_lsb` | -2.01444 (`ff_125c_3.63v`) | -2.00813 (`ff_125c_3.63v`) | +0.00631 | +0.3132 | 0.00661 |
| `vref_droop_mv` | 0.263 (`ss_125c_3.63v`) | 0.323 (`ss_-40c_3.63v`) | +0.06 | +22.81 | 0.061 |

`inl_worst_lsb` / `dnl_worst_lsb` are reduced spec-line quantities the records
do not carry as their own columns; the tool derives them from the
`inl_t*_lsb` / `dnl_t*_t*_lsb` columns (worst by magnitude, sign kept).

**Read `max per-corner delta` alongside `delta (worst)`.** A worst-vs-worst
delta hides a per-corner swing that moves the worst corner around: DNL's
worst-vs-worst delta is +0.0001 LSB, but some individual corner's DNL moves by
up to **0.041 LSB**. The spec-line conclusion (PASS with 10× margin) is
unaffected either way; the distinction matters for anyone reading these numbers
as a parasitic model rather than as a verdict.

### 4.2 Per transition

Full table: run the command in §2 step 3 without `--only`. The pattern worth
recording is that the extracted INL degradation is **not uniform across the
code range — it grows toward full scale**, which is the signature of top-plate
and interconnect parasitic capacitance loading the array:

| transition | schematic worst INL | extracted worst INL | delta | delta % |
|---|---|---|---|---|
| `inl_t2_lsb` | -0.0525844 | -0.0538944 | -0.00131 | -2.5 |
| `inl_t128_lsb` | -0.105403 | -0.107494 | -0.002091 | -2.0 |
| `inl_t384_lsb` | -0.108233 | -0.110911 | -0.002678 | -2.5 |
| `inl_t640_lsb` | -0.08597 | -0.0916761 | -0.0057061 | -6.6 |
| `inl_t768_lsb` | -0.0251871 | -0.0314642 | -0.0062771 | -24.9 |
| `inl_t896_lsb` | -0.0783432 | -0.085378 | -0.0070348 | -9.0 |
| `inl_t1022_lsb` | -0.0640824 | -0.0712504 | -0.007168 | -11.2 |

The largest *relative* deltas sit at the top of the range; the largest
*absolute* INL still sits where the schematic's did (`inl_t384`,
`ss_-40c_2.97v`). The layout did not move the worst transition.

### 4.3 `gain_err_lsb`: this run does not reproduce record `20260805-163000-e8017f2`'s −0.55 LSB delta

This must be stated plainly rather than quietly averaged in.

Record [`20260805-163000-e8017f2`](adc-inl-dnl/records/20260805-163000-e8017f2.md)
(merged in PR #96) reported an extracted-vs-schematic `gain_err_lsb` delta of
**−0.5146 … −0.6340 LSB, mean −0.5552 LSB**, attributed to top-plate /
interconnect parasitic gain attenuation. **The like-for-like re-measurement
above does not reproduce it**: the delta is **+0.00285 … +0.00661 LSB, mean
+0.00520 LSB** over the same 27 corners — two orders of magnitude smaller, and
of the opposite sign.

The two runs measure the same core with the same formula and read the same
node. They differ in **how the input reaches the two endpoint transitions**:

| | record `…-163000-e8017f2` (PR #96) | record `…-203322-3b6d7b7` (this run) |
|---|---|---|
| deck | bespoke, `measure_extracted_gain_err.py` | the `adc-inl-dnl` manifest, unmodified |
| transitions simulated | 2 (endpoints 1 and 1023 only) | 18 (the full probed set) |
| input step into transition 1023 | ~1022 LSB, in one 10 ns ramp | ≤ 126 LSB, walking up the ladder |
| settling budget before the decision | `INL_CONV_PER_POINT = 1` conversion (1000 ns) | identical |

At `tt_-40c_2.97v`, the **lower** endpoint agrees to all printed digits
(`e1` = `terr_t1_lsb` = **1.02068** in both), while the **upper** endpoint does
not (`e1023` = −1.52863 vs `terr_t1023_lsb` = −0.972589, a 0.556 LSB gap that
is essentially the whole reported delta). The schematic bench's own value at
that corner is −0.978255 — i.e. **the manifest-driven extracted and schematic
runs agree with each other to 0.006 LSB and both disagree with the bespoke
deck.**

An error that appears only at the endpoint reached by a near-full-scale step,
and not at the endpoint reached with a full warmup, is the signature of an
**incompletely acquired input sample**, not of a parasitic gain term — the same
1000 ns conversion budget must absorb an 8× larger input step through an
RC-laden input network.

**Disposition, taken deliberately:**

- Record `20260805-163000-e8017f2` is **not edited or deleted** — `sim/` is
  append-only (`sim/README.md`, "Append-only rule"). It stands as what that
  measurement produced.
- The number this document, and any downstream consumer such as #53's
  top-plate-parasitic adjudication, should use for the extracted converter-level
  gain error is **−2.0081 LSB worst (`ff_125c_3.63v`), delta +0.006 LSB vs
  schematic** — the like-for-like value, from a run that used the schematic
  bench's own manifest.
- The decisive control — running the bespoke 2-endpoint deck against the
  *schematic* core, which should reproduce ≈ −2.55 LSB if the deck rather than
  the layout is responsible — has **not** been run here, and is filed as a
  follow-up rather than asserted. Until it is, the mechanism above is the
  best-supported explanation, not a closed finding.

**Update (issue #98, record [`20260805-230438-048ff7e`](adc-inl-dnl/records/20260805-230438-048ff7e.md)) — the control has now been run, and confirms the mechanism above.**

The bespoke deck's own 2-endpoint stimulus and error-node instrumentation,
wired onto the **schematic** `ADC_TOP` core (`design/adc-top/gen_adc_top.py`'s
`_core()` — zero layout parasitics) instead of the extracted `.SUBCKT`, reports
**mean `gain_err_lsb` = −2.5545 LSB** (range −2.5139 … −2.6278) over the same
27 `tt`/`ff`/`ss` × temp × supply corners — reproducing record
`20260805-163000-e8017f2`'s extracted-core reading (mean −2.5572 LSB) to
within **+0.0027 LSB mean** (range +0.0018 … +0.0045), and disagreeing with
the schematic-manifest baseline (`20260802-141402-1224e11`, mean −2.0020 LSB)
by essentially the *same* −0.55 LSB gap record `20260805-163000-e8017f2`
reported. A core with **no layout parasitics at all** cannot produce a
parasitic-capacitance gain term; the −0.55 LSB delta is therefore **the
bespoke deck's own methodology** — the near-full-scale single-ramp step into
transition 1023 outrunning the DR-0013 input network's acquisition within one
1000 ns conversion, exactly as diagnosed above — **not** a real extracted-layout
effect.

**This closes the open question left above**: the number this document and any
downstream consumer (including #53's adjudication) should use for the
extracted converter-level gain error remains **−2.0081 LSB worst
(`ff_125c_3.63v`), delta +0.006 LSB vs schematic** — record
`20260805-203322-3b6d7b7`'s manifest-driven reading, now **confirmed** rather
than merely preferred. Record `20260805-163000-e8017f2` is **still not edited
or deleted** (append-only); its own numbers remain valid as a measurement of
what its own deck measured — the disposition above only reassigns the
*interpretation* of its extracted-vs-schematic delta from "parasitic gain
attenuation" to "input-acquisition artifact of the 2-endpoint deck". No
secondary control (raising the transition-1023 settling budget) was needed:
the result landed cleanly on the "deck responsible" side of issue #98's
decision tree rather than sitting ambiguously between the two reference
points.

---

## 5. Scope item 2 — Monte Carlo on the extracted netlist: the explicit answer

Issue #89 Scope item 2 asks for a #14 Monte Carlo re-run against the extracted
netlist "if the extraction flow's parasitic/mismatch models support statistical
variation — state explicitly if not." Stating it explicitly:

**1. #14's bench has no netlist to swap.** `sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py`
is a *behavioral* numpy model of CDAC unit-cap mismatch, not an ngspice deck. It
never invokes ngspice. There is no `--netlist` to point at an extraction; a
"re-run against the extracted netlist" is not a defined operation on it.

**2. The reason it is behavioral applies equally to the extracted netlist.** The
gf180mcu open PDK ships **no local capacitor mismatch model** —
`cap-local-mismatch` and `moscap-statistics` are both `ABSENT` findings from
`sim/tools/pdk_mismatch_audit.py` (`sim/device-characterization-report.md` §5.1).
Independently confirmed here for the exact subckt this extraction binds to:
`sm141064_mim.ngspice` contains no `agauss`, no `mis_*` term and no
`sw_stat_mismatch` reference at all. An ngspice Monte Carlo of the extracted
CDAC would report *exactly zero* capacitor mismatch regardless of trial count —
a silent false pass, which is worse than no number.

Extraction does not change this. `klt extract --parasitics` emits ideal R and C
values plus PDK device calls; it carries no statistical construct of its own, so
it cannot supply the mismatch the PDK omits.

**3. What *is* statistically available on the extracted netlist, and why it is
not run here.** The extracted MOS devices are `X … nfet_03v3` / `pfet_03v3` PDK
subckt calls, which *do* pick up the PDK's `fets_mm` threshold-mismatch
statistics when `sw_stat_mismatch = 1` (the mechanism `sim/comparator-offset-mc/`
uses). So a MOS-mismatch Monte Carlo of the extracted core is technically
supported. It is not run in this increment because the ratified rows that ride
on MOS mismatch — Offset, and the comparator's contribution — live in the
**comparator**, which is schematic-level in this wrapper (the extracted core is
`ADC_TOP`, the CDAC array and its switches). Running it would re-measure a
schematic comparator and label the result "extracted". `ADC_BLOCK` (core +
comparator) has been extracted and remediated, and is the netlist that would
make that run meaningful; it is named in §6.4 as remaining work, not skipped
silently.

**Net answer: Scope item 2 is answered, not deferred, for the CDAC-mismatch
half — that run is not possible on any netlist in this PDK, extracted or
schematic, and #14's behavioral model remains the only available instrument.
The MOS-mismatch half is possible and is deferred, with the netlist it needs
named.**

---

## 6. What is not yet measured, and what each one needs

### 6.1 ENOB / SFDR / THD (`sim/adc-enob-fft/`)

Needs its own extracted-core deck, on the pattern of
`gen_extracted_inl_dnl_tb.py`: the FFT bench's coherent-sampling stimulus and
`se_*`-tagged measurement nodes ported onto `_core_extracted()`. Compute is the
obstacle, not the method: that deck runs **66 conversions per PVT point**
(`FFT_WARMUP_CONV = 2` + `FFT_N = 64`) against this bench's 20
(`INL_WARMUP_CONV = 2` + 18 probed transitions × `INL_CONV_PER_POINT = 1`),
i.e. ≈ 3.3× the 86 s/point measured here — call it **~1.5 h for the same
27-point grid**, single-threaded.

### 6.2 Power (`sim/adc-power/`)

Does **not** port mechanically. Its claim is a per-block supply decomposition
(comparator / CDAC / logic measured on separate supply branches), and the
core swap replaces exactly one of those blocks with a subckt whose internal
supply topology differs from the schematic's. The decomposition has to be
re-derived against the extracted core's actual supply pins before the bench
means anything post-layout; that is a methodology task, not a re-run.

### 6.3 Gain error (DR-0012/13 row), rate closure

Both reuse other experiments' testbenches (`sim/dr0014-sampling/`,
`sim/timing-budget-closure/`). Each needs the same treatment as §6.1: an
extracted-core variant of that deck.

### 6.4 The `cdac` capacitor-corner set, and `ADC_BLOCK`

Two coverage gaps, both stated rather than papered over:

- **Corner set.** This run used `tt`/`ss`/`ff` (27 points) rather than the
  manifest's default `cdac` set (7 process corners × 3 × 3 = 63 points),
  because those 27 are exactly the corners the schematic baseline ran — so
  every extracted corner has a counterpart to difference against. `ff`/`ss`
  *do* include `mimcap_ff`/`mimcap_ss`, so the MiM process corners are
  exercised on both sides of every delta above; what is missing is the `cdac`
  set's **isolation** of individual device-class corners.

  **Schematic half now closed** (issue #89 Scope item 7, first half): record
  [`20260805-220405-bff6eaf`](adc-inl-dnl/records/20260805-220405-bff6eaf.md)
  runs the manifest's own `cdac` corner set — `tt`, `cap_ff`, `cap_ss`,
  `mim_ff`, `mim_ss`, `moscap_ff`, `moscap_ss` × 3 temperatures × 3 supplies,
  63/63 points, **all PASS** (2556 s wall at `-j 1` on an 8-core host — `-j 1`
  matters here too: a schematic-only point still measured 4–8x user CPU vs
  wall time under ngspice-46's own OpenMP threading, so `-j 4` reproduced the
  same oversubscription trap §"Run an extracted deck at -j 1" in
  `sim/harness/README.md` describes for the much heavier extracted netlist —
  a single `cap_ff_-40c_3.30v` point that converges in 34 s standalone timed
  out at the default 300 s under 4-way contention). `gain_err_lsb` stays
  within 0.006–0.052 % spread across the whole grid (well inside the `cdac`
  set's per-corner sensitivity floor), and every worst-INL/worst-DNL/gain-error
  reading matches the `mos`-set baseline (`20260802-141402-1224e11`) to within
  the same few-percent band that record's own MOS-corner spread showed — i.e.
  the capacitor-family corners this run isolates do not, on the schematic
  core, move linearity outside what the MOS corners already bounded.

  **Still open**: the matching **extracted**-side `cdac`-set run (≈ 95 min at
  `-j 1`, scaling this record's own 27-point/2436 s extracted throughput —
  see §4 — to 63 points) and the pairwise schematic-vs-extracted delta table
  in the format of §4, corner-for-corner over the 7 `cdac` corners. Until
  that lands, Scope item 7 is half-closed: the missing schematic baseline
  this section previously flagged no longer blocks it, but the comparison
  itself has not been run.
- **`ADC_BLOCK`.** `remediate_extracted.py` already generalises to it (160
  PMOS devices / 25 body islands retied, 1024 MiM caps confirmed, DC verified
  63/63). Using it in place of `ADC_TOP` would put the **comparator** inside
  the extracted boundary too, which is what §5's MOS-mismatch Monte Carlo and
  any comparator-offset post-layout claim require.

---

## 7. Baseline caveat: the SFDR row was already failing before layout

Issue #89 Scope item 6, restated here so the ENOB/FFT row is not misread when
it lands: **the schematic-level SFDR baseline is already a FAIL** — 61.33 dB
against the ≥ 62 dB target, a 0.67 dB miss, at one corner of nine
(`ss_125c_2.97v`), recorded in `spec/testbench-suite-memo.md` §11.2 for the
DR-0014 topology. The other eight corners span 63.62–69.98 dB.

A continued extracted-netlist SFDR failure at that corner is **expected
pre-existing baseline behaviour** (schematic FAIL → extracted FAIL), not a new
layout-induced regression, and must be reported as such. What *would* be a new
finding is the extracted result failing at corners the schematic passed, or the
margin at `ss_125c_2.97v` widening materially. Read §11.2 before writing that
row.

---

## 8. Provenance of this document

| | |
|---|---|
| Extraction | `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice` |
| Remediation | `layout/adc-top/parasitics/remediate_extracted.py` (PMOS body → `vdd`; input rails → pins; MiM untouched) |
| Deck generator | `layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py` |
| Manifest | `sim/adc-inl-dnl/testbench/tb.json`, **unmodified** |
| Records diffed | `20260802-141402-1224e11` (schematic) → `20260805-203322-3b6d7b7` (extracted) |
| Delta tool | `sim/tools/schematic_vs_extracted.py` |
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| ngspice | 46 |
| Grid | 27 points, 27 completed, 0 non-convergent; 2436 s wall at `-j 1` |

Every `sim/` record cited here carries its own `Netlist provenance` field, and
no extracted record replaces a schematic one — they append alongside each
other, per `sim/README.md`, "Extracted vs schematic semantics".
