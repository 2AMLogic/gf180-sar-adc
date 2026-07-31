# DR-0006: CDAC switching scheme — MCS / Vcm-based, differential, top-plate sampling

- **Status**: proposed — requires operator sign-off (spec ratification authority sits with engineering per #1)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #8
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #3, #8, #9, #11, #12, DR-0002, `spec/prior-art-survey.md` §2, `spec/cdac-sizing-memo.md`, `sim/` record `20260731-231537-1ee5578` (`sim/cdac-bit-settling/`), `design/cdac/cdac_array.sch`

## Context

`spec/prior-art-survey.md` §2 (issue #3) surveyed CDAC switching schemes
against three inputs — switching energy, comparator common-mode excursion,
and total array capacitance vs. reference-drive burden — and produced a
ranked shortlist (§2.6), but §3's own curation explicitly scoped writing the
decision record *out* of that survey's deliverable ("stops short of writing
the architecture decision records"). No other issue claims it. This record
closes that gap: it is #8's first deliverable, consuming #3's shortlist as
input, so that the sizing memo and the settling testbenches that follow have
a fixed topology to size against rather than defaulting silently to
whatever is easiest.

## Decision

**Merged-Capacitor Switching (MCS) / Vcm-based switching, differential,
top-plate sampling** — shortlist item 1 in `spec/prior-art-survey.md` §2.6.

- **Sampling**: top-plate. The input is sampled directly onto each side's
  top-plate node through its own sampling switch while every bottom plate is
  held at `V_cm = V_REF/2` (DR-0002: 1.65 V). This resolves the MSB (bit 1)
  with **no array switching at all** — the comparator's first decision is
  the sign of the sampled differential voltage — which is the source of
  MCS's ~50 % array-size reduction relative to conventional charge
  redistribution (`spec/prior-art-survey.md` §2.4).
- **Array size per side**: `2^(N-1) = 512` unit-capacitor positions
  (`N = 10`): 511 binary-weighted positions (weights `2^8 .. 2^0`, i.e.
  256..1) resolving bits 2..10, plus one terminating unit (weight 1, fixed
  to `V_cm`, never switched) padding the array to the full `2^(N-1)`
  capacitance the switching-energy and settling figures below assume.
- **Bit-trial switching**: at each of the 9 remaining trials, the decided
  block on one side steps `V_cm -> V_REF` while the mirror block on the
  other side steps `V_cm -> GND` (or vice versa), each a `V_REF/2` step.
  Every trial is charge-*balanced* across the two sides by construction, so
  the comparator's input common mode is **constant at `V_cm` for the entire
  conversion** (`spec/prior-art-survey.md` §2.3) — zero comparator-offset
  code-correlation, the property that drives this choice.
- **Reference levels**: three rails — `V_REF`, `V_cm`, `GND` — vs. two for
  the conventional/split-capacitor fallback. `V_cm` needs its own drive and
  decoupling; see Consequences.
- **Both single-ended (pseudo-differential, one side driven, the other
  pinned to `V_cm`) and true-differential (both sides driven ±`V_REF` about
  `V_cm`) input modes use this same array**, per `spec/cdac-sizing-memo.md`
  §2 — only the effective full-scale differs (`V_REF` vs. `2·V_REF`), not
  the topology.

### Why this dominates the shortlist (traced to #3's inputs)

| Input (from `spec/prior-art-survey.md` §2) | MCS / Vcm | Conventional (fallback) | Monotonic |
|---|---|---|---|
| Comparator CM excursion | **0** (constant) | 0 (constant, differential) | `V_REF/2` = 1.65 V droop — code-correlated offset, INL/DNL risk `spec/prior-art-survey.md` §2.3 |
| Switching energy (`C_u·V_REF²`, N=10) | **170.2** | 1363.3 (8×) | 255.5 |
| Array capacitance per side | **`2^(N-1)·C_u`** | `2^N·C_u` (2×) | `2^(N-1)·C_u` |
| Extra rails needed | `V_cm` (one more than conventional) | none | `V_cm` not required, but PMOS input pair forced |

Monotonic is ruled out here on the same basis §2.6 item 3 gives: the
`V_REF/2` common-mode droop converts comparator offset into a
code-correlated error, which is an architectural risk to the `< 1 LSB`
(`< 0.5 LSB` stretch) INL/DNL target that MCS/Vcm removes entirely. The
`V_cm` rail MCS needs in exchange is a real, stated cost (see Consequences),
not a free win.

## Alternatives considered

- **Conventional differential, bottom-plate sampling** — not chosen, kept as
  the fallback `spec/prior-art-survey.md` §2.6 names it. Needs no `V_cm`
  rail (de-risks DR-0002/#7 further) and is simpler to verify, at the cost
  of 8× switching energy (still only ~7 % of the <1 mW budget, per the
  survey) and 2× array capacitance/area (still ~8 % of the 0.1 mm² budget).
  Both costs fit the spec on their own; MCS is chosen for the CM-excursion
  property, not because the fallback is infeasible. Revisit if the `V_cm`
  generator (see Consequences) turns out to cost more area than currently
  assumed.
- **Monotonic / set-and-down** — not chosen. Best energy/simplicity trade in
  1.0–1.2 V literature, but at 3.3 V the `V_REF/2` = 1.65 V comparator
  common-mode droop is larger than the NMOS/PMOS `V_th` measured in
  `sim/device-characterization-report.md` §3.2 by more than 2×, converting
  comparator offset into a linearity error. Reconsider only if #9 later
  shows a comparator whose offset is flat over a 1.65 V CM range, or if #1
  relaxes the INL/DNL target.
- **Split-capacitor** — not chosen. `spec/prior-art-survey.md` §2.2 flags its
  own energy figure as `[V]` (unconfirmed against the cited source) and it
  offers no CM-excursion advantage over the conventional fallback while
  adding switching complexity; no scenario in this repo currently favors it
  over the two above.
- **Tri-level / charge-recycling / bypass variants** — not chosen. Survey
  §2.1 notes these exist but does not shortlist them; no evidence in this
  repo argues for taking on their added switching complexity at this
  resolution/rate.
- **Segmented (thermometer + binary) array** — deferred, not rejected. Noted
  in `spec/prior-art-survey.md` §2.5 as a proven open-source technique
  (sky130 12-bit reference) but probably overkill at 10 bits; the array
  chosen here is uniform binary-within-MCS. Revisit only if #14's Monte
  Carlo shows binary-weighted matching insufficient at the chosen unit cap.

## Consequences

- **`spec/cdac-sizing-memo.md` sizes against this topology specifically**:
  `C_sample` is the per-side top-plate array capacitance (not the whole
  8-rail conventional array), and the matching-to-linearity propagation is
  re-derived for a `2^(N-1)`-element sub-array with a zero-mismatch free
  MSB, not the plain-binary `2^N` formula (see sizing memo §3).
- **A third rail, `V_cm = V_REF/2`, is required** with its own drive and
  decoupling — a real pinout/area cost `spec/prior-art-survey.md` §2.4
  flags explicitly (the sky130 12-bit reference's on-chip `V_cm` generator
  is ~30 % of that design's area). Not sized here; `V_cm` generation is a
  new, currently-unbudgeted deliverable for a future issue, or `V_cm` may be
  supplied off-chip like `V_REF` (DR-0002) — that scope decision is not
  made by this record and should be raised as a follow-up issue if it is not
  already covered by #7's remaining scope.
- **#9 (comparator)** designs against a **constant** `V_cm` input common
  mode — the offset requirement is loose (row 0, "none + digital offset
  removal" in `spec/prior-art-survey.md` §3.4 applies by default), not the
  CM-tracking problem monotonic switching would have forced.
- **#12 (timing budget)** inherits the total array capacitance and the
  worst-bit settling number from `spec/cdac-sizing-memo.md` §5 /
  `sim/cdac-bit-settling/`, and DR-0002's `Z_ref ≤ 240 Ω` / `C_dec ≥ 40 nF`
  reference-drive envelope is shown to hold with margin against this
  scheme's real per-step charge, not re-derived from scratch.
- **#14 (Monte Carlo)** must use the re-derived worst-case transition
  (sub-array MSB carry, not the whole-array MSB carry) from the sizing memo,
  not the plain-binary formula.
- **#11 (SAR logic)** must generate, per bit, the release-to-`V_cm` /
  engage-to-`V_REF`-or-`GND` switch timing this scheme needs (see
  `design/cdac/cdac_array.sch`'s `REL_*` / `SEL_HI_*` / `SEL_LO_*` control
  pins) — not designed here, exposed as schematic ports for #11 to drive.
- **`design/cdac/cdac_array.sch` is a representative schematic**, not the
  full 512-position array: it elaborates the two structurally-relevant
  positions (weight 256, the sub-array's own MSB and the worst settling
  case per `sim/cdac-bit-settling/`; weight 1, the LSB) plus each side's
  terminating dummy and sampling switch, and states in-schematic that the
  seven omitted weighted positions are identical copies scaled by the cap's
  `m=` multiplicity parameter. A future layout-facing issue (#15/#16) must
  either elaborate the full array or generate it programmatically; this
  record does not claim the schematic is layout-complete.

## Spec lines affected

- `README.md#target-specification` (pending #1) — CDAC switching scheme —
  new: no explicit row exists in the current DRAFT table; this adds one —
  MCS / Vcm-based, differential, top-plate sampling, `2^(N-1)` unit
  positions per side, third rail `V_cm = V_REF/2` required.
