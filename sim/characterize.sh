#!/usr/bin/env bash
#
# sim/characterize.sh -- single entry point behind `make smoke` / `make characterize`.
#
# Runs every campaign that backs a spec row in
# docs/chipalooza/challenge-3-proposal.md Sec 4 ("Target specification at the
# Challenge rails"), via the same sim/run_corners.py harness sim/selftest.sh
# uses to prove the HARNESS ITSELF works. This script is different: it proves
# the ADC-LEVEL characterization campaign the Chipalooza proposal cites --
# see sim/harness/README.md for why sim/smoke_test/ (install check),
# sim/selftest.sh (harness acceptance test) and this script (full-ADC
# characterization campaign) are three different things.
#
#   sim/characterize.sh smoke
#       One nominal PVT corner (tt / 27 C / nominal supply) per campaign,
#       writes NO evidence (--no-write throughout). Minutes, not hours --
#       proof that the whole command surface (every experiment, every
#       schematic/extracted netlist variant, every bespoke driver script)
#       actually runs from a clean checkout, nothing more.
#
#   sim/characterize.sh characterize
#       The full PVT/corner campaign behind every spec row, exactly as the
#       citations in docs/chipalooza/challenge-3-proposal.md Sec 4 name them.
#       Mints a new, dated, append-only sim/<experiment>/records/ entry per
#       run_corners.py-driven campaign (sim/README.md's format -- a genuinely
#       new record, not an overwrite of the ones already committed); the two
#       campaigns with bespoke drivers (mc-cdac-mismatch, the extracted
#       comparator-regeneration measurement) write their raw CSV/JSON output
#       under sim/.work/characterize/ instead, because minting a narrative
#       sim/README.md-format record from them is a manual documentation step
#       in this repo's own convention (see their sections below) -- their
#       PRINTED numbers are what a reviewer compares against the governing
#       citation, same as this repo's own agents have always done for them.
#       Hours -- see README.md#independent-verification-chipalooza for the
#       current estimate and how each spec row maps to this script's output.
#
# Every campaign below names, in a comment, which docs/chipalooza/
# challenge-3-proposal.md Sec 4 row(s) it backs -- cross-reference against
# that table's "Source (dated)" column: this script's default invocation
# reproduces the schematic citation, and the "--netlist ... extracted"
# variant (where one exists) reproduces the GOVERNING (extracted) citation.
#
# Exit status: 0 if every campaign that ran exited 0; non-zero (the count of
# failing campaigns) otherwise, with a full pass/fail summary printed at the
# end regardless of where a failure happened -- one bad campaign does not
# stop the rest from running, so a reviewer gets one full report per
# invocation instead of bisecting failures one re-run at a time.

set -uo pipefail

SIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SIM_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:-}"
case "${MODE}" in
  smoke|characterize) ;;
  *)
    echo "usage: $(basename "$0") {smoke|characterize}" >&2
    echo "  smoke         one nominal corner per campaign, writes no evidence (minutes)" >&2
    echo "  characterize  full PVT campaign, mints sim/ evidence records (hours)" >&2
    exit 1
    ;;
esac

JOBS="${JOBS:-}"
if [ -z "${JOBS}" ]; then
  JOBS="$(command -v nproc >/dev/null 2>&1 && nproc || echo 4)"
fi

RESULTS=()
FAILURES=0

_run() {
  # _run <label> <run_corners.py args...>
  local label="$1"; shift
  echo
  echo "-- ${label} (${MODE}) --"
  echo "   python3 sim/run_corners.py $*"
  if python3 "${SIM_DIR}/run_corners.py" "$@"; then
    RESULTS+=("OK    ${label}")
  else
    local st=$?
    RESULTS+=("FAIL  ${label} (exit ${st})")
    FAILURES=$((FAILURES + 1))
  fi
}

_report() {
  # _report <label> <exit-status>
  local label="$1" st="$2"
  if [ "${st}" -eq 0 ]; then
    RESULTS+=("OK    ${label}")
  else
    RESULTS+=("FAIL  ${label} (exit ${st})")
    FAILURES=$((FAILURES + 1))
  fi
}

echo "=== sim/characterize.sh ${MODE} -- jobs=${JOBS} ==="

# ---------------------------------------------------------------------------
# Digital sequencer / interface: Resolution, Interface, Clock rows
# ---------------------------------------------------------------------------

