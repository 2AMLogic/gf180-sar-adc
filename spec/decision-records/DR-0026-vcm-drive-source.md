# DR-0026: V_cm drive source — the analogue of DR-0002's `V_REF` budget

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-08-25
- **Decided by**: Builder agent, issue #260
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #259 / `docs/chipalooza/challenge-3-proposal.md` (where the
  gap was found), #260 (this issue), [DR-0002](DR-0002-reference-source.md)
  (the `V_REF` analogue this record mirrors, and whose own drive network
  this record borrows the R || L + C_dec modelling convention from),
  [DR-0011](DR-0011-cdac-switching-scheme.md) (names `V_cm` generation "a
  new, currently-unbudgeted deliverable for a future issue" — the gap this
  record closes), [DR-0014](DR-0014-bottom-plate-sampling.md) (the
  bottom-plate sampling topology this derivation's charge bookkeeping is
  taken from), `spec/cdac-sizing-memo.md` §5 (the array-capacitance and
  bit-cycle-settling conventions reused here), `sim/vcm-drive-impedance/`
  (the sensitivity evidence this record cites), `sim/` record IDs
  `20260825-162620-e09a2d0` (ideal, Z_vcm = 0), `20260825-163251-cb36f0a`
  (at the derived budget, Z_vcm = 220 Ω), `20260825-163508-64203b5` (5×
  beyond the derived budget, Z_vcm = 1100 Ω)

## Context

