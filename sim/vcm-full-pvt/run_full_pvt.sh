#!/usr/bin/env bash
# Re-run the ratified ADC-level decks against a REAL V_cm drive network at
# DR-0026's derived budget, over each deck's OWN governing PVT grid --
# DR-0026's named follow-up (issue #358, `spec/testbench-suite-memo.md` Sec 12
# item 3).
#
# This is NOT `sim/vcm-drive-impedance/run_sweep.sh`. That script sweeps Z_vcm
# over three points on ONE deck (`adc-inl-dnl`) at ONE nominal PVT point, and
# reports that deck's own converter-level metrics -- an exploratory
# sensitivity sweep for DR-0026's derivation. This script instead holds Z_vcm
# fixed at DR-0026's budget and re-runs each RATIFIED-ROW-owning deck on the
# grid that deck's own governing record already uses, so the result can be
# read against the ratified rows themselves.
#
# ---------------------------------------------------------------------------
# PAIRED ARMS, SAME COMMIT
# ---------------------------------------------------------------------------
# Every deck is run TWICE at the same commit, same grid, same host:
#
#   ideal   -- no --netlist override at all: the manifest's own default deck,
#              i.e. the ideal, zero-impedance `vcms vcmn 0 dc {vcm}` source
#              every existing record in this suite assumes. This is the
#              CONTROL, and it is re-taken rather than read off an older
#              record, because the older ideal-source records were taken at
#              earlier commits: a delta against them would carry every
#              intervening design change as well as the V_cm network.
#   vcmnet  -- the same deck with that one line replaced by DR-0026's budget
#              network (Z_vcm = 220 ohm, C_dec = 40 nF, R||L corner at the
#              16 MHz bit clock) via sim/vcm-drive-impedance/gen_vcm_variant.py
#              --deck.
#
# The paired difference is therefore attributable to the V_cm network and to
# nothing else. `sim/vcm-full-pvt/compare_vcm.py` computes it.
#
# ---------------------------------------------------------------------------
# CLEAN TREE
# ---------------------------------------------------------------------------
# `sim/run_corners.py` samples `git status --porcelain` before each run and
# stamps a dirty tree into the record as "not citable as a clean-tree result".
# The harness writes its own per-corner logs and record into the tracked
# evidence tree, so the SECOND run of a back-to-back campaign sees the FIRST
# run's output as dirt. Run this from a scratch checkout of the commit under
# test and harvest the records out after each arm, or run one arm per clean
# checkout. `sim/vcm-full-pvt/README.md` Sec "Reproducing this campaign"
# spells out the exact recipe used for the committed records.
#
#   ./sim/vcm-full-pvt/run_full_pvt.sh                    # every deck, both arms
#   ./sim/vcm-full-pvt/run_full_pvt.sh adc-power          # one deck, both arms
#   ARMS=vcmnet ./sim/vcm-full-pvt/run_full_pvt.sh adc-power   # one deck, one arm
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# DR-0026's derived, provisioned envelope: Z_vcm,max = 220 ohm,
# C_dec,min = 40 nF. Held fixed here -- sweeping it is
# sim/vcm-drive-impedance/'s job, not this campaign's.
Z_OHM="${Z_OHM:-220}"
C_DEC_NF="${C_DEC_NF:-40}"

VARIANT_DIR="sim/.work/vcm-full-pvt/variants"
JOBS="${JOBS:-4}"
NGSPICE_THREADS="${NGSPICE_THREADS:-1}"
# Every deck here needed well past the 300 s harness default in its own
# governing record; sim/characterize.sh carries the same load-bearing
# --timeout for the same reason.
TIMEOUT="${TIMEOUT:-3600}"
ARMS="${ARMS:-ideal vcmnet}"

# Two-stage corner strategy for the FFT deck, quoted from the grid its own
# governing records (and sim/characterize.sh) already use -- reproduced here
# rather than invented, so the paired control is point-for-point comparable
# with the existing ENOB/SFDR citation.
ENOB_SUBSET_REASON="Two-stage corner strategy (spec/testbench-suite-memo.md \
Sec 5): the dynamic FFT deck is this suite's single most expensive per-point \
campaign, so it runs only at the corners the cheap full-grid static deck \
(adc-inl-dnl) and sim/comparator-preamp-noise/ independently identify as \
worst (125 C). This V_cm-network re-run (issue #358) reproduces that same, \
already-documented reduced grid rather than inventing a new one, so its \
paired ideal-source control is point-for-point comparable with the existing \
ENOB/SFDR citation it is meant to be read against."

