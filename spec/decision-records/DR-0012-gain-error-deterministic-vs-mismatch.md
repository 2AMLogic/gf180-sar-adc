# DR-0012: Gain error — the ratified row bounds mismatch only; deterministic charge injection gets its own budgeted row

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #39
- **Supersedes**: none — first record on this question. It does not replace
  [DR-0006 (spec ratification)](DR-0006-spec-ratification.md)'s gain-error
  decision; it adds a second, separately-conditioned row beside it and
  narrows one note's attribution, leaving every ratified value intact.
- **Superseded by**: (none while this record stands)
- **Related**: #1, #10, #39, [DR-0006 (spec ratification)](DR-0006-spec-ratification.md),
  [DR-0007](DR-0007-track-switch-topology.md) § "Charge injection / gain
  error — measured, real, and a separate open problem",
  [DR-0013](DR-0013-input-pin-charge-split.md) (the mitigation this record's
  new row is then verified against), `sim/track-switch-sampling/records/20260801-023754-267871b.md`,
  `sim/device-characterization-report.md` §2.2

## Context

[DR-0007](DR-0007-track-switch-topology.md) measured the input sampling
switch's turn-off charge-injection pedestal across the ratiometric input
range on the full 117-point PVT grid
(`sim/track-switch-sampling/records/20260801-023754-267871b.md`). The
*input-dependent* part of that pedestal — pedestal at full scale minus
pedestal at zero — is **3.57–5.38 LSB** for the switch DR-0007 chose, 7–11×
the ratified `Gain error ≤ 0.5 LSB, untrimmed, excluding V_REF error` row
(`README.md#target-specification`), at every PVT point measured. DR-0007
filed that as #39 rather than absorbing it.

Before any mitigation can be judged, one question has to be answered:
**does that ratified row bound this quantity at all?** The row's stated
condition is *3σ mismatch*; the measurement is *zero-mismatch,
deterministic, PVT-corner*. Getting this wrong in either direction is
expensive — judge it in-scope and the mitigation is measured against a
budget that is already fully spent; judge it out-of-scope and a 5 LSB
deterministic term ships under a 0.5 LSB headline. Three pieces of evidence
in the ratified text settle it.

**1. The row's binding condition names a statistic, not a corner.** In the
same column where every PVT-bound row of the table names a corner
(`ss_125c_2.97v`, `ff_125c_3.63v`, …), the gain row reads "3σ mismatch". Its
two neighbouring statistical rows are more explicit still — INL/DNL: "3σ
Monte Carlo mismatch (**not** a PVT corner)"; Offset error: "3σ mismatch
(not a PVT corner)". A quantity that is identical on every nominally-matched
die and moves only with process/voltage/temperature is precisely what that
parenthetical is distinguishing the row *from*.

**2. The 0.5 LSB value is derived, in note [e], as the mismatch term itself
— with nothing else in it.** Note [e]: "The on-chip term is the 3σ spread of
the total array — `3 × 0.52 % / √1024 = 0.049 %` of full scale = 0.5 LSB".
The number is not a budget with allocations inside it; it *equals*, to the
rounding, the single mechanism it names. Reading it as also bounding a
second, deterministic term would double-book a line the ratification wrote
with one entry.

**3. The ratification did not overlook switch charge injection — it filed it
under a different row.** Note [d] budgets "switch charge injection **after
compensation**" **inside** the INL/DNL numbers, citing
`sim/device-characterization-report.md` §2.2's "raw T-gate input-dependent
pedestal spread is 4.4 LSB". So the intent question is settled by the text:
charge injection was costed, and it was not costed into the gain row.

**Where note [d]'s attribution goes wrong, and why that leaves a hole.** The
input-dependent pedestal is an affine-plus-residual quantity: a part linear
in `V_in` (a gain error) plus the deviation from that straight line (a
linearity error). INL is evaluated *after* offset and gain are removed —
under the endpoint fit this repo's own testbench implements (the `nl_*`
columns of `sim/track-switch-sampling/testbench/tb.json` take the deviation
from the f00→f100 chord) and under any standard best-fit convention alike.
By construction, then, the affine part cannot consume INL/DNL budget. The
measurement bears that out. For the very geometry note [d] cites — devchar
§2.2's nominal 10 µm/20 µm T-gate, whose "4.4 LSB spread" is that note's
number — the full-grid re-measurement on the real 8.827 pF array splits the
spread into **2.04–2.92 LSB of gain error** and only **0.27–0.42 LSB of
endpoint-fit residual** (`gain_tg1_lsb` / `nl_tg1_lsb`,
`sim/track-switch-sampling/records/20260801-070046-50bffb1.md`); for the
DR-0007 switch it is 3.57–5.38 LSB against 0.43–0.69 LSB. Roughly seven
eighths of what note [d] filed under INL/DNL is in fact gain error. The
ratified table therefore contains **no row that bounds the deterministic
gain term**, and that hole, not a failing row, is what #39 actually found.

