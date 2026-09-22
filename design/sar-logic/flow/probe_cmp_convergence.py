#!/usr/bin/env python3
"""A/B instrument for issue #296's comparator non-convergence root cause.

Issue #289 ran the full ratified 45-point `mos` grid for
`sim/sar-logic-timing-gates/` and **0 of 45 points reached a scored result**:
every one aborted with

    doAnalyses: TRAN:  Timestep too small; time = ...: trouble with node
    "btiecmp#branch"  (or "bokcmp#branch" / "vtiemode#branch" / "vltmode#branch")

usually within tens of picoseconds of t=0. Issue #296 asked for that to be
**confirmed or refuted by actual instrumentation, not left as a guess**. This
script is that instrumentation, kept in the tree so an outside reader can
re-run the same A/B rather than take the conclusion on trust (CLAUDE.md,
"Work in the open").

## What it does

Composes exactly the deck `sim/run_corners.py` would compose for one PVT
point of one gate-level experiment (same `sim/harness` code path, same PDK
resolution, same corner sections), then optionally:

  --ideal-cmp   rewrite the committed testbench's comparator back to the
                PRE-#296 form -- the bare
                `b<tag>cmp <tag>_cmpo 0 V = v(<tag>_topp) > v(<tag>_topn) ?
                vdd_val : 0` driving the synthesized cell's gate input with
                no series element at all. This is the A side of the A/B.
  --until T     shorten the transient stop time (e.g. `--until 200n`), so a
                convergence question can be answered without paying for the
                whole ratified run. The measurement analyses in `tb.json` are
                NOT run in this mode -- this script answers "does the solver
                survive", not "what does the deck measure"; the latter is
                `sim/run_corners.py`'s job and only it writes evidence.
  --probe       print the comparator differential and output, timepoint by
                timepoint, right up to wherever the run stopped. This is the
                readout that settles the root cause.

It writes nothing under `sim/<slug>/records|corners|netlist-snapshots/` --
it is a debugging instrument, not an evidence writer.

## What it measured (issue #296, `sar-logic-timing-gates` @ tt/27C/3.30V)

    python3 design/sar-logic/flow/probe_cmp_convergence.py \
        sar-logic-timing-gates --ideal-cmp --probe
    -> ABORT at t = 1.16593e-11 s, trouble node btiecmp#branch
       ... with v(tie_topp) and v(tie_topn) equal to ten printed digits and
       still converging on each other: the `tie` loop's comparator is sitting
       exactly on its decision crossing, approaching it with a differential
       slope near zero.

    python3 design/sar-logic/flow/probe_cmp_convergence.py \
        sar-logic-timing-gates --until 200n
    -> completes, no abort.

That is the confirmation. The mechanism is NOT "ngspice cannot resolve a fast
edge" -- a fast edge is resolvable by taking a smaller step. It is that the
comparator B-source's value is a step function of the solution, so the jump it
imposes on the DUT's gate capacitance is `vdd_val` **no matter how small the
timestep is**: halving `h` does not make the discontinuity any smaller, which
is why the logs bottom out at `timestep = 6.25e-21` instead of recovering.

The corroborating contrast is in #289's own 45 logs and needs no new run: the
trouble node is always `bokcmp` / `btiecmp` (the two loops whose comparator
drives the DUT gate input directly) or a collateral ideal source in the same
block, and **never** `bltcmp` / `bxlcmp` / `bbadcmp` -- the three loops whose
comparator drives a matched 50 ohm terminated transmission line instead of a
bare gate capacitance.

See `gen_sar_ctrl_gates_tb.py`'s "Comparator output slew" section for the fix
this justified, and for the soft-comparator alternative that was prototyped
with this same script and rejected on measurement.

## The second wall, past 200 ns (issue #310)

#296's B side was only ever validated to `--until 200n`, which was enough to
clear every pre-#296 abort (the latest anywhere in #289's 45-point grid is
t = 1.566e-7 s). #303 then ran `tt`/27 C/3.30 V to its own natural
completion and hit a SECOND, distinct abort at t = 3.84657e-07 s, trouble
node `vvdd_gate#branch` -- the DUT supply branch, i.e. a node the five loops
SHARE, so unlike `b<tag>cmp#branch` the node name alone does not name a
loop. These flags were added here to isolate it:

  --only-loops ok,tie   keep only the named `* ---- loop <tag> ----` sections
                        of the composed testbench, dropping the rest. A
                        five-loop deck costs ~two orders of magnitude more
                        per simulated nanosecond than one loop (tb.json's own
                        "COMPUTATIONAL COST, MEASURED" note), so a per-loop
                        A/B that would otherwise cost ~50 min a point costs
                        seconds. NOTE the caveat this buys its speed with:
                        removing loops also removes their load on `vdd_gate`
                        and `clk`, so a subset deck is a DIFFERENT circuit --
                        use it to find WHICH loop carries the mechanism, then
                        confirm on the full deck. MEASURED SINCE (#311/PR
                        #321 landed the per-loop decomposition): for a SINGLE
                        tag the cut is not merely a proxy -- its circuit lines
                        are byte-for-byte the committed
                        `sim/sar-logic-timing-gates-<tag>/` deck, pinned by
                        `sim/tests/test_probe_cmp_convergence.py::
                        PerLoopExperimentTests`. Those five slugs are also
                        probeable directly, by name.
  --cmp-rc R,C          retune the #296 output network for THIS RUN ONLY,
                        e.g. `--cmp-rc 1k,10f`. #310 forbids silencing its
                        abort by loosening `cmp_out_rc`; it does not forbid
                        sweeping tau to find out whether the abort depends on
                        tau at all, which is the measurement that separates a
                        propagation-network mechanism from a circuit one.
                        Writes nothing -- the committed value stays whatever
                        `gen_sar_ctrl_gates_tb.py`'s `CMP_OUT_RC` says.
  --tail N              print only the last N rows of each probe table (the
                        rows next to the abort). Default 0 = every row, so
                        the #296 invocations above are unchanged.
  --chatter             print, per loop, the two numbers #310's investigation
                        actually reads: how many times the comparator's own
                        hard decision `v(<tag>_cmpd)` REVERSES between accepted
                        timepoints, and how long the DUT-facing `v(<tag>_cmpo)`
                        dwells in the standard cells' mid-rail switching band.
                        Computed over the whole run (independent of `--tail`)
                        so a reader re-derives the investigation's tables
                        instead of trusting transcribed rows.
  --spice-option K=V    append `.options K=V` to THIS RUN's deck only, e.g.
                        `--spice-option abstol=1e-10`. Repeatable. #310's
                        measured abort happens with the whole DUT quiescent
                        and every comparator output at a rail, on the one
                        matrix row that couples all five DUT instances
                        (`vvdd_gate#branch`), so the question "is this a
                        SOLVER-TOLERANCE failure on a near-zero branch current
                        rather than a circuit event?" is answerable only by
                        moving the tolerance and re-measuring. A solver option
                        is not a spec bound and not a `tb.json` check -- but
                        this flag still writes NOTHING: no manifest gains an
                        `options` entry from it.
  --probe (extended)    now also prints, per loop, the comparator's own
                        decision node `v(<tag>_cmpd)` NEXT TO the RC-filtered
                        node `v(<tag>_cmpo)` the DUT actually sees, plus the
                        shared `v(vdd_gate)` / `i(vvdd_gate)`. `cmpd` vs
                        `cmpo` is the whole question at `vvdd_gate#branch`:
                        a hard decision that is resolved at a rail on `cmpd`
                        but sitting mid-rail on `cmpo` is the rejected soft
                        comparator's static-crowbar mechanism arriving by a
                        different route, and `i(vvdd_gate)` says whether the
                        crowbar current is actually there or not.

## Measuring the sub-LSB-offset candidate (issue #322)

#310's investigation left the chatter itself unretired and named three
candidate responses, one of which -- "give the `tie` input a deterministic
sub-LSB offset (e.g. `vcm + 1 uV`) so the differential has a real sign
instead of a feedback artifact" -- is a claim about what the deck would
measure, and therefore had to be *measured* before being adopted or
rejected. This flag is how:

  --tie-offset V        rewrite THIS RUN's `tie` stimulus from `dc {vcm}` to
                        `dc {vcm+V}`, e.g. `--tie-offset 1u`. Same contract as
                        `--cmp-rc` and `--spice-option`: a measurement knob
                        that writes NOTHING -- the committed deck's input stays
                        pinned exactly on the threshold, because whether it
                        should stop being pinned is a `spec/` decision
                        (DR-0029), not a probe flag's to make.

What it measured (`sar-logic-timing-gates-tie`, `tt`/27 C/3.30 V, 400 ns) is
the offset sweep tabulated in
`spec/decision-records/DR-0029-tie-loop-decision-chatter.md`, and the short
version is that the candidate's own proposed value does not work: at `1u` the
differential is at ngspice's default `vntol` (1e-6 V), i.e. at the solver's
own node-voltage resolution, and the chatter is not removed -- it gets worse
(50 reversals against the committed 32). Offsets large enough to remove it
are large enough to remove the near-metastable condition the loop exists to
create.

## The third wall: a per-loop deck that still aborts (issue #332)

#310's Evidence 5b predicted -- and measured -- that the per-loop decks clear
the `vvdd_gate#branch` abort, because each carries exactly one DUT instance on
its own supply source. #303's ratified 45-point grid then found one point where
`sim/sar-logic-timing-gates-tie/` aborts anyway:

    sf_27c_2.97v: doAnalyses: TRAN:  Timestep too small; time = 3.99655e-07,
    timestep = 6.25e-21: trouble with node "vvdd_gate#branch"

Same node name, one DUT instance, so #310's composition mechanism is ruled out
by the netlist's own instance count rather than by analogy. One flag was added
here to settle what the sign test is actually reading at that abort:

  --numdgt N            print the probe tables with N significant digits
                        (10..17; default 10, which is what #296 and #310 read
                        their evidence at, so every table those documents
                        transcribe still reproduces byte-for-byte). At the
                        #332 abort `v(tie_topp)` and `v(tie_topn)` agree to
                        ALL TEN default digits, so the default tables cannot
                        distinguish "the differential is at the solver's
                        `vntol`" from "the differential is at the
                        floating-point ulp of a 1.485 V node" -- and those two
                        readings disagree about whether any tolerance change
                        could retire the abort. Writes nothing.

The finding is in
`sim/sar-logic-timing-gates-tie/investigations/20260921-issue-332-quiescent-supply-row-nonconvergence.md`.

## The fourth wall: the DELAY-LINE decks abort too (issue #343)

#303's ratified grids for the two delay-line per-loop decks found that
**every point that ran long enough to reach a verdict aborted** -- `lt`
10 of 45 between t = 1.29 and 2.37 us, `xl` 6 of 45 between 1.43 and
2.71 us, 15 of those 16 on `vvdd_gate#branch` again -- while the T-line-free
`ok` deck completed 45 of 45. The leading hypothesis #343 filed was that the
**ideal lossless transmission line** is the mechanism. Two flags were added
here to settle it, both one-variable A/Bs on the committed deck:

  --delay-line MODE     substitute the `t<tag>d ... z0=50 td=<cmp_delay>` /
                        `r<tag>term` element for THIS RUN ONLY.
                        `ideal` re-emits it byte-identically (the control),
                        `lumped` is an LC artificial line of the same Z0 and
                        the same total delay (so: same transport, different
                        numerics, and a finite bandwidth), `lossy` is a
                        distributed LTRA line of the same Z0/td plus 0.1*Z0
                        of series loss (the `ltra`-style substitution #343
                        asks for), `none` removes the transport entirely
                        (ideal unity buffer onto the same shunt load = the
                        pre-#296 topology), and `series` is the matched
                        line's far-end THEVENIN EQUIVALENT -- full step
                        amplitude through Z0/2 -- with no transport at all.
                        `none` vs `series` is what separates "an ideal source
                        forcing the gate node" from "a bounded-current source
                        driving it"; `ideal` vs `lumped`/`lossy` is what
                        separates the T-element's own numerics from the
                        delay it carries.
  --delay-line-rc R,C   interpose #296's `CMP_OUT_RC` network between the
                        delay element's output and the DUT `cmp` input,
                        e.g. `1k,100f`. On its own it implies
                        `--delay-line ideal`, so it is the sharpest single
                        variable available: the committed line, its Z0, its
                        td and its matched termination are all untouched and
                        ONLY the rise time of the edge the standard cell is
                        asked to chase changes.

Same contract as every knob above -- they write NOTHING. The committed decks
keep their ideal lossless lines, their bounds, their `tran` line and their
comparator decision exactly as ratified. The finding is in
`sim/sar-logic-timing-gates/investigations/20260922-issue-343-delay-line-abort-mechanism.md`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "sim"))

from harness import corners as C  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import runner as R  # noqa: E402
from harness import testbench as T  # noqa: E402

#: The decks this script knows how to probe, mapped to a FALLBACK loop-tag
#: tuple used only if the composed testbench carries no `* ---- loop <tag> ----`
#: banners at all; when the banners are present (they always are for a deck
#: emitted by the current generator) the tags are read from the deck itself.
#:
#: For the two multi-loop parents the fallback names the loops whose comparator
#: drives the DUT gate input DIRECTLY (i.e. the ones #296 is about). The
#: `lt`/`xl`/`bad` timing loops are deliberately absent from that fallback:
#: their comparator drives a 50 ohm terminated T-line and was never the problem.
#:
#: The five single-loop `sar-logic-timing-gates-<tag>` slugs are issue #311's
#: per-loop decomposition of the five-loop parent (PR #321). They are listed
#: here so #310's A/B can be re-run against the decks `sim/run_corners.py`
#: actually scores, not only against this script's own `--only-loops` cut of
#: the parent -- the two are NOT the same circuit (`--only-loops` drops the
#: other loops' `vdd_gate`/`clk` load from a deck that still carries the
#: parent's manifest, while a `-<tag>` slug is a committed deck with its own
#: manifest and its own bounds).
EXPERIMENTS = {
    "sar-logic-timing-gates": ("ok", "tie"),
    "sar-logic-timing-gates-ok": ("ok",),
    "sar-logic-timing-gates-lt": ("lt",),
    "sar-logic-timing-gates-xl": ("xl",),
    "sar-logic-timing-gates-bad": ("bad",),
    "sar-logic-timing-gates-tie": ("tie",),
    "sar-logic-functional-gates": ("se", "df"),
}

_ABORT_RE = re.compile(
    r"Timestep too small; time = (?P<t>[0-9.eE+-]+), "
    r"timestep = (?P<h>[0-9.eE+-]+): trouble with node \"(?P<node>[^\"]+)\""
)

#: Deaths that are NOT a step-control abort. Without these the only failure
#: test here was `_ABORT_RE`, so an ngspice that died for any other reason
#: printed `RESULT  : completed, no 'Timestep too small' abort` -- issue
#: #341's defect class (a run that produced output is not a run that
#: finished), in the instrument rather than in `sim/harness/runner.py`.
#: Observed on issue #343's `--delay-line lossy` arm, which ran out of
#: output memory at t = 3.82e-07 s of a 1.5 us transient and reported
#: "completed".
_FATAL_RE = re.compile(
    r"^(?:ERROR: fatal error in ngspice[^\n]*"
    r"|Error: memory required[^\n]*"
    r"|\s*Fatal error:[^\n]*"
    r"|run simulation\(s\) aborted[^\n]*)$",
    re.MULTILINE,
)

#: The control block's own last statement (`let n = length(time)`/`print n`).
#: Its absence means ngspice never reached the end of the script.
_STEPS_RE = re.compile(r"^n = ([0-9.eE+-]+)", re.MULTILINE)


def _classify(out: str) -> tuple[str, int]:
    """Turn one ngspice log into (one-line verdict, process exit code).

    Three outcomes, deliberately distinct so a caller -- or a shell driving
    a matrix of arms -- can tell them apart:

    * ``0`` the transient reached its stop time,
    * ``1`` it aborted with `Timestep too small` (the thing this script
      exists to measure),
    * ``3`` it died some OTHER way and measured nothing. This one is new:
      it used to be reported as ``0``/"completed", which is how issue
      #343's `lossy` arm came within one reading of being written up as
      "the lossy line converges" on the strength of a run ngspice killed
      for want of memory a quarter of the way in.
    """
    abort = _ABORT_RE.search(out)
    if abort:
        return (f"ABORT at t = {abort['t']} s (timestep {abort['h']}), "
                f"trouble node {abort['node']}"), 1
    fatal = _FATAL_RE.search(out)
    steps = _STEPS_RE.search(out)
    if fatal or steps is None:
        why = fatal.group(0).strip() if fatal else (
            "ngspice never reached the end of the control block (no "
            "timepoint count printed)")
        return (f"FAILED -- no 'Timestep too small' abort, but this run "
                f"measured nothing: {why}"), 3
    return ("completed, no 'Timestep too small' abort "
            f"({float(steps.group(1)):.0f} timepoints)"), 0

#: The post-#296 output network, as emitted by `gen_sar_logic._loop`.
_RC_RE = re.compile(
    r"^b(?P<tag>\w+)cmp (?P=tag)_cmpd 0 V = (?P<expr>.*)\n"
    r"r(?P=tag)cmps (?P=tag)_cmpd (?P=tag)_cmpo \S+\n"
    r"c(?P=tag)cmpl (?P=tag)_cmpo 0 \S+\n",
    re.MULTILINE,
)

#: `gen_sar_logic._timing_body`/`_functional_body` emit one of these banners
#: ahead of every loop, and nothing else in the deck starts with it -- so the
#: composed testbench can be split into per-loop sections without reaching
#: back into the generator (issue #310's `--only-loops`).
_LOOP_BANNER_RE = re.compile(r"^\* ---- loop (?P<tag>\w+) ----$", re.MULTILINE)

#: First line AFTER the last loop section: everything from here on is shared
#: (the `.global`/`.subckt` DUT definition and the library).
_LOOPS_END_RE = re.compile(r"^\.global\b", re.MULTILINE)

#: Marks each probe table in the ngspice log so the reader (and `--tail`)
#: can tell them apart. `print` emits its own header, which is not enough
#: when several tables carry the same column count.
_SECTION = "---PROBE"


def _loop_sections(text: str) -> dict[str, tuple[int, int]]:
    """Map loop tag -> (start, end) character offsets in the composed deck."""
    banners = list(_LOOP_BANNER_RE.finditer(text))
    if not banners:
        return {}
    end_m = _LOOPS_END_RE.search(text, banners[-1].end())
    tail = end_m.start() if end_m else len(text)
    spans: dict[str, tuple[int, int]] = {}
    for i, m in enumerate(banners):
        stop = banners[i + 1].start() if i + 1 < len(banners) else tail
        spans[m["tag"]] = (m.start(), stop)
    return spans


def _only_loops(text: str, keep: tuple[str, ...]) -> str:
    """Drop every loop section whose tag is not in `keep`.

    This makes the deck CHEAPER, not equivalent: the dropped loops also
    stop loading `vdd_gate` and `clk`. See the module docstring.
    """
    spans = _loop_sections(text)
    if not spans:
        raise SystemExit(
            "--only-loops found no '* ---- loop <tag> ----' banners in the "
            "composed testbench; is it stale? run "
            "python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py"
        )
    unknown = sorted(set(keep) - set(spans))
    if unknown:
        raise SystemExit(
            f"--only-loops: no such loop(s) {', '.join(unknown)}; "
            f"this deck has {', '.join(sorted(spans))}"
        )
    drop = sorted((spans[t] for t in spans if t not in keep), reverse=True)
    for start, stop in drop:
        text = text[:start] + text[stop:]
    return text


_RC_VALUES_RE = re.compile(
    r"^(?P<r>r(?P<tag>\w+)cmps (?P=tag)_cmpd (?P=tag)_cmpo )\S+\n"
    r"(?P<c>c(?P=tag)cmpl (?P=tag)_cmpo 0 )\S+$",
    re.MULTILINE,
)


def _set_cmp_rc(text: str, r_val: str, c_val: str) -> tuple[str, int]:
    """Retune (not relax) the #296 output network, for measurement only.

    Issue #310 forbids *silencing* its abort by loosening `cmp_out_rc`. It
    does not forbid SWEEPING tau to find out what the abort depends on --
    which is the only way to tell a time-constant-dependent mechanism from a
    time-constant-independent one. Nothing here writes the tree; the
    committed `CMP_OUT_RC` is whatever `gen_sar_ctrl_gates_tb.py` says.
    """
    text, n = _RC_VALUES_RE.subn(
        lambda m: f"{m['r']}{r_val}\n{m['c']}{c_val}", text
    )
    if not n:
        raise SystemExit(
            "--cmp-rc found no #296 comparator output network to retune; "
            "is the committed testbench stale? run "
            "python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py"
        )
    return text, n


#: The DELAYED loops' comparator output path, as `gen_sar_logic._loop` emits
#: it when `cmp_delay` is set: an IDEAL LOSSLESS transmission line into a
#: matched shunt termination, with the DUT's `cmp` gate input hanging
#: directly off the far end and no #296 output network anywhere.
_TLINE_RE = re.compile(
    r"^t(?P<tag>\w+)d (?P=tag)_cmpi 0 (?P=tag)_cmpo 0 "
    r"z0=(?P<z0>\S+) td=(?P<td>\S+)\n"
    r"r(?P=tag)term (?P=tag)_cmpo 0 (?P<zt>\S+)$",
    re.MULTILINE,
)

#: What `--delay-line` can put in place of that ideal lossless line. Every
#: mode keeps the comparator DECISION line byte-identical -- only the path
#: between the decision node `<tag>_cmpi` and the DUT-facing `<tag>_cmpo`
#: changes, which is exactly the variable issue #343 is testing.
DELAY_LINE_MODES = ("ideal", "lumped", "lossy", "none", "series")

#: Sections in the `lumped` artificial line. 40 sections at `td` = 40 ns puts
#: the ladder's cutoff at N/(pi*td) ~ 318 MHz, i.e. it transports the same
#: delay and the same Z0 but CANNOT transport a zero-rise edge -- which is
#: the difference between a lumped delay and an ideal distributed one.
LADDER_SECTIONS = 40

#: Total series loss the `lossy` LTRA line carries, as a fraction of Z0.
LOSSY_R_FRACTION = 0.1

_SI = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
       "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12}


def _spice_float(value: str) -> float:
    """`'40n'` -> `4e-08`. Only what the committed decks actually use."""
    m = re.fullmatch(r"([0-9.eE+-]+)\s*([a-zA-Z]*)", value.strip())
    if not m:
        raise SystemExit(f"cannot read {value!r} as a SPICE number")
    mant, suffix = float(m.group(1)), m.group(2).lower()
    if not suffix:
        return mant
    for key in ("meg",):                      # longest first
        if suffix.startswith(key):
            return mant * _SI[key]
    if suffix[0] in _SI:
        return mant * _SI[suffix[0]]
    raise SystemExit(f"unknown SPICE suffix in {value!r}")


def _delay_transport(mode: str, tag: str, z0: float, td: float,
                     zt: str, out: str, raw: tuple[str, str]) -> list[str]:
    """The lines that carry the decision from `<tag>_cmpi` to `out`.

    `ideal` re-emits the committed element with its own `z0`/`td` LITERALS
    (`raw`), not a reformatted float, so `--delay-line ideal` alone is a
    byte-identical no-op and `--delay-line ideal --delay-line-rc R,C` is a
    pure "add the #296 network" A/B rather than two changes at once.
    """
    if mode == "ideal":
        return [f"t{tag}d {tag}_cmpi 0 {out} 0 z0={raw[0]} td={raw[1]}",
                f"r{tag}term {out} 0 {zt}"]
    if mode == "lumped":
        l_sec, c_sec = z0 * td / LADDER_SECTIONS, td / z0 / LADDER_SECTIONS
        lines = []
        node = f"{tag}_cmpi"
        for k in range(LADDER_SECTIONS):
            nxt = out if k == LADDER_SECTIONS - 1 else f"{tag}_lad{k}"
            lines.append(f"l{tag}l{k} {node} {nxt} {l_sec:.6e}")
            lines.append(f"c{tag}l{k} {nxt} 0 {c_sec:.6e}")
            node = nxt
        lines.append(f"r{tag}term {out} 0 {zt}")
        return lines
    if mode == "lossy":
        return [
            f"o{tag}d {tag}_cmpi 0 {out} 0 ltra_{tag}",
            f".model ltra_{tag} ltra(r={z0 * LOSSY_R_FRACTION:g} "
            f"l={z0 * td:.6e} g=0 c={td / z0:.6e} len=1 rel=1 abs=1)",
            f"r{tag}term {out} 0 {zt}",
        ]
    if mode == "none":
        # No transport at all: an ideal unity buffer puts the decision on the
        # DUT-facing node in zero time, keeping the same shunt load. This is
        # the pre-#296 topology (an IDEAL source driving a gate input) reached
        # without touching the decision expression.
        return [f"e{tag}d {out} 0 {tag}_cmpi 0 1",
                f"r{tag}term {out} 0 {zt}"]
    if mode == "series":
        # The matched line's far-end THEVENIN EQUIVALENT, minus the transport:
        # open-circuit voltage = the full incident step (a matched line does
        # not divide it), source impedance = z0 || zterm = z0/2. The shunt
        # termination is deliberately NOT re-emitted here -- on a delay-free
        # path it would only divide the step, changing the logic level the
        # gate sees instead of the property under test.
        return [f"e{tag}d {tag}_cmpx 0 {tag}_cmpi 0 1",
                f"r{tag}zs {tag}_cmpx {out} {z0 / 2:g}"]
    raise SystemExit(f"unknown --delay-line mode {mode!r}")


def _set_delay_line(text: str, mode: str,
                    rc: tuple[str, str] | None = None) -> tuple[str, int]:
    """Substitute the delayed loops' delay element, for measurement only.

    Issue #343 asks whether the **ideal lossless transmission line** is the
    mechanism behind the `lt`/`xl`/`bad` `Timestep too small` aborts. That is
    answerable only by running the same point with the line replaced by
    something that carries the same `z0`/`td` but different numerics -- which
    is what `--delay-line` does, and why it is a knob here rather than an edit
    to `gen_sar_ctrl_gates_tb.py`. Same contract as `--cmp-rc`,
    `--tie-offset` and `--spice-option`: it writes NOTHING. The committed
    deck keeps its `t<tag>d ... z0=50 td=<cmp_delay>`, its bounds, its
    `tran` line and its comparator decision exactly as ratified; nothing
    below can make a committed record read differently.

    `rc` additionally interposes #296's `CMP_OUT_RC` network between the
    delay element's output and the DUT-facing node -- the one variant that
    changes ONLY the edge the standard-cell gate input is asked to chase,
    leaving the delay element itself untouched.
    """
    if mode not in DELAY_LINE_MODES:
        raise SystemExit(f"--delay-line wants one of "
                         f"{'|'.join(DELAY_LINE_MODES)}, got {mode!r}")

    def _sub(m: re.Match[str]) -> str:
        tag = m["tag"]
        z0, td = _spice_float(m["z0"]), _spice_float(m["td"])
        out = f"{tag}_cmpt" if rc else f"{tag}_cmpo"
        lines = _delay_transport(mode, tag, z0, td, m["zt"], out,
                                 (m["z0"], m["td"]))
        if rc:
            lines += [f"r{tag}cmps {out} {tag}_cmpo {rc[0]}",
                      f"c{tag}cmpl {tag}_cmpo 0 {rc[1]}"]
        return "\n".join(lines)

    text, n = _TLINE_RE.subn(_sub, text)
    if not n:
        raise SystemExit(
            "--delay-line found no `t<tag>d <tag>_cmpi 0 <tag>_cmpo 0 z0=.. "
            "td=..` / `r<tag>term` delay element to substitute; this deck "
            "carries no delayed loop (ok/tie have none), or the committed "
            "testbench is stale -- run "
            "python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py"
        )
    return text, n


#: The `tie` loop's stimulus, as emitted by `gen_sar_logic._timing_body`:
#: the ONLY loop whose input is a plain `dc {vcm}` rather than a `pwl` ramp,
#: which is exactly what "pinned exactly on the free-MSB threshold" means in
#: the committed deck. Anchored on `_vinp` so the matching `_vinn` reference
#: (`v<tag>cm`, also `dc {vcm}`) is never rewritten -- moving both would move
#: the common mode and leave the differential at zero, i.e. measure nothing.
_TIE_INPUT_RE = re.compile(
    r"^(?P<head>v(?P<tag>\w+)in (?P=tag)_vinp 0 dc )\{vcm\}$", re.MULTILINE
)


def _set_tie_offset(text: str, offset: str) -> tuple[str, int]:
    """Give the pinned-on-threshold input a deterministic offset, for
    measurement only (issue #322's candidate response 2).

    This is a *stimulus* rewrite, so it is the one rewrite in this script
    that could change what the deck CLAIMS rather than only what the solver
    has to do -- which is precisely why it lives here and not in
    `gen_sar_logic._timing_body`. `sim/sar-logic-timing-gates-tie/testbench/
    tb.json`'s claim says the input is pinned *exactly* on the threshold and
    DR-0008 ratifies the loop; changing that is a decision record's business
    (DR-0029), not a flag's. Nothing here writes the tree.
    """
    text, n = _TIE_INPUT_RE.subn(
        lambda m: f"{m['head']}{{vcm+{offset}}}", text
    )
    if not n:
        raise SystemExit(
            "--tie-offset found no pinned-on-threshold input to offset "
            "(expected a `v<tag>in <tag>_vinp 0 dc {vcm}` line); this deck "
            "carries no `tie`-style loop, or the committed testbench is "
            "stale -- run python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py"
        )
    return text, n


def _with_options(head: str, options: list[str]) -> str:
    """Append `.options K=V` lines to the composed deck's preamble.

    A solver tolerance is not a spec bound and not a `tb.json` check, so
    sweeping one is a legitimate measurement rather than a relaxation --
    but it is only legitimate if it stays out of the tree, which is why
    this appends to the deck text under `tempfile` and nothing else.

    `K=V` is required (rather than accepting bare flag-style options) so a
    typo cannot silently become a no-op the reader then over-interprets.
    """
    for opt in options:
        key, sep, _ = opt.partition("=")
        if not sep or not key.strip():
            raise SystemExit(
                f"--spice-option wants 'K=V', got {opt!r} -- a bare option "
                "name is rejected so a typo cannot pass as a measurement"
            )
        head += f".options {opt}\n"
    return head


def _probe_nodes(text: str, tag: str) -> list[str]:
    """The readout for one loop: its comparator inputs, then its decision
    node and the node the DUT actually sees.

    The undelayed loops (`ok`/`tie`) carry the #296 output network, so their
    decision lands on `<tag>_cmpd` and reaches the DUT through the RC as
    `<tag>_cmpo`. The delayed loops (`lt`/`xl`/`bad`) drive a terminated
    T-line instead, so their decision node is `<tag>_cmpi` -- keyed off the
    DECISION source rather than off the `t<tag>d` element, so every
    `--delay-line` substitution (issue #343) still reads out the same two
    nodes and `--chatter` keeps working across the A/B.
    """
    groups = [f"v({tag}_topp) v({tag}_topn)"]
    if f"\nb{tag}cmp {tag}_cmpd " in text:
        groups.append(f"v({tag}_cmpd) v({tag}_cmpo)")
    elif f"\nb{tag}cmp {tag}_cmpi " in text:
        groups.append(f"v({tag}_cmpi) v({tag}_cmpo)")
    else:
        # --ideal-cmp: the decision lands straight on the DUT-facing node.
        groups.append(f"v({tag}_cmpo)")
    return groups


def _ideal_cmp(text: str) -> tuple[str, int]:
    """Undo #296: collapse the output network back to a bare ideal source."""
    text, n = _RC_RE.subn(
        lambda m: f"b{m['tag']}cmp {m['tag']}_cmpo 0 V = {m['expr']}\n", text
    )
    if not n:
        raise SystemExit(
            "--ideal-cmp found no post-#296 comparator output network to undo; "
            "is the committed testbench stale? run "
            "python3 design/sar-logic/flow/gen_sar_ctrl_gates_tb.py"
        )
    return text, n


#: ngspice's `set numdgt` for the probe tables. 10 is what #296 and #310 read
#: their evidence at, so it stays the default -- every table transcribed into
#: those documents is reproduced byte-for-byte by a run that passes nothing.
DEFAULT_NUMDGT = 10

#: The largest `numdgt` worth asking for. A `double` carries ~15.95 decimal
#: digits, so 17 digits round-trips one exactly and anything beyond that is
#: printing noise the reader would over-interpret.
MAX_NUMDGT = 17


def _control(tb: T.Testbench, until: str | None, tags: tuple[str, ...],
             probe: bool, netlist: str,
             numdgt: int = DEFAULT_NUMDGT,
             save_probed_only: bool = False) -> list[str]:
    tran = next(a for a in tb.analyses if a.split()[0] == "tran")
    if until is not None:
        fields = tran.split()
        fields[2] = until               # tran <step> <stop> <start> <max>
        tran = " ".join(fields)
    if not DEFAULT_NUMDGT <= numdgt <= MAX_NUMDGT:
        raise SystemExit(
            f"--numdgt wants {DEFAULT_NUMDGT}..{MAX_NUMDGT}, got {numdgt}: "
            f"below {DEFAULT_NUMDGT} the tables stop reproducing #296/#310's "
            f"transcribed evidence, and above {MAX_NUMDGT} a double has no "
            "more digits to print"
        )
    groups = [g for tag in tags for g in _probe_nodes(netlist, tag)]
    groups.append("v(vdd_gate) i(vvdd_gate)")
    lines = [".control", f"set numdgt={numdgt}", "set noaskquit",
             "set num_threads=1",
             "set width=512", "set nobreak"]
    if save_probed_only:
        # Store ONLY what the probe tables read back. This changes nothing
        # the solver computes -- same matrix, same steps, same numbers -- it
        # changes how much of the answer ngspice keeps in RAM. Without it a
        # long transient on a big synthesized netlist keeps every node at
        # every accepted timepoint, which is how issue #343's `lossy` arm hit
        # `Error: memory required ... is more than memory available` a
        # quarter of the way into a 1.5 us window.
        lines.append("  save " + " ".join(groups))
    lines.append(f"  {tran}")
    if probe:
        for tag in tags:
            for i, group in enumerate(_probe_nodes(netlist, tag)):
                lines.append(f'  echo {_SECTION} {tag}.{i} {group}')
                lines.append(f"  print {group}")
        # The shared DUT supply: `vvdd_gate#branch` is the trouble node
        # issue #310 is about, and it belongs to no single loop.
        lines.append(f'  echo {_SECTION} supply v(vdd_gate) i(vvdd_gate)')
        lines.append("  print v(vdd_gate) i(vvdd_gate)")
    lines += ["  let n = length(time)", "  print n", ".endc", ".end", ""]
    return lines


#: Default mid-rail band for the dwell figure. The DUT's `cmp` port drives
#: `gf180mcu_fd_sc_mcu7t5v0` `aoi21_1`/`nor2_1` inputs; 0.8 V / 2.5 V brackets
#: the switching band those cells present at a 3.30 V rail, so time spent in
#: here is time real standard-cell inputs are held in their high-gain linear
#: region -- the state #296's rejected soft comparator produced statically.
MID_RAIL_BAND = (0.8, 2.5)


def _probe_tables(out: str) -> dict[str, list[tuple[float, ...]]]:
    """Parse every `---PROBE` table in the log into numeric rows.

    Returns banner-suffix -> [(time, col0, col1, ...), ...], e.g.
    `"tie.1"` -> the `v(tie_cmpd) v(tie_cmpo)` table. ngspice's own `Index`
    header line and the index column itself are dropped.
    """
    tables: dict[str, list[tuple[float, ...]]] = {}
    key: str | None = None
    for line in out.splitlines():
        if line.startswith(_SECTION):
            key = line[len(_SECTION):].split()[0]
            tables.setdefault(key, [])
        elif key is not None and re.match(r"^\d+\t", line):
            fields = line.split("\t")[1:]
            try:
                tables[key].append(tuple(float(f) for f in fields if f != ""))
            except ValueError:      # a wrapped or malformed row -- skip it
                continue
    return tables


def _chatter_summary(out: str, tags: tuple[str, ...], vdd: float,
                     band: tuple[float, float] = MID_RAIL_BAND) -> list[str]:
    """The two figures issue #310's investigation reads, computed here rather
    than by hand, so an outside reader re-derives them instead of trusting a
    transcribed table (CLAUDE.md, "Work in the open").

    * **decision reversals** -- accepted-timepoint-to-accepted-timepoint
      changes of the comparator's own hard decision `v(<tag>_cmpd)`,
      thresholded at mid-rail. The decision is a ternary that always resolves
      to a rail, so a reversal is the decision *changing its mind*, not a slow
      edge. This is the quantity that distinguishes a chattering hard decision
      from the soft (statically mid-rail) comparator #296 rejected.
    * **mid-rail dwell** -- how long the DUT-facing node `v(<tag>_cmpo)`
      spends inside `band`, trapezoid-integrating the in-band indicator over
      the accepted-timepoint grid. This is the *consequence* of chatter: each
      reversal restarts the 100 ps `cmp_out_rc` network, so the node the gates
      actually see need never reach a rail.

    Reversals are counted over the WHOLE run, independent of `--tail` (which
    only limits what is printed).
    """
    tables = _probe_tables(out)
    mid = vdd / 2.0
    lo, hi = band
    rows = [f"chatter summary (band {lo}-{hi} V, decision threshold {mid:g} V)",
            f"{'loop':>6}  {'timepoints':>10}  {'reversals':>9}  "
            f"{'mid-rail dwell':>14}"]
    for tag in tags:
        data = tables.get(f"{tag}.1", [])
        if not data:
            rows.append(f"{tag:>6}  {'(no decision/output table)':>10}")
            continue
        reversals = 0
        dwell = 0.0
        prev_hi: bool | None = None
        for i, row in enumerate(data):
            if len(row) < 3:
                continue
            t, decision, dut = row[0], row[1], row[2]
            now_hi = decision > mid
            if prev_hi is not None and now_hi != prev_hi:
                reversals += 1
            prev_hi = now_hi
            if i:
                t_prev, dut_prev = data[i - 1][0], data[i - 1][2]
                in_now = lo <= dut <= hi
                in_prev = lo <= dut_prev <= hi
                dwell += (t - t_prev) * (in_now + in_prev) / 2.0
        rows.append(f"{tag:>6}  {len(data):>10}  {reversals:>9}  "
                    f"{dwell * 1e9:>11.3f} ns")
    supply = tables.get("supply", [])
    if supply:
        currents = [abs(r[2]) for r in supply if len(r) >= 3]
        if currents:
            rows.append(f"  shared supply: peak |i(vvdd_gate)| = "
                        f"{max(currents) * 1e3:.3f} mA, median = "
                        f"{sorted(currents)[len(currents) // 2] * 1e6:.2f} uA")
    return rows


def _emit_probe(out: str, tail: int) -> None:
    """Print each `---PROBE` table from the log, optionally only its last
    `tail` data rows (0 = all, the pre-#310 behaviour)."""
    banner: str | None = None
    columns: str | None = None
    rows: list[str] = []

    def flush() -> None:
        if banner is None and columns is None:
            return
        if banner:
            print(banner)
        if columns:
            print(columns)
        for r in (rows[-tail:] if tail else rows):
            print(r)

    for line in out.splitlines():
        if line.startswith(_SECTION):
            flush()
            banner, columns, rows[:] = line, None, []
        elif line.startswith("Index"):
            columns = line          # ngspice's own column header
        elif re.match(r"^\d+\t", line):
            rows.append(line)
    flush()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("experiment", choices=sorted(EXPERIMENTS))
    p.add_argument("--corner", default="tt")
    p.add_argument("--temp", type=float, default=27.0)
    p.add_argument("--vdd", type=float, default=3.30)
    p.add_argument("--until", default=None,
                   help="shorten the transient stop time, e.g. 200n")
    p.add_argument("--ideal-cmp", action="store_true",
                   help="A side of the A/B: restore the pre-#296 comparator")
    p.add_argument("--probe", action="store_true",
                   help="print the comparator differential up to the stop")
    p.add_argument("--only-loops", default=None, metavar="TAG[,TAG...]",
                   help="keep only these '* ---- loop <tag> ----' sections "
                        "(issue #310 A/B). Cheaper, but a DIFFERENT circuit: "
                        "the dropped loops also stop loading vdd_gate/clk")
    p.add_argument("--cmp-rc", default=None, metavar="R,C",
                   help="retune the #296 comparator output network for this "
                        "run only, e.g. '1k,10f'. A MEASUREMENT knob for "
                        "issue #310 (does the abort depend on tau?), never a "
                        "way to silence an abort -- it changes nothing in "
                        "the tree")
    p.add_argument("--delay-line", default=None, choices=DELAY_LINE_MODES,
                   help="substitute the delayed loops' (lt/xl/bad) delay "
                        "element for this run only: 'ideal' the committed "
                        "lossless T-line, 'lumped' a %d-section LC line of "
                        "the same Z0/td, 'lossy' an LTRA line of the same "
                        "Z0/td plus %g*Z0 of series loss, 'none' an ideal "
                        "zero-delay buffer onto the same load, 'series' the "
                        "matched line's far-end Thevenin equivalent (Z0/2) "
                        "without the transport. A MEASUREMENT knob for issue "
                        "#343 (is the ideal lossless line the abort "
                        "mechanism?). Changes nothing in the tree"
                        % (LADDER_SECTIONS, LOSSY_R_FRACTION))
    p.add_argument("--delay-line-rc", default=None, metavar="R,C",
                   help="interpose #296's comparator output network between "
                        "the delay element's output and the DUT gate input, "
                        "e.g. '1k,100f'. Implies --delay-line ideal unless "
                        "one is given, so on its own it is the one-variable "
                        "A/B: committed line untouched, only the EDGE the "
                        "gate sees changes. Changes nothing in the tree")
    p.add_argument("--tie-offset", default=None, metavar="V",
                   help="rewrite the pinned-on-threshold `tie` input to "
                        "`dc {vcm+V}` for this run only, e.g. '1u'. A "
                        "MEASUREMENT knob for issue #322: candidate response 2 "
                        "was to adopt exactly this, so it had to be measured "
                        "before being adopted or rejected (see DR-0029). It "
                        "changes nothing in the tree -- the committed input "
                        "stays pinned exactly on the threshold")
    p.add_argument("--tail", type=int, default=0, metavar="N",
                   help="with --probe, print only the last N rows of each "
                        "table (0 = all, the default and pre-#310 behaviour)")
    p.add_argument("--chatter", action="store_true",
                   help="print per-loop decision-reversal counts and mid-rail "
                        "dwell over the WHOLE run (issue #310's two figures, "
                        "re-derived here rather than transcribed). Implies "
                        "--probe; unaffected by --tail")
    p.add_argument("--spice-option", action="append", default=[],
                   metavar="K=V",
                   help="append '.options K=V' to this run's deck only "
                        "(repeatable), e.g. --spice-option abstol=1e-10. A "
                        "MEASUREMENT knob for issue #310: the abort lands on a "
                        "near-zero shared-supply branch current with the DUT "
                        "quiescent, so only moving the solver tolerance "
                        "separates a conditioning failure from a circuit "
                        "event. Changes nothing in the tree")
    p.add_argument("--numdgt", type=int, default=DEFAULT_NUMDGT,
                   metavar="N",
                   help="print the probe tables with N significant digits "
                        f"({DEFAULT_NUMDGT}..{MAX_NUMDGT}; default "
                        f"{DEFAULT_NUMDGT}, which is what #296/#310 read "
                        "their evidence at). A MEASUREMENT knob for issue "
                        "#332: at the sf/27C/2.97V abort the comparator's two "
                        "input nodes agree to all 10 default digits, so only "
                        "a wider print says whether the differential the hard "
                        "sign test is reading is at the solver's node "
                        "tolerance or at the floating-point ulp of the node "
                        "voltage itself. Changes nothing in the tree")
    p.add_argument("--save-probed-only", action="store_true",
                   help="keep only the probed vectors in memory (`save` in "
                        "the control block) instead of every node at every "
                        "timepoint. Changes NOTHING the solver computes -- "
                        "it is a memory knob, added because issue #343's "
                        "LTRA arm died with 'Error: memory required ... is "
                        "more than memory available' a quarter of the way "
                        "into a 1.5 us window. Off by default so #296/#310's "
                        "recorded invocations compose byte-identical decks")
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--keep", metavar="DIR",
                   help="keep the composed deck and raw log in DIR")
    args = p.parse_args(argv)
    # --chatter reads the same per-loop tables --probe emits.
    probe_tables = args.probe or args.chatter

    tb = T.load(REPO / "sim" / args.experiment)
    point = C.PvtPoint(corner=C.CORNERS[args.corner], temp_c=args.temp,
                       vdd=args.vdd)

    netlist = Path(tb.netlist).read_text()
    # #296 only ever probed the two loops whose comparator drives the DUT
    # gate input directly. #310's trouble node is the SHARED supply branch,
    # so every loop present is a suspect until measurement says otherwise.
    tags = tuple(_loop_sections(netlist)) or EXPERIMENTS[args.experiment]
    if args.ideal_cmp:
        netlist, n = _ideal_cmp(netlist)
        print(f"--ideal-cmp: reverted {n} comparator output network(s)")
    if args.cmp_rc:
        if args.ideal_cmp:
            raise SystemExit("--cmp-rc and --ideal-cmp are mutually exclusive: "
                             "--ideal-cmp removes the network --cmp-rc tunes")
        r_val, _, c_val = args.cmp_rc.partition(",")
        if not r_val or not c_val:
            raise SystemExit("--cmp-rc wants 'R,C', e.g. '1k,10f'")
        netlist, n = _set_cmp_rc(netlist, r_val.strip(), c_val.strip())
        print(f"--cmp-rc: retuned {n} comparator output network(s) to "
              f"R={r_val.strip()} C={c_val.strip()} (measurement only)")
    if args.delay_line or args.delay_line_rc:
        rc: tuple[str, str] | None = None
        if args.delay_line_rc:
            r_val, _, c_val = args.delay_line_rc.partition(",")
            if not r_val.strip() or not c_val.strip():
                raise SystemExit("--delay-line-rc wants 'R,C', e.g. '1k,100f'")
            rc = (r_val.strip(), c_val.strip())
        mode = args.delay_line or "ideal"
        netlist, n = _set_delay_line(netlist, mode, rc)
        print(f"--delay-line: substituted {n} delay element(s) with mode "
              f"{mode!r}"
              + (f" plus a {rc[0]}/{rc[1]} output network" if rc else "")
              + "  (measurement only -- the committed deck keeps its "
                "ideal lossless line)")
    if args.tie_offset:
        netlist, n = _set_tie_offset(netlist, args.tie_offset.strip())
        print(f"--tie-offset: offset {n} pinned-on-threshold input(s) to "
              f"{{vcm+{args.tie_offset.strip()}}} (measurement only -- the "
              f"committed deck stays pinned exactly on the threshold)")
    if args.only_loops:
        keep = tuple(t.strip() for t in args.only_loops.split(",") if t.strip())
        present = sorted(_loop_sections(netlist))
        netlist = _only_loops(netlist, keep)
        tags = tuple(t for t in present if t in keep)
        print(f"--only-loops: kept {', '.join(tags)} of "
              f"{', '.join(present)}  (a DIFFERENT circuit -- the dropped "
              f"loops also stop loading vdd_gate/clk)")

    with tempfile.TemporaryDirectory() as tmp:
        # `.resolve()` matters: ngspice is launched with `cwd=work`, so a
        # RELATIVE --keep would compose `deck_path` relative to the repo root
        # and then hand that same relative string to a process whose cwd is
        # the keep directory -- "No such file or directory", with the deck
        # sitting right there. Absolute from here on.
        work = Path(args.keep).resolve() if args.keep else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        frag = work / Path(tb.netlist).name
        frag.write_text(netlist)
        tb.netlist = frag
        deck = R.compose_deck(tb, P.find_pdk(), point, num_threads=1)
        # replace the manifest's measurement control block with our own
        head = _with_options(deck[: deck.index(".control")],
                             args.spice_option)
        if args.spice_option:
            print("--spice-option: "
                  + ", ".join(args.spice_option)
                  + "  (this run only -- writes nothing)")
        deck = head + "\n".join(
            _control(tb, args.until, tags, probe_tables, netlist,
                     numdgt=args.numdgt,
                     save_probed_only=args.save_probed_only)
        )
        deck_path = work / f"probe_{point.corner_id}.spice"
        deck_path.write_text(deck)

        print(f"deck    : {deck_path}")
        print(f"point   : {point.corner_id}  (stop="
              f"{args.until or 'manifest default'})")
        try:
            proc = subprocess.run([R.NGSPICE, "-b", str(deck_path)],
                                  capture_output=True, text=True,
                                  timeout=args.timeout, cwd=work, check=False)
        except subprocess.TimeoutExpired:
            print(f"RESULT  : TIMEOUT after {args.timeout}s")
            return 2
        out = proc.stdout + "\n" + proc.stderr
        if args.keep:
            (work / f"probe_{point.corner_id}.log").write_text(out)

        if args.probe:
            _emit_probe(out, args.tail)
        if args.chatter:
            for row in _chatter_summary(out, tags, args.vdd):
                print(row)

        label, code = _classify(out)
        print(f"RESULT  : {label}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
