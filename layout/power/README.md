# `layout/power/` — IR drop and electromigration (`klt power`)

**Is the supply adequate for what it powers?** `layout/erc/` answered the
structural half of that question (T1 item 11: `vdd` and `vss` each resolve
to exactly one electrical island) and stopped there, deliberately — IR drop
and electromigration are `klt power`'s question, not `klt erc`'s. This
directory is the analysis half. Issue #346.

The premise it priced at issue #346 was the finding `layout/erc/` surfaced
on the way past: **neither rail had any geometry above Metal1.** Block-level
continuity ran through Metal1 trunks stitched by **Poly2 risers** — the
Metal1-trunk / Poly2-riser channel router in
`layout/adc-top/lib/geometry.py`.

**That premise is no longer true, because this flow's own numbers retired
it.** The droop it measured depended on *which* labelled site a parent
landed the supply at, by a factor of six, and one of the four missed the
budget (issue #378). The three block-level `vdd`/`vss` straps run on
**Metal2** since [DR-0037][dr0037], landing on each sub-block's Metal1 trunk
through a single Via1. What is still Poly2 is every *in-sub-block* terminal
riser — one per device terminal, the channel router itself — which is why
the EM verdict below is still `pass_partial` and why this flow still reports
a Poly2 current density at all.

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
`501f3985…` — the same bytes `layout/erc/cases.json` and
`signoff/gf180-sar-adc.manifest.json` pin), at the **worst-corner average
supply current** the block was measured to draw (40.12 µA total,
`ff_125c_3.63v`), graded against [DR-0034][dr0034]'s 33 mV combined budget.
Record: `records/20260923-084734-5f13cf9.md`, the issue #378 re-run against
the Metal2-strapped geometry; the "was" column is the figure the previous
record (`20260923-070149-e84ad26`, Poly2 straps) reported, kept beside it
because the delta is the point:

| Supply landed at | R corner | Worst site | `vdd` + `vss` | was | Budget |
|---|---|---|---:|---:|---|
| `COMPARATOR` | nominal | `ADC_DECODE_BANK_N` | **1.703 mV** | 5.722 | PASS (19× margin) |
| `ADC_DECODE_BANK_N` | nominal | `COMPARATOR` | 12.770 mV | 14.907 | PASS (2.6×) |
| `ADC_TOP_SW` | nominal | `COMPARATOR` | 5.962 mV | 21.390 | PASS (5.5×) |
| `ADC_DECODE_BANK_P` | nominal | `COMPARATOR` | **13.227 mV** | 33.552 **FAIL** | PASS (2.5×) |
| `COMPARATOR` | pessimistic | `ADC_DECODE_BANK_N` | 2.767 mV | 10.877 | PASS (12×) |
| `ADC_DECODE_BANK_N` | pessimistic | `COMPARATOR` | 16.697 mV | (not run) | PASS (2.0×) |
| `ADC_TOP_SW` | pessimistic | `COMPARATOR` | 11.485 mV | (not run) | PASS (2.9×) |
| `ADC_DECODE_BANK_P` | pessimistic | `COMPARATOR` | **17.184 mV** | 58.552 **FAIL** | PASS (1.9×) |
| `COMPARATOR` | optimistic | `ADC_DECODE_BANK_N` | 0.772 mV | 1.248 | PASS |

**The verdict is: adequate as drawn, at every labelled landing site.**
This block has no supply pad — it has four labelled sites, and until issue
#378 which one a parent connected decided whether the budget was met.
It no longer does: all four meet DR-0034 at both the nominal and the
pessimistic resistance corner, the worst of the eight at 17.184 mV, 1.9×
inside budget. Both pessimistic-corner cases that did not exist before
(`ADC_DECODE_BANK_N`, `ADC_TOP_SW`) were added at #378 for exactly that
reason: "at every labelled site" is a claim about four sites, so four sites
are run.

**What that does and does not say.** The droop still varies by site —
13.227 mV at the worst landing against 1.703 mV at the best is a factor of
7.8 — so this is not a flat rail and the flow does not claim one. What
changed is that no labelled site misses the budget, which is what makes the
block integrable without an unstated, uncheckable constraint on the parent.
And the margins are still margins against a current that is a **lower
bound** (see "Two things" below), which is why 1.9× is reported as adequate
rather than comfortable.

