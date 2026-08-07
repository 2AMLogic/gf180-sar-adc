# Record 20260806-adc-block-resistor-markers-pass

- **Record ID**: 20260806-adc-block-resistor-markers-pass
- **Claim**: issue #118's Revised Acceptance Criterion 4 -- with the
  comparator's two load resistors now drawn WITH `SAB`/`RES_MK`/`Resistor`
  markers (`layout/adc-top/lib/place.draw_poly_resistor`, issue #118), so
  they extract as real `ppolyf_u_1k` devices (1000 ohm/sq) instead of a
  Poly2 short, `verify_extracted_core_conversion.py --top ADC_BLOCK` now
  **PASSes** at both `tt_27c_3.30v` and `ss_125c_2.97v` -- the same three
  transitions, same tolerance, same corners `records/
  20260806-adc-block-comparator-smoke.md` recorded as a reproducible
  **FAIL** (decode stuck at 1023, all bits set, at both corners). This
  record supersedes that FAIL's disposition for the specific root cause it
  left open (the un-marked resistor bodies), not for the whole record --
  see "Relationship to the prior FAIL record" below.
- **Netlist provenance**: extracted (remediated: PMOS-body -> `vdd` local
  remediation of klayout-tools#555; input rails promoted to `vinp`/`vinn`)
  wired to the rung-1 SAR controller + DR-0013 input drive network
  (comparator baked into the extraction, `ADC_BLOCK`) --
  `Netlist provenance: extracted`.
- **Source extraction**: `layout/adc-top/parasitics/reports/
  20260806-230838-56be937/adc_block.para.spice` (this repo's own
  `run_extract_parasitics.py`, re-run against the issue #118 geometry;
  `adc_block` now reports `device_count=1349` / `net_count=198` /
  `pin_count=71` / `device_counts.ppolyf_u_1k=2`, up from 1347/196/69/{}
  before this change -- see `layout/lvs/cells/cells.json`'s `adc_block`
  entries for the full re-baseline).
- **PDK binding**: gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
  resolved via `sim/harness/pdk.py`. ngspice-46.
- **Repo git sha**: base commit `56be937e75e21051f4d91ff20988c1c1d56c1623`
  (`feature/issue-118`, this record's own files and the issue #118 code
  change land together in the same PR).

## Reproduce

```
python3 layout/adc-top/gen_comparator.py
python3 layout/adc-top/gen_adc_top.py
python3 layout/adc-top/parasitics/run_extract_parasitics.py
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK \
    --json reports/20260806-adc-block-resistor-markers-pass/verify_extracted_core_conversion_tt.json
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK \
    --corner ss --temp 125 --vdd 2.97 \
    --json reports/20260806-adc-block-resistor-markers-pass/verify_extracted_core_conversion_ss125c2.97v.json
```

## Results

| top | corner | transition (expected code) | decoded code | within tolerance |
|---|---|---|---|---|
| `ADC_BLOCK` | `tt_27c_3.30v` | 2 | 2.0 | yes |
| `ADC_BLOCK` | `tt_27c_3.30v` | 512 | 511.0 | yes |
| `ADC_BLOCK` | `tt_27c_3.30v` | 1022 | 1020.0 | yes |
| `ADC_BLOCK` | `ss_125c_2.97v` | 2 | 2.0 | yes |
| `ADC_BLOCK` | `ss_125c_2.97v` | 512 | 511.0 | yes |
| `ADC_BLOCK` | `ss_125c_2.97v` | 1022 | 1020.0 | yes |

**`RESULT: PASS`** for `ADC_BLOCK` at both corners: every probed transition
tracks the known code within the inherited `+/-45 LSB` liveness tolerance
(`design/adc-top/gen_adc_top.py`'s own INL/DNL liveness check), at both a
nominal and the worst-case PVT corner this harness's axes reach. Contrast
with `records/20260806-adc-block-comparator-smoke.md`'s prior run at the
SAME transitions/corners, which decoded **1023** (all bits set) on every
probe at both corners.

## Relationship to the prior FAIL record

`records/20260806-adc-block-comparator-smoke.md` root-caused the stuck
decode to a solver `singular matrix` warning on an anonymous internal net
(`xdut.$168`) and left the underlying identity of that node **unresolved**
within its own scope, while noting the decision-latch's cross-coupled
topology as the likely location. Two SEPARATE defects were later found to
both be present at that time (`layout/README.md`'s friction table, `git log`
on `feature/issue-116`):

1. The comparator's differential inputs were **floating** (a `Vpp`/`Vpn`
   alias-merge naming defect in `gen_comparator.py`, fixed on `main` before
   this issue started -- see `parasitics/records/
   20260806-adc-block-comparator-input-float.md`). Fixing it alone was
   **not sufficient** to make `ADC_BLOCK` convert.
2. The comparator's two 150 kohm load resistors extracted as a Poly2
   **short** (no resistor device class recognised the drawn geometry),
   collapsing `pop`/`pon` onto `vdd` and removing the preamp's gain --
   independently confirmed by `probe_comparator_load_short.py` (schematic
   comparator, shorted vs. drawn: identically 0.000000 V differential
   output when shorted, vs +/-0.106 V / +/-0.166 V as drawn) and filed
   upstream as `2AMLogic/klayout-tools#595`.

This record's PASS is the direct resolution of defect (2): the resistor
bodies are now real, LVS-visible `ppolyf_u_1k` devices (issue #118), so
`pop`/`pon` are no longer shorted to `vdd`, and `ADC_BLOCK` converts. This
does NOT retroactively explain `xdut.$168`'s specific identity in the prior
record (that record's own scope never traced it to a named net), but the
functional symptom it was standing in for -- a decision stuck at a single
constant code, independent of the array's actual input -- is now resolved
at both corners this record probes.

## What this still is NOT

Same scope caveat as the prior smoke records: this is `verify_extracted_
core_conversion.py`'s three-transition, two-corner liveness smoke test, not
the #13 INL/DNL/ENOB/power suite re-run (issue #89 Scope item 1), the #14
Monte Carlo re-run (Scope item 2, still explicitly gated `--top ADC_TOP`
only in `mc_extracted_core.py`), or the schematic-vs-extracted delta
summary's `gain_err_lsb` line (Scope item 3/8). `sim/extracted-delta-
summary.md` §6.4 is updated to say the comparator-inclusive extracted core
now converts, and to restate precisely what remains open below that.

## Artifacts in this record

- `reports/20260806-adc-block-resistor-markers-pass/verify_extracted_core_conversion_tt.json`
- `reports/20260806-adc-block-resistor-markers-pass/verify_extracted_core_conversion_ss125c2.97v.json`

Append-only per `sim/README.md`'s evidence rule: this record never
overwrites `records/20260806-adc-block-comparator-smoke.md` or any other
prior record.
