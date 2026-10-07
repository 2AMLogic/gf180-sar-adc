#!/usr/bin/env bash
# Re-run the ratified ADC-level decks against a REAL V_DD pin network at
# DR-0036's derived budget, over each deck's OWN governing PVT grid -- issue
# #393, the V_DD counterpart of sim/vcm-full-pvt/run_full_pvt.sh (issue #358,
# DR-0026). Same structure, same pairing discipline; only the network differs.
#
# ---------------------------------------------------------------------------
# PAIRED ARMS, SAME COMMIT
# ---------------------------------------------------------------------------
# Every deck is run TWICE at the same commit, same grid, same host:
#
#   ideal   -- the deck exactly as committed: ideal, zero-impedance
#              `vddt`/`vddd`/`vddc ... dc {vdd_val}` island sources, the
#              assumption every existing record in this suite makes. This is
#              the CONTROL, re-taken rather than read off the cited record so
#              the paired delta carries the V_DD network and nothing else.
#   vddnet  -- the same deck with those island sources replaced by ONE shared
#              V_DD pin network at DR-0036's budget (Z_vdd = 3 ohm,
#              C_dec = 40 nF, R||L corner at the 1 MHz conversion rate) via
#              sim/vdd-drive-impedance/gen_vdd_variant.py, each island kept
#              as a 0 V ammeter. Why one pin and not three islands, and why
#              1 MHz and not the bit clock: that script's docstring and
#              sim/vdd-full-pvt/README.md.
#
# `sim/vdd-full-pvt/compare_vdd.py` computes the paired difference.
#
# ---------------------------------------------------------------------------
# EXTRACTED ROWS ARE PINNED TO THEIR GOVERNING CITATION
# ---------------------------------------------------------------------------
# For an extracted (governing) deck the ideal arm is supposed to REPRODUCE the
# record sim/characterization-summary.md cites for that ratified row. So each
# extracted row names that record, and the preflight below refuses to start if
# the committed deck's sha256 is not the one that record pins -- a re-extraction
# landing on main would otherwise turn "reproduces the citation" into a
# comparison against different bytes. The ideal arm's --netlist-provenance is
# read VERBATIM out of that record (same bytes, same provenance), not retyped.
#
# ---------------------------------------------------------------------------
# CLEAN TREE
# ---------------------------------------------------------------------------
# `sim/run_corners.py` stamps a dirty tree into the record. Run each arm from
# its own clean clone of the commit under test and harvest the record +
# corners/<id>/ + netlist-snapshots/<id>.spice afterwards -- the recipe is in
# sim/vdd-full-pvt/README.md "Reproducing this campaign".
#
#   ./sim/vdd-full-pvt/run_full_pvt.sh                         # every deck, both arms
#   ./sim/vdd-full-pvt/run_full_pvt.sh adc-inl-dnl-extracted   # one deck, both arms
#   ARMS=vddnet ./sim/vdd-full-pvt/run_full_pvt.sh adc-power   # one deck, one arm
#   PREFLIGHT_ONLY=1 ./sim/vdd-full-pvt/run_full_pvt.sh        # checks only
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# DR-0036's provisioned envelope, at its pessimistic edge: Z_vdd,max = 3 ohm,
# C_dec,min = 40 nF. Held fixed -- this campaign grades the budget, it does
# not sweep it.
Z_OHM="${Z_OHM:-3}"
C_DEC_NF="${C_DEC_NF:-40}"
CORNER_HZ="${CORNER_HZ:-1e6}"

VARIANT_DIR="sim/.work/vdd-full-pvt/variants"
JOBS="${JOBS:-4}"
NGSPICE_THREADS="${NGSPICE_THREADS:-1}"
# Every extracted deck here needed well past the 300 s harness default in its
# own governing record; sim/characterize.sh carries the same --timeout.
TIMEOUT="${TIMEOUT:-3600}"
ARMS="${ARMS:-ideal vddnet}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-}"

ENOB_SUBSET_REASON="Two-stage corner strategy (spec/testbench-suite-memo.md \
Sec 5): the dynamic FFT deck is this suite's single most expensive per-point \
campaign, so it runs only at the corners the cheap full-grid static deck \
(adc-inl-dnl) and sim/comparator-preamp-noise/ independently identify as \
worst (125 C). This V_DD-network re-run (issue #393) reproduces that same, \
already-documented reduced grid rather than inventing a new one, so its \
paired ideal-source control is point-for-point comparable with the existing \
ENOB/SFDR citation it is meant to be read against."

