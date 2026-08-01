# DR-0011: CDAC switching scheme — MCS / Vcm-based, differential, top-plate sampling

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
- **Bit-trial switching — one side per trial single-ended, both sides
  differential.** At each of the 9 remaining trials the decided weight-`w`
  block's bottom plate takes a `V_REF/2` step (`V_cm -> V_REF` for a "1"
  decision, `V_cm -> GND` for a "0"), which moves *that side's* top plate by
  `(V_REF/2)·(w/512)`. **How many sides move per trial is mode-dependent,
  and has to be**, because the two modes have different full-scales and
  therefore different LSBs:

  | Mode | Sides switched per trial | Differential step at weight `w` | Step at `w = 1` | Total correction range (`Σw = 511`) | Post-MSB residue to cover |
  |---|---|---|---|---|---|
  | Single-ended (pseudo-differential) | **one** — only the side that sampled `V_in`; the `V_cm`-pinned side's bottom plates stay at `V_cm` for the whole conversion | `(V_REF/2)·(w/512) = V_REF·w/1024` | `V_REF/1024` = **3.2227 mV** = `LSB_se` | `V_REF·511/1024` = 1.647 V | ±`V_REF/2` = ±1.65 V |
  | Differential | **both** — the decided block steps `V_cm -> V_REF` on one side while its mirror block steps `V_cm -> GND` on the other | `2·(V_REF/2)·(w/512) = V_REF·w/512` | `V_REF/512` = **6.4453 mV** = `LSB_diff` | `V_REF·511/512` = 3.294 V | ±`V_REF` = ±3.3 V |

  In both rows the weight-1 trial resolves exactly **one LSB of that mode's
  own full-scale**, which is precisely the condition for the array to
  resolve all 10 bits, and the correction range just covers that mode's
  post-MSB residue. Getting this wrong in either direction breaks the
  converter: switching *both* sides in single-ended mode would double every
  step and resolve only 9 bits across the 3.3 V span, while switching *one*
  side in differential mode would halve every step and leave the array
  unable to correct the top half of its residue. The switching sequence is
  therefore a **per-mode property of the control logic (#11), not a free
  choice** — see Consequences.
- **Comparator common mode**: in **differential** mode every trial is
  charge-*balanced* across the two sides by construction, so the
  comparator's input common mode is **constant at `V_cm` for the entire
  conversion** (`spec/prior-art-survey.md` §2.3) — zero comparator-offset
  code-correlation, the property that drives this choice. In
  **single-ended** mode only one side moves, so the common mode is
  `V_cm + residue/2`: it starts up to `|V_in − V_cm|/2 ≤ 0.825 V` off `V_cm`
  (set by the *sampled input*, before any switching happens) and halves
  along with the residue at every trial, so the excursion is smallest
  exactly where the decision is hardest — the late, small-residue trials.
  That term is inherent to mapping a single-ended input onto a
  pseudo-differential array and is present for **every** scheme on §2.6's
  shortlist including the conventional fallback; unlike monotonic
  switching's fixed `V_REF/2` droop it does not persist into the final
  trials. It does not change the comparison below, which is about
  *switching-induced* common-mode movement.
- **Reference levels**: three rails — `V_REF`, `V_cm`, `GND` — vs. two for
  the conventional/split-capacitor fallback. `V_cm` needs its own drive and
  decoupling; see Consequences.
- **Both single-ended (pseudo-differential, one side driven, the other
  pinned to `V_cm`) and true-differential (both sides driven ±`V_REF` about
  `V_cm`) input modes use this same array, the same unit cap, and the same
  per-side `V_REF/2` bottom-plate step**, per `spec/cdac-sizing-memo.md`
  §0/§3. What differs between the modes is the effective full-scale
  (`V_REF` vs. `2·V_REF`), the LSB that follows from it, and — as the table
  above shows — **how many sides switch per trial**. The array is neither
  re-sized nor re-wired between modes; only #11's switching sequence
  changes.

### Why this dominates the shortlist (traced to #3's inputs)

| Input (from `spec/prior-art-survey.md` §2) | MCS / Vcm | Conventional (fallback) | Monotonic |
|---|---|---|---|
| Switching-induced comparator CM excursion | **0** (constant) | 0 (constant, differential) | `V_REF/2` = 1.65 V droop — code-correlated offset, INL/DNL risk `spec/prior-art-survey.md` §2.3 |
| Switching energy (`C_u·V_REF²`, N=10) | **170.2** | 1363.3 (8×) | 255.5 |
| Array capacitance per side | **`2^(N-1)·C_u`** | `2^N·C_u` (2×) | `2^(N-1)·C_u` |
| Extra rails needed | `V_cm` (one more than conventional) | none | `V_cm` not required, but PMOS input pair forced |

The CM row compares **switching-induced** common-mode movement in
differential mode. The single-ended `residue/2` term described in the
Decision is a property of the pseudo-differential input mapping, not of the
switching scheme, so it adds the same amount to every column and does not
affect the ranking; monotonic's 1.65 V droop is on top of it, and unlike it
does not decay with the residue.

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
  MSB, not the plain-binary `2^N` formula (see sizing memo §3). **The
  mode-dependent switching sequence above changes none of those numbers**:
  the sampling event is identical in both modes (memo §1.1), the matching
  propagation is in units of the array's own LSB and both the step and the
  LSB scale together between modes (memo §3.2), and the per-trial settling
  network is one side's charge divider in either mode (memo §5.3). Only the
  control sequence differs.
- **A third rail, `V_cm = V_REF/2`, is required** with its own drive and
  decoupling — a real pinout/area cost `spec/prior-art-survey.md` §2.4
  flags explicitly (the sky130 12-bit reference's on-chip `V_cm` generator
  is ~30 % of that design's area). Not sized here; `V_cm` generation is a
  new, currently-unbudgeted deliverable for a future issue, or `V_cm` may be
  supplied off-chip like `V_REF` (DR-0002) — that scope decision is not
  made by this record and should be raised as a follow-up issue if it is not
  already covered by #7's remaining scope.
- **#9 (comparator)** designs against a **constant** `V_cm` input common
  mode **in differential mode** — the offset requirement is loose (row 0,
  "none + digital offset removal" in `spec/prior-art-survey.md` §3.4 applies
  by default), not the CM-tracking problem monotonic switching would have
  forced. **In single-ended mode it must also tolerate the `residue/2`
  common-mode term** from the Decision: up to `±0.825 V` off `V_cm` at the
  first (free-MSB) decision, halving every trial thereafter, so the
  requirement is "offset may drift with CM over ±0.825 V early, but must be
  stable over the final few tens of millivolts of CM" — a weaker
  requirement than monotonic's, which holds the full 1.65 V droop through
  the *last* trial, but not the flat-CM assumption differential mode gives.
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
  `design/cdac/cdac_array.sch`'s `rel_*` / `sel_hi_*` / `sel_lo_*` control
  pins) — not designed here, exposed as schematic ports for #11 to drive.
  **The sequence is mode-dependent** (see the table in Decision), and this
  is the control-port semantics #11 inherits:
  - *Differential*: at trial `k`, the weight-`w` cells on **both** sides
    release from `V_cm` together and engage to opposite rails —
    `sel_hi_*_<w>p` + `sel_lo_*_<w>n`, or the complement, according to the
    decision.
  - *Single-ended*: at trial `k`, **only the input side's** weight-`w` cell
    releases and engages. Every cell on the `V_cm`-pinned reference side
    stays released to `V_cm` (`rel` asserted, both `sel_hi`/`sel_lo` off)
    for the whole conversion. Driving the reference side as well would
    double every step and cost a bit of resolution.
  - Consequently `rel` must be driven **per weight** (each cell releases at
    its own trial and stays engaged afterwards) and, in single-ended mode,
    **per side**. The representative schematic draws `rel_n`/`rel_p` as one
    shared net across the cells it elaborates — a drawing economy for a
    two-cell excerpt, not the control granularity the real array needs;
    #11 owns that decode.
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
  positions per side, third rail `V_cm = V_REF/2` required, bit-trial
  switching sequence mode-dependent (single-ended switches one side per
  trial, differential switches both — see Decision).
