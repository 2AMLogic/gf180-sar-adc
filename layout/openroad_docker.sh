#!/usr/bin/env bash
#
# layout/openroad_docker.sh -- invoke the pinned openroad/orfs Docker image's
# `openroad` binary as if it were a native `openroad` on $PATH.
#
# Why a container, not a native install: `openroad` has no Homebrew formula
# and no common Linux-distro package as of this writing. OpenROAD-flow-scripts
# (ORFS) publishes an official Docker image with a matched, pinned OpenROAD +
# Yosys + KLayout toolchain -- 2AMLogic/klayout-tools's own
# `docs/design/openroad-invocation-survey.md` and `docs/cli/place-and-route.md`
# ("Installing OpenROAD" -> "Docker: extract the binary onto $PATH") already
# document this route. `2AMLogic/gf180-trng`'s `layout/openroad_docker.sh`
# (issue #111) provisions `openroad` the same way for its own `klt
# place-and-route` runs; this is that same pattern, ported here for issue
# #274 rather than reinvented, per `CLAUDE.md`'s "bootstrap from the
# sim-harness pattern... rather than reinventing" rule generalised to "port
# from a sibling repo's flow driver when one exists".
#
# Usage (identical to a native `openroad` binary):
#   ./layout/openroad_docker.sh -version
#   ./layout/openroad_docker.sh -no_init -exit script.tcl
#
# The current working directory is bind-mounted into the container at the
# *same absolute path* it has on the host (not a fixed /workspace) -- this
# matters beyond relative paths: `klt place-and-route` (klayout-tools)
# generates its per-stage Tcl scripts with **absolute host paths** baked in
# throughout (the netlist, the LEF/liberty deck, and every
# `-metrics`/`write_db`/`write_def` output path). Mounting source==target for
# both the repo tree and the resolved PDK root (below) is what makes those
# absolute paths resolve identically on both sides of the container boundary.
# Set OPENROAD_DOCKER_MOUNT to bind-mount a different host directory instead
# of $(pwd).
#
# -- pinned version -- keep in sync with layout/sar-logic/README.md --------
# `openroad -version` inside this image reports 26Q3-2056-g41a28926b9.
OPENROAD_DOCKER_IMAGE="${OPENROAD_DOCKER_IMAGE:-openroad/orfs:latest}"
OPENROAD_DOCKER_DIGEST="${OPENROAD_DOCKER_DIGEST:-sha256:ee88641037a1c8e3403203bdca2b6256bf44a7957fa26719c8463ba638d76f9d}"
# ----------------------------------------------------------------------------

set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "FATAL: docker not found on \$PATH." >&2
  echo "  openroad is provisioned on this host only via the pinned" >&2
  echo "  ${OPENROAD_DOCKER_IMAGE} Docker image -- install Docker and re-run." >&2
  echo "  See layout/sar-logic/README.md's 'OpenROAD' section." >&2
  exit 1
fi

# Prefer a plain `docker` the caller can already run; fall back to
# non-interactive sudo for hosts where the invoking user is not in the
# `docker` group but has passwordless sudo. `sudo -n` never blocks on a
# password prompt -- it fails fast instead, so this fallback is safe to try
# unconditionally.
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  if sudo -n docker info >/dev/null 2>&1; then
    DOCKER=(sudo -n docker)
  else
    echo "FATAL: docker daemon is not reachable (not running, or this user" >&2
    echo "  has neither docker-group membership nor passwordless sudo)." >&2
    exit 1
  fi
fi

MOUNT_DIR="${OPENROAD_DOCKER_MOUNT:-$(pwd)}"

# Resolve the PDK root the same way klayout-tools' `find_pdk()` does
# (sim/harness/pdk.py's own resolution order: GF180_PDK_PATH, PDK_ROOT, then
# ~/.ciel, then ~/.volare) so it can be bind-mounted too -- `klt
# place-and-route`/`klt synthesize` resolve liberty/LEF paths under there,
# and those absolute host paths need to exist inside the container at the
# identical path. Best-effort: if none of these exist, no extra mount is
# added and a downstream `openroad` "cannot read file" error will point at
# the same gap this comment describes.
PDK_MOUNT_DIR=""
if [ -n "${GF180_PDK_PATH:-}" ]; then
  PDK_MOUNT_DIR="$(dirname "${GF180_PDK_PATH}")"
elif [ -n "${PDK_ROOT:-}" ] && [ -d "${PDK_ROOT}" ]; then
  PDK_MOUNT_DIR="${PDK_ROOT}"
elif [ -d "${HOME}/.ciel" ]; then
  PDK_MOUNT_DIR="${HOME}/.ciel"
elif [ -d "${HOME}/.volare" ]; then
  PDK_MOUNT_DIR="${HOME}/.volare"
fi

VOLUME_ARGS=(-v "${MOUNT_DIR}:${MOUNT_DIR}")
if [ -n "${PDK_MOUNT_DIR}" ] && [ "${PDK_MOUNT_DIR}" != "${MOUNT_DIR}" ]; then
  VOLUME_ARGS+=(-v "${PDK_MOUNT_DIR}:${PDK_MOUNT_DIR}")
fi

exec "${DOCKER[@]}" run --rm --platform linux/amd64 \
  "${VOLUME_ARGS[@]}" \
  -w "${MOUNT_DIR}" \
  "${OPENROAD_DOCKER_IMAGE}@${OPENROAD_DOCKER_DIGEST}" \
  bash -lc 'source /OpenROAD-flow-scripts/env.sh >/dev/null 2>&1 && exec openroad "$@"' bash "$@"
