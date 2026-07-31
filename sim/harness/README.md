# sim/harness — the PVT corner runner

Reproducible ngspice simulation against the gf180mcu PDK. This document covers
**how to run** the harness, **how to write a testbench**, and **how this
harness diverges from the gf180-bandgap pattern it was ported from**.

The *output* of a run — directory layout, record-id format, the summary record
field set, and the append-only rule — is defined by
[`sim/README.md`](../README.md), not here. That convention is authoritative;
this harness exists to produce records that conform to it.

```
sim/
  run_corners.py            CLI entry point (stdlib python3, no venv)
  env.sh                    `source sim/env.sh` to export the same PDK to your shell
  selftest.sh               harness acceptance test (unit tests, PVT run, negative control)
  pdk.json                  committed PDK defaults (variant, extra search roots)
  harness/                  the runner itself (this directory)
  tests/                    harness unit tests (no PDK, no ngspice required)
  .work/                    generated ngspice decks (git-ignored, disposable)

  <experiment-slug>/        one per claim under test -- see sim/README.md
    testbench/              tb.json + netlist fragment      <- you write these
    netlist-snapshots/      frozen netlist per record       <- the harness writes these
    corners/<record-id>/    raw <corner-id>.log per PVT point
    records/<record-id>.md  append-only summary record
```

## Quick start

```bash
python3 sim/run_corners.py --check-env      # is ngspice + the PDK present?
python3 sim/run_corners.py --list           # experiments, corners, corner sets
python3 sim/run_corners.py smoke-sar-bias   # run the full PVT grid, mint a record
bash sim/selftest.sh                        # prove the harness works (writes nothing)
```

`sim/selftest.sh` takes ~2.5 minutes on a laptop (4 sweeps of 45–63 points
each). `--quick` skips to a single PVT point, but see the warning it prints:
a single point cannot verify corner switching.

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| `ngspice` | simulation | `brew install ngspice` / `apt-get install ngspice` |
| gf180mcu PDK | device models | `pip install volare && volare enable --pdk gf180mcu <hash>` |
| `xschem` | schematic capture (optional for simulation) | build from source, see `docs/environment-setup.md` |
| python3 ≥ 3.9 | the harness | stdlib only, no packages |

Full bootstrap, including pinned versions: [`docs/environment-setup.md`](../../docs/environment-setup.md).

The harness never hardcodes a PDK path. It resolves one, in order:

1. `GF180_PDK_PATH` — the *variant* directory, e.g. `~/.volare/gf180mcuD`
   (the one containing `libs.tech/`).
2. `PDK_ROOT` (+ `PDK`, default `gf180mcuD`) — the open_pdks / OpenLane convention.
3. `sim/pdk.local.json` — machine-local, git-ignored.
4. `sim/pdk.json` — committed defaults.
5. Built-in search roots: `~/.volare`, `~/.ciel`, `/usr/share/pdk`,
   `/usr/local/share/pdk`, `~/share/pdk`, `/opt/pdk`.

If nothing is found the runner exits 3 with install instructions rather than
producing a misleading result. `sim/run_corners.py --print-env` emits the
resolved paths as shell exports; `source sim/env.sh` applies them so that an
interactive ngspice or xschem session uses the identical PDK.

## The PVT grid

`CLAUDE.md` requires PVT corners on every recorded result. The defaults are
baked into `corners.py` and are what a testbench gets unless its manifest says
otherwise:

- **Temperature**: −40, 27, 125 °C
- **Voltage**: nominal ±10 % (3.3 V flavor → 2.97 / 3.3 / 3.63 V)
- **Process**: see below

gf180mcu has no single global corner switch — each device family carries its
own `.lib` section in `sm141064.ngspice`, so a named corner here is a bundle of
six sections (MOS, resistor, BJT, diode, MOS cap, MIM cap):

