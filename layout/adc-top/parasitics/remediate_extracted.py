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

1. **PMOS body gap** (README "NOT closed", `klayout-tools#555`, guidance item 1)
   -- **now closed in the LAYOUT, by DR-0035; see "The body-tie step after
   DR-0035" below.** Against an *untapped* stream, gf180mcu's curated `klt
   extract` deck had no drawn tap to derive a body net from, so every PMOS
   device's body (Nwell) terminal landed on an anonymous, un-pinned net
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

THE BODY-TIE STEP AFTER DR-0035 (issue #381)
--------------------------------------------
DR-0035 (#356/PR #384) drew an n+ tap inside every `Nwell` island and routed it
to `vdd`, and closed/strapped both substrate-tie rings to `vss`. The deck's
implant-narrowed `tap_nplus`/`tap_pplus` derivations then give `klt extract` a
real body net to report, so on the **tapped** geometry there is no anonymous
body net left to rewrite. Measured directly on the two committed extractions,
same pinned `klt` (`0.5.0+gb15edf5e3a2e`), geometry the only variable --
`reports/20260819-060730-bbed59c/` (pre-tap) vs
`reports/20260923-094816-904af96/` (post-tap, and post-DR-0037's Metal2
straps):

    block       pre-tap PMOS bodies              post-tap PMOS bodies
    adc_top     20 anonymous nets / 148 terms    1 net `vdd`   / 0 anonymous
    adc_block   25 anonymous nets / 160 terms    1 net `vdd`   / 0 anonymous
    adc_tgate    1 anonymous net  /   1 term     1 net `vdd`   / 0 anonymous
                (NMOS bodies: pre `vsubs` (a pin), post `vss` in both blocks;
                 the leaf keeps `vsubs`, which is a pin of the leaf either way)

So the rewrite is **retired on tapped input, not deleted**: the block and leaf
entry points below now *partition* the PMOS body terminals into "already on the
drawn `vdd` tie" and "anonymous", rewrite only the second set, and assert -- on
every path -- that no MOS body terminal is left on a net the instantiating deck
cannot reach. Three reasons it is retired this way rather than by deleting the
code:

  * `reports/` is **append-only evidence**. Every extraction minted before
    2026-09-23 is untapped, and this module has to keep reading those
    unchanged (the same argument `_LEG_RE` already makes for pre-`875eac3`
    netlists). Deleting the rewrite would make the older records unreadable.
  * The assertion is the part with ongoing value. A silent regression -- a
    tap deleted, a strap broken, a future cell drawn without one -- puts a
    body back on an anonymous net, and the partition below fails loudly
    instead of quietly resimulating a floating well.
  * Running the rewrite unconditionally on tapped input is not merely
    redundant, it **hard-fails**: `vdd` appears hundreds of times as a
    non-body terminal, so the exclusivity guard refuses it (verified against
    the post-tap reports: `ValueError: refusing to rewrite PMOS body net
    'vdd': it also appears 536x as a non-body terminal` on `adc_top`; 594x on
    `adc_block`, 3x on `adc_tgate`). "Keep it as-is" was therefore never an
    available disposition.

The *second* step below (the sampled-input port promotion) is unaffected by
DR-0035 and is kept exactly as it was: it is a pin-naming gap, not a body-bias
gap.

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
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: The supply net the schematic ties every PMOS body to (single-well).
VDD_NET = "vdd"

#: `klt extract --parasitics` leg-node suffix. Since the `875eac3` toolchain
#: pin (issue #116, upstream `klayout-tools#593`) the extractor no longer
#: hangs a net's whole resistance off a dead-end `<net>__par` stub: it splits
#: each net into a HUB (`<net>`, keeping the net's name and its C to
#: substrate) plus one LEG per device terminal (`<net>__t<k>`), with a
#: distance-weighted series R from each leg back to the hub. The terminal
#: nets written on device cards are therefore leg names, not net names.
#:
#: Every STRUCTURAL rule in this module -- "is this terminal a bottom
#: plate?", "is this leg source a supply?", "does this body net appear
#: anywhere else?" -- is a statement about the NET, so it is evaluated on the
#: hub. Every REWRITE preserves the leg: promoting rail `$8` to `vinp`
#: renames `$8__t3` to `vinp__t3`, so the in-path resistors this pin bump
#: exists to deliver survive the remediation instead of being collapsed by
#: it. Netlists from before the bump have no legs at all, `_hub()` is the
#: identity on them, and this module still reads them unchanged -- which is
#: required, because `reports/` is append-only evidence.
_LEG_RE = re.compile(r"^(?P<hub>.+)__t\d+$")


