# Record 20260806-adc-block-comparator-input-open

- **Record ID**: 20260806-adc-block-comparator-input-open
- **Claim**: issue #116 Scope item 1 — the `ADC_BLOCK` stuck-code defect
  reproduced by `records/20260806-adc-block-comparator-smoke.md` (every
  probed transition decoding to **1023** at two PVT corners) is **root-caused
  to two independent, both structural, defects** and **fixed**. A
  comparator-inclusive extracted-netlist conversion
  (`verify_extracted_core_conversion.py --top ADC_BLOCK_NORES`) now decodes
  correctly at **both** corners the failing run used, with the `ADC_TOP`
  control unchanged. This record does **not** make any regeneration-margin,
  settling or rate-closure claim — those are Scope items 2–4 and remain open.
- **Netlist provenance**: extracted, then remediated (PMOS bodies → `vdd`,
  input rails promoted to `vinp`/`vinn`, and — for `ADC_BLOCK_NORES` only —
  the comparator's two 150 kΩ preamp load resistors restored as ideal
  `ppolyf_u_2k` devices; see "What is not post-layout" below) —
  `Netlist provenance: extracted`.
- **Source extraction**:
  `layout/adc-top/parasitics/reports/20260806-194351-a0dbcf6/adc_block_nores.para.spice`
  (and `adc_block.para.spice` / `adc_top.para.spice` from the same run, for the
  two controls).
- **PDK binding**: gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
  resolved via `sim/harness/pdk.py`. ngspice-46. `klt 0.2.0` at
  `layout/toolchain.json`'s pin `af5791b557fc7c669c3981335a294256ccf37e6f`
  (**unchanged** by this record — the pin bump is Scope item 3 and is not
  done here).
