# `signoff/` — this block's gap to T1, graded rather than hand-read

**This directory is the verdict of record for "how far is this block from
T1?"** The answer is not prose here; it is
[`gf180-sar-adc.manifest.json`](gf180-sar-adc.manifest.json) graded by `klt
signoff --manifest`, with the grader's own output committed under
[`reports/`](reports/) and re-derived by CI on every pull request.

Current verdict — record
[`20260921-212741-2d4e6c9`](records/20260921-212741-2d4e6c9.md):

```
block: gf180-sar-adc  kind: mixed-signal
tier: none
T1: 6/22 items met
```

| # | T1 item | analog | digital |
|---|---|---|---|
| 1 | Design sources | `no_evidence` | `no_evidence` |
| 2 | Layout | `no_evidence` | `no_evidence` |
| 3 | DRC clean | **met** | **met** |
| 4 | LVS clean | **met** | `no_evidence` |
| 5 | Full corner verification vs a ratified spec | `no_evidence` | `no_evidence` |
| 6 | Statistical claims carry Monte Carlo evidence | **met** | `no_evidence` (no statistical row) |
| 7 | Post-layout verification | `check_failed` | `no_evidence` |
| 8 | Characterization report | **met** [^item8] | **met** [^item8] |
| 9 | Testbenches shipped | `no_evidence` | `no_evidence` |
| 10 | Repo hygiene | `no_evidence` | `no_evidence` |
| 11 | Power delivery (structural) | `supply_spec_incomplete` [^erc] | `no_evidence` |

[^erc]: **Cited and graded as of issue #347 — `unmet`, not `met`.** Item 11
    is the one *compound* T1 item: its citation is a list (the `klt erc`
    supply run plus the LVS report item 4 already cites), which
    `run_signoff.py`'s `manifest_citations()` now understands
    (`_manifest_citation_part()`). The cited `klt erc` run says `vdd` and
    `vss` each resolve to exactly one electrical island, with zero
    `erc.unconnected_net` and zero `erc.supply_short` — but the committed
    supply spec declares **no `ties[]`** at all, which the grader treats as
    an incomplete declaration rather than a passing one regardless of what
    else is clean. That is not a spec defect: `ADC_BLOCK` draws no implant
    layers, so the real gf180mcu tap boolean (`COMP ∩ Nplus`) has nothing to
    intersect, and per
    [DR-0032](../spec/decision-records/DR-0032-implant-layers-not-drawn.md)
    the geometry answers the same question directly — **zero n-well taps
    drawn in any of this block's 25 wells**. `supply_spec_incomplete` is
    therefore the correct, actionable reading: "we looked, here is the
    artifact, here is the one condition it cannot meet and why", not
    "nobody has looked". The layout work that would move this row to `met`
    (drawing the taps) is #340. A row is only ever moved here by a `--regen`
    plus a new record, never by editing this table.

