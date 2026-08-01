# DR-0009: Redundancy / non-binary weighting — not adopted for simulation-complete

- **Status**: ratified — Builder agent, issue #11
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #11
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #3, #8, #11, `spec/prior-art-survey.md` §4.5, §2.5, DR-0006,
  DR-0008

## Context

`spec/prior-art-survey.md` §4.5 flags redundancy / non-binary weighting as
"related but separate, deferred to #11/#8" — cheap insurance against
incomplete DAC settling and comparator metastability, used by both surveyed
sky130 12-bit designs and, via MSB-split sub-radix-2 correction, the sky130
10-bit closest-match design. It is explicitly orthogonal to the sync-vs-async
choice (DR-0008) and was left for this issue to decide on its own merits
rather than being implied by it. #8's CDAC switching-scheme record
(DR-0006) already committed to a plain-binary array — `2^(N-1) = 512` unit
positions per side, weights `256..1` plus one fixed terminating unit,
9 switched trials summing to `511` — without redundant capacitance, so this
record either ratifies that choice explicitly for the logic side or reopens
it; leaving it unstated (as the survey warns) is not acceptable.

## Decision

**No redundancy / non-binary weighting for the simulation-complete
milestone.** The array stays plain binary as DR-0006 already sized it (one
decision per trial, no bit overlap, no digital error-correction adder), and
`design/sar-logic/` implements exactly one decision sequence per output
code (`sim/sar-logic-functional/`'s exhaustive 1024-code sweep in each input
mode is possible at all only because this holds).

This is a **defer, not a permanent rule**: redundancy is not ruled out for a
later milestone, and the trigger for revisiting it is stated concretely
below rather than left open-ended.

## Alternatives considered

- **Adopt now (sub-radix-2 / non-binary weighting with digital error
  correction)** — not chosen for this milestone. Its stated purpose is
  insurance against incomplete DAC settling and comparator metastability
  (survey §4.5, citing Kuttner 2002 and Liu 2011); `sim/sar-logic-timing/`
  measures directly that this block does not currently need that insurance:
  the design tolerates comparator-decision delay up to 80% of the 62.5 ns
  bit cycle before any error appears, and a comparator pinned on an exact
  tie for an entire run still produces a conversion on every 16-clock
  boundary with the code landing on one of the two adjacent, both-correct
  codes rather than propagating a wrong branch. Both are the specific
  failure modes redundancy exists to absorb, and both already have margin
  without it. Adopting it now would also cost real design and verification
  scope this milestone does not need: extra bit trials (more than 10 for the
  same resolution), a digital error-correction adder in `design/sar-logic/`,
  and an enlarged CDAC array in `design/cdac/` — all outside DR-0006's
  already-ratified sizing.
- **Adopt only the free-MSB / top-plate-sampling trick as "redundancy"** —
  not a real alternative; DR-0006 already adopts top-plate sampling for a
  different reason (the ~50% array-size reduction of MCS switching, survey
  §2.4), and it does not add any bit-overlap or correction capability. Not
  counted as redundancy here.

## Consequences

- `design/sar-logic/gen_sar_logic.py`'s 9-slice, plain-binary decode
  (`sar_slice` × 9 + a terminating `sar_bitreg`) is the ratified
  architecture, not a placeholder pending a later redundant rework.
  `sim/tests/test_sar_logic_netlist.py::test_nine_switched_weights_free_msb`
  asserts the weight set `[256, 128, ..., 1]` summing to `511` as a
  structural fact this record depends on.
- `sim/sar-logic-functional/`'s exhaustive-code methodology (1024
  conversions per input mode, one bit-trial decision sequence per code) is
  valid only under plain binary weighting; a future redundant array would
  need a different exhaustive-coverage argument (bit-overlap means multiple
  decision sequences can map to the same code), so this record is a
  precondition for that testbench's methodology, not an incidental fact
  about it.
- **Bad consequence, stated plainly**: this block carries no digital margin
  against a comparator whose real (post-#4/#9, post-#12 gf180mcu
  standard-cell) decision-and-propagation time turns out to exceed the
  measured ~50 ns rung-1 boundary (DR-0008's Spec lines affected). At
  rung 1, exceeding it produces an outright wrong bit with no correction
  path — `sim/sar-logic-timing/`'s `bad` (70 ns) loop demonstrates exactly
  this failure mode as its negative control.
- **Concrete revisit trigger**: if #4/#9's measured comparator decision time,
  or #12's measured gf180mcu standard-cell logic-propagation delay, consumes
  a large fraction of the ~50 ns rung-1 margin once re-measured at
  transistor level (rung 3, DR-0010), redundancy is the next escalation to
  evaluate — via a record superseding this one, not a silent design change.

## Spec lines affected

- none — this is a scope/architecture decision, not a change to a ratified
  spec parameter. It confirms DR-0006's already-ratified array sizing
  (511 binary-weighted positions, no redundant capacitance) applies to the
  logic side as well, without changing any `README.md#target-specification`
  row.
