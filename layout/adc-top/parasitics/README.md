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

The runner probes `klt`'s capabilities against the pin, resolves the
fleet-ratified `gf180mcuD` PDK install via `klt pdk find --pdk gf180mcuD`
(the same resolver `sim/harness/pdk.py` uses for its own `PDK_ROOT`/`PDK`,
now pinned to the same `DEFAULT_VARIANT` — see DR-0022), and runs

```
klt extract ../adc_top.gds   --deck gf180mcu --parasitics --top ADC_TOP   --pdk gf180mcuD --pdk-root <resolved> -o adc_top.para.spice   --format json
klt extract ../adc_block.gds --deck gf180mcu --parasitics --top ADC_BLOCK --pdk gf180mcuD --pdk-root <resolved> -o adc_block.para.spice --format json
```

live on every invocation, asserts each block's structured summary against
`cells.json` (device/net/pin counts, the per-class device tally, and that the
`parasitics` block populated with the expected R/C counts), verifies each
source GDS's sha256 belongs to the committed geometry, and writes an
append-only record under `records/` + `reports/`. **If `gf180mcuD`
specifically fails to resolve, the run fails loudly** (`resolve_pdk()`
raises `ToolingError`, exit code 1, no record written) instead of silently
degrading to bare `M ... nfet` class cards against an unpinned or
wrong-variant PDK — this closed a real defect (issue #228): earlier runs on
hosts without a `gf180mcuD` install silently resolved `gf180mcuA` instead
(via ciel or volare, on two different hosts) and minted evidence against it
without anyone noticing. Install `gf180mcuD` (volare or ciel) or set
`PDK_ROOT`/`GF180_PDK_PATH` to a `gf180mcuD` install to unblock a failing
run; there is no more silent bare-device-card fallback.

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
| `adc_tgate` (leaf) | ADC_TGATE | 2 | 6 | 5 | 0 | 1 | 1 | 4 | 4 | 303 | 9.2 |

> **This table is the ORIGINAL (2026-08-05) extraction and is kept as the
> record of it.** The parasitic topology changed at the `875eac3` pin
> (star-split in-path R — see "What the parasitics model" below), and the CDAC
> unit cap itself changed with DR-0019. The **current** extraction is
> [`records/20260817-153913-2494bd0.md`](records/20260817-153913-2494bd0.md)
> (issue #218), the first taken after PR #202 physically implemented the
> resize:
>
> | block | devices | nets | pins | para R | para C | ΣR (Ω) | ΣC (fF) |
> |---|---|---|---|---|---|---|---|
> | `adc_top` | 1320 | 177 | 65 | 2936 | 156 | 118 907.45 | 5855.91 |
> | `adc_block` | 1349 | 198 | 71 | 3021 | 172 | 146 741.22 | 6307.03 |
> | `adc_tgate` (leaf) | 2 | 6 | 5 | 6 | 4 | 302.80 | 9.235 |
>
> The array-side check that this extraction belongs to the resized geometry is
> per-device, not per-block: each of the 1024 MiM caps reports
> `area_um2 = 16.0` and `c_f = 3.56528e-14` (DR-0019's ratified `C_u`), against
> `7.365796` / `1.7244919e-14` in every earlier report. `adc_tgate`'s netlist
> is **byte-identical** across the two vintages — DR-0019 resizes the CDAC unit
> cap only, not the switch leaf — which is why `sim/device-switch-ron/`'s
> re-take at this extraction is an exact null
> (`sim/extracted-delta-summary.md` §4.12.5).

`adc_top` is the CDAC analog core (both sides, the four-leg bottom-plate switch
network + local drivers); `adc_block` additionally carries the comparator.
`adc_tgate` is a **leaf** cell, not a block: the drawn transmission gate the
DR-0014 fourth leg and the input structure are built from, extracted so
`sim/extracted-delta-summary.md` §6.3's post-layout switch-R_on re-take has a
real netlist to measure (`layout/adc-top/cells/` holds the only standalone
drawn cells; there is no `adc_cdac_side.gds`). Its counts are per-cell: two
devices, five pins, no MiM. The
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
(measured 3.13–3.15 V, not the 3.3 V tie).

**Update — the wrapper is built and the first full bench has run.**
`gen_extracted_inl_dnl_tb.py` (this directory) is that wrapper for the #13
static-linearity bench: it puts the remediated extracted `ADC_TOP` in place of
the two schematic `adc_cdac_side` instances and keeps the comparator, rung-1
SAR controller and DR-0013 input drive schematic-level, reusing
`sim/adc-inl-dnl/testbench/tb.json` **unmodified** via
`run_corners.py --netlist`. The 27-point `tt`/`ss`/`ff` PVT grid runs 27/27
PASS on it.

**Update — all three #13 spec-line decks have now run.** The same wrapper
pattern carries two more generators in this directory, each reusing its own
experiment's `tb.json` unmodified:

| deck | generator | extracted record |
|---|---|---|
| static linearity | `gen_extracted_inl_dnl_tb.py` | `sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md` (27 pts, 27/27 PASS); `cdac`-set isolation `20260806-052258-8d36824.md` (63 pts, 63/63 PASS) |
| dynamic (ENOB/FFT/SFDR/THD) | `gen_extracted_enob_fft_tb.py` | `sim/adc-enob-fft/records/20260806-060520-72a230a.md` (9 pts, the schematic baseline's own two-stage subset) |
| power | `gen_extracted_power_tb.py` | `sim/adc-power/records/` — see §"Power: a four-way split, not five" below |

The **DR-0012/13 gain-error** row has since been added to that list of closed
ones: it is **measured and PASSING** post-layout (`tp_inj_signal_dep_lsb`,
27/27, ~307× inside the ≤ 0.5 LSB bound on the in-path extraction —
[`sim/dr0014-sampling/records/20260807-091733-434dc37.md`](../../../sim/dr0014-sampling/records/20260807-091733-434dc37.md),
superseding the lumped-stub
[`20260806-141727-5ba48d5`](../../../sim/dr0014-sampling/records/20260806-141727-5ba48d5.md)
that first closed this row at ~65×,
[`sim/extracted-delta-summary.md`](../../../sim/extracted-delta-summary.md)
§4.9 / §6.3), on the same `_wire_pin()` wrapper pattern — the flat `ADC_TOP`
boundary already *is* the array sides DR-0014's Groups A/C isolate, so no
standalone `adc_cdac_side` leaf extraction is needed for it.

What remains open on #89 after these is **rate closure** and the
comparator-inclusive MOS-mismatch Monte Carlo on `ADC_BLOCK` — see
[`sim/extracted-delta-summary.md`](../../../sim/extracted-delta-summary.md) §6,
which states the cost and the blocker for each. Rate closure is **not**
a missing deck; see the next section.

### What the parasitics model, and what they do not: in-path R since the `875eac3` pin

Measured over every committed extraction by
`audit_parasitic_topology.py` (record
[`records/20260806-parasitic-topology.md`](records/20260806-parasitic-topology.md)),
because the answer bounds what any post-layout number here can mean:

**Now** (pin `875eac3`, upstream `klayout-tools#593`):

| netlist | form | parasitic nets | **in-path R** | stub R | ΣR (Ω) | max R (Ω) |
|---|---|---|---|---|---|---|
| `adc_top.para.spice` | star-split | 156 | **156** | 0 | 117 685 | 16 014 |
| `adc_block.para.spice` | star-split | 170 | **170** | 0 | 132 775 | 20 421 |
| `adc_tgate.para.spice` | star-split | 4 | **4** | 0 | 303 | 120 |

Each net is now a hub plus one leg per device terminal
(`R<net>_t<k> <net>__t<k> <net>`), with the net's C on the hub, so two
terminals on one net are separated by real, layout-dependent series
resistance. 330 of 330 parasitic nets are in-path.

**Before** (pin `af5791b` and earlier — still the topology of the netlists
extracted at those pins, which are kept in `reports/`):

| netlist | parasitic nets | **in-path R** | stub R | ΣR (Ω) | max R (Ω) |
|---|---|---|---|---|---|
| `adc_top.para.spice` | 156 | **0** | 156 | 115 320 | 16 013 |
| `adc_block.para.spice` | 172 | **0** | 172 | 129 704 | 20 499 |
| `adc_tgate.para.spice` | 4 | **0** | 4 | 303 | 120 |

At those pins `klt extract --parasitics` wrote one
`R<net> <net> <net>__par` and one `C<net> <net>__par <ground>` per net, and
**every device was attached to `<net>`, never to `<net>__par`**. The extracted
resistance was a stub — it put each net's capacitance behind a small series
resistance and carried no device current itself, so **no resistive quantity
could move post-layout**: R_on, IR drop, electromigration, or the CDAC
settling network's `R_WORST_BIT_OHM` that rate closure needs. That was
confirmed by measurement, not inferred: the drawn `adc_tgate` cell was
extracted, spliced into `sim/device-switch-ron/`'s own deck by
`gen_extracted_switch_ron_tb.py`, and run over the 45-point `mos` PVT grid —
**0 of 1125 result cells differed** from the schematic baseline, while a
positive control that moved the same extracted resistors into the channel
shifted R_on by +196.2 Ω.

That was a generic gap in the open flow rather than something specific to this
design, and per CLAUDE.md's canary rule it went upstream.
[`klayout-tools#338`](https://github.com/2AMLogic/klayout-tools/issues/338)
reported the same Γ-topology and was closed **completed on 2026-08-03 as a
documentation-only fix**: its curation scoped out the star-topology split and
full distributed RC, recommending a separate follow-up issue "if/when there's
appetite to implement Option 2". That follow-up was filed as
[`#592`](https://github.com/2AMLogic/klayout-tools/issues/592) and **closed
`COMPLETED` on 2026-08-06** via merged PR
[`#593`](https://github.com/2AMLogic/klayout-tools/pull/593). Re-running the
same 45-point grid at the new pin now measures **+77.4 Ω at
`ss_125c_2.97v`** where it measured exactly zero before — delta summary §1.4,
§4.8 and §6.3.

What the fix does **not** buy: full distributed per-segment RC (`#592`'s
Option 2) is still explicitly out of scope upstream, so a number that depends
on the resistance profile *along* a conductor, rather than on
terminal-to-terminal series resistance, is still not expressible here.

**A second, magnitude-side caveat on the same tables.** The pinned build's
gf180mcu parasitics table has one `LayerRC` for a five-level metal stack, so
Metal2..Metal5 contribute zero R **and zero C** — verified against the
installed `klt 0.2.0`
(`len(gf180mcu.EXTRACTION_DECK.metals) == 5` vs
`len(gf180mcu.PARASITICS.metals) == 1`), while `lib/geometry.py` draws the
`L_METAL2` riser and the Metal4/Metal5 MiM plates. Upstream
[`klayout-tools#547`](https://github.com/2AMLogic/klayout-tools/issues/547)
fixed this on 2026-08-05, after this repo's pin (`layout/toolchain.json`,
`af5791b`). So every ΣC in the table above, and every loading delta in the
delta summary's §4, is a **Metal1-only lower bound**. Closing it is a
toolchain-pin bump plus a re-run of the three §4 decks — its own increment.

### Decision record — issue #123: the star-split in-path pin is the basis for the three `sim/adc-*` decks

`_latest_report()` (`remediate_extracted.py`) selects the newest committed
`adc_top.para.spice` containing `pfet_03v3` cards — i.e. it already always
resolves to whatever `layout/toolchain.json` last extracted at. When PR #119
bumped the pin `af5791b` → `875eac3` (landing `klayout-tools#593`'s
star-topology in-path parasitic resistance, `r_count` 156 → 2936 on
`adc_top`), the *selector* picked up the new report automatically, but the
three `gen_extracted_{inl_dnl,enob_fft,power}_tb.py` decks are only
*regenerated* on demand (`python3 <generator>.py`, no flags) — so they kept
emitting the pre-bump 156-R deck until this issue's regeneration, silently
diverging from every other consumer of `_latest_report()` (DRC, LVS, the
`device-switch-ron` deck) that had already moved.

**Decision: yes, adopt the pinned star-split in-path extraction as the basis
for these three decks — it already is the basis for everything else in this
directory.** There is no live blocker specific to what these three decks
extract:

- They wrap the **`ADC_TOP`** extraction only (the CDAC array + top-plate
  switch), with the comparator and rung-1 SAR controller kept
  schematic-level — see each generator's own module docstring, "Scope item
  0". `2AMLogic/klayout-tools#595` (still open) blocks the
  comparator-**inclusive** `ADC_BLOCK` extraction (issue #116's regeneration
  margin), a different, unrelated extraction target these decks never touch.
- `klayout-tools#592`/`#593` (the star-topology in-path R this pin lands) is
  **closed and merged**, and is already this repo's pinned toolchain state,
  not a pending change.
- Full **distributed per-segment RC** (`#592`'s Option 2 — resistance
  distributed *along* a conductor rather than lumped terminal-to-terminal) is
  still explicitly out of scope upstream (see "What the fix does not buy"
  above). "In-path" here means star-split terminal-to-terminal series R, not
  per-segment distributed RC — issue #123's title uses the two terms loosely
  as a pair; they are not the same topology, and only the star-split in-path
  form is what landed and what these three decks now use.

Regenerated and re-run, each appending a new dated record alongside — never
replacing — the pre-`875eac3` one it supersedes, per `sim/README.md`'s
append-only rule, at that record's **own** grid (no coverage narrowed because
the DUT changed):

| claim | superseded | in-path record | verdict |
|---|---|---|---|
| INL/DNL | `20260806-052258-8d36824` | `sim/adc-inl-dnl/records/20260807-051433-7845f17.md` | 63/63 PASS, worst \|INL\| 0.148 LSB |
| ENOB/FFT | `20260806-081350-862d054` | `sim/adc-enob-fft/records/20260807-054805-e8cd2b8.md` | 9/9 PASS, worst ENOB 9.311 bits |
| power | `20260806-083932-faebccc` | `sim/adc-power/records/20260807-060526-03e80b9.md` | 220.9 µW worst vs < 1 mW; harness FAIL on one sensitivity witness — `sim/extracted-delta-summary.md` §7.3 |

The full lumped-stub → in-path comparison is `sim/extracted-delta-summary.md`
§4.10, and the power record's escalation §7.3.

#### Superseded again by the DR-0019 re-take (issue #218)

Those three records — and the two below them (`dr0014-sampling`,
`device-switch-ron`) — all measure the layout at the historical
`C_u = 17.24 fF`. PR #202 physically implemented DR-0019's resize, and issue
#218 re-extracted the layout
([`records/20260817-153913-2494bd0.md`](records/20260817-153913-2494bd0.md))
and re-ran all five campaigns against it on the **same** decks, manifests and
grids. The decision recorded above is unchanged (the star-split in-path
extraction is still the basis); only the geometry moved:

| campaign | DR-0019 re-take | verdict at `C_u = 35.6528 fF` |
|---|---|---|
| INL/DNL | `sim/adc-inl-dnl/records/20260817-162837-3a9afd2.md` | 27/27 PASS; worst \|INL\| 0.148 → **0.528 LSB**, worst \|DNL\| → **0.728 LSB** — inside `< 1 LSB`, outside the `< 0.5` stretch |
| ENOB/FFT | `sim/adc-enob-fft/records/20260817-180617-c4693f9.md` | capture 9/9 PASS; **ENOB 8.857 bits and SFDR 60.40 dB worst — both spec rows FAIL** |
| power | `sim/adc-power/records/20260817-174602-71b6844.md` | 27/27 PASS, 220.9 → **246.5 µW** worst; the §7.3 sensitivity witness passes in this vintage |
| DR-0014 mechanism | `sim/dr0014-sampling/records/20260817-172040-5c0f0cc.md` | 27/27 PASS; `tp_inj_signal_dep_lsb` **improves −70.7 %**, ~1047× inside its bound |
| switch `R_on` | `sim/device-switch-ron/records/20260817-172213-5c0f0cc.md` | **exact null** — `adc_tgate`'s extracted netlist is byte-identical across the two vintages |

Per-campaign before/after tables: `sim/extracted-delta-summary.md` §4.12.

#### Superseded AGAIN, in the same way, by issue #215's layout recovery (issue #224)

Those five records — and the extraction that fed them
(`20260817-153913-2494bd0`) — all measured the pre-#215 geometry. Issue #215
changed `adc_top.gds` / `adc_block.gds` (the comparator's load-resistor fold
and a re-derivation of both top-level supply corridors), and issue #224
re-extracted the layout
([`records/20260817-204449-076d545.md`](records/20260817-204449-076d545.md))
and re-ran all five campaigns against it, exactly the same shape as
PR #202 → issue #218:

| block | ΣR (Ω), `2494bd0` → #224 | ΣC (fF), `2494bd0` → #224 |
|---|---|---|
| `adc_top` | 118 907.45 → 118 871.00 (**−0.03 %**) | 5855.91 → 5843.59 (**−0.21 %**) |
| `adc_block` | 146 741.22 → 129 734.59 (**−11.59 %**) | 6307.03 → 6052.98 (**−4.03 %**) |
| `adc_tgate` (leaf) | unchanged | unchanged |

`adc_top` — the top cell **every** `sim/*` extracted deck is built from —
moves by a fifth of a percent; `adc_block` moves much more (no campaign in
`sim/` is built on it — its one consumer is `measure_extracted_regeneration.py`).
Despite the small aggregate `adc_top` move, the **power** campaign shows a
real, non-trivial delta (§4.13.3 below): the comparator load-resistor fold
changed a resistor the comparator's own dynamic switching current runs
through directly, which the aggregate ΣR/ΣC summary does not surface. Every
other campaign moves by noise-floor amounts, confirming the "should move very
little" expectation issue #224 stated but did not assume:

| campaign | issue #224 re-take | verdict at the recovered layout |
|---|---|---|
| INL/DNL | `sim/adc-inl-dnl/records/20260817-214114-076d545.md` | 27/27 PASS; worst \|INL\| 0.528446 → **0.528287 LSB** (+0.03 %), worst \|DNL\| 0.72779 → **0.727556 LSB** (−0.03 %) — noise-floor move, both still inside `< 1 LSB`, outside the `< 0.5` stretch |
| ENOB/FFT | `sim/adc-enob-fft/records/20260817-215657-076d545.md` | capture 9/9 PASS; **ENOB 8.857 bits and SFDR 60.40 dB worst — unchanged from the pre-#215 vintage, both spec rows still FAIL** |
| power | `sim/adc-power/records/20260817-211252-076d545.md` | 27/27 PASS, 246.5 → **231.8 µW** worst (**−6.0 %**) — the comparator load-resistor fold's real, measured effect; still 4.3× inside the `< 1 mW` bound |
| DR-0014 mechanism | `sim/dr0014-sampling/records/20260817-204729-076d545.md` | 27/27 PASS; `tp_inj_signal_dep_lsb` moves +1.5 % (noise-floor), stays ~1030× inside its bound |
| switch `R_on` | `sim/device-switch-ron/records/20260817-204715-076d545.md` | **exact null** — `adc_tgate`'s extracted netlist is byte-identical to the pre-#215 vintage (the fourth-leg cell #215 did not touch), `ron_t_max`/`ron_t_min`/`ron_t_flatness` all delta 0 |

Per-campaign before/after tables: `sim/extracted-delta-summary.md` §4.13.

`gen_extracted_switch_ron_tb.py` is unaffected by this decision — its deck
already tracked the pin's *content*, and only its `* Source:` provenance
comment needed rewriting (consistent with issue #111's measured zero R_on
delta at the previous pin and the +77.4 Ω at this one, `sim/extracted-delta-summary.md`
§4.8). All four generators are now covered by the same guard test
(`sim/tests/test_extracted_decks_current.py`), so a future re-drift on any of
them is caught before it ships rather than a generation later.

**Runnability, recorded because it is part of re-deriving these numbers.**
The in-path split adds ~4256 nodes to `ADC_TOP`, and ngspice stores a
transient waveform for every node unless told otherwise — 260 822 400 B for
the 20 µs INL/DNL deck, which it refuses to allocate, killing the point
before any measurement (all 63 points, at `-j 6`). The three ADC generators
now emit `.save <exactly the vectors the manifest reads>`
(`gen_extracted_core_tb.saved_vectors_lines()`, derived from the manifest
rather than hand-listed). Retention only: no model, tolerance or timestep
changes, and `tt_27c_3.30v` returns `m_gain_err_lsb = -1.988646536e+00` with
and without it. ngspice-46 implements no `maxdata` option, so raising the cap
is not an available alternative.

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
| 3 | every #13 bench re-run over full PVT with `Netlist provenance: extracted` | **met for all three #13 spec-line decks; rate closure still tracked in #89** — static linearity 27/27 PASS ([`20260805-203322-3b6d7b7`](../../../sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md)) plus the `cdac`-set isolation 63/63 PASS ([`20260806-052258-8d36824`](../../../sim/adc-inl-dnl/records/20260806-052258-8d36824.md)); ENOB/FFT/SFDR/THD 9/9 on the schematic baseline's own two-stage subset ([`20260806-081350-862d054`](../../../sim/adc-enob-fft/records/20260806-081350-862d054.md), the clean-tree re-run PR #105 minted); power 27/27 PASS ([`20260806-083932-faebccc`](../../../sim/adc-power/records/20260806-083932-faebccc.md)). The DR-0012/13 gain-error row is **measured and PASSING** post-layout (`tp_inj_signal_dep_lsb`, 27/27, ~307× inside the ≤ 0.5 LSB bound on the in-path extraction — [`20260807-091733-434dc37`](../../../sim/dr0014-sampling/records/20260807-091733-434dc37.md), superseding [`20260806-141727-5ba48d5`](../../../sim/dr0014-sampling/records/20260806-141727-5ba48d5.md), `sim/extracted-delta-summary.md` §4.9): it is a charge-injection voltage snapshot, not a resistive quantity, and the flat `ADC_TOP` boundary already *is* the array sides its Groups A/C isolate. Rate closure remains **not measurable at this extraction fidelity**: its `R_WORST_BIT_OHM` input is a resistance, and this extraction places no resistance in any signal path — measured on the one leaf cell that *is* drawn (`adc_tgate`, 45-point grid, 0 of 1125 cells different, with a positive control proving the deck would have seen it), [`records/20260806-parasitic-topology.md`](records/20260806-parasitic-topology.md) and `sim/extracted-delta-summary.md` §1.4/§4.8/§6.3. §6.4's `ADC_BLOCK` defect still blocks the `T_COMP_REGEN_NS` input too, but is no longer the binding one |
| 4 | #14 Monte Carlo re-run if models support it, else stated | **met — both halves, one stated and one measured**. *Capacitor half*: stated (`sim/extracted-delta-summary.md` §5) — #14's bench is a behavioral numpy model with no netlist to swap, and the reason is structural: this PDK ships no local capacitor mismatch model (`sm141064_mim.ngspice` carries no `agauss`/`mis_*`/`sw_stat_mismatch` term), so an ngspice MC of the extracted CDAC would report exactly zero mismatch — a silent false pass. *MOS half*: **measured**, not deferred — `mc_extracted_core.py` runs a 120-draw mismatch population of full transistor-level conversions on the extracted core with a mandatory null control, σ = 1.99e-3 LSB at the worst carry against σ = 0 frozen control ([`records/20260805-extracted-core-mc.md`](records/20260805-extracted-core-mc.md)). A comparator-inclusive run needs `ADC_BLOCK`; the wiring now exists (`gen_extracted_core_tb.py --top ADC_BLOCK`) but its own functional smoke test reproducibly FAILs (stuck decision, two PVT corners, root cause not yet identified) — [`records/20260806-adc-block-comparator-smoke.md`](records/20260806-adc-block-comparator-smoke.md), also `sim/extracted-delta-summary.md` §6.4 |
| 5 | schematic-vs-extracted delta summary (incl. `gain_err_lsb`) | **met for the benches that have run** — [`sim/extracted-delta-summary.md`](../../../sim/extracted-delta-summary.md), one row per spec line, each row either measured-with-a-delta or not-yet-measured-with-the-reason. Numbers derived mechanically from the two committed records by `sim/tools/schematic_vs_extracted.py`, not transcribed |
| 6 | no spec relaxation | **held** — no spec touched; SFDR baseline caveat recorded, not patched. The extracted static-linearity run passes on its own terms; no verdict changed schematic → extracted |
| 7 | worst-corner edge cases re-checked post-extraction | **met, and it found something** — static linearity: worst INL corner unchanged by the layout (`ss_-40c_2.97v`, transition 384, −0.1082 → −0.1109 LSB). ENOB/SFDR: worst corner unchanged (`ss_125c_2.97v` on both sides), and the pre-existing SFDR FAIL there widens from a 0.67 dB to a 1.89 dB miss — escalated in `sim/extracted-delta-summary.md` §7.1, not absorbed. Power: the worst-corner re-check surfaced a **2× comparator-current excursion at `tt_125c_3.63v`, full scale**, against ±1.4 % at the other 26 corners — diagnosed against both cores ([`records/20260806-power-cmp-anomaly.md`](records/20260806-power-cmp-anomaly.md)) and escalated in §7.2. The row still PASSES with 3.7× margin |
| 8 | extracted `gain_err_lsb` per corner alongside schematic + delta | **met, and the disagreement is now closed by experiment** — 27 corners, delta +0.00285 … +0.00661 LSB (mean +0.00520). This does **not** reproduce record `20260805-163000-e8017f2`'s −0.55 LSB delta, and that is no longer a hypothesis: the schematic core reproduces the same −2.54 … −2.59 LSB endpoint under the same two-point stimulus (record [`20260805-224500-2c21be4`](../../../sim/adc-inl-dnl/records/20260805-224500-2c21be4.md)), so the −0.55 LSB is a settling artefact of that deck, not a layout effect. Downstream consumers such as #53 use the +0.006 LSB number |

Items 3–5, 7, 8 are a coherent, separable follow-up, split off as issue #89:
resolve the PMOS-body gap (upstream #555, or a documented local remediation),
finish the remaining adaptation-layer items above, and run the #13/#14 suite
against this netlist. This increment is the netlist, the PDK-bound extraction
path, and the specification (including the newly-found blocking gap) of what
#89 must do.

## `klt pex` evidence (issue #173, T1 checklist item 7)

`klayout-tools` epic #709 shipped `klt pex` — a single-command
schematic-vs-extracted delta report, meant to close the T1 checklist's
"Post-layout verification" item directly against a live tool report instead
of the manual re-simulation this directory's own extracted-core generators
(above) hand-build. It was run for real, against `comparator.gds`, from
issue #173: [`sim/comparator-pex/`](../../../sim/comparator-pex/).

**Result: blocked, not a pass.** `klt pex`'s DUT-swap mechanism requires the
schematic and extracted-side netlists to share one identical top-level
`.subckt` interface (name + pin list), because it re-simulates both sides
from the SAME unmodified `Xdut` instantiation line, re-pointing only the
`.include` target. That precondition does not hold for any block this
directory's own extractions produce: `klt extract`'s gf180mcu deck promotes
body/tap nets (`vsubs`) and, at whatever granularity a block was extracted,
internal analog nodes (`comparator`'s preamp outputs, `pon`/`pop`) that a
hand-written schematic `.subckt` does not expose at its public interface —
exactly the gap `_wire_pin()`/`gen_extracted_core_tb.py` (above) were built
to bridge, with a bespoke per-block wiring layer instead of a single
`.include` swap. `klt pex` has no equivalent caller-supplied
interface-remapping mechanism today; filed generically as
[`klayout-tools#1030`](https://github.com/2AMLogic/klayout-tools/issues/1030).

This is a genuinely different, more specific blocker than "the `pex`
subcommand does not exist yet" (the pre-#173 state): the tool exists, was
installed, and was run against a real post-layout target with a real
schematic-vs-extracted testbench — it fails structurally at netlist
elaboration, cited with the exact `ngspice` diagnostic in
[`sim/comparator-pex/records/`](../../../sim/comparator-pex/records/). It
does **not** supersede or replace the non-`klt-pex` post-layout evidence
this directory and `sim/extracted-delta-summary.md` already carry (the
manual `_wire_pin()`-based extracted-core re-simulations remain this
repo's actual post-layout evidence path for now) — it is a distinct claim
(can `klt pex` itself close item 7 today) with its own answer (not yet).

Also note: issue #173 tried bumping `layout/toolchain.json`'s production
`klt` pin to pick up `klt pex` and found the bump is **not** the safe,
mechanical absorption it looked like from the outside — `klt extract`'s
device-parameter and warning-list shape changed between the pinned commit
and `klt pex`'s shipment. `klt lvs` itself was unaffected (every case still
reported `mismatches=0` against a fresh extraction), so this was bookkeeping
drift, not a design regression — but re-baselining it was real work with
real review burden, deferred to
[gf180-sar-adc#178](https://github.com/2AMLogic/gf180-sar-adc/issues/178)
rather than rushed through here. **#178 has since landed the bump** (`klt`
pin now `85b8125`, `layout/toolchain.json`'s own `_comment` has the full
re-baseline): the committed `.spice` netlist snapshots turned out NOT to go
stale after all (verified directly — `af58e41`'s device-parameter fields
land on `--pdk`-bound X cards only, and `run_lvs.py`'s extraction never
passes `--pdk`), only the `klt extract` JSON summary's `warnings[]`/
`devices[].params` shape and the `--pdk`-bound `.para.spice` reports under
`reports/` (which this directory's own extracted-core generators DO
consume) moved — see `layout/toolchain.json` for the full accounting,
including a real (~1.1-1.2%) extracted-capacitance shift `#178` found and
closed a manifest-assertion gap for (`klayout-tools#764`, vertical-overlap
coupling capacitance). This section's own `klt pex` finding above is
unaffected by that bump: `klt pex` is still blocked by
`klayout-tools#1030` regardless of which pin is production.
`sim/comparator-pex/`'s evidence above still runs against a separate,
investigative `klt` pin (`run_pex_comparator.py`'s own docstring), not the
production one this directory's other evidence uses.

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
inherited +/-45 LSB liveness tolerance). Full writeup, the pin-mapping table,
and the reproduce commands: [`records/20260805-extracted-core-smoke.md`](records/20260805-extracted-core-smoke.md).

This closes Scope item 0 — this harness is the substrate the campaigns run
against, not the campaigns themselves. Those campaigns have since run on it:
the #13 static-linearity PVT bench (Scope item 1) and the delta summary
(items 3 / 8) in PR #97, and the extracted-core Monte Carlo (item 2) plus the
gain-error settling control below. **ENOB/FFT/SFDR and power (the rest of
item 1) remain open, tracked in #89.**

**`ADC_BLOCK` (comparator baked in) — wiring added, functional smoke test
FAILs.** Both `gen_extracted_core_tb.py` and `verify_extracted_core_conversion.py`
now accept `--top ADC_BLOCK` (the extraction whose comparator sits INSIDE the
boundary, `.SUBCKT` pins `cmpclk`/`dout`/`doutb`/`ibias` wired directly onto
the controller instead of a second schematic comparator instance). Its own
functional smoke test does NOT pass: every probed transition decodes to the
same stuck code at both a nominal and the worst-case PVT corner, independent
of `dout`/`doutb` polarity, while the `ADC_TOP` control at the same commit is
unaffected -- ngspice's initial transient bias-point solve reports a singular
internal node (`xdut.$168`) through every fallback strategy first. Root cause
not identified within this pass. Full repro, what was ruled out, and the raw
diagnostic log: [`records/20260806-adc-block-comparator-smoke.md`](records/20260806-adc-block-comparator-smoke.md).
**Not** a Scope item 0 regression (that item's own `ADC_TOP` claim is
unaffected) -- this is the concrete blocker for the still-open
comparator-inclusive Monte Carlo item named in `sim/extracted-delta-summary.md`
§6.4, now measured rather than merely anticipated.

## Extracted-core gain-error delta (issue #89 Scope items 3 / 8)

The first real spec-line quantity is now measured against the extracted core:
`measure_extracted_gain_err.py` adds the ideal shadow DAC + input-referred
error node (copied verbatim from `gen_adc_top._core()`) onto the harness above
and reports **`gain_err_lsb`**, per corner, by the SAME endpoint-extrapolation
(transitions 1 and 1023) `sim/adc-inl-dnl/`'s schematic bench uses -- so the
number is directly comparable to that bench's own column. Over the full
`mos` PVT grid (5 process × 3 temp × 3 supply = 45 points, 0 non-convergent),
the extracted core's `gain_err_lsb` runs a **consistent -0.51 to -0.63 LSB
(mean -0.555)** more negative than the schematic baseline
(`sim/adc-inl-dnl/records/20260802-141402-1224e11.md`), worst at
`ss_125c_2.97v` -- the extracted layout's top-plate / interconnect parasitic
gain-attenuation term #53 predicts, adding to the schematic's ≈ -2.00 LSB
DR-0012 systematic term for a total ≈ -2.56 LSB (well inside the DR-0014
INL/DNL record's wide `gain_err_lsb` check window; a systematic, correctable
term, not a spec threat). Full delta table, per-corner data, and reproduce
commands:
[`sim/adc-inl-dnl/records/20260805-163000-e8017f2.md`](../../../sim/adc-inl-dnl/records/20260805-163000-e8017f2.md).

> ### ⚠ CORRECTED — do not use the −0.51 to −0.63 LSB delta above
>
> That delta is a **measurement artefact of this deck's two-point stimulus**,
> not a layout effect, and it is now **superseded by experiment** — see
> "The gain-error disagreement, closed by a null control" below. The
> corrected extracted-vs-schematic `gain_err_lsb` delta is **+0.006 LSB**
> (record
> [`20260805-203322-3b6d7b7`](../../../sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md),
> 27 corners, PR #97), and the control that establishes it is record
> [`20260805-224500-2c21be4`](../../../sim/adc-inl-dnl/records/20260805-224500-2c21be4.md).
> Per `sim/README.md`'s append-only rule the superseded record is not edited
> or deleted; the paragraph above is left standing as what that measurement
> reported, with this pointer attached.

### The gain-error disagreement, closed by a null control

Two records measured `gain_err_lsb` on the *same* extracted core with the
*same* endpoint-extrapolation formula and disagreed by 0.57 LSB:
`20260805-163000-e8017f2` (the bespoke two-point deck above) reported
−2.52 … −2.63 LSB, while `20260805-203322-3b6d7b7` (PR #97, the schematic
bench's own 18-transition manifest run against the extracted core) reported
−1.99 … −2.01 LSB — matching the schematic baseline's own value. §4.3 of
[`sim/extracted-delta-summary.md`](../../../sim/extracted-delta-summary.md)
named the likely mechanism and explicitly filed the decisive control as a
follow-up rather than asserting it.

`probe_gain_err_settling.py` is that control, and it is falsifiable rather
than a plausible story. It drives the bespoke deck's own two-point ladder,
then **holds** transition 1023 for `--hold` further conversions and reads the
same error node at each — and it does so against **either** core, changing
nothing else. Without the schematic arm, "the deck reads an unsettled value
one conversion after a full-scale step" and "the extracted core settles more
slowly than the schematic one" are indistinguishable, and only the second
would be a post-layout finding.

`gain_err_lsb`, 3 PVT points × 2 cores (extracted / schematic control):

| corner | hold 1 (what the bespoke deck reads) | hold 8 (settled) |
|---|---|---|
| `tt_27c_2.97v` | −2.5601 / **−2.5570** | −1.9865 / **−1.9895** |
| `ss_-40c_2.97v` | −2.5946 / **−2.5918** | −1.9839 / **−1.9873** |
| `ff_125c_3.63v` | −2.5406 / **−2.5388** | −2.0038 / **−2.0077** |

The **schematic** core — with no parasitics at all — reproduces the
"extracted" −2.54 … −2.59 LSB at hold 1 to within 0.003 LSB, and both arms
collapse onto ≈ −1.99 … −2.01 LSB by hold 2. The endpoint is simply not
settled one conversion after a ~1022 LSB step, so the −0.55 LSB cannot be a
post-layout effect. The schematic bench's own deck header anticipates exactly
this: it argues its largest 126 LSB step leaves 126·e⁻¹⁰ ≈ 0.006 LSB of
residual — an argument that does not survive a 1022 LSB step on the same
1000 ns conversion budget.

**Consequence for #53**: the adjudicating post-layout number is
−2.008 … −1.992 LSB, **+0.006 LSB** from schematic — i.e. the drawn top-plate
/ interconnect parasitic adds **no measurable systematic gain error** on top
of the schematic's ≈ −2.00 LSB DR-0012 term, the opposite of what the
superseded record said. Full record, per-hold tables and reproduce commands:
[`sim/adc-inl-dnl/records/20260805-224500-2c21be4.md`](../../../sim/adc-inl-dnl/records/20260805-224500-2c21be4.md).

## Monte Carlo on the extracted core (issue #89 Scope item 2)

Scope item 2 asks for the #14 Monte Carlo re-run "**if** the extraction flow's
parasitic/mismatch models support statistical variation — state explicitly if
not". That question has two halves with two different answers, so
`mc_extracted_core.py` **measures** both rather than asserting either.
§5 of `sim/extracted-delta-summary.md` (PR #97) answered the capacitor half
and deferred the MOS half; this closes the MOS half.

**MOS device mismatch: SUPPORTED, and demonstrated.** `klt extract --pdk
gf180mcuD` writes every FET as a real PDK subcircuit call, so the PDK's own
`sw_stat_mismatch` switch reaches all ~296 of the extracted core's FETs
exactly as it reaches the schematic core's. The script turns that switch on
and runs a real population of full transistor-level conversions on the
extracted core at transition 256 (the array's worst carry), with a
**mandatory mismatch-off null control** — `sim/device-mismatch-mc/`'s header
records three ways an ngspice Monte Carlo silently collapses to a frozen draw
and reports σ ≈ 0 while looking healthy, so a run whose population is not
varying **fails** here instead of being recorded. Three such traps were in
fact walked into and are recorded in the evidence record rather than quietly
fixed.

**CDAC capacitor mismatch: NOT supported — on EITHER netlist, and not because
of the extraction.** `sim/tools/pdk_mismatch_audit.py`'s `cap-local-mismatch`
finding (re-asserted by the script *before* it simulates anything, so a PDK
revision changes this answer rather than leaving a stale sentence behind) is
that gf180mcu models capacitor statistics only through the die-global
`sw_stat_global`, which cancels exactly in a capacitor ratio and therefore
contributes no CDAC INL/DNL by construction. The extracted MiM caps bind to
the same `cap_mim_2f0_m4m5_noshield` subckt with the same absent local term.
Re-running `sim/mc-cdac-mismatch/`'s behavioural deck against the extracted
netlist would resimulate the same literature coefficient against capacitors
that still have no statistical model — a new record with no new information.

**Result** (`tt`, 27 °C, 3.30 V, transition 256, N = 120 draws): mismatch-on
σ **1.99e-3 LSB** (mean +0.48656 LSB, range +0.48219 … +0.49258), against a
12-draw mismatch-off null control whose σ is exactly 0 from a single distinct
draw. MOS local mismatch is therefore a ~2e-3 LSB (1σ) term at the array's
worst carry — about 5 % of that transition's own ≈ 0.10 LSB DNL, and three
orders inside the < 1 LSB bound. Full record, the corner-subset
justification, and the three numerical traps:
[`records/20260805-extracted-core-mc.md`](records/20260805-extracted-core-mc.md).

## Power: a four-way split, not five (issue #89, `sim/extracted-delta-summary.md` §4.7)

The #13 power deck was the last of the three spec-line decks to port, and the
only one that needed a **methodology decision** first rather than just a
generator. Its claim is a per-block supply decomposition — five separately
measured sources (`vddc` comparator, `vddd` CDAC bottom-plate drivers, `vddt`
DR-0014's top-plate V_cm switch, `vrefs`, `vcms`) — and the core swap replaces
one of those blocks.

**The drawn layout has one supply rail.** The extracted `.SUBCKT ADC_TOP`
exposes a single `vdd` pin, and the parasitic network on it is a lone pin-stub
`Rvdd`/`Cvdd` pair with every device hung directly off the pin node. There is
no internal `vdd` segmentation to tap, and inserting an ammeter *inside* the
extracted subckt would mean editing extraction output — which the remediation
methodology above deliberately does not do beyond the two documented rewrites.

So `gen_extracted_power_tb.py` reports a **four-way** split and says so in its
own deck header: `p_cdac_*` carries the merged CDAC + top-plate-switch
current, `p_trk_*` reads exactly 0 by construction, and `p_total_*` — the
spec-line row — is untouched, because the manifest's own expression already
sums all five sources. The reported breakdown is coarsened; the claim is not.
The like-for-like block comparison is made by summing the same two columns on
*both* sides (`schematic_vs_extracted.py --sum`, added for this case).

**Result** (27-point `tt`/`ss`/`ff` grid, 27/27 PASS, record
[`sim/adc-power/records/20260806-083932-faebccc.md`](../../../sim/adc-power/records/20260806-083932-faebccc.md)):
the merged CDAC + top-plate rail costs **+6 … +12 %** post-layout (~4 µW on a
~180 µW converter, worst corner `ff_-40c_3.63v` on both sides), and
`Power @ 1 MS/s < 1 mW` **PASSES at 267.3 µW worst** — 3.7× inside the bound
and inside the < 500 µW stretch target.

**One outlier, diagnosed rather than absorbed.** At `tt_125c_3.63v`, full
scale, the comparator supply term doubles (109.4 → 225.0 µW, +105.7 %) against
−1.33 … +0.98 % at the other 26 corners. `probe_power_cmp_anomaly.py` re-runs
the same deck at that corner against **both** cores with per-conversion
instrumentation: it is not a measurement-window artefact, not the static
preamp bias (a fixed 10 µA source in both arms — the excess is dynamic, peak
draw +39 %), and it *is* attributable to the extracted core — the schematic arm
reaches the same top code 1023 at the same corner and draws a normal −29.9 µA,
while the extracted arm walks into 1023 one conversion earlier and stays there
drawing 2×. Full record:
[`records/20260806-power-cmp-anomaly.md`](records/20260806-power-cmp-anomaly.md);
escalation and what remains unexplained: `sim/extracted-delta-summary.md` §7.2.

**Still open after this increment (issue #89)**: **rate closure**. The
DR-0012/13 gain-error row that this paragraph used to pair with it is
**closed** — measured and PASSING post-layout (`tp_inj_signal_dep_lsb`, 27/27,
~307× inside the ≤ 0.5 LSB bound on the in-path extraction,
`sim/extracted-delta-summary.md` §4.9 / §6.3). The earlier reading here — that it was structurally blocked because
`sim/dr0014-sampling/` instantiates `adc_cdac_side` as a bare leaf subckt that
was never drawn or extracted as its own GDS — is **superseded**: the flat
`ADC_TOP` extraction *is* the union of exactly the cells Groups A/C isolate
(2 × `adc_cdac_side` + 2 × `adc_tp_sw` = 296 FETs, matching the extracted
device count recorded above), so one `Xdut ADC_TOP` per DR-0014 probe pair
gives each pair a real post-layout array side, and the measured quantity is an
instantaneous charge-injection voltage snapshot rather than a resistive or
RC-settling one.

Rate closure stays open for a different, structural reason: this extraction
places **no resistance in any signal path** (§"What the parasitics model, and
what they do not" above; `sim/extracted-delta-summary.md` §1.4/§4.8/§6.3), and
`R_WORST_BIT_OHM`/`C_WORST_BIT_F` — two of `sim/timing-budget-closure/`'s three
input constants — are settling-network quantities, while the third
(comparator regeneration delay, `T_COMP_REGEN_NS`) is blocked by §6.4's
`ADC_BLOCK` defect; that deck is itself a fully synthesized rung-1 composition
with no netlist to swap at all. The one sub-piece named as tractable without
new layout (the Input-structure R_on re-take, `adc_tgate` only) is **done**,
since `adc_tgate.gds` **is** a standalone leaf cell: extracted and run over the
45-point `mos` grid, 45/45 PASS on both sides with 0 of 1125 result cells
different (`sim/extracted-delta-summary.md` §4.8) — and that null is what
generalises the blocker past Group D. Also still open: comparator-inclusive
Monte Carlo on the extracted `ADC_BLOCK`, and the device-level mechanism behind
the power outlier above. Each is itemised with its blocker and compute cost in
`sim/extracted-delta-summary.md` §6 / §7.2 (the power outlier's mechanism is
issue #107).
