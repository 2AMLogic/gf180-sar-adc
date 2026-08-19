# DR-0023: Digital-interface device flavor — adopt shipped 6 V-oxide cells

- **Status**: proposed
- **Date**: 2026-08-19
- **Decided by**: Builder agent, issue #171 — ratification-via-PR per
  `2AMLogic/2am#357` Class 1 standing policy: this record is proposed on its
  merits with sources shown, and the operator's PR approval is the
  ratification act (no separate sign-off comment).
- **Supersedes**: DR-0004, digital-interface / SAR-logic clause only. DR-0004's
  analog-signal-path clause is **not** superseded — see "Scope of this
  supersession" below. DR-0004's `Status`/`Superseded by` back-pointer is
  edited **at ratification, not by this proposed record** (matching
  DR-0017's precedent for a still-`proposed` superseding record).
- **Superseded by**: (none while this record stands)
- **Related**: #169, #171, `2AMLogic/2am#357`, DR-0001, DR-0002, DR-0004,
  DR-0008, DR-0010, `design/sar-logic/README.md` §"Path to the netlist layout
  and LVS will use (#15)", `layout/adc-top/README.md` area table

## Context

DR-0004 ratified "3.3 V devices throughout … analog signal path **and** SAR
logic / digital interface," reasoning that gf180mcu ships no sub-3.3 V core
logic flavor, so single-supply 3.3 V was "not a choice among comparable
alternatives — it is the only flavor this PDK offers that fits the design at
all." That reasoning is still correct for the *analog* path (forced
independently by the 0–3.3 V input range, DR-0001, and by V_REF = 3.3 V,
DR-0002) but was wrong for the *digital* path on one point DR-0004 did not
check: gf180mcu's standard-cell libraries. #169 (re-confirmed here) found
that the open gf180mcu PDK's only two digital standard-cell libraries —
`gf180mcu_fd_sc_mcu7t5v0` and `gf180mcu_fd_sc_mcu9t5v0` — are built entirely
from `nfet_06v0`/`pfet_06v0` devices, not `nfet_03v3`/`pfet_03v3`. Verified
directly against the pinned toolchain (open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, `docs/environment-setup.md`) for
this reduction:

```
$ grep -oE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice \
    | sort | uniq -c
   2403 nfet_06v0
   2406 pfet_06v0
$ grep -oE '\b(nfet|pfet)_[0-9a-z_]+' \
    gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0/spice/gf180mcu_fd_sc_mcu9t5v0.spice \
    | sort | uniq -c
   2411 nfet_06v0
   2405 pfet_06v0
```

4809 and 4816 device references respectively, zero `*_03v3` in either —
matching #169's counts exactly. Both libraries' Liberty corner sets
(`gf180mcu_fd_sc_mcu{7,9}t5v0__{tt_025C_3v30,ss_125C_3v00,ff_n40C_3v60}.lib`,
confirmed present) are characterized for this block's 3.3 V supply grid —
i.e. gf180mcu ships 6 V-oxide digital cells meant to run at a 3.3 V rail, not
3.3 V-device digital cells. **No 3.3 V-device standard-cell library exists in
this PDK** — no GDS, no LEF, no Liberty, at any of the four installed PDK
variants (A/B/C/D).

DR-0004's ratified text and the PDK's actual cell inventory cannot both hold
as written. Per #169's verdict table (closing comment,
`2AMLogic/gf180-sar-adc#169`, 2026-08-15): Item 1 (Design sources) FAILs on
the digital column — no RTL, no synthesized gate netlist; Item 2 (Layout)
FAILs — the sequencer footprint is reserved and ringed
(`layout/adc-top/README.md`) but not drawn, because there is no
transistor-level netlist to place; Item 5 (Full corner verification) is
N/A-by-construction — no gate netlist exists to run STA against. All three
trace to this one root cause. `design/sar-logic/README.md` §"Path to the
netlist layout and LVS will use (#15)" states plainly that resolving this
"is a real decision that a future record has to make. It is not made here" —
this record is that future record.

De-parked from `loom:operator-only` per the operator's 2026-08-19 batch
ruling (`2AMLogic/2am#357`, Class 1): "for canary spec/DR ratification and
decision-record operator questions, a builder drafts the ratification/DR as
a PR on the evidence, and the operator's PR approval is the ratification
act. Values are proposed on their merits with sources shown — never relaxed
to make results pass."

## Scope of this supersession

DR-0004 bundled two device-flavor questions under one heading because, at
the time, both resolved to the same answer for the same PDK-inventory
reason. They are separable questions and this record revises only one of
them:

- **Analog signal path** (track switch, CDAC, comparator input): **unchanged**.
  Still forced to `nfet_03v3`/`pfet_03v3` independently, by the 0–3.3 V input
  range (DR-0001) and V_REF = 3.3 V (DR-0002) — neither of those records
  depends on standard-cell availability, and 3.3 V-device transistors for
  custom analog layout are fully available in this PDK (verified in DR-0004
  itself). DR-0004's ratification of this clause remains in force.
- **SAR logic / digital interface**: **revised by this record**, below.

## Decision

**Supersede DR-0004's digital-interface clause. The SAR-logic sequencer and
digital interface use the PDK-shipped 6 V-oxide standard-cell libraries
(`gf180mcu_fd_sc_mcu7t5v0` and/or `gf180mcu_fd_sc_mcu9t5v0`), running at the
block's existing 3.3 V digital supply rail — not 3.3 V-device cells.**

This is electrically sound, not a compromise dressed up as one: a 6 V-oxide
transistor operating at a 3.3 V rail is well within its voltage rating (the
reverse — a 3.3 V-device transistor forced onto a rail above its rating —
would be the unsafe direction), and both libraries' Liberty corners
(`tt_025C_3v30`, `ss_125C_3v00`, `ff_n40C_3v60`) are characterized at exactly
this rail, so no re-characterization or margin study is needed to use them
as shipped. The choice between the 7-track (`mcu7t5v0`) and 9-track
(`mcu9t5v0`) footprint is a synthesis/P&R density-vs-yield tradeoff, not a
device-flavor question — it is explicitly **left open**, deferred to the
RTL/synthesis follow-on issue this record's ratification unblocks (see
"Consequences").

