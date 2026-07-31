# DR-0003: Clocking — external clock pin, no on-chip oscillator

- **Status**: ratified — operator sign-off 2026-07-31 (#1, recorded in DR-0006)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #7
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #7, #11, #12, #13, `spec/prior-art-survey.md` §1.1, §4

## Context

#12 cannot close its bit-cycle timing budget, and #11's sync-vs-async
argument is not fully load-bearing, without a clock-source decision.
`spec/prior-art-survey.md` §4 already recommends synchronous SAR logic at
`M = 16` (16 MHz @ 1 MS/s) with high confidence, but that recommendation's
"reconsider if" clause is explicitly conditioned on this issue: "reconsider
if #1/#7 adds a requirement for a low-frequency-only external clock
interface." This record closes that condition. An on-chip oscillator is
added design scope not present in the draft spec table and must be decided
explicitly, not left implicit.

## Decision

**External clock pin.** `M = 16 × f_s`: **16 MHz @ 1 MS/s** (target),
**32 MHz @ 2 MS/s** (stretch). This clock drives both the SAR bit-cycle
state machine and (very likely) the SPI interface timing. **No on-chip
oscillator is in scope for the simulation-complete milestone.**

**Budgeted rms aperture jitter**: **≤ 250 ps rms** at the 1 MS/s target;
**≤ 180 ps rms** if the 9.5 ENOB / 2 MS/s stretch is pursued.

### Aperture-jitter derivation (shown, not asserted)

Per the issue's stated formula, `SNR_jitter (dB) = −20·log10(2π·f_in·σ_t)`,
evaluated at Nyquist `f_in = 500 kHz` (half of 1 MS/s).

Required SNDR for **ENOB > 9.0**: `6.02×9 + 1.76 = 55.94 dB`
(`spec/prior-art-survey.md` §1.1). A **6 dB margin** is applied so that
jitter's noise-power contribution stays a minority term (≤ ~25 % of the
total allowed non-quantization noise power) rather than dominating the
budget — i.e. the design target is `SNR_jitter ≥ 55.94 + 6 = 61.94 dB`:

```
σ_t ≤ 10^(−61.94/20) / (2π × 500 kHz)
    = 8.00e-4 / 3.1416e6
    ≈ 2.55e-10 s ≈ 255 ps rms     → round down to 250 ps for the target
```

For the **ENOB > 9.5** stretch (required SNDR `6.02×9.5 + 1.76 = 58.95 dB`,
same 6 dB margin, target `64.95 dB`):

```
σ_t ≤ 10^(−64.95/20) / (2π × 500 kHz)
    = 5.66e-4 / 3.1416e6
    ≈ 1.80e-10 s ≈ 180 ps rms
```

Both numbers are loose relative to any commodity crystal or MEMS oscillator
(typically single-digit to double-digit ps rms) or even a modest on-chip RC
oscillator (typically tens of ps to low ns depending on design) — the
issue's expectation that "the requirement at this rate is expected to be
loose" is now a shown number, not an assertion.

### Why external, given the budget is loose either way

1. **Zero added scope.** `spec/prior-art-survey.md` §4.3 already establishes
   that a clean 16–32 MHz external clock is "almost certainly already
   required for the SPI interface" — an external clock pin costs nothing
   beyond what the interface needs regardless of this decision.
2. **An on-chip oscillator is unbudgeted scope.** It needs its own PVT-corner
   characterization (frequency accuracy, temperature drift, startup time) —
   real design and verification work with no line item in the current spec,
   and no existing evidence record in this repo uses one.
3. **Verification determinism.** `spec/prior-art-survey.md` §4.4 shows the
   entire `#13` testbench methodology assumes a deterministic ideal pulse
   clock source; an external pin preserves that directly. An on-chip
   oscillator would need its own jitter/drift model injected into every
   PVT/Monte Carlo run, multiplying the cost of the campaign §3.5 already
   flags as the most expensive item.

## Alternatives considered

- **On-chip RC/ring oscillator** — not chosen. Unbudgeted design and
  characterization scope, with no benefit given the loose (≥ 180 ps) jitter
  budget and the interface's independent need for an external clock anyway.
- **Dual-mode: on-chip oscillator with external clock as a selectable
  fallback** — not chosen for simulation-complete. Doubles the clocking
  verification surface (two clock paths to characterize) for a milestone
  whose acceptance criteria do not require a self-clocked mode. Revisit if a
  later, no-external-clock milestone is scoped.

## Consequences

- #12 designs bit-cycle generation against a supplied 16–32 MHz external
  clock budgeted to ≤ 250 ps rms aperture jitter (1 MS/s) / ≤ 180 ps rms
  (2 MS/s stretch).
- #11's synchronous-logic recommendation is now load-bearing rather than
  merely convenient: the one scenario in `spec/prior-art-survey.md` §4.5
  that could have reopened the sync-vs-async trade (a low-frequency-only
  external clock forcing self-timing) is closed off by this decision.
- A clean external clock source at the board level is now a real integration
  requirement for any user of this catalog part, and one more package pin —
  stated as a cost, not elided.
- The 2 MS/s stretch's tighter 180 ps rms budget is shown above and is not
  further excluded — it is covered by this record, unlike the source-
  impedance budget in DR-0001.

## Spec lines affected

- `README.md#target-specification` (pending #1) — Clock — new: no explicit
  "Clock" row exists in the current DRAFT table; this adds one — external
  pin, 16 MHz @ 1 MS/s (32 MHz @ 2 MS/s stretch), ≤ 250 ps rms aperture
  jitter (≤ 180 ps rms for the stretch).
