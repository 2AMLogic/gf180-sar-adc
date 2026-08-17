#!/usr/bin/env python3
"""Emit one C_u variant of the `sim/adc-enob-fft/` deck.

Issue #211 asks for a *controlled isolation*: hold everything else fixed and
move only the CDAC unit capacitance, so SFDR/ENOB can be watched moving
continuously instead of being inferred from the single before/after pair
DR-0019 left behind.  "Everything else fixed" is only credible if the variant
decks come out of **the same generator** the ratified deck does, so this
script does not template or patch SPICE text for the C_u axis: it imports
``design/adc-top/gen_adc_top.py``, rebinds the one module constant
``C_UNIT_FF``, and calls ``fft_deck()``.  Every downstream consequence of a
different C_u -- the nine per-block MiM square sides, the published
``512 * C_u`` capacitance in the deck's own comments -- is then recomputed by
the ratified code path rather than by this file's idea of it.

Self-check, asserted rather than assumed: run at the ratified
``C_u = 35.6528 fF`` with no switch scaling, the emitted text must be
byte-identical to the checked-in
``sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice`` (``--verify-baseline``,
and ``sim/tests/test_cu_sweep_variant.py`` asserts it in CI).  That is what
makes "the only difference is C_u" a checked statement.

THE ONE THING THIS SCRIPT DOES PATCH, AND WHY.  ``--acq-switch-scale`` widens
**only** the CDAC cell's fourth leg -- the ``Xsi`` T-gate DR-0014 made the
input's path into the array -- leaving the release/V_REF/GND legs at the
ratified 10u/20u.  ``gen_adc_top.py`` sizes all four legs from one pair of
constants, so there is no constant to rebind for "the input leg only"; the
substitution below is anchored on the exact emitted line and asserts its own
hit count.  This leg is the orthogonal control the isolation needs: growing
C_u scales the acquisition time constant ``R_on(V_in) * C_arr`` AND the charge
the array draws from V_REF AND the ``C_arr/(C_arr + C_par)`` divider, all at
once.  Widening the input leg alone moves the FIRST of those three and
nothing else, so a point taken at the ratified C_u with the switch widened by
the same factor C_u grew tells the RC hypothesis apart from its two
confounds.

Usage::

    python3 sim/dr0019-cu-sweep/gen_cu_variant.py --c-unit-ff 22.0 --out /tmp/v.spice
    python3 sim/dr0019-cu-sweep/gen_cu_variant.py --verify-baseline

Stdlib only, like the rest of ``sim/``.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "design" / "adc-top" / "gen_adc_top.py"
BASELINE_DECK = REPO_ROOT / "sim" / "adc-enob-fft" / "testbench" / "tb_adc_enob_fft.spice"

#: DR-0019's own two endpoints, in fF.  ``spec/cdac-sizing-memo.md`` Sec 4/5.2.
C_UNIT_PRE_RESIZE_FF = 17.24
C_UNIT_RATIFIED_FF = 35.6528

#: The fourth leg exactly as ``gen_adc_top.py`` emits it (line 298).  Anchored
#: on the full line so a generator edit breaks this loudly instead of silently
#: patching nothing.
ACQ_LEG_LINE = "Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn=10u wp=20u"


def load_generator():
    """Import ``design/adc-top/gen_adc_top.py`` as a module.

    It lives outside any package and its directory name (`adc-top`) is not a
    legal identifier, so it is loaded by path rather than imported by name.
    """
    sys.path.insert(0, str(GENERATOR.parent))
    spec = importlib.util.spec_from_file_location("gen_adc_top_cu_sweep", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def variant_deck(c_unit_ff: float, acq_switch_scale: float = 1.0) -> str:
    """The FFT deck at ``c_unit_ff``, optionally with a widened input leg."""
    gen = load_generator()
    gen.C_UNIT_FF = float(c_unit_ff)
    deck = gen.fft_deck()

    if acq_switch_scale != 1.0:
        if deck.count(ACQ_LEG_LINE) != 1:
            raise SystemExit(
                f"error: expected exactly one {ACQ_LEG_LINE!r} in the generated "
                f"deck, found {deck.count(ACQ_LEG_LINE)} -- gen_adc_top.py's "
                "cell emission has changed and this substitution is no longer "
                "anchored"
            )
        wn = float(gen.CDAC_SW_WN.rstrip("u")) * acq_switch_scale
        wp = float(gen.CDAC_SW_WP.rstrip("u")) * acq_switch_scale
        deck = deck.replace(
            ACQ_LEG_LINE,
            f"Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn={wn:.4f}u wp={wp:.4f}u",
        )
    return deck


def _verify_baseline() -> int:
    deck = variant_deck(C_UNIT_RATIFIED_FF)
    disk = BASELINE_DECK.read_text()
    if deck != disk:
        print(
            "FAIL: the generator run at the ratified C_u does NOT reproduce\n"
            f"      {BASELINE_DECK}\n"
            "      -- the sweep's 'only C_u moved' claim is not supported.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: C_u = {C_UNIT_RATIFIED_FF} fF reproduces {BASELINE_DECK.name} byte-for-byte")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--c-unit-ff", type=float, help="unit capacitance for this variant, in fF")
    p.add_argument("--out", type=Path, help="where to write the deck (default: stdout)")
    p.add_argument(
        "--acq-switch-scale",
        type=float,
        default=1.0,
        help="multiply the CDAC cell's FOURTH-LEG (input/acquisition) T-gate "
        "width by this factor, leaving the other three legs ratified. 1.0 "
        "(default) emits the ratified geometry.",
    )
    p.add_argument(
        "--verify-baseline",
        action="store_true",
        help="assert the generator at the ratified C_u reproduces the "
        "checked-in adc-enob-fft deck byte-for-byte, and exit",
    )
    args = p.parse_args(argv)

    if args.verify_baseline:
        return _verify_baseline()
    if args.c_unit_ff is None:
        p.error("--c-unit-ff is required (or pass --verify-baseline)")

    deck = variant_deck(args.c_unit_ff, args.acq_switch_scale)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(deck)
        print(f"wrote {args.out}  (C_u = {args.c_unit_ff} fF, "
              f"acq switch x{args.acq_switch_scale:g})")
    else:
        sys.stdout.write(deck)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
