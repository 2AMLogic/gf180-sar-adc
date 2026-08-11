# layout/ — DRC + LVS flow (klayout-tools)

Layout verification for this block is driven by
[klayout-tools](https://github.com/2AMLogic/klayout-tools) (`klt`), per
`CLAUDE.md`. This directory stands up the **DRC** and **LVS** halves of that
flow, proves each on trivial cells built for the purpose, and records
exactly where the flow currently stops.

**There is now a block layout**: `layout/adc-top/` (issue #57) holds the
drawn `design/adc-top/` block — 1024 common-centroid unit capacitors with
dummy rings, the 216-transistor decode banks, the two input sampling
switches, the comparator, guard rings and the reserved SAR-logic region —
DRC-clean and LVS-matched against `design/adc-top/adc_top.spice`. See
[`adc-top/README.md`](adc-top/README.md) for what that does and does not
prove, and for the as-drawn area tally.

The rest of this file is the verification scaffolding that had to exist
*before* real layout did, plus the evidence that it works. It is still the
place to read about the deck's coverage — which is what decides how much a
clean report on the block above is worth.

```
layout/
  README.md                         this file
  adc-top/                          THE BLOCK LAYOUT (issue #57) -- see its
                                    own README.md; its cells are listed in
                                    drc/cells/cells.json and
                                    lvs/cells/cells.json so their results
                                    land in the same two record trails
  toolchain.json                    pinned klt commit + required verbs (drc/extract/lvs)
  toolchain_pin.py                  the shared check that enforces that pin (both runners)
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
  lvs/
    run_lvs.py                      reproducible klt extract + klt lvs invocation + assertions
    cells/
      cells.json                    proof cell, LVS cases, and their expected reports
      gen_lvs_unit.py                generator: single-device cell with Metal1 pin labels
      lvs_unit.gds                   committed, byte-reproducible
      lvs_unit.spice                 committed, klt extract output (regenerated, never hand-edited)
      lvs_unit_ref_match.spice       hand-authored reference: positive control
      lvs_unit_ref_mismatch.spice    hand-authored reference: negative control (seeded W error)
      lvs_request_match.json        klt lvs request document: positive control
      lvs_request_mismatch.json     klt lvs request document: negative control
    reports/<record-id>/            klt extract/lvs output, verbatim, append-only
      lvs_unit.extract.json/.spice    the stable extraction contract
      <case>.lvs.json/.txt            the stable LVS contract per case
      toolchain.json                  what produced the reports
    records/<record-id>.md          append-only summary record
  records/<record-id>.md            append-only cross-cutting verification
                                    records that read (not re-run) both the
                                    drc/ and lvs/ trails above plus spec/
                                    ratification status -- e.g. issue #141's
                                    per-report freshness+verdict audit
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
4. **LVS has no upstream precedent to port from.** `2AMLogic/gf180-bandgap`
   has no `layout/lvs/` as of this writing (checked directly while
   implementing #51) — the DRC-only snapshot ported in point 1 above simply
   predates `klt extract`/`klt lvs` existing anywhere. This bring-up (see
   "LVS: standing up the flow" below) is therefore original to this repo,
   not ported; a later gf180-bandgap LVS bring-up would be the one
   borrowing from here, not the reverse.

## Install `klt`

No PyPI release yet — install from the klayout-tools git repo, **pinned to
an exact commit** — see `../toolchain.json`'s `_comment` for why floating
against `main` is unsafe for this repo (an upstream deck gaining coverage
is a change this repo's committed negative controls and manifests have to
absorb deliberately, in one reviewed change, not silently on the next
reinstall — which is exactly what issue #70 did):

```bash
uv tool install git+https://github.com/2AMLogic/klayout-tools@af5791b557fc7c669c3981335a294256ccf37e6f
# or: pip install git+https://github.com/2AMLogic/klayout-tools@af5791b557fc7c669c3981335a294256ccf37e6f
# (that commit is `layout/toolchain.json`'s `klt_install`/`klt_last_verified_commit`
# -- treat this README's copy as a courtesy and that file as the source of truth)

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
- Probes `klt`'s own capabilities against `../toolchain.json`'s
  `klt_required_commands` before running anything — the same shared check
  `run_lvs.py` makes (`../toolchain_pin.py`), so a `klt` that has drifted off
  the pin fails both runners the same loud, actionable way.
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
  single-cell proofs here, and `adc-top/` works within it rather than around
  it: every block cell is listed in `drc/cells/cells.json` as its own
  stream with its own expected report, so each is checked whole rather than
  filtered out of a larger one.
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

## Running LVS

```bash
python3 layout/lvs/run_lvs.py            # extract + run both LVS cases, mint a record
python3 layout/lvs/run_lvs.py --check    # run and assert, write nothing
python3 layout/lvs/run_lvs.py --regen    # rebuild the GDS and re-extract its netlist first
```

The underlying invocation is unremarkable, and you can always run it by
hand — each `klt lvs` request document under `layout/lvs/cells/` also
repeats its own stand-alone command in its header comment:

```bash
klt extract layout/lvs/cells/lvs_unit.gds --deck gf180mcu --format json
klt lvs layout/lvs/cells/lvs_request_match.json --format json     # positive control
klt lvs layout/lvs/cells/lvs_request_mismatch.json --format json  # negative control
```

Both `klt extract` and `klt lvs` are, like `klt drc`, **fully headless** —
`docs/cli/lvs.md`/`docs/cli/extract.md` document the same no-GUI/no-`DISPLAY`
contract, confirmed the same way DRC's was: every command above ran to
completion with no `klayout` application binary and no `$DISPLAY` on the
machine that produced `records/`'s LVS record.

`klt extract`'s own exit codes are `0` extracted, `1` failed to run/bad deck.
`klt lvs`'s are `0` match, `3` mismatch found, `1` an actual error (unreadable
request/netlist, unknown deck). `run_lvs.py` does **not** pass those through
directly: `0` there means "extraction and every LVS case reported exactly
what this bring-up expects", `2` means an expectation was missed, `1` means a
tooling problem. The negative-control case is *supposed* to make `klt lvs`
exit `3` — a `0` there would mean the seeded mismatch stopped being caught.

### What `run_lvs.py` adds over the bare commands

- Runs `klt extract` live on every invocation (not only `--regen`), so a run
  proves the verb itself, not just its previously-cached output.
- **Asserts** the extraction report's device/net/pin fields — crucially
  `devices[].nets`, which is what proves the Metal1 (34/10) pin labels
  actually named the nets — against `cells/cells.json`.
- **Asserts** each `klt lvs` case's `status`/`mismatch_count`/
  `category_counts` against that manifest, for both the positive control (a
  genuine match) and the negative control (a genuine, seeded mismatch), so a
  run that silently stops catching the seeded defect fails instead of
  looking green.
- Verifies every committed artifact's sha256 (GDS, extracted netlist,
  reference netlists, request documents), so a report provably belongs to
  the committed geometry and netlists.
