# DR-0047: draw the source/drain implants — one merged region per polarity per placement group

- **Status**: superseded-by DR-0049
- **Date**: 2026-11-17
- **Decided by**: Builder agent, issue #836
- **Supersedes**: DR-0035 (*draw and route every well tap and both
  substrate-tie straps, and mark them with implants*) — in its implant SCOPE
  only ("implants are drawn ONLY on the tap structures"), by DR-0032's own
  second revisit trigger, *the curated deck gains implant rules*. DR-0035's
  tap-and-strap geometry, routing and area accounting all stand; this record
  extends the same implant marking to transistor source/drain.
- **Superseded by**: DR-0049 (*draw the latch-up tap lattice*,
  `DR-0049-latch-up-tap-lattice.md`) — in its EVIDENCE-PINS scope only: the
  implant decision stands; DR-0049 amends this record's acceptance-criteria
  evidence pins `well_tap_candidates == 25` /
  `substrate_tie_candidates == 2` (the lattice adds tie structures, and
  one strip Comp merges with the analog ring), not the implant scope.
- **Related**: #836, #797 (the 0.8.0 adjudication that counted the markers),
  #652 (the pin bump this unblocks), DR-0032, DR-0035, DR-0024 (the area
  bound the cost is scored against), #885 (the tap-distance lattice this
  change's evidence surfaces as the next defect), #886 (the extracted-campaign
  re-runs deliberately left behind),
  `layout/drc/records/20261117-171000-3a3d3617.md` (the 0.8.0 measurement),
  `layout/drc/records/20261117-164727-3a3d3617.md` (the 0.6.0-pin run),
  `layout/lvs/records/20261117-164652-3a3d3617.md`,
  `layout/erc/records/20261117-165043-3a3d3617.md`,
  `layout/power/records/20261117-165350-3a3d3617.md`,
  `layout/adc-top/economy/records/20261117-170000-3a3d3617.md`,
  `layout/adc-top/parasitics/records/20261117-165510-3a3d361.md`,
  `signoff/records/20261117-165822-3a3d3617.md`

## Context

DR-0032 deferred drawing implant layers until either of two triggers fired,
and DR-0035 fired the first (*well taps are drawn*) while explicitly
recording that the second — *"the curated deck gains implant rules"* — **had
not**: "a full implant derivation over every S/D is a downstream step this
generated flow still leaves downstream, and no rule in the pinned deck names
31/0 or 32/0, so drawing it would add unverifiable geometry." The
klayout-tools 0.8.0 deck added the DRM's `7.8 Nplus` / `7.9 Pplus` sections
(eight rules: width/space 400/400, gate-region enclosure 230, COMP enclosure
160 near a well / 20 far, cross-space to the opposite implant's diffusion
160 near / 80 far, 5 nm grid), and with them `comp.coverage.1` (DF.12: COMP
not covered by `Nplus` or `Pplus` is forbidden) — which the #797 adjudication
measured firing on **every cell that carries transistor diffusion**: 323
markers on `adc_block`, 296 on `adc_top`, 27 on the comparator, 2–16 on every
decode/switch leaf. The trigger DR-0032 named verbatim is fired; DR-0032's
own text says a fired trigger "should be superseded, not worked around."

## Decision

**Draw the source/drain implants in the placer** — `geo.draw_sd_implants`,
called from `lib/place.py` after `draw_shared_nwell` for every placement
group, one merged region per polarity: the union box of the group's NMOS
actives enlarged `SD_IMPLANT_MARGIN` = 230 nm on every side → one `Nplus`
shape; the PMOS actives likewise → one `Pplus` shape. No Nwell predicate on
either (in this library `Nwell` is drawn only around PMOS actives; NMOS sits
in the undrawn p-substrate). Guard rings and tap strips keep their existing
marking untouched.

The geometry is sized by the deck's own numbers, enumerated before it was
chosen (the issue's first acceptance criterion; full table in the 0.8.0 DRC
record):

- **230** is `nplus`/`pplus.enclosing.poly2.1` (NP.5a/PP.5a): a transistor
  gate is a full-height Poly2 stripe over COMP, so an implant covering a
  device must clear the active's top and bottom edges by the full 230 — 160
  (the diffusion enclosure, NP.5b/PP.5b) is not enough. 230 is the minimum
  legal value and also clears the 160 diffusion enclosure everywhere.