**Why the answer is not "out of scope, therefore unbounded".** A datasheet's
gain-error line has to bound what a user measures, and a user measuring gain
error sees the deterministic and the statistical terms summed — they are not
separable at the pin. The deterministic term is therefore out of scope of
*that row*, which is conditioned on mismatch, but not out of scope of *gain
error*. The resolution is a second row, not silence.

## Decision

**The ratified `Gain error ≤ 0.5 LSB` row bounds the mismatch component
only. The deterministic charge-injection component is specified in its own
new row, budgeted at 0.5 LSB over the full PVT grid, and the two are
published together with their sum.** No ratified value is changed and no
ratified row is relaxed.

| `README.md#target-specification` row | Target | Binding corner / condition |
|---|---|---|
| Gain error, mismatch *(existing row, value and condition unchanged; label and parenthetical clarified)* | ≤ 0.5 LSB, untrimmed, **excluding** V_REF error | 3σ mismatch (**not** a PVT corner); full scale is ratiometric to V_REF — note **[e]** |
| **Gain error, systematic** *(new)* | **≤ 0.5 LSB, untrimmed, excluding V_REF error** | **Full PVT grid (13 process × 3 temperature × 3 supply), zero mismatch, at the specified input drive network ([DR-0013](DR-0013-input-pin-charge-split.md)) — note [g]** |

with note **[g]** stating the consequence a user actually measures:
**worst-case total gain error ≤ 1.0 LSB**, the two rows summed.

### Derivation of the new row's target (0.5 LSB), shown not asserted

A spec row sized to whatever the present design happens to measure is not a
spec; CLAUDE.md is explicit that agents do not relax the ratified spec to
make results pass, and the same discipline has to apply to a *new* row or
the rule is trivially evaded by adding rows. So the 0.5 LSB is derived:

- **No other ratified row constrains it.** A deterministic gain error is
  invariant under the ENOB, SFDR, INL and DNL definitions this table uses —
  each removes a scale factor (or, for the ENOB row, is defined against an
  rms *noise* budget) before the quantity is evaluated. Its bound cannot be
  borrowed from another row's arithmetic; it has to come from what "gain
  error" itself promises.
- **What it promises is note [c]'s ratiometric full scale** — "full scale ≡
  `V_REF` by construction". A gain error of `g` LSB is exactly the amount by
  which that construction fails. The ratification already fixed how much
  failure is acceptable from the one mechanism it costed: **0.5 LSB**.
- **The deterministic term is therefore budgeted at that same 0.5 LSB, not
  looser.** Looser would let the headline gain number be dominated by the
  mechanism the headline does not name — the failure mode this record
  exists to close. Tighter would be an unearned tightening with no
  derivation behind it. Equal shares between a statistical and a
  deterministic contributor is the same convention note **[b]** uses to
  split the non-quantization noise budget three ways.
- **The two add, so the sum is published**: ≤ 1.0 LSB worst case (0.049 % +
  0.049 % of full scale). Publishing only one half of a number a user
  measures as a whole is the same silent failure in a new costume.

### Also clarified (no value change)

Note **[d]**'s attribution of "switch charge injection **after
compensation**" to the INL/DNL budget is narrowed to the part that lands
there under the table's own linearity convention — the endpoint-fit residual
(measured 0.43–0.69 LSB for the DR-0007 switch, inside the `< 1 LSB` target
but consuming most of it; 0.013–0.197 LSB once
[DR-0013](DR-0013-input-pin-charge-split.md)'s drive network and dummy ratio
are applied) — with the affine part moved to the new
systematic-gain-error row. The INL/DNL target value is unchanged.

## Alternatives considered

- **Read the existing row as already bounding both.** Not chosen: it is
  contradicted by all three evidence points above, and it would judge every
  candidate mitigation against a 0.5 LSB budget that note [e] shows is
  already fully consumed by array mismatch alone — i.e. against a budget of
  zero, which no switch can meet. Convenient for declaring failure, but not
  what the ratified text says.
- **Declare the deterministic term out of scope of "gain error" entirely,
  with no new row.** Not chosen: this is the reading #39 was filed to
  prevent. The two components are not separable at the pin, so a table with
  no bound on the deterministic one publishes a gain-error figure the part
  does not meet — a categorical-difference argument used to make a real
  5 LSB error nobody's problem.
