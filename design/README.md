# design — schematics and netlists

Schematic capture is xschem; simulation is ngspice via the corner runner in
[`../sim/`](../sim/harness/README.md).

```
design/
  xschemrc        repo xschem config: resolves the PDK, adds repo symbol libraries
  smoke_test.sch  environment-bootstrap smoke test (see docs/environment-setup.md)
  cdac/           CDAC array schematic (representative cells, see DR-0011)
  comparator/     comparator schematic + netlist (see DR-0007-comparator-topology.md)
  track-switch/   sample/track switch schematic (see DR-0007-track-switch-topology.md)
  sar-logic/      synchronous SAR control logic (see sar-logic/README.md)
  adc-top/        generated top-level ADC netlist + testbench-suite generator (see gen_adc_top.py)
  symbols/        repo-local .sym files (created when the first one exists)
  netlist/        xschem-generated .spice netlists (git-ignored, created on demand)
```

Not everything here is a schematic. `sar-logic/` is a **generated** ngspice
subckt library at the rung-1 abstraction of DR-0010 (ideal XSPICE digital
primitives), because the SAR controller is decided and verified as logic before
it is drawn as transistors — see [`sar-logic/README.md`](sar-logic/README.md)
for the port list, the regeneration command and the path from there to the
netlist layout and LVS will use.

## Running xschem

```bash
source sim/env.sh                              # exports PDK_ROOT / PDK / XSCHEM_USER_LIBRARY_PATH
xschem --rcfile design/xschemrc                # from anywhere
```

Always pass `--rcfile design/xschemrc` explicitly. Relying on xschem's
cwd-relative `./xschemrc` auto-discovery only works when xschem's working
directory happens to be `design/`, and a stale machine-level
`~/.xschem/xschemrc` can otherwise silently break the symbol library path —
see `docs/environment-setup.md` §2.

`design/xschemrc` finds the gf180mcu install by the same rules as the harness
(`GF180_PDK_PATH`, then `PDK_ROOT`+`PDK`, then the usual prefixes — see
`sim/harness/README.md`), sources the PDK's own xschemrc so the gf180mcu
device symbols are on the library path, and adds `design/`, `design/symbols/`
and every `sim/<experiment-slug>/testbench/`.

## Getting a schematic into the corner runner

The corner runner consumes netlist *fragments*: devices and sources only, no
`.include`, `.lib`, `.temp`, `.control` or `.end` (the harness supplies those
per PVT point). Netlist the schematic from xschem, strip any simulator
directives, and point a `sim/<experiment-slug>/testbench/tb.json` at the
result. The runner does not care whether a fragment was generated or typed by
hand.

One gotcha specific to this block: do **not** write a MIM capacitor's PDK
subckt name (`cap_mim_2f0_m4m5_noshield`) into a fragment. The metal pair in
that name is a property of the PDK variant, not of the device. Instantiate the
harness-supplied `mim_cap_1f0` / `mim_cap_1f5` / `mim_cap_2f0` aliases instead
— the harness binds them to the resolved variant's stack, so a variant switch
cannot silently leave a testbench pointing at the wrong model.
