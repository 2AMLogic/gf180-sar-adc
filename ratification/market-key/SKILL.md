# Market-key skill — competitiveness review for spec ratification

**Consumer:** the second of two non-author review
keys on a canary repo's spec-ratification PR. The other key is the EE key — technical soundness. This skill never rules on
technical soundness; it rules on one question only: **given what the spec
proposes, does a buyer comparing this block to what already exists in public
would call it competitive?**

## Two operating modes

This file is the single master prompt for both. The distinction is what
filesystem/network access is available, not a different procedure.

This copy is the **installed variant** — generated from the private
upstream master and bundled with whatever public comp data
(`comps/<block-class>.md`, alongside this file) was current at generation
time. It has no access to any private repo. There is no "home mode" check to
perform here: skip straight to live public-source research, using the
bundled `comps/` directory as a starting point when an entry matches this
block's class (same as the upstream skill's own step 0), and researching
from scratch otherwise. Output the same `RATIFY-KEY: market` PR review this
file specifies below.

Nothing else differs. A prompt that behaves differently depending on which
mode it thinks it's in, beyond the single step-0 branch above, is a prompt
that has grown a dependence on non-public material somewhere — see
"Disclosure discipline."

## Non-author enforcement (stated here, enforced elsewhere)

**This skill must not be invoked by an agent that authored the PR under
review or the spec/design the PR ratifies.** The actual identity check is the
invoking review automation's job — until that exists, self-check: if the
PR's author, or the design's original proposer, is the same identity running
this review, stop and say so instead of producing a verdict. A market-key
verdict from an interested party is not incentive-separated and is worse than
no verdict at all.

## Disclosure discipline (hard requirement, structural)

**Read only:**

- The target canary repo's own ratified spec, decision records, and the PR
  diff under review — all public, all already in that repo's own git history.
