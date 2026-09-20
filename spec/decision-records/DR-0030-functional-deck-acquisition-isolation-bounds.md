# DR-0030: Bind the acquisition/isolation limits to the rung of the DUT, not to the deck that measures it

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-09-19
- **Decided by**: Builder agent, issue #324
- **Supersedes**: none. This record does **not** supersede
  [DR-0028](DR-0028-gate-level-acquisition-isolation-bounds.md) — it discharges
  the standing debt DR-0028's Consequences names, on the two manifests
  DR-0028's own "Spec lines affected" deliberately left out of scope.
- **Superseded by**: (none while this record stands)
- **Related**: #324 (this record's own issue), #319 /
  [DR-0028](DR-0028-gate-level-acquisition-isolation-bounds.md) (the
  derivation this record applies, unchanged, to a second pair of manifests),
  [DR-0003](DR-0003-clocking.md) (`M = 16`, the 62.5 ns clock phase and the
  4-clock sample phase every limit below is expressed in),
  [DR-0013](DR-0013-input-pin-charge-split.md) (the drive contract the
  acquisition floor is derived from),
  [DR-0014](DR-0014-bottom-plate-sampling.md) (the two-phase sample these
  three measurements exist to check; **not** superseded, **not** weakened),
  [DR-0023](DR-0023-digital-interface-device-flavor.md) (the synthesis flow
  that produced the netlist re-read below),
  [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md) (the same
  standard-cell P/N-skew mechanism, root-caused there),
  #273/#289 (the runs that produced this deck's grids), #274/#275 (P&R / STA
  — the post-layout re-check these limits are written to survive),
  #334 (the cross-loop isolation-skew check this record's `iso_gap_df_ns`
  consequence routes there),
  `sim/sar-logic-functional-gates/records/20260917-044312-c7ff0ff.md` and
  `sim/sar-logic-functional-gates/records/20260915-214338-912a8ec.md` (the
  two scored grids re-read here — both left untouched),
  `sim/sar-logic-functional/records/20260802-110241-131989b.md` (the rung-1
  measurement that keeps the ideal deck's own bound),
  `sim/sar-logic-timing-gates-ok/records/20260918-233547-1d81aa1.md`
  (DR-0028's 45-point grid, which still owns the governing slack)

## Context

[DR-0028](DR-0028-gate-level-acquisition-isolation-bounds.md) re-derived
`acq_window_ns` and `iso_gap_ns` from the margin each protects and applied the
result to the two gate-level **timing** manifests only. It said so, and said
why the rest was left: harmonising the *functional* pair would re-interpret
five committed records and touch a fourth measurement it had no evidence for
(`iso_gap_df_ns`, the differential loop). Its Consequences filed that as a
tracked debt. This record is that debt, paid.

Two things are wrong on `main` as a result, and they are the same thing seen
from two sides:

1. **`sim/sar-logic-functional-gates/` fails these checks for exactly the
   reason DR-0028 adjudicates.** Its scored grids measure the same synthesized
   `sar_ctrl_a` netlist, through the same measurement expressions, and land
   outside 185 … 190 / 60 … 65 at the P/N skew corners —
   `20260917-044312-c7ff0ff` reads 179.743 ns / 70.3956 ns at `fs_27c_3.30v`
   and 192.972 ns / 57.3198 ns at `sf_27c_3.30v`. DR-0028's Alternatives
   section already cites those exact rows as its reason for *rejecting* the
   185 … 190 / 60 … 65 pair.
2. **The coarse deck is held tighter than the tight deck.** The functional
   decks run at a 20 ns maximum timestep and their own descriptions say, in
   capitals, that the tight bound on this quantity is not theirs. After
   DR-0028 they nonetheless carry a ±2.5 ns window where the 5 ns-timestep
   deck that owns the tight claim carries ±21.9 ns.

The question #324 asks is which limits the two functional manifests should
carry. It is not a question about the design: nothing below re-runs, re-scores
or re-measures anything, and no measurement expression changes.

## Decision

**The limits on these three measurements are a property of the DUT being
measured, not of the deck measuring it.** A deck whose DUT is the synthesized
netlist carries DR-0028's margin bounds, because it is measuring a physical
margin with a real PVT spread. A deck whose DUT is the rung-1 ideal XSPICE
model carries a regression guard on that generator, sized to the measuring
deck's own resolution, because there is no physical margin in it to bound.

| manifest | rung / DUT | `acq_window_ns` | `iso_gap_ns` | `iso_gap_df_ns` |
|---|---|---|---|---|
| `sim/sar-logic-functional-gates/` | rung 2 — synthesized gf180mcu standard-cell netlist, full PVT axis | 185 … 190 → **175.0 … 218.7** | 60 … 65 → **31.3 … 75.0** | 60 … 65 → **31.3 … 75.0** |
| `sim/sar-logic-functional/` | rung 1 — ideal XSPICE model, no process axis | **185 … 190, unchanged** | **60 … 65, unchanged** | **60 … 65, unchanged** |

The gate-level numbers are DR-0028's, adopted digit-for-digit and with its
derivation — settling floor `30 ns × ln(83.06/0.25) = 174.17 ns` rounded up to
175.0; ceiling `250 − 31.25 = 218.75 ns` rounded down to 218.7; ordering floor
`62.5/2 = 31.25 ns` rounded up to 31.3; ceiling `250 − 175.0 = 75.0 ns`. They
are **layout-independent** for DR-0028's reason: every input is a spec quantity
P&R does not change. Nothing is re-derived here, because nothing needs to be:
it is the same DUT, the same expression and the same physical requirement.

This makes the divergence axis the **rung**, not the deck. Both rung-2
decks now read 175.0 … 218.7 / 31.3 … 75.0; both rung-1 decks keep their own
generator guards (`sim/sar-logic-timing/` at 187.3 … 188.0 / 62.2 … 62.8 per
DR-0028's Consequences, `sim/sar-logic-functional/` at 185 … 190 / 60 … 65 per
this record). The inversion #324 was filed on is removed.

### `iso_gap_df_ns` takes the same limits, by derivation and not by evidence

DR-0028 was right that it has no gate-level *timing* evidence for the
differential loop: `iso_gap_df_ns` is measured only by the functional decks.
It needs none. DR-0028's isolation derivation contains no term that
distinguishes the loops — it is DR-0003's 62.5 ns clock phase, the
sub-nanosecond requirement that the top-plate switch be fully off before the
bottom plates move, and the 250 ns sample phase. DR-0014's fourth leg is
deliberately **not** mode-gated, so the differential loop acquires through the
same two controls, in the same phase, against the same requirement. The floor
and the ceiling therefore transfer verbatim.

The committed evidence is used only to confirm the transfer is not hiding a
surprise, never to set the limit: across every scored point in
`20260915-214338-912a8ec`, `20260916-043850-e5440a0` and
`20260917-044312-c7ff0ff`, `iso_gap_df_ns` tracks `iso_gap_ns` to
**≤ 0.0004 ns** — four orders of magnitude below either limit's distance from
nominal.

### Why the rung-1 ideal deck keeps 185 … 190 / 60 … 65

DR-0028 kept `sim/sar-logic-timing/` tight because its DUT is a fixed-delay
model that *cannot* move with process, so a tight window is a correct and
useful guard on the generator's output. The same argument holds for
`sim/sar-logic-functional/`, at that deck's own resolution — and the width is
not arbitrary:

- **The value is deterministic.** `20260802-110241-131989b` measures
  187.522 ns / 62.2135 ns / 62.2135 ns, with a spread of 1.6e-4 % and 6.6e-4 %
  (≈ 0.0003 ns and 0.0004 ns) across the supply axis, which is the only axis
  that can move anything in this deck.
- **It cannot carry the tight deck's window, and that is measured, not
  assumed.** `sim/sar-logic-timing/` measures 187.625 ns / 62.4888 ns on the
  *same* ideal DUT — a composition offset of 0.103 ns and 0.275 ns. Its
  62.2 … 62.8 window would leave this deck 0.0135 ns inside its own floor.
  The ±2.5 ns width is what accommodates a real, known composition difference
  between two decks measuring one deterministic model.
- **It still does the job it claims.** Against a composition offset of
  0.275 ns it holds ~9× headroom, and it fails a dropped or added clock phase
  (62.5 ns) by 60 ns — which is precisely the "did the sequencer drop or add
  a whole clock" guard its own description says it is.

Widening it to 175.0 … 218.7 would discard that working guard and buy nothing:
no point of this deck can approach either new limit, because no axis in it
moves the number by more than 0.0004 ns.

## Alternatives considered

- **Both decks adopt DR-0028's limits** (#324's second named shape). Not
  chosen: it drops a real, working regression guard on a deterministic
  generator in exchange for uniformity of appearance. DR-0028 already decided
  this question for the rung-1 *timing* deck on exactly this reasoning; making
  the opposite call for the rung-1 *functional* deck would leave the two
  rung-1 decks inconsistent to cure an inconsistency.
- **Give the functional decks their own third, coarser, derived numbers** —
  an explicit ±1-clock-phase "did the sequencer drop or add a whole clock"
  guard (#324's third named shape). Not chosen for the gate-level deck, and
  the reason is that DR-0028's limits **already are** that guard, and strictly
  better than a fresh one because they also carry a derivation: a dropped
  clock (125.0 ns) misses the 175.0 ns floor by 50 ns and an added one
  (250.0 ns) misses the 218.7 ns ceiling by 31.3 ns. Minting a second set of
  numbers for the same DUT, the same netlist and the same expression would
  put two different pass/fail answers on one measurement and would be exactly
  the "four unrelated numbers" DR-0028 argued against. (It *is* what the
  rung-1 deck keeps — but there it is not a third value, it is the value
  already in force.)
- **Keep 185 … 190 / 60 … 65 on the gate-level deck and treat it as failing.**
  Not chosen: refuted by committed measurement in DR-0028's own Alternatives
  section, on this deck's own records. It also preserves the inversion #324
  was filed on — a 20 ns-timestep deck holding a tighter bound than the 5 ns
  deck that owns the tight claim — which is not a defensible state to leave a
  verification suite in.
- **Drop `acq_window_ns` / `iso_gap_ns*` from the gate-level functional deck
  and leave them to the timing deck.** Not chosen. That second, independent
  composition agreeing with the timing deck to 0.083 ns is what ruled out a
  decomposition artifact in DR-0028's Context in the first place; deleting it
  would remove the only evidence that the timing deck's numbers are a property
  of the netlist rather than of its own composition. And `iso_gap_df_ns` is
  measured nowhere else at all.
- **Amend DR-0028 in place instead of writing this record.** Not chosen.
  DR-0028's "Spec lines affected" names exactly two manifests and its
  Consequences states the functional divergence as a standing debt *at its
  date*; rewriting it would make its own honest statement retroactively false
  and would silently enlarge what the operator is being asked to sign off.
  README.md's append-only rule points the same way. Exactly one edit is made
  to DR-0028 — a pointer from that debt bullet to this record — which is the
  navigability minimum, not a revision, and changes no value in it.

## Consequences

- **Re-read against these limits, `20260917-044312-c7ff0ff` becomes a 5-of-5
  PASS, and that must be stated plainly rather than buried.** Its only failing
  checks were `acq_window_ns` / `iso_gap_ns` / `iso_gap_df_ns` at
  `fs_27c_3.30v` and `sf_27c_3.30v`; every one of those values lies inside the
  new limits. This is the strongest objection to this record and it is
  answered on the evidence, not on convenience: the quantity that was failing
  is the inherited bound DR-0028 root-caused to standard-cell P/N rise/fall
  asymmetry, cross-confirmed between two independent compositions to 0.083 ns,
  and no independent defect is hiding behind it in this deck —
  `err_se_max/min` and `err_df_max/min` read exactly **0** at every scored
  point, `conv_period_ns` reads exactly 1000, and the one-hot hazard is
  separately bounded and separately recorded by DR-0027. **Nothing is re-run
  and nothing is re-scored**: the records keep their text, their FAIL verdicts
  and their stated reasons as written, per `sim/`'s append-only rule; the next
  run of this deck mints a new record under the new limits.
- **All five committed `sim/sar-logic-functional-gates/records/` entries meet
  these limits on these three checks.** The scored ones read 179.742 …
  192.972 ns and 57.3197 … 70.3956 ns, i.e. worst slack **4.74 ns** on the
  acquisition floor (`fs_27c_3.30v`) and **4.60 ns** on the isolation ceiling
  (`fs_27c_3.30v`). Two entries (`20260916-042153-e5440a0`,
  `20260916-042719-e5440a0`) scored no points at all and are unaffected;
  `20260915-214338-912a8ec` stays FAIL regardless, on the pre-DR-0027
  `sw_conflict` bounds it was scored against.
- **The governing slack does not improve, and this deck's grid does not
  establish it.** These grids are 5 points — the process axis at 27 °C /
  3.30 V — not the ratified 45. The binding number stays DR-0028's **1.93 ns**
  at `fs_125c_2.97v`, from the 45-point `sim/sar-logic-timing-gates-ok/` grid.
  When this deck next runs its full grid it should be expected to land near
  that, not near the 4.74 ns above; the point of these limits is that it will
  then be scored against a derivation instead of an inheritance.
- **`iso_gap_df_ns` loses detection of a *small* cross-loop asymmetry, and
  that is a real cost.** With both loops bounded independently at 31.3 … 75.0,
  the two numbers could part company by tens of nanoseconds with both still
  passing, where 60 … 65 would have tripped on ~5 ns. What is **not** lost is
  the failure the check exists for: gating `sel_in` by mode is a whole-clock
  event on the differential loop, driving `iso_gap_df_ns` to 0 or −62.5 ns,
  both of which the 31.3 ns floor still fails by 31.25 ns and 93.75 ns — the
  same margins DR-0028 relies on for the single-ended loop. Restoring the
  asymmetry guard properly needs the *difference* measured directly (it tracks
  to ≤ 0.0004 ns and would carry a genuinely tight bound), which is a new
  measurement expression and therefore outside #324's stated scope; filed as
  **#334** so it is tracked rather than forgotten.
- **The gate-level functional deck gives up the same detection power DR-0028
  gave up, for the same reason.** It can no longer see a ±10 ns shift in the
  sequencer's control-path timing. What still catches the consequences here:
  `err_se_*` / `err_df_*` (exactly 0 on every scored point — any timing shift
  that breaks a conversion shows there), `conv_period_ns` at 999.9 … 1000.1,
  and DR-0027's `sw_conflict_*` / `nside_cells_*` hazard budget, which sees
  decode-path skew directly.
- **A prose claim in the gate-level manifest becomes false and is corrected.**
  `sim/sar-logic-functional-gates/testbench/tb.json`'s evidence notes assert
  that `acq_window_ns` and `iso_gap_ns*` are "UNCHANGED from
  `sim/sar-logic-functional/testbench/tb.json`". After this record they are
  deliberately not, so that sentence is rewritten to name the divergence and
  cite this record. The three rung-1 descriptions are likewise extended to say
  why they stay put. No rung-1 value changes.
- **[DR-0014](DR-0014-bottom-plate-sampling.md) is not superseded and not
  weakened**, on either loop. Its ordering claim is still enforced on the
  gate-level netlist, now with 31.3 ns of *required positive margin* on both
  the single-ended and the differential loop instead of a window no skew
  corner could satisfy. [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md)
  is untouched.
- **DR-0028's tracked debt is discharged.** Its Consequences bullet gains a
  pointer to this record; no value in DR-0028 changes and its derivations are
  not reopened.

## Spec lines affected

- `README.md#target-specification` — **none changed**. No row is added,
  widened, relaxed or removed; the acquisition window and isolation gap have
  no row in the ratified table, which is why this record and DR-0028 exist.
- `sim/sar-logic-functional-gates/testbench/tb.json` — `acq_window_ns` —
  **changed** (`min 185.0` → `175.0`, `max 190.0` → `218.7`); `iso_gap_ns` —
  **changed** (`min 60.0` → `31.3`, `max 65.0` → `75.0`); `iso_gap_df_ns` —
  **changed** (`min 60.0` → `31.3`, `max 65.0` → `75.0`). Measurement
  expressions unchanged. Evidence note corrected (no value).
- `sim/sar-logic-functional/testbench/tb.json` — `acq_window_ns`,
  `iso_gap_ns`, `iso_gap_df_ns` — **unchanged, by decision**; the three
  descriptions are **clarified** to state what the bound guards and why it
  diverges from the gate-level sibling. No limit and no expression moves.
- `spec/decision-records/DR-0028-gate-level-acquisition-isolation-bounds.md` —
  **clarified, no value changed**: one pointer added to the Consequences
  bullet that filed this debt. Its limits, derivations and Spec-lines-affected
  list are untouched, and it is **not** superseded.
- `spec/decision-records/DR-0014-bottom-plate-sampling.md`,
  `spec/decision-records/DR-0027-gate-decode-one-hot-hazard-budget.md` —
  **not superseded, no value changed.**
- `sim/sar-logic-functional-gates/records/*`,
  `sim/sar-logic-functional/records/*` — **untouched.** Re-read against this
  decision, never re-scored or rewritten.
