# Investigation 20260919-issue-320: `abs_err_delay_0ns` is two different findings, and neither is a setup violation

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — a root-cause investigation of the
`abs_err_delay_0ns` failures in
`sim/sar-logic-timing-gates-ok/records/20260918-233547-1d81aa1.md`, the first
scored 45-point grid for the gate-level SAR timing claim. Kept in
`investigations/`, alongside (not inside) `records/`, so the append-only
`records/` tree is never edited.

Everything below is re-runnable from the tree, through one new instrument
this investigation adds (`design/sar-logic/flow/probe_code_readout.py`,
structurally guarded by `sim/tests/test_probe_code_readout.py`) plus reads of
evidence already committed:

```bash
# the worst point of the grid, full ratified 8.5 us window: per-conversion
# INSTANTANEOUS vs SETTLED code error, and the settling-guard sweep
python3 design/sar-logic/flow/probe_code_readout.py sar-logic-timing-gates-ok \
    --corner sf --temp 125 --vdd 3.30 --bits

# a cheap cut -- the first conversion only (8 of the 10 failing points)
python3 design/sar-logic/flow/probe_code_readout.py sar-logic-timing-gates-ok \
    --corner tt --temp 125 --vdd 2.97 --until 1.3u --bits

# the A/B: start the same point from the state a power-on reset would leave
# the engaged-weight flags in. Writes nothing -- no RTL, netlist, testbench
# or bound changes.
python3 design/sar-logic/flow/probe_code_readout.py sar-logic-timing-gates-ok \
    --corner tt --temp 125 --vdd 2.97 --until 1.3u --bits --ic-eng-zero
```

## Conclusion

**Issue #320's ten failing points are TWO unrelated mechanisms, and the one
the issue proposed — a setup-time violation in the SAR register's gate-level
logic path — is not either of them.**

> **A. The first conversion after power-up is genuinely invalid** (8 of the 10
> points; measured settled code errors of 252, 252, 252, 252, 5, 5, 1 and 1
> LSB). `sar_ctrl.v`'s `start` pulse seeds the 16-phase ring `ph[15:0]` and
> nothing else: the nine engaged-weight flags `eng[9:1]` are cleared only by
> `endconv = ph[13]`, which arrives *inside* the first conversion, after that
> conversion's own sample and its first nine bit trials. So the first
> conversion runs its binary search against an arbitrary, PVT-dependent set of
> already-engaged CDAC weights, and produces a wrong code. This is a **real
> property of the committed design**, not a testbench artifact — it would
> happen on silicon — and it is bounded: **exactly one** conversion is
> affected, and every conversion after it is exact at every corner measured.
>
> **B. `b<tag>err`'s `drdy` gate opens while the output register is still
> updating** (the 2 remaining points, both reporting the headline 512 LSB).
> `drdy` and `c[9:0]` are loaded on the *same* rising clock edge; the ten
> code bits take 0.186–0.199 ns to settle, and the measurement decodes
> whatever accepted timepoints land inside that window as a code. At the
> 511 → 512 major carry the `ok` stimulus deliberately crosses, all ten bits
> change at once, so the mid-update word can read 0 — giving exactly 512 LSB
> against an expected 512. **The conversion is correct**: at
> `sf_125c_3.30v`, conversion #6's settled code is 512, exactly right, while
> `meas tran aerr_ok MAX` reports 512 LSB of error for it. A 0.25 ns
> settling guard removes this entirely at every corner measured, while
> leaving mechanism A's real error untouched.

**On the setup-violation hypothesis (issue #320's own reading, and its
acceptance criterion 2): refuted, from three directions.** See
"STA's verdict" below. Neither mechanism is a max-delay path, so STA and
SPICE are not in disagreement about anything; the existing post-route STA
record's +56.365 ns worst setup slack (a ~6.1 ns data path in a 62.5 ns
budget) leaves no room for the ~10x degradation a setup failure would need;
and the direct SPICE readout at `sf`/125 °C — the corner STA cannot reach —
shows conversions #2–#8 all exact with the output register settling in
0.186 ns.

