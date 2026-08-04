# layout/adc-top/ — the block-level layout of `design/adc-top/`

Issue #57. This directory holds the **drawn block layout** for the ADC's
analog core and the code that generates it, plus the flat SPICE references
`klt lvs` compares the extraction against.

Everything here is generated. The generators are the reviewable source of
the GDS, not the GDS itself — same rule `layout/drc/cells/` already set for
its proof cells, for the same reason: the deck is upstream-owned and grows,
so a stream that cannot be rebuilt is evidence with a short shelf life.

```
layout/adc-top/
  lib/
    geometry.py      gf180mcu primitives + the two-layer channel router
    place.py         flattened-device-list -> placed, routed row
    netlist.py       design/ SPICE parser, flattener, LVS-reference writer
  cells/
    gen_adc_cells.py       generates the five leaf cells below
    adc_drv.*              local T-gate driver          (2 devices)
    adc_tgate.*            CDAC bottom-plate T-gate     (2 devices)
    adc_tgate_dum.*        superseded input sampling switch (4 devices) --
                            DR-0014 dropped it from `adc_top`/`adc_block`'s
                            composition; still drawn/LVS-matched standalone
                            (`design/adc-top/adc_top.spice` still defines it)
    adc_cdac_cell.*        one weighted CDAC position   (16 devices + 1 cap,
                            the cap wired and LVS-checked -- issue #70)
    adc_tp_sw.*            top-plate V_cm switch (DR-0014) (4 devices)
  gen_comparator.py        generates the comparator cells
    comparator.*           comparator + load resistors  (27 devices + 2 R)
    comparator_nores.*     same, resistor bodies omitted
  gen_adc_top.py           generates the block
    adc_top.*              the block: exactly adc_top.spice    (296 devices)
    adc_block.*            the assembled block: + comparator   (323 devices)
    area.json              the as-drawn area tally
```

For each cell `X`: `X.gds` (the layout), `X.spice` (`klt extract`'s output,
regenerated, never hand-edited), `X.ref.spice` (the flat LVS reference) and
`X.lvs.json` (the `klt lvs` request document).

## Reproducing it

```bash
python3 layout/adc-top/cells/gen_adc_cells.py
python3 layout/adc-top/gen_comparator.py
python3 layout/adc-top/gen_adc_top.py
git status --short layout/adc-top/          # should be empty: byte-reproducible

python3 layout/drc/run_drc.py --check       # every cell here, asserted
python3 layout/lvs/run_lvs.py --check       # every extraction + LVS case, asserted
```

The two runners are `layout/`'s existing ones (issues #15 and #51). These
cells are listed in their manifests rather than given a third runner, so
this repo keeps **one** append-only DRC record trail and **one** LVS record
trail with one set of assertions behind them.

## Results

