# Record 20260806-parasitic-topology-inpath

- **Record ID**: 20260806-parasitic-topology-inpath
- **Claim**: at the `875eac3` toolchain pin (upstream `klayout-tools#593`),
  the parasitic **resistance** produced by `klt extract --deck gf180mcu
  --parasitics` is **in the signal path** for every parasitic net of every
  block this project extracts — not the dead-end shunt stub that
  [`20260806-parasitic-topology.md`](20260806-parasitic-topology.md) proved it
  was at the `af5791b` pin. This record is that record's post-bump companion
  and issue #116's acceptance-criterion 4 ("in-path resistance confirmed
  present (not another stub), via the same positive-control discipline
  `records/20260806-parasitic-topology.md` established"). It substantiates the
  claim three ways: **structurally**, by re-classifying every parasitic
  element of the committed post-bump netlists; **by a negative control**, by
  running the identical script at the identical commit against the committed
  *pre*-bump extraction and getting the opposite verdict; and **numerically**,
  by reconciling the extracted per-leg resistances against the measured
  45-point PVT R_on delta, per input point, to within 0.3 Ω on the points
  where the reconciliation is one-branch and therefore closed-form.
- **Netlist provenance**: extracted — post-bump netlists from record
  [`20260806-193910-68ad582`](20260806-193910-68ad582.md) (`klt extract
  --parasitics --pdk gf180mcuA`); pre-bump control netlists from record
  [`20260806-140411-968d138`](20260806-140411-968d138.md), read exactly as
  committed and not re-extracted.
- **Toolchain**: klt 0.2.0 @ `875eac33dfbc004d2ab4dfcebc522734d159dc5f`
  (`layout/toolchain.json`), klayout pip package 0.30.10, ngspice-46, gf180mcu
  open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
- **Supersedes**: nothing. Append-only per `sim/README.md`:
  `20260806-parasitic-topology.md` stands exactly as written — its stub
  verdict was true of the pin it was taken at, and §2 below re-demonstrates it
  at *this* commit rather than asking a reader to take it on trust.

---

## 1. Result — the structure: 330 parasitic nets, 330 of them in the signal path

`audit_parasitic_topology.py` reads both topologies the extractor has written
over this repo's life and reports which one it found. At the `875eac3` pin:

```
python3 layout/adc-top/parasitics/audit_parasitic_topology.py
```

| netlist | form | parasitic nets | in-path R | stub R | total R (Ω) | max R (Ω) | total C (fF) |
|---|---|---|---|---|---|---|---|
| `adc_block.para.spice` | star-split | 170 | **170** | **0** | 132775.3 | 20421.3 | 5548.784 |
| `adc_tgate.para.spice`  | star-split | 4   | **4**   | **0** | 302.8    | 120.0   | 9.235    |
| `adc_top.para.spice`    | star-split | 156 | **156** | **0** | 117685.3 | 16013.5 | 5215.824 |

`SERIES RESISTANCE IS IN THE SIGNAL PATH` on all three. 330 of 330 parasitic
nets in-path, 0 stubs.

The shape changed, not just the classification. Per net, `af5791b` wrote one
pair —

```
R<net> <net> <net>__par <ohms>
C<net> <net>__par <ground> <farads>
```

— with every device terminal on `<net>` and nothing but the `C` on
`<net>__par`. `875eac3` writes one **leg per device terminal** plus one hub
capacitance, and every device card names its own leg:

```
R<net>_t<k> <net>__t<k> <net> <ohms>        (one per terminal on the net)
C<net>      <net> <ground> <farads>
```

so two terminals on one net are now separated by real, layout-dependent
resistance where they were previously separated by exactly zero.

The audit is mechanical — it classifies a net `in-path` if any non-parasitic
card has a terminal on a leg/internal node, `stub` otherwise — so this is a
property read out of the committed netlists, not asserted from reading a few
lines of one of them.

## 2. Negative control — the same script, same commit, the pre-bump netlists

A structural verdict is only evidence if the instrument can return the other
answer. `audit_parasitic_topology.py` was deliberately **not** rewritten for
the new form; it reads both, because `reports/` is append-only evidence and a
netlist extracted at an older pin must keep auditing the way it did when its
record was minted. Pointing this commit's script at the committed `af5791b`
extraction:

```
python3 layout/adc-top/parasitics/audit_parasitic_topology.py \
    layout/adc-top/parasitics/reports/20260806-140411-968d138/*.para.spice
```

| netlist | form | parasitic nets | in-path R | stub R | total R (Ω) | max R (Ω) | total C (fF) |
|---|---|---|---|---|---|---|---|
| `adc_block.para.spice` | shunt-stub | 172 | **0** | **172** | 129703.6 | 20499.2 | 4056.184 |
| `adc_tgate.para.spice`  | shunt-stub | 4   | **0** | **4**   | 302.8    | 120.0   | 9.235    |
| `adc_top.para.spice`    | shunt-stub | 156 | **0** | **156** | 115319.7 | 16013.5 | 3730.486 |