**On the `sf`/`fs` STA coverage gap** the Curator flagged on the issue: it is
real, and it **cannot be closed with this PDK**. `gf180mcu_fd_sc_mcu7t5v0`
ships 15 Liberty files — 6 `ss`, 6 `ff`, 3 `tt` — and **zero** `sf`/`fs`
(same census for `mcu9t5v0`: 6/6/3). Mixed nfet/pfet-skew corners are not
characterised in the open gf180mcu standard-cell libraries, so no `klt sta`
run at `sf` or `fs` is possible, now or later, without new library
characterisation. This is stated as a fact about the shipped PDK, measured by
counting files (below), not as a claim about what such a run would find.

The disposition is
`spec/decision-records/DR-0029-power-up-first-conversion-validity.md`.

## Evidence 1 — the failing points' own `at=` timestamps already split the set

Read from the committed 45 logs, no new run
(`sim/sar-logic-timing-gates-ok/corners/20260918-233547-1d81aa1/*.log`,
`grep '^aerr_ok'`). `meas` reports *when* the maximum was attained, and the
record's result table does not carry that column:

| corner-id | `aerr_ok` | `at` | drdy rise it lands on |
|---|---:|---:|---|
| `sf_125c_3.30v` | 512 | 6.06316 µs | #6 + 30 ps |
| `sf_125c_3.63v` | 512 | 6.06311 µs | #6 + 30 ps |
| `sf_125c_2.97v` | 252 | 1.12566 µs | #1 (window end) |
| `ss_-40c_3.63v` | 252 | 1.12542 µs | #1 |
| `ss_125c_3.63v` | 252 | 1.12564 µs | #1 |
| `tt_125c_2.97v` | 252 | 1.12549 µs | #1 |
| `fs_27c_2.97v` | 5 | 1.12543 µs | #1 |
| `ss_125c_3.30v` | 5 | 1.12567 µs | #1 |
| `ss_-40c_3.30v` | 1 | 1.12544 µs | #1 |
| `tt_-40c_2.97v` | 1 | 1.12541 µs | #1 |
| *(the other 35)* | 0 | 8.50000 µs | — (no error anywhere) |

Eight of the ten land in the **first** `drdy` window; two land 30 ps after
the **sixth** `drdy` rise. Two populations, two mechanisms. The rest of this
document takes them in that order.

## Evidence 2 — the correlation, across all 45 committed points

Also read from the committed logs, no new run. Every ngspice log carries its
own `Initial Transient Solution` node dump, so the DUT's power-up flop state
is recoverable for all 45 points. Thresholding `xok.eng<i>` at that point's
own VDD/2:

| | `aerr_ok > 0` | `aerr_ok = 0` |
|---|---:|---:|
| `eng[9:1] != 0` at power-up | **10** | 7 |
| `eng[9:1] == 0` at power-up | **0** | 28 |

**Every failing point has a non-zero power-up engaged-weight state, and every
point that powers up with `eng == 0` passes — zero counterexamples in either
direction.** The 7 points in the top-right cell are the reason this is stated
as a *necessary*, not sufficient, condition: a benign garbage pattern
(or one whose injected offset happens not to flip any trial) still converts
correctly. Re-derive with:

```python
# for each corners/*.log: parse the Initial Transient Solution node dump,
# threshold xok.eng9..xok.eng1 at that point's VDD/2, and compare with the
# log's own `aerr_ok = ... at= ...` line.
```

## Evidence 3 — the first conversion's code, read out per failing point

`probe_code_readout.py ... --until 1.3u --bits`, one run per point. `exp` is
the deck's own `ok_exp` (= `floor(v(ok_shxp)/lsbse)`), 507 at every point —
the ramp's first sample is the same everywhere. "First wrong bit" is the
most-significant position at which the settled `c9..c0` word differs from the
expected word `0111111011`:

| corner-id | power-up `eng9..eng1` | conv-1 code `c9..c0` | value | settled err | first wrong bit (trial phase) |
|---|---|---|---:|---:|---|
| `tt_125c_2.97v` | `111111111` | `0011111111` | 255 | **252** | bit 8, weight 128 (`ph[5]`) |
| `ss_125c_3.63v` | `111111111` | `0011111111` | 255 | **252** | bit 8, weight 128 (`ph[5]`) |
| `sf_125c_2.97v` | `111111111` | `0011111111` | 255 | **252** | bit 8, weight 128 (`ph[5]`) |
| `ss_-40c_3.63v` | `111111110` | `0011111111` | 255 | **252** | bit 8, weight 128 (`ph[5]`) |
| `fs_27c_2.97v` | `100000000` | `1000000000` | 512 | **5** | bit 9, free MSB (`ph[4]`) |
| `ss_125c_3.30v` | `000111111` | `1000000000` | 512 | **5** | bit 9, free MSB (`ph[4]`) |
| `ss_-40c_3.30v` | `000000001` | `0111111100` | 508 | **1** | bit 2, weight 4 (`ph[11]`) |
| `tt_-40c_2.97v` | `000000001` | `0111111100` | 508 | **1** | bit 2, weight 4 (`ph[11]`) |
| `sf_125c_3.30v` | `101011111` | `0111011111` | 479 | **28** | bit 5, weight 16 (`ph[8]`) |
| `sf_125c_3.63v` | `101010101` | `0111111011` | **507** | **0** | — (conversion 1 is exact here) |
| *`tt_27c_3.30v` (passing, for contrast)* | `000000000` | `0111111011` | 507 | 0 | — |

That is acceptance criterion 1's "bit index", per point. Two structural
readings fall straight out of the code words:

* **`255 = 0011111111` is the signature of one wrong decision at bit 8.** The
  free MSB is right (`c9 = 0`); bit 8 resolves low when it should resolve
  high; and the search then correctly drives every remaining weight high,
  saturating at the largest code reachable below the wrong branch.
  `512 = 1000000000` is the same signature one bit up: the free MSB resolves
  high and everything below saturates low.
* **`sf_125c_3.63v`'s conversion 1 is exact.** Its 512 LSB is mechanism B
  alone. `sf_125c_3.30v` carries *both* — a real 28 LSB conversion-1 error
  and a 512 LSB decode transient at conversion 6 — and `MAX` reports the
  larger, which is why the headline number in the record points at the
  harmless one.

## Evidence 4 — the A/B: forcing the engaged flags to their post-reset value

`--ic-eng-zero` adds `.ic v(xok.eng<i>)=0` for all nine flags to **one run's
deck**, i.e. starts the run from the state a power-on reset would leave them
in. It writes nothing: no RTL, no netlist, no manifest, no bound.

| point | conv-1 settled error, as committed | with `--ic-eng-zero` |
|---|---:|---:|
| `tt_125c_2.97v` | 252 (code 255) | **0 (code 507)** |
| `ss_125c_3.63v` | 252 (code 255) | **0 (code 507)** |
| `sf_125c_3.30v` | 28 (code 479) | 5 (code 512) |

The first two rows are the causal demonstration: the same deck, the same
corner, the same stimulus, the same netlist — only the power-up value of nine
flip-flops differs — and the first conversion goes from 252 LSB wrong to
exactly right.

**The third row is reported because it is a partial result, not a clean one.**
`.ic` constrains a node during the operating-point solve and releases it at
t = 0; for a `dffq_1` whose *internal* latch nodes are not constrained with
it, the flop can settle back toward its natural state. At `sf_125c_3.30v` the
knob improves the first conversion (28 → 5 LSB) without fixing it, which is
consistent with an incompletely-applied initial condition and is **not**
offered as evidence for anything. The clean, knob-free version of the same
claim is Evidence 5: at that same point, conversions #2–#8 are all exact.

## Evidence 5 — instantaneous vs settled, over the full ratified window

`probe_code_readout.py ... --bits`, no `--until`, the deck's own
`tran 5n 8.5u 0 5n`. "inst max" is the maximum of `|code - exp|` over the
`drdy` window — the quantity `meas tran aerr_ok MAX v(ok_aerr) FROM=0.1u`
takes its maximum of. "settled" is the same quantity at the **end** of that
window, after the output register has finished updating.

**`sf_125c_3.30v` — the grid's worst point (7260 accepted timepoints):**

| conv | exp | settled code | settled err | inst max err | inst max at | register settling |
|---:|---:|---:|---:|---:|---|---:|
| 1 | 507 | 479 | **28** | 187 | drdy rise + 0 s | 0.1986 ns |
| 2 | 508 | 508 | 0 | 32 | drdy rise + 0 s | 0.1861 ns |
| 3 | 509 | 509 | 0 | 1 | drdy rise + 0 s | 0.1985 ns |
| 4 | 510 | 510 | 0 | 2 | drdy rise + 0 s | 0.1861 ns |
| 5 | 511 | 511 | 0 | 1 | drdy rise + 0 s | 0.1985 ns |
| **6** | **512** | **512** | **0** | **512** | drdy rise + 0 s | 0.1861 ns |
| 7 | 513 | 513 | 0 | 1 | drdy rise + 0 s | 0.1985 ns |
| 8 | 514 | 514 | 0 | 2 | drdy rise + 0 s | 0.1861 ns |

