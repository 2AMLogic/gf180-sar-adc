# layout/ — DRC flow (klayout-tools)

Layout verification for this block is driven by
[klayout-tools](https://github.com/2AMLogic/klayout-tools) (`klt`), per
`CLAUDE.md`. This directory stands up the **DRC** half of that flow, proves
it on trivial cells built for the purpose, and records exactly where the
flow currently stops.

There is no block layout yet. This repo is still in the simulation-complete
phase — the design lives in `design/` and `sim/`. What is here is the
verification scaffolding that has to exist *before* real layout does, plus
the evidence that it works.

```
layout/
  README.md                         this file
  drc/
    run_drc.py                      reproducible klt drc invocation + assertions
    cells/
      cells.json                    proof cells and their expected reports
      gen_sw_unit.py                generator: positive control (klayout.db API)
      sw_unit.gds                   committed, byte-reproducible
      gen_uncovered_layer_probe.py  generator: negative control
      uncovered_layer_probe.gds     committed, byte-reproducible
    reports/<record-id>/            klt drc output, verbatim, append-only
      <cell>.drc.json                 the stable contract
      <cell>.drc.txt                  courtesy view
      toolchain.json                  what produced the reports
    records/<record-id>.md          append-only summary record
```

## Provenance: ported from gf180-bandgap

Per `CLAUDE.md` ("bootstrap from the sim-harness pattern... rather than
reinventing") and per issue #15's own instruction to check the sister repo
first, this bring-up is **ported from `2AMLogic/gf180-bandgap`'s
`layout/README.md` and `layout/drc/`**, which ran the same bring-up against
the same tool. The install path, the headless claim, the `klt drc`
invocation, the JSON-is-the-contract rule, the record-id scheme, the
seeded-violation pattern, and the append-only convention are kept identical
so the two repos read as one house style.

Divergences, each for a reason stated where it occurs:

1. **A negative control was added.** Upstream proves the deck catches a
   seeded violation. It does not prove the deck was *looking* — and for a
   curated starter deck that distinction is load-bearing here, because this
   block's precision element sits on layers the deck does not cover. See
   "The negative control" below.
2. **Expectations are asserted, not eyeballed.** `run_drc.py` fails the run
   when a cell's `rule_counts` stops matching `cells/cells.json`. Upstream's
   runner writes the report and leaves the comparison to a human reading the
   README. Making it an assertion is what lets a re-run function as a
   regression test rather than a screenshot.
3. **A summary record per run** (`records/<record-id>.md`), mirroring
   `sim/README.md`'s record format rather than only committing raw tool
   output. Same append-only rule, same `<record-id>` scheme; this just gives
   a run one file that states its own claim, toolchain, and result.
4. **The LVS section reaches a different conclusion**, because upstream's
   snapshot of the tool is out of date — see "LVS: deferred" below.

## Install `klt`

No PyPI release yet — install from the klayout-tools git repo:

```bash
uv tool install git+https://github.com/2AMLogic/klayout-tools
# or: pip install git+https://github.com/2AMLogic/klayout-tools

klt --version
klt drc --help
```

`klt drc` runs **fully headless**: it drives the pip `klayout` package's
native `klayout.db.Region` check primitives directly, with no dependency on
the standalone KLayout GUI/application binary, its `.drc`/`.lydrc` script
runner, Qt, or `DISPLAY` (klayout-tools `docs/cli/drc.md`). Confirmed for
this bring-up, not assumed: every command below ran to completion on a
machine where `command -v klayout` finds nothing at all. It also needs no
gf180mcu PDK install — the deck's thresholds are transcribed into
klayout-tools itself, so DRC here has none of the PDK dependency that keeps
`sim/`'s corner sweeps off the PR CI path.

## Running DRC

```bash
python3 layout/drc/run_drc.py            # run the proof cells, mint a record
python3 layout/drc/run_drc.py --check    # run and assert, write nothing
python3 layout/drc/run_drc.py --regen    # rebuild the GDS from its generators first
```

The underlying invocation is unremarkable, and you can always run it by
hand:

```bash
klt drc layout/drc/cells/sw_unit.gds --deck gf180mcu --format json
klt drc layout/drc/cells/sw_unit.gds --deck gf180mcu --format text
```

`--format json` is the committed, stable-contract report (klayout-tools
treats JSON as the API and text as a courtesy view — `docs/cli/drc.md`); the
`--format text` capture is kept alongside purely for human skimming.

`klt drc`'s own exit codes are `0` clean, `1` failed to run, `2` usage
error, `3` ran successfully with violations found. `run_drc.py` does **not**
pass those through: `0` there means "every cell reported exactly what it was
supposed to report", `2` means an expectation was missed, `1` means a
tooling problem. The positive-control cell is *supposed* to make `klt drc`
exit `3`.

### What `run_drc.py` adds over the bare command

- Runs every cell in `cells/cells.json` — positive and negative control.
- **Asserts** each cell's reported `rule_counts`, `status`, `violation_count`
  and `dbu_um` against that manifest, so a run that silently stops catching
  the seeded violations fails instead of looking green.
- Verifies the committed GDS hashes, so a report provably belongs to the
  committed geometry.
- Stamps the toolchain (`klt` version and path, `klayout` package version,
  interpreter, platform) and the repo git sha into the record. A DRC report
  without its deck version means nothing: the deck is upstream-owned and
  grows.
- Writes into a fresh `<record-id>` directory and refuses to overwrite an
  existing one.

### Limitations carried from klayout-tools

- **DRC is whole-layout, flattened per top cell.** There is no `--top <cell>`
  filter to scope a check to one cell inside a larger layout
  (`docs/cli/drc.md` § "Limitation: whole-layout, flattened"). Fine for the
  single-cell proofs here; it will matter as soon as a real hierarchical
  block layout exists.
- **Deck thresholds are authored in nanometres.** The release this bring-up
  ran against does not rescale them by the stream's database unit, so a
  layout written at a different dbu would silently be held to different
  numbers. Upstream has since fixed this
  ([#172](https://github.com/2AMLogic/klayout-tools/issues/172)), but both
  behaviours agree at dbu = 0.001 um, which is what the generators write and
  what `run_drc.py` asserts.
- **`klt` has no layout-generation verb** (the `klt gen` work is upstream
  epic [#152](https://github.com/2AMLogic/klayout-tools/issues/152)), so the
  proof cells are built directly against the `klayout.db` API — see below.

## The gf180mcu deck: coverage

The `gf180mcu` deck
(`klayout-tools/src/klayout_tools/decks/gf180mcu.py`) is a **curated starter
subset** of the GlobalFoundries 180nm MCU Design Rule Manual, not a
transcription of it. In the release this bring-up is pinned against it is 10
width/spacing/enclosure rules across exactly four layers:

| Layer     | GDS layer/datatype | Rules |
| --------- | ------------------ | ----- |
| `Comp`    | 22/0               | width, space, enclosing contact |
| `Poly2`   | 30/0               | width, space, enclosing contact |
| `Contact` | 33/0               | width (min half only), space |
| `Metal1`  | 34/0               | width, space |

Upstream `main` has since added `Nwell` (21/0) spacing/enclosure and one
`DRC_BJT` (127/5) rule, from
[#157](https://github.com/2AMLogic/klayout-tools/issues/157) — filed by the
sister bandgap block's bring-up. Neither layer appears in the proof cells
here, and a rule whose layer is absent from a stream is skipped, so both
cells produce **identical reports** on the pinned release and on `main`
(verified, not assumed). That is the property that lets these reports stay
meaningful across a deck bump.

Not covered, in the release pinned here or on `main`: the MiM capacitor
stack (`Metal4` 46/0, `FuseTop` 75/0, `Via4` 41/0, `Metal5` 81/0), the
intermediate routing metals (`Metal2` 36/0, `Metal3` 42/0), `MetalTop`,
implant-specific rules, HV/5V-variant rules, density/antenna rules, and the
DFM guidelines.

**This block's precision element is on the MiM stack** (see
`sim/device-characterization-report.md` §1 and
[DR-0011](../spec/decision-records/DR-0011-cdac-switching-scheme.md)), i.e.
squarely in the uncovered set. That is not a blocker for anything today —
there is no layout to check — but it does mean a future `klt drc --deck
gf180mcu` pass over a real capacitor array would be **silent about the most
matching-critical geometry in the block**, and would say so by reporting
`clean`. Hence the negative control, and hence the friction filed below.

## The proof cells

`klt` has no layout-generation verb, so both cells are built directly with
the `klayout.db` (`pya`-compatible) Python API, mirroring the construction
pattern in klayout-tools' own worked example
(`klayout-tools/examples/drc/generate.py`). The **generators are committed,
not just the GDS**, so the proof is reproducible if the deck's rules change
upstream: regenerate, re-run, mint a new record.

Both GDS files are byte-reproducible. That is not free — `klayout.db`'s
GDSII writer stamps wall-clock times into the `BGNLIB`/`BGNSTR` records by
default, so a plain `layout.write(path)` yields byte-different files every
run even for identical geometry. The generators write with
`SaveLayoutOptions.gds2_write_timestamps = False`, which makes the output a
pure function of the geometry and makes the `sha256` in `cells/cells.json` a
real integrity check.

### Positive control: `sw_unit`

A single NMOS-style switch device — active island, gate stripe with a
contact head, source/drain/gate contacts, metal1 straps — drawn on all four
covered layers, with **two seeded rule violations**:

| Seeded | Rule | DRM | Drawn | Minimum |
| --- | --- | --- | --- | --- |
| source contact row on too tight a pitch | `contact.space.1` | CO.2a | 0.20 um | 0.25 um |
| neighbouring poly2 stub too close to the gate head | `poly2.space.1` | PL.3a | 0.20 um | 0.24 um |

Everything else is drawn clean, so the report proves the deck catches real
violations without drowning them in incidental ones — the same
seeded-violation pattern as klayout-tools' own sky130 worked example. The
metal1 layer is deliberately left entirely clean as the in-cell control.

Both seeds sit on the device itself rather than on free-floating scrap
shapes, so each violation's reported bbox points at an actual feature.

It is a *DRC proof cell*, not a device: the geometry exercises the deck, it
is not a switch anyone should build. Nothing downstream should read it as
this block's real switch layout.

### The negative control: `uncovered_layer_probe`

A deliberately, grossly illegal layout drawn **entirely on layers the deck
has no rules for** — the MiM stack and the intermediate metals — violating
the PDK's own shipped rules (`MIMTM.1`/`.2`/`.3` in
`libs.tech/klayout/drc/rule_decks/mim_b.drc`) and drawing 0.05 um metal
bars. `klt drc --deck gf180mcu` reports `"status": "clean",
"violation_count": 0`, exit `0`.

**That "clean" is the finding, not a pass.** It is the concrete,
re-runnable demonstration that a green DRC report from this deck does not
by itself mean a layout was verified — it can equally mean nothing was
checked. `run_drc.py` asserts the clean result, which makes this control
fail loudly the day upstream closes the coverage gap. That is the useful
failure: it tells us the gap closed.

Without this cell, this bring-up would be able to claim only "the deck
catches what we seeded". With it, the bring-up also records what the deck
*cannot* catch — which, for this block, is the more consequential fact.

## Evidence convention: append-only

`layout/` DRC results follow the same append-only rule `sim/README.md`
documents for simulation evidence (`CLAUDE.md`: "`sim/` results are
append-only evidence"; this repo applies the same rule to `layout/`).

- A run mints a new `<record-id>` — `<YYYYMMDD>-<HHMMSS>-<short-git-sha>`,
  the same scheme `sim/` uses — and writes `reports/<record-id>/` plus
  `records/<record-id>.md`.
- Nothing under `reports/` or `records/` is ever edited or deleted. A re-run
  that corrects a mistake mints a new record; `run_drc.py` refuses outright
  to write into an existing record id.
- The record states its own claim, geometry provenance, deck, toolchain, and
  per-cell result, so it can be read years later without this README.

## LVS: deferred

**Not deferred for the reason issue #15 was curated with.** That curation
(2026-07-31, bootstrapped from the sister repo's same-day snapshot) recorded
that `klt lvs` did not exist and that the capability gap was filed
generically as
[`2AMLogic/klayout-tools#54`](https://github.com/2AMLogic/klayout-tools/issues/54).
Re-verified against klayout-tools `main` while implementing that issue, as it
instructed — **that is now out of date**:

- `klt extract` — extract a schematic-equivalent netlist from a stream —
  landed upstream (`023a564`,
  [#162](https://github.com/2AMLogic/klayout-tools/issues/162)).
- `klt lvs` — compare an extracted netlist against a reference — landed
  upstream (`e08f24f`,
  [#163](https://github.com/2AMLogic/klayout-tools/issues/163)).

`#54` is still open upstream despite both verbs shipping;
[`#164`](https://github.com/2AMLogic/klayout-tools/issues/164) (phase 4,
loop closure) is the live tracker. **No duplicate friction issue was filed
for this gap**, per #15's acceptance criteria — and none is warranted now
for a different reason: the gap is closing, not unaddressed.

LVS bring-up remains out of scope *here* on narrower grounds:

1. Neither verb is in the CLI release this directory is pinned against, so
   LVS bring-up starts with a toolchain bump, not a script.
2. There is still no block layout to run LVS on, and the trivial cells above
   carry no `Metal1` pin labels (34/10), which gf180mcu's extraction deck
   needs for net naming — so even the trivial proof needs new geometry.

#15's own descoping note said a follow-on issue picks up LVS bring-up proper
once the capability exists. It does, so that issue is filed: **#51**.

## Friction filed (klayout-tools tracker)

Per `CLAUDE.md`'s friction protocol, every klayout-tools gap this bring-up
surfaced is tracked generically on the public
[klayout-tools issue tracker](https://github.com/2AMLogic/klayout-tools/issues)
— tool capability only, never this design's specifics, per the repo's Tier 2
confidentiality rule.

| Gap | Upstream issue | Filed by this bring-up? |
| --- | --- | --- |
| Deck has no MiM capacitor or upper-metal (Metal2–Metal5) rule coverage | [#188](https://github.com/2AMLogic/klayout-tools/issues/188) | yes — new, distinct from the closed #157 |
| `klt drc` reports `clean` for a stream drawn entirely on uncovered layers; no coverage manifest | [#189](https://github.com/2AMLogic/klayout-tools/issues/189) | yes — generic across decks and PDKs |
| No netlist extraction / LVS capability | [#54](https://github.com/2AMLogic/klayout-tools/issues/54), epic [#153](https://github.com/2AMLogic/klayout-tools/issues/153) | no — already open, and largely closed by `klt extract`/`klt lvs` landing upstream |
| Deck has no well/tap or BJT rule coverage | [#157](https://github.com/2AMLogic/klayout-tools/issues/157) | no — filed by the sister bandgap block, since closed |
| `klt drc` ignores the stream's dbu when scaling thresholds | [#172](https://github.com/2AMLogic/klayout-tools/issues/172) | no — already filed and closed upstream |

Both new issues (#188, #189) describe the tool gap and its reproducer in
terms of PDK layer numbers and the PDK's own published rule ids. Neither
mentions this block, its architecture, its spec values, or any content from
this repository.

## Dependencies: none technical

Issue #15 carried a "hold: layout phase — do not start until the schematic
phase (#8–#12) closes" header, and #15's original text listed #8 as a
blocker ("needs at least one real netlist to LVS against").

**Neither applies to the DRC work in this directory, and it is worth being
explicit so a future reader does not mistake the hold for a real blocker.**
The proof cells are built directly against the `klayout.db` API and are
deliberately synthetic — they depend on nothing in `design/`, nothing in
`sim/`, and no ratified spec value. The hold was a *scheduling* choice
(exercise the flow against current tool versions near design completion),
not a technical gate. The "needs a netlist" blocker was specific to LVS,
which is not delivered here.

All of #8–#12 are closed in any case, so the scheduling hold is moot. The
distinction is recorded because it will come up again: #16 (floorplan) and
#17 (post-layout re-run) genuinely do depend on this flow being green, in
the other direction.

## Verifying this bring-up

```bash
# 1. Rebuild both proof cells and confirm they match the committed GDS
python3 layout/drc/run_drc.py --regen --check
git status --short layout/drc/cells/          # should be empty

# 2. Re-run from a clean shell and confirm the reports reproduce
python3 layout/drc/run_drc.py --check
#   sw_unit                violations {"contact.space.1": 1, "poly2.space.1": 1} [ok]
#   uncovered_layer_probe  clean      {}                                        [ok]
#   exit 0

# 3. Confirm it is genuinely headless
command -v klayout        # nothing -- there is no KLayout application here
echo "$DISPLAY"           # empty
python3 layout/drc/run_drc.py --check   # still passes
```

Step 2's output must match the committed `records/<record-id>.md` for the
same `klt` version. A mismatch is either a deck change upstream (mint a new
record, update `cells/cells.json`, and say so) or a real regression.
