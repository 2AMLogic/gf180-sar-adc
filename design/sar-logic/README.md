# design/sar-logic — synchronous SAR control logic

The bit-cycle sequencer, the CDAC switch drivers and the 10-bit parallel
output register, at the abstraction [DR-0009](../../spec/decision-records/DR-0009-mixed-signal-sim-strategy.md)
calls **rung 1**: ideal XSPICE event-driven digital primitives with
`adc_bridge` / `dac_bridge` at the analog boundary.

Logic style is fixed by [DR-0007](../../spec/decision-records/DR-0007-sar-logic-synchronous.md)
(synchronous, `M = 16`), weighting by
[DR-0008](../../spec/decision-records/DR-0008-no-redundancy.md) (plain binary,
no redundancy), the switching sequence by
[DR-0006](../../spec/decision-records/DR-0006-cdac-switching-scheme.md)
(MCS / V_cm, top-plate sampling, free MSB), the interface scope by
[DR-0005](../../spec/decision-records/DR-0005-interface-scope.md) (parallel
output register in scope, SPI deferred) and the clock by
[DR-0003](../../spec/decision-records/DR-0003-clocking.md). This directory
implements those decisions; it does not make them.

```
design/sar-logic/
  gen_sar_logic.py   generator -- the single source of truth
  sar_ctrl.spice     GENERATED subckt library (do not edit)
  README.md          this file
```

```bash
python3 design/sar-logic/gen_sar_logic.py           # regenerate
python3 design/sar-logic/gen_sar_logic.py --check   # exit 1 if anything is stale
```

## Why a generator

`sim/harness/testbench.py` rejects `.include` inside a testbench fragment (the
harness owns the includes so one fragment can sweep the whole PVT grid
unedited), so a testbench cannot pull the DUT in by reference — it has to carry
it inline. That means three copies of the same 9-slice, 54-control decode
exist: this library and the two testbench fragments under `sim/`. Hand-editing
three copies is how a testbench silently stops testing the design it claims to.
`gen_sar_logic.py` writes all three, and
[`sim/tests/test_sar_logic_netlist.py`](../../sim/tests/test_sar_logic_netlist.py)
fails CI on every pull request if a committed file stops matching the
generator.

## The conversion, 16 clocks (`M = 16`, DR-0003)

| Phase | Clocks | What happens |
|---|---|---|
| `ph0..ph3` | 4 | **Sample.** `samp` asserted; every bottom plate parked at `V_cm`. |
| `ph4` | 1 | **Trial 1, the free MSB.** No array switching at all — top-plate sampling means the comparator's first decision is the sign of the sampled residue (DR-0006). |
| `ph5..ph13` | 9 | **Trials 2..10.** Weights 256, 128, … 1 engage in turn, each in the direction set by the immediately preceding decision. |
| `ph14` | 1 | Output register loads the ten decisions. |
| `ph15` | 1 | `drdy` asserted; the array releases back to `V_cm`. |