**What issue #378 changed, and what it did not.** [DR-0037][dr0037] moved
the three block-level `vdd`/`vss` straps from Poly2 to **Metal2** with a
Via1 at each trunk. The solved networks keep their shape — `vdd` 476 nodes /
477 edges, `vss` 610 / 613, one island each — with 3 Metal2 and 8 Via1 edges
per rail replacing the same count of Poly2 and Contact edges. **`vcm` was
deliberately left on Poly2**: it is a reference, not a supply, and sources
no standing current in the measured model. **The extracted netlists are
byte-identical** — this moves conductors, not connectivity.

**What issue #356 did before it**, kept because the two deltas are
independent: drawing 25 n-well taps and strapping both substrate-tie rings
into `vss` ([DR-0035][dr0035]) grew both solved networks (`vdd` 376 → 476
nodes, `vss` 494 → 610) and made every droop figure ~1.6 % worse, with no
verdict flipped. Those taps are still Poly2 risers — #378 changed the
block-level straps only.

### Where the droop actually is

Two counterfactual corners bracket it, and both are committed cases rather
than arguments:

- **`control.metal2-as-poly2`** re-solves the *new* geometry with Metal2
  given Poly2's sheet resistance — i.e. #378 un-done — and returns
  **33.177 mV, FAIL**, at the same site and corner that read 33.552 mV
  before the change. That is the attribution: the improvement is the
  straps, not some other movement in the network.
- **`control.poly-as-metal1`** re-solves the `COMPARATOR` landing with
  Poly2 given Metal1's sheet resistance. It used to move the worst combined
  droop from 5.722 mV to 1.681 mV — **~71 %** of the block-level droop was
  the poly stitching. It now moves it from 1.703 mV to 1.574 mV: **~8 %**.
  The poly term is no longer the story; what remains is Metal1 trunk and
  Contact.

One line does not move at all between the two: the `COMPARATOR` site's own
`vss` bounce, 1.4421 mV in both. That is the comparator's *local* access
resistance — its own 30.7 µA through its own contacts and short Metal1 runs
— not the block-level rail. (At the optimistic corner, where contacts are
0 Ω, it halves to 0.739 mV, which says roughly half of it is Contact.)

### Electromigration: `pass_partial`, and why it can never be `pass`

| | |
|---|---|
| `em_verdict.status` | `pass_partial` at every average-current case |
| failing edges | **0** |
| checked edges | 375 |
| unchecked edges | **715** |

Every unchecked edge is on **Poly2 or Contact**, because gf180mcuD publishes
no current-density limit for either: `Poly2` is `TYPE MASTERSLICE` and `CON`
is a bare `TYPE CUT` in the standard-cell tech LEF, with no
`DCCURRENTDENSITY` line, and nothing else in the install has one. `klt power`
counts them unchecked rather than guessing — correctly. This verdict cannot
become `pass` without a published poly limit, and no amount of re-running
will change that.

**Issue #378 moved the counts and not the verdict, which is worth being
exact about because #378's own acceptance criteria hoped otherwise.**
Carrying the block-level straps on Metal2 moved 22 edges per solve onto
roles that *do* publish a limit (353 → 375 checked, 737 → 715 unchecked),
so the edges carrying the most block-level current are now checked ones.
But every in-sub-block terminal riser is still Poly2 — one per device
terminal, by construction of the channel router — so `pass_partial` is
structural here, not a re-run away. Making it `pass` needs either a
published poly limit or a rewrite of `lib/place.Channel`, and
[DR-0037][dr0037] says so rather than implying the strap change settled it.

What *can* be said is the measured density. `run_power.py` derives it from
each segment's own reported resistance and endpoint nodes (see "What
`klt power` does not report" below):

| Case | Worst Poly2 riser | Width | Density |
|---|---:|---:|---:|
| `COMPARATOR` landing, nominal | 4.53 µA | 0.40 µm | **1.13 × 10⁻⁵ A/µm** |
| `ADC_DECODE_BANK_P` landing, nominal | 4.53 µA | 0.40 µm | **1.13 × 10⁻⁵ A/µm** |
| `ADC_TOP_SW` landing, nominal | 4.53 µA | 0.40 µm | **1.13 × 10⁻⁵ A/µm** |
| `ADC_DECODE_BANK_P` landing, `control.metal2-as-poly2` | 17.31 µA | 0.40 µm | 4.33 × 10⁻⁵ A/µm |

