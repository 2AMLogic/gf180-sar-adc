# Record 20260805-layout-pin-dc

- **Record ID**: 20260805-layout-pin-dc
- **Claim**: issue #91 -- the DR-0014 fourth-leg analog-input rail
  (`design/adc-top/adc_top.spice`'s `adc_cdac_side.vin`) is now a real,
  drawn, labelled pin of the physical layout (`layout/adc-top/gen_adc_top.py`),
  not just of the LVS reference. A RAW `klt extract` (no
  `remediate_extracted.py` post-processing) of the current `adc_top.gds` /
  `adc_block.gds` declares `pinp`/`pinn` as `.SUBCKT` pins, `klt lvs`/`klt
  drc` are unaffected, and a DC `op` across the full #13 `cdac` PVT grid
  shows each pin driving its own side's nine weighted cells' fourth-leg
  T-gate source (bottom plate) to exactly the voltage forced on the pin --
  not floating, not shorted to `vss`/`vcm`/`vref` or the opposite side's pin.
- **Netlist provenance**: extracted (`klt extract`, RAW -- no remediation)
- **Source extraction**: `layout/adc-top/parasitics/reports/20260805-122607-e8017f2/{adc_top,adc_block}.para.spice`
  (repo sha `e8017f2`, `klt 0.2.0`, pin `af5791b`, `--pdk gf180mcuA`)
- **PDK binding (this DC verification)**: gf180mcuD, open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, resolved via `sim/harness/pdk.py`
  (`search_root:~/.volare`), MiM stack `m4m5`. ngspice-46.

## Root cause (Test Plan item 1): label-only, not a routing gap

Confirmed directly, not guessed. `design/adc-top/adc_top.spice`'s
`adc_cdac_side.vin` is a broadcast net shared by all nine weighted
`adc_cdac_cell` instances of one side -- structurally identical to
`sel_in`/`vref`/`vcm`/`vss`, which the layout already pin-labels correctly.
`layout/adc-top/gen_adc_top.py`'s `block_subckt()` already resolves `vin` to
`pin{tag}` (`pinp`/`pinn`) one level up, before the flattened device list
ever reaches `place.draw_devices()` -- so every one of a side's nine
`Xsi` T-gate drain terminals already carries the literal net name `pinp` (or
`pinn`), and `lib/geometry.Channel._spans()` already merges all nine drops
into ONE continuous Metal1 trunk spanning the whole decode-bank row, exactly
like the rail nets. `Channel.finish()` draws every net's trunk
unconditionally but only emits a Metal1 (34/10) pin label
(`Channel.mark_pin()`) for nets named in the `pins=` argument -- and
`gen_adc_top.py`'s per-side `pins=bank_shared + [...]` list simply never
included `pinp`/`pinn`. The net was therefore already a real, correctly
routed, single-piece trunk with no external name: `klt extract` reported it
as an anonymous net (`$8`/`$91` on the full `ADC_TOP` after per-side
merging), never floating and never shorted to anything else.

**Fix**: `gen_adc_top.py` now passes `pinp` (P-side bank) / `pinn` (N-side
bank) into each decode bank's `pins=` list. No routing change; the drawn
polygons are byte-identical except for the two new Metal1 label texts (GDS
bounding boxes/dimensions unchanged, confirmed by `area.json` being
byte-identical before/after).

## `klt extract` (Test Plan item 2): pin now declared

| block | pin_count before | pin_count after | device_count | net_count |
|---|---|---|---|---|
| `ADC_TOP` | 63 | **65** | 1320 (unchanged) | 177 (unchanged) |
| `ADC_BLOCK` | 67 | **69** | 1347 (unchanged) | 198 (unchanged) |

Device/net counts unchanged (a label adds no geometry, no connectivity) --
exactly what a label-only fix predicts. Full extraction summary:
[`../reports/20260805-122607-e8017f2/`](../reports/20260805-122607-e8017f2/),
record
[`20260805-122607-e8017f2.md`](20260805-122607-e8017f2.md).

## `klt lvs` / `klt drc` (Test Plan item 3): no regression

```
python3 layout/lvs/run_lvs.py --check
python3 layout/drc/run_drc.py --check
```

| check | `adc_top` | `adc_block` |
|---|---|---|
| `klt drc` | clean | clean |
| `klt lvs` status | match | match |
| `klt lvs` mismatch_count | 0 | 2 (pre-existing resistor-ambiguity warnings, unrelated -- see `../../adc-top/README.md`) |
| `klt lvs` pins (layout / reference / matched) | 65 / 65 / 65 | 69 / 69 / 69 |

Before this fix, `klt lvs` already reported `status: match` for `adc_block`
despite the layout declaring 67 pins against the reference's 69 (the
reference already listed `pinp`/`pinn` -- `gen_adc_top.py`'s `pin_set`
construction always did, independent of whether the GDS drew the label) --
`klt lvs`'s `NetlistComparer` matches structurally, not by pin-count parity,
so this gap was never visible as an LVS failure. It is visible now as
`pins: 65/65/65` and `69/69/69`, an improvement over the previous silent
mismatch, not a new pass/fail state. Full run:
[`../../lvs/records/20260805-122516-e8017f2.md`](../../lvs/records/20260805-122516-e8017f2.md),
[`../../drc/records/20260805-122538-e8017f2.md`](../../drc/records/20260805-122538-e8017f2.md).