def _hub(net: str) -> str:
    """The net a (possibly leg) terminal name belongs to."""
    m = _LEG_RE.match(net)
    return m.group("hub") if m else net


def _leg_suffix(net: str) -> str:
    """`"__t3"` for a leg name, `""` for a hub name."""
    m = _LEG_RE.match(net)
    return net[len(m.group("hub")):] if m else ""

#: PDK MiM subckt the `--pdk` extraction binds each unit cap to; asserted, not
#: rewritten (guidance item 2 -- "map to the PDK MiM subckt").
MIM_SUBCKT = "cap_mim_2f0_m4m5_noshield"

#: Nets a rail may legitimately be if it is a supply/reference, not the input.
SUPPLY_LIKE = {"vdd", "vss", "vcm", "vref", "vsubs", "0"}

#: Names the two promoted input-rail pins get, topp side then topn side.
VINP_PIN = "vinp"
VINN_PIN = "vinn"

#: Names issue #91's layout fix gives the fourth-leg input rail directly in
#: the drawn GDS (`layout/adc-top/gen_adc_top.py`'s own `pins=` list, chosen
#: to match `lib/netlist.py`'s pre-existing LVS-reference port names) --
#: distinct from `VINP_PIN`/`VINN_PIN` above, which is the name THIS
#: script's own promotion gives the rail in its *remediated* output. A raw
#: `klt extract` of a post-#91 layout already declares these as `.SUBCKT`
#: pins, so `_find_input_rails`'s "already a declared pin -> not an input-
#: rail candidate" rule has to carve out exactly these two names, or the
#: real per-side input rails would be structurally indistinguishable from
#: `topp`/`topn` (see that function's docstring for why `topp`/`topn` reach
#: the same code path and must stay excluded).
RAW_LAYOUT_INPUT_PINS = {"pinp", "pinn"}


@dataclass
class Card:
    """One netlist statement, already continuation-joined."""

    raw: str  # original text (comments/params preserved verbatim)
    tokens: list[str]  # whitespace-split tokens of `raw`

    @property
    def head(self) -> str:
        return self.tokens[0] if self.tokens else ""


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
    #: Anonymous PMOS-body nets this pass actually rewrote (pre-DR-0035 input).
    pmos_body_nets: set[str] = field(default_factory=set)
    #: PMOS-body nets that were ALREADY the drawn `vdd` tie (post-DR-0035
    #: input) -- nothing was rewritten for these; they are recorded so the
    #: caller and the emitted header can say which disposition applied.
    tied_body_nets: set[str] = field(default_factory=set)
    input_rails: list[str] = field(default_factory=list)  # [topp-side, topn-side]
    n_pmos_rewritten: int = 0
    n_pmos_already_tied: int = 0
    n_mim: int = 0

    @property
    def body_gap_closed_in_layout(self) -> bool:
        """True when the extraction needed no body rewrite because the layout
        already ties every PMOS body (DR-0035 drawn n-well taps)."""
        return self.n_pmos_rewritten == 0 and self.n_pmos_already_tied > 0

    @property
    def body_tie_disposition(self) -> str:
        if self.body_gap_closed_in_layout:
            return "drawn-in-layout"
        if self.n_pmos_rewritten:
            return "rewritten"
        return "none"


def _collect_bottom_plates(nl: Netlist) -> set[str]:
    """Cap terminals that are NOT top plates -- i.e. the CDAC bottom plates."""
    plates: set[str] = set()
    for card in nl.cards:
        if _is_cap(card):
            a, b = _hub(card.tokens[1]), _hub(card.tokens[2])
            for net in (a, b):
                if net not in ("topp", "topn"):
                    plates.add(net)
    return plates


