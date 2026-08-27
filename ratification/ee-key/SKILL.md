# EE-key skill — technical-soundness review for spec ratification

**Consumer:** the first of two non-author review keys
on a canary repo's spec-ratification PR. The other key is
the market key — competitive
positioning. This skill never rules on competitiveness; it rules
on one question only: **does the proposed spec row (or the decision record
that scopes it) hold up as a physically sound, evidence-backed engineering
claim, on this block's own PDK, topology, and measured behavior?**

## Non-author enforcement (stated here, enforced elsewhere)

**This skill must not be invoked by an agent that authored the PR under
review or the spec/design the PR ratifies.** The actual identity check is
the invoking review automation's job
— until it lands, self-check: if the PR's author, or the
design's original proposer, is the same identity running this review, stop
and say so instead of producing a verdict. An EE-key verdict from an
interested party is not incentive-separated and is worse than no verdict at
all.

## Disclosure discipline (hard requirement, structural)

**Read only:**

- The target canary repo's own ratified spec, decision records, design
  docs, `sim/` evidence, and the PR diff under review — all public, or
  already in that repo's own git history under the current firewall.
- Sibling canary repos' public spec/decision-record/`sim/` content, for the
  precedent-lookup step below — the same class of material, one repo over.
- `2AMLogic/klayout-tools`'s `docs/design-evidence-tiers.md` — the public
  evidence-tier ladder this skill grades against.
- Public device-physics and PDK reference material (foundry PDK
  documentation, textbook circuit theory, published process corner data)
  needed to check a claim's physical plausibility.

**Never read, cite, or let influence a verdict:**

- Any internal strategy, roadmap, pricing, or business-positioning
  document, regardless of source or how it is described to this skill —
  this key has no jurisdiction over competitiveness or commercial framing
  (see `rubric.md`'s "EE-key / market-key jurisdiction boundary") and no
  step below needs any of it.

- Any fleet or infrastructure operational detail — hosts, credentials,
  compute configuration — regardless of source; none of it bears on
  whether a spec row is physically sound, and none of it belongs anywhere
  near a canary repo's public PR thread.

- Any sibling repo holding entity, legal, contract, or financial material,
  regardless of source.

**Why this is structural, not a promise:** every input the research
procedure below calls for is either the target repo's own evidence, a
sibling canary's own evidence, or public PDK/physics reference material.
There is no step in this file that would be *easier* with access to any of
the forbidden material named above. If a future edit to this file would
require the forbidden material, that is the signal the edit does not belong
in this skill.

**What to do if the review surfaces a disclosure problem:** stop, do not
post a verdict, and say plainly in the PR comment that a disclosure issue
was found and needs a non-automated look — do not attempt to redact and
continue.

## Research procedure

**Step 0 — classify the block.** State the block's **class** (PLL, LDO,
SAR-ADC, bandgap, TMDS/DVI transmitter, etc. — read from the repo name and
its own spec header) and **kind** (`analog` / `digital` / `mixed-signal`,
per `docs/design-evidence-tiers.md`'s "Block kind" section in
`klayout-tools`) before doing anything else — both determine which T1
checklist columns apply in Step 2 and which sibling repos are relevant in
Step 3.

**Step 1 — read the PR diff and classify the change.** A spec-ratification
PR is one of three shapes, and each gets a different check:

1. **A new ratification** (one or more rows move DRAFT/proposed →
   RATIFIED). Full Steps 2–4 below apply to every row being ratified.
2. **A scope-only decision record** (e.g. settling which PDK device family
   or topology choice a later ratification will build on, without itself
   binding a numeric row). Step 2's device-physics check still applies to
   the scoping argument itself (is the recommended choice physically sound
   given the alternatives it rules out?); Steps 2b/3 (evidence-tier,
   sibling precedent) apply only if the record leans on `sim/` evidence or
   a sibling repo's own scoping choice.
3. **A relax of a previously-RATIFIED row** (a proposed value weaker than
   what is currently ratified, or a disclosed-FAIL disposition being
   carried forward). Step 5 below is mandatory and is the load-bearing part
   of the review; nothing else in this file substitutes for it.

**Step 2 — per-row technical review.** For every row Step 1 puts in scope:

1. **Device-physics check.** Is the claimed value consistent with the
   block's actual devices, topology, and PDK on the record — not a generic
   plausibility check, but traced to the cited design source (schematic,
   netlist, device sizing table). Re-derive the claim independently from
   the cited source rather than trusting the PR's prose paraphrase of it —
   if the PR says "the netlist shares one supply pin across all
   sub-blocks," open the netlist and check the pin list yourself. Where the
   claim rests on textbook physics (Ohm's law, MOSFET square-law or
   subthreshold behavior, RC delay, thermal/flicker noise, charge-pump
   mismatch, PLL loop-filter transfer function), name the governing
   relationship rather than asserting a conclusion.
