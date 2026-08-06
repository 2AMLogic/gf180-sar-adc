# Record 20260806-adc-block-comparator-input-float

- **Record ID**: 20260806-adc-block-comparator-input-float
- **Claim**: the root cause left open by
  [`records/20260806-adc-block-comparator-smoke.md`](20260806-adc-block-comparator-smoke.md)
  — `verify_extracted_core_conversion.py --top ADC_BLOCK` decoding every
  probed transition to one stuck code at two PVT corners — is **identified**.
  There are **two** independent causes, not one. The first is a defect in this
  repository and is **fixed** by this record's own commit; the second is an
  extraction-deck capability gap, is **not** fixable here, and is filed
  upstream. This record does NOT claim `ADC_BLOCK` now converts: it still does
  not, for the second reason, and `sim/extracted-delta-summary.md` §6.4 stays
  reported as **not measured** rather than backfilled.
- **Netlist provenance**: mixed, stated per finding —
  - Finding 1's structural evidence: `extracted` (`klt extract` of
    `layout/adc-top/adc_block.gds`, plus `klt lvs`'s own
    `net_correspondence` for `layout/adc-top/comparator.gds`).
  - Finding 2's testbench: `schematic` —
    `design/comparator/comparator.spice`, read verbatim by
    `probe_comparator_load_short.py`; no layout is involved, on purpose (see
    §3).
- **Toolchain**: `klt 0.2.0` @ `875eac33dfbc004d2ab4dfcebc522734d159dc5f`
  (`layout/toolchain.json`, bumped by this same change), klayout 0.30.10,
  ngspice-46, gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
- **Supersedes**: nothing. Append-only per `sim/README.md`:
  `records/20260806-adc-block-comparator-smoke.md` stands exactly as written —
  its FAIL is real and its "root cause still open" section is what this record
  closes.

---

## 1. Finding 1 — the comparator's differential inputs were FLOATING (fixed here)

### What was wrong

`design/comparator/comparator.spice` brings its inputs in through two
zero-volt probe sources, so a testbench can measure the current the comparator
draws from each CDAC top plate:

```
Vpp preamp_in1 vinp dc 0
Vpn preamp_in2 vinn dc 0
Xpre preamp_in1 preamp_in2 ibias pop pon vdd vss preamp
```

`layout/adc-top/lib/netlist.py`'s `flatten()` correctly refuses to draw a
voltage source and hands each one back as a **net alias**, to be merged by
`resolve_aliases()`. That function picks the surviving name from a `prefer`
set — its own docstring says why this matters: *"naming the comparator's
merged supply node after an internal net instead of `vdd` turned a clean block
compare into 449 mismatches during this bring-up."*

`gen_comparator.build_into()` called it **without** `prefer`:

```python
devices = nl.resolve_aliases(devices, aliases)      # no prefer=
```

so the tie-break fell through to "lexicographically smallest name wins" — and
`preamp_in1` < `vinp`, `XCMP.preamp_in1` < `topp`. The merged net therefore
took the **internal** name. The cell then labelled and routed a `vinp` (in
`ADC_BLOCK`, `topp`) trunk that **no device sat on**, and the preamp's
differential pair gates were left on a net with exactly one terminal.

### Why LVS did not catch it

`build_into()` returns one device list, `info["devices"]`, and that same list
is used to *draw the cell* and to *generate the LVS reference*. Both sides
therefore agreed the comparator's inputs were disconnected. What `klt lvs`
**did** say was baselined away in `layout/lvs/cells/cells.json` as
`expect_mismatch_count: 2 / {"topology": 2}`. Reading the report it wrote
(`layout/lvs/reports/20260805-122516-e8017f2/comparator.lvs.json`, committed,
pre-fix):

```json
"counts": { "pins": { "layout": 7, "reference": 9, "matched": 9 } },
"mismatches": [
  { "category": "topology", "severity": "warning",
    "description": "nets were paired ambiguously; ...",
    "net": { "layout": "$10", "reference": "PREAMP_IN1" } },
  { "category": "topology", "severity": "warning",
    "net": { "layout": "$9",  "reference": "PREAMP_IN2" } }
],
"net_correspondence": [
  ...
  { "layout": null, "reference": "VINN", "pin": false },
  { "layout": null, "reference": "VINP", "pin": false },
  ...
]
```

`pins.layout = 7` against `pins.reference = 9`, and `VINP`/`VINN` each
carrying a **null** layout counterpart, is the defect stated in the tool's own
output. It was pinned as an expectation rather than read.

### The fix, and the evidence it worked

One line, plus moving the `labelled` list above the call:

```python
devices = nl.resolve_aliases(devices, aliases, prefer=set(labelled))
```

