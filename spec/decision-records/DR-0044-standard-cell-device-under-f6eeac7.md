# DR-0044: DR-0023's standard-cell device re-counted under open_pdks `f6eeac7` — the device is unchanged, only its subcircuit name moved

- **Status**: proposed
- **Date**: 2026-11-13
- **Decided by**: Builder agent, issue #757
- **Supersedes**: none. DR-0023's decision text is **not** edited and its
  conclusion is **not** changed by this record; this record re-states
  DR-0023's supporting evidence under the PDK revision this repository now
  pins, and records one supporting claim of DR-0023's that no longer
  reproduces (see "Open question", which this record does **not** resolve).
- **Superseded by**: (none while this record stands)
- **Related**: #757, #596, #754, PR #756, DR-0004, DR-0010, DR-0023, DR-0027,
  `docs/environment-setup.md` §3, `sim/requalification-596-sar-logic.md`

## Context

`sim/toolchain.json`'s `open_pdks` pin moved `c6d73a3` -> `f6eeac7` (#514 /
#517). PR #756 regenerated the seven gate-level decks under the new pin and
found that every standard-cell instance now binds `nfet_05v0`/`pfet_05v0`
where it previously bound `nfet_06v0`/`pfet_06v0`, with every `W` and `L`
unchanged. DR-0023's evidence for adopting the shipped libraries is a device
count quoted by device name, so the question this record answers is narrow and
factual: **does DR-0023's evidence still reproduce under `f6eeac7`, and does
its conclusion still hold?** Nothing was simulated for this record; it is a
re-count and a read of the pinned PDK.

## Evidence, re-taken under the pinned PDK

Pinned revision `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
(`docs/environment-setup.md` §3; `$PDK_ROOT/gf180mcuD/SOURCES`), the same
reduction DR-0023 ran, re-run verbatim from `$PDK_ROOT`:

```
$ grep -oE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice \
    | sort | uniq -c
   2403 nfet_05v0
   2407 pfet_05v0
$ grep -oE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0/spice/gf180mcu_fd_sc_mcu9t5v0.spice \
    | sort | uniq -c
   2411 nfet_05v0
   2405 pfet_05v0
```

4810 and 4816 device references, **zero `*_03v3` in either** — against
DR-0023's `c6d73a3` counts of 4809 (2403 + 2406) and 4816 (2411 + 2405). The
graded files:

| file | sha256 |
|---|---|
| `libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice` | `0e126c5e10e45e705a83acfa47f6fd2c4ef0357e99c339dec43cdc16bfb13664` |
| `libs.ref/gf180mcu_fd_sc_mcu9t5v0/spice/gf180mcu_fd_sc_mcu9t5v0.spice` | `415d693a8eb35efd744495484c162b8926e7f72c1d4995d7ce16952c8a58d658` |
| `libs.tech/ngspice/sm141064.ngspice` | `f6f4a96e18fc5ad11270ad3451aaecc7ac37fc81eb61e15b0d7d94c7bc594a24` |

**`*fet_05v0` is not a different transistor.** In the pinned model library
`nfet_05v0`/`pfet_05v0` are `.subckt` wrappers whose single MOS instance binds
the `nfet_06v0`/`pfet_06v0` *model card*:

```
$ sed -n '46959,46972p;46987,47000p' gf180mcuD/libs.tech/ngspice/sm141064.ngspice
.subckt nfet_05v0 d g s b w=1e-6 l=6e-7 ...
...
m0 d g s b nfet_06v0 ad=ad as=as ... w=w
.ends nfet_05v0
.subckt pfet_05v0 d g s b w=1e-5 l=5e-7 ...
...
m0 d g s b pfet_06v0 ad=ad as=as ... w=w
.ends pfet_05v0
$ grep -oE '^\s*\.model\s+(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.tech/ngspice/sm141064.ngspice | awk '{print $2}' | sort | uniq -c
     96 nfet_03v3
      2 nfet_06v0
      2 nfet_06v0_nvt
     96 pfet_03v3
      2 pfet_06v0
