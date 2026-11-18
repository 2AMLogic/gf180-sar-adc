# Investigation 20261118-issue-910-above-rail-ringing

Not a `sim/run_corners.py` evidence record — a manual root-cause
investigation of the above-rail ringing family filed as issue #910:
gf180mcu standard-cell outputs exceeding the 3.300 V rail at slow-NMOS
cold corners, on (a) the `sel_hi_n` select legs that `nside_cells_df`
sums raw (the `ss_-40c` FAIL, #844 §4b) and (b) the comparator output
`cmpo` whose above-rail excursion #854's unmerged note first reported at
a `sf_-40c` restart. Characterisation only: no committed testbench,
netlist, RTL or bound is changed by this investigation. The one
confirmation re-run this issue mints through the instrument is
`records/20261118-040726-44bd78d.md` (batch fleet, `ss_-40c`/`sf_-40c`),
cited
in §1.

## Conclusion

**Two physically distinct excitation mechanisms, neither of them a
behavioural-source artifact, neither of them a physical out-of-rail
drive, and neither of them the cause of the one wrong conversion the
legal-trajectory run contains.**

1. **The `sel_hi_n` legs — real gate-drain capacitive coupling,
   amplified ~4× by the deck's parasitic-less witness load.** The
   overshooting nodes are the *rising* `sel_hi_n_<w>n` driver outputs
   (nor3 cells in df mode; worst `hi_4n` at 3.5438 V vs the 3.300 V
   rail). The energy source is displacement current through the driver's
   own gate-drain overlap capacitance as its input edge switches — onto
   an output node whose *only* load in this deck is the B-source
   expressions of `bdftopn`/`bdfnside`, which present infinite impedance.
   Hanging the real extracted CDAC T-gate (the load these legs drive in
   the actual bit cells) on every control leg shrinks the worst leg
   3.5438 → 3.3752 V and the whole-run `nside_cells_df` maximum
   9.16096 → **9.06642, back inside the ratified 8.9–9.1 bound** (§5).
   The excursion survives `trtol=1` and `method=gear` (§2), so it is not
   trapezoidal-integration ringing. Into the real load a ~75 mV
   above-rail residual remains — the same mild family the ratified bound
   already admits at nominal (`tt_27c` steady-state 9.04957, #844 §4b's
   own numbers).
2. **`cmpo` — a real coupled excitation through the comparator path's
   own capacitances, whose rendered peak amplitude is dominated by
   solver integration behaviour.** `cmpo`'s driver `bdfcmp` is
   algebraically bounded and was measured *exactly at its rail
   (3.3000/0.0000) at every excursion instant* across the full 64.5 µs
   ss run (§3) — the B-source never drives the node out of bounds, so
   this is not a behavioural-source artifact. The excitation is the
   acquisition→trial transition of each conversion (all 18 DAC legs plus
   the ten trial-latch AOI cells reconfigure simultaneously; `nside` ≈
   8.0 at every excursion instant), coupling through the load `cmpo`
   legitimately drives. The excursion is annihilated by +1 pF of
   explicit load (3.6389 → 3.3016 V), survives 10 kΩ port isolation
   (3.5927 — it comes from the DUT side, not the B-source side), and its
   rendered amplitude moves strongly with solver options (`trtol=1`
   3.3024, `method=gear` 3.3500, default 3.6389) — so the *default-option
   peak value* (3.6–3.66 V) is not a quantitatively trustworthy physical
   number. What is robust: the excursions are sub-ns, symmetric (up to
   +0.36 V, down to −0.55 V), have no DC path, and — decisive for this
   issue — **never coincide with a capture instant** (§4).
3. **The corruption question is answered NO, with the real cause of the
   wrong word identified and it is not analog.** On the legal
   trajectory (the `ss_-40c` full run: 64 conversions, ring one-hot
   throughout, cadence nominal), every trial-latch capture edge sampled
   a fully settled `cmpo` at rail value (±1 mV); the excursions live in
   the 6–10 ns dead zone *after* each edge, 62.5 ns before the next
   capture. Conversion 3's wrong word (52 against expected 37, +15
   exactly, the run's only steady-state error) is a **hold race at two
   trial flops**: `q4` (8-weight trial, edge 2.7500 µs) and `q2`
   (2-weight trial, edge 2.8750 µs) held their previous-conversion
   rejects even though their D inputs had held logic-0 for the full
   ~60 ns of each trial (clean −0.001 V for the last ~10 ns before the
   edge) — the phase-ring flop's clk→Q fall re-gated the AOI ~0.28 ns
   after the edge, and its hold-path value beat the master latch's close
   at this corner. `q0`'s identical clear at 3.0000 µs succeeded because
   its ring phase fell ~0.5–1.0 ns later. That race is a netlist/RTL
   timing defect in the #854 family, not an analog overshoot effect, and
   this issue changes none of it (§4).
4. **`nside_cells_df`'s deck instrument still reads 9.16096 > 9.1 and
   the point stays a recorded FAIL** — the deck is unchanged, the bound
   is unchanged. The benign demonstration (§5) shows the *same mechanism*
   measured into the real T-gate load lands inside the bound; what that
   means for the bound's scope is filed as
   `spec/decision-records/DR-0048-...md` (derivation-backed, **proposed**
   status — this issue does not move the bound and does not re-score the
   point).

## Provenance

- git: worktree `feature/issue-910` on `44bd78dd9e08402ef9754c04f30e29c52af1533a`
  (the `main` head this branch tracks — the pre-#854 netlist; #854 is
  open and unmerged, so every number below is re-taken, not cited).
- Testbench: `sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice`
  sha256 `f73d12206c2a5816ac1fb8f11b5182bb97ee14e798fbfc7b89b2309ccda9a47a`
  (unchanged by this branch).
- PDK: gf180mcuD @ open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
  (`sim/toolchain.json` pin, enforced by the harness).
- ngspice: ngspice-47 (single-corner local probes, KLU solver, default
  integration options except where an §2/§3 experiment states
  otherwise); python 3.12.3; klt 0.9.3.dev1136+g81926eccba7b.
- Probe decks: composed by `design/sar-logic/flow/probe_code_readout.py`
  (the issue #320 readout instrument with the generic `--nodes` option,
  #844's extension); every run kept deck + raw log under
  `/tmp/910-probe/<name>/` (regenerable from the commands in §7).
  The A/B decks are the composed probe decks with probe-only edits
  (stated verbatim in §2/§3/§5); nothing under `sim/` was written by any
  probe run. **E1 no longer leans on that `/tmp` provenance (issue
  #913)**: its 27-instance construction is committed as the probe's
  `--tgate-load <para.spice>` flag (invocations in §7 item 4; wiring
  pinned by `sim/tests/test_probe_code_readout.py`'s `TgateLoadTests`),
  so the E1 deck is byte-reproducible from the committed tree like
  every other probe here — re-verified on `main` after #912 merged
  (2026-11-18, ngspice-47p1): all three headline E1 numbers reproduce
  to 5 significant figures, with one recorded deviation on the §5
  conversion-error row (§5). Cell-internal node vectors (e.g. the trial
  flops' master
  nodes, `xdf.x204_.net4`) are **not addressable** from an ngspice
  control block in this flow — refused under the control-block `save`
  command, under `save all`, and under a netlist-level `.save` card
  (all three verified on ngspice-47) — so the §4 flop analysis reads the
  top-level D nets (`_025_`, `_017_`), the flops' Q (`q4`, `q2`), the
  ring phases and `cmpo`. Filed as issue #911 (the probe instrument's
  supported probing surface); it is ngspice's limitation, not `klt`'s,
  so it is not a klayout-tools friction item.
- The batch record this issue minted for the re-taken corner scores:
  `records/20261118-040726-44bd78d.md` (`ss_-40c_3.30v`,
  `sf_-40c_3.30v`, manifest-verified artifact store per DR-0041). It
  re-states the two points' committed scores on the current main
  netlist — `ss_-40c` FAIL on exactly the baseline's three checks
  (`err_se_max` 15, `err_df_max` 15, `nside_cells_df` 9.16096) with
  every other measure identical to the baseline record, and `sf_-40c`
  ERROR on the post-conversion-7 stall, agreeing with
  `20261116-012005-d0b5171`'s row in 15 of 17 cells. That baseline
  record remains committed unchanged as evidence for the same two
  points. **The two differing `sf_-40c` cells, measured and closed
  (issue #913) — not an abort artifact.** PR #912's description called
  the record "row-for-row" / "values identical"; the correction:
  `sw_conflict_se` 7.96063 -> 7.7076 and `nside_cells_se`
  0.0496545 -> 0.0475052. Two back-to-back local re-runs of the same
  point (testbench netlist sha256 `f73d1220...` unchanged, ngspice-47p1,
  `--ngspice-threads 1`, 968.8 s / 971.7 s) reproduce the 20261118
  record's values **exactly** (`sw_conflict_se` 7.70760,
  `nside_cells_se` 0.0475052, 40583 data rows in every log) — the
  ERROR point's partial `meas` maxima are reproducible, because the
  fatal is a *post-transient* `.meas` evaluation failure (`tdr_b`
  `WHEN=` out of interval after the stall; the derived
  `conv_period_ns` expression then errors), while the transient itself
  completes the full 64.5 us — no measurement window is truncated by
  the abort. The two cells differ between the records because the
  *measurement window*, not the circuit, moved between them: DR-0046
  (issue #844, `9f789758`/`7b01f5b6`) start these one-hot checks at
  `FROM=1.5u` instead of `FROM=0.1u` (manifest sha256 `93433a68...` ->
  `a9e8b4e7...`), and the baseline record's two maxima land inside
  conversion 1 (`sw_conflict_se` at 0.376 us, `nside_cells_se` at
  1.0006 us) — exactly the power-up window DR-0046 excludes; the
  20261118 record's land at 7.376 us / 2.0006 us. The suspected cause
  in issue #913 ("a run terminating on an ngspice fatal does not
  reproduce its partial `meas` maxima") is thereby measured-and-
  refuted; both values sit far inside their bounds either way.

## 1. The re-taken traces (AC1)

The issue's starting evidence could not be cited: the `cmpo` numbers
lived in #854's unmerged note (and its DR number is not this issue's to
cite), and the `sel_hi_n` numbers, while committed in #844's
investigation, predate this issue's own record requirement. Both traces
were re-taken on the current main netlist at `44bd78dd`.

### (a) `ss_-40c`, df loop, full 64.5 µs (18 n-side legs + `df_nside` saved)

The record's maximum reproduces **exactly**:
`df_nside` peaks at **9.16096 at t = 63.00066 µs** (bound 8.9–9.1;
#844's record row: 9.16096 at 63.0007 µs). The 18 leg voltages at the
peak instant:

```
weight :  256        128        64         32         16         8          4          2          1
hi  V  :  0.023      0.023      0.023      0.023      0.023      3.332      3.542      0.025      3.419
lo  V  :  3.300      3.300      3.300      3.300      3.300     -0.000     -0.000      3.300     -0.000
```

— identical to #844 §4b's table (3.542 worst on `hi_4n`), one-hot
boolean pattern intact, sum = 9 × 1.000 + (0.242 + 0.119 + 0.032) =
9.161. Over the whole run 16 of the 18 n-side legs exceed the rail at
least once (per-leg maxima 3.34–3.54 V on `hi_*`, 3.41–3.44 V on
`lo_*`); `lo_4n` never leaves 0 V and `hi_2n` never rises (their weights
are never asserted high in this run's code sequence).

Conversion table: **64 windows, every settled code exact except
conversion 3** (52 against expected 37, +15 exactly — §4). The record's
`err_df_max` = 15 at `ss_-40c` reproduces.

`cmpo` over the same run: max **3.6562 V at 34.3306 µs**, min
**−0.5545 V at 61.1389 µs**, 1924 of 53917 accepted timepoints above
VDD + 1 mV.

### (b) `sf_-40c`, df loop, full 64.5 µs (`df_cmpd`, `df_nside`, `df_drdy` saved)

**Seven conversions, all exact** (settled 5, 21, 37, 53, 69, 85, 101),
drdy #7 rising at 7.063 µs is the last — the sequencer then stalls
(the #844 §3 terminal-ring finding, here measured on the df loop; the
stall itself is #854's closed RTL defect and is not re-litigated here).
Pre-stall `nside_cells_df` = 9.03782 at 6.9387 µs (the record's value,
inside the bound). `cmpo` max **3.6468 V at 6.88088 µs**, min −0.3415 V,
138 of 40583 timepoints above VDD + 1 mV.

**The excursion time-stamp is the mechanism's signature**: the seven
largest excursions sit at 0.880854, 1.880877, 2.881658, 3.881009,
4.881008, 5.880875, 6.880875 µs — each **k + 0.8809 µs**, i.e. ~0.18 µs
before each conversion's drdy rise (k + 1.063 µs), and at every instant
`nside` reads ≈ 7.99 — the acquisition→trial transition where all 8–9
asserted DAC legs reconfigure at once. The same stamp appears in the ss
run's `cmpo` peaks (§3). At every one of these instants `df_cmpd` reads
**exactly 3.3000** (or 0.0000 at the undershoot instants, e.g. −0.3415 V
at 0.8165 µs with `cmpd` = 0.0000) — the bounded B-source never leaves
its rails while the node it feeds does.

## 2. The `sel_hi_n` overshoot: node, edge, energy source (AC2)

- **Node**: the rising `sel_hi_n_<w>n` outputs. In df mode these are the
  nor3 cells `X_091` (w4), `X_100` (w8), `X_163` (w1) — exactly the three
  weights asserted at the peak instant, with `hi_4n` worst.
- **Edge**: the conversion-boundary / trial-decision edges where the
  nor3's output rises as its `q<w>` input falls (the per-leg maxima
  cluster at the trial-boundary instants 2.0008, 3.0008, …, 63.00066 µs;
  the early-window A/Bs reproduce the family at every trial boundary).
- **Energy source**: displacement current through the driver's own
  gate-drain overlap capacitance as the input edge switches. In this
  deck the select legs drive *nothing physical*: `bdftopn`, `bdfnside`
  and `bdfconf` read them inside B-source expressions, which sense
  voltage with infinite impedance. The node's only capacitance is the
  driver transistors' own drain junctions and overlap caps — a
  parasitic-less witness node, so a few fF of coupled-injected charge
  produces tenths of a volt.

**Backing measurements** (all `ss_-40c`, df, `--until 4.2u`, identical
control block; the only difference per run is stated):

| run | deck delta (probe-only) | worst leg | `nside` max | `cmpo` max / min |
|---|---|---|---|---|
| baseline | — | 3.4855 (`hi_4n`) | 9.1597 | 3.6389 / −0.3118 |
| **E1 load-swap** | extracted `adc_tgate` on all 27 CDAC-array control legs (§5) | **3.3516** | **9.0463** | 3.6300 / −0.3277 |
| E2a | `.option trtol=1` | 3.5711 | 9.223 | 3.3024 / −0.2542 |
| E2b | `.option method=gear` | 3.5642 | 9.217 | 3.3500 / −0.0014 |

- The **load swap shrinks the excursion 3–4×** (worst leg −134 mV;
  every above-rail leg reduced) without changing the boolean one-hot
  pattern — the magnitude is set by the load, exactly as a
  capacitive-divider coupling predicts (~30 fF of real T-gate gate cap
  against a few fF of driver parasitics).
- The excursion **survives both tighter truncation control (trtol=1) and
  Gear integration** (3.57 / 3.56 vs 3.49 baseline) — it is not
  trapezoidal ringing, and the solver-options runs land at *slightly
  different* per-leg maxima because the accepted-timepoint population
  changes, not because the mechanism moved.
- **Classification**: *real driver/load interaction* (the coupling is
  in the BSIM models' overlap capacitances — real physics that a real
  netlist exhibits), with the deck's parasitic-less load amplifying it
  ~4× into visibility. Not a behavioural-source artifact (no B-source
  drives or senses these legs into range), not an ngspice artifact (E2).

Into the real load a ~52 mV above-rail residual remains on the worst
leg — the same mild family the ratified bound already carries at
nominal: `tt_27c`'s steady-state `nside_cells_df` 9.04957 (#844 §4b) is
this mechanism at 27 °C passing, and the E1 run's 9.0463 at ss cold is
indistinguishable from it.

## 3. The `cmpo` excursion: node, edge, energy source (AC2)

- **Node**: `df_cmpo` — `bdfcmp` (the behavioural comparator,
  `v(topp) > v(topn) ? vdd : 0`) through `rdfcmps` (1 kΩ) into
  `cdfcmpl` (100 fF) **plus the DUT `cmp` port's real gate load**: ten
  `aoi21_1` B inputs (the trial-latch array), ~100 fF of gate
  capacitance. So unlike the select legs, `cmpo` legitimately drives
  real gates — the load itself is the coupling path.
- **Edge**: each conversion's acquisition→trial transition
  (k + 0.8809 µs instants, §1b) where all asserted DAC legs plus the
  trial-latch AOI array switch simultaneously.
- **Energy source**: capacitive coupling from the DUT's simultaneous
  switching onto the comparator node. Ruled out, by measurement:
  *the behavioural source* — `df_cmpd` is exactly at its rail at every
  excursion instant over the full run (§1b), and an RC fed by a bounded
  node cannot exceed it; *the DUT-vs-source question* — E5 inserts
  10 kΩ between `df_cmpo` and the DUT `cmp` port (probe-only deck edit;
  logic levels unchanged, DC gate current zero) and the excursion
  **survives** (3.5927 at the same 0.8808 µs instant vs 3.6407
  baseline) — the excitation is the DUT's switching, reaching `cmpo`
  through the comparator path's capacitances whether or not the port is
  directly wired.

| run | deck delta (probe-only) | `cmpo` max | `cmpo` min |
|---|---|---|---|
| baseline (sf, 8 µs) | — | 3.6407 | −0.3415 |
| **E3** | +1 pF explicit on `df_cmpo` | **3.3016** | −0.0003 |
| **E5** | 10 kΩ between `df_cmpo` and the DUT `cmp` port | 3.5927 | −0.2852 |
| E2a (ss window) | `.option trtol=1` | 3.3024 | −0.2542 |
| E2b (ss window) | `.option method=gear` | 3.3500 | −0.0014 |

- **+1 pF annihilates it** (170×, far more than a fixed-charge
  capacitive divider's ~6× would give) — the excursion lives in the
  coupled gate-cap network of the load, and extra capacitance to the
  driven node breaks it.
- **The rendered amplitude is integration-dependent**: default 3.6389 →
  `trtol=1` 3.3024 → `gear` 3.3500. A physical coupled kick of a given
  charge does not move 300 mV with truncation tolerance; the
  default-option peak (3.6–3.66 V across runs) is therefore **not a
  quantitatively trustworthy physical number**, and this investigation
  does not use it as one.
- **Classification**: a *real coupled excitation* (real simultaneous
  switching, real load capacitances, no DC path, sub-ns, symmetric)
  whose saved amplitude in this deck is substantially solver-rendered.
  Not a behavioural-source artifact (§1b's `cmpd` measurement), not a
  parasitic-less-load artifact (`cmpo` carries ~100 fF of real gate
  load), and not cleanly separable into a ngspice artifact either — the
  honest statement is that the *mechanism* (coupling at the
  acquisition→trial edge) is measured and real, the *amplitude* is
  option-sensitive, and *nothing functional* ever samples it (§4).

## 4. Can `cmpo` > VDD corrupt the trial latch on a legal trajectory? (AC3)

**No — with waveforms, and with the actual cause of the one wrong word
identified.**

The legal-trajectory run is §1(a): `ss_-40c`, 64 conversions, the ring
one-hot for the whole run (#844 §4b measured the same; cadence nominal).
The run's only steady-state error is conversion 3: settled 52 against
expected 37 (+15 = +16 − 1, one-sided, settled — not a mid-update
capture artifact). The bit-level trace (probe `--nodes xdf.q0..q9,
xdf.ph_4..ph_14` + `--analog`, run `ss-qtrace`) decodes it completely:

- The trial flops are `q9..q0` (phase mapping `ph_4→q9 … ph_13→q0`),
  clocked by `clk`; flop `q_k`'s D is the AOI `!(ph·cmp | !(q_k+ph))`,
  i.e. **at its own trial edge `q_k` captures `!cmp`** (set = reject),
  otherwise it holds. The output register copies `q` at endconv
  (`c_i ← q_i`), so the end-of-conversion q word **is** the scored code.
- Entering conversion 3, the q word carried conversion 2's rejects
  (1010100000₂ = q0,q2,q4 set = 21 — conversion 2's correct output).
  Conversion 3's trials must *clear* q0, q2, q4 where the comparator
  accepts, and set fresh rejects otherwise.
- **`cmpo` was clean and correct at every one of the ten capture
  edges** (2.4375 → 3.0000 µs): fully settled 3.3000 or 0.0000,
  ±1 mV, at each `clk` rise. Every excursion (both §3's overshoots and
  undershoots down to −0.31 V) occurs in the 6–10 ns *after* an edge,
  in the dead zone before the next capture 62.5 ns later. **No capture
  instant ever samples an excursion.**
- The residue trace at the edges is clean ±weight quanta
  (+474.3, +218.3, +90.4, +26.4, −5.6, +10.4, +18.4, +14.4, +16.4, final
  +15.4 LSB-df) — the comparator decisions implied by the residues agree
  with `cmpo` at every edge.
- **The failures are captures, not decisions**: at the 8-weight trial
  (edge 2.7500 µs) `q4` must clear (D = `_025_` held logic-0 for the
  full ~60 ns of the trial — settling from a ±0.2 V post-edge chatter
  to a clean −0.001 V in the last ~10 ns) — it stays 1. At the
  2-weight trial (edge 2.8750 µs) `q2` must clear (D = `_017_`, same
  profile) — it stays 1. Both failures show the same signature: the D
  net **rises back to its hold-path value ~0.28 ns after the edge**
  (`_025_` reads 2.18 V at 2.750281 µs) as the phase-ring flop's clk→Q
  fall re-gates the AOI (`ph_9`: 3.30 V at the edge → 0.90 V at +0.28 ns
  → 0.09 V at +1.2 ns). The master latch, closing on its own
  internally-buffered clock at this corner, loses the race against that
  D edge and re-captures the stale Q. `q0`'s identical clear at 3.0000
  µs **succeeds** — its ring phase (`ph_13`) falls ~0.5–1.0 ns after
  the edge (1.98 V at +0.76 ns, 0.03 V at +1.3 ns), leaving the master
  time to close first — so the race outcome is edge-dependent, exactly
  what a marginal hold condition does at one PVT corner.
- Consequences, all measured: the q word at endconv is
  q2,q4,q5 = 4+16+32 = **52**; the DAC-removal steps (+16, +8, +2 LSB-df
  after the 2.6875/2.7500/2.8750 µs edges) are driven by the stale
  q values, so the residue terminates at +15.4 LSB where a correct
  conversion ends < 1 LSB; the free-MSB trial then correctly reads the
  shifted residue and accepts (q0 cleared — capture OK), landing the
  word at 52.
- **`drdy` is not touchable by this mechanism**: it is the ring's own
  output flop (`X_245`), clocked by `clk` with a D from the ring decode
  only — no `cmp` term exists in its input cone. The `q` capture is
  exonerated of the analog excursion by the settled-at-rail measurement
  above. **Verdict: cmpo > VDD cannot corrupt the trial latch, `drdy` or
  `q` capture on a legal trajectory in this deck; the one corruption the
  legal run contains is a flop hold race in the #854 netlist family,
  owned and dispositioned there.**

## 5. Benign demonstration into the real extracted T-gate gate load (AC4b)

The real CDAC bit cell (`design/cdac/cdac_array.sch`) loads every
control leg with a transmission gate: nfet_03v3 W=10 µm gate on the
`_n`-suffixed leg, pfet_03v3 W=20 µm gate on the `_p`-suffixed leg —
the laid-out, extracted, PMOS-body-remediated leaf
`ADC_TGATE` of
`layout/adc-top/parasitics/reports/20261117-165510-3a3d361/adc_tgate.para.spice`
(the same cell the committed extracted benches
`sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice` and
`gen_extracted_switch_ron_tb.py` instantiate, verbatim, with its
gate-net parasitics: R≈53–76 Ω, C≈0.59–0.76 fF per gate net, on top of
the W=10 µm/W=20 µm channel gates' ~30/60 fF).

**E1** wires one extracted `ADC_TGATE` per CDAC-array control leg
(rel/hi/lo × 9 weights × both gate polarities = 27 instances) into the
composed probe deck, `gn`/`gp` on the deck's own leg nets exactly as the
real bit cells drive them, channels tied to a common mid-rail node
(the gate capacitance is the load under test; the probe never switches
the channels), `vsubs` tied to ground the same way the committed
extracted bench does, and the cell's `vdd` pin on the deck's own
`.global vdd_gate` supply. Probe-only; the committed testbench is
untouched. **Committed as a flag (issue #913)**: this construction is
`probe_code_readout.py --tgate-load <that same para.spice leaf>` (exact
invocations in §7 item 4), with the instance count, pin order and all
three terminations pinned by
`sim/tests/test_probe_code_readout.py::TgateLoadTests` — E1 is now a
pure flag invocation, byte-reproducible from the committed tree like
every other probe in this note, with no hand-edited deck and no `/tmp`
provenance.

Results, `ss_-40c` (the worst corner), 0–4.2 µs window:

| metric | baseline (deck as committed) | **E1 (real T-gate load)** |
|---|---|---|
| worst leg | 3.4855 V (`hi_4n`) | **3.3516 V** |
| `nside` peak | 9.1597 (outside 8.9–9.1) | **9.0463 (inside 8.9–9.1)** |
| legs above 3.311 V at the `nside` peak | 7 (3.344–3.485 V) | 7 (3.312–3.352 V) |
| boolean one-hot at the peak | intact | intact |
| settled conversion errors | conv 3 = +15 | conv 3 = +15 (unchanged — §4's race is not load-sensitive, as expected) † |

And `sf_-40c`, same construction, 0–8 µs window: baseline `nside` max
9.03782 (already inside the bound, at 6.9387 µs pre-stall); with the
T-gate load the whole-window peak lands at **9.00939** (4.00063 µs) —
further inside the bound. The
ss cold corner is the governing case and it lands at 9.0463 —
statistically the ratified bound's own nominal-temperature territory
(`tt_27c` 9.04957, `ss_125c` 9.09143, `sf_125c` 9.03607 in the deck's
committed records).

The full-length E1 run (64.5 µs, same construction) is the benign
demonstration's headline: its whole-run `nside_cells_df` maximum is
**9.06642 at 63.00066 µs** — the same trial-boundary instant the
committed deck peaks at — against the unloaded deck's 9.16096 (worst
leg `hi_4n` 3.3752 V against 3.5438 V). Inside the ratified 8.9–9.1
bound over the whole legal run.

**Re-verified via the committed `--tgate-load` flag (issue #913,
2026-11-18, post-#912 `main`, ngspice-47p1)**: all three headline
numbers reproduce to 5 significant figures — the 0–4.2 µs window reads
`nside` max **9.04625** at 2.00076 µs with worst leg **3.35159 V**
(above: 9.0463 / 3.3516); the `sf_-40c` 0–8 µs window reads
**9.00939** at 4.00063 µs (above: 9.00939); the full-length run reads
whole-run `nside` max **9.06642** at 63.0007 µs with worst leg
**3.37521 V** (above: 9.06642 at 63.00066 µs / 3.3752 V). † **One
recorded deviation**: under the committed reconstruction conversion 3
settles *correctly* (code 37 against exp 37) in both the 4.2 µs window
and the full 64.5 µs run, where the original hand-edited E1 deck had
reported conv 3 = +15 unchanged; the unloaded baseline re-measured on
the same host does show the +15 (code 52 against exp 37), so the A/B
is otherwise faithful. §4's hold race is a ~0.28 ns margin race, and
the extracted legs' gate-net RC (R≈53–76 Ω, C≈0.59–0.76 fF per gate
net ahead of the ~30/60 fF channel gates) is exactly the scale of
perturbation that can re-time the re-gating edge and resolve it — a
benign-direction difference between the original hand edit and the
committed reconstruction, recorded here rather than reconciled away
(the original `/tmp/910-probe/e1-*` logs are gone, so which
construction detail carried the difference is not auditable). It does
not weaken the load conclusion: the reproduced headline numbers are
the ones DR-0048 leans on, and a resolved race only shrinks the
benign demonstration's residue.

**Honest residual, stated rather than buried**: into the real load the
legs still transiently exceed the rail by ~50 mV worst-case. That is
the same in-model coupling family every corner of the deck already
measures at nominal temperature inside the ratified bound; it is a
self-limiting sub-ns transient into gate-oxide caps rated for the rail,
not a DC condition, and the boolean one-hot pattern — what the check
exists to witness — is intact at every instant.

## 6. Dispositions and what stays open

1. **`ss_-40c`'s `nside_cells_df` stays a recorded FAIL.** The deck and
   the bound are untouched by this issue; the committed instrument reads
   9.16096 > 9.1. What changed is the *attribution*: the excursion is a
   load-model-amplified real coupling, into the real T-gate load it
   lands inside the bound, and the deck's own failure is entangled with
   a genuine netlist defect (§4's hold race keeps `err_*` failing at
   this corner regardless).
2. **DR-0048** (`spec/decision-records/DR-0048-nside-witness-above-rail-attribution.md`,
   **proposed — requires operator sign-off**) records the derivation
   behind that attribution and the bound-scope question. This issue does
   not move the bound and does not re-score the point; the DR is the
   properly-derived instrument for whoever ratifies a disposition.
3. **The hold race (§4) is new evidence in the #854 family**: a
   netlist-level timing defect at ss cold, visible in this deck's
   legal-trajectory run as conversion 3's +15. This issue does not
   change RTL, synthesis or the netlist; #854's fix branch re-times the
   ring and its evidence already covers the ring-half. Whether the
   trial-flop D-hold margin needs its own STA clause is #854's (or its
   successor's) to close — the waveforms here are the starting
   measurement.
4. **No klt friction filed for extraction** (the extracted leaf already
   existed and instantiated cleanly). The one flow gap hit —
   cell-internal nodes unaddressable from an ngspice `.control` block
   (§ Provenance), which cost the flop-master-latch visibility in §4 —
   is filed as **issue #911** against this repo's probe instrument, not
   against klayout-tools: `klt` was never the awkward tool here.

## 7. Probe command reference

Each run: `python3 design/sar-logic/flow/probe_code_readout.py <args>`,
kept under `/tmp/910-probe/<name>/` (composed deck + raw log;
regenerable). The `<w>` lists are 256,128,64,32,16,8,4,2,1. The
`nside` leg list is `v(df_sel_hi_n_<w>n),v(df_sel_lo_n_<w>n),v(df_nside)`
for all nine weights.

1. **AC1 ss re-take** (`ss-full`): `--tag df --corner ss --temp -40
   --vdd 3.30 --analog --nodes <nside legs>` (full 64.5 µs).
2. **AC1 sf re-take** (`sf-full`): `--tag df --corner sf --temp -40
   --vdd 3.30 --analog --nodes v(df_cmpd),v(df_nside),v(df_drdy)`
   (full 64.5 µs).
3. **Early-window baseline** (`ss-early-base` / `sf-early-base`): same
   as 1/2 with `--until 4.2u` / `--until 8u` — the A/B baseline for
   every experiment below.
4. **E1 load-swap** (`e1-tgload`, `e1-full`, `e1-sf`): the §3 baseline
   commands plus `--tgate-load layout/adc-top/parasitics/reports/20261117-165510-3a3d361/adc_tgate.para.spice`
   — committed as the `--tgate-load` flag by issue #913, so E1 is a
   pure flag invocation like every other probe here (the probe emits
   the 27 extracted `ADC_TGATE` instances, the `vgcm vcm_tg 0 dc
   {vdd_val/2}` / `vsubsrc vsubs 0 dc 0` ties and the leaf `.include`
   itself; see §5):

   ```
   # e1-tgload (ss, 0-4.2 us) and e1-full (ss, 64.5 us: drop --until)
   python3 design/sar-logic/flow/probe_code_readout.py \
       sar-logic-functional-gates --tag df --corner ss --temp -40 \
       --vdd 3.30 [--until 4.2u] --analog --nodes <nside legs> \
       --tgate-load layout/adc-top/parasitics/reports/20261117-165510-3a3d361/adc_tgate.para.spice
   # e1-sf (sf, 0-8 us)
   python3 design/sar-logic/flow/probe_code_readout.py \
       sar-logic-functional-gates --tag df --corner sf --temp -40 \
       --vdd 3.30 --until 8u --analog --nodes <nside legs> \
       --tgate-load layout/adc-top/parasitics/reports/20261117-165510-3a3d361/adc_tgate.para.spice
   ```
5. **E2a/E2b solver options** (`e2a-trtol`, `e2b-gear`): baseline deck +
   `.option trtol=1` / `.option method=gear`.
6. **E3** (`e3-cmpo1p`): baseline deck + `cf910 df_cmpo 0 1p`.
7. **E5** (`e5-cmpo-iso`): baseline deck with the testbench copy's DUT
   instantiation re-wired through `rdf910 df_cmpo xcmp_dut 10k`.
8. **§4 flop trace** (`ss-qtrace`, `ss-flopd2`): `--tag df --corner ss
   --temp -40 --until 4.2u/3.1u --analog --nodes xdf.q0..q9,
   xdf.ph_4..ph_14` / `--nodes xdf._025_,xdf.q4,xdf._017_,xdf.q2,
   xdf.ph_9,xdf.ph_11,xdf._057_,xdf.ph_13,xdf.ph_14`.

The batch confirmation record (§ Provenance) was minted with:

```
python3 sim/run_corners.py sar-logic-functional-gates \
  --corners ss sf --temps -40 --supply 3.30 --supply-tol 0 \
  --backend batch --timeout 1700 --max-units-per-job 2 \
  --max-concurrent-jobs 2 --capacity-retries 6 \
  --subset-reason "Issue #910 AC1 re-take: ..."
```
