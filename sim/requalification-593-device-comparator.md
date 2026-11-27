# Device and comparator re-qualification under open_pdks f6eeac7

Issue #593 covers 18 experiment directories in the #515 PDK re-qualification.
At `01cc53d1`, 15 have measurements under the pinned open_pdks revision
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. Two comparator offset runs
are pending. The retired comparator PEX experiment accounts for the
eighteenth directory.

## Measurements on the pinned PDK

| Experiment | Child issue | Recorded result | Measurement record |
|---|---|---|---|
| `device-cdac-cap` | #599 | PASS | [20261126-223814-c0e9a48](device-cdac-cap/records/20261126-223814-c0e9a48.md) |
| `device-comparator-flicker-noise` | #599 | PASS | [20261126-224110-6808a6a](device-comparator-flicker-noise/records/20261126-224110-6808a6a.md) |
| `device-comparator-gm-id` | #599 | PASS | [20261126-223400-5188a25](device-comparator-gm-id/records/20261126-223400-5188a25.md) |
| `device-mismatch-mc` | #599 | PASS | [20261126-224321-01ac126](device-mismatch-mc/records/20261126-224321-01ac126.md) |
| `device-switch-charge-injection` | #599 | PASS | [20261126-223612-b864f6e](device-switch-charge-injection/records/20261126-223612-b864f6e.md) |
| `device-switch-leakage` | #599 | PASS | [20261126-222336-51b6bb1](device-switch-leakage/records/20261126-222336-51b6bb1.md) |
| `device-switch-ron` | #599 | PASS (schematic) | [20261126-222612-2a6a335](device-switch-ron/records/20261126-222612-2a6a335.md) |
| `comparator-kickback` | #600 | PASS | [20261116-050139-42785df](comparator-kickback/records/20261116-050139-42785df.md) |
| `comparator-offset` | #600 | PASS | [20261020-212041-fe5ceca](comparator-offset/records/20261020-212041-fe5ceca.md) |
| `comparator-preamp-noise` | #609 | PASS | [20261108-031240-6ba19f6](comparator-preamp-noise/records/20261108-031240-6ba19f6.md) |
| `comparator-regeneration` | #600 | PASS (schematic) | [20261020-212335-05bb9f5](comparator-regeneration/records/20261020-212335-05bb9f5.md) |
| `cdac-bit-settling` | #601 | PASS | [20261123-071939-3703e3a](cdac-bit-settling/records/20261123-071939-3703e3a.md) |
| `top-plate-cpar` | #601 | PASS | [20261105-061018-e5489fc](top-plate-cpar/records/20261105-061018-e5489fc.md) |
| `smoke-sar-bias` | #601 | PASS | [20261105-050948-bca53f9](smoke-sar-bias/records/20261105-050948-bca53f9.md) |
| `adc-block-pex` | #601 | 468/468 delta checks passed | [20261123-074242-78a29859](adc-block-pex/records/20261123-074242-78a29859.md) |

The extracted `device-switch-ron` record from #940 also used `f6eeac7`.
It reports a 9.737% supply-axis spread for `ron_t_max` against the
manifest's 10% floor. Issue #1066 owns its clean-tree retake with installer
provenance. [Extracted switch record](device-switch-ron/records/20261123-072950-78a2985.md)

## Pending comparator offset measurements

| Experiment | Required fleet coverage | Previous result under `c6d73a3` |
|---|---|---|
| `comparator-offset-gof` | Three supplies at `tt`, 27 °C, with 300 draws each | Offset sigma 1.19920–1.19937 mV, ngspice 46. [GOF record](comparator-offset-gof/records/20260806-233111-56be937.md) |
| `comparator-offset-mc` | Five process corners × three temperatures × three supplies, with 150 draws per point | Offset sigma 1.27899–1.28089 mV, ngspice 47. This run governs schematic differential CMRR. [Monte Carlo record](comparator-offset-mc/records/20260816-050001-d002e66.md) |

Both manifests select batch deck transport. On November 27, both recorded
runs exited at the evidence-store preflight because the launcher lacked
`KLT_ARTIFACT_BROKER`. Fleet job IDs and old-to-new deltas are pending.
The reruns need a clean checkout on a launcher provisioned for the Spot
fleet and the artifact store.

## Exceptions

- **Comparator PEX.** Its only record documents a structural error before
  measurement (klayout-tools#1030). Commit `662f0a9f` retired the
  comparator-only runner. [Error record](comparator-pex/records/20260815-230715-56fbe50.md)
- **Extracted comparator regeneration.** Only the schematic variant is
  counted above. The extracted driver invokes local ngspice twice per
  point across a 45-point grid and writes working files. Re-qualification
  requires a fleet execution path and an evidence-record writer for this
  driver. [Extracted record](comparator-regeneration/records/20260814-215626-f613571.md)
  · [Driver](../layout/adc-top/parasitics/measure_extracted_regeneration.py)