`design/adc-top/adc_top.spice`'s `adc_cdac_cell`/`adc_tp_sw` subckts drive
`V_cm` from two mechanisms every conversion, and DR-0002 derived a
drive-impedance/decoupling budget for `V_REF` while explicitly leaving
`V_cm` unbudgeted (DR-0011 Consequences: "`V_cm` generation is … a new,
currently-unbudgeted deliverable for a future issue, or `V_cm` may be
supplied off-chip like `V_REF`"). Every existing ADC-level testbench
(`sim/adc-inl-dnl/`, `sim/adc-enob-fft/`, `sim/adc-power/`) sources `V_cm`
from an ideal, zero-impedance DC source and says so plainly in its own text:
*"V_cm generation is explicitly unbudgeted work … so there is no ratified
envelope to model it against and it is an IDEAL source here. That is a
stated assumption of every record this deck produces, not a measured
result."* `spec/testbench-suite-memo.md` §12 item 3 repeats the same
statement as a known limitation of the whole suite. Issue #259's Chipalooza
Challenge #3 proposal then leaned on an *inferred*, not derived,
`V_cm`-impedance requirement to justify a dedicated (non-multiplexed) pad —
issue #260 asks for the derivation that inference was standing in for, and
for evidence of whether the ideal-source assumption is actually
conservative.

## Decision

**`V_cm` gets its own drive-impedance / decoupling budget, derived the same
way DR-0002 derived `V_REF`'s, and it is *tighter* than DR-0002's — not
because the methodology differs, but because the mechanism does.**

- **Required external decoupling: ≥ 40 nF** at the `V_cm` pin (same
  provisioned value as DR-0002's `V_REF` row, arrived at independently —
  see Derivation).
- **Required effective source impedance: ≤ 220 Ω** at the switching band
  (DR-0002's `V_REF` row provisions ≤ 240 Ω; this is not a coincidence of
  rounding — see Derivation for why the two numbers land close together for
  different reasons).

### Derivation (shown, not asserted)

**What actually moves charge through `V_cm`, and when.** Two mechanisms,
identified directly from `design/adc-top/adc_top.spice` and
`design/sar-logic/README.md`'s phase table (`ph0..ph15`, DR-0003/DR-0014):

1. **Release-phase engagement of every bottom-plate leg, once per
   conversion, within one bit cycle.** At the `ph3 → ph4` edge, `samp_bp`
   falls and **every** switched bottom-plate cell on **both** sides —
   9 weighted positions/side under DR-0011's `2^(N-1) = 512`-unit-per-side
   array (511 switched + 1 terminating unit, DR-0019's resized
   `C_u = 35.6528 fF`, `C_side = 512·C_u = 18.254 pF/side`,
   `spec/cdac-sizing-memo.md` §5.2) — moves from `V_in` to `V_cm`
   *simultaneously*, in a **single 62.5 ns bit cycle** (`ph4`, trial 1, the
   free MSB). The symmetric release at `ph15` (`"drdy asserted; the array
   releases back to V_cm"`) moves the same total capacitance back from
   whatever rail each cell's own trial engaged it to (`V_REF` or `GND`),
   again within one bit cycle. **This is the load-bearing difference from
   DR-0002's derivation**: DR-0002 treats the *whole array* switching in one
   bit cycle as a deliberately unrealistic conservative floor ("this treats
   the entire array as if it switched in one bit cycle, which no real
   switching scheme does"). For `V_cm`, the whole array release genuinely
   **does** happen in one bit cycle, twice a conversion — it is the real
   worst case, not a conservative overestimate.
2. **The top-plate `V_cm` switch during acquisition (`ph0..ph2`).** This
   switch holds the top node at `V_cm` while the bottom plates track a
   changing `V_in` through the cell's fourth leg (DR-0014). Holding the top
   node fixed against a slewing input requires a continuous current
   `I = C_side · dV_in/dt`, ultimately sourced through `V_cm`'s own network.
   In **differential** mode this current is equal and opposite on the two
   sides for a symmetric differential input and cancels at the shared `V_cm`
   node by construction (the same "constant common mode" property
   DR-0011/DR-0014 already rely on); in **single-ended** mode only the input
   side moves (the reference side is pinned to `V_cm` for the whole
   conversion, `design/sar-logic/README.md`), so there is no cancellation
   and the full current is real.

**Source impedance, `Z_vcm,max`.** Reusing DR-0002's own bit-cycle
convention (`t/τ ≥ ln(2¹¹) = 7.6246` within one 62.5 ns bit cycle at 1 MS/s),
applied to the load that genuinely switches in one cycle — **both sides'
full array capacitance**, `C_total = 2·C_side = 36.508 pF`
(`spec/cdac-sizing-memo.md` §5.2, at the ratified, resized `C_u`):

```
τ_max      = 62.5 ns / 7.6246       ≈ 8.20 ns
Z_vcm,max  = τ_max / C_total         = 8.20 ns / 36.508 pF ≈ 224.5 Ω
             → provisioned ≤ 220 Ω (round down for margin, DR-0002's own
               convention: 241 Ω → 240 Ω)
```

Unlike DR-0002's use of the whole-array figure (a deliberate, stated
overestimate), this is the **actual** load for the actual mechanism above —
so `V_cm`'s ceiling comes out tighter than `V_REF`'s not from a modelling
choice but because the two rails are switched differently by this topology.

**Decoupling, `C_dec,min`.** Two independent routes to the same number,
which is itself worth noting:

*Route A — the release-phase charge event.* Worst case, no side-to-side
cancellation assumed (a conservative choice: a real external `V_cm` rail's
current cancellation between the two sides depends on layout-level parasitic
sharing this repo has not characterized, so the safe floor sums both sides'
charge rather than assuming they net to zero):

```
ΔQ_max     = C_total · (V_REF/2) = 36.508 pF · 1.65 V ≈ 60.24 pC
C_dec,min  = ΔQ_max / (0.5 · LSB_se) = 60.24 pC / 1.61133 mV ≈ 37.4 nF
```

*Route B — the acquisition tracking current, single-ended mode, at Nyquist
(the worst-case input rate this budget must survive).* Over one bit cycle,
the charge the top-plate switch's `V_cm` side must supply/sink to hold the
top node fixed while the input side's array tracks a near-full-scale
`f_Nyquist = 500 kHz` sine is bounded by the same total charge the array
moves over one half-period of that tone (`C_side · V_REF`, full swing),
because the acquisition window (187.5 ns) is a small fraction of the input
period and the instantaneous current is therefore well approximated as
constant over any one bit cycle inside it:

```
Q_half-period = C_side · V_REF = 18.254 pF · 3.3 V ≈ 60.24 pC
C_dec,min     = Q_half-period / (0.5 · LSB_se) ≈ 37.4 nF
```

Both routes land on **≈ 37.4 nF**, which is not a coincidence: both reduce
to the same quantity, `C_side · V_REF` (route A sums two sides at half that
swing each; route B takes one side at the full swing) — a useful
cross-check that the release mechanism and the tracking mechanism are not
double-counted, since they bound the same worst-case charge from two
directions. **Provisioned: ≥ 40 nF** (round up for margin, same convention
DR-0002 uses, and the same value DR-0002 already provisions for `V_REF` —
independently arrived at, not copied).

**Which mechanism binds `Z_vcm,max`.** The release-phase event (mechanism 1)
requires settling within `τ_max ≈ 8.2 ns` — a genuinely fast requirement,
because it is a real once-per-conversion step, not a continuous signal. The
acquisition tracking current (mechanism 2) is bounded instead by how well
`C_dec` alone (sized above) filters a 500 kHz-scale current at the *local*
node: at `C_dec = 40 nF`, the decoupling cap's own impedance at 500 kHz is
`1/(2π·500 kHz·40 nF) ≈ 8 Ω` — far below any Z_vcm this record would
provision — so a `C_dec` sized for mechanism 1 already keeps mechanism 2's
requirement on `Z_vcm` far looser than mechanism 1's. **Mechanism 1 (the
release-phase transient) is therefore the binding one for `Z_vcm,max`**;
mechanism 2 does not tighten it further.

