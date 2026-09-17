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
             probe: bool) -> list[str]:
    tran = next(a for a in tb.analyses if a.split()[0] == "tran")
    if until is not None:
        fields = tran.split()
        fields[2] = until               # tran <step> <stop> <start> <max>
        tran = " ".join(fields)
    lines = [".control", "set numdgt=10", "set noaskquit", "set num_threads=1",
             f"  {tran}"]
    if probe:
        for tag in tags:
            lines.append(f"  print v({tag}_topp) v({tag}_topn) v({tag}_cmpo)")
    lines += ["  let n = length(time)", "  print n", ".endc", ".end", ""]
    return lines


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
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--keep", metavar="DIR",
                   help="keep the composed deck and raw log in DIR")
    args = p.parse_args(argv)

    tags = EXPERIMENTS[args.experiment]
    tb = T.load(REPO / "sim" / args.experiment)
    point = C.PvtPoint(corner=C.CORNERS[args.corner], temp_c=args.temp,
                       vdd=args.vdd)

    netlist = Path(tb.netlist).read_text()
    if args.ideal_cmp:
        netlist, n = _ideal_cmp(netlist)
        print(f"--ideal-cmp: reverted {n} comparator output network(s)")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(args.keep) if args.keep else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        frag = work / Path(tb.netlist).name
        frag.write_text(netlist)
        tb.netlist = frag
        deck = R.compose_deck(tb, P.find_pdk(), point, num_threads=1)
        # replace the manifest's measurement control block with our own
        deck = deck[: deck.index(".control")] + "\n".join(
            _control(tb, args.until, tags, args.probe)
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
            for line in out.splitlines():
                if line.startswith("Index") or re.match(r"^\d+\t", line):
                    print(line)

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