```

There is **no `nfet_05v0`/`pfet_05v0` model card in the PDK at all** — the
`_05v0` and `_06v0` names are two rated-voltage views of one thick-oxide
(`Dualgate`) device, which is also how the PDK's own technology description
reads it: `libs.tech/klayout/tech/gf180mcu.lyt` says *"GLOBALFOUNDRIES 0.18UM
3.3V/(5V)6V MCU TECHNOLOGY"*. The `_05v0` wrappers differ from the `_06v0`
wrappers only in their *default* `w`/`l`, and the standard-cell netlists carry
an explicit `W=`/`L=` on every instance, so even that difference is inert
here.

## Decision

1. **DR-0023's conclusion stands unchanged.** The SAR-logic sequencer and
   digital interface continue to use the PDK-shipped
   `gf180mcu_fd_sc_mcu7t5v0` / `mcu9t5v0` libraries at the block's 3.3 V rail.
   The re-pin renamed the subcircuit the cells bind; it did not change the
   device, the oxide, the `W`/`L` of any instance, or the Liberty corner set.
   DR-0023's "a 6 V-oxide transistor operating at a 3.3 V rail is well within
   its voltage rating" argument is unaffected, because the model card behind
   `*fet_05v0` *is* the 6 V-oxide model card.
   PR #756's own signoff record
   (`signoff/records/20261113-093700-a699814d.md`) describes the swap as going
   "from the 6V-oxide device to the 5V-oxide one"; the model-card evidence
   above says that reading is wrong in one respect — there is no distinct 5 V
   device to have moved to. That record is append-only and is not edited; this
   is the correction.
2. **Live prose cites the device by the name the pinned library actually
   uses** (`nfet_05v0`/`pfet_05v0`), and says "thick-oxide" where it used to
   say "6 V-oxide" as a *device-flavor* label, so a reader grepping the
   committed decks for the cited name finds it. Where the physical claim
   itself is what is being made ("a 6 V-oxide device run at 3.3 V is within
   rating"), the wording is left alone — it is still true.
3. **No timing, area or margin number is re-derived or relaxed by this
   record.** Every `W`/`L` is unchanged, so nothing downstream of the device
   count moves. DR-0027's leakage reference point, DR-0024's area
   re-check note and the timing-budget memo's bounds are untouched.

## Open question — NOT resolved here

DR-0023's rejected alternative states: *"No GDS, LEF, or Liberty exists for a
3.3 V-device digital library in this PDK at any of the four installed
variants"*, and its Context states *"**No 3.3 V-device standard-cell library
exists in this PDK**"*. **That claim does not reproduce at `f6eeac7`.** All
four installed variants (A/B/C/D, all at `f6eeac7`) ship two OSU-sourced
3.3 V-device libraries:

```
$ ls gf180mcuD/libs.ref/
gf180mcu_fd_io  gf180mcu_fd_ip_sram  gf180mcu_fd_pr  gf180mcu_fd_sc_mcu7t5v0
gf180mcu_fd_sc_mcu9t5v0  gf180mcu_osu_sc_gp12t3v3  gf180mcu_osu_sc_gp9t3v3
$ grep -ohE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_osu_sc_gp9t3v3/spice/*.spice | sort | uniq -c
    270 nfet_03v3
    270 pfet_03v3
$ ls gf180mcuD/libs.ref/gf180mcu_osu_sc_gp9t3v3/lib/
gf180mcu_osu_sc_gp9t3v3__tt_025C_3v30.lib
```

Both (`gp9t3v3`, `gp12t3v3`; 51 cells each) carry GDS, LEF, techLEF and
Liberty, and are built entirely from `nfet_03v3`/`pfet_03v3` — i.e. they are
exactly the thing DR-0023 said does not exist. **They also ship a single
Liberty corner, `tt_025C_3v30`**, where DR-0023's ratified STA grid needs
`ss_125C_3v00` and `ff_n40C_3v60` as well (`gf180mcu_fd_sc_mcu7t5v0` ships
15 corners), and `gp12t3v3` ships no Verilog view.

This record **does not** reopen DR-0023 on that basis, and nothing in the
repository is re-targeted at these libraries. What is recorded here is the
discrepancy, stated plainly:

- Whether these libraries were absent at `c6d73a3` and arrived with the
  re-pin, or were present and overlooked when DR-0023 was written, **is not
  determinable from this host** — `c6d73a3` is not installed, and no
  committed artifact in this repository carries its `libs.ref/` listing.
- Re-opening the device-flavor decision would require corner characterization
  these libraries do not ship, a resynthesis, a re-P&R and a re-STA of
  `sar_ctrl` — i.e. its own issue with its own evidence, not a paragraph in a
  re-count record. Choosing a device flavor is explicitly out of scope for
  #757.

A future record that wants to revisit DR-0023 starts here, with the
single-corner Liberty gap as the first thing to cost.

## Alternatives considered

- **Search-and-replace `06v0` -> `05v0`, including the physical "6 V-oxide"
  phrasing** — not chosen. "6 V-oxide" is a claim about the gate oxide and is
  still true: the PDK has one thick-oxide model card and `*fet_05v0` binds it.
  Rewriting those sentences to "5 V-oxide" would replace a true statement with
  a false one to chase a filename.
- **Leave the prose alone, since the physics did not change** — not chosen.
  The device *names* in `design/sar-logic/README.md`, the generator docstring
  and the `tb.json` manifest note are cited as reproducible evidence
  ("verified by counting device references"), and that reduction no longer
  reproduces as written. A citation a reader cannot re-run is the defect,
  whether or not the underlying physics moved.
- **Amend DR-0023 in place to say `*fet_05v0`** — not chosen. Decision records
  are never rewritten (`spec/decision-records/README.md`); DR-0023's evidence
  is correct *for the PDK revision it graded*, which is exactly what an
  append-only record is for.
- **Re-open the device-flavor decision now, on the OSU 3.3 V libraries** —
  not chosen, and deliberately not pre-judged either way. See "Open question".

## Consequences

- `layout/lvs/run_sar_ctrl_lvs.py`'s `wrong_width()` negative control, which
  anchored a regex on `pfet_06v0` and raises `RuntimeError` on a non-match,
  **would have crashed the whole LVS runner** under `f6eeac7` — the device
  flavor is no longer part of its anchor, and a unit test
  (`sim/tests/test_run_sar_ctrl_lvs_wrong_width.py`) now pins both the match
  and the loud-failure behaviour so the next re-pin cannot re-break it
  silently. This unblocks #754's LVS re-qualification from a defect it would
  otherwise have hit first.
- Records already under `sim/*/records/` keep their `6V-oxide` notes: they are
  accurate for the instrument they measured, and `sim/` is append-only. The
  *manifest* note is corrected so that records minted from here on do not copy
  a citation that no longer reproduces.
- **Bad consequence, stated plainly**: this record leaves a known discrepancy
  in a `proposed` ratified-by-PR record (DR-0023) unreconciled — its rejected
  alternative rests on a premise that is false at the pinned PDK. That is a
  real debt, carried openly under "Open question" rather than closed by a
  Builder picking a device flavor, because reversing DR-0023 is a spec
  decision with a characterization bill attached and no measurement here
  supports taking it.
- `sim/timing-budget-closure/testbench/tb.json`'s note is **left as written**:
  it reports what *DR-0010 states* ("DR-0010 states … the open gf180mcu
  standard-cell libraries are 6 V-oxide only"), an attributed historical
  quotation, not an assertion about the library content today. Correcting a
  decision record's finding inside a testbench manifest is the wrong place for
  it; the correction lives here.

## Spec lines affected

- `spec/timing-budget-memo.md#33-t_logic_delay--still-open-flagged-not-silently-absorbed`
  — the standard-cell device citation — clarified (no value change): the library
  device reference moves `nfet_06v0`/`pfet_06v0` -> `nfet_05v0`/`pfet_05v0`
  with a pointer to this record. No budget, bound, margin or ratified value in
  that memo changes, and the DR-0010 options paraphrase that follows it is
  left verbatim.
- `README.md#target-specification` — none. Device flavor has no
  spec-table representation, consistent with DR-0004's and DR-0023's own
  "Spec lines affected" entries.
