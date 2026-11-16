# Investigation 20261116-issue-844-cold-corner-sequencing

Not a `sim/run_corners.py` evidence record (no PVT grid is claimed here) —
a manual root-cause investigation of the four non-passing points of
`sim/sar-logic-functional-gates/records/20261116-012005-d0b5171.md` (the
deck's **first ever measured −40 °C / 125 °C data**, PR #843 for #779).
Kept in `investigations/`, alongside (not inside) `records/`, so the
append-only record this investigation explains is never edited. Filed by
Judge during #843's review; characterisation only — the fix is
**issue #854**, per #295 → #298's precedent.

## Conclusion

**Three distinct mechanisms, none of them a bound that was derived
wrong, and one instrument correction.** Two of the four non-passing
points are measurement-window artefacts scoring the discarded first
conversion (dispositioned by DR-0046 as an instrument correction with
DR-0031 part 2 as precedent — no bound moved); the two cold points are
**real, measured sequencing failures of the synthesized `sar_ctrl_a` at
slow-NMOS corners**, at two severities, plus one analog finding the
issue's own hypothesis did not predict:

1. **`ss_125c` / `sf_125c` — conversion-1 window artefact.** Their
   `nside_cells_df` maxima land at **0.939 µs / 0.751 µs**, inside
   conversion 1 (drdy #1 closes ≈ 1.126 µs), whose select pattern is an
   arbitrary function of the no-reset power-up flop state
   (DR-0031 part 1(b)) and has no one-hot invariant to violate.
   DR-0031 part 2's "Not taken" clause had kept `conf_*`/`nside_*` at
   `FROM=0.1u` bundled with the code witnesses, without weighing what
   conversion 1 does to steady-state hazard budgets. **DR-0046** moves
   the one-hot family past the discarded conversion and records why the
   code witnesses stay put. Bounds unchanged; the 8.9–9.1
   `nside_cells_df` bound is not what was wrong.
2. **`tt_-40c` — the `ph` ring degenerates from one-hot to multi-hot**
   (probe-measured ring waveforms): conversion 3 still walks one-hot;
   by conversion 9 the ring state is a rotating multi-hot block
   (popcount 5–6, e.g. `111111000000000`). Set-bits accumulate ~1 per
   conversion. The sample phase (`samp_tp_n = ph[0]|ph[1]|ph[2]`) grows
   1,1,1,2,3,4,4,6 clocks over conversions 1–9 (record average over 60:
   11.7 clocks vs DR-0003's 4) while the conversion period survives at
   ~992 ns — the *period* is intact, the *contents* corrupt: garbage
   codes with MSB-weight errors (523 / −513), one-hot decode blow-ups
   (`nside_cells_df` 15.56, `sw_conflict_df` 26.5), all steady-state,
   all downstream of the ring.
3. **`sf_-40c` — the same family, terminal.** Conversions 1–7 complete
   exactly; `drdy` #7 (7.063 µs) is the **last rise** — the sequencer
   stops. The record's frozen `code_se_hi = 101` is conversion 7's own
   output (expected at stall time ≈ 101). `tdr_b` failing (`out of
   interval`) is the only check that sees the stall: `conv_period_ns`
   "failed" is a downstream artefact of `tdr_b`, and `err_*` read 0
   **vacuously** (the `err` node is drdy-gated and no window ever opens
   again).
4. **`ss_-40c` — two independent steady-state findings.** (a) A **single
   wrong decision** at conversion 3: `+15` exactly, one-sided, settled
   (not a mid-update capture): the probe's residue trace shows the
   search terminating ~15.4 LSB off balance, with `c4` (weight 16) set
   and `c0` clear where the expected 37 needs the opposite — cadence
   and decode stay normal all run (`acq_av` 185.77 ns, all 60
   conversions complete). (b) `nside_cells_df` 9.16096 at 63.0 µs is
   **analog overshoot above VDD on the rising `sel_hi_n` driver outputs**
   (3.332–3.542 V vs 3.300 V), not the make-before-break overlap the
   issue hypothesised: the one-hot boolean pattern is intact at the
   peak; the raw-voltage sum crosses the bound on the overshoot alone.
   A measured refutation of the issue's hypothesis.

**Axis pattern confirmed**: every cold failure is at a non-fast-NMOS
corner — `ff`/`fs` pass at −40 °C, `tt`/`ss`/`sf` fail; the pattern is
5/5 on the err/sequencing cluster and 3/3 on the (now dispositioned)
125 °C one-hot excursions. One record at one supply: a pattern, not yet
a mechanism-level derivation (that is #854's to close).

**No ratified bound moves.** `nside_cells_df`'s 8.9–9.1 bound did its
job: it caught a real cold-corner excursion (`ss_-40c`), which stays a
recorded FAIL until #854 resolves the design. `ss_-40c`'s +15 and the
`tt_-40c` cluster stay FAILs for the same reason.

## Provenance

- git: worktree `feature/issue-844` on `974d249f2aa6ff4ba5a51d4783b9836c7b32f4ba`
  (the `main` head this branch tracks); the stored-log analysis below is
  against record `20261116-012005-d0b5171` (taken at commit `d0b5171`,
  PR #843), fetched through its hash-verified manifest
  `manifests/artifacts/sar-logic-functional-gates-20261116-012005-d0b5171.manifest.json`
  — every `klt artifact get` printed `verified <sha256>` (21 objects;
  `python3 scripts/check_artifact_manifests.py verify <manifest>` passes).
- PDK: gf180mcuD @ open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
  (`~/.ciel/gf180mcuD`, `SOURCES`-verified; same pin as `sim/toolchain.json`
  and as the record itself)
- ngspice: ngspice-47 (local single-corner probes; KLU solver)
- python: 3.12.3
- Probe decks: composed by `design/sar-logic/flow/probe_code_readout.py`
  (the issue #320 readout instrument, which this investigation extends
  with a generic `--nodes` option: extra saved/printed node expressions,
  e.g. the ring's `xse.ph_0..ph_14`, `se_samp_tp_n`, the 18 `df_sel_*n`
  legs). Single corner per run, local per the host rules; each run keeps
  its composed deck and raw log under `/tmp/844-probe/<name>/` and is
  re-derivable from the commands quoted below. Nothing under `sim/` was
  written by any probe run (the instrument writes evidence only via
  `sim/run_corners.py`; the one confirmation re-run this investigation
  minted is `records/20261116-092415-<sha>.md`, batch fleet, cited in
  §6). `records/` itself is untouched.

## 1. The classification: every violating measure, stamped and placed

Method: zero simulation. `klt artifact get` the six relevant logs from the
record's manifest, `grep` every `meas` result line's `at=` stamp, place it
against the conversion timeline (drdy #N rises at `1.063 + (N−1) × 1.000`
µs at nominal cadence; drdy #1's window closes ≈ 1.126 µs; DR-0031 part 2
already starts the `err_*` window at 1.5 µs). Violating rows in **bold**.

### `ss_125c_3.30v` (FAIL: `nside_cells_df`)

| measure | value | `at=` | placement |
|---|---|---|---|
| `nside_cells_df` (`nside_df`) | **9.84717** (8.9–9.1) | **0.939 µs** | **conversion 1** — power-up garbage |
| `sw_conflict_df` (`conf_df`) | 18.0777 (≤ 20) | 0.376 µs | conversion 1 — passing, but at **90 % of the bound on garbage** |
| `sw_conflict_se` (`conf_se`) | 9.07811 (≤ 15) | 0.376 µs | conversion 1 |
| `nside_cells_se` (`nside_se`) | 0.0515 (≤ 0.1) | 1.001 µs | conversion 1 |
| `code_se_lo`/`code_df_lo` | 0 | 1.063 µs | conversion 1 — **by design**: bottom-of-range witness (DR-0031 part 2; bound already admits it) |
| `code_se_hi`/`code_df_hi` | 1013 | 64.5 µs | end of ramp |
| `err_*` | 0 | 64.5 µs | steady state (window already `FROM=1.5u`) |

### `sf_125c_3.30v` (FAIL: `nside_cells_df`)

Same placement as `ss_125c` with `nside_df` **9.90088** at **0.751 µs**
(conversion 1), `conf_df` 18.0837 and `conf_se` 9.0844 at 0.376 µs
(conversion 1), `nside_se` 0.0611 at 1.0009 µs (conversion 1), code
witnesses as above.

### `ss_-40c_3.30v` (FAIL: `err_se_max` 15, `err_df_max` 15, `nside_cells_df` 9.161)

| measure | value | `at=` | placement |
|---|---|---|---|
| `err_se_hi` / `err_df_hi` | **15** | 3.125 µs | **steady state** — conversion 3, at the close of its own drdy window (drdy #3 rises 3.063 µs); §4a |
| `nside_cells_df` | **9.16096** | 63.0007 µs | **steady state** — §4b |
| `sw_conflict_df` | 14.7700 (≤ 20) | 63.0007 µs | steady state — passing, but **above DR-0027's 27 °C worst** (13.0045): the hazard budget's temperature margin is thin |
| `sw_conflict_se` | 9.38728 (≤ 15) | 58.377 µs | steady state |
| `nside_cells_se` | 0.0483 (≤ 0.1) | 63.000 µs | steady state |
| `code_se_lo`/`code_df_lo` | 2 | 1.063 µs | conversion 1 (witness, admitted by bound) |
| `err_*_lo` | 0 | 64.5 µs | steady state |

Cadence measures all normal: `acq_av` 185.77 ns, `iso_av` 64.50 ns,
`tdr_a` 5.063 µs, `tdr_b` 60.063 µs — **all 60 conversions complete at
nominal spacing**. The cold failures at this point are *not* cadence
failures.

### `tt_-40c_3.30v` (FAIL: all four `err_*`, `sw_conflict_df`, `nside_cells_df`, `conv_period_ns`, `acq_window_ns`)

| measure | value | `at=` | placement |
|---|---|---|---|
| `err_se_hi` | **523** | 7.828 µs | **steady state** — conversion ≈ 8 |
| `err_se_lo` | **−513** | 32.06 µs | **steady state** |
| `err_df_hi` | **506** | 32.58 µs | **steady state** |
| `err_df_lo` | **−513** | 32.06 µs | **steady state** |
| `nside_cells_df` | **15.5594** | 55.376 µs | **steady state** — §2 |
| `sw_conflict_df` | **26.5382** | 58.376 µs | **steady state** |
| `acq_window_ns` | **667.495** (175.0–218.7) | 2–62 µs average | **steady state** — §2 |
| `conv_period_ns` | **992.045** | tdr_a 4.938, tdr_b 59.50 µs | **steady state** — all 60 rises, ~0.8 % fast |
| `sw_conflict_se` | 14.0224 (≤ 15) | 32.376 µs | steady state — passing at **93 % of bound** |
| `nside_cells_se` | 0.0670 (≤ 0.1) | 55.438 µs | steady state |
| `code_se_hi`/`code_df_hi` | 1023 | 64.5 µs | end of ramp (saturated; witness bound `[990, 1023.5]` admits it) |
| `code_*_lo` | 0 | 32.06 µs | steady state |

The issue's "mis-triggered measure" alternative for `acq_window_ns` was
already refuted without simulation (Curator enhancement, verified here:
the measure is `AVG v(se_acq) FROM=2u TO=62u` over a normalized duty
node — no trigger to mis-fire). §2 measures *what* stretches instead.

### `sf_-40c_3.30v` (ERROR, not scored)

| measure | value | placement |
|---|---|---|
| `tdr_a` | 5.063 µs | rise #5 normal |
| `tdr_b` | **absent** — `when(WHEN) : out of interval` | fewer than 60 rises in 64.5 µs: **§3** |
| `conv_period_ns` | `failed` | pure downstream of `tdr_b` (the expression is `(tdr_b−tdr_a)/55*1e9`); **not** evidence about cadence |
| `code_se_hi`/`code_df_hi` | 101 | conversion 7's frozen output (§3) |
| `err_*` | 0 @ 64.5 µs | **vacuous** — the `err` node is drdy-gated; no window opens after the stall, so `MAX` reads the ungated 0 |
| `conf_df` | 11.3283 (≤ 20) | 7.0006 µs — steady, pre-stall |
| `nside_cells_df` | 9.03782 (8.9–9.1) | 6.9387 µs — steady, pre-stall |
| `conf_se` | 7.96063 | 0.376 µs — conversion 1 |
| `nside_se` | 0.0497 | 1.0006 µs — conversion 1 |
| `acq_window_ns` / `iso_gap_ns` | 19.17 / 5.86 | the stall: sample control asserted only during conversions 1–7 |

Note what the record's score sheet cannot say and this table does: at
`sf_-40c` the checks that *pass* (except `tdr_a`/`tdr_b`) do so only
because the DUT stopped converting — `err_*` pass vacuously, and
`conf_df`/`nside_df`'s pre-stall values score a healthy sequencer that
then dies.

## 2. `tt_-40c`: the `ph` ring degenerates from one-hot to multi-hot

Probe (single corner, local, 10 µs cut — full command in §7):

```
probe_code_readout.py sar-logic-functional-gates --tag se --corner tt \
  --temp -40 --vdd 3.30 --until 10u \
  --nodes xse.ph_0,...,xse.ph_14,v(se_samp_tp_n),v(se_sel_in_n)
```

**(a) Conversions 1–3 are healthy and exact.** drdy #1–#3 rise at
1.063/2.063/3.063 µs (nominal spacing), codes 5/21/21 = expected at #1/#2
(conversion 3 settles +11 — one wrong accept, the same single-decision
family as §4a, visible *before* any ring damage). The ring walks one-hot
at 62.4 ns/phase: `ph_0` rises 1.1256 µs, each next phase 62.5 ns later,
`ph_13`→`ph_14`→(drdy rise at `ph_14`'s fall)→wrap.

**(b) The sample phase grows, monotonically, ending at each drdy rise.**
`samp_tp_n` high-time per conversion, measured from the probe's
`samp_tp_n` waveform:

| conversion (drdy rise) | samp high | clocks (62.5 ns) |
|---|---|---|
| 1 (1.063 µs) | 62.3 ns | 1 |
| 2 (2.063) | 62.3 | 1 |
| 3 (3.063) | 62.4 | 1 |
| 4 (4.063) | 124.8 | 2 |
| 5 (5.063) | 187.3 | 3 |
| 6 (6.063) | 249.8 | 4 |
| 7 (7.063) | 249.8 | 4 |
| 8 (8.063) | 374.8 | 6 |
| 9 (9.063) | 374.8 | 6 |

Growth ≈ +0.7 clock per conversion, extrapolated over the record's 60
conversions to the measured 11.7-clock average (667.495 ns / 62.5 ns),
with the cycle saturating at 16 clocks. RTL says `samp_tp_n =
ph[0]|ph[1]|ph[2]` — a fixed 3-clock decode. A 1→6-clock samp window
with the decode unchanged means **the ring state feeding it is no longer
one-hot**: extra `ph` bits are being set and not cleared.

**(c) The ring state, read directly (conversion 9, 7.55–8.07 µs):**

```
t=7.550737e-06  ph14..ph0=000011111000000  popcount=5
t=7.813115e-06  ph14..ph0=111100000000001  popcount=5
t=7.875618e-06  ph14..ph0=111000000000011  popcount=5
t=7.938115e-06  ph14..ph0=110000000000111  popcount=5
t=8.000615e-06  ph14..ph0=100000000001111  popcount=5
t=8.063115e-06  ph14..ph0=000000000011111  popcount=5
```

A contiguous **block of five 1s rotating through the register** — the
ring's rotate preserves popcount, so the extra set-bits were *injected*
earlier and persist. Popcount grows from 1 (conversions 1–3) to 5–6 by
conversion 9: ~1 injected bit per conversion, matching (b)'s growth
rate. This is a **state-injection mechanism** (a marginal path letting a
flop capture the wrong value on some cycles — cold slow-NMOS), not a
fixed timing skew: a skew would shift edges, not accumulate state.

**(d) Everything the record scores at `tt_-40c` follows.** With a
multi-hot ring: multiple trial phases assert simultaneously → multiple
weights engaged during trials → codes garbage with MSB-weight errors
(523 = 512+11, −513 — the magnitudes the record shows); the samp decode
(`ph_0|ph_1|ph_2` under a 5-hot state) is high ~11 clocks → `acq_window_ns`
667.5; the switch decode driven from concurrent phases violates one-hot
at scale → `nside_cells_df` 15.56 (≈ both legs of ~7 of 9 weights
asserted), `sw_conflict_df` 26.5. The conversion *period* survives
(~992 ns, 0.8 % fast) because the register still rotates once per 16
clocks — which is exactly why `tdr_a`/`tdr_b` stay within bounds while
everything the phases *do* goes wrong.

The MSB-weight error is a **consequence of the ring degeneration** (plus,
in its +11/+15 early-conversion form, the single-decision mechanism of
§4a while the ring is still nearly one-hot) — not an independent
decision error.

## 3. `sf_-40c`: the same family, terminal — the sequencer stops after conversion 7

Probe (single corner, local, 10 µs cut):

```
probe_code_readout.py sar-logic-functional-gates --tag se --corner sf \
  --temp -40 --vdd 3.30 --until 10u
```

Result: **seven drdy windows, all exact** (settled codes 5, 21, 37, 53,
69, 85, 101 = expected at every one; instantaneous worst 0 LSB), the
last rise at **7.063 µs, and no eighth** — through the probe's 10 µs
end. Combined with the record's own numbers over the full 64.5 µs
(`code_se_hi` frozen at **101** = conversion 7's output; expected code
reaches 101 at t ≈ 6.4–7.1 µs on this ramp; `acq_av` 19.17 ns and
`iso_av` 5.86 ns — the sample control asserted only ~1.1 µs of the
60 µs window, i.e. roughly conversions 1–7's worth at nominal 3-clock
acquisition): **`drdy` #7 is the last conversion the sequencer ever
completes; the stall begins immediately after conversion 7, at
t ≈ 7.1 µs.**

Reconciliation with the record:

- `tdr_b` (`WHEN v(se_drdy)=1.4 RISE=60`) → `out of interval`: correct
  and load-bearing — it is the **only** check that sees the stall.
- `conv_period_ns` = `failed`: the expression reads `tdr_b`, which never
  fired. An instrument consequence, not a cadence measurement.
- `err_se/df_hi/lo` = 0: **vacuous**. `b<tag>err` is
  `min(drdy,drdyg) > vth ? code − exp : 0`; with no drdy window after
  7.1 µs the node sits at its ungated 0 for the rest of the run, so the
  `MAX`/`MIN` over `FROM=1.5u` read 0 while the DUT is producing
  nothing.
- The frozen code 101: the output register holds conversion 7's word;
  the expected ramp reaches 101 at ≈ 6.4 µs, so the record's
  `code_se_hi` is the stall snapshot, not a conversion result.

Whether the stall is the §2 injection mechanism run to completion (the
ring collapsing into a state whose rotation never again produces the
drdy phase) is plausible and unproven — the probe's 10 µs cut ends
before the frozen state could be read directly. #854 owns that question;
a longer probe or the fix's A/B will answer it.

## 4. `ss_-40c`: two independent steady-state findings

Probe (single corner, local; two runs — full command in §7):

### (a) Conversion 3's `+15`: a real, settled, single wrong decision

The probe's conversion table at `ss_-40c` (se loop, 4.2 µs cut, with
`--bits`): conversions 1–2 settle exact (6 vs 5 = the discarded
conversion 1's +1; 21 = 21); **conversion 3 settles code 52 against
expected 37 — +15 exactly**, with register settling 0.0 ns — the
instantaneous and settled readings agree, so this is not DR-0031's
mid-update capture; conversion 4 is exact (53 = 53), and the error
never recurs (the record's `err` is stamped once, at 3.125 µs = the
close of conversion 3's window; `err_*_lo` read 0).

`c9..c0` at conversion 3's window close: `0000110100` (52) against the
expected `0000100101` (37): **`c4` (weight 16) is set where 37 clears
it; `c0` (weight 1) is clear where 37 sets it** — +16 − 1 = +15. A
wrong accept at the 16-weight trial forces every lower trial to
compensate downward, which is why the error is exactly the one-sided
`16 − 1`.

The comparator-input residue at conversion 3's ten trial edges (probe
`--analog`, `topp − topn` at each clk rising edge, LSB = 3.2226 mV):

```
2.4377us  +474.3 LSB   (post-sample, first trial connected)
2.5001us  +218.3       step −256
2.5628us   +90.4       step −128
2.6251us   +26.4       step  −64
2.6876us    −5.6       step  −32   (cmpo falls at this edge)
2.7503us   +10.4       step  +16   (16-weight restored)
2.8126us   +18.4       step   +8   (8-weight restored)
2.8753us   +14.4       step   −4
2.9376us   +16.4       step   +2   (2-weight restored)
3.0001us   +15.4       step   −1
```

The steps are clean ±weight quanta (no degraded amplitude), the search
terminates at +15.4 LSB from balance where correct conversions end
< 1 LSB — **the +15 is the search's own end state, visible on the
comparator inputs, not a capture or decode artefact.** Cadence and the
one-hot decode stay normal at this corner all run (`acq_av` 185.77 ns
= the nominal 3-clock acquisition; all 60 conversions; `nside_df`'s
only excursion is §4b's), so unlike `tt_-40c`/`sf_-40c` there is no
ring degeneration here — the wrong decision is an isolated
comparator/trial-latch marginality at a slow-NMOS cold corner.
Whether it shares a root cause with §2 is #854's to establish.

### (b) `nside_cells_df` 9.16096 at 63.0 µs: analog overshoot above VDD, not a decode overlap

Probe (df loop, **full 64.5 µs**, single corner, local — the expensive
run this investigation contains; ~27 min wall):

```
probe_code_readout.py sar-logic-functional-gates --tag df \
  --corner ss --temp -40 --vdd 3.30 \
  --nodes v(df_nside),v(df_drdy),v(df_sel_hi_n_<w>n)...,v(df_sel_lo_n_<w>n)...
```

The probe reproduces the record's maximum exactly: `df_nside` peaks at
**9.16096 at t = 63.00066 µs**. The 18 n-side select-leg voltages at
the peak instant:

```
weight :  256        128        64         32         16         8          4          2          1
hi  V  :  0.023      0.023      0.023      0.023      0.023      3.332      3.542      0.025      3.419
lo  V  :  3.300      3.300      3.300      3.300      3.300     -0.000     -0.000      3.300     -0.000
```

- The **one-hot boolean pattern is intact**: exactly one leg per weight
  above threshold (256..16 → lo, 8 → hi, 2 → lo, 1 → hi = 9 asserted).
  The issue's hypothesis — a make-before-break overlap of one cell's
  `sel_hi_n`/`sel_lo_n` pair — is **refuted at this corner**: no weight
  ever shows both legs high through the excursion.
- What exceeds the bound is **overshoot**: the three *rising* `sel_hi_n`
  outputs sit **above VDD** — 3.542 V on weight 4, 3.419 V on weight 1,
  3.332 V on weight 8 (VDD = 3.300 V; +0.24 V worst). The check sums
  raw node voltages (as DR-0027's and DR-0011's checks do), so the
  sum = 9 × 1.000 + (0.242 + 0.119 + 0.032) = **9.161**.
- The excursion is **conversion-boundary switching**, not ramp-top
  specific: `nside` also crosses 9.1 (9.10479) at t = 64.000 µs, and
  >9.0 for 1640 solver timepoints across the run; 27 °C's worst
  (9.04957) is the same overshoot family, milder. Cold + slow-NMOS
  makes it worst measured so far (+0.161 over the 9.0 baseline vs
  +0.050 at `tt_27c`).
- Physical reading: a standard-cell output ringing above its rail
  during a trial transition (fast input edge into a lightly loaded
  gate at this corner). It is measured on the real cell outputs into
  the deck's *behavioural* switch-gate load; the magnitude into a real
  (P&R) T-gate gate load is unknown — #854 owns that, along with
  whether the overshoot is the same mechanism DR-0027 budgeted at
  smaller magnitude or a separate one.

**The bound stays.** 8.9–9.1 admits ±0.1 of transient skew around the
9.0 one-hot baseline; the measured excursion is +0.161, from a real
(mildly out-of-rail) driver behaviour that gets worse at cold. Widening
the bound to admit it would be relaxing a ratified bound to pass a
result (`CLAUDE.md`), and would bury the only currently-failing witness
of that behaviour. `ss_-40c`'s `nside_cells_df` stays a recorded FAIL
until #854 resolves the design or produces a properly-derived bound
decision.

## 5. Dispositions (one line per non-passing point)

| point | disposition | evidence |
|---|---|---|
| `ss_125c_3.30v` `nside_cells_df` 9.847 | **instrument correction** — DR-0046 (`FROM=0.1u` → `1.5u` on the one-hot family; bounds unchanged) | `at=` 0.939 µs, inside the discarded conversion 1 (§1) |
| `sf_125c_3.30v` `nside_cells_df` 9.901 | **instrument correction** — DR-0046, same clause | `at=` 0.751 µs, inside conversion 1 (§1) |
| `tt_-40c_3.30v` (all eight violating measures) | **design-defect follow-up → #854** — `ph`-ring one-hot degeneration (state injection ~1 bit/conversion; sample phase 1→6→~12 clocks; codes/one-hot sums corrupt downstream); documented limitation: `conv_period_ns` still passes while the conversion contents are garbage, and `err`'s drdy gate cannot see a *stall* (only `tdr_b` can) | §2's ring waveforms and samp-growth table |
| `sf_-40c_3.30v` (ERROR row) | **design-defect follow-up → #854** (same family, terminal: sequencer stops after conversion 7) + **documented limitation** recorded: at a stalled DUT, `err_*`/`code_*` pass vacuously or freeze — `tdr_b` is the stall's only witness, and `conv_period_ns` "failed" is downstream of it, not a cadence reading | §3's seven-exact-conversions probe + the record's own frozen code/`acq_av` |
| `ss_-40c_3.30v` `err_*` = +15 | **design-defect follow-up → #854** — single wrong accept at conversion 3's 16-weight trial; search ends 15.4 LSB off balance; cadence/decode normal | §4a's probe tables |
| `ss_-40c_3.30v` `nside_cells_df` 9.161 | **design-defect follow-up → #854** — analog overshoot above VDD on rising `sel_hi_n` outputs (3.54 V worst), one-hot boolean pattern intact; bound unchanged, point stays FAIL | §4b's leg-voltage table |

Hypotheses refuted along the way (each a successful outcome per the
issue): the "mis-triggered measure" reading of `acq_window_ns` (it is an
untriggered duty average; §2 measures the real stretch); the
make-before-break overlap reading of `ss_-40c`'s `nside_cells_df` (§4b:
boolean one-hot intact, overshoot instead); "the three `tt_-40c`
symptoms could be one measure-window artefact" (all steady-state, one
mechanism, §2); and DR-0031 part 2's implicit assumption that leaving
`conf_*`/`nside_*` at the wide window was harmless (DR-0046's Context).

## 6. The confirmation re-run

The instrument correction's consequence — that the two 125 °C points
pass under the corrected window with bounds unchanged — is demonstrated
by a **new record** minted on the batch fleet (`klt sim` backend,
`--wait-for-capacity 600` applied by the harness's own
`CAPACITY_WAIT_S`), nominal supply only, two points:

```
python3 sim/run_corners.py sar-logic-functional-gates \
  --corners ss sf --temps 125 --supply 3.30 --supply-tol 0 \
  --backend batch --timeout 1700 --max-units-per-job 2 --max-concurrent-jobs 3 \
  --subset-reason "Confirmation re-run for issue #844 / DR-0046: ..."
```

`records/20261116-082605-974d249.md` (minted by that run — `status: PASS`,
2/2 points completed; committed with this investigation, evidence in the
artifact store via its manifest, per DR-0041) is the evidence for the
**corrected** instrument; `20261116-012005-d0b5171` remains committed
unchanged as evidence for the old one. The corrected-instrument values,
against the old row:

| measure | `ss_125c` old (conv-1 scored) → new | `sf_125c` old → new | bound |
|---|---|---|---|
| `nside_cells_df` | 9.847 FAIL → **9.091 PASS** | 9.901 FAIL → **9.036 PASS** | 8.9–9.1 |
| `sw_conflict_df` | 18.078 → **11.540** | 18.084 → **10.763** | ≤ 20 |
| `sw_conflict_se` | 9.078 → **8.907** | 9.084 → **7.274** | ≤ 15 |
| `nside_cells_se` | 0.0515 → **0.0456** | 0.0611 → **0.0580** | ≤ 0.1 |
| `err_*` | 0 → **0** | 0 → **0** | ±0.5 |
| `conv_period_ns` | 1000.0 → **1000.0** | 1000.0 → **1000.0** | 999.9–1000.1 |
| `acq_window_ns` | 186.7 → **186.7** | 196.0 → **196.0** | 175.0–218.7 |

The steady-state readings land where the 27 °C records sit (`nside_cells_df`
9.03–9.09 vs `tt_27c`'s 9.04957; `conv_period` exactly 1000.0), so the
correction changes what the two failing rows report and nothing else — the
AC's "a correction must not silently change what a *passing* point reports"
edge case holds: every other measure's new value is inside its bound and
consistent with the pre-correction steady-state picture. A first attempt at this re-run
(`20261116-081833-974d249`, taken with the default 300 s per-point
timeout and the full supply axis) timed out all six of its points
before completing any and was **deleted before commit** — it was never
committed, minted no conclusion, and is superseded by the correctly-
shaped run above; it is recorded here so the attempt is not silent.

## 7. Probe command reference

Each run: `python3 design/sar-logic/flow/probe_code_readout.py <args>`,
kept under `/tmp/844-probe/<name>/` (composed deck + raw ngspice log;
regenerable). Where `--nodes` carries node lists, `xse.ph_<i>` for
`i` in 0..14 is the synthesized ring (`ph_15` has no net in this
netlist); top-level nodes take their testbench names.

1. `--tag se --corner sf --temp -40 --vdd 3.30 --until 10u` — §3's
   seven-exact-conversions stall point.
2. `--tag se --corner ss --temp -40 --vdd 3.30 --until 4.2u --bits` —
   §4a's settled +15, register word `0000110100`, settle 0.0 ns.
3. `--tag se --corner ss --temp -40 --vdd 3.30 --until 4.2u
   --analog --trials 2.05e-6,3.1e-6` — §4a's residue trace.
4. `--tag se --corner tt --temp -40 --vdd 3.30 --until 4u --nodes
   xse.ph_0,...,xse.ph_14` — §2(a)'s healthy early walk.
5. `--tag se --corner tt --temp -40 --vdd 3.30 --until 10u --nodes
   xse.ph_0,...,xse.ph_14,v(se_samp_tp_n),v(se_sel_in_n)` — §2(b)/(c)'s
   samp growth and multi-hot ring states.
6. `--tag df --corner ss --temp -40 --vdd 3.30 --nodes v(df_nside),
   v(df_drdy),v(df_sel_hi_n_<w>n)...,v(df_sel_lo_n_<w>n)...` (full
   64.5 µs) — §4b's overshoot leg voltages.

(The `<w>` lists are 256,128,64,32,16,8,4,2,1.)
