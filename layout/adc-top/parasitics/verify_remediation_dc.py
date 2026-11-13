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
   the remediated core, EVERY `pfet_03v3` card's 4th (body) terminal resolves
   to the `vdd` net -- a structural, net-identity invariant that no corner or
   bias can move. The check reads `remediate_extracted.py`'s own body-terminal
   partition (`Remediation.n_pmos_rewritten` / `.n_pmos_already_tied`), so it
   holds across BOTH extraction eras: pre-DR-0035 input, where every body
   arrives on an anonymous un-pinned net and the remediation reties it, and
   post-DR-0035 input, where the drawn n-well tap already puts it on `vdd` and
   nothing is rewritten. It is a count-complete partition over the PMOS cards,
   not a net-name string match, so a body left anywhere else still fails it.

   **Historical, pre-DR-0035:** this script also used to run one RAW-core DC op
   and print the anonymous body nodes' floating voltages beside the tie, so the
   gap was shown rather than asserted (README's reproduced leaf test saw ~0 V
   with a driven-low source; a full-core op with sources near vdd floated them
   near, but not at, vdd -- either way un-tied). DR-0035 (#356 / PR #384) drew a
   tap inside every `Nwell` island, so no newly-minted extraction has an
   anonymous body net left to probe and that probe was removed (#784). Its
   evidence stays on record, unchanged, in
   `records/20260805-remediation-dc.md` and the
   `raw_floating_pmos_body_nodes_v` map of
   `reports/20260805-remediation-dc/verify_remediation_dc.json` (20 nets for
   `ADC_TOP`, 25 for `ADC_BLOCK`); the per-era body-terminal counts are in
   `README.md` -> "The body-tie step after DR-0035".

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


def body_tie_result(core_text: str, rem: R.Remediation, top: str,
                    nl: "R.Netlist | None" = None) -> dict:
    """Invariant 1, as a dict: does every PMOS body resolve to the `vdd` net?

    Net identity, not a bias, so no corner or operating point can move it --
    which is why this is decided by parsing alone and needs no simulation
    (and is unit-testable against every committed extraction without a PDK).

    It reads `remediate_extracted.py`'s own body-terminal partition rather
    than string-matching the terminal net, for two reasons. The terminal net
    written on a device card is a parasitic LEG of its hub (`vdd__t<k>` since
    the `875eac3` toolchain pin, issue #116), so a literal `== "vdd"` test is
    false on every current extraction; and post-DR-0035 the bodies arrive
    already tied by the drawn n-well tap instead of being rewritten here, so
    "how many did we rewrite" is no longer the whole story either.

    The invariant is **count-complete**: every PMOS card must be accounted
    for by exactly one of the two dispositions (rewritten / already tied),
    AND every body hub must be `vdd`. A body left anywhere else -- a tap
    deleted, a strap broken, a future cell drawn without one -- fails it.
    """
    nl = nl if nl is not None else R.parse(core_text, top)
    pfet_cards = [c for c in nl.cards if R._is_mos(c) == "pfet"]
    body_hubs = {R._hub(R._mos_terminals(c)[3]) for c in pfet_cards}
    n_dispositioned = rem.n_pmos_rewritten + rem.n_pmos_already_tied
    holds = (
        bool(pfet_cards)
        and body_hubs == {R.VDD_NET}
        and n_dispositioned == len(pfet_cards)
    )
    return {
        "holds": holds,
        "disposition": rem.body_tie_disposition,
        "gap_closed_in_layout": rem.body_gap_closed_in_layout,
        "pmos_body_terminals": len(pfet_cards),
        "pmos_bodies_rewritten_to_vdd": rem.n_pmos_rewritten,
        "pmos_bodies_already_tied_in_layout": rem.n_pmos_already_tied,
        "pmos_body_nets_after": sorted(body_hubs),
    }


def verify(corner_set: str, top: str = "ADC_TOP") -> dict:
    pdk = PDK.find_pdk()
    src = R._latest_report(top)
    core_text, rem = R.remediate(src.read_text(), top)

    # Invariant 1 (see `body_tie_result()`): parse-only, no simulation.
    nl = R.parse(core_text, top)
    body_tie = body_tie_result(core_text, rem, top, nl=nl)
    body_tie_ok = body_tie["holds"]
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

    return {
        "top": top,
        "claim": f"issue #89 pre-work: the remediated extracted {top} core is a "
                 "well-posed, simulatable circuit across PVT, with every PMOS body "
                 "hard-tied to vdd and the sampled-input rails reachable. No ADC "
                 "spec-line claim is made here.",
        "netlist_provenance": "extracted (remediated: PMOS body ties "
                              + ("drawn in layout per DR-0035, nothing rewritten"
                                 if rem.body_gap_closed_in_layout
                                 else "rewritten to vdd -- the local remediation "
                                      "of klayout-tools#555 on untapped input")
                              + "; input rails $8/$91 promoted to vinp/vinn pins)",
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
        "body_tie": {k: v for k, v in body_tie.items() if k != "holds"},
        "corner_set": corner_set,
        "grid_points": len(points),
        "all_converged": all_ok,
        "points": points,
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
    bt = result["body_tie"]
    print(f"body tie -> vdd   : {result['body_tie_invariant_holds']} "
          f"({bt['pmos_bodies_rewritten_to_vdd']} rewritten + "
          f"{bt['pmos_bodies_already_tied_in_layout']} already tied in layout "
          f"of {bt['pmos_body_terminals']} PMOS bodies, "
          f"{bt['disposition']} -> {bt['pmos_body_nets_after']})")
    print(f"input rails        : {result['remediation']['input_rails_promoted']}")
    print(f"MiM PDK subckts    : {result['remediation']['mim_caps_native_pdk_subckt']} "
          f"x {result['remediation']['mim_subckt']}")
    print("RESULT            :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
