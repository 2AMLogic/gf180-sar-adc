# DR-0008: Mixed-signal simulation strategy — a three-rung fidelity ladder

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #11
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #2, #3, #9, #11, #13, #15, #17; DR-0005 (parallel output register
  at transistor level), DR-0007 (synchronous logic — the decomposition this
  ladder rests on); `spec/prior-art-survey.md` §3.5, §4.4; `sim/README.md`,
  `sim/harness/README.md`

## Context

Which fidelity the digital controller is modelled at dominates the runtime of
every mixed-signal testbench #13 will build, and #13 cannot scope its matrix
without knowing which campaign runs at which level. `spec/prior-art-survey.md`
§4.4 lists what the flow provides but stops at "three fidelity levels … results
compared"; it names no campaign and no sign-off path. The original #11 text
calls out the specific gap: *the path from whichever abstraction is chosen to
the netlist that layout/LVS will actually use* must not be left implicit,
because that is where a fast-simulation shortcut silently stops being evidence
about the thing that gets fabricated.

DR-0007's synchronous decision is the precondition for any ladder at all: a
clocked controller lets the analog core be simulated with no digital block
present, which is the only reason the expensive campaigns are affordable.

### What the engine actually provides (verified 2026-08-01, not assumed)

Probed against the **pinned** engine (`ngspice-46`, `sim/toolchain.json`), not
the distro `ngspice-42` also present on the machine:

| Capability | Status | How it was checked |
|---|---|---|
| `digital.cm` loaded | **yes** | listed in the install's `spinit` `codemodel` block |
| `d_dff` | **works** | probe deck: `adc_bridge` → `d_dff` → `dac_bridge`, ran to completion, `meas` returned the expected 3.3 V output |
| `adc_bridge` / `dac_bridge` | **works** | same probe deck (they are what crosses the analog/event boundary in it) |
| `d_process` | **present, not usable as-is** | instantiates and runs; forks an external executable and speaks a versioned pipe protocol (`d_process returned invalid version: 10`). Needs a purpose-built binary, which this repo does not have. |
| `d_cosim` | **present, unprovisioned** | instantiates and `dlopen`s a `.so` from the install's `lib/ngspice/`; fails only on a missing object |
| `ivlng.so` / `ivlng.vpi` | **shipped** | both present in `lib/ngspice/` |
| `iverilog` / `verilator` | **absent** | neither is installed on this machine, and neither is pinned in `sim/toolchain.json` |

So the RTL co-simulation path exists *in the engine* and is unprovisioned *in
this repo's toolchain*. That distinction is the whole content of rung 2 below,
and it is stated as a measured fact rather than inherited from the survey.

## Decision

**A three-rung fidelity ladder, with each rung assigned to named campaigns.**
Rung 2 is explicitly **not adopted** for this block.

### Rung 0 — logic-only evaluation, no simulator

`design/sar-logic/sar_logic.py`'s `GateSim` evaluates the *same* structural
element list the transistor netlist is emitted from, as two-valued logic.
No ngspice, no PDK, milliseconds per conversion.

- **Used for**: exhaustive functional verification of the controller — all
  2 × 1024 decision sequences in both input modes, cycle by cycle, against the
  independent reference model in `design/sar-logic/sar_reference.py`
  (`sim/tests/test_sar_logic.py`).
- **Cannot answer**: anything about time, voltage, corner or device.

### Rung 1 — ideal clocked stimulus, controller absent (the workhorse)

The analog core is simulated **standalone**: CDAC bottom plates driven from an
ideal clocked bit-pattern source, comparator clocked from an ideal `pulse`
source, no controller instance in the deck. Where an event-driven digital
element is genuinely wanted, it is an ideal XSPICE primitive
(`digital.cm`'s `d_dff` / `d_source` across `adc_bridge` / `dac_bridge`).

- **Used for**: every long campaign. #13's INL/DNL × PVT matrix and its
  ENOB/SNDR FFT runs; #9's transient-noise Monte Carlo (the campaign
  `spec/prior-art-survey.md` §3.5 identifies as the most expensive item in the
  plan); #8's CDAC mismatch Monte Carlo. `sim/cdac-bit-settling/` is the
  existing worked example of this rung — it drives bit trials from PWL sources
  with no controller present, and runs the full 117-point grid.
