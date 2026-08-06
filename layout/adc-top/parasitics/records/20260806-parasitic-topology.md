# Record 20260806-parasitic-topology

- **Record ID**: 20260806-parasitic-topology
- **Claim**: the extracted parasitic **resistance** produced by `klt extract
  --deck gf180mcu --parasitics` is, for every net of every block this project
  extracts, a **stub** — it is wired between the net and a dangling internal
  node that carries only that net's ground capacitance, so no device current
  flows through any of it. Consequently no resistive (DC / R_on / IR-drop /
  settling-resistance) quantity can differ between a schematic deck and an
  extracted-core deck built from these netlists, and
  `sim/extracted-delta-summary.md` §6.3's post-layout re-take of the CDAC
  settling network's resistance (`R_WORST_BIT_OHM`, rate closure's input)
  cannot be obtained from this extraction at all — not because the deck is
  missing, but because the extraction does not express the quantity.
  This record substantiates that claim two ways: **structurally**, by
  classifying every parasitic element in the committed netlists, and
  **by measurement**, via the 45-point PVT R_on re-take in
  `sim/device-switch-ron/records/20260806-140815-7fa57ad.md` plus a positive
  control that shows the measurement would have detected series resistance
  had any been present.
- **Netlist provenance**: extracted (`klt extract --parasitics --pdk
  gf180mcuA`), record
  [`20260806-140411-968d138`](20260806-140411-968d138.md); the `adc_tgate`
  leaf additionally post-processed by `remediate_extracted.py --leaf` (PMOS
  body promoted to a `vnw` pin, nothing tied inside the cell).
- **PDK binding**: gf180mcuA, open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`. klt 0.2.0. ngspice-46.
- **Working tree**: clean at commit `5e2db8e` (the commit that landed the
  extracted R_on record) before this record's own files were added —
  `git status --porcelain` empty, per the citability lesson
  `sim/adc-enob-fft/records/20260806-081350-862d054.md` documents.

## Why this was run

`sim/extracted-delta-summary.md` §6.3 blocks rate closure and the DR-0012/13
gain-error row on a post-layout re-take of two settling-network inputs, and
names exactly one piece of it as tractable without drawing new geometry:

> **Group D (the Input-structure R_on re-take) is the one piece of this deck
> that is structurally tractable without new layout.** It instantiates
> `adc_tgate` only […] and `adc_tgate.gds` **is** a standalone drawn leaf
> cell […] A post-layout R_on re-take is possible in principle by extending
> `run_extract_parasitics.py` […] to a third `adc_tgate` target, then a new
> forced-voltage/measured-current deck against it on
> `sim/device-switch-ron/`'s own method (`mos` corner set).

That is what was built and run. The result is a null — and a null is only
worth recording if it is shown to be a property of the thing measured rather
than of the measurement, which is what the rest of this record establishes.

## Reproduce

```
# 1. Extract all three targets (the leaf is the new one), asserted against
#    cells.json.
python3 layout/adc-top/parasitics/run_extract_parasitics.py --check

# 2. Classify every parasitic element of every committed extraction.
python3 layout/adc-top/parasitics/audit_parasitic_topology.py
python3 layout/adc-top/parasitics/audit_parasitic_topology.py --format json

# 3. Regenerate the extracted-cell R_on deck (asserts byte-identity with the
#    committed fixture).
python3 layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py --check

# 4. The 45-point PVT grid, schematic side then extracted side, tb.json
#    unmodified on both.
python3 sim/run_corners.py device-switch-ron
python3 sim/run_corners.py device-switch-ron \
    --netlist sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice \
    --netlist-provenance "extracted (...)"
python3 sim/tools/schematic_vs_extracted.py device-switch-ron \
    --schematic 20260806-140624-4f71285 --extracted 20260806-140815-7fa57ad

# 5. The positive control: the same deck with the extracted parasitic R moved
#    into the channel path. Never written into sim/ -- the exact bytes used
#    are in this record's report directory.
python3 layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py \
    --in-path-control --stdout \
    > reports/20260806-parasitic-topology/tb_switch_ron_in_path_control.spice
python3 sim/run_corners.py device-switch-ron \
    --netlist layout/adc-top/parasitics/reports/20260806-parasitic-topology/tb_switch_ron_in_path_control.spice \
    --netlist-provenance "extracted (positive control: parasitic R moved in-path)" \
    --corners tt --temps 27 --supply-tol 0 --no-write