Conversion #6 is the 511 → 512 major carry. Its settled code is **512 —
exactly correct** — and the measurement reports **512 LSB of error** for it.
Conversions #2–#8 are all exact; only conversion #1 is really wrong, and by
28 LSB, not 512.

**The other three full-window runs, same command, different points:**

| point | conv-1 settled err | conv-2..8 settled err | worst inst max |
|---|---:|---:|---:|
| `sf_125c_3.30v` | 28 | 0 (all seven) | 512 |
| `tt_125c_2.97v` | 252 | 0 (all seven) | 252 |
| `ss_125c_3.63v` | 252 | 0 (all seven) | 252 |
| `tt_27c_3.30v` *(passing)* | 0 | 0 (all seven) | 0 |

**Why the transient shows up at `sf` and not at `tt`/`ss`.** At
`tt_125c_2.97v` and `ss_125c_3.63v` the "inst max" equals the settled value
exactly — the solver's accepted timepoints straddle the whole ~0.19 ns
register transition without landing inside it, so nothing mid-update is ever
decoded. At `sf_125c_3.30v` they do land inside it. **Whether
`abs_err_delay_0ns` reports a 512 LSB decode transient is therefore a
property of the solver's accepted-timepoint grid, not of the circuit** —
which is the strongest single argument that the measurement as written is
ill-posed, independent of any judgment about the design.

## Evidence 6 — the settling guard that separates the two mechanisms

Computed by the probe over the same runs: what `MAX v(ok_aerr)` would report
if the `drdy` gate were held off for a settling guard after each `drdy` rise.
0 ns is the committed `bokerr` gate.

**`sf_125c_3.30v`, full 8.5 µs:**

| guard (ns) | MAX \|code − exp\| (LSB) | conversions flagged wrong |
|---:|---:|---:|
| **0.00** | **512** | **8** |
| 0.25 | 28 | 1 |
| 0.50 | 28 | 1 |
| 1.00 | 28 | 1 |
| 2.00 | 28 | 1 |
| 5.00 | 28 | 1 |

A guard anywhere from 0.25 ns to 5 ns gives the same answer — 28 LSB, one
wrong conversion, the first — so the choice of guard is not a tuning knob
with a convenient value; the transient simply ends and nothing else in the
1 µs conversion period is sensitive to it. The same sweep at
`tt_125c_2.97v` and `ss_125c_3.63v` reads 252 at every guard including 0 (no
transient there to remove), and 0 at every guard at the passing
`tt_27c_3.30v`.

**Note what the guard does NOT do**: it does not relax `abs_err_delay_0ns`.
The 0.5 LSB bound is untouched, the first conversion still fails it by 28–252
LSB, and a genuinely late decision — the `bad` loop's whole purpose — moves
the *settled* code and is caught by a larger margin than a 1-LSB glitch ever
was.

## Evidence 7 — the mechanism is structural, and is now pinned by a test

Mechanism A is not an inference from waveforms: it is readable off the
committed RTL and re-derivable from the committed gate netlist. Both are
asserted by `sim/tests/test_probe_code_readout.py::ResetStructureTests`, so a
later reset change breaks the test and points at DR-0029 rather than silently
invalidating it.

**From `design/sar-logic/rtl/sar_ctrl.v`:**

```verilog
ph[0]  <= start | ph[15];
ph[k]  <= ph[k-1] & ~start;          // all 15 other phases
...
wire endconv = ph[13];
eng<i> <= (arm<i> | eng<i>) & ~endconv;   // <- no `start` term
if (arm<i>) q<i> <= dec;                  // <- no `start` term
if (ph[14]) c<i>_r <= q<i>;               // <- no `start` term
```

**From the committed gate netlist** (`tb_sar_logic_timing_gates_ok.spice`,
walking each of the 45 flip-flops' combinational D-cone back to a flop
output or a port):

