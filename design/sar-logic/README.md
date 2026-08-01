# design/sar-logic — the SAR control logic

Bit-cycle sequencing, CDAC switch drivers and the 10-bit parallel output
register, at transistor level in gf180mcu 3.3 V devices.

Ratified inputs this implements: **DR-0003** (external clock, `M = 16`),
**DR-0004** (`nfet_03v3`/`pfet_03v3` throughout), **DR-0005** (parallel output
register only; SPI deferred), **DR-0006-cdac-switching-scheme** (MCS/Vcm
switching, mode-dependent sequence). Decisions this directory *is* the
implementation of: **DR-0007** (synchronous, custom 3.3 V cells), **DR-0008**
(fidelity ladder), **DR-0009** (no redundancy).

```
design/sar-logic/
  sar_reference.py   spec-level reference model -- the ORACLE, not the design
  sar_logic.py       structural gate list + custom cell set -- THE design
  generate.py        emits the derived artifacts;  --check reports drift
  sar_logic.spice    GENERATED transistor netlist -- the layout/LVS reference
```

## The design is `sar_logic.py`, not `sar_logic.spice`

`sar_logic.py` holds the circuit once, as a list of primitive gate instances,
and everything else is derived from it:

| Derived from it | Where it lands | What it is for |
|---|---|---|
| transistor netlist | `sar_logic.spice` | the netlist #15 lays out and #17 LVS-checks |
| corner testbench | `sim/sar-logic/testbench/tb_sar_logic.spice` (+ `tb.json`) | rung 3 of DR-0008's ladder: the real netlist, full PVT grid |
| logic evaluation | `GateSim`, in-process | rung 0: all 2 × 1024 decision sequences, both modes |

Because rung 0 evaluates the *same* element list the netlist is emitted from,
"verified" and "laid out" cannot come apart. `generate.py --check` runs inside
`sim/tests/test_sar_logic.py`, so a structural change that is not regenerated
fails the test suite rather than shipping a netlist that no longer matches its
verification. **Regenerate after every change:**

```bash
python3 design/sar-logic/generate.py          # write
python3 design/sar-logic/generate.py --check  # report drift, write nothing
```

There is no synthesis step and no standard-cell library in this path — see
DR-0007 for why (gf180mcu's two digital libraries are built from 6 V devices,
which DR-0004 rules out for this block) and for the cost that carries.

## Why the reference model is a separate file

`sar_reference.py` is written from the ratified records — the phase map, the
switching table, the output word — and knows nothing about how the logic is
built. The tests check the *structure* against *it*. A model derived from the
netlist would agree with the netlist by construction and prove nothing.

## Verifying

```bash
python3 -m unittest discover -s sim/tests -v         # rung 0: exhaustive, seconds
python3 sim/run_corners.py sar-logic --timeout 3600  # rung 3: full PVT, hours
```

The corner run is the most expensive record in `sim/` (~1600 MOSFETs over a
2.45 µs transient at 45 PVT points), which is exactly why the exhaustive
functional sweep lives at rung 0. See DR-0008.

## Interface

```
.subckt sar_logic clk rstb mode cmp | <switch drives> | d1..d10 eoc | vdd vss
```

| Pin | Direction | Meaning |
|---|---|---|
| `clk` | in | external clock, `M × f_s` (DR-0003) |
| `rstb` | in | asynchronous, active-low reset; lands the sequencer in acquire |
| `mode` | in | `1` = differential (both CDAC sides switch), `0` = single-ended (only the `V_in` side switches — DR-0006-cdac-switching-scheme) |
| `cmp` | in | comparator decision, captured at the edge that ends each trial |
| `samp_n` / `samp_p` | out | sampling-switch drive, complementary T-gate pair |
| `rel_*`, `sel_hi_*`, `sel_lo_*` | out | per-weight, per-side bottom-plate drives; `_n`/`_p` are the T-gate's NMOS/PMOS gates |
| `d1..d10` | out | parallel output register, MSB first, held for a full sample period |
| `eoc` | out | new code available (asserted in cycle 0 of the following period) |

`mode` is static configuration, not a per-conversion input: the testbench only
changes it mid-acquire, where no cell is engaged.
