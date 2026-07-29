# gf180-sar-adc — agent instructions

Private repo; proprietary 2AM Logic IP. Canary block.

- **PDK**: gf180mcu (open PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout work.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue
  at `2AMLogic/klayout-tools` describing the need generically (never
  include proprietary design details, spec values, or this repo's content
  in the public issue — describe the tool gap, not the design).
- **Verification is the product**: no claim without a testbench. PVT
  corners on every recorded result. `sim/` results are append-only
  evidence.
- **Confidentiality**: this repo, its specs, and its results are Tier 2
  (see marketing repo POSITIONING.md). The block's *name/existence* is
  public; everything else here is not. Never copy content from here into
  public repos, issues, or posts.
- Spec changes go through `spec/` with a decision record; agents do not
  relax the ratified spec to make results pass.
- Harness bootstrap: copy the sim-harness pattern from
  `2AMLogic/gf180-bandgap` once it lands there rather than reinventing.
