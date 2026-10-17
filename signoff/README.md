# `signoff/` — this block's gap to T1, graded rather than hand-read

**This directory is the verdict of record for "how far is this block from
T1?"** The answer is not prose here; it is
[`gf180-sar-adc.manifest.json`](gf180-sar-adc.manifest.json) graded by `klt
signoff --manifest`, with the grader's own output committed under
[`reports/`](reports/) and re-derived by CI on every pull request.

Current verdict — record <!-- signoff:current-record -->
[`20261017-195658-8c2da250`](records/20261017-195658-8c2da250.md):

```
block: gf180-sar-adc  kind: mixed-signal
tier: none
T1: 17/22 items met
```

| # | T1 item | analog | digital |
|---|---|---|---|
| 1 | Design sources | **met** [^item1] | **met** [^item1] |
| 2 | Layout | **met** [^item2] | **met** [^item2] |
| 3 | DRC clean | **met** | `unmet` (`check_failed`, 208 violations) |
| 4 | LVS clean | **met** | **met** [^lvsdig] |
| 5 | Full corner verification vs a ratified spec | `no_evidence` | `no_evidence` |
| 6 | Statistical claims carry Monte Carlo evidence | **met** | `no_evidence` (no statistical row) |
| 7 | Post-layout verification | **met** [^item7] | `no_evidence` |
| 8 | Characterization report | **met** [^item8] | **met** [^item8] |
| 9 | Testbenches shipped | **met** [^item9] | **met** [^item9] |
| 10 | Repo hygiene | **met** [^item10] | **met** [^item10] |
| 11 | Power delivery (structural) | **met** [^erc] | **met** [^ercdig] |

