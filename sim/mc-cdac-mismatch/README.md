# mc-cdac-mismatch — CDAC unit-cap mismatch campaign

Behavioral Monte Carlo model of CDAC unit-capacitor mismatch
(`testbench/mc_cdac_mismatch.py`), its committed run populations
(`runs/<record-id>/`), and the `klt yield` evidence bundles derived from
them (`yield-evidence*/`). Results here are **append-only evidence** — see
[`sim/README.md`](../README.md) for the record format.

This README exists because the directory hosts **three** `yield-evidence*/`
bundles whose negative-control prose describes the same convention in three
different wordings, and two facts that prose cannot carry are load-bearing
for any reader comparing bundles side by side: what design state each
bundle certifies, and that all three 1.5 % negative controls are the *same*
run. Both facts are stated below. The wording difference itself is
deliberate and stays — see [Why the three wordings differ](#why-the-three-wordings-differ)
(decision recorded on #814).

## The three bundles at a glance

| bundle | certifies | design state | nominal `sigma_u` | neg-control `sigma_u` | run record |
|---|---|---|---|---|---|
| `yield-evidence/` meas. 0–3 (DNL/INL @ code 256, baseline + stretch) | code-256 DNL/INL rows (klayout-tools#818, phase 1c of epic #710) | DR-0019-resized | `0.5000 %` | `1.500000 %` | [`20260816-125421-737d16e`](records/20260816-125421-737d16e.md) |
| `yield-evidence/` meas. 4 (gain error) | gain-error row (`README.md#target-specification` line 50, #172) | pre-resize, as drawn | `0.7372097807744856 %` (verbatim, do not round) | `2.211629 %` | [`20260816-044942-56fbe50`](records/20260816-044942-56fbe50.md) |
| `yield-evidence-177/` (gain error, resized `C_u`) | the **resizing decision** #177 makes (DR-0019) — a proposal, not the built design | resized **proposal** | `0.500000 %` | `1.500000 %` | [`20260816-125421-737d16e`](records/20260816-125421-737d16e.md) |
| `yield-evidence-656/` (worst-over-all-codes DNL/INL) | INL/DNL row < 1 LSB baseline / < 0.5 LSB stretch (#656, split from #654; DR-0006) | **as-built** (post-DR-0019) | `0.500000 %` | `1.500000 %` | [`20261028-190000-5489f3a`](records/20261028-190000-5489f3a.md), reading [`20260816-125421-737d16e`](records/20260816-125421-737d16e.md) |

`yield-evidence/` spans two rows because it spans two runs and two design
states — itself part of what a side-by-side reader cannot see from the
prose alone.

## The shared negative-control run

All three bundles' 1.5 % negative controls derive from the **same** committed
run: [`runs/20260816-125421-737d16e/summary_n2000_3xsigma.json`](runs/20260816-125421-737d16e/summary_n2000_3xsigma.json)
— forced `sigma_u = 1.500000 %` (summary carries `sigma_u_pct: 1.5`),
`N = 2000`, `seed = 99109901`. That is: `yield-evidence/` measurements 0–3,
`yield-evidence-177/` measurement 0, and `yield-evidence-656/` measurements
0–3 all cite this one run at this one forced sigma. The three prose
wordings ("the chosen design's calibrated value", "the RESIZED design's
calibrated value", "the as-built value") describe the *same samples*; what
differs is which design's nominal each bundle triples, not which run each
bundle ran. `yield-evidence/` measurement 4 (gain error) is the one
exception: it keeps its own pre-resize negative control at
`sigma_u = 2.211629 %` (`3 × 0.7372097807744856 %`) from run
[`20260816-044942-56fbe50`](records/20260816-044942-56fbe50.md).

## Why the three wordings differ

Deliberately, and they stay different (decision on #814, 2026-11-15;
unification declined). Each wording names the design state that bundle
certifies, and the three states are genuinely distinct claims:

- `yield-evidence/` says "**the chosen design's** calibrated value" because
  its five measurements span two design states (rows 1–2 of the table
  above), so no single-state wording would be true of all five.
- `yield-evidence-177/` says "**the RESIZED design's** calibrated value"
  because it certifies the *resizing proposal* of
  [DR-0019](../../spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md)
  — its own `build_yield_evidence.py` docstring explicitly denies
  certifying the built design. Calling its control "the as-built value"
  would assert what that docstring denies.
- `yield-evidence-656/` says "**the as-built value**" because it certifies
  the built, post-resize design.

Two further mechanical differences are kept for the same reason:
`yield-evidence/` renders its nominal `sigma_u` as a literal string —
`0.5000 %` for measurements 0–3, the full `0.7372097807744856 %` for
measurement 4, quoted verbatim from its run records (a shared float
formatter would truncate it to `0.737210 %`) — and `yield-evidence-656/`
ends its sentence `.json.` where the others say `.json for full
provenance.` Beyond prose fidelity, the committed bytes are pinned:
`yield-evidence-177/mc-samples.json`'s sha256 is the live T1 item-6.analog
signoff pin (`signoff/freshness.json`, `signoff/gf180-sar-adc.manifest.json`,
and 124 historical reports), and `yield-evidence-656/`'s three artifacts'
hashes are recorded in the append-only record
[`20261028-190000-5489f3a`](records/20261028-190000-5489f3a.md), which
cannot be edited to follow a re-baseline. Re-baselining any of them to
uniform the prose is a provenance-visible change, not a cleanup.

## Not part of this family

[`sim/comparator-offset-mc/yield-evidence/`](../comparator-offset-mc/yield-evidence/)
shares the bundle *pattern* (an `mc-samples.json` /
`spec-limits.json` pair built by its own `build_yield_evidence.py`) but is
a different campaign — ADC_BLOCK offset, not CDAC mismatch — and emits no
`negative_control` block at all, so it has no row here.

## Provenance

Every number and path above was re-derived from the tree at commit
`34647c54` (2026-11-15), not copied from #814's curation snapshot:
bundle claims and design states from each bundle's
`build_yield_evidence.py` module docstring; nominal and forced `sigma_u`,
`N`, `seed`, and run citations from each bundle's `mc-samples.json`
`measurements[*].negative_control.description` and from the run summaries
`runs/20260816-125421-737d16e/summary_n2000_3xsigma.json`
(`sigma_u_pct: 1.5`, `seed: 99109901`) and
`runs/20260816-044942-56fbe50/summary_n2000_3xsigma.json`
(`sigma_u_pct: 2.211629342323457`, `seed: 99109901`); hash pinning from
`signoff/freshness.json` and
`records/20261028-190000-5489f3a.md` (lines 34–41).
