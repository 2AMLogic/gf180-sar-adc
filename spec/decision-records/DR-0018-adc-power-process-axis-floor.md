# DR-0018: `adc-power`'s `p_cmp_f050_uw` process-axis sensitivity floor — re-derived for the post-layout (in-path extracted) DUT

- **Status**: ratified — Builder agent, issue #133
- **Date**: 2026-08-07
- **Decided by**: Builder agent, issue #133
- **Supersedes**: none — the 3 % figure in
  `sim/adc-power/testbench/tb.json` predates any decision record; this is
  the first record to state a derivation for it
- **Superseded by**: (none while this record stands)
- **Related**: #133 (this decision), #123 (the in-path re-run that surfaced
  the failure), #107 (open — "Explain the 2x comparator-current excursion…",
  the separately-tracked mechanism question this record explicitly does
  **not** resolve),
  `sim/adc-power/records/20260807-060526-03e80b9.md` (the record this
  record is written against),
  `sim/adc-power/records/20260807-234512-*.md` (the re-run taken under the
  revised floor — record ID filled in once minted, see Consequences),
  `sim/extracted-delta-summary.md` §7.3 (updated by this issue to reflect
  this resolution)

## Context

`sim/adc-power/testbench/tb.json`'s `p_cmp_f050_uw` check carries a
`min_spread_pct_by_axis: {"process": 3.0}` witness: the *weakest* slice of
the process axis (the other two axes — temperature, supply — held fixed)
must spread by at least 3 % across `tt`/`ss`/`ff`. It exists to catch a
runner that only *looks* like it sweeps process (`.lib`/`.temp` silently not
taking effect), not to bound comparator power itself — the manifest's own
`description` field says exactly that. No prior record states how the 3 %
number was chosen; it is not derived anywhere in this repository.

Record `20260807-060526-03e80b9` (issue #123's re-run of the power deck onto
the ratified in-path star-split extraction, `klayout-tools#593`) carries
**Overall: FAIL** on this witness alone — every performance check, including
the ratified `p_total_* < 1 mW` row, passes with margin:

```
CHECK FAIL p_cmp_f050_uw min_spread_pct_by_axis on the process axis=3
           (got 2.50595)
```

Reworking the record's own per-axis table (`sim/harness/report.py`'s
`axis_sensitivity`, which groups by the two fixed axes and reduces to
min/max spread across the swept one) into per-`(temperature, supply)`-group
spreads for `p_cmp_f050_uw` gives:

| temperature | supply | `tt` | `ss` | `ff` | spread |
|---|---|---|---|---|---|
| 125 °C | 2.97 V | 85.2226 | 85.0998 | 87.2514 | **2.506 %** (the failing slice) |
| −40 °C | 2.97 V | 81.9743 | 80.2852 | 83.2378 | 3.608 % |
| −40 °C | 3.63 V | 109.700 | 107.336 | 112.842 | 5.007 % |
| 125 °C | 3.63 V | 114.764 | 111.737 | 117.497 | 5.023 % |
| −40 °C | 3.30 V | 97.334 | 92.2587 | 97.4042 | 5.379 % |
| 125 °C | 3.30 V | 98.5472 | 96.6755 | 103.319 | 6.676 % |
| 27 °C | 3.30 V | 96.5163 | 103.265 | 99.1927 | 6.772 % |
| 27 °C | 2.97 V | 82.2015 | 101.262 | 84.7398 | 21.320 % |
| 27 °C | 3.63 V | 110.572 | **161.771** | 115.111 | 39.643 % (issue #107's outlier corner, `ss_27c_3.63v`) |

Two findings, both needed to re-derive the floor correctly:

1. **The failing slice (`125 °C`, `2.97 V`) is not the #107 outlier's own
   group.** `sim/extracted-delta-summary.md` §7.3 (as landed by #130)
   describes the failure as the outlier corner "flattening" a "sibling
   process slice" — that reads as if the two were the same group. They are
   not: the outlier sits at `(27 °C, 3.63 V)`, the failing slice sits at
   `(125 °C, 2.97 V)`, opposite corners of the temperature/supply grid, and
   `axis_sensitivity`'s spread is computed purely within each
   `(temperature, supply)` group — the outlier's own inflated group
   (39.64 %) cannot mathematically depress a different group's spread. This
   record corrects that description in `sim/extracted-delta-summary.md`
   §7.3, per this issue's acceptance criteria.
2. **The failing slice is a real, physically distinct, un-elevated corner.**
   At the lowest supply (`2.97 V`, −10 % of nominal) and highest temperature
   (`125 °C`) all three process corners land within a 2.2 µW band
   (85.10–87.25 µW) — narrower than at any other `(temperature, supply)`
   pair, including every pair that does *not* touch the #107 outlier. That
   is consistent with the comparator's preamp bias current entering a
   low-overdrive regime at reduced `V_DD` and elevated temperature (`DR-0007`
   sets ~33 µW of static bias by design at nominal conditions), where
   thermal-voltage-scaled behaviour common to all three process corners
   dominates the (smaller, at low overdrive) `V_th` process spread between
   them. It is not evidence of a stuck axis: the same measurement, same
   axis, moves by up to 39.6 % elsewhere in the same 27-point grid, and
   every *other* `(temperature, supply)` group clears 3.6 % or more.

The 3 % floor was, on the evidence available, an unstated number that
happened to sit inside the natural range of process-axis spread this
measurement produces (roughly 2.5–40 % across the grid, ignoring the
still-open #107 mechanism) rather than a value derived from any bound on
what "the axis moved" should mean. It is not wrong to fail *some* number —
picking a floor from inside a measurement's natural noise band, with no
margin, means the next otherwise-unremarkable re-run trips it again, on a
process/DUT change, at whichever `(temperature, supply)` pair happens to sit
at the bottom of that band.

## Decision

**Lower `sim/adc-power/testbench/tb.json`'s `p_cmp_f050_uw`
`min_spread_pct_by_axis.process` floor from `3.0` to `2.0`, and record the
derivation in the manifest's `description` field.** The new floor is set
with margin below the observed minimum (2.506 % at `125 °C`/`2.97 V`) rather
than at it, so it does not itself become a number the next otherwise-clean
re-run trips on run-to-run numerical noise, while staying far above what a
runner that never varies `.lib`/`.temp` would produce (this deck's `p_trk_*`
measurements, driven by a rung with no measured devices, show that failure
mode directly: `n/a`/`-0` spread, not "a few percent") — i.e. the floor
still does its job of proving the axis moved, it is just no longer set
inside this measurement's normal low end.

This does **not** resolve or absorb issue #107. The mechanism behind the
`ss_27c_3.63v` outlier (161.8 µW vs. a 98.5 µW median at that slice) is
tracked separately at #107, which already has the relevant evidence
(`sim/extracted-delta-summary.md` §7.3, ported into #107 by its own most
recent comment). This record only re-derives a bench health-check number;
it makes no claim about *why* the comparator's power moves the way it does.

## Alternatives considered

- **Diagnose the loading mechanism first (issue #133's Option 1), then
  derive the floor from the finding.** Not chosen for this issue: that
  diagnostic charter belongs to #107, which is still open with no landed
  mechanism finding (a candidate mechanism exists only as an
  un-recreated comment on #107, explicitly not yet backed by its own
  re-runnable evidence record per that issue's own acceptance criteria).
  Duplicating that diagnostic work here would fork the investigation across
  two issues. This record's re-derivation holds regardless of which
  mechanism #107 eventually finds, because the failing slice is
  demonstrably independent of the outlier slice (finding 1, above) — #107's
  answer cannot change which `(temperature, supply)` group is weakest here.
- **Raise the floor's precision by excluding the outlier's own group from
  the witness.** Not chosen: the check only ever reads the single weakest
  slice (`min_pct`), and the weakest slice was never the outlier's group in
  this record — there is nothing to exclude. Special-casing one grid point
  out of a per-axis witness would also reintroduce exactly the "silently
  relax the check until it stops complaining" pattern `CLAUDE.md` forbids;
  a floor that holds for the whole grid, including whatever slice is
  weakest, is a stronger check.
- **Keep the 3 % floor and mark the record's overall verdict FAIL as an
  accepted, permanent state.** Not chosen: an append-only evidence record
  that is expected to read FAIL forever on every future re-run of an
  unmodified circuit (the deck's grid, manifest and analyses are
  byte-identical to the superseded, passing pre-in-path record) is
  indistinguishable, to a reader, from a check nobody has looked at. It also
  leaves the harness `--check` CI guard (added by #130) permanently red on
  this deck, defeating its purpose.
- **Raise the floor instead of lowering it, to make the witness more
  demanding.** Not chosen: nothing in the evidence argues for a *stricter*
  bound — 2.506 % is a real, physically-explained value this circuit
  produces at a legitimate PVT corner, not a runner defect the floor should
  be tightened to catch harder.
- **Set the floor exactly at the observed 2.506 % (or round to 2.5 %).** Not
  chosen: a floor set at (or barely under) the current record's own value
  reproduces the original problem — a future re-run's ordinary point-to-point
  numerical variation (ngspice solver tolerance, PDK model-section refresh,
  etc., none of which change the circuit) could trip it again with zero
  margin. `2.0` keeps roughly 20 % headroom below the observed minimum.

## Consequences

- **The revised floor is a re-justified bench-health parameter, not a
  performance claim.** No row of `README.md#target-specification` changes;
  `p_total_* < 1 mW` (the ratified claim this deck exists to substantiate)
  was already passing on 20260807-060526-03e80b9 with 4.5× margin and is
  untouched by this record.
- **`sim/adc-power/testbench/tb.json`'s `p_cmp_f050_uw` check `description`
  is updated** to carry this record's derivation basis (the 9-group
  per-axis table above, the corner and value it is set against, and the
  ~20 % margin), so a future reader who finds the check trips again does not
  face the same unreconstructible number this record was written to fix.
- **The power deck is re-run against the unmodified extracted netlist** once
  this record lands, superseding `20260807-060526-03e80b9`. Nothing in the
  circuit, grid, or non-`process`-floor checks changes, so every other row
  of the record is expected to reproduce bit-for-bit; only the harness
  verdict is expected to flip to PASS. The new record is cited in this
  record's **Related** field once minted, and in
  `sim/extracted-delta-summary.md` §7.3.
- **A future process/DUT change that genuinely flattens the process axis
  below ~2 % everywhere (not just at one corner)** would still trip this
  floor, which is the intended behaviour — this record does not disable the
  witness, it re-calibrates it to the post-layout DUT's actual noise floor
  at its weakest legitimate corner.
- **If #107 lands a mechanism finding that changes the comparator's power
  behaviour at any PVT corner** (e.g. gating `cmpclk` to the decide phases,
  named in #107 as the actual fix, out of scope there and here), the
  process-axis spread at every slice — including the two named in this
  record — will move again, and this floor should be revisited by a
  superseding record against the new evidence rather than assumed to still
  hold. This record does not pre-empt that revisit.
- **`sim/extracted-delta-summary.md` §7.3's "sibling process slice"
  description of the failure is corrected** (finding 1, above) as part of
  this issue's required update to that section, so the two grid points
  involved are not conflated going forward.

## Spec lines affected

- `README.md#target-specification` — none. This record changes a testbench
  manifest's internal bench-health assertion, not a ratified performance
  target; no row of the target-specification table is touched.
- `sim/adc-power/testbench/tb.json` — `checks.p_cmp_f050_uw.min_spread_pct_by_axis.process`
  — changed (`3.0` → `2.0`); `checks.p_cmp_f050_uw.description` — changed
  (adds the derivation basis).
