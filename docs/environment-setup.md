# Environment Setup: xschem + ngspice + gf180mcu (macOS / Homebrew)

Bootstrap steps for the open-source design/sim flow described in
[`CLAUDE.md`](../CLAUDE.md): xschem (schematic capture / netlisting) +
ngspice (simulation) against the gf180mcu PDK (fetched via
[volare](https://github.com/efabless/volare)).

This doc is intended to be followed **verbatim, from a clean shell**, on any
fresh machine or agent session.

**Ported from `2AMLogic/gf180-bandgap@58024be`** per `CLAUDE.md`'s bootstrap
rule. The install steps are identical — the sister canary repos deliberately
share one bootstrap and one pinned PDK hash — and only the acceptance step
(§5, §7) is specific to this repo.

Recorded on macOS (Darwin, arm64) with Homebrew. If you are on a different
OS, the `xschem` source build steps are the same; substitute your platform's
package manager for the Homebrew dependency installs.

A worked **Linux** install of the simulation half of this toolchain (no xschem)
is scripted in
[`.github/workflows/nightly-pdk.yml`](../.github/workflows/nightly-pdk.yml):
ngspice built from the upstream release tarball at the pinned major, and the
gf180mcu PDK fetched with volare at the pinned hash below. It is executable
documentation — it runs nightly, so it cannot rot silently the way a prose
install guide can.

## 1. Versions used to validate this doc (2026-07-31)

| Tool | Version | Source |
|---|---|---|
| xschem | **3.4.7** (tag `3.4.7`, commit `92dd8fe5f4d5c1057489710d8a22f18fdc9d7ed0`) — also recorded machine-readably as `xschem_tag`/`xschem_commit` in `sim/toolchain.json`, so the nightly's from-source build (`.github/workflows/nightly-pdk.yml`) and this table cannot silently diverge | built from source, see §2 |
| ngspice | **46** | Homebrew (`ngspice`) |
| volare | **0.20.6** | Homebrew / pip (`volare`) |
| gf180mcu PDK | commit hash **`c6d73a35f524070e85faff4a6a9eef49553ebc2b`** | `volare fetch` |
| python3 | **3.14.6** (≥ 3.9 required) | Homebrew; stdlib only, no venv |
| Build deps | `cairo`, `tcl-tk@8`, `xorgproto`, XQuartz (cask), `bison`, `flex` | Homebrew / macOS system tools |

The gf180mcu hash above is the one every sister gf180 canary repo should
reuse verbatim (pinned, not "latest" — re-running `volare ls-remote` later
will show newer hashes; do not silently switch to them without updating this
doc and re-validating §5 and §7).

**These pins are enforced, not just documented.** The same values live in
machine-readable form in [`sim/toolchain.json`](../sim/toolchain.json), and the
corner runner checks them **before simulating a single point**:

| Pin | Rule | Why |
|---|---|---|
| `open_pdks` hash | exact match | the hash *is* the device model set — a different revision produces numbers no other record under `sim/` is comparable with, silently and with no error |
| `ngspice_min_major` | floor (newer allowed, and recorded) | a run on an engine older than the validated one is not something this repo has ever verified |
| `python_min` | floor | the harness is written against it |

A mismatch is fatal: the runner exits `3` having simulated nothing, rather than
emitting a partial or incomparable result. To re-validate the repo against a
newer PDK deliberately, pass `--allow-toolchain-drift` — every record written
under that flag is stamped with the drift, both as a banner at the top of the
record and in its Environment section, so drifted evidence can never be
mistaken for pinned evidence. Changing a pin means editing **both**
`sim/toolchain.json` and this table in the same change (a unit test fails if
they disagree) and re-running `bash sim/selftest.sh`.

`sim/toolchain.json` also carries `xschem_tag` / `xschem_commit` (§2's pin,
repeated verbatim). That pair is **not** in the table above and is not checked
by `run_corners.py --check-env` — `sim/smoke_test/run_smoke_test.sh` already
fails outright if xschem is simply missing, and there is no xschem-version
banner comparison wired up (unlike ngspice's `ngspice-<major>`). Its job is to
give `.github/workflows/nightly-pdk.yml`'s from-source xschem build a single
source of truth for its cache key and clone ref, instead of retyping the tag
in the workflow.

## 2. Build xschem from source

`xschem` has **no Homebrew formula** on macOS (`brew search xschem` / `brew
info xschem` both come back empty; there is no relevant tap, and there is no
MacPorts `port` binary either as a fallback). Build it from the upstream
[xschem](https://github.com/StefanSchippers/xschem) repository:

```bash
# Build dependencies (Homebrew + macOS system tools):
brew install cairo tcl-tk@8 xorgproto
brew install --cask xquartz   # provides /opt/X11 (X11 headers/libs)
# bison and flex ship with the macOS command line tools (/usr/bin/bison,
# /usr/bin/flex) -- no separate install needed on a machine with Xcode CLT.

# Clone the exact tag this doc was validated against:
git clone --branch 3.4.7 https://github.com/StefanSchippers/xschem.git
cd xschem
git rev-parse HEAD   # expect 92dd8fe5f4d5c1057489710d8a22f18fdc9d7ed0

# tcl-tk@8 is keg-only on Homebrew -- point configure/make at it explicitly:
export PATH="/opt/homebrew/opt/tcl-tk@8/bin:$PATH"
export PKG_CONFIG_PATH="/opt/homebrew/opt/tcl-tk@8/lib/pkgconfig:$PKG_CONFIG_PATH"
export LDFLAGS="-L/opt/homebrew/opt/tcl-tk@8/lib"
export CPPFLAGS="-I/opt/homebrew/opt/tcl-tk@8/include"

./configure --prefix=/opt/homebrew
make -j4
make install PREFIX=/opt/homebrew
```

(On Intel Macs, substitute `/usr/local` for `/opt/homebrew` throughout.)

Verify the headless netlist mode works against a trivial schematic (no GUI,
no PDK needed for this check):

```bash
xschem -n -x -q -r /opt/homebrew/share/doc/xschem/examples/lm317.sch -o /tmp
# no "Error:" lines expected; produces /tmp/lm317.spice
```

`-n` (netlist), `-x`/`--no_x` (headless, no X11 window), `-q` (quit after),
`-r`/`--no_readline` (safe for non-interactive/redirected stdin+stdout).

### A note on `~/.xschem/xschemrc` (machine-specific gotcha)

xschem loads, in order: the system-wide `xschemrc`, then
`~/.xschem/xschemrc` (**user**-level, overrides the system one), then a
project-local `./xschemrc` in the current working directory (overrides
both) — **or** whatever file `--rcfile <path>` points at, if given.

If a machine already has a stale/unrelated `~/.xschem/xschemrc` (e.g. left
over from a prior, unrelated project), it can silently override
`XSCHEM_LIBRARY_PATH` and break even the generic `devices/` symbol library
(`l_s_d(): Symbol not found: ...` for every basic symbol). This repo does
**not** rely on `~/.xschem/xschemrc` being correct — see
[`design/xschemrc`](../design/xschemrc), a project-local rc file that resets
`XSCHEM_LIBRARY_PATH` explicitly. Always invoke xschem for this repo with
`--rcfile design/xschemrc` (see §5) so behavior does not depend on
whatever is (or isn't) in any given machine's user-level dotfile.

## 3. Fetch the gf180mcu PDK via volare

```bash
volare --version                              # expect 0.20.6 (or record whatever is installed)
volare ls-remote --pdk gf180mcu               # lists available commit hashes, newest first
volare fetch  --pdk gf180mcu c6d73a35f524070e85faff4a6a9eef49553ebc2b
volare enable --pdk gf180mcu c6d73a35f524070e85faff4a6a9eef49553ebc2b
volare output --pdk gf180mcu                  # confirm: c6d73a35f524070e85faff4a6a9eef49553ebc2b
```

This creates `~/.volare/gf180mcuA` / `gf180mcuB` / `gf180mcuC` / `gf180mcuD`
(symlinks into `~/.volare/volare/gf180mcu/versions/<hash>/...`) — one
directory per gf180mcu variant. Per `CLAUDE.md` and the block's 0–3.3 V input
range, this repo uses the 3.3 V flavor, variant **`gf180mcuD`**.

The variant letter also fixes the **metal stack**, which matters for the CDAC:
per the PDK's own `libs.tech/klayout/drc/README.md` variant table, `gf180mcuD`
is `metal_level=5LM` with `mim_option=B`, so its MIM capacitor sits between
metal 4 and metal 5 and the corresponding model subckts are
`cap_mim_*_m4m5_noshield`. The harness encodes that mapping
(`MIM_STACK_BY_VARIANT` in `sim/harness/pdk.py`) so no testbench has to name a
metal stack; `sim/run_corners.py --check-env` prints the resolved stack.

## 4. `PDK_ROOT` / `PDK` environment convention

```bash
export PDK_ROOT="$(volare path)"   # -> ~/.volare (volare's PDK root)
export PDK="gf180mcuD"             # the 3.3V variant this repo targets
```

So `$PDK_ROOT/$PDK` resolves to `~/.volare/gf180mcuD`, and the ngspice
models live under `$PDK_ROOT/$PDK/libs.tech/ngspice/`.

Add this as a small sourceable snippet rather than a one-off manual export,
e.g. append to your shell profile:

```bash
# gf180-sar-adc: xschem/ngspice/gf180mcu env (see docs/environment-setup.md)
export PDK_ROOT="$(volare path)"
export PDK="gf180mcuD"
```

Demonstrate it survives a fresh shell:

```bash
$ echo $PDK_ROOT $PDK
/Users/you/.volare gf180mcuD
```

Equivalently, from inside the repo: `source sim/env.sh`, which exports the
same variables plus `GF180_PDK_PATH`, `GF180_MODELS` and
`XSCHEM_USER_LIBRARY_PATH`, all derived from whatever PDK the harness itself
resolved — so xschem and the corner runner can never disagree about which PDK
is in use.

## 5. Smoke test: xschem netlist -> ngspice sim, referencing gf180mcu models

[`design/smoke_test.sch`](../design/smoke_test.sch) is a throwaway
sample-and-hold primitive — **not** SAR ADC content, just enough to exercise
the full toolchain: `VIN (1.0 V)` into the source of one gf180mcu 3.3 V nfet
(`nfet_03v3_dss`) used as a sampling switch, gate held on at 3.3 V by
`VSAMPLE`, drain (`vhold`) loaded by an ideal 1 pF hold capacitor and pulled
up to `VDD` through a 10 kΩ resistor so the operating point is well defined.

The gf180mcu model include is deliberately **not** hardcoded into the
schematic (no machine-specific `$PDK_ROOT` path baked into version-controlled
files) — [`sim/smoke_test/run_smoke_test.sh`](../sim/smoke_test/run_smoke_test.sh)
generates a small `sim/smoke_test/pdk_include.spice` shim from the
`PDK_ROOT`/`PDK` environment variables at run time (git-ignored: it is a
derived artifact, regenerated on every run, not committed evidence), then:

1. Netlists `design/smoke_test.sch` with `xschem -n -x -q -r --rcfile
   design/xschemrc -o sim/smoke_test design/smoke_test.sch`, producing
   `sim/smoke_test/smoke_test.spice` (git-ignored — it is regenerated, and
   xschem stamps the generating machine's absolute path into it).
2. Runs `ngspice -b smoke_test.spice` from `sim/smoke_test/`, computing the
   operating point.

Run it (after §3 is done — §4's exports are optional, see below):

```bash
sim/smoke_test/run_smoke_test.sh
```

No environment setup and no hand-editing is required: if `PDK_ROOT`/`PDK` are
unset, the script resolves the PDK through the harness (`sim/run_corners.py
--print-env`) so the smoke test and the corner runner can never disagree about
which PDK is under test. Exported `PDK_ROOT`/`PDK` still win, which is what
makes the two paths equivalent:

```bash
export PDK_ROOT="$(volare path)"   # optional — pins the smoke test to a
export PDK="gf180mcuD"             # specific install instead of the resolver
sim/smoke_test/run_smoke_test.sh
```

If the PDK genuinely cannot be found, the script says so and exits non-zero
before netlisting anything.

Pass `--no-write` to run the same check without appending to
`sim/smoke_test/smoke_test.log` — for a throwaway re-run, or for any automated
runner, which must never add machine-generated sections to an append-only
evidence log:

```bash
sim/smoke_test/run_smoke_test.sh --no-write   # same run, recorded nowhere
```

Expected: exits 0, no `Error:` lines, and `sim/smoke_test/smoke_test.log`
(committed, append-only — each run appends a new dated section rather than
overwriting prior runs, per `CLAUDE.md`'s "`sim/` results are append-only
evidence") ends with the operating-point voltages, e.g.:

```
v(vdd) = 3.300000e+00
v(vsample) = 3.300000e+00
v(vin) = 1.000000e+00
v(vhold) = 1.025608e+00
ngspice-46 done
```

`v(vhold)` sits just above `v(vin)` because the 10 kΩ pull-up pushes ~230 µA
through the closed switch's on-resistance. That the value is *not* exactly
1.0 V is the point: a real device model is in the loop.

## 6. Reproducibility checklist

- [ ] From a **new terminal** (nothing pre-sourced from a prior session),
      confirm `xschem --version` reports `XSCHEM V3.4.7` and `ngspice -v`
      reports `ngspice-46`.
- [ ] Confirm `echo $PDK_ROOT $PDK` resolves correctly after sourcing your
      shell profile snippet from §4 (not just in the shell where you first
      set it).
- [ ] Confirm the gf180mcu hash in use is the **pinned** one recorded in §1
      (`volare output --pdk gf180mcu`), not silently "whatever `ls-remote`
      shows as newest today." `python3 sim/run_corners.py --check-env` checks
      this for you and prints `pins    : OK` only when every pin is satisfied;
      `pins    : DRIFT` (exit 1) names each tool that does not match.
- [ ] Run `sim/smoke_test/run_smoke_test.sh` **from a shell with nothing
      sourced** and confirm it exits 0 with no `Error:` lines in its output.
- [ ] Run `bash sim/selftest.sh` and confirm it ends with
      `PASS: harness is functional end to end and corner switching is verified.`

## 7. Next: the PVT corner harness

Everything above establishes the *install*. The evidence-producing harness
sits on top of it and resolves the same PDK by a superset of the same rules
(`GF180_PDK_PATH` -> `PDK_ROOT` + `PDK` -> `sim/pdk.local.json` ->
`sim/pdk.json` -> the usual install prefixes, volare first), so the
`PDK_ROOT`/`PDK` exports from §4 are all it needs:

```bash
python3 sim/run_corners.py --check-env   # what the harness resolved, or how to fix it
python3 sim/run_corners.py --print-env   # shell exports for the resolved PDK
source sim/env.sh                        # same exports, for xschem and ad-hoc ngspice
bash sim/selftest.sh                     # unit tests + PVT sweeps + the negative control
```

`bash sim/selftest.sh` takes ~2.5 minutes and is the acceptance step that
matters: passing §5 only proves the tools are installed. Stage 4 of the
self-test re-runs the same testbenches with every model section forced to
typical and requires them to **fail** — that is the only thing that
distinguishes a working corner sweep from one that silently simulates typical
everywhere.

`design/xschemrc` follows the same resolution order, so xschem and the corner
runner never disagree about which PDK is in use; compare
`sim/run_corners.py --print-env` against the path xschem reports if you ever
suspect they have drifted apart.

The full harness reference — PDK resolution, corner definitions, how to write
a testbench manifest, the corner-sensitivity guarantees, and why
`sim/smoke_test/` (this document's install check) and `sim/smoke-sar-bias/`
(the harness's own acceptance test) are two different things — is
[`sim/harness/README.md`](../sim/harness/README.md). The record format it
writes into is [`sim/README.md`](../sim/README.md).
