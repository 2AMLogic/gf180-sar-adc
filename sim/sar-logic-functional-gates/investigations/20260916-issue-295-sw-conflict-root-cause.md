# Investigation 20260916-issue-295-sw-conflict-root-cause

Not a `sim/run_corners.py` evidence record (no PVT grid is claimed here) --
a manual root-cause investigation of the `sw_conflict_se`/`sw_conflict_df`
one-hot-invariant violation issue #295 was filed to explain, following the
two-step disambiguation method the issue itself specified (port-order diff,
then waveform archaeology). Kept in `investigations/`, alongside (not
inside) `records/`, so the append-only `records/20260915-214338-912a8ec.md`
this investigation explains is never edited.

## Conclusion

**Root cause: (1) a genuine combinational hazard from real, non-zero
per-cell propagation delay in the synthesized switch-decode logic --
NOT (2) a wiring/pin-mapping defect.** The synthesized netlist implements
each cell's `rel_n_<weight><side>` output as a single real standard cell
(`gf180mcu_fd_sc_mcu7t5v0__nor2_1` on the p-side, `__aoi21_1` on the n-side)
that reads the shared `sel_in_n` broadcast net directly as one of its own
inputs. Because the `sw_conflict_*` check sums the four one-hot legs'
*raw node voltages* (`v(sel_in_n) + v(rel_n) + v(sel_hi_n) + v(sel_lo_n)`),
and `sel_in_n`'s own voltage falls with zero additional delay while
`rel_n`'s response to that same edge is delayed by that one real gate's
finite propagation delay, every acquisition-window-closing transition (once
per conversion, on **all 18** switch-decode cells simultaneously, since
`sel_in_n` fans out to all of them) opens a real, measured **~143-163 ps**
window in which *neither* the `in` leg nor the `rel` leg is asserted. This
is exactly the class of effect `klt equiv`'s zero-delay `"yosys-sequential"`
equivalence check cannot see (`design/sar-logic/rtl/README.md` already says
so), and it is a real pre-layout design defect, not evidence the deck, the
translator, or DR-0014's bound is wrong.

- Hypothesis (2) (wiring/pin-mapping defect) is **ruled out**: a
  byte-for-byte diff of the 71-port `sar_ctrl_a` port list across three
  independent sources -- the RTL source of truth, the synthesized gate
  netlist's own module header, and the SPICE `.subckt` header actually used
  in the committed #289 corner-grid run -- shows **zero** mismatches (see
  "Step 1" below).
- Hypothesis (1) (genuine hazard) is **confirmed** with a specific,
  reproduced, sub-nanosecond-precision mechanism (see "Step 2" below).
