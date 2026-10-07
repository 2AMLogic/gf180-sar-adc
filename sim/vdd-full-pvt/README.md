# `sim/vdd-full-pvt/` — the ratified rows, re-run against a real `V_DD` pin network

**This directory holds no testbench and mints no records of its own.** It is
the *driver* and the *findings* for issue #393: re-running the decks that own
ratified spec rows against a real external `V_DD` drive network at
[DR-0036](../../spec/decision-records/DR-0036-vdd-decoupling-budget.md)'s
derived budget (`C_dec ≥ 40 nF` at the pin, `Z_vdd ≤ 3 Ω` in the switching
band), over each deck's **own governing PVT grid**, and reading the result
against the **ratified rows**. It is the `V_DD` counterpart of
[`sim/vcm-full-pvt/`](../vcm-full-pvt/README.md) (issue #358, DR-0026) and
follows its method exactly; the records it mints land in each target deck's
own `sim/<deck>/records/` directory.

**DR-0036 is *proposed — requires operator sign-off*.** This campaign grades
the converter against that proposed budget; it does not ratify it, and it
changes no bound, target or manifest check.

## Why this exists

Every ADC-level deck in `sim/` sources its three supply islands from ideal,
zero-impedance DC sources:

```spice
vddt vddt 0 dc {vdd_val}     * track / top-plate switch island
vddd vddd 0 dc {vdd_val}     * CDAC bottom-plate drivers
vddc vddc 0 dc {vdd_val}     * comparator
```

DR-0036 derived a drive requirement for the `V_DD` pin from a measured rail
current (`sim/adc-rail-current/records/20260923-002945-1cefe83.md`: a
34.383980 mA peak against a 39.5421 µA average at `ff_-40c_3.63v`), but no
deck had ever run the converter *behind* such a source — so what the budget
buys, and what missing it costs the ratified rows, was unmeasured
(`sim/characterization-summary.md`'s `Supply` row said so and pointed here).

## The modelling decision: one `V_DD` pin, not three independent islands

This had to be settled before the variant generator was written, because the
wrong choice would still produce self-consistent, plausible-looking PASS
results that nothing downstream would catch.

**Chosen: ONE shared pin network feeding every island.**
[`sim/vdd-drive-impedance/gen_vdd_variant.py`](../vdd-drive-impedance/gen_vdd_variant.py)
replaces the island sources with:

```spice
vddsup  vdd_ext 0       dc {vdd_val}   * ideal supply behind the pin
rvddpin vdd_ext vdd_pin 3              * R ‖ L: the source impedance,
lvddpin vdd_ext vdd_pin 477.46n        *   corner at 1 MHz
cvddpin vdd_pin 0       40n            * the external decoupling at the pin
vddt    vddt    vdd_pin dc 0           * } 0 V ammeters, one per island:
vddd    vddd    vdd_pin dc 0           * } every i(vddX) keeps its name
vddc    vddc    vdd_pin dc 0           * } AND its sign
```

Why:

1. **DR-0036 budgets one pin, off the summed current.** Its step 1 bounds the
   per-conversion charge from the window average of
   `i(vddc)+i(vddd)+i(vddt)`, and its budget is "external decoupling ≥ 40 nF
   at **the** `V_DD` pin". The ratified table carries a single `V_DD`.
2. **The drawn layout has one supply rail.** The extracted `.SUBCKT ADC_TOP`
   exposes a single `vdd` pin
   (`sim/adc-power/testbench/tb_adc_power_extracted.spice`'s header: *"The
   drawn layout has ONE supply rail"*); the three islands are a testbench
   **instrumentation** split — one ammeter per block — not three package pins.
3. **Three independent networks would silently grade against 3× the budget.**
   Patching each island with its own 40 nF / 3 Ω network (the literal
   generalisation of `gen_vcm_variant.py`'s one-line patch) models three
   off-chip pins: 120 nF of total decoupling and three 3 Ω sources in
   parallel (1 Ω effective). It would also **hide the one real coupling a
   shared pin has** — the CDAC drivers' switching sag (`vddd`, 99.75 % of the
   peak) landing on the comparator's supply (`vddc`). The shared network is
   both the faithful choice and the conservative one.

The ammeters are what make the shared node safe for the existing manifests:
each island keeps its instance name, so `sim/adc-power/`'s per-block
`i(vddc)`/`i(vddd)`/`i(vddt)` measurements still resolve, and each keeps its
`+` terminal on the island node exactly as the ideal line it replaces did, so
the sign every `p_*` expression derives on is preserved (issue #395's failure
mode on the `V_cm` generator, designed out here up front;
`sim/tests/test_vdd_variant.py::AmmeterTests` checks it from connectivity).

### The `R ‖ L` corner sits at the 1 MHz conversion rate, not the 16 MHz bit clock

DR-0002 (`V_REF`) and DR-0026 (`V_CM`) apply their settling convention to the
62.5 ns **bit** cycle, so their networks corner at 16 MHz. DR-0036 step 5
applies the same convention to the 1 µs **conversion** period
(`τ_max = 1 µs / ln 2¹¹`, `Z_vdd,max = τ_max / C_dec`), because the `V_DD`
transient happens once per conversion and `C_dec` must be recharged between
conversions. The band where `Z_vdd ≤ 3 Ω` must hold therefore starts at
1 MHz, and the corner is placed there (`L = R / 2π·1 MHz = 477.46 nH`).

That is also the **pessimistic** placement. Above the corner the network is
`R`; below it, the smaller `ωL`. At the recharge frequency
`1/(2π·Z·C_dec) ≈ 1.33 MHz` this network presents ≈ 2.4 Ω — at the budget —
where a 16 MHz corner would present ≈ 0.25 Ω and grade the converter against a
source ~10× stiffer than DR-0036 allows. It also damps the `L`–`C_dec`
resonance (`Q = R·√(C/L)` ≈ 0.87 vs ≈ 3.5). `L` shorts at DC, so the DC
operating point is identical to the ideal arm and the paired delta is the
network's dynamic behaviour alone.

### What the network does NOT model — the result is a statement about the external budget only

- **No package inductance.** This repo has no package model (DR-0036 open
  question 2); DR-0036 step 7 already shows an off-die path cannot supply the
  sub-ns edge through any realistic package.
- **No on-die rail resistance** between the pin and each island (the
  `layout/power/` flow's domain, DR-0036 step 8). Every island sits directly
  on the pin node.
- **No on-die decoupling.** DR-0036 clause 3 requires it; the block as drawn
  has none, so this models the block as drawn.

All three would make the real supply *worse* than this network. A clean
result here therefore says the **external** ≥ 40 nF / ≤ 3 Ω budget is not
what limits the ratified rows — not that the block as integrated is immune to
its supply.

## The decks, and which ratified row each one answers for

The issue enumerated seven testbenches. Reporting against the **ratified
rows** requires one more: `Gain error, systematic` is cited from the
**extracted** `sim/dr0014-sampling/` record, and that deck lives in its own
`testbench-extracted/` directory (with its own manifest, and only two islands
— the extracted core has one `vdd` pin and its generator wires no `vddt`).

| tag | Deck | Ratified row | Grid | Points | Governing record the ideal arm must reproduce |
|---|---|---|---|---|---|
| `dr0014-sampling-extracted` | `sim/dr0014-sampling/testbench-extracted/` | **Gain error, systematic** (≤ 0.5 LSB) | manifest default `tt`/`ss`/`ff` × 3 T × 3 V | 27 | [`20260923-104443-904af96`](../dr0014-sampling/records/20260923-104443-904af96.md) |
| `dr0014-sampling` | `sim/dr0014-sampling/testbench/` (schematic) | Gain error, systematic | manifest default | 27 | — |
| `adc-inl-dnl-extracted` | `tb_adc_inl_dnl_extracted.spice` | **INL / DNL** (< 1 LSB) | `--corners tt ss ff` × 3 T × 3 V | 27 | [`20260923-095400-904af96`](../adc-inl-dnl/records/20260923-095400-904af96.md) |
| `adc-inl-dnl` | `tb_adc_inl_dnl.spice` (schematic) | INL / DNL | manifest default `cdac` 7 × 3 T × 3 V | 63 | — |
| `adc-power-extracted` | `tb_adc_power_extracted.spice` | **Power @ 1 MS/s** (< 1 mW) | `--corners tt ss ff` × 3 T × 3 V | 27 | [`20260923-102440-904af96`](../adc-power/records/20260923-102440-904af96.md) |
| `adc-power` | `tb_adc_power.spice` (schematic) | Power @ 1 MS/s | `--corners tt ss ff` (load-bearing, #266) | 27 | — |
| `adc-enob-fft-extracted` | `tb_adc_enob_fft_extracted.spice` | **ENOB / SFDR** | `--corners tt ss ff --temps 125` (two-stage, §5) | 9 | [`20260923-111149-904af96`](../adc-enob-fft/records/20260923-111149-904af96.md) |
| `adc-enob-fft` | `tb_adc_enob_fft.spice` (schematic) | ENOB / SFDR | same | 9 | — |

Every grid is the one that deck's own governing record uses; none is narrowed
here. `run_full_pvt.sh`'s preflight refuses to start an extracted row whose
committed deck no longer hashes to the sha256 its governing record pins, and
it reads the ideal arm's `--netlist-provenance` **verbatim** out of that
record, so "the control reproduces the citation" is a comparison of the same
bytes.

`Offset error` is not reachable, for the reason `sim/vcm-full-pvt/` gives: its
row is cited from comparator-only decks with no array, no switching event and
a single ideal comparator supply. The array-level offset term
(`bp_inj_mis_lsb`) lives in `sim/dr0014-sampling/`, which this campaign runs.

## Paired arms — the control is re-taken, not read off an older record

Every deck that was run was run **twice at the same commit (`800bf53`), same
grid, same host**:

- **`ideal`** — the committed deck, unmodified. For a schematic row that is
  the manifest's own default deck; for an extracted row it is the same
  extracted deck passed with `--netlist`, byte-identical to its governing
  record's.
- **`vddnet`** — the same deck with its island sources replaced by the one
  shared pin network above, via `gen_vdd_variant.py --deck`.

### Which pairs were run, and which were deferred

**Run: the four extracted (governing) pairs — eight arms, 27 + 27 + 27 + 9 =
90 grid points per side, all PASS.** **Deferred: the four schematic pairs** (`dr0014-sampling`,
`adc-inl-dnl`, `adc-power`, `adc-enob-fft`). They are wired into
`run_full_pvt.sh` under the identical recipe and need no new code.

Why those four and not the others (the margin-triage precedent of
[`sim/vcm-full-pvt/README.md`](../vcm-full-pvt/README.md), applied):

1. **Every ratified row this campaign can touch is cited from an extracted
   record** (the table above names each one), so the extracted pair is the one
   whose verdict a ratified row rests on. A schematic pair adds a second
   opinion on a row whose citation it is not.
2. **The extracted pairs came back with the V_DD network moving every bounded
   quantity by ≥ 33× less than its remaining margin** (table below), so
   nothing in the extracted result points at the schematic deck as a place the
   network would bite harder. That is an argument for deferral, not a
   measurement of the schematic decks.
3. **Cost.** On this shared host (load average 25–65 on 18 cores while the
   campaign ran) one extracted arm took 2.1–2.9 h wall at 4 concurrent
   `ngspice`; the schematic `adc-inl-dnl` pair alone is 63 points per arm.
   Compute went to the arms that decide a row.

This is a deferral, **not** a claim that the schematic decks are unaffected:
no schematic arm was measured.

`Offset error` and the comparator-only rows are not reachable, for the reason
given above.

## Reproducing this campaign

```bash
./sim/vdd-full-pvt/run_full_pvt.sh                           # every deck, both arms
./sim/vdd-full-pvt/run_full_pvt.sh adc-inl-dnl-extracted     # one deck, both arms
ARMS=vddnet ./sim/vdd-full-pvt/run_full_pvt.sh adc-power     # one deck, one arm
PREFLIGHT_ONLY=1 ./sim/vdd-full-pvt/run_full_pvt.sh          # hash/provenance/generator checks only
```

**Run each arm from its own clean clone.** `sim/run_corners.py` stamps a
dirty tree into the record, and every arm writes into the tracked evidence
tree. The committed records were taken with one `git clone --shared -b
feature/issue-393` per arm, all at `800bf53`, each arm run as
`JOBS=4 ARMS=<arm> ./sim/vdd-full-pvt/run_full_pvt.sh <tag>`, four arms
concurrently (16 `ngspice` processes, the sweep's CPU budget), and the minted
`records/<id>.md`, `corners/<id>/` and `netlist-snapshots/<id>.spice` copied
out afterwards. **The ENOB/SFDR pair needs `TIMEOUT=14400`**: its first
attempt at the script's default 3600 s per-point timeout lost 8 of 9 points
per arm to `ngspice timed out after 3600s` on this contended host, so it was
re-run (`TIMEOUT=14400 JOBS=9`, one clean clone per arm) and only that second
pair is committed. The first attempt's two partial records were not kept: 1 of
9 points each, they measured the host, not the converter (the one point each
that did complete, `ff_125c_3.63v`, agreed with the committed pair).

Then difference each pair (`--manifest` only for the deck whose manifest is
not `sim/<slug>/testbench/tb.json`):

```bash
python3 sim/vdd-full-pvt/compare_vdd.py --experiment adc-inl-dnl \
    --ideal sim/adc-inl-dnl/records/20261007-044826-800bf53.md \
    --vddnet sim/adc-inl-dnl/records/20261007-044830-800bf53.md
python3 sim/vdd-full-pvt/compare_vdd.py --experiment dr0014-sampling \
    --manifest sim/dr0014-sampling/testbench-extracted/tb.json \
    --ideal sim/dr0014-sampling/records/20261007-071907-800bf53.md \
    --vddnet sim/dr0014-sampling/records/20261007-072143-800bf53.md
python3 sim/vdd-full-pvt/compare_vdd.py --experiment adc-power \
    --ideal sim/adc-power/records/20261007-072338-800bf53.md \
    --vddnet sim/adc-power/records/20261007-072514-800bf53.md
python3 sim/vdd-full-pvt/compare_vdd.py --experiment adc-enob-fft \
    --ideal sim/adc-enob-fft/records/20261007-072654-800bf53.md \
    --vddnet sim/adc-enob-fft/records/20261007-072721-800bf53.md
```

`compare_vdd.py` is `sim/vcm-full-pvt/compare_vcm.py`'s arithmetic, imported
rather than copied (that script's `compare()` gained label and manifest
keyword arguments whose defaults reproduce its own output byte-for-byte —
checked against both committed #358 pairs). It creates no numbers beyond the
subtraction. The ENOB/SFDR rows are not `meas` scalars, so they are compared
with that deck's own post-processor over both arms' raw logs:

```bash
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/<id>/ --markdown --sigma-extra-lsb 0.0488
```

### Why this ran on the dispatch host and not the batch fleet

`klt sim --backend batch` takes a `klt sim` *request* and composes its own
per-corner decks; this repo's evidence is minted by `sim/run_corners.py` from
decks it composes itself, and the ideal arms exist precisely to reproduce
records that harness minted. A request-based re-expression would mint a
different artifact. That tool gap is filed generically as
[klayout-tools#2804](https://github.com/2AMLogic/klayout-tools/issues/2804)
(a corrected re-filing of #2464).

## Provenance

| item | value |
|---|---|
| commit under test | `800bf53` (`feature/issue-393`; every arm ran from a clean clone) |
| network | `Z_vdd = 3 Ω`, `C_dec = 40 nF`, `R ‖ L` corner 1 MHz (`L = 477.46 nH`), one shared pin, three `0 V` island ammeters |
| toolchain | `ngspice-46`; PDK `gf180mcuD @ c6d73a35f524070e85faff4a6a9eef49553ebc2b` (MIM `m4m5`) |
| decks | the four extracted decks named in the table above; each sha256-checked against its governing record by the preflight |
| governing records the ideal arms were checked against | `20260923-095400-904af96` (INL/DNL), `20260923-104443-904af96` (gain error), `20260923-102440-904af96` (power), `20260923-111149-904af96` (ENOB/SFDR) |

## Findings

### Result (extracted, governing netlists; 90 points per side, every point PASS in both arms)

| ratified row (bound) | records (ideal → network) | ideal arm worst | network arm worst | largest single paired move | verdict |
|---|---|---|---|---|---|
| **INL / DNL** (< 1 LSB) | [`…044826`](../adc-inl-dnl/records/20261007-044826-800bf53.md) → [`…044830`](../adc-inl-dnl/records/20261007-044830-800bf53.md) | INL 0.517545, DNL 0.681240 LSB (`ss_125c_2.97v`) | INL 0.517513, DNL 0.681199 LSB (same corner) | 0.0018 LSB across all 27 INL/DNL measures (`inl_t256_lsb`, `tt_27c_3.63v`) | **inside, margin unchanged**; every bound-carrying measure moves by under 1/400 of its margin (tightest 407×, `dnl_t255_t256_lsb`) |
| **Gain error, systematic** (≤ 0.5 LSB) | [`…071907`](../dr0014-sampling/records/20261007-071907-800bf53.md) → [`…072143`](../dr0014-sampling/records/20261007-072143-800bf53.md) | `tp_inj_signal_dep_lsb` 0.0010063 LSB (`ff_-40c_3.63v`) | 0.000834 LSB (same corner; the network arm's worst is `-0.00115` on `tp_inj_mis_l4_lsb`) | 0.000766 LSB (`tp_inj_mis_l0_lsb`) | **inside, ~500× margin on this row's own term**; the five bounded deck checks move by ≤ 0.0068 LSB, ≥ 101× inside their margins |
| **Power @ 1 MS/s** (< 1 mW) | [`…072338`](../adc-power/records/20261007-072338-800bf53.md) → [`…072514`](../adc-power/records/20261007-072514-800bf53.md) | `p_total` 218.627 µW (`ff_125c_3.63v`, f050 window) | 218.554 µW (same) | 2.555 µW (`p_total_f050_uw`, `ff_-40c_3.30v`), 1.2 % of the window | **inside, 4.57× margin against 1 mW, 2.29× against the 500 µW stretch, unchanged**; `p_cmp_f050_uw` (20…200 µW window) 115.459 → 115.388 µW |
| **ENOB / SFDR** (> 9.0 / ≥ 62 dB) | [`…072654`](../adc-enob-fft/records/20261007-072654-800bf53.md) → [`…072721`](../adc-enob-fft/records/20261007-072721-800bf53.md) | ENOB 8.860 bits (`tt_125c_3.63v`), SFDR 60.41 dB (`ff_125c_2.97v`) | **identical** at every one of 9 points, to the 0.01 dB / 0.001 bit printed precision | all 64 output codes identical at all 9 points; three diagnostic residue rows (`decerr_c008/c032/c040_lsb`) move 0.001 LSB | **no change**; rows already FAIL in both arms (ENOB below 9.0 at 2 of 9 points, SFDR below 62 dB at 4 of 9) and stay exactly as they were |

`compare_vdd.py` reported, for all four pairs, **no measurement leaving its
manifest bound under the network that does not already leave it under the
control arm**. No ratified row changed status, no bound or budget was
touched, and nothing here threatens a ratified bound.

### Do the ideal control arms reproduce the cited records?

The criterion was *same PASS/FAIL, same headline figures*:

| row | cited record | control arm vs cited, over every measurement |
|---|---|---|
| INL / DNL | `20260923-095400-904af96` | worst \|Δ\| 2e-5 on any of 83 rows; same worst corners; **reproduces** |
| ENOB / SFDR | `20260923-111149-904af96` | all 75 rows Δ = 0 at every point; **reproduces exactly** |
| Power | `20260923-102440-904af96` | worst \|Δ\| 0.235 µW (`p_total_f075_uw`, 0.12 % of the window); worst figure 218.628 vs 218.627 µW; **reproduces** to the cited precision |
| Gain error | `20260923-104443-904af96` | headline term `tp_inj_signal_dep_lsb` 0.000981002 → 0.0010063 LSB (+2.6 %, 2.5e-5 LSB absolute); worst `samp_span_lsb` move 0.01 LSB in 1831; **same PASS, same worst corner, not bit-identical** |

The two non-exact controls are the reason the pairs are same-commit pairs: the
cited records were taken at `904af96` on a dirty tree (`compare_vdd.py` prints
that), these at `800bf53` clean, on a different host load. Both differences
are two to four orders of magnitude below the effect size the network is
graded on, and the paired difference — which carries the network and nothing
else — is unaffected by them. I have not isolated what the residual
difference is (`ngspice` thread/scheduling versus a harness change between the
two commits); it is stated, not explained.

### What this does and does not establish

- **It establishes** that, on the governing extracted netlists, over each
  deck's own PVT grid, a single external pin network at the **edge** of
  DR-0036's budget (`40 nF`, `3 Ω`, `R ‖ L` corner at the conversion rate) does
  not move any ratified row measurably, and does not flip any verdict. The
  external budget is **not what limits** `INL / DNL`, `Gain error`, `Power` or
  `ENOB / SFDR`.
- **It does not establish the 0.5 LSB denominator in DR-0036 step 3 can be
  relaxed**, and DR-0036 is not changed. These decks measure the converter's
  *DC-to-conversion-rate* response to the source; the ≥ 40 nF figure is sized
  from a per-conversion charge that is **bounded** from a window average, not
  integrated (#386). The network above has no package inductance, no on-die
  rail resistance between pin and island, and no on-die decoupling (see
  *What the network does NOT model*), all of which make the real rail worse.
  A measured near-zero sensitivity at the pin is a necessary condition for a
  relaxation, not a sufficient one.
- **It does not integrate the switching event.** DR-0036's `ΔQ_event` is
  still bounded from a window average (#386), and this campaign adds no
  per-pin droop measurement for `V_DD`: it grades the ratified rows against the
  network, not the network's own instantaneous sag.
- **Schematic arms were not run** (above).

### Does anything need to change in `spec/`?

No. No ratified row is outside its bound under the network, and nothing here
relaxes a row or DR-0036's `≥ 40 nF` / `≤ 3 Ω`. DR-0036's open question 3
is updated with this evidence by that record itself (its `≥ 40 nF` / `≤ 3 Ω`
values and the 0.5 LSB denominator are unchanged).

### Flow friction

None that is new. The batch-dispatch gap this driver works around is the
already-filed klayout-tools#2804; the per-point `TIMEOUT` default needing a
raise for the ENOB deck on a contended host is a property of this repo's
driver, noted above.
