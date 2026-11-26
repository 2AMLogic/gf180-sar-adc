# layout/adc-top/sar_ctrl/ — the SAR-logic sequencer's placed-and-routed macro

Issue #274 (DR-0023 follow-on (b)). This directory holds the **placed and
routed** digital macro for the SAR-logic sequencer — the physical
implementation of `design/sar-logic/rtl/sar_ctrl.v`'s `sar_ctrl_a`, one
step past issue #272's synthesized gate netlist
(`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`).

Unlike every other cell under `layout/adc-top/`, this macro's "source" is
not hand-placed KLayout primitives — it is `klt place-and-route`
(OpenROAD's native Tcl API) driven from the synthesized netlist plus a
fixed request document. The **reviewable source** is
[`design/sar-logic/flow/pnr_sar_ctrl.py`](../../../design/sar-logic/flow/pnr_sar_ctrl.py)
(the driver script) and the request/response JSON it writes under
[`design/sar-logic/flow/sar_ctrl/reports/`](../../../design/sar-logic/flow/sar_ctrl/reports/)
— the files in *this* directory are that run's output, exactly the same
"generated, not hand-edited" convention the rest of `layout/adc-top/`
follows for its own `.gds`/`.spice` pairs.

```
layout/adc-top/sar_ctrl/
  sar_ctrl.gds   merged, routed GDS (DEF + standard-cell GDS views, KLayout pya, in-process)
  sar_ctrl.def   routed DEF (OpenROAD's own write_def)
  sar_ctrl.v     as-built gate-level Verilog (CTS buffers/resizes/fillers/tapcells included --
                 NOT byte-identical to design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v)
```

## Reproduce

```bash
python3 design/sar-logic/flow/pnr_sar_ctrl.py
```

Requires `klt`/`openroad` on `$PATH` and the gf180mcu PDK resolvable the
same way `sim/harness/pdk.py` resolves it everywhere else in this repo
(`docs/environment-setup.md` §4). `openroad` has no apt/pip package — see
`klayout-tools`' `docs/cli/place-and-route.md` "Installing OpenROAD" for
the Docker-wrapper recipe this macro's own evidence record was produced
with.

## What is and is not claimed

**Verified, by a committed record** (the driver script's own evidence
record under
[`design/sar-logic/flow/sar_ctrl/records/`](../../../design/sar-logic/flow/sar_ctrl/records/),
named `<rid>.mcu7t5v0.pnr.md`):

* the routed macro **fits** the reserved SAR-logic footprint
  `layout/adc-top/gen_adc_top.py` carves out and rings, at zero floorplan
  margin — `target_stage: "route"` reached `status: "ok"` inside an
  EXPLICIT floorplan sized to exactly that footprint's current
  ring-exclusive core box (see `../README.md`'s "Area, as drawn" section,
  issue #274 update, for why that box is 199.21 × 40.0 µm and not the
  7,624 µm²-derived box the issue that filed this work originally cited);
* `route_drc_violation_count: 0` and `antenna_violation_count: 0`
  (OpenROAD's own TritonRoute/antenna checks);
* `klt drc --deck gf180mcu` against the merged GDS in this directory
  (klt 0.7.1.dev531, deck `sha256:9babf6fd...`): **208 violations**, all
  library-cell geometry (`nplus.space.pcomp.1` and `pplus.enclosing.comp.1`
  = 104 each, sourced from the PDK `endcap`, `filltie`, `fill_1`, `fill_2`
  cells). The pre-repair GDS from `main` gives the same 208 with the same two
  rules under this klt, so the supply repair (issue #485) added **no** new
  violations; an earlier version of this README recorded "clean, 0
  violations" under an older klt/deck that this build does not reproduce.
  Macro DRC is therefore **not clean** and is not claimed clean. Issue #520
  classified the 208 (record
  [`20261015-230646-1dbc6282.mcu7t5v0.cell_drc.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261015-230646-1dbc6282.mcu7t5v0.cell_drc.md)):
  the same two rules fire on the unmodified PDK `endcap` and `filltie` cells
  checked alone (8 markers each; deck `sha256:9babf6fd...`, klt
  0.7.1.dev515), whose 0.08 um Pplus/Nplus margin to the substrate tap is below
  the deck's flat 0.16 um but inside the relaxed band the deck's own notes say
  it cannot evaluate. This is a deck over-approximation scoped to those PDK
  cells, not a P&R defect; it is **not** confirmed against the foundry deck. The same
  curated deck `layout/drc/run_drc.py` exercises over every other cell in
  this directory is run directly against this macro's GDS rather than folded
  into that runner's own `cells/cells.json` manifest (that manifest is
  sha256-pinned, hand-authored-expected-violation-count infrastructure
  built around the full-custom analog cells; wedging a P&R-generated macro
  into it is a bigger, separable piece of work);
* **Supply connectivity (issue #485).** The PDN is Metal1 `followpins` plus
  one VDD and one VSS vertical Metal4 strap (x = 20 um and 160 um), each
  joined to the row rails by `pdngen`'s Metal1-Metal4 via stack. The
  transistor-level LVS runner
  [`layout/lvs/run_sar_ctrl_lvs.py`](../../lvs/run_sar_ctrl_lvs.py) compares
  this GDS to a golden built from the unmodified `sar_ctrl.v` and the PDK
  circuits and reports `match` (1852 devices, 961 nets, one `VDD` and one
  `VSS` pin net), with the gate-level `power_connectivity` also `match`. A
  geometry-edited copy with the Metal4 straps deleted is `mismatch` in both
  modes. The dated record is under
  [`layout/lvs/sar_ctrl/records/`](../../lvs/sar_ctrl/records/) (latest
  `20261015-*`; the earlier `20261009-*` record is the pre-repair `mismatch`).
  No netlist hand-short is involved.

**Not verified, and not claimable here:**

* **Signoff LVS.** The macro-level compare above is a match against a
  golden derived from the macro's own routed netlist; it is not cited in
  `signoff/gf180-sar-adc.manifest.json` (item 4.digital / 11.digital stay
  uncited) and the analog block's LVS is not substituted. Whether the
  single transistor-level `VSS` net is carried by metal or only by the
  substrate is not isolated (klayout-tools#2971).
* **Timing closure, by the P&R run itself.** `constraints.clock_period_ns`
  in the request this macro was routed against (62.5 ns / 16 MHz,
  `spec/timing-budget-memo.md`'s DR-0008/DR-0003 nominal SAR clock) is
  present only because `klt place-and-route` requires *a* clock once past
  the floorplan stage. It is deliberately generous, not a signoff target,
  and the P&R record makes no timing claim. Timing for this routed macro
  is the subject of a separate record, described below.
* **Composition into `adc_top.gds`/`adc_block.gds`.** This macro is a
  standalone artifact, physically separate from the analog block's own
  top-cell GDS. Merging the two (`klt place-and-route`'s own
  `request.macros` hard-macro-placement field, or an equivalent top-level
  GDS assembly step) is not this issue's scope.

## Timing of the routed macro (separate, later record)

> **Stale geometry (issue #485).** The STA and SPEF records below describe the
> PRE-repair `sar_ctrl.def`/`.gds` (no Metal4 straps). The supply repair
> regenerated those artifacts; re-timing them is separate work and has not
> been done.

DR-0023 follow-on (c) (issue #275) has since timed this macro's committed
routed DEF. The dated record of that run is
[`design/sar-logic/flow/sar_ctrl/records/20260915-093934-7ab8971.mcu7t5v0.sta_postroute.md`](../../../design/sar-logic/flow/sar_ctrl/records/20260915-093934-7ab8971.mcu7t5v0.sta_postroute.md).
It supersedes the pre-route, placement-estimate record
`20260914-235615-7022eab.mcu7t5v0.sta.md`. The record measured the
following:

* `klt sta` (klt 0.4.0) ran against the one fixed `sar_ctrl.def` in this
  directory, which was not re-placed per corner. The constraint was
  `create_clock -period 62.5000` on `clk`, the DR-0003 16 MHz clock.
* It covered five `gf180mcu_fd_sc_mcu7t5v0` library corners: the three
  DR-0023 names (`tt_025C_3v30`, `ss_125C_3v00`, `ff_n40C_3v60`) plus
  `ss_n40C_3v00` and `ff_125C_3v60`.
* Setup and hold **PASS** at all five corners. Worst setup slack is
  +56.3650 ns (`ss_125C_3v00`) and worst hold slack is +0.6512 ns
  (`ff_n40C_3v60`).

The record discloses these limits. The first no longer applies to this macro's
cited evidence (see "Bounded claim" below); the second still does:

* **No extracted SPEF.** That record's slack includes no wire parasitics at
  all, only Liberty pin capacitance. The record itself says OpenSTA
  "estimated RC from the DEF geometry", but the `klt sta` script it ran has
  no RC-estimation step. Issue #481's record (below) corrects this and shows
  a same-toolchain re-run reproduces the record exactly. The record judges
  that the margins are wide enough that missing parasitics are unlikely to
  flip the verdict, but states that this is a judgment, not a proof. Lifted
  for this macro by the SPEF receipts below (issue #1028): wire capacitance
  from an extracted SPEF is now annotated at all five corners.
* **Ideal clock.** The clock is an ideal SDC clock, not a propagated one.
  `klt sta` has no propagated-clock mode (klayout-tools#2739, open).
  `fmax_mhz` is OpenSTA's extrapolation, not a bisected value.

Issue #481 attempted to close the SPEF limit. The attempt is recorded at
[`design/sar-logic/flow/sar_ctrl/records/20261009-131918-bf22e71c.mcu7t5v0.sta_postroute_spef.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261009-131918-bf22e71c.mcu7t5v0.sta_postroute_spef.md)
(`sta_sar_ctrl_postroute.py --spef`). It extracted a SPEF from this
directory's GDS with `klt extract` and ran `klt sta` with it at the same five
corners. The annotation gate **rejected every corner**, so the "No extracted
SPEF" limit still stands, and that record does not supersede the one above.
The reason is a known extractor gap (klayout-tools#2880). Eleven timed nets
have a top-level pin whose name differs from the net (`c0`..`c9` on
`c0_r`..`c9_r`, and `drdy` on `ph[15]`). OpenSTA drops all of their
parasitics, and the floating outputs of the two CTS dummy loads have none.
That record also gives the partially annotated slack movement, but it is not
a timing result. Its negative controls show the gate rejects a dropped net, a
renamed net, and a SPEF that annotates nothing.

**Retry (issue #486, 2026-10-16): still REJECTED at all five corners.**
Upstream klayout-tools#2880 closed after PR #3512 (SPEF ports named by DEF PIN,
floating duplicate nets skipped), and the `klt` used here
(`0.7.1.dev1440+gbc4f028aafd6`) is 650 commits past that merge. The rerun is
[`design/sar-logic/flow/sar_ctrl/records/20261016-173027-b36376fe.mcu7t5v0.sta_postroute_spef.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261016-173027-b36376fe.mcu7t5v0.sta_postroute_spef.md),
on the current `sar_ctrl.def`/`.gds` (DEF sha256 `96c8e30a...`), so it is not
the stale pre-repair geometry. The alias gap is closed: all 192 design nets are
annotated and `c0`..`c9`/`drdy` are written as `*P c0` with a `c0_r:1` hub. The
strict gate still rejects, because `annotation_complete` is false: 2 drivers
(the CTS dummy-load outputs) have no parasitics, 11 drivers are partially
unannotated, and 2 intra-cell labels (`Z`, `ZN`) draw STA-1650. The gate was
not relaxed, the three negative controls still reject their specific defects,
and the clock is still ideal (klayout-tools#2739 is closed, but the installed
`klt sta` exposes no propagated-clock option, so that mode was not run). The record's
boilerplate that calls the port-name gap "open" predates the fix and is
superseded by this paragraph. The remaining upstream gaps are tracked in
klayout-tools#3662. The "No extracted SPEF" limit above still stands, and
`20260915-093934-7ab8971` remains the cited bounded evidence.

**Second retry (issue #486, 2026-10-16, after klayout-tools#3662 closed):
still REJECTED at all five corners, with a smaller gap.** The `klt` used is
`0.7.1.dev1525+g973b3242904a`, 38 commits past the #3663 merge that closed
#3662. The rerun is
[`design/sar-logic/flow/sar_ctrl/records/20261016-201820-0d4bba91.mcu7t5v0.sta_postroute_spef.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261016-201820-0d4bba91.mcu7t5v0.sta_postroute_spef.md),
on the same `sar_ctrl.def`/`.gds`. All 192 design nets are annotated, there are
no reader warnings, and the `Z`/`ZN` intra-cell label warnings are gone. What
remains is 2 unannotated drivers (`clkload0/Z`, `clkload1/ZN`, the CTS
dummy-load outputs, which have no DEF net), so `annotation_complete` is still
false. The 11 partially unannotated drivers are reported but do not gate. The
gate was not relaxed, the three negative controls still reject their specific
defects, and the clock is still ideal. The remaining gap is tracked in
klayout-tools#3669. The "No extracted SPEF" limit above still stands.

**Third retry (issue #486, 2026-10-16, after klayout-tools#3668/#3669
closed): still REJECTED at all five corners, but the cause is now a gate
question.** The `klt` used is `0.7.1.dev1600+g786dd097e1db`, a throwaway
build of klayout-tools `main` at `786dd097e` (not a release and not a host
install), because the host `klt` (`dev1588`) lacks the #3673 fix. The rerun is
[`design/sar-logic/flow/sar_ctrl/records/20261016-231433-2f9469f7.mcu7t5v0.sta_postroute_spef.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261016-231433-2f9469f7.mcu7t5v0.sta_postroute_spef.md),
on the same `sar_ctrl.def`/`.gds`. klt itself now reports
`annotation_complete: true` with 192/192 nets annotated and the 2 dummy-load
outputs (`clkload0/Z`, `clkload1/ZN`) classed as `floating_driver_count: 2`.
This repository's own gate (`spef_audit.py`, `unannotated_driver_count > 0`)
still counts them and rejects. It was **not** relaxed here: treating
floating-only unannotated drivers as acceptable is a gate change that needs
its own decision. The 11 partially unannotated drivers are the port-alias
flops and do not gate. Negative controls still reject their specific defects,
the clock is still ideal, and the "No extracted SPEF" limit above still
stands.

**Fourth run (issue #486, 2026-11-04, after DR-0040): 5 of 5 corners pass the
annotation gate, as a qualification run only.** DR-0040 lets the gate exempt
an unannotated output only when klt calls it floating *and* an independent
DEF/Verilog/Liberty proof finds it on no net (`clkload0/Z`, `clkload1/ZN`).
The run used `klt 0.8.0` from a throwaway `klayout-tools==0.8.0` environment
against the same `sar_ctrl.def`/`.gds`. Record:
[`design/sar-logic/flow/sar_ctrl/records/20261104-195336-b4950aa2.mcu7t5v0.sta_postroute_spef.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261104-195336-b4950aa2.mcu7t5v0.sta_postroute_spef.md).
Limits that still apply: the working tree was **dirty** at run time (the record
says so), the clock is still ideal, there is one nominal extraction, and the
stale-geometry note above still applies. It is not timing closure, so
the "No extracted SPEF" limit above stands and `20260915-093934-7ab8971`
remains the cited bounded evidence until a clean-tree re-run is accepted.

**Clean-tree re-run (issue #486, 2026-11-04):** the same `klt 0.8.0` pin, run
from a clean checkout at `9cde5a64`, reproduced the fourth run byte for byte
(identical SPEF sha256 and identical setup/hold at all five corners, 5 of 5
annotation-gate accepts, three negative controls rejecting). Record:
[`design/sar-logic/flow/sar_ctrl/records/20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_spef.md`](../../../design/sar-logic/flow/sar_ctrl/records/20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_spef.md).
This removes only the dirty-tree caveat. The ideal clock, the single nominal
extraction and the missing wire resistance (lumped-star model) still apply, so
this is not timing closure.

**Bounded claim (issue #1028, 2026-11-26; closes #486 per the operator ruling
of 2026-11-26).** From both receipts above, the routed macro's timing is
**SPEF-annotated, ideal clock, lumped no-R extraction, 5 corners met
(setup/hold, 0 violators); not propagated-clock or RC closure.** The
qualification receipt
[`20261104-195336-b4950aa2`](../../../design/sar-logic/flow/sar_ctrl/records/20261104-195336-b4950aa2.mcu7t5v0.sta_postroute_spef.md)
and the clean-tree re-run
[`20261104-212437-9cde5a64`](../../../design/sar-logic/flow/sar_ctrl/records/20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_spef.md)
agree on every number (same SPEF sha256 `9167446e...`, same slack at all five
corners). SPEF run at the ratified 62.5 ns clock, with the change against the
same-toolchain unannotated reference:

| Corner | Setup slack (ns) | Hold slack (ns) | Setup/hold violators | Setup delta vs. no SPEF (ns) | Hold delta vs. no SPEF (ns) |
|---|---|---|---|---|---|
| `tt_025C_3v30` | +59.1114 | +1.2665 | 0/0 | -0.3677 | +0.1200 |
| `ss_125C_3v00` | +55.6796 | +2.5436 | 0/0 | -0.6854 | +0.2241 |
| `ff_n40C_3v60` | +60.5632 | +0.7250 | 0/0 | -0.2246 | +0.0738 |
| `ss_n40C_3v00` | +57.6609 | +1.7964 | 0/0 | -0.5092 | +0.1653 |
| `ff_125C_3v60` | +59.7972 | +1.0120 | 0/0 | -0.2960 | +0.1024 |

Worst setup slack is +55.6796 ns (`ss_125C_3v00`) and worst hold slack
+0.7250 ns (`ff_n40C_3v60`). Wire capacitance costs 0.22 to 0.69 ns of setup
slack per corner and adds 0.07 to 0.22 ns of hold slack. What the claim does
not cover:

* **Ideal clock**, as above.
* **One nominal extraction, lumped star with no wire resistance** between
  driver and loads. It is evidence about wire capacitance, not RC closure: no
  RC corners, no distributed wire R (klayout-tools#2858).
* **Unconstrained endpoints.** The request sets no I/O delays, as the baseline
  did not: the 67 output ports are unconstrained endpoints and the 3 non-clock
  inputs (`cmp`, `mode`, `start`) are unconstrained startpoints. Only
  register-to-register paths are timed.
* **Stale geometry (issue #485)**, as above: the receipts time the pre-repair
  `sar_ctrl.def`/`.gds`.

**AC 2 reconciliation: the eleven aliased timed nets.** #486 AC 2 requires
"the eleven aliased timed nets receive parasitics, audited pin mappings
agree". Both receipts report **11 partially unannotated drivers** at every
corner, so that had to be reconciled before the claim above cites them. It is:
the eleven are the same nets, and each one carries its extracted parasitics.

| Timed net | Port alias | Driver | Timed load | `*D_NET` cap (fF) | Reader wire cap (fF) | Pin the reader flags |
|---|---|---|---|---|---|---|
| `c0_r` | `c0` | `_211_/Q` | `_175_/I0` | 4.296 | 4.30 | `c0` |
| `c1_r` | `c1` | `_212_/Q` | `_178_/I0` | 3.577 | 3.58 | `c1` |
| `c2_r` | `c2` | `_213_/Q` | `_179_/I0` | 4.084 | 4.08 | `c2` |
| `c3_r` | `c3` | `_214_/Q` | `_188_/I0` | 6.216 | 6.22 | `c3` |
| `c4_r` | `c4` | `_215_/Q` | `_191_/I0` | 5.269 | 5.27 | `c4` |
| `c5_r` | `c5` | `_216_/Q` | `_192_/I0` | 3.757 | 3.76 | `c5` |
| `c6_r` | `c6` | `_217_/Q` | `_197_/I0` | 4.057 | 4.06 | `c6` |
| `c7_r` | `c7` | `_218_/Q` | `_198_/I0` | 4.718 | 4.72 | `c7` |
| `c8_r` | `c8` | `_219_/Q` | `_171_/I0` | 4.325 | 4.32 | `c8` |
| `c9_r` | `c9` | `_220_/Q` | `_172_/I0` | 3.913 | 3.91 | `c9` |
| `ph[15]` | `drdy` | `_245_/Q` | `_170_/A2` | 7.798 | 7.80 | `drdy` |

Each column answers a different question:

* **Pin mappings agree.** These are the only eleven DEF nets whose top-level
  PIN is named differently from the net, the only eleven `assign` aliases in
  the routed Verilog, and the eleven nets the October 9 audit names as on a
  timed register path. Both SPEFs write `*P <alias>`, `*I <driver>` and
  `*I <load>` for each, and the static audit finds no error.
* **Extracted capacitance.** The `*D_NET` header of each net carries the
  capacitance shown, in both SPEFs. This is what the extractor wrote.
* **The reader kept it.** At all five corners of both receipts, 192 of 192
  design nets are named, the reader discards no record (0 warnings; in October
  it discarded 524 records on exactly these nets) and `delay_changed` is true.
  That is run-wide. Per net, OpenSTA's `report_net` gives the wire
  capacitance shown, equal to the `*D_NET` value.
* **"Partially unannotated" is the port pin, not the net.** For each net the
  reader lists the driver and exactly one pin it holds no parasitic for: the
  DEF top-level pin, which is this macro's output port. The port has no pin
  capacitance of its own. The net's lumped wire capacitance is attached, and
  the timed load hangs on that net. Every output port is an unconstrained
  endpoint, so the flagged pin is on no timed path.

The two DR-0040 exemptions are separate and unchanged: the only unannotated
drivers are `clkload0/Z` and `clkload1/ZN`, the CTS dummy-load outputs that the
independent DEF/Verilog/Liberty proof puts on no net.

The receipts retain only the first 20 lines of the reader's listing, which
covers ten drivers and cuts the eleventh. The full listing and the per-net
capacitance come from a single-corner reader probe,
[`20261126-070556-780bae77.mcu7t5v0.sar_ctrl.spef_reader_probe_tt.json`](../../../design/sar-logic/flow/sar_ctrl/reports/20261126-070556-780bae77.mcu7t5v0.sar_ctrl.spef_reader_probe_tt.json)
(re-run from its [`.tcl`](../../../design/sar-logic/flow/sar_ctrl/reports/20261126-070556-780bae77.mcu7t5v0.sar_ctrl.spef_reader_probe_tt.tcl)).
It is reader accounting, not a receipt: it ran on host tools (`klt
0.9.3.dev5631`, not the pinned 0.8.0) against the committed DEF, SPEF and TT
request, on the OpenROAD build the receipts used (`26Q3-1510-g6cb3f2b704`).
It reproduces the TT corner's annotation fields and slack.
`sim/tests/test_sta_postroute_spef_record.py` re-derives both tables above from
the committed DEF, Verilog, SPEFs, receipts and probe.

Both committed November records were rendered before the record renderer was
fixed. Their summary lines read "every corner is rejected ... exits 1" beside
"5 of 5 corners passed", which is wrong for them: every corner is accepted and
every negative control detected its defect, so the driver's exit logic gives 0,
and each audit JSON records `verdict: ACCEPTED`. Records are append-only, so
they are not re-rendered; re-rendering either audit now prints "exits 0"
(tested).

This is bounded timing evidence, not full digital signoff. LVS and
composition into `adc_top`/`adc_block` (both listed above) are still not
done. The gate-level SPICE functional/timing replay over the PVT grid is a
separate check from STA, and its open items are tracked in
[`design/sar-logic/rtl/README.md`](../../../design/sar-logic/rtl/README.md).
This STA record does not resolve them.
