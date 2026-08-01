# DR-0007: Sample/track switch topology — 4× CMOS transmission gate with dummy compensation, not bootstrapped

- **Status**: proposed — requires operator sign-off
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #10
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #1, #3, #4, #6, #7, #10, #39 (follow-up: charge-injection gain error), [DR-0001](DR-0001-input-drive.md), [DR-0004](DR-0004-device-flavor.md), [DR-0006 (CDAC switching scheme)](DR-0006-cdac-switching-scheme.md), `spec/prior-art-survey.md` §5, `sim/device-characterization-report.md` §2.1/§2.2/§3.2, `sim/track-switch-thd/records/20260801-020125-267871b.md`, `sim/track-switch-sampling/records/20260801-023754-267871b.md`, `design/track-switch/track_switch.sch`

## Context

#10 must decide plain CMOS transmission gate vs. a bootstrapped switch for
the CDAC's input sampling switch, and back the choice with a testbench, not
an assumption (CLAUDE.md: "no claim without a testbench"). `spec/prior-art
-survey.md` §5 argues the classic reason to bootstrap — a mid-range dead
zone when `V_DD < V_thn + |V_thp|` — is largely absent at gf180mcu's 3.3 V,
and that the acquisition window is enormous (>25τ even at a derated R_on).
That argument says settling is not the risk; it does not by itself say a
plain T-gate meets the ratified `SFDR ≥ 62 dB` (stretch `≥ 65 dB`) floor
(`README.md#target-specification`), which is a **track-mode distortion**
question (R_on(V_in) modulating the RC tracking lag of a moving input), not
a settling question. This record answers that question with a measurement.

### The dead zone is genuinely absent (confirms the survey, now with real device data)

`sim/device-characterization-report.md` §3.2 measures, at the switch's own
`L = 0.28 µm` channel length: NMOS `V_th` nominal 0.574 V (worst-case, slow/
cold, `ss_-40c_2.97v`: 0.750 V), PMOS `|V_th|` nominal 0.747 V (worst-case
0.951 V). Even at the worst-case corner and the lowest supply in the grid,
`V_thn + |V_thp| ≈ 1.70 V` (worst-case sum) `< 2.97 V` (lowest supply) — no
input code exists where both devices are simultaneously off. A plain
transmission gate spans the full input range at every PVT corner in the
grid; §2.1 confirms this directly (neither the lone NMOS nor the lone PMOS
spans the rail, but the parallel combination does, at every one of the 45
`mos`-grid points).

### The acquisition margin is enormous, confirmed with the design's actual (not placeholder) numbers