| flop group | count | is `start` in the D cone? |
|---|---:|---|
| `ph_0` … `ph_14` | 15 | **yes** (all 15) |
| `drdy` | 1 | **yes** |
| `eng9` … `eng1` | 9 | **no** (none) |
| `q9` … `q0` | 10 | **no** (none) |
| `c9` … `c0` | 10 | **no** (none) |

Two consequences follow directly, and neither needs a simulation:

1. **No `start` pulse of any length clears `eng`.** While `start` is high the
   ring is pinned at `ph[0]`, so `arm<i> = ph[4..12]` and
   `endconv = ph[13]` are all low and `eng<i> <= eng<i>` holds its power-up
   value indefinitely. Asserting `start` for longer does not help; this is
   why `design/sar-logic/rtl/README.md`'s "Real hardware note" remedy, which
   is correct for the ring, is not sufficient for the conversion.
2. **Exactly one conversion is affected.** `endconv = ph[13]` clears all nine
   flags on the edge leaving the last bit trial of conversion 1; `q[9:0]` are
   all overwritten by conversion 2's own trials, and `c[9:0]` reload from
   them at `ph[14]`. Conversion 2 onward is a function of the input alone.
   That is what Evidence 5's "conv-2..8 settled err = 0 (all seven)" column
   measures, at all four points including the two worst.

## STA's verdict on this path, at these corners (acceptance criterion 2)

**There is no disagreement between STA and SPICE to explain, because neither
mechanism is a timing path STA models.** Mechanism A is a missing reset — a
power-up state question, invisible to static timing by construction.
Mechanism B is a measurement B-source in the testbench sampling the DUT's
output register during its own clk→Q window; the register itself meets
timing, which is exactly why the settled code is right.