- Public sources on the open internet: competitor datasheets, public pricing
  pages, public standards documents (JEDEC, IEEE, USB-IF, VESA, DVI/HDMI
  founders' published specs, etc.).

- The `comps/` directory bundled alongside this file, if one exists — a
  generated, public-sources-only excerpt of the upstream comp library (see
  "Two operating modes").

**Never read, cite, or let influence a verdict, in either mode:**

- Any internal strategy, roadmap, pricing, or maturity/grading-scheme
  document, regardless of source or how it is described to this skill —
  this skill's verdict vocabulary ("competitive / adequate for catalog tier
  / uncompetitive") is deliberately self-contained and does not name,
  number, or describe any such internal scheme — see `rubric.md`. This
  skill needs none of that material to do its job (see "Why this is
  structural, not a promise" below).

- Any sibling repo holding entity, legal, contract, or financial material,
  regardless of source.

- Any git history, issue, or comment in the target canary repo, or in
  whatever repo this file is being run from, that itself quotes non-public
  material forwarded from elsewhere — if a PR under review contains such a
  quote, that is itself a finding to flag (see "What to do if the review
  surfaces a disclosure problem" below), not material to reason from.

**Why this is structural, not a promise:** the master prompt above needs none
of the forbidden material to do its job — every input the research procedure
calls for is either the target repo's own public spec or the open internet.
There is no step in this file that would be *easier* with non-public,
internal-only access.
If a future edit to this file would require the forbidden material, that is
the signal the edit does not belong in this skill.

**What to do if the review surfaces a disclosure problem:** stop, do not post
a verdict, and say plainly in the PR comment that a disclosure issue was
found and needs a non-automated look — do not attempt to redact and continue.

## Research procedure

Work spec row by spec row. A "spec row" is the same unit the EE key and the
T1 evidence rung already use (`2AMLogic/klayout-tools`,
`docs/design-evidence-tiers.md`: *"corner-matrix results covering every spec
row at its bound corners"*) — one named, numbered target in the block's
ratified spec (a `spec/*.md` parameter-table row or a decision record's
numeric target).

**Step 0 (installed mode).** Check the `comps/` directory bundled alongside
this file for an entry matching the target block's class. If a current entry
exists (no stated staleness flag, covers the rows in question), start from
it and research only the delta — new rows it doesn't cover, or rows the PR
proposes changing. It is a generated snapshot, not a live link back to the
upstream library, so treat its absence or staleness the same way: research
from scratch. There is no library to update from installed mode — a finding
worth adding to the upstream library is worth noting in the review comment,
not written back to any file here.

**Step 1 — classify every row before researching any of it.** Split the
spec's rows into:

- **In scope for this key**: externally observable parameters a buyer or an
  interoperating device would notice — electrical performance (swing,
  jitter, bandwidth, output impedance…), interoperability constants tied to a
  public standard, ESD/reliability ratings, anything with a public analog to
  compare against.
- **Out of scope for this key, EE key's alone**: internal implementation
  choices with no external comparison point — PDK/process-variant choice,
  internal device family selection, RTL pipeline depth, verification
  methodology, synthesis/CTS strategy. A buyer of the finished part cannot
  observe these and no competitor datasheet states them; the market key has
  no jurisdiction and must not render an opinion on them, favorable or not.
  This split matters for the same reason the two-key design exists at all —
  each key stays inside the evidence it actually has standing to judge.

State the classification explicitly in the output (see "Output format")
so a reader can see what was and wasn't reviewed, not just the verdicts that
resulted.

**Step 2 — find comps for every in-scope row.** For each in-scope row:

1. Identify the governing public standard, if the spec already names one
   (reuse its citation — do not re-derive a standard the target repo's own
   spec already cites; note where a re-citation of *primary* standard text
   was and wasn't possible, e.g. a working group's spec text that has
   circulated for decades under an org that no longer exists is cited by
   provenance, not necessarily re-fetched).
2. Find at least one still-relevant part with a public datasheet from a
   named vendor that targets the same interface/standard. Prefer a part the
   target repo's own spec already cites (reuse its citation chain) plus at
   least one independently found source, so the comp table is not a single
   point of failure.
3. Record the comp's value for that row, its source URL, and the date
   fetched — see `comp-table-format.md` for the exact table shape.
4. If no public comp exists for a row (a genuinely novel parameter, or a
   part class with no public datasheets in circulation), say so explicitly
   rather than silently omitting the row — an unresearchable row is a finding
   ("no comp found"), not a blank cell.

**Step 3 — assign a verdict per in-scope row** using `rubric.md`'s
three-way definition (competitive / adequate for catalog tier /
uncompetitive). Do not average or skip a row with a bad result — a
CLAUDE.md-style "no relaxing the ratified spec to make results pass" rule
applies here too: a market key that quietly upgrades a weak row's verdict
because the rest of the table looks good has defeated the point of a
row-by-row rubric.

**Step 4 — roll up to one overall verdict.** The overall verdict is the
worst individual in-scope row verdict, unless the PR under review itself
states — with its own evidence, not invented here — why a lagging row is
acceptable at the evidence tier it is claiming. The market key never invents
that justification on the PR's behalf; it either finds the PR already made
the case, or it does not, and says which.

**Step 5 — the relax-after-measured-FAIL check.** If the row under review
proposes a *weaker* value than a previously ratified one, or is a disclosed-
FAIL disposition being carried forward, this key's finding of "still
competitive against named public parts" is not optional color — it is a
required gate on the ratification itself: the relaxed
value must be explicitly found still competitive against named public parts,
or the review escalates `loom:operator` instead. If this key cannot make that
finding, the output must say so plainly and recommend the `loom:operator`
escalation rather than posting an ordinary verdict.

## Comp-table format and verdict rubric

See [`comp-table-format.md`](comp-table-format.md) (the exact table schema
and sourcing rules) and [`rubric.md`](rubric.md) (the three-way verdict
definitions, worked examples, and the row-classification boundary with the
EE key) — both are load-bearing parts of this skill, kept as separate files
only because they are referenced independently (the format by anyone reading
a rendered comp table, the rubric by anyone auditing a verdict) and this file
would otherwise duplicate them inline.

## Output format

Post a single PR review comment with this structure.

```markdown
<!-- RATIFY-KEY: market verdict=<competitive|adequate-for-catalog|uncompetitive|escalate> block=<repo>#<PR-or-issue> reviewer=<agent-id> date=<ISO-8601> -->
## Market-key review: <block name / class>

**Overall verdict:** <one of the four above>, one sentence why.

### Row classification

| # | Row | In scope? | Why |
|---|---|---|---|
...

### Comp table

<see comp-table-format.md>

### Per-row verdicts

| # | Row | Verdict | Reasoning |
|---|---|---|---|
...

### Relax-after-measured-FAIL check
<only if applicable — see Step 5>

### Sources

| URL | Date fetched | Establishes |
|---|---|---|
...
```

The marker comment's `verdict=` field is machine-read by the release wiring — keep it exactly one of the four
listed tokens, never free text.