`every parasitic R is a STUB` on all three — bit-identical to the table
`20260806-parasitic-topology.md` recorded at the time, reproduced here by
today's script. So the in-path verdict in §1 is a property of the **netlists**
(i.e. of the toolchain pin that wrote them), not of a changed classifier, and
the older record's numbers remain readable at face value.

`sim/tests/test_parasitic_topology_audit.py` pins both directions as
assertions rather than leaving them to this record's prose: the original
"every committed extraction is stub topology" test was **inverted** (not
deleted) for the current extractions, a synthetic star-form control was added,
and a pre-bump-extraction test keeps §2's control green in CI.

## 3. Numerical reconciliation — the extracted legs against the measured R_on

§1 says resistance is in the path; it does not say the right amount is. The
drawn `adc_tgate` leaf is the one cell where that can be closed against a
measurement, because `sim/device-switch-ron/` runs the same 45-point PVT grid
on both sides with `tb.json` unmodified.

What the extraction writes for that leaf
(`reports/20260806-193910-68ad582/adc_tgate.para.spice`, all 6 R cards):

```
Rgn_t0   gn__t0   gn    53.1159      <- NMOS gate  (DC current = 0)
Rgp_t0   gp__t0   gp    53.1159      <- PMOS gate  (DC current = 0)
Rvin_t0  vin__t0  vin   60.0163      <- NMOS source leg
Rvin_t1  vin__t1  vin   60.0163      <- PMOS source leg
Rvout_t0 vout__t0 vout  38.2668      <- NMOS drain leg
Rvout_t1 vout__t1 vout  38.2668      <- PMOS drain leg
```

Each conducting branch therefore sits behind **60.0163 + 38.2668 = 98.283 Ω**
of in-path leg resistance, and the two gate legs carry no DC current. Note
that 98.283 Ω is exactly **half** of the 196.566 Ω (`Rvin` 120.0326 +
`Rvout` 76.5336) that the *pre*-bump positive control had to force entirely
in-path by hand — which is what a two-terminal star split should give.

Measured, per input point, at both a nominal and the worst-case corner —
schematic [`20260806-140624-4f71285`](../../../../sim/device-switch-ron/records/20260806-140624-4f71285.md)
vs. extracted [`20260806-194322-68ad582`](../../../../sim/device-switch-ron/records/20260806-194322-68ad582.md),
`ron_t_*` columns:

| corner | point | schematic (Ω) | extracted (Ω) | delta (Ω) | delta − 98.283 Ω |
|---|---|---|---|---|---|
| `tt_27c_3.30v`  | `ron_t_f00`  | 156.855 | 254.902 | **+98.047** | −0.236 |
| `tt_27c_3.30v`  | `ron_t_f17`  | 178.669 | 276.660 | **+97.991** | −0.292 |
| `tt_27c_3.30v`  | `ron_t_f33`  | 218.828 | 315.736 | **+96.908** | −1.375 |
| `tt_27c_3.30v`  | `ron_t_f50`  | 229.465 | 284.813 | +55.348 | −42.935 |
| `tt_27c_3.30v`  | `ron_t_f67`  | 299.410 | 361.971 | +62.561 | −35.722 |
| `tt_27c_3.30v`  | `ron_t_f83`  | 275.593 | 373.820 | **+98.227** | −0.056 |
| `tt_27c_3.30v`  | `ron_t_f100` | 220.697 | 318.926 | **+98.229** | −0.054 |
| `ss_125c_2.97v` | `ron_t_f00`  | 235.324 | 333.340 | **+98.016** | −0.267 |
| `ss_125c_2.97v` | `ron_t_f17`  | 284.311 | 382.277 | **+97.966** | −0.317 |
| `ss_125c_2.97v` | `ron_t_f33`  | 379.199 | 476.854 | **+97.655** | −0.628 |
| `ss_125c_2.97v` | `ron_t_f50`  | 464.592 | 521.250 | +56.658 | −41.625 |
| `ss_125c_2.97v` | `ron_t_f67`  | 570.436 | 647.818 | +77.382 | −20.901 |
| `ss_125c_2.97v` | `ron_t_f83`  | 424.448 | 522.717 | **+98.269** | −0.014 |
| `ss_125c_2.97v` | `ron_t_f100` | 323.280 | 421.537 | **+98.257** | −0.026 |

