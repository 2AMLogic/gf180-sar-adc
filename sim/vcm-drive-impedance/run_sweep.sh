#!/usr/bin/env bash
# Run the V_cm drive-impedance sensitivity sweep (issue #260).
#
# One recorded harness run per V_cm network point, each over the SAME
# 7-corner `cdac` process axis at nominal temperature/supply, so every point
# is directly comparable. Nothing here post-processes: the numbers a reader
# needs (gain_err_lsb, inl_t256_lsb, inl_t768_lsb, vref_droop_mv) are printed
# by run_corners.py itself and cited straight into the summary record.
#
#   ./sim/vcm-drive-impedance/run_sweep.sh             # the whole sweep
#   ./sim/vcm-drive-impedance/run_sweep.sh ideal        # one point only
#
# Wall time: each point is seven 20 us transients of a ~1300-device deck --
# a few minutes per point uncontended.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

VARIANT_DIR="sim/.work/vcm-drive-impedance/variants"
JOBS="${JOBS:-7}"
NGSPICE_THREADS="${NGSPICE_THREADS:-1}"
TIMEOUT="${TIMEOUT:-1800}"

# tag, Z_vcm (ohm), C_dec (nF).
#
# `ideal` is NOT generated -- it IS the unmodified checked-in
# sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice, i.e. the manifest's own
# default netlist, run with no --netlist override at all. This is
# deliberate: every existing sim/adc-inl-dnl/, sim/adc-enob-fft/ and
# sim/adc-power/ record already IS this experiment's ideal-source data
# point, so re-deriving it here (rather than reusing the manifest default)
# keeps this sweep self-contained without hand-copying a second baseline
# deck that could drift from the real one.
#
# `budget` is DR-0026's derived, provisioned envelope: Z_vcm,max = 220 ohm,
# C_dec,min = 40 nF.
#
# `5x-over-budget` is a deliberate NEGATIVE-CONTROL-style point beyond the
# derived budget (Z_vcm = 1100 ohm, same 40 nF decoupling): issue #260 asks
# to find where a real budget bites, and a single at-budget point cannot by
# itself show whether the derived ceiling is doing any work.
POINTS=(
  "ideal 0 40"
  "budget 220 40"
  "5x-over-budget 1100 40"
)

SUBSET_REASON="Reduced to the cdac 7-corner process axis (the capacitor-\
family corners this mechanism's C_u-driven charge/impedance interaction \
rides on, sim/harness/README.md 'Why the capacitor corners matter here') \
at NOMINAL temperature and supply only (27 C, 3.30 V) -- an exploratory \
sensitivity sweep for a new decision record's derivation (issue #260 / \
DR-0026), not a re-verification of a ratified spec-line campaign. The full \
temperature/supply axes are a follow-up if this sweep's findings warrant \
one."

only="${1:-}"
results=()

for point in "${POINTS[@]}"; do
  read -r tag z c <<<"$point"

  if [ -n "$only" ] && [ "$only" != "$tag" ]; then
    continue
  fi

  echo "=== sweep point ${tag} (Z_vcm=${z} ohm, C_dec=${c} nF) ==========="
  status=0
  if [ "$tag" = "ideal" ]; then
    # No --netlist override: run the manifest's own default netlist, i.e.
    # the unmodified checked-in tb_adc_inl_dnl.spice.
    python3 sim/run_corners.py vcm-drive-impedance \
      --subset-reason "$SUBSET_REASON" \
      --note "IDEAL V_cm SOURCE (Z_vcm = 0, unmodified checked-in deck): the baseline every existing sim/adc-inl-dnl/, sim/adc-enob-fft/ and sim/adc-power/ record already assumes." \
      --timeout "$TIMEOUT" \
      -j "$JOBS" \
      --ngspice-threads "$NGSPICE_THREADS" \
      --quiet || status=$?
  else
    variant="${VARIANT_DIR}/tb_vcm_${tag}.spice"
    mkdir -p "$VARIANT_DIR"
    python3 sim/vcm-drive-impedance/gen_vcm_variant.py \
      --z-ohm "$z" --c-dec-nf "$c" --out "$variant"

    prov="schematic (V_cm drive-impedance sweep point: Z_vcm = ${z} ohm, C_dec = ${c} nF, R||L corner at the 16 MHz bit clock -- sim/vcm-drive-impedance/gen_vcm_variant.py)"
    note="V_cm DRIVE-IMPEDANCE SWEEP POINT '${tag}': Z_vcm = ${z} ohm, C_dec = ${c} nF. Every other parameter of the deck is the ratified one -- only the ideal V_cm source (sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice's 'vcms vcmn 0 dc {vcm}' line) is replaced by an R || L (source impedance, DC-accurate, resistive at the switching band) + C_dec (decoupling) network, modelled the same way this same deck already models V_REF (DR-0002)."

    python3 sim/run_corners.py vcm-drive-impedance \
      --netlist "$variant" \
      --netlist-provenance "$prov" \
      --subset-reason "$SUBSET_REASON" \
      --note "$note" \
      --timeout "$TIMEOUT" \
      -j "$JOBS" \
      --ngspice-threads "$NGSPICE_THREADS" \
      --quiet || status=$?
  fi
  echo "=== sweep point ${tag}: run_corners.py exit ${status}"
  results+=("${tag} exit=${status}")
done

echo
echo "=== sweep complete ==================================================="
printf '  %s\n' "${results[@]}"
