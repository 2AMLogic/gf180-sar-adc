# Post-layout parasitic extraction of the adc-top block

This directory is issue #17's **Scope item 1**: parasitic extraction of the
DRC/LVS-clean `layout/adc-top/` block (the DR-0014 four-leg bottom-plate
sampling topology) to a netlist, done reproducibly, with the extraction path
recorded so an outside reader can re-run it and reach the same numbers.

It is the parasitic-extraction half of the flow `layout/lvs/` stood up for LVS
(issue #51): the same `klt extract` verb, the same commit-pinned toolchain
(`../../toolchain.json`), the same append-only evidence discipline — with
`--parasitics` turned on, so the written netlist additionally carries the
first-order lumped RC the schematic-equivalent LVS extraction deliberately
omits.

## Reproduce

```
python3 layout/adc-top/parasitics/run_extract_parasitics.py            # run + mint a record
python3 layout/adc-top/parasitics/run_extract_parasitics.py --check    # run + assert, write nothing
```

The runner probes `klt`'s capabilities against the pin, runs

```
klt extract ../adc_top.gds   --deck gf180mcu --parasitics --top ADC_TOP   -o adc_top.para.spice   --format json
klt extract ../adc_block.gds --deck gf180mcu --parasitics --top ADC_BLOCK -o adc_block.para.spice --format json
```

live on every invocation, asserts each block's structured summary against
`cells.json` (device/net/pin counts, the per-class device tally, and that the
`parasitics` block populated with the expected R/C counts), verifies each
source GDS's sha256 belongs to the committed geometry, and writes an
append-only record under `records/` + `reports/`.

`klt extract --parasitics` landed upstream in `2AMLogic/klayout-tools#216`/
`#217` and is available because `../../toolchain.json` is pinned past it
(commit `af5791b`, `klt 0.2.0`; the earlier `e08f24f` pin this issue's body
flagged could not do parasitics). The friction issue for the original
capability gap, `2AMLogic/klayout-tools#54`, is confirmed to exist (now closed
upstream) — Scope item 1's precondition, met, no duplicate filing.

## What was extracted (record `20260805-032116-3169620`)

| block | top | devices | nets | pins | MiM caps | nfet | pfet | para R | para C | ΣR (Ω) | ΣC (fF) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `adc_top`   | ADC_TOP   | 1320 | 177 | 63 | 1024 | 148 | 148 | 156 | 156 | 115 320 | 3730 |
| `adc_block` | ADC_BLOCK | 1347 | 198 | 67 | 1024 | 163 | 160 | 172 | 172 | 129 704 | 4056 |

`adc_top` is the CDAC analog core (both sides, the four-leg bottom-plate switch
network + local drivers); `adc_block` additionally carries the comparator. The
1024 MiM caps are the CDAC unit-capacitor array. The device/net counts match
the post-#69 DR-0014 draw (296 FETs + 1024 caps for `adc_top`, 177 nets) — i.e.
this is the current topology, not the superseded DR-0011 224-device draw.

## The simulation-integration gap (why #17 is only partly closed here)

Scope items **2–5** — re-running the #13 testbench suite, the #14 Monte Carlo,
and building the schematic-vs-extracted delta summary against this netlist —
all require the extracted netlist to be **simulatable by the `sim/` harness**,
and it is not yet. This is a real, specific gap, stated explicitly here rather
than worked around, so a follow-up can execute it and this record is not
mistaken for a completed bench re-run.

The extractor emits **device-class primitive cards**, but the harness's gf180
models are **subckts** — the two do not connect without an adaptation layer:

| extracted card (`*.para.spice`) | harness expectation (`design/` + `sim/harness/pdk.py`) |
|---|---|
| `M$1 $65 sel_in vss vsubs nfet L=0.35U W=4U AS=4.4P …` | `X… vin gn vout 0 nfet_03v3 w=… l=…` — `nfet_03v3` is `.subckt d g s b`, **not** a `.model`, so a raw `M … nfet` card has no model to bind to |
| `M$149 $65 sel_in vdd $157 pfet L=0.35U W=8U …` | `pfet_03v3` subckt; the extracted p-device bulk is an extracted nwell net (`$157`), not `vdd` |
| `C$297 $166 $165 1.4731592e-14 cap_mim_2f0_m4m5_noshield` | schematic instantiates the MiM as a subckt with geometry: `Xc top bp mim_cap_2f0 c_width=… c_length=…` — the extracted card is a value + a class token, not that subckt |
| `R_10 $10 $10__par 1848.76` / `C… …__par vsubs …` | ideal R/C — these simulate directly, but hang off `vsubs`, which the harness has no top-level tie for |

Concretely, an adaptation layer (the follow-up's job) has to:

1. **Rewrite `M … nfet` / `M … pfet` → `X … nfet_03v3` / `pfet_03v3`**, mapping
   `L/W/AS/AD/PS/PD` onto the subckt's `w/l/as/ad/ps/pd` params, so the
   extracted devices use the **same** binned BSIM models the schematic uses
   (a plain `.model nfet nmos …` would parse but be the wrong physics —
   fabricated numbers, which CLAUDE.md forbids).
2. **Map `C … cap_mim_2f0_m4m5_noshield`** either onto the PDK MiM subckt or a
   validated ideal capacitor at the extracted value, and decide which is the
   fair comparison against the schematic's subckt-instantiated MiM (a
   methodology choice that must be stated in the delta summary, not made
   silently).
3. **Tie `vsubs`** (and the extracted nwell nets) to the harness's supplies,
   and present a wrapper whose port list the `sim/` testbench can instantiate
   in place of the schematic core.
4. **Bridge the structural mismatch**: the extracted netlist is a single flat
   `ADC_TOP`/`ADC_BLOCK` subckt with explicit `_p`/`_n` control pins, whereas
   `design/adc-top/gen_adc_top.py` inlines *two* `adc_cdac_side` instances and
   wires the comparator + SAR logic around them. `gen_adc_top.py` currently has
   no path to emit a testbench that instantiates the extracted core, so the
   generator needs an "extracted-core" mode (or a separate harness) that keeps
   the comparator/SAR-logic/stimulus schematic-level while swapping only the
   analog core.

None of this is produced here, because doing it half-correctly would yield
plausible-but-wrong spec numbers, which is worse than none. This directory
produces and substantiates the netlist that work consumes.

### Compute note

Even with the adaptation layer, the bench re-run is a large campaign: the
#13 static-linearity bench alone is the `cdac` corner set (7 process × 3 temp ×
3 supply = 63 points) × 18 full transistor-level conversions per point, now on
a ~1300-device RC-laden netlist rather than the schematic core. That is a
material multi-hour simulation job per spec-line bench, and is called out so
the follow-up is scoped with it in mind, not surprised by it.

