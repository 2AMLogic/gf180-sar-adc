#!/usr/bin/env python3
"""DC operating-point verification of the remediated extracted `ADC_TOP` core.

    python3 layout/adc-top/parasitics/verify_remediation_dc.py            # run + print
    python3 layout/adc-top/parasitics/verify_remediation_dc.py --corners cdac
    python3 layout/adc-top/parasitics/verify_remediation_dc.py --json out.json

This is issue #89's **pre-work verification** (Test Plan item 1): before any
full transistor-level bench is run against the extracted core, confirm the two
remediations `remediate_extracted.py` applies actually make the core a
well-posed, simulatable circuit -- across the PVT grid, per CLAUDE.md ("PVT
corners on every recorded result", "no claim without a testbench"). It does NOT
run a conversion or make any ADC spec-line claim; Scope items 1-5 (the #13 PVT
bench, #14 Monte Carlo, and the schematic-vs-extracted delta summary) remain
deferred and are a material multi-hour transient campaign, not this DC smoke.

What it substantiates, and how:

1. **PMOS body tie is hard and corner-independent (guidance item 1).** Parsing
   the remediated core, EVERY `pfet_03v3` card's 4th (body) terminal is the
   `vdd` net -- a structural, net-identity invariant that no corner or bias can
   move. Contrast: the RAW extraction leaves each PMOS body on an anonymous
   un-pinned net whose DC value is bias-dependent and NOT a vdd tie -- this
   script measures those raw body nodes at one corner and reports them beside
   the tie, so the gap is shown, not asserted (README's reproduced leaf test saw
   ~0 V with a driven-low source; a full-core op with sources near vdd floats
   them near, but not at, vdd -- either way un-tied).

2. **The core is simulatable across PVT (guidance items 1+3).** A DC `op` is
   composed for every point of the requested grid -- the same `.lib` process
   sections and +/-10 % supply / -40..125 C axes `sim/harness/corners.py`
   defines -- against the resolved gf180mcu PDK. Every point must converge
   (finite supply current, no singular matrix); a non-converging point fails.

3. **The promoted input pins are reachable (guidance item 3 / scope item 0).**
   Each deck drives `vinp`/`vinn` (the rails `remediate_extracted.py` promoted
   from the internal `$8`/`$91`) and the op resolves them -- so an
   extracted-core testbench can inject the sampled input, which the 63-pin raw
   `ADC_TOP` gave no port for.

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

import gen_extracted_core_tb as G  # noqa: E402 (same directory)

MIM_SECTION = "mimcap_typical"


def _bias(pin: str) -> float:
    """A quiescent, physically-sane DC bias for each ADC_TOP pin.

    `sel_in` high -> the fourth-leg sampling T-gates conduct (acquisition);
    `rel_*` high -> the other three legs release their bottom plates to V_cm;
    `hi_*`/`lo_*` low -> V_ref / V_ss legs off. This is a static acquisition
    bias: it exercises the sampled-input path (vinp/vinn -> bottom plates ->
    top plates) without needing a transient, which is all a DC well-posedness
    check requires.
    """
    fixed = {
        "vdd": None,  # set to the point's supply by the caller
        "vss": 0.0,
        "vsubs": 0.0,
        "vcm": None,  # vdd/2
        "vref": None,  # vdd
        "sel_in": None,  # vdd (sampling)
        "tp_gn": None,  # vdd (top-plate switch closed)
        "topp": None,  # vcm
        "topn": None,  # vcm
        "vinp": 1.0,
        "vinn": 2.3,
    }
    if pin in fixed:
        return fixed[pin]  # type: ignore[return-value]
    if pin.startswith("rel_"):
        return None  # -> vdd
    if pin.startswith("hi_") or pin.startswith("lo_"):
        return 0.0
    return 0.0


def _pin_source_value(pin: str, vdd: float) -> float:
    v = _bias(pin)
    if v is not None:
        return v
    if pin in ("vcm", "topp", "topn"):
        return round(vdd / 2.0, 6)
    # vdd, vref, sel_in, tp_gn, rel_* -> full supply
    return vdd


def compose_dc_deck(core_path: Path, pins: list[str], pdk: PDK.Pdk,
                    corner: C.Corner, temp_c: float, vdd: float,
                    probe_nodes: list[str] | None = None, top: str = "ADC_TOP") -> str:
    """A thin wrapper around `gen_extracted_core_tb.compose_dc_op_deck()`
    (issue #183) -- see that function for the shared PVT preamble /
    `.include` / pin loop / `Xdut` / `.control` shape this deck's body used
    to hand-roll, byte-for-byte identically to
    `verify_layout_pin_dc.compose_dc_deck()`.
    """
    header = [f"* DC op verification -- remediated extracted {top} core"]
    trailing = [f"print {node}" for node in probe_nodes or []]
    return G.compose_dc_op_deck(core_path, pins, pdk, corner, temp_c, vdd,
                                top, _pin_source_value, header, "vdd", trailing)


def raw_body_nodes(core_src: Path, pdk: PDK.Pdk, workdir: Path, top: str = "ADC_TOP") -> dict[str, float]:
    """One RAW-core (unremediated) DC op; return anonymous PMOS-body node DC."""
    text = core_src.read_text()
    nl = R.parse(text, top)
    body_nets = sorted({R._mos_terminals(c)[3] for c in nl.cards
                        if R._is_mos(c) == "pfet"})
    # deck instantiates the RAW pins (no vinp/vinn) and writes a rawfile
    lines = [
        f"* RAW extracted {top} -- anonymous PMOS body nets float (the gap)",
        f'.include "{pdk.design_include}"',
    ]
    for section in C.CORNERS["tt"].sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    lines.append(f'.include "{core_src}"')
    for pin in nl.pins:
        lines.append(f"V{pin} {pin} 0 dc {_pin_source_value(pin, 3.3)}")
    lines.append("Xdut " + " ".join(nl.pins) + f" {top}")
    raw = workdir / "raw_op.raw"
    lines += [".control", "set noaskquit", "op", "write raw_op.raw", ".endc", ".end"]
    (workdir / "raw.spice").write_text("\n".join(lines) + "\n")
    subprocess.run([G.NGSPICE, "-b", str(workdir / "raw.spice")],
                   capture_output=True, text=True, cwd=workdir, timeout=600, check=False)
    if not raw.exists():
        return {}
    data = raw.read_bytes()
    hdr = data.split(b"Binary:")[0].decode("latin1", "replace")
    names = [m.group(2) for m in re.finditer(r"^\s*(\d+)\s+(\S+)\s+(\S+)", hdr, re.M)]
    body_ids = {b.split("$")[-1] for b in body_nets}
    vals = struct.unpack("<%dd" % len(names), data.split(b"Binary:\n", 1)[1][:8 * len(names)])
    by = dict(zip(names, vals))
    result: dict[str, float] = {}
    for name, val in by.items():
        m = re.search(r"\$(\d+)\)?$", name)
        if m and m.group(1) in body_ids and "__par" not in name:
            result[name] = val
    return result


def verify(corner_set: str, top: str = "ADC_TOP") -> dict:
    pdk = PDK.find_pdk()
    src = R._latest_report(top)
    core_text, rem = R.remediate(src.read_text(), top)

    # invariant 1: every pfet body terminal is now the vdd net (net identity)
    nl = R.parse(core_text, top)
    pfet_bodies = {R._mos_terminals(c)[3] for c in nl.cards if R._is_mos(c) == "pfet"}
    body_tie_ok = pfet_bodies == {R.VDD_NET}
    pins = nl.pins

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        core_path = work / f"{top.lower()}.remediated.spice"
        core_path.write_text(core_text)

        corners = C.resolve_corners([corner_set])
        temps = C.DEFAULT_TEMPERATURES_C
        supplies = C.supply_points()
        grid = C.build_grid(corners, temps, supplies)

        points = []
        all_ok = True
        for pt in grid:
            deck = compose_dc_deck(core_path, pins, pdk, pt.corner, pt.temp_c, pt.vdd, top=top)
            ok, isup, _log = G.run_op(deck, work, pt.corner_id)
            all_ok = all_ok and ok
            points.append({"corner_id": pt.corner_id, "converged": ok,
                           "isupply_a": None if isup != isup else isup})

        raw_bodies = raw_body_nodes(src, pdk, work, top=top)

    return {
        "top": top,
        "claim": f"issue #89 pre-work: the remediated extracted {top} core is a "
                 "well-posed, simulatable circuit across PVT, with every PMOS body "
                 "hard-tied to vdd and the sampled-input rails reachable. No ADC "
                 "spec-line claim is made here.",
        "netlist_provenance": "extracted (remediated: PMOS-body->vdd local "
                              "remediation of klayout-tools#555; input rails "
                              "$8/$91 promoted to vinp/vinn pins)",
        "source_extraction": str(src.relative_to(REPO)),
        "remediation": {
            "pmos_bodies_retied": rem.n_pmos_rewritten,
            "input_rails_promoted": {"vinp": rem.input_rails[0],
                                     "vinn": rem.input_rails[1]},
            "mim_caps_native_pdk_subckt": rem.n_mim,
            "mim_subckt": R.MIM_SUBCKT,
        },
        "pdk": pdk.provenance(),
        "body_tie_invariant_holds": body_tie_ok,
        "pfet_body_nets_after": sorted(pfet_bodies),
        "corner_set": corner_set,
        "grid_points": len(points),
        "all_converged": all_ok,
        "points": points,
        "raw_floating_pmos_body_nodes_v": {k: round(v, 4)
                                           for k, v in sorted(raw_bodies.items())},
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

    ok = result["all_converged"] and result["body_tie_invariant_holds"]
    print(f"top               : {result['top']}")
    print(f"corner set        : {result['corner_set']}")
    print(f"grid points       : {result['grid_points']}")
    print(f"all converged     : {result['all_converged']}")
    print(f"body tie == vdd   : {result['body_tie_invariant_holds']} "
          f"(pfet bodies -> {result['pfet_body_nets_after']})")
    print(f"input rails        : {result['remediation']['input_rails_promoted']}")
    print(f"MiM PDK subckts    : {result['remediation']['mim_caps_native_pdk_subckt']} "
          f"x {result['remediation']['mim_subckt']}")
    print(f"raw floating bodies: "
          f"{sorted(set(result['raw_floating_pmos_body_nodes_v'].values()))} V "
          f"(NOT a vdd tie)")
    print("RESULT            :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
