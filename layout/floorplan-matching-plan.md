# Floorplan and matching plan — CDAC, comparator, analog/digital separation

**Issue**: #16. **Status**: planning document, no polygons drawn here — this
is the bridge between the schematic-phase decision records (#8–#11) and
whatever issue next elaborates the real cell layout, and the input #17's
post-layout extraction ultimately checks against.
**Consumes**: `spec/cdac-sizing-memo.md`, `spec/comparator-budget-memo.md`,
`sim/device-characterization-report.md` §5.1,
`sim/comparator-offset-mc/records/20260801-035221-90d7e67.md`,
[DR-0007 (track-switch topology)](../spec/decision-records/DR-0007-track-switch-topology.md),
[DR-0008 (SAR logic synchronous)](../spec/decision-records/DR-0008-sar-logic-synchronous.md),
[DR-0009 (no redundancy)](../spec/decision-records/DR-0009-no-redundancy.md),
[DR-0011 (CDAC switching scheme)](../spec/decision-records/DR-0011-cdac-switching-scheme.md),
[DR-0013 (input-pin charge split)](../spec/decision-records/DR-0013-input-pin-charge-split.md),
`design/cdac/cdac_array.sch`, `design/comparator/comparator.spice`,
`design/track-switch/track_switch.sch`, `layout/README.md` (DRC deck
coverage).
**Feeds**: #15 (DRC deck coverage — capacitor layer flagged below), #17
(post-layout extraction — the actual verification point for the routing/
parasitic claims here), and whichever future issue elaborates the real cell
layout.

Every matching-technique claim below cites the specific decision record or
evidence record it derives from, per `CLAUDE.md` ("Verification is the
product... no claim without a testbench"). Where a number in this document
is a planning estimate rather than a measured or derived one — principally
in the §4 area tally — it is labelled as such inline, the same convention
`spec/cdac-sizing-memo.md` §2 uses for its `literature-assumption-with-
derating` tag.

---

## 1. CDAC array floorplan

### 1.1 Array topology — plain binary, free-MSB/MCS, per DR-0009/DR-0011

The array is **plain binary, not segmented or redundant** — a `2^(N-1) =
512`-unit-position, differential, top-plate (MCS/Vcm) sampling array per
side. Bit 1 (the MSB) is resolved directly from the sampled charge with **no
array switching at all** — the free-MSB property that gives MCS its ~50 %
array-size reduction over a conventional charge-redistribution array
([DR-0011](../spec/decision-records/DR-0011-cdac-switching-scheme.md)
Decision). The remaining 9 bits (2..10) are resolved by a 511-position
binary-weighted sub-array (weights `2^8..2^0` = 256..1) plus one fixed
terminating unit (weight 1, permanently released to `V_cm`, never switched),
summing to the full `2^(N-1)` capacitance — 512 unit-cap positions per side,
1024 total across both sides.

`design/cdac/cdac_array.sch` elaborates this structurally: the two
boundary/worst-case weighted positions (`256`, the sub-array's own MSB and
`sim/cdac-bit-settling/`'s measured worst settling case, and `1`, the LSB)
plus each side's terminating dummy and sampling switch, with the seven
omitted weighted positions (128, 64, 32, 16, 8, 4, 2) stated in-schematic as
identical copies scaled by the cap's `m=` multiplicity parameter. **This
floorplan elaborates the full 512-position array as the layout unit of
planning**, not the two-position schematic excerpt — the schematic's own
comment flags that a future layout-facing issue must either draw the full
array or generate it programmatically, and this plan treats that as a given
of the floorplan rather than a decision still open.

[DR-0009](../spec/decision-records/DR-0009-no-redundancy.md) confirms this
array carries **no redundancy or non-binary weighting** at the
simulation-complete milestone — one decision per trial, no bit overlap, no
digital error-correction adder — so the floorplan does not need to reserve
area or routing for a correction network. DR-0009 states this is a defer,
not a permanent rule, with a concrete revisit trigger tied to measured
comparator/logic timing margin; nothing here forecloses that.

### 1.2 Capacitor structure and layer — MiM, `cap_mim_2f0fF`

The unit capacitor is **MiM**: the PDK's stack-agnostic `cap_mim_2f0fF`
subckt (2.0 fF/µm² density), drawn `C_u = 17.24 fF` at **2.71 µm × 2.71 µm**
per `spec/cdac-sizing-memo.md` §4 — sized to the `< 0.5 LSB` (stretch)
matching target at 3σ, not merely the `< 1 LSB` baseline (memo §4's
deliberate choice, costing negligible extra area). Every weighted position
in `design/cdac/cdac_array.sch` instantiates this same subckt with an `m=`
multiplicity parameter carrying the position's binary weight (e.g. `Cp256`
at `m=256`), which the memo (§5.4) states is a faithful layout
representation: `m` parallel unit devices is exactly what the drawn array
implements.

**Flag to #15**: this capacitor layer falls **outside** the four layers
`layout/README.md` documents the current `gf180mcu` `klt drc` deck covering
(`Comp`/`Poly2`/`Contact`/`Metal1`). The MiM stack (`Metal4`, `FuseTop`,
`Via4`, `Metal5`) is explicitly named in `layout/README.md` as not covered
in the pinned release or on `klayout-tools` `main`, and #15's own bring-up
already anticipated and confirmed this gap — filing it generically upstream
as
[klayout-tools#188](https://github.com/2AMLogic/klayout-tools/issues/188)
(no MiM/upper-metal rule coverage) and
[klayout-tools#189](https://github.com/2AMLogic/klayout-tools/issues/189)
(no coverage-manifest signal, so an uncovered-layer layout reports
`clean`). This plan's job is only to state the layer definitively for
whoever runs `klt drc` against the real array: **a clean DRC report over
this array's MiM geometry means nothing was checked, not that the
capacitor structure is rule-clean.** No new klayout-tools issue is filed
from this document — that stays #15's acceptance criterion, already met.

### 1.3 No capacitor mismatch model — the matching argument here is layout discipline, not simulation

`sim/device-characterization-report.md` §5.1 (confirmed in
`spec/cdac-sizing-memo.md` §2) finds the gf180mcu open PDK provides **no
local (device-to-device) capacitor mismatch model of any kind**:
`cap-local-mismatch` and `moscap-statistics` are both **ABSENT** findings
from `sim/tools/pdk_mismatch_audit.py`. The PDK's `mimcap_statistical`
section defines only die-global (`sw_stat_global`) terms, which cancel
exactly in a capacitor ratio and contribute zero DNL/INL — there is no
statistical section for local mismatch at all.

**Consequence, stated as a requirement**: every common-centroid / dummy-ring
technique in this section is a **layout-discipline argument**, grounded in
standard capacitor-matching practice and the Pelgrom-law sizing
`spec/cdac-sizing-memo.md` §2–§4 already used (with a 2× literature-derated
`A_C = 2.0 %·µm` planning value, flagged there as unverified in this repo),
not a claim this repo's simulation flow can verify. No Monte Carlo run
against gf180mcu's capacitor models — however large — will produce a
non-zero mismatch distribution to check a layout against
(`sim/device-characterization-report.md` §5.1). The floorplan below is
therefore written to the discipline a foundry-verified matching flow would
demand, on the assumption that the risk is real even though this repo
cannot simulate it, and is explicit that it stays unverified until either
foundry MiM matching data replaces the `A_C` placeholder or #17's
post-layout flow gains a mismatch-capable extraction path.

**Floorplan technique** (layout discipline, not simulated):

- **Common-centroid placement of the binary-weighted unit-cap array.**
  Because `m=` multiplicity means each weighted position is `m` parallel
  physical unit cells, the natural implementation is to draw one unit-cap
  cell and tile it: interleave each weighted position's `m` unit cells
  across the array footprint (e.g. a standard binary-weighted common-
  centroid tiling such as a modified switching-sequence or bit-slice
  interleave) rather than laying each weight out as a contiguous block. A
  contiguous-block layout would let any gradient (oxide thickness, etch
  bias, stress) across the die correlate with weight — exactly the
  systematic-mismatch mechanism common-centroid tiling exists to cancel —
  and would do so on the array's own binding constraint (§1.1's `σ(DNL)_max
  ≈ 22.61·σ_u`, `spec/cdac-sizing-memo.md` §3.2, the DNL-binding coefficient
  for this free-MSB topology, not the plain-binary `31.98·σ_u`).
- **Full dummy ring** around the tiled array perimeter, matched to the unit
  cell's own geometry (same MiM stack, same drawn size), so every real unit
  cap — including those at the array's edge — sees the same local
  environment (etch loading, edge proximity) as an interior cell. Edge cells
  without a dummy border are a well-known source of systematic (not
  Pelgrom-random) mismatch that a Pelgrom-law sizing argument does not
  price in at all.
- **Shielding**: top-plate routing (§1.4) and bottom-plate switch routing
  are kept off the capacitor dielectric stack itself and routed in metal
  layers above/beside the array rather than crossing it, so routing-induced
  parasitic asymmetry does not add a second, unmodelled mismatch mechanism
  on top of the process-driven one this section addresses.

### 1.4 Top-plate routing strategy

Per-side top-plate routing (the node the comparator's preamp directly
inputs, §2.3) is planned to minimize parasitic capacitance and to keep
routing symmetric between the two sides:

- **Single top-plate net per side**, routed in one metal layer with the
  shortest practical path from the array's electrical center to the
  comparator input pin, rather than daisy-chained across the tiled unit
  cells — daisy-chaining adds series routing resistance/capacitance that
  differs cell-to-cell and would itself be a source of the layout-induced
  asymmetry §2.1 requires controlling on the comparator side.
- **Symmetric routing between the P and N sides**, matched in length and
  layer, so the array does not introduce a systematic P/N top-plate
  parasitic mismatch that would show up as comparator-input-referred offset
  or as a gain-error term distinct from the switch-driven one
  [DR-0013](../spec/decision-records/DR-0013-input-pin-charge-split.md)
  already closed.
- **No routing crossing the array's own dielectric layers** (§1.3's
  shielding point) — top-plate routing runs above the array in a layer that
  does not couple into the MiM capacitor stack itself.

**This plan states the routing strategy, not a verified parasitic number.**
`spec/cdac-sizing-memo.md` §5.3 already shows the *simulated* (schematic-
level, ideal-cap) settling margin is enormous — four orders of magnitude
inside the 0.5 LSB settling bound at every PVT point — but that result
contains no layout parasitics. **#17's post-layout extracted re-run is the
actual verification point for whether this routing plan held**; this
document is not a substitute for that measurement, and the top-plate node is
explicitly the one this design most needs left uncorrupted (`spec/
comparator-budget-memo.md` §4's own framing, in the context of why higher
offset-cancellation tiers were rejected — anything hung on the top plate
costs settling margin and kickback risk this array does not have to spend).

### 1.5 Switch placement — 4× CMOS transmission gate with charge-injection-compensation dummies

**Sampling/track switch topology**: 4× upsized CMOS transmission gate
(NMOS `W = 40 µm`, PMOS `W = 80 µm`, `L = 0.28 µm`), with charge-injection-
compensation dummy devices on the hold node, gated on the complementary
clock phase, **not bootstrapped**
([DR-0007](../spec/decision-records/DR-0007-track-switch-topology.md)
Decision) — the `tg4dum` configuration, captured in
`design/track-switch/track_switch.sch`. One instance per input pin (per
side in differential mode; the single driven pin in single-ended mode).

**Dummy sizing — revised by DR-0013, not the DR-0007 half-width figure.**
DR-0007 originally specified a textbook half-width (1:2) dummy; DR-0013
measured that ratio failing the `Gain error ≤ 0.5 LSB` row by 7–11× and
re-derived the correct fix: the turn-off charge split is not a fixed
property of the switch alone but depends on source impedance, so DR-0013
pins the split with a required external input-pin capacitor (`C_pin`,
100 pF–1 nF) and revises the dummy-to-main **width ratio to 7/16 = 0.4375**
— dummy NMOS `17.5 µm`, dummy PMOS `35.0 µm`, both `L = 0.28 µm`
([DR-0013](../spec/decision-records/DR-0013-input-pin-charge-split.md)
Decision). `design/track-switch/track_switch.sch` already reflects this
(`MDN`/`MDP` at `W=17.5u`/`W=35u`). **DR-0013 states the layout-facing
consequence directly, and this plan follows it**: "the dummy ratio is to be
drawn as a finger count, not as a width — 7 of the main device's 16 fingers
— so the dummy is a literal replica slice of the main device and the ratio
survives process bias on the drawn width, which a separately-dimensioned
dummy would not." This plan's switch-placement rationale is written to that
requirement.

**Placement rationale**:

- **Symmetric dummy placement relative to the main switch is required for
  the compensation to hold**, not merely proximity to the array. Because
  the dummy ratio is drawn as a finger-count fraction of the main device
  (7 of 16 fingers, DR-0013), the dummy's fingers are laid out as literal
  replica slices interleaved with or immediately adjacent to the main
  device's own fingers — the construction that lets the ratio survive
  process bias on the drawn width (DR-0013's own stated reason for the
  finger-count requirement). An asymmetric or merely-nearby dummy
  placement would reintroduce exactly the drawn-vs-effective-width
  mismatch DR-0013's finger-count requirement exists to avoid.
- **Both main-device terminals (source/drain shorted onto the hold node)
  and the dummy's terminals land on the same top-plate node the array
  routes to §1.4's plan** — the switch sits at the array's input edge,
  between the external input pin/pin-capacitor network (DR-0013) and the
  array's electrical center, not embedded inside the tiled unit-cap array
  itself, so its own layout does not disturb the common-centroid tiling of
  §1.3.
- **One switch instance per input pin** (2 instances total in differential
  mode) is placed at each side's own array edge — no shared switch between
  sides, consistent with DR-0007's Decision that the switch topology
  applies identically, and independently, to each side.

### 1.6 CDAC bit-trial decode switches — a separate, smaller structure, currently unsized for layout

Distinct from the input sampling switch above, each of the array's 9
weighted positions per side carries its own bottom-plate decode switches —
release-to-`V_cm` (`rel`), engage-to-`V_REF` (`sel_hi`), and engage-to-`GND`
(`sel_lo`) — three T-gates per weighted position, 27 T-gates per side, 54
total across both sides (`design/cdac/cdac_array.sch`). These are currently
drawn at the **nominal 10 µm/20 µm characterization geometry**, the same
placeholder geometry
[DR-0007](../spec/decision-records/DR-0007-track-switch-topology.md)
measured failing the SFDR floor for the *input* sampling function — DR-0007
Consequences states explicitly that its 4× resizing "does not yet replace
the placeholder 10 µm/20 µm T-gate wired inline into
`design/cdac/cdac_array.sch`'s `samppN`/`samppP`/`sampnN`/`sampnP`
instances," and the per-weight `rel`/`sel_hi`/`sel_lo` triples were never in
scope for that record at all — they switch a fixed reference rail
(`V_cm`/`V_REF`/`GND`), not a moving input, so the track-mode SFDR argument
that drove the input switch's 4× sizing does not directly apply to them.
**This plan does not resize them** — that is real design scope belonging to
whichever issue next elaborates the full array, not a floorplan decision —
but flags them as a real, currently-placeholder area and switching-noise
contributor: each decode triple sits adjacent to its own weighted cap
position (following the position's location in the common-centroid tiling
of §1.3, not clustered separately), so their layout is bound to the array
tiling plan rather than being a free placement choice.

---

## 2. Comparator floorplan

### 2.1 Common-centroid IS required for both preamp branches, including the load resistors

`spec/comparator-budget-memo.md` §9 addresses this issue directly: **the two
preamp branches — including the 150 kΩ load resistors, not just the input
pair — need common-centroid treatment.** This is stated as the memo's direct
conclusion and is not a threshold call this document re-derives:

> "#16 (floorplan): the two preamp branches — including the 150 kΩ load
> resistors, not just the input pair — need common-centroid treatment.
> Numerically: 0.4 mV of layout-induced systematic asymmetry costs as much
> budget as a 10 % increase in `A_Vt`, and the PDK models no resistor
> mismatch at all (§3.4), so layout is the only place that term can be
> controlled or even seen."

The quantitative basis (`spec/comparator-budget-memo.md` §3.4): this PDK
wires `*(1+mis_r*sw_stat_mismatch)` into every resistor subckt and then
hard-sets `mis_r = 0` — gf180mcu models **zero** resistor mismatch, verified
by `sim/comparator-offset-mc/`'s own two-resistor null control
(`sig_rpair_uv` reads `0` or numeric-noise-floor `~1e-11` µV at every
completed corner in
`sim/comparator-offset-mc/records/20260801-035221-90d7e67.md`, row `sig_rpair_uv`).
With the preamp's `gm·R` structure, the memo derives that a fractional load
mismatch `δ` contributes `δ·V_ov/2` to input-referred offset, so a modest
0.5 % load-resistor mismatch would add roughly 0.5 mV — comparable to the
input pair's own threshold-mismatch term (§3.1's `σ(ΔV_th)` at the chosen
`L = 1 µm` geometry, 1.235 mV) — and this term is **entirely un-modelled**
in simulation, the largest un-modelled term in the whole offset budget
(memo §3.4, §10 item 2).

**Floorplan technique**: both `Xrlp`/`Xrln` (the two 150 kΩ, `1 µm × 75 µm`,
unsalicided p+ poly resistors in `design/comparator/comparator.spice`) are
laid out **interdigitated/common-centroid**, split into matched segments
placed symmetrically about the preamp's own layout axis, alongside the
input pair (`Xmip`/`Xmin`, `40/1 µm` each) treated the same way — not merely
placed near each other, but tiled so that any process gradient across the
cell affects both branches identically. This is the same layout-discipline
argument as §1.3's CDAC case, applied to a device this PDK's resistor model
also cannot simulate mismatch for.

### 2.2 Context: the measured offset margin does not license skipping load-resistor symmetry

For context, not as a threshold to re-derive: measured worst-corner
comparator offset is **σ(V_os) = 1.195 mV** (`tt_27c_3.63v`,
`sim/comparator-offset-mc/records/20260801-035221-90d7e67.md`, column
`sig_vos_mv`), **3σ = 3.58 mV = 1.11 LSB** (column `vos_3sig_lsb`, worst
value 1.11221 at `tt_27c_3.63v`) against the ratified `≤ 2 LSB` offset row —
**0.81 LSB (41 %) of margin unspent**, per `spec/comparator-budget-memo.md`
§3.3's combined preamp+latch total.

**This margin does not license skipping load-resistor symmetry.** The
measured 1.195 mV/1.11 LSB figure is the preamp's threshold-mismatch term
only — `sim/comparator-offset-mc/`'s own null control confirms load-resistor
mismatch is exactly zero in this simulation, not small (§2.1 above), so the
margin reported above has never had the real, un-modelled load-resistor term
subtracted from it. The memo's own framing (§3.4, §10 item 2) is that this
margin is "reported rather than spent" for exactly this reason. Common-
centroid layout of the load resistors is the only place this term can be
controlled, since it cannot be measured in this repo's simulation flow at
all — the same "layout discipline, not simulation-verified" framing as
§1.3.

### 2.3 Top-plate kickback-routing constraint

The comparator's input **is** the CDAC top plate (DR-0011's top-plate
sampling), so the two floorplans are not independent: `spec/comparator-
budget-memo.md` §5 measures kickback from the comparator back into the
top-plate node as a first-class term (residual signal-dependent kickback
`≤ 0.00062 LSB`, well inside the DNL target, but measured at
schematic-level with **no parasitics** — post-layout extraction moves
kickback the *unsafe* direction per §5.2's own caveat, unlike noise).

**Floorplan constraint, stated directly by the memo (§9)**: "the comparator's
input is the CDAC top plate, so the kickback path is also a floorplan
constraint: keep the latch's regeneration nodes away from top-plate
routing." The regeneration nodes are `outp`/`outn` in
`design/comparator/comparator.spice` — the StrongARM latch's cross-coupled
output pair, which swing rail-to-rail during regeneration and are the node
the 3.3 V latch-swing kickback risk (`spec/prior-art-survey.md` §3.6's
2.75× penalty at 3.3 V vs. a 1.2 V design) originates from. This plan
routes:

- The top-plate nets (§1.4) into the preamp's input pins (`vinp`/`vinn` in
  the comparator subckt) directly, on the shortest practical path, with the
  StrongARM latch and its regeneration nodes physically set back from that
  routing rather than interposed near it.
