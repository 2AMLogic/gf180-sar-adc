# sim/ — evidence record format

This directory holds simulation testbenches and their results. Results are
**append-only evidence**: once a record is written, it is never edited or
deleted. A re-run — even one that corrects a mistake — mints a new record
with a new ID; a correction references the record it supersedes rather than
overwriting it in place.

This convention exists because CLAUDE.md commits this repo to two rules that
need a concrete schema to be enforceable:

- **Verification is the product.** No claim without a testbench. PVT
  corners on every recorded result (see "Corner matrix run" below).
- **`sim/` results are append-only evidence.** Re-runs get new records;
  records are never edited or deleted.

## Provenance: ported from gf180-bandgap

Per CLAUDE.md ("bootstrap from the sim-harness pattern... once it lands"),
this format is **ported from `2AMLogic/gf180-bandgap`'s `sim/README.md`**
rather than designed from scratch. The directory/naming convention,
record-id and corner-id schemes, and the base summary-record schema are kept
identical to upstream. Divergences exist only where an ADC-specific need
requires them; each is called out at the point it occurs, and summarized
here:

1. **Corner matrix is not fixed to a specific PVT list.** Upstream's
   bandgap `CLAUDE.md` states an explicit matrix (−40/27/125 °C, ±10%
   supply, process corners) that its README quotes directly. This repo's
   `CLAUDE.md` states the *rule* ("PVT corners on every recorded result")
   without a repo-wide fixed matrix — the actual corner list is pinned by
   the ratified spec (#1) and produced by the corner runner (#2), neither of
   which exists yet. The "Corner matrix run" field below is therefore
   normative on *what a record must state*, not on a specific numeric list.
2. **Five ADC-specific field groups added**: dynamic-test (FFT) metadata,
   a linearity methodology field, an extended Monte Carlo convention (seed +
   mismatch scope), a noise methodology field, and a characterization
   record variant. None of these exist upstream — the bandgap block has no
   analog-to-digital conversion, code density, or coherent-sampling
   concerns. See "ADC-specific extensions" below.
3. Everything else (directory layout, `<record-id>` / `<corner-id>` schemes,
   the base summary-record field list, the append-only rule, and the
   extracted-vs-schematic / `Supersedes` semantics) is unchanged from
   upstream, so that #2 (this repo's corner runner, bootstrapped from the
   same upstream repo) does not have to reconcile gratuitous drift.

## Directory / naming convention

Each testbench topic gets its own experiment directory:

```
sim/
  <experiment-slug>/                 # e.g. inl-dnl, enob-fft, comparator-noise,
                                      # mc-cdac-mismatch, device-characterization
    testbench/                       # testbench netlist(s) / xschem export used
    netlist-snapshots/
      <record-id>.spice              # frozen DUT netlist used for this record
    corners/
      <record-id>/
        <corner-id>.log              # raw ngspice output per PVT point
                                      # e.g. ss_-40c_2.97v.log
    records/
      <record-id>.md                 # append-only summary record
```

- **`<experiment-slug>`** — short, descriptive, kebab-case name for what is
  being verified (`inl-dnl`, `enob-fft`, `comparator-noise`,
  `mc-cdac-mismatch`, `device-characterization`, ...). One directory per
  distinct claim being tested, not per run.
- **`<record-id>`** — unique and traceable:
  `<YYYYMMDD>-<HHMMSS>-<short-git-sha>` (e.g. `20260730-143000-9f2a1cd`).
  Re-runs simply mint a new `<record-id>`; nothing under `records/` is ever
  edited in place. The same `<record-id>` ties together the netlist
  snapshot, the raw per-corner logs, and the summary record for one run.
- **`<corner-id>`** — `<process-corner>_<temp>c_<supply>v.log`, e.g.
  `ss_-40c_2.97v.log`, `tt_27c_3.30v.log`, `ff_125c_3.63v.log`.
- **`testbench/`** is not versioned per record — it holds the current
  testbench netlist(s)/xschem export(s) used to generate records. If the
  testbench itself changes in a way that could affect comparability across
  records, note that in the new record's summary (e.g. under Claim or a
  free-text note).

## Summary record format

Each run produces one `records/<record-id>.md` file. All records carry the
base fields below; records substantiating specific kinds of claims (dynamic
test, linearity, Monte Carlo, noise, characterization) also carry the
matching ADC-specific extension fields.

