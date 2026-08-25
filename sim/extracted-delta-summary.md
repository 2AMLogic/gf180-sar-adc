# Schematic vs extracted: the post-layout delta, spec line by spec line

Issue #89 Scope item 3. This is the project-level answer to "what did the
layout cost us?" — for every ratified spec line, the schematic-level result,
the extracted post-layout result, and the delta, with the corner each was
measured at.

It is deliberately **not** a summary of everything that has been extracted. It
is a status page with one row per spec line, and a row is either *measured*
(there is an extracted `sim/` record and a delta) or *not yet measured* (with
the specific reason and what closing it needs). No row is left implicit, and
nothing here is transcribed by hand — every number in the delta tables below is
reproduced by running the command printed above it.

**Nothing in this document adjusts a spec line.** Where an extracted result
misses a target the schematic passed, it is reported as a FAIL and escalated
(CLAUDE.md: agents do not relax the ratified spec to make results pass). As of
this revision there is no such case in the benches that have run — but two
results are still not clean passes and are escalated in **§7**: the SFDR row,
which was already failing before layout and whose margin widens (§7.1), and
the power row, which passes with 3.7× margin but carries a localised 2×
comparator-current excursion at one corner — now diagnosed: metastable
regeneration on the one undamped bit cycle per conversion, bounded to that
single corner and exact input level (§7.2).

