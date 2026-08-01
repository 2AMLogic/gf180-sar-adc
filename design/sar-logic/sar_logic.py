#!/usr/bin/env python3
"""Structural gate-level description of the SAR control logic, and its emitters.

This module holds the design **once**, as a list of primitive gate instances,
and derives everything else from it:

* :func:`emit_design_spice` writes the transistor-level netlist
  (``design/sar-logic/sar_logic.spice``) -- the netlist layout and LVS (#15)
  take as their reference. There is no synthesis step and no standard-cell
  library between this description and the transistor netlist, so nothing can
  drift between what is verified and what is laid out.
* :class:`GateSim` evaluates the *same* instance list as logic, which is what
  makes an exhaustive sweep over all decision sequences affordable
  (``sim/tests/test_sar_logic.py``).

Why custom 3.3 V cells rather than the PDK's standard-cell library: gf180mcu
ships exactly two digital libraries, ``gf180mcu_fd_sc_mcu7t5v0`` and
``gf180mcu_fd_sc_mcu9t5v0``, and both are built from ``nfet_06v0`` /
``pfet_06v0`` devices (verified by reading their ``.spice`` views in the
installed PDK). DR-0004 ratifies ``nfet_03v3`` / ``pfet_03v3`` **throughout**,
SAR logic and digital interface included, and explicitly rejects the 5 V/6 V
flavors for digital. Honouring that record means a small hand-built 3.3 V cell
set, which is what ``CELL_LIBRARY`` below is. See DR-0007 for the decision and
the cost this carries.

Regenerate the derived artifacts with::

    python3 design/sar-logic/generate.py

``sim/tests/test_sar_logic.py`` fails if a committed artifact has drifted from
what this module emits, so the generated files cannot silently go stale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sar_reference import (
    ACQUIRE_CYCLES,
    CLOCK_MULTIPLIER,
    N_BITS,
    SIDES,
    WEIGHTS,
)

# --------------------------------------------------------------------------
# Device sizing
# --------------------------------------------------------------------------
#
# One "1x" inverter is pfet W=2u / nfet W=1u at the 0.28u minimum length the
# rest of this repo's testbenches use (sim/device-switch-ron/,
# sim/cdac-bit-settling/). Everything else is a multiple of that, so the whole
# cell set has one sizing knob.

L_NM = "0.28u"
NFET_1X_UM = 1.0
PFET_1X_UM = 2.0

DRIVES = (1, 4, 8, 48)
"""Inverter drive strengths instantiated. 1x logic, 4x control-output buffers,
8x reset and sampling-switch drivers, 48x the two clock-tree final stages."""


def _inv_subckt(drive: int) -> str:
    suffix = "" if drive == 1 else str(drive)
    return "\n".join(
        [
            f".subckt sl_inv{suffix} a z vdd vss",
            f"Xmp z a vdd vdd pfet_03v3 w={PFET_1X_UM * drive:g}u l={L_NM}",
            f"Xmn z a vss vss nfet_03v3 w={NFET_1X_UM * drive:g}u l={L_NM}",
            ".ends",
        ]
    )


CELL_LIBRARY = "\n\n".join(
    [
        "* ---- primitive cells (custom 3.3 V, DR-0004; see module docstring) ----",
        *[_inv_subckt(d) for d in DRIVES],
        "\n".join(
            [
                "* Transmission gate. gn is the NMOS gate (active high), gp the PMOS",
                "* gate (active low). Series devices are 1x; a T-gate passes both rails.",
                ".subckt sl_tg a z gn gp vdd vss",
                f"Xmn a gn z vss nfet_03v3 w={NFET_1X_UM:g}u l={L_NM}",
                f"Xmp a gp z vdd pfet_03v3 w={PFET_1X_UM:g}u l={L_NM}",
                ".ends",
            ]
        ),
        "\n".join(
            [
                "* NAND2. Series NMOS stack is doubled so pull-down strength matches 1x.",
                ".subckt sl_nand2 a b z vdd vss",
                f"Xmp1 z a vdd vdd pfet_03v3 w={PFET_1X_UM:g}u l={L_NM}",
                f"Xmp2 z b vdd vdd pfet_03v3 w={PFET_1X_UM:g}u l={L_NM}",
                f"Xmn1 z a nmid vss nfet_03v3 w={2 * NFET_1X_UM:g}u l={L_NM}",
                f"Xmn2 nmid b vss vss nfet_03v3 w={2 * NFET_1X_UM:g}u l={L_NM}",
                ".ends",
            ]
        ),
        "\n".join(
            [
                "* NOR2. Series PMOS stack is doubled so pull-up strength matches 1x.",
                ".subckt sl_nor2 a b z vdd vss",
                f"Xmp1 pmid a vdd vdd pfet_03v3 w={2 * PFET_1X_UM:g}u l={L_NM}",
                f"Xmp2 z b pmid vdd pfet_03v3 w={2 * PFET_1X_UM:g}u l={L_NM}",
                f"Xmn1 z a vss vss nfet_03v3 w={NFET_1X_UM:g}u l={L_NM}",
                f"Xmn2 z b vss vss nfet_03v3 w={NFET_1X_UM:g}u l={L_NM}",
                ".ends",
            ]
        ),
        "\n".join(
            [
                "* 2:1 mux, z = s ? a : b. Buffered output: a bare T-gate pair leaves",
                "* the node undriven for the few tens of ps around an s transition.",
                ".subckt sl_mux2 a b s z vdd vss",
                "Xisb s sb vdd vss sl_inv",
                "Xta a zi s sb vdd vss sl_tg",
                "Xtb b zi sb s vdd vss sl_tg",
                "Xb1 zi zn vdd vss sl_inv",
                "Xb2 zn z vdd vss sl_inv",
                ".ends",
            ]
        ),
        "\n".join(
            [
                "* Positive-edge D flip-flop, transmission-gate master-slave, with an",
                "* ASYNCHRONOUS active-low clear. The clear is inside both latches (the",
                "* forward inverter of each is a NAND2 against rstb), so q is forced low",
                "* regardless of the clock phase -- which is what gives the sequencer a",
                "* defined state at t = 0 instead of whatever the DC operating point",
                "* happens to find.",
                ".subckt sl_dffr d clk clkb rstb q qb vdd vss",
                "Xtm d mi clkb clk vdd vss sl_tg",
                "Xnm mi rstb mb vdd vss sl_nand2",
                "Xim mb mq vdd vss sl_inv",
                "Xtmfb mq mi clk clkb vdd vss sl_tg",
                "Xts mq si clk clkb vdd vss sl_tg",
                "Xns si rstb qb vdd vss sl_nand2",
                "Xis qb q vdd vss sl_inv",
                "Xtsfb q si clkb clk vdd vss sl_tg",
                ".ends",
            ]
        ),
        "\n".join(
            [
                "* Same flip-flop with an ASYNCHRONOUS active-high preset (NOR2 in place",
                "* of NAND2). Exactly one instance exists: sequencer stage 0. The",
                "* one-hot ring needs precisely one stage that resets to 1, or reset",
                "* would leave the ring empty and no conversion would ever start.",
                ".subckt sl_dffs d clk clkb rst q qb vdd vss",
                "Xtm d mi clkb clk vdd vss sl_tg",
                "Xnm mi rst mb vdd vss sl_nor2",
                "Xim mb mq vdd vss sl_inv",
                "Xtmfb mq mi clk clkb vdd vss sl_tg",
                "Xts mq si clk clkb vdd vss sl_tg",
                "Xns si rst qb vdd vss sl_nor2",
                "Xis qb q vdd vss sl_inv",
                "Xtsfb q si clkb clk vdd vss sl_tg",
                ".ends",
            ]
        ),
    ]
)


# --------------------------------------------------------------------------
# Structural netlist
# --------------------------------------------------------------------------

COMBINATIONAL = {"inv", "nand2", "nor2", "mux2"}
SEQUENTIAL = {"dffr", "dffs"}


@dataclass(frozen=True)
class Element:
    kind: str
    inst: str
    ins: tuple[str, ...]
    outs: tuple[str, ...]
    drive: int = 1

    def spice(self) -> str:
        if self.kind == "inv":
            suffix = "" if self.drive == 1 else str(self.drive)
            return f"X{self.inst} {self.ins[0]} {self.outs[0]} vdd vss sl_inv{suffix}"
        if self.kind in ("nand2", "nor2"):
            return f"X{self.inst} {self.ins[0]} {self.ins[1]} {self.outs[0]} vdd vss sl_{self.kind}"
        if self.kind == "mux2":
            a, b, s = self.ins
            return f"X{self.inst} {a} {b} {s} {self.outs[0]} vdd vss sl_mux2"
        if self.kind == "dffr":
            return (
                f"X{self.inst} {self.ins[0]} clki clkb rstbi "
                f"{self.outs[0]} {self.outs[1]} vdd vss sl_dffr"
            )
        if self.kind == "dffs":
            return (
                f"X{self.inst} {self.ins[0]} clki clkb rsti "
                f"{self.outs[0]} {self.outs[1]} vdd vss sl_dffs"
            )
        raise ValueError(f"unknown element kind {self.kind!r}")


@dataclass
class Netlist:
    elements: list[Element] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    # -- construction ------------------------------------------------------
    def add(self, kind: str, inst: str, ins: tuple[str, ...], outs: tuple[str, ...], drive: int = 1) -> None:
        self.elements.append(Element(kind, inst, ins, outs, drive))

    def inv(self, inst: str, a: str, z: str, drive: int = 1) -> str:
        self.add("inv", inst, (a,), (z,), drive)
        return z

    def nand2(self, inst: str, a: str, b: str, z: str) -> str:
        self.add("nand2", inst, (a, b), (z,))
        return z

    def nor2(self, inst: str, a: str, b: str, z: str) -> str:
        self.add("nor2", inst, (a, b), (z,))
        return z

    def mux2(self, inst: str, a: str, b: str, s: str, z: str) -> str:
        """z = s ? a : b"""
        self.add("mux2", inst, (a, b, s), (z,))
        return z

    def dffr(self, inst: str, d: str, q: str, qb: str) -> str:
        self.add("dffr", inst, (d,), (q, qb))
        return q

    def dffs(self, inst: str, d: str, q: str, qb: str) -> str:
        self.add("dffs", inst, (d,), (q, qb))
        return q

    def or2(self, inst: str, a: str, b: str, z: str) -> str:
        self.nor2(f"{inst}_n", a, b, f"{z}_b")
        return self.inv(f"{inst}_i", f"{z}_b", z)

    def and2(self, inst: str, a: str, b: str, z: str) -> str:
        self.nand2(f"{inst}_n", a, b, f"{z}_b")
        return self.inv(f"{inst}_i", f"{z}_b", z)

    # -- queries -----------------------------------------------------------
    @property
    def flops(self) -> list[Element]:
        return [e for e in self.elements if e.kind in SEQUENTIAL]

    def nets(self) -> list[str]:
        seen: dict[str, None] = {}
        for e in self.elements:
            for net in (*e.ins, *e.outs):
                seen[net] = None
        return list(seen)


def control_net(kind: str, phase: str, weight: int, side: str) -> str:
    """Control-pin name, matching design/cdac/cdac_array.sch's convention.

    ``kind`` is ``rel`` / ``sel_hi`` / ``sel_lo``; ``phase`` is ``n`` for the
    T-gate's NMOS gate (active high) and ``p`` for its PMOS gate (active low);
    ``side`` is the CDAC half. So ``sel_lo_n_256p`` is the NMOS gate of the
    weight-256 p-side "engage to GND" T-gate.
    """
    return f"{kind}_{phase}_{weight}{side}"


def build() -> Netlist:
    """The SAR controller, as gates.

    Structure (see ``sar_reference`` for the phase map this realizes):

    * a 16-stage one-hot ring sequencer, stage 0 preset on reset;
    * ten decision flip-flops, each holding its trial's comparator result;
    * nine "engaged" flip-flops, each latching high at its own trial and
      staying high for the rest of the conversion;
    * a ten-bit parallel output register loaded at the end of trial 10;
    * per-weight, per-side switch decode producing complementary T-gate drives.
    """
    n = Netlist()
    n.inputs = ["clk", "rstb", "mode", "cmp"]

    # ---- clock tree: three inversions to clkb, one more to clki, so every
    # flip-flop sees a matched complementary pair from the same buffer.
    n.inv("ck0", "clk", "ck_a", drive=1)
    n.inv("ck1", "ck_a", "ck_b", drive=8)
    n.inv("ck2", "ck_b", "clkb", drive=48)
    n.inv("ck3", "clkb", "clki", drive=48)

    # ---- reset tree: rstbi is buffered rstb (for the clear flops), rsti its
    # complement (for the single preset flop).
    n.inv("rs0", "rstb", "rs_a", drive=1)
    n.inv("rs1", "rs_a", "rstbi", drive=8)
    n.inv("rs2", "rstbi", "rsti", drive=8)

    # ---- 16-stage one-hot sequencer ------------------------------------
    n.dffs("ring0", d=f"s{CLOCK_MULTIPLIER - 1}", q="s0", qb="s0b")
    for j in range(1, CLOCK_MULTIPLIER):
        n.dffr(f"ring{j}", d=f"s{j - 1}", q=f"s{j}", qb=f"s{j}b")

    trial_net = {j: f"s{ACQUIRE_CYCLES + j - 1}" for j in range(1, N_BITS + 1)}
    last_trial = trial_net[N_BITS]

    # ---- sampling-switch drive: asserted for the acquire stages ---------
    n.or2("smpa", "s0", "s1", "smp_01")
    n.or2("smpb", "s2", "s3", "smp_23")
    n.or2("smpc", "s4", "s5", "smp_45")
    n.or2("smpd", "smp_01", "smp_23", "smp_0123")
    n.nor2("smpe", "smp_0123", "smp_45", "smp_off")
    n.inv("smpf", "smp_off", "samp_n", drive=8)
    n.inv("smpg", "samp_n", "samp_p", drive=8)

    # ---- decision flip-flops -------------------------------------------
    for j in range(1, N_BITS + 1):
        n.mux2(f"bmux{j}", a="cmp", b=f"b{j}", s=trial_net[j], z=f"bd{j}")
        n.dffr(f"bff{j}", d=f"bd{j}", q=f"b{j}", qb=f"b{j}b")

    # ---- "engaged" flip-flops, one per switched weight -----------------
    # eng_i latches high at the edge that ends trial i and stays high for the
    # rest of the conversion, then clears at the edge that ends the last trial
    # so that the next acquire phase starts with every bottom plate released to
    # V_cm -- which top-plate sampling requires
    # (DR-0006-cdac-switching-scheme). Forgetting that
    # `AND s15b` would leave the array frozen in the previous conversion's
    # state while the next input was being sampled onto it.
    last_trial_b = f"s{ACQUIRE_CYCLES + N_BITS - 1}b"
    for i in range(1, len(WEIGHTS) + 1):
        n.or2(f"engor{i}", f"eng{i}", trial_net[i], f"engo{i}")
        n.and2(f"engcl{i}", f"engo{i}", last_trial_b, f"engd{i}")
        n.dffr(f"engff{i}", d=f"engd{i}", q=f"eng{i}", qb=f"eng{i}b")

    # ---- parallel output register (DR-0005) -----------------------------
    # Loaded from the decision flip-flops' D inputs, not their outputs: at the
    # edge that ends trial 10 the last decision is still only at bff10's input,
    # so taking b10 there would bank a stale bit. Sourcing bd_j costs one mux
    # delay and makes the completed code available for the whole of the
    # following sample period.
    for j in range(1, N_BITS + 1):
        n.mux2(f"dmux{j}", a=f"bd{j}", b=f"d{j}", s=last_trial, z=f"dd{j}")
        n.dffr(f"dff{j}", d=f"dd{j}", q=f"d{j}", qb=f"d{j}b")
    n.inv("eocb", "s0b", "eoc", drive=4)

    # ---- switch decode ---------------------------------------------------
    for i, weight in enumerate(WEIGHTS, start=1):
        eng, bit, bitb = f"eng{i}", f"b{i}", f"b{i}b"

        # p side: engaged from its own trial onward, direction set by the bit.
        rel_n_p = control_net("rel", "n", weight, "p")
        n.inv(f"relp{i}a", eng, rel_n_p, drive=4)
        n.inv(f"relp{i}b", rel_n_p, control_net("rel", "p", weight, "p"), drive=4)
        n.nand2(f"hip{i}", eng, bitb, control_net("sel_hi", "p", weight, "p"))
        n.inv(f"hip{i}b", control_net("sel_hi", "p", weight, "p"),
              control_net("sel_hi", "n", weight, "p"), drive=4)
        n.nand2(f"lop{i}", eng, bit, control_net("sel_lo", "p", weight, "p"))
        n.inv(f"lop{i}b", control_net("sel_lo", "p", weight, "p"),
              control_net("sel_lo", "n", weight, "p"), drive=4)

        # n side: identical, but gated by `mode`. In single-ended mode every
        # n-side cell stays released to V_cm for the whole conversion
        # (DR-0006-cdac-switching-scheme); driving it would double every step
        # and cost a bit.
        n.nand2(f"enn{i}", eng, "mode", f"enn{i}b")
        n.inv(f"enn{i}i", f"enn{i}b", f"enn{i}")
        rel_n_n = control_net("rel", "n", weight, "n")
        n.inv(f"reln{i}a", f"enn{i}", rel_n_n, drive=4)
        n.inv(f"reln{i}b", rel_n_n, control_net("rel", "p", weight, "n"), drive=4)
        n.nand2(f"hin{i}", f"enn{i}", bit, control_net("sel_hi", "p", weight, "n"))
        n.inv(f"hin{i}b", control_net("sel_hi", "p", weight, "n"),
              control_net("sel_hi", "n", weight, "n"), drive=4)
        n.nand2(f"lon{i}", f"enn{i}", bitb, control_net("sel_lo", "p", weight, "n"))
        n.inv(f"lon{i}b", control_net("sel_lo", "p", weight, "n"),
              control_net("sel_lo", "n", weight, "n"), drive=4)

    n.outputs = ports_out()
    return n


def ports_out() -> list[str]:
    """Output port order, fixed once so the design and every testbench agree."""
    ports = ["samp_n", "samp_p"]
    for side in SIDES:
        for weight in WEIGHTS:
            for kind in ("rel", "sel_hi", "sel_lo"):
                ports.append(control_net(kind, "n", weight, side))
                ports.append(control_net(kind, "p", weight, side))
    ports += [f"d{j}" for j in range(1, N_BITS + 1)]
    ports.append("eoc")
    return ports


SUBCKT_PORTS = ["clk", "rstb", "mode", "cmp", *ports_out(), "vdd", "vss"]


# --------------------------------------------------------------------------
# Gate-level simulator
# --------------------------------------------------------------------------


class GateSim:
    """Two-valued evaluator for the *same* element list the SPICE is emitted from.

    Deliberately not a timing simulator: it answers "does this structure
    implement the reference model's control sequence for every decision
    sequence", which is the question a 1024-conversion transient at transistor
    level could never answer inside a PVT campaign. The transistor-level
    testbench (``sim/sar-logic/``) answers the complementary question -- does
    the real gf180mcu netlist do it, at every corner, fast enough.
    """

    def __init__(self, netlist: Netlist) -> None:
        self.netlist = netlist
        self.order = self._topological_order()
        self.state: dict[str, int] = {e.inst: 0 for e in netlist.flops}
        self.values: dict[str, int] = {net: 0 for net in netlist.nets()}
        for name in netlist.inputs:
            self.values[name] = 0

    def _topological_order(self) -> list[Element]:
        driver: dict[str, Element] = {}
        for e in self.netlist.elements:
            if e.kind in COMBINATIONAL:
                for out in e.outs:
                    if out in driver:
                        raise ValueError(f"net {out!r} driven by two elements")
                    driver[out] = e
        order: list[Element] = []
        visiting: set[str] = set()
        done: set[str] = set()

        def visit(inst_net: str) -> None:
            e = driver.get(inst_net)
            if e is None or e.inst in done:
                return
            if e.inst in visiting:
                raise ValueError(f"combinational loop through {inst_net!r}")
            visiting.add(e.inst)
            for src in e.ins:
                visit(src)
            visiting.discard(e.inst)
            done.add(e.inst)
            order.append(e)

        for net in list(driver):
            visit(net)
        return order

    # -- evaluation --------------------------------------------------------
    def _eval_comb(self) -> None:
        v = self.values
        for e in self.order:
            if e.kind == "inv":
                v[e.outs[0]] = 1 - v[e.ins[0]]
            elif e.kind == "nand2":
                v[e.outs[0]] = 1 - (v[e.ins[0]] & v[e.ins[1]])
            elif e.kind == "nor2":
                v[e.outs[0]] = 1 - (v[e.ins[0]] | v[e.ins[1]])
            elif e.kind == "mux2":
                a, b, s = e.ins
                v[e.outs[0]] = v[a] if v[s] else v[b]

    def _apply_flop_outputs(self) -> None:
        for e in self.netlist.flops:
            q = self.state[e.inst]
            self.values[e.outs[0]] = q
            self.values[e.outs[1]] = 1 - q

    def _apply_async(self) -> None:
        """Async clear / preset, honoured continuously while asserted."""
        if self.values.get("rstbi", 1) == 0:
            for e in self.netlist.flops:
                self.state[e.inst] = 1 if e.kind == "dffs" else 0

    def settle(self, **inputs: int) -> None:
        for name, value in inputs.items():
            if name not in self.netlist.inputs:
                raise KeyError(f"{name!r} is not a primary input")
            self.values[name] = int(bool(value))
        self._apply_flop_outputs()
        self._eval_comb()
        if self.values["rstbi"] == 0:
            # Async clear/preset is level sensitive, so it needs a second pass:
            # the first computed rstbi, this one propagates the forced state.
            self._apply_async()
            self._apply_flop_outputs()
            self._eval_comb()

    def clock(self, **inputs: int) -> None:
        """One rising clock edge, with the given primary-input levels held over it."""
        self.settle(**inputs)
        captured = {e.inst: self.values[e.ins[0]] for e in self.netlist.flops}
        self.state.update(captured)
        self.settle()

    # -- convenience -------------------------------------------------------
    def bus(self, kind: str, phase: str, side: str) -> int:
        """Weighted read-back of one control bus -- the same encoding the testbench uses."""
        total = 0
        for weight in WEIGHTS:
            total += weight * self.values[control_net(kind, phase, weight, side)]
        return total

    def cell_states(self) -> dict[tuple[str, int], str]:
        out: dict[tuple[str, int], str] = {}
        for side in SIDES:
            for weight in WEIGHTS:
                rel = self.values[control_net("rel", "n", weight, side)]
                hi = self.values[control_net("sel_hi", "n", weight, side)]
                lo = self.values[control_net("sel_lo", "n", weight, side)]
                if rel + hi + lo != 1:
                    raise AssertionError(
                        f"weight {weight}{side}: exactly one of rel/hi/lo must be "
                        f"asserted, got rel={rel} hi={hi} lo={lo}"
                    )
                out[(side, weight)] = "rel" if rel else ("hi" if hi else "lo")
        return out

    def code(self) -> int:
        value = 0
        for j in range(1, N_BITS + 1):
            value = (value << 1) | self.values[f"d{j}"]
        return value

    def complements_ok(self) -> bool:
        """Every T-gate drive pair must be a true complement, or the gate half-opens."""
        for side in SIDES:
            for weight in WEIGHTS:
                for kind in ("rel", "sel_hi", "sel_lo"):
                    a = self.values[control_net(kind, "n", weight, side)]
                    b = self.values[control_net(kind, "p", weight, side)]
                    if a + b != 1:
                        return False
        return self.values["samp_n"] + self.values["samp_p"] == 1


# --------------------------------------------------------------------------
# Emitters
# --------------------------------------------------------------------------

_GENERATED = (
    "* GENERATED by design/sar-logic/generate.py from sar_logic.py -- do not edit.\n"
    "* Regenerate after any change; sim/tests/test_sar_logic.py fails on drift.\n"
)


def _wrapped_instance(head: str, nets: list[str], tail: str) -> list[str]:
    """SPICE line with `+` continuations -- a 127-pin instance needs them."""
    lines: list[str] = []
    current = head
    for token in [*nets, tail]:
        if len(current) + len(token) + 1 > 78:
            lines.append(current)
            current = "+ " + token
        else:
            current = f"{current} {token}"
    lines.append(current)
    return lines


def _max_expr(names: list[str]) -> str:
    """max() over scalars using only arithmetic and abs().

    nutmeg's ``maximum()`` reduces a vector; there is no portable two-argument
    ``max`` in the interactive expression parser, and a measurement that
    silently parsed as something else would be worse than a verbose one.
    """
    expr = names[0]
    for name in names[1:]:
        expr = f"(({expr})+({name})+abs(({expr})-({name})))/2"
    return expr


def emit_design_spice(netlist: Netlist | None = None) -> str:
    n = netlist or build()
    lines = [
        _GENERATED.rstrip("\n"),
        "*",
        "* SAR control logic -- bit-cycle sequencing, CDAC switch drivers and the",
        "* 10-bit parallel output register, at transistor level in gf180mcu 3.3 V",
        "* devices. This netlist IS the layout/LVS reference for #15: no synthesis,",
        "* no standard-cell library, nothing between it and the schematic-level",
        "* verification in sim/sar-logic/.",
        "*",
        "* Records this implements: DR-0003 (external clock, M = 16), DR-0004",
        "* (3.3 V devices throughout), DR-0005 (parallel output register only; SPI",
        "* deferred), DR-0006-cdac-switching-scheme (MCS / Vcm switching,",
        "* mode-dependent sequence), DR-0007 (synchronous logic, custom 3.3 V cells),",
        "* DR-0009 (no redundancy, so the output word is the decisions themselves).",
        "*",
        "* Ports: clk rstb mode cmp | switch drives | d1..d10 eoc | vdd vss",
        "*   mode = 1 -> differential (both sides switch each trial)",
        "*   mode = 0 -> single-ended (only the p side switches;",
        "*                             DR-0006-cdac-switching-scheme)",
        "",
        CELL_LIBRARY,
        "",
        "* ---- controller ------------------------------------------------------",
    ]
    port_lines = [".subckt sar_logic"]
    current = port_lines[0]
    for port in SUBCKT_PORTS:
        if len(current) + len(port) + 1 > 78:
            port_lines[-1] = current
            current = "+ " + port
            port_lines.append(current)
        else:
            current = current + " " + port
    port_lines[-1] = current
    lines += port_lines
    for e in n.elements:
        lines.append(e.spice())
    lines.append(".ends sar_logic")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Testbench generation
# --------------------------------------------------------------------------

T_CLK_NS = 62.5
"""16 MHz -- M = 16 at the 1 MS/s target (DR-0003)."""

T_EDGE_NS = 0.2
"""Clock rise/fall time; matches the 200 ps driving edge sim/cdac-bit-settling/ uses."""

T_RESET_RELEASE_NS = 150.0
T_FIRST_EDGE_NS = 200.0

PATTERN_A = (1, 0, 1, 0, 1, 0, 1, 0, 1, 0)
PATTERN_B = (0, 1, 0, 1, 0, 1, 0, 1, 0, 1)

CONVERSIONS = (
    (PATTERN_A, False),
    (PATTERN_B, True),
)
"""Two back-to-back conversions: pattern A single-ended, then pattern B differential.

