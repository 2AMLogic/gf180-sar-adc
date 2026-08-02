# design/sar-logic — synchronous SAR control logic

The bit-cycle sequencer, the CDAC switch drivers and the 10-bit parallel
output register, at the abstraction [DR-0010](../../spec/decision-records/DR-0010-mixed-signal-sim-strategy.md)
calls **rung 1**: ideal XSPICE event-driven digital primitives with
`adc_bridge` / `dac_bridge` at the analog boundary.

Logic style is fixed by [DR-0008](../../spec/decision-records/DR-0008-sar-logic-synchronous.md)
(synchronous, `M = 16`), weighting by
[DR-0009](../../spec/decision-records/DR-0009-no-redundancy.md) (plain binary,
no redundancy), the switching sequence by
[DR-0011](../../spec/decision-records/DR-0011-cdac-switching-scheme.md)
(MCS / V_cm, free MSB) as amended by
[DR-0014](../../spec/decision-records/DR-0014-bottom-plate-sampling.md)
(**bottom-plate sampling**: a fourth one-hot leg per cell and a two-phase
sample — DR-0011 is superseded on the sampling phase only, and everything else
it decided is re-ratified), the interface scope by
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
| `ph0..ph2` | 3 | **Acquire.** `samp_tp` and `samp_bp` both asserted: the top plate is held at `V_cm` by its own switch and every bottom plate tracks `V_in` through the cell's fourth leg. |
| `ph2→ph3` | — | **The sampling instant.** `samp_tp` falls; the top-plate switch opens and the top node floats. |
| `ph3` | 1 | The bottom plates stay on `V_in` one more whole clock, so the input legs turn off onto an already-isolated node (DR-0014). |
| `ph3→ph4` | — | `samp_bp` falls; the bottom plates move to `V_cm`. |
| `ph4` | 1 | **Trial 1, the free MSB.** No array switching at all — the comparator's first decision is the sign of the sampled residue. DR-0014 keeps this: it is a property of sampling the differential input onto the array and comparing before any switching, not of which plate it lands on. |
| `ph5..ph13` | 9 | **Trials 2..10.** Weights 256, 128, … 1 engage in turn, each in the direction set by the immediately preceding decision. |
| `ph14` | 1 | Output register loads the ten decisions. |
| `ph15` | 1 | `drdy` asserted; the array releases back to `V_cm`. |

