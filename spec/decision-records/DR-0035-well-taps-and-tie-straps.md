# DR-0035: draw and route every well tap and both substrate-tie straps, and mark them with implants

- **Status**: ratified
- **Date**: 2026-09-23
- **Decided by**: Builder agent, issue #356
- **Supersedes**: DR-0032 (*implant layers stay undrawn in `adc_block.gds`
  until a well tap exists to mark*) — by DR-0032's own first revisit
  trigger, "well taps are drawn"
- **Superseded by**: (none while this record stands)
- **Related**: #356, #340 (the measurement that produced DR-0032 and this
  issue), #330 (the `klt erc` bring-up), DR-0024 (the area budget this
  growth is scored against), #346 / DR-0034 (the IR/EM read whose "zero
  supply area above Metal1" premise this change deliberately preserves),
  `layout/erc/well-tap-audit.json`, `layout/erc/records/20260923-071448-e84ad26.md`,
  `layout/drc/records/20260923-064140-e84ad26.md`,
  `layout/lvs/records/20260923-064203-e84ad26.md`,
  klayout-tools#2234, klayout-tools#555

## Context

DR-0032 decided **not** to draw implant layers, on a measured ground: an
implant marks tap geometry, `ADC_BLOCK` had no tap geometry, and so
`COMP ∩ Nplus` inside the wells would be empty after the change exactly as
it was before it. That record named, as its first revisit trigger, the
layout work that would make the marking meaningful — *well taps are drawn* —
and said explicitly that the trigger should **supersede** it rather than be
worked around. This record is that supersession.

What `layout/erc/well_tap_audit.py` measured on the pre-change geometry
(`adc_block.gds` sha256 `b4cf6ad7…`) was a real defect, not a marking gap:

- **Zero of the 25 `Nwell` islands carried a tap.** All 160 `COMP` polygons
  interacting with a well also interacted with `Poly2`, i.e. every diffusion
  region inside every well was transistor source/drain/channel. Every PMOS
  body in the block sat in a well biased by nothing.
- **Both substrate-tie guard rings reached no supply.** They were drawn,
  contacted and DRC-clean, but `gen_adc_top.py` called `draw_guard_ring`
  twice with `label_net` at its `None` default and routed nothing to either.
- **Each ring's `Metal1` was open at all four corners** — four mutually
  disjoint bars, 0 touching pairs — so labelling one bar would have strapped
  a quarter of a ring and produced a *second* island named `vss`, which
  `erc.unconnected_net` fires on (it fires on more than one match as well as
  on zero). The strap was never a one-line `label_net=` change.
- **Each ring's contacts were four long bars** (0.468 µm × up to
  596.698 µm), passing the curated deck's `contact.width.1` — a check whose
  own description calls itself an approximation of gf180mcu's `CO.1` *exact*
  min/max size rule. DRC-clean did not mean manufacturable.

## Decision

**Draw an `Nplus`-marked, contacted n+ tap inside every `Nwell` island and
route it to `vdd`; close both substrate-tie rings' `Metal1`, mark them
`Pplus`, label them `vss` and route them into the block's own `vss` island;
redraw every tap contact as a `CO.1`-compliant array; and declare the
resulting tie in `layout/erc/adc_block.supply-spec.json`.**

Concretely, as built and measured:

| | before (`b4cf6ad7…`) | after (`ae4e8964…`) |
|---|---|---|
| well taps drawn (`COMP` in `Nwell`, clear of `Poly2`) | **0** | **25** (one per island) |
| implants drawn (`Pplus` 31/0, `Nplus` 32/0) | neither | both |
| `Metal1` bars per substrate-tie ring / touching pairs | 4 / 0 (open) | 1 (a closed annulus) |
| `Metal1_Label` texts on each ring | **0** | 2 |
| ring contact dimensions | 0.468 µm × ≤ 596.698 µm bars | 0.22 × 0.22 µm squares (3276 + 1006 cuts) |
| `Nwell` area | 9 614.820 µm² | 10 000.276 µm² |
| `erc.missing_tie` | *never computed* (no `ties[]`) | **0**, with the rule in `erc_coverage.checked` |
| extracted PMOS body net | anonymous per-island well net | `vdd` |
| extracted NMOS body net | `vsubs` (a synthesized global) | `vss` |

