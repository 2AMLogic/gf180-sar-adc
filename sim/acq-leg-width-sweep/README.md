# `sim/acq-leg-width-sweep/` -- intermediate acquisition-leg widths (issue #429)

Schematic-level SFDR / composed ENOB (125 C, 3 process x 3 supply) with only the
CDAC cell's fourth-leg (acquisition) T-gate scaled; C_u held at the ratified
35.6528 fF. Characterization only: no point is a verdict on any README row and
none replaces `sim/characterization-summary.md`. Read
[`findings-20261008.md`](findings-20261008.md) first -- as of that memo **no
spectral point has been measured** (batch fleet blocked); `records/` holds only
`Overall: ERROR` blocker evidence, which the collator skips.

    ./sim/acq-leg-width-sweep/run_sweep.sh [scale]          # via klt sim / batch fleet
    KLT_CMD="uvx --from klayout-tools==X.Y.Z klt" RUNNER_VERSION_CHECK=warn ...
    python3 sim/acq-leg-width-sweep/analyze_width_sweep.py --markdown

Layout counterpart: `layout/adc-top/candidates/gen_acq_leg_candidate.py --scale S`.
