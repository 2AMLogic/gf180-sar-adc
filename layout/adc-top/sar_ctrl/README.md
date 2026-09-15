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
* `klt drc --deck gf180mcu` against the merged GDS in this directory:
  **clean**, 0 violations — the same curated deck
  `layout/drc/run_drc.py` exercises over every other cell in this
  directory, run directly against this macro's GDS rather than folded into
  that runner's own `cells/cells.json` manifest (that manifest is
  sha256-pinned, hand-authored-expected-violation-count infrastructure
  built around the full-custom analog cells; wedging a P&R-generated macro
  into it is a bigger, separable piece of work this issue did not take on).

**Not verified, and not claimable here:**

* **LVS.** Nothing in this repo yet converts `sar_ctrl.v` (or the merged
  GDS) into a form `klt lvs` can compare against a golden reference —
  `klayout-tools`' own `docs/cli/place-and-route.md` records the identical
  gap for its own gf180mcu worked example (issue klayout-tools#1336, "no
  available code path to run"). Out of this issue's scope.
* **Timing closure.** `constraints.clock_period_ns` in the request this
  macro was routed against (62.5 ns / 16 MHz,
  `spec/timing-budget-memo.md`'s DR-0008/DR-0003 nominal SAR clock) is
  present only because `klt place-and-route` requires *a* clock once past
  the floorplan stage — it is deliberately generous, not a signoff target.
  DR-0023 follow-on (c) (issue #275, SDC/STA closure) is the follow-on that
  actually derives and asserts one.
* **Composition into `adc_top.gds`/`adc_block.gds`.** This macro is a
  standalone artifact, physically separate from the analog block's own
  top-cell GDS. Merging the two (`klt place-and-route`'s own
  `request.macros` hard-macro-placement field, or an equivalent top-level
  GDS assembly step) is not this issue's scope.
