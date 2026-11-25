# Investigation 20261021-issue-623-tp-inj-host-offset

This is not a `sim/run_corners.py` evidence record and scores no PVT grid. It
is a provenance analysis of committed records plus **one** single-corner local
probe. It sits in `investigations/`, next to `records/`, so the append-only
`records/` tree is not edited.

- **Date**: 2026-10-21 (UTC)
- **Base commit**: `e85469757350ef0979b4436d5b442f2b6b59f359` (`origin/main`)
- **Issue**: #623 (part of #595; found by #615)
- **Compared pair (in scope)**: A = [`20260923-104443-904af96`](../records/20260923-104443-904af96.md) vs B = [`20261007-071907-800bf53`](../records/20261007-071907-800bf53.md). Both record testbench sha256 `4fea809d68eba487643e166fb30011b5bbf3c32056644778afab98ecfdf1dd2f` and manifest sha256 `8eab6926ae7baacd94d66a255fc9556ce345440fa089562f72458e15392a8819`.
- **Out of scope**: [`20261007-072143-800bf53`](../records/20261007-072143-800bf53.md). It records testbench sha256 `cc6d2b44b73b0da359196a95ba42f0cdc86b8cb89cb81b66b6e2dba0854b465c`, the V_DD-pin-network variant deck, so its tp_inj shift against A is expected and is not part of this question. (The issue body says all three ran one deck; only A and B did.)
- **Companion files** (outputs committed verbatim):
  [`20261021-issue-623-compat-probe.txt`](20261021-issue-623-compat-probe.txt),
  [`20261021-issue-623-cross-host-deltas.py`](20261021-issue-623-cross-host-deltas.py) /
  [`.txt`](20261021-issue-623-cross-host-deltas.txt)
- **Delta tool**: `sim/dr0014-sampling/requal_delta.py` from PR #624 (branch `feature/issue-615`, not yet on `main`), read with `git show`.

## Conclusion

**(c) undetermined, but narrowed to one cause class.** B's offset is a
property of the macOS host's ngspice execution environment. The remaining
discriminating run is one corner on that host. Specifically:

