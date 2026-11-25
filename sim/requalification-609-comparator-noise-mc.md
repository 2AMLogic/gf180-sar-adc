# Re-qualification under open_pdks f6eeac7 — comparator offset-gof / offset-mc / preamp-noise (issue #609)

Part of #593. Old records stay untouched (append-only). Pinned PDK: open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the host's `~/.ciel/gf180mcuD`
`SOURCES` matches it). Submitting client: `klt 0.9.2.dev271+gbb7f8c253c87`
(`aws-batch-fleet` backend). Fleet runner klt: `0.9.0`.

## Re-qualified

| experiment | new record | supersedes | job ids | result |
|---|---|---|---|---|
| comparator-preamp-noise | `20261108-031240-6ba19f6` | `20260806-233123-56be937` (latest of the three old records, `90d7e67` / `033b56b` / `56be937`, all under `c6d73a3`) | `klt-sim-c34c71935837`, `klt-sim-cfa9a305ab07`, `klt-sim-ccbc1852b4ac` (one per supply; runner klt 0.9.0 [match], ngspice 46, runner PDK `f6eeac7`) | 45/45 points ok, PASS |

Submitted from the host's klt `0.9.2.dev271+gbb7f8c253c87` with
`python3 sim/run_corners.py comparator-preamp-noise --backend batch --supersedes 20260806-233123-56be937`,
through a one-line `klt` wrapper outside the repo that appends
`--wait-for-capacity 600` to `klt sim` (the harness has no such option). The
fleet runner image now carries `analysis_steps` (klayout-tools#3516 closed
2026-11-07 after a live 15-corner check on launch template v10), which is what
the earlier `2026-10-20` submit (ERROR record `20261020-212535-0a6694a`) lacked.

Old-vs-new, `20260806-233123-56be937` (`c6d73a3`) against `20261108-031240-6ba19f6`
(`f6eeac7`): every min / max / mean / spread for all eight measurements, and
every per-axis sensitivity range, is identical to the printed precision (e.g.
`vn_in_uv` 76.6562 .. 143.698, mean 105.148; `white_nv_rthz` 200.779 .. 327.496;
`av_dc` 10.0812 .. 22.4784). No metric moved, so there is no delta table to
file and no follow-up decision record. The older `033b56b` / `90d7e67` records
differ slightly (`vn_in_uv` max 153.223), a difference that predates this
change: `56be937` already sat at the new values under `c6d73a3`.

## Not re-qualified, with reason

| experiment | records in scope | reason |
|---|---|---|
| comparator-offset-gof | 2 | Not expressible as the same experiment. The deck is `setseed 20260801` plus a 300-iteration `reset` / `dc` draw loop that prints every draw. `klt sim` `monte_carlo` derives its own per-sample seed and runs one ngspice process per sample, so the draw sequence is not preserved and the result would be a different population. The fleet's klt 0.7.0 also lacks `monte_carlo.seed_scope`. |
| comparator-offset-mc | 4 (3 corner-matrix, 1 `klt yield` reformat) | Same capability gap as offset-gof, at 45 corners x 150 draws. The yield record (`20260816-050504-66a0e2e`) reformats `20260816-050001-d002e66` and runs no simulation of its own, so it is superseded through that record. |

Offset decks, capability stated generically: a testbench that depends on a
single seeded draw sequence (`setseed` plus a loop that prints every draw) has
no `klt sim` equivalent that reproduces the same population; `monte_carlo`
runs one ngspice process per sample. A different population would not be a
re-qualification of the old record, so these stay listed here. Whether a
`monte_carlo.seed` request can express an equivalent experiment is a design
decision for a separate issue, not this tranche.

## Tooling and records (this tranche, including #612)

* `klt_sim` manifest block (`sim/harness/testbench.py`, `sim/harness/batch.py`):
  a testbench may state its `analysis_steps` / derived `measurements` so a deck
  the single-analysis export refuses can still ship to the fleet. The local
  runner ignores it; a manifest that omits it behaves as before. Unit tests in
  `sim/tests/test_batch.py` (`KltSimStepsTests`).
* `comparator-preamp-noise/testbench/tb.json` carries that block.
* The new record `20261108-031240-6ba19f6` and its artifact manifest.
* The ERROR record `20261020-212535-0a6694a` stays as evidence of the earlier
  blocked submit (runner klt 0.7.0 predated `analysis_steps`). Its "toolchain
  drift" banner (ngspice `unknown`) is the harness reporting that no point
  completed.

The spec was not touched.
