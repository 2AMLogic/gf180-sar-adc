# Testbench-suite methodology memo — one testbench per spec line

**Issue**: #13. **Status**: methodology ratified here; per-row evidence linked
from §2. This memo does not re-derive any upstream budget — it turns
#8/#9/#10/#11's ratified numbers and #12's closed timing budget into a
runnable, corner-swept verification matrix, and states the methodology choices
that matrix rests on.

> **Headline, so it is not buried in §11 — superseded once, and this is the
> current state (#61, 2026-08-02).** The suite has now been run twice: once on
> the DR-0011 top-plate-sampling converter, where INL, ENOB and SFDR all
> failed and all three traced to one mechanism (the voltage dependence of
> top-plate parasitic loading), and again on the
> [DR-0014](decision-records/DR-0014-bottom-plate-sampling.md) bottom-plate-
> sampling converter #60 built. **Two of those three rows now pass and one
> still fails.** INL is 0.108 LSB worst against < 1 LSB (was −4.494), ENOB is
> 9.163 bits against > 9.0 (was 8.005), and **SFDR is 61.33 dB against ≥ 62 dB
> — still failing, by 0.67 dB, at one corner of nine** (was 52.01 dB). DNL,
> power, the conversion-rate closure and the `Gain error, systematic` row pass.
> Nothing here relaxes a ratified bound to make a result pass, and nothing in
> the still-failing row is patched: §11.2 reports it as a failure and names
> what would have to change to close it.
>
> Both runs are kept. The DR-0011 records are retained unedited as the measured
> evidence DR-0014's Context rests on (`sim/` is append-only); every DR-0014
> record carries a `Supersedes` pointer to its predecessor. Where a number
> below is the *superseded* one, this memo says so at the point of use rather
> than rewriting history — including §3.5's original attribution of the
> parasitic to the preamplifier, which the measurement then corrected to 66 %
> sampling switch / 34 % comparator.

`CLAUDE.md` commits this repo to *no claim without a testbench* and to *PVT
corners on every recorded result*. This memo is the aggregation gate for that
commitment: it maps every row of the ratified target-specification table
(`README.md#target-specification`, DR-0006) onto a testbench and a recorded
corner result under `sim/`, and it states — explicitly, not by implication —
the four methodology choices that decide whether those results mean what they
appear to mean:

1. which codes the static-linearity sweep actually exercises, and why that set
   is the right one for **this** array (§3);
2. the coherent-sampling parameters, and why `window = none` is valid (§4);
3. the two-stage corner strategy, and whether the linearity-worst and
   noise-worst corners coincide (§5);
4. the noise-verification path this suite's schedule absorbs, with its measured
   cost, and the condition under which the expensive path returns (§7).

---

## 1. What this suite is, and what it is not

Three new testbenches are added by this issue, and one more by #61 when DR-0014
required four terms to be measured that no existing deck covered. Everything
else in the coverage map is **reused, not reimplemented** — a second,
independently-authored closure of a claim another issue already closed is a
duplication risk, not added rigor.

| New here | Slug | Substantiates |
|---|---|---|
| Static linearity | `sim/adc-inl-dnl/` | INL / DNL row (nominal design over PVT) |
| Dynamic performance | `sim/adc-enob-fft/` | ENOB and SFDR rows (distortion half) |
| Power | `sim/adc-power/` | Power @ 1 MS/s row, broken down by block |
| *(added by #61)* DR-0014's four assumed-away terms | `sim/dr0014-sampling/` | no ratified row of its own — the measurements DR-0014's Consequences require, plus the re-taken Input-structure `R_on` and the sampling path's own gain and linearity |

All four are generated from one source of truth,
`design/adc-top/gen_adc_top.py`, and all four instantiate the **same**
converter: DR-0013's input drive network, DR-0011's 512-unit-per-side MiM array
with real T-gate bottom-plate switches and real local drivers — **four legs per
cell under [DR-0014](decision-records/DR-0014-bottom-plate-sampling.md), the
fourth carrying `V_in`** — DR-0014's per-side top-plate `V_cm` switch and its
two-phase sample, DR-0007's static-preamp + StrongARM comparator, and the
rung-1 SAR controller `sim/sar-logic-functional/` verified. There is no longer a
dedicated, dummy-compensated input sampling switch: DR-0014 removed it, and
`sim/tests/test_adc_top_netlist.py` asserts no deck instantiates one. Everything in the
analog signal path is transistor level; only the sequencer and the output
register are ideal, which is exactly the rung DR-0010's fidelity ladder assigns
to this campaign type.

`sim/harness/testbench.py` rejects `.include` inside a testbench fragment (the
harness owns the includes so one fragment can sweep the whole grid unedited), so
each deck has to carry the whole DUT inline. `sim/tests/test_adc_top_netlist.py`
fails CI if any committed copy stops matching the generator — a testbench that
has quietly drifted from the design it claims to verify still passes, and
certifies a circuit that is no longer in `design/`.

**This suite verifies the nominal design.** Mismatch is off (`sw_stat_mismatch
= 0`, the harness default) and PVT moves. The statistical half —
device-to-device mismatch with PVT held at nominal — is #14's, in
`sim/mc-cdac-mismatch/`, `sim/comparator-offset-mc/` and
`sim/comparator-offset-gof/`. §6 states that division of labor in full.

---

## 2. Coverage map: every ratified row → a testbench and a record

Rows are those of `README.md#target-specification` as ratified in DR-0006, plus
the `Gain error, systematic` row DR-0012/DR-0013 added (#39).

| Spec row | Testbench | Record | Owner |
|---|---|---|---|
| Resolution | — (architectural: DR-0011 fixes the array, `sim/sar-logic-functional/` proves 10 bits are resolved) | `sim/sar-logic-functional/records/20260801-041242-96c2ea7.md` | #11 |
| Rate (1 MS/s) | `sim/timing-budget-closure/` — **reused, see §8** | `sim/timing-budget-closure/records/20260801-091939-7aa8ed7.md` | #12 |
| ENOB @ Nyquist | `sim/adc-enob-fft/` (distortion) **composed with** `sim/comparator-preamp-noise/` + `spec/cdac-sizing-memo.md` §1 (noise) — see §4.3 | `sim/adc-enob-fft/records/20260802-141402-1224e11.md` (supersedes `20260801-180501-845f76e`) + the preamp-noise record | **#13** → #61 |
| SFDR @ Nyquist | `sim/adc-enob-fft/` (whole converter); `sim/track-switch-thd/` (switch contribution alone) | `sim/adc-enob-fft/records/20260802-141402-1224e11.md` | **#13** → #61 |
| INL / DNL | `sim/adc-inl-dnl/` (nominal, PVT) + `sim/mc-cdac-mismatch/` (3σ mismatch) | `sim/adc-inl-dnl/records/20260802-141402-1224e11.md` (supersedes `20260801-144717-d407dfe`) + `sim/mc-cdac-mismatch/records/20260801-093800-c033611.md`; this row's own `klt yield` reformat (record `20260812-132011-f613571.md`) is PR #149's, tracked under issue #172 alongside the two rows below — not carried here | **#13** → #61 / #14 |
| Offset error | `sim/comparator-offset-mc/` + `sim/comparator-offset-gof/` | `sim/comparator-offset-gof/records/20260801-093644-c033611.md` + `sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md` (clean-tree `klt yield` evidence, issue #172) | #9 / #14 |
| Gain error, mismatch | `sim/mc-cdac-mismatch/` | `sim/mc-cdac-mismatch/records/20260801-093800-c033611.md` + `sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md` (`klt yield` evidence, issue #172) | #14 |
| Gain error, systematic | `sim/dr0014-sampling/` (the mechanism DR-0014 moved it to), corroborated end to end by `sim/adc-inl-dnl/`; `sim/track-switch-sampling/` re-taken for the drive network — **see §9** | `sim/dr0014-sampling/records/20260802-141402-1224e11.md` + `sim/track-switch-sampling/records/20260802-141402-1224e11.md` | #39 → **#13** → #61 |
| CMRR (differential) | `sim/comparator-offset-mc/` — **reused, see §10** | `sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md` (clean-tree `klt yield` evidence, issue #172; supersedes the §10 citation of `20260801-035221-90d7e67.md`) | #9 / #14 |
| Input (drive contract) | `sim/track-switch-sampling/` (the whole DR-0013 drive envelope) | `sim/track-switch-sampling/records/20260802-141402-1224e11.md` (supersedes `20260801-113511-c05043b`) | #39 |
| Input structure (C_in, R_on, T/H BW) | `sim/dr0014-sampling/` for the series `R_on` of the path DR-0014 built (nine parallel cell T-gates, not one dedicated switch); `sim/device-switch-ron/` for the device-level curve; C_in asserted against the array in `sim/tests/test_adc_top_netlist.py` | `sim/dr0014-sampling/records/20260802-141402-1224e11.md` + `sim/device-characterization-report.md` §2.1 | #4 / #10 / #61 |
| *(no ratified row)* DR-0014's four assumed-away terms | `sim/dr0014-sampling/` — top-plate switch injection and its side-to-side part, bottom-plate switch injection after that switch has opened, the fourth leg's settling cost, second-order `C_par`-mismatch residue | `sim/dr0014-sampling/records/20260802-141402-1224e11.md` | #61 |
| *(no ratified row)* Top-plate `C_par` decomposition | `sim/top-plate-cpar/` | `sim/top-plate-cpar/records/20260802-125708-1de758a.md` (supersedes `20260802-033948-75497e8`) | #53 → #61 |
| Reference (Z_ref, C_dec) | `sim/cdac-bit-settling/` | `sim/cdac-bit-settling/records/20260731-231537-1ee5578.md` | #8 |
| Clock (M = 16, jitter) | `sim/sar-logic-timing/`; jitter budget is analytic (DR-0003) | `sim/sar-logic-timing/records/20260801-033032-06bad60.md` | #11 |
| Supply (±10 %) | spanned by the supply axis of every corner sweep in this table | every record above | — |
| Latency / conversion timing | `sim/sar-logic-functional/` + `sim/sar-logic-timing/` | both records above | #11 |
| Power @ 1 MS/s | `sim/adc-power/` | `sim/adc-power/records/20260802-141402-1224e11.md` (supersedes `20260801-134035-7d48a44`) | **#13** → #61 |
| Area | — (layout-bound; #16/#17) | none — stated gap, not a silent one | #16 |
| Interface (parallel register) | `sim/sar-logic-functional/` | `sim/sar-logic-functional/records/20260801-041242-96c2ea7.md` | #11 (SPI deferred, DR-0005) |

Two rows carry an honest "no simulation is possible yet" rather than a
manufactured result:

- **Area** is layout-bound. There is no layout, so there is no measurement.
  #16 (floorplan) and #17 (post-layout re-run) own it.
- **Clock jitter** (≤ 250 ps rms) is a *specification on the user's clock
  source*, not a property of this block; DR-0003 derives the budget
  analytically. `sim/sar-logic-timing/` verifies what this block does own — that
  a 16-phase conversion completes deterministically.

### 2.1 Clean-tree citability of the records cited above

`sim/harness/README.md` makes a run taken against a dirty working tree
non-citable as a clean-tree result, and the record says so in its own
**Netlist provenance** field. Of the records this memo cites:

- **Clean-tree**: `adc-inl-dnl`, `adc-enob-fft`, `adc-power` (this issue's own,
  all minted after the testbenches were committed — and, at #61, all re-minted
  clean on the DR-0014 topology), `dr0014-sampling` and `top-plate-cpar` (#61's
  own, both clean), `track-switch-sampling`
  (§9), `timing-budget-closure`, `mc-cdac-mismatch`, `comparator-offset-gof`,
  `sar-logic-functional`, `sar-logic-timing`, `cdac-bit-settling`,
  `comparator-preamp-noise` (§7.3 — re-run clean by this issue, for the same
  reason §9 re-ran the gain-error row), and, as of issue #172 (2026-08-16),
  `comparator-offset-mc` — `sim/comparator-offset-mc/records/20260816-050001-d002e66.md`
  is a clean-tree, complete 45/45-corner re-run, reformatted into `klt yield`
  evidence by `20260816-050504-66a0e2e.md`; it supersedes the dirty-tree
  citation below for the Offset error and CMRR rows.
- **Dirty-tree, carried as such**: `comparator-regeneration`,
  `comparator-kickback`, `track-switch-thd`,
  `device-switch-ron`. These are #4/#9/#10's own deliverables, already merged
  and not modified here. Where a number from one of them is load-bearing for a
  claim in this suite, this memo says so at the point of use, and the *derived*
  claim is carried by a clean-tree record of this issue's own (e.g. the 863 ps
  comparator delay enters the Rate row through `sim/timing-budget-closure/`,
  which is itself clean).

---

## 3. Static linearity: the code set, targeted at DR-0011's own array

A full 1024-code transistor-level ramp, repeated over the PVT grid, is exactly
the cost problem this issue's original text flags. The methodology used is
`reduced-code-set-major-carry` (the tag is declared in the manifest's
`evidence` block and validated by `sim/harness/evidence.py`, so it cannot be
free text nobody notices), **targeted at the array DR-0011 actually ratified,
not at a plain binary-weighted array's mid-scale MSB carry.**

### 3.1 Why mid-scale is not this array's worst transition

DR-0011 ratifies MCS / V_cm switching with **top-plate sampling and a free
MSB**: the first bit trial is resolved with no array switching at all, and only
nine binary weights (256…1, 511 units, plus one terminating unit fixed to V_cm)
are switched per side. Consequences for the code set:

- **Mid-scale (511 → 512)** is the *free-MSB* transition. Every one of the nine
  switched weights changes state across it, but the **deciding** bit forms no
  charge-division ratio at all. It is a stress case for switching activity and
  for reference droop — worth probing — but it is not where the array's
  accuracy is decided.
- **The largest charge-division ratio the array actually forms is the
  sub-array MSB**: weight 256 against the remaining 255 units. That is
  transitions **255 → 256** and **767 → 768**, one in each MSB half.

Three independent lines of evidence point at the same weight, which is why this
memo treats it as the targeted worst case rather than an assumption:

| Source | Finding |
|---|---|
| `sim/cdac-bit-settling/` | `Ceq(w) = w(512−w)·C_u/512` is maximised at `w = 256` — the slowest-settling trial |
| `sim/mc-cdac-mismatch/` | the analytically worst code for mismatch is the same sub-array MSB carry |
| this deck | the deciding trial's own input-referred error is read at exactly those transitions |

### 3.2 The 18 probed transitions

```
1, 2            bottom endpoint (endpoint-fit anchor) + its DNL partner
128, 129        weight-128 carry
255, 256, 257   weight-256 sub-array MSB carry (predicted worst) and BOTH sides
384, 640, 896   further weight-128 / weight-64 carries spanning the range
511, 512, 513   the free-MSB transition and both sides
767, 768, 769   weight-256 carry in the MSB = 1 half
1022, 1023      top endpoint (endpoint-fit anchor) + its DNL partner
```

`sim/tests/test_adc_top_netlist.py` asserts this set still contains the
weight-256 carries from both sides, the free-MSB transition, and both
endpoints — so a later edit to the generator cannot silently retarget it.

### 3.3 One conversion per transition, not a search

The reason transistor-level INL/DNL is normally unaffordable is that *finding*
each code transition takes 10–100 conversions of bisection. This deck does not
search. It carries an **ideal shadow DAC** driven by the controller's own
switch-driver outputs, so at every comparator strobe the node `se_err` is
exactly the input-referred error that decision was taken with, in LSB:

```
err = [ (top_p − top_n) − ideal_residue(decisions so far) ] / LSB
```

A transition's voltage error *is*, by definition, the input-referred error at
the decision that resolves it. So each probed transition is read at its own
deciding trial (trial 1 for the free MSB, trial 2 for a weight-256 carry, …,
trial 10 for a weight-1 transition) from **one** conversion. INL is the
endpoint-corrected error; DNL between two probed neighbours is their
difference. Both are computed in the manifest's `measure` block from the
measured errors, so the numbers in the record are not a hand calculation
applied afterwards.

Because `err` is a difference between the **real** top plates and an ideal DAC
— not between two models — every mechanism that moves a real transition is
inside it: acquisition error, sampling-switch charge injection, incomplete
bit-cycle settling, reference movement through DR-0002's network, comparator
kickback into the top plate, and top-plate parasitic attenuation of the DAC
steps.

Two falsifiers guard the fine measurement, because a small error number alone
is not evidence that the converter works:

- **`code_t<k>`** — the converter must actually output code *k* for an input
  0.25 LSB above transition *k*'s ideal voltage. A 1 LSB-resolution end-to-end
  decision check.
- **`decerr_t<k>_lsb`** — the worst input-referred error over **all ten**
  decisions of that conversion (held by a track-and-hold opened by the
  comparator strobe, so it reports the error each decision was actually taken
  with and blanks the settling transient in between). This bounds the
  early-trial errors a plain-binary SAR with no redundancy (DR-0009) cannot
  recover from.

### 3.4 The one input-referred term deliberately outside `err`

The comparator's own input-referred **offset** is not in the error node. That
is deliberate and it is not a gap: a static offset is the ratified Offset row
(≤ 2 LSB, digitally removable, measured by `sim/comparator-offset-mc/`) and it
consumes no INL/DNL budget by construction. What *would* land here is any
**code-dependent** part of it. In differential mode DR-0011 holds the
comparator's input common mode constant for the whole conversion, so to first
order there is none; in single-ended mode the common-mode excursion is bounded
by `|V_in − V_cm|/2` and halves every trial. The measured size of that term is
`sim/comparator-offset-mc/`'s `mean_dvos_*` / `sig_dvos_*` pair over a ±50 mV
common-mode band: **≤ 0.067 µV systematic and ≤ 0.19 µV (1σ) mismatch**, i.e.
≤ 0.00006 LSB — three to four decades under the DNL budget. It is carried here
as a stated, quantified term rather than left implied.

### 3.5 A finding this deck produced: an unbudgeted top-plate gain error

The first corner this deck ran did not merely pass or fail — it produced a term
the ratified table has **no row for**, and it is recorded here rather than
absorbed.

**What was measured.** The transition errors `terr_t<k>_lsb` are not scattered:
they run almost exactly linearly with code, from about −13.9 LSB at code 1 to
about +17.1 LSB at code 1023 (`tt_27c_3.30v`), i.e. a **converter-level
systematic gain error of ~31 LSB ≈ 3.0 % of full scale**, with the transfer
curve crossing zero at mid-scale.

**Where it comes from.** DR-0011 ratifies **top-plate sampling**, and this deck
puts the comparator's inputs directly on that node — which is what a real
implementation of DR-0011 does. The input is sampled onto the top plate and is
*not* attenuated; each subsequent DAC step, however, is divided by the array
against everything else hanging on the top node:

```
ΔV_top = w·C_u·ΔV_bottom / (C_arr + C_par)
```

so the DAC's effective full scale is short by `C_par/(C_arr + C_par)`. At the
ratified `C_arr = 512·C_u = 8.827 pF`, the measured 3.0 % implies
`C_par ≈ 0.27 pF` — squarely the range a preamplifier input pair plus routing
puts on that node. This is a **first-order, architectural** consequence of
top-plate sampling, not a modelling artifact and not a switch effect.

> **Update (#53, 2026-08-02): the magnitude was right, the attribution was
> wrong, and the correction matters.** `sim/top-plate-cpar/`
> (`records/20260802-033948-75497e8.md`) measures the divider directly rather
> than backing it out of the gain error: `C_arr` = 8827.13 fF and `C_par` =
> 240.9–301.4 fF over 63 PVT points, a 2.42–3.66 % divider error against the
> 2.85–3.30 % this deck measures end to end — an independent confirmation from
> an unrelated testbench. But the decomposition shows the **sampling switch,
> not the comparator, is the larger half**: 194.3 fF (66 %) against 99.5 fF
> (34 %) at `tt_27c_3.30v`, because DR-0013's dummy-compensation devices sit in
> hold with source and drain both tied to the top plate. The sentence above,
> which reads the term as a preamplifier effect, is therefore the part of this
> memo #53 corrects; it is left standing rather than rewritten so the record of
> what was inferred, and what measurement then changed, stays legible.
> Adjudicated in [DR-0014](decision-records/DR-0014-bottom-plate-sampling.md):
> sample on the bottom plate, where the divider applies to the sampled input
> and the DAC step alike and cancels from the comparator's decision.

**Why it is not any existing row.** DR-0012 splits gain error into
`Gain error, mismatch` (3σ Monte Carlo, #14) and `Gain error, systematic`
(scoped by DR-0012/DR-0013 to the **sampling switch's** charge injection, and
measured at 0.421 LSB worst case by `sim/track-switch-sampling/`). Neither row
contains an allowance for top-plate parasitic loading; note **[e]**'s derivation
of the mismatch row explicitly states "it is one mechanism, and the row's value
equals it, so there is no headroom in it for a deterministic term."

**What this memo does and does not do about it.** `CLAUDE.md` is explicit that
agents do not relax a ratified spec to make results pass, and equally that spec
changes go through `spec/` with a decision record. So:

- the term is **measured and reported** (`gain_err_lsb`, per corner, in the
  record), with a bound loose enough to be a report rather than a verdict;
- the **INL bound is not widened** — `inl_t<k>_lsb` stays at the ratified 1 LSB,
  evaluated after gain and offset removal, which is the definition the ratified
  row's note **[d]** already uses;
- the **adjudication is deferred to a decision record**, and a follow-up issue
  is filed for it (**#53**). The two obvious resolutions are a compensating dummy
  capacitance on the top plate (trading area for gain accuracy) or an amended
  spec row that budgets a top-plate term explicitly; choosing between them is a
  design decision, not a testbench decision.

> **Update (#61, 2026-08-02): re-measured on the topology DR-0014 produced,
> the term is 15× smaller and no longer moves with the corner.**
> `sim/adc-inl-dnl/records/20260802-141402-1224e11.md` measures
> `gain_err_lsb` = **−1.997 … −2.014 LSB** over the same 27 points, i.e.
> **0.20 % of full scale** against the 2.85–3.30 % above; and
> `sim/top-plate-cpar/records/20260802-125708-1de758a.md` measures the divider
> that used to cause it at 0.586–2.162 % — still an order of magnitude larger
> than the residual gain error, which is the whole content of DR-0014's claim:
> the divider is still there and it no longer lands in the gain. The residual
> is also **flat across the PVT grid** — it varies by 0.9 % of itself, while
> the divider it would have to come from varies by a factor of 2.2 at the
> `V_cm` probe alone (0.704 % at `cap_ss_-40c_3.63v` to 1.577 % at
> `cap_ff_-40c_3.30v`). Whatever the residual 2 LSB is, it does not track
> `C_par`. It remains a term the ratified table has **no row for**, and none is
> added here.

**#53 is now closed and neither of those two is what it chose.**
[DR-0014](decision-records/DR-0014-bottom-plate-sampling.md) moves the sampling
phase to the bottom plates, keeping every other DR-0011 decision — MCS / V_cm
switching, 512 units per side, the free MSB, `C_in` = 8.827 pF — unchanged.
Under bottom-plate sampling the sampled input and the DAC steps share one
denominator, so `C_par` cancels from the comparator's decision rather than being
reduced, and **no ratified row is added, widened or relaxed**. The measured
compensation cost (5× array = 44 % of the area row, and still 6.8 LSB of
residual gain error) and the measured 34 % ceiling on what shielding the
comparator could buy are argued there against the Area, Power and ENOB rows.

**Two consequences inside this suite**, both stated at the point of use rather
than quietly absorbed:

1. `sim/adc-inl-dnl/`'s end-to-end `code_t<k>` check is a **liveness and
   tracking** check with a ±45 LSB window, not an exact-code check — the offset
   from the exact code *is* this gain term. `decerr_t<k>_lsb` carries the same
   window for the same reason: an early trial's residue carries the whole gain
   error.
2. `sim/adc-enob-fft/` drives **0.94 × half full scale (−0.54 dBFS)** rather
   than a true rail-to-rail sine. With a 3 % gain error a full-scale drive
   clips at both ends, and an FFT of a clipped capture reports clipping as
   distortion the block does not have.

---

## 4. Dynamic performance: coherent sampling, stated rather than asserted

### 4.1 The parameters

| Parameter | Value | Why |
|---|---|---|
| `f_s` | 1 MS/s | the ratified Rate row |
| `N` (record length) | 64 samples | a **power of two**, so the post-processor's FFT needs no zero padding — padding would itself destroy the coherence it is supposed to preserve. 64 rather than 128 is a **cost** decision, stated in §5: each captured conversion is 1 µs of transistor-level transient, and this deck is the single largest cost item in the suite |
| `M` (input cycles captured) | 31 | **prime**, hence coprime to any power of two |
| `f_in` | 484.375 kHz | `= M·f_s/N` |
| `f_in / f_Nyquist` | 0.969 | "near Nyquist", as the ratified ENOB and SFDR rows specify (`f_Nyquist = f_s/2 = 500 kHz`) |
| Amplitude | 0.94 × half full scale (−0.54 dBFS) | **not a habit — a measured necessity.** §4.5's top-plate gain error would clip a true rail-to-rail drive at both ends, and the FFT would then report clipping as distortion the block does not have. `analyze_fft.py` reports the dBFS shortfall per corner so it is visible rather than assumed |
| Window | `none` | see §4.2 |

### 4.2 Why `window = none` is valid here

Coherence is a property of two integers, and it is asserted as such
(`sim/tests/test_adc_top_netlist.py::CoherentSamplingTests`, and again inside
`analyze_fft.py` before it computes anything):

`gcd(31, 64) = 1`, so the 64 samples land on 64 **distinct** phases of the
input and the capture contains exactly 31 whole input periods. An integer
number of periods leaves **no discontinuity at the record boundary**. A window
is a repair for exactly that discontinuity; with none to repair, applying one
would spread the signal over three bins and *understate* SFDR. That is the
justification the original issue text's `window = none` requires — it is stated
here, not assumed.

### 4.3 What this FFT measures, and what it cannot

**ngspice injects no device noise into a transient analysis.** Noise enters a
transient only through explicit `trnoise` / `trrandom` sources, and this deck
has none. The non-signal bins of this FFT therefore contain **distortion,
settling error and quantization — and no thermal or flicker noise at all.**

Reporting an ENOB straight off this FFT would overstate it by omitting every
noise term in the ratified budget. So the ENOB claim is **composed**, and the
composition is stated here rather than buried:

| Term | Source | Value |
|---|---|---|
| Distortion + settling + quantization | this deck's FFT | measured per corner (§11) |
| Comparator input-referred noise | `sim/comparator-preamp-noise/` (ac-based `.noise`, §7) | 153.2 µV rms worst (`ff_125c_3.63v`) |
| Sampling `kT/C` | `spec/cdac-sizing-memo.md` §1, at the ratified `C_side = 512·C_u = 8.827 pF`, hot corner | `√(2kT/C_side)` = 35.3 µV rms @ 125 °C |
| **Composed non-quantization noise** | root-sum-square | **157.2 µV rms = 0.0488 LSB** (single-ended, `LSB = V_REF/1024 = 3.2227 mV`) |

That composed 0.157 mV rms sits **10.2× under** the ratified budget
(`σ_total ≤ 1.6113 mV rms` for ENOB > 9.0; 0.930 mV for the > 9.5 stretch — it
is 5.9× under the stretch too). `analyze_fft.py --sigma-extra-lsb 0.0488`
performs the composition against the measured spectrum; §11 reports the result.

The reference's noise share is **not** in this composition, and that is not an
omission: `README.md` note **[b]** makes V_REF noise user-supplied and
explicitly allocated (≤ 0.93 mV rms), not guaranteed by this block.

### 4.4 Post-processing, from the runner's own logs

A spectral figure of merit is not a scalar an ngspice `meas` can produce, so
the deck exports the code sequence as one `meas` per sample
(`m_code_s000 … m_code_s063`) and
`sim/adc-enob-fft/testbench/analyze_fft.py` computes SFDR / THD / SNDR / ENOB
from the **raw per-corner logs the corner runner wrote**. Nothing is
hand-entered. This is the same post-processing pattern, for the same reason, as
`sim/comparator-offset-gof/testbench/analyze_gof.py` — with one deliberate
difference: `analyze_fft.py` is **standard-library only** (it carries its own
40-line radix-2 FFT). The PDK-free CI path installs no dependencies, so a
numpy-dependent post-processor could not be regression-tested there;
`sim/tests/test_analyze_fft.py` pins the transform against cases with a
closed-form answer — an ideal 10-bit quantizer must measure 61.96 dB, an
injected −40 dBc harmonic must appear at the folded bin the arithmetic
predicts, and the noise composition handed `1/√12` LSB against an unquantized
sine must reproduce quantization itself. A spectral post-processor is exactly
the kind of code that yields a plausible number from a wrong normalisation with
no second measurement to disagree with it.

Two coverage witnesses are checked *inside* the manifest, so a degenerate
capture cannot silently produce a plausible-looking spectrum: `code_max` and
`code_min` assert the full-scale sine actually drove the converter to within a
few LSB of both rails.

---

## 5. The two-stage corner strategy, and whether the worst corners coincide

**The strategy.** Sweep a full PVT grid with the cheaper static-linearity and
power decks; spend the expensive dynamic run only at the corners those sweeps
and `sim/comparator-preamp-noise/` identify.

**The cost that forces it, measured rather than assumed.** One PVT point of
these decks is a complete transistor-level transient of the whole converter —
CDAC, switches, drivers, comparator — at 1 µs per conversion:

| Deck | Transient | Wall time per point (measured, on a contended host) |
|---|---|---|
| `sim/adc-power/` | 17 conversions (17 µs) | ~20 min |
| `sim/adc-inl-dnl/` | 20 conversions (20 µs) | ~22 min |
| `sim/adc-enob-fft/` | 66 conversions (66 µs) | ~70 min |

Both full-grid decks spend exactly **one** conversion per measured point. An
earlier draft spent a second, un-measured conversion re-acquiring each input
level — doubling the cost of the most expensive deck in the suite to buy
0.006 LSB (the input steps 10 ns before the conversion boundary and the
4-clock sample phase is 250 ns = 10 τ of DR-0013's 25 ns network, against a
largest ladder step of 126 LSB). It also made the deck *less* representative:
converting the same code twice in a row lets DR-0002's reference network
(τ = 9.6 µs, which never settles between conversions in any case) see a repeat
it would never see in service.

**Grids actually run**, with the reason for each:

| Deck | Grid | Points |
|---|---|---|
| `sim/adc-inl-dnl/` | process `tt, ss, ff` × 3 temperatures × 3 supplies | 27 |
| `sim/adc-power/` | same | 27 |
| `sim/adc-enob-fft/` | process `tt, ss, ff` × 125 °C × 3 supplies | 9 |

`tt`/`ss`/`ff` are the harness's **all-family** bundles: each one skews every
device family together, **including both capacitor families** (`ss` binds
`moscap_ss` + `mimcap_ss`, `ff` binds `moscap_ff` + `mimcap_ff` — see any
record's "Per-corner model sections used" table). So the MiM unit capacitor —
which every claim in this suite rides on, and which a MOS-only sweep would
leave at typical (`sim/harness/README.md`, "Why the capacitor corners matter
here") — **is** swept here, at its combined worst case with the MOS skew. The
dedicated `mim_ss`/`mim_ff` corners would *isolate* the MiM contribution rather
than worsen it, which is a decomposition question, not a pass/fail one, and is
left to a fuller campaign (#17's post-layout re-run runs this same suite again).

Three process corners × all three temperatures × all three supplies is a full
mandated matrix by the harness's own rule, so the two 27-point grids need no
subset justification. The dynamic deck's single-temperature grid does, and
carries one (`--subset-reason`, copied verbatim into its record).

**The trap the original issue text names, and how it is avoided.** "At the
worst corners identified by the static runs" is only valid if the
linearity-worst corner and the dynamic-worst corner coincide. They need not:
CDAC settling (the dominant INL/DNL term, #8) and comparator noise (the
dominant ENOB term, #9) are different mechanisms with different corner
dependence. **This memo does not assume they coincide. It checks.**

`sim/comparator-preamp-noise/` independently identifies the noise-worst corner
over its own 45-point grid: input-referred noise rises monotonically with
temperature and with process speed, worst at **`ff_125c_3.63v`**
(153.2 µV rms) and best at `ss_-40c_2.97v` (76.9 µV rms) — a 2× spread. The
settling-worst corner named by every upstream record (`sim/device-switch-ron/`,
`spec/cdac-sizing-memo.md`, `sim/comparator-regeneration/`, and the ratified
Rate row itself) is **`ss_125c_2.97v`** — slow process, hot, low supply. **They
are opposite corners of the process axis.**

So the dynamic deck is run at **both**, plus nominal:

So the dynamic deck's grid is chosen to contain **both**, plus a reference:

| Corner | Why it is in the dynamic set |
|---|---|
| `ss_125c_2.97v` | settling/linearity-worst — the corner the ratified Rate row binds at |
| `ff_125c_3.63v` | **noise-worst**, identified independently by `sim/comparator-preamp-noise/`, *not* inherited from the static sweep |
| `tt_125c_*`, and both other supplies at `ss`/`ff` | the reference point, and the full supply axis, so the corner deltas are readable and the supply axis is genuinely swept rather than pinned |

Only the **temperature** axis is reduced (to 125 °C, the temperature both
identified worst corners sit at). That subset is declared to the runner with
`--subset-reason`, which `sim/harness/README.md` requires and copies verbatim
into the record — an unexplained subset is not a valid record.

---

## 6. Division of labor with #14 (nominal vs. statistical)

Stated here from this issue's side; `spec/monte-carlo-methodology-memo.md` §4
states the identical division from #14's side. Neither campaign substitutes for
the other, and neither duplicates the other's expensive sweep.

| | This suite (#13) | Monte Carlo (#14) |
|---|---|---|
| Question | does *this exact, nominal* design meet spec across environmental conditions? | given that nominal design, how much does device-to-device **mismatch** spread the same figures? |
| Mismatch | **off** (`sw_stat_mismatch = 0`, harness default) | **on** |
| PVT | **swept** (63-point `cdac` grid) | **held at nominal** |
| INL/DNL evidence | `sim/adc-inl-dnl/` — 18 transitions, transistor level, per corner | `sim/mc-cdac-mismatch/` — full-code analytic array model, N draws at nominal PVT |
| Rows it closes | INL/DNL (environmental half), ENOB, SFDR, Power, Gain error **systematic** | INL/DNL (3σ half), Offset, Gain error **mismatch**, CMRR |

The quantitative reason a nominal-PVT-only mismatch sweep is a valid substitute
for a mismatch-at-every-corner campaign — rather than merely a convenient
shortcut — is `sim/cdac-bit-settling/` §5.3's independent finding that global
process variation **cancels exactly** in the charge-division ratio INL/DNL
depend on. That is why there is no third, combined campaign, and why the
absence of one is not a coverage gap.

Explicitly: **no full-code transistor-level sweep is run twice.** This suite
runs 18 targeted transitions at transistor level over 63 corners; #14 runs all
1024 codes through an analytic array model at one corner. Running either
campaign's method at the other's scope would multiply cost by ~50× and change
no number.

---

## 7. Noise verification: which path, what it cost, and what would bring the expensive one back

### 7.1 The path taken — verified against #9's merged decision record, not assumed

`spec/decision-records/DR-0015-comparator-topology.md` (merged in PR #45,
closing #9) ratifies a **static preamplifier + StrongARM latch**, not a bare
dynamic latch. That is what makes the cheap path legal:

- **Method: `ac-based`.** ngspice `.noise` on the preamplifier about a **real
  DC operating point**, with the latch instantiated in reset so its input
  capacitance loads the preamp. The reported figure is the total integrated
  **output** noise divided by the measured DC gain.
- **Measured cost on this repo's own throughput: 45 PVT points in 318 s**
  (`sim/comparator-preamp-noise/`, Wall time field). Against an
  order-of-magnitude estimate of **~250 CPU-hours** for the `trnoise` transient
  Monte Carlo path not taken (10³–10⁴ transient runs per corner, per the
  prior-art survey §8), that is a ~2800× saving. **The schedule check this
  issue's curation demanded therefore passes trivially**: the noise campaign is
  not a constraint on the #2 batch runner's capacity at all — the three new
  transient decks in §1 dominate this suite's cost by orders of magnitude.

### 7.2 What would bring the expensive path back

**The cheap path is conditional on DR-0007 standing.** If a later decision
record supersedes it with a *dynamic* topology (bare StrongARM, double-tail,
dynamic preamp), `.noise` no longer applies — there is no DC operating point to
analyse around — and the full `trnoise` Monte Carlo campaign returns, with it a
batch-runner throughput check against #2. As of this memo, DR-0007 stands and
is not superseded; the check performed was to read the merged decision record,
not to inherit this issue's pre-merge guidance.

### 7.3 The latch's own noise is bounded, not measured

No ngspice analysis can measure it: `.noise` needs a DC point a
reset-and-regenerate structure does not have, and ngspice injects no
device-level noise into a transient absent explicit `trnoise`/`trrandom`
sources. `spec/comparator-budget-memo.md` §8.1 bounds it **analytically** as a
minority term after gain division. It is carried in this suite as a stated
assumption, not as a sim result.

The preamp-noise record this memo composes the ENOB claim from was originally
taken against a dirty working tree (`20260801-035352-90d7e67`) and is therefore
not clean-tree citable. Because that number is load-bearing for this issue's
headline ENOB claim, and because the run costs ~5 minutes, it is **re-run clean
here** by the same reuse-not-duplicate pattern §9 applies to the gain-error row:
the testbench and methodology are #9's, unmodified; only a clean-tree run was
missing.

- **Clean-tree record**: `sim/comparator-preamp-noise/records/20260801-123440-033b56b.md`
  (git `033b56b…` on `feature/issue-13`, **clean**; 45 points, PASS)
- The numbers are **identical** to the dirty-tree run — which is the expected
  outcome, and worth stating rather than glossing: the state of the working
  tree does not enter the simulation, only the citability of the record. So
  this is not a *correction* of `20260801-035352-90d7e67` (which is why it
  carries no `Supersedes`) — it is the same measurement, taken so it can be
  cited.

### 7.4 Two ngspice measurement traps, regression-tested rather than remembered

Both are inherited from #9 and both are checked by the manifests in this suite
so they cannot silently recur:

1. **`onoise_total` / `inoise_total` are rms volts, not noise power.** Taking
   their square root understates noise by ~2 decades. #9 verified the units
   independently against an ideal 1 kΩ resistor (4.0693 nV/√Hz flat over
   1 Hz–1 GHz → `onoise_total = 1.2868e-4` = `4.0693e-9 × √1e9` exactly).
2. **The input-referred noise integral does not converge** for a band-limited
   amplifier swept to high frequency — above the amplifier's bandwidth the gain
   rolls off and ngspice's input-referred density diverges. The correct
   quantity is the **output** noise integral, referred back by the measured DC
   gain. `sim/comparator-preamp-noise/`'s manifest keeps the divergent
   `inoise_band_uv` in the record *specifically* as the visible witness of that
   trap, next to the correct `vn_in_uv`.

A third trap, from the harness rather than from ngspice, applies to this
suite's own decks: **a `meas` result is carried at ~6 significant digits, so a
quantity read off a node biased near mid-rail is quantized to ~1 µV before any
`measure` expression sees it** (`sim/harness/README.md`, "The `meas`
result-precision floor"; the correction that established it is #46). All three
new decks avoid it structurally by measuring an error node referenced to **0 V**
rather than differencing two mid-rail levels, so the six significant digits land
on the effect rather than on the bias point. Where a bounded quantity from
another record is reused — notably `sim/comparator-kickback/`'s top-plate
disturbance — it is carried as a **resolution-limited bound (< 1 LSB, ~1 µV
`meas`-precision floor), not as a point value**, per #46.

---

## 8. Conversion rate: #12's testbench is *reused*, not extended

The Rate row's evidence is `sim/timing-budget-closure/` — #12's own worst-corner
timing closure, **referenced, not reimplemented**. This issue does **not** stand
up a second conversion-rate testbench, for the reason the issue's own curation
gives: two independently-authored timing closures for the same claim are a
duplication risk, not added rigor.

What #12's record already closes:

- `T_bitcycle = T_CDAC_settle (#8) + T_comparator_regen (#9, measured) +
  T_logic_delay` inside the 62.5 ns bit cycle at 1 MS/s, with the comparator's
  **863 ps** worst-case decision delay at half-LSB overdrive
  (`ss_125c_2.97v`, `sim/comparator-regeneration/`) taken as a fixed measured
  term rather than re-derived here;
- a negative control at every rate bracket, so the passes are falsifiable;
- the one open term (SAR logic propagation delay, DR-0010 rung 3, blocked on the
  open gf180mcu PDK shipping no 3.3 V standard-cell library) swept as a
  candidate range rather than asserted.

**What this suite adds to it, and why that is not an extension of #12's claim.**
The three new decks in §1 run a *complete* conversion at the ratified 62.5 ns
bit cycle with the real CDAC, real switches and the real comparator in the loop.
They therefore constitute an **independent corroboration** of #12's closure: if
the bit cycle were too short at any corner, the `code_t<k>` end-to-end decision
checks in `sim/adc-inl-dnl/` and the `code_max`/`code_min` coverage witnesses in
`sim/adc-enob-fft/` would fail there. That is a *consequence* of running these
decks, not a re-derivation of the timing budget, and the Rate row's citation
stays #12's record.

---

## 9. `Gain error, systematic`: reused testbench, clean-tree re-run

DR-0012 split the ratified "Gain error" row into `Gain error, mismatch` (3σ
Monte Carlo — #14's domain) and `Gain error, systematic` (full PVT grid, zero
mismatch, at the DR-0013 input drive network — this suite's domain, by the same
nominal-vs-statistical division §6 states for INL/DNL).

A full-PVT-grid testbench for that row already existed:
`sim/track-switch-sampling/testbench/tb_track_sampling.spice`. It is **reused
unmodified** — no second, independently-authored gain-error testbench was
written.

The record PR #47 cited (`20260801-080221-fa8fd37`) states in its own header
that it was taken against a dirty working tree and is **not citable as a
clean-tree result**. No later record superseded it, so the testbench was re-run
clean:

- **Record**: `sim/track-switch-sampling/records/20260801-113511-c05043b.md`
- **Provenance**: git `c05043b…` on `feature/issue-13`, **clean**; toolchain
  pins satisfied
- **Grid**: 117 points (13 process corners × 3 temperatures × 3 supplies) — the
  full-factorial `full` set, 117 completed
- **Result**: **PASS** at every point, against the ≤ 0.5 LSB row

### 9.1 DR-0014 moved this row's mechanism; the row's target did not move (#61)

DR-0014's Consequences say it directly: "the 0.421 LSB measurement behind it
was taken on a different sampling phase and must be re-taken." The **≤ 0.5 LSB
target is unchanged**; what changed is which device sets it. Under DR-0014 the
converter has **no dedicated input sampling switch at all** — the sampling
instant is set by the per-side top-plate `V_cm` switch one whole bit cycle
*before* the bottom plates leave `V_in`, and the input reaches the array
through the nine cell T-gates whose own injection lands on plates that are
immediately driven to `V_cm`.

So the row is now carried by three measurements rather than one, and this memo
names all three rather than silently re-pointing the row:

| Measurement | Record | Result |
|---|---|---|
| The device that now defines the sampling instant: top-plate `V_cm` switch injection, and how much of it is **signal-dependent** | `sim/dr0014-sampling/` `tp_inj_*` | injection 0.0613–0.3018 LSB per side; its variation over the **full** input range is **0.0045–0.0088 LSB** — an offset, not a gain term |
| The sampled path end to end, endpoint-fitted | `sim/dr0014-sampling/` `samp_gain_err_lsb`, `samp_inl_worst_lsb` | `k` = 0.9874–0.9900 (the divider DR-0014 shows cancels); bow 0.0213–0.6903 LSB |
| The converter end to end | `sim/adc-inl-dnl/` `gain_err_lsb` | **−1.997 … −2.014 LSB**, flat over the grid |
| The old device, re-taken unchanged for comparison | `sim/track-switch-sampling/` `gain_s20_lsb` | **0.421653 LSB** at `ff_125c_3.63v` — bit-identical to the superseded record |

- **Record (#61 re-take)**:
  `sim/track-switch-sampling/records/20260802-141402-1224e11.md`, superseding
  `20260801-113511-c05043b`; 117 points, clean tree, **PASS** at every point.
  The deck is unmodified, so the number is unchanged to all printed digits —
  which is the reproducibility statement, and also the reason the re-take
  alone cannot close the row on the new topology.
- **Does DR-0013 still need its dummy devices?** DR-0014 asked, and the
  measurement answers it for the device that replaced them: `adc_tp_sw` is a
  plain T-gate, deliberately **not** dummy-compensated, and its injection is
  signal-independent to within 0.0088 LSB. Dummies exist to cancel the
  *signal-dependent* part of a sampling switch's injection; there is 0.0088 LSB
  of it to cancel here, against a ≤ 0.5 LSB row. On this evidence the dummies
  are not needed on the new switch. Whether DR-0013's own record should be
  amended is a decision-record matter, not a memo matter, and is **not** done
  here.
- **What this row's evidence does not cover** is device-to-device mismatch
  between the two sides, which is #14's Monte Carlo domain by §6's division.
  `sim/dr0014-sampling/` is the harness's nominal zero-mismatch case, so its
  `tp_inj_mis_l2_lsb` and `bp_inj_mis_lsb` at the `f = 0` level are **null
  controls that must read zero** (they read ≤ 9.3e-12 and ≤ 1e-8 LSB), not
  mismatch measurements. The signal-*driven* side-to-side asymmetry, which is
  deterministic and does land in a row, is ≤ 0.0064 LSB.

---

## 10. CMRR: reused, with its extrapolation stated

The ratified CMRR row (≥ 60 dB, ≥ 65 dB stretch, DC–Nyquist, over
`V_CM = V_REF/2 ± 100 mV`) binds at **3σ mismatch**, not at a PVT corner — so by
§6's division it is a statistical row. In a differential SAR whose CDAC is
symmetric by construction, the only common-mode-sensitive element is the
comparator, and `sim/comparator-offset-mc/` already measures exactly that: the
change in input-referred offset over a common-mode step, both its systematic
mean and its mismatch sigma, at all 45 PVT points.

| Quantity | Worst over the 45-point grid | Implied CMRR |
|---|---|---|
| Systematic Δoffset over ±50 mV CM (`mean_dvos_*`) | 0.0667 µV (`sf_125c_3.63v`) | **117.5 dB** |
| 3σ mismatch Δoffset over ±50 mV CM (`3 × sig_dvos_*`) | 0.561 µV (`tt_-40c_3.30v`) | **99.0 dB** |

Both are ≥ 34 dB above the ratified ≥ 60 dB target and ≥ 34 dB above the ≥ 65 dB
stretch.

**Stated limitation, not glossed:** the measured band is ±50 mV, the ratified
row specifies ±100 mV. CMRR is a *ratio*, so a first-order (linear)
common-mode sensitivity extrapolates unchanged; only a second-order term would
differ, and the ≥ 34 dB margin leaves room for a factor of 50 of it. A direct
±100 mV measurement is nonetheless the honest closure of this row and is not
performed here — see §12.

> **Superseded citation (issue #172, T1 item 6, 2026-08-16).** The two
> figures above were read from `sim/comparator-offset-mc/records/20260801-035221-90d7e67.md`,
> a grid with **7 of 45 corners errored** (`ss_-40c_*` exit −9; `sf_-40c_*`
> timeout) — it never reached `ss_-40c_3.63v`. A clean-tree, complete 45/45
> re-run (`sim/comparator-offset-mc/records/20260816-050001-d002e66.md`,
> reformatted into `klt yield` evidence by
> `sim/comparator-offset-mc/records/20260816-050504-66a0e2e.md`) finds
> `ss_-40c_3.63v` is the true worst corner for the mismatch term: systematic
> **118.2 dB** (was 117.5 dB, close), 3σ mismatch **85.6 dB** (was 99.0 dB —
> materially different because the prior worst-of-converged-corners citation
> never saw the true worst corner). **Both figures still clear the ratified
> ≥ 60 dB target by a large margin** (85.6 dB is 25.6 dB above baseline,
> 20.6 dB above the ≥ 65 dB stretch) — this is a correction to a
> previously-narrower citation, not a new finding that threatens the row.
> Per this memo's own "Both runs are kept" convention (top of file), the
> table above is retained unedited as the record of what was cited before;
> this note says so at the point of use rather than rewriting history.

---

## 11. Results

*(Per-corner results live in the append-only records under `sim/`; this section
summarises them and must never be read as a substitute for them.)*

### 11.1 Headline — the DR-0014 bottom-plate-sampling converter (#61)

Measured on the topology #60 built and PR #64 merged, all records clean-tree
and append-only, each superseding its DR-0011 predecessor. The predecessor's
number is carried in its own column so the delta is legible without opening
two records:

| Ratified row | Target | Measured (DR-0014, nominal design, schematic) | Verdict | Was (DR-0011, superseded) |
|---|---|---|---|---|
| DNL | < 1 LSB (< 0.5 stretch) | **0.100 LSB** worst (`tt_27c_2.97v`, pair 128/129) | **PASS** (stretch too) | 0.483 LSB — PASS |
| INL | < 1 LSB (< 0.5 stretch) | **0.108 LSB** worst (`ss_-40c_2.97v`, transition 384) | **PASS** (stretch too) | −4.494 LSB — **FAIL** |
| ENOB @ Nyquist | > 9.0 (> 9.5 stretch) | **9.163 bits** worst (`ss_125c_2.97v`) | **PASS** (not stretch) | 8.005 bits — **FAIL** |
| SFDR @ Nyquist | ≥ 62 dB (≥ 65 stretch) | **61.33 dB** worst (`ss_125c_2.97v`) | **FAIL** by 0.67 dB | 52.01 dB — **FAIL** |
| Power @ 1 MS/s | < 1 mW (< 500 µW stretch) | **183.3 µW** worst (`ff_-40c_3.63v`, mid-scale) | **PASS** (5.5×; stretch too) | 157.0 µW — PASS |
| Gain error, systematic — the row as DR-0012/DR-0013 **scoped** it: the sampling switch's own charge injection | ≤ 0.5 LSB | mechanism moved by DR-0014 (**§9.1**). The device that now defines the sampling instant contributes **0.0045–0.0088 LSB** of signal-dependent injection; the removed switch, re-measured unchanged, still reads 0.421 LSB | **PASS** | 0.421 LSB — PASS |
| Rate (1 MS/s) | closure at worst corner | #12's record, reused | **PASS** | unchanged |

Plus the measurement the ratified table has **no row for**, and the two
published Input-structure numbers DR-0014 required to be re-taken:

| Term | Measured (DR-0014) | Was (DR-0011) | Status |
|---|---|---|---|
| Converter-level systematic gain error | **−1.997 … −2.014 LSB** (0.20 % of full scale), flat over the grid | 29.2 … 33.8 LSB (2.85–3.30 %) | still unbudgeted; **15× smaller**, and no row is added — §3.5 |

**Read the gain-error row and the gain-error term together, not as one number.**
`Gain error, systematic` is scoped by DR-0012/DR-0013 to the *sampling switch's
charge injection*, and §3.5 already established — before DR-0014 — that the
converter-level term is **not** that row and has no row of its own. That has not
changed, and this memo is not quietly re-pointing a ≤ 0.5 LSB row at a −2 LSB
measurement in either direction: the row passes on its own scope, and the
converter-level 2 LSB stays reported as unbudgeted. A reader who wants a single
end-to-end gain number should take the −2.0 LSB, and note that no ratified row
bounds it.
| Top-plate `C_par` | **57.2 … 175.4 fF**, of which the top-plate `V_cm` switch is 16.0–19.0 fF | 240.9 … 301.4 fF, of which the sampling switch's DR-0013 dummies were 194.3 fF (66 %) | characterization — `sim/top-plate-cpar/` |
| Input-structure series `R_on` | **21.3 … 60.0 Ω** (nine parallel cell T-gates per side; 119.8–540.2 Ω per single cell T-gate) | 156–570 Ω (one dedicated switch, now removed) | published row is stale — see §11.4 |
| Input-structure `C_in` | 8.827 pF per side — **unchanged**, as DR-0014 said it would be | 8.827 pF | row stands |

### 11.2 The one row that still fails, reported rather than closed

**SFDR misses ≥ 62 dB by 0.67 dB, at one corner of the nine.** The other eight
span 63.62–69.98 dB. This section states what the measurement shows and what it
does not, and deliberately stops short of changing anything to close the gap —
`CLAUDE.md` forbids relaxing a ratified row, and tuning a testbench until a row
passes is the same act wearing a different hat.

- **The mechanism that caused the old failure is gone.** Under DR-0011 all three
  dynamic and static failures were one thing: the voltage dependence of
  `C_arr/(C_arr + C_par)` bowing the transfer curve — the diagnosis this
  section carried before #61, and which the superseded records still hold the
  numbers for. That bow is measured by the
  endpoint-referred transition errors, and it has collapsed: at
  `tt_-40c_3.30v`, `terr_t1_lsb` = **+1.0198** and `terr_t1023_lsb` =
  **−0.9802**, against −13.5686 and +17.7497 before. The two halves of the
  transfer curve no longer have different gains, which is why INL falls from
  −4.494 LSB to 0.108 LSB.
- **THD confirms it in the spectrum**: −58.53 to −67.27 dBc across the dynamic
  grid, against −50.18 to −53.34 dBc before — a 8–14 dB improvement, and the
  reason ENOB clears its row.
- **What is left is the ACQUISITION's own nonlinearity, and two independent
  decks say so.** Across the nine dynamic points, SFDR does **not** order with
  static INL (which is flat at 0.092–0.104 LSB) and it is not settling (which
  `sim/dr0014-sampling/` measures at **exactly 0.0000 LSB at every 125 °C
  point** — the 0.4832 LSB worst-case settling residue is at the *cold* end of
  the slow corner, and the deck-local three-leg DR-0011 cell is short by the
  same amount to within 1e-4 LSB, so it is the array's, not the fourth leg's).
  What SFDR *does* order with is `samp_inl_worst_lsb` — the endpoint-fitted bow
  of the **held sample itself**, measured on a different deck, from a different
  netlist, with an ideal reference:

  | corner-id | SFDR (dB) | `samp_inl_worst_lsb` | static INL worst (LSB) | settling residue (LSB) |
  |---|---|---|---|---|
  | `ff_125c_3.63v` | 69.98 | 0.0898 | 0.0921 | 0.0000 |
  | `ff_125c_2.97v` | 69.45 | 0.0833 | 0.0960 | 0.0000 |
  | `tt_125c_3.30v` | 69.14 | 0.0324 | 0.0950 | 0.0000 |
  | `tt_125c_3.63v` | 68.96 | 0.0423 | 0.0941 | 0.0000 |
  | `ff_125c_3.30v` | 67.32 | 0.1056 | 0.0934 | 0.0001 |
  | `ss_125c_3.63v` | 65.99 | 0.1169 | 0.0987 | −0.0002 |
  | `tt_125c_2.97v` | 64.67 | 0.1441 | 0.0970 | 0.0000 |
  | `ss_125c_3.30v` | 63.62 | 0.2114 | 0.1007 | −0.0001 |
  | **`ss_125c_2.97v`** | **61.33** | **0.3321** | 0.1041 | 0.0000 |

  The worst SFDR point is the worst sampling-bow point, and within the `ss`
  column both move monotonically with supply. **This is a nine-point
  correlation, not an isolation**, and it is stated as such: no experiment here
  drives the acquisition bow independently and watches SFDR follow. Doing that
  is the obvious next measurement, and it is not done in this re-run.
- **One candidate, named and not taken.** The dynamic deck still drives
  0.94 × half full scale, a backoff §3.5 sized so that a *3 % gain error* would
  not clip. That gain error is now 0.20 %, and the captures land at
  −0.58 dBFS with `code_max` = 990 and `code_min` = 33 at every point — about
  0.6 dB of range the deck is no longer using. Restoring it would raise the
  signal by roughly the size of the miss. **Whether that closes the row is not
  known and must not be assumed**: the bullet above says the limiting term is a
  *signal-dependent* acquisition bow, so a larger drive raises the distortion as
  well as the signal, and by how much is exactly the thing no measurement here
  answers. **It is not done in this re-run** either way: it changes the
  testbench, in the direction that makes the number pass, inside the run whose
  whole purpose is to test a design change — and it would break comparability
  with the record this one supersedes. It belongs in a separate, declared
  change with its own record.

**Update (issue #151, 2026-08-14): the extracted-vs-schematic divergence,
tested and reconciled — the extracted result now governs the row.**
`sim/extracted-delta-summary.md` §4.10 measured the in-path-extracted
`ADC_TOP` core's worst SFDR over the same nine-point grid at 64.38 dB — a
result that *beats* this section's own schematic-level 61.33 dB FAIL at the
same corner, `ss_125c_2.97v`, on two independent captures
([`20260807-054805-e8cd2b8`](../sim/adc-enob-fft/records/20260807-054805-e8cd2b8.md),
[`20260807-052432-eac5d11`](../sim/adc-enob-fft/records/20260807-052432-eac5d11.md)).
That left open *why* the extracted netlist outperforms the schematic one at
the corner the schematic fails. Three candidate explanations were tested,
not assumed:

1. **Baseline staleness — REFUTED.** `design/adc-top/gen_adc_top.py` diffed
   directly against the exact commit (`1224e11`) the 2026-08-02 baseline
   record was generated at shows only a comment renumbering
   (DR-0007 → DR-0015) and an unrelated `adc-power` DR-0018
   process-axis-sensitivity-floor threshold edit — nothing touches
   `FFT_AMP_FRAC`, the input drive network, or any CDAC/array parameter.
   That scoping holds for the top-level generator only — **the simulated
   deck did not stand still.** Diffing the two frozen netlist snapshots
   committed alongside these records
   (`sim/adc-enob-fft/netlist-snapshots/20260802-141402-1224e11.spice`
   against `sim/adc-enob-fft/netlist-snapshots/20260814-193205-f613571.spice`)
   shows `design/comparator/comparator.spice` moved the preamp load
   resistors from `ppolyf_u_2k r_width=1u r_length=75u` to
   `ppolyf_u_1k r_width=1u r_length=150u` between `1224e11` and `f613571`
   (issue #118 / `2AMLogic/klayout-tools#595`): nominally the same 150 kΩ,
   but a *different* PDK device model with its own sheet rho and its own
   tempco, exercised here at a 125 °C corner. A fresh single-corner re-run
   at `ss_125c_2.97v` against current sources
   ([`20260814-193205-f613571`](../sim/adc-enob-fft/records/20260814-193205-f613571.md),
   `Supersedes: 20260802-141402-1224e11`) nonetheless reproduces the
   original capture: **all 64 decoded codes (`code_s000`…`code_s063`) are
   bit-identical**, and the only result cells that move at all are 6 of the
   8 decode-**error** metrics plus `vref_droop_mv` — `decerr_c000_lsb`
   259.514 → 259.53 (0.016 LSB), `decerr_c008_lsb` 623.966 → 623.955,
   `decerr_c024_lsb` 602.884 → 602.881, `decerr_c032_lsb` 258.616 → 258.637
   (0.021 LSB, the largest drift of the seven), `decerr_c040_lsb`
   624.593 → 624.594, `decerr_c048_lsb` 851.295 → 851.299, and
   `vref_droop_mv` 1.676 → 1.680 mV. Every decode-error drift is ≤ 0.021
   LSB, consistent with the ngspice-46 → ngspice-47 toolchain
   minor-version bump *and* the comparator load-device swap above, and
   `analyze_fft.py` measures **SFDR = 61.3317 dB**, matching the baseline's
   61.33 dB. The baseline was not stale — and because that figure survives
   both a toolchain minor-version bump and a comparator preamp load-device
   change, this is a *stronger* reproduction than a like-for-like re-run
   against frozen sources would have been.
2. **Deck/comparability gap — REFUTED.** A line-by-line diff of
   `sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice` (schematic) against
   `sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice` (extracted,
   generated by `layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py`)
   shows the shared preamble — clocks, split supplies, the DR-0002
   reference network, the coherent sine (frequency, phase, and the
   `FFT_AMP_FRAC = 0.94` backoff line itself, byte-identical:
   `vsein se_vinp 0 sin({vcm} {vref/2*0.94} 484375.000000 ...)` in both
   files), and the DR-0013 input drive network (`Rsesp`/`Csexp`/`Rsesn`/
   `Csexn`, identical values) — is byte-for-byte identical between the two
   decks. The only differences are header comments, a `.save`
   vector-retention directive on the extracted deck (needed only to avoid
   an ngspice OOM from the in-path split's ~4256 extra nodes, and already
   shown measurement-neutral — `sim/extracted-delta-summary.md` §4.10), and
   the declared CDAC-core substitution itself. There is no undeclared
   topology divergence between the two decks.
3. **The fixed backoff interacting differently — refuted as a testbench
   artifact, but it named the right neighborhood.** Both decks import the
   same `FFT_AMP_FRAC` constant and drive the identical stimulus (confirmed
   by (2) above), so the backoff itself is not a source of divergence
   between the two decks. But re-running `analyze_fft.py` against both
   independent in-path captures' own raw per-corner logs — not previously
   published in this memo, only the grid's own worst figure was — finds
   that the extracted grid's worst SFDR point is **not** `ss_125c_2.97v`;
   it is `ff_125c_3.63v`, at 64.38 dB. At the corner-matched
   `ss_125c_2.97v` point itself the extracted SFDR is **64.93 dB**,
   identical to four significant figures between the two independent
   captures:

   | corner-id | schematic SFDR (dB) | extracted SFDR (dB) | delta (dB) |
   |---|---|---|---|
   | `ff_125c_2.97v` | 69.45 | 65.48 | −3.97 |
   | `ff_125c_3.30v` | 67.32 | 67.65 | +0.33 |
   | `ff_125c_3.63v` | 69.98 | **64.38** | **−5.60** |
   | `ss_125c_2.97v` | **61.33** | 64.93 | +3.60 |
   | `ss_125c_3.30v` | 63.62 | 67.87 | +4.25 |
   | `ss_125c_3.63v` | 65.99 | 69.49 | +3.50 |
   | `tt_125c_2.97v` | 64.67 | 68.62 | +3.95 |
   | `tt_125c_3.30v` | 69.14 | 65.79 | −3.35 |
   | `tt_125c_3.63v` | 68.96 | 68.19 | −0.77 |

   The entire `ss` column improves (+3.50 … +4.25 dB) while `ff`/`tt`
   corners move in **both** directions, including two that get materially
   worse (`ff_125c_3.63v` −5.60 dB, becoming the extracted grid's new worst
   point; `ff_125c_2.97v` −3.97 dB; `tt_125c_3.30v` −3.35 dB). A uniform
   testbench artifact — an undeclared stimulus, deck, or backoff difference
   — would move every corner the same direction; a real, corner-dependent
   parasitic effect would not, and does not here. The in-path extraction
   adds real series R and shunt C along the CDAC array / top-plate
   acquisition path (`sim/extracted-delta-summary.md` §1.4), which is
   exactly positioned to change the *acquisition's own sampling-bow
   nonlinearity* — the mechanism this section's correlation table above
   already attributes the schematic-level miss to — differently at each
   corner, depending on that corner's own R_on and RC time constant. This
   is the same "moves rather than uniformly shifts" behavior
   `sim/extracted-delta-summary.md` §7.2/§7.3 already documents for the
   power row's comparator excursion, recurring here on a second measured
   quantity. As with that finding, this is a **correlation observed on an
   existing, independently-replicated dataset, not a controlled
   isolation** — no experiment here varies only the extracted RC and
   watches SFDR move continuously, and that remains the obvious follow-up
   this section's original correlation bullet already flagged as undone.

   **Disposition.** Two of the three candidates are refuted outright
   (staleness, deck comparability); the third's literal framing (a
   testbench-level backoff difference) is also refuted, but the mechanism
   it pointed at — the acquisition's own signal-dependent nonlinearity
   responding to a real change in the circuit — is confirmed as the best
   available explanation, consistent with a genuine parasitic effect and
   inconsistent with a measurement artifact. `sim/adc-enob-fft/records/
   20260814-193205-f613571.md` establishes that the schematic-level record
   `20260802-141402-1224e11` was accurate, not stale: the schematic-level
   SFDR miss at `ss_125c_2.97v` (61.33 dB against ≥ 62 dB) stands, unedited,
   as the correct reading of the pre-layout, schematic-level netlist —
   nothing here retires or hides that FAIL. It is not, however, the record
   this repository's evidence trail reads as **governing** the ratified row
   for the design as laid out. The authority for that reading is
   *precedent*, and only precedent: every other ratified row already reads
   off the post-layout capture once one exists — INL, ENOB, power and
   systematic gain error, all reported from the extracted records in
   `README.md`'s Status line. (`sim/README.md`'s "Extracted vs schematic
   semantics" is **not** authority here and is not cited as such: it fixes
   the bookkeeping — an extracted record appends alongside the schematic
   one in the same experiment directory and never replaces or edits it —
   and says nothing about which record governs a spec row's verdict.) On
   that precedent, the two independent in-path-extracted records
   (`20260807-054805-e8cd2b8`, `20260807-052432-eac5d11`, agreeing to the
   significant figures reported here) are the governing measurement of the
   fabricatable design. **On that basis the SFDR row now passes**, at
   64.38 dB worst (`ff_125c_3.63v`, not `ss_125c_2.97v`) against the
   ≥ 62 dB target. **"Worst" here is worst of a temperature-degenerate
   subgrid**: all nine FFT points sit at 125 °C (3 process × 3 supply —
   both the schematic and extracted grid records declare the same
   `Gaps: temperature: missing -40 C, 27 C`), so `ff_125c_3.63v` is not
   shown to beat the −40 °C
   R_on-modulation point the README row previously named. That is the
   deck's deliberate two-stage strategy, not an omission — the static decks
   sweep the full 27-point PVT grid and the dynamic runs are spent at the
   corners it names — but it bounds what "binding corner" can be read to
   mean on this row. The 62 dB target itself is unchanged — nothing here
   relaxes it — and the schematic-level FAIL is reported, not smoothed
   over. See `sim/extracted-delta-summary.md` §7.1 for the same disposition
   stated from the extracted side.

### 11.3 The four terms DR-0014's derivation assumed away, measured

DR-0014's Consequences name four quantities its charge-balance derivation
treats as negligible, and require each to be measured rather than argued.
`sim/dr0014-sampling/` (27 points, clean tree, PASS) is that measurement. It is
one transient carrying DR-0014's real two-phase schedule on DR-0003's 62.5 ns
clock, so the sampling instant and the one-bit-cycle lead are the design's own
numbers, not the deck's.

| # | Term DR-0014 assumed away | Measured over 27 PVT points | Read against |
|---|---|---|---|
| 1 | Top-plate `V_cm` switch's own charge injection | 0.0613–0.3018 LSB per side; **variation over the full input range 0.0045–0.0088 LSB** | it is an **offset**, which is the classic reason to sample on the bottom plate — shown, not assumed |
| 1b | …and its side-to-side part | signal-driven asymmetry ≤ **0.0064 LSB**; the `f = 0` null control reads ≤ 9.3e-12 LSB | Offset row, ≤ 2 LSB |
| 2 | Bottom-plate input switches' injection, after the top switch has already opened | ≤ **2.02e-4 LSB** per side; mismatch null control ≤ 1e-8 LSB | three decades under the INL row |
| 3 | The fourth leg's effect on bit-trial settling | weight-256 step short by −0.0002…**0.4832 LSB** at the strobe; **4-leg minus 3-leg ≤ 1e-4 LSB** | the residue is the array's, not the leg's |
| 4 | Second-order residue from side-to-side `C_par` mismatch | **−0.0026 … −0.0032 LSB/fF**, measured at 10 / 30 / 100 fF of deliberate imbalance | at 1 % of the measured 57–175 fF `C_par`, ≈ 0.002–0.006 LSB |

Two methodology points, stated because they change how the numbers should be
read:

- **Term 1 needs no reference simulation.** Before the sampling instant the top
  plate is held at `V_cm` through a closed switch and nothing else in the branch
  moves; after it, the only thing that has happened is that switch opening. The
  measured displacement *is* the injection, not a difference of two large
  numbers, so it is not sitting on the harness's ~1 µV `meas` precision floor.
- **Term 4 is measured at exaggerated mismatch on purpose.** At a
  centroid-matched percent-level imbalance the residue *is* below that floor;
  reporting it would be reporting the floor. The deck therefore measures a
  **slope** across imbalances large enough to be real numbers, and publishes it,
  so a reader can price whatever mismatch a layout can defend. Each point is a
  measurement; none is extrapolated.

### 11.4 The two published numbers DR-0014 invalidated the evidence for

- **`Gain error, systematic`** — §9.1 in full. The ≤ 0.5 LSB target does not
  move; the mechanism does.
- **Input-structure series `R_on`** — the ratified row publishes **156–570 Ω**
  for one dedicated 40u/80u switch that DR-0014 removes. Re-measured by the
  same forced-voltage / measured-current method on the path DR-0014 *built* —
  nine 10u/20u cell T-gates per side in parallel, one per switched weight — the
  series resistance is **21.3–60.0 Ω** (worst `ss_125c_2.97v`, best
  `ff_-40c_3.63v`), i.e. **119.8–540.2 Ω per single cell T-gate**, nine in
  parallel. The published row's figure is therefore stale by roughly 7–10×, in
  the *favourable* direction; DR-0014 already says so and this is the
  measurement behind it. **`C_in` stays 8.827 pF** — the array is untouched — so
  DR-0013's `R_source × (C_pin + C_in) ≤ 30 ns` contract and the ≥ 5.3 MHz T/H
  bandwidth stand exactly as published. Amending the row's text is a
  decision-record matter and is not done in this memo.

### 11.5 The noise budget is still not the problem

Composing the separately measured noise terms into the measured spectrum
(§4.3: comparator input-referred noise 153.2 µV rms worst + sampling `kT/C`
35.3 µV rms = **0.0488 LSB** total) moves ENOB by ≤ **0.021 bits**:

| corner-id | SNDR (dB) | ENOB | SFDR (dB) | THD (dBc) | amplitude (dBFS) | SNDR composed | ENOB composed |
|---|---|---|---|---|---|---|---|
| `tt_125c_2.97v` | 59.46 | 9.584 | 64.67 | −61.97 | −0.583 | 59.38 | 9.571 |
| `tt_125c_3.30v` | 61.28 | 9.888 | 69.14 | −65.77 | −0.581 | 61.16 | 9.868 |
| `tt_125c_3.63v` | 61.49 | 9.922 | 68.96 | −65.31 | −0.581 | 61.37 | 9.901 |
| `ss_125c_2.97v` | 56.96 | **9.170** | **61.33** | −58.53 | −0.582 | 56.92 | **9.163** |
| `ss_125c_3.30v` | 59.40 | 9.574 | 63.62 | −61.50 | −0.581 | 59.32 | 9.561 |
| `ss_125c_3.63v` | 59.96 | 9.668 | 65.99 | −62.70 | −0.583 | 59.87 | 9.653 |
| `ff_125c_2.97v` | 61.41 | 9.908 | 69.45 | −67.27 | −0.583 | 61.28 | 9.888 |
| `ff_125c_3.30v` | 60.52 | 9.761 | 67.32 | −63.74 | −0.583 | 60.42 | 9.744 |
| `ff_125c_3.63v` | 61.60 | 9.939 | 69.98 | −66.69 | −0.582 | 61.47 | 9.918 |

The noise term is now a larger *share* of a much smaller error — which is the
expected consequence of removing a distortion mechanism, not a regression — and
it still costs at most 0.021 bits. DR-0007's noise design remains ~10× under
its allocated budget, and the SFDR row misses on **distortion at one settling
corner**, not on noise. The amplitude column also carries the §11.2 point: every
capture peaks at −0.58 dBFS, `code_max` = 990 / `code_min` = 33, so nothing is
clipping and the spectrum is not reporting clipping as distortion.

### 11.6 What this settles about the two-stage corner strategy (§5)

Unchanged by the re-run, and now confirmed on a second topology: the measured
ENOB- and SFDR-worst corner is **`ss_125c_2.97v`** — the *settling*-worst
corner — **not** `ff_125c_3.63v`, which `sim/comparator-preamp-noise/`
independently identifies as noise-worst and where, per the table above, ENOB is
in fact *best* (9.918 bits). §5 refused to assume the two coincide; both runs
show why that refusal mattered, and *why* they do not coincide here: noise is
not the limiting mechanism at this design point, so the dynamic-worst corner is
set by the same mechanism as the static-worst one. Had the design been
noise-limited the ordering would have inverted — exactly the case a strategy
that inherits the static-worst corner unexamined would have got wrong.

### 11.7 Power, block by block, each at its own worst corner

Worst total is **183.3 µW** at `ff_-40c_3.63v` (mid-scale input): 5.5× under the
ratified < 1 mW row and 2.7× under the < 500 µW stretch. DR-0014 cost **+26 µW
(+17 %)** against the superseded topology's 157.0 µW, and it is paid where
DR-0014 said it would be — in the switch and gate-drive terms, not in comparator
current. The blocks do **not** share a worst-power corner, which is why the row
is reported this way rather than as one number at one corner:

| Block | Worst power | Its own worst corner | Was (DR-0011) | Mechanism |
|---|---|---|---|---|
| Comparator (#9) | 122.1 µW | `ff_-40c_3.63v` | 118.8 µW | static preamp bias — fast/high-supply |
| CDAC + local drivers (#8) | 36.4 µW | `ff_-40c_3.63v` | 12.5 µW | gate-drive dynamic — now **four** legs per cell, not three |
| V_REF (DR-0002) | 34.4 µW | `ss_125c_3.63v` | 32.9 µW | array switching charge — slow/hot |
| V_cm rail | 24.1 µW | `ff_-40c_3.63v` | 14.4 µW | array switching charge — the bottom plates now park on `V_cm` between phases |
| Top-plate `V_cm` switch | 1.26 µW | `ff_-40c_3.63v` | 0.01 µW (the *removed* input switch) | gate drive of `adc_tp_sw`; not the same device |

Fast/hot is worst for the static bias term; the terms that move charge peak at
the fast/cold/high-supply end. Reusing one corner across all five would have
understated at least two of them. The comparator is now 67 % of the total
(76 % before) because the switching terms grew and it did not.

### 11.8 Record index

Both generations are listed. The DR-0011 records are **not** deleted — `sim/` is
append-only, and they are the measured evidence DR-0014's Context rests on.

| Experiment | DR-0014 record (#61) | Grid | Verdict | Supersedes (DR-0011) |
|---|---|---|---|---|
| `sim/adc-inl-dnl/` | `records/20260802-141402-1224e11.md` | 27 points, clean tree | **PASS** | `20260801-144717-d407dfe` (FAIL, INL) |
| `sim/adc-enob-fft/` | `records/20260802-141402-1224e11.md` | 9 points, clean tree | capture **PASS**; **ENOB row PASSES, SFDR row FAILS** per §11.2 | `20260801-180501-845f76e` |
| `sim/adc-power/` | `records/20260802-141402-1224e11.md` | 27 points, clean tree | **PASS** | `20260801-134035-7d48a44` |
| `sim/track-switch-sampling/` | `records/20260802-141402-1224e11.md` | 117 points, clean tree | **PASS** | `20260801-113511-c05043b` |
| `sim/top-plate-cpar/` | `records/20260802-125708-1de758a.md` | 63 points, clean tree | **PASS** (characterization) | `20260802-033948-75497e8` |
| `sim/dr0014-sampling/` | `records/20260802-141402-1224e11.md` | 27 points, clean tree | **PASS** | — (first record) |
| `sim/comparator-preamp-noise/` | `records/20260801-123440-033b56b.md` | 45 points, clean tree | PASS | — (not affected by DR-0014) |

**The negative control was re-checked on the new topology.** `sim/harness/`
mechanism 3 requires a healthy testbench to **fail** under `--sabotage-corners`
(every corner *name* kept, every model section forced to typical).
`sim/top-plate-cpar/` still does on the DR-0014 topology: 63/63 points simulate
happily, and the run fails on `c_arr_v1p65_ff`'s process-axis sensitivity floor
collapsing from its healthy value to **0 %**. The new
`sim/dr0014-sampling/` deck fails the same way on `ron_path_worst_ohm`
(process-axis floor 15 %, sabotaged spread 0 %), checked at the three process
corners at 27 °C and nominal supply — enough levels to exercise the process
axis the control is about, and a sabotaged run is not evidence in the first
place. Sabotaged runs force `--no-write`, so neither can enter the evidence
tree.

**Four ENOB records now exist, and the earlier three are superseded rather than
deleted** (`sim/` is append-only). `20260801-134049-7d48a44` took a single
whole-capture `MAX` of the per-decision error, which spanned the conversion
*boundaries* — where the array releases to V_cm and the ideal shadow steps to
zero a numerical instant apart — and reported an 889 LSB spike at exactly
`t = k·1 µs` that no comparator ever samples. `20260801-153441-7302e1b`
measures per conversion, inside the trial phases, which fixed that — and
exposed the deeper point below, that the quantity is not a decision error at
all for a moving input. `20260801-180501-845f76e` reports it unbounded and
carries the V_REF corner-sensitivity floor instead.

**The first three captures agree to four significant figures at all nine PVT
points**, which is the reproducibility statement this suite's spectral claim
rests on: those corrections were to what was *checked*, never to what was
*measured*. The fourth, `20260802-141402-1224e11`, is the one that legitimately
*does* differ, because the converter underneath it changed — that is #61's whole
point, and the §11.5 table is its numbers, not theirs.

**The per-decision error is reported, not bounded, in the dynamic deck**, and
the reason is a property of the deck rather than a convenience. `se_err`
differences the **held** top plates against `se_di`, which is built from the
**instantaneous** input. With a static input (`sim/adc-inl-dnl/`) those are the
same thing and the node is exactly the input-referred decision error. With a
0.969 × Nyquist sine they are not: the input keeps moving through the 600 ns
trial window, by up to `2π · 484 kHz · 600 ns · 512 LSB ≈ 930 LSB`, and that
motion — not any decision error — is what dominates the 165–810 LSB measured.
Bounding it would be bounding the input's slew rate. Making it meaningful needs
a shadow sample-and-hold on the ideal input path, i.e. a **netlist** change
that would break comparability with the sibling records already taken from this
generator; it is left to #17's post-layout re-run, which regenerates all three
decks anyway. The deck keeps a real corner-sensitivity assertion in its place
(V_REF droop through DR-0002's network, with a process-axis spread floor,
mirroring `sim/adc-inl-dnl/`).

**What the dynamic record's own PASS/FAIL covers, and what it does not.** The
harness verdict on `sim/adc-enob-fft/` covers the **capture's validity** —
coverage witnesses that the sine drove the converter across its range without
clipping, plus the V_REF corner-sensitivity floor. ENOB and SFDR are spectral
quantities, not scalars an ngspice `meas` can produce; they are computed from
that record's own raw per-corner logs by `analyze_fft.py` and adjudicated here
in §11.5. **A reader must not read a harness PASS on that record as the ENOB
and SFDR rows passing.** As of this memo the ENOB row passes and the SFDR row
does not, and neither verdict comes from the harness.

---

## 12. Known limitations and stated assumptions

Every item here is a limitation of the *evidence*, stated so a reader does not
have to infer it from a silence.

1. **The SAR sequencer and output register draw no measured power.** They are
   DR-0010 rung 1 — ideal XSPICE event-driven primitives, which contain no
   devices. `design/sar-logic/README.md` says so directly. The **dominant**
   digital term in a SAR ADC is driving the array's switch gates, and that *is*
   measured (the local T-gate drivers are real devices on `vddd`); what is
   missing is the sequencer's own flip-flops and decode. It is carried as an
   analytic bound in the power record, not as a measurement, and it cannot be
   closed until rung 3 — which DR-0010 in turn states is blocked on the open
   gf180mcu PDK shipping no 3.3 V standard-cell library.
2. **The sampling switch's own gate driver is analytic for the same reason,
   plus one more.** Its complementary clock phase is generated at rung 1 so the
   NMOS/PMOS turn-off skew is *identical* to the one DR-0013's ratified
   charge-split measurement was taken with. A real driver's skew would change
   that split — i.e. it would silently re-open a closed decision — so the driver
   is carried as an analytic power term rather than simulated here.
3. **V_cm is an ideal source.** DR-0011's Consequences make V_cm generation "a
   new, currently-unbudgeted deliverable for a future issue", so there is no
   ratified envelope to model it against. Every record in this suite carries
   that as a stated assumption.
4. **Each block is drawn as one capacitor of the block's total area**, not as
   *w* separate unit cells. That is exact for this campaign by construction:
   these records verify the nominal design, where unit-to-unit mismatch is zero.
   The statistical spread of the same array is `sim/mc-cdac-mismatch/`'s claim.
   Drawing 1022 unit cells here would multiply simulation cost by ~50× and
   change no number.
5. **`A_C = 2.0 %·µm` remains an uncited planning placeholder** (devchar §5.1,
   `README.md` note [d]) pending GlobalFoundries' own MiM matching data. It
   feeds #14's mismatch campaign, not this suite's nominal one, but the INL/DNL
   *row* is only closed by both halves together.
6. **The MiM voltage coefficient is not in any simulated number in this repo** —
   the PDK's own deck has the bias-dependent instance line commented out
   (devchar §1.5). `README.md` note [d] budgets ≈ 0.27 LSB for it inside the
   INL/DNL target. This suite's measured INL/DNL therefore excludes a term the
   ratified row includes.
7. **CMRR is closed by extrapolation from a ±50 mV measurement** to the
   ratified ±100 mV band (§10), not by a direct measurement at the ratified
   band.
8. **The converter carries an unbudgeted systematic gain error** — ~3 % under
   DR-0011 (§3.5), **0.20 % after #61's re-run on the DR-0014 topology**. It is
   measured and reported, never absorbed; adjudicating it is a decision-record
   matter, which **[DR-0014](decision-records/DR-0014-bottom-plate-sampling.md)**
   did on 2026-08-02 by a design change rather than a spec change, so no
   ratified row was added, widened or relaxed at any point. What has *not* been
   adjudicated is the 2 LSB that is left: it is 15× smaller, it is flat across
   PVT, and it still has no row.
   **Two checks in this suite are still widened for the term DR-0014 removed**
   — the end-to-end `code_t<k>` window (±45 LSB) and the per-decision error —
   and #61 deliberately left them alone so that its own re-run could not be
   accused of having been tuned to pass. Tightening them against the topology
   they now measure is follow-up work, and so is re-examining the dynamic
   deck's −0.54 dBFS drive backoff (§11.2), which was sized for a 3 % gain
   error that is now 0.20 %.
8b. **The SFDR row fails by 0.67 dB at one corner of nine** on the DR-0014
   topology (§11.2). It is reported as a failure. Nothing in this memo, and
   nothing in #61's testbenches, was changed to close it.
8c. **The `Gain error, mismatch` row measures 2.12σ against its ratified 3σ
   condition** — 0.708 LSB at 3σ against the ratified ≤ 0.5 LSB — the first
   time that row has been checked against a sample population rather than a
   closed-form ceiling (`sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md`,
   issue #172). `README.md` note **[e]**'s `3 × 0.52 % / √1024 = 0.049 %`
   uses `sim/device-characterization-report.md` §5.1's *binding requirement*
   `σ_u ≤ 0.52 %`; the chosen design's calibrated `σ_u = 0.7372 %`
   (`spec/monte-carlo-methodology-memo.md`'s `A_C/√A_unit = 2.0/√7.36`, off
   `spec/cdac-sizing-memo.md` §3.4/§4's chosen unit cap) is larger than that
   ceiling, because
   DR-0011's split topology was sized against its own looser-by-√2 DNL
   coefficient (§3.2's `√511`), and gain error — a total-array-capacitance
   sum, §5.2's architecture-invariant `C_total = 1024·C_u` — takes no benefit
   from the split. Substituting the *actual* `σ_u` into note [e]'s own
   `3σ_u/√1024` formula reproduces the measured figure to 0.3 %. It is
   reported as a failure (the `klt yield` report's own top-level `status` is
   `fail`): no spec value was relaxed, no testbench was retuned, and the
   resizing decision — the only thing that can actually close it — is issue
   #177, not this memo.
9. **Area is not measured** — there is no layout (§2).
10. **Everything here is schematic-level.** #17 re-runs this whole suite against
   extracted parasitics; each such re-run appends an `extracted` record
   alongside the schematic one with a `Supersedes` delta, per `sim/README.md`.

---

## 13. How to re-run this suite

```bash
python3 sim/run_corners.py --check-env          # ngspice + PDK + pinned versions
python3 design/adc-top/gen_adc_top.py --check   # committed decks match the generator
python3 -m unittest discover -s sim/tests       # PDK-free structural guards

# stage 1 -- the full-grid sweeps (27 points each; hours, not minutes)
python3 sim/run_corners.py adc-inl-dnl --corners tt ss ff -j 9 --timeout 20000
python3 sim/run_corners.py adc-power   --corners tt ss ff -j 9 --timeout 20000

# the DR-0014 mechanism decks (Sec 11.3 / 11.4): the four assumed-away terms
# and the re-taken R_on, then the C_par decomposition they act on
python3 sim/run_corners.py dr0014-sampling  -j 9 --timeout 20000
python3 sim/run_corners.py top-plate-cpar   -j 9 --timeout 6000

# the DR-0013 drive contract, unchanged by DR-0014 (Sec 9.1)
python3 sim/run_corners.py track-switch-sampling -j 9 --timeout 20000

# stage 2 -- the expensive dynamic run, only at the corners stage 1 and
# sim/comparator-preamp-noise/ identify (see Sec 5)
python3 sim/run_corners.py adc-enob-fft --corners tt ss ff --temps 125 \
    -j 9 --timeout 40000 --subset-reason "<see Sec 5>"

# post-process the dynamic capture from the runner's own raw logs
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/<record-id>/ --markdown --sigma-extra-lsb 0.0488
```

Add `--supersedes <prior-record-id>` to every re-run: `sim/` is append-only, so
a re-run mints a new record and points back at the one it replaces rather than
editing it. **Start the runs within a minute of each other, on a clean tree.**
The harness samples git state *before* a run and writes its per-corner logs into
the tracked evidence tree as points complete, so a run started after a sibling's
first log has landed records itself as taken against a dirty working tree — and
`sim/harness/README.md` makes that non-citable (§2.1).

Every deck must **fail** under `--sabotage-corners` (`sim/harness/README.md`
mechanism 3); each carries a process-axis sensitivity floor on at least one
measurement for exactly that reason. #61 re-checked that on the DR-0014
topology for `top-plate-cpar` and for the new `dr0014-sampling` deck (§11.8).
