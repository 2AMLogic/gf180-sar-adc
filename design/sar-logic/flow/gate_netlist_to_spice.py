#!/usr/bin/env python3
"""Translate a Yosys-written structural gate-level Verilog netlist into a
flat SPICE `.subckt`, wired against the gf180mcu standard-cell library's own
`.SUBCKT` pin order -- issue #272's gate-level functional/timing replay.

## Why this exists instead of Yosys's own `write_spice`

Yosys ships a `write_spice` backend, and it was tried first. It does not
work for this purpose, for two independent reasons, both confirmed directly
against a real synthesis run before writing this module:

1. **No power pins at all.** `write_spice` emits `X<inst> <signal-pins-only>
   <celltype>` -- e.g. `X0 a y gf180mcu_fd_sc_mcu9t5v0__clkinv_1` for a
   2-input inverter whose real SPICE subckt takes six pins
   (`I ZN VDD VNW VPW VSS`). There is no flag to add them, and a transistor-
   level replay with no supply/well-tie connections at all does not
   simulate anything meaningful.
2. **"Guessing order of ports"** (Yosys's own warning text) when no
   blackbox module declares the cell's real pin order, and the guessed
   order is **not safe to trust** even where it happens to work for a
   2-pin cell: the gf180mcu standard-cell library's own Verilog blackbox
   headers (`libs.ref/<lib>/verilog/<lib>.v`, `` `ifdef USE_POWER_PINS ``
   form) declare power pins in the order `VDD, VSS, VNW, VPW`, but the
   library's own SPICE subckts declare them `VDD VNW VPW VSS` --
   *different* orders for the *same* four names. Handing Yosys the verilog
   blackbox to fix problem 1 would silently connect the wrong physical pin
   whenever `write_spice` trusted that module's port order for the SPICE
   call. Confirmed by direct comparison against both files while writing
   this module, not assumed -- automated regression tests for this module
   are the follow-on gate-level replay issue's scope (issue #272's own PR
   introduces this module without a caller yet; see
   `design/sar-logic/rtl/README.md`'s "Verification performed" section),
   not this one.

This module therefore reads pin order from exactly one source of truth per
cell type: the PDK's own `.spice` library text (the same file the PDK ships
for its own SPICE-level verification), never Yosys's guess and never the
Verilog blackbox header.

## Power/ground convention

Every cell instantiated by this design's synthesis (dffq/nor/aoi21/clkinv/
and2/mux2/nor3/or4/or2/nand3, both libraries -- see
`design/sar-logic/flow/sar_ctrl/records/`) declares its SPICE pins as
`<signal pins...> VDD VNW VPW VSS`, consistently, in both
`gf180mcu_fd_sc_mcu7t5v0` and `gf180mcu_fd_sc_mcu9t5v0`. `VDD`/`VNW`
(n-well tie) go to the supply net; `VSS`/`VPW` (p-well/substrate tie) go to
ground -- the standard "n-well to VDD, p-well to VSS" single-well tie
convention for a library with no isolation/triple-well cells (none are
instantiated here). This module does **not** rely on the library's
`*.PININFO` annotation to make that P/G call, because it is not
consistently present: `gf180mcu_fd_sc_mcu9t5v0__clkinv_1`'s SPICE text
carries a `*.PININFO I:I ZN:O VDD:P VNW:P VPW:P VSS:G` comment,
`gf180mcu_fd_sc_mcu7t5v0__clkinv_1`'s does not (checked directly). Instead
it matches by the four *names* directly -- `_POWER_PINS`/`_GROUND_PINS`
below -- which is exactly as reliable here since every cell in both
libraries this design uses shares the identical four names in the identical
trailing position.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: The four power/ground pin names every standard cell in both libraries
#: this design uses declares, and the net each ties to (see module
#: docstring's "Power/ground convention"). Any OTHER pin absent from an
#: instance's own named connection list is an error, not a guess.
_POWER_PINS = ("VDD", "VNW")
_GROUND_PINS = ("VSS", "VPW")

_SUBCKT_RE = re.compile(
    r"^\.SUBCKT\s+(\S+)\s+(.*?)$", re.MULTILINE
)
_CONTINUATION_RE = re.compile(r"^\+\s*(.*)$")


class NetlistTranslationError(RuntimeError):
    """The Verilog netlist or the SPICE library did not have the expected shape."""


def parse_spice_subckt_pins(spice_text: str) -> dict[str, list[str]]:
    """``{cell_name: [pin, ...]}`` for every ``.SUBCKT`` in a PDK library file,
    in the library's own declared pin order (its own physical pin order,
    verified against `libs.ref/<lib>/spice/<lib>.spice`'s `.SUBCKT` lines
    directly, per this module's docstring). Continuation lines (`+`) are
    joined -- none of this design's cells need one, but a generic library
    file may have some for wider cells.
    """
    pins: dict[str, list[str]] = {}
    lines = spice_text.splitlines()
    i = 0
    while i < len(lines):
        m = _SUBCKT_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name, rest = m.group(1), m.group(2)
        i += 1
        while i < len(lines):
            cont = _CONTINUATION_RE.match(lines[i])
            if not cont:
                break
            rest += " " + cont.group(1)
            i += 1
        pins[name] = rest.split()
    return pins


#: ngspice's own `v(name[idx])` syntax reinterprets a bracketed suffix as
#: VECTOR INDEXING into a results vector, not as a literal node-name
#: character (confirmed directly: `print v(ph[2])` on a netlist with a
#: literal node named `ph[2]` reports "vector ph is not available", i.e. it
#: parses `ph` and `[2]` as separate tokens rather than treating `ph[2]` as
#: one node name). Yosys's `write_verilog` freely emits `<bus>[<bit>]` net
#: names for any multi-bit internal `wire` it does not bit-blast away
#: (confirmed on this design's own `ph`/internal `_009_` buses), so every
#: net name is sanitized through this function before being written into a
#: SPICE line -- `ph[2]` -> `ph_2`, bijective (a bus width < 10 bits never
#: collides with a same-named scalar signal in this design's own net
#: namespace, checked at translation time by `build_spice_subckt`'s
#: uniqueness assertion below).
_BUS_BIT_RE = re.compile(r"\[(\d+)\]")


def _sanitize_net(name: str) -> str:
    return _BUS_BIT_RE.sub(lambda m: f"_{m.group(1)}", name)


_MODULE_RE = re.compile(r"module\s+(\S+)\s*\((.*?)\);", re.DOTALL)
_PORT_DECL_RE = re.compile(r"^\s*(input|output|inout)\s+(?:wire\s+)?(\S+)\s*;\s*$", re.MULTILINE)
# One cell instance: `<celltype> <instname> ( .PORT(net), ... );`
_INSTANCE_RE = re.compile(r"\n  (\S+) (\S+) \((.*?)\);", re.DOTALL)
_CONN_RE = re.compile(r"\.(\w+)\((\S*?)\)")
# `assign <lhs> = <rhs>;` -- `write_verilog -noattr` emits these for every
# NET-TO-NET pass-through `opt_clean`/`clean` did not fold into a cell
# connection (confirmed directly on this design: `assign c9 = c9_r;`,
# `assign drdy = ph[15];`, `assign arm9 = ph[4];`, ... -- see this module's
# docstring's own "one bug found and fixed" note below `_resolve_aliases`).
# Both sides must be a single identifier or a single bus-bit reference
# (`name` or `name[<digits>]`) -- anything richer (concatenation, a
# constant, an expression) is NOT a pass-through and this module refuses to
# guess what it means.
_ASSIGN_RE = re.compile(r"^\s*assign\s+(\S+)\s*=\s*(\S+);\s*$", re.MULTILINE)
_SIMPLE_NET_RE = re.compile(r"^\w+(\[\d+\])?$")


@dataclass
class GateInstance:
    cell_type: str
    inst_name: str
    connections: dict[str, str]  # pin name -> net name (nets already declared)


@dataclass
class GateNetlist:
    top: str
    ports: list[str]  # in module-declaration order
    instances: list[GateInstance]


def _resolve_aliases(text: str, ports: list[str]) -> dict[str, str]:
    """Build a `{alias_name: canonical_name}` map from every `assign lhs =
    rhs;` pass-through statement in the netlist.

    **One bug found and fixed while building this module, recorded here
    because it is the kind of thing an untested translator gets silently
    wrong**: `write_verilog -noattr` does not inline every trivial
    pass-through into the driving cell's own connection -- a bare wire
    rename (a flop's `Q` pin driving an internal net like `c9_r`, exposed at
    the module boundary as `c9` via a separate `assign c9 = c9_r;`, or a bus
    bit `ph[4]` given the convenience name `arm9` the same way) is left as a
    plain Verilog continuous assignment instead. A first version of this
    module's `parse_gate_verilog` silently dropped every `assign` line
    (treating it as inert boilerplate, matching a wrong assumption that
    `clean`/`opt_clean -purge` always inline pass-throughs into a cell port).
    The result was a SPICE netlist where `c9`/`c0`../`drdy`/`arm1`..`arm9`/
    `endconv` were never connected to anything at all -- confirmed directly:
    a standalone sanity deck built from that version reported those exact
    net names as absent from ngspice's own node list (not even present as a
    floating node), while every OTHER exposed net (e.g. `samp_tp_n`,
    `rel_n_256p`, both driven by a real gate, not a bare assign) was present
    and correct. This function is the fix: fold every `assign` into a name
    alias instead of dropping it, so the port/register connection it
    expresses is not silently lost.

    Direction of the fold is chosen so a MODULE PORT is always kept as the
    canonical name (a port cannot be renamed -- the whole point of this
    translation is byte-identical port compatibility with `sar_ctrl_a`) and,
    when neither side is a port, the right-hand side (the side with an
    independent driver in every case seen on this design -- e.g. `ph[4]`
    driving the convenience name `arm9`) is kept.
    """
    port_set = set(ports)
    alias_to_canonical: dict[str, str] = {}
    for lhs, rhs in _ASSIGN_RE.findall(text):
        for side in (lhs, rhs):
            if not _SIMPLE_NET_RE.match(side):
                raise NetlistTranslationError(
                    f"assign {lhs} = {rhs}; is not a simple net-to-net pass-through "
                    "(expected a bare identifier or a single bus-bit reference on both "
                    "sides) -- this translator does not evaluate Verilog expressions"
                )
        if lhs in port_set and rhs in port_set:
            raise NetlistTranslationError(f"assign {lhs} = {rhs}; aliases two module ports together")
        canonical, alias = (lhs, rhs) if lhs in port_set else (rhs, lhs)
        if alias in alias_to_canonical and alias_to_canonical[alias] != canonical:
            raise NetlistTranslationError(
                f"{alias!r} is aliased to both {alias_to_canonical[alias]!r} and {canonical!r}"
            )
        alias_to_canonical[alias] = canonical
    # Resolve transitively (not needed by this design's own netlist -- no
    # alias chain is longer than one hop -- but a future synthesis run
    # producing e.g. `assign b = a; assign c = b;` should not silently
    # mis-wire net `c`).
    for _ in range(len(alias_to_canonical) + 1):
        changed = False
        for alias, canonical in list(alias_to_canonical.items()):
            if canonical in alias_to_canonical:
                alias_to_canonical[alias] = alias_to_canonical[canonical]
                changed = True
        if not changed:
            break
    return alias_to_canonical


def parse_gate_verilog(text: str, expected_top: str | None = None) -> GateNetlist:
    """Parse a `write_verilog -noattr` structural netlist: one module, named
    port connections on every cell instance, plus zero or more `assign
    lhs = rhs;` net-to-net pass-throughs (see `_resolve_aliases`) -- the
    exact shape `klt synthesize` produces (verified directly against a real
    run of this design).
    """
    mod = _MODULE_RE.search(text)
    if not mod:
        raise NetlistTranslationError("no `module ... (...);` header found")
    top, port_list_text = mod.group(1), mod.group(2)
    if expected_top is not None and top != expected_top:
        raise NetlistTranslationError(f"expected top module {expected_top!r}, found {top!r}")
    ports = [p.strip() for p in port_list_text.replace("\n", " ").split(",") if p.strip()]

    aliases = _resolve_aliases(text, ports)

    instances: list[GateInstance] = []
    for m in _INSTANCE_RE.finditer(text):
        cell_type, inst_name, body = m.group(1), m.group(2), m.group(3)
        if cell_type in ("input", "output", "inout", "wire", "assign"):
            continue
        conns = {pin: aliases.get(net, net) for pin, net in _CONN_RE.findall(body)}
        instances.append(GateInstance(cell_type=cell_type, inst_name=inst_name, connections=conns))
    if not instances:
        raise NetlistTranslationError("no cell instances found -- did `write_verilog -noattr` shape change?")
    return GateNetlist(top=top, ports=ports, instances=instances)


def build_spice_subckt(
    netlist: GateNetlist,
    cell_pins: dict[str, list[str]],
    *,
    subckt_name: str,
    supply_net: str,
    ground_net: str = "0",
) -> str:
    """Emit a flat `.subckt <subckt_name> <ports...> ... .ends` SPICE block.

    Every cell instance is emitted with its pins in the PDK SPICE library's
    OWN declared order (`cell_pins`), never Yosys's port-connection order
    and never a guess -- signal pins come from the netlist's own named
    connections, and the four power/ground pins (present on every cell this
    design uses, see module docstring) are supplied here since the
    synthesized netlist itself carries no power connections at all.
    """
    all_raw_nets = set(netlist.ports)
    for inst in netlist.instances:
        all_raw_nets.update(inst.connections.values())
    _assert_no_collisions(
        sorted(all_raw_nets), [_sanitize_net(n) for n in sorted(all_raw_nets)], context="every net in the design"
    )

    sanitized_ports = [_sanitize_net(p) for p in netlist.ports]

    lines: list[str] = [
        f".subckt {subckt_name} " + " ".join(sanitized_ports),
    ]
    for inst in netlist.instances:
        try:
            pins = cell_pins[inst.cell_type]
        except KeyError:
            raise NetlistTranslationError(
                f"no SPICE .SUBCKT found for cell type {inst.cell_type!r} "
                f"(instance {inst.inst_name}) -- check the PDK spice library text passed in"
            ) from None
        nets: list[str] = []
        for pin in pins:
            if pin in inst.connections:
                nets.append(_sanitize_net(inst.connections[pin]))
            elif pin in _POWER_PINS:
                nets.append(supply_net)
            elif pin in _GROUND_PINS:
                nets.append(ground_net)
            else:
                raise NetlistTranslationError(
                    f"{inst.inst_name} ({inst.cell_type}): pin {pin!r} has no named "
                    "connection in the netlist and is not a recognised power/ground pin "
                    f"({_POWER_PINS + _GROUND_PINS}) -- a real, unconnected signal pin"
                )
        lines.append(f"X{_sanitize_net(inst.inst_name)} " + " ".join(nets) + f" {inst.cell_type}")
    lines.append(".ends")
    return "\n".join(lines) + "\n"


def _assert_no_collisions(original: list[str], sanitized: list[str], *, context: str) -> None:
    """`_sanitize_net` is bijective in practice for this design (see its own
    docstring), but "in practice" is not good enough for a wiring claim --
    this checks it for the actual names in play rather than asserting it in
    prose only."""
    seen: dict[str, str] = {}
    for orig, san in zip(original, sanitized):
        if san in seen and seen[san] != orig:
            raise NetlistTranslationError(
                f"{context}: sanitizing {orig!r} and {seen[san]!r} both produced {san!r} -- "
                "net-name collision, translation is not safe to trust"
            )
        seen[san] = orig


def extract_used_subckts(spice_text: str, cell_types: set[str]) -> str:
    """Return the verbatim `.SUBCKT ... .ENDS` text for exactly the cell
    types in `cell_types`, in the order they appear in `spice_text` -- this
    is a controlled, provenance-stated COPY of PDK library text into a
    generated testbench fragment (never an `.include`, which
    `sim/harness/testbench.py` forbids in a netlist fragment -- see
    `gen_sar_ctrl_gates_tb.py`'s own docstring for why inlining is legal
    where `.include` is not).
    """
    blocks: list[str] = []
    remaining = set(cell_types)
    lines = spice_text.splitlines()
    i = 0
    while i < len(lines) and remaining:
        m = _SUBCKT_RE.match(lines[i])
        if not m or m.group(1) not in remaining:
            i += 1
            continue
        name = m.group(1)
        start = i
        i += 1
        while i < len(lines) and not lines[i].strip().upper().startswith(".ENDS"):
            i += 1
        if i >= len(lines):
            raise NetlistTranslationError(f".SUBCKT {name} has no matching .ENDS")
        block = "\n".join(lines[start : i + 1])
        blocks.append(block)
        remaining.discard(name)
        i += 1
    if remaining:
        raise NetlistTranslationError(f"cell type(s) not found in PDK spice library: {sorted(remaining)}")
    return "\n\n".join(blocks) + "\n"


def translate(
    gate_verilog_path: Path,
    pdk_spice_library_path: Path,
    *,
    subckt_name: str,
    supply_net: str,
    ground_net: str = "0",
    expected_top: str | None = None,
) -> tuple[str, str]:
    """High-level entry point: `(spice_subckt_text, used_cell_subckts_text)`.

    Callers inline BOTH return values into a self-contained testbench
    fragment -- the standard-cell subckt bodies (copied, per
    `extract_used_subckts`'s docstring) plus this design's own flat subckt
    built against them.
    """
    gate_text = gate_verilog_path.read_text()
    netlist = parse_gate_verilog(gate_text, expected_top=expected_top)
    lib_text = pdk_spice_library_path.read_text()
    cell_types = {inst.cell_type for inst in netlist.instances}
    cell_pins = parse_spice_subckt_pins(lib_text)
    subckt_text = build_spice_subckt(
        netlist, cell_pins, subckt_name=subckt_name, supply_net=supply_net, ground_net=ground_net
    )
    used_subckts_text = extract_used_subckts(lib_text, cell_types)
    return subckt_text, used_subckts_text
