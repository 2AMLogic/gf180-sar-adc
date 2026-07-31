# spec/decision-records/ — decision-record format

This directory holds the block's decision records. A decision record fixes
one spec change or one architecture choice, with the reasoning that produced
it, so downstream design work can lock to it without re-litigating it.

Records are **append-only**: once a record is ratified it is never rewritten
or deleted. A reversal — even one that corrects a mistake — is written as a
new record that supersedes the old one, rather than overwriting it in place.
This mirrors the append-only rule for `sim/` evidence records (`sim/README.md`)
on purpose: `spec/` records why we decided, `sim/` records what we measured,
and both are read as one continuous, non-rewritable trail.

Start from [`TEMPLATE.md`](TEMPLATE.md).

## Provenance: ported from gf180-bandgap

Per CLAUDE.md's bootstrap rule, this convention is **adapted from
`2AMLogic/gf180-bandgap`'s `spec/decision-records/TEMPLATE.md`** rather than
designed from scratch. Sections, tone, and the one-page discipline are kept
identical to upstream. Two deliberate divergences:

1. **A `Spec lines affected` field was added** (no upstream equivalent). It
   uses the same `spec/<file>.md#<anchor>` form that `sim/` evidence records
   use in their **Claim** field, so a decision and the evidence
   substantiating it point at the same anchor.
2. **Naming and numbering are pinned to one convention** (below). Upstream's
   template prescribes `DR-NNN-<slug>.md` while its records use a bare
   `NNNN-<slug>.md` prefix, and its two records both landed at number 0001.
   This repo picks one form and defines "next unused" concretely so that
   collision cannot recur here.

Worked examples stay upstream — this directory holds the generic template,
and this repo's own records once they are written.

## When a record is required

Write a record for:

- **Any change to the ratified spec** — a new parameter, a changed value, a
  relaxed or tightened limit, a removed row. CLAUDE.md is explicit here:
  spec changes go through `spec/` with a decision record, and agents do not
  relax the ratified spec to make results pass. A failing result is grounds
  for a decision record proposing the change, never for a silent edit.
- **Any architecture choice that constrains downstream design** — e.g. CDAC
  switching scheme, comparator topology, sync vs. async logic, input
  sampling/bootstrapping approach, mixed-signal simulation strategy. If
  another issue would have to re-derive the choice to proceed, record it.
- **Any scope decision** — what is in or out of this wave (device flavor,
  interface scope, clocking source, ...), including decisions to defer.

A record is **not** required for:

- Implementation detail already fully determined by a ratified record.
- Simulation results — those are `sim/` evidence records
  (`sim/README.md`), not decision records. A decision record may *cite* a
  `sim/` `<record-id>` as the evidence that forced it.

## File naming

```
spec/decision-records/DR-NNNN-<slug>.md
```

- **`DR-` prefix, always.** The same `DR-NNNN` token is used in the
  filename, in the document's `# DR-NNNN: <title>` heading, and in every
  cross-reference (`Status: superseded-by DR-0007`, `Supersedes: DR-0003`),
  so one token identifies a record everywhere it appears. This is the form
  upstream's template prescribes; upstream's bare-number filenames are not
  followed here.
- **`NNNN` is four digits, zero-padded** — `DR-0001`, `DR-0042`,
  `DR-0117`. Four digits everywhere, including in the heading and in
  cross-references. Never `DR-1`, never `DR-001`.
- **`<slug>`** is short and kebab-case, describing the decision, not the
  issue: `DR-0001-device-flavor-scope.md`,
  `DR-0002-cdac-switching-scheme.md`.

## Numbering

**`NNNN` is the next unused number**, defined concretely as: strictly
greater than every number already present in this directory on `main`, and
not already claimed by an open PR.

- **Superseded records still count.** Numbers are never reused, recycled, or
  reclaimed — a superseded record keeps its number forever, and the next
  record takes a fresh one. "Unused" means never used, not "not currently
  in force".
- **Check `main`, not just your worktree**, and check open PRs — a record
  added on a branch you have not merged has still claimed its number:

  ```bash
  git fetch origin main
  git ls-tree -r --name-only origin/main spec/decision-records/ \
    | grep -oE 'DR-[0-9]{4}' | sort -u | tail -1     # highest number on main
  gh pr list --state open --search 'DR- in:title'    # numbers claimed in flight
  ```

  If neither returns anything, the first record is `DR-0001`.
- **If two records collide anyway** (two branches picked the same number
  concurrently), the later-merged one is **renumbered before merge** —
  filename, heading, and every cross-reference to it. Two records must never
  share a number, even when one of them is superseded.

## One decision per record, one page

- **One decision per record.** If a record contains the word "and" between
  two independent choices, it is two records. Splitting keeps supersession
  precise: superseding one choice must not drag an unrelated, still-valid
  choice along with it.
- **One page.** Context, Decision, Alternatives considered, Consequences,
  and Spec lines affected, all readable at once. Long supporting analysis
  (survey material, derivations, simulation output) belongs in the issue or
  in `sim/`, cited from the record's **Related** field — not inlined into
  it.

## Superseding a ratified record

A ratified record is never rewritten or deleted. To reverse or revise one:

1. **Write a new record** with the next unused `DR-NNNN`, its own Context /
   Decision / Alternatives / Consequences / Spec lines affected. Its
   **Supersedes** field names the old record: `Supersedes: DR-0003`.
2. **Add the back-pointer to the old record.** Set the old record's
   **Status** to `superseded-by DR-0009` and fill its **Superseded by**
   field. This is the *only* edit ever made to a ratified record — its
   Context, Decision, Alternatives considered, Consequences, and Spec lines
   affected sections are left exactly as ratified, wrong conclusions and
   all. The narrow carve-out exists because a decision record states what is
   currently in force: a reader landing on an obsolete record must be able
   to see, in that record, that it no longer governs. (A `sim/` evidence
   record needs no such carve-out — a timestamped measurement stays true
   regardless of what supersedes it, so `sim/` records are never touched at
   all.)
3. **Both directions must resolve.** After the change, the old record points
   forward via `Status` / `Superseded by`, and the new record points back via
   `Supersedes`. A one-way link is a broken record.

The **Supersedes** field means "replaces this record's decision on the same
question", matching the same field's meaning in `sim/` evidence records: a
record that decides a *different* question about the same block is a new,
independent decision and leaves `Supersedes` empty, even when the two
records are closely related.

A record still in `proposed` status has not been ratified and may simply be
edited or withdrawn in its PR — supersession applies from ratification
onward.
