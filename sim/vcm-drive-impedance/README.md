# `sim/vcm-drive-impedance/` — is the ideal-`V_cm`-source assumption conservative?

**This experiment is a sensitivity check, not a re-verification of a ratified
spec row.** It measures `sim/adc-inl-dnl/`'s own converter-level metrics
(`gain_err_lsb`, `inl_t*_lsb` — its own `gain_err_lsb` check explicitly
states these are **not** the ratified `Gain error, systematic` row) with the
ideal `V_cm` source replaced by a real drive-impedance / decoupling network,
at and beyond
[DR-0026](../../spec/decision-records/DR-0026-vcm-drive-source.md)'s derived
budget.

## Why it exists

Every ADC-level testbench in this repo (`sim/adc-inl-dnl/`,
`sim/adc-enob-fft/`, `sim/adc-power/`) sources `V_cm` from an ideal,
zero-impedance DC source and says so in its own text: *"V_cm generation is
explicitly unbudgeted work … so there is no ratified envelope to model it
against and it is an IDEAL source here."* DR-0002 derived a
drive-impedance/decoupling budget for the analogous `V_REF` rail; `V_cm` had
no equivalent (issue #260). DR-0026 derives one. This experiment answers the
question DR-0026's own Evidence section needs an answer to: is the
ideal-source assumption every existing record already makes actually
conservative once a real network at the derived budget is modelled?

## What is swept, and what is held

The netlist for every non-ideal point is
`sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice` (the SAME committed,
ratified deck `sim/adc-inl-dnl/`'s own records use) with its one ideal
`V_cm` source line (`vcms vcmn 0 dc {vcm}`) replaced by
[`gen_vcm_variant.py`](gen_vcm_variant.py) with a real network: an ideal
source behind a resistor `R` in parallel with an inductor `L` (DC-accurate,
resistive at the switching band — modelled exactly the way this same deck
already models `V_REF`, DR-0002's `vrefs`/`rref`/`lref`/`cref` block) feeding
a decoupling capacitor `C_dec` to ground. `gen_vcm_variant.py` patches only
that one line and asserts a hit count, so a future edit to the baseline deck
breaks the substitution loudly instead of silently patching nothing (the
same discipline `sim/dr0019-cu-sweep/gen_cu_variant.py` uses for its own
single-line substitution).

Everything else — the array, the switches, the comparator, the SAR
controller, the `V_REF` network, the input schedule, the shadow-DAC error
node — is bit-identical to `sim/adc-inl-dnl/`'s own ratified deck.

### The three points

| Tag | Z_vcm | C_dec | What it is |
|---|---|---|---|
| `ideal` | 0 Ω | ∞ (ideal source) | **Not a generated variant at all** — the unmodified checked-in `sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice`, i.e. the assumption every existing ADC-level record already makes |
| `budget` | 220 Ω | 40 nF | DR-0026's derived, provisioned envelope (`Z_vcm,max ≤ 220 Ω`, `C_dec,min ≥ 40 nF`) |
| `5x-over-budget` | 1100 Ω | 40 nF | A deliberate point beyond the derived ceiling, so a single at-budget point cannot by itself hide whether the ceiling is doing any work |

### Re-running it

```bash
./sim/vcm-drive-impedance/run_sweep.sh                    # the whole sweep
./sim/vcm-drive-impedance/run_sweep.sh budget             # one point only
```

Each point is a 7-corner (`cdac` process axis) run at nominal temperature
(27 °C) and supply (3.30 V) — a deliberately reduced grid, justified in each
record's own `--subset-reason`: this is an exploratory sensitivity sweep for
a new decision record's derivation, not a re-verification of a ratified
spec-line campaign. Wall time: a few minutes per point uncontended.

## Findings (at `tt_27c_3.30v`)

| Point | `gain_err_lsb` | `inl_t256_lsb` | `inl_t768_lsb` | `vref_droop_mv` |
|---|---|---|---|---|
| `ideal` | −2.005 | −0.0134 | −0.0020 | 0.383 |
| `budget` | −2.205 | −0.2805 | −0.0549 | 0.382 |
| `5x-over-budget` | −2.312 | −0.0980 | +0.1116 | 0.376 |

(Full corner tables: `records/20260825-162620-e09a2d0.md` (`ideal`),
`20260825-163251-cb36f0a.md` (`budget`), `20260825-163508-64203b5.md`
(`5x-over-budget`).)

- **`gain_err_lsb` moves monotonically in magnitude with `Z_vcm`** — a real,
  non-negligible ≈ 0.2 LSB (≈ 10 %) shift at the derived budget alone, and
  more beyond it. **The ideal-source assumption is not shown to be
  conservative.**
- **Individual code errors move by more, and not monotonically** —
  `inl_t256_lsb` swings 21× at the budget point then partially recovers at
  5×; `inl_t768_lsb` changes sign between the two non-ideal points. Both
  stay well inside the ratified ±1 LSB INL window at every point tested
  here. The non-monotonicity is attributed to a stated modelling choice
  (the R || L network's inductor is tuned to the 16 MHz bit clock, making
  it a lightly-damped resonant tank with `C_dec`, not a simple RC) rather
  than to the derived budget itself — see DR-0026's Evidence section for
  the full discussion.
- **`vref_droop_mv` is unaffected** (0.383 → 0.382 → 0.376 mV) — the `V_cm`
  network change is isolated from `V_REF`'s own behavior, confirming the
  two rails' budgets are independent.

**No ratified spec row is shown to fail by this experiment.** What changes
is how every existing ADC-level record's ideal-`V_cm` assumption should be
read: as "achievable under a real network meeting DR-0026's budget," not as
"insensitive to `V_cm`'s source impedance." A full re-run of the ratified
campaigns (`sim/adc-inl-dnl/`, `sim/adc-enob-fft/`, `sim/adc-power/`) against
the real network, at full PVT, is a well-motivated follow-up this experiment
does not itself attempt — see DR-0026's Alternatives considered.

## Why not ENOB/SFDR

Those rows already fail for unrelated, tracked reasons at the ratified
design ([DR-0025](../../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md),
`sim/adc-enob-fft/`), which would make a `V_cm`-attributable delta
impossible to isolate from the existing acquisition-RC/top-plate-parasitic
regression. `gain_err_lsb` and the endpoint-adjacent `inl_t*_lsb` values are
the cleaner, currently-passing metrics this experiment uses instead.
