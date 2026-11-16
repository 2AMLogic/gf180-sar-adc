# DR-0046: The one-hot checks measure the power-up conversion's arbitrary select pattern — extend DR-0031 part 2's window to `conf_*`/`nside_*`, keep the coverage witnesses where they are

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-11-16
- **Decided by**: Builder agent, issue #844
- **Supersedes**: none — this record narrows one clause of
  [DR-0031](DR-0031-power-up-first-conversion-validity.md) part 2's
  "Not taken" note; DR-0031's decision, its parts 1 and 3, and its
  code-error correction all stand unchanged.
- **Superseded by**: (none while this record stands)
- **Related**: #844 (this record's own issue, and the investigation whose
  measurements this record cites:
  `sim/sar-logic-functional-gates/investigations/20261116-issue-844-cold-corner-sequencing.md`),
  #779 / PR #843 (the record that produced the first measured −40 °C /
  125 °C data and surfaced the failures this record explains),
  [DR-0031](DR-0031-power-up-first-conversion-validity.md) (the power-up
  contract and the code-error window this record extends),
  [DR-0027](DR-0027-gate-decode-one-hot-hazard-budget.md) (the steady-state
  hazard budget whose evidence base this record leaves untouched),
  [DR-0014](DR-0014-bottom-plate-sampling.md) (the one-hot invariant itself),
  #327 / #371 (the precedent: DR-0031 part 2's execution on the code-error
  family)

## Context

