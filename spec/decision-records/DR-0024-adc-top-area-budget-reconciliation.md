# DR-0024: Reconcile the adc-top area budget — ratify `< 0.16 mm²`, superseding DR-0017's stale proposal

- **Status**: proposed
- **Date**: 2026-08-21
- **Decided by**: Builder agent, issue #198 — ratification-via-PR per
  `2AMLogic/2am#357` Class 1 standing policy: this record is proposed on its
  merits with sources shown, and the operator's PR approval is the
  ratification act (no separate sign-off comment).
- **Supersedes**: DR-0017 (its `< 0.13 mm²` proposal, itself never ratified,
  is stale — it predates issue #118's comparator growth and the DR-0019
  unit-cap resize). DR-0017's own `Status`/`Superseded by` back-pointer is
  edited **at ratification, not by this proposed record** (matching
  DR-0017's own precedent for a still-`proposed` superseding record, and
  DR-0023's precedent for citing it). DR-0017's file itself is left
  untouched by this record.
- **Superseded by**: (none while this record stands)
- **Related**: #198 (this decision), #215 (the area-recovery follow-up whose
  outcome this record's proposed number rests on), #208 (the `klt economy`
  evidence-gathering pass that scoped #215), #118 (the comparator growth that
  moved the block off DR-0017's `0.12100 mm²` figure), DR-0006 (the
  target-spec table this record's Area row revises), DR-0017 (superseded by
  this record), DR-0019 (the CDAC unit-cap resize whose area cost is the
  other half of the number this record ratifies), `layout/adc-top/README.md`,
  `layout/adc-top/area.json`, `layout/adc-top/economy/records/
  20260817-185745-40cfeb8.md` (the as-built figure this record cites),
  `spec/cdac-sizing-memo.md` §5.5 (the drive-contract bound addressed under
  Alternatives)

## Context

DR-0006's ratified target-spec table set `Area < 0.1 mm²`. That target has
been overrun by a sequence of independently-justified, previously-decided
changes, and the record of the overrun has itself gone stale twice:

1. **0.09619 mm²** (96 % of target) — the original design, in budget.
2. **0.12100 mm²** (121 %) — issue #70/#80 legalized the CDAC unit-capacitor
   MiM stack against `MIMTM.3`'s 0.6 µm enclosure rule, which the original
   3.914 µm pitch violated 4896 times. `spec/decision-records/DR-0017-
   adc-top-area-budget-overrun.md` proposed `< 0.13 mm²` against this figure
   (2026-08-04, status `proposed`) but was never ratified.
3. **0.15446 mm²** (154 %) — issue #118's comparator growth (fixing an
   `ADC_BLOCK`-level LVS convergence defect) added area DR-0017 never
   accounted for, making its `0.12100 mm²` figure stale on DR-0017's own
   terms before DR-0019 even existed.
4. **0.18045 mm²** (180 %) — DR-0019 (#177, merged as #193) resized the CDAC
   unit capacitor 2.7136 µm → 4.0 µm to close the ratified **Gain error,
   mismatch** row's 2.12σ gap (`sim/mc-cdac-mismatch/records/
   20260816-044942-56fbe50.md`), physically built in #196/PR #202. This is
   the figure issue #198's own title cites, and is the last point at which
   neither DR-0017's proposal nor the original DR-0006 target had been
   reconciled against either #118 or DR-0019.
5. **0.150536 mm² (150,536.239 µm²) — current, as-built.** Issue #208 ran
   `klt economy` against the #202/#196 layout and returned verdict
   **revise**: most of 0.18045 mm² is legitimately spent (CDAC arrays at
   0.802 utilization, DR-0019-driven; decode banks at 0.446, DRC-floor-driven
   per #67/#69; the DR-0010 SAR-logic reserve is a named, deliberate
   reservation, not waste), but it named one recoverable, coordinate-level
   dead corridor (~23,000 µm², right of the decode banks) plus a loose
   comparator-internal bbox. Issue #215 recovered both — a load-resistor
   fold (R2) plus a re-derivation of both top-level strap corridors off
   their actual routing need rather than a stale `top.bbox().right` (R1) —
   for a measured **−29,909.75 µm² (−16.57 %)**, landing at the current
   figure. `layout/adc-top/area.json`'s `block_total` (150536.239) and `klt
   economy`'s `bbox_area_um2` (`layout/adc-top/economy/records/
   20260817-185745-40cfeb8.md`) agree exactly; both are re-runnable, not
   asserted.

Two decision records now sit against this chain without ever having been
reconciled to the same number: DR-0006's original `< 0.1 mm²` (obsolete since
step 2) and DR-0017's proposed `< 0.13 mm²` (obsolete since step 3, and in
any case unratified). Neither has ever been checked against the design's
actual current geometry (step 5). This record is the single superseding
decision issue #198 exists to produce, using the current as-built figure —
not the stale `0.18045 mm²` issue #198's own title cites, which #215 has
since reduced by 16.57 %.

Per the operator's 2026-08-21 comment on issue #198, this reconciliation is
worked as ratification-via-PR (`2AMLogic/2am#357` Class 1, amended by
`2AMLogic/2am#372`): a builder drafts the record on the evidence, and the
operator's PR approval is the ratification act, not a separate sign-off
comment — the same routing DR-0023 already used for this repo's other
pending device-flavor question.

