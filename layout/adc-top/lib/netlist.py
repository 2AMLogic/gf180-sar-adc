#!/usr/bin/env python3
"""Read `design/adc-top/adc_top.spice` (and `design/comparator/
comparator.spice`) and flatten a chosen instantiation into the device list
this directory's layout generators place -- and, from the SAME list, the
flat SPICE reference `klt lvs` compares the extracted layout against.

WHY THE LAYOUT AND THE LVS REFERENCE SHARE A SOURCE
---------------------------------------------------
Both come from the *design* netlist under `design/`, parsed here -- not
hand-transcribed into the generator and then hand-transcribed again into a
reference. That is deliberate, and it is worth being explicit about what it
does and does not prove:

* It **does** prove that the drawn polygons realise the connectivity and
  the W/L of `design/adc-top/adc_top.spice`. That is what LVS is for, and a
  routing defect (two nets merged, a terminal on the wrong trunk, a stub
  that shorts across a channel) still fails loudly -- one did, during this
  bring-up, before the router in `geometry.py` was rebuilt.
* It does **not** prove the design netlist itself is right. Nothing in
  `layout/` claims that; `sim/` does.

A hand-copied reference would add a transcription check and subtract a
provenance guarantee (a typo in the copy would show up as an LVS failure
indistinguishable from a real layout defect). Deriving both sides from
`design/` keeps the layout honest about *which* netlist it implements.

SUPPORTED SPICE SUBSET
----------------------
Exactly what the two design files use: `.subckt`/`.ends` with positional
ports and `k=v` defaults, `X`-prefixed subcircuit instances with `k=v`
overrides, `*` comments, `+` continuations, and quoted arithmetic
parameter expressions (`w='wn*rd'`). Leaf devices are recognised by model
name (`nfet_03v3`/`pfet_03v3` -> MOSFET, `ppolyf_u_2k` -> resistor,
`mim_cap_2f0` -> capacitor). Anything else raises -- silently ignoring an
unrecognised line in a netlist an LVS reference is generated from would be
the worst possible failure mode.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

#: Leaf model names and the device kind each maps to.
NFET_MODELS = {"nfet_03v3"}
PFET_MODELS = {"pfet_03v3"}
RES_MODELS = {"ppolyf_u_2k"}
CAP_MODELS = {"mim_cap_2f0"}

#: `klt extract`'s gf180mcu `CapacitorDevice` name for the 5LM MiM stack --
#: the official PDK LVS deck's own device name, which is what the extracted
#: netlist writes as each capacitor's model.
MIM_DEVICE_CLASS = "cap_mim_2f0_m4m5_noshield"

#: Capacitance per um^2 of plate overlap the *extraction deck* models for
#: that device (`CapacitorDevice.area_cap_f_um2`, 2.0 fF/um^2 -- the density
#: the `_2f0` flavour is named for).
#:
#: THIS IS NOT THE PDK MODEL CARD'S NUMBER, and the difference is the reason
#: this constant is spelled out here instead of hidden in a literal.
#: `cap_mim_2f0fF` in `sm141064.ngspice` is
#:
#:     C = 1.99 fF/um^2 * W*L  +  0.2383 fF/um * 2*(W+L)
#:
#: (`sim/device-characterization-report.md` Sec 1.2, reproduced there to four
#: significant figures against measurement), i.e. an area term AND a
#: perimeter/fringe term. The extraction deck models the area term only, so
#: for the ratified 2.7136 um unit plate it reports 14.73 fF where the model
#: card gives 17.24 fF -- 14.6 % low, entirely in the missing fringe term,
#: and proportionally worse the smaller the plate. Filed generically upstream
#: (see `../README.md`'s friction table).
#:
#: The LVS reference therefore states the DECK's number, so `klt lvs` checks
#: what it can actually check -- the capacitor's connectivity and its drawn
#: plate area -- instead of failing on a modelling difference that no layout
#: change could fix. The design-vs-extraction capacitance delta is reported
#: in `layout/lvs/records/`, not silently absorbed here.
DECK_MIM_AREA_CAP_F_UM2 = 2.0e-15


def mim_reference_farads(plate_w_nm: int, plate_l_nm: int) -> float:
    """The capacitance `klt extract` will report for a drawn `plate_w_nm` x
    `plate_l_nm` MiM plate, in farads. See :data:`DECK_MIM_AREA_CAP_F_UM2`
    for why the reference uses this and not the PDK model card's value."""
    return DECK_MIM_AREA_CAP_F_UM2 * (plate_w_nm * 1e-3) * (plate_l_nm * 1e-3)