Current records: DRC
[`layout/drc/records/20260804-181054-4097611.md`](../drc/records/20260804-181054-4097611.md),
LVS
[`layout/lvs/records/20260804-181107-c672a81.md`](../lvs/records/20260804-181107-c672a81.md)
— the area re-pitch (issue #67). Prior records: the DR-0014 redraw
(issue #66), DRC
[`layout/drc/records/20260804-100548-688c2eb.md`](../drc/records/20260804-100548-688c2eb.md),
LVS
[`layout/lvs/records/20260804-100640-688c2eb.md`](../lvs/records/20260804-100640-688c2eb.md);
and the pre-DR-0014 bring-up (issue #62), DRC
[`layout/drc/records/20260801-225603-7866d03.md`](../drc/records/20260801-225603-7866d03.md),
LVS
[`layout/lvs/records/20260801-225959-7866d03.md`](../lvs/records/20260801-225959-7866d03.md).

| Cell | Devices | `klt drc` | `klt lvs` vs. `design/` |
|---|---|---|---|
| `adc_drv` | 2 | clean | match, 0 mismatches |
| `adc_tgate` | 2 | clean | match, 0 mismatches |
| `adc_tgate_dum` (superseded, standalone only) | 4 | clean | match, 0 mismatches |
| `adc_cdac_cell` | 16 + **1 MiM cap** | clean | match, 0 mismatches |
| `adc_tp_sw` | 4 | clean | match, 0 mismatches |
| `comparator_nores` | 27 | clean | match, 0 mismatches |
| `comparator` | 27 (+2 R) | clean | match, 2 `warning` findings † |
| **`adc_top`** | **296** | **clean** | **match, 0 mismatches** |
| **`adc_block`** | **323** | **clean** | **match, 2 `warning` findings †** |

† `status: "match"` with a non-zero `mismatch_count` is not a contradiction:
`klt lvs`'s verdict is always `NetlistComparer.compare()` itself, and both
findings are severity `warning` — "nets were paired ambiguously; the
comparer resolved it structurally". They appear only in the two cases that
contain the comparator's load resistors, for the reason in
"Resistors" below, and `comparator_nores` is the companion case that removes
the ambiguity.

**`adc_top`'s LVS target is `design/adc-top/adc_top.spice` exactly** — two
`adc_cdac_side` arrays (each cell's fourth, one-hot leg to `V_in` included,
DR-0014) and the two per-side top-plate `V_cm` switches (`adc_tp_sw`,
DR-0014), the same composition `sim/adc-enob-fft/testbench/` instantiates.
`adc_block` is that plus `design/comparator/comparator.spice`'s comparator,
strapped to the top plates and the analog rails. `adc_tgate_dum` (the
dedicated input sampling switch DR-0014 superseded) is no longer part of
either composition, but `design/adc-top/adc_top.spice` still defines it
(DR-0014-comment-marked), so it stays drawn and LVS-matched standalone —
see `cells/gen_adc_cells.py`'s own docstring.

## What the matching plan asked for, and what is drawn

Against [`../floorplan-matching-plan.md`](../floorplan-matching-plan.md).
Every row is either *implemented* or a **stated deviation** — nothing is
silently skipped.

| Plan | Status | Where / why |
|---|---|---|
| §1.1 512 unit positions per side, plain binary, free-MSB | implemented | 32 × 16 grid per side, 1024 units total; per-weight census in `area.json` (`256`:256 … `1`:1, `term`:1) |
| §1.2 MiM `cap_mim_2f0fF`, `C_u` = 17.24 fF at 2.7136 µm | implemented, **and now DRC-checked** | `geometry.draw_mim_cap`; the FuseTop plate is drawn at the ratified 2.7136 µm and Metal4 is derived from `MIMTM.3`. The deck checks `MIMTM.1`/`.2`/`.3` and Metal2/3/5 as of the issue #70 pin — see "The MiM stack" below |
| §1.3 common-centroid unit-cap tiling | implemented, with a stated caveat | `gen_adc_top.centroid_tiling` — centro-symmetric position pairs, bit-reversed deal; common-centroid *by construction*, not by inspection. Exact for every even-count weight; the two single-unit groups are exact only *combined* — see "Caveat" below. Asserted by [`sim/tests/test_layout_centroid_tiling.py`](../../sim/tests/test_layout_centroid_tiling.py) |
| §1.3 full dummy ring | implemented | one extra tile all round, identical drawn geometry, electrically floating |
| §1.3 routing kept off the capacitor dielectric | implemented | nothing but the Metal5 top-plate mesh is drawn over the array; all switch/driver routing is Metal1/Poly2 in a separate region |
| §1.4 single top-plate net per side, short path from the electrical centre, P/N symmetric | implemented (drawn, unverifiable) | Metal5 row straps + a spine on the array's own centre, identical on both sides |
| §1.4 no daisy-chaining | implemented | mesh, not chain |
| §1.5 sampling switch at the array's input edge, not inside the array | implemented | `ADC_TOP_SW` (the `adc_tp_sw` top-plate `V_cm` switch, DR-0014) placed beside the arrays, same floorplan slot the superseded `adc_tgate_dum` used to occupy |
| §1.5 dummy placed symmetrically w.r.t. its main device | **superseded** | this row describes DR-0013's dummy-compensated input sampling switch (`adc_tgate_dum`), which DR-0014 removed from the converter. Still true of `adc_tgate_dum` where it is still drawn (device order `XDN XN | XN XDN` / `XDP XP | XP XDP`), but that cell is no longer in `adc_top`/`adc_block`'s composition. The switch that IS in the composition now, `adc_tp_sw`, is deliberately NOT dummy-compensated — `design/adc-top/adc_top.spice`'s own comment on the subckt explains why (its channel always opens at `V_cm`, a signal-independent node, so there is no input-dependent injection left to compensate) |
| §1.5/DR-0013 dummy drawn as a **finger count** (7 of 16 fingers) | **superseded** | applied to `adc_tgate_dum`, no longer in the composition (see row above); N/A to `adc_tp_sw` |
| §1.6 decode switches adjacent to their own weighted position | implemented | one placement group per weighted cell, in MSB→LSB order |
| §2.1 preamp branches common-centroid **including** the load resistors | **partial** | resistors: yes, genuinely (A-B-B-A, two segments each). Transistors: mirror-symmetric adjacent pairs, **not** common-centroid. See "Single-finger devices" |
| §2.3 regeneration nodes kept away from top-plate routing | implemented | placement order preamp → latch → inverters → SR latch, so `outp`/`outn` and `clk` sit at the far end of the cell from `vinp`/`vinn` |
| §2.4 guard rings around the comparator and the CDAC array | implemented | one contacted Comp/Contact/Metal1 ring around the whole analog core |
| §2.4 physical spacing between SAR logic and the analog core, ring on the boundary | implemented | 20 µm gap, separately-ringed reserved region |
| §3 dedicated analog supply routing | implemented | `vdd`/`vss`/`vref`/`vcm` are analog-domain trunks strapped between the two decode banks and the comparator; the digital region carries its own, separate, unlabelled rails |
| §2.4/§3 the SAR-logic sequencer itself | **not drawn** | there is no transistor-level netlist to place: DR-0010 keeps the sequencer and output register at rung 1 because the open gf180mcu PDK ships no 3.3 V standard-cell library. The area is reserved and ringed; that is the whole of what this layout can honestly do |

### Deviation: single-finger devices, not multi-finger / split matched pairs

Every MOSFET is drawn as **one** gate stripe at its full drawn `W`. A real
tapeout of a 80 µm PMOS would fold it into fingers, and a real matched pair
would be split and interleaved. Both are impossible to *verify* here, and
this repo's standard is that an unverifiable claim is not made:

* `design/adc-top/adc_top.spice` models each switch leg as one lumped SPICE
  device at its full `W` — that is the literal LVS target;
* the pinned `klt`'s LVS engine (`klayout_tools/lvs.py`, wrapping
  `klayout.db.NetlistComparer`) never calls `Netlist.combine_devices()` on
  either side, so a folded or interleaved device extracts as N parallel
  MOSFETs and is reported as `device.unmatched` against that one lumped
  device. Read out of the installed `klt`, not assumed.

Consequences, stated rather than hidden:

* **DR-0013's finger-count dummy** ("7 of the main device's 16 fingers, so
  the ratio survives process bias on the drawn width") is not literally
  drawn on `adc_tgate_dum` (kept standalone-drawable and LVS-matched, but no
  longer in `adc_top`/`adc_block`'s composition — DR-0014). The ratio is
  drawn as a width instead — which is exactly the construction DR-0013
  rejected. What *is* honoured is the placement half of the requirement:
  symmetric, immediately-adjacent dummies. Moot for the switch actually IN
  the composition now, `adc_tp_sw`: it is deliberately not dummy-compensated
  at all (see the matching-plan table above).
* **§2.1's common-centroid input pair** is drawn as a mirror-symmetric
  adjacent pair (`Xmb Xmip Xmin Xmt`, identically oriented, in one row),
  which cancels a gradient *between* the pair's local environments but not
  the first-order gradient across each device — that needs splitting. The
  **load resistors**, which the extraction deck cannot see as devices at
  all, ARE split and placed genuinely common-centroid (A-B-B-A).

Filed generically upstream as
[klayout-tools#261](https://github.com/2AMLogic/klayout-tools/issues/261).
Closing it is the precondition for drawing either of these two as the
matching plan intends.

### Deviation: contacts as bars, not discrete squares

The real DRM (`CO.1`) fixes contacts at 0.22 × 0.22 µm in an array. This
deck's `contact.width.1` enforces only the minimum-width half of that rule
(`decks/gf180mcu.py`'s own docstring says so), so one wide contact bar per
source/drain is legal *here* and is not legal on a real mask deck. A
deliberate use of an already-documented curated-deck approximation, taken to
keep the geometry tractable at 323 transistors.

### The MiM stack, and what issue #70 changed

The unit capacitor used to be drawn with `cw`/`cl` taken as the **Metal4**
size and FuseTop derived by insetting it (capped at 0.3 µm). That is
backwards, and it was wrong twice over:

* `cw`/`cl` are the PDK subcircuit's own `c_width`/`c_length`, i.e. the
  **FuseTop plate** — the thing whose area sets the capacitance. Insetting
  it drew a 2.114 µm plate where the ratified device is 2.7136 µm, i.e. a
  10.9 fF unit where `C_u` is 17.24 fF;
* the inset could not reach `MIMTM.3`'s 0.6 µm Metal4-over-FuseTop overlap
  at any size, because it was capped at 0.3 µm. Every one of the 1224 drawn
  stacks per block was illegal — invisibly, because the deck had no rule on
  those layers at the old pin.

`geometry.draw_mim_cap` now takes the **plate** and derives everything else
from the DRM:

| Drawn | Size | Rule |
|---|---|---|
| FuseTop (the device) | `cw` × `cl` = 2.7136 µm | ratified `C_u`, `spec/cdac-sizing-memo.md` §4 |
| Metal4 (bottom plate) | plate + 0.6 µm each side | `MIMTM.3` = `mim.enclosing.fusetop.1` |
| tiling pitch | plate + 2 × 0.6 + 1.2 = **5.1136 µm** | + `MIMTM.1` = `mim.space.1` |
| Via4 + Metal5 pad (device mode only) | 0.26 µm, ≥ 0.4 µm inside Metal4 | `MIMTM.2` = `mim.enclosing.via4.1` |

All three MiM rules, plus Metal2/Metal3/Metal5 width and space, are checked
by the pinned deck. `adc_cdac_cell`, `adc_top` and `adc_block` report
**clean** against them — the first time a clean report over this block's
capacitor geometry has meant anything at all.

**The area cost is real and is the DRM's, not this layout's**: 5.1136 µm is
the tightest a 2.7136 µm MiM unit can legally be tiled on gf180mcu. See
"Area, as drawn" — the block no longer fits DR-0006's row, and that is
recorded rather than dialled away.

### Deviation: the CDAC bottom-plate interconnect is not drawn

Each unit capacitor's Metal4 bottom plate is drawn; the per-weight network
that would tie a weight's `m` scattered units together is not. The top-plate
mesh IS drawn (Metal5, one node per side, which is what DR-0011's top-plate
sampling makes it).

The toolchain reason for this has now gone — the pinned extraction deck
carries the full Metal1–Metal5 / Via1–Via4 stack (klayout-tools#220/#238),
so Metal2/Metal3/Via2/Via3 are checkable and extractable. What remains is
the routing work itself: 512 scattered unit positions per side, ten
per-weight nets, each of which has to reach its decode switch. That is a
distinct piece of work with its own evidence to produce.

**The consequence, stated plainly:** the array's unit caps are drawn
*without* the `CAP_MK`/`MIM_L_MK` marker layers, so `klt extract` does not
recognise them as devices and `adc_top`/`adc_block`'s LVS still compares 296
and 323 transistors with **no capacitors on either side**. That is
deliberate and it is not a way of dodging a failure: marking a capacitor
whose bottom plate goes nowhere would produce 1224 extracted devices on 1224
floating nets, which is a worse result than no result, not a better one. The
markers and the interconnect land together.

What *is* proven, end to end, is the same device at the leaf: `adc_cdac_cell`
draws one unit cap with both plates wired — Via4 up to a Metal5 `top` pin,
Via3/Via2/Via1 down onto the `bp` trunk — with the markers, and `klt extract`
reports a `cap_mim_2f0_m4m5_noshield` between exactly those two nets, which
`klt lvs` matches against `design/adc-top/adc_top.spice`. The construction
the array needs is therefore demonstrated on the real device; only its
replication across the array is outstanding.

### Capacitance: what the extractor says, and why it differs

`klt extract` reports **14.7316 fF** for the drawn 2.714 µm unit plate. The
PDK model card (`cap_mim_2f0fF` in `sm141064.ngspice`, and
`sim/device-characterization-report.md` §1.2, which reproduces it to four
significant figures against measurement) gives **17.245 fF** for the same
geometry:

```
model card:  C = 1.99 fF/µm² · W·L + 0.2383 fF/µm · 2(W+L)
             = 14.658 + 2.587 = 17.245 fF
deck:        C = 2.0 fF/µm² · W·L
             = 14.732 fF                       (−14.6 %)
```

The whole difference is the **perimeter/fringe term**, which the extraction
deck's MiM device model does not have (`CapacitorDevice.area_cap_f_um2` is
its entire accuracy). It gets proportionally worse the smaller the plate, so
a unit capacitor is close to the worst case.

**The decision, explicitly:** the layout draws the plate at the ratified
2.7136 µm and the delta is *reported*. The alternative — growing the plate
to 2.936 µm so the extractor's number lands on 17.24 fF — would change the
physical device to compensate for a missing term in a tool's model, i.e.
make the drawn capacitor no longer the capacitor `design/` and `sim/`
simulate. Nothing in `spec/` moves either: `C_u` = 17.24 fF at 2.7136 µm is
untouched, because the drawn geometry *is* that device. The LVS reference
states the deck's number (see `lib/netlist.py`'s `DECK_MIM_AREA_CAP_F_UM2`)
so `klt lvs` checks what it can actually check — the capacitor's
connectivity and its drawn plate area — instead of failing on a modelling
difference no layout change could close.

Filed generically upstream:
[klayout-tools#512](https://github.com/2AMLogic/klayout-tools/issues/512).

### Caveat: the two single-unit groups are on-centre only *combined*

`centroid_tiling` puts every **even**-count weight group on the array centre
exactly, because each such group owns whole centro-symmetric position pairs
— no first-order gradient term can survive. The two **odd**-count groups
(the weight-1 bit and DR-0011's terminating unit, one unit each) cannot own
a whole pair, so they share one: their *combined* centroid is exact, and
that is the only guarantee.

The pair they share is dealt like any other, so it is **not** the
centre-most pair. As drawn, it is `(30, 7)` / `(1, 8)` in the 32 × 16 array
— each of the two units sits (14.5, 0.5) pitches, ≈ (56.8, 2.0) µm, off
centre in opposite directions. The resulting error is a
`displacement × gradient × C_u` term against a **one**-unit weight, i.e. the
two smallest and least DNL-consequential positions in the array, which is
why the deal is left alone rather than special-cased. It is recorded here,
and pinned by
[`sim/tests/test_layout_centroid_tiling.py`](../../sim/tests/test_layout_centroid_tiling.py),
so it cannot change — in either direction — without a test saying so.

*(This corrects a `centroid_tiling` docstring that claimed the two odd
groups were each displaced by "half a pitch", found in review of PR #62; the
placement is unchanged, only the claim about it.)*

## What is and is not verified

**Verified, by a committed record:**

* every Comp / Poly2 / Contact / Metal1 / Nwell width, space and enclosure
  rule in the pinned deck, over all nine cells (`klt drc`, clean);
* **the MiM capacitor stack's geometry** — `MIMTM.1` (bottom-plate spacing,
  1.2 µm), `MIMTM.2` (bottom-plate overlap of Via4, 0.4 µm) and `MIMTM.3`
  (bottom-plate overlap of the top plate, 0.6 µm), plus Metal2/Metal3/Metal5
  width and space, over all 1224 unit-capacitor footprints per block
  (`klt drc`, clean, issue #70). This row was in the "not claimable" list
  below until the pin bump, and the geometry failed `MIMTM.3` 4896 times
  when the rule first ran against it;
* the full transistor-level connectivity and every `W`/`L` of all 296
  devices `design/adc-top/adc_top.spice` defines, and of the comparator's 27
  (`klt lvs`, match);
* **one MiM capacitor as a device**, end to end: `adc_cdac_cell`'s unit cap
  extracts as a `cap_mim_2f0_m4m5_noshield` between `top` and `bp` and
  `klt lvs` matches it against `design/`. Its extracted capacitance is
  14.7316 fF for the drawn plate — see "Capacitance" above for why that is
  14.6 % below the model card's 17.245 fF and why the plate was not resized
  to close the gap;
* the CDAC tiling's own matching claim — every even-count weight group's
  centroid is the array centre exactly, the two single-unit groups' combined
  centroid is the array centre exactly, and their individual offset is the
  one stated in the caveat above (`sim/tests/test_layout_centroid_tiling.py`,
  exact rational arithmetic, no PDK and no KLayout needed). DRC and LVS are
  both blind to *which* unit position belongs to which weight, so without
  this test nothing checks the tiling at all.

**Not verified, and not claimable:**

* **the CDAC array's capacitors, as devices.** The array's 1024 unit caps
  (plus 2 terminating units and 200 dummies) are drawn without the
  `CAP_MK`/`MIM_L_MK` markers, so `adc_top`/`adc_block` extract **zero**
  capacitors and their LVS compares transistors only. The blocker is no
  longer the deck — it models the device, and `adc_cdac_cell` proves the
  whole construction on the real unit — it is that the per-weight
  bottom-plate interconnect is still undrawn. See "Deviation: the CDAC
  bottom-plate interconnect is not drawn" for why the markers are withheld
  rather than drawn onto floating plates.
* **array capacitance.** Following from the above: nothing here confirms the
  drawn array realises 512 · `C_u` per side. The unit count and the drawn
  unit size are auditable (`area.json`'s census, and the plate is now the
  ratified 2.7136 µm rather than a derived inset); the array's total
  capacitance is not extracted. What *is* extracted is one unit's, on
  `adc_cdac_cell`.
* **capacitance to the model card's accuracy.** Even where a capacitor
  *is* extracted, the deck's MiM model is area-only and reads 14.6 % low on
  a unit-sized plate — see "Capacitance" above and
  [klayout-tools#512](https://github.com/2AMLogic/klayout-tools/issues/512).
* **resistance.** The pinned deck now *has* a `ppolyf_u` resistor device
  class, but it recognises a resistor by its `RES_MK`/`SAB`/`Pplus`
  markers, none of which this layout draws — so the comparator's two 150 kΩ
  poly bodies still extract as plain Poly2 conductors, and `klt extract`
  now says so out loud (the "unmodelled poly" warning both block cells
  carry, pinned by shape count in `layout/lvs/cells/cells.json`). `klt drc`
  checks their drawn width/space/enclosure; nothing checks that they are
  150 kΩ. Marking them is the resistor analogue of what #70 did for the
  MiM cap and is not done here.
* **parasitics.** Out of scope by construction — that is #17, which the
  pin bump in this change unblocks (`klt extract --parasitics` exists at
  the pinned commit and runs on these cells).

## Resistors, and why there are two comparator cells

Because the deck extracts a poly resistor as a **conductor**, the full
`comparator` cell's `pop`, `pon` and `vdd` collapse into one net, and its LVS
reference has to say the same thing. That comparison still checks all 27
transistors, but it can no longer tell `pop` from `pon` — it would not catch
a swapped preamp output.

`comparator_nores` closes exactly that hole: identical placement and routing,
resistor bodies not drawn, `pop`/`pon` distinct, LVS `match` with zero
mismatches. Between the two runs every transistor terminal in the cell is
checked, and the resistor geometry is DRC-checked. That is the most this
toolchain can do, and it is stated rather than papered over.

## The routing model, in one paragraph

When this block was drawn, `klt extract`'s gf180mcu deck declared **one**
metal level and no vias, so the only interconnect LVS could see was Metal1
plus Poly2 (joined only through Contact). Every net therefore had to close
in a two-layer planar graph. *(That constraint has since lifted — the pinned
deck carries Metal1–Metal5 and Via1–Via4, klayout-tools#220/#238 — and the
MiM stack's plate wiring uses the upper levels. The transistor-level routing
below is deliberately left as drawn: it is DRC-clean and LVS-matched, and
re-routing 323 devices onto a five-level stack is its own piece of work with
its own evidence to produce, not a free side-effect of a toolchain bump.)*
The
construction: devices in one row with their gate heads down; one horizontal
Metal1 "trunk" per net in a channel below, **left-edge packed** so nets whose
spans do not overlap share a track; every terminal drops to its trunk on a
vertical Poly2 riser that passes under every foreign trunk without
connecting to it. Top-level straps between separately-placed blocks use the
same discipline (`geometry.stitch`), with the corridor asserted free of Comp
(a Poly2 strap over diffusion is a parasitic MOSFET) and free of Poly2 (it
would short to whatever riser is already there). This is the single biggest
shape driver in the directory and it is a tool limitation, not a design
choice — already tracked upstream as
[klayout-tools#220](https://github.com/2AMLogic/klayout-tools/issues/220),
independently re-encountered here. That fix is now IN this repo's pinned
commit, so the constraint no longer binds; what still holds this shape is
that nothing has re-drawn it yet.

Three real defects this bring-up hit and the assertions that now catch them,
recorded because each one produced a *DRC-clean* layout that was
electrically wrong:

1. per-net Metal1 buses with Metal1 stubs merged four nets into one
   (`klt extract` reported the net as `"clk,clkb,vin,vout"`) — fixed by the
   Poly2-riser scheme, which cannot express that failure;
2. a trunk extension requested *after* the channel was packed silently drew
   nothing, leaving two `vdd` pins and two `vss` pins in the extracted block
   — now `Channel.extend()` is declared before packing and
   `Channel.drop()` after `finish()` is a hard error;
3. a top-level strap grown along its own track shorted to the net sitting
   next along it (`cmpclk,ibias,topn`) — now `Channel.extend_drawn()`
   refuses to grow a trunk past a track-mate, and `geometry.stitch()`
   refuses to place a contact outside the trunk it is meant to land on.

## Area, as drawn

Supersedes [`../floorplan-matching-plan.md`](../floorplan-matching-plan.md)
§4's planning tally, per that section's own instruction ("should be
superseded … rather than edited in place") — it is left untouched. Numbers
below are bounding boxes from `area.json`, written by the generator, as of
the MiM-stack correction (issue #70).

| Region | As drawn | Previous (#67) | §4.2's estimate |
|---|---|---|---|
| CDAC array, per side (512 units + dummy ring + top-plate mesh) | 15,688 µm² (172.7 × 90.9 µm) | 9,133 µm² | — |
| CDAC arrays, both sides | **31,376 µm²** | 18,265 µm² | 12,000–16,000 µm² (§4.2 subtotal) |
| CDAC decode bank, per side (144 devices — DR-0014's fourth leg, 9 × 16) | 15,787 µm² | 13,763 µm² | (inside the §4.2 subtotal) |
| CDAC decode banks, both sides | **31,575 µm²** | 27,526 µm² | — |
| Top-plate `V_cm` switches, both sides (8 devices, DR-0014's `adc_tp_sw`) | **889 µm²** | 889 µm² | 800–1,500 µm² |
| Comparator (27 devices + 2 resistors) | **5,723 µm²** | 6,657 µm² | 1,500–3,000 µm² |
| Analog core incl. guard ring | **88,387 µm²** | 67,730 µm² | — |
| SAR-logic reserved region incl. its ring | **7,624 µm²** | 6,665 µm² | 1,000–5,000 µm² |
| **Block total (`adc_block`, 527.4 × 229.4 µm)** | **121,005 µm² = 0.12100 mm²** | 96,190 µm² | ~0.02–0.03 mm² |
| `adc_top` alone (no comparator), 461.4 × 229.4 µm | 105,853 µm² = 0.10585 mm² | 96,190 µm² | — |

> The decode bank and comparator rows are cell bounding boxes measured
> *after* the block-level rail stitch has been drawn into them, so they
> track the position of the far stitch column, not the number of devices in
> the cell. The banks did not grow — the same 144 devices sit at the same
> pitch; their rail trunks now reach further right (see below). Stated
> because the raw number invites the opposite reading.

**Against the ratified `< 0.1 mm²` row (DR-0006): 0.12100 mm², i.e. 121 % of
budget — OVER it, by 21,005 µm².** DR-0006's own row is untouched and is not
going to be: this is the layout failing a ratified row, recorded as a
failure. Tracked for recovery by a follow-up issue; nothing downstream may
quote 0.09619 mm² any more.

### Why it went over (issue #70)

The 0.09619 mm² above was measured on a MiM stack that could not be
manufactured as drawn. Every unit capacitor violated `MIMTM.3` (0.6 µm
Metal4-over-FuseTop overlap; 0.3 µm was drawn) and the tiling pitch was set
from the plate + `MIMTM.1` alone, with the 2 × 0.6 µm of bottom-plate ring
simply missing. Drawing it legally costs, per unit position,
2.7136 + 2 × 0.6 + 1.2 = 5.1136 µm of pitch instead of 3.914 µm — a factor
of 1.31 in each direction, on the one structure the block has 1224 of.

The three contributions, in order of size:

* **the arrays themselves**: 18,265 → 31,376 µm² (+13,111). Unavoidable at
  this unit size; it is the DRM's number.
* **the block got taller with them**: 209.0 → 229.4 µm, i.e. exactly the
  array's own +21.6 µm. Nothing else in the vertical stack moved.
* **`adc_block` got wider than `adc_top` for the first time**: 461.4 →
  527.4 µm. The arrays sit side by side, so their +40.8 µm each pushes the
  top-plate switch and the comparator right — far enough that the
  comparator now extends past the decode banks' own right edge. The far
  rail-stitch column has to clear all of it, and it is now derived from
  what is actually drawn (`max(bank_w, top.bbox().right) + 6 µm`) rather
  than from `bank_w`, which is what it assumed before. Without that the
  block does not build at all: `geometry.stitch` refuses to run a Poly2
  strap over the comparator's diffusion, which is exactly how the stale
  assumption surfaced.

**What was NOT done to get the number down**: the plate was not shrunk. A
2.114 µm plate (what the old construction actually drew) tiles at 4.514 µm
and would have brought the block back to ~0.104 mm², but it is a 10.9 fF
unit capacitor, not the ratified 17.24 fF one — see "Capacitance" above.
Making a ratified area row pass by quietly drawing a different device than
the one `design/` and `sim/` use is precisely the trade `CLAUDE.md` forbids.

### How it got back inside the row (issue #67) — superseded by the above

DR-0014's redraw (#66) measured 0.1136 mm² — 114 % of budget, over it by
13,623 µm², a regression from the pre-DR-0014 draw's 0.0991 mm² (#62). That
number stands as recorded; it is not restated away here. What changed is the
layout, in one place:

* **Two construction constants were sized by nothing in particular, and a
  decode bank pays for both on every device column it draws.**
  `geometry.COLUMN_GAP` — the gap between adjacent device columns' active
  islands — sat at 900 nm against a `comp.space.1` of 280 nm, and
  `place.NWELL_KEEPOUT` at 1600 nm against a clearance whose governing rule
  (`nwell.space.1`) is 600 nm. Both are now set from the threshold they exist
  for plus stated headroom: 400 nm (= 280 + 120) and 900 nm (giving
  Nwell-edge-to-foreign-NMOS-active `COLUMN_GAP + NWELL_KEEPOUT -
  NWELL_MARGIN` = 800 nm = 600 + 200). A bank crosses a column boundary 144
  times and a well boundary 17 times per side, so that is ~83 µm off the
  bank's own width per side, 16,319 → 13,763 µm² (−16 %).
* **The banks set the block's right edge, so the block narrowed with them.**
  543.6 → 460.2 µm. The height is **unchanged at 209.0 µm** — nothing in the
  vertical stack (bank channel depths, `REGION_GAP`, the array, the
  analog/digital separation) moved at all, which is the clearest evidence
  that this was a width-only, per-column change and not a floorplan
  rearrangement.
* **The comparator's reported area falls the same way it rose** (10,318 →
  6,657 µm², vs. 6,564 pre-DR-0014). Its 27-device cell is unchanged in kind;
  it is narrower for the same per-column reason as everything else, and its
  `vdd`/`vss` trunks no longer have to reach as far right, because the decode
  banks' rail column came back left with them.
* **The SAR-logic reserved region shrank with the block** (7,855 → 6,665 µm²)
  because its footprint is `max(120 µm, analog-ring-width / 3)` wide by
  40 µm tall, and the analog ring narrowed. It is still 152.9 × 40 µm of
  reserved area, comfortably above its own 120 × 40 µm floor — the reserve
  was not shaved to buy budget.
* **Nothing else moved.** Same 323 devices, same netlist, same placement
  order, same common-centroid tiling (`test_layout_centroid_tiling.py` still
  passes unchanged), same two-layer routing model, same floorplan structure.
  The arrays' own numbers (9,133 µm² per side) are byte-identical, because
  the MiM pitch is set by the PDK's `MIMTM.3` spacing and not by any of this.
  *(That last sentence was true of #67's change and false about the pitch:
  the pitch was missing `MIMTM.3`'s ring entirely — issue #70.)*

Why this is a verified change and not an argued one: `comp.space.1` is a rule
the pinned deck **checks**, so drawing at 400 nm is a claim `klt drc` can
falsify — and the DRC record above is it. Every other clearance that crosses
a column boundary (S/D poly risers, S/D Metal1 drop stubs, S/D contact bars,
gate heads) is looser than `comp.space.1` by construction, and each is now
asserted at import in `lib/geometry.py` beside the pre-existing
device-internal asserts, so "`comp.space.1` is the binding rule here" is
checked rather than asserted in prose. The one clearance the deck does **not**
cover — the DRM's "Nwell to unrelated COMP", which is not in the pinned deck
at all — is asserted per drawn row in `place._assert_nwell_clearances`, which
is the only place it could be caught.

What has **not** changed is the pair of verification-driven constructions that
still dominate this block's area: single-finger devices spending area linearly
in `W`, and single-metal-level planar routing forcing one horizontal track per
simultaneously-live net. Closing either upstream gap
([#261](https://github.com/2AMLogic/klayout-tools/issues/261),
[#220](https://github.com/2AMLogic/klayout-tools/issues/220)) would still move
this number by roughly a factor of two on the dominant term; neither is
available at this repo's pinned `klt` commit, and nothing here claims
otherwise. This change bought margin inside the current toolchain's
constraints, which is what was available to buy.

## Friction filed upstream

Per `CLAUDE.md`'s friction protocol — tool capability only, described
generically, never this design's specifics.

| Gap | Upstream issue | Filed by this work? |
|---|---|---|
| MiM capacitor device model is plate-**area** only — no perimeter/fringe term — so extracted `C` is systematically low against the PDK's own model card (−14.6 % at a unit-sized plate, worse as plates shrink) | [#512](https://github.com/2AMLogic/klayout-tools/issues/512) | **yes — new** (issue #70) |
| LVS has no device-merge step, so a folded / split / interleaved matched device cannot be compared against a lumped schematic device | [#261](https://github.com/2AMLogic/klayout-tools/issues/261) | **yes** — filed by #57, still open, and the one that most constrains this block's matching |
| Extraction deck exposes one metal level and no vias, so an LVS-verifiable layout must be two-layer planar | [#220](https://github.com/2AMLogic/klayout-tools/issues/220) | no — filed and closed upstream, and **the fix is now in this repo's pinned commit** |
| Extraction decks recognise MOS only — no capacitor or resistor device class | [#219](https://github.com/2AMLogic/klayout-tools/issues/219), [#222](https://github.com/2AMLogic/klayout-tools/issues/222), [#225](https://github.com/2AMLogic/klayout-tools/issues/225) | no — closed upstream, and **the capacitor half is now in the pinned commit and used here** |
| DRC deck has no MiM / upper-metal rule coverage | [#188](https://github.com/2AMLogic/klayout-tools/issues/188) | no — filed by #15; **closed upstream and now in the pin**, which is what found this block's 4896 `MIMTM.3` violations |
| A stream drawn entirely on uncovered layers reports `clean`; no coverage manifest | [#189](https://github.com/2AMLogic/klayout-tools/issues/189) | no — filed by #15; the deck now emits a `coverage` block naming checked layers and skipped rules |
| No `klt extract` RC parasitic path (matters for #17) | [#216](https://github.com/2AMLogic/klayout-tools/issues/216) | no — filed and closed upstream; **`--parasitics` is in the pin as of issue #70** |

## What this unblocks, and what it does not

**#17 (post-layout extracted re-run) is unblocked by this change.** It
needed three things that did not exist together before: a DRC-clean layout
including its MiM stack, `klt extract --parasitics`, and an extracted
netlist that contains a capacitor at all. The first two are now true of
`adc_top.gds`/`adc_block.gds` at the pinned commit — `klt extract
--parasitics` runs on them and emits lumped RC per net.

The third is true **only at the leaf**: `adc_cdac_cell` extracts its unit
capacitor, `adc_top`/`adc_block` still extract none, because the array's
per-weight bottom-plate interconnect is undrawn and its unit caps are
therefore left unmarked (see "Deviation" above). A block-level post-layout
netlist from this flow is still a netlist of switches with no CDAC in it.
#17 should either work from the leaf cell plus the schematic array, or wait
on the follow-up that draws the array interconnect — but it no longer waits
on the toolchain, and the construction it needs is demonstrated.
