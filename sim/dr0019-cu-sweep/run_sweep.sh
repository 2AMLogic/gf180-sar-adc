#!/usr/bin/env bash
# Run the DR-0019 C_u isolation sweep (issue #211).
#
# One recorded harness run per sweep point, each over the SAME 9-point
# (3 process x 3 supply, all 125 C) grid sim/adc-enob-fft/'s own records use,
# so every point is directly comparable with the pre- and post-resize captures
# issue #211 reports.  Nothing here post-processes: SFDR/ENOB come out of
# sim/dr0019-cu-sweep/analyze_sweep.py, run afterwards over the records this
# script writes.
#
#   ./sim/dr0019-cu-sweep/run_sweep.sh                    # the whole sweep
#   ./sim/dr0019-cu-sweep/run_sweep.sh 22.0000            # every point at that C_u
#   ./sim/dr0019-cu-sweep/run_sweep.sh cu35.6528-sw2.068  # exactly one point, by tag
#
# The C_u axis and the orthogonal control SHARE a C_u (35.6528 fF), so the
# bare-C_u form selects both of them; the tag form is what re-runs a single
# point after a timeout without also re-running its twin.
#
# Wall time: each point is nine 66 us transients of a ~1300-device deck. On an
# 18-core host with nothing else running that is ~8-10 min per point; measured
# at ~26 min per point on the same host with one other campaign competing for
# cores, which is why TIMEOUT defaults well above the uncontended figure --
# a per-point ngspice timeout does not fail loudly, it writes a record full of
# FAIL corners that has to be superseded.
#
# The point loop, selection, exit-status contract and the run_corners.py
# arguments common to every sweep live in sim/sweep_common.sh (shared with
# sim/acq-leg-width-sweep/ and sim/vcm-drive-impedance/). Exit status: 0 only
# if every selected point succeeded, else the number of failing points; an
# unknown selector exits 2 without running anything.
set -euo pipefail

VARIANT_DIR="sim/.work/dr0019-cu-sweep/variants"
JOBS="${JOBS:-9}"
NGSPICE_THREADS="${NGSPICE_THREADS:-1}"
TIMEOUT="${TIMEOUT:-7200}"
SWEEP_EPILOGUE="Now collate: python3 sim/dr0019-cu-sweep/analyze_sweep.py --markdown"

# shellcheck source=sim/sweep_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../sweep_common.sh"

# C_u in fF, and the multiplier applied to the CDAC cell's FOURTH-LEG
# (acquisition) T-gate width.  The first seven points are the C_u axis itself:
# DR-0019's own two endpoints (17.24 -> 35.6528 fF), three intermediates,
# DR-0019's own rejected exact-boundary sizing (33.00 fF, the smallest C_u
# that meets the gain-error matching constraint at all), and one point BEYOND
# the ratified value so the trend is tested for continuation rather than
# merely interpolated between the two known points.  The 33.00 fF point is not
# decoration: issue #211 asks whether a SMALLER admissible resize would have
# cost less dynamic margin, and that is the only other sizing DR-0019 itself
# put on the table.
#
# The eighth is the orthogonal control.  Growing C_u moves three things at
# once -- the acquisition time constant R_on(V_in)*C_arr, the charge the array
# draws from the DR-0002 reference network, and the C_arr/(C_arr + C_par)
# divider.  Holding C_u at the ratified value while widening ONLY the input
# leg by the same 2.068x factor C_u grew restores the FIRST of those three to
# its pre-resize value and leaves the other two at their resized values.  If
# the acquisition-RC hypothesis (spec/testbench-suite-memo.md Sec 11.2) is
# right, that point recovers most of the lost SFDR; if reference droop or the
# divider is doing the work, it does not.
POINTS=(
  "17.2400 1.0"
  "22.0000 1.0"
  "26.0000 1.0"
  "30.0000 1.0"
  "33.0000 1.0"
  "35.6528 1.0"
  "42.0000 1.0"
  "35.6528 2.068"
)

SUBSET_REASON="Two-stage corner strategy, spec/testbench-suite-memo.md Sec 5, \
kept UNCHANGED from sim/adc-enob-fft/'s own records so this sweep point is \
point-for-point comparable with the pre- and post-DR-0019 captures issue #211 \
reports. 125 C is the temperature the settling/linearity-worst ss_125c_2.97v \
corner sits at; full process and supply axes are swept, only temperature is \
reduced."

# Selectable by C_u (both points at a shared C_u) or by the unique tag.
sweep_describe() {
  local cu scale
  read -r cu scale <<<"$1"
  if [ "$scale" = "1.0" ]; then SWEEP_TAG="cu${cu}"; else SWEEP_TAG="cu${cu}-sw${scale}"; fi
  SWEEP_ALIASES=("$cu")
}

sweep_run_point() {
  local cu scale tag prov note variant
  read -r cu scale <<<"$1"
  tag="$SWEEP_TAG"

  if [ "$scale" = "1.0" ]; then
    prov="schematic (DR-0019 C_u sweep point: C_u = ${cu} fF, ratified acquisition-leg T-gate geometry)"
    note="C_u SWEEP POINT: C_u = ${cu} fF, i.e. C_side = C_in = 512 * C_u \
(spec/cdac-sizing-memo.md Sec 5.2). Every other parameter of the deck is the \
ratified one -- the netlist is emitted by design/adc-top/gen_adc_top.py with \
only C_UNIT_FF rebound, and sim/dr0019-cu-sweep/gen_cu_variant.py asserts that \
the same code path at C_u = 35.6528 fF reproduces \
sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice byte-for-byte."
  else
    prov="schematic (DR-0019 C_u sweep ORTHOGONAL CONTROL: C_u = ${cu} fF with the CDAC cell's fourth-leg (acquisition) T-gate width scaled x${scale})"
    note="ORTHOGONAL CONTROL POINT, not a C_u sweep point: C_u is the ratified \
${cu} fF and the ONLY deviation from the ratified deck is the CDAC cell's \
fourth-leg (input/acquisition) T-gate, widened x${scale} from 10u/20u to \
20.68u/41.36u. The other three legs (release / V_REF / GND) keep the ratified \
geometry, so bit-trial drive strength is unchanged. This restores the \
acquisition time constant R_on(V_in) * C_arr to roughly its pre-resize value \
while leaving the reference-charge and C_arr/(C_arr+C_par) consequences of the \
resize in place -- the discriminator between the three mechanisms a plain C_u \
sweep moves together."
  fi

  variant="${VARIANT_DIR}/tb_${tag}.spice"
  sweep_gen_variant "$tag" python3 sim/dr0019-cu-sweep/gen_cu_variant.py \
    --c-unit-ff "$cu" --acq-switch-scale "$scale" --out "$variant" || return $?

  echo "=== sweep point ${tag} ==============================================="
  # `--corners tt ss ff` is passed explicitly rather than taken from the
  # manifest's `"corners": ["cdac"]`: the sim/adc-enob-fft/ records this sweep
  # has to be comparable with were themselves taken on the tt/ss/ff process
  # axis (see their "Per-corner model sections used" block), not on the
  # 7-corner `cdac` set. Copying the manifest without copying the invocation
  # would have silently produced a 21-point grid that is not point-for-point
  # comparable with anything issue #211 cites.
  sweep_run_corners dr0019-cu-sweep \
    --netlist "$variant" \
    --netlist-provenance "$prov" \
    --corners tt ss ff \
    --temps 125 \
    --subset-reason "$SUBSET_REASON" \
    --note "$note"
}

sweep_main "$@"
