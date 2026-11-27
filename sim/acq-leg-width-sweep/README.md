# `sim/acq-leg-width-sweep/` -- intermediate acquisition-leg widths (issue #429)

Schematic-level SFDR / composed ENOB (125 C, 3 process x 3 supply) with only the
CDAC cell's fourth-leg (acquisition) T-gate scaled; C_u held at the ratified
35.6528 fF. Characterization only: no point is a verdict on any README row and
none replaces `sim/characterization-summary.md`. Read
[`findings-20261031.md`](findings-20261031.md) first -- all six width points
are measured (schematic, 125 C subset). [`findings-20261008.md`](findings-20261008.md)
holds the layout-cost table; its "spectral NOT measured" status is superseded.
`records/` also keeps the older `Overall: ERROR` blocker records, which the
collator skips.

    ./sim/acq-leg-width-sweep/run_sweep.sh [scale]          # via klt sim / batch fleet
    KLT_CMD="uvx --from klayout-tools==X.Y.Z klt" RUNNER_VERSION_CHECK=warn ...
    python3 sim/acq-leg-width-sweep/analyze_width_sweep.py --markdown

Layout counterpart: `layout/adc-top/candidates/gen_acq_leg_candidate.py --scale S`,
which is **historical for the six sweep scales** (1, 1.1, 1.25, 1.5, 1.75,
2.068). DR-0050 folds every decode-bank T-gate PMOS, and the layout rejects an
unpaired PMOS wider than `FOLD_ROW_MAX_W` (10 um), which the unfolded widened
`Xsi` is at all six scales; the generator now exits with a DR-0050 message
for them. The six scales are netlist-only (the `run_sweep.sh` reproduction
above is unaffected). The committed `layout/adc-top/candidates/acq-leg-*`
directories and records are unchanged evidence; a scale builds when its
drawn PMOS width (`20u * scale`, as emitted in the `wp=` token) is at most
`FOLD_ROW_MAX_W` -- `--scale 0.5` (5u/10u) and `--scale 0.4` are working
examples. Re-folding the widened leg would change the shared `Xsi` line
and the scale-for-scale comparability, so it is not done here.