## Decision

**Revise the `Area` row of the DR-0006 target-spec table
(`README.md#target-specification`) from `< 0.1 mm²` to `< 0.16 mm²`, and
record the current drawn `adc_block` bounding box of 150,536.239 µm²
(0.150536 mm², 94.1 % of the new bound) as the value it bounds.** This
supersedes DR-0017's stale `< 0.13 mm²` proposal (itself now insufficient —
0.150536 mm² > 0.13 mm² — even setting aside that it was never ratified).

The `< 0.16 mm²` bound is the current as-built figure plus ~6.3 % headroom,
in the same spirit as DR-0017's own precedent (which recorded its `0.12100
mm²` measured value against a rounded `0.13 mm²` bound, ~7.4 % headroom) —
enough to absorb benign, non-substantive future deltas (a guard-ring rule
revision, a rounding change in a downstream `klt` release) without forcing a
fresh decision record for no real design change, but not so loose that it
stops meaning anything against the measured geometry. It is **not** padding
for the one known-but-unquantified future growth risk this design carries —
see Consequences.

The CDAC array geometry (DR-0019's ratified `C_u`), the decode banks'
`comp.space.1` DRC floor (#67/#69), and the DR-0008/DR-0010 analog/digital
isolation and SAR-logic reserve are **not** touched by this record, matching
DR-0017's own scope discipline: none of those are relaxed, shaved, or
silently redrawn to make an area row pass.

## Alternatives considered

- **Accept the stale `0.18045 mm²` figure from issue #198's own title** —
  not chosen. #215 has already landed and reduced the as-built figure by
  16.57 % since that number was current; ratifying a figure the design no
  longer draws would be wrong the moment this record merges, and would
  itself need an immediate superseding record.
- **Hold `< 0.1 mm²` and claw back area by revisiting DR-0019's sizing
  within `cdac-sizing-memo.md` §5.5's `3.840 µm ≤ s ≤ 4.1975 µm` window** —
  not chosen, on the numbers DR-0019 itself already published. Dropping from
  the chosen `s = 4.0 µm` to the window's exact-boundary floor (`s = 3.840
  µm`, `C_u = 33.00 fF`) saves only **1.8 %** of block area (0.18045 mm² →
  0.17721 mm², `layout/adc-top/area_feasibility.py`'s `unit_cap_sweep`
  section) while giving up essentially all of the resize's own margin: the
  exact-boundary sizing measured `sigma_to_spec = 3.009` against the ratified
  3σ gain-error condition (`sim/mc-cdac-mismatch/records/
  20260816-125421-737d16e.md`, "Rejected exact-boundary alternative") —
  "statistically indistinguishable from the `3.0` threshold this whole issue
  exists to move away from," DR-0019's own words. Compounding that 1.8 %
  saving with #215's 16.57 % corridor/comparator recovery (which does not
  depend on `C_u`, so it would apply either way) projects to roughly
  0.17721 × (1 − 0.1657) ≈ **0.1478 mm²** — still 48 % over the original
  `< 0.1 mm²` target — in exchange for reopening a verified-marginal
  mismatch finding DR-0019 closed with real margin for the first time. Not a
  defensible trade: it buys back essentially no area at real risk to a
  ratified spec row.
- **Set an intermediate target by interpolation** (e.g. splitting the
  difference between DR-0017's `0.13 mm²` and the current `0.150536 mm²`) —
  not chosen. Such a number corresponds to no measured geometry and no
  design decision; DR-0017's own convention — record the drawn bounding box
  as the value it bounds — is the more defensible pattern to follow, not an
  arbitrary midpoint between two numbers that were never commensurable (one
  predates #118 and DR-0019 entirely).
- **Ratify the current figure with zero headroom** (`< 0.150536 mm²` or
  `< 0.1506 mm²` exactly) — not chosen. DR-0017 itself did not do this (it
  rounded `0.12100 mm²` up to `0.13 mm²`) for the same reason this record
  doesn't: a target equal to the last measured value forces a fresh
  decision record on the next benign, non-substantive geometry delta (a
  `klt` version bump that changes a guard-ring corner by a few nm, for
  example), which is friction without a corresponding gain in the target's
  meaning.
- **Wait for a further area-recovery investigation beyond #215 before
  ratifying** — not chosen. #208's `klt economy` review already
  characterized the remaining geometry (CDAC arrays, decode banks, SAR-logic
  reserve) as legitimately spent against already-decided constraints, and
  #215's own closing evidence (`layout/adc-top/economy/records/
  20260817-185745-40cfeb8.md`) shows the residual right-side dead margin
  (149.76 µm) consistent with guard-ring and routing needs, not a further
  named recoverable finding. Re-opening that investigation without a new
  finding to justify it only delays a reconciliation issue #198 exists
  specifically to stop deferring.

## Consequences

- **`adc_block` is compliant with the revised target as currently drawn** —
  0.150536 mm² < 0.16 mm² — and the block stops being scored against two
  disconnected, stale targets (DR-0006's original and DR-0017's proposed
  figure) neither of which the current geometry was ever checked against.
- **The die is ~50 % larger than the original DR-0006 planning budget.**
  That is a real, compounding cost across two independent, already-decided
  causes (#118's comparator fix, DR-0019's mismatch-margin resize) — this
  record does not create that cost, it records it against a single current
  number instead of leaving it split across a stale ratified target and a
  stale unratified proposal.
- **This record does not budget for the one known, unquantified future
  growth risk this design carries.** DR-0023 (digital-interface device
  flavor, ratified separately) flags that the DR-0010 SAR-logic reserved
  footprint — already included in the current 150,536.239 µm² figure as a
  named reservation, not yet a placed-and-routed netlist — "may need
  re-checking against the actual 6 V-oxide cell area once synthesis/P&R
  produces real numbers," a follow-on issue DR-0023 itself defers. This
  record's `< 0.16 mm²` headroom is sized for benign geometry churn, not for
  that risk, which is unquantified today. If synthesis/P&R work grows
  `adc_block` past `< 0.16 mm²`, a further superseding record is required at
  that time — this record does not pre-authorize it, per DR-0006/CLAUDE.md's
  "agents do not relax the ratified spec to make results pass."
- **No verification result changes.** `design/`, `sim/`, DRC and LVS are
  untouched by this record — the drawn geometry it cites is exactly what
  #215's own DRC-clean, LVS-matched close (`klt lvs` 1,349 devices / 198
  nets / 71 pins, `layout/lvs/records/20260817-185722-40cfeb8.md`) already
  established. This record moves an area *target*, not any measured or
  simulated quantity.
- **DR-0006's other rows are untouched.** This revises one row of its
  table, using DR-0006's own stated mechanism ("a change to it requires a
  new decision record superseding this one").
- **README.md and `layout/adc-top/README.md`'s remaining citations of the
  now-superseded `< 0.1 mm²` / `< 0.13 mm²` / `0.12100 mm²` figures are
  updated to point at this record** where they describe the target rather
  than a specific historical measurement (the historical figures themselves,
  e.g. DR-0017's `0.12100 mm²` step in the provenance chain above, are left
  as history, not scrubbed).

## Spec lines affected

- `README.md#target-specification` — `Area` row — changed (`< 0.1 mm²` →
  `< 0.16 mm²`, bounding the drawn `adc_block` at 150,536.239 µm² /
  0.150536 mm²). **Applied on ratification, not by this proposed record** —
  the ratified row and DR-0006's `Superseded by` back-pointer are edited by
  the operator's ratification act (PR approval), per DR-0006, DR-0017's own
  precedent, and `CLAUDE.md`.
- `spec/decision-records/DR-0017-adc-top-area-budget-overrun.md` — `Status`
  / `Superseded by` — changed (`proposed` → `superseded-by DR-0024` / `(none
  while this record stands)` → `DR-0024`). **Applied on ratification, not by
  this proposed record**, matching DR-0017's own stated mechanism for how it
  expects to be superseded.