- **Merging per polarity** is what satisfies the 400 nm same-layer spacing
  (NP.2/PP.2) by construction: per-device implants would leave 80 nm slivers
  between adjacent columns (`COLUMN_GAP` 400 vs 2 × 160), and a 10 nm-gap
  sliver pair at the PMOS-to-tap boundary besides.
- **The PMOS-to-tap boundary** needed no constant change: the deck spaces an
  implant from the opposite implant's *diffusion*, never implant-to-implant,
  so `TAP_ACTIVE_GAP` (400) gives 170 nm (Pplus top to tap `NCOMP`, vs 160)
  and 240 nm (tap `Nplus` bottom to PMOS PCOMP, vs 160) — both asserted at
  generation time beside the constant-level enclosure/containment asserts,
  in the `_assert_nwell_clearances` style, so a future constant change fails
  in the generator rather than in DRC.

Measured result (0.8.0 deck, full table in the DRC record):

| | before (`63e502a8…`) | after (`33f6f0c4…`) |
|---|---|---|
| `comp.coverage.1` | 323 (`adc_block`) / 296 (`adc_top`) / 27 / 2–16 | **0 everywhere** |
| `nplus.*` / `pplus.*` markers | 0 | **0** (new geometry clean under the whole 7.8/7.9 families) |
| 0.6.0-pin `klt drc` | clean | **clean, unchanged** (0.6.0 names neither layer — verified, 46 rules) |
| `klt lvs` | match | **match**; extracted netlists differ only in placement-coordinate comments |
| block bbox | 670.93 × 191.92 µm | 671.005 × 191.92 µm (**+14.394 µm², +0.011 %**, 80.49 % of DR-0024's 0.16 mm²) |
| implant shapes | 27 (25 taps + 2 rings) | 86 (51 `Nplus` + 35 `Pplus` by occurrence) |
| `comp.tap_distance.psub.lv.1` (0.8.0) | 0 (vacuous) | 84 / 67 / 15 / 1–8 — **see Consequences** |

## Alternatives considered

- **One implant per device, inside `draw_mosfet`** — not chosen: the two 80
  nm same-polarity slivers measured in #836's curation put adjacent implants
  under the 400 nm spacing rules, and fixing that needs the merge anyway.
- **One block-wide `Nplus` with `Pplus` only over the wells** — not chosen:
  fewer shapes, but it puts `Nplus` over the Nwell taps and guard rings and
  needs subtraction logic the per-polarity merge gets for free; it also
  drags `Nplus` under every well edge, which the deck's near/far
  enclosure split then has to be argued through for no benefit.
- **Clamp the PMOS `Pplus` to abut the tap `Nplus` exactly** — not chosen:
  the deck does not permit "abutment" as such, it demands 160 nm from each
  implant to the opposite implant's diffusion, and the existing
  `TAP_ACTIVE_GAP` already satisfies both sides (170/240) without moving any
  constant. Abutting would also leave zero margin for the `nwell`-edge
  containment the merged box now asserts.
- **Waive or relax `comp.coverage.1` in the repo's deck configuration** —
  forbidden (CLAUDE.md): DF.12 is a real manufacturability rule, not a deck
  artifact; the fix is to draw what the process needs.
- **Defer until #652 lands the 0.8.0 pin** — not chosen: #652 is parked
  precisely because the pin bump breaks the committed evidence; this change
  is part of its unblocking, measured at 0.8.0 in a throwaway env while every
  committed pin stays 0.6.0.
- **Draw the substrate-tap / well-tap lattice the activated DF.13/DF.14
  rules demand, in the same change** — not chosen, and not this record's to
  choose: #836's ratified acceptance criteria pin `well_tap_candidates == 25`
  and `substrate_tie_candidates == 2` (`well-tap-audit.json`,
  `sim/tests/test_well_tap_audit.py`), so the lattice needs its own record
  superseding those pins with its own measured area and routing cost. Tracked
  as #885 with the full marker table already measured.

## Consequences

- **The 0.8.0 deck's headline marker family on this block is gone.**
  `comp.coverage.1` = 0 on all nine adc-top streams, zero `nplus.*`/`pplus.*`
  markers, and the 0.6.0-pin flow is untouched (its deck names neither
  layer) — the committed `clean` verdicts stand over the new bytes
  (`layout/drc/records/20261117-164727-3a3d3617.md`).
- **The evidence trail moved with the geometry, in one PR** (the
  hash-pin coupling #836's curation identified): nine non-report files
  re-pinned (`layout/{drc,lvs}/cells/cells.json`, `layout/{erc,power}/
  cases.json`, `layout/adc-top/parasitics/cells.json`,
  `layout/erc/well-tap-audit.json`, `signoff/gf180-sar-adc.manifest.json`,
  `signoff/freshness.json`, `signoff/layout/layout.analog.json`), new
  DRC/LVS/ERC/power/economy/PEX/signoff records minted, and signoff's items
  3/4/11 (analog) citations re-pointed over the new geometry (verdict
  unchanged at 18/22; no row moved).
- **The extraction is invariant.** The 0.6.0 deck types devices by well
  context, not by implant, so the re-extracted netlists differ from the
  pre-change ones only in placement-coordinate comments (compared directly,
  `adc_top`/`comparator` byte-identical) — device and body-net assignments
  unchanged, which the issue's LVS criterion demanded.
- **The ERC `tie-wrong-implant` discrimination control was redesigned, not
  re-baselined.** `Pplus`-narrowed, it collapsed to `clean` on this stream
  (0 findings, measured) because Pplus-marked PMOS S/D now sits inside every
  well and reaches `vdd`; the control now narrows on **Poly2 30/0** — the
  *transistor* marking, `COMP n Poly2`, 323 non-empty gate-stripe polygons
  inside every well, none of them a tap — and reports the same 25
  `erc.missing_tie` from a non-empty tap region with the rule checked. The
  discriminator moved from what-is-marked to how, for the same reason as
  before: mis-marking the taps must swap the control's and the artifact's
  verdicts.
- **Bad consequence, stated plainly: this change activates DF.13/DF.14.**
  With `Nplus` on all NMOS S/D, `NCOMP outside Nwell` is non-empty for the
  first time and the 0.8.0 deck's 20 µm latch-up tap-distance rules report
  84 markers on `adc_block` (67 `adc_top`, 15 comparator, 1–8 per leaf, plus
  one `nwell`-domain marker on `adc_tgate_dum`'s ~80 µm-tall dummy PMOS).
  Before this change both rules were vacuous; the 0.6.0 pin does not carry
  them. The block's substrate ties are two edge rings and its well taps one
  strip per island — a real tie deficit this marking exposes, exactly as
  DR-0032's marking exposed the untapped wells, and deliberately not fixed
  here (the ratified 25/2 pins above). Tracked as #885 with the table in the
  0.8.0 DRC record.
- **The five extracted sim campaigns and the 117-corner block PEX are stale
  against the new geometry** — disposition (b) of #836's parasitics boundary:
  the single-block extraction was re-taken (total R/C moved ~0.0003 %;
  `layout/adc-top/parasitics/records/20261117-165510-3a3d361.md`), the
  campaigns were not, `parasitics/README.md` re-discloses the staleness, and
  #886 tracks the fleet re-run. Item 7's `input: CHANGED` flag in signoff is
  that disclosure.
- **`well_tap_audit.py` still measures 25 / 2** and both implants present;
  its manifest is re-measured, and `sim/tests/test_well_tap_audit.py` now
  also asserts DR-0035's supersession back-pointer the way it asserted
  DR-0032's.
- **The implants are electrically redundant but not verification-neutral**:
  `klt power` droop figures moved < 0.005 mV at every site (routing
  lengthened by the 0.075 µm bbox growth; no verdict changed) and the
  comparator/leaf-cell layout READMEs' "implants on taps only" statements
  are corrected by this record.

## Spec lines affected

- None — this is a layout-geometry and evidence-scope decision. It changes
  no target parameter or row in `spec/`; the area figure is recorded against
  DR-0024's existing bound (80.49 %, `layout/adc-top/economy/records/
  20261117-170000-3a3d3617.md`) and re-opens nothing.
