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
    gen_adc_cells.py       generates the four leaf cells below
    adc_drv.*              local T-gate driver          (2 devices)
    adc_tgate.*            CDAC bottom-plate T-gate     (2 devices)
    adc_tgate_dum.*        input sampling switch        (4 devices)
    adc_cdac_cell.*        one weighted CDAC position   (12 devices + 1 cap)
  gen_comparator.py        generates the comparator cells
    comparator.*           comparator + load resistors  (27 devices + 2 R)
    comparator_nores.*     same, resistor bodies omitted
  gen_adc_top.py           generates the block
    adc_top.*              the block: exactly adc_top.spice    (224 devices)
    adc_block.*            the assembled block: + comparator   (251 devices)
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

Bring-up records: DRC
[`layout/drc/records/20260801-225603-7866d03.md`](../drc/records/20260801-225603-7866d03.md),
LVS
[`layout/lvs/records/20260801-225959-7866d03.md`](../lvs/records/20260801-225959-7866d03.md).

| Cell | Devices | `klt drc` | `klt lvs` vs. `design/` |
|---|---|---|---|
| `adc_drv` | 2 | clean | match, 0 mismatches |
| `adc_tgate` | 2 | clean | match, 0 mismatches |
| `adc_tgate_dum` | 4 | clean | match, 0 mismatches |
| `adc_cdac_cell` | 12 | clean | match, 0 mismatches |
| `comparator_nores` | 27 | clean | match, 0 mismatches |
| `comparator` | 27 (+2 R) | clean | match, 2 `warning` findings † |
| **`adc_top`** | **224** | **clean** | **match, 0 mismatches** |
| **`adc_block`** | **251** | **clean** | **match, 2 `warning` findings †** |

† `status: "match"` with a non-zero `mismatch_count` is not a contradiction:
`klt lvs`'s verdict is always `NetlistComparer.compare()` itself, and both
findings are severity `warning` — "nets were paired ambiguously; the
comparer resolved it structurally". They appear only in the two cases that
contain the comparator's load resistors, for the reason in
"Resistors" below, and `comparator_nores` is the companion case that removes
the ambiguity.

**`adc_top`'s LVS target is `design/adc-top/adc_top.spice` exactly** — two
`adc_cdac_side` arrays and the two `adc_tgate_dum` sampling switches, the
same composition `sim/adc-enob-fft/testbench/` instantiates. `adc_block` is
that plus `design/comparator/comparator.spice`'s comparator, strapped to the
top plates and the analog rails.

## What the matching plan asked for, and what is drawn

Against [`../floorplan-matching-plan.md`](../floorplan-matching-plan.md).
Every row is either *implemented* or a **stated deviation** — nothing is
silently skipped.

| Plan | Status | Where / why |
|---|---|---|
| §1.1 512 unit positions per side, plain binary, free-MSB | implemented | 32 × 16 grid per side, 1024 units total; per-weight census in `area.json` (`256`:256 … `1`:1, `term`:1) |
| §1.2 MiM `cap_mim_2f0fF`, `C_u` = 17.24 fF at 2.7136 µm | implemented (drawn, **unverifiable**) | `geometry.draw_mim_cap`; the deck has no rule on Metal4/FuseTop/Metal5 — see "What is not verified" |
| §1.3 common-centroid unit-cap tiling | implemented, with a stated caveat | `gen_adc_top.centroid_tiling` — centro-symmetric position pairs, bit-reversed deal; common-centroid *by construction*, not by inspection. Exact for every even-count weight; the two single-unit groups are exact only *combined* — see "Caveat" below. Asserted by [`sim/tests/test_layout_centroid_tiling.py`](../../sim/tests/test_layout_centroid_tiling.py) |
| §1.3 full dummy ring | implemented | one extra tile all round, identical drawn geometry, electrically floating |
| §1.3 routing kept off the capacitor dielectric | implemented | nothing but the Metal5 top-plate mesh is drawn over the array; all switch/driver routing is Metal1/Poly2 in a separate region |
| §1.4 single top-plate net per side, short path from the electrical centre, P/N symmetric | implemented (drawn, unverifiable) | Metal5 row straps + a spine on the array's own centre, identical on both sides |
| §1.4 no daisy-chaining | implemented | mesh, not chain |
| §1.5 sampling switch at the array's input edge, not inside the array | implemented | `ADC_SAMPLE_SW` placed beside the arrays |
| §1.5 dummy placed symmetrically w.r.t. its main device | implemented | device order `XDN XN | XN XDN` / `XDP XP | XP XDP` — each dummy abuts its own main device and the P/N sides mirror |
| §1.5/DR-0013 dummy drawn as a **finger count** (7 of 16 fingers) | **deviation** | drawn as one lumped device at `W = rd·W_main`. See "Single-finger devices" |
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
  drawn. The ratio is drawn as a width instead — which is exactly the
  construction DR-0013 rejected. What *is* honoured is the placement half of
  the requirement: symmetric, immediately-adjacent dummies.
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
keep the geometry tractable at 251 transistors.