A and B are bitwise complements, so between the two every one of the nine
switched weights drives its p-side cell in BOTH directions (weight 256 goes
`lo` in conversion 0 and `hi` in conversion 1, and so on down the array), and
each input mode is exercised once. The n side is driven only in differential
mode -- that asymmetry IS the mode difference DR-0006-cdac-switching-scheme
turns on, and conversion 0 is what asserts it stays released.

Two conversions, not four: at ~62.5 ns per cycle a conversion is 1 us of
transient across ~1600 transistors, and this testbench runs 45 of those. Adding
the two mirror-image conversions (A differential, B single-ended) would double
the most expensive record in the repo to re-cover, per weight, a direction the
pair above already covers. Exhaustive coverage of all 2 x 1024 decision
sequences in both modes is not attempted here at all -- it is done at gate level
in sim/tests/test_sar_logic.py, where it costs milliseconds instead of days.
That split is DR-0008's fidelity ladder applied to this testbench.
"""

CMP_SETTLE_NS = 20.0
"""How late in its cycle the comparator result appears. Models a decision that
arrives well after the DAC step rather than immediately, so the capture path is
verified against a late-arriving input rather than a convenient one."""

PROBE_OFFSET_NS = 50.0
"""Where inside a cycle the control buses are sampled: late enough that all
logic has settled at the slowest corner, early enough to be before the next edge."""


def edge_ns(index: int) -> float:
    """Time of rising clock edge ``index`` (0-based)."""
    return T_FIRST_EDGE_NS + index * T_CLK_NS


def cycle_start_ns(g: int) -> float:
    """Start of global cycle ``g``. Cycle 0 begins when reset is released."""
    return T_RESET_RELEASE_NS if g == 0 else edge_ns(g - 1)


def trial_cycle(conversion: int, trial: int) -> int:
    return CLOCK_MULTIPLIER * conversion + ACQUIRE_CYCLES + trial - 1


def readout_cycle(conversion: int) -> int:
    """A cycle in which conversion ``conversion``'s code is stable in the register."""
    return CLOCK_MULTIPLIER * (conversion + 1) + 2


