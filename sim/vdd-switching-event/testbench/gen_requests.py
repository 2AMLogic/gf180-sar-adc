#!/usr/bin/env python3
"""Generate this experiment's `klt sim` requests and wrapper netlist bodies.

Issue #386. One source of truth for the deck: every file this script writes
is committed, and re-running it must reproduce them byte for byte
(``--check`` verifies that without writing).

WHAT IS GENERATED, AND WHY THREE OF EACH
---------------------------------------
``request_<supply>.json`` + ``tb_vdd_event_<supply>.spice`` for each supply
rail of the +/-10 % axis (2.97 / 3.30 / 3.63 V). The shared circuit
(``sim/adc-power/testbench/tb_adc_power.spice``) takes its supply as the
``.param vdd_val`` the repo harness injects, and that one parameter also sets
V_REF (= V_DD), V_cm, the clock amplitudes and the input staircase. `klt
sim`'s ``corners.supply_v`` axis can only ``alter`` an instance, and
``alter`` cannot re-evaluate a ``.param`` that other expressions depend on
(verified on ngspice 46: ``alter vdd_val=2.0`` prints ``Error: no such
device or model name vdd_val`` and the run continues at the old value). So
the supply axis is carried by three wrapper bodies, one ``.param vdd_val``
each, and each request sweeps process x temperature (9 points) on its own
rail. Tool gap: 2AMLogic/klayout-tools#2725.

Each wrapper body reproduces, line for line, what ``sim/harness`` puts ahead
of the shared netlist (``runner.compose_deck``): the PVT ``.param``s, the
PDK's ``design.ngspice`` global switches (inlined -- its only
non-comment content is one ``.param`` card, copied verbatim below, so the
body needs no PDK-absolute ``.include`` that would not resolve on a batch
worker), and the ``mim_cap_*`` aliases bound to the variant's MiM stack.
`klt sim` then adds the corner's ``.lib`` sections and ``.temp`` card.

Usage::

    python3 sim/vdd-switching-event/testbench/gen_requests.py          # (re)write
    python3 sim/vdd-switching-event/testbench/gen_requests.py --check  # verify only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---- the circuit ------------------------------------------------------------
#: The shared, generator-written deck -- the SAME file sim/adc-power/ and
#: sim/adc-rail-current/ record against (sha256 43fef1c1... at the time of
#: writing; the record stamps the value it actually ran).
SHARED_NETLIST = "../../adc-power/testbench/tb_adc_power.spice"

NOMINAL_V = 3.3
SUPPLIES_V = (2.97, 3.30, 3.63)        # sim/harness/corners.supply_points(3.3, 0.10)
TEMPERATURES_C = (-40, 27, 125)

#: gf180mcuD binds MiM between Metal4/Metal5 (sim/harness/pdk.py
#: MIM_STACK_BY_VARIANT); the harness emits exactly these three aliases.
PDK_VARIANT = "gf180mcuD"
MIM_STACK = "m4m5"
MIM_DENSITIES = {"1f0": "cap_mim_1f0", "1f5": "cap_mim_1f5", "2f0": "cap_mim_2f0"}

#: Section bundles copied from sim/harness/corners.py (MOS, res, bjt, diode,
#: moscap, mimcap -- the harness's own inclusion order).
PROCESS = {
    "tt": ["typical", "res_typical", "bjt_typical", "diode_typical", "moscap_typical", "mimcap_typical"],
    "ss": ["ss", "res_ss", "bjt_ss", "diode_ss", "moscap_ss", "mimcap_ss"],
    "ff": ["ff", "res_ff", "bjt_ff", "diode_ff", "moscap_ff", "mimcap_ff"],
}

# ---- the analysis -----------------------------------------------------------
#: Same tstep / tstop as sim/adc-rail-current/ (`tran 1n 17.000u 0 2n`); ONLY
#: the maximum timestep changes, 2 ns -> 25 ps. The record and the
#: investigation note show why that is the one change that matters (the
#: window integrals move by up to 46 % between 2 ns and 10 ps; the peak by
#: < 1 %) and that the finer setting is converged (10 ps agrees with an
#: independent Gear-integration run to <= 0.6 %; 25 ps agrees with 10 ps to
#: 0.02 % on the window charge, 0.8 % on the peak). 25 ps rather than 10 ps
#: because every 10 ps run on the batch fleet aborted at 7.71885 us
#: ("Timestep too small", node pa_00); 25 ps completes to 7.8 us but then
#: aborts the same way at 15.3775 us, so the wrapper also selects Gear
#: (`.options method=gear`) -- see the investigation note, Finding 5.
ANALYSIS_ARGS = "1n 17u 0 25p"

#: 14 conversions in the same 3 -> 17 us window sim/adc-rail-current/ uses
#: (DR-0003: 16 clocks x 62.5 ns = 1 us per conversion, ph0 entered on the
#: clock edge at t = k us).
CONVERSIONS = range(3, 17)
BIT_NS = 62.5
LEAD_NS = 1.0   # every window opens 1 ns before its clock edge

#: The three array-wide bottom-plate switching events of one conversion,
#: located on a 2 ns-cap probe of the peak corner (every excursion of the
#: summed vdd current beyond 3 mA in 3 -> 7.4 us falls on one of these three
#: edges; the bit trials between them each switch one cell per side and stay
#: below 3 mA). Offsets are the clock edge, in ns after conversion start.
EVENTS = {
    "a": (0.0, "ph15->ph0: every bottom plate V_cm -> V_in (acquisition starts)"),
    "b": (4 * BIT_NS, "ph3->ph4: samp_bp falls, every bottom plate V_in -> V_cm"),
    "c": (14 * BIT_NS, "ph13->ph14: endconv releases every engaged leg back to V_cm"),
}
#: Static-current reference: ph1..ph2 (two whole bit cycles, so the
#: comparator's per-cycle latch activity is averaged over whole periods), no
#: array switching, top-plate switch still closed (it opens on the ph3 edge,
#: 1 ns after this window shuts).
BASELINE_NS = (1 * BIT_NS, 3 * BIT_NS)

BRANCHES = {"c": "vddc", "d": "vddd", "t": "vddt"}
ISUM_PAR = "par('i(vddc)+i(vddd)+i(vddt)')"
WINDOW = (3000.0, 17000.0)


def _ns(value: float) -> str:
    return f"{value:.1f}n"


def measurements() -> list[dict]:
    """Every entry is a plain top-level `.meas` card.

    The summed-branch current is measured through ngspice's ``par('...')``
    expression form (ngspice builds an internal B-source for it), not
    through a `klt sim` ``measurements[].expr``: the batch fleet's pinned
    klt image rejected ``expr`` entries outright at the time of this run
    ("each request.measurements[] entry requires 'name' and 'spice'") even
    though the submitting klt accepted them -- see the record's tool-gap
    note. A ``.meas`` card is understood by every klt version. The charges
    are integrated per branch (INTEG is linear, so their sum is the charge
    of the summed current exactly) and summed in make_record.py.
    """
    out: list[dict] = []

    def card(name, text, unit, limits=None):
        entry = {"name": name, "spice": text, "unit": unit}
        if limits:
            entry["limits"] = limits
        out.append(entry)

    lo, hi = WINDOW
    span = f"FROM={_ns(lo)} TO={_ns(hi)}"
    # --- comparability with sim/adc-rail-current/ (same window, same sum) ---
    card("isum_min", f".meas tran isum_min MIN {ISUM_PAR} {span}", "A", {"min": -0.2, "max": -0.001})
    for b, src in BRANCHES.items():
        card(f"iavg_{b}", f".meas tran iavg_{b} AVG i({src}) {span}", "A")
    # --- the never-absorbs test: MAX, which the earlier deck never took -----
    card("isum_max", f".meas tran isum_max MAX {ISUM_PAR} {span}", "A")
    for b, src in BRANCHES.items():
        card(f"imax_{b}", f".meas tran imax_{b} MAX i({src}) {span}", "A")
    card("vddm", ".meas tran vddm FIND v(vddc) AT=1u", "V")

    # --- per conversion: static baseline, then the three events -------------
    for k in CONVERSIONS:
        t0 = k * 1000.0
        blo, bhi = t0 + BASELINE_NS[0] - LEAD_NS, t0 + BASELINE_NS[1] - LEAD_NS
        for b, src in BRANCHES.items():
            card(f"ib{b}_{k:02d}",
                 f".meas tran ib{b}_{k:02d} AVG i({src}) FROM={_ns(blo)} TO={_ns(bhi)}", "A")
        for e, (offset, _desc) in EVENTS.items():
            wlo = t0 + offset - LEAD_NS
            whi = wlo + BIT_NS
            for b, src in BRANCHES.items():
                card(f"q{b}_{e}{k:02d}",
                     f".meas tran q{b}_{e}{k:02d} INTEG i({src}) FROM={_ns(wlo)} TO={_ns(whi)}", "C")
            card(f"ipk_{e}{k:02d}",
                 f".meas tran ipk_{e}{k:02d} MIN {ISUM_PAR} FROM={_ns(wlo)} TO={_ns(whi)}", "A")
    return out


def wrapper_body(supply: float) -> str:
    tag = f"{supply:.2f}".replace(".", "v")
    lines = [
        f"* tb_vdd_event_{tag} -- GENERATED by gen_requests.py, do not edit.",
        "*",
        f"* sim/vdd-switching-event/ (issue #386), supply rail {supply:.2f} V.",
        "* Everything sim/harness/runner.compose_deck puts ahead of the shared",
        "* netlist, so the circuit is the one sim/adc-power/ and",
        "* sim/adc-rail-current/ record against; `klt sim` adds the corner's",
        "* .lib sections and .temp card. See gen_requests.py for why the supply",
        "* is a per-file .param rather than a corners.supply_v alter.",
        "",
        "* ---- PVT parameters (harness: compose_deck) --------------------------",
        f".param vdd_nom={NOMINAL_V!r}",
        f".param vdd_val={supply!r}",
        "",
        f"* ---- {PDK_VARIANT} libs.tech/ngspice/design.ngspice, inlined verbatim ---",
        "* (its only non-comment content; the harness .includes the same file)",
        ".param",
        "+  sw_stat_global = 0",
        "+  sw_stat_mismatch = 0",
        "+ mc_skew = 3",
        "+ res_mc_skew = 3",
        "+ cap_mc_skew = 3",
        "+  fnoicor = 0",
        "",
        "* ---- CDAC MIM unit-cap aliases (harness: mim_wrapper_subckts) --------",
        f"* variant {PDK_VARIANT} -> MIM between {MIM_STACK}",
    ]
    for density in sorted(MIM_DENSITIES):
        subckt = f"{MIM_DENSITIES[density]}_{MIM_STACK}_noshield"
        lines += [
            f".subckt mim_cap_{density} 1 2 c_width=10u c_length=10u dtemp=0",
            f"Xmim 1 2 {subckt} c_width=c_width c_length=c_length dtemp=dtemp",
            ".ends",
        ]
    lines += [
        "",
        "* ---- integrator ------------------------------------------------------",
        "* Gear, not ngspice's default trapezoidal: the trapezoidal run aborts",
        "* (`Timestep too small`, node pa_00) at 7.71885 us with a 10 ps cap and",
        "* at 15.3775 us with a 25 ps cap on every corner. See the investigation",
        "* note, Finding 5. Gear keeps the window charges to <= 0.04 % of the",
        "* trapezoidal value where both complete.",
        ".options method=gear",
        "",
        "* ---- the shared circuit, unmodified ---------------------------------",
        f".include {SHARED_NETLIST}",
        "",
    ]
    return "\n".join(lines)


def request(supply: float) -> dict:
    tag = f"{supply:.2f}".replace(".", "v")
    return {
        "_comment": [
            "`klt sim` request -- sim/vdd-switching-event/ (issue #386). GENERATED by",
            "gen_requests.py; edit that, not this file.",
            "",
            f"Supply rail {supply:.2f} V (one request per rail -- see gen_requests.py).",
            "Measures, per conversion k = 3..16 and per array-wide switching event",
            "(a: ph15->ph0, b: ph3->ph4, c: ph13->ph14), the charge each vdd branch",
            "delivers over a one-bit-cycle window opening 1 ns before the edge",
            "(q<branch>_<event><k>, .meas INTEG), the summed-branch peak inside that",
            "window (ipk_<event><k>), and each branch's static current over ph1..ph2",
            "of the same conversion (ib<branch>_<k>) so the static charge can be",
            "subtracted. Plus MAX on all three branches and their sum (does the rail",
            "ever absorb current?), and the same 3-17 us MIN/AVG sim/adc-rail-current/",
            "reports, for a like-for-like read of what the timestep change moved.",
            "Sign: i(vddX) is current INTO the source, so delivered current is negative.",
        ],
        "netlist": f"tb_vdd_event_{tag}.spice",
        "netlist_source": "schematic",
        "engine": "ngspice",
        "models": {"pdk": PDK_VARIANT, "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": n, "sections": s} for n, s in PROCESS.items()],
            "temperature_c": list(TEMPERATURES_C),
        },
        "analysis": {"kind": "tran", "args": ANALYSIS_ARGS},
        "measurements": measurements(),
        "options": {"timeout_s": 14400, "keep_artifacts": True},
    }


def outputs() -> dict[Path, str]:
    files: dict[Path, str] = {}
    for supply in SUPPLIES_V:
        tag = f"{supply:.2f}".replace(".", "v")
        files[HERE / f"tb_vdd_event_{tag}.spice"] = wrapper_body(supply)
        files[HERE / f"request_{tag}.json"] = json.dumps(request(supply), indent=2) + "\n"
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="verify the committed files match; write nothing")
    args = parser.parse_args(argv)
    stale = []
    for path, text in outputs().items():
        current = path.read_text() if path.exists() else None
        if current != text:
            stale.append(path.name)
            if not args.check:
                path.write_text(text)
    if args.check and stale:
        print("stale (re-run gen_requests.py): " + ", ".join(stale), file=sys.stderr)
        return 1
    if not args.check:
        print(f"wrote {len(stale)} file(s)" + (": " + ", ".join(stale) if stale else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