- **Working tree**: tracked files clean at commit `a0dbcf6` (the fix commit
  this record's own repro commands were run against) — `git status
  --porcelain` shows no tracked modifications, only this record's own new
  files, per the citability lesson
  `sim/adc-enob-fft/records/20260806-081350-862d054.md` documents.

## Root cause

### Defect 1 — the comparator's differential input was never connected

`layout/adc-top/gen_comparator.py`'s `build_into()` called
`lib/netlist.resolve_aliases(devices, aliases)` **without a `prefer=` set**.

`design/comparator/comparator.spice` ends its `comparator` subckt with two
zero-volt top-plate current probes:

```
Vpp preamp_in1 vinp dc 0
Vpn preamp_in2 vinn dc 0
```

`lib/netlist.flatten()` correctly turns those into net *aliases*
(`preamp_in1 ≡ vinp`, `preamp_in2 ≡ vinn`) rather than components. But
`resolve_aliases()`'s union-find keeps the member of `prefer` when the merged
set contains one, and **otherwise the lexicographically smallest name**. With
`prefer` empty:

| merged set | name kept | name wanted |
|---|---|---|
| `{preamp_in1, vinp}` (standalone cell) | `preamp_in1` | `vinp` |
| `{XCMP.preamp_in1, topp}` (assembled block) | `XCMP.preamp_in1` | `topp` |

Both the **drawn placement** (`by_path` is built from the alias-resolved
device list) and the **LVS reference** (`ref_devices`) come from that one
call. So the preamp input pair's gates were drawn on an internal net, the
`vinp`/`vinn` (resp. `topp`/`topn`) trunk the cell exports was drawn with
nothing attached to it, and the reference said the same thing. In
`adc_block.gds` **the comparator's differential input was not connected to
the CDAC top plates at all** — the preamp gates were floating.

That is exactly the singular node the failing record saw. In the pre-fix
extraction (`reports/20260805-102856-1118e9a/adc_block.para.spice`):

```
X$141 vdd \$167 \$166 vsubs nfet_03v3 L=1U W=40U   <- preamp Xmip
X$144 vdd \$168 \$166 vsubs nfet_03v3 L=1U W=40U   <- preamp Xmin
```

`\$168` appears on exactly one device terminal — that gate — plus its own
parasitic `R_168`/`C_168` stub. No DC path, hence
`Warning: singular matrix: check node xdut.\$168` through every solver
fallback.

**Why LVS did not catch it.** The same `resolve_aliases()` call writes the
comparison's *reference*, so both sides carried the identical defect. `klt
lvs` could only report it as two severity-`warning` rows —

```
"nets were paired ambiguously; the comparer resolved it structurally"
  layout "$167" <-> reference "XCMP.PREAMP_IN1"
  layout "$168" <-> reference "XCMP.PREAMP_IN2"
```

(verbatim from `layout/lvs/reports/20260805-122516-e8017f2/adc_block.lvs.json`)
— and `layout/lvs/cells/cells.json` had those two pinned as **expected**,
attributed to the load-resistor short (defect 2 below). The signal was
present in every LVS record this repo has; the attribution was wrong.

**Fix**: `prefer=set(labelled)` on that call. `comparator` pin_count 7 → 9
(`vinp`/`vinn` become real pins), `adc_block` net_count 198 → 196 (the two
dangling preamp-input nets stop existing), and both cases drop from 2
`topology` warnings to **0 mismatches**.

### Defect 2 — the preamp load resistors short `pop`/`pon` to `vdd`

Fixing defect 1 alone does **not** make `ADC_BLOCK` decode (measured — see
the `ADC_BLOCK` control row below, run at this record's own commit with
defect 1 already fixed). The pinned `klt extract` gf180mcu deck has no
resistor device class and no silicide-block layer, so a drawn p+ poly
resistor body extracts as a plain Poly2 **conductor** — already documented in
`gen_comparator.py`'s docstring and `layout/adc-top/README.md`'s "Resistors"
section, and the reason the `comparator_nores` companion cell exists.

At LVS that costs only resolution. In a **post-layout transient it is
fatal**: `pop`, `pon` and `vdd` are one net, so

```
X$141 vdd topp  \$166 ...   <- preamp drain on vdd, no 150k load
X$150 \$169 vdd \$168 ...   <- StrongARM latch input gate on vdd
```

both preamp drains **and** both latch input gates sit hard-tied to the
supply. The preamp has no load resistance and therefore no gain; the latch's
input pair sees no differential drive at all. The decision is a constant,
independent of the array — which is precisely the reported symptom (the same
stuck code for all 30 strobe edges, and flipping to the *other* constant when
`dout`/`doutb` are swapped, as the failing record already found).

**Fix**: a block-level analogue of `comparator_nores`. `gen_adc_top.py`'s
`build(..., comparator_resistors=False)` writes **`adc_block_nores`** — the
same assembled block, resistor bodies omitted, so `pop`/`pon` survive
extraction as distinct nets — and
`parasitics/remediate_extracted._restore_preamp_loads()` puts the two
resistors back as the ideal `ppolyf_u_2k` devices
`design/comparator/comparator.spice` specifies. `adc_block_nores` is a
**simulation companion, not a deliverable**: `adc_block` (with the resistors
drawn, DRC-checked) remains the block this repo ships.

The restoration is located **structurally, not by name** — the extracted
`pop`/`pon` are anonymous `$N` nets, so a name lookup would be a guess. It
finds the two drains of the only 40 µm/1 µm NMOS pair in the block, asserts
they are distinct, share one tail source, and are not already `vdd`, and
raises otherwise. **No polarity can be guessed wrong**: the two resistors are
electrically identical and symmetric (`Xrlp vdd pop vss` / `Xrln vdd pon
vss`), so only the *set* of two nets matters, never which is which.

### A third defect, found by the companion block

`gen_adc_top._clear_offset()` — the search that picks the comparator's Y
placement so its Metal1 straps clear already-placed straps — was told about
only the top-plate switch's trunks, and skipped same-net pairs. The companion
block's comparator packs one channel track differently (no resistor-terminal
drops), reached a `cmp_y` the deliverable block happens not to reach, and
`klt drc` reported **two real `metal1.space.1` violations**: a 170 nm gap
between the comparator's own `vdd`/`vss` strap and a decode bank's. Same-net,
so electrically harmless — and invisible to every check this generator ran,
because `assert_no_bar_shorts` looks for *touches*, not for spacing. The
search now includes the decode banks' `vdd`/`vss` trunks and checks same-net
pairs too. All three blocks are DRC-clean.

## Reproduce

```
python3 layout/drc/run_drc.py --check
python3 layout/lvs/run_lvs.py --check
python3 layout/adc-top/parasitics/run_extract_parasitics.py --check
python3 layout/adc-top/parasitics/remediate_extracted.py --top ADC_BLOCK_NORES --check

python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK_NORES \
    --json reports/20260806-adc-block-comparator-input-open/verify_nores_tt.json
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK_NORES \
    --corner ss --temp 125 --vdd 2.97 \
    --json reports/20260806-adc-block-comparator-input-open/verify_nores_ss125c2.97v.json
# controls, same commit:
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK \
    --json reports/20260806-adc-block-comparator-input-open/verify_adc_block_control_tt.json
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_TOP \
    --json reports/20260806-adc-block-comparator-input-open/verify_adc_top_control_tt.json
```

## Results

| top | corner | transition 2 | transition 512 | transition 1022 | verdict |
|---|---|---|---|---|---|
| `ADC_BLOCK_NORES` | `tt_27c_3.30v` | 4.0 | 513.0 | 1022.0 | **PASS** |
| `ADC_BLOCK_NORES` | `ss_125c_2.97v` | 4.0 | 513.0 | 1022.0 | **PASS** |
| `ADC_BLOCK` (control, defect 1 fixed, resistor short still present) | `tt_27c_3.30v` | 1023.0 | 1023.0 | 1023.0 | **FAIL**, unchanged |
| `ADC_TOP` (control, comparator schematic-level) | `tt_27c_3.30v` | 3.0 | 511.0 | 1020.0 | **PASS** |

Tolerance is `gtop.CODE_TOL_LSB` = ±45 LSB, inherited from
`design/adc-top/gen_adc_top.py`'s own INL/DNL liveness check — this is a
"the whole chain ran and tracked the input" claim, **not** a linearity claim.

Both corners are the ones
`records/20260806-adc-block-comparator-smoke.md` reproduced the failure at,
re-used rather than re-chosen. The `ADC_BLOCK` control row is the load-bearing
one: it is the **same commit, with defect 1 already fixed**, and it still
fails identically — so it establishes that defect 2 is real and independent,
rather than leaving "we changed two things and it started working".

## What is *not* post-layout in the passing result

Exactly two elements: the comparator's two 150 kΩ preamp load resistors.
Their bodies are drawn and their geometry is `klt drc`-checked, but no
extraction this toolchain can run turns them into a device, so their value
comes from `design/comparator/comparator.spice`. **Everything else** —
all 27 comparator transistors, all 296 array/switch transistors, the 1024
unit MiM capacitors, and the block's extracted parasitic RC — is post-layout.
The remediated netlist's own header states this in the file, not only here.

Two further, pre-existing limitations still apply to the extracted RC itself
and are **not** addressed by this record:

- the pinned `klt` writes each net's parasitic resistance as a dead-end
  capacitive stub, never in any device's current path
  (`records/20260806-parasitic-topology.md`; upstream
  `2AMLogic/klayout-tools#592`, fixed by merged `#593` which this repo's pin
  does not yet reach — issue #116 Scope item 3);
- MiM capacitance is the deck's area-only model, 14.6 % below the PDK model
  card's area+fringe value for the same plate
  (`layout/adc-top/README.md`).

## Disposition

**Issue #116 Scope item 1 / AC1: closed.** A comparator-inclusive extracted
core decodes correctly at both corners, the root cause is documented rather
than worked around silently, and the `ADC_TOP` control is unregressed.

**Scope items 2–5 remain open**: the worst-corner regeneration margin (#9)
against this core, the `layout/toolchain.json` pin bump past
`klayout-tools#593` and the `R_WORST_BIT_OHM`/`C_WORST_BIT_F` re-measure
(#8/#10), #12's rate closure, and `sim/extracted-delta-summary.md`
§3/§6.3/§6.4. `sim/extracted-delta-summary.md`'s rows for those stay reported
as **not measured**, per CLAUDE.md's no-relaxation rule — this record does not
backfill them.

**Follow-on now unblocked, and deliberately not taken here**:
`mc_extracted_core.py`'s `--top` is still `ADC_TOP`-only (the failing record
made that restriction deliberately). Extending it — and the other
`gen_extracted_*_tb.py` decks — to `ADC_BLOCK_NORES` is a separate increment
with its own evidence to produce.

## Artifacts in this record

- `reports/20260806-adc-block-comparator-input-open/verify_nores_tt.json`
- `reports/20260806-adc-block-comparator-input-open/verify_nores_ss125c2.97v.json`
- `reports/20260806-adc-block-comparator-input-open/verify_adc_block_control_tt.json`
- `reports/20260806-adc-block-comparator-input-open/verify_adc_top_control_tt.json`
- `reports/20260806-194351-a0dbcf6/` + `records/20260806-194351-a0dbcf6.md`
  — the extraction this record's decks were built from
- `layout/drc/records/20260806-194341-a0dbcf6.md` — all 12 cells DRC-clean
- `layout/lvs/records/20260806-194351-a0dbcf6.md` — all 12 LVS cases,
  0 mismatches everywhere (the two `warning` rows this repo had pinned for a
  year of records are gone, not silenced)

Append-only per `sim/README.md`'s evidence rule: this record never overwrites
`records/20260806-adc-block-comparator-smoke.md` (the failing repro it
resolves), `records/20260806-parasitic-topology.md`, or
`records/20260805-remediation-dc.md`.
