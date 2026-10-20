# Re-qualification under open_pdks f6eeac7 — comparator offset-gof / offset-mc / preamp-noise (issue #609)

Part of #593. Old records stay untouched (append-only). Pinned PDK: open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the host's `~/.ciel/gf180mcuD`
`SOURCES` matches it). Submitting client: `klt 0.7.1.dev2334+gbe9ee5c7010b`
(`aws-batch-fleet` backend). Fleet runner klt: `0.7.0`.

## Re-qualified (this PR)

None. No experiment in scope produced a measured `f6eeac7` record.

## Not re-qualified, with reason

| experiment | records in scope | reason |
|---|---|---|
| comparator-preamp-noise | 3 | Expressible: the deck maps onto `klt sim` `analysis_steps[]` (two `noise` steps and an `ac` step, derived measurements). A one-corner local probe (tt, 27 °C, 3.3 V) gave `vn_in_uv` 101.36, `av_dc` 15.76, `white_nv_rthz` 261.65, `enbw_mhz` 37.29, inside the old records' ranges (`vn_in_uv` 76.7–143.7). The 45-point batch submit, record `20261020-212535-0a6694a`, **failed on every point**: the fleet runner's klt is 0.7.0, which predates `analysis_steps` (`job command exited 87`; jobs `klt-sim-736fef13dbfa`, `klt-sim-21cf67fca95d`, `klt-sim-564b5226e235`). Per host policy the grid was not run locally. Re-run `python3 sim/run_corners.py comparator-preamp-noise --backend batch --supersedes 20260801-123440-033b56b` once the fleet image carries `analysis_steps`. |
| comparator-offset-gof | 2 | Not expressible as the same experiment. The deck is `setseed 20260801` plus a 300-iteration `reset` / `dc` draw loop that prints every draw. `klt sim` `monte_carlo` derives its own per-sample seed and runs one ngspice process per sample, so the draw sequence is not preserved and the result would be a different population. The fleet's klt 0.7.0 also lacks `monte_carlo.seed_scope`. |
| comparator-offset-mc | 4 (3 corner-matrix, 1 `klt yield` reformat) | Same capability gap as offset-gof, at 45 corners x 150 draws. The yield record (`20260816-050504-66a0e2e`) reformats `20260816-050001-d002e66` and runs no simulation of its own, so it is superseded through that record. |

Missing capability, stated generically (upstream: 2AMLogic/klayout-tools#3516,
live recurrence commented 2026-10-20): the batch fleet runner image lags the
submitting client's klt, so `analysis_steps[]` and the newer Monte Carlo
request fields are rejected at job time, after the instance launch.

## What this PR adds

* `klt_sim` manifest block (`sim/harness/testbench.py`, `sim/harness/batch.py`):
  a testbench may state its `analysis_steps` / derived `measurements` so a deck
  the single-analysis export refuses can still ship to the fleet. The local
  runner ignores it; a manifest that omits it behaves as before. Unit tests in
  `sim/tests/test_batch.py` (`KltSimStepsTests`).
* `comparator-preamp-noise/testbench/tb.json` carries that block.
* The ERROR record `20261020-212535-0a6694a` as evidence of the blocked submit.
  Its "toolchain drift" banner (ngspice `unknown`) is the harness reporting that
  no point completed, so no engine banner was read; it is not a local drift.

No metric was measured on the fleet, so there is no old-vs-new delta table and
no follow-up decision record. The spec was not touched.
