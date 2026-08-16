# Decomposing #169's T1/bronze failing items into dispatchable issues

**Date:** 2026-08-16
**Author:** Loom Builder, issue #170
**Source:** `2AMLogic/gf180-sar-adc#169`, closing comment (2026-08-15T19:04:56Z)
— the item-by-item T1/bronze checklist re-read against `origin/main` @ `76598b3`.

This is a triage record, not a decision record in the `spec/decision-records/`
sense (no spec row, ratified value, or DR changes here) — it documents how
#169's six FAILING items were turned into filed work per #170's scope, so a
later reader can see the reasoning without re-deriving it from the issue
threads.

## #169's verdict summary

`4/10 pass — blocking items: 1, 2, 5, 6, 7, 8.` Items 3, 4, 9, 10 passed on
their own merits and needed no follow-up issue.

## Disposition of each failing item

| # | Item | Verdict | Disposition |
|---|---|---|---|
| 1 | Design sources | FAIL (digital column) | Grouped into **#171** (operator-decision) — see below |
| 2 | Layout | FAIL (digital column) | Grouped into **#171** |
| 5 | Full corner verification vs. spec | FAIL (digital column N/A) | Grouped into **#171** |
| 6 | Statistical claims carry MC evidence | FAIL | Filed as **#172** (buildable) |
| 7 | Post-layout verification | FAIL / N-A by construction | Filed as **#173** (buildable — STALE-classed) |
| 8 | Characterization report | FAIL | Filed as **#174** (buildable) |

## Why items 1, 2, 5 are one operator-decision issue, not three build issues

All three fail on the digital partition's column for the identical reason:
the SAR sequencer has no RTL, no gate-level netlist, and no drawn layout
beyond `design/sar-logic/gen_sar_logic.py`'s ideal XSPICE behavioral model
(DR-0010's "rung 1", explicitly documented as not the tapeout netlist).
`design/sar-logic/README.md`'s own "Path to the netlist layout and LVS will
use (#15)" section identifies the actual blocker: the open gf180mcu PDK's
only digital standard-cell libraries are built entirely from 6 V-oxide
devices, while `DR-0004` ratified 3.3 V devices "throughout … analog signal
path **and** SAR logic / digital interface." Those two facts cannot both
hold, and resolving that conflict is a ratified-spec-level question, not an
engineering task — per #170's own guardrails, spec-level disputes are routed
as operator-decision requests, not buildable issues. Because the same single
root cause blocks all three checklist rows, and no single re-run or
deliverable would resolve them independently of that decision, they are
grouped into one issue (**#171**) rather than filed three times with the
same content. #171's acceptance criteria call for filing the *now-separate*
downstream build issues (RTL/synthesis, P&R'd layout, STA closure) once the
operator makes the call — those are genuinely distinct engineering
deliverables and do not get merged into #171 itself.

## Why item 7 is STALE-classed rather than a fresh build task

#169 graded item 7 FAIL "by construction" because the installed `klt` in its
environment has no `pex` subcommand, citing `klayout-tools` epic #709. That
epic closed 2026-08-14 (`klayout-tools` main), fully shipping `klt pex`
(CLI-registered, tested, documented) — one day before #169's own read. This
repo's `layout/toolchain.json` pin (`875eac33d`, 2026-08-06) predates that
shipment by eight days, so the FAIL is an artifact of a stale toolchain pin,
not a currently-unresolvable gap. #173 asks for the deliberate pin bump (this
repo's established, reviewed-absorption convention — see
`layout/toolchain.json`'s own pin-history comments) plus a real `klt pex` run,
matching #170's "STALE-classed failures … become re-run/refresh issues"
instruction.

**Outcome (appended 2026-08-16, from #173's own run — the paragraph above is
left as filed).** The STALE classification was right about the *cause* and
wrong about the *remedy*. `klt pex` was installed at `755d3ef` and run for
real against `layout/adc-top/comparator.gds`; the run is committed as
`sim/comparator-pex/`. Item 7 re-grades **FAIL — blocked by a named,
tool-verified limitation**, no longer "N/A by construction": `klt pex`'s
DUT-swap re-simulates both sides from one unmodified `Xdut` line and so
requires the schematic and extracted top-level `.subckt` interfaces to be
pin-identical, which `klt extract`'s promoted body/tap/internal nets never
are here (extracted `COMPARATOR` has 11 pins, schematic `comparator` has 8).
Filed upstream as `klayout-tools#1030`. The pin bump #173 asked for was
attempted and deliberately not taken — it re-baselines every committed
`.spice` snapshot and both manifests at once, and would not have changed the
verdict — so it is tracked separately as `2AMLogic/gf180-sar-adc#178`, with
the reasoning recorded in `layout/toolchain.json`'s own `_comment` block.

## Tracker epic

No open "gap to T1" / bronze tracker epic exists in this repo at filing time
— `2AMLogic/gf180-sar-adc#140` ("Track the gap to T1 sim-validated / bronze")
is **closed** (2026-08-11, comment-only closure, no grant recorded). Per
#170's instructions ("if this repo has an open gap-to-T1 tracker epic, link
each filed issue from it"), there was nothing open to link.

## Issues filed

- `2AMLogic/gf180-sar-adc#171` — [Operator decision] DR-0004 digital-interface
  device-flavor conflict blocks SAR-sequencer RTL/layout/STA (T1 items 1, 2, 5)
- `2AMLogic/gf180-sar-adc#172` — Land PR #149 and extend klt-yield-format
  statistical evidence to all MC rows (T1 item 6)
- `2AMLogic/gf180-sar-adc#173` — Bump klt pin past klayout-tools epic #709 and
  run klt pex for post-layout T1 evidence (T1 item 7, STALE)
- `2AMLogic/gf180-sar-adc#174` — Consolidate the characterization report and
  fix the README/extracted-delta-summary sync lag (T1 item 8)

All four are left unlabeled per #170's constraints — Curator and Champion
promote through the normal pipeline.
