# Testbench-suite methodology memo — one testbench per spec line

**Issue**: #13. **Status**: methodology ratified here; per-row evidence linked
from §2. This memo does not re-derive any upstream budget — it turns
#8/#9/#10/#11's ratified numbers and #12's closed timing budget into a
runnable, corner-swept verification matrix, and states the methodology choices
that matrix rests on.

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

Three new testbenches are added by this issue. Everything else in the coverage
map is **reused, not reimplemented** — a second, independently-authored closure
of a claim another issue already closed is a duplication risk, not added rigor.

| New here | Slug | Substantiates |
|---|---|---|
| Static linearity | `sim/adc-inl-dnl/` | INL / DNL row (nominal design over PVT) |
| Dynamic performance | `sim/adc-enob-fft/` | ENOB and SFDR rows (distortion half) |
| Power | `sim/adc-power/` | Power @ 1 MS/s row, broken down by block |

All three are generated from one source of truth,
`design/adc-top/gen_adc_top.py`, and all three instantiate the **same**
converter: DR-0013's input drive network and dummy-compensated sampling switch,
DR-0011's 512-unit-per-side MiM array with real T-gate bottom-plate switches
and real local drivers, DR-0007's static-preamp + StrongARM comparator, and the
rung-1 SAR controller `sim/sar-logic-functional/` verified. Everything in the
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
| ENOB @ Nyquist | `sim/adc-enob-fft/` (distortion) **composed with** `sim/comparator-preamp-noise/` + `spec/cdac-sizing-memo.md` §1 (noise) — see §4.3 | this issue's `adc-enob-fft` record + the preamp-noise record | **#13** |
| SFDR @ Nyquist | `sim/adc-enob-fft/` (whole converter); `sim/track-switch-thd/` (switch contribution alone) | this issue's `adc-enob-fft` record | **#13** |
| INL / DNL | `sim/adc-inl-dnl/` (nominal, PVT) + `sim/mc-cdac-mismatch/` (3σ mismatch) | this issue's `adc-inl-dnl` record + `sim/mc-cdac-mismatch/records/20260801-093800-c033611.md` | **#13** / #14 |
| Offset error | `sim/comparator-offset-mc/` + `sim/comparator-offset-gof/` | `sim/comparator-offset-gof/records/20260801-093644-c033611.md` | #9 / #14 |
| Gain error, mismatch | `sim/mc-cdac-mismatch/` | `sim/mc-cdac-mismatch/records/20260801-093800-c033611.md` | #14 |
| Gain error, systematic | `sim/track-switch-sampling/` — **reused, clean-tree re-run, see §9** | `sim/track-switch-sampling/records/20260801-113511-c05043b.md` | #39 → **#13** |
| CMRR (differential) | `sim/comparator-offset-mc/` — **reused, see §10** | `sim/comparator-offset-mc/records/20260801-035221-90d7e67.md` | #9 / #14 |
| Input (drive contract) | `sim/track-switch-sampling/` (the whole DR-0013 drive envelope) | `sim/track-switch-sampling/records/20260801-113511-c05043b.md` | #39 |
| Input structure (C_in, R_on, T/H BW) | `sim/device-switch-ron/`; C_in asserted against the array in `sim/tests/test_adc_top_netlist.py` | `sim/device-characterization-report.md` §2.1 | #4 / #10 |
| Reference (Z_ref, C_dec) | `sim/cdac-bit-settling/` | `sim/cdac-bit-settling/records/20260731-231537-1ee5578.md` | #8 |
| Clock (M = 16, jitter) | `sim/sar-logic-timing/`; jitter budget is analytic (DR-0003) | `sim/sar-logic-timing/records/20260801-033032-06bad60.md` | #11 |
| Supply (±10 %) | spanned by the supply axis of every corner sweep in this table | every record above | — |
| Latency / conversion timing | `sim/sar-logic-functional/` + `sim/sar-logic-timing/` | both records above | #11 |
| Power @ 1 MS/s | `sim/adc-power/` | this issue's `adc-power` record | **#13** |
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
  all minted after the testbenches were committed), `track-switch-sampling`
  (§9), `timing-budget-closure`, `mc-cdac-mismatch`, `comparator-offset-gof`,
  `sar-logic-functional`, `sar-logic-timing`, `cdac-bit-settling`,
  `comparator-preamp-noise` (§7.3 — re-run clean by this issue, for the same
  reason §9 re-ran the gain-error row).
