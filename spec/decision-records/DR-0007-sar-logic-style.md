# DR-0007: SAR logic style — synchronous, M = 16, custom 3.3 V cells

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #11
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #3, #4, #11, #12, #13, #15, #16; DR-0003 (external clock, M = 16),
  DR-0004 (3.3 V devices throughout), DR-0005 (parallel output register),
  DR-0006-cdac-switching-scheme (MCS/Vcm switching);
  `spec/prior-art-survey.md` §4.1–§4.5;
  `sim/sar-logic/` (this design's worst-corner logic propagation delay),
  `sim/` record `20260731-231537-1ee5578` (per-bit CDAC settling)

## Context

`spec/prior-art-survey.md` §4 (issue #3) surveyed synchronous, asynchronous and
hybrid SAR control logic and produced a *shortlist with a recommendation*, not a
decision. #12 (bit-cycle timing budget), #13 (testbench suite) and #16
(floorplan) all list this issue as a blocker, so the choice has to be fixed in
`spec/` before those can close. DR-0003 already ratified the clock source that
the synchronous option depends on — an external pin at `M × f_s`, `M = 16` —
and closed the one condition §4.5 named as grounds for reopening the trade
("reconsider if #1/#7 adds a requirement for a low-frequency-only external clock
interface"). What remained open was the control-logic style itself.

**On scope — why the cell set is in this record and not its own.**
`spec/decision-records/README.md` requires one decision per record, and exempts
"implementation detail already fully determined by a ratified record". The cell
set is that case: DR-0004 ratified `nfet_03v3`/`pfet_03v3` **throughout**, and
neither of gf180mcu's two digital libraries is built from those devices, so a
custom 3.3 V cell set is what DR-0004 *entails* rather than a second choice made
here. It is written down anyway because it is surprising, because it is load-
bearing for #15's layout scope, and because a reader who assumes a standard-cell
flow would otherwise mis-plan around it.

## Decision

**Synchronous SAR control logic**, clocked from the DR-0003 external clock at
`M = 16 × f_s` — **16 MHz at the 1 MS/s target, 32 MHz at the 2 MS/s stretch**.
One clock cycle per bit trial; the sample period is 16 cycles = 6 acquire
cycles + 10 bit trials. No self-timed loop, no comparator-ready handshake, no
internal delay element anywhere in the block.

**The logic is built from a custom 3.3 V cell set**, not from a gf180mcu
standard-cell library. gf180mcu ships exactly two digital libraries,
`gf180mcu_fd_sc_mcu7t5v0` and `gf180mcu_fd_sc_mcu9t5v0`, and **both are built
from `nfet_06v0` / `pfet_06v0` devices** — verified by reading the `.spice`
views in the installed PDK (open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`),
not assumed from their names. DR-0004 ratifies `nfet_03v3` / `pfet_03v3`
throughout, SAR logic and digital interface included, and explicitly rejects the
5 V/6 V flavors for digital. There is no 3.3 V digital library in this PDK to
honour that record with, so the design carries its own small cell set:
inverters at four drive strengths, NAND2, NOR2, a transmission gate, a 2:1 mux,
and a master–slave D flip-flop in async-clear and async-preset variants
(`design/sar-logic/sar_logic.py`, `CELL_LIBRARY`).

**Clock rate, stated for its consumers** (#7's clock-source pin requirement is
already ratified in DR-0003; #12 budgets against these numbers):

| `f_s` | `M` | `f_clk` | bit-cycle period | measured worst-corner logic delay |
|---|---|---|---|---|
| 1 MS/s (target) | 16 | **16 MHz** | 62.5 ns | see `sim/sar-logic/` record |
| 2 MS/s (stretch) | 16 | **32 MHz** | 31.25 ns | same number, against a 31.25 ns cycle |

`M = 16` is not a free parameter: `M = ACQUIRE_CYCLES + N_BITS` with
`N_BITS = 10`, so `M = 16` buys exactly 6 acquire cycles (375 ns at 1 MS/s,
187.5 ns at the stretch). Changing `M` changes the acquire window and is a
superseding-record change, not a tuning knob.

### Cycle allocation within the ratified 16 — a divergence, stated

`README.md#target-specification`'s Latency row cites
`spec/prior-art-survey.md` §1.4's *plausible* allocation, "4 sample cycles +
10 bit cycles + 2 reset/output cycles = 16". **This design allocates the same
16 cycles as 6 acquire + 10 bit trials**, with no separate reset or output
cycles:

- **No reset cycle**: reset is asynchronous (`rstb`), so it costs no cycle. It
  is a power-on/error input, not a per-conversion phase.
- **No output cycle**: the parallel output register loads at the clock edge that
  *ends* trial 10, sourced from the decision flip-flops' D inputs rather than
  their outputs, so the completed code is valid at the start of the next sample
  period and holds for all of it (DR-0005 scopes a register, not a strobe).
  `eoc` is asserted in cycle 0 of that period.
- **The freed cycles go to acquisition**, which is where they are worth most:
  6 × 62.5 ns = 375 ns of track time against §1.4's own 300 ns (30 %) target,
  where DR-0001's ≤ 500 Ω source impedance and the ~34 pF track-mode `C_in`
  make settling the binding constraint.

The **ratified value is unchanged** — 16 clocks per conversion, 1 µs at
1 MS/s, one-conversion latency, no pipeline. What changes is the illustrative
decomposition in that row's Notes column, which the survey marked `[D]`
(derived/plausible), not measured. It is listed under *Spec lines affected*
below rather than edited into the table here: DR-0006-spec-ratification makes
the table non-freely-editable, so this record proposes the reconciliation and
operator sign-off carries it.

### Why synchronous, on this block's evidence

1. **Speed margin is not the constraint.** `spec/prior-art-survey.md` §4.2
   budgets a 62.5 ns bit cycle as ~19.5 ns DAC settling + < 1 ns comparator
   + ~1 ns logic ≈ 22 ns, leaving ~40 ns of slack; at the 2 MS/s stretch
   ~9 ns remains. Both halves of that budget are now measured on this design
   rather than estimated: `sim/cdac-bit-settling/` record
   `20260731-231537-1ee5578` shows every bit trial settled with a residual of
   at most 1 × 10⁻⁴ mV against a 1.61 mV (0.5 LSB) bound, at the 62.5 ns *and*
   31.25 ns probes, across all 117 PVT points, and
   `sim/sar-logic/` measures this controller's own clock-to-output delay at
   every corner. Asynchronous logic exists to recover the gap between
   worst-case and average comparator decision time; at ~40 ns of slack per
   cycle that gap is not worth recovering.
2. **The clocking burden is already paid.** DR-0003 ratified an external clock
   pin regardless of this decision, and §4.3 notes a 16–32 MHz clock is
   unremarkable in 180 nm and very likely needed for the deferred SPI interface
   anyway. `M = 16` is demonstrated adequate for a 10-bit SAR in an
   open-source flow (`[O: UAH-IC-Design-Team/sky130-10-bit-SAR-ADC]`, whose own
   notes say its `M = 32` controller could be reconfigured to 16).
3. **Simulability is the sharpest differentiator, and it is what makes #13
   affordable.** With a clocked controller the analog core can be verified
   *standalone* — drive the CDAC bottom plates from an ideal clocked bit-pattern
   source and the comparator from an ideal clock, and the analog block has no
   feedback dependency on the digital block. That decomposition is what makes
   #13's INL/DNL × PVT × Monte-Carlo matrix tractable at all, and it is the
   premise the fidelity ladder in DR-0008 is built on. An asynchronous loop
   cannot be decomposed: every analog Monte-Carlo run would have to carry the
   full comparator → logic → DAC loop, multiplying the cost of the campaign
   `spec/prior-art-survey.md` §3.5 already identifies as the most expensive
   item in the plan.
4. **Asynchronous carries a concrete gf180mcu-specific tax.** The surveyed
   sky130 12-bit self-clocked SAR needed a *custom high-delay standard cell*
   (`sky130_mm_sc__hd_dlyPoly5ns`) fitted to its cell grid to build the timing
   loop `[O: jjbbff/SKY__ADC-2496]`. No equivalent exists in gf180mcu; it would
   have to be designed, characterized over PVT, and DRC/LVS-signed-off — new
   scope outside this ADC, on top of a delay loop that must then be shown to
   track process, voltage and temperature.

## Alternatives considered

- **Fully asynchronous / self-timed** — not chosen. It buys speed this block
  does not need (point 1), costs a custom high-delay cell that gf180mcu does not
  have (point 4), multiplies the cost of the most expensive verification
  campaign (point 3), and replaces "a stalled decision corrupts one bit" with
  "a stalled decision stalls the whole conversion", which then needs a
  timeout/watchdog. Well-proven in the literature `[P: Chen 2006]` at 600 MS/s —
  600× this block's rate, in a node 1.4× finer — so the argument does not
  transfer. **Reconsider if** the rate target moves well above 2 MS/s; DR-0003
  has already closed the low-frequency-clock route to reopening it.
- **Hybrid: clocked cycle boundaries with a comparator-ready handshake inside
  the cycle** — not chosen *now*. §4.5 conditions it on #4 showing a comparator
  far slower than the survey's ~1 ns estimate. It keeps standalone analog
  simulability but still needs a ready-detection path and a timeout, and it
  partially reintroduces the closed-loop simulation problem. Revisit only if
  #4's comparator characterization lands a decision time that eats the measured
  per-cycle slack.
- **Build the logic from `gf180mcu_fd_sc_mcu7t5v0` / `mcu9t5v0` standard cells**
  — not chosen. Both libraries are `nfet_06v0`/`pfet_06v0`, which DR-0004
  explicitly rejects for this block's digital; using them would mean a second
  supply domain and level shifters at the analog boundary, for logic that has
  ~40 ns of slack and does not need the speed. It would also put a synthesis
  and library-characterization step between the verified design and the netlist
  LVS sees.
- **Behavioral-only controller (XSPICE/RTL) with no transistor-level design** —
  not chosen. DR-0005 requires the parallel output register at full transistor
  level because it physically loads the digital boundary of the analog core, and
  the same argument applies to the switch drivers, which drive the CDAC bottom
  plates directly. Behavioral models remain the *fast rung* of DR-0008's ladder,
  not the design.

## Consequences

- **#12 budgets against a fixed 62.5 ns (31.25 ns stretch) bit cycle** with the
  logic's contribution measured at every corner rather than assumed from the
  survey's typical-corner ~1 ns estimate.
- **#13 may verify the analog core standalone**, driving the CDAC from an ideal
  clocked bit-pattern source. This is the single largest cost saving in the
  verification plan and it is a *consequence of this record* — it evaporates if
  this decision is ever superseded by an asynchronous one.
- **#16 floorplans a synchronous digital block** with a clock distribution
  network to 45 flip-flops (16 sequencer + 10 decision + 9 engaged + 10 output
  register) and no analog timing elements. `design/sar-logic/sar_logic.spice` is
  the netlist #15's layout and LVS take as their reference.
- **Bad consequence, stated plainly (1): the custom cell set is unhardened
  scope.** It is not DRC/LVS-signed-off, has no Liberty timing model, and is not
  reusable by any tool that expects a standard-cell library. Every cell in it is
  work #15 must lay out by hand. Choosing gf180mcu's 6 V libraries would have
  bought a hardened, characterized library — at the cost of contradicting
  DR-0004 — and that trade is being taken knowingly. It also means **this block
  cannot be synthesized**: the structural netlist in
  `design/sar-logic/sar_logic.py` is the design, and a change to it is an
  engineering change, not a re-synthesis.
- **Bad consequence, stated plainly (2): a near-metastable comparator decision
  corrupts a bit and nothing corrects it.** With no redundancy (DR-0009) and no
  handshake, a decision that has not resolved by the capture edge is captured
  as whatever the flip-flop's input happens to be, and the resulting code error
  is permanent. The mitigation this design relies on is margin — ~40 ns of
  per-cycle slack at the target rate — not correction. DR-0009 states the
  residual risk and the escalation path.
- **Bad consequence, stated plainly (3): the block cannot run without a clean
  16–32 MHz clock.** That is already DR-0003's cost, but this record makes it
  load-bearing rather than incidental: there is no self-clocked fallback mode
  anywhere in the design.
- **Friction filed upstream.** The fact this decision turns on — which device
  flavor each shipped standard-cell library is built from — is discoverable only
  by grepping the library's SPICE views; no tool exposes it, and a block that
  pins a device flavor in a decision record needs it early. Per CLAUDE.md's
  friction protocol that is logged generically on the public tracker as
  [`2AMLogic/klayout-tools#147`](https://github.com/2AMLogic/klayout-tools/issues/147).

## Spec lines affected

- `README.md#target-specification` — Clock row — clarified (no value change):
  DR-0003 already fixes the external pin and 16 MHz / 32 MHz; this record fixes
  what consumes it (`M = 16` = 6 acquire cycles + 10 bit trials) and states that
  the multiplier is architectural, not a tuning knob.
- `README.md#target-specification` — Latency / conversion timing row, **Notes
  column only** — changed (`4 sample + 10 bit-trial + 2 reset/output cycles` ->
  `6 acquire + 10 bit-trial cycles; reset is asynchronous and the output
  register loads on the edge ending trial 10`). The row's ratified *values*
  (M = 16 clocks per conversion, 1 µs @ 1 MS/s, 0.5 µs stretch,
  one-conversion latency, no pipeline) are **unchanged**; only the survey's
  `[D]`-marked illustrative decomposition is superseded by what the design
  actually does. Not edited into the table by this PR — DR-0006-spec-
  ratification makes the table non-freely-editable, so this line is the
  proposal that operator sign-off of this record carries.
- No "logic style" or "cell library" row exists in the target-specification
  table — both are implementation choices that constrain downstream design
  rather than spec parameters: none — logic style and cell library have no
  spec-table representation, and this record is filed under
  `spec/decision-records/README.md`'s "any architecture choice that constrains
  downstream design" clause.
