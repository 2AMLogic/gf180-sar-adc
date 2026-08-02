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
  DR-0011  MCS / Vcm switching, free MSB, 9 switched weights (256..1) per
           side, terminating unit fixed to V_cm -- superseded by DR-0014 on
           the sampling phase only, every other decision re-ratified
  DR-0014  BOTTOM-PLATE sampling: a fourth leg to V_in per cell, one
           top-plate switch to V_cm per side which opens FIRST, and the
           dedicated top-plate sampling switch removed
  DR-0013  input drive network: series source R and a pin capacitor sized so
           R_source * (C_pin + C_in) <= 30 ns. The dummy/main width ratio of
           7/16 belonged to the dedicated sampling switch DR-0014 removes;
           the drive contract stands, the dummy ratio no longer applies
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

#: DR-0013 / sim/track-switch-sampling/ "cxopt" branch -- the dedicated
#: top-plate sampling switch and the drive network its gain-error number was
#: measured at. DR-0014 REMOVES that switch from the converter: the input now
#: reaches the array through the nine cell T-gates of each side's fourth leg.
#: The geometry is kept here because sim/top-plate-cpar/ still instantiates it
#: -- that deck measures the load set of the SUPERSEDED topology, which is the
#: evidence DR-0014's Context rests on, and #61 owns re-taking it on the new
#: topology. TRACK_RS_OHM / TRACK_CPIN are unchanged and still in the
#: converter: DR-0014 leaves DR-0013's drive contract standing.
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
    a("* adc_top.spice -- the SAR ADC analog core: CDAC array, its four-leg")
    a("* bottom-plate switch network and the local drivers, and the")
    a("* top-plate V_cm switch DR-0014's sampling phase turns on.")
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
    a("* Dedicated top-plate input sampling switch: dummy-compensated T-gate,")
    a("* DR-0007 (track switch) / DR-0013. NO LONGER IN THE CONVERTER --")
    a("* DR-0014 samples on the bottom plates, so the input reaches the array")
    a("* through the nine cell T-gates of each side's fourth leg and this")
    a("* switch is gone from adc_cdac_side and from every adc-* deck. It is")
    a("* kept in the library because sim/top-plate-cpar/ instantiates it to")
    a("* measure the SUPERSEDED topology's top-plate load set -- the measured")
    a("* evidence DR-0014's Context rests on -- and because #61 re-takes that")
    a("* measurement on the new topology from this same library. Identical")
    a("* device text to the `tgate_dum` subckt sim/track-switch-sampling/")
    a("* measured the ratified gain-error number with, at the same default")
    a("* rd = 7/16.")
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
    a("* ---- top-plate V_cm switch (DR-0014) ------------------------------")
    a("* One per array side. Closed for ph0..ph2 and OPENED ON THE EDGE INTO")
    a("* ph3 -- that edge is the sampling instant, and it is the reason the")
    a("* whole record exists: with the top plate released before the bottom")
    a("* plates move, the sampled input and every subsequent DAC step land in")
    a("* the same numerator over the same denominator, so C_arr/(C_arr+C_par)")
    a("* cancels from the comparator's decision instead of dividing the DAC")
    a("* step alone.")
    a("*")
    a("* Plain T-gate at the CDAC bottom-plate geometry -- deliberately NOT")
    a("* dummy-compensated, and this is a choice, not an omission. DR-0013's")
    a("* dummies exist because the OLD sampling switch opened with an")
    a("* input-dependent voltage on its channel. This switch always opens")
    a("* with its node at V_cm, so its injection is signal-independent: a")
    a("* fixed offset, common to both sides, which differential operation")
    a("* removes and which DR-0007's Offset row already covers. Adding")
    a("* dummies would instead re-hang two permanently-connected MOS")
    a("* capacitors on the top plate -- the 194 fF sim/top-plate-cpar/")
    a("* measured as 66 % of C_par -- which no longer costs gain under this")
    a("* record but does cost bit-trial settling. The residual side-to-side")
    a("* MISMATCH of this injection is one of the four things DR-0014's")
    a("* Consequences require #61 to measure; it is not claimed here.")
    a("*")
    a("* Sizing, from the acquisition it has to support: it holds the top")
    a("* node at V_cm while the bottom plates slew, so its own time constant")
    a("* is R_on * (C_arr + C_par) = 570 ohm * 9.1 pF = 5.2 ns worst case,")
    a("* i.e. 36 tau inside the 187.5 ns acquisition window and 0.21 of the")
    a("* input network's own 25 ns tau. The lag it leaves at the sampling")
    a("* instant is (tau_sw/tau_in)*exp(-7.5) = 1.1e-4 of the input step --")
    a("* 0.12 LSB at full scale, and LINEAR in the input, so it is a gain")
    a("* term and not a linearity term. Widening it would buy that back at")
    a("* the price of more injection to mismatch, which is the term this")
    a("* topology cannot cancel.")
    a(".subckt adc_tp_sw top vcm gn vdd vss")
    a("Xd gn gp vdd vss adc_drv")
    a(f"Xs vcm top gn gp vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(".ends adc_tp_sw")
    a("")
    a("* ---- one CDAC cell ------------------------------------------------")
    a("* A weight-w block of unit capacitors and its FOUR-way bottom-plate")
    a("* switch: driven to V_in while sampling (DR-0014's fourth leg),")
    a("* released to V_cm, or engaged to V_REF or GND (DR-0011, unchanged).")
    a("* Exactly one leg conducts at a time -- the four-leg one-hot invariant")
    a("* sim/sar-logic-functional/ checks on the control side.")
    a("*")
    a("* The fourth leg is the same T-gate as the other three. That is what")
    a("* makes the cell one repeated device rather than four different ones,")
    a("* and it is why the Input-structure row's series R_on has to be")
    a("* re-measured rather than carried over (DR-0014, and #61 owns it): the")
    a("* input now reaches the array through nine of these in parallel,")
    a("* instead of through one dedicated 40u/80u switch.")
    a(".subckt adc_cdac_cell top vin vref vcm vss vdd gn_in gn_rel gn_hi gn_lo")
    a("+ cw=10u cl=10u")
    a("Xc  top bp mim_cap_2f0 c_width='cw' c_length='cl'")
    a("Xdi gn_in  gp_in  vdd vss adc_drv")
    a("Xdr gn_rel gp_rel vdd vss adc_drv")
    a("Xdh gn_hi  gp_hi  vdd vss adc_drv")
    a("Xdl gn_lo  gp_lo  vdd vss adc_drv")
    a(f"Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
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
    a("*")
    a("* `sel_in` is ONE port, not nine: every cell's fourth leg is driven by")
    a("* the same broadcast control, because all bottom plates sample")
    a("* together by construction (design/sar-logic/README.md states the same")
    a("* bus-width argument from the controller side). The per-cell decode is")
    a("* still four one-hot legs; one of the four is shared.")
    ports = ["top", "vin", "vref", "vcm", "vss", "vdd", "sel_in"]
    for w in WEIGHTS:
        ports += [f"rel_{w}", f"hi_{w}", f"lo_{w}"]
    L += sar._wrap(".subckt adc_cdac_side", ports)
    for w in WEIGHTS:
        s = mim_side_um(w * C_UNIT_FF)
        a(
            f"X{w} top vin vref vcm vss vdd sel_in rel_{w} hi_{w} lo_{w}"
            f" adc_cdac_cell cw={_fmt(s)}u cl={_fmt(s)}u"
        )
    s1 = mim_side_um(C_UNIT_FF)
    a("* terminating unit: DR-0011's 512th position, fixed to V_cm, never")
    a("* switched -- it is what makes the weight-1 trial resolve exactly one")
    a("* LSB of full scale rather than one part in 511. Under DR-0014 it is")
    a("* also the one unit that does NOT track V_in during acquisition, so")
    a("* the capacitance the input PIN drives is 511*C_u = 8.810 pF while the")
    a("* C_arr the charge balance runs on is still 512*C_u = 8.827 pF. The")
    a("* 0.2 % difference sits inside the ratified Input-structure row's own")
    a("* rounding and does not change DR-0013's <= 30 ns drive contract.")
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

        vddt  top-plate V_cm switch and its driver (DR-0014); before that
              record this rail supplied the dedicated top-plate sampling
              switch, i.e. it still means "the switch that defines the
              sampling instant"
        vddd  CDAC bottom-plate switches and their local drivers -- now four
              legs per cell, so DR-0014's fourth (V_in) leg and its driver
              are measured here rather than analytically
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

    # --- input drive network + DR-0014's top-plate switches -----------------
    a("* Input drive network, DR-0013: series source resistance and a pin")
    a("* capacitor, at the compliant point sim/track-switch-sampling/")
    a(f"* measured the ratified gain-error number at ({TRACK_RS_OHM} ohm,"
      f" {TRACK_CPIN}). DR-0014 leaves that contract standing and removes the")
    a("* DEDICATED sampling switch that used to sit behind it: the pin now")
    a("* drives the array's fourth-leg T-gates directly, nine per side.")
    for s in ("p", "n"):
        a(f"R{tag}s{s} {tag}_vin{s} {tag}_pin{s} {TRACK_RS_OHM}")
        a(f"C{tag}x{s} {tag}_pin{s} 0 {TRACK_CPIN}")
    a("* The top-plate V_cm switch, one per side (DR-0014). It opens on the")
    a("* edge into ph3 -- one whole bit cycle before the bottom plates leave")
    a("* V_in -- and THAT edge is the sampling instant. Both sides are driven")
    a("* by the SAME control net: their skew is precisely the term this")
    a("* topology cannot cancel, so it is not manufactured here by routing")
    a("* two copies. Body ties go to vddt, which used to supply the")
    a("* dedicated sampling switch, so the power record's `trk` block still")
    a("* reports 'the switch that defines the sampling instant'.")
    for s in ("p", "n"):
        a(
            f"X{tag}tsw{s} {tag}_top{s} vcmn {tag}_samp_tp_n vddt 0"
            f" adc_tp_sw"
        )

    # --- the two array sides ------------------------------------------------
    for s in ("p", "n"):
        ports = [
            f"{tag}_top{s}",
            f"{tag}_pin{s}",
            "vrefn",
            "vcmn",
            "0",
            "vddd",
            f"{tag}_sel_in_n",
        ]
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
    a("* Wired conventionally (top_p to the + input) even though DR-0014")
    a("* inverts the residue: the inversion is taken once inside the")
    a("* controller instead, so `cmp` keeps meaning 'top_p > top_n'")
    a("* everywhere in this repo. Under this record the comparator's own")
    a("* input capacitance is still ON the sampling node, but it no longer")
    a("* divides the DAC step against an undivided sampled input -- both are")
    a("* now over the same C_arr + C_par, which is the term that cancels.")
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
            f"{w}*((v({tag}_rel_n_{w}{s})*vcm+v({tag}_sel_hi_n_{w}{s})*vref"
            f"+v({tag}_sel_in_n)*v({tag}_vin{s}))/vdd_val-vcm)"
            for w in WEIGHTS
        ]
        L += sar._wrap(
            f"b{tag}dac{s} {tag}_dac{s} 0 V = (1.0/512)*(",
            [" + ".join(terms) + " )"],
        )
    a("* The ideal differential top plate under DR-0014 bottom-plate")
    a("* sampling. The sampled input enters INVERTED about V_cm -- charge")
    a("* conservation on a top node released at V_cm gives")
    a("*   V_top,s = V_cm + k*[(V_cm - V_in,s) + dac_s],  k = C_arr/(C_arr+C_par)")
    a("* -- so the ideal (k = 1) differential residue is")
    a("*   di = (V_inn - V_inp) + dac_p - dac_n")
    a("* where under DR-0011 it was +(V_inp - V_inn) + dac_p - dac_n. This")
    a("* one sign is the whole behavioural consequence of the record, and it")
    a("* is why the controller inverts the comparator once at its own")
    a("* boundary (design/sar-logic/, `dec = !cmp`).")
    a(
        f"b{tag}di {tag}_di 0 V = v({tag}_vinn)-v({tag}_vinp)"
        f"+v({tag}_dacp)-v({tag}_dacn)"
    )
    a("* Error, in LSB of this deck's own mode. Referenced to zero, not to a")
    a("* mid-rail level, so the ~1 uV `meas` result-precision floor")
    a("* (sim/harness/README.md) lands 3 decades below one LSB instead of on")
    a("* top of the quantity being measured.")
    a("*")
    a("* NEGATED with respect to the superseded version, deliberately: the")
    a("* residue now moves OPPOSITE the input, so d(top_p-top_n)/dV_in = -1")
    a("* and an INPUT-REFERRED error is (ideal - actual), not (actual -")
    a("* ideal). Keeping the node input-referred is what makes this deck's")
    a("* terr/INL numbers comparable in sign with the records taken before")
    a("* DR-0014 instead of silently flipping every one of them.")
    a(
        f"b{tag}e {tag}_err 0 V = (v({tag}_di)-(v({tag}_topp)-v({tag}_topn)))"
        f"/lsb"
    )
    a("* The error, GATED TO THE DECIDE PHASES ONLY. A comparator decides on")
    a("* the strobe, so the only instants at which the input-referred error")
    a("* matters are the ten strobe-high windows; in between, the residue is")
    a("* still settling and its excursion is a transient nobody samples. So")
    a("* this node is |err| while cmpclk is high and zero otherwise, and MAX")
    a("* over a conversion's trial window is that conversion's WORST DECISION")
    a("* ERROR -- one number instead of ten.")
    a("*")
    a("* An earlier draft used a track-and-hold switched by cmpclkb instead.")
    a("* That was wrong in a way worth recording: the T/H TRACKS during the")
    a("* settling half of each bit cycle, so a MAX over the same window picked")
    a("* up the settling transient it was supposed to blank -- reporting ~300")
    a("* LSB where the decisions were actually taken within a few LSB. Gating")
    a("* is the correct primitive here; holding is not.")
    a(f"b{tag}ea {tag}_aerrh 0 V = abs(v({tag}_err))*(v(cmpclk)>vth ? 1 : 0)")
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

#: Tolerance on the end-to-end code check, in LSB. Sized to absorb the gain
#: error the SUPERSEDED top-plate-sampling topology measured (~31 LSB full
#: scale) plus margin, so this check tests liveness and tracking rather than
#: restating the gain claim. The LINEARITY bound (inl_t<k>_lsb) is NOT widened:
#: it stays at the ratified 1 LSB.
#:
#: DELIBERATELY NOT TIGHTENED FOR DR-0014. That record's derivation says the
#: term this window was opened for should now cancel, which would allow a much
#: tighter window -- but tightening it here would be asserting the outcome of a
#: run that has not been taken. #61 owns the re-run on this topology and owns
#: closing the window against what it measures. Loosening is what CLAUDE.md
#: forbids; leaving an inherited bound in place while the evidence is re-taken
#: is not.
CODE_TOL_LSB = 45.0

#: Bound on the worst per-decision input-referred error, in LSB. Same argument
#: and the same inheritance: an early trial's residue carried the full gain
#: error under the superseded topology, so this could not be tighter than the
#: gain term without restating it, and it is left where it was until #61
#: measures the new one.
DECERR_MAX_LSB = 45.0

#: Conversions of settling before the first measured one.
INL_WARMUP_CONV = 2
#: Conversions per test point. ONE: the input steps 10 ns before the
#: conversion boundary and DR-0014's acquisition window -- ph0..ph2, which is
#: where the input has to be settled, because the top-plate switch opens on the
#: edge into ph3 -- is 187.5 ns, i.e. 7.5 tau of DR-0013's 25 ns input network.
#: The ladder's largest step between adjacent probed transitions is 126 LSB, so
#: the residual acquisition error is 126 * exp(-7.5) = 0.07 LSB, an order under
#: the 1 LSB claim. (Under the superseded top-plate sampling phase the whole
#: 250 ns sample window was acquisition time and the same number was 0.006 LSB;
#: DR-0014 spends the last of the four clocks isolating the top plate instead,
#: and this is what that costs.) An earlier draft spent a second, un-measured
#: conversion per
#: point re-acquiring the level; that doubled the cost of the single most
#: expensive deck in the suite to buy 0.006 LSB, and it made the deck LESS
#: representative, not more: converting the same code twice in a row lets the
#: reference network (DR-0002, tau = 9.6 us, which never settles between
#: conversions in any case) see a repeat it would never see in service.
INL_CONV_PER_POINT = 1


def _first_differing_bit(k: int) -> int:
    """Bit position (9 = MSB .. 0 = LSB) that resolves the transition k-1 -> k."""
    diff = (k - 1) ^ k
    return diff.bit_length() - 1


def _inl_trial(k: int) -> int:
    """Trial index (1..10) whose decision sets transition `k`'s voltage."""
    return 10 - _first_differing_bit(k)


def _inl_conv_start_ns(idx: int) -> float:
    """Start of the conversion that is MEASURED for probed transition `idx`.

    The input ladder steps 10 ns before conversion
    ``INL_WARMUP_CONV + INL_CONV_PER_POINT*idx``; the measured conversion is
    the LAST of that point's group, so the offset is
    ``INL_CONV_PER_POINT - 1``, not a hardcoded 1. (With the earlier
    two-conversion schedule the two happened to be the same number, which is
    exactly why an off-by-one hid here when the schedule changed: DNL jumped to
    2-5 LSB because every point was being read one conversion late, i.e.
    against the NEXT point's input.)
    """
    return (
        INL_WARMUP_CONV + INL_CONV_PER_POINT * idx + INL_CONV_PER_POINT - 1
    ) * CONV_NS


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
    a("* network, DR-0011's 512-unit MiM array with real T-gate bottom-plate")
    a("* switches and real local drivers -- FOUR legs per cell under DR-0014,")
    a("* the fourth carrying V_in -- DR-0014's per-side top-plate V_cm switch,")
    a("* DR-0007's preamp+StrongARM comparator, and the rung-1")
    a("* controller sim/sar-logic-functional/ verified. Everything in the")
    a("* analog signal path is transistor level; only the sequencer and the")
    a("* output register are ideal (DR-0010 rung 1, which that record")
    a("* assigns to exactly this campaign type).")
    a("*")
    a("* SAMPLING PHASE (DR-0014, superseding DR-0011's). ph0..ph2 acquire")
    a("* with the top plates held at V_cm and every bottom plate on V_in;")
    a("* the top-plate switch opens on the edge into ph3 and THAT is the")
    a("* sampling instant; the bottom plates leave V_in for V_cm a whole bit")
    a("* cycle later, on the edge into ph4, onto an already-isolated node.")
    a("* Nothing else about the conversion changes: M = 16, 1 us, free MSB.")
    a("*")
    a("* LINEARITY METHODOLOGY -- reduced code set at major-carry")
    a("* transitions, TARGETED AT THIS ARRAY. A plain binary-")
    a("* weighted array's worst transition is the mid-scale MSB carry; this")
    a("* array is NOT that. It resolves")
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
    a("*     err = [ ideal_residue(decisions so far) - (top_p - top_n) ] / LSB")
    a("*")
    a("* (the subtraction is that way round because DR-0014's residue moves")
    a("* OPPOSITE the input -- see the error node's own comment; the node")
    a("* stays input-referred, so its sign is comparable with the records")
    a("* taken before that change.)")
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
    a("* DAC, not between two models: acquisition error, the top-plate")
    a("* switch's charge injection and its side-to-side mismatch, the")
    a("* bottom-plate input legs' injection after that switch has already")
    a("* opened, incomplete bit-cycle settling, reference movement through")
    a("* DR-0002's network, comparator kickback into the top plate, and any")
    a("* RESIDUAL top-plate parasitic term -- which DR-0014's derivation says")
    a("* should now cancel to the accuracy the two sides match, and which")
    a("* this deck is therefore the direct test of. That test is #61's to")
    a("* run: no record on this topology exists yet.")
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
    a("* INPUT SCHEDULE. One conversion per probed transition. The input")
    a("* steps 10 ns before the conversion boundary and the conversion's own")
    a("* 4-clock sample phase is 250 ns = 10 tau of DR-0013's 25 ns input")
    a("* network, while the ladder's largest step between adjacent probed")
    a("* transitions is 126 LSB -- so the residual acquisition error is")
    a("* 126*exp(-10) = 0.006 LSB, three orders under the claim. Spending a")
    a("* second, un-measured conversion per point to re-acquire would double")
    a("* the cost of the most expensive deck in this suite for that 0.006 LSB,")
    a("* and would make the deck LESS representative: converting the same code")
    a("* twice in a row lets DR-0002's reference network (tau = 9.6 us, which")
    a("* never settles between conversions in any case) see a repeat it would")
    a("* never see in service.")
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
            "min": k - CODE_TOL_LSB,
            "max": k + CODE_TOL_LSB,
            "description": (
                f"END-TO-END LIVENESS CHECK at transition {k}: the converter "
                f"must actually produce a code near {k} for an input 0.25 LSB "
                f"above that transition's ideal voltage -- i.e. the whole "
                f"chain (acquire, ten trials, decode) ran and tracked the "
                f"input. The tolerance is +/-{CODE_TOL_LSB:.0f} LSB rather "
                f"than +/-0.5 because the converter carries a MEASURED "
                f"converter-level gain error of ~31 LSB full-scale, dominated "
                f"by top-plate parasitic loading of the array by the "
                f"comparator's own input capacitance (DR-0011 samples on the "
                f"top plate and the comparator inputs ARE that node). That is "
                f"a gain term, reported by gain_err_lsb and analysed in "
                f"spec/testbench-suite-memo.md; the LINEARITY claim is "
                f"inl_t{k}_lsb below, which is evaluated after gain and offset "
                f"are removed and is NOT relaxed here."
            ),
        }
        checks[f"decerr_t{k}_lsb"] = {
            "max": DECERR_MAX_LSB,
            "description": (
                f"Worst input-referred error over ALL TEN decisions of the "
                f"conversion at transition {k}, not just the deciding one: "
                f"|err| gated to the ten comparator-strobe windows, so it "
                f"reports the error each decision was actually taken with and "
                f"ignores the settling excursion in between, which nobody "
                f"samples. Bounds the early-trial errors that a plain-binary "
                f"SAR with no redundancy (DR-0009) cannot recover from. The "
                f"bound is the same ~31 LSB gain term the code check above "
                f"absorbs, with margin -- an early trial's residue carries the "
                f"full gain error, so this cannot be tighter than it without "
                f"restating the gain claim."
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
        "min": -60.0,
        "max": 60.0,
        "description": (
            "Converter-level systematic gain error, extrapolated from the two "
            "endpoint transitions to full scale. NOT the ratified Gain error, "
            "systematic row's claim -- that row is scoped by DR-0012/DR-0013 "
            "to the sampling switch's charge injection, and DR-0014 "
            "invalidated the 0.421 LSB evidence behind it by removing the "
            "switch it was measured on. Under the SUPERSEDED top-plate "
            "sampling phase this measurement was a different, larger term the "
            "ratified table has no row for at all -- top-plate parasitic "
            "loading, C_par/(C_arr + C_par), measured end-to-end at ~3 % of "
            "full scale and independently by sim/top-plate-cpar/ -- and that "
            "is what DR-0014 exists to remove. Under THIS topology both the "
            "sampled input and every DAC step sit over the same C_arr + C_par, "
            "so the derivation says the term should cancel to the accuracy the "
            "two sides match, and this number becomes the direct test of the "
            "record rather than a report of a known defect. It is a "
            "DERIVATION until #61 re-runs this deck: no measurement on this "
            "topology exists. The +/-60 LSB window is inherited unchanged from "
            "the superseded run and is deliberately not tightened here, "
            "because tightening it would assert the outcome of that run in "
            "advance. See spec/testbench-suite-memo.md and DR-0014."
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
            "converter over the PVT grid: DR-0013 input network, DR-0011 "
            "512-unit MiM array with real T-gate bottom-plate switches and "
            "local drivers (four legs per cell under DR-0014, the fourth "
            "carrying V_in), DR-0014's per-side top-plate V_cm switch and its "
            "two-phase sample, DR-0007 preamp+StrongARM comparator, "
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
                "deciding bit forms no ratio at all, because the free MSB is "
                "decided before any array switching -- a property DR-0014 "
                "keeps), weight-128 carries spanning the range, and "
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
FFT_N = 64
FFT_CYCLES = 31  # prime; 31/64 * 1 MHz = 484.375 kHz, 0.969 x Nyquist

#: Sine amplitude as a fraction of half full scale. Backed off from 1.0 for a
#: measured reason, not as a habit: under the SUPERSEDED top-plate sampling
#: phase the converter carried a ~3 % gain error (see inl_manifest's
#: gain_err_lsb), so a true full-scale drive would CLIP at both rails and the
#: FFT would report clipping as distortion the block does not have. 0.94 clears
#: that gain error with margin; the resulting -0.54 dBFS shortfall is reported
#: per corner by analyze_fft.py so a reader can see it rather than having to
#: assume it.
#:
#: KEPT AT 0.94 UNDER DR-0014, which is now a conservative choice rather than a
#: necessary one -- if the gain term cancels as that record derives, the
#: backoff costs 0.54 dB of signal and buys headroom the block no longer needs.
#: Raising it is a change to what the deck MEASURES, so it belongs with #61's
#: re-run and its measured gain figure, not with this topology change: moving
#: both the circuit and the stimulus in one step would leave no way to attribute
#: a spectral difference to either.
FFT_AMP_FRAC = 0.94

#: How many of the FFT_N captured conversions get a per-conversion
#: worst-decision-error measurement. Eight, spread evenly across the sine, is
#: enough to catch a decision the dynamic input broke without adding 64 more
#: `meas` lines to every corner log.
FFT_DECERR_CONV = 8
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
    a("* ---- near-full-scale sine -----------------------------------------")
    a("* Amplitude is 0.94 x half full scale, i.e. -0.54 dBFS. The backoff")
    a("* was for a MEASURED reason, not out of habit: under the SUPERSEDED")
    a("* top-plate sampling phase sim/adc-inl-dnl/ found a converter-level")
    a("* gain error of ~3 % of full scale, dominated by top-plate parasitic")
    a("* loading of the array by the comparator input capacitance, and a")
    a("* rail-to-rail drive would therefore CLIP at both ends with the FFT")
    a("* reporting the clipping as distortion the block does not have.")
    a("* DR-0014 is expected to remove that term, which makes 0.94")
    a("* conservative rather than necessary; it is deliberately UNCHANGED")
    a("* here so that #61's re-run moves the circuit and not the stimulus.")
    a("* analyze_fft.py reports the resulting dBFS shortfall per corner, so a")
    a("* reader sees the backoff rather than assuming it.")
    a(
        f"vsein se_vinp 0 sin({{vcm}} {{vref/2*{FFT_AMP_FRAC}}}"
        f" {fft_input_hz():.6f}"
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
    # Worst per-decision error, sampled on FFT_DECERR_CONV conversions spread
    # evenly across the capture. It has to be measured PER CONVERSION, inside
    # that conversion's ten trial phases: a single MAX over the whole capture
    # instead picks up the conversion BOUNDARY, where the array releases to
    # V_cm and the ideal shadow steps to zero a numerical instant apart -- an
    # 889 LSB spike at exactly t = k*1 us that no comparator ever samples.
    # Record 20260801-134049-7d48a44 measured that and is superseded for it.
    decerr_keys: list[str] = []
    step = max(1, FFT_N // FFT_DECERR_CONV)
    for n in range(0, FFT_N, step):
        t0 = (FFT_WARMUP_CONV + n) * CONV_NS
        analyses.append(
            f"meas tran d{n:03d} MAX v(se_aerrh) FROM={t0 + 280:.1f}n"
            f" TO={t0 + 880:.1f}n"
        )
        measure[f"decerr_c{n:03d}_lsb"] = f"d{n:03d}"
        decerr_keys.append(f"decerr_c{n:03d}_lsb")
    measure["code_max"] = "cmax"
    measure["code_min"] = "cmin"
    analyses.append(
        f"meas tran vrefhi MAX v(vrefn) FROM={FFT_WARMUP_CONV * CONV_NS}n"
        f" TO={_fft_end_ns()}n"
    )
    analyses.append(
        f"meas tran vreflo MIN v(vrefn) FROM={FFT_WARMUP_CONV * CONV_NS}n"
        f" TO={_fft_end_ns()}n"
    )
    measure["vref_droop_mv"] = "(vrefhi-vreflo)*1e3"
    checks = {
        "code_max": {
            "min": 900.0,
            "max": 1023.5,
            "description": (
                "COVERAGE WITNESS, upper end: a near-full-scale sine must "
                "actually drive the converter near full scale. Without it an "
                "FFT taken over a stuck or heavily attenuated output would "
                "still produce a plausible-looking spectrum. The window allows "
                "for the 0.94 amplitude backoff and the gain error the "
                "SUPERSEDED top-plate sampling phase measured, together; it "
                "does NOT allow a clipped capture, which would pin at 1023.5. "
                "Under DR-0014 the gain term is expected to cancel, so the "
                "window's lower edge is now slack rather than tight -- #61 "
                "owns closing it against a measurement."
            ),
        },
        "code_min": {
            "min": -0.5,
            "max": 124.0,
            "description": "COVERAGE WITNESS, lower end, same window.",
        },
    }
    checks["vref_droop_mv"] = {
        "max": 50.0,
        "min_spread_pct_by_axis": {"process": 3.0},
        "description": (
            "Peak-to-peak movement of the V_REF node across the capture, "
            "through DR-0002's ratified >= 40 nF / <= 240 ohm envelope. Same "
            "measurement sim/adc-inl-dnl/ carries, and for the same reason: it "
            "is this deck's corner-sensitivity assertion. The charge the array "
            "demands per conversion is set by the MiM sections and the switch "
            "R_on, so a sabotaged corner sweep (sim/harness/README.md "
            "mechanism 3) collapses its process-axis spread."
        ),
    }
    for key in decerr_keys:
        # REPORTED, NOT BOUNDED, and the reason is a property of the deck, not
        # a convenience. `se_err` differences the HELD top plates against
        # `se_di`, which is built from the INSTANTANEOUS input. With a static
        # input (sim/adc-inl-dnl/) those are the same thing and the node is
        # exactly the input-referred decision error. With a 0.969 x Nyquist
        # sine they are not: the input keeps moving through the 600 ns trial
        # window, by up to 2*pi*484 kHz*600 ns*512 LSB ~ 930 LSB, and that
        # motion -- not any decision error -- is what dominates the measured
        # 165..810 LSB. Bounding it would be bounding the input's slew rate.
        # Making it meaningful needs a shadow sample-and-hold on the ideal
        # input path, i.e. a NETLIST change, which would break comparability
        # with the sibling records already taken from this generator; it is
        # left to the post-layout re-run (#17) that regenerates all three.
        checks[key] = {
            "description": (
                "Reported, not bounded. Worst |input-referred error| over the "
                "ten decisions of one conversion, measured inside that "
                "conversion's trial phases -- but for a NEAR-NYQUIST input it "
                "is dominated by the input's own motion through the trial "
                "window, because the ideal shadow path compares the held top "
                "plates against the instantaneous input. It is kept as a "
                "cross-corner consistency witness (the nine PVT points agree "
                "to ~1 %), not as a decision-error claim; the static "
                "decision-error claim is sim/adc-inl-dnl/'s decerr_t<k>_lsb, "
                "where the input IS static and the node means what it says."
            ),
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
                "WHAT THIS RECORD'S PASS/FAIL COVERS. The harness verdict here "
                "covers the CAPTURE's validity -- coverage witnesses that the "
                "sine actually drove the converter across its range without "
                "clipping, and the V_REF corner-sensitivity floor. It does NOT "
                "cover the ENOB and SFDR rows themselves: those are spectral "
                "quantities, not scalars an ngspice `meas` can produce, and "
                "they are computed from THIS RECORD's raw per-corner logs by "
                "sim/adc-enob-fft/testbench/analyze_fft.py and adjudicated in "
                "spec/testbench-suite-memo.md Sec 11. A reader must not read a "
                "PASS here as the ENOB row passing -- as of this record it "
                "does not (8.005 bits worst against a > 9.0 target, "
                "distortion-limited; see Sec 11.2 and issue #53).",
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
#: Conversions per input level: the first re-acquires, the rest are averaged.
#: Three rather than four -- the average over two full conversions is already
#: exact for a periodic waveform, and the fourth conversion cost 25 % of the
#: deck's runtime to average an identical period.
PWR_CONV_PER_LEVEL = 3
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
    a("*                               drivers -- FOUR legs per cell under")
    a("*                               DR-0014, so the V_in leg and its")
    a("*                               driver are measured here, not")
    a("*                               apportioned")
    a("*   vddt   sampling (#10)       DR-0014's top-plate V_cm switch and")
    a("*                               its driver. Before that record this")
    a("*                               rail supplied the dedicated top-plate")
    a("*                               sampling switch, so the block still")
    a("*                               means 'the switch that defines the")
    a("*                               sampling instant' -- but it is now a")
    a("*                               DRIVEN switch, so what used to be an")
    a("*                               analytic gate-drive term is measured")
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
    a("* DR-0014 CLOSES one previously-analytic term rather than adding one:")
    a("* the dedicated sampling switch it removes was driven by a rung-1")
    a("* ideal inverter (to preserve the NMOS/PMOS turn-off skew DR-0013's")
    a("* charge-split measurement was taken with), so its gate-drive power")
    a("* was carried analytically. The top-plate switch that replaces it has")
    a("* a real adc_drv on vddt, and the fourth bottom-plate leg has a real")
    a("* adc_drv on vddd, so both are measured here.")
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
        ("trk", "vddt", "vddm", "top-plate V_cm switch + driver (#10)"),
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
            "(comparator / CDAC four-leg switches + drivers / DR-0014 top-plate "
            "V_cm switch / V_REF / "
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
                "The dominant digital term -- driving the 72 T-gate legs of "
                "the array (four per cell under DR-0014, 18 cells) -- IS "
                "measured, on vddd, because those drivers are "
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
# top-plate parasitic loading: what is actually on the node, and how much of
# it moves with the residue (#53)
# ---------------------------------------------------------------------------

#: Quasi-static ramp used to extract C(V) at the top-plate node. The rate is
#: deliberately SUPPLY-INDEPENDENT (2.70 V in 900 ns = exactly 3.0 V/us) so
#: the same literal dV/dt converts a measured current to a capacitance at
#: every point of the supply axis -- manifest `params` are not visible inside
#: the harness's `.control` block, so a supply-scaled rate could not be
#: divided out in a `measure` expression.
CPAR_RAMP_LO_V = 0.15
CPAR_RAMP_HI_V = 2.85
CPAR_RAMP_NS = 900.0
CPAR_SLEW_V_PER_S = (CPAR_RAMP_HI_V - CPAR_RAMP_LO_V) / (CPAR_RAMP_NS * 1e-9)

#: Absolute top-plate voltages the capacitance is read at. 1.65 V is V_cm at
#: the nominal supply (the late-trial operating point); 0.30 / 2.70 V bracket
#: the excursion a freshly sampled full-scale input puts on the node -- under
#: DR-0011 by sampling onto it, and under DR-0014 by the inverted residue the
#: bottom plates drive onto it, which spans the same range.
CPAR_PROBES_V = (0.30, 0.90, 1.65, 2.40, 2.70)

#: The four branches: three loads measured alone, then all three on one node.
CPAR_BRANCHES = (
    ("cmp", "a", "comparator input (DR-0007 preamp pair gate, latch in reset)"),
    ("sw", "b", "the top-plate V_cm switch in HOLD (DR-0014's adc_tp_sw, open)"),
    ("arr", "c", "the CDAC array itself (DR-0011, bottom plates released to V_cm)"),
    ("tot", "d", "all three on one node -- the real top plate"),
)


def _cpar_tag(v: float) -> str:
    return "v" + f"{v:.2f}".replace(".", "p")


def _cpar_t_ns(v: float) -> float:
    frac = (v - CPAR_RAMP_LO_V) / (CPAR_RAMP_HI_V - CPAR_RAMP_LO_V)
    return frac * CPAR_RAMP_NS


def _cpar_array(inst: str, top: str) -> list[str]:
    """One `adc_cdac_side` with every bottom plate released to V_cm.

    DR-0014's fourth leg is present in the cell but held OFF (`cpoff`) and
    its `vin` port is parked on V_cm, so this branch measures exactly the
    same quantity it measured before that record -- the array alone, bottom
    plates on V_cm, which is the state a bit trial settles in.
    """
    ports = [top, "cpvcm", "cpvref", "cpvcm", "0", "vdd", "cpoff"]
    for _w in WEIGHTS:
        ports += ["cprel", "cpoff", "cpoff"]
    return sar._wrap(f"X{inst}", ports + ["adc_cdac_side"])


def cpar_netlist() -> str:
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_top_plate_cpar -- WHAT IS ON THE CDAC TOP PLATE, and how much of")
    a("* it moves with the residue (issue #53).")
    a("*")
    a("* GENERATED by design/adc-top/gen_adc_top.py -- do not edit.")
    a("*")
    a("* WHY THIS DECK EXISTS. sim/adc-inl-dnl/ measures a converter-level")
    a("* systematic gain error of 29.2-33.8 LSB (2.85-3.3 % of full scale)")
    a("* and an endpoint-corrected INL of up to -4.494 LSB against a < 1 LSB")
    a("* row. Both are ATTRIBUTED to top-plate parasitic loading: DR-0011")
    a("* samples on the top plate, so the sampled input is not attenuated")
    a("* while every DAC step is divided by C_arr/(C_arr + C_par). That")
    a("* attribution was an inference from one number -- the implied C_par")
    a("* backed out of the measured gain error -- and the whole of #53's")
    a("* decision rests on it. This deck measures the divider directly, and")
    a("* measures WHICH devices form it.")
    a("*")
    a("* METHOD. Quasi-static C(V) by ramped displacement current: each")
    a("* branch's node is driven by an ideal voltage ramp of exactly")
    a("* 3.0 V/us and the current the ramp source delivers is read at five")
    a("* absolute voltages, so C(V) = -i(v_ramp) / (dV/dt) with no")
    a("* differencing of two large levels (sim/harness/README.md's `meas`")
    a("* precision floor never enters: the measured quantity is a current of")
    a("* order 100 nA - 30 uA, not a microvolt displacement on a biased")
    a("* node). 3.0 V/us is four decades slower than the 31.25 ns settling")
    a("* window the divider actually acts in, so the extracted capacitance")
    a("* is the quasi-static one.")
    a("*")
    a("* FOUR BRANCHES, three loads alone and then all three together:")
    for name, _sfx, what in CPAR_BRANCHES:
        a(f"*   {name:<4} {what}")
    a("*")
    a("* The fourth branch is not redundant. c_cmp + c_sw + c_arr - c_tot is")
    a("* reported as `c_sum_err_pct` and bounded: it is the deck's own")
    a("* internal control, and it is what distinguishes 'these three loads")
    a("* add up to the top plate' from 'three plausible numbers'.")
    a("*")
    a("* WHAT IS DELIBERATELY NOT HERE. Routing and MiM top-plate parasitics")
    a("* are absent -- this is a schematic-level deck and there is no layout")
    a("* (#16/#17). Every number below is therefore a LOWER BOUND on the")
    a("* real C_par, and #17's extracted re-run can only move it up.")
    a("*")
    a("* LATCH STATE. The comparator strobe is held LOW, i.e. the latch is in")
    a("* reset/precharge and the preamp is tracking. That is the state the")
    a("* node is in while the DAC step settles, which is the state whose")
    a("* capacitance divides the step. The strobe-high transient is a")
    a("* different quantity and a different deck: sim/comparator-kickback/.")
    a("*")
    a("* WHICH TOPOLOGY THIS DECK MODELS: DR-0014, AS OF #61.")
    a("* Branch b used to be the DEDICATED top-plate sampling switch, whose")
    a("* two DR-0013 dummy devices sat permanently across this node and")
    a("* contributed 66 % of the measured C_par. DR-0014 removes that switch")
    a("* from the converter entirely -- the input reaches the array through")
    a("* the nine fourth-leg cell T-gates per side -- and puts a per-side")
    a("* top-plate V_cm switch (adc_tp_sw, plain T-gate, deliberately NOT")
    a("* dummy-compensated) on this node instead. Branch b is therefore that")
    a("* switch, in hold, i.e. open, which is the state the node is in while")
    a("* a bit trial settles.")
    a("*")
    a("* The record this one supersedes measured the SUPERSEDED load set and")
    a("* is retained, unedited, as the measured evidence DR-0014's Context")
    a("* rests on -- `sim/` is append-only. The two are directly comparable:")
    a("* same method, same probe voltages, same corner grid, one branch")
    a("* changed. What changed in the CONVERTER, and what this deck cannot")
    a("* show on its own, is that the divider it measures no longer divides")
    a("* the DAC step against an undivided sampled input -- both are now over")
    a("* the same C_arr + C_par. That claim is sim/adc-inl-dnl/'s gain_err_lsb")
    a("* to settle, not this deck's; what this deck settles is how much")
    a("* C_par is left once DR-0013's dummies are gone.")
    a("* ==================================================================")
    a("")
    a(".param vcm={vdd_val/2}")
    a(".param ib=10u")
    a("")
    a("vsup vdd 0 dc {vdd_val}")
    a("* Static control levels. `cpclkl` also serves as the comparator strobe")
    a("* (latch held in reset) and as the top-plate V_cm switch's active-high")
    a("* control (switch held OFF -- hold, which is when the array converts).")
    a("vcpclkl cpclkl 0 dc 0")
    a("vcpclkh cpclkh 0 dc {vdd_val}")
    a("vcpvcm  cpvcm  0 dc {vcm}")
    a("vcpvref cpvref 0 dc {vdd_val}")
    a("* Array control, active-high into each cell's local driver: every")
    a("* weight RELEASED to V_cm, none engaged to V_REF or GND. That is the")
    a("* bottom-plate state during a bit trial's settling window.")
    a("vcprel cprel 0 dc {vdd_val}")
    a("vcpoff cpoff 0 dc 0")
    a("")
    ramp = (
        f"pwl(0 {CPAR_RAMP_LO_V} {CPAR_RAMP_NS:.0f}n {CPAR_RAMP_HI_V})"
    )
    a("* ---- branch a: the comparator's own input ---------------------------")
    a(f"vra cpa 0 {ramp}")
    a("vcpan cpan 0 dc {vcm}")
    a("iba vdd cpaib dc {ib}")
    a("Xcmpa cpa cpan cpclkl cpaib cpadout cpadoutb vdd 0 comparator")
    a("")
    a("* ---- branch b: the top-plate V_cm switch, in hold -------------------")
    a("* DR-0014's adc_tp_sw, open -- the state the node is in for every bit")
    a("* trial. What is left on the node is one T-gate's off-state junction")
    a("* and overlap capacitance at the CDAC bottom-plate geometry, plus its")
    a("* local driver's output. Under the superseded topology this branch")
    a("* held the dedicated sampling switch, whose two DR-0013 dummy devices")
    a("* were ON in hold with source and drain both tied to the top plate --")
    a("* two MOS capacitors permanently across the sampling node, and 66 % of")
    a("* the C_par the record this one supersedes measured. Removing them is")
    a("* a consequence of DR-0014, not an independent choice: the switch they")
    a("* compensated no longer exists.")
    a(f"vrb cpb 0 {ramp}")
    a("Xswb cpb vcpbcm cpclkl vdd 0 adc_tp_sw")
    a("vcpbcm vcpbcm 0 dc {vcm}")
    a("")
    a("* ---- branch c: the array alone --------------------------------------")
    a(f"vrc cpc 0 {ramp}")
    L += _cpar_array("arrc", "cpc")
    a("")
    a("* ---- branch d: the real top plate -- all three at once --------------")
    a(f"vrd cpd 0 {ramp}")
    a("vcpdn cpdn 0 dc {vcm}")
    a("ibd vdd cpdib dc {ib}")
    a("Xcmpd cpd cpdn cpclkl cpdib cpddout cpddoutb vdd 0 comparator")
    a("Xswd cpd vcpdcm cpclkl vdd 0 adc_tp_sw")
    a("vcpdcm vcpdcm 0 dc {vcm}")
    L += _cpar_array("arrd", "cpd")
    a("")
    a("* The SR latch's hold state is metastable at DC; steer both instances")
    a("* to a definite state so the operating point is unique, exactly as")
    a("* sim/comparator-kickback/ does and for the same reason.")
    a(".nodeset v(cpadout)=0 v(cpadoutb)={vdd_val}")
    a(".nodeset v(cpddout)=0 v(cpddoutb)={vdd_val}")
    return "\n".join(L) + "\n"


def cpar_manifest() -> dict:
    analyses = [f"tran 1n {CPAR_RAMP_NS:.0f}n 0 1n"]
    measure: dict[str, str] = {}
    checks: dict[str, dict] = {}
    slew = f"{CPAR_SLEW_V_PER_S:.6e}"
    for v in CPAR_PROBES_V:
        t = _cpar_t_ns(v)
        for name, sfx, _what in CPAR_BRANCHES:
            analyses.append(
                f"meas tran i{sfx}_{_cpar_tag(v)} FIND i(vr{sfx}) AT={t:.3f}n"
            )
            measure[f"c_{name}_{_cpar_tag(v)}_ff"] = (
                f"(0-i{sfx}_{_cpar_tag(v)})/{slew}*1e15"
            )
        # the divider the converter actually sees, at this top-plate voltage
        measure[f"cpar_{_cpar_tag(v)}_ff"] = (
            f"(0-(id_{_cpar_tag(v)}-ic_{_cpar_tag(v)}))/{slew}*1e15"
        )
        measure[f"gain_err_{_cpar_tag(v)}_pct"] = (
            f"100*(1-ic_{_cpar_tag(v)}/id_{_cpar_tag(v)})"
        )

    mid = CPAR_PROBES_V[len(CPAR_PROBES_V) // 2]
    measure["c_sum_err_pct"] = (
        f"100*((ia_{_cpar_tag(mid)}+ib_{_cpar_tag(mid)}+ic_{_cpar_tag(mid)})"
        f"/id_{_cpar_tag(mid)}-1)"
    )

    def _fold(fn: str, terms: list[str]) -> str:
        expr = terms[0]
        for t in terms[1:]:
            expr = f"{fn}({expr},{t})"
        return expr

    # The RANGE over the whole probed excursion, not the endpoint-to-endpoint
    # difference: C_par is peaked near mid-rail (the preamp pair's input
    # capacitance is largest at balance, i.e. at the small-residue late
    # trials), so a lo-minus-hi "swing" reads a fraction of the real
    # variation and would understate the linearity term this deck exists to
    # quantify.
    g = [f"(1-ic_{_cpar_tag(v)}/id_{_cpar_tag(v)})" for v in CPAR_PROBES_V]
    measure["gain_err_range_pct"] = f"100*({_fold('max', g)}-{_fold('min', g)})"
    p = [f"(0-(id_{_cpar_tag(v)}-ic_{_cpar_tag(v)}))" for v in CPAR_PROBES_V]
    measure["cpar_range_ff"] = (
        f"({_fold('max', p)}-{_fold('min', p)})/{slew}*1e15"
    )

    checks[f"c_arr_{_cpar_tag(mid)}_ff"] = {
        "min": 7000.0,
        "max": 11000.0,
        "min_spread_pct_by_axis": {"process": 1.0},
        "description": (
            "The array itself, at V_cm, with every bottom plate released to "
            "V_cm -- i.e. the C_arr the ratified Input-structure row "
            "publishes as 8.827 pF per side (512 x C_u, "
            "spec/cdac-sizing-memo.md Sec 4). The window is deliberately "
            "wide: this is a characterization record and the number under "
            "test is the DIVIDER, not the array. The process-axis floor is "
            "the corner-sensitivity control -- the `cdac` corner set skews "
            "the MiM family by ~10 %, so a run that silently pinned every "
            "model section to typical (sim/harness/README.md mechanism 3) "
            "collapses this spread and fails here."
        ),
    }
    checks["c_sum_err_pct"] = {
        "min": -3.0,
        "max": 3.0,
        "description": (
            "THE DECK'S INTERNAL CONTROL. The three loads measured "
            "separately must add up to the fourth branch, where all three "
            "sit on one node. Three plausible capacitances that do not sum "
            "to the measured total would mean the decomposition -- which is "
            "the whole point of this deck -- is wrong, however reasonable "
            "each individual number looked."
        ),
    }
    checks[f"gain_err_{_cpar_tag(mid)}_pct"] = {
        "min": 0.0,
        "max": 10.0,
        "description": (
            "1 - C_arr/(C_arr + C_par) at V_cm, in percent of full scale: "
            "the fraction of a DAC step that top-plate parasitic loading "
            "swallows. UNDER DR-0011 THIS WAS A GAIN ERROR AND UNDER DR-0014 "
            "IT IS NOT, and that difference is the whole point of the record "
            "this one supersedes: with the sample taken on the bottom plates, "
            "the same factor multiplies the sampled input and the DAC step "
            "alike and cancels from the comparator's decision. It is still "
            "measured, and still bounded loosely, because it is the divider "
            "the second-order terms (C_par MISMATCH between the two sides, "
            "sim/dr0014-sampling/) act on. Whether it still appears in the "
            "converter's gain is sim/adc-inl-dnl/'s gain_err_lsb to answer, "
            "not this deck's."
        ),
    }
    return {
        "name": "top-plate-cpar",
        "description": (
            "What loads the CDAC top plate under DR-0014 bottom-plate "
            "sampling, decomposed into the comparator input, the top-plate "
            "V_cm switch in hold and the array itself, and the resulting "
            "C_arr/(C_arr+C_par) divider vs top-plate voltage, over the "
            "capacitor-corner PVT grid (#53, re-taken by #61). The record "
            "this supersedes measured the same decomposition for the "
            "SUPERSEDED DR-0011 load set, whose second branch was the "
            "dedicated sampling switch and its two DR-0013 dummy devices."
        ),
        "claim": (
            "None -- characterization. No ratified row in "
            "README.md#target-specification covers top-plate parasitic "
            "loading; that gap is the subject of #53 and of "
            "spec/decision-records/DR-0014-bottom-plate-sampling.md, and the "
            "superseded record is the measured evidence that decision's "
            "Context rests on. This record re-takes the same decomposition on "
            "the topology the decision produced: what C_par is once DR-0013's "
            "dummies are gone, and therefore what the side-to-side C_par "
            "mismatch measured by sim/dr0014-sampling/ is a mismatch OF."
        ),
        "netlist": "tb_top_plate_cpar.spice",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["cdac"],
        "analyses": analyses,
        "measure": measure,
        "checks": checks,
        "evidence": {
            "record_kind": "characterization",
            "data_provenance": (
                "simulated -- quasi-static C(V) by ramped displacement "
                "current on the gf180mcu device models, schematic level. "
                "No foundry parasitic data and no layout extraction is in "
                "it, so every capacitance here is a LOWER bound on the "
                "post-layout node (#17)."
            ),
            "notes": [
                "SCHEMATIC ONLY, AND THAT MATTERS IN ONE DIRECTION. Routing "
                "capacitance and the MiM stack's own top-plate parasitic are "
                "not modelled, so the measured C_par is a floor and the "
                "measured divider error is a floor with it. #17's extracted "
                "re-run can only make both worse.",
                "THE RAMP RATE IS SUPPLY-INDEPENDENT BY CONSTRUCTION "
                "(0.15 V -> 2.85 V in 900 ns = 3.0 V/us at every point of "
                "the supply axis), because the harness does not expose "
                "netlist params to the measure expressions. One consequence "
                "is stated rather than hidden: the probe voltages are "
                "ABSOLUTE, so 1.65 V is V_cm only at the nominal supply, and "
                "at 2.97 / 3.63 V it is V_cm -/+ 165 mV. The C(V) curve is "
                "reported at five points precisely so a reader can "
                "interpolate rather than take one number on trust.",
                "THE LATCH IS HELD IN RESET. The capacitance that divides a "
                "DAC step is the one present while the step settles, which "
                "is the strobe-low half of the bit cycle. Kickback during "
                "the strobe-high half is a different quantity, already "
                "measured by sim/comparator-kickback/.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# deck 5: the four terms DR-0014's derivation assumes away (#61)
# ---------------------------------------------------------------------------
#
# DR-0014's Consequences name four quantities its charge-balance derivation
# treats as negligible without measuring them. #61 requires a NUMBER for each,
# not an argument. This deck produces all four from one transient, plus the
# two measurements DR-0014 invalidates the prior evidence for (the sampling
# path's own gain error and linearity, and the series R_on of the new input
# path). Everything here is at the same schematic fidelity as the adc-* decks
# and uses the same library subckts.

#: DR-0014's two-phase sample, on DR-0003's 62.5 ns clock. The top-plate
#: switch opens on the edge into ph3; the bottom plates leave V_in one whole
#: bit cycle later. These are the design's own numbers, not this deck's.
DR14_TP_FALL_NS = 3 * CLK_PERIOD_NS  # 187.5 -- THE SAMPLING INSTANT
DR14_BP_FALL_NS = 4 * CLK_PERIOD_NS  # 250.0
#: One bit trial, started two clocks after the sample so the held value is
#: quiet first. Weight 256 -- the largest step this array makes, i.e. the
#: worst case for the settling term.
DR14_TRIAL_NS = 6 * CLK_PERIOD_NS  # 375.0
#: The settling half of a bit cycle at the ratified 1 MS/s rate: the CDAC has
#: this long before the comparator strobe (spec/prior-art-survey.md Sec 1.4).
DR14_SETTLE_HALF_NS = CMP_STROBE_NS  # 31.25
DR14_END_NS = 600.0

#: Probe instants. `pre` is inside the acquisition, with the top-plate switch
#: still closed; `tp` is after that switch has opened and its injection has
#: settled but BEFORE the bottom plates move; `hold` is the sampled value;
#: `set` is the comparator strobe of the bit trial; `res` is the same trial
#: fully settled, three settling-halves later.
DR14_T_PRE_NS = DR14_TP_FALL_NS - 0.5
DR14_T_TP_NS = DR14_BP_FALL_NS - 5.0
DR14_T_HOLD_NS = DR14_BP_FALL_NS + 60.0
DR14_T_SET_NS = DR14_TRIAL_NS + DR14_SETTLE_HALF_NS
DR14_T_RES_NS = DR14_TRIAL_NS + 3 * CLK_PERIOD_NS

#: Differential input levels, as a fraction f of V_cm: V_inp = V_cm(1+f),
#: V_inn = V_cm(1-f), so the differential input is f * V_REF and the level is
#: ratiometric at every point of the supply axis. f = 0 is the one that makes
#: the bottom-plate injection directly readable: the ideal sampled step is
#: then exactly zero, so whatever the top plate does at that edge IS the
#: injection. +/-0.9 are the endpoints the gain fit anchors on (0.95 / 0.05 of
#: V_REF single-ended, i.e. inside the rails without clipping).
DR14_LEVELS = (-0.9, -0.45, 0.0, 0.45, 0.9)
#: Index of the level the C_par-mismatch branches reuse as their matched
#: reference: a non-zero, non-endpoint input, so both the sampled charge and
#: the DAC step are non-zero when the mismatch acts on them.
DR14_MIS_LEVEL = 3

#: Deliberate top-plate capacitance imbalance, in fF on the p side only.
#: sim/top-plate-cpar/ measures C_par at 216-266 fF under the SUPERSEDED load
#: set and this record re-measures it for DR-0014's; 10 / 30 / 100 fF
#: therefore span roughly 5 % to 100 % of it. They are exaggerated on
#: purpose: the second-order residue at a realistic centroid-matched
#: mismatch is below the harness's ~1 uV `meas` precision floor, so the deck
#: measures a SLOPE over mismatches large enough to be real numbers instead
#: of reporting a floor as a result.
DR14_DCPAR_FF = (10.0, 30.0, 100.0)

#: Ratiometric input levels the new input path's R_on is measured at.
DR14_RON_FRACS = (0.05, 0.275, 0.5, 0.725, 0.95)
#: Volts forced across the closed path for the R_on measurement. Small enough
#: that the T-gate stays in its linear region, large enough that the current
#: (~10 uA) is four decades above the harness's measurement floor.
DR14_RON_DV = 0.001


def _dr14_side(inst, top, vin, sel_in, rel_hi_lo, rel_other) -> list[str]:
    """One `adc_cdac_side` wired for this deck's control nets."""
    rel256, hi256, lo256 = rel_hi_lo
    ports = [top, vin, "vrefn", "vcmn", "0", "vddd", sel_in, rel256, hi256, lo256]
    for _w in WEIGHTS[1:]:
        ports += [rel_other, "onl", "onl"]
    return sar._wrap(f"X{inst}", ports + ["adc_cdac_side"])


def _dr14_side3(inst, top, rel_hi_lo, rel_other) -> list[str]:
    """The DR-0011 three-leg reference side (deck-local, see `tb3_cdac_side`)."""
    rel256, hi256, lo256 = rel_hi_lo
    ports = [top, "vrefn", "vcmn", "0", "vddd", rel256, hi256, lo256]
    for _w in WEIGHTS[1:]:
        ports += [rel_other, "onl", "onl"]
    return sar._wrap(f"X{inst}", ports + ["tb3_cdac_side"])


def _dr14_pair(tag: str, f: float, dcpar_ff: float = 0.0) -> list[str]:
    """A differential sampling pair at input fraction `f`, +dC_par on p."""
    L: list[str] = []
    a = L.append
    a(f"* ---- pair {tag}: differential input f = {f:+.3f} x V_cm"
      + (f", +{dcpar_ff:g} fF on the p top plate" if dcpar_ff else ""))
    for s, scale in (("p", 1.0 + f), ("n", 1.0 - f)):
        a(f"v{tag}src{s} {tag}_src{s} 0 dc {{vcm*{scale!r}}}")
        a(f"R{tag}s{s} {tag}_src{s} {tag}_pin{s} {TRACK_RS_OHM}")
        a(f"C{tag}x{s} {tag}_pin{s} 0 {TRACK_CPIN}")
        a(f"X{tag}tsw{s} {tag}_top{s} vcmn smptp vddt 0 adc_tp_sw")
        L += _dr14_side(
            f"{tag}arr{s}",
            f"{tag}_top{s}",
            f"{tag}_pin{s}",
            "smpbp",
            ("nrel256", "hi256" if s == "p" else "onl", "onl" if s == "p" else "lo256"),
            "nrel",
        )
    if dcpar_ff:
        a(f"C{tag}dcpar {tag}_topp 0 {dcpar_ff:g}f")
    a(f"i{tag}b vddc {tag}_ib dc {{ibias}}")
    a(
        f"X{tag}cmp {tag}_topp {tag}_topn cmpstrobe {tag}_ib {tag}_do"
        f" {tag}_dob vddc 0 comparator"
    )
    a(f".nodeset v({tag}_do)=0 v({tag}_dob)={{vdd_val}}")
    a(f"b{tag}dp {tag}_dp 0 V = (v({tag}_topp)-vcm)/lsb")
    a(f"b{tag}dn {tag}_dn 0 V = (v({tag}_topn)-vcm)/lsb")
    a(f"b{tag}dd {tag}_dd 0 V = (v({tag}_topp)-v({tag}_topn))/lsb")
    a("")
    return L


def _dr14_ref_side3() -> list[str]:
    """The DR-0011 three-leg CDAC side, kept LOCAL to this testbench.

    It is the A/B partner for the fourth leg's settling cost and nothing
    else, so it does not belong in `design/adc-top/adc_top.spice`: that
    library describes the converter as built, and the converter no longer has
    a three-leg cell. Device text below is `adc_cdac_cell` with the `in` leg
    and its driver deleted and nothing else changed, which is exactly what
    makes the A/B attributable to that leg.
    """
    L: list[str] = []
    a = L.append
    a("* ---- DR-0011 three-leg reference cell (deck-local A/B partner) ------")
    a(".subckt tb3_cdac_cell top vref vcm vss vdd gn_rel gn_hi gn_lo")
    a("+ cw=10u cl=10u")
    a("Xc  top bp mim_cap_2f0 c_width='cw' c_length='cl'")
    a("Xdr gn_rel gp_rel vdd vss adc_drv")
    a("Xdh gn_hi  gp_hi  vdd vss adc_drv")
    a("Xdl gn_lo  gp_lo  vdd vss adc_drv")
    a(f"Xsr vcm  bp gn_rel gp_rel vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(f"Xsh vref bp gn_hi  gp_hi  vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(f"Xsl vss  bp gn_lo  gp_lo  vdd adc_tgate wn={CDAC_SW_WN} wp={CDAC_SW_WP}")
    a(".ends tb3_cdac_cell")
    a("")
    ports = ["top", "vref", "vcm", "vss", "vdd"]
    for w in WEIGHTS:
        ports += [f"rel_{w}", f"hi_{w}", f"lo_{w}"]
    L += sar._wrap(".subckt tb3_cdac_side", ports)
    for w in WEIGHTS:
        s = mim_side_um(w * C_UNIT_FF)
        a(
            f"X{w} top vref vcm vss vdd rel_{w} hi_{w} lo_{w}"
            f" tb3_cdac_cell cw={_fmt(s)}u cl={_fmt(s)}u"
        )
    s1 = mim_side_um(C_UNIT_FF)
    a(f"Xterm top vcm mim_cap_2f0 c_width={_fmt(s1)}u c_length={_fmt(s1)}u")
    a(".ends tb3_cdac_side")
    a("")
    return L


def dr14_netlist() -> str:
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_dr0014_sampling -- THE FOUR TERMS DR-0014'S DERIVATION ASSUMES")
    a("* AWAY, each as a measured number (issue #61).")
    a("*")
    a("* GENERATED by design/adc-top/gen_adc_top.py -- do not edit.")
    a("*")
    a("* DR-0014 moves the sampling phase from the CDAC top plate to the")
    a("* bottom plates. Its charge-balance derivation shows that")
    a("* k = C_arr/(C_arr + C_par) then multiplies the sampled input and")
    a("* every DAC step alike, so it cancels from the comparator's decision")
    a("* instead of dividing the DAC step alone. That derivation is exact")
    a("* only if four things are negligible, and the record itself says so:")
    a("*")
    a("*   1. the top-plate V_cm switch's own charge injection, and its")
    a("*      side-to-side MISMATCH (the injection is claimed to be")
    a("*      signal-independent -- an offset -- which is the classic reason")
    a("*      to sample on the bottom plate, and is SHOWN here, not assumed);")
    a("*   2. the bottom-plate input switches' injection, which happens one")
    a("*      whole bit cycle AFTER the top-plate switch has opened, i.e.")
    a("*      onto a node that is already isolated;")
    a("*   3. the fourth leg's cost in bit-trial settling -- one more T-gate's")
    a("*      junction and overlap load on every bottom plate, against the")
    a(f"*      {DR14_SETTLE_HALF_NS:g} ns settling half of the bit cycle;")
    a("*   4. the second-order residue left by C_par MISMATCH between the two")
    a("*      sides, i.e. what survives the first-order cancellation.")
    a("*")
    a("* It also re-takes the two measurements DR-0014 invalidated the prior")
    a("* evidence for: the sampling path's own gain error and linearity")
    a("* (DR-0012/DR-0013's 0.421 LSB was measured on a dedicated top-plate")
    a("* switch that no longer exists), and the series R_on of the new input")
    a("* path -- nine parallel cell T-gates per side, not one 40u/80u switch.")
    a("*")
    a("* METHOD. One transient carries DR-0014's real two-phase schedule on")
    a("* DR-0003's 62.5 ns clock:")
    a(f"*   0 .. {DR14_TP_FALL_NS:g} ns      acquire: top plate held at V_cm by its own")
    a("*                     switch, every bottom plate on V_in")
    a(f"*   {DR14_TP_FALL_NS:g} ns          THE SAMPLING INSTANT -- the top-plate switch")
    a("*                     opens and the top node floats")
    a(f"*   {DR14_BP_FALL_NS:g} ns          the bottom plates leave V_in for V_cm, one")
    a("*                     whole bit cycle later")
    a(f"*   {DR14_TRIAL_NS:g} ns          one bit trial: weight 256 engaged, p side to")
    a("*                     V_REF and n side to GND (MCS, DR-0011)")
    a("*")
    a("* Nothing else moves at the sampling instant, which is what makes")
    a("* term 1 DIRECTLY measurable: the top plate sits at V_cm before that")
    a("* edge by construction, so its displacement after it IS the switch's")
    a("* injection, with no reference simulation and no subtraction of two")
    a("* large numbers. Term 2 is read the same way at the f = 0 level, where")
    a("* both sides sit at V_cm and the ideal sampled step is exactly zero.")
    a("*")
    a("* V_REF AND V_cm ARE IDEAL SOURCES HERE, deliberately, and this is the")
    a("* one place this deck differs from sim/adc-inl-dnl/. DR-0002's")
    a("* reference network is a shared node; with 18 array sides on one deck")
    a("* it would couple every branch to every other and the A/B comparisons")
    a("* below -- which are differences of two branches -- would report that")
    a("* coupling as the effect under test. Reference droop is a real term")
    a("* and it is measured, with the real network, by sim/adc-inl-dnl/ and")
    a("* sim/adc-power/; it is not double-counted here.")
    a("*")
    a("* EVERY QUANTITY IS PUBLISHED IN LSB, computed by a B-source inside")
    a("* the netlist rather than by the measure expression, because the")
    a("* harness does not expose `.param lsb` to the `.control` block and LSB")
    a("* is supply-dependent (ratiometric spec, README.md note [c]).")
    a("* ==================================================================")
    a("")
    a(".param vref={vdd_val}")
    a(".param vcm={vdd_val/2}")
    a(".param lsb={vdd_val/1024}")
    a(".param ibias=10u")
    a("")
    a("* ---- rails -------------------------------------------------------")
    a("vddd vddd 0 dc {vdd_val}")
    a("vddt vddt 0 dc {vdd_val}")
    a("vddc vddc 0 dc {vdd_val}")
    a("vrefs vrefn 0 dc {vref}")
    a("vcms vcmn 0 dc {vcm}")
    a("vonh onh 0 dc {vdd_val}")
    a("vonl onl 0 dc 0")
    a("* The comparator strobe is held LOW: the latch is in reset and the")
    a("* preamp is tracking, which is the state the top plate is in while a")
    a("* DAC step settles. Kickback on the strobe edge is a different")
    a("* quantity and a different deck (sim/comparator-kickback/).")
    a("vcmpstrobe cmpstrobe 0 dc 0")
    a("")
    a("* ---- DR-0014's two-phase sample, as pure edges --------------------")
    a("* Each control is one clean edge from an ideal source. The controller")
    a("* that generates them from the phase ring is verified separately and")
    a("* exhaustively by sim/sar-logic-functional/ (the four-leg one-hot")
    a("* invariant and the measured samp_tp -> samp_bp lead); re-deriving")
    a("* them here would make this deck's numbers depend on that logic's")
    a("* delays instead of on the analog terms it exists to measure.")
    a("* `nrel` rises exactly as `smpbp` falls, with matched 100 ps edges --")
    a("* the delay balance design/sar-logic/ builds smpb and engnb to hold.")
    a(f"vsmptp smptp 0 pulse({{vdd_val}} 0 {DR14_TP_FALL_NS:g}n 100p 100p 10u 20u)")
    a(f"vsmpbp smpbp 0 pulse({{vdd_val}} 0 {DR14_BP_FALL_NS:g}n 100p 100p 10u 20u)")
    a(f"vnrel  nrel  0 pulse(0 {{vdd_val}} {DR14_BP_FALL_NS:g}n 100p 100p 10u 20u)")
    a("* weight 256's release leg: engaged at the trial, so it is high only")
    a("* between the end of the sample and the trial edge.")
    a(
        f"vnrel256 nrel256 0 pwl(0 0 {DR14_BP_FALL_NS:g}n 0"
        f" {DR14_BP_FALL_NS + 0.1:g}n {{vdd_val}} {DR14_TRIAL_NS:g}n {{vdd_val}}"
        f" {DR14_TRIAL_NS + 0.1:g}n 0)"
    )
    a(f"vhi256 hi256 0 pulse(0 {{vdd_val}} {DR14_TRIAL_NS:g}n 100p 100p 10u 20u)")
    a(f"vlo256 lo256 0 pulse(0 {{vdd_val}} {DR14_TRIAL_NS:g}n 100p 100p 10u 20u)")
    a("* the settling branches never sample, so their weight-256 release leg")
    a("* is high from t = 0 until the trial edge.")
    a(
        f"vbrel brel 0 pwl(0 {{vdd_val}} {DR14_TRIAL_NS:g}n {{vdd_val}}"
        f" {DR14_TRIAL_NS + 0.1:g}n 0)"
    )
    a("")
    a("* ==================================================================")
    a("* GROUP A -- terms 1 and 2, plus the sampling path's gain and")
    a("* linearity. Five differential pairs, identical except for the input.")
    a("* ==================================================================")
    for i, f in enumerate(DR14_LEVELS):
        L += _dr14_pair(f"a{i}", f)
    a("* ==================================================================")
    a("* GROUP B -- term 3. Two single sides, engaged into the same weight-")
    a("* 256 trial from the same released state, differing ONLY in whether")
    a("* the cell carries DR-0014's fourth leg. Neither samples: `smpbp` is")
    a("* not routed to them and their inputs sit at V_cm, so what is")
    a("* compared is the bit trial alone.")
    a("* ==================================================================")
    a("* b4: the DR-0014 four-leg cell, fourth leg present but off")
    a("Xb4tsw b4_top vcmn smptp vddt 0 adc_tp_sw")
    L += _dr14_side("b4arr", "b4_top", "vcmn", "onl", ("brel", "hi256", "onl"), "onh")
    a("ib4b vddc b4_ib dc {ibias}")
    a("Xb4cmp b4_top vcmn cmpstrobe b4_ib b4_do b4_dob vddc 0 comparator")
    a(".nodeset v(b4_do)=0 v(b4_dob)={vdd_val}")
    a("bb4d b4_d 0 V = (v(b4_top)-vcm)/lsb")
    a("")
    a("* b3: the DR-0011 three-leg cell, everything else identical")
    a("Xb3tsw b3_top vcmn smptp vddt 0 adc_tp_sw")
    L += _dr14_side3("b3arr", "b3_top", ("brel", "hi256", "onl"), "onh")
    a("ib3b vddc b3_ib dc {ibias}")
    a("Xb3cmp b3_top vcmn cmpstrobe b3_ib b3_do b3_dob vddc 0 comparator")
    a(".nodeset v(b3_do)=0 v(b3_dob)={vdd_val}")
    a("bb3d b3_d 0 V = (v(b3_top)-vcm)/lsb")
    a("")
    a("* ==================================================================")
    a("* GROUP C -- term 4. The same pair as group A's level "
      f"{DR14_MIS_LEVEL} (f = {DR14_LEVELS[DR14_MIS_LEVEL]:+.3f}),")
    a("* with a deliberate capacitance imbalance on the p top plate. Group")
    a(f"* A's a{DR14_MIS_LEVEL} IS the matched reference -- same input, same controls, same")
    a("* deck -- so the difference is attributable to the imbalance alone.")
    a("* ==================================================================")
    for j, dc in enumerate(DR14_DCPAR_FF):
        L += _dr14_pair(f"c{j}", DR14_LEVELS[DR14_MIS_LEVEL], dcpar_ff=dc)
    a("* ==================================================================")
    a("* GROUP D -- the ratified Input-structure row's series R_on, re-taken")
    a("* for the path DR-0014 actually built. The input no longer reaches")
    a("* the array through one dedicated 40u/80u dummy-compensated T-gate")
    a("* (156-570 ohm, sim/device-switch-ron/ + sim/track-switch-sampling/):")
    a(f"* it reaches it through NINE {CDAC_SW_WN}/{CDAC_SW_WP} cell T-gates per side, one per")
    a("* weight, in parallel. Forced-voltage / measured-current, the same")
    a("* method sim/device-switch-ron/ uses, at five ratiometric levels.")
    a("* ==================================================================")
    for j, frac in enumerate(DR14_RON_FRACS):
        a(f"* r{j}: nine parallel legs at V_in = {frac:g} x V_DD")
        a(f"vr{j}s r{j}_s 0 dc {{{frac!r}*vdd_val}}")
        a(f"vr{j}d r{j}_d 0 dc {{{frac!r}*vdd_val-{DR14_RON_DV!r}}}")
        for k in range(len(WEIGHTS)):
            a(
                f"Xr{j}g{k} r{j}_s r{j}_d onh onl vddd adc_tgate"
                f" wn={CDAC_SW_WN} wp={CDAC_SW_WP}"
            )
        a("")
    L += _dr14_ref_side3()
    return "\n".join(L) + "\n"


def _dr14_ideal_lsb(f: float) -> float:
    """Ideal held differential top plate, in LSB, at input fraction `f`.

    DR-0014 inverts the residue: a top node released at V_cm holds
    ``V_cm + k[(V_cm - V_in) + dac]``, so the ideal (k = 1) differential
    sampled value is ``V_inn - V_inp = -f * V_REF`` -- i.e. ``-f * 1024`` LSB.
    """
    return -f * 1024.0


def dr14_manifest() -> dict:
    analyses = [f"tran 20p {DR14_END_NS:g}n 0 100p"]
    measure: dict[str, str] = {}
    checks: dict[str, dict] = {}

    pair_tags = [f"a{i}" for i in range(len(DR14_LEVELS))]
    pair_tags += [f"c{j}" for j in range(len(DR14_DCPAR_FF))]
    for tag in pair_tags:
        for s in ("p", "n"):
            analyses.append(
                f"meas tran {tag}pre{s} FIND v({tag}_d{s}) AT={DR14_T_PRE_NS:.3f}n"
            )
            analyses.append(
                f"meas tran {tag}tp{s} FIND v({tag}_d{s}) AT={DR14_T_TP_NS:.3f}n"
            )
            analyses.append(
                f"meas tran {tag}bp{s} FIND v({tag}_d{s}) AT={DR14_T_HOLD_NS:.3f}n"
            )
        analyses.append(
            f"meas tran {tag}hld FIND v({tag}_dd) AT={DR14_T_HOLD_NS:.3f}n"
        )
        analyses.append(
            f"meas tran {tag}res FIND v({tag}_dd) AT={DR14_T_RES_NS:.3f}n"
        )

    # --- term 1: the top-plate switch's injection ---------------------------
    for i, f in enumerate(DR14_LEVELS):
        tag = f"a{i}"
        for s in ("p", "n"):
            measure[f"tp_inj_{s}_l{i}_lsb"] = f"{tag}tp{s}-{tag}pre{s}"
        measure[f"tp_inj_mis_l{i}_lsb"] = (
            f"({tag}tpp-{tag}prep)-({tag}tpn-{tag}pren)"
        )
    inj = [f"(a{i}tpp-a{i}prep)" for i in range(len(DR14_LEVELS))]

    def _fold(fn: str, terms: list[str]) -> str:
        expr = terms[0]
        for t in terms[1:]:
            expr = f"{fn}({expr},{t})"
        return expr

    measure["tp_inj_signal_dep_lsb"] = f"{_fold('max', inj)}-{_fold('min', inj)}"

    # --- term 2: the bottom-plate switches' injection ------------------------
    zero = DR14_LEVELS.index(0.0)
    for s in ("p", "n"):
        measure[f"bp_inj_{s}_lsb"] = f"a{zero}bp{s}-a{zero}tp{s}"
    measure["bp_inj_mis_lsb"] = (
        f"(a{zero}bpp-a{zero}tpp)-(a{zero}bpn-a{zero}tpn)"
    )

    # --- the sampling path itself: gain and linearity ------------------------
    lo_i, hi_i = 0, len(DR14_LEVELS) - 1
    span_ideal = _dr14_ideal_lsb(DR14_LEVELS[hi_i]) - _dr14_ideal_lsb(DR14_LEVELS[lo_i])
    for i, f in enumerate(DR14_LEVELS):
        measure[f"hold_l{i}_lsb"] = f"a{i}hld"
        measure[f"res_l{i}_lsb"] = f"a{i}res"
    measure["samp_span_lsb"] = f"a{hi_i}hld-a{lo_i}hld"
    measure["samp_gain_ratio"] = f"(a{hi_i}hld-a{lo_i}hld)/({span_ideal!r})"
    measure["samp_gain_err_lsb"] = f"(a{hi_i}hld-a{lo_i}hld)-({span_ideal!r})"
    for i in range(lo_i + 1, hi_i):
        frac = (DR14_LEVELS[i] - DR14_LEVELS[lo_i]) / (
            DR14_LEVELS[hi_i] - DR14_LEVELS[lo_i]
        )
        measure[f"samp_inl_l{i}_lsb"] = (
            f"a{i}hld-(a{lo_i}hld+({frac!r})*(a{hi_i}hld-a{lo_i}hld))"
        )
    worst = [
        f"abs(a{i}hld-(a{lo_i}hld+"
        f"({(DR14_LEVELS[i] - DR14_LEVELS[lo_i]) / (DR14_LEVELS[hi_i] - DR14_LEVELS[lo_i])!r})"
        f"*(a{hi_i}hld-a{lo_i}hld)))"
        for i in range(lo_i + 1, hi_i)
    ]
    measure["samp_inl_worst_lsb"] = _fold("max", worst)

    # --- term 3: what the fourth leg costs the bit trial ---------------------
    for tag in ("b4", "b3"):
        analyses.append(
            f"meas tran {tag}set FIND v({tag}_d) AT={DR14_T_SET_NS:.3f}n"
        )
        analyses.append(
            f"meas tran {tag}fin FIND v({tag}_d) AT={DR14_T_RES_NS:.3f}n"
        )
        analyses.append(
            f"meas tran {tag}pre FIND v({tag}_d) AT={DR14_TRIAL_NS - 0.5:.3f}n"
        )
    measure["set_err_4leg_lsb"] = "b4set-b4fin"
    measure["set_err_3leg_lsb"] = "b3set-b3fin"
    measure["set_err_delta_lsb"] = "(b4set-b4fin)-(b3set-b3fin)"
    measure["step_4leg_lsb"] = "b4fin-b4pre"
    measure["step_3leg_lsb"] = "b3fin-b3pre"

    # --- term 4: second-order residue from C_par mismatch --------------------
    ref = f"a{DR14_MIS_LEVEL}"
    for j, dc in enumerate(DR14_DCPAR_FF):
        measure[f"dhold_dc{j}_lsb"] = f"c{j}hld-{ref}hld"
        measure[f"dres_dc{j}_lsb"] = f"c{j}res-{ref}res"
    measure["dres_per_ff_lsb"] = (
        f"(c{len(DR14_DCPAR_FF) - 1}res-{ref}res)/({DR14_DCPAR_FF[-1]!r})"
    )

    # --- the re-taken Input-structure R_on ----------------------------------
    for j, frac in enumerate(DR14_RON_FRACS):
        analyses.append(f"meas tran ron{j} FIND i(vr{j}d) AT={DR14_T_HOLD_NS:.3f}n")
        measure[f"ron_path_l{j}_ohm"] = f"abs({DR14_RON_DV!r}/ron{j})"
        measure[f"ron_cell_l{j}_ohm"] = (
            f"abs({DR14_RON_DV!r}/ron{j})*{float(len(WEIGHTS))!r}"
        )
    rons = [f"abs({DR14_RON_DV!r}/ron{j})" for j in range(len(DR14_RON_FRACS))]
    measure["ron_path_worst_ohm"] = _fold("max", rons)

    # ---- checks -------------------------------------------------------------
    checks["bp_inj_mis_lsb"] = {
        "min": -2.0,
        "max": 2.0,
        "description": (
            "TERM 2's side-to-side mismatch, against the ratified Offset row "
            "(<= 2 LSB, README.md#target-specification). Measured at the "
            "f = 0 level, where both sides sit at V_cm and the ideal sampled "
            "step is exactly zero -- so the differential top plate at the end "
            "of the sample IS the mismatch of the two sides' bottom-plate "
            "switch injection, with nothing subtracted. A common-mode "
            "injection is removed by differential operation and is not "
            "bounded here; the differential part is what lands in a spec row."
        ),
    }
    for i in range(1, len(DR14_LEVELS) - 1):
        checks[f"samp_inl_l{i}_lsb"] = {
            "min": -1.0,
            "max": 1.0,
            "description": (
                "The SAMPLE's own nonlinearity, endpoint-fitted across the "
                "input range, against the ratified INL row (< 1 LSB). This is "
                "the signal-DEPENDENT part of everything that happens during "
                "acquisition and turn-off -- input-switch injection, the "
                "voltage dependence of C_par, and the drive network -- and it "
                "is the part DR-0014's cancellation does NOT remove. The "
                "endpoint gain is removed by construction (that is what an "
                "endpoint fit does) because a pure scale factor on the "
                "sampled value cancels against the same scale factor on the "
                "DAC step; a bow does not."
            ),
        }
    checks["set_err_4leg_lsb"] = {
        "min": -1.0,
        "max": 1.0,
        "description": (
            "TERM 3: how much of the weight-256 step is still missing at the "
            f"comparator strobe, {DR14_SETTLE_HALF_NS:g} ns after the trial "
            "edge, with DR-0014's fourth leg on every bottom plate. Bounded "
            "at the ratified INL row's 1 LSB: an unsettled step is an error "
            "the decision is taken with, and there is no redundancy (DR-0009) "
            "to recover it. `set_err_delta_lsb` reports the part attributable "
            "to the fourth leg specifically, against the three-leg DR-0011 "
            "cell run in the same deck from the same released state."
        ),
    }
    checks["ron_path_worst_ohm"] = {
        "min": 1.0,
        "max": 2000.0,
        "min_spread_pct_by_axis": {"process": 15.0},
        "description": (
            "The ratified Input-structure row's series switch R_on, re-taken "
            "for DR-0014's path: nine parallel cell T-gates per side rather "
            "than one dedicated 40u/80u switch. Bounded loosely -- the "
            "published row states a measured value, not a limit -- but the "
            "PROCESS-AXIS FLOOR is a real corner-sensitivity control: R_on "
            "moves by more than 3x across tt/ss/ff (sim/device-switch-ron/), "
            "so a run that silently pinned every model section to typical "
            "(sim/harness/README.md mechanism 3, and the runner's own "
            "--sabotage-corners negative control) collapses this spread and "
            "fails here."
        ),
    }
    checks[f"hold_l{hi_i}_lsb"] = {
        "min": -1200.0,
        "max": -700.0,
        "description": (
            "END-TO-END LIVENESS: the deck must actually sample. At "
            f"f = {DR14_LEVELS[hi_i]:+.2f} the ideal held differential top "
            f"plate is {_dr14_ideal_lsb(DR14_LEVELS[hi_i]):.1f} LSB (negative "
            "because DR-0014 inverts the residue). The window is wide because "
            "the held value carries the FULL k = C_arr/(C_arr+C_par) "
            "attenuation -- which is precisely the term DR-0014 shows cancels "
            "from the comparator's decision, so it must not be bounded "
            "tightly here as if it were an error."
        ),
    }

    return {
        "name": "dr0014-sampling",
        "description": (
            "The four terms DR-0014's charge-balance derivation assumes away, "
            "each as a measured number over the PVT grid (#61): the top-plate "
            "V_cm switch's charge injection and its side-to-side mismatch; "
            "the bottom-plate input switches' injection after that switch has "
            "already opened; the fourth leg's cost in bit-trial settling "
            f"against the {DR14_SETTLE_HALF_NS:g} ns settling half; and the "
            "second-order residue left by C_par mismatch between the two "
            "sides. Also re-takes the two measurements DR-0014 invalidated "
            "the evidence for -- the sampling path's own gain error and "
            "linearity, and the series R_on of the nine-parallel-T-gate input "
            "path."
        ),
        "claim": (
            "README.md#target-specification -- Offset (<= 2 LSB) for the "
            "side-to-side injection mismatch, INL (< 1 LSB) for the sample's "
            "own nonlinearity and for the unsettled part of a bit trial, and "
            "the Input-structure row's series switch R_on, re-taken for the "
            "path DR-0014 built. The four risk terms themselves have no "
            "ratified row: they are the quantities "
            "spec/decision-records/DR-0014-bottom-plate-sampling.md's "
            "Consequences require to be measured rather than argued, and this "
            "record is that measurement."
        ),
        "netlist": "tb_dr0014_sampling.spice",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["tt", "ss", "ff"],
        "analyses": analyses,
        "measure": measure,
        "checks": checks,
        "evidence": {
            "notes": [
                "TERM 1 IS MEASURED WITHOUT A REFERENCE SIMULATION, and that "
                "is the point of the schedule. Before the sampling instant "
                "the top plate is held at V_cm through a closed switch and "
                "nothing else in the branch moves; after it, the only thing "
                "that has happened is that switch opening. So "
                "tp_inj_*_L*_lsb is the injection itself, not a difference of "
                "two large numbers, and tp_inj_signal_dep_lsb is its total "
                "variation across the full input range -- the number that "
                "decides whether it is an offset (DR-0014's claim) or a gain "
                "and linearity term (the reason DR-0013 needed dummies on the "
                "switch this one replaces).",
                "TERM 4 IS MEASURED AT EXAGGERATED MISMATCH ON PURPOSE. A "
                "centroid-matched layout would leave C_par mismatch around a "
                "percent, where the second-order residue is below the "
                "harness's ~1 uV `meas` result-precision floor "
                "(sim/harness/README.md) -- reporting that would be reporting "
                "the floor, not the term. The deck instead measures the "
                "residue at 10 / 30 / 100 fF of deliberate imbalance, spanning "
                "roughly 5 % to 100 % of the measured C_par, and publishes the "
                "SLOPE (dres_per_ff_lsb) so a reader can price any mismatch "
                "they can defend from a layout. Each dres_dc*_lsb is a "
                "measured value at that imbalance; none of them is "
                "extrapolated.",
                "V_REF AND V_cm ARE IDEAL SOURCES IN THIS DECK. Eighteen array "
                "sides share one netlist so that every A/B comparison here is "
                "a difference of two branches in the SAME simulation; a shared "
                "DR-0002 reference network would couple them and report that "
                "coupling as the effect under test. Reference droop is "
                "measured, with the real network, by sim/adc-inl-dnl/ and "
                "sim/adc-power/. V_cm generation is unbudgeted work under "
                "DR-0011's Consequences and is an ideal source in every deck "
                "in this repo.",
                "THE CONTROLS ARE IDEAL EDGES, NOT THE CONTROLLER'S. "
                "sim/sar-logic-functional/ verifies exhaustively that the "
                "rung-1 controller produces exactly this schedule -- the "
                "four-leg one-hot invariant, and a measured (not assumed) "
                "samp_tp -> samp_bp lead of one bit cycle. Driving it from the "
                "controller here would make four analog measurements depend on "
                "that logic's delays instead of isolating them.",
                "THE THREE-LEG A/B PARTNER IS DECK-LOCAL. tb3_cdac_cell is "
                "adc_cdac_cell with the fourth leg and its driver deleted and "
                "nothing else changed. It is not in "
                "design/adc-top/adc_top.spice because that library describes "
                "the converter as built, and the converter no longer has a "
                "three-leg cell -- but the A/B needs the superseded cell to "
                "attribute the settling delta to the leg rather than to the "
                "corner.",
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


def cpar_deck() -> str:
    return _deck(cpar_netlist())


def cpar_json() -> str:
    return _json(cpar_manifest())


def dr14_deck() -> str:
    return _deck(dr14_netlist())


def dr14_json() -> str:
    return _json(dr14_manifest())


TARGETS = {
    "library": ("design/adc-top/adc_top.spice", library),
    "inl": ("sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice", inl_deck),
    "inl-json": ("sim/adc-inl-dnl/testbench/tb.json", inl_json),
    "fft": ("sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice", fft_deck),
    "fft-json": ("sim/adc-enob-fft/testbench/tb.json", fft_json),
    "power": ("sim/adc-power/testbench/tb_adc_power.spice", power_deck),
    "power-json": ("sim/adc-power/testbench/tb.json", power_json),
    "cpar": ("sim/top-plate-cpar/testbench/tb_top_plate_cpar.spice", cpar_deck),
    "cpar-json": ("sim/top-plate-cpar/testbench/tb.json", cpar_json),
    "dr14": ("sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice", dr14_deck),
    "dr14-json": ("sim/dr0014-sampling/testbench/tb.json", dr14_json),
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
