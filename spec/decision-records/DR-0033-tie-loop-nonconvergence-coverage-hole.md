# DR-0033: Non-convergence on the `tie` deck is a hash-bound attributed coverage hole, not a reason to change its stimulus or its comparator

- **Status**: ratified — two-key ratification PR #413 (routed by agent
  decision option (a) on issue #363, 2026-10-08)
- **Date**: 2026-09-21
- **Decided by**: Builder agent, issue #345
- **Supersedes**: [DR-0029](DR-0029-tie-loop-decision-chatter.md) — same
  question (what the `tie` loop's decision chatter is, and what to do about
  it), decided on a strictly larger evidence base. DR-0029's disposition of
  the stimulus, the comparator and `CMP_OUT_RC` is carried forward unchanged;
  its characterisation of the chatter regime, its statement of where the
  chatter's exposure lies, and its "no evidence record is invalidated"
  consequence are replaced.
- **Superseded by**: (none while this record stands)
- **Related**: #345 (this record's own issue), #332 (the `cd57d203…` abort,
  root-caused), #337 (the sibling bound "failure" on `cd57d203…`, root-caused),
  #303 (the initial `c6d73a3` grid), #322 (DR-0029's own issue), #310, #296,
  #327 (DR-0031 part 2's execution, commit `60336f22`), #341 (the harness
  defect that lets an aborted point still print a number), #343 (`lt`/`xl`'s
  aborts — **not** this record's business), #363 (the citation reconciliation
  this record gates on its own sign-off), #596 / #777 (the `f6eeac7` deck
  regeneration and re-qualification grid),
  [DR-0008](DR-0008-sar-logic-synchronous.md) (the record that defines the
  `tie` loop and the near-metastable consequence it measures — **not**
  superseded, see Spec lines affected),
  [DR-0010](DR-0010-mixed-signal-sim-strategy.md) (the bisected 50 ns / 52 ns
  `cmp_delay` boundary candidate 2 would invalidate),
  [DR-0031](DR-0031-power-up-first-conversion-validity.md) (whose mechanism B
  explains #337 and whose part 2 is the correction #327 executes; note DR-0031
  itself remains `proposed`),
  `sim/sar-logic-timing-gates-tie/investigations/20260921-issue-332-quiescent-supply-row-nonconvergence.md`
  (the `cd57d203…` abort measurement),
  `sim/sar-logic-timing-gates-tie/investigations/20260921-issue-337-tie-code-deviation-decode-transient.md`
  (the `cd57d203…` decode-transient measurement that retires the other half of
  the trigger),
  `sim/sar-logic-timing-gates-tie/records/20260920-020802-2043286.md` (the
  45-point grid on deck `cd57d203…`, 29/45 scored),
  `sim/sar-logic-timing-gates-tie/records/20261117-094722-0185db3.md` (the
  45-point grid on current `f6eeac7` deck `2a6bfef4…`, 39/45 scored, all PASS),
  `sim/sar-logic-timing-gates-tie/records/20261125-193834-c361768.md` (the
  full 8.5 µs `sf_27c_2.97v` single-corner re-measure on current deck
  `2a6bfef4…`, PASS),
  `sim/sar-logic-timing-gates-tie/testbench/tb.json` (the manifest whose
  claim and bounds this record leaves **unchanged**)

## Ratification note

Ratified together with the supersession of DR-0029 by two-key ratification
PR #413, routed by the 2026-10-08 agent decision (option (a)) on issue #363.
DR-0029 was `proposed` and is ratified-and-superseded in this same change;
this record is the one in force. Prior to ratification (while still
`proposed`, per `spec/decision-records/README.md`), this record was updated
in PR #413 in response to the engineering-key review: every #332, #337 and
`20260920-020802-2043286` measurement was pinned to its testbench netlist
sha256 (`cd57d203…`); Decision item 5 gained the rule that an attribution
lapses when the deck hash changes; and the title, Context, Decision item 6
and Consequences were updated against the current `f6eeac7` deck
(`2a6bfef4…`), its 45-point grid (`20261117-094722-0185db3`, 39/45 PASS) and
the full 8.5 µs `sf_27c_2.97v` re-measure (`20261125-193834-c361768`, PASS).
DR-0029's `Superseded by` back-pointer is now in force. The citation edits
this record gated (`tb.json`'s note, the `design/sar-logic/rtl/README.md`
entry, the probe re-check) are issue #363 Part B and land after this
ratification, in their own change.

## Context

DR-0029 nominated its own supersede trigger: *"If #303's remaining coverage
finds a corner where `tie_conv_period_ns` or `tie_code_deviation` actually
fails **and** the chatter is implicated, this record is the one to supersede —
with the measurement, not with a relaxation."* #303's `tie` grid ran on the
pre-#327 `c6d73a3` testbench deck (**netlist sha256
`cd57d203850b1c88529f20eedfab3c75358ec33405965470cfee1d2cacc9f69d`**, record
`20260920-020802-2043286`), and two candidate firings arrived. Only one of
them is real, and saying which — pinned to the exact deck hash each
measurement came from — is the first thing this record has to do.