N_CYCLES = readout_cycle(len(CONVERSIONS) - 1) + 2
TSTOP_NS = cycle_start_ns(N_CYCLES) + T_CLK_NS

_BUSES = (
    ("relp", "rel", "p"),
    ("hip", "sel_hi", "p"),
    ("lop", "sel_lo", "p"),
    ("reln", "rel", "n"),
    ("hin", "sel_hi", "n"),
    ("lon", "sel_lo", "n"),
)
"""Encoded control buses. Each is the weighted sum of one control's nine
NMOS-gate drives on one side, so a whole switch vector reads as one number."""

PROBE_TRIALS = (5, 10)
"""Trials at which the control vector is probed: one partially engaged, one
fully engaged."""


def _level(bit: int) -> str:
    return "{vdd_val}" if bit else "0"


def _wrapped_pwl(instance: str, node: str, points: list[str]) -> list[str]:
    """A PWL source split over `+` continuations. The comparator pattern is 40
    breakpoints long; on one line it is unreviewable."""
    lines = [f"{instance} {node} 0 pwl("]
    current = "+"
    for point in points:
        if len(current) + len(point) + 1 > 76:
            lines.append(current)
            current = "+ " + point
        else:
            current = f"{current} {point}"
    lines.append(current)
    lines.append("+ )")
    return lines