[^erc]: **`met` as of issue #356 — and read the limits before reading the
    tick.** Item 11 is the one *compound* T1 item: its citation is a list
    (the `klt erc` supply run plus the LVS report item 4 already cites),
    which `run_signoff.py`'s `manifest_citations()` understands
    (`_manifest_citation_part()`, #347). The cited run says `vdd` and `vss`
    each resolve to exactly one electrical island — zero
    `erc.unconnected_net`, zero `erc.supply_short` — **and** that all 25 of
    this block's `Nwell` islands carry a tap that reaches `vdd`: zero
    `erc.missing_tie`, from a rule that was *checked* rather than skipped
    (`erc_coverage.checked` carries `erc.missing_tie:["nwell_tap"]`, which
    `layout/erc/cases.json` asserts by name). This row read
    `supply_spec_incomplete` until #356 because the supply spec declared no
    `ties[]` — `ADC_BLOCK` drew no implant layers, so the real gf180mcu tap
    boolean `COMP ∩ Nplus` had nothing to intersect, and #340 measured the
    underlying fact directly and found **zero n-well taps in 25 wells** with
    both substrate-tie rings strapped to nothing. #356 fixed the layout
    ([DR-0035](../spec/decision-records/DR-0035-well-taps-and-tie-straps.md),
    superseding DR-0032) rather than the declaration. **What this `met` does
    not claim**: the *substrate* tie is not graded by `erc.missing_tie` at
    all (that rule needs a drawn `well_layer`, and the p-substrate is not
    drawn) — the two `Pplus` guard rings are covered only by their
    membership of the one `vss` island and by
    `layout/erc/well_tap_audit.py`'s direct measurement; `pdn` is `no` and
    `power_connectivity` `unchecked`, which item 11 does not require of an
    analog partition; and item 11 asks whether the supply is *connected*,
    not whether it is *adequate* — the IR/EM read in `layout/power/` still
    misses DR-0034's droop budget at one of the four candidate landing
    sites (#378, #379). A row is only ever moved here by a `--regen` plus a
    new record, never by editing this table.

[^item9]: **`met` as of issue #561 — presence, hashes and pins, not a re-run.**
    Each partition cites a `klt signoff --attest 9` envelope over a committed
    inventory
    ([`testbench-inventory.analog.json`](testbench-inventory.analog.json),
    [`testbench-inventory.digital.json`](testbench-inventory.digital.json)):
    every listed bench exists, `sim/toolchain.json`'s open_pdks revision and
    tool versions are pinned, and one PDK-free cold-start command exits 0
    (`python3 -m unittest discover -s sim/tests -t sim/tests` for analog,
    `python3 design/sar-logic/gen_sar_logic.py --check` for digital). **What
    this does not claim**: that any ngspice bench succeeds. They cannot
    cold-start on a stock machine (ngspice >= 46 and the pinned gf180mcu
    models), so they are listed, not run; reproduce them with `make smoke` /
    `make characterize` (`README.md#independent-verification-chipalooza`).
    `make check` is not the attested cold start: it exits 1 where the
    installed toolchain has drifted from `sim/toolchain.json`. A reviewer
    still has to confirm the listed commands are the documented ones.

[^item10]: **`met` as of issue #561, and read the limits.** Both partitions
    cite one `klt signoff --attest 10` envelope over
    [`repo-hygiene-inventory.json`](repo-hygiene-inventory.json): the README,
    `LICENSE`, the CI workflow, `sim/README.md`, `signoff/README.md` and
    `docs/environment-setup.md` exist, and five hermetic commands the CI
    workflow also runs exit 0 (harness unit tests, compileall, README status
    table, markdown links, characterization citations). It does not attest
    that a CI run is green, and `run_signoff.py --check` is excluded because
    it re-derives this very envelope.

[^lvsdig]: **`met` as of issue #559.** The citation is the routed `sar_ctrl`
    macro's gate-level LVS,
    [`layout/lvs/sar_ctrl/reports/20261015-222058-0a0ab20b/gatelevel.lvs.json`](../layout/lvs/sar_ctrl/reports/20261015-222058-0a0ab20b/gatelevel.lvs.json)
    (`status: match`, engine `klayout`, `error_count` 0). It compares the
    netlist extracted from the routed `layout/adc-top/sar_ctrl/sar_ctrl.gds`
    against the gate-level netlist `layout/adc-top/sar_ctrl/sar_ctrl.v`, not
    the analog block's compare. Its `mismatch_count` is 13, and none is an
    error: 11 `topology.reference_port_alias_joined` (reference ports the
    comparison joins as aliases), 1 `topology.power_only_pruned` (a net
    reaching only power pins, pruned) and 1 `topology.top_level_pins_anchored`
    (top-level pins anchored to the extracted nets). Single engine, like
    4.analog.

[^ercdig]: **`met` as of issue #559; structural only.** The compound citation
    is three parts: the `klt erc` supply run on the routed `sar_ctrl` GDS
    ([`layout/erc/sar_ctrl.supply-spec.json`](../layout/erc/sar_ctrl.supply-spec.json),
    report under `layout/erc/sar_ctrl/reports/20261017-193247-9869b69/`), the P&R
    response with the PDN (`power.pdn: true`, tapcell master
    `gf180mcu_fd_sc_mcu7t5v0__filltie`, straps on `Metal1` and `Metal4`), and
    the same gate-level LVS report as 4.digital, whose
    `power_connectivity.status` is `match`. The ERC run reports `VDD` and
    `VSS` as one island each (zero `erc.unconnected_net`,
    `erc.supply_short`) and zero `erc.missing_tie`, which `erc_coverage.checked`
    shows was computed (`erc.missing_tie:["nwell_tap"]`). The spec's stackup
    covers every strap layer the P&R response lists. Like the analog run, the
    report's top-level `status` is `not_checked` (no antenna check) and `klt
    erc` exits 4; the item-11 conditions are the findings, not that status.
    This run is not committed through `layout/erc/run_erc.py` and has no
    negative control of its own. It does not grade IR drop or
    electromigration (`klt power`).

[^item7]: **`met` as of issue #428, across the committed 117-point grid as
    of issue #439. Read the scope before reading the tick.** The citation is a
    block-scoped `klt pex` run (released klt 0.7.0) of the whole `ADC_BLOCK`
    against the current GDS:
    [`sim/adc-block-pex/records/20261015-071816-0dacd542.md`](../sim/adc-block-pex/records/20261015-071816-0dacd542.md).
    It ran the full committed request on the Spot batch fleet, with 468/468
    delta rows passing over 117 corners (`CORNER_SETS['full']` × V_dd
    {2.97, 3.3, 3.63} V × {−40, 27, 125} C). `freshness.json` pins
    `corner_count: 117`. Until #439 the row rested on one PVT point,
    [`20261008-185501-c618a90d`](../sim/adc-block-pex/records/20261008-185501-c618a90d.md)
    (tt / 3.3 V / 27 C), because the fleet runner then ran klt 0.5.0 and
    refused 0.7.0 clients. The corner coverage is now met, but the row is
    still narrower than the item's text, like 6.analog. The testbench is one
    sample/redistribute/decide sequence, not the spec suite: the spec-row
    post-layout evidence is still the five extracted campaigns, which item 7
    cannot grade (klayout-tools#871). What unblocked the row was #1558's
    `klt pex --pins`/`--deck-option` plus a pin-matched schematic `ADC_BLOCK`;
    #1030's closure added diagnostics only. Full reasoning:
    [`records/20261008-185541-ad38795c.md`](records/20261008-185541-ad38795c.md)
    (the #428 move) and
    [`records/20261015-222800-a90cb5ba.md`](records/20261015-222800-a90cb5ba.md)
    (the #439 grid re-point, including the batch probe).

[^item1]: **`met` as of issue #560 -- read what the inventories cover.** Each
    partition cites the envelope `klt signoff --attest 1 --inventory
    signoff/design-source/inventory.<partition>.json` produced
    ([`design-source/`](design-source/)), whose `status` is derived from the
    checks it ran, not asserted. Every inventoried file is pinned by sha256 in
    the envelope and again in `freshness.json`, so `run_signoff.py --check`
    (CI) fails if any of them changes without a `--regen`; the freshness
    commands themselves re-run only under `--regen`, because CI has no `klt`.
    **Analog:** the comparator, CDAC and track-switch schematics plus
    `xschemrc` and `design/adc-top/gen_adc_top.py`; derived netlists
    `comparator.spice` (check: schematic-vs-netlist device inventory and
    testbench-copy tests) and `adc_top.spice` (check: its generator's
    `--check`; there is no `adc_top.sch`). **Not covered:** the CDAC and
    track-switch schematics have no derived netlist and no equivalence test,
    so they are pinned as sources only; netlisting any `.sch` goes through
    `klt netlist`, never raw `xschem`. **Digital:** `sar_ctrl.v`, its rung-1
    generator and the synthesis script; derived `sar_ctrl.spice` (generator
    `--check`) and both synthesized gate-level netlists. The gate-level
    freshness check is **formal equivalence to the RTL**, not byte-for-byte
    re-synthesis, which is pinned to one Yosys build and is not reproducible
    on this host (`sim/tests/test_sar_ctrl_gate_netlist.py`).

[^item2]: **`met` as of issue #560.** Each partition cites a generic
    envelope ([`layout/`](layout/)) pinning the GDS by path and sha256, the
    same stream its item-3 DRC report read (`--regen` refuses to mint a
    passing envelope if the two hashes differ). **Analog:**
    `layout/adc-top/adc_block.gds`, with a regeneration claim -- `--regen`
    re-ran `layout/adc-top/gen_adc_top.py` into an empty directory and
    recorded the hash it produced, equal to the committed stream. `klt
    signoff` grades that hash equality but never runs the generator.
    **Digital:** `layout/adc-top/sar_ctrl/sar_ctrl.gds`, generator named
    (`design/sar-logic/flow/pnr_sar_ctrl.py`) but **not re-run**: its output
    depends on the pinned Yosys/OpenROAD/PDK build, so the row rests on the
    pinned hash and the committed flow, not on a reproduction. Item 2 says
    nothing about DRC or LVS cleanliness; items 3 and 4 grade that (3.digital
    is `unmet`, 208 violations).

[^item8]: **Read this before reading item 8 as good news.** It means *an
    aggregated, current characterization report exists and a human re-read
    it* — not that the block passes. **Three ratified rows FAIL** in the
    document those two citations wrap: ENOB (8.855 bit worst vs `> 9.0`),
    SFDR (60.41 dB vs `≥ 62 dB`) and Area (0.151827 mm² vs `< 0.1 mm²`);
    the digital partition's rung-2 gate-level replay is not passing either.
    *Does the block pass its corner set* is item **5**, `unmet` on both
    partitions, and it stays that way. Item 8 is also the only T1 item whose
    evidence this repo **writes for the grader** rather than cites — see
    [`evidence/README.md`](evidence/README.md) and
    [**#339**](records/20260921-175516-93ddfe3.md).

**Do not read those rows as a to-do list without reading the record.** Several
are `unmet` for structural reasons that no amount of work on this block
changes (items 1 and 2 were in that set until issue #560, items 9 and 10 until
issue #561), one is `unmet` because the item does not apply
(6.digital), and three are `met` on evidence narrower than the item's own text
(6.analog, 7.analog — one stimulus, not the spec suite — and both halves of item 8; see the
footnotes above). Each row's
reasoning — and every coverage disclosure the checklist requires the
*claimant* to make, which a `met` verdict does not discharge — is not
in <!-- signoff:current-record -->
[`records/20261017-195658-8c2da250.md`](records/20261017-195658-8c2da250.md)
alone. That record re-grades the merge of #559, #560 and #561 (the chain had
forked again) and supersedes
[`20261017-194455-beb05921`](records/20261017-194455-beb05921.md) (#559 + #560,
13/22) and
[`20261017-193929-9869b691`](records/20261017-193929-9869b691.md) (#561 alone:
attests items 9 and 10 with `klt signoff --attest`, re-pins the grader, 11/22).
Against `main` it moves four rows, items 9 and 10 in both partitions,
`no_evidence` -> `met` (issue #561). Its predecessors
[`20261017-193831-9869b691`](records/20261017-193831-9869b691.md) (#560 alone,
11/22) and
[`20261017-193508-9869b691`](records/20261017-193508-9869b691.md) (#559: cites
the routed `sar_ctrl` gate-level LVS and a `klt erc` supply run, moving
4.digital and 11.digital `unmet` -> `met`) both descend from
[`20261015-222800-a90cb5ba`](records/20261015-222800-a90cb5ba.md) re-mints the digital DRC envelope after the Metal4
supply-strap repair (issue #485) and moves one row, 3.digital `met` ->
`unmet`; its predecessor
[`20261015-072035-3ff1153f`](records/20261015-072035-3ff1153f.md) re-points item 7 (analog) at the full 117-point
`klt pex` grid (issue #439) without moving a row, and its predecessor
[`20261015-001716-74685b3a`](records/20261015-001716-74685b3a.md)
(issue #392) only re-anchors an unchanged verdict to the item-8 evidence
re-minted under it, as do
[`20261009-170226-b6ca4338`](records/20261009-170226-b6ca4338.md)
(issue #484, correcting the baseline STA parasitics wording),
[`20261009-094003-124c2a53`](records/20261009-094003-124c2a53.md)
(issue #459, PR #469 review follow-up),
[`20261009-093206-c472fff3`](records/20261009-093206-c472fff3.md)
(issue #459),
[`20261009-083433-6dc5cd2e`](records/20261009-083433-6dc5cd2e.md)
(issue #437, PR #462 review follow-up),
[`20261009-082407-c53a9b17`](records/20261009-082407-c53a9b17.md)
(issue #437) and
[`20261008-202455-4b5693ef`](records/20261008-202455-4b5693ef.md) (issue #432). The reasoning for the one row that last moved
(item 7, issue #428) is in
[`20261008-185541-ad38795c`](records/20261008-185541-ad38795c.md); the one before that,
[`20261007-032748-191e2243`](records/20261007-032748-191e2243.md), like the six
before that
([`20260924-044244-cda7de50`](records/20260924-044244-cda7de50.md),
[`20260923-142807-f58df2b`](records/20260923-142807-f58df2b.md),
[`20260923-130547-7256414`](records/20260923-130547-7256414.md),
[`20260923-114030-904af96`](records/20260923-114030-904af96.md),
[`20260923-084903-5f13cf9`](records/20260923-084903-5f13cf9.md),
[`20260923-071455-e84ad26`](records/20260923-071455-e84ad26.md)), only
re-anchors an unchanged verdict to evidence that was re-minted under it, and
says so. The substantive reasoning is in
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
| `run_signoff.py` | `--regen` (mint a report with the pinned `klt`), `--check` (re-derive it with stdlib only — what CI runs, and which also checks the repo-root `README.md`'s current-record pointer), `--selftest` (negative control: tampered-input cases). |
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
envelope from standing as the *analog* partition's evidence. A row it cannot
reach this way is one the grader renders with `citation: null`. Until #428
`7.analog` was one, because its errored `klt pex` run left no citation. It now
renders a citation and is compared like every other row. `11.analog`'s
grader (`_grade_power_delivery`) only builds a `citation` on the `met` path,
so an `unmet` compound row renders `citation: null` however many parts were
cited. Such a gap must be declared in `freshness.json`
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

**The "Current verdict" pointer at the top of this file — and the repo-root
[`README.md`](../README.md)'s matching citation — are checked, not
hand-maintained.** This file's pointer had gone two re-grades stale (#397) and
nothing failed, because it stayed *accidentally* true — neither intervening
re-grade moved a row; the repo-root README named the same stale drift one file
over, for the same reason (#399). `--check` now asserts that every citation
tagged — in either file, per `run_signoff.py`'s `README_CURRENT_RECORD_FILES`
— with a line-ending `<!-- signoff:current-record -->` HTML comment, which a
reader never sees, names `freshness.json`'s `report.record_id`, the record
whose report the checks above just re-derived, **and** that no other record's
`Supersedes:` line claims to replace it. The second half catches the inverse
mistake: a
`--regen` whose record was written but whose pins were never refreshed would
otherwise leave these files and `freshness.json` agreeing on the same stale
record. `README.md` cites the record as a bare `` `<record-id>` `` with no
link (unlike this file's `records/<id>.md` link); `--check` accepts both
forms. Every assertion carries a `--selftest` control.

What `--check` cannot do is re-run the grader, so it cannot see a change in
`klt`'s own grading rules. That is what `toolchain.json`'s `grading_ruleset_id`
and `source_doc_content_hash` pins are for: they name the rules and the
checklist text the committed report was graded under, and a bump is a reviewed
change with a new record, never a silent re-grade.

## Changing the verdict

Any change to what this block claims goes through the same four steps:

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
4. Re-point every `<!-- signoff:current-record -->` citation at the new
   record — in this file, **and** in the repo-root [`README.md`](../README.md)
   (`run_signoff.py`'s `README_CURRENT_RECORD_FILES`). Not a courtesy —
   `--check` fails until you do (#397, #399), and it fails the same way if the
   new record is missing entirely.

`reports/` and `records/` are **append-only**, like `sim/` and
`layout/*/reports/`: a superseded verdict is superseded by a new record that
says so, never by an edit. `run_signoff.py --regen` enforces this by refusing
to overwrite an existing record slot.

### Open work that will move a row

| Row | Blocked on |
|---|---|
| ~~11 (analog)~~ | **MOVED TO `met` AT ISSUE #356 — this row is closed.** It read `unmet` / `supply_spec_incomplete` for as long as the committed supply spec declared no `ties[]`, which the grader reads as an incomplete declaration regardless of what else is clean. That was not a spec defect to edit around: `ADC_BLOCK` drew no implant layers, so the real gf180mcu tap boolean (`COMP ∩ Nplus`) had nothing to intersect, and the only declarable alternative is classified *degenerate* by klayout-tools#2199 (filed generically upstream as klayout-tools#2234). #340 answered the same question from geometry and found **no n-well tap in any of the 25 wells**, both substrate-tie rings strapped to nothing — *failed on evidence*, not uncomputed. #356 drew and routed the taps, closed and strapped both rings, and marked them with implants (`spec/decision-records/DR-0035-well-taps-and-tie-straps.md`, superseding DR-0032), so the declaration became expressible and its verdict clean in the same change. Both failure modes remain committed as re-run controls under `layout/erc/controls/`, joined by a discrimination control that proves the new zero could have been non-zero. Left in this table, struck, rather than deleted, for the same reason items 4 and 8 are: this table is the map of where the block's gap to T1 is, and a row that closed is part of that map. |
| ~~4 (analog, its missing `content_hash`)~~ | **Done, #338** — `layout/toolchain.json`'s `klt` pin moved to `b15edf5e` (past klayout-tools#1969/#2027), the LVS proof-cell suite was re-run under it, and the re-pointed citation now carries a real `provenance.input.content_hash`. The repo-side `environment.layout_sha256` / `environment.reference_sha256` pins that stood in for it are kept anyway, belt-and-suspenders. Left in this table, struck, rather than deleted, for the same reason item 8's row is. |
| ~~4 (digital), 11 (digital)~~ | **Done, #559** — the routed `sar_ctrl` gate-level LVS (#480, #519) is cited as `4.digital`, and `11.digital` cites it with a new `klt erc` supply run and the P&R response's PDN. Left in this table, struck, like the other closed rows. |
| ~~8 (both)~~ | **Done, #339** — `signoff/evidence/characterization-summary.{analog,digital}.json` now wrap `sim/characterization-summary.md`, one envelope per partition, and both rows render `met`. What that does *and does not* mean is the footnote above and [`records/20260921-175516-93ddfe3.md`](records/20260921-175516-93ddfe3.md). Left in this table, struck, rather than deleted: this table is the map of where the block's gap to T1 is, and a row that closed is part of that map. |
| ~~7 (analog)~~ | **MOVED TO `met` AT ISSUE #428, on one PVT point; grid re-taken at issue #439 (117/117 corners, 468/468 rows pass, `sim/adc-block-pex/records/20261015-071816-0dacd542.md`). This row is closed for corner coverage; it remains one stimulus, not the spec suite (footnote 7).** The history below is kept as written: The citation was re-pointed from the errored, comparator-scoped 2026-08-15 run to a block-scoped `klt pex` 0.7.0 run against the current GDS (`sim/adc-block-pex/`). #1030 closed with diagnostics only. What unblocked the run was #1558's `--pins`/`--deck-option`, plus a pin-matched schematic `ADC_BLOCK`. **What remains** is the committed 117-point grid. It is blocked on the batch fleet's runner image (klt 0.5.0 refuses 0.7.0 clients, `batch_runner_version_mismatch`), which is a worker-spec change, not a repo change: `run_pex_adc_block.py --backend batch` re-runs it. Two generic frictions from the retry are filed as klayout-tools#2871 (the multi-`.include` remedy advice drops a PDK switch-parameter file from the extracted side) and #2872 (`klt pex` drops `klt sim`'s per-corner diagnostics). |
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
