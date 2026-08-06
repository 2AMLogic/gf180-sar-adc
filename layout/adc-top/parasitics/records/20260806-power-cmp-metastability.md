# Record 20260806-power-cmp-metastability

- **Record ID**: 20260806-power-cmp-metastability
- **Claim**: the single outlier in the extracted-core power grid
  ([`sim/adc-power/records/20260806-093034-c9981fb.md`](../../../../sim/adc-power/records/20260806-093034-c9981fb.md),
  issue #89 Scope item 1) is diagnosed, not left as a footnote. That record's
  `p_cmp_f100_uw` reads **224.95 µW at `tt_125c_3.63v`** against the schematic
  baseline's **109.38 µW** — a 2.06× jump at exactly one of 135 (27 corners ×
  5 input levels) comparator cells. Both records PASS: `tb.json`'s only
  comparator bound is on `p_cmp_f050_uw` (20–200 µW), which is unaffected, so
  nothing in the harness would have flagged it. **Result: mechanism
  identified, and it is a property of this deck's free-running comparator
  strobe rather than of the extracted layout's power.**
- **Netlist provenance**: `extracted` for the probed arm (remediated
  `ADC_TOP`: PMOS bodies retied to `vdd`, input rails promoted to
  `vinp`/`vinn`, MiM cards left as native PDK subckt calls); `schematic`
  (`design/adc-top/gen_adc_top.py`'s own `_core()`) for the control arm. The
  comparator itself is schematic-level in **both** arms — the same
  `comparator` subckt instance, unchanged, on both sides.
- **Source extraction**: `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`
  — the same extraction every other #89 record cites.
- **PDK binding**: gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
  resolved via `sim/harness/pdk.py`. ngspice-46.
- **Working tree**: clean at commit `e9ae10c` — `git status --porcelain`
  empty when both arms were run, before this record's own files were added,
  per the citability lesson `sim/adc-enob-fft/records/20260806-081350-862d054.md`
  documents.
- **Statistical convention**: N/A — a deterministic single-corner diagnostic,
  not a distribution claim.

## Reproduce

```
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py \
    --json reports/20260806-power-cmp-metastability/probe_extracted.json
# the control that decides whether this is a post-layout finding at all:
python3 layout/adc-top/parasitics/probe_power_cmp_anomaly.py --core schematic \
    --json reports/20260806-power-cmp-metastability/probe_schematic.json
```

Both arms default to `--corner tt --temp 125 --vdd 3.63`, the anomalous cell's
own corner. 57 s and 43 s respectively, single-threaded. Raw stdout and the
per-bit-cycle JSON for both arms are committed under
[`reports/20260806-power-cmp-metastability/`](../reports/20260806-power-cmp-metastability/).

## What the probe measures, and how it could have said "no"

The comparator is a static preamp (10 µA of bias by design, DR-0015) plus a
StrongARM latch whose current is paid per decision. Two mechanisms would
double the *average* over the 2-conversion measurement window, and they are
distinguishable by **where in the window** the charge sits:

- **decision-localised** — one or a few of the 32 bit cycles the window spans
  hold the latch in its high-current regenerative phase, the rest look normal;
- **static / bias-shift** — the preamp's operating point moved, so the excess
  spreads roughly uniformly across all 32.

`probe_power_cmp_anomaly.py` resolves `i(vddc)` per bit cycle and reports the
charge concentration explicitly (uniform ⇒ the top 4 of 32 cycles hold 12.5 %
of the charge). A flat profile would have falsified the first mechanism; a
spiky one falsifies the second. It cannot come back inconclusive by
construction. The adjacent f075 window is measured **in the same run** as an
in-deck control, so that comparison carries no run-to-run variation at all.

## Result

| arm | level | `p_cmp` (µW) | mean `i(vddc)` per bit cycle (µA) | peak (µA) | peak/mean | top-4-of-32 charge share |
|---|---|---|---|---|---|---|
| **extracted** | f075 | 109.435 | 30.149 | 34.179 | 1.13× | 14.0 % |
| **extracted** | **f100** | **224.950** | **61.967** | **543.705** | **8.77×** | **58.8 %** |
| *schematic (control)* | f075 | 109.455 | 30.154 | 34.391 | 1.14× | 14.0 % |
| *schematic (control)* | f100 | 109.378 | 30.132 | 37.209 | 1.23× | 14.9 % |

The extracted arm's `p_cmp_f100_uw` = 224.950 µW reproduces the grid record's
own 224.951 µW to the sixth digit — the probe is averaging the same window the
manifest did, not a lookalike.

**The profile is emphatically decision-localised, not a bias shift.** Almost
59 % of the window's comparator charge sits in 4 of its 32 bit cycles, and the
per-cycle series shows it is really **one** cycle per conversion, repeated
identically in both conversions of the window:

```
extracted, f100, i(vddc) per bit cycle (µA), conversion 0 then conversion 1:
 -33.6 -32.9 -543.7 -38.7 -27.9 -27.6 -27.7 -27.7 -27.8 -28.1 -28.4 -28.9 -29.5 -32.5 -27.9 -27.7
 -33.6 -32.9 -543.6 -39.7 -27.9 -27.6 -27.7 -27.7 -27.8 -28.1 -28.4 -28.9 -29.6 -33.1 -27.9 -27.7

schematic control, same cell:
 -33.8 -33.1  -37.2 -33.5 -27.9 -27.6 -27.7 -27.7 -27.8 -28.1 -28.5 -28.9 -29.6 -35.3 -30.7 -27.8
 -33.8 -33.1  -37.2 -33.5 -27.9 -27.6 -27.7 -27.7 -27.8 -28.1 -28.5 -28.9 -29.5 -32.2 -27.9 -27.8
```

## Which cycle, and what the comparator's inputs were doing in it

Bit cycle `b` spans `[b·CLK_PERIOD_NS, (b+1)·CLK_PERIOD_NS)` from the start of
a conversion, and trial `i` decides in bit cycle `3+i`
(`gen_adc_top.trial_decision_ns`). So bit cycles 0–3 are the **acquisition
phases**, not bit trials — and the peak cycle is **cycle 2, `ph2`, in the
middle of acquisition**:

| arm | peak cycle | phase | `v(topp)` in that cycle | `v(topn)` in that cycle | `v(topp) − v(topn)` at that cycle's strobe |
|---|---|---|---|---|---|
| **extracted** | 2 | `ph2` (acquisition) | 1.8129 … 1.8167 V | 1.8128 … 1.8167 V | **+0.00 µV** |
| *schematic* | 2 | `ph2` (acquisition) | 1.8128 … 1.8168 V | 1.8127 … 1.8168 V | **−20.00 µV** |

Both top plates sit at V_cm (= vdd/2 = 1.815 V) to within 4 mV — exactly what
DR-0014's top-plate V_cm switch is *supposed* to do during acquisition. The
comparator's inputs never approach a rail on either arm, which rules out the
input-common-mode / forward-biased-junction story outright.

## Mechanism

`gen_adc_top._preamble()` runs `cmpclk` **free** at the bit rate — a plain
`pulse(...)` source, not gated to the ten decide phases. So the StrongARM
latch fires in **every** bit cycle, including the four acquisition phases,
where by construction both top plates are held at V_cm and the differential
residue is nominally zero. A latch strobed with (near-)zero input differential
is metastable: it stays in its high-current regenerative phase for the whole
strobe window instead of resolving in the ~863 ps
`sim/comparator-regeneration/` measured against a real residue.

That is a **knife-edge** condition, and the two arms land on opposite sides of
it at this one corner: the extracted core's residue at that strobe is **below
the deck's `meas` resolution (+0.00 µV)**, the schematic core's is **−20 µV**.
Twenty microvolts is enough to get the latch out of metastability inside the
strobe window; zero is not. Nothing about the extracted core makes it *tend*
toward zero — it is a coincidence at one corner, which is exactly why the
other 26 corners and the other four input levels show no such effect (the same
extracted core reads 109.435 µW at f075, 0.02 % from the schematic control).

**Why full scale specifically**: at f100 the `p` side's bottom plates track
V_in = V_REF while the `n` side's track V_cm — the largest side-to-side
asymmetry this staircase produces — so the two top plates' settling toward
V_cm during acquisition is at its most different, and the crossing where their
difference passes through zero has the best chance of landing on a strobe
edge.

## Disposition

1. **This is not a post-layout power finding.** The mechanism is present on
   both cores (both peak in the same cycle, in the same phase, with the same
   rails); the extracted arm merely lands closer to the metastable point at
   this one corner. Reporting the 2.06× as a layout cost would be wrong.
2. **It is not a functional defect either.** No decision is taken in `ph2` —
   the rung-1 controller samples the comparator only at the trial phases — and
   both arms decode correctly at full scale (extracted `1023, 1023`;
   schematic `1022, 1023`, the 1 LSB boundary a full-scale input sits on). The
   power deck makes no code claim and neither number is read as one.
3. **No spec line moves.** `p_total` at that cell is 267.31 µW against the
   ratified < 1 mW row — 3.7× of margin, and still inside the < 500 µW stretch
   target. Excluding this cell, the extracted worst `p_total` is 184.52 µW
   (`ff_-40c_3.63v`, f050), +0.64 % on the schematic worst of 183.34 µW at the
   same cell, and the largest per-cell `p_total` delta anywhere else on the
   grid is +12.75 µW (`tt_27c_3.63v`, f050). **No spec is relaxed and no
   record is edited** to accommodate this; the grid record stands as run, with
   this diagnostic attached.
4. **It is a real property of the rung-1 bench**, worth knowing before anyone
   quotes a comparator-power number from these decks: a free-running strobe
   pays a metastability toll in the acquisition phases whose size depends on
   where the residue happens to sit, on either netlist. Gating `cmpclk` to the
   decide phases would remove it — but that changes `gen_adc_top._preamble()`,
   which every committed record in `sim/` was taken against, so it is **not**
   done here as a drive-by inside an evidence increment. Filed as follow-up
   work in `sim/extracted-delta-summary.md` §6.5.

## Provenance

| | |
|---|---|
| Probe | `layout/adc-top/parasitics/probe_power_cmp_anomaly.py` |
| Grid record diagnosed | `sim/adc-power/records/20260806-093034-c9981fb.md` |
| Schematic baseline | `sim/adc-power/records/20260802-141402-1224e11.md` |
| Extraction | `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice` |
| Remediation | `layout/adc-top/parasitics/remediate_extracted.py` |
| Deck under test | `sim/adc-power/testbench/tb_adc_power_extracted.spice` (extracted arm); `gen_adc_top._core()` (control arm) |
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| ngspice | 46 |
| Corner | `tt_125c_3.63v` (the anomalous cell's own corner), both arms |
| Raw artifacts | `layout/adc-top/parasitics/reports/20260806-power-cmp-metastability/` |
