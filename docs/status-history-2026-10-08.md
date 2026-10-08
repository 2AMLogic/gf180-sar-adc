# Status history: the DR-0019-era README Status narrative

This file holds the introductory prose of the root `README.md` "Status"
section exactly as it stood when it was relocated on **2026-10-08** (issue
#415). It is a **snapshot of text relocated on that date, not a claim measured
on that date**: it was written around the DR-0019 CDAC unit-cap resize
(August 2026) and has not been kept current since. Many figures in it have been
superseded (for example the #381 re-extraction moved the governing ENOB/SFDR
figures to 8.855 bits / 60.41 dB). For the current state read the root
[`README.md`](../README.md) Status section, [`signoff/README.md`](../signoff/README.md)
and [`sim/characterization-summary.md`](../sim/characterization-summary.md).

The text between the two rule lines below is byte-for-byte the original span
(from the line after `## Status` up to the `| Area | State |` table header).
Its relative links were written for the repository root and do **not** resolve
from `docs/`; the reference map after it gives a working destination for each.

---

Pre-tapeout. The analog core is drawn end to end — sub-block schematics, a
transistor-level netlist, a DRC-clean and LVS-matched block layout, and a
PVT-cornered verification suite that has been re-run in full against
post-layout extracted parasitics — but it is not a converged design, and as of
the DR-0019 CDAC unit-cap resize it is **less** converged than it was:

- **The resize closed one row and opened two.** DR-0019 (#177) resized
  `C_u` from 17.24 fF to 35.6528 fF to close the `Gain error, mismatch` row's
  2.12σ-vs-3σ gap, and #196 built it. Re-running the transistor-level suite at
  the built design (#197 and its sub-issues) finds the **ENOB row newly FAILS
  at 2 of its 9 corners** (worst 8.5064 bits against a `> 9.0` target, was
  9.163 and all-PASS) and the **SFDR row's pre-existing miss widens from
  0.67 dB to 5.59 dB** (worst 56.41 dB against `≥ 62 dB`). Reported, not
  fixed, and no target was moved to absorb it — the mechanism is tracked in
  **#211**. Power grows 13.4 % and still passes with 2.4× stretch margin;
  bit settling, the top-plate `C_par` divider, the `Gain error, systematic`
  row, static INL/DNL (worst \|INL\| 0.1036 → 0.1100 LSB, worst \|DNL\|
  0.1036 → 0.0938 LSB) and the input drive contract (which *improves*, to
  +0.082…+0.370 LSB) are unchanged or better. **The schematic re-verification
  is now complete**, and the last two decks it reached add a third flagged
  result: the sampling switch's *own* SFDR contribution
  (`sim/track-switch-thd/`, a distortion term linear in the array
  capacitance) loses 4.96–5.77 dB at all 117 corners and falls below the
  ratified 62 dB at 11 of them, where none did before — the first measured
  mechanism that moves the same way, and by the same size, as the end-to-end
  SFDR regression #211 owns.
- **The post-layout (extracted) side has now been re-taken too, and it does
  not rescue those two rows** (**#218**). The #202 layout was re-extracted at
  the resized unit cap (1024 MiM caps at `c_f = 35.6528 fF`, against 17.245 fF
  before) and all five extracted campaigns re-run against it. Because the
  extracted result is the one this repo reports as *governing* where both
  exist, that settles a row that had been left with **no** valid governing
  result: **SFDR measures 60.40 dB worst post-layout — a FAIL by 1.60 dB at 4
  of 9 corners** (its pre-resize extracted PASS of 64.38 dB described an array
  that is no longer drawn), and **ENOB 8.857 bits — a FAIL at 2 of 9**. Power
  passes at 246.5 µW (+11.6 %), `Gain error, systematic` improves to ~1047×
  inside its bound, and the Input-structure `R_on` re-take is an exact null.
  One row lands in between and is flagged rather than absorbed: post-layout
  static INL/DNL still passes the ratified `< 1 LSB` row but now misses the
  `< 0.5 LSB` stretch (0.528 / 0.728 LSB). Per-campaign before/after:
  [`sim/extracted-delta-summary.md`](sim/extracted-delta-summary.md) §4.12.
- **The candidate fix for the ENOB/SFDR regression is measured and NOT
  adopted (#238/#249).** #211 isolated the mechanism (an acquisition-RC-
  limited distortion that scales with the array capacitance,
  [`sim/dr0019-cu-sweep-findings.md`](sim/dr0019-cu-sweep-findings.md)) and
  found an orthogonal control — widening the CDAC cell's acquisition-leg
  T-gate 2.068× — that recovers 89–101 % of the loss in a schematic-level,
  125 °C-only probe, but deferred five measurements before that recovery
  could be read as achievable margin. All five have landed (#238): charge
  injection, top-plate `C_par`, and clock-driver power all cost little, but
  the fifth — a genuine `klt`-verified re-layout of the candidate width — grows
  `adc_block` area **+17.00 %** (150,536.239 → 176,126.8006 µm²), pushing it
  **+76.1 %** over the still-ratified `< 0.1 mm²` Area target and **+10.1 %**
  over even the still-unratified `< 0.16 mm²` relaxation proposed below to
  reconcile the *current* geometry. Adopting the candidate would not close
  the ENOB/SFDR FAILs without opening a worse one on Area, which `CLAUDE.md`'s
  "do not relax the ratified spec to make results pass" rules out — so the
  candidate is **not adopted**, `CDAC_SW_WN`/`CDAC_SW_WP` remain `10u`/`20u`,
  and the ENOB/SFDR rows stand as a recorded, unresolved regression:
  [DR-0025](spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md).
  The extracted ENOB/SFDR campaign was re-taken on a clean tree against the
  unchanged, ratified design and reproduces the same governing FAIL figures
  exactly (8.857 bits / 60.40 dB worst-corner):
  [`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](sim/adc-enob-fft/records/20260825-061750-d00911a.md),
  superseding the dirty-tree `20260817-215657-076d545`.
- A comparator-inclusive extraction's statistical offset campaign has not been
  run yet (the functional defect that used to block `ADC_BLOCK` outright is
  fixed, #118), and there has been no silicon:

---

## Reference map (links relative to `docs/`)

Each destination below appears as a Markdown link in the relocated text above.

- `sim/extracted-delta-summary.md` -> [`../sim/extracted-delta-summary.md`](../sim/extracted-delta-summary.md)
- `sim/dr0019-cu-sweep-findings.md` -> [`../sim/dr0019-cu-sweep-findings.md`](../sim/dr0019-cu-sweep-findings.md)
- `spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md` -> [`../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md`](../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md)
- `sim/adc-enob-fft/records/20260825-061750-d00911a.md` -> [`../sim/adc-enob-fft/records/20260825-061750-d00911a.md`](../sim/adc-enob-fft/records/20260825-061750-d00911a.md)