_SUFFIX = {
    "t": 1e12, "g": 1e9, "meg": 1e6, "x": 1e6, "k": 1e3,
    "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15,
}


@dataclass(frozen=True)
class Device:
    """One flattened leaf device, with fully-qualified net names."""

    kind: str  # 'nfet' | 'pfet' | 'res' | 'cap'
    path: str  # hierarchical instance path, e.g. "XP.X256.Xsr.XN"
    nets: tuple[str, ...]  # positional terminals, as written in the netlist
    params: dict[str, float]  # numeric parameters in SI units (metres/farads)

    @property
    def is_mos(self) -> bool:
        return self.kind in ("nfet", "pfet")

    @property
    def w_nm(self) -> int:
        return int(round(self.params["w"] * 1e9))

    @property
    def l_nm(self) -> int:
        return int(round(self.params["l"] * 1e9))

    @property
    def cap_plate_nm(self) -> tuple[int, int]:
        """A capacitor's plate `(width, length)` on the 1 nm database grid --
        the PDK subckt's own `c_width`/`c_length`, rounded exactly as the
        layout generator rounds them before drawing. Both sides of LVS have
        to agree on the DRAWN plate, not on the un-representable design
        value (2.7136 um is not on a 1 nm grid)."""
        return int(round(self.params["w"] * 1e9)), int(round(self.params["l"] * 1e9))


@dataclass
class Subckt:
    name: str
    ports: list[str]
    defaults: dict[str, str]
    lines: list[list[str]]  # tokenised instance lines


def _value(token: str, scope: dict[str, float]) -> float:
    """Evaluate a SPICE parameter value: a bare number with an optional
    engineering suffix, a parameter name, or a quoted arithmetic expression
    over the enclosing subcircuit's parameters."""
    token = token.strip()
    if token.startswith(("'", '"')) and token.endswith(("'", '"')):
        expr = token[1:-1]
        return float(eval(expr, {"__builtins__": {}}, dict(scope)))  # noqa: S307
    if token in scope:
        return float(scope[token])
    m = re.fullmatch(r"([+-]?[0-9.]+(?:[eE][+-]?[0-9]+)?)([a-zA-Z]*)", token)
    if not m:
        raise ValueError(f"cannot evaluate SPICE value {token!r}")
    mantissa, suffix = m.group(1), m.group(2).lower()
    if not suffix:
        return float(mantissa)
    for key in sorted(_SUFFIX, key=len, reverse=True):
        if suffix.startswith(key):
            return float(mantissa) * _SUFFIX[key]
    raise ValueError(f"unknown SPICE suffix in {token!r}")