## DC smoke test (Test Plan item 4): pin reaches the T-gate source

```
python3 layout/adc-top/parasitics/verify_layout_pin_dc.py --corners cdac --top ADC_TOP \
    --json reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_top.json
python3 layout/adc-top/parasitics/verify_layout_pin_dc.py --corners cdac --top ADC_BLOCK \
    --json reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_block.json
```

Unlike `verify_remediation_dc.py` (PR #92), this composes a DC `op` directly
against the **RAW** `klt extract` output -- no `remediate_extracted.py` call
in between -- driving every one of the RAW extraction's own declared pins
(`pinp`/`pinn` included, at 1.0 V / 2.3 V, chosen distinct from every other
rail this core drives: `vss`=0 V, `vcm`=vdd/2, `vref`=vdd) with the fourth
leg's own decode gate ON (`sel_in`=vdd) and every other leg OFF
(`rel_*`/`hi_*`/`lo_*`=0, so no other leg can also claim the same bottom
plate and mask a `pinp`/`pinn` connectivity defect). Every one of a side's
nine weighted cells' bottom-plate node (identified structurally, the same
rule `remediate_extracted._find_input_rails` uses) is probed via a written
`.raw` file (`print v(...)` cannot address these `$`-prefixed anonymous
nets -- `$` opens a SPICE comment -- the same reason
`verify_remediation_dc.raw_body_nodes()` uses the binary-rawfile route for
the anonymous PMOS-body nodes).

| check | `ADC_TOP` | `ADC_BLOCK` |
|---|---|---|
| `pinp`/`pinn` declared in the RAW extraction | yes | yes |
| DC `op` convergence, 63-point `cdac` grid | 63/63 | 63/63 |
| bottom plates reached via `pinp` (of 9) | 9 | 9 |
| bottom plates reached via `pinn` (of 9) | 9 | 9 |
| `pinp` driven 1.0 V -> bottom plates | all 1.000000 V | 1.000001 - 1.000108 V |
| `pinn` driven 2.3 V -> bottom plates | all 2.300000 V | 2.300000 - 2.300233 V |
| reaches the fourth leg's T-gate source | **yes** | **yes** |

**Not floating**: an unconnected `pinp`/`pinn` would leave every bottom plate
at its own separate, un-driven equilibrium instead of tracking the forced
1.0 V / 2.3 V -- it does not. **Not shorted**: a short to `vss` (0 V),
`vcm` (vdd/2), `vref` (vdd), or the opposite side's pin (2.3 V on the `pinp`
side or 1.0 V on `pinn`) would pull the bottom plates to one of those
values instead -- none of the 18 probed nodes (9 per side, both blocks) land
anywhere but their own side's driven value. `ADC_BLOCK`'s residual (up to
+0.233 V on the deepest weight) is the comparator's added leakage paths
through the shared rails at DC equilibrium, not a connectivity defect -- well
inside the 5 mV-scale-appropriate tolerance the script checks against 1 mV
increments of drift, and two orders of magnitude below a "shorted to a
different rail" signature (which would show a multi-hundred-mV to multi-volt
jump, not a sub-1V-fraction creep).

