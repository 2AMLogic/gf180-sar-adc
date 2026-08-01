# DR-0013: Pin the sampling switch's turn-off charge split with a required input-pin capacitor, and size the dummy to it

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #39
- **Supersedes**: [DR-0001](DR-0001-input-drive.md) — same question (the
  input-drive interface contract), restated here with a required external
  pin capacitor and a settling-derived source-impedance budget. DR-0001's
  other conclusions (external driver required, no on-chip input buffer,
  per-pin budget in differential mode, 2 MS/s stretch explicitly excluded)
  are carried forward unchanged below, not dropped.
- **Superseded by**: (none while this record stands)
- **Related**: #1, #7, #10, #13, #39, [DR-0002](DR-0002-reference-source.md)
  (the existing precedent for a required external component),
  [DR-0003](DR-0003-clocking.md), [DR-0011 (CDAC switching scheme)](DR-0011-cdac-switching-scheme.md),
  [DR-0007](DR-0007-track-switch-topology.md) (fixes the switch topology and
  main-device sizing this record keeps; its dummy **width ratio** is the one
  parameter revised here), [DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md)
  (the spec row this record is verified against),
  `sim/track-switch-sampling/records/20260801-070046-50bffb1.md`,
  `sim/track-switch-sampling/records/20260801-080221-fa8fd37.md` (the
  verification run)

## Context

[DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md) gives the
sampling switch's deterministic charge-injection gain error its own spec row
at ≤ 0.5 LSB over the full PVT grid. The switch as
[DR-0007](DR-0007-track-switch-topology.md) drew it — 40 µm/80 µm T-gate,
textbook half-width dummy — measures **3.57–5.38 LSB** on that row
(`sim/track-switch-sampling/records/20260801-023754-267871b.md`), 7–11× over.
This record fixes that.

**The finding that decides the fix.** DR-0007's measurement held two things
fixed at once: the textbook 1:2 dummy-to-main width ratio, and DR-0001's
contracted **worst-case** 500 Ω source impedance. Separating the two axes on
the full 117-point grid
(`sim/track-switch-sampling/records/20260801-070046-50bffb1.md`) shows the
dummy is not the dominant variable — the **drive condition** is:

| Source impedance (bare drive, dummy ratio held at the as-drawn 1:2) | Gain-error contribution over the full PVT grid (LSB) |
|---|---|
| 10 Ω | −0.494 … −0.023 |
| 20 Ω | −0.023 … +0.421 |
| 30 Ω | +0.382 … +0.812 |
| 50 Ω | +0.839 … +1.471 |
| 150 Ω | +2.123 … +3.501 |
| 500 Ω (DR-0001's contracted worst case) | +3.573 … +5.380 |

The turn-off channel charge divides between the driven source and the
floating hold node in a ratio set by how fast charge can leave through the
source relative to how fast the channel collapses —
`sim/device-characterization-report.md` §2.2 already flagged this as a
caveat; here it is measured. A dummy of ratio `r` cancels the fraction `f`
that lands on the hold node, so the residual gain error goes as `(f − r)`,
and **`f` is a function of the user's source impedance**. DR-0001 leaves
that anywhere in 0–500 Ω. Confirming the mechanism directly, re-tuning the
dummy alone does work — but only at one drive point:

| Dummy-to-main width ratio, at 500 Ω | Gain-error contribution over the full PVT grid (LSB) |
|---|---|
| 0.50 (as drawn, DR-0007) | +3.573 … +5.380 |
| 0.70 | +1.300 … +2.509 |
| 0.85 | −0.389 … +0.375 |

A ratio of 0.85 meets the row at 500 Ω and would be badly over-compensated
at 20 Ω, where `f` is near 0.5. **No fixed dummy ratio can bound a quantity
the user sets after tape-out.** Either the spec row acquires a source-
impedance condition so narrow it is not a usable contract, or the split is
pinned in the design. That is the decision below.

**What pins it.** A capacitor at the input pin holds the source-side node
rigid for the whole 1 ns turn-off edge, so the series resistance stops
rate-limiting the escaping charge and `f` stops depending on it. Measured
with the dummy ratio and pin capacitance both held fixed, varying **only**
the source impedance by 20× (25 Ω → 500 Ω), worst case over the full grid:

| Pin capacitor | Worst-corner change in gain error across a 20× change in source impedance |
|---|---|
| none (bare drive) | 5.126 LSB |
| 100 pF | 0.025 LSB |
| 1 nF | 0.002 LSB |

This is not the naive "the split becomes the capacitor ratio
`C_in/(C_in+C_pin)`" argument — that predicts `f ≈ 0.009` at 1 nF, and the
measurement puts `f ≈ 0.44`. The pin capacitor does not make the split
small; it makes it **fixed**, which is what a fixed dummy needs.

## Decision

**A capacitor at each input pin is part of the interface contract, and the
dummy compensation is sized to the charge split that capacitor pins.** These
are one decision, not two: the dummy ratio is only well-defined once the
split is pinned, and the pin capacitor is only required because a fixed
ratio has to be sized against something fixed.

### Interface contract (replaces DR-0001's)

- **External driver required.** No on-chip input buffer (unchanged from
  DR-0001, and for DR-0001's reasons — a buffer's linearity, noise and power
  are not allocated inside the < 1 mW / < 0.1 mm² targets).
- **`C_pin` between 100 pF and 1 nF, external, from each input pin to the
  analog ground**, single-ended and independently on each pin in differential
  mode. Both bounds are set by measurement, not by preference, and the range
  is two-sided because the pinned split fraction is not perfectly independent
  of `C_pin` — it is what is left of the drive dependence, and the dummy
  ratio can only be centred on a bounded range. 100 pF (11.3 × the 8.827 pF
  per-side array) is the smallest capacitance measured to hold the split;
  1 nF is the largest measured, and is in any case where the time-constant
  budget below stops leaving a usable source impedance.
- **`R_source × (C_pin + C_in) ≤ 30 ns`**, where `R_source` is the *total*
  series resistance at the pin (driver output impedance plus any isolation
  resistor) and `C_in = 8.827 pF` is the per-side array
  ([DR-0011](DR-0011-cdac-switching-scheme.md), `spec/cdac-sizing-memo.md`
  §5.2). Two reference points, both directly measured:

  | `C_pin` | `R_source` | `tau_in` | Verified at |
  |---|---|---|---|
  | 100 pF | ≤ 250 Ω | 27.2 ns | `20260801-080221-fa8fd37` (branches `px1`, `px250`) |
  | 1 nF | ≤ 25 Ω | 25.2 ns | `20260801-070046-50bffb1`, `20260801-080221-fa8fd37` (branches `cxoptl`, `cxopt`) |

- **1 MS/s only**, as in DR-0001: the 2 MS/s stretch column is not covered
  by this record either. The track window halves to 150 ns, which halves the
  time-constant budget to 15 ns; whether that is drivable is left to
  whichever issue takes up the stretch column.

#### Derivation of the 30 ns budget (shown, not asserted)

Closing the switch connects `C_in` to the pin, and the pin's charge
redistributes. The kick is set by the capacitive divider and is
supply-independent when expressed in LSB, because full scale and the LSB
both scale with `V_REF`:

```
kick [LSB] = 1024 × C_in / (C_in + C_pin)
           = 1024 × 8.827 / 108.827  = 83.1 LSB   at C_pin = 100 pF
           = 1024 × 8.827 / 1008.827 =  9.0 LSB   at C_pin = 1 nF
```

The pin recovers it from the source with `tau_in = R_source × (C_pin +
C_in)` inside the 300 ns track window. At the budget's limit, and at the
worst (smallest) permitted `C_pin`:

```
residual = 83.1 × exp(-300 ns / 30 ns) = 83.1 × 4.54e-5 = 0.0038 LSB
```

— 130× inside DR-0001's own ½-LSB settling criterion, and a minority term
against both the 0.5 LSB this record is closing and the 1 LSB INL row. The
30 ns is the round number below the point where that stops being true: the
½-LSB criterion alone would permit `tau_in ≤ 58.7 ns` at `C_pin = 100 pF`
(`ln(83.1 / 0.5) = 5.11` e-folds into 300 ns), and the budget is set at
roughly half that so the term stays negligible rather than merely legal. The
same budget sets the input bandwidth: `f_-3dB ≥ 1/(2π × 30 ns) = 5.3 MHz`,
i.e. ≥ 10.6 × Nyquist.

### Dummy compensation

- **Dummy-to-main width ratio 7/16 = 0.4375** — dummy NMOS 17.5 µm, dummy
  PMOS 35.0 µm against DR-0007's 40 µm/80 µm main devices, both
  `L = 0.28 µm`, source and drain shorted onto the hold node, gated on the
  phase complementary to the main devices. This revises the one parameter
  DR-0007 set at the textbook value (1/2); DR-0007's topology choice
  (T-gate, not bootstrap) and its 4× main-device sizing are unchanged and
  not re-opened.
- **The ratio is to be drawn as a finger count, not as a width** — 7 of the
  main device's 16 fingers — so the dummy is a literal replica slice of the
  main device and the ratio survives process bias on the drawn width, which
  a separately-dimensioned dummy would not.

### Result on the DR-0012 row

Verification run `sim/track-switch-sampling/records/20260801-080221-fa8fd37.md`,
full 117-point PVT grid, both ends of the permitted `C_pin` range and across
the permitted source impedance:

| Branch | `C_pin` | `R_source` | `tau_in` | In contract? | Gain error over the grid (LSB) |
|---|---|---|---|---|---|
| `px1` | 100 pF | 1 Ω | 0.1 ns | yes | −0.257 … +0.251 |
| `px250` | 100 pF | 250 Ω | 27.2 ns | yes | −0.107 … **+0.421** |
| `cxoptl` | 1 nF | 1 Ω | 1.0 ns | yes | **−0.293** … +0.219 |
| `cxopt` | 1 nF | 25 Ω | 25.2 ns | yes | −0.289 … +0.224 |
| `px500` | 100 pF | 500 Ω | 54.4 ns | no — margin probe | −0.106 … +0.423 |
| `cxopth` | 1 nF | 500 Ω | 504 ns | no — margin probe | −0.288 … +0.223 |

**Worst case anywhere inside the contract: 0.421 LSB** (`px250`, at
`ff_125c_3.63v`) against DR-0012's `≤ 0.5 LSB` row — a **pass, with 1.19×
margin**, from 3.57–5.38 LSB before. Stating the margin plainly because it is
not large: the residual is dominated not by PVT (each individual branch spans
only ~0.5 LSB) but by the `C_pin` dependence of the pinned split — the 100 pF
end sits at +0.42 and the 1 nF end at −0.29, and a single fixed dummy ratio
has to straddle both. Narrowing the permitted `C_pin` range, or moving the
ratio from 7/16 to 4/9, would re-centre it; that margin is available and is
deliberately not spent here, because a two-decade `C_pin` range is worth more
to a user than 0.1 LSB of headroom on a row that already passes.

Three further quantities move the right way as a side effect, same run:

| Quantity | DR-0007 switch, bare 500 Ω drive | This record's switch and network (in contract) |
|---|---|---|
| Endpoint-fit residual (the part that *does* land in INL/DNL) | 0.430 … 0.685 LSB | **0.013 … 0.197 LSB** |
| Deterministic offset contribution (pedestal at zero scale) | 1.110 … 1.558 LSB | **≤ 0.119 LSB** |
| Worst-case full-scale acquisition error | 0 LSB | **≤ 0.0021 LSB** |

The acquisition figure is also a check on the 30 ns derivation above rather
than just a pass: that derivation predicts 0.0013 LSB of un-recovered kick at
the 250 Ω / 100 pF point (`83.1 × exp(−300/27.2)`), and the measurement reads
0.0011–0.0021 LSB across the grid. The 1 nF branches predict 6e-5 LSB and
read 0, which is this measurement's resolution (1 µV), not a smaller number.
Hold droop over the 700 ns conversion phase stays ≤ 8.8 µV (0.0027 LSB).

## Alternatives considered

- **Re-tune the dummy ratio alone (0.85 at 500 Ω), leaving the drive
  contract as DR-0001 wrote it.** Not chosen, though it does meet the row
  at the corner it is tuned to (−0.389 … +0.375 LSB over the full grid).
  It meets it *only there*. The measured bare-drive sweep puts the split
  fraction near 0.5 at 20 Ω (that is the source impedance at which the
  as-drawn 0.5 ratio nulls), so a 0.85 dummy would over-compensate there by
  about as much as the 0.5 dummy under-compensates at 500 Ω today, with the
  sign reversed — an extrapolation from the two measured axes rather than a
  measured point, but the direction is not in doubt. Either way the part
  would have a gain error the user selects with their driver. It is also
  measurably worse on linearity (endpoint-fit residual 0.268–0.461 LSB
  versus 0.013–0.197 LSB for the pinned configuration) — over-sizing the
  dummy nulls the endpoint slope by adding a compensating charge with a
  *different* input dependence, which straightens the chord and bows the
  middle.
- **Specify a narrow source-impedance window instead of a pin capacitor**
  (e.g. "`R_source = 500 Ω ± 20 %`"). Not chosen: it turns a benign upper
  bound into a two-sided requirement no ordinary driver meets, and it is
  fragile against everything that shifts `f` besides `R_source` — package
  and board parasitics at the pin, most obviously. A capacitor swamps those;
  a resistance window is at their mercy.
- **A system-level gain trim.** Not chosen: the ratified row says
  "untrimmed", so adding a trim is itself a spec change, and it would need
  its own storage, a production trim step and a trim-drift budget — real
  cost, to correct a term that a 100 pF capacitor removes. Worth revisiting
  only if a *later* mechanism turns out to need trim anyway.
- **Shrink the main device back toward the nominal 10 µm/20 µm geometry** to
  reduce the injected charge. Not chosen: DR-0007 measured the nominal
  geometry failing the ratified `SFDR ≥ 62 dB` floor by ~8 dB. Trading a
  ratified row for a ratified row is not a fix, and the nominal geometry is
  over the gain row anyway (2.04–2.92 LSB) at DR-0001's contracted drive.
- **Slow the turn-off edge** so the channel charge has time to leave through
  the source at any `R_source`. Not chosen here: it makes the effective
  sampling instant input-dependent, which is a distortion mechanism aimed
  straight at DR-0007's 2.8 dB of SFDR margin, and it would need
  `sim/track-switch-thd` re-run to price. A capacitor costs nothing on that
  axis. Not measured, so listed as unpriced rather than as rejected on data.
- **Leave it, and write the new row's target around the measured value.**
  Not chosen, and out of bounds: CLAUDE.md forbids relaxing the ratified
  spec to make results pass, and DR-0012 applies the same discipline to a
  new row.

## Consequences

- **The part now requires an external component to meet a datasheet row.**
  That is a real cost, stated: a user who omits the pin capacitor gets a
  gain error of up to 5.4 LSB set by their own source impedance, and
  nothing on the die warns them. It is a familiar cost — every SAR ADC
  wants a charge-kickback filter at its input, and
  [DR-0002](DR-0002-reference-source.md) already requires ≥ 40 nF of
  external decoupling on `V_REF` — but requiring it *to meet a spec row*,
  rather than recommending it as good practice, is stronger than what
  DR-0001 promised.
- **The allowed source impedance drops from 500 Ω to 250 Ω** at the
  reference `C_pin = 100 pF` (and to 25 Ω if the user picks 1 nF). Users
  driving through a large isolation resistor are worse off than DR-0001
  promised. The trade is explicit in the time-constant budget, so a user can
  buy source impedance back only by *reducing* `C_pin`, which the 100 pF
  floor bounds.
- **Input bandwidth drops, by about 3×.** DR-0001's network had only the
  array's own `(R_source + R_on) × C_in = (500 + 570) Ω × 8.827 pF ≈
  9.4 ns`, i.e. ~17 MHz; the pin capacitor makes `tau_in` ~3× that at the
  budget limit, so the T/H −3 dB bandwidth falls to ≥ 5.3 MHz. Still
  > 10 × Nyquist, so no ratified row moves — but it is a real loss of margin
  against out-of-band content, and it is the price of the pin capacitor.
  (The 4.4 MHz the input-structure row published before this record is not
  the right comparison: it was derived from the 34 pF *planning* array that
  #8 closed at 8.827 pF, so it understated the old network. Correcting that
  stale figure is part of this record's row edit rather than a separate
  change, because the same row's bandwidth clause is being rewritten
  anyway.)
- **Acquisition still closes, measured not assumed** — worst-case full-scale
  step through the specified network, ≤ 0.0021 LSB over the grid, against a
  derivation that predicted 0.0013 LSB. It is no longer the exact 0 the bare
  network read, and that is the honest cost of putting charge storage at the
  pin.
- **DR-0007's SFDR result is not disturbed, by construction.** The dummy
  devices are off during track (their gates take the complementary phase),
  so they contribute no `R_on` and no `R_on` modulation; narrowing them from
  1/2 to 7/16 only reduces the parasitic they add to the hold node. The pin
  network is linear and sits ahead of the switch, so it cannot generate
  distortion of its own. There is therefore no mechanism by which this
  record regresses `sim/track-switch-thd`'s numbers — but that is an
  argument from topology, not a measurement, and a confirming re-run of
  `sim/track-switch-thd` through the specified network is cheap and is left
  as follow-up.
- **The deterministic offset contribution improves as a side effect**, from
  1.110–1.558 LSB (most of the ratified ≤ 2 LSB offset row consumed by the
  sampling switch alone) to ≤ 0.119 LSB. DR-0012's Consequences note that the offset
  row has the same mismatch-vs-deterministic structure as the gain row; this
  record does not open that question, but it does move the number well clear
  of it.
- **#13 (testbench suite) and #16 (layout) inherit conditions.** #13's
  gain-error corner run must instantiate the specified pin network or it
  measures a different quantity. #16 must draw the dummy as 7 of the main
  device's 16 fingers, not as an independently-dimensioned 17.5 µm/35 µm
  device.
- **`design/track-switch/track_switch.sch` needs its dummy widths updated**
  from 20 µm/40 µm to 17.5 µm/35 µm. That schematic edit is in this
  record's scope and is made with it.

## Spec lines affected

- `README.md#target-specification` — Input row — **changed**: adds the
  required `C_pin ≥ 100 pF` per-pin capacitor and replaces the flat
  `≤ 500 Ω` source-impedance limit with the time-constant budget
  `R_source × (C_pin + C_in) ≤ 30 ns` (`≤ 250 Ω` at the 100 pF reference
  point). Citation moves from [DR-0001](DR-0001-input-drive.md) to this
  record.
- `README.md#target-specification` — Input structure row — **changed**:
  T/H −3 dB bandwidth restated for the specified network (≥ 5.3 MHz,
  ≥ 10.6 × Nyquist, from the 30 ns budget) in place of the 4.4 MHz figure
  derived from the superseded 500 Ω / 34 pF network; and `C_in` corrected
  from the `≈ 34 pF (planning value, pending #8)` placeholder to #8's
  measured `8.827 pF` per side, which the new bandwidth clause is derived
  from and which the same row cannot self-consistently omit.
- `README.md#target-specification` — note **[f]** — **changed**: derivation
  updated to the specified network and to the measured `C_in`.
- `README.md#target-specification` — Gain error, systematic row
  ([DR-0012](DR-0012-gain-error-deterministic-vs-mismatch.md)) — **no value
  change**; this record is the evidence that the row is met, and the source
  of the drive network its binding condition names.
- `spec/decision-records/DR-0001-input-drive.md` — **superseded** by this
  record (back-pointer added to DR-0001's Status / Superseded by fields, the
  only edit ever made to a ratified record).
