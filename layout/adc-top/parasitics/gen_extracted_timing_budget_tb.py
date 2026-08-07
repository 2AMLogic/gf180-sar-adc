#!/usr/bin/env python3
"""Issue #12's conversion-timing-budget deck, re-composed with the settling
network's **post-layout** R and C.

    python3 layout/adc-top/parasitics/gen_extracted_timing_budget_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_timing_budget_tb.py --check

Writes ONE file:

    sim/timing-budget-closure/testbench/tb_timing_budget_closure_extracted.spice

into the SAME experiment directory as the schematic-level deck, per
`sim/README.md` "Extracted vs schematic semantics", and deliberately does NOT
write a second `tb.json`: the run is

    python3 sim/run_corners.py timing-budget-closure \\
        --netlist sim/timing-budget-closure/testbench/tb_timing_budget_closure_extracted.spice \\
        --netlist-provenance 'extracted (...)'

i.e. the UNMODIFIED manifest -- same analyses, same `meas` expressions, same
checks, same ratified pass/fail thresholds. Nothing about the spec moves.

## What is post-layout here, and what is NOT

Issue #12's closed-loop budget consumes exactly three numbers
(`design/sar-logic/gen_sar_logic.py`):

| input | schematic | this deck | post-layout? |
|---|---|---|---|
| `R_WORST_BIT_OHM` | 570 Ω | **648 Ω** | **yes** |
| `C_WORST_BIT_F` | 2.20672 pF | **2.40712 pF** | **yes** |
| `T_COMP_REGEN_NS` | 0.863 ns | 0.863 ns | **NO -- still schematic** |

so this deck is **two thirds post-layout, and says so** rather than being
labelled "extracted" as though all three had moved. Per CLAUDE.md's
no-relaxation rule, a schematic number relabelled as an extracted one is
exactly what must not happen; the honest form is to state which input is
which, and that is what this module and the record it feeds do.

**`R_WORST_BIT_OHM` = 648 Ω** -- `ron_t_max` at `ss_125c_2.97v`, the worst
cell of the 45 point PVT grid in
`sim/device-switch-ron/records/20260806-194322-68ad582.md`, measured against
the extracted `adc_tgate` leaf at the `875eac3` toolchain pin (647.818 Ω,
rounded up). The schematic number it replaces, 570 Ω, is `ron_t_max` at the
SAME corner from the same deck's schematic run -- so the two are like-for-
like and the +78 Ω delta is the drawn cell's own in-path interconnect,
which no earlier pin could express (every prior extracted run measured a
delta of exactly zero; `records/20260806-parasitic-topology.md`).

**`C_WORST_BIT_F` = 2.40712 pF** -- the schematic's 2.20672 pF
(`Ceq(w=256) = 128 * C_u`, `spec/cdac-sizing-memo.md` §5.3) PLUS 200.4 fF of
extracted top-plate parasitic capacitance, the `topp` net's own extracted C
in `layout/adc-top/parasitics/reports/20260806-193910-68ad582/adc_top.para.spice`
(the worse of the two sides; `topn` is 189.7 fF). The unit capacitor itself
needs no correction any more: at this pin the deck's MiM model is the PDK
model card's own two-term area+fringe formula (`klayout-tools#512`), so the
extracted unit cap is 17.2449 fF against the 17.24 fF the schematic figure
was derived from -- agreement to the drawn-geometry rounding, where every
earlier pin was 14.6 % low.

**`T_COMP_REGEN_NS` is NOT post-layout, and cannot be yet.** It needs a
worst-corner regeneration measurement against the comparator-inclusive
extracted core (`ADC_BLOCK`). Issue #118 closed the functional blocker
that used to prevent that measurement -- the preamp's load resistors now
extract as real `ppolyf_u_1k` devices instead of shorting -- and
`ADC_BLOCK` **converts**
(`records/20260806-adc-block-resistor-markers-pass.md`). Two gaps remain,
neither closed by #118: `2AMLogic/klayout-tools#595` is still open, now
tracking only the extraction deck's `ppolyf_u_1k`-vs-`ppolyf_u_2k`
sheet-rho selection rather than a device short; and the comparator-
inclusive Monte Carlo/regeneration campaign itself has not been run yet
(issue #89 Scope item 2). Until that campaign lands, this input stays at
#9's schematic-level 0.863 ns and this deck is explicitly not the "fully
post-layout rate closure" issue #17's AC7 asks for.

## The `.save`, and why its reason here is NOT the other decks' reason

`gen_extracted_core_tb.saved_vectors_lines()` (PR #130, issue #123) emits a
`.save` naming exactly the vectors a deck's manifest reads -- derived from
the manifest, never hand-listed. Issue #131 brought this deck under that
treatment too, but the reason it needs one is a different one, and the
emitted comment block says so rather than repeating the ADC decks' text.

In `gen_extracted_{inl_dnl,enob_fft,power,dr0014_sampling}_tb.py` the cause
is node COUNT: the star-split in-path extraction (`klayout-tools#593`, the
`875eac3` pin) gives every device terminal on a net its own leg node, so the
full-node store overruns what ngspice will allocate. **That cause does not
apply here** -- this deck wraps no extracted core at all. What is post-layout
about it is two SCALAR component values (the table above); the netlist is
`gen_sar_logic.budget_closure()`'s own schematic text with those two values
substituted, one lumped R and one lumped C per loop, rung-1 XSPICE digital,
zero parasitic elements.

The cause here is transient LENGTH across eight parallel loops: `tb.json`'s
`tran 5n 8.55u 0 5n` runs 8.55 us over eight full SAR loops' worth of nodes
(11 634 data rows), and ngspice keeps a waveform per node per step either
way. Measured on `tt_27c_3.30v` with `/usr/bin/time -l ngspice -b` against
the harness-composed point (issue #131, ngspice-46, `num_threads=1`, two
runs each): **241.2 / 241.4 MB peak RSS without the `.save`, 32.8 / 32.6 MB
with it** -- a 7.4x cut.

Stated honestly: this deck **did not fail** without the `.save`, on this
host, at one point at a time. What it did was sit within a factor of ~1.1 of
the 260.8 MB store PR #130's INL/DNL deck was refused outright, on a
threshold that is the OS's *available* memory rather than a fixed ngspice
cap -- so it collapses as concurrent `-j` points allocate. The claim being
made here is therefore "one busy host away from a load-dependent,
comes-and-goes failure", not "it cannot run"; the line is worth having on
those merits without borrowing the extraction's stronger rationale, which
would be an overstatement in this deck.

**It cannot move a number**, and that was checked on this deck rather than
inferred from PR #130's check on another one: the same `tt_27c_3.30v` point
run with and without the `.save` returns all eight measurements bit-identical
(`aerr_r1_l55 = 2.55000e+02 at= 4.00256e-06`, and so on for the other seven).
`.save` selects which waveforms are RETAINED; it touches no model, tolerance
or timestep.

This does mean the deck now differs from the committed schematic-level
`tb_timing_budget_closure.spice` in one more line than the two component
values -- `_header()` below states that, rather than keeping its previous
"and in nothing else" wording, because the whole point of that sentence is
that a reader can trust it literally.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import gen_extracted_core_tb as G  # noqa: E402  (same directory)

_GEN_SAR = REPO / "design" / "sar-logic" / "gen_sar_logic.py"
_spec = importlib.util.spec_from_file_location("gen_sar_logic", _GEN_SAR)
gsar = importlib.util.module_from_spec(_spec)
sys.modules["gen_sar_logic"] = gsar
_spec.loader.exec_module(gsar)  # type: ignore[union-attr]

OUT = REPO / "sim" / "timing-budget-closure" / "testbench" / \
    "tb_timing_budget_closure_extracted.spice"

#: The manifest this deck runs under -- the UNMODIFIED schematic-level one, in
#: the same testbench directory (see the module docstring's opening). Committed
#: JSON with no Python emitter, so it is read from disk; still the same object
#: the run uses, so the derived `.save` cannot drift from it.
MANIFEST = REPO / "sim" / "timing-budget-closure" / "testbench" / "tb.json"

#: This deck's OWN reason for carrying a `.save` -- transient length across
#: eight loops, not the ADC decks' extracted-node count. Passed to
#: `gen_extracted_core_tb.saved_vectors_lines()` in place of its default text,
#: which would be untrue of this deck. See the module docstring for the
#: measured before/after and the bit-identity check.
SAVE_RATIONALE = (
    "* ngspice keeps a transient waveform for EVERY node unless told which",
    "* ones matter. This deck carries NO extracted core, so the sim/adc-*",
    "* decks' leg-node explanation does not apply -- what costs memory here",
    "* is 8.55 us of transient across eight parallel SAR loops. Measured at",
    "* tt_27c_3.30v: 241.2 MB peak RSS without this line, 32.8 MB with it,",
    "* 7.4x. It did NOT fail without it on a quiet host -- the honest claim",
    "* is that 241 MB sits within ~1.1x of the 260.8 MB store PR #130's",
    "* INL/DNL deck was refused, against a threshold that is the OS's free",
    "* memory and so falls as concurrent -j points allocate. These are",
    "* exactly the vectors",
    "* sim/timing-budget-closure/testbench/tb.json reads, derived from it",
    "* rather than hand-listed. Retention only: no model, tolerance or",
    "* timestep changes, and all eight measurements are bit-identical with",
    "* and without it. See gen_extracted_core_tb.saved_vectors_lines.",
)

#: Post-layout worst-corner T-gate R_on. See this module's docstring.
R_WORST_BIT_OHM_EXTRACTED = "648"
R_ON_SOURCE_RECORD = "sim/device-switch-ron/records/20260806-194322-68ad582.md"
R_ON_MEASURED_OHM = 647.818

#: Post-layout worst-side bit-trial load. See this module's docstring.
C_WORST_BIT_F_EXTRACTED = "2.40712p"
C_TOPPLATE_PARASITIC_FF = 200.4
C_EXTRACTION_RECORD = "layout/adc-top/parasitics/records/20260806-193910-68ad582.md"


def _header() -> list[str]:
    return [
        "* ==================================================================",
        "* tb_timing_budget_closure_extracted -- issue #12's conversion timing",
        "* budget, re-composed with the settling network's POST-LAYOUT R and C.",
        "*",
        "* GENERATED by layout/adc-top/parasitics/gen_extracted_timing_budget_tb.py",
        "* -- do not edit. Run it, or `--check` it, instead.",
        "*",
        "* This deck differs from the committed schematic-level",
        "* tb_timing_budget_closure.spice in the settling network's two component",
        "* values and in NOTHING ELSE THAT CAN MOVE A NUMBER -- same loops, same",
        "* rates, same candidate logic delays, same measurement points, same",
        "* manifest. (The one other textual difference is the retained-waveform",
        "* .save below, added by issue #131; it selects which waveforms ngspice",
        "* keeps, and all eight measurements are bit-identical with and without",
        "* it -- see gen_extracted_timing_budget_tb.py's module docstring.)",
        "*",
        f"*   R_WORST_BIT_OHM  {gsar.R_WORST_BIT_OHM} -> "
        f"{R_WORST_BIT_OHM_EXTRACTED} ohm   POST-LAYOUT",
        f"*     ron_t_max at ss_125c_2.97v ({R_ON_MEASURED_OHM} ohm, rounded up)",
        f"*     against the extracted adc_tgate leaf at the 875eac3 pin --",
        f"*     {R_ON_SOURCE_RECORD}",
        f"*   C_WORST_BIT_F    {gsar.C_WORST_BIT_F} -> "
        f"{C_WORST_BIT_F_EXTRACTED}    POST-LAYOUT",
        f"*     the schematic Ceq(w=256) plus {C_TOPPLATE_PARASITIC_FF} fF of",
        "*     extracted top-plate parasitic C (the worse of topp/topn) --",
        f"*     {C_EXTRACTION_RECORD}",
        f"*   T_COMP_REGEN_NS  {gsar.T_COMP_REGEN_NS} ns, UNCHANGED -- STILL",
        "*     SCHEMATIC-LEVEL. ADC_BLOCK converts (issue #118 fixed the",
        "*     resistor-marker gap that used to block this measurement); the",
        "*     comparator-inclusive Monte Carlo/regeneration campaign itself",
        "*     has not been run yet (issue #89 Scope item 2), and",
        "*     2AMLogic/klayout-tools#595 (sheet-rho selection) is still",
        "*     open. This deck is therefore TWO THIRDS post-layout and must",
        "*     not be recorded as more than that.",
        "* ==================================================================",
        "*",
    ]


def netlist() -> str:
    """The schematic deck's own text with the two settling values swapped.

    Textual substitution against `gen_sar_logic`'s own emitter output, NOT a
    re-derivation: the whole point is that everything except the two component
    values is byte-identical to the deck the ratified schematic-level record
    was taken against, so a delta between the two runs can only come from
    those two values.
    """
    base = gsar.budget_closure()
    r_old, c_old = gsar.R_WORST_BIT_OHM, gsar.C_WORST_BIT_F
    n_r = base.count(f" {r_old}\n")
    n_c = base.count(f" {c_old}\n")
    if n_r == 0 or n_c == 0:
        raise RuntimeError(
            "could not find the settling network's R/C cards in "
            "gen_sar_logic.budget_closure() output -- refusing "
            f"to emit a deck that silently kept the schematic values "
            f"(found {n_r} R, {n_c} C)"
        )
    if n_r != n_c:
        raise RuntimeError(
            f"settling R and C card counts disagree ({n_r} vs {n_c}) -- the "
            "deck's shape changed; re-read it before substituting."
        )
    body = base.replace(f" {r_old}\n", f" {R_WORST_BIT_OHM_EXTRACTED}\n")
    body = body.replace(f" {c_old}\n", f" {C_WORST_BIT_F_EXTRACTED}\n")
    saved = G.saved_vectors_lines(
        json.loads(MANIFEST.read_text()), rationale=SAVE_RATIONALE
    )
    return (
        "\n".join(_header()) + "\n" + "\n".join(saved) + "\n\n" + body
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true",
                    help="assert the committed file matches, write nothing")
    args = ap.parse_args(argv)

    text = netlist()
    rel = OUT.relative_to(REPO)
    if args.check:
        if not OUT.exists():
            print(f"MISSING    {rel}", file=sys.stderr)
            return 1
        if OUT.read_text() != text:
            print(f"STALE      {rel} -- re-run without --check", file=sys.stderr)
            return 1
        print(f"up to date {rel}")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"  wrote      {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
