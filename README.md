# gf180-sar-adc

A 10-bit SAR ADC for **gf180mcu**, GlobalFoundries' open 180 nm PDK, designed
end to end on the open-source analog flow: [xschem](https://xschem.sourceforge.io/)
for schematics, [ngspice](https://ngspice.sourceforge.io/) for simulation, and
[KLayout](https://www.klayout.de/) — driven by
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — for layout.

**This block is designed by AI agents.** Not agent-assisted: agents pick the
topology, write the testbenches, run the corners, argue about the trade-offs in
decision records, and file the tool bugs they hit along the way. Every artifact
in this repository — the prior-art survey, the device characterization, the
simulation harness, the evidence records — was produced that way. The repo is
public so the work can be checked, not admired: every number here is traceable
to a testbench you can re-run.

## Status

Early. There is no ADC yet — there is the substrate you need before there
honestly can be one:

| Area | State |
|---|---|
| Target spec | DRAFT (table below), ratification in progress |
| Prior-art survey | Done — `spec/prior-art-survey.md` |
| Simulation harness | Working — PVT corner runner over gf180mcu, with a self-test |
| Device characterization | Done — CDAC caps, sampling switches, comparator input devices |
| Schematics | Smoke-test only (`design/`) |
| Layout | Not started |
| Silicon | None |

## Target specification (DRAFT — engineering to ratify, see issue #1)

| Parameter | Target | Stretch |
|---|---|---|
| Resolution | 10 bit | 12 bit variant |
| Rate | 1 MS/s | 2 MS/s |
| ENOB @ Nyquist | > 9.0 | > 9.5 |
| INL / DNL | < 1 LSB | < 0.5 LSB |
| Input | 0–3.3 V single-ended + diff mode, ≤ 500 Ω source impedance ([DR-0001](spec/decision-records/DR-0001-input-drive.md)) | — (source-impedance budget not resolved at this rate, see DR-0001) |
| Power @ 1 MS/s | < 1 mW | < 500 µW |
| Area | < 0.1 mm² | — |
| Interface | SPI-readable + parallel (parallel/output-register in scope for simulation-complete; SPI deferred, [DR-0005](spec/decision-records/DR-0005-interface-scope.md)) | — |

These are targets, not results. Nothing here has been measured in silicon.

## Verification is the product

The rule this repository is built around: **no claim without a testbench.**

- Every recorded result carries its PVT corners, its netlist provenance, and
  the toolchain versions that produced it.
- `sim/` is **append-only evidence**. Records are never edited or deleted; a
  superseded result is superseded by a new record that says so.
- The harness refuses to run when the toolchain drifts from its pinned
  versions, so a record cannot silently mean something different than it did
  last week.

The record format is documented in [`sim/README.md`](sim/README.md).

## Friction protocol

This block is also a forcing function for its own tooling. Every time
`klayout-tools` is awkward, missing a capability, or simply wrong for the job
at hand, that becomes an issue on the public tracker:

**[github.com/2AMLogic/klayout-tools/issues](https://github.com/2AMLogic/klayout-tools/issues)**

Friction issues describe the *tool gap* generically, not this design — so the
tool improves for everyone using the open gf180mcu flow, not just for us.

**Scope decisions (issue #7).** Five scope questions the draft table left
open are now resolved with decision records in `spec/decision-records/`
(all `proposed`, pending engineering ratification per #1):

- Input drive: [DR-0001](spec/decision-records/DR-0001-input-drive.md) — external driver required, ≤ 500 Ω source impedance, 1 MS/s only.
- Reference source: [DR-0002](spec/decision-records/DR-0002-reference-source.md) — external `V_REF` pin (3.3 V), not internal/bandgap-derived; not yet a spec-table row.
- Clocking: [DR-0003](spec/decision-records/DR-0003-clocking.md) — external clock pin, 16 MHz @ 1 MS/s (32 MHz @ 2 MS/s stretch), ≤ 250 ps rms aperture jitter; not yet a spec-table row.
- Device flavor: [DR-0004](spec/decision-records/DR-0004-device-flavor.md) — 3.3 V devices throughout (`nfet_03v3`/`pfet_03v3`), single supply, no level shifters; an implementation detail with no spec-table row.
- Interface scope: [DR-0005](spec/decision-records/DR-0005-interface-scope.md) — parallel output register in scope for simulation-complete, SPI deferred to a later maturity rung.

The DRAFT marking above is #1's to remove, not this issue's.

## Layout

```
spec/          target spec, prior-art survey, decision records
design/        schematics / netlists (xschem)
sim/           testbenches, PVT corner harness, append-only result records
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
docs/          environment bootstrap
```

## Running the simulations

```bash
# one-time environment bootstrap: docs/environment-setup.md
source sim/env.sh                            # export the resolved gf180mcu PDK
python3 sim/run_corners.py --check-env       # ngspice + PDK present?
python3 sim/run_corners.py --list            # available experiments and corners
python3 sim/run_corners.py <experiment>      # sweep the PVT grid, mint a record
bash sim/selftest.sh                         # prove the harness (and its corner
                                             # switching) actually works
```

### Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the headless half of
the above on every push and pull request: `sim/selftest.sh` stage 1 (the harness
unit tests), plus shell and Python syntax checks. It installs no PDK.

```bash
npm run check:ci    # exactly what CI runs — no ngspice, no PDK, seconds
npm run check:all   # the full sim/selftest.sh — needs ngspice + gf180mcu
npm run check:pdk   # what the nightly PDK workflow runs (--require-pdk: a
                    # missing PDK fails instead of skipping the sim stages)
```

`sim/selftest.sh` stages 2–4 (toolchain pin check, end-to-end PVT sweeps, and
the sabotaged-corner negative control) need a real PDK, so they run in
[`.github/workflows/nightly-pdk.yml`](.github/workflows/nightly-pdk.yml)
instead: nightly on a schedule, on demand, or on a pull request labelled
`ci:pdk`. That workflow builds the pinned ngspice and caches the gf180mcu
install at the pinned `open_pdks` hash, both keyed on
[`sim/toolchain.json`](sim/toolchain.json) — a pin bump re-installs rather than
reusing a stale cache. A nightly failure files (or comments on) a GitHub issue
rather than only turning the run red; a stage-4 regression — a *sabotaged*
corner sweep passing, meaning corner switching is not taking effect — is
escalated as urgent. Run stages 2–4 locally too, before recording evidence.

Neither workflow ever writes evidence: CI runs `sim/selftest.sh` without
`--record`, and asserts the working tree is unchanged afterwards. The workflow
files enumerate every self-check in the repo and where each one runs; keep that
list current when adding a check.

- [`docs/environment-setup.md`](docs/environment-setup.md) — xschem + ngspice +
  gf180mcu install, with pinned versions.
- [`sim/harness/README.md`](sim/harness/README.md) — corner runner reference:
  corners, testbench manifests, corner-sensitivity guarantees.
- [`sim/README.md`](sim/README.md) — the append-only evidence-record format
  every run writes into.
- [`sim/device-characterization-report.md`](sim/device-characterization-report.md)
  — measured-in-simulation device data, with per-number provenance.

## License

[Apache-2.0](LICENSE).
