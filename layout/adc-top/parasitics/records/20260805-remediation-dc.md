# Record 20260805-remediation-dc

- **Record ID**: 20260805-remediation-dc
- **Claim**: issue #89 pre-work (Scope item 0 + guidance items 1-3). The
  `--pdk gf180mcuD` extraction of `adc_top` (record `20260805-102856-1118e9a`)
  is made into a **well-posed, simulatable extracted core** by a documented,
  deterministic remediation, and that core is verified to converge in a DC
  operating point across the full #13 `cdac` PVT grid with every PMOS body
  hard-tied to `vdd` and the sampled-input rails reachable. This record makes
  **no ADC spec-line performance claim** -- the #13 PVT bench, #14 Monte Carlo,
  and the schematic-vs-extracted delta summary (Scope items 1-5) remain
  deferred (see "What remains" below).
- **Netlist provenance**: extracted, then **remediated** -- PMOS-body->`vdd`
  local remediation of the `klt` PMOS-body gap (upstream
  [`klayout-tools#555`](https://github.com/2AMLogic/klayout-tools/issues/555),
  still OPEN as of 2026-08-05); internal per-side input rails `$8`/`$91`
  promoted to `.SUBCKT` pins `vinp`/`vinn`. **NOT raw `klt extract` output.**
- **Source extraction**: `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`
  (repo sha `1118e9a`, `klt 0.2.0`, pin `af5791b`, PDK `--pdk gf180mcuD`).
- **PDK binding (this DC verification)**: gf180mcuD, open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, resolved via `sim/harness/pdk.py`
  (`search_root:~/.volare`), MiM stack `m4m5`. ngspice-46.

## The three judgment calls this issue required, made with provenance

The issue named three judgment calls that "must be made and documented ... not
silently absorbed." Here they are, each with the path taken and why.

### 1. PMOS-body gap -> **local remediation** (not waiting on upstream #555)

Every PMOS device's body (Nwell) terminal in the extraction lands on an
anonymous, un-pinned net (`X$149 ... vdd $157 pfet_03v3`), because gf180mcu's
curated `klt extract` deck has no tap/well-label layer -- not the `vdd` tie the
schematic assumes (single-well convention, stated in
`sim/device-switch-ron/testbench/`). Two paths were available (guidance item 1):
wait on upstream `klayout-tools#555`, or apply a documented local remediation.

**Path taken: local remediation.** `klayout-tools#555` was re-checked and is
still `OPEN` (2026-08-05), so waiting would block all of Scope items 1-5
indefinitely. `remediate_extracted.py` rewrites every anonymous PMOS-body net to
`vdd`. It is the same fix `layout/adc-top/lib/netlist.py`'s `body_net_of`
mapping applies for LVS (each PMOS body -> its Nwell island; a single-well
layout means every island is the `vdd` net), restated as a simulation netlist
rewrite. **Safety:** the rewrite is applied only after asserting each such net
appears *exclusively* as a PMOS body terminal -- never as a signal terminal, a
pin, or a parasitic RC node -- so it cannot corrupt a real connection. All 20
anonymous body nets (148 PMOS devices) passed that assertion; had any failed,
the script raises rather than emit a plausibly-wrong core. The output netlist is
explicitly headered as a remediation, not raw `klt` output.

### 2. MiM-cap mapping -> **map to the PDK MiM subckt** (the extraction's native form)

The MiM cards needed a methodology choice (guidance item 2): map each onto the
PDK MiM subckt, or onto a validated ideal capacitor at the extracted value.

**Path taken: PDK MiM subckt -- and it needs no rewrite.** The `--pdk gf180mcuD`
extraction already writes each unit cap as
`X$297 $10 topp cap_mim_2f0_m4m5_noshield c_length=2.714U c_width=2.714U`, a
subckt call that binds directly to `sm141064_mim.ngspice`'s
`cap_mim_2f0_m4m5_noshield` (verified defined at line 252; parameters `gleak`,
`c_cox`, `c_c0`, ... are internal to the subckt). This is the *same* subckt
`sim/harness/pdk.py`'s `mim_subckt('2f0')` resolves and the same physical model
`design/adc-top/adc_top.spice`'s `mim_cap_2f0` wrapper reaches -- so it is the
fair comparison against the schematic's subckt-instantiated MiM, and includes
the full area+fringe capacitance law (not the area-only value the `--deck`-only
LVS reference uses, see `netlist.py`'s `DECK_MIM_AREA_CAP_F_UM2`). The
remediation asserts the binding is present (1024 cards) and leaves the cards
untouched.

### 3. Extracted-core testbench integration -> **dedicated remediation + input-rail pin promotion**

The extracted `ADC_TOP` is a single flat 63-pin subckt; `gen_adc_top.py` inlines
*two* `adc_cdac_side` instances and wires the comparator + SAR logic around them,
with no path to swap in the extracted core (guidance item 3). Building the swap
surfaced a **second structural gap the issue's three items did not enumerate**:
the extracted `ADC_TOP` has **no input pin**. DR-0014 samples the input on the
CDAC bottom plates through each cell's fourth-leg T-gate; the common per-side
input rail those nine T-gates share is an internal, un-pinned net (`$8` for the
topp side, `$91` for the topn side, degree 18 = 9 T-gates x nfet+pfet each). A
wrapper testbench cannot inject the sampled input through a net that is not a pin.

**Path taken:** `remediate_extracted.py` identifies the two rails *structurally*
(the non-supply, non-pin leg source shared by the bottom-plate T-gates -- not by
name) and promotes them to named pins `vinp`/`vinn`. This is the analog-core
adaptation Scope item 0 asks for, realized as a "swap only the analog core"
remediation rather than a `gen_adc_top.py` mode; the comparator, SAR logic and
stimulus stay schematic-level in the (deferred) full bench. The rail promotion
is documented in the netlist header as a local remediation, not raw `klt` output.

## DC verification (reproducible)

```
python3 layout/adc-top/parasitics/remediate_extracted.py --check
python3 layout/adc-top/parasitics/verify_remediation_dc.py --corners cdac \
    --json reports/20260805-remediation-dc/verify_remediation_dc.json
```

`verify_remediation_dc.py` composes a DC `op` for every point of the #13 `cdac`
corner set -- 7 process sections (`tt`, `cap_ff/ss`, `mim_ff/ss`, `moscap_ff/ss`)
x 3 temperatures (-40/27/125 C) x 3 supplies (2.97/3.30/3.63 V) = **63 points**,
using `sim/harness/corners.py`'s own sections and axes -- against the resolved
gf180mcu PDK.

## Results

| check | result |
|---|---|
| PMOS bodies retied to `vdd` | 148 (all pfet_03v3 devices) |
| body-tie invariant: every pfet body net == `vdd` | **holds** (net identity, corner-independent) |
| input rails promoted to pins | `$8`->`vinp`, `$91`->`vinn` |
| MiM caps as native PDK subckt | 1024 x `cap_mim_2f0_m4m5_noshield` |
| DC `op` convergence over the 63-point `cdac` PVT grid | **63/63 converge** |
| promoted input pins reachable in `op` | yes (`vinp`/`vinn` biased and resolved) |

**Contrast (the gap, measured not asserted):** the *raw* (unremediated)
extraction's 20 anonymous PMOS-body nodes settle in a DC `op` to **3.13-3.15 V**
with device sources near `vdd` -- bias-dependent and NOT the hard 3.3 V `vdd`
tie the physical single-well layout guarantees (the README's reproduced leaf-cell
test, with a driven-*low* source, saw the same kind of node float to ~0 V; both
show an un-tied, floating body, i.e. a full degree of freedom the schematic does
not have). The remediation removes that freedom by construction. Full per-node
values and per-point convergence are in
`reports/20260805-remediation-dc/verify_remediation_dc.json`.

## What remains (still deferred, tracked in #89)

This record closes the pre-work the parasitics README listed as required before
any bench can run against a *physical* extracted core. It does **not** close:

- **Scope item 1** -- the full #13 testbench suite (INL/DNL, ENOB/FFT, power)
  re-run over the PVT matrix against the extracted core. This is the material
  multi-hour transient campaign the README's "Compute note" describes (the
  static-linearity bench alone is 63 points x 18 transistor-level conversions on
  a ~1300-device RC netlist), and needs the comparator + SAR-logic + stimulus
  wrapper around the `vinp`/`vinn`-remediated core (a `gen_adc_top.py`
  "extracted-core" mode or a dedicated transient harness).
- **Scope item 2** -- the #14 Monte Carlo re-run (and whether the extraction
  flow supports statistical variation at all).
- **Scope items 3, 8** -- the schematic-vs-extracted delta summary, incl.
  `gain_err_lsb` per corner (which #53 needs to adjudicate its top-plate
  parasitic gain-error finding).
- **Scope item 6 baseline caveat** -- when the delta summary is built, the
  SFDR @ Nyquist row must diff against the schematic-level **FAIL** already
  recorded (61.33 dB vs >= 62 dB at `ss_125c_2.97v`, `spec/testbench-suite-memo.md`
  §11.2); a continued extracted FAIL there is expected baseline behavior, not a
  new layout regression.

## Artifacts in this record

- `reports/20260805-remediation-dc/verify_remediation_dc.json` -- full DC
  verification result (per-point convergence, raw floating-body voltages, PDK
  provenance).
- `reports/20260805-remediation-dc/adc_top.remediated.spice` -- the remediated
  extracted core (reproducible from `remediate_extracted.py`; committed for
  convenience, headered as a remediation not raw `klt` output).

Append-only per `sim/README.md`'s evidence rule: this record never overwrites
the extraction record `20260805-102856-1118e9a` it builds on.
