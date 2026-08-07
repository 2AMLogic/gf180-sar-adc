#!/usr/bin/env python3
"""Wire the remediated extracted `ADC_TOP` (or `ADC_BLOCK`) core into a
complete, simulatable conversion chain -- issue #89's **Scope item 0**:

    "Give gen_adc_top.py (or a dedicated harness) a way to instantiate the
    PMOS-body-remediated, MiM-mapped extracted netlist as the analog core
    while keeping comparator/SAR-logic/stimulus schematic-level."

This is the "dedicated harness" branch of that sentence. It does not modify
`design/adc-top/gen_adc_top.py` (its `TARGETS` are guarded byte-for-byte by
`sim/tests/test_adc_top_netlist.py`, and rewiring its `_core()` to carry a
second, extracted-core code path is a larger, separately reviewable change
than this increment). Instead it *imports* the pieces that are safe to
reuse verbatim -- the comparator subckt, the rung-1 SAR controller library,
and the DR-0013 input-drive-network / reference-network preamble -- and
supplies new wiring, `_wire_pin()` / `_core_extracted()` below, for the one
piece that has to differ: the analog core itself.

    python3 layout/adc-top/parasitics/gen_extracted_core_tb.py            # to stdout
    python3 layout/adc-top/parasitics/gen_extracted_core_tb.py --top ADC_TOP
    python3 layout/adc-top/parasitics/gen_extracted_core_tb.py --top ADC_BLOCK

Why this is possible at all -- the extracted `ADC_TOP` maps cleanly onto
`gen_adc_top.py`'s own per-tag net-naming convention:

| extracted `ADC_TOP` pin | schematic net (`_core()`, tag `t`, side `s`) |
|---|---|
| `hi_<w>_<s>` / `lo_<w>_<s>` / `rel_<w>_<s>` | `t_sel_hi_n_<w><s>` / `t_sel_lo_n_<w><s>` / `t_rel_n_<w><s>` |
| `sel_in` | `t_sel_in_n` (one broadcast net, both sides) |
| `tp_gn` | `t_samp_tp_n` (one broadcast net, both sides) |
| `topp` / `topn` | `t_topp` / `t_topn` (the comparator's own inputs) |
| `vinp` / `vinn` (promoted by `remediate_extracted.py`) | `t_pinp` / `t_pinn` (post-R_s/C_pin node) |
| `vcm` / `vref` / `vss` / `vsubs` | `vcmn` / `vrefn` / `0` / `0` (shared, not tag-prefixed) |
| `vdd` | `vddd` (one of the three supply rails `_preamble()` already declares) |

Every one of those is the SAME net a schematic-core deck's controller /
input-drive-network / comparator already drives, by construction: `_wire_pin`
below is a literal restatement of `_ports_ctrl_analog()`'s own naming rule
(`design/sar-logic/gen_sar_logic.py`), not a new convention. No renaming
layer, so a wiring bug here cannot silently point at the wrong controller
net -- an unrecognised pin name raises instead of guessing.

**`ADC_BLOCK` (issue #89 Scope item 2's comparator-inclusive follow-up,
`sim/extracted-delta-summary.md` §6.4).** The physical layout draws the
comparator INSIDE `ADC_BLOCK`'s boundary (`layout/adc-top/parasitics/
README.md` "What was extracted"), so its `.SUBCKT` exposes `cmpclk` /
`dout` / `doutb` / `ibias` where `ADC_TOP` exposes nothing -- those four
pins map onto exactly the four wires a schematic-level comparator instance
would otherwise carry between the controller and the array (the strobe, the
two digital outputs, the bias current), so wiring `ADC_BLOCK` replaces
`_core_extracted()`'s separate `X<tag>cmp ... comparator` instantiation with
a direct connection, rather than adding a second, redundant comparator on
top of the one the extraction already contains. `topp`/`topn` remain real
pins on `ADC_BLOCK` too (the physical layout still brings the CDAC-to-
comparator analog node to the block boundary for testability), so the ideal
shadow-DAC error node (`shadow_dac_and_error`) reads exactly the same nets
either way -- no separate formula for the two `--top` choices.

Issue #118 adds two more `ADC_BLOCK`-only pins, `XCMP.pop` / `XCMP.pon` --
the comparator's two load-resistor terminals, promoted to top-level pins
purely because they now carry a Metal1 label (an LVS-disambiguation device
for `klt lvs`'s `NetlistComparer`, not a real hierarchical port -- see
`gen_comparator.draw_load_resistors`'s docstring). `_wire_pin()` gives each
its own dedicated, otherwise-unused net (`{tag}_xcmp_pop`/`{tag}_xcmp_pon`)
rather than mapping it onto any other wire.

What this buys, and what it deliberately does not:

- **Buys**: a real, `ADC_TOP`- or `ADC_BLOCK`-instantiated conversion chain
  that a smoke test (`verify_extracted_core_conversion.py`, this directory)
  can actually run a transient simulation against and read a decoded code
  back from -- the concrete substrate Scope items 1-2 (the full #13 PVT
  bench, the #14 Monte Carlo) need before they can start.
- **Does not buy**: any spec-line claim. This module only composes text; it
  makes no measurement and records no result. See
  `verify_extracted_core_conversion.py` for the (deliberately narrow) claim
  this increment DOES substantiate.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

# --- reuse gen_adc_top.py (and, through it, gen_sar_logic.py) without ------
# --- retyping the comparator / SAR-controller / preamble wiring -----------
_GEN_ADC_TOP = REPO / "design" / "adc-top" / "gen_adc_top.py"
_spec = importlib.util.spec_from_file_location("gen_adc_top", _GEN_ADC_TOP)
gtop = importlib.util.module_from_spec(_spec)
sys.modules["gen_adc_top"] = gtop
_spec.loader.exec_module(gtop)  # type: ignore[union-attr]

import remediate_extracted as R  # noqa: E402  (same directory)

#: The tag every net this module emits carries, matching `_core()`'s own
#: convention (`design/adc-top/gen_adc_top.py`).
TAG = "ex"

_LEG_PIN = re.compile(r"^(hi|lo|rel)_(\d+)_([pn])$")
_LEG_PORT = {"hi": "sel_hi_n", "lo": "sel_lo_n", "rel": "rel_n"}

#: Every SINGLE-NODE `v(<node>)` / `i(<source>)` reference in a manifest's
#: `analyses` or `measure` text. Used by :func:`saved_vectors_lines` to derive
#: the exact `.save` set a deck needs -- deliberately derived, not hand-listed,
#: so a manifest that grows a measurement cannot leave the deck saving too
#: little.
#:
#: **Single-node only, on purpose, and guarded** -- see
#: `_VECTOR_REF_UNSUPPORTED` below. ngspice also accepts a differential
#: `v(a,b)` and a `par('<expr>')` wrapper; neither shape matches here, so
#: extending this pattern is the only correct way to support them. Adding one
#: to a manifest without extending it would drop the vector out of the derived
#: `.save` set SILENTLY at generation time, and the deck would then fail at run
#: time with ngspice's "no such vector" and a missing measurement -- a
#: confusing failure a long way from its cause. `measured_vectors()` raises
#: instead (issue #131).
_VECTOR_REF = re.compile(r"\b([vi])\s*\(\s*([A-Za-z_][\w.$#\[\]]*)\s*\)", re.I)

#: The two vector forms `_VECTOR_REF` deliberately cannot express: ngspice's
#: differential `v(a,b)` and its `par('<expr>')` expression wrapper. Matched
#: only to REFUSE, never to parse -- see `measured_vectors()`.
_VECTOR_REF_UNSUPPORTED = re.compile(
    r"\bv\s*\(\s*[A-Za-z_][\w.$#\[\]]*\s*,"  # differential v(a,b)
    r"|\bpar\s*\(",  # par('<expr>')
    re.I,
)


def measured_vectors(manifest: dict) -> list[str]:
    """The `v(...)`/`i(...)` vectors a manifest actually reads, sorted.

    `manifest` is one of `gen_adc_top.{inl,fft,power}_manifest()` -- the same
    object that writes the committed `sim/adc-*/testbench/tb.json` -- or a
    committed `tb.json` loaded verbatim (`gen_extracted_dr0014_sampling_tb.py`),
    so this cannot drift from the manifest the run uses.

    Raises `ValueError` if the manifest uses a vector form `_VECTOR_REF` cannot
    express (differential `v(a,b)`, `par('<expr>')`). Failing loudly HERE, at
    generation time, is the point: the alternative is a `.save` set that is
    silently missing a vector the run needs, which only surfaces later as
    ngspice's "no such vector" and a measurement that never lands.
    """
    text = "\n".join(
        list(manifest.get("analyses", ()))
        + [str(v) for v in manifest.get("measure", {}).values()]
    )
    bad = _VECTOR_REF_UNSUPPORTED.search(text)
    if bad:
        raise ValueError(
            f"manifest uses the vector form {bad.group(0).strip()!r}, which "
            "_VECTOR_REF does not match -- a differential v(a,b) or a "
            "par('<expr>') reference would fall out of the derived .save set "
            "silently and the measurement would then fail at run time with "
            "ngspice's 'no such vector'. Extend _VECTOR_REF (and this guard) "
            "to cover the new form rather than letting the vector drop."
        )
    seen = {f"{kind.lower()}({name})" for kind, name in _VECTOR_REF.findall(text)}
    return sorted(seen)


#: Why the `sim/adc-*` extracted decks carry a `.save`. Split out from
#: :func:`saved_vectors_lines` so a deck whose reason DIFFERS can state its own
#: (the `rationale=` argument) rather than emit a rationale that is not true of
#: it -- the committed deck is evidence, and a false explanation in it is a
#: false claim. Default text is byte-for-byte what
#: `gen_extracted_{inl_dnl,enob_fft,power}_tb.py`'s committed decks already
#: carry, and must stay that way unless those three are re-run.
_RATIONALE_EXTRACTED_CORE = (
    "* ngspice keeps a transient waveform for EVERY node unless told which",
    "* ones matter. The in-path extraction splits every net into one leg",
    "* node per device terminal, so the full store overruns what ngspice",
    "* will allocate and the point dies before measuring anything. These",
    "* are exactly the vectors this deck's manifest reads, derived from it",
    "* rather than hand-listed. Retention only: no model, tolerance or",
    "* timestep changes, and the measurements are bit-identical with and",
    "* without this line. See gen_extracted_core_tb.saved_vectors_lines.",
)


def saved_vectors_lines(
    manifest: dict, rationale: tuple[str, ...] | list[str] | None = None
) -> list[str]:
    """`.save` + why, for an extracted ADC deck.

    **Why this is load-bearing, not an optimisation.** The star-split in-path
    extraction (`klayout-tools#593`, this repo's `layout/toolchain.json`
    `875eac3` pin) gives every device terminal on a net its own `__t<k>` leg
    node -- ~4256 new nodes on `ADC_TOP` -- and ngspice keeps a full transient
    waveform for every node in the circuit unless told otherwise. Measured on
    `adc-inl-dnl` (20 us at 2 ns max step) that store is 260 822 400 B, and
    ngspice refuses to allocate it:

        Error: memory required (260822400 Bytes)
               is more than memory available (253485056 Bytes)!
        Setting the output memory is not possible.

    killing the point before a single measurement is taken. On a 16 GB host
    every point of the 63-point grid died this way at `-j 6`, and 51 of 63 at
    `-j 4` -- the reported "available" figure collapses as concurrent points
    allocate, so the failure is load-dependent and would come and go rather
    than stay honestly broken. The 66 us `adc-enob-fft` deck is ~3.3x worse
    again.

    `.save` fixes the cause rather than the symptom: these manifests read
    between three and six vectors (see :func:`measured_vectors`), so storing
    only those cuts the run's peak RSS to 37 MB and lets the grid run at
    whatever `-j` the host's CPUs justify.

    **It cannot change a result.** `.save` selects which waveforms are
    RETAINED; it does not touch the circuit, the models, the tolerances or
    the timestep sequence. Verified directly on `tt_27c_3.30v`: the same
    point run with and without it returns bit-identical measurements
    (`m_gain_err_lsb = -1.988646536e+00` either way).

    Fragment-legal, and deliberately emitted HERE rather than added to
    `sim/adc-*/testbench/tb.json`: `sim/harness/testbench.py`'s
    `FORBIDDEN_DIRECTIVES` bans `.control`/`.end`/`.lib`/`.temp`/`.include`
    in a fragment but not `.save`; and the manifests are byte-for-byte
    guarded against `design/adc-top/gen_adc_top.py` by
    `sim/tests/test_adc_top_netlist.py` AND shared with the schematic decks,
    which do not need this and whose records must stay reproducible from an
    unmodified manifest. The need is a property of the extracted core's node
    count, so it belongs with the core -- where anyone re-running the deck
    picks it up without having to remember a CLI flag, and where
    `sim/tests/test_extracted_decks_current.py` will flag it stale if the
    manifest's vector set ever moves underneath it.

    `rationale` overrides the explanation comment block ONLY (never the
    derived `.save` line). Default is `_RATIONALE_EXTRACTED_CORE` above --
    the text the three committed `sim/adc-*` decks already carry. A caller
    whose deck carries a `.save` for a DIFFERENT reason passes its own, rather
    than emitting an extraction-node-count rationale that is not true of it;
    a committed deck is evidence, and a false explanation inside one is a
    false claim (CLAUDE.md, "Work in the open").
    """
    vectors = measured_vectors(manifest)
    if not vectors:  # pragma: no cover - every ADC manifest reads something
        raise ValueError("manifest reads no v()/i() vectors -- refusing to .save nothing")
    return [
        "* ---- retained waveforms --------------------------------------------",
        *(_RATIONALE_EXTRACTED_CORE if rationale is None else rationale),
        ".save " + " ".join(vectors),
    ]


def _wire_pin(pin: str, tag: str = TAG) -> str:
    """The net one extracted-core `.SUBCKT` pin connects to in this deck.

    Structural, not name-guessed: every branch below is asserted against the
    actual pin set `remediate_extracted.parse()` returns (see
    `_core_extracted`), and an unrecognised pin raises rather than being
    silently dropped or misconnected.
    """
    if pin == "vinp":
        return f"{tag}_pinp"
    if pin == "vinn":
        return f"{tag}_pinn"
    if pin in ("topp", "topn"):
        return f"{tag}_{pin}"
    if pin == "sel_in":
        return f"{tag}_sel_in_n"
    if pin == "tp_gn":
        return f"{tag}_samp_tp_n"
    if pin == "cmpclk":
        # The SAME global strobe net `_preamble()` already drives
        # (`vcmpclk cmpclk 0 pulse(...)`) -- `ADC_BLOCK`'s baked-in
        # comparator uses the identical net name, no renaming needed.
        return "cmpclk"
    if pin == "dout":
        # ADC_BLOCK-only: the extracted comparator's own decision output,
        # wired directly onto the controller's `cmp` port -- see
        # _core_extracted()'s ADC_BLOCK branch, which omits the separate
        # schematic `X<tag>cmp` instance this net would otherwise come from.
        return f"{tag}_cmp"
    if pin == "doutb":
        # ADC_BLOCK-only: the complementary decision output. No net in this
        # harness reads `cmpb` (sar_ctrl_a's own port list has no such pin --
        # design/sar-logic/gen_sar_logic.py's _ports_ctrl_analog()), so this
        # is wired to a dedicated node for probing/consistency, matching the
        # schematic comparator's own unused `{tag}_cmpb` net at the ADC_TOP
        # wiring site.
        return f"{tag}_cmpb"
    if pin in ("XCMP.pop", "XCMP.pon"):
        # ADC_BLOCK-only, issue #118: the comparator's two load-resistor
        # terminals (`pop`/`pon`) now carry a Metal1 label purely to give
        # `klt lvs`'s NetlistComparer a same-named net to pair -- see
        # `gen_comparator.draw_load_resistors`'s docstring. That is an
        # LVS-disambiguation device, not a real hierarchical port: nothing
        # outside the comparator ever needs to drive or read this node, so
        # it gets its own dedicated, otherwise-unused net here rather than
        # a case that maps it onto some OTHER wire (which would silently
        # create a connection this design does not have).
        return f"{tag}_{pin.replace('.', '_').lower()}"
    if pin == "ibias":
        # ADC_BLOCK-only: the extracted comparator's own bias-current pin,
        # fed by the same 10 uA ideal source _core_extracted() already
        # instantiates for the ADC_TOP+external-comparator wiring.
        return f"{tag}_ibias"
    if pin == "vcm":
        return "vcmn"
    if pin == "vref":
        return "vrefn"
    if pin in ("vss", "vsubs"):
        return "0"
    if pin == "vdd":
        # One of the three supply rails `_preamble()` already declares
        # (vddt/vddd/vddc); ADC_TOP is drawn as a single vdd rail, so there
        # is no per-block current attribution to preserve here (that is the
        # #13 power deck's job, Scope item 1, deferred) -- any of the three
        # is electrically identical. vddd is chosen because ADC_TOP's
        # dominant device count is the CDAC bottom-plate switch network,
        # which vddd names in the schematic.
        return "vddd"
    m = _LEG_PIN.match(pin)
    if not m:
        raise ValueError(
            f"unrecognised extracted-core pin {pin!r} -- _wire_pin() does not "
            "know how to wire it; add a case rather than skip it."
        )
    leg, w, s = m.group(1), m.group(2), m.group(3)
    return f"{tag}_{_LEG_PORT[leg]}_{w}{s}"


def shadow_dac_and_error(tag: str = TAG, gated: bool = False) -> list[str]:
    """Ideal shadow DAC, input-referred error node, and (optionally) the
    strobe-gated |err| node the #13 static-linearity manifest reads.

    Copied verbatim (same variable names, same formula) from the shadow-DAC
    block inside `gen_adc_top._core()` -- see that function's own comments
    for the full charge-conservation derivation. Not re-derived here: the
    only reason this is possible at all is that `_wire_pin()` above already
    drives the extracted core's `.SUBCKT` pins onto THE SAME net names
    `_core()`'s formula expects (`{tag}_rel_n_<w><s>`,
    `{tag}_sel_hi_n_<w><s>`, `{tag}_sel_in_n`, `{tag}_vin<s>`,
    `{tag}_topp`/`{tag}_topn`).

    `_core_extracted()` deliberately omits this block: a "the extracted core
    converts" smoke test does not need it. Anything making an INL/DNL or
    gain-error CLAIM does, because the claim is defined as a difference
    against this ideal shadow -- so it lives here, next to the wiring it
    depends on, and is emitted by the callers that make such a claim
    (`measure_extracted_gain_err.py`, `probe_gain_err_settling.py`,
    `mc_extracted_core.py`).

    `gen_extracted_inl_dnl_tb.py` (PR #97) carries its own `_shadow_dac_lines()`
    copy of the same block rather than calling this one. That duplication is
    deliberate for now: its emitted fragment is pinned byte-for-byte by
    `--check` against the committed
    `sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice`, and the
    committed record `20260805-203322-3b6d7b7` was produced from those exact
    bytes. Collapsing the two emitters is a follow-up that must regenerate the
    fixture, not a drive-by edit inside an evidence PR.

    `gated=True` emits the strobe-gated `|err|` node the #13 manifest reads;
    no caller in-tree needs it yet (the INL/DNL deck emits its own), but it is
    kept here so the next extracted-core bench that does need it has one
    emitter to call rather than a third copy of the formula.
    """
    L: list[str] = []
    a = L.append
    a("* ---- ideal shadow DAC + error node (issue #89 Scope items 1/3/8) ----")
    a("* Verbatim formula from gen_adc_top._core() -- see that function for")
    a("* the charge-conservation derivation. Wired onto the SAME per-weight")
    a("* nets gen_extracted_core_tb._wire_pin() already drives.")
    for s in ("p", "n"):
        terms = [
            f"{w}*((v({tag}_rel_n_{w}{s})*vcm+v({tag}_sel_hi_n_{w}{s})*vref"
            f"+v({tag}_sel_in_n)*v({tag}_vin{s}))/vdd_val-vcm)"
            for w in gtop.WEIGHTS
        ]
        L += gtop.sar._wrap(
            f"b{tag}dac{s} {tag}_dac{s} 0 V = (1.0/512)*(",
            [" + ".join(terms) + " )"],
        )
    a(
        f"b{tag}di {tag}_di 0 V = v({tag}_vinn)-v({tag}_vinp)"
        f"+v({tag}_dacp)-v({tag}_dacn)"
    )
    a(
        f"b{tag}e {tag}_err 0 V = (v({tag}_di)-(v({tag}_topp)-v({tag}_topn)))"
        f"/lsb"
    )
    if gated:
        a("* |err| gated to the ten comparator-strobe windows -- verbatim from")
        a("* gen_adc_top._core(); MAX over a trial window is that conversion's")
        a("* WORST DECISION ERROR. Gating, not holding: see _core()'s own note")
        a("* on why a track-and-hold reported the settling transient instead.")
        a(f"b{tag}ea {tag}_aerrh 0 V = abs(v({tag}_err))*(v(cmpclk)>vth ? 1 : 0)")
    return L


def core_pins(top: str = "ADC_TOP") -> tuple[list[str], str]:
    """`(pins, remediated_subckt_text)` for the latest committed extraction.

    Delegates entirely to `remediate_extracted.py`: this module trusts that
    script's own safety assertions (PMOS-body rewrite exclusivity, structural
    input-rail identification) rather than re-deriving them.
    """
    src = R._latest_report(top)
    core_text, rem = R.remediate(src.read_text(), top)
    nl = R.parse(core_text, top)
    assert rem.n_pmos_rewritten > 0 and len(rem.input_rails) == 2, (
        "remediation invariants did not hold for the latest extraction -- "
        "refusing to wire an unremediated core"
    )
    return nl.pins, core_text


def _core_extracted(tag: str, mode: str, pins: list[str], top: str) -> list[str]:
    """One extracted-core conversion chain.

    Identical wiring to `gen_adc_top._core()` for the controller, the
    DR-0013 input drive network, the comparator, and the decoded-code node --
    those are schematic-level per Scope item 0 and are reused unmodified in
    spirit (same net names, same subckt calls). The ONLY thing that differs
    is the analog core itself: one `Xdut ... <top>` call in place of
    `_core()`'s two `adc_cdac_side` instances plus its two `adc_tp_sw`
    instances -- because the extracted layout drew both array sides AND the
    per-side top-plate switch inside the same flat block (296 FETs = 288
    switch/driver FETs + 8 top-plate-switch FETs, `parasitics/README.md`
    "What was extracted").

    `top == "ADC_BLOCK"` additionally bakes the comparator into that one
    `Xdut` call (`README.md` "What was extracted": 1347 devices = the
    `ADC_TOP` 296 + the comparator's own ~1051, `cells.json`'s `adc_block`
    row) -- so this function emits the bias-current source that feeds
    `Xdut`'s `ibias` pin either way, but omits the separate schematic
    `X<tag>cmp ... comparator` instance for `ADC_BLOCK` (its `dout`/`doutb`
    pins, wired by `_wire_pin` onto the SAME `{tag}_cmp`/`{tag}_cmpb` nets
    that instance would otherwise drive, already supply the controller's
    decision input -- instantiating both would put two comparators on one
    net).

    Deliberately OMITTED relative to `_core()`: the ideal-shadow DAC and the
    LSB-referred error node. Those exist to support an INL/DNL CLAIM
    (Scope item 1, deferred); this harness's own claim is narrower --
    "the extracted core converts" -- and is checked directly against the
    decoded code, so the shadow DAC is not needed to make it.
    """
    L: list[str] = []
    a = L.append
    mode_word = "differential" if mode != "0" else "single-ended"
    a(f"* ================= extracted core {tag} ({mode_word}) ==================")
    a(f"v{tag}start {tag}_start 0 dc 0")
    a(f"v{tag}mode {tag}_mode 0 dc {mode}")

    # --- controller (rung 1) -- identical wiring to gen_adc_top._core() -----
    ports = [f"{tag}_{p}" for p in gtop.sar._ports_ctrl_analog()]
    ports[0] = "clk"
    ports[1] = f"{tag}_start"
    ports[2] = f"{tag}_mode"
    ports[3] = f"{tag}_cmp"
    L += gtop.sar._wrap(f"x{tag}ctrl", ports + ["sar_ctrl_a"])

    # --- input drive network, DR-0013 -- identical to gen_adc_top._core() ---
    a("* Input drive network (DR-0013), same R_s/C_pin gen_adc_top._core()")
    a("* uses for the schematic core -- the drive contract is unchanged by")
    a("* which core sits behind it.")
    for s in ("p", "n"):
        a(f"R{tag}s{s} {tag}_vin{s} {tag}_pin{s} {gtop.TRACK_RS_OHM}")
        a(f"C{tag}x{s} {tag}_pin{s} 0 {gtop.TRACK_CPIN}")

    # --- the extracted analog core (issue #89 Scope item 0) ------------------
    a(f"* {top}: both CDAC array sides (four-leg bottom-plate switches, local")
    a("* drivers) and the per-side top-plate V_cm switch (DR-0014), all in ONE")
    a("* flat extracted instance, PMOS-body-remediated and MiM-mapped to the")
    a("* native PDK subckt (layout/adc-top/parasitics/remediate_extracted.py).")
    if top == "ADC_BLOCK":
        a("* Comparator is INSIDE this extraction (Scope item 2's")
        a("* comparator-inclusive follow-up); only the controller stays")
        a("* schematic-level.")
    else:
        a("* Comparator and controller stay schematic-level (Scope item 0).")
    dut_nets = [_wire_pin(p, tag) for p in pins]
    L += gtop.sar._wrap("Xdut", dut_nets + [top])

    # --- comparator bias current -- always needed: for ADC_TOP it feeds the
    # separate schematic X<tag>cmp instance below; for ADC_BLOCK it feeds
    # Xdut's own `ibias` pin directly (wired by _wire_pin above).
    a(f"i{tag}b vddc {tag}_ibias dc 10u")
    if top != "ADC_BLOCK":
        # --- comparator -- identical wiring to gen_adc_top._core() -----------
        a(
            f"X{tag}cmp {tag}_topp {tag}_topn cmpclk {tag}_ibias {tag}_cmp"
            f" {tag}_cmpb vddc 0 comparator"
        )

    # --- decoded output code (the parallel register, DR-0005) ---------------
    terms = [f"({2 ** b})*(v({tag}_c{b})>vth ? 1 : 0)" for b in range(9, -1, -1)]
    L += gtop.sar._wrap(f"b{tag}code {tag}_code 0 V = ", [" + ".join(terms)])
    return L


def library_and_core(top: str = "ADC_TOP") -> tuple[str, list[str]]:
    """`(text, pins)`: the comparator + SAR-controller library, the extracted
    core's own `.SUBCKT`, and one wired conversion chain, ready to append
    after `gtop._preamble(...)` and a stimulus source.
    """
    pins, core_text = core_pins(top)
    body = "\n".join(_core_extracted(TAG, "0", pins, top)) + "\n"
    lib = (
        gtop.comparator_block()
        + "\n"
        + gtop.sar.library()
        + "\n"
        + core_text
        + "\n"
    )
    return lib + "\n" + body, pins


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--top", default="ADC_TOP", choices=["ADC_TOP", "ADC_BLOCK"],
        help="ADC_TOP keeps the comparator schematic-level (Scope item 0's "
             "own wording); ADC_BLOCK bakes the comparator INTO the "
             "extracted core too (its .SUBCKT exposes cmpclk/dout/doutb/"
             "ibias pins, wired directly onto the controller -- see "
             "_core_extracted()'s ADC_BLOCK branch) for the "
             "comparator-inclusive follow-up (sim/extracted-delta-summary.md "
             "SS6.4).",
    )
    args = ap.parse_args(argv)
    text, pins = library_and_core(args.top)
    sys.stdout.write(f"* {len(pins)} extracted-core pins wired, tag={TAG!r}\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
