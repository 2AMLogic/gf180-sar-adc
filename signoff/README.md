# `signoff/` — this block's gap to T1, graded rather than hand-read

**This directory is the verdict of record for "how far is this block from
T1?"** The answer is not prose here; it is
[`gf180-sar-adc.manifest.json`](gf180-sar-adc.manifest.json) graded by `klt
signoff --manifest`, with the grader's own output committed under
[`reports/`](reports/) and re-derived by CI on every pull request.

Current verdict — record
[`20260921-021722-2422cac`](records/20260921-021722-2422cac.md):

```
block: gf180-sar-adc  kind: mixed-signal
tier: none
T1: 4/22 items met
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
| 8 | Characterization report | `no_evidence` | `no_evidence` |
| 9 | Testbenches shipped | `no_evidence` | `no_evidence` |
| 10 | Repo hygiene | `no_evidence` | `no_evidence` |
| 11 | Power delivery (structural) | `no_evidence` [^erc] | `no_evidence` |

[^erc]: **This row is stale on the analog side as of issue #330.** The
    evidence item 11's `klt erc` half needs now exists and is committed —
    `layout/erc/adc_block.supply-spec.json` and its report under
    `layout/erc/reports/`, which say `vdd` and `vss` each resolve to exactly
    one electrical island, with zero `erc.unconnected_net` and zero
    `erc.supply_short`. The manifest does not cite it yet, so the grader
    still renders `no_evidence`; **#347** is what teaches it to, and "Open
    work that will move a row" below says why the row will then read
    `unmet` / `supply_spec_incomplete` rather than `met`. A row is only
    ever moved here by a `--regen` plus a new record, never by editing this
    table.

**Do not read those rows as a to-do list without reading the record.** Several
are `unmet` for structural reasons that no amount of work on this block
changes (items 1, 2, 9 and 10 have no `klt` verb behind them and are
deliberately left uncited), one is `unmet` because the item does not apply
(6.digital), and one is `met` on evidence narrower than the item's own text
(6.analog). Each row's reasoning — and every coverage disclosure the checklist
requires the *claimant* to make, which a `met` verdict does not discharge — is
in [`records/20260921-021722-2422cac.md`](records/20260921-021722-2422cac.md).

## What is here

| File | What it is |
|---|---|
| `gf180-sar-adc.manifest.json` | **The block manifest.** `block`, `kind`, and one evidence citation per T1 item that has one. This is the file the fleet roll-up (2AMLogic/2am#956) reads. |
| `toolchain.json` | The pinned `klt` build that grades it — an exact commit, plus the grading-ruleset id and the checklist-document hash it graded against. |
| `freshness.json` | Repo-side pins: for every citation, the artifacts whose bytes it depends on, the envelope fields that must not move, and the row verdict it produced. Machine-written by `--regen`. |
| `run_signoff.py` | `--regen` (mint a report with the pinned `klt`), `--check` (re-derive it with stdlib only — what CI runs), `--selftest` (negative control). |
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
envelope from standing as the *analog* partition's evidence. The single row it
cannot reach is `7.analog`, whose errored `klt pex` run makes the grader render
`citation: null`; that gap is declared in `freshness.json`
(`report_citation_note`), and `--check` fails any cited item that renders no
citation and has no such note.

For one citation the repo-side check is strictly *stronger* than the grader's:
the digital DRC envelope names its input by an absolute path from the worktree
that produced it, so `klt signoff` cannot re-hash the artifact and says so
(`input: not re-hashed`). `--check` hashes the committed macro GDS and compares.

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
| 11 (analog) | **The `klt erc` half is done** (#330): `layout/erc/` holds the supply spec and a committed report saying `vdd` and `vss` each resolve to exactly one electrical island. Two things still block the row, both on **#347**. (1) **The manifest cannot cite it yet.** Item 11 is the only *compound* T1 item — its manifest entry is a **list** of evidence entries (the `klt erc` run plus the LVS report item 4 grades) — and `run_signoff.py`'s `manifest_citations()` understands only the single-file entry shapes this repo has needed so far, as does `freshness.json`. Teaching both the list shape is what lets `--regen` grade the row at all. (2) **Even then the row reads `unmet` / `supply_spec_incomplete`, not `met`**, because the spec declares no `ties[]` and an uncomputed `erc.missing_tie` is not a clean one. That is not an oversight to fix in the spec: `ADC_BLOCK` draws no implant layers, so the real gf180mcu tap boolean (`COMP ∩ Nplus`) has nothing to intersect, and the only declarable alternative is classified *degenerate* by klayout-tools#2199 (filed generically upstream as klayout-tools#2234). Both failure modes are committed as re-run controls under `layout/erc/controls/`. (3) **And the row would not reach `met` even with a declarable tie** — #340 settled the layout side: `layout/erc/well_tap_audit.py` measures the same question directly from the geometry and finds **no n-well tap drawn in any of the 25 wells**, with both substrate-tie guard rings strapped to nothing. The tie half of item 11 therefore *fails on evidence* rather than being uncomputed. The layout work is **#356**; the decision not to draw implants ahead of it is `spec/decision-records/DR-0032-implant-layers-not-drawn.md`. |
| 4 (analog, its missing `content_hash`) | **#338**, currently `loom:blocked` — the committed LVS report predates klayout-tools#1969, so `provenance.input` is `null`; an LVS re-run under a newer `klt` pin is what lets the manifest pin a hash here. The exception stands until that issue moves, which is why `freshness.json` pins the envelope's own `environment.layout_sha256` / `environment.reference_sha256` in the meantime rather than leaving the citation unchecked. |
| 4 (digital), 11 (digital) | No LVS of the routed `sar_ctrl` macro exists; item 11's digital branch also needs that report's `power_connectivity` verdict. |
| 8 (both) | **#339** — no `generic` evidence envelope wraps `sim/characterization-summary.md` yet; item 8 is the only T1 item such a citation may satisfy. |
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
