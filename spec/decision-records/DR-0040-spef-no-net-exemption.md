# DR-0040: the SPEF annotation gate may exempt an unannotated output only when klt calls it floating and an independent connectivity proof shows it has no net

- **Status**: ratified
- **Date**: 2026-10-17
- **Decided by**: Operator ruling (Robb), attended session 2026-10-16, batch 11
  Q3 option 1, recorded 2026-10-17 00:37 UTC on issue #486; drafted by a
  Builder agent, issue #486
- **Supersedes**: none — first record for this decision. It narrows, but does
  not replace, the strict "any unannotated driver rejects" rule that #481
  implemented in `spef_audit.gate()`; that rule still applies to everything the
  exemption below does not cover.
- **Superseded by**: (none while this record stands)
- **Related**: #486, #481, PR #532 (all five corners REJECTED on two floating
  CTS dummy-load outputs), `design/sar-logic/flow/spef_audit.py`,
  `sim/tests/test_spef_audit.py`

## Context

`klt sta` reports `annotation_complete: true` (192/192 design nets) for the
extracted SAR-control SPEF, yet `spef_audit.gate()` still rejects every corner
because OpenSTA counts two CTS dummy-load outputs (`clkload0/Z`,
`clkload1/ZN`) as unannotated drivers. Those pins sit on no net, so there is
no `*D_NET` that could ever carry parasitics for them. The gate cannot be
satisfied by any SPEF, and the strict rule hides which unannotated drivers are
a real defect. Relaxing it naively would let a genuinely dropped net pass as
"floating".

## Decision

An unannotated driver is exempt from the rejection **only when both** hold for
that exact output (`inst/pin`):

1. `klt sta` lists it in `spef_annotation.floating_driver_sample`; and
2. `spef_audit.prove_no_net_outputs` — computed from the routed DEF, the
   as-built Verilog and the Liberty pin lists, never from klt's output —
   names it and finds it on no net in either netlist view.

The proof is fail-closed. The gate refuses the exemption on: a missing or
malformed proof or klt classification; input hashes that differ from the
campaign's DEF/Verilog/Liberty hashes; unknown instances, cells or pins, or a
pin that is not a Liberty output; DEF and Verilog disagreeing about the pin or
its cell; any real net on the pin, including a single-pin net; and incomplete
accounting. Accounting is exact per output: `unannotated_driver_count` must
equal the number of distinct named floating outputs, `floating_driver_count`
must equal the names given, klt must name no non-floating unannotated driver,
and every named output must be proven. A count, a klt classification, or the
fact that a load is a dummy is never sufficient on its own.

Nothing else changes. The eleven aliased timed nets still need parasitics,
every real design net stays covered, audited pin mappings must agree, and
errors or discarded records touching design nets still reject. The 62.5 ns
constraint, the five library corners, the unconstrained-endpoint checks and
the actual-clock-mode disclosure are untouched. No propagated-clock or other
numerical waiver is granted.

## Alternatives considered

- **Keep the gate strict and wait for a released klt carrying klayout-tools#3673**
  — a newer release cannot implement this policy: current main rejects any
  positive unannotated-driver count regardless of klt's version, and the two
  dummy loads would stay unannotated.
- **Accept any corner whose only unannotated drivers klt reports floating** —
  one tool's classification could mask a genuinely dropped net, which the
  negative controls exist to prevent.
- **Patch the SPEF, drop timed nets, or change the circuit to manufacture a
  pass** — each conceals the very condition the gate detects.

## Consequences

- Two floating dummy-load outputs no longer block acceptance, once a
  qualified pinned tool build and fresh evidence exist.
- The gate is more complex: a new prover, new inputs (the three hashes) and
  a larger surface for the offline tests to cover.
- The exemption is only as good as the DEF/Verilog/Liberty agreement. If the
  prover shares a parser defect with the netlists it reads, it can be wrong; the
  existing agreement audit and the adversarial tests are the mitigation.
- This record grants no measurement. Qualifying a supported pinned tool build,
  and re-running the five-corner campaign, remain open work under #486.
  The existing bounded no-parasitics timing claim stands until fresh accepted
  evidence supports a stronger one.

## Spec lines affected

none — this changes the acceptance gate of an evidence-producing audit, not a
ratified spec parameter, and it relaxes no spec value or limit.