## Evidence: is the ideal-source assumption conservative?

Not shown to be. `sim/vcm-drive-impedance/` measures `sim/adc-inl-dnl/`'s own
converter-level metrics (`gain_err_lsb`, `inl_t*_lsb` — explicitly **not**
the ratified `Gain error, systematic` row; see that deck's own
`gain_err_lsb` check description) with the ideal `V_cm` source replaced by
an R || L (source impedance, DC-accurate, resistive at the 16 MHz
switching band — modelled exactly the way this same deck already models
`V_REF`) + `C_dec` network, at three points, over the `cdac` 7-corner
process axis at nominal temperature/supply (`tt_27c_3.30v` cited below;
subset justified in each record):

| Point | Z_vcm | C_dec | `gain_err_lsb` | `inl_t256_lsb` | `inl_t768_lsb` |
|---|---|---|---|---|---|
| Ideal (every existing record's assumption) | 0 Ω | ∞ | **−2.005** | −0.0134 | −0.0020 |
| At the derived budget | 220 Ω | 40 nF | **−2.205** | −0.2805 | −0.0549 |
| 5× beyond the derived budget | 1100 Ω | 40 nF | **−2.312** | −0.0980 | +0.1116 |

(`sim/vcm-drive-impedance/records/20260825-162620-e09a2d0.md`,
`20260825-163251-cb36f0a.md`, `20260825-163508-64203b5.md`.)

Three findings:

1. **`gain_err_lsb` moves monotonically in magnitude with `Z_vcm`** —
   ideal → budget → 5× is a real, non-negligible ≈ 0.2 LSB (≈ 10 %) shift at
   the derived budget alone, growing further beyond it. This is evidence
   against reading the ideal-source assumption as free: a real `V_cm`
   network at exactly the budget this record provisions changes this
   metric measurably.
2. **Individual code errors move by more, and NOT monotonically.**
   `inl_t256_lsb` swings 21× (−0.013 → −0.281 LSB) at the budget point, then
   partially recovers at 5×; `inl_t768_lsb` changes sign entirely between
   the budget and 5× points. Both stay well inside the ratified ±1 LSB
   INL window at every point tested here, so no ratified row is shown to
   fail — but the non-monotonic behavior is real and attributable to a
   specific modelling choice this record makes explicit: the R || L
   network's inductor is tuned to put the R-L corner at the 16 MHz bit
   clock (mirroring DR-0002's own `V_REF` network exactly), which makes the
   network a genuine, lightly-damped **resonant tank** with `C_dec`, not a
   simple single-pole RC. A real external decoupling network's parasitic
   inductance is unspecified in practice, so the exact per-code sign and
   magnitude found here is a property of *this* modelling choice, not a
   universal statement about any 220 Ω / 40 nF network — but "neither
   non-ideal point is near the ideal one" is robust across the choice.
3. **`vref_droop_mv` is unaffected (0.383 → 0.382 → 0.376 mV)**, confirming
   the `V_cm` network change is isolated from the `V_REF` network's own
   behavior — the two rails' budgets are independent, as this record's
   Derivation assumes.

**Conclusion**: the ideal-`V_cm`-source assumption every existing ADC-level
testbench makes is **not shown to be conservative** — it is a real,
now-quantified gap, not merely a documented one. This record does not
re-run `ENOB`/`SFDR` (both already fail for unrelated, tracked reasons at the
ratified design — DR-0025 — which would make a `V_cm`-attributable delta
impossible to isolate from the existing acquisition-RC/top-plate-parasitic
regression); `gain_err_lsb` and per-code `inl_t*_lsb` are the cleaner,
currently-passing metrics available for this sensitivity check.

## Alternatives considered

- **Assert the ideal-source assumption is conservative without measuring
  it.** Not chosen — this is exactly the unverified inference issue #259's
  proposal leaned on, and the sensitivity evidence above shows it is false
  at the derived budget, not merely unproven.
- **Derive `Z_vcm,max`/`C_dec,min` by directly reusing DR-0002's `V_REF`
  numbers (240 Ω / 40 nF) without a separate derivation.** Not chosen: `V_cm`
  and `V_REF` are switched onto the array by structurally different events
  (a per-bit engagement for `V_REF` vs. a whole-array release twice a
  conversion for `V_cm`), so reusing DR-0002's numbers verbatim would either
  overstate or understate the real requirement depending on which
  mechanism actually binds — and it would not have surfaced that `V_cm`'s
  ceiling is tighter for a structural reason, which is the finding worth
  recording.
- **Run the full ratified-row campaigns (`sim/adc-inl-dnl/`,
  `sim/adc-enob-fft/`, `sim/adc-power/`) at the real `V_cm` network, full
  PVT, as this record's own evidence.** Not chosen for this record's scope:
  those campaigns are the ratified rows' own governing evidence and
  re-running all of them (63–117 points each, several ×) is a properly
  separate, larger follow-up once this record's derivation and the
  reduced-grid sensitivity check above establish that the exercise is
  worth the cost. The reduced 7-corner, nominal-T/V, three-network-point
  sweep this record cites is sized to answer this record's own question
  ("is the assumption conservative?") without pre-committing the larger
  campaign's scope.

## Consequences

- **Every existing ADC-level `sim/` record (`sim/adc-inl-dnl/`,
  `sim/adc-enob-fft/`, `sim/adc-power/`, and everything downstream of them
  in `sim/characterization-summary.md`) should be read as "achievable under
  a real `V_cm` network meeting this record's ≤ 220 Ω / ≥ 40 nF budget", not
  as "insensitive to `V_cm`'s source impedance."** No ratified row is shown
  to fail by this record — the shifts measured above stay inside every
  ratified window tested — but the assumption itself is no longer
  cost-free, and a future re-run of the ratified campaigns against the real
  network (full PVT, all three ADC-level decks) is now a well-motivated,
  explicitly named follow-up rather than an open-ended "someday."
- **A new external pin's worth of drive requirement is added to `V_cm`**,
  parallel to `V_REF`'s (DR-0002): whatever supplies `V_cm` (an external pin,
  or a future on-chip generator per DR-0011's still-open scope question)
  must meet `Z_vcm ≤ 220 Ω` / `C_dec ≥ 40 nF`, a real, stated design cost —
  not a free assumption.
- **Issue #259's Chipalooza Challenge #3 proposal's `V_cm`-pad justification
  is now backed by a derivation** (this record) instead of an inference —
  the proposal's own follow-up work should cite this record rather than
  re-deriving or re-asserting the requirement.
- **2 MS/s stretch**: at 2 MS/s the bit cycle halves to 31.25 ns, roughly
  halving `Z_vcm,max` to ≈ 112 Ω, mirroring DR-0002's own 2 MS/s note for
  `V_REF`. Not further resolved here.
- **The resonance caveat in the Evidence section is itself a stated
  limitation of this record's own modelling choice** (the R-L corner
  placement), not of the derived budget — a future record characterizing a
  *specific* real decoupling network's parasitic inductance could refine
  the per-code finding without changing `Z_vcm,max`/`C_dec,min` themselves.

## Spec lines affected

- `README.md#target-specification` — `V_CM` — new: no explicit `V_CM` drive
  row exists in the current table; this adds one — `V_cm = V_REF/2`,
  external pin (or future on-chip generator, DR-0011), external decoupling
  ≥ 40 nF, effective source impedance ≤ 220 Ω in the switching band.
