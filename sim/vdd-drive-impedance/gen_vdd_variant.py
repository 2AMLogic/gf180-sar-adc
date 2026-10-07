#!/usr/bin/env python3
"""Emit a V_DD drive-network variant of any deck that carries the ideal
V_DD island sources.

Issue #393 asks what DR-0036's `V_DD` drive budget -- external decoupling
`C_dec >= 40 nF` at the V_DD pin and an effective source impedance
`Z_vdd <= 3 ohm` in the switching band
(`spec/decision-records/DR-0036-vdd-decoupling-budget.md`) -- buys the
converter, and what missing it costs the ratified rows. Every ADC-level deck
in this repo sources its supply islands from ideal, zero-impedance DC
sources::

    vddt vddt 0 dc {vdd_val}     <- track / top-plate switch island
    vddd vddd 0 dc {vdd_val}     <- CDAC bottom-plate drivers
    vddc vddc 0 dc {vdd_val}     <- comparator

This script is the V_DD counterpart of
`sim/vcm-drive-impedance/gen_vcm_variant.py` (issue #260 / #358, DR-0026):
it does NOT template or hand-patch the converter, it replaces only the
island-source lines, each anchored on its exact text with a hit-count
assertion, so a drifted deck is a loud `SystemExit` rather than a silently
unpatched copy.

ONE PIN, NOT THREE ISLANDS (the modelling decision, issue #393)
---------------------------------------------------------------
DR-0036 budgets ONE physical `V_DD` pin, derived from the SUM
`i(vddc)+i(vddd)+i(vddt)` (`sim/adc-rail-current/`), and the drawn layout
has ONE supply rail: the extracted `.SUBCKT ADC_TOP` exposes a single `vdd`
pin (see `sim/adc-power/testbench/tb_adc_power_extracted.spice`'s header).
The three islands are a testbench *instrumentation* split -- one ammeter per
block -- not three package pins. So the variant builds ONE network and feeds
all the islands from it::

    vddsup  vdd_ext 0        dc {vdd_val}   ideal supply behind the pin
    rvddpin vdd_ext vdd_pin  Z              R || L : the source impedance
    lvddpin vdd_ext vdd_pin  L
    cvddpin vdd_pin 0        C_dec          the external decoupling at the pin
    vddt    vddt    vdd_pin  dc 0           } 0 V ammeters, one per island,
    vddd    vddd    vdd_pin  dc 0           } so every i(vddX) the manifests
    vddc    vddc    vdd_pin  dc 0           } measure keeps its name AND sign

Patching each island with its own 40 nF / 3 ohm network would model three
independent off-chip pins: 3 x 40 nF of decoupling and three 3 ohm sources
in parallel (1 ohm effective) -- i.e. it would silently grade the converter
against 3x the decoupling and 1/3 the impedance DR-0036 actually budgets,
and it would hide the one physically real cross-coupling a shared pin has
(the CDAC drivers' switching sag landing on the comparator's supply). The
shared network is therefore the conservative AND the faithful choice.

What the shared node does NOT model, stated rather than implied: there is no
package inductance (this repo has no package model -- DR-0036 open question
2) and no on-die rail resistance between the pin and each island (the
`layout/power/` flow's domain; DR-0036 step 8). Both would make the real
supply WORSE than this network, so a clean result here is a statement about
the external budget alone, not about the block as integrated. Nor is there
any on-die decoupling -- DR-0036 clause 3 requires one and the block as drawn
has none, so this models the block as drawn.

AMMETER SIGN CONVENTION (issue #395's lesson, applied up front)
---------------------------------------------------------------
ngspice reports `i(vsrc)` as the current INTO the source's POSITIVE terminal,
so a source delivering current reads negative
(`sim/adc-rail-current/testbench/tb.json`). Each baseline line puts its `+`
terminal on the ISLAND node (`vddX vddX 0 ...`); each ammeter does the same
(`vddX vddX vdd_pin dc 0`), so `i(vddX)` keeps the sign every
`sim/adc-power/testbench/tb.json` `p_*` expression derives on. Unlike
`gen_vcm_variant.py`, the ammeters are emitted unconditionally: the island
names are what keep the per-block instrumentation alive, and there are no
previously-minted variant hashes to preserve.

WHERE THE R || L CORNER SITS, AND WHY IT IS NOT THE BIT CLOCK
-------------------------------------------------------------
DR-0002 (V_REF) and DR-0026 (V_cm) apply their settling convention to the
62.5 ns BIT cycle, so their networks put the R-L corner at the 16 MHz bit
clock. DR-0036 step 5 applies the same convention to the 1 us CONVERSION
period instead (`tau_max = 1 us / ln(2^11)`, `Z_vdd,max = tau_max / C_dec`):
the V_DD transient is once per conversion and the decoupling has to be
recharged between conversions. The "switching band" in which `Z_vdd <= 3 ohm`
must hold therefore starts at the 1 MHz conversion rate, so this script puts
the corner there (`L = R / (2 pi f_s)`). That is also the PESSIMISTIC
choice: above the corner the network looks like R, below it like the
smaller `omega L`, so a lower corner keeps the full 3 ohm across more of the
band -- at the recharge frequency `1/(2 pi Z C_dec)` ~ 1.3 MHz this network
presents ~2.4 ohm, where a 16 MHz corner would present ~0.25 ohm and grade
the converter against a source ~10x stiffer than the budget. It also damps
the L-C_dec resonance (Q ~ 0.87 at a 1 MHz corner vs ~3.5 at 16 MHz), so
the network does not ring at a frequency the decks would mistake for
signal. `--corner-hz` overrides it.

L shorts at DC, so the DC operating point is identical to the ideal arm --
the paired difference is the network's DYNAMIC behaviour and nothing else
(a pure 3 ohm R would add a 0.12 mV DC drop at the rail's 40 uA average,
DR-0036 step 5, which the ratified +/-10 % supply window already spans).

Usage::

    python3 sim/vdd-drive-impedance/gen_vdd_variant.py \\
        --deck sim/adc-power/testbench/tb_adc_power.spice \\
        --z-ohm 3 --c-dec-nf 40 --out /tmp/p.spice

Stdlib only, like the rest of ``sim/``.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The three ideal island sources, exactly as every ADC-level deck spells
#: them. Anchored on the full line so an edit to a deck breaks this loudly.
ISLANDS = ("vddt", "vddd", "vddc")


def island_line(name: str) -> str:
    """The ideal source line for island `name`, as the decks spell it."""
    return f"{name} {name} 0 dc {{vdd_val}}"


#: Which islands each known target deck carries. A deck listed here must
#: carry EXACTLY these island lines, once each -- a deck that loses one, or
#: grows one, fails loudly. A deck not listed here must carry all three
#: (the schematic decks' convention). `sim/dr0014-sampling/`'s extracted deck
#: carries two because the extracted ADC_TOP core exposes one `vdd` pin and
#: its generator wires no `vddt` island at all
#: (layout/adc-top/parasitics/gen_extracted_dr0014_sampling_tb.py).
EXPECTED_ISLANDS: dict[str, tuple[str, ...]] = {
    "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice": ISLANDS,
    "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice": ISLANDS,
    "sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice": ISLANDS,
    "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice": ISLANDS,
    "sim/adc-power/testbench/tb_adc_power.spice": ISLANDS,
    "sim/adc-power/testbench/tb_adc_power_extracted.spice": ISLANDS,
    "sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice": ISLANDS,
    "sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice":
        ("vddd", "vddc"),
}

#: DR-0003's conversion rate at the ratified 1 MS/s: 16 bit clocks x 62.5 ns
#: = 1 us. DR-0036 step 5 sets Z_vdd,max against this period, so the R-L
#: corner sits here (see the module docstring).
CONVERSION_RATE_HZ = 1.0e6

#: DR-0036's provisioned budget: Z_vdd <= 3 ohm, C_dec >= 40 nF. The variant
#: is built at the pessimistic EDGE of that envelope (largest Z, smallest C).
BUDGET_Z_OHM = 3.0
BUDGET_C_DEC_NF = 40.0

#: Element / node names the network introduces. Checked against each deck
#: before patching, so a collision is a loud failure, not a silent short.
NEW_NAMES = ("vddsup", "rvddpin", "lvddpin", "cvddpin", "vdd_ext", "vdd_pin")


def l_for_corner(r_ohm: float, corner_hz: float = CONVERSION_RATE_HZ) -> float:
    """Inductor value putting the R-L parallel corner at `corner_hz`.

    At DC, L shorts the ideal source straight through (DC-accurate). Above
    `corner_hz`, `omega * L > R` so R sets the source impedance -- the
    switching band DR-0036 step 5 budgets.
    """
    return r_ohm / (2.0 * math.pi * corner_hz)


def _repo_relative(path: Path) -> str:
    """`path` relative to the repo root when it is inside it, else as given."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def expected_islands(deck: Path) -> tuple[str, ...]:
    return EXPECTED_ISLANDS.get(_repo_relative(deck), ISLANDS)