def _partition_pmos_body_nets(nl: Netlist) -> tuple[set[str], set[str]]:
    """Split the PMOS body nets into `(anonymous, already_tied)`.

    *already_tied* is the post-DR-0035 case: the layout draws an n+ tap in
    every Nwell island and routes it to `vdd`, so `klt extract` reports the
    body terminal directly on the `vdd` net -- which is also a declared
    `.SUBCKT` pin, i.e. a node the instantiating deck drives. Nothing needs
    rewriting for these, and rewriting them anyway is impossible: `vdd`
    fails the exclusivity guard below by construction.

    *anonymous* is the pre-DR-0035 case this module was written for. A net
    rewritten to `vdd` must not appear anywhere else, or the rewrite would
    corrupt a real connection. We collect every PMOS 4th-terminal net, then
    verify each appears in no other terminal position, in no pin list, and in
    no parasitic RC branch. Any collision raises -- that guard is unchanged,
    it just no longer sees the drawn-tie nets.
    """
    body_nets: set[str] = set()
    other_occurrences: dict[str, int] = {}

    def note_other(net: str) -> None:
        other_occurrences[net] = other_occurrences.get(net, 0) + 1

    for card in nl.cards:
        kind = _is_mos(card)
        if kind == "pfet":
            d, g, s, b = (_hub(n) for n in _mos_terminals(card))
            body_nets.add(b)
            for net in (d, g, s):
                note_other(net)
        elif kind == "nfet":
            d, g, s, b = (_hub(n) for n in _mos_terminals(card))
            for net in (d, g, s, b):
                note_other(net)
        elif _is_cap(card):
            for net in card.tokens[1:3]:
                note_other(_hub(net))
        elif card.tokens and card.head[0] in ("R", "C"):
            for net in card.tokens[1:3]:
                note_other(_hub(net))

    pins = set(nl.pins)
    tied = {net for net in body_nets if net == VDD_NET}
    for net in sorted(tied):
        # A drawn tie is only a *closed* gap if the deck instantiating this
        # subckt can actually drive it. `vdd` that is not a pin would be a
        # hardcoded global the caller cannot see -- exactly the failure
        # `remediate_leaf` refuses to create.
        if net not in pins:
            raise ValueError(
                f"PMOS bodies extract on {net!r}, but {net!r} is not a declared "
                f".SUBCKT pin of {nl.top} -- that is a hidden global, not a "
                "drivable body tie; refusing to treat the body gap as closed."
            )

    anonymous = body_nets - tied
    for net in sorted(anonymous):
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
    return anonymous, tied


def _find_pmos_body_nets(nl: Netlist) -> set[str]:
    """Back-compatible alias: just the anonymous half of the partition."""
    return _partition_pmos_body_nets(nl)[0]


def _count_pmos_body_terminals(nl: Netlist, nets: set[str]) -> int:
    """How many PMOS body terminals land on one of `nets`."""
    return sum(
        1
        for card in nl.cards
        if _is_mos(card) == "pfet" and _hub(_mos_terminals(card)[3]) in nets
    )


def _assert_no_unreachable_bodies(nl: Netlist, pins: list[str]) -> None:
    """Post-condition: every MOS body terminal is on a node the caller can bias.

    This is the invariant the body-tie *rewrite* used to deliver and which is
    kept after DR-0035 retired the rewrite on tapped input (issue #381). A
    body is acceptable if it is a declared `.SUBCKT` pin of the emitted cell
    or one of the extractor's own supply/substrate globals; anything else is
    an un-biased node and a resimulation of it would be meaningless.
    """
    ok = set(pins) | SUPPLY_LIKE
    bad: dict[str, int] = {}
    for card in nl.cards:
        if _is_mos(card) is None:
            continue
        body = _hub(_mos_terminals(card)[3])
        if body not in ok:
            bad[body] = bad.get(body, 0) + 1
    if bad:
        raise ValueError(
            f"{nl.top}: {sum(bad.values())} MOS body terminal(s) remain on "
            f"net(s) the instantiating deck cannot bias: {sorted(bad)}. "
            "Neither a declared pin nor a supply -- refusing to emit a core "
            "whose bodies float."
        )


