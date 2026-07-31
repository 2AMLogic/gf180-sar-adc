# Source me:  source sim/env.sh
#
# Exports the gf180mcu PDK environment that the harness resolved, so that an
# interactive ngspice / xschem session sees exactly the same PDK the corner
# runner uses. Safe to source from any directory.
#
#   PDK_ROOT                 parent of the variant dir (open_pdks convention)
#   PDK                      variant, e.g. gf180mcuD
#   GF180_PDK_PATH           the variant dir itself
#   GF180_MODELS             libs.tech/ngspice (design.ngspice, sm141064.ngspice)
#   XSCHEM_USER_LIBRARY_PATH repo symbol/testbench dirs, honoured by the PDK xschemrc

_gf180_env_self="${BASH_SOURCE[0]:-${(%):-%x}}"
_gf180_sim_dir="$(cd "$(dirname "${_gf180_env_self}")" && pwd)"

if _gf180_exports="$(python3 "${_gf180_sim_dir}/run_corners.py" --print-env)"; then
  eval "${_gf180_exports}"
  echo "gf180mcu: PDK_ROOT=${PDK_ROOT} PDK=${PDK}"
else
  echo "gf180mcu: PDK not found -- run 'python3 ${_gf180_sim_dir}/run_corners.py --check-env'" >&2
fi

unset _gf180_env_self _gf180_sim_dir _gf180_exports