| check | before | after |
|---|---|---|
| `klt lvs comparator` mismatches | 2 (`topology`) | **0** |
| `klt lvs adc_block` mismatches | 2 (`topology`) | **0** |
| `comparator` extract `pin_count` | 7 | **9** |
| `comparator_nores` extract `pin_count` | 7 | **9** |
| `adc_block` extract `net_count` | 198 | **196** (two floating nets merged away) |
| `adc_block` extracted preamp input pair gates | `\$167` / `\$168`, degree 1 | **`topp__t1` / `topn__t0`** |
| `klt drc` on all three regenerated cells | clean | clean |

Every one of `layout/{drc,lvs}/cells/cells.json`'s changed expectations moves
in the *stricter* direction — the two accepted `topology` findings are gone
and two dangling pins became real ones. Re-baselined records:
`layout/drc/records/20260806-193859-68ad582.md`,
`layout/lvs/records/20260806-193909-68ad582.md`.

### What the fix did NOT do

`verify_extracted_core_conversion.py --top ADC_BLOCK` at `tt_27c_3.30v` after
the fix:

```
  transition    2 -> decoded 0.0 : OK
  transition  512 -> decoded 0.0 : FAIL
  transition 1022 -> decoded 0.0 : FAIL
RESULT            : FAIL
```

The stuck code moved from **1023** to **0**. Necessary, not sufficient. The
`ADC_TOP` control at the same commit and the same toolchain still decodes
correctly (`3.0 / 511.0 / 1020.0`, `RESULT: PASS`,
`reports/20260806-adc-block-comparator-input-float/verify_adc_top_control_tt.json`),
so this is still specific to the comparator-inclusive path.

---

## 2. Finding 2 — the preamp's load resistors extract as a short (NOT fixable here)

### What is wrong

The preamp's gain comes from two 150 kΩ unsalicided p+ poly loads:

```
Xrlp vdd pop vss ppolyf_u_2k r_width=1u r_length=75u
Xrln vdd pon vss ppolyf_u_2k r_width=1u r_length=75u
```

The pinned gf180mcu extraction deck models `ppolyf_u` (350 Ω/sq) and
`ppolyf_u_1k` (1000 Ω/sq). It does **not** model `ppolyf_u_2k`. All three
high-sheet-rho flavours share identical recognition geometry and upstream's
own deck distinguishes them with a deck variable (`POLY_RES`) that `klt` has
no equivalent for, so only the default is wired. A drawn `_2k` body is
therefore absorbed into ordinary interconnect — **a zero-ohm short between its
own terminals**.

This is not new information in this repository — `gen_comparator.py`'s module
docstring is built around it, and `layout/adc-top/adc_block.ref.spice`'s own
header states it:

> the comparator's two 150 kohm p+ poly load resistors are drawn but are not
> extractable devices, so each shorts its own terminals and `pop`/`pon`
> collapse onto `vdd`.

What is new is that this is the **remaining cause of the stuck decision**, not
just an LVS-visibility inconvenience. In the extracted `ADC_BLOCK` the preamp
input pair's drains and the StrongARM latch's input gates all land on `vdd`
legs:

```
X$141 vdd__t1  topp__t1 \$166__t0 vsubs nfet_03v3 L=1U W=40U   <- Xmip, drain = pon
X$144 vdd__t10 topn__t0 \$166__t1 vsubs nfet_03v3 L=1U W=40U   <- Xmin, drain = pop
X$150 \$169__t0 vdd__t2 \$168__t1 vsubs nfet_03v3 L=0.5U W=8U  <- Xmlp, gate  = inp
X$151 \$170__t2 vdd__t9 \$168__t2 vsubs nfet_03v3 L=0.5U W=8U  <- Xmln, gate  = inn
```

`pop`, `pon` and `vdd` are one net.

### The testbench (§3) — stated as a claim that can fail

`probe_comparator_load_short.py` runs the **schematic** comparator, read
verbatim from `design/comparator/comparator.spice`, in two arms at one corner:
as drawn, and with exactly its two `Xrlp`/`Xrln` cards replaced by 0 V
sources — which is precisely what an extraction that sees the poly body as
interconnect produces. Four strobes, alternating input polarity, ±100 mV
overdrive (far above the block's measured offset).

The verdict is taken on the **preamp differential output**, not on `dout` —
see §3 for why that distinction is load-bearing.

| corner | arm | v(pop)−v(pon) per strobe (+/−/+/−) | dout |
|---|---|---|---|
| `tt_27c_3.30v` | as-drawn | +0.106100 / −0.102610 / +0.106100 / −1.243160 | 1 / 0 / 1 / 0 |
| `tt_27c_3.30v` | loads-shorted | **+0.000000 / +0.000000 / +0.000000 / +0.000000** | 0 / 0 / 0 / 0 |
| `ss_125c_2.97v` | as-drawn | +0.165710 / −0.162560 / +0.165700 / −1.122460 | 1 / 0 / 1 / 0 |
| `ss_125c_2.97v` | loads-shorted | **+0.000000 / +0.000000 / +0.000000 / +0.000000** | 1 / 0 / 1 / 0 |

`RESULT: CONFIRMED` at both corners. With the loads shorted the comparator has
**no signal path from its inputs to its latch at all** — the differential the
latch is supposed to decide on is identically zero, at a nominal corner and at
the worst-case corner this harness's axes reach.

### Filed upstream, per CLAUDE.md's friction protocol

`2AMLogic/klayout-tools#595` — "no way to select WHICH shared-geometry
sheet-rho flavour a resistor family extracts as, so the other flavours still
collapse to a short". Written generically (PDK layer numbers, the upstream
deck's own `POLY_RES` variable, a generic differential-pair-with-resistive-loads
consequence); it names no part of this design. It is the direct child of the
already-closed `#299`, which fixed the base-vs-high-rho half of the same
problem.

