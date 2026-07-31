"""gf180-sar-adc simulation harness.

Reproducible ngspice + gf180mcu PVT corner running, writing append-only
evidence records in the format ratified in ``sim/README.md``.

Ported from ``2AMLogic/gf180-bandgap`` per CLAUDE.md ("copy the sim-harness
pattern ... rather than reinventing"). Divergences from upstream are
enumerated in ``sim/harness/README.md`` -- never forked silently.
"""

HARNESS_VERSION = "0.1.0"

#: The upstream commit on ``2AMLogic/gf180-bandgap`` this harness was ported
#: from. Recorded in every evidence record so a future reconciliation against
#: upstream knows exactly which revision was copied.
UPSTREAM_PATTERN = "2AMLogic/gf180-bandgap@58024be"

__all__ = ["HARNESS_VERSION", "UPSTREAM_PATTERN"]