def _clock_source() -> str:
    """Ideal external clock (DR-0003: supplied off-chip, no on-chip oscillator)."""
    high = T_CLK_NS / 2 - T_EDGE_NS
    return (
        f"vclk clk 0 pulse(0 {{vdd_val}} {T_FIRST_EDGE_NS - T_EDGE_NS / 2:.4f}n "
        f"{T_EDGE_NS:g}n {T_EDGE_NS:g}n {high:.4f}n {T_CLK_NS:.4f}n)"
    )


def _cmp_points() -> list[str]:
    points = ["0", "0", f"{T_RESET_RELEASE_NS:.4f}n", "0"]
    level = 0
    for conversion, (pattern, _mode) in enumerate(CONVERSIONS):
        for trial in range(1, N_BITS + 1):
            want = pattern[trial - 1]
            if want == level:
                continue
            t = cycle_start_ns(trial_cycle(conversion, trial)) + CMP_SETTLE_NS
            points += [f"{t - T_EDGE_NS:.4f}n", _level(level), f"{t:.4f}n", _level(want)]
            level = want
    return [f"{points[i]} {points[i + 1]}" for i in range(0, len(points), 2)]


def _mode_points() -> list[str]:
    points = ["0", "0"]
    level = 0
    for conversion, (_pattern, mode) in enumerate(CONVERSIONS):
        want = 1 if mode else 0
        if want == level:
            continue
        # The mode input is static configuration. It is changed in the middle of
        # an acquire cycle, where no cell is engaged and no edge is near.
        t = cycle_start_ns(CLOCK_MULTIPLIER * conversion + 1) + T_CLK_NS / 2
        points += [f"{t - T_EDGE_NS:.4f}n", _level(level), f"{t:.4f}n", _level(want)]
        level = want
    return [f"{points[i]} {points[i + 1]}" for i in range(0, len(points), 2)]


