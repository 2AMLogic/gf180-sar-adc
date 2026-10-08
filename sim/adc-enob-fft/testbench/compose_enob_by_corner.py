#!/usr/bin/env python3
"""Per-corner ENOB composition for the adc-enob-fft campaign (issue #430).

``analyze_fft.py --sigma-extra-lsb`` composes ONE noise figure into every
corner it is pointed at.  The ratified composition (spec/testbench-suite-memo.md
Sec 4.3) uses the hot-corner worst value (157.2 uV rms) for that figure, which
is conservative at 125 C but is NOT a measurement at -40 / 27 C.  This script
composes, per FFT log, the noise terms that belong to THAT corner:

* comparator input-referred noise ``vn_in_uv`` read from the same-corner row of
  a ``sim/comparator-preamp-noise`` record (default: the clean-tree
  full-grid record 20260801-123440-033b56b, schematic netlist);
* sampling kT/C, ``sqrt(2 k T / C_side)`` with T the corner's own temperature
  and the ratified C_side = 512 * C_u = 8.827 pF.

Scope it does NOT cover, printed in every table so a reader cannot miss it:
the comparator-noise record is a *schematic* ac ``.noise`` result (not the
extracted netlist), C_side is the nominal value (no capacitor corner), the
latch's own noise is bounded not measured (memo Sec 7.3) and V_REF noise is
user-supplied (README note [b]).  A corner whose id has no row in the noise
record is reported ``noise-unavailable`` and gets NO composed ENOB -- the
script never substitutes another corner's noise.

Usage::

    python3 compose_enob_by_corner.py <corners-dir> [<corners-dir> ...]
        [--noise-record PATH] [--c-side-pf 8.827] [--vref 3.3]
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_fft as af  # noqa: E402

K_B = 1.380649e-23
DEFAULT_NOISE = (
    Path(__file__).resolve().parents[2]
    / "comparator-preamp-noise"
    / "records"
    / "20260801-123440-033b56b.md"
)
_ID = re.compile(r"^(?P<p>[a-z]+)_(?P<t>-?\d+)c_(?P<v>[\d.]+)v$")


def read_noise_rows(path: Path) -> dict[str, float]:
    """corner-id -> comparator input-referred noise (uV rms) from a record."""
    rows: dict[str, float] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*\| `([^`]+)` \| ([\d.]+) \|", line)
        if m:
            rows[m.group(1)] = float(m.group(2))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--noise-record", type=Path, default=DEFAULT_NOISE)
    ap.add_argument("--c-side-pf", type=float, default=8.827)
    ap.add_argument("--vref", type=float, default=3.3)
    args = ap.parse_args()

    noise = read_noise_rows(args.noise_record)
    lsb_uv = args.vref / 1024 * 1e6
    print(
        f"| corner-id | SFDR dB | THD dB | distortion-only SNDR dB | "
        f"distortion-only ENOB | comparator vn uV | kT/C uV | sigma LSB | "
        f"composed ENOB | noise scope |"
    )
    print("|---" * 10 + "|")
    worst = {}
    for d in args.dirs:
        for log in sorted(d.glob("*.log")):
            cid = log.stem
            r = af.analyze(af.extract_codes(log.read_text(), af.DEFAULT_N), af.DEFAULT_BIN)
            m = _ID.match(cid)
            vn = noise.get(cid)
            if m is None or vn is None:
                print(
                    f"| `{cid}` | {r['sfdr_db']:.2f} | {r['thd_db']:.2f} | "
                    f"{r['sndr_db']:.2f} | {r['enob_bits']:.3f} | n/a | n/a | n/a | "
                    f"noise-unavailable | none |"
                )
                continue
            t_k = int(m.group("t")) + 273.15
            ktc = math.sqrt(2 * K_B * t_k / (args.c_side_pf * 1e-12)) * 1e6
            sig_uv = math.hypot(vn, ktc)
            sig_lsb = sig_uv / lsb_uv
            c = af.analyze(
                af.extract_codes(log.read_text(), af.DEFAULT_N),
                af.DEFAULT_BIN,
                sigma_extra_lsb=sig_lsb,
            )
            print(
                f"| `{cid}` | {r['sfdr_db']:.2f} | {r['thd_db']:.2f} | "
                f"{r['sndr_db']:.2f} | {r['enob_bits']:.3f} | {vn:.1f} | {ktc:.1f} | "
                f"{sig_lsb:.4f} | {c['enob_composed_bits']:.3f} | "
                f"same-corner comparator + same-T kT/C |"
            )
            worst[cid] = (r["sfdr_db"], c["enob_composed_bits"], r["enob_bits"])
    if worst:
        s = min(worst.items(), key=lambda kv: kv[1][0])
        e = min(worst.items(), key=lambda kv: kv[1][1])
        print(f"\nSFDR-worst: `{s[0]}` {s[1][0]:.2f} dB")
        print(f"composed-ENOB-worst: `{e[0]}` {e[1][1]:.3f} bits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
