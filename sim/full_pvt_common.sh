# shellcheck shell=bash
# Shared campaign driver for the paired-arm full-PVT re-runs:
#   sim/vcm-full-pvt/run_full_pvt.sh   (V_cm drive network, DR-0026, issue #358)
#   sim/vdd-full-pvt/run_full_pvt.sh   (V_DD pin network,   DR-0036, issue #393)
#
# SOURCED, never executed. Each campaign script is a thin wrapper that keeps
# its own path (records and docs cite it for reproduction), its own DECKS
# table and network-specific prose, and calls `fpvt_main "$@"`.
#
# What lives here: the paired-arm loop, `want` deck selection, the
# provenance-validator preflight gate, run_corners.py argument assembly for
# everything that is NOT network-specific, and the failure summary. The
# SUPERSEDES / EXTRA_NOTE / KLT_CMD hooks therefore exist for EVERY campaign:
#
#   SUPERSEDES  record-id this run's record corrects (run_corners.py
#               --supersedes writes the record's own `Supersedes:` field).
#               `sim/` is append-only, so a correction is a NEW record that
#               names the one it replaces.
#   EXTRA_NOTE  one more --note, carried verbatim into the record.
#   KLT_CMD     batch-dispatch hosts only: the `klt` invocation handed to
#               run_corners.py --klt-cmd (a throwaway version-matched client,
#               e.g. 'uvx --from klayout-tools==0.5.0 klt').
#   PREFLIGHT_ONLY=1  run the checks and exit before any run_corners.py call.
#
# The wrapper must define, before calling fpvt_main:
#   DECKS             rows "tag|experiment|deck|extra run_corners args|base"
#   ARMS              default arm list (space separated; first is the control)
#   ENOB_TAG_GLOB     bash glob of tags that get --subset-reason
#   ENOB_SUBSET_REASON
#   fpvt_preflight_row tag exp deck extra base   -- per-deck checks; append each
#                     provenance string to be validated to the array `provs`
#   fpvt_banner tag arm                          -- the "=== ..." line
#   fpvt_arm_args tag arm deck base              -- append the arm's
#                     --netlist/--netlist-provenance/--note args to `args`
# Optional: fpvt_pre_loop (runs after a successful preflight, before runs).

SUPERSEDES="${SUPERSEDES:-}"
EXTRA_NOTE="${EXTRA_NOTE:-}"
KLT_CMD="${KLT_CMD:-}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-}"
JOBS="${JOBS:-4}"
NGSPICE_THREADS="${NGSPICE_THREADS:-1}"
# Every deck here needed well past the 300 s harness default in its own
# governing record; sim/characterize.sh carries the same load-bearing
# --timeout for the same reason.
TIMEOUT="${TIMEOUT:-3600}"

wanted=()
want() {
  [ ${#wanted[@]} -eq 0 ] && return 0
  local t
  for t in "${wanted[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

# Every --netlist-provenance string the campaign will hand to run_corners.py
# is checked against the harness's OWN validator (imported, never
# re-implemented) before a single ngspice process starts. run_corners.py
# rejects a malformed provenance in under a second, so without this gate a
# campaign can die instantly on one arm while the other arm runs for half an
# hour. Strings are read NUL-separated from stdin.
fpvt_validate_provenances() {
  python3 -c '
import sys
sys.path.insert(0, "sim")
from harness.testbench import PROVENANCE_RULE, valid_netlist_provenance
bad = [p for p in sys.stdin.buffer.read().split(b"\0")[:-1]
       if not valid_netlist_provenance(p.decode())]
for p in bad:
    print("PREFLIGHT FAIL:", PROVENANCE_RULE, "-- got:", p.decode()[:120],
          file=sys.stderr)
sys.exit(1 if bad else 0)
'
}

fpvt_preflight() {
  local row tag exp deck extra base
  provs=()
  for row in "${DECKS[@]}"; do
    IFS='|' read -r tag exp deck extra base <<<"$row"
    want "$tag" || continue
    [ -f "$deck" ] || { echo "PREFLIGHT FAIL: no such deck: $deck" >&2; return 1; }
    fpvt_preflight_row "$tag" "$exp" "$deck" "$extra" "$base" || return 1
  done
  [ ${#provs[@]} -eq 0 ] && return 0
  printf '%s\0' "${provs[@]}" | fpvt_validate_provenances
}

fpvt_main() {
  wanted=("$@")
  local provs=() row tag exp deck extra base arm status extra_args
  local results=() failures=0 args

  if ! fpvt_preflight; then
    echo "=== preflight failed; nothing was run ===" >&2
    exit 2
  fi
  echo "=== preflight OK ==="
  [ -n "$PREFLIGHT_ONLY" ] && exit 0
  if declare -F fpvt_pre_loop >/dev/null; then fpvt_pre_loop; fi

  for row in "${DECKS[@]}"; do
    IFS='|' read -r tag exp deck extra base <<<"$row"
    want "$tag" || continue

    # shellcheck disable=SC2206  # deliberate word-splitting of the arg string
    extra_args=($extra)

    for arm in $ARMS; do
      fpvt_banner "$tag" "$arm"
      args=("$exp" "${extra_args[@]}"
            --timeout "$TIMEOUT" -j "$JOBS"
            --ngspice-threads "$NGSPICE_THREADS")

      # shellcheck disable=SC2254  # ENOB_TAG_GLOB is a deliberate glob
      case "$tag" in
        $ENOB_TAG_GLOB) args+=(--subset-reason "$ENOB_SUBSET_REASON") ;;
      esac

      # Append-only evidence: a corrective re-run names the record it
      # replaces and says why, inside the record itself. Empty by default,
      # so an ordinary run is byte-for-byte the run this script always made.
      # (if/fi, not `[ ... ] && ...`: under `set -e` a false test as the
      # whole command would abort the campaign rather than skip the flag.)
      if [ -n "$SUPERSEDES" ]; then args+=(--supersedes "$SUPERSEDES"); fi
      if [ -n "$EXTRA_NOTE" ]; then args+=(--note "$EXTRA_NOTE"); fi
      if [ -n "$KLT_CMD" ]; then args+=(--klt-cmd "$KLT_CMD"); fi

      fpvt_arm_args "$tag" "$arm" "$deck" "$base"

      status=0
      python3 sim/run_corners.py "${args[@]}" || status=$?
      echo "=== ${tag} / ${arm}: run_corners.py exit ${status}"
      results+=("${tag}/${arm} exit=${status}")
      if [ "$status" -ne 0 ]; then failures=$((failures + 1)); fi
    done
  done

  echo
  echo "=== campaign complete ================================================"
  printf '  %s\n' "${results[@]}"
  # A non-zero exit, not just a line in a log: an arm that failed is an arm
  # whose paired difference does not exist, and a caller that harvests
  # records must not mistake "one arm ran" for "the pair ran".
  if [ "$failures" -ne 0 ]; then
    echo "=== ${failures} arm(s) FAILED -- no paired difference for those ===" >&2
    exit 1
  fi
}
