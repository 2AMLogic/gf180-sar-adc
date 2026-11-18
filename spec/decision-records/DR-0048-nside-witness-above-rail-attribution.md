# DR-0048: The `nside_cells_df` raw-voltage sum's above-rail term is a load-model-amplified coupling transient, not a decode hazard — attribution and bound-scope derivation for the `ss_-40c` FAIL

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-11-18
- **Decided by**: Builder agent, issue #910
- **Supersedes**: none — this record derives the attribution of one
  term inside an existing check; no bound moves and no instrument
  changes by this record.
- **Superseded by**: (none while this record stands)
- **Related**: #910 (this record's own issue, and the investigation
  whose measurements it cites:
  `sim/sar-logic-functional-gates/investigations/20261118-issue-910-above-rail-ringing.md`),
  #844 (the characterisation parent whose §4b first measured the
  excursion),
  [DR-0046](DR-0046-one-hot-checks-power-up-window.md) (the measurement
  window this record operates in),
  [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md) (the
  steady-state decode-hazard budget whose family this check belongs to),
  #854 (the netlist fix family whose hold-race evidence the same
  investigation contributes)

## Context

`nside_cells_df` (bound 8.9–9.1, unchanged through DR-0027 and DR-0046)
scores `ss_-40c_3.30v` at **9.16096** — the deck's only steady-state
one-hot-family FAIL. #844 §4b measured the excess precisely: the
boolean one-hot pattern is intact; the violation is three *rising*
`sel_hi_n_<w>n` driver outputs sitting **above the 3.300 V rail**
(3.542 / 3.419 / 3.332 V) at a trial-boundary instant, whose
out-of-range fractions (0.242 + 0.119 + 0.032 V) push the raw-voltage
sum from its 9.000 one-hot baseline to 9.161.

