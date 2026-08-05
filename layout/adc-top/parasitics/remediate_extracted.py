#!/usr/bin/env python3
"""Post-process a `klt extract --pdk` netlist into a *simulatable* extracted
core, remediating the two known gaps that stop the raw extraction from being
resimulated by the `sim/` harness -- both documented, both deterministic,
neither a silent edit.

    python3 layout/adc-top/parasitics/remediate_extracted.py <in.para.spice> \
        --top ADC_TOP -o <out.remediated.spice>

    python3 layout/adc-top/parasitics/remediate_extracted.py --check   # self-test
                                                                       # on the
                                                                       # committed
                                                                       # reports/

WHY THIS EXISTS (issue #89, scope item 0 + guidance items 1 & 3)
----------------------------------------------------------------
`layout/adc-top/parasitics/README.md` established that the `--pdk gf180mcuD`
extraction of `adc_top` binds every device and every MiM cap to a real
`sm141064.ngspice` model, but is still NOT directly simulatable as an ADC core,
for two structural reasons this pass closes:

1. **PMOS body gap** (README "NOT closed", `klayout-tools#555`, guidance item 1).
   gf180mcu's curated `klt extract` deck has no tap/well-label layer, so every
   PMOS device's body (Nwell) terminal lands on an anonymous, un-pinned net
   (`X$149 ... vdd $157 pfet_03v3`, `$157` not a `.SUBCKT` pin) instead of the
   `vdd` tie the schematic assumes (`design/adc-top/adc_top.spice`; the
   single-well convention `sim/device-switch-ron/testbench/` states outright:
   "NMOS body to ground, PMOS body to vdd"). The README's reproduced smoke test
   showed such a net settling to ~=0 V, a full supply-rail V_sb error on every
   PMOS. This pass rewrites every anonymous PMOS-body net to `vdd`.

   This is the *local remediation* path guidance item 1 sanctions instead of
   waiting on upstream `klayout-tools#555` (still OPEN as of 2026-08-05). It is
   the same fix `layout/adc-top/lib/netlist.py`'s `body_net_of` mapping applies
   for LVS purposes -- there, each PMOS body is tied to the Nwell-island net; a
   single-well layout means all those islands are the `vdd` net -- restated here
   as a netlist rewrite for *simulation* rather than an LVS reference.

2. **Sampled-input port gap** (structural mismatch, guidance item 3, plus a
   finding this pass surfaces). The extracted `ADC_TOP` has 63 pins -- the 54
   `hi/lo/rel_<w>_<s>` decode controls plus `sel_in topn topp tp_gn vcm vdd vref
   vss vsubs` -- but **no input pin**. DR-0014 samples the input on the CDAC
   bottom plates through each cell's fourth-leg T-gate; the common per-side
   input rail those nine T-gates share is an internal, un-pinned net (`$8` for
   the topp side, `$91` for the topn side, each degree 18 = 9 T-gates x
   nfet+pfet). With no pin, a wrapper testbench cannot inject the input, so no
   conversion can run. This pass promotes those two rails to named pins
   `vinp`/`vinn`, so an extracted-core testbench can drive the sampled input.

The MiM-mapping question (guidance item 2) needs **no rewrite**: the `--pdk`
extraction already emits each unit cap as `X... cap_mim_2f0_m4m5_noshield
c_length=.. c_width=..`, a subckt call that binds to `sm141064_mim.ngspice`'s
`cap_mim_2f0_m4m5_noshield` (the same subckt `sim/harness/pdk.py`'s
`mim_subckt('2f0')` resolves, and the same physical model
`design/adc-top/adc_top.spice`'s `mim_cap_2f0` wrapper reaches). So the chosen
methodology -- **map to the PDK MiM subckt** -- is the extraction's native form,
and is the fair comparison against the schematic's subckt-instantiated MiM. This
script asserts that binding holds and otherwise leaves the cards untouched.

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO
-----------------------------------------
It does not touch device geometry, connectivity, or the parasitic R/C ladder.
It rewrites *net labels* only (PMOS body -> vdd; two input rails -> pins). Every
rewrite is asserted safe before it is applied: a body net is rewritten only if
it appears *exclusively* as a PMOS body terminal (never as a signal, a pin, or a
parasitic RC node), and the input rails are identified structurally (the
non-cap, non-supply terminal shared by the fourth-leg T-gates), not by name. If
an assertion fails the script raises rather than emit a plausibly-wrong core.
The output header records that it is a remediation, not raw `klt extract`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: The supply net the schematic ties every PMOS body to (single-well).
VDD_NET = "vdd"

#: PDK MiM subckt the `--pdk` extraction binds each unit cap to; asserted, not
#: rewritten (guidance item 2 -- "map to the PDK MiM subckt").
MIM_SUBCKT = "cap_mim_2f0_m4m5_noshield"

#: Nets a rail may legitimately be if it is a supply/reference, not the input.
SUPPLY_LIKE = {"vdd", "vss", "vcm", "vref", "vsubs", "0"}

#: Names the two promoted input-rail pins get, topp side then topn side.
VINP_PIN = "vinp"
VINN_PIN = "vinn"


@dataclass
class Card:
    """One netlist statement, already continuation-joined."""

    raw: str  # original text (comments/params preserved verbatim)
    tokens: list[str]  # whitespace-split tokens of `raw`

    @property
    def head(self) -> str:
        return self.tokens[0] if self.tokens else ""

    @property
    def is_comment(self) -> bool:
        return self.raw.lstrip().startswith("*")


@dataclass
class Netlist:
    header_comments: list[str] = field(default_factory=list)
    subckt_line_idx: int = -1
    top: str = ""
    pins: list[str] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)  # body cards (device/R/C)
    tail: list[str] = field(default_factory=list)  # .ENDS and after


def _join_continuations(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("+"):
            if not out:
                raise ValueError("continuation line with nothing to continue")
            out[-1] = out[-1] + " " + line.lstrip()[1:].strip()
        else:
            out.append(line)
    return out


def parse(text: str, top: str) -> Netlist:
    lines = _join_continuations(text)
    nl = Netlist(top=top)
    state = "pre"  # pre -> body -> tail
    for line in lines:
        stripped = line.strip()
        low = stripped.lower()
        if state == "pre":
            if low.startswith(".subckt") and top.lower() in low.split():
                nl.pins = stripped.split()[2:]
                state = "body"
            else:
                nl.header_comments.append(line)
            continue
        if state == "body":
            if low.startswith(".ends"):
                nl.tail.append(line)
                state = "tail"
                continue
            if not stripped or stripped.startswith("*"):
                nl.cards.append(Card(raw=line, tokens=[]))
            else:
                nl.cards.append(Card(raw=line, tokens=stripped.split()))
            continue
        nl.tail.append(line)
    if not nl.pins:
        raise ValueError(f".SUBCKT {top} not found")
    return nl


def _is_mos(card: Card) -> str | None:
    """Return 'nfet'/'pfet' if this card is a MOS device, else None."""
    if not card.tokens or not card.head.startswith("X"):
        return None
    if "nfet_03v3" in card.tokens:
        return "nfet"
    if "pfet_03v3" in card.tokens:
        return "pfet"
    return None


def _is_cap(card: Card) -> bool:
    return bool(card.tokens) and card.head.startswith("X") and MIM_SUBCKT in card.tokens


def _mos_terminals(card: Card) -> tuple[str, str, str, str]:
    """(drain, gate, source, body) for a 4-terminal MOS card."""
    return card.tokens[1], card.tokens[2], card.tokens[3], card.tokens[4]


@dataclass
class Remediation:
    pmos_body_nets: set[str] = field(default_factory=set)
    input_rails: list[str] = field(default_factory=list)  # [topp-side, topn-side]
    n_pmos_rewritten: int = 0
    n_mim: int = 0


def _collect_bottom_plates(nl: Netlist) -> set[str]:
    """Cap terminals that are NOT top plates -- i.e. the CDAC bottom plates."""
    plates: set[str] = set()
    for card in nl.cards:
        if _is_cap(card):
            a, b = card.tokens[1], card.tokens[2]
            for net in (a, b):
                if net not in ("topp", "topn"):
                    plates.add(net)
    return plates


def _find_pmos_body_nets(nl: Netlist) -> set[str]:
    """PMOS body nets that appear ONLY as a PMOS body terminal.

    A net rewritten to `vdd` must not appear anywhere else, or the rewrite would
    corrupt a real connection. We collect every PMOS 4th-terminal net, then
    verify each appears in no other terminal position, in no pin list, and in no
    parasitic RC branch (`<net>__par`). Any collision raises.
    """
    body_nets: set[str] = set()
    other_occurrences: dict[str, int] = {}

    def note_other(net: str) -> None:
        other_occurrences[net] = other_occurrences.get(net, 0) + 1

    for card in nl.cards:
        kind = _is_mos(card)
        if kind == "pfet":
            d, g, s, b = _mos_terminals(card)
            body_nets.add(b)
            for net in (d, g, s):
                note_other(net)
        elif kind == "nfet":
            d, g, s, b = _mos_terminals(card)
            for net in (d, g, s, b):
                note_other(net)
        elif _is_cap(card):
            for net in card.tokens[1:3]:
                note_other(net)
        elif card.tokens and card.head[0] in ("R", "C"):
            for net in card.tokens[1:3]:
                note_other(net)

    pins = set(nl.pins)
    for net in sorted(body_nets):
        if other_occurrences.get(net):
            raise ValueError(
                f"refusing to rewrite PMOS body net {net!r}: it also appears "
                f"{other_occurrences[net]}x as a non-body terminal (would corrupt "
                "a real connection)."
            )
        if net in pins:
            raise ValueError(
                f"refusing to rewrite PMOS body net {net!r}: it is a declared "
                ".SUBCKT pin."
            )
    return body_nets


def _find_input_rails(nl: Netlist, bottom_plates: set[str]) -> list[str]:
    """The two per-side sampled-input rails, identified structurally.

    Every four-leg CDAC switch is a T-gate connecting a bottom plate to one leg
    source: V_in (the sampled input), V_ref, V_cm or V_ss. The three reference
    legs land on pins (`vref`/`vcm`/`vss`); the input leg lands on an internal
    rail. So: for each MOS whose channel touches exactly one bottom plate, the
    OTHER channel terminal is a leg source; the non-supply, non-pin leg sources
    are the input rails. We expect exactly two (one per side) and order them by
    which side's top plate their bottom plates feed.
    """
    pins = set(nl.pins)
    # bottom plate -> which top plate ("topp"/"topn") its cap connects to
    plate_side: dict[str, str] = {}
    for card in nl.cards:
        if _is_cap(card):
            a, b = card.tokens[1], card.tokens[2]
            top = "topp" if "topp" in (a, b) else ("topn" if "topn" in (a, b) else "")
            for net in (a, b):
                if net not in ("topp", "topn") and top:
                    plate_side[net] = top

    rail_side: dict[str, str] = {}
    for card in nl.cards:
        if not _is_mos(card):
            continue
        d, g, s, _b = _mos_terminals(card)
        chan = [d, s]
        touched = [n for n in chan if n in bottom_plates]
        if len(touched) != 1:
            continue
        bp = touched[0]
        other = chan[1] if chan[0] == bp else chan[0]
        if other in SUPPLY_LIKE or other in pins:
            continue
        side = plate_side.get(bp, "")
        if side:
            rail_side.setdefault(other, side)

    if len(rail_side) != 2:
        raise ValueError(
            f"expected exactly 2 sampled-input rails, found {len(rail_side)}: "
            f"{sorted(rail_side)}. The structural rule (non-supply leg source of a "
            "bottom-plate T-gate) did not resolve cleanly -- inspect the netlist."
        )
    # order: topp-side rail first, then topn-side
    ordered = sorted(rail_side, key=lambda n: (rail_side[n] != "topp", n))
    return ordered


def _rewrite(nl: Netlist, rem: Remediation) -> None:
    """Apply the net-label rewrites in place across every body card."""
    body = set(rem.pmos_body_nets)
    rail_map = {}
    if rem.input_rails:
        rail_map[rem.input_rails[0]] = VINP_PIN
        rail_map[rem.input_rails[1]] = VINN_PIN

    def remap(net: str) -> str:
        if net in body:
            return VDD_NET
        return rail_map.get(net, net)

    for card in nl.cards:
        if not card.tokens:
            continue
        kind = _is_mos(card)
        if kind is not None:
            d, g, s, b = _mos_terminals(card)
            new = [card.tokens[0], remap(d), remap(g), remap(s), remap(b), *card.tokens[5:]]
            if kind == "pfet" and b in body:
                rem.n_pmos_rewritten += 1
            card.tokens = new
            card.raw = " ".join(new)
        elif _is_cap(card):
            rem.n_mim += 1
            a, b = card.tokens[1], card.tokens[2]
            new = [card.tokens[0], remap(a), remap(b), *card.tokens[3:]]
            card.tokens = new
            card.raw = " ".join(new)
        elif card.head and card.head[0] in ("R", "C"):
            a, b = card.tokens[1], card.tokens[2]
            new = [card.tokens[0], remap(a), remap(b), *card.tokens[3:]]
            card.tokens = new
            card.raw = " ".join(new)


def remediate(text: str, top: str) -> tuple[str, Remediation]:
    nl = parse(text, top)
    rem = Remediation()
    rem.pmos_body_nets = _find_pmos_body_nets(nl)
    bottom_plates = _collect_bottom_plates(nl)
    rem.input_rails = _find_input_rails(nl, bottom_plates)
    _rewrite(nl, rem)

    # Assert MiM binding still present (guidance item 2).
    if rem.n_mim == 0:
        raise ValueError(
            f"no {MIM_SUBCKT} cap cards found -- extraction is not the --pdk "
            "form this remediation assumes (guidance item 2)."
        )

    new_pins = list(nl.pins) + [VINP_PIN, VINN_PIN]
    out: list[str] = []
    out.append("* REMEDIATED extracted core -- NOT raw `klt extract` output.")
    out.append("* Produced by layout/adc-top/parasitics/remediate_extracted.py:")
    out.append(f"*   - {rem.n_pmos_rewritten} PMOS body terminals retied to '{VDD_NET}'")
    out.append(
        "*     (local remediation of the klt PMOS-body gap; upstream "
        "klayout-tools#555)."
    )
    out.append(
        f"*   - input rails {rem.input_rails[0]}/{rem.input_rails[1]} promoted to "
        f"pins {VINP_PIN}/{VINN_PIN} (sampled-input port gap)."
    )
    out.append(
        f"*   - {rem.n_mim} MiM caps left as native PDK '{MIM_SUBCKT}' subckt calls."
    )
    out.append("* See remediate_extracted.py's module docstring for provenance.")
    out += [c for c in nl.header_comments if c.strip().startswith("*")
            and "extracted by klt" not in c]
    # SUBCKT line, wrapped modestly
    out.append(f".SUBCKT {top} " + " ".join(new_pins))
    for card in nl.cards:
        out.append(card.raw)
    out.extend(nl.tail)
    return "\n".join(out) + "\n", rem


def _latest_report(top: str) -> Path:
    """The newest `--pdk` extraction for `top` under reports/ (has X-subckt
    device cards, i.e. `pfet_03v3`, not bare `pfet` class labels)."""
    candidates = sorted((HERE / "reports").glob(f"*/{top.lower()}.para.spice"))
    for path in reversed(candidates):
        if "pfet_03v3" in path.read_text():
            return path
    raise FileNotFoundError(
        f"no --pdk extraction of {top} under {HERE/'reports'} (need pfet_03v3 cards)"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("netlist", nargs="?", help="extracted .para.spice (defaults to latest report)")
    ap.add_argument("--top", default="ADC_TOP")
    ap.add_argument("-o", "--output", help="write remediated netlist here")
    ap.add_argument("--check", action="store_true",
                    help="remediate the latest committed report and assert invariants; write nothing")
    args = ap.parse_args(argv)

    src = Path(args.netlist) if args.netlist else _latest_report(args.top)
    out_text, rem = remediate(src.read_text(), args.top)

    if args.check:
        assert rem.n_pmos_rewritten > 0, "no PMOS bodies rewritten"
        assert len(rem.input_rails) == 2, "input rails not resolved"
        assert rem.n_mim > 0, "no PDK MiM cards"
        print(f"OK {src.name}: {rem.n_pmos_rewritten} PMOS bodies -> {VDD_NET}, "
              f"rails {rem.input_rails} -> {VINP_PIN}/{VINN_PIN}, {rem.n_mim} MiM caps.")
        return 0

    if args.output:
        Path(args.output).write_text(out_text)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
