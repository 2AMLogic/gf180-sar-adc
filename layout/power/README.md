# `layout/power/` — IR drop and electromigration (`klt power`)

**Is the supply adequate for what it powers?** `layout/erc/` answered the
structural half of that question (T1 item 11: `vdd` and `vss` each resolve
to exactly one electrical island) and stopped there, deliberately — IR drop
and electromigration are `klt power`'s question, not `klt erc`'s. This
directory is the analysis half. Issue #346.

The premise it prices is the finding `layout/erc/` surfaced on the way past:
**neither rail has any geometry above Metal1.** Block-level continuity runs
through Metal1 trunks stitched by **Poly2 risers** — the Metal1-trunk /
Poly2-riser channel router in `layout/adc-top/lib/geometry.py`. Metal2–Metal5
are in heavy use by the CDAC arrays and carry **zero** supply area.

```
layout/power/
  README.md                    this file
  adc_block.power-spec.json    geometry + PDK numbers only (runnable bare,
                               extraction-only: no pads, no current model)
  cases.json                   the ASSUMPTIONS, named and sourced — where the
                               supply is landed, which resistance corner, what
                               each sub-block draws — plus what is asserted
  toolchain.json               pinned klt build, asserted before anything runs
  run_power.py                 composes, runs, asserts, mints a record
  reports/<record-id>/         klt power output verbatim + the composed spec
                               each case was actually run with, append-only
  records/<record-id>.md       append-only summary record
```

## Install and run

`klt power` here needs a **newer `klt` than either `layout/toolchain.json`
or `layout/erc/toolchain.json` pins**, and not for convenience: two defects
fixed on 2026-09-22 would each have produced a *confidently wrong* number on
this block rather than an error. `run_power.py` refuses to run under any
other build. See `toolchain.json`'s `_comment`.

```bash
pip install 'klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@c622e8addb362491664d44ba4d717f354ca88bbd'
pip install 'klayout==0.30.10'

python3 layout/power/run_power.py            # run, assert, mint a record
python3 layout/power/run_power.py --check    # run, assert, write nothing
python3 layout/power/run_power.py --verify   # re-derive the committed reports, no klt
```

Headless: no KLayout GUI, no gf180mcu PDK install. `--verify` is stdlib-only
and is what CI runs: it **re-composes** every case's spec from
`adc_block.power-spec.json` + `cases.json` and compares it to the composed
spec committed beside that case's report, then re-reads the report and
re-asserts every expectation — network shape, droop at every site, the EM
roll-up, the Poly2 riser current density, the budget verdict — plus the
sha256 of the committed GDS. Edit the geometry, a sheet resistance, a
resistance corner or the measured current model, and that lane goes red
instead of leaving a droop verdict on file that describes none of them.

## The three inputs, and where each one comes from

A droop number is a joint function of geometry, PDK constants, and
assumptions. They are kept in separate files on purpose.

| Input | Lives in | Source |
|---|---|---|
| Layer numbers, device carve-outs | `adc_block.power-spec.json` | identical to `layout/erc/adc_block.supply-spec.json`'s, derived there from the PDK's own `gf180mcu.lyp` |
| Sheet resistance, via resistance | `adc_block.power-spec.json` (nominal) + `cases.json` `resistance_corners` (all three) | `gf180mcuD.tech` § *Layer resistance*, its own three `variants` blocks, citing foundry doc `180MCU_YI-141-EP059-01_10.pdf`; metals cross-checked against `gf180mcu_fd_sc_mcu9t5v0__{nom,max,min}.tlef`'s `RESISTANCE RPERSQ` |
| EM current-density limits | `adc_block.power-spec.json` | `gf180mcu_fd_sc_mcu9t5v0__nom.tlef` `DCCURRENTDENSITY AVERAGE` (`UNITS CURRENT MILLIAMPS 1`) |
| Where the supply is landed | `cases.json` `sites` + each case's `pad_site` | the eight `Metal1_Label` 34/10 texts in `adc_block.gds` itself — this block's entire declared supply interface |
| What each sub-block draws | `cases.json` `current_models` | measured: `sim/adc-rail-current/`, 27-point PVT grid |
| The budget it is graded against | `cases.json` `budget` | [DR-0034][dr0034] — **proposed**, not ratified |

### Poly2 is ~80× Metal1, not ~1000×

