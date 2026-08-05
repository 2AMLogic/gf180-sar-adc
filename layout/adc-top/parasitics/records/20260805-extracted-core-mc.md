# Record 20260805-extracted-core-mc

- **Record ID**: 20260805-extracted-core-mc
- **Claim**: issue #89 **Scope item 2** — "Monte Carlo re-run (#14's bench) on
  the extracted netlist, **if** the extraction flow's parasitic/mismatch
  models support statistical variation — state explicitly if not, rather than
  silently skipping." That sentence has two halves and they get **different**
  answers, so neither an unqualified "ran it" nor an unqualified "not
  supported" would be true. This record answers both, measuring the half that
  can be measured rather than asserting it:
  - **MOS device mismatch reaches the extracted netlist** — demonstrated here
    by a real 120-draw population of full transistor-level conversions on the
    extracted core, with a mandatory mismatch-off null control.
  - **CDAC capacitor local mismatch is absent from the PDK on _both_
    netlists** — an audit finding, not a simulation result, because a
    simulation cannot prove a model library lacks a construct.

  **No ADC spec-line pass/fail is claimed here.** The statistical half of the
  gain/linearity rows remains `sim/mc-cdac-mismatch/`'s behavioural claim; see
  "What this does and does not license" below.
- **Netlist provenance**: **extracted** — the `--pdk gf180mcuD` parasitic
  extraction of the drawn `adc_top` GDS, then locally remediated
  (`remediate_extracted.py`, record `20260805-remediation-dc.md`): anonymous
  PMOS-body nets rewritten to `vdd`, the two internal per-side input rails
  promoted to `.SUBCKT` pins `vinp`/`vinn`, MiM caps left on the PDK's own
  `cap_mim_2f0_m4m5_noshield` subckt (no rewrite, no ideal-capacitor
  substitution). Wired into a schematic-level comparator + rung-1 SAR
  controller + DR-0013 input drive network by `gen_extracted_core_tb.py`.
  **NOT raw `klt extract` output.**
- **Source extraction**: `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`.
- **PDK binding**: gf180mcuD, open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, resolved via
  `sim/harness/pdk.py`. ngspice-46.
- **Corner matrix run**: `tt`, 27 °C, 3.30 V — **one point, deliberately**.
  - *Why a single point is the right subset here* (`sim/README.md` requires a
    stated reason): this record's claim is a **capability** claim — does
    statistical variation reach the extracted devices at all, and on which
    device classes — not a distribution claim about ADC performance over PVT.
    A PVT sweep of a capability question re-answers the same yes/no 27 times.
    The corner-matrix half of #89 is carried by
    `sim/adc-inl-dnl/records/20260805-211605-c59f75d.md` (27 points, full PVT
    matrix per `CLAUDE.md`); this record deliberately holds PVT at nominal and
    moves mismatch instead, which is the same nominal-vs-statistical division
    `spec/monte-carlo-methodology-memo.md` §4 states and the schematic-side
    benches (`sim/mc-cdac-mismatch/`, `sim/comparator-offset-mc/`) already
    follow.
  - Cost, for whoever extends it: 1378 s of ngspice for 120 draws
    (≈ 11.5 s/draw) against this ~1300-device RC-laden netlist.