The gate-level functional deck's first measured −40 °C / 125 °C grid
(`sim/sar-logic-functional-gates/records/20261116-012005-d0b5171.md`, PR
#843 for #779) failed `nside_cells_df` at three of its nine non-27 °C
points. Issue #844's investigation fetched the record's own hash-verified
stored logs and stamped every violating measure's `MAX`/`MIN` instant
(`at=`). For two of the three `nside_cells_df` excursions the maximum falls
**inside the first conversion after power-up** — the conversion DR-0031
part 1(b) ratifies as invalid and discardable:

| point | `nside_cells_df` | `at=` | inside conversion 1? (drdy #1 closes ≈ 1.126 µs) |
|---|---|---|---|
| `ss_125c_3.30v` | 9.84717 (limit 8.9–9.1) | **0.939 µs** | yes |
| `sf_125c_3.30v` | 9.90088 (limit 8.9–9.1) | **0.751 µs** | yes |
| `ss_-40c_3.30v` | 9.16096 (limit 8.9–9.1) | 63.000 µs | **no** — steady state |

The same split holds for their `conf_df` peaks (both `at=` 0.376 µs, reading
18.078/18.084 against the `max=20` bound — inside conversion 1, and at 90 %
of the bound on power-up garbage even where they pass), and for
`nside_cells_se`'s 125 °C peaks (`at=` ≈ 1.0 µs).

Conversion 1 has **no one-hot invariant to violate**. `sar_ctrl.v`'s
`start` pulse seeds only the `ph[15:0]` ring; the engaged-weight flags
`eng[9:1]`, the trial registers `q[9:0]` and the output register `c[9:0]`
have no reset (DR-0008's `dffq_1`), so conversion 1's select pattern is an
arbitrary function of the power-up flop state — up to both `sel_hi` and
`sel_lo` asserted at a weight, i.e. `nside_cells_df` up to 18 and
`sw_conflict_df` up to 36 in principle, independent of any decode hazard.
DR-0031 part 1(b) ratified exactly this: conversion 1's word "is therefore
an arbitrary function of the power-up flop state and must not be consumed".

The bound these failing rows are scored against is **not** where the
problem is. DR-0027's budgets (`sw_conflict_df max=20`,
`nside_cells_df` unchanged at 8.9–9.1, `nside_cells_se max=0.1`) budget a
*steady-state, sub-nanosecond* decode hazard — a ~143–165 ps one-hot gap
per acquisition-window-closing edge, worst measured 13.0045 /
9.04957-implied / 0.0644431 at 27 °C. Conversion 1's arbitrary pattern is
outside anything that budget describes, and a bound widened to admit it
would no longer be a decode-hazard budget at all — it would be a
power-up-state lottery ticket. Per `CLAUDE.md` no bound moves to make a
result pass, and none does here.

## Decision

**Two parts. No bound moves.**

**1. Extend DR-0031 part 2(a)'s window to the one-hot checks.** In
`sim/sar-logic-functional-gates/testbench/tb.json` **only**, the four
one-hot-family measurements move their window start past the discarded
conversion, exactly as DR-0031 part 2(a) already did for that deck's
code-error family. The rung-1 ideal deck
`sim/sar-logic-functional/testbench/tb.json` is **not** edited: DR-0031
lines 171-174 (ratified) keep the rung-1 ideal decks at `FROM=0.1u` because
their XSPICE `sar_ctrl_a` seeds the ring with `ph15`'s `ic=1` and powers
every other flop up at `ic=0`, so their first conversion is valid and
"discarding it would cost a conversion of coverage for nothing" (see also
DR-0031 line 290). Conversion 1's arbitrary select pattern is a property of
the synthesized netlist's no-reset flops, which the rung-1 deck does not
instantiate:

- `meas tran conf_se MAX v(se_conf) FROM=0.1u` → **`FROM=1.5u`**
- `meas tran conf_df MAX v(df_conf) FROM=0.1u` → **`FROM=1.5u`**
- `meas tran nside_se MAX v(se_nside) FROM=0.1u` → **`FROM=1.5u`**
- `meas tran nside_df MAX v(df_nside) FROM=0.1u` → **`FROM=1.5u`**

1.5 µs is DR-0031's own already-measured choice: `drdy` #1 rises at
1.06305 µs and its window closes ≈ 1.1257 µs, so a 1.5 µs start drops
conversion 1 and nothing else. The checks keep scoring the full steady-state
conversion sequence (conversions 2–64), which is what DR-0014's invariant
and DR-0027's budget are about.

**2. The `code_*` coverage witnesses keep `FROM=0.1u` — now with their
reason recorded at the measurement, not inherited from a clause that
bundled them with the one-hot checks.** DR-0031 part 2's "Not taken" note
kept *four* families at the old window and gave one rationale: "`code_se_lo`
in particular *needs* conversion 1 — it is the witness that the sweep
reached the bottom of the range." That rationale is genuinely code-family
specific and does not extend to `conf_*`/`nside_*`; it was the bundling,
not the reasoning, that this record corrects. The code witnesses keep the
wide window because:

- they are range witnesses, not correctness or invariant checks —
  `code_se_min`'s own bound (`[-0.5, 15]`) was already derived, in the same
  manifest, *with conversion 1 scored* ("the FIRST conversion's own
  acquisition instant lands near ~0.19 us into the run"), so conv-1
  behaviour is inside their ratified envelope by construction; and
- `se_code`/`df_code` are bounded 0–1023 by construction (a weighted sum of
  ten threshold comparisons), so conversion 1's arbitrary pattern cannot
  push them outside a range witness's meaning the way it can push a
  one-hot sum to 18.

## Alternatives considered

- **Widen `nside_cells_df` to admit 9.9.** Rejected on the measurement
  itself: two of the three excursions are conversion-1 artefacts, so the
  bound is not what is wrong, and the third (`ss_-40c`, steady state) is a
  genuine cold-corner excursion of ~0.06 — the DR-0027 skew family at
  larger magnitude, needing a waveform and its own disposition (see the
  investigation), not a bound written around a power-up lottery.
- **Keep `FROM=0.1u` and let the bound cover conversion 1 too** (i.e.
  treat the 27 °C data as the whole envelope). Rejected: conversion 1's
  select pattern is PVT-dependent by DR-0031's own mechanism (its A/B
  flipped 252→0 LSB by PVT alone), so no fixed bound on a conv-1-scoring
  one-hot check can be derived — only observed to hold so far. A check
  whose failure means "the power-up flops happened to come up a bad way"
  is not a decode-hazard check.
- **Move the window on both rungs.** Rejected: DR-0031 lines 171-174 state
  the reason the rung-1 deck diverges (its XSPICE `sar_ctrl_a` makes the first
  conversion valid), and the rung-1 deck's latest record
  (`sim/sar-logic-functional/records/20261113-080421-3eed6a0.md`) scores
  conversion 1 at the numeric floor (`sw_conflict_*` 4.09e-14,
  `nside_cells_se` 0, `nside_cells_df` 9 against max=0.02 / 8.9-9.1), so
  the move would drop ~1.4 us of passing coverage, retire that record as
  evidence, and buy a re-run for no measurement gain. All of this record's
  evidence is from the gate-level deck.

## Consequences

- **The composed deck changes, so every record taken before this change is
  evidence for the old instrument** — same disclosure DR-0031 part 2 made.
  `sim/sar-logic-functional-gates/records/` and
  `sim/sar-logic-functional/records/` are append-only and are not edited
  (the rung-1 deck is unchanged, so its records stay current evidence);
  re-read the gate-level deck's `nside_cells_df`/`sw_conflict_*`/`nside_cells_se` values as
  including conversion 1. No already-passing value is invalidated by the
  re-read: for every measured point whose `MAX` instant is already at or
  after 1.5 µs (e.g. `tt_27c` `nside_df` 9.04957 `at=` 1.939 µs), the
  narrower window scores the identical value, because a window that starts
  later cannot lower a maximum that was attained after the start — and the
  27 °C records' one-hot `at=` stamps all land at or after 1.5 µs except
  where the point fails today.
- **The two 125 °C `nside_cells_df` failures are expected to become
  passes**, and `sw_conflict_df`'s 18.08-against-20 conv-1 headroom
  artefacts disappear. This is an instrument correction with DR-0031 part 2
  as precedent, not a result change. Confirmed on the batch fleet by the
  run this decision's own issue minted:
  `sim/sar-logic-functional-gates/records/20261116-082605-974d249.md`
  (`ss_125c_3.30v` `nside_cells_df` 9.847 → **9.091 PASS**; `sf_125c_3.30v`
  9.901 → **9.036 PASS**; `sw_conflict_df` 18.078/18.084 → 11.540/10.763;
  every untouched measure identical — `conv_period_ns` 1000.0,
  `acq_window_ns` 186.7/196.0, `err_*` 0).
- **`ss_-40c`'s steady-state excursion is untouched by this record** —
  `nside_cells_df` 9.16096 at 63.0 µs is inside the new window too. Its
  disposition (a real cold-corner decode excursion, DR-0027's skew family)
  is the investigation's, and is not closed by the window change.
- **DR-0027 is not superseded and no value in it changes.** Its budgets
  were derived and stay derived for the steady-state hazard; this record
  only stops the instrument from feeding them conversion 1.
- The regression test added with this record
  (`sim/tests/test_sar_ctrl_gates_tb.py::PowerUpWindowContractTests`)
  asserts the window contract mechanically, so the asymmetry cannot
  silently return: on the gate-level deck one-hot family and code-error
  family at `FROM=1.5u`, code witnesses at `FROM=0.1u`; on the rung-1 deck
  everything stays at `FROM=0.1u`; the code witnesses are identical across
  rungs.

## Spec lines affected

- `README.md#target-specification` — **none changed**. No ratified row is
  added, widened, relaxed or removed; the one-hot checks are regression
  testbench instrumentation (DR-0027's precedent), not target-spec rows.
- `sim/sar-logic-functional-gates/testbench/tb.json` — `analyses`:
  `conf_se`, `conf_df`, `nside_se`, `nside_df` — **measurement window
  changed, bounds unchanged** (`FROM=0.1u` → `FROM=1.5u`). `checks`
  descriptions of the same four: clarified to state the window basis.
  `code_se_*`/`code_df_*` — **unchanged, by decision** (see Decision part 2).
- `sim/sar-logic-functional/testbench/tb.json` — **unchanged, by decision**
  (DR-0031:171-174; see Decision part 1).
- `spec/decision-records/DR-0031-power-up-first-conversion-validity.md` —
  **not edited** (append-only precedent); this record's Supersedes line
  scopes the narrowing and the investigation document cites both.
- `spec/decision-records/DR-0027-gate-decode-one-hot-hazard-budget.md` —
  **not superseded, no value changed.**
- `sim/tests/test_sar_ctrl_gates_tb.py` — new `PowerUpWindowContractTests`.
- `sim/sar-logic-functional-gates/records/*`,
  `sim/sar-logic-functional/records/*` — **untouched.**
