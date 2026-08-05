#!/usr/bin/env python3
"""DC operating-point verification of issue #91's drawn `pinp`/`pinn` layout
pins -- run directly against a RAW `klt extract` output, with **none** of
`remediate_extracted.py`'s post-processing applied.

    python3 layout/adc-top/parasitics/verify_layout_pin_dc.py            # run + print
    python3 layout/adc-top/parasitics/verify_layout_pin_dc.py --top ADC_BLOCK
    python3 layout/adc-top/parasitics/verify_layout_pin_dc.py --corners cdac --json out.json

This is issue #91's Test Plan item 4 ("A DC smoke test ... drives the new pin
and confirms it reaches the fourth leg's T-gate source (not floating, not
shorted), without needing `remediate_extracted.py`'s post-processing step").
It follows `verify_remediation_dc.py`'s pattern (PR #92) -- a DC `op` across
the full PVT grid, PVT provenance, an append-only record -- but differs from
it in the one respect the issue asks for: it drives the extracted netlist
**as `klt extract` wrote it**, no `remediate_extracted.py` rewrite in
between. `verify_remediation_dc.py` proves the *remediated* core is
simulatable; this script proves the *drawn layout* itself -- the actual
GDS -- now carries a real, reachable `pinp`/`pinn` pin, independent of any
simulation-side workaround.

What it substantiates, and how:

1. **The layout, not just the LVS reference, declares the pin.** Parsing the
   latest raw (`--pdk`) extraction directly (no `remediate()` call), `pinp`
   and `pinn` are asserted present in the `.SUBCKT` pin list. Before #91 they
   were not: `klt extract` reported the fourth-leg input rail as an
   anonymous internal net (`$8`/`$91` in the pre-#91 record; see #91's own
   issue body). A regression here means the label draw call regressed, not
   a simulation-harness problem.
2. **The pin is reachable and well-posed across PVT.** A DC `op` is composed
   for every point of the requested grid, driving every declared pin
   (`pinp`/`pinn` included) at a fixed, physically-sane bias -- the same
   `.lib` process sections and +/-10% supply / -40..125 C axes
   `sim/harness/corners.py` defines. Every point must converge.
3. **The driven pin genuinely reaches the fourth leg's T-gate source -- not
   floating, not shorted.** `pinp`/`pinn` are driven at two DISTINCT,
   otherwise-unused voltages (1.0 V / 2.3 V, matching `verify_remediation_
   dc.py`'s choice, clear of `vss`=0 V, `vcm`=vdd/2, `vref`=vdd). With the
   fourth leg's own decode gate ON (`sel_in` high) and every other leg OFF
   (`rel_*`/`hi_*`/`lo_*` low, so no other leg contends for the same bottom
   plate), every one of a side's nine weighted cells' bottom-plate node
   (identified structurally -- the same non-supply, non-pin channel
   terminal test `remediate_extracted._find_input_rails` uses, generalised
   to return every match instead of just the rail) is probed via a written
   `.raw` file (`print v(...)` cannot address these anonymous, `$`-prefixed
   internal nets -- `$` opens a SPICE end-of-line comment -- which is why
   `verify_remediation_dc.raw_body_nodes()` uses the same rawfile technique
   for the anonymous PMOS-body nodes). Each bottom-plate node must land
   within a tight tolerance of its side's driven pin voltage: proof the pin
   is not floating (an unconnected node would not track it) and not shorted
   to `vss`/`vcm`/`vref`/the opposite side's pin (any of which would pull it
   to a different, wrong value instead).

The PDK is discovered through `sim/harness/pdk.py` (the same resolver every
`sim/` record uses); with no PDK installed the script skips with a clear
message rather than fabricating a result.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness import corners as C  # noqa: E402
from harness import pdk as PDK  # noqa: E402

import remediate_extracted as R  # noqa: E402

NGSPICE = "ngspice"

#: The two distinct, otherwise-unused DC biases driven onto `pinp`/`pinn` --
#: chosen clear of every other rail this core drives (`vss`=0, `vcm`=vdd/2,
#: `vref`=vdd), so a downstream node landing at one of THOSE values instead
#: would read as a wrong-net short, not a rounding coincidence.
PINP_BIAS = 1.0
PINN_BIAS = 2.3
#: Tolerance for "the bottom plate tracks the driven pin" -- an ON T-gate's
#: channel carries no DC current at true equilibrium (the CDAC bottom plate
#: is a capacitor: an open circuit at DC), so the only residual is the
#: device model's own leakage-driven numerical settle, empirically well
#: under a millivolt; 5 mV is generous headroom, not a tuned-to-pass number.
TRACK_TOL_V = 0.005


def _bias(pin: str, vdd: float) -> float:
    """A quiescent, physically-sane DC bias for each RAW `ADC_TOP`/
    `ADC_BLOCK` pin, chosen so ONLY the fourth (input) leg conducts:
    `sel_in` high enables it, every other leg's own gate control
    (`rel_*`/`hi_*`/`lo_*`) stays low so it cannot also claim the same
    bottom plate and mask a `pinp`/`pinn` connectivity defect."""
    fixed = {
        "vdd": vdd,
        "vss": 0.0,
        "vsubs": 0.0,
        "vcm": round(vdd / 2.0, 6),
        "vref": vdd,
        "sel_in": vdd,  # fourth leg ON (acquisition)
        "tp_gn": vdd,  # top-plate switch closed (adc_top/adc_block only)
        "topp": round(vdd / 2.0, 6),
        "topn": round(vdd / 2.0, 6),
        "pinp": PINP_BIAS,
        "pinn": PINN_BIAS,
    }
    if pin in fixed:
        return fixed[pin]
    if pin.startswith(("rel_", "hi_", "lo_")):
        return 0.0  # every OTHER leg OFF
    # comparator pins, when present (ADC_BLOCK only) -- not this test's
    # concern; a sane fixed bias is enough for the op to converge.
    return 0.0


def _rail_to_plates(nl: R.Netlist, bottom_plates: set[str]) -> dict[str, set[str]]:
    """net -> the set of bottom-plate nets it reaches through exactly one
    T-gate channel terminal -- the same structural rule
    `remediate_extracted._find_input_rails` uses, generalised to return
    every match (not just the two rail candidates), so this module can look
    up `pinp`/`pinn`'s own bottom plates directly rather than re-deriving
    the rule."""
    out: dict[str, set[str]] = {}
    for card in nl.cards:
        if not R._is_mos(card):
            continue
        d, g, s, _b = R._mos_terminals(card)
        chan = [d, s]
        touched = [n for n in chan if n in bottom_plates]
        if len(touched) != 1:
            continue
        bp = touched[0]
        other = chan[1] if chan[0] == bp else chan[0]
        out.setdefault(other, set()).add(bp)
    return out


def compose_dc_deck(core_path: Path, pins: list[str], pdk: PDK.Pdk,
                    corner: C.Corner, temp_c: float, vdd: float,
                    top: str, raw_name: str | None) -> str:
    """`raw_name` is a bare filename (no directory, unquoted in the deck's
    own `write` command) -- `ngspice -b` is always invoked with `cwd=workdir`
    (see `run_op`), and a quoted absolute path handed to `write` was found,
    empirically, to write nothing at all (no error, no file) while the
    unquoted-relative form `verify_remediation_dc.raw_body_nodes()` already
    uses works every time; this mirrors that working form rather than the
    one that silently failed."""
    lines = [
        f"* DC op verification -- RAW extracted {top} core (issue #91,",
        "* no remediate_extracted.py post-processing)",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    lines.append(f'.include "{core_path}"')
    for pin in pins:
        lines.append(f"V{pin} {pin} 0 dc {_bias(pin, vdd)}")
    lines.append("Xdut " + " ".join(pins) + f" {top}")
    lines.append(".control")
    lines.append("set numdgt=8")
    lines.append("set noaskquit")
    lines.append("op")
    lines.append("let isupply = i(Vpinp)")
    lines.append("print isupply")
    if raw_name is not None:
        lines.append(f"write {raw_name}")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n"


_ISUP = re.compile(r"isupply\s*=\s*([-\d.eE+]+)")


def run_op(deck: str, workdir: Path, name: str) -> tuple[bool, float, str]:
    path = workdir / f"{name}.spice"
    path.write_text(deck)
    proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                          text=True, cwd=workdir, timeout=600, check=False)
    out = proc.stdout + "\n" + proc.stderr
    m = _ISUP.search(out)
    isup = float(m.group(1)) if m else float("nan")
    # Same "only the log up to our own print is authoritative" discipline as
    # verify_remediation_dc.run_op() -- see that function's docstring for
    # the ADC_BLOCK trailing-transient-op false-FAIL this guards against.
    authoritative = out[: m.end()] if m else out
    bad = any(s in authoritative.lower() for s in
              ("singular", "no convergence", "aborted", "iteration number"))
    ok = (proc.returncode == 0) and (not bad) and (isup == isup)  # nan check
    return ok, isup, out


def _read_raw_node_values(raw_path: Path) -> dict[str, float]:
    """Every named node's DC value from a `write <path>` rawfile -- the same
    technique `verify_remediation_dc.raw_body_nodes()` uses, generalised to
    return the full name->value map instead of filtering for PMOS bodies."""
    if not raw_path.exists():
        return {}
    data = raw_path.read_bytes()
    hdr = data.split(b"Binary:")[0].decode("latin1", "replace")
    names = [m.group(2) for m in re.finditer(r"^\s*(\d+)\s+(\S+)\s+(\S+)", hdr, re.M)]
    vals = struct.unpack("<%dd" % len(names), data.split(b"Binary:\n", 1)[1][:8 * len(names)])
    return dict(zip(names, vals))


def _match_by_dollar_id(values: dict[str, float], net: str) -> float | None:
    """`net` is a `klt`-escaped anonymous net (`\\$10`); ngspice's rawfile
    names the corresponding node `xdut.$10` (or similarly qualified) -- match
    by the trailing `$<digits>` id, exactly as `verify_remediation_dc.
    raw_body_nodes()` does for the anonymous PMOS-body nodes."""
    m = re.search(r"\$(\d+)$", net)
    if not m:
        return None
    want = m.group(1)
    for name, val in values.items():
        if "__par" in name:
            continue
        nm = re.search(r"\$(\d+)\)?$", name)
        if nm and nm.group(1) == want:
            return val
    return None


def verify(corner_set: str, top: str = "ADC_TOP") -> dict:
    pdk = PDK.find_pdk()
    src = R._latest_report(top)
    nl = R.parse(src.read_text(), top)

    # invariant: the RAW extraction (no remediation) already declares the
    # pin -- this is issue #91's own deliverable, and a regression here
    # means the layout's pin-label draw call regressed, not that this
    # script's harness broke.
    pin_declared = "pinp" in nl.pins and "pinn" in nl.pins

    bottom_plates = R._collect_bottom_plates(nl)
    rail_plates = _rail_to_plates(nl, bottom_plates)
    plates_p = sorted(rail_plates.get("pinp", set()))
    plates_n = sorted(rail_plates.get("pinn", set()))

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        core_path = work / f"{top.lower()}.raw_core.spice"
        core_path.write_text(src.read_text())

        corners = C.resolve_corners([corner_set])
        temps = C.DEFAULT_TEMPERATURES_C
        supplies = C.supply_points()
        grid = C.build_grid(corners, temps, supplies)

        points = []
        all_ok = True
        # Nominal-corner probe: every weighted cell's bottom plate must
        # track its side's driven pin -- checked once (not per PVT point;
        # this is a connectivity claim, not a corner-dependent one, and the
        # binary-rawfile round trip per point would multiply runtime for no
        # new information).
        probe_result: dict = {}
        for index, pt in enumerate(grid):
            raw_name = "probe.raw" if index == 0 else None
            deck = compose_dc_deck(core_path, nl.pins, pdk, pt.corner,
                                   pt.temp_c, pt.vdd, top, raw_name)
            ok, isup, _log = run_op(deck, work, pt.corner_id)
            all_ok = all_ok and ok
            points.append({"corner_id": pt.corner_id, "converged": ok,
                           "isupply_a": None if isup != isup else isup})
            if index == 0 and ok:
                values = _read_raw_node_values(work / "probe.raw")
                probe_p = {net: _match_by_dollar_id(values, net) for net in plates_p}
                probe_n = {net: _match_by_dollar_id(values, net) for net in plates_n}
                probe_result = {
                    "corner_id": pt.corner_id,
                    "pinp_driven_v": PINP_BIAS,
                    "pinn_driven_v": PINN_BIAS,
                    "bottom_plates_p": probe_p,
                    "bottom_plates_n": probe_n,
                    "p_side_all_within_tolerance": all(
                        v is not None and abs(v - PINP_BIAS) <= TRACK_TOL_V
                        for v in probe_p.values()
                    ) and len(probe_p) == len(plates_p) > 0,
                    "n_side_all_within_tolerance": all(
                        v is not None and abs(v - PINN_BIAS) <= TRACK_TOL_V
                        for v in probe_n.values()
                    ) and len(probe_n) == len(plates_n) > 0,
                }

    reaches_tgate_source = bool(
        probe_result.get("p_side_all_within_tolerance")
        and probe_result.get("n_side_all_within_tolerance")
    )

    return {
        "top": top,
        "claim": f"issue #91: the RAW (unremediated) `klt extract` of {top} "
                 "already declares `pinp`/`pinn` as .SUBCKT pins, both are "
                 "reachable and well-posed in a DC op across PVT, and each "
                 "drives its side's nine weighted cells' fourth-leg T-gate "
                 "source (bottom plate) to the exact voltage forced on the "
                 "pin -- not floating, not shorted to vss/vcm/vref or the "
                 "opposite side's pin.",
        "netlist_provenance": "extracted (RAW klt extract output -- "
                              "remediate_extracted.py NOT applied)",
        "source_extraction": str(src.relative_to(REPO)),
        "pdk": pdk.provenance(),
        "pin_declared_in_raw_extraction": pin_declared,
        "bottom_plates_reached_by_pinp": plates_p,
        "bottom_plates_reached_by_pinn": plates_n,
        "corner_set": corner_set,
        "grid_points": len(points),
        "all_converged": all_ok,
        "points": points,
        "probe": probe_result,
        "reaches_fourth_leg_t_gate_source": reaches_tgate_source,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corners", default="cdac",
                    help="corner set from sim/harness/corners.py (default: cdac)")
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP", "ADC_BLOCK"],
                    help="extracted top cell to verify (default: ADC_TOP)")
    ap.add_argument("--json", help="write the full result JSON here")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py). "
              "This verification needs the PDK to run ngspice.", file=sys.stderr)
        return 0

    result = verify(args.corners, top=args.top)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")

    ok = (result["pin_declared_in_raw_extraction"] and result["all_converged"]
          and result["reaches_fourth_leg_t_gate_source"])
    print(f"top                        : {result['top']}")
    print(f"source extraction          : {result['source_extraction']}")
    print(f"pinp/pinn declared (raw)   : {result['pin_declared_in_raw_extraction']}")
    print(f"corner set                 : {result['corner_set']}")
    print(f"grid points                : {result['grid_points']}")
    print(f"all converged              : {result['all_converged']}")
    print(f"bottom plates via pinp     : {len(result['bottom_plates_reached_by_pinp'])}")
    print(f"bottom plates via pinn     : {len(result['bottom_plates_reached_by_pinn'])}")
    probe = result["probe"]
    if probe:
        print(f"probe corner               : {probe['corner_id']}")
        print(f"  pinp driven {probe['pinp_driven_v']} V -> bottom plates "
              f"{sorted(set(round(v, 6) for v in probe['bottom_plates_p'].values() if v is not None))}")
        print(f"  pinn driven {probe['pinn_driven_v']} V -> bottom plates "
              f"{sorted(set(round(v, 6) for v in probe['bottom_plates_n'].values() if v is not None))}")
    print(f"reaches T-gate source      : {result['reaches_fourth_leg_t_gate_source']}")
    print("RESULT                     :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
