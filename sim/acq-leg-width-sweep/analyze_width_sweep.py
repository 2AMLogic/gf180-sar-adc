#!/usr/bin/env python3
"""Collate the acquisition-leg width sweep (issue #429).

Reuses ``sim/dr0019-cu-sweep/analyze_sweep.py``'s record reader (raw per-corner
logs -> ``analyze_fft.py`` -> SFDR / composed ENOB, noise re-derived at this
point's ``C_side``), pointed at this experiment's records/corners.  Stdlib only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "dr0019-cu-sweep" / "analyze_sweep.py"


def _base():
    spec = importlib.util.spec_from_file_location("analyze_sweep_base", BASE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base = _base()
    # Records whose harness verdict is ERROR (blocked batch submissions, kept as
    # append-only blocker evidence) carry no codes and must not be collated.
    import re
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        keep = Path(tmp)
        for rec in sorted((HERE / "records").glob("*.md")):
            if re.search(r"\*\*Overall: ERROR\*\*", rec.read_text()):
                continue
            (keep / rec.name).write_text(rec.read_text())
        points = base.read_points(keep, HERE / "corners")
    if not points:
        print(f"error: no usable records under {HERE / 'records'}", file=sys.stderr)
        return 1
    if "--markdown" in argv:
        print("| acq-leg width | worst SFDR (dB) | at | worst composed ENOB (bits) | at | harness | max V_REF droop (mV) | record |")
        print("|---|---|---|---|---|---|---|---|")
        for p in points:
            droop = "-" if p["vref_droop_mv_max"] is None else f"{p['vref_droop_mv_max']:.3f}"
            print(
                f"| x{p['acq_switch_scale']:g} | {p['worst_sfdr_db']:.2f} | `{p['worst_sfdr_corner']}` | "
                f"{p['worst_enob_bits']:.3f} | `{p['worst_enob_corner']}` | {p['harness_verdict']} | "
                f"{droop} | `{p['record_id']}` |"
            )
    else:
        print(json.dumps({"points": points}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
