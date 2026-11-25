# shellcheck shell=bash
# Shared point-loop driver for the one-run_corners.py-per-point sweeps:
#   sim/dr0019-cu-sweep/run_sweep.sh      (DR-0019 C_u isolation, issue #211)
#   sim/acq-leg-width-sweep/run_sweep.sh  (acquisition-leg width,  issue #429)
#   sim/vcm-drive-impedance/run_sweep.sh  (V_cm drive impedance,   issue #260)
#
# SOURCED, never executed. Each run_sweep.sh is a thin wrapper that keeps its
# own path (records and docs cite it for reproduction), its POINTS table,
# SUBSET_REASON, provenance/note prose and variant generation, and ends with
# `sweep_main "$@"`. Sibling of sim/full_pvt_common.sh, which does the same
# for the paired-arm full-PVT campaigns.
#
# What lives here, identically for every sweep: repo-root `cd`, selection of
# one point by tag (`$1`), rejection of an unknown selector (exit 2, nothing
# run), the `status=0 ... || status=$?` capture, the per-point exit line, the
# summary, and a non-zero exit when any point failed. A failing point is DATA
# and never stops the later ones. run_corners.py arguments common to all
# sweeps (--timeout, -j, --ngspice-threads, --klt-cmd,
# --runner-version-check, --quiet) are assembled once, in sweep_run_corners.
#
# Environment knobs (every sweep honours all of them):
#   TIMEOUT                 per-corner ngspice timeout, seconds
#   JOBS / NGSPICE_THREADS  passed as -j / --ngspice-threads when non-empty
#   KLT_CMD                 batch-dispatch hosts: the `klt` invocation handed
#                           to run_corners.py --klt-cmd (e.g. a throwaway
#                           version-matched client,
#                           'uvx --from klayout-tools==0.5.0 klt')
#   RUNNER_VERSION_CHECK    handed to --runner-version-check when non-empty
# The wrapper sets its own defaults BEFORE sourcing this file, e.g.
#   JOBS="${JOBS:-9}"; TIMEOUT="${TIMEOUT:-7200}"
#
# The wrapper must define, before calling sweep_main:
#   POINTS                   array, one row per point
#   sweep_describe row       -- set SWEEP_TAG (the point's unique tag) and, if
#                               the point is also selectable by something else
#                               (e.g. a shared C_u), SWEEP_ALIASES (array)
#   sweep_run_point row      -- print the banner, generate any variant, call
#                               sweep_run_corners, and return run_corners.py's
#                               status. Do NOT rely on `set -e` inside it (it
#                               runs in an `||` context): chain with
#                               `|| return $?`.
# Optional: SWEEP_EPILOGUE (a line printed after the summary).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

JOBS="${JOBS:-}"
NGSPICE_THREADS="${NGSPICE_THREADS:-}"
KLT_CMD="${KLT_CMD:-}"
RUNNER_VERSION_CHECK="${RUNNER_VERSION_CHECK:-}"
SWEEP_EPILOGUE="${SWEEP_EPILOGUE:-}"

# Set by sweep_gen_variant when run_corners.py was never reached.
SWEEP_NOT_RUN=0

# sweep_run_corners <experiment> [point-specific run_corners.py args...]
# Appends the arguments every sweep shares and runs the harness.
sweep_run_corners() {
  local exp=$1; shift
  local args=("$exp" "$@" --timeout "$TIMEOUT")
  if [ -n "$JOBS" ]; then args+=(-j "$JOBS"); fi
  if [ -n "$NGSPICE_THREADS" ]; then args+=(--ngspice-threads "$NGSPICE_THREADS"); fi
  if [ -n "$KLT_CMD" ]; then args+=(--klt-cmd "$KLT_CMD"); fi
  if [ -n "$RUNNER_VERSION_CHECK" ]; then
    args+=(--runner-version-check "$RUNNER_VERSION_CHECK")
  fi
  python3 sim/run_corners.py "${args[@]}" --quiet
}

# sweep_gen_variant <tag> <command...>
# Runs a variant generator; on failure reports it, flags SWEEP_NOT_RUN and
# returns the generator's status so the point is counted as failed.
sweep_gen_variant() {
  local tag=$1; shift
  local status=0
  mkdir -p "$VARIANT_DIR"
  "$@" || status=$?
  if [ "$status" -ne 0 ]; then
    echo "=== sweep point ${tag}: variant generation failed (exit ${status}); run_corners.py not run"
    SWEEP_NOT_RUN=1
  fi
  return "$status"
}

sweep_main() {
  local only="${1:-}"
  local results=() failures=0 point status k known=0 listed=()
  SWEEP_TAG="" SWEEP_ALIASES=()

  if [ -n "$only" ]; then
    for point in "${POINTS[@]}"; do
      sweep_describe "$point"
      for k in "$SWEEP_TAG" ${SWEEP_ALIASES[@]+"${SWEEP_ALIASES[@]}"}; do
        [ "$only" = "$k" ] && known=1
        case " ${listed[*]-} " in *" $k "*) ;; *) listed+=("$k") ;; esac
      done
    done
    if [ "$known" -eq 0 ]; then
      echo "run_sweep.sh: unknown point '${only}' (expected one of: ${listed[*]})" >&2
      exit 2
    fi
  fi

  for point in "${POINTS[@]}"; do
    sweep_describe "$point"
    if [ -n "$only" ]; then
      known=0
      for k in "$SWEEP_TAG" ${SWEEP_ALIASES[@]+"${SWEEP_ALIASES[@]}"}; do
        [ "$only" = "$k" ] && known=1
      done
      [ "$known" -eq 1 ] || continue
    fi

    # A harness FAIL at a sweep point is DATA, not a reason to abandon the
    # remaining points -- the non-zero exit is captured and reported at the
    # end rather than aborting.
    status=0
    SWEEP_NOT_RUN=0
    sweep_run_point "$point" || status=$?
    if [ "$SWEEP_NOT_RUN" -eq 0 ]; then
      echo "=== sweep point ${SWEEP_TAG}: run_corners.py exit ${status}"
    fi
    results+=("${SWEEP_TAG} exit=${status}")
    if [ "$status" -ne 0 ]; then failures=$((failures + 1)); fi
  done

  echo
  echo "=== sweep complete ==================================================="
  printf '  %s\n' "${results[@]}"
  if [ -n "$SWEEP_EPILOGUE" ]; then echo "$SWEEP_EPILOGUE"; fi

  # A non-zero exit, not just a line in a log: sim/characterize.sh and any
  # caller that harvests records must not mistake "some points ran" for
  # "the sweep ran".
  if [ "$failures" -ne 0 ]; then
    echo "=== sweep FAILED: ${failures} point(s) did not complete successfully"
    exit "$failures"
  fi
}
