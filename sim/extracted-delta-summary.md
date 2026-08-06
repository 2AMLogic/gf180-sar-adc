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
| ENOB @ Nyquist > 9.0 | 9.163 bits (`ss_125c_2.97v`) | **9.103 bits** (`ss_125c_2.97v`) | −0.060 bit (−0.66 %) | **measured — PASS** (§4.6) |
| SFDR @ Nyquist ≥ 62 dB | 61.33 dB (`ss_125c_2.97v`) — **already FAIL** | **60.11 dB** (`ss_125c_2.97v`) — **still FAIL, margin widened** | −1.22 dB (worst corner) | **measured — FAIL, pre-existing mechanism, margin widened, not a new corner failure** (§4.6; read §7 first) |
| Power @ 1 MS/s < 1 mW | 183.3 µW (`ff_-40c_3.63v`) | — | — | not yet run — §6.2 |
| Gain error, systematic (DR-0012/13 scope: sampling-switch injection) ≤ 0.5 LSB | 0.0045–0.0088 LSB | — | — | not yet run — §6.3 |
| Offset ≤ 2 LSB (3σ mismatch) | `sim/comparator-offset-mc/` | — | n/a | comparator is schematic-level in this wrapper — §5 |
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

### 4.6 ENOB / SFDR / THD — the dynamic-performance (FFT) delta, in full

Closes the last un-ported #13 spec-line deck named in the old §6.1 (power,
§6.2, does not port mechanically and remains separate).

