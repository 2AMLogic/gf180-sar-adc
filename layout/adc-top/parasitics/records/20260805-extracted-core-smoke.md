# Record 20260805-extracted-core-smoke

- **Record ID**: 20260805-extracted-core-smoke
- **Claim**: issue #89 **Scope item 0**. `gen_extracted_core_tb.py` wires the
  PMOS-body-remediated, MiM-mapped extracted `ADC_TOP` core
  (`remediate_extracted.py`, `records/20260805-remediation-dc.md`) into a
  complete conversion chain -- the schematic comparator, the rung-1 SAR
  controller, and the DR-0013 input drive network stay schematic-level, per
  the issue's own wording. `verify_extracted_core_conversion.py` proves that
  wiring actually **converts**: a real transient simulation, three known
  input transitions, one nominal corner. **No spec-line performance claim is
  made** -- the #13 PVT bench, #14 Monte Carlo, and the schematic-vs-extracted
  delta summary (Scope items 1-5, 7-8) all remain deferred; see "What remains"
  below.
- **Netlist provenance**: extracted, then remediated (unchanged from
  `records/20260805-remediation-dc.md`) -- `Netlist provenance: extracted`.
- **Source extraction**: `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`.
- **PDK binding**: gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
  resolved via `sim/harness/pdk.py`. ngspice-46.

## Why a "dedicated harness", not a `gen_adc_top.py` mode

The issue's Scope item 0 offers two paths: "give `gen_adc_top.py` (or a
dedicated harness) a way to instantiate...". `gen_adc_top.py`'s `TARGETS` are
guarded byte-for-byte by `sim/tests/test_adc_top_netlist.py`; carrying a
second, extracted-core code path through `_core()` (which currently
hardcodes two `adc_cdac_side` + two `adc_tp_sw` instances) is a materially
larger, separately reviewable change than reusing what is already exported
(`comparator_block()`, `_preamble()`, `sar.library()`, the timing/geometry
constants) and supplying new wiring only for the one piece that differs: the
analog core. `gen_extracted_core_tb.py` does the latter -- see its own module
docstring for the full pin-mapping table (`_wire_pin()`), which is a literal
restatement of `design/sar-logic/gen_sar_logic.py`'s own
`_ports_ctrl_analog()` naming rule, not a new convention.

**`ADC_TOP` only, not `ADC_BLOCK`.** `ADC_BLOCK`'s `.SUBCKT` bakes the
comparator INTO the extracted core (its pin list exposes `cmpclk` / `dout` /
`doutb` / `ibias`, not `topp`/`topn` for an external one) -- wiring it would
mean the comparator is no longer schematic-level, which is exactly what
Scope item 0 asks NOT to do. `gen_extracted_core_tb.py --top` only accepts
`ADC_TOP`.

## Reproduce

```
python3 layout/adc-top/parasitics/gen_extracted_core_tb.py --top ADC_TOP
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py \
    --json reports/20260805-extracted-core-smoke/verify_extracted_core_conversion.json
```

`verify_extracted_core_conversion.py` steps three known inputs (the bottom
endpoint, the free-MSB transition, the top endpoint -- the same three anchor
transitions `design/adc-top/gen_adc_top.py`'s own `INL_TRANSITIONS` ladder
opens and closes on) through one nominal-corner (`tt`, 27 C, 3.3 V) transient
run, single-ended mode, and reads the decoded code back at the end of each
conversion.

## Results

| transition (expected code) | decoded code | within +/-45 LSB (inherited liveness tolerance) |
|---|---|---|
| 2   | 3.0    | yes |
| 512 | 511.0  | yes |
| 1022 | 1020.0 | yes |

`RESULT: PASS`. Also re-run at the worst-case corner in `sim/harness/corners.py`'s
axes (`ss`, 125 C, 2.97 V) as a robustness spot-check (not part of the
committed JSON, reproducible with `--corner ss --temp 125 --vdd 2.97`): same
three codes decode within 2 LSB of the nominal-corner run, i.e. this wiring
does not merely work at one arbitrarily convenient point.

The decoded codes are within **1-2 LSB** of the expected transitions --
tighter than the inherited +/-45 LSB tolerance by more than an order of
magnitude. That gap is expected and deliberately not tightened here: the
inherited tolerance absorbs the ~31 LSB gain error the OLD (pre-DR-0014)
topology measured, which DR-0014's own derivation (and now this observation)
say should now mostly cancel -- but Scope item 1 (the real PVT/INL/DNL/gain
campaign) is what actually measures and reports that number; this record
observes 1-2 LSB at three points and one corner, which is evidence FOR that
derivation, not a substitute for the campaign that adjudicates it.

## What this does NOT close (still deferred, tracked in #89)

- **Scope item 1** -- the full #13 testbench suite (INL/DNL, ENOB/FFT, power)
  re-run over the 63-point PVT matrix. This record runs 1 corner x 3
  transitions; the static-linearity bench alone is 63 x 18 (`README.md`
  "Compute note").
- **Scope item 2** -- the #14 Monte Carlo re-run.
- **Scope items 3, 8** -- the schematic-vs-extracted delta summary, incl.
  `gain_err_lsb` per corner (#53's adjudication).
- **Scope item 6 baseline caveat** -- unaffected by this record; still applies
  when the delta summary is built (`records/20260805-remediation-dc.md`
  "What remains").

## Artifacts in this record

- `reports/20260805-extracted-core-smoke/verify_extracted_core_conversion.json`
  -- full result (per-transition decode, PDK provenance).

Append-only per `sim/README.md`'s evidence rule: this record never overwrites
`records/20260805-remediation-dc.md` or the extraction record it builds on.
