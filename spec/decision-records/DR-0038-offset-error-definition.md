# DR-0038: which statistic of the ADC input-referred offset is held to the "≤ 2 LSB, 3σ mismatch" bound — spread about the mean, mean-plus-spread, or a quantile of |offset|

- **Status**: proposed — for operator ratification. Nothing below is in force
  until the operator picks an option; agents do not choose between readings of
  a ratified spec row.
- **Date**: 2026-10-09
- **Decided by**: Builder agent drafting for the operator, issue #453
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #453 (this question), #427 /
  [`sim/adc-offset-mc/README.md`](../../sim/adc-offset-mc/README.md) §5
  (pilot numbers), §6.2 and §6.7 item 1 (which defer to this record),
  [`README.md`](../../README.md) target table Offset row and note **[e]**,
  [DR-0006](DR-0006-spec-ratification.md) (ratified the row)

## Context

The ratified Offset row reads "≤ 2 LSB, untrimmed", binding condition "3σ
mismatch (not a PVT corner)", note [e]. It does not say whether the
population's systematic mean counts against the bound or only the mismatch
spread about it. The #427 pilot (`sim/adc-offset-mc/README.md` §5, `tt` /
27 °C / 3.3 V, mismatch only, 8 draws, evidence directory
`corners/20261009-042900-2a4b3fac/`) shows the choice changes the verdict:

- bound: 2 LSB_se = 6.445 mV (LSB_se = V_REF/1024 = 3.2227 mV);
- null control (mismatch off, 4/4 draws): systematic threshold +3.25 mV
  = 1.0 LSB_se, spread 0.000 mV;
- enabled draws: range 1.75 .. 5.25 mV, mean 3.69 mV, sample sd 1.178 mV
  (1.169 mV after Sheppard correction), 8/8 valid;
- §5 states these are eight draws at one PVT point and "none of this is the
  spec's number"; the row stays Unmeasured. The source of the +3.25 mV is
  not attributed in §5.

The comparator-inclusive population (§6) cannot start until the compared
statistic is fixed, because mean, σ and |offset| quantiles give different
verdicts on the same data. This record only frames that choice.

## Worked example: the three definitions on the §5 numbers

Derived here from the §5 figures, no new simulation. The σ_U row uses §6.1's
formula `σ_U = s·√((n−1)/χ²₀.₀₅,ₙ₋₁)` with n = 8 (7 d.o.f., χ² = 2.167, the
"about 1.8×" of §5/§6); normal-model tails use `s = 1.169 mV`, mean 3.69 mV.
Eight draws support a plausibility reading only, not a verdict.

| Definition compared with 6.445 mV | Point value on the pilot | In LSB_se | Verdict at point | 95 % upper (σ_U, n = 8) |
|---|---|---|---|---|
| 1. `3σ` about the mean | 3 × 1.169 = 3.51 mV | 1.09 | within bound | 3 × 1.169 × 1.797 = 6.30 mV (1.96) — within, by 0.14 mV |
| 2. `\|mean\| + 3σ` | 3.69 + 3.51 = 7.20 mV | 2.23 | **exceeds** bound by 0.75 mV | 3.69 + 6.30 = 9.99 mV (3.10) — exceeds |
| 3. quantile of `\|offset\|` (P(\|offset\| ≤ 6.445 mV)) | observed max 5.25 mV of 8; normal-model P(exceed) ≈ 0.9 % (z = 2.36) | — | 8 draws cannot resolve 99.73 % (§6.1: ~1,000 draws needed) | undetermined at n = 8 |

Note the pilot mean (3.69 mV) is 0.44 mV above the null value (3.25 mV) with
standard error 0.42 mV (§5), so the shift is not distinguishable from zero;
the mean in this example is effectively the systematic +3.25 mV. Definitions
2 and 3 count that term, and it alone consumes 1.0 of the 2 LSB. Definition 3
with a ~99.73 % target and the observed mean is the strictest in practice: the
normal model gives ≈ 99.1 % within bound, below 99.73 %.

## Decision

Proposed for ratification: **Option 1** below. If the operator ratifies it,
the Offset row's binding condition is read as "3σ of the input-referred
offset about its population mean, per PVT corner, at the worst corner", and
the population mean is characterised and published per corner as a datasheet
constant (a reported number, not a new gated bound). The 2 LSB value is
unchanged. If the operator ratifies a different option, that option's reading
applies instead. Until then the row is read exactly as ratified, stays
Unmeasured, and `sim/adc-offset-mc/README.md` §6.2 records the question as
pending ratification.