**#337 does not fire the trigger, and this record records that as a finding
rather than passing over it.** On deck `cd57d203…` (`20260920-020802-2043286`),
six of the 29 scored points reported `tie_code_deviation = 512` against a
`max 1.0` bound. Measured on that same deck
(`…-issue-337-tie-code-deviation-decode-transient.md`), the *settled* code at
every conversion of every one of the six is **511 or 512** — inside the bound,
and exactly the "either adjacent code answers an exact tie" behaviour the
bound exists for. Each 512 LSB deviation came from decoding zero as `drdy`
rose, before the register outputs had settled. At `tt_-40c_3.63v`,
conversion 7, the register changed from 512 to 511. The high bit fell below
the decode threshold before the nine low bits crossed it, so the probe read
an intermediate zero. At `ff_27c_3.63v`, conversion 1, the probe still read
the power-up word, zero, as the register loaded 512. Both are examples of
sampling during a register load (mechanism B in
[DR-0031](DR-0031-power-up-first-conversion-validity.md)). Commit `60336f22`
(#327, merged 2026-09-22) implemented the readout correction in part 2.
**DR-0031 itself remains `proposed`.** The chatter is
implicated in the *carries* (a loop pinned on the threshold latches 511 on one
conversion and 512 on the next, so `tie` sees up to 8 ten-bit carries in 8
conversions — more than any other loop in the family) but not in the failure.
The subsequent `f6eeac7` grid (`20261117-094722-0185db3`, deck `2a6bfef4…`,
carrying #327's settled-`drdy` gate and `FROM=1.5u`) confirms zero `512`
failures across all 39 scored points (`tie_code_deviation` 0–1 everywhere).
**`tie_code_deviation` has never failed on a settled code.**

**#332 fires the trigger on deck `cd57d203…`, on a reading that must be
stated plainly rather than assumed.** On deck `cd57d203…`
(`20260920-020802-2043286`, ngspice-46, open_pdks `c6d73a3`), at
`sf_27c_2.97v` the run did not *fail* a bound — it aborted
(`Timestep too small; time = 3.99655e-07, timestep = 6.25e-21: trouble with
node "vvdd_gate#branch"`) at 399.655 ns — before `tie_a`, the second `drdy`
rise that `tie_conv_period_ns` is defined from. `tie_conv_period_ns` was
therefore `n/a`, and the `tie_code_deviation = 0` that grid printed at that
point was not a measurement at all: `dev_tie` was an unbounded-right
`meas tran … MAX v(tie_dev) FROM=0.1u`, so ngspice emitted a number from a
400 ns truncated transient in which no conversion completed (the harness
defect is #341). An ERROR is not a FAIL, and DR-0029's trigger says "actually
fails". **What fires the trigger is the stronger condition the trigger was
written to catch**: a corner of the ratified box at which a deck hash delivers
*neither* claim, with the chatter as the implicated proximate driver. That was
met once on `cd57d203…` — not, as #345 supposed, twice.

And the trigger fires on a fact DR-0029 did not have, which is why a new
record and not a re-reading is required. DR-0029 measured the `tie`
differential at "~1e-7 V — the solver's own noise floor", and built its whole
argument on the model's resolution being set by ngspice's node-voltage
tolerance `vntol` (1e-6 V). At the `cd57d203…` abort, `--numdgt 17` resolves
what the default probe could not: over the last 25 accepted timepoints
(`--tail 25`) the differential is **0 … 3.8 × 10⁻¹³ V (0 … 1690 ulp of a
1.485 V node)**, and over the 97-point terminal window (`t ≥ 399.486 ns`) its
median is **3.4 × 10⁻¹⁴ V** with **two accepted timepoints at which the two
nodes are bit-identical**. The median is about seven orders of magnitude below
`vntol`. At this scale, rounding in the last LU update could change the sign
seen by the comparator. The probe records only accepted timepoints, so it
cannot identify which Newton iteration or update caused a given reversal.

**The abort outcome changed across deck revisions.** Two later revisions of
`tb_sar_logic_timing_gates_tie.spice` have measurements at the same corner.

- **Deck `9a9405e60589b8e34e87dca34d9b8746ced365619a0aa704954d30295f6a450c`**
  (commit `60336f22`, DR-0031 part 2): five measurement-only lines (a
  behavioural copy of `drdy`, a 1 kΩ / 721.348 fF RC network on it, and the
  code-deviation gate) that load neither the DUT, the comparator, nor the
  supply row. During PR #413's engineering-key review, `sf_27c_2.97v` ran to
  410 ns without aborting (7337 accepted timepoints, 1483 reversals, 12.636 ns
  mid-rail dwell) while the differential still hit the same ulp floor in
  393–399.66 ns (median 2.7e-13 V, minimum 1 ulp). A non-electrical edit
  flipped the abort off, proving that an abort attribution is evidence about
  one netlist hash, not a permanent property of a corner.
- **Current deck `2a6bfef48cd5ae0cb9677219dd39c977a34e7b634986558248d565118e454fc1`**
  (commit `a699814d`, regenerated under pinned open_pdks `f6eeac7`, swapping
  `*fet_06v0` → `*fet_05v0`): the 45-point grid `20261117-094722-0185db3`
  (ngspice-47, AWS Spot batch fleet, 900 s per-point timeout, superseding
  `20260920-020802-2043286`) scored **39 of 45 points, all 39 PASS** (0 FAIL,
  `tie_code_deviation` 0–1, `tie_conv_period_ns` 999.999–1000 ns). Three
  points timed out at 900 s (`ss_27c_3.63v`, `ss_125c_2.97v`, `sf_27c_2.97v`).
  One Spot interruption, job `klt-sim-475afca7e317`, left three more points
  unscored (`sf_-40c_3.63v`, `sf_27c_3.63v`, `sf_125c_3.63v`).
  A dedicated full 8.5 µs single-corner re-measure of
  `sf_27c_2.97v` at zero offset on this same deck (`20261125-193834-c361768`,
  fleet job `klt-sim-441a9130bdc0`, `c7i.4xlarge`, ngspice-47, `timeout_s = 2400`)
  **completed all 8.5 µs in 762.6 s (48,616 data rows, zero abort) and PASSED
  both bounds** (`tie_code_deviation = 0`, `tie_conv_period_ns = 1000.0 ns`).
  On the current deck, `sf_27c_2.97v` is scorable and passes; the old abort
  belongs to `cd57d203…`.

## Decision

**The `tie` loop's stimulus, comparator model, output network and bounds all
stand unchanged; any solver non-convergence on a `tie` deck is priced as a
hash-bound *attributed coverage hole* — lost coverage of that deck hash's PVT
grid rather than a licence to alter the stimulus, comparator, or bounds.**
Concretely:

1. The `tie` loop's input stays `dc {vcm}` — pinned **exactly** on the
   threshold, with no offset of any magnitude. (DR-0029 item 1, carried;
   re-argued below on the new measurement, not merely restated.)
2. The comparator stays the continuous-time hard ternary
   `v(topp) > v(topn) ? vdd_val : 0`, evaluated at every accepted timepoint
   and **not** strobed, identically for all five loops and the rung-1 ideal
   decks. (DR-0029 item 2, carried unchanged.)
3. `CMP_OUT_RC` stays `("1k", "100f")` (tau = 100 ps), pinned from below by
   #296 and from above by DR-0029. At `sf_27c_2.97v` on deck `cd57d203…`,
   #332 tested three alternative `--cmp-rc` settings through 410 ns.
   All three reached that stop time (see Candidate 5).
   (DR-0029 item 3, carried.)
4. `sim/sar-logic-timing-gates-tie/testbench/tb.json`'s `claim`,
   `tie_code_deviation` (`max = 1.0`) and `tie_conv_period_ns`
   (`999.9 … 1000.1 ns`) are unchanged in wording and in value; no manifest
   gains a solver `.options` entry. (DR-0029 item 4, carried. Note that #327 /
   commit `60336f22` moved `dev_tie`'s measurement window from `FROM=0.1u` to
   `FROM=1.5u` and added the settled-`drdy` gate per DR-0031 part 2 without
   moving `claim` or either bound.)
5. **New — an ngspice non-convergence on this deck is a coverage hole, not a
   result and not an accepted property, until it is attributed on that exact
   deck hash.** A point that ERRORs may be excluded from a `tie` claim's
   coverage only when a committed `investigations/` document names its
   mechanism on that point's own run. Until then it is an **open defect**, not
   a recorded property. **Every attribution is bound to the testbench netlist
   sha256 on which it was measured and lapses automatically whenever that hash
   changes** (even for a measurement-only edit, as `60336f22` / `9a9405e6…`
   demonstrated). Concretely:
   - On deck `cd57d203…` (`20260920-020802-2043286`): `sf_27c_2.97v` is
     discharged by #332; that grid's **15 timed-out points are not
     discharged**, and #332 explicitly declines to assume they are free of the
     same state.
   - On current deck `2a6bfef4…` (`20261117-094722-0185db3`): #332's
     attribution has **lapsed** (and `20261125-193834-c361768` measures
     `sf_27c_2.97v` completing 8.5 µs and PASSing). The 6 ERROR points in
     `20261117-094722-0185db3` (three 900 s timeouts and three points lost
     to one Spot interruption) are **open defects** on that grid record until
     a fresh grid scores them or a committed investigation attributes them on
     `2a6bfef4…`.
6. **New — the `tie` claims are scoped to the points that scored in the cited
   grid record.** Any signoff text, spec row or record citing
   `tie_conv_period_ns` or `tie_code_deviation` must carry that grid record's
   scored coverage and record id (or deck hash) in the same breath as the
   number:
   - For historical record `20260920-020802-2043286` (deck `cd57d203…`,
     open_pdks `c6d73a3`): **29 of 45** points scored (`tie_conv_period_ns`
     29/29 PASS; `tie_code_deviation` 23 PASS and 6 decode-transient FAILs).
   - For current governing grid `20261117-094722-0185db3` (deck `2a6bfef4…`,
     open_pdks `f6eeac7`): **39 of 45** points scored (**39/39 PASS**, 0 FAIL,
     6 ERROR). Subset record `20261125-193834-c361768` additionally confirms
     that `sf_27c_2.97v` completes 8.5 µs and PASSes on `2a6bfef4…`
     (`tie_code_deviation = 0`, `tie_conv_period_ns = 1000.0 ns`), without
     retroactively raising `20261117-094722-0185db3`'s grid count until a
     fresh full-grid run scores all 45 points.

The reasoning, stated once: **DR-0029's disposition was right and its account
of why was wrong in the way that matters.** The chatter is not "at the
solver's noise floor"; it is at the floating-point floor, and it does not
endanger the DUT — it endangers the matrix. A model property that can cost a
point of solver coverage on a given deck hash is priced as hash-bound
coverage. It is not paid for with the experiment's own definition.

## What this record rests on

Every number above and below is pinned to the testbench netlist sha256 on
which it was measured and is re-derivable from a committed document:

| fact | deck netlist sha256 | source | re-run with |
|---|---|---|---|
| `sf_27c_2.97v` aborts at `t = 3.99655e-07`, `h = 6.25e-21`, `vvdd_gate#branch` (2446 timepoints, 481 reversals, 8.416 ns dwell) | `cd57d203…` (`f063c771`, `c6d73a3`) | #332 Evidence 1 (reproduced in PR #413 EE-key review) | `probe_cmp_convergence.py sar-logic-timing-gates-tie --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter` on `f063c771` |
| differential 0 … 3.8e-13 V (0 … 1690 ulp) over last 25 timepoints; median 3.4e-14 V and two bit-identical timepoints over 97-point terminal window (`t ≥ 399.486 ns`) | `cd57d203…` | #332 Evidence 3 (median and two zeros reproduced in PR #413 EE-key review) | same, `--numdgt 17 --tail 25` on `f063c771` |
| `v(tie_cmpo)` at 2.96980 V at the abort, 200 µV below the 2.970 V supply | `cd57d203…` | #332 Evidence 2, terminal timepoints | same, `--probe --chatter --tail 40` on `f063c771` |
| 197.8 µA excursion, invariant to a 2× change in `h`, on a 4.8 nA row | `cd57d203…` | #332 Evidence 4 | same, `--keep` + `_probe_tables` on `f063c771` |
| The 100 µV and 1 mV offset probes both reached their 410 ns stop time at `sf_27c_2.97v` | `cd57d203…` | [#332 Evidence 5](../../sim/sar-logic-timing-gates-tie/investigations/20260921-issue-332-quiescent-supply-row-nonconvergence.md#evidence-5--the-lethal-coincidence-and-why-one-corner-of-45) | On `f063c771`, run the 410 ns abort probe above once with `--tie-offset 100u` and once with `--tie-offset 1m` |
| settled code is 511 or 512 at every conversion of all six "failing" points | `cd57d203…` | #337 Evidence 3 | `probe_code_readout.py sar-logic-timing-gates-tie --corner … --bits` on `f063c771` |
| `tie_conv_period_ns` PASSES at **29 of 29** scored points (999.999 … 1000 ns); 23 PASS, 6 `512` FAIL, 15 timeouts, 1 abort | `cd57d203…` | `records/20260920-020802-2043286.md` Result table | historical record (`c6d73a3`, ngspice-46) |
| `sf_27c_2.97v` completes to 410 ns without aborting (7337 timepoints, 1483 reversals, 12.636 ns dwell; differential median 2.7e-13 V, min 1 ulp in 393–399.66 ns) | `9a9405e6…` (`60336f22`, `c6d73a3`) | PR #413 EE-key review (2026-10-08) | `probe_cmp_convergence.py sar-logic-timing-gates-tie --corner sf --temp 27 --vdd 2.97 --until 410n --probe --chatter --numdgt 17` on `60336f22` |
| **39 of 45** points score and **all 39 PASS** (`tie_code_deviation` 0–1, `tie_conv_period_ns` 999.999–1000 ns). Three points timed out at 900 s, including `sf_27c_2.97v`. One Spot interruption left three more unscored. | `2a6bfef4…` (`a699814d`, `f6eeac7`) | [20261117-094722-0185db3](../../sim/sar-logic-timing-gates-tie/records/20261117-094722-0185db3.md) | [Full grid](#full-grid) |
| At zero offset, `sf_27c_2.97v` completes the full 8.5 µs in 762.6 s (48,616 rows, zero abort) and **PASSES** (`tie_code_deviation = 0`, `tie_conv_period_ns = 1000.0 ns`) | `2a6bfef4…` (`a699814d`, `f6eeac7`) | [20261125-193834-c361768](../../sim/sar-logic-timing-gates-tie/records/20261125-193834-c361768.md) (job `klt-sim-441a9130bdc0`) | [Single corner](#single-corner) |

The bottom rows are the ones that decide this record, and the conclusion is
stronger on the current deck than on the old one: **the chatter has never
falsified the claim the loop exists to test.** DR-0008's consequence is that a
near-metastable decision "corrupts at most one bit and cannot stall the
conversion". Measured: `drdy` arrives 16 clocks apart to within the ratified
999.9 … 1000.1 ns bound at every point where the measurement was reached
(29/29 on `cd57d203…`; 39/39 on `2a6bfef4…` plus `sf_27c_2.97v` in
`20261125-193834-c361768`), and the settled code is within 1 LSB of mid-scale
everywhere it has been measured (and every scored point on `2a6bfef4…` passes
directly).

### Full grid

From the repository root, reproduce the November 17 grid with five jobs per
supply, three process/temperature points per job, and 900 s per point.

```sh
python3 sim/run_corners.py sar-logic-timing-gates-tie --backend batch \
    --timeout 900 --max-units-per-job 3 --max-in-flight 1 \
    --max-concurrent-jobs 3 --capacity-retries 2 \
    --supersedes 20260920-020802-2043286
```

### Single corner

The November 25 record used a 2400 s budget for the corner that timed out
in the grid. The quoted subset justification is copied from that record.

```sh
python3 sim/run_corners.py sar-logic-timing-gates-tie --backend batch \
    --corners sf --temps 27 --supply 2.97 --supply-tol 0 \
    --timeout 2400 --runner-version-check warn \
    --subset-reason 'PR #413 / EE-key item 1 single-corner 8.5 us re-measure of sf_27c_2.97v on the current f6eeac7 deck (tb netlist sha256 2a6bfef4...4fc1) with timeout_s=2400, supplementing 45-point grid 20261117-094722-0185db3 where this corner hit the 900 s timeout.'
```

## Alternatives considered

### Candidate 1 — a sub-LSB `tie` offset at 100 µV (0.031 LSB at 3.30 V, 0.0345 LSB at 2.97 V) — **the strongest candidate, and rejected on three measured grounds**

At `sf_27c_2.97v` on base deck `cd57d203…`, #332 set a 410 ns stop time for
both probes. The last column gives the longest contiguous interval with
comparator input differential below 1 nV and supply current below 1 µA,
both in magnitude. #332 Evidence 5 reports that duration to four decimal places.

| Input offset | Probe outcome | Total accepted timepoints | Reversals | Mid-rail dwell | Longest qualifying interval |
|---|---|---:|---:|---:|---:|
| 0 | Aborted at 399.655 ns | 2446 | 481 | 8.416 ns | 0.1693 ns |
| 100 µV | Reached 410 ns | 481 | 36 | 2.748 ns | 0.0000 ns |

DR-0029's original 1 µV proposal equalled the solver's voltage tolerance
`vntol`. The proposed 100 µV input offset is 100× that tolerance and about
4.5 × 10¹¹ ulp at 1.485 V.

- **Two corners is not the evidence base for a stimulus change to a 45-point
  grid whose incidence is corner-dependent, on a knob whose own sweep is
  measurably non-monotone.** DR-0029 measured `{vcm+10u}` to be **4.4× worse**
  than committed on mid-rail dwell (11.118 ns against 2.523 ns) at
  `tt`/27 °C/3.30 V — a small offset can relocate reversal bursts into a
  worse-placed window rather than remove them. The 100 µV measurements on
  base deck `cd57d203…` cover two short windows. At `tt`/27 °C/3.30 V,
  DR-0029's 400 ns probe recorded 397 accepted timepoints, 14 reversals and
  1.083 ns of mid-rail dwell. The SF probe above reached 410 ns.
  At the same SF corner, the separate `--cmp-rc 1k,10f` probe reached 410 ns
  despite a longer qualifying interval (0.4485 ns) than the aborting baseline.
  The 45-point grid remains unmeasured at 100 µV. Adopting that offset
  would require fresh grid evidence for the changed stimulus.
- **It costs the claim, and the claim is the deliverable.** `tb.json` and
  DR-0008 both turn on the input being pinned *exactly* on the threshold. At
  `{vcm+100u}` the deck measures a 0.034 LSB input, and DR-0008's consequence
  would have to be restated as "near-metastable, where *near* means within
  1/29 of an LSB". That is a defensible experiment — it is simply not the one
  DR-0008 promised, and an honest version of it is a **sixth loop placed
  beside `tie`**, not a quiet substitution inside it. DR-0029 anticipated
  exactly this and required the successor to "adopt a redesigned loop *with
  its own stated claim*"; this record declines to pretend a 0.034 LSB offset
  leaves the stated claim intact.
- **Full-transient runtime.** On base deck `cd57d203…` at `tt`/27 °C/3.30 V,
  DR-0029 timed the full 8.5 µs at **209.07 core-s with zero offset** and
  **76.71 core-s with 1 mV**, a **2.7× speedup**. The 100 µV row in its
  400 ns sweep reports timepoints, reversals and dwell. [DR-0029 timing experiment](DR-0029-tie-loop-decision-chatter.md#the-cost-the-chatter-actually-carries)

  On the current `f6eeac7` deck `2a6bfef4…`, `sf_27c_2.97v`
  already completes the full 8.5 µs transient and
  passes with zero offset (`20261125-193834-c361768`), and 39/39 scored grid
  points pass (`20261117-094722-0185db3`). Paying the experiment's definition
  while the loop is still answering its own question everywhere it is scored
  is the wrong trade.

**What would license it later, stated so a future record does not have to
invent the bar.** A record adopting a `tie` offset should carry: (a) the full
45-point grid re-run at the proposed offset, scoring **at least** the scored
coverage of the governing committed-deck grid (`29/45` on `cd57d203…`;
`39/45` on `2a6bfef4…`); (b) a measurement that the asymptotic differential
stays above `vntol` by a stated margin at every corner; (c) a restated
`claim` and a restated DR-0008 consequence that
say what "near" now means numerically; and (d) an explicit disposition of
whether the exact-tie loop is *replaced* or *joined*. None of those exists
today.

### Candidate 2 — strobe the comparator — **rejected on cost to the rest of the family, which #332 raises rather than lowers**

DR-0029 §Alternatives candidate 1 already enumerated the consequences, and
they are carried here rather than re-derived: `gen_sar_logic._loop` emits one
comparator for every loop of every deck in this family, so **strobing all
five** stops `lt`/`xl`/`bad` measuring what they exist to measure — the margin
between a *continuous-time* decision and the latching edge — forcing
re-derivation of the 40/50/70 ns `cmp_delay` brackets, **DR-0010's bisected
50 ns / 52 ns boundary**, the decks' own committed header text, and the
existing evidence in `sim/sar-logic-timing/`,
`sim/sar-logic-timing-gates-ok/`'s 45-point grid and the five-loop parent's
records. **Strobing only `tie`** destroys the `ok`-vs-`tie` control that let
#310 attribute the chatter to the stimulus in the first place — the two decks
run the identical comparator and identical `cmp_out_rc` and differ only in
stimulus. And a strobe instant has to come from somewhere: deriving it from
`clk` writes the bit-trial cadence into the stimulus of the loop whose sole
cadence claim is that the *DUT* keeps that cadence.

#332 changes the balance in two ways, one for and one against, and both are
recorded:

- **For strobing.** On `cd57d203…`, the longest measured stretch with a
  quiescent supply and a differential below 1 nV lasted 0.1693 ns, ending at
  the abort, 6.6 ns before the next clock edge (#332 Evidence 5). A comparator
  strobed only on clock edges would hold its output throughout that window.
  As DR-0029 observes, the strobe would still sample a hard sign test at the
  threshold once per bit trial.
- **Against (new, and decisive)**: `lt` and `xl` originally had **zero**
  points that completed the ratified transient across two `c6d73a3` 45-point
  grids (#303, `20260920-182006-2422cac` / `20260921-021359-2422cac`), and
  their own aborts were a separate mechanism (#343). The family cannot absorb
  a model change that re-dates `ok`'s and the parent's evidence to chase a
  `tie` corner that already completes on `2a6bfef4…`. A strobed model belongs
  to a deck designed around it, not a retrofit across an active timing family.

### Candidate 3 as a bare "no change" — **not sufficient, and not what is ratified here**

Restating DR-0029 unchanged would leave three of its statements standing that
the #332 measurement on `cd57d203…` contradicts: that the differential sits at
the solver's noise floor (it reaches the floating-point floor, confirmed on
both `cd57d203…` and `9a9405e6…`); that the exposure is the DUT's `cmp` port
sitting in the standard cells' 0.8–2.5 V switching band (at `sf_27c_2.97v` on
`cd57d203…`, `v(tie_cmpo)` stayed at 2.9698 ± 0.0001 V during the terminal
window, well above the switching band); and that "#303's remaining
`tie` coverage can be scheduled against the decks exactly as they stand"
without explicit coverage scoping or hash-bound attribution (a deck hash can
lose points to solver non-convergence, as `cd57d203…` did at `sf_27c_2.97v`).
Items 5 and 6 of the Decision exist because of those three.

### Candidate 4 — a solver `.options` entry — **measured to work on `cd57d203…`, and forbidden**

On deck `cd57d203…`, #332 Evidence 6 measured **8.416 ns of mid-rail dwell**
with default solver tolerances and 2,446 accepted timepoints through the abort
at 399.655 ns. With `reltol=1e-2`, ngspice completed 410 ns in 848 accepted
timepoints and reported **205.451 ns of mid-rail dwell**. The 24.4× ratio
compares the reported dwell durations over those two runs. The looser tolerance
changed the diagnostic as well as the convergence outcome. The manifest keeps
the default tolerances, as enforced by
`sim/tests/test_sar_ctrl_gates_tb.py::SharedSupplyRowTests::test_no_manifest_papers_over_the_abort_with_a_solver_option`.

### Candidate 5 — move `CMP_OUT_RC` — **three alternative settings reached 410 ns**

At `sf_27c_2.97v` on base deck `cd57d203…`, the `1k,1p`, `1k,10f` and
`10k,10f` probes all reached their 410 ns stop time (#332 Evidence 5).
`1k,1p` accumulated **391.326 ns** of mid-rail dwell (46× the aborting
baseline's 8.416 ns). The `1k,10f` probe had a longer hazard window than the
baseline and 826 µA excursions. The committed network addresses the abort
in #296. Changing it across all five decks would require evidence beyond
this single-corner probe.

### Candidate 6 — relax or re-scope a `tb.json` bound — **not applicable and forbidden**

Neither bound is implicated: an abort never reaches a measurement, so moving a
bound would hide an ERROR rather than change anything about convergence.

## Consequences

- **This record buys no convergence, and convergence behaviour is hash-bound.**
  On deck `cd57d203…`, `sf_27c_2.97v` reproduces the `t = 3.99655e-07` abort
  deterministically (confirmed independently in PR #413's engineering-key
  review) — on that hash a re-run is not a retry. On later hashes that abort
  is gone: `sf_27c_2.97v` completed to 410 ns on `9a9405e6…` and completed the
  full 8.5 µs transient with `PASS` on current deck `2a6bfef4…`
  (`20261125-193834-c361768`, 762.6 s). The probes measured the comparator
  input differential near 399.65 ns on `cd57d203…` and `9a9405e6…`. The full
  run on `2a6bfef4…` measured conversion cadence and code deviation. Item 5
  requires fresh evidence to attribute an abort on a different netlist hash.
- **Every `tie` claim now carries its grid record's scored coverage**, and
  that is a real constraint on what this block can say, not a bookkeeping
  note. On historical record `20260920-020802-2043286` (`cd57d203…`),
  `tie_conv_period_ns` is substantiated at **29/45** points and unknown at 16.
  On current governing grid `20261117-094722-0185db3` (`2a6bfef4…`), both
  claims are substantiated at **39/45** points (all PASS) and unknown at 6;
  subset record `20261125-193834-c361768` additionally scores `sf_27c_2.97v`
  as PASS on `2a6bfef4…`. Correcting the text that presents the grid as
  full-PVT is **gated on ratification** and lands in #363 Part B (see Spec
  lines affected).
- **Decision item 5 makes unattributed ERRORs open defects rather than neutral
  gaps.** On `cd57d203…`, `20260920-020802-2043286`'s 15 timeouts remain
  unattributed; on current deck `2a6bfef4…`, `20261117-094722-0185db3`'s 6
  ERRORs (three 900 s timeouts and three points lost to one Spot interruption)
  remain open defects on that grid until a fresh grid scores them or a
  committed investigation attributes them on `2a6bfef4…`. The separate
  `20261125-193834-c361768` run scored `sf_27c_2.97v` in 762.6 s.
- **Bad consequence, stated plainly**: this record establishes **no predictive
  rule** for which corners or deck hashes abort. #332 explicitly declined to
  claim one on `cd57d203…` (one of its ten rows had a longer hazard window and
  reached the 410 ns stop time), and `9a9405e6…` showed that even five
  measurement-only lines could change the outcome. If a future deck hash
  returns solver aborts, item 5 forces each to be attributed individually on
  that hash, and nothing here makes that cheaper.
- **Bad consequence, stated plainly**: the strongest argument *against* this
  record is candidate 1's. At `sf_27c_2.97v` on base deck `cd57d203…`, the
  100 µV offset moved the input by 0.034 LSB and the probe reached 410 ns.
  At the same corner on current deck `2a6bfef4…`, the full 8.5 µs run
  passed both bounds at zero offset (`20261125-193834-c361768`).
  A reader who wants to trade exact-tie fidelity for
  runtime or full-box convergence should re-open it with the four items listed
  under candidate 1.
- **The DUT-facing node stayed above the switching band in the terminal
  window.** At the abort on `cd57d203…`, #332 measured `v(tie_cmpo)` at
  2.96980 V, about 200 µV below the 2.970 V rail. The ~10 µV figure is the
  estimated movement during one short reversal. The upstream hard decision
  `v(tie_cmpd)` switched between 0 and 2.970 V.
  `probe_cmp_convergence.py --probe` reports both nodes.
- **`tie_code_deviation` remains a check that the code lands adjacent to
  mid-scale**, not a bit-wise reproducible number (DR-0029, carried) — and
  after #337, a 512 in a pre-#327 `tie` grid (`cd57d203…`) is a decode
  transient, not a saturated code. Since #327 (commit `60336f22`, executing
  DR-0031 part 2 while DR-0031 itself remains `proposed`), all 39 scored
  points of `20261117-094722-0185db3` and `20261125-193834-c361768` report
  `tie_code_deviation` ∈ {0, 1}.
- **This record licenses nothing outside this loop.** A chattering decision in
  a loop whose input is *not* pinned on the decision threshold is a defect,
  not a model property. In particular it says nothing about `lt`/`xl`'s aborts
  on the same `vvdd_gate#branch` node (#343): those are on decks whose only
  structural difference from the converging `ok` deck is an ideal lossless
  transmission line, and their leading hypothesis is unrelated to this one.
- **What becomes easier**: nothing in the testbench circuit or bounds changes,
  so no evidence record is invalidated and no bound moves. Any future `tie`
  abort investigation is pointed at the solver's conditioning of the DUT's
  supply row — on `cd57d203…`, an h-independent 197.8 µA excursion on a row
  carrying 4.8 nA — rather than at the DUT's logic, which is where DR-0029's
  Consequences pointed it and where #332 measured there is nothing to find.

## Spec lines affected

- [`DR-0029`](DR-0029-tie-loop-decision-chatter.md) — `Status` /
  `Superseded by` — **changed** (ratified and superseded by this record in
  PR #413; back-pointer is now in force). Its Context, Decision, Alternatives
  considered and Consequences are left exactly as written, per `README.md`'s
  append-only rule.
- [`DR-0008`](DR-0008-sar-logic-synchronous.md) — the near-metastable
  consequence ("corrupts at most one bit and cannot stall the conversion";
  "drdy keeps arriving every 16 clocks even with the comparator pinned on an
  exact tie") — **clarified (no value change)**, and **not** superseded. It is
  substantiated at 29 of 45 points on `cd57d203…` (`20260920-020802-2043286`)
  and at 39 of 45 points on current deck `2a6bfef4…`
  (`20261117-094722-0185db3`, supplemented at `sf_27c_2.97v` by PASS record
  `20261125-193834-c361768`), and contradicted at none. An ngspice
  non-convergence is not the conversion stalling: it is the matrix failing to
  produce a transient, which is why item 5 prices it as hash-bound coverage
  and not as a counterexample.
- [`DR-0031`](DR-0031-power-up-first-conversion-validity.md) — mechanism B and
  part 2 — **clarified (no value change)**; #337 extended its reach to the
  `tie` deck's own corners, and its part 2 was executed in #327 (commit
  `60336f22`). Note that DR-0031 itself remains `Status: proposed` and is not
  ratified by this record.
- `sim/sar-logic-timing-gates-tie/testbench/tb.json` — `claim`,
  `tie_code_deviation`, `tie_conv_period_ns` — **unchanged** (no relaxation;
  listed so the record is explicit that it moves none of them). Its `Note`
  text still carries DR-0029's superseded "~1e-7 V … the solver's own noise
  floor" characterisation; correcting it is gated on this record's
  ratification and is **not** in PR #413's scope — tracked in **#363 Part B**.
- `design/sar-logic/rtl/README.md` (the `#322` and `#303 (continued)` entries
  of *Verification performed*) — **unchanged**, same gating (#363 Part B;
  Part A merged in PR #374).
- `sim/sar-logic-timing-gates-tie/records/20260920-020802-2043286.md` and
  `sim/sar-logic-timing-gates-tie/records/20261117-094722-0185db3.md` — **not
  touched**: `sim/` records are append-only (`sim/README.md`), and a
  timestamped measurement stays true regardless of what supersedes the record
  that interprets it. `sim/sar-logic-timing-gates-tie/records/20261125-193834-c361768.md`
  is added as append-only subset evidence for `sf_27c_2.97v` on `2a6bfef4…`.
- `README.md#target-specification` — none. This record changes no target
  specification row.