def _find_input_rails(nl: Netlist, bottom_plates: set[str]) -> list[str]:
    """The two per-side sampled-input rails, identified structurally.

    Every four-leg CDAC switch is a T-gate connecting a bottom plate to one leg
    source: V_in (the sampled input), V_ref, V_cm or V_ss. The three reference
    legs land on pins (`vref`/`vcm`/`vss`); the input leg lands on either an
    internal, un-pinned rail (the raw extraction this script was originally
    written against) or -- since issue #91 drew the missing pin label at the
    layout level -- an already-declared `pinp`/`pinn` pin (`RAW_LAYOUT_INPUT_
    PINS`). Either way: for each MOS whose channel touches exactly one bottom
    plate, the OTHER channel terminal is a leg source; the non-supply,
    non-already-pinned leg sources -- PLUS the two `RAW_LAYOUT_INPUT_PINS`
    names specifically -- are the input rails. We expect exactly two (one per
    side) and order them by which side's top plate their bottom plates feed.

    The "already a declared pin -> not a candidate" half of this rule is
    NOT redundant with `SUPPLY_LIKE`: the DR-0011 terminating unit's cap
    ties directly to `vcm` (not a per-weight bottom-plate node), so `vcm`
    itself is a member of `bottom_plates`, which makes the top-plate V_cm
    switch's OWN T-gate (`Xs vcm top gn gp vdd adc_tgate` in `adc_tp_sw`)
    structurally match this same rule with `other` = `topp`/`topn` -- a
    real pin, just not an input rail. Excluding every already-pinned
    candidate except the two names #91's layout generator actually gives
    the input rail keeps that exclusion (proven necessary directly: without
    it, this function returns `{pinp, pinn, topp, topn}` against a post-#91
    extraction) while still admitting the one already-pinned candidate this
    script has to recognise.
    """
    # bottom plate -> which top plate ("topp"/"topn") its cap connects to
    plate_side: dict[str, str] = {}
    for card in nl.cards:
        if _is_cap(card):
            a, b = _hub(card.tokens[1]), _hub(card.tokens[2])
            top = "topp" if "topp" in (a, b) else ("topn" if "topn" in (a, b) else "")
            for net in (a, b):
                if net not in ("topp", "topn") and top:
                    plate_side[net] = top

    pins = set(nl.pins)
    rail_side: dict[str, str] = {}
    for card in nl.cards:
        if not _is_mos(card):
            continue
        d, g, s, _b = (_hub(n) for n in _mos_terminals(card))
        chan = [d, s]
        touched = [n for n in chan if n in bottom_plates]
        if len(touched) != 1:
            continue
        bp = touched[0]
        other = chan[1] if chan[0] == bp else chan[0]
        if other in SUPPLY_LIKE:
            continue
        if other in pins and other not in RAW_LAYOUT_INPUT_PINS:
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
        # Structural decisions are about the NET; the rewrite preserves the
        # leg, so `$8__t3` -> `vinp__t3` and the star's in-path series R
        # stays attached to the same terminal (see `_hub`).
        hub, leg = _hub(net), _leg_suffix(net)
        if hub in body:
            return VDD_NET + leg
        return rail_map.get(hub, hub) + leg

    for card in nl.cards:
        if not card.tokens:
            continue
        kind = _is_mos(card)
        if kind is not None:
            d, g, s, b = _mos_terminals(card)
            new = [card.tokens[0], remap(d), remap(g), remap(s), remap(b), *card.tokens[5:]]
            if kind == "pfet" and _hub(b) in body:
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


#: Pin name the LEAF remediation gives the promoted PMOS-body (Nwell) net.
NWELL_PIN = "vnw"