**Implants are drawn ONLY on the tap structures**, not on transistor
source/drain. That is the substantive half of superseding DR-0032, and it is
a deliberate scope, not an oversight: an implant is what makes a diffusion
region a *tap* rather than a source/drain, so marking the taps is the
statement that carries information and is exactly what `klt erc`'s
`tap_requires` reads. A full implant derivation over every S/D is a
downstream step this generated flow still leaves downstream, and no rule in
the pinned deck names 31/0 or 32/0, so drawing it would add unverifiable
geometry — DR-0032's second revisit trigger (*the curated deck gains implant
rules*) has **not** fired, and this record does not claim it has.

The tie declaration is `tap_layer: "22/0"` narrowed by
`tap_requires: ["32/0"]`, `connect_to: "Metal1"`, `net: "vdd"` — the real
gf180mcu tap boolean, now non-vacuous because `Nplus` is drawn on the 25
taps and nowhere else.

**Where the geometry went.** The wells were drawn at `NWELL_MARGIN` = 0.5 µm
around the PMOS active they cover, with no room reserved, so the tap needed
new area. It is a horizontal `TAP_COMP_H` = 0.4 µm strip **above** each
device row — the one direction with nothing on the other side of it; the
`COLUMN_GAP` between PMOS columns is 0.4 µm and cannot hold a 0.22 µm
diffusion with `comp.space.1` (0.28 µm) on both sides — and each island grows
by `TAP_STRIP_H` = 0.8 µm to enclose it. That cost is paid once per stacked
device row, not once per island. Each tap's `Metal1` reaches sideways into
the inter-group gap and drops to the row's `vdd` trunk on a Poly2 riser, the
same Metal1-trunk / Poly2-riser discipline every other terminal in this
library uses. The two rings are strapped in two hops: digital ring → analog
ring on plain Metal1 up the (deliberately empty) analog/digital separation
strip, then analog ring → decode bank P's `vss` trunk on a Poly2 riser
starting from a Metal1 tab that carries the net inward past the ring's own
`Comp` first, so the riser never crosses the tie diffusion.

**Area.** `block_total` 150 536.239 → **151 827.342 µm²** (+1 291.103 µm²,
**+0.86 %**), block bbox 599.03 × 251.3 → 599.35 × 253.32 µm. That is
0.151827 mm², **94.9 %** of the `< 0.16 mm²` bound DR-0024 proposes (it was
94.1 %). **DR-0024's bound is not reopened**: the growth fits inside the
headroom that record deliberately left, and this record ratifies no new area
figure. The per-row detail is `layout/adc-top/area.json`; the decode banks
grew most in relative terms (+2.77 %) because they are the shallowest rows
and pay the same 0.8 µm strip as the deep ones.

## Alternatives considered

- **Put the tap in the gap between PMOS columns instead of above the row** —
  not chosen, and not a preference: it does not fit. `COLUMN_GAP` is 0.4 µm
  and a 0.22 µm tap diffusion needs `comp.space.1` = 0.28 µm on each side,
  i.e. 0.78 µm. Widening `COLUMN_GAP` to make it fit would grow every device
  row horizontally by 0.38 µm per column across 323 transistors — strictly
  more area than the 0.8 µm-per-row strip, and it would move every routing
  column in the block.
- **Strap the rings by labelling one `Metal1` bar and leaving the corners
  open** — not chosen, and this is the trap #340 measured and warned about.
  `Comp` 22/0 is deliberately not a conducting role in the supply spec's
  stackup (source and drain of every device share one `COMP` polygon), so
  the diffusion ring underneath does not join the four bars in the
  connectivity model either. A label on one bar makes a second island named
  `vss`, and `erc.unconnected_net` fires on *more than one* match. The result
  would have read **worse** than the unlabelled ring it replaced.
