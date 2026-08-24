# Verdict rubric

Three tokens, applied per spec row (`SKILL.md` Step 3) and rolled up to one
overall verdict (`SKILL.md` Step 4). A fourth token, `escalate`, is not a
competitiveness verdict at all — it means Step 5's relax-after-measured-FAIL
check could not be satisfied and this key is declining to rule; see that
section of `SKILL.md` rather than this file for what it means.

Deliberately self-contained: nothing below names, numbers, or maps onto any
internal maturity/grading scheme this skill's owner may use privately.
"Catalog" here means "listed for sale in whatever form this program
eventually sells blocks" — a public-safe generic, not a pointer to any
internal scheme.

## `competitive`

The row's target matches or exceeds what the comp table found in current,
still-relevant public comps, **or** matches the governing public standard
exactly where the standard itself is the ceiling a buyer would check against
(e.g. a DVI-class swing target that exactly matches the DVI 1.0 window a
comp part also targets is `competitive` even if no single comp beats it — the
standard itself is the bar, and the row clears it with nothing a
knowledgeable buyer would flag as a gap).

**Worked example**: `gf180-tmds-tx`'s
single-ended output swing target (400–600 mV,
`spec/decisions/0013-operating-conditions.md` row 1) is bit-for-bit the same
window TI's TFP410 DVI transmitter datasheet states
(`V_SWING`, 400–600 mV p-p, SLDS145D §5.5) — both target the same public
standard, and the row matches a still-sold, industry-standard part exactly.
`competitive`.

## `adequate for catalog tier`

The row does not match the strongest public comp found, but clears the
functional/interoperability floor the governing standard or a public
reference design sets, **and** the gap is named explicitly rather than
hidden. A buyer evaluating the block for a non-flagship or evaluation-grade
use would accept it; a buyer who needs best-in-class on that specific row
would not, and the review must say so rather than let the token alone imply
"fine."

This is also the correct verdict for a row whose target is honestly marked
`Proposed`/estimated in the target repo's own spec (not yet independently
verified) when the *proposed number itself*, if achieved, would clear the
floor — the `Proposed` status is a finding about evidence maturity, separate
from whether the target value itself would be competitive; do not conflate
"unverified" with "uncompetitive." State both facts (the value's competitive
standing, and its unverified status) rather than picking one to report.

**Worked example**: `gf180-tmds-tx`'s ESD target (HBM ≥ 2 kV, CDM ≥ 500 V,
`spec/decisions/0011-pad-esd-strategy.md`) meets the JEDEC minimum a lab/
shuttle-run part needs, but TI's TFP410 — a shipping commercial DVI
transmitter — specifies ±4000 V HBM on its DVI pins specifically, double the
target here. The target itself already states its own reasoning honestly
("the standard minimum appropriate for a lab/shuttle-run canary part... not a
commercial-product target"). `adequate-for-catalog`, with the gap to a real
shipping part's rating named, not `competitive`.

## `uncompetitive`

The row falls short of the functional/interoperability floor a public
standard or comparable comp requires — not merely short of best-in-class,
but short of *working* for the interface it claims to serve — **or** no
evidence at all supports the value (a row asserted with no comp, no
standard, and no measurement is `uncompetitive` by default, not
`adequate-for-catalog`; absence of evidence is not evidence of adequacy, and
this key does not extend the benefit of the doubt a fabricated-looking number
does not deserve).

**Worked example** (hypothetical, not found in the `gf180-tmds-tx#9` dry
run): if a spec row claimed a
jitter budget tighter than the standard's own stated total budget with no
supporting measurement and no comp cited, that would be `uncompetitive`
regardless of whether the number sounds impressive — an unsupported claim
that a block beats the standard it targets is a red flag, not a strength,
under CLAUDE.md's "no claim without a testbench" (which this key applies to
market claims the same way the EE key applies it to technical ones).

## Rows with no verdict: `no-comp-found`

Used when Step 2.4 applies — a genuinely novel parameter or a part class
with no public datasheets in circulation. This is not a verdict on the row's
value; it is a statement that this key could not evaluate it and says so
rather than defaulting silently to any of the three tokens above.

## The market-key / EE-key jurisdiction boundary

Restated from `SKILL.md` Step 1 because it is the rubric's own boundary, not
just a research-procedure detail: this key only scores rows an external
buyer or interoperating device could observe. A row stating an internal
implementation choice — which PDK/process variant, which internal device
family, how many pipeline stages an encoder uses, what verification
methodology was applied — gets no verdict from this key under any of the
five tokens above; it is marked out-of-scope in the row-classification table
and left entirely to the EE key. Scoring an out-of-scope row, favorably or
unfavorably, is itself a rubric violation: it lets the market key exercise
judgment over ground the two-key design deliberately reserves for the other
key, defeating the incentive-separation the whole mechanism exists to
protect.

## Overall-verdict roll-up (restated from `SKILL.md` Step 4)

Overall verdict = the worst individual in-scope row verdict
(`uncompetitive` < `adequate-for-catalog` < `competitive`, treating
`no-comp-found` as a gap to flag rather than a score, and `escalate`
overriding all three when Step 5 applies), unless the PR under review
already states — with its own cited evidence — why a lagging row is
acceptable at the evidence tier it claims. This key never invents that
justification; it reports whether the PR made the case.