```

## Result 1 — the structure: 332 parasitic nets, 0 of them in the signal path

`klt extract --parasitics` writes, per net it covers, exactly one pair:

```
R<net> <net> <net>__par <ohms>
C<net> <net>__par <ground> <farads>
```

Whether that `R` carries current depends on which node the **devices** are
attached to. `audit_parasitic_topology.py` answers that mechanically — it
classifies a net `in-path` if any non-parasitic card has a terminal on
`<net>__par`, and `stub` otherwise:

| netlist | parasitic nets | in-path R | stub R | total R (Ω) | max R (Ω) | total C (fF) |
|---|---|---|---|---|---|---|
| `adc_block.para.spice` | 172 | 0 | 172 | 129703.6 | 20499.2 | 4056.184 |
| `adc_tgate.para.spice` | 4 | 0 | 4 | 302.8 | 120.0 | 9.235 |
| `adc_top.para.spice` | 156 | 0 | 156 | 115319.7 | 16013.5 | 3730.486 |

**Every device in all three extractions hangs directly off the net node.**
115 kΩ (`ADC_TOP`) / 130 kΩ (`ADC_BLOCK`) of extracted resistance exists in
the netlist and carries no signal current; individual nets are assigned up to
20.5 kΩ. The extractor's own JSON summary names the same node
(`parasitics.nets[].internal_node`), so this is the model's intended shape,
not a defect in a particular run.

What the parasitics therefore **do** model: capacitive loading, behind a small
series resistance (a lossy load). Every dynamic delta this campaign has
measured — §4.1's INL/DNL, §4.6's ENOB, §4.7's switching power — is a real
consequence of that loading and is unaffected by this record. What they do
**not** model: series/IR resistance of any drawn conductor.

## Result 2 — the measurement: 1125 of 1125 result cells identical

The 45-point `mos`-set PVT grid (tt/ff/ss/fs/sf × −40/27/125 °C × ±10 %), run
against `sim/device-switch-ron/testbench/tb.json` **unmodified** on both
sides, with only the transmission-gate branch swapped for instances of the
extracted, leaf-remediated `adc_tgate`:

| | schematic `20260806-140624-4f71285` | extracted `20260806-140815-7fa57ad` | delta |
|---|---|---|---|
| worst T-gate `ron_t_max` | 570.436 Ω (`ss_125c_2.97v`) | 570.436 Ω (`ss_125c_2.97v`) | **0** |
| worst `ron_t_flatness` | 3.28898 (`ss_-40c_2.97v`) | 3.28898 (`ss_-40c_2.97v`) | **0** |
| per-corner verdicts | 45/45 PASS | 45/45 PASS | none changed |
| result cells that differ | — | — | **0 of 1125** (45 corners × 25 columns) |

The `ron_n_*` / `ron_p_*` columns are a built-in control: those branches are
copied verbatim into the extracted deck, so a nonzero delta there would mean
the comparison itself was broken. They are zero, as required.

The drawn cell's device geometry is asserted equal to the schematic branch's
before the deck is emitted (NMOS W = 10 µm, PMOS W = 20 µm, both L = 0.28 µm),
so this is a like-for-like comparison and not two different transistors that
happen to agree.

## Result 3 — the positive control: the deck does detect series resistance

A null result is only evidence if the measurement could have come out
otherwise. `gen_extracted_switch_ron_tb.py --in-path-control` emits the same
deck with every device terminal moved onto its net's `__par` node — the
netlist the extraction **would** have written if its parasitic resistance were
in the signal path. At `tt_27c_3.30v`:

| measurement | drawn cell (as extracted) | in-path control | delta |
|---|---|---|---|
| `ron_t_f00` | 156.855 Ω | 353.08 Ω | **+196.2 Ω** |
| `ron_t_max` | 299.41 Ω | 495.821 Ω | +196.4 Ω |
| `ron_n_f00` (control branch) | 156.855 Ω | 156.855 Ω | 0 |

+196.2 Ω against the **196.566 Ω** the extraction assigns to those two nets
(`Rvin` 120.0326 Ω + `Rvout` 76.5336 Ω). The ~0.3 Ω residue is the channel
re-biasing: moving the source terminal onto the internal node shifts V_gs and
V_sb by I·R, so the transistor's own R_on moves slightly too. The gate nets'
53.1 Ω each contribute nothing, as expected for a DC gate current of zero.

So the measurement resolves in-path resistance at the ~0.1 Ω level, and would
have reported the drawn cell's 196.6 Ω had the extraction placed it in the
channel. It reports 0.000 Ω because the extraction does not.

## What this closes, and what it does not

**Closes**: §6.3's Input-structure R_on re-take, as a measured result rather
than an outstanding task. Post-layout worst-case transmission-gate R_on is
**570.436 Ω at `ss_125c_2.97v`**, unchanged from the schematic
characterization, and the T-gate flatness ratio is unchanged at 3.28898.

**Does not close, and now for a different reason than §6.3 stated**: the
`R_WORST_BIT_OHM` re-take that rate closure and the DR-0012/13 gain-error row
need. §6.3 attributed that block to missing leaf-cell geometry
(`adc_cdac_side.gds` does not exist). That is still true for the *array-level*
isolation `sim/dr0014-sampling/`'s Groups A/B/C need — but this record shows a
second, independent and more fundamental block underneath it: **even with the
geometry drawn and extracted, this extraction carries no in-path resistance
for a settling-resistance re-take to find.** Drawing `adc_cdac_side.gds` and
extracting it would not change that. Closing rate closure post-layout requires
an extraction flow that emits distributed or in-path net resistance, which is
an extractor capability, not a deck.

Per CLAUDE.md's no-relaxation rule, the affected rows stay reported as
not-measurable-post-layout rather than being backfilled with the schematic
number relabelled, or with a differently-scoped substitute. The schematic
`R_WORST_BIT_OHM` remains the ratified input to the timing budget, and it is
now known to be the *only* value this flow can supply.

**Tool friction** (CLAUDE.md's canary rule): the gap is generic to the open
flow — any post-layout R_on, IR-drop, electromigration or RC-settling question
hits it — and it is already reported upstream as
[`klayout-tools#338`](https://github.com/2AMLogic/klayout-tools/issues/338),
"extracted lumped-RC parasitics put the net resistance in series with the
net's ground capacitance, so no extracted R ever sits between a driver and its
receivers". That issue was closed **completed on 2026-08-03 as a
documentation-only fix**: its curation verified the topology directly against
`_inject_parasitics()` and deliberately scoped out both model changes
("star-topology split", "full distributed RC"), recommending "filing a
separate follow-up issue if/when there's appetite to implement Option 2".

