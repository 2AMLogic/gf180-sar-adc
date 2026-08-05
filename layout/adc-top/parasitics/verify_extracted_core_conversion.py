#!/usr/bin/env python3
"""Run an actual transient conversion through `gen_extracted_core_tb.py`'s
wiring and confirm it decodes a sane code -- issue #89 Scope item 0's own
test plan item: "instantiate the extracted core" is a claim that needs a
testbench (CLAUDE.md), not just a script that composes text without ever
being run.

    python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py
    python3 layout/adc-top/parasitics/verify_extracted_core_conversion.py --json out.json

What this substantiates, and how narrowly:

- **The extracted core, wired as `gen_extracted_core_tb.py` wires it, converts.**
  Three known inputs (near the bottom of range, the free-MSB transition, near
  the top of range) are stepped through ONE nominal-corner (`tt`, 27 C, 3.3 V)
  transient run, single-ended mode; the rung-1 controller and comparator run a
  real 10-trial SAR conversion against the extracted core for each, and the
  decoded code is read back and checked against the known transition with the
  SAME liveness tolerance (`gtop.CODE_TOL_LSB`, inherited, not invented here)
  `design/adc-top/gen_adc_top.py`'s own INL/DNL deck uses for its liveness
  check -- i.e. "the whole chain ran and tracked the input", not a linearity
  claim.

- **What this explicitly is NOT**: the #13 INL/DNL/ENOB/power suite re-run
  (Scope item 1), the #14 Monte Carlo re-run (Scope item 2), or the
  schematic-vs-extracted delta summary incl. `gain_err_lsb` (Scope item 3, 8).
  Those need the full PVT grid (63 points x 18 transitions for the
  static-linearity bench alone -- a multi-hour campaign,
  `parasitics/README.md` "Compute note") and are deferred, unstarted by this
  script. This script runs exactly ONE corner and THREE transitions -- enough
  to prove the wiring in `gen_extracted_core_tb.py` produces a converter that
  actually converts, not enough to make any spec-line claim about it.

The PDK is discovered through `sim/harness/pdk.py`; with no PDK installed the
script skips with a clear message rather than fabricating a result.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness import corners as C  # noqa: E402
from harness import pdk as PDK  # noqa: E402

import gen_extracted_core_tb as G  # noqa: E402 (same directory)

NGSPICE = "ngspice"

#: Probed transitions: bottom endpoint, the free-MSB (trial 1, no array
#: switching) transition, and the top endpoint -- the same three points
#: `design/adc-top/gen_adc_top.py`'s own INL_TRANSITIONS opens and closes
#: its ladder on, reused here rather than invented, since they already carry
#: a stated rationale (endpoint anchors + the trial that needs no charge
#: redistribution at all, so it is the least likely of the 18 to be sensitive
#: to any wiring bug in this new harness).
SMOKE_TRANSITIONS = [2, 512, 1022]
SMOKE_WARMUP_CONV = 1


def _end_ns() -> float:
    return (SMOKE_WARMUP_CONV + len(SMOKE_TRANSITIONS)) * G.gtop.CONV_NS


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                  vdd: float) -> tuple[str, dict[int, float]]:
    """The complete ngspice deck plus `{transition: decode_time_ns}`."""
    tag = G.TAG
    lines = [
        f"* extracted-core functional smoke test -- issue #89 Scope item 0",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        f".param vdd_val={vdd!r}",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    # BUGFIX (issue #89 measure_extracted_gain_err.py increment): `temp_c` was
    # accepted as a parameter and stamped into the corner-id/comment, but
    # never actually applied to the simulation -- so every "--corner ss
    # --temp 125" style spot-check (see this module's own
    # records/20260805-extracted-core-smoke.md "worst-case corner
    # spot-check") ran at ngspice's DEFAULT temperature (27 C), not the
    # temperature the record claimed. Found while building
    # measure_extracted_gain_err.py, which copied this same compose_deck
    # pattern -- fixed here too rather than left silently wrong, since this
    # is exactly the "looks like it sweeps a PVT axis but doesn't" failure
    # class sim/harness/corners.py's own sabotage() negative control exists
    # to catch (see sim/harness/README.md).
    lines.append(f".temp {temp_c!r}")
    lines.append("")

    lines += G.gtop._preamble("{vdd_val/1024}")
    lines.append("")
    lines.append("* ---- input: three known transitions, one conversion each ----------")
    pts: list[str] = []
    decode_ns: dict[int, float] = {}
    prev = ""
    for idx, k in enumerate(SMOKE_TRANSITIONS):
        t0 = (SMOKE_WARMUP_CONV + idx) * G.gtop.CONV_NS
        lvl = f"{{({k}+0.25)*lsb}}"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
        decode_ns[k] = t0 + 950.0
    pts.append(f"{_end_ns():.1f}n {prev}")
    lines += G.gtop.sar._wrap(f"v{tag}vinp {tag}_vinp 0 pwl(", [" ".join(pts) + ")"])
    lines.append(f"v{tag}vinn {tag}_vinn 0 dc {{vcm}}")
    lines.append("")

    pins, core_text = G.core_pins(top)
    lines.append(G.gtop.comparator_block())
    lines.append(G.gtop.sar.library())
    lines.append(core_text)
    lines += G._core_extracted(tag, "0", pins, top)

    lines.append("")
    lines.append(".control")
    lines.append("set numdgt=8")
    lines.append("set noaskquit")
    lines.append(f"tran 1n {_end_ns() / 1000:.3f}u 0 2n")
    for k, t_ns in decode_ns.items():
        lines.append(f"meas tran cd{k} FIND v({tag}_code) AT={t_ns:.3f}n")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n", decode_ns


_CODE_RE_TMPL = r"\bcd{k}\s*=\s*([-\d.eE+]+)"


def run(deck: str, workdir: Path, decode_ns: dict[int, float]) -> tuple[dict[int, float], str]:
    path = workdir / "extracted_core_smoke.spice"
    path.write_text(deck)
    proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                          text=True, cwd=workdir, timeout=900, check=False)
    out = proc.stdout + "\n" + proc.stderr
    codes: dict[int, float] = {}
    for k in decode_ns:
        m = re.search(_CODE_RE_TMPL.format(k=k), out)
        codes[k] = float(m.group(1)) if m else float("nan")
    return codes, out


def verify(top: str = "ADC_TOP", corner_name: str = "tt", temp_c: float = 27.0,
          vdd: float = 3.3) -> dict:
    pdk = PDK.find_pdk()
    corner = C.CORNERS[corner_name]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        deck, decode_ns = compose_deck(top, pdk, corner, temp_c, vdd)
        codes, log = run(deck, work, decode_ns)

    tol = G.gtop.CODE_TOL_LSB
    points = []
    all_ok = True
    for k in SMOKE_TRANSITIONS:
        got = codes[k]
        ok = (got == got) and abs(got - k) <= tol  # nan-safe
        all_ok = all_ok and ok
        points.append({"transition": k, "decoded_code": None if got != got else got,
                       "tolerance_lsb": tol, "converged": ok})

    return {
        "top": top,
        "claim": "issue #89 Scope item 0: the extracted core, wired by "
                 "gen_extracted_core_tb.py, converts a real transient "
                 "conversion -- decoded codes track three known transitions "
                 "within the SAME liveness tolerance gen_adc_top.py's own "
                 "INL/DNL deck uses. NOT an INL/DNL/gain-error claim "
                 "(Scope items 1, 3, 8 remain deferred) and NOT a "
                 "multi-corner result (Scope items 1-2's PVT/MC grid remain "
                 "deferred) -- one nominal corner only.",
        "netlist_provenance": "extracted (remediated: PMOS-body->vdd local "
                              "remediation of klayout-tools#555; input rails "
                              "promoted to vinp/vinn) wired to the schematic "
                              "comparator + rung-1 SAR controller + DR-0013 "
                              "input drive network",
        "corner": corner_name,
        "temp_c": temp_c,
        "vdd": vdd,
        "pdk": pdk.provenance(),
        "code_tolerance_lsb": tol,
        "points": points,
        "all_converged": all_ok,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP"],
                    help="ADC_TOP only -- see gen_extracted_core_tb.py's --top "
                         "help for why ADC_BLOCK is not offered here")
    ap.add_argument("--corner", default="tt", help="corner name from sim/harness/corners.py")
    ap.add_argument("--temp", type=float, default=27.0)
    ap.add_argument("--vdd", type=float, default=3.3)
    ap.add_argument("--json", help="write the full result JSON here")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py). "
              "This verification needs the PDK to run ngspice.", file=sys.stderr)
        return 0

    result = verify(args.top, args.corner, args.temp, args.vdd)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")

    print(f"top               : {result['top']}")
    print(f"corner            : {result['corner']} {result['temp_c']}C {result['vdd']}V")
    print(f"code tolerance    : +/-{result['code_tolerance_lsb']:.0f} LSB (inherited, "
          f"liveness only -- see docstring)")
    for pt in result["points"]:
        print(f"  transition {pt['transition']:>4} -> decoded "
              f"{pt['decoded_code']!r} : {'OK' if pt['converged'] else 'FAIL'}")
    print("RESULT            :", "PASS" if result["all_converged"] else "FAIL")
    return 0 if result["all_converged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
