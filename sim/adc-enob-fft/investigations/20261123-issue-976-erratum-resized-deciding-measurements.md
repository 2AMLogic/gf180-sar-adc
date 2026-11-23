# Issue #976 -- Erratum to the #943 record: the N = 64 `ss_125c` baseline verdict in Section 4 is a fail, not a pass (2026-11-23)

- **Date**: 2026-11-23 (UTC).
- **Erratum to**: `20261123-issue-943-resized-deciding-measurements.md` (merged by #970), Section 4, "Consequences for orderings" table, row "`ss_125c` vs the 62 dB row", **N = 64, bin 31 (#430) column cell** -- [permalink to the incorrect cell at `be4e673`](https://github.com/2AMLogic/gf180-sar-adc/blob/be4e67383a0e0b63ebbc363a7d15a8742c42ebdf/sim/adc-enob-fft/investigations/20261123-issue-943-resized-deciding-measurements.md#L70).
- **Policy**: `sim/` is append-only evidence ([evidence policy](../../../README.md)); the correction is recorded here rather than by editing the record in place.

## What is wrong

The cell reads `61.09 (pass)`. The row's threshold is **SFDR >= 62 dB**, and 61.09 dB falls **0.91 dB below** it. The verdict in that cell is wrong: the N = 64 baseline at `ss_125c_2.97v` **fails** the 62 dB row.

## Corrected row (capture order)

| ordering question | N = 64, bin 31 (#430) | N = 256, bin 125 (#935 + repeat) | N = 256, bin 115 (that record) |
|---|---|---|---|
| `ss_125c` vs the 62 dB row | 61.09 (**fail**) | 58.59 (**fail**) | 63.24 (pass) |

All three verdicts follow from the committed measurements the record already cites, with SFDR >= 62 dB applied to each reading; no measurement changed, only the one verdict cell.

## What this does and does not change

- The record's headline claim about this row -- the 62 dB verdict at `ss_125c_2.97v` **flips with tone choice alone** (Verdict item 3: 58.59 dB FAIL at bin 125 vs 63.24 dB PASS at bin 115, both N = 256) -- stands unchanged; it never relied on the N = 64 cell's verdict.
- The correction sharpens Section 4's reading rather than reversing it: with the baseline corrected, **two of the three captures** at `ss_125c_2.97v` fall below the row and only the bin-115 capture clears it.
- Sections 5-8 (re-sizing, first candidate, 27-point re-take decision) are unaffected: none of those decisions consumed the N = 64 cell's verdict.

## Provenance

| Item | Value |
|---|---|
| Corrects | `sim/adc-enob-fft/investigations/20261123-issue-943-resized-deciding-measurements.md` Sec 4, line 70 at commit `be4e67383a0e0b63ebbc363a7d15a8742c42ebdf` (PR #970) |
| Values verified against | `sim/adc-enob-fft/investigations/20261123-issue-943-data/points.md` at `354ab2b216748625379fefcef8f15256fbc49206`: the two `ss_125c_2.97v` rows (`c1` 256/125, `t115` 256/115) -- baseline read from the `#430 N=64` column (61.09), the two 256-sample readings from the `SFDR dB` column (58.59, 63.24) |
| Threshold | SFDR >= 62 dB, the row Section 4 cites |
| New simulations | none; the existing measurements are sufficient (this erratum, per issue #976) |
