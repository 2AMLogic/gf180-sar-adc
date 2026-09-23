# DR-0032: implant layers stay undrawn in `adc_block.gds` until a well tap exists to mark

- **Status**: superseded-by DR-0035
- **Date**: 2026-09-21
- **Decided by**: Builder agent, issue #340
- **Supersedes**: none — first record for this decision
- **Superseded by**: [DR-0035](DR-0035-well-taps-and-tie-straps.md) (issue
  #356, 2026-09-23) — by this record's own first revisit trigger, *well taps
  are drawn*. Every one of the 25 wells now carries an `Nplus`-marked,
  contacted n+ tap routed to `vdd`, and both substrate-tie rings are closed,
  `Pplus`-marked and strapped to `vss`, so the implants this record deferred
  now have tap geometry to mark and `tap_requires: ["32/0"]` is a meaningful
  declaration. The second revisit trigger (*the curated deck gains implant
  rules*) has **not** fired; DR-0035 draws implants on the taps and ties
  only, and says so.
- **Related**: #340, #330 (the `klt erc` bring-up this answers a residual
  gap in), `layout/erc/well-tap-audit.json` +
  `layout/erc/well_tap_audit.py` (the measurement this record rests on),
  `layout/erc/records/20260921-105407-3922180.md` (the committed `klt erc`
  run), `layout/erc/README.md`, klayout-tools#2234 (the tool gap filed
  upstream), klayout-tools#555 (the extraction deck's missing
  `nwell`↔`contact` connection)

## Context

T1 item 11 (*power delivery, structural*) has two halves. `klt erc` answers
the first — `vdd` and `vss` each resolve to exactly one electrical island —
and the committed run says so. The second half, `erc.missing_tie`, is **not
computed**: the supply spec declares no `ties[]`, because `ADC_BLOCK` draws
no implant layers (`Pplus` 31/0 and `Nplus` 32/0 carry zero shapes), so the
real gf180mcu tap boolean `COMP ∩ Nplus` has nothing to intersect. Issue
#340 asks the obvious next question: should the implants simply be drawn?

Answering it needed a fact nobody had measured. `layout/erc/well_tap_audit.py`
measures it directly from the drawn layers, with no implant marking, no
extraction deck and no net model involved — a well tap is diffusion inside a
well that is not part of a transistor, and that is a pure geometry question:

| Measurement | Value |
|---|---|
| `Nwell` 21/0 islands | 25 (9614.820 µm²) |
| `COMP` 22/0 polygons interacting with an `Nwell` | 160 |
| …of those, polygons **not** also interacting with `Poly2` 30/0 | **0** |
| `COMP` polygons outside every `Nwell` and clear of `Poly2` | 2 (2874.872 µm²) |
| `Metal1_Label` 34/10 texts landing on either of those two | **0** |
| `Metal1` bars per ring / pairs that touch each other | 4 / **0** |

Read in order, that says: **every diffusion region inside every well in this
block is transistor source/drain/channel. `ADC_BLOCK` draws no n-well tap at
all.** The two polygons that *are* tap structures are the substrate-tie guard
rings `lib/geometry.py:draw_guard_ring` draws around the analog core and the
reserved digital region — contacted `Comp`/`Contact`/`Metal1` rings, DRC-clean,
and strapped to nothing: no label, no route, and (a second finding) four
mutually disjoint `Metal1` bars, so the Metal1 ring is open at all four
corners and strapping one bar would not strap the ring.

That reframes the question this record has to decide. Drawing implants
faithfully would mark the PMOS source/drain inside each well as `Pplus`, and
would draw `Nplus` inside a well only where a tap exists — nowhere. So
`COMP ∩ Nplus` inside the wells would be **empty after the change exactly as
it is empty before it**, and the committed `tie-narrowed` control would go on
reporting the same 25 `erc.missing_tie` findings, one per well, byte for byte.

## Decision

**Do not draw implant layers (`Pplus` 31/0, `Nplus` 32/0) in
`adc_block.gds` in this pass.** The geometry is unchanged by this record;
`layout/adc-top/adc_block.gds` keeps sha256 `b4cf6ad7…` and every DRC, LVS,
ERC and signoff pin that cites it stands.

`layout/erc/adc_block.supply-spec.json` accordingly keeps its `ties[]`
omission, and `erc.missing_tie` stays formally **not computed** — but it is
no longer *unanswered*. The answer is recorded, as geometry, in
`layout/erc/well-tap-audit.json`, re-derived on every run of
`layout/erc/well_tap_audit.py` and guarded on this repo's headless CI path by
`sim/tests/test_well_tap_audit.py`: **this block's 25 n-wells are untapped,
and its two substrate-tie rings reach no supply.** Item 11's tie half is
therefore *failed*, on evidence, rather than uncomputed for want of a
declarable tap layer.

The decision is scoped, and the scope is the point: it is *not* a ruling that
gf180mcu implants are optional. A mask-level database for this process needs
them, and nothing here should be read as saying otherwise. It is a ruling
about **ordering** — implants mark tap geometry, and the tap geometry they
would mark does not exist yet, so drawing them first buys a re-baseline and
no evidence. Revisit this record when either trigger fires:

1. **Well taps are drawn** (the layout work tracked separately — see
   Consequences). At that point `tap_requires: ["32/0"]` becomes a
   meaningful declaration and drawing the implants is what makes it
   answerable; this record should be superseded, not worked around.
2. **The curated deck gains implant rules.** `klayout_tools.decks.get_deck
   ("gf180mcu")` carries 46 rules and **not one of them names 31/0 or 32/0**
   — no width, no spacing, no `COMP` enclosure, no `Pplus`/`Nplus` overlap
   prohibition. Checked on two builds on 2026-09-21, `0.4.0+g31a3e3c` and
   the ERC pin `0.5.0+g67d617f`: 46 rules, zero implant rules, both. Until
   that changes, drawn implants are geometry this repo has no check for, in
   an artifact whose whole warrant is that every claim on it has one.

