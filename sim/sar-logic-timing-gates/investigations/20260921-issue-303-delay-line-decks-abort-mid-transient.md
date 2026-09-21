# Investigation 20260921-issue-303: the delay-line per-loop decks never reach the end of the ratified transient, and the harness scores them as if they did

Not a `sim/run_corners.py` evidence record (no PVT grid is scored here, and
nothing below is citable as a spec claim) — an audit of the raw ngspice logs
belonging to two grids that *are* records:

- `sim/sar-logic-timing-gates-lt/records/20260920-182006-2422cac.md`
- `sim/sar-logic-timing-gates-xl/records/20260921-021359-2422cac.md`

Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only `records/` tree is never edited. Both records are committed
exactly as `run_corners.py` wrote them; this document does not amend them, it
states what their own logs say that their Result tables do not.

The abort times, counts, and node names below are re-derivable from evidence
already committed in this tree — no new instrument, no re-run. The wall-time
columns in §3.1/§3.2 are the one exception: they were measured on the run host
from `sim/.work/` deck mtimes, which are gitignored and not part of this
tree, so they are not reproducible from the committed evidence alone.

```bash
# which of a grid's 45 points hit the cap, which aborted, and where
for f in sim/sar-logic-timing-gates-lt/corners/20260920-182006-2422cac/*.log; do
  if grep -q '^TIMEOUT' "$f"; then echo "$(basename "$f") TIMEOUT";
  else echo "$(basename "$f") $(grep -o 'Timestep too small; time = [0-9.e-]*' "$f" | head -1)"; fi
done

# the single-measurement false-PASS mechanism, in one log
grep -n 'm_abs_err_delay_40ns\|Timestep too small' \
  sim/sar-logic-timing-gates-lt/corners/20260920-182006-2422cac/tt_27c_3.63v.log
```

## 1. The finding in one line

**Across the two delay-line per-loop decks that have now been run
(`lt`, `xl`), not one point of either 45-point grid reached the end of the
ratified `tran 5n 8.5u 0 5n`.** Every point either hit the 7200 s per-point
cap or aborted with `doAnalyses: TRAN: Timestep too small` between 1.29 µs
and 2.71 µs — 15 % to 32 % of the ratified window.

The `lt` record's Result table nevertheless reads `PASS` on 7 of its 45 rows
and `FAIL` on 3 more, i.e. it presents 10 scored points. Those 10 are exactly
the 10 aborts. Their `abs_err_delay_40ns` values are `meas` results computed
over a transient that stopped after roughly one and a half conversions, not
the seven the measurement is defined over. The `xl` record presents 6 scored
points the same way (all 6 `FAIL`), and those 6 are exactly its 6 aborts.

## 2. Why the harness does not notice

`sim/sar-logic-timing-gates-{lt,xl,bad}/testbench/tb.json` each declare
exactly **one** measurement (`abs_err_delay_40ns` / `_50ns` / `_70ns`), and
that measurement is an unbounded-right `MAX`:

```
"tran 5n 8.5u 0 5n",
"meas tran aerr_lt MAX v(lt_aerr) FROM=0.1u"
```

`meas ... MAX ... FROM=0.1u` with no `TO=` runs to the end of *whatever data
exists*, so an aborted run still emits a number. `sim/harness/runner.py`'s
only failure test on a process that exited is whether any manifest
measurement is **missing**:

```python
measurements = parse_measurements(output)
missing = [name for name in tb.measure if name not in measurements]
if missing:
    ...  # status="failed", message = first "Error|Fatal|doAnalyses:" line
return PointResult(point=point, status="ok", measurements=measurements, ...)
```

`doAnalyses:` is in `_ERROR_RE`, but that regex is only consulted **inside**
the `if missing:` branch. With one measurement that always parses, the branch
is unreachable and the point is returned `status="ok"`.