Issue #346's body states that Poly2's sheet resistance is *"roughly three
orders of magnitude above Metal1's"*. It is not, and the number matters
enough to correct in the flow that measures it:

| | Poly2 | Metal1 | ratio |
|---|---:|---:|---:|
| nominal | 7.3 Ω/sq | 0.090 Ω/sq | **81×** |
| pessimistic | 15.0 Ω/sq | 0.104 Ω/sq | **144×** |

The likely origin of the ~1000× claim is the techfile's separate
poly-**resistor** flavours (`rpp` 350 Ω/sq, `rnp` 310 Ω/sq — the ones
`layout/adc-top/lib/geometry.py` quotes, because they are what the
comparator's load resistors are made of). Routing poly is
`resist (allpolynonres)`. The two differ by ~48×, and conflating them would
have overstated every riser in this flow by that factor.

## What the committed run says

Against `layout/adc-top/adc_block.gds` (top cell `ADC_BLOCK`, sha256
`ae4e8964…` — the same bytes `layout/erc/cases.json` and
`signoff/gf180-sar-adc.manifest.json` pin), at the **worst-corner average
supply current** the block was measured to draw (40.12 µA total,
`ff_125c_3.63v`), graded against [DR-0034][dr0034]'s 33 mV combined budget.
Record: `records/20260923-070149-e84ad26.md`, the issue #356 re-run against
the tapped geometry; the "was" column is the pre-tap figure the first record
(`20260923-010407-d84c7b4`) reported, kept beside it because the delta is
the point:

| Supply landed at | R corner | Worst site | `vdd` + `vss` | was | Budget |
|---|---|---|---:|---:|---|
| `COMPARATOR` | nominal | `ADC_DECODE_BANK_P` | **5.722 mV** | 5.616 | PASS (5.8× margin) |
| `ADC_DECODE_BANK_N` | nominal | `ADC_DECODE_BANK_P` | 14.907 mV | 14.792 | PASS |
| `ADC_TOP_SW` | nominal | `ADC_DECODE_BANK_P` | 21.390 mV | 21.212 | PASS |
| `ADC_DECODE_BANK_P` | nominal | `COMPARATOR` | **33.552 mV** | 33.029 | **FAIL** (by 0.55 mV) |
| `COMPARATOR` | pessimistic | `ADC_DECODE_BANK_P` | 10.877 mV | 10.660 | PASS (3.0× margin) |
| `ADC_DECODE_BANK_P` | pessimistic | `COMPARATOR` | **58.552 mV** | 57.485 | **FAIL** (1.77×) |
| `COMPARATOR` | optimistic | `ADC_DECODE_BANK_P` | 1.248 mV | 1.233 | PASS |

**The verdict is: adequate as drawn, conditional on where the parent lands
the supply.** This block has no supply pad — it has four labelled sites, and
which one a parent connects changes the answer by a factor of six. Landed at
the `COMPARATOR` label the rail meets the budget with 5.8× margin nominal and
still 3.0× at the PDK's high-resistance corner. Landed at the
`ADC_DECODE_BANK_P` label it misses the budget outright, nominally by half a
millivolt and at the pessimistic corner by 1.77×.

**What issue #356 did to these numbers, and what it did not.** Drawing 25
n-well taps and strapping both substrate-tie rings into `vss`
([DR-0035][dr0035]) grew both solved networks — `vdd` 376 → 476 nodes,
`vss` 494 → 610, with `vss`'s Metal1 edge count nearly doubling (124 → 239)
as the two ring annuli and their strap joined the island. Every droop figure
got **~1.6 % worse**, in the direction physics predicts: the taps add Poly2
riser length to `vdd`, and the rings add resistance — not current — to
`vss`. **No verdict flipped**: every case's `budget_status` and `worst_site`
is unchanged, which is why DR-0034 is re-measured here rather than reopened.
The taps were deliberately routed on Poly2 rather than Metal2 precisely to
keep this flow's own premise — zero supply geometry above Metal1 — true of
the tapped layout.

That is a real, narrow result rather than either of the two comfortable
answers. It is **not** the "fails by orders of magnitude" a poly-stitched
rail invites you to assume, and it is **not** a clean pass either.

### Where the droop actually is

The `control.poly-as-metal1` counterfactual re-solves the `COMPARATOR`
landing with Poly2 given Metal1's sheet resistance. Worst combined droop
falls from **5.722 mV to 1.681 mV** — so **~71 % of the block-level droop is
the Poly2 stitching**, and issue #346's premise is correct in direction even
though its magnitude claim was not. The remaining 30 % is Metal1 trunk and
Contact resistance.

One line does not move at all between the two: the `COMPARATOR` site's own
`vss` bounce, 1.4454 mV in both. That is the comparator's *local* access
resistance — its own 30.7 µA through its own contacts and short Metal1 runs
— not the block-level rail. (At the optimistic corner, where contacts are
0 Ω, it halves to 0.742 mV, which says roughly half of it is Contact.)

### Electromigration: `pass_partial`, and why it can never be `pass`

| | |
|---|---|
| `em_verdict.status` | `pass_partial` at every average-current case |
| failing edges | **0** |
| checked edges | 353 |
| unchecked edges | **737** |

Every unchecked edge is on **Poly2 or Contact**, because gf180mcuD publishes
no current-density limit for either: `Poly2` is `TYPE MASTERSLICE` and `CON`
is a bare `TYPE CUT` in the standard-cell tech LEF, with no
`DCCURRENTDENSITY` line, and nothing else in the install has one. `klt power`
counts them unchecked rather than guessing — correctly — so the roles this
block's rail actually runs through are precisely the ones with no limit to
check against. This verdict cannot become `pass` without a published poly
limit, and no amount of re-running will change that.

What *can* be said is the measured density. `run_power.py` derives it from
each segment's own reported resistance and endpoint nodes (see "What
`klt power` does not report" below):

| Case | Worst Poly2 riser | Width | Density |
|---|---:|---:|---:|
| `COMPARATOR` landing, nominal | 4.53 µA | 0.40 µm | **1.13 × 10⁻⁵ A/µm** |
| `ADC_DECODE_BANK_P` landing, nominal | 17.32 µA | 0.40 µm | **4.33 × 10⁻⁵ A/µm** |
| `ADC_TOP_SW` landing, nominal | 39.79 µA | 0.40 µm | **9.95 × 10⁻⁵ A/µm** |

Both edge counts above moved at issue #356 (213 → 353 checked, 659 → 737
unchecked) because the 25 well-tap risers and the two strapped ring annuli
are new edges on the two rails. The *verdict* did not, and cannot: every one
of the new unchecked edges is Poly2 or Contact, the same two roles with no
published limit. The worst Poly2 density is essentially unchanged — the taps
add riser length, not riser current.