- **Why this is legitimate, not a shortcut**: with a synchronous controller
  (DR-0007) the analog core has *no feedback dependency* on the digital block —
  the bit-trial vector is a function of the comparator decisions and the clock,
  nothing else. The stimulus is therefore not a *model* of the controller; it is
  the controller's output vector, supplied directly. Its equivalence to the real
  controller is not assumed: it is established by rung 3 (below), which measures
  that the transistor-level controller produces exactly that vector at every
  PVT corner.

### Rung 2 — RTL co-simulation — NOT ADOPTED for this block

`d_cosim` (Verilator/Icarus-generated model) and the `ivlng` Icarus VPI bridge
are the flow's middle rung, and there is a working open-source existence proof
on an open PDK (`[O: Vaticori/3bit_sar_adc]`, a 3-bit SAR with a Verilog
controller co-simulated against transistor-level analog). **This block does not
use it**, for three reasons:

1. **There is no RTL to co-simulate.** DR-0007 builds the controller as a
   structural custom-cell netlist, not as synthesized RTL. An RTL model would be
   a *fourth* description of the same logic, and the third that could drift from
   the netlist LVS sees.
2. **Rung 0 already covers what rung 2 would cover here.** Rung 2's value is
   fast, exhaustive functional coverage of a digital block; rung 0 delivers that
   for this controller in milliseconds, against an independent reference model,
   with a drift check that fails if the committed netlist and the evaluated
   structure diverge.
3. **It is unprovisioned.** Neither `iverilog` nor `verilator` is installed or
   pinned. Adopting rung 2 means adding a compiler to `sim/toolchain.json`,
   pinning it, and re-validating `docs/environment-setup.md` — real cost for
   coverage rung 0 already provides.

Kept on the shelf rather than deleted: if the deferred SPI interface (DR-0005)
is ever brought into scope it *is* a synthesizable RTL block of a size where
rung 2 earns its keep, and the smoke test to reproduce first is
`[O: Vaticori/3bit_sar_adc]`.

### Rung 3 — full transistor level (sign-off)

`design/sar-logic/sar_logic.spice` — the real gf180mcu netlist — in the deck.

- **Used for**: (a) this issue's own `sim/sar-logic/` corner run, which is what
  licenses rung 1: two conversions, both input modes, the full 45-point `mos`
  PVT grid, asserting the switch vector against the reference model at every
  point and measuring worst-corner clock-to-output delay; (b) the output
  register's own verification, which DR-0005 requires at this level because it
  loads the analog boundary; (c) #13's final closed-loop sign-off — a small
  number of complete conversions with the real controller, real CDAC and real
  comparator in one deck, at a *reduced* corner set with a written
  `--subset-reason`, run once per sign-off rather than per campaign.
- **Cost, measured not estimated**: the controller alone is ~1600 MOSFETs and a
  2.45 µs transient; one PVT point is minutes of CPU, and the 45-point grid is
  the most expensive record in `sim/`. That number is the reason rungs 0 and 1
  exist.

### The path from the fast rungs to the LVS netlist (the explicit ask)

There is exactly one netlist, and it is generated, not transcribed:

```
design/sar-logic/sar_logic.py          structural element list  (THE design)
        |  generate.py  (deterministic; --check fails CI on drift)
        +--> design/sar-logic/sar_logic.spice        <-- rung 3 DUT, and the
        |                                                netlist #15 lays out
        |                                                and #17 LVS-checks
        +--> sim/sar-logic/testbench/tb_sar_logic.spice   (inlines the above
                                                           verbatim -- the corner
                                                           runner forbids
                                                           .include in a fragment)
        |
        +--> GateSim (rung 0) evaluates the SAME element list
```

