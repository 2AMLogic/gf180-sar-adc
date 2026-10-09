# Investigation 20261009-issue-459-gain-error-control-arm-delta

This is not a `sim/run_corners.py` evidence record. No PVT grid was scored
and **no simulation was run**. It is a provenance analysis of two committed
records. It sits in `investigations/`, next to `records/` and not inside it,
so the append-only `records/` tree is not edited.

- **Date**: 2026-10-09 (UTC)
- **Base commit**: `c472fff3ab037e3ebde00e66d35871e461092514` (`main`), clean worktree
- **Issue**: #459 (filed by the #437 Builder; paired-control records from #393)
- **Inputs (read-only)**:
  - **A**, governing: [`records/20260923-104443-904af96.md`](../records/20260923-104443-904af96.md), its snapshot `netlist-snapshots/20260923-104443-904af96.spice` and its 27 logs in `corners/20260923-104443-904af96/`
  - **B**, #393 ideal-supply control arm: [`records/20261007-071907-800bf53.md`](../records/20261007-071907-800bf53.md), its snapshot `netlist-snapshots/20261007-071907-800bf53.spice` and its 27 logs in `corners/20261007-071907-800bf53/`
- **Tools used here**: `python3` 3.12.3 (stdlib only), `git`, `sha256sum`, `diff`.
  No ngspice, PDK or klt run. The two helper scripts are committed next to
  this file, and their outputs are committed verbatim as `.txt`.

## Question

The `Gain error, systematic` row of `sim/characterization-summary.md` cites
A at **`tp_inj_signal_dep_lsb` = 0.000981002 LSB**, worst corner
`ff_-40c_3.63v`. B runs the same extracted deck and reads **0.0010063 LSB**
at the same corner. Both PASS by about 500× against the ≤ 0.5 LSB bound. The
other three #393 control arms reproduce their citations, and this one does
not reproduce bit-for-bit. Issue #459 asks why, and which figure governs.

## Conclusion

1. **Cause.** The difference is a **solver-path difference between two
   ngspice execution environments**. The deck, manifest, harness, PDK pin,
   recording code and dirty-tree state are excluded as causes.
   - A ran on the `/home/ubuntu` Linux host family: Python 3.12.3,
     `ngspice-46`, front-end note `No compatibility mode selected!`.
   - B ran on the `/Users/rwalters` workstation: Python 3.14.8, `ngspice-46`,
     front-end note `Compatibility modes selected: hs a`. That mode comes from
     an ngspice init file on that host. The init file was not recorded, and
     the harness does not write one.
   - Fed byte-identical inputs, the two environments produce t = 0 operating
     points that differ only at the floating-point-residue level (≤ 8.7e-11
     LSB on the near-zero readout nodes). At 24 of 27 corners the adaptive
     transient then follows a different accepted-timepoint path.
   - At `ff_-40c_3.63v` that path difference moves all five sampled
     top-plate values `tp_inj_p_l0..l4_lsb` by an almost common
     −0.00670 LSB (≈ 24 µV on the top plate). That is about 75× inside the
     ≈ 1.8 mV Newton convergence band that ngspice's default tolerances
     (`RELTOL` 1e-3 · |v| + `VNTOL` 1 µV, with no `.options` in the deck or
     manifest) allow on a ≈ 1.8 V node.
   - `tp_inj_signal_dep_lsb` is max − min over those five values, so the
     common part cancels. What is left is a **+2.53e-5 LSB level-to-level
     residue**: l1 moved by −0.0066919 and l2 by −0.0067172. That residue is
     exactly 0.0010063 − 0.000981002.
2. **Ruled out by committed evidence (§2–§5)**:
   - a deck change: both snapshots hash to the recorded
     `4fea809d…`;
   - a manifest change;
   - a harness or recording change: no commits in `904af96..800bf53` touch
     the harness, and all 2,322 transcribed cells match the logs;
   - the dirty tree;
   - run-to-run non-determinism: six same-environment repeat pairs are
     bit-identical, and those include a dirty-vs-clean pair of an extracted
     deck;
   - a parsing or rounding artefact.
