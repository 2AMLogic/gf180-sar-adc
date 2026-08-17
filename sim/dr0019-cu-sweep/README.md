# `sim/dr0019-cu-sweep/` — what a bigger `C_u` costs the dynamic rows

**This experiment is an isolation, not a claim about the design.** Every
record under `records/` measures a converter that is *not* the ratified one
(except at `C_u = 35.6528 fF`, which is), and none of them is a verdict on
`README.md`'s ENOB or SFDR rows. Those rows are claimed by
`sim/adc-enob-fft/` at the ratified `C_u`, and a reader must not cite a sweep
point as this block's performance.

## Why it exists

DR-0019 resized the CDAC unit capacitor `17.24 fF → 35.6528 fF` to close the
`Gain error, mismatch` row's 3σ gap, and it closes it. Re-running the dynamic
campaign at the resized value afterwards (issue #204, PR #210,
[`sim/adc-enob-fft/records/20260817-080939-afb1b3a.md`](../adc-enob-fft/records/20260817-080939-afb1b3a.md))
found an unbudgeted regression: worst-corner SFDR `61.33 → 56.41 dB`,
worst-corner composed ENOB `9.163 → 8.507 bits`.

`spec/testbench-suite-memo.md` §11.2 attributes the pre-resize SFDR miss to
the **acquisition's own signal-dependent nonlinearity**, and says in the same
breath that this is *"a nine-point correlation, not an isolation … no
experiment here drives the acquisition bow independently and watches SFDR
follow."* Issue #211 asks for that experiment. This directory is it.

## What is swept, and what is held

The netlist for every point comes out of `design/adc-top/gen_adc_top.py` —
the same generator that emits the ratified deck — via
[`gen_cu_variant.py`](gen_cu_variant.py), which rebinds the single module
constant `C_UNIT_FF` and re-emits. Nothing is templated or patched on the
`C_u` axis, so the nine per-block MiM square sides and every derived comment
are recomputed by the ratified code path. `gen_cu_variant.py --verify-baseline`
(and `sim/tests/test_cu_sweep_variant.py`) assert that this path at
`C_u = 35.6528 fF` reproduces `sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice`
**byte-for-byte** — that is what makes "only `C_u` moved" a checked statement
rather than an assurance.

The manifest [`testbench/tb.json`](testbench/tb.json) copies
`sim/adc-enob-fft/testbench/tb.json`'s `analyses` / `measure` / `checks`
blocks byte-for-byte, and `run_sweep.sh` runs the same 9-point
(3 process × 3 supply, all 125 °C) grid those records use, so every sweep
point is point-for-point comparable with the pre- and post-resize captures
issue #211 reports.

### The C_u axis (seven points)

DR-0019's own two endpoints, three intermediates, one point beyond the
ratified value (so the trend is tested for *continuation*, not merely
interpolated between two known points), and the exact-boundary alternative
DR-0019 considered and rejected:

| `C_u` (fF) | `C_side = 512·C_u` (pF) | why this point |
|---|---|---|
| 17.24 | 8.827 | the pre-resize design — `spec/cdac-sizing-memo.md` §4, historical |
| 22.0 | 11.264 | intermediate |
| 26.0 | 13.312 | intermediate |
| 30.0 | 15.360 | intermediate |
| 33.0 | 16.896 | DR-0019's **rejected exact-boundary** sizing (`σ_u = 0.5208 %`, `s = 3.84 µm`) — the smallest `C_u` that meets the gain-error matching constraint at all |
| 35.6528 | 18.254 | the **ratified** DR-0019 value (`s = 4.0 µm`, `σ_u = 0.5000 %`) |
| 42.0 | 21.504 | beyond the ratified value — a mechanism probe only, **not an admissible sizing**: DR-0019's Consequences cap `C_u ≤ 39.06 fF` on DR-0013's ratified drive contract |

### The orthogonal control (one point)

A plain `C_u` sweep cannot by itself name the mechanism, because growing `C_u`
moves **three** things at once:

1. the acquisition time constant `R_on(V_in)·C_arr` — the §11.2 hypothesis;
2. the charge the array draws from the DR-0002 reference network per
   conversion (i.e. `V_REF` droop);
3. the `C_arr/(C_arr + C_par)` divider the residue is scaled by.

So one extra point holds `C_u` at the ratified 35.6528 fF and widens **only**
the CDAC cell's fourth leg — the `Xsi` T-gate DR-0014 made the input's path
into the array — by 2.068×, from `10u/20u` to `20.68u/41.36u`, leaving the
release / `V_REF` / GND legs ratified so bit-trial drive strength is
untouched. That returns (1) to roughly its pre-resize value while leaving (2)
and (3) at their resized values. If SFDR recovers there, the mechanism is the
acquisition RC; if it does not, it is one of the other two.

## Re-running it

```bash
./sim/dr0019-cu-sweep/run_sweep.sh                    # the whole sweep
./sim/dr0019-cu-sweep/run_sweep.sh 30.0000            # every point at that C_u
./sim/dr0019-cu-sweep/run_sweep.sh cu35.6528-sw2.068  # exactly one point, by tag
python3 sim/dr0019-cu-sweep/analyze_sweep.py --markdown
```

Each point is nine 66 µs transients of a ~1300-device deck: ~8–10 min per
point on an idle 18-core host, and ~26 min per point measured on the same
host with one other campaign competing for cores. `TIMEOUT` (default 7200 s)
is the per-point ngspice cap; it is set well above the uncontended figure on
purpose, because a timeout does not fail loudly — it writes a record full of
`FAIL` corners that then has to be superseded.

`analyze_sweep.py` reads the records' **own raw per-corner logs** and reuses
`sim/adc-enob-fft/testbench/analyze_fft.py`'s transform, so nothing here is
hand-entered and every figure is produced by the same code that produced the
ratified campaign's figures. It re-derives §4.3's noise composition at each
point's own `C_side` rather than carrying the published `0.0488 LSB` across
the sweep (the `kT/C` half of that term is a function of the quantity being
swept); as an arithmetic check it reproduces `0.0488 LSB` exactly at
`C_u = 17.24 fF`.

## Findings

Written up in [`sim/dr0019-cu-sweep-findings.md`](../dr0019-cu-sweep-findings.md).
