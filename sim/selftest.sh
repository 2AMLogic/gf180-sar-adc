#!/usr/bin/env bash
#
# Harness acceptance test.
#
#   sim/selftest.sh                  unit tests + PVT runs + the negative control
#   sim/selftest.sh --record         also mint evidence records for the PVT runs
#   sim/selftest.sh --quick          unit tests + a single tt/27C/nominal point
#   sim/selftest.sh --require-pdk    fail (instead of skipping) if the PDK is absent
#   sim/selftest.sh --with-sar-logic add the sar-logic testbench (hours, see below)
#
# Stage 4 is the one that matters. Stages 1-3 can all pass while the corner
# runner silently simulates typical everywhere -- the numbers would look
# perfectly plausible and every downstream evidence record would be worthless.
# Stage 4 re-runs the same testbenches with every model section forced to
# typical (`--sabotage-corners`) and requires them to FAIL. If a sabotaged run
# passes, corner switching is not taking effect.
#
# Exit codes: 0 pass (or skipped sim stages), 1 something failed.

set -uo pipefail

SIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Experiments exercised end to end. smoke-sar-bias proves the MOS/temp/supply
# axes; device-cdac-cap proves the capacitor sections, which a MOS-only sweep
# would never touch. Both are needed: sabotaging only one hides the other.
#
# The device-characterization testbenches (#4) are here too, and belong here:
# stage 4 is the only thing that proves their per-axis sensitivity checks can
# actually detect a corner runner stuck on typical, and three of them could NOT
# when first written -- their floors sat on the temperature and supply axes,
# which --sabotage-corners leaves alone. Each now carries a process-axis floor
# because of this stage. A characterization record whose corner sweep is fake
# is worse than no record, because four downstream design issues budget against
# it.
EXPERIMENTS=(
  smoke-sar-bias
  device-cdac-cap
  device-switch-ron
  device-switch-charge-injection
  device-switch-leakage
  device-comparator-gm-id
  device-comparator-flicker-noise
  device-mismatch-mc
  cdac-bit-settling
)

# sar-logic is NOT in the list above, and is opt-in via --with-sar-logic.
#
# It is not exempt from stage 4 -- it carries a process-axis floor on
# tpd_worst_ns for exactly that reason, and it does fail under
# --sabotage-corners. It is out of the default list purely on cost: it is a
# ~1600-MOSFET transient across a 2.45 us window at 45 PVT points, roughly ten
# CPU-minutes per point, so running it twice (stage 3 + stage 4) is hours where
# the whole rest of this script is ~25 minutes. A self-test nobody can afford to
# run is a self-test nobody runs.
#
#   sim/selftest.sh --with-sar-logic        # full acceptance test, hours
#
# The cost is itself the finding DR-0008's fidelity ladder is built on; see
# design/sar-logic/README.md.
OPTIONAL_EXPERIMENTS=(
  sar-logic
)

RECORD=0
QUICK=0
REQUIRE_PDK=0
for arg in "$@"; do
  case "${arg}" in
    --record) RECORD=1 ;;
    --quick) QUICK=1 ;;
    --require-pdk) REQUIRE_PDK=1 ;;
    --with-sar-logic) EXPERIMENTS+=("${OPTIONAL_EXPERIMENTS[@]}") ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: ${arg}" >&2; exit 1 ;;
  esac
done

run_corners() {
  python3 "${SIM_DIR}/run_corners.py" "$@"
}

echo "== 1/4 harness unit tests (no PDK required) =="
if ! python3 -m unittest discover -s "${SIM_DIR}/tests" -t "${SIM_DIR}/tests"; then
  echo "FAIL: harness unit tests"
  exit 1
fi

echo
echo "== 2/4 environment =="
# --check-env distinguishes its two failure modes, and so must we: exit 3 means
# a tool is MISSING (skippable on a machine that has not been bootstrapped),
# exit 1 means everything is installed but a pinned version DRIFTED -- which is
# a real problem and must never be reported as "tools unavailable, skipping".
run_corners --check-env
env_status=$?
case "${env_status}" in
  0) ;;
  1)
    echo
    echo "FAIL: the installed toolchain does not match sim/toolchain.json."
    echo "      Simulation stages skipped deliberately: results from a drifted"
    echo "      toolchain are not comparable with the records already in sim/."
    exit 1
    ;;
  *)
    if [ "${REQUIRE_PDK}" -eq 1 ]; then
      echo "FAIL: ngspice and/or the gf180mcu PDK are not available"
      exit 1
    fi
    echo
    echo "SKIP: simulation stages -- ngspice and/or the gf180mcu PDK are not available."
    echo "      Unit tests passed. Install the PDK (see docs/environment-setup.md)"
    echo "      to run the end-to-end PVT and corner-sensitivity stages."
    exit 0
    ;;
esac

echo
echo "== 3/4 end-to-end PVT runs =="
for experiment in "${EXPERIMENTS[@]}"; do
  echo
  echo "-- ${experiment} --"
  args=("${experiment}")
  if [ "${QUICK}" -eq 1 ]; then
    args+=(--corners tt --temps 27 --supply-tol 0)
  fi
  if [ "${RECORD}" -eq 1 ]; then
    # --quick is deliberately a PVT subset; sim/README.md demands a written
    # reason before a subset run may be recorded as evidence.
    if [ "${QUICK}" -eq 1 ]; then
      args+=(--subset-reason "sim/selftest.sh --quick: single-point harness smoke test, not a spec claim")
    fi
  else
    args+=(--no-write)
  fi
  if ! run_corners "${args[@]}"; then
    echo "FAIL: PVT run for ${experiment}"
    exit 1
  fi
done

if [ "${QUICK}" -eq 1 ]; then
  echo
  echo "SKIP: stage 4 (negative control) -- --quick sweeps a single PVT point,"
  echo "      so there is no corner switching to sabotage. Run without --quick"
  echo "      before trusting any evidence record."
  echo
  echo "PASS (quick): harness plumbing is functional; corner switching NOT verified."
  exit 0
fi

echo
echo "== 4/4 negative control: corner switching must be verifiable =="
echo "Re-running the same testbenches with every model section forced to typical."
echo "Each MUST fail its per-axis sensitivity checks; a pass here means the"
echo "corner runner is not actually switching corners."
sabotage_failures=0
for experiment in "${EXPERIMENTS[@]}"; do
  echo
  echo "-- ${experiment} (sabotaged) --"
  run_corners "${experiment}" --sabotage-corners --quiet
  status=$?
  case "${status}" in
    1)
      echo "ok: ${experiment} correctly FAILED under sabotage"
      ;;
    0)
      echo "FAIL: ${experiment} PASSED with every corner forced to typical."
      echo "      Corner switching is not taking effect, or its sensitivity checks"
      echo "      are too weak to notice. Do not trust any evidence record from"
      echo "      this testbench until this is fixed."
      sabotage_failures=$((sabotage_failures + 1))
      ;;
    *)
      echo "FAIL: ${experiment} errored (exit ${status}) under sabotage instead of"
      echo "      reporting a check failure; the negative control is inconclusive."
      sabotage_failures=$((sabotage_failures + 1))
      ;;
  esac
done

if [ "${sabotage_failures}" -ne 0 ]; then
  echo
  echo "FAIL: ${sabotage_failures} testbench(es) did not detect sabotaged corners."
  exit 1
fi

echo
echo "PASS: harness is functional end to end and corner switching is verified."