Total 4 + 10 + 2 = 16, which is the ratified Latency row in
[`README.md`](../../README.md#target-specification), and 16 × 62.5 ns = 1 µs
per conversion at 1 MS/s. **DR-0014's two-phase sample buys its isolation gap
out of the existing sample window, not out of a new clock**: `M`, the 1 µs
conversion and the ratified Latency row are all unchanged. The cadence is
measured, not assumed — `conv_period_ns` in `sim/sar-logic-functional/`.

What it does cost is acquisition time: the input has to be settled by the
`ph2→ph3` edge, so the window is 3 × 62.5 = **187.5 ns** rather than the 250 ns
the superseded top-plate sampling phase had. That is 7.5 τ of DR-0013's 25 ns
input network, and it is bounded rather than assumed (`acq_window_ns`, measured
**187.625 ns**) because `sim/adc-inl-dnl/`'s one-conversion-per-point schedule
rests on it.

Both sample controls are also checked for **order**, not just for existence.
`iso_gap_ns` is the mean of `(sel_in_n − samp_tp_n)/V_DD` over whole
conversions: both controls rise on the same clock edge, so that mean is the
difference of their pulse widths, i.e. how far the top-plate switch's opening
*leads* the bottom plates leaving `V_in`. It must be **positive** — the input
legs have to turn off onto an already-isolated node — and it measures
**62.4888 ns**, one bit cycle. If the two were ever swapped it would read
about −62.5; if the second phase were dropped, 0. Nothing else catches that:
the behavioural loop's sample-and-hold is clocked by the top-plate control *by
construction*, so every code would still come out right.

> **Where each bound lives, and why.** The tight bounds on both numbers are in
> [`sim/sar-logic-timing/`](../../sim/sar-logic-timing/) (8.5 µs at a 5 ns
> timestep; supply-axis spread 4 × 10⁻⁴ %).
> [`sim/sar-logic-functional/`](../../sim/sar-logic-functional/) carries the
> same two measurements with a ±2.5 ns window, as a regression guard against a
> whole clock appearing or disappearing. That split is a correction taken from
> a run, not a preference: the first version of this check measured the two
> falling edges directly in the functional deck, which runs 1024.5 µs at a
> **20 ns maximum timestep** — so a crossing on a 0.3 ns bridge transition is
> interpolated from samples up to 20 ns apart. Record
> `sim/sar-logic-functional/records/20260802-094246-16ec0f1.md` (committed,
> failing) measured this same unchanged design as 61.28 ns at conversion 5 and
> 63.30 ns at conversion 500. That is the instrument's resolution, not the
> design's jitter, and the answer was to measure something the instrument can
> resolve rather than to widen the window until the unresolved number fitted.

The sequencer is a one-hot ring seeded by an initial condition on `ph15`, so
exactly one token circulates from t = 0. `start` is a *synchronous restart*: it
sets stage 0 and clears every other stage on the same edge, so asserting it
cannot inject a second token alongside the circulating one.

## Switch decode — four one-hot legs per cell

Each of the nine switched weights gets a **slice** carrying two flip-flops: an
engage flag (`eng`, set on the edge entering that weight's trial, held until
the end of the conversion) and a direction bit (`dir`, the decision of the
*previous* trial — which is also this bit position's output bit). Everything
else is combinational:

```
in      = smp                          bottom plate on V_in  (DR-0014)
rel     = !eng & !smp                  bottom plate parked at V_cm
p side: sel_hi = eng &  dir  -> V_REF   sel_lo = eng & !dir  -> GND
n side: sel_hi = eng & !dir  -> V_REF   sel_lo = eng &  dir  -> GND
        (n side additionally gated by `mode`)
```

`eng` is zero for the whole sample window, so exactly one of the **four** legs
conducts at every instant. That is the invariant `sim/sar-logic-functional/`
measures as `sw_conflict_*`, and DR-0014 makes it strictly stronger than its
three-leg ancestor: a cell holding `in` together with any other leg shorts the
**input pin** to `V_cm` or to a reference rail, a failure the three-leg check
could not see at all.

`in` is deliberately **not** mode-gated. Both sides must acquire their own
input pin during the sample phase; DR-0011's mode rule is about bit trials. In
single-ended mode the n-side pin sits at `V_cm`, so driving its bottom plates
from it changes nothing electrically — but gating the leg by mode would make
the two sides' sampling switches differ, and side-to-side asymmetry is the one
thing bottom-plate sampling cannot cancel.

### Sign convention, re-derived for DR-0014

`cmp = 1` when `top_p > top_n`, as before — the comparator is wired
conventionally and that meaning holds everywhere in this repo. But sampling on
the bottom plate **inverts the residue** with respect to the input: after the
sample, `top_p − top_n = −k·(V_inp − V_inn)`. The controller therefore takes
the inversion once at its own boundary,

```
dec = !cmp      = 1 when the sampled input is ABOVE the DAC's current
                  estimate, i.e. "add this weight"
```

so `dir` still holds the **output bit** of its position, at the cost of the
`sel_hi`/`sel_lo` assignment above being the mirror of DR-0011's. Exactly one
of the two inversions is not enough: inverting only `cmp` diverges (right code
polarity, wrong feedback direction), and inverting only the decode emits the
one's complement of every code. `sim/sar-logic-functional/` falsifies either
error on all 1024 codes in both modes.

`mode = 1` is differential, `mode = 0` single-ended. DR-0011 is explicit that
this is **not** a cosmetic difference: in single-ended mode only the side that
sampled `V_in` switches and every n-side cell stays released to `V_cm` for the
whole conversion, because driving the reference side too "would double every
step and cost a bit of resolution". Both halves of that rule are checked
directly in `sim/sar-logic-functional/` (`nside_cells_se` must be 0,
`nside_cells_df` must be 9), not merely inferred from the output code.

### Delay balance is load-bearing here

`in` and `rel` are complementary across the sample boundary, and `rel_n` and
`hi_n`/`lo_n` are complementary at a trial edge. Both pairs are produced by
different gates, so the generator equalises their logic depth on purpose:
`smpb` is distributed to the slices already inverted (and `samp_bp` is emitted
through a matching inverter), and `engnb` is built as `!eng | !mode` rather
than as an inverter on `engn`. A one-gate difference in either pair leaves
every cell driving two sources at once for 0.2 ns — a real short, not a
modelling artifact, and `sw_conflict_*` is what catches it.

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
| `samp_tp_n` | out | top-plate `V_cm` switch, asserted `ph0..ph2`; its falling edge is the sampling instant (DR-0014) |
| `sel_in_n` | out | every cell's fourth leg, asserted `ph0..ph3` — one broadcast net, both sides |
| `drdy` | out | data ready, asserted `ph15` |
| `c9..c0` | out | 10-bit parallel output register, `c9` = MSB |
| `rel_n_<w><s>` | out | release weight `w` on side `s` to `V_cm` |
| `sel_hi_n_<w><s>` | out | engage weight `w` on side `s` to `V_REF` |
| `sel_lo_n_<w><s>` | out | engage weight `w` on side `s` to `GND` |

`<w>` ∈ {256,128,64,32,16,8,4,2,1}, `<s>` ∈ {p,n} — the CDAC side. The naming
matches [`design/cdac/cdac_array.sch`](../cdac/cdac_array.sch) exactly, where
the leading `_n_` is the **NMOS gate** of that T-gate leg and the trailing
`p`/`n` is the array side. DR-0011's Consequences require `rel` to be driven
per weight *and* per side, and note that the schematic's single shared
`rel_n`/`rel_p` pair is a two-cell drawing economy with the real decode owned
here — these 18 `rel_n_<w><s>` nets are that decode. **`design/cdac/` needs its
`rel` net split accordingly when the full array is elaborated (#15/#16).**

**Only the active-high half of each leg leaves the controller: 55 nets, not
110.** The complementary PMOS gate is generated by `sar_tgate_drv`, one per
leg, placed with the CDAC cell. Routing both polarities from the controller
would double the control-bus width across the array floorplan (#16) to save one
inverter per leg, and a long complementary pair then has to be skew-matched,
which a local inverter does not.

**DR-0014's fourth leg costs one wire, not eighteen.** All bottom plates sample
together by construction, so `sel_in_n` is a single broadcast net feeding every
cell's fourth-leg driver rather than a per-cell decode that would carry no
information and widen the array bus by a third. The per-cell decode is still
four one-hot legs; one of the four is shared. `samp_tp_n` is likewise one net
for both sides — their skew is precisely the term this topology cannot cancel,
so it is not manufactured by routing two copies.

## What rung 1 does and does not establish

The gate delays in this library (`T_CLK_Q = 0.5 ns`, `T_GATE = 0.2 ns`) are
**ideal placeholders chosen small against the 62.5 ns bit cycle**, not gf180mcu
numbers. This netlist is evidence about *sequencing and decode*, and about
*how much of the bit cycle the architecture can afford to lose*
(`sim/sar-logic-timing/`); it is not evidence about gf180mcu gate delay, real
CDAC settling (`sim/cdac-bit-settling/` owns that), comparator behaviour (#9),
or power. DR-0010 states which rung owns which claim.

## Path to the netlist layout and LVS will use (#15)

DR-0010 § "From rung 1 to the sign-off netlist" is authoritative; the short
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
