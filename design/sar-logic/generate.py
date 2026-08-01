#!/usr/bin/env python3
"""Write the generated artifacts of the SAR control logic.

    python3 design/sar-logic/generate.py          # write
    python3 design/sar-logic/generate.py --check   # report drift, write nothing

Three files are derived from ``sar_logic.py`` and committed alongside it, so a
reader (or a Judge, or LVS) never has to run a generator to see the netlist:

    design/sar-logic/sar_logic.spice     the transistor-level design
    sim/sar-logic/testbench/tb_sar_logic.spice
    sim/sar-logic/testbench/tb.json

``--check`` is what ``sim/tests/test_sar_logic.py`` runs, so a change to the
structure that is not regenerated fails CI rather than shipping a netlist that
no longer matches its verification.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import sar_logic  # noqa: E402


def artifacts() -> dict[Path, str]:
    return {
        HERE / "sar_logic.spice": sar_logic.emit_design_spice(),
        REPO / "sim" / "sar-logic" / "testbench" / "tb_sar_logic.spice": sar_logic.emit_tb_fragment(),
        REPO / "sim" / "sar-logic" / "testbench" / "tb.json": sar_logic.emit_tb_manifest_json(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    args = parser.parse_args(argv)

    stale: list[Path] = []
    for path, content in artifacts().items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"wrote {path.relative_to(REPO)}")

    if stale:
        for path in stale:
            print(f"STALE: {path.relative_to(REPO)}", file=sys.stderr)
        print("run: python3 design/sar-logic/generate.py", file=sys.stderr)
        return 1
    if args.check:
        print("generated artifacts are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