### Base fields (ported from upstream, unchanged)

- **Record ID** — the `<record-id>` for this run (matches the filename and
  the corresponding `netlist-snapshots/` / `corners/` subdirectory).
- **Claim** — which spec parameter/line this record substantiates (reference
  the ratified spec, e.g. `spec/<file>.md#<anchor>`, once ratified specs
  exist — see #1).
- **Netlist provenance** — `schematic` (`design/...`) or `extracted`
  (post-layout, `layout/...`). Required so post-layout re-runs are
  distinguishable from the original schematic-level record.
- **Corner matrix run** — explicit list of (process corner, temperature,
  supply) points actually executed. Must be the full PVT matrix pinned by
  the ratified spec (#1) / produced by the corner runner (#2) unless the
  record states why a subset was used (see "Subset-corner justification"
  below).
- **Statistical convention** (when applicable, e.g. Monte Carlo mismatch
  analysis) — see the Monte Carlo extension below for the ADC-specific
  fields this carries in addition to upstream's base N-samples-and-sigma.
- **Result** — per-corner pass/fail, plus an overall pass/fail against the
  ratified spec value. (Characterization records use "Measured value(s)"
  instead — see the Characterization-record variant below.)
- **Links** — paths to the testbench file(s), the frozen netlist snapshot,
  and the raw per-corner logs used to produce this record.
- **Timestamp / author** — when the record was created and who (human or
  agent) created it.
- **Supersedes** (optional) — the prior `<record-id>` this record
  supersedes, for corrections or for a post-layout extracted re-run that
  reports a schematic-vs-extracted delta against the schematic-level
  record. Mirrors the status/supersession language used for `spec/`
  decision records (see #6), so both conventions read as one house style.

#### Subset-corner justification

A record may legitimately run fewer than the full PVT matrix (e.g. a
Monte Carlo mismatch distribution evaluated at nominal PVT only, or a
behaviorally-accelerated linearity sweep run at a reduced corner set to
bound simulation time). This is allowed, but the record's "Corner matrix
run" field must **state which corners were run and why the rest were
omitted** — an unexplained subset is not a valid record.

#### Correction-supersession vs distinct-claim distinction

`Supersedes` is only for records that **replace** a prior result for the
*same claim* (a correction, or a schematic → extracted re-run of the same
claim). A new record that tests a **different** claim about the same DUT
(e.g. a Monte Carlo distribution check following a corner-matrix pass/fail
check on the same parameter) is not a correction and must leave
`Supersedes` empty — see the two base worked-example records below, which
illustrate exactly this distinction.

### ADC-specific extensions

These fields have no upstream equivalent; each is required only on records
substantiating the corresponding kind of claim.

- **Dynamic-test (FFT) metadata** — required on any record substantiating an
  FFT-derived claim (ENOB, SNDR, SFDR, THD, ...):
  - **N samples** — FFT record length.
  - **Input frequency / coherent bin** — analog input frequency and the
    integer FFT bin it lands on under coherent sampling
    (`f_in = bin * f_s / N`, with `bin` coprime to `N`).
  - **Window** — `none` for coherent sampling (the default and preferred
    method); otherwise the windowing function name (e.g. `hann`,
    `blackman-harris`) and why coherent sampling was not used.
  - **Sampling rate** — `f_s` in Hz/MS/s.
- **Linearity methodology** — required on any INL/DNL record; states the
  code-set/method used, not left implied:
  - `full-1024-code-ramp` — every code exercised (exhaustive, most
    expensive).
  - `reduced-code-set-major-carry` — a reduced set concentrated at
    major-carry transitions (CDAC segment boundaries).
  - `code-density` — histogram/code-density method (e.g. sine-wave
    histogram) rather than a deterministic ramp.
  - `behavioral-accelerated` — a behaviorally-accelerated block substitutes
    for full transistor-level simulation on some portion of the codes;
    state which portion.
  - Free text after the tag should give the exact code count / transition
    list / acceleration method used.
- **Monte Carlo convention** — extends the base "Statistical convention"
  field. In addition to upstream's N samples and sigma level, a Monte Carlo
  record on this repo also states:
  - **Seed handling** — fixed seed value(s) used, or the seed-sweep policy
    (e.g. `seeds 1-500`, or ngspice's `.options seed=...` value(s)).
  - **Scope** — `mismatch-only` or `mismatch+process`, i.e. whether process
    (global) variation was included alongside device mismatch.
  - **Sigma level** — the sigma level the pass/fail criterion corresponds to
    (e.g. "±3σ within spec target").
- **Noise methodology** — required on any noise-budget record; states which
  method the claim rests on:
  - `transient-noise` — ngspice transient-noise analysis; must also state
    the **seed** and a **duration justification** (e.g. settling-time
    margin, noise-floor convergence check) so the run is reproducible and
    its length is defensible.
  - `ac-based` — an AC-noise-analysis-derived estimate (e.g. integrated
    output-referred noise from an `.noise` or `.ac` analysis with a stated
    integration bandwidth).
  - `both` — both methods were run and reported; state how they were
    reconciled (e.g. AC estimate as a bound, transient-noise as the
    reported claim).

### Characterization-record variant

A subset of records (e.g. device characterization, #4) report **measured
values under stated corner conditions** rather than pass/fail against a
ratified spec line — there may be no spec line yet, or the record's purpose
is to inform one. These records use the same base fields with two
modifications:

- **Result** is replaced by **Measured value(s)** — the measured
  quantity/quantities, each paired with the corner condition(s) it was
  measured at. No pass/fail verdict is required (though one may be added
  once a ratified spec line exists, via a later record referencing this one
  under Links).
- **Data provenance** (new, required) — where the measured value's inputs
  came from:
  - `model-card-monte-carlo` — derived from the gf180mcu PDK model card's
    Monte Carlo mismatch statistics.
  - `foundry-documentation` — taken from foundry-published device
    documentation/datasheets.
  - `literature-assumption-with-derating` — a literature-sourced assumption,
    with the derating applied and its rationale stated.
  - Free text after the tag should identify the specific source (model
    card revision, document title/section, or literature citation) and any
    derating factor applied.

## Extracted vs schematic semantics

Unchanged from upstream. **Netlist provenance** states `schematic` or
`extracted`; a post-layout extracted re-run of an existing claim lives in
the *same* experiment directory with its own `<record-id>`,
`Netlist provenance: extracted`, and a `Supersedes` field carrying a
schematic-vs-extracted delta summary in its Result (or Measured value(s))
section. The extracted record **appends alongside** the schematic record —
it never replaces or edits it; both remain readable as the evidence trail
CLAUDE.md requires.

## Append-only rule

`records/*.md` files are never edited or deleted after creation. A re-run or
a correction always creates a new record with a new `<record-id>`. If it
corrects or replaces a prior result, it references that prior record via
**Supersedes** rather than overwriting it. This applies even to typo fixes —
the append-only guarantee is what makes `sim/` usable as an evidence trail;
"fixing" an existing record in place would defeat that.

## Worked example

Directory layout for an INL/DNL linearity claim, followed by a Monte Carlo
mismatch re-check of a related claim on the same DUT (illustrating the
correction-supersession vs distinct-claim distinction):

```
sim/
  inl-dnl/
    testbench/
      tb_inl_dnl_ramp.spice
    netlist-snapshots/
      20260730-143000-9f2a1cd.spice
      20260731-101500-2b6e0f1.spice
    corners/
      20260730-143000-9f2a1cd/
        tt_27c_3.30v.log
        ss_-40c_2.97v.log
        ff_125c_3.63v.log
        ...
      20260731-101500-2b6e0f1/
        tt_27c_3.30v.log
        ...
    records/
      20260730-143000-9f2a1cd.md
      20260731-101500-2b6e0f1.md
```

`records/20260730-143000-9f2a1cd.md` (placeholder values — no ratified spec
values exist yet, see #1):

```markdown
# Record 20260730-143000-9f2a1cd

- **Record ID**: 20260730-143000-9f2a1cd
- **Claim**: `spec/adc.md#inl-dnl` — INL/DNL over the full code range,
  TBD LSB target (placeholder; ratified spec pending #1; draft target in
  README.md is < 1 LSB / stretch < 0.5 LSB)
- **Netlist provenance**: schematic (`design/sar_adc.sch`)
- **Corner matrix run**:
  - Process: tt, ss, ff
  - Temperature: −40 °C, 27 °C, 125 °C
  - Supply: 2.97 V, 3.30 V, 3.63 V (±10% of 3.3 V)
  - (9 corner points total; see testbench for exact point list — matrix
    pinned by ratified spec #1 / produced by corner runner #2, both
    pending, so this list is illustrative pending those)
- **Statistical convention**: N/A (corner-matrix claim, not a distribution
  claim)
- **Linearity methodology**: `full-1024-code-ramp` — all 1024 codes
  exercised via a monotonic ramp input (placeholder methodology; issue #13
  will confirm the production method)
- **Result**:
  - tt/27C/3.30V: PASS, max|INL| = 0.42 LSB, max|DNL| = 0.31 LSB
    (placeholder values)
  - ss/-40C/2.97V: PASS (placeholder value)
  - ff/125C/3.63V: PASS (placeholder value)
  - ... (remaining corners: PASS, placeholder values)
  - **Overall: PASS** (placeholder — pending ratified spec, #1)
- **Links**:
  - Testbench: `sim/inl-dnl/testbench/tb_inl_dnl_ramp.spice`
  - Netlist snapshot: `sim/inl-dnl/netlist-snapshots/20260730-143000-9f2a1cd.spice`
  - Raw logs: `sim/inl-dnl/corners/20260730-143000-9f2a1cd/`
- **Timestamp / author**: 2026-07-30T14:30:00Z, agent-builder
- **Supersedes**: (none — first record for this claim)
```

`records/20260731-101500-2b6e0f1.md` — a later Monte Carlo mismatch check of
CDAC-induced linearity spread on the same DUT (illustrates the Monte Carlo
extension fields; this is a distinct claim from the corner-matrix record
above, not a correction of it, so it does not use Supersedes):

```markdown
# Record 20260731-101500-2b6e0f1

- **Record ID**: 20260731-101500-2b6e0f1
- **Claim**: `spec/adc.md#inl-dnl-mismatch-spread` — INL/DNL spread under
  CDAC capacitor mismatch, untrimmed (placeholder; ratified spec pending
  #1)
- **Netlist provenance**: schematic (`design/sar_adc.sch`)
- **Corner matrix run**: nominal corner (tt/27C/3.30V) only — mismatch
  distribution is evaluated at nominal PVT; see Statistical convention and
  Subset-corner justification above
- **Statistical convention**: N = 500 Monte Carlo samples, ±3σ spread
  reported against the untrimmed spec target
  - **Seed handling**: seeds 1–500 (`.options seed=<n>`, one run per seed)
  - **Scope**: mismatch-only (process held at nominal `tt` corner)
- **Linearity methodology**: `reduced-code-set-major-carry` — mismatch
  spread evaluated at CDAC major-carry transitions only, not the full
  1024-code ramp, to keep the 500-sample sweep tractable (placeholder
  methodology)
- **Result**: ±3σ max|INL| and max|DNL| spread within untrimmed spec
  (placeholder value) — **Overall: PASS** (placeholder — pending ratified
  spec, #1)
- **Links**:
  - Testbench: `sim/inl-dnl/testbench/tb_inl_dnl_mc.spice`
  - Netlist snapshot: `sim/inl-dnl/netlist-snapshots/20260731-101500-2b6e0f1.spice`
  - Raw logs: `sim/inl-dnl/corners/20260731-101500-2b6e0f1/`
- **Timestamp / author**: 2026-07-31T10:15:00Z, agent-builder
- **Supersedes**: (none — distinct claim from 20260730-143000-9f2a1cd, not a
  correction of it)
```

A later post-layout extracted re-run of the original corner-matrix claim
would live under the same `inl-dnl/` experiment directory with its own
`<record-id>`, `Netlist provenance: extracted (layout/sar_adc.gds ->
extracted netlist)`, and a `Supersedes: 20260730-143000-9f2a1cd` field
carrying a schematic-vs-extracted delta summary in its Result section — see
#17.

The remaining ADC-specific field groups not shown in the two records above
follow the same pattern; each is a required addition to the base schema on
the record types below, not a separate document:

- A dynamic-test (ENOB/SNDR/SFDR/THD) record adds the **Dynamic-test (FFT)
  metadata** block (N samples, input frequency / coherent bin, window,
  sampling rate) alongside the base fields — see #13.
- A noise-budget record adds the **Noise methodology** field
  (`transient-noise` with seed/duration justification, `ac-based`, or
  `both`) — see #9.
- A device-characterization record (e.g. CDAC cap, switch, comparator
  input-pair characterization) uses the **Characterization-record variant**
  (Measured value(s) + Data provenance instead of Result) — see #4.
