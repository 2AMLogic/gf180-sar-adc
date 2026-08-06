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
was `OPEN` when this path was chosen and has since **closed** (2026-08-05,
via [`klayout-tools#581`](https://github.com/2AMLogic/klayout-tools/issues/581),
re-checked 2026-08-06) — but that PR shipped only the Shape-2 fix (surfacing
the anonymous PMOS-body net name as a structured JSON signal); the Shape-1
opt-in `--tie-well-to`-style re-biasing flag that would let `klt extract`
itself emit a `vdd`-tied body was explicitly deferred to its own follow-up
issue and has not landed. So `layout/adc-top/parasitics/remediate_extracted.py`
still does the retie locally: it rewrites every anonymous PMOS-body net to
`vdd`, after asserting structurally that each such net appears *only* as a
PMOS body terminal (148 devices across 20 nets for `ADC_TOP`).

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
| **INL** < 1 LSB (< 0.5 stretch) | −0.1082 LSB (`ss_-40c_2.97v`) | **−0.1109 LSB** (`ss_-40c_2.97v`) | −0.0027 LSB (−2.5 %) | **measured — PASS, stretch too** (§4.1; `cdac`-set isolation confirms, §4.5) |
| **DNL** < 1 LSB (< 0.5 stretch) | 0.1003 LSB (`tt_27c_2.97v`) | **0.1003 LSB** (`tt_27c_3.30v`) | +0.0001 LSB (+0.1 %) | **measured — PASS, stretch too** (§4.1; `cdac`-set isolation confirms, §4.5) |
| Gain error, converter-level (unbudgeted, no ratified row — §3.5 of the suite memo) | −2.0144 LSB (`ff_125c_3.63v`) | **−2.0081 LSB** (`ff_125c_3.63v`) | +0.0063 LSB (+0.3 %) | **measured** — see §4.3 and §4.4 (an earlier −0.55 LSB delta was shown by null control to be a settling artefact) |
| ENOB @ Nyquist > 9.0 | 9.163 bits (`ss_125c_2.97v`) | **9.103 bits** (`ss_125c_2.97v`) | −0.060 bits (−0.65 %) | **measured — PASS** (§4.6) |
| SFDR @ Nyquist ≥ 62 dB | 61.33 dB (`ss_125c_2.97v`) — **already FAIL** | **60.11 dB** (`ss_125c_2.97v`) — **still FAIL** | −1.22 dB (−1.99 %) | **measured — FAIL, expected baseline** (§4.6, and read §7 first) |
| Power @ 1 MS/s < 1 mW | 183.3 µW (`ff_-40c_3.63v`, f050) | **267.3 µW** (`tt_125c_3.63v`, f100); **184.5 µW** (`ff_-40c_3.63v`, f050) excluding the one comparator-metastability cell | +84.0 µW (+45.8 %) as measured; **+1.2 µW (+0.64 %)** excluding that cell | **measured — PASS**, 3.7× margin (§4.7). Read §4.7's disposition of the outlier before quoting the +45.8 % |
| Gain error, systematic (DR-0012/13 scope: sampling-switch injection) ≤ 0.5 LSB | 0.0045–0.0088 LSB | — | — | not yet run — §6.3 |
| Offset ≤ 2 LSB (3σ mismatch) | `sim/comparator-offset-mc/` | — | n/a | comparator is schematic-level in the closed runs — §5. A comparator-inclusive (`ADC_BLOCK`) attempt found a functional defect before any measurement was taken — §6.4 |
| INL/DNL under 3σ CDAC **capacitor** mismatch | `sim/mc-cdac-mismatch/` | — | n/a | **not applicable** — the PDK has no local cap-mismatch model on either netlist, §5 |
| Transition error under **MOS** local mismatch (no ratified row; the statistical half of Scope item 2) | — (schematic-side equivalent not run at this transition) | **σ = 1.99e-3 LSB**, N = 120, `tt_27c_3.30v`, transition 256 | n/a — capability claim, not a delta | **measured** — §5, null control σ = 0 |
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
  the layout is responsible — was filed as a follow-up when this section was
  first written. **It has since been run, and it does reproduce it.** See
  §4.4.

### 4.4 The control, run: the schematic core reproduces the "extracted" number

`layout/adc-top/parasitics/probe_gain_err_settling.py` drives the bespoke
deck's own two-point ladder, then **holds** transition 1023 for N further
conversions and reads the same error node at each — against **either** core,
changing nothing else in the deck. Record
[`20260805-224500-2c21be4`](adc-inl-dnl/records/20260805-224500-2c21be4.md),
3 PVT points × 2 cores:

| corner | `gain_err_lsb` @ hold 1 — extracted / **schematic** | @ hold 8 — extracted / **schematic** |
|---|---|---|
| `tt_27c_2.97v` | −2.5601 / **−2.5570** | −1.9865 / **−1.9895** |
| `ss_-40c_2.97v` | −2.5946 / **−2.5918** | −1.9839 / **−1.9873** |
| `ff_125c_3.63v` | −2.5406 / **−2.5388** | −2.0038 / **−2.0077** |

Hold 1 is *exactly* the instant `measure_extracted_gain_err.py` reads. At that
instant the **schematic** core — which has no parasitics at all — sits within
**0.003 LSB** of the extracted one and reproduces the whole −2.54 … −2.59 LSB
figure that record `20260805-163000-e8017f2` attributed to layout. By hold 2
both arms have collapsed onto ≈ −1.99 … −2.01 LSB, the value the 18-transition
manifest reports on both netlists. The extracted-minus-schematic difference is
≤ 0.004 LSB at every hold length and every corner probed.

The probe was built able to say "no": had `e1023` been flat across the hold,
step size would not have been the explanation and the script reports that
instead. It is not flat — it moves 0.56 LSB between hold 1 and hold 2 — and it
moves the same way on both cores.

**The mechanism in §4.3 is therefore closed, not merely best-supported.** The
number to use everywhere, including #53's top-plate-parasitic adjudication,
is the like-for-like **−2.0081 LSB worst, delta +0.006 LSB vs schematic**; the
drawn top-plate / interconnect parasitic adds no measurable systematic gain
error on top of the schematic's ≈ −2.00 LSB DR-0012 term. Record
`20260805-163000-e8017f2` remains unedited and undeleted per `sim/README.md`'s
append-only rule; `20260805-224500-2c21be4` carries it in **Supersedes**, for
its `gain_err_lsb` result and the parasitic attribution only.

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

### 4.5 The `cdac` capacitor-corner-set delta (Scope item 7, now closed)

§4's 27-point grid uses `tt`/`ss`/`ff` because those are the corners the
original schematic baseline (`20260802-141402-1224e11`) ran — every MOS
corner, but the capacitor families sit at `*_typical` throughout (`ff`/`ss`
skew every `.lib` section, capacitors included, but do not *isolate* them —
see `sim/harness/README.md`, "Why the capacitor corners matter here"). The
`cdac` corner set (`tt`, `cap_ff`, `cap_ss`, `mim_ff`, `mim_ss`, `moscap_ff`,
`moscap_ss`) isolates each capacitor-family skew individually, which is what a
CDAC's own linearity claim actually rides on.

- schematic record: [`20260805-220405-bff6eaf`](adc-inl-dnl/records/20260805-220405-bff6eaf.md) (PR #100, 63/63 PASS)
- extracted record: [`20260806-052258-8d36824`](adc-inl-dnl/records/20260806-052258-8d36824.md) (this increment, 63/63 PASS, 1100 s wall at `-j 6 --ngspice-threads 1`)
- both runs use `sim/adc-inl-dnl/testbench/tb.json`'s **default** `"corners": ["cdac"]` unmodified — no `--corners`/`--corner-set` override on either side
- shared corners: **63** (7 process corners × 3 temperatures × 3 supplies) — every corner in the extracted record has a schematic counterpart
- per-corner verdicts, read from the records: schematic **all PASS**, extracted **all PASS**
- corners whose verdict changed schematic → extracted: **none**

```bash
python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
    --schematic 20260805-220405-bff6eaf --extracted 20260806-052258-8d36824 \
    --only inl_worst_lsb dnl_worst_lsb gain_err_lsb vref_droop_mv
```

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `inl_worst_lsb` | -0.103629 (`cap_ff_-40c_2.97v`) | -0.106421 (`cap_ff_-40c_2.97v`) | -0.002792 | -2.694 | 0.003094 |
| `dnl_worst_lsb` | 0.103599 (`cap_ff_27c_2.97v`) | 0.105346 (`cap_ff_27c_2.97v`) | +0.001747 | +1.686 | 0.0354985 |
| `gain_err_lsb` | -2.00234 (`cap_ff_-40c_3.63v`) | -1.99676 (`cap_ff_-40c_3.63v`) | +0.00558 | +0.2787 | 0.00639 |
| `vref_droop_mv` | 0.264 (`cap_ss_27c_3.63v`) | 0.324 (`cap_ss_27c_3.63v`) | +0.06 | +22.73 | 0.061 |

**Reading this alongside §4.1.** The worst corner for INL/DNL/gain-error is
`cap_ff` (both `-40c` extremes), not the `mos`-set's `ss_-40c`/`ff_125c`
corners §4.1 reports — expected, since `cap_ff` is the one corner in this set
that skews *both* capacitor families fast while leaving MOS untouched, and
this array's linearity is capacitor-ratio-dominated. The magnitude and sign of
every delta here matches §4.1's pattern closely (worst INL/DNL move by a few
percent, degrading toward full scale; `gain_err_lsb` moves by +0.006 LSB,
matching §4.3/§4.4's now-closed reading to 3 decimal places) — **isolating the
capacitor corners individually does not surface anything the combined `ff`/`ss`
sweep missed.** `vref_droop_mv`'s +22.7% delta is the same reference-buffer
effect §4.1 already reports at the same magnitude; it is not a spec line (no
ratified row names it) and is unchanged in character here.

**Disposition**: Scope item 7 is closed. The schematic half (PR #100) and the
extracted half (this record) now exist at the same 63-point `cdac` grid, both
generated by the unmodified manifest per §1.3/§2's methodology, and the
pairwise delta is derived by `schematic_vs_extracted.py`, not transcribed. The
`ADC_BLOCK` (comparator-inclusive) extension named in the old §6.4 remains a
separate, still-open item — see §6.4 below — and is not part of this item's
scope.

### 4.6 ENOB / SFDR / THD (Scope item 1's dynamic half, now closed)

`layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py` ports
`gen_adc_top.fft_netlist()` onto the extracted core exactly as
`gen_extracted_inl_dnl_tb.py` ports `inl_netlist()` (§1.3): same coherent
64-sample sine, same `se_*`-tagged conversion chain, same gated ideal-shadow
error node (`gen_extracted_core_tb.shadow_dac_and_error(gated=True)`, called
directly rather than re-derived — this deck needed no bespoke copy because
it has no committed byte-identity fixture predating that shared emitter).
`sim/run_corners.py adc-enob-fft --netlist ... --netlist-provenance
extracted` runs `sim/adc-enob-fft/testbench/tb.json` **unmodified**.

**Grid, and why it is a 9-point subset rather than 27.** The schematic
baseline itself (`20260802-141402-1224e11`) is a 9-point subset —
`tt`/`ss`/`ff` × 125 °C only × 3 supplies — per the two-stage corner
strategy `spec/testbench-suite-memo.md` §5 states: the coherent-sampling FFT
is the single most expensive bench per point (66 conversions vs. the static
deck's 18–20), so it runs only at the temperature the cheap full-grid decks
and `sim/comparator-preamp-noise/` jointly identify as worst
(settling/linearity-worst `ss` and independently noise-worst `ff`, both at
125 °C). This run reuses that **same** 9-point grid, unchanged, so the two
captures are point-for-point comparable rather than comparing two different
corner sets — the same discipline §4's `tt`/`ss`/`ff` 27-point grid already
follows relative to the `cdac`-set default.

**Compute, measured**: 9 points, 230 s/point single-threaded (matching the
static deck's ≈3.3× ratio the original §6.1 estimate predicted), completed
in **550 s wall at `-j 6 --ngspice-threads 1`** on this 8-core host.

**Citability correction.** The first capture of this grid,
[`20260806-060520-72a230a`](adc-enob-fft/records/20260806-060520-72a230a.md),
was taken against a dirty working tree and self-flagged as "not citable as a
clean-tree result" (its own `Netlist provenance` field states this). A
second, independently-run capture of the identical deck against a clean tree
(discarded as PR #104, a verified duplicate of this slice) reproduced the
*same* per-corner codes with a clean tree, establishing that the dirty-tree
condition did not affect the result — but citability itself is a provenance
property, not just a numerical-agreement one, so the minimal fix is a clean
re-run of the same deck rather than asserting the discarded duplicate's
numbers. That re-run is
[`20260806-081350-862d054`](adc-enob-fft/records/20260806-081350-862d054.md)
(`Supersedes: 20260806-060520-72a230a`), taken against a clean tree at the
same commit this document ships with — its per-corner `Result` table is
byte-identical to `20260806-060520-72a230a`'s, confirming the dirty-tree
capture was numerically sound; only its citability status changes. All
`sim/extracted-delta-summary.md` references below now cite the clean record.

- schematic record: [`20260802-141402-1224e11`](adc-enob-fft/records/20260802-141402-1224e11.md) (9/9 PASS on the harness's coverage-witness verdict — see the note below on what that PASS does and does not cover)
- extracted record: [`20260806-081350-862d054`](adc-enob-fft/records/20260806-081350-862d054.md) (clean-tree re-run of the prior increment's `20260806-060520-72a230a`, 9/9 PASS, same meaning)
- shared corners: **9** (`tt`/`ss`/`ff` × 125 °C × 2.97/3.30/3.63 V) — every corner in the extracted record has a schematic counterpart
- per-corner harness verdicts, read from the records: schematic **all PASS**, extracted **all PASS**, none changed

**What the harness PASS covers, restated so it is not misread here**: the
coverage witnesses (`code_max`/`code_min` — the sine actually drove the
converter near full scale without clipping) and the `vref_droop_mv`
corner-sensitivity floor. It does **not** cover the ENOB and SFDR rows
themselves — those are spectral quantities, computed by
`sim/adc-enob-fft/testbench/analyze_fft.py` from each record's own raw
per-corner logs, exactly as the schematic record's own note states.

```bash
python3 sim/tools/schematic_vs_extracted.py adc-enob-fft \
    --schematic 20260802-141402-1224e11 --extracted 20260806-081350-862d054 \
    --only code_max code_min vref_droop_mv

python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/20260806-081350-862d054/ --markdown --sigma-extra-lsb 0.0488
```

`--sigma-extra-lsb 0.0488` reuses `spec/testbench-suite-memo.md` §4.3's
composed noise term (153.2 µV rms comparator input-referred noise worst +
35.3 µV rms sampling `kT/C`) unchanged: that term is a property of the
**comparator and the sampling network**, both schematic-level in this
wrapper (issue #89 Scope item 0), not of the CDAC layout this run swaps in
— composing the same noise budget onto both spectra is the correct
like-for-like comparison, not a shortcut.

**Harness-measured columns** (`schematic_vs_extracted.py`):

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `code_max` | 990 (`ff_125c_2.97v`) | 990 (`ff_125c_2.97v`) | +0 | +0 | 0 |
| `code_min` | 33 (`ff_125c_2.97v`) | 33 (`ff_125c_2.97v`) | +0 | +0 | 0 |
| `vref_droop_mv` | 2.049 (`ss_125c_3.63v`) | 2.317 (`ss_125c_3.63v`) | +0.268 | +13.08 | 0.284 |

No clipping on either side (`code_max`/`code_min` identical to the digit),
same droop-worst corner, same pattern §4.1/§4.5 already report for this
node (a reference-buffer effect, not a spec line).

**Spectral columns**, `analyze_fft.py` on each side's own raw logs, ENOB
composed with the noise term above:

| corner-id | schematic ENOB composed | extracted ENOB composed | Δ ENOB | schematic SFDR | extracted SFDR | Δ SFDR |
|---|---|---|---|---|---|---|
| `tt_125c_2.97v` | 9.571 | 9.604 | +0.033 | 64.67 | 65.03 | +0.36 |
| `tt_125c_3.30v` | 9.868 | 9.896 | +0.028 | 69.14 | 70.05 | +0.91 |
| `tt_125c_3.63v` | 9.901 | 9.804 | −0.097 | 68.96 | 67.72 | −1.24 |
| `ss_125c_2.97v` | **9.163** | **9.103** | **−0.060** | **61.33 — FAIL** | **60.11 — FAIL** | **−1.22** |
| `ss_125c_3.30v` | 9.561 | 9.541 | −0.020 | 63.62 | 64.48 | +0.86 |
| `ss_125c_3.63v` | 9.653 | 9.709 | +0.056 | 65.99 | 67.52 | +1.53 |
| `ff_125c_2.97v` | 9.888 | 9.998 | +0.110 | 69.45 | 71.67 | +2.22 |
| `ff_125c_3.30v` | 9.744 | 9.741 | −0.003 | 67.32 | 69.68 | +2.36 |
| `ff_125c_3.63v` | 9.918 | 9.929 | +0.011 | 69.98 | 68.99 | −0.99 |

(ENOB in bits, SFDR in dB. Bold row is the worst corner on both sides —
`ss_125c_2.97v`, the same settling-worst corner §11.6 of the memo names.)

**ENOB @ Nyquist > 9.0**: worst-corner delta **−0.060 bits (−0.65 %)**, max
per-corner swing 0.110 bits (`ff_125c_2.97v`). **9.103 bits worst — still
PASS**, 0.103 bits of margin over the ratified row (was 0.163 bits
schematic). The layout narrows the margin but does not threaten the row.

**SFDR @ Nyquist ≥ 62 dB**: worst-corner delta **−1.22 dB (−1.99 %)**, max
per-corner swing 2.36 dB (`ff_125c_3.30v`, where the extracted side is
*better*). **60.11 dB worst — still FAIL**, at the *same* corner
(`ss_125c_2.97v`) the schematic baseline already failed at, per issue #89
Scope item 6 / §7 below. The margin widens from a 0.67 dB miss to a 1.89 dB
miss — read against §7 before treating that as a new layout-induced
regression: it is not a new corner failing, and the mechanism §11.2 of the
memo diagnoses (acquisition nonlinearity, not settling or top-plate
loading) is unrelated to what changed between schematic and extracted (the
CDAC's parasitic R/C, not the acquisition network). The other eight corners
span 64.48–71.67 dB, all comfortably clear.

**THD**: tracks SFDR's pattern (worst `ss_125c_2.97v`: −57.85 dBc extracted
vs. −58.53 dBc schematic, a **+0.68 dB** — i.e. slightly worse — delta),
consistent with the SFDR-worst corner being distortion-limited on both
sides, as §11.2 of the memo already established for the schematic core.

**Disposition**: Scope item 1's ENOB/FFT/SFDR slice is closed for the
`mos`-set 9-point grid, and §3's spec-line table below is updated
accordingly. The `cdac`-set isolation §4.5 ran for static linearity is
**not** repeated here — the dynamic deck's own two-stage strategy already
scopes it to the temperature/corner subset a full `cdac`×3×3 = 63-point
dynamic grid would cost roughly 63/9 × 550 s ≈ 1 h to run, and nothing in
§4.5's static-linearity finding ("isolating the capacitor corners
individually does not surface anything the combined `ff`/`ss` sweep
missed") suggests the dynamic deck would find something different; left as
a candidate for a future increment if that assumption needs checking
directly, not asserted as already covered.

### 4.7 Power (Scope item 1's power slice, now closed)

`layout/adc-top/parasitics/gen_extracted_power_tb.py` ports
`gen_adc_top.power_netlist()` onto the extracted core exactly as §4.6's
generator ports `fft_netlist()`: same five-level PWL staircase (byte-identical
to the schematic deck's), same `gtop._preamble()` rails, the extracted
`ADC_TOP` in place of two `adc_cdac_side` + two `adc_tp_sw` instances, and
`sim/adc-power/testbench/tb.json` run **unmodified** via `run_corners.py
--netlist`. No ideal-shadow DAC: this manifest measures supply currents and
one supply voltage, so it makes no claim referenced to an ideal conversion.

**The supply-attribution problem §6.2 flagged, and what was done about it.**
§6.2 called this the one #13 bench that "does not port mechanically", because
its claim is a *per-block* decomposition and the core swap replaces exactly
one of those blocks. That is real, and it has one honest resolution rather
than a workaround:

- `klt extract` gives `ADC_TOP` exactly **one** power pin, `vdd`, and the
  layout draws DR-0014's per-side top-plate V_cm switch **and its `adc_drv`**
  inside that same block (`parasitics/README.md`, "What was extracted": 296
  FETs = 288 switch/driver FETs + 8 top-plate-switch FETs). There is no drawn
  boundary to attribute current across, and partitioning a flat extracted
  device list by guessing which device belongs to which schematic block is
  precisely the apportionment `tb.json` exists to avoid ("so the breakdown is
  measured rather than apportioned").
- **Choice, stated not absorbed**: wire the extracted `vdd` to `vddd`.
  Therefore, on the extracted side, `p_cdac_*` means **CDAC bottom-plate
  switches + local drivers + the top-plate V_cm switch and its driver** — the
  schematic's `p_cdac_* + p_trk_*`, merged — and `p_trk_*` is **structurally
  zero**: a rail still declared and still measured, with no device on it. A
  `0` in that column is the *absence of a separate rail*, not a top-plate
  switch that got cheaper.
- **`p_total_*` — the ratified spec line — is conserved exactly** by that
  merge, because it sums all five rails and the merge moves current between
  two of its terms rather than out of it. The headline row below is therefore
  directly comparable with no adjustment; the per-block row is compared
  against the schematic's `p_cdac + p_trk` sum, computed from the records.

The same caveat the schematic record carries is carried here unweakened: the
rung-1 SAR sequencer draws no supply current on **either** netlist (DR-0010
rung 1, ideal XSPICE primitives, no devices). The core swap neither closes
nor widens that gap.

- schematic record: [`20260802-141402-1224e11`](adc-power/records/20260802-141402-1224e11.md) (DR-0014 re-run, #61 / PR #64)
- extracted record: [`20260806-093034-c9981fb`](adc-power/records/20260806-093034-c9981fb.md) (this increment, 27/27 PASS)
- shared corners: **27** (`tt`/`ss`/`ff` × −40/27/125 °C × 2.97/3.30/3.63 V) — the schematic baseline's own grid, matched on purpose
- per-corner verdicts, read from the records: schematic **all PASS**, extracted **all PASS**; corners whose verdict changed: **none**
- measured compute: 57 s/point single-threaded, **~330 s wall for the 27-point grid at `-j 6 --ngspice-threads 1`** — the cheapest of the three extracted decks (the 17 µs transient is comparable to the static deck's, and it has no ideal-shadow network)

```bash
python3 layout/adc-top/parasitics/gen_extracted_power_tb.py --check
python3 sim/tools/schematic_vs_extracted.py adc-power \
    --schematic 20260802-141402-1224e11 --extracted 20260806-093034-c9981fb \
    --only p_cmp_f050_uw p_cdac_f050_uw p_ref_f050_uw p_vcm_f050_uw p_total_f050_uw
```

| measurement (at f050, mid-scale) | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `p_cmp_f050_uw` | 122.147 (`ff_-40c_3.63v`) | 118.829 (`ff_125c_3.63v`) | -3.318 | -2.716 | 5.996 |
| `p_cdac_f050_uw` | 34.814 (`ff_-40c_3.63v`) | 38.3318 (`ff_-40c_3.63v`) | +3.5178 | +10.1 | 6.1353 |
| `p_ref_f050_uw` | 32.0765 (`ss_125c_3.63v`) | 35.6751 (`tt_125c_3.63v`) | +3.5986 | +11.22 | 10.1645 |
| `p_vcm_f050_uw` | 2.68804 (`ss_27c_3.63v`) | 1.88276 (`ff_-40c_3.63v`) | -0.80528 | -29.96 | 2.38974 |
| `p_total_f050_uw` | 183.342 (`ff_-40c_3.63v`) | 184.519 (`ff_-40c_3.63v`) | +1.177 | +0.642 | 12.749 |

**`p_cdac_f050_uw`'s +10.1 % is not the array term's real delta** — remember
the merge: the schematic's separate `p_trk_f050_uw` (1.25 µW at that corner)
has to be added to its `p_cdac` before the comparison is like-for-like.
Computed that way over all 27 corners and all five input levels, the array
term rises by a **mean +15.0 % to +17.6 % per input level**, spanning **+6.3 %
to +27.4 %** across individual corners. That is the headline post-layout cost
of this array: the drawn interconnect and top-plate parasitic capacitance are
charged and discharged every bit trial, and ~16 % more switching energy is
what that costs. The reference and V_cm charge terms move in the same
direction and the same band (`p_ref` +11 %, `p_vcm` in the ±25 % range whose
sign flips with input level because the V_cm rail sources charge at low codes
and sinks it at high ones — see the schematic record's own note).

**THE SPEC LINE. Power @ 1 MS/s < 1 mW: PASS, 3.7× margin.** Worst
`p_total` anywhere on the extracted grid is **267.31 µW** (`tt_125c_3.63v`,
full scale) against the schematic's 183.34 µW worst — but that single cell is
a comparator artefact of this bench, not array power, and §4.7.1 below shows
so by experiment. **Excluding it, the extracted worst is 184.52 µW
(`ff_-40c_3.63v`, mid-scale) — +0.64 % on the schematic worst at the same
cell — and the largest `p_total` delta anywhere else on the grid is
+12.75 µW.** Either number passes the ratified < 1 mW row, and both remain
inside the < 500 µW stretch target.

#### 4.7.1 The one outlier, diagnosed rather than footnoted

At exactly one of 135 comparator cells (27 corners × 5 input levels) —
`tt_125c_3.63v` at full scale — `p_cmp` reads **224.95 µW against the
schematic's 109.38 µW**, a 2.06× jump. `tb.json`'s only comparator bound is on
`p_cmp_f050_uw` (20–200 µW), which is unaffected, so **both records PASS and
nothing in the harness would have flagged this** — which is why it gets a
probe (CLAUDE.md: report and escalate, do not absorb).

`layout/adc-top/parasitics/probe_power_cmp_anomaly.py` resolves `i(vddc)` per
bit cycle across that window, with the adjacent f075 window measured in the
same run as an in-deck control, and `--core schematic` swapping
`gen_adc_top._core()` in while changing nothing else. Record
[`layout/adc-top/parasitics/records/20260806-power-cmp-metastability.md`](../layout/adc-top/parasitics/records/20260806-power-cmp-metastability.md):

- **58.8 % of the window's comparator charge sits in 4 of its 32 bit cycles**
  (uniform would be 12.5 %) — really one cycle per conversion, at **543.7 µA**
  against a ~28 µA baseline. Decision-localised, not a bias shift; the probe
  was built so a flat profile would have said the opposite.
- That cycle is **`ph2`, an acquisition phase, not a bit trial**. Both top
  plates sit at V_cm to within 4 mV — exactly what DR-0014's top-plate switch
  is supposed to do — and never approach a rail.
- `_preamble()` runs `cmpclk` **free** at the bit rate, so the StrongARM latch
  fires in the acquisition phases too, where the residue is nominally zero. A
  latch strobed at zero differential is **metastable** and stays in its
  high-current regenerative phase for the whole strobe window.
- **The control decides it**: the *schematic* core peaks in the *same* cycle,
  in the same phase, with the same rails — it simply lands on the other side
  of the knife edge (**−20 µV** of residue at that strobe versus the extracted
  core's **+0.00 µV**, below the deck's `meas` resolution). Twenty microvolts
  is enough to resolve inside the strobe window; zero is not.

**Disposition**: this is **not** a post-layout power finding (the mechanism is
on both cores; the extracted arm lands closer to the metastable point at one
corner by coincidence — the same core reads 109.435 µW at f075, 0.02 % from
the schematic control), and **not** a functional defect (no decision is taken
in `ph2`; both arms decode full scale correctly). No spec line moves, no
record is edited, and nothing is relaxed. It is a real property of the rung-1
bench worth knowing before quoting a comparator-power number from any of these
decks — see §6.5.

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

**3. What *is* statistically available on the extracted netlist — measured,
not asserted.** The extracted MOS devices are `X … nfet_03v3` / `pfet_03v3`
PDK subckt calls, which *do* pick up the PDK's `fets_mm` threshold-mismatch
statistics when `sw_stat_mismatch = 1` (the mechanism
`sim/comparator-offset-mc/` uses). When this section was first written that
was stated as "technically supported" and deferred. It is no longer deferred:
`layout/adc-top/parasitics/mc_extracted_core.py` runs a real 120-draw
mismatch population of full transistor-level conversions on the remediated
extracted core at transition 256 (the array's worst carry), with a
**mandatory** mismatch-off null control — record
[`layout/adc-top/parasitics/records/20260805-extracted-core-mc.md`](../layout/adc-top/parasitics/records/20260805-extracted-core-mc.md).

| population | `sw_stat_mismatch` | N | mean (LSB) | σ (LSB) | distinct draws |
|---|---|---|---|---|---|
| mismatch-on | 1 | 120 | +0.48656 | **1.99e-03** | 120 |
| null control | 0 | 12 | +0.48659 | **0.0** | 1 |

So MOS local mismatch **does** reach the extracted devices, and it is a
≈ 2e-3 LSB (1σ) term at the worst carry — about 5 % of that transition's own
≈ 0.10 LSB DNL and three orders inside the < 1 LSB bound. The null control is
not decoration: it caught three separate ways this run silently reported a
plausible-looking wrong answer (statistical switches placed before the PDK
includes and overridden; `meas`'s 6-digit echo double-counting every draw; an
in-deck σ that returns NaN for a frozen population), each recorded in that
record rather than quietly fixed.

**What this still does not cover** is the *comparator*: the ratified rows that
ride hardest on MOS mismatch — Offset, and the comparator's INL contribution —
live in the comparator, which is schematic-level in this wrapper (the
extracted core is `ADC_TOP`: the CDAC array and its switches). A
comparator-inclusive post-layout mismatch claim needs `ADC_BLOCK` (core +
comparator), already extracted and remediated, named in §6.4 as remaining
work — **attempted this increment and found blocked, not merely unbuilt**:
`gen_extracted_core_tb.py --top ADC_BLOCK` now wires the comparator-baked-in
extraction, but its own functional smoke test (`records/../
records/20260806-adc-block-comparator-smoke.md`) reproducibly decodes every
probed transition to the same stuck code at two PVT corners — a real
functional defect the DC-only remediation check never exercised, not a
missing harness. `mc_extracted_core.py` is deliberately kept `ADC_TOP`-only
until that is resolved, so a comparator-inclusive Monte Carlo cannot be run
against a core that is not yet known to decide correctly.

**Net answer: Scope item 2 is answered for both halves. The CDAC-capacitor
half is not possible on any netlist in this PDK, extracted or schematic, and
#14's behavioral model remains the only available instrument. The
MOS-mismatch half is possible, and has now been run on the extracted core —
with the comparator-inclusive variant on `ADC_BLOCK` named as remaining work
rather than skipped silently.**

---

## 6. What is not yet measured, and what each one needs

### 6.1 ENOB / SFDR / THD (`sim/adc-enob-fft/`) — closed, see §4.6

`layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py` now exists, on the
pattern this section originally called for
(`gen_extracted_inl_dnl_tb.py`'s stimulus/measurement-node porting), and the
9-point `tt`/`ss`/`ff` × 125 °C grid the schematic baseline itself uses
(the two-stage corner strategy, not the original 27-point estimate below)
has run on both sides. **See §4.6** for the full delta table: ENOB PASSES
(9.103 bits worst, −0.060 bits vs. schematic), SFDR continues to FAIL at
the same corner the schematic baseline already failed at (60.11 dB vs. the
62 dB target, §7). Measured compute: 230 s/point single-threaded (not the
~1.5 h/27-point-grid estimate below, both because the actual grid run is
9 points and because `--ngspice-threads 1 -j 6` parallelises cleanly rather
than the naive single-threaded estimate) — 550 s wall for the full 9-point
grid.

*Original estimate, kept for the record*: this deck runs **66 conversions
per PVT point** (`FFT_WARMUP_CONV = 2` + `FFT_N = 64`) against the static
deck's 20 (`INL_WARMUP_CONV = 2` + 18 probed transitions ×
`INL_CONV_PER_POINT = 1`), i.e. ≈ 3.3× the 86 s/point the static deck
measured — the ≈ 3.3× ratio held (230 s vs. 70 s/point at
`--ngspice-threads 1`); what changed was scoping the grid to the 9 points
the schematic baseline itself uses rather than a 27-point `mos`-set sweep.

### 6.2 Power (`sim/adc-power/`) — closed, see §4.7

This section originally said the deck does **not** port mechanically, because
its claim is a per-block supply decomposition and the core swap replaces
exactly one of those blocks with a subckt whose internal supply topology
differs from the schematic's — "a methodology task, not a re-run". That was
correct, and the methodology task has now been done rather than side-stepped:
`gen_extracted_power_tb.py` exists, the decomposition is re-derived against
the extracted core's *actual* single `vdd` pin (which necessarily merges the
schematic's `vddd` and `vddt` blocks, because the layout draws the top-plate
V_cm switch inside the same extracted block), the merge is stated in the
deck header, in the record's own notes, and in §4.7 — and `p_total`, the
ratified spec line, is shown to be conserved by it. The 27-point grid has
run on both sides. **See §4.7** for the full delta table and §4.7.1 for the
one outlier's diagnosis. Measured compute: 57 s/point single-threaded,
~330 s wall for the grid at `-j 6 --ngspice-threads 1`.

### 6.3 Gain error (DR-0012/13 row), rate closure

Both reuse other experiments' testbenches (`sim/dr0014-sampling/`,
`sim/timing-budget-closure/`). Each needs the same treatment as §6.1: an
extracted-core variant of that deck.

### 6.4 The `cdac` capacitor-corner set (closed), and `ADC_BLOCK` (open)

- **Corner set — closed.** §4's 27-point grid used `tt`/`ss`/`ff` rather than
  the manifest's default `cdac` set (7 process corners × 3 × 3 = 63 points)
  because those 27 are exactly the corners the original schematic baseline
  ran. `ff`/`ss` *do* include `mimcap_ff`/`mimcap_ss`, so the MiM process
  corners were already exercised on both sides of every §4 delta; what was
  missing was the `cdac` set's **isolation** of each capacitor-family corner
  individually (PR #100 closed the missing schematic half; this increment
  closed the extracted half and the pairwise comparison). **See §4.5** for
  the full delta table: 63/63 shared corners, both sides all-PASS, no verdict
  changed, and every reading matches §4.1's `mos`-set pattern to within the
  same few-percent band — isolating the capacitor corners individually does
  not surface anything the combined `ff`/`ss` sweep missed. Scope item 7 is
  now fully closed.
- **`ADC_BLOCK` — still open, now blocked on a found-and-recorded defect,
  not merely unbuilt.** `remediate_extracted.py` already generalises to it
  (160 PMOS devices / 25 body islands retied, 1024 MiM caps confirmed, DC
  verified 63/63). Using it in place of `ADC_TOP` would put the
  **comparator** inside the extracted boundary too, which is what a
  *comparator-inclusive* extension of §5's MOS-mismatch Monte Carlo — and any
  comparator-offset post-layout claim — requires. §5's run and §4/§4.5's runs
  all cover the CDAC array and its switches only, not the comparator.
  This increment built the wiring (`gen_extracted_core_tb.py --top
  ADC_BLOCK`, `verify_extracted_core_conversion.py --top ADC_BLOCK`) and ran
  its functional smoke test before attempting any Monte Carlo population —
  the test **FAILs, reproducibly**: every probed transition decodes to the
  same stuck code (1023) at both a nominal and the worst-case PVT corner,
  independent of dout/doutb polarity, while the `ADC_TOP` control at the same
  commit is unaffected. Root cause not identified (ngspice's initial
  transient bias-point solve reports a singular internal node,
  `xdut.$168`, through every fallback before an unreliable "success");
  full repro, diagnostics, and what was ruled out are in
  [`records/20260806-adc-block-comparator-smoke.md`](../layout/adc-top/parasitics/records/20260806-adc-block-comparator-smoke.md).
  The next increment on this item should start from that record, not
  re-discover the same failure.

### 6.5 The free-running comparator strobe (found by §4.7.1, not yet acted on)

`gen_adc_top._preamble()` drives `cmpclk` from a plain `pulse(...)` source at
the bit rate, so the StrongARM latch fires in **every** bit cycle — including
the four acquisition phases, where the residue is nominally zero and the latch
is therefore metastable. §4.7.1 measured what that costs when it happens to
land badly: **543.7 µA in one bit cycle**, against a ~28 µA baseline, enough
to double a whole window's average comparator power.

This is present on **both** netlists and is a property of the rung-1 bench,
not of the layout or of the comparator. It is recorded here because it changes
how a comparator-power number from any of these decks should be read, and
because closing it is a well-defined piece of work:

- **What would close it**: gating `cmpclk` to the ten decide phases (the
  controller already emits the phase information — `sim/sar-logic-functional/`
  checks the one-hot invariant on it).
- **Why it is not done here**: that edits `gen_adc_top._preamble()`, which
  **every** committed record under `sim/` was taken against — including all
  three schematic baselines this document diffs. Changing it inside an
  evidence increment would silently invalidate the like-for-like property that
  makes every delta in §4 meaningful. It needs its own issue, its own
  re-baseline of the affected schematic records, and a decision on whether the
  free-running strobe is actually *wrong* (a real converter's strobe is gated;
  a rung-1 behavioural sequencer's need not be, as long as no claim reads the
  comparator outside a decide phase — and none currently does).
- **What is safe to rely on meanwhile**: everything measured at a decide
  phase, which is every spec-line row in §3. The only quantity this touches is
  the *average* comparator supply current, i.e. `p_cmp_*`, and only when a
  strobe lands on a near-zero residue.

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

**Update (§4.6, this increment) — measured, not merely expected.** The
extracted-netlist run confirms the "no new corner fails" half exactly: all
nine shared corners keep their schematic verdict, `ss_125c_2.97v` remains
the sole failing corner, and the other eight span 64.48–71.67 dB (all clear
of the 62 dB target with margin comparable to or wider than the schematic
grid's 63.62–69.98 dB). Per CLAUDE.md ("report FAIL and escalate rather than
silently adjusting"), the second half is flagged rather than absorbed: the
**margin at `ss_125c_2.97v` does widen** — from a 0.67 dB miss (schematic,
61.33 dB) to a **1.89 dB miss** (extracted, 60.11 dB), a −1.22 dB
worst-corner delta. This is *not* attributed to a new mechanism — §4.6
shows THD moves the same direction by a comparable amount at the same
corner, consistent with §11.2's existing diagnosis (acquisition
nonlinearity, unrelated to the CDAC's own R/C this extraction adds) rather
than a distinct post-layout effect — but the widened margin is reported
here explicitly rather than folded into "expected baseline behaviour"
without qualification, per Scope item 5's no-relaxation rule. A reader
deciding whether this needs its own remediation (rather than remaining the
pre-existing, already-tracked failure §11.2 describes) should start from
the §4.6 per-corner table, not this section's summary.

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
| §4.4 control | `layout/adc-top/parasitics/probe_gain_err_settling.py` → record `20260805-224500-2c21be4` (3 PVT points × 2 cores) |
| §5 Monte Carlo | `layout/adc-top/parasitics/mc_extracted_core.py` → record `layout/adc-top/parasitics/records/20260805-extracted-core-mc.md` (N = 120 + 12-draw null control) |
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| ngspice | 46 |
| Grid | 27 points, 27 completed, 0 non-convergent; 2436 s wall at `-j 1` |
| §4.5 `cdac`-set records | `20260805-220405-bff6eaf` (schematic, PR #100) → `20260806-052258-8d36824` (extracted, this increment) |
| §4.5 grid | 63 points, 63 completed, 0 non-convergent; 1100 s wall at `-j 6 --ngspice-threads 1` (throughput note: capping ngspice's own OpenMP thread count to 1 per point lets `-j` scale near-linearly on this host instead of oversubscribing — see `sim/harness/cli.py --ngspice-threads` and `sim/harness/README.md`) |
| §4.6 deck generator | `layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py` |
| §4.6 records | `20260802-141402-1224e11` (schematic) → `20260806-081350-862d054` (extracted, clean-tree re-run; supersedes the dirty-tree `20260806-060520-72a230a`) |
| §4.6 analysis tool | `sim/adc-enob-fft/testbench/analyze_fft.py --sigma-extra-lsb 0.0488` (noise term per `spec/testbench-suite-memo.md` §4.3, unchanged from the schematic composition) |
| §4.6 grid | 9 points (`tt`/`ss`/`ff` × 125 °C × 3 supplies, the schematic baseline's own two-stage-strategy subset), 9 completed, 0 non-convergent; 550 s wall at `-j 6 --ngspice-threads 1` |
| §4.7 deck generator | `layout/adc-top/parasitics/gen_extracted_power_tb.py` → `sim/adc-power/testbench/tb_adc_power_extracted.spice` (extracted `vdd` → `vddd`; `vddt` declared, measured, and structurally empty — see §4.7) |
| §4.7 records | `20260802-141402-1224e11` (schematic) → `20260806-093034-c9981fb` (extracted) |
| §4.7 grid | 27 points (`tt`/`ss`/`ff` × −40/27/125 °C × 3 supplies, the schematic baseline's own grid), 27 completed, 0 non-convergent; ~330 s wall at `-j 6 --ngspice-threads 1` |
| §4.7.1 outlier probe | `layout/adc-top/parasitics/probe_power_cmp_anomaly.py` → record `layout/adc-top/parasitics/records/20260806-power-cmp-metastability.md` (2 arms × 2 input levels × 32 bit cycles, extracted vs schematic core at `tt_125c_3.63v`) |

Every `sim/` record cited here carries its own `Netlist provenance` field, and
no extracted record replaces a schematic one — they append alongside each
other, per `sim/README.md`, "Extracted vs schematic semantics".