3. **Not isolated: which part of the environment.** The ngspice build and
   platform (Linux vs macOS) and the `hs a` front-end mode change together in
   every committed cross-environment pair, so committed evidence cannot
   separate them. The evidence does show that `hs a` did not change the
   elaborated circuit, its models or its options: 3 of 27 corners agree to
   ≤ 1e-10 LSB on every measurement (§4). It cannot rule out that `hs a`
   reorders elements and so changes floating-point rounding. Separating the
   two needs a controlled run that could not be done this pass (§7).
4. **Governing figure: unchanged.** A remains the governing citation at
   0.000981002 LSB. B is a valid same-deck re-solve. It confirms A's verdict
   (27/27 PASS), A's worst corner and A's figure to 2.5e-5 LSB (2.6 %), from
   a clean tree. It does not supersede A. Neither figure is more correct:
   both are solutions within the solver's own tolerance, and the observed
   environment spread is 2e4× smaller than the margin to the bound. The
   #437 citation exception keeps its exact tuple. Its reason now names this
   cause instead of saying "cause not isolated". No bound, measurement
   definition, manifest check or verdict changes.

## 1. Reproduce this

From the repository root, at the base commit above:

```
python3 -I sim/dr0014-sampling/investigations/20261009-issue-459-trace.py \
  > /tmp/trace.txt
diff /tmp/trace.txt sim/dr0014-sampling/investigations/20261009-issue-459-trace.txt
python3 -I sim/dr0014-sampling/investigations/20261009-issue-459-record-pairs.py \
  > /tmp/pairs.txt
diff /tmp/pairs.txt sim/dr0014-sampling/investigations/20261009-issue-459-record-pairs.txt
git diff --numstat 904af96..800bf53 -- sim/dr0014-sampling/testbench-extracted sim/harness sim/run_corners.py
git log --oneline 904af96..800bf53 -- sim/harness sim/run_corners.py sim/dr0014-sampling/testbench-extracted/tb.json
for c in 904af96 96a8546a 800bf53; do
  git show $c:sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice | sha256sum
done
```

Both scripts finish in under a second and read only committed files.

## 2. Deck, manifest and harness identity

