#!/usr/bin/env python3
"""Generate the top-level SAR ADC netlist and issue #13's testbench suite.

Single source of truth for the committed artifacts listed in ``TARGETS``:

  design/adc-top/adc_top.spice                        the analog-core library
  sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice      static linearity
  sim/adc-inl-dnl/testbench/tb.json
  sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice    dynamic performance
  sim/adc-enob-fft/testbench/tb.json
  sim/adc-power/testbench/tb_adc_power.spice          power breakdown
  sim/adc-power/testbench/tb.json

``sim/harness/testbench.py`` rejects ``.include`` inside a testbench fragment
(the harness owns the includes so one fragment can sweep the whole PVT grid
unedited), so a testbench cannot pull the DUT in by reference -- it has to
carry it inline.  That is the same constraint
``design/sar-logic/gen_sar_logic.py`` already lives under, and the same answer
is used here: the copies are generated, and
``sim/tests/test_adc_top_netlist.py`` fails CI if a committed file stops
matching this generator.

Every deck this file writes is composed from three inlined sources, none of
which is retyped here:

  1. ``design/comparator/comparator.spice``  -- copied verbatim between its own
     BEGIN/END markers, so ``sim/tests/test_comparator_netlist.py`` guards it.
  2. ``design/sar-logic/gen_sar_logic.py``   -- imported and called, so the
     rung-1 controller is the same text ``sim/sar-logic-functional/`` verifies.
  3. ``library()`` below                     -- the CDAC array, its switches and
     their local drivers, which exist nowhere else yet.

Usage:
    python3 design/adc-top/gen_adc_top.py            # write the files
    python3 design/adc-top/gen_adc_top.py --check    # exit 1 if stale
    python3 design/adc-top/gen_adc_top.py --stdout library

Architecture implemented here is fixed by ratified decision records and by
already-closed evidence records; this file implements them, it does not choose
them:

  DR-0002  V_REF external, <= 240 ohm in the switching band, >= 40 nF decap
  DR-0003  external clock, M = 16 -> 16 phases per conversion, 1 MS/s
  DR-0004  3.3 V devices throughout
  DR-0007  comparator: static preamp + StrongARM latch (design/comparator/)
  DR-0007  track switch: dummy-compensated T-gate (bootstrap rejected)
  DR-0009  plain binary weighting, no redundancy
  DR-0010  fidelity ladder -- rung 1 for the sequencer, transistor level for
           everything in the analog signal path
  DR-0011  MCS / Vcm switching, top-plate sampling, free MSB, 9 switched
           weights (256..1) per side, terminating unit fixed to V_cm
  DR-0013  input drive network: series source R and a pin capacitor sized so
           R_source * (C_pin + C_in) <= 30 ns; dummy/main width ratio 7/16
  spec/cdac-sizing-memo.md Sec 4   C_u = 17.24 fF, MiM 2.0 fF/um^2 flavour
  sim/device-characterization-report.md Sec 1.2  MiM density law used to turn
           a target capacitance into a drawn square side
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# --- the two netlists this generator inlines rather than retypes ------------
_GEN_SAR = REPO / "design" / "sar-logic" / "gen_sar_logic.py"
_spec = importlib.util.spec_from_file_location("gen_sar_logic", _GEN_SAR)
sar = importlib.util.module_from_spec(_spec)
sys.modules["gen_sar_logic"] = sar
_spec.loader.exec_module(sar)

_COMPARATOR = REPO / "design" / "comparator" / "comparator.spice"
_CMP_BEGIN = "* --- COMPARATOR-NETLIST-BEGIN"
_CMP_END = "* --- COMPARATOR-NETLIST-END ---"

ADC_BEGIN = "* --- ADC-TOP-NETLIST-BEGIN (verbatim-copied into every testbench) ---"
ADC_END = "* --- ADC-TOP-NETLIST-END ---"


def comparator_block() -> str:
    """The canonical comparator netlist, verbatim, markers included."""
    lines = _COMPARATOR.read_text().splitlines(keepends=True)
    b = [i for i, ln in enumerate(lines) if ln.startswith(_CMP_BEGIN)]
    e = [i for i, ln in enumerate(lines) if ln.startswith(_CMP_END)]
    assert len(b) == 1 and len(e) == 1 and b[0] < e[0], _COMPARATOR
    return "".join(lines[b[0] : e[0] + 1])


# ---------------------------------------------------------------------------
# Sizing constants -- every one of these is consumed from a ratified record,
# not chosen here.
# ---------------------------------------------------------------------------

#: spec/cdac-sizing-memo.md Sec 4 -- the chosen unit capacitance.
C_UNIT_FF = 17.24

#: sim/device-characterization-report.md Sec 1.2 -- measured MiM 2.0 fF/um^2
#: density law for a square of side s um:  C(s) = A*s^2 + B*s  fF.
MIM_A = 1.99
MIM_B = 0.9532

#: DR-0011 -- 2^(N-1) unit positions per side: 511 switched + 1 terminating.
WEIGHTS = [2 ** (9 - i) for i in range(1, 10)]  # 256 .. 1
N_UNIT_PER_SIDE = 512

#: sim/device-switch-ron/ + sim/cdac-bit-settling/ -- the CDAC bottom-plate
#: T-gate geometry every existing settling record was taken at.
CDAC_SW_WN = "10u"
CDAC_SW_WP = "20u"

#: DR-0013 / sim/track-switch-sampling/ "cxopt" branch -- the ratified input
#: sampling switch and the drive network its gain-error number was measured at.
TRACK_SW_WN = "40u"
TRACK_SW_WP = "80u"
TRACK_SW_RD = 0.4375  # dummy/main width ratio, 7/16
TRACK_RS_OHM = 25
TRACK_CPIN = "1n"

#: DR-0002 -- reference envelope.
VREF_Z_OHM = 240
VREF_CDEC = "40n"

#: DR-0003 -- M = 16 at 1 MS/s.
CLK_PERIOD_NS = sar.CLK_PERIOD_NS  # 62.5
CONV_NS = sar.CONV_NS  # 1000
#: The comparator strobe rises in the middle of the bit cycle: the CDAC gets
#: the first half of the cycle to settle, the comparator the second half --
#: the 31.25 ns / 31.25 ns split spec/prior-art-survey.md Sec 1.4 allocates and
#: sim/comparator-regeneration/ measured its 863 ps worst-case delay against.
CMP_STROBE_NS = CLK_PERIOD_NS / 2

#: Phase index of trial i (i = 1..10):  ph(3+i).  Trial 1 is DR-0011's free
#: MSB (no array switching), trials 2..10 engage weights 256..1.
def trial_decision_ns(trial: int) -> float:
    """Time from the start of a conversion to trial `trial`'s strobe edge."""
    return (3 + trial) * CLK_PERIOD_NS + CMP_STROBE_NS


def mim_side_um(c_ff: float) -> float:
    """Drawn square side that realises `c_ff` under the measured density law."""
    return (-MIM_B + math.sqrt(MIM_B**2 + 4 * MIM_A * c_ff)) / (2 * MIM_A)


def _fmt(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}"


# ---------------------------------------------------------------------------
# library: the analog core's own subckts
# ---------------------------------------------------------------------------


