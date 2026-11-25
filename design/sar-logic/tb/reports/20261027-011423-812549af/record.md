# Record 20261027-011423-812549af (sar_ctrl functional verification)

- **Record ID**: 20261027-011423-812549af.sar_ctrl.functional_verification
- **Claim**: `design/sar-logic/rtl/sar_ctrl.v` (`sar_ctrl_a`) returns the bit-exact expected code for every
  input code 0..1023 in differential and single-ended mode, and every output (sampling window, drdy, all 54
  switch legs, c9..c0) matches an independent cycle-accurate model on every cycle. Cited as `5.digital` in
  `signoff/gf180-sar-adc.manifest.json` (issue #642), next to the multi-corner `klt sta` record.
- **Verdict**: **PASS** -- 4/4 tests passed;
  mutation testing killed 9/9 valid mutants (score 1.0).

| Test | Status | Sim time (ns) |
| --- | --- | --- |
| `test_all_codes_differential` | passed | 1025156 |
| `test_all_codes_single_ended` | passed | 1025156 |
| `test_free_running_wrap` | passed | 6031 |
| `test_start_restarts_mid_conversion` | passed | 2594 |

- **Why the suite can fail**: `design/sar-logic/tb/sar_ctrl.mutation_proposals.json` mutates the RTL nine ways (restart clear,
  sample window, comparator polarity, drdy, a stuck bit, LSB timing, an n-side leg, a gating term, an output
  wiring); every mutant is killed (`mutation_response.json`).
- **Scope**: zero-delay RTL only. The gate-level / SDF re-run is item 7 (#645) and reuses `test_sar_ctrl.py`
  with a different `sources` list.
- **Tool versions**: `klt` `klt 0.7.1.dev1744+g44cc42323184`; icarus 13.0;
  cocotb 2.1.0; random seed 642.
- **Reproducibility**: commit `812549af50cc224ae3520af9d1023f572857c39b`; re-run with
  `python3 design/sar-logic/tb/run_functional.py` (response `environment` paths are the run host's).
- **Links**: `design/sar-logic/tb/reports/20261027-011423-812549af/fv_response.json`, `design/sar-logic/tb/reports/20261027-011423-812549af/results_icarus.xml`, `design/sar-logic/tb/reports/20261027-011423-812549af/mutation_response.json`;
  request `design/sar-logic/tb/sar_ctrl.fv_request.json`; bench `design/sar-logic/tb/test_sar_ctrl.py`.
- **Timestamp / author**: 2026-10-27 01:14:23 UTC, `design/sar-logic/tb/run_functional.py` (agent-run)