Issue #910's investigation re-took the traces on the current main
netlist (reproducing #844's numbers exactly) and root-caused the
above-rail term:

- **Mechanism**: real gate-drain overlap-capacitance coupling from the
  driver's own input edge onto its output node — measured to survive
  `trtol=1` and `method=gear` (not solver ringing), and to shrink 3–4×
  when the real extracted CDAC T-gate load
  (`layout/adc-top/parasitics/reports/20261117-165510-3a3d361/adc_tgate.para.spice`,
  the same extracted cell the committed extracted benches instantiate)
  is hung on all 27 CDAC-array control legs the way the real bit cells
  load them (worst leg 3.4855 → 3.3516 V; `nside` peak 9.1597 →
  **9.0463**, inside the bound; over the full 64.5 µs run the loaded
  whole-run maximum is **9.06642 at 63.00066 µs** against the unloaded
  deck's 9.16096 at the same instant).
- **Why the deck sees it at 4× the real magnitude**: the deck's select
  legs drive *nothing physical* — `bdftopn`/`bdfnside`/`bdfconf` read
  them inside B-source expressions, which sense voltage with infinite
  impedance — so the witness node carries only the driver transistors'
  own parasitics. A real bit cell presents ~30–60 fF of T-gate gate
  capacitance per leg; the deck's witness presents a few fF.
- **The same term at nominal already passes**: `tt_27c` steady-state
  reads 9.04957, `ss_125c` 9.09143, `sf_125c` 9.03607 — all inside
  8.9–9.1, all carrying this coupling's mild above-rail contribution.
  The `ss_-40c` violation is the same mechanism at cold amplitude into
  a zero-load witness, not a new decode failure: the investigation's
  legal-trajectory run shows the one-hot boolean pattern intact at
  every instant, and its one wrong conversion (conversion 3's +15) is
  fully attributed to a trial-flop hold race (§4 of the investigation),
  which `err_*` already scores — `nside_cells_df`'s bound plays no part
  in catching it.

So the check currently mixes two quantities in one raw-voltage sum: the
**decode-hazard witness** it was derived for (DR-0027's one-hot gap
budget: exactly one leg per weight above threshold, no make-before-break
overlap) and a **driver-coupling overshoot term** whose magnitude is an
artifact of the deck's deliberately behavioural load model.

## Decision

This record proposes, for ratification, the following attribution and
derived disposition — **it does not itself move any bound**:

1. **Attribution (derived, measurement-backed)**: the above-rail term in
   `nside_cells_df`'s raw sum at `ss_-40c` is a load-model-amplified
   capacitive coupling transient (investigation §2), not a decode
   hazard. Evidence: one-hot intact at every instant; 3–4× shrink into
   the real extracted T-gate load (9.1597 → 9.0463, inside the bound);
   insensitivity to `trtol`/`method`.
2. **The point's disposition stays FAIL until a netlist-level fix
   lands**: `ss_-40c` also fails `err_se_max`/`err_df_max` (= 15) via
   the trial-flop hold race the same investigation identified
   (investigation §4). The corner is genuinely defective at this
   netlist; relaxing the one-hot bound would not and must not clear it.
   When the #854-family netlist fix lands, the whole corner re-scores
   on the fixed netlist under the bounds then in force.
3. **Bound scope, going forward**: `nside_cells_df`'s 8.9–9.1 remains
   what DR-0027 ratified it as — the steady-state decode-hazard budget
   around the 9.000 one-hot baseline — with the *stated* understanding
   (this record) that on THIS deck the raw sum also carries a
   driver-coupling term of up to +0.05 at nominal temperatures
   (measured 9.036–9.091 across the committed 27 °C/125 °C records) and
   up to +0.161 at `ss_-40c` into the zero-load witness. Whether a
   future instrument separates the two terms (e.g. a boolean-threshold
   one-hot count beside the raw sum, or a realistic-load deck variant)
   is left as a follow-up instrument change with its own record; this
   record derives the attribution so such a change starts from evidence
   instead of a bound edit.

## Alternatives considered

- **Move the bound to admit 9.161** (e.g. to 8.9–9.2). Rejected: that
  is relaxing a ratified bound to pass a result (CLAUDE.md), and it
  would bury the only currently-failing witness of a corner that
  *genuinely fails* `err_*` for an unrelated, real reason.
- **Re-derive the bound around the deck's cold behaviour** (i.e.
  widen to the measured cold envelope). Rejected for the same reason,
  and because the cold envelope is set by the zero-load witness's
  coupling amplification — a deck-model quantity, not a design margin.
- **Change the deck's load model now** (add the T-gate loads to the
  committed testbench). Rejected for this issue: it changes the deck's
  netlist sha256 and re-baselines every record taken under the current
  instrument (the DR-0031/DR-0046 precedent makes that an
  instrument-correction decision with its own evidence pass, not a
  side effect of an investigation). The E1 probe decks in the
  investigation are the measured evidence that such an instrument
  change would land inside the current bound; the change itself belongs
  to a dedicated instrument decision if wanted.
- **Do nothing (no record)**. Rejected: the FAIL row currently reads as
  a decode failure it is not; leaving the attribution undocumented
  invites the next reader to "fix" it by moving the bound.

## Consequences

- `ss_-40c_3.30v` keeps its recorded FAIL on `nside_cells_df` (and on
  `err_*`); no committed number, bound, instrument or netlist changes
  under this record.
- A reader of the `ss_-40c` row now has a derivation-backed attribution
  to consult before touching the bound.
- The zero-load witness's coupling amplification is documented as a
  deck-model property (~4× vs the real T-gate load; real-load value
  9.0463, inside the bound), so future cold-corner excursions of this
  family can be compared against the mechanism instead of the bound.
- If ratified, the proposed instrument follow-up (separate the boolean
  one-hot count from the raw sum) can be scoped against DR-0046's
  window conventions; if rejected, the bound stays exactly as DR-0027
  left it and the FAIL row keeps its current meaning.

## Spec lines affected

None. No bound, check, corner, or instrument definition changes under
this record. (This record's Decision proposes wording *alongside*
`nside_cells_df`'s existing description if ratified; the check itself
is untouched until a superseding record says otherwise.)
