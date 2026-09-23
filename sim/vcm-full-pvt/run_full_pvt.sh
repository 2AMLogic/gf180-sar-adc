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

# PREFLIGHT -----------------------------------------------------------------
# Every string this script will hand to `run_corners.py --netlist-provenance`
# is checked HERE, before a single ngspice process starts, against the
# harness's OWN validator (`sim/harness/testbench.py:valid_netlist_provenance`
# -- imported, never re-implemented, so the rule cannot drift out of sync).
#
# This gate is not decoration. `run_corners.py` rejects a malformed
# provenance in under a second and exits 3, and the first version of this
# script mis-spelled the V_cm-network form -- so every `vcmnet` arm died
# instantly while every `ideal` arm ran for its full half hour. A campaign
# that is half-dead in a way only a post-hoc log read reveals is worse than
# one that refuses to start, because the wasted arms are not the ones that
# failed loudly.
# The `--netlist-provenance` string for a V_cm-network arm. ONE definition,
# called by both `preflight_provenance` (before anything runs) and the run
# loop (what is actually recorded), so the gate checks the string it gates.
#
# `sim/harness/testbench.py`'s `valid_netlist_provenance` admits exactly three
# forms: bare "schematic", "schematic (<detail>)", or anything starting with
# "extracted". A V_cm-patched schematic deck is a PARAMETRIC VARIANT of the
# schematic deck -- precisely the case the parenthesised form exists for -- so
# the detail goes INSIDE the parentheses, the same way
# sim/vcm-drive-impedance/run_sweep.sh spells its own sweep points. The
# extracted decks' variants start with "extracted", which is the third form.
#
# $1 = deck path, $2 = the row's base_prov (non-empty only for extracted rows)
vcm_provenance() {
  local deck="$1" base_prov="$2"
  if [ -n "$base_prov" ]; then
    printf '%s' "extracted, V_cm DRIVE NETWORK AT DR-0026 BUDGET (Z_vcm = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF, R||L corner at the 16 MHz bit clock) -- ${deck} with its single ideal V_cm source line replaced by sim/vcm-drive-impedance/gen_vcm_variant.py --deck. Nothing else in the deck is touched."
  else
    printf '%s' "schematic (V_cm DRIVE NETWORK AT DR-0026 BUDGET: Z_vcm = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF, R||L corner at the 16 MHz bit clock -- ${deck} with its single ideal V_cm source line replaced by sim/vcm-drive-impedance/gen_vcm_variant.py --deck; nothing else in the deck is touched)"
  fi
}

preflight_provenance() {
  local row tag slug deck extra base_prov provs=()
  for row in "${DECKS[@]}"; do
    IFS='|' read -r tag slug deck extra base_prov <<<"$row"
    want "$tag" || continue
    [ -n "$base_prov" ] && provs+=("$base_prov")
    # The string checked here is the string the run will use, built by the
    # same function (#391 review): a probe of the same *shape* would have
    # caught the bug this gate was written for, but the probe and the real
    # string were assembled in two places and could drift apart, so the next
    # provenance-shape bug would walk straight through the gate.
    provs+=("$(vcm_provenance "$deck" "$base_prov")")
    [ -f "$deck" ] || { echo "PREFLIGHT FAIL: no such deck: $deck" >&2; return 1; }
  done
  [ ${#provs[@]} -eq 0 ] && return 0
  printf '%s\0' "${provs[@]}" | python3 -c '
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

if ! preflight_provenance; then
  echo "=== preflight failed; nothing was run ===" >&2
  exit 2
fi

results=()
failures=0

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

    # An extracted deck's ideal arm is the one case where the control is not
    # simply "the manifest's default deck": both arms must be the same
    # extracted netlist for the paired difference to isolate the V_cm network.
    if [ -n "$base_prov" ]; then
      which_deck="This is the EXTRACTED deck -- the governing netlist for the ratified row this experiment owns -- so its paired control is the same extracted deck run with --netlist and no V_cm patch, not the manifest's schematic default."
      control_note="Paired same-commit ideal-source control: the same extracted deck, unpatched."
    else
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

      # Built by the SAME function `preflight_provenance` already validated
      # against the harness's own rule, above.
      vcm_prov="$(vcm_provenance "$deck" "$base_prov")"

      args+=(--netlist "$variant"
        --netlist-provenance "$vcm_prov"
        --note "ISSUE #358, DR-0026's named follow-up (spec/testbench-suite-memo.md Sec 12 item 3): this deck re-run against a REAL external V_cm drive network at DR-0026's derived budget -- an ideal source behind R || L (DC-accurate, resistive at the switching band) feeding C_dec to ground -- instead of the ideal, zero-impedance V_cm source every existing record in this suite uses. Z_vcm = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF. Unlike sim/vcm-drive-impedance/'s exploratory sweep (one deck, nominal 27 C / 3.30 V only, reporting that deck's own converter-level metrics), this run uses THIS deck's own governing PVT grid so the result can be read against the RATIFIED rows this deck owns. ${control_note} Differences: sim/vcm-full-pvt/compare_vcm.py; findings: sim/vcm-full-pvt/README.md.")
    fi

    status=0
    python3 sim/run_corners.py "${args[@]}" || status=$?
    echo "=== ${tag} / ${arm}: run_corners.py exit ${status}"
    results+=("${tag}/${arm} exit=${status}")
    [ "$status" -ne 0 ] && failures=$((failures + 1))
  done
done

echo
echo "=== campaign complete ================================================"
printf '  %s\n' "${results[@]}"
# A non-zero exit, not just a line in a log: an arm that failed is an arm
# whose paired difference does not exist, and a caller that harvests records
# must not mistake "one arm ran" for "the pair ran".
if [ "$failures" -ne 0 ]; then
  echo "=== ${failures} arm(s) FAILED -- no paired difference for those ===" >&2
  exit 1
fi