- **Relax the existing row to cover both (e.g. `≤ 6 LSB` total).** Not
  chosen, and not close: CLAUDE.md forbids relaxing the ratified spec to
  make results pass. The measured 3.57–5.38 LSB is a property of one
  un-tuned compensation choice and one unspecified drive condition, not a
  floor — [DR-0013](DR-0013-input-pin-charge-split.md) measures the same
  mechanism at 0.421 LSB worst case over the same grid, 13× lower, by
  changing the drive network and the dummy width ratio.
- **Fold the deterministic term into the full-scale definition instead of
  specifying it.** Not chosen: full scale is ratiometric to `V_REF` *by
  construction* (note [c]) and the row says "untrimmed", so there is no
  mechanism — no trim, no scale register — by which it could be absorbed.
  It also moves over PVT (1.8 LSB of spread in the DR-0007 measurement), so
  even a hypothetical one-point absorption would leave the spread behind.
- **Defer the question to #13 (whole-converter testbench suite).** Not
  chosen: #13 measures the converter's *total*; it cannot decide which
  ratified row a mechanism belongs to, and until that is decided no
  mitigation for #39 can be judged. Deferring here would have left the
  decision to be made implicitly, by whichever testbench happened to report
  the number first.

## Consequences

- **The datasheet gets longer and slightly worse-looking, on purpose.** Two
  gain-error rows and a ≤ 1.0 LSB total replace one ≤ 0.5 LSB line. The part
  did not get worse; the published number got honest. This is the bad
  consequence, stated: a reader comparing headline numbers against a part
  whose datasheet quietly specifies only its mismatch term will read this
  one as 2× worse.
- **The systematic row is a *PVT-corner* row, so every future claim against
  it needs the full grid**, not a nominal-corner spot check — the same
  standard the settling and power rows already carry, and the reason #39's
  finding was visible at all.
- **The systematic row is conditioned on a specified input drive network.**
  This record does not specify it; [DR-0013](DR-0013-input-pin-charge-split.md)
  does, and the row is unverifiable — not merely unmet — without it. That
  coupling is real and is the price of the split: a gain-error row that
  depends on how the user drives the pin is a weaker promise than one that
  does not.
- **#13 (testbench suite) inherits a two-part gain-error check**: a Monte
  Carlo mismatch run against the existing row and a corner-grid run against
  the new one. Reporting one number for both would no longer substantiate
  either.
- **Offset has the same structural split, and it is left alone here.** The
  pedestal at zero scale is a deterministic offset contribution against a
  row that is likewise conditioned on 3σ mismatch. It is not opened here
  (one decision per record) and it is not urgent: note [e] already makes
  offset user-removable by constant code subtraction, and under
  [DR-0013](DR-0013-input-pin-charge-split.md)'s drive network the
  deterministic offset contribution measures **≤ 0.119 LSB**, well inside the
  existing 2 LSB row. It was **1.110–1.558 LSB** before that record — most of
  the row consumed by the sampling switch alone — which is the version of this
  question that would have been urgent. A follow-up record should still make
  the same distinction explicit rather than leaving it to be re-derived.
- **Nothing about DR-0007's topology choice changes.** That record turns on
  SFDR and on the bootstrap's device-reliability blocker; this record
  re-files the number DR-0007 flagged, it does not re-open the choice.

## Spec lines affected

- `README.md#target-specification` — Gain error row — **clarified (no value
  change)**: renamed "Gain error, mismatch" and its condition made explicit
  as `3σ mismatch (**not** a PVT corner)`, matching the Offset and INL/DNL
  rows' existing phrasing. Target `≤ 0.5 LSB, untrimmed, excluding V_REF
  error` unchanged.
- `README.md#target-specification` — Gain error, systematic — **new**:
  `≤ 0.5 LSB, untrimmed, excluding V_REF error`, binding condition full PVT
  grid at the [DR-0013](DR-0013-input-pin-charge-split.md) input drive
  network, zero mismatch.
- `README.md#target-specification` — note **[d]** — **clarified (no value
  change)**: the charge-injection term budgeted inside INL/DNL is narrowed
  to the endpoint-fit residual; the affine part is pointed at the new row.
- `README.md#target-specification` — note **[e]** — **clarified (no value
  change)**: states that its derivation covers the mismatch row only.
- `README.md#target-specification` — note **[g]** — **new**: the systematic
  row's derivation and the ≤ 1.0 LSB total-gain-error statement.
