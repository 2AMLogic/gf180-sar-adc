# Comp-table format

The exact table schema `SKILL.md`'s research procedure fills in, and the
schema the comp library's own entries use, so a market-key review and a
comp-library entry are always literally the same table shape — one can be
pasted into the other with no reformatting.

In the installed canary variant, that library is the `comps/` directory
bundled alongside this file (a generated, public-sources-only excerpt of the
upstream one).

## The table

| # | Row | Our target | Comp source | Comp value | Verdict | Notes |
|---|---|---|---|---|---|---|

- **#** — the spec row's own number, matching the target repo's own spec
  table/decision-record numbering where one exists (e.g. `gf180-tmds-tx`'s
  `spec/decisions/0013-operating-conditions.md` numbers its verifiable rows
  1–11; reuse that numbering rather than inventing a parallel one).
- **Row** — the parameter name, in the target spec's own words.
- **Our target** — the ratified (or proposed, if this is a PR under review
  rather than an already-ratified spec) value, with its citation back to the
  decision record that sets it.
- **Comp source** — `<Vendor> <part number>, <datasheet doc ID if named>` or
  `<standard name>, <section>` for a standards citation. One comp source per
  table row is the floor; prefer two independent sources per row so the
  table is not a single point of failure (see `SKILL.md` Step 2.2). When two
  sources are used for one spec row, add a second table row directly below
  the first repeating the `#`/`Row`/`Our target` columns.
- **Comp value** — the comp's stated value for the equivalent parameter, with
  enough of the comp's own test condition quoted (supply, temperature,
  frequency, load) that a reader can judge comparability rather than trust
  it. **Do not strip the test condition to make two numbers look more
  comparable than they are** — if the comparison is apples-to-oranges (e.g.
  different measurement bandwidth, different rate), say so in Notes rather
  than silently presenting bare numbers side by side.
- **Verdict** — one of the three tokens from `rubric.md`
  (`competitive` / `adequate-for-catalog` / `uncompetitive`), or `no-comp-found`
  if Step 2.4 applied.
- **Notes** — anything a reader needs to trust the comparison: measurement
  basis mismatches, whether the comp part is still in production or only
  historically relevant, an explicit flag if the comp itself looks weaker
  than the standard it claims to meet.

## Sourcing rules

1. **Primary sources only.** A vendor's own datasheet page or PDF, a
   standards body's own published document, a distributor's own listed
   price (Digi-Key/Mouser/LCSC product pages) — never a third-party
   aggregator's restated numbers (`alldatasheet.com`-style mirrors, forum
   posts quoting a spec from memory) unless the primary source is
   confirmed unreachable, in which case say so and flag the number
   UNVERIFIED rather than presenting it with primary-source confidence.

2. **Every fetched source gets a `Sources` table row** (URL, date fetched,
   what it establishes) at the bottom of the review/comp-file, per
   `SKILL.md`'s "Output format" — not just cited inline in prose.
3. **Date every fetch.** Datasheets get revised; a comp value is only as
   good as the revision it was read from. Cite the datasheet's own document
   ID/revision letter when the datasheet states one (e.g. `SLDS145D`), not
   just "TI's website."
4. **A raw capture belongs in a sibling `datasheets/` directory** next to
   whichever file cites it, so a broken link later doesn't strand the
   review's evidence.

5. **Public pricing is optional, not required**, for a spec-row comp table —
   most spec rows are electrical/interoperability parameters, not price
   points. Include a price row only when the block's own spec states a cost
   target, or when a `Notes` entry needs it to explain why an otherwise
   uncompetitive spec might still be catalog-adequate (a part that trades a
   weaker row for a materially lower price is a legitimate market argument,
   but it must be made with a cited price, not asserted).

## Row classification table (companion, from `SKILL.md` Step 1)

| # | Row | In scope? | Why |
|---|---|---|---|

Same numbering as the comp table. `Why` for an out-of-scope row should name
which kind of internal-implementation choice it is (process/PDK variant,
device family, RTL structure, verification methodology) — enough that a
reader can confirm the exclusion is principled, not a row the review simply
skipped.