- Probes `klt`'s own capabilities against `../toolchain.json`'s
  `klt_required_commands` before running anything (the shared
  `../toolchain_pin.py` check, also used by `run_drc.py`), and stamps the
  toolchain (`klt` version and path, `klayout` package version, interpreter,
  platform) and the repo git sha into the record.
- Writes into a fresh `<record-id>` directory and refuses to overwrite an
  existing one.

### Why a sibling cell (`lvs_unit`) and not an extension of `sw_unit`

Issue #51 offered either option. `layout/drc/cells/sw_unit` carries two
seeded *DRC* violations (a too-tight source-contact pitch and a
free-floating poly2 stub) that are irrelevant to a connectivity proof — and
the floating poly2 stub is actively unwelcome for extraction: it touches no
contact and no other poly, so `klt extract` turns it into its own
disconnected net with no device terminals, which would show up as a
spurious extra net on the layout side of every LVS comparison. `lvs_unit`
(`cells/gen_lvs_unit.py`) is instead a clean, purpose-built single-NMOS cell
— no seeded DRC violations, since DRC is not what it proves — plus the
Metal1 (34/10) pin labels (`S`/`D`/`G`) gf180mcu's `EXTRACTION_DECK` needs
for net naming, which `sw_unit` has never carried.

### Documented gf180mcu extraction approximations