- **Statistical convention**: N = 120 draws, mismatch-only
  (`sw_stat_mismatch = 1`, `sw_stat_global = 0` — this is a *mismatch*
  population, not mismatch + global process spread; the PVT axes own the
  latter). σ is the **population** standard deviation of the measured
  transition error, computed in Python from the 120 parsed draws (see "A
  numerical trap", below). Seed `20260805` via ngspice's `setseed`, the one
  seeding control `sim/device-mismatch-mc/` verified actually works.
- **Probed quantity**: the input-referred error `v(ex_err)`, in LSB, at the
  deciding trial of transition **256** — the weight-256 sub-array MSB carry,
  the largest charge-division ratio this array forms, independently the
  slowest-settling trial (`sim/cdac-bit-settling/`) and the analytically
  worst code for mismatch (`sim/mc-cdac-mismatch/`). The choice is inherited
  from `sim/adc-inl-dnl/`'s deck header, not re-derived here.

## Result

| population | `sw_stat_mismatch` | N | mean (LSB) | σ (LSB) | distinct draws |
|---|---|---|---|---|---|
| mismatch-on | 1 | 120 | +0.48655595 | **1.991769e-03** | 120 |
| null control | 0 | 12 | +0.48659340 | **0.0** | 1 |

- Range of the mismatch-on population: +0.482190 … +0.492580 LSB.
- σ ratio on/off: **∞** (required ≥ 100). **PASS** — the population really is
  varying, and the control really is frozen.
- The deck's own `mc_mean` / `mc_sigma` scalars agree with the Python figures
  to all printed digits (+0.48655595 / 1.991769e-03), an independent
  cross-check of the parse.
- Re-running the whole script a second time with the same seed reproduced
  σ = 1.991769e-03 LSB exactly.

**Reading it**: MOS local mismatch contributes σ ≈ 2.0e-3 LSB (3σ ≈ 6.0e-3
LSB) to the error at the array's worst carry on the extracted core — about
**5 % of that transition's own DNL** (≈ 0.10 LSB, `sim/adc-inl-dnl/records/20260805-211605-c59f75d.md`)
and three orders below the < 1 LSB ratified bound. It is a real, non-zero,
reachable statistical term; it is not a spec threat.

### PDK statistical support, re-asserted before anything was simulated

`sim/tools/pdk_mismatch_audit.py` is imported and run by the script, so a PDK
revision that changes either finding changes this record's answer instead of
leaving a stale sentence behind. Both findings held on this run:

| finding | present in gf180mcuD? | holds? |
|---|---|---|
| `mos-local-mismatch` | **PRESENT** | yes |
| `cap-local-mismatch` | **ABSENT** | yes |

The capacitor evidence, verbatim from the audit:

> `sm141064.ngspice: mimcap_statistical defines 3 mc_c_cox_* term(s)` ·
> `mc_c_cox_1p0fF='mc_c_cox_1p0fF2*sw_stat_global*cap_mc_skew'` ·
> `mc_c_cox_1p5fF='mc_c_cox_1p5fF2*sw_stat_global*cap_mc_skew'` ·
> `every one is gated on sw_stat_global (die-global), which cancels in a
> capacitor RATIO and so contributes no CDAC DNL/INL`

Every extracted FET is written by `klt extract --pdk gf180mcuD` as a real PDK
subcircuit call (`X$149 … vdd pfet_03v3 L=… W=…`), i.e. the same
`fets_mm`-wrapped subckt the schematic deck instantiates — which is *why*
`sw_stat_mismatch` reaches all ~296 of them without anything special being
done to the extraction. The extracted MiM caps likewise bind to the same
`cap_mim_2f0_m4m5_noshield` subckt as the schematic ones, and therefore
inherit the same **absent** local-mismatch term.

## Why the #14 CDAC-mismatch bench is answered rather than re-run

`sim/mc-cdac-mismatch/` runs the dominant #14 term **behaviourally**, off a
literature matching coefficient, precisely because gf180mcu carries no
capacitor local-mismatch model. Extraction changes nothing about that: the
extracted capacitors bind to the same subckt with the same missing term, so a
post-layout re-run of that deck would resimulate the same behavioural
coefficient against capacitors that still have no statistical model, and mint
a record containing no new information. Stating that explicitly is what Scope
item 2's "state explicitly if not" asks for; running it anyway would be
evidence theatre.

## A numerical trap this run walked into, recorded so the next one does not

Two failures were found by *running* code that had previously only been
written, and both produce a plausible-looking wrong answer rather than an
error:

1. **`.param sw_stat_mismatch=1` placed before the PDK includes is silently
   overridden.** `design.ngspice` sets the switch to 0 and ngspice's `.param`
   is last-wins, so the first full population was 120 draws of the identical
   zero-mismatch circuit: a healthy-looking mean and σ = 0. This is exactly
   the collapse `sim/device-mismatch-mc/`'s header documents. The switches now
   follow the includes.
2. **`meas` echoes its result at 6 significant figures regardless of
   `numdgt`**, so a loop that also `print`s the same vector emits two
   differently-rounded lines per draw and any `^e =` parser silently reports
   2N samples for N. The draw is now copied into a distinctly-named vector.
3. **σ computed in-deck as `sqrt(s2/n - (s/n)^2)` returns NaN for a frozen
   population.** For the null control every draw is bit-identical, the two
   terms cancel to a tiny *negative* radicand, and ngspice returns NaN — which
   propagated into the on/off ratio and **failed the run for "not varying"**,
   the exact opposite of what an exactly-frozen control means. σ is now
   computed from the parsed draws with a two-pass form (and the in-deck
   expression is clamped at 0 so the cross-check stays readable).

The null control is what surfaced (1) and (2) rather than letting them reach a
record. It is not optional here.

## What this does and does not license

**Licenses**: the statement, with evidence, that the extracted post-layout
netlist accepts MOS-mismatch Monte Carlo exactly as the schematic netlist
does, and that MOS mismatch is a ≈ 2e-3 LSB (1σ) term at the array's worst
carry. Also licenses the negative statement about CDAC capacitor mismatch —
as an audit of the model library, cited to the audit tool, not as a
simulation result.

**Does not license**: any claim about ADC performance *distribution* over PVT
(one corner), about comparator offset distribution (the comparator is
schematic-level in this harness by construction), or about the CDAC mismatch
term itself (still `sim/mc-cdac-mismatch/`'s behavioural claim on either
netlist).

## Reproduce

```
export PATH="$HOME/.local/ngspice/bin:$PATH"
python3 layout/adc-top/parasitics/mc_extracted_core.py \
    --samples 120 --control-samples 12 --ngspice-threads 1 \
    --json  layout/adc-top/parasitics/reports/20260805-extracted-core-mc/mc_extracted_core.json \
    --log-dir layout/adc-top/parasitics/reports/20260805-extracted-core-mc
```

- Result JSON — **all 120 individual draws**, both populations, wall times,
  the PDK audit and the netlist provenance string:
  [`../reports/20260805-extracted-core-mc/mc_extracted_core.json`](../reports/20260805-extracted-core-mc/mc_extracted_core.json)
- The exact decks simulated, byte-for-byte as composed (`.temp`, the corner
  `.lib` sections, the statistical switches in their load-bearing position,
  the remediated core, the control block):
  [`../reports/20260805-extracted-core-mc/mc_extracted_core_mm_on.spice`](../reports/20260805-extracted-core-mc/mc_extracted_core_mm_on.spice),
  [`../reports/20260805-extracted-core-mc/mc_extracted_core_mm_off.spice`](../reports/20260805-extracted-core-mc/mc_extracted_core_mm_off.spice)
- Raw ngspice logs are written by `--log-dir` (as above) but are **not
  committed**: the repository `.gitignore` drops `*.log` everywhere except
  `sim/*/corners/*/*.log`, and the mismatch-on log is 2.7 MB of repeated
  operating-point node dumps for a ~1300-device netlist. Every number this
  record states is in the committed JSON, and the logs regenerate from the
  committed decks above.

- **Timestamp / author**: 2026-08-05, Loom Builder (issue #89).
- **Supersedes**: (none) — this is a new claim, not a correction. The
  schematic-side Monte Carlo records (`sim/mc-cdac-mismatch/`,
  `sim/device-mismatch-mc/`) stand unchanged.
