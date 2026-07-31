# DR-0001: Input drive — external low-impedance driver, benign track-mode load

- **Status**: proposed — requires operator sign-off (spec ratification authority sits with engineering per #1; this record is a scope decision, not yet ratified)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #7
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #3, #4, #7, #8, #10, `spec/prior-art-survey.md` §1.4 §5, `sim/device-characterization-report.md` §2.1, §5.1

## Context

#10 cannot budget the track-switch settling window without a stated source
impedance, and #8 cannot fix the CDAC array size without knowing whether an
on-chip input buffer is in scope. The draft spec table states the input
range (0–3.3 V single-ended + differential) but not the interface contract
around it: is an external buffer assumed, or must the ADC present a benign
load? `spec/prior-art-survey.md` §5.2 already establishes that bootstrapping
is unnecessary at 3.3 V (>100 τ of raw acquisition margin) and that a plain
CMOS transmission gate is the default candidate for #10; what remains open is
the maximum source impedance the interface promises to a driving source.

## Decision

**External driver required.** The ADC does not include an on-chip input
buffer. It presents a benign but explicitly bounded track-mode load, and the
interface contract is a stated maximum source impedance a driving source
must meet:

- **Maximum external source impedance: ≤ 500 Ω**, single-ended and
  independently on each pin in differential mode (each differential input
  samples its own half-array; the same per-pin budget applies to both).
- **Input load presented in track**: the parallel combination of the T-gate
  switch resistance (measured 156–570 Ω across the full PVT grid, worst case
  `ss_125c_2.97v`, `sim/device-switch-ron/records/20260731-191216-5f5288b.md`)
  and the CDAC array capacitance (order 10s of pF; exact value is #8's to
  fix — 34 pF is the derated planning figure used below,
  `sim/device-characterization-report.md` §5.1).
- **This budget covers the 1 MS/s target only.** See Consequences for why
  the 2 MS/s stretch is explicitly excluded.

### Derivation (shown, not asserted)

Settling to 0.5 LSB at 10 bits requires `t/τ ≥ ln(2¹¹) = 7.62`
(`spec/prior-art-survey.md` §1.4). The acquisition window is 300 ns (30 % of
the 1 µs period at 1 MS/s, same section).

```
τ_max            = 300 ns / 7.62               ≈ 39.4 ns
R_total,max       = τ_max / C_array            = 39.4 ns / 34 pF ≈ 1159 Ω
R_source,max      = R_total,max − R_switch,worst = 1159 Ω − 570 Ω ≈ 589 Ω
```

`C_array = 34 pF` is the derated planning value from
`sim/device-characterization-report.md` §5.1 (A_C = 2.0 %·µm derating,
1024-unit array) — a conservative upper bound relative to the prior-art
survey's original 5 fF/unit placeholder, chosen because it is the more
recent, simulation-grounded figure. `R_switch,worst = 570 Ω` is the measured
worst-case T-gate R_on (`ss_125c_2.97v`, §2.1 of the device-characterization
report). The 589 Ω computed ceiling is rounded down to a clean **500 Ω**
spec figure for margin against everything this simple single-pole RC model
does not include (source-side capacitance, layout parasitics, and the
assumption that both the switch and the array simultaneously sit at their
stated worst case, which is itself conservative).

## Alternatives considered

- **On-chip input buffer (benign-load requirement, no stated source-impedance
  limit)** — not chosen. This adds a buffer design with its own linearity
  and noise budget and extra power, none of which is currently allocated
  inside the < 1 mW / < 0.1 mm² targets. The margin computed above (≥100 τ
  at nominal, per `spec/prior-art-survey.md` §5.2) means a buffer is not
  *needed* to meet the target spec; it would only earn its keep for source
  impedances well above 500 Ω, which is not the expected use case for a part
  meant to be driven by an op-amp or DAC output.
- **No stated source-impedance limit at all** — not chosen. Silently
  assuming "someone will drive it low enough" is exactly the kind of
  undecided interface contract that blocks #10 from budgeting anything; a
  catalog part must publish a number.

## Consequences

- #10 designs the T-gate/compensation scheme against a fixed ≤ 500 Ω
  external source (single-ended and per differential pin) at 1 MS/s — this
  is now a closed input, not an open question.
- #13's test/verification plan must include a source-impedance corner (e.g.
  0 Ω, 250 Ω, 500 Ω) in the timing/linearity sweep to substantiate this
  margin claim with a testbench, per CLAUDE.md's "no claim without a
  testbench" — this record's arithmetic is not itself the evidence.
- The datasheet for this catalog part must publish an explicit maximum
  source-impedance spec. This is a real, stated constraint on how the part
  can be used, not a free simplification — recording the bad consequence
  alongside the good one.
- **The 2 MS/s / 12-bit stretch column is explicitly NOT covered by this
  record.** At 2 MS/s the acquisition window halves to 150 ns, giving
  `R_total,max = 150 ns / 7.62 / 34 pF ≈ 579 Ω` — leaving only ~9 Ω of margin
  above the 570 Ω worst-case switch resistance alone, i.e. essentially zero
  headroom for any external source impedance under this conservative
  capacitance assumption. The stretch case is left unresolved here and
  deferred to #8/#10 once the actual (not conservative-placeholder) CDAC
  size is fixed.

## Spec lines affected

- `README.md#target-specification` — Input row — clarified (no value
  change): adds a maximum external source-impedance requirement (≤ 500 Ω,
  single-ended and per-pin differential) and states the ADC's track-mode
  input load, without changing the stated 0–3.3 V range itself.