# tag | run_corners.py experiment (slug or testbench dir) | deck |
#   extra run_corners.py args | governing record the ideal arm must reproduce
#   (empty => schematic row: the ideal arm takes NO --netlist override, the
#   manifest's own default deck already IS the ideal-supply deck)
#
# Grids are each deck's OWN governing grid, none invented here:
#   dr0014-sampling            27  manifest default (tt/ss/ff x 3 T x 3 V)
#   dr0014-sampling-extracted  27  manifest default -- GOVERNING, Gain error
#                                  systematic (its own testbench-extracted/
#                                  manifest, not a --netlist on the schematic
#                                  one; sim/characterize.sh does the same)
#   adc-inl-dnl                63  manifest default (cdac 7 x 3 T x 3 V)
#   adc-inl-dnl-extracted      27  --corners tt ss ff -- GOVERNING, INL / DNL
#   adc-power                  27  --corners tt ss ff (LOAD-BEARING, #266)
#   adc-power-extracted        27  --corners tt ss ff -- GOVERNING, Power
#   adc-enob-fft                9  --corners tt ss ff --temps 125 (two-stage)
#   adc-enob-fft-extracted      9  same -- GOVERNING, ENOB / SFDR
DECKS=(
  "dr0014-sampling|dr0014-sampling|sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice||"
  "dr0014-sampling-extracted|sim/dr0014-sampling/testbench-extracted|sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice||sim/dr0014-sampling/records/20260923-104443-904af96.md"
  "adc-inl-dnl|adc-inl-dnl|sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice||"
  "adc-inl-dnl-extracted|adc-inl-dnl|sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice|--corners tt ss ff|sim/adc-inl-dnl/records/20260923-095400-904af96.md"
  "adc-power|adc-power|sim/adc-power/testbench/tb_adc_power.spice|--corners tt ss ff|"
  "adc-power-extracted|adc-power|sim/adc-power/testbench/tb_adc_power_extracted.spice|--corners tt ss ff|sim/adc-power/records/20260923-102440-904af96.md"
  "adc-enob-fft|adc-enob-fft|sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice|--corners tt ss ff --temps 125|"
  "adc-enob-fft-extracted|adc-enob-fft|sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice|--corners tt ss ff --temps 125|sim/adc-enob-fft/records/20260923-111149-904af96.md"
)

