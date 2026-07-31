# DR-0004: Device flavor — 3.3 V devices throughout

- **Status**: ratified — operator sign-off 2026-07-31 (#1, recorded in DR-0006)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #7
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #4, #7, #11, `spec/prior-art-survey.md` §4.2, DR-0001, DR-0002

## Context

#11 cannot scope the SAR logic and output register without knowing which
device flavor they are built from, and #4's device-characterization scope
depends on which flavors have to be characterized at all. The analog signal
path (track switch, CDAC, comparator input) is already forced to 3.3 V
devices by the 0–3.3 V input range (DR-0001) and by V_REF = 3.3 V (DR-0002);
what remained open was the flavor for the SAR logic and digital interface —
single-supply 3.3 V throughout, or a second, lower-voltage domain with level
shifters at the boundary.

## Decision

**3.3 V devices throughout** (`nfet_03v3` / `pfet_03v3`) — analog signal path
**and** SAR logic / digital interface, a single supply domain, no level
shifters anywhere in the block.

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
PDK offers that fits the design at all.

## Alternatives considered

- **Mixed 3.3 V analog / lower-voltage digital domains** — not chosen: no
  sub-3.3 V logic flavor exists in this PDK to mix in; it would require
  level shifters and a second supply rail for zero measurable benefit given
  the timing margin already shown (§4.2).
- **5 V/6 V devices for the digital interface** (e.g. for off-chip-tolerant
  I/O) — not chosen for simulation-complete: no off-chip voltage requirement
  is stated in the target spec (V_REF and V_DD are both fixed at 3.3 V,
  DR-0002), so the extra area/speed cost of thick-oxide digital cells buys
  nothing. The 5 V/6 V flavors are strictly worse for a 3.3 V-native design
  (larger area, slower, no benefit) and would only be relevant for I/O pins
  with an off-chip voltage requirement this block does not have. Revisit
  only if a future package/system integration requires 5 V-tolerant I/O.

## Consequences

- #11 designs the SAR logic and the output register at 3.3 V, single supply,
  no level shifters — the smallest, simplest digital implementation this PDK
  makes available.
- #4 characterizes one flavor pair only (`nfet_03v3`/`pfet_03v3`); no 5 V/6 V
  device data is needed for this block, which keeps the characterization
  matrix and its PVT corner set to a single voltage domain.
- **Bad consequence, stated plainly**: the digital logic pays 3.3 V
  thick-gate-class dynamic power and area — in a process with a core flavor
  it would be cheaper on both axes, and that cost is accepted here, not
  avoided. And because the whole block is pinned to one rail, any later
  system requirement for 5 V-tolerant I/O (or for a lower-voltage digital
  domain, should a different PDK ever be targeted) is not a local change:
  it re-opens this decision with a superseding record and introduces level
  shifters and a second supply that no part of the design currently plans
  for.

## Spec lines affected

- No explicit "device flavor" row exists in the target-specification table —
  device flavor is an implementation detail, not a spec parameter: none —
  device flavor has no spec-table representation.
