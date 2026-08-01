# DR-0010: Mixed-signal simulation strategy — three-rung fidelity ladder

- **Status**: ratified — Builder agent, issue #11
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #11
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #2, #3, #11, #13, #15, `spec/prior-art-survey.md` §4.4,
  DR-0008, `design/sar-logic/README.md`

## Context

The original issue text that seeded #11 is explicit that the mixed-signal
simulation strategy "is itself a decision to record," separate from the
sync-vs-async choice (DR-0008), because it "dominates testbench runtime for
the full-suite issues" and therefore has to be written down before #13's
testbench matrix is built against it. `spec/prior-art-survey.md` §4.4 already
verified that the local `ngspice-46` install provides three usable fidelity
levels and found a working open-source existence proof of the fastest two
levels feeding a transistor-level analog core, but stopped short of stating
which level #13's specific campaigns should use or the concrete path from a
behavioural controller to the netlist `layout/LVS` (#15) tapes out — the gap
this record closes.

## Decision

**A three-rung fidelity ladder, with an explicit campaign-to-rung
assignment and a stated path from rung 1 to the sign-off netlist:**

| Rung | What it is | Built from | Status |
|---|---|---|---|
| **1** | Ideal XSPICE event-driven digital primitives (`digital.cm`'s `d_dff`, `d_and`, `d_or`, `d_inverter`) plus `adc_bridge`/`dac_bridge` at the analog boundary | `design/sar-logic/gen_sar_logic.py` -> `design/sar-logic/sar_ctrl.spice` | **Delivered by #11** (this issue) |
| **2** | RTL co-simulation: an HDL model of the same FSM/decode compiled through Verilator or Icarus, loaded via ngspice's `d_cosim` code model or the `ivlng.so`/`ivlng.vpi` Icarus VPI bridge | RTL source (not yet written) driving the same `sar_ctrl_a` port list | **Not yet built** — optional, see Consequences |
| **3** | Full transistor-level: the synthesized/hand-built gate netlist in the target standard-cell library, replayed against the *same* testbenches with `sar_ctrl_a` swapped for the transistor-level subckt of the same port list | `design/sar-logic/` (future) + gf180mcu standard cells | **Not yet built** — owned by the netlist path below, feeding #15 |

**Campaign assignment:**

- **Long PVT/Monte-Carlo campaigns** (the #13 matrix: INL/DNL × PVT × Monte
  Carlo, and any campaign that needs the digital controller merely to
  *exist* in the loop rather than to be the thing under test) use **rung 1**.
  This is what makes those campaigns affordable at all: per
  `spec/prior-art-survey.md` §4.4, the analog core (CDAC + comparator) can be
  verified standalone against an ideal clocked bit-pattern source with no
  digital feedback dependency, so the expensive analog runs never have to
  carry a digital model heavier than rung 1.
- **Sign-off** (the claim that the taped-out gate netlist actually implements
  the sequencing and decode rung 1 specifies) uses **rung 3**, run once
  against the same functional and timing testbenches this issue delivers
  (`sim/sar-logic-functional/`, `sim/sar-logic-timing/`), not against a new
  test plan — see "From rung 1 to the sign-off netlist" below.
- **Rung 2 is optional infrastructure**, not a required gate between 1 and
  3. It exists in the ladder because the toolchain supports it and the
  survey found a working existence proof (`Vaticori/3bit_sar_adc`, a
  Verilog SAR controller compiled through Verilator and co-simulated against
  transistor-level analog), and it is the right tool if a future issue needs
  RTL-speed regression runs during synthesis/PnR iteration. It is not built
  by #11 because nothing in this issue's acceptance criteria or #13's
  matrix currently needs it: rung 1 already gives the analog core its
  standalone verification path, and rung 3 is a one-time sign-off check, not
  an iteration loop, at this milestone.

### From rung 1 to the sign-off netlist

`design/sar-logic/sar_ctrl.spice`
(rung 1) is the **executable specification**, not the netlist that gets
taped out. The transistor-level implementation (rung 3) is built to match
it and is checked against it by replaying `sim/sar-logic-functional/` and
`sim/sar-logic-timing/` with `sar_ctrl_a` swapped for the transistor-level
subckt of the same port list (`clk`, `start`, `mode`, `cmp`, `samp`, `drdy`,
`c9..c0`, and the 54 `rel_n_<w><s>` / `sel_hi_n_<w><s>` / `sel_lo_n_<w><s>`
switch-driver nets) — the port list in `design/sar-logic/README.md` is
stated as a fixed interface for exactly this reason. This gives #15 a
netlist that is checked against the same functional and timing claims #11
already verified, rather than a fresh, unrelated implementation.

**A concrete gap this path already surfaced, recorded here because it is a
PDK fact and not a design choice**: the open gf180mcu PDK ships no 3.3 V
standard-cell library. Both `gf180mcu_fd_sc_mcu7t5v0` and
`gf180mcu_fd_sc_mcu9t5v0` are built entirely from `nfet_06v0`/`pfet_06v0`
(verified by device-reference count in their `spice/` netlists: 4809 and
4816 respectively, zero `*_03v3`), while their Liberty corners
(`tt_025C_3v30`, `ss_125C_3v00`, `ff_n40C_3v60`) are characterized for
exactly this block's 3.3 V supply grid — with 6 V-oxide transistors. DR-0004
ratified "3.3 V devices throughout ... analog signal path **and** SAR
logic / digital interface." Those two facts cannot both hold, so building
rung 3 requires a choice this record does not make: use the shipped 6 V-oxide
cells (which would need a record superseding DR-0004's digital half), or
hand-build 3.3 V-device cells with no existing GDS/LEF/Liberty. **This is
named as an open precondition of rung 3 / #15, not resolved here** — #15 is
where it must be settled before transistor-level sign-off can proceed.

## Alternatives considered

- **Transistor-level for every campaign, no ideal-digital rung** — not
  chosen. `spec/prior-art-survey.md` §4.4 is explicit that this is what makes
  an asynchronous design's verification unaffordable, and it would apply the
  same cost to a synchronous design for no benefit: the digital controller's
  correctness (sequencing, decode) does not depend on gf180mcu gate delay,
  and rung 1 already isolates that claim from the analog PVT/Monte-Carlo
  campaigns that do need transistor-level accuracy on the analog side.
- **RTL co-simulation (rung 2) as the primary campaign level, skipping the
  ideal-primitive rung** — not chosen as primary. Building and validating an
  RTL model and a Verilator/Icarus co-simulation harness before any
  functional verification exists would have blocked #11's own acceptance
  criteria (functional verification of all code paths) behind
  infrastructure this issue does not need to meet them: `digital.cm`'s
  primitives already give a self-contained, single-tool (ngspice-only)
  functional and timing testbench with no external compiler dependency.
  Rung 2 remains available as a later addition without discarding rung 1's
  testbenches, since rung 3 replays the same test plan rung 1 uses.
- **Skip rung 1, go straight from a paper design to rung 3** — not chosen.
  This is the "wrong or under-specified choice" the issue's Curator guidance
  warns blows up #13's verification schedule silently: without a fast,
  self-contained functional check, every sequencing/decode bug (there was
  one found during this issue's own verification pass — see DR-0008's Spec
  lines affected) would only surface after a full transistor-level run,
  multiplying debug cost by however slow gf180mcu simulation is relative to
  ideal-primitive simulation.

## Consequences

- #13's testbench suite scopes its long PVT/Monte-Carlo campaigns to rung 1
  for the digital controller, consistent with the analog-core-standalone
  argument in `spec/prior-art-survey.md` §4.4; #13 does not need to justify
  that choice independently, it can cite this record.
- #15 (layout/LVS) inherits an explicit obligation: build the transistor-level
  controller to the `sar_ctrl_a` port list, then replay
  `sim/sar-logic-functional/` and `sim/sar-logic-timing/` against it rather
  than writing a new test plan, and resolve the DR-0004-vs-PDK gap above
  before that netlist can be called sign-off-ready.
- Rung 2 (RTL co-simulation) is left unbuilt. **Bad consequence, stated
  plainly**: if a later issue needs fast, iteration-speed regression runs
  during synthesis/PnR (e.g. checking a PnR-perturbed netlist against the
  same test plan without paying rung 3's full transistor-level simulation
  cost every iteration), that harness does not exist yet and is new scope,
  not a checkbox already covered by this record.
- This record's own verification pass is itself an instance of rung 1's
  value: bisecting `sim/sar-logic-timing/`'s comparator-decision-delay
  margin at rung 1 (cheap, self-contained ngspice runs) found and corrected
  a testbench-modeling error (DR-0008's Spec lines affected) before any
  transistor-level time was spent on it.

## Spec lines affected

- none — this is a verification-methodology decision, not a change to a
  ratified `README.md#target-specification` row. It fixes which fidelity
  rung substantiates which future claim; `sim/sar-logic-functional/` and
  `sim/sar-logic-timing/`'s own evidence records state their rung
  explicitly (`Netlist provenance: schematic`, rung-1 XSPICE, per their
  "evidence.notes" fields) rather than leaving it implicit.
