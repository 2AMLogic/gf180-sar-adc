# DR-0025: The candidate CDAC acquisition-leg widening is NOT adopted — ENOB/SFDR remain FAIL, no admissible change closes them

- **Status**: ratified
- **Date**: 2026-08-25
- **Decided by**: Builder agent, issue #249
- **Supersedes**: none — first record on this specific candidate's
  adoption question
- **Superseded by**: (none while this record stands)
- **Related**: #211 (found the candidate lever and deferred five
  measurements before it could be read as achievable margin), #238 (parent
  issue decomposing the five measurements this record synthesizes; this
  record is #238's final increment), #244/#245/#246/#247/#248 (the five
  measurement issues, closed), #249 (this decision + re-run), DR-0019 (the
  ratified `C_u` resize whose dynamic-range cost this record evaluates one
  candidate fix for — untouched by this record), DR-0024 (the still-`proposed`
  Area budget reconciliation this record's Consequences interact with),
  `sim/dr0019-cu-sweep-findings.md` (the mechanism isolation and orthogonal
  control this record's Context evidence rests on), `sim/characterization-
  summary.md`, `README.md#target-specification`, `sim/extracted-delta-
  summary.md` §4.13.2 (updated alongside this record)

## Context

`sim/dr0019-cu-sweep-findings.md` (issue #211) isolated the mechanism behind
the ENOB/SFDR regression DR-0019's CDAC unit-cap resize caused: a
signal-dependent acquisition-lag distortion `R_on(V_in)·C_arr·dV_in/dt` that
scales with the array capacitance. An orthogonal control — holding the
ratified `C_u = 35.6528 fF` fixed and widening only the CDAC cell's
fourth-leg (acquisition) T-gate 2.068× (`CDAC_SW_WN`/`CDAC_SW_WP`, `10u`/`20u`
→ `20.68u`/`41.36u`) — recovered most of the loss **in that one schematic-
level, 125 °C-only, 9-point deck**: worst-corner SFDR 56.41 → 60.80 dB (89 %
of the loss) and worst-corner composed ENOB 8.507 → 9.170 bits (101 %, back
above the pre-resize 9.163 bits). That page explicitly declined to read the
recovery as achievable margin and named five measurements a follow-up would
need first (§4, "Recommendation"). Issue #238 decomposed those five; all five
have now landed with governing `sim/`/`layout/` records (table below). This
record is the synthesis #238 and #249 exist to produce: does the total
evidence support adopting the candidate width, and — per `CLAUDE.md`'s
"agents do not relax the ratified spec to make results pass" — if not, that
is recorded plainly rather than worked around.

**The governing ENOB/SFDR rows FAIL independently of this record's
conclusion.** The current extracted (governing) campaign
([`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](../../sim/adc-enob-fft/records/20260825-061750-d00911a.md),
a clean-tree re-take of the design as ratified today, superseding the
dirty-tree `20260817-215657-076d545`) measures worst ENOB **8.857 bits**
(`tt_125c_3.63v`, target `> 9.0`) and worst SFDR **60.40 dB**
(`ff_125c_3.63v`, target `≥ 62 dB`) — byte-identical per-sample codes and
identical spectral figures to the record it supersedes, because the ratified
design (`CDAC_SW_WN`/`CDAC_SW_WP` still `10u`/`20u`) has not changed.

### The five measurements, read together