For scale, and **not** as a verdict: Metal1's own published DC limit is
6.7 × 10⁻⁴ A/µm, so the worst Poly2 riser carries about a seventh of what
the same width of Metal1 would be allowed. Polysilicon's real DC limit is
not Metal1's and is not published here, so this is context for a human
reading the number, not a pass.

### The peak-current case is an upper bound, not a prediction

`sim/adc-rail-current/` also measures the **peak** current — 34.38 mA worst
corner (`ff_-40c_3.63v`), ~860× the average, because the CDAC's bottom-plate
T-gate legs switch together. Solving the same static network at that current
reports **17.99 V** of combined droop on a 3.3 V rail, and an EM verdict of
`fail`.

That is not a prediction of the rail voltage. It is what a purely resistive
network with **no charge storage in it** would develop if asked to source a
sub-nanosecond switching transient as a DC current — i.e. a statement that
the DC path alone cannot source the peak. That is true of essentially every
block, and it is what decoupling is for. **This block neither draws nor
specifies any decoupling**, and that gap is now recorded rather than
implied: see [DR-0034][dr0034]'s Consequences, and issue #379, which
asks for the decoupling budget this flow deliberately does not claim.

The case is kept in the committed set, with `budget_status: fail`, precisely
so that the gap is visible in the evidence rather than resting on a sentence
in a README.

### Two things that make the measured current a LOWER bound

Both travel with the verdict because both push the droop the wrong way:

1. **The SAR sequencer and output register draw nothing.** They are DR-0010
   rung-1 ideal XSPICE primitives in the deck, so their flip-flop and decode
   current is absent from every number here. The dominant digital term —
   driving the array's 72 T-gate legs — *is* measured; the sequencer's own
   consumption is not.
2. **2 ns is the deck's maximum timestep.** A switching spike shorter than
   that is averaged over the step it lands in.

So the margins quoted above are margins against a current that is smaller
than the real one, which is why a 5.8× nominal margin is reported as
adequate-with-a-condition rather than as comfortable.