def _bus_source(name: str, kind: str, phase: str, side: str) -> str:
    terms = " + ".join(
        f"{weight}*(v({control_net(kind, phase, weight, side)}) > {{vdd_val/2}})"
        for weight in WEIGHTS
    )
    return f"B{name} n{name} 0 v = {terms}"


def _rail_source() -> str:
    terms = [f"min(v(d{j}),{{vdd_val}}-v(d{j}))" for j in range(1, N_BITS + 1)]
    expr = terms[-1]
    for term in reversed(terms[:-1]):
        expr = f"max({term},{expr})"
    return f"Brail nrail 0 v = {expr}"


def emit_tb_fragment() -> str:
    design = emit_design_spice()
    lines = [
        _GENERATED.rstrip("\n"),
        "*",
        "* tb_sar_logic -- functional and timing verification of the SAR control",
        "* logic (design/sar-logic/sar_logic.spice, inlined verbatim below because",
        "* the corner runner forbids .include in a fragment).",
        "*",
        "* WHAT THIS ANSWERS.",
        "*   1. Does the transistor-level controller produce the exact CDAC switch",
        "*      vector DR-0006-cdac-switching-scheme requires, at every PVT",
        "*      corner, in BOTH input modes -- including the load-bearing mode",
        "*      difference (single-ended switches one side per trial,",
        "*      differential switches both)?",
        "*   2. Does the 10-bit parallel output register (DR-0005) hold the right",
        "*      word, at full rails, for a whole sample period after the conversion?",
        "*   3. What is the SAR logic propagation delay at the WORST corner --",
        "*      measured, not taken from spec/prior-art-survey.md Sec 4.2's",
        "*      typical-corner ~1 ns estimate?",
        "*",
        "* STIMULUS. An ideal 16 MHz clock (M = 16 at 1 MS/s, DR-0003), an",
        f"* asynchronous reset released at {T_RESET_RELEASE_NS:g} ns, a static mode input, and a",
        "* comparator-decision input driven from a fixed pattern. The comparator",
        f"* result is presented {CMP_SETTLE_NS:g} ns into each trial cycle rather than at its start,",
        "* so the capture path is exercised against a late decision.",
        "*",
        "* Two conversions run back to back: pattern A single-ended, then its bitwise",
        "* complement B differential. Between them every bit position sees both",
        "* decisions, every weight's p-side driver is exercised in both directions,",
        "* and each input mode is exercised once. All 2 x 1024 decision sequences are",
        "* covered separately, at gate level, in sim/tests/test_sar_logic.py -- a",
        "* transient that long is not affordable inside a PVT campaign, which is",
        "* exactly the fidelity-ladder argument DR-0008 makes.",
        "*",
        "* READ-OUT. The nine per-weight drives of each control are summed into one",
        "* node by an ideal B-source, weighted by the weight itself, so a whole",
        "* switch vector reads as a single number (256 for the sub-array MSB down to",
        "* 1 for its LSB). The same trick encodes the output register. These sources",
        "* are measurement instruments, not part of the DUT: they read node voltages",
        "* and drive nothing.",
        "",
        design,
        "",
        "* ---- supplies and stimulus -------------------------------------------",
        "vsup vdd 0 dc {vdd_val}",
        _clock_source(),
        (
            "vrstb rstb 0 pwl(0 0 "
            f"{T_RESET_RELEASE_NS - T_EDGE_NS:.4f}n 0 {T_RESET_RELEASE_NS:.4f}n {{vdd_val}})"
        ),
        *_wrapped_pwl("vcmp", "cmp", _cmp_points()),
        *_wrapped_pwl("vmode", "mode", _mode_points()),
        "",
        "* ---- device under test -----------------------------------------------",
        *_wrapped_instance("Xdut", [p if p != "vss" else "0" for p in SUBCKT_PORTS], "sar_logic"),
        "",
        "* ---- CDAC gate load on every switch drive ------------------------------",
        "* Each control pin drives one bit cell's T-gate. 50 fF is the gate",
        "* capacitance of the NMOS W=10u / PMOS W=20u T-gate pair that",
        "* sim/cdac-bit-settling/ and design/cdac/cdac_array.sch use, at the 3.3 V",
        "* oxide. Loading every pin equally follows that testbench's own stated",
        "* convention of not upsizing the driver for the larger weights, which makes",
        "* the delay reported here conservative.",
    ]
    for port in ports_out():
        if port.startswith(("rel_", "sel_", "samp_")):
            lines.append(f"Cld_{port} {port} 0 50f")
    lines += [
        "",
        "* ---- measurement instruments (ideal, not part of the DUT) -------------",
        "* Normalized copies of the three edges whose delay is measured, so that a",
        "* 50 % threshold is 0.5 at every supply in the sweep rather than a fixed",
        "* voltage that would mean a different fraction at 2.97 V and 3.63 V.",
        "Bclkn nclkn 0 v = v(clk)/{vdd_val}",
        "Bselo nselo 0 v = v(sel_lo_n_256p)/{vdd_val}",
        "Bd1n nd1n 0 v = v(d1)/{vdd_val}",
        "Bsampn nsampn 0 v = v(samp_n)/{vdd_val}",
        "",
    ]
    for name, kind, side in _BUSES:
        lines.append(_bus_source(name, kind, "n", side))
    lines += [
        "",
        "Bcode ncode 0 v = "
        + " + ".join(
            f"{1 << (N_BITS - j)}*(v(d{j}) > {{vdd_val/2}})" for j in range(1, N_BITS + 1)
        ),
        "* Worst distance of any output-register bit from its nearer rail. A bit",
        "* stuck mid-rail would still decode to a plausible code; this is what makes",
        "* that impossible to miss.",
        _rail_source(),
        "",
    ]
    return "\n".join(lines)


