#!/usr/bin/env python3
"""Port `sim/dr0014-sampling/`'s Group A (terms 1+2, sampling gain/INL) and
Group C (term 4, C_par-mismatch residue) onto the PMOS-body-remediated,
MiM-mapped **extracted** `ADC_TOP` core -- issue #89 **Section 6.3**'s
"Gain error (DR-0012/13 row)" line.

    python3 layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py --check

Writes ONE file:

    sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice

into a SIBLING testbench directory next to the schematic deck's own
(`sim/dr0014-sampling/testbench/`), not the same one -- see "Why a second
testbench directory, and why that still satisfies sim/README.md" below.
`sim.harness.testbench.load()` accepts any directory containing its own
`tb.json` (`Testbench.experiment_dir` is `directory.parent`), so pointing
`sim/run_corners.py` at `sim/dr0014-sampling/testbench-extracted/` still
writes records/corners/netlist-snapshots into the SAME
`sim/dr0014-sampling/` experiment directory the schematic run uses.

## What this ports, and how

`design/adc-top/gen_adc_top.py`'s `dr14_netlist()` builds GROUP A as five
differential pairs (`DR14_LEVELS`), each one schematic `adc_cdac_side`
instance per polarity plus a standalone `adc_tp_sw` top-plate switch, driven
by one shared two-phase schedule (`smptp`/`smpbp`/`nrel`/`nrel256`/
`hi256`/`lo256`) and read out through a per-pair `comparator` instance and
LSB-referred B-sources. The extracted `ADC_TOP` `.SUBCKT` already contains
BOTH array sides and BOTH per-side top-plate switches in one flat block
(`layout/adc-top/parasitics/README.md` "What was extracted"), so one `Xdut`
call per pair replaces the schematic's two `adc_cdac_side` + two
`adc_tp_sw` instances -- the same substitution `gen_extracted_core_tb.py`
already makes for the full #13 static-linearity deck.

`gen_extracted_core_tb._wire_pin()` maps every extracted-core pin onto a
`{tag}_...`-scoped net using `design/adc-top/gen_adc_top.py`'s own
per-tag-per-side naming convention. This module reuses it TWICE per pair,
with two different tags for the SAME `Xdut` call's pin list
(`_wire_pin_for_pair`, below): the per-weight leg pins, `sel_in` and
`tp_gn` are wired onto ONE shared ctrl-tag (`CTRL_TAG = "d14"`) so every
pair's `Xdut` receives the identical physical schedule the schematic deck's
a0..a4 already share (same net names, driven once); `vinp`/`vinn`/`topp`/
`topn` stay tag-scoped per pair, so each pair's own analog input level and
comparator readout stay independent. `_leg_sources()` drives that shared
schedule directly onto the `d14`-tagged net names -- the SAME waveforms
`dr14_netlist()` uses (`DR14_TP_FALL_NS`/`DR14_BP_FALL_NS`/`DR14_TRIAL_NS`),
just targeting different (but electrically equivalent) net names because
`_wire_pin()`'s convention differs from the schematic deck's bespoke one.

GROUP C reuses `_dr14_pair_extracted()` with an extra `C{tag}dcpar
{tag}_topp 0 <fF>` capacitor directly on the pair's own exposed `topp` net
-- the same injection `_dr14_pair()` (schematic) applies, unchanged: an
external capacitor in parallel with whatever else sits on that node,
independent of whether the node belongs to a schematic or an extracted
core.

## What this does NOT port, and why (CLAUDE.md: state explicitly)

- **GROUP B** (term 3, the fourth-leg settling A/B) needs
  `tb_dr0014_sampling.spice`'s deck-local `tb3_cdac_side` -- the DR-0011
  THREE-leg cell DR-0014 deleted from the design
  (`design/adc-top/gen_adc_top.py._dr14_ref_side3()`'s own docstring:
  "the converter no longer has a three-leg cell"). It was never drawn or
  extracted, so there is no extracted netlist to run this A/B against --
  not a missing deck, a nonexistent circuit. No extracted equivalent is
  possible without inventing a second, undrawn CDAC cell.
- **GROUP D** (the ratified Input-structure row's series R_on) needs a
  standalone `adc_tgate` instance at forced voltage/measured current.
  `klt extract` was run at `ADC_TOP`/`ADC_BLOCK` granularity only
  (`layout/adc-top/parasitics/README.md`), so no individually-addressable
  T-gate exists in the extracted netlist to probe this way -- the real
  R_on IS embedded in every `Xdut` instance below, but only reachable
  through a full conversion's worth of settling behaviour (already
  measured by `sim/adc-inl-dnl/`'s extracted-core `set_err`-style checks),
  not this deck's isolated forced-voltage method.

## Why a second testbench directory, and why that still satisfies
## sim/README.md

`sim/dr0014-sampling/testbench/tb.json`'s `measure`/`checks` reference
Group B's `b3_d`/`b4_d` and Group D's `ron0..4` nodes -- names this module's
netlist never defines, because those groups have no extracted equivalent
(above). Reusing that manifest unmodified (the pattern
`gen_extracted_inl_dnl_tb.py`/`gen_extracted_power_tb.py` follow) would
therefore not "reuse the methodology byte-for-byte" as it does for those
two decks -- it would silently fail every Group B/D measurement instead of
stating the gap. A second, explicitly SCOPED manifest
(`tb_extracted.json`'s own `measure`/`checks`, Groups A+C only) is the
honest alternative; sim/README.md's "same experiment directory" rule is
about where the record/corners/netlist-snapshot files land, not about
manifest identity, and `harness.testbench.load()` already supports pointing
at any directory that owns its own `tb.json` (`Testbench.experiment_dir`
is `directory.parent`) -- so this still writes into `sim/dr0014-sampling/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import gen_extracted_core_tb as G  # noqa: E402  (same directory)

gtop = G.gtop
sar = gtop.sar

#: The one physical DR-0014 two-phase schedule every pair's `Xdut` shares --
#: analogous to `design/adc-top/gen_adc_top.py`'s bare `smptp`/`smpbp`/
#: `nrel`/`nrel256`/`hi256`/`lo256` net names, but routed through
#: `_wire_pin()`'s tag convention so it lands on the SAME nets every pair's
#: `Xdut` call expects for its shared pins.
CTRL_TAG = "d14"


def _wire_pin_for_pair(pin: str, pair_tag: str) -> str:
    """`Xdut`'s net for one `.SUBCKT` pin: per-pair for the analog I/O,
    shared (`CTRL_TAG`) for everything else -- see module docstring."""
    if pin in ("vinp", "vinn", "topp", "topn"):
        return G._wire_pin(pin, tag=pair_tag)
    return G._wire_pin(pin, tag=CTRL_TAG)


def _leg_sources(pins: list[str]) -> list[str]:
    """Ideal sources for the shared schedule: every per-weight leg pin, plus
    `sel_in`/`tp_gn`, all `CTRL_TAG`-scoped -- one physical waveform driven
    once, read by every pair's `Xdut`. Waveforms are copied verbatim from
    `design/adc-top/gen_adc_top.py.dr14_netlist()`'s `vsmptp`/`vsmpbp`/
    `vnrel`/`vnrel256`/`vhi256`/`vlo256`.
    """
    L: list[str] = []
    a = L.append
    a("* ---- shared DR-0014 two-phase schedule (issue #89 Sec 6.3) ---------")
    a("* One physical schedule, broadcast onto every pair's Xdut via the")
    a("* SAME ctrl-tag ('d14') net names _wire_pin_for_pair() gives every")
    a("* pair for its shared (non-analog-I/O) pins -- see module docstring.")
    seen: set[str] = set()
    for pin in pins:
        net = _wire_pin_for_pair(pin, CTRL_TAG)
        if net in seen:
            continue
        seen.add(net)
        if pin == "sel_in":
            a(
                f"v{net} {net} 0 pulse({{vdd_val}} 0 {gtop.DR14_BP_FALL_NS:g}n"
                " 100p 100p 10u 20u)"
            )
        elif pin == "tp_gn":
            a(
                f"v{net} {net} 0 pulse({{vdd_val}} 0 {gtop.DR14_TP_FALL_NS:g}n"
                " 100p 100p 10u 20u)"
            )
        else:
            m = G._LEG_PIN.match(pin)
            if not m:
                continue  # vcm/vref/vss/vsubs/vdd -- driven by the rails below
            leg, w, s = m.group(1), int(m.group(2)), m.group(3)
            if w == 256:
                if leg == "rel":
                    a(
                        f"v{net} {net} 0 pwl(0 0 {gtop.DR14_BP_FALL_NS:g}n 0"
                        f" {gtop.DR14_BP_FALL_NS + 0.1:g}n {{vdd_val}}"
                        f" {gtop.DR14_TRIAL_NS:g}n {{vdd_val}}"
                        f" {gtop.DR14_TRIAL_NS + 0.1:g}n 0)"
                    )
                elif (leg == "hi" and s == "p") or (leg == "lo" and s == "n"):
                    a(
                        f"v{net} {net} 0 pulse(0 {{vdd_val}}"
                        f" {gtop.DR14_TRIAL_NS:g}n 100p 100p 10u 20u)"
                    )
                else:
                    a(f"v{net} {net} 0 dc 0")
            else:
                if leg == "rel":
                    a(
                        f"v{net} {net} 0 pulse(0 {{vdd_val}}"
                        f" {gtop.DR14_BP_FALL_NS:g}n 100p 100p 10u 20u)"
                    )
                else:
                    a(f"v{net} {net} 0 dc 0")
    return L


def _dr14_pair_extracted(
    tag: str, f: float, pins: list[str], top: str, dcpar_ff: float = 0.0
) -> list[str]:
    """One differential sampling pair, `Xdut`-wired -- the extracted
    equivalent of `design/adc-top/gen_adc_top.py._dr14_pair()`."""
    L: list[str] = []
    a = L.append
    a(
        f"* ---- pair {tag}: differential input f = {f:+.3f} x V_cm"
        + (f", +{dcpar_ff:g} fF on the p top plate" if dcpar_ff else "")
    )
    for s, scale in (("p", 1.0 + f), ("n", 1.0 - f)):
        a(f"v{tag}src{s} {tag}_src{s} 0 dc {{vcm*{scale!r}}}")
        a(f"R{tag}s{s} {tag}_src{s} {tag}_pin{s} {gtop.TRACK_RS_OHM}")
        a(f"C{tag}x{s} {tag}_pin{s} 0 {gtop.TRACK_CPIN}")
    dut_nets = [_wire_pin_for_pair(p, tag) for p in pins]
    L += sar._wrap(f"X{tag}dut", dut_nets + [top])
    if dcpar_ff:
        a(f"C{tag}dcpar {tag}_topp 0 {dcpar_ff:g}f")
    a(f"i{tag}b vddc {tag}_ib dc {{ibias}}")
    a(
        f"X{tag}cmp {tag}_topp {tag}_topn cmpstrobe {tag}_ib {tag}_do"
        f" {tag}_dob vddc 0 comparator"
    )
    a(f".nodeset v({tag}_do)=0 v({tag}_dob)={{vdd_val}}")
    a(f"b{tag}dp {tag}_dp 0 V = (v({tag}_topp)-vcm)/lsb")
    a(f"b{tag}dn {tag}_dn 0 V = (v({tag}_topn)-vcm)/lsb")
    a(f"b{tag}dd {tag}_dd 0 V = (v({tag}_topp)-v({tag}_topn))/lsb")
    a("")
    return L


def dr14_netlist_extracted(top: str = "ADC_TOP") -> tuple[str, list[str]]:
    """`(text, pins)` for the extracted-core Group A + Group C deck."""
    pins, core_text = G.core_pins(top)
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_dr0014_sampling_extracted -- issue #89 Sec 6.3: the DR-0012/13")
    a("* Gain-error-systematic row (Group A, terms 1+2 + sampling gain/INL)")
    a("* and the C_par-mismatch residue (Group C, term 4), against the")
    a("* PMOS-body-remediated, MiM-mapped EXTRACTED ADC_TOP core, on")
    a("* sim/dr0014-sampling/'s own schedule and LSB-referred formulas.")
    a("*")
    a("* GENERATED by")
    a("* layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py --")
    a("* do not edit.")
    a("*")
    a("* Group B (fourth-leg settling A/B) and Group D (isolated T-gate")
    a("* R_on) have no extracted equivalent -- see this generator's own")
    a("* module docstring for why -- and are not emitted here.")
    a("* ==================================================================")
    a("")
    a(".param vref={vdd_val}")
    a(".param vcm={vdd_val/2}")
    a(".param lsb={vdd_val/1024}")
    a(".param ibias=10u")
    a("")
    a("* ---- rails ---------------------------------------------------------")
    a("vddd vddd 0 dc {vdd_val}")
    a("vddc vddc 0 dc {vdd_val}")
    a("vrefs vrefn 0 dc {vref}")
    a("vcms vcmn 0 dc {vcm}")
    a("* Comparator strobe held LOW throughout, same rationale as the")
    a("* schematic deck: the latch is in reset/preamp-tracking while a DAC")
    a("* step settles; kickback on the strobe edge is sim/comparator-kickback/.")
    a("vcmpstrobe cmpstrobe 0 dc 0")
    a("")
    L += _leg_sources(pins)
    a("")
    a("* ==================================================================")
    a("* GROUP A -- terms 1 and 2, plus the sampling path's own gain/INL.")
    a("* Five differential pairs, identical schedule, differing input only.")
    a("* ==================================================================")
    for i, f in enumerate(gtop.DR14_LEVELS):
        L += _dr14_pair_extracted(f"a{i}", f, pins, top)
    a("* ==================================================================")
    a(
        "* GROUP C -- term 4, C_par-mismatch residue at Group A's level "
        f"{gtop.DR14_MIS_LEVEL} (f = {gtop.DR14_LEVELS[gtop.DR14_MIS_LEVEL]:+.3f});"
    )
    a(f"* a{gtop.DR14_MIS_LEVEL} above is the matched reference -- same input,")
    a("* same schedule, same deck.")
    a("* ==================================================================")
    for j, dc in enumerate(gtop.DR14_DCPAR_FF):
        L += _dr14_pair_extracted(
            f"c{j}", gtop.DR14_LEVELS[gtop.DR14_MIS_LEVEL], pins, top, dcpar_ff=dc
        )
    lib = gtop.comparator_block() + "\n" + core_text + "\n"
    return lib + "\n".join(L) + "\n", pins


OUT = (
    REPO
    / "sim"
    / "dr0014-sampling"
    / "testbench-extracted"
    / "tb_dr0014_sampling_extracted.spice"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--check", action="store_true", help="assert byte-identity with the committed file, write nothing"
    )
    args = ap.parse_args(argv)
    text, pins = dr14_netlist_extracted()
    if args.check:
        if not OUT.is_file():
            print(f"MISSING: {OUT}", file=sys.stderr)
            return 1
        if OUT.read_text() != text:
            print(f"STALE: {OUT} does not match the generator output", file=sys.stderr)
            return 1
        print(f"OK: {OUT} matches ({len(pins)} extracted-core pins/pair)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT} ({len(pins)} extracted-core pins/pair)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