Full per-point convergence and per-node probe values:
[`../reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_top.json`](../reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_top.json),
[`../reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_block.json`](../reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_block.json).

## `remediate_extracted.py` forward-compatibility (found while re-running the existing #89 evidence chain)

Minting a fresh extraction record (`20260805-122607-e8017f2`) makes it the
new "latest report" `remediate_extracted._latest_report()` /
`gen_extracted_core_tb.py` pick up by default -- and its rails are now
ALREADY named `pinp`/`pinn` pins, not anonymous `$8`/`$91`. That broke
`remediate_extracted.py`'s structural rail-detection outright
(`ValueError: expected exactly 2 sampled-input rails, found 0`), because its
"already a declared pin -> not a rail candidate" guard, written against a
netlist that could never have a pinned rail, now excludes the real rails
too.

**Fixed** (`remediate_extracted.py`, this PR): the guard now carves out
exactly `pinp`/`pinn` (the two names issue #91's layout generator gives the
rail) from the "already pinned -> excluded" rule, and the emitted `.SUBCKT`
pin header drops the raw rail name before appending the canonical
`vinp`/`vinn` pair (so a promoted rail is not declared twice). Verified
both directions:

```
python3 layout/adc-top/parasitics/remediate_extracted.py --check                          # new report: pinp/pinn -> vinp/vinn
python3 layout/adc-top/parasitics/remediate_extracted.py --top ADC_BLOCK --check           # new report, ADC_BLOCK
python3 layout/adc-top/parasitics/remediate_extracted.py reports/20260805-102856-1118e9a/adc_top.para.spice --top ADC_TOP --check    # pre-#91 report still works: $8/$91 -> vinp/vinn
python3 layout/adc-top/parasitics/remediate_extracted.py reports/20260805-102856-1118e9a/adc_block.para.spice --top ADC_BLOCK --check
python3 layout/adc-top/parasitics/verify_remediation_dc.py --corners cdac --top ADC_TOP    # 63/63, unchanged
python3 layout/adc-top/parasitics/verify_remediation_dc.py --corners cdac --top ADC_BLOCK  # 63/63, unchanged
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py                      # 3/3 known transitions decode correctly, unchanged
```

All pass. The full #89 evidence chain (`verify_remediation_dc.py`,
`gen_extracted_core_tb.py`, `verify_extracted_core_conversion.py`) continues
to work unchanged against both the new and every previously-committed
report.

## Friction protocol

No `klt`/klayout-tools capability gap found or filed for this issue: the pin
label mechanism (`Channel.mark_pin()` -> Metal1 (34/10) label) already
existed and already worked for every other net in this block (issues
#85-#88) -- this was a one-line omission in the caller's `pins=` list, not a
tool limitation.

## Artifacts in this record

- `reports/20260805-122607-e8017f2/` -- the RAW re-extraction this record's
  pin-count table and DC smoke test are taken against (issue #17's ordinary
  parasitic-extraction record trail, minted by `run_extract_parasitics.py`).
- `reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_top.json` -- full
  DC verification result for `ADC_TOP` (per-point convergence, per-node
  bottom-plate probe values, PDK provenance).
- `reports/20260805-layout-pin-dc/verify_layout_pin_dc_adc_block.json` --
  same, for `ADC_BLOCK`.
- `../../lvs/records/20260805-122516-e8017f2.md`,
  `../../drc/records/20260805-122538-e8017f2.md` -- the LVS/DRC re-run this
  record's "no regression" table is taken from.

Append-only per `sim/README.md`'s evidence rule: this record is never
overwritten. A later change to the fourth-leg pin (name, routing) mints a new
`<record-id>` beside it.
