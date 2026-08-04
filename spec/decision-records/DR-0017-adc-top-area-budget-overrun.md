# DR-0017: adc-top drawn area exceeds the ratified `< 0.1 mm²` target at the legal MiM geometry

- **Status**: proposed
- **Date**: 2026-08-04
- **Decided by**: Builder agent, issue #80 (**proposing**; operator ratification
  required — the area row is part of the DR-0006 ratified target-spec table, and
  per DR-0006 and `CLAUDE.md` only the operator ratifies a change to it)
- **Supersedes**: none — first record on the area target; on ratification it
  revises the `Area` row of the DR-0006 target-spec table, and DR-0006's
  `Superseded by` back-pointer is filled in **at that ratification**, not here
- **Superseded by**: (none while this record stands)
- **Related**: #80 (this decision), #70 (the MiM-stack fix that surfaced the
  overrun), #69 (decode-bank `comp.space.1` DRC floor), #67 (the prior
  DR-0014 area regression), DR-0006 (the ratified target-spec table),
  DR-0008 (analog/digital isolation), DR-0010 (SAR-logic rung-1 reserve),
  `spec/cdac-sizing-memo.md` §4 (`C_u` = 17.24 fF / 2.7136 µm),
  `layout/adc-top/README.md` "Area, as drawn";
  reproducible evidence: `layout/adc-top/area_feasibility.py`,
  `layout/adc-top/area.json`;
  upstream tool gap blocking the one remaining lever:
  [klayout-tools#261](https://github.com/2AMLogic/klayout-tools/issues/261)

## Context

The DR-0006 target-spec table (`README.md#target-specification`) ratifies an
`Area < 0.1 mm²` target. That target was drawn against with slack — `adc_block`
measured 0.09619 mm² (96 %, #69) — until #70 corrected the CDAC unit-capacitor
stack. The old 3.914 µm MiM unit pitch drew a stack that violated `MIMTM.3`
(0.6 µm Metal4-over-FuseTop enclosure) 4896 times: it was never a
manufacturable number, only an unchecked one. Drawing the **ratified** device
legally — the `C_u` = 17.24 fF / 2.7136 µm plate, plus `MIMTM.3`'s 0.6 µm ring
each side and `MIMTM.1`'s 1.2 µm spacing — forces a 5.1136 µm unit tile
(1.31× per direction) on the one structure the block draws 1224 of, and the
assembled `adc_block` bounding box rose to **0.12100 mm² (121 %, over by
21,005 µm²)**. Issue #80 asks whether a *legal* floorplan pass can recover
that overrun; this record fixes the answer and the target it forces.

## Decision

**Revise the `Area` row of the DR-0006 target-spec table
(`README.md#target-specification`) from `< 0.1 mm²` to `< 0.13 mm²`, and record
the drawn `adc_block` bounding box of 0.12100 mm² as the value it bounds.** The
original `< 0.1 mm²` figure predates the pinned deck's MiM rule coverage and is
unreachable for the ratified unit-capacitor geometry under the pinned DRM; the
new bound reflects the block as it can legally be drawn, with headroom for the
still-undrawn per-weight bottom-plate interconnect. The MiM plate is **not**
resized (that would draw a different device than `design/`/`sim/` simulate), the
decode bank is **not** taken below its `comp.space.1` DRC floor (#69), and the
DR-0008/DR-0010 isolation reserve is **not** shaved — none of which this record
authorizes and all of which `CLAUDE.md` forbids as silent spec relaxation.

Recovery to `< 0.1 mm²` is proven infeasible with the tooling pinned in this
repo (see Alternatives). The one lever that could still move the dominant term
by ~2× — folding the single-finger decode devices into multi-finger devices —
is blocked on [klayout-tools#261](https://github.com/2AMLogic/klayout-tools/issues/261)
(LVS device-merge), which is not available at the pinned `klt` commit. If that
gap closes, the target should be revisited by a superseding record.

## Alternatives considered

- **Recover to `< 0.1 mm²` by CDAC-array aspect ratio** — not possible. The
  array is common-centroid tiled over 512 unit positions; only factor pairs of
  512 are legal shapes. `area_feasibility.py` rebuilds the block at every pair:
  the shipped 32 × 16 (0.12100 mm²) is the **minimum**; every other pair is
  worse (16 × 32 → 0.14494, 64 × 8 → 0.16113, …), because the two arrays sit
  side-by-side and a taller array multiplies against the block's larger width.
- **Recover by tighter block packing (whitespace / comparator overhang)** — does
  not close the gap. The decode bank is one row of 144 single-finger devices at
  the `comp.space.1` DRC floor (#69), so `bank_w` = 440.94 µm is not a choice;
  the block height 229.4 µm is the analog stack plus the DR-0008/DR-0010
  isolation gap and SAR reserve. Their product, 440.94 × 229.4 =
  **101,168 µm² > 100,000 µm²**, bounds the block area from below *before any
  whitespace or comparator overhang* — so even a perfectly packed floorplan
  stays over budget. (`area_feasibility.py`, "Irreducible packing floor".)
- **Shrink the MiM plate below the ratified `C_u`** — forbidden. A 2.114 µm
  plate tiles at 4.514 µm and returns the block to ~0.104 mm², but it draws a
  10.9 fF unit capacitor, not the ratified 17.24 fF one. Making an area row pass
  by silently drawing a different device than `design/` and `sim/` simulate is
  exactly the trade `CLAUDE.md` forbids (`spec/cdac-sizing-memo.md` §4 is
  untouched by this record — the drawn geometry *is* that device).
- **Take the decode bank below its `comp.space.1` DRC floor, or shave the
  DR-0008/DR-0010 isolation reserve** — forbidden. Both are silent relaxations
  of a checked DRC rule / a ratified isolation requirement; #69 already took the
  bank pitch to its governing rule, and the 20 µm analog/digital gap plus 40 µm
  SAR reserve implement DR-0008's isolation and DR-0010's rung-1 sequencer
  footprint.
- **Keep `< 0.1 mm²` and carry the block as a permanent, un-annotated fail** —
  not chosen. It leaves a ratified row that no legal layout can satisfy, and
  invites downstream readers to keep quoting the retired 0.09619 mm² number.
  Recording the forced bound is more honest than holding a target the DRM makes
  unreachable.

## Consequences

- **The block layout is compliant with the revised target as drawn** — 0.12100
  mm² < 0.13 mm² — and stops being scored against a target the pinned DRM makes
  unreachable at the ratified unit-capacitor geometry.
- **The die is ~21 % larger than the original planning budget.** That is a real
  cost — more silicon per part, and any floorplan or pad-ring budget built on
  `< 0.1 mm²` must be revisited. The number is the DRM's (legal MiM tiling), not
  slack in this layout.
- **The bound is provisional on tooling.** If klayout-tools#261 (LVS
  device-merge / multi-finger devices) lands in the pin, the single-finger
  decode bank — still one of the two dominant terms — could fold to roughly half
  its width, which would likely bring the block back under the original
  `< 0.1 mm²`. This record's target should then be revisited by a superseding
  record rather than treated as settled.
- **No verification result changes.** `design/` and `sim/` are untouched; the
  drawn device is still the ratified `C_u`. This record moves an area *target*,
  not any measured or simulated quantity, and asserts nothing about ENOB, SFDR,
  INL/DNL, or power.
- **DR-0006's other rows are untouched.** This revises one row of its table; on
  ratification the mechanism is DR-0006's own ("a change to it requires a new
  decision record superseding this one"), scoped to the `Area` row.

## Spec lines affected

- `README.md#target-specification` — `Area` row — changed (`< 0.1 mm²` →
  `< 0.13 mm²`, bounding the drawn `adc_block` at 0.12100 mm²). **Applied on
  ratification, not by this proposed record** — the ratified row and DR-0006's
  `Superseded by` back-pointer are edited by the operator's ratification act,
  per DR-0006 and `CLAUDE.md`.
