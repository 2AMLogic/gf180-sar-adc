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

The runner probes `klt`'s capabilities against the pin, resolves a gf180mcu PDK
install via `klt pdk find` (the same resolver `sim/harness/pdk.py` uses for its
own `PDK_ROOT`/`PDK`), and runs

```
klt extract ../adc_top.gds   --deck gf180mcu --parasitics --top ADC_TOP   --pdk gf180mcuD --pdk-root <resolved> -o adc_top.para.spice   --format json
klt extract ../adc_block.gds --deck gf180mcu --parasitics --top ADC_BLOCK --pdk gf180mcuD --pdk-root <resolved> -o adc_block.para.spice --format json
```

live on every invocation, asserts each block's structured summary against
`cells.json` (device/net/pin counts, the per-class device tally, and that the
`parasitics` block populated with the expected R/C counts), verifies each
source GDS's sha256 belongs to the committed geometry, and writes an
append-only record under `records/` + `reports/`. When no PDK resolves
(`PDK_ROOT` unset), extraction still runs and is still asserted — just without
the `--pdk`/`--pdk-root` flags, so devices come back as bare `M ... nfet`
class cards instead of `X ... nfet_03v3` subcircuit calls (the record says
which happened).

`klt extract --parasitics` landed upstream in `2AMLogic/klayout-tools#216`/
`#217` and is available because `../../toolchain.json` is pinned past it
(commit `af5791b`, `klt 0.2.0`; the earlier `e08f24f` pin this issue's body
flagged could not do parasitics). The friction issue for the original
capability gap, `2AMLogic/klayout-tools#54`, is confirmed to exist (now closed
upstream) — Scope item 1's precondition, met, no duplicate filing.

## What was extracted

| block | top | devices | nets | pins | MiM caps | nfet | pfet | para R | para C | ΣR (Ω) | ΣC (fF) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `adc_top`   | ADC_TOP   | 1320 | 177 | 63 | 1024 | 148 | 148 | 156 | 156 | 115 320 | 3730 |
| `adc_block` | ADC_BLOCK | 1347 | 198 | 67 | 1024 | 163 | 160 | 172 | 172 | 129 704 | 4056 |

