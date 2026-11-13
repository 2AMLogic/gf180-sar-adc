# DR-0045: DR-0023's "no 3.3 V-device standard-cell library" premise is false at open_pdks `f6eeac7` — its conclusion is re-affirmed on the corner-characterization gap instead

- **Status**: proposed
- **Date**: 2026-11-13
- **Decided by**: Builder agent, issue #765 — ratification-via-PR per
  `2AMLogic/2am#357` Class 1 standing policy: this record is proposed on its
  merits with sources shown, and the operator's PR approval is the
  ratification act (no separate sign-off comment).
- **Supersedes**: none. This record decides a **different question** from
  DR-0023 — whether DR-0023's decision survives the falsification of one of
  its supporting premises — and **re-affirms** that decision rather than
  replacing it. Per `README.md` § "Superseding a ratified record", a record
  that decides a different question about the same block "is a new,
  independent decision and leaves `Supersedes` empty, even when the two
  records are closely related". DR-0023's header is **not** edited: this
  directory defines only `Supersedes` / `Superseded by` links and no "amends"
  link, and DR-0044 is the precedent for a correcting record that adds no
  back-pointer.
- **Superseded by**: (none while this record stands)
- **Related**: #765, #757, PR #763, DR-0004, DR-0010, DR-0023, DR-0044,
  `design/sar-logic/README.md` § "Path to the netlist layout and LVS will use
  (#15)", `design/sar-logic/flow/flow_env.py` `CORNERS`,
  `spec/timing-budget-memo.md` §3.3

## Context

DR-0044 re-counted DR-0023's standard-cell device evidence under this
repository's current `open_pdks` pin and, in doing so, recorded one supporting
claim of DR-0023's that **no longer reproduces**: that the PDK ships no
3.3 V-device standard-cell library. DR-0044 deliberately left that open —
"A future record that wants to revisit DR-0023 starts here, with the
single-corner Liberty gap as the first thing to cost" — and issue #765 is the
tracked home for it. This record is that future record.

The question is narrow. A `proposed` record (DR-0023) awaiting the operator's
ratification rests, in part, on a premise that is false at the pinned PDK.
Either the conclusion falls with the premise, or it stands on other grounds
that must be stated. Nothing is simulated, synthesized, placed or re-timed
for this record: it is a read of the pinned PDK plus citations of evidence
already closed on `main`.

## The premise, as DR-0023 wrote it

DR-0023 states it twice. In its Context:

> **No 3.3 V-device standard-cell library exists in this PDK** — no GDS, no
> LEF, no Liberty, at any of the four installed PDK variants (A/B/C/D).

and in its first rejected alternative ("Hold DR-0004 as ratified; commission a
custom 3.3 V-device standard-cell library"):

> No GDS, LEF, or Liberty exists for a 3.3 V-device digital library in this
> PDK at any of the four installed variants

**Both statements are false at the PDK revision this repository now pins.**

## Evidence, re-taken under the pinned PDK

Pinned revision `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
(`docs/environment-setup.md` §3; `$PDK_ROOT/gf180mcuD/SOURCES`), re-run from
`$PDK_ROOT` on 2026-11-13:

```
$ ls gf180mcuD/libs.ref/
gf180mcu_fd_io  gf180mcu_fd_ip_sram  gf180mcu_fd_pr  gf180mcu_fd_sc_mcu7t5v0
gf180mcu_fd_sc_mcu9t5v0  gf180mcu_osu_sc_gp12t3v3  gf180mcu_osu_sc_gp9t3v3
$ ls -d gf180mcu{A,B,C,D}/libs.ref/gf180mcu_osu_sc_* | wc -l
8
$ ls -d gf180mcu{A,B,C,D}/libs.ref/gf180mcu_osu_sc_* | sed -n '1,2p'
gf180mcuA/libs.ref/gf180mcu_osu_sc_gp12t3v3
gf180mcuA/libs.ref/gf180mcu_osu_sc_gp9t3v3
```

Two OSU-sourced libraries, present at **all four** installed variants — so
the "at any of the four installed variants" qualifier does not rescue either
statement. Both are built from the 3.3 V device and nothing else:

```
$ grep -ohE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_osu_sc_gp9t3v3/spice/*.spice | sort | uniq -c
    270 nfet_03v3
    270 pfet_03v3
$ grep -ohE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_osu_sc_gp12t3v3/spice/*.spice | sort | uniq -c
    275 nfet_03v3
    275 pfet_03v3
```

540 and 550 device references, **zero `*_05v0`/`*_06v0` in either** — the
mirror image of DR-0044's count on `mcu7t5v0`/`mcu9t5v0` (4810 and 4816
references, zero `*_03v3`). And all three view classes DR-0023 named as
absent are present:

```
$ ls gf180mcuD/libs.ref/gf180mcu_osu_sc_gp9t3v3/ | tr '\n' ' '
gds lef lib mag maglef spice techlef verilog xschem
$ ls gf180mcuD/libs.ref/gf180mcu_osu_sc_gp12t3v3/ | tr '\n' ' '
gds lef lib mag maglef spice techlef xschem
```

`gp9t3v3` carries GDS, LEF, techLEF, Liberty **and** a Verilog view;
`gp12t3v3` carries the same minus `verilog`. The graded files:

| file (under `$PDK_ROOT/gf180mcuD/`) | sha256 |
|---|---|
| `libs.ref/gf180mcu_osu_sc_gp9t3v3/spice/gf180mcu_osu_sc_gp9t3v3.spice` | `b625b79062caac28a0782fd473c0d37c5a05028bcb94625090e1a3b113820846` |
| `libs.ref/gf180mcu_osu_sc_gp12t3v3/spice/gf180mcu_osu_sc_gp12t3v3.spice` | `12a0be9d71286eadc30a31a4156290e0fbdcf2ab85ce5f58cbc4b6454b573705` |
| `libs.ref/gf180mcu_osu_sc_gp9t3v3/lef/gf180mcu_osu_sc_gp9t3v3.lef` | `7a01bd22186bbaf1edb829c87e23f77c22eedbe79f6ec084af2ceca6b92e9a50` |
| `libs.ref/gf180mcu_osu_sc_gp12t3v3/lef/gf180mcu_osu_sc_gp12t3v3.lef` | `f340d2ae067bba68fda583743360a19d92b4a11403cf688ca5a8066e9fb8ca1e` |

## The corner gap: what the OSU libraries ship vs. what the ratified grid needs

Each OSU library ships **exactly one** Liberty file; `mcu7t5v0` ships 15, of
which five are at this block's 3.3 V rail family:

```
$ ls gf180mcuD/libs.ref/gf180mcu_osu_sc_gp9t3v3/lib/
gf180mcu_osu_sc_gp9t3v3__tt_025C_3v30.lib
$ ls gf180mcuD/libs.ref/gf180mcu_osu_sc_gp12t3v3/lib/
gf180mcu_osu_sc_gp12t3v3__tt_025C_3v30.lib
$ ls gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/ | wc -l
15
```

The three corners DR-0023 ratified as this block's STA grid
(`design/sar-logic/flow/flow_env.py` `CORNERS[0:3]`, each annotated
"DR-0023-named") against what is characterized:

| corner | DR-0023's grid | `mcu7t5v0` | `gp9t3v3` | `gp12t3v3` |
|---|---|---|---|---|
| `tt_025C_3v30` | required | ships | ships | ships |
| `ss_125C_3v00` (worst-case setup) | required | ships | **absent** | **absent** |
| `ff_n40C_3v60` (worst-case hold) | required | ships | **absent** | **absent** |

sha256 of every Liberty file in that table:

| Liberty file | sha256 |
|---|---|
| `gf180mcu_osu_sc_gp9t3v3/lib/…__tt_025C_3v30.lib` | `e25078de3cdfbda6945164f63ec9df7ddf3f76e5da8473a7c66efcb0705fd83c` |
| `gf180mcu_osu_sc_gp12t3v3/lib/…__tt_025C_3v30.lib` | `c773ee164eb71e6528ae2003e47197c61e959cc7ab7177540b2247f5cb8da3bf` |
| `gf180mcu_fd_sc_mcu7t5v0/lib/…__tt_025C_3v30.lib` | `f9dee07cf158324934b0c59144d970a2e8313f43533ede6283ec3c136f82fe53` |
| `gf180mcu_fd_sc_mcu7t5v0/lib/…__ss_125C_3v00.lib` | `5d2f37ba6f43e33aeba26dc1da55c96394a862eeec4148043f1d48bdf65ccea6` |
| `gf180mcu_fd_sc_mcu7t5v0/lib/…__ff_n40C_3v60.lib` | `a222740b574d0699c8a416400bd9746ecb8556bc87a515ab7fb80f911e2cd74b` |

No other characterization of these libraries exists anywhere in the PDK, at
any variant — not under another name, not in a `.db`:

```
$ find -L gf180mcu{A,B,C,D} -iname '*osu*' \( -name '*.lib' -o -name '*.db' \) | wc -l
8
$ find -L gf180mcu{A,B,C,D} -iname '*osu*' -name '*.lib' -exec basename {} \; | sort -u
gf180mcu_osu_sc_gp12t3v3__tt_025C_3v30.lib
gf180mcu_osu_sc_gp9t3v3__tt_025C_3v30.lib
```

Eight files = two libraries × four variants, one corner each. (`find -L` is
required, not cosmetic: `$PDK_ROOT/gf180mcu{A,B,C,D}` are symlinks into
`ciel/gf180mcu/versions/`, so a bare `find` treats each as one file, descends
into none of them and prints nothing.)

**The PDK's own flow configuration says the same thing.** Its librelane
library configs declare an STA corner list per standard-cell library; the two
OSU configs override the PDK default down to the single corner they ship:

```
$ grep -A3 'STA_CORNERS' gf180mcuD/libs.tech/librelane/gf180mcu_osu_sc_gp9t3v3/config.tcl
set ::env(STA_CORNERS) "\
    nom_tt_025C_3v30 \
"
$ grep -A12 'STA_CORNERS' gf180mcuD/libs.tech/librelane/config.tcl
set ::env(STA_CORNERS) "\
nom_tt_025C_5v00 \
nom_ss_125C_4v50 \
nom_ff_n40C_5v50 \
min_tt_025C_5v00 \
min_ss_125C_4v50 \
min_ff_n40C_5v50 \
max_tt_025C_5v00 \
max_ss_125C_4v50 \
max_ff_n40C_5v50 \
"

set ::env(DEFAULT_CORNER) "nom_tt_025C_5v00"
```

(`gp12t3v3`'s config is byte-identical in this respect.) The root list is the
PDK's **5 V-rail** default (three PVT points × three RC extractions) and is
quoted only to show that the per-library OSU setting is a *narrowing* of a
multi-corner default to one corner — it is not this block's 3.3 V grid, which
DR-0023 fixes in `flow_env.py` and which `mcu7t5v0`'s 15 Liberty files
support. The load-bearing fact remains the one Liberty file per OSU library;
the config corroborates it from the PDK's side. So a multi-corner STA grid on
an OSU library is not merely uncharacterized in this repository's flow — it
is not expressible in the PDK's own shipped flow configuration either.

## Decision

1. **The premise is corrected, on the record.** DR-0023's two statements
   quoted above are false at `open_pdks f6eeac7`: the PDK ships two
   3.3 V-device standard-cell libraries, with GDS, LEF, techLEF and Liberty,
   at all four installed variants. Live prose in this repository that repeats
   the premise as current fact is corrected to match (see "Spec lines
   affected"); DR-0023's and DR-0044's bodies are **not** edited, per this
   directory's append-only rule.

2. **DR-0023's decision is re-affirmed.** The SAR-logic sequencer and digital
   interface continue to use `gf180mcu_fd_sc_mcu7t5v0` at the block's 3.3 V
   rail. Nothing in this repository is re-targeted at an OSU library. The
   re-affirmation rests on grounds that do **not** depend on the false
   premise, each sourced:

   - **The ratified STA grid cannot be run on them.** DR-0023's grid needs
     `ss_125C_3v00` and `ff_n40C_3v60`; neither OSU library ships either, and
     no other characterization of them exists in the PDK (table and `find`
     above). `sar_ctrl`'s closed sign-off is a three-corner post-route STA
     with SPEF; on an OSU library two of those three corners could not be
     run at all without a characterization campaign nobody has done. This is
     the decisive ground, and it is the one DR-0044 predicted would cost the
     most.
   - **DR-0023's electrical argument never depended on the premise.** "A
     6 V-oxide transistor operating at a 3.3 V rail is well within its
     voltage rating" is a claim about the device actually chosen, confirmed
     by DR-0044's model-card evidence (`*fet_05v0` binds the `*fet_06v0`
     model card). Falsifying "no alternative exists" does not touch "the
     thing we chose is sound".
   - **The whole closed evidence base is on `mcu7t5v0`.** Synthesis, P&R,
     post-route STA with SPEF, cell DRC and LVS for `sar_ctrl` are all closed
     against `mcu7t5v0` (`design/sar-logic/flow/sar_ctrl/records/`,
     `sim/requalification-596-sar-logic.md`). Re-targeting discards that
     evidence; keeping it costs nothing.
   - **`gp12t3v3` ships no Verilog view**, so the gate-level functional
     verification path would have to change for that library. (`gp9t3v3`
     *does* ship one — this ground applies to one of the two libraries, not
     both, and is secondary to the corner gap.)

3. **Two sub-claims in circulation are corrected, because this record will
   not re-affirm on a ground that does not hold.** DR-0044's "51 cells each"
   is the LEF/SPICE count; the Liberty files carry 44 (`gp9t3v3`) and 43
   (`gp12t3v3`) `cell (` entries. **That gap is benign and is not a ground
   for anything**: every cell in it is a physical-only or special cell that
   legitimately carries no timing arc —

   ```
   $ cd $PDK_ROOT/gf180mcuD/libs.ref/gf180mcu_osu_sc_gp9t3v3
   $ comm -23 <(grep '^MACRO' lef/*.lef | awk '{print $2}' | sort -u) \
              <(grep -oE '^[[:space:]]*cell *\([^)]*\)' lib/*.lib \
                | sed -E 's/.*\([[:space:]]*"?([^")]*)"?[[:space:]]*\)/\1/' | sort -u) \
       | sed 's/gf180mcu_osu_sc_gp9t3v3/…/'
   …__ant
   …__antfill
   …__fill_1
   …__fill_16
   …__fill_2
   …__fill_4
   …__fill_8
   ```

   antenna-diode and filler cells for `gp9t3v3` (the PDK's own config assigns
   exactly these as `DIODE_CELL` / `FILL_CELLS` / `FP_WELLTAP_CELL`), plus
   `__lshifdown` / `__lshifup` for `gp12t3v3`. "Some LEF cells have no
   Liberty timing" is therefore **withdrawn as a re-affirming ground**; the
   corner gap stands on its own.

4. **No number, bound, margin or budget is re-derived or relaxed here.** No
   netlist, flow script, Liberty path, corner list or testbench changes. The
   only edits are the new record and prose that repeats the false premise.

## What the false premise did, and did not, carry

DR-0023 used the premise to reject **"commission a custom 3.3 V-device
standard-cell library"** — an alternative whose cost was "cell layout,
characterization, LEF/Liberty generation, verification". At `f6eeac7` that is
no longer the relevant alternative, because two such libraries already exist.
The corrected alternative is **"retarget `sar_ctrl` to a shipped OSU 3.3 V
library"**, and it is rejected below on its own cost, not on the claim that
it is impossible. Three sentences of DR-0023's reasoning change character:

- Its Context's "no 3.3 V-device standard-cell library exists in this PDK" is
  **false** and is corrected here.
- Its rejected alternative's "no GDS, LEF, or Liberty exists" is **false**
  and is corrected here.
- Its Consequences' "inherently worse on both axes than a purpose-built
  3.3 V-device library would be" is **unaffected** — it is a statement about
  the cost paid, not about availability, and the OSU libraries' existence
  makes the comparison concrete rather than hypothetical.

DR-0023's **Decision** section does not cite the premise at all. That is why
correcting it does not reverse the decision.

## Not determined: were the OSU libraries present at `c6d73a3`?

**Not determined, and not guessed.** DR-0023 graded `open_pdks c6d73a3`;
this record cannot say whether it would have found these libraries. Checkable
reasons:

```
$ ls ~/.ciel/ciel/gf180mcu/versions/
f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7
```

`c6d73a3` is not installed on this host, and no committed artifact in this
repository carries a `libs.ref/` listing for it (`git grep -l c6d73a3` hits
prose and records that cite the revision, none that enumerate its
directories). The question is answerable by anyone who installs `c6d73a3` and
runs the `ls` above, and is **deliberately left open** rather than inferred
from the re-pin: installing a superseded PDK revision to settle the
provenance of a premise that is false *today* changes no decision this record
makes. It matters only for attributing DR-0023's error between "the libraries
arrived with the re-pin" and "they were overlooked", which this record does
not need to do and does not do.

## Alternatives considered

- **Retarget `sar_ctrl` to `gf180mcu_osu_sc_gp9t3v3` (or `gp12t3v3`) now** —
  not chosen, and the reason is a bill, not an impossibility. Two of the three
  ratified STA corners do not exist for these libraries, so this requires a
  characterization campaign (cell-level SPICE characterization at
  `ss_125C_3v00` and `ff_n40C_3v60`, Liberty generation, validation) that no
  tooling in `klayout-tools` or the PDK's own flow configuration currently
  supports, followed by a resynthesis, re-P&R, re-STA, re-DRC and re-LVS of
  `sar_ctrl` — discarding a closed sign-off chain to buy an area/capacitance
  improvement no spec row requires. The sequencer already shows ~40 ns of
  slack per 62.5 ns bit cycle. A device-flavor reversal is also not a
  Builder's call (issue #765 is explicit), so even a favourable cost estimate
  would land as a proposal, not as this record.
- **Characterize the OSU libraries at the two missing corners, then decide** —
  not chosen *now*. It is the one piece of work that would make the
  alternative live, and it is correspondingly expensive; nothing in the
  current spec or margin picture motivates spending it. Recorded here as the
  named precondition for anyone who wants to reopen the question, so the next
  record does not have to rediscover it.
- **Leave DR-0044's "Open question" as the only record of the discrepancy** —
  not chosen. DR-0044 itself says a future record "starts here", and a
  known-false premise inside a record awaiting ratification is debt that a
  reader of `spec/` cannot see without reading two records and an issue. This
  repository is public and exists to be checked.
- **Amend DR-0023 in place** — not chosen. Records are never rewritten
  (`README.md`), and DR-0023's evidence is correct for the revision it
  graded. DR-0044 set this precedent for exactly this situation.
- **Reverse DR-0023 and reopen the device-flavor question without
  re-targeting anything** — not chosen. Reopening a decision while leaving
  every artifact pointed at the old answer produces a repository whose spec
  and implementation disagree, which is worse than either resolving it or
  leaving it closed. The corner gap means the evidence points at "closed", so
  it is recorded closed.

## Consequences

- **DR-0023's ratification is unblocked on this point.** The operator can
  ratify it knowing which of its supporting statements is false, why that does
  not move its conclusion, and where the correction lives. Before this record,
  ratifying DR-0023 meant ratifying a record with a known-false premise and no
  record saying so.
- **The corner gap is now the named, costed precondition** for anyone
  revisiting the device flavor: characterize `ss_125C_3v00` and
  `ff_n40C_3v60` for the chosen OSU library first, or propose a different
  STA grid through `spec/`. That is a cheaper starting point than DR-0044's
  open question gave.
- **Bad consequence, stated plainly**: this record re-affirms a decision whose
  originally-stated justification was partly wrong, which is a weaker position
  than a decision that was right for the right reasons. A reader is entitled
  to ask whether the 3.3 V-device option would have been chosen in 2026-08 had
  the OSU libraries been noticed then. This record cannot answer that — see
  "Not determined" — and does not pretend the re-affirmation is evidence that
  the original reasoning was sound. It is evidence that the *outcome* survives
  on different grounds.
- **Second bad consequence**: the repository now carries three records
  (DR-0023, DR-0044, DR-0045) on one device-flavor question, and a reader must
  read all three to know what is in force. That is the cost of the
  append-only rule, paid deliberately rather than by rewriting DR-0023.
- **One re-affirming ground was withdrawn during this work** (the Liberty
  cell-count gap, §Decision 3). Recording the withdrawal rather than quietly
  dropping it is the point: a future record that re-reads this one should not
  re-inherit a ground this one checked and rejected.
- No `sim/` record, `signoff/` record, flow script, Liberty path, corner list
  or testbench is touched, so no closed evidence is invalidated and nothing
  needs re-running.

## Spec lines affected

- `spec/timing-budget-memo.md#33-t_logic_delay--still-open-flagged-not-silently-absorbed`
  — the standard-cell library-availability citation — clarified (no value
  change): "the open gf180mcu PDK ships no 3.3 V-device standard-cell
  library" becomes the true statement of why rung 3 is blocked (the shipped
  3.3 V libraries are single-corner), with a pointer to this record. No
  budget, bound, margin or ratified value in that memo changes, and DR-0010's
  quoted options paraphrase is left verbatim. This is the same
  clarified-no-value-change edit DR-0044 made to the same section.
- `README.md#target-specification` — none. Device flavor has no spec-table
  representation, consistent with DR-0004's, DR-0023's and DR-0044's own
  "Spec lines affected" entries.

Non-spec prose corrected by this record (same false premise, outside `spec/`):
`design/sar-logic/README.md` § "Path to the netlist layout and LVS will use
(#15)", `design/sar-logic/rtl/README.md`, and
`docs/chipalooza/challenge-3-proposal.md` §3. All four sites — those three plus
the memo above — carried the premise as current fact; three now carry the
qualified form

> no 3.3 V-device standard-cell library in the open gf180mcu PDK is
> characterized across this block's ratified STA corner set

and the Chipalooza proposal names the single-corner limit directly. Note for
anyone auditing by grep: the substring "no 3.3 V-device standard-cell library"
**still appears** at those sites, now as the opening of the qualified sentence
above rather than as an assertion. A grep for the bare phrase is therefore not
a sufficient check; read the qualifier that follows it.