## The controls

A clean number is worth its verdict only if it could have come out
differently. Two cases exist for the two ways it could have been a lie:

- **`control.doubled-current`** doubles every instance current and asserts,
  site by site, that every combined droop is **exactly** 2× the case it
  perturbs (5.722 → 11.444 mV). A linear resistive network must do that; a
  solve that had quietly stopped consuming the current model, or that was
  reporting some other network, cannot. The assertion is on the *factor*,
  not merely on the numbers differing.
- **`control.poly-as-metal1`** is the attribution counterfactual described
  above. If its answer had been close to the real one, the poly risers would
  not be the story and #346's premise would have been wrong.

## What `klt power` does not report (and what is done about it)

Two gaps were found standing this flow up. Both are filed upstream per this
repo's friction protocol, and both are worked around here in a way that
fails loudly if the workaround stops being valid.

1. **Per-edge geometry is dropped** —
   [klayout-tools#2345][ktp2345]. An edge carries `resistance_ohm` and
   `current_limit_a` but not the `length_um`/`cross_um` both were computed
   from, so a role with **no** published limit (Poly2, Contact — exactly the
   ones this block's rail runs through) has no derivable current density at
   all. `run_power.py` inverts the documented model instead:
   `cross_um = sheet_r × dist(node_from, node_to) / resistance_ohm`. That
   inversion is **asserted every run** against the roles that *do* publish a
   limit — for every Metal1 edge it must reproduce
   `current_limit_a / current_limit_a_per_um` to 1 part in 10⁶ — so an
   upstream change to the segment model fails the run rather than silently
   rescaling a density.
2. **No `provenance` block at all** — [klayout-tools#2349][ktp2349].
   `klt erc` has carried `provenance.input.content_hash` since
   klayout-tools#1968 and `provenance.spec.content_hash` since #2036;
   `klt power` echoes `file`/`spec` as bare paths and nothing else, so a
   committed report cannot be tied to the bytes it was solved against.
   `run_power.py` stamps `_layout_sha256` into each committed report and
   commits the composed spec beside it, and `--verify` re-checks both. That
   is *this runner's* attestation, not the tool's, and it is weaker for
   exactly that reason — it proves the report has not been separated from
   the geometry, not that `klt power` read those bytes. `check_case` fails
   the run if a `provenance` block ever appears, so this stand-in is retired
   deliberately rather than left to rot.

Two further `klt power` defects were found, filed, and **fixed** before this
flow's first record: [klayout-tools#2259][ktp2259] (a via attached to the
nearest node on the whole net instead of the polygon it lands on —
which fragments exactly this trunk-and-stub topology and reported ~0 mV
droop) and [klayout-tools#2260][ktp2260] (no `devices[]` carve-out, so the
comparator's poly load resistors and the CDAC's MiM caps were solved as
wire). Both are in the pinned `v0.6.0`. Both would have produced a *wrong
answer* rather than no answer, which is why `toolchain.json` asserts the
build instead of merely recording it.

## Scope: what this flow does not claim

- **Nothing transient.** A static DC solve prices the average current. See
  the peak-current section above, and issue #379.
- **No substrate or well path.** Only the declared conductor roles are
  modelled. `ADC_BLOCK`'s guard rings reach diffusion, not a labelled
  supply (`layout/erc/well-tap-audit.json`, [DR-0032][dr0032]) — so the 203
  `Contact` shapes `klt power` warns it skipped are diffusion contacts, not
  a missing supply path. Any real parallel conduction through substrate or
  well would *lower* the droop, so omitting it is conservative.
- **No package or board.** The pad is an ideal source at 3.3 V.
- **`VSUBS` is not modelled**, for the same reason `layout/erc/` does not
  declare it: it carries no label text in this stream.

[dr0032]: ../../spec/decision-records/DR-0032-implant-layers-not-drawn.md
[dr0035]: ../../spec/decision-records/DR-0035-well-taps-and-tie-straps.md
[dr0034]: ../../spec/decision-records/DR-0034-supply-droop-budget.md
[ktp2259]: https://github.com/2AMLogic/klayout-tools/issues/2259
[ktp2260]: https://github.com/2AMLogic/klayout-tools/issues/2260
[ktp2345]: https://github.com/2AMLogic/klayout-tools/issues/2345
[ktp2349]: https://github.com/2AMLogic/klayout-tools/issues/2349