- schematic record: [`20260802-141402-1224e11`](adc-enob-fft/records/20260802-141402-1224e11.md) (DR-0014 topology, #61 / PR #64)
- extracted record: [`20260806-064029-727ba1c`](adc-enob-fft/records/20260806-064029-727ba1c.md)
- deck: `layout/adc-top/parasitics/gen_extracted_fft_tb.py`, on the same
  "extracted core, schematic everything-else" pattern §1.3 describes — it
  ports `gen_adc_top.py`'s coherent-sampling sine verbatim and calls
  `gen_extracted_core_tb.shadow_dac_and_error(tag="se", gated=True)` for the
  ideal shadow DAC / gated decision-error node the manifest's `decerr_c*_lsb`
  checks read, rather than re-deriving either
- **grid run: the same 9-point subset the schematic baseline itself ran**
  (`tt`/`ss`/`ff` × 125 °C × 2.97/3.30/3.63 V), not the full 27- or 63-point
  grid §4/§4.5 use. This is not a truncation of this increment's own scope —
  it reproduces the schematic record's own two-stage-corner-strategy subset
  (spec/testbench-suite-memo.md §5: 125 °C is where both the
  settling/linearity-worst `ss_125c_2.97v` corner and the independently
  noise-worst `ff_125c_3.63v` corner sit) so the two records are point-for-
  point comparable, and because a full 63-point `cdac` grid at this deck's
  measured ≈4 min/point single-threaded cost (9 points, 592 s wall at
  `--ngspice-threads 1 -j 6`) would be a multi-hour campaign disproportionate
  to the baseline it is diffed against — see the record's own **Subset of the
  mandated PVT matrix** justification.
- per-corner verdicts, read from the records: schematic **all PASS**,
  extracted **all PASS** (both **capture-validity** verdicts only — neither
  record's harness PASS covers the ENOB/SFDR rows themselves; those are
  spectral quantities computed below, exactly as §7 and each record's own
  Note already state)
- corners whose capture-validity verdict changed schematic → extracted: none

```bash
python3 layout/adc-top/parasitics/gen_extracted_fft_tb.py --check
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/20260802-141402-1224e11/ --markdown --sigma-extra-lsb 0.0488
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/20260806-064029-727ba1c/ --markdown --sigma-extra-lsb 0.0488
```

`--sigma-extra-lsb 0.0488` composes in the separately measured noise terms
(`sim/comparator-preamp-noise/`'s comparator input-referred noise + the
sampling `kT/C` term), exactly as `spec/testbench-suite-memo.md` §11.5 does
for the schematic figure — **not re-measured here**: the comparator and its
noise are schematic-level in this wrapper (§1.3), so the noise composition
term is unchanged from the schematic run and reused, not re-derived. `enob_
composed_bits` is the figure the ratified ENOB row uses; `sfdr_db` (THD is a
distortion figure with no separate noise composition) is the ratified SFDR
row's own quantity.

| corner-id | schem SFDR (dB) | ext SFDR (dB) | Δ SFDR (dB) | schem ENOB (composed, bits) | ext ENOB (composed, bits) | Δ ENOB (bits) | schem THD (dBc) | ext THD (dBc) | Δ THD (dB) |
|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_2.97v` | 69.45 | 71.67 | +2.22 | 9.888 | 9.998 | +0.110 | −67.27 | −67.60 | −0.33 |
| `ff_125c_3.30v` | 67.32 | 69.68 | +2.36 | 9.744 | 9.741 | −0.003 | −63.74 | −65.30 | −1.56 |
| `ff_125c_3.63v` | 69.98 | 68.99 | −0.99 | 9.918 | 9.929 | +0.011 | −66.69 | −65.68 | +1.01 |
| **`ss_125c_2.97v`** | **61.33** | **60.11** | **−1.22** | **9.163** | **9.103** | **−0.060** | −58.53 | −57.85 | +0.68 |
| `ss_125c_3.30v` | 63.62 | 64.48 | +0.86 | 9.561 | 9.541 | −0.020 | −61.50 | −61.43 | +0.07 |
| `ss_125c_3.63v` | 65.99 | 67.52 | +1.53 | 9.653 | 9.709 | +0.056 | −62.70 | −63.74 | −1.04 |
| `tt_125c_2.97v` | 64.67 | 65.03 | +0.36 | 9.571 | 9.604 | +0.033 | −61.97 | −62.27 | −0.30 |
| `tt_125c_3.30v` | 69.14 | 70.05 | +0.91 | 9.868 | 9.896 | +0.028 | −65.77 | −65.58 | +0.19 |
| `tt_125c_3.63v` | 68.96 | 67.72 | −1.24 | 9.901 | 9.804 | −0.097 | −65.31 | −64.30 | +1.01 |

**ENOB — PASS, both sides, same worst corner, margin narrows slightly.**
Worst extracted ENOB is **9.103 bits at `ss_125c_2.97v`** (schematic:
9.163 bits, same corner) — a −0.060 bit delta, clearing the > 9.0 target with
0.103 bits of margin (schematic: 0.163). No corner's ENOB verdict changes.

**SFDR — the pre-existing FAIL survives layout, and the margin widens.**
Every one of the other eight corners stays comfortably clear of the ≥ 62 dB
target on the extracted side too (64.48–71.67 dB); no corner that passed on
the schematic fails on the extracted side. But at `ss_125c_2.97v` — the
corner §7 (below) already flags as a pre-existing schematic-level failure —
the extracted SFDR is **60.11 dB, 1.22 dB worse than the schematic's
61.33 dB**. That moves the miss from 0.67 dB (schematic) to **1.89 dB**
(extracted): the miss is not merely repeated, it is **materially wider**.
Per §7's own framing this is the outcome that section explicitly names as
what *would* be a new finding rather than a repeat of the known FAIL, so it
is reported here as exactly that, not folded silently into "still fails as
expected." See §7 for the full disposition.

Reading the table alongside the direction of the other deltas: THD improves
(more negative, i.e. lower distortion) at six of nine corners and the
opposite-process-corner pattern in §4.1/§4.5 (worst linearity sitting at the
cold/`ss`-adjacent end) is not what governs here — SFDR's worst corner is
unchanged (`ss_125c_2.97v` on both sides) but its *sign* of movement is not
uniform across the grid (three of nine corners, all at 125 °C across
different process/supply combinations, show negative SFDR deltas of
0.99–1.24 dB, while the other six improve by 0.36–2.36 dB). This is
consistent with §11.2's own diagnosis of the schematic-level SFDR mechanism
(acquisition-bow, not settling or static INL) being layout-sensitive in a way
static INL is not — §4.1/§4.5 show static INL/DNL moving by only a few
percent, uniformly, while this table's SFDR moves are larger and mixed-sign.
No further mechanism attribution is done here; that is the "obvious next
measurement... not done in this re-run" §11.2 itself names, now doubly true
post-layout.

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
work.

**Net answer: Scope item 2 is answered for both halves. The CDAC-capacitor
half is not possible on any netlist in this PDK, extracted or schematic, and
#14's behavioral model remains the only available instrument. The
MOS-mismatch half is possible, and has now been run on the extracted core —
with the comparator-inclusive variant on `ADC_BLOCK` named as remaining work
rather than skipped silently.**

---

## 6. What is not yet measured, and what each one needs

### 6.1 ENOB / SFDR / THD (`sim/adc-enob-fft/`) — closed

Was: needs its own extracted-core deck, on the pattern of
`gen_extracted_inl_dnl_tb.py`, ported onto `_core_extracted()`. **Done**:
`layout/adc-top/parasitics/gen_extracted_fft_tb.py` is that deck (it reuses
`gen_extracted_core_tb.shadow_dac_and_error(gated=True)` rather than carrying
a second copy of the shadow-DAC formula). Run at the same 9-point subset the
schematic ENOB/SFDR baseline itself used (`tt`/`ss`/`ff` × 125 °C × three
supplies), not the full grid — a full 63-point `cdac` sweep of a ≈4-min/point
deck was judged disproportionate to the baseline it is diffed against; see
§4.6 for the stated reason and the full delta table. **ENOB PASSES** (worst
9.103 bits, `ss_125c_2.97v`, delta −0.060 bits). **SFDR still FAILS** at the
same corner the schematic baseline already failed at — expected per §7 — but
the miss **widens** from 0.67 dB to 1.89 dB, which is itself a new,
plainly-reported finding, not a repeat of the known FAIL. See §4.6 and §7.

### 6.2 Power (`sim/adc-power/`)

Does **not** port mechanically. Its claim is a per-block supply decomposition
(comparator / CDAC / logic measured on separate supply branches), and the
core swap replaces exactly one of those blocks with a subckt whose internal
supply topology differs from the schematic's. The decomposition has to be
re-derived against the extracted core's actual supply pins before the bench
means anything post-layout; that is a methodology task, not a re-run.

### 6.3 Gain error (DR-0012/13 row), rate closure

Both reuse other experiments' testbenches (`sim/dr0014-sampling/`,
`sim/timing-budget-closure/`). Each needs the same treatment §6.1 got: an
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
- **`ADC_BLOCK` — still open.** `remediate_extracted.py` already generalises
  to it (160 PMOS devices / 25 body islands retied, 1024 MiM caps confirmed,
  DC verified 63/63). Using it in place of `ADC_TOP` would put the
  **comparator** inside the extracted boundary too, which is what a
  *comparator-inclusive* extension of §5's MOS-mismatch Monte Carlo — and any
  comparator-offset post-layout claim — requires. §5's run and §4/§4.5's runs
  all cover the CDAC array and its switches only, not the comparator.

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

### 7.1 Measured (§4.6): the failure survives, and the margin widens materially

Now measured, per §4.6's full table: the extracted result **does not fail any
corner the schematic passed** — the coverage half of this section's
prediction holds. But the second half does not: the extracted SFDR at
`ss_125c_2.97v` is **60.11 dB, against the schematic's 61.33 dB** — the miss
grows from **0.67 dB to 1.89 dB**, a 1.22 dB widening that is not explained by
measurement noise (every other corner's SFDR delta is 0.36–2.36 dB in the
*improving* direction; only `ss_125c_2.97v` and two other 125 °C corners move
the other way, and `ss_125c_2.97v` moves furthest). Per this section's own
stated criterion, **this is the new finding**, reported plainly rather than
absorbed into "still fails as expected": layout measurably worsens the one
mechanism §11.2 already identified as acquisition-bow-limited, not settling-
or static-INL-limited (§4.1/§4.5 show static INL moving only a few percent at
this same corner, an order smaller than SFDR's move). No spec relaxation is
made or implied — the ≥ 62 dB target stands, the row is reported FAIL, and
the widening is escalated here rather than silently noted.

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
| §4.6 deck generator | `layout/adc-top/parasitics/gen_extracted_fft_tb.py` |
| §4.6 records | `20260802-141402-1224e11` (schematic) → `20260806-064029-727ba1c` (extracted, this increment) |
| §4.6 post-processor | `sim/adc-enob-fft/testbench/analyze_fft.py --sigma-extra-lsb 0.0488` (same noise-composition figure the schematic record uses, `spec/testbench-suite-memo.md` §11.5 — not re-measured, the comparator/noise are schematic-level in this wrapper per §1.3) |
| §4.6 grid | 9 points (`tt`/`ss`/`ff` × 125 °C × three supplies — same subset as the schematic baseline, §4.6's own note), 9 completed, 0 non-convergent; 592 s wall at `-j 6 --ngspice-threads 1` |

Every `sim/` record cited here carries its own `Netlist provenance` field, and
no extracted record replaces a schematic one — they append alongside each
other, per `sim/README.md`, "Extracted vs schematic semantics".