- **Route the taps on Metal2 rather than on Poly2 risers** — not chosen.
  Poly2 is ~81× Metal1's sheet resistance and these risers are 20–60 µm long,
  which is irrelevant *here* and would not be on a rail: a well tie carries
  reverse-bias junction leakage — nanoamps — so even 1 kΩ of riser puts
  microvolts on the body. Choosing Metal2 would have put supply geometry
  above Metal1 for the first time and silently invalidated #346's measured
  premise (this block has **zero** `vdd`/`vss` area on Metal2–Metal5), which
  DR-0034's droop budget rests on. Keeping the taps on Poly2 keeps that
  premise true of the tapped layout.
- **Keep the ring contacts as bars, since they pass the pinned deck** — not
  chosen. The bars were recorded by DR-0032 as an observation precisely
  because they *would* pass: `contact.width.1` is a minimum-width check and
  `CO.1` is an exact min **and max** size rule. There are only 25 taps and two
  rings in the whole block (unlike the 224 source/drain bars per decode-bank
  side), so drawing them to the DRM's own square costs ~5.4 k shapes and buys
  a structure that is manufacturable rather than merely deck-clean. The
  source/drain bars are untouched and remain a stated, separately-recorded
  approximation.
- **Draw implants on transistor source/drain as well** — not chosen, per
  DR-0032's still-unfired second trigger (above). It would add tens of
  thousands of shapes on two layers no rule in the pinned deck checks, and
  change no number in any report.