This is why `tie` caught its abort and `lt`/`xl` did not:
`sim/sar-logic-timing-gates-tie/testbench/tb.json` declares two measurements,
its `sf_27c_2.97v` abort at 399.655 ns killed the run before the second one
was emitted, `missing` was non-empty, and the record correctly reads
`ERROR — doAnalyses: TRAN: Timestep too small …` (that abort is issue #332).

**Blast radius, checked rather than assumed.** Grepping every committed
per-corner log in the tree for `Timestep too small`:

| deck | record | logs containing an abort |
|---|---|---|
| `sar-logic-timing-gates-ok` | `20260918-233547-1d81aa1` | **0** of 45 |
| `sar-logic-timing-gates-tie` | `20260920-020802-2043286` | 1 of 45 — reported as `ERROR`, tracked as #332 |
| `sar-logic-timing-gates-lt` | `20260920-182006-2422cac` | **10** of 45 — all reported as `PASS`/`FAIL` |
| `sar-logic-timing-gates-xl` | `20260921-021359-2422cac` | **6** of 45 — all reported as `FAIL` |
| `sar-logic-timing-gates` (pre-decomposition) | `20260915-210638-912a8ec` | 37 of 45 — reported as `ERROR` |
| `sar-logic-functional-gates` | `20260915-214338-912a8ec` | 2 of 45 — reported as `ERROR` |
| `sar-logic-functional-gates` | `20260916-042719-e5440a0` | 1 of 45 — reported as `ERROR` |

So no previously committed record is affected: `ok`'s 45-of-45 grid — the one
#319 and #320 rest on — contains no abort at all, `tie`'s single abort was
reported honestly, and the three multi-measurement decks above (each
declaring 16 or 9 manifest measurements, so `missing` is non-empty on an
aborted run) all correctly read `ERROR`. The defect bites exactly the
single-measurement decks, and it bit on their first run. Filed as issue
**#341**.

## 3. What the two grids actually measured

### 3.1 `lt` (`cmp_delay = 40 ns`, `tltd … z0=50 td=40n`), 45 points, `--timeout 7200`

Per-point wall time is `corners/<id>/<corner>.log` mtime minus the
corresponding `sim/.work/…/<corner>.spice` mtime (the runner writes the deck
when it dispatches the point and the log when the point returns):

| corner | wall | outcome |
|---|---|---|
| `ff_125c_3.30v` | 2586 s | abort @ 1.38481 µs, `vvdd_gate#branch` |
| `ss_27c_2.97v` | 2894 s | abort @ 1.28656 µs, `vvdd_gate#branch` |
| `ff_-40c_3.30v` | 3173 s | abort @ 1.29467 µs, `vvdd_gate#branch` |
| `ss_-40c_3.63v` | 3187 s | abort @ 1.45645 µs, `vvdd_gate#branch` |
| `tt_27c_3.63v` | 3400 s | abort @ 1.40244 µs, `vvdd_gate#branch` |
| `ff_125c_2.97v` | 3429 s | abort @ 1.60405 µs, `vvdd_gate#branch` |
| `ss_27c_3.30v` | 4338 s | abort @ 1.56238 µs, `vvdd_gate#branch` |
| `sf_125c_3.63v` | 4855 s | abort @ 2.36650 µs, `vvdd_gate#branch` |
| `fs_125c_3.30v` | 6813 s | abort @ 2.13535 µs, **`vltmode#branch`** |
| `fs_27c_3.30v` | 7180 s | abort @ 2.10511 µs, `vvdd_gate#branch` |
| the other 35 | 7200 s | `TIMEOUT` (no ngspice output retained) |

### 3.2 `xl` (`cmp_delay = 50 ns`, `txld … z0=50 td=50n`), 45 points, `--timeout 7200`

Same derivation, same columns. The 6 rows below are every `xl` point that
reached a verdict; the other 39 hit the cap. (The record's own header reads
"6 completed" — that is `points_ok` from the harness, i.e. 6 points that
*returned a parseable measurement*, not 6 that completed the ratified
transient; none did.)

| corner | wall | outcome |
|---|---|---|
| `ff_125c_3.30v` | 4991 s | abort @ 1.61473 µs, `vvdd_gate#branch` |
| `sf_27c_3.63v` | 5177 s | abort @ 2.71334 µs, `vvdd_gate#branch` |
| `ss_27c_2.97v` | 5341 s | abort @ 1.42592 µs, `vvdd_gate#branch` |
| `fs_-40c_3.30v` | 5657 s | abort @ 2.51333 µs, `vvdd_gate#branch` |
| `fs_-40c_3.63v` | 5772 s | abort @ 2.71300 µs, `vvdd_gate#branch` |
| `fs_125c_3.63v` | 6848 s | abort @ 2.61354 µs, `vvdd_gate#branch` |
| the other 39 | 7200 s | `TIMEOUT` (no ngspice output retained) |

Unlike `lt`, **none** of `xl`'s six scored rows reads `PASS`: all six report
`FAIL — abs_err_delay_50ns max=0.5`, at 4, 4, 4, 122, 507 and 507 LSB. Those
numbers are still products of the same defect in §2 — a `MAX` over 1.4–2.7 µs
of an 8.5 µs window — so they are no more trustworthy as failures than `lt`'s
were as passes; they are quoted here only to show what the record says.

**Host contention, stated because it inflates every wall time above.** Per the
operator note on issue #303 (2026-09-21T06:08Z), this `xl` run shared the host
with a launchd-respawned **duplicate** `lt` grid (work dir
`20260921-021339-2422cac`, discarded, never scored) for its first 3 h 48 m — 24
ngspice jobs on 18 cores, host load average 58. Its first `-j 12` wave
therefore ran at roughly half a core each, so the early timeouts are host
contention, not evidence that those points are slower than the six that
aborted. This does not touch the finding: contention can turn an abort into a
timeout, but it cannot turn a completed 8.5 µs transient into an abort at
1.6 µs, and the six points that *did* reach a verdict all aborted.

## 4. Two things this does and does not say

**It does say the 7200 s cap was too low.** The 10 `lt` aborts spent
2586–7180 s to cover 1.29–2.37 µs of the 8.5 µs window, and the 6 `xl` aborts
4991–6848 s to cover 1.43–2.71 µs (the latter partly under the host contention
noted in §3.2, which makes those wall times an over-estimate of the deck's own
cost but does not change the ratio's order). Even assuming the cost
per simulated nanosecond does not keep rising — and
`20260917-issue-303-transient-cost-and-retention.md` measured that it does —
a point that survived would need of order 15 000–30 000 s. `run_deck.sh`'s
own `--note` justified 7200 s as ">10x the ~570 core-s/point this deck's
calibration probe extrapolates to", from a 0.5 µs truncated probe; the
extrapolation is wrong by more than an order of magnitude, and the note is
committed inside both records saying so. Any future run of these decks needs a
cap derived from a full-length point, not from a truncated probe — or, per the
operator direction recorded on issue #303, a batch fleet rather than a
dispatch host.

**It does NOT say the timeouts would have aborted.** 35 `lt` points and the
`xl` timeouts were cut off without ngspice output (the runner writes only
`TIMEOUT after 7200s` on `subprocess.TimeoutExpired`), so where they were and
what they would have done is unknown. What is known is that **every point of
either deck that ran long enough to reach a verdict reached an abort, and none
reached the end of the transient.**

## 5. Why this is new information, not #296 or #310 again

Both of the standing convergence diagnoses predict these decks should be fine:

- **#296** (fixed): an ideal comparator B-source stepping rail-to-rail in zero
  time into a bare standard-cell gate input. That mechanism is explicitly
  *not* present on `lt`/`xl`/`bad` — their comparator drives a matched 50 Ω
  terminated line, and #296's own evidence noted the trouble node in #289's 45
  logs was "always `bokcmp`/`btiecmp` … and **never**
  `bltcmp`/`bxlcmp`/`bbadcmp`". Consistent with that, none of the 16 aborts
  here names a comparator source.
- **#310** (closed by #311's decomposition): `vvdd_gate#branch` is "the one
  matrix row that couples all five otherwise-independent DUT instances
  (5 × 181 cells on one `.global vdd_gate` source)", and decomposition "removes
  the shared row by construction". **The per-loop decks have exactly one
  `sar_ctrl_a` instance each** (`grep -c '^+ sar_ctrl_a'` returns 1 on the
  `lt`, `xl` and `ok` testbenches) — and 15 of these 16 aborts still name
  `vvdd_gate#branch`. A single-instance deck cannot be aborting because five
  instances share a supply row.

The control that isolates the variable is already in the tree:
`sar-logic-timing-gates-ok` is the *same* DUT, the *same* single instance, the
*same* supply source, the *same* 8.5 µs window and the *same* comparator
model, differing only in that it has **no transmission line** and
`cmp_delay = 0` — and it completed 45 of 45 with zero aborts, in 2.0 core-h
for the whole grid. `tie`, also T-line-free, completed 29 of 45 with one
abort. The two decks that carry an ideal lossless `tltd`/`txld` are the two
that abort at every point that gets far enough.

That makes the ideal lossless transmission line the leading hypothesis and
gives it a cheap first test (a truncated `tran`, `z0`/`td` unchanged, against
the same point with the line replaced by a matched lumped delay), but nothing
here confirms it — no instrumented probe was run for this document. Filed for
diagnosis as issue **#343**; nothing in any deck, manifest, comparator model
or `tran` parameter was changed here, and no bound was relaxed.