## Options, ranked

Q1. Which statistic is compared with 2 LSB (6.445 mV) for the Offset row?
   Blocks the comparator-inclusive population (§6.7 item 1); it is the
   operator's call because it chooses between readings of a ratified row.

1. **`3σ` about the mean, mean reported separately (recommended).** Why: it is
   the reading note [e] already states. [e] says static offset "consumes no
   INL/DNL or ENOB budget and is removable by the user as a constant code
   subtraction; that is the offset-handling policy, in place of a trim", and
   its 2 LSB bound is *derived* as 3σ of the comparator-pair mismatch alone
   (`3 × 1.92 mV = 5.8 mV = 1.8 LSB`), a spread-only quantity. A user of the
   1 MS/s block sees a fixed code offset; the part common to all dies (the
   mean) can be subtracted once from a datasheet constant, and only the
   die-to-die spread needs a per-die measurement. Gives up: the gated number
   no longer bounds the absolute error at the pin, so the mean must be
   published per corner and checked not to eat the code range (it is 1.0 LSB
   in the pilot at one PVT point; its spread over PVT is not measured). It is
   also the thinnest pass on the pilot at 95 % confidence (6.30 vs 6.445 mV),
   so the full population may still fail it; that is a measurement outcome,
   not a reason to prefer another definition.
2. **`|mean| + 3σ`.** Why lower: it bounds the worst absolute offset a
   die can show and needs no assumption about user calibration, which is the
   more conservative reading. It ranks below 1 because it charges the block
   2 LSB for a term the stated policy treats as free to remove, it is not the
   quantity note [e]'s bound was derived from, and on the pilot it already
   fails (7.20 mV, 2.23 LSB) because of the 1.0 LSB systematic term, which
   would effectively tighten the ratified bound to about 1 LSB of spread.
   That is a spec tightening by interpretation. It still wins over 3 by
   needing only a normal-model σ estimate and a mean.
3. **Empirical quantile of `|offset|` (e.g. P ≤ 2 LSB ≥ 99.73 %).** Why
   lower: it makes no normality assumption (it is §6.1 Claim B) and is
   the most literal "fraction of dies within 2 LSB", but it counts the mean
   like option 2, and at the 99.73 % level it needs on the order of a
   thousand draws with zero exceedances per corner (§6.1), against §6.3's
   45-corner screening of n = 30 each. It is best kept as the normality
   fallback for option 1 rather than as the definition.
4. **Defer.** Why last: costs nothing today, but the population cannot start
   (§6.7 item 1), so the ratified row stays Unmeasured indefinitely and any
   population run first would be forced to pick silently.

## Alternatives considered

- **Choosing the definition by the sign of the verdict** — rejected outright:
  the definition is picked on the policy in note [e] and on what a user
  observes, not because option 1 passes the pilot and option 2 does not.
  Agents do not relax or tighten the ratified spec to change a result.
- **Two gated bounds (spread ≤ 2 LSB and |mean| ≤ some value)** — adds a new
  ratified limit with no derivation behind it; if the operator wants a mean
  limit it is a separate record with its own evidence.

## Consequences

- If option 1: §6 proceeds with `3σ_U` (Claim A, gated by the §6.4 normality
  test, Claim B as fallback) per PVT corner; mean per corner is reported.
  Bad: the row's headline no longer bounds raw absolute offset; a reader
  comparing against a datasheet that quotes absolute offset must read the
  mean beside it; the pilot's 95 % margin is 0.14 mV, so a failure is
  plausible.
- If option 2 or 3: the pilot's point estimate already exceeds (option 2) or
  is likely to miss (option 3) 2 LSB; the likely follow-up is a *separate*
  record proposing a tighter comparator design target or a changed bound,
  never an edit to this one.
- Under every option the campaign records mean, σ and |offset| quantiles
  (§6.2), so the choice can be revisited by a superseding record without
  re-simulating.
- Not decided here: whether the +3.25 mV systematic term is a design artefact
  to remove; the PVT spread of the mean; any change to the 2 LSB value.

## Spec lines affected

None while proposed — this record changes no spec line and does not change
the Offset row's Unmeasured status. On ratification of option 1 (or another
option) the following would be clarified, by the ratifying change:

- `README.md#target-specification` — Offset error row, binding condition —
  clarified (no value change): states which statistic of the offset
  population is held to 2 LSB.
