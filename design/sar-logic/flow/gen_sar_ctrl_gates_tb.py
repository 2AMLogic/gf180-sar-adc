#!/usr/bin/env python3
"""Generate the gate-level SAR-sequencer functional/timing replay testbenches
(issue #273 -- DR-0023 follow-on (a)'s own follow-on, filed from #272's PR).

#272 landed the RTL (`../rtl/sar_ctrl.v`), the `klt synthesize` flow, both
gate netlists, and the translator this script depends on
(`gate_netlist_to_spice.py`), but deliberately deferred the "load-bearing"
half of that work: actually replaying the closed-loop functional/timing
testbenches against the *synthesized* netlist instead of the ideal
rung-1 XSPICE model. This script builds that replay.

Single source of truth for two committed artifacts:

  sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice
  sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice

It does not reimplement the closed-loop composition or the translation --
both already exist and are reused directly:

  - `gen_sar_logic.py`'s `_functional_body`/`_timing_body` -- the SAME
    controller + behavioural-CDAC + comparator loop, one-hot invariant,
    two-phase-sample duty-cycle instrument and code-error checks the ideal
    rung-1 decks use, now accepting `dut_subckt` (which subckt each loop
    instantiates in place of the ideal `sar_ctrl_a`) and `start_pulse_clocks`
    (see both functions' docstrings, and "Seeding `start`" below).
  - `gate_netlist_to_spice.translate()` -- turns the committed
    `sar_ctrl.<lib>.synth.v` gate netlist into a flat SPICE `.subckt` named
    `sar_ctrl_a`, with the SAME 71-net port order as the ideal model it
    replaces (`../rtl/sar_ctrl.v`'s own port-compatibility requirement,
    `../rtl/README.md`) -- so `_loop`'s existing `x<tag> ... sar_ctrl_a`
    instantiation line needs no other change to wrap the real netlist.

Which library: `../rtl/README.md` names `gf180mcu_fd_sc_mcu7t5v0` as the
*chosen* library (smaller, more P&R headroom against the reserved SAR-logic
footprint) and explicitly says the gate-level replay "should run against
this chosen library's netlist only" -- running both would double the
replay's already-substantial simulation cost (see below) for a library this
design does not build against, and the two netlists are already proven
register-correspondence equivalent to the same RTL (#272's `klt equiv`
records), so a functional divergence between them is not a possibility
either replay could newly discover.

## Seeding `start`

`../rtl/README.md`'s "Real hardware note" is explicit: a real standard-cell
flip-flop (`dffq_1` in both libraries) carries no reset pin at all, so
`sar_ctrl.v`'s `ph` ring powers up in an arbitrary state rather than the
rung-1 ideal model's `ic=1`-seeded one-hot state. `start` must be asserted
for at least one whole clock after power-up before any other output can be
trusted. `START_PULSE_CLOCKS` below drives `start` high with a `pwl` ramp
(not an ideal step -- a real transistor gate should not be asked to chase a
literal discontinuity) from t=0 for that many whole clock periods before
dropping it back to 0 for the remainder of the run, comfortably exceeding
the "at least one clock" the README requires so the very first sampled edge
is not also the edge `start` itself is transitioning on.

## Comparator output slew (issue #296)

`gen_sar_logic._loop`'s comparator is an ideal behavioural voltage source
whose VALUE is a hard ternary on `v(top_p) > v(top_n)` -- it steps
rail-to-rail in literally zero time. That is harmless in the rung-1 ideal
decks (the XSPICE `cmp` bridge presents no analog load at all) and harmless
in this deck's three DELAYED timing loops (`lt`/`xl`/`bad`, whose `t...d`
transmission line presents a matched 50 ohm resistive load). It is NOT
harmless when the same source drives the `cmp` gate input of a *real*
synthesized standard cell, which is a pure capacitance: the source's own
branch current is then `i = C dV/dt` with `dV` fixed at `vdd_val`, so `i`
grows without bound as the step shrinks. ngspice's adaptive step control has
no way out of that -- the discontinuity is exactly as large at `h = 6.25e-21`
as it was at `h = 5e-9` -- and it halves the step to its floor and aborts
with `Timestep too small ... trouble with node "b<tag>cmp#branch"`.

Measured, not assumed (issue #296's own instrumentation, on
`sim/sar-logic-timing-gates/` @ `tt_27c_3.30v`): the run aborts at
t = 11.66 ps with `v(tie_topp)` and `v(tie_topn)` equal to ten printed
digits and converging on each other -- i.e. right on the `tie` loop's
comparator crossing, with a differential slope near zero, which is exactly
the case a zero-time step function cannot be stepped over. Across all 45
points of #289's grid the trouble node is ALWAYS one of `bokcmp` / `btiecmp`
(the two loops whose comparator drives the DUT gate input directly) or a
collateral ideal source in the same block (`vtiemode` / `vltmode`) -- and
NEVER `bltcmp` / `bxlcmp` / `bbadcmp`, the three that drive the 50 ohm
terminated line. That contrast is the confirmation.

`CMP_OUT_RC` therefore interposes a first-order output network on the
undelayed comparators only, leaving the hard decision itself -- and all
three delayed loops -- exactly as they were.

A SOFT comparator (a narrow high-gain/`tanh` transition band instead of the
ternary) was prototyped first and REJECTED on measurement: it does move the
abort from t = 11.66 ps to t = 112.6 ps, but it then aborts with
`trouble with node "vvdd_gate#branch"`, because it makes the `tie` loop's
comparator output sit *statically* near mid-rail, holding real standard-cell
inputs in their linear region. That converts a numerical problem into a
physical one, and it also silently changes what the `tie` loop claims: the
loop exists to show that a near-metastable comparator input still yields a
conversion that COMPLETES on schedule, which presupposes a comparator that
always resolves to a rail. Keeping the hard ternary and slewing only its
output preserves that.

## Why the exhaustive functional sweep does NOT run at nconv=1024 here

`sim/sar-logic-functional/`'s ideal-XSPICE sibling converts 1024 times (one
per code) because XSPICE digital primitives cost the same whether the deck
"does something" that instant or not. A synthesized gate netlist is real
gf180mcu 6 V-oxide transistors (`nfet_06v0`/`pfet_06v0`, ~15 devices per
standard cell, 181 cells for `mcu7t5v0` -- one per closed loop), and ngspice
transient analysis of a circuit that size is not free the way an XSPICE
event is. Measured directly while building this script, on the two-loop
(`se`+`df`) functional composition, nominal corner (`tt`/27 C/3.30 V):
**~7.9 s of wall-clock per simulated conversion** (31.5 s for a 4-conversion
probe). At `nconv=1024` that is ~2.25 **hours** for a single PVT point, which
would make the full ratified `mos` corner-set grid (5 process corners x 3
temperatures x 3 supplies = 45 points) cost on the order of **100 hours**
serial CPU-time even before accounting for the timing deck's own (larger,
see below) per-point cost -- not something a single verification pass can
run to completion.

`FUNCTIONAL_NCONV` below is deliberately reduced to keep the *whole ratified
corner grid* tractable rather than running the full 1024-conversion sweep at
only one or two PVT points and leaving most of the grid unswept -- the
corner-grid claim (does gf180mcu process/temperature/supply skew move any of
these numbers) is the one #273 was actually filed to answer, and the
grid coverage matters more here than per-point code-exhaustiveness that the
rung-1 ideal sibling (which runs unmodified, at full nconv=1024, on every
PR) already owns. The ramp still covers the SAME full range (half an LSB
above 0 through half an LSB above full scale, `_functional_body`'s own `pwl`
construction), just at a coarser step -- `1024 // FUNCTIONAL_NCONV` codes per
conversion instead of one -- so the coverage-witness checks (`code_se_max`/
`code_se_min` and their `df` counterparts) still exercise both ends of the
range, and the error/one-hot/mode/cadence checks still run on every
conversion actually taken. This is the same "documented, reasoned reduction
in coverage, not a relaxed pass/fail bound" this repo's own
`sim/README.md` "Subset-corner justification" convention blesses for PVT
subsets, applied here to conversion count instead: the record this script's
caller (`sim/run_corners.py`) produces states the reduction and the measured
cost that justifies it, per CLAUDE.md ("no claim without a testbench" cuts
both ways -- an infeasible claim is not owed a fabricated result either).

The timing deck's (`sim/sar-logic-timing-gates/`) 8.5 us duration and
5-loop (`ok`/`lt`/`xl`/`bad`/`tie`) *measurement* structure are NOT
shortened: they are fixed by the measurement definitions themselves
(`tie_conv_period_ns` needs `RISE=2`..`RISE=7` on `tie_drdy`, i.e. seven
whole conversions; the delay brackets are a bisected boundary, not swept).
Its cost is real too -- but issue #303/#311 measured that almost all of it
is NOT the five loops' own arithmetic (5x the one-loop cost would be
expected and is fine): it is that all five loops used to share ONE deck and
therefore one ngspice clock-sharing global timestep, so their combined
circuit saw near-continuous switching activity rather than each loop's own
quieter, well-separated edges -- measured at up to two orders of magnitude
slower than a single loop's own per-ns cost
(`sim/sar-logic-timing-gates/investigations/
20260917-issue-303-five-loop-composition-cost.md`).

## Per-loop timing decomposition (issue #311)

Nothing in the five loops' measurement definitions requires them to share
one deck -- each owns its own `sar_ctrl_a` instance, behavioural CDAC/
comparator and stimulus, and shares only the `clk` stimulus source and the
`.global vdd_gate` supply with the others. `timing_gates()` above therefore
now accepts `loop_tags` (forwarded to `gen._timing_body`), and `TARGETS`
below adds one `timing-gates-<tag>` target per tag in
`gen.TIMING_LOOP_TAGS` (`ok`/`lt`/`xl`/`bad`/`tie`) alongside the original,
unchanged five-loop `timing-gates` target.

**Evidence-tree shape, decided**: five experiment slugs
(`sim/sar-logic-timing-gates-ok/`, `-lt/`, `-xl/`, `-bad/`, `-tie/`), each
carrying its own `testbench/tb.json` with only the measurements/checks that
read its own loop's nodes -- NOT a deck-variant axis on the existing
`sim/sar-logic-timing-gates/` manifest. Chosen over the axis alternative
because `sim/harness/testbench.py`'s manifest schema has no notion of
"more than one netlist fragment per experiment" today (one `tb.json` names
exactly one `netlist`); a deck-variant axis would mean teaching the shared
harness (`Testbench`, `run_corners.py`, the record writer) a new
composition primitive general enough not to be special-cased to this one
block, which is a harness-design decision with its own review, not a
byte-for-byte-safe generator change. Five slugs need none of that -- every
existing harness code path (`sim.harness.testbench.load`, `run_corners.py`,
the `records/`/`corners/`/`netlist-snapshots/` layout) already handles
"one experiment, one deck" and needs no change to run the split decks.
The ORIGINAL five-loop `sim/sar-logic-timing-gates/` experiment (and its
already-committed 0-of-45 record from issue #289) is kept, unchanged, as
the full-composition deck used for the nominal-PVT cross-check against the
split decks (issue #311's acceptance criteria) -- it is not deleted or
repurposed, and its `records/`/`corners/`/`netlist-snapshots/` stay exactly
as issue #289 left them (append-only, `sim/README.md`).

Usage:
    python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py            # write all files
    python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py --check    # exit 1 if stale
    python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py --stdout functional-gates
    python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py --stdout timing-gates-ok

Needs the gf180mcu PDK resolvable (`sim/harness/pdk.py`'s resolution order)
for the standard-cell SPICE library text `gate_netlist_to_spice.translate()`
reads -- it does NOT need `klt`/Yosys, since the gate netlist it wraps is
already committed (`../flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim.harness.pdk import Pdk, PdkNotFound, find_pdk  # noqa: E402

import gate_netlist_to_spice as g2s  # noqa: E402
import gen_sar_logic as gen  # noqa: E402

#: The chosen library, per ../rtl/README.md -- see module docstring.
LIBRARY = "gf180mcu_fd_sc_mcu7t5v0"
LIB_TAG = "mcu7t5v0"
NETLIST_PATH = REPO / "design" / "sar-logic" / "flow" / "sar_ctrl" / "netlist" / f"sar_ctrl.{LIB_TAG}.synth.v"
TOP = "sar_ctrl_a"

#: Internal net the translated subckt's power pins tie to -- driven by an
#: explicit `vdd_val`-referenced source appended after the subckt text (the
#: translated subckt has no power PORTS of its own, see
#: `gate_netlist_to_spice.py`'s "Power/ground convention").
SUPPLY_NET = "vdd_gate"
GROUND_NET = "0"

#: >=1 whole clock, per ../rtl/README.md's "Real hardware note" -- see module
#: docstring's "Seeding `start`". 2 clocks of margin, not the bare minimum of
#: 1, so the very first edge a check would actually measure is never also the
#: edge `start` itself last transitioned on.
START_PULSE_CLOCKS = 2

#: See module docstring's "Why the exhaustive functional sweep does NOT run
#: at nconv=1024 here" -- measured ~7.9 s/conversion (2-loop composition,
#: nominal corner); 64 keeps the full ratified `mos` corner grid tractable.
FUNCTIONAL_NCONV = 64

#: `(R, C)` for the UNDELAYED comparators' output network -- see
#: "Comparator output slew" below and `gen_sar_logic._loop`'s `cmp_out_rc`.
#: 1 kohm * 100 fF = 100 ps, i.e. a ~220 ps 10-90% output edge: the same
#: order as a gf180mcu 5 V standard cell's own output transition, and
#: 0.35 % of the 62.5 ns bit cycle these decks measure margins in.
CMP_OUT_RC = ("1k", "100f")

GENERATOR_PATH = "design/sar-logic/flow/gen_sar_ctrl_gates_tb.py"


class GateTbError(RuntimeError):
    """The PDK or the committed gate netlist did not have the expected shape."""


def _gate_subckt_text(pdk: Pdk) -> tuple[str, str]:
    """`(sar_ctrl_a_subckt_text, used_pdk_subckts_text)` -- see
    `gate_netlist_to_spice.translate`'s own docstring for the return shape.
    """
    spice_lib = pdk.path / "libs.ref" / LIBRARY / "spice" / f"{LIBRARY}.spice"
    if not spice_lib.is_file():
        raise GateTbError(
            f"standard-cell SPICE library not found at {spice_lib}\n"
            f"(expected the gf180mcu {LIBRARY} library -- check the PDK install / variant)"
        )
    if not NETLIST_PATH.is_file():
        raise GateTbError(
            f"gate netlist not found at {NETLIST_PATH} -- run "
            "design/sar-logic/flow/synth_sar_ctrl.py first (issue #272)"
        )
    return g2s.translate(
        NETLIST_PATH,
        spice_lib,
        subckt_name=TOP,
        supply_net=SUPPLY_NET,
        ground_net=GROUND_NET,
        expected_top=TOP,
    )


def _assemble(body: list[str], subckt_text: str, used_subckts_text: str) -> str:
    text = (
        "\n".join(body)
        + "\n\n"
        + subckt_text
        + "\n"
        + used_subckts_text
        + f"\nvvdd_gate {SUPPLY_NET} {GROUND_NET} dc {{vdd_val}}\n"
    )
    _assert_supply_is_globally_scoped(text)
    return text


def _assert_supply_is_globally_scoped(text: str) -> None:
    """The deck's single `vvdd_gate` source sits at the TOP level while every
    standard cell that draws from it sits inside `.subckt sar_ctrl_a` -- so
    `SUPPLY_NET` only actually connects the two if it is globally scoped.

    Issue #282: without that, SPICE gives each `sar_ctrl_a` instance its own
    private, undriven copy of the net and the whole DUT simulates as an
    unpowered network sitting at ~0 V -- which reads as a solver/power-up
    failure rather than as a wiring one. `gate_netlist_to_spice` emits the
    `.global` line (and has its own guard for it); this re-checks the
    property on the *assembled deck*, where it is actually load-bearing,
    because that is the artifact `sim/run_corners.py` consumes.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(".global") and SUPPLY_NET in stripped.split()[1:]:
            return
    raise GateTbError(
        f"assembled deck never declares `.global {SUPPLY_NET}` -- the top-level "
        f"vvdd_gate source would not reach the cells inside .subckt {TOP} "
        "(issue #282: the DUT would simulate unpowered at ~0 V)"
    )


