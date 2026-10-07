# `sim/vdd-drive-impedance/` — the V_DD pin-network variant generator

**This directory holds a generator only: no testbench, no records.** It is the
V_DD counterpart of [`sim/vcm-drive-impedance/gen_vcm_variant.py`](../vcm-drive-impedance/gen_vcm_variant.py)
(DR-0026), built for issue #393 to grade
[DR-0036](../../spec/decision-records/DR-0036-vdd-decoupling-budget.md)'s
`V_DD` drive budget (`C_dec ≥ 40 nF`, `Z_vdd ≤ 3 Ω`) against the converter.

[`gen_vdd_variant.py`](gen_vdd_variant.py) takes any deck carrying the ideal
island sources (`vddt`/`vddd`/`vddc … dc {vdd_val}`) and replaces them with
**one** shared external-pin network — an ideal source behind `R ‖ L` feeding
`C_dec` to ground — with each island kept alive as a 0 V ammeter so every
`i(vddX)` a manifest measures keeps its name and sign. Each island line is
anchored on its exact text with a per-deck hit-count assertion, so a drifted
deck fails loudly.

```bash
python3 sim/vdd-drive-impedance/gen_vdd_variant.py \
    --deck sim/adc-power/testbench/tb_adc_power.spice --out /tmp/p.spice
```

Defaults are DR-0036's budget at its pessimistic edge (`Z_vdd = 3 Ω`,
`C_dec = 40 nF`) with the `R‖L` corner at the 1 MHz conversion rate. The
reasoning for **one pin rather than three per-island networks**, and for the
**1 MHz corner rather than the 16 MHz bit clock** DR-0002/DR-0026 use, is in
the script's docstring and in [`sim/vdd-full-pvt/README.md`](../vdd-full-pvt/README.md),
which is also where the campaign that uses it, and its findings, live.
`sim/tests/test_vdd_variant.py` checks the substitution, the one-pin
topology and the ammeter polarity without ngspice.
