"""The drawn schematic and the simulated netlist must be the same circuit.

`design/comparator/comparator.spice` is what every testbench simulates (the
corner runner consumes self-contained fragments, so the devices are copied
verbatim into each one -- `test_comparator_netlist.py` guards those copies).
`design/comparator/comparator.sch` is the drawn view a human reads and a future
layout is built from.

Neither is generated from the other, so without a check they would drift, and
the drift would be invisible: the schematic would keep looking right while the
evidence under `sim/` described a different circuit. This test flattens the
.spice hierarchy, normalizes both sides, and asserts the two device inventories
are identical as *circuits* -- same multiset of (model, W, L, terminal nets).

Instance names are deliberately NOT compared: xschem prefixes and hierarchical
paths differ by construction, and requiring them to match would make the test
about naming rather than about the circuit. Everything that determines what the
circuit DOES is compared.

Runs in `sim/selftest.sh` stage 1: no PDK, no ngspice, no xschem needed.
"""

import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
SPICE = REPO / "design" / "comparator" / "comparator.spice"
SCH = REPO / "design" / "comparator" / "comparator.sch"

# The .spice inserts two 0 V probe sources between the block's input pins and
# the preamp gates so a testbench can measure the current drawn from each CDAC
# top plate. They carry no circuit function; the schematic connects the pins
# straight through. Normalizing them away is the one deliberate difference.
NET_ALIASES = {"preamp_in1": "vinp", "preamp_in2": "vinn", "vss": "0"}

# Hierarchy-internal nets have no name in common between the two views. The
# .spice reuses one subcircuit definition twice, so its internal PMOS stack
# node is `ps` inside BOTH nor2 instances and only becomes distinguishable
# once the hierarchy is flattened; the flat schematic has to name the two
# nodes apart. The rule applied below is: a flattened internal net keeps its
# short name when that short name occurs in exactly one instance, and
# otherwise needs an explicit entry here. An unlisted collision is a genuine
# mismatch and fails the test rather than being papered over.
HIER_ALIASES = {"xno1.ps": "ps1", "xno2.ps": "ps2"}

FET_MODELS = {"nfet_03v3", "pfet_03v3"}
# ppolyf_u_1k (1000 ohm/sq), not the ppolyf_u_2k an earlier revision assumed
# -- issue #118, see design/comparator/comparator.spice's Xrlp/Xrln comment.
RES_MODELS = {"ppolyf_u_1k"}


def norm_size(value):
    """'0.35u' / '.35u' / '2U' -> a canonical float-in-metres string."""
    v = value.strip().lower()
    mult = 1.0
    if v.endswith("u"):
        mult, v = 1e-6, v[:-1]
    elif v.endswith("n"):
        mult, v = 1e-9, v[:-1]
    return f"{float(v) * mult:.6g}"


def norm_net(net):
    net = net.strip().lower()
    return NET_ALIASES.get(net, net)