The curated `gf180mcu` extraction deck (unlike a full foundry LVS deck) has
**no distinct substrate/well-tie layer**, so body terminals are not derived
from drawn geometry:

- The **NMOS body** is tied to the deck's global `substrate_net` (named
  `"vsubs"`) rather than to any drawn tap — see `lvs_unit`'s extracted
  netlist (`M$1 D G S vsubs nfet ...`) and `gen_lvs_unit.py`'s own note.
- The **PMOS body**, symmetrically, lands on an anonymous, deck-internal net
  rather than a named one (there is no PMOS device in `lvs_unit` — an
  n-type-only proof cell, per the "sibling cell" rationale above — so this
  bring-up does not exercise it directly, but a later reader extracting a
  cell with a PMOS should expect it and not read it as a bug).

Both are read as **documented behavior of the curated deck**, not defects in
any netlist this flow produces — the same posture `layout/README.md`
already takes toward the DRC deck's curated (not exhaustive) rule coverage.

### A real engine quirk this bring-up worked around, not filed as new friction

Pointing `klt lvs`'s `layout` side at `{"file": ..., "deck": ...}` (inline
extraction) instead of a pre-extracted netlist produces a spurious
`topology`/`severity: "error"` `device_class_mismatch` finding here — even
when the layout and reference are genuinely equivalent — because `klt
extract` unconditionally registers *both* the `nfet` and `pfet` device
classes regardless of whether either polarity actually appears in the
layout (`lvs_unit` is n-type only), and the unused class then fails to pair
during comparison. Reproduced directly while implementing #51 (see
`cells/lvs_request_match.json`'s own header comment for the exact
`status`/`mismatch_count` observed).

