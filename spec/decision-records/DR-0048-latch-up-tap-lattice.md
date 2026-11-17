# DR-0048: draw the latch-up tap lattice — per-row substrate-tie strips and extra well taps for short PMOS columns

- **Status**: ratified
- **Date**: 2026-11-17
- **Decided by**: Builder agent, issue #885
- **Supersedes**: DR-0047 (*draw the source/drain implants*) — in its
  EVIDENCE-PINS scope only: the implant decision stands unchanged; what is
  superseded is the two evidence pins that decision's acceptance criteria
  froze (`well_tap_candidates == 25` and `substrate_tie_candidates == 2` in
  `layout/erc/well-tap-audit.json` and `sim/tests/test_well_tap_audit.py`),
  by DR-0032's own second revisit trigger *the curated deck gains [new]
  rules*: the klayout-tools 0.8.0 deck transcribed the DRM's DF.13/DF.14
  latch-up tap-distance rules, which made the tap lattice a requirement
  rather than a decoration. Follows the DR-0035 precedent (the marking
  change surfaced the tie deficit; this record draws the ties).
- **Superseded by**: (none while this record stands)
- **Related**: #885, #836 / DR-0047 (the implant change whose evidence
  surfaced the DF.13/DF.14 markers), DR-0035 (the taps this lattice
  extends), DR-0032, #797 (the 0.8.0 adjudication), #652 (the 0.8.0 pin
  bump this unblocks further), `layout/adc-top/economy/records/20261117-203922-0986aeb.md`
  (the area cost), `layout/drc/records/20261117-203113-0986aeb.md` (the
  pinned-flow DRC), `layout/lvs/records/20261117-210055-0986aeb.md`,
  `layout/erc/records/20261117-203416-0986aeb.md`,
  `layout/power/records/20261117-203724-0986aeb.md`,
  `layout/adc-top/parasitics/records/20261117-203842-0986aeb.md`

## Context

DR-0047 drew the source/drain implants. That made the 0.8.0 deck's
latch-up rules live, and the #836 DRC record disclosed the result rather
than passing it: `comp.tap_distance.psub.lv.1` (DF.14_LV — every COMP
polygon outside every well within 20 µm of a p+ substrate tie) measured
84 markers on `adc_block` (67 on `ADC_DECODE_BANK_N`, 4 on `ADC_TOP_SW`,
13 on `COMPARATOR`; `ADC_DECODE_BANK_P`'s row happens to sit within 20 µm
of the bottom guard ring and stayed legal), 67 on `adc_top`, 15 on the
comparator cells, 1–8 on the leaves; `comp.tap_distance.nwell.lv.1`
(DF.13_LV — every COMP polygon inside a well within 20 µm of an n+ well
tap) measured 1 on `adc_tgate_dum`. The pinned 0.6.0 deck names neither
rule, so the committed flow stayed `clean` — a 0.8.0 finding only, which
is why #652's re-baseline hits it too.

The deck's own semantics decided the geometry (read from the deck source,
then confirmed by measurement — the same discipline DR-0047's thresholds
followed): **the selection is of whole active polygons** that do not
interact with the tap reach region (the taps grown by 20 µm), so a polygon
whose bottom edge — every S/D stripe in a row shares `row_y0` — sits
within the reach of one tie is legal no matter how tall the row is, and a
polygon whose TOP edge reaches a well tap's reach is legal no matter how
far its bottom is from that tap.

## Decision

**Two structures, both in the placer, both drawn unconditionally:**

