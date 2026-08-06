# Record 20260806-adc-block-comparator-smoke

- **Record ID**: 20260806-adc-block-comparator-smoke
- **Claim**: issue #89 Scope item 2's comparator-inclusive follow-up
  (`sim/extracted-delta-summary.md` §6.4, `layout/adc-top/parasitics/
  README.md`'s acceptance-criterion-4 row: "A comparator-inclusive run still
  needs `ADC_BLOCK`"). `gen_extracted_core_tb.py` now wires `ADC_BLOCK`
  (the extraction that bakes the comparator INSIDE the CDAC-array core,
  `.SUBCKT` pins `cmpclk`/`dout`/`doutb`/`ibias` wired directly onto the
  rung-1 SAR controller in place of a second, redundant schematic comparator
  instance) into a complete conversion chain, on the same pattern
  `records/20260805-extracted-core-smoke.md` used for `ADC_TOP`.
  `verify_extracted_core_conversion.py --top ADC_BLOCK` runs the SAME
  three-transition, one-corner smoke test that record already used for
  `ADC_TOP`. **Result: FAIL, reproducibly** -- this record does NOT close
  the comparator-inclusive Monte Carlo item; it sharpens what blocks it from
  "still needs building" to "built, and blocked on a specific, reproduced
  functional defect", so the next increment does not have to re-derive this.
- **Netlist provenance**: extracted, then remediated (PMOS bodies -> `vdd`,
  input rails promoted to `vinp`/`vinn`) -- `Netlist provenance: extracted`.
  Comparator baked into the extraction (`ADC_BLOCK`), controller stays
  schematic-level.
- **Source extraction**: `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_block.para.spice`
  (same extraction `records/20260805-remediation-dc.md` DC-verified 63/63 for
  `ADC_BLOCK`).
- **PDK binding**: gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
  resolved via `sim/harness/pdk.py`. ngspice-46.
- **Working tree**: clean at commit `9de4f1f` (the wiring-code commit this
  record's own repro commands were run against) before this record's own
  files were added -- `git status --porcelain` empty, per the citability
  lesson `sim/adc-enob-fft/records/20260806-081350-862d054.md` documents.

## Reproduce

```
python3 layout/adc-top/parasitics/gen_extracted_core_tb.py --top ADC_BLOCK
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK \
    --json reports/20260806-adc-block-comparator-smoke/verify_extracted_core_conversion_tt.json
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_BLOCK \
    --corner ss --temp 125 --vdd 2.97 \
    --json reports/20260806-adc-block-comparator-smoke/verify_extracted_core_conversion_ss125c2.97v.json
# control, same commit, unaffected:
python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --top ADC_TOP \
    --json reports/20260806-adc-block-comparator-smoke/verify_extracted_core_conversion_adc_top_control.json
```

## Results

| top | corner | transition (expected code) | decoded code | within tolerance |
|---|---|---|---|---|
| `ADC_BLOCK` | `tt_27c_3.30v` | 2 | 1023.0 | **no** |
| `ADC_BLOCK` | `tt_27c_3.30v` | 512 | 1023.0 | **no** |
| `ADC_BLOCK` | `tt_27c_3.30v` | 1022 | 1023.0 | yes (coincidentally near the top of range) |
| `ADC_BLOCK` | `ss_125c_2.97v` | 2 | 1023.0 | **no** |
| `ADC_BLOCK` | `ss_125c_2.97v` | 512 | 1023.0 | **no** |
| `ADC_BLOCK` | `ss_125c_2.97v` | 1022 | 1023.0 | yes (same reason) |
| `ADC_TOP` (control, same commit) | `tt_27c_3.30v` | 2 / 512 / 1022 | 3.0 / 511.0 / 1020.0 | yes, yes, yes |

**`RESULT: FAIL`** for `ADC_BLOCK` at both corners, **identically** --
every probed transition, at both a nominal and the worst-case PVT corner
this harness's axes reach, decodes to **1023** (all bits set), i.e. the
comparator makes the SAME "count up" decision on all ten bit-trials of
all three conversions (30 strobe edges total) regardless of what the array
actually presents to it. The `ADC_TOP` control, re-run at the same commit
with the unchanged wiring path, still decodes correctly -- confirming this
is specific to the new `ADC_BLOCK` code path, not a regression in the
shared controller/array/stimulus wiring.

## What was ruled out

- **Not a dout/doutb polarity swap.** `design/comparator/comparator.spice`
  states the convention directly ("`dout` = 1 means `v(vinp) > v(vinn)`"),
  matched by `_wire_pin`'s `dout -> {tag}_cmp` mapping. Swapping the mapping
  (`dout -> {tag}_cmpb`, `doutb -> {tag}_cmp`) as a diagnostic experiment
  (not committed) does not fix the decode -- it flips the stuck code from
  **1023** to **0**, i.e. the decision is stuck at *some* fixed value
  regardless of which physical net feeds the controller's `cmp` port, not
  wrongly polarized.
- **Not the `ADC_TOP`-side wiring.** The array/controller/input-network
  wiring is identical code for both `--top` values (`_wire_pin`'s
  `hi`/`lo`/`rel`/`sel_in`/`tp_gn`/`vcm`/`vref`/`vdd` cases are unchanged);
  the `ADC_TOP` control at the same commit decodes correctly.
- **Not a `cmpclk` connectivity gap.** Grepping the raw extraction
  (`adc_block.para.spice`) for `cmpclk` shows it lands on exactly the device
  sizes `design/comparator/comparator.spice`'s `sarlatch` reset network
  uses (one 16 u/0.35 u NMOS tail switch, four 2-4 u/0.35 u PMOS resets) --
  the strobe reaches the expected devices structurally.

## What was NOT resolved -- root cause still open

Every attempted transient's own initial bias-point solve reports (raw
ngspice log, `reports/20260806-adc-block-comparator-smoke/
ngspice_tt_singular_matrix_excerpt.txt`):

```
Warning: singular matrix:  check node xdut.\$168
Note: Starting dynamic gmin stepping
Warning: singular matrix:  check node xdut.\$168
Warning: Dynamic gmin stepping failed
Note: Starting true gmin stepping
Warning: singular matrix:  check node xdut.\$168   (x4)
Warning: True gmin stepping failed
Note: Starting source stepping
Warning: source stepping failed
Note: Transient op started
Note: Transient op finished successfully
```

`xdut.$168` is an anonymous, klayout-assigned internal net inside the
`ADC_BLOCK` extraction -- **not** the same class of warning
`records/20260805-remediation-dc.md` already found and disposed of as
benign (that record's "trailing pass" note is about a *separate*,
unrelated implicit `.tran` bias pass ngspice's batch driver runs after an
`.op`-only deck's own measurement has already printed; that fallback DOES
resolve there). Here, EVERY fallback the solver tries (dynamic gmin, true
gmin, source stepping) fails outright before ngspice's `Transient op`
pass finally "succeeds" -- printing a result, but not necessarily a
*correct* one; the decode-stuck-at-a-constant behavior above is consistent
with the solver landing on a self-consistent but wrong equilibrium for
whatever `$168` participates in, most likely inside the comparator's own
cross-coupled StrongARM latch or SR output latch (`sarlatch`/`nor2` in
`design/comparator/comparator.spice`), which by design has two stable DC
states and no reset default -- but this was **not traced to a specific
device or net identity** (`$168` carries no name provenance back to the
schematic's own node names; the extraction assigns these arbitrarily, and
cross-referencing device geometry against the schematic's device list did
not produce an unambiguous match within this record's scope). Whether the
defect is (a) a genuine layout/extraction connectivity gap specific to the
`ADC_BLOCK` boundary that `ADC_TOP`'s DC-only remediation check
(`records/20260805-remediation-dc.md`) did not exercise because it never
runs a real clocked transient, (b) a missing initial-condition/reset
requirement this harness's wiring does not supply, or (c) something else,
is **left open** rather than guessed at.

## Disposition

**Scope item 2's comparator-inclusive Monte Carlo (`sim/extracted-
delta-summary.md` §6.4, §5's "still open" note) remains open** -- this
record does not close it. What changes: the blocker is now a specific,
reproduced functional failure (stuck-decision, singular internal node,
confirmed at two PVT corners, confirmed independent of dout/doutb
polarity) rather than "the wiring does not exist yet". Running
`mc_extracted_core.py --top ADC_BLOCK` against this wiring without first
fixing this would be exactly the "silent false pass" failure class that
script's own null control exists to catch, except upstream of what a
null control alone would detect: a frozen, wrong DECISION is not a frozen
MISMATCH DRAW, so `mc_extracted_core.py`'s existing on/off sigma-ratio
check would not by itself catch it (a population of identical wrong
decisions still "varies" once mismatch perturbs the exact instant the
stuck node tips, which is a different failure signature than this record's
20260805 sibling's frozen-draw class). `mc_extracted_core.py`'s `--top` is
therefore deliberately left `ADC_TOP`-only (not extended to `ADC_BLOCK`) by
this same commit, so a future run cannot point it at `ADC_BLOCK` without
first re-reading this record.

**What this record DOES establish**: the `ADC_BLOCK` wiring infrastructure
(`gen_extracted_core_tb.py --top ADC_BLOCK`,
`verify_extracted_core_conversion.py --top ADC_BLOCK`) exists, is
structurally sound by every check short of an actual clocked decision
(pin mapping matches the `.SUBCKT` header exactly, `cmpclk` reaches the
expected reset devices, the `ADC_TOP` control path is unaffected), and the
one thing it does NOT yet do -- decide correctly -- is caught by a real
testbench before it could contaminate a Monte Carlo population's numbers,
per CLAUDE.md's "no claim without a testbench".

## Artifacts in this record

- `reports/20260806-adc-block-comparator-smoke/verify_extracted_core_conversion_tt.json`
- `reports/20260806-adc-block-comparator-smoke/verify_extracted_core_conversion_ss125c2.97v.json`
- `reports/20260806-adc-block-comparator-smoke/verify_extracted_core_conversion_adc_top_control.json`
- `reports/20260806-adc-block-comparator-smoke/ngspice_tt_singular_matrix_excerpt.txt`

Append-only per `sim/README.md`'s evidence rule: this record never
overwrites `records/20260805-extracted-core-smoke.md`,
`records/20260805-remediation-dc.md`, or `records/20260805-extracted-core-mc.md`.
