# DR-0002: Reference source — external V_REF pin

- **Status**: proposed — requires operator sign-off (spec ratification authority sits with engineering per #1)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #7
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #7, #8, `spec/prior-art-survey.md` §1.1, §2.4, `sim/device-characterization-report.md` §5.1, DR-0003, `2AMLogic/gf180-bandgap` (sister block, referenced only — no dependency taken)

## Context

#8 cannot fix the CDAC's per-bit settling budget without a reference drive
model. `spec/prior-art-survey.md` §2.4 already forces one conclusion
regardless of switching scheme: on-chip decoupling alone cannot supply the
CDAC's per-step reference charge (it would need nF-scale capacitance,
multiple mm² — many times the entire 0.1 mm² area budget) so **the reference
must be actively driven and settle within a bit cycle, or be supplied
off-chip with external decoupling.** What that section does not decide is
*where the reference comes from*: internal (the sister `gf180-bandgap` block
plus a reference buffer) or an external pin.

## Decision

**External reference pin (`V_REF`)**, not derived from the internal
sister `gf180-bandgap` block.

- **V_REF = 3.3 V** nominal, supplied as an independent low-impedance pin
  (not tied directly to `V_DD`, so it can be decoupled and measured
  separately from digital switching noise on the supply).
- **Full-scale mapping**: single-ended input range = 0–`V_REF` (0–3.3 V);
  differential input range = ±`V_REF` about a common mode `V_CM = V_REF/2 =
  1.65 V` (differential full-scale peak-to-peak = 2×`V_REF`), matching
  `spec/prior-art-survey.md` §1.1's framing that "a differential architecture
  with ±V_ref gives 2× this [range]."
- **Reference drive model for #8**:
  - Required external decoupling: **≥ 40 nF** at the `V_REF` pin.
  - Required effective source impedance: **≤ 240 Ω** at the switching band
    (a conservative floor — see derivation; #8 may relax this once its
    actual per-bit switched capacitance, not the whole array, is fixed).

### Derivation (shown, not asserted)

**Source impedance.** Reuse the bit-cycle settling requirement from
`spec/prior-art-survey.md` §1.4 (`t/τ ≥ ln(2¹¹) = 7.62` within one 62.5 ns
bit cycle at M = 16, 1 MS/s), applied conservatively to the full planning
array capacitance (34 pF, `sim/device-characterization-report.md` §5.1,
A_C = 2.0 %·µm derated):

```
τ_max      = 62.5 ns / 7.62        ≈ 8.2 ns
Z_ref,max  = τ_max / C_array        = 8.2 ns / 34 pF ≈ 241 Ω
```

This treats the *entire* array as if it switched in one bit cycle, which no
real switching scheme does (only a fraction of the array moves per trial) —
so 241 Ω is a safe floor #8 can only relax, never tighten, once its actual
per-step capacitance is known.

**Decoupling.** Reuse §2.4's exact charge/voltage relation
(`C_dec ≥ ΔQ / ΔV_LSB`, `ΔV_LSB = 0.5 LSB = 1.61 mV rms` from
`spec/prior-art-survey.md` §1.1), rescaled from the survey's original
`C_u = 5 fF` placeholder to the device-characterization report's derated
planning value `C_u = 33 fF` (6.6× larger,
`sim/device-characterization-report.md` §5.1):

```
ΔQ_max (conventional scheme, worst MSB step) ≈ 8.4 pC × 6.6 ≈ 55 pC
C_dec,min = 55 pC / 1.61 mV ≈ 34 nF   → round up to 40 nF for margin
```

MCS/monotonic switching schemes need proportionally less (§2.4's original
ratio scales to ≈ 8.6–14 nF) — #8's eventual choice of scheme only relaxes
this 40 nF ceiling, never tightens it. 40 nF is trivially achievable with a
standard off-chip ceramic capacitor (100 nF – 1 µF parts are routine).

## Alternatives considered

- **Internal reference (sister `gf180-bandgap` block + a purpose-built
  reference buffer)** — not chosen for the simulation-complete milestone. It
  imports the bandgap block's own schedule as a hard dependency on this
  canary, and it adds an unbuilt reference-buffer design (sized to the
  ≤ 240 Ω / ≥ 40 nF model above) with no existing evidence record in this
  repo. Not rejected forever — a later, more integrated milestone may revisit
  this once `gf180-bandgap`'s own reference output impedance is
  characterized — but taking that dependency now is unbudgeted scope this
  decision defers, matching the issue's framing that external "decouples the
  canary and gives a cleaner accuracy story for simulation-complete."
- **Deriving V_REF directly from V_DD (no separate pin)** — not chosen. This
  couples reference noise/drift directly to digital switching noise on
  `V_DD`, defeating the point of the drive/decoupling budget above, and
  forecloses future per-part reference trimming.

## Consequences

- #8 designs its CDAC switching scheme and per-bit settling budget against
  `Z_ref ≤ 240 Ω` / `C_dec ≥ 40 nF` as a fixed input, not a free variable.
- A new package pin (`V_REF`) is required beyond `V_DD`/GND — a pinout cost
  #12/#15 must account for.
- The "self-contained catalog part" story is explicitly deferred: for the
  simulation-complete milestone this block is reference-dependent, and its
  datasheet must say so plainly. This is a real, stated cost — an external
  reference is one more thing a user of this catalog part must supply
  correctly (a clean, low-noise 3.3 V source) — not merely a scheduling
  convenience for the canary.
- **2 MS/s stretch**: at 2 MS/s the bit cycle halves to 31.25 ns, roughly
  halving `Z_ref,max` to ≈ 120 Ω. This is noted but not further resolved
  here — #8 must revisit the reference drive model at that rate.

## Spec lines affected

- `README.md#target-specification` (pending #1) — Reference (`V_REF`) — new:
  no explicit "Reference" row exists in the current DRAFT table; this adds
  one — value 3.3 V, external pin, full-scale mapping as above.