def functional_gates(pdk: Pdk | None = None) -> str:
    pdk = pdk or find_pdk()
    subckt_text, used = _gate_subckt_text(pdk)
    body = gen._functional_body(
        FUNCTIONAL_NCONV,
        dut_subckt=TOP,
        start_pulse_clocks=START_PULSE_CLOCKS,
        generator_path=GENERATOR_PATH,
        cmp_out_rc=CMP_OUT_RC,
    )
    return _assemble(body, subckt_text, used)


def timing_gates(pdk: Pdk | None = None, *, loop_tags: tuple[str, ...] | None = None) -> str:
    """The gate-level timing-margin deck. `loop_tags` (default: all five,
    `gen.TIMING_LOOP_TAGS`) selects which loops this deck instantiates --
    see `gen._timing_body`'s docstring (issue #311). The default reproduces
    the original five-loop deck byte-for-byte.
    """
    pdk = pdk or find_pdk()
    subckt_text, used = _gate_subckt_text(pdk)
    body = gen._timing_body(
        dut_subckt=TOP,
        start_pulse_clocks=START_PULSE_CLOCKS,
        generator_path=GENERATOR_PATH,
        cmp_out_rc=CMP_OUT_RC,
        loop_tags=loop_tags or gen.TIMING_LOOP_TAGS,
    )
    return _assemble(body, subckt_text, used)