- **Rung 0 cannot drift from the sign-off netlist**, because it evaluates the
  same in-memory structure the netlist is emitted from, and
  `sim/tests/test_sar_logic.py::test_generated_artifacts_are_current` fails if
  the committed `.spice` no longer matches what the generator emits.
- **Rung 1 is licensed by rung 3, not asserted.** The ideal bit-pattern stimulus
  used in the long campaigns is exactly the control vector the `sim/sar-logic/`
  record measures the transistor-level controller producing, at all 45 PVT
  points, in both input modes. If that record ever fails, every rung-1 campaign
  built on it is invalidated with it — which is the intended coupling.
- **Post-layout (#17) re-enters at rung 3.** The extracted netlist replaces
  `sar_logic.spice` in the same testbench and mints a new record with
  `Netlist provenance: extracted` and `Supersedes:` the schematic-level record,
  per `sim/README.md`. No other rung changes, because no other rung claims
  anything about parasitics.

## Alternatives considered

- **Full transistor level for everything** — not chosen. At the measured cost
  above, #13's INL/DNL × PVT matrix and #9's transient-noise Monte Carlo become
  weeks of compute; the survey's §3.5 already flags the noise campaign as the
  binding cost item before any controller is added to it. This is the option
  DR-0007 was chosen partly to avoid being forced into.
- **Behavioral controller everywhere, transistor level never** — not chosen. It
  would leave the block with no evidence that the real gates meet the bit-cycle
  budget at the slow corner, and it directly contradicts DR-0005's requirement
  that the output register exist at transistor level because it loads the analog
  boundary. "Fast enough at typical" is not a claim this repo accepts.
- **Adopt rung 2 (RTL co-simulation) as the workhorse** — not chosen, for the
  three reasons in rung 2 above. The decisive one is that rung 1 does not model
  the controller at all, so it is strictly cheaper *and* strictly more
  decomposed than any co-simulated model could be; rung 2 would sit between two
  rungs that already meet in the middle.
- **`d_process` (external process co-simulation)** — not chosen. It requires
  writing and maintaining a binary that speaks ngspice's versioned pipe
  protocol, for the same coverage rung 0 already provides in-process.

## Consequences

- **#13 can scope its matrix now**: long campaigns at rung 1, sign-off at
  rung 3, functional coverage at rung 0. The expensive analog runs never carry a
  digital model.
- **#9's transient-noise Monte Carlo stays affordable** — it runs at rung 1 with
  no controller in the deck.
- **#15/#17 have one unambiguous netlist to lay out and extract against**, and
  it is the same file rung 3 simulates.
- **Bad consequence, stated plainly (1): rung 1 is only as good as the rung-3
  record that licenses it.** Every INL/DNL, ENOB and noise number in this repo
  ultimately depends on `sim/sar-logic/`'s claim that the real controller emits
  the assumed vector at every corner. That is a single point of failure by
  design, and it is why that record runs the full 45-point grid rather than a
  subset.
- **Bad consequence, stated plainly (2): closed-loop behaviour is verified
  rarely.** Rung 1 decomposes the loop, so effects that only appear with the
  real controller in the loop — supply bounce from the switch drivers coupling
  into the comparator, clock-to-analog crosstalk, digital switching noise on the
  shared substrate — are seen only in the rung-3 sign-off run and, for
  parasitics, only after #17. A schematic-level ladder cannot see them at all.
  This is a known blind spot, not an oversight.
- **Bad consequence, stated plainly (3): declining rung 2 costs the block its
  RTL portability.** There is no Verilog description of this controller, so it
  cannot be dropped into a digital flow, formally verified, or reused by anyone
  who wants a synthesizable SAR controller. If the SPI interface returns to
  scope, rung 2 has to be provisioned then, at that moment's cost.

## Spec lines affected

- No simulation-strategy row exists in the target-specification table —
  verification methodology constrains downstream design without being a spec
  parameter: none — this is a methodology decision, filed under
  `spec/decision-records/README.md`'s "any architecture choice that constrains
  downstream design" clause, which names mixed-signal simulation strategy
  explicitly.
