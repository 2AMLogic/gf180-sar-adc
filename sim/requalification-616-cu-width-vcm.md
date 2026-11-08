# Re-qualification under open_pdks f6eeac7 — C_u / acquisition-width / V_cm drive group (issue #616)

Part of #595 (grandparent #515). Old records stay untouched (append-only); each
new record names its `Supersedes` target and carries the fleet job id in its
Environment section (`Executed via`). Pinned PDK: open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. Every new record reports the
**runner's** PDK as `f6eeac7d...` (client klt `0.9.2.dev299+ge5ccedae13f0`, runner klt
`0.9.0` [match], engine ngspice 46, backend `aws-batch-fleet`); this is the check
the earlier parks of this issue were waiting on (klayout-tools#4020).

All 16 points ran on the Spot batch fleet through `sim/run_corners.py --backend
batch` (submits went through `klt sim --wait-for-capacity 600`). Nothing ran as a
local grid. Each point's corner grid is the one its sweep script already defines
(vcm-drive-impedance: 7 `cdac` corners at 27 C / 3.30 V; acq-leg-width-sweep and
dr0019-cu-sweep: tt/ss/ff x 3 supplies at 125 C), so old and new are
point-for-point comparable. `vcm-drive-impedance` ran with `--timeout 3660`
(the earlier 1800 s limit timed out the 1100 ohm / ideal points).

## Re-qualified (this PR)

### vcm-drive-impedance

| point | new record | supersedes | fleet job | measurements changed | largest change (old -> new) |
|---|---|---|---|---|---|
| ideal (Z=0) | `20261108-220820-3b60e1b` | `20260825-162620-e09a2d0` | `klt-sim-997e7a365961` | 36 / 83 | `vref_droop_mv` min: 0.351 -> 0.35161 |
| budget (Z=220 ohm, 40 nF) | `20261108-220424-3b60e1b` | `20260825-163251-cb36f0a` | `klt-sim-73fbbabf3e77` | 21 / 83 | `vref_droop_mv` min: 0.351 -> 0.351515 |
| 5x-over-budget (Z=1100 ohm, 40 nF) | `20261108-221026-3b60e1b` | `20260825-163508-64203b5` | `klt-sim-d6a988aa5e88` | 24 / 83 | `vref_droop_mv` mean: 0.376571 -> 0.376176 |

### acq-leg-width-sweep

| point | new record | supersedes | fleet job | measurements changed | largest change (old -> new) |
|---|---|---|---|---|---|
| x1.1 | `20261108-221350-3b60e1b` | `20261031-200740-51e89c5` | `klt-sim-5a561e85f9ba` | 0 / 75 | none |
| x1.25 | `20261108-221813-3b60e1b` | `20261031-204539-51e89c5` | `klt-sim-b4d09455443b` | 0 / 75 | none |
| x1.5 | `20261108-222405-3b60e1b` | `20261031-204606-51e89c5` | `klt-sim-878487527e99` | 0 / 75 | none |
| x1.75 | `20261108-222856-3b60e1b` | `20261031-204610-51e89c5` | `klt-sim-9551c30e9dad` | 0 / 75 | none |
| x2.068 | `20261108-223322-3b60e1b` | `20261031-204614-51e89c5` | `klt-sim-bbd939d0ead7` | 0 / 75 | none |

### dr0019-cu-sweep

| point | new record | supersedes | fleet job | measurements changed | largest change (old -> new) |
|---|---|---|---|---|---|
| C_u 17.24 fF | `20261108-223745-3b60e1b` | `20260817-131658-9b8498f` | `klt-sim-319d95d44f33` | 3 / 75 | `vref_droop_mv` max: 2.055 -> 2.04965 |
| C_u 22.0 fF | `20261108-224159-3b60e1b` | `20260817-133432-77fd05c` | `klt-sim-48eed541657f` | 6 / 75 | `vref_droop_mv` max: 2.562 -> 2.56836 |
| C_u 26.0 fF | `20261108-234207-3b60e1b` | `20260817-135204-7aea936` | `klt-sim-2889f52cf820` | 6 / 75 | `code_s006` mean: 461.333 -> 461.222 |
| C_u 30.0 fF | `20261108-231940-3b60e1b` | `20260817-140653-692daba` | `klt-sim-2b60d4a8b43a` | 11 / 75 | `code_s009` mean: 699.556 -> 699.444 |
| C_u 33.0 fF | `20261108-232354-3b60e1b` | `20260817-142130-1292176` | `klt-sim-41f8bf2925a6` | 10 / 75 | `code_s048` mean: 936.556 -> 936.444 |
| C_u 35.6528 fF | `20261108-232808-3b60e1b` | `20260817-144622-70a6345` | `klt-sim-f7a727e92d62` | 7 / 75 | `code_s010` mean: 280.333 -> 280.222 |
| C_u 42.0 fF | `20261108-233246-3b60e1b` | `20260817-150327-ccee900` | `klt-sim-b56359092bf2` | 6 / 75 | `decerr_c008_lsb` min: 623.31 -> 623.318 |
| C_u 35.6528 fF, acq x2.068 (control) | `20261108-233702-3b60e1b` | `20260817-152151-7024f8d` | `klt-sim-635ad0cddcd1` | 9 / 75 | `code_s003` mean: 423 -> 422.889 |

"Measurements changed" counts the per-measurement min / max / mean entries of the
record's "Spread across the grid" table that differ at all between the old and
new record; the largest change is the biggest absolute difference among them.

## Old-vs-new delta

No metric moved beyond tolerance, so no follow-up issue or decision record is
needed from this tranche, and no spec limit was touched.

- `acq-leg-width-sweep` x1.1 .. x2.068: all 75 measurements identical at every
  corner (min, max and mean), for all five points.
- `dr0019-cu-sweep`: 3 to 11 of 75 measurements differ per point, by at most one
  ADC code in one of nine corners (a mean shifting 0.111, i.e. 1 count / 9
  corners; relative change <= 4e-4) or by sub-millivolt `vref_droop_mv` /
  micro-LSB `decerr_*_lsb` differences (relative <= 2.6e-3).
- `vcm-drive-impedance`: 21 to 36 of 83 measurements differ per point, the largest
  on `vref_droop_mv` (<= 0.0006 mV, relative <= 1.7e-3).

The old `acq-leg-width-sweep` x1.1 .. x2.068 records (`20261031-*-51e89c5`) printed
`f6eeac7d...` as their PDK line, but at the time the fleet runner did not report the
PDK it used (klayout-tools#4020), so that line only described the client. The
identical values above are consistent with the runner having used the same models
then; this tranche is the first set whose runner PDK is reported by klt itself.

## Notes on the old records compared against

- `acq-leg-width-sweep` x1.25, x1.5, x1.75, x2.068: the superseded records
  (`20261031-204539/204606/204610/204614-51e89c5`) were taken against a dirty
  working tree and are flagged "not citable as a clean-tree result". They were the
  only valid-looking record for those scales, so they are the comparison base, with
  that caveat. x1.0 control (`20261020-180420-c33f4e4`, PR #603) was not re-run.
- All 15 other old records are listed in the tables above; none was edited.

## Dirty-tree flag on the new records

The first record written (`vcm-drive-impedance` budget, `20261108-220424-3b60e1b`) was
taken against a clean tree. The other 15 were run in the same worktree afterwards,
whose only uncommitted content was the freshly written evidence files of the earlier
points of this same tranche (records and `manifests/artifacts/*.manifest.json`;
no tracked file was modified), so the harness flags them "dirty". The commit is
the same for all 16 (`3b60e1b9`), and the netlists are the checked-in or
regenerated ones recorded in each record's netlist snapshot.

## Not re-qualified, with reason

None. Every point listed in the issue (3 + 5 + 8) was run on the fleet. One
submission needed a repeat: the first `dr0019-cu-sweep` C_u 26.0 fF job returned
no runner klt version and the harness refused to record it (`the fleet runner's klt
differs from the client's (None vs ...)`, nothing recorded); the immediate re-submit
produced `20261108-234207-3b60e1b` (fleet job `klt-sim-2889f52cf820`).

## How to re-run

`python3 sim/run_corners.py <experiment> --backend batch --supersedes <old-record-id>`
with the per-point arguments in `sim/<experiment>/run_sweep.sh` (which does not pass
`--supersedes` itself), `--timeout 3660` or more for `vcm-drive-impedance`.
