# Re-qualification under open_pdks f6eeac7 — SAR-logic / extraction flow group (issue #596)

Part of #515 (grandparent #513). Old records stay untouched (append-only);
each new record names its `Supersedes` target and carries the fleet job ids in
its Environment section. Pinned PDK: open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`; fleet engine ngspice 47, `klt sim`
backend `aws-batch-fleet`, client klt 0.9.2.dev885.

This issue is landing in tranches. **Tranche 1** was PR #747; **tranche 2** is
the PR this paragraph lands in. The remainder is tracked in #753 and #754.

## Tranche 2: the gate-level decks did not describe the pinned PDK

The re-pin (#514, merged as #517) did more than change which model file the
grids read. `gf180mcu_fd_sc_mcu7t5v0`'s **SPICE library** changed with it:

| | open_pdks `c6d73a3` | open_pdks `f6eeac7` |
|---|---|---|
| device the standard cells bind | `nfet_06v0` / `pfet_06v0` (4809 occurrences) | `nfet_05v0` / `pfet_05v0` (4810) |
| `__clkbuf_1`'s pull-up | two parallel `W=5.25e-07` pfets | one `W=1.05e-06` pfet (upstream fix, "to properly match the layout", 2025-11-03) |

The seven gate-level decks **inline that library text**, so every one of them
still described the *old* standard cells. Both device models exist in the new
`sm141064.ngspice`, so the stale decks still simulated — they simply simulated
the wrong transistors. A grid run against them is not a re-qualification
under `f6eeac7`, which is why tranche 1's gate-level attempt is not counted as
one below even where it produced numbers.

Regenerated with `python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py`.
The deck diff is **device-name-only**: all 1148 changed lines are a
`*fet_06v0` -> `*fet_05v0` swap, every `W`/`L` unchanged. The `__clkbuf_1`
geometry fix does not reach these decks — the synthesized `sar_ctrl` netlist
never instantiates that cell (0 occurrences in all seven decks).

**Consequence for the evidence tree**: the decks' sha256 moved, so every
record taken under `sim/sar-logic-*-gates*/records/` before this change stays
committed but is evidence for the **old** instrument — the same consequence
DR-0031 part 2 recorded for the previous deck change.

### How this went unnoticed for 29 days

`sim/tests/test_sar_ctrl_gates_tb.py`'s drift tests compare each committed
deck with a fresh generation. They `skipTest` when no gf180mcu PDK is
resolvable, which is the case on the PR CI runner (`.github/workflows/ci.yml`
installs no PDK) — so the PR path was green throughout. The nightly PDK job
(`.github/workflows/nightly-pdk.yml`, which does install the PDK) **did**
catch it and filed **#632**, open since the re-pin landed on 2026-10-15.
Regenerating the decks takes that suite from 9 failures to 916/916 passing and
closes #632.

T1 item 9 attests those decks' bytes, so its inventories, envelopes and
manifest pins moved with them (signoff record `20261113-093700-a699814d`,
18/22 met + 1 not applicable, row table byte-identical — no row moved). The
same pass corrected the open_pdks revision both item-9 inventories still
declared (`c6d73a3` -> `f6eeac7`), which is the `signoff/testbench-inventory.*.json`
line of this issue's scope.

## Re-qualified in tranche 1 (PR #747)

| experiment | new record | supersedes | old-vs-new |
|---|---|---|---|
| sar-logic-functional (rung-1 ideal XSPICE, 3 supplies) | `20261113-080421-3eed6a0` | `20260802-110241-131989b` | PASS. All 1023/0 codes, ±0 LSB error, conv_period 1000 ns, acq_window 187.522 ns unchanged; iso_gap 62.2133–62.2145 ns vs 62.2133–62.2137 ns (<0.001 ns); `sw_conflict` ~4.2e-14 vs ~4.2e-14 (limit 0.02). No metric moved beyond tolerance. |

`sar-logic-functional` and `sar-logic-timing` are rung-1 ideal-XSPICE decks
with no PDK device models, so the deck regeneration above does not touch them
and their records stand. `sar-logic-timing` already has a record under
`f6eeac7` (`20261031-191202-befcce4`, superseding `20260802-102758-d8a363d`).

## Re-qualified in tranche 2 (this PR)

Nothing. Both gate-level grids this tranche attempted were defeated by the
batch fleet, and per the no-local-fallback rule neither was re-run on the
dispatch host. The decks are now correct (above); what is missing is fleet
capacity to execute them.

| experiment | outcome | detail |
|---|---|---|
| sar-logic-functional-gates | **not launched** | `klt sim` accepted the per-supply set but none of `klt-sim-03fa4557dfd8` / `klt-sim-c33f3ce62b66` / `klt-sim-e40b2adc2814` left `pending` inside the 600 s `--wait-for-capacity` window. The harness recorded nothing; no point ran on this host. |
| sar-logic-timing-gates | **ran, no usable evidence** | All three jobs launched, then 45/45 points failed: 30 `batch_job_interrupted` (`klt-sim-fee52cb1f49f` and `klt-sim-752d46d96a11` were Spot-reclaimed and sat `interrupted` for 1821 s / 1817 s, past `batch.interrupted_grace_s=1800`, with no re-launch) and 15 `batch_job_timeout` (`klt-sim-204b1e17a0df` exceeded the 3600 s job ceiling). No point produced a result, so klt reported no engine identity and the pin check degraded to drift. |

**No record was committed for either.** `run_corners.py` writes the
`--supersedes` pointer even when every point errored, so committing the
`sar-logic-timing-gates` ERROR record would have put a measurement-free record
at the tip of that experiment's supersession chain, displacing
`20260915-210638-912a8ec` — the only record that has ever measured this deck.
The run's own output is reproduced above instead. That harness behaviour is
filed as **#755**; it already happened once, in tranche 1's
`20261113-080712-3eed6a0`, which declares `Supersedes: 20260917-044312-c7ff0ff`
even though every one of its 45 points timed out.

Both grids therefore remain open, alongside the five in #753.

## Not re-qualified, with reason

| scope | reason | tracked in |
|---|---|---|
| `sar-logic-functional-gates`, `sar-logic-timing-gates` | attempted this tranche against the regenerated decks; defeated by fleet capacity / Spot reclamation (see above). Retry when the fleet has headroom — the decks need no further change. | #753 |
| `sar-logic-timing-gates-ok`, `-bad`, `-lt`, `-tie`, `-xl` | not attempted this tranche: four of the five never completed a full 45-point grid even under the old PDK (`-bad` 0/45, every point timed out at 3400 s; `-xl` 6/45; `-lt` 10/45; `-tie` 29/45), so each is hours of fleet wall-clock and needs its own long `--timeout`. All five now need a fresh run anyway, because the deck regeneration changed their instrument. | #753 |
| `design/sar-logic/flow/**` (STA/synth/P&R), `layout/adc-top/parasitics/**`, `layout/lvs/**` | not `klt sim` flows; they need the heavy (OpenROAD) fleet slice, which does not exist yet — 2AMLogic/2am#6548 is open and itself blocked, its proof runs refused at launch for fleet capacity. LVS `--check` must record the klayout-tools#1063 net-numbering caveat when it does run. | #754 |

## Fleet capacity during this tranche

The batch fleet was saturated for part of the session. `klt sim` accepted the
`sar-logic-functional-gates` set but none of its three per-supply jobs
(`klt-sim-03fa4557dfd8`, `klt-sim-c33f3ce62b66`, `klt-sim-e40b2adc2814`)
launched within the 600 s `--wait-for-capacity` window; the harness recorded
nothing and nothing was run on this host, per the no-local-fallback rule.
2AMLogic/2am#6548 independently measured the same pressure the same day
(`240 vCPU already running ... exceeds BATCH_MAX_VCPU=64`).