### Delta-summary baseline caveat (for the follow-up)

When the delta summary is built, the **SFDR @ Nyquist** row must diff against a
**schematic-level FAIL**, not a pass: `spec/testbench-suite-memo.md` §11.2
records SFDR at 61.33 dB vs. the ≥ 62 dB spec (a 0.67 dB miss) at one corner of
nine (`ss_125c_2.97v`) on the DR-0014 topology. A continued extracted-netlist
SFDR fail is *expected pre-existing baseline behavior* (schematic FAIL →
extracted FAIL), not a new layout-induced regression, and should be reported as
such — read §11.2 before writing that row.

## Acceptance-criteria status for #17

| # | criterion | status here |
|---|---|---|
| 1 | friction issue `klt-tools#54` confirmed to exist | **met** — exists (closed upstream), not re-filed |
| 2 | extracted netlist produced, extraction path documented | **met** — this directory: runner, record, netlists, pinned tool/command/version |
| 3 | every #13 bench re-run over full PVT with `Netlist provenance: extracted` | **deferred** — blocked on the adaptation layer above |
| 4 | #14 Monte Carlo re-run if models support it, else stated | **deferred / stated** — cannot run until the netlist is simulatable; whether the extraction flow supports statistical variation is itself a follow-up question |
| 5 | schematic-vs-extracted delta summary (incl. `gain_err_lsb`) | **deferred** — needs items 3–4 |
| 6 | no spec relaxation | **held** — no spec touched; SFDR baseline caveat recorded, not patched |
| 7 | worst-corner edge cases re-checked post-extraction | **deferred** — part of the bench re-run |
| 8 | extracted `gain_err_lsb` per corner alongside schematic + delta | **deferred** — needs item 3 |

Items 3–5, 7, 8 are a coherent, separable follow-up: build the extracted-core
simulation adaptation and run the #13/#14 suite against this netlist. This
increment is the netlist and the specification of what that follow-up must do.
