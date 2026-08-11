# T1 checklist items 3/4 and the item-5 precondition — verdicts read

Part of #141, scoped by epic #140's 2026-08-09 T1/bronze evidence-tier
survey. That survey confirmed the DRC/LVS *artifacts* exist (99 files under
`layout/drc/`, 181 under `layout/lvs/`) but explicitly did not open them:
"a checked box below means the artifact exists on `main`; it does not
assert the pass condition unless the note says the verdict was read." This
document is that reading pass, plus the separate item-5 precondition (is a
spec table actually ratified). No new simulation or layout work was done —
this is a read-only audit of what is already committed, run at
`a51bd10` (2026-08-11).

**Method**: every DRC/LVS JSON file under `layout/drc/` and `layout/lvs/`
was parsed programmatically (not sampled) and its `status` field checked
against the deck's own documented pass/fail semantics
(`layout/README.md`); freshness was checked two ways — (a) content-hash
comparison between the latest report's `provenance.input.content_hash` and
the sha256 of the currently-committed GDS it claims to describe, and (b)
re-running the repo's own `--check` entry points (`run_drc.py --check`,
`run_lvs.py --check`), which re-derive DRC/LVS verdicts from the
currently-checked-out layout/design sources rather than trusting a
committed report. Where (a) and (b) disagree, (b) — the live re-run — wins,
since it cannot be stale by construction.

---

## 0. What "99" and "181" actually count

`layout/drc/` holds 99 JSON files, but not all 99 are per-run *reports*:

| Kind | Count | Example |
|---|---|---|
| Per-cell DRC report (`<cell>.drc.json`, one of 9 report runs) | 89 | `reports/20260806-233236-56be937/adc_top.drc.json` |
| Per-run toolchain manifest (`toolchain.json`) | 9 | `reports/20260806-233236-56be937/toolchain.json` |
| Expectations fixture (not a report) | 1 | `cells/cells.json` |
| **Total** | **99** | |

`layout/lvs/` holds 181 JSON files, similarly mixed:

| Kind | Count | Example |
|---|---|---|
| Per-cell LVS verdict (`<cell>.lvs.json`) | 89 | `reports/.../adc_top.lvs.json` |
| Per-cell extraction report (`<cell>.extract.json`) | 80 | `reports/.../adc_top.extract.json` |
| Per-run toolchain manifest (`toolchain.json`) | 9 | `reports/.../toolchain.json` |
| Expectations/request fixtures (not reports) | 3 | `cells/cells.json`, `cells/lvs_request_match.json`, `cells/lvs_request_mismatch.json` |
| **Total** | **181** | |

This distinction matters for coverage-honesty: three of the 99, and four of
the 181, are not verdicts at all, so "99 DRC reports" / "181 LVS reports"
overstates the verdict count by that much. It does not change any
conclusion below, but the checklist item should cite the corrected figures
(89 DRC verdicts across 9 runs, 89 LVS verdicts + 80 extraction verdicts
across 9 runs) rather than the raw file counts.

The 9 runs are 9 successive append-only records (`layout/drc/reports/<id>/`,
`layout/lvs/reports/<id>/`), one per layout-affecting change since 2026-08-01
(one record — 2026-08-01 05:12 — is an early partial run of 2 proof cells
only, before the block layout existed; the other 8 cover the full 9-cell +
2-proof-cell set, 10 once `adc_tp_sw` was added).

---

## 1. DRC verdicts (T1 item 3)

**All 89 committed DRC verdicts were read. Every one that is expected to be
clean is `status: clean`; both proof cells report exactly their seeded/
discovered violations in every run they appear in — no unexplained result
anywhere in the 89.**

