# DR-0045: Track-switch topology — DR-0014's bottom-plate acquisition path supersedes DR-0007's dedicated 4×+dummy switch; what survives, and the systematic gain-error row's stale provenance

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-11-15
- **Decided by**: Builder agent, issue #819
- **Supersedes**: [DR-0007](DR-0007-track-switch-topology.md) — same question
  (the input sampling switch's topology). DR-0007's Decision — a dedicated
  4× `40u`/`80u` CMOS transmission gate with half-width dummy charge-injection
  compensation, one instance per input pin (dummy ratio later revised to 7/16
  by [DR-0013](DR-0013-input-pin-charge-split.md)) — was removed from the
  converter as a side effect of [DR-0014](DR-0014-bottom-plate-sampling.md)'s
  move to bottom-plate sampling, effected by implementation (#58) without a
  record naming DR-0007 until now: DR-0014's own `Supersedes` field names
  DR-0011 only, and its records-to-update pass rules explicitly on DR-0013 but
  is silent on DR-0007. This record retires that Decision and states which
  parts of DR-0007 survive it.
- **Superseded by**: (none while this record stands)
- **Related**: #819 (this record's issue), #53, #58, #61, #75,
  [DR-0007](DR-0007-track-switch-topology.md) (the retired choice),
  [DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md) (the
  `Gain error, systematic` row),
  [DR-0013](DR-0013-input-pin-charge-split.md) (the 7/16 dummy ratio and the
  drive contract that survives),
  [DR-0014](DR-0014-bottom-plate-sampling.md) (the removal and its own
  records-to-update pass),
  [DR-0016](DR-0016-input-structure-ron-repoint.md) (the Input-structure
  `R_on` re-point — the precedent for this record's "evidence stale, value
  unchanged" treatment),
  [DR-0019](DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md) (the `C_u`
  resize), `sim/track-switch-sampling/records/20261105-083025-9de35aa.md` and
  `sim/track-switch-sampling/records/20260817-142951-72d15de.md` (the
  dedicated-switch (`tg4dum`/`cxopt`) deck's lineage — the source of README
  note **[g]**'s figure), `sim/dr0014-sampling/` (the built-path
  converter-level deck), `sim/characterization-summary.md` (the row's evidence
  ledger), `sim/adc-enob-fft/investigations/20261114-issue-800-cold-distortion-candidate-ranking.md`
  (candidate A4 — where the gap surfaced), #769 (dead-cell removal — operator
  decision, out of scope here), #595 (PDK re-pin re-qualification, which
  re-runs the same superseded deck)

## Context

[DR-0007](DR-0007-track-switch-topology.md) (`Status: proposed`) chose a
dedicated 4× `40u`/`80u` T-gate with half-width dummy compensation as the
converter's input sampling switch, against a bootstrapped switch. It was never
built that way. [DR-0014](DR-0014-bottom-plate-sampling.md) moved the sampling
phase to the bottom plates, and the built path connects the input to the array
through the nine parallel `10u`/`20u` cell T-gates of each side's fourth leg
(`design/adc-top/gen_adc_top.py`, `CDAC_SW_WN`/`CDAC_SW_WP` instantiated per
weight); the dedicated switch and its dummy devices were never instantiated in
the converter. DR-0014's records-to-update pass superseded DR-0011, ruled on
DR-0013, and — silently — left DR-0007 standing over a topology nothing builds.
Nothing else supersedes it either: no record names DR-0007 in a `Supersedes`
field, so a reader landing on DR-0007 cannot tell its Decision is void. The gap
surfaced from the Judge's cold-distortion candidate ranking (candidate A4 of
`sim/adc-enob-fft/investigations/20261114-issue-800-cold-distortion-candidate-ranking.md`,
filed as #819) and is a coherence defect, not a failing measurement: the
converter's acquisition path is DR-0014's, by implementation, and the records
now say so.

Two adjacent facts sharpen the case. First, the dead `TRACK_SW_*` constants in
`design/adc-top/gen_adc_top.py` (the dedicated switch's geometry, kept only
because `sim/top-plate-cpar/` still instantiates it) corroborate that the
topology left the design — but those constants and the `adc_tgate_dum` cell
are **#769**'s scope, an operator decision, and are not touched by this
record's PR. Second, README note **[g]**'s published figure for the
`Gain error, systematic` row — the row [DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md)
created and the dummy devices existed to protect — is still measured on the
removed topology (below), so the same silence left a stale-provenance figure
on a ratified row.

## Decision

**DR-0007's Decision is superseded.** The converter has no dedicated input
sampling switch and no dummy compensation; the acquisition path is
DR-0014's — sample on the bottom plates, input through the nine parallel cell
T-gates of each side's fourth leg. What survives and what does not:

- **T-gate vs. bootstrap — survives, and independently of sampling phase.**
  DR-0007's dead-zone argument is about device thresholds against the supply
  (no input code exists where both T-gate devices are off, at any grid corner),
  and its bootstrap rejection is about gate-oxide reliability at 3.3 V —
  neither premise mentions where or by whom the sampling instant is set.
  Every switch in the built converter is a plain CMOS T-gate; that is
  DR-0007's conclusion carried forward, not a new one.
- **Series `R_on` — superseded by a better measurement.** Nine parallel
  `10u`/`20u` legs measure **21.3–60.0 Ω** over PVT (`README.md` Input-structure
  row, re-pointed by [DR-0016](DR-0016-input-structure-ron-repoint.md)), lower
  than the dedicated 4× switch's 156–570 Ω; the settling margin DR-0007 sized
  grows. DR-0007's `R_on` numbers remain as the historical measurement of the
  switch it chose, not of the path that shipped.
- **Dummy compensation — does not survive, and has no replacement.** No
  dedicated switch means no turn-off pedestal at a sampling instant, hence no
  mechanism for half-width dummies to cancel; nothing else in the design plays
  that role, by intent (see the exposure ruling below). DR-0013's 7/16 ratio
  revision and its sizing contract are historical: they size a device the
  converter does not contain. DR-0013's *drive* contract
  (`R_source × (C_pin + C_in) ≤ 30 ns`, the required `C_pin`) is a separate
  decision, untouched and still in force — DR-0014 left it standing and this
  record does not reopen it.

**Residual exposure to the `Gain error, systematic` row
(`README.md` line 80 — [DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md)'s
row, not the mismatch row, which [DR-0019](DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md)'s
`C_u` resize governs and which the dummy devices never touched): none
unbounded, and the row is attested on the built path.** The mechanism the
dummies compensated — an input-dependent turn-off pedestal of a dedicated
switch *defining the sampling instant* — is structurally absent in the built
path: the sampling instant is the bottom-plate drive edge, and the input leg's
own turn-off pedestal does not set it (DR-0014's absorption argument). That
argument is not left standing on derivation alone: the converter-level deck
built for DR-0014's path, `sim/dr0014-sampling/`, measures the row on the
built path at zero mismatch across PVT — schematic 0.0021–0.0039 LSB, and
**extracted (governing) 0.000981002 LSB worst (`ff_-40c_3.63v`), ~510× inside
the ≤ 0.5 LSB bound** — and `sim/characterization-summary.md`'s
`Gain error, systematic` row already cites that lineage as governing. What is
stale is narrower: README note **[g]**'s *isolated switch-contribution* figure
(**+0.082 … +0.370 LSB**, from `sim/track-switch-sampling/`'s `tg4dum`/`cxopt`
branch — the dedicated-switch deck, re-run on the old switch even at the
DR-0019 resize). That deck cannot measure the built path, because the built
path has no dedicated switch to isolate; the converter-level total above
bounds whatever the input legs contribute, so no separate isolation
measurement is owed for the row to stand. This record and its README
annotation make the note say what it measures and stop implying the row rests
on it. DR-0014's re-take requirement ("the 0.421 LSB measurement … must be
re-taken") is satisfied in the only form the built path admits — at the
converter level, where the row lives — and is discharged as to the *row*;
the switch-level deck remains append-only history of the removed topology.
No re-measurement obligation is created by this record.

## Alternatives considered

- **Re-measure the isolated switch contribution on the built path before
  recording anything** — rejected: it requires a new switch-level deck
  modelling the fourth-leg path with a two-phase sample (the built path has no
  dedicated switch to drop into the existing deck), a batch-fleet PVT campaign
  against hardware that does not exist, and it would leave a proposed record
  describing an unbuilt topology standing the whole time. The converter-level
  total already bounds the row; the provenance defect should not wait on, and
  is not fixed by, an isolation measurement the row does not need.
- **Amend DR-0007 in place to describe the built path** — forbidden: records
  are superseded, never rewritten (`spec/decision-records/README.md`
  § "Superseding a ratified record"); DR-0007's Context, Decision,
  Alternatives considered, Consequences and Spec lines affected stay exactly
  as written.
- **Fold the supersession into DR-0014 as an amendment** — rejected:
  DR-0014 is itself still `proposed`, and editing a pending record to absorb a
  consequence discovered 15 months later obscures both records' histories.
  DR-0014's silence was a scoping gap, not a mistake to patch inside it.
- **Close as already covered** — tested and false: no record's `Supersedes`
  names DR-0007; [DR-0025](DR-0025-acquisition-leg-widening-not-adopted.md)
  does not mention DR-0007 or the dummy devices; DR-0014's records-to-update
  pass is silent on it. The premise of #819 was re-verified against
  `origin/main` before this record was written.

## Consequences

- README note **[g]** carries a provenance annotation ("evidence stale, value
  unchanged", the form DR-0014 established for the Input-structure row and
  DR-0016 discharged): the figure stays as measured, tagged to the removed
  topology, and the note now points at the built-path governing evidence. No
  target, threshold, measured value or row changes anywhere in `README.md`.
- `spec/decision-records/STATUS.md` is regenerated by the STATUS generator in
  the same PR, so the index shows DR-0007 `superseded-by DR-0045` and
  counts 45 records.
- **#769** (removing the dead `adc_tgate_dum` cell and `TRACK_SW_*`
  constants) gains the record its options are weighed against: with DR-0007
  superseded, the constants' only remaining referent is a deck that measures
  a superseded topology. This record does not remove them and does not
  prejudge the operator's choice.
- **#595** (PDK re-pin re-qualification) re-runs `sim/track-switch-sampling/`
  — the superseded-topology deck — under the re-pinned PDK, so its fresh
  records will measure the removed switch and will carry the same
  stale-topology caveat note **[g]** now carries. That is correct behaviour
  for a re-qualification (it re-scores the deck it has) and is not a reason
  to hold either issue; the caveat travels with the deck, not the record.
- Nothing under `sim/` is edited or appended to by this record's PR — the
  `tg4dum` records stay as history of the topology they measured, per the
  append-only rule both `sim/` and `spec/` share.
- Operator sign-off is still owed for DR-0007, DR-0014 and this record alike;
  nothing here ratifies anything. Until sign-off, DR-0007's `Status` reads
  `superseded-by DR-0045` (was: proposed) and this record reads `proposed`,
  matching the DR-0011/DR-0014 precedent for superseding one proposed record
  with another.

## Spec lines affected

- `README.md#target-specification` — note **[g]** — clarified (no value
  change): the `+0.082 … +0.370 LSB` figure's provenance is annotated as
  measured on the superseded dedicated-switch deck (`sim/track-switch-sampling/`'s
  `tg4dum`/`cxopt` branch, DR-0007's topology), evidence stale, value
  unchanged, with the row's built-path governing evidence
  (`sim/dr0014-sampling/`, per `sim/characterization-summary.md`) named. No
  target, threshold, measured value or row is changed.
- `spec/decision-records/DR-0007-track-switch-topology.md` — `Status` /
  `Superseded by` — changed (`proposed — requires operator sign-off` →
  `superseded-by DR-0045`; back-pointer set to this record, the only edit
  ever made to that record).
