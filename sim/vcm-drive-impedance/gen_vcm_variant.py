#!/usr/bin/env python3
"""Emit a V_cm drive-impedance variant of the `sim/adc-inl-dnl/` deck.

Issue #260 asks whether the ideal, zero-impedance V_cm source every ADC-level
testbench in this repo uses (`sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice`:
`vcms vcmn 0 dc {vcm}`) is a conservative stand-in for a real external V_cm
pin, once `spec/decision-records/DR-0026-vcm-drive-source.md` derives that
pin's own drive-impedance / decoupling budget (the V_cm analogue of DR-0002's
`V_REF` budget). This script does NOT template or hand-patch the converter --
it patches only the one line the ideal V_cm source sits on, anchored on its
exact text so a hit-count assertion catches drift instead of silently patching
nothing (the same discipline `sim/dr0019-cu-sweep/gen_cu_variant.py` uses for
its own single-line substitution, `ACQ_LEG_LINE`).

The replacement models a real external V_cm pin exactly the way the SAME deck
already models V_REF (DR-0002): an ideal DC source behind a resistor R in
parallel with an inductor L, feeding a decoupling capacitor C_dec to ground.
R || L is DC-accurate (L shorts at DC, so there is no offset the derivation
never specified) and resistive at the switching band (L's impedance dominates
below the R-L corner, so R sets the AC impedance there) -- see
`sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice`'s `vrefs`/`rref`/`lref`/
`cref` block for the identical pattern this script re-derives for V_cm.  `L`
is picked so the R-L corner sits at the 16 MHz bit-clock (DR-0003), the same
choice that network makes (`R=240` / `L=2.3873u` -> corner = 240/(2*pi*
2.3873u) = 16.00 MHz, confirmed by `--verify-vref-corner`).

Zero impedance (Z_vcm = 0) is not a variant of this script at all: it is the
UNMODIFIED checked-in `tb_adc_inl_dnl.spice`, which is exactly the point --
every existing record already IS the "ideal source" data point.

Usage::

    python3 sim/vcm-drive-impedance/gen_vcm_variant.py \\
        --z-ohm 220 --c-dec-nf 40 --out /tmp/v.spice
    python3 sim/vcm-drive-impedance/gen_vcm_variant.py --verify-vref-corner

Stdlib only, like the rest of ``sim/``.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_DECK = REPO_ROOT / "sim" / "adc-inl-dnl" / "testbench" / "tb_adc_inl_dnl.spice"

#: The ideal V_cm source exactly as `sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice`
#: emits it. Anchored on the full line so a future edit to that deck breaks
#: this loudly instead of silently patching nothing.
VCM_LINE = "vcms vcmn 0 dc {vcm}"

#: DR-0003's bit clock: 16 x f_s at the ratified 1 MS/s rate. The V_REF
#: network's own R/L pair (240 ohm / 2.3873 uH) sits its R-L corner here --
#: `--verify-vref-corner` checks that identity so this script's L formula is
#: proven consistent with the checked-in V_REF network, not merely modelled
#: after it by eye.
BIT_CLOCK_HZ = 16.0e6

#: The checked-in V_REF network's own values, `sim/adc-enob-fft/testbench/
#: tb_adc_enob_fft.spice`: `rref vrefs vrefn 240` / `lref vrefs vrefn 2.3873u`.
VREF_R_OHM = 240.0
VREF_L_H = 2.3873e-6


def l_for_corner(r_ohm: float, corner_hz: float = BIT_CLOCK_HZ) -> float:
    """Inductor value putting the R-L parallel corner at `corner_hz`.

    At DC, L shorts the ideal source straight through (DC-accurate, no
    offset). At `corner_hz` and above, `omega * L >> R` so R sets the AC
    impedance -- the "switching band" DR-0002's own network targets.
    """
    return r_ohm / (2.0 * math.pi * corner_hz)


def variant_deck(z_ohm: float, c_dec_nf: float, corner_hz: float = BIT_CLOCK_HZ) -> str:
    """`tb_adc_inl_dnl.spice` with the ideal V_cm source replaced by a real
    R || L (source impedance) + C_dec (decoupling) network, DC-accurate and
    resistive at the switching band -- the V_cm analogue of DR-0002's V_REF
    network in the SAME deck (`vrefs`/`rref`/`lref`/`cref`, untouched here)."""
    text = BASELINE_DECK.read_text()
    hits = text.count(VCM_LINE)
    if hits != 1:
        raise SystemExit(
            f"expected exactly 1 occurrence of {VCM_LINE!r} in {BASELINE_DECK},"
            f" found {hits} -- the baseline deck has drifted, update VCM_LINE"
        )
    l_h = l_for_corner(z_ohm, corner_hz) if z_ohm > 0 else 0.0
    replacement = (
        "* ---- V_cm drive network, issue #260 / DR-0026 --------------------\n"
        "* Real external V_cm pin, modelled the SAME way this deck already\n"
        "* models V_REF (DR-0002, the 'vrefs'/'rref'/'lref'/'cref' block\n"
        "* above): an ideal DC source behind a resistor R in parallel with an\n"
        "* inductor L (DC-accurate, resistive at the switching band), feeding\n"
        f"* a decoupling capacitor C_dec to ground. Z_vcm = {z_ohm:g} ohm,\n"
        f"* C_dec = {c_dec_nf:g} nF, R-L corner = {corner_hz/1e6:g} MHz\n"
        "* (sim/vcm-drive-impedance/gen_vcm_variant.py, GENERATED -- do not\n"
        "* edit by hand).\n"
        "vcmi vcmi 0 dc {vcm}\n"
        f"rvcm vcmi vcmn {z_ohm:.6f}\n"
        f"lvcm vcmi vcmn {l_h:.9e}\n"
        f"cvcm vcmn 0 {c_dec_nf:.6f}n\n"
    )
    return text.replace(VCM_LINE, replacement.rstrip("\n"), 1)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--z-ohm", type=float, help="V_cm source impedance in ohms")
    p.add_argument("--c-dec-nf", type=float, help="V_cm decoupling capacitance in nF")
    p.add_argument(
        "--corner-hz", type=float, default=BIT_CLOCK_HZ,
        help="R-L parallel corner frequency (default: the 16 MHz bit clock)",
    )
    p.add_argument("--out", type=Path, help="output path for the variant deck")
    p.add_argument(
        "--verify-vref-corner", action="store_true",
        help="assert the checked-in V_REF network's own R-L corner is the "
        "16 MHz bit clock, then exit",
    )
    args = p.parse_args(argv)

    if args.verify_vref_corner:
        corner = VREF_R_OHM / (2.0 * math.pi * VREF_L_H)
        ok = math.isclose(corner, BIT_CLOCK_HZ, rel_tol=1e-3)
        print(f"V_REF network R-L corner: {corner/1e6:.4f} MHz "
              f"(bit clock: {BIT_CLOCK_HZ/1e6:.4f} MHz) -> "
              f"{'OK' if ok else 'MISMATCH'}")
        return 0 if ok else 1

    if args.z_ohm is None or args.c_dec_nf is None or args.out is None:
        p.error("--z-ohm, --c-dec-nf and --out are required unless "
                 "--verify-vref-corner is given")

    deck = variant_deck(args.z_ohm, args.c_dec_nf, args.corner_hz)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(deck)
    print(f"wrote {args.out} (Z_vcm={args.z_ohm:g} ohm, "
          f"C_dec={args.c_dec_nf:g} nF, corner={args.corner_hz/1e6:g} MHz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