- **Dirty-tree, carried as such**: `comparator-regeneration`,
  `comparator-offset-mc`, `comparator-kickback`, `track-switch-thd`,
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

---

## 4. Dynamic performance: coherent sampling, stated rather than asserted

### 4.1 The parameters

| Parameter | Value | Why |
|---|---|---|
| `f_s` | 1 MS/s | the ratified Rate row |
| `N` (record length) | 128 samples | a **power of two**, so the post-processor's FFT needs no zero padding — padding would itself destroy the coherence it is supposed to preserve |
| `M` (input cycles captured) | 61 | **prime**, hence coprime to any power of two |
| `f_in` | 476.5625 kHz | `= M·f_s/N` |
| `f_in / f_Nyquist` | 0.953 | "near Nyquist", as the ratified ENOB and SFDR rows specify (`f_Nyquist = f_s/2 = 500 kHz`) |
| Window | `none` | see §4.2 |

### 4.2 Why `window = none` is valid here

Coherence is a property of two integers, and it is asserted as such
(`sim/tests/test_adc_top_netlist.py::CoherentSamplingTests`, and again inside
`analyze_fft.py` before it computes anything):

`gcd(61, 128) = 1`, so the 128 samples land on 128 **distinct** phases of the
input and the capture contains exactly 61 whole input periods. An integer
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
(`m_code_s000 … m_code_s127`) and
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

**The strategy.** Sweep the full `cdac` grid (7 process corners × 3
temperatures × 3 supplies = 63 points) with the cheaper static-linearity and
power decks; spend the expensive dynamic run only at the corners those sweeps
identify. The dynamic deck is ~3.4× the transient length of the static one and
~5.9× the power one, so a full-grid dynamic sweep is the single largest cost
item in this suite.

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

| Corner | Why it is in the dynamic set |
|---|---|
| `ss_125c_2.97v` | settling/linearity-worst — the corner the ratified Rate row binds at, and the corner the static sweep is expected to find worst |
| `ff_125c_3.63v` | **noise-worst**, identified independently by `sim/comparator-preamp-noise/`, *not* inherited from the static sweep |
| `tt_27c_3.30v` | nominal reference point, so the corner deltas are readable |
| (+ whatever corner the static sweep actually finds worst, if it is none of the above) | closes the loop: the strategy is "run at the corners the cheap sweep identifies", so the identification has to be honoured, not predicted |

That subset is declared to the runner with `--subset-reason`, which
`sim/harness/README.md` requires and copies verbatim into the record — an
unexplained subset is not a valid record.

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

`spec/decision-records/DR-0007-comparator-topology.md` (merged in PR #45,
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
missing. See §11 for the resulting record id.

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

---

## 11. Results

*(Per-corner results live in the append-only records under `sim/`; this section
summarises them and must never be read as a substitute for them.)*

*Pending the sweeps this commit makes runnable — `sim/README.md` makes a run
against a dirty working tree non-citable, so the testbenches have to land
before the records they produce can. Filled in by the follow-on commit on this
branch.*

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
8. **Area is not measured** — there is no layout (§2).
9. **Everything here is schematic-level.** #17 re-runs this whole suite against
   extracted parasitics; each such re-run appends an `extracted` record
   alongside the schematic one with a `Supersedes` delta, per `sim/README.md`.

---

## 13. How to re-run this suite

```bash
python3 sim/run_corners.py --check-env          # ngspice + PDK + pinned versions
python3 design/adc-top/gen_adc_top.py --check   # committed decks match the generator
python3 -m unittest discover -s sim/tests       # PDK-free structural guards

# stage 1 -- the cheap full-grid sweeps
python3 sim/run_corners.py adc-inl-dnl --corner-set cdac -j 8 --timeout 5000
python3 sim/run_corners.py adc-power   --corner-set cdac -j 8 --timeout 5000

# stage 2 -- the expensive dynamic run, only at the corners stage 1 and
# sim/comparator-preamp-noise/ identify (see Sec 5)
python3 sim/run_corners.py adc-enob-fft \
    --corners tt ss ff --temps 27 125 --supply-tol 0.1 -j 8 --timeout 9000 \
    --subset-reason "<see Sec 5>"

# post-process the dynamic capture from the runner's own raw logs
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/<record-id>/ --markdown --sigma-extra-lsb 0.0488
```

Every deck must **fail** under `--sabotage-corners` (`sim/harness/README.md`
mechanism 3); each carries a process-axis sensitivity floor on at least one
measurement for exactly that reason.
