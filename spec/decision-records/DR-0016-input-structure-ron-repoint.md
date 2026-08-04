# DR-0016: Input-structure series `R_on` — re-point the ratified row's evidence from the removed dedicated switch to the DR-0014 T-gate-array path

- **Status**: ratified — Builder agent, issue #75
- **Date**: 2026-08-04
- **Decided by**: Builder agent, issue #75
- **Supersedes**: none — this record does not reopen
  [DR-0011](DR-0011-cdac-switching-scheme.md)'s or
  [DR-0014](DR-0014-bottom-plate-sampling.md)'s decisions (both stand
  unchanged); it settles the re-measurement DR-0014's own Consequences
  deferred, on a value DR-0014 never itself claimed.
- **Superseded by**: (none while this record stands)
- **Related**: #53, #61, #75,
  [DR-0014 (bottom-plate sampling)](DR-0014-bottom-plate-sampling.md) —
  Consequences ("Two published Input-structure numbers must be re-measured")
  and Spec lines affected ("evidence stale, value unchanged"),
  `spec/testbench-suite-memo.md` §11.4 ("The two published numbers DR-0014
  invalidated the evidence for"),
  `sim/dr0014-sampling/records/20260802-141402-1224e11.md` (the
  `ron_path_*_ohm` / `ron_cell_*_ohm` measurement)

## Context

The ratified `README.md#target-specification` Input-structure row publishes
`series switch R_on 156–570 Ω over PVT at the characterization geometry`,
measured on the dedicated 40 µm/80 µm input sampling switch
(`sim/device-characterization-report.md` §2.1) that
[DR-0011](DR-0011-cdac-switching-scheme.md) sampled the input through. DR-0014
removed that switch from the converter: the input now reaches the array
through **nine parallel bottom-plate cell T-gates per side** (one per switched
weight, 10 µm/20 µm each), and DR-0014's own Consequences and Spec-lines
sections say the published `R_on` figure is therefore stale evidence — a
value the design no longer produces — while explicitly deferring the
re-measurement to land with the design change rather than inside that record.

`sim/dr0014-sampling/` (#61, `sim/dr0014-sampling/records/20260802-141402-1224e11.md`)
is that re-measurement, on the converter as DR-0014 actually built, by the
same forced-voltage/measured-current method the original 156–570 Ω figure
used. Over the 27-point full PVT grid, the worst per-side path resistance
(`ron_path_worst_ohm`) is **21.3293 Ω** at `ff_-40c_3.63v` (best) and
**60.0218 Ω** at `ss_125c_2.97v` (worst) — i.e. **21.3–60.0 Ω**, roughly 7–10×
lower than the published figure, in the favourable direction. The per-cell
figure (`ron_cell_*_ohm`, nine T-gates in parallel) spans **119.777–540.196 Ω**
at the same two corners. `C_in` is unaffected (the array is untouched, and
`sim/dr0014-sampling/` measures the drivers unchanged), so DR-0013's
`R_source × (C_pin + C_in) ≤ 30 ns` contract and the ≥ 5.3 MHz T/H bandwidth
are not implicated and are not touched here — only the `R_on` figure moved.

## Decision

**The Input-structure row's series switch `R_on` figure is changed from
`156–570 Ω` to `21.3–60.0 Ω`, and its evidence citation is re-pointed from
`sim/device-characterization-report.md` §2.1 (the removed dedicated switch) to
`sim/dr0014-sampling/records/20260802-141402-1224e11.md` (the nine-parallel
T-gate path DR-0014 built).** No target is relaxed or tightened — the row
carries no target/stretch value (its column reads `—`), only a measured
figure — and no other cell of the row changes: `C_in = 8.827 pF` per side and
the `≥ 5.3 MHz` T/H bandwidth stand exactly as published, per DR-0014's own
Consequences.

| `README.md#target-specification` field | Was | Now |
|---|---|---|
| Input-structure row — series switch `R_on` | 156–570 Ω, "at the characterization geometry" | **21.3–60.0 Ω**, nine parallel bottom-plate cell T-gates per side |
| Input-structure row — binding corner/condition citation | `R_on` range over the 45-point grid, worst `ss_125c_2.97v` ([devchar §2.1]) | `R_on` range over the 27-point grid, worst `ss_125c_2.97v` ([`sim/dr0014-sampling/`](../../sim/dr0014-sampling/records/20260802-141402-1224e11.md)) |

Note **[f]** is reviewed and left unchanged: it derives the T/H bandwidth from
`R_source × (C_pin + C_in)` — the *external* drive resistance and `C_in`, not
the switch's own `R_on` — and does not itself restate the `156–570 Ω` (or any
other) numeric `R_on` figure, so there is no second numeric instance to
correct there. `devchar §2.1`'s own text is left untouched (append-only,
`sim/README.md`): it correctly describes the switch it measured, which is no
longer the one in the converter, and this record's context section states
that plainly rather than editing history.

