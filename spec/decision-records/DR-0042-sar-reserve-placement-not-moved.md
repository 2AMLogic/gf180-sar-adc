# DR-0042: SAR reserve stays below the core; right-column placement needs a notched guard ring

- **Status**: proposed
- **Date**: 2026-10-30
- **Decided by**: builder agent, issue #667 (parent #644)
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none)
- **Related**: #644, #667, DR-0008, DR-0010, DR-0024 (unratified),
  `layout/adc-top/candidates/records/20261030-220000-9b3a3ff.md`

## Context

37,321.5 µm² (24.6 %) of `adc_block` is the full-width band holding the
ringed SAR reserve, while about 20,653 µm² of the core's right column is
empty. #667 asked for one candidate placing the reserve there.

## Decision

Do not move the reserve in this change; commit the placement analysis only.
The best candidate (reserve in the top-right hole, overhanging the core's
right edge, analog ring notched around it) gives about 127,759 µm² (inferred),
not the 114.5k to 123.2k target, and needs an L-shaped guard ring the
generator cannot draw. The 20 µm `ANALOG_DIGITAL_GAP` and boundary guard ring
are kept; DR-0008 and DR-0010 hold unchanged. The Area row stays a disclosed
FAIL.

## Alternatives considered

- **Reserve inside the hole, no overhang** — 148 µm of width against 226 µm
  needed; geometrically impossible.
- **Shrink the gap to fit** — relaxes DR-0008; forbidden.
- **Implement the notched ring now** — generator change plus full
  DRC/LVS/ERC/PEX regeneration, a separate issue; the saving is 15.9 %, still
  failing.

## Consequences

Layout, `area.json` and all signoff records are unchanged. A follow-up issue
can implement the notched ring; it should expect about 127.8k µm², not the
target range, and must re-run every layout check.

## Spec lines affected

none — an analysis and non-adoption record; no spec row changes.
