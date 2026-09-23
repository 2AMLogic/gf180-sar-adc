# `layout/erc/` — structural power delivery (`klt erc`)

**Is the supply actually connected to what it powers?** That question is T1
item 11 (*Power delivery (structural)*, added to klayout-tools'
`docs/design-evidence-tiers.md` by [klayout-tools#2025][2025] on
2026-09-17), and this directory is where this block answers it. Issue #330.

It is the **structural** question only. IR drop and electromigration
(`klt power`) are deliberately outside item 11 and outside this directory —
that is the *analysis* question, and it lives in
[`layout/power/`](../power/README.md) (issue #346), whose first record this
flow's own findings prompted. No `klt power` run is cited by any T1 item
today; item 11 does not have a slot for one.

```
layout/erc/
  README.md                  this file
  adc_block.supply-spec.json THE item-11 artifact: the `klt erc` supply spec
  toolchain.json             pinned klt build, asserted before anything runs
  cases.json                 what run_erc.py runs and what it asserts
  run_erc.py                 reproducible invocation + assertions + record
  controls/                  the specs that make the clean verdict mean something
    adc_block.unconnected-net-control.json   negative control (nets[])
    adc_block.tie-wrong-implant.control.json discrimination control (ties[])
    adc_block.tie-bare.known-gap.json        known gap (A)
    adc_block.no-devices.known-gap.json      known gap (C)
  well_tap_audit.py          the same tie question, answered from geometry
  well-tap-audit.json        its committed result AND its expectations
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

The well-tie audit beside it needs no `klt` at all — only the pip `klayout`
package, and nothing for its freshness half:

```bash
python3 layout/erc/well_tap_audit.py           # measure, print, assert
python3 layout/erc/well_tap_audit.py --verify  # stdlib-only geometry freshness
```

## What the committed run says

Against `layout/adc-top/adc_block.gds` (top cell `ADC_BLOCK`,
sha256 `501f3985…`, the same bytes `signoff/gf180-sar-adc.manifest.json`
pins for this block's DRC citation). Record:
[`records/20260923-084733-5f13cf9.md`](records/20260923-084733-5f13cf9.md) —
re-taken at issue #378 against the Metal2-strapped geometry; every case
reports exactly what it reported before, which is the point of re-taking it
rather than reasoning that a strap cannot change a structural verdict.

| Case | `status` | `erc_status` | findings | exit |
|---|---|---|---|---|
| `adc_block.supply` (the artifact) | `not_checked` | `clean` | none | 4 |
| `adc_block.unconnected-net-control` | `violations` | `violations` | 1 × `erc.unconnected_net` | 3 |
| `adc_block.tie-bare.known-gap` | `not_checked` | `clean_partial` | none, 1 skipped | 4 |
| `adc_block.tie-wrong-implant.control` | `violations` | `violations` | 25 × `erc.missing_tie` | 3 |
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
- **Every one of the 25 drawn `Nwell` islands is tapped, and every tap
  reaches `vdd`.** Zero `erc.missing_tie` — and, critically, from a rule
  that **ran**: `erc_coverage.checked` carries
  `erc.missing_tie:["nwell_tap"]`, which `cases.json` asserts by name.
  That distinction is the whole of what changed here at issue #356; see
  "The tie half" below.
- Those islands span the whole block: the merged GDS carries four `vdd`
  labels and **six** `vss` labels — one pair in each of
  `ADC_DECODE_BANK_N`, `ADC_DECODE_BANK_P`, `ADC_TOP_SW` and `COMPARATOR`,
  plus one on each of the two substrate-tie guard rings — and all of each
  land on one node. Between the labelled sub-blocks there is no Metal1
  path: since issue #378 ([DR-0037][dr0037]) three **Metal2** straps join
  them, landing on each sub-block's Metal1 trunk through a single Via1.
  Everything else — every in-sub-block terminal riser, the 25 well-tap
  risers #356 added, the guard-ring strap, and `vcm` — is still Poly2.
  `layout/power/`'s solved network for the same geometry counts the result
  directly: the `vdd` island is 476 nodes / 477 edges (130 Poly2, 114
  Metal1, 222 Contact, **3 Metal2, 8 Via1**) and `vss` is 610 / 613 (121
  Poly2, 239 Metal1, 242 Contact, **3 Metal2, 8 Via1**). Counting that
  rather than assuming it is exactly what a structural check is for — and
  it is how this README's previous claim, *no edge on any layer above
  Metal1*, was falsified on purpose rather than quietly outgrown.
- 142 gate nets, identified as `poly ∩ diff` — the comparator's two poly
  load-resistor bodies and any other gate-oxide-free poly are excluded from
  the gate set rather than reported with non-physical antenna ratios.

## The tie half: computed, and why the zero is not vacuous

This section used to be titled *"What it does **not** say: `erc.missing_tie`
was never computed"*. It is kept, re-titled, because the reason it is no
longer true is the substance of issue #356 and
[DR-0035][dr0035] — and because the argument that got the flow here is the
reusable part.

**Until #356 the check could not have said anything.** The supply spec
declared no `ties[]`, on a measured ground: the only expressible narrowing
is the real gf180mcu tap boolean `COMP ∩ Nplus`, and `ADC_BLOCK` drew **no
implant layers at all**, so the tap region was empty and all 25 wells
reported untied *whatever the layout drew*. Those findings were not false —
[the audit below](#the-same-question-answered-from-geometry) showed their
verdict was right — but they were **unfounded**, and a check that cannot
vary with the layout is not evidence about the layout. Omitting `ties[]`
was the honest form of that, and [DR-0032][dr0032] recorded it.

**Issue #356 removed the premise.** `lib/geometry.py` now draws an
`Nplus`-marked, contacted n+ tap inside every `Nwell` island and
`lib/place.py` routes each one to the `vdd` trunk on a Poly2 riser;
`gen_adc_top.py` closes both substrate-tie rings' `Metal1` at the corners,
marks them `Pplus`, labels them `vss` and straps them into the block's own
`vss` island. `Nplus` is drawn **only** on the 25 taps, so
`tap_layer: "22/0"` narrowed by `tap_requires: ["32/0"]` derives exactly
those 25 strips and nothing else. The declaration is now load-bearing:

```json
"ties": [{ "name": "nwell_tap", "well_layer": "21/0", "tap_layer": "22/0",
           "tap_requires": ["32/0"], "connect_to": "Metal1", "net": "vdd" }]
```

**Why the resulting zero is evidence.** A zero from a rule that never ran
and a zero from a rule that ran are the same number in
`erc_finding_counts`; only `erc_coverage` tells them apart, and only a
control tells you the rule could have fired on *this* stream. Both are
committed:

- **`controls/adc_block.tie-wrong-implant.control.json`** is the
  discrimination control. It is byte-identical to the supply spec except
  for one character — `tap_requires: ["31/0"]`, `Pplus`, the substrate-tie
  implant. Both implants really are drawn in `ADC_BLOCK`, and deliberately
  in **different places**: `Nplus` marks the 25 well taps, `Pplus` marks
  the two guard rings, which sit outside every well. So `COMP ∩ Pplus` is a
  large, non-empty region that simply never lands inside a well, and all 25
  wells report `erc.missing_tie`. It fails for a reason that depends on
  *where* the implant is drawn — so mis-marking the taps would swap this
  control's verdict with the artifact's, which is the property a control is
  supposed to have. It replaces the old `tie-narrowed` known gap, whose 25
  findings came from an empty tap region and discriminated nothing.
- **`controls/adc_block.tie-bare.known-gap.json`** is unchanged and still
  reproduces [klayout-tools#2199][2199]'s degenerate-declaration skip: a
  bare `tap_layer: "22/0"` matches every source/drain contact inside the
  well, so `klt erc` records the work as skipped
  (`degenerate_tap_declaration`) and downgrades `erc_status` to
  `clean_partial` rather than letting a clean verdict stand for a check
  that could not tell a tap from a source/drain contact. It is the reason
  the narrowing is mandatory rather than cosmetic.

**What is still *not* computed: the substrate tie.** `klt erc`'s `ties[]`
requires a drawn `well_layer`, and the p-substrate of a bulk process is not
drawn, so `erc.missing_tie` can only ever grade n-well taps here. The two
`Pplus` rings are graded only as part of the `vss` island — they carry
`vss` labels and are routed into it, which is exactly what zero
`erc.unconnected_net` on `vss` asserts — and measured directly by the audit
below. `tap_is_dedicated` does not apply either (gf180mcu has no tap-only
layer, and this block draws no tub-contact marker).

Note that [klayout-tools#2169][2169] — the false `erc.supply_short` a
`ties[]` declaration used to induce on a routed design, which is the reason
the sibling `gf180-drone-fc` omits `ties[]` — is **fixed** in the build
`toolchain.json` pins: ties are evaluated in their own isolated extraction
now and cannot affect `gates[]` or the `nets[]` findings. It was never the
reason for the old omission, and it is not an obstacle to the current
declaration.

## The same question, answered from geometry

A tool-derived verdict is worth more when something independent agrees with
it. The question — *is any well or the substrate actually tapped?* — is a
property of the drawn layers and needs no implant marking, no extraction
deck and no net model to settle: **a well tap is diffusion inside a well
that is not part of a transistor.** `well_tap_audit.py` measures exactly
that, and `well-tap-audit.json` commits the result alongside the sha256 of
the GDS it was measured on. It is the same instrument #340 used, unchanged,
pointed at the new geometry:

| Measurement | before #356 | now |
|---|---|---|
| `Nwell` 21/0 islands | 25 (9614.820 µm²) | 25 (10000.276 µm²) |
| `COMP` 22/0 polygons interacting with an `Nwell` | 160 | 185 |
| …of those, polygons **not** also interacting with `Poly2` 30/0 — i.e. **well taps** | **0** | **25** |
| implants drawn (`Pplus` 31/0 / `Nplus` 32/0) | neither | both |
| `COMP` polygons outside every `Nwell` and clear of `Poly2` | 2 (2874.872 µm²) | 2 (2879.632 µm²) |
| `Metal1_Label` 34/10 texts on each ring | **0** | **2** |
| `Metal1` polygons per ring | 4, mutually disjoint | **1** (a closed annulus) |
| ring contact dimensions | 0.468 µm × ≤ 596.698 µm bars | 0.22 × 0.22 µm squares |

Read in order:

- **Every well in this block is tapped, one tap each.** 25 of the 185 `COMP`
  polygons interacting with a well do not interact with `Poly2`; the other
  160 are transistor source/drain/channel, exactly as before.
- **Both substrate-tie rings are closed and labelled.** Each ring's `Metal1`
  is now a single merged polygon rather than four corner-open bars.
  ⚠️ **`metal1_bar_pairs_touching` is `0` in both states and cannot tell
  them apart** — with one polygon there are no pairs to touch. The
  discriminating field is `metal1_bars` (4 → 1), and
  `sim/tests/test_well_tap_audit.py` pins *that*, not the pair count.
- **Both rings carry two `Metal1_Label` texts.** Two, not one, because the
  rings' Metal1 and the bar that straps them are one merged island, so each
  ring's region interacts with both `vss` labels. That is the correct
  reading: electrically there is one strapped structure, not two.
- **The contacts are arrays, not bars.** 3276 cuts on the analog ring and
  1006 on the digital one, every one an exact 0.22 µm square. The old bars
  passed the curated deck's `contact.width.1` — a *minimum*-width check
  whose own description calls itself an approximation of gf180mcu's `CO.1`
  exact min **and max** size rule — so DRC-clean did not mean
  manufacturable. It does now, for these structures; the transistor
  source/drain bars are a separate, still-stated approximation.

**The consequence for item 11 is that its tie half now passes on evidence.**
It spent #330 uncomputed, #340 failed-on-evidence, and #356 computed and
clean. [DR-0035][dr0035] records the decision and supersedes
[DR-0032][dr0032], whose own first revisit trigger — *well taps are drawn* —
is what fired.

`sim/tests/test_well_tap_audit.py` keeps this honest on the headless CI
path: it re-hashes the committed GDS against the audit and pins
`well_tap_candidates == nwell_islands`, one labelled `Metal1` annulus per
ring, exact-square ring contacts and both implants present — hard-coded, so
undoing this work fails there and names DR-0035 rather than quietly
orphaning it. (That mechanism has already fired once in the other
direction: it pinned `well_tap_candidates == 0` for DR-0032, went red the
moment #356 drew a tap, and forced the supersession instead of a silent
`--regen`.)

### What the other routes to a well-tie verdict now say

| Evidence | What it establishes |
|---|---|
| `layout/adc-top/lib/geometry.py` + the DRC record for `adc_block` (`layout/drc/records/20260923-064140-e84ad26.md`) | The taps and both substrate-tie rings are drawn, contacted with `CO.1`-compliant arrays, implant-marked, and DRC-clean |
| `layout/erc/reports/20260923-071448-e84ad26/adc_block.supply.erc.json` | Every drawn well carries a tap that reaches `vdd`; both rings are inside the one `vss` island |
| `layout/lvs/reports/20260923-064203-e84ad26/adc_block.lvs.json` — `status: "match"`, 172 net pairs | The supplies were genuinely part of the LVS compare (item 11's *other* half), **and** the bodies are now biased in the compare rather than excused from it |

The third row is the one that moved. The reference netlist's PMOS bodies
used to be deliberately re-pointed at per-leg n-well nodes (`NW_P256`, …) by
`lib/netlist.py:write_reference`'s `body_net_of`, because the curated deck
never connected `nwell` to `contact` ([klayout-tools#555][555], filed from
this repo) — the compare was configured not to ask the question. It now
asks it: `klt extract` reports every PMOS body on `vdd` and every NMOS body
on `vss`, `vsubs` does not appear in `adc_block.spice` at all, and the
deck's *"N PMOS devices tie their body to an anonymous net with no DC bias
path"* warning is gone from every cell. `ExtractionDeck.tap` is indeed
`None`, but the deck **does** carry implant-narrowed `tap_pplus` (31/0) /
`tap_nplus` (32/0) derivations, and `connect_global` merges its synthesized
global into the drawn net once they are marked — which is precisely what
`layout/README.md`'s "documented gf180mcu extraction approximations" now
says, corrected. The stand-alone `comparator.gds` / `comparator_nores.gds`
cells draw no ring and still report `vsubs`, so the approximation is real
for an unmarked stream and is stated that way.

So: a tool-derived answer for the **n-wells** now exists, from two
independent routes (`klt erc` ties and `klt extract` bulk nets), agreeing
with the direct geometric measurement. For the **substrate** the tool
routes still cannot answer — `ties[]` cannot name an undrawn well — and the
geometry measurement plus the `vss` island membership is what stands in.

## Real findings this flow surfaced (tracked separately)

Both are recorded here and tracked as their own issues rather than worked
around in the spec, per this repo's rule that a spec is never tuned until a
layout passes.

- **No well was tapped, and the substrate-tie rings were unstrapped** —
  filed as **#356** from `well_tap_audit.py`'s measurement, and **fixed**
  there ([DR-0035][dr0035]). The table above is the before/after. The fix
  moved `adc_block.gds`, so the DRC, LVS, ERC, IR/EM and signoff evidence
  were all re-minted against the new bytes; every one of them is listed in
  DR-0035's Consequences.
- **No supply geometry existed above Metal1** — filed as **#346**,
  **measured** ([`layout/power/`][power]), and then **fixed** at **#378**
  ([DR-0037][dr0037]). The finding was real and its consequence was worse
  than "poly is resistive": with both rails' block-level continuity on
  Poly2 risers, the droop verdict depended on *which* of the four labelled
  sites a parent landed the supply at — 5.722 mV at `COMPARATOR` (inside
  [DR-0034][dr0034]'s 33 mV budget) but 33.552 mV at `ADC_DECODE_BANK_P`,
  which missed it, and 58.552 mV at that site at the high-resistance
  corner. The three block-level `vdd`/`vss` straps are Metal2 now, and all
  four sites meet the budget at both the nominal and the pessimistic corner
  (worst 17.184 mV, 1.9× inside —
  `layout/power/records/20260923-084734-5f13cf9.md`). Structurally this is
  still one island per supply, which is all item 11 asks; what changed is
  the *electrical* verdict, and the structural claim this section used to
  make ("Metal2–Metal5 carry zero `vdd`/`vss` area") is deliberately no
  longer true. Electromigration is still `pass_partial` with zero failing
  edges and still cannot become `pass`: 715 edges remain unchecked because
  gf180mcuD publishes no current-density limit for Poly2 or Contact, and
  every in-sub-block terminal riser is still Poly2. The transient half this
  static read does not claim: **#379**.

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
`power_connectivity.status: "match"`.

**`T1#11.analog` reads `met` as of issue #356**, on the run above plus
`layout/lvs/reports/20260923-064203-e84ad26/adc_block.lvs.json`
(record [`signoff/records/20260923-071455-e84ad26.md`][sr]; the block moved
from 6/22 to 7/22 T1 rows). It read `unmet` / `supply_spec_incomplete` for
as long as this directory's supply spec declared no `ties[]` — the grader
reads a missing tie declaration as an incomplete spec regardless of what
else is clean — and the fix was to make the declaration expressible by
fixing the layout, not to change what the grader accepts.

Read the `met` with its stated limits, which are in that record and in
`signoff/README.md`'s own footnote: the **substrate** tie is not graded by
`erc.missing_tie` at all, `pdn` is `no` and `power_connectivity`
`unchecked` (item 11 does not require a P&R response of an analog
partition), and item 11 asks whether the supply is *connected*, not whether
it is *adequate* — `layout/power/` still misses DR-0034's droop budget at
one of the four candidate landing sites.

`T1#11.digital` is unchanged and still `unmet` / `no_evidence`: no LVS of
the routed `sar_ctrl` macro exists in this repo.

## Friction filed upstream

Per this repo's friction protocol (`CLAUDE.md`), the `ties[]` dead end this
flow hit in #330 was not this block's problem alone and was filed
generically as [klayout-tools#2234][2234]: a stream whose taps are drawn but
carry no distinguishing mark has **no declarable tap at all**, so item 11's
`erc.missing_tie` condition is structurally unreachable for that whole class
of designs — not merely hard. The four-case table it cites is the same one
`controls/` reproduces here, which is why those controls are committed
rather than described.

`ADC_BLOCK` turned out **not** to be an instance of that class — its wells
drew no tap at all, marked or unmarked — and #356 has now marked the taps it
draws, so this block is no longer even adjacent to it. The filing stands on
its own terms: the tool still cannot distinguish "tapped but unmarked" from
"untapped", which is why this repo had to measure the geometry itself to
tell them apart, and `well_tap_audit.py` is still what works around it
locally.

A second, distinct gap bounds what this flow can claim, and it is **already
filed and already fixed upstream — just not in the build this flow pins**.
`ties[]` is keyed on a drawn `well_layer`, which the p-substrate of a bulk
process has not got, so `erc.missing_tie` can grade the n-well taps here and
can never grade the two substrate ties, however carefully they are drawn,
contacted, implant-marked and strapped. That was filed generically as
[klayout-tools#2255][2255] ("`klt erc` cannot grade a native-substrate tie:
`ties[].well_layer` requires drawn geometry"), and closed by
klayout-tools PR #2273, which lets a native-substrate block declare its tie
via asserted `well_boxes`.

That PR merged **after** `toolchain.json`'s pinned commit
(`67d617f`), so the capability is not available to the run committed here.
Adopting it is a pin bump, which this directory's `toolchain.json` treats as
a reviewed change with its own record — not something to fold into a layout
issue. Until then the two `Pplus` rings are evidenced by their membership of
the one `vss` island plus `well_tap_audit.py`'s direct geometric
measurement, and this section is where that limit is written down rather
than left for a reader to infer from a `met` row.

[2025]: https://github.com/2AMLogic/klayout-tools/issues/2025
[2169]: https://github.com/2AMLogic/klayout-tools/issues/2169
[2199]: https://github.com/2AMLogic/klayout-tools/issues/2199
[2234]: https://github.com/2AMLogic/klayout-tools/issues/2234
[555]: https://github.com/2AMLogic/klayout-tools/issues/555
[2255]: https://github.com/2AMLogic/klayout-tools/issues/2255
[dr0032]: ../../spec/decision-records/DR-0032-implant-layers-not-drawn.md
[dr0035]: ../../spec/decision-records/DR-0035-well-taps-and-tie-straps.md
[sr]: ../../signoff/records/20260923-071455-e84ad26.md
[dr0034]: ../../spec/decision-records/DR-0034-supply-droop-budget.md
[dr0037]: ../../spec/decision-records/DR-0037-block-level-supply-straps-on-metal2.md
[power]: ../power/README.md
