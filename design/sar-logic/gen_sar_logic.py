#!/usr/bin/env python3
"""Generate the synchronous SAR control-logic netlists (issue #11).

Single source of truth for three committed artifacts:

  design/sar-logic/sar_ctrl.spice                              the subckt library
  sim/sar-logic-functional/testbench/tb_sar_logic_functional.spice
  sim/sar-logic-timing/testbench/tb_sar_logic_timing.spice

The corner runner consumes *self-contained* netlist fragments -- `.include` is
rejected by `sim/harness/testbench.py` on purpose, so a testbench cannot pull
the DUT in by reference and must carry it inline. Hand-maintaining three copies
of a 9-slice, 108-control decode is exactly how a testbench silently drifts
from the design it claims to verify, so the copies are generated instead and
`sim/tests/test_sar_logic_netlist.py` fails CI if a committed file stops
matching this generator.

Usage:
    python3 design/sar-logic/gen_sar_logic.py            # write the files
    python3 design/sar-logic/gen_sar_logic.py --check    # exit 1 if stale
    python3 design/sar-logic/gen_sar_logic.py --stdout library

Architecture implemented here is fixed by ratified decision records; this file
implements them, it does not choose them:

  DR-0003  external clock, M = 16  -> 16 phases per conversion
  DR-0005  10-bit parallel output register in scope, SPI deferred
  DR-0011  MCS / Vcm switching, free MSB, 9 switched weights (256..1) per
           side, mode-dependent side switching -- superseded by DR-0014 on
           the sampling phase ONLY; everything else it decided is re-ratified
  DR-0014  BOTTOM-PLATE sampling: a fourth one-hot leg to V_in per cell, one
           top-plate switch to V_cm per side, and a two-phase sample in which
           the top-plate switch opens FIRST
  DR-0008  synchronous SAR logic (this issue)
  DR-0009  no redundancy / plain binary weighting (this issue)
  DR-0010  fidelity ladder; this netlist is rung 1 (ideal XSPICE digital)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Trial i (i = 1..9) engages the weight-w cell, w = 2**(9-i): 256..1.
WEIGHTS = [2 ** (9 - i) for i in range(1, 10)]
SIDES = ("p", "n")

# Bit-cycle phase map, M = 16 (DR-0003 / README Latency row:
# 4 sample + 10 bit trials + 2 reset/output).
PH_SAMPLE = (0, 1, 2, 3)
PH_TRIAL0 = 4  # free-MSB trial: comparator decides sign of the sampled residue
PH_LAST_TRIAL = 13
PH_LOAD = 14  # output register loads here (visible from ph15)
PH_DRDY = 15

# DR-0014's two-phase sample, laid inside the SAME 4-clock sample window --
# M = 16 and the 1 us conversion do not change, and neither does the clock:
# every edge below is a rising edge of the one external clock, so DR-0008's
# synchronous choice is not quietly re-opened to buy a sub-phase.
#
#   ph0..ph2   top-plate switch CLOSED (top plate held at V_cm) and every
#              bottom plate on V_in: 3 clocks = 187.5 ns of acquisition,
#              7.5 tau of DR-0013's 25 ns input network, so the residual
#              acquisition error is 5.5e-4 of a full-scale step (0.6 LSB of
#              1024 for a rail-to-rail step, 0.07 LSB for the 126 LSB
#              largest step sim/adc-inl-dnl/'s ladder actually takes).
#   ph2 -> ph3 edge   THE SAMPLING INSTANT: the top-plate switch opens. What
#              is frozen on the now-floating top node is the bottom-plate
#              voltage at this edge; nothing the bottom plates do afterwards
#              changes the sampled charge, which is the entire point.
#   ph3        the bottom plates STAY on V_in for one more whole clock. This
#              62.5 ns gap is the isolation DR-0014 is buying: the bottom-
#              plate input switches turn off onto a node that was already
#              released, so their charge injection lands on a driven node
#              and not on the sample.
#   ph3 -> ph4 edge   the bottom plates leave V_in for V_cm.
#   ph4        trial 1 (the free MSB) decides on the strobe, 31.25 ns later
#              -- the same settling budget spec/prior-art-survey.md Sec 1.4
#              allocates to every other bit trial. The slowest cell releases
#              with tau = R_on * w*C_u = 570 ohm * 4.41 pF = 2.51 ns (worst
#              R_on, sim/device-switch-ron/), i.e. 12.4 tau, so the residue
#              is settled to 4e-6 of full scale before the decision.
#
# Whole clocks, one clock edge, no clock-derived control: an earlier draft
# released the bottom plates half a clock into ph3 (as `samp4 & (clk | !ph3)`)
# to buy trial 1 a second 31.25 ns of settling it does not need. That form has
# a static-0 hazard at the ph3 -> ph4 edge -- clk rises one T_CLK_Q before ph3
# falls, so the V_in leg glitches back on for ~0.5 ns AFTER the top plate has
# been released, injecting the input onto an isolated node. It was measured
# doing exactly that (an extra falling edge on sel_in_n at every conversion
# boundary) and is recorded here rather than silently dropped.
PH_SAMPLE_TOP = (0, 1, 2)

# ---------------------------------------------------------------------------
# gate-level timing of the rung-1 model
#
# These are *ideal* placeholders, not gf180mcu numbers. The measured
# gf180mcu_fd_sc_mcu7t5v0 clk->Q + logic-path delay over the full PVT grid is
# a separate evidence record (sim/sar-logic-cell-delay/); DR-0010 states which
# rung owns which claim. Values here are chosen small against the 62.5 ns bit
# cycle so the rung-1 model tests *sequencing*, not timing.
# ---------------------------------------------------------------------------
T_CLK_Q = "0.5n"
T_GATE = "0.2n"


def _ports_ctrl_digital() -> list[str]:
    """Digital port list of `sar_ctrl` (event nodes)."""
    ports = ["clk", "start", "mode", "cmp", "samp_tp", "samp_bp", "drdy"]
    ports += [f"b{b}" for b in range(9, -1, -1)]
    for s in SIDES:
        for w in WEIGHTS:
            ports += [f"rel_{w}{s}", f"hi_{w}{s}", f"lo_{w}{s}"]
    return ports


def _ports_ctrl_analog() -> list[str]:
    """Analog port list of `sar_ctrl_a`.

    Switch-driver names follow design/cdac/cdac_array.sch exactly: in
    `sel_hi_n_256p` the *first* p/n is the transistor polarity of the T-gate
    leg (n = NMOS gate, active high; p = PMOS gate, active low) and the
    *trailing* p/n is the CDAC side. DR-0011's Consequences require `rel` to be
    driven per weight and per side; the schematic draws `rel_n`/`rel_p` as one
    shared pair as a two-cell drawing economy, and says #11 owns the real
    decode -- which is what the per-weight/per-side names below are.

    Only the NMOS-gate (active-high) half of each T-gate leg leaves the
    controller: 54 nets, not 108. The complementary PMOS gate is generated by
    `sar_tgate_drv` local to the CDAC cell it drives. Routing both polarities
    from the controller would double the control-bus width across the array
    floorplan (#16) to save one inverter per leg, and a long complementary
    pair also has to be skew-matched, which a local inverter does not.

    DR-0014 adds two nets, not nineteen. `sel_in_n` is the fourth (V_in) leg
    of every cell on both sides, and it is ONE broadcast net rather than 18
    per-cell copies: all bottom plates sample together by construction, so
    per-cell decode of that leg would carry no information and would widen
    the array control bus by a third for nothing. Each cell's decode is still
    four one-hot legs; one of the four is simply shared. `samp_tp_n` is the
    per-side top-plate switch to V_cm -- also one net, because both sides
    sample on the same edge and their skew is exactly what must NOT differ.
    """
    ports = ["clk", "start", "mode", "cmp", "samp_tp_n", "sel_in_n", "drdy"]
    ports += [f"c{b}" for b in range(9, -1, -1)]
    for s in SIDES:
        for w in WEIGHTS:
            ports += [
                f"rel_n_{w}{s}",
                f"sel_hi_n_{w}{s}",
                f"sel_lo_n_{w}{s}",
            ]
    return ports


def _wrap(prefix: str, items: list[str], width: int = 74) -> list[str]:
    """Emit `prefix` + items as continuation-wrapped netlist lines."""
    lines: list[str] = []
    cur = prefix
    for item in items:
        if len(cur) + 1 + len(item) > width and cur.strip() not in ("+", ""):
            lines.append(cur)
            cur = "+"
        cur += " " + item
    lines.append(cur)
    return lines


def library() -> str:
    """The reusable subckt library: `design/sar-logic/sar_ctrl.spice`."""
    L: list[str] = []
    a = L.append

    a("* ------------------------------------------------------------------")
    a("* sar_ctrl.spice -- synchronous SAR control logic, rung-1 abstraction")
    a("*")
    a("* GENERATED by design/sar-logic/gen_sar_logic.py -- do not edit.")
    a("*")
    a("* Ideal XSPICE event-driven digital primitives (digital.cm: d_dff,")
    a("* d_and, d_or, d_inverter) plus adc_bridge/dac_bridge at the analog")
    a("* boundary. This is rung 1 of the fidelity ladder in DR-0010: it fixes")
    a("* the SEQUENCING and the SWITCH DECODE, and deliberately says nothing")
    a("* about gf180mcu gate delay (rung 3 / sim/sar-logic-cell-delay/ owns")
    a("* that).")
    a("*")
    a("* Conversion, M = 16 clocks (DR-0003), with DR-0014's TWO-PHASE")
    a("* BOTTOM-PLATE sample laid inside the same 4-clock sample window:")
    a("*   ph0..ph2   acquire  samp_tp and samp_bp both asserted: the top")
    a("*                       plate is held at Vcm by its own switch and")
    a("*                       every bottom plate tracks V_in through the")
    a("*                       cell's fourth leg")
    a("*   ph2->ph3   THE SAMPLING INSTANT -- samp_tp falls, the top-plate")
    a("*                       switch opens and the top node floats")
    a("*   ph3        the bottom plates stay on V_in one more clock")
    a("*   ph3->ph4   samp_bp falls a full bit cycle after the sampling")
    a("*                       instant: the bottom plates leave V_in for Vcm")
    a("*                       onto a node that is ALREADY isolated, which")
    a("*                       is the whole reason bottom-plate sampling is")
    a("*                       worth a fourth leg (DR-0014, README note [d])")
    a("*   ph4        trial 1  free MSB -- no array switching at all, the")
    a("*                       comparator decides the sign of the sampled")
    a("*                       residue (DR-0014 keeps DR-0011's free MSB)")
    a("*   ph5..ph13  trials 2..10, weights 256,128,...,1 engaged in turn")
    a("*   ph14       output register loads the 10 decisions")
    a("*   ph15       drdy asserted; array released back to Vcm")
    a("*")
    a("* Switch decode per weight w and side s -- FOUR one-hot legs per cell")
    a("* now, not three -- from the slice's own engage flag `eng`, the")
    a("* direction bit `dir` (= the decision of the PREVIOUS trial, which is")
    a("* also that trial's output bit) and the shared sample control `smp`:")
    a("*   in  = smp                      bottom plate on V_in (DR-0014)")
    a("*   rel = !eng & !smp              bottom plate parked at Vcm")
    a("*   p-side:  hi = eng &  dir       -> V_REF      lo = eng & !dir -> GND")
    a("*   n-side:  hi = eng & !dir       -> V_REF      lo = eng &  dir -> GND")
    a("*   n-side is additionally gated by `mode` (1 = differential): in")
    a("*   single-ended mode every n-side cell stays released to Vcm for the")
    a("*   whole conversion, per DR-0011 -- driving it too would double every")
    a("*   step and cost a bit of resolution. The `in` leg is NOT mode-gated:")
    a("*   both sides must acquire their own input pin, and DR-0011's mode")
    a("*   rule is about bit trials, not about the sample phase.")
    a("*   `eng` is zero for the whole sample window, so exactly one of the")
    a("*   four legs conducts at every instant -- the invariant")
    a("*   sim/sar-logic-functional/ measures directly as sw_conflict_*.")
    a("*")
    a("* Sign convention, RE-DERIVED FOR DR-0014 and the one place the")
    a("* superseded record's decode could not simply be carried forward.")
    a("* Sampling on the bottom plate INVERTS the residue with respect to the")
    a("* input: after the sample, top_p - top_n = -k*(V_inp - V_inn). The")
    a("* comparator is wired conventionally (cmp = 1 when top_p > top_n), so")
    a("* the controller inverts it ONCE at its own boundary --")
    a("*")
    a("*     dec = !cmp    = 1 when the sampled input is ABOVE the DAC's")
    a("*                     current estimate, i.e. 'add this weight'")
    a("*")
    a("* -- and `dir` therefore still holds the OUTPUT BIT of its position,")
    a("* exactly as under DR-0011, at the cost of the hi/lo assignment above")
    a("* being the mirror of DR-0011's. Inverting only one of the two would")
    a("* either diverge (right code polarity, wrong feedback direction) or")
    a("* emit the one's complement of the code (right feedback, wrong bits);")
    a("* both were checked against the closed loop before this form was")
    a("* chosen, and sim/sar-logic-functional/ falsifies either error on")
    a("* every one of the 1024 codes in both modes.")
    a("* ------------------------------------------------------------------")
    a("")
    a("* --- ideal digital primitives -------------------------------------")
    a(f".model sarl_dff d_dff(clk_delay={T_CLK_Q} set_delay={T_CLK_Q}")
    a(f"+ reset_delay={T_CLK_Q} ic=0 rise_delay={T_CLK_Q} fall_delay={T_CLK_Q})")
    a(f".model sarl_dff1 d_dff(clk_delay={T_CLK_Q} set_delay={T_CLK_Q}")
    a(f"+ reset_delay={T_CLK_Q} ic=1 rise_delay={T_CLK_Q} fall_delay={T_CLK_Q})")
    a(f".model sarl_and d_and(rise_delay={T_GATE} fall_delay={T_GATE} input_load=0)")
    a(f".model sarl_or d_or(rise_delay={T_GATE} fall_delay={T_GATE} input_load=0)")
    a(f".model sarl_inv d_inverter(rise_delay={T_GATE} fall_delay={T_GATE}")
    a("+ input_load=0)")
    a("")
    a("* --- enabled bit register -----------------------------------------")
    a("* Captures `d` on the clock edge that ENDS the phase in which `en` is")
    a("* asserted, and holds otherwise. Written as an explicit D-mux rather")
    a("* than a gated clock: gating the clock with a phase signal that itself")
    a("* changes one gate delay after the clock edge creates a spurious")
    a("* rising edge on the gated clock, which is a real bug in a real")
    a("* implementation, not just in this model.")
    a(".subckt sar_bitreg clk d en q qb")
    a("a_inv en enb sarl_inv")
    a("a_sel [en d] dsel sarl_and")
    a("a_hold [enb q] dhold sarl_and")
    a("a_mux [dsel dhold] dnext sarl_or")
    a("a_ff dnext clk NULL NULL q qb sarl_dff")
    a(".ends sar_bitreg")
    a("")
    a("* --- one bit slice: engage flag + direction bit + switch decode -----")
    a("* `arm`     one-hot phase pulse of the trial BEFORE this slice's own")
    a("*           trial: the slice engages on the edge entering its trial,")
    a("*           and the direction bit captures the decision made during")
    a("*           `arm` (which is also this bit position's output bit).")
    a("* `endconv` forces the engage flag low on the edge leaving the last")
    a("*           trial, releasing the whole array back to Vcm for the next")
    a("*           sample phase.")
    a("* `dec`     the comparator decision in OUTPUT-BIT polarity (= !cmp;")
    a("*           see the sign-convention note in the header).")
    a("* `smpb`    the inverse of the shared bottom-plate sample control,")
    a("*           distributed already-inverted so that all four legs of the")
    a("*           cell come out at the SAME logic depth. That is not")
    a("*           cosmetic: `rel` and the V_in leg are complementary during")
    a("*           the sample window, so a one-gate depth difference between")
    a("*           them opens a window in which a cell drives V_in and Vcm at")
    a("*           once -- which is exactly what the one-hot invariant is")
    a("*           there to catch, and it would catch this generator.")
    a(".subckt sar_slice clk dec mode arm endconv smpb dir dirb")
    a("+ rel_p hi_p lo_p rel_n hi_n lo_n")
    a("a_set [arm eng] eng_set sarl_or")
    a("a_ninv endconv nend sarl_inv")
    a("a_keep [eng_set nend] eng_d sarl_and")
    a("a_ff eng_d clk NULL NULL eng engb sarl_dff")
    a("xdir clk dec arm dir dirb sar_bitreg")
    a("* p side: always driven")
    a("a_relp [engb smpb] rel_p sarl_and")
    a("a_hip [eng dir] hi_p sarl_and")
    a("a_lop [eng dirb] lo_p sarl_and")
    a("* n side: driven only in differential mode (DR-0011). `engnb` is built")
    a("* as !eng | !mode rather than as an inverter on `engn`, so that it")
    a("* lands at the same depth as `engn` and rel_n/hi_n/lo_n switch")
    a("* together -- the same delay-balance argument as `smpb` above.")
    a("a_engn [eng mode] engn sarl_and")
    a("a_modeb mode modeb sarl_inv")
    a("a_engnb [engb modeb] engnb sarl_or")
    a("a_reln [engnb smpb] rel_n sarl_and")
    a("a_hin [engn dirb] hi_n sarl_and")
    a("a_lon [engn dir] lo_n sarl_and")
    a(".ends sar_slice")
    a("")
    a("* --- 16-phase one-hot sequencer ------------------------------------")
    a("* A one-hot ring, seeded by ph15's ic=1 so the very first clock edge")
    a("* enters ph0 (sample) with exactly one token in the ring. `start`")
    a("* forces a synchronous restart: it sets stage 0 and clears every other")
    a("* stage on the same edge, so an asserted `start` cannot inject a")
    a("* SECOND token alongside the circulating one.")
    a(".subckt sar_seq clk start " + " ".join(f"ph{k}" for k in range(16)))
    a("a_nstart start nstart sarl_inv")
    a("a_d0 [ph15 start] d0 sarl_or")
    a("a_ff0 d0 clk NULL NULL ph0 ph0b sarl_dff")
    for k in range(1, 16):
        model = "sarl_dff1" if k == 15 else "sarl_dff"
        a(f"a_d{k} [ph{k - 1} nstart] d{k} sarl_and")
        a(f"a_ff{k} d{k} clk NULL NULL ph{k} ph{k}b {model}")
    a(".ends sar_seq")
    a("")
    a("* --- digital top ----------------------------------------------------")
    L += _wrap(".subckt sar_ctrl", _ports_ctrl_digital())
    a("xseq clk start " + " ".join(f"ph{k}" for k in range(16)) + " sar_seq")
    a("* ---- DR-0014's two-phase sample ----------------------------------")
    a("* `samp_tp` closes the top-plate switch for ph0..ph2 and opens it on")
    a("* the edge into ph3: THAT edge is the sampling instant. `samp_bp`")
    a("* keeps every bottom plate on V_in for the whole 4-clock window, so")
    a("* the input legs turn off one full clock LATER, onto a top node that")
    a("* is already floating. Both are one-hot phase ORs off the same ring:")
    a("* one external clock, rising edges only (DR-0008), no gated or")
    a("* inverted clock anywhere in the sample path.")
    a("* `samp_bp` is emitted through smpb -> inverter rather than straight")
    a("* off the OR so that it lands at the SAME logic depth as each cell's")
    a("* `rel`, which is AND(engb, smpb). Those two legs are complementary")
    a("* across the sample boundary, so a one-gate depth difference would")
    a("* leave every cell driving V_in and V_cm together for 0.2 ns.")
    a("a_samp4 [" + " ".join(f"ph{k}" for k in PH_SAMPLE) + "] samp4 sarl_or")
    a(
        "a_samptp ["
        + " ".join(f"ph{k}" for k in PH_SAMPLE_TOP)
        + "] samp_tp sarl_or"
    )
    a("a_smpb samp4 smpb sarl_inv")
    a("a_sampbp smpb samp_bp sarl_inv")
    a("* The comparator decision, inverted once here into output-bit")
    a("* polarity: bottom-plate sampling inverts the residue with respect to")
    a("* the input (DR-0014). See the header's sign-convention note.")
    a("a_dec cmp dec sarl_inv")
    a(f"a_drdy ph{PH_DRDY} drdy_n sarl_inv")
    a("a_drdy2 drdy_n drdy sarl_inv")
    for i, w in enumerate(WEIGHTS, start=1):
        arm = PH_TRIAL0 + i - 1  # ph4..ph12
        bit = 10 - i  # b9..b1
        a(
            f"xs{w} clk dec mode ph{arm} ph{PH_LAST_TRIAL} smpb q{bit} q{bit}b "
            f"rel_{w}p hi_{w}p lo_{w}p rel_{w}n hi_{w}n lo_{w}n sar_slice"
        )
    a(f"xb0 clk dec ph{PH_LAST_TRIAL} q0 q0b sar_bitreg")
    a("* 10-bit parallel output register (DR-0005: in scope, SPI deferred)")
    for b in range(9, -1, -1):
        a(f"xo{b} clk q{b} ph{PH_LOAD} b{b} b{b}b sar_bitreg")
    a(".ends sar_ctrl")
    a("")
    a("* --- analog-boundary wrapper ----------------------------------------")
    a("* Presents the controller at the analog boundary with the port names")
    a("* design/cdac/cdac_array.sch uses, so the two connect directly. Only")
    a("* the NMOS-gate (active-high) half of each T-gate leg is routed out of")
    a("* the controller; `sar_tgate_drv` below makes the PMOS gate locally at")
    a("* the cell. Bridges are VECTOR instances on purpose: 54 scalar")
    a("* dac_bridges would put 54 separate sources in the analog matrix.")
    a("* DR-0014's two additions ride on the SCALAR bridge group with drdy")
    a("* and the code bits, not on the 54-wide array bus: `sel_in_n` is one")
    a("* broadcast net feeding every cell's fourth leg and `samp_tp_n` is the")
    a("* per-side top-plate switch, so the array control bus grows from 54 to")
    a("* 55 wires, not to 72.")
    L += _wrap(".subckt sar_ctrl_a", _ports_ctrl_analog())
    a("a_in [clk start mode cmp] [dclk dstart dmode dcmp] sarl_adc")
    dports = ["dclk", "dstart", "dmode", "dcmp", "dsamp_tp", "dsamp_bp", "ddrdy"]
    dports += [f"db{b}" for b in range(9, -1, -1)]
    for s in SIDES:
        for w in WEIGHTS:
            dports += [f"drel_{w}{s}", f"dhi_{w}{s}", f"dlo_{w}{s}"]
    L += _wrap("xctrl", dports + ["sar_ctrl"])
    outn = ["dsamp_tp", "dsamp_bp", "ddrdy"] + [f"db{b}" for b in range(9, -1, -1)]
    anaout = ["samp_tp_n", "sel_in_n", "drdy"] + [f"c{b}" for b in range(9, -1, -1)]
    L += _wrap("a_dout [" + " ".join(outn) + "]", ["[" + " ".join(anaout) + "]"])
    L[-1] += " sarl_dac"
    g_nodes, g_ports = [], []
    for s in SIDES:
        for w in WEIGHTS:
            for f, port in (("rel", "rel"), ("hi", "sel_hi"), ("lo", "sel_lo")):
                g_nodes.append(f"d{f}_{w}{s}")
                g_ports.append(f"{port}_n_{w}{s}")
    L += _wrap("a_gn [" + " ".join(g_nodes) + "]", ["[" + " ".join(g_ports) + "]"])
    L[-1] += " sarl_dac"
    a(".ends sar_ctrl_a")
    a("")
    a("* --- local T-gate driver -------------------------------------------")
    a("* One per T-gate leg, placed with the CDAC cell (#15/#16), not with")
    a("* the controller: `gn` is the controller's active-high control and")
    a("* `gp` the complementary PMOS gate. Modelled as an ideal inverter at")
    a("* rung 1; at rung 3 it is one standard-cell inverter.")
    a(".subckt sar_tgate_drv gn gp")
    a("a_adc gn dgn sarl_adc")
    a("a_inv dgn dgp sarl_inv")
    a("a_dac dgp gp sarl_dac")
    a(".ends sar_tgate_drv")
    a("")
    a("* Bridge models. Thresholds and rails track the PVT point's supply, so")
    a("* the supply axis of the corner grid actually moves something in this")
    a("* otherwise PVT-invariant model.")
    a(".model sarl_adc adc_bridge(in_low={vdd_val*0.4} in_high={vdd_val*0.6})")
    a(".model sarl_dac dac_bridge(out_low=0 out_high={vdd_val}")
    a("+ out_undef={vdd_val/2} t_rise=0.3n t_fall=0.3n)")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# testbench harnesses
# ---------------------------------------------------------------------------

CLK_PERIOD_NS = 62.5  # M = 16 at 1 MS/s (DR-0003)
CONV_NS = 16 * CLK_PERIOD_NS  # 1 us


def _loop(
    tag: str,
    mode_expr: str,
    cmp_delay: str | None = None,
    r_ohm: str = "1k",
    c_val: str = "2.56p",
    clk_net: str = "clk",
) -> list[str]:
    """One closed SAR loop: controller + ideal CDAC + ideal comparator.

    The CDAC is built behaviourally FROM THE CONTROLLER'S OWN SWITCH-DRIVER
    OUTPUTS, so the loop is not a tautology: a wrong decode (wrong direction,
    wrong side in single-ended mode, a cell that never releases) moves the top
    plate wrongly and the conversion produces the wrong code.

    `r_ohm`/`c_val` size the first-order DAC-settling network (default:
    `functional()`/`timing()`'s original placeholder, tau = 1k * 2.56p =
    2.56 ns, spec/prior-art-survey.md Sec 1.4's network -- unchanged so this
    default keeps those two committed netlists byte-identical).
    `budget_closure()` below overrides both with the real worst-case
    charge-divider values #8's CDAC-sizing memo and #10's switch-Ron
    measurement actually produced. `clk_net` lets one deck host loops driven
    by more than one clock (budget_closure() needs both a 1 MS/s and a
    2 MS/s clock in the same file).
    """
    L: list[str] = []
    a = L.append
    ports = [f"{tag}_{p}" if p not in ("clk",) else clk_net for p in _ports_ctrl_analog()]
    # mode / start / cmp are driven locally
    ports[1] = f"{tag}_start"
    ports[2] = f"{tag}_mode"
    ports[3] = f"{tag}_cmpo"
    a(f"* ---- loop {tag} ----")
    a(f"v{tag}start {tag}_start 0 dc 0")
    a(f"v{tag}mode {tag}_mode 0 dc {mode_expr}")
    L += _wrap(f"x{tag}", ports + ["sar_ctrl_a"])
    # Ideal sample-and-hold on each side, clocked by the TOP-PLATE switch
    # control and not by the bottom-plate one. That is the DR-0014 sampling
    # instant expressed in the behavioural model: with the top node floating,
    # charge conservation makes the held value the bottom-plate voltage at
    # the edge `samp_tp_n` fell, and nothing the bottom plates do in the
    # remaining half clock can change it.
    a(f"s{tag}p {tag}_vinp {tag}_shp {tag}_samp_tp_n 0 sarl_sw")
    a(f"s{tag}n {tag}_vinn {tag}_shn {tag}_samp_tp_n 0 sarl_sw")
    a(f"c{tag}p {tag}_shp 0 1p")
    a(f"c{tag}n {tag}_shn 0 1p")
    # A SECOND sample-and-hold pair on a deliberately late copy of the
    # sampling control, used ONLY to compute the expected code. `samp_tp_n`
    # rises at the same instant `drdy` falls, so an expected code derived from
    # the DUT's own hold node changes while the drdy evaluation window is
    # still closing, and reports a spurious one-LSB error every conversion.
    # These track ~7 ns longer, which holds the expected code valid across
    # that edge. The input moves ~0.007 LSB in 7 ns at the ramp rate used
    # here, i.e. 70x below the 0.5 LSB the check has to resolve.
    a(f"r{tag}sd {tag}_samp_tp_n {tag}_sampd 10k")
    a(f"c{tag}sd {tag}_sampd 0 1p")
    a(f"s{tag}xp {tag}_vinp {tag}_shxp {tag}_sampd 0 sarl_sw")
    a(f"s{tag}xn {tag}_vinn {tag}_shxn {tag}_sampd 0 sarl_sw")
    a(f"c{tag}xp {tag}_shxp 0 1p")
    a(f"c{tag}xn {tag}_shxn 0 1p")
    # Behavioural CDAC top plates, driven by the controller's own NMOS gate
    # drives -- now FOUR legs per cell, and the DR-0014 charge-domain result
    # rather than DR-0011's:
    #
    #   V_top = V_cm + k*[ (V_cm - V_sampled) + sum_j w_j*(V_bp,j - V_cm)/512 ]
    #
    # with k = C_arr/(C_arr + C_par) = 1 in this ideal model. The sampled
    # input therefore enters INVERTED about V_cm, which is the whole
    # behavioural consequence of moving the sampling phase to the bottom
    # plates, and it is what the controller's `dec = !cmp` inversion answers.
    # The `sel_in_n` term is carried so the expression also describes the
    # bottom plates DURING the sample window (all of them on that side's
    # input pin), not only after it.
    for s in SIDES:
        terms = []
        for w in WEIGHTS:
            terms.append(
                f"{w}*((v({tag}_rel_n_{w}{s})*vcm+v({tag}_sel_hi_n_{w}{s})*vref"
                f"+v({tag}_sel_in_n)*v({tag}_vin{s}))/vdd_val-vcm)"
            )
        sh = f"{tag}_shp" if s == "p" else f"{tag}_shn"
        L += _wrap(
            f"b{tag}top{s} {tag}_topi{s} 0 V = 2*vcm-v({sh})+(1.0/512)*(",
            [" + ".join(terms) + " )"],
        )
    # first-order DAC settling network. Default (r_ohm/c_val unset): tau =
    # 1k * 2.56p = 2.56 ns, the survey's spec/prior-art-survey.md Sec 1.4
    # placeholder network -- unchanged from the original functional()/
    # timing() decks. Real settling over PVT is sim/cdac-bit-settling/'s
    # claim, not this model's; budget_closure() below overrides r_ohm/c_val
    # with that claim's real worst-case numbers instead of the placeholder.
    a(f"r{tag}p {tag}_topip {tag}_topp {r_ohm}")
    a(f"r{tag}n {tag}_topin {tag}_topn {r_ohm}")
    a(f"c{tag}tp {tag}_topp 0 {c_val}")
    a(f"c{tag}tn {tag}_topn 0 {c_val}")
    # ideal comparator
    if cmp_delay is None:
        a(
            f"b{tag}cmp {tag}_cmpo 0 V = "
            f"v({tag}_topp) > v({tag}_topn) ? vdd_val : 0"
        )
    else:
        a(
            f"b{tag}cmp {tag}_cmpi 0 V = "
            f"v({tag}_topp) > v({tag}_topn) ? vdd_val : 0"
        )
        a(
            f"t{tag}d {tag}_cmpi 0 {tag}_cmpo 0 z0=50 td={cmp_delay}"
        )
        a(f"r{tag}term {tag}_cmpo 0 50")
    # decoded output code
    terms = [f"({2 ** b})*(v({tag}_c{b})>vth ? 1 : 0)" for b in range(9, -1, -1)]
    L += _wrap(f"b{tag}code {tag}_code 0 V = ", [" + ".join(terms)])
    # Switch-driver one-hot invariant, RE-DERIVED FOR DR-0014's FOUR legs and
    # normalised to the supply: on every cell, on both sides, exactly one of
    # {sel_in, rel, sel_hi, sel_lo} is asserted at all times. Summed as
    # absolute deviations over all 18 cells, so a single cell that ever drives
    # two sources at once (or none) shows up here.
    #
    # The fourth leg makes this check strictly stronger than its three-leg
    # ancestor, and in the direction DR-0014 needs: `sel_in` shorts the input
    # pin to the bottom plate, so a cell that held `rel` and `sel_in` together
    # would short V_in to V_cm, and one that held `sel_in` with `sel_hi` or
    # `sel_lo` would short the input pin to a reference rail. It is also what
    # catches a decode whose four legs are individually correct but skewed --
    # see the delay-balance note on sar_slice.
    terms = []
    for s in SIDES:
        for w in WEIGHTS:
            terms.append(
                f"abs(v({tag}_sel_in_n)+v({tag}_rel_n_{w}{s})"
                f"+v({tag}_sel_hi_n_{w}{s})"
                f"+v({tag}_sel_lo_n_{w}{s})-vdd_val)"
            )
    L += _wrap(f"b{tag}conf {tag}_conf 0 V = (", [" + ".join(terms) + ")/vdd_val"])
    # n-side activity, normalised to the supply so the bound is a count of
    # engaged cells rather than a voltage: the direct, non-inferential form of
    # DR-0011's mode-dependent rule. Single-ended must leave every n-side cell
    # released to Vcm for the whole conversion (this stays 0); differential
    # must engage all nine of them (this reaches 9 by the last trial).
    terms = [
        f"v({tag}_sel_hi_n_{w}n)+v({tag}_sel_lo_n_{w}n)" for w in WEIGHTS
    ]
    L += _wrap(f"b{tag}nside {tag}_nside 0 V = (", [" + ".join(terms) + ")/vdd_val"])
    # DR-0014's two-phase sample, as two DUTY-CYCLE nodes rather than as a
    # pair of edge times, and this is a correction taken from a run rather
    # than a preference.
    #
    # The first form of this check measured the two controls' falling edges
    # directly (`meas WHEN v(samp_tp_n)=1.4 FALL=k` against the same on
    # sel_in_n) and required their difference to be one bit cycle to within
    # 1 ns. That is not measurable in the deck it was put in:
    # sim/sar-logic-functional/ runs 1024.5 us with a 20 ns MAXIMUM TIMESTEP,
    # so a `WHEN` crossing on a 0.3 ns bridge transition is interpolated from
    # samples up to 20 ns apart. Record 20260802-094246-16ec0f1 measured the
    # same, unchanged, correct design as 61.28 ns at conversion 5 and 63.30 ns
    # at conversion 500 -- a 2 ns spread on a quantity whose true value is one
    # clock plus one inverter, i.e. the instrument's resolution, not the
    # design's jitter. That record is committed, failing, as the evidence for
    # this change. The response is to measure something the instrument can
    # resolve, not to widen the window until the unresolved number fits.
    #
    # A TIME AVERAGE over an integer number of conversions is exactly that
    # something: it is an integral, so it is insensitive to where the samples
    # land inside an edge, and it is phase-independent -- averaging a periodic
    # waveform over N whole periods gives the same answer wherever the window
    # starts.
    #
    #   <tag>_acq = samp_tp_n / vdd          duty -> acquisition window
    #   <tag>_iso = (sel_in_n - samp_tp_n) / vdd
    #
    # `iso` is +1 while the bottom plates are still on V_in and the top plate
    # has already been released -- the isolation gap DR-0014 exists to create.
    # Both controls rise on the SAME clock edge (ph15 -> ph0), so the mean of
    # `iso` over whole conversions is the difference of the two pulse widths,
    # which is the fall-order lead: positive means sel_in_n falls LAST, which
    # is the record's ordering claim, and its magnitude is the gap in ns per
    # 1000 ns conversion. If the two controls were ever swapped the mean goes
    # negative; if the second phase were dropped it goes to zero. Neither
    # failure can hide inside a timestep.
    a(f"b{tag}acq {tag}_acq 0 V = v({tag}_samp_tp_n)/vdd_val")
    a(
        f"b{tag}iso {tag}_iso 0 V = (v({tag}_sel_in_n)"
        f"-v({tag}_samp_tp_n))/vdd_val"
    )
    return L


def _functional_body(nconv: int) -> list[str]:
    """Exhaustive code sweep, both input modes, in one deck."""
    L: list[str] = []
    a = L.append
    t_end_ns = nconv * CONV_NS
    a("* ==================================================================")
    a("* tb_sar_logic_functional -- exhaustive functional verification of")
    a("* the synchronous SAR controller (issue #11).")
    a("*")
    a("* GENERATED by design/sar-logic/gen_sar_logic.py -- do not edit.")
    a("*")
    a("* Two independent closed loops run in the same deck: `se` in")
    a("* single-ended mode and `df` in differential mode (DR-0011's two")
    a("* input modes, which switch a DIFFERENT NUMBER OF SIDES per trial and")
    a("* therefore need separate coverage, not one run with a flag flipped).")
    a("*")
    a(f"* Each loop converts {nconv} times. The input ramps by exactly one")
    a("* LSB of its own mode per conversion, offset half an LSB so every")
    a("* sample lands mid-code, so the run exercises every one of the 1024")
    a("* output codes exactly once -- i.e. every possible bit-trial decision")
    a("* sequence, since a plain-binary SAR with no redundancy (DR-0009) has")
    a("* exactly one decision sequence per code.")
    a("*")
    a("* All 1024 conversions are checked with two scalars per mode, not")
    a("* 1024 assertions: an error signal (converted code minus the")
    a("* closed-form ideal code of the held sample) is evaluated during every")
    a("* drdy window and its MAX and MIN over the whole run are measured. A")
    a("* single wrong conversion anywhere moves one of them by >= 1 LSB.")
    a("*")
    a("* DR-0014 (bottom-plate sampling) changes three things in this deck")
    a("* and they are stated here rather than left to be inferred from the")
    a("* netlist: (1) the behavioural top plate is now")
    a("* 2*V_cm - V_sampled + DAC, i.e. the sampled input enters INVERTED,")
    a("* (2) the ideal sample-and-hold is clocked by the TOP-PLATE switch")
    a("* control `samp_tp_n`, which is the sampling instant, not by the")
    a("* bottom-plate control that falls one clock later, and (3) the")
    a("* one-hot invariant is over FOUR legs per cell. The two-phase sample")
    a("* itself is measured as `iso_gap_ns` in tb.json, from the `_iso` duty-")
    a("* cycle node below: the behavioural loop cannot catch an ordering bug")
    a("* on its own, because its sample-and-hold is clocked by the top-plate")
    a("* control by construction, so the ordering is asserted on the")
    a("* controller's own two output controls instead. The TIGHT bound on")
    a("* that number is sim/sar-logic-timing/'s, not this deck's -- see the")
    a("* note on the `_iso` node for why a 20 ns maximum timestep cannot")
    a("* carry a sub-nanosecond timing claim.")
    a("* ==================================================================")
    a("")
    a("* V_REF is ratiometric to the supply here: the ratified spec (README")
    a("* note [c]) makes V_REF <= V_DD a hard condition, so a fixed 3.3 V")
    a("* reference is not legal at the 2.97 V corner. Taking V_REF = V_DD")
    a("* keeps the deck legal at every point of the supply axis; the code")
    a("* check is ratiometric too, so it is unaffected.")
    a(".param vref={vdd_val}")
    a(".param vcm={vdd_val/2}")
    a(".param vth={vdd_val/2}")
    a(".param lsbse={vdd_val/1024}")
    a(".param lsbdf={vdd_val/512}")
    a(".model sarl_sw sw(vt={vdd_val/2} vh=0 ron=1 roff=1e12)")
    a("")
    a(f"vclk clk 0 pulse(0 {{vdd_val}} 0 100p 100p {CLK_PERIOD_NS / 2}n"
      f" {CLK_PERIOD_NS}n)")
    a("")
    L += _loop("se", "0")
    a("* single-ended: the p side samples V_in over 0..V_REF, the n side is")
    a("* pinned at V_cm (DR-0011). Full scale = V_REF, LSB = V_REF/1024.")
    a(f"vsein se_vinp 0 pwl(0 {{lsbse/2}} {t_end_ns}n {{vref+lsbse/2}})")
    a("vsecm se_vinn 0 dc {vcm}")
    a("bseexp se_exp 0 V = "
      "min(max(floor(v(se_shxp)/lsbse),0),1023)")
    a("bseerr se_err 0 V = v(se_drdy)>vth ? v(se_code)-v(se_exp) : 0")
    a("")
    L += _loop("df", "{vdd_val}")
    a("* differential: both pins swing +-V_REF/2 about V_cm, so the")
    a("* differential input covers +-V_REF. Full scale = 2*V_REF,")
    a("* LSB = V_REF/512, mid-scale code 512 at zero differential input.")
    a(f"vdfp df_vinp 0 pwl(0 {{vcm-vref/2+lsbdf/4}} {t_end_ns}n"
      f" {{vcm+vref/2+lsbdf/4}})")
    a(f"vdfn df_vinn 0 pwl(0 {{vcm+vref/2-lsbdf/4}} {t_end_ns}n"
      f" {{vcm-vref/2-lsbdf/4}})")
    a("bdfexp df_exp 0 V = "
      "min(max(512+floor((v(df_shxp)-v(df_shxn))/lsbdf),0),1023)")
    a("bdferr df_err 0 V = v(df_drdy)>vth ? v(df_code)-v(df_exp) : 0")
    return L


def _timing_body() -> list[str]:
    """Comparator-decision-delay margin, tie handling, cadence."""
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_sar_logic_timing -- what the synchronous choice actually buys,")
    a("* measured rather than asserted (issue #11, DR-0008).")
    a("*")
    a("* GENERATED by design/sar-logic/gen_sar_logic.py -- do not edit.")
    a("*")
    a("* Four single-ended loops, identical except for a delay inserted")
    a("* between the comparator\'s analog decision and the controller")
    a("* sampling it. The delay stands in for everything that has to happen")
    a("* inside one 62.5 ns bit cycle before the latching edge: DAC settling,")
    a("* comparator regeneration, and logic propagation.")
    a("*   ok   0 ns    reference")
    a("*   lt  40 ns    the whole of the ~40 ns of per-cycle slack the")
    a("*                survey (Sec 4.2) claims a 62.5 ns bit cycle has,")
    a("*                spent in one place")
    a("*   xl  50 ns    80 % of the cycle consumed -- still correct")
    a("*   bad 70 ns    DELIBERATELY past the 62.5 ns cycle: the decision")
    a("*                arrives after the edge that was supposed to latch it")
    a("*")
    a("* The 50 ns point is not the survey's original guess: an earlier draft")
    a("* of this deck used 55 ns and measured a real failure (max|err| = 2")
    a("* LSB against a >= 1 LSB threshold). Bisecting against this SAME")
    a("* behavioural DAC/comparator model found the true boundary between")
    a("* 50 ns (exact) and 52 ns (max|err| = 1 LSB, already over the 0.5 LSB")
    a("* bound). 50 ns is kept as the bracket point precisely because it is")
    a("* the largest round number this model measures as exact, not because")
    a("* it was the original guess -- CLAUDE.md requires a measured number")
    a("* here, not an assumed one. DR-0010 records the gap between the")
    a("* survey's slack estimate and this measured boundary; the shortfall")
    a("* is attributed to this testbench's RC DAC-settling model (tau =")
    a("* 2.56 ns) consuming part of the delay budget the survey treated as")
    a("* separate, not to a synchronous-logic problem.")
    a("*")
    a("* `bad` is the negative control, and it is the reason the other three")
    a("* mean anything: its check asserts the conversion IS wrong. Without a")
    a("* case that must fail, an err == 0 result on the first three would not")
    a("* show that this testbench can detect a broken conversion at all.")
    a("*")
    a("* A fifth loop, `tie`, holds its input exactly on the free-MSB")
    a("* decision threshold (v_in = V_cm to the last bit) for the whole run.")
    a("* That is the near-metastable input a real comparator resolves slowly")
    a("* or wrongly. The claim under test is NOT that the code is right --")
    a("* on an exact tie either adjacent code is correct -- but that the")
    a("* conversion still COMPLETES on schedule: drdy keeps arriving exactly")
    a("* 16 clocks apart. That is the concrete form of the row")
    a("* spec/prior-art-survey.md Sec 4.3 gives synchronous logic (\'a stalled")
    a("* decision corrupts one bit\') against asynchronous (\'a stalled")
    a("* decision stalls the whole conversion; needs a timeout/watchdog\').")
    a("* ==================================================================")
    a("")
    a(".param vref={vdd_val}")
    a(".param vcm={vdd_val/2}")
    a(".param vth={vdd_val/2}")
    a(".param lsbse={vdd_val/1024}")
    a(".model sarl_sw sw(vt={vdd_val/2} vh=0 ron=1 roff=1e12)")
    a("")
    a(f"vclk clk 0 pulse(0 {{vdd_val}} 0 100p 100p {CLK_PERIOD_NS / 2}n"
      f" {CLK_PERIOD_NS}n)")
    a("")
    for tag, delay in (("ok", None), ("lt", "40n"), ("xl", "50n"),
                       ("bad", "70n")):
        L += _loop(tag, "0", cmp_delay=delay)
        a(f"* {tag}: input ramps one LSB per conversion THROUGH mid-scale")
        a("* (codes 507..515), so the run crosses the major carry where every")
        a("* bit changes at once -- the worst case for a late decision -- and")
        a("* exercises both branches of the free-MSB trial.")
        a(f"v{tag}in {tag}_vinp 0 pwl(0 {{vcm-4.75*lsbse}} 8u"
          f" {{vcm+3.25*lsbse}})")
        a(f"v{tag}cm {tag}_vinn 0 dc {{vcm}}")
        a(f"b{tag}exp {tag}_exp 0 V = "
          f"min(max(floor(v({tag}_shxp)/lsbse),0),1023)")
        a(f"b{tag}err {tag}_err 0 V = "
          f"v({tag}_drdy)>vth ? v({tag}_code)-v({tag}_exp) : 0")
        a(f"b{tag}aerr {tag}_aerr 0 V = abs(v({tag}_err))")
        a("")
    L += _loop("tie", "0")
    a("* tie: input pinned exactly on the free-MSB threshold for the whole")
    a("* run. No code check -- either adjacent code is a correct answer to")
    a("* an exact tie. The measured claim is the cadence.")
    a("vtiein tie_vinp 0 dc {vcm}")
    a("vtiecm tie_vinn 0 dc {vcm}")
    a("* Gated by drdy, like b<tag>err above: c9..c0 hold their POWER-UP")
    a("* reset value (all zero, i.e. code 0) until the first ph14 load, and")
    a("* an earlier draft of this deck measured tie_dev unconditionally --")
    a("* which made every run report a spurious code-0 deviation of 512 for")
    a("* the ~875 ns before the first conversion's drdy, independent of")
    a("* whether the design was actually correct. Gating on drdy restricts")
    a("* the measurement to windows where the register holds a completed")
    a("* conversion's result, the same fix b<tag>err already applied above.")
    a("btiedev tie_dev 0 V = v(tie_drdy)>vth ? abs(v(tie_code)-512) : 0")
    return L


def functional(nconv: int = 1024) -> str:
    return "\n".join(_functional_body(nconv) + ["", library()])


def timing() -> str:
    return "\n".join(_timing_body() + ["", library()])


# ---------------------------------------------------------------------------
# issue #12 -- timing budget closure at the worst PVT corner
#
# Same closed-loop composition as _timing_body() (controller + behavioural
# CDAC + comparator), but with spec/prior-art-survey.md Sec 1.4's placeholder
# DAC-settling network and round-number delay brackets replaced by the real,
# closed-dependency numbers spec/timing-budget-memo.md derives from, at BOTH
# the 1 MS/s target and the 2 MS/s stretch rate:
#
#   DAC-settling network (R_WORST_BIT_OHM / C_WORST_BIT_F): the worst bit
#   trial's real charge-divider load, Ceq(w=256) = 128*C_u = 2.20672 pF
#   (spec/cdac-sizing-memo.md Sec 5.3, DR-0011's actual array; UNCHANGED by
#   issue #116's toolchain-pin bump -- C_u = 17.24 fF was always the
#   ratified device, the extractor's prior area-only model just could not
#   see it, layout/adc-top/README.md's "Capacitance" section), driven
#   through the real worst-case T-gate R_on = 647.818 ohm at
#   ss_125c_2.97v. UPDATED at issue #116 from the schematic-level 570 ohm:
#   `layout/toolchain.json`'s `klt` pin (af5791b -> 875eac3) now writes
#   genuinely in-path parasitic resistance (star-topology split,
#   klayout-tools#593), and re-measuring the DRAWN, extracted `adc_tgate`
#   leaf cell (sim/device-switch-ron/, gen_extracted_switch_ron_tb.py)
#   against the SAME schematic deck finds +13.57% worst-case R_on from real
#   layout-dependent series resistance -- not the survey's 1k/2.56p guess
#   _loop()'s defaults still carry for functional()/timing().
#
#   Comparator decision delay (T_COMP_REGEN_NS): STILL the schematic-level
#   FIXED 863 ps, the measured worst-case (ss_125c_2.97v, half-LSB
#   overdrive) regeneration delay from #9 (sim/comparator-regeneration/
#   records/20260801-050155-109944e.md) -- not swept, because it is already
#   a closed, measured number. Issue #116 did NOT re-measure this against
#   the extracted, comparator-inclusive `ADC_BLOCK_NORES` core (that core
#   exists and decodes correctly as of #116's own Scope item 1, but porting
#   this deck's precise 0.5 LSB / 100 mV / 0.1 mV forced-overdrive method
#   onto it is a separate, not-yet-built increment) -- so this input, and
#   therefore this whole composition, is NOT a fully post-layout rate
#   closure. It is a partial one: 2 of 3 inputs (R_WORST_BIT_OHM here,
#   C_WORST_BIT_F always) are post-layout: T_COMP_REGEN_NS is not.
#
#   Logic-propagation delay (LOGIC_DELAY_CANDIDATES_NS): SWEPT, because it
#   is the one term this budget cannot yet source from a closed
#   transistor-level record (DR-0010: rung 3 for the SAR controller is
#   blocked on the DR-0004-vs-PDK standard-cell gap -- see
#   spec/timing-budget-memo.md Sec 4). Each bracket point adds a candidate
#   logic delay on top of the fixed 863 ps comparator delay, so the combined
#   added transport delay is 0.863 ns + <candidate>.
#
# This is a COMPOSITION testbench, not a new PVT-swept transistor-level
# measurement: the "worst PVT corner" is represented by plugging in the
# worst-case VALUES that #8/#9/#10's own full-grid PVT sweeps already found,
# not by instantiating gf180mcu device models and sweeping this deck's own
# corners. Same disclosure sim/sar-logic-timing/ and
# sim/sar-logic-functional/ already make: rung-1 ideal-digital primitives
# carry no PDK device models, so process/temperature cannot move any number
# here -- only the supply axis does, because vdd_val sets vref, vcm, lsbse
# and the bridge thresholds ratiometrically.
# ---------------------------------------------------------------------------

T_COMP_REGEN_NS = 0.863
R_WORST_BIT_OHM = "647.818"
C_WORST_BIT_F = "2.20672p"
RATES_NS = (("r1", 62.5), ("r2", 31.25))  # 1 MS/s target, 2 MS/s stretch
LOGIC_DELAY_CANDIDATES_NS = (0.0, 10.0, 25.0, 55.0)


def _budget_closure_body() -> list[str]:
    """Closed-loop budget check at both rates, real component values."""
    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_timing_budget_closure -- issue #12's conversion timing budget,")
    a("* composed from #8/#9/#10's real worst-case numbers instead of")
    a("* spec/prior-art-survey.md Sec 1.4's placeholder DAC model, at both")
    a("* the 1 MS/s target (r1, 62.5 ns bit cycle) and the 2 MS/s stretch")
    a("* (r2, 31.25 ns bit cycle).")
    a("*")
    a("* GENERATED by design/sar-logic/gen_sar_logic.py -- do not edit.")
    a("*")
    a("* Per rate, four single-ended loops, identical except for the")
    a("* candidate logic-propagation delay added on top of the FIXED,")
    a("* measured 863 ps comparator regeneration delay (#9):")
    a("*   l0    +0 ns    just the two closed, measured/derived terms")
    a("*   l10   +10 ns   a generous logic-delay allowance -- still well")
    a("*                  inside both rates' margin per")
    a("*                  spec/timing-budget-memo.md")
    a("*   l25   +25 ns   inside the 1 MS/s margin (~52 ns) but OVER the")
    a("*                  2 MS/s stretch margin (~21 ns) -- the illustrative")
    a("*                  case the memo reports: the stretch's margin can")
    a("*                  go negative before the target's does")
    a("*   l55   +55 ns   over BOTH rates' margin -- the negative control")
    a("*")
    a("* Same PVT-subset justification as sim/sar-logic-timing/: rung-1")
    a("* ideal-digital + behavioural analog carries no PDK device models, so")
    a("* process/temperature cannot move anything here. The worst-PVT-corner")
    a("* claim is carried by the injected component VALUES (R_WORST_BIT_OHM,")
    a("* C_WORST_BIT_F, T_COMP_REGEN_NS above), each sourced from a closed,")
    a("* full-grid PVT sweep (#8/#9/#10), not by sweeping this deck's own")
    a("* corners.")
    a("* ==================================================================")
    a("")
    a(".param vref={vdd_val}")
    a(".param vcm={vdd_val/2}")
    a(".param vth={vdd_val/2}")
    a(".param lsbse={vdd_val/1024}")
    a(".model sarl_sw sw(vt={vdd_val/2} vh=0 ron=1 roff=1e12)")
    a("")
    for rtag, period_ns in RATES_NS:
        a(
            f"vclk_{rtag} clk_{rtag} 0 pulse(0 {{vdd_val}} 0 100p 100p "
            f"{period_ns / 2}n {period_ns}n)"
        )
    a("")
    for rtag, period_ns in RATES_NS:
        conv_ns = 16 * period_ns
        for logic_ns in LOGIC_DELAY_CANDIDATES_NS:
            tag = f"{rtag}_l{int(logic_ns)}"
            cmp_delay = f"{T_COMP_REGEN_NS + logic_ns:g}n"
            L += _loop(
                tag,
                "0",
                cmp_delay=cmp_delay,
                r_ohm=R_WORST_BIT_OHM,
                c_val=C_WORST_BIT_F,
                clk_net=f"clk_{rtag}",
            )
            a(
                f"* {tag}: {period_ns:g} ns/cycle ({conv_ns:g} ns/conversion); "
                f"added delay = 863 ps (measured, #9) + {logic_ns:g} ns "
                "(candidate logic delay)"
            )
            a("* input ramps one LSB per conversion THROUGH mid-scale")
            a("* (codes 507..515), the worst case for a late decision.")
            a(
                f"v{tag}in {tag}_vinp 0 pwl(0 {{vcm-4.75*lsbse}} 8u"
                f" {{vcm+3.25*lsbse}})"
            )
            a(f"v{tag}cm {tag}_vinn 0 dc {{vcm}}")
            a(
                f"b{tag}exp {tag}_exp 0 V = "
                f"min(max(floor(v({tag}_shxp)/lsbse),0),1023)"
            )
            a(
                f"b{tag}err {tag}_err 0 V = "
                f"v({tag}_drdy)>vth ? v({tag}_code)-v({tag}_exp) : 0"
            )
            a(f"b{tag}aerr {tag}_aerr 0 V = abs(v({tag}_err))")
            a("")
    return L


def budget_closure() -> str:
    return "\n".join(_budget_closure_body() + ["", library()])


TARGETS = {
    "library": ("design/sar-logic/sar_ctrl.spice", library),
    "functional": (
        "sim/sar-logic-functional/testbench/tb_sar_logic_functional.spice",
        functional,
    ),
    "timing": (
        "sim/sar-logic-timing/testbench/tb_sar_logic_timing.spice",
        timing,
    ),
    "budget-closure": (
        "sim/timing-budget-closure/testbench/tb_timing_budget_closure.spice",
        budget_closure,
    ),
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true",
                   help="exit 1 if any committed file differs from generated")
    p.add_argument("--stdout", choices=sorted(TARGETS),
                   help="print one artifact instead of writing files")
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
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {rel}")
    if args.check:
        for rel in stale:
            print(f"STALE: {rel}", file=sys.stderr)
        if stale:
            print("run: python3 design/sar-logic/gen_sar_logic.py",
                  file=sys.stderr)
            return 1
        print("all generated netlists are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