def remediate_leaf(
    text: str, top: str, body_pin: str = NWELL_PIN
) -> tuple[str, Remediation]:
    """PMOS-body remediation for a **leaf cell**, which has no supply pin.

    `remediate()` above ties every anonymous PMOS-body net to the literal net
    `vdd`, because the blocks it handles (`ADC_TOP`/`ADC_BLOCK`) declare a
    `vdd` pin -- the tie is then made outside, by whatever drives that pin. A
    drawn leaf cell like `adc_tgate` declares no supply pin at all (its pins
    are `gn gp vin vout vsubs`), so hardcoding `vdd` inside it would create a
    global net the instantiating deck cannot see or drive, which is exactly
    the silent-rewrite failure this module exists to avoid.

    So the leaf path **promotes** the body net(s) to one new `.SUBCKT` pin
    (`vnw`) instead of tying them: same gap closed (the body terminal is no
    longer an anonymous, un-biased net), same single-well assumption
    (`layout/adc-top/lib/netlist.py`'s `body_net_of`; every Nwell island in a
    single-well layout is the same electrical node), but the bias is supplied
    by the testbench at the instance, where a reader can see it, rather than
    baked into the extracted cell.

    Everything else is unchanged from `remediate()`: `_find_pmos_body_nets`
    supplies the same exclusivity assertion (a net is only rewritten if it
    appears *exclusively* as a PMOS body terminal), no geometry, connectivity
    or parasitic RC element is touched, and the emitted header says the file
    is a remediation rather than raw `klt extract` output.

    Deliberately does NOT run the two block-level steps: there is no CDAC in a
    leaf cell, so `_collect_bottom_plates`/`_find_input_rails` have nothing to
    resolve and the MiM assertion has nothing to assert. Calling `remediate()`
    on a leaf raises on both counts, which is the correct behaviour for it --
    hence a separate entry point rather than a flag threaded through it.

    **Post-DR-0035 (issue #381)**: `adc_tgate.gds` now draws its own n+ tap, so
    the extracted leaf declares a real `vdd` pin and its PMOS body lands on it
    (`.SUBCKT ADC_TGATE gn gp vdd vin vout vsubs`, `X$2 ... vdd__t0
    pfet_03v3`). On that input the promotion is skipped -- no `vnw` pin is
    added, the pin list is the extractor's own -- and
    `_assert_no_unreachable_bodies` proves the bodies are still drivable.
    The promotion path above stays for the untapped netlists under `reports/`,
    which are append-only evidence and must keep reading as they always did.
    """
    nl = parse(text, top)
    rem = Remediation()
    rem.pmos_body_nets, rem.tied_body_nets = _partition_pmos_body_nets(nl)
    rem.n_pmos_already_tied = _count_pmos_body_terminals(nl, rem.tied_body_nets)
    if not rem.pmos_body_nets and not rem.tied_body_nets:
        raise ValueError(
            f"{top}: no PMOS body terminals found at all -- this is not a "
            "`--pdk` extraction (no `pfet_03v3` cards); refusing to emit a "
            "'remediated' file over a netlist this function cannot read."
        )

    out_pins = list(nl.pins)
    if rem.pmos_body_nets:
        # Pre-DR-0035 (untapped) input: promote the anonymous Nwell net(s).
        if body_pin in nl.pins:
            raise ValueError(
                f"{top}: cannot promote the PMOS body to pin {body_pin!r} -- that "
                "name is already a declared .SUBCKT pin."
            )
        body = set(rem.pmos_body_nets)
        for card in nl.cards:
            if not card.tokens:
                continue
            if _is_mos(card) != "pfet":
                continue
            d, g, s, b = _mos_terminals(card)
            if _hub(b) not in body:
                continue
            rem.n_pmos_rewritten += 1
            card.tokens = [card.tokens[0], d, g, s, body_pin + _leg_suffix(b),
                           *card.tokens[5:]]
            card.raw = " ".join(card.tokens)
        out_pins.append(body_pin)

    _assert_no_unreachable_bodies(nl, out_pins)

    out: list[str] = []
    out.append("* REMEDIATED extracted leaf cell -- NOT raw `klt extract` output.")
    out.append("* Produced by layout/adc-top/parasitics/remediate_extracted.py")
    out.append("* (remediate_leaf):")
    if rem.n_pmos_rewritten:
        out.append(
            f"*   - {rem.n_pmos_rewritten} PMOS body terminal(s) on "
            f"{len(rem.pmos_body_nets)} anonymous Nwell net(s) promoted to a new"
        )
        out.append(
            f"*     .SUBCKT pin '{body_pin}', so the instantiating testbench "
            "supplies the"
        )
        out.append(
            "*     well bias explicitly (local remediation of the klt PMOS-body "
            "gap;"
        )
        out.append("*     upstream klayout-tools#555). No net is tied inside the cell.")
    else:
        tied = ", ".join(sorted(rem.tied_body_nets))
        out.append(
            f"*   - body-tie step NOT APPLIED: all {rem.n_pmos_already_tied} "
            f"PMOS body terminal(s) already"
        )
        out.append(
            f"*     extract on `{tied}`, a declared .SUBCKT pin, because DR-0035 "
            "draws an n+ tap"
        )
        out.append(
            "*     inside the cell's Nwell and routes it there -- closing the "
            "klayout-tools#555"
        )
        out.append(
            "*     body gap in the LAYOUT, with no anonymous Nwell net left to "
            "promote."
        )
        out.append(
            "*     Asserted, not assumed: see remediate_extracted."
            "_assert_no_unreachable_bodies()"
        )
        out.append("*     (issue #381).")
    out.append(
        "*   - device geometry, connectivity and the parasitic RC ladder are "
        "untouched."
    )
    out.append("* See remediate_extracted.py's remediate_leaf() for provenance.")
    out += [
        c
        for c in nl.header_comments
        if c.strip().startswith("*") and "extracted by klt" not in c
    ]
    out.append(f".SUBCKT {top} " + " ".join(out_pins))
    for card in nl.cards:
        out.append(card.raw)
    out.extend(nl.tail)
    return "\n".join(out) + "\n", rem