**Read §1.4 before reading any delta below.** Two properties of the extraction
itself bound what these numbers can mean, both established by measurement
rather than by reading tool docs: the extracted resistance is a shunt stub and
sits in no signal path (so no resistive quantity can move post-layout — §4.8
measures exactly that, and §6.3's blocked rows follow from it), and the pinned
extractor assigns parasitics to Metal1 only (so every loading delta here is a
lower bound).

**For the current status of every ratified spec row** — not just the ones
this document's schematic-vs-extracted comparison covers — see
[`sim/characterization-summary.md`](characterization-summary.md), which cites
§3's table below alongside the statistical (Monte Carlo / `klt yield`) and
architectural rows this document does not scope to.

> ### ⚠ §4.1–§4.11 describe the PRE-resize layout. §4.12 is the current one.
>
> **Narrowed, and now carrying its answer** (issue #218, 2026-08-17;
> the wider "flagged, not fixed" banner it replaces was #197's). Every
> extracted result in §4.1–§4.11 and §7 was measured against the netlist
> extracted from the layout as it stood at the **historical `C_u = 17.24 fF`**
> CDAC unit cap. DR-0019
> ([`spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md`](../spec/decision-records/DR-0019-cdac-unit-cap-resize-for-gain-error-margin.md))
> resized that unit to **`C_u = 35.6528 fF`**, and #196/PR #202 physically
> implemented it — a 2.068× array capacitance change, drawn at a new geometry.
>
> **The re-extraction and all five extracted campaigns have now been re-run at
> that geometry** ([`layout/adc-top/parasitics/records/20260817-153913-2494bd0.md`](../layout/adc-top/parasitics/records/20260817-153913-2494bd0.md)
> plus five new `sim/` records). What that changes:
>
> - **§3's spec-line table now cites the post-resize extracted records**, and
>   its extracted figures are current again. §4.1–§4.11 are **not** rewritten
>   — per `sim/README.md`'s append-only rule they stand as the true record of
>   the pre-resize layout, and **§4.12** is the post-resize re-take, campaign
>   by campaign, with the before/after delta for each (including the two rows
>   that do not move).
> - **The SFDR row has a valid governing result again, and it is a FAIL.**
>   Its standing governing PASS (64.38 dB, §4.10/§7.3) was pre-resize; the
>   post-resize extraction measures **60.40 dB worst** (`ff_125c_3.63v`),
>   missing `≥ 62 dB` at 4 of 9 corners. **ENOB likewise now FAILs** on the
>   governing side, 8.857 bits worst against `> 9.0`. Reported, not absorbed:
>   no target is relaxed here and the mechanism remains **#211**'s.
> - **Two rows improve** — the DR-0012/13 systematic gain-error row and the
>   sample's own nonlinearity — and **one is an exact null** (the drawn
>   `adc_tgate` R_on, whose leaf geometry DR-0019 does not touch). Both are
>   reported in §4.12 rather than left implicit.
> - **Static INL/DNL still PASSes its ratified `< 1 LSB` row but now misses
>   the `< 0.5 LSB` stretch** post-layout (worst |INL| 0.528 LSB, worst |DNL|
>   0.728 LSB at `ss_125c_2.97v`), where the pre-resize extraction cleared the
>   stretch by ~3.4×. Flagged in §4.12.1, not folded into a passing sentence.
>
> One row was unaffected by construction all along: **Reference (`Z_ref`,
> `C_dec`) / CDAC bit-settling** has no extracted counterpart in this document
> at all (it sits off the extracted `ADC_TOP` boundary), so its schematic-level
> re-run under #197 left no extracted pair to go stale.
>
> The consolidated **schematic**-side before/after adjudication of the same
> resize is [`spec/testbench-suite-memo.md`](../spec/testbench-suite-memo.md)
> §11.9; §11.9.8 carries the extracted-side verdict this banner summarises.

> ### ⚠ Toolchain provenance: the `klt` pin behind every currently-governing number is `85b8125`, not `875eac3` (issue #189)
>
> **Every extracted number this document currently cites as governing — §3's
> table, §4.12, and §4.13 — was produced by an extraction run under
> `layout/toolchain.json`'s `klt` pin `85b8125fb012f6038883ab884490a3caa3d41db3`,
> not the `875eac3` pin §1.4/§4.8/§4.10/§7.3 narrate as "current" in their own
> (earlier, still-correct-for-their-own-vintage) text.** That pin bump landed
> via PR #195 (issue #178, merged 2026-08-16) and carries two upstream
> `klayout-tools` commits confirmed ancestors of `85b8125`: `af58e41`
> (`klayout-tools#697`) adds junction area/perimeter (`AS=`/`AD=`/`PS=`/`PD=`)
> to every `--pdk`-bound MOS `X` card, and `7c5cef8` (`klayout-tools#728`)
> prepends a parasitic-model scope header. This is a real SPICE-model input
> change — it changes what junction capacitance ngspice computes for every
> extracted MOS device, not just extraction-report text — so issue #189 tracked
> it as a fast-follow requiring its own measured before/after rather than being
> silently absorbed by a passing `--check`.
>
> **What was measured, and how it reached every number below:**
>
> - PR #195 minted the first `85b8125`-pin record
>   ([`20260816-174824-539f5d9`](../layout/adc-top/parasitics/records/20260816-174824-539f5d9.md))
>   and regenerated all six `gen_extracted_*_tb.py` decks against it — the
>   diff in each was exactly the `AS=`/`AD=`/`PS=`/`PD=` device-card additions
>   plus the new header, nothing else (`layout/toolchain.json`'s own `_comment`
>   carries the full accounting). At the **same** geometry, that pin bump also
>   moved total extracted capacitance (a distinct, ancestor `b40955d` /
>   `klayout-tools#764` vertical-overlap-coupling change in the same pin range,
>   not the junction params themselves): `adc_top` 5215.82 fF → 5154.95 fF
>   (−1.2 %), `adc_block` 5622.31 fF → 5561.44 fF (−1.1 %); total resistance
>   was unaffected.
> - Every extraction and PVT campaign re-run since PR #195 — issue #219's
>   DR-0019 resize re-take (§4.12, record `20260817-153913-2494bd0`) and issue
>   #224's comparator-load-resistor-fold re-take (§4.13, record
>   `20260817-204449-076d545`) — re-extracted and re-ran the full PVT grid
>   against decks generated under this **same** `85b8125` pin, so every
>   junction-capacitance-inclusive number these later geometry changes measured
>   already carries the `AS=`/`AD=`/`PS=`/`PD=` SPICE-model effect. `klt`'s own
>   `--pdk` variant was additionally corrected `gf180mcuA` → the fleet-ratified
>   `gf180mcuD` by issue #228/PR #229 (record
>   [`20260819-060730-bbed59c`](../layout/adc-top/parasitics/records/20260819-060730-bbed59c.md)),
>   verified electrically identical to `076d545` for every block (same ΣR/ΣC,
>   confirmed directly against both records' own extracted-summary tables) —
>   a PDK-variant metadata fix, not a further physics change.
> - There is no clean-room "junction params alone, current geometry, nothing
>   else changed" isolation, because the current geometry did not exist yet
>   when the pin bump alone (pre-DR-0019, pre-#215) was the only variable —
>   §3/§4.12/§4.13's post-`85b8125` deltas are against those geometry
>   baselines, not an isolated pin-only baseline. What is directly measured
>   and reported, not silently assumed, is: (1) the isolated same-geometry
>   capacitance-total effect of the pin bump itself (the `b40955d` figures
>   above), and (2) that the junction-parameter-inclusive decks are what every
>   PVT campaign cited as governing in this document has run since — no
>   currently-governing number in §3, §4.12, or §4.13 was measured against a
>   pre-`85b8125` deck.
> - §1.4, §4.8, §4.10, §7.3 and similar sections below still narrate `875eac3`
>   as "current" — that text is correct **for the vintage each section
>   describes** (append-only per `sim/README.md`) and is not rewritten here;
>   this banner is the one place that states which pin governs *today's* cited
>   figures. `sim/characterization-summary.md` carries the equivalent note in
>   its own Freshness section.

---

## 1. What the extracted netlist is, and what was done to it

Every extracted number below comes from **one** netlist, produced and
substantiated in [`layout/adc-top/parasitics/`](../layout/adc-top/parasitics/):

- **Source**: `klt extract ../adc_top.gds --deck gf180mcu --parasitics --top
  ADC_TOP --pdk gf180mcuD --pdk-root <resolved>`, written to
  `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice`
  — 1320 devices (148 nfet, 148 pfet, 1024 MiM), 177 nets, 156 parasitic R +
  156 parasitic C, ΣR 115 320 Ω, ΣC 3730 fF.
- **Toolchain, pinned** (`sim/toolchain.json`): open_pdks
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, gf180mcuD, ngspice ≥ 46 (46 in
  every run below), `klt` at the `af5791b` pin.

Two methodology choices had to be made before this netlist could be simulated
at all. Issue #89's guidance section requires both to be **stated, not silently
absorbed**, because either one made differently moves every number below.

### 1.1 PMOS body terminals — local remediation of a known upstream gap

gf180mcu's curated `klt extract` deck has no tap/well-label layer, so every
PMOS device's body (Nwell) terminal lands on an anonymous, un-pinned internal
net rather than the `vdd` tie the schematic assumes. Measured, not assumed: a
single-PMOS leaf-cell extraction's anonymous body node sits at ≈ 0 V against a
driven-low source — a full supply-rail `V_sb` error on every PMOS device.

**Path taken: local remediation**, not waiting on upstream.
[`2AMLogic/klayout-tools#555`](https://github.com/2AMLogic/klayout-tools/issues/555)
was `OPEN` when this path was chosen and has since **closed** (2026-08-05,
via [`klayout-tools#581`](https://github.com/2AMLogic/klayout-tools/issues/581),
re-checked 2026-08-06) — but that PR shipped only the Shape-2 fix (surfacing
the anonymous PMOS-body net name as a structured JSON signal); the Shape-1
opt-in `--tie-well-to`-style re-biasing flag that would let `klt extract`
itself emit a `vdd`-tied body was explicitly deferred to its own follow-up
issue and has not landed. So `layout/adc-top/parasitics/remediate_extracted.py`
still does the retie locally: it rewrites every anonymous PMOS-body net to
`vdd`, after asserting structurally that each such net appears *only* as a
PMOS body terminal (148 devices across 20 nets for `ADC_TOP`).

**This is therefore not raw `klt extract` output**, and every record says so in
its `Netlist provenance` field. The remediation's own DC verification —
`verify_remediation_dc.py`, record
[`layout/adc-top/parasitics/records/20260805-remediation-dc.md`](../layout/adc-top/parasitics/records/20260805-remediation-dc.md)
— converges 63/63 on the `cdac` PVT grid with the bodies hard-tied, against a
raw extraction whose bodies float at 3.13–3.15 V.

### 1.2 MiM capacitors — the PDK subckt, unmodified

The `--pdk gf180mcuD` extraction emits
`X … cap_mim_2f0_m4m5_noshield c_length=… c_width=…` **subckt calls**, which
bind to `sm141064_mim.ngspice` — the same subckt `sim/harness/pdk.py` resolves
and the same one the schematic CDAC instantiates.

**Choice: use the PDK MiM subckt as extracted; no rewrite, no ideal-capacitor
substitution.** This is the fair comparison against the schematic's
subckt-instantiated MiM: both sides of every delta below are the same device
model, so the delta carries the layout's geometry and interconnect, not a model
swap. `remediate_extracted.py` asserts the binding (1024 caps) and leaves the
cards untouched.

The consequence for statistical work is stated in §5: `sm141064_mim.ngspice`
contains no mismatch term at all, so this choice neither adds nor removes
capacitor mismatch — there is none to have.

### 1.3 The wrapper: extracted core, schematic everything-else

The extracted `ADC_TOP` is the CDAC analog core. It is wired into a
**schematic-level** comparator, rung-1 SAR controller and DR-0013 input-drive
network by `layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py`, which ports
`design/adc-top/gen_adc_top.py`'s own input ladder and ideal shadow DAC
verbatim rather than restating them.

So each delta below isolates **the analog core**. It is not a full-chip
post-layout number, and this document does not claim it is.

### 1.4 What the extracted parasitics are: capacitive loading, and (since the `875eac3` pin) in-path resistance

> **RE-STATED at issue #116.** Everything below the rule was true at the
> `af5791b` pin this document was first written against, is still true of the
> netlists extracted at that pin (they are still in `reports/`, append-only),
> and is *no longer* true of the current pin. Both states are kept, because
> several §4 findings — most of all §4.8's "+0, 0 of 1125 cells differ" — are
> only readable against the topology they were measured on.

**Now (`875eac3`, upstream `klayout-tools#593`).**
`layout/adc-top/parasitics/audit_parasitic_topology.py`, re-run against the
current extractions:

| netlist | form | parasitic nets | **in-path R** | stub R | ΣR (Ω) | max R (Ω) | ΣC (fF) |
|---|---|---|---|---|---|---|---|
| `adc_top.para.spice` | star-split | 156 | **156** | 0 | 117 685 | 16 014 | 5216 |
| `adc_block.para.spice` | star-split | 170 | **170** | 0 | 132 775 | 20 421 | 5549 |
| `adc_tgate.para.spice` (leaf) | star-split | 4 | **4** | 0 | 303 | 120 | 9.2 |

Every device terminal now sits on its own leg node (`<net>__t<k>`) with a
distance-weighted series resistor back to the net's hub, so two terminals on
one net are separated by real, layout-dependent resistance. 330 of 330
parasitic nets across the three extractions are in-path; none is a stub. The
consequence is measured, not asserted: §4.8's post-layout T-gate R_on delta
moves from **exactly zero** to **+77.4 Ω at `ss_125c_2.97v`**, and §3's rate
closure row becomes measurable on two of its three inputs (§6.3).

**Before (`af5791b` and every earlier pin)** — record
[`20260806-parasitic-topology`](../layout/adc-top/parasitics/records/20260806-parasitic-topology.md):

| netlist | parasitic nets | **in-path R** | stub R | ΣR (Ω) | max R (Ω) | ΣC (fF) |
|---|---|---|---|---|---|---|
| `adc_top.para.spice` | 156 | **0** | 156 | 115 320 | 16 013 | 3730 |
| `adc_block.para.spice` | 172 | **0** | 172 | 129 704 | 20 499 | 4056 |
| `adc_tgate.para.spice` (leaf) | 4 | **0** | 4 | 303 | 120 | 9.2 |

At that pin `klt extract --parasitics` wrote, per net, one
`R<net> <net> <net>__par` and one `C<net> <net>__par <ground>`. **Every device
in all three extractions was attached to `<net>`, never to `<net>__par`**, so
the extracted resistance was a stub: it put the parasitic capacitance behind a
small series resistance and carried no device current itself. 115 kΩ of
extracted resistance in `ADC_TOP`, none of it in any signal path. That is the
gap this repo filed as `klayout-tools#592`; it closed the same day via
`#593`, and `layout/toolchain.json`'s pin now consumes it.

(The ΣC column also moves, for a second and unrelated upstream fix:
`klayout-tools#512` gave the deck the PDK model card's two-term
area+fringe MiM formula, so the extracted unit capacitor is 17.2449 fF where
it was 14.7316 fF — the 14.6 % modelling delta this document reported as
unclosable is closed at the source. See `layout/adc-top/lib/netlist.py`.)

What that means for the rest of this document, in both directions:

- **The deltas in §4 are real.** They are capacitive-loading effects — the
  extraction models the drawn capacitance faithfully, and INL/DNL, ENOB and
  switching power are all loading-sensitive. Nothing in §4 depends on series
  resistance being modelled, which is why every §4 number survives the pin
  bump unchanged in kind (they are not re-run here; a re-run mints new records
  with `Supersedes`, it does not edit these).
- **No resistive quantity could move — until the `875eac3` pin.** Any
  post-layout number defined by a conductor's resistance — R_on (§4.8), IR
  drop, electromigration, or the CDAC settling network's `R_WORST_BIT_OHM`
  that rate closure and the DR-0012/13 row need (§6.3) — was identically the
  schematic number *by construction*, and would have remained so no matter how
  much more geometry were drawn and extracted. That was an extractor
  capability gap, not a missing deck, and it is the gap this repo filed as
  `klayout-tools#592`. **It is now closed** (`#593`, merged 2026-08-06;
  `layout/toolchain.json` pinned past it at issue #116), and the first
  consequence is measured in §4.8/§6.3: the T-gate R_on delta moves from
  exactly zero to +77.4 Ω.
- **What is bought is in-path resistance, NOT a distributed RC line model.**
  `#593` splits each net into a hub plus one distance-weighted leg per device
  terminal. Full distributed per-segment RC (`#592`'s Option 2) remains
  explicitly out of scope upstream. A number that depends on the resistance
  *profile along* a conductor rather than on terminal-to-terminal series
  resistance is still not something this extraction can express.

**A second fidelity caveat, found while checking the first, and it bounds the
§4 numbers.** The pinned `klt` build's gf180mcu parasitics table has **one**
`LayerRC` for a **five**-level metal stack, so Metal2..Metal5 contribute
exactly zero R and zero C. Verified directly against the installed build
(`len(gf180mcu.EXTRACTION_DECK.metals) == 5`,
`len(gf180mcu.PARASITICS.metals) == 1`), and the layout does draw on those
levels (`layout/adc-top/lib/geometry.py`'s `L_METAL2` riser; Metal4/Metal5 for
the MiM plates). Upstream
[`klayout-tools#547`](https://github.com/2AMLogic/klayout-tools/issues/547)
fixed it on 2026-08-05, *after* this repo's pin (`layout/toolchain.json`,
`af5791b`, `klt 0.2.0`). **Every extracted parasitic in this document is
therefore a Metal1-only value, and every §4 loading delta is a lower bound.**
The remedy is a pin bump plus a re-run of the three §4 decks — a separate
bounded increment; nothing here is adjusted to anticipate it (records are
append-only, and a re-measurement mints new records with `Supersedes`).

The upstream status of the topology gap, checked rather than assumed:
[`klayout-tools#338`](https://github.com/2AMLogic/klayout-tools/issues/338)
already reported exactly this Γ-topology (net → R → internal node → C →
ground) and was closed **completed on 2026-08-03 as a documentation-only
fix** — its own curation explicitly scoped out the two options that would
change the model ("star-topology split", "full distributed RC") and
recommended "filing a separate follow-up issue if/when there's appetite to
implement Option 2". No such follow-up existed until this project filed
[`klayout-tools#592`](https://github.com/2AMLogic/klayout-tools/issues/592)
per CLAUDE.md's canary protocol, citing this section, §4.8 and
`records/20260806-parasitic-topology.md` as substantiation and describing the
gap generically (an extractor-capability question, not this design's
specifics).

**`#592` closed `COMPLETED` on 2026-08-06** via merged PR
[`#593`](https://github.com/2AMLogic/klayout-tools/pull/593) (merge commit
`875eac3`) — the star-topology split, i.e. `#592`'s Option 1. (A competing
even-split implementation, `#594`, was closed without merging; re-verified
live before the pin was cut.) `layout/toolchain.json`'s pin moved
`af5791b` → `875eac3` at issue #116 and this project's resistive numbers are
no longer subject to the gap. Option 2, full distributed per-segment RC,
remains out of scope upstream and this project's numbers *are* still subject
to that.

**The Metal2..Metal5 half of the caveat above is also closed by the same pin
bump** (`klayout-tools#547`), which is most of why ΣC moves in the table
above — together with `#512`'s two-term MiM model. §4's loading deltas were
recorded as lower bounds against a Metal1-only extraction; they are **not
re-run here**, so they stay lower bounds until a separate increment re-runs
those three decks and mints records with `Supersedes`. Nothing in §4 is
edited to anticipate that.

---

## 2. How to re-derive every number here

```bash
# 1. Regenerate the extracted-core deck from the committed extraction (asserts
#    byte-identity with the committed fixture; writes nothing on --check).
python3 layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py --check

# 2. Re-run the SCHEMATIC manifest against the extracted netlist. -j 1 and the
#    raised timeout are load-bearing -- see sim/harness/README.md, "Run an
#    extracted deck at -j 1". ~41 min for 27 points on an 8-core host.
python3 sim/run_corners.py adc-inl-dnl \
    --netlist sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice \
    --netlist-provenance "extracted (remediated) -- ..." \
    --corners tt ss ff -j 1 --timeout 1200 \
    --supersedes 20260802-141402-1224e11

# 3. Derive the delta table from the two committed records.
python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
    --schematic 20260802-141402-1224e11 \
    --extracted  20260805-203322-3b6d7b7
```

Step 2 uses `sim/adc-inl-dnl/testbench/tb.json` **unmodified**: the same claim,
analyses, measure expressions and checks that produced the schematic record.
That is the point of `--netlist` — a delta between two independently-written
measurement decks is not a delta between two circuits.

Step 3 parses the two records' own per-corner Result tables. It does not
recompute a single pass/fail verdict; verdicts are read out of the records.

---

## 3. Spec-line status

**Every row below is at the DR-0019-resized `C_u = 35.6528 fF`, on both
sides**, as of issue #218 (2026-08-17): the extracted column cites the
post-#202 re-extraction and its five re-run campaigns (§4.12), the schematic
column cites #197's re-takes. The pre-resize values each row used to carry are
preserved in §4.1–§4.11 and in the superseded records, per the append-only
rule.

| Ratified row | Schematic | Extracted | Delta | State |
|---|---|---|---|---|
| **INL** < 1 LSB (< 0.5 stretch) | −0.1100 LSB (`cap_ss_125c_2.97v`, 63-pt `cdac` grid) | **−0.5284 LSB** (`ss_125c_2.97v`) | −0.418 LSB | **measured — PASS on the ratified row, MISSES the < 0.5 LSB stretch** (§4.12.1; pre-resize this read −0.148 LSB and cleared the stretch by 3.4×) |
| **DNL** < 1 LSB (< 0.5 stretch) | 0.0938 LSB (`cap_ss_125c_2.97v`) | **+0.7278 LSB** (`ss_125c_2.97v`) | +0.634 LSB | **measured — PASS on the ratified row, MISSES the < 0.5 LSB stretch** (§4.12.1; pre-resize −0.0905 LSB) |
| Gain error, converter-level (unbudgeted, no ratified row — §3.5 of the suite memo) | −2.0059 LSB (`tt_-40c_3.30v`) | **−2.0068 LSB** (`ff_125c_3.30v`) | −0.0009 LSB (−0.04 %) | **measured** — unmoved by the resize on either side (§4.12.1); an earlier −0.55 LSB delta was shown by null control to be a settling artefact (§4.3/§4.4) |
| ENOB @ Nyquist > 9.0 | 8.506 bits (`ss_125c_2.97v`) — **FAIL at 2 of 9** | **8.857 bits** (`tt_125c_3.63v`) — **FAIL at 2 of 9** | +0.351 bits at the schematic-worst corner; the extracted grid's own worst corner is elsewhere | **measured — FAIL** (§4.12.2). Pre-resize this row read 9.103 bits extracted and PASSed; the governing side now misses the target |
| SFDR @ Nyquist ≥ 62 dB | 56.41 dB (`ss_125c_2.97v`) — **FAIL by 5.59 dB** | **60.40 dB** (`ff_125c_3.63v`) — **FAIL by 1.60 dB, at 4 of 9 corners** | +3.99 dB at the schematic-worst corner; worst-corner identity differs | **measured — FAIL** (§4.12.2, and read §7.1 for the pre-resize baseline). The row's standing governing PASS (64.38 dB) was pre-resize; this is its first valid post-resize governing result |
| Power @ 1 MS/s < 1 mW | 207.9 µW (`ff_-40c_3.63v`) | **246.5 µW** (`ff_27c_3.63v`) | +38.6 µW (+18.6 %) | **measured — PASS**, 4.06× inside the bound and 2.03× inside the < 500 µW stretch (§4.12.3). The growth lands on the two array-facing rails (`p_ref` +90 %, `p_cdac` +21 %); §7.2's one-corner comparator excursion does not reappear in this vintage |
| Gain error, systematic (DR-0012/13 scope: sampling-switch injection) ≤ 0.5 LSB | 0.0021–0.0039 LSB (`ff_-40c_2.97v`) | **0.00013–0.00048 LSB** (`ff_-40c_3.63v`) | −0.0035 LSB (−87.9 %) | **measured — PASS**, ~1047× inside the bound and *wider* than before the resize (§4.12.4) |
| Offset ≤ 2 LSB (3σ mismatch) | `sim/comparator-offset-mc/` | — | n/a | comparator is schematic-level in the closed runs — §5. `ADC_BLOCK` now converts (issue #118, §6.4 update) but a comparator-inclusive Monte Carlo population has not been run yet — that is issue #89 Scope item 2's remaining work, not blocked on a functional defect any more. **A related, DETERMINISTIC (not statistical) finding from issue #116's regeneration-margin campaign**: the extracted core's own systematic offset (no mismatch enabled) measures −0.597…−4.357 mV across the 45-point grid — well inside this ≤ 2 LSB (12.89 mV) bound, but not the same claim as a 3σ mismatch population; see §6.4's update |
| INL/DNL under 3σ CDAC **capacitor** mismatch | `sim/mc-cdac-mismatch/` | — | n/a | **not applicable** — the PDK has no local cap-mismatch model on either netlist, §5 |
| Transition error under **MOS** local mismatch (no ratified row; the statistical half of Scope item 2) | — (schematic-side equivalent not run at this transition) | **σ = 1.99e-3 LSB**, N = 120, `tt_27c_3.30v`, transition 256 | n/a — capability claim, not a delta | **measured** — §5, null control σ = 0 |
| Rate (1 MS/s) closure | [`20260802-112832-ed9a325`](timing-budget-closure/records/20260802-112832-ed9a325.md), PASS | **PASS** — [`20260814-220124-f613571`](timing-budget-closure/records/20260814-220124-f613571.md) (issue #116, superseding [`20260807-082234-eb860c1`](timing-budget-closure/records/20260807-082234-eb860c1.md)) | settling τ 1.258 ns → **1.560 ns**; comparator delay 0.863 → **1.257 ns**; every `abs_err_*` cell at the `logic0ns`/`logic10ns`/`logic25ns@1MS/s` brackets bit-identical (0), the two negative-control brackets that were already meant to fail move to reflect the larger, real comparator delay | **measured — PASS on ALL THREE post-layout inputs** (§6.3/§6.4). `R_WORST_BIT_OHM` 570 → 648 Ω, `C_WORST_BIT_F` 2.20672 → 2.40712 pF, and **`T_COMP_REGEN_NS` 0.863 → 1.257 ns** (issue #116) are all post-layout. This is the fully post-layout rate closure issue #17's AC7 asks for |
| Input-structure switch R_on (characterization, no ratified row — feeds the settling budget) | 570.436 Ω (`ss_125c_2.97v`) | **647.818 Ω** (`ss_125c_2.97v`) | **+77.4 Ω (+13.6 %)** | **measured — PASS both sides** (§4.8, §6.3), and **unmoved by DR-0019**: re-taken against the post-#202 extraction it reproduces every one of 45 × 24 result cells (§4.12.5). The earlier "+0, 0 of 1125 cells differ" row was a property of the *extractor*, not of the layout: the `875eac3` pin puts parasitic resistance in the current path and the drawn cell's interconnect now shows up |
| Worst-corner comparator regeneration margin (#9's `T_COMP_REGEN_NS`, feeds the row above) | 0.859 ns (`ss_125c_2.97v`, [`20260806-233153-56be937`](comparator-regeneration/records/20260806-233153-56be937.md), re-run at the issue #118 resistor resize — see the §6.4 update's before/after table) | **1.256 ns** (`ss_125c_2.97v`, [`20260814-215626-f613571`](comparator-regeneration/records/20260814-215626-f613571.md)) | +0.397 ns (+46.3 %) | **measured — PASS** (issue #116, §6.4 update). `margin_ns` (slack against the 31.25 ns decide phase) narrows 30.39 → 29.99 ns but stays 1.9× the 15.625 ns floor at every one of 45 corners. `td_half_ns`/`td_big_ns`/`margin_ns`/`tau_ps`/`resolve_decades` all PASS their ratified bounds at all 45/45 corners; the 0.1 mV metastability probe (`td_tiny_ns`) does not resolve at this measurement's offset-referencing resolution and is reported `n/a` rather than fabricated — see the record |

---

## 4. The static-linearity delta, in full

- schematic record: [`20260802-141402-1224e11`](adc-inl-dnl/records/20260802-141402-1224e11.md) (DR-0014 bottom-plate topology, #61 / PR #64)
- extracted record: [`20260805-203322-3b6d7b7`](adc-inl-dnl/records/20260805-203322-3b6d7b7.md)
- shared corners: **27** (`tt`/`ss`/`ff` × −40/27/125 °C × 2.97/3.30/3.63 V) — every corner in the extracted record has a schematic counterpart
- per-corner verdicts, read from the records: schematic **all PASS**, extracted **all PASS**
- corners whose verdict changed schematic → extracted: **none**

### 4.1 Headline

```
python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
    --schematic 20260802-141402-1224e11 --extracted 20260805-203322-3b6d7b7 \
    --only inl_worst_lsb dnl_worst_lsb gain_err_lsb vref_droop_mv
```

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `inl_worst_lsb` | -0.108233 (`ss_-40c_2.97v`) | -0.110911 (`ss_-40c_2.97v`) | -0.002678 | -2.474 | 0.00321 |
| `dnl_worst_lsb` | 0.100251 (`tt_27c_2.97v`) | 0.100348 (`tt_27c_3.30v`) | +9.7e-05 | +0.09676 | 0.0407528 |
| `gain_err_lsb` | -2.01444 (`ff_125c_3.63v`) | -2.00813 (`ff_125c_3.63v`) | +0.00631 | +0.3132 | 0.00661 |
| `vref_droop_mv` | 0.263 (`ss_125c_3.63v`) | 0.323 (`ss_-40c_3.63v`) | +0.06 | +22.81 | 0.061 |

`inl_worst_lsb` / `dnl_worst_lsb` are reduced spec-line quantities the records
do not carry as their own columns; the tool derives them from the
`inl_t*_lsb` / `dnl_t*_t*_lsb` columns (worst by magnitude, sign kept).

**Read `max per-corner delta` alongside `delta (worst)`.** A worst-vs-worst
delta hides a per-corner swing that moves the worst corner around: DNL's
worst-vs-worst delta is +0.0001 LSB, but some individual corner's DNL moves by
up to **0.041 LSB**. The spec-line conclusion (PASS with 10× margin) is
unaffected either way; the distinction matters for anyone reading these numbers
as a parasitic model rather than as a verdict.

### 4.2 Per transition

Full table: run the command in §2 step 3 without `--only`. The pattern worth
recording is that the extracted INL degradation is **not uniform across the
code range — it grows toward full scale**, which is the signature of top-plate
and interconnect parasitic capacitance loading the array:

| transition | schematic worst INL | extracted worst INL | delta | delta % |
|---|---|---|---|---|
| `inl_t2_lsb` | -0.0525844 | -0.0538944 | -0.00131 | -2.5 |
| `inl_t128_lsb` | -0.105403 | -0.107494 | -0.002091 | -2.0 |
| `inl_t384_lsb` | -0.108233 | -0.110911 | -0.002678 | -2.5 |
| `inl_t640_lsb` | -0.08597 | -0.0916761 | -0.0057061 | -6.6 |
| `inl_t768_lsb` | -0.0251871 | -0.0314642 | -0.0062771 | -24.9 |
| `inl_t896_lsb` | -0.0783432 | -0.085378 | -0.0070348 | -9.0 |
| `inl_t1022_lsb` | -0.0640824 | -0.0712504 | -0.007168 | -11.2 |

The largest *relative* deltas sit at the top of the range; the largest
*absolute* INL still sits where the schematic's did (`inl_t384`,
`ss_-40c_2.97v`). The layout did not move the worst transition.

### 4.3 `gain_err_lsb`: this run does not reproduce record `20260805-163000-e8017f2`'s −0.55 LSB delta

This must be stated plainly rather than quietly averaged in.

Record [`20260805-163000-e8017f2`](adc-inl-dnl/records/20260805-163000-e8017f2.md)
(merged in PR #96) reported an extracted-vs-schematic `gain_err_lsb` delta of
**−0.5146 … −0.6340 LSB, mean −0.5552 LSB**, attributed to top-plate /
interconnect parasitic gain attenuation. **The like-for-like re-measurement
above does not reproduce it**: the delta is **+0.00285 … +0.00661 LSB, mean
+0.00520 LSB** over the same 27 corners — two orders of magnitude smaller, and
of the opposite sign.

The two runs measure the same core with the same formula and read the same
node. They differ in **how the input reaches the two endpoint transitions**:

| | record `…-163000-e8017f2` (PR #96) | record `…-203322-3b6d7b7` (this run) |
|---|---|---|
| deck | bespoke, `measure_extracted_gain_err.py` | the `adc-inl-dnl` manifest, unmodified |
| transitions simulated | 2 (endpoints 1 and 1023 only) | 18 (the full probed set) |
| input step into transition 1023 | ~1022 LSB, in one 10 ns ramp | ≤ 126 LSB, walking up the ladder |
| settling budget before the decision | `INL_CONV_PER_POINT = 1` conversion (1000 ns) | identical |

At `tt_-40c_2.97v`, the **lower** endpoint agrees to all printed digits
(`e1` = `terr_t1_lsb` = **1.02068** in both), while the **upper** endpoint does
not (`e1023` = −1.52863 vs `terr_t1023_lsb` = −0.972589, a 0.556 LSB gap that
is essentially the whole reported delta). The schematic bench's own value at
that corner is −0.978255 — i.e. **the manifest-driven extracted and schematic
runs agree with each other to 0.006 LSB and both disagree with the bespoke
deck.**

An error that appears only at the endpoint reached by a near-full-scale step,
and not at the endpoint reached with a full warmup, is the signature of an
**incompletely acquired input sample**, not of a parasitic gain term — the same
1000 ns conversion budget must absorb an 8× larger input step through an
RC-laden input network.

**Disposition, taken deliberately:**

- Record `20260805-163000-e8017f2` is **not edited or deleted** — `sim/` is
  append-only (`sim/README.md`, "Append-only rule"). It stands as what that
  measurement produced.
- The number this document, and any downstream consumer such as #53's
  top-plate-parasitic adjudication, should use for the extracted converter-level
  gain error is **−2.0081 LSB worst (`ff_125c_3.63v`), delta +0.006 LSB vs
  schematic** — the like-for-like value, from a run that used the schematic
  bench's own manifest.
- The decisive control — running the bespoke 2-endpoint deck against the
  *schematic* core, which should reproduce ≈ −2.55 LSB if the deck rather than
  the layout is responsible — was filed as a follow-up when this section was
  first written. **It has since been run, and it does reproduce it.** See
  §4.4.

### 4.4 The control, run: the schematic core reproduces the "extracted" number

`layout/adc-top/parasitics/probe_gain_err_settling.py` drives the bespoke
deck's own two-point ladder, then **holds** transition 1023 for N further
conversions and reads the same error node at each — against **either** core,
changing nothing else in the deck. Record
[`20260805-224500-2c21be4`](adc-inl-dnl/records/20260805-224500-2c21be4.md),
3 PVT points × 2 cores:

| corner | `gain_err_lsb` @ hold 1 — extracted / **schematic** | @ hold 8 — extracted / **schematic** |
|---|---|---|
| `tt_27c_2.97v` | −2.5601 / **−2.5570** | −1.9865 / **−1.9895** |
| `ss_-40c_2.97v` | −2.5946 / **−2.5918** | −1.9839 / **−1.9873** |
| `ff_125c_3.63v` | −2.5406 / **−2.5388** | −2.0038 / **−2.0077** |

Hold 1 is *exactly* the instant `measure_extracted_gain_err.py` reads. At that
instant the **schematic** core — which has no parasitics at all — sits within
**0.003 LSB** of the extracted one and reproduces the whole −2.54 … −2.59 LSB
figure that record `20260805-163000-e8017f2` attributed to layout. By hold 2
both arms have collapsed onto ≈ −1.99 … −2.01 LSB, the value the 18-transition
manifest reports on both netlists. The extracted-minus-schematic difference is
≤ 0.004 LSB at every hold length and every corner probed.

The probe was built able to say "no": had `e1023` been flat across the hold,
step size would not have been the explanation and the script reports that
instead. It is not flat — it moves 0.56 LSB between hold 1 and hold 2 — and it
moves the same way on both cores.

**The mechanism in §4.3 is therefore closed, not merely best-supported.** The
number to use everywhere, including #53's top-plate-parasitic adjudication,
is the like-for-like **−2.0081 LSB worst, delta +0.006 LSB vs schematic**; the
drawn top-plate / interconnect parasitic adds no measurable systematic gain
error on top of the schematic's ≈ −2.00 LSB DR-0012 term. Record
`20260805-163000-e8017f2` remains unedited and undeleted per `sim/README.md`'s
append-only rule; `20260805-224500-2c21be4` carries it in **Supersedes**, for
its `gain_err_lsb` result and the parasitic attribution only.

**Update (issue #98, record [`20260805-230438-048ff7e`](adc-inl-dnl/records/20260805-230438-048ff7e.md)) — the control has now been run, and confirms the mechanism above.**

The bespoke deck's own 2-endpoint stimulus and error-node instrumentation,
wired onto the **schematic** `ADC_TOP` core (`design/adc-top/gen_adc_top.py`'s
`_core()` — zero layout parasitics) instead of the extracted `.SUBCKT`, reports
**mean `gain_err_lsb` = −2.5545 LSB** (range −2.5139 … −2.6278) over the same
27 `tt`/`ff`/`ss` × temp × supply corners — reproducing record
`20260805-163000-e8017f2`'s extracted-core reading (mean −2.5572 LSB) to
within **+0.0027 LSB mean** (range +0.0018 … +0.0045), and disagreeing with
the schematic-manifest baseline (`20260802-141402-1224e11`, mean −2.0020 LSB)
by essentially the *same* −0.55 LSB gap record `20260805-163000-e8017f2`
reported. A core with **no layout parasitics at all** cannot produce a
parasitic-capacitance gain term; the −0.55 LSB delta is therefore **the
bespoke deck's own methodology** — the near-full-scale single-ramp step into
transition 1023 outrunning the DR-0013 input network's acquisition within one
1000 ns conversion, exactly as diagnosed above — **not** a real extracted-layout
effect.

**This closes the open question left above**: the number this document and any
downstream consumer (including #53's adjudication) should use for the
extracted converter-level gain error remains **−2.0081 LSB worst
(`ff_125c_3.63v`), delta +0.006 LSB vs schematic** — record
`20260805-203322-3b6d7b7`'s manifest-driven reading, now **confirmed** rather
than merely preferred. Record `20260805-163000-e8017f2` is **still not edited
or deleted** (append-only); its own numbers remain valid as a measurement of
what its own deck measured — the disposition above only reassigns the
*interpretation* of its extracted-vs-schematic delta from "parasitic gain
attenuation" to "input-acquisition artifact of the 2-endpoint deck". No
secondary control (raising the transition-1023 settling budget) was needed:
the result landed cleanly on the "deck responsible" side of issue #98's
decision tree rather than sitting ambiguously between the two reference
points.

### 4.5 The `cdac` capacitor-corner-set delta (Scope item 7, now closed)

§4's 27-point grid uses `tt`/`ss`/`ff` because those are the corners the
original schematic baseline (`20260802-141402-1224e11`) ran — every MOS
corner, but the capacitor families sit at `*_typical` throughout (`ff`/`ss`
skew every `.lib` section, capacitors included, but do not *isolate* them —
see `sim/harness/README.md`, "Why the capacitor corners matter here"). The
`cdac` corner set (`tt`, `cap_ff`, `cap_ss`, `mim_ff`, `mim_ss`, `moscap_ff`,
`moscap_ss`) isolates each capacitor-family skew individually, which is what a
CDAC's own linearity claim actually rides on.

- schematic record: [`20260805-220405-bff6eaf`](adc-inl-dnl/records/20260805-220405-bff6eaf.md) (PR #100, 63/63 PASS)
- extracted record: [`20260806-052258-8d36824`](adc-inl-dnl/records/20260806-052258-8d36824.md) (this increment, 63/63 PASS, 1100 s wall at `-j 6 --ngspice-threads 1`)
- both runs use `sim/adc-inl-dnl/testbench/tb.json`'s **default** `"corners": ["cdac"]` unmodified — no `--corners`/`--corner-set` override on either side
- shared corners: **63** (7 process corners × 3 temperatures × 3 supplies) — every corner in the extracted record has a schematic counterpart
- per-corner verdicts, read from the records: schematic **all PASS**, extracted **all PASS**
- corners whose verdict changed schematic → extracted: **none**

```bash
python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
    --schematic 20260805-220405-bff6eaf --extracted 20260806-052258-8d36824 \
    --only inl_worst_lsb dnl_worst_lsb gain_err_lsb vref_droop_mv
```

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `inl_worst_lsb` | -0.103629 (`cap_ff_-40c_2.97v`) | -0.106421 (`cap_ff_-40c_2.97v`) | -0.002792 | -2.694 | 0.003094 |
| `dnl_worst_lsb` | 0.103599 (`cap_ff_27c_2.97v`) | 0.105346 (`cap_ff_27c_2.97v`) | +0.001747 | +1.686 | 0.0354985 |
| `gain_err_lsb` | -2.00234 (`cap_ff_-40c_3.63v`) | -1.99676 (`cap_ff_-40c_3.63v`) | +0.00558 | +0.2787 | 0.00639 |
| `vref_droop_mv` | 0.264 (`cap_ss_27c_3.63v`) | 0.324 (`cap_ss_27c_3.63v`) | +0.06 | +22.73 | 0.061 |

**Reading this alongside §4.1.** The worst corner for INL/DNL/gain-error is
`cap_ff` (both `-40c` extremes), not the `mos`-set's `ss_-40c`/`ff_125c`
corners §4.1 reports — expected, since `cap_ff` is the one corner in this set
that skews *both* capacitor families fast while leaving MOS untouched, and
this array's linearity is capacitor-ratio-dominated. The magnitude and sign of
every delta here matches §4.1's pattern closely (worst INL/DNL move by a few
percent, degrading toward full scale; `gain_err_lsb` moves by +0.006 LSB,
matching §4.3/§4.4's now-closed reading to 3 decimal places) — **isolating the
capacitor corners individually does not surface anything the combined `ff`/`ss`
sweep missed.** `vref_droop_mv`'s +22.7% delta is the same reference-buffer
effect §4.1 already reports at the same magnitude; it is not a spec line (no
ratified row names it) and is unchanged in character here.

**Disposition**: Scope item 7 is closed. The schematic half (PR #100) and the
extracted half (this record) now exist at the same 63-point `cdac` grid, both
generated by the unmodified manifest per §1.3/§2's methodology, and the
pairwise delta is derived by `schematic_vs_extracted.py`, not transcribed. The
`ADC_BLOCK` (comparator-inclusive) extension named in the old §6.4 remains a
separate, still-open item — see §6.4 below — and is not part of this item's
scope.

### 4.6 ENOB / SFDR / THD (Scope item 1's dynamic half, now closed)

`layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py` ports
`gen_adc_top.fft_netlist()` onto the extracted core exactly as
`gen_extracted_inl_dnl_tb.py` ports `inl_netlist()` (§1.3): same coherent
64-sample sine, same `se_*`-tagged conversion chain, same gated ideal-shadow
error node (`gen_extracted_core_tb.shadow_dac_and_error(gated=True)`, called
directly rather than re-derived — this deck needed no bespoke copy because
it has no committed byte-identity fixture predating that shared emitter).
`sim/run_corners.py adc-enob-fft --netlist ... --netlist-provenance
extracted` runs `sim/adc-enob-fft/testbench/tb.json` **unmodified**.

**Grid, and why it is a 9-point subset rather than 27.** The schematic
baseline itself (`20260802-141402-1224e11`) is a 9-point subset —
`tt`/`ss`/`ff` × 125 °C only × 3 supplies — per the two-stage corner
strategy `spec/testbench-suite-memo.md` §5 states: the coherent-sampling FFT
is the single most expensive bench per point (66 conversions vs. the static
deck's 18–20), so it runs only at the temperature the cheap full-grid decks
and `sim/comparator-preamp-noise/` jointly identify as worst
(settling/linearity-worst `ss` and independently noise-worst `ff`, both at
125 °C). This run reuses that **same** 9-point grid, unchanged, so the two
captures are point-for-point comparable rather than comparing two different
corner sets — the same discipline §4's `tt`/`ss`/`ff` 27-point grid already
follows relative to the `cdac`-set default.

**Compute, measured**: 9 points, 230 s/point single-threaded (matching the
static deck's ≈3.3× ratio the original §6.1 estimate predicted), completed
in **550 s wall at `-j 6 --ngspice-threads 1`** on this 8-core host.

**Citability correction.** The first capture of this grid,
[`20260806-060520-72a230a`](adc-enob-fft/records/20260806-060520-72a230a.md),
was taken against a dirty working tree and self-flagged as "not citable as a
clean-tree result" (its own `Netlist provenance` field states this). A
second, independently-run capture of the identical deck against a clean tree
(discarded as PR #104, a verified duplicate of this slice) reproduced the
*same* per-corner codes with a clean tree, establishing that the dirty-tree
condition did not affect the result — but citability itself is a provenance
property, not just a numerical-agreement one, so the minimal fix is a clean
re-run of the same deck rather than asserting the discarded duplicate's
numbers. That re-run is
[`20260806-081350-862d054`](adc-enob-fft/records/20260806-081350-862d054.md)
(`Supersedes: 20260806-060520-72a230a`), taken against a clean tree at the
same commit this document ships with — its per-corner `Result` table is
byte-identical to `20260806-060520-72a230a`'s, confirming the dirty-tree
capture was numerically sound; only its citability status changes. All
`sim/extracted-delta-summary.md` references below now cite the clean record.

- schematic record: [`20260802-141402-1224e11`](adc-enob-fft/records/20260802-141402-1224e11.md) (9/9 PASS on the harness's coverage-witness verdict — see the note below on what that PASS does and does not cover)
- extracted record: [`20260806-081350-862d054`](adc-enob-fft/records/20260806-081350-862d054.md) (clean-tree re-run of the prior increment's `20260806-060520-72a230a`, 9/9 PASS, same meaning)
- shared corners: **9** (`tt`/`ss`/`ff` × 125 °C × 2.97/3.30/3.63 V) — every corner in the extracted record has a schematic counterpart
- per-corner harness verdicts, read from the records: schematic **all PASS**, extracted **all PASS**, none changed

**What the harness PASS covers, restated so it is not misread here**: the
coverage witnesses (`code_max`/`code_min` — the sine actually drove the
converter near full scale without clipping) and the `vref_droop_mv`
corner-sensitivity floor. It does **not** cover the ENOB and SFDR rows
themselves — those are spectral quantities, computed by
`sim/adc-enob-fft/testbench/analyze_fft.py` from each record's own raw
per-corner logs, exactly as the schematic record's own note states.

```bash
python3 sim/tools/schematic_vs_extracted.py adc-enob-fft \
    --schematic 20260802-141402-1224e11 --extracted 20260806-081350-862d054 \
    --only code_max code_min vref_droop_mv

python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/20260806-081350-862d054/ --markdown --sigma-extra-lsb 0.0488
```

`--sigma-extra-lsb 0.0488` reuses `spec/testbench-suite-memo.md` §4.3's
composed noise term (153.2 µV rms comparator input-referred noise worst +
35.3 µV rms sampling `kT/C`) unchanged: that term is a property of the
**comparator and the sampling network**, both schematic-level in this
wrapper (issue #89 Scope item 0), not of the CDAC layout this run swaps in
— composing the same noise budget onto both spectra is the correct
like-for-like comparison, not a shortcut.

**Harness-measured columns** (`schematic_vs_extracted.py`):

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `code_max` | 990 (`ff_125c_2.97v`) | 990 (`ff_125c_2.97v`) | +0 | +0 | 0 |
| `code_min` | 33 (`ff_125c_2.97v`) | 33 (`ff_125c_2.97v`) | +0 | +0 | 0 |
| `vref_droop_mv` | 2.049 (`ss_125c_3.63v`) | 2.317 (`ss_125c_3.63v`) | +0.268 | +13.08 | 0.284 |

No clipping on either side (`code_max`/`code_min` identical to the digit),
same droop-worst corner, same pattern §4.1/§4.5 already report for this
node (a reference-buffer effect, not a spec line).

**Spectral columns**, `analyze_fft.py` on each side's own raw logs, ENOB
composed with the noise term above:

| corner-id | schematic ENOB composed | extracted ENOB composed | Δ ENOB | schematic SFDR | extracted SFDR | Δ SFDR |
|---|---|---|---|---|---|---|
| `tt_125c_2.97v` | 9.571 | 9.604 | +0.033 | 64.67 | 65.03 | +0.36 |
| `tt_125c_3.30v` | 9.868 | 9.896 | +0.028 | 69.14 | 70.05 | +0.91 |
| `tt_125c_3.63v` | 9.901 | 9.804 | −0.097 | 68.96 | 67.72 | −1.24 |
| `ss_125c_2.97v` | **9.163** | **9.103** | **−0.060** | **61.33 — FAIL** | **60.11 — FAIL** | **−1.22** |
| `ss_125c_3.30v` | 9.561 | 9.541 | −0.020 | 63.62 | 64.48 | +0.86 |
| `ss_125c_3.63v` | 9.653 | 9.709 | +0.056 | 65.99 | 67.52 | +1.53 |
| `ff_125c_2.97v` | 9.888 | 9.998 | +0.110 | 69.45 | 71.67 | +2.22 |
| `ff_125c_3.30v` | 9.744 | 9.741 | −0.003 | 67.32 | 69.68 | +2.36 |
| `ff_125c_3.63v` | 9.918 | 9.929 | +0.011 | 69.98 | 68.99 | −0.99 |

(ENOB in bits, SFDR in dB. Bold row is the worst corner on both sides —
`ss_125c_2.97v`, the same settling-worst corner §11.6 of the memo names.)

**ENOB @ Nyquist > 9.0**: worst-corner delta **−0.060 bits (−0.65 %)**, max
per-corner swing 0.110 bits (`ff_125c_2.97v`). **9.103 bits worst — still
PASS**, 0.103 bits of margin over the ratified row (was 0.163 bits
schematic). The layout narrows the margin but does not threaten the row.

**SFDR @ Nyquist ≥ 62 dB**: worst-corner delta **−1.22 dB (−1.99 %)**, max
per-corner swing 2.36 dB (`ff_125c_3.30v`, where the extracted side is
*better*). **60.11 dB worst — still FAIL**, at the *same* corner
(`ss_125c_2.97v`) the schematic baseline already failed at, per issue #89
Scope item 6 / §7 below. The margin widens from a 0.67 dB miss to a 1.89 dB
miss — read against §7 before treating that as a new layout-induced
regression: it is not a new corner failing, and the mechanism §11.2 of the
memo diagnoses (acquisition nonlinearity, not settling or top-plate
loading) is unrelated to what changed between schematic and extracted (the
CDAC's parasitic R/C, not the acquisition network). The other eight corners
span 64.48–71.67 dB, all comfortably clear.

**THD**: tracks SFDR's pattern (worst `ss_125c_2.97v`: −57.85 dBc extracted
vs. −58.53 dBc schematic, a **+0.68 dB** — i.e. slightly worse — delta),
consistent with the SFDR-worst corner being distortion-limited on both
sides, as §11.2 of the memo already established for the schematic core.

**Disposition**: Scope item 1's ENOB/FFT/SFDR slice is closed for the
`mos`-set 9-point grid, and §3's spec-line table below is updated
accordingly. The `cdac`-set isolation §4.5 ran for static linearity is
**not** repeated here — the dynamic deck's own two-stage strategy already
scopes it to the temperature/corner subset a full `cdac`×3×3 = 63-point
dynamic grid would cost roughly 63/9 × 550 s ≈ 1 h to run, and nothing in
§4.5's static-linearity finding ("isolating the capacitor corners
individually does not surface anything the combined `ff`/`ss` sweep
missed") suggests the dynamic deck would find something different; left as
a candidate for a future increment if that assumption needs checking
directly, not asserted as already covered.

### 4.7 Power (Scope item 1's last deck — the one that needed a methodology decision first)

`layout/adc-top/parasitics/gen_extracted_power_tb.py` ports
`gen_adc_top.power_netlist()` onto the extracted core on the same pattern as
§4.6's FFT deck, and `sim/run_corners.py adc-power --netlist ...
--netlist-provenance extracted` runs `sim/adc-power/testbench/tb.json`
**unmodified**.

- schematic record: [`20260802-141402-1224e11`](adc-power/records/20260802-141402-1224e11.md)
- extracted record: [`20260806-083932-faebccc`](adc-power/records/20260806-083932-faebccc.md) (this increment, 27/27 PASS, 2413 s wall at `-j 6 --ngspice-threads 1`)
- shared corners: **27** (`tt`/`ss`/`ff` × −40/27/125 °C × 2.97/3.30/3.63 V), the schematic baseline's own grid
- per-corner verdicts, read from the records: schematic **all PASS**, extracted **all PASS**; **none changed**

#### 4.7.1 The per-block split is four-way post-layout, not five-way

This is the reason §6.2 called this deck "a methodology task, not a re-run",
and it is resolved by narrowing the *reported breakdown*, never the claim.

The schematic deck brings out five separately-measured sources: `vddc`
(comparator), `vddd` (CDAC bottom-plate four-leg T-gate drivers), `vddt`
(DR-0014's per-side top-plate V_cm switch and its driver), `vrefs` and `vcms`.
**The drawn layout has one supply rail.** The extracted `.SUBCKT ADC_TOP`
exposes a single `vdd` pin, and the parasitic network on it is a lone
pin-stub `Rvdd`/`Cvdd` pair with every device hung directly off the pin node —
there is no internal `vdd` segmentation to tap, and inserting an ammeter
*inside* the extracted subckt would mean editing extraction output, which §1's
methodology rule forbids.

So `vddd` and `vddt` **merge**:

- `p_cdac_*` on the extracted side carries the CDAC drivers **and** the
  top-plate switch;
- `p_trk_*` reads **exactly 0 by construction** (`vddt` is tied to `vddd`
  through 1 GΩ at identical potential, purely so the node does not have a
  single connection — the record says so, and a reader must not read that zero
  as "the top-plate switch draws no power");
- `p_total_*` — **the spec-line row** — is untouched, because the manifest's
  own expression already sums all five sources. Every microamp the schematic
  deck attributed to `vddt` is still measured and still inside the < 1 mW
  check.

The like-for-like block comparison is therefore made by summing the *same* two
columns on *both* sides (`schematic_vs_extracted.py --sum`, added for this
case; it accepts only a sum of bare column names and is applied identically to
both records, so it cannot make two different quantities look comparable):

```bash
python3 sim/tools/schematic_vs_extracted.py adc-power \
    --schematic 20260802-141402-1224e11 --extracted 20260806-083932-faebccc \
    --sum p_core_f000_uw=p_cdac_f000_uw+p_trk_f000_uw \
    --sum p_core_f050_uw=p_cdac_f050_uw+p_trk_f050_uw \
    --sum p_core_f100_uw=p_cdac_f100_uw+p_trk_f100_uw \
    --only p_core_f000_uw p_core_f050_uw p_core_f100_uw
```

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `p_core_f000_uw` (CDAC + top-plate switch, 0.00 × FS) | 33.8591 (`ff_-40c_3.63v`) | 37.8398 (`ff_-40c_3.63v`) | +3.9807 | +11.76 | 4.50863 |
| `p_core_f050_uw` (0.50 × FS) | 36.0657 (`ff_-40c_3.63v`) | 38.2723 (`ff_-40c_3.63v`) | +2.20657 | +6.118 | 5.2255 |
| `p_core_f100_uw` (1.00 × FS) | 37.7131 (`ff_-40c_3.63v`) | 41.6326 (`ff_-40c_3.63v`) | +3.91945 | +10.39 | 4.48417 |

**The block the layout actually changed costs +6 … +12 %**, at the same worst
corner (`ff_-40c_3.63v`) on both sides — the extracted array's parasitic R/C
has to be charged and discharged every switching event, so a switching-charge
term rising by roughly a tenth is the expected direction and magnitude. It is
~4 µW on a ~180 µW converter.

#### 4.7.2 The spec-line row

```bash
python3 sim/tools/schematic_vs_extracted.py adc-power \
    --schematic 20260802-141402-1224e11 --extracted 20260806-083932-faebccc \
    --only p_total_f000_uw p_total_f025_uw p_total_f050_uw p_total_f075_uw \
           p_total_f100_uw p_cmp_f050_uw p_ref_f050_uw p_vcm_f050_uw
```

| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |
|---|---|---|---|---|---|
| `p_total_f000_uw` | 167.577 (`ff_125c_3.63v`) | 176.741 (`ff_125c_3.63v`) | +9.164 | +5.469 | 10.122 |
| `p_total_f025_uw` | 171.538 (`ff_125c_3.63v`) | 179.743 (`ff_125c_3.63v`) | +8.205 | +4.783 | 8.937 |
| `p_total_f050_uw` | 183.342 (`ff_-40c_3.63v`) | 184.538 (`ff_-40c_3.63v`) | +1.196 | +0.6523 | 12.751 |
| `p_total_f075_uw` | 166.53 (`ff_125c_3.63v`) | 170.85 (`ff_125c_3.63v`) | +4.32 | +2.594 | 6.435 |
| `p_total_f100_uw` | 153.776 (`ff_125c_3.63v`) | **267.309** (`tt_125c_3.63v`) | **+113.533** | **+73.83** | 119.434 |
| `p_cmp_f050_uw` | 122.147 (`ff_-40c_3.63v`) | 118.825 (`ff_125c_3.63v`) | -3.322 | -2.72 | 5.931 |
| `p_ref_f050_uw` | 32.0765 (`ss_125c_3.63v`) | 35.6751 (`tt_125c_3.63v`) | +3.5986 | +11.22 | 10.1645 |
| `p_vcm_f050_uw` | 2.68804 (`ss_27c_3.63v`) | 1.89598 (`ff_-40c_3.63v`) | -0.79206 | -29.47 | 2.38974 |

**`Power @ 1 MS/s < 1 mW`: worst point over the whole extracted grid and all
five input levels is 267.3 µW (`tt_125c_3.63v`, 1.00 × FS) — PASS, 3.7×
inside the ratified bound and still inside the < 500 µW stretch target.** The
schematic worst over the same grid and levels is 183.3 µW, so the row moves
+84.0 µW (+45.8 %) while remaining comfortably clear.

That +45.8 % is **not** a uniform post-layout cost, and must not be read as
one. Four of the five input levels move by +0.7 … +5.5 % worst-vs-worst; the
whole of the difference sits in **one corner at one input level**, and that
one cell is escalated in §7.2 rather than averaged in.

#### 4.7.3 The one outlier, stated rather than absorbed

Per-corner, `p_total_f100_uw` moves by **+2.17 … +4.26 %** at 26 of the 27
corners, and its comparator term `p_cmp_f100_uw` by **−1.33 … +0.98 %**.
At `tt_125c_3.63v` alone, `p_cmp_f100_uw` moves **+105.7 %** (109.4 →
225.0 µW) and drags `p_total_f100_uw` **+80.8 %** (147.9 → 267.3 µW).

A 2× move in a block that is **schematic-level in this wrapper** is exactly
the kind of passing outlier that gets absorbed, so it was diagnosed rather
than reported bare. `layout/adc-top/parasitics/probe_power_cmp_anomaly.py`
re-runs the same deck at that corner against **either** core, instrumented per
conversion (average and peak `i(vddc)`, `i(vddd)`, decoded code) instead of
the manifest's 2 µs level average — record
[`layout/adc-top/parasitics/records/20260806-power-cmp-anomaly.md`](../layout/adc-top/parasitics/records/20260806-power-cmp-anomaly.md).

| conversion | input level | code (sch) | `i(vddc)` avg, sch | code (**ext**) | `i(vddc)` avg, **ext** | peak, sch → **ext** |
|---|---|---|---|---|---|---|
| 14 | 1.00 | 1022 | −29.515 µA | 1022 | −29.508 µA | −1838.39 → −1838.40 µA |
| 15 | 1.00 | 1022 | −30.322 µA | **1023** | **−61.926 µA** | −1838.39 → **−2545.72** µA |
| 16 | 1.00 | 1023 | −29.944 µA | 1023 | **−62.015 µA** | −1838.35 → **−2565.84** µA |

Conversions 15 and 16 are exactly the two the manifest's `f100` window
averages, and the probe reproduces both recorded numbers to the printed
digits. What it establishes:

- **Not a measurement-window artefact** — both conversions in the window carry
  the excess, and conversion 14 at the same input level is normal.
- **Not the static bias** — DR-0007's preamp bias is a fixed 10 µA source in
  both arms. The excess is dynamic: peak draw rises +39 %.
- **Attributable to the extracted core, and not simply "code 1023 costs
  more"** — the schematic arm also reaches code 1023 (conversion 16) at this
  corner and draws a normal −29.9 µA there. The extracted core walks into 1023
  **one conversion earlier** and then stays there drawing 2×; the two cores
  resolve the same full-scale input differently, and the extracted core's
  resolution of it is the expensive one.

What it does **not** establish is the device-level mechanism inside the
comparator, or how close the other 26 corners sit to the same boundary. Both
are named as open in §7.2 rather than guessed at.

**Disposition**: Scope item 1 is now closed for all three #13 spec-line decks
(static linearity §4.1/§4.5, dynamic §4.6, power §4.7). The power row passes
with 3.7× margin; the outlier is carried as an open finding in §7.2, not as a
spec adjustment.

### 4.8 Switch R_on (the Input-structure re-take §6.3 named) — measured twice: exactly zero at the `af5791b` pin, +77.4 Ω at `875eac3`

- schematic record: [`20260806-140624-4f71285`](device-switch-ron/records/20260806-140624-4f71285.md)
  (a clean-tree re-take of `20260731-191216-5f5288b`, which was taken against
  a dirty tree and says so; the deck is unchanged since `3876a8d` and the
  re-take reproduces all 45 corners bit-exactly)
- extracted record: [`20260806-140815-7fa57ad`](device-switch-ron/records/20260806-140815-7fa57ad.md)
- shared corners: **45** (`mos` set `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C ×
  2.97/3.30/3.63 V), `sim/device-switch-ron/testbench/tb.json` **unmodified**
  on both sides
- per-corner verdicts: schematic **45/45 PASS**, extracted **45/45 PASS**, none changed

```bash
python3 layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py --check
python3 sim/run_corners.py device-switch-ron \
    --netlist sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice \
    --netlist-provenance "extracted (adc_tgate leaf, --leaf remediated)"
python3 sim/tools/schematic_vs_extracted.py device-switch-ron \
    --schematic 20260806-140624-4f71285 --extracted 20260806-140815-7fa57ad
```

| measurement | schematic worst | extracted worst | delta | max per-corner delta |
|---|---|---|---|---|
| `ron_t_max` (worst-input T-gate R_on) | 570.436 Ω (`ss_125c_2.97v`) | 570.436 Ω (`ss_125c_2.97v`) | **+0** | **0** |
| `ron_t_min` | 235.324 Ω (`ss_125c_2.97v`) | 235.324 Ω (`ss_125c_2.97v`) | **+0** | **0** |
| `ron_t_flatness` | 3.28898 (`ss_-40c_2.97v`) | 3.28898 (`ss_-40c_2.97v`) | **+0** | **0** |
| `ron_n_*` / `ron_p_*` (control branches, copied verbatim) | — | — | **+0** | **0** |

**0 of 1125 result cells** (45 corners × 25 columns) differ. That is not a
rounding statement: the two records are numerically identical.

**Why, and why that is a finding rather than a non-event.** The deck is the
committed schematic R_on deck with only its transmission-gate branch replaced
by instances of the drawn, extracted `adc_tgate` cell (the generator refuses to
emit unless both sides' device W/L match, so this is like-for-like). What the
extraction adds to that branch is 302.8 Ω of parasitic resistance and 9.235 fF
of parasitic capacitance — and **none of the resistance is in the channel
path**: `klt extract --parasitics` writes each net's R between the net and a
dangling `<net>__par` node that carries only the ground C (§1.4). A DC R_on
measurement therefore cannot see it, and does not.

The measurement is not insensitive — it was shown to resolve in-path series
resistance to ~0.1 Ω by a positive control that moves the same extracted
resistors into the channel and reads +196.2 Ω against the 196.566 Ω the
extraction assigns those two nets. Full method, per-net audit and control:
[`layout/adc-top/parasitics/records/20260806-parasitic-topology.md`](../layout/adc-top/parasitics/records/20260806-parasitic-topology.md).

**Disposition at the `af5791b` pin**: §6.3's Input-structure R_on item was
**closed as measured** — post-layout worst-case T-gate R_on 570.436 Ω at
`ss_125c_2.97v`, unchanged. The `R_WORST_BIT_OHM` re-take that rate closure
needs was **not** closed by it.

#### Update (issue #116): re-measured at the `875eac3` pin — the null is gone

The gap the paragraphs above diagnose (`klayout-tools#592`) closed upstream
via `#593`, and `layout/toolchain.json` is pinned past it. Same deck, same
manifest, same 45-point grid, re-extracted `adc_tgate` leaf — record
[`20260806-194322-68ad582`](device-switch-ron/records/20260806-194322-68ad582.md):

| measurement | schematic worst | extracted worst (`875eac3`) | delta |
|---|---|---|---|
| `ron_t_max` (worst-input T-gate R_on) | 570.436 Ω (`ss_125c_2.97v`) | **647.818 Ω** (`ss_125c_2.97v`) | **+77.4 Ω (+13.6 %)** |
| `ron_t_max` at `tt_27c_3.30v` | 299.410 Ω | **373.820 Ω** | **+74.4 Ω (+24.9 %)** |
| `ron_t_min` | 235.324 Ω (`ss_125c_2.97v`) | **333.340 Ω** (`ss_125c_2.97v`) | **+98.0 Ω (+41.7 %)** |
| `ron_n_*` / `ron_p_*` (control branches, copied verbatim) | — | — | **+0**, as designed |

The added resistance is the drawn cell's own interconnect, now in the current
path: the extraction gives the T-gate's drain legs 60.0163 Ω each and its
source legs 38.2668 Ω each, and the NMOS/PMOS parallel combination of those
four legs is what the +74…+98 Ω is. The NMOS-only and PMOS-only control
branches, which contain no extracted cell, still come back bit-identical —
so the change is confined to exactly the branch that was swapped.

That reconciliation is closed numerically, per input point, in
[`records/20260806-parasitic-topology-inpath.md`](../layout/adc-top/parasitics/records/20260806-parasitic-topology-inpath.md)
§3: at the five input points where one branch carries essentially all the
current, the measured delta lands on the extracted per-branch leg total of
60.0163 + 38.2668 = **98.283 Ω to within 0.3 Ω**; the two mid-range points,
where both branches conduct, fall between that and the parallel limit of
49.14 Ω, as they must. That record also carries the post-bump structural audit
(**330 of 330 parasitic nets in-path, 0 stubs**) and a negative control — the
same script at the same commit re-derives `shunt-stub` from the committed
pre-bump netlists — so the in-path verdict is a property of the netlists, not
of a changed classifier. **Read the worst-of-column headline above with its
own caveat**: at `tt_27c_3.30v` the schematic `ron_t_max` is at `f67` and the
extracted one at `f83`, so the +74.4 Ω there is a worst-to-worst delta, not a
same-point one (`ss_125c_2.97v`'s +77.4 Ω is `f67` on both sides).

**This run reports `status: FAIL`, and the FAIL is left standing.** It is not
a spec check: `sim/device-switch-ron/testbench/tb.json` requires `ron_t_max`
to move ≥ 10 % across the **supply** axis, a liveness guard that the axis is
being swept at all, and it now moves **9.715 %** — because ~75 Ω of
supply-independent interconnect is now in series with a supply-dependent
channel, compressing the relative spread. That is the measurement's physics
changing, not the sweep breaking; the schematic deck still passes the same
guard against the same manifest. Lowering the threshold to make the extracted
run green would be exactly the relaxation CLAUDE.md forbids, so the manifest
is untouched and the FAIL is reported here.

`R_WORST_BIT_OHM` is now a post-layout number, and §6.3's closing update
composes it into #12's rate closure.

#### Update (issue #150): clean-tree re-take of the same measurement

`20260806-194322-68ad582`'s own **Netlist provenance** field says it was
"taken against a dirty working tree ... not citable as a clean-tree result"
(`sim/harness/README.md` "What a run writes") — yet it had stood as the only
citable evidence behind this section for over a week, with no clean-tree
re-take ever minted. Record
[`20260814-191138-f613571`](device-switch-ron/records/20260814-191138-f613571.md)
closes that gap: same deck (re-verified current via `gen_extracted_switch_ron_tb.py
--check` first), same `875eac3`-pin extraction, taken from a clean
`feature/issue-150` worktree. All 45 corners × 25 columns match
`20260806-194322-68ad582` bit-for-bit, including the same supply-axis
liveness-guard FAIL at 9.71502 % — the number was never in question, only its
citability.

That agreement is stronger than a bare re-run, because the two records'
**Environment** blocks are not the same host: `20260806-194322-68ad582` ran
on Linux under ngspice-46 / python 3.12.3, `20260814-191138-f613571` on
macOS under ngspice-47 / python 3.14.7, against the same pinned open_pdks
`c6d73a35…` and the same manifest sha256 `71b1ed2e…`. The per-corner logs
differ only in ngspice's own banner lines (compatibility-mode note, an
`m=xx on .subckt line` warning) with a single numeric exception: in
`sf_125c_3.30v.log`, `m_ron_t_f83` reads `3.9946004807e+02` against the
re-take's `3.9946004808e+02`. That is one count in the 11th significant
digit — it rounds to the same `399.46` at the precision the records report,
which is why the record tables above still agree with zero differing cells.
Stated exactly: **1079 of the 1080 raw `m_ron_*` values reproduce
bit-for-bit, and the remaining one reproduces to 10 significant digits.** So this
measurement is reproducible across ngspice minor version and host OS, not
merely re-runnable on the machine that first produced it — which is what
CLAUDE.md's "an outside reader can re-run them and reach the same
conclusion" actually asks for.

Full determination, and why no companion `timing-budget-closure` re-take is
needed (only a provenance-citation repair), is in §6.4's "Update (issue
#150)".

---

### 4.9 Gain error / INL (DR-0012/13 row, `sim/dr0014-sampling/`) — closed, see §6.3

The gain-error half of §6.3 is now measured.
`layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py` ports
`sim/dr0014-sampling/`'s Group A (the top-plate V_cm switch's own charge
injection and its side-to-side mismatch, plus the sampling path's own gain
error and linearity) and Group C (the second-order residue left by C_par
mismatch between the two sides) onto the extracted core, on a second,
explicitly-scoped manifest (`sim/dr0014-sampling/testbench-extracted/tb.json`)
rather than overloading the schematic manifest's own `measure`/`checks` with
names the extracted deck cannot produce. Group B (the fourth-leg settling A/B)
needs the deck-local DR-0011 three-leg cell, which was never drawn or
extracted — the converter as built has no three-leg cell. Group D (the
isolated T-gate R_on) needs a standalone `adc_tgate` instance at forced
voltage, which the `ADC_TOP`-granularity extracted core used here cannot
address; that measurement was taken separately, against the drawn `adc_tgate`
leaf extraction, in **§4.8** — so it is not re-derived here. Group B has no
extracted equivalent at all: a structural gap, not an omission of
convenience.

```bash
python3 sim/tools/schematic_vs_extracted.py dr0014-sampling \
    --schematic 20260802-141402-1224e11 --extracted 20260807-091733-434dc37 \
    --only tp_inj_signal_dep_lsb bp_inj_mis_lsb samp_inl_l1_lsb samp_inl_l2_lsb \
           samp_inl_l3_lsb samp_gain_err_lsb
```

**Read against the IN-PATH extraction.** The table below is regenerated
against `20260807-091733-434dc37` (issue #131), not the
`20260806-141727-5ba48d5` this section first published. Those two are not the
same experiment: PR #121 regenerated this deck onto the star-split in-path
topology (`adc_top` parasitic R 158 → 2952), so the earlier record measures a
DUT the committed deck no longer is. §4.10 makes the same move for the three
`sim/adc-*` decks; this is the fourth. The numbers move materially and every
verdict holds.

| measurement | schematic worst | extracted worst | delta (worst) | delta % | ratified bound | verdict |
|---|---|---|---|---|---|---|
| `tp_inj_signal_dep_lsb` (Gain error, systematic — DR-0012/13 scope) | 0.0088145 (`ff_-40c_2.97v`) | 0.0016277 (`ff_-40c_3.63v`) | −0.0071868 | −81.53 % | ≤ 0.5 LSB | **PASS**, ~307× margin |
| `bp_inj_mis_lsb` (null control, zero-mismatch) | −1.000e-08 (`ss_-40c_2.97v`) | −1.3785e-04 (`ss_27c_3.30v`) | −1.3784e-04 | n/a (near-zero ÷ near-zero) | ±2 LSB | **PASS**, ~1.5e4× inside the bound |
| `samp_inl_l1_lsb` / `l2` / `l3` (sample's own nonlinearity) | 0.6903 (`tt_-40c_2.97v`) | −0.580725 (`ss_-40c_2.97v`) | +0.109575 | −15.9 % on \|x\| | < 1 LSB | **PASS** |
| `samp_gain_err_lsb` (raw held-value gain error — unbounded by design, see below) | 23.3086 (`ss_-40c_2.97v`) | 63.4789 (`ff_-40c_2.97v`) | +40.1703 | +172.3 % | — (no ratified row) | not a spec check |

**Verdict: PASS at all 27 corners, on both sides, no verdict changed.** The
row this deck exists to substantiate — `tp_inj_signal_dep_lsb`, the DR-0014
sampling switch's own signal-dependent charge injection, DR-0012/13's scoping
of the ratified Gain error, systematic row — sits **~307× inside** the
≤ 0.5 LSB bound after layout (4.588e-04 … 0.0016277 LSB across the grid),
moving by −81.5 % against schematic: a narrowing, not a widening, and a much
larger one than the lumped-stub topology showed (−12.1 %). The null-control
`bp_inj_mis_lsb` term no longer sits at the harness's result-precision floor
as it did on the lumped-stub extraction — it reads ±1.4e-04 LSB, four orders
of magnitude inside its ±2 LSB bound, which is what a real (rather than
identically-zero) parasitic asymmetry between the two drawn sides looks like
under an extraction that finally places resistance in the signal path.
`samp_inl_l1/l2/l3_lsb`, the sample's own nonlinearity against the ratified
INL row, improves in magnitude (0.6903 → 0.5807 LSB worst) and stays inside
1 LSB on both sides.

`samp_gain_err_lsb` — the raw, un-normalised gain error of the *held*
differential top-plate value against its ideal span — is reported (and
carries by far the largest delta of this group's terms, +172 %) but is
**not** a spec check on either manifest: it carries the full
`k = C_arr / (C_arr + C_par)` attenuation factor that DR-0014's own
derivation shows cancels out of the comparator's decision, so bounding it as
if it were an error would mis-state what DR-0014 claims. That is exactly the
term the in-path split should move most — it is the one that *is* the
attenuation — and its moving while every checked term narrows is consistent
with, not evidence against, DR-0014's derivation. `tp_inj_signal_dep_lsb` is
the term DR-0012/13 actually scope to this deck, and it is the one both
manifests check.

**Rate (1 MS/s) closure — still open.** §6.3 named two deliverables; this
increment closes the gain-error half only. Timing-budget closure at 1 MS/s
reuses `sim/timing-budget-closure/`'s testbench and needs its own
extracted-core generator, on the same `_wire_pin()` pattern — not attempted
here.

---

### 4.10 Re-take on the **in-path** extraction (issue #123)

Everything in §4.5–§4.7 above was measured on the **pre-`875eac3`** extraction
— the one §1.4 and record
[`20260806-parasitic-topology`](../layout/adc-top/parasitics/records/20260806-parasitic-topology.md)
show put each net's whole resistance on a dead-end stub with no device
terminal behind it, so 156 R on `adc_top` carried no signal current at all.
PR #119 bumped `layout/toolchain.json` to `875eac3` (`klayout-tools#593`,
star-topology in-path resistance: one `__t<k>` leg node per device terminal
with a distance-weighted series resistor back to the net hub, `r_count`
156 → 2936), and `remediate_extracted._latest_report()` began selecting the
new report immediately — but the three `sim/adc-*` decks are only rewritten
when their generator is run, so they kept emitting the old topology until
issue #123. The extraction basis this repo now stands behind is recorded in
`layout/adc-top/parasitics/README.md`, "Decision record — issue #123".

Three decks regenerated, three claims re-run at their **own existing grids**
(no coverage narrowed because the DUT changed), each appending a dated record
alongside — never replacing — the one it supersedes:

| claim | superseded record (lumped stubs) | in-path record | grid | verdict |
|---|---|---|---|---|
| §4.5 INL/DNL | `20260806-052258-8d36824` | [`20260807-051433-7845f17`](adc-inl-dnl/records/20260807-051433-7845f17.md) | 63 pt `cdac` set | 63/63 **PASS**, 1931 s wall |
| §4.6 ENOB/FFT | `20260806-081350-862d054` | [`20260807-054805-e8cd2b8`](adc-enob-fft/records/20260807-054805-e8cd2b8.md) | 9 pt two-stage subset | 9/9 **PASS**, 970 s wall |
| §4.7 power | `20260806-083932-faebccc` | [`20260807-060526-03e80b9`](adc-power/records/20260807-060526-03e80b9.md) → [`20260807-084749-290d003`](adc-power/records/20260807-084749-290d003.md) | 27 pt `tt`/`ss`/`ff` | spec passes; harness **FAIL** on one sensitivity witness, then **PASS** under the [DR-0018](../spec/decision-records/DR-0018-adc-power-process-axis-floor.md)-revised floor — §7.3 | 

**What moved, lumped-stub → in-path.**

| measurement | lumped stubs | in-path | ratified bound |
|---|---|---|---|
| worst \|INL\| | 0.106 LSB | 0.148 LSB | < 1 LSB |
| worst \|DNL\| | 0.105 LSB | 0.098 LSB | < 1 LSB |
| `vref_droop_mv` worst | 0.324 mV | 0.356 mV | < 50 mV |
| worst ENOB (distortion only) | 9.109 bits | 9.311 bits | see §4.6 / `spec/testbench-suite-memo.md` §11 |
| worst SFDR (distortion only) | 60.11 dB | 64.38 dB | ≥ 62 dB |
| worst `p_total` (any level) | 267.3 µW | 220.9 µW | < 1 mW |

Making the parasitic resistance carry current costs ~0.04 LSB of INL and
~0.03 mV of reference droop, and *improves* the dynamic and power worst
corners — because the term that dominated both of those was the one-corner
comparator excursion §7.2 reports, which the in-path extraction relocates
(§7.3) rather than amplifies. No verdict on any ratified row changes.

**Runnability note, because it is load-bearing for anyone re-deriving these.**
The in-path split adds ~4256 nodes to `ADC_TOP`, and ngspice keeps a
transient waveform for every node unless told otherwise — 260 822 400 B for
the 20 µs INL/DNL deck, which it refuses to allocate ("`Error: memory
required … is more than memory available`"), killing the point before any
measurement. All 63 points died this way at `-j 6`. The three generators now
emit a `.save` naming exactly the vectors their manifest reads
(`gen_extracted_core_tb.saved_vectors_lines()`, derived from the manifest,
not hand-listed); peak RSS drops to 37 MB and the measurements are
bit-identical with and without it (checked directly on `tt_27c_3.30v`:
`m_gain_err_lsb = -1.988646536e+00` either way). ngspice-46 has no `maxdata`
option, so raising the cap is not an available alternative.

`sim/tests/test_extracted_decks_current.py` now runs every
`gen_extracted_*_tb.py --check` invocation on the PDK-free CI path, so a
future report bump cannot leave a deck a generation behind in silence again.
It covered four of the six generators as of this section; issue #131 added
the remaining two (`dr0014_sampling`, `timing_budget`) and gave both the same
`.save` treatment, re-running each against the regenerated deck
(`sim/dr0014-sampling/records/`, `sim/timing-budget-closure/records/`,
2026-08-07).

#### mos-grid re-take (issue #132): the basis for §3's INL/DNL cells

The table above re-runs INL/DNL on its **`cdac`** grid (63 points, `tt` +
6 capacitor-family skews × 3 temperatures × 3 supplies) — the manifest's own
default, and the grid record `20260806-052258-8d36824` already used, so
nothing was narrowed relative to what it replaced. It does **not** re-run the
**other** extracted static-linearity record,
[`20260805-203322-3b6d7b7`](adc-inl-dnl/records/20260805-203322-3b6d7b7.md),
taken on the 27-point **`mos`** grid (`tt`/`ss`/`ff` × −40/27/125 °C ×
2.97/3.30/3.63 V) that §3's INL and DNL cells actually report against — the
`cdac` and `mos` grids are not nested (the `cdac` set holds every MOS section
at typical and skews the capacitor families one at a time; the `mos` set does
the reverse), so the `cdac` re-take above does not stand in for it. That gap
was tracked as issue #132; it is closed by this re-take.

[`20260807-081223-6bd9d80`](adc-inl-dnl/records/20260807-081223-6bd9d80.md)
re-runs `20260805-203322-3b6d7b7` at its own 27-point `mos` grid, on the same
`875eac3`-pin in-path extraction (report `20260806-230838-56be937`) the table
above uses — **27/27 PASS**, 852.7 s wall at `-j 8 --ngspice-threads 1`
(fewer jobs than the `-j 12` the issue suggested: this host has 8 cores, and
`-j 8` avoids the oversubscription that is the likely reason a prior attempt
on a contended host slowed to a crawl — see the record's own environment
block for the host it ran on). `Supersedes: 20260805-203322-3b6d7b7`.

**Lumped-stub → in-path, on the `mos` grid** (`sim/tools/schematic_vs_extracted.py`
against the pre-in-path `mos`-grid record, `--schematic 20260805-203322-3b6d7b7
--extracted 20260807-081223-6bd9d80`):

| measurement | lumped stubs | in-path | ratified bound |
|---|---|---|---|
| worst \|INL\| | 0.111 LSB (`ss_-40c_2.97v`) | 0.148 LSB (`ss_125c_2.97v`) | < 1 LSB |
| worst \|DNL\| | 0.100 LSB (`tt_27c_3.30v`) | 0.090 LSB (`ss_-40c_2.97v`, sign flips) | < 1 LSB |
| `gain_err_lsb` worst | −2.008 LSB (`ff_125c_3.63v`) | −1.995 LSB (`ff_125c_2.97v`) | unbudgeted, no ratified row |
| `vref_droop_mv` worst | 0.323 mV (`ss_-40c_3.63v`) | 0.358 mV (`ss_125c_3.63v`) | < 50 mV |

The worst-\|INL\| move (0.111 → 0.148 LSB) lands in the same few-percent-of-LSB
band the `cdac`-grid re-take shows (0.106 → 0.148 LSB, same table above) —
consistent with §4.10's "what moved" reading: making the parasitic resistance
carry current costs a small, comparable amount of INL regardless of which
corner set stresses the array, and no verdict on either ratified row moves.

**Schematic vs in-path, on the `mos` grid** (`--schematic 20260802-141402-1224e11
--extracted 20260807-081223-6bd9d80`, the pair §3's INL/DNL cells now cite):
worst \|INL\| −0.1082 → −0.1480 LSB (−0.0398 LSB, −36.7 %); worst \|DNL\|
0.1003 → −0.0905 LSB (−0.0098 LSB by magnitude, −9.8 %, sign flips); both
comfortably inside the < 1 LSB bound (and the < 0.5 LSB stretch target) with
no verdict change on any of the 27 shared corners.

### 4.11 An independent second campaign, run concurrently — and what it shows about §7.2's excursion

§4.10's three re-runs were produced twice, by two agents that did not know
about each other, on the same day and against the same extraction report
(`20260806-230838-56be937`, sha256 `db800c70…`). The second campaign's records
are committed here alongside the first, per `sim/README.md`'s append-only rule
— nothing is replaced, and this section reports the comparison rather than
picking a winner:

| claim | §4.10's record | this campaign's record | grid |
|---|---|---|---|
| INL/DNL | `20260807-051433-7845f17` | [`20260807-041111-ccf1f9b`](adc-inl-dnl/records/20260807-041111-ccf1f9b.md) | 63 pt `cdac` set |
| ENOB/FFT | `20260807-054805-e8cd2b8` | [`20260807-052432-eac5d11`](adc-enob-fft/records/20260807-052432-eac5d11.md) | 9 pt two-stage subset |
| power | `20260807-060526-03e80b9` | [`20260807-062903-1e3f48c`](adc-power/records/20260807-062903-1e3f48c.md) | 27 pt `tt`/`ss`/`ff` |

**The one methodological difference, stated up front.** §4.10's campaign added
the `.save` line described above; this campaign ran on a 51 GB host, never hit
the allocation ceiling, and so ran the decks *without* it — every node's
waveform retained. Each record's committed
`sim/<slug>/netlist-snapshots/<record-id>.spice` **is** the deck it was run on,
so both variants are re-runnable from the tree as it stands. That makes the two
campaigns a direct, if unplanned, test of §4.10's "bit-identical with and
without `.save`" claim across the whole grid instead of one corner.

**Result: the two campaigns agree almost everywhere.**

| bench | cells compared | agreement |
|---|---|---|
| ENOB/FFT capture | 675 | **bit-identical** — every code, every corner |
| INL/DNL | 5229 | identical to ≥ 4 significant figures; largest relative difference 4.4 % on a single near-zero cell (`dnl_t256_t257_lsb` at `cap_ss_27c_2.97v`, 8.66e-05 vs 8.28e-05 LSB) |
| power | 837 | identical to ≥ 4 significant figures at **26 of 27 corners**; one corner diverges — below |

That is a strong independent confirmation of §4.10's numbers, and of its
`.save` claim: a 675-cell bit-identical FFT capture is not something a
result-changing edit produces.

#### 4.11.1 The exception is exactly §7.2's comparator excursion, and it does not reproduce

The single disagreement is `ss_27c_3.63v` — the very corner §7.3 identifies as
the relocated §7.2 excursion — and it is confined to that corner's mid-scale
(`f050`) measurement window:

| measurement @ `ss_27c_3.63v` | §4.10 (`03e80b9`) | this campaign (`1e3f48c`) | delta |
|---|---|---|---|
| `p_cmp_f050_uw` | **161.771** | **113.887** | −47.88 µW (−29.6 %) |
| `p_total_f050_uw` | **220.893** | **177.990** | −42.90 µW (−19.4 %) |
| `p_ref_f050_uw` | 29.3875 | 35.950 | +6.56 |
| `p_cdac_f050_uw` | 29.6083 | 28.9309 | −0.68 |
| every other level (`f000`/`f025`/`f075`/`f100`) at this corner | — | — | agree to ≥ 4 s.f. |

In this campaign's run there is **no excursion anywhere on the grid**: worst
`p_cmp` over all corners and levels is 117.5 µW against a 98.5 µW median, and
worst `p_total` is 185.0 µW (`ff_125c_3.63v`, `f050`) — the same corner and
level the *schematic* baseline peaks at, 183.3 µW.

**What that changes about the reading in §7.3.** §7.3 concludes the excursion
"relocated" from `tt_125c_3.63v`/`f100` (pre-in-path) to `ss_27c_3.63v`/`f050`
(in-path), and offers the relocation as evidence for issue #107's item 1 —
a marginal final-trial decision boundary rather than a fixed property of one
PVT corner. This campaign sharpens that: **the excursion does not reproduce on
the same DUT at the same corner in a second run**, while 26 of 27 corners and
every other measurement reproduce to 4+ significant figures. So it is not a
corner property *and* not a topology property; it is a **per-run** outcome at a
marginal point.

Two candidate mechanisms remain, and this evidence does not separate them:

1. **Run-to-run sensitivity at a marginal decision** — the transient's
   operating-point path or timestep sequence tips the comparator's final trial
   one way in one run and the other way in the next. #107's item 1.
2. **`.save` perturbing this one point** — the only known difference between
   the two decks. This is the less likely of the two given the 675-cell
   bit-identical FFT capture and the 26 clean power corners, but it is not
   excluded by them, because a marginal point is exactly where a small
   perturbation would show and a robust point is exactly where it would not.

The experiment that separates them is cheap and is **not** run here: take
`sim/adc-power/netlist-snapshots/20260807-062903-1e3f48c.spice` (no `.save`)
and `…/20260807-060526-03e80b9.spice` (with it), run *each twice* at
`ss_27c_3.63v` alone, and read `p_cmp_f050_uw`. Two runs of the same deck
disagreeing settles it as (1); a clean split along the deck variant settles it
as (2). Reported to issue #107 rather than absorbed here.

**What does not change**: the ratified power row passes on both campaigns'
records (worst `p_total` 220.9 µW and 185.0 µW respectively, against < 1 mW),
and the harness verdict on **both** power records is FAIL for the same reason
— the `p_cmp_f050_uw` process-axis sensitivity witness reads below its 3 %
floor (2.51 % in §4.10's record, 2.37 % here). That witness trips in this
campaign's record *without* an excursion inflating any slice, which means it is
not solely a side-effect of the outlier as §7.3 reads it — the comparator's
mid-scale power is genuinely less process-sensitive on the in-path core at the
weakest slice of that axis. Tracked as issue #133.

---

### 4.12 The DR-0019 re-take: the whole extracted side at `C_u = 35.6528 fF` (issue #218)

**Everything in §4.1–§4.11 measures the layout as it stood at the historical
`C_u = 17.24 fF`.** #196/PR #202 physically implemented DR-0019's resize to
`C_u = 35.6528 fF` — a 2.068× array-capacitance change drawn at a new
geometry — and no extraction postdated it. This section is the post-resize
re-take: one new extraction and five new campaign records, each superseding
its pre-resize counterpart on the **same** deck, manifest and grid, so every
number below is a before/after on one changed variable.

**The re-extraction, and the check that it is the right geometry.**
[`layout/adc-top/parasitics/records/20260817-153913-2494bd0.md`](../layout/adc-top/parasitics/records/20260817-153913-2494bd0.md)
re-runs `run_extract_parasitics.py` against the current GDS. The manifest
spot-check is on the array itself, not on a block total: each of the 1024 MiM
devices in `adc_top.extract.json` reports

| | pre-resize (`20260816-174824-539f5d9`) | post-resize (`20260817-153913-2494bd0`) |
|---|---|---|
| MiM `area_um2` | 7.365796 | **16.0** |
| MiM `c_f` | 1.7244919e-14 F | **3.56528e-14 F** |
| MiM card | `c_length=2.714U c_width=2.714U` | `c_length=4U c_width=4U` |
| `adc_top` ΣC | 5154.95 fF | **5855.91 fF** |
| `adc_top` ΣR | 117 685.26 Ω | **118 907.45 Ω** |
| `adc_block` ΣC / ΣR | 5561.44 fF / 145 386.45 Ω | **6307.03 fF / 146 741.22 Ω** |
| `adc_tgate` (leaf) | 9.234924 fF / 302.798 Ω | **byte-identical netlist** |

`c_f = 35.6528 fF` is DR-0019's ratified unit exactly (31.840 fF plate +
3.813 fF fringe, `layout/adc-top/README.md`), so the extraction belongs to the
resized draw and not to the historical one. `cells.json`'s `expect{}` block and
the two block GDS `sha256` pins were updated to the re-extracted values in the
same change, so the runner keeps asserting against current geometry.

**Reproduce (each campaign, in the order run):**

```bash
# 0. re-extract, and regenerate all five extracted decks from the new report
python3 layout/adc-top/parasitics/run_extract_parasitics.py
for g in inl_dnl enob_fft power dr0014_sampling switch_ron; do
    python3 layout/adc-top/parasitics/gen_extracted_${g}_tb.py --check
done

# 1..5. re-run each campaign against it (-j 6 --ngspice-threads 1 throughout;
#       see §4.10's runnability note for why the thread cap is load-bearing)
python3 sim/run_corners.py adc-inl-dnl  --netlist sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice   --corners tt ss ff              --supersedes 20260807-081223-6bd9d80 --netlist-provenance "extracted …"
python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --corners tt ss ff --temps 125 --supersedes 20260817-164712-3a9afd2 --netlist-provenance "extracted …"   # see §4.12.2 on the two-record chain
python3 sim/run_corners.py adc-power    --netlist sim/adc-power/testbench/tb_adc_power_extracted.spice       --corners tt ss ff              --supersedes 20260807-084749-290d003 --netlist-provenance "extracted …"
python3 sim/run_corners.py sim/dr0014-sampling/testbench-extracted                                                                           --supersedes 20260807-091733-434dc37 --netlist-provenance "extracted …"
python3 sim/run_corners.py device-switch-ron --netlist sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice                         --supersedes 20260814-191138-f613571 --netlist-provenance "extracted …"
```

Every delta table below is produced by `sim/tools/schematic_vs_extracted.py`,
which compares two records **positionally** (`--schematic` = the baseline arm,
`--extracted` = the new arm) and does not itself assert what provenance either
arm has. Where a table below is an *extracted-vs-extracted* before/after, that
is stated in its own caption — the tool's column headers still read
"schematic"/"extracted" and should be read as "before"/"after" there.

| campaign | superseded (pre-resize) | new record (post-resize) | grid | verdict |
|---|---|---|---|---|
| static INL/DNL | `20260807-081223-6bd9d80` | [`20260817-162837-3a9afd2`](adc-inl-dnl/records/20260817-162837-3a9afd2.md) | 27 (`tt`/`ss`/`ff`) | 27/27 PASS, **stretch target now missed** |
| ENOB / SFDR / THD | `20260807-054805-e8cd2b8`, then the dirty-tree `20260817-164712-3a9afd2` | [`20260817-180617-c4693f9`](adc-enob-fft/records/20260817-180617-c4693f9.md) | 9 (125 °C subset) | capture 9/9 PASS; **both spec rows FAIL** |
| power | `20260807-084749-290d003` | [`20260817-174602-71b6844`](adc-power/records/20260817-174602-71b6844.md) | 27 | see §4.12.3 |
| DR-0014 mechanism | `20260807-091733-434dc37` | [`20260817-172040-5c0f0cc`](dr0014-sampling/records/20260817-172040-5c0f0cc.md) | 27 | 27/27 PASS, **improves** |
| switch `R_on` (leaf) | `20260814-191138-f613571` | [`20260817-172213-5c0f0cc`](device-switch-ron/records/20260817-172213-5c0f0cc.md) | 45 (`mos`) | **exact null** |

#### 4.12.1 Static INL/DNL — passes the ratified row, misses the stretch

Extracted **before → after**, 27 shared corners, both records 27/27 PASS:

| measurement | pre-resize worst | post-resize worst | delta | max per-corner delta |
|---|---|---|---|---|
| `inl_worst_lsb` | −0.14796 (`ss_125c_2.97v`) | **−0.528446** (`ss_125c_2.97v`) | −0.380486 | 0.380486 |
| `dnl_worst_lsb` | −0.090489 (`ss_-40c_2.97v`) | **+0.72779** (`ss_125c_2.97v`) | +0.818279 | 0.647164 |
| `gain_err_lsb` | −1.99547 (`ff_125c_2.97v`) | −2.00677 (`ff_125c_3.30v`) | −0.0113 | 0.01301 |
| `vref_droop_mv` | 0.358 (`ss_125c_3.63v`) | 0.679 (`tt_125c_3.63v`) | +0.321 | 0.337 |

- **Reported rather than absorbed**: |INL| 0.528 LSB and |DNL| 0.728 LSB stay
  inside the ratified `< 1 LSB` row — which is why the harness verdict is PASS
  at all 27 points — but they are **outside the `< 0.5 LSB` stretch target**
  the pre-resize extraction cleared by ≈ 3.4×. The stretch is a target, not a
  ratified bound, so no row's verdict flips; nothing here is relaxed to make
  that read better.
- **This is a post-layout interaction, not the resize alone.** The schematic
  side of the same resize moved worst |INL| only 0.1036 → 0.1100 LSB
  (`20260817-131106-abf9c75`, §11.9 of the suite memo). The extracted side
  moves 3.6×. The mechanism the two have in common is that 2.068× more array
  charge now moves through the **same** drawn in-path resistance.
- **The worst transition relocates**, consistent with §4.2's signature: worst
  |INL| moves from `inl_t384_lsb` to **`inl_t896_lsb`**, and worst DNL from
  `dnl_t128_t129` to **`dnl_t767_t768`** — both toward full scale, where the
  array's switched charge is largest.
- **Schematic-vs-extracted at the same `C_u`** can only be taken on the 9
  corners the two grids share (`tt` × 3 T × 3 V — the schematic re-take used
  the 63-point `cdac` set, this deck the 27-point `tt`/`ss`/`ff` set): there
  `inl_worst_lsb` −0.10467 → −0.272117 and `dnl_worst_lsb` 0.0874 → 0.2534,
  i.e. the post-layout cost is ≈ 2.6× on INL and ≈ 2.9× on DNL, and the `tt`
  corners are the *mild* ones — the extracted grid's own worst corner
  (`ss_125c_2.97v`) is not one the schematic re-take's grid shares with it.
- `gain_err_lsb` is unmoved (−0.0113 LSB, 0.6 %), which keeps §4.3/§4.4's
  finding intact at the new `C_u`.

#### 4.12.2 ENOB / SFDR — the governing side now FAILs both rows

**Two records exist for this campaign in this increment, and the citable one is
the second.** `20260817-164712-3a9afd2` was taken while this branch's own
earlier campaign outputs were still uncommitted, so it declares itself
"taken against a dirty working tree … not citable as a clean-tree result"
(`sim/harness/README.md`). It is retained as append-only evidence and
superseded by `20260817-180617-c4693f9`, a clean-tree re-run of the identical
deck and grid that reproduces it **cell for cell — all 75 measurement columns
at delta exactly 0**. Same closure #150/#153 and PR #214 applied to their own
dirty-tree records; nothing about the DUT differs between the two.

The record's own PASS covers capture validity only (9/9); ENOB/SFDR are
computed from its raw logs, as always:

```bash
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/20260817-180617-c4693f9/ --markdown --sigma-extra-lsb 0.0488
```

Extracted **before → after**, all nine corners (composed ENOB, i.e. with the
separately-measured noise terms folded back in):

| corner-id | ENOB was | ENOB now | Δ bits | SFDR was | SFDR now | Δ dB |
|---|---|---|---|---|---|---|
| `ff_125c_2.97v` | 9.599 | 9.329 | −0.270 | 65.48 | 60.84 | −4.64 |
| `ff_125c_3.30v` | 9.797 | 9.203 | −0.594 | 67.65 | 62.96 | −4.69 |
| `ff_125c_3.63v` | 9.481 | 9.268 | −0.213 | 64.38 | **60.40** | −3.98 |
| `ss_125c_2.97v` | 9.414 | **8.969** | −0.445 | 64.93 | 61.09 | −3.84 |
| `ss_125c_3.30v` | 9.668 | 9.172 | −0.496 | 67.87 | 62.96 | −4.91 |
| `ss_125c_3.63v` | 9.675 | 9.116 | −0.559 | 69.49 | 64.09 | −5.40 |
| `tt_125c_2.97v` | 9.513 | 9.087 | −0.426 | 68.62 | 63.13 | −5.49 |
| `tt_125c_3.30v` | 9.302 | 9.214 | −0.088 | 65.79 | 62.90 | −2.89 |
| `tt_125c_3.63v` | 9.735 | **8.857** | −0.878 | 68.19 | 60.98 | −7.21 |

- **ENOB `> 9.0`: PASS → FAIL** at 2 of 9 (`tt_125c_3.63v` 8.857,
  `ss_125c_2.97v` 8.969). All nine corners degrade.
- **SFDR `≥ 62 dB`: PASS → FAIL** at 4 of 9 (`ff_125c_3.63v` 60.40,
  `ff_125c_2.97v` 60.84, `tt_125c_3.63v` 60.98, `ss_125c_2.97v` 61.09). All
  nine degrade, by 2.89–7.21 dB. **This is the row §7.1/§7.3 left with no
  valid governing result**; it now has one, and it misses by 1.60 dB.
- **The worst corner does not carry over from the schematic side, and that is
  a finding, not bookkeeping.** Schematic-worst is `ss_125c_2.97v` (8.506
  bits / 56.41 dB); the extracted core is *better* there (8.969 / 61.09) and
  worse at `tt_125c_3.63v` / `ff_125c_3.63v`. §4.6 recorded the same
  relocation pre-resize and #151 established it is a real corner-dependent
  effect of the in-path CDAC parasitics rather than a deck-comparability
  artefact; the resize preserves that behaviour while shifting the whole grid
  down.
- **Mechanism stays #211's.** §11.9.7 of the suite memo already showed that
  the acquisition-bow term §11.2 argues from *improves* across this resize
  while SFDR degrades; the post-layout re-take does not resolve that, and
  nothing here re-litigates DR-0019's chosen `C_u`.

#### 4.12.3 Power — still PASS, and the growth lands on the two array-facing rails

Extracted **before → after**, 27 shared corners, `Overall: PASS` on both
records, no per-corner verdict changed. The spec-line row is `p_total_*`; the
per-block split stays four-way post-layout for the reason §4.7.1 gives
(`p_trk_*` reads exactly 0 by construction on this netlist, in both vintages):

| measurement | pre-resize worst | post-resize worst | delta | delta % |
|---|---|---|---|---|
| **`p_total_f050_uw`** (worst of all five input levels) | 220.893 µW (`ss_27c_3.63v`) | **246.513 µW** (`ff_27c_3.63v`) | +25.62 µW | **+11.6 %** |
| `p_total_f000_uw` | 176.443 µW (`ff_125c_3.63v`) | 200.460 µW | +24.02 µW | +13.6 % |
| `p_total_f025_uw` | 181.440 µW (`ff_125c_3.63v`) | 213.054 µW | +31.61 µW | +17.4 % |
| `p_total_f075_uw` | 171.575 µW (`ff_125c_3.63v`) | 200.630 µW | +29.06 µW | +16.9 % |
| `p_total_f100_uw` | 157.455 µW (`ff_125c_3.63v`) | 174.391 µW | +16.94 µW | +10.8 % |
| `p_cdac_f050_uw` (merged CDAC + top-plate switch) | 36.146 µW | 43.628 µW | +7.48 µW | +20.7 % |
| `p_ref_f050_uw` (charge drawn from V_REF) | 40.582 µW | 77.071 µW | +36.49 µW | **+89.9 %** |
| `p_cmp_f050_uw` (comparator) | 161.771 µW | 134.999 µW | −26.77 µW | −16.6 % |
| `p_trk_*` | 0 µW | 0 µW | 0 | — (zero by construction, §4.7.1) |

- **`Power @ 1 MS/s < 1 mW` PASSES at 246.5 µW worst** — 4.06× inside the
  ratified bound and still 2.03× inside the `< 500 µW` stretch.
- **The growth is where the array is.** `p_ref_*` (+90 %) and `p_cdac_*`
  (+21 %) are the two terms that move charge onto and off a 2.068× larger
  array; the comparator term, which does not touch it, does not grow. That is
  the same consistency check §11.9.3 applies to the schematic side (V_REF
  +92.2 % there), and the two agree.
- **Against the post-resize *schematic* record** (`20260817-081223-afb1b3a`,
  207.884 µW worst): +38.6 µW, **+18.6 %** — the post-layout cost of the power
  row at the resized `C_u`, now a like-for-like pair.
- **§7.2/§7.3's `tt_125c_3.63v` comparator excursion does not reappear** in
  this vintage, consistent with §4.11.1's finding that it is a marginal-decision
  artefact that does not reproduce run-to-run rather than a corner or layout
  property (issue #107). Neither does the `p_cmp_f050_uw` process-axis
  sensitivity witness that made §4.10's and §4.11's records report `FAIL`
  (issue #133 / DR-0018): this record's overall verdict is **PASS**. Both are
  stated as observations of this run, not as closures of those issues.

#### 4.12.4 DR-0014 mechanism deck — the ratified row it backs improves

Extracted **before → after**, 27 shared corners, 27/27 PASS on both:

| measurement | pre-resize worst | post-resize worst | delta | ratified bound |
|---|---|---|---|---|
| `tp_inj_signal_dep_lsb` | 0.0016277 (`ff_-40c_3.63v`) | **4.774e-04** (`ff_-40c_3.63v`) | −70.7 % | ≤ 0.5 LSB → **PASS, ~1047× inside** (was ~307×) |
| `samp_inl_l1_lsb` | 0.576225 (`ss_-40c_2.97v`) | 0.306975 | −46.7 % | < 1 LSB → PASS |
| `samp_inl_l3_lsb` | −0.580725 (`ss_-40c_2.97v`) | −0.308775 | −46.8 % | < 1 LSB → PASS |
| `bp_inj_mis_lsb` | −1.3785e-04 | +6.050e-05 | sign flip at ~1e−4 LSB | ± 2 LSB → PASS, ~3e4× inside |
| `samp_gain_err_lsb` | 63.4789 (`ff_-40c_2.97v`) | 39.6169 | −37.6 % | — (the `k = C_arr/(C_arr+C_par)` attenuation term; not a spec check on either manifest, §4.9) |

The direction is what an unchanged `C_par` against a 2.068× larger `C_arr`
predicts — the injected charge is diluted into a bigger array — and it matches
the schematic side's own re-take (0.0045–0.0088 → 0.0021–0.0039 LSB,
§11.9.6). Post-resize schematic vs post-resize extracted is now a like-for-like
pair for the first time: `tp_inj_signal_dep_lsb` −87.9 %, and
`samp_inl_l1`/`l3` agree between the two netlists to within 0.002 LSB.

#### 4.12.5 Switch `R_on` — an exact null, measured rather than assumed

DR-0019 resizes the CDAC unit capacitor only, so the drawn `adc_tgate` leaf
this deck extracts is geometrically untouched. That is not asserted here, it is
shown twice over:

- `adc_tgate.para.spice` is **byte-identical** between the pre-resize report
  (`20260816-174824-539f5d9`) and the post-#202 one
  (`20260817-153913-2494bd0`); the regenerated deck differs from the superseded
  record's only in its `* Source:` provenance comment.
- Re-running the 45-point `mos` grid against it reproduces the superseded
  record cell for cell: **max per-corner delta is exactly 0 on 21 of 24
  measurements** and 0.001 Ω (the harness's own result precision) on the other
  three. `ron_t_max` stays **647.818 Ω** at `ss_125c_2.97v`, `ron_t_flatness`
  2.35739.

The record's overall verdict is **FAIL**, for exactly the reason the superseded
record already carries and not for anything this re-take changed:
`ron_t_max`'s `min_spread_pct_by_axis` on the supply axis reads **9.71502 %**
against a 10 % floor, identically in both vintages. That is a deck
corner-sensitivity sanity check, not a spec check (this is a characterization
record with no ratified row) — reproduced and reported, not repaired here.

---

### 4.13 The issue #215 layout-recovery re-take (issue #224)

**Everything in §4.1–§4.12 measures the layout as it stood before issue #215.**
PR #223 (issue #215) folded the comparator's load resistors into a compact
serpentine and re-derived both top-level supply corridors — recovering
29 910 µm² of `adc_block` area — without touching the CDAC/decode core. This
section is the post-#215 re-take: one new extraction and five new campaign
records, each superseding its pre-#215 counterpart on the **same** deck,
manifest and grid, so every number below is a before/after on one changed
variable.

**The re-extraction, and the check that it is the right geometry.**
[`layout/adc-top/parasitics/records/20260817-204449-076d545.md`](../layout/adc-top/parasitics/records/20260817-204449-076d545.md)
re-runs `run_extract_parasitics.py` against the current GDS:

| | pre-#215 (`20260817-153913-2494bd0`) | post-#215 (`20260817-204449-076d545`) |
|---|---|---|
| `adc_top` ΣR / ΣC | 118 907.45 Ω / 5855.91 fF | **118 871.00 Ω / 5843.59 fF** (−0.03 % / −0.21 %) |
| `adc_block` ΣR / ΣC | 146 741.22 Ω / 6307.03 fF | **129 734.59 Ω / 6052.98 fF** (−11.59 % / −4.03 %) |
| `adc_tgate` (leaf) | 302.798 Ω / 9.234924 fF | **byte-identical netlist** |

`adc_top` — the top cell every `sim/*` extracted deck is built from — moves by
a fifth of a percent, because #215 touched the comparator's own cell and two
top-level supply corridors and nothing in the CDAC/decode core. `adc_block`
moves much more, and only there (no campaign in `sim/` is built on it).
`cells.json`'s `expect{}` block and the two block GDS `sha256` pins were
updated to the re-extracted values in the same change.

**Reproduce (each campaign, in the order run):**

```bash
# 0. re-extract, and regenerate the five extracted decks that depend on it
python3 layout/adc-top/parasitics/run_extract_parasitics.py --regen-manifest
for g in inl_dnl enob_fft power dr0014_sampling switch_ron; do
    python3 layout/adc-top/parasitics/gen_extracted_${g}_tb.py --check
done

# 1..5. re-run each campaign against it (-j 6 --ngspice-threads 1 throughout)
python3 sim/run_corners.py adc-inl-dnl  --netlist sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice   --corners tt ss ff              --supersedes 20260817-162837-3a9afd2 --netlist-provenance "extracted …"
python3 sim/run_corners.py adc-enob-fft --netlist sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice --corners tt ss ff --temps 125 --supersedes 20260817-180617-c4693f9 --netlist-provenance "extracted …"
python3 sim/run_corners.py adc-power    --netlist sim/adc-power/testbench/tb_adc_power_extracted.spice       --corners tt ss ff              --supersedes 20260817-174602-71b6844 --netlist-provenance "extracted …"
python3 sim/run_corners.py sim/dr0014-sampling/testbench-extracted                                                                           --supersedes 20260817-172040-5c0f0cc --netlist-provenance "extracted …"
python3 sim/run_corners.py device-switch-ron --netlist sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice                         --supersedes 20260817-172213-5c0f0cc --netlist-provenance "extracted …"
```

Every delta table below is produced by `sim/tools/schematic_vs_extracted.py`,
read as before/after (§4.12's same caveat: the tool's own column headers still
read "schematic"/"extracted").

| campaign | superseded (pre-#215) | new record (post-#215) | grid | verdict |
|---|---|---|---|---|
| static INL/DNL | `20260817-162837-3a9afd2` | [`20260817-214114-076d545`](adc-inl-dnl/records/20260817-214114-076d545.md) | 27 (`tt`/`ss`/`ff`) | 27/27 PASS, **noise-floor move** |
| ENOB / SFDR / THD | `20260817-180617-c4693f9` | [`20260817-215657-076d545`](adc-enob-fft/records/20260817-215657-076d545.md) | 9 (125 °C subset) | capture 9/9 PASS; **both spec rows still FAIL, worst corner unmoved** |
| power | `20260817-174602-71b6844` | [`20260817-211252-076d545`](adc-power/records/20260817-211252-076d545.md) | 27 | see §4.13.3 |
| DR-0014 mechanism | `20260817-172040-5c0f0cc` | [`20260817-204729-076d545`](dr0014-sampling/records/20260817-204729-076d545.md) | 27 | 27/27 PASS, **noise-floor move** |
| switch `R_on` (leaf) | `20260817-172213-5c0f0cc` | [`20260817-204715-076d545`](device-switch-ron/records/20260817-204715-076d545.md) | 45 (`mos`) | **exact null** |

#### 4.13.1 Static INL/DNL — a noise-floor move, no row's verdict changes

Extracted **before → after**, 27 shared corners, both records 27/27 PASS:

| measurement | pre-#215 worst | post-#215 worst | delta | delta % |
|---|---|---|---|---|
| `inl_worst_lsb` | −0.528446 (`ss_125c_2.97v`) | **−0.528287** (`ss_125c_2.97v`) | +0.000159 | +0.030 % |
| `dnl_worst_lsb` | +0.72779 (`ss_125c_2.97v`) | **+0.727556** (`ss_125c_2.97v`) | −0.000234 | −0.032 % |
| `gain_err_lsb` | −2.00677 (`ff_125c_3.30v`) | −2.00677 (`ff_125c_3.30v`) | +0 | +0 % |
| `vref_droop_mv` | 0.679 (`tt_125c_3.63v`) | 0.679 (`tt_125c_3.63v`) | +0 | +0 % |

- **Worst corner and worst transition are unchanged** (`ss_125c_2.97v`,
  `inl_t896_lsb`/`dnl_t767_t768_lsb`, same as §4.12.1) — the move is two to
  three orders of magnitude smaller than the DR-0019 resize's own 0.38/0.82 LSB
  shift, consistent with `adc_top`'s −0.21 % ΣC / −0.03 % ΣR being a fifth of a
  percent, not a structural change.
- Both figures **stay inside the ratified `< 1 LSB` row and outside the
  `< 0.5 LSB` stretch**, exactly as they did pre-#215 — no verdict flips.

#### 4.13.2 ENOB / SFDR — both governing rows FAIL, at the same worst corner

The record's own PASS covers capture validity only (9/9); ENOB/SFDR are
computed from its raw logs, as always:

```bash
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/20260817-215657-076d545/ --markdown --sigma-extra-lsb 0.0488
```

Extracted **before → after**, all nine corners (composed ENOB, i.e. with the
separately-measured noise terms folded back in):

| corner-id | ENOB was | ENOB now | Δ bits | SFDR was | SFDR now | Δ dB |
|---|---|---|---|---|---|---|
| `ff_125c_2.97v` | 9.329 | 9.329 | 0 | 60.84 | 60.84 | 0 |
| `ff_125c_3.30v` | 9.203 | 9.203 | 0 | 62.96 | 62.96 | 0 |
| `ff_125c_3.63v` | 9.268 | 9.268 | 0 | **60.40** | **60.40** | 0 |
| `ss_125c_2.97v` | **8.969** | **8.969** | 0 | 61.09 | 61.09 | 0 |
| `ss_125c_3.30v` | 9.172 | 9.172 | 0 | 62.96 | 62.96 | 0 |
| `ss_125c_3.63v` | 9.116 | 9.142 | +0.026 | 64.09 | 65.05 | +0.96 |
| `tt_125c_2.97v` | 9.087 | 9.127 | +0.040 | 63.13 | 63.23 | +0.10 |
| `tt_125c_3.30v` | 9.214 | 9.214 | 0 | 62.9 | 62.9 | 0 |
| `tt_125c_3.63v` | **8.857** | **8.857** | 0 | 60.98 | 60.98 | 0 |

- **ENOB `> 9.0`: still FAIL** at the same 2 of 9 (`tt_125c_3.63v` 8.857,
  `ss_125c_2.97v` 8.969) — unmoved.
- **SFDR `≥ 62 dB`: still FAIL** at the same 4 of 9 (`ff_125c_3.63v` 60.40,
  `ff_125c_2.97v` 60.84, `tt_125c_3.63v` 60.98, `ss_125c_2.97v` 61.09) —
  unmoved.
- **Only two of nine corners move at all**, both improving, and neither is a
  worst corner for either metric: `ss_125c_3.63v` (+0.026 bits / +0.96 dB) and
  `tt_125c_2.97v` (+0.040 bits / +0.10 dB). Both are `125 °C` corners with
  `ss`/`tt` process and touch the comparator load-resistor network only
  indirectly.
- **Neither spec-line adjudication moves**: worst ENOB 8.857 bits and worst
  SFDR 60.40 dB are exactly the pre-#215 figures, at exactly the pre-#215
  corners. #215's layout change does not touch this row's governing result.

**Issue #249 addendum — clean-tree re-take, and the one measured candidate
fix is not adopted.** The `20260817-215657-076d545` record above was taken
against a **dirty** working tree (its own provenance note states this) and
so was not citable as a clean-tree result. Issue #249 re-ran the identical
deck/manifest/grid on a clean tree:
[`sim/adc-enob-fft/records/20260825-061750-d00911a.md`](adc-enob-fft/records/20260825-061750-d00911a.md),
superseding `20260817-215657-076d545`. Every per-sample code and both
spec-line figures reproduce byte-for-byte — the design did not change (the
current ratified `CDAC_SW_WN`/`CDAC_SW_WP` are still `10u`/`20u`) — so this
re-take confirms rather than moves the FAIL: **worst ENOB 8.857 bits
(`tt_125c_3.63v`), worst SFDR 60.40 dB (`ff_125c_3.63v`)**, unchanged.

Issue #249 also closes the question `sim/dr0019-cu-sweep-findings.md` §4
deferred: #211's orthogonal control (the CDAC cell's acquisition-leg T-gate
widened 2.068×, `10u`/`20u` → `20.68u`/`41.36u`) recovered 89–101 % of this
row's loss in a schematic-level, 125 °C-only probe, but five measurements
were deferred (issue #238) before that recovery could be read as achievable
margin. All five have now landed. Four cost little: charge injection
(`sim/dr0014-sampling/`), top-plate `C_par` (`sim/top-plate-cpar/`),
comparator kickback (`sim/comparator-kickback/`, structurally invariant —
that deck carries no acquisition-leg device), and clock-driver power
(`sim/adc-power/`, +0.41 % worst-case total). The fifth does not: a genuine
`klt`-verified re-layout of the candidate width
([`layout/adc-top/candidates/records/20260825-030447-4e220d1.md`](../layout/adc-top/candidates/records/20260825-030447-4e220d1.md))
grows `adc_block` area +17.00 % (150,536.239 → 176,126.8006 µm²), **+76.1 %**
over the still-ratified `< 0.1 mm²` Area target and **+10.1 %** over even
DR-0024's still-*proposed* `< 0.16 mm²` relaxation — which the ratified
geometry currently satisfies. Adopting the candidate would trade this row's
FAIL for a worse regression on Area, exactly what `CLAUDE.md`'s "do not
relax the ratified spec to make results pass" rules out (here, relaxing a
*different* row's spec to admit a pass on this one). **Decision: the
candidate is NOT adopted** —
[`spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md`](../spec/decision-records/DR-0025-acquisition-leg-widening-not-adopted.md).
`design/adc-top/gen_adc_top.py` is unchanged, and this row's FAIL stands as
a recorded, unresolved regression rather than an open lever.

#### 4.13.3 Power — still PASS, and the comparator load-resistor fold's own effect is real

Extracted **before → after**, 27 shared corners, `Overall: PASS` on both
records, no per-corner verdict changed:

| measurement | pre-#215 worst | post-#215 worst | delta | delta % |
|---|---|---|---|---|
| **`p_total_f050_uw`** (worst of all five input levels) | 246.513 µW (`ff_27c_3.63v`) | **231.834 µW** (`ff_27c_3.63v`) | −14.679 µW | **−5.96 %** |
| `p_total_f000_uw` | 200.46 µW (`ff_125c_3.63v`) | 200.462 µW | +0.002 µW | +0.001 % |
| `p_total_f025_uw` | 213.054 µW (`ff_125c_3.63v`) | 213.049 µW | −0.005 µW | −0.002 % |
| `p_total_f075_uw` | 200.63 µW (`ff_125c_3.63v`) | 200.647 µW | +0.017 µW | +0.008 % |
| `p_total_f100_uw` | 174.391 µW (`ff_125c_3.63v`) | 174.4 µW | +0.009 µW | +0.005 % |
| `p_cmp_f050_uw` (comparator) | 134.999 µW (`ff_27c_3.63v`) | **129.297 µW** | −5.702 µW | **−4.22 %** |
| `p_cdac_f050_uw` (merged CDAC + top-plate switch) | 43.628 µW (`ff_27c_3.63v`) | 44.362 µW | +0.734 µW | +1.68 % |
| `p_ref_f050_uw` (charge drawn from V_REF) | 77.071 µW (`ss_27c_3.63v`) | 77.428 µW (`ss_125c_3.63v`, worst corner moves) | +0.356 µW | +0.46 % |

- **`Power @ 1 MS/s < 1 mW` PASSES at 231.8 µW worst** — 4.31× inside the
  ratified bound and still 2.16× inside the `< 500 µW` stretch (both margins
  *widen* relative to the pre-#215 vintage's 4.06× / 2.03×).
- **This is the one campaign where the small aggregate `adc_top` ΣR/ΣC move
  (−0.03 % / −0.21 %) does not predict the size of the effect.** The mid-scale
  `p_total_f050_uw` figure moves **−6.0 %** and the comparator's own term
  moves **−4.2 %**, both far larger than the aggregate parasitic delta —
  because #215's comparator load-resistor fold changed a resistor the
  comparator's *own* dynamic switching current runs through directly. A
  block-wide ΣR/ΣC summary averages over ~2900 parasitic elements and cannot
  surface a change concentrated in the handful the comparator load sees; this
  is exactly why issue #224 measured rather than assumed the "should move
  very little" expectation.
- **The other four input-level totals (`f000`/`f025`/`f075`/`f100`) barely
  move at all** (≤ 0.02 % each) — those levels' worst corner is
  `ff_125c_3.63v`, not `ff_27c_3.63v`, and evidently sit further from the
  comparator load resistor's own operating point at that corner.
- **`p_ref_f050_uw`'s worst corner itself relocates** (`ss_27c_3.63v` →
  `ss_125c_3.63v`), a small (+0.46 %) but real reminder that a worst-corner
  citation is not guaranteed to survive a layout change even when the
  measurement barely moves in absolute terms.

#### 4.13.4 DR-0014 mechanism deck — a noise-floor move, the ratified row it backs stays deeply PASS

Extracted **before → after**, 27 shared corners, 27/27 PASS on both:

| measurement | pre-#215 worst | post-#215 worst | delta | ratified bound |
|---|---|---|---|---|
| `tp_inj_signal_dep_lsb` | 4.774e-04 (`ff_-40c_3.63v`) | **4.845e-04** (`ff_-40c_3.63v`) | +1.5 % | ≤ 0.5 LSB → **PASS, ~1032× inside** (was ~1047×) |
| `samp_inl_l1_lsb` | 0.306975 (`ss_-40c_2.97v`) | 0.306925 | −0.02 % | < 1 LSB → PASS |
| `samp_inl_l3_lsb` | −0.308775 (`ss_-40c_2.97v`) | −0.308625 | +0.05 % | < 1 LSB → PASS |
| `bp_inj_mis_lsb` | +6.050e-05 | −5.430e-05 | sign flip at ~1e−4 LSB | ± 2 LSB → PASS, ~4×10⁴× inside |
| `samp_gain_err_lsb` | 39.6169 (`ff_-40c_2.97v`) | 39.6196 | +0.01 % | — (not a spec check on either manifest, §4.9) |

- **Every measurement moves by noise-floor amounts** (≤ 1.5 % on the one
  spec-relevant term, `tp_inj_signal_dep_lsb`), the smallest delta of any of
  the five campaigns in relative terms — consistent with the DR-0014 sampling
  mechanism living entirely in the CDAC array and its local drivers, which
  #215 did not touch.
- `samp_gain_err_lsb` (the `k = C_arr/(C_arr+C_par)` attenuation term; not a
  spec check on either manifest, §4.9) is likewise flat.

#### 4.13.5 Switch `R_on` — an exact null, measured rather than assumed

Issue #215's comparator load-resistor fold and supply-corridor re-derivation
never touch `layout/adc-top/cells/adc_tgate.gds`, the drawn transmission-gate
leaf this deck extracts. That is not asserted here, it is shown twice over:

- `adc_tgate.para.spice` is **byte-identical** between the pre-#215 report
  (`20260817-153913-2494bd0`) and the post-#215 one
  (`20260817-204449-076d545`) — `cells.json`'s `adc_tgate` `gds_sha256` pin is
  unchanged across the two extractions.
- Re-running the 45-point `mos` grid against it reproduces the superseded
  record cell for cell: `ron_t_max`, `ron_t_min` and `ron_t_flatness` all
  delta **exactly 0** at their respective worst corners.

The record's overall verdict is **FAIL**, for exactly the reason the
superseded record already carries and not for anything this re-take changed:
`ron_t_max`'s `min_spread_pct_by_axis` on the supply axis reads **9.71502 %**
against a 10 % floor, identically across all three vintages now on record.
That is a deck corner-sensitivity sanity check, not a spec check (this is a
characterization record with no ratified row) — reproduced and reported, not
repaired here.

---

## 5. Scope item 2 — Monte Carlo on the extracted netlist: the explicit answer

Issue #89 Scope item 2 asks for a #14 Monte Carlo re-run against the extracted
netlist "if the extraction flow's parasitic/mismatch models support statistical
variation — state explicitly if not." Stating it explicitly:

**1. #14's bench has no netlist to swap.** `sim/mc-cdac-mismatch/testbench/mc_cdac_mismatch.py`
is a *behavioral* numpy model of CDAC unit-cap mismatch, not an ngspice deck. It
never invokes ngspice. There is no `--netlist` to point at an extraction; a
"re-run against the extracted netlist" is not a defined operation on it.

**2. The reason it is behavioral applies equally to the extracted netlist.** The
gf180mcu open PDK ships **no local capacitor mismatch model** —
`cap-local-mismatch` and `moscap-statistics` are both `ABSENT` findings from
`sim/tools/pdk_mismatch_audit.py` (`sim/device-characterization-report.md` §5.1).
Independently confirmed here for the exact subckt this extraction binds to:
`sm141064_mim.ngspice` contains no `agauss`, no `mis_*` term and no
`sw_stat_mismatch` reference at all. An ngspice Monte Carlo of the extracted
CDAC would report *exactly zero* capacitor mismatch regardless of trial count —
a silent false pass, which is worse than no number.

Extraction does not change this. `klt extract --parasitics` emits ideal R and C
values plus PDK device calls; it carries no statistical construct of its own, so
it cannot supply the mismatch the PDK omits.

**3. What *is* statistically available on the extracted netlist — measured,
not asserted.** The extracted MOS devices are `X … nfet_03v3` / `pfet_03v3`
PDK subckt calls, which *do* pick up the PDK's `fets_mm` threshold-mismatch
statistics when `sw_stat_mismatch = 1` (the mechanism
`sim/comparator-offset-mc/` uses). When this section was first written that
was stated as "technically supported" and deferred. It is no longer deferred:
`layout/adc-top/parasitics/mc_extracted_core.py` runs a real 120-draw
mismatch population of full transistor-level conversions on the remediated
extracted core at transition 256 (the array's worst carry), with a
**mandatory** mismatch-off null control — record
[`layout/adc-top/parasitics/records/20260805-extracted-core-mc.md`](../layout/adc-top/parasitics/records/20260805-extracted-core-mc.md).

| population | `sw_stat_mismatch` | N | mean (LSB) | σ (LSB) | distinct draws |
|---|---|---|---|---|---|
| mismatch-on | 1 | 120 | +0.48656 | **1.99e-03** | 120 |
| null control | 0 | 12 | +0.48659 | **0.0** | 1 |

So MOS local mismatch **does** reach the extracted devices, and it is a
≈ 2e-3 LSB (1σ) term at the worst carry — about 5 % of that transition's own
≈ 0.10 LSB DNL and three orders inside the < 1 LSB bound. The null control is
not decoration: it caught three separate ways this run silently reported a
plausible-looking wrong answer (statistical switches placed before the PDK
includes and overridden; `meas`'s 6-digit echo double-counting every draw; an
in-deck σ that returns NaN for a frozen population), each recorded in that
record rather than quietly fixed.

**What this still does not cover** is the *comparator*: the ratified rows that
ride hardest on MOS mismatch — Offset, and the comparator's INL contribution —
live in the comparator, which is schematic-level in this wrapper (the
extracted core is `ADC_TOP`: the CDAC array and its switches). A
comparator-inclusive post-layout mismatch claim needs `ADC_BLOCK` (core +
comparator), already extracted and remediated, named in §6.4 as remaining
work — **attempted this increment and found blocked, not merely unbuilt**:
`gen_extracted_core_tb.py --top ADC_BLOCK` now wires the comparator-baked-in
extraction, but its own functional smoke test (`records/../
records/20260806-adc-block-comparator-smoke.md`) reproducibly decodes every
probed transition to the same stuck code at two PVT corners — a real
functional defect the DC-only remediation check never exercised, not a
missing harness. `mc_extracted_core.py` is deliberately kept `ADC_TOP`-only
until that is resolved, so a comparator-inclusive Monte Carlo cannot be run
against a core that is not yet known to decide correctly.

**Net answer: Scope item 2 is answered for both halves. The CDAC-capacitor
half is not possible on any netlist in this PDK, extracted or schematic, and
#14's behavioral model remains the only available instrument. The
MOS-mismatch half is possible, and has now been run on the extracted core —
with the comparator-inclusive variant on `ADC_BLOCK` named as remaining work
rather than skipped silently.**

---

## 6. What is not yet measured, and what each one needs

### 6.1 ENOB / SFDR / THD (`sim/adc-enob-fft/`) — closed, see §4.6

`layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py` now exists, on the
pattern this section originally called for
(`gen_extracted_inl_dnl_tb.py`'s stimulus/measurement-node porting), and the
9-point `tt`/`ss`/`ff` × 125 °C grid the schematic baseline itself uses
(the two-stage corner strategy, not the original 27-point estimate below)
has run on both sides. **See §4.6** for the full delta table: ENOB PASSES
(9.103 bits worst, −0.060 bits vs. schematic), SFDR continues to FAIL at
the same corner the schematic baseline already failed at (60.11 dB vs. the
62 dB target, §7). Measured compute: 230 s/point single-threaded (not the
~1.5 h/27-point-grid estimate below, both because the actual grid run is
9 points and because `--ngspice-threads 1 -j 6` parallelises cleanly rather
than the naive single-threaded estimate) — 550 s wall for the full 9-point
grid.

*Original estimate, kept for the record*: this deck runs **66 conversions
per PVT point** (`FFT_WARMUP_CONV = 2` + `FFT_N = 64`) against the static
deck's 20 (`INL_WARMUP_CONV = 2` + 18 probed transitions ×
`INL_CONV_PER_POINT = 1`), i.e. ≈ 3.3× the 86 s/point the static deck
measured — the ≈ 3.3× ratio held (230 s vs. 70 s/point at
`--ngspice-threads 1`); what changed was scoping the grid to the 9 points
the schematic baseline itself uses rather than a 27-point `mos`-set sweep.

### 6.2 Power (`sim/adc-power/`) — closed, see §4.7

The methodology task this section named has been done, and its answer was
**not** the one the section assumed. It assumed the decomposition could be
"re-derived against the extracted core's actual supply pins". It cannot: the
drawn layout has **one** supply pin, so `vddd` (CDAC bottom-plate drivers) and
`vddt` (DR-0014's top-plate V_cm switch) are not separable post-layout at all.
The resolution taken — coarsen the reported breakdown from five-way to
four-way, leave the claim and the manifest untouched, and state the merge in
the record and the deck header — is written up in **§4.7.1**, with the
like-for-like merged-rail comparison derived by `schematic_vs_extracted.py
--sum`.

**See §4.7** for the full result: the block the layout actually changed costs
**+6 … +12 %**, and the ratified `Power @ 1 MS/s < 1 mW` row **PASSES** at
**267.3 µW worst** (3.7× inside the bound, and inside the < 500 µW stretch
target). One corner-and-level cell — `tt_125c_3.63v` at full scale — moves
+81 % against +2.2 … +4.3 % everywhere else; it is diagnosed in §4.7.3 and
escalated in §7.2 rather than averaged in. Measured compute: 2413 s wall for
the 27-point grid at `-j 6 --ngspice-threads 1` (~455 s/point
single-threaded).

### 6.3 Gain error (DR-0012/13 row) — closed, see §4.9; rate closure — closed at issue #116, fully post-layout

> **RE-STATED at issue #116.** This section previously concluded that rate
> closure was "not measurable at this extraction fidelity", because the
> extraction carried no in-path resistance. That conclusion was correct at the
> `af5791b` pin and is *no longer* correct: upstream `klayout-tools#592` —
> which this project filed, citing this very section — closed via `#593`, and
> `layout/toolchain.json` is pinned past it. The narrative below is kept as
> written, with a closing update, because it is the reasoning that produced
> the upstream filing and it says exactly which of its own conclusions the fix
> retires. **All three inputs are now post-layout** — the third
> (`T_COMP_REGEN_NS`) closed later in the same issue; see this section's own
> closing update and §6.4's.

This section named two deliverables, both reusing other experiments'
testbenches (`sim/dr0014-sampling/`, `sim/timing-budget-closure/`). The
gain-error half is now **closed** on an extracted-core deck, in the same
shape as §6.1. The rate half is not, and what blocks it turned out to be
structural — an extraction-fidelity gap, not another `gen_extracted_*_tb.py`
still to be written.

**Gain error / INL (`sim/dr0014-sampling/`) — closed.**
`layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py` now exists,
porting Groups A and C onto the extracted core. **See §4.9** for the full
delta table: the ratified Gain error, systematic row (via
`tp_inj_signal_dep_lsb`) **PASSES** at all 27 corners, ~307× inside the
≤ 0.5 LSB bound and narrowing by 81.5 % post-layout; the sample's own INL
(`samp_inl_l1/l2/l3_lsb`) also PASSES, improving from 0.6903 to 0.5807 LSB
worst. (Those figures are the in-path re-take, `20260807-091733-434dc37`;
the lumped-stub reading this paragraph first carried was ~65× / −12.1 % /
under 0.4 %.)

An earlier reading of this section held that this row needed a standalone
`adc_cdac_side` leaf extraction — which does not exist — and was therefore
*not measurable at this extraction fidelity*. That reading is superseded, and
the reason is checkable rather than a matter of judgement: the flat `ADC_TOP`
extraction **is** the union of exactly the cells Groups A/C isolate.
`design/adc-top/gen_adc_top.py`'s `adc_cdac_side` is nine `adc_cdac_cell`
instances plus one terminating cap, and `_core()` instantiates the array from
exactly 2× `adc_cdac_side` + 2× `adc_tp_sw` and nothing else — 9 × 16 × 2 +
2 × 4 = **296 FETs**, which is precisely the extracted `ADC_TOP` device count
recorded in `layout/adc-top/parasitics/README.md`. Wiring one `Xdut ADC_TOP`
per DR-0014 probe pair, on tag-scoped private analog nets, therefore gives
each pair a real, post-layout array side without needing a leaf-cell GDS that
was never drawn. It is the same substitution mechanism (`_wire_pin()`, from
`gen_extracted_core_tb.py`) already accepted for the three closed §6.1/§6.2
decks. The measured quantity, `tp_inj_signal_dep_lsb`, is an instantaneous
node-voltage snapshot difference at switch opening — not an RC-settling or
IR-drop quantity — so the in-path-resistance gap below (§1.4) does not touch
it.

Groups B and D are **not** ported, for reasons that remain structural: Group B
needs the deck-local DR-0011 three-leg cell, which the converter as built does
not contain and which was never drawn or extracted; Group D needs a standalone
`adc_tgate` instance at forced voltage, which an `ADC_TOP`-granularity core
cannot address — that measurement was instead taken directly against the drawn
`adc_tgate` leaf extraction, and is reported in §4.8 (first bullet below).

**Rate (1 MS/s) closure (`sim/timing-budget-closure/`) — still open**, and
what blocks it is *not* a missing deck. Checked directly against the generator
code and the extraction manifest, not assumed:

- **Group D (the Input-structure R_on re-take) — DONE, and its answer
  changes this section's conclusion.** This was named here as the one piece
  tractable without new layout: `adc_tgate.gds` **is** a standalone drawn leaf
  cell, so it can be extracted and measured. It now has been.
  `run_extract_parasitics.py`'s manifest carries an `adc_tgate` leaf target,
  `remediate_extracted.remediate_leaf()` promotes its anonymous PMOS-body net
  to a `vnw` pin (a leaf has no supply pin to tie to), and
  `gen_extracted_switch_ron_tb.py` splices the drawn cell into
  `sim/device-switch-ron/`'s own deck.

  **Result at the `af5791b` pin: 45/45 PASS on both sides and 0 of 1125
  result cells different** (§4.8). Worst-case T-gate R_on stayed 570.436 Ω at
  `ss_125c_2.97v`. **Re-run at the `875eac3` pin it is 647.818 Ω, +77.4 Ω** —
  see this section's closing update.

  The reason is not that the layout is free — it is that **this extraction
  carries no in-path resistance to find** (§1.4): all 332 parasitic resistors
  across the three extracted blocks are stubs, so 115 kΩ of extracted
  `ADC_TOP` resistance sits outside every signal path. A positive control
  that moves the same resistors into the channel shifts the measurement by
  +196.2 Ω, so the null is a property of the extraction, not of the deck
  ([`records/20260806-parasitic-topology.md`](../layout/adc-top/parasitics/records/20260806-parasitic-topology.md)).

  **This generalises past Group D.** Reading `R_WORST_BIT_OHM` off the
  extracted array — whether via a drawn `adc_cdac_side.gds` or via the flat
  `ADC_TOP` boundary §4.9 uses — would *also* return the schematic value,
  because the extractor models array interconnect the same way it models the
  T-gate's. So a post-layout settling-resistance re-take needs an extraction
  flow that emits distributed or in-path net resistance. That is an extractor
  capability, filed as tool friction upstream per CLAUDE.md's canary rule
  rather than worked around locally, and it is why the §3 **rate-closure** row
  stays **not measurable post-layout at this extraction fidelity** rather than
  being backfilled with the schematic number relabelled as an extracted one.
  (The DR-0012/13 gain-error row is a different quantity and is *not* caught by
  this: `tp_inj_signal_dep_lsb` is a charge-injection voltage snapshot with no
  resistance in its definition — measured, and PASS, §4.9.)
- **`sim/timing-budget-closure/` is a fully synthesized rung-1 composition
  with no netlist at all** (`design/sar-logic/gen_sar_logic.py`'s
  `_budget_closure_body()`, and its own header: "rung-1 ideal-digital +
  behavioural analog carries no PDK device models, so process/temperature
  cannot move anything here"). It plugs in three literal constants —
  `R_WORST_BIT_OHM` / `C_WORST_BIT_F` (the CDAC bit-trial settling network,
  `sim/dr0014-sampling/` Group D / spec/cdac-sizing-memo.md §5.3) and
  `T_COMP_REGEN_NS` (the comparator's own regeneration delay, `sim/
  comparator-regeneration/`, #9). There is no core to swap; "closing" it
  post-layout means re-measuring those three inputs and re-composing the
  same deck with the new values. Two of the three (`R_WORST_BIT_OHM`,
  `C_WORST_BIT_F`) are settling-network quantities and hit the in-path
  resistance gap above; the
  third, `T_COMP_REGEN_NS`, is comparator-only and is unaffected by the
  `ADC_TOP`-only extracted core used everywhere in §4/§5/§6.1/§6.2 (the
  comparator stays schematic-level in that wrapper by construction, Scope
  item 0) — a post-layout comparator regeneration delay needs the
  comparator-**inclusive** `ADC_BLOCK` core, which is §6.4's still-open,
  functional-defect-blocked item, not a separate task.

**Net effect**, restated after both this increment's gain-error closure and
the Group D measurement above: the DR-0012/13 gain-error row is **measured and
PASSING** post-layout (§4.9). Rate closure, *as #12 originally measured it*,
remains blocked on **two** things, of which the second is the binding one and
is not a deck:

1. §6.4's `ADC_BLOCK` functional defect, for the `T_COMP_REGEN_NS` input;
2. **the extraction carries no in-path resistance at all** (§1.4, §4.8) —
   measured, with a positive control, on the one leaf cell that *is* drawn.
   `R_WORST_BIT_OHM` is a resistance, so it comes back identical to the
   schematic value by construction, on any extraction boundary.

Per CLAUDE.md's no-relaxation rule the rate-closure row stays reported as a
not-measured row in §3 — not skipped, not backfilled with a differently-scoped
substitute number, and specifically not "closed" by relabelling the schematic
resistance as an extracted one, which is the tempting move once the deck
exists and returns the same number.

The extractor-capability gap in (2) is generic to the open gf180mcu flow —
any post-layout R_on, IR-drop, electromigration or RC-settling question hits
it. Per CLAUDE.md's canary rule it belongs upstream, and it is already there:
[`klayout-tools#338`](https://github.com/2AMLogic/klayout-tools/issues/338),
closed 2026-08-03 as a **documentation-only** fix that deliberately deferred
the model change and asked for a follow-up issue to carry it. That follow-up
did not exist as of 2026-08-06 — it was then filed,
[`klayout-tools#592`](https://github.com/2AMLogic/klayout-tools/issues/592),
carrying the actual model-change ask (star-topology split or full
distributed RC) with this project's structural audit and R_on null result as
substantiating evidence — see §1.4.

#### Update (issue #116): `#592` landed, and blocker (2) is retired

`klayout-tools#592` closed `COMPLETED` on 2026-08-06 via merged PR `#593`
(merge commit `875eac3`, the star-topology split). `layout/toolchain.json` is
pinned past it. What that changes here, measured rather than predicted:

| input | schematic | post-layout | source |
|---|---|---|---|
| `R_WORST_BIT_OHM` | 570 Ω (`ss_125c_2.97v`) | **648 Ω** (647.818, same corner) | [`20260806-194322-68ad582`](device-switch-ron/records/20260806-194322-68ad582.md), 45-point PVT grid against the extracted `adc_tgate` leaf |
| `C_WORST_BIT_F` | 2.20672 pF | **2.40712 pF** | schematic `Ceq(w=256)` + 200.4 fF extracted `topp` top-plate parasitic ([`20260806-193910-68ad582`](../layout/adc-top/parasitics/records/20260806-193910-68ad582.md); `topn` is 189.7 fF, `topp` is the worse side) |
| `T_COMP_REGEN_NS` | 0.859 ns (re-run at the issue #118 resistor resize) | **still schematic** | `ADC_BLOCK` now converts (issue #118, §6.4 update) — the comparator-inclusive regeneration campaign through the extracted core just has not been run yet (issue #89 Scope item 2) |

Blocker (1) — §6.4's `ADC_BLOCK` defect — is now **root-caused and, for the
functional half, fixed**: the floating-input cause (#116) and the
unmarked-resistor-short cause (#118, drawing `SAB`/`RES_MK`/`Resistor`
markers) are both resolved, and `ADC_BLOCK` converts (§6.4 update below).
What is **not resolved** is the upstream extraction-deck capability gap
(`klayout-tools#595`, the `_2k`/`_3k` sheet-rho selection) and the
comparator-inclusive regeneration/offset campaigns through the extracted
core, neither of which #118 attempted — so `T_COMP_REGEN_NS` stays
schematic-level for now.

`layout/adc-top/parasitics/gen_extracted_timing_budget_tb.py` re-composes
#12's deck with the two post-layout values and nothing else changed — same
manifest, same analyses, same ratified thresholds. Result
([`20260806-195653-9cf262a`](timing-budget-closure/records/20260806-195653-9cf262a.md),
re-taken from a clean tree as
[`20260807-082234-eb860c1`](timing-budget-closure/records/20260807-082234-eb860c1.md)
after issue #131 added the deck's `.save` line — every cell identical between
the two, which is what that re-run was for):
**PASS**, with every `abs_err_*` cell bit-identical to the schematic-level
record [`20260802-112832-ed9a325`](timing-budget-closure/records/20260802-112832-ed9a325.md)
(0/0/0/255 at 1 MS/s, 0/0/256/257 at 2 MS/s). The settling time constant moves
1.258 ns → **1.560 ns** against a 62.5 ns bit cycle — a 24 % increase in a
term that is 40× smaller than the budget it sits in, which is why no verdict
moves.

Per CLAUDE.md's no-relaxation rule the §3 rate-closure row was recorded as
**PASS on two of three post-layout inputs**, stated in exactly those words —
not as a fully post-layout closure, and not backfilled by relabelling the
schematic `T_COMP_REGEN_NS` as an extracted one. Issue #17's AC7 was
therefore **still not satisfied**; what remained was the single input above.

#### Update (issue #116): `T_COMP_REGEN_NS` measured, rate closure fully post-layout

The remaining input is now measured, closing this row. §6.4's update below
covers the full methodology (a comparator-inclusive `ADC_BLOCK` regeneration
campaign, with #9's overdrive ladder referred to the extracted core's own
measured systematic offset — a new, deterministic post-layout finding in its
own right). Summary of what changes here:

`T_COMP_REGEN_NS` worst-corner (`ss_125c_2.97v`, same corner every other
input in this row cites) moves **0.863 ns → 1.257 ns** (measured 1.25638 ns,
rounded up — [`sim/comparator-regeneration/records/
20260814-215626-f613571`](comparator-regeneration/records/20260814-215626-f613571.md),
45/45 corners PASS every ratified check). `layout/adc-top/parasitics/
gen_extracted_timing_budget_tb.py` substitutes all three post-layout values
into the same unmodified `sim/timing-budget-closure/testbench/tb.json`
manifest; result
[`20260814-220124-f613571`](timing-budget-closure/records/20260814-220124-f613571.md),
superseding [`20260807-082234-eb860c1`](timing-budget-closure/records/20260807-082234-eb860c1.md):
**PASS** at both 1 MS/s and the 2 MS/s stretch, at every bracket that was
already meant to pass (`logic0ns`/`logic10ns` at both rates, `logic25ns` at
1 MS/s: 0 error, bit-identical to the schematic record). The two brackets
that were ALREADY the negative control (deliberately over budget:
`logic25ns` at 2 MS/s, `logic55ns` at both rates) move to reflect the larger,
real comparator delay (256/384 vs the schematic's 256/255 and 257) — moving
further into their already-expected failure territory is not a new finding;
those brackets exist to demonstrate what "too much added delay" looks like,
not to pass.

Per CLAUDE.md's no-relaxation rule, restated now that it is fully satisfied
rather than partially: the §3 rate-closure row is **PASS on all three
post-layout inputs**, and issue #17's AC7 is satisfied for this row.

### 6.4 The `cdac` capacitor-corner set (closed), and `ADC_BLOCK` (open)

- **Corner set — closed.** §4's 27-point grid used `tt`/`ss`/`ff` rather than
  the manifest's default `cdac` set (7 process corners × 3 × 3 = 63 points)
  because those 27 are exactly the corners the original schematic baseline
  ran. `ff`/`ss` *do* include `mimcap_ff`/`mimcap_ss`, so the MiM process
  corners were already exercised on both sides of every §4 delta; what was
  missing was the `cdac` set's **isolation** of each capacitor-family corner
  individually (PR #100 closed the missing schematic half; this increment
  closed the extracted half and the pairwise comparison). **See §4.5** for
  the full delta table: 63/63 shared corners, both sides all-PASS, no verdict
  changed, and every reading matches §4.1's `mos`-set pattern to within the
  same few-percent band — isolating the capacitor corners individually does
  not surface anything the combined `ff`/`ss` sweep missed. Scope item 7 is
  now fully closed.
- **`ADC_BLOCK` — still open, now blocked on a found-and-recorded defect,
  not merely unbuilt.** `remediate_extracted.py` already generalises to it
  (160 PMOS devices / 25 body islands retied, 1024 MiM caps confirmed, DC
  verified 63/63). Using it in place of `ADC_TOP` would put the
  **comparator** inside the extracted boundary too, which is what a
  *comparator-inclusive* extension of §5's MOS-mismatch Monte Carlo — and any
  comparator-offset post-layout claim — requires. §5's run and §4/§4.5's runs
  all cover the CDAC array and its switches only, not the comparator.
  This increment built the wiring (`gen_extracted_core_tb.py --top
  ADC_BLOCK`, `verify_extracted_core_conversion.py --top ADC_BLOCK`) and ran
  its functional smoke test before attempting any Monte Carlo population —
  the test **FAILs, reproducibly**: every probed transition decodes to the
  same stuck code (1023) at both a nominal and the worst-case PVT corner,
  independent of dout/doutb polarity, while the `ADC_TOP` control at the same
  commit is unaffected. Root cause not identified (ngspice's initial
  transient bias-point solve reports a singular internal node,
  `xdut.$168`, through every fallback before an unreliable "success");
  full repro, diagnostics, and what was ruled out are in
  [`records/20260806-adc-block-comparator-smoke.md`](../layout/adc-top/parasitics/records/20260806-adc-block-comparator-smoke.md).

#### Update (issue #116): the `ADC_BLOCK` defect is root-caused — two causes, one fixed, one filed upstream

Full evidence:
[`records/20260806-adc-block-comparator-input-float.md`](../layout/adc-top/parasitics/records/20260806-adc-block-comparator-input-float.md).
Summary, because the conclusion is load-bearing for §3's regeneration-margin
and offset rows:

1. **The comparator's differential inputs were floating** — this repo's own
   defect, **fixed**. `gen_comparator.py` resolved `comparator.spice`'s
   `Vpp`/`Vpn` zero-volt input probes into net aliases without `prefer=`, so
   the merged net took the internal name (`preamp_in1` < `vinp`;
   `XCMP.preamp_in1` < `topp`) and the cell labelled a `topp`/`topn` trunk no
   device sat on. `klt lvs` had said so — `pins.layout = 7` against
   `pins.reference = 9`, `VINP`/`VINN` with a null layout counterpart in
   `net_correspondence` — and it had been pinned in `cells.json` as
   `expect_mismatch_count: 2 / {"topology": 2}` rather than read. Both
   findings are now zero and `pin_count` is 9. This also explains
   `xdut.$168`: it was one of the two floating input gates, which is why the
   bias-point solve reported it singular through every fallback.

   Fixing it moved the stuck code from 1023 to **0**. Necessary, not
   sufficient.

2. **The preamp's two 150 kΩ `ppolyf_u_2k` load resistors have no device
   class in the pinned extraction deck** — an upstream capability gap, **not
   fixable here**. Each shorts its own terminals, so `pop`/`pon` collapse onto
   `vdd` and the preamp's differential output is identically zero. New
   testbench `probe_comparator_load_short.py` measures exactly that on the
   **schematic** comparator, with and without the short:
   `v(pop) − v(pon)` = ±0.106 V (`tt_27c_3.30v`) / ±0.166 V
   (`ss_125c_2.97v`) as drawn, **+0.000000 V at every strobe** with the loads
   shorted. `RESULT: CONFIRMED` at both corners. Filed generically upstream as
   [`klayout-tools#595`](https://github.com/2AMLogic/klayout-tools/issues/595).

   A methodology note worth carrying forward: once the preamp differential is
   zero the StrongARM latch is **metastable**, so its `dout` is not evidence
   of anything. The identical shorted circuit freezes at `tt_27c_3.30v` and
   *appears to track the input* at `ss_125c_2.97v`. That is why the probe's
   verdict is taken on the preamp differential, and it is a warning to anyone
   reading a comparator-inclusive result at one corner.

**`ADC_BLOCK` therefore still does not convert**, and §3's
regeneration-margin and offset rows stay **not measured** rather than being
backfilled. What would unblock them: `klayout-tools#595` landing a
flavour-selection knob, or a documented post-extraction remediation that
re-inserts the two load resistors — the second is *not* attempted, because the
extraction has already merged `pop`, `pon` and `vdd` into one net and which
terminal belongs to which is not recoverable from the netlist.

#### Update (issue #118): the resistor-marker gap is closed — `ADC_BLOCK` converts, comparator-inclusive Monte Carlo/regeneration are the next campaign, not this one

Issue #118 drew `SAB` (49/0) + `RES_MK` (110/5) + `Resistor` (62/0) markers
over each load-resistor body
(`layout/adc-top/lib/place.draw_poly_resistor`), so `klt extract`'s gf180mcu
deck now recognises each as a real device instead of an unmodelled Poly2
short — closing defect (2) above **for this repo's purposes**, though not
upstream: the pinned `klt` deck can only select `ppolyf_u_1k` (1000 Ω/sq),
not the schematic's original `ppolyf_u_2k` (2000 Ω/sq) assumption
(`klayout-tools#595` stays open — no flavour-selection knob landed; this is
a resize-around, not a capability fix). `design/comparator/comparator.spice`
and every `sim/*/testbench*/*.spice` `Xrlp`/`Xrln` device line were resized
to `ppolyf_u_1k`, `r_length=150u` (was `ppolyf_u_2k`, `r_length=75u`) to hit
the same 150 kΩ target at the new sheet-rho — see
`layout/adc-top/README.md` "Resistors, and why there are two comparator
cells".

With `pop`/`pon` genuinely LVS-checked, class-and-value-identical devices
rather than a `vdd` short, `verify_extracted_core_conversion.py --top
ADC_BLOCK` now **PASSes** at both `tt_27c_3.30v` and `ss_125c_2.97v` — dated
record
[`records/20260806-adc-block-resistor-markers-pass.md`](../layout/adc-top/parasitics/records/20260806-adc-block-resistor-markers-pass.md),
independently re-run and confirmed bit-identical (same three transitions,
same two corners, same decoded codes) during this issue's own review pass.
`layout/lvs/cells/cells.json`'s `comparator`/`comparator_nores`/`adc_block`
cases are re-baselined to `expect_mismatch_count: 0` with `pop`/`pon`
distinct in the full (non-`_nores`) cases; `klt drc` stays clean on all
three cells at the new geometry.

**What this is NOT**: the same three-transition, one-nominal/one-worst-corner
liveness smoke test §6.4's original text describes, not the #9 offset/
regeneration-margin campaign or the #14 Monte Carlo re-run. §3's
"Offset ≤ 2 LSB" and "Worst-corner comparator regeneration margin" rows are
**still not measured** — not because `ADC_BLOCK` fails to convert any more
(it does, as of this update), but because the actual campaigns (a
comparator-inclusive Monte Carlo population at #14's statistical N, and a
comparator-inclusive re-run of `sim/comparator-regeneration/`'s full PVT
grid through the extracted core) have not been run. That is issue #89
Scope items 1/2's remaining work, not issue #118's — #118's scope was
narrowly the marker/device-recognition gap and the liveness re-check it
unblocks.

**Resize check: the SCHEMATIC-level decks that reference the load resistor
value were all re-run at the resized `ppolyf_u_1k`/150u geometry** (not the
extracted core — that is #89's remaining work above) to confirm the resize
itself, not just the marker/device recognition, leaves previously-ratified
schematic-level results inside their accepted margins. Full PVT grid
(45-point `mos` set, `-40/27/125 °C × ±10 % supply × 5 process corners`)
except `comparator-offset-gof` (nominal-only by design, subset-reason
carried in its own record). Before (`ppolyf_u_2k`, `r_length=75u`) vs after
(`ppolyf_u_1k`, `r_length=150u`), same checks, all PASS both times:

| Deck | Metric | Before | After | Record (before → after) |
|---|---|---|---|---|
| `comparator-offset` | `av_nom` gain, min…max (mean) | 9.51…23.90 dB (16.03) | 9.99…22.48 dB (15.72) | [`20260801-035221-90d7e67`](comparator-offset/records/20260801-035221-90d7e67.md) → [`20260806-233045-56be937`](comparator-offset/records/20260806-233045-56be937.md) |
| `comparator-offset` | `rload_kohm`, min…max (mean) | 109.7…212.6 (157.1) | 115.3…199.1 (154.8) | same pair |
| `comparator-offset-mc` | `sig_vos_mv`, min…max (mean) | 1.17926…1.19477 (1.19053) | 1.17923…1.19478 (1.19094) | [`20260801-035221-90d7e67`](comparator-offset-mc/records/20260801-035221-90d7e67.md) → [`20260806-233042-56be937`](comparator-offset-mc/records/20260806-233042-56be937.md) |
| `comparator-offset-mc` | `avt_back_mv_um`, min…max (mean) | 6.8848…6.97536 (6.95057) | 6.88463…6.97542 (6.95296) | same pair |
| `comparator-offset-mc` | `sig_rpair_uv` (load-mismatch null control) | 0 at every corner | 0 at every corner (unaffected — `mis_r=0` in both models, §5) | same pair |
| `comparator-offset-gof` | `sig_vos_mv`, min…max (mean), `tt_27c` only | 1.18933…1.18935 (1.18934) | 1.1992…1.19937 (1.19926) | [`20260801-093644-c033611`](comparator-offset-gof/records/20260801-093644-c033611.md) → [`20260806-233111-56be937`](comparator-offset-gof/records/20260806-233111-56be937.md) |
| `comparator-preamp-noise` | `vn_in_uv`, min…max (mean) | 76.94…153.22 (109.18) | 76.66…143.70 (105.15) | [`20260801-123440-033b56b`](comparator-preamp-noise/records/20260801-123440-033b56b.md) → [`20260806-233123-56be937`](comparator-preamp-noise/records/20260806-233123-56be937.md) |
| `comparator-regeneration` | `td_half_ns` worst corner (`ss_125c_2.97v`) | 0.863429 ns | 0.858944 ns | [`20260801-050155-109944e`](comparator-regeneration/records/20260801-050155-109944e.md) → [`20260806-233153-56be937`](comparator-regeneration/records/20260806-233153-56be937.md) |
| `comparator-regeneration` | `margin_ns` worst corner (≥ 15.625 ns floor) | 30.3866 ns | 30.3911 ns | same pair |

Every metric moves by well under 5 % and no check's margin changes verdict
— the `ppolyf_u_1k`/150u resize is, as expected for a resistor whose
nominal value (150 kΩ) and W/L aspect ratio are held fixed, electrically
equivalent to the `ppolyf_u_2k`/75u geometry it replaces at the level these
decks measure, with small (≤ 1.3 %) differences attributable to the two
models' distinct PVT/mismatch coefficients rather than to any error in the
resize arithmetic.

#### Update (issue #150): one methodology, not two — PR #120 re-derived and closed as fully covered

Operator ruling on issue #139 (2026-08-14) settled the fork this section's
prior updates trace: `main`'s real-device extraction (#118/#121 — real
`SAB`/`RES_MK`/`Resistor` markers, `klt extract` recognises genuine
`ppolyf_u_1k` load-resistor devices) is the sole accepted methodology.
PR #120's `ADC_BLOCK_NORES`/idealized-resistor-restoration approach — a
core that restored the two preamp load resistors as *ideal* `ppolyf_u_2k`
elements after the extraction had omitted their bodies, explicitly
documented in that PR's own text as "the only non-post-layout elements in
the resulting core" — is **rejected**, and PR #120 is **closed**, not
rebased. This is a written determination of what that leaves outstanding.

**1. What PR #130 did and did not measure post-layout.** PR #130
("Rebuild the three extracted ADC decks…", issue #123) regenerated all four
`gen_extracted_*_tb.py` decks at the `875eac3` pin, `gen_extracted_switch_ron_tb.py`
included — but its own body states that deck "moved only in its `* Source:`
provenance comment, as expected." It minted no new
`sim/device-switch-ron` record, and none is dated after PR #130's merge
(`2026-08-07T06:30:46Z`). That is correct, not a gap: the actual post-layout
re-measurement at this pin had already landed the day before, via PR #119
("Post-layout re-check of #17's AC7", merged `2026-08-06T22:24:21Z`) —
record `20260806-194322-68ad582`, which §4.8's "Update (issue #116)" above
documents in full (570.436 → 647.818 Ω, +13.57 %, `ss_125c_2.97v`). PR #130
ran after that record existed and correctly left it alone.

**2. What PR #120's R_on/rate-closure commits (`be02c85`/`60d469e`) added
beyond what PR #119 already put on `main` — nothing, numerically.** PR #120's
own summary claims the identical delta (570.436 → 647.818 Ω, +13.57 %,
`ss_125c_2.97v`) from the identical deck (`sim/device-switch-ron/`) and the
identical rate-closure composition (`R_WORST_BIT_OHM`/`C_WORST_BIT_F`
post-layout, `T_COMP_REGEN_NS` still schematic, PASS on two of three inputs)
— because its branch's first unique commit (`a0dbcf6`, the comparator
differential-input fix) was already redundant with the independently merged
PR #119/#121, and everything downstream of it re-derived numbers `main`
already had. There is nothing left to re-derive on `ADC_BLOCK`, because
**this measurement was never on `ADC_BLOCK` in the first place** — see (3).
The one thing genuinely missing was citability, not a number: closed by
§4.8's clean-tree re-take, record
[`20260814-191138-f613571`](device-switch-ron/records/20260814-191138-f613571.md),
which reproduces `20260806-194322-68ad582` bit-for-bit across all 45
corners × 25 columns.

**3. `gen_extracted_switch_ron_tb.py` targets the extracted `adc_tgate`
leaf, not `ADC_BLOCK` — this section's methodology fork never applied to
it.** The switch-R_on deck wraps the **CDAC sample/transmission-gate**
cell, a standalone drawn leaf with no comparator content; the
`ADC_BLOCK`/`ADC_BLOCK_NORES` fork this section otherwise tracks is about
the **comparator preamp's two load resistors**, a disjoint set of devices
the switch-R_on deck never touches. PR #120 bundled two unrelated things
into one PR body — a `R_WORST_BIT_OHM` re-measurement (unaffected by, and
predating, the resistor-methodology question) and the `ADC_BLOCK_NORES`
comparator-conversion approach (the part actually rejected) — which read as
one measurement riding on the rejected methodology. It was not: the R_on
number was never idealized, on either PR #119's or PR #120's telling, and
needed no methodology-driven re-derivation, only the citability re-take in
(2).

**4. `sim/timing-budget-closure/` needs no companion re-take, but its
citation did need repairing.** Its most recent record,
[`20260807-082234-eb860c1`](timing-budget-closure/records/20260807-082234-eb860c1.md),
is already clean-tree (`git: ... (clean)`, issue #131's `.save` re-run), so
no re-run is owed. Its post-layout inputs are **not** read live from a
record: `R_WORST_BIT_OHM_EXTRACTED = "648"` / `R_ON_MEASURED_OHM = 647.818`
are literal constants in
`layout/adc-top/parasitics/gen_extracted_timing_budget_tb.py` (the schematic
values they replace, `570` / `2.20672p`, are the literals in
`design/sar-logic/gen_sar_logic.py`). But that module also carries an
explicit `R_ON_SOURCE_RECORD` pointer, which it emits into the generated
deck's header — and it pointed at `20260806-194322-68ad582`, the record this
repo's own provenance field declares "not citable as a clean-tree result".
Leaving it there would have left the rate-closure chain's only post-layout
R_on input tracing to a non-citable source even after §4.8's re-take. So
this issue **repoints** `R_ON_SOURCE_RECORD` at the superseding clean-tree
record `20260814-191138-f613571` (retaining the superseded ID alongside it,
so the chain stays readable) and regenerates the deck. The regenerated deck
differs in **provenance comments only** — 647.818 Ω is bit-identical between
the two records, so no measurement moves and no new
`timing-budget-closure` record is minted. This is the same
comment-only-regeneration precedent PR #130 set when it moved
`gen_extracted_switch_ron_tb.py`'s `* Source:` line without minting a
record. `sim/tests/test_extracted_decks_current.py`'s `--check` guard is
green on the regenerated deck. The frozen
`timing-budget-closure/netlist-snapshots/` copies are untouched, per the
append-only rule.

**5. No `ADC_BLOCK_NORES` reference remains live.** `ADC_BLOCK_NORES` was
defined only on PR #120's own closed branch (`d38a70b`) and never merged;
the current tree contains no occurrence of that identifier outside this
section's own record of it as rejected — no cell name, no build target, no
generator, no live convention anywhere in the design or harness.
(`comparator_nores`/the pre-existing `adc_block` LVS/DRC cases are a
different, unrelated thing — drawn-level companion cells that keep
`pop`/`pon` distinct at the geometry level, present since before PR #120 and
orthogonal to the rejected idealized-restoration approach; they are not
retired by this ruling.)

**6. What stays not measured — unchanged by this ruling, on either
methodology.** The comparator regeneration margin (`T_COMP_REGEN_NS`,
issue #89 Scope item 2) is not measured against the comparator-inclusive
`ADC_BLOCK` core under the accepted real-device methodology, exactly as it
was not measured against PR #120's now-rejected `ADC_BLOCK_NORES` core
either (PR #120's own "What is NOT done" section: "Scope item 2 … is NOT
re-measured"). Closing PR #120 therefore does not remove any coverage that
existed — it removes a duplicate PR carrying a rejected methodology for a
gap that stays exactly as open as it already was.
#### Update (issue #116): the comparator-inclusive regeneration campaign is run — AC2 closes

`ADC_BLOCK` converting (issue #118, above) unblocked the actual campaign
this section's "still open" state named as remaining work: a
comparator-inclusive re-run of `sim/comparator-regeneration/`'s full PVT
grid through the extracted core. It is now run.

**Method, and why it differs from a straight re-run of the schematic
deck.** The schematic deck instantiates three parallel, independently
supplied `comparator` subckt copies and forces `vinp`/`vinn` directly, so it
can integrate one comparator's own supply current cleanly. `ADC_BLOCK` bakes
the comparator INSIDE a ~1350-device extracted core with no isolable
per-comparator supply node, so tripling it would triple simulation cost for
no metrological benefit. `layout/adc-top/parasitics/
measure_extracted_regeneration.py` instead drives ONE `Xdut ADC_BLOCK`
instance sequentially through all three overdrive steps, forcing
`topp`/`topn` (the comparator's own input pins, per `gen_extracted_core_tb
.py`'s wiring table) directly, loaded by the REAL extracted CDAC array
sitting on those nodes with every array control net held at a fixed
DR-0014 one-hot decode. `e_dec_fj`/`i_static_ua` (dynamic energy, static
current) are NOT re-measured — that per-comparator supply integral is
exactly what this topology cannot cleanly provide, and neither is a scope
item this issue's AC2 asks for.

**A new, measured, deterministic finding along the way.** The first working
run (nominal corner) found a naïve 0 V-referenced 0.5 LSB decision
**stuck**. Direct measurement (a slow `topp`−`topn` ramp with `cmpclk`
free-running) explains why: the extracted core carries a real systematic
input-referred offset — **−0.597…−4.357 mV across the 45-point grid**,
bigger than the half-LSB overdrive itself at every corner. No statistical
mismatch is enabled anywhere in this deck (same nominal geometry as the
schematic), so this can only be a deterministic asymmetry the drawn
layout's real interconnect between the `topp`/`topn` block-boundary pins and
the preamp's actual gates introduces — something no schematic-level deck can
show by construction. Per CLAUDE.md, the honest response is to measure it
and refer #9's ladder to it (`vos_v ± dv_...`), not to pretend the extracted
core is still offset-free. The offset stays well inside the ratified
`Offset ≤ 2 LSB` (12.89 mV) 3σ **mismatch** bound at every corner, but is
NOT a substitute for that row — it is one deterministic value per corner,
not a statistical population, and §3's "Offset ≤ 2 LSB" row is updated to
note this new, related-but-distinct finding rather than claiming it closed.

**Result** — full 45-point PVT grid (`mos` set, same grid the schematic
baseline used), record
[`sim/comparator-regeneration/records/20260814-215626-f613571`](comparator-regeneration/records/20260814-215626-f613571.md):

| measurement | schematic worst (`ss_125c_2.97v`) | extracted worst (`ss_125c_2.97v`) | delta | verdict |
|---|---|---|---|---|
| `td_half_ns` | 0.858944 ns | **1.25638 ns** | +0.397394 ns (+46.3 %) | PASS (≤ 15.625 ns ceiling), 45/45 corners |
| `margin_ns` | 30.3911 ns | **29.9936 ns** | −0.3975 ns (−1.3 %) | PASS (≥ 15.625 ns floor, 1.9× margin), 45/45 corners |
| `tau_ps` | 42.3729 ps | **55.8977 ps** | +13.5248 ps (+31.9 %) | PASS ([1, 20000] ps), 45/45 corners |
| `resolve_decades` | 311.489 | **233.034** | −78.455 (−25.2 %) | PASS (≥ 3), 45/45 corners |

Every direction matches what real layout parasitic loading on the
comparator's own input nodes predicts: slower, not faster (the extracted
core's CDAC array now sits electrically on `topp`/`topn`, where the
schematic's isolated comparator had no load at all), and the worst PVT
corner does not move. Per-axis sensitivity witnesses (process/temperature
≥ 5 % floors) clear with 3.8×–5.5× margin; the grid-wide 20 % floor on
`td_half_ns` clears at 82.3 %. **`td_tiny_ns`** (the 0.1 mV metastability
probe) does **not** resolve at any of the 45 corners — the offset-ramp
measurement's own ~1.25 mV resolution (one `cmpclk` cycle's worth of ramp
movement) is roughly an order of magnitude coarser than the 100 µV probe it
would need to land next to. This is a stated measurement-resolution limit
(see the record's own section on it), not silently dropped, and it does not
gate the PASS verdicts above — the schematic manifest's own check
description already frames it as "a metastability probe, not an accuracy
requirement".

`T_COMP_REGEN_NS` — the input this measurement feeds — moves **0.863 → 1.257 ns**
(rounded up from 1.25638 ns) in `layout/adc-top/parasitics/
gen_extracted_timing_budget_tb.py`, closing §6.3's rate-closure row fully
post-layout (see that section's own update).

**§3's "Worst-corner comparator regeneration margin" row is now `measured
— PASS`.** Issue #116 Scope item 2 (AC2) is satisfied; §3's "Offset ≤ 2 LSB"
row stays `not measured` for the ratified 3σ-mismatch claim specifically
(the comparator-inclusive Monte Carlo population issue #89 Scope item 2 also
named remains unrun — a separate, statistical campaign this issue does not
attempt).

---

## 7. Escalations: results reported rather than absorbed

Two results in this document are not clean "measured, PASS, small delta" rows.
Both are stated here in full, in their own subsection, because CLAUDE.md's
no-relaxation rule cuts both ways: a spec line is never adjusted to make a
result pass, and a result is never smoothed to make a spec line look
untroubled.

### 7.1 Baseline caveat: the SFDR row was already failing before layout

Issue #89 Scope item 6, restated here so the ENOB/FFT row is not misread when
it lands: **the schematic-level SFDR baseline is already a FAIL** — 61.33 dB
against the ≥ 62 dB target, a 0.67 dB miss, at one corner of nine
(`ss_125c_2.97v`), recorded in `spec/testbench-suite-memo.md` §11.2 for the
DR-0014 topology. The other eight corners span 63.62–69.98 dB.

A continued extracted-netlist SFDR failure at that corner is **expected
pre-existing baseline behaviour** (schematic FAIL → extracted FAIL), not a new
layout-induced regression, and must be reported as such. What *would* be a new
finding is the extracted result failing at corners the schematic passed, or the
margin at `ss_125c_2.97v` widening materially. Read §11.2 before writing that
row.

**Update (§4.6, this increment) — measured, not merely expected.** The
extracted-netlist run confirms the "no new corner fails" half exactly: all
nine shared corners keep their schematic verdict, `ss_125c_2.97v` remains
the sole failing corner, and the other eight span 64.48–71.67 dB (all clear
of the 62 dB target with margin comparable to or wider than the schematic
grid's 63.62–69.98 dB). Per CLAUDE.md ("report FAIL and escalate rather than
silently adjusting"), the second half is flagged rather than absorbed: the
**margin at `ss_125c_2.97v` does widen** — from a 0.67 dB miss (schematic,
61.33 dB) to a **1.89 dB miss** (extracted, 60.11 dB), a −1.22 dB
worst-corner delta. This is *not* attributed to a new mechanism — §4.6
shows THD moves the same direction by a comparable amount at the same
corner, consistent with §11.2's existing diagnosis (acquisition
nonlinearity, unrelated to the CDAC's own R/C this extraction adds) rather
than a distinct post-layout effect — but the widened margin is reported
here explicitly rather than folded into "expected baseline behaviour"
without qualification, per Scope item 5's no-relaxation rule. A reader
deciding whether this needs its own remediation (rather than remaining the
pre-existing, already-tracked failure §11.2 describes) should start from
the §4.6 per-corner table, not this section's summary.

**Update (§4.10, the in-path re-take) — the picture reverses, and issue #151
reconciles it.** The paragraph above was measured on the superseded
lumped-stub extraction, whose 156 parasitic resistors on `adc_top` carried
no device current at all (§1.4). §4.10's in-path re-take
([`20260807-054805-e8cd2b8`](adc-enob-fft/records/20260807-054805-e8cd2b8.md),
independently replicated by
[`20260807-052432-eac5d11`](adc-enob-fft/records/20260807-052432-eac5d11.md))
moves worst SFDR from 60.11 dB to **64.38 dB** — now *better* than the
schematic baseline's 61.33 dB at the corner the schematic fails, the
opposite direction from the lumped-stub result this subsection first
reported. Issue #151 tested, rather than assumed, why: `spec/testbench-suite-memo.md`
§11.2 rules out baseline staleness (a fresh schematic-level re-run at
`ss_125c_2.97v` against current sources,
[`20260814-193205-f613571`](adc-enob-fft/records/20260814-193205-f613571.md),
reproduces 61.3317 dB with **all 64 decoded codes bit-identical** to the
baseline capture — only 6 of the 8 `decerr_c*_lsb` decode-**error** metrics
and `vref_droop_mv` move at all, by ≤ 0.021 LSB — and it does so *across* a
source change, not merely a re-run: the two records' frozen netlist
snapshots differ in `design/comparator/comparator.spice`, whose preamp load
resistors moved from `ppolyf_u_2k r_length=75u` to `ppolyf_u_1k
r_length=150u` at issue #118, a different PDK device model with its own
tempco at a 125 °C corner, on top of an ngspice-46 → ngspice-47 bump) and a
deck/comparability gap (the schematic and
extracted FFT decks' shared preamble — stimulus, backoff, input drive
network — is byte-for-byte identical), and finds instead that the extracted
grid's own worst SFDR corner **relocates** from `ss_125c_2.97v` (schematic)
to `ff_125c_3.63v` (extracted, 64.38 dB; `ss_125c_2.97v` itself measures
64.93 dB extracted) — a real, corner-dependent effect of the in-path CDAC
parasitics on the acquisition's own sampling-bow nonlinearity, the same
"moves rather than uniformly shifts" pattern §7.2/§7.3 below document for
the power row's comparator excursion. **Disposition**: the schematic-level
FAIL at `ss_125c_2.97v` stands, unedited, as accurate for the pre-layout
netlist, but the two independent in-path-extracted records are read as
governing the ratified row for the design as laid out — same precedent
every other row in `README.md`'s Status line already follows once a
post-layout capture exists. **The SFDR row now passes**, worst 64.38 dB
against the ≥ 62 dB target. Full candidate-by-candidate test detail and the
per-corner delta table: `spec/testbench-suite-memo.md` §11.2.

### 7.2 The power row PASSES, and one corner's comparator term doubles — diagnosed and bounded

`Power @ 1 MS/s < 1 mW` passes on the extracted core with 3.7× of margin
(§4.7.2), so nothing here is a spec failure and nothing is adjusted. It stays
escalated in its own subsection anyway, because a **2.06× move in a measured
block at one PVT corner** is a finding whether or not it fails a bound, and
because the block that moved is one the wrapper keeps *schematic-level* — the
last place a post-layout effect was expected.

**The shape of it.** At 26 of the 27 corners, `p_cmp_f100_uw` moves by −1.33 …
+0.98 % and `p_total_f100_uw` by +2.17 … +4.26 %. At `tt_125c_3.63v` alone,
`p_cmp_f100_uw` moves +105.7 % (109.4 → 225.0 µW) and drags `p_total_f100_uw`
+80.8 % (147.9 → 267.3 µW). That single cell is the whole of the ratified
row's +45.8 % worst-vs-worst delta.

**What is established** (§4.7.3, and record
[`20260806-power-cmp-anomaly`](../layout/adc-top/parasitics/records/20260806-power-cmp-anomaly.md)):
it is not a measurement-window artefact (both conversions in the window carry
it, the one before does not), not the static preamp bias (a fixed 10 µA
source in both arms; the excess is dynamic, peak draw +39 %), and it is
**attributable to the extracted core** — the schematic arm reaches the same
top code 1023 at the same corner and draws a normal −29.9 µA there, while the
extracted arm walks into 1023 one conversion earlier and then stays there
drawing 2×.

**Issue #107 closes the two items that record left open.** Record
[`20260806-power-cmp-metastability`](../layout/adc-top/parasitics/records/20260806-power-cmp-metastability.md)
extends the same probe with per-bit-cycle comparator-output transition
counting and top-plate differential/common-mode voltage at each decision
instant, plus a fine full-scale-level sweep, and finds:

1. **The device-level mechanism, named.** `cmpclk`
   (`design/adc-top/gen_adc_top.py::_preamble()`) strobes the StrongARM latch
   every bit cycle, including the three DR-0014 acquisition cycles where the
   top-plate V_cm switch holds `v(se_topp)`/`v(se_topn)` low-impedance, AND
   bit cycle 3 — the first cycle after that switch opens, releasing the top
   plate to a floating, high-impedance node. On both cores, the residual left
   over from the previous conversion decays to the comparator's own
   microvolt-scale noise/offset floor during acquisition and triggers a
   spurious, unused "decision" — but on the extracted core, at
   `tt_125c_3.63v` full scale specifically, that crossing lands on bit cycle
   3 (undamped) instead of bit cycle 2 (damped, where the schematic core's
   own crossing lands at the same corner and conversions). It is that
   one-cycle-later, undamped-node metastable regeneration that costs the
   extra +39–40 % peak current — not a bias shift (already ruled out) and not
   a common-mode shift (top-plate common mode agrees between the two cores to
   within 0.03 mV at every matching bit cycle, ruling out that half of the
   predecessor record's second candidate). *Not fully closed*: why the
   extracted core's crossing lands exactly one cycle later than the
   schematic's — the leading candidate is the extracted core's real top-plate
   parasitic capacitance slowing the acquisition-window RC decay just enough
   at this one corner/level, but no net-by-net capacitance comparison was run
   to confirm it quantitatively; see the record's §3 for the exact follow-up
   instrument.
2. **How much of the grid sits near the same boundary, bounded.** A fine
   sweep of the full-scale input level at the tipping corner and its two
   nearest PVT-grid neighbors (`tt_125c_3.30v`, its supply neighbor;
   `tt_27c_3.63v`, its temperature neighbor) finds the excursion **only** at
   `tt_125c_3.63v`, **only** at input level exactly 1.0000 — one part in 10⁴
   below full scale (under 1 LSB) already clears it — and **neither tested
   neighbor shows any trace of it at any level up to and including exactly
   1.0000**. This is a single-corner, single-exact-code coincidence, not
   "1/27 of operating space" sitting near the same edge, though it remains a
   2-of-26-corner sample rather than an exhaustive one.
3. **Whether it survives a comparator-inclusive extraction — still open,
   unchanged.** The comparator is schematic-level in this wrapper; the
   `ADC_BLOCK` extraction would put it inside the extracted boundary, where
   its own layout parasitics could make this better or worse. That path is
   itself blocked today — §6.4's `ADC_BLOCK` smoke test FAILs reproducibly —
   so this item is NOT closed by issue #107, which was scoped to items 1 and
   2 on `ADC_TOP` only, per its own "Related" framing.

The correct reading of the power row is now: **PASS at 267.3 µW worst, with a
diagnosed, bounded, layout-attributable metastable-regeneration excursion
confined to one exact corner and one exact input level — not a wide-region
post-layout power effect.** A design change (gating `cmpclk` to the ten real
decide phases, so the comparator never strobes an undamped, undecided node at
all) is a real candidate but touches `_preamble()`, which every committed
`sim/` record was taken against; it is named as a follow-up in the record
rather than made here, and no spec line is adjusted either way.

### 7.3 On the in-path extraction the §7.2 excursion **moves** — resolved: process-axis floor re-derived, harness verdict now PASS (issue #133 / DR-0018)

The §4.10 re-take (record
[`20260807-060526-03e80b9`](adc-power/records/20260807-060526-03e80b9.md))
carries the ratified row with more margin than before — worst `p_total`
across all five input levels and all 27 corners is **220.9 µW** against
< 1 mW, down from 267.3 µW. The harness verdict on the record is
nevertheless **FAIL**, and nothing was relaxed to change that:

    CHECK FAIL p_cmp_f050_uw min_spread_pct_by_axis on the process axis=3
               (got 2.50595)

That check is a **sensitivity witness** — "did the corner runner demonstrably
move this axis?" — not a spec bound, and it reads the *weakest* slice of the
grid. It trips for a reason worth reading rather than waiving:

| | lumped stubs (`20260806-083932-faebccc`) | in-path (`20260807-060526-03e80b9`) |
|---|---|---|
| outlier corner | `tt_125c_3.63v` | `ss_27c_3.63v` |
| outlier input level | f100 (full scale) | f050 (mid scale) |
| `p_cmp` there | 225.0 µW (median 93.1) | 161.8 µW (median 98.5) |
| `p_total` there | 267.3 µW | 220.9 µW |
| weakest process slice of `p_cmp_f050_uw` | 4.25 % | 2.51 % |

**The excursion did not persist and did not vanish — it relocated**, to a
different corner *and* a different input level, and shrank from 2.42× the
median to 1.64×. That is new evidence for issue #107's open item 2 ("how much
of the grid sits near the same boundary"): a fixed property of one PVT corner
would not move when only the parasitic topology changes, whereas a marginal
final-trial decision boundary — #107's item 1 hypothesis — is exactly what
would.

**Correction (issue #133): the failing witness is a different, unrelated
slice, not the outlier's own "sibling."** The paragraph above originally read
the witness failure as the outlier "inflating the slice it sits in, leaving
the sibling process slice … below the … floor" — that description is wrong
and is corrected here rather than silently edited (`sim/README.md` — this
document is evidence, edits are tracked). `sim/harness/report.py`'s per-axis
spread is computed independently within each `(temperature, supply)` group,
so the outlier's own group (`27 °C`, `3.63 V`, spread 39.6 %) cannot
mathematically depress a different group. Reworking the record's per-axis
table into all nine `(temperature, supply)` groups for `p_cmp_f050_uw` shows
the witness actually fails at `125 °C`/`2.97 V` (`tt`=85.2226, `ss`=85.0998,
`ff`=87.2514 µW, spread 2.506 %) — the opposite corner of the grid from the
`27 °C`/`3.63 V` outlier group, and not elevated itself. Every other group
(including the seven that touch neither extreme) spreads 3.6–21.3 %; only
these two groups sit apart from that band, one high (the #107 outlier) and
one low (this witness), and they are independent findings, not one
mechanism. See [DR-0018](../spec/decision-records/DR-0018-adc-power-process-axis-floor.md)
Context for the full nine-group table.

**Resolution (issue #133).** [DR-0018](../spec/decision-records/DR-0018-adc-power-process-axis-floor.md)
re-derives the `p_cmp_f050_uw` process-axis floor for this DUT rather than
diagnosing the #107 mechanism (#107 was still open with no landed mechanism
finding at the time this issue was scoped — its record-backed diagnostic
work stays there, not absorbed here). The `125 °C`/`2.97 V` slice's 2.506 %
spread is a real, physically-explained value — the comparator's preamp bias
enters a low-overdrive regime at reduced `V_DD` and elevated temperature
where thermal-voltage-scaled behaviour common to all three process corners
dominates the (smaller, at low overdrive) `V_th` spread between them — not a
sign the runner failed to sweep process (the same measurement, same axis,
moves by up to 39.6 % elsewhere in the same grid). DR-0018 lowers the floor
from 3.0 % to 2.0 %, ~20 % of margin below the observed minimum rather than
at it, and record
[`20260807-084749-290d003`](adc-power/records/20260807-084749-290d003.md)
re-runs the unmodified deck under the revised floor, on a clean tree at the
DR-0018 commit — every row reproduces bit-for-bit against
`20260807-060526-03e80b9` except the harness verdict, which is now
**PASS** (`p_cmp_f050_uw`'s process-axis witness reads
`min_spread_pct_by_axis[process]=2`, cleared by the same 2.506 % minimum).

Correct reading of the power row on the in-path extraction: **PASS at
220.9 µW worst, with the §7.2 comparator excursion still present but
relocated and smaller, and the harness verdict now PASS under the
DR-0018-revised process-axis floor.** The comparator-current mechanism
itself remains reported to #107, not absorbed here.

> **Amended by §4.11.1.** A second, independently-run campaign on the same
> extraction re-measured this grid and found **no excursion at all** — including
> at `ss_27c_3.63v`, where it reads `p_cmp_f050_uw` = 113.9 µW against this
> record's 161.8 µW — while agreeing with this record to ≥ 4 significant
> figures at the other 26 corners and at every other input level of this one.
> Two consequences for the paragraph above: the excursion is **not** a corner
> property *or* a topology property but a per-run outcome at a marginal point,
> which strengthens #107's item 1; and the sensitivity witness is **not** a
> direct consequence of the outlier, since it trips (at 2.37 %) in a record that
> has no outlier to inflate any slice. Both records stand — see §4.11.

---

## 8. Provenance of this document

| | |
|---|---|
| Extraction | `layout/adc-top/parasitics/reports/20260805-102856-1118e9a/adc_top.para.spice` |
| Remediation | `layout/adc-top/parasitics/remediate_extracted.py` (PMOS body → `vdd`; input rails → pins; MiM untouched) |
| Deck generator | `layout/adc-top/parasitics/gen_extracted_inl_dnl_tb.py` |
| Manifest | `sim/adc-inl-dnl/testbench/tb.json`, **unmodified** |
| Records diffed | `20260802-141402-1224e11` (schematic) → `20260805-203322-3b6d7b7` (extracted) |
| Delta tool | `sim/tools/schematic_vs_extracted.py` |
| §4.4 control | `layout/adc-top/parasitics/probe_gain_err_settling.py` → record `20260805-224500-2c21be4` (3 PVT points × 2 cores) |
| §5 Monte Carlo | `layout/adc-top/parasitics/mc_extracted_core.py` → record `layout/adc-top/parasitics/records/20260805-extracted-core-mc.md` (N = 120 + 12-draw null control) |
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| ngspice | 46 |
| Grid | 27 points, 27 completed, 0 non-convergent; 2436 s wall at `-j 1` |
| §4.5 `cdac`-set records | `20260805-220405-bff6eaf` (schematic, PR #100) → `20260806-052258-8d36824` (extracted, this increment) |
| §4.5 grid | 63 points, 63 completed, 0 non-convergent; 1100 s wall at `-j 6 --ngspice-threads 1` (throughput note: capping ngspice's own OpenMP thread count to 1 per point lets `-j` scale near-linearly on this host instead of oversubscribing — see `sim/harness/cli.py --ngspice-threads` and `sim/harness/README.md`) |
| §4.6 deck generator | `layout/adc-top/parasitics/gen_extracted_enob_fft_tb.py` |
| §4.6 records | `20260802-141402-1224e11` (schematic) → `20260806-081350-862d054` (extracted, clean-tree re-run; supersedes the dirty-tree `20260806-060520-72a230a`) |
| §4.6 analysis tool | `sim/adc-enob-fft/testbench/analyze_fft.py --sigma-extra-lsb 0.0488` (noise term per `spec/testbench-suite-memo.md` §4.3, unchanged from the schematic composition) |
| §4.6 grid | 9 points (`tt`/`ss`/`ff` × 125 °C × 3 supplies, the schematic baseline's own two-stage-strategy subset), 9 completed, 0 non-convergent; 550 s wall at `-j 6 --ngspice-threads 1` |
| §4.7 deck generator | `layout/adc-top/parasitics/gen_extracted_power_tb.py` (four-way supply split, `vddd`+`vddt` merged — §4.7.1) |
| §4.7 records | `20260802-141402-1224e11` (schematic) → `20260806-083932-faebccc` (extracted, this increment) |
| §4.7 grid | 27 points (`tt`/`ss`/`ff` × −40/27/125 °C × 3 supplies, the schematic baseline's own grid), 27 completed, 0 non-convergent; 2413 s wall at `-j 6 --ngspice-threads 1` (~455 s/point single-threaded) |
| §4.7.1 merged-rail comparison | `sim/tools/schematic_vs_extracted.py --sum p_core_f<lvl>_uw=p_cdac_f<lvl>_uw+p_trk_f<lvl>_uw` — the same sum applied to both records, never one side only |
| §7.2 outlier diagnostic | `layout/adc-top/parasitics/probe_power_cmp_anomaly.py` → record `layout/adc-top/parasitics/records/20260806-power-cmp-anomaly.md` (1 corner × 2 cores, per-conversion instrumentation) |
| §1.4 parasitic-topology audit | `layout/adc-top/parasitics/audit_parasitic_topology.py` → record `layout/adc-top/parasitics/records/20260806-parasitic-topology.md` (332 parasitic nets across 3 extractions, 0 in-path) |
| §4.8 leaf extraction | `layout/adc-top/parasitics/reports/20260806-140411-968d138/adc_tgate.para.spice` (record `20260806-140411-968d138`), leaf-remediated by `remediate_extracted.py --leaf` (PMOS body → a `vnw` pin, biased at the instance) |
| §4.8 deck generator | `layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py` (schematic deck spliced; only the T-gate branch replaced) + its `--in-path-control` positive control |
| §4.8 records | `20260806-140624-4f71285` (schematic, clean-tree re-take superseding the dirty-tree `20260731-191216-5f5288b`) → `20260806-140815-7fa57ad` (extracted, this increment). The extracted record deliberately leaves `Supersedes` empty: it does not replace the device characterization, which stays the live citable baseline for the settling budget (`spec/cdac-sizing-memo.md` §5.3 cites its 570 Ω) — a post-layout record marked as superseding it would read as "the characterization was replaced", which is not what happened |
| §4.8 grid | 45 points (`mos` set × −40/27/125 °C × 3 supplies, the manifest's own grid), 45/45 completed on both sides, 0 non-convergent; ~2 s wall each (`op` analysis) |
| §4.9 deck generator | `layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py` (Groups A+C only; Groups B/D have no extracted equivalent on this core — Group D is measured separately in §4.8) |
| §4.9 manifest | `sim/dr0014-sampling/testbench-extracted/tb.json` — a second, explicitly-scoped manifest (not a copy of the schematic one's `measure`/`checks`), sitting alongside `sim/dr0014-sampling/testbench/` |
| §4.9 records | `20260802-141402-1224e11` (schematic) → `20260806-141727-5ba48d5` (extracted, this increment, lumped-stub topology) → `20260807-091733-434dc37` (in-path re-take, issue #131, 27/27 PASS, 2884 s, clean tree at `434dc37`) |
| §4.9 grid | 27 points (`tt`/`ss`/`ff` × −40/27/125 °C × 3 supplies, the schematic baseline's own grid), 27 completed, 0 non-convergent; 1298 s wall at `-j 8 --ngspice-threads 1` |
| §4.10 extraction | `layout/adc-top/parasitics/reports/20260806-230838-56be937/adc_top.para.spice` — the `875eac3`-pin star-split **in-path** extraction (`klayout-tools#593`), 2936 parasitic R + 156 parasitic C on `adc_top`, superseding the 156-R lumped-stub extraction §4.5–§4.7 used. Basis decision recorded in `layout/adc-top/parasitics/README.md`, "Decision record — issue #123" |
| §4.10 records | `20260806-052258-8d36824` → `20260807-051433-7845f17` (INL/DNL, 63/63 PASS, 1931 s) · `20260806-081350-862d054` → `20260807-054805-e8cd2b8` (ENOB/FFT, 9/9 PASS, 970 s) · `20260806-083932-faebccc` → `20260807-060526-03e80b9` (power, spec PASS / harness FAIL on one witness — §7.3, 636 s), further superseded by `20260807-084749-290d003` (issue #133, harness PASS under the DR-0018-revised floor, 622 s). All at `-j 6 --ngspice-threads 1`, from a clean tree, at the commit carrying the deck each measures |
| §4.10 grids | Unchanged from the records they supersede — 63 pt `cdac` set, 9 pt two-stage subset, 27 pt `tt`/`ss`/`ff`. No coverage narrowed because the DUT changed |
| §4.10 runnability | The three generators emit `.save <manifest's own vectors>` via `gen_extracted_core_tb.saved_vectors_lines()`; without it ngspice will not allocate the ~4256-extra-node waveform store and every point dies before measuring. Retention only — bit-identical measurements, checked on `tt_27c_3.30v` |
| §4.10 CI guard | `sim/tests/test_extracted_decks_current.py` — all four `gen_extracted_*_tb.py --check` on the PDK-free path (extended to all six by issue #131) |
| §4.10 mos-grid re-take (issue #132) records | `20260805-203322-3b6d7b7` → [`20260807-081223-6bd9d80`](adc-inl-dnl/records/20260807-081223-6bd9d80.md) (INL/DNL, 27/27 PASS, 852.7 s) |
| §4.10 mos-grid re-take grid | 27 points (`tt`/`ss`/`ff` × −40/27/125 °C × 3 supplies — the record it supersedes' own grid, and §3's INL/DNL basis grid), 27 completed, 0 non-convergent; `-j 8 --ngspice-threads 1` (matched to this host's 8 cores rather than the `-j 12` first suggested, to avoid the oversubscription implicated in a prior contended-host attempt) |
| §4.10 mos-grid re-take delta tool | `sim/tools/schematic_vs_extracted.py adc-inl-dnl --schematic 20260802-141402-1224e11 --extracted 20260807-081223-6bd9d80` (schematic vs in-path) and `--schematic 20260805-203322-3b6d7b7 --extracted 20260807-081223-6bd9d80` (lumped-stub vs in-path) |
| §4.11 records | The second, concurrently-run campaign on the **same** extraction report: `20260807-041111-ccf1f9b` (INL/DNL, 63/63 PASS, 4343 s) · `20260807-052432-eac5d11` (ENOB/FFT, 9/9 PASS, 3777 s) · `20260807-062903-1e3f48c` (power, spec PASS at 185.0 µW / harness FAIL on the same witness at 2.37 %, 2245 s). All three at `-j 9…12 --ngspice-threads 1` with the per-point timeout raised to 3600–7200 s, from a clean tree, on an 18-core / 51 GB host |
| §4.11 deck variant | Run **without** §4.10's `.save` (the host had the memory to retain every node), so each record's committed `sim/<slug>/netlist-snapshots/<record-id>.spice` differs from the deck now in `testbench/` by exactly that line. The snapshot is the re-runnable artefact, per `sim/README.md`'s directory convention |
| §4.11 comparison | `sim/tools/schematic_vs_extracted.py`'s record parser over both campaigns' per-corner tables: 675 ENOB cells bit-identical, 5229 INL/DNL cells to ≥ 4 s.f., 837 power cells to ≥ 4 s.f. at 26 of 27 corners — the exception is §4.11.1 |
| §7.2 mechanism + bound (issue #107) | `layout/adc-top/parasitics/probe_power_cmp_anomaly.py` (extended: `--waveform` per-bit-cycle transition/diff/CM instrumentation, `--levels` fine full-scale sweep) → record `layout/adc-top/parasitics/records/20260806-power-cmp-metastability.md` (mechanism: 1 corner × 2 cores; bound: 3 corners × extracted core × 8-point fine level sweep) |
| §4.8/§6.4 clean-tree re-take (issue #150) | `20260806-194322-68ad582` (dirty-tree, superseded) → [`20260814-191138-f613571`](device-switch-ron/records/20260814-191138-f613571.md) (clean tree at `f613571`, `feature/issue-150`), 45/45 corners bit-identical across a *different* host/toolchain (Linux ngspice-46 → macOS ngspice-47, same open_pdks pin and manifest sha256), same supply-axis liveness FAIL at 9.71502 %; `gen_extracted_timing_budget_tb.py`'s `R_ON_SOURCE_RECORD` repointed to the clean record and its deck regenerated (provenance comments only, no measurement moves); PR #120 closed as fully covered by this record plus the pre-existing PR #119 composition (§6.4 update) |

Every `sim/` record cited here carries its own `Netlist provenance` field, and
no extracted record replaces a schematic one — they append alongside each
other, per `sim/README.md`, "Extracted vs schematic semantics".

## 9. `klt pex` — item 7's own named tool, tried directly (issue #173)

Everything above is this repo's **own** hand-built extracted-core
re-simulation methodology (`gen_extracted_*_tb.py`'s `_wire_pin()` wiring
layer), predating `klayout-tools`' own single-command
schematic-vs-extracted tool, `klt pex` (epic #709). Issue #173 installed
`klt pex` once it shipped and ran it for real against `comparator.gds` —
[`sim/comparator-pex/`](comparator-pex/) — specifically to check whether it
could now generate this section's evidence directly, superseding the
hand-built path above.

**It cannot, today, for this repo's netlists.** `klt pex` re-simulates the
schematic and extracted sides from one unmodified testbench, rewriting only
its `.include` line — which requires both sides' top-level `.subckt` to
share one pin list. `klt extract`'s output here never satisfies that: it
promotes body/tap nets (`vsubs`) and, per block, internal analog nodes a
hand-written schematic keeps private (`comparator`'s `pon`/`pop`) — the
exact gap `_wire_pin()` above exists to bridge with a per-block wiring
layer instead of a bare `.include` swap. `klt pex` reports `status: "error"`
on the resulting `ngspice` pin-count mismatch; full diagnostic in
[`sim/comparator-pex/records/`](comparator-pex/records/). Filed generically
as [`klayout-tools#1030`](https://github.com/2AMLogic/klayout-tools/issues/1030).

**This does not change anything above.** Every measured row in §§4–7 stands
on the `_wire_pin()`-based methodology, unaffected by `klt pex`'s own
limitation; §9 answers a narrower, distinct question ("can `klt pex` itself
close item 7 today") with its own citation, not a re-grade of any spec-line
result. Item 7 of the T1 checklist is graded FAIL from this section — a
concrete, tool-verified blocker, not "N/A by construction" (the pre-#173
state, when `klt pex` did not exist upstream at all).

Issue #173 also found that adopting `klt pex`'s upstream commit as this
repo's *production* `klt` pin (`layout/toolchain.json`) is a separate,
larger change than the pin bump itself — `klt extract`'s device-parameter
and warning-list shape moved between the two commits, staling every
committed `.spice` snapshot and both drc/lvs manifests' `expect` blocks
(`klt lvs` itself still reports `mismatches=0` throughout, so this is
bookkeeping drift, not a connectivity regression). Deferred to
[gf180-sar-adc#178](https://github.com/2AMLogic/gf180-sar-adc/issues/178);
`sim/comparator-pex/`'s run above therefore used a separate, investigative
`klt` pin, documented in `layout/adc-top/parasitics/run_pex_comparator.py`.
