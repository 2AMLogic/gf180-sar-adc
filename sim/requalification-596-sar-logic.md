# Re-qualification under open_pdks f6eeac7 — SAR-logic / extraction flow group (issue #596)

Part of #515 (grandparent #513); this PR is **partial** — see "Not re-qualified".
Old records stay untouched (append-only); each new record names its
`Supersedes` target and carries the fleet job ids in its Environment section.
Pinned PDK: open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`; fleet engine
ngspice 47, `klt sim` backend `aws-batch-fleet`, client klt 0.9.2.dev885.

Harness change: `sim/harness/batch.py` now passes `--wait-for-capacity 600` on
every batch submit (it previously failed immediately on `batch_no_capacity`).

## Re-qualified (this PR)

| experiment | new record | supersedes | old-vs-new |
|---|---|---|---|
| sar-logic-functional (rung-1 ideal XSPICE, 3 supplies) | `20261113-080421-3eed6a0` | `20260802-110241-131989b` | PASS. All 1023/0 codes, ±0 LSB error, conv_period 1000 ns, acq_window 187.522 ns unchanged; iso_gap 62.2133–62.2145 ns vs 62.2133–62.2137 ns (<0.001 ns); `sw_conflict` ~4.2e-14 vs ~4.2e-14 (limit 0.02). No metric moved beyond tolerance. |

`sar-logic-timing` already has a record under `f6eeac7`
(`20261031-191202-befcce4`, superseding `20260802-102758-d8a363d`); not repeated.

## Attempted, no usable evidence

| experiment | record | outcome |
|---|---|---|
| sar-logic-functional-gates, full 45-point grid | `20261113-080712-3eed6a0` | all 45 points `ngspice timed out after 300s` (default per-point timeout too short for the 64-conversion gate-level deck). ERROR record kept as evidence of the attempt; supersedes nothing. |
| sar-logic-functional-gates, 5-point subset, `--timeout 3600` | none written | fleet accepted job `klt-sim-bd0053dc48eb` but it did not launch within the 600 s capacity wait; harness wrote nothing and nothing ran locally. |

## Not re-qualified, with reason

| scope | reason |
|---|---|
| sar-logic-functional-gates (needs a fleet slot that launches) | fleet capacity, above; retry with `--timeout 3600` and the 5-point subset command in the table |
| sar-logic-timing-gates, -ok, -bad, -lt, -tie, -xl (45-point gate-level grids) | not attempted: same gate-level deck class as the above, which could not get a fleet slot; each needs a long `--timeout` |
| `design/sar-logic/flow/**` (STA/synth/P&R), `layout/adc-top/parasitics/**`, `layout/lvs/**` | not `klt sim` flows; need the heavy (OpenROAD) fleet slice, capacity-refused as of 2026-11-13 (2am#6548) and no driver exists in this repo yet. LVS `--check` must record the klayout-tools#1063 net-numbering non-determinism caveat. |
| `signoff/testbench-inventory.*.json` | provenance pointers only; defer until the records they point at exist |

These remain open under #596 and should be split by experiment/flow into
`Part of #596` children once the fleet has capacity. No metric moved beyond
tolerance in the one re-qualified record, so no follow-up decision record is
needed from this tranche.