## Alternatives considered

- **Leave the row as published and rely on DR-0014's Consequences text to
  flag the staleness.** Not chosen: `CLAUDE.md` requires spec changes to go
  through a decision record, and a reader landing on `README.md`'s ratified
  table — the document this repo asks outside readers to check — sees only
  the stale `156–570 Ω`, not DR-0014's caveat six files away. Leaving it
  published understates the block's actual (better) series resistance by
  7–10× indefinitely.
- **Fold this correction into a future record that also changes something
  else about the input structure.** Not chosen: one decision per record
  (`spec/decision-records/README.md`). This is a self-contained evidence
  re-point with no other spec-line dependency, and bundling it with an
  unrelated future decision would make that decision's supersession drag an
  already-settled question along with it.
- **Re-derive a fresh characterization deck for the T-gate array instead of
  citing `sim/dr0014-sampling/`.** Not chosen: `sim/dr0014-sampling/`
  already measures `R_on` by the same forced-voltage/measured-current method
  on the exact converter DR-0014 built, over the full 27-point PVT grid,
  clean-tree and `PASS` (#61). Re-deriving the same number in a second deck
  would duplicate evidence without changing the answer, and this repo's own
  convention is to cite the existing `sim/` record rather than re-run a
  settled measurement.
- **Publish only the per-cell figure (119.8–540.2 Ω) instead of the per-side
  path figure (21.3–60.0 Ω).** Not chosen: the row states a *series switch
  R_on*, i.e. the resistance the input actually sees between the pin and the
  array, which is the nine T-gates in parallel — the path figure. The
  per-cell figure is retained in this record's Context for readers who want
  the single-device number, matching how `spec/testbench-suite-memo.md`
  §11.4 already reports both.

## Consequences

- **The published Input-structure `R_on` figure gets better, not worse** —
  the design change DR-0014 made for linearity reasons also happens to
  lower series resistance, since nine T-gates in parallel beat one dedicated
  switch. There is no bad consequence to the value itself; the residual risk
  is process/documentation only, stated next.
- **`devchar §2.1`'s 156–570 Ω figure is now documentation of a switch this
  design no longer contains.** It is not deleted or edited (`sim/` records
  are append-only), but a reader who opens `sim/device-characterization-report.md`
  directly, without first reading `README.md`'s row or this record, can be
  misled into thinking that figure still governs the converter. This is the
  same residual risk DR-0014's own Consequences already named and accepted
  for the interim; this record does not add to it, and closes the interim by
  giving `README.md` a citation that points at the current path.
- **Any future re-topology of the input path (a further change to which
  switches sample the input) invalidates this record's citation the same way
  DR-0014 invalidated the one before it**, and must be re-measured and
  re-pointed the same way — this record does not claim permanence for the
  T-gate-array path, only correctness as of the path DR-0014 built.
- **No downstream row is affected.** `C_in`, the `R_source × (C_pin + C_in) ≤
  30 ns` contract, and the ≥ 5.3 MHz T/H bandwidth are unchanged; no other
  ratified row cites the Input-structure `R_on` figure.

## Spec lines affected

- `README.md#target-specification` — Input structure row, series switch
  `R_on` — **changed** (`156–570 Ω` → `21.3–60.0 Ω`), citation re-pointed
  from `sim/device-characterization-report.md` §2.1 to
  `sim/dr0014-sampling/records/20260802-141402-1224e11.md`.
- `README.md#target-specification` — Input structure row, binding
  corner/condition column — **changed**: grid size `45-point` → `27-point`
  to match the new citation's grid; corner (`ss_125c_2.97v`) and structure
  (note **[f]** reference) unchanged.
- `README.md#target-specification` — note **[f]** — **reviewed, no change**:
  does not restate the `R_on` numeric figure and its `R_source × (C_pin +
  C_in)` derivation is unaffected.
- `spec/decision-records/DR-0014-bottom-plate-sampling.md` — **not edited**:
  its Consequences already state the figure was stale and defer the
  re-measurement here; no `Supersedes` relationship applies because DR-0014
  made no numeric `R_on` claim of its own to replace.