args=(sar-logic-functional -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "sar-logic-functional (Resolution, Interface)" "${args[@]}"

args=(sar-logic-timing -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "sar-logic-timing (Clock)" "${args[@]}"

# ---------------------------------------------------------------------------
# Sample rate row -- schematic baseline, then the extracted, GOVERNING run
# ---------------------------------------------------------------------------

args=(timing-budget-closure -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "timing-budget-closure schematic baseline (Sample rate)" "${args[@]}"

args=(timing-budget-closure
      --netlist sim/timing-budget-closure/testbench/tb_timing_budget_closure_extracted.spice
      --netlist-provenance "extracted (post-layout timing inputs -- independent re-run via sim/characterize.sh)"
      -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "timing-budget-closure extracted, GOVERNING (Sample rate)" "${args[@]}"

# ---------------------------------------------------------------------------
# Reference (V_REF) drive, Input drive contribution, switch-contribution SFDR
# ---------------------------------------------------------------------------

args=(cdac-bit-settling -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "cdac-bit-settling (Reference V_REF drive)" "${args[@]}"

args=(track-switch-sampling -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "track-switch-sampling (Input drive contribution)" "${args[@]}"

args=(track-switch-thd -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "track-switch-thd (SFDR, switch's own contribution)" "${args[@]}"

# ---------------------------------------------------------------------------
# Offset error, CMRR rows (same deck backs both)
# ---------------------------------------------------------------------------

args=(comparator-offset-mc -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "comparator-offset-mc (Offset error, CMRR)" "${args[@]}"

# schematic baseline for the comparator's own regeneration margin (also one
# of the Sample rate row's transcluded inputs, pre-extraction). UNLIKE every
# other campaign here, this manifest's td_half_ns check carries a bare,
# grid-wide `min_spread_pct: 20` floor (not the `_by_axis` form --no-write
# is allowed to skip when an axis is simply unswept, sim/harness/report.py):
# it demands the run's OWN observed spread be >= 20 %, which a genuine
# single-point run can never produce (spread of one point is always 0). So
# smoke mode sweeps the 3-corner process axis here (still a few points, not
# the full grid) instead of the universal single-point override every other
# campaign uses.
args=(comparator-regeneration -j "${JOBS}" --ngspice-threads 1)
if [ "${MODE}" = smoke ]; then
  args+=(--corners tt ss ff --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
fi
_run "comparator-regeneration schematic baseline (Offset error / Sample rate input)" "${args[@]}"

# ---------------------------------------------------------------------------
# Input structure R_on row -- schematic baseline, then extracted GOVERNING
# ---------------------------------------------------------------------------

args=(device-switch-ron -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "device-switch-ron schematic baseline (Input structure R_on)" "${args[@]}"

args=(device-switch-ron
      --netlist sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice
      --netlist-provenance "extracted (klt-extracted adc_tgate leaf -- independent re-run via sim/characterize.sh)"
      -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "device-switch-ron extracted, GOVERNING (Input structure R_on)" "${args[@]}"

# ---------------------------------------------------------------------------
# Gain error (systematic), Offset (deterministic), INL row inputs --
# schematic baseline, then extracted GOVERNING (a DIFFERENT testbench dir,
# not a --netlist override -- see sim/dr0014-sampling/testbench-extracted/)
# ---------------------------------------------------------------------------

args=(dr0014-sampling -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "dr0014-sampling schematic baseline (Gain error systematic, Offset, INL inputs)" "${args[@]}"

args=(sim/dr0014-sampling/testbench-extracted -j "${JOBS}" --ngspice-threads 1)
if [ "${MODE}" = smoke ]; then
  args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
else
  # LOAD-BEARING: this full-ADC_BLOCK-core extracted deck's governing record
  # (sim/dr0014-sampling/records/20260817-172040-5c0f0cc.md) needed --timeout
  # 2400 at -j 6; the 300s harness default (sim/harness/README.md "Run an
  # extracted deck at -j 1, with a raised --timeout") returns 0/N points, all
  # "ngspice timed out", on this deck even with --ngspice-threads 1 already
  # capping OpenMP oversubscription -- confirmed directly while verifying
  # this script (issue #263). Raised further here for headroom against a
  # busier host than that record's.
  args+=(--timeout 3600)
fi
_run "dr0014-sampling extracted, GOVERNING (Gain error systematic, Offset, INL inputs)" "${args[@]}"

# ---------------------------------------------------------------------------
# ENOB @ Nyquist, SFDR @ Nyquist -- schematic baseline, then extracted
# GOVERNING (a deliberate, documented SUBSET of the full grid: 125 C only --
# see docs/chipalooza/challenge-3-proposal.md Sec 4's ENOB/SFDR rows)
# ---------------------------------------------------------------------------

args=(adc-enob-fft -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "adc-enob-fft schematic baseline (ENOB, SFDR)" "${args[@]}"

args=(adc-enob-fft
      --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice
      --netlist-provenance "extracted (post-layout adc_top core -- independent re-run via sim/characterize.sh)"
      -j "${JOBS}" --ngspice-threads 1)
if [ "${MODE}" = smoke ]; then
  args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
else
  # LOAD-BEARING --timeout: this is this suite's single most expensive
  # per-point campaign (see the subset-reason below) -- its governing records
  # (sim/adc-enob-fft/records/20260817-164712-3a9afd2.md,
  # 20260807-052432-eac5d11.md) needed --timeout 1800-7200 depending on host
  # contention, well past the 300s harness default. See the identical note
  # on the dr0014-sampling extracted run above.
  args+=(--corners tt ss ff --temps 125 --timeout 3600 --subset-reason
"Two-stage corner strategy (spec/testbench-suite-memo.md Sec 5): the dynamic \
FFT deck is this suite's single most expensive per-point campaign, so the \
citation this reproduces runs it only at the corners the cheap full-grid \
static deck (adc-inl-dnl) and sim/comparator-preamp-noise/ independently \
identify as worst (125 C). This independent re-run reproduces that same, \
already-documented reduced grid rather than inventing a new one.")
fi
_run "adc-enob-fft extracted, GOVERNING (ENOB, SFDR)" "${args[@]}"

# ---------------------------------------------------------------------------
# INL, DNL -- schematic baseline, then extracted GOVERNING
# ---------------------------------------------------------------------------

args=(adc-inl-dnl -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "adc-inl-dnl schematic baseline (INL, DNL)" "${args[@]}"

args=(adc-inl-dnl
      --netlist sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice
      --netlist-provenance "extracted (post-layout adc_top core -- independent re-run via sim/characterize.sh)"
      -j "${JOBS}" --ngspice-threads 1)
if [ "${MODE}" = smoke ]; then
  args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
else
  # LOAD-BEARING --timeout: this deck's governing records (e.g.
  # sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md) document that the
  # 300s harness default returns 0/27 points ("ngspice timed out") at this
  # deck's real per-point cost; 1200-3600s was needed depending on host. See
  # the identical note on the dr0014-sampling extracted run above.
  args+=(--corners tt ss ff --timeout 3600)
fi
_run "adc-inl-dnl extracted, GOVERNING (INL, DNL)" "${args[@]}"

# ---------------------------------------------------------------------------
# Power @ 1 MS/s -- schematic baseline, then extracted GOVERNING
# ---------------------------------------------------------------------------

args=(adc-power -j "${JOBS}" --ngspice-threads 1)
[ "${MODE}" = smoke ] && args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
_run "adc-power schematic baseline (Power)" "${args[@]}"

args=(adc-power
      --netlist sim/adc-power/testbench/tb_adc_power_extracted.spice
      --netlist-provenance "extracted (post-layout adc_top core -- independent re-run via sim/characterize.sh)"
      -j "${JOBS}" --ngspice-threads 1)
if [ "${MODE}" = smoke ]; then
  args+=(--corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet)
else
  # LOAD-BEARING --timeout: this deck's governing records (e.g.
  # sim/adc-power/records/20260806-083932-faebccc.md) needed --timeout
  # 3600-7200 depending on host, well past the 300s harness default. See the
  # identical note on the dr0014-sampling extracted run above.
  args+=(--corners tt ss ff --timeout 3600)
fi
_run "adc-power extracted, GOVERNING (Power)" "${args[@]}"

# ---------------------------------------------------------------------------
# V_CM drive -- issue #260 / DR-0026's sensitivity sweep. `ideal` reuses the
# unmodified adc-inl-dnl schematic deck; `budget` / `5x-over-budget` patch a
# real R||L + C_dec network in via generated variants. Full mode uses the
# committed sweep driver (mints real records for all three points); smoke
# mode runs just the `ideal` point directly, --no-write, to prove the
# manifest/netlist plumbing without regenerating variant decks.
# ---------------------------------------------------------------------------

if [ "${MODE}" = smoke ]; then
  args=(vcm-drive-impedance --corners tt --temps 27 --supply-tol 0 --timeout 900 --no-write --quiet
        -j "${JOBS}" --ngspice-threads 1)
  _run "vcm-drive-impedance, ideal point only (V_CM drive)" "${args[@]}"
else
  echo
  echo "-- vcm-drive-impedance, full sweep -- ideal / budget / 5x-over-budget (V_CM drive) (${MODE}) --"
  echo "   JOBS=${JOBS} NGSPICE_THREADS=1 sim/vcm-drive-impedance/run_sweep.sh"
  sweep_log="$(mktemp)"
  JOBS="${JOBS}" NGSPICE_THREADS=1 "${SIM_DIR}/vcm-drive-impedance/run_sweep.sh" | tee "${sweep_log}"
  sweep_status=0
  # run_sweep.sh itself always exits 0 (it captures each point's status and
  # keeps going, per point, by design) -- check its own per-point report
  # lines rather than trusting the driver's exit code.
  if ! grep -q "exit=0" "${sweep_log}"; then
    sweep_status=1
  elif grep -qE "exit=[1-9]" "${sweep_log}"; then
    sweep_status=1
  fi
  rm -f "${sweep_log}"
  _report "vcm-drive-impedance full sweep (V_CM drive)" "${sweep_status}"
fi

# ---------------------------------------------------------------------------
# Gain error, mismatch -- behavioral Monte Carlo model, not a PVT sweep
# (the gf180mcu PDK ships no local capacitor mismatch model to sweep against;
# see sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py's own module
# docstring). Governing parameters: sigma_u = 0.5 % (the resized, as-built
# C_u = 35.6528 fF, spec/cdac-sizing-memo.md Sec 4), N = 20000, seed = 20260801
# -- sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md. This script
# does NOT mint a new sim/README.md-format record for this one (that write-up
# is a manual documentation step in this repo's own convention -- the
# governing record's raw CSV/JSON already lives under
# sim/mc-cdac-mismatch/runs/, committed evidence); it writes fresh raw output
# under sim/.work/characterize/ and prints the same summary statistics a
# reviewer compares directly against that record's numbers.
# ---------------------------------------------------------------------------

echo
echo "-- mc-cdac-mismatch (Gain error, mismatch) (${MODE}) --"
if [ "${MODE}" = smoke ]; then
  out_dir="$(mktemp -d)"
  echo "   python3 sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py --sigma-u 0.5 --trials 200 --seed 20260801"
  echo "   (smoke: reduced trial count, output discarded -- ${out_dir})"
  python3 "${SIM_DIR}/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py" \
    --sigma-u 0.5 --trials 200 --seed 20260801 \
    --out-csv "${out_dir}/trials.csv" --out-json "${out_dir}/summary.json"
  st=$?
  rm -rf "${out_dir}"
  _report "mc-cdac-mismatch smoke (Gain error, mismatch)" "${st}"
else
  out_dir="sim/.work/characterize/mc-cdac-mismatch/$(date -u +%Y%m%d-%H%M%S)"
  mkdir -p "${out_dir}"
  echo "   python3 sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py --sigma-u 0.5 --trials 20000 --seed 20260801"
  echo "   governing parameters -- compare against sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md"
  echo "   raw output (NOT committed evidence): ${out_dir}"
  python3 "${SIM_DIR}/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py" \
    --sigma-u 0.5 --trials 20000 --seed 20260801 \
    --out-csv "${out_dir}/trials_n20000.csv" --out-json "${out_dir}/summary_n20000.json"
  st=$?
  _report "mc-cdac-mismatch N=20000 sigma_u=0.5% (Gain error, mismatch)" "${st}"
fi

# ---------------------------------------------------------------------------
# Offset error's comparator-inclusive (ADC_BLOCK) regeneration margin --
# a bespoke, diagnostic script (NOT a committed tb.json deck -- see its own
# --help for why: the per-corner deck shape is not uniform, so it cannot be
# expressed as one sim/run_corners.py manifest). Full mode only: this is a
# comparator-INSIDE-the-extraction run over the full 45-point 'mos' grid and
# is one of the heavier campaigns here; smoke mode already exercises the
# schematic comparator-regeneration deck above, which is enough to prove the
# comparator/regeneration methodology runs at all within smoke's "minutes,
# not hours" budget.
# ---------------------------------------------------------------------------

if [ "${MODE}" = characterize ]; then
  echo
  echo "-- comparator-regeneration extracted, GOVERNING, ADC_BLOCK-inclusive (Offset error / Sample rate input) (characterize) --"
  out_json="sim/.work/characterize/comparator-regeneration-extracted/$(date -u +%Y%m%d-%H%M%S).json"
  mkdir -p "$(dirname "${out_json}")"
  echo "   python3 layout/adc-top/parasitics/measure_extracted_regeneration.py --corners mos --json ${out_json}"
  echo "   compare against sim/comparator-regeneration/records/20260814-215626-f613571.md"
  python3 "${REPO_ROOT}/layout/adc-top/parasitics/measure_extracted_regeneration.py" \
    --corners mos --json "${out_json}"
  st=$?
  _report "comparator-regeneration extracted, ADC_BLOCK-inclusive (Offset error / Sample rate input)" "${st}"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo
echo "=== sim/characterize.sh ${MODE} complete ==="
printf '  %s\n' "${RESULTS[@]}"
echo
if [ "${FAILURES}" -ne 0 ]; then
  echo "FAIL: ${FAILURES} campaign(s) did not pass."
  exit "${FAILURES}"
fi
echo "PASS: every campaign in ${MODE} mode completed successfully."