**Not filed as new friction**: this is the same root cause already filed —
by a different bring-up (klayout-tools issue
[#196](https://github.com/2AMLogic/klayout-tools/issues/196)) — as
[`#201`](https://github.com/2AMLogic/klayout-tools/issues/201), and already
fixed upstream (severity downgraded to `warning`, PR
[`#204`](https://github.com/2AMLogic/klayout-tools/pull/204), merged after
this repo's pinned commit — see `../toolchain.json` for why this pin does
not float past it). `run_lvs.py`'s request documents point both sides of
each LVS case at pre-extracted/hand-authored SPICE files instead of using
inline extraction, which sidesteps the artifact entirely (both sides then
go through the same `NetlistSpiceReader` parser) rather than depending on
that fix landing in this repo's pinned `klt`.

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

### That gap is now closed (issue #70)

Everything above this heading describes the deck as of the **previous** pin
(`e08f24f`), and is left as recorded. The pin is now `af5791b`, and the MiM
stack and the intermediate metals are covered:

| Layer | GDS layer/datatype | Rules added since `e08f24f` |
| --- | --- | --- |
| `Metal2` | 36/0 | width, space (`M2.1`/`M2.2a`) |
| `Metal3` | 42/0 | width, space (`M3.1`/`M3.2a`) |
| `Metal4` | 46/0 | MiM bottom-plate space (`MIMTM.1`), overlap of `FuseTop` (`MIMTM.3`), overlap of `Via4` (`MIMTM.2`, scoped to the derived virtual bottom plate) |
| `Metal5` | 81/0 | width, space (`M5.1`/`M5.2a`) |
| `MetalTop` | 53/0 | width, space (`MT.1`/`MT.2a`) |

Two things followed immediately, both recorded rather than argued:

* **the negative control went red, as designed.**
  `uncovered_layer_probe` — built to prove the deck was *not* looking at
  these layers — now reports four real violations. `cells/cells.json`'s
  expectations for it are re-baselined from `clean` to those four rule ids
  in the same change that moved the pin, which is what
  `../toolchain.json`'s own note said a future bump would have to do.
* **the block layout went red too, and was wrong.** `adc_top` reported
  4896 `mim.enclosing.fusetop.1` violations the first time the rule ran
  against it: every one of its 1224 unit-capacitor footprints drew 0.3 µm
  of Metal4-over-FuseTop overlap against `MIMTM.3`'s 0.6 µm. That is the
  defect this deck coverage existed to find, found on the first run. Fixed
  in `layout/adc-top/lib/geometry.py`; see
  [`adc-top/README.md`](adc-top/README.md)'s "The MiM stack".

Still not covered: implant-specific rules, HV/5V-variant rules,
density/antenna rules, and the DFM guidelines.

**This block's precision element is on the MiM stack** (see
`sim/device-characterization-report.md` §1 and
[DR-0011](../spec/decision-records/DR-0011-cdac-switching-scheme.md)) — so
the closure above is the single most valuable deck change this repo has
consumed. The paragraph that used to stand here said a clean report over a
real capacitor array would be *silent about the most matching-critical
geometry in the block*. It is no longer silent, and the first thing it said
was that the array was illegal (4896 `mim.enclosing.fusetop.1` violations,
fixed in `layout/adc-top/lib/geometry.py`, issue #70). Read every `clean` on
`adc_top`/`adc_block` with the coverage's remaining limit in mind, though:
`adc-top/README.md` §"What is and is not verified" keeps DRC-clean geometry
and the array's units extracting as capacitor *devices* as two separate
claims. Both now hold across the array (issues #85/#86 wired both plates of
all 1024 real units, so `klt lvs` matches them), but the second one carries
the extraction deck's area-only MiM model with it — 14.7316 fF per unit
against the PDK model card's 17.245 fF — which is stated in that section
rather than folded into the `clean`.

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

**That "clean" was the finding, not a pass.** It was the concrete,
re-runnable demonstration that a green DRC report from this deck did not by
itself mean a layout was verified — it could equally mean nothing was
checked. `run_drc.py` asserted the clean result, which made this control
fail loudly the day upstream closed the coverage gap. That is the useful
failure: it tells us the gap closed.

**It fired.** At the issue #70 pin bump this cell stopped reporting `clean`
and started reporting

```
{"metal2.width.1": 1, "metal3.width.1": 1,
 "mim.enclosing.fusetop.1": 5, "mim.space.1": 1}
```

so `cells/cells.json`'s expectation for it is re-baselined from `{}` to
exactly those four counts, and the control's role changes from "records a
gap" to "records the closure". Three of the four failures
`gen_uncovered_layer_probe.py`'s docstring predicted are now caught by name
(`MIMTM.1`, `MIMTM.3`, and the sub-minimum Metal2/Metal3 widths). The
fourth, `MIMTM.2`, IS in the deck and IS evaluated here (it is absent from
the report's `rules_skipped`) but does not fire on this cell: it is scoped
to the derived "virtual bottom plate" (`FuseTop` sized by 1.06 µm,
intersected with `Metal4`), and this probe's `FuseTop` hangs entirely off
its `Metal4`, so its via straddles the edge of a region the derived layer
does not cover. Confirmed not to be a deck defect by a scratch probe drawn
as a well-formed MiM stack with only the Via4 overlap wrong, which the same
rule catches — recorded in the record for that run.

Without this cell, this bring-up would have been able to claim only "the
deck catches what we seeded". With it, the bring-up recorded what the deck
*could not* catch, and then recorded the day it could — which for this
block was the day its capacitor array was found to be illegal.

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

The bring-up record for this flow is
[`records/20260801-051207-4a0643b.md`](drc/records/20260801-051207-4a0643b.md)
— `klt 0.1.0`, `klayout` 0.30.10, both cells matching. Later records
accumulate beside it; this pointer is not maintained as a "latest" link,
because the whole point is that no record supersedes another by overwriting
it.

## LVS: standing up the flow (issue #51)

**No longer deferred.** Issue #15's curation (2026-07-31) recorded that `klt
lvs` did not exist and filed the capability gap generically as
[`2AMLogic/klayout-tools#54`](https://github.com/2AMLogic/klayout-tools/issues/54).
That gap has since closed:

- `klt extract` — extract a schematic-equivalent netlist from a stream —
  landed upstream (`023a564`,
  [#162](https://github.com/2AMLogic/klayout-tools/issues/162)).
- `klt lvs` — compare an extracted netlist against a reference — landed
  upstream (`e08f24f`,
  [#163](https://github.com/2AMLogic/klayout-tools/issues/163)).

`#54` is still open upstream despite both verbs shipping;
[`#164`](https://github.com/2AMLogic/klayout-tools/issues/164) (phase 4,
loop closure) is the live tracker. This bring-up needed no duplicate
friction issue for the capability itself — the gap had already closed by
the time #51 was worked.

**Outcome: the flow is stood up and proven, per `layout/lvs/`** (see
"Running LVS" above for the runner, and "Documented gf180mcu extraction
approximations" / "A real engine quirk this bring-up worked around" above
for the two caveats a later reader needs). Summary:

- **Toolchain bump** — `layout/toolchain.json` pins `klt` to an exact
  upstream commit with `extract`/`lvs`/`drc` all present, checked by both
  `run_drc.py` and `run_lvs.py` — one shared probe
  (`layout/toolchain_pin.py`), run before either does anything else, so
  neither can drift off the pin silently or away from the other. See that
  file's `_comment` for why this is a capability list (not a version
  string) *and* why the install is pinned to an exact commit rather than
  left floating against `main`. *(That pin was
  `e08f24f88095f1cf99471a841e505b7a10b1313d` for #51, deliberately chosen
  to sit before `1d5fc60` so issue #15's DRC negative control still held.
  Issue #70 moved it forward across `1d5fc60` and re-baselined that control
  in the same change — see "That gap is now closed" above.)*
- **Proof cell** — `layout/lvs/cells/lvs_unit` (a sibling to
  `layout/drc/cells/sw_unit`, not an extension of it — see "Why a sibling
  cell" above), a single NMOS device with Metal1 (34/10) `S`/`D`/`G` pin
  labels, extracted and asserted against `cells/cells.json`.
- **Positive control** — the extracted `lvs_unit` netlist against a
  hand-authored matching reference: `klt lvs` reports `status: "match"`,
  `mismatch_count: 0`.
- **Negative control** — the *same* extracted netlist against a
  hand-authored reference with a deliberately seeded channel-width error
  (1.2 µm → 2.4 µm, the kind of schematic/layout-edit-forgot-the-other-side
  mistake this is meant to catch): `klt lvs` reports `status: "mismatch"`,
  exit `3` — a real, structured finding, not an empty-vs-empty false match.
  *(#51 recorded `mismatch_count: 10`, all of it collateral —
  `device.unmatched: 2`, `net.unmatched: 8`. At the issue #70 pin the
  comparer NAMES the seeded defect instead: 15 findings, of which 5 are
  `device.property` on `w_um` and the four drawn-width-derived
  `as`/`ad`/`ps`/`pd` values. Same seed, sharper control; re-baselined in
  `lvs/cells/cells.json`.)*
- **Evidence** — [`records/20260801-093334-97bcbcf.md`](lvs/records/20260801-093334-97bcbcf.md),
  same append-only convention as DRC's.

LVS against a real block netlist was out of scope for #51 and is **now
done**: issue #57's `layout/adc-top/` extracts and LVS-matches the full
224-transistor `design/adc-top/adc_top.spice` block (and a 251-transistor
assembled block including the comparator) through this same runner, from the
`block_extractions` and block `lvs_cases` entries in
`lvs/cells/cells.json`. Parasitic extraction remains out of scope here and
is #17's.

## Friction filed (klayout-tools tracker)

Per `CLAUDE.md`'s friction protocol, every klayout-tools gap this bring-up
surfaced is tracked generically on the public
[klayout-tools issue tracker](https://github.com/2AMLogic/klayout-tools/issues)
— tool capability only, never this design's specifics. That is the friction
protocol's own rule ("describe the tool gap, not this design", `CLAUDE.md`), so
the fix serves everyone on the open gf180mcu flow rather than just this block;
it is not a confidentiality constraint, this repository being public.

| Gap | Upstream issue | Filed by this bring-up? |
| --- | --- | --- |
| MiM capacitor device model is plate-**area** only, with no perimeter/fringe term, so extracted `C` is systematically low against the PDK's own model card (−14.6 % on a unit-sized plate, worse as plates shrink) | [#512](https://github.com/2AMLogic/klayout-tools/issues/512) | **yes — new** (issue #70); **closed upstream and now in this repo's pin** (issue #116) — the deck carries the model card's two-term formula and the drawn unit cap extracts at 17.2449 fF against 14.7316 fF before, so the delta this row reports is gone |
| Deck has no MiM capacitor or upper-metal (Metal2–Metal5) rule coverage | [#188](https://github.com/2AMLogic/klayout-tools/issues/188) | yes — filed by #15, distinct from the closed #157; **closed upstream and now in this repo's pin**, which is what found the block's 4896 `MIMTM.3` violations |
| `klt drc` reports `clean` for a stream drawn entirely on uncovered layers; no coverage manifest | [#189](https://github.com/2AMLogic/klayout-tools/issues/189) | yes — generic across decks and PDKs; the deck now emits a `coverage` block naming checked layers and skipped rules, which this repo reads |
| No netlist extraction / LVS capability | [#54](https://github.com/2AMLogic/klayout-tools/issues/54), epic [#153](https://github.com/2AMLogic/klayout-tools/issues/153) | no — already open, and largely closed by `klt extract`/`klt lvs` landing upstream |
| Deck has no well/tap or BJT rule coverage | [#157](https://github.com/2AMLogic/klayout-tools/issues/157) | no — filed by the sister bandgap block, since closed |
| `klt drc` ignores the stream's dbu when scaling thresholds | [#172](https://github.com/2AMLogic/klayout-tools/issues/172) | no — already filed and closed upstream |
| `klt lvs` reports a spurious `device_class_mismatch` when extraction registers an unused device class (issue #51's bring-up) | [#201](https://github.com/2AMLogic/klayout-tools/issues/201) | no — independently re-encountered while implementing #51, but already filed by a different bring-up and already fixed upstream (PR [#204](https://github.com/2AMLogic/klayout-tools/pull/204)); worked around here instead of depending on the fix landing in this repo's pinned commit (see "Running LVS" above) |
| `klt lvs` has no device-merge step, so a folded / split / interleaved matched device cannot be compared against a lumped schematic device (issue #57's block layout) | [#261](https://github.com/2AMLogic/klayout-tools/issues/261) | **yes** — new, and the gap that most constrains this block's matching layout (see [`adc-top/README.md`](adc-top/README.md)) |
| Extraction deck declares one metal level and no vias, forcing single-metal planar routing on any block that wants to LVS | [#220](https://github.com/2AMLogic/klayout-tools/issues/220) | no — already filed and closed upstream; independently re-encountered by #57, and **the fix is now in this repo's pin** (Metal1–Metal5 / Via1–Via4), which is what let the MiM stack's plate wiring be drawn at all |
| Extraction decks recognise MOS only — no capacitor or resistor device class | [#219](https://github.com/2AMLogic/klayout-tools/issues/219), [#222](https://github.com/2AMLogic/klayout-tools/issues/222), [#225](https://github.com/2AMLogic/klayout-tools/issues/225) | no — already tracked upstream; **the capacitor half is now in the pin and used** (issue #70's `adc_cdac_cell` extracts a real `cap_mim_2f0_m4m5_noshield`). The resistor half exists too but recognises a resistor by markers this layout does not draw, so the comparator's load resistors are still conductors here |
| Extracted parasitic resistance has no in-path or distributed model — each net's R is a dead-end shunt behind the net's own C, so no device current flows through any extracted resistance and every resistance-sensitive post-layout number is identically the schematic one | [#592](https://github.com/2AMLogic/klayout-tools/issues/592) (child of the documentation-only [#338](https://github.com/2AMLogic/klayout-tools/issues/338)) | **yes — new** (issue #89's structural audit); **closed upstream via [#593](https://github.com/2AMLogic/klayout-tools/pull/593) and now in this repo's pin** (issue #116) — the first non-zero post-layout switch-R_on delta this project has been able to measure, +77.4 Ω, followed immediately |
| No way to select WHICH of several shared-geometry sheet-rho flavours a resistor family extracts as, so a correctly-marked body of any non-default flavour has no recognizer and is absorbed into interconnect — **shorting its own terminals**, which for a resistively-loaded analog stage removes the stage rather than perturbing a number | [#595](https://github.com/2AMLogic/klayout-tools/issues/595) (child of the closed [#299](https://github.com/2AMLogic/klayout-tools/issues/299)) | **yes — new** (issue #116); **narrowed by issue #118**. #118 drew the missing `SAB`/`RES_MK`/`Resistor` markers so the preamp's load resistors extract as real devices at the deck's only selectable flavour (`ppolyf_u_1k`), and `ADC_BLOCK` now converts. `#595` staying open no longer means the loads short or the differential output is zero — it means only that there is still no flavour-selection knob upstream: this repo worked around the gap by resizing its resistors to the `ppolyf_u_1k`/150 µm geometry (`design/comparator/comparator.spice`) rather than depending on a fix that would let the deck select the schematic's original `ppolyf_u_2k` assumption |

Issue #70 filed one new issue (#512, the missing fringe term): the deck can
now recognise a MiM capacitor, but the value it reports for one is not the
value the PDK's own model card gives for the same drawn geometry, and a
caller has no way to express the difference. It is the first friction this
repo has filed about an extracted *number* rather than a missing
capability.

Issue #57's block layout filed one new issue (#261, the device-merge gap):
it is the difference between drawing a matched pair the way matching
requires and being able to prove the drawn block is the netlist. The other
three gaps it hit were all already tracked upstream.

Issue #51's LVS bring-up filed no new friction issue: the one real engine
quirk it surfaced (the row above) turned out to already be tracked and
already fixed upstream, just not yet in the commit this repo pins against
(see `../toolchain.json` for why that pin does not float to pick the fix
up automatically).

Both new DRC-era issues (#188, #189) describe the tool gap and its
reproducer in terms of PDK layer numbers and the PDK's own published rule
ids, and #512 does the same with the open PDK's own published model-card
coefficients and four generic square plate sizes. None of the rows above
mention this block, its architecture, its spec values, or any content from
this repository.

## Dependencies: none technical

Issue #15 carried a "hold: layout phase — do not start until the schematic
phase (#8–#12) closes" header, and #15's original text listed #8 as a
blocker ("needs at least one real netlist to LVS against").

**Neither applies to the DRC or LVS work in this directory, and it is worth
being explicit so a future reader does not mistake the hold for a real
blocker.** Every proof cell (DRC's and LVS's alike) is built directly
against the `klayout.db` API and is deliberately synthetic — none depends
on anything in `design/`, anything in `sim/`, or any ratified spec value.
The hold was a *scheduling* choice (exercise the flow against current tool
versions near design completion), not a technical gate. The "needs a
netlist" blocker in #15's original text meant a *real block* netlist to LVS
against — #51 (this directory's LVS bring-up) proves the flow on a
hand-authored reference netlist for a trivial synthetic cell instead, which
needs no block netlist at all; a real block netlist remains #16/#17's
scope, unchanged.

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

# 4. Same three checks for LVS
python3 layout/lvs/run_lvs.py --regen --check
git status --short layout/lvs/cells/          # should be empty

python3 layout/lvs/run_lvs.py --check
#   extract lvs_unit         devices=1 nets=4 [ok]
#   lvs match                match      mismatches=0 [ok]
#   lvs mismatch             mismatch   mismatches=10 [ok]
#   exit 0

command -v klayout && echo "$DISPLAY"   # still nothing/empty
python3 layout/lvs/run_lvs.py --check   # still passes
```

Step 2's/step 4's output must match the committed `records/<record-id>.md`
for the same `klt` version (both directories keep their own `records/`).
A mismatch is either a deck/engine change upstream (mint a new record,
update `cells/cells.json`, and say so) or a real regression.
