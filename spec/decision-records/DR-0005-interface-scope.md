# DR-0005: Interface scope for simulation-complete — parallel output register, SPI deferred

- **Status**: ratified — operator sign-off 2026-07-31 (#1, recorded in DR-0006)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #7
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #7, #11, #13, `spec/prior-art-survey.md` §4.4, §4.5, DR-0004

## Context

The README's Interface row promises "SPI-readable + parallel" as the
*ultimate* target but says nothing about how much of that must exist at the
first rung of the maturity ladder. #11 therefore cannot scope the output
register, and #13 cannot scope its digital-interface verification, without an
explicit interface-scope line drawn for the simulation-complete milestone.
The milestone is graded on ENOB / INL / DNL over PVT and Monte Carlo, so the
question is which parts of the interface actually have to exist — and at what
fidelity — for those numbers to be earned honestly.

## Decision

**In scope for simulation-complete: the 10-bit parallel output register
only**, at full transistor level, designed and verified. **The SPI serial
interface is explicitly deferred past the simulation-complete milestone** —
it is not designed or verified for this milestone's acceptance.

The parallel register is kept at transistor level rather than modeled,
because it is the digital block that physically loads the CDAC/comparator
boundary; that loading is an analog effect the milestone's numbers depend on.
SPI sits behind that register and touches no analog node, so its absence
cannot change any number the milestone is graded on.

## Alternatives considered

- **Full transistor-level SPI in scope for simulation-complete** (the
  issue's option a) — not chosen. SPI is a well-understood, low-analog-risk
  digital communication protocol whose correctness is proven by digital
  functional verification, not by the PVT-corner/Monte-Carlo analog campaign
  this milestone's acceptance criteria — and CLAUDE.md's "no claim without a
  testbench" for analog claims — are built around. Building and verifying it
  now spends schedule on a block whose risk this repo's methodology is not
  optimized to retire, without moving the ENOB/INL/DNL numbers the milestone
  is actually graded on.
- **Behavioral-only interface models for simulation-complete** (the issue's
  option c) — not chosen as the primary answer. A behavioral model (XSPICE
  primitives or an RTL co-simulation via `d_cosim`/`ivlng`, `spec/prior-art-survey.md`
  §4.4) would not exercise the output register's actual transistor-level
  timing and loading on the CDAC/comparator's digital boundary — a real (if
  small) interaction the analog verification plan should not simply assume
  away. Behavioral models remain available as the *fast* fidelity level for
  long campaigns (§4.4's three-level scheme), but they are not the sign-off
  level for the register itself.

## Consequences

- #11 designs and delivers the parallel output register at transistor level;
  no SPI state machine, shift register, or pad-level serial protocol work is
  in its scope for this milestone.
- #13's testbench suite scopes its digital-interface verification to the
  parallel output register only; SPI functional verification is out of scope
  for simulation-complete and becomes a named follow-up milestone (not filed
  as a spinoff issue by this record — see CLAUDE.md's "issues are
  suggestions" note; a later curator/architect pass can file it when useful).
- **Bad consequence, stated plainly**: a part at "simulation-complete" per
  this maturity ladder does not yet have a working serial readout. The
  DRAFT table's "SPI-readable + parallel" promise is only partially met at
  this rung, and that gap must be visible in the README, not implied away.
  Deferral also means the SPI block's own boundary requirements (pin count,
  clock-domain crossing from the SAR clock of DR-0003, register-map width)
  are discovered later, when the parallel register's layout and floorplan are
  already fixed — a rework risk accepted knowingly here.

## Spec lines affected

- `README.md#target-specification` — Interface row — clarified (no value
  change): the ultimate target ("SPI-readable + parallel") is unchanged, but
  the simulation-complete milestone's scope is narrowed to parallel/output-
  register only; SPI is deferred to a later maturity rung.
