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
running it, so this campaign runs five deck-pairs, not three:

| Deck | Ratified row it owns | Grid used here | Points |
|---|---|---|---|
| `sim/dr0014-sampling/` | **Gain error, systematic** (≤ 0.5 LSB) | manifest default: `tt`/`ss`/`ff` × 3 T × 3 V | 27 |
| `sim/adc-inl-dnl/` | **INL / DNL** (< 1 LSB) | manifest default: `cdac` 7-corner × 3 T × 3 V | 63 |
| `sim/adc-inl-dnl/` (**extracted, governing**) | **INL / DNL** (< 1 LSB), the *governing* netlist | `--corners tt ss ff` × 3 T × 3 V | 27 |
| `sim/adc-power/` (schematic) | **Power @ 1 MS/s** (< 1 mW) | `--corners tt ss ff` × 3 T × 3 V | 27 |
| `sim/adc-enob-fft/` | **ENOB / SFDR** | `--corners tt ss ff --temps 125` (two-stage strategy) | 9 |

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
