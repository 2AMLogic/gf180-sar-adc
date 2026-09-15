# `layout/sar-logic/` — the SAR sequencer, placed and routed

`design/sar-logic/flow/synth_sar_ctrl.py` (issue #272) already synthesized
`design/sar-logic/rtl/sar_ctrl.v` to a `gf180mcu_fd_sc_mcu7t5v0` gate-level
netlist (`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`,
181 cell instances). This directory takes that netlist through `klt
place-and-route` (DR-0023 follow-on (b), issue #274) and answers the
question `layout/adc-top/README.md` §2.4/§3 deferred: does the sequencer fit
the region that layout already reserved and rings for it?

## The one command

```sh
export PDK_ROOT=~/.ciel     # or GF180_PDK_PATH -- must resolve gf180mcuD
python3 layout/sar-logic/build.py               # run both attempts below
python3 layout/sar-logic/build.py --explicit-only    # only the `fit` attempt
python3 layout/sar-logic/build.py --reference-only   # only the `reference` attempt
```

It drives the netlist through `klt place-and-route` (OpenROAD under the
hood: floorplan -> global/detailed placement -> clock-tree synthesis ->
global/detailed routing) **twice**, each answering a different half of the
question:

1. **`fit`** — an `"explicit"` floorplan pinned to the reserved region's own
   *live* interior box, read directly off `layout/adc-top/gen_adc_top.py`'s
   constants and `layout/adc-top/area.json` (never hand-copied — see
   `build.py`'s own `_reserved_footprint_um()`). Does the netlist fit the
   shape layout already carved out, as drawn, with no floorplan change?
2. **`reference`** — a generous 50%-utilization floorplan, square aspect
   ratio. How much area would a comfortably-routable implementation of this
   netlist actually need, independent of the reserved region's shape?

Per this repo's append-only evidence rule, a documented *failure* of either
attempt is a complete, valid outcome — this script does not retry with a
looser floorplan to make a result pass, and does not touch
`gen_adc_top.py`'s own `SAR_RESERVED_W`/`SAR_RESERVED_H` constants.

## Result (record [`records/20260915-002842-07505c9.md`](records/20260915-002842-07505c9.md))

| Attempt | Floorplan | `stage_reached` | Die area | Utilization | `klt drc` |
|---|---|---|---|---|---|
| `fit` | explicit, pinned to the reserved 199.21 x 40.00 µm box | `route` | 7,968.40 µm² | 85.1% | clean |
| `reference` | 50% utilization, square | `route` | 12,014.40 µm² | 57.5% | clean |

**The netlist fits the reserved footprint as drawn.** Both attempts reach a
fully routed DEF with zero setup/hold/antenna/route-DRC violations from
OpenROAD's own checks, and a clean, independent `klt drc` (`gf180mcu` deck —
the same deck and invocation shape `layout/drc/run_drc.py` uses for every
other cell in this repository) pass over each attempt's own merged GDS.

Committed artifacts: `sar_ctrl_fit.{def,gds,pnr.v}` /
`sar_ctrl_reference.{def,gds,pnr.v}`, plus the full `klt place-and-route`
request/response payloads under `reports/`. See the record above for
per-attempt PDN notes, informational (non-signoff) timing/power numbers, and
toolchain provenance.

## What this does not establish

Not signoff timing — DR-0023's timing-closure follow-on (c) is a separate,
already-completed issue (#275 / PR #278). Not a composed layout: this
macro's `vdd`/`vss`/`clk`/... pins are not wired into `layout/adc-top/`'s
own analog-domain rails, and that composition is not attempted here. Not a
change to the reserved footprint itself — both attempts implement *against*
it or independently of it, never redefine it.

## OpenROAD

`klt place-and-route` shells out to an `openroad` binary. There is no
Homebrew formula and no common Linux-distro package for it, so
[`../openroad_docker.sh`](../openroad_docker.sh) presents the pinned ORFS
Docker image as if it were a native `openroad`; `build.py` puts a shim onto
`$PATH` only when no native `openroad` binary is already there (a real
local install always wins). The pin:

| | |
|---|---|
| Image | `openroad/orfs:latest` |
| Digest | `sha256:ee88641037a1c8e3403203bdca2b6256bf44a7957fa26719c8463ba638d76f9d` |
| `openroad -version` inside it | `26Q3-2056-g41a28926b9` |

The wrapper bind-mounts the working directory **and** the resolved PDK root
at their own absolute host paths (`OPENROAD_DOCKER_MOUNT` overrides the
former; `GF180_PDK_PATH`/`PDK_ROOT`/`~/.ciel`/`~/.volare`, in that order,
resolve the latter), because `klt place-and-route`'s generated Tcl carries
absolute paths for the netlist, the LEF/liberty deck and every output —
source == target is what makes those resolve identically on both sides of
the container boundary.

## `klt` version

`klt place-and-route` needs table entries for `gf180mcu_fd_sc_mcu7t5v0`
(clock-buffer, routing-layer, tapcell, power-pin patterns) that only landed
upstream at
[klayout-tools#1653](https://github.com/2AMLogic/klayout-tools/pull/1653)
("fix(place-and-route): add gf180mcu_fd_sc_mcu7t5v0 table entries", merged
2026-09-11, commit `5826244d`). The repo-wide `layout/toolchain.json` pin
(`85b8125`) predates both `place-and-route` and `synthesize` and covers only
`drc`/`extract`/`lvs`; it was not bumped for this directory. Install a `klt`
at or past `5826244d` explicitly, e.g.:

```sh
uv tool install --force "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@5826244def4b8d093b2a9cc444db414c67d4ca91"
```