The worst Poly2 density is now the **same edge at the same current for every
landing site** — a `vss` riser carrying 4.53 µA — because no Poly2 edge is
on the block-level path any more; the site-dependent figures this table used
to carry (17.32 µA at the `ADC_DECODE_BANK_P` landing, 39.79 µA at
`ADC_TOP_SW`) were the block-level straps, and they are Metal2 now. The
counterfactual row is those straps put back on poly, kept so the number that
used to be here is still readable. Earlier edge-count history: 213 → 353
checked at issue #356, as the 25 well-tap risers and two strapped ring
annuli joined the rails.

For scale, and **not** as a verdict: Metal1's own published DC limit is
6.7 × 10⁻⁴ A/µm, so the worst Poly2 riser carries about a seventh of what
the same width of Metal1 would be allowed. Polysilicon's real DC limit is
not Metal1's and is not published here, so this is context for a human
reading the number, not a pass.

### The peak-current case is an upper bound, not a prediction

`sim/adc-rail-current/` also measures the **peak** current — 34.38 mA worst
corner (`ff_-40c_3.63v`), ~860× the average, because the CDAC's bottom-plate
T-gate legs switch together. Solving the same static network at that current
reports **4.93 V** of combined droop on a 3.3 V rail (17.99 V before the
Metal2 straps), and an EM verdict of `fail` with 30 failing edges.

That is not a prediction of the rail voltage. It is what a purely resistive
network with **no charge storage in it** would develop if asked to source a
sub-nanosecond switching transient as a DC current — i.e. a statement that
the DC path alone cannot source the peak. That is true of essentially every
block, and it is what decoupling is for. **This block neither draws nor
specifies any decoupling**, and that gap is now recorded rather than
implied: see [DR-0034][dr0034]'s Consequences, and issue #379, which
asks for the decoupling budget this flow deliberately does not claim.

That budget is now written — [DR-0036][dr0036], issue #379 — and it uses
this case, without changing it: read as an effective resistance rather than
as a droop, `17.987806 V / 34.383980 mA = 523 Ω` is the resistance between
the landing site and the decode banks *at the peak's own load distribution*
(the average case's same path is `5.616 mV / 40.120 µA = 140 Ω`; the two
differ because the average is comparator-dominated and the peak is
CDAC-dominated, which is exactly why the peak case is not a scaled average
case). DR-0036 is what concludes from that number that any local decoupling
has to be drawn **inside** `ADC_BLOCK`. Nothing in this flow changes: the
case stays an upper bound, and DR-0034 stays the static budget.

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
than the real one, which is why 1.9× at the worst site and corner is
reported as adequate rather than as comfortable.

## The controls

A clean number is worth its verdict only if it could have come out
differently. Three cases exist for the three ways it could have been a lie:

- **`control.doubled-current`** doubles every instance current and asserts,
  site by site, that every combined droop is **exactly** 2× the case it
  perturbs (1.703 → 3.406 mV). A linear resistive network must do that; a
  solve that had quietly stopped consuming the current model, or that was
  reporting some other network, cannot. The assertion is on the *factor*,
  not merely on the numbers differing.
- **`control.poly-as-metal1`** is the attribution counterfactual described
  above. When #346 filed it, an answer close to the real one would have
  meant the poly risers were not the story and #346's premise was wrong. It
  now IS close to the real one (1.574 vs 1.703 mV) — which is the same
  statement read from the other side, after [DR-0037][dr0037] took the
  block-level current off poly.
- **`control.metal2-as-poly2`** is the control on issue #378 itself: the
  new geometry with Metal2 given Poly2's sheet resistance, which must
  return this block to the pre-#378 verdict (33.177 mV, FAIL, against
  33.552 mV measured on the Poly2-strapped geometry). If it did not, the
  improvement would be coming from something other than the straps and the
  whole change would be unattributed.

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
  the peak-current section above; the transient half is budgeted separately
  by [DR-0036][dr0036] (issue #379), which cites this flow's numbers and
  changes nothing in it.
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
[dr0036]: ../../spec/decision-records/DR-0036-vdd-decoupling-budget.md
[dr0037]: ../../spec/decision-records/DR-0037-block-level-supply-straps-on-metal2.md
[ktp2259]: https://github.com/2AMLogic/klayout-tools/issues/2259
[ktp2260]: https://github.com/2AMLogic/klayout-tools/issues/2260
[ktp2345]: https://github.com/2AMLogic/klayout-tools/issues/2345
[ktp2349]: https://github.com/2AMLogic/klayout-tools/issues/2349
