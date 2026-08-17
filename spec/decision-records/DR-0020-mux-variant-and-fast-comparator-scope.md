# DR-0020: Multi-channel input mux and comparator-only fast threshold-detect — out of scope for this block

- **Status**: ratified — Builder agent, issue #226
- **Date**: 2026-08-17
- **Decided by**: Builder agent, issue #226
- **Supersedes**: none — first record on multi-channel/mux scope
- **Superseded by**: (none while this record stands)
- **Related**: #226, `README.md#target-specification` (Input, Interface
  rows), [DR-0001](DR-0001-input-drive.md), [DR-0013](DR-0013-input-pin-charge-split.md),
  [DR-0015](DR-0015-comparator-topology.md), [DR-0017](DR-0017-adc-top-area-budget-overrun.md)

## Context

Issue #226 was filed from a chip-level integration exercise: an integrator
wants this ADC shared as a **muxed** converter across several slow channels
(supply, shunt current, temperature) plus fast comparator-class threshold
detection, on a die that also carries switching power/driver structures. The
ratified spec (DR-0006) already describes a single input pair (Input row) fed
by one CDAC array, and DR-0015 already designs the comparator as a sequential
decision element used only by the SAR sequencer — but neither states plainly
that a mux variant or a repurposed fast-comparator path is out of scope. A
reader integrating this block at the chip level has no explicit statement to
work from, only an absence.

## Decision

**This block, as designed, verified, and laid out, is a single-channel
converter.** Two capabilities a chip-level integrator may want are explicitly
**out of scope** for this repository's deliverable, not silently assumed
available:

1. **N-channel input mux.** No channel-select mux, address decode, or
   per-channel sample-and-hold is designed, verified, or laid out. This is a
   real, costed addition, not "just add a mux in front":
   - **Area.** An N:1 analog mux adds N series switches sized to the same
     R_on/settling class as the existing input T-gates (21.3–60.0 Ω over PVT,
     [DR-0016](DR-0016-input-structure-ron-repoint.md)) plus channel-select
     decode, on top of a block that is already **over** its `< 0.1 mm²`
     target at the ratified `C_u` ([DR-0017](DR-0017-adc-top-area-budget-overrun.md)).
   - **Speed.** Each channel switch adds its own track-mode RC ahead of the
     existing 30 ns input time-constant budget
     ([DR-0013](DR-0013-input-pin-charge-split.md)). An N-channel mux either
     divides the per-channel settling window by roughly N or stretches the
     4-sample-cycle window (M = 16 clocks/conversion, DR-0003), extending
     total conversion latency for every channel, not just the muxed ones.
   - **Crosstalk.** No channel-to-channel isolation spec exists today, and
     per CLAUDE.md's "no claim without a testbench" rule, none can be
     asserted without a dedicated channel-isolation testbench (mux R_on
     corner sweep, off-channel injection through mux parasitic capacitance)
     that this repository has not built.
2. **A comparator-only fast threshold-detect mode.** DR-0015's comparator is
   a sequential, StrongARM-latch decision element clocked by, and consumed
   only by, the SAR control logic (`design/sar-logic/`): it resolves one
   CDAC-residue bit per bit-trial, and its output is read by the SAR
   sequencer, not brought out to a pin as an independently triggerable fast
   comparator. An over-current-protection-class (OCP) threshold detector — a
   comparator that runs continuously/asynchronously against a fixed
   threshold, independent of and concurrent with ADC conversions — is a
   **different circuit** with a different verification burden (continuous-time
   bandwidth and propagation-delay spec, no SAR-cycle amortization of offset
   cancellation) and is **not designed, verified, or drawn here.**

Both capabilities, if wanted, belong to a **separate block, or a future,
explicitly-scoped variant of this one** — not an assumed extension of the
current deliverable. The closest thing achievable today without new design
work on this repository's part is a system-level analog mux **external** to
this ADC, sized and characterized by the integrator, feeding the single input
pair this block already specifies. An OCP-class fast comparator belongs with
whichever block is switching the current being protected (for example a
gate-driver-class block such as `2AMLogic/gf180-gate-driver`) or as its own
standalone comparator IP — not as a repurposed tap of this ADC's internal,
SAR-sequencer-owned comparator.

## Alternatives considered

- **Design an N-channel mux variant now, folded into this block.** Not
  chosen: no channel-crosstalk testbench exists to verify it against, and
  area is already over budget before adding mux devices
  ([DR-0017](DR-0017-adc-top-area-budget-overrun.md)); expanding scope here
  would compete with the base single-channel spec's own open rows (#211
  SFDR/ENOB, #198 area) rather than help close them.
- **Expose the internal comparator's output as a free-running threshold
  pin.** Not chosen: DR-0015's tier-0 offset cancellation, bias current, and
  noise verification are all conditioned on the SAR sequencer's own use
  pattern (multiple strobes per conversion, offset digitally removed once
  per full conversion). Using it as a continuously-running threshold detector
  was never verified and would need its own offset/noise/propagation-delay
  campaign — effectively DR-0015's whole verification tree, redone for a
  different duty cycle.

## Consequences

- README's Input row (single input pair) and DR-0015's comparator description
  are unchanged in meaning; this record makes explicit what was previously
  only implicit, and adds a "Multi-channel / mux integration" section to
  README so an integrator does not have to infer scope from an absence.
- A future N-channel mux variant or standalone OCP comparator, if pursued,
  needs its own decision record, its own crosstalk/propagation-delay
  testbenches, and its own area/timing budget — not an amendment to this
  record.
- **Bad consequence, stated plainly**: an integrator who needs shared
  multi-channel telemetry or an OCP-class fast path gets no help from this
  repository beyond "build it externally, or as separate scope" — that gap is
  named, not closed, by this record.

## Spec lines affected

- `README.md#target-specification` — Input row — clarified (no value
  change): a single input pair only; no channel mux is in scope for this
  block.
- `README.md` — new "Multi-channel / mux integration" section — new: states
  this record's decision and cost analysis for a reader who has not read
  `spec/decision-records/`.