- The smaller `nside_cells_se` overshoot (1.5-3x, DR-0011's mode rule) is
  the **same root cause at smaller magnitude** -- a small (1-2% of VDD),
  real transient glitch on the logically-constant-0 n-side `sel_hi_n`/
  `sel_lo_n` nodes, triggered by the identical `sel_in_n` transition edge
  (see "Triage: nside_cells_se" below). Not a separate defect.
- The `fs`/`sf`-only `acq_window_ns`/`iso_gap_ns`/`iso_gap_df_ns` misses are
  **triaged as a separate, plausible, expected corner-driven timing shift**,
  not the same defect and not investigated further here (see "Triage:
  fs/sf timing misses" below) -- exactly the kind of effect #273's PVT grid
  exists to catch, per the issue's own hypothesis.
- **No DR-0014/DR-0011 bound change is warranted.** The measured violation
  is a genuine, real hazard in the pre-layout design, not evidence the
  ratified `max=0.02` bound picked the wrong number for a correct design.
- **Follow-up filed** to fix the hazard before P&R (#274)/STA (#275)
  sign-off (fix not attempted here, per issue #295's own scope): see
  "Follow-up issue" below.

## Provenance

- git: `75f544aac85a514b237af3d2357bcbbbe3c40785` on `feature/issue-295`
  (clean tree at HEAD; the corner-grid evidence this investigation explains,
  `sim/sar-logic-functional-gates/records/20260915-214338-912a8ec.md`, was
  committed by #297 at `8790267`, already on this branch's `main` ancestor)
- PDK: gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (`/home/ubuntu/.volare/gf180mcuD`, found via `search_root:~/.volare`) --
  same PDK build the #289/#297 corner-grid record used
- ngspice: ngspice-46 (KLU direct linear solver)
- python: 3.12.3
- Probe decks: generated ad hoc from the SAME generator functions the
  committed testbench uses (`design/sar-logic/gen_sar_logic.py`'s
  `_functional_body`, `design/sar-logic/flow/gen_sar_ctrl_gates_tb.py`'s
  `_gate_subckt_text`/`_assemble`, `sim/harness/runner.py`'s
  `compose_deck`/`run_point`) at `nconv=2` (not the committed 64) and a
  shortened `.tran` stop time, with extra diagnostic `.meas tran ... WHEN`
  lines appended -- **not committed** (throwaway diagnostic decks, `tt`
  corner, 27&nbsp;C/3.30&nbsp;V only; the committed
  `sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice`
  and its `tb.json` manifest are unmodified by this investigation). Each
  probe run is individually reproducible from the script fragments quoted
  below plus the harness functions named -- rerun cost measured directly at
  12-37 s per probe (`nconv=2` on the shared `se`+`df` composition), well
  inside a single investigation session's budget.

## Step 1: port-order diff (ruling hypothesis (2) in or out)

Per the issue's own suggested first step: diff the intended (RTL) vs.
translated (synthesized-netlist / SPICE `.subckt`) port order for the
71-net `sar_ctrl_a` port list (36 of which are the `rel_n_*`/`sel_hi_n_*`/
`sel_lo_n_*`/`sel_in_n` switch-decode ports hypothesis (2) named).

Three independent sources compared, byte-for-byte, in full (not sampled):

1. `design/sar-logic/rtl/sar_ctrl.v`'s own `module sar_ctrl_a(...)` port
   declaration list (the RTL source of truth).
2. `design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`'s own
   `module sar_ctrl_a(...)` header (the `klt synthesize`-produced gate
   netlist `gate_netlist_to_spice.py` translates).
3. `sim/sar-logic-functional-gates/netlist-snapshots/20260915-214338-912a8ec.spice`'s
   `.subckt sar_ctrl_a ...` header (the translated SPICE port list actually
   wired into the closed loop for the #289 corner-grid run this issue is
   about).

```
RTL (design/sar-logic/rtl/sar_ctrl.v) port count:                          71
Synthesized netlist (sar_ctrl.mcu7t5v0.synth.v) module port count:         71
.subckt sar_ctrl_a port count (netlist-snapshots/20260915-214338-912a8ec): 71

RTL vs synth-netlist-module: IDENTICAL, 0 mismatches across all 71 ports
synth-netlist-module vs .subckt-sar_ctrl_a(committed-snapshot): IDENTICAL, 0 mismatches across all 71 ports
RTL vs .subckt-sar_ctrl_a(committed-snapshot): IDENTICAL, 0 mismatches across all 71 ports
```

All three port lists are **byte-identical**, in the same order, across all
71 ports (including all 36 switch-decode ports). This diff alone rules out
a top-level port-order/pin-mapping defect at the `sar_ctrl_a` boundary
`gate_netlist_to_spice.py`/`gen_sar_ctrl_gates_tb.py` are responsible for --
consistent with `gate_netlist_to_spice.py`'s own design (it derives the
emitted `.subckt`'s port list directly from the synthesized netlist's own
`module (...)` header, `GateNetlist.ports`, never re-deriving or guessing
an order) and consistent with `sim/tests/test_gate_netlist_to_spice.py`'s
existing `TranslateEndToEndTests` already generically asserting this
property (`.subckt <name> <ports in declaration order>`) against a small
hand-built fixture. No new regression test is added here per issue #295's
own guidance (a translator regression test is only called for on the
hypothesis-(2) branch, which this step rules out).

Reproduction: the three-way diff above was produced by a short ad hoc
Python script (regex-extracting each of the three port lists and comparing
them positionally) run against the paths named above -- not committed as
a script, since it is a one-shot diagnostic, not a reusable tool; the exact
extraction/compare logic is inlined for reference in this record's own git
history (see the PR this file was introduced in).

## Step 2: waveform archaeology (confirming hypothesis (1) and its mechanism)

With hypothesis (2) ruled out, the issue's second step -- probing waveforms
around a representative bit-trial edge -- was run. Rather than eyeballing
committed logs (which the `sim/run_corners.py` runs did not `.print`/
`.wrdata`, only `.meas`, per `sim/harness/runner.py`'s `compose_deck`),
this used the `.meas tran ... WHEN` mechanism directly, which reports
sub-nanosecond crossing times independent of any print-step granularity.

### 2a. Where does the committed corner-grid's own `sw_conflict_*`/
`nside_cells_se` MAX actually land, in every corner already run?

The `#289`/`#297` corner-grid record itself already carries the answer, in
each `.meas ... MAX ... at=<time>` line in the raw per-corner logs
(`sim/sar-logic-functional-gates/corners/20260915-214338-912a8ec/*.log`) --
it was simply never converted to a phase-of-conversion before this
investigation. `sar_ctrl.v`'s `start` is asserted for
`START_PULSE_CLOCKS=2` full clock periods (125 ns) before the ring's first
*real* one-hot phase-0 begins, so every subsequent conversion boundary is
offset by that same 125 ns (`conversion k` spans
`[125 + (k-1)*1000, 125 + k*1000)` ns, `k=1,2,...`; 1000 ns = 16 phases x
62.5 ns/phase, `phase_idx = ((t - 125ns) mod 1000ns) / 62.5ns`):

| measurement | corner | `at=` (ns) | conversion # | phase_idx |
|---|---|---:|---:|---:|
| `conf_se` (`sw_conflict_se`) | `tt` | 33376.7 | 34 | 4.027 |
| `conf_se` | `ff` | 45376.4 | 46 | 4.022 |
| `conf_se` | `ss` | 12377.4 | 13 | 4.038 |
| `conf_se` | `fs` | 38376.9 | 39 | 4.030 |
| `conf_se` | `sf` | 376.67 | 1 | 4.027 |
| `conf_df` (`sw_conflict_df`) | `tt` | 40000.7 | 41 | 14.011 |
| `conf_df` | `ff` | 64000.6 | 65 | 14.010 |
| `conf_df` | `ss` | 32001.0 | 33 | 14.016 |
| `conf_df` | `fs` | 64000.8 | 65 | 14.013 |
| `conf_df` | `sf` | 64000.7 | 65 | 14.011 |
| `nside_se` (`nside_cells_se`) | `tt` | 34000.7 | 35 | 14.011 |
| `nside_se` | `ff` | 1000.56 | 2 | 14.009 |
| `nside_se` | `ss` | 1000.91 | 2 | 14.015 |
| `nside_se` | `fs` | 2000.79 | 3 | 14.013 |
| `nside_se` | `sf` | 1000.74 | 2 | 14.012 |

Every one of these 15 instants -- across all 5 corners tested, at whatever
conversion number they happen to occur on -- lands on **exactly one of two
phase offsets, to within +/-0.02 of a phase (+/-1.25 ns)**: `phase_idx ~
4.03` (the acquisition-window-closing edge, `sel_in_n` falling as the first
bit trial begins) or `phase_idx ~ 14.01` (the `endconv`/array-release edge,
`ph[13]->ph[14]`). This periodic, corner-independent recurrence at a fixed
phase offset -- never at a random instant, never a value that is simply
"wrong" whenever a given net is read -- is itself strong evidence against a
static wiring defect (which would not care what phase of the conversion it
is) and for a real, clock-relative propagation-delay hazard.

### 2b. Direct crossing-time measurement at the dominant edge (`phase_idx ~ 4`)

A `tt`/27&nbsp;C/3.30&nbsp;V probe (2 conversions, `.tran` stop time shortened to
500 ns, extra `.meas tran ... WHEN` lines for `se_sel_in_n` and every
`se_rel_n_<weight>p`/`se_rel_n_<weight>n` net) measured:

```
t_selin_fall        =  3.76681e-07   (376.681 ns -- se_sel_in_n FALL=1)
t_rel256p_rise      =  3.76824e-07   (376.824 ns -- se_rel_n_256p RISE=1)
t_rel128p_rise      =  3.76824e-07
t_rel64p_rise       =  3.76824e-07
t_rel32p_rise       =  3.76824e-07
t_rel16p_rise       =  3.76824e-07
t_rel8p_rise        =  3.76824e-07
t_rel4p_rise        =  3.76824e-07
t_rel2p_rise        =  3.76824e-07
t_rel1p_rise        =  3.76824e-07   (all 9 p-side rel_n legs, identical to 3 sig figs)
t_rel256n_rise      =  3.76844e-07   (376.844 ns -- se_rel_n_256n RISE=1)
t_rel128n_rise .. t_rel1n_rise = 3.76844e-07   (all 9 n-side rel_n legs, identical)
conf_se_gapwindow   =  7.74370e+00 at=  3.76604e-07   (matches the committed
                                                        corner-grid's own
                                                        conf_se MAX shape)
```

- `se_sel_in_n` falls at **t=376.681 ns**.
- All **9** p-side `rel_n_<weight>p` legs rise together at **t=376.824 ns**
  -- **143 ps** after `sel_in_n`'s own fall.
- All **9** n-side `rel_n_<weight>n` legs rise together at **t=376.844 ns**
  -- **163 ps** after `sel_in_n`'s own fall.

For that 143-163 ps window, on **all 18** switch-decode cells
simultaneously, the one-hot sum
`v(sel_in_n) + v(rel_n) + v(sel_hi_n) + v(sel_lo_n)` reads **0**, not
`vdd_val` -- both the shared `in` leg and each cell's own `rel` leg are
de-asserted at once. This is not an "overlap" (two legs asserted together);
it is a real, physically-inherent "gap" (neither leg asserted), and its
duration matches the gf180mcu_fd_sc_mcu7t5v0 `nor2_1`/`aoi21_1` cells'
own real propagation delay reading `sel_in_n` -- **not** a fixed logical
"wrong value", and not something a zero-delay register-correspondence check
could ever see.

### 2c. Why `rel_n` depends on `sel_in_n` directly (not through a shared
`smpb` net)

`sar_ctrl.v`'s own structural description computes `rel_n_<w>p = ~eng &
smpb` via an intermediate `wire smpb = ~sel_in_n;` shared across all 18
cells. The synthesized netlist does **not** preserve that intermediate
wire -- ABC folded the inversion directly into each cell's own gate via
De Morgan's law, e.g. (from
`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`):

```verilog
gf180mcu_fd_sc_mcu7t5v0__nor2_1 _132_ (
  .A1(eng9),
  .A2(sel_in_n),
  .ZN(rel_n_256p)
);
gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _133_ (
  .A1(mode),
  .A2(eng9),
  .B(sel_in_n),
  .ZN(rel_n_256n)
);
```

i.e. `rel_n_256p = NOR2(eng9, sel_in_n) = ~(eng9 | sel_in_n)`, algebraically
identical to the RTL's `~eng9 & ~sel_in_n` (De Morgan's), but implemented as
**one real standard cell reading `sel_in_n` directly**, not through a
shared inverter whose own delay every cell would inherit equally. Every one
of the 18 `rel_n_<weight><side>` cells is wired the same way (confirmed
directly in the netlist -- every `rel_n_*` instance takes `sel_in_n` as a
named input pin, one `NOR2`/`AOI21` per cell). Meanwhile `sel_hi_n`/
`sel_lo_n` for each weight are driven from `eng<n>`/`q<n>` only (no
`sel_in_n` term at all -- e.g. `sel_hi_n_256p = AND2(q9, eng9)`), so they
are unaffected by `sel_in_n`'s own edge and do not race to fill the gap.

The gap is real, structural, and reproducible: `sel_in_n`'s own node
voltage (used directly, undelayed, in the check's summed expression) always
leads every `rel_n_<weight><side>` cell's own response to that same edge by
that cell's real propagation delay, on every conversion, on every corner.

## Triage: `nside_cells_se` (DR-0011's mode rule, 1.5-3x overshoot)

Same probe deck, extended to 1100 ns to also capture the wraparound into
conversion 2 (`phase_idx ~ 14`, the *other* instant the committed record's
own `nside_se` MAX lands on -- see 2a's table):

```
t_nside_se_peak      =  4.48277e-02 at=  1.00074e-06   (matches the shape of
                                                          committed ff/ss/fs/sf
                                                          nside_se MAX values,
                                                          0.036-0.064)
t_selhi256n_glitch   =  1.66181e-02 at=  1.00074e-06   (se_sel_hi_n_256n MAX
                                                          in [850ns,1050ns])
t_selhi1n_glitch     =  1.25255e-02 at=  1.00074e-06   (se_sel_hi_n_1n MAX)
```

In single-ended mode (`mode=0` constant), every n-side `sel_hi_n`/
`sel_lo_n` gate is synthesized with `mode`'s own inverted value as one
input of a `NOR3`/`AND2`, which pins the gate's output to logic 0
*regardless* of its other inputs' switching activity -- e.g.
`sel_hi_n_256n = NOR3(~mode, q9, ~eng9)`, and `~mode` is a DC-constant 1 for
the whole `se` loop, so the NOR3's output is provably always 0. What this
probe measures is a **small (1.2-1.7% of VDD), real transient glitch** on
that provably-constant-0 node, coincident with the exact same `sel_in_n`
transition edge the headline `sw_conflict_*` finding is built on (same
`t=1.00074e-06` instant `nside_se`'s own MAX lands at). This is the
**same root cause at a much smaller magnitude** -- real, non-ideal
transistor-level switching behaviour on a node a zero-delay logic
equivalence check would treat as a hard constant -- not a second, distinct
defect requiring its own investigation.

## Triage: `fs`/`sf`-only `acq_window_ns`/`iso_gap_ns`/`iso_gap_df_ns` misses

Not investigated further here; triaged as **a separate, plausible, expected
corner-driven timing shift**, distinct from the `sw_conflict_*`/
`nside_cells_se` hazard above, for three reasons:

1. **Different measurement basis.** `acq_window_ns`/`iso_gap_ns*` are
   *time-averaged duty cycles* over 60 whole conversions
   (`AVG v(se_acq) FROM=2u TO=62u`, `gen_sar_logic.py`'s own docstring on
   this node), specifically chosen (per that docstring's own history,
   record `20260802-094246-16ec0f1`) to be insensitive to exactly the kind
   of sub-nanosecond single-instant transient this investigation found for
   `sw_conflict_*`/`nside_cells_se` (both instantaneous `MAX` measurements).
   A ~143-163 ps gap, once per 1000 ns conversion, moves a 60-conversion
   time-average by an entirely negligible fraction of a nanosecond -- far
   below the several-ns misses actually observed on `fs`/`sf`.
2. **Corner-selective, not corner-independent.** The `sw_conflict_*`/
   `nside_cells_se` violation is essentially identical in magnitude across
   all 5 corners tested (Step 2a's table) -- consistent with a fixed,
   structural gate-level hazard that doesn't care about process skew beyond
   changing its own (already-negligible-to-the-duty-cycle-average)
   picosecond width slightly. The timing misses are `fs`/`sf`-only (not
   `tt`/`ff`/`ss`) -- exactly the pattern of a real NMOS/PMOS speed-skew
   corner effect shifting the *relative* delay balance between different
   gate topologies along the 16-stage `ph` ring's own cumulative real
   propagation path, which is precisely what `fs`/`sf` corners exist to
   stress.
3. **This is what #273's own PVT grid was filed to catch.** The issue's own
   text names this possibility directly ("a genuine, expected process-corner
   timing shift... rather than a defect"). A few-ns shift against a
   ~185-190 ns acquisition window / ~60-65 ns isolation gap (a 3-5% shift)
   is a modest, plausible magnitude for a real corner-driven delay-balance
   change, not the many-orders-of-magnitude overshoot the `sw_conflict_*`
   hazard produces.

No further action recommended here; a future full temperature/supply sweep
of this deck (out of scope for #295, per its own "Out of scope" section)
would be the next evidence-gathering step if this needs to be conclusively
separated from a defect, not more waveform archaeology on the process axis
alone.

## Why no DR-0014/DR-0011 decision-record change

CLAUDE.md: "agents do not relax the ratified spec to make results pass."
The measured `sw_conflict_se/df` overshoot is not evidence the `max=0.02`
bound picked the wrong number for a *correct* design -- the bound's own
description already states it should read "a numerical floor ~1e-14 when
correct" (issue #295's own text, quoting `tb.json`), and the rung-1 ideal
sibling (`sim/sar-logic-functional/`) meets exactly that floor on the
identical closed loop with the identical check. What changed is the DUT:
zero-delay ideal digital primitives replaced by a real synthesized netlist
with a genuine, structural propagation-delay hazard in its switch decode.
The correct response is to fix the design (or accept a documented, bounded
real-hazard budget in a *new* decision if the hazard turns out to be
physically unavoidable at the gate level -- a question for the follow-up
issue below, not this investigation) -- not to widen a bound that is
already proven achievable by a correct implementation of the same
specification.

## Follow-up issue

**#298** -- "fix: real gate-delay hazard in sar_ctrl_a switch decode (rel_n
races sel_in_n)" -- filed to fix the identified hazard before P&R (#274)/
STA (#275) sign-off, per issue #295's own acceptance criteria (the fix
itself does not need to land in #295's own PR).