# The ideal arm normally takes NO --netlist override: the manifest's own
# default deck already IS the ideal-V_cm-source deck. One deck breaks that
# symmetry -- `adc-power`'s GOVERNING result is the EXTRACTED deck, not the
# schematic one (`sim/characterize.sh` labels it exactly that: "adc-power
# extracted, GOVERNING (Power)", and sim/characterization-summary.md's
# `Power @ 1 MS/s` row cites sim/adc-power/records/20260817-211252-076d545.md,
# an extracted record). Reporting the V_cm-network verdict against the
# RATIFIED Power row therefore requires running the extracted deck too, so
# `adc-power-extracted`'s ideal arm passes --netlist explicitly. Both arms of
# that pair are extracted, so the paired difference still carries the V_cm
# network and nothing else.
extracted_prov() {  # $1: the row and sim/characterize.sh label it governs
  printf '%s' "extracted (post-layout adc_top core) -- the GOVERNING netlist \
for the ratified $1. Re-taken here UNMODIFIED as the paired ideal-V_cm \
control for the issue #358 V_cm-drive-network arm of the same deck."
}
POWER_EXT_PROV="$(extracted_prov "Power row (sim/characterize.sh: 'adc-power \
extracted, GOVERNING (Power)')")"
INL_EXT_PROV="$(extracted_prov "INL / DNL row (sim/characterize.sh: \
'adc-inl-dnl extracted, GOVERNING (INL, DNL)')")"

# tag | experiment slug | baseline deck | extra run_corners.py args |
#   ideal-arm --netlist-provenance (empty => ideal arm uses no --netlist
#   override at all, i.e. the manifest's own default deck)
#
# The grid for each deck is the one its OWN governing record uses, not a new
# one invented here:
#   dr0014-sampling      27 pts  manifest default (tt/ss/ff x 3 T x 3 V)
#   adc-inl-dnl          63 pts  manifest default (cdac 7-corner x 3 T x 3 V)
#   adc-power            27 pts  --corners tt ss ff (LOAD-BEARING, issue #266:
#                                the manifest's own `cdac` set is
#                                capacitor-only and pins the MOS section
#                                typical, so p_cmp_*'s process axis reads
#                                near-zero under it)
#   adc-inl-dnl-extracted
#                        27 pts  --corners tt ss ff --timeout 3600, the grid
#                                sim/characterize.sh's own "adc-inl-dnl
#                                extracted, GOVERNING" run uses -- the
#                                EXTRACTED deck, which is the governing one
#                                for the ratified INL / DNL row
#   adc-power-extracted  27 pts  same grid, same reason -- the EXTRACTED deck,
#                                which is the governing one for the Power row
#   adc-enob-fft          9 pts  --corners tt ss ff --temps 125 (two-stage
#                                corner strategy, subset-reason above)
DECKS=(
  "dr0014-sampling|dr0014-sampling|sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice||"
  "adc-inl-dnl|adc-inl-dnl|sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice||"
  "adc-inl-dnl-extracted|adc-inl-dnl|sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice|--corners tt ss ff|${INL_EXT_PROV}"
  "adc-power|adc-power|sim/adc-power/testbench/tb_adc_power.spice|--corners tt ss ff|"
  "adc-power-extracted|adc-power|sim/adc-power/testbench/tb_adc_power_extracted.spice|--corners tt ss ff|${POWER_EXT_PROV}"
  "adc-enob-fft|adc-enob-fft|sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice|--corners tt ss ff --temps 125|"
)

