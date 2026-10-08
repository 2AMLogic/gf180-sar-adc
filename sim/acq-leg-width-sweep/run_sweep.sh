#!/usr/bin/env bash
# Intermediate acquisition-leg width sweep (issue #429).
#
# One recorded harness run per width point, each over the SAME 9-point
# (3 process x 3 supply, all 125 C) grid sim/dr0019-cu-sweep/ and
# sim/adc-enob-fft/ use.  C_u is held at the ratified 35.6528 fF; ONLY the
# CDAC cell's fourth-leg (acquisition) T-gate scales.
#
#   ./sim/acq-leg-width-sweep/run_sweep.sh            # all points
#   ./sim/acq-leg-width-sweep/run_sweep.sh 1.25       # one point
#
# HOST RULE: this script never launches ngspice itself.  On a dispatch worker
# ($KLT_SIM_BACKEND=batch) sim/run_corners.py exports each 9-point grid as a
# `klt sim` request and submits it to the Spot batch fleet; a failed submit is
# an error, never a local fallback (sim/harness/batch.py).  A harness FAIL or
# submit error at one point is DATA and does not abort the remaining points.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

CU="35.6528"
VARIANT_DIR="sim/.work/acq-leg-width-sweep/variants"
TIMEOUT="${TIMEOUT:-7200}"
# KLT_CMD: e.g. "uvx --from klayout-tools==0.5.0 klt" for a throwaway client matching the fleet runner image.
SCALES=(1.0 1.1 1.25 1.5 1.75 2.068)

SUBSET_REASON="Two-stage corner strategy, spec/testbench-suite-memo.md Sec 5, \
kept UNCHANGED from sim/adc-enob-fft/ and sim/dr0019-cu-sweep/ so every width \
point is point-for-point comparable with them. 125 C is the temperature the \
settling/linearity-worst ss_125c_2.97v corner sits at; full process and \
supply axes are swept, only temperature is reduced."

only="${1:-}"
results=()
for scale in "${SCALES[@]}"; do
  if [ -n "$only" ] && [ "$only" != "$scale" ]; then continue; fi
  tag="sw${scale}"
  # Provenance wording is parsed by sim/dr0019-cu-sweep/analyze_sweep.py.
  prov="schematic (acquisition-leg width sweep, issue #429: C_u = ${CU} fF with the CDAC cell's fourth-leg (acquisition) T-gate width scaled x${scale})"
  note="ACQUISITION-LEG WIDTH POINT x${scale} (issue #429): C_u is the ratified \
${CU} fF and the ONLY deviation from the ratified deck is the CDAC cell's \
fourth-leg (input/acquisition) T-gate, scaled x${scale} from 10u/20u. \
Release / V_REF / GND legs and the top-plate switch keep the ratified geometry. \
x1.0 is the regenerated control and reproduces the ratified deck \
byte-for-byte (gen_cu_variant.py --verify-baseline). Schematic-level, 125 C \
subset: NOT the governing extracted performance."
  variant="${VARIANT_DIR}/tb_${tag}.spice"
  mkdir -p "$VARIANT_DIR"
  python3 sim/dr0019-cu-sweep/gen_cu_variant.py \
    --c-unit-ff "$CU" --acq-switch-scale "$scale" --out "$variant"
  echo "=== width point ${tag} ==="
  status=0
  python3 sim/run_corners.py acq-leg-width-sweep \
    --netlist "$variant" \
    --netlist-provenance "$prov" \
    --corners tt ss ff \
    --temps 125 \
    --subset-reason "$SUBSET_REASON" \
    --note "$note" \
    --timeout "$TIMEOUT" \
    --klt-cmd "${KLT_CMD:-klt}" \
    --runner-version-check "${RUNNER_VERSION_CHECK:-enforce}" \
    --quiet || status=$?
  echo "=== width point ${tag}: run_corners.py exit ${status}"
  results+=("${tag} exit=${status}")
done
printf '  %s\n' "${results[@]}"
echo "Collate: python3 sim/acq-leg-width-sweep/analyze_width_sweep.py --markdown"
