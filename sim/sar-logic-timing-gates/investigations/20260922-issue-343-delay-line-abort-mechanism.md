# Investigation 20260922-issue-343: the delay-line decks' step control collapses because the DUT's gate input hangs on the ideal lossless line's termination node — not because of the line's own numerics

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — a single-corner, truncated-window
A/B answering issue #343: **is the ideal lossless transmission line the
mechanism behind the `Timestep too small` aborts in
`sim/sar-logic-timing-gates-{lt,xl,bad}/`?**

Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only `records/` tree is never edited. **Nothing in any deck, manifest,
comparator model, `tran` line or `tb.json` bound is changed by this
document.** The only code it carries is measurement-only flags on the probe
(`--delay-line`, `--delay-line-rc`, `--save-probed-only`) which write nothing
into the tree, plus one classification fix in the probe itself (§6).

## Conclusion

**Confirmed, with a correction to which half of the structure does the
damage.** The ideal lossless transmission line *is* the mechanism, but not
through its own model numerics: what is lethal is the **pairing** of that
line with the DUT's bare standard-cell `cmp` gate input sitting directly on
the line's far-end termination node.

> Measured at `lt` / `ss` / 27 °C / 2.97 V — the `lt` grid's earliest abort
> (abort at 1.28656 µs on `vvdd_gate#branch`, per the raw-log audit in
> `20260921-issue-303-delay-line-decks-abort-mid-transient.md` §3.1; the
> record `sar-logic-timing-gates-lt/records/20260920-182006-2422cac.md`
> itself still prints that point as `PASS`, which is #341's defect and not
> this investigation's business):
>
> - The **committed deck** takes **754,946 accepted timepoints** to cover
>   1.5 µs, and its median accepted timestep **decays monotonically through
>   the whole run** — 9.20 ps in the first 200 ns to **0.15 ps** in the
>   1.4 µs bin, a **61× collapse that is still falling** when the window ends
>   (§2, Evidence 1). It bottoms out below 1 fs on **972** accepted steps and
>   below 0.1 fs on **15**, the first at 320 ns.
> - Keeping that line **byte-identically** — same `z0=50`, same `td=40n`,
>   same matched 50 Ω termination — and interposing **#296's own
>   `1 kΩ / 100 fF` network between the termination node and the DUT `cmp`
>   port** stops the collapse dead: the median accepted step is **flat at
>   34–56 ps** for the whole window (1.6× spread, no trend), **227× the
>   committed deck's** by the 1.4 µs bin, and the run costs **16,282**
>   timepoints instead of 754,946 (§2 and §3, arm B).
> - The **external control** — `sim/sar-logic-timing-gates-ok/`, the
>   ratified T-line-free sibling deck, run unmodified at the same corner over
>   the same 1.5 µs — costs **1,263** timepoints at a flat 242 ps median
>   step. That is the regime every substituted arm returns to, and it is
>   **598×** cheaper than the committed `lt` deck for identical simulated
>   time.
>
> That single substitution changes nothing about the line. It moves the gate
> capacitance off the line's termination node — and that is the whole
> difference between a deck whose step control diverges and one whose does
> not.

**The load-bearing sentence committed in all three delay-line manifests and
records is wrong in its second clause.**
`sim/sar-logic-timing-gates-lt/testbench/tb.json` (and `-xl`, `-bad`, and
each deck's records) says:

> Issue #296's comparator-output-slew fix does NOT apply to this loop:
> `lt`'s comparator drives a matched 50 ohm terminated transmission line,
> **not a bare gate input**, so it was never subject to the zero-time-step
> abort #296 fixed.

The comparator does drive a matched line. But the **DUT's `cmp` port is a
bare gate input** — ten `gf180mcu_fd_sc_mcu7t5v0__aoi21_1` `A2` inputs (the
cell's pin order is `A1 A2 B ZN VDD VNW VPW VSS`, and `cmp` is the second net
on all ten instance lines), a pure capacitance — and it hangs directly off
`lt_cmpo`, which is the line's
*termination node*. The line is matched into the 50 Ω resistor on that node
and is **not** matched into the capacitance in parallel with it; being
lossless, it never attenuates what that mismatch returns. #296's mechanism was
not avoided by the delayed loops. It was **relocated 40 ns downstream**.

**The aborts and the timeouts are the same phenomenon.** A deck that needs
754,946 accepted timepoints for 1.5 µs needs of order 4 × 10⁶ for the ratified
8.5 µs *even if the collapse stopped* — and it does not stop. That is why 35
of `lt`'s 45 points hit the 7200 s cap and why the 10 that reached a verdict
aborted: they are the same trajectory, read at two different places.

**A remedy is stated and costed in §5. None of it is landed here**, because
extending `cmp_out_rc` to the delayed loops changes what `abs_err_delay_40ns`
/ `_50ns` / `_70ns` measure by +69 ps, and DR-0010's bisected 50 ns/52 ns
bracket is measured through these lines — so it belongs to a decision record,
not to an investigation.

## 1. How to re-run everything below

Every row in every table is produced by one of these commands. `--until`,
`--delay-line`, `--delay-line-rc`, `--save-probed-only` and `--chatter` all
write nothing: the committed decks, their stimuli, their comparators, their
`tran` lines and their bounds are untouched by all of them.

```bash
P=design/sar-logic/flow/probe_cmp_convergence.py
C="sar-logic-timing-gates-lt --corner ss --temp 27 --vdd 2.97 --until 1.5u --chatter"

# A  the committed deck, unsubstituted (§2 and §3, arm A)
python3 $P $C --probe --tail 30 --keep sim/.work/issue-343/A-baseline
# B  the line UNTOUCHED, #296's network between it and the DUT gate (§3, arm B)
python3 $P $C --probe --tail 20 --delay-line-rc 1k,100f --keep sim/.work/issue-343/ideal-rc
# C  a 40-section LC artificial line of the same z0 and the same total td
python3 $P $C --probe --tail 20 --delay-line lumped  --keep sim/.work/issue-343/lumped
# D  the matched line's far-end Thevenin equivalent, no transport at all
python3 $P $C --probe --tail 20 --delay-line series  --keep sim/.work/issue-343/series
# E  no transport, ideal buffer onto the same shunt load (the pre-#296 topology)
python3 $P $C --probe --delay-line none --save-probed-only --keep /tmp/i343/none

# F  a SECOND corner of the same deck (its grid abort: 1.38481 us)
python3 $P sar-logic-timing-gates-lt --corner ff --temp 125 --vdd 3.30 \
    --until 1.45u --probe --chatter --delay-line-rc 1k,100f --save-probed-only
# G  a SECOND deck (xl, td=50n; its grid abort at this corner: 1.42592 us)
python3 $P sar-logic-timing-gates-xl --corner ss --temp 27 --vdd 2.97 \
    --until 1.50u --probe --chatter --delay-line-rc 1k,100f --save-probed-only

# OK  the T-line-free control deck, SAME corner, SAME truncated window, no
#     substitution of any kind -- the floor this whole comparison is read
#     against (34 s wall; every arm above shared one core with others)
python3 $P sar-logic-timing-gates-ok --corner ss --temp 27 --vdd 2.97 \
    --until 1.5u --probe --chatter --save-probed-only \
    --keep sim/.work/issue-343/ok-control
```

The per-timepoint tables are recomputed from a `--keep` log with
`probe_cmp_convergence._probe_tables`, the same parser `--chatter` uses, so a
reader re-derives the numbers rather than trusting a transcription:

```python
import sys, statistics; sys.path.insert(0, "design/sar-logic/flow")
import probe_cmp_convergence as P
d = P._probe_tables(open("sim/.work/issue-343/A-baseline/probe_ss_27c_2.97v.log").read())["lt.1"]
h = [(d[i][0], d[i][0] - d[i-1][0]) for i in range(1, len(d)) if d[i][0] > d[i-1][0]]
bins = {}
for t, dt in h: bins.setdefault(int(t * 1e9 // 200) * 200, []).append(dt)
print({k: round(statistics.median(v) * 1e12, 2) for k, v in sorted(bins.items())})
```

The deck is the one the record was written from: `sha256` of
`sim/sar-logic-timing-gates-lt/testbench/tb_sar_logic_timing_gates_lt.spice`
is `ad6b8bd63cb6043ee1deb05afe82c12fe0a49eac83ff5f7c919bdb42fa87cc9e`, which
is the "Testbench netlist sha256" line of
`records/20260920-182006-2422cac.md`, and `--delay-line ideal` re-emits the
delay element with its own `z0`/`td` literals, so the A arm's composed
testbench fragment is **byte-identical** to the committed file.

## 2. Evidence 1 — the committed deck does not abort in this window, and that is the finding

**Stated first because it is the one place this investigation does not
reproduce what the grid recorded.** The `lt` grid's `ss_27c_2.97v` point
aborted at t = 1.28656 µs (`20260921-issue-303-delay-line-decks-abort-mid-transient.md`
§3.1, read off the raw ngspice logs). Arm A — the same deck, the same corner, the same
`tran` step and max-step, stop time truncated to 1.5 µs — **completed**:

```
RESULT  : completed, no 'Timestep too small' abort (754946 timepoints)
```

It completed the way a car "completes" a journey in first gear. The accepted
timestep, binned in 200 ns windows over the run:

| arm | 0 | 200 | 400 | 600 | 800 | 1000 | 1200 | 1400 ns |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **A committed (ideal lossless line)** | **9.20** | **0.73** | **0.35** | **0.24** | **0.19** | **0.17** | **0.17** | **0.15 ps** |
| B ideal line + `1k/100f` at the far end | 56.00 | 41.17 | 39.95 | 47.19 | 47.46 | 46.23 | 37.04 | 34.08 ps |
| C lumped LC line, same `z0`/`td` | 393.97 | 407.32 | 299.24 | 303.03 | 304.59 | 320.34 | 1022.23 | 370.10 ps |
| D series Thevenin, no transport | 226.34 | 314.29 | 242.35 | 260.42 | 268.56 | 241.58 | 281.18 | 281.41 ps |
| *`ok` deck, no substitution — the control* | *212.20* | *314.29* | *226.48* | *260.55* | *254.07* | *230.44* | *281.13* | *223.13 ps* |

Arm A is the only row with a trend. It is **monotone decreasing at every
bin**, 61× over the measured window, with no sign of a floor. Arms B, C and D
are flat to within 1.6×, 1.4× (excluding one high outlier bin) and 1.4×
respectively — i.e. their step control is in a steady state and arm A's is
not. The last row is the `ok` deck itself, unsubstituted, at the same corner
and the same truncated window: it is flat to within 1.5×, and lands on the
**same 212–314 ps band as the two no-transport substitutions**, which is what
a healthy step-size trajectory for this DUT looks like.

How close arm A gets to the give-up threshold, in accepted steps (ngspice
abandons the run at `timestep = 6.25e-21` in the grid's own aborts):

| accepted steps below | count | first at |
|---|---:|---:|
| 10 fs | 21,685 | 160.15 ns |
| 1 fs | 972 | 320.11 ns |
| 0.1 fs | 15 | 718.95 ns |
| smallest accepted step anywhere in the run | **3.0 × 10⁻¹⁷ s** | — |

So arm A repeatedly descends to within four orders of magnitude of the abort
floor and recovers, from 320 ns onward. **Whether a given run crosses the
floor is the tail of a continuous quantity, not a separate event** — which is
why the grid aborted 10 of 45 points, timed out 35, and scored none: the
`lt` grid's aborts land at 1.29–2.37 µs, exactly where this trajectory is
heading.

**The contrast with the deck this one is a copy of.**
`sim/sar-logic-timing-gates-ok/` — same DUT, same single instance, same supply
source, same 8.5 µs window, same comparator, differing only in having no
transmission line — completed 45 of 45 at ~132 core-s per point
(`sim/sar-logic-timing-gates-ok/testbench/tb.json`). Run here at **arm A's own
corner and arm A's own truncated window**, with no substitution of any kind,
it takes **1,263 accepted timepoints** where arm A takes **754,946** — a
**598×** ratio for the identical 1.5 µs of simulated time (command in §1;
`sim/.work/issue-343/ok-control/`). The comparison is quoted in timepoints
rather than seconds deliberately: this host's arms shared one core, and no
wall-clock number here is a deck property (§7).

**Why the abort itself does not reproduce here is not established**, and this
document does not claim it. The candidates it does not separate are: the
truncated stop time (`tran 5n 1.5u` vs `5n 8.5u`; #332's Evidence 1 found
truncation *neutral* on the `tie` deck, but that deck aborts at 400 ns, well
inside both windows), the probe's control block versus `run_corners.py`'s
(`--save-measured-vectors` retention, measured *non*-neutral for this deck
family in `20260917-issue-303-transient-cost-and-retention.md`), and the run
host. **None of them is load-bearing for the conclusion**, because the
conclusion is read off the step-size trajectory — a quantity arm A shares with
the aborting grid points and no substituted arm shares with either.

## 3. Evidence 2 — the one-variable A/B: the line is necessary, and not sufficient

Every arm below is the same deck, the same corner, the same stop time. Only
the path from the comparator decision node `lt_cmpi` to the DUT-facing node
`lt_cmpo` differs. `ret` is retention: `full` = every node kept (the probe's
default), `probed` = `--save-probed-only`.

| arm | what it is | ret | timepoints | median `h` | min `h` | result |
|---|---|---|---:|---:|---:|---|
| **A** | **committed: `tltd … z0=50 td=40n` + `rltterm 50`, DUT gate on `lt_cmpo`** | full | **754,946** | **0.200 ps** | **3.0e-17** | completes 1.5 µs |
| **B** | **the SAME line, terminated in the SAME 50 Ω, DUT gate reached through `1k`/`100f`** | full | **16,282** | **43.38 ps** | 1.6e-13 | completes 1.5 µs |
| B′ | as B | probed | 14,468 | 44.10 ps | 1.6e-13 | completes 1.35 µs |
| C | 40-section LC artificial line, same `z0`, same total `td` | full | 3,339 | 317.15 ps | 1.0e-12 | completes 1.5 µs |
| C′ | as C | probed | 3,062 | 312.88 ps | 1.0e-12 | completes 1.35 µs |
| D | far-end Thevenin equivalent (`Z0/2` series), no transport | full | 1,243 | 255.49 ps | 1.0e-12 | completes 1.5 µs |
| D′ | as D | probed | 1,134 | 255.49 ps | 1.0e-12 | completes 1.35 µs |
| E′ | no transport: ideal buffer onto the same shunt load | probed | 1,137 | 255.08 ps | 1.0e-12 | completes 1.35 µs |
| *ok* | *the T-line-free `ok` deck itself, no substitution — the control* | *probed* | *1,263* | *242.35 ps* | *1.0e-12* | *completes 1.5 µs* |

Five readings, in decreasing order of confidence.

- **A vs B is a one-variable A/B and it decides the issue.** B's composed
  deck keeps `tltd lt_cmpi 0 lt_cmpt 0 z0=50 td=40n` and
  `rltterm lt_cmpt 0 50` — the line, its impedance, its delay and its matched
  termination are all bit-for-bit what the committed deck has. The only change
  is that the DUT's `cmp` port now reaches that node through
  `rltcmps lt_cmpt lt_cmpo 1k` / `cltcmpl lt_cmpo 0 100f` instead of being
  wired onto it. That alone is worth **46× the timepoints and 227× the median
  step in the last bin**, and it converts a diverging step-size trajectory
  into a flat one. **The line's own numerics cannot be the mechanism: the line
  is still there in B.**
- **The line is nonetheless necessary.** A is the only arm that keeps the
  line *and* the bare gate input on its termination node, and it is the only
  arm in the collapse regime. Removing the line (D, E′) or replacing it with a
  band-limited one (C) also removes the collapse, but each of those changes
  the transport as well, so on their own they do not separate "the line" from
  "what the line's far end is connected to". B does.
- **The `ok` row is the external control, and every substituted arm lands on
  it.** It is not an arm of this A/B at all — it is the committed, ratified,
  T-line-free deck, run unmodified at arm A's corner over arm A's window. It
  costs 1,263 timepoints at a flat 242 ps median step, i.e. within 6 % of
  arms D and D′ and within 31 % of arm C. So the substitutions are not
  producing some new, unphysically-easy circuit: they are returning this DUT
  to the step-size regime its own ratified sibling already runs in, and arm A
  is the outlier by nearly three orders of magnitude.
- **E′ rules out "an un-slewed edge into a gate capacitance" as a sufficient
  cause on its own.** E′ drives the DUT gate from an ideal unity buffer: its
  steepest accepted-step move on `v(lt_cmpo)` is the full 2.97 V in 10 ps —
  **297 V/ns**, a rail-to-rail step onto the same bare gate input — and it
  completes with a flat 255 ps median step. So #296's mechanism *in
  isolation* is not what these decks are dying of; it is #296's mechanism
  **presented at the far end of a lossless line**, where the mismatch between
  the 50 Ω termination and the gate capacitance on the same node is returned
  into the line undamped, forever.
- **Retention is neutral for this comparison.** B/B′, C/C′ and D/D′ are the
  same arms run with full retention and with `--save-probed-only`, and agree
  on the median step to 2 % (43.38 vs 44.10 ps), 1.4 % (317.15 vs 312.88 ps)
  and 0.0 % (255.49 vs 255.49 ps). The timepoint-count differences are the
  0.15 µs of extra window, not the retention setting.

**Chatter is controlled for, and is not the discriminator.** The probe's
`--chatter` summary over the same runs:

| arm | decision reversals | mid-rail dwell | peak \|i(vvdd_gate)\| |
|---|---:|---:|---:|
| A committed | 9 | 1.505 ns | 2.468 mA |
| B ideal line + far-end RC | 9 | 2.869 ns | 2.579 mA |
| C lumped LC line | 9 | 28.866 ns | 2.270 mA |
| D series Thevenin | 23 | 0.000 ns | 2.284 mA |

A and B have the **same number of decision reversals** and B has *more*
mid-rail dwell, yet B's step control is flat and A's diverges. That is the
same negative result #332 reached on the `tie` deck from the other direction —
"this deck chatters more" does not predict convergence — and it is why the
mechanism is located in the delay path's topology rather than in the
comparator's behaviour.

## 4. Evidence 3 — it is not one corner and not one deck

Both rows below are the `--delay-line-rc 1k,100f` substitution (arm B's
variable) at a point whose **committed grid run aborted**. The abort times in
column 2 come from the raw-log audit of those grids
(`20260921-issue-303-delay-line-decks-abort-mid-transient.md` §§3.1–3.2), not
from the records' own verdict tables — the records print these points as
`PASS`, which is #341's scoring defect and is out of scope here:

| deck, corner | grid run's actual outcome at this point | with `1k/100f` at the far end | timepoints | median `h` | trend |
|---|---|---|---:|---:|---|
| `lt` @ `ff`/125 °C/3.30 V | abort @ **1.38481 µs**, `vvdd_gate#branch` | **completes 1.45 µs** | 15,096 | 36.94 ps | 47.10 → 34.92 ps (1.35×) |
| `xl` @ `ss`/27 °C/2.97 V (`txld … td=50n`) | abort @ **1.42592 µs**, `vvdd_gate#branch` | **completes 1.50 µs** | 14,079 | 32.65 ps | 58.03 → 35.59 ps (1.63×) |

Both run past the time their own committed grid point aborted at, with a flat
step-size trajectory in the same 33–58 ps band arm B sits in. The control for
these two rows is the **committed grid run**, not an in-session run of the
unsubstituted deck (§7 says so plainly): the two in-session controls were
started (`/tmp/i343/lt-ff-ideal`, `/tmp/i343/xl-ideal`) and killed at
t = 0.442 µs and 0.463 µs after 2,415 s each, sharing this host's single core with the two
substituted arms they were the control for. They are reported as
`FAILED — … measured nothing`, which is §6's classification fix doing exactly
its job: neither is evidence of anything, in either direction.

## 5. The answer to the acceptance criteria — the remedy, costed, not landed

The issue asks for "a stated, costed remedy (and a decision record if the
remedy changes what `cmp_delay` measures)". Here is the enumeration, so a
reader can check the list is exhaustive rather than convenient.

| candidate | what it does | measured cost/benefit | why it is not landed here |
|---|---|---|---|
| **R1 — extend `cmp_out_rc` to the delayed loops** (recommended) | in `gen_sar_logic._loop`, emit the line into its own node terminated in 50 Ω and feed the DUT `cmp` port through the same `1 kΩ`/`100 fF` network #296 already gives `ok`/`tie` | **46× fewer timepoints, 227× the median step in the last bin, flat trajectory** (arm B). Reproduced at a second corner and on a second deck (§4). ~4 lines of generator change | It adds `0.693·τ = 69 ps` of lag to the comparator-to-latch path, i.e. the loops realise 40.069/50.069/70.069 ns instead of 40/50/70. DR-0010's bracket was bisected to **50 ns exact vs 52 ns = 1 LSB**, so 69 ps is 3.5 % of the bracket's own 2 ns granularity and does not move the bracket point — but it does change what `abs_err_delay_50ns` measures, and CLAUDE.md puts that in a decision record, not an investigation |
| **R1b — R1, with `td` reduced by the RC's own delay** | as R1 but `td=39.931n`/`49.931n`/`69.931n`, so the *total* comparator-to-latch delay is the ratified number to the picosecond | same as R1; one extra generator line and a stated rounding | Same reason: it still changes the emitted deck for three ratified experiments. It is the variant that leaves DR-0010's bracket arithmetically untouched, and is the one a superseding record should cost first |
| R2 — replace the ideal line with a lumped LC line of the same `z0`/`td` | arm C | **226×** fewer timepoints than A — better than R1 | It changes the *transport*, not just what hangs off its end: a 40-section ladder is band-limited at ~318 MHz, and the deck's own `--chatter` readout moves from 1.5 ns of mid-rail dwell to **28.9 ns** (19×). It buys convergence by changing the edge the standard cell is asked to chase, i.e. by changing what the loop measures. R1 leaves the line alone |
| R3 — an `ltra`-style lossy line | not measured here (§7) | — | Would tell us whether the T-element's *own* model is implicated; it is not needed to decide the issue, because B keeps the T-element and converges |
| R4 — raise the per-point timeout / move to a batch fleet | nothing about the deck | extrapolating arm A's *whole-run* rate linearly (754,946 accepted timepoints for 1.5 µs) the ratified 8.5 µs needs of order **4 × 10⁶ accepted timepoints even if the collapse stopped** — and if it does not, the 1.4 µs bin's own 0.15 ps median step puts the remaining 7 µs alone at of order **5 × 10⁷**. 10 of 45 `lt` points show it does not stop: they cross ngspice's floor before 2.4 µs | Not a remedy. A bigger cap converts timeouts into aborts, not into results |
| relax any `tb.json` bound, `tran` parameter, comparator model or `cmp_out_rc` value to make a result pass | — | — | Forbidden by CLAUDE.md and by the issue. Not attempted; nothing in the tree is changed by this document |

**What a superseding decision record has to decide**, if one is written: R1 vs
R1b (accept +69 ps, or absorb it into `td`), and whether the three delay-line
records
(`sar-logic-timing-gates-lt/records/20260920-182006-2422cac.md`,
`-xl/records/20260921-021359-2422cac.md`, and `bad`'s when it is run) plus
the `tb.json` note quoted in the Conclusion are amended or superseded, since
that note's stated reason for exempting these loops from #296 is the clause
this investigation falsifies.

## 6. One change this document does carry, and why it is not a fix

`probe_cmp_convergence.py`'s only failure test used to be the
`Timestep too small` regex, so **an ngspice that died for any other reason
printed `RESULT : completed`** — issue #341's defect class, in the instrument
rather than in `sim/harness/runner.py`. It was found the hard way: an
`--delay-line lossy` arm of this investigation ran out of output memory
(`Error: memory required (608134128 Bytes) is more than memory available
(607293440 Bytes)!` → `ERROR: fatal error in ngspice, exit(1)`) at
t = 3.82041 × 10⁻⁷ s of a 1.5 µs transient and reported "completed" — the
scratch driver's own log for that batch still records it as
`lossy exit=0`. The probe now
classifies three outcomes (`0` reached the stop time / `1` aborted / `3` died
measuring nothing) and requires ngspice to have reached the end of its own
control block. This is a correctness fix to a debugging instrument that writes
nothing into the tree; it does not touch `sim/harness/runner.py` (#341) and it
cannot change any committed record.

`--save-probed-only` exists for the same incident: it keeps only the vectors
the probe tables read. Measured at this corner, with `/usr/bin/time -f
'%M KB'`: every `--save-probed-only` arm peaked between **42 MB and 51 MB**
resident, while the full-retention unsubstituted run in the same batch
(`/tmp/i343/committed`, `--until 1.35u`) was at **605 MB and still climbing**
when it was killed at 4,717 s having reported nothing. Arm A, also full
retention, left a **134 MB** raw log behind for its 754,946 timepoints.
`--save-probed-only` changes nothing the solver computes, and §3's `B/B′`,
`C/C′`, `D/D′` pairs are the measurement that says so.

## 7. What this investigation does NOT establish

- **It is not a scored PVT result.** `--until`/`--delay-line`/
  `--delay-line-rc`/`--save-probed-only` runs answer "how is the step control
  behaving", not "what does the deck measure". Only `sim/run_corners.py`
  writes evidence, and no record in this tree is amended or edited.
- **It did not reproduce the abort itself.** Arm A completed 1.5 µs where the
  grid's same point aborted at 1.28656 µs (§2). The conclusion rests on the
  step-size trajectory, which arm A shares with the aborting grid points and
  no substituted arm shares; a reader who wants the abort itself reproduced in
  the probe needs a full 8.5 µs arm-A run, which this host could not afford.
- **It is one corner for the full A/B** (`ss`/27 °C/2.97 V), plus one extra
  corner and one extra deck for the decisive arm only (§4). It is not a sweep,
  and it says nothing about which corners abort.
- **The `bad` deck (`tbadd … z0=50 td=70n`) was not run at all.** It has no
  committed grid, and no arm here touches it. It carries the same structure —
  ideal lossless line, matched 50 Ω termination, DUT gate input on that same
  node — so the mechanism applies to it *by construction*, but that is an
  inference from the netlist, not a measurement.
- **The `ltra` lossy-line arm (the issue's suggested step 3) was not
  completed.** Two attempts were cut: the first died for want of output memory
  (§6) and the second was killed to give the single available core to the
  control. It is not load-bearing — arm B keeps the ideal T-element and
  converges, which already refutes "the T-element's own numerics" without it —
  but it means this document cannot say whether a *lossy* line alone would
  suffice.
- **It does not instrument ngspice's lossless-line model.** "The 50 Ω
  termination is matched to the resistor and not to the gate capacitance on
  the same node, and a lossless line never attenuates what that mismatch
  returns" is a reading of the topology and of the `T`-element's definition,
  not an instrumented per-iteration residual. What *is* measured is everything
  that reading has to explain: the monotone step collapse with the line and
  the bare gate together, its complete absence with the line and a buffered
  gate, and its absence with no line at all.
- **It does not reopen #296 or #310, and it does not touch #341.** #296's
  network is used here unmodified and at its committed values; #310's
  five-instance mechanism is excluded by instance count (one `sar_ctrl_a` per
  per-loop deck, pinned by
  `sim/tests/test_sar_ctrl_gates_tb.py::SharedSupplyRowTests`); the harness
  scoring defect is #341's, fixed separately in `e61fa8d`.
- **No wall-clock figure is quoted as a deck property.** The host capped this
  agent's whole process scope at one core (`cpu.max 100000 100000`) for the
  entire session, and several arms shared it. Every quantitative claim the
  conclusion rests on is an accepted timestep, an accepted-timepoint count, a
  voltage or a current. The four seconds-figures that do appear (§1's "34 s"
  re-run hint, §4's two 2,415 s kill points, §6's 4,717 s) are contended wall
  times reported so a reader knows what was cut and roughly what a re-run
  costs — **none of them is comparable to a `records/` per-point cost**, and
  none of them is load-bearing.

## Environment

- PDK: `gf180mcuD` @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (the pin in `sim/toolchain.json`, and the one
  `records/20260920-182006-2422cac.md` was taken at)
- ngspice: `ngspice-46`; these decks run on SPARSE 1.3 (`option klu` is not
  set — see
  `sim/sar-logic-timing-gates/investigations/20260918-issue-308-klu-solver-evaluation.md`)
- Python: 3.14.7
- Decks: `sim/sar-logic-timing-gates-lt/testbench/tb_sar_logic_timing_gates_lt.spice`
  (`sha256 ad6b8bd6…cc9e`, the record's own),
  `sim/sar-logic-timing-gates-xl/testbench/tb_sar_logic_timing_gates_xl.spice`
  and, as the external control,
  `sim/sar-logic-timing-gates-ok/testbench/tb_sar_logic_timing_gates_ok.spice`
  — all as committed, composed through `sim/harness`'s `compose_deck` so the
  PVT preamble, corner sections and `sar_ctrl_a` subckt are the ones
  `sim/run_corners.py` uses
- Tree: `773f906` (`origin/main` at the time of the runs)
- Host: 8 cores, but the agent scope was cgroup-capped to **one** core
  (`cpu.max 100000 100000`) throughout