| # | Question | Record | Finding |
|---|---|---|---|
| 1 | Charge injection / clock feedthrough from the wider switch (`sim/dr0014-sampling/`, issue #244/PR merged) | [`20260825-015032-446a3c4`](../../sim/dr0014-sampling/records/20260825-015032-446a3c4.md) | **PASS, noise-floor cost.** Full ratified 27-point PVT grid, schematic. Every charge-injection/settling term this deck reports moves by noise-floor amounts at the candidate width (`samp_inl_worst_lsb` 0.30895 → 0.30915 LSB against the ±1 LSB bound; `bp_inj_mis_lsb`, `set_err_4leg_lsb`, `hold_l4_lsb` unchanged to the deck's own numerical floor), while `ron_path_worst_ohm` **halves** as `R_on ∝ 1/width` predicts (60.02 → 29.03 Ω) — the mechanism the width change is supposed to fix, confirmed fixed at the leaf level. Caveat carried forward: this deck's DR-0014 two-phase top-plate sample is architected to reject switch injection as a common-mode term regardless of switch width, a plausible reason this term costs so little here. |
| 2 | Top-plate `C_par` the wider device adds, and the `C_arr/(C_arr+C_par)` divider it feeds (`sim/top-plate-cpar/`, issue #245, PR #254) | [`20260825-034455-4cf1ca4`](../../sim/top-plate-cpar/records/20260825-034455-4cf1ca4.md) | **PASS, structural invariance.** Full 63-point `cdac` capacitor-corner grid, schematic. `c_arr_v1p65_ff`/`c_sw_v1p65_ff` bit-identical on all 63 rows; every `cpar_v*_ff` column moves ≤ 0.0033 fF (≤ 0.0056 %) and `gain_err_v1p65_pct` by ≤ 2×10⁻⁵ percentage points. Read out of the netlist, not asserted: the acquisition leg (`Xsi`) sits between the cell's `vin` port and the **bottom** plate, and in this deck's measurement state (leg off, released to `V_cm`) both its terminals sit on ideal-source-pinned nodes, so its off-state capacitance contributes no displacement current to the ramp that measures the top plate. |
| 3 | Comparator kickback / DR-0014 sampling-instant definition (`sim/comparator-kickback/`, issue #246, closed) | [`20260825-044912-9fe3b68`](../../sim/comparator-kickback/records/20260825-044912-9fe3b68.md) (after #250's unrelated `peak_dip_uv` floor recalibration) | **PASS, structural invariance — not a fresh measurement.** This deck carries **no acquisition-leg T-gate device of any kind** (confirmed by a full-file read) — it drives the comparator from a lumped RC top-plate model, not the CDAC array — so the candidate width has no netlist parameter to vary here. Two coupling paths were traced, not just asserted: kickback itself originates entirely inside the comparator subckt (no path through a CDAC switch), and DR-0014's sampling instant is defined solely by the top-plate `V_cm` switch (`adc_tp_sw`) opening, a different device from the widened fourth leg. This item's outcome is legitimately a documented invariance finding, not a new PASS/FAIL number, and must not be read as one. |
| 4 | Clock-driver load and power (`sim/adc-power/`, issue #247, PR #257) | [`20260825-044700-9229d0d`](../../sim/adc-power/records/20260825-044700-9229d0d.md) | **PASS, small and localized cost.** Full ratified 27-point PVT grid, schematic. The CDAC-driver block (`p_cdac_*_uw`) that drives the widened gate grows +9.4…+15.1 % at the binding corner, but it is only ~15–20 % of total converter power, so the grid-worst `p_total_*_uw` moves 207.884 → 208.744 µW, **+0.41 %** — the ratified `< 1 mW` row keeps 4.79× margin and the `< 500 µW` stretch keeps 2.4×. The ratified Power row does not move into risk at this geometry. |
| 5 | Array area and routing (`layout/adc-top/candidates/`, issue #248, PR #252) | [`20260825-030447-4e220d1`](../../layout/adc-top/candidates/records/20260825-030447-4e220d1.md) | **The one deferred item that argues against the lever.** Not a schematic estimate — a genuine `klt`-verified re-layout (DRC-clean, LVS-matched on both `ADC_TOP` and `ADC_BLOCK`) of the candidate geometry reached through the width-parametric placer. `block_total` grows 150,536.239 → **176,126.8006 µm² (+17.00 %, +0.150536 → +0.176127 mm²)**, a height-only growth of the decode-bank row (the bank's tallest active becomes the widened `Xsi`, not the ratified 10u/20u legs) diluted from a per-bank-row +69.69 % once amortised over the CDAC arrays / comparator / SAR-logic reserve, none of which the candidate touches. |

### Why item 5 is decisive

Both readings of the Area row already fail at the **ratified** geometry
(0.150536 mm²): +50.5 % over the still-nominally-ratified `README.md` line
98 (`< 0.1 mm²`, DR-0006), and −5.9 % (i.e. compliant, if ratified) against
the `< 0.16 mm²` figure DR-0024 has *proposed* — not yet ratified — to
reconcile it. The candidate acquisition-leg width does not merely fail to
help the Area row, it makes both readings measurably worse: **+76.1 % over**
the still-ratified `< 0.1 mm²` target, and **+10.1 % over even DR-0024's own
proposed relaxed figure**, which the ratified geometry currently satisfies.
Adopting the candidate would not just fail an already-failing row harder —
it would retroactively invalidate the one pending area reconciliation
already in flight, forcing a *second*, larger relaxation of the same row
specifically to admit this candidate. That is exactly the shape `CLAUDE.md`
rules out: a spec value bent to manufacture a pass, here transplanted from
the row under test (ENOB/SFDR) onto a different one (Area) that would have
to give further ground instead.

**The evidence quality is also asymmetric.** The benefit side — 89–101 % of
the SFDR/ENOB loss recovered — is a **schematic-level, 125 °C-only, 9-point**
measurement (the same subset `sim/dr0019-cu-sweep-findings.md` used, not the
full ratified 27-point PVT grid, and not against extracted parasitics of the
candidate layout). The cost side — the +17.00 % area growth — is a
**DRC-clean, LVS-matched, fully re-drawn** physical measurement. Even setting
the Area argument aside, the recovery this record would need to act on has
not itself been confirmed at the rigor level (extracted, full-grid) this
row's own governing citation requires — re-doing that extraction-and-resim
step for a candidate this record is about to reject is not a productive use
of the verification budget `CLAUDE.md`'s "verification is the product"
principle asks to spend deliberately.

## Decision

**The candidate CDAC acquisition-leg T-gate widening (`CDAC_SW_WN`/
`CDAC_SW_WP`, `10u`/`20u` → `20.68u`/`41.36u`) is NOT adopted.**
`design/adc-top/gen_adc_top.py`'s ratified geometry is unchanged by this
record. The ENOB @ Nyquist (`> 9.0`) and SFDR @ Nyquist (`≥ 62 dB`) rows
remain **FAIL** on the governing extracted side — worst ENOB 8.857 bits
(`tt_125c_3.63v`), worst SFDR 60.40 dB (`ff_125c_3.63v`) — per the clean-tree
re-take
[`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](../../sim/adc-enob-fft/records/20260825-061750-d00911a.md),
which reproduces the superseded `20260817-215657-076d545` figures exactly
(byte-identical per-sample codes at all nine corners) because the design did
not change. **No ratified spec value is relaxed to manufacture a pass on
either row.**

This closes #238 and #211's open question for the *specific* candidate
measured: the 2.068× acquisition-leg width is evaluated on its own merits,
not adopted, and the ENOB/SFDR FAILs stand as a recorded, unresolved
regression from DR-0019's `C_u` resize — exactly the outcome `CLAUDE.md`
requires when "the evidence does not support adopting the width change":
recorded plainly, not forced.

## Alternatives considered

- **Adopt the 2.068× width and accept the Area cost, deferring Area's own
  resolution to DR-0024/#237** — not chosen. DR-0024 is itself unratified
  and was sized specifically to bound the *current* as-built geometry
  (150,536.239 µm², −5.9 % margin under its proposed `< 0.16 mm²`); adopting
  this candidate would push the design **out of range of the very target
  DR-0024 was proposed to reconcile** (+10.1 % over `< 0.16 mm²`), turning
  one pending area decision into a resolved failure the moment it is
  ratified. Accepting that trade silently, or asking DR-0024 to widen its
  own bound further to absorb it, is exactly the "relax the ratified spec to
  make results pass" pattern `CLAUDE.md` forbids — moved from the row under
  test onto a different one.
- **Adopt at a smaller scale factor than 2.068×, splitting the difference
  between recovery and area cost** — not chosen, for lack of evidence, not
  on principle. No measurement in this record's evidence base (or `sim/
  dr0019-cu-sweep-findings.md`'s) characterizes any acquisition-leg width
  between the ratified 1× and the candidate 2.068×. Adopting an untested
  intermediate width, or asserting it would trade proportionally, would be
  exactly the unverified claim `CLAUDE.md`'s "no claim without a testbench"
  rules out. A narrower-scale-factor sweep, run against `layout/adc-top/`
  the same way item 5 was, is a defensible follow-up (see Consequences) —
  it is not this record's evidence to spend.
- **Treat item 3's structural-invariance finding as disqualifying (no
  measurement, therefore no evidence)** — not chosen. `sim/comparator-
  kickback/`'s deck carries no acquisition-leg device by construction (traced
  in the table above, not merely asserted from the deck's own header), so
  "no coupling exists in this topology" is itself the complete, correct
  answer to the question item 3 was scoped to ask. Demanding a numeric delta
  where the mechanism the deck models has no dependency on the varied
  parameter would manufacture a false precision, not more rigor.
- **Wait for a full-grid, extracted-netlist re-run of the candidate width
  before deciding** — not chosen. Item 5's DRC-clean, LVS-matched physical
  measurement already answers the question that re-run exists to
  cross-check (does the candidate fit the block): it does not, independent
  of how the dynamic rows would extract. Spending a second full extraction-
  and-27/9-point-campaign cycle on a candidate the Area evidence alone
  already disqualifies is not a good use of the verification budget.

## Consequences

- **The ENOB/SFDR regression from DR-0019's `C_u` resize is now a recorded,
  closed-investigation FAIL, not an open lever.** #211's isolated mechanism
  (acquisition-RC-limited distortion, `sim/dr0019-cu-sweep-findings.md`)
  still explains the regression; this record settles that the one measured
  fix for it is not adoptable, not that the mechanism is wrong.
- **No spec-table row changes.** `README.md#target-specification`'s ENOB,
  SFDR, Power, and Area rows are all unchanged by this record; the
  characterization-summary and README status prose are updated in the same
  change to cite the new governing ENOB/SFDR record ID and this decision,
  not to move any verdict.
- **A narrower acquisition-leg width, or an alternative acquisition-path
  redesign that does not cost decode-bank height, remains open and
  unmeasured.** This record closes the specific 2.068×-width candidate
  #211/#238 measured; it does not foreclose a differently-scoped follow-up
  (see the "smaller scale factor" alternative above) — that is new
  evidence-gathering, tracked as a fresh issue rather than reopening #238.
- **#238 is complete.** All five deferred measurements have governing
  records, and this record is the synthesis they existed to produce; #238
  is closed by this PR's description, with a comment left on it noting the
  final disposition if GitHub does not auto-close it from this record's own
  reference.
- **DR-0024's pending ratification is unaffected — and this record removes
  one reason to worry it might need revisiting.** Had the candidate been
  adopted, DR-0024's proposed `< 0.16 mm²` figure would already have been
  insufficient at ratification time. Declining the candidate leaves DR-0024
  exactly as sized against the geometry it was proposed against.

## Spec lines affected

- `README.md#target-specification` — none. The ENOB, SFDR, Power, and Area
  rows are unchanged; only their citations move to the new governing record
  ([`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](../../sim/adc-enob-fft/records/20260825-061750-d00911a.md))
  in the accompanying documentation update, not by this record.
- `design/adc-top/gen_adc_top.py` — none. `CDAC_SW_WN`/`CDAC_SW_WP` remain
  `10u`/`20u` — this is precisely the candidate change this record declines
  to make.