The existing post-route record
(`design/sar-logic/flow/sar_ctrl/records/20260915-093934-7ab8971.mcu7t5v0.sta_postroute.md`,
issue #275) nevertheless rules the setup hypothesis out with room to spare:

| corner | setup slack | data path implied (62.5 ns − slack) |
|---|---:|---:|
| `tt_025C_3v30` | +59.4791 ns | 3.021 ns |
| `ss_125C_3v00` | **+56.3650 ns** (worst) | **6.135 ns** |
| `ss_n40C_3v00` | +58.1701 ns | 4.330 ns |
| `ff_125C_3v60` | +60.0932 ns | 2.407 ns |
| `ff_n40C_3v60` | +60.7878 ns | 1.712 ns |

A setup failure needs the longest data path to exceed 62.5 ns. At the slowest
corner STA can reach it is 6.135 ns — **a 10.2x degradation would be required**,
which no process-skew corner produces (the whole `ff`→`ss` span in this table
is 3.6x). And the SPICE side supplies the direct measurement at the corner
STA cannot reach: at `sf_125c_3.30v`, the output register's clk→Q settling is
**0.186–0.199 ns** against the 62.5 ns period, and conversions #2–#8 are all
exact. If the logic missed setup at `sf`/125 °C, those conversions would be
wrong too.

**The `sf`/`fs` gap the Curator flagged is real and is not closeable with this
PDK.** Counted in the resolved PDK
(`~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/`, open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`):

| library | Liberty files | `tt` | `ss` | `ff` | `sf` | `fs` |
|---|---:|---:|---:|---:|---:|---:|
| `gf180mcu_fd_sc_mcu7t5v0` | 15 | 3 | 6 | 6 | **0** | **0** |
| `gf180mcu_fd_sc_mcu9t5v0` | 15 | 3 | 6 | 6 | **0** | **0** |

`klt sta` needs a Liberty view per corner. The open gf180mcu standard-cell
libraries are characterised at pure-skew corners only, so **no `sf`/`fs` STA
run was, is, or will be possible** without new characterisation — a PDK
limitation, not an un-run measurement, and not a `klt` gap (so not a
friction-protocol filing under CLAUDE.md either). The corner axis SPICE
sweeps (`mos`, five process skews) and the corner axis STA can sweep are
structurally different sets, and this investigation does not paper over that:
it supplies the SPICE-side measurement at `sf` instead.

## The sibling functional deck agrees, and its pass was luck (issue #320 step 3)

`sim/sar-logic-functional-gates/` carries the same `FROM=0.1u` measurement
window and the same ±0.5 LSB bound (`err_se_max`/`err_se_min`/`err_df_*`), so
it is exposed to mechanism A identically. Issue #320 asked whether running
its temperature axis would confirm or refute. **It is answerable without
running anything**, from that deck's own committed logs:

| record | points | power-up `eng` (both loops) | `err_se_*` / `err_df_*` |
|---|---:|---|---|
| `20260915-214338-912a8ec` | 5 (`mos` axis, 27 °C, 3.30 V) | `000000000` at all 5 | 0 at all 5 |
| `20260917-044312-c7ff0ff` | 5 (same axis) | `000000000` at all 5 | 0 at all 5 |

**Every point that deck has ever scored powers up with `eng == 0`** — the
benign cell of Evidence 2's table — so its clean pass is consistent with
mechanism A rather than evidence against it. Its temperature axis (−40 /
125 °C) and its supply axis have never been run, and in the `ok` grid the
non-zero power-up states cluster exactly there (6 of the 10 failing points
are at 125 °C; every one is off the `tt`/27 °C/3.30 V point that deck has
scored). Running the functional deck's temperature axis is therefore expected
to surface the same first-conversion error — a **prediction**, stated as one,
not a result.

## What this investigation does NOT establish

- **It is not a scored PVT result.** `probe_code_readout.py` replaces the
  manifest's `meas` block with a raw print and writes nothing under
  `records/`/`corners/`/`netlist-snapshots/`. The grid this document
  interprets is still `20260918-233547-1d81aa1`, unedited, and this document
  does not mint a new record or move a bound. Re-running the `ok` grid is
  explicitly out of scope for issue #320.
- **It does not claim the 7 benign `eng != 0` points are safe.** They are
  points at which an arbitrary power-up state happened not to flip a trial on
  this one input ramp. Nothing here predicts which power-up states are
  benign, and the point of DR-0029 is that none of them should be relied on.
- **It does not measure silicon power-up behaviour.** ngspice's
  `Initial Transient Solution` is the DC operating point of the cross-coupled
  latches, which is a *plausible* stand-in for an unknown power-up state, not
  a distribution over real ones. What the measurements establish is that the
  design's output depends on that state at all — which is the defect —
  not how a real die would land.
- **It does not fix anything.** The `b<tag>err` gate, the `FROM=0.1u`
  windows, `sar_ctrl.v` and every `tb.json` bound are **unchanged in the
  tree**. `--ic-eng-zero` is a measurement knob that writes nothing. The
  disposition, the alternatives weighed, and the follow-on work are in
  `spec/decision-records/DR-0029-power-up-first-conversion-validity.md`,
  and the work that record defers is filed as **#327** (correct the
  measurement, regenerate and re-score the decks) and **#328** (decide the
  RTL reset and pay the P&R/STA re-do if it is taken).
- **It does not re-open DR-0027.** That record's accepted one-hot hazard
  budget is a different measurement on a different net; mechanism B is the
  same *class* of finding (a continuously-evaluated check reading a
  synthesized netlist's real sub-nanosecond switching window as a
  steady-state violation) one register further downstream, and DR-0029 says
  why the same response — revise the bound — is the wrong one here.

## Environment

- PDK: `gf180mcuD` @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (`~/.volare/gf180mcuD`, MIM stack `m4m5`)
- ngspice: `ngspice-46`, SPARSE 1.3 direct solver (`option klu` not set)
- python 3.12.3; `klt 0.4.0+g2f64ab88bfcc` (used only for the Liberty-corner
  census above — no `klt` run was made)
- Deck: `sim/sar-logic-timing-gates-ok/testbench/` as committed, composed
  through `sim/harness`'s own `compose_deck`, so the PVT preamble, corner
  sections and `sar_ctrl_a` subckt are the ones `sim/run_corners.py` uses.
  The probe replaces only the `.control` measurement block.
- Tree: `feature/issue-320` on top of `177618b`; the only addition the runs
  above depend on is `design/sar-logic/flow/probe_code_readout.py` itself.
- Host: 8 cores, 15 GiB, shared with concurrent ngspice work throughout
  (load average 4–5 for the whole session). **No wall-clock figure appears
  anywhere above**, deliberately: every quantitative claim is a code, a
  voltage threshold, a settling time, a file count or a slack.
