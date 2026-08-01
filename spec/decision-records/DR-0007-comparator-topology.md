# DR-0007: Comparator topology — static preamplifier + StrongARM latch, offset cancellation tier 0

- **Status**: proposed — requires operator sign-off (spec ratification authority sits with engineering per #1 / DR-0006-spec-ratification)
- **Date**: 2026-08-01
- **Decided by**: Builder agent, issue #9
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #3, #4, #8, #9, #12, #13, #14, #16;
  DR-0006-cdac-switching-scheme, DR-0006-spec-ratification, DR-0003;
  `spec/prior-art-survey.md` §1.1, §1.4, §3; `spec/comparator-budget-memo.md`;
  `sim/device-characterization-report.md` §3; `design/comparator/comparator.spice`;
  `sim/comparator-offset/`, `sim/comparator-offset-mc/`,
  `sim/comparator-preamp-noise/`, `sim/comparator-regeneration/`,
  `sim/comparator-kickback/`

## Context

`spec/prior-art-survey.md` §3 (issue #3) surveyed comparator topologies against
offset, noise, speed and kickback, and produced a ranked shortlist (§3.7) —
but, exactly as for the CDAC axis, its own curation scoped writing the decision
record *out* of the survey deliverable ("stops short of writing the architecture
decision records", §0.2). No other issue claims it. This record closes that gap
as #9's first deliverable.

Two things have changed since the survey ranked a bare **StrongARM latch** as
its primary candidate, and both are measurements the survey explicitly deferred
to #4 and #8:

1. **The mismatch coefficient is now measured, not assumed.**
   `sim/device-characterization-report.md` §3.3 measures `A_Vt = 7.208 mV·µm`
   (pair convention, effective area) and states directly that at a candidate
   40/0.5 µm input pair a 3σ input-referred offset is **1.8 LSB** — *from the
   input pair alone*, before any latch-referred term. The ratified spec
   (`README.md#target-specification`) allows **≤ 2 LSB untrimmed** offset. A
   bare StrongARM adds its regeneration-node and load mismatch referred back
   through only the modest gain of its own input stage, which does not fit in
   the 0.2 LSB that is left.
2. **The switching scheme is decided.** DR-0006 ratifies MCS/Vcm with a
   **constant** comparator common mode in differential mode (and a decaying
   `residue/2` term in single-ended mode), which — per survey §3.1 — makes a
   *static* offset a whole-converter offset that digital subtraction removes.
   That is what makes offset-cancellation tier 0 admissible **provided the
   residual offset itself fits the ratified row**, which is the condition item 1
   puts at risk.

There is also a verification-cost fork the survey identified (§3.5) and that
this repo's toolchain makes concrete: ngspice has no PSS/pnoise, and `.noise`
requires a DC operating point. Every dynamic topology on the shortlist would
therefore have to close its noise claim with a `trnoise` transient Monte Carlo
campaign of **10³–10⁴ runs per corner** — the single most expensive item in the
verification suite, and one that would land on #13 and #2.

## Decision

**The comparator is a static differential preamplifier followed by a StrongARM
latch, a pair of isolation inverters, and a NOR SR output latch** — shortlist
item 3 in
`spec/prior-art-survey.md` §3.7, not item 1 — **with offset-cancellation tier 0
(none + digital offset removal)**. The netlist is
`design/comparator/comparator.spice`; sizing is derived in
`spec/comparator-budget-memo.md` §3.

- **Preamplifier**: NMOS input pair, 40/1 µm, resistively loaded with 150 kΩ
  unsalicided p+ poly (`ppolyf_u_2k`, 1 µm × 75 µm), 10 µA tail from a 1:1 NMOS
  mirror. Measured differential gain `A_v ≈ 16` at nominal PVT. The input pair
  is sized for **area** (Pelgrom), not for speed: it is now the dominant offset
  and noise source, and `L = 1 µm` rather than a minimum length is the direct
  consequence of `sim/device-characterization-report.md` §3.3's warning that
  effective area, not drawn width, is what buys matching.
- **Latch**: StrongARM, 8/0.5 µm input pair, single clock phase, precharged
  high on `clk` low. Its offset and noise are divided by `A_v` when referred to
  the comparator input, so it is sized for speed, not matching.
- **Output**: one small inverter per regeneration node driving a NOR SR latch,
  so the decision is held through the next reset phase — the SAR logic (#11)
  reads a level, not a pulse. **The inverters are load-bearing, not buffering
  for its own sake.** The obvious circuit — a NAND SR latch wired straight to
  the StrongARM outputs — was built first and measured **~10 mV (≈ 3 LSB) of
  hysteresis**: an SR latch's held state loads the two regeneration nodes
  asymmetrically (the node driving the NAND whose output is LOW sees that
  output swing, Miller-multiplying its `C_gd` by ~26 fF against a regeneration
  node of a few tens of fF), so the latch is biased toward the answer it
  already holds. In a SAR, where one comparator makes ten successive decisions
  on a shrinking residue, that is a **code-dependent error, not an offset**, and
  digital offset removal cannot touch it. The inverters are identical, both of
  their inputs precharge to `V_DD`, and neither loading depends on the held
  state.
- **Bias**: a 10 µA current **into** the `ibias` pin is the block's contract.
  Bias generation is out of scope here (see Consequences). The block's real
  static draw is **~20 µA** (mirror diode branch + tail), not 10 µA.
- **Input polarity**: NMOS, matched to the constant `V_cm = V_REF/2 = 1.65 V`
  DR-0006 produces. Measured `V_th(NMOS, L = 1 µm) = 0.635 V` nominal, 0.817 V
  at slow/cold (`sim/device-characterization-report.md` §3.2), so the pair has
  ~0.8 V of common-mode headroom at the worst corner.
- **Offset cancellation: tier 0** — none, plus one-time digital offset
  subtraction. Justified in `spec/comparator-budget-memo.md` §4 against #4's
  measured `A_Vt`, not against an assumed value, and admissible only because
  DR-0006 holds the input common mode constant.
- **Noise-verification path: `.noise` on the preamplifier for the dominant
  term, plus an explicit analytic bound on the latch's residual contribution** —
  `spec/prior-art-survey.md` §3.5's "lowest cost" row, which only this topology
  admits. The full `trnoise` Monte Carlo campaign the dynamic topologies would
  need is **not** run, and the reason it is not needed is a property of this
  decision, not an omission (see Consequences). The latch's own noise is bounded
  rather than measured because ngspice injects no device noise into a transient
  at all — no analysis in this flow can reach it, for any topology.

### Why this beats the survey's primary, traced to measured data

| Input (survey §3.3 / §3.4) | Bare StrongARM | **Static preamp + StrongARM (chosen)** |
|---|---|---|
| Input-pair 3σ offset at #4's measured `A_Vt` | 1.8 LSB at 40/0.5 µm (`devchar` §3.3, quoted) — **before** any latch term | **1.11 LSB** at 40/1 µm (measured, `sim/comparator-offset-mc/`); 1.19 LSB with the latch term |
| Latch-referred offset | added through the input stage's own modest gain | divided by measured `A_v ≈ 16` → a minority term in quadrature |
| Fits ratified ≤ 2 LSB untrimmed at tier 0? | **no** — forces tier 2 (capacitive trim + calibration FSM + trim register) | **yes**, measured with margin |
| Noise verification in ngspice | `trnoise` MC, 10³–10⁴ runs/corner × 45 corners | `.noise`, 45 points in ~5 minutes |
| Kickback into the CDAC top plate | worst of the shortlist; regeneration nodes couple to the top plate through the input pair's `C_gd` at a 3.3 V swing (2.75× a 1.2 V design, survey §3.6) | preamp is unidirectional; measured in `sim/comparator-kickback/` |
| Static power | zero | 19.6 µA × V_DD = **65 µW measured** (72 µW at `ff_125c_3.63v`) — a real, stated cost |
| Clock phases | one | one (plus a DC bias pin) |
| Hysteresis between successive decisions | not measured here | **measured, and designed out** — see the Output bullet |

The trade is explicit: **~65 µW of static power buys the offset headroom that
keeps cancellation at tier 0 and the only noise-verification path this toolchain
can close cheaply.** With switching energy the block measures 89 µW at nominal
and **108 µW at the ratified power corner** (`ff_125c_3.63v`) — 10.8 % of the
< 1 mW row, 22 % of the < 500 µW stretch. Measured against the ratified rows:
3σ offset **1.19 LSB** (row: ≤ 2 LSB), input-referred noise **153 µV rms**
worst-case (allocation: 537 µV at the ENOB stretch), worst-case decision delay
**863 ps** (decide phase: 31.25 ns), signal-dependent kickback **2 µV**
(0.0006 LSB).

## Alternatives considered

- **Bare StrongARM latch, single stage** (survey §3.7 item 1, its primary) —
  **not chosen**, and the reason is #4's measured mismatch, not a preference.
  At the survey's own candidate geometry the input pair alone spends 1.8 of the
  2 LSB untrimmed offset budget (`devchar` §3.3), leaving nothing for the
  latch's own mismatch, which in this topology is referred back through only a
  small input-stage gain. Restoring the budget means either growing the input
  pair by ~4× in area (which slows the comparator and enlarges kickback) or
  moving to cancellation tier 2 — a programmable capacitive trim plus a
  calibration FSM and trim register, i.e. new digital scope for #11 and a
  foreground calibration mode this block does not otherwise need. On top of
  that it would force the expensive `trnoise` Monte Carlo path for noise
  (survey §3.5) and it is the worst of the shortlist for kickback into the CDAC
  top plate at a 3.3 V regeneration swing. Reconsider if a future PDK revision
  or a foundry mismatch dataset lowers `A_Vt` materially, or if the power budget
  tightens below the ~65 µW this decision spends.
- **Double-tail latch-type sense amplifier** (survey §3.7 item 2) — not chosen.
  It improves kickback isolation and common-mode range over a bare StrongARM,
  but it does **not** solve the problem that actually binds here: its input
  pair's own mismatch is still referred to the input undivided, so it lands in
  the same place against #4's `A_Vt`, while costing a second clock phase or an
  internally derived delay (which DR-0003's external-clock contract would have
  to absorb) and ~1.5–2× the area. It also remains a reset-and-regenerate
  structure with no DC operating point, so it inherits the expensive noise path.
  Its historical low-supply motivation is neutralized at 3.3 V (survey §0.5,
  §3.6) and is deliberately not cited here.
- **Dynamic / integrating preamplifier + latch** — not chosen. It would keep
  the zero-static-power property and divide the latch's offset, but its gain is
  set by an integration window rather than by a bias point, so it has no DC
  operating point either: the noise claim would again need the 10³–10⁴-run
  transient campaign, and the gain that divides the latch offset would itself
  become PVT- and timing-dependent (and would have to be re-verified against
  every change #12 makes to the bit-cycle timing). The static preamp trades
  65 µW for removing both of those couplings.
- **Time-domain comparator** — not shortlisted by the survey (§3.2) and not
  reconsidered: delay-based resolution scales the wrong way with a 3.3 V
  supply, and nothing in this block's spec asks for it.
- **Offset-cancellation tier 2, capacitive latch-load trim** (survey §3.4 row 2,
  the survey's recommended escalation) — not chosen *because tier 0 measurably
  fits*, which is the order §3.4 prescribes ("pick the lowest row that meets the
  requirement"). Tier 2 is the named fallback if post-layout extraction (#17) or
  a foundry mismatch dataset pushes measured 3σ offset past the ratified 2 LSB;
  the sky130 12-bit open-source precedent the survey cites remains the reference
  implementation for it. Tiers 3+ (body-bias trim, current-DAC injection,
  auto-zero, chopping) are not reached for: each burns static power, a clock
  phase, or aux capacitance on the CDAC top plate, and none is needed while
  tier 0 holds.
- **Chopping / conversion averaging (tier 6)** — not chosen, and specifically
  incompatible with the 2 MS/s stretch: it converts offset into a throughput
  penalty this block has no room for.

## Consequences

- **The block is no longer zero-static-power.** 19.6 µA flows whenever the
  comparator is enabled — the mirror's diode branch sinking the forced 10 µA
  bias plus the mirrored tail — i.e. **65 µW at 3.3 V, 72 µW at the 3.63 V
  corner**, measured on the block's own supply
  (`sim/comparator-regeneration/`). It is 6.5 % of the < 1 mW row and 13 % of
  the < 500 µW stretch on its own, it is present during acquisition as well as
  conversion, and it does **not** scale down with sample rate the way the
  dynamic energy does (which is only 28 % of the block's total at 1 MS/s). A future low-power
  variant would have to power-gate the preamp between conversions, which is not
  designed here.
- **A 10 µA bias current becomes an interface requirement.** The `ibias` pin is
  a contract with a bias generator that does not exist in this repo's scope
  today. DR-0002 made `V_REF` external and DR-0006 added a `V_cm` rail; this
  adds a third off-block dependency. Whether the bias is generated on-chip or
  supplied externally is **not decided here** and should be raised as a
  follow-up issue alongside DR-0006's identical open question about `V_cm`.
  Nothing in this record's evidence depends on which way that goes: every
  testbench forces an ideal 10 µA and reports the sensitivity of gain and
  offset to it.
- **Offset removal is now a system-level requirement, not an internal one.**
  Tier 0 means the block ships with an untrimmed input-referred offset of
  ~1.2 mV (1σ). The ratified spec's own note calls offset "digitally
  removable", so this is in line with it — but it means the readback path
  (#11/#13) must subtract a stored constant, and #14's Monte Carlo must model
  offset as a per-instance constant rather than assume zero.
- **The noise claim rests on `.noise`, which is only valid because of this
  decision.** If a future record supersedes this one with any dynamic topology,
  every noise number under `sim/comparator-preamp-noise/` becomes inapplicable
  and the 10³–10⁴-runs-per-corner campaign returns. That coupling is the reason
  the verification path is written into this record rather than left to #13.
- **#13 (testbench suite) inherits a cheap noise path, and a specific residual
  obligation.** ngspice does not inject device noise into a transient at all
  (survey §3.5), so the latch's *own* noise cannot be measured by any analysis
  this toolchain has. It is bounded analytically in
  `spec/comparator-budget-memo.md` §5.3 and shown to be a minority term after
  division by `A_v`; #13 should carry that bound as an assumption, and revisit
  it only if a future ngspice gains device-level transient noise.
- **#12 (timing) gets a measured regeneration number, not the survey's
  estimate.** `sim/comparator-regeneration/` measures the decision delay and the
  regeneration time constant at all 45 PVT points; the worst-corner delay is
  **863 ps** against a 31.25 ns decide phase, so comparator delay is not a term
  in #12's critical path at either the ratified rate or the 2 MS/s stretch — a
  stronger statement than the survey's typical-corner "[E4]", and one that
  survives a deliberately pessimistic measurement (every delay is taken while
  flipping a latch that holds the opposite answer).
- **#14 (Monte Carlo) gets an offset distribution and a warning.** The offset is
  dominated by the preamp input pair's threshold mismatch, which
  `sim/device-characterization-report.md` §3.3 shows to be corner-invariant in
  this PDK, so corner and mismatch remain separable. Current-factor (β)
  mismatch is *included* in `sim/comparator-offset-mc/`'s measurement (the pair
  runs in moderate inversion) but load-resistor mismatch is **not modelled by
  this PDK at all** (`devchar` §5.1 class of gap) and is budgeted by hand.
- **#16 (floorplan) gets a symmetry requirement with a number attached.** Any
  layout-induced asymmetry between the two preamp branches adds directly to the
  input-referred offset, in the same units as the ~1.2 mV mismatch sigma
  measured here: 0.4 mV of systematic asymmetry would consume as much budget as
  a 10 % increase in `A_Vt`. The load resistors, not just the input pair, need
  common-centroid treatment — the PDK models no resistor mismatch, so layout is
  the only place that term can be controlled or even seen.
- **An SR latch may never be wired directly to the regeneration nodes again.**
  The hysteresis defect above was found only because the regeneration testbench
  strobes each instance twice with the input polarity reversed between strobes,
  so every measured decision has to flip a latch holding the opposite answer. A
  single-strobe deck — the obvious way to measure a comparator — passes happily
  with 3 LSB of hysteresis present. Any future change to the output stage
  (including a layout that adds asymmetric loading to `outp`/`outn`) has to be
  re-checked against that two-way test, and #16 should treat symmetry of the
  regeneration-node loading as a floorplan constraint alongside the input pair.
- **The netlist is a schematic-level design with no parasitics.** Every number
  in the evidence tree is `Netlist provenance: schematic`. Post-layout
  extraction (#17) can only add capacitance at the preamp output (lowering
  bandwidth and hence measured noise) and at the input (raising kickback), so
  the noise number is conservative in the right direction and the kickback
  number is **not**. That asymmetry is stated here so a post-layout re-run is
  read as a required check on kickback, not a formality.

## Spec lines affected

- `README.md#target-specification` — Offset error — clarified (no value
  change): the ratified `≤ 2 LSB, untrimmed … digitally removable` row is met
  at **cancellation tier 0**, i.e. with no analog trim of any kind; the
  "digitally removable" qualifier in the ratified row is now load-bearing
  rather than permissive.
- `README.md#target-specification` — Power @ 1 MS/s — clarified (no value
  change): this block contributes 65 µW of **static** power at 3.3 V (72 µW at
  3.63 V) plus 25 µW of switching power at 1 MS/s (36 µW at the fast/hot/high
  corner), i.e. **89 µW nominal and 108 µW at the ratified power corner**,
  against the < 1 mW row and the < 500 µW stretch. No row is relaxed; the allocation is recorded so
  #12/#13 can sum the block budgets.
- `spec/comparator-budget-memo.md#2-noise-allocation` — comparator noise
  allocation — new: **≤ 0.930 mV rms at ENOB > 9.0, ≤ 0.537 mV rms at the
  > 9.5 stretch**, i.e. the equal three-way split of the non-quantization
  budget already ratified in `README.md` note **[b]** and already taken by
  `spec/cdac-sizing-memo.md` §1.2 for the `kT/C` term. This record does not
  choose a new split; it records that the comparator takes the share the
  ratified table already allocates to it.
