"""Static SPEF / DEF / Verilog / Liberty agreement audit and the SPEF-annotated
STA acceptance gate for `sta_sar_ctrl_postroute.py --spef` (issue #481).

Why this exists. `klt sta` with a `spef` field reports slack numbers whether or
not OpenSTA's `read_spef` actually attached the parasitics. A half-applied SPEF
returns plausible slack with no error signal. `klt sta`'s own `spef_annotation`
block is the primary evidence (klayout-tools `docs/cli/sta.md`, "Annotation
evidence"), but it reports counts, not *which* nets failed. This module adds
the two things a reader of the record needs to trust a verdict either way:

1. **A static agreement audit** (`audit_agreement`) of the SPEF against the
   routed DEF it was extracted from, the as-built Verilog, and the Liberty pin
   lists. It runs before any STA and names every disagreement: units and
   delimiters, design nets with no `*D_NET`, `*I inst:pin` sets that differ
   from the DEF's own `NETS` connections, and `*P`/bare RC nodes naming a
   top-level port that does not exist. The last is the mechanism behind
   klayout-tools#2880: OpenSTA resolves a bare node name as a port pin, and
   when that port does not exist it drops every RC element touching it.
2. **A reader-warning classifier** (`classify_reader_warnings`) over the
   retained OpenROAD log. It splits OpenSTA's `STA-1650`/`STA-1656`/`STA-1648`
   "not found" warnings into records about non-design nets (intra-cell `$N`
   nets, sub-cell labels) and records that touch a design net.

`gate()` combines `klt sta`'s verdict with both and returns the list of
rejection reasons. An empty list means accepted. The gate never upgrades
`klt`'s own `annotation_complete: false` to a pass, and there is no fallback to
the unannotated (no-SPEF) timing: a rejected corner is reported as rejected.

Import-only and stdlib-only: no tool runs at import time, so `python3 -m
compileall design` covers it and `sim/tests/test_spef_audit.py` exercises it
with tiny synthetic inputs, without `klt`, OpenROAD or a PDK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Units this flow expects in a `klt extract --spef` header. A SPEF in other
#: units is not wrong in itself, but nothing downstream of this audit rescales,
#: so any other unit is reported as a disagreement rather than silently read.
EXPECTED_UNITS = {"C_UNIT": "1 FF", "R_UNIT": "1 OHM"}


def unescape(name: str) -> str:
    """Strip SPEF/DEF/Verilog per-character backslash escapes (`ph\\[15\\]` ->
    `ph[15]`). Both SPEF (IEEE 1481) and DEF escape the same way."""
    return re.sub(r"\\(.)", r"\1", name)


def _split_node(node: str, delimiter: str = ":") -> tuple[str, str | None]:
    """`_010_:2` -> (`_010_`, `2`); `_219_:D` -> (`_219_`, `D`); `clk` ->
    (`clk`, None). Escaped delimiters (`\\:`) are not split."""
    m = re.match(r"^((?:\\.|[^\\" + re.escape(delimiter) + r"])*)" + re.escape(delimiter) + r"(.*)$", node)
    if not m:
        return unescape(node), None
    return unescape(m.group(1)), unescape(m.group(2))


# --------------------------------------------------------------------- SPEF


@dataclass
class SpefNet:
    name: str
    total_cap: float
    ports: list[str] = field(default_factory=list)  # *P entries
    insts: list[tuple[str, str]] = field(default_factory=list)  # *I inst:pin
    nodes: set[str] = field(default_factory=set)  # every node named in *CAP/*RES (escaped form)


@dataclass
class Spef:
    header: dict[str, str]
    ports: list[str]
    nets: list[SpefNet]

    @property
    def net_names(self) -> list[str]:
        return [n.name for n in self.nets]


def parse_spef(text: str) -> Spef:
    """Parse the subset of IEEE 1481 SPEF that `klt extract --spef` writes
    (and a `*NAME_MAP`, if a different writer used one). Names are returned
    unescaped. Raises ValueError on a structurally unreadable file."""
    header: dict[str, str] = {}
    ports: list[str] = []
    nets: list[SpefNet] = []
    name_map: dict[str, str] = {}

    def resolve(tok: str) -> str:
        if tok.startswith("*") and tok[1:].isdigit():
            if tok not in name_map:
                raise ValueError(f"SPEF uses name-map index {tok} with no *NAME_MAP entry")
            return name_map[tok]
        return tok

    section = None
    cur: SpefNet | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("*D_NET"):
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(f"malformed *D_NET line: {raw!r}")
            cur = SpefNet(name=unescape(resolve(parts[1])), total_cap=float(parts[2]))
            nets.append(cur)
            section = "dnet"
            continue
        if line == "*END":
            cur = None
            section = None
            continue
        if cur is not None:
            if line in ("*CONN", "*CAP", "*RES", "*INDUC"):
                section = line
                continue
            parts = line.split()
            if section == "*CONN" and parts[0] in ("*P", "*I") and len(parts) >= 2:
                ref = resolve(parts[1])
                if parts[0] == "*P":
                    cur.ports.append(unescape(ref))
                else:
                    inst, pin = _split_node(ref, header.get("DELIMITER", ":"))
                    if pin is None:
                        raise ValueError(f"*I entry without inst:pin delimiter: {raw!r}")
                    cur.insts.append((inst, pin))
            elif section in ("*CAP", "*RES", "*INDUC") and len(parts) >= 3:
                # `id node value` (ground C) or `id node node value` (coupling C / R / L)
                for tok in parts[1:-1]:
                    cur.nodes.add(resolve(tok))
            continue
        if line == "*PORTS":
            section = "ports"
            continue
        if line == "*NAME_MAP":
            section = "name_map"
            continue
        if section in ("ports", "name_map") and line.startswith("*") and not re.match(r"^\*\d+\s", line):
            section = None  # a new header keyword ends the list (`*12 B` is a name-mapped entry)
        if section == "ports":
            ports.append(unescape(resolve(line.split()[0])))
            continue
        if section == "name_map":
            idx, name = line.split(None, 1)
            name_map[idx] = name.strip()
            continue
        m = re.match(r"^\*(\w+)\s+(.*)$", line)
        if m:
            header[m.group(1)] = m.group(2).strip().strip('"')
    if not nets:
        raise ValueError("SPEF contains no *D_NET blocks")
    return Spef(header=header, ports=ports, nets=nets)


# ---------------------------------------------------------------------- DEF


@dataclass
class Def:
    divider: str
    busbit: str
    components: dict[str, str]  # inst -> cell
    pins: dict[str, str]  # top pin name -> net name
    pin_dirs: dict[str, str]  # top pin name -> INPUT/OUTPUT/INOUT
    nets: dict[str, list[tuple[str, str]]]  # signal net -> [(inst | "PIN", pin)]
    special_nets: list[str]


def _def_section(text: str, name: str) -> str:
    m = re.search(rf"^{name}\s+\d+\s*;(.*?)^END {name}\b", text, re.DOTALL | re.MULTILINE)
    return m.group(1) if m else ""


def _def_statements(body: str) -> list[str]:
    """Split a DEF section body into `- ... ;` statements (whitespace-joined)."""
    out = []
    for stmt in re.split(r";\s*\n", body):
        s = " ".join(stmt.split())
        if s.startswith("- "):
            out.append(s)
    return out


def parse_def(text: str) -> Def:
    divider = (re.search(r'^DIVIDERCHAR\s+"(.)"', text, re.MULTILINE) or [None, "/"])[1]
    busbit = (re.search(r'^BUSBITCHARS\s+"(..)"', text, re.MULTILINE) or [None, "[]"])[1]
    components: dict[str, str] = {}
    for s in _def_statements(_def_section(text, "COMPONENTS")):
        parts = s.split()
        components[unescape(parts[1])] = parts[2]
    pins: dict[str, str] = {}
    pin_dirs: dict[str, str] = {}
    for s in _def_statements(_def_section(text, "PINS")):
        parts = s.split()
        name = unescape(parts[1])
        m = re.search(r"\+ NET (\S+)", s)
        pins[name] = unescape(m.group(1)) if m else name
        d = re.search(r"\+ DIRECTION (\S+)", s)
        pin_dirs[name] = d.group(1) if d else "INOUT"
    nets: dict[str, list[tuple[str, str]]] = {}
    for s in _def_statements(_def_section(text, "NETS")):
        head = s.split(" + ", 1)[0]
        name = unescape(head.split()[1])
        conns = [(unescape(a), unescape(b)) for a, b in re.findall(r"\(\s*(\S+)\s+(\S+)\s*\)", head)]
        nets[name] = conns
    special = [unescape(s.split()[1]) for s in _def_statements(_def_section(text, "SPECIALNETS"))]
    if not nets:
        raise ValueError("DEF has no NETS section")
    return Def(divider, busbit, components, pins, pin_dirs, nets, special)


# ------------------------------------------------------------------ Verilog


@dataclass
class Verilog:
    module: str
    ports: dict[str, str]  # port -> input/output/inout (bit-blasted)
    wires: set[str]
    instances: dict[str, tuple[str, dict[str, str]]]  # inst -> (cell, {pin: net})
    assigns: list[tuple[str, str]]  # (lhs, rhs)


def _expand(name: str, rng: str | None) -> list[str]:
    if not rng:
        return [name]
    a, b = (int(x) for x in rng.strip("[]").split(":"))
    return [f"{name}[{i}]" for i in range(min(a, b), max(a, b) + 1)]


def parse_verilog(text: str) -> Verilog:
    """Parse the flat structural netlist OpenROAD's `write_verilog` emits:
    one module, scalar/vector `input`/`output`/`wire` declarations, named-port
    cell instances, and `assign a = b;` aliases. Not a general Verilog
    parser -- anything else raises ValueError so a format change is loud."""
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    m = re.search(r"\bmodule\s+(\S+)\s*\(", text)
    if not m:
        raise ValueError("no module declaration")
    module = m.group(1)
    ports: dict[str, str] = {}
    wires: set[str] = set()
    for kind, rng, names in re.findall(r"^\s*(input|output|inout|wire)\s*(\[\d+:\d+\])?\s*([^;]+);", text, re.MULTILINE):
        for n in names.split(","):
            n = unescape(n.strip())
            for bit in _expand(n, rng):
                if kind == "wire":
                    wires.add(bit)
                else:
                    ports[bit] = kind
    instances: dict[str, tuple[str, dict[str, str]]] = {}
    for cell, inst, body in re.findall(r"^\s*(\w+)\s+(\\\S+|\w+)\s*\((.*?)\)\s*;", text, re.MULTILINE | re.DOTALL):
        if cell in ("module", "input", "output", "inout", "wire", "assign"):
            continue
        conns = {p: unescape(n.strip()) for p, n in re.findall(r"\.(\w+)\s*\(([^()]*)\)", body)}
        instances[unescape(inst)] = (cell, {p: n for p, n in conns.items()})
    assigns = [(unescape(a.strip()), unescape(b.strip())) for a, b in re.findall(r"^\s*assign\s+(\S+)\s*=\s*([^;]+);", text, re.MULTILINE)]
    if not instances:
        raise ValueError("no cell instances found")
    return Verilog(module, ports, wires, instances, assigns)


# ------------------------------------------------------------------ Liberty


def parse_liberty_pins(text: str, cells: set[str] | None = None) -> dict[str, dict[str, str]]:
    """Map cell -> {signal pin: direction} from a Liberty file. `pg_pin`
    groups (supplies) are excluded. Restrict to `cells` when given -- a
    full gf180mcu Liberty is ~20 MB, so this scans cell headers by regex
    rather than building a full parse tree."""
    out: dict[str, dict[str, str]] = {}
    cell_iter = list(re.finditer(r'^\s*cell\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{', text, re.MULTILINE))
    for i, cm in enumerate(cell_iter):
        name = cm.group(1)
        if cells is not None and name not in cells:
            continue
        end = cell_iter[i + 1].start() if i + 1 < len(cell_iter) else len(text)
        body = text[cm.end():end]
        pins: dict[str, str] = {}
        pin_iter = list(re.finditer(r'^\s*pin\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{', body, re.MULTILINE))
        for j, pm in enumerate(pin_iter):
            seg = body[pm.end():pin_iter[j + 1].start() if j + 1 < len(pin_iter) else len(body)]
            dm = re.search(r"direction\s*:\s*\"?(\w+)", seg)
            direction = dm.group(1) if dm else "unknown"
            if re.search(r"\bclock\s*:\s*\"?true", seg):
                direction += ":clock"
            pins[pm.group(1)] = direction
        if re.search(r"^\s*(ff|latch)\s*\(", body, re.MULTILINE):
            pins["__sequential__"] = "true"
        out[name] = pins
    return out


def timed_path_witness(verilog: Verilog, liberty: dict[str, dict[str, str]], net: str, limit: int = 12) -> str | None:
    """Follow `net` forward through combinational cells (Liberty output pins)
    to the first data (non-clock) input of a sequential cell. Returns the
    path as text, or None if no register is reached within `limit` stages.
    Used to show a net is on a timed register path, not to time it."""
    loads: dict[str, list[tuple[str, str, str]]] = {}
    for inst, (cell, conns) in verilog.instances.items():
        for pin, n in conns.items():
            if n and liberty.get(cell, {}).get(pin, "").startswith("input"):
                loads.setdefault(n, []).append((inst, pin, cell))
    frontier = [(net, "")]
    seen: set[str] = set()
    for _ in range(limit):
        nxt = []
        for n, path in frontier:
            for inst, pin, cell in sorted(loads.get(n, [])):
                lib = liberty.get(cell, {})
                step = f"{path}{inst}/{pin}"
                if lib.get("__sequential__") and not lib.get(pin, "").endswith(":clock"):
                    return f"{net} -> {step} ({cell})"
                if inst in seen:
                    continue
                seen.add(inst)
                for opin, d in lib.items():
                    if d.startswith("output") and verilog.instances[inst][1].get(opin):
                        nxt.append((verilog.instances[inst][1][opin], f"{step} -> "))
        frontier = nxt
    return None


# -------------------------------------------------------- agreement audit


def audit_agreement(spef: Spef, def_: Def, verilog: Verilog, liberty: dict[str, dict[str, str]]) -> dict:
    """Return a JSON-serialisable audit. `errors` lists every disagreement
    that can cost a timed net its parasitics; `info` lists expected,
    non-timing differences (counted, with a sample), so the reader sees
    both. Nothing here consults OpenSTA."""
    errors: list[dict] = []
    info: list[dict] = []

    # 1. Units and delimiters.
    for key, want in EXPECTED_UNITS.items():
        got = spef.header.get(key)
        if got is None or " ".join(got.split()).upper() != want.upper():
            errors.append({"check": "units", "detail": f"SPEF *{key} is {got!r}, expected {want!r}"})
    if spef.header.get("DIVIDER", "/") != def_.divider:
        errors.append({"check": "delimiters", "detail": f"SPEF *DIVIDER {spef.header.get('DIVIDER')!r} != DEF DIVIDERCHAR {def_.divider!r}"})
    bus = spef.header.get("BUS_DELIMITER", "[ ]").replace(" ", "")
    if bus != def_.busbit:
        errors.append({"check": "delimiters", "detail": f"SPEF *BUS_DELIMITER {spef.header.get('BUS_DELIMITER')!r} != DEF BUSBITCHARS {def_.busbit!r}"})

    # 2. Net-name correlation, both directions.
    counts: dict[str, int] = {}
    for n in spef.net_names:
        counts[n] = counts.get(n, 0) + 1
    by_name = {n.name: n for n in spef.nets}
    design_signal = set(def_.nets)
    design_all = design_signal | set(def_.special_nets)
    missing = sorted(design_signal - set(by_name))
    for n in missing:
        errors.append({"check": "net_missing_in_spef", "net": n, "detail": f"DEF signal net {n!r} has no *D_NET"})
    missing_special = sorted(set(def_.special_nets) - set(by_name))
    if missing_special:
        info.append({"check": "power_net_missing_in_spef", "nets": missing_special, "detail": "supply nets are not timed"})
    dup = sorted(n for n, c in counts.items() if c > 1)
    for n in dup:
        (errors if n in design_signal else info).append({"check": "duplicate_dnet", "net": n, "count": counts[n]})
    extras = sorted(set(by_name) - design_all)
    anon = [n for n in extras if n.startswith("$")]
    labelled = [n for n in extras if not n.startswith("$")]
    if extras:
        info.append({
            "check": "non_design_spef_nets",
            "count": len(extras),
            "anonymous_count": len(anon),
            "labelled": labelled,
            "detail": "SPEF nets with no DEF counterpart (flat extraction's intra-cell nets and sub-cell labels); "
                      "OpenSTA discards these as STA-1650 'net not found'. Not design nets, so not timed.",
        })

    # 3. *I connections vs DEF NETS connections, per design signal net.
    for name in sorted(design_signal & set(by_name)):
        want = {(i, p) for i, p in def_.nets[name] if i != "PIN"}
        got = set(by_name[name].insts)
        if want != got:
            errors.append({
                "check": "conn_mismatch", "net": name,
                "missing_in_spef": sorted(f"{i}:{p}" for i, p in want - got),
                "extra_in_spef": sorted(f"{i}:{p}" for i, p in got - want),
            })

    # 4. Ports: every *P (and every bare RC node) must name a real top-level
    #    port, or OpenSTA drops the RC elements touching it (klayout-tools#2880).
    top_pins = set(def_.pins)
    pin_of_net: dict[str, list[str]] = {}
    for p, n in def_.pins.items():
        pin_of_net.setdefault(n, []).append(p)
    delim = spef.header.get("DELIMITER", ":")
    # A bare node (no `:`) names a port pin in SPEF; it is that net's own hub
    # wherever it appears (including as another net's coupling endpoint).
    bare_nodes: dict[str, int] = {}
    for net in spef.nets:
        for nd in net.nodes:
            if _split_node(nd, delim)[1] is None:
                bare_nodes[unescape(nd)] = bare_nodes.get(unescape(nd), 0) + 1
    for net in spef.nets:
        if net.name not in design_signal:
            continue
        bad_ports = [p for p in net.ports if p not in top_pins]
        bare_refs = bare_nodes.get(net.name, 0) if net.name not in top_pins else 0
        if bad_ports or bare_refs:
            errors.append({
                "check": "port_name_mismatch", "net": net.name,
                "spef_ports": bad_ports, "bare_node_references": bare_refs,
                "def_pins_on_net": sorted(pin_of_net.get(net.name, [])),
                "detail": "SPEF names this net as a top-level port/bare node, but no top-level port has that name; "
                          "OpenSTA resolves it as a port pin, fails (STA-1656) and drops every RC element on it",
            })
    spef_ports = set(spef.ports)
    stray_ports = sorted(spef_ports - top_pins)
    if stray_ports:
        (errors if any(p in design_signal for p in stray_ports) else info).append({
            "check": "spef_ports_not_def_pins", "ports": stray_ports})
    missing_ports = sorted(top_pins - spef_ports - set(def_.special_nets))
    if missing_ports:
        info.append({"check": "def_pins_not_spef_ports", "ports": missing_ports,
                     "detail": "top-level pins the SPEF declares under a different (net) name or not at all"})

    # 5. DEF vs Verilog.
    alias = {}
    for lhs, rhs in verilog.assigns:
        alias[lhs] = rhs
    vnets = set(verilog.wires) | set(verilog.ports)
    for name in sorted(design_signal):
        if name not in vnets:
            errors.append({"check": "def_net_not_in_verilog", "net": name})
    for pin, net in sorted(def_.pins.items()):
        if pin not in verilog.ports and pin not in def_.special_nets:
            errors.append({"check": "def_pin_not_verilog_port", "pin": pin})
        elif pin != net and alias.get(pin) != net and pin not in def_.special_nets:
            errors.append({"check": "def_pin_net_alias_unexplained", "pin": pin, "net": net,
                           "detail": "DEF attaches this pin to a differently-named net with no matching Verilog assign"})
    conn_mismatch = []
    for inst, (cell, conns) in sorted(verilog.instances.items()):
        if def_.components.get(inst) != cell:
            errors.append({"check": "verilog_inst_not_in_def", "inst": inst, "cell": cell,
                           "def_cell": def_.components.get(inst)})
            continue
        for pin, net in conns.items():
            if net and (inst, pin) not in set(def_.nets.get(net, [])) and net not in def_.special_nets:
                conn_mismatch.append(f"{inst}:{pin}->{net}")
    if conn_mismatch:
        errors.append({"check": "verilog_conn_not_in_def", "conns": conn_mismatch})
    def_only = sorted(
        f"{i}:{p}" for n in design_signal for i, p in def_.nets[n]
        if i != "PIN" and verilog.instances.get(i, (None, {}))[1].get(p) not in (n, alias.get(n))
    )
    if def_only:
        errors.append({"check": "def_conn_not_in_verilog", "conns": def_only})

    # 6. Liberty pin names, and floating outputs (driver pins on no net).
    floating = []
    for net in sorted(design_signal):
        for inst, pin in def_.nets[net]:
            if inst == "PIN":
                continue
            cell = def_.components.get(inst)
            if cell not in liberty:
                errors.append({"check": "cell_not_in_liberty", "inst": inst, "cell": cell})
            elif pin not in liberty[cell]:
                errors.append({"check": "pin_not_in_liberty", "inst": inst, "pin": pin, "cell": cell})
    for inst, (cell, conns) in sorted(verilog.instances.items()):
        for pin, direction in liberty.get(cell, {}).items():
            if direction == "output" and not conns.get(pin):
                floating.append(f"{inst}/{pin}")
    if floating:
        info.append({"check": "floating_outputs", "pins": floating,
                     "detail": "cell output pins connected to no net (e.g. CTS dummy loads): no loads, so not on a "
                               "timed path, but OpenSTA counts them as unannotated drivers (klayout-tools#2880)"})

    timed_nets_at_risk = sorted({e["net"] for e in errors if "net" in e})
    return {
        "spef_header": spef.header,
        "counts": {
            "spef_dnets": len(spef.nets),
            "spef_ports": len(spef.ports),
            "def_signal_nets": len(design_signal),
            "def_special_nets": len(def_.special_nets),
            "def_pins": len(def_.pins),
            "def_components": len(def_.components),
            "verilog_instances": len(verilog.instances),
            "design_signal_nets_in_spef": len(design_signal & set(by_name)),
            "spef_star_i_entries": sum(len(n.insts) for n in spef.nets),
        },
        "errors": errors,
        "info": info,
        "nets_with_errors": timed_nets_at_risk,
        "timed_path_witness": {n: timed_path_witness(verilog, liberty, n) for n in timed_nets_at_risk},
        "conn_sets_all_match": not any(e["check"] == "conn_mismatch" for e in errors),
        "ok": not errors,
    }


# --------------------------------------------------- reader warnings / gate


_WARN = re.compile(r"\[WARNING (STA-16(?:48|50|56))\][^,]*,\s*(?:net|pin|instance)\s+(.+?) not found\.")


def classify_reader_warnings(log_text: str, design_nets: set[str], design_insts: set[str]) -> dict:
    """Split OpenSTA's SPEF-reader 'not found' warnings by whether the name
    they reject belongs to the routed design."""
    by_code: dict[str, int] = {}
    touching: dict[str, int] = {}
    other: dict[str, int] = {}
    for code, name in _WARN.findall(log_text):
        by_code[code] = by_code.get(code, 0) + 1
        base = name.split(":", 1)[0] if code != "STA-1650" else name
        if base in design_nets or base in design_insts:
            touching[base] = touching.get(base, 0) + 1
        else:
            key = "$<n> (anonymous intra-cell net)" if base.startswith("$") else base
            other[key] = other.get(key, 0) + 1
    return {
        "total": sum(by_code.values()),
        "by_code": by_code,
        "touching_design": dict(sorted(touching.items())),
        "touching_design_records": sum(touching.values()),
        "non_design": dict(sorted(other.items())),
    }


def gate(response: dict, audit: dict, warnings: dict | None) -> list[str]:
    """Rejection reasons for one SPEF-annotated corner. Empty == accepted."""
    reasons: list[str] = []
    ann = response.get("spef_annotation")
    if not ann:
        return ["response has no spef_annotation block: the SPEF was not read"]
    if response.get("timing_status") != "constrained":
        reasons.append(f"timing_status is {response.get('timing_status')!r}, not 'constrained'")
    if not ann.get("annotation_complete"):
        reasons.append("klt sta annotation_complete is false: " + str(ann.get("annotation_warning")))
    if ann.get("design_nets_annotated") != ann.get("design_nets_total") or not ann.get("design_nets_total"):
        reasons.append(
            f"design nets named by SPEF {ann.get('design_nets_annotated')}/{ann.get('design_nets_total')}; "
            f"missing sample {ann.get('design_nets_missing_sample')}"
        )
    if ann.get("delay_changed") is False:
        reasons.append("delay_changed is false: timing is byte-identical to the unannotated run")
    if (ann.get("unannotated_driver_count") or 0) > 0:
        reasons.append(f"{ann['unannotated_driver_count']} driver(s) with no parasitics after read_spef")
    if warnings is None:
        reasons.append("OpenROAD log not retained: reader warnings could not be classified")
    elif warnings["touching_design_records"]:
        reasons.append(
            f"{warnings['touching_design_records']} discarded SPEF record(s) touch design nets/instances: "
            + ", ".join(sorted(warnings["touching_design"]))
        )
    if not audit.get("ok"):
        reasons.append("static SPEF/DEF/Verilog/Liberty audit has errors on nets: " + ", ".join(audit.get("nets_with_errors") or ["(non-net checks)"]))
    return reasons


# ------------------------------------------------------- negative controls


def derive_negative_control(spef_text: str, net: str, mode: str) -> str:
    """Return a copy of `spef_text` with design net `net` either dropped
    (`mode="drop"`: its whole *D_NET block removed) or misnamed
    (`mode="rename"`: every reference renamed to `<net>_negctl`, so the SPEF
    still carries the RC but under a name the design does not have)."""
    esc = re.escape(net)
    if mode == "drop":
        out, n = re.subn(rf"^\*D_NET {esc} .*?^\*END\n\n?", "", spef_text, flags=re.DOTALL | re.MULTILINE)
    elif mode == "rename":
        out, n = re.subn(rf"(?<![\w\\$]){esc}(?=[\s:]|$)", f"{net}_negctl", spef_text, flags=re.MULTILINE)
    else:
        raise ValueError(f"unknown negative-control mode {mode!r}")
    if n == 0:
        raise ValueError(f"negative control {mode!r}: net {net!r} not found in SPEF")
    return out


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
