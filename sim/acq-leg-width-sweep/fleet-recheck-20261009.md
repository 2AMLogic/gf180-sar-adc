# Issue #429 -- spectral sweep fleet re-check (2026-10-09)

Blocker evidence only; no measurement. Follows `findings-20261008.md` section 3 (not edited).

- Base commit `44baac57` (main), clean tree. Host client `klt 0.7.0`; submitted with the throwaway client `uvx --from klayout-tools==0.6.0 klt` and `--runner-version-check warn`, `KLT_SIM_BACKEND=batch`.
- Request: `./sim/acq-leg-width-sweep/run_sweep.sh 1.0` (x1.0 control, 9 points, 125 C). Only this point was submitted; the other five were not, because the probe failed.
- Outcome: fleet job `klt-sim-baf742e6dc92` (m7i.4xlarge spot, us-east-1c) was accepted (no capacity refusal, no runner/client refusal), then `state failed`: all 9 points hit
  `Error: Could not find include file /home/ubuntu/.volare/gf180mcuD/libs.tech/ngspice/design.ngspice` / `fatal error in ngspice, exit(1)`.
  Record kept as append-only ERROR evidence: `records/20261009-032254-44baac5.md` (the collator skips it).
- Reading: the already-filed PDK-include-path friction (2AMLogic/klayout-tools#2882) for this schematic deck. The extracted #430 deck passed the same fleet earlier today, so the cause is deck- or runner-image-specific, not a repo change here. Nothing new filed.
- No local ngspice fallback was run (host rule). Ratified Area/ENOB/SFDR rows and the `findings-20261008.md` conclusions are unchanged.
- Resume: once #2882 is fixed or the fleet rewrites this deck's PDK include, run `./sim/acq-leg-width-sweep/run_sweep.sh` then `analyze_width_sweep.py --markdown`.
