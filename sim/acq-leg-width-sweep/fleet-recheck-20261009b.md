# Issue #429 -- spectral sweep fleet re-check, second probe (2026-10-09)

Blocker evidence only; no measurement. Follows `fleet-recheck-20261009.md` (not edited).

- Base commit `87360110` (main), clean tree. Request: `KLT_CMD="uvx --from klayout-tools==0.6.0 klt" RUNNER_VERSION_CHECK=warn ./sim/acq-leg-width-sweep/run_sweep.sh 1.0` (x1.0 control, 9 points, 125 C, `KLT_SIM_BACKEND=batch`). Only this probe point was submitted.
- Outcome: fleet job `klt-sim-a75a6adf15c1` accepted, then all 9 points failed with
  `Error: Could not find include file /home/ubuntu/.volare/gf180mcuD/libs.tech/ngspice/design.ngspice` / `fatal error in ngspice, exit(1)`.
  Append-only ERROR record: `records/20261009-094741-8736011.md` (collator skips it).
- Reading: unchanged from the earlier probe; the already-filed PDK-include-path friction (2AMLogic/klayout-tools#2882). Nothing new filed. No local ngspice fallback was run (host rule); the remaining five widths were not submitted.
- Ratified Area/ENOB/SFDR rows and `findings-20261008.md` conclusions are unchanged: the Area failure remains at every width including the 1x control, and no SFDR/ENOB value exists for any intermediate width.
