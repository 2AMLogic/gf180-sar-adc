# DR-0000: <short title>

<!--
Copy this file to spec/decision-records/DR-NNNN-<slug>.md and fill it in.

- NNNN is the next unused four-digit number (see README.md, "Numbering":
  strictly greater than every number already used in this directory,
  including superseded records, and not claimed by an open PR). Numbers are
  never reused.
- One decision per record; keep it to one page.
- A decision record is required for every spec change and every architecture
  choice that constrains downstream design (see CLAUDE.md and README.md,
  "When a record is required").
- A ratified record is never rewritten or deleted — supersede it with a new
  record (see README.md, "Superseding a ratified record"). The only edit
  ever made to a ratified record is adding its `Superseded by` back-pointer.

Delete this comment when filling the template in.
-->

- **Status**: proposed | ratified | superseded-by DR-NNNN
- **Date**: YYYY-MM-DD
- **Decided by**: <name / role / agent + issue number>
- **Supersedes**: DR-NNNN (or: none — first record for this decision)
- **Superseded by**: (none while this record stands; filled in when a later
  record replaces it — this is the one field ever edited after ratification)
- **Related**: <issue numbers, prior records, `sim/` record IDs>

## Context

What forced this decision? One short paragraph: the constraint, the
measurement, or the conflict that made the current spec or the current
undecided state inadequate. Link to the issue, to the simulation evidence in
`sim/` (by `<record-id>`), or to the prior record this one revises.

## Decision

The decision, stated as a change to the spec — the parameter and its new
value, or the approach now ratified. Be specific enough that design work can
lock to it without further interpretation.

## Alternatives considered

- **<alternative>** — why it was not chosen.
- **<alternative>** — why it was not chosen.

State a real why-not for each, not just a preference. An alternative listed
without a reason it lost is not a considered alternative.

## Consequences

What follows from this: what becomes possible, what becomes harder, which
testbenches or corner sets change, what work is invalidated or must be
re-run. **Include the bad consequences, not just the good ones** — a record
with only upside is not finished.

## Spec lines affected

Every spec location this record changes, one per line, in the same
`spec/<file>.md#<anchor>` form that `sim/` evidence records use in their
**Claim** field, so decisions and evidence point at the same anchors:

- `spec/<file>.md#<anchor>` — <parameter / row name> — new | changed
  (`<old>` -> `<new>`) | clarified (no value change) | removed.

If no ratified spec file exists yet (spec ratification is #1), name the
target parameter/row and mark it `pending #1` instead of inventing an
anchor — for example:

- `spec/<file>.md#<anchor>` (pending #1) — <parameter / row name> — new.

If this record genuinely changes no spec line (a scope or process decision),
write `none — <why>`; never leave this field blank.
