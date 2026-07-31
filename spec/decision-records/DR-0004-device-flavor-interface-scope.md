# DR-0004: Device flavor + interface scope

- **Status**: proposed — requires operator sign-off (spec ratification authority sits with engineering per #1)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #7
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #4, #7, #11, #13, `spec/prior-art-survey.md` §4.2, §4.3, DR-0001, DR-0002

## Context

#11 cannot scope the SAR logic / output register, and #13 cannot scope its
digital-interface verification, without a device-flavor decision and an
explicit interface-scope line for the simulation-complete milestone. The
analog signal path (switches, CDAC, comparator input) is already forced to
3.3 V devices by the 0–3.3 V input range (DR-0001); what remained open was
the SAR logic/digital interface's device flavor, and how much of the
SPI + parallel interface is in scope for simulation-complete.

## Decision

**(a) Device flavor: 3.3 V devices throughout** (`nfet_03v3`/`pfet_03v3`) —
analog signal path **and** SAR logic / digital interface, single supply
domain, no level shifters.

**(b) Interface scope for simulation-complete: 10-bit parallel output
register only**, full transistor-level, in scope and verified. **The SPI
serial interface is explicitly deferred past the simulation-complete
milestone** — it is not designed or verified for this milestone's
acceptance.

### What the PDK actually offers (verified, not assumed)

Grepped the `.subckt` declarations in the installed gf180mcuD model file
(`libs.tech/ngspice/sm141064.ngspice`, open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` — the pinned toolchain per
`docs/environment-setup.md`):

```
nfet_03v3, nfet_03v3_dss, nfet_05v0, nfet_06v0, nfet_06v0_dss, nfet_06v0_nvt
pfet_03v3, pfet_03v3_dss, pfet_05v0, pfet_06v0, pfet_06v0_dss
```

gf180mcu ships exactly three voltage-domain FET flavors — 3.3 V, 5 V, and
6 V (plus drain-extended `_dss` and a native `_nvt` variant). **There is no
sub-3.3 V ("core"/1.8 V-class) logic flavor in this PDK at all.** As an
0.18 µm-class MCU-oriented process, gf180mcu does not offer the low-voltage
core-device option that would make a mixed-voltage-domain digital design
meaningful the way it would in a deep-submicron flow.

Given that:

- The analog signal path is already forced onto 3.3 V devices by the input
  range (DR-0001) and by V_REF (DR-0002).
- There is no lower-voltage flavor available for the SAR logic/digital
  interface, even if a design wanted one.
- `spec/prior-art-survey.md` §4.2 already shows the synchronous SAR logic
  has ~40 ns of margin per 62.5 ns bit cycle using "180 nm standard cells at
  3.3 V" — no speed pressure exists that would make a different (nonexistent)
  flavor worth pursuing.

**there is no real trade-off on this axis in gf180mcu.** Single-supply 3.3 V
is not a choice among comparable alternatives — it is the only flavor this
PDK offers that fits the design at all. The 5 V/6 V flavors exist but are
strictly worse for a 3.3 V-native design (larger area, slower, no benefit)
and would only be relevant for I/O pins with an off-chip voltage requirement
this block does not have.

## Alternatives considered

- **Mixed 3.3 V analog / lower-voltage digital domains** — not chosen: no
  sub-3.3 V logic flavor exists in this PDK to mix in; would require level
  shifters and a second supply rail for zero measurable benefit given the
  timing margin already shown.
- **5 V/6 V devices for the digital interface** (e.g. for off-chip-tolerant
  I/O) — not chosen for simulation-complete: no off-chip voltage requirement
  is stated in the target spec (V_REF and V_DD are both fixed at 3.3 V,
  DR-0002), so the extra area/speed cost of thick-oxide digital cells buys
  nothing. Revisit only if a future package/system integration requires
  5 V-tolerant I/O.
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
  option c) — not chosen as the primary answer. A behavioral model would not
  exercise the output register's actual transistor-level timing/loading on
  the CDAC/comparator's digital boundary, a real (if small) interaction the
  analog verification plan should not simply assume away.

## Consequences

- #11 designs the SAR logic and the output register at 3.3 V, single supply,
  no level shifters — the smallest, simplest digital implementation this PDK
  makes available.
- #13's testbench suite scopes its digital-interface verification to the
  parallel output register only; SPI functional verification is out of scope
  for simulation-complete and becomes a named follow-up milestone (not filed
  as a spinoff issue by this record — see CLAUDE.md's "issues are
  suggestions" note; a later curator/architect pass can file it when useful).
- **Bad consequence, stated plainly**: a part at "simulation-complete" per
  this maturity ladder does not yet have a working serial readout. The
  DRAFT table's "SPI-readable + parallel" promise is only partially met at
  this rung, and that gap must be visible in the README, not implied away.

## Spec lines affected

- `README.md#target-specification` — Interface row — clarified (no value
  change): the ultimate target ("SPI-readable + parallel") is unchanged, but
  the simulation-complete milestone's scope is narrowed to parallel/output-
  register only; SPI is deferred to a later maturity rung.
- No explicit "device flavor" row exists in the table — device flavor is an
  implementation detail, not a spec parameter, so this decision affects no
  additional spec line: none — device flavor has no spec-table representation.