| item | A (`904af96`, dirty) | B (`800bf53`, clean) |
|---|---|---|
| recorded `Testbench netlist sha256` | `4fea809d68eba487643e166fb30011b5bbf3c32056644778afab98ecfdf1dd2f` | same |
| snapshot body sha256 (4-line "Frozen netlist snapshot" header removed) | `4fea809d…dd2f` | `4fea809d…dd2f` |
| snapshot `diff A B` | only line 1, the record ID | |
| recorded `Manifest sha256` (`testbench-extracted/tb.json`) | `8eab6926ae7baacd94d66a255fc9556ce345440fa089562f72458e15392a8819` | same |
| `tb.json` at the commit | `8eab6926…` at `904af96` | `8eab6926…` at `800bf53` |
| harness | `sim/harness 0.1.0`; `git log 904af96..800bf53 -- sim/harness sim/run_corners.py` is **empty** | same code |
| PDK | gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` | same pin |
| corner model sections | `tt`/`ss`/`ff` bundles as listed in both records | identical lists |

**Why `git diff 904af96..800bf53` shows a changed deck even though the
recorded hashes match.** At the commit `904af96` the extracted deck hashes to
`314cfabf…`, the older pre-re-extraction deck. A ran on a **dirty** tree that
already held the regenerated deck. That deck was then committed in
`96a8546a` (#390), the same commit that committed record A, and it hashes to
`4fea809d…`. `800bf53` inherits that file unchanged. So the 6651/6044-line
numstat is the difference between `904af96`'s *committed* deck and the deck A
*actually ran*. Both runs ran `4fea809d…`, as the snapshots prove.

## 3. Dirty-tree and inherited-provenance accounting

- **A's "dirty" flag.** The harness samples `git status --porcelain` before
  the run and, if the tree is dirty, appends "taken against a dirty working
  tree at commit …" to the netlist provenance (`sim/harness/report.py`,
  `render_record`). The dirty content that matters is the deck, and A's own
  snapshot pins it to the bytes later committed in `96a8546a`. The record
  does not say which other files were dirty. Two pieces of evidence bound
  that gap:
  1. Every one of the 2,322 Result cells (2 records × 27 corners × 43
     measured columns) traces to its log value through the harness's own
     `_fmt()` (trace script, "Harness transcription: 0 … differ"). The
     harness at `904af96` and `800bf53` is the same code.
  2. Three corners agree on every measurement to ≤ 1e-10 LSB (§4). A dirty
     harness that changed the composed deck would show at every corner.

  Separately, a dirty-vs-clean pair of an *extracted* deck from this host
  family (`adc-inl-dnl` `20260817-214114-076d545`, dirty, vs
  `20260923-095803-836a876`, clean) is identical at all 27 corners (§5).
  Dirty-tree status is not a mechanism here.
- **B's inherited dirty-tree wording.** B's `Netlist provenance` field says
  "taken against a dirty working tree at commit `904af96…`". B's own
  Environment section says `800bf53…` (clean). The wording is inherited.
  `sim/vdd-full-pvt/run_full_pvt.sh` (`governing_prov()`) copies the
  governing record's `Netlist provenance` field **verbatim** into the
  ideal arm's `--netlist-provenance`, and that field already carried A's
  harness-appended dirty clause. The harness then appended the deck path a
  second time, which is why the path appears twice, and appended no dirty
  clause of its own because B's tree was clean. The clause names A's commit
  and describes A's run, not B's.

## 4. The measurement trace at `ff_-40c_3.63v`

`tp_inj_signal_dep_lsb` is defined in `testbench-extracted/tb.json` as
`max(tp_inj_p_l0..l4) − min(tp_inj_p_l0..l4)`, with
`tp_inj_p_lN = aNtpp − aNprep`. These are `FIND v(aN_dp)` at 245 ns and
187 ns under `tran 20p 600n 0 100p`. `aN_dp` is the B-source readout
`(v(aN_topp) − vcm)/lsb`. Values below are the 11-significant-digit
`m_*` lines each log printed (`set numdgt=10`):

| level | A `tp_inj_p_lN_lsb` | B | B − A |
|---|---|---|---|
| l0 | 0.11308866028 | 0.10638585822 | −0.0067028021 |
| l1 (max in both) | 0.11326106020 | 0.10656915817 | −0.0066919020 |
| l2 (min in both) | 0.11228005827 | 0.10556285529 | −0.0067172030 |
| l3 | 0.11315025666 | 0.10645845462 | −0.0066918020 |
| l4 | 0.11306587596 | 0.10636347569 | −0.0067024003 |
| **signal_dep** | **9.8100193138e-04** | **1.0063028795e-03** | **+2.5301e-05** |

- **The term is computed the same way in both runs.** The same levels set
  max and min (l1/l2). Recomputing max − min from the printed per-level
  values reproduces each log's own `m_tp_inj_signal_dep_lsb` to the printed
  precision. The records' 0.000981002 and 0.0010063 are the harness's
  6-significant-digit `_fmt()` of those log values. Parsing and rounding
  contribute < 1e-9 LSB.
- **Every level moves by the same amount, to within 0.4 %.** The spread of
  the per-level shifts (2.54e-5 LSB) *is* the signal_dep change.
  Hold-phase values (`hold_l*`, about ±900 LSB) move by ≤ 2e-4 LSB.
  `samp_span_lsb` is identical in both logs (−1804.4593) at this corner.
- **The two runs took different time steps.** `No. of Data Rows` (accepted
  timepoints kept in the saved plot) is 6066 in A and 6061 in B.
- **The two t = 0 operating points already differ, at roundoff level.** Of
  27,018 printed OP values, 60 differ. They are the 24 LSB-scaled readout
  nodes, which sit about 1e-8 LSB from zero (top plate ≈ vcm), plus
  near-zero branch currents. The largest node difference is 3.6e-11 LSB
  (≈ 1.3e-13 V). Every other node agrees at the printed 6 significant
  digits.
- **One extra line in B: a warning.** B also prints
  `Warning: m=xx on .subckt line will override multiplier m hierarchy!` at
  every corner. This is an `hs`-mode parse message. In the pinned gf180mcuD
  models the only `.subckt` lines that carry `m=` are
  `nfet_03v3_dss`/`pfet_03v3_dss` (`m=1`). Those devices are not
  instantiated by this deck, which uses `nfet_03v3`/`pfet_03v3`.

**The same pattern holds across the whole grid** (trace output, "Per
corner"):

- At **3 corners** (`tt_27c_3.63v`, `ss_27c_2.97v`, `ff_27c_3.63v`) A and B
  agree on **every** measurement to ≤ 1e-10 LSB, even though their t = 0
  OPs differ at the same 1e-11 level. These three corners span all three
  model bundles (`tt`, `ss`, `ff`). Running in the two environments
  therefore elaborates the same circuit, binds the same model behaviour and
  uses the same options.
- At the other **24 corners** the timestep path diverges.
  - Accepted-row counts differ at 17 corners.
  - The common-mode `tp_inj_p` shift ranges from −0.0067 to +0.0051 LSB.
  - `|Δ tp_inj_signal_dep_lsb|` is ≤ 2.78e-5 LSB at every corner (largest
    at `ff_27c_2.97v`).
  - The max/min levels change at exactly one corner (`tt_125c_2.97v`).
- The worst corner (`ff_-40c_3.63v`) and 27/27 PASS are the same in both
  runs.

## 5. Same-environment repeats are bit-identical; cross-environment pairs are not

Every pair below shares the recorded deck and manifest sha256. "Logs
identical" means the raw ngspice logs are byte-identical once the
`Reference value :` progress lines are removed (ngspice prints those on a
wall-clock cadence). Source: `20261009-issue-459-record-pairs.txt`.

| experiment | pair | environment | Result rows identical | logs identical |
|---|---|---|---|---|
| dr0014-sampling (schematic) | `20260817-134517-cde979d` / `20260923-085243-664c8dc` | Linux, no compat mode, both | 27/27 | 27/27 |
| adc-inl-dnl (extracted; dirty vs clean) | `20260817-214114-076d545` / `20260923-095803-836a876` | Linux, both | 27/27 | 27/27 |
| adc-inl-dnl | `20260817-131106-abf9c75` / `20260923-072117-664c8dc` | Linux, both | 63/63 | 63/63 |
| adc-power | `20260826-085142-155595d` / `20260923-112459-836a876` | Linux, both | 27/27 | 27/27 |
| track-switch-sampling (transient) | `20260801-113511-c05043b` / `20260802-141402-1224e11` | macOS, `hs a`, both | 117/117 | 117/117 |
| smoke-sar-bias | `20260731-155343-685ba01` / `20260731-162251-1dcdf3a` | macOS, `hs a`, both | 45/45 | 45/45 |
| **dr0014-sampling (extracted)** | **A / B** | **Linux → macOS** | **0/27** | **0/27** |
| adc-inl-dnl (#393 control) | `20260923-095400-904af96` / `20261007-044826-800bf53` | Linux → macOS | 0/27 | 0/27 |
| adc-power (#393 control) | `20260923-102440-904af96` / `20261007-072338-800bf53` | Linux → macOS | 0/27 | 0/27 |
| adc-enob-fft (#393 control) | `20260923-111149-904af96` / `20261007-072654-800bf53` | Linux → macOS | 9/9 (digital output codes) | 0/9 |
| device-switch-ron (`.op` only) | `20260731-191216-5f5288b` / `20260806-140624-4f71285` | macOS → Linux | 45/45 | 0/45 |

Each environment is deterministic: repeats weeks apart, across commits and
across dirty/clean trees, are bit-identical, transients included. Every
cross-environment pair differs in its logs. Where the scored rows depend on
the transient's analog values, the rows differ too:

| #393 control arm | worst delta vs its citation |
|---|---|
| INL/DNL | 2e-5 LSB |
| power | 0.235 µW |
| this gain-error arm | 2.5e-5 LSB |

They match where the output is quantised (ENOB/SFDR codes) or comes from a DC
operating point (`device-switch-ron`). So the gain-error arm is not unusual.
It is the one #393 control whose headline figure is small enough
(≈ 1e-3 LSB) that a 2.5e-5 LSB solver-path difference shows in its fourth
significant digit.

This also corrects the open hypothesis in `sim/vdd-full-pvt/README.md`
("`ngspice` thread/scheduling versus a harness change", "a different host
load"). There was no harness change between the commits. Thread scheduling
does not change results within an environment (the repeats above, and the
harness's own `--ngspice-threads` note: bit-identical at 1 vs default
threads). The two runs were on **different hosts**, not one host under
different load.

## 6. Unrecorded inputs (why the split in Conclusion 3 is not possible from records)

- **ngspice build identity.** Records keep only the banner's first line
  (`ngspice-46 : Circuit level simulation program`). There is no build date,
  compiler, OS/arch, or OpenMP/KLU configuration. Both logs report
  `Using SPARSE 1.3`.
- **ngspice init state.** Neither the init file (`spinit`, `~/.spiceinit`)
  nor `ngbehavior` is recorded. The `hs a` mode is visible only in the
  first line of B's raw logs. The harness runs `ngspice -b` in a scratch
  directory and does not write a `.spiceinit`.
- **Platform and hostname.** The harness puts these in its environment dict
  (`sim/harness/report.py:environment()`), but the Markdown record does not
  render them and no JSON sidecar is committed. The PDK path
  (`/home/ubuntu/…` vs `/Users/rwalters/…`) is the only committed host
  marker.
- **PDK model bytes.** Only the open_pdks commit is recorded, not the hashes
  of `design.ngspice`, `sm141064.ngspice` or `sm141064_mim.ngspice`. The
  three bit-agreeing corners (§4) show the bytes behave identically in the
  `tt`/`ss`/`ff` sections. They cannot prove byte identity.
- **Composed per-corner deck.** It is generated by `compose_deck()` in a
  scratch directory and not kept. It is reconstructable from the committed
  harness, manifest and snapshot plus the PDK path.
- **Thread count.** B: `run_full_pvt.sh` defaults `NGSPICE_THREADS=1`,
  `JOBS=4`. A: the #390 invocation is not recorded. Within-environment
  thread settings are measurement-neutral (§5).

## 7. The controlled split, and why it was not run this pass

Separating "build/platform" from "`hs a` front-end mode" needs **one pinned
`ngspice-46` binary** run at `ff_-40c_3.63v` twice: once with no init file,
once with `set ngbehavior=hsa`. The composed deck is identical and only the
init file changes. If the two runs are bit-identical, the cause is the
build/platform. If they differ, the compat mode alone shifts the solver
path. It was not run here:

- **This dispatch worker has `ngspice-42`, below the `>= 46` pin.**
  `python3 sim/run_corners.py --check-env` reports `pins: DRIFT` and refuses
  to simulate. A 42-vs-46 run would add a third environment, not separate
  the two in question.
- **The batch fleet cannot take the request.** On the same day the fleet
  runner (klt 0.5.0) refused this worker's klt 0.7.0 client
  (`sim/adc-enob-fft/investigations/20261009-issue-430-0.7.0-client-mismatch-recurs.md`).
  The fleet's ngspice would also be a third environment. Neither `klt sim`
  nor the harness has a switch to set or clear the ngspice compat mode.
- **B's host is a private workstation** and is not reachable from here.

None of this changes the governing decision. Whichever component is
responsible, both figures are valid solutions of the same deck, and their
gap is about 2e4× below the margin to the bound.

**Follow-on, not done here** (filed as #468):

1. Harness provenance should render platform, hostname, the full
   `ngspice -v` banner and the ngspice compatibility-mode note into every
   record. It should also either pin `ngbehavior` or neutralise host init
   files, so the two host families stop differing silently.
2. Run the one-binary A/B above on a pinned worker.

## 8. What this does not change

- No `sim/` record, snapshot or corner log is edited or regenerated.
- No ratified bound, measurement definition, manifest check or verdict
  changes.
- No single-corner result is presented as grid evidence. No new grid result
  exists.
- The governing citation stays `20260923-104443-904af96`, A's 27-point full
  PVT grid.