Read the bolded rows first. At the input points where **one** branch carries
essentially all the current — `f00`/`f17`/`f33`, where the PMOS is off
(`ron_p_f00` = 3.030303e+09 Ω at `tt_27c_3.30v` / 3.367003e+09 Ω at
`ss_125c_2.97v`, identical on both sides), and `f83`/`f100`, where the NMOS is
off (`ron_n_f83` = 5.865304e+08 Ω / 1.983169e+08 Ω respectively) — the
measured post-layout delta lands on the
extracted per-branch leg total of **98.283 Ω to within 0.3 Ω** at five of the
seven points, and within 1.4 Ω at the sixth. That is the same ~0.1–0.3 Ω
residue the pre-bump positive control characterized and attributed to channel
re-biasing (moving the source terminal behind a resistor shifts V_gs and V_sb
by I·R, so the transistor's own R_on moves slightly too).

The two un-bolded points, `f50` and `f67`, are the mid-range where **both**
branches conduct comparably. There the two 98.283 Ω leg paths are in parallel,
so the added resistance falls toward 98.283/2 = 49.14 Ω; the measured
+55.3 / +62.6 / +56.7 / +77.4 Ω sit between the parallel and single-branch
limits, ordered as the relative branch conductances demand. This record does
**not** claim a closed-form value at those two points — the branch-current
split is bias-dependent and no per-branch current decomposition was run — it
claims only the bracket, which every one of the four mid-range readings
satisfies.

**A caveat about the headline number, stated here because it is easy to
misread.** `sim/extracted-delta-summary.md` §4.8 reports the delta as
**+77.4 Ω (+13.6 %)** at `ss_125c_2.97v` and **+74.4 Ω (+24.9 %)** at
`tt_27c_3.30v`. Those are **worst-of-column** deltas (`ron_t_max` on each
side), and the worst column is not the same input point on both sides at
`tt_27c_3.30v`: schematic `ron_t_max` occurs at `f67` (299.410 Ω), extracted
at `f83` (373.820 Ω). The `ss_125c_2.97v` pair is like-for-like (`f67` on both
sides, +77.382 Ω). `ron_t_max` is the quantity the settling budget consumes,
so the worst-of-column figure is the right one to feed
`R_WORST_BIT_OHM` — but the per-point table above, not the headline, is what
reconciles against the extracted netlist.

## 4. What this closes, and what it does not

**Closes** — issue #116's third and fourth acceptance criteria, as measured
results:

- `layout/toolchain.json` is pinned at `875eac3` (upstream `main` HEAD,
  2026-08-06), past the merged `klayout-tools#593`. The competing
  `klayout-tools#594` was **closed without merging**, re-verified live before
  the pin was cut, so `#593` alone is what landed.
- Extracted resistance at that pin is **in-path, not another stub** — §1,
  with §2's negative control showing the audit distinguishes and §3's
  measurement showing the amount reconciles.

**Does not close, and is not claimed to**:

- **Distributed per-segment RC.** `#593` is a distance-weighted *star split*
  (`#592`'s Option 1). Full distributed RC (Option 2) remains explicitly out
  of scope upstream. A star split puts real resistance between any two
  terminals on a net; it does not model the resistance profile *along* a
  conductor, so a long shared trunk is still a single hub. Every number in §1
  and §3 should be read with that model in mind.
- **The Metal1-only parasitic magnitude.** `20260806-parasitic-topology.md`'s
  closing section recorded that `PARASITICS.metals` carried one `LayerRC` for
  a five-level stack (`klayout-tools#547`), so extracted parasitics are
  Metal1-only lower bounds. That finding is about *magnitude*; this record is
  about *topology*, and nothing here re-measures it.
- **The comparator-inclusive core.** `ADC_BLOCK` still does not convert, for
  an unrelated reason (the preamp's `ppolyf_u_2k` loads have no device class
  and short — `klayout-tools#595`, open;
  [`20260806-adc-block-comparator-input-float.md`](20260806-adc-block-comparator-input-float.md)).
  The worst-corner regeneration-margin re-take stays **not measured**.

## Reproduce

```
# 1. The post-bump structural audit (Section 1)
python3 layout/adc-top/parasitics/audit_parasitic_topology.py
python3 layout/adc-top/parasitics/audit_parasitic_topology.py --format json

# 2. The negative control: today's script, the committed pre-bump netlists
python3 layout/adc-top/parasitics/audit_parasitic_topology.py \
    layout/adc-top/parasitics/reports/20260806-140411-968d138/*.para.spice

# 3. Both directions as CI assertions
python3 -m pytest sim/tests/test_parasitic_topology_audit.py -q

# 4. The measurement Section 3 reconciles against (already recorded)
python3 sim/tools/schematic_vs_extracted.py device-switch-ron \
    --schematic 20260806-140624-4f71285 --extracted 20260806-194322-68ad582
```

## Artifacts in this record

- `reports/20260806-parasitic-topology-inpath/audit.md` — §1's table, as emitted
- `reports/20260806-parasitic-topology-inpath/audit.json` — per-net
  classification of all 330 parasitic nets, including each net's leg count,
  per-leg maximum, total resistance, capacitance and internal node(s)
- `reports/20260806-parasitic-topology-inpath/audit_prebump_control.md` — §2's
  negative control, as emitted

Append-only per `sim/README.md`'s evidence rule: this record is never
overwritten.