`DR-0001` derived its ≤ 500 Ω source-impedance budget against a *placeholder*
34 pF array capacitance (pending #8). #8 has since closed with the actual
value: `C_side = 8.827 pF` per side (`spec/cdac-sizing-memo.md` §5.2,
[DR-0006](DR-0006-cdac-switching-scheme.md)) — 3.85× smaller than the
placeholder, so every acquisition-margin number below is more conservative
than it needs to be by that same factor if anything.

```
tau_worst  = (R_source,max + R_on,worst) * C_side
           = (500 Ω + 570.4 Ω) * 8.827 pF        [R_on,worst @ ss_125c_2.97v, devchar §2.1]
           ≈ 9.45 ns

n_tau      = t_track / tau_worst = 300 ns / 9.45 ns ≈ 31.7 tau
```

31.7τ of settling margin gives a residual error of `e^-31.7 ≈ 1.7e-14` —
astronomically inside any accuracy target. This holds for the **nominal**
10 µm/20 µm T-gate geometry (the worst-case, smallest-device number); the
4× upsized geometry this record chooses has proportionally lower R_on, so
its margin is larger still. Settling is confirmed, not assumed, to be a
non-issue at this rate — consistent with the survey's prediction — and this
is why the decision below turns entirely on the distortion measurement, not
on settling.

### The distortion measurement is the one that actually decides this

`sim/track-switch-thd/` (full 117-point PVT grid: 13 process corners × 3
temperatures × 3 supplies, `sim/track-switch-thd/records/20260801-020125
-267871b.md`) measures track-mode SFDR at `f_in` = Nyquist (500 kHz) for a
500 Ω source (DR-0001) into the real 8.827 pF per-side array capacitance
(DR-0006), for the nominal T-gate geometry, a 4× upsized T-gate, and an
*ideal* bootstrap (gate held exactly `V_in + V_DD`, no boost-network
non-idealities), single-ended and differential, against an ideal-resistor
null control (floor ≥ 213 dB — confirms the measurement itself is not the
limit):

| Topology | Worst-case single-ended SFDR | Worst corner | Worst-case differential SFDR | Worst corner |
|---|---|---|---|---|
| T-gate 10 µm/20 µm (nominal — `sim/device-switch-ron`'s own geometry, and the placeholder inline in `design/cdac/cdac_array.sch`) | **53.76 dB** | `ss_27c_2.97v` | 54.53 dB | `ss_125c_2.97v` |
| **T-gate 40 µm/80 µm (4× upsized — this record's choice)** | **64.81 dB** | `ss_27c_2.97v` | **66.04 dB** | `ss_125c_2.97v` |
| Ideal bootstrap (`V_gs` held exactly at `V_DD`) | 76.39 dB | `ss_125c_2.97v` | 94.54 dB | `ss_125c_2.97v` |

Against the ratified floor (`≥ 62 dB`, stretch `≥ 65 dB`):

- The **nominal 10 µm/20 µm T-gate — the geometry currently placeholder-
  wired into `design/cdac/cdac_array.sch` — fails the spec floor by ~8 dB**
  at its worst corner, single-ended. This is a real, measured shortfall,
  not a marginal pass: the curator guidance's escalation path ("escalate
  only if measurements show THD actually limiting ENOB") is triggered by
  data, not by assumption.
- **Upsizing the T-gate 4× clears the floor** with margin (64.81 dB single-
  ended, +2.8 dB; 66.04 dB differential, +4.0 dB) and clears the **65 dB
  stretch target in differential mode** (66.04 dB), though it falls 0.19 dB
  short of the stretch target in single-ended mode (64.81 dB) at the worst
  corner — the baseline target is the binding requirement
  (`README.md#target-specification`), the stretch is aspirational.
- An ideal bootstrap clears both targets by a wide margin in both modes,
  but — see Alternatives considered — a *real* (non-ideal) bootstrap at
  this supply carries a device-reliability cost the upsized T-gate does
  not, and is not needed once the upsized T-gate already meets spec.

The worst SFDR corner measured (`ss_27c_2.97v` single-ended, `ss_125c_2.97v`
differential) differs from the corner `README.md#target-specification`'s
SFDR row currently cites as binding (`ss_-40c_2.97v`, derived from §2.1's
R_on-*flatness* worst corner). This is not a spec relaxation — the ratified
target value is unchanged — but a refinement worth flagging: R_on flatness
(the ratio driving that citation) and worst-case track-mode SFDR (the
quantity the spec target actually governs) are measured here to peak at
different corners, because SFDR also depends on the *absolute* R_on and its
interaction with `dv/dt` at Nyquist, not flatness alone. A follow-up spec
note correcting the binding-corner citation is worth filing separately;
not done here to keep this record to one decision.

### Downstream spec consumers of this switch's contribution

This switch's track-mode distortion is one contributor (not the only one —
#13 owns the whole-converter number) to two ratified target rows:
**`SFDR ≥ 62 dB` (stretch `≥ 65 dB`)**, substantiated directly above, and
**`CMRR ≥ 60 dB, differential mode` (stretch `≥ 65 dB`)**. The switch
contributes to CMRR only through a *mismatch* between its two per-side
instances (an ideally-matched pair, as simulated in `sim/track-switch-thd`,
rejects a common-mode disturbance perfectly by construction — the
`hd2_*d_db` columns read the simulator's numerical floor, not a real
number). A real CMRR figure is therefore a Monte Carlo mismatch claim, not
a corner-matrix claim, and belongs to **#14**, not to this record; this
record's role is to hand #14 a fixed switch geometry (4× T-gate,
Context above) to run mismatch against, which it now has. Also feeding the
`ENOB > 9.0` line already named in the original issue: the SFDR margin
measured above is one of the three roughly-equal-power non-quantization
error shares `README.md` note **[a]** derives the SFDR target from.

### Charge injection / gain error — measured, real, and a separate open problem

`sim/track-switch-sampling` (full 117-point PVT grid,
`sim/track-switch-sampling/records/20260801-023754-267871b.md`) measures the
turn-off charge-injection pedestal onto the real 8.827 pF array load across
the ratiometric input range, for the nominal T-gate, the 4× T-gate, and this
record's chosen 4× T-gate + dummy compensation. Its *input-dependent* part
(pedestal at full scale minus pedestal at zero) is exactly the switch's own
contribution to the `Gain error ≤ 0.5 LSB, untrimmed` spec row — and the
result is **not a pass** for any configuration measured:

| Topology | Gain-error contribution (LSB), full PVT grid |
|---|---|
| T-gate 10 µm/20 µm (nominal) | 2.04 – 2.92 |
| T-gate 40 µm/80 µm (4×, no compensation) | 9.11 – 12.84 |
| **T-gate 40 µm/80 µm + dummy compensation (this record's choice)** | **3.57 – 5.38** |

Upsizing alone (tg4) roughly **quadruples** the raw gain-error contribution
relative to the nominal geometry — larger devices inject more absolute
channel charge, and that charge is still input-dependent because each
half's `V_gs` (and therefore its channel charge) depends on the sampled
input. Dummy compensation claws back roughly half of that increase (tg4 to
tg4dum), but the compensated result (3.57–5.38 LSB) is still **worse than
the uncompensated *nominal*-size switch** (2.04–2.92 LSB) and **7–11×
over the 0.5 LSB target** at every PVT point measured — this compensation
scheme removes *some* channel charge but the geometry this record chose for
SFDR reasons injects enough more of it that compensation does not recover
the nominal switch's smaller starting point, let alone reach spec.
Nonlinearity (`nl_tg4dum_lsb`) is a smaller but still real 0.43–0.69 LSB,
inside the `< 1 LSB` INL/DNL target but consuming a large fraction of it
before any CDAC/comparator mismatch contribution is added. Hold droop
(`droop_tg4dum_*_uv`), by contrast, closes easily — worst case 88 µV
(`ff_125c_3.63v`) is 0.027 LSB, consistent with the off-state leakage
lower bound below. The worst-case acquisition-step error
(`acqerr_tg1_lsb`) reads exactly 0 at every corner — the simulator's own
confirmation of the >30τ analytical margin above, at the limit of this
measurement's resolution.

**This finding does not change the Decision above.** The T-gate-vs-bootstrap
choice turns on SFDR (closed, with margin, by the 4× geometry) and on the
bootstrap's categorical device-reliability blocker (independent of any
switch's charge-injection number) — neither depends on this gain-error
result. But it is real, measured, material evidence that **the gain-error
spec row is not yet closed by this switch alone**, at any tested T-gate
size or compensation scheme, and is flagged here rather than silently
absorbed, per CLAUDE.md's "no claim without a testbench": this is exactly
the kind of PVT-corner result that would be easy to miss without sweeping
the grid.

### Off-state leakage at 125 °C

Already characterized by #4, full 45-point `mos` grid:
`sim/device-switch-leakage/records/20260731-195001-5f5288b.md` measures the
transmission-gate's net off-state leakage (`ileak_tg_fa`) at
**1.096 nA worst-case (`ff_125c_3.63v`)** — the fast/hot/high-supply
corner, as expected for subthreshold leakage. That record's own caveat
carries forward unchanged: gf180mcu's 3.3 V FET model cards define no
junction leakage parameters (`JS`/`JSW`/`JSWG`), so this number is
subthreshold channel leakage only, a **lower bound** on real hold droop —
real drain-body junction leakage must be budgeted from foundry data or
literature, not from this PDK. This record does not re-run that
characterization (same devices, same claim); `sim/track-switch-sampling`'s
125 °C hold-droop measurements (`droop_*_uv`, Consequences below) are the
same lower-bound quantity expressed as a voltage on the actual 8.827 pF
array load rather than as a current, and are consistent with it.

## Decision

**CMOS transmission gate, upsized 4× relative to the nominal
characterization geometry (NMOS `W = 40 µm`, PMOS `W = 80 µm`, both
`L = 0.28 µm`), with half-width dummy charge-injection-compensation devices
on the hold node, clocked on the complementary phase — NOT a bootstrapped
switch.** This is the "`tg4dum`" configuration in
`sim/track-switch-sampling/testbench/tb_track_sampling.spice` and is
captured as `design/track-switch/track_switch.sch`. One instance per input
pin (per side, in differential mode; the single driven pin, in single-ended
mode), consistent with DR-0001's per-pin ≤ 500 Ω source-impedance budget.

- **Sizing is set by the SFDR measurement, not by settling** (settling
  closes with >30× margin at either geometry — see Context). The nominal
  10 µm/20 µm geometry measurably fails the SFDR floor; 4× clears it.
- **Charge-injection compensation**: half-width (20 µm/40 µm) dummy NMOS/
  PMOS devices, source and drain shorted onto the hold node, gated by the
  clock phase complementary to the main devices — the textbook channel-
  charge-cancellation construction. This compensates channel charge only,
  not gate-overlap clock feedthrough (both the main and dummy devices
  inject the latter, and this construction does not cancel it) —
  `sim/track-switch-sampling` measures both effects.
- **Not bottom-plate sampling.** [DR-0006](DR-0006-cdac-switching-scheme.md)
  ratifies **top-plate** sampling for the MCS/Vcm array (it is what gives
  the array its MSB for free), so the delayed-turn-off ground-switch
  charge-injection remedy `spec/prior-art-survey.md` §5.3 lists as the
  primary compensation scheme is **not available** to this design —
  already-ratified and out of this record's scope to revisit. Compensation
  therefore has to come from the switch itself (the dummy pair above),
  which is a deviation from the curator guidance's literal "bottom-plate
  sampling" phrasing, forced by DR-0006, not overlooked.
- **Applies identically to single-ended and differential input modes** —
  same switch, same per-pin budget; what differs between modes is only how
  many sides the CDAC array switches per bit trial (DR-0006), which this
  record does not touch.

## Alternatives considered

- **Nominal 10 µm/20 µm T-gate** (the geometry `sim/device-switch-ron`
  already characterized, and the geometry currently wired as a placeholder
  inline in `design/cdac/cdac_array.sch`) — not chosen: measured 53.76 dB
  worst-case single-ended SFDR, ~8 dB short of the `≥ 62 dB` floor
  (Context, above). Rejected on measured data, not on a size assumption.
- **Bootstrapped switch** — not chosen, for two independent reasons:
  1. **Not needed.** The 4× upsized T-gate already clears the SFDR floor
     with margin (Context, above); an ideal bootstrap clears it by more,
     but that headroom is not required once the floor is met, and every
     dB beyond the target buys nothing against a spec that stops at 62/65
     dB.
  2. **A real (non-ideal) bootstrap has a device-reliability cost this
     design does not need to pay.** The classic bootstrap topology
     (Abo & Gray-style; the sky130 10-bit reference `spec/prior-art
     -survey.md` §5.1 cites is a portable *schematic pattern* for this
     class, not a portable *decision*) holds `V_gs = V_DD` on the sampling
     device by driving its gate to `V_in + V_DD`. At this design's
     ratiometric full scale (`V_REF = V_DD`, worst case `V_DD = 3.63 V`),
     that boosted node reaches **up to 6.6 V** — roughly **2× the 3.3 V
     device flavor's own supply rating** ([DR-0004](DR-0004-device-flavor.md)
     fixes the analog signal path to `nfet_03v3`/`pfet_03v3`), on a node
     that is gate, drain, or source to multiple devices in the boost
     network. This is a categorical overstress by construction (a "3.3 V"
     device flavor is not rated for a 6.6 V terminal-to-terminal swing),
     not a marginal design risk to be verified away. Making a real
     bootstrap safe at this supply would require either the `nfet_05v0`/
     `pfet_05v0` flavor for the boost network (available in this PDK per
     DR-0004's device survey, but adding a second device flavor and its
     own characterization burden to a block that is otherwise
     single-flavor by DR-0004), active clamping of the boosted node, or a
     different bootstrap topology altogether (e.g. one that caps the boost
     at `V_DD` above a mid-rail node rather than above ground) — real
     design cost, not assumed away, and not spent here because it is not
     needed. `sim/track-switch-thd`'s ideal-bootstrap branch (`V_gs` held
     exactly at `V_DD` by a behavioral source, no boost-network devices of
     its own) is deliberately the best case a real implementation could
     only approach, so the 76–95 dB it measures is an upper bound on what
     bootstrapping could buy here, not a claim about a real circuit's
     terminal-voltage safety — a real bootstrap's own terminal-voltage
     stress is not separately re-derived in this record, since the
     decision does not turn on it once reason 1 already settles the
     question.
- **Even larger T-gate (> 4×)** — not chosen: the 4× point already clears
  the baseline floor with margin and the differential-mode stretch target;
  the single-ended stretch target is missed by only 0.19 dB at the worst
  corner, and closing that residual gap is not free. `sim/track-switch
  -sampling` prices exactly this trade: going from nominal to 4× already
  roughly quadruples the switch's charge-injection-driven gain-error
  contribution (Context, above), so a still-larger device would make the
  already-open gain-error problem worse in exchange for a sub-1-dB,
  aspirational-only SFDR gain. Revisit only if a future issue shows the
  single-ended stretch target is load-bearing (it is currently aspirational,
  not a spec floor).

## Consequences

- `design/track-switch/track_switch.sch` captures this topology (4×
  T-gate + dummy compensation) and is the schematic future layout work
  (#16) and the SAR/timing integration work (#11, #12) should reference.
  **It does not yet replace** the placeholder 10 µm/20 µm T-gate wired
  inline into `design/cdac/cdac_array.sch`'s `samppN`/`samppP`/`sampnN`/
  `sampnP` instances — updating that placeholder to reference this block
  is real work belonging to whichever issue next touches the CDAC
  schematic (#8's follow-on, or #16), out of this issue's scope to do
  silently as a side effect.
- **`sim/track-switch-sampling`'s bootstrap branches (bs10/bs20) are
  disabled, and this is a deliberate scope cut, not a silent shortfall.**
  The originally-authored testbench instantiated all five configurations
  (nominal T-gate, 4× T-gate, 4× T-gate + dummy compensation, and two
  bootstrap sizes) in one 27-branch deck. Under this session's host
  contention (~20–30 concurrent, unrelated ngspice jobs from other
  repositories' worktrees observed at run time), a single PVT point of
  that full deck did not complete within a 300–1800 s timeout across
  several attempts. Isolating the cost (a standalone timed run of the
  non-bootstrap branches alone: ~7.5 CPU-seconds; the full deck: still
  incomplete after >100 CPU-seconds) showed the "`boot`" subckt's internal
  positive-feedback turn-on loop (M3/M5/M6) — not PVT-grid size — was the
  bottleneck, costing an order of magnitude more than the other 20+
  branches combined. Since the bootstrap alternative is already rejected
  on grounds independent of this testbench (SFDR margin already measured
  in `sim/track-switch-thd`; the categorical 6.6 V device-reliability
  argument above), the bs10/bs20 branches were disabled (commented out;
  the `boot` subckt definition is retained for a future re-enable) rather
  than accepted as a permanent blocker on getting **any** real number for
  the topology this record actually chooses. With them disabled, the
  **full 117-point PVT grid completed**
  (`sim/track-switch-sampling/records/20260801-023754-267871b.md`) — see
  the gain-error subsection above for what it found. Re-enabling the
  bootstrap branches for a dedicated terminal-voltage-stress
  characterization remains a legitimate follow-up if the bootstrap
  alternative is ever revisited, but is not needed to substantiate
  anything this record's Decision depends on.
- **#11 (SAR logic)** drives this switch's `clk`/`clkb` pins; the dummy
  compensation pair needs the same two phases already required by the main
  devices, no new control signal.
- **#12 (timing budget)** can treat this switch's `R_on` as roughly 1/4 of
  the `sim/device-switch-ron` nominal-geometry numbers (R_on scales ~1/W);
  the acquisition-margin arithmetic above already uses the more
  conservative *nominal*-geometry `R_on` and still clears with enormous
  margin, so no tightening of #12's budget is required by this record.
- **#16 (floorplan/matching)** inherits a switch 4× the area of the
  nominal characterization geometry (plus the dummy pair, another ~50 % on
  top of the main devices) — a real area cost against the < 0.1 mm² target,
  not zero, though small in absolute terms (tens of µm² per switch) next to
  the CDAC array itself.
- **Datasheet-facing consequence**: the SFDR floor is met with margin in
  differential mode at both target and stretch levels, and in single-ended
  mode at the target level only (stretch missed by 0.19 dB worst-case) —
  a real, stated limitation for a catalog part offering both input modes,
  not a free simplification.
- **The gain-error finding above (3.57–5.38 LSB switch contribution vs. a
  0.5 LSB target) is an open problem this record surfaces but does not
  close.** It does not change this record's Decision (Context, above), but
  it is a real, newly-measured risk to the `Gain error ≤ 0.5 LSB` spec row.
  Filed as **#39** rather than expanded into this record's scope, which is
  the T-gate-vs-bootstrap topology choice, not the charge-injection
  compensation scheme's own tuning — candidate mitigations (a larger
  dummy-to-main width ratio than the textbook 1:2 used above, an
  alternative compensation topology, or a system-level gain-trim step the
  ratified spec's "untrimmed" framing does not currently budget for) are
  listed there, not evaluated here.

## Spec lines affected

- `README.md#target-specification` — none changed. This record substantiates
  the existing `SFDR ≥ 62 dB` (stretch `≥ 65 dB`) row for the specific
  mechanism this switch contributes and closes the open topology question,
  but does not change any ratified value.
- `README.md#target-specification` — SFDR row's cited binding corner
  (`ss_-40c_2.97v`) — **flagged, not changed by this record.** The worst
  corner actually measured for track-mode SFDR (`ss_27c_2.97v` single-
  ended, `ss_125c_2.97v` differential) differs from the corner currently
  cited, which was derived from R_on *flatness* rather than from a direct
  SFDR sweep (see Context). Correcting the citation is left to a follow-up
  record so this one stays to a single decision.
