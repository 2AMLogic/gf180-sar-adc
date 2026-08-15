#!/usr/bin/env python3
"""Is the extraction deck's Poly2 short of the preamp load resistors enough,
on its own, to freeze the comparator's decision?

    python3 layout/adc-top/parasitics/probe_comparator_load_short.py
    python3 layout/adc-top/parasitics/probe_comparator_load_short.py \\
        --corner ss --temp 125 --vdd 2.97 --json out.json

WHY THIS EXISTS (issue #116)
----------------------------
`records/20260806-adc-block-comparator-smoke.md` recorded a reproducible
functional failure: `verify_extracted_core_conversion.py --top ADC_BLOCK`
decoded every probed transition to the SAME stuck code (1023) at two PVT
corners, independent of `dout`/`doutb` polarity, while the `ADC_TOP` control
decoded correctly. That record left the root cause explicitly open.

Issue #116 found **two** independent causes, and fixed the first:

1. **The comparator's differential inputs were floating** -- `gen_comparator.py`
   resolved `comparator.spice`'s `Vpp`/`Vpn` zero-volt input probes into net
   aliases without `prefer=`, so the merged net took the internal name
   (`preamp_in1` < `vinp`; `XCMP.preamp_in1` < `topp`) and the drawn cell
   labelled a `topp`/`topn` trunk no device sat on. Fixed at the generator;
   the extracted `ADC_BLOCK` now puts the input pair's gates on `topp__t1` /
   `topn__t0`, LVS's `pins.layout` moved 7 -> 9 and its two `topology`
   findings went to zero.

   That fix alone moved the stuck code from 1023 to **0** -- still stuck.
   Necessary, not sufficient.

2. **The preamp's two 150 kohm load resistors are not extractable devices**,
   so each shorts its own terminals and `pop`/`pon` collapse onto `vdd`
   (`layout/adc-top/adc_block.ref.spice`'s own header says so, and
   `gen_comparator.py`'s module docstring is built around it: that is why
   `comparator_nores` exists). The extracted preamp therefore has no load:
   both of its outputs sit at `vdd`, the StrongARM latch sees zero
   differential input on every strobe, and its decision is set by residual
   asymmetry rather than by the CDAC residue.

THIS SCRIPT IS THE TESTBENCH FOR (2), stated as a claim that can fail.
It runs the **schematic** comparator -- `design/comparator/comparator.spice`,
verbatim, no layout involved -- twice at one corner:

  * `as-drawn`  : the ratified netlist, `ppolyf_u_1k` loads present.
  * `loads-shorted` : the SAME netlist with the two load resistors replaced
    by 0 V sources, which is exactly what an extraction that sees the poly
    body as ordinary interconnect produces.

Each is strobed four times, alternating the input polarity
(+overdrive, -overdrive, +overdrive, -overdrive). The claim is stated on the
PREAMP OUTPUT, not on `dout`:

    as-drawn      : v(pop) - v(pon) is non-zero and FOLLOWS the input polarity
    loads-shorted : v(pop) - v(pon) is IDENTICALLY ZERO at every strobe,
                    i.e. there is no signal path from the comparator's inputs
                    to its latch at all.

**Why not `dout`.** Once the preamp differential is exactly zero the
StrongARM latch is topologically symmetric with both gates at `vdd` -- it is
METASTABLE, and whatever it then prints is numerical, not a decision. Two
observations in this repo make that concrete rather than theoretical:

  * At `tt_27c_3.30v` the shorted arm's `dout` freezes at 0 on all four
    strobes; at `ss_125c_2.97v` the SAME arm alternates 1/0/1/0 and "looks
    correct", with the preamp differential still exactly zero in both cases.
  * An earlier revision of this probe ran both arms in ONE deck. The
    metastable arm's `dout` then tracked the healthy arm's input, because
    the solver's matrix couples them -- a completely spurious "the short is
    harmless" result. That is why each arm now gets its own ngspice process.

So `dout` is reported (it is the symptom the `ADC_BLOCK` smoke test sees) but
the verdict is taken on the preamp differential, which is deterministic. If
the loads-shorted arm ever develops a non-zero preamp differential, this
explanation is wrong and the script says so (`RESULT: REFUTED`) rather than
being quietly cited.

Diagnostic only: it mints no `sim/` record and makes no spec claim. Its
output is cited by `records/20260806-adc-block-comparator-input-float.md`
and by `sim/extracted-delta-summary.md` SS6.4.
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

#: The canonical comparator netlist, read (not retyped) so this probe cannot
#: drift from the block it is making a statement about.
_CMP = REPO / "design" / "comparator" / "comparator.spice"
_BEGIN = "* --- COMPARATOR-NETLIST-BEGIN (verbatim-copied into every testbench) ---"
_END = "* --- COMPARATOR-NETLIST-END ---"

#: The two load-resistor cards, exactly as `comparator.spice` writes them.
_LOADS = (
    "Xrlp vdd pop vss ppolyf_u_1k r_width=1u r_length=150u",
    "Xrln vdd pon vss ppolyf_u_1k r_width=1u r_length=150u",
)

#: One strobe every `STROBE_NS`; the input polarity flips between strobes.
STROBE_NS = 100.0
N_STROBE = 4
#: Input overdrive, well above the block's measured offset (`sim/
#: comparator-offset/`) so a working comparator cannot get this wrong.
OVERDRIVE_V = 0.100


def comparator_block(shorted: bool) -> str:
    """`comparator.spice`'s verbatim netlist block, optionally with the two
    `ppolyf_u_1k` loads replaced by shorts.

    A 0 V source, not a `0`-value resistor: ngspice treats a zero resistance
    as an error in some versions, and a voltage source is exactly what the
    extraction's merged net is -- an ideal connection.
    """
    text = _CMP.read_text()
    body = text.split(_BEGIN, 1)[1].split(_END, 1)[0]
    if not shorted:
        return body
    for idx, card in enumerate(_LOADS):
        assert card in body, (
            f"{card!r} is not in design/comparator/comparator.spice any more -- "
            "this probe's whole point is that it edits the CANONICAL netlist, "
            "so refuse rather than silently probe something else."
        )
        node = "pop" if "pop" in card else "pon"
        body = body.replace(card, f"Vrl{idx} vdd {node} dc 0")
    return body


def compose_deck(pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                 vdd: float, shorted: bool) -> str:
    """ONE arm per deck, deliberately.

    An earlier revision of this probe put both arms in a single deck to share
    stimulus exactly. That was wrong, and wrong in a way that manufactured a
    false answer: with its loads shorted the StrongARM latch is genuinely
    METASTABLE (both its gates sit at `vdd`, its two halves are topologically
    identical), so what resolves it is whatever asymmetry the numerical solve
    happens to have. In a shared deck the solver's matrix couples the two
    arms, and the metastable arm's resolution tracked the healthy arm's
    input -- reporting "the short is harmless" from what is really solver
    crosstalk. Each arm therefore gets its own ngspice process, its own
    matrix and its own bias source; nothing is shared but the source text.
    """
    tag = "sh" if shorted else "ok"
    lines = [
        "* comparator preamp-load-short probe -- issue #116, diagnostic only",
        f"* arm={'loads-shorted' if shorted else 'as-drawn'}",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
    ]
    lines += G.pvt_preamble(pdk, corner, temp_c, vdd)
    lines.append("")

    block = comparator_block(shorted)
    for sub in ("preamp", "sarlatch", "inv", "nor2", "comparator"):
        block = re.sub(rf"\b{sub}\b", f"{tag}_{sub}", block)
    lines.append(block)

    lines.append("* ---- supplies, bias and stimulus ----")
    lines.append("vdd vdd 0 dc {vdd_val}")
    lines.append("vcm vcm 0 dc {vdd_val/2}")
    lines.append("ibias vdd ibias dc 10u")
    # Input pair: vinn held at vcm, vinp stepped +/- OVERDRIVE_V, flipping
    # polarity between strobes.
    lines.append("vinn vinn 0 dc {vcm_val}".replace("{vcm_val}", "{vdd_val/2}"))
    pts: list[str] = []
    for k in range(N_STROBE):
        sign = 1 if k % 2 == 0 else -1
        t0 = k * STROBE_NS
        lvl = f"{{vdd_val/2{'+' if sign > 0 else '-'}{OVERDRIVE_V!r}}}"
        if k == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 20:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
    pts.append(f"{N_STROBE * STROBE_NS:.1f}n {prev}")
    lines.append("vinp vinp 0 pwl(" + " ".join(pts) + ")")
    # Strobe: low (reset) for the first 60 ns of each window, high (decide)
    # for the last 40 ns -- the same one-phase convention comparator.spice
    # documents.
    clk: list[str] = ["0 0"]
    for k in range(N_STROBE):
        t0 = k * STROBE_NS
        clk += [
            f"{t0 + 59.9:.1f}n 0",
            f"{t0 + 60.0:.1f}n {{vdd_val}}",
            f"{t0 + 99.9:.1f}n {{vdd_val}}",
            f"{t0 + 100.0:.1f}n 0",
        ]
    lines.append("vclk clk 0 pwl(" + " ".join(clk) + ")")
    lines.append("")
    lines.append(
        f"X{tag} vinp vinn clk ibias {tag}_dout {tag}_doutb vdd 0 "
        f"{tag}_comparator"
    )
    lines.append("")
    lines.append(".control")
    lines.append("set numdgt=8")
    lines.append("set noaskquit")
    lines.append(f"tran 0.2n {N_STROBE * STROBE_NS:.1f}n 0 0.5n")
    for k in range(N_STROBE):
        t = k * STROBE_NS + 95.0
        lines.append(f"meas tran d{k} FIND v({tag}_dout) AT={t:.1f}n")
        lines.append(f"meas tran p{k} FIND v(x{tag}.pop) AT={t:.1f}n")
        lines.append(f"meas tran n{k} FIND v(x{tag}.pon) AT={t:.1f}n")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines) + "\n"


def _meas(out: str, name: str) -> float:
    m = re.search(rf"\b{name}\s*=\s*([-\d.eE+]+)", out)
    return float(m.group(1)) if m else float("nan")


def probe(corner_name: str = "tt", temp_c: float = 27.0,
          vdd: float = 3.3) -> dict:
    pdk = PDK.find_pdk()
    corner = C.CORNERS[corner_name]
    out: dict[bool, str] = {}
    for shorted in (False, True):
        deck = compose_deck(pdk, corner, temp_c, vdd, shorted)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cmp_load_short.spice"
            path.write_text(deck)
            proc = subprocess.run([NGSPICE, "-b", str(path)],
                                  capture_output=True, text=True, cwd=td,
                                  timeout=1800, check=False)
            out[shorted] = proc.stdout + "\n" + proc.stderr

    vth = vdd / 2.0
    strobes = []
    for k in range(N_STROBE):
        polarity = "+" if k % 2 == 0 else "-"
        ok_v, sh_v = _meas(out[False], f"d{k}"), _meas(out[True], f"d{k}")
        strobes.append({
            "strobe": k,
            "input_polarity": polarity,
            "expected_dout": 1 if polarity == "+" else 0,
            "as_drawn_dout_v": ok_v,
            "as_drawn_dout": None if ok_v != ok_v else int(ok_v > vth),
            "as_drawn_preamp_diff_v": _meas(out[False], f"p{k}")
                                      - _meas(out[False], f"n{k}"),
            "loads_shorted_dout_v": sh_v,
            "loads_shorted_dout": None if sh_v != sh_v else int(sh_v > vth),
            "loads_shorted_preamp_diff_v": _meas(out[True], f"p{k}")
                                           - _meas(out[True], f"n{k}"),
        })

    ok_bits = [s["as_drawn_dout"] for s in strobes]
    sh_bits = [s["loads_shorted_dout"] for s in strobes]
    expected = [s["expected_dout"] for s in strobes]
    as_drawn_tracks = ok_bits == expected
    # The deterministic statement: does the preamp still produce a
    # differential the latch could decide on?
    as_drawn_diff_tracks = all(
        (s["as_drawn_preamp_diff_v"] > 0) == (s["input_polarity"] == "+")
        and abs(s["as_drawn_preamp_diff_v"]) > 1e-3
        for s in strobes
    )
    shorted_diff_is_zero = all(
        abs(s["loads_shorted_preamp_diff_v"]) < 1e-9 for s in strobes
    )
    # Reported, NOT used for the verdict -- see the module docstring on why a
    # metastable latch's output is not evidence either way.
    shorted_dout_is_frozen = None not in sh_bits and len(set(sh_bits)) == 1

    if not (as_drawn_tracks and as_drawn_diff_tracks):
        verdict = "INCONCLUSIVE (the as-drawn control did not track the input)"
    elif shorted_diff_is_zero:
        verdict = "CONFIRMED"
    else:
        verdict = ("REFUTED (the loads-shorted preamp still developed a "
                   "differential output)")

    return {
        "claim": "the extraction deck's Poly2 short of the preamp's two "
                 "150 kohm ppolyf_u_1k load resistors is, on its own, enough "
                 "to freeze the comparator's decision -- pop/pon collapse "
                 "onto vdd, the StrongARM latch sees zero differential input "
                 "on every strobe, and dout stops following the input. "
                 "Issue #116: this is the SECOND of the two causes of the "
                 "ADC_BLOCK stuck-code failure recorded in "
                 "records/20260806-adc-block-comparator-smoke.md; the first "
                 "(floating differential inputs) is fixed in gen_comparator.py.",
        "netlist_provenance": "schematic -- design/comparator/comparator.spice "
                              "read verbatim; the loads-shorted arm replaces "
                              "exactly its two Xrlp/Xrln cards with 0 V "
                              "sources and changes nothing else",
        "corner": corner_name,
        "temp_c": temp_c,
        "vdd": vdd,
        "pdk": pdk.provenance(),
        "overdrive_v": OVERDRIVE_V,
        "strobes": strobes,
        "as_drawn_tracks_input": as_drawn_tracks,
        "as_drawn_preamp_diff_tracks_input": as_drawn_diff_tracks,
        "loads_shorted_preamp_diff_is_zero": shorted_diff_is_zero,
        "loads_shorted_dout_is_frozen": shorted_dout_is_frozen,
        "loads_shorted_dout_note": (
            "NOT part of the verdict. With the preamp differential at exactly "
            "zero the latch is metastable, so dout is numerical, not a "
            "decision -- it freezes at some corners and alternates at others."
        ),
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--corner", default="tt")
    ap.add_argument("--temp", type=float, default=27.0)
    ap.add_argument("--vdd", type=float, default=3.3)
    ap.add_argument("--json", help="write the full result JSON here")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py).",
              file=sys.stderr)
        return 0

    r = probe(args.corner, args.temp, args.vdd)
    if args.json:
        Path(args.json).write_text(json.dumps(r, indent=2) + "\n")

    print(f"corner            : {r['corner']} {r['temp_c']}C {r['vdd']}V")
    print(f"input overdrive   : +/-{r['overdrive_v'] * 1e3:.0f} mV")
    print("  strobe  input  expected  as-drawn dout  v(pop)-v(pon)  "
          "shorted dout  v(pop)-v(pon)")
    for s in r["strobes"]:
        print(f"  {s['strobe']:>6}  {s['input_polarity']:^5}  "
              f"{s['expected_dout']:^8}  "
              f"{s['as_drawn_dout']!r:^13}  "
              f"{s['as_drawn_preamp_diff_v']:+13.6f}  "
              f"{s['loads_shorted_dout']!r:^12}  "
              f"{s['loads_shorted_preamp_diff_v']:+13.6f}")
    print(f"as-drawn preamp diff tracks the input : "
          f"{r['as_drawn_preamp_diff_tracks_input']}")
    print(f"loads-shorted preamp diff == 0        : "
          f"{r['loads_shorted_preamp_diff_is_zero']}")
    print(f"loads-shorted dout frozen (NOT the verdict, see docstring) : "
          f"{r['loads_shorted_dout_is_frozen']}")
    print("RESULT            :", r["verdict"])
    return 0 if r["verdict"] == "CONFIRMED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