## Alternatives considered

- **Draw the implants now, and accept 25 true `erc.missing_tie` findings
  instead of 25 uninformative ones** — not chosen, and this was the close
  call. It buys a *re-labelling* of an existing control's output, not a new
  number: the count is 25 before and 25 after, because the `Nplus` inside the
  wells that the check intersects on would be empty either way (there is no
  tap to mark). The same re-labelling is obtained at zero geometric cost by
  the audit this record cites, which establishes the underlying fact
  *directly* and — unlike the implant-marked control — can distinguish a
  tapped well from an untapped one. Set against that: drawing implants moves
  `adc_block.gds`, which re-mints the DRC report, the LVS report, the `klt
  erc` report and record, `layout/erc/cases.json`'s `layout_sha256`,
  `signoff/freshness.json` and the signoff manifest — while adding thousands
  of shapes on two layers **no rule in the pinned deck checks**. Unverifiable
  geometry, in exchange for a conclusion already in hand by other means.
- **Draw implants *and* the missing well taps in one change, so item 11's
  tie half can go clean** — not chosen *here*, and not rejected either: it is
  the right end state, and it is a layout change, not a marking change. A tap
  inside a well needs area inside that well (the wells are drawn at
  `NWELL_MARGIN` = 0.5 µm around the PMOS active they cover, with no room
  reserved), a contact, and a route to `vdd` for each of 25 islands; the
  analog and digital substrate rings need the same treatment to `vss`, plus a
  fix for their corner-open `Metal1`. That re-does placement, re-runs DRC and
  LVS, and reopens the DR-0017 / DR-0024 area budget. Bundling it into a
  record about whether to *mark* implants would hide a large, independently
  reviewable layout change inside a labelling decision. Tracked as its own
  issue instead.
- **Declare `ties[]` with the bare `tap_layer: "22/0"` form and take the
  `clean_partial` verdict** — not chosen: unchanged from #330's reasoning,
  and the audit strengthens it. `klt erc` classifies a bare `COMP` tap layer
  as degenerate (klayout-tools#2199) precisely because it cannot tell a tap
  from a source/drain contact — and this block is the case that shows why
  that refusal is right: *every* `COMP` polygon in all 25 wells is a
  source/drain contact, so a tool that accepted the declaration would report
  25 tapped wells where there are none. The committed
  `controls/adc_block.tie-bare.known-gap.json` keeps reproducing that skip.
- **Silently leave "not computed" as it stands and close #340 as
  unactionable** — not chosen: "not computed" reads to a future grader as an
  oversight or a tool limitation, and it is neither. The tie half of item 11
  fails on this block for a concrete, measurable layout reason, and a repo
  whose product is verification has to say which.

## Consequences

- **Item 11's tie half is now failed-on-evidence rather than uncomputed.**
  `layout/erc/README.md` and `signoff/README.md` say so, and both point at
  the audit. A grader can no longer read the zero `erc.missing_tie` count as
  ambiguous: it is an uncomputed rule sitting beside a committed measurement
  that answers the same question in the negative.
- **The `klt erc` evidence trail gains a correction.** #330's record, spec
  and README described the `tie-narrowed` control's 25 findings as "false".
  They are not false — they are *unfounded*, produced by a check that would
  emit them regardless of the layout, and their verdict happens to be
  correct. The committed record
  `layout/erc/records/20260921-105407-3922180.md` is append-only and stays
  exactly as minted; the prose in the specs, `cases.json` and the README is
  corrected and the reports re-minted under the same pinned build, which is
  what `run_erc.py`'s spec-hash check exists to force.
- **Bad consequence, stated plainly**: `adc_block.gds` remains a database
  that could not be taped out. Implants are not optional on this process, and
  deferring them means the gap between this stream and a mask set stays
  larger than the DRC-clean status suggests — a reader who sees "DRC clean"
  and infers "manufacturable" is wrong, and this record is where that is
  written down. The deferral is defensible only because the block is also not
  tapeout-ready for the reason that dominates it: **no well in it is tied**.
  Fixing the marking before the thing it marks would put the cosmetics in
  front of the defect.
- **A second bad consequence**: nothing forces the trigger conditions above
  to be noticed. `sim/tests/test_well_tap_audit.py` pins `well_tap_candidates
  == 0` by hand, so the day a well tap is drawn the test fails and names this
  record — that is the mechanism, and it is deliberately a hard-coded number
  rather than a `--regen`-able one.
- **Follow-on layout work is tracked separately**: drawing 25 n-well taps
  strapped to `vdd`, strapping both substrate-tie rings to `vss` (closing
  their corner-open `Metal1` first), and drawing the implants that then
  become meaningful. `layout/erc/README.md`'s "Real findings" section carries
  the pointer; that work supersedes this record when it lands.
- **One unrelated observation recorded rather than acted on**: each guard
  ring's contacts are drawn as four long bars (0.468 µm × up to 596.698 µm)
  rather than arrays of 0.22 µm squares. They pass the curated deck's
  `contact.width.1`, whose own description calls itself an approximation of
  gf180mcu's CO.1 *exact* min/max size rule. Recorded in
  `well-tap-audit.json`; it belongs to the same follow-on layout work, not to
  this record.

## Spec lines affected

- None — this is a layout-geometry and evidence-scope decision. It changes no
  target parameter or row in `spec/`, and deliberately leaves
  `layout/adc-top/adc_block.gds` byte-identical, so every spec-facing
  citation that rests on its sha256 is untouched.
