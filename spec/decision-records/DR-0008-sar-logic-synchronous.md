# DR-0008: SAR logic style — synchronous, M = 16

- **Status**: ratified — Builder agent, issue #11
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #11
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #3, #4, #7, #11, #12, #13, `spec/prior-art-survey.md` §4,
  DR-0003, DR-0011, DR-0010

## Context

`spec/prior-art-survey.md` §4 surveys synchronous, asynchronous/self-timed,
and hybrid SAR control-logic styles and hands #11 a primary recommendation
(synchronous, `M = 16`) with high confidence, but the original issue text
that seeded #11 pointed at "the #3 survey decision record" as if the choice
were already ratified — #3 delivered the survey and a shortlist only (§4.5),
not a ratified decision. #11 is the record that closes it, and #7's
clocking/interface decisions (DR-0003, DR-0005) now depend on it being
closed: DR-0003 states plainly that "#11's synchronous-logic recommendation
is now load-bearing rather than merely convenient" once an external clock
pin is committed.

## Decision

**Synchronous SAR logic, `M = 16`.** An external clock steps a one-hot
16-phase sequencer through sample → 10 bit trials → output/reset every
conversion, deterministically, regardless of comparator decision time. Per
DR-0003: **16 MHz at the 1 MS/s target, 32 MHz at the 2 MS/s stretch.**

The hybrid alternative (clocked cycle boundaries with an internal
comparator-ready handshake) is **not adopted, but is the named fallback**
if a later comparator characterization (#4/#9) shows decision times far
slower than `spec/prior-art-survey.md` §4.2's ~1 ns estimate — see
Consequences.

## Alternatives considered

- **Asynchronous / self-timed** — not chosen. Its entire benefit is
  recovering the gap between worst-case and average comparator decision
  time (survey §4.2); at 1 MS/s with `M = 16` there is **~40 ns of slack per
  62.5 ns bit cycle** against a ~22 ns typical budget (DAC settle +
  comparator decision + logic propagation), and ~9 ns of slack remains even
  at the 2 MS/s stretch. This block does not have the speed problem
  asynchronous logic exists to solve. It also carries a concrete,
  gf180mcu-specific tax: no high-delay standard cell exists in the PDK
  today (survey §4.3, citing `sky130_mm_sc__hd_dlyPoly5ns` as the open-source
  precedent for what one costs to build and characterize) — new scope
  outside this ADC and a strong candidate for a klayout-tools friction
  filing if pursued. Simulability is the sharpest differentiator (§4.4):
  asynchronous logic cannot be decomposed for verification — every
  analog Monte-Carlo run would have to carry the full comparator → logic →
  DAC loop, multiplying the cost of #13's most expensive campaign, and
  introduces a transient-convergence hazard at near-metastable decisions.
- **Hybrid (clocked boundaries + comparator-ready handshake)** — not chosen
  as the primary; kept as the escalation path. It recovers most of the
  async timing benefit while keeping externally-referenced cycle
  boundaries, but still needs a ready-detection path and a timeout, and
  partially reintroduces the closed-loop simulation problem asynchronous
  logic has. With ~40 ns of measured slack already in hand (see Spec lines
  affected below), there is no evidence yet that motivates paying that
  cost.

## Consequences

- #12 designs the bit-cycle timing budget against a supplied 16 MHz (32 MHz
  stretch) external clock; #7's clock-source pin requirement (DR-0003) is
  the input this decision consumes, not one it re-derives.
- The analog core (CDAC + comparator) can be verified standalone against an
  ideal clocked bit-pattern source, with no digital feedback loop — this is
  what makes #13's full PVT/Monte-Carlo matrix tractable at all (survey
  §4.4). An asynchronous choice would have made every analog Monte-Carlo run
  carry the full loop.
- A stalled or near-metastable comparator decision corrupts at most one bit
  and cannot stall the conversion; `sim/sar-logic-timing/` measures this
  directly (the `tie` loop: drdy keeps arriving every 16 clocks even with
  the comparator pinned on an exact tie for the whole run). An asynchronous
  design would instead need a timeout/watchdog against exactly this failure
  mode.
- **Bad consequence, stated plainly**: synchronous logic needs a clean
  16–32 MHz clock at the block boundary — one more package pin and a board-
  level integration requirement (already accepted by DR-0003, not
  re-litigated here). It also fixes every bit-trial slot to the
  *worst-case* comparator decision time rather than the average, which is
  strictly slower than a well-behaved asynchronous loop at high sample
  rates — irrelevant at this block's 1–2 MS/s target, but a real limit if
  the rate target ever moves well above 2 MS/s (survey §4.5's own
  reconsider condition).
- **Escalation trigger, stated concretely**: if #4/#9's comparator
  characterization measures decision times that consume a large fraction of
  the ~40 ns slack margin (`sim/sar-logic-timing/`'s own measured boundary
  is narrower than the survey's arithmetic-only estimate — see Spec lines
  affected), the hybrid alternative above becomes the next escalation to
  evaluate, via a superseding record — not a silent redesign.
- This record does not decide redundancy / non-binary weighting (DR-0009,
  a separate, orthogonal decision) or the mixed-signal simulation strategy
  used to verify this choice (DR-0010).

## Spec lines affected

- `README.md#target-specification` — Latency / conversion timing row —
  clarified (no value change): the existing "M = 16 clocks per conversion"
  / "4 sample + 10 bit-trial + 2 reset/output" row already states this
  decision's numeric consequence; this record is the rationale the row
  rests on. `sim/sar-logic-functional/` measures the row directly
  (`conv_period_ns` = 1000.0 ns exactly, all three supply corners).
- `spec/prior-art-survey.md#4-axis-3--sar-logic-synchronous-vs-asynchronous`
  — none — this record ratifies §4.5's shortlisted primary recommendation
  as-is; no survey content changes.
- **New finding beyond the survey, recorded here because it affects #12's
  timing budget**: the survey's §4.2 ~40 ns slack figure is an arithmetic
  estimate (62.5 ns cycle − ~22 ns typical budget); `sim/sar-logic-timing/`
  measures a narrower boundary in a real closed loop — exact at 50 ns of
  added comparator-decision delay (80 % of the cycle), already 1 LSB over
  the 0.5 LSB pass bound at 52 ns. The gap between the survey's estimate and
  the measured boundary is attributed to that testbench's own RC DAC-settling
  model (`τ = 2.56 ns`) consuming part of the delay budget the survey's
  arithmetic treated as separate, not to a flaw in the synchronous
  architecture — see `sim/sar-logic-timing/testbench/tb.json`'s
  `abs_err_delay_50ns` check description and DR-0010. #12 should treat ~50 ns
  (not the survey's ~40 ns) as the working slack figure for the rung-1
  model, pending a transistor-level (rung-3) re-measurement of the same
  boundary.