1. A Linux run reproduces A **exactly** (all 43 `m_*` and `a*` values of
   `ff_-40c_3.63v` identical to A's log), including under a newer PDK commit
   (f6eeac7 vs c6d73a3). The two fleet re-runs reproduce A the same way. So
   the deck, harness, PDK pin and Linux ngspice-46 are stable, and B is the
   outlier.
2. The `Compatibility modes selected: hs a` ngspice note that every B log
   carries is **not** the cause. Forcing `ngbehavior=hsa` on the Linux host
   changes the compatibility note and nothing else: the whole ngspice output
   is identical apart from that one line (diff in the probe file).
3. What is left is whatever else differs on the macOS workstation: the
   ngspice build and platform (arithmetic, libm, BLAS/solver build), init
   state other than `ngbehavior`, and PDK model-file bytes at
   `/Users/rwalters/.volare/gf180mcuD`. None of these is recorded.
   Host/engine build is the likeliest, but it is **not confirmed**.

**Not run (needs the macOS host, which is not reachable from here):** one
corner (`ff_-40c_3.63v`) of the extracted deck, with `ngspice --version` (full
banner), `uname -a`, `cat ~/.spiceinit` and `sha256sum` of the PDK
`sm141064.ngspice`, run twice (default, and with `ngbehavior` cleared if the
init file sets it). If it differs from A there, the build is confirmed. If it
matches A there, the cause is the PDK bytes or a harness-level difference.

## 1. Every recorded difference between A and B

| Field | A `20260923-104443-904af96` | B `20261007-071907-800bf53` | Status |
|---|---|---|---|
| Testbench / manifest sha256 | `4fea809d…` / `8eab6926…` | identical | ruled out (equal) |
| open_pdks commit | `c6d73a35f524…` | `c6d73a35f524…` | ruled out (equal); PDK pin is also ruled out by the fleet re-runs below |
| PDK path | `/home/ubuntu/.volare/gf180mcuD` | `/Users/rwalters/.volare/gf180mcuD` | host marker; file bytes **not recorded** |
| ngspice string | `ngspice-46` | `ngspice-46` | equal as recorded; minor version / build / platform **not recorded** |
| ngspice front-end note (from logs) | `No compatibility mode selected!` | `Compatibility modes selected: hs a` | **ruled out as cause** (§2) |
| Python | 3.12.3 | 3.14.8 | not isolated (§3) |
| Harness | `sim/harness 0.1.0` | `sim/harness 0.1.0` | `git diff 904af96 800bf53 -- sim/harness` is empty |
| Working tree | dirty at `904af96` | clean at `800bf53` | ruled out: the run deck's sha256 matches the committed `main` deck either way (the committed `904af96` deck differs, `314cfabf…`, which is what "dirty" captured) |
| Wall time | not stated here | 9850.64 s | not informative |

## 2. What was measured

Per-corner pairing with `requal_delta.py 20260923-104443-904af96
20261007-071907-800bf53` (27 of 27 corners paired, 10 measurements moved
beyond the tool's 1 % / 1e-3 tolerance), worst corner for each:

| Measurement | Worst corner | A | B | B − A |
|---|---|---|---|---|
| `tp_inj_p_l0_lsb` | `ff_-40c_3.63v` | 0.113089 | 0.106386 | −0.0067 |
| `tp_inj_n_l0_lsb` | `ff_-40c_3.63v` | 0.112588 | 0.105739 | −0.00685 |
| `tp_inj_p_l1_lsb` | `ff_-40c_3.63v` | 0.113261 | 0.106569 | −0.00669 |
| `tp_inj_n_l1_lsb` | `ff_-40c_3.63v` | 0.112669 | 0.10583 | −0.00684 |
| `tp_inj_p_l2_lsb` | `ff_-40c_3.63v` | 0.11228 | 0.105563 | −0.00672 |
| `tp_inj_n_l2_lsb` | `ff_-40c_3.63v` | 0.111872 | 0.10501 | −0.00686 |
| `tp_inj_p_l3_lsb` | `ff_-40c_3.63v` | 0.11315 | 0.106458 | −0.00669 |
| `tp_inj_n_l3_lsb` | `ff_-40c_3.63v` | 0.112901 | 0.106067 | −0.00683 |
| `tp_inj_p_l4_lsb` | `ff_-40c_3.63v` | 0.113066 | 0.106363 | −0.0067 |
| `tp_inj_n_l4_lsb` | `ff_-40c_3.63v` | 0.112748 | 0.105904 | −0.00684 |

The other 34 measurements agree within tolerance, including
`tp_inj_signal_dep_lsb` (+2.78e-05 LSB at worst), `samp_gain_err_lsb`
(+0.0003 LSB) and `samp_inl_worst_lsb` (−0.000125 LSB). The offset is a common
shift of the p and n injections by about 0.0067 to 0.0069 LSB (about 6 % of
their value at the fast corner); it cancels in the mismatch and signal-dependent
terms.

**Fleet re-runs.** The two fleet re-runs of the extracted deck under open_pdks
f6eeac7 (`20261020-233008-0bf0747`, `20261020-231428-0bf0747`, from PR #624)
reproduce A's values and not B's (`requal_delta.py` pair 5: 0 moved against A;
pair 6: 10 moved against B). That rules out the PDK pin, as the issue states.

**Compat-mode correlation and probe** (full output in
[`…-compat-probe.txt`](20261021-issue-623-compat-probe.txt)):

- Over the committed records that have both a per-corner log and a PDK path,
  `Compatibility modes selected: hs a` appears in 72 of 72 records on
  `/Users/rwalters` and never on `/home/ubuntu` (84 of 84 show
  `No compatibility mode selected!`). It is a marker of the macOS host, so
  the correlation alone cannot separate "compat mode" from "everything else
  on that host".
- Probe, host `loom-worker-1` (Linux 7.0.0-1014-aws x86_64, `ngspice-46`
  banner in the probe file), harness deck for `ff_-40c_3.63v` of the extracted
  deck, run with and without `set ngbehavior=hsa` in a local `.spiceinit`:
  output identical except line 2. The default run's 43 measured values match
  A's log for the same corner with no differences, and differ from B's
  (`a0_dp`, `a0tpp` and others).

## 3. What is not isolated

- **Python 3.12.3 vs 3.14.8.** The harness writes the deck text, so a
  float-formatting difference in the deck is conceivable, but the deck's
  generated text for a corner is not committed for either record, so it cannot
  be compared. This is the second thing the macOS run should capture (the
  composed deck's sha256).
- **ngspice minor version and build string**, `~/.spiceinit` contents, and the
  PDK `sm141064.ngspice` bytes on the macOS host. None is recorded.

## 4. Other macOS-vs-Linux pairs on identical deck bytes

Four other cross-host pairs on identical deck and manifest sha256 exist
(`20261021-issue-623-cross-host-deltas.py`, output in `.txt`). They agree with
what #459 already tabulated for byte-identity; this table adds the magnitudes.

| Experiment | Linux → macOS records | Result |
|---|---|---|
| `adc-inl-dnl` | `20260923-095400-904af96` → `20261007-044826-800bf53` | 56 of 84 measurements differ, largest ~2e-5 LSB on the listed `decerr`/`terr`/`gain_err` rows |
| `adc-power` | `20260923-102440-904af96` → `20261007-072338-800bf53` | 24 of 32 differ; largest −0.235 µW on `p_total_f075_uw` (168.079 → 167.844, 0.14 %) |
| `adc-enob-fft` | `20260923-111149-904af96` → `20261007-072654-800bf53` | digital codes; 0 differ (raw logs still differ) |
| `device-switch-ron` | `20260731-191216-5f5288b` (macOS) → `20260806-140624-4f71285` (Linux) | `.op` only; 0 differ (raw logs still differ) |

So a cross-host offset appears wherever the measurement comes from a
transient with a continuous analog readout, at 1e-5 LSB (`adc-inl-dnl`) up to
about 6 % relative (`tp_inj_*`), and vanishes for digital codes and `.op`
values. This is consistent with a numerical-path difference, and does not
distinguish between the candidates in §3. Issue #459 reached the same
"unsplit environment" conclusion for the same A/B pair.

## 5. What the paired-control citation should say

`sim/vdd-full-pvt/` compares B (`…071907`) against the V_DD-network arm
(`…072143`). Both ran on the macOS host (`/Users/rwalters`, `hs a`) with the
same harness commit `800bf53`, so the **paired delta is a same-host
difference and does not carry this offset**: the Linux→macOS shift is common to
both arms. What must not be done is mixing families: B's absolute values are
macOS values and should not be compared to, or cited as equal to, A's or the
fleet's (`tp_inj_p_l0_lsb` at `ff_-40c_3.63v`: 0.113089 Linux/fleet vs
0.106386 macOS). Any citation of B's absolute `tp_inj_*` numbers should name
"macOS host, offset ~0.007 LSB vs the Linux/fleet value, cause not isolated
(#623)". No spec-bearing figure is affected: `tp_inj_signal_dep_lsb` moves
by 2.78e-05 LSB against a 0.5 LSB bound. No edit to `sim/vdd-full-pvt/README.md`
is made here; a caveat, if wanted, is a follow-up edit to that README, not to
a record.

## Reproduce

```
python3 -I sim/dr0014-sampling/investigations/20261021-issue-623-cross-host-deltas.py
python3 -I sim/dr0014-sampling/requal_delta.py 20260923-104443-904af96 20261007-071907-800bf53   # after PR #624 lands, or on its branch
```

The probe ran the harness `compose_deck` for `ff` at −40 °C / 3.63 V, then
`ngspice -b` once with and once without `set ngbehavior=hsa` in the working
directory's `.spiceinit`, as a single local corner per host guidance.