### Deviation: the CDAC bottom-plate interconnect is not drawn

Each unit capacitor's Metal4 bottom plate is drawn; the per-weight network
that would tie a weight's `m` scattered units together is not. It needs
Metal2/Metal3 and Via2/Via3 — layers the `klt drc` deck has no rule for and
the `klt extract` deck does not read — so drawing it would add geometry no
tool in this toolchain can check, while making the stream *look* more
complete than it has been shown to be. The top-plate mesh IS drawn (Metal5,
one node per side, which is what DR-0011's top-plate sampling makes it).

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
  rule in the pinned deck, over all eight cells (`klt drc`, clean);
* the full transistor-level connectivity and every `W`/`L` of all 224
  devices `design/adc-top/adc_top.spice` defines, and of the comparator's 27
  (`klt lvs`, match);
* the CDAC tiling's own matching claim — every even-count weight group's
  centroid is the array centre exactly, the two single-unit groups' combined
  centroid is the array centre exactly, and their individual offset is the
  one stated in the caveat above (`sim/tests/test_layout_centroid_tiling.py`,
  exact rational arithmetic, no PDK and no KLayout needed). DRC and LVS are
  both blind to *which* unit position belongs to which weight, so without
  this test nothing checks the tiling at all.

**Not verified, and not claimable:**

* **the MiM capacitor stack.** `layout/README.md` already records that the
  deck has no rule on Metal4 (46/0), FuseTop (75/0), Metal5 (81/0), Via4 or
  the intermediate metals — `layout/drc/cells/uncovered_layer_probe` exists
  to demonstrate exactly that, and `layout/floorplan-matching-plan.md` §1.2
  states the consequence in advance: *a clean DRC report over this array's
  MiM geometry means nothing was checked.* The 1024 unit capacitors are the
  most matching-critical geometry in the block and the deck is silent about
  every one of them (klayout-tools
  [#188](https://github.com/2AMLogic/klayout-tools/issues/188)/[#189](https://github.com/2AMLogic/klayout-tools/issues/189)).
  The capacitor geometry here is drawn to the PDK's own published MIM rules
  (`MIMTM.1`/`.2`/`.3`) by construction — a 1.2 µm inter-cell gap and a
  bottom-plate-largest stack — which is a *design-time* argument, not a
  checked result.
* **capacitance.** No tool in this toolchain extracts a capacitor, so
  nothing here confirms the drawn array realises 512 · `C_u` per side. The
  unit count and the drawn unit size are auditable (`area.json`'s census);
  the capacitance is not.
* **resistance.** Same reason: the deck has no resistor device class, so the
  comparator's two 150 kΩ poly bodies extract as plain Poly2 conductors.
  `klt drc` does check their drawn width/space/enclosure; nothing checks
  that they are 150 kΩ.
* **parasitics.** Out of scope by construction — that is #17.

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

`klt extract`'s gf180mcu deck declares **one** metal level and no vias, so
the only interconnect LVS can see is Metal1 plus Poly2 (joined only through
Contact). Every net therefore has to close in a two-layer planar graph. The
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
independently re-encountered here (that issue is closed on `main`, but the
fix lands after this repo's pinned commit — see `../toolchain.json` for why
the pin does not float).

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
below are bounding boxes from `area.json`, written by the generator.

| Region | As drawn | §4.2's estimate |
|---|---|---|
| CDAC array, per side (512 units + dummy ring + top-plate mesh) | 9,133 µm² (131.9 × 69.3 µm) | — |
| CDAC arrays, both sides | **18,265 µm²** | 12,000–16,000 µm² (§4.2 subtotal) |
| CDAC decode bank, per side (108 devices) | 12,725 µm² (401.4 × 28.8 µm) | (inside the §4.2 subtotal) |
| CDAC decode banks, both sides | **25,450 µm²** | — |
| Input sampling switches (both, 8 devices) | **2,650 µm²** | 800–1,500 µm² |
| Comparator (27 devices + 2 resistors) | **6,564 µm²** | 1,500–3,000 µm² |
| Analog core incl. guard ring | **71,019 µm²** | — |
| SAR-logic reserved region incl. its ring | **6,564 µm²** | 1,000–5,000 µm² |
| **Block total (`adc_block`, 453.1 × 218.6 µm)** | **99,060 µm² = 0.0991 mm²** | ~0.02–0.03 mm² |
| `adc_top` alone (no comparator, 412.5 × 218.6 µm) | 90,180 µm² = 0.0902 mm² | — |

**Against the ratified `< 0.1 mm²` row (DR-0006): 0.0991 mm², i.e. 99 % of
budget — inside it, with essentially no margin.** That is a far worse result
than §4.2's 0.02–0.03 mm² planning estimate predicted, and the reason is not
the design:

* §4.2 priced the CDAC capacitor core at 7,520 µm² and it came in at 18,265
  µm² with tiling, dummy ring and the PDK's own 1.2 µm MIM spacing — a 2.4×
  layout multiplier against §4.2's assumed 1.5–2×. That part is real design
  cost and is the one line that behaved roughly as planned.
* Everything else is dominated by the two verification-driven constructions
  above. **Single-finger devices** spend area linearly in `W` where a folded
  device would spend it in `W/n`; the 80 µm sampling PMOS alone sets an
  85 µm-tall row. **Single-metal-level planar routing** forces one
  horizontal track per simultaneously-live net and a ~3.4 µm column pitch,
  where a real 5-metal flow would route over the devices. Left-edge track
  packing already bought ~35 µm of channel height back on the decode banks;
  the residue is structural.

So the honest reading is: the *design* still fits the ratified row
comfortably, and the *drawable-and-verifiable-with-this-toolchain* layout
only just does. The spec row is not relaxed and nothing here asks for it to
be. The two upstream gaps above ([#220](https://github.com/2AMLogic/klayout-tools/issues/220),
[#261](https://github.com/2AMLogic/klayout-tools/issues/261)) are the ones
whose closure would move this number, and either is worth roughly a factor
of two.

## Friction filed upstream

Per `CLAUDE.md`'s friction protocol — tool capability only, described
generically, never this design's specifics.

| Gap | Upstream issue | Filed by this work? |
|---|---|---|
| LVS has no device-merge step, so a folded / split / interleaved matched device cannot be compared against a lumped schematic device | [#261](https://github.com/2AMLogic/klayout-tools/issues/261) | **yes — new**, and the one that most constrains this block's matching |
| Extraction deck exposes one metal level and no vias, so an LVS-verifiable layout must be two-layer planar | [#220](https://github.com/2AMLogic/klayout-tools/issues/220) | no — already filed and closed upstream; independently re-encountered here, and the fix lands after this repo's pinned commit |
| Extraction decks recognise MOS only — no capacitor or resistor device class | [#219](https://github.com/2AMLogic/klayout-tools/issues/219), [#222](https://github.com/2AMLogic/klayout-tools/issues/222), [#225](https://github.com/2AMLogic/klayout-tools/issues/225) | no — already open/closed upstream |
| DRC deck has no MiM / upper-metal rule coverage | [#188](https://github.com/2AMLogic/klayout-tools/issues/188) | no — filed by #15 |
| A stream drawn entirely on uncovered layers reports `clean`; no coverage manifest | [#189](https://github.com/2AMLogic/klayout-tools/issues/189) | no — filed by #15 |
| No `klt extract` RC parasitic path (matters for #17, not for this issue) | [#216](https://github.com/2AMLogic/klayout-tools/issues/216) | no — already filed and closed upstream |

## What this unblocks, and what it does not

#17 (post-layout extracted re-run) needs a DRC/LVS-clean layout to extract
from; `adc_top.gds`/`adc_block.gds` are it. Note before starting: `klt
extract` in this pinned toolchain produces a **schematic-equivalent**
netlist, explicitly *no parasitics* (`docs/cli/extract.md`), and reads only
Metal1 — so the top-plate and reference-rail parasitics #17 most wants are
not obtainable from this flow as pinned. `klt extract --parasitics` has
since landed upstream ([#216](https://github.com/2AMLogic/klayout-tools/issues/216)/[#217](https://github.com/2AMLogic/klayout-tools/issues/217)),
after this repo's pinned commit, so #17's first task is a toolchain-pin bump
— which will also require re-baselining `layout/drc/cells/cells.json`'s
`uncovered_layer_probe` expectations (see `../toolchain.json`'s `_comment`).
Better found here than four review cycles in.