`adc_top` is the CDAC analog core (both sides, the four-leg bottom-plate switch
network + local drivers); `adc_block` additionally carries the comparator. The
1024 MiM caps are the CDAC unit-capacitor array. The device/net counts match
the post-#69 DR-0014 draw (296 FETs + 1024 caps for `adc_top`, 177 nets) — i.e.
this is the current topology, not the superseded DR-0011 224-device draw.
These counts are identical with or without `--pdk` (it only changes how a
device is *serialized* in the written SPICE, not what `klt` recognises or
counts — see `klt`'s own `docs/cli/extract.md` → "SPICE model binding").

Two records exist, append-only, for two different extraction invocations —
neither supersedes the other:

- [`records/20260805-032116-3169620.md`](records/20260805-032116-3169620.md)
  — the first cut, `--deck gf180mcu --parasitics` only (no `--pdk`): devices
  come back as bare `M ... nfet`/`M ... pfet` class cards.
- [`records/20260805-102856-1118e9a.md`](records/20260805-102856-1118e9a.md)
  — adds `--pdk gf180mcuD --pdk-root <resolved>`: devices come back as
  `X ... nfet_03v3`/`pfet_03v3` subcircuit calls, the same syntax
  `design/adc-top/adc_top.spice`'s own `.subckt`s use. This is the netlist to
  use for any future resimulation attempt (subject to the open gap below).

## Extracted-netlist resimulation: what closes, and what doesn't (issue #17 / #89)

Scope items **2–5** — re-running the #13 testbench suite, the #14 Monte Carlo,
and building the schematic-vs-extracted delta summary against this netlist —
all require the extracted netlist to be **simulatable by the `sim/` harness**.
This revision closes one real half of that gap and found a second, deeper one
that it does **not** close — both stated explicitly here rather than worked
around, so a follow-up (#89) can execute against an accurate map of what
remains, and this record is not mistaken for a completed bench re-run.

**Closed by `--pdk gf180mcuD` (this revision):** the model-binding half. A
`--deck`-only extraction writes bare device-class primitive cards that cannot
bind to `sm141064.ngspice` at all —

| bare extraction (no `--pdk`) | with `--pdk gf180mcuD --pdk-root <resolved>` |
|---|---|
| `M$1 \$65 sel_in vss vsubs nfet L=0.35U W=4U AS=4.4P …` — `nfet` is a deck class label, not a model `sm141064.ngspice` defines | `X$1 \$65 sel_in vss vsubs nfet_03v3 L=0.35U W=4U` — the real PDK subcircuit, same syntax `design/adc-top/adc_top.spice`'s own `.subckt`s use |
| `C$297 \$166 \$165 1.4731592e-14 cap_mim_2f0_m4m5_noshield` | unchanged by `--pdk` (gf180mcu's curated deck has no bound MiM subckt table entry beyond the class label) — still a value + class token, not a subckt call; the schematic-vs-extracted MiM mapping methodology question below is **not** resolved by this flag |
| `R_10 \$10 \$10__par 1848.76` / `C… …__par vsubs …` | unchanged — ideal R/C, simulate directly, hang off `vsubs` |

**NOT closed — found here, filed upstream, and the actual blocker for #89:**
every PMOS device's body (Nwell) terminal lands on an **anonymous,
internal, non-pin net** — e.g. `X$149 \$65 sel_in vdd \$157 pfet_03v3 ...`,
where `$157` is not among `ADC_TOP`'s declared `.SUBCKT` pins at all, so a
wrapper testbench cannot even reach in and bias it — instead of the `vdd` tie
`design/adc-top/adc_top.spice`'s schematic assumes (the single-well
convention `sim/device-switch-ron/testbench/`'s own header states outright:
"NMOS body to ground, PMOS body to vdd"). gf180mcu's curated `klt extract`
deck has no distinct tap or well-label layer (documented in `klt`'s own
`docs/cli/extract.md` → "Coverage"), so this is a `klt` capability gap, not
something `--pdk` or any extraction flag fixes.

**Verified, not just read off the docs** (CLAUDE.md: no claim without a
testbench). Extracting the single-PMOS leaf cell `adc_tgate` the same way
(`--pdk gf180mcuD --parasitics`) and instantiating it in ngspice against
`sm141064.ngspice`'s `typical` corner, with the switch's source driven to 0 V
and the gate held on: the anonymous body node's DC operating point came back
at **≈ 0 V**, not the 3.3 V `vdd` the schematic ties it to — a full
supply-rail `V_sb` error on every PMOS device (switch `R_on`, comparator
branch bias, threshold voltage via the body effect), not a second-order
parasitic. Filed generically upstream, since it is a tool gap, not a defect in
this drawn layout:
[2AMLogic/klayout-tools#555](https://github.com/2AMLogic/klayout-tools/issues/555).

Concretely, closing the remaining gap (in #89, not here) needs, in some
order:

1. **Resolve the PMOS-body gap** — either upstream #555 landing, or a
   documented, reviewed local remediation (e.g. a post-processing pass that
   rewrites every anonymous PMOS-body net to `vdd`, using the same
   `body_net_of` Nwell-island mapping `layout/adc-top/lib/netlist.py` already
   computes for LVS purposes — clearly labelled as a local remediation of a
   known gap, not raw `klt extract` output, if taken instead of waiting on
   upstream).
2. **Map `C … cap_mim_2f0_m4m5_noshield`** either onto the PDK MiM subckt or a
   validated ideal capacitor at the extracted value, and decide which is the
   fair comparison against the schematic's subckt-instantiated MiM (a
   methodology choice that must be stated in the delta summary, not made
   silently).
3. **Bridge the structural mismatch**: the extracted netlist is a single flat
   `ADC_TOP`/`ADC_BLOCK` subckt, whereas `design/adc-top/gen_adc_top.py`
   inlines *two* `adc_cdac_side` instances and wires the comparator + SAR
   logic around them. `gen_adc_top.py` currently has no path to emit a
   testbench that instantiates the extracted core, so the generator needs an
   "extracted-core" mode (or a separate harness) that keeps the
   comparator/SAR-logic/stimulus schematic-level while swapping only the
   analog core.

None of this is produced here, because doing it half-correctly would yield
plausible-but-wrong spec numbers, which is worse than none. This directory
produces and substantiates the netlist that #89's work consumes.

#### Status update (#89, `remediate_extracted.py`)

The three items above are now **closed as pre-work** by
`remediate_extracted.py` + `verify_remediation_dc.py` (record
[`records/20260805-remediation-dc.md`](records/20260805-remediation-dc.md)),
which turn this extraction into a well-posed, simulatable core:

1. **PMOS-body gap — done, local remediation.** #555 re-checked, still OPEN, so
   the local path was taken: every anonymous PMOS-body net is rewritten to
   `vdd`, after asserting each appears *only* as a PMOS body terminal (148
   devices, 20 nets). Labelled as a remediation, not raw `klt` output.
2. **MiM mapping — done, PDK MiM subckt.** No rewrite needed: the `--pdk`
   extraction already emits `X … cap_mim_2f0_m4m5_noshield c_length=… c_width=…`
   subckt calls that bind to `sm141064_mim.ngspice` (the same subckt
   `sim/harness/pdk.py` resolves). The remediation asserts the binding (1024
   caps) and leaves the cards untouched.
3. **Structural mismatch — analog-core swap done; a second gap found and fixed.**
   The extracted `ADC_TOP` had **no input pin** (DR-0014 samples on the bottom
   plates through an internal per-side rail, `$8`/`$91`, never brought out).
   The remediation promotes those two rails to `vinp`/`vinn` pins, so a wrapper
   can inject the input. What is still **not** built is the wrapper itself —
   the comparator/SAR-logic/stimulus around the core, as a `gen_adc_top.py`
   "extracted-core" mode or a dedicated transient harness — which is what the
   deferred bench re-run (Scope items 1-5) needs.

A DC `op` across the full 63-point `cdac` PVT grid converges on the remediated
core with the PMOS bodies hard-tied to `vdd`; the raw extraction's bodies float
(measured 3.13–3.15 V, not the 3.3 V tie). The transient bench, Monte Carlo and
delta summary remain the open half of #89.

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
| 3 | every #13 bench re-run over full PVT with `Netlist provenance: extracted` | **deferred, tracked in #89** — blocked on the PMOS-body gap above (upstream #555 or a documented local remediation), then the remaining adaptation-layer items |
| 4 | #14 Monte Carlo re-run if models support it, else stated | **deferred, tracked in #89** — cannot run until the netlist is simulatable; whether the extraction flow supports statistical variation is itself a follow-up question |
| 5 | schematic-vs-extracted delta summary (incl. `gain_err_lsb`) | **deferred, tracked in #89** — needs items 3–4 |
| 6 | no spec relaxation | **held** — no spec touched; SFDR baseline caveat recorded, not patched |
| 7 | worst-corner edge cases re-checked post-extraction | **deferred, tracked in #89** — part of the bench re-run |
| 8 | extracted `gain_err_lsb` per corner alongside schematic + delta | **deferred, tracked in #89** — needs item 3 |

Items 3–5, 7, 8 are a coherent, separable follow-up, split off as issue #89:
resolve the PMOS-body gap (upstream #555, or a documented local remediation),
finish the remaining adaptation-layer items above, and run the #13/#14 suite
against this netlist. This increment is the netlist, the PDK-bound extraction
path, and the specification (including the newly-found blocking gap) of what
#89 must do.

## `adc_block` coverage (this revision)

`remediate_extracted.py` identifies every rewrite structurally (PMOS body
terminals, the bottom-plate T-gates' non-supply leg source), not by a
hardcoded `adc_top`-only name, so it already generalised to `adc_block` (the
same core plus the comparator) unchanged -- confirmed by running it, not
assumed: 160 PMOS devices / 25 anonymous body islands retied to `vdd`, the
same two input rails (`$8`→`vinp`, `$91`→`vinn`) promoted, 1024 MiM caps
confirmed on the native PDK subckt.

`verify_remediation_dc.py` was `ADC_TOP`-only (hardcoded, no `--top` flag);
this revision adds `--top {ADC_TOP,ADC_BLOCK}` (default unchanged) so it can
verify either. Doing so found and fixed a real bug the extension surfaced,
not present when only `adc_top` had ever been run through it: `adc_block`'s
comparator adds a cross-coupled regenerative latch node that makes ngspice's
own *trailing*, unrelated implicit-transient-op pass emit `singular matrix`
warnings after this script's own `.control op` had already converged and
printed a real result -- `run_op()`'s blanket log-keyword scan treated that
as a hard FAIL, reporting 0/63 for a core that had, in fact, converged 63/63.
See [`records/20260805-remediation-dc.md`](records/20260805-remediation-dc.md)
for the full root-cause writeup, the fix, and the re-run: 63/63 for both
`adc_top` and `adc_block` on the same 63-point `cdac` PVT grid.

While attempting to reuse this remediation for a full extracted-core
generator mode (the wrapper this record's "What remains" section still
defers), the underlying *physical layout* — as opposed to this directory's
simulation netlist — was independently confirmed to still have no drawn pin
for the fourth-leg input rail either (`layout/adc-top/gen_adc_top.py`'s own
intended flattening already names it `pinp`/`pinn`, but that name never
reaches the actual GDS/extraction). The `vinp`/`vinn` promotion above is an
accepted, permanent simulation-side remediation (the same class of fix as the
PMOS-body retie, not a stopgap waiting on a layout change) — but the GDS
still not carrying a real pin there is a separate, lower-priority
layout-fidelity gap worth having drawn for its own sake (accurate future
extractions without a promotion step). Tracked, downgraded from "blocks #89"
to a non-blocking enhancement, in #91.

**#91 closed the layout-fidelity gap** (label-only, no routing change --
`gen_adc_top.py`'s per-side decode bank already routed the fourth-leg input
rail into one continuous Metal1 trunk; the pin label draw call was simply
missing from that bank's `pins=` list). A RAW `klt extract` of the current
GDS (no `remediate_extracted.py` post-processing) now declares `pinp`/`pinn`
directly: `pin_count` 63→65 (`ADC_TOP`), 67→69 (`ADC_BLOCK`); `klt
lvs`/`klt drc` unaffected (device/net counts and DRC status unchanged --
labels carry no geometry or connectivity); record
[`records/20260805-layout-pin-dc.md`](records/20260805-layout-pin-dc.md).
`remediate_extracted.py`'s own rail-detection was made forward-compatible
with an already-pinned rail so it keeps producing the canonical `vinp`/`vinn`
names either way (verified against both a pre-#91 and a post-#91 report,
see that record).

## Extracted-core testbench harness (issue #89 Scope item 0)

The wrapper the section above still deferred is done: `gen_extracted_core_tb.py`
wires the remediated extracted `ADC_TOP` core into a complete conversion
chain (the schematic comparator + rung-1 SAR controller + DR-0013 input
drive network stay schematic-level, per the issue's own wording), and
`verify_extracted_core_conversion.py` runs an actual transient conversion
against it and confirms it decodes real codes: three known input transitions,
one nominal corner, decoded within 1-2 LSB of expected (well inside the
inherited +/-45 LSB liveness tolerance). `ADC_TOP` only, not `ADC_BLOCK` --
`ADC_BLOCK`'s extracted core bakes the comparator IN, which would no longer
be schematic-level. Full writeup, the pin-mapping table, and the reproduce
commands: [`records/20260805-extracted-core-smoke.md`](records/20260805-extracted-core-smoke.md).

This closes Scope item 0. **Scope items 1-2 (the full #13 PVT bench, the #14
Monte Carlo) and 3, 8 (the schematic-vs-extracted delta summary) remain
open, tracked in #89** — this harness is the substrate those campaigns run
against, not the campaigns themselves.
