# Investigation 20261020-issue-584: what the `bad` 45-point grid actually showed, and a costed single-point pilot plan

Not a `sim/run_corners.py` evidence record. **No simulation was run to produce
this document** — local or batch, paid or unpaid. Every number below is read
from files already committed under `sim/` or from source/issue text, and each
has a command in §8 that re-derives it. Nothing here is a PVT result and
nothing here is citable as a spec claim.

It corrects the *reading* of
`sim/sar-logic-timing-gates-bad/records/20261020-011850-edf81f4.md` (PR #582)
without editing it: that record, its raw logs, its klt reports and its
snapshots stay byte-identical (`git diff --stat` of this PR touches only this
file). Parent issue: #303 (`Part of #303`; this does not complete it). The
plan in §6 is **returned to #303 for method and budget approval and is not
launched**.

## Conclusion

1. **Five statements the #582 record makes or implies are wrong or
   unsupported.**
   - The three points the record reports as "`aerr_bad` produced no value
     because `options.save_mode` was `"netlist"`" are *the same three points
     whose raw logs show `Timestep too small` at `vvdd_gate#branch`*, at
     1.69847 µs, 2.0925 µs and 1.6983 µs (20 %, 24.6 % and 20 % of the
     ratified 8.5 µs). They are **aborts**, not retention errors.
     Retention is not shown to be the cause of anything (§2.3, §4).
   - The retention sentence is not specific to those three: **all 45**
     per-point diagnostics, including the 42 timeouts that have no data at all,
     carry the identical `save_mode` hint text (§2.3). It is boilerplate that
     klt appends to every `measurement` error under `save_mode: "netlist"`
     (§4.2), not a finding.
   - The record's toolchain-drift banner attributes the drift to the *run*.
     The report's own `worker_environment` says the **runner** simulated
     against open_pdks `c6d73a35…` — the *pinned* revision. `f6eeac7…` is what
     the **submitting client** resolved (`models_lib_sha256_scope: "client"`).
     The record's "runner PDK as reported by klt" line prints the client value.
     Which models the 45 points actually used is therefore not established by
     the record (§5.1).
   - "`ngspice` version unknown" is a harness parsing gap; two of the three
     reports carry `engine_version: "46"` (the third has `null`), and all
     three carry the full `ngspice-46` banner and end their logs with
     `ngspice-46 done` (§5.1).
   - Cost: the record's expectation that `bad` costs "about the same order as
     `ok`'s ~132 core-s per point" is **falsified** — 42 of 45 points ran
     ≥ 3400 s without finishing, ≥ 25× that figure (§2.4).
2. **No point completed; no point is a measurement.** The 3 aborted points
   have a partial row count (358 468 – 711 819) and no value. The 42 timeouts
   have no ngspice output at all (their `.log` is the 20-byte string the
   *client harness* writes, `TIMEOUT after 3400s`). The negative-control claim
   ("a late decision MUST corrupt the conversion", `min=0.9` LSB) remains
   **unverified**, exactly as #582 said; this document does not move it.
3. **The aborts are consistent with #343/#372's mechanism but are not proof of
   it for these corners** (§3). The `bad` deck has the topology #343 identified
   as lethal (ideal lossless line, matched 50 Ω termination, the DUT's bare
   `cmp` gate input on the termination node), the remedy #343 costed (R1/R1b)
   is **not landed**, and #343 never ran this deck. The three aborts name the
   same node (`vvdd_gate#branch`) and the same ngspice floor
   (`timestep = 6.25e-21`) as the 14 `lt`/`xl` aborts #343 explained. That is
   consistent with, not a measurement of, the same mechanism.
4. **The three aborted points imply a ~210 accepted-timepoint/s throughput**
   (207 – 223 rows per wall-second, §2.4), which puts the 3400 s cap at
   ≈ 7 × 10⁵ accepted timepoints — the same order as the 754 946 timepoints
   #343 measured for the first 1.5 µs of the `lt` deck. At that density the
   ratified 8.5 µs cannot fit in the fleet's 3600 s whole-job ceiling, and
   **raising 3400 s to 3600 s (or to the ceiling's 3480 s per-unit maximum)
   does not change the outcome** (§2.4, §6.4). This is an inference from three
   points under 15-way concurrency, flagged as such.
5. **What would discriminate the remaining hypotheses is cheap and specific**
   (§6): one diagnostic-window A/B on one known-abort corner
   (`sf`/27 °C/3.63 V), two single-unit jobs, hard-capped at 2 × 2520 s
   (≈ 1.4 instance-hours, about half of what the failed grid consumed). The
   ratified-window pilot (§6.5) is **gated on a decision that is not made
   here**: the unmodified deck is not expected to complete inside the fleet
   ceiling, and changing it needs a decision record.
6. **A generic klt gap is substantiated** (§4.2): the `save_mode` hint is
   attached to `measurement` errors even when the corner already has a
   `timeout` (or `timestep_too_small`) cause. Deduplicated against
   `2AMLogic/klayout-tools` and filed there, worded without reference to this
   design (link in §7).

---

## 1. Artifacts and identities everything below is read from

Base tree: `493959f0cd93d6b40d08db4e5affd9f150e34d85` (`origin/main` when this
was written). Paths are relative to the repository root.

| artifact | identity |
|---|---|
| record | `sim/sar-logic-timing-gates-bad/records/20261020-011850-edf81f4.md` |
| source deck | `sim/sar-logic-timing-gates-bad/testbench/tb_sar_logic_timing_gates_bad.spice`, sha256 `273f81083b21ef34d13b4ce3c0eb0d46e7598efe606567c98b6fc5be113c78ef` (equals the record's "Testbench netlist sha256") |
| manifest | `sim/sar-logic-timing-gates-bad/testbench/tb.json`, sha256 `9a0de0f31187429e970127eebc023f78be0f67175b3a698601437f54e8e7bf36` (equals the record's "Manifest sha256") |
| deck frozen at record time | `…/netlist-snapshots/20261020-011850-edf81f4.spice`; lines 5-end hash to `273f8108…` (the 4-line header is the snapshot's own) |
| bodies sent to klt | `…/netlist-snapshots/20261020-011850-edf81f4.batch-body.vdd{0-2p97v,1-3p3v,2-3p63v}.spice`, sha256 `bb8d7757…a77278c`, `d5f3a28f…9faf5a`, `8c08c6d1…c0e04` — each equals the `input.content_hash` in its `klt-report` |
| requests | `…/corners/20261020-011850-edf81f4/klt-request.vdd{0,1,2}-*.json`, sha256 `c06a162d…1024`, `fc7f5851…e731`, `44cc180e…a6b` — equal the record's "request sha256" |
| reports | `…/corners/20261020-011850-edf81f4/klt-report.vdd{0,1,2}-*.json`, `klt-set-report.json` |
| raw logs | `…/corners/20261020-011850-edf81f4/<corner-id>.log` (45) |
| last commit touching the `bad` testbench dir on `main` | `60336f22` (#371) — i.e. the deck on `main` today **is** the deck #582 ran |
| #343 investigation | `sim/sar-logic-timing-gates/investigations/20260922-issue-343-delay-line-abort-mechanism.md` |
| #303 audit of `lt`/`xl` | `sim/sar-logic-timing-gates/investigations/20260921-issue-303-delay-line-decks-abort-mid-transient.md` |
| klt source read | host install `klayout-tools 0.7.1.dev2226+gfda8dad261dc`, `klayout_tools/sim.py` sha256 `98e819ad…def1e`. **This is not the client build (`0.7.1.dev2222+gae4a88b4c3eb`) and not the runner build (`0.7.0`) that produced the #582 reports** — see §4.3 for what that limits. |

## 2. Audit of all 45 points

### 2.1 Taxonomy

The terms are used strictly. A point is exactly one of these:

| term | meaning | #582 count |
|---|---|---|
| **completed** | ngspice reached the ratified stop time (8.5 µs) and the measurement printed a value | **0** |
| **aborted** | ngspice itself ended the transient early with `Timestep too small` (a log line says so) | **3** |
| **timed out** | the harness/klt killed ngspice at `options.timeout_s`; no statement about where it was | **42** |
| **missing measurement** | the report has `value: null` — a *consequence* of any of the above, never a cause | 45 |
| **unverified attribution** | a stated cause with no observation that discriminates it from the alternatives | see §2.3, §3 |

A partial transient — the 3 aborted points have 358 468, 540 082 and 711 819
data rows — **is not a completed measurement** and is not counted as one.

### 2.2 The 3 aborted points

Re-derive with §8 command A. All three: `doAnalyses: TRAN:  Timestep too
small; … timestep = 6.25e-21: trouble with node "vvdd_gate#branch"`, followed
by `tran simulation(s) aborted`.

| corner-id | abort time | % of 8.5 µs | data rows at abort | klt `runtime_s` | rows / s | sim-ns / wall-s |
|---|---:|---:|---:|---:|---:|---:|
| `tt_-40c_3.63v` | 1.69847 µs | 20.0 % | 540 082 | 2607.043 | 207.2 | 0.651 |
| `fs_27c_3.30v` | 2.0925 µs | 24.6 % | 711 819 | 3189.864 | 223.2 | 0.656 |
| `sf_27c_3.63v` | 1.6983 µs | 20.0 % | 358 468 | 1718.062 | 208.6 | 0.988 |

All three aborted *before* the 3400 s cap; they are the only three points in
the grid whose `runtime_s` is below 3400. None names a comparator source node
(`bbadcmp`); the trouble node is the supply-source branch in every case.

No klt diagnostic names the abort. The report's `diagnostics` for each is the
single `measurement` entry (§2.3). The abort is visible only in the raw log.

### 2.3 The 42 timeouts, and what the record's three "errors" really are

- 42 `<corner>.log` files contain exactly `TIMEOUT after 3400s\n` (20 bytes).
  That text is written by the **client harness**
  (`sim/harness/batch.py:723`), not by ngspice. There is **no ngspice output**
  for any timed-out point: no time reached, no row count, no abort/no-abort.
  *The 42 timeouts say nothing about whether those points would have aborted,
  completed or run on.*
- The reports carry `timeout` in 42 corners (15 + 14 + 13 across the three
  requests) and a `measurement` diagnostic in **all 45**. The three corners
  without a `timeout` diagnostic are exactly the three aborts of §2.2.
- Every one of the 45 `measurement` diagnostics has the identical message
  ending `options.save_mode is "netlist", so klt emitted no `save all` …`.
  For the 42 timeouts that sentence cannot be a diagnosis (no data existed
  under any retention setting). For the 3 aborts it is not a diagnosis either
  (§4).
- The record's `Result` table reads those three rows as retention errors
  because the harness scores a klt `error` corner with no values as an error
  carrying klt's first diagnostic text (`sim/harness/batch.py:742`), and the
  abort scan `runner.analysis_aborted` that would have named the abort
  (`batch.py:766`) sits **after** that early return. For these three corners
  the scan does flag the abort when applied to the logs (§8 command A). So the
  harness had the information and ordered the checks so that it was never
  consulted for error corners — the #341 misclassification in the opposite
  direction (there, aborts were scored as passes; here, aborts are reported as
  a different, unsupported cause).

### 2.4 Cost, and what the record's cost note got wrong

- The #582 grid consumed three jobs of 3411, 3413 and 3413 s
  (`environment.remote.elapsed_seconds`), on three `c7i.8xlarge` Spot
  instances: **10 237 job-seconds = 2.84 instance-hours** of the fleet. The
  record's wall-time line (3471.05 s) is the client's elapsed time. **No price
  is recorded anywhere in this repository**, so the dollar cost is not stated;
  §6.3 handles that explicitly.
- Each request was submitted as **one job holding all 15 units** (3 PVT
  temperature × 5 process points) on one `c7i.8xlarge` (16 physical cores). The
  job finished 11 – 13 s after the 3400 s cap (`elapsed_seconds` 3411 / 3413 /
  3413) while 13 – 15 of its units each ran the full 3400 s, so the units
  necessarily **overlapped in time — up to 15-way** — which is also what klt
  warned about before launch: every report's `environment.remote.job_ceiling`
  has `exceeds_ceiling: true`, `check: "warn"`, `job_bound_s: 51120`, and the
  advice "Set request.remote.hosts to at least 15 to run one job per shard of
  at most 1 units". The 207 – 223 rows/s above are therefore rates **under up to
  15-way concurrency**, not isolated-loop rates. (The same block's
  `concurrency: "2"` field is unexplained by anything in the report and is not
  relied on.) An isolated rate has never been measured for this deck.
- The record's note ("expected to cost about the same order as `ok`'s measured
  ~132 core-s per point") is **contradicted**: 42/45 points exceeded 3400 s
  (≥ 25.8 × 132 s) and none finished.
- Linear extrapolation of the three aborted points' sim-ns per wall-s to
  8.5 µs gives 8 599 – 13 047 s (2.5 – 3.8 × the cap). That is a *floor*, not an
  estimate: #343 measured the accepted timestep still **falling** (61 × over
  1.4 µs, no floor in sight) for the `lt` deck, so a constant rate is the
  optimistic case. Nothing here supports "the cap is merely a bit too small".
- Cross-check: ≈ 7.1 × 10⁵ rows (3400 s × ~210 rows/s) is the same order as the
  754 946 accepted timepoints #343 measured to cover only the first 1.5 µs of
  the `lt` deck's committed topology. Different decks, different delays, a
  different instrument generation — a consistency check on the mechanism, not
  a cost model.

### 2.5 What is and is not established about attribution

| claim | status |
|---|---|
| the 3 "retention errors" are aborts | **established** (logs) |
| `save_mode` retention caused any of the 45 outcomes | **not established**; contradicted for the 42 (no data to retain) and unsupported for the 3 |
| the aborts have the #343 mechanism | **unverified** — same topology/node/floor; no probe of this deck |
| the 42 timeouts are the same trajectory as the aborts | **unverified inference** (#343 argued this for `lt`; no log from any of these 42) |
| the toolchain drift in the banner changed these numbers | **unestablished in both directions** (§5.1) |

## 3. Reconciliation with #343 / PR #372

### 3.1 What #343 found, what it costed, what it did not do

(Verbatim sources: its §Conclusion, §5 and §7.) The mechanism is the *pairing*
of the ideal lossless `tltd`/`txld` line, matched into a 50 Ω resistor on the
termination node, with the DUT's bare standard-cell `cmp` input hung on that
same node; moving the gate behind #296's `1 kΩ`/`100 fF` network (arm B,
the line untouched) cut accepted timepoints 46 × (754 946 → 16 282) and gave
a flat median step. The remedy table (R1 `cmp_out_rc`; R1b R1 with `td`
reduced by the RC's 69 ps; R2 lumped line; R3 lossy line, unmeasured; R4 raise
the cap — "converts timeouts into aborts, not into results") is **costed and
not landed**; it needs a decision record because it changes what
`abs_err_delay_*` measures.

Its stated limitations, restated because they bound what may be borrowed:

- Single corner for the full A/B (`lt`, `ss`/27 °C/2.97 V); one extra corner
  and one extra deck (`xl`) for the decisive arm only.
- **It did not reproduce the abort**: arm A "completed" 1.5 µs where the grid
  point aborted at 1.28656 µs. The conclusion rests on the step-size trajectory.
- **The `bad` deck was not run at all**; "applies by construction" is an
  inference from the netlist.
- Every arm ran on the pre-#371 deck family, at open_pdks `c6d73a35…`, on a
  host capped to one core; no wall-clock is comparable to a record.

### 3.2 Topology identity: #343's decks vs the `bad` deck #582 ran vs `main` today

| | #343 arm A (`lt`, pre-#371) | `bad`, #582 | `bad`, `main` @ `493959f0` |
|---|---|---|---|
| comparator → line | `bltcmp → tltd(z0=50, td=40n)` | `bbadcmp bad_cmpi 0 V = … ; tbadd bad_cmpi 0 bad_cmpo 0 z0=50 td=70n` (deck line 83) | identical |
| termination | `rltterm` 50 Ω | `rbadterm bad_cmpo 0 50` (line 84) | identical |
| DUT `cmp` port | on the termination node | `xbad … bad_cmpo …` (line 48): **on `bad_cmpo`, the termination node** | identical |
| #296 `1 kΩ/100 fF` network ahead of the gate | **no** (arm B adds it) | **no** | **no** |
| deck sha256 | `ad6b8bd6…cc9e` (old instrument) | `273f8108…78ef` | `273f8108…78ef` (unchanged since `60336f22`) |
| remedy R1/R1b landed | — | no | **no** (no commit after `60336f22` touches the dir) |

So the `bad` deck has precisely the structure #343 identified as lethal and
precisely none of the structure that arm B showed fixes it. That is the
strength of the inference, and also its limit: it is structural.

### 3.3 What may and may not be carried over

- **May be cited**: the mechanism as the leading, topologically-supported
  hypothesis; the R1/R1b cost table; "R4 is not a remedy".
- **May not be cited**: #343's numbers as measurements of `bad`; #343's
  conclusion as a diagnosis of the 3 aborted corners (it did not run `bad`,
  did not reproduce an abort, and measured at `c6d73a35…`, 1 core, pre-#371).
- **Contradiction to carry, not paper over**: #343 states its own
  `tb.json` quoted sentence ("#296's fix does NOT apply to this loop") is
  falsified in its second clause. `sim/sar-logic-timing-gates-bad/testbench/tb.json`
  on `main` **still contains that sentence** (it is in the manifest `evidence.notes`
  and is copied verbatim into the #582 record). This document does not edit
  either; the correction belongs to the decision record #343 §5 says is
  needed.

### 3.4 #341

#341's fix (`e61fa8d`, `runner.analysis_aborted`) lives in the **local**
runner path. The batch path (`sim/harness/batch.py`) calls the same function,
but only after the error-corner early return (§2.3), so for any corner klt
grades `error` with no values the scan is unreachable. The local-harness fix
therefore does **not** cover the present klt/batch path for error corners. The
three #582 aborts are the live example. (Whether to reorder is a code change;
see §7.)

## 4. Requested vs effective retention and error classification

### 4.1 Requested

`sim/harness/batch.py:372` sets `options.save_mode = "netlist"` iff
`save_measured` (the `--save-measured-vectors` flag; `cli.py:189`, rationale
there: the five-loop deck "grows ~4.6 MB of resident set per simulated ns").
All three #582 requests carry `"save_mode": "netlist"`, `"timeout_s": 3400`,
`"keep_artifacts": true`, `ngspice_init = ["set numdgt=10","set num_threads=1"]`
and the measurement `.meas tran aerr_bad MAX v(bad_aerr) FROM=1.5u`.

The generated body contains **`.save v(bad_aerr)`** (the line after the
`mim_cap` aliases in every `batch-body` snapshot; the frozen deck has no
`.save` of its own, `grep -n save` finds none). So the one vector the single
measurement reads was explicitly requested to be retained. The hint's premise
("only the vectors the netlist's own `.save` cards retain were available: add
every signal this measurement reads") is **already satisfied** by this
deck for this measurement.

### 4.2 Effective — what the klt source does (host build `dev2226`)

Read in `klayout_tools/sim.py`:

- `_no_value_message` (≈ L10600-10640) appends
  `SAVE_MODE_NETLIST_NO_VALUE_HINT` to **every** "produced no value"
  diagnostic whenever `save_mode == "netlist"`, with no check of why the value
  is missing.
- `_run_corner` (≈ L9395-9560) records `timeout` when `subprocess.TimeoutExpired`
  fires, classifies the log with `_classify_diagnostics`, and then
  `_demote_abort_cascade(measurement_diagnostics, engine_aborted or
  analysis_never_started)` drops the per-measurement errors **only** for an
  `engine_aborted` or a deck-parse abort (#3067/#3879). A `timeout`, or a
  mid-transient `timestep_too_small` (its own code since #2918), does not
  trigger the demotion — so the cascade of `measurement` errors, each with the
  retention hint, remains alongside the real cause.
- `timestep_too_small` exists in this build as a first-class diagnostic with
  time and node (#2918, closed 2026-10-15). **None of the #582 reports contains
  it**, for any of the 3 corners that demonstrably log `Timestep too small`.
  Likewise #3921 (progress-at-timeout) is not reflected in the 42 timeout
  messages (`ngspice did not complete within 3400s, killed`, no time reached).

Reading: the retention sentence is a *hint*, emitted unconditionally under one
option, and the report that carried it came from a build that predates (or does
not apply) at least the abort classification. **Error precedence** in the
shipped report is: `measurement` (all 45) > `timeout` (42) > nothing about the
abort (3). The abort appears only in the raw log.

### 4.3 What this does and does not establish

- It does **not** establish where the 3 `.meas` values went. Open observation:
  a local-harness `lt` abort log (`sim/sar-logic-timing-gates-lt/corners/
  20260920-182006-2422cac/ff_125c_3.30v.log`, line 14118) shows ngspice
  *printing* `aerr_lt = 0.00000e+00 at= 1.56238e-06` from truncated data
  immediately before the abort line — the exact behaviour `runner.analysis_aborted`'s
  docstring describes. The three `bad` logs contain **no** `aerr_bad =` line.
  Candidate explanations — `.meas` not evaluated under the klt/`save_mode`
  path; the line printed to a stream the runner does not capture into the
  copied log; ngspice behaviour differing with the restricted save set; a
  runner-version difference — are all untested. **The retention hypothesis is
  one of four, and the only one #582's record stated.** §6 A/B discriminates
  it directly.
- The host klt source is `dev2226`; the reports came from client `dev2222` +
  runner `0.7.0`, whose reported `runner_compatibility` was `match`.
  `match` is a version-string comparison; it is not feature parity (cf.
  `2AMLogic/klayout-tools#3676`, open: "runner image predates … live parity
  unmeasured"; `#2851` closure — publish runner identity / reject
  incompatible clients — "proves neither live toolchain parity nor correct
  vector retention/error precedence", as #584 says, and this trace agrees:
  the missing `timestep_too_small` diagnostic is direct evidence of a
  client/runner behavioural gap under a `match`).
- `keep_artifacts: true` was set, and each report lists `artifacts.deck`
  (`…/klt/out/vdd*/<corner>/corner.cir`) and `artifacts.log`. The `corner.cir`
  files were copied to a `sim/.work/…` directory that is not committed and no
  longer exists, so **the exact deck klt handed to ngspice (where `.save` and
  `.meas` landed relative to each other) is not preserved**. A future run
  must commit it (§6.6).

### 4.4 Findings, in the order a reader should weigh them

| id | finding | evidence | generic? |
|---|---|---|---|
| F1 | 3 "retention" errors are aborts | §2.2, logs | no |
| F2 | retention hint appended to 45/45 no-value errors, incl. 42 with no data | reports; `sim.py` ≈ L10624 | **yes** → filed (§7) |
| F3 | abort not classified in the shipped reports although the host build can | reports vs `sim.py` ≈ L945-964 | runner-image currency, tracked by #3676 |
| F4 | harness scores klt `error` corners before the abort scan | `batch.py:742` vs `:766` | no (this repo) → §7 |
| F5 | where `aerr_bad` went on abort is unobserved | §4.3 | resolved only by §6 |
| F6 | the klt-generated deck (`corner.cir`) is not retained as evidence | §4.3 | no (harness artifact policy) |

## 5. Toolchain

### 5.1 Historical drifted evidence, as recorded

What the #582 reports say about the environment, which the record's banner and
"Environment" section do not fully reflect:

| fact | where | note |
|---|---|---|
| client resolved open_pdks `f6eeac7…` (`~/.ciel`), `ambiguous_sources: ["search root: ~/.volare"]` | `provenance.pdk` in each report | the shadowing hazard of `gf180-comparator#288` (see #513) |
| client `models_lib_sha256` `f6f4a96e…94a24`, `scope: "client"` | `environment.models_lib_sha256` | client file, not the runner's |
| **runner** `pdk.stamp_text` = `open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b`, `root: /opt/pdk`, `models_staged: false` | `environment.remote.worker_environment.pdk` | the **pinned** revision |
| `pdk_stamp_comparison`: `not_comparable`, `client_stamp_unavailable` | same | klt did not compare the two |
| engine `ngspice-46`; client banner `Creation Date: Sat Aug 1 …`, runner `Thu Oct 1 …` → `engine_build_comparison: mismatch` | `environment`, `worker_environment` | build date differs |
| `engine_version: "46"` (`null` in the `vdd0-2p97v` report; banner present in all three) | `environment` | the record's "found `unknown`" is a harness parse gap |
| runner klt `0.7.0` vs client `0.7.1.dev2222+gae4a88b4c3eb`: `runner_compatibility: "match"` | `environment.remote` | version-string `match` |

Consequence: the drift banner ("the device models, and therefore every
measured value, differ from the pinned ones") is true of the **client's**
resolution. For the simulation itself the report points the other way (runner
= pinned revision) — but it also shows klt could not compare the stamps, so
**neither reading is established**. The earlier `sim/adc-inl-dnl` batch record
(`20261015-001125-74685b3`) shows the same runner stamp `c6d73a35…`, so this is
a property of the runner image, not of one run. This is a *historical*,
*non-comparable-with-pinned* record in the sense #303's operator ruling uses,
and nothing here relaxes that.

### 5.2 Supported toolchain going forward (#513 / #514 / #515)

Policy is not decided here; it is owned by #513 (parent, `loom:blocked`),
#514 (`loom:building`, PR #517 open, merge state `CLEAN`) and #515
(`loom:blocked`, requalification of reference records). Stated as the
dependency this plan has on them:

- **Forward pin**: open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` via
  ciel 2.6.1, with `~/.ciel` searched before `~/.volare` and a pin-vs-resolved
  mismatch made a failure (#514 AC 5). `sim/toolchain.json` on `main` still
  holds `c6d73a35…` until #517 lands.
- **Not a pilot-launch condition**: #515 (requalifying the *other* reference
  records). A `bad` pilot does not depend on those.
- **A qualified run** (as distinct from #582) = a run whose record carries no
  drift banner because the **client-resolved**, **runner-reported** and
  **`sim/toolchain.json`** revisions are all the same value, with the
  receipts of §6.2 attached. Absent all of those, any pilot output is
  diagnostic-only and must say so.

## 6. One concrete single-point pilot plan (NOT launched)

### 6.0 Shape

The question is not "does the grid pass" but "what does ONE `bad` point do,
and why". Two stages, the second **gated on a decision this document does not
make**:

- **Stage D (diagnostic, shortened window — never evidence).** One corner, two
  single-unit jobs differing in exactly one request field (`save_mode`).
  Window deliberately shortened to `1.8 µs`. Its outputs go under
  `investigations/`, never `records/`, and are labelled non-comparable to the
  ratified window.
- **Stage R (ratified window, unchanged `tran 5n 8.5u 0 5n`).** One nominal
  point. **Not launchable until the unmodified-deck viability question is
  answered by Stage D and the remedy/capability question of §6.5 is
  decided.**

### 6.1 Chosen corner and rationale

- **Stage D: `sf` / 27 °C / 3.63 V.** It is the *cheapest* of the three known
  verdict-bearing points (abort at 1.6983 µs after 1718 s, 358 468 rows) and
  has a recorded outcome to compare against, so reproducing or failing to
  reproduce it is itself the discriminating observation. It is a skewed corner
  on purpose: determinism/toolchain sensitivity is read off a case with a known
  answer, not a nominal one with none. 1.8 µs is 6 % past the recorded abort,
  and keeps `FROM=1.5u` of the measurement inside the window (1.5 – 1.8 µs).
- **Stage R: `tt` / 27 °C / 3.30 V** (nominal). This is the corner at which
  `ok`'s ~132 core-s was measured, so the first completed number is directly
  comparable to the only measured isolated-loop cost in the tree. It is **not**
  a known-abort corner and has no recorded outcome (it timed out in #582).
  Choosing it is a judgement; the approver may substitute.

### 6.2 Exact inputs, hashes and commands (Stage D)

Inputs are all committed; nothing is regenerated.

| input | identity |
|---|---|
| netlist body | `…/netlist-snapshots/20261020-011850-edf81f4.batch-body.vdd2-3p63v.spice`, sha256 `8c08c6d16ea734147c2794a935d237f89d9e23fa54e18156b648726cfbcc0e04` (staged under the request's expected name `vdd2-3p63v.spice`) |
| base request | `…/corners/20261020-011850-edf81f4/klt-request.vdd2-3p63v.json`, sha256 `44cc180ebf065c12266b5d88f240f2e29b530b8977af382b7462bf9f6e014a6b` |
| arm A request (`save_mode: "netlist"`, as #582) | base request with only: `corners.process` = `[sf]`, `corners.temperature_c` = `[27.0]`, `analysis.args` = `"5n 1.8u 0 5n"`, `options.timeout_s` = `2400`; serialized `json.dumps(indent=2, sort_keys=True)+"\n"`; sha256 `a6df36bd1aa02e673b0d2998ed56a6e8014f1c30158c8a7813e2941ab9f4ebec` |
| arm B request (`save_mode` omitted ⇒ klt default `"all"`) | arm A with `options.save_mode` deleted; sha256 `4b18935b8d16b4152478a3265ab18387bb99fe00b920ebb39b3be15cc5414f1a` |
| deck, models, solver options | unchanged: `273f8108…` source, `set num_threads=1`, `set numdgt=10`. `num_threads` is held at 1 deliberately: the harness's own documentation (`cli.py`, `--ngspice-threads`) records that the accepted-timestep *sequence* is not invariant to it on gate-level decks, so a different value would invalidate the comparison to the recorded abort time. |

Derivation of both request files from the committed base (reproducible,
no network):

```bash
python3 -I - <<'EOF'
import json, hashlib
base = json.load(open("sim/sar-logic-timing-gates-bad/corners/20261020-011850-edf81f4/klt-request.vdd2-3p63v.json"))
dump = lambda x: json.dumps(x, indent=2, sort_keys=True) + "\n"
assert dump(base) == open("sim/sar-logic-timing-gates-bad/corners/20261020-011850-edf81f4/klt-request.vdd2-3p63v.json").read()
for tag, drop in (("A-save-netlist", False), ("B-save-all", True)):
    q = json.loads(json.dumps(base))
    q["corners"]["process"] = [p for p in q["corners"]["process"] if p["name"] == "sf"]
    q["corners"]["temperature_c"] = [27.0]
    q["analysis"]["args"] = "5n 1.8u 0 5n"
    q["options"]["timeout_s"] = 2400
    if drop:
        del q["options"]["save_mode"]
    print(tag, hashlib.sha256(dump(q).encode()).hexdigest())
EOF
```

Launch (the executor, **after approval and after the receipts below pass**;
the dispatch host only submits and collects — no `ngspice` runs here):

```bash
# 0. validate, touches no compute / S3 / EC2:
klt sim --dry-run --backend batch <A.json> ; klt sim --dry-run --backend batch <B.json>
# 1. submit both as separate single-unit jobs, never more than 2 in flight, no capacity retries:
klt sim --batch-set <A.json> <B.json> --max-in-flight 2 --capacity-retries 0 \
        --report-out <outdir>/set-report.json -o <outdir> --format json
# (--backend batch is implied by --batch-set; there is no local fallback.)
```

Receipts that must be on file before step 1 (a missing one = do not launch):

1. `sim/toolchain.json` pin (post-#517) = client-resolved open_pdks = the
   runner's `worker_environment.pdk.stamp_text`, and
   `pdk_stamp_comparison.status == "match"` (not `not_comparable`). Obtained
   from a **read-only** receipt, not a simulation: the expected form is the
   worker environment block of any prior fleet report from the rolled-out
   image; if none exists post-rollout, a one-unit trivial-deck canary is a
   separate, separately-approved ask and is not part of this plan.
2. Runner klt identity and feature level: `runner_klt_version` and a
   statement from the fleet owner (2AMLogic/2am) that the image includes
   klayout-tools#2918 (`timestep_too_small`) and #3921 (progress-at-timeout).
   A `match` string is not accepted as this receipt (§4.3).
3. `--dry-run` output for both requests, committed with the plan.
4. The approval record on #303 (§6.7).

### 6.3 Caps (resource, wall-clock, dollar) and how each was derived

| cap | value | derivation |
|---|---|---|
| units | 2 (1 per job) | one A/B pair; no grid |
| per-unit kill | `options.timeout_s` = **2400 s** | #582's slowest observed route to a verdict at this corner was 1718 s under **15-way** concurrency; this runs 1 unit/job, so 2400 s is ≈ 1.4 × the contended figure, a cap and not a prediction |
| per-job bound | 2400 + 120 s overhead = **2520 s** | klt's own `job_ceiling` formula (`per_unit_timeout × units + overhead`, `overhead_s: 120`), observed in `sim/adc-inl-dnl` and #582 reports; well under the fleet's 3600 s whole-job ceiling (`max_job_seconds_source: fleet_config`) |
| total worst case | **5040 job-seconds = 1.40 instance-hours** | 2 jobs × 2520 s; 49 % of the 2.84 instance-hours #582 consumed |
| concurrency | 2 jobs, 2 instances, 1 ngspice thread each | removes the 15-way contention of #582 so the isolated rate is observable for the first time |
| dollars | **not stated by this document.** Cap = *instance-hours above* × the then-current `c7i.8xlarge` Spot rate in the fleet's billing for `us-east-1`. The rate is not recorded in this repository and is not guessed here. The approver converts 1.40 instance-hours to dollars and writes the figure on #303; the executor refuses to launch without that figure. | |

Stage D cannot spend more than the table's worst case; there are no retries
(§6.4).

### 6.4 Stop conditions, retries, recovery

- **Hard stops (no re-submission, no cap raise, no "one more try")**: either
  unit reaches `timeout_s` (record as `timeout`; the *information* is "isolated
  `sf` unit did not reach 1.8 µs in 2400 s", which is itself the answer to
  whether the cap or the deck is the limit); a job ends `failed` or
  `batch_job_timeout`; a fleet capacity refusal (do not wait/retry: report it);
  any receipt of §6.2 fails; spend would exceed the approved figure.
- **No retries of any kind.** `--capacity-retries 0`; a failed submit is
  reported on #303 and the issue/PR, not repeated, and **never** falls back to
  a local grid (host rule; `--batch-set` has no local backend).
- **Not stop conditions, deliberately**: the abort itself. An abort is a
  successful observation of the hypothesis under test.
- **Raising 3400 → 3600 s is not a path.** The fleet's whole-job ceiling is
  3600 s and a single-unit job's per-unit maximum is 3480 s (klt's own
  `job_ceiling.warning`, "lower options.timeout_s to at most 3480s", seen in
  the `sim/adc-inl-dnl` report). Against the §2.4 floor of 8 599 – 13 047 s,
  120 – 200 s of headroom is noise. Any plan that depends on it is rejected here.
- **Output collection and recovery if the client exits.** Submit with
  `-o <outdir>` and `--report-out`; the job id is printed on stderr at launch
  and is the recovery handle. If the client dies: `klt sim --job-status
  <JOB_ID> <same-request>` (reads one `status.json`, launches nothing) and
  `klt sim --attach <JOB_ID> <same-request> --backend batch -o <outdir>`
  (waits, bounded by the request's `batch.poll_timeout_s`; never re-launches).
  Alternatively `--submit-only` per request to detach deliberately. The
  executor writes both job ids and request sha256s to the PR/issue **before**
  waiting. If the Spot instance is reclaimed, report it; do not resubmit
  without a new approval.
- **Collection must include** (this is what #582 lost): each `ngspice.log`
  *and* each `corner.cir` verbatim, committed with sha256, even for timeouts;
  the full `klt-report` including `worker_environment`; the host-side
  `klt --version` and `klt sim --dry-run` output.

### 6.5 Stage R — gated, and why it is not scheduled

The ratified-window pilot is **one** unit: `tt`/27 °C/3.30 V, `tran 5n 8.5u 0
5n` unchanged, `timeout_s` 3480 (the single-unit maximum), one job of ≤ 3600 s
(1.0 instance-hour), no retries, one thread.

It is **not launchable on the unmodified deck on the evidence in hand**: the
§2.4 floor puts completion at 2.5 – 3.8 × the largest timeout the fleet allows,
and #343 measured no floor to the step collapse. Launching it would spend
≈ 1 instance-hour to re-observe a timeout. Stage R is released only by one of:

1. **Stage D shows the unmodified deck completes or is tractable** at 1.8 µs
   in an isolated unit (e.g. finishes well inside 2400 s without aborting),
   which contradicts the §2.4 inference and re-opens the question; or
2. **A deck remedy is ratified by a decision record** (#343 §5: R1b is the
   variant "a superseding record should cost first"), producing a *new* deck
   with a new sha256 and a new `tb.json` note; or
3. **The fleet's whole-job ceiling is raised** (an infrastructure change owned
   outside this repo), with the new ceiling and per-unit maximum stated.

Absent any of those, the honest statement is that the ratified-window
`bad` run is **not achievable on current capability**, and #303 should be told
so rather than asked to approve another timeout. That decision is #303's, not
this document's.

### 6.6 What each Stage D outcome would discriminate

| observation | reading it supports | does **not** show |
|---|---|---|
| arm A and arm B both abort at ≈ 1.6983 µs, same node, similar row count | the abort is deterministic and independent of retention; the #582 retention attribution is refuted for this point | the mechanism (needs a probe); behaviour at other corners |
| abort time differs materially from 1.6983 µs | sensitivity to PDK stamp/ngspice build (record 5.1 and the build-date mismatch); the #582 abort times are toolchain-specific | which one |
| both complete 1.8 µs inside the cap | the unmodified deck is tractable in isolation; the #582 failures were concurrency/throughput; re-opens §6.5 option 1 | anything about 8.5 µs |
| arm A reports a value, arm B reports a value, or exactly one does | direct measurement of `.meas`-after-abort and of retention's effect (F5), under a qualified toolchain | which build of klt/ngspice to blame without the receipts |
| `timestep_too_small` present in the report | runner has #2918; F3 closed | — |
| `timestep_too_small` absent despite the log line | runner lacks #2918; the receipt in §6.2(2) was wrong | — |
| rows/s differs strongly from 207 – 223 | the §2.4 rates were contention-driven | cost at 8.5 µs |

### 6.7 Evidence required before any larger run

All of the following, on file, before a multi-point `bad` request is even
drafted:

1. Stage D complete under the §6.2 receipts, with `ngspice.log` and
   `corner.cir` committed.
2. A **completed** ratified-window unit (§6.5) with its measured `runtime_s`
   in isolation, `aerr_bad`, and its disposition against `min=0.9`.
3. A grid cost estimate `N × c` where `c` is that unit's measured isolated
   cost, **not** the five-loop ~10 CPU-h, not `ok`'s 132 core-s, and not an
   extrapolation from the aborted points.
4. Every unit's expected runtime ≤ half its `timeout_s` and ≤ the fleet's
   per-unit maximum (a margin proposal: this is a proposed gate, not a
   ratified rule). The request must also respect klt's own job-ceiling
   advice, which #582 ignored (§2.4): one unit per job
   (`--max-units-per-job 1` / `remote.hosts` ≥ the unit count) so units do not
   share an instance — and the fleet's instance cap for that many concurrent
   jobs must be stated by its owner, because it is not recorded here.
5. Toolchain receipts unchanged from §6.2 and no drift banner.
6. A separately approved dollar figure for the larger run.

### 6.8 Concurrency and the five-loop cost

The plan is deliberately two **concurrent single-unit jobs** (not one job of
two units), so neither unit shares an instance and the isolated rate is
observable. The five-loop deck's ~10 CPU-h/point is not used anywhere in this
plan, as #584 requires; the 15-way-concurrency rates of §2 are used only to set
**caps**, never to predict cost.

### 6.9 Absent approvals and capabilities

| absent | owner | needed for |
|---|---|---|
| method and budget approval, with the dollar figure | #303 (operator) | any launch of Stage D or R |
| #517 merged (forward pin, ciel, pin-vs-resolved check) | #514 / #513 | the qualified-toolchain receipt |
| runner-image feature receipt (#2918, #3921) and `pdk_stamp_comparison: match` | fleet owner (2AMLogic/2am); klayout-tools#3676 (open) | §6.2 receipts 1-2 |
| a decision on the deck remedy (R1/R1b) or a raised fleet ceiling | a new decision record / infra | Stage R |
| permission to edit `tb.json`'s now-falsified sentence | the same decision record | amending the manifest note |
| any change to the spec, comparator model, measurement bounds or ratified window | **not requested** | — |

## 7. Follow-ups raised by this audit (none is done here)

- **klayout-tools** (filed per the friction protocol, deduplicated first; the
  closest hits were #3067, #3879, #3921, #2918, all closed and all about
  different symptoms): the `save_mode: "netlist"` no-value hint is attached to
  every `measurement` error, including corners whose cause is already a
  `timeout` or `timestep_too_small`. Link: 2AMLogic/klayout-tools#3963 (https://github.com/2AMLogic/klayout-tools/issues/3963).
- **This repo, harness**: `sim/harness/batch.py` scores a klt `error` corner
  with no values before the abort scan (§2.3, F4), and does not preserve
  `corner.cir` when a corner is a timeout or an error (F6). Filed as #585; a
  code change, out of scope for this plan.
- **This repo, prose**: `design/sar-logic/rtl/README.md` (the `bad` paragraph
  near line 612) restates the retention attribution for the three points as
  fact. It should be superseded by a note pointing here; the append-only
  `records/` are untouched by that.
- `tb.json`'s "#296 does NOT apply" sentence: see §3.3, belongs to the
  decision record.

## 8. Re-derive every number

Run from the repository root at `493959f0` (or any later tree where
`sim/sar-logic-timing-gates-bad/` is unchanged). No command runs a simulation.

```bash
D=sim/sar-logic-timing-gates-bad/corners/20261020-011850-edf81f4

# A. the three aborts (time, node, floor, rows) and only those three:
grep -n 'Timestep too small\|No. of Data Rows' $D/{tt_-40c_3.63v,fs_27c_3.30v,sf_27c_3.63v}.log
grep -l 'Timestep too small' $D/*.log                 # exactly those three
python3 -I - <<'EOF'
import sys, glob, os
sys.path.insert(0, "sim")
from harness import runner
for f in sorted(glob.glob("sim/sar-logic-timing-gates-bad/corners/20261020-011850-edf81f4/*.log")):
    t = open(f, errors="replace").read()
    if not t.startswith("TIMEOUT") and runner.analysis_aborted(t):
        print(os.path.basename(f), runner.analysis_aborted(t))
EOF

# B. the 42 timeouts are 20-byte harness-written stubs, and no others:
grep -lx 'TIMEOUT after 3400s' $D/*.log | wc -l        # 42
find $D -name '*.log' -size -21c | wc -l               # 42

# C. per-corner status/runtime/diagnostic codes in the klt reports:
python3 -I - <<'EOF'
import json, glob
n = {"timeout": 0, "measurement": 0}
hint = 0
for f in sorted(glob.glob("sim/sar-logic-timing-gates-bad/corners/20261020-011850-edf81f4/klt-report.vdd*.json")):
    for c in json.load(open(f))["corners"]:
        codes = [d["code"] for d in c["diagnostics"]]
        for k in n: n[k] += k in codes
        hint += all('save_mode is "netlist"' in d["message"] for d in c["diagnostics"] if d["code"] == "measurement")
        if "timeout" not in codes:
            print(f.split(".")[-2], c["corner_id"], c["runtime_s"], codes)
print(n, "all-45 carry the save_mode hint:", hint == 45)
EOF

# D. rows/s, % of window, linear extrapolation (arithmetic on A and C):
python3 -I -c "
for k,(r,w,t) in {'tt_-40c_3.63v':(540082,2607.043,1.69847e-6),'fs_27c_3.30v':(711819,3189.864,2.0925e-6),'sf_27c_3.63v':(358468,1718.062,1.6983e-6)}.items():
    print(k, round(r/w,1), 'rows/s', round(t/8.5e-6*100,1), '%', round(8500/(t*1e9/w)), 's')"

# E. runner vs client PDK/engine, job elapsed times, job ceiling:
python3 -I - <<'EOF'
import json, glob
for f in sorted(glob.glob("sim/sar-logic-timing-gates-bad/corners/20261020-011850-edf81f4/klt-report.vdd*.json")):
    r = json.load(open(f)); e = r["environment"]; rm = e["remote"]
    print(f.split(".")[-2], "client pdk:", r["provenance"]["pdk"]["version"],
          "| runner pdk:", rm["worker_environment"]["pdk"]["stamp_text"],
          "| cmp:", rm["worker_environment"]["pdk_stamp_comparison"]["status"],
          "| engine_version:", e["engine_version"], "| elapsed_s:", rm["elapsed_seconds"],
          "| compat:", rm["runner_compatibility"])
EOF

# F. deck / body / snapshot identities:
sha256sum sim/sar-logic-timing-gates-bad/testbench/* sim/sar-logic-timing-gates-bad/netlist-snapshots/* $D/klt-request.*
tail -n +5 sim/sar-logic-timing-gates-bad/netlist-snapshots/20261020-011850-edf81f4.spice | sha256sum   # = 273f8108…
grep -n '^\.save' sim/sar-logic-timing-gates-bad/netlist-snapshots/*batch-body*.spice                    # .save v(bad_aerr)
grep -n 'save' sim/sar-logic-timing-gates-bad/testbench/tb_sar_logic_timing_gates_bad.spice             # (none)
sed -n '48p;83,84p' sim/sar-logic-timing-gates-bad/testbench/tb_sar_logic_timing_gates_bad.spice          # topology
git log --oneline -3 -- sim/sar-logic-timing-gates-bad/testbench                                       # 60336f22 is the last

# G. the harness ordering (F4) and the local-harness abort that DID print a .meas value:
sed -n '723p;742p;766p' sim/harness/batch.py
sed -n '14118p;14123p' sim/sar-logic-timing-gates-lt/corners/20260920-182006-2422cac/ff_125c_3.30v.log

# H. klt source (host install dev2226) -- the hint, the demotion, the classification:
S=~/.local/share/uv/tools/klayout-tools/lib/python3.13/site-packages/klayout_tools/sim.py
grep -n 'SAVE_MODE_NETLIST_NO_VALUE_HINT\|def _demote_abort_cascade\|"timestep_too_small"' "$S"
sha256sum "$S"

# I. issue states cited:
gh issue view 2918 -R 2AMLogic/klayout-tools --json state,closedAt
gh issue view 3676 -R 2AMLogic/klayout-tools --json state
gh issue view 514 --json state,labels; gh pr view 517 --json state,mergeStateStatus
```

## Environment of this investigation

- No ngspice, xschem or klt simulation was executed. `klt sim --help` and the
  installed `klt` package source were read; `python3 -I` was used for the
  pure-text analyses and for calling `harness.runner.analysis_aborted` on
  already-committed logs.
- Host: `klt 0.7.1.dev2226+gfda8dad261dc` (read-only use), Python 3.12.3.
- Tree: `493959f0cd93d6b40d08db4e5affd9f150e34d85`; this file is the only
  addition.