def _split_params(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split a token list into leading positional tokens and trailing
    `k=v` assignments. SPICE allows the two to interleave in principle; the
    files here never do, so the first `k=v` ends the positional run."""
    positional: list[str] = []
    params: dict[str, str] = {}
    for tok in tokens:
        if "=" in tok:
            key, _, val = tok.partition("=")
            params[key.strip().lower()] = val.strip()
        elif params:
            raise ValueError(f"positional token {tok!r} after a k=v assignment")
        else:
            positional.append(tok)
    return positional, params


def parse(path: str) -> dict[str, Subckt]:
    """Parse every `.subckt` in `path`. Raises on any construct outside the
    documented subset."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.readlines()

    # Join continuations, drop comments/blank lines.
    joined: list[str] = []
    for line in raw:
        line = line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        if stripped.startswith("+"):
            if not joined:
                raise ValueError(f"{path}: continuation with nothing to continue")
            joined[-1] += " " + stripped[1:].strip()
        else:
            joined.append(stripped)

    subckts: dict[str, Subckt] = {}
    current: Subckt | None = None
    for line in joined:
        tokens = line.split()
        head = tokens[0].lower()
        if head == ".subckt":
            if current is not None:
                raise ValueError(f"{path}: nested .subckt {tokens[1]!r}")
            positional, defaults = _split_params(tokens[1:])
            current = Subckt(
                name=positional[0], ports=positional[1:], defaults=defaults, lines=[]
            )
        elif head == ".ends":
            if current is None:
                raise ValueError(f"{path}: .ends outside a .subckt")
            subckts[current.name] = current
            current = None
        elif current is not None:
            current.lines.append(tokens)
        else:
            raise ValueError(f"{path}: top-level line outside any .subckt: {line!r}")
    if current is not None:
        raise ValueError(f"{path}: unterminated .subckt {current.name!r}")
    return subckts


def flatten(
    subckts: dict[str, Subckt],
    name: str,
    port_nets: dict[str, str],
    params: dict[str, float] | None = None,
    prefix: str = "",
    aliases: list[tuple[str, str]] | None = None,
) -> list[Device]:
    """Flatten one instantiation of subcircuit `name`.

    `port_nets` maps each of the subcircuit's own port names to the net name
    the caller wants it to carry; every net not in that map becomes
    `"<prefix><net>"`, so hierarchy is preserved in the flat net names.
    """
    sub = subckts[name]
    scope: dict[str, float] = {
        key: _value(val, {}) for key, val in sub.defaults.items()
    }
    if params:
        scope.update(params)

    def resolve(net: str) -> str:
        if net in port_nets:
            return port_nets[net]
        if net == "0":
            return "0"
        return f"{prefix}{net}"

    devices: list[Device] = []
    for tokens in sub.lines:
        inst = tokens[0]
        if inst.upper().startswith("V"):
            # A zero-volt source is a probe, not a component: SPICE writers
            # use it to make a branch current measurable (`design/comparator/
            # comparator.spice`'s `Vpp`/`Vpn` on the CDAC top plates). It is
            # electrically a short, so it becomes a net alias -- the caller
            # resolves them. A NON-zero source would be a real element with
            # no layout counterpart, so it is an error, not a silent skip.
            positional, raw = _split_params(tokens[1:])
            value = positional[-1] if positional[-1].lower() != "dc" else "0"
            if len(positional) >= 4 and positional[2].lower() == "dc":
                value = positional[3]
            if _value(value, scope) != 0.0:
                raise ValueError(f"{name}: non-zero source {inst!r} has no layout form")
            if aliases is None:
                raise ValueError(
                    f"{name}: {inst!r} is a net alias; pass `aliases=` to flatten()"
                )
            aliases.append((resolve(positional[0]), resolve(positional[1])))
            continue
        if not inst.upper().startswith("X"):
            raise ValueError(f"{name}: unsupported element {inst!r} (only X supported)")
        positional, raw_params = _split_params(tokens[1:])
        model = positional[-1]
        terminals = [resolve(n) for n in positional[:-1]]
        path = f"{prefix}{inst}"

        if model in NFET_MODELS or model in PFET_MODELS:
            kind = "nfet" if model in NFET_MODELS else "pfet"
            devices.append(
                Device(
                    kind=kind,
                    path=path,
                    nets=tuple(terminals),
                    params={
                        "w": _value(raw_params["w"], scope),
                        "l": _value(raw_params["l"], scope),
                    },
                )
            )
        elif model in RES_MODELS:
            devices.append(
                Device(
                    kind="res",
                    path=path,
                    nets=tuple(terminals),
                    params={
                        "w": _value(raw_params["r_width"], scope),
                        "l": _value(raw_params["r_length"], scope),
                    },
                )
            )
        elif model in CAP_MODELS:
            devices.append(
                Device(
                    kind="cap",
                    path=path,
                    nets=tuple(terminals),
                    params={
                        "w": _value(raw_params["c_width"], scope),
                        "l": _value(raw_params["c_length"], scope),
                    },
                )
            )
        elif model in subckts:
            child = subckts[model]
            child_ports = dict(zip(child.ports, terminals, strict=True))
            child_params = {
                key: _value(val, scope) for key, val in raw_params.items()
            }
            devices.extend(
                flatten(
                    subckts,
                    model,
                    child_ports,
                    child_params,
                    prefix=f"{path}.",
                    aliases=aliases,
                )
            )
        else:
            raise ValueError(f"{name}: unknown model/subcircuit {model!r} on {inst!r}")
    return devices


# --------------------------------------------------------------------------- #
# the LVS reference netlist
# --------------------------------------------------------------------------- #

#: Net name `klt extract`'s gf180mcu deck ties every NMOS body to -- the
#: deck's `substrate_net` global. gf180mcu's curated extraction deck has no
#: distinct tap layer, so a drawn substrate tie is NOT what names this net
#: (see `layout/README.md`'s "documented gf180mcu extraction approximations"
#: and `../README.md`).
SUBSTRATE_NET = "vsubs"


def resolve_aliases(
    devices: list[Device], aliases: list[tuple[str, str]], prefer: set[str] | None = None
) -> list[Device]:
    """Merge every alias pair (from a zero-volt probe source) into one net
    name and rewrite `devices` accordingly.

    Union-find. The surviving name is a member of `prefer` when the merged
    set contains one -- so a merge that swallows a labelled pin keeps the
    pin's name, which is what the extracted layout will call it -- and
    otherwise the lexicographically smallest, so the result is
    deterministic either way. Getting this wrong is not cosmetic: naming the
    comparator's merged supply node after an internal net instead of `vdd`
    turned a clean block compare into 449 mismatches during this bring-up.
    """
    prefer = prefer or set()
    parent: dict[str, str] = {}

    def find(net: str) -> str:
        parent.setdefault(net, net)
        while parent[net] != net:
            parent[net] = parent[parent[net]]
            net = parent[net]
        return net

    def rank(net: str) -> tuple[int, str]:
        return (0 if net in prefer else 1, net)

    for a, b in aliases:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb), key=rank)
            parent[hi] = lo
    if not aliases:
        return devices
    return [
        Device(
            kind=d.kind,
            path=d.path,
            nets=tuple(find(n) for n in d.nets),
            params=d.params,
        )
        for d in devices
    ]