[^item8]: **Read this before reading item 8 as good news.** It means *an
    aggregated, current characterization report exists and a human re-read
    it* — not that the block passes. **Three ratified rows FAIL** in the
    document those two citations wrap: ENOB (8.857 bit worst vs `> 9.0`),
    SFDR (60.40 dB vs `≥ 62 dB`) and Area (0.150536 mm² vs `< 0.1 mm²`);
    the digital partition's rung-2 gate-level replay is not passing either.
    *Does the block pass its corner set* is item **5**, `unmet` on both
    partitions, and it stays that way. Item 8 is also the only T1 item whose
    evidence this repo **writes for the grader** rather than cites — see
    [`evidence/README.md`](evidence/README.md) and
    [**#339**](records/20260921-175516-93ddfe3.md).

**Do not read those rows as a to-do list without reading the record.** Several
are `unmet` for structural reasons that no amount of work on this block
changes (items 1, 2, 9 and 10 have no `klt` verb behind them and are
deliberately left uncited), one is `unmet` because the item does not apply
(6.digital), and two are `met` on evidence narrower than the item's own text
(6.analog, and both halves of item 8 — see the footnote above). Each row's
reasoning — and every coverage disclosure the checklist requires the
*claimant* to make, which a `met` verdict does not discharge — is not in
[`records/20260921-212741-2d4e6c9.md`](records/20260921-212741-2d4e6c9.md)
itself — that record only re-anchors an unchanged verdict to a manifest
carrying two edits that raced, and says so. The substantive reasoning is in
[`records/20260921-175516-93ddfe3.md`](records/20260921-175516-93ddfe3.md)
(item 8),
[`records/20260921-175049-93ddfe3.md`](records/20260921-175049-93ddfe3.md)
(item 4's `content_hash`),
[`records/20260921-131851-36d405e.md`](records/20260921-131851-36d405e.md)
(item 11, issue #347) and, for the rows none of them moved,
[`records/20260921-021722-2422cac.md`](records/20260921-021722-2422cac.md).

## What is here

| File | What it is |
|---|---|
| `gf180-sar-adc.manifest.json` | **The block manifest.** `block`, `kind`, and one evidence citation per T1 item that has one. This is the file the fleet roll-up (2AMLogic/2am#956) reads. |
| `toolchain.json` | The pinned `klt` build that grades it — an exact commit, plus the grading-ruleset id and the checklist-document hash it graded against. |
| `freshness.json` | Repo-side pins: for every citation, the artifacts whose bytes it depends on, the envelope fields that must not move, and the row verdict it produced. Machine-written by `--regen`. |
| `run_signoff.py` | `--regen` (mint a report with the pinned `klt`), `--check` (re-derive it with stdlib only — what CI runs), `--selftest` (negative control, 10 tampered inputs). |
| `evidence/` | **The one exception to "this directory stores no evidence of its own."** T1 item 8 names no `klt` verb, so no verb's output can satisfy it; the grader ingests it through a hand-written *generic evidence envelope*, and item 8 is the only item that accepts one. Two live here, one per partition, both wrapping `sim/characterization-summary.md` — [`evidence/README.md`](evidence/README.md). |
| `reports/<record-id>/` | Committed grader output: `signoff.json` byte-identical to `klt signoff --format json`, and `signoff.txt` (ANSI stripped — klayout-tools#2227). Append-only. |
| `records/<record-id>.md` | The claim: what was graded, what the verdict means, every disclosure the grader does not enforce. Append-only. |

## Reproducing the verdict

```bash
# The grader is pinned to a commit, not a release -- see toolchain.json's
# _comment for why a released wheel cannot render item 11 at all.
pip install 'git+https://github.com/2AMLogic/klayout-tools@67d617f899c7fb941b86cfc85491f75b91ae1176'

klt signoff --manifest signoff/gf180-sar-adc.manifest.json --format json   # from the repo root
python3 signoff/run_signoff.py --check                                     # no klt needed
python3 signoff/run_signoff.py --selftest                                  # prove --check can fail
```

Run the grader **from the repo root**: a manifest's file-backed evidence paths
resolve against the invoking process's working directory, with no
manifest-relative anchoring.

## Why there is a repo-side `--check` at all

`klt signoff` is the grader; `run_signoff.py --check` is what keeps its verdict
from rotting between runs. CI installs neither `klt` nor the PDK on the
pull-request path (`.github/workflows/ci.yml` says why, at length), so a
verdict only CI *cannot* re-derive is a verdict that goes stale silently —
exactly the failure the manifest exists to end.

`--check` re-derives, with nothing but CPython: that every cited envelope still
says what the report says it said; that every repo artifact behind a citation
still hashes to its pin (**edit `layout/adc-top/adc_block.gds` without re-running
DRC and the next pull request goes red**); that both committed renderings of the
report (`signoff.json` and `signoff.txt`) hash to what `--regen` wrote; that the
committed report agrees with the manifest and with the toolchain pin; and that
every rendered row's status/reason is the one recorded beside it — a row
flipping to `met` is as much a drift signal as one flipping to `unmet`.

**Agreement with the manifest is row by row, not just block-level.** Each graded
row in the committed report carries the `citation.file` and
`citation.content_hash` the grader read at grading time, and `--check` asserts
both against the manifest's citation for that same item key. Re-pointing a
citation and updating `freshness.json` to match — the one hand-edit the
manifest's `_comment` warns against — therefore fails, instead of leaving a
verdict on file that was graded on a file the manifest no longer cites. On a
per-partition manifest that check is what stops the *digital* partition's DRC
envelope from standing as the *analog* partition's evidence. Two rows it
cannot reach this way: `7.analog`, whose errored `klt pex` run makes the
grader render `citation: null`, and `11.analog`, whose grader
(`_grade_power_delivery`) only ever builds a `citation` at all on the `met`
path — an `unmet` compound row renders `citation: null` regardless of how
many parts were cited. Both gaps are declared in `freshness.json`
(`report_citation_note`), and `--check` fails any cited item that renders no
citation and has no such note.

For **three** citations the repo-side check is strictly *stronger* than the
grader's — each one a case where `klt signoff` reports
`input: not re-hashed` and `--check` re-hashes the committed artifact anyway:

- **`3.digital`** — the digital DRC envelope names its input by an absolute
  path from the worktree that produced it, which does not exist anywhere in
  this repo. `--check` hashes the committed macro GDS and compares.
- **`8.analog` / `8.digital`** — a `generic` envelope's author chooses their
  own field names, so the grader cannot know which key names the input and
  reports `input_verified: null` by construction (klayout-tools#2196's table
  lists `generic` among the kinds it cannot resolve). `--check` re-hashes
  `sim/characterization-summary.md` directly. That matters more here than
  anywhere else in this file: it is the only rot path where the grader would
  otherwise render `met` indefinitely over a document that had been rewritten
  underneath it. `--selftest` carries a dedicated control per generic
  citation proving the check fires.

What `--check` cannot do is re-run the grader, so it cannot see a change in
`klt`'s own grading rules. That is what `toolchain.json`'s `grading_ruleset_id`
and `source_doc_content_hash` pins are for: they name the rules and the
checklist text the committed report was graded under, and a bump is a reviewed
change with a new record, never a silent re-grade.

## Changing the verdict

Any change to what this block claims goes through the same three steps:

1. Produce or re-run the evidence, and commit it where its own flow records it
   (`layout/`, `sim/`, `design/sar-logic/flow/` — this directory stores no
   evidence of its own, only citations to it).
2. Edit `gf180-sar-adc.manifest.json`'s citation, then run
   `python3 signoff/run_signoff.py --regen`. It refuses to run under a `klt`
   that is not the pinned build, mints a new `reports/<record-id>/`, and
   rewrites `freshness.json`'s derived values.
3. Write the new `records/<record-id>.md`: what moved, why, and every
   disclosure the grader does not enforce (item 3's deck-coverage gaps, item
   7's `body_bias`, the scope of anything cited). A `--regen` without a record
   is half a change.

`reports/` and `records/` are **append-only**, like `sim/` and
`layout/*/reports/`: a superseded verdict is superseded by a new record that
says so, never by an edit. `run_signoff.py --regen` enforces this by refusing
to overwrite an existing record slot.

### Open work that will move a row

| Row | Blocked on |
|---|---|
| 11 (analog) | **Cited and graded, #347: `unmet` / `supply_spec_incomplete`, not `met`.** The manifest now carries item 11's compound citation (the `klt erc` supply run plus the LVS report item 4 grades), and `run_signoff.py` grades it. It does not reach `met`: the committed supply spec declares no `ties[]` at all, which the grader reads as an incomplete declaration regardless of what else is clean. That is not an oversight to fix in the spec — `ADC_BLOCK` draws no implant layers, so the real gf180mcu tap boolean (`COMP ∩ Nplus`) has nothing to intersect, and the only declarable alternative is classified *degenerate* by klayout-tools#2199 (filed generically upstream as klayout-tools#2234). Both failure modes are committed as re-run controls under `layout/erc/controls/`. Per `spec/decision-records/DR-0032-implant-layers-not-drawn.md`, `layout/erc/well_tap_audit.py` answers the same question directly from geometry: **no n-well tap drawn in any of the 25 wells**, both substrate-tie guard rings strapped to nothing. The tie half of item 11 is therefore *failed on evidence*, not uncomputed. The layout work that would move this row to `met` is **#340**. |
| ~~4 (analog, its missing `content_hash`)~~ | **Done, #338** — `layout/toolchain.json`'s `klt` pin moved to `b15edf5e` (past klayout-tools#1969/#2027), the LVS proof-cell suite was re-run under it, and the re-pointed citation now carries a real `provenance.input.content_hash`. The repo-side `environment.layout_sha256` / `environment.reference_sha256` pins that stood in for it are kept anyway, belt-and-suspenders. Left in this table, struck, rather than deleted, for the same reason item 8's row is. |
| 4 (digital), 11 (digital) | No LVS of the routed `sar_ctrl` macro exists; item 11's digital branch also needs that report's `power_connectivity` verdict. |
| ~~8 (both)~~ | **Done, #339** — `signoff/evidence/characterization-summary.{analog,digital}.json` now wrap `sim/characterization-summary.md`, one envelope per partition, and both rows render `met`. What that does *and does not* mean is the footnote above and [`records/20260921-175516-93ddfe3.md`](records/20260921-175516-93ddfe3.md). Left in this table, struck, rather than deleted: this table is the map of where the block's gap to T1 is, and a row that closed is part of that map. |
| 7 (analog) | klayout-tools#1030 blocks `klt pex` for every block this repo extracts, **and** the cited run is comparator-scoped — it must be re-pointed at a block-level run, not merely re-run. |
| 5 (analog) | Three ratified spec rows FAIL on the governing extracted side (ENOB, SFDR, Area), and no `klt sim` envelope exists for the harness's own PVT sweeps. |
| 5 (digital) | The `klt sta` runs are one-corner-per-response; item 5 grades the corner set the cited run declares. No `klt functional-verification` envelope exists. |

## Relationship to this repo's earlier T1 reads

`sim/t1-checklist-reread-20260825.md` and `sim/t1-drc-lvs-spec-verification.md`
are dated, append-only evidence records and stay exactly as they are. **They
are no longer the verdict of record** — this directory is. Two things had
already invalidated a hand-maintained checklist by the time it was written
down: the T1 checklist itself grew an eleventh item on 2026-09-17
(klayout-tools#2025), and this block's digital partition went from a
behavioural model to RTL + synthesis + STA + a routed macro, which changes its
`kind` from `analog` to `mixed-signal`. A hand-read cannot notice either
without someone remembering to re-read it; a graded manifest notices the first
automatically (the checklist hash moves) and CI refuses to go green on the
second.

**Item 8 is where that argument gets tested rather than asserted**, because
it is the one row a machine cannot grade for itself. The 2026-08-25 re-read
scored `sim/characterization-summary.md` PASS while that document's own
Freshness banner named a commit five weeks and ~40 commits behind the tree —
the re-read quoted the banner instead of checking it, and nothing noticed.
Issue #339's re-read found that, five other currency defects, and a missing
ratified spec row. The lesson the `evidence/` envelopes are built around:
`--check` proves **the bytes graded are the bytes committed**; it cannot
prove the bytes are still *true*. Only a re-read does that, which is why each
envelope records `assertion.reread_commit` and why re-asserting one means
re-reading the document, not editing a hash.