- The latch's own supply and clock (`clk`) routing kept separate from the
  top-plate routing corridor, so latch switching transients do not couple
  capacitively into the top-plate net through adjacent routing.

`spec/comparator-budget-memo.md` §5's static-preamp topology is itself the
primary defense here (a unidirectional buffer between the top plate and the
regenerating nodes, so the 3.3 V latch swing never reaches the top plate
through an input pair's `C_gd`) — the floorplan constraint above is the
second, layout-level line of defense on top of that topology choice, and
**#17's post-layout re-run of `sim/comparator-kickback/` is the actual
verification point**, per the memo's own stated limitation, not this
document.

### 2.4 SAR-logic isolation — against the actual clocked switching source

Isolation from digital switching noise is stated against the design's
actual switching source, not a generic "digital logic" assumption:
[DR-0008](../spec/decision-records/DR-0008-sar-logic-synchronous.md)
ratifies **synchronous** SAR control logic — an external clock (**16 MHz**
at the 1 MS/s target, **32 MHz** at the 2 MS/s stretch) stepping a **one-hot
16-phase sequencer** through sample → 10 bit trials → output/reset every
conversion, deterministically. This is a known, periodic, high-activity
digital switching source physically adjacent to the array/comparator, not
an occasional or asynchronous one.

**Isolation technique**:

- **Guard rings** around both the comparator cell and the CDAC array,
  tied to dedicated substrate/well contacts on the analog supply domain
  (§3), separating the analog core's substrate return path from the SAR
  logic's.
- **Physical spacing** between the SAR logic block (the 16-phase sequencer,
  the 9-slice decode register per
  [DR-0009](../spec/decision-records/DR-0009-no-redundancy.md), and any
  clock buffering) and the comparator/CDAC array, with the guard ring
  occupying the boundary between them rather than the blocks abutting.
- **Dedicated supply routing** for the comparator and the sampling path,
  separate from the SAR logic's own supply rails (detailed in §3) — the
  16/32 MHz clock edges are the dominant supply-noise source on the digital
  rail, and isolating that rail from the analog one is the primary defense
  against the SAR logic's switching coupling into the comparator's
  regeneration decision or the CDAC top plate.
- **Clock routing** kept off the top-plate routing corridor (§2.3) and off
  the comparator cell's regeneration-node routing specifically — the
  16/32 MHz clock is the single highest-*du/dt* net in the design and the
  one most likely to couple capacitively into a sensitive analog node if
  routed adjacent to it.

This is a deterministic, known switching pattern (one clock edge per bit
trial, 16 phases per conversion, `sim/sar-logic-functional/` measures
`conv_period_ns = 1000.0 ns` exactly at all three supply corners) rather
than a data-dependent or asynchronous one, which is what makes fixed
physical spacing and dedicated routing a tractable isolation strategy —
DR-0008's own Consequences note this determinism is also what makes the
analog core verifiable standalone against an ideal clocked bit pattern,
the same property that makes its physical isolation plannable here rather
than needing a self-timed handshake's more elaborate mitigation.

---

## 3. Analog/digital separation

**Dedicated analog supply routing** (separate from the digital/SAR-logic
domain):

- **Sampling path**: the input pins, the `C_pin` network boundary
  ([DR-0013](../spec/decision-records/DR-0013-input-pin-charge-split.md)),
  and the track/sample switch (§1.5) — this path carries the signal before
  any quantization decision has been made, so any coupled noise here is
  indistinguishable from input signal and is not removable downstream.
- **Comparator**: preamp, StrongARM latch, isolation inverters, and the SR
  output latch (§2) — the offset/noise budget in `spec/comparator-budget-
  memo.md` is derived against a clean supply; injected supply noise is not
  a term either §2 or §7 of that memo accounts for.
- **CDAC array and its reference rails**: `V_REF`, `V_cm`, and `GND` as
  routed to the array's bottom plates
  ([DR-0011](../spec/decision-records/DR-0011-cdac-switching-scheme.md))
  — DR-0002's reference-drive envelope (`Z_ref ≤ 240 Ω`, `C_dec ≥ 40 nF`)
  is sized against a clean reference; digital-domain noise coupled onto
  these rails inside the die would not be visible to that external
  decoupling budget at all.

**Shared/digital routing**: the SAR logic's own supply, the 16/32 MHz clock
distribution, and the digital control signals it generates for the CDAC's
per-weight decode switches (§1.6) and the track switch's `clk`/`clkb`
phases (§1.5) — these are high-activity, periodic nets that do not carry
analog signal information themselves, so they are routed on the shared
digital domain rather than costing dedicated analog routing.

**Why the split is drawn at this boundary, not at (e.g.) the CDAC-array/
comparator boundary**: every node listed as "dedicated analog" above
directly participates in the signal path whose error budget this repo's
spec rows constrain (§1.3, §2.1's un-modelled matching terms; DR-0011's
`V_cm`/`V_REF` rails the array's linearity is a ratio of), while every node
listed as "shared/digital" is a control signal whose *value* (not its
noise) is what the analog blocks consume — a control signal glitching a
few tens of ps late costs timing margin (DR-0008's ~50 ns rung-1 margin,
still comfortable), while supply noise coupled onto the top plate or the
comparator's regeneration nodes costs accuracy directly and is not
recoverable by any downstream correction this design has (tier 0 offset
cancellation, `spec/comparator-budget-memo.md` §4, corrects a static
offset — not injected transient noise).

---

## 4. Area budget (provisional)

### 4.1 Ratification status

The original issue framing (and this issue's curator pass) treated the
`< 0.1 mm²` area row as a **draft-spec comparison**, pending issue #1's
ratification. **That status has since changed**: issue #1 closed on
2026-07-31, and
[DR-0006](../spec/decision-records/DR-0006-spec-ratification.md) records
the target specification — including the `< 0.1 mm²` area row — as
**ratified**, with the operator's engineering ratification authority per
#1. This document therefore compares against a ratified target, not a
draft one.

**That does not make the tally below anything other than provisional.**
Ratification of the *target* does not create a measured *result* — no real
cell layout exists yet for any block in this design (this issue's whole
premise, per its "hold" framing), so every number below is a planning
estimate, not a drawn-layout measurement, regardless of the target row's
ratification status. The distinction that matters here is measured-vs-
estimated, not draft-vs-ratified, and every line below is estimated.

### 4.2 Running tally

| Component | Basis | Estimated area | Confidence |
|---|---|---|---|
| CDAC array — unit-cap core | **Grounded**: 1024 unit-cap positions (512/side × 2 sides) at `2.71 µm × 2.71 µm = 7.34 µm²` each, `spec/cdac-sizing-memo.md` §4 | 7,520 µm² (0.00752 mm²) | Direct from ratified sizing |
| CDAC array — bit-trial decode switches | Grounded device count (54 T-gates, §1.6), currently-nominal `10/20 µm` geometry, `design/cdac/cdac_array.sch` | ~450 µm² raw channel area (0.00045 mm²) before layout overhead | Grounded count, placeholder geometry — see §1.6 |
| CDAC array — dummy ring, tiling spacing, top-plate/bottom-plate routing | **Planning estimate**: common-centroid tiling + full dummy ring + inter-cell routing typically adds 50–100 % over bare cap area for a matched array of this size (not measured, not derived from any record in this repo) | +50–100 % of the two rows above | Unmeasured planning multiplier |
| **CDAC array subtotal** | | **~0.012–0.016 mm²** | Mixed |
| Comparator (preamp incl. 150 kΩ resistors, StrongARM latch, isolation invs, NOR SR latch) | Grounded device sizes (`design/comparator/comparator.spice`); common-centroid layout overhead (§2.1) is a **planning estimate**, typically 5–8× raw device area for a small interdigitated analog cell | ~0.0015–0.003 mm² | Mixed — sizes grounded, layout multiplier unmeasured |
| Track/sample switch (main, 2 instances differential mode) | Grounded device sizes: `40/80 µm` main + `17.5/35 µm` dummy per side ([DR-0007](../spec/decision-records/DR-0007-track-switch-topology.md)/[DR-0013](../spec/decision-records/DR-0013-input-pin-charge-split.md)); layout overhead for a multi-finger power-MOS structure is a **planning estimate** | ~0.0008–0.0015 mm² | Mixed — sizes grounded, layout multiplier unmeasured |
| SAR logic (16-phase one-hot sequencer, 9-slice decode + terminating register, [DR-0008](../spec/decision-records/DR-0008-sar-logic-synchronous.md)/[DR-0009](../spec/decision-records/DR-0009-no-redundancy.md)) | **No cell-level or synthesized area exists** (`design/sar-logic/` is rung-1, ideal-digital only); order-of-magnitude planning guess for a few-hundred-gate control block in a mature 180 nm-class std-cell library | ~0.001–0.005 mm² | **Least grounded line in this tally — replace once digital implementation begins** |
| Guard-ring / analog-digital boundary / global routing overhead | **Planning estimate**: ~30 % of the summed core blocks, common mixed-signal planning convention, not measured | +30 % of the four rows above | Unmeasured planning multiplier |
| **Total (provisional)** | | **~0.02–0.03 mm²** | Provisional |

### 4.3 Comparison against the `< 0.1 mm²` target

At roughly **0.02–0.03 mm²**, the provisional tally sits at **20–30 % of the
ratified `< 0.1 mm²` target** — a 3–5× margin on the low estimate. The CDAC
array (§1) dominates the tally, consistent with the general pattern noted
in `spec/prior-art-survey.md` §1.3 (capacitor area is a small but
non-negligible fraction of an SAR ADC's total budget) and with this design's
own topology (a 512-position/side array with a 17.24 fF unit cap sized to
the stretch matching target, `spec/cdac-sizing-memo.md` §4). The comparator,
track switch, and SAR logic are each estimated as small fractions of the
CDAC array's footprint, in line with the general pattern that CDAC arrays
dominate SAR ADC area at this class of resolution.

**This margin should not be read as settled.** Every non-CDAC-cap-core line
in §4.2 carries an explicitly unmeasured layout-overhead multiplier, and the
SAR-logic line has no grounding at all beyond an order-of-magnitude guess.
The margin is wide enough (3–5×) that it is unlikely a real layout erases
it, but "unlikely" is not a claim this repo's own verification standard
accepts without a testbench — the tally should be revisited and replaced
with real numbers as soon as (a) `design/sar-logic/` gets a synthesized or
hand-drawn cell area, and (b) the CDAC array, comparator, and track switch
get real cell layouts, at which point this section should be superseded
(per the append-only convention this repo already applies to `sim/` and
`layout/drc/` evidence) rather than edited in place.

### 4.4 Superseded by the as-drawn tally (issue #57)

Per §4.3's own instruction, this section is **superseded, not edited**: the
block layout now exists (`layout/adc-top/`, issue #57) and
[`layout/adc-top/README.md` §"Area, as drawn"](adc-top/README.md) carries
the measured, generator-written tally (`layout/adc-top/area.json`) that
replaces every estimate above. Headline: **0.09619 mm² as drawn against the
ratified `< 0.1 mm²` row** — inside it, with ~4 % margin, where §4.2
predicted 0.02–0.03 mm². (It read 0.0991 mm² when this section was written
at issue #57/#62, then 0.1136 mm² — over the row — after DR-0014's redraw
added a fourth decode leg per CDAC cell (#66), then came back inside it when
the device-row column pitch was set from the deck's own `comp.space.1`
rather than from a round number (#67). The README's own "Area, as drawn"
section carries that history; this line is only the headline.)

The gap is not a design overrun. The two constructions the layout is forced
into by `klt`'s pinned capability surface — single-finger devices (the LVS
engine has no device-merge step) and single-metal-level planar channel
routing (the extraction deck exposes one metal level) — dominate everything
except the capacitor core, which came in at 18,265 µm² against §4.2's
7,520 µm² bare-cap figure, i.e. a 2.4× tiling/dummy-ring/spacing multiplier
against the 1.5–2× §4.2 assumed. That README states which upstream gaps
would move the number and by roughly how much; nothing in the ratified spec
row is relaxed here.

---

## 5. Summary for downstream issues

- **#15 (DRC/LVS)**: the CDAC's capacitor layer is MiM (`cap_mim_2f0fF`),
  confirmed outside the four layers the current `klt drc` deck covers —
  #15's own bring-up already anticipated and filed this generically
  (klayout-tools #188/#189); no new filing needed from this document.
- **#17 (post-layout re-run)**: this plan's top-plate routing strategy
  (§1.4) and kickback-isolation constraint (§2.3) are stated as plans, not
  verified parasitic numbers — #17's post-layout extracted re-run of
  `sim/cdac-bit-settling/` and `sim/comparator-kickback/` is the actual
  verification point for both.
- **Issue #57 (the real cell layout) — now closed against this plan**: see
  [`layout/adc-top/README.md`](adc-top/README.md) for the row-by-row
  implementation status of everything in §1–§4, including the two stated
  deviations (DR-0013's finger-count dummy and §2.1's common-centroid input
  pair are both drawn as symmetric-but-unsplit devices, because the pinned
  `klt` cannot LVS a split device against a lumped schematic device —
  klayout-tools#261).
- **Whichever issue elaborates the real cell layout**: inherits the
  common-centroid/dummy-ring plan for the CDAC array (§1.3) and the
  comparator's preamp branches including load resistors (§2.1) as
  layout-discipline requirements (not simulation-verified, per §1.3/§2.2),
  the switch placement/dummy-finger requirement of §1.5 (DR-0013's 7/16
  finger-count construction), the currently-unresized CDAC decode switches
  flagged in §1.6, the analog/digital supply-domain split of §3, and the
  provisional area tally of §4 — to be superseded with measured numbers
  once real layout exists.