def merge_nets(
    devices: list[Device],
    merges: list[tuple[str, str]],
    prefer: set[str] | None = None,
) -> list[Device]:
    """Same union-find rewrite as :func:`resolve_aliases`, but for nets a
    *layout* merges that the schematic does not -- specifically the two
    terminals of a resistor, which `klt extract`'s gf180mcu deck sees as a
    plain Poly2 conductor because it has no resistor device class (see
    `place.draw_poly_resistor`). Kept as a separate, explicitly-named entry
    point so a reference netlist can never acquire such a merge by accident.
    """
    return resolve_aliases(devices, merges, prefer)


def write_reference(
    path: str,
    top: str,
    devices: list[Device],
    pins: list[str],
    body_net_of: dict[str, str],
    header: list[str],
    *,
    include_caps: bool = False,
) -> None:
    """Write the flat SPICE reference `klt lvs` compares the extracted
    layout netlist against.

    `body_net_of` maps each MOSFET's device path to the net its body
    terminal lands on in the *layout*: `SUBSTRATE_NET` for every NMOS, and
    the net of the Nwell island the device sits in for a PMOS (see
    `../README.md` -- the schematic ties every PMOS body to `vdd`, which the
    curated extraction deck cannot reproduce because it never connects
    `nwell` to `contact`).

    `include_caps` decides whether the MiM capacitors are written. It is a
    property of the LAYOUT, not of the schematic, and the two states are not
    interchangeable:

    * `True` -- the caller drew every capacitor in `devices` as a *recognised*
      device (`geometry.draw_mim_cap(..., device=True)`, i.e. carrying
      `CAP_MK`/`MIM_L_MK`) **and** wired both of its plates. `klt extract`
      then reports a `cap_mim_2f0_m4m5_noshield` per capacitor and the
      reference has to say so too.
    * `False` (the default) -- the capacitors are drawn as inert MiM geometry
      with no marker layers, so the extraction deck never recognises them and
      a capacitor in the reference would be an unconditional
      `device.unmatched`. This is still the state of the tiled CDAC arrays in
      `gen_adc_top.py`, whose per-weight bottom-plate interconnect is not
      drawn -- see `../README.md`.

    Resistors are always omitted, and their layout bodies extract as a
    *short* between their terminals -- callers pass the shorted net names in
    `body_net_of`'s companion net-merge map before calling this. Every
    omission is stated in `../README.md`, never silent.
    """
    lines = list(header)
    lines.append(f".SUBCKT {top} " + " ".join(pins))
    for dev in devices:
        if not dev.is_mos:
            continue
        d, g, s, _b = dev.nets
        body = body_net_of[dev.path]
        model = "nfet" if dev.kind == "nfet" else "pfet"
        name = "M" + dev.path.replace(".", "_")
        lines.append(
            f"{name} {d} {g} {s} {body} {model} "
            f"L={dev.params['l'] * 1e6:g}U W={dev.params['w'] * 1e6:g}U"
        )
    if include_caps:
        for dev in devices:
            if dev.kind != "cap":
                continue
            # The schematic writes the MiM as `X<name> top bottom mim_cap_2f0`;
            # the extraction reports its terminals in (a, b) order with `a` on
            # the bottom plate. SPICE capacitors are symmetric and the comparer
            # pairs them structurally, so the drawn order is used as-is.
            top_net, bottom_net = dev.nets[0], dev.nets[1]
            name = "C" + dev.path.replace(".", "_")
            lines.append(
                f"{name} {bottom_net} {top_net} "
                f"{mim_reference_farads(*dev.cap_plate_nm):.8g} "
                f"{MIM_DEVICE_CLASS}"
            )
    lines.append(f".ENDS {top}")
    lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def design_dir(start: str) -> str:
    """Absolute path to this repo's `design/` directory, found by walking up
    from `start` (so a generator can be run from anywhere)."""
    here = os.path.abspath(start)
    while True:
        candidate = os.path.join(here, "design")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(here)
        if parent == here:
            raise RuntimeError(f"no design/ directory above {start}")
        here = parent