def remediate(text: str, top: str) -> tuple[str, Remediation]:
    nl = parse(text, top)
    rem = Remediation()
    rem.pmos_body_nets, rem.tied_body_nets = _partition_pmos_body_nets(nl)
    rem.n_pmos_already_tied = _count_pmos_body_terminals(nl, rem.tied_body_nets)
    bottom_plates = _collect_bottom_plates(nl)
    rem.input_rails = _find_input_rails(nl, bottom_plates)
    _rewrite(nl, rem)

    # Assert MiM binding still present (guidance item 2).
    if rem.n_mim == 0:
        raise ValueError(
            f"no {MIM_SUBCKT} cap cards found -- extraction is not the --pdk "
            "form this remediation assumes (guidance item 2)."
        )

    # Drop the raw rail names from the header before appending the canonical
    # `vinp`/`vinn` pair -- a no-op set difference against the pre-#91 raw
    # extraction (its rails were anonymous, un-pinned nets, never in
    # `nl.pins` to begin with) and what stops the post-#91 raw extraction
    # (whose rails are ALREADY declared `pinp`/`pinn` pins) from emitting
    # both the old and the new name: `_rewrite` below renames every BODY
    # occurrence of a rail to its canonical name, so leaving the raw name in
    # the pin list would declare an orphaned, unused external pin.
    new_pins = [p for p in nl.pins if p not in rem.input_rails] + [VINP_PIN, VINN_PIN]
    _assert_no_unreachable_bodies(nl, new_pins)
    out: list[str] = []
    out.append("* REMEDIATED extracted core -- NOT raw `klt extract` output.")
    out.append("* Produced by layout/adc-top/parasitics/remediate_extracted.py:")
    if rem.n_pmos_rewritten:
        out.append(
            f"*   - {rem.n_pmos_rewritten} PMOS body terminals retied to "
            f"'{VDD_NET}'"
        )
        out.append(
            "*     (local remediation of the klt PMOS-body gap; upstream "
            "klayout-tools#555)."
        )
    else:
        tied = ", ".join(sorted(rem.tied_body_nets))
        out.append(
            f"*   - body-tie step NOT APPLIED: all {rem.n_pmos_already_tied} "
            f"PMOS body terminals already"
        )
        out.append(
            f"*     extract on `{tied}` because DR-0035 draws an n+ tap in every "
            "Nwell and routes"
        )
        out.append(
            "*     it there, closing the klayout-tools#555 body gap in the "
            "LAYOUT. Asserted,"
        )
        out.append(
            "*     not assumed -- see _assert_no_unreachable_bodies() "
            "(issue #381)."
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
    ap.add_argument(
        "--leaf",
        action="store_true",
        help="leaf-cell mode: promote the anonymous PMOS body net(s) to a new "
             f"'{NWELL_PIN}' .SUBCKT pin instead of tying them to '{VDD_NET}' "
             "(a drawn leaf cell has no supply pin to tie to). Skips the "
             "CDAC-specific input-rail promotion and MiM assertion, which have "
             "nothing to resolve in a leaf. See remediate_leaf().",
    )
    args = ap.parse_args(argv)

    src = Path(args.netlist) if args.netlist else _latest_report(args.top)
    if args.leaf:
        out_text, rem = remediate_leaf(src.read_text(), args.top)
    else:
        out_text, rem = remediate(src.read_text(), args.top)

    if args.check:
        assert rem.n_pmos_rewritten > 0 or rem.n_pmos_already_tied > 0, (
            "no PMOS bodies rewritten and none already tied -- the netlist has "
            "no readable PMOS body terminals at all"
        )
        if rem.body_gap_closed_in_layout:
            body_note = (
                f"{rem.n_pmos_already_tied} PMOS bodies already on "
                f"{sorted(rem.tied_body_nets)} (drawn tap, DR-0035; no rewrite)"
            )
        elif args.leaf:
            body_note = (
                f"{rem.n_pmos_rewritten} PMOS body terminal(s) on "
                f"{sorted(rem.pmos_body_nets)} promoted to pin {NWELL_PIN}"
            )
        else:
            body_note = f"{rem.n_pmos_rewritten} PMOS bodies -> {VDD_NET}"
        if args.leaf:
            print(f"OK {src.name}: {body_note}.")
            return 0
        assert len(rem.input_rails) == 2, "input rails not resolved"
        assert rem.n_mim > 0, "no PDK MiM cards"
        print(f"OK {src.name}: {body_note}, "
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