def parse_spice(text):
    """Flatten design/comparator/comparator.spice into device tuples.

    Nets are carried through the hierarchy RAW (no aliasing) so that a
    subcircuit port and the net a caller connects to it resolve to the same
    string; aliasing happens once, at the leaf.
    """
    subckts, current = {}, None
    for raw in text.splitlines():
        line = "" if raw.lstrip().startswith("*") else raw.split("*")[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith(".subckt"):
            parts = line.split()
            current = parts[1].lower()
            subckts[current] = {"ports": [x.lower() for x in parts[2:]], "items": []}
        elif low.startswith(".ends"):
            current = None
        elif current and line[0].lower() in "xv":
            subckts[current]["items"].append(line)

    devices = []

    def split_item(item):
        parts = item.split()
        head, rest = parts[0].lower(), parts[1:]
        idx = max(i for i, tok in enumerate(rest) if "=" not in tok)
        model = rest[idx].lower()
        nets = [tok.lower() for tok in rest[:idx]]
        params = dict(tok.split("=", 1) for tok in rest[idx + 1:] if "=" in tok)
        return head, model, nets, params

    def flatten(name, mapping, prefix):
        for item in subckts[name]["items"]:
            head, model, nets, params = split_item(item)
            if head[0] == "v":
                continue  # 0 V probe source, normalized away (see NET_ALIASES)
            nets = [mapping.get(n, n) for n in nets]
            if model in subckts:
                child = subckts[model]
                sub_map = dict(zip(child["ports"], nets))
                for sub_item in child["items"]:
                    _, _, sub_nets, _ = split_item(sub_item)
                    for n in sub_nets:
                        if n not in sub_map:
                            sub_map[n] = f"{prefix}{head}.{n}"
                flatten(model, sub_map, f"{prefix}{head}.")
            elif model in FET_MODELS:
                devices.append((model, params["w"], params["l"], nets))
            elif model in RES_MODELS:
                devices.append((model, params["r_width"], params["r_length"], nets))
            else:
                raise AssertionError(f"unknown device model in {SPICE}: {model}")

    flatten("comparator", {p: p for p in subckts["comparator"]["ports"]}, "")

    # Resolve flattened internal names back to short names where unambiguous.
    qualified = {n for _, _, _, nets in devices for n in nets if "." in n}
    short_counts = {}
    for q in qualified:
        short_counts.setdefault(q.rsplit(".", 1)[1], set()).add(q)
    resolve = {}
    for q in qualified:
        short = q.rsplit(".", 1)[1]
        if q in HIER_ALIASES:
            resolve[q] = HIER_ALIASES[q]
        elif len(short_counts[short]) == 1:
            resolve[q] = short
        else:
            raise AssertionError(
                f"internal net {q!r} collides with {sorted(short_counts[short])}; "
                "add an explicit entry to HIER_ALIASES"
            )

    out = []
    for model, w, l, nets in devices:
        nets = [norm_net(resolve.get(n, n)) for n in nets]
        if model in FET_MODELS:
            out.append((model, norm_size(w), norm_size(l), tuple(nets)))
        else:
            out.append((model, norm_size(w), norm_size(l),
                        (tuple(sorted(nets[:2])), nets[2])))
    return out


# xschem pin geometry: a lab_pin placed at these offsets from the instance
# origin connects to that terminal. Taken from the PDK's own symbols.
PIN_OFFSETS = {
    "nfet_03v3": {(20, -30): "d", (-20, 0): "g", (20, 30): "s", (20, 0): "b"},
    "pfet_03v3": {(20, 30): "d", (-20, 0): "g", (20, -30): "s", (20, 0): "b"},
    "ppolyf_u_1k": {(0, -30): "p", (0, 30): "m", (-20, 0): "b"},
}
SYM_RE = re.compile(r"^C \{(?:symbols/)?([\w./]+?)\.sym\}\s+(-?\d+)\s+(-?\d+)\s+\d+\s+\d+\s+\{(.*)\}\s*$")


def parse_sch(text):
    """Device tuples from the drawn schematic (connectivity via lab_pins)."""
    placements, labels = [], {}
    for line in text.splitlines():
        m = SYM_RE.match(line.strip())
        if not m:
            continue
        sym, x, y, attrs = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        fields = dict(
            kv.split("=", 1) for kv in attrs.split() if "=" in kv
        )
        if sym == "lab_pin":
            labels[(x, y)] = norm_net(fields["lab"])
        elif sym in PIN_OFFSETS:
            placements.append((sym, x, y, fields))

    devices = []
    for sym, x, y, fields in placements:
        nets = {}
        for (dx, dy), pin in PIN_OFFSETS[sym].items():
            key = (x + dx, y + dy)
            assert key in labels, f"{SCH}: {fields.get('name')} pin {pin} has no label at {key}"
            nets[pin] = labels[key]
        w, l = norm_size(fields["W"]), norm_size(fields["L"])
        if sym in FET_MODELS:
            devices.append((sym, w, l, (nets["d"], nets["g"], nets["s"], nets["b"])))
        else:
            devices.append(
                (sym, w, l, (tuple(sorted((nets["p"], nets["m"]))), nets["b"]))
            )
    return devices


class SchematicMatchesNetlist(unittest.TestCase):
    def test_both_views_exist(self):
        self.assertTrue(SPICE.is_file(), f"missing {SPICE}")
        self.assertTrue(SCH.is_file(), f"missing {SCH}")

    def test_same_device_inventory(self):
        spice = sorted(parse_spice(SPICE.read_text()))
        sch = sorted(parse_sch(SCH.read_text()))
        self.assertTrue(spice, "parsed no devices from the .spice netlist")
        self.assertEqual(
            len(spice),
            len(sch),
            f"device count differs: {len(spice)} in comparator.spice, "
            f"{len(sch)} in comparator.sch",
        )
        only_spice = [d for d in spice if d not in sch]
        only_sch = [d for d in sch if d not in spice]
        self.assertEqual(
            (only_spice, only_sch),
            ([], []),
            "the drawn schematic and the simulated netlist are different "
            "circuits.\nonly in comparator.spice: "
            f"{only_spice}\nonly in comparator.sch: {only_sch}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