---

## 3. A methodology finding worth keeping: `dout` is not evidence here

The first revision of `probe_comparator_load_short.py` put both arms in **one**
ngspice deck, to guarantee bit-identical stimulus. It reported the
loads-shorted arm tracking the input perfectly, 4/4 — i.e. "the short is
harmless". That was **wrong**, and wrong in a way worth recording because the
same trap sits under the original stuck-code record's own hypothesis:

Once the preamp differential is exactly zero, the StrongARM latch is
topologically symmetric with both gates at `vdd`. It is **metastable**. What
resolves it is whatever asymmetry the numerical solve happens to carry — and
in a shared deck the solver's matrix couples the two arms, so the metastable
arm's output tracked the *healthy* arm's input. Splitting the two arms into
separate ngspice processes removes the coupling and the shorted arm's `dout`
stops being correlated with anything.

The corner-to-corner behaviour in the table above makes the same point without
any solver argument: the identical shorted circuit **freezes** at
`tt_27c_3.30v` and **appears to track the input** at `ss_125c_2.97v`, with the
preamp differential at exactly zero in both. A latch output that is metastable
is not a decision, and reading it as one is how "it works at this corner" gets
recorded about a circuit that has no input path.

This is why the probe's verdict keys off `v(pop) − v(pon)`, which is
deterministic, and why `dout` is reported as a symptom only.

---

## 4. What this means for `ADC_BLOCK`, stated without overreach

- The comparator-inclusive extracted core **does not yet convert**, and this
  record does not claim it does.
- `sim/extracted-delta-summary.md` §6.4 (comparator-inclusive Monte Carlo) and
  the worst-corner regeneration-margin re-take against the extracted core
  (issue #9's methodology, issue #17's AC7) therefore stay **not measured**,
  per CLAUDE.md's no-relaxation rule — not backfilled with the schematic-level
  number relabelled as extracted.
- The blocker has moved, and the move is the point: from *"root cause not
  identified; a singular internal node `xdut.$168` and a stuck decision"* to
  *"two named causes, one fixed here with LVS/DRC evidence, one an extraction
  deck capability gap filed upstream as `klayout-tools#595` with a testbench
  that says exactly what it costs"*. `xdut.$168` itself is now explained: it
  was one of the two floating preamp input gates (finding 1), which is why the
  bias-point solve reported it singular through every fallback.
- **What would unblock it**: `klayout-tools#595` landing a flavour-selection
  knob (then `ppolyf_u_2k` extracts as a real 150 kΩ device and no remediation
  is needed at all), or — if upstream prefers not to — a documented
  post-extraction remediation in `remediate_extracted.py` that re-inserts the
  two load resistors. The second is NOT attempted here: the extraction has
  already merged `pop`, `pon` and `vdd` into one net, so which device terminals
  belong to which of the three is not recoverable from the netlist, and a
  remediation that guessed would be exactly the "plausibly-wrong core" that
  module's own header refuses to emit.

## Reproduce

```
# Finding 1: the fix, and its DRC/LVS evidence
python3 layout/adc-top/gen_comparator.py
python3 layout/adc-top/gen_adc_top.py
python3 layout/drc/run_drc.py --check
python3 layout/lvs/run_lvs.py --check
python3 layout/adc-top/parasitics/run_extract_parasitics.py --check

# Finding 1: what it did and did not fix, functionally
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_TOP   # control

# Finding 2: the root-cause testbench, both corners
python3 layout/adc-top/parasitics/probe_comparator_load_short.py
python3 layout/adc-top/parasitics/probe_comparator_load_short.py \
    --corner ss --temp 125 --vdd 2.97
```

## Artifacts in this record

- `reports/20260806-adc-block-comparator-input-float/probe_comparator_load_short_tt.json`
- `reports/20260806-adc-block-comparator-input-float/probe_comparator_load_short_ss125c2.97v.json`
- `reports/20260806-adc-block-comparator-input-float/verify_adc_top_control_tt.json`
- `layout/lvs/records/20260806-193909-68ad582.md` (LVS, post-fix, 0 mismatches)
- `layout/drc/records/20260806-193859-68ad582.md` (DRC, post-fix, clean)
- `layout/adc-top/parasitics/records/20260806-193910-68ad582.md` (extraction)