wanted=("$@")
want() {
  [ ${#wanted[@]} -eq 0 ] && return 0
  local t
  for t in "${wanted[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

# The ideal-arm provenance of an extracted row: the governing record's own
# `Netlist provenance` field, verbatim.
governing_prov() {  # $1: governing record path
  python3 - "$1" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
m = re.search(r"^- \*\*Netlist provenance\*\*: (.*)$", text, re.M)
if not m:
    sys.exit(f"{sys.argv[1]}: no Netlist provenance field")
print(m.group(1), end="")
PY
}

# The sha256 a governing record pins for the deck it ran.
governing_sha() {  # $1: governing record path
  # shellcheck disable=SC2016  # the backticks are literal Markdown, not expansion
  sed -n 's/^- Testbench netlist sha256: `\([0-9a-f]*\)`$/\1/p' "$1"
}

# The --netlist-provenance string for a V_DD-network arm. ONE definition,
# used by both the preflight and the run loop, so the gate checks the string
# it gates (the #391 lesson).
#   $1 = deck path, $2 = governing record (empty for schematic rows)
vdd_provenance() {
  local deck="$1" gov="$2"
  local net="V_DD PIN NETWORK AT DR-0036 BUDGET: Z_vdd = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF, R||L corner at ${CORNER_HZ} Hz (the conversion rate), ONE shared pin feeding every supply island -- ${deck} with its ideal V_DD island sources replaced by sim/vdd-drive-impedance/gen_vdd_variant.py --deck, each island kept as a 0 V ammeter; nothing else in the deck is touched"
  if [ -n "$gov" ]; then
    printf '%s' "extracted, ${net}. Base extraction: the same bytes governing record $(basename "$gov" .md) ran."
  else
    printf '%s' "schematic (${net})"
  fi
}

# PREFLIGHT ------------------------------------------------------------------
# Before a single ngspice process starts: every deck exists, every extracted
# deck still hashes to its governing record's pin, every variant generates
# (gen_vdd_variant.py's own hit-count assertions), and every provenance string
# passes the harness's OWN validator (imported, never re-implemented).
preflight() {
  local row tag exp deck extra gov provs=() got pin
  for row in "${DECKS[@]}"; do
    IFS='|' read -r tag exp deck extra gov <<<"$row"
    want "$tag" || continue
    [ -f "$deck" ] || { echo "PREFLIGHT FAIL: no such deck: $deck" >&2; return 1; }
    if [ -n "$gov" ]; then
      [ -f "$gov" ] || { echo "PREFLIGHT FAIL: no governing record $gov" >&2; return 1; }
      got="$(shasum -a 256 "$deck" | cut -d' ' -f1)"
      pin="$(governing_sha "$gov")"
      if [ "$got" != "$pin" ]; then
        echo "PREFLIGHT FAIL: $deck sha256 $got != $pin pinned by $gov --" \
             "the ideal arm could not reproduce that citation; update the" \
             "governing record in DECKS" >&2
        return 1
      fi
      provs+=("$(governing_prov "$gov")")
    fi
    provs+=("$(vdd_provenance "$deck" "$gov")")
    python3 sim/vdd-drive-impedance/gen_vdd_variant.py --deck "$deck" \
      --z-ohm "$Z_OHM" --c-dec-nf "$C_DEC_NF" --corner-hz "$CORNER_HZ" \
      --out "${VARIANT_DIR}/tb_${tag}_vddnet.spice" >/dev/null
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

mkdir -p "$VARIANT_DIR"
if ! preflight; then
  echo "=== preflight failed; nothing was run ===" >&2
  exit 2
fi
echo "=== preflight OK ==="
[ -n "$PREFLIGHT_ONLY" ] && exit 0

results=()
failures=0

for row in "${DECKS[@]}"; do
  IFS='|' read -r tag exp deck extra gov <<<"$row"
  want "$tag" || continue

  # shellcheck disable=SC2206  # deliberate word-splitting of the arg string
  extra_args=($extra)

  for arm in $ARMS; do
    echo "=== ${tag} / ${arm} (Z_vdd=${Z_OHM} ohm, C_dec=${C_DEC_NF} nF) ======"
    args=("$exp" "${extra_args[@]}"
          --timeout "$TIMEOUT" -j "$JOBS"
          --ngspice-threads "$NGSPICE_THREADS")

    case "$tag" in
      adc-enob-fft*) args+=(--subset-reason "$ENOB_SUBSET_REASON") ;;
    esac

    if [ -n "$gov" ]; then
      which_deck="This is the EXTRACTED deck -- the governing netlist for the ratified row this experiment owns, byte-identical (sha256-checked) to the one governing record $(basename "$gov" .md) ran -- so its paired control is that same deck, unpatched."
    else
      which_deck="No --netlist override: this IS the manifest's own default deck, with the ideal zero-impedance 'vddX vddX 0 dc {vdd_val}' island sources every existing record in this suite assumes."
    fi

    if [ "$arm" = "ideal" ]; then
      if [ -n "$gov" ]; then
        args+=(--netlist "$deck" --netlist-provenance "$(governing_prov "$gov")")
      fi
      args+=(--note "PAIRED IDEAL-V_DD CONTROL for the issue #393 full-PVT V_DD-pin-network re-run (DR-0036's budget). ${which_deck} It is re-taken at THIS commit, on THIS host, rather than read off an older record, so the paired delta against the V_DD-network arm carries the V_DD network and nothing else. Paired arm: same experiment, same grid, netlist provenance 'V_DD PIN NETWORK AT DR-0036 BUDGET'. See sim/vdd-full-pvt/README.md.")
    else
      variant="${VARIANT_DIR}/tb_${tag}_vddnet.spice"
      python3 sim/vdd-drive-impedance/gen_vdd_variant.py --deck "$deck" \
        --z-ohm "$Z_OHM" --c-dec-nf "$C_DEC_NF" --corner-hz "$CORNER_HZ" \
        --out "$variant"
      args+=(--netlist "$variant"
        --netlist-provenance "$(vdd_provenance "$deck" "$gov")"
        --note "ISSUE #393: this deck re-run against a REAL external V_DD pin network at DR-0036's derived budget (proposed, not operator-ratified) -- ONE ideal source behind R || L (DC-accurate, resistive above the 1 MHz conversion rate) feeding C_dec to ground at a single shared pin node, from which every supply island is fed through a 0 V ammeter -- instead of the ideal, zero-impedance per-island V_DD sources every existing record in this suite uses. Z_vdd = ${Z_OHM} ohm, C_dec = ${C_DEC_NF} nF. NOT modelled: package inductance (no package model exists, DR-0036 open question 2), on-die rail resistance between the pin and each island, and on-die decoupling (DR-0036 clause 3, unmet as drawn) -- so this grades the EXTERNAL budget alone. Paired same-commit control: the 'PAIRED IDEAL-V_DD CONTROL' record of the same experiment and grid. Differences: sim/vdd-full-pvt/compare_vdd.py; findings: sim/vdd-full-pvt/README.md.")
    fi

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
if [ "$failures" -ne 0 ]; then
  echo "=== ${failures} arm(s) FAILED -- no paired difference for those ===" >&2
  exit 1
fi