Tooling to consume this decision already exists and needs bring-up, not new
development: `klayout-tools` `main` (`8cdaa3d`, confirmed present and wired
into the CLI parser as of this writing) ships `klt synthesize`, `klt
place-and-route`, `klt sta`, and `klt functional-verification` subcommands
(`src/klayout_tools/cli/{synthesize,place_and_route,sta,functional_verification}_cmd.py`),
i.e. once this device-flavor question is answered, the RTL→gate-netlist→P&R→STA
flow to consume the chosen library plausibly already exists upstream.

## Alternatives considered

- **Hold DR-0004 as ratified; commission a custom 3.3 V-device standard-cell
  library** — not chosen. No GDS, LEF, or Liberty exists for a 3.3 V-device
  digital library in this PDK at any of the four installed variants; building
  one (cell layout, characterization, LEF/Liberty generation, verification)
  is a multi-issue undertaking with no existing tooling support in
  `klayout-tools`, disproportionate to a sequencer whose rung-1 model already
  shows ~40 ns of slack per 62.5 ns bit cycle (`spec/prior-art-survey.md`
  §4.2) — there is no performance reason a bespoke library would buy back
  that the shipped 6 V-oxide cells don't already satisfy.
- **Scope the digital partition out of this block's taped-out deliverable
  entirely** — not chosen. This would leave Items 1, 2, and 5 permanently
  N/A rather than resolved, contradicts DR-0008's synchronous-SAR decision
  (which assumes a real gate-level sequencer exists to close timing against)
  and DR-0010's stated sign-off path (rung 3 = "the synthesized/hand-built
  gate netlist… feeding #15"), and defers indefinitely a decision the PDK's
  actual inventory already answers unambiguously.
- **Mixed 6 V-oxide digital / 3.3 V-device analog with a level-shifted
  boundary at a different rail** — not chosen. Not needed: the 6 V-oxide
  cells' own Liberty corners are characterized at the block's existing 3.3 V
  rail, so no rail change and therefore no level shifter is required at the
  analog/digital boundary. This isn't a second domain — it's one 3.3 V rail
  driving devices of two oxide thicknesses, which needs no boundary circuitry
  at all.

## Consequences

- Item 1 (Design sources), Item 2 (Layout), and Item 5 (Full corner
  verification) become buildable: RTL/synthesis can target a real gate
  netlist, `layout/adc-top`'s reserved-but-undrawn sequencer footprint can be
  placed and routed, and STA can run against a real timing graph instead of
  being N/A-by-construction.
- Per this record's own acceptance criteria (#171) and the operator's
  ratification-via-PR policy, **three follow-on buildable issues are filed
  once this record is ratified** (PR merged) — not before — each citing this
  DR: (a) the RTL/synthesis flow producing item 1's gate-level netlist
  (`klt synthesize`, choosing between `mcu7t5v0`/`mcu9t5v0` as part of that
  work), (b) the P&R'd digital layout for item 2 (`klt place-and-route`), and
  (c) STA closure for item 5 (`klt sta`).
- **Bad consequence, stated plainly**: the digital logic pays 6 V-oxide gate
  capacitance and area at a 3.3 V rail — inherently worse on both axes than a
  purpose-built 3.3 V-device library would be, exactly the cost DR-0004
  originally flagged for the single-supply-throughout choice, now paid for
  real rather than accepted in the abstract. `layout/floorplan-matching-plan.md`'s
  reserved sequencer footprint area was sized against a hypothetical
  3.3 V-device cell area and may need re-checking against the actual
  6 V-oxide cell area once synthesis/P&R produces real numbers — a task for
  follow-on issue (b), not this record.
- DR-0010's rung-3 sign-off path ("the synthesized/hand-built gate netlist…
  feeding #15") is now concretely instantiable rather than a placeholder for
  an undecided library.

## Spec lines affected

None — device flavor has no spec-table representation (consistent with
DR-0004's own "Spec lines affected" entry). This record revises an
architecture/tooling decision, not a `README.md#target-specification` row.