**That follow-up does not exist as of 2026-08-06** — searched
`2AMLogic/klayout-tools` for "distributed RC", "star topology",
"parasitic resistance in path" and `_inject_parasitics`; #338 and the earlier
#216 are the only matches. Filing it is the open action this record leaves
behind, and it could not be done from the session that produced this record:
its token has `{"pull": false, "push": false}` on `2AMLogic/klayout-tools`, so
no issue could be created there. What to file, in one line: *`extract
--parasitics` should be able to emit net resistance between device terminals
(star split at minimum), so post-layout R_on / IR-drop / settling-resistance
questions are answerable — today every extracted R is a shunt stub and those
questions return the schematic answer by construction.*

Re-verified rather than assumed: the extraction audited above was produced by
the repo's own pinned build (`klt 0.2.0`, `layout/toolchain.json`,
`af5791b`), no follow-up capability issue exists upstream, and the audit is of
that build's actual output.

### A second, independent fidelity finding, surfaced while checking the first

While confirming the upstream status of the topology gap, a *different*
upstream issue turned up and was checked directly against the installed
build — `klayout-tools#547`, "gf180mcu `PARASITICS.metals` has one `LayerRC`
for a five-level metal stack, so Metal2..Metal5 silently contribute zero R and
C" (closed **completed 2026-08-05**). The pinned build this project extracts
with still has it:

```
$ "$(dirname "$(readlink -f "$(command -v klt)")")/python" -c \
    "from klayout_tools.decks import gf180mcu; \
     print(len(gf180mcu.EXTRACTION_DECK.metals), len(gf180mcu.PARASITICS.metals))"
5 1
```

Five metal levels in the extraction deck, **one** entry in the parasitics
table. `layout/adc-top/lib/geometry.py` draws on Metal1 **and** Metal2
(`L_METAL2 = (36, 0)`, the riser that crosses the device row) and up to
Metal4/Metal5 for the MiM plates — so every extracted parasitic in this
project's records is a **Metal1-only** number, and the true drawn parasitic is
larger.

This does not weaken this record's conclusion — it is about *where* the
extracted R sits, not how large it is, and a fixed magnitude on a stub is
still a stub. It does mean the §4 loading deltas in
`sim/extracted-delta-summary.md` should be read as **lower bounds**. The
follow-up is a toolchain-pin bump plus a re-run of the three §4 decks against
a `klt` that carries the #547 fix — a separate, bounded increment, not
something to silently fold into this one, and explicitly **not** a reason to
adjust any recorded number here (CLAUDE.md: records are append-only; a
re-measurement mints a new record with `Supersedes`).

