# gf180-sar-adc

**PRIVATE — 2AM Logic proprietary IP. Canary block (wave 1).**

10-bit SAR ADC on gf180mcu (open PDK), designed by agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source analog flow. Dual purpose, per the canary model: catalog
inventory (eventually silicon-measured) and tool forcing-function
(friction issues go to the public klayout-tools tracker).

Selection rationale: sky130 existence proofs port; no free measured competitor on gf180 (matrix row 4).

## Target specification (DRAFT — engineering to ratify, see issue #1)

| Parameter | Target | Stretch |
|---|---|---|
| Resolution | 10 bit | 12 bit variant |
| Rate | 1 MS/s | 2 MS/s |
| ENOB @ Nyquist | > 9.0 | > 9.5 |
| INL / DNL | < 1 LSB | < 0.5 LSB |
| Input | 0–3.3 V single-ended + diff mode | — |
| Power @ 1 MS/s | < 1 mW | < 500 µW |
| Area | < 0.1 mm² | — |
| Interface | SPI-readable + parallel | — |

Maturity ladder: simulation-complete → layout DRC/LVS-clean → shuttle
seat → measured silicon over temperature.

## Layout

```
spec/          ratified spec + decision records
design/        schematics / netlists (xschem)
sim/           testbenches + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
docs/          environment bootstrap
```

## Simulation

```bash
# one-time environment bootstrap: docs/environment-setup.md
source sim/env.sh                            # export the resolved gf180mcu PDK
python3 sim/run_corners.py --check-env       # ngspice + PDK present?
python3 sim/run_corners.py --list            # available experiments and corners
python3 sim/run_corners.py <experiment>      # sweep the PVT grid, mint a record
bash sim/selftest.sh                         # prove the harness (and its corner
                                             # switching) actually works
```

- [`docs/environment-setup.md`](docs/environment-setup.md) — xschem + ngspice +
  gf180mcu install, with pinned versions.
- [`sim/harness/README.md`](sim/harness/README.md) — corner runner reference:
  corners, testbench manifests, corner-sensitivity guarantees.
- [`sim/README.md`](sim/README.md) — the append-only evidence-record format
  every run writes into.
