# DR-0019: Resize the CDAC unit capacitor to the gain-error matching coefficient

- **Status**: proposed
- **Date**: 2026-08-16
- **Decided by**: Builder agent, issue #177
- **Supersedes**: none — `spec/cdac-sizing-memo.md` §4's original `C_u`
  choice predates any decision-record gate on this design's sizing memos;
  this is the first decision record on the CDAC unit-cap value itself
- **Superseded by**: (none while this record stands)
- **Related**: #177 (this decision), #172 (the `klt yield` evidence that
  found the gap), #70/#80/DR-0017 (the CDAC layout area this decision
  compounds), `spec/cdac-sizing-memo.md` §3.6/§4 (the re-derivation this
  record implements), `spec/decision-records/DR-0011-cdac-switching-scheme.md`
  (the split topology whose free-MSB property does not extend to gain
  error), `spec/decision-records/DR-0012-gain-error-deterministic-vs-mismatch.md`
  (splits the ratified "Gain error" row into this mismatch half and a
  separate systematic half, unaffected by this record);
  reproducible evidence: `sim/mc-cdac-mismatch/records/
  20260816-125421-737d16e.md`, `layout/adc-top/area_feasibility.py`

## Context

`sim/mc-cdac-mismatch/records/20260816-044942-56fbe50.md` (issue #172)
measured the ratified `README.md#target-specification` **Gain error,
mismatch** row (`≤ 0.5 LSB`, untrimmed, 3σ Monte Carlo mismatch) at
**2.12σ** against its own 3σ condition — `0.708 LSB` at 3σ, against the
built design's calibrated unit-cap mismatch `σ_u = 0.7372097807744856 %`
(`C_u = 17.24 fF`, `spec/cdac-sizing-memo.md` §3.4/§4, chosen 2026-07-31).
This is a real design gap, not a testbench defect: `spec/cdac-sizing-memo.md`
§3.6 (added by this issue) shows `C_u` was sized against the DNL/INL
matching coefficient (`σ(DNL) = 22.61·σ_u`, requiring `σ_u ≤ 0.737 %` at the
stretch target) rather than the gain-error coefficient
(`σ(gain error) = 32·σ_u`, requiring the tighter `σ_u ≤ 0.521 %`) — gain
error is a total-array-capacitance sum (`C_total = 1024·C_u`,
§5.2) that does not benefit from DR-0011's free-MSB relief the way DNL/INL
do (§3.1–§3.2), so it was never checked against its own, tighter
requirement until #172's `klt yield` run measured it directly.

## Decision

**Resize the CDAC unit capacitor from `C_u = 17.24 fF` (2.7136 µm square,
`σ_u = 0.7372 %`) to `C_u = 35.6528 fF` (4.0 µm square, `σ_u = 0.5000 %`)**,
sized to the gain-error matching constraint (`spec/cdac-sizing-memo.md`
§3.6/§4, the binding one of the three matching-based rows — gain error's
`σ_u ≤ 0.521 %` ceiling is tighter than DNL/INL's `≤ 0.737 %` stretch
ceiling by `√2`), with a deliberate margin over that constraint's
exact-boundary value (`33.00 fF` / `3.84 µm` / `σ_u = 0.5208 %` — see
Alternatives).

**Verification** (`sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`,
behavioral Monte Carlo, N = 20000, same methodology and seed as every prior
campaign in `sim/mc-cdac-mismatch/`, since the gf180mcu PDK ships no local
capacitor mismatch model to simulate against directly):

- **Gain error, mismatch**: `klt yield` `status: pass`, `sigma_to_spec =
  3.13`, empirical yield 0.998100 [0.997393, 0.998655] against the ratified
  0.9973 target; negative control at 3× `σ_u` correctly detected (yield
  0.7095); analytic cross-check consistent (Δ −0.31 %, matching the same
  small analytic-vs-measured gap #172's own record showed).
- **DNL/INL** (re-stated, not assumed, per issue #177's Acceptance
  Criteria): 3σ DNL = 0.340 LSB, 3σ INL = 0.170 LSB, both clearing the
  `< 0.5 LSB` **stretch** target (not merely the `< 1 LSB` baseline) with
  wide margin — confirming `spec/cdac-sizing-memo.md` §3.6's prediction that
  sizing to the (tighter) gain-error constraint satisfies DNL/INL
  automatically.

**This decision does not itself change any ratified spec value** — it
implements the existing ratified `≤ 0.5 LSB` gain-error target more
correctly; the target itself is untouched, per `CLAUDE.md`'s "agents do not
relax the ratified spec to make results pass."

**Scope limitation, stated plainly**: this record is the **sizing decision**
and its **verification against the standalone Monte Carlo mismatch model**
(the same evidentiary standard `spec/cdac-sizing-memo.md` already uses for
every matching-based row, since the PDK has no local capacitor mismatch
model to simulate against on a real netlist). It does **not** update
`design/adc-top/gen_adc_top.py`'s `C_UNIT_FF` constant or
`layout/adc-top/`'s `UNIT_CAP_NM` constant, and it does **not** re-run the
existing transistor-level PVT verification suite (INL/DNL environmental
half, ENOB/FFT, SFDR, power, `sim/cdac-bit-settling/`) — see Consequences.

## Alternatives considered

- **Exact-boundary sizing** (`σ_u = 0.520833 %` = the exact inverse of
  `3σ = 0.5 LSB`, `C_u = 33.00 fF`, `s = 3.84 µm`) — tried first, and
  rejected. `sim/mc-cdac-mismatch/records/20260816-125421-737d16e.md`'s
  "Rejected exact-boundary alternative" shows this measured `sigma_to_spec
  = 3.009` — statistically indistinguishable from the `3.0` threshold this
  whole issue exists to move away from (the historical sizing's own
  `2.12σ` result already shows how sensitive this figure is to which
  coefficient it is checked against; a knife-edge `3.009σ` invites exactly
  the same kind of near-miss on a different seed, a different `A_C`
  re-estimate, or a small model refinement). The chosen `s = 4.0 µm` costs
  only **+1.8 %** more array area than the exact-boundary point
  (0.18045 mm² vs. 0.17721 mm², `layout/adc-top/area_feasibility.py`) for a
  real margin (`3.13σ`), so the trade was cheap and taken.
- **A larger margin** (e.g. sizing to an analytic `3σ ≤ 0.45 LSB`, 10 %
  margin under target, `C_u ≈ 40.3 fF`, `s ≈ 4.27 µm`) — not chosen. The
  area cost of *any* size in this range is dominated by the tile-pitch's
  fixed `MIMTM.3`/`MIMTM.1` ring-and-spacing addition (`+2.4 µm` to the
  plate side regardless of plate size, `spec/cdac-sizing-memo.md` §4
  cross-reference, `layout/adc-top/gen_adc_top.py`), not by the plate area
  itself, so a bigger margin buys progressively less resolution-per-area —
  moving from `s = 4.0 µm` to `s = 4.27 µm` (an additional +6.6 % analytic
  margin) costs another `~3 %` of array area for a benefit issue #177 does
  not need: `3.13σ` is already a real, non-knife-edge margin, and the DNL/
  INL/kT/C/DR-0002 cross-checks (`spec/cdac-sizing-memo.md` §5) all still
  clear their own bounds comfortably at `s = 4.0 µm`.
- **Trade DNL/INL margin instead of resizing `C_u`** (the original issue's
  "e.g." framing) — not applicable here. `spec/cdac-sizing-memo.md` §3.6
  shows gain error's own coefficient is the *tightest* of the three
  matching-based rows, so there is no DNL/INL-margin-for-gain-error-margin
  trade available in the other direction: any `C_u` that clears gain error
  clears DNL/INL with room to spare (verified directly above), not the
  reverse.
- **Do nothing (report the `2.12σ` finding as a permanent open item)** —
  not chosen. `CLAUDE.md`'s "no claim without a testbench" / "verification
  is the product" culture treats a measured gap against a ratified target as
  something to close, not carry indefinitely, when a design-side fix is
  available and (as shown above) cheap in area.

## Consequences

- **The gain-error mismatch mechanism is verified to clear its ratified 3σ
  target at the chosen sizing** (`sim/mc-cdac-mismatch/records/
  20260816-125421-737d16e.md`) — the specific finding issue #172/#177 exists
  to close is closed at the sizing-decision level.
- **`C_total` grows from 17.65 pF to 36.51 pF (≈ 2.07×)** — the number
  `spec/cdac-sizing-memo.md` §5.2 flags for #12 (settling/timing budget) and
  #15/#16 (array layout). §5.3's DR-0002 cross-check re-derives the
  reference-drive envelope at the new value and still clears it
  (`C_dec,min ≈ 9.35 nF` vs. `≥ 40 nF`, `Z_ref,max ≈ 899 Ω` vs. `≤ 240 Ω`),
  with less headroom than the historical sizing left.
- **kT/C noise margin only improves** (bigger `C_u` means less sampled
  thermal noise) — no risk introduced there (§5.1, ~478× headroom at the
  resized value vs. ~231× before).
- **The array area cost is real and is surfaced here, not hidden.**
  `layout/adc-top/area_feasibility.py`, re-run with the resized plate
  geometry (`s = 4.0 µm`, in-memory rebuild, nothing written to disk):
  `adc_block` bounding box moves from **0.15446 mm² (154 % of the original
  `< 0.1 mm²` DR-0006 target) to 0.18045 mm² (180 % of that target)** — a
  **+16.8 % area increase** (+0.02599 mm²) on top of an **already-worse-than-
  documented** baseline. **Neither of these numbers is the `0.121 mm²`
  figure DR-0017 records**: DR-0017 (2026-08-04, status `proposed`, not yet
  ratified) predates issue #118's comparator growth, and
  `layout/adc-top/README.md` already documents (independently of this
  record) that the *current, un-resized* design measures `0.15446 mm²`, not
  DR-0017's `0.12100 mm²` — DR-0017 itself is stale pending its own
  superseding record. **This decision compounds an already-unresolved,
  operator-pending area situation rather than creating a new one.** It does
  not attempt to resolve either the pre-existing comparator-growth drift or
  DR-0017's own pending ratification — both are out of this issue's scope
  (`CLAUDE.md`: agents do not silently absorb an area overrun; DR-0017's own
  template requires operator ratification for any area **target** change,
  which this record does not attempt) — but the resize's own marginal cost
  (+16.8 % over the current as-built baseline) is quantified here so a
  future area-target decision has the real number, not an unverified
  "roughly 2×" estimate (the Curator's own back-of-envelope on issue #177,
  explicitly flagged there as unverified). The actual cost is far below 2×
  because the dominant array-area term is the fixed `MIMTM.3`/`MIMTM.1`
  ring-and-spacing addition to the tile pitch (`+2.4 µm`, independent of
  plate size), not the plate area itself, and because the decode bank and
  comparator — not the CDAC array — are large, fixed contributors to
  `adc_block`'s bounding box.
- **Not done by this record, tracked as follow-up work**:
  1. Update `design/adc-top/gen_adc_top.py`'s `C_UNIT_FF` (currently
     `17.24`) and `layout/adc-top/`'s `UNIT_CAP_NM` (`gen_adc_top.py`'s own
     module constant and `layout/adc-top/cells/gen_adc_cells.py`'s, both
     currently `2714`) to the resized value, regenerate the committed
     design-netlist artifacts (`design/adc-top/adc_top.spice` and the three
     spec-line testbenches `test_adc_top_netlist.py` guards), and redraw/
     DRC/LVS-check the physical layout.
  2. **Re-run the full transistor-level PVT verification suite at the
     resized `C_u`** — INL/DNL (environmental half), ENOB/FFT, SFDR, power,
     and `sim/cdac-bit-settling/'s own 117-point settling campaign — all of
     which currently certify the **historical** `C_u = 17.24 fF` design.
     This is a large, separately-schedulable body of work (the same scale as
     issues #17/#89/#116/#123/#151/#173 combined took to build up the
     existing evidence base) and is explicitly **not** attempted in this
     record: doing so here would either take an infeasible amount of time
     for one issue or produce unverified claims, neither of which this
     repo's "verification is the product" culture permits. Until that
     follow-up lands, `README.md`, `sim/characterization-summary.md`, and
     `spec/testbench-suite-memo.md` continue to correctly describe the
     **built** design (`C_u = 17.24 fF`) for every row except gain error,
     mismatch, whose sizing decision (not yet physically implemented) is
     recorded here.
  3. A superseding area-target decision record, once the physical layout is
     redrawn at the resized geometry, reconciling this record's compounded
     number with DR-0017's own pending (and, per the point above, already
     stale) ratification.

## Spec lines affected

- `spec/cdac-sizing-memo.md` §3 — new §3.6, "Gain error, mismatch: a
  total-array sum, not a DNL/INL coefficient" — new derivation.
- `spec/cdac-sizing-memo.md` §4 — "Required unit-cap area and capacitance" —
  changed (adds the gain-error row to the requirement table; "Chosen unit
  cap" changed `17.24 fF` → `35.6528 fF`, with the historical value kept for
  provenance).
- `spec/cdac-sizing-memo.md` §5.1/§5.2/§5.3/§6 — re-derived at the resized
  `C_u` (matching-vs-kT/C ratio, `C_total`, DR-0002 cross-check, summary).
- `README.md#target-specification` — **Gain error, mismatch** row and note
  **[e]** — not changed by this record directly (the row still correctly
  describes the *built* design, `σ_u = 0.7372 %`, per the Consequences
  scope-limitation above); a documentation cross-reference to this record is
  added, not a verdict change, since the physical implementation is still
  pending.
