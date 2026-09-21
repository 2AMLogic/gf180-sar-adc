# `layout/erc/` — structural power delivery (`klt erc`)

**Is the supply actually connected to what it powers?** That question is T1
item 11 (*Power delivery (structural)*, added to klayout-tools'
`docs/design-evidence-tiers.md` by [klayout-tools#2025][2025] on
2026-09-17), and this directory is where this block answers it. Issue #330.

It is the **structural** question only. IR drop and electromigration
(`klt power`) are deliberately outside item 11 and outside this directory —
that is the *analysis* question, and no `klt power` run is cited by any T1
item today.

```
layout/erc/
  README.md                  this file
  adc_block.supply-spec.json THE item-11 artifact: the `klt erc` supply spec
  toolchain.json             pinned klt build, asserted before anything runs
  cases.json                 what run_erc.py runs and what it asserts
  run_erc.py                 reproducible invocation + assertions + record
  controls/                  the specs that make the clean verdict mean something
    adc_block.unconnected-net-control.json   negative control
    adc_block.tie-bare.known-gap.json        known gap (A)
    adc_block.tie-narrowed.known-gap.json    known gap (B)
    adc_block.no-devices.known-gap.json      known gap (C)
  reports/<record-id>/       klt erc output, verbatim, append-only
  records/<record-id>.md     append-only summary record
```

## Install and run

`klt erc` here needs a **newer `klt` than `layout/toolchain.json` pins** —
see `toolchain.json`'s `_comment` for the seven upstream changes involved
and why this flow carries its own pin rather than re-baselining the DRC/LVS
evidence trail. `run_erc.py` refuses to run under any other build.

```bash
pip install 'git+https://github.com/2AMLogic/klayout-tools@67d617f899c7fb941b86cfc85491f75b91ae1176'

python3 layout/erc/run_erc.py            # run, assert, mint a record
python3 layout/erc/run_erc.py --check    # run, assert, write nothing
python3 layout/erc/run_erc.py --verify   # re-derive the committed reports, no klt
```

Headless: no KLayout GUI, no gf180mcu PDK install. `--verify` is stdlib-only
and is what CI runs — it re-reads the committed reports, re-asserts every
expectation in `cases.json` against them, and re-hashes the committed GDS
and every spec, so a report that stops describing the committed geometry (or
a spec edited after its report was minted) goes red instead of rotting.

## What the committed run says

Against `layout/adc-top/adc_block.gds` (top cell `ADC_BLOCK`,
sha256 `b4cf6ad7…`, the same bytes `signoff/gf180-sar-adc.manifest.json`
pins for this block's DRC citation):

| Case | `status` | `erc_status` | findings | exit |
|---|---|---|---|---|
| `adc_block.supply` (the artifact) | `not_checked` | `clean` | none | 4 |
| `adc_block.unconnected-net-control` | `violations` | `violations` | 1 × `erc.unconnected_net` | 3 |
| `adc_block.tie-bare.known-gap` | `not_checked` | `clean_partial` | none, 1 skipped | 4 |
| `adc_block.tie-narrowed.known-gap` | `violations` | `violations` | 25 × `erc.missing_tie` | 3 |
| `adc_block.no-devices.known-gap` | `not_checked` | `clean` | none | 4 |

**The item-11 verdict is not the `status` column.** `status` is the
*antenna* half's roll-up, and `klt erc` ships an antenna-ratio table for
sky130 only — so on gf180mcu no level is ever compared against a limit and
`status: "not_checked"` / exit `4` is the expected outcome for **every**
run, clean layout or not. The connectivity half's own verdict is
`erc_status`, and the item grades the supply-continuity rules directly
rather than either roll-up.

What the supply case establishes:

- **`vdd` is exactly one electrical island**, and **`vss` is exactly one
  electrical island**, and they are not the same island. Zero
  `erc.unconnected_net` (which fires on zero matches *and* on more than
  one) and zero `erc.supply_short`.
- Those islands span the whole block: the merged GDS carries four `vdd`
  labels and four `vss` labels, one pair in each of `ADC_DECODE_BANK_N`,
  `ADC_DECODE_BANK_P`, `ADC_TOP_SW` and `COMPARATOR`, and all four of each
  land on one node. On Metal1 alone the `vdd` rail is three disjoint
  polygons — it is the **Poly2 risers** of this block's Metal1-trunk /
  Poly2-riser channel router that join them. Per-layer, the `vdd` island
  carries 643.8 µm² of Metal1 and 376.9 µm² of Poly2 (`vss`: 780.4 and
  133.7), and **zero** area on Metal2–Metal5. Confirming that rather than
  assuming it is exactly what a structural check is for; the IR/EM
  consequence of distributing a rail through poly is item 11's sibling
  question, not item 11's, and is tracked separately (see "Real findings"
  below).
- 142 gate nets, identified as `poly ∩ diff` — the comparator's two poly
  load-resistor bodies and any other gate-oxide-free poly are excluded from
  the gate set rather than reported with non-physical antenna ratios.

## What it does **not** say: `erc.missing_tie` was never computed

The supply spec declares **no `ties[]`**. Per `klt erc`'s own contract
(*"Omitted entirely → `erc.missing_tie` is never computed"*), the zero
`erc.missing_tie` count in the committed report is **an absence of
evidence, not evidence of absence**. Half of item 11's pass condition is
therefore unanswered by this run, and any claim built on it must say so.

The omission is a measured conclusion, not a preference. Both alternatives
are committed as controls and re-run on every `run_erc.py`:

- **(A) a bare `tap_layer`** — the only form this stream can express — is
  classified *degenerate* by [klayout-tools#2199][2199]: a bare `COMP`
  tap layer matches every source/drain contact inside the well, so `klt
  erc` records the work as skipped (`degenerate_tap_declaration`) and
  downgrades `erc_status` to `clean_partial` rather than letting a clean
  verdict stand for a check that could not tell a tap from a source/drain
  contact.
- **(B) the real gf180mcu tap boolean** (`COMP ∩ Nplus`, via
  `tap_requires`) has nothing to intersect: **`ADC_BLOCK` draws no implant
  layers at all** — `Nplus` 32/0 and `Pplus` 31/0 have zero shapes in this
  GDS, because this generated full-custom flow leaves implants to be
  derived downstream. The result is 25 `erc.missing_tie` findings, one per
  drawn `Nwell` shape, **every one of them false**.
- `tap_is_dedicated` does not apply (gf180mcu has no tap-only layer, and
  this block draws no tub-contact marker), and a substrate tie cannot be
  declared at all (`well_layer` requires drawn geometry; the p-substrate is
  not drawn).

Note that [klayout-tools#2169][2169] — the false `erc.supply_short` a
`ties[]` declaration used to induce on a routed design, which is the reason
the sibling `gf180-drone-fc` omits `ties[]` — is **fixed** in the build
`toolchain.json` pins: ties are evaluated in their own isolated extraction
now and cannot affect `gates[]` or the `nets[]` findings. It is not the
reason for this omission. The implant-free stream is.

### The well-tie evidence that stands in — and what it does not cover

| Evidence | What it does establish | What it does not |
|---|---|---|
| `layout/adc-top/lib/geometry.py:draw_guard_ring` + the DRC record for `adc_block` | Contacted `Comp`/`Contact`/`Metal1` substrate-tie rings are **drawn**, around both the analog core and the reserved digital region, and are DRC-clean | That any of them is *connected to a supply* |
| `layout/lvs/reports/20260817-185722-40cfeb8/adc_block.lvs.json` — `status: "match"`, 198 net pairs, `VDD`/`VSS`/`VSUBS` all `pin: true` | The supplies were genuinely part of the LVS compare (which is item 11's *other*, LVS half), and the layout's well partitioning matches the reference's | That any well is biased. The reference netlist's PMOS bodies were deliberately re-pointed at per-leg n-well nodes (`NW_P256`, …) by `lib/netlist.py:write_reference`'s `body_net_of`, precisely because gf180mcu's curated extraction deck never connects `nwell` to `contact` ([klayout-tools#555][555], already filed from this repo). The compare was configured not to ask the question |

So: **this block has no tool-derived proof that any well or the substrate
is tied to a supply**, from any of the three routes that could give one
(`klt erc` ties, `klt extract`/`klt lvs` bulk nets, or a dedicated
well-tie checker, which does not exist). Two of those three are blocked by
already-filed upstream gaps; the third is a property of this layout, and it
is a real finding rather than a tool limitation — see the next section.

## Real findings this flow surfaced (tracked separately)

Both are recorded here and tracked as their own issues rather than worked
around in the spec, per this repo's rule that a spec is never tuned until a
layout passes.

- **The guard rings are drawn but unstrapped** — tracked on **#340**,
  which asks the neighbouring question (whether implants should be drawn
  at all); this is the answer to its point 1. `gen_adc_top.py` calls
  `draw_guard_ring` twice with no `label_net` and routes nothing to either
  ring, so both substrate-tie rings — and the two Metal1 rails drawn inside
  the reserved digital region, deliberately unlabelled — are connected to
  no supply net in the merged GDS. The `vdd` island's whole Metal1 area is
  643.8 µm² while a single analog-ring bar is 417.8 µm² on its own, and
  neither ring is part of either supply island.
- **No supply geometry exists above Metal1** — filed as **#346**. Both rails' block-level
  continuity runs through Metal1 trunks and Poly2 risers; Metal2–Metal5
  carry zero `vdd`/`vss` area. Structurally that is still one island per
  supply, which is all item 11 asks. Electrically, a rail whose stitching
  is polysilicon is an IR-drop and EM question — `klt power`'s, not
  `klt erc`'s — and this block has no `klt power` evidence at all.

## Why the controls exist

The supply spec's entire claim is an **absence** — zero findings. An
absence is only evidence if the rule that would have produced it was live.
`controls/adc_block.unconnected-net-control.json` is byte-identical to the
supply spec except that it declares a supply name nothing in the layout
carries; it must produce exactly one `erc.unconnected_net`. That is the
same argument `layout/drc/cells/`'s negative control makes for the DRC
deck (`layout/README.md`, "The negative control"): upstream proves the
check catches a seeded fault, this repo additionally proves the check was
*looking*.

`controls/adc_block.no-devices.known-gap.json` does the same job for the
supply spec's `devices[]` block, which is not cosmetic here: without it the
comparator's two poly load-resistor bodies are read as wire and fuse `vdd`
to the preamp outputs (`gates[]` reports a net literally named
`XCMP.pon,XCMP.pop,vdd`), and all 1024 CDAC MiM unit capacitors are shorted
plate-to-plate through the Via4 role. The supply verdict does not flip in
either case, but the island the verdict describes would not be the rail.

## Relationship to `signoff/`

`signoff/` is this block's verdict of record for "how far is this block
from T1?" This directory produces one of the artifacts it cites, not a
verdict of its own. Item 11 is a **compound** claim — `klt erc` plus the
LVS report item 4 grades, plus (for an RTL-flow digital partition) a `klt
place-and-route` response with `power.pdn: true` and that report's
`power_connectivity.status: "match"` — so a clean run here does not by
itself move the item-11 row. Two things stand between this report and a
graded row, both on **#347**: `signoff/run_signoff.py` understands only
single-artifact citations while item 11 is the one *compound* item, and
even once cited the row reads `unmet` / `supply_spec_incomplete` rather
than `met`, for the `ties[]` reason above. See `signoff/README.md`'s "Open
work that will move a row".

## Friction filed upstream

Per this repo's friction protocol (`CLAUDE.md`), the `ties[]` dead end is
not this block's problem alone and was filed generically as
[klayout-tools#2234][2234]: a stream whose taps are drawn but carry no
distinguishing mark has **no declarable tap at all**, so item 11's
`erc.missing_tie` condition is structurally unreachable for that whole
class of designs — not merely hard. The four-case table it cites is the
same one `controls/` reproduces here, which is why those controls are
committed rather than described.

[2025]: https://github.com/2AMLogic/klayout-tools/issues/2025
[2169]: https://github.com/2AMLogic/klayout-tools/issues/2169
[2199]: https://github.com/2AMLogic/klayout-tools/issues/2199
[2234]: https://github.com/2AMLogic/klayout-tools/issues/2234
[555]: https://github.com/2AMLogic/klayout-tools/issues/555