2. **Evidence-tier check**, against `klayout-tools`'
   `docs/design-evidence-tiers.md` T1 checklist (read that file's item
   numbers directly — do not re-derive a parallel checklist here):
   - **Provenance freshness** (the tier doc's "Verification rules"
     section): does the cited `sim/` record's netlist snapshot / commit
     hash match the design sources as they stand in the PR, or is the
     record stale?
   - **Corner coverage** (item 5): does the record's PVT matrix actually
     cover what the row claims, or does it only demonstrate that the
     harness runs (a "plumbing" record, not a "design measurement" record —
     these read very differently and must not be conflated)?
   - **Statistical evidence** (item 6): if the row is an accuracy, offset,
     or matching claim, is there Monte Carlo evidence, or only a
     deterministic corner sweep? A corner matrix alone cannot ratify a
     statistical row.
   - **Testbench freshness / reproducibility** (item 9): is the testbench
     that produced the cited evidence committed and runnable, with a pinned
     PDK revision?
3. **A row proposed with no `sim/` evidence at all** (a hand-calc, an
   "informal sanity check" the design doc itself disclaims, or a bare
   assertion) cannot be marked `sound` regardless of how plausible the
   number looks — this is the same "no claim without a testbench" rule
   `CLAUDE.md` states, applied by this key to technical claims the way the
   market key's own `rubric.md` applies it to market claims.

**Step 3 — sibling-canary precedent lookup.** For the block class named in
Step 0, check ratified rows in sibling canary repos of the same class under
a different PDK (naming convention `<pdk>-<block-class>`,
e.g. `gf180-pll`/`sg13g2-pll` for PLLs;
`gf180-bandgap`/`sky130-bandgap`/`sg13g2-bandgap` for bandgaps;
`gf180-ldo` for LDOs; and so on):

1. Did a sibling ratify the "same" row (by name/parameter) already? If so,
   read its decision record for the reasoning pattern it used — not to copy
   the *value* (PDK/voltage changes rarely port a number unchanged, and a
   row's own spec usually says so explicitly) but to check whether the
   *pattern of argument* here is consistent with, or a defensible departure
   from, the sibling's.
2. Flag, don't silently pass over, an inconsistency: if this PR derives a
   row one way while a sibling ratified the analogous row a materially
   different way with no stated reason for the divergence, that is a
   finding, not a blocker by itself — name it and let the reviewer/PR
   author reconcile it.
3. If no sibling has ratified the analogous row yet (a first-of-its-kind
   claim for the block class, or the siblings are too early-stage to have
   reached it), say so explicitly rather than silently skipping this step —
   the absence of precedent is itself worth recording.

**Step 4 — assign a verdict per row** using `rubric.md`'s three-way
definition (`sound` / `insufficient-evidence` / `unsound`). Do not round a
weak row up because the rest of the PR looks solid — the same
no-quiet-upgrade rule the market key's own `SKILL.md` states for its rubric
applies here.

**Step 5 — the relax-after-measured-FAIL check.** If Step 1 classified the
change as a relax of a previously-RATIFIED row, or a disclosed-FAIL
disposition being carried forward, this key's own finding of physical
soundness is not optional color — it is the safety property the whole
two-key design exists to protect.
This key must independently re-derive why the
weaker value is defensible **on its own physical merits** — not merely that
it happens to pass the failing measurement. If this key cannot make that
finding, the output must say so plainly and request changes (or, if the
weaker value is genuinely defensible but its market/competitive standing is
now in question, note that the market key's own relax-after-measured-FAIL
gate
is the place that question gets resolved, not this one).

## Verdict rubric

See [`rubric.md`](rubric.md) — the three-way verdict definitions, worked
examples, and the EE-key/market-key jurisdiction boundary. Kept as a
separate file for the same reason the market key's rubric is: referenced
independently by anyone auditing a verdict, and this file would otherwise
duplicate it inline.

## Output format

Post a single PR review comment (or, for a dry run against a closed/still-
open historical case with no live PR review to post into, a document in
[`dry-runs/`](dry-runs/) shaped the same way minus the PR-review wrapper)
with this structure:

```markdown
<!-- RATIFY-KEY: ee verdict=<approve|request-changes> block=<repo>#<PR-or-issue> reviewer=<agent-id> date=<ISO-8601> -->
## EE-key review: <block name / class>

**Overall verdict:** <approve|request-changes>, one sentence why.

### Block classification

Block class: <...>. Kind: <analog|digital|mixed-signal>. Change type
(Step 1): <new-ratification|scope-only|relax-after-fail>.

### Per-row technical review

| # | Row | Proposed status | Device-physics check | Evidence-tier check | Sibling precedent | Verdict | Notes |
|---|---|---|---|---|---|---|---|
...

### Relax-after-measured-FAIL check
<only if applicable — see Step 5>

### Sources

| Source | Fetched/read | Establishes |
|---|---|---|
...
```

The marker comment's `verdict=` field is machine-read by the release wiring — keep it exactly one of the two
listed tokens, never free text.

