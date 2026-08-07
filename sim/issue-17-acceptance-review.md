# Issue #17 acceptance-criteria review

Issue #17 ("Post-layout extracted re-run of the full verification suite")
was decomposed, over its own build attempt, into #89 ("Full #13/#14 PVT
bench + Monte Carlo re-run against the extracted post-layout netlist, with
schematic-vs-extracted delta summary") once extraction itself surfaced an
upstream gf180mcu gap. #89 closed `COMPLETED` on 2026-08-06 (PR #113),
leaving `sim/extracted-delta-summary.md` on `origin/main` as a 19-subsection
per-spec-line schematic-vs-extracted comparison. The curator's last re-check
(2026-08-06, re-check #8) explicitly deferred a line-by-line acceptance-
criteria verification to "a Builder/Champion/Judge call" rather than doing
it itself. This document is that call.

**Method**: each of #17's 8 acceptance-criteria checkboxes is verified
against a concrete file, record, or forge query — not against the delta
summary's own prose claims. Where the delta summary's claim and the
underlying evidence agree, that is noted; where they diverge, the
underlying evidence wins.

---

## AC1 — friction issue exists, no duplicate filing

**PASS.**

`2AMLogic/klayout-tools#54` ("Friction: no netlist/parasitic extraction or
LVS capability yet — blocks the layout→simulation loop") exists (now
`CLOSED`, since the capability landed upstream — `klt extract`/`klt lvs`
both shipped, per #17's own dependency history). `layout/adc-top/
parasitics/README.md` states directly: "The friction issue for the original
capability gap, `2AMLogic/klayout-tools#54`, is confirmed to exist (now
closed upstream) — Scope item 1's precondition, met, no duplicate filing."
Verified independently via `gh issue view 54 --repo 2AMLogic/klayout-tools`
— a real, single, non-duplicate issue.

## AC2 — extraction path (tool, command, version) documented for reproducibility

**PASS.**

`layout/adc-top/parasitics/README.md`, "Reproduce" section, gives the exact
commands:

```
klt extract ../adc_top.gds   --deck gf180mcu --parasitics --top ADC_TOP   --pdk gf180mcuD --pdk-root <resolved> -o adc_top.para.spice   --format json
klt extract ../adc_block.gds --deck gf180mcu --parasitics --top ADC_BLOCK --pdk gf180mcuD --pdk-root <resolved> -o adc_block.para.spice --format json
```

with the toolchain pin (`layout/toolchain.json`, commit `af5791b`, `klt
0.2.0` — past `2AMLogic/klayout-tools#216`/`#217`, which shipped
`--parasitics`), PDK (`gf180mcuD`, `open_pdks`
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`), and ngspice version (46, per
every cited `sim/` record's own provenance field) all stated. The runner
(`run_extract_parasitics.py`) additionally asserts each block's structured
summary against a committed `cells.json` fixture and the source GDS's
sha256 before writing a record — reproducibility is checked mechanically,
not just documented in prose.

## AC3 — full #13 spec-line bench re-run, full PVT matrix, `Netlist provenance: extracted`, #13's own methodology

**PASS.**

18 `sim/*/records/*.md` files carry a `**Netlist provenance**: extracted`
field (grep-verified: `grep -rln "provenance" sim/*/records/*.md | xargs
grep -l extracted`), spanning:

| deck | grid | manifest reused unmodified |
|---|---|---|
| `adc-inl-dnl` (`mos` set) | 27 pts (`tt`/`ss`/`ff` × 3 temp × 3 supply) | `sim/adc-inl-dnl/testbench/tb.json` |
| `adc-inl-dnl` (`cdac` set) | 63 pts (7 process corners × 3 × 3) | same, default `cdac` corner set |
| `adc-enob-fft` | 9 pts (schematic baseline's own two-stage-strategy subset: `tt`/`ss`/`ff` × 125 °C × 3 supply) | `sim/adc-enob-fft/testbench/tb.json` |
| `adc-power` | 27 pts | `sim/adc-power/testbench/tb.json` |
| `dr0014-sampling` | 27 pts | new, explicitly-scoped `testbench-extracted/tb.json` (Groups A/C only — Group B has no extracted equivalent, a structural gap not a shortcut, see AC7) |
| `device-switch-ron` | 45 pts (`mos` set × 3 temp × 3 supply, leaf-cell extraction) | `sim/device-switch-ron/testbench/tb.json` |

Every re-used manifest is confirmed unmodified in its own record's notes
("SAME MANIFEST, NOT A COPY" — spot-checked directly in
`sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md`), so this is "the same
bench against a different netlist" per #13's own stated methodology (code-
set targeting, coherent-sampling parameters, two-stage corner strategy),
not a re-derivation.

## AC4 — Monte Carlo (#14) re-run, or explicit non-support statement

**PASS** (explicit non-support for one half, real re-run for the other —
the AC's own escape valve).

`sim/extracted-delta-summary.md` §5, verified against the underlying
records:

- **CDAC capacitor mismatch**: `sim/mc-cdac-mismatch/` is a *behavioral*
  numpy model with no `ngspice` invocation at all — "re-run against the
  extracted netlist" is not a defined operation on it. Independently, the
  PDK ships no local capacitor-mismatch model on any netlist
  (`sm141064_mim.ngspice` checked directly — no `agauss`, no `mis_*` term).
  Stated explicitly, not silently skipped.
- **MOS local mismatch**: actually run against the extracted core.
  `layout/adc-top/parasitics/mc_extracted_core.py` → record
  `layout/adc-top/parasitics/records/20260805-extracted-core-mc.md`: N=120
  mismatch-on draws (σ = 1.99e-3 LSB at the worst carry, transition 256)
  plus a mandatory 12-draw mismatch-off null control (σ = 0.0, as required).
  Reuses #14's `sw_stat_mismatch`-based statistical mechanism (the same one
  `sim/comparator-offset-mc/` uses), not a new one.
- **Comparator-inclusive extension** (would additionally cover Offset and
  the comparator's own INL contribution): explicitly named as blocked, not
  dropped — the `ADC_BLOCK` functional smoke test fails reproducibly (see
  AC7).

## AC5 — delta summary committed, large-but-passing deltas flagged

**PASS.**

`sim/extracted-delta-summary.md` (1292 lines) is committed on `origin/main`.
§7 ("Escalations: results reported rather than absorbed") is the flagging
mechanism the AC asks for, and covers two cases:

- §7.1: SFDR's pre-existing schematic FAIL widens from a 0.67 dB miss to a
  1.89 dB miss post-extraction (still the same corner, `ss_125c_2.97v`) —
  reported explicitly rather than folded into "expected baseline behaviour"
  without qualification.
- §7.2: `Power @ 1 MS/s` PASSES with 3.7× margin, but one corner
  (`tt_125c_3.63v`) shows a 2.06× comparator-current excursion — split out
  to a dedicated, still-open tracking issue (**#107**) rather than averaged
  into the aggregate PASS.

## AC6 — no spec relaxation; FAIL reported and escalated, not silently adjusted

**PASS.**

`git log --oneline -- spec/` shows no `spec/` commits between #79/#83
(2026-08-02, well before extraction started) and the current `origin/main`
HEAD (2026-08-06) — the entire #89 extraction campaign touched zero spec
files. The SFDR row is reported as **FAIL** (not adjusted) in the delta
summary's §3 table, §4.6, and §7.1, and the widened margin is stated as a
number a reader should see, not smoothed over. Issue #1 (spec ratification)
is itself already closed, so the AC's literal "comment on #1" option isn't
available; the escalation instead lives in permanent, discoverable public
artifacts: the append-only `sim/` records, `sim/extracted-delta-summary.md`
§7 itself, and PR #103's own description (which states the widened miss
explicitly in the PR body, not just in the doc). The power anomaly (also
FAIL-adjacent in character, though not a spec FAIL) got a dedicated
tracking issue (#107) rather than only a doc mention.

## AC7 — degenerate/edge-case conditions (regen margin #9, settling #8/#10) re-checked post-extraction

**NOT SATISFIED — genuine, structurally-blocked gap.**

Neither condition was actually re-measured against the extracted netlist:

- **Worst-corner comparator regeneration margin (#9, `T_COMP_REGEN_NS`)**
  needs the comparator-inclusive `ADC_BLOCK` extraction. That extraction
  exists and is DC-remediated (63/63), but its functional smoke test
  **fails reproducibly** — every probed transition decodes to a stuck code
  (1023) at two PVT corners, independent of `dout`/`doutb` polarity, while
  the `ADC_TOP` control at the same commit decodes correctly. Root cause
  not identified (record `layout/adc-top/parasitics/records/
  20260806-adc-block-comparator-smoke.md`).
- **Worst-corner CDAC/switch settling (#8/#10, `R_WORST_BIT_OHM` /
  `C_WORST_BIT_F`)**, and #12's rate closure at 1 MS/s that consumes them,
  need an extraction with in-path or distributed net resistance. The
  currently pinned extractor (`layout/toolchain.json`, `af5791b`) writes
  every net's resistance as a dead-end capacitive stub, verified
  structurally across all three committed extractions plus a positive
  control (`records/20260806-parasitic-topology.md`) and independently
  confirmed on the one leaf cell that is drawn (`adc_tgate`,
  `sim/device-switch-ron/`: 0 of 1125 result cells differ from the
  schematic value). Filed upstream as `2AMLogic/klayout-tools#592`
  (2026-08-06); that issue has since closed `COMPLETED` the same day via
  `2AMLogic/klayout-tools#593`/`#594` — this repo's toolchain pin predates
  that landing, so nothing here yet consumes it, and it is not confirmed
  whether those PRs ship the *full* model this project's ask (star-topology
  split or distributed RC) needs.

Both rows are reported in `sim/extracted-delta-summary.md` §3/§6.3/§6.4 as
**not measured**, with the reason stated, rather than backfilled with the
schematic-level number relabelled as an extracted one — so the AC's
"not assumed to still hold from the schematic-level margin alone" half is
satisfied. The "re-checked" half is not. This is real, bounded, remaining
work, tracked as **#116** (root-cause the `ADC_BLOCK` defect, bump the
toolchain pin once the upstream fix is confirmed sufficient, re-measure
both rows, re-close #12's rate closure).

### AC7 update (issue #116, 2026-08-06): one half re-checked, one half still blocked

**STILL NOT SATISFIED — but the settling half is now measured, and the
regeneration half's blocker is root-caused rather than open.**

**Settling / rate closure (#8/#10/#12) — RE-CHECKED.** `klayout-tools#592`
closed via merged PR `#593` (`#594` was a competing implementation and was
closed **without** merging — re-verified live before the pin was cut).
`layout/toolchain.json` is pinned `af5791b` → `875eac3`, `klt` now emits
in-path star-split parasitic resistance (330/330 nets in-path, 0 stubs,
`audit_parasitic_topology.py`), and the re-measured numbers are:

| input | schematic | post-layout | source |
|---|---|---|---|
| `R_WORST_BIT_OHM` | 570 Ω | **648 Ω** (+13.6 %) | `sim/device-switch-ron/records/20260806-194322-68ad582.md`, full 45-point PVT grid |
| `C_WORST_BIT_F` | 2.20672 pF | **2.40712 pF** | extracted `topp` top-plate parasitic, `layout/adc-top/parasitics/records/20260806-193910-68ad582.md` |

#12's rate closure re-composed on those two:
`sim/timing-budget-closure/records/20260806-195653-9cf262a.md`, re-taken as
`sim/timing-budget-closure/records/20260807-082234-eb860c1.md` after issue
#131 added the deck's retained-waveform `.save` (all eight measurements
identical across the two records) — **PASS**,
every cell bit-identical to the schematic record; settling τ 1.258 → 1.560 ns
against a 62.5 ns bit cycle. The `875eac3` pin's own re-baseline (DRC negative
control 8 → 11 violations, extraction warning counts, MiM two-term model) is in
the same change and all of DRC/LVS/extraction re-runs clean.

**Regeneration margin (#9) — STILL NOT re-checked.** The `ADC_BLOCK` stuck-code
defect is now root-caused into two independent causes
(`layout/adc-top/parasitics/records/20260806-adc-block-comparator-input-float.md`):

1. the comparator's differential inputs were **floating** — this repo's own
   generator defect, **fixed** (LVS `pins.layout` 7 → 9, two `topology`
   findings → 0); it also explains `xdut.$168`, the singular node the original
   record could not identify. Fixing it moved the stuck code 1023 → 0;
2. the preamp's `ppolyf_u_2k` load resistors have **no device class in the
   pinned extraction deck**, so they short and the preamp's differential output
   is identically zero — measured on the schematic comparator by
   `probe_comparator_load_short.py` at both `tt_27c_3.30v` and
   `ss_125c_2.97v`, `RESULT: CONFIRMED`. Filed upstream as
   `2AMLogic/klayout-tools#595`.

So `T_COMP_REGEN_NS` stays schematic-level, the §3 rate-closure row is recorded
as **PASS on two of three post-layout inputs** in exactly those words, and the
regeneration-margin and offset rows stay **not measured**. AC7 closes when
`klayout-tools#595` lands (or an equivalent remediation becomes tractable) and
`ADC_BLOCK` converts.

### AC7 update (issue #118, 2026-08-06): `ADC_BLOCK` now converts — via a resize, not `klayout-tools#595` landing

**Still not satisfied — the specific blocker cause (2) named above is now
resolved, but not the way this document anticipated, and not the way that
closes AC7 by itself.** Cause (2)'s load resistors now carry `SAB`/`RES_MK`/
`Resistor` markers (`layout/adc-top/lib/place.draw_poly_resistor`, issue
#118), so `klt extract` recognises them as real `ppolyf_u_1k` devices
instead of an unmodelled short; `pop`/`pon` are genuinely distinct, and
`verify_extracted_core_conversion.py --top ADC_BLOCK` PASSes at both
`tt_27c_3.30v` and `ss_125c_2.97v`
(`layout/adc-top/parasitics/records/20260806-adc-block-resistor-markers-pass.md`).
`klayout-tools#595` itself is **still open** — the pinned deck still cannot
select `ppolyf_u_2k`, so this is a resize-around (`r_length` doubled to hold
150 kΩ at `ppolyf_u_1k`'s 1000 Ω/sq), not the capability landing this
document's prior wording expected.

`ADC_BLOCK` converting removes the functional blocker that made the
regeneration-margin and offset rows *unmeasurable*, but it does not measure
them: no comparator-inclusive Monte Carlo population or full-PVT
regeneration re-run through the extracted core has been done (issue #89
Scope item 2's remaining work — see `sim/extracted-delta-summary.md` §6.4's
own issue #118 update for the schematic-level resize re-checks that WERE
run). **AC7 therefore stays open, on a narrower remaining gap than before**:
not "blocked on a stuck-code defect or an upstream capability," but "the
comparator-inclusive statistical/regeneration campaign through the extracted
core has not been run yet."

## AC8 — extracted-netlist `gain_err_lsb` per corner, alongside schematic value + delta, for #53

**PASS.**

`sim/adc-inl-dnl/records/20260805-203322-3b6d7b7.md` reports `gain_err_lsb`
at all 27 `mos`-set PVT corners (spot-checked directly in the record's
Result table). `sim/extracted-delta-summary.md` §4.1/§4.3/§4.4 reports the
worst-corner value and delta (**−2.0081 LSB worst** at `ff_125c_3.63v`,
**+0.00631 LSB** delta vs. schematic, ~0.3 %) and documents the methodology
work (two independent control experiments, §4.4, plus a second confirming
control under issue #98) that resolved an earlier, non-reproducing
−0.55 LSB reading (record `20260805-163000-e8017f2`, PR #96) to an input-
acquisition artifact of that record's own bespoke 2-endpoint deck rather
than a real post-layout effect — so the number available for adjudication
is the like-for-like one, not the first one measured. #53 itself closed
2026-08-02 (resolved via the DR-0014 design change, before extraction
started), so this AC's "the post-layout number #53's decision record needs"
clause is satisfied prospectively: the number exists and is citable, should
any future adjudication need it.

---

## Disposition

**7 of 8 acceptance criteria PASS. AC7 is a genuine, unresolved gap** — not
an oversight in the delta summary's own accounting (which reports it
honestly as "not measured," never as a false PASS), but real remaining work
that a single verification pass cannot close: it needs either (a) root-
causing and fixing the `ADC_BLOCK` comparator-inclusive extraction's
stuck-code defect, or (b) an upstream extractor capability (in-path/
distributed resistance) that may have just landed (`klayout-tools#593`/
`#594`, closed the same day this review was written) but is not yet
consumed by this repo's pinned toolchain, plus a re-extraction and re-run.
Both are open-ended enough that attempting them inside this verification
pass would itself be "unnecessary new simulation work" of exactly the kind
this review was scoped to avoid doing on top of #89's already-substantial
campaign.

**Issue #17 is therefore not closed by this review.** The remaining work is
tracked as **#116** and #17 is left `loom:blocked` on it, consistent with
this issue's own history of being repeatedly re-blocked on numbered
sub-issues (#51, #60, #66, #67, #89) rather than closed prematurely.

Per CLAUDE.md ("no claim without a testbench," "agents do not relax the
ratified spec to make results pass"), this document does not claim AC7 is
satisfied, and does not close #17 on the strength of the other seven items
alone.