- **Declare a substrate tie in `ties[]` alongside the well tap** — not
  chosen, because the pinned build cannot express it: `klt erc`'s tie
  declaration is keyed on a drawn `well_layer`, and the p-substrate of a bulk
  process is not drawn. That gap was already filed generically from this repo
  as klayout-tools#2255 and is **closed upstream** by klayout-tools PR #2273
  (a native-substrate block may assert `well_boxes` instead) — but #2273
  merged after `layout/erc/toolchain.json`'s pinned commit `67d617f`, and
  bumping that pin is a reviewed re-baselining of this whole evidence trail
  with its own record, not something to fold into a layout change. Until then
  the rings are graded only as part of the `vss` island (zero
  `erc.unconnected_net` on `vss`, with both rings' labels on it) and by the
  direct geometric measurement in `well-tap-audit.json`, and
  `layout/erc/README.md` says so where a reader of the `met` row will find
  it.

## Consequences

- **Item 11's tie half stops failing on evidence and starts passing on
  evidence.** The committed `klt erc` run
  (`layout/erc/records/20260923-071448-e84ad26.md`) reports zero
  `erc.missing_tie` over 25 wells with `erc.missing_tie:["nwell_tap"]` in
  `erc_coverage.checked` — a computed verdict, not an omitted check.
  `cases.json` asserts the coverage entry explicitly, because a zero from a
  skipped rule and a zero from a rule that ran are the same number in
  `erc_finding_counts` and only the coverage list tells them apart.
- **The clean verdict has a discriminating control.**
  `controls/adc_block.tie-wrong-implant.control.json` is the same declaration
  narrowed on `Pplus` 31/0 — a non-empty implant this stream really draws,
  but only outside every well — and reports all 25 wells untapped. It
  replaces the `tie-narrowed` known gap, which reproduced the implant-free
  stream this is no longer; that control's 25 findings came from an *empty*
  tap region and discriminated nothing.
- **The extraction now reports the schematic's own answer.** `klt extract`
  reports every PMOS body on `vdd` and every NMOS body on `vss` in
  `adc_top.gds`/`adc_block.gds`; `vsubs` no longer appears in either
  netlist, and the deck's *"N PMOS devices tie their body to an anonymous net
  with no DC bias path"* warning is gone from every cell. `net_count` drops
  accordingly (`adc_block` 198 → 172, `adc_top` 177 → 156): one anonymous
  well net per island, plus `vsubs` where a ring is drawn. `lib/netlist.py`'s
  `write_reference` takes the nets the generator actually routed the taps to,
  so the reference cannot drift from the geometry. LVS is `match` on all nine
  block-level cases.
- **This corrects a claim this repo had been making.** `layout/README.md`'s
  "documented gf180mcu extraction approximations" said body terminals are
  *not* derived from drawn geometry because the curated deck has no distinct
  tap layer. `ExtractionDeck.tap` is indeed `None`, but the deck **does**
  carry implant-narrowed `tap_pplus` (31/0) / `tap_nplus` (32/0)
  derivations, and `connect_global` merges its synthesized global into the
  drawn net when they are marked. The approximation was real for an
  *unmarked* stream and is stated that way now. klayout-tools#555's practical
  bite on this block — PMOS bodies on an un-biased anonymous net, which
  blocked faithful resimulation of the extracted netlist — is consequently
  gone; the upstream filing stands on its own terms for unmarked streams.
- **`adc_block.gds` moved, and the whole evidence trail moved with it** —
  a deliberate absorption this record authorizes. Re-minted under their own
  pinned builds: the DRC report (`20260923-064140-e84ad26`, clean),
  the LVS report (`20260923-064203-e84ad26`, `match`), the `klt erc` report
  and record (`20260923-071448-e84ad26`), `layout/erc/cases.json`'s
  `layout_sha256`, `layout/erc/well-tap-audit.json`, `signoff/freshness.json`
  and the signoff manifest.
- **Bad consequence, stated plainly**: the stream still is not a mask-level
  database. Implants are drawn on the taps and the ties only, so a faithful
  implant derivation over every source/drain is still downstream work, and
  DR-0032's warning — that "DRC clean" must not be read as "manufacturable" —
  survives its own supersession. What has changed is that the *dominant*
  reason the block could not be taped out (no well in it was tied) is fixed;
  what remains is the marking of geometry that is electrically correct
  either way.
- **A third flow is left stale, deliberately and on the record**: the
  parasitic-extraction flow (`layout/adc-top/parasitics/`) and the five
  extracted campaigns built on it were **not** re-run here.
  `parasitics/cells.json` still pins the pre-#356 GDS hashes, so
  `run_extract_parasitics.py` fails loudly rather than minting evidence over
  different bytes; the re-extraction plus five ngspice PVT campaigns is its
  own reviewable body of work (it was #218's scope the last time the layout
  moved) and is tracked as **#383**, with a disclosure note at the top of
  `parasitics/README.md`. The `klt power` re-run above measures the same
  change at ~1.6 % worse droop with no verdict flipped, which is a
  reasonable prior for the ΣR/ΣC delta and is explicitly not a substitute
  for measuring it.
- **A second bad consequence**: the block is 0.86 % larger, and the growth is
  structural rather than recoverable — it is the area a tap physically needs.
  Every future area-recovery pass starts from 151 827.342 µm², and any
  proposal to shrink the wells has to say where the taps go.
- **Guard against silent re-breakage**: `sim/tests/test_well_tap_audit.py`
  now pins `well_tap_candidates == 25`, one `Metal1` annulus per ring with a
  label on it, and both implants present — hard-coded in the same deliberate
  way DR-0032 pinned the zero, so undoing this work fails CI and names this
  record rather than quietly re-orphaning it.

## Spec lines affected

- None — this is a layout-geometry and evidence decision. It changes no
  target parameter or row in `spec/`. The as-built area figure moves
  (150 536.239 → 151 827.342 µm²) but stays inside the `< 0.16 mm²` bound
  DR-0024 proposes, so no area row is re-ratified here; DR-0024 continues to
  stand on its own terms, against the new figure.