wanted=("$@")
want() {
  [ ${#wanted[@]} -eq 0 ] && return 0
  local t
  for t in "${wanted[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

results=()

for row in "${DECKS[@]}"; do
  IFS='|' read -r tag slug deck extra base_prov <<<"$row"
  want "$tag" || continue

  # shellcheck disable=SC2206  # deliberate word-splitting of the arg string
  extra_args=($extra)

  for arm in $ARMS; do
    echo "=== ${tag} / ${arm} (Z_vcm=${Z_OHM} ohm, C_dec=${C_DEC_NF} nF) ======"
    args=("$slug" "${extra_args[@]}"
          --timeout "$TIMEOUT" -j "$JOBS"
          --ngspice-threads "$NGSPICE_THREADS")

    if [ "$tag" = "adc-enob-fft" ]; then
      args+=(--subset-reason "$ENOB_SUBSET_REASON")
    fi

    # The V_cm-network arm's provenance must not call an extracted deck
    # "schematic" -- say which kind of netlist the variant was patched from.
    # `kind` renders byte-identically to the previous hardcoded "schematic"
    # for every deck whose ideal arm takes no --netlist override, so the
    # records already minted by this script remain reproducible from it.
    if [ -n "$base_prov" ]; then
      kind="extracted"
      which_deck="This is the EXTRACTED deck -- the governing netlist for the ratified row this experiment owns -- so its paired control is the same extracted deck run with --netlist and no V_cm patch, not the manifest's schematic default."
      control_note="Paired same-commit ideal-source control: the same extracted deck, unpatched."
    else
      kind="schematic"
      which_deck="No --netlist override: this IS the manifest's own default deck, with the ideal zero-impedance 'vcms vcmn 0 dc {vcm}' source every existing record in this suite assumes."
      control_note="Paired same-commit ideal-source control: the arm of this campaign with no --netlist override."
    fi

    if [ "$arm" = "ideal" ]; then
      if [ -n "$base_prov" ]; then
        args+=(--netlist "$deck" --netlist-provenance "$base_prov")
      fi
      args+=(--note "PAIRED IDEAL-V_cm CONTROL for the issue #358 full-PVT V_cm-drive-network re-run (DR-0026's named follow-up, spec/testbench-suite-memo.md Sec 12 item 3). ${which_deck} It is re-taken at THIS commit, on THIS host, rather than read off an older record, so the paired delta against the V_cm-network arm carries the V_cm network and nothing else. Paired arm: same experiment, same grid, netlist provenance 'V_cm DRIVE NETWORK AT DR-0026 BUDGET'. See sim/vcm-full-pvt/README.md.")
    else
      variant="${VARIANT_DIR}/tb_${tag}_vcmnet.spice"
      mkdir -p "$VARIANT_DIR"
      python3 sim/vcm-drive-impedance/gen_vcm_variant.py \
        --deck "$deck" --z-ohm "$Z_OHM" --c-dec-nf "$C_DEC_NF" --out "$variant"

      args+=(--netlist "$variant"
        --netlist-provenance "${kind}, V_cm DRIVE NETWORK AT DR-0026 BUDGET (Z_vcm = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF, R||L corner at the 16 MHz bit clock) -- ${deck} with its single ideal V_cm source line replaced by sim/vcm-drive-impedance/gen_vcm_variant.py --deck. Nothing else in the deck is touched."
        --note "ISSUE #358, DR-0026's named follow-up (spec/testbench-suite-memo.md Sec 12 item 3): this deck re-run against a REAL external V_cm drive network at DR-0026's derived budget -- an ideal source behind R || L (DC-accurate, resistive at the switching band) feeding C_dec to ground -- instead of the ideal, zero-impedance V_cm source every existing record in this suite uses. Z_vcm = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF. Unlike sim/vcm-drive-impedance/'s exploratory sweep (one deck, nominal 27 C / 3.30 V only, reporting that deck's own converter-level metrics), this run uses THIS deck's own governing PVT grid so the result can be read against the RATIFIED rows this deck owns. ${control_note} Differences: sim/vcm-full-pvt/compare_vcm.py; findings: sim/vcm-full-pvt/README.md.")
    fi

    status=0
    python3 sim/run_corners.py "${args[@]}" || status=$?
    echo "=== ${tag} / ${arm}: run_corners.py exit ${status}"
    results+=("${tag}/${arm} exit=${status}")
  done
done

echo
echo "=== campaign complete ================================================"
printf '  %s\n' "${results[@]}"