| Run (`<record-id>`) | Cells covered | Result |
|---|---|---|
| `20260801-051207-4a0643b` | `sw_unit`, `uncovered_layer_probe` (proof cells only — pre-block-layout) | `sw_unit` violations:2 (seeded, expected); `uncovered_layer_probe` clean:0 (deck did not yet cover MiM/upper-metal — this *was* the finding this cell exists to make, see below) |
| `20260801-225603-7866d03` | + `adc_drv`,`adc_tgate`,`adc_tgate_dum`,`adc_cdac_cell`,`comparator`,`comparator_nores`,`adc_top`,`adc_block` (no `adc_tp_sw` yet) | all real-design cells clean:0; proof cells unchanged |
| `20260804-100548-688c2eb` | + `adc_tp_sw` (full 11-cell set from here on) | all real-design cells clean:0 |
| `20260804-181054-4097611` | full set | all real-design cells clean:0 |
| `20260804-184332-9d8422d` | full set | all real-design cells clean:0; `uncovered_layer_probe` flips to violations:8 — deck gained Metal2–5/MetalTop/MiM-stack rules (klayout-tools#157/#188 upstream), so the negative control now correctly fires |
| `20260804-205502-a0f8784` | full set | all real-design cells clean:0; `uncovered_layer_probe` violations:8 |
| `20260805-122538-e8017f2` | full set | all real-design cells clean:0; `uncovered_layer_probe` violations:8 |
| `20260806-193859-68ad582` | full set | all real-design cells clean:0; `uncovered_layer_probe` violations:11 — deck gained the `via4.width.1`/`metal4.enclosing.via4.1` closure at the issue #116 pin bump |
| `20260806-233236-56be937` (**latest**) | full set | all real-design cells clean:0; `uncovered_layer_probe` violations:11; `sw_unit` violations:2 |

The 9 real-design cells (`adc_drv`, `adc_tgate`, `adc_tgate_dum`,
`adc_cdac_cell`, `adc_tp_sw`, `comparator`, `comparator_nores`, `adc_top`,
`adc_block`) report `status: clean`, `violation_count: 0` in **every** run
they appear in — 71 of 71 clean reports, no exceptions. `sw_unit` (positive
control) reports its two seeded violations in all 9 runs it appears in.
`uncovered_layer_probe` (negative control) legitimately transitions from
`clean` (deck had no rules for the layers it draws on) to `violations`
(deck gained coverage) partway through the trail — that transition is the
recorded evidence the coverage gap closed, not a defect (see
`layout/drc/records/20260806-233236-56be937.md` and `layout/README.md`
"The gf180mcu deck: coverage" for the narrative this record trail backs).

**Freshness of the latest run (`20260806-233236-56be937`)**:

- Content-hash check: every cell's `provenance.input.content_hash` in the
  latest run's reports matches the sha256 of the currently-committed GDS it
  names (`adc_top.gds`, `adc_block.gds`, `comparator.gds`,
  `comparator_nores.gds`, and all five `layout/adc-top/cells/*.gds`) —
  11/11 fresh, verified directly, not assumed.
- Live re-run: `python3 layout/drc/run_drc.py --check` (klt 0.2.0,
  klayout 0.30.10, this worktree) reproduces every cell's expected
  `rule_counts` against the currently-checked-out layout with `[ok]` on all
  11 cells. No stale result.
- git history: the most recent commit touching any committed GDS
  (`6c2b41c`, #121) is the **same commit** that minted the latest DRC/LVS
  report pair — no commit since has touched a GDS or a DRC/LVS cell
  generator (`git log 6c2b41c..HEAD -- layout/ design/` shows 5 commits,
  all touching only post-layout parasitic-extraction testbench generators
  or a power-corner sensitivity floor, none touching drawn geometry or the
  DRC/LVS harness).

**Deck named**: `gf180mcu` (`klt drc --deck gf180mcu`), `klt 0.2.0`,
`klayout` package `0.30.10`, pinned via `layout/toolchain.json` /
`layout/toolchain_pin.py`, git sha `56be937` at the latest run
(`repo_dirty: true` in that run's `toolchain.json` — expected, since the
record-minting commit itself was still being assembled when the run
executed; the content-hash check above is the actual freshness proof, not
this field).

**Conclusion — item 3: DRC clean, PASS.** All 89 committed verdicts read;
latest run fresh by two independent checks; deck identified.

---

## 2. LVS verdicts (T1 item 4)

**All 89 committed LVS verdicts and all 80 committed extraction verdicts
were read.**

| Run (`<record-id>`) | `match`/`mismatch` cells | `adc_block` & `comparator` |
|---|---|---|
| `20260801-093334-97bcbcf` | proof cells only (`match`/`mismatch` controls) | n/a — pre-block-layout |
| `20260801-225959-7866d03` | all real cells `match`, controls as expected | **`match` but `mismatch_count: 2`, `category_counts: {"topology": 2}`** — see below |
| `20260804-100640-688c2eb` | same | same 2-topology-warning pattern |
| `20260804-181107-c672a81` | same | same |
| `20260804-184401-9d8422d` | same (control `mismatch` count rises 10→15, an unrelated pinned-deck sharpening, see `layout/lvs/records/*.md`) | same |
| `20260804-205512-a0f8784` | same | same |
| `20260805-122516-e8017f2` | same | same |
| `20260806-193909-68ad582` | all real cells `match`, `mismatch_count: 0` | **clean — 0 topology findings** |
| `20260806-233251-56be937` (**latest**) | all real cells `match`, `mismatch_count: 0` | **clean — 0 topology findings** |

**Warnings-only LVS mismatches — not dropped from this record.** In every
run from `20260801-225959-7866d03` through `20260805-122516-e8017f2` (6 of
9 runs), `comparator.lvs.json` and `adc_block.lvs.json` both report
`status: match` (the overall verdict) alongside `mismatch_count: 2`,
`category_counts: {"topology": 2}`. Reading the `mismatches[]` array
(`layout/lvs/reports/20260805-122516-e8017f2/comparator.lvs.json`) shows
both are `"severity": "warning"`, `"category": "topology"`, "nets were
paired ambiguously; the comparer resolved it structurally" — the
comparator's differential input pair (`PREAMP_IN1`/`PREAMP_IN2`) sitting on
two internally-symmetric, ambiguously-nameable nets rather than a real
connectivity defect. This is a genuine warning-level LVS finding that
coexisted with an overall `match` verdict for six of nine runs — exactly
the kind of result `design-evidence-tiers.md`'s coverage-honesty
requirement says must travel with the verdict rather than be dropped. It is
resolved, not hidden: the two most recent runs (`20260806-193909-68ad582`,
`20260806-233251-56be937`) both report `mismatch_count: 0` for these two
cells, matching the LVS record's own narrative
(`layout/lvs/records/20260806-233251-56be937.md`: "RE-BASELINED at issue
#116 from 2 `topology` findings to 0 for the `vinp`/`vinn` floating-input
defect"). No `match`-with-nonzero-`mismatch_count` case exists anywhere
else in the 89 LVS reports (checked programmatically across all 89, not
sampled).

**Freshness of the latest run (`20260806-233251-56be937`)**: a direct
content-hash comparison of LVS verdicts is not meaningful the way it is for
DRC, because each `.lvs.json`'s `environment.layout_sha256` is the hash of
a *freshly re-extracted* netlist from `/tmp` at run time, not of the
committed GDS — and `klt extract`'s net numbering is not fully
deterministic across re-runs of the identical geometry (a known upstream
property, not specific to this run). The live re-run is therefore the
correct freshness check here, not a hash diff:

- `python3 layout/lvs/run_lvs.py --check` (same toolchain pin as above) was
  run directly in this worktree. Every extraction (`lvs_unit` plus all 9
  design cells) and every LVS case (`match`, `mismatch`, and all 9 design
  cells) reproduced its expected result with `[ok]` — 10 extractions, 11
  LVS cases, 0 unexpected results. This run did not hit the known
  net-numbering nondeterminism; it is a known occasional-flake source on
  this specific check (pre-existing on `main`, not a regression), noted
  here so a future spurious `--check` FAIL on this repo is read against
  that known cause rather than as new evidence of a stale/broken LVS state.
- Same git-history argument as DRC §1: no commit since the record-minting
  commit (`6c2b41c`) has touched drawn geometry, `design/*.spice`, or the
  LVS harness/reference generators.

**Engine named**: every one of the 89 `.lvs.json` reports carries
`"engine": "klayout"` (checked programmatically across all 89 — no
exceptions). This repo has **only one** LVS engine's verdict — there is no
second, independently-implemented engine (e.g. netgen) concurring, which
`design-evidence-tiers.md` notes would strengthen the LVS claim. That is a
real, standing coverage gap, not a defect in what exists (see §3 below).

**Conclusion — item 4: LVS match, PASS, with one disclosed and now-resolved
warning-level finding.** All 89 LVS + 80 extraction verdicts read; latest
run fresh by live re-run and git-history cross-check; engine named
(`klayout`, single-engine); the six-run topology-warning window on
`comparator`/`adc_block` is recorded rather than dropped, and its
resolution (issue #116) is cited.

---

## 3. Deck / block coverage gaps (enumerated, not dropped)

1. **Rule categories the `gf180mcu` deck does not check at all**, per
   `layout/README.md` "The gf180mcu deck: coverage": implant-specific
   rules, HV/5V-variant rules, density/antenna rules, and DFM guidelines.
   A `clean` DRC verdict on any cell in this repo says nothing about these
   — this is a deck limitation stated directly in the deck's own coverage
   note, not discovered by this pass.
2. **The SAR-logic sequencer has no layout, and therefore no DRC or LVS
   report, at all.** `design/sar-logic/` (the bit-cycle sequencer, CDAC
   switch drivers, and output register) is implemented only at
   [DR-0010](../spec/decision-records/DR-0010-mixed-signal-sim-strategy.md)'s
   "rung 1" abstraction — ideal XSPICE digital primitives — because the
   open gf180mcu PDK ships no 3.3 V standard-cell library to draw it with.
   `layout/adc-top/README.md` states this plainly: "the SAR-logic
   sequencer itself — **not drawn**." The reserved SAR-logic region (with
   its own guard ring) *is* drawn and *is* covered by the `adc_top`/
   `adc_block` DRC/LVS reports above, but the logic that would occupy it is
   not. This is a deliberate, previously-recorded design decision, not a
   gap newly found by this pass — restated here because item 3/4's
   acceptance criteria ask for block coverage gaps to be enumerated
   explicitly.
3. **Single LVS engine.** See §2 above — `klayout` only, no second engine's
   concurring verdict.
4. **One early run (`20260801-051207-4a0643b` / DRC,
   `20260801-093334-97bcbcf` / LVS) covers only the two proof cells**, not
   any real design cell — the block layout did not exist yet. Not a gap in
   current coverage (every later run supersedes it for the real cells), but
   listed for completeness since the record trail is append-only and this
   run is still committed.
5. **`design/cdac/` and `design/track-switch/` hold only schematics
   (`.sch`), no `.spice` netlist and no independent DRC/LVS report.** Their
   content is folded into and superseded by `design/adc-top/adc_top.spice`
   and the `adc_top`/`adc_block` layout, which *are* DRC/LVS-covered above;
   these two directories are earlier schematic-capture artifacts, not
   separately-verified blocks. Flagged for completeness, not treated as a
   missing report, since nothing downstream claims them as verified in
   isolation.

---

## 4. Spec-table ratification (precondition for item 5)

**Ratified.** [DR-0006](../spec/decision-records/DR-0006-spec-ratification.md)
("Target specification ratified, conditional on the #33 amendments"),
status `ratified`, dated 2026-07-31, decided by the operator (Robb, per
issue #1's engineering-ratification authority), recorded by a Builder agent
on issue #33. `README.md#target-specification` reflects this directly:

- Line 40: `Ratified 2026-07-31 ([DR-0006](spec/decision-records/DR-0006-spec-ratification.md), issue #1).`
- No `DRAFT` marking remains on the `## Target specification` heading or
  table (the pre-ratification heading read "DRAFT — engineering to ratify,
  see issue #1" per DR-0006's own "Spec lines affected" section; that text
  is gone from the current table).
- DR-0001 through DR-0005 (Input/drive, Reference source, Clocking, Device
  flavor, Interface scope) are cited as `ratified` by the same decision,
  each folded into a row or a condition on a row of the ratified table.

This satisfies T1 item 5's stated precondition ("requires the spec table
itself to be ratified"). It does **not** by itself close item 5 — item 5
also requires "every spec row at its bound corners, per-row pass/fail and
binding corner recorded," which is a large, separate PVT-campaign
verification effort (`README.md`'s own "Verification suite" row and
`sim/extracted-delta-summary.md` are the relevant starting points for that
follow-on work, out of scope here per #141's own scope statement).

**Conclusion — item 5 precondition: MET, cited.**

---

## Disposition

| #140 checklist item | Prior state | This record |
|---|---|---|
| 3. DRC clean | unverified — artifact presence only | **verdict read: PASS** — all 89 committed DRC verdicts clean where expected, latest run fresh by hash + live re-run + git history, deck (`gf180mcu`) identified, coverage gaps enumerated (§3) |
| 4. LVS clean | unverified — artifact presence only | **verdict read: PASS** — all 89 LVS + 80 extraction verdicts match/extracted where expected, latest run fresh by live re-run + git history, engine (`klayout`, single-engine) identified, one warning-level finding on `comparator`/`adc_block` disclosed and its resolution cited (not dropped) |
| 5. item-5 precondition (ratified spec table) | unverified | **MET** — DR-0006, ratified 2026-07-31, `README.md#target-specification` confirmed to carry no DRAFT marking. Item 5 itself (full PVT-vs-spec-row campaign) remains open, unaffected by this record |

Per CLAUDE.md ("no claim without a testbench," "`sim/` results are
append-only evidence"), this document is the append-only record of that
reading pass; a future re-run (e.g. after the next layout change) mints a
new record rather than editing this one.

A summary of these findings, and the corresponding checklist-state update,
was posted as a comment on #140 (this repo does not permit a Builder to
edit another issue's body directly).

- **Author** — Loom Builder agent (issue #141)
- **Reviewed artifacts** — `layout/drc/` (99 files, 89 per-cell verdicts
  across 9 runs), `layout/lvs/` (181 files, 89 LVS + 80 extraction verdicts
  across 9 runs), `spec/decision-records/DR-0006-spec-ratification.md`,
  `README.md#target-specification`
- **Toolchain used for live re-runs** — `klt 0.2.0`, `klayout` package
  `0.30.10`, per `layout/toolchain.json`
- **Timestamp** — 2026-08-11T00:35:20Z
- **Repo state** — `a51bd10` (origin/main)