1. **One substrate-tie strip per placed row with NMOS columns**
   (`place._draw_substrate_tie_strip`): a `TAP_COMP_H`-tall `Comp` band
   `Pplus`-marked (`IMPLANT_MARGIN` overhang), contact-arrayed, under one
   continuous `Metal1` bar, hung `SUBTIE_M1_GAP` (500 nm) below the
   channel's deepest trunk. It covers the whole row at once because the
   deck selects whole polygons: every S/D polygon in the row touches the
   strip's grown reach. It routes to `vss` — the net both guard rings
   strap to — by a Poly2 riser to the substrate trunk
   (`subtie_via="trunk"`, the default: every cell this library LVSes
   stand-alone), on a column reserved before track packing: the widest
   gap between the row's drop-riser edges, or — when the row's shared
   source/drain buses leave no gap wide enough for the corridor plus
   `SUBTIE_RISER_COLUMN_CLEAR` (300 nm, `find_stitch_column`'s own demand)
   on both flanks, which is the case in every decode bank — the
   deterministic fallback `SUBTIE_FALLBACK_REACH` (1750 nm) left of
   `row_x0`, where nothing in this library draws Poly2. Rows whose caller
   straps them to the guard ring instead (`subtie_via="ring"` — the
   banks, whose strips reach the analog ring through
   `_strap_guard_rings`' Metal1 bars) draw the strip with no riser and a
   full-width Comp.

2. **Extra well taps over PMOS columns the top strip cannot cover**
   (`geometry.draw_shared_nwell`): the deck flags a whole S/D polygon
   whose top edge sits further than `TAP_DISTANCE_LV` (20 000 nm) below
   the top strip, so an island mixing tall and short columns needs a
   second strip over the short ones. Each extra strip is the same
   construction as the top strip — one `TAP_COMP_H` band
   `TAP_ACTIVE_GAP` above the tallest column it serves, `Nplus`-marked,
   contacted, `Metal1` over it — placed inside the island the top strip
   already grew, routed to `vdd` by the same `PendingTap` machinery, and
   stacked one per remaining height band until every column's top edge is
   inside some strip's reach. Drawn whenever any PMOS active is shorter
   than `SECOND_WELL_TAP_MAX_COVERED` (19 200 nm, the reach minus the
   strip structure minus a 200 nm margin); `adc_tgate_dum`'s 35 µm
   working column under its 80 µm dummy was the one flag, and is covered.

**The area and routing cost is measured, not estimated** (economy record
`20261117-203922-0986aeb`): block bbox 671.005 × 191.92 µm →
671.605 × 194.80 µm, +2 049.374 µm² (+1.59 %), **81.77 % of DR-0024's
0.16 mm² bound** — the strips sit in already-empty field, so drawn area
grew only 834 µm² and whitespace rose. Power droops moved at most
+0.63 mV worst-case (13.29 mV combined at the comparator site, no verdict
changed, DR-0034 budget still `pass`); PEX total R +0.28 %, total C
+1.55 %.

## Alternatives considered

- **A per-tie vertical column in each inter-group gap** — not chosen: the
  strip's `Pplus` must overhang its `Comp` by `IMPLANT_MARGIN` (160) on
  all four sides and clear the neighbouring NMOS `Nplus` by the same
  160 nm, which needs a ≥ 960 nm gap; the banks' `NWELL_KEEPOUT` (900)
  cannot hold one, and widening it costs bank width on every boundary for
  a tie every ~18 µm that a single full-width strip covers better.
- **Strapping the strips to the ring on Poly2, in-row** — not chosen for
  the banks: after the strips span the rows, the only columns left cross
  the strips' own diffusion (a parasitic MOSFET — the hazard
  `geo.stitch` refuses) or the escape zone, which the cross-bank bridge
  risers saturate at their 1000 nm pitch. The banks' strips therefore
  carry no riser at all: they reach the analog ring on Metal1
  (`_strap_guard_rings`' bars), and the ring reaches the labelled `vss`
  trunk on a Metal2 strap (`geo.stitch_metal2`) — the same
  Metal2-crosses-everything property the comparator's supply straps have
  used since #378. Every cell this library LVSes stand-alone keeps the
  in-cell riser.
- **Lowering the strips' height or reach below the 20 µm rule** —
  forbidden (CLAUDE.md): DF.14 is a real latch-up rule, not a deck
  artifact; the fix is to draw what the process needs.
- **Folding the lattice into #836** — not chosen, and not that record's to
  choose: #836's ratified acceptance criteria pinned the tap counts this
  record amends, so the lattice needed its own record and its own measured
  cost.

## Consequences

- `layout/erc/well-tap-audit.json` now commits `substrate_tie_candidates: 7`
  (the two guard rings, of which the analog one has absorbed decode
  bank P's strip Comp where they overlap, plus the five strip Comp
  polygons of decode bank N, the top-plate switch and both comparator
  variants' two-segment strips) and `substrate_tie_comp_area_um2:
  3290.042`; `well_tap_candidates` stays **25** — one per Nwell island,
  the claim DR-0035 made — because the extra well taps live in
  `adc_tgate_dum`, a stand-alone deliverable the block-level audit does
  not traverse. `sim/tests/test_well_tap_audit.py` pins the new counts in
  the same direction-reversing mechanism it has used since DR-0032, and
  asserts the amendment chain (DR-0047 → amended by this record) beside
  the supersession chain it already guards.
- All nine regenerated GDS measure **zero** `comp.tap_distance.*` markers
  under 0.8.0, and the pinned 0.6.0 flow stays `clean` (the 46-rule deck
  still names neither tap-distance rule nor anything the strips touch
  newly). LVS matches on all nine with zero mismatches — the strips
  extract as part of the `vss` island exactly as the guard rings do, and
  the extra well taps as part of their islands' `vdd`, so device and net
  counts are unchanged. #652's 0.8.0 re-baseline loses its tap-distance
  blocker.
- Every placed row with NMOS columns now draws `Pplus` diffusion that is
  a real, contacted, routed tie — the lattice is geometry the ERC supply
  spec could narrow on (`ties[]`), not a DRC countermeasure. The
  `tie-wrong-implant` control still counts its pinned 25 `erc.missing_tie`
  findings: the strips are `Pplus`, so the `Nplus`-narrowed control's
  population is unchanged.
- The next layout move that shifts `adc_block.gds` re-takes the same
  evidence set (DRC/LVS/ERC/power/PEX/economy/signoff); #851's resistor
  columns land on top of this stream and re-take it once, on the final
  layout.

## Spec lines affected

- None — this is a layout-geometry and evidence-scope decision. It changes
  no target parameter or row in `spec/`; the area figure is recorded
  against DR-0024's existing bound (81.77 %,
  `layout/adc-top/economy/records/20261117-203922-0986aeb.md`) and
  re-opens nothing.
