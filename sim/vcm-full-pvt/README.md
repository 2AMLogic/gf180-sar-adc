# `sim/vcm-full-pvt/` — the ratified rows, re-run against a real `V_cm` network

**This directory holds no testbench and mints no records of its own.** It is
the *driver* and the *findings* for DR-0026's named follow-up (issue #358):
re-running the decks that own ratified spec rows against a real external
`V_cm` drive network at [DR-0026](../../spec/decision-records/DR-0026-vcm-drive-source.md)'s
derived budget, over each deck's **own governing PVT grid**, and reading the
result against the **ratified rows** rather than against a deck-internal
metric. The records it mints land in the target decks' own
`sim/<deck>/records/` directories, where that deck's evidence has always
lived.

## Why this exists, and how it differs from `sim/vcm-drive-impedance/`

Every ADC-level testbench in this repo sources `V_cm` from an ideal,
zero-impedance DC source (`vcms vcmn 0 dc {vcm}`).
[`sim/vcm-drive-impedance/`](../vcm-drive-impedance/README.md) (issue #260)
asked whether that assumption is *conservative*, and found it is not: a real
network at DR-0026's derived budget moved `sim/adc-inl-dnl/`'s own
`gain_err_lsb` by ≈ 0.2 LSB (≈ 10 %). That sweep was deliberately narrow, and
said so in every record it wrote — **three** limitations it left open, which
are exactly this campaign's scope:

| `sim/vcm-drive-impedance/` (issue #260) | This campaign (issue #358) |
|---|---|
| One deck (`adc-inl-dnl`) | Every deck that owns a ratified row and carries an ideal `V_cm` source |
| Nominal PVT only — `cdac` 7 corners at **27 °C / 3.30 V** | Each deck's **own governing grid** (temperature and supply axes included) |
| Deck-internal metrics (`gain_err_lsb`, `inl_t*_lsb`), which that deck's own check descriptions state are **not** the ratified `Gain error, systematic` row | The **ratified rows**: `INL / DNL`, `Gain error, systematic`, `Power @ 1 MS/s`, `ENOB`/`SFDR`, and `Offset error` |
| Z_vcm swept (0 / 220 Ω / 1100 Ω), one PVT point | Z_vcm **held** at DR-0026's budget (220 Ω / 40 nF), full grid |

## The decks, and which ratified row each one answers for

The issue that opened this work named three decks (`sim/adc-inl-dnl/`,
`sim/adc-enob-fft/`, `sim/adc-power/`) but asked for a verdict on three
ratified **rows** — and those two sets do not line up. `Gain error,
systematic` is not owned by `adc-inl-dnl` at all: `sim/characterization-summary.md`
cites `sim/dr0014-sampling/` for it, and that deck **also** sources `V_cm`
from an ideal supply. Reporting against the ratified row therefore requires
running it, so the deck set is not the issue's three:

| Deck | Ratified row it owns | Grid | Points | Run here |
|---|---|---|---|---|
| `sim/dr0014-sampling/` | **Gain error, systematic** (≤ 0.5 LSB) | manifest default: `tt`/`ss`/`ff` × 3 T × 3 V | 27 | **yes** |
| `sim/adc-inl-dnl/` | **INL / DNL** (< 1 LSB) | manifest default: `cdac` 7-corner × 3 T × 3 V | 63 | **yes** |
| `sim/adc-inl-dnl/` (**extracted, governing**) | **INL / DNL** (< 1 LSB), the *governing* netlist | `--corners tt ss ff` × 3 T × 3 V | 27 | **yes** |
| `sim/adc-power/` (schematic) | **Power @ 1 MS/s** (< 1 mW) | `--corners tt ss ff` × 3 T × 3 V | 27 | **yes** |
| `sim/adc-power/` (**extracted, governing**) | **Power @ 1 MS/s**, the *governing* netlist | `--corners tt ss ff` × 3 T × 3 V | 27 | wired, deferred |
| `sim/adc-enob-fft/` | **ENOB / SFDR** | `--corners tt ss ff --temps 125` (two-stage strategy) | 9 | wired, deferred |

Four pairs — eight arms — were run. The two marked *wired, deferred* are
selectable from `run_full_pvt.sh` with no new code; the findings section below
records why the campaign's compute went elsewhere, with the margin arithmetic
that decided it.

### Schematic is not where these rows are cited from — so one extracted deck is run too

Every ratified row in `sim/characterization-summary.md` that this campaign can
touch is cited from an **extracted** record, not a schematic one: `INL / DNL`
from [`20260817-214114-076d545`](../adc-inl-dnl/records/20260817-214114-076d545.md),
`Power @ 1 MS/s` from [`20260817-211252-076d545`](../adc-power/records/20260817-211252-076d545.md),
`Gain error, systematic` from [`20260817-204729-076d545`](../dr0014-sampling/records/20260817-204729-076d545.md),
`ENOB`/`SFDR` from [`20260825-061750-d00911a`](../adc-enob-fft/records/20260825-061750-d00911a.md).
`sim/characterize.sh` labels each of those runs `GOVERNING` in as many words.
A verdict taken only on the schematic decks would therefore be a verdict on
netlists the rows are not cited from.

Running **every** deck twice over (schematic pair *and* extracted pair) is
about 17 CPU-hours on this host, which this campaign does not have. It spends
what it has where a verdict can actually change, which is a question of
**margin**, not of principle:

| Ratified row | Governing (extracted) worst | Bound | Headroom |
|---|---|---|---|
| **INL / DNL** | DNL **0.7278 LSB** (`dnl_t767_t768_lsb`, `ss_125c_2.97v`) | 1 LSB | **0.272 LSB — 1.37×** |
| Gain error, systematic | 0.20 % ≈ 2 LSB span-referred, reported flat across PVT | ≤ 0.5 LSB | tracked separately (memo §12 item 8) |
| Power @ 1 MS/s | 231.8 µW | 1000 µW | 4.31× |
| ENOB / SFDR | already **FAIL** (DR-0025) | — | a delta cannot flip a row that already fails |

`INL / DNL` on the extracted netlist is the **only** ratified row in this
suite whose verdict a `V_cm`-network-sized perturbation could plausibly flip —
1.37× of headroom, against 4.31× for power and an already-failing dynamic
row — so `adc-inl-dnl-extracted` is the extracted pair this campaign runs.
`run_full_pvt.sh` carries the `adc-power-extracted` pair too, ready to run
under the identical recipe, and this README's findings section records that it
was **not run here and why**, rather than leaving it unnamed.

The driver supports this because an extracted deck's *ideal* arm is the one
case where the control is not simply "the manifest's default deck": both arms
must be extracted for the paired difference to isolate the `V_cm` network, so
the ideal arm passes `--netlist` explicitly (the per-deck `base_prov` field).

Each grid is the one that deck's **own** governing record already uses — none
is invented here, and none is narrowed for this campaign's convenience:

- `adc-power`'s `--corners tt ss ff` is **load-bearing**, not a narrowing: the
  manifest's own `cdac` set is capacitor-only and pins the MOS `.lib` section
  to `typical`, so a MOS-bias-dominated measurement like `p_cmp_*` reads a
  near-zero process-axis spread under it (issue #266). `sim/characterize.sh`
  carries the same override for the same reason.
- `adc-enob-fft`'s 9-point grid is the two-stage corner strategy
  (`spec/testbench-suite-memo.md` §5) its own governing records and
  `sim/characterize.sh` already use — reproduced so the paired ideal-source
  control is point-for-point comparable with the existing ENOB/SFDR citation.
  It is declared to the harness via `--subset-reason`, as the convention
  requires.

**`Offset error` is not reachable from this campaign, and that is a
structural fact rather than a gap in it.** `sim/characterization-summary.md`
cites `sim/comparator-offset-mc/` and `sim/comparator-regeneration/` for that
row — comparator-only decks which contain no `V_cm` node and no
`vcms vcmn 0 dc {vcm}` line at all, so there is nothing for a `V_cm` drive
network to change in them. The array-level offset term that *is* sensitive to
`V_cm` is the top-plate `V_cm` switch's charge injection, and that lives in
`sim/dr0014-sampling/`'s `tp_inj_*` / `bp_inj_mis_lsb` measurements, which
this campaign does run.

## Paired arms — the control is re-taken, not read off an older record

Every deck is run **twice at the same commit, same grid, same host**:

- **`ideal`** — no `--netlist` override at all: the manifest's own default
  deck, with the ideal zero-impedance `V_cm` source. This is the control.
- **`vcmnet`** — the same deck with that one line replaced by DR-0026's budget
  network (`Z_vcm = 220 Ω`, `C_dec = 40 nF`, R‖L corner at the 16 MHz bit
  clock) via `sim/vcm-drive-impedance/gen_vcm_variant.py --deck`.

The control is **re-taken** rather than read off the existing ideal-source
records because those were minted at earlier commits: a delta against them
would carry every intervening design change as well as the `V_cm` network.
Re-taking it makes the paired difference attributable to the network and to
nothing else — at the cost of doubling the campaign, which is the right
trade for a question whose whole content is "did this one change move a
ratified row?"

## Reproducing this campaign

```bash
./sim/vcm-full-pvt/run_full_pvt.sh                  # every deck, both arms
./sim/vcm-full-pvt/run_full_pvt.sh adc-power        # one deck, both arms
ARMS=vcmnet ./sim/vcm-full-pvt/run_full_pvt.sh adc-power   # one deck, one arm
```

**Run each arm from a clean checkout.** `sim/run_corners.py` samples
`git status --porcelain` *before* each run and stamps a dirty tree into the
record as "not citable as a clean-tree result". The harness writes its own
record and per-corner logs into the tracked evidence tree, so a second
back-to-back arm would see the first arm's output as dirt. The committed
records were taken by running each arm in a scratch clone of the commit
under test, harvesting the minted record + `corners/<id>/` +
`netlist-snapshots/<id>.spice` out after each arm, and restoring the scratch
tree to a clean checkout before the next one:

```bash
git clone --no-hardlinks --shared . /tmp/vcm-run -b <branch>
cd /tmp/vcm-run
for arm in ideal vcmnet; do
  git checkout -- . && git clean -fd        # back to a clean tree
  ARMS=$arm ./sim/vcm-full-pvt/run_full_pvt.sh <deck>
  # copy the new sim/<deck>/{records,corners,netlist-snapshots} entries out
done
```

Then difference each pair:

```bash
python3 sim/vcm-full-pvt/compare_vcm.py \
    --experiment adc-inl-dnl \
    --ideal  sim/adc-inl-dnl/records/<ideal-id>.md \
    --vcmnet sim/adc-inl-dnl/records/<vcmnet-id>.md
```

`compare_vcm.py` creates no numbers of its own beyond the subtraction: every
value it prints is read out of the two records' own per-point measurement
tables, and every bound it compares against is read out of that deck's own
`testbench/tb.json` `checks` block, so a bound that moves in the manifest
moves here too.

For `adc-enob-fft` the spectral rows are not scalars an ngspice `meas` can
produce, so the ENOB/SFDR comparison is made with that deck's own
post-processor over **both** arms' raw logs, exactly as
`spec/testbench-suite-memo.md` §11 does for the single-arm case:

```bash
python3 sim/adc-enob-fft/testbench/analyze_fft.py \
    sim/adc-enob-fft/corners/<id>/ --markdown --sigma-extra-lsb 0.0488
```

<!-- FINDINGS -->

## Findings (2026-09-23, issue #358)

### The answer, first

**No ratified row moves outside its bound under a real `V_cm` network meeting
DR-0026's budget, at full PVT, on either the schematic or the governing
extracted netlist.** Every arm of this campaign scored a clean sweep against
its own manifest's checks — eight arms, two of 63 points and six of 27, all
PASS on every point, all clean-tree. `compare_vcm.py` reports no bound left in
the `V_cm` arm that was
not already left in the ideal control arm, for any deck.

That is the question DR-0026's named follow-up asked, and the answer is no.

### The answer that matters more

**The ideal-source assumption is not merely "not conservative" — under
DR-0026's budget the governing `INL / DNL` row is left with 0.2126 LSB of
worst-case margin against its ratified `< 1 LSB` bound.**

| | worst `INL` | worst `DNL` | **minimum headroom** | points worse than the **0.5 LSB stretch** |
|---|---|---|---|---|
| extracted, ideal `V_cm` (= the committed governing citation at this vintage) | 0.5283 LSB | 0.7276 LSB | 0.2724 LSB | **1 of 27** |
| extracted, `V_cm` network at DR-0026's budget | 0.6651 LSB | 0.7874 LSB | **0.2126 LSB** | **20 of 27** |

#### The number an operator should read: minimum headroom, 0.2126 LSB

The ratified bound is `< 1 LSB` and both arms clear it everywhere. The
**tightest remaining margin** anywhere in the `V_cm`-network arm — the smallest
`1 − |value|` over all 18 probed `inl_*`/`dnl_*` metrics × 27 corners — is

```
headroom = 0.2126 LSB   dnl_t767_t768_lsb @ ss_125c_2.97v   (value +0.787422)
```

That is the worst-case margin DR-0026's sign-off actually rests on, and it is
**36 % tighter** than the 0.3326 LSB this document quoted in its first draft.
Two things are worth separating there:

- The network costs that particular point comparatively little: the same
  transition and corner reads `+0.727556` in the ideal control arm, so the
  headroom goes `0.2724 → 0.2126 LSB` — a **0.0599 LSB** move, 22 % of the
  margin it had. It is the *tightest* point because the extracted deck is
  already tight there without any `V_cm` network at all, not because the
  network hits it hardest.
- The point the network hits hardest is a different one (below), and it is
  *not* the point with the least margin left. Worst absolute perturbation and
  worst remaining margin are two different quantities and this document now
  states both rather than letting the first stand in for the second.

#### The largest paired move: 0.6163 LSB

The largest paired move is **0.6163 LSB** (`dnl_t1_t2_lsb` at `ss_27c_2.97v`;
`inl_t2_lsb` moves 0.6161 LSB at the same point). At *that* corner and
transition the headroom goes `0.9497 → 0.3334 LSB`, i.e. the budget DR-0026
derives consumes **65 % of the margin that transition had** and leaves
**0.54× the move** behind it. A second perturbation that size at that point
would breach the bound.

(For the avoidance of the corner-mixing this document previously committed:
`0.3326 LSB` is `dnl_t1_t2_lsb` at `ss_-40c_2.97v`, and `0.9472 LSB` is the
ideal arm's worst `dnl_t1_t2_lsb` over the whole grid, also at
`ss_-40c_2.97v`. All three figures in the paragraph above are taken at the
single corner `ss_27c_2.97v`.)

Both numbers are recomputed directly from the per-corner tables in
[`20260923-095803-836a876`](../adc-inl-dnl/records/20260923-095803-836a876.md)
and
[`20260923-100947-836a876`](../adc-inl-dnl/records/20260923-100947-836a876.md).

The `< 0.5 LSB` stretch target is not a ratified bound and its verdict does not
flip a row — but going from **1 of 27** points outside it to **20 of 27** is
the clearest single statement of what a real `V_cm` pin costs this converter.

### Where the existing evidence understated it, and why

`sim/vcm-drive-impedance/` (issue #260) published ≈ 0.2 LSB at the budget, and
`sim/characterization-summary.md`'s `V_CM` row and DR-0026 both quote that
figure. **This campaign reproduces that sweep exactly at its own point** — at
`tt_27c_3.30v`, on the same deck:

| quantity | that sweep published | this campaign, same point |
|---|---|---|
| `gain_err_lsb` | −2.005 → −2.205 | −2.00532 → −2.20527 |
| `inl_t256_lsb` | −0.0134 → −0.2805 | −0.01342 → −0.28053 |

So the two campaigns agree where they overlap, to every digit either one
publishes. The understatement is **not** a PVT-coverage effect, and this is
worth being precise about because the issue that opened this work assumed it
was. At that *same* `tt_27c_3.30v` point, `inl_t2_lsb` moves **0.4215 LSB** —
1.6× the largest number the exploratory sweep reported. The sweep quoted the
mid-scale carries (`inl_t256`, `inl_t768`) and the gain term; the transitions
that actually move most are the **bottom-of-range** ones (`inl_t2`,
`dnl_t1_t2`), which it did not quote.

The PVT axes matter much less than that: across the whole 63-point schematic
grid the worst paired move ranges only 0.3765 → 0.4669 LSB (a 24 % spread),
and the nominal 27 °C / 3.30 V point sits at 0.4644 LSB, near the top of it.
**The process axis is where the remaining factor lives**: the extracted deck's
`tt`/`ss`/`ff` MOS corners reach 0.6163 LSB, while the schematic deck's
capacitor-family `cdac` set — which pins the MOS section to `typical`, exactly
the effect issue #266 documents for the power deck — tops out at 0.4669 LSB.

So the honest correction to the record is: *the exploratory sweep's
≈ 0.2 LSB understated the effect by ~3×, because of the transitions it quoted
and the capacitor-only process axis it swept, not because it held temperature
and supply fixed.*

### Per deck

| deck | grid | verdict | the number |
|---|---|---|---|
| `sim/adc-inl-dnl/` **extracted** (governing at the pre-#381 vintage this ran on — see "Which extraction this ran on" below) | 27 pt | **no ratified row outside bound** | **minimum headroom 0.2724 → 0.2126 LSB** (`dnl_t767_t768_lsb`, `ss_125c_2.97v`); worst `DNL` 0.7276 → 0.7874 LSB; largest single move 0.6163 LSB (`dnl_t1_t2_lsb`, `ss_27c_2.97v`), leaving 0.3334 LSB there |
| `sim/adc-inl-dnl/` schematic | 63 pt | no ratified row outside bound | worst `INL` 0.1100 → 0.4834 LSB, worst `DNL` 0.0938 → 0.4856 LSB |
| `sim/adc-power/` schematic | 27 pt | no ratified row outside bound | worst `p_total` 207.884 → 223.961 µW; margin 4.81× → **4.47×** against 1 mW |
| `sim/dr0014-sampling/` | 27 pt | no ratified row outside bound | `samp_gain_err_lsb` 12.7674 → 12.7676 LSB (+0.0004); `ron_path_worst_ohm` unmoved to the last digit |

**Every ideal-source control arm reproduces the committed citation it was the
control for at the commit this campaign ran on**, which is what makes the
paired differences above attributable:

- extracted `INL`/`DNL`: 0.528287 / 0.727556 LSB at `inl_t896_lsb` /
  `dnl_t767_t768_lsb`, `ss_125c_2.97v` — the same numbers, transitions and
  corner that
  [`20260817-214114-076d545`](../adc-inl-dnl/records/20260817-214114-076d545.md)
  published and `sim/characterization-summary.md` cited **when this campaign
  ran**. That citation has since been superseded — see immediately below.
- schematic `INL`/`DNL`: 0.1100 / 0.0938 LSB at `inl_t384_lsb` /
  `dnl_t128_t129_lsb`, `*_ss_125c_2.97v` — likewise, and still the current
  schematic citation.
- `Power`: 207.884 µW at `ff_-40c_3.63v` — the same number
  [`20260826-085142-155595d`](../adc-power/records/20260826-085142-155595d.md)
  reads, and still current.

### Which extraction this ran on (issue #392)

**The extracted pair above was taken on the pre-#381 extraction vintage, which
`main` superseded while this campaign was in review.** Stated rather than
absorbed, because it bounds what the extracted numbers here may be used for.

Issue #381 / PR #390 re-extracted `adc_top` against the post-DR-0035 (#356) /
post-DR-0037 (#378) geometry, rewrote
`sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice`, and re-quoted the
governing `INL / DNL` row:

| | worst `INL` | worst `DNL` | minimum headroom |
|---|---|---|---|
| pre-#381 extraction — **what the pair above ran on** (`…076d545`) | 0.528287 LSB | 0.727556 LSB | 0.2724 LSB |
| post-#381 re-extraction — **the current governing citation** (`20260923-095400-904af96`) | 0.517546 LSB | 0.681240 LSB | 0.3188 LSB |

What this does and does not cost the result:

- **The paired delta stands.** Both arms of the pair ran at the same commit, on
  the same netlist, on the same host, so the difference between them still
  carries the `V_cm` network and nothing else. The campaign's conclusion — *no
  ratified row moves outside its bound under a real `V_cm` network at
  DR-0026's budget* — holds on the vintage it was measured on, and the ideal
  control arm of the current extraction passes the same row by a wider margin
  still.
- **The 0.2126 LSB headroom figure is vintage-specific, and is the pessimistic
  one.** The re-extraction moved the ideal arm's worst `DNL` down
  (0.727556 → 0.681240 LSB, −6.37 %), i.e. *away* from the bound, so if the
  network's perturbation is comparable on the new vintage the headroom there is
  wider than 0.2126 LSB. **That is an inference, not a measurement**, and it is
  deliberately not folded into the headline number: an operator risk-acceptance
  call on DR-0026 should read a measured worst case, not an extrapolated one.
- **Re-taking the extracted pair on the current extraction is filed as #392**,
  with the cost (~87 min wall per arm at 1 CPU on this host) and the recipe. No
  new code is needed — `run_full_pvt.sh adc-inl-dnl-extracted` already targets
  whatever `tb_adc_inl_dnl_extracted.spice` currently holds.

The schematic, `Power` and `dr0014-sampling` arms are unaffected: none of those
three decks' netlists were touched by #381.

### Reproducing the `V_cm`-network decks (the netlist sha256 pins)

`sim/vcm-drive-impedance/gen_vcm_variant.py` emits these decks at run time;
each arm's exact bytes are frozen in that campaign's
`netlist-snapshots/<record-id>.spice`, and each record pins their sha256. Two
notes for anyone regenerating them:

**Issue #260's three pins are preserved, and are enforced by a test.** The
generator's `--deck` parametrization (added here) originally reworded the
header comment it writes and added a `Source deck:` line, which changed the
bytes of the *default* deck's variant and silently broke the sha256 pinned in
`sim/vcm-drive-impedance/records/20260825-16*.md`. That was caught in review
and reverted: the `has_vref_network` branch now emits issue #260's wording
verbatim, and `Source deck:` is emitted only for a non-default `--deck`. So
`gen_vcm_variant.py --z-ohm 220 --c-dec-nf 40` reproduces `b76e7c67…` and
`--z-ohm 1100` reproduces `9efd4111…`, exactly as those records claim.
`sim/tests/test_vcm_variant.py::test_issue_260_netlist_sha256_pins_still_reproduce`
pins both hashes so the invariant is checked rather than asserted in prose.

**Three of this campaign's own arms were run *before* that revert**, so their
frozen snapshots differ from what the generator emits today. The difference is
confined to SPICE comment lines (`*`-prefixed) in the generated header, so it
is electrically inert and no measured value is affected — but a reader who
regenerates will get a different hash from the one the record pins, and should
know why:

| arm | record pin (bytes actually simulated) | current generator emits | delta |
|---|---|---|---|
| `adc-inl-dnl` schematic, `vcmnet` | `a56faec6…` | `b76e7c67…` | 3 comment lines |
| `adc-power` schematic, `vcmnet` | `0b0c88bf…` | `dc475090…` | 3 comment lines |
| `adc-inl-dnl` extracted, `vcmnet` | `52234c13…` | — | 3 comment lines, **plus** the #381 re-extraction (above) |
| `dr0014-sampling`, `vcmnet` | `849d993d…` | `849d993d…` | **none** |

The record pins are left as they are on purpose: they record the bytes that
were actually simulated, which is what a provenance pin is for. To check the
claim that the delta is comment-only, diff the frozen snapshot against a fresh
regeneration, e.g.

```sh
python3 sim/vcm-drive-impedance/gen_vcm_variant.py \
    --deck sim/adc-power/testbench/tb_adc_power.spice \
    --z-ohm 220 --c-dec-nf 40 --out /tmp/v.spice
diff <(tail -n +5 sim/adc-power/netlist-snapshots/20260923-114021-836a876.spice) /tmp/v.spice
```

(`tail -n +5` drops the snapshot's own four-line provenance header.)

### Two structural results, not just numbers

**`sim/dr0014-sampling/` is insensitive and `sim/adc-inl-dnl/` is not, by
more than three orders of magnitude** (sampling-path linearity moves
1.5 × 10⁻⁴ LSB; converter linearity moves 0.616 LSB on the same network, the
same budget and the same host). That is not noise, it is the mechanism: the sampling
deck measures one sampling event, during which `V_cm` is *held*; the converter
deck measures ten bit trials, across which the array is *released onto*
`V_cm` and re-engaged twice per conversion. DR-0026's derivation identifies
that whole-array release as `V_cm`'s binding case and as the structural reason
`V_cm`'s ceiling is tighter than `V_REF`'s — and the split measured here is
that argument showing up as data.

**`Offset error` is not reachable from this campaign, and this run supports
rather than merely asserts that.** `sim/characterization-summary.md` cites
that row from comparator-only decks which contain no `V_cm` node at all. The
array-level offset term that *is* `V_cm`-sensitive is the top-plate `V_cm`
switch's charge-injection mismatch, which lives in `sim/dr0014-sampling/`'s
`tp_inj_mis_*` / `bp_inj_mis_lsb` — measured here, and moving 2.2 × 10⁻⁴ LSB
against a 2 LSB ratified window.

### What this campaign did not run, and why

**`sim/adc-enob-fft/` (`ENOB` / `SFDR`) — deferred, and DR-0026's stated
reason for deferring it no longer holds.** DR-0026 excluded the dynamic deck
because both rows already fail for reasons DR-0025 tracks, "which would make a
`V_cm`-attributable delta impossible to isolate". **That objection is answered
by this campaign's design**: a paired same-commit control arm isolates the
delta regardless of whether the row passes, and `compare_vcm.py` now reports a
breach present in both arms separately from one the network introduces,
precisely so an already-failing row can still be differenced. The reasons it is
deferred anyway are narrower and should be recorded as such:

1. a delta cannot flip a verdict that is already **FAIL** (`SFDR` by 5.59 dB,
   `ENOB` below 9.0), so no ratified row's *status* depends on it; and
2. it is this suite's single most expensive per-point campaign, and on this
   host — where each agent is capped at one CPU by cgroup quota, and the
   measured per-arm cost of the cheaper decks already ran to 1–2.5 hours —
   the pair was the one deck whose cost exceeded what remained after the
   decisive extracted pair was run.

It remains worth running, and it is now the most informative unrun measurement
in this area: the 0.616 LSB static-linearity move this campaign measured is
large enough that a dynamic cost is plausible rather than speculative, and the
`SFDR` gap is a live design question.

**`adc-power-extracted` — not run.** The `Power` row's governing citation is
extracted, so in principle it deserves the same treatment as `INL / DNL`'s. It
was not run because the schematic pair puts the answer 4.47× away from the
bound: for the extracted netlist to breach `< 1 mW`, extraction would have to
multiply the `V_cm` network's power cost by more than fifty. The deck-pair is
wired into `run_full_pvt.sh` under the identical recipe
(`./sim/vcm-full-pvt/run_full_pvt.sh adc-power-extracted`) and needs no new
code to run.

### Does anything need to change in `spec/`?

**Not on this evidence, and this campaign does not propose it.** No ratified
row is outside its bound, so nothing here forces a spec change, and CLAUDE.md's
rule runs the other way in any case: a spec change goes through `spec/` with a
decision record, and agents do not relax a ratified bound to make a result
pass. Nothing in this campaign widened, relaxed or restated a bound — the
manifests, the targets and the `< 1 LSB` window are untouched.

What the result *does* bear on is a decision that is already open.
[DR-0026](../../spec/decision-records/DR-0026-vcm-drive-source.md) is
**proposed — requires operator sign-off**, and it asks the operator to accept
`Z_vcm ≤ 220 Ω` / `C_dec ≥ 40 nF` as the provisioned envelope. That decision is
now materially better-informed in a specific way: at exactly that envelope the
governing `INL / DNL` row's **worst-case remaining margin is 0.2126 LSB**
against its ratified `< 1 LSB` bound (`dnl_t767_t768_lsb`, `ss_125c_2.97v`);
at the corner the network perturbs hardest it retains **0.54×** of the
perturbation (0.3334 LSB after a 0.6163 LSB move); and the `< 0.5 LSB` stretch
goes from missed at 1 of 27 points to missed at 20 of
27. Whether that is an acceptable price for the envelope — or whether
`Z_vcm,max` should be tightened below 220 Ω so the row keeps more of its
margin — is an authority call on risk acceptance, not something this campaign
can settle. It is flagged for the operator on DR-0026's own sign-off, where it
belongs, and not absorbed here.
