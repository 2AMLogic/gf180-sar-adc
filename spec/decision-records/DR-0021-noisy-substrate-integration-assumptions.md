# DR-0021: Integration assumptions for a substrate shared with switching power structures

- **Status**: ratified — Builder agent, issue #226
- **Date**: 2026-08-17
- **Decided by**: Builder agent, issue #226
- **Supersedes**: none — first record on shared-substrate integration
  assumptions
- **Superseded by**: (none while this record stands)
- **Related**: #226, [DR-0002](DR-0002-reference-source.md),
  [DR-0003](DR-0003-clocking.md), [DR-0004](DR-0004-device-flavor.md),
  `layout/adc-top/README.md` §2.4, `sim/track-switch-thd/`,
  `sim/adc-enob-fft/`

## Context

Issue #226 was filed from a chip-level integration exercise: this ADC is
wanted on a die that also carries switching power/driver structures (a
mixed-signal-with-power design). Every dynamic-performance row in the
ratified target spec (ENOB, SFDR, CMRR) is verified against a supply and
reference that meet [DR-0002](DR-0002-reference-source.md)'s external,
filtered-source terms (`V_DD`/`V_REF` independent pins, `V_REF` decoupling
≥ 40 nF, effective source impedance ≤ 240 Ω in the switching band) and
[DR-0004](DR-0004-device-flavor.md)'s single 3.3 V supply — **with no on-die
switching-power aggressor modeled**. `layout/adc-top/README.md` §2.4 already
draws one contacted body-tie guard ring (`Comp`/`Contact`/`Metal1`) around
the whole analog core, plus a separately-ringed 20 µm gap isolating the
reserved SAR-logic region — but that ring addresses **intra-block**
digital/analog isolation, not coupling from an external switching-power
aggressor on the same die, and no deep n-well (DNW) device-tub isolation is
drawn or characterized against one. None of this was previously stated as an
integration assumption; a reader had to infer it from what the verification
suite does *not* test.

## Decision

**State explicitly, with an evidence tier, what an integrator sharing a die
with switching power/driver structures must provide** — rather than leave it
implicit in what the verification suite happens not to cover:

1. **Guard-ring / DNW guidance** — evidence tier: **design guidance, not
   testbench-verified.** When this block shares a die with switching-power
   devices, standard mixed-signal practice is to add a deep n-well tub around
   the CDAC array, comparator, and input-switch devices, tied to a dedicated
   quiet analog well/substrate contact **separate from any switching-power
   ground return** — beyond the existing body-tie ring
   (`layout/adc-top/README.md` §2.4), which was drawn for intra-block
   isolation only. This repository has not laid out, DRC/LVS'd, or extracted
   a DNW-isolated variant, and no `sim/` evidence measures substrate coupling
   from a switching aggressor into this block's nodes. This is a planning
   recommendation, not a verified structure.
2. **Supply / reference isolation** — evidence tier: **derived from ratified
   rows, not independently tested against an aggressor.** `V_DD` and `V_REF`
   must each be independent, filtered, external pins meeting DR-0002's
   ≤ 240 Ω / ≥ 40 nF terms, with **no coupled switching-power noise**; every
   dynamic-performance row (ENOB, SFDR, CMRR) was verified under that
   condition. Sharing a rail or a return path with a switching-power driver
   on the same die directly violates that source model, and invalidates
   every dynamic-performance row until it is re-verified with the aggressor
   present — which this repository has not done.
3. **Timing assumption: sample outside switching edges** — evidence tier:
   **architectural, not testbench-verified against an aggressor.** This
   block's own conversion timing (M = 16 clocks/conversion — 4 sample + 10
   bit-trial + 2 reset/output, [DR-0003](DR-0003-clocking.md),
   `spec/prior-art-survey.md` §1.4) has no synchronization interface to an
   external switching-power event. An integrator sharing a die with a
   switching driver is responsible for scheduling this ADC's track/sample
   phase to avoid overlapping the aggressor's switching edges: the
   aperture-jitter budget (DR-0003) and the sampling-switch's own SFDR
   contribution (`sim/track-switch-thd/`) both assume a quiet sampling
   instant and have not been characterized against an injected switching
   transient.

**No ratified target-spec value changes.** Every dynamic-performance row's
target and last-verified value stand as recorded in
`README.md#target-specification`; what changes is that the *conditions*
those rows were verified under (quiet, external, filtered supply/reference;
no substrate aggressor) are now stated as explicit integration requirements
rather than left implicit.

## Alternatives considered

- **Design and lay out a DNW-isolated variant now.** Not chosen: no
  chip-level substrate-noise model exists to size or verify it against (what
  aggressor, what coupling coefficient, what di/dt) — building one now would
  be design work with no testbench able to close its own claim, which
  violates CLAUDE.md's "no claim without a testbench."
- **Silently rely on the existing body-tie guard ring.** Not chosen: it was
  drawn for a different purpose (intra-block isolation, `layout/adc-top/README.md`
  §2.4) and asserting it also covers an external switching aggressor without
  a testbench is exactly the unlabelled-evidence-tier problem issue #226
  raised.

## Consequences

- A future chip-level integration campaign, if pursued, has a named list of
  what to model first: aggressor di/dt magnitude, substrate coupling
  coefficient, and DNW isolation effectiveness — each needing its own `sim/`
  evidence record before any coupled-noise number can be claimed.
- README gains an explicit "Integration on a noisy, mixed-signal-with-power
  substrate" section (below) stating these three assumptions and their
  evidence tier, so a reader is not misled into thinking the existing
  verification suite covers a switching-aggressor scenario.
- **Bad consequence, stated plainly**: an integrator following this guidance
  still has no measured number for coupled substrate noise, DNW isolation
  effectiveness, or timing margin against a real aggressor — this record
  names the gap and the assumption a user must hold to close it themselves;
  it does not close the gap itself.

## Spec lines affected

none — this record adds integration guidance and states the evidence tier of
an assumption that was already implicit in DR-0002's and DR-0004's
external-pin decisions; it does not alter any ratified target-spec parameter
or value.