## Artifacts in this record

- `reports/20260806-parasitic-topology/audit.md` — the topology table above
- `reports/20260806-parasitic-topology/audit.json` — per-net classification,
  including each net's resistance, capacitance and internal node
- `reports/20260806-parasitic-topology/tb_switch_ron_in_path_control.spice` —
  the exact positive-control netlist, header-labelled `!! POSITIVE CONTROL --
  NOT THE DRAWN CELL !!`
- `reports/20260806-parasitic-topology/in_path_control_tt_27c_3.30v.txt` —
  its measured row

Append-only per `sim/README.md`'s evidence rule: this record is never
overwritten.

---

## Addendum (2026-08-06, issue #116) — post-bump re-audit: RESOLVED

This record's own finding above (332 parasitic nets, 0 of them in-path) was
true of the `af5791b` pin. `layout/toolchain.json` is now bumped to
`875eac33dfbc004d2ab4dfcebc522734d159dc5f` (`klayout-tools#593`, the
star-topology split `#592` asked for). `audit_parasitic_topology.py` is
updated to detect and parse BOTH the old dead-end-stub shape and the new
per-terminal-leg shape (per netlist, not assumed) — see its own module
docstring and `sim/tests/test_parasitic_topology_audit.py`'s new
star-topology positive/negative-control tests.

Re-run against a fresh extraction of all four committed blocks at the new
pin (`layout/adc-top/parasitics/reports/20260806-225302-be02c85/`):

```
python3 layout/adc-top/parasitics/audit_parasitic_topology.py \
    layout/adc-top/parasitics/reports/20260806-225302-be02c85/adc_top.para.spice \
    layout/adc-top/parasitics/reports/20260806-225302-be02c85/adc_block.para.spice \
    layout/adc-top/parasitics/reports/20260806-225302-be02c85/adc_block_nores.para.spice \
    layout/adc-top/parasitics/reports/20260806-225302-be02c85/adc_tgate.para.spice
```

| netlist | parasitic nets | in-path R | stub R | total R (Ω) | max R (Ω) | total C (fF) |
|---|---|---|---|---|---|---|
| `adc_top.para.spice` | 156 | **156** | 0 | 117685.3 | 16013.5 | 5215.824 |
| `adc_block.para.spice` | 170 | **170** | 0 | 132708.4 | 20387.9 | 5548.248 |
| `adc_block_nores.para.spice` | 172 | **172** | 0 | 127273.5 | 18581.6 | 5437.420 |
| `adc_tgate.para.spice` | 4 | **4** | 0 | 302.8 | 120.0 | 9.235 |

**Result: 100% in-path, 0 stub, on every committed extraction.** The
positive-control discipline this record established (moving devices onto
the internal node and checking the classifier reports "in-path") is no
longer needed as an artificial construction to prove the classifier can see
in-path resistance -- the REAL extraction now IS that construction. The
total resistance figures also moved from this record's own table (e.g.
`adc_top.para.spice` 115319.7 Ω -> 117685.3 Ω) because the same pin bump
also re-curated the deck's Metal2-5 parasitics coefficients and corrected
its Metal5 sheet resistance (`klayout-tools#571`/`#579`, bundled in the
same 29-commit range as the star-split fix) -- a second, independent
magnitude change this addendum notes but does not separately re-derive
(flagged, not re-verified against the `#547` Metal2-5-coverage finding
§"A second, independent fidelity finding" above names).

**Consuming re-measurement**: `sim/device-switch-ron/`'s extracted deck,
re-run against this same post-bump `adc_tgate` extraction, now measures a
real, nonzero worst-case R_on delta (+13.57%, 570.436 Ω -> 647.818 Ω at
`ss_125c_2.97v`) -- see `sim/extracted-delta-summary.md` §6.3's second
status-update addendum and `sim/device-switch-ron/records/
20260806-225315-be02c85.md`.

### Artifacts in this addendum

- `reports/20260806-parasitic-topology-post116/audit.md` — the table above
- `reports/20260806-parasitic-topology-post116/audit.json` — per-net
  classification against the new topology (`legs` field replaces the old
  single `internal_node` field)

Append-only: this addendum is appended below the original record per
`sim/README.md`'s evidence rule, and the original record's own tables and
conclusions above are unedited.
