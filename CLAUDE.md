# gf180-sar-adc — agent instructions

A 10-bit SAR ADC on gf180mcu, designed end to end by AI agents on the
open-source analog flow. See `README.md` for the project overview and
`LICENSE` (Apache-2.0) for terms.

- **PDK**: gf180mcu (open PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout work.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue
  at `2AMLogic/klayout-tools` describing the need generically — describe
  the tool gap, not this design, so the fix serves everyone on the open
  gf180mcu flow and not just this block.
- **Verification is the product**: no claim without a testbench. PVT
  corners on every recorded result. `sim/` results are append-only
  evidence.
- **Work in the open**: this repository is public and exists to be checked.
  Write specs, decision records, and evidence records so an outside reader
  can re-run them and reach the same conclusion — provenance (netlist,
  corners, toolchain versions) travels with every number.
- Spec changes go through `spec/` with a decision record; agents do not
  relax the ratified spec to make results pass.
- Harness bootstrap: copy the sim-harness pattern from
  `2AMLogic/gf180-bandgap` once it lands there rather than reinventing.

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.
<!-- END LOOM ORCHESTRATION -->
<!-- BEGIN REPO-SKILLS -->
This repository has [Repo Skills](https://github.com/rjwalters/repo) v0.8.1 installed —
general repository hygiene and environment commands invoked as `/repo:<command>`. Run
`/repo:help` for the command list, or see `.claude/skills/repo/SKILL.md` for the full
guide. Hygiene commands apply safe, reversible fixes by default and report each
change; run with `--ask` to review first, and `--prune` to allow irreversible
removals. Managed by `install.sh` — edit outside the markers only.
<!-- END REPO-SKILLS -->
