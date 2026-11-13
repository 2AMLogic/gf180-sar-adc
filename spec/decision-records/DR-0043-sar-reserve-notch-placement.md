# DR-0043: SAR reserve placed in a top-right notch of the analog core, L-shaped analog guard ring

- **Status**: proposed
- **Date**: 2026-11-01
- **Decided by**: builder agent, issue #667 (parent #644)
- **Supersedes**: none. Implements the route DR-0042 identified and left undrawn;
  DR-0042's decision text is untouched.
- **Superseded by**: (none)
- **Related**: #644, #667, #692, DR-0008, DR-0010, DR-0034, DR-0042,
  `layout/adc-top/economy/records/20261101-063000-f44f1140.md`

## Context

DR-0042 showed the ringed SAR reserve does not fit the analog core's
right-column hole without overhanging the core, and that the best candidate is
a notch in the core's top-right corner with an L-shaped analog guard ring,
which the generator could not draw. This change adds that ring
(`geo.draw_notched_guard_ring`) and places the reserve in the notch.

## Decision

`gen_adc_top.py` computes the notch from the drawn geometry (everything right
of the CDAC arrays, plus `GUARD_CLEARANCE`), draws the analog ring around the
L-shaped core, and puts the ringed reserve in the notch flush with the ring's
top edge, overhanging the old right edge. Reserve footprint (width rule,
`SAR_RESERVED_H`) is unchanged, so the placed-and-routed `sar_ctrl`
(199.21 x 40.0 um) fits as before and no new P&R is implied.

## Isolation re-argument (DR-0008 / DR-0010: not relaxed)

* `ANALOG_DIGITAL_GAP` is still 20 um, measured the way the old band was: from
  the analog ring's outer edge to the digital box, on both facing sides (the
  notch wall and the notch floor). Measured `Comp`-to-`Comp` ring separation
  is 18.6 um (`separation_check` finds none below 18.5 um, one at 19.0 um),
  the same as the old band (20 um minus the 1.4 um ring width).
* The ring stays on the boundary: the digital ring is a closed, `Pplus`-marked
  ring; the analog ring now follows the notch walls so no analog device has a
  digital ring edge closer than the ring that guards it.
* Nearest analog device (instance bbox) to the reserve ring's `Comp`: between
  27.5 and 28.0 um (500 nm bisection).
* Both rings stay strapped to the block's one `vss` island; `klt erc` reports
  zero `erc.unconnected_net` and zero `erc.supply_short` (record
  `layout/erc/records/20261101-061745-f44f1140.md`).

## Result (measured, `klt economy`)

`ADC_BLOCK` bbox 151,827.3 um2 -> 128,764.9 um2 (-23,062.5 um2, -15.2 %);
670.93 x 191.92 um. DR-0042 inferred 127,759 um2; the 1.0 k difference is the
ring/implant margins the inference ignored. The Area row stays a disclosed FAIL
(needs < 100,000 um2).

## Alternatives considered

As DR-0042: reserve inside the hole (does not fit), shrinking the gap
(relaxes DR-0008), bottom-right notch (136.7k), beside the core (156.9k).

## Consequences

`adc_block.gds`/`adc_top.gds`, their extracted `.spice`, `area.json`, the
DRC, LVS, ERC and parasitic-extraction records are regenerated. **Not
regenerated here:** the `klt power` droop run (`layout/power/`; the `vss`
network gained 20 Metal1 edges and the `metal2-as-poly2` negative control no
longer fails the budget, so its expectations need a reviewed re-baseline) and
the ngspice post-layout PEX simulations under `sim/adc-block-pex/` (batch
fleet). `signoff/run_signoff.py --check` is therefore red on its GDS-freshness
pins until those are re-run; this is tracked in the follow-up issue linked from
the PR.

### Update (#692): the deferred re-baseline has landed

The three items deferred above were re-run against the notched stream
(`layout/adc-top/adc_block.gds` sha256 `fc10bb28…`) before PR #693 merged, so
the paragraph above describes the state *at the time this record was written*,
not the state on `main`. The paragraph is left as written; this note records
what closed it.

* **`klt power` droop/EM** — record
  [`layout/power/records/20261106-202719-e38687e0.md`][pwr], every case re-run
  on the new GDS (`klayout-tools==0.6.0`, klayout 0.30.10). `vss` grew 610/613
  -> 630/633 nodes/edges; `COMPARATOR`'s worst combined droop rose 1.703 ->
  3.048 mV and `ADC_DECODE_BANK_P`'s is 12.653 mV (was 13.227), worst
  pessimistic 16.697 mV against the 33 mV [DR-0034][dr0034] budget. No budget
  was relaxed and no verdict moved except the control below.
* **The negative control was replaced, not re-baselined to pass.**
  `control.metal2-as-poly2` returned 33.177 mV (FAIL) before the notch and
  32.60 mV (PASS) after it, so it no longer discriminated. Its expectation was
  **not** flipped to pass; it was replaced by `control.metal2-at-4x-poly2`
  (Metal2 at 4x Poly2's sheet resistance, 29.2 ohm/sq), which fails the budget
  at 45.901 mV. Full reasoning: [`layout/power/README.md`][pwrreadme] section
  "Re-baseline at the SAR-reserve notch".
* **Block PEX** — record
  [`sim/adc-block-pex/records/20261106-204055-26617d82.md`][pex]: the full
  117-point PVT grid on the batch fleet, 468/468 delta rows pass, klt 0.9.0.
* **Signoff re-attestation** — record
  [`signoff/records/20261106-204639-e72cadbb.md`][so] re-pinned items 2, 3, 4,
  7 and 11 to the new bytes. The freshness check itself was not loosened.
  `python3 -I signoff/run_signoff.py --check` is green on `main`.

[pwr]: ../../layout/power/records/20261106-202719-e38687e0.md
[pwrreadme]: ../../layout/power/README.md
[pex]: ../../sim/adc-block-pex/records/20261106-204055-26617d82.md
[so]: ../../signoff/records/20261106-204639-e72cadbb.md
[dr0034]: DR-0034-supply-droop-budget.md

## Spec lines affected

none — no spec row changes.