Total 4 + 10 + 2 = 16, which is the ratified Latency row in
[`README.md`](../../README.md#target-specification), and 16 × 62.5 ns = 1 µs
per conversion at 1 MS/s. The cadence is measured, not assumed —
`conv_period_ns` in `sim/sar-logic-functional/`.

The sequencer is a one-hot ring seeded by an initial condition on `ph15`, so
exactly one token circulates from t = 0. `start` is a *synchronous restart*: it
sets stage 0 and clears every other stage on the same edge, so asserting it
cannot inject a second token alongside the circulating one.

## Switch decode

Each of the nine switched weights gets a **slice** carrying two flip-flops: an
engage flag (`eng`, set on the edge entering that weight's trial, held until
the end of the conversion) and a direction bit (`dir`, the decision of the
*previous* trial — which is also this bit position's output bit). Everything
else is combinational:

```
rel     = !eng                         bottom plate parked at V_cm
p side: sel_hi = eng & !dir  -> V_REF   sel_lo = eng &  dir  -> GND
n side: sel_hi = eng &  dir  -> V_REF   sel_lo = eng & !dir  -> GND
        (n side additionally gated by `mode`)
```

Sign convention: `cmp = 1` when `top_p > top_n`, so `dir = 1` means "residue
positive, subtract this weight" — p side down, n side up.

`mode = 1` is differential, `mode = 0` single-ended. DR-0006 is explicit that
this is **not** a cosmetic difference: in single-ended mode only the side that
sampled `V_in` switches and every n-side cell stays released to `V_cm` for the
whole conversion, because driving the reference side too "would double every
step and cost a bit of resolution". Both halves of that rule are checked
directly in `sim/sar-logic-functional/` (`nside_cells_se` must be 0,
`nside_cells_df` must be 9), not merely inferred from the output code.

## Ports

`sar_ctrl` is the digital top (event nodes only). `sar_ctrl_a` is the
analog-boundary wrapper and is what a testbench or a top-level schematic
instantiates:

| Port | Dir | Meaning |
|---|---|---|
| `clk` | in | external clock, 16 MHz at 1 MS/s (DR-0003) |
| `start` | in | synchronous restart; tie low to free-run |
| `mode` | in | 1 = differential, 0 = single-ended |
| `cmp` | in | comparator output, high when `top_p > top_n` |
| `samp` | out | sampling-switch control, asserted `ph0..ph3` |
| `drdy` | out | data ready, asserted `ph15` |
| `c9..c0` | out | 10-bit parallel output register, `c9` = MSB |
| `rel_n_<w><s>` | out | release weight `w` on side `s` to `V_cm` |
| `sel_hi_n_<w><s>` | out | engage weight `w` on side `s` to `V_REF` |
| `sel_lo_n_<w><s>` | out | engage weight `w` on side `s` to `GND` |

`<w>` ∈ {256,128,64,32,16,8,4,2,1}, `<s>` ∈ {p,n} — the CDAC side. The naming
matches [`design/cdac/cdac_array.sch`](../cdac/cdac_array.sch) exactly, where
the leading `_n_` is the **NMOS gate** of that T-gate leg and the trailing
`p`/`n` is the array side. DR-0006's Consequences require `rel` to be driven
per weight *and* per side, and note that the schematic's single shared
`rel_n`/`rel_p` pair is a two-cell drawing economy with the real decode owned
here — these 18 `rel_n_<w><s>` nets are that decode. **`design/cdac/` needs its
`rel` net split accordingly when the full array is elaborated (#15/#16).**

**Only the active-high half of each leg leaves the controller: 54 nets, not
108.** The complementary PMOS gate is generated by `sar_tgate_drv`, one per
leg, placed with the CDAC cell. Routing both polarities from the controller
would double the control-bus width across the array floorplan (#16) to save one
inverter per leg, and a long complementary pair then has to be skew-matched,
which a local inverter does not.

## What rung 1 does and does not establish

The gate delays in this library (`T_CLK_Q = 0.5 ns`, `T_GATE = 0.2 ns`) are
**ideal placeholders chosen small against the 62.5 ns bit cycle**, not gf180mcu
numbers. This netlist is evidence about *sequencing and decode*, and about
*how much of the bit cycle the architecture can afford to lose*
(`sim/sar-logic-timing/`); it is not evidence about gf180mcu gate delay, real
CDAC settling (`sim/cdac-bit-settling/` owns that), comparator behaviour (#9),
or power. DR-0009 states which rung owns which claim.

## Path to the netlist layout and LVS will use (#15)

DR-0009 § "From rung 1 to the sign-off netlist" is authoritative; the short
version is that this library is the **executable specification**, not the
netlist that gets taped out. The transistor-level implementation is built to
match it and is checked against it by replaying these same testbenches with
`sar_ctrl_a` swapped for the transistor-level subckt of the same port list —
which is why the port list above is stated as an interface rather than left
implicit.

One finding from this work that the transistor-level step has to confront
first, recorded here because it is a property of the PDK and not of this
design: **the open gf180mcu PDK ships no 3.3 V-device standard-cell library.**
Both `gf180mcu_fd_sc_mcu7t5v0` and `gf180mcu_fd_sc_mcu9t5v0` are built
*entirely* from `nfet_06v0`/`pfet_06v0` (verified by counting device
references in their `spice/` netlists: 4809 and 4816 respectively, zero
`*_03v3`), while their Liberty corners include `tt_025C_3v30`, `ss_125C_3v00`
and `ff_n40C_3v60` — i.e. they are characterized for exactly this block's
supply grid, but with 6 V-oxide transistors. DR-0004 ratified "3.3 V devices
throughout … analog signal path **and** SAR logic / digital interface". Those
two facts cannot both hold, so the choice — use the shipped cells and supersede
DR-0004's digital half, or hand-build 3.3 V-device cells with no GDS, no LEF
and no Liberty — is a real decision that a future record has to make. It is not
made here, and DR-0004 is not relaxed here.
