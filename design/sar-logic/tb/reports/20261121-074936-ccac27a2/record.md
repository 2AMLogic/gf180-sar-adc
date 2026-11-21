# Record 20261121-074936-ccac27a2.sar_ctrl.functional_verification_gate_sdf

- **Record ID**: 20261121-074936-ccac27a2.sar_ctrl.functional_verification_gate_sdf
- **Claim**: the post-route gate-level netlist `layout/adc-top/sar_ctrl/sar_ctrl.v` (the one LVS'd
  as `4.digital` and hash-pinned to the #486 receipt) returns the bit-exact expected code for every
  input code 0..1023 in differential and single-ended mode, with every output matching the
  cycle-accurate model every cycle, WHILE back-annotated with each Liberty corner's post-route SDF
  (written from the qualified SPEF by `sdf_sar_ctrl.py`, record `20261121-074733-ccac27a2.mcu7t5v0.sta_sdf`).
  Cited as `7.digital` in `signoff/gf180-sar-adc.manifest.json` (issue #645): the graded citation is
  the setup-binding slowest corner `ss_125C_3v00`; the other four corners are committed beside it.
- **Verdict**: **PASS** -- the bench is `test_sar_ctrl.py` UNMODIFIED from #642 (`5.digital`):
  swapping `sources` to the routed netlist and adding `options.sdf` is the only difference. The
  suite's sensitivity (nine RTL mutants killed) is #642's mutation record; mutation testing is not
  combinable with `options.sdf` (klt rejects the pair), so the gate-level leg carries no mutants of
  its own.

| Corner | Tests | SDF | Icarus-dropped SDF classes | Verdict |
| --- | --- | --- | --- | --- |
| `tt_025C_3v30` | 4/4 | `20261121-074733-ccac27a2.mcu7t5v0.sar_ctrl.tt_025C_3v30.sdf` | iopath_cond_expression×84, iopath_ifnone_edge_modpath×20, timingcheck×44, zero_delay_alias_port_interconnect×11, zero_delay_internal_bus_net_interconnect×75 | PASS |
| `ss_125C_3v00` | 4/4 | `20261121-074733-ccac27a2.mcu7t5v0.sar_ctrl.ss_125C_3v00.sdf` | iopath_cond_expression×84, iopath_ifnone_edge_modpath×20, timingcheck×44, zero_delay_alias_port_interconnect×11, zero_delay_internal_bus_net_interconnect×75 | PASS |
| `ff_n40C_3v60` | 4/4 | `20261121-074733-ccac27a2.mcu7t5v0.sar_ctrl.ff_n40C_3v60.sdf` | iopath_cond_expression×84, iopath_ifnone_edge_modpath×20, timingcheck×44, zero_delay_alias_port_interconnect×11, zero_delay_internal_bus_net_interconnect×75 | PASS |
| `ss_n40C_3v00` | 4/4 | `20261121-074733-ccac27a2.mcu7t5v0.sar_ctrl.ss_n40C_3v00.sdf` | iopath_cond_expression×84, iopath_ifnone_edge_modpath×20, timingcheck×44, zero_delay_alias_port_interconnect×11, zero_delay_internal_bus_net_interconnect×75 | PASS |
| `ff_125C_3v60` | 4/4 | `20261121-074733-ccac27a2.mcu7t5v0.sar_ctrl.ff_125C_3v60.sdf` | iopath_cond_expression×84, iopath_ifnone_edge_modpath×20, timingcheck×44, zero_delay_alias_port_interconnect×11, zero_delay_internal_bus_net_interconnect×75 | PASS |

- **What the dropped classes mean** (all machine-reported by klt, all Icarus limitations, not design
  facts): `timingcheck` -- Icarus implements SDF delays but not SDF timing checks, so no
  `$setup`/`$hold` violation *reporting* exists on this path (slack numbers remain OpenSTA's job,
  #486's receipt); `iopath_cond_expression` / `iopath_ifnone_edge_modpath` -- conditional-path
  IOPATHs whose condition shape Icarus's parser rejects; `zero_delay_*` -- zero-delay entries with
  nothing to annotate. A genuine timing failure still surfaces as a functional failure the bench
  catches, which is this leg's signal.
- **Sampling margin**: the bench drives and samples on falling edges (31.25 ns after the launching
  edge). #486's receipt times the worst reg-to-reg path at ~6.8 ns at the slowest corner (setup
  slack +55.7 ns of the 62.5 ns period; output ports carry no `set_output_delay`, so reg-to-output
  paths are not STA endpoints) -- the direct evidence the sampled outputs settle inside the
  half-cycle is the bench passing every cycle at every corner, which is what the verdict above is.
- **Inputs (sha256)**: netlist `6d32ab0ed1cd1ccb4b1d2c953060afbe3e5947bf634398661c2a04423023304b` (equals the #486 receipt pin); bench
  `690d9aaca0bd3e74ecaf13f2472fba65b8b270c44c16b4fce01f6a36896b1240`; SDFs as pinned per corner above and in `signoff/freshness.json`.
- **Tool versions**: `klt` `klt 0.9.3.dev2575+g6bd18bbc8637`; icarus `13.0`;
  cocotb `2.0.1`; PDK variant `gf180mcuD`
  (open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, resolved via `search_root:~/.ciel`; `--pdk-root` pinned because the install
  search is ambiguous on multi-install hosts). This klt is newer than the flow's `toolchain.json`
  pin (`0.8.0`): the `pdk` request block (klayout-tools #5782) postdates it.
- **Reproducibility**: working tree DIRTY at run time -- re-run against a clean checkout before trusting this record at commit `ccac27a233573881ad0c3786f957031795c26482`.
  Re-run: `python3 design/sar-logic/tb/run_functional_gate.py` with this record's `klt` build first
  on `PATH`. Archived requests resolve their relative paths from this directory (no `--base-dir`
  needed); `environment` paths inside a response are the run host's.
- **Links**: per-corner `fv_request.<corner>.json` / `fv_response.<corner>.json` /
  `results_icarus.<corner>.xml` beside this record; SDFs under
  `design/sar-logic/flow/sar_ctrl/reports/` (`20261121-074733-ccac27a2.*`).
- **Timestamp / author**: 2026-11-21 07:49:36 UTC, `design/sar-logic/tb/run_functional_gate.py` (agent-run)