def variant_deck(
    z_ohm: float,
    c_dec_nf: float,
    deck: Path,
    corner_hz: float = CONVERSION_RATE_HZ,
) -> str:
    """`deck` with its ideal V_DD island sources replaced by ONE shared
    R || L + C_dec pin network, each island kept alive as a 0 V ammeter.

    The network block is emitted where the FIRST island line sat; every
    island line (that one included) becomes that island's ammeter in place.
    Nothing else in the deck moves.
    """
    deck = Path(deck)
    if not deck.is_file():
        raise SystemExit(f"--deck {deck} does not exist")
    if z_ohm <= 0 or c_dec_nf <= 0:
        raise SystemExit(
            "--z-ohm and --c-dec-nf must be > 0: the ideal-supply arm is the "
            "UNMODIFIED committed deck, not a zero-impedance variant of it")
    text = deck.read_text()
    want = expected_islands(deck)

    for name in ISLANDS:
        hits = text.count(island_line(name))
        expected = 1 if name in want else 0
        if hits != expected:
            raise SystemExit(
                f"expected {expected} occurrence(s) of {island_line(name)!r} "
                f"in {_repo_relative(deck)}, found {hits} -- the deck has "
                f"drifted, or it does not source V_DD from ideal island "
                f"supplies at all; update EXPECTED_ISLANDS or pick a "
                f"different --deck")

    lowered = text.lower()
    for name in NEW_NAMES:
        # Whole-token match: `vdd_pin` must not collide, `vdd_pinx` may.
        for line in lowered.splitlines():
            if name in line.replace("(", " ").replace(")", " ").split():
                raise SystemExit(
                    f"{_repo_relative(deck)} already uses the name {name!r}, "
                    f"which the V_DD network would introduce")

    l_h = l_for_corner(z_ohm, corner_hz)
    first = min(want, key=lambda n: text.index(island_line(n)))

    network = (
        "* ---- V_DD drive network, issue #393 / DR-0036 --------------------\n"
        "* ONE external V_DD pin feeding every supply island, modelled after\n"
        "* DR-0002's V_REF / DR-0026's V_cm networks: an ideal DC source\n"
        "* behind a resistor R in parallel with an inductor L (DC-accurate,\n"
        "* resistive in the switching band), feeding a decoupling capacitor\n"
        "* C_dec to ground at the pin. One pin, not one network per island:\n"
        "* DR-0036 budgets a single pin off the summed island current.\n"
        f"* Z_vdd = {z_ohm:g} ohm, C_dec = {c_dec_nf:g} nF, R-L corner = "
        f"{corner_hz/1e6:g} MHz\n"
        "* (the conversion rate DR-0036 step 5 settles against).\n"
        "* No package L, no on-die rail R, no on-die decap: the external\n"
        "* budget alone (sim/vdd-full-pvt/README.md).\n"
        f"* Source deck: {_repo_relative(deck)}\n"
        "* (sim/vdd-drive-impedance/gen_vdd_variant.py, GENERATED -- do not\n"
        "* edit by hand).\n"
        "vddsup vdd_ext 0 dc {vdd_val}\n"
        f"rvddpin vdd_ext vdd_pin {z_ohm:.6f}\n"
        f"lvddpin vdd_ext vdd_pin {l_h:.9e}\n"
        f"cvddpin vdd_pin 0 {c_dec_nf:.6f}n\n"
        "* Each island survives as a 0 V ammeter, '+' on the island node like\n"
        "* the ideal line it replaces, so i(vddX) keeps name AND sign.\n"
    )

    out = text
    for name in want:
        ammeter = f"{name} {name} vdd_pin dc 0"
        if name == first:
            ammeter = network + ammeter
        out = out.replace(island_line(name), ammeter, 1)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deck", type=Path, required=True,
                   help="baseline deck to patch (any deck carrying the ideal "
                        "V_DD island source lines)")
    p.add_argument("--z-ohm", type=float, default=BUDGET_Z_OHM,
                   help=f"V_DD source impedance in ohms (default: DR-0036's "
                        f"{BUDGET_Z_OHM:g})")
    p.add_argument("--c-dec-nf", type=float, default=BUDGET_C_DEC_NF,
                   help=f"V_DD pin decoupling in nF (default: DR-0036's "
                        f"{BUDGET_C_DEC_NF:g})")
    p.add_argument("--corner-hz", type=float, default=CONVERSION_RATE_HZ,
                   help="R-L parallel corner (default: the 1 MHz conversion "
                        "rate, DR-0036 step 5)")
    p.add_argument("--out", type=Path, required=True,
                   help="output path for the variant deck")
    args = p.parse_args(argv)

    text = variant_deck(args.z_ohm, args.c_dec_nf, args.deck, args.corner_hz)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"wrote {args.out} from {_repo_relative(args.deck)} "
          f"(Z_vdd={args.z_ohm:g} ohm, C_dec={args.c_dec_nf:g} nF, "
          f"corner={args.corner_hz/1e6:g} MHz, "
          f"islands={','.join(expected_islands(args.deck))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
