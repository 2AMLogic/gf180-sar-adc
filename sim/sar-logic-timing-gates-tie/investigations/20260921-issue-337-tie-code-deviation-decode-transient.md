# Investigation 20260921-issue-337: `tie_code_deviation = 512` is the output register read mid-carry, not a saturated code

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — a root-cause investigation of the
six `tie_code_deviation` failures in `sim/sar-logic-timing-gates-tie/`'s
ratified 45-point `mos` grid
(`records/20260920-020802-2043286.md`, issue #303), each reporting **exactly
512** against a `max 1.0` bound:

| corner-id | `dev_tie` | `at` (s) |
|---|---:|---:|
| `ff_27c_3.63v` | 512 | 1.06289e-06 |
| `ss_27c_3.30v` | 512 | 2.06323e-06 |
| `fs_27c_3.30v` | 512 | 3.06302e-06 |
| `fs_27c_3.63v` | 512 | 7.06298e-06 |
| `tt_-40c_3.63v` | 512 | 7.06293e-06 |
| `tt_27c_2.97v` | 512 | 8.06309e-06 |

Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only `records/` tree is never edited. **Nothing in the tree's decks,
manifests, RTL or bounds is changed by this document**; the only code change
it carries is the readout probe learning to read a loop whose reference code
is a constant (`--exp-const`, defaulted for `tie`), which writes nothing and
is what makes the central measurement reproducible at all.

Everything below is re-runnable from the tree:

```bash
# the issue's own nominated point: the full ratified 8.5 us window,
# per-conversion INSTANTANEOUS vs SETTLED code, register settling, and the
# settling-guard sweep
python3 design/sar-logic/flow/probe_code_readout.py sar-logic-timing-gates-tie \
    --corner tt --temp -40 --vdd 3.63 --bits --rows 6

# the other five failing points, and the passing control
python3 design/sar-logic/flow/probe_code_readout.py sar-logic-timing-gates-tie \
    --corner ff --temp 27 --vdd 3.63 --bits --rows 6     # and ss/27/3.30,
    #                                                      fs/27/3.30,
    #                                                      fs/27/3.63,
    #                                                      tt/27/2.97
python3 design/sar-logic/flow/probe_code_readout.py sar-logic-timing-gates-tie \
    --corner tt --temp 27 --vdd 3.30 --bits --rows 6     # PASSES, dev = 1
```

## Conclusion

**All six failures are measurement artifacts of the same kind DR-0031
(`DR-0031-power-up-first-conversion-validity.md`, renumbered from DR-0029
by #354) already names as its
mechanism B — the `drdy` gate opening while the output register is still
updating — reproduced here on the `tie` deck, at its own corners. No
conversion at any of the six points produced a saturated code. Answer (b) of
issue #337's two candidate root causes; the design is not implicated.**

> **The settled code is 511 or 512 at every conversion of every one of the six
> points** (Evidence 3), i.e. within `tie_code_deviation`'s `max 1.0` bound
> and exactly the "either adjacent code answers an exact tie" behaviour the
> bound was written for. The **512** is read at the single accepted timepoint
> at which `drdy` crosses mid-rail — `dt after rise = 0` at all twelve
> occurrences — while the ten code bits are still crossing. The word decoded
> there is **0**, which is neither the code the register held nor the one it
> is loading (Evidence 4): at `tt_-40c_3.63v` conversion #7 the register goes
> from 512 (`1000000000`) to 511 (`0111111111`), and at the sampled instant
> `c9` has already fallen while `c8..c0` sit at 1.81 V against that point's
> own 1.815 V decode threshold. Both words are *correct*; only their
> superposition is 512 LSB from mid-scale.
>
> **The `drdy` gate cannot exclude that window, structurally** (Evidence 6):
> `sar_ctrl.v` has `assign drdy = ph[15]` and loads `c[9:0]` on the edge
> leaving `ph[14]` — the *same* clock edge — so the gate opens at the instant
> the data it gates begins to change. The generator's own comment on
> `btiedev` ("Gating on `drdy` restricts the measurement to windows where the
> register holds a completed conversion's result") is measurably false as
> written, and `ff_27c_3.63v` is the proof: its 512 is at conversion **#1**,
> where the pre-load word being read is the register's *power-up* value —
> precisely the code-0 artifact that comment says the gate removed.
>
> **A ≥ 0.25 ns settling guard removes all six, and moves no bound**
> (Evidence 5): every point reports 0 or 1 LSB at 0.25 ns and at every larger
> guard swept, with zero conversions above the `max 1.0` bound. That is the
> correction DR-0031 part 2 already specifies (window *and* guard), whose
> execution is issue **#327**.

**On DR-0029-tie-loop-decision-chatter: implicated as the cause of the
carry, not of the failure, and its supersede trigger is NOT fired.** The
chatter is why this deck sees major carries at all — a loop pinned on the
threshold lands on 511 on one conversion and 512 on the next, and 511 → 512
is a full ten-bit carry (Evidence 7). But `tie_code_deviation`'s *settled*
value is 0 or 1 LSB at all six points, so the chatter record's own condition
for being superseded — "a corner where `tie_code_deviation` actually fails"
— is not met by this grid: the check never failed on a settled code. The
chatter model, the stimulus and every bound stand.

**Nothing here requires a new decision record.** The disposition already
exists (DR-0031 part 2), it already names `tie_code_deviation` by name, and
its execution is already filed and claimed (#327). This document supplies the
`tie`-deck measurement that record predicted but had not taken, plus one fact
#327 should carry (Evidence 7): `tie` is the *most* exposed deck in the
family, not an incidental one.

## Evidence 1 — the committed logs already split the set, with no new run

`meas` reports *when* the maximum was attained and the record's result table
does not carry that column. Read from the 29 committed logs
(`corners/20260920-020802-2043286/*.log`, `grep '^dev_tie'`), reduced modulo
the deck's own 1 µs conversion period:

| `dev_tie` | points | `at` mod 1 µs | what that instant is |
|---:|---:|---|---|
| **512** | 6 | **62.89 … 63.23 ns** | the `drdy` **rise** (measured: 62.93 ns at `tt_-40c_3.63v`) |
| 1 | 16 | 125.30 … 125.63 ns | the `drdy` window **end** (measured: 125.37 ns) |
| 0 | 7 | 500 ns (= 8.5 µs, end of run) | never exceeded 0 |
| *(unscored)* | 1 | 399.66 ns | `sf_27c_2.97v`, the #332 abort instant |

(6 + 16 + 7 = the 29 scored points; the 16 remaining grid points are 15
3600 s timeouts and that one abort.)

The split is total: **no 512 lands anywhere but the rise instant, and no
1 lands anywhere but the window end.** A genuinely wrong settled code is flat
across its whole `drdy` window (so `MAX`'s reported `at` is the window's last
timepoint); a mid-update read is a spike at the rise. That is the same
signature issue #320's Evidence 1 found on the `ok` deck, and it is visible
without running anything.

## Evidence 2 — the power-up state rules out DR-0031's *other* mechanism

Also from the committed logs: every ngspice log carries an
`Initial Transient Solution` node dump, so the DUT's power-up flop state is
recoverable for all 29 completed points. Thresholding at each point's own
VDD/2:

| point | power-up `eng9..eng1` | power-up `c9..c0` | `dev_tie` |
|---|---|---:|---:|
| `ff_27c_3.63v` | `000000000` | 0 | 512 |
| `ss_27c_3.30v` | `000000000` | 0 | 512 |
| `fs_27c_3.30v` | `000000000` | 0 | 512 |
| `fs_27c_3.63v` | `000000000` | 0 | 512 |
| `tt_-40c_3.63v` | `000000000` | 1020 | 512 |
| `tt_27c_2.97v` | `000000000` | 0 | 512 |
| *(`sf_125c_2.97v`, passing)* | `111111111` | 0 | 1 |
| *(`ss_125c_3.63v`, passing)* | `111111111` | 0 | 1 |
| *(`fs_125c_3.63v`, passing)* | `111111000` | 127 | 0 |

**All six failing points power up with `eng == 0`** — the state DR-0031's
mechanism A (the invalid first conversion) *cannot* corrupt — while three of
the points carrying a garbage `eng` word pass. Mechanism A is therefore not
what produces the 512s here; the `ok` grid's correlation ran the other way
(all ten of its failures had `eng != 0`), which is why the two decks needed
separate measurements rather than one inference.

`tt_-40c_3.63v`'s power-up `c9..c0 = 1020` is worth noting separately: the
output register's power-up word is arbitrary too, and only the `eng` flags
are cleared by `endconv`. It does not affect this conclusion (that point's
512 is at conversion #7, not #1), but see Evidence 4's `ff_27c_3.63v` row for
the case where the power-up word *is* what gets decoded.

## Evidence 3 — instantaneous vs settled, all six failing points plus a control

`probe_code_readout.py … --bits --rows 6`, one full 8.5 µs run per point, the
deck's own `tran 5n 8.5u 0 5n`. "inst" is what
`meas tran dev_tie MAX v(tie_dev) FROM=0.1u` takes its maximum over; "settled"
is the same quantity at the **end** of each `drdy` window.

| point | settled code, conversions #1…#8 | worst **settled** \|code−512\| | worst **inst** | conversions reporting 512 | probe's own worst instant (grid's `at`) |
|---|---|---:|---:|---|---|
| `ff_27c_3.63v` | 512 512 512 512 512 512 512 512 | **0** | 512 | #1 | 1.062891e-06 (1.06289e-06) |
| `ss_27c_3.30v` | **511** 512 512 512 512 512 512 512 | **1** | 512 | #1, #2 | 2.063231e-06 (2.06323e-06) |
| `fs_27c_3.30v` | **511 511** 512 512 512 512 512 512 | **1** | 512 | #3 | 3.063014e-06 (3.06302e-06) |
| `fs_27c_3.63v` | **511** 512 **511** 512 **511** 512 **511** 512 | **1** | 512 | #1, #3, #5, #7 | 7.062974e-06 (7.06298e-06) |
| `tt_-40c_3.63v` | 512 512 512 512 512 512 **511** 512 | **1** | 512 | #7 | 7.062929e-06 (7.06293e-06) |
| `tt_27c_2.97v` | 512 512 **511** 512 **511** 512 **511** 512 | **1** | 512 | #4, #6, #8 | 8.063090e-06 (8.06309e-06) |
| *`tt_27c_3.30v` (PASSES, dev = 1)* | 512 512 512 **511** 512 512 512 512 | **1** | **1** | *(none)* | 4.125460e-06 (4.12546e-06) |

Each grid `at=` is reproduced at the *last* conversion of the run that
attains the maximum — `ngspice`'s `MAX` reports the last timepoint attaining
it, which is why a flat 1 LSB over a whole window (the control's row, and the
sixteen dev = 1 points of Evidence 1) is reported at the window **end** while
a spike is reported at the rise. Four of the seven agree with the grid's own
instant to every printed digit; `fs_27c_3.30v` and `fs_27c_3.63v` differ by
6 ps — one accepted timepoint — which is the expected fidelity for a
re-composed deck carrying a different `.control` block, not a different
event.

**The worst settled deviation anywhere in the six runs is 1 LSB**, i.e.
`tie_code_deviation` would PASS at all six points if it were evaluated on a
settled register. Forty-eight conversions were read out across the six; not
one settled on a saturated code. Code 0 never appears as a settled value, and
1024 is not representable in ten bits at all (the largest is 1023, which would
read 511 LSB, not 512) — so "the code landed on 0/1024" is refuted in both
halves.

## Evidence 4 — the decoded word is neither the old code nor the new one

`--bits` prints `c9..c0` per accepted timepoint. At the exact timepoint the
512 is attained (all voltages as printed, thresholded at that point's own
VDD/2):

**`tt_-40c_3.63v`, conversion #7 — the point issue #337 nominated.** The
register goes 512 → 511:

| t (s) | `c9` | `c8..c0` (all nine) | decoded | \|code−512\| |
|---|---:|---:|---:|---:|
| **7.0629293e-06** | **0.13 V** | **1.81 V** | **`0000000000` = 0** | **512** |
| 7.0629838e-06 | −0.03 V | 3.30 V | `0111111111` = 511 | 1 |

The nine lower bits are sitting **5 mV below** that point's 1.815 V decode
threshold at the sampled instant — mid-transition, together, because a
511 ↔ 512 carry moves all ten bits at once. The old word (512) and the new
word (511) are both within the bound; only the instant in between reads 0.

**The other three read out the same way**, with the carry direction and the
pre-load word varying:

| point | conv | carry | `c9` / `c8..c0` at the sampled instant | decoded |
|---|---:|---|---|---:|
| `ss_27c_3.30v` | #2 | 511 → 512 | 1.64 V (rising, vth 1.65) / 0.04 V | 0 |
| `tt_27c_2.97v` | #4 | 511 → 512 | 1.48 V (rising, vth 1.485) / 0.06 V | 0 |
| `ff_27c_3.63v` | #1 | **power-up 0 → 512** | 1.79 V (rising, vth 1.815) / −0.00 V | 0 |

Only two intermediate words are reachable on a 511 ↔ 512 carry — `0` when
`c9` has not yet caught up with `c8..c0`, and `1023` when it leads them —
reading 512 and 511 LSB respectively. All twelve occurrences across the six
runs landed on 0, which is why the grid's failures are *exactly* 512 with no
spread: the number is a property of the word boundary, not of an error.

`ff_27c_3.63v` is the special case worth stating plainly: **its 512 is the
pre-first-`drdy` code-0 artifact the generator's comment claims the `drdy`
gate removed.** The gate moved it from ~875 ns wide to ~4 ps wide; it did not
remove it, because `drdy` rises on the same edge that first loads `c[9:0]`.

## Evidence 5 — the settling guard, swept

What `meas tran MAX v(tie_dev)` would report if the `drdy` gate were held off
for a guard after each `drdy` rise. 0 ns is the committed `btiedev` gate.
"Wrong" is `tie_code_deviation`'s own bound, `> 1.0` LSB:

| guard (ns) | `ff_27c_3.63v` | `ss_27c_3.30v` | `fs_27c_3.30v` | `fs_27c_3.63v` | `tt_-40c_3.63v` | `tt_27c_2.97v` | conversions wrong, all six |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **0.00** | **512** | **512** | **512** | **512** | **512** | **512** | **12** |
| 0.25 | 0 | 1 | 1 | 1 | 1 | 1 | **0** |
| 0.50 | 0 | 1 | 1 | 1 | 1 | 1 | 0 |
| 1.00 | 0 | 1 | 1 | 1 | 1 | 1 | 0 |
| 2.00 | 0 | 1 | 1 | 1 | 1 | 1 | 0 |
| 5.00 | 0 | 1 | 1 | 1 | 1 | 1 | 0 |

The guard is not a tuning knob: 0.25 ns and 5 ns give the identical answer at
every point, so there is no value in between that changes a verdict. The
window it has to clear is small — the last `c<i>` threshold crossing after
`drdy`'s own crossing measures **0.0002 … 0.055 ns** across the twelve
occurrences, against `ok`'s measured 0.186–0.199 ns — so DR-0031's already-
ratified **≥ 0.25 ns** covers the `tie` deck with ≥ 4.5x margin and needs no
`tie`-specific value.

**What the guard does not do**: it does not relax `tie_code_deviation`. The
`max 1.0` bound is untouched, and a conversion that really did saturate would
move the *settled* code and be caught by 512 LSB rather than 1.

## Evidence 6 — the gate opens on the edge that loads the data, structurally

Not an inference from waveforms. From `design/sar-logic/rtl/sar_ctrl.v`:

```verilog
assign drdy = ph[15];                 // line 194
ph[15] <= ph[14] & ~start;            // line 171
always @(posedge clk) if (ph[14]) begin c9_r <= q9; … c0_r <= q0; end
assign c9 = c9_r;                     // … c0
```

`ph[15]` and `c9_r…c0_r` are loaded by the **same** rising clock edge — the
one leaving `ph[14]` — and the RTL's own comment says so ("Loads {q9..q0} on
the edge leaving ph14 (visible from ph15, the same phase drdy asserts on)").
A measurement gated on `v(drdy) > vth` therefore opens at the instant its
data starts moving, and closes ~62.5 ns later; the only part of the window in
which the register is *not* settled is the part the gate is guaranteed to
include. This is the same structural fact `sim/tests/test_probe_code_readout.py`
already pins for the `ok` deck (`ResetStructureTests`), read one register
further along.

## Evidence 7 — why `tie` is the family's most exposed deck, and the control

Counting a **carry** as a conversion whose loaded word differs from what the
register held (the power-up word standing in for conversion #1), over the
seven full-window runs of Evidence 3 — 56 conversions:

| point | carries | of those, reporting 512 |
|---|---:|---:|
| `ff_27c_3.63v` | 1 | 1 |
| `ss_27c_3.30v` | 2 | 2 |
| `fs_27c_3.30v` | 2 | 1 |
| `fs_27c_3.63v` | 8 | 4 |
| `tt_-40c_3.63v` | 3 | 1 |
| `tt_27c_2.97v` | 7 | 3 |
| `tt_27c_3.30v` *(passes)* | 3 | **0** |
| **total** | **26** | **12** |

Two readings, and both matter for issue #327:

* **512 is reported at 12 of the 26 carries and at 0 of the 30 non-carry
  conversions.** A carry is necessary; being *caught* is a coin-flip decided
  by whether the solver happened to accept a timepoint inside a ≤ 0.055 ns
  window. `fs_27c_3.63v` shows both outcomes inside one run — it carries on
  all eight conversions and reports four of them — and `tt_27c_3.30v` is the
  clean control: it carries three times, reports none, and **passes the grid
  with dev = 1**. Whether this deck fails `tie_code_deviation` is a property
  of the accepted-timepoint grid, not of the converter.
* **The `tie` loop carries far more often than any other loop in the family.**
  `ok`/`lt`/`xl`/`bad` ramp through mid-scale once per run, so each sees the
  511 ↔ 512 major carry exactly once (issue #320 found it at `ok`'s
  conversion #6). `tie` sits *on* the boundary, so DR-0029-tie-loop-decision-
  chatter's reversals decide, per conversion, which adjacent code is latched —
  and every flip is a full ten-bit carry. Measured here: up to 8 carries in 8
  conversions. The chatter does not cause the misreading; it maximises the
  number of opportunities for it.

## What this investigation does NOT establish

- **It is not a scored PVT result.** `probe_code_readout.py` replaces the
  manifest's `meas` block with a raw print and writes nothing under
  `records/`/`corners/`/`netlist-snapshots/`. The grid this document
  interprets is still `20260920-020802-2043286`, unedited. Re-scoring the
  `tie` deck belongs to #327's corrected-measurement grid.
- **It does not fix anything.** `btiedev`'s gate, the `FROM=0.1u` window,
  `sar_ctrl.v` and every `tb.json` bound are **unchanged in the tree**. The
  correction is DR-0031 part 2's, and its execution is issue #327 — which
  covers this deck by name and was already claimed when this was written.
  Landing the same edit from two issues would be the conflict, not the fix.
- **It does not clear the 16 points the grid never scored.** Fifteen timed
  out at 3600 s and one aborted (#332, a separate mechanism, separately
  filed). This document explains six failures, not the grid's `ERROR`
  verdict.
- **It says nothing about silicon.** ngspice's `Initial Transient Solution`
  is a DC operating point of cross-coupled latches, a plausible stand-in for
  an unknown power-up state and not a distribution over real ones; and the
  mid-update decode is a property of *this measurement*, which has no
  silicon counterpart at all. What a real SAR's consumer must do — read
  `c[9:0]` after `drdy`, not on it — is a consequence of Evidence 6 that this
  deck was never the right instrument to state.
- **It does not re-open DR-0027.** That record's accepted one-hot hazard
  budget is a different measurement on a different net, and DR-0031 already
  records why revising a bound is the wrong response to this class of
  finding.

## Environment

- PDK: `gf180mcuD` @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (the pin in `sim/toolchain.json`, and the one
  `records/20260920-020802-2043286.md` was taken at)
- ngspice: `ngspice-46`, compiled with the KLU direct linear solver — this
  deck still runs on SPARSE 1.3 (`option klu` is not set; see
  `sim/sar-logic-timing-gates/investigations/20260918-issue-308-klu-solver-evaluation.md`)
- Python: 3.12.3
- Deck: `sim/sar-logic-timing-gates-tie/testbench/` as committed, composed
  through `sim/harness`'s own `compose_deck`, so the PVT preamble, corner
  sections and `sar_ctrl_a` subckt are the ones `sim/run_corners.py` uses.
  The probe replaces only the `.control` measurement block, and adds one
  `btieexp tie_exp 0 V = 512` reference source to its own temporary deck.
- Tree: `feature/issue-337` on top of `93ddfe3`; the only addition the runs
  above depend on is the `--exp-const` path in
  `design/sar-logic/flow/probe_code_readout.py`.
- Host: 8 cores, shared with other agents' concurrent ngspice workloads
  throughout (load average 8–14 for the whole session). **No wall-clock figure
  appears anywhere above**, deliberately: every quantitative claim is a code,
  a voltage, a threshold crossing, a settling time or a conversion count.
