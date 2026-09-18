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
loop. Three flags were added here to isolate it:

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
                        confirm on the full deck.
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

#: The two decks this script knows how to probe, and the loop tags in each
#: whose comparator drives the DUT gate input DIRECTLY (i.e. the ones #296 is
#: about). The `lt`/`xl`/`bad` timing loops are deliberately absent: their
#: comparator drives a 50 ohm terminated T-line and was never the problem.
EXPERIMENTS = {
    "sar-logic-timing-gates": ("ok", "tie"),
    "sar-logic-functional-gates": ("se", "df"),
}

_ABORT_RE = re.compile(
    r"Timestep too small; time = (?P<t>[0-9.eE+-]+), "
    r"timestep = (?P<h>[0-9.eE+-]+): trouble with node \"(?P<node>[^\"]+)\""
)

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


def _probe_nodes(text: str, tag: str) -> list[str]:
    """The readout for one loop: its comparator inputs, then its decision
    node and the node the DUT actually sees.

    The undelayed loops (`ok`/`tie`) carry the #296 output network, so their
    decision lands on `<tag>_cmpd` and reaches the DUT through the RC as
    `<tag>_cmpo`. The delayed loops (`lt`/`xl`/`bad`) drive a terminated
    T-line instead, so their decision node is `<tag>_cmpi`.
    """
    groups = [f"v({tag}_topp) v({tag}_topn)"]
    if f"\nb{tag}cmp {tag}_cmpd " in text:
        groups.append(f"v({tag}_cmpd) v({tag}_cmpo)")
    elif f"\nt{tag}d {tag}_cmpi " in text:
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


def _control(tb: T.Testbench, until: str | None, tags: tuple[str, ...],
             probe: bool, netlist: str) -> list[str]:
    tran = next(a for a in tb.analyses if a.split()[0] == "tran")
    if until is not None:
        fields = tran.split()
        fields[2] = until               # tran <step> <stop> <start> <max>
        tran = " ".join(fields)
    lines = [".control", "set numdgt=10", "set noaskquit", "set num_threads=1",
             "set width=512", "set nobreak", f"  {tran}"]
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
    p.add_argument("--tail", type=int, default=0, metavar="N",
                   help="with --probe, print only the last N rows of each "
                        "table (0 = all, the default and pre-#310 behaviour)")
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--keep", metavar="DIR",
                   help="keep the composed deck and raw log in DIR")
    args = p.parse_args(argv)

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
    if args.only_loops:
        keep = tuple(t.strip() for t in args.only_loops.split(",") if t.strip())
        present = sorted(_loop_sections(netlist))
        netlist = _only_loops(netlist, keep)
        tags = tuple(t for t in present if t in keep)
        print(f"--only-loops: kept {', '.join(tags)} of "
              f"{', '.join(present)}  (a DIFFERENT circuit -- the dropped "
              f"loops also stop loading vdd_gate/clk)")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(args.keep) if args.keep else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        frag = work / Path(tb.netlist).name
        frag.write_text(netlist)
        tb.netlist = frag
        deck = R.compose_deck(tb, P.find_pdk(), point, num_threads=1)
        # replace the manifest's measurement control block with our own
        deck = deck[: deck.index(".control")] + "\n".join(
            _control(tb, args.until, tags, args.probe, netlist)
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

        abort = _ABORT_RE.search(out)
        if abort:
            print(f"RESULT  : ABORT at t = {abort['t']} s "
                  f"(timestep {abort['h']}), trouble node {abort['node']}")
            return 1
        steps = re.search(r"^n = ([0-9.eE+-]+)", out, re.MULTILINE)
        print("RESULT  : completed, no 'Timestep too small' abort"
              + (f" ({float(steps.group(1)):.0f} timepoints)" if steps else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
