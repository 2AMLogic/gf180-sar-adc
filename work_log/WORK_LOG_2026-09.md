# Work Log Archive — 2026-09

Sections moved byte-for-byte from [WORK_LOG.md](../WORK_LOG.md) by `loom-daemon work-docs archive`.

### 2026-09-16

- **PR #302**: docs(DR-0027): fix garbled lead-in sentence mixing units
- **PR #300**: fix: accept bounded gate-decode one-hot hazard via decision record (DR-0027)
- **PR #299**: docs: root-cause the gate-level sw_conflict one-hot violation
- **Issue #301** (closed): docs(DR-0027): fix garbled lead-in sentence mixing ns-per-day / ps-per-conversion units
- **Issue #298** (closed): fix: real gate-delay hazard in sar_ctrl_a switch decode (rel_n races sel_in_n)
- **Issue #295** (closed): Gate-level SAR switch-decode one-hot invariant violated on every corner tested (sw_conflict_se/df, DR-0014)

### 2026-09-15

- **PR #297**: feat(sar-logic): execute and record the gate-level SPICE replay corner grid (#289)
- **PR #294**: fix(loom): break SIGPIPE/pipefail false-MISS in verify-proposal-refs.sh
- **PR #293**: fix(ci): stop pruning libs.ref from cached gf180mcu PDK in nightly-pdk.yml
- **PR #290**: fix(sar-logic): declare vdd_gate .global in translated gate netlists (#282)
- **PR #288**: fix: isolate gate-netlist drift test from committed synth output
- **PR #286**: layout(adc-top): refresh the stale "Area, as drawn" table against live area.json
- **PR #285**: refactor: remove unused label() function from geometry.py
- **PR #283**: Scaffold gate-level SAR-sequencer SPICE replay testbenches (#273)
- **PR #279**: DR-0023 follow-on (b): place-and-route the SAR sequencer gate netlist
- **PR #278**: feat: pre-route STA evidence for sar_ctrl_a vs DR-0003's 62.5 ns budget
- **Issue #292** (closed): verify-proposal-refs.sh false-flags real files as MISSING via SIGPIPE/pipefail bug
- **Issue #291** (closed): Nightly PDK check failed (sim/selftest.sh stages 2-4)
- **Issue #289** (closed): Execute and record the sar-logic gate-level SPICE replay corner-grid now that #282 unblocks it
- **Issue #287** (closed): check:ci's gate-netlist drift test mutates the working tree (yosys version drift, unrelated file changes land as a side effect)
- **Issue #284** (closed): Remove unused geometry.label() Metal1 helper
- **Issue #282** (closed): Gate-level SPICE replay of the SAR sequencer does not reach a valid digital operating point (blocks #273's corner-grid run)
- **Issue #280** (closed): layout/adc-top/README.md's 'Area, as drawn' table is stale against area.json
- **Issue #277** (closed): Complete the mos-corner-grid temperature/supply axes for sim/sar-logic-timing-gates/ (issue #273 follow-on)
- **Issue #275** (closed): DR-0023 follow-on (c): STA closure for the SAR sequencer gate netlist (klt sta)
- **Issue #274** (closed): DR-0023 follow-on (b): place-and-route the SAR sequencer gate netlist (klt place-and-route)
- **Issue #273** (closed): Gate-level functional/timing corner-grid replay for the SAR sequencer (issue #272 continuation)
- **Issue #272** (closed): Synthesize the SAR sequencer to a gf180mcu gate-level netlist (DR-0023 follow-on (a): RTL + `klt synthesize`, rung-1 replay as equivalence evidence)

### 2026-09-14

- **PR #276**: feat: synthesize the SAR sequencer RTL to a gf180mcu gate-level netlist