def library() -> str:
    """`design/adc-top/adc_top.spice` -- the reusable analog-core subckts."""
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* adc_top.spice -- the SAR ADC analog core: CDAC array, its bottom-")
    a("* plate switches and their local drivers, and the input sampling")
    a("* switch.")
    a("*")
    a("* GENERATED by design/adc-top/gen_adc_top.py -- do not edit.")
    a("*")
    a("* This library holds ONLY what is not already owned by another")
    a("* canonical file. The comparator lives in design/comparator/")
    a("* comparator.spice and the SAR controller in design/sar-logic/")
    a("* sar_ctrl.spice; the testbenches under sim/adc-*/ inline all three.")
    a("*")
    a("* Fidelity (DR-0010): everything here is transistor level. The")
    a("* sequencer and the output register stay at rung 1 (ideal XSPICE")
    a("* primitives) because the open gf180mcu PDK ships no 3.3 V standard-")
    a("* cell library -- the gap DR-0010 names as an open precondition of")
    a("* rung 3. The T-gate DRIVERS are transistor level even so: they are")
    a("* custom cells placed with the CDAC (design/sar-logic/README.md), not")
    a("* standard cells, so the library gap does not apply to them, and they")
    a("* are the dominant digital load in a SAR ADC.")
    a("* ==================================================================")
    a("")
    a(ADC_BEGIN)
    a("* ---- switches ----------------------------------------------------")
    a("* CDAC bottom-plate T-gate. Same geometry as sim/device-switch-ron/")
    a("* and sim/cdac-bit-settling/, so R_on carries the corner sensitivity")
    a("* those records already characterised.")
    a(".subckt adc_tgate vin vout gn gp vdd wn=10u wp=20u")
    a("XN vin gn vout 0   nfet_03v3 w='wn' l=0.28u")
    a("XP vin gp vout vdd pfet_03v3 w='wp' l=0.28u")
    a(".ends adc_tgate")
    a("")
    a("* Input sampling switch: dummy-compensated T-gate, DR-0007 (track")
    a("* switch) / DR-0013. Identical device text to the `tgate_dum` subckt")
    a("* sim/track-switch-sampling/ measured the ratified gain-error number")
    a("* with, at the same default rd = 7/16.")
    a(".subckt adc_tgate_dum vin vout clk clkb vdd wn=40u wp=80u rd=0.4375")
    a("XN  vin  clk  vout 0   nfet_03v3 w='wn' l=0.28u")
    a("XP  vin  clkb vout vdd pfet_03v3 w='wp' l=0.28u")
    a("XDN vout clkb vout 0   nfet_03v3 w='wn*rd' l=0.28u")
    a("XDP vout clk  vout vdd pfet_03v3 w='wp*rd' l=0.28u")
    a(".ends adc_tgate_dum")
    a("")
    a("* Local T-gate driver -- one per leg, placed with the CDAC cell. This")
    a("* is design/sar-logic/sar_ctrl.spice's `sar_tgate_drv` promoted from")
    a("* its rung-1 ideal inverter to real devices: the controller routes")
    a("* only the active-high (NMOS gate) half of each leg, and the")
    a("* complementary PMOS gate is made here.")
    a(".subckt adc_drv a y vdd vss")
    a("Xp y a vdd vdd pfet_03v3 w=8u l=0.35u")
    a("Xn y a vss vss nfet_03v3 w=4u l=0.35u")
    a(".ends adc_drv")
    a("")
    a("* ---- one CDAC cell ------------------------------------------------")
    a("* A weight-w block of unit capacitors and its three-way bottom-plate")
    a("* switch (DR-0011): released to V_cm, or engaged to V_REF or GND.")
    a("* Exactly one leg conducts at a time -- the one-hot invariant")
    a("* sim/sar-logic-functional/ checks on the control side.")
    a(".subckt adc_cdac_cell top vref vcm vss vdd gn_rel gn_hi gn_lo")
    a("+ cw=10u cl=10u")
    a("Xc  top bp mim_cap_2f0 c_width='cw' c_length='cl'")
    a("Xdr gn_rel gp_rel vdd vss adc_drv")
    a("Xdh gn_hi  gp_hi  vdd vss adc_drv")
    a("Xdl gn_lo  gp_lo  vdd vss adc_drv")
    a(f"Xsr vcm  bp gn_rel gp_rel vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(f"Xsh vref bp gn_hi  gp_hi  vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(f"Xsl vss  bp gn_lo  gp_lo  vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(".ends adc_cdac_cell")
    a("")
    a("* ---- one array side -----------------------------------------------")
    a("* DR-0011: 2^(N-1) = 512 unit positions per side -- nine binary")
    a("* weighted blocks (256..1, 511 units) plus one terminating unit fixed")
    a(f"* to V_cm. C_u = {C_UNIT_FF} fF (spec/cdac-sizing-memo.md Sec 4), so the")
    a("* per-side track-mode capacitance is 512 * C_u = "
      f"{N_UNIT_PER_SIDE * C_UNIT_FF / 1000:.3f} pF, which is")
    a("* the C_in the ratified Input-structure row publishes.")
    a("*")
    a("* Each block is drawn as ONE capacitor of the block's total area, not")
    a("* as w separate unit cells. That is exact for this campaign and it is")
    a("* deliberate: these records verify the NOMINAL design over PVT, where")
    a("* unit-to-unit mismatch is zero by construction, and the statistical")
    a("* spread of the same array is sim/mc-cdac-mismatch/'s claim, taken at")
    a("* nominal PVT with a behavioural model because the open PDK ships no")
    a("* local capacitor mismatch model at all. Drawing 1022 unit cells here")
    a("* would multiply simulation cost by ~50x and change no number.")
    a("*")
    a("* Areas from the measured MiM density law (devchar Sec 1.2),")
    a(f"* C(s) = {MIM_A}*s^2 + {MIM_B}*s fF for a square of side s um:")
    for w in WEIGHTS + [1]:
        c = w * C_UNIT_FF
        tag = "terminating unit" if w == 1 and WEIGHTS[-1] == 1 else ""
        a(f"*   w={w:>3}  C = {c:>9.2f} fF  ->  s = {mim_side_um(c):.4f} um")
        if tag:
            break
    ports = ["top", "vref", "vcm", "vss", "vdd"]
    for w in WEIGHTS:
        ports += [f"rel_{w}", f"hi_{w}", f"lo_{w}"]
    L += sar._wrap(".subckt adc_cdac_side", ports)
    for w in WEIGHTS:
        s = mim_side_um(w * C_UNIT_FF)
        a(
            f"X{w} top vref vcm vss vdd rel_{w} hi_{w} lo_{w} adc_cdac_cell"
            f" cw={_fmt(s)}u cl={_fmt(s)}u"
        )
    s1 = mim_side_um(C_UNIT_FF)
    a("* terminating unit: DR-0011's 512th position, fixed to V_cm, never")
    a("* switched -- it is what makes the weight-1 trial resolve exactly one")
    a("* LSB of full scale rather than one part in 511.")
    a(f"Xterm top vcm mim_cap_2f0 c_width={_fmt(s1)}u c_length={_fmt(s1)}u")
    a(".ends adc_cdac_side")
    a(ADC_END)
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# the core: one complete converter, emitted flat with a tag prefix
# ---------------------------------------------------------------------------


def _core(tag: str, mode: str) -> list[str]:
    """One complete ADC: front end, array, comparator, rung-1 controller.

    `mode` is "0" (single-ended) or "{vdd_val}" (differential), the same
    encoding `sar_ctrl_a`'s `mode` pin takes.

    Supplies are brought out as four separate nodes so a power record can
    attribute current per block rather than reporting one lump:

        vddt  input sampling switch (body ties)
        vddd  CDAC bottom-plate switches and their local drivers
        vddc  comparator
        plus the vref / vcm reference sources, measured separately

    The rung-1 sequencer draws no supply current at all -- it is XSPICE
    event-driven primitives, not devices. That is a stated gap in the power
    record, not an omission.
    """
    L: list[str] = []
    a = L.append
    a(f"* ================= core {tag} ({'differential' if mode != '0' else 'single-ended'}) ==")
    a(f"v{tag}start {tag}_start 0 dc 0")
    a(f"v{tag}mode {tag}_mode 0 dc {mode}")

    # --- controller (rung 1) ------------------------------------------------
    ports = [f"{tag}_{p}" for p in sar._ports_ctrl_analog()]
    ports[0] = "clk"
    ports[1] = f"{tag}_start"
    ports[2] = f"{tag}_mode"
    ports[3] = f"{tag}_cmp"
    L += sar._wrap(f"x{tag}ctrl", ports + ["sar_ctrl_a"])

    # --- input sampling switches (DR-0013 drive network) --------------------
    a("* Input drive network, DR-0013: series source resistance and a pin")
    a("* capacitor, at the compliant point sim/track-switch-sampling/")
    a(f"* measured the ratified gain-error number at ({TRACK_RS_OHM} ohm,"
      f" {TRACK_CPIN}).")
    for s in ("p", "n"):
        a(f"R{tag}s{s} {tag}_vin{s} {tag}_pin{s} {TRACK_RS_OHM}")
        a(f"C{tag}x{s} {tag}_pin{s} 0 {TRACK_CPIN}")
        a(
            f"X{tag}sw{s} {tag}_pin{s} {tag}_top{s} {tag}_samp {tag}_sampb"
            f" vddt adc_tgate_dum wn={TRACK_SW_WN} wp={TRACK_SW_WP}"
            f" rd={TRACK_SW_RD}"
        )
    a("* The complementary sampling-clock phase is generated at rung 1 (an")
    a("* ideal inverter + dac_bridge) rather than by a real inverter, so the")
    a("* NMOS/PMOS turn-off skew is identical to the one the ratified")
    a("* DR-0013 charge-split measurement was taken with. A real driver's")
    a("* own skew would change that split -- i.e. it would silently re-open")
    a("* a closed decision -- so the sampling-switch DRIVER is carried as an")
    a("* analytic power term instead (see the power record), not simulated.")
    a(f"a{tag}sb [{tag}_samp] [{tag}_dsamp] sarl_adc")
    a(f"a{tag}si {tag}_dsamp {tag}_dsampb sarl_inv")
    a(f"a{tag}sd [{tag}_dsampb] [{tag}_sampb] sarl_dac")

    # --- the two array sides ------------------------------------------------
    for s in ("p", "n"):
        ports = [f"{tag}_top{s}", "vrefn", "vcmn", "0", "vddd"]
        for w in WEIGHTS:
            ports += [
                f"{tag}_rel_n_{w}{s}",
                f"{tag}_sel_hi_n_{w}{s}",
                f"{tag}_sel_lo_n_{w}{s}",
            ]
        L += sar._wrap(f"X{tag}arr{s}", ports + ["adc_cdac_side"])

    # --- comparator ---------------------------------------------------------
    a("* Comparator, DR-0007: static preamp + StrongARM latch. Its inputs")
    a("* ARE the CDAC top plates, so its input capacitance and its kickback")
    a("* are inside every number this deck reports, not bolted on after.")
    a(f"i{tag}b vddc {tag}_ibias dc 10u")
    a(
        f"X{tag}cmp {tag}_topp {tag}_topn cmpclk {tag}_ibias {tag}_cmp"
        f" {tag}_cmpb vddc 0 comparator"
    )

    # --- ideal shadow: the same conversion with an exact DAC ----------------
    a("* ---- the ideal shadow --------------------------------------------")
    a("* The reference this deck measures against is NOT a second simulation:")
    a("* it is the exact charge-domain result of THE DECISIONS THE REAL")
    a("* CONVERTER JUST MADE, computed from the controller's own switch-")
    a("* driver outputs. So the error node below isolates the analog error")
    a("* mechanisms (acquisition, charge injection, incomplete settling,")
    a("* reference movement, comparator kickback, top-plate parasitic")
    a("* attenuation) from decision errors, which the code check catches")
    a("* separately.")
    for s in ("p", "n"):
        terms = [
            f"{w}*((v({tag}_rel_n_{w}{s})*vcm+v({tag}_sel_hi_n_{w}{s})*vref)"
            f"/vdd_val-vcm)"
            for w in WEIGHTS
        ]
        L += sar._wrap(
            f"b{tag}dac{s} {tag}_dac{s} 0 V = (1.0/512)*(",
            [" + ".join(terms) + " )"],
        )
    a(
        f"b{tag}di {tag}_di 0 V = v({tag}_vinp)-v({tag}_vinn)"
        f"+v({tag}_dacp)-v({tag}_dacn)"
    )
    a("* Error, in LSB of this deck's own mode. Referenced to zero, not to a")
    a("* mid-rail level, so the ~1 uV `meas` result-precision floor")
    a("* (sim/harness/README.md) lands 3 decades below one LSB instead of on")
    a("* top of the quantity being measured.")
    a(
        f"b{tag}e {tag}_err 0 V = (v({tag}_topp)-v({tag}_topn)-v({tag}_di))"
        f"/lsb"
    )
    a("* Track-and-hold on the error, opened by the comparator strobe: it")
    a("* therefore holds, through each decide phase, exactly the input-")
    a("* referred error that decision was taken with. MAX over a conversion's")
    a("* trial window is that conversion's worst decision error -- one")
    a("* number instead of ten, and it cannot be fooled by the settling")
    a("* transient in between, which the hold blanks out.")
    a(f"s{tag}eh {tag}_err {tag}_errh cmpclkb 0 adc_sw")
    a(f"c{tag}eh {tag}_errh 0 0.1p")
    a(f"b{tag}ea {tag}_aerrh 0 V = abs(v({tag}_errh))")
    a("* Decoded output code (the parallel register, DR-0005).")
    terms = [f"({2 ** b})*(v({tag}_c{b})>vth ? 1 : 0)" for b in range(9, -1, -1)]
    L += sar._wrap(f"b{tag}code {tag}_code 0 V = ", [" + ".join(terms)])
    return L


def _preamble(mode_lsb: str) -> list[str]:
    """Params, models, clocks and reference network shared by every deck."""
    L: list[str] = []
    a = L.append
    a("* ---- ratiometric rails --------------------------------------------")
    a("* V_REF = V_DD. README.md note [c] makes V_REF <= V_DD a hard")
    a("* condition of the ratified spec, so a fixed 3.3 V reference is not")
    a("* legal at the 2.97 V corner; taking V_REF = V_DD keeps the deck legal")
    a("* at every point of the supply axis, and every figure below is in LSB")
    a("* of whatever full scale that point has.")
    a(".param vref={vdd_val}")
    a(".param vcm={vdd_val/2}")
    a(".param vth={vdd_val/2}")
    a(f".param lsb={mode_lsb}")
    a("")
    a(".model adc_sw sw(vt={vdd_val/2} vh=0 ron=1 roff=1e12)")
    a("")
    a("* ---- clocks --------------------------------------------------------")
    a("* DR-0003: one external clock pin at 16 x f_s. The comparator strobe")
    a("* is the same clock shifted half a bit cycle, so the CDAC settles in")
    a("* the first 31.25 ns and the comparator decides in the second -- the")
    a("* split spec/prior-art-survey.md Sec 1.4 allocates and")
    a("* sim/comparator-regeneration/ measured 863 ps of worst-case decision")
    a("* delay against.")
    a(
        f"vclk clk 0 pulse(0 {{vdd_val}} 0 100p 100p {CLK_PERIOD_NS / 2}n"
        f" {CLK_PERIOD_NS}n)"
    )
    a(
        f"vcmpclk cmpclk 0 pulse(0 {{vdd_val}} {CMP_STROBE_NS}n 100p 100p"
        f" {CLK_PERIOD_NS / 2}n {CLK_PERIOD_NS}n)"
    )
    a(
        f"vcmpclkb cmpclkb 0 pulse({{vdd_val}} 0 {CMP_STROBE_NS}n 100p 100p"
        f" {CLK_PERIOD_NS / 2}n {CLK_PERIOD_NS}n)"
    )
    a("")
    a("* ---- supplies, split per block so power is attributable -----------")
    a("vddt vddt 0 dc {vdd_val}")
    a("vddd vddd 0 dc {vdd_val}")
    a("vddc vddc 0 dc {vdd_val}")
    a("")
    a("* ---- reference network, DR-0002 -----------------------------------")
    a("* DR-0002 specifies an EXTERNAL V_REF pin with an effective source")
    a("* impedance <= 240 ohm IN THE SWITCHING BAND and >= 40 nF of external")
    a("* decoupling. Both halves of that sentence are modelled: the inductor")
    a("* in parallel with the 240 ohm makes the network 240 ohm at the")
    a("* switching band and DC-accurate below it, which is what an external")
    a("* reference buffer behind a decoupling capacitor actually is. A bare")
    a("* 240 ohm series resistor would instead assert a DC offset DR-0002")
    a("* never specified -- and, with 40 nF, a 9.6 us settling tail that")
    a("* would dominate any run shorter than ~50 us.")
    a(f"vrefs vrefs 0 dc {{vref}}")
    a(f"rref vrefs vrefn {VREF_Z_OHM}")
    a(f"lref vrefs vrefn {VREF_Z_OHM / (2 * math.pi * 16e6) * 1e6:.4f}u")
    a(f"cref vrefn 0 {VREF_CDEC}")
    a("* V_cm generation is explicitly unbudgeted work (DR-0011")
    a("* Consequences: 'a new, currently-unbudgeted deliverable for a future")
    a("* issue'), so there is no ratified envelope to model it against and it")
    a("* is an IDEAL source here. That is a stated assumption of every record")
    a("* this deck produces, not a measured result -- see the known-")
    a("* limitations section of spec/testbench-suite-memo.md.")
    a("vcms vcmn 0 dc {vcm}")
    return L


# ---------------------------------------------------------------------------
# deck 1: static linearity
# ---------------------------------------------------------------------------

#: Transitions probed by the static-linearity deck. Chosen from DR-0011's
#: actual array, not assumed binary-weighted-with-a-mid-scale-carry: see the
#: header comment the deck carries.
INL_TRANSITIONS = [
    1, 2,          # bottom of range: endpoint-fit anchor + its DNL partner
    128, 129,      # weight-128 carry
    255, 256, 257, # weight-256 carry (the sub-array MSB) and both neighbours
    384,           # weight-128 carry in the upper half of the lower segment
    511, 512, 513, # the free-MSB transition and both neighbours
    640,
    767, 768, 769, # weight-256 carry, MSB = 1
    896,
    1022, 1023,    # top of range: endpoint-fit anchor + its DNL partner
]

#: (lower, upper) transition pairs whose DNL this deck reports.
INL_DNL_PAIRS = [
    (1, 2), (128, 129), (255, 256), (256, 257), (511, 512), (512, 513),
    (767, 768), (768, 769), (1022, 1023),
]

#: Conversions of settling before the first measured one.
INL_WARMUP_CONV = 2
#: Conversions per test point: the first re-acquires the new input level, the
#: second is measured. See the deck header.
INL_CONV_PER_POINT = 2


def _first_differing_bit(k: int) -> int:
    """Bit position (9 = MSB .. 0 = LSB) that resolves the transition k-1 -> k."""
    diff = (k - 1) ^ k
    return diff.bit_length() - 1


def _inl_trial(k: int) -> int:
    """Trial index (1..10) whose decision sets transition `k`'s voltage."""
    return 10 - _first_differing_bit(k)


def _inl_conv_start_ns(idx: int) -> float:
    return (INL_WARMUP_CONV + INL_CONV_PER_POINT * idx + 1) * CONV_NS


def _inl_end_ns() -> float:
    return (INL_WARMUP_CONV + INL_CONV_PER_POINT * len(INL_TRANSITIONS)) * CONV_NS


def inl_netlist() -> str:
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_inl_dnl -- static linearity of the NOMINAL converter over")
    a("* the PVT grid (issue #13).")
    a("*")
    a("* GENERATED by design/adc-top/gen_adc_top.py -- do not edit.")
    a("*")
    a("* WHAT IS SIMULATED. One complete converter: DR-0013's input drive")
    a("* network and dummy-compensated sampling switch, DR-0011's 512-unit")
    a("* MiM array with real T-gate bottom-plate switches and real local")
    a("* drivers, DR-0007's preamp+StrongARM comparator, and the rung-1")
    a("* controller sim/sar-logic-functional/ verified. Everything in the")
    a("* analog signal path is transistor level; only the sequencer and the")
    a("* output register are ideal (DR-0010 rung 1, which that record")
    a("* assigns to exactly this campaign type).")
    a("*")
    a("* LINEARITY METHODOLOGY -- reduced code set at major-carry")
    a("* transitions, TARGETED AT DR-0011's ACTUAL ARRAY. A plain binary-")
    a("* weighted array's worst transition is the mid-scale MSB carry; this")
    a("* array is NOT that. DR-0011 samples on the top plate and resolves")
    a("* bit 1 with no array switching at all (the free MSB), so mid-scale")
    a("* (511->512) is a transition where every one of the nine switched")
    a("* weights changes state but the DECIDING bit involves no charge")
    a("* redistribution ratio. The largest ratio the array actually forms is")
    a("* the sub-array MSB, weight 256 against the remaining 255 units --")
    a("* i.e. transitions 255->256 and 767->768, one in each MSB half.")
    a("* sim/cdac-bit-settling/ independently predicts and measures the same")
    a("* weight as the slowest-settling trial (Ceq(w) = w(512-w)C_u/512 is")
    a("* maximised at w = 256), and sim/mc-cdac-mismatch/ finds the same")
    a("* code analytically worst for mismatch. All three point at the same")
    a("* place, and this deck probes it from both sides.")
    a("*")
    a("* The 18 probed transitions are therefore:")
    a("*   1, 2          bottom endpoint (endpoint-fit anchor) + its DNL pair")
    a("*   128, 129      weight-128 carry")
    a("*   255,256,257   weight-256 carry (predicted worst) and BOTH sides")
    a("*   384, 640, 896 further weight-128/64 carries spanning the range")
    a("*   511,512,513   the free-MSB transition and both sides")
    a("*   767,768,769   weight-256 carry in the MSB=1 half")
    a("*   1022, 1023    top endpoint (endpoint-fit anchor) + its DNL pair")
    a("*")
    a("* WHAT IS NOT COVERED, AND BY WHOM. This deck verifies the NOMINAL")
    a("* (typical-instance, zero-mismatch) design across the PVT grid.")
    a("* Device-to-device mismatch of the same array is sim/mc-cdac-mismatch/")
    a("* and sim/comparator-offset-mc/'s claim, evaluated at nominal PVT --")
    a("* spec/monte-carlo-methodology-memo.md Sec 4 states that division of")
    a("* labor from the other side. Neither substitutes for the other and")
    a("* neither is a duplicate of the other: one moves PVT with mismatch")
    a("* off, the other moves mismatch with PVT held.")
    a("*")
    a("* HOW LINEARITY IS MEASURED. Not by searching for each code transition")
    a("* with a fine input sweep -- that is 10-100 conversions per")
    a("* transition and it is what makes transistor-level INL/DNL")
    a("* unaffordable. Instead the deck carries an IDEAL SHADOW DAC driven")
    a("* by the controller's own switch-driver outputs, so at every")
    a("* comparator strobe the node `<tag>_err` is exactly the input-referred")
    a("* error that decision was taken with, in LSB:")
    a("*")
    a("*     err = [ (top_p - top_n) - ideal_residue(decisions so far) ] / LSB")
    a("*")
    a("* A transition's voltage error is by definition the input-referred")
    a("* error at the decision that resolves it, so ONE conversion per")
    a("* transition suffices, and the deck reads `err` at that transition's")
    a("* own deciding trial -- trial 2 for a weight-256 carry, trial 1 for")
    a("* the free-MSB transition, trial 10 for a weight-1 transition. INL is")
    a("* the endpoint-corrected error; DNL between two probed neighbours is")
    a("* their difference. Both are computed in the manifest's `measure`")
    a("* block from the measured errors, so the numbers in the record are")
    a("* not a hand calculation applied afterwards.")
    a("*")
    a("* Every mechanism that moves a real transition is inside `err`,")
    a("* because it is a difference between the real top plates and an ideal")
    a("* DAC, not between two models: acquisition error, sampling-switch")
    a("* charge injection, incomplete bit-cycle settling, reference movement")
    a("* through DR-0002's network, comparator kickback into the top plate,")
    a("* and top-plate parasitic attenuation of the DAC steps.")
    a("*")
    a("* The one input-referred term NOT inside `err` is the comparator's own")
    a("* input-referred offset. That is deliberate and it is not a gap: a")
    a("* static offset is the ratified Offset row (<= 2 LSB, digitally")
    a("* removable), measured by sim/comparator-offset-mc/, and it consumes")
    a("* no INL/DNL budget by construction. What WOULD land here is any")
    a("* CODE-DEPENDENT part of it, and in differential mode DR-0011 makes")
    a("* the comparator's input common mode constant for the whole")
    a("* conversion, so there is none to first order; in single-ended mode")
    a("* the common-mode excursion is bounded by |V_in - V_cm|/2 and halves")
    a("* every trial. spec/testbench-suite-memo.md carries that term")
    a("* explicitly rather than leaving it implied.")
    a("*")
    a("* INPUT SCHEDULE. Each probed transition gets two conversions: the")
    a("* first re-acquires the new input level (the DR-0013 network's 25 ns")
    a("* time constant needs far less, but the reference network and the")
    a("* array need to return to a steady cadence), the second is measured.")
    a("* The input sits 0.25 LSB above the ideal transition voltage so the")
    a("* expected code is unambiguous -- exactly ON a transition the last")
    a("* decision is a coin flip, which would make the code check untestable")
    a("* while changing none of the error mechanisms.")
    a("* ==================================================================")
    a("")
    L += _preamble("{vdd_val/1024}")
    a("")
    a("* ---- input: piecewise-constant ladder of probed transitions -------")
    pts: list[str] = []
    for idx, k in enumerate(INL_TRANSITIONS):
        t0 = (INL_WARMUP_CONV + INL_CONV_PER_POINT * idx) * CONV_NS
        lvl = f"{{({k}+0.25)*lsb}}"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
    pts.append(f"{_inl_end_ns():.1f}n {prev}")
    L += sar._wrap("vseinp se_vinp 0 pwl(", [" ".join(pts) + ")"])
    a("vsevinn se_vinn 0 dc {vcm}")
    a("")
    L += _core("se", "0")
    return "\n".join(L) + "\n"


def inl_manifest() -> dict:
    analyses = [f"tran 1n {_inl_end_ns() / 1000:.3f}u 0 2n"]
    measure: dict[str, str] = {}
    checks: dict[str, dict] = {}
    for idx, k in enumerate(INL_TRANSITIONS):
        t0 = _inl_conv_start_ns(idx)
        tdec = t0 + trial_decision_ns(_inl_trial(k)) - 0.05
        analyses.append(f"meas tran e{k} FIND v(se_err) AT={tdec:.3f}n")
        analyses.append(
            f"meas tran x{k} MAX v(se_aerrh) FROM={t0 + 280:.1f}n"
            f" TO={t0 + 880:.1f}n"
        )
        analyses.append(f"meas tran cd{k} FIND v(se_code) AT={t0 + 950:.1f}n")
        measure[f"terr_t{k}_lsb"] = f"e{k}"
        measure[f"decerr_t{k}_lsb"] = f"x{k}"
        measure[f"code_t{k}"] = f"cd{k}"
        checks[f"code_t{k}"] = {
            "min": k - 0.5,
            "max": k + 0.5,
            "description": (
                f"END-TO-END DECISION CHECK at transition {k}: the converter "
                f"must actually output code {k} for an input 0.25 LSB above "
                f"that transition's ideal voltage. This is the coarse (1 LSB "
                f"resolution) falsifier for the fine error measurement below "
                f"-- if the error mechanisms ever exceed a quarter LSB in the "
                f"wrong direction, or a decision is taken on a residue that "
                f"has not settled, the code moves and this fails while "
                f"terr_t{k}_lsb alone might still look small."
            ),
        }
        checks[f"decerr_t{k}_lsb"] = {
            "max": 1.0,
            "description": (
                f"Worst input-referred error over ALL TEN decisions of the "
                f"conversion at transition {k}, not just the deciding one. "
                f"Held by a track-and-hold opened by the comparator strobe, so "
                f"it reports the error each decision was actually taken with "
                f"and blanks the settling transient in between. Bounds the "
                f"early-trial errors that a plain-binary SAR with no "
                f"redundancy (DR-0009) cannot recover from."
            ),
        }
    # endpoint-corrected INL, using the two extreme probed transitions as the
    # endpoint anchors.
    lo, hi = INL_TRANSITIONS[0], INL_TRANSITIONS[-1]
    for k in INL_TRANSITIONS:
        frac = (k - lo) / (hi - lo)
        measure[f"inl_t{k}_lsb"] = f"e{k}-(e{lo}+({frac!r})*(e{hi}-e{lo}))"
        checks[f"inl_t{k}_lsb"] = {
            "min": -1.0,
            "max": 1.0,
            "description": (
                f"THE INL CLAIM at transition {k}: < 1 LSB "
                f"(README.md#target-specification). Endpoint-corrected against "
                f"the probed transitions {lo} and {hi}, i.e. with offset and "
                f"gain removed, which is the definition the ratified row's "
                f"note [d] uses when it assigns the linear part of the "
                f"sampling switch's charge injection to the Gain error, "
                f"systematic row instead of to this one."
            ),
        }
    for a_, b_ in INL_DNL_PAIRS:
        measure[f"dnl_t{a_}_t{b_}_lsb"] = f"e{b_}-e{a_}"
        checks[f"dnl_t{a_}_t{b_}_lsb"] = {
            "min": -1.0,
            "max": 1.0,
            "description": (
                f"THE DNL CLAIM across code {a_} (transitions {a_} and {b_}): "
                f"< 1 LSB. DNL is the difference of two adjacent transition "
                f"voltage errors by definition, so it is computed from the two "
                f"measured errors rather than measured again."
            ),
        }
    measure["gain_err_lsb"] = f"(e{hi}-e{lo})*({(1023 / (hi - lo))!r})"
    checks["gain_err_lsb"] = {
        "min": -3.0,
        "max": 3.0,
        "description": (
            "Converter-level systematic gain error, extrapolated from the two "
            "endpoint transitions to full scale. NOT the ratified Gain error, "
            "systematic row's claim -- that row is owned by "
            "sim/track-switch-sampling/, which measures the sampling switch's "
            "contribution across the whole permitted DR-0013 drive envelope "
            "rather than at one point of it. This is the loose cross-check "
            "that the converter as a whole is in the same place, so a bound "
            "wide enough to be a genuine falsifier and not a restatement."
        ),
    }
    measure["vref_droop_mv"] = "(vrefhi-vreflo)*1e3"
    analyses.append(
        f"meas tran vrefhi MAX v(vrefn) FROM={INL_WARMUP_CONV * CONV_NS}n"
        f" TO={_inl_end_ns()}n"
    )
    analyses.append(
        f"meas tran vreflo MIN v(vrefn) FROM={INL_WARMUP_CONV * CONV_NS}n"
        f" TO={_inl_end_ns()}n"
    )
    checks["vref_droop_mv"] = {
        "max": 50.0,
        "min_spread_pct_by_axis": {"process": 3.0},
        "description": (
            "Peak-to-peak movement of the V_REF node across the whole measured "
            "window, through DR-0002's ratified >= 40 nF / <= 240 ohm envelope. "
            "Reported because it is the one error mechanism in this deck that "
            "is a property of the USER's network rather than of the block. The "
            "process-axis floor is the corner-sensitivity assertion this deck "
            "carries: the charge the array demands per conversion is set by "
            "the MiM sections and the switch R_on, so a sabotaged corner sweep "
            "(sim/harness/README.md) collapses it."
        ),
    }
    return {
        "name": "adc-inl-dnl",
        "description": (
            "Static linearity (INL/DNL) of the nominal, zero-mismatch "
            "converter over the PVT grid: DR-0013 input network and sampling "
            "switch, DR-0011 512-unit MiM array with real T-gate bottom-plate "
            "switches and local drivers, DR-0007 preamp+StrongARM comparator, "
            "rung-1 controller (DR-0010). Reduced code set at the array's own "
            "major-carry transitions -- 18 probed transitions read at the "
            "trial that actually resolves each one, against an ideal shadow "
            "DAC driven by the controller's own switch-driver outputs."
        ),
        "claim": (
            "README.md#target-specification -- INL / DNL < 1 LSB "
            "(< 0.5 LSB stretch), untrimmed and uncalibrated, NOMINAL design "
            "over the PVT grid. The ratified row's binding condition names 3 "
            "sigma Monte Carlo mismatch, which sim/mc-cdac-mismatch/ owns; "
            "this record is the complementary environmental half of the same "
            "row (spec/monte-carlo-methodology-memo.md Sec 4). Also "
            "substantiates the note [d] claim that the endpoint-fit residual "
            "of the ratified switch and drive network is what lands in this "
            "row, the linear part having been moved to Gain error, systematic "
            "by DR-0012."
        ),
        "netlist": "tb_adc_inl_dnl.spice",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["cdac"],
        "analyses": analyses,
        "measure": measure,
        "checks": checks,
        "evidence": {
            "record_kind": "corner-matrix",
            "linearity_method": (
                "reduced-code-set-major-carry -- 18 probed transitions "
                "(1, 2, 128, 129, 255, 256, 257, 384, 511, 512, 513, 640, 767, "
                "768, 769, 896, 1022, 1023) targeted at DR-0011's OWN array: "
                "the weight-256 sub-array MSB carry at 255->256 and 767->768 "
                "(the largest charge-division ratio this array forms, and "
                "independently the slowest-settling trial per "
                "sim/cdac-bit-settling/ and the analytically worst code per "
                "sim/mc-cdac-mismatch/), the free-MSB transition at 511->512 "
                "(where all nine switched weights change state but the "
                "deciding bit forms no ratio at all, because DR-0011 samples "
                "on the top plate), weight-128 carries spanning the range, and "
                "both endpoints as the endpoint-fit anchors. Each transition "
                "is read at the trial that resolves it, from a full "
                "transistor-level conversion, against an ideal shadow DAC "
                "driven by the controller's own switch-driver outputs -- one "
                "conversion per transition, not a fine input search. NOT "
                "assumed binary-weighted-with-a-mid-scale-carry: see the "
                "netlist header."
            ),
            "notes": [
                "NOMINAL vs STATISTICAL, stated so the two campaigns are not "
                "read as duplicating or as omitting each other's coverage: "
                "this record moves PVT with mismatch off (the harness "
                "default), sim/mc-cdac-mismatch/ and sim/comparator-offset-mc/ "
                "move mismatch with PVT held at nominal. "
                "spec/monte-carlo-methodology-memo.md Sec 4 states the same "
                "division from the Monte Carlo side, and "
                "sim/cdac-bit-settling/ Sec 5.3's finding that global process "
                "variation cancels in the charge-division ratio is why "
                "neither campaign needs to be run inside the other.",
                "COMPARATOR OFFSET IS DELIBERATELY OUTSIDE THE ERROR NODE. A "
                "static input-referred offset is the ratified Offset row, "
                "measured by sim/comparator-offset-mc/, and consumes no "
                "INL/DNL budget. Only a CODE-DEPENDENT part would land here; "
                "spec/testbench-suite-memo.md carries that term explicitly.",
                "V_cm is an ideal source: DR-0011's Consequences make V_cm "
                "generation an unbudgeted future deliverable, so there is no "
                "ratified envelope to model it against. Stated assumption, "
                "not a measured result.",
                "The `cdac` corner set (7 process corners x 3 temperatures x 3 "
                "supplies = 63 points) is used rather than `mos`: this claim "
                "rides on the MiM sections, which a MOS-only sweep leaves at "
                "typical (sim/harness/README.md, 'Why the capacitor corners "
                "matter here').",
            ],
        },
    }


# ---------------------------------------------------------------------------
# deck 2: dynamic performance (coherent-sampling FFT)
# ---------------------------------------------------------------------------

#: Coherent-sampling parameters. N is a power of two so the post-processor's
#: FFT needs no zero padding (which would destroy coherence); the input-cycle
#: count is odd and prime, hence coprime to N, so the N samples land on N
#: distinct phases of the input and no sample is repeated.
FFT_N = 128
FFT_CYCLES = 61  # prime; 61/128 * 1 MHz = 476.5625 kHz, 0.953 x Nyquist
FFT_WARMUP_CONV = 2


def fft_input_hz() -> float:
    return FFT_CYCLES / FFT_N * (1e9 / CONV_NS)


def _fft_end_ns() -> float:
    return (FFT_WARMUP_CONV + FFT_N) * CONV_NS


def fft_netlist() -> str:
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_enob_fft -- dynamic performance near Nyquist, by coherently")
    a("* sampled FFT (issue #13).")
    a("*")
    a("* GENERATED by design/adc-top/gen_adc_top.py -- do not edit.")
    a("*")
    a("* Same converter as sim/adc-inl-dnl/ -- same generator, same core")
    a("* function -- driven by a full-scale sine instead of a code ladder.")
    a("*")
    a("* COHERENT SAMPLING. f_in = (M / N) * f_s with")
    a(f"*     N = {FFT_N} samples (a power of two: no zero padding, which")
    a("*         would destroy the coherence it is supposed to preserve)")
    a(f"*     M = {FFT_CYCLES} input cycles captured, prime and therefore")
    a("*         coprime to N")
    a(f"*     f_s = 1 MS/s  ->  f_in = {fft_input_hz() / 1e3:.4f} kHz")
    a(f"*         = {2 * FFT_CYCLES / FFT_N:.4f} x Nyquist (f_s/2 = 500 kHz),")
    a("*         i.e. 'near Nyquist' as the ratified ENOB and SFDR rows")
    a("*         specify")
    a("* Because gcd(M, N) = 1 the N samples fall on N distinct phases of the")
    a("* input and the capture contains a whole number of input periods, so")
    a("* the signal lands entirely in bin M with no leakage into its")
    a("* neighbours. THAT is why the window is `none`: a window is a repair")
    a("* for the discontinuity a non-integer number of periods leaves at the")
    a("* record boundary, and coherent sampling leaves none. Applying one")
    a("* here would spread the signal over three bins and understate SFDR.")
    a("*")
    a("* WHAT AN FFT OF THIS DECK DOES AND DOES NOT MEASURE. ngspice injects")
    a("* NO device noise into a transient analysis -- noise enters only")
    a("* through explicit trnoise/trrandom sources. So the non-signal bins")
    a("* of this FFT contain distortion, settling error and quantization,")
    a("* and NOT thermal or flicker noise. The ENOB claim is therefore")
    a("* composed in the record: this deck's measured distortion terms plus")
    a("* the separately measured noise terms (sim/comparator-preamp-noise/'s")
    a("* ac-based .noise result, and the kT/C term")
    a("* spec/cdac-sizing-memo.md Sec 1 sizes the array against). Reporting")
    a("* an ENOB straight off this FFT alone would overstate it by omitting")
    a("* every noise term in the budget -- see spec/testbench-suite-memo.md.")
    a("*")
    a("* The deck exports the code sequence as one `meas` per sample, so the")
    a("* FFT itself is done by sim/adc-enob-fft/testbench/analyze_fft.py over")
    a("* the runner's own raw per-corner logs -- the same post-processing")
    a("* pattern sim/comparator-offset-gof/ uses. Nothing is hand-entered:")
    a("* the script reads the logs the corner runner wrote.")
    a("* ==================================================================")
    a("")
    L += _preamble("{vdd_val/1024}")
    a("")
    a("* ---- full-scale sine, 0.5 LSB inside each rail --------------------")
    a("* Amplitude is one LSB short of a true rail-to-rail swing so the")
    a("* converter is never asked to code an out-of-range input, which would")
    a("* clip and report as distortion that the block does not have.")
    a(
        f"vsein se_vinp 0 sin({{vcm}} {{vref/2-lsb}} {fft_input_hz():.6f}"
        f" {FFT_WARMUP_CONV * CONV_NS / 1e9:.9f} 0 0)"
    )
    a("vsevinn se_vinn 0 dc {vcm}")
    a("")
    L += _core("se", "0")
    a("")
    a("* Sample-and-hold on the output code, opened at the end of each")
    a("* conversion's drdy phase, so one `meas ... FIND` per conversion")
    a("* period recovers the code sequence unambiguously.")
    a("bseph seph 0 V = v(se_drdy)")
    return "\n".join(L) + "\n"


def fft_manifest() -> dict:
    analyses = [f"tran 1n {_fft_end_ns() / 1000:.3f}u 0 2n"]
    measure: dict[str, str] = {}
    for n in range(FFT_N):
        t = (FFT_WARMUP_CONV + n) * CONV_NS + 950.0
        analyses.append(f"meas tran s{n:03d} FIND v(se_code) AT={t:.1f}n")
        measure[f"code_s{n:03d}"] = f"s{n:03d}"
    analyses.append(
        f"meas tran cmax MAX v(se_code) FROM={FFT_WARMUP_CONV * CONV_NS}n"
        f" TO={_fft_end_ns()}n"
    )
    analyses.append(
        f"meas tran cmin MIN v(se_code) FROM={FFT_WARMUP_CONV * CONV_NS}n"
        f" TO={_fft_end_ns()}n"
    )
    analyses.append(
        f"meas tran dmax MAX v(se_aerrh) FROM={FFT_WARMUP_CONV * CONV_NS + 280}n"
        f" TO={_fft_end_ns()}n"
    )
    measure["code_max"] = "cmax"
    measure["code_min"] = "cmin"
    measure["worst_decision_err_lsb"] = "dmax"
    checks = {
        "code_max": {
            "min": 1000.0,
            "max": 1023.5,
            "description": (
                "COVERAGE WITNESS, upper end: a full-scale sine must actually "
                "drive the converter near full scale. Without it an FFT taken "
                "over a stuck or heavily attenuated output would still produce "
                "a plausible-looking spectrum."
            ),
        },
        "code_min": {
            "min": -0.5,
            "max": 23.0,
            "description": "COVERAGE WITNESS, lower end.",
        },
        "worst_decision_err_lsb": {
            "max": 2.0,
            "min_spread_pct_by_axis": {"process": 3.0},
            "description": (
                "Worst input-referred error over every decision of every "
                "conversion in the capture -- the dynamic-input counterpart of "
                "sim/adc-inl-dnl/'s per-conversion measure, and this deck's "
                "corner-sensitivity assertion (a sabotaged corner sweep "
                "collapses its process-axis spread). Bounded at 2 LSB rather "
                "than 1: a slewing input is sampled at a different point of "
                "its trajectory than a DC one, so the acquisition term is "
                "legitimately larger here than in the static deck."
            ),
        },
    }
    return {
        "name": "adc-enob-fft",
        "description": (
            f"Coherently sampled {FFT_N}-point FFT of the same converter "
            f"sim/adc-inl-dnl/ measures statically, driven by a full-scale "
            f"{fft_input_hz() / 1e3:.3f} kHz sine ({FFT_CYCLES} cycles in "
            f"{FFT_N} samples at 1 MS/s, i.e. "
            f"{2 * FFT_CYCLES / FFT_N:.3f} x Nyquist). Exports the code sequence "
            "as one meas per sample; SFDR / THD / SNDR are computed by "
            "testbench/analyze_fft.py from the runner's own raw logs."
        ),
        "claim": (
            "README.md#target-specification -- ENOB @ Nyquist > 9.0 (> 9.5 "
            "stretch) and SFDR @ Nyquist >= 62 dB (>= 65 dB stretch). This "
            "deck measures the DISTORTION half of both rows; the noise half "
            "is sim/comparator-preamp-noise/'s ac-based .noise result plus "
            "the kT/C term spec/cdac-sizing-memo.md Sec 1 sizes against, "
            "because ngspice injects no device noise into a transient. "
            "spec/testbench-suite-memo.md composes the two into the ENOB "
            "figure and states why the composition, not the FFT alone, is the "
            "claim."
        ),
        "netlist": "tb_adc_enob_fft.spice",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["cdac"],
        "analyses": analyses,
        "measure": measure,
        "checks": checks,
        "evidence": {
            "record_kind": "corner-matrix",
            "fft_n": FFT_N,
            "fft_input_hz": fft_input_hz(),
            "fft_bin": FFT_CYCLES,
            "fft_window": "none",
            "fft_fs_hz": 1e9 / CONV_NS,
            "notes": [
                f"COHERENCE, stated rather than asserted: N = {FFT_N} samples "
                f"capture exactly M = {FFT_CYCLES} whole input cycles, and "
                f"gcd({FFT_CYCLES}, {FFT_N}) = 1 because {FFT_CYCLES} is "
                "prime, so the N samples land on N distinct input phases and "
                "the record contains an integer number of periods. The signal "
                "therefore occupies bin M exactly, with no boundary "
                "discontinuity to repair -- which is what makes window = none "
                "valid here. N is a power of two so the post-processor's FFT "
                "needs no zero padding, which would itself destroy coherence.",
                "This deck is run at a SUBSET of the PVT grid on purpose: it "
                "is ~4x the transient length of sim/adc-inl-dnl/, and the "
                "two-stage strategy spec/testbench-suite-memo.md states is to "
                "sweep the full grid cheaply with the static deck and spend "
                "the dynamic runs at the corners that sweep identifies -- plus "
                "the corner sim/comparator-preamp-noise/ independently finds "
                "worst for noise, because linearity-worst and noise-worst are "
                "not the same mechanism and are not assumed to coincide.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# deck 3: power
# ---------------------------------------------------------------------------

#: Input levels (in fraction of full scale) the power deck converts at, four
#: conversions each. Switching energy in an MCS array is code-dependent, so a
#: single input level would report one point of a curve as if it were the
#: worst case.
PWR_LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]
PWR_CONV_PER_LEVEL = 4
PWR_WARMUP_CONV = 2


def _pwr_level_start_ns(idx: int) -> float:
    return (PWR_WARMUP_CONV + PWR_CONV_PER_LEVEL * idx) * CONV_NS


def _pwr_end_ns() -> float:
    return (PWR_WARMUP_CONV + PWR_CONV_PER_LEVEL * len(PWR_LEVELS)) * CONV_NS


def power_netlist() -> str:
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_adc_power -- power at 1 MS/s, broken down by block (issue #13).")
    a("*")
    a("* GENERATED by design/adc-top/gen_adc_top.py -- do not edit.")
    a("*")
    a("* Same converter as sim/adc-inl-dnl/ and sim/adc-enob-fft/, from the")
    a("* same generator function, with the supplies brought out as separate")
    a("* sources so each block's current is attributable rather than lumped:")
    a("*")
    a("*   vddc   comparator (#9)      static preamp bias + latch dynamic")
    a("*   vddd   CDAC (#8)            bottom-plate T-gates and their local")
    a("*                               drivers")
    a("*   vddt   track switch (#10)   sampling-switch body ties")
    a("*   vrefs  reference            charge drawn from V_REF through")
    a("*                               DR-0002's network")
    a("*   vcms   reference            charge drawn from V_cm")
    a("*")
    a("* WHAT IS NOT MEASURED HERE, STATED PLAINLY. The SAR sequencer and")
    a("* output register are DR-0010 rung 1 -- ideal XSPICE event-driven")
    a("* primitives, which draw no supply current because they contain no")
    a("* devices. design/sar-logic/README.md says so directly: that netlist")
    a("* 'is not evidence about ... power'. The dominant digital term in a")
    a("* SAR ADC is driving the array's switch gates, and THAT is measured")
    a("* here (the local drivers are real devices on vddd); what is missing")
    a("* is the sequencer's own flip-flops and decode. It is carried as an")
    a("* analytic bound in the record, not as a measurement, and it cannot")
    a("* be closed until rung 3 -- which DR-0010 states is itself blocked on")
    a("* the open gf180mcu PDK shipping no 3.3 V standard-cell library.")
    a("* The sampling switch's own gate driver is likewise analytic: see the")
    a("* comment in the core about why its drive is kept identical to the")
    a("* one the ratified DR-0013 charge-split measurement used.")
    a("*")
    a("* INPUT LEVELS. Switching energy in an MCS array depends on the code")
    a("* being converted, so the deck converts at five input levels")
    a("* (0, 1/4, 1/2, 3/4, full scale), four conversions each, and reports")
    a("* each block's average current per level. Reporting one level would")
    a("* be reporting one point of a curve as if it were the worst case.")
    a("* ==================================================================")
    a("")
    L += _preamble("{vdd_val/1024}")
    a("")
    a("* ---- input: staircase over the code range -------------------------")
    pts: list[str] = []
    for idx, f in enumerate(PWR_LEVELS):
        t0 = _pwr_level_start_ns(idx)
        lvl = f"{{{f!r}*vref}}" if f else "0"
        if idx == 0:
            pts.append(f"0 {lvl}")
        else:
            pts.append(f"{t0 - 10:.1f}n {prev}")
            pts.append(f"{t0:.1f}n {lvl}")
        prev = lvl
    pts.append(f"{_pwr_end_ns():.1f}n {prev}")
    L += sar._wrap("vseinp se_vinp 0 pwl(", [" ".join(pts) + ")"])
    a("vsevinn se_vinn 0 dc {vcm}")
    a("")
    L += _core("se", "0")
    return "\n".join(L) + "\n"


def power_manifest() -> dict:
    analyses = [f"tran 1n {_pwr_end_ns() / 1000:.3f}u 0 2n"]
    measure: dict[str, str] = {}
    checks: dict[str, dict] = {}
    # (tag, source element name, rail-voltage multiplier, description). The
    # multiplier matters: V_cm sits at vdd/2, so charge drawn from it costs
    # half what the same charge costs on a vdd rail. Multiplying every branch
    # by one supply voltage -- the obvious shortcut -- would overstate the
    # V_cm term by 2x, and V_cm is one of the two largest terms in an MCS
    # array (DR-0011 releases every unswitched weight to it).
    blocks = [
        ("cmp", "vddc", "vddm", "comparator (#9)"),
        ("cdac", "vddd", "vddm", "CDAC switches + local drivers (#8)"),
        ("trk", "vddt", "vddm", "sampling switch (#10)"),
        ("ref", "vrefs", "vddm", "V_REF, through DR-0002's network"),
        ("vcm", "vcms", "(vddm/2)", "V_cm rail, which sits at vdd/2"),
    ]
    for idx, f in enumerate(PWR_LEVELS):
        t0 = _pwr_level_start_ns(idx) + CONV_NS  # skip the re-acquire conversion
        t1 = _pwr_level_start_ns(idx) + PWR_CONV_PER_LEVEL * CONV_NS
        tag = f"f{int(f * 100):03d}"
        for blk, src, _v, _desc in blocks:
            # ngspice names a voltage source's branch current i(<element>) --
            # the element name already carries its leading 'v'.
            analyses.append(
                f"meas tran i{blk}{tag} AVG i({src}) FROM={t0:.1f}n TO={t1:.1f}n"
            )
        for blk, _src, volts, _desc in blocks:
            measure[f"p_{blk}_{tag}_uw"] = f"-i{blk}{tag}*{volts}*1e6"
        terms = " + ".join(
            f"i{blk}{tag}*{volts}" for blk, _s, volts, _d in blocks
        )
        measure[f"p_total_{tag}_uw"] = f"-({terms})*1e6"
        checks[f"p_total_{tag}_uw"] = {
            "max": 1000.0,
            "description": (
                f"THE POWER CLAIM at input level {f:.2f} x full scale: < 1 mW "
                "at 1 MS/s (README.md#target-specification). Sum of every "
                "measured supply and reference source. The rung-1 sequencer's "
                "own flip-flop and decode power is NOT in this number and is "
                "carried analytically in the record -- the switch-gate drive, "
                "which dominates it, IS measured (vddd)."
            ),
        }
    analyses.append("meas tran vddm FIND v(vddc) AT=1u")
    measure["supply_v"] = "vddm"
    checks["p_cmp_f050_uw"] = {
        "min": 20.0,
        "max": 200.0,
        "min_spread_pct_by_axis": {"process": 3.0},
        "description": (
            "Comparator power at mid-scale. DR-0007 spends ~33 uW of static "
            "preamp bias by design (10 uA at 3.3 V) precisely to make the "
            "cheap ac-based .noise path valid, so a comparator power far below "
            "that would mean the bias is not flowing and every noise and "
            "offset record taken on this topology is measuring a different "
            "circuit. The process-axis floor is this deck's corner-sensitivity "
            "assertion."
        ),
    }
    return {
        "name": "adc-power",
        "description": (
            "Power at 1 MS/s, broken down by block, over the PVT grid. Same "
            "converter as sim/adc-inl-dnl/, with per-block supply sources "
            "(comparator / CDAC switches + drivers / sampling switch / V_REF / "
            "V_cm) so the breakdown is measured rather than apportioned. Five "
            "input levels, because MCS switching energy is code-dependent."
        ),
        "claim": (
            "README.md#target-specification -- Power @ 1 MS/s < 1 mW "
            "(< 500 uW stretch), binding corner ff_125c_3.63v. Reported per "
            "block so each block's own worst-power corner can be named rather "
            "than one corner being reused across all four."
        ),
        "netlist": "tb_adc_power.spice",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["cdac"],
        "analyses": analyses,
        "measure": measure,
        "checks": checks,
        "evidence": {
            "record_kind": "corner-matrix",
            "notes": [
                "The rung-1 sequencer contributes zero measured current "
                "because it contains no devices (DR-0010 rung 1, XSPICE "
                "event-driven primitives). This is a STATED GAP, closed only "
                "at rung 3, which DR-0010 in turn states is blocked on the "
                "open gf180mcu PDK shipping no 3.3 V standard-cell library. "
                "The dominant digital term -- driving the 54 T-gate legs of "
                "the array -- IS measured, on vddd, because those drivers are "
                "custom cells placed with the CDAC rather than standard cells.",
                "Each block's worst-power corner is reported separately in the "
                "record. They are not assumed to coincide: static bias current "
                "and dynamic switching charge move in opposite directions with "
                "process and temperature, so a single 'worst corner' reused "
                "across four blocks would understate at least one of them.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------


def _deck(body: str) -> str:
    """A complete testbench fragment: body + the three inlined netlists."""
    return (
        body
        + "\n"
        + "* ==================================================================\n"
        + "* The three netlists below are COPIES, kept honest by unit tests:\n"
        + "*   design/comparator/comparator.spice   (test_comparator_netlist)\n"
        + "*   design/sar-logic/sar_ctrl.spice      (test_sar_logic_netlist)\n"
        + "*   design/adc-top/adc_top.spice         (test_adc_top_netlist)\n"
        + "* sim/harness/testbench.py rejects .include in a fragment, so a\n"
        + "* testbench has to carry its DUT inline; generating the copies is\n"
        + "* what stops them drifting from the design they claim to verify.\n"
        + "* ==================================================================\n\n"
        + comparator_block()
        + "\n"
        + sar.library()
        + "\n"
        + library()
    )


def inl_deck() -> str:
    return _deck(inl_netlist())


def fft_deck() -> str:
    return _deck(fft_netlist())


def power_deck() -> str:
    return _deck(power_netlist())


def _json(manifest: dict) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def inl_json() -> str:
    return _json(inl_manifest())


def fft_json() -> str:
    return _json(fft_manifest())


def power_json() -> str:
    return _json(power_manifest())


TARGETS = {
    "library": ("design/adc-top/adc_top.spice", library),
    "inl": ("sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice", inl_deck),
    "inl-json": ("sim/adc-inl-dnl/testbench/tb.json", inl_json),
    "fft": ("sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice", fft_deck),
    "fft-json": ("sim/adc-enob-fft/testbench/tb.json", fft_json),
    "power": ("sim/adc-power/testbench/tb_adc_power.spice", power_deck),
    "power-json": ("sim/adc-power/testbench/tb.json", power_json),
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true", help="exit 1 if any file is stale")
    p.add_argument("--stdout", metavar="TARGET", choices=sorted(TARGETS))
    args = p.parse_args(argv)

    if args.stdout:
        sys.stdout.write(TARGETS[args.stdout][1]())
        return 0

    stale = []
    for name, (rel, fn) in sorted(TARGETS.items()):
        path = REPO / rel
        text = fn()
        if args.check:
            if not path.is_file() or path.read_text() != text:
                stale.append(rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_text() == text:
            print(f"  unchanged  {rel}")
            continue
        path.write_text(text)
        print(f"  wrote      {rel}")
    if args.check:
        for rel in stale:
            print(f"STALE: {rel}", file=sys.stderr)
        return 1 if stale else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