def _timing_gates_loop(tag: str):
    """Bind a single-loop `timing_gates` variant for `TARGETS` below --
    issue #311's per-loop decomposition (see that function's docstring)."""

    def _fn(pdk: Pdk | None = None) -> str:
        return timing_gates(pdk, loop_tags=(tag,))

    _fn.__name__ = f"timing_gates_{tag}"
    return _fn


TARGETS = {
    "functional-gates": (
        "sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice",
        functional_gates,
    ),
    "timing-gates": (
        "sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice",
        timing_gates,
    ),
}
#: Issue #311: one single-loop deck per tag, each its own experiment slug
#: (`sar-logic-timing-gates-<tag>/`) -- see sim/sar-logic-timing-gates/
#: investigations/20260917-issue-303-five-loop-composition-cost.md for why,
#: and this module's own header docstring / the PR that added this block for
#: the "five slugs vs one deck-variant axis" decision record.
for _tag in gen.TIMING_LOOP_TAGS:
    TARGETS[f"timing-gates-{_tag}"] = (
        f"sim/sar-logic-timing-gates-{_tag}/testbench/tb_sar_logic_timing_gates_{_tag}.spice",
        _timing_gates_loop(_tag),
    )
del _tag


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="exit 1 if any committed file differs from generated")
    p.add_argument("--stdout", choices=sorted(TARGETS), help="print one artifact instead of writing files")
    args = p.parse_args(argv)

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if args.stdout:
        rel, fn = TARGETS[args.stdout]
        sys.stdout.write(fn(pdk))
        return 0

    stale = []
    try:
        for name, (rel, fn) in sorted(TARGETS.items()):
            path = REPO / rel
            text = fn(pdk)
            if args.check:
                if not path.is_file() or path.read_text() != text:
                    stale.append(rel)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                print(f"wrote {rel}")
    except GateTbError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        for rel in stale:
            print(f"STALE: {rel}", file=sys.stderr)
        if stale:
            print(f"run: python3 {GENERATOR_PATH}", file=sys.stderr)
            return 1
        print("all generated gate-level testbenches are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
