# Re-qualification under open_pdks f6eeac7 — timing / switching / sampling group (issue #595)

Part of #515. Old records stay untouched (append-only); each new record names
its `Supersedes` target and carries the fleet job ids in its Environment
section. Pinned PDK: open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`;
fleet engine ngspice 46, `klt sim` backend `aws-batch-fleet`.

## Re-qualified (this PR)

| experiment | new record | supersedes | old-vs-new |
|---|---|---|---|
| timing-budget-closure (schematic) | `20261020-175238-bc92f79` | `20260802-112832-ed9a325` | all 8 measurements identical at all 3 supplies (1 MS/s: 0/0/0/255; 2 MS/s: 0/0/256/257) |
| timing-budget-closure (extracted) | `20261020-175429-bc92f79` | `20260814-220124-f613571` | all 8 measurements identical (1 MS/s: 0/0/0/256; 2 MS/s: 0/0/256/384) |
| acq-leg-width-sweep, x1.0 control | `20261020-180420-c33f4e4` | none — every earlier record is an ERROR record (fleet blocked, no measurement) | no old value to compare; first measured x1.0 point |

No metric moved, so no follow-up decision record is needed from this tranche.
`timing-budget-closure` is a rung-1 ideal-XSPICE deck with no PDK device models
(DR-0010), so identical results are expected; it is re-run because the issue
lists it.

## Not re-qualified, with reason

The batch fleet refused every further submit during this session
(`batch_concurrency_cap`: 15 instances already running, and earlier
`batch_no_capacity`). Per host policy these were not run as local grids.

| experiment | reason |
|---|---|
| acq-leg-width-sweep x1.1, x1.25, x1.5, x1.75, x2.068 | fleet concurrency cap / no capacity |
| dr0014-sampling (7 un-superseded records, incl. two ~2.7 h extracted grids) | not attempted: fleet saturated; a 1-corner batch probe did run (90 s), so the path works |
| vdd-switching-event | not attempted: fleet saturated |
| dr0019-cu-sweep (8 points) | not attempted: fleet saturated |
| track-switch-sampling | **re-qualified under #618** — see the section below |
| track-switch-thd | **re-qualified under #618** — see the section below |
| vcm-drive-impedance | not attempted: fleet saturated |
| vdd-full-pvt, vcm-full-pvt, vdd-drive-impedance | not attempted: fleet saturated; vdd-drive-impedance / vcm-full-pvt have no `c6d73a3` hits and need only a README check |

These remain open under #595 and should be split by experiment (children with
`--parent 595`, `loom:triage`) once the fleet has capacity.

## Re-qualified under #618 (track-switch group)

klayout-tools#4014 shipped `analysis.linearize` and `expr` measurements in the
0.9.0 fleet runner, so `sim/harness/batch.py` now exports a `tran` + `linearize`
+ `let` manifest as one `klt sim` request (a `let` over earlier `.meas` results
becomes a `.meas ... param=` card; the vector `let ph = ...*time` is inlined).
A 1-corner fleet probe of each deck passed before the full grids ran. Both are
117-point grids (13 process x 3 T x 3 V) on open_pdks `f6eeac7`, engine ngspice 46,
runner klt 0.9.0, fleet job ids in each record's Environment section. Records were
taken against a tree whose only uncommitted content was the freshly written
evidence files, so they are flagged "dirty" by the harness.

| experiment | new record | supersedes | old-vs-new |
|---|---|---|---|
| track-switch-thd | `20261105-082853-9de35aa` | `20260817-142956-72d15de` | 35 measurements x 117 points; 7 differ at all, max 0.018 dB (a harmonic near the numerical floor) |
| track-switch-sampling | `20261105-083025-9de35aa` | `20260817-142951-72d15de` | 79 non-droop measurements: max abs delta 0.0009 mV / LSB-scale columns; droop columns differ by < 1 uV (old record shows 0 / 3-digit values, new shows full precision) |

No metric moved beyond tolerance, so no follow-up decision record. Not re-run:
sampling records `20260801-023754-267871b`, `-070046-50bffb1`, `-080221-fa8fd37`
(un-superseded pre-DR-0014 topologies; they describe a superseded design).