| Corner | Meaning |
|---|---|
| `tt` | everything typical |
| `ff` / `ss` | every device family fast / slow |
| `fs` / `sf` | fast-N/slow-P and slow-N/fast-P, passives typical |
| `cap_ff` / `cap_ss` | **both** capacitor families skewed, rest typical |
| `mim_ff` / `mim_ss` | MiM cap skewed (the CDAC unit element), rest typical |
| `moscap_ff` / `moscap_ss` | MOS cap skewed, rest typical |
| `res_ff` / `res_ss` | resistor sheet rho skewed, rest typical |

Corner sets: `tt` (1), `mos` (5, the default), `cdac` (7 — the capacitor
families a CDAC's linearity rides on), `full` (13, every defined corner).
`full` × 3 temperatures × 3 supplies = 117 operating points.

**Why the capacitor corners matter here.** The five MOS corners leave both
capacitor families at `*_typical`, so a MOS-only sweep would never notice a
broken `mimcap`/`moscap` include — and a 10-bit CDAC's accuracy rides on the
unit capacitor far more than on the MOS skew. Any experiment whose claim
depends on capacitance must use `cdac` or `full`, not the default `mos`.

**MoM capacitors are not modelled.** The open gf180mcu PDK ships no MoM /
lateral-flux capacitor subckt (neither `sm141064.ngspice` nor
`sm141064_mim.ngspice` defines one), so there is no MoM `.lib` section to
sweep. A MoM-based CDAC would have to be substantiated by parasitic extraction
rather than a model corner. This is a PDK limitation, not a harness one, and
it is an input to the CDAC topology decision — not something the harness can
paper over.

Each point becomes one `<corner-id>` — `<process>_<temp>c_<supply>v`, the
naming `sim/README.md` ratifies — and one raw log under `corners/<record-id>/`.

Override any axis from the command line:

```bash
python3 sim/run_corners.py device-cdac-cap --corner-set full -j 8
python3 sim/run_corners.py smoke-sar-bias --corners tt mim_ss --temps -40 125
python3 sim/run_corners.py smoke-sar-bias --supply 1.8 --supply-tol 0.10
```

**Subsets need a reason.** `sim/README.md` requires every record's *Corner
matrix run* field to be the full mandated matrix "unless the record states why
a subset was used". The runner enforces that: if the grid you asked for is
missing a mandated temperature, a mandated supply, or has fewer than three
process corners, it refuses to write a record unless you supply
`--subset-reason '<why>'` (copied verbatim into the record), or pass
`--no-write` because you are only debugging.

```bash
# debugging: runs, records nothing
python3 sim/run_corners.py smoke-sar-bias --corners tt --temps 27 --supply-tol 0 --no-write

# a deliberate, justified subset: runs and records, with the reason on the record
python3 sim/run_corners.py smoke-sar-bias --corners tt --temps 27 \
    --subset-reason "nominal-only mismatch sweep; distribution claim, see Statistical convention"
```

## Corner-sensitivity: proving the sweep is real

The failure this harness is built to prevent is **silent**: a runner that
appears to sweep PVT but simulates typical everywhere — a wrong model include,
an ignored parameter, a mistyped corner-bundle name — produces plausible
numbers with no error, and every record built on it is worthless. Three
mechanisms guard against it, in increasing strength.

**1. `min_spread_pct` (grid-wide).** Ported from upstream. Asserts a
PVT-sensitive measurement moved *somewhere* across the grid.

**2. `min_spread_pct_by_axis` / `max_spread_pct_by_axis` (per axis).** The
grid-wide floor is not enough: it passes happily when the temperature axis
moves and the process axis is stuck on typical. For each axis, the harness
slices the grid so the other two axes are held fixed, measures the spread
within each slice, and checks the **weakest** slice against the floor — so one
dead slice cannot hide behind the others. `report.axis_sensitivity()` computes
this, and every record carries the resulting table whether or not the
testbench checks it.

An axis with fewer than two levels in the grid was never swept, so nothing
about it was verified. That is reported as a **failure**, not a pass — unless
the run is already declared non-evidence (`--no-write`) or carries a written
`--subset-reason`.

**3. `--sabotage-corners` (the negative control).** Flags and thresholds can
themselves be wrong. This flag keeps every corner *name* but forces every
model section to typical, reproducing the exact silent failure above. A
healthy testbench **must fail** under it. `sim/selftest.sh` stage 4 runs both
repo testbenches this way and fails the whole self-test if either passes.
Sabotaged runs force `--no-write`, so they can never enter the evidence tree.

Concretely, on `smoke-sar-bias`: sabotage leaves the grid-wide spread of
`vgs_nfet` at ~17 % (temperature is still moving it), which a grid-wide floor
would accept — while the process-axis spread collapses to 0 % and the per-axis
floor catches it. That gap is exactly why mechanism 2 exists.

## Writing a testbench

Create `sim/<experiment-slug>/testbench/` with a manifest and a netlist
fragment. The slug is the experiment directory from `sim/README.md`: one per
distinct claim under test, kebab-case.

`tb.json`:

```json
{
  "name": "my-experiment",
  "description": "one line, shows up in --list and in the record",
  "claim": "spec/adc.md#inl-dnl",
  "netlist": "my_tb.spice",
  "nominal_supply_v": 3.3,
  "supply_tolerance": 0.1,
  "temperatures_c": [-40, 27, 125],
  "corners": ["cdac"],
  "analyses": ["op"],
  "params": {"iload": "10u"},
  "options": ["reltol=1e-5"],
  "measure": {"vref": "v(vref)", "iq_ua": "-i(vsup)*1e6"},
  "checks": {
    "vref": {
      "min": 1.15,
      "max": 1.25,
      "max_spread_pct": 2.0,
      "min_spread_pct_by_axis": {"process": 2.0}
    }
  },
  "evidence": {"record_kind": "corner-matrix"}
}
```

`claim` is the default for the record's **Claim** field — the ratified spec
line this experiment substantiates. `--claim` overrides it per run.

The netlist is a **fragment**, not a complete deck. It must not contain
`.include`, `.lib`, `.temp`, `.control`, `.endc` or `.end` — the harness owns
all of those, which is what lets one netlist sweep the whole grid unedited.
The loader rejects fragments that break this rule instead of silently pinning
every corner to 27 °C. The harness hands the fragment:

| Parameter | Value |
|---|---|
| `vdd_val` | supply for this PVT point |
| `vdd_nom` | nominal supply, for ratio measurements |
| `temp_c` | temperature for this PVT point (also applied via `.temp`) |
| `mim_cap_1f0` / `mim_cap_1f5` / `mim_cap_2f0` | CDAC unit-cap subckts, see below |

The PDK names its MIM subckts after the metal pair the capacitor sits between
(`cap_mim_2f0_m4m5_noshield`), which is a property of the **variant**, not of
the device. So no testbench in this repo names a metal stack: the harness
emits `mim_cap_<density>` wrapper subckts bound to the resolved variant's
stack (`MIM_STACK_BY_VARIANT` in `pdk.py`, derived from the PDK's own DRC
variant table). An unrecognised variant is a loud error, never a guessed
stack.

Each `measure` entry becomes `let m_<name> = <expr>` followed by `print` inside
the control block, so the expression must reduce to a **scalar**: fine for
`op`; for `tran`/`ac` reduce with `maximum()`, `mean()`, `v(out)[0]`, etc.
Note that manifest `params` become `.param` directives in *netlist* scope and
are **not** visible inside the `.control` block — write literals in `measure`
expressions.

`checks` are evaluated after the sweep. Unknown keys and unknown axis names
are rejected at load time, because a silently-ignored `min_spread_pct` is the
exact failure this harness exists to catch:

| Key | Applies to | Meaning |
|---|---|---|
| `min` / `max` | every point | hard limit; failure names the offending corner-id |
| `max_spread_pct` | the grid | `(max−min)/\|mean\|` must stay under the limit |
| `min_spread_pct` | the grid | must *exceed* it — asserts the sweep really moved |
| `min_spread_pct_by_axis` | one named axis | the **weakest** slice must exceed it |
| `max_spread_pct_by_axis` | one named axis | the **strongest** slice must stay under it |

Axis names: `process`, `temperature`, `supply`.

### Evidence extensions

`sim/README.md` adds five ADC-specific field groups on top of the base record.
Declare them in the manifest's `evidence` block or pass them per run; both are
**validated** (`harness/evidence.py`), so a mistyped methodology tag is an
error rather than free text nobody notices:

| Group | Manifest keys / CLI flags |
|---|---|
| Dynamic-test (FFT) | `fft_n`, `fft_input_hz`, `fft_bin`, `fft_window`, `fft_fs_hz` |
| Linearity methodology | `linearity_method` (one of the four ratified tags) |
| Monte Carlo convention | `mc_seed`, `mc_scope`, `mc_sigma` |
| Noise methodology | `noise_method`, `noise_seed`, `noise_duration_justification` |
| Characterization variant | `record_kind: characterization` + `data_provenance` |

Rules the validator enforces, straight from `sim/README.md`: a
characterization record must carry `data_provenance`; a windowed FFT record
must say why coherent sampling was not used; a `transient-noise` record must
state its seed and justify its duration; a Monte Carlo record must state seed
handling, scope and sigma level together.

## What a run writes

One run mints one `<record-id>` (`<YYYYMMDD>-<HHMMSS>-<short-git-sha>`) and
writes, under `sim/<experiment-slug>/`:

| Path | Contents |
|---|---|
| `records/<record-id>.md` | the append-only summary record (the fields from `sim/README.md`, the per-axis sensitivity table, and an Environment section with PDK / MIM stack / ngspice / harness / git provenance) |
| `netlist-snapshots/<record-id>.spice` | verbatim frozen copy of the testbench fragment, with its sha256 |
| `corners/<record-id>/<corner-id>.log` | raw ngspice output, one file per PVT point |

Nothing is ever overwritten: the runner refuses to write over an existing
record or snapshot, and mints a later record-id if one is somehow already
taken. Corrections and re-runs get a new record-id and reference the prior one
with `--supersedes <record-id>`. Do not edit or delete anything under
`records/`, `netlist-snapshots/` or `corners/` — see the append-only rule in
`sim/README.md`. (The repo's `.gitignore` has a blanket `*.log`; it explicitly
re-admits `sim/*/corners/*/*.log` so the evidence a record links to is
actually committed.)

A run taken against a dirty working tree says so in the record's **Netlist
provenance** field and is not citable as a clean-tree result.

Exit codes: `0` pass · `1` a check failed · `2` a simulation failed or did not
converge · `3` environment problem (no ngspice, no PDK, unknown PDK variant,
bad manifest, unjustified PVT subset, non-conforming evidence fields).

Generated decks land in `sim/.work/<experiment-slug>/<record-id>/` and are
git-ignored, so a failing corner can be reproduced by hand with
`ngspice -b sim/.work/<slug>/<record-id>/<corner-id>.spice`.

## The two repo testbenches

`sim/smoke-sar-bias/` and `sim/device-cdac-cap/` are the harness's own
acceptance tests, not circuit deliverables. Both are needed: sabotaging only
one hides the other.

**`smoke-sar-bias`** (`op`, `mos` corner set) — four independent branches:

1. an ideal resistor divider — its *ratio* must read exactly 0.5 at all 45
   points (the PVT-invariant control), while its *absolute* value must track
   the supply and nothing else;
2. a diode-connected `nfet_03v3` at a supply-independent 10 µA — proves the
   MOS `.lib` section and `.temp` both take effect;
3. an `nfet_03v3` sampling switch, gate at vdd, 50 mV across the channel —
   `Ron` moves with all three axes, so it is what the per-axis floors lean on;
4. a `ppolyf_u` poly resistor — proves the resistor sections load.

**`device-cdac-cap`** (`ac`, `cdac` corner set) — effective capacitance of the
MiM unit cap (2.0 and 1.0 fF/µm²) and the 3.3 V MOS cap, from a 1 MHz AC
probe. This is the only thing in the repo that exercises the `mimcap`/`moscap`
sections, and it is written as a **characterization** record (measured values
+ data provenance, no spec pass/fail) because no ratified spec line exists yet.

### `sim/smoke-sar-bias/` vs `sim/smoke_test/` — two different jobs

The repo has two things with "smoke" in the name. They are deliberately
distinct and neither replaces the other:

| | `sim/smoke_test/` | `sim/smoke-sar-bias/` |
|---|---|---|
| Question it answers | "is my *install* correct?" | "is the *harness* correct?" |
| Scope | one point (tt, 27 °C, nominal) | the full 45-point PVT grid, plus the negative control |
| Path exercised | xschem netlisting → `$PDK_ROOT/$PDK` shim → ngspice | `sim/run_corners.py` → corner shim → ngspice → record writer |
| Run it | `sim/smoke_test/run_smoke_test.sh` | `bash sim/selftest.sh` |
| Output | `sim/smoke_test/smoke_test.log` (evidence of an install) | an append-only record under `sim/smoke-sar-bias/records/` |
| Owns | `docs/environment-setup.md`'s acceptance step | this harness's acceptance criteria |

`sim/smoke_test/` is the first thing to run on a fresh machine. `sim/selftest.sh`
runs *after* that passes. A green `smoke_test` with a red `selftest.sh` means
the harness is broken; the reverse cannot happen, because the harness cannot
run without a working install.

## xschem

`design/xschemrc` resolves the PDK the same way the harness does and sources
the PDK's own xschemrc, so gf180mcu symbols and this repo's `design/`,
`design/symbols/` and every `sim/<experiment-slug>/testbench/` are all on the
library path:

```bash
source sim/env.sh
cd design && xschem
```

Schematic netlists are written to `design/netlist/`. To simulate a schematic,
strip it to a fragment (or netlist a testbench schematic without its
`.control`/`.end` block) and point a `tb.json` at it — the corner runner is
agnostic about whether the fragment was typed or generated.

Note: xschem itself is not required to run any of the above; the corner runner
only needs ngspice and the PDK.

## Divergences from the gf180-bandgap pattern

Per `CLAUDE.md`, this harness is **ported from `2AMLogic/gf180-bandgap`**
(commit `58024be`) rather than designed from scratch. Module layout, PDK
resolution, deck composition, manifest schema, record-id scheme and the
append-only writer are kept identical so a future upstream reconciliation is
cheap. `sim/README.md` records the same provenance for the record format
itself, and this list is the harness-side companion to it. Nothing below is a
silent fork.

1. **Capacitor-dominated corners replace the bandgap's BJT/resistor ones.**
   Upstream adds `res_*` and `bjt_*` corners because a bandgap rides on
   resistor rho and BJT Is/beta. A SAR ADC has no BJT and rides on the CDAC,
   so this repo adds `cap_ff/ss`, `mim_ff/ss`, `moscap_ff/ss` and a `cdac`
   corner set, and keeps `res_*` for the bias/reference network. The
   six-family bundle structure is unchanged.
2. **Per-axis sensitivity checks (`*_spread_pct_by_axis`) are new.** Upstream
   has only the grid-wide `min_spread_pct`, which passes when one axis is
   stuck. See "Corner-sensitivity" above for why that is not sufficient here.
3. **`--sabotage-corners` and `sim/selftest.sh` stage 4 are new.** Upstream's
   self-test verifies the harness runs; it does not verify that corner
   switching is detectable when it breaks.
4. **The evidence writer implements `sim/README.md`'s five ADC extension
   groups** (`harness/evidence.py`), which have no upstream equivalent, and
   validates them. Upstream's writer knows only the base fields — and
   upstream's own harness PR had to be reworked because it was built before
   its record format was ratified. Building the extensions in from the start
   is the direct lesson from that.
5. **MIM subckts are bound to the PDK variant** (`MIM_STACK_BY_VARIANT`,
   `mim_cap_*` wrapper subckts). Upstream has no CDAC and never instantiates a
   MIM cap, so it has no equivalent.
6. **Manifest validation is stricter**: unknown `checks` keys and unknown axis
   names are rejected at load time.
7. **Testbench names differ** (`smoke-sar-bias` / `device-cdac-cap` vs
   upstream's `smoke-bias`), because the acceptance circuits are ADC devices.

A formal `spec/` decision record for these divergences is deferred to #6,
which lands the decision-record template this repo does not yet have; until
then this section is the authoritative list.
