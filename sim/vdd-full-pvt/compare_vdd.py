#!/usr/bin/env python3
"""Paired difference between two `sim/` corner-matrix records -- the V_DD
counterpart of `sim/vcm-full-pvt/compare_vcm.py` (issue #393).

Each ratified-row-owning deck is run twice at the same commit -- once with the
ideal, zero-impedance V_DD island sources every existing record in this suite
assumes, once with DR-0036's real V_DD pin network
(`sim/vdd-drive-impedance/gen_vdd_variant.py`) -- so the difference is
attributable to the V_DD network and nothing else. The arithmetic is
`compare_vcm.compare`'s, imported rather than copied: every value printed is
read out of the two records' own per-point tables, and every bound out of the
deck's own manifest `checks` block.

    python3 sim/vdd-full-pvt/compare_vdd.py \\
        --experiment adc-inl-dnl \\
        --ideal  sim/adc-inl-dnl/records/<ideal-id>.md \\
        --vddnet sim/adc-inl-dnl/records/<vddnet-id>.md

For a deck whose manifest is not `sim/<experiment>/testbench/tb.json` -- the
governing extracted `dr0014-sampling` deck lives in
`sim/dr0014-sampling/testbench-extracted/` -- pass `--manifest`.

Stdlib only, like the rest of ``sim/``.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_compare_vcm():
    path = REPO_ROOT / "sim" / "vcm-full-pvt" / "compare_vcm.py"
    spec = importlib.util.spec_from_file_location("compare_vcm", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["compare_vcm"] = module
    spec.loader.exec_module(module)
    return module


compare_vcm = _load_compare_vcm()

RAIL = "V_DD"
BUDGET = "DR-0036's budget (Z_vdd = 3 ohm, C_dec = 40 nF)"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--experiment", required=True,
                   help="experiment slug (labels the output, and locates "
                        "sim/<slug>/testbench/tb.json unless --manifest)")
    p.add_argument("--ideal", type=Path, required=True,
                   help="record from the ideal-V_DD-source control arm")
    p.add_argument("--vddnet", type=Path, required=True,
                   help="record from the V_DD-pin-network arm")
    p.add_argument("--manifest", type=Path, default=None,
                   help="manifest whose `checks` give the bounds (default: "
                        "sim/<experiment>/testbench/tb.json)")
    args = p.parse_args(argv)
    return compare_vcm.compare(args.experiment, args.ideal, args.vddnet,
                               rail=RAIL, budget=BUDGET,
                               manifest=args.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