def _expected() -> dict:
    """Expected measurement values, from the reference model -- never from the design."""
    import sar_reference

    out: dict[str, float] = {}
    for conversion, (pattern, mode) in enumerate(CONVERSIONS):
        out[f"code_c{conversion}"] = float(sar_reference.code_of(pattern))
        for trial in PROBE_TRIALS:
            cells = {
                (side, weight): sar_reference.cell_state(
                    index, trial, pattern[index - 1], side, mode
                )
                for side in SIDES
                for index, weight in enumerate(WEIGHTS, start=1)
            }
            for name, kind, side in _BUSES:
                want = {"rel": sar_reference.REL, "sel_hi": sar_reference.HI,
                        "sel_lo": sar_reference.LO}[kind]
                out[f"{name}_c{conversion}t{trial}"] = float(
                    sum(w for w in WEIGHTS if cells[(side, w)] == want)
                )
    return out


def emit_tb_manifest() -> dict:
    expected = _expected()

    analyses = [
        # Only the measurement instruments are saved. The controller has well
        # over a thousand internal nodes and the transient is 4 us long; saving
        # everything would cost hundreds of megabytes per corner for data no
        # check reads.
        "save v(nclkn) v(nselo) v(nd1n) v(nsampn) v(ncode) v(nrail) "
        + " ".join(f"v(n{name})" for name, _k, _s in _BUSES),
        f"tran 100p {TSTOP_NS:.4f}n 0 1n",
    ]
    for conversion in range(len(CONVERSIONS)):
        t = cycle_start_ns(readout_cycle(conversion)) + PROBE_OFFSET_NS
        analyses.append(f"meas tran code_c{conversion} FIND v(ncode) AT={t:.4f}n")
        analyses.append(f"meas tran rail_c{conversion} FIND v(nrail) AT={t:.4f}n")
        for trial in PROBE_TRIALS:
            tp = cycle_start_ns(trial_cycle(conversion, trial)) + PROBE_OFFSET_NS
            for name, _kind, _side in _BUSES:
                analyses.append(
                    f"meas tran {name}_c{conversion}t{trial} FIND v(n{name}) AT={tp:.4f}n"
                )

    # Propagation delays. Each TARG edge is the FIRST of its kind in the run, so
    # the measurement cannot latch onto the wrong one:
    #   - sel_lo_n_256p first rises at the edge ending trial 1 of conversion 0
    #     (pattern A's first decision is 1, so weight 256 engages toward GND);
    #   - d1 first rises when the output register loads that conversion's code;
    #   - samp_n first falls when the acquire phase ends.
    first_engage_edge = trial_cycle(0, 1) + 1        # 1-based RISE index below
    load_edge = trial_cycle(0, N_BITS) + 1
    acquire_end_edge = trial_cycle(0, 1)
    analyses += [
        f"meas tran tpd_sel TRIG v(nclkn) VAL=0.5 RISE={first_engage_edge} "
        "TARG v(nselo) VAL=0.5 RISE=1",
        f"meas tran tpd_dout TRIG v(nclkn) VAL=0.5 RISE={load_edge} "
        "TARG v(nd1n) VAL=0.5 RISE=1",
        f"meas tran tpd_samp TRIG v(nclkn) VAL=0.5 RISE={acquire_end_edge} "
        "TARG v(nsampn) VAL=0.5 FALL=1",
    ]

    measure = {}
    for conversion in range(len(CONVERSIONS)):
        measure[f"code_c{conversion}"] = f"code_c{conversion}"
        measure[f"rail_c{conversion}_mv"] = f"rail_c{conversion}*1e3"
        for trial in PROBE_TRIALS:
            for name, _kind, _side in _BUSES:
                key = f"{name}_c{conversion}t{trial}"
                measure[key] = key
    measure["tpd_sel_ns"] = "tpd_sel*1e9"
    measure["tpd_dout_ns"] = "tpd_dout*1e9"
    measure["tpd_samp_ns"] = "tpd_samp*1e9"
    measure["tpd_worst_ns"] = (
        "(" + _max_expr(["tpd_sel", "tpd_dout", "tpd_samp"]) + ")*1e9"
    )

    checks: dict[str, dict] = {}
    for conversion, (pattern, mode) in enumerate(CONVERSIONS):
        want = expected[f"code_c{conversion}"]
        checks[f"code_c{conversion}"] = {
            "min": want - 0.5,
            "max": want + 0.5,
            "description": (
                f"Output register after conversion {conversion} "
                f"({'differential' if mode else 'single-ended'}, decisions "
                f"{''.join(str(b) for b in pattern)}). Expected {int(want)}: the decisions "
                "themselves, MSB first, because DR-0009 adopts no redundancy and so no "
                "digital correction stands between the decisions and the code. Read one "
                "full cycle into the following sample period, which is also the check "
                "that the register HOLDS (DR-0005) rather than merely updating."
            ),
        }
        checks[f"rail_c{conversion}_mv"] = {
            "max": 50.0,
            "description": (
                "Worst distance of any output-register bit from its nearer rail at the "
                "same instant. The code check above decodes through a threshold and would "
                "accept a bit sitting at mid-rail; this will not."
            ),
        }
        for trial in PROBE_TRIALS:
            for name, kind, side in _BUSES:
                key = f"{name}_c{conversion}t{trial}"
                want_bus = expected[key]
                checks[key] = {
                    "min": want_bus - 0.5,
                    "max": want_bus + 0.5,
                    "description": (
                        f"CDAC switch vector: weighted sum of the nine {kind} drives on the "
                        f"{side} side during trial {trial} of conversion {conversion} "
                        f"({'differential' if mode else 'single-ended'}). Expected "
                        f"{int(want_bus)} from the scheme in "
                        "spec/decision-records/DR-0006-cdac-switching-scheme.md, "
                        "computed by design/sar-logic/sar_reference.py -- the reference "
                        "model, not the design. For the n side in single-ended mode the "
                        "expected rel vector is all nine weights (511) and hi/lo are both 0: "
                        "that is the mode difference DR-0006-cdac-switching-scheme "
                        "says costs a bit of resolution "
                        "if it is got wrong, asserted here rather than assumed."
                    ),
                }

    checks["tpd_worst_ns"] = {
        "max": 10.0,
        "min_spread_pct_by_axis": {"process": 20.0},
        "description": (
            "THE BUDGET CHECK and the corner-sensitivity anchor in one. Worst of the "
            "three measured clock-to-output delays. The bound is derived, not "
            "invented: at the 2 MS/s stretch a bit cycle is 31.25 ns, of which "
            "sim/cdac-bit-settling/ and spec/prior-art-survey.md Sec 4.2 spend 19.5 ns on "
            "DAC settling and ~1 ns on the comparator, leaving ~10 ns for the logic. "
            "At the 1 MS/s target the same number sits against a 62.5 ns cycle, so a "
            "pass here closes the target with large margin and the stretch without "
            "special pleading. The process-axis FLOOR is what makes this testbench "
            "falsifiable under --sabotage-corners: gate delay is the most "
            "process-sensitive quantity in the whole design, so a run with every model "
            "section forced to typical collapses this spread to zero. The functional "
            "checks above would all still pass under sabotage -- static CMOS logic is "
            "correct at any corner -- which is exactly why a functional-only testbench "
            "would be worthless as evidence."
        ),
    }
    checks["tpd_sel_ns"] = {
        "max": 10.0,
        "description": (
            "Clock edge to CDAC switch drive: the path the bit cycle actually waits on "
            "(flip-flop clock-to-Q, switch decode, output buffer, 50 fF T-gate load). "
            "This is the number spec/prior-art-survey.md Sec 4.2 estimated at ~1 ns from "
            "generic 180 nm standard cells; here it is measured on this design in this "
            "PDK at every corner."
        ),
    }
    checks["tpd_dout_ns"] = {
        "max": 10.0,
        "description": "Clock edge to parallel output register valid (DR-0005).",
    }
    checks["tpd_samp_ns"] = {
        "max": 10.0,
        "description": (
            "Clock edge to sampling-switch release. Bounded on the same budget: the "
            "acquire window shortens by exactly this delay."
        ),
    }

    return {
        "name": "sar-logic",
        "description": (
            "SAR control logic at transistor level: bit-cycle sequencing, CDAC switch "
            "decode and the 10-bit parallel output register, over the full PVT matrix. "
            "Two back-to-back conversions cover both input modes with complementary "
            "decision patterns; the same run measures worst-corner logic propagation "
            "delay against the bit-cycle budget."
        ),
        "claim": (
            "spec/decision-records/DR-0007-sar-logic-style.md (pending #1 for a ratified "
            "spec anchor). Substantiates the synchronous-logic decision's timing premise "
            "and the mode-dependent switching sequence of "
            "DR-0006-cdac-switching-scheme."
        ),
        "netlist": "tb_sar_logic.spice",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["mos"],
        "options": ["klu"],
        "analyses": analyses,
        "measure": measure,
        "checks": checks,
        "evidence": {
            "record_kind": "corner-matrix",
            "notes": [
                "The mos corner set (tt, ff, ss, fs, sf) is the right one here and the "
                "cdac/mim/moscap corners are deliberately absent: this DUT contains no "
                "capacitor from the PDK at all. Its only devices are nfet_03v3 / "
                "pfet_03v3, and its only load is a lumped 50 fF ideal capacitor standing "
                "in for the CDAC bit cell's T-gate gate capacitance. A capacitor-family "
                "corner would move nothing, and a testbench whose corner set cannot move "
                "its result is worse than one that omits it.",
                "Two conversions are simulated, not all 2 x 1024 decision sequences. The "
                "exhaustive sweep runs at gate level in sim/tests/test_sar_logic.py "
                "against the same element list this netlist is generated from, in "
                "milliseconds. That split IS the fidelity-ladder decision in DR-0008, "
                "applied to this testbench: the expensive rung answers the question only "
                "it can answer (does the real netlist do it, at every corner, fast "
                "enough) and the cheap rung answers the one only it can afford (does the "
                "structure do it for every input).",
                "`.options klu` selects ngspice's KLU direct linear solver instead of the "
                "SPARSE 1.3 default. This is the largest DUT in the repo by device count "
                "(~1600 MOSFETs, against tens elsewhere), which is the regime KLU's "
                "sparse ordering is for. It changes which factorization the same equations "
                "go through, not the equations: every check in this manifest is a bound on "
                "circuit behaviour, so a solver that changed an answer would show up as a "
                "failed check, not as a silently different number.",
                "The B-sources that encode the control buses, the output code and the "
                "rail margin are measurement instruments: they read node voltages and "
                "drive nothing in the DUT. Removing them cannot change a single node "
                "voltage in the controller.",
                "Delay is measured against normalized (v/vdd) copies of the clock and the "
                "observed signals so that the 50 % threshold is 50 % at 2.97 V and at "
                "3.63 V alike. A fixed-voltage threshold would have made the supply axis "
                "of the delay sweep partly an artifact of the measurement.",
            ],
        },
    }


def emit_tb_manifest_json() -> str:
    return json.dumps(emit_tb_manifest(), indent=2) + "\n"
