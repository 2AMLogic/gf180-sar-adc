#!/usr/bin/env python3
"""Readout instrument for the `abs_err_*` code-error family (issue #320).

`sim/sar-logic-timing-gates-ok/`'s first scored 45-point grid
(`records/20260918-233547-1d81aa1.md`) reported `abs_err_delay_0ns` up to
**512 LSB** at 10 of 45 PVT points, with `ok_conv_period_ns` at exactly
1000 ns everywhere -- a converter that keeps its cadence and (apparently)
produces a wrong code. The manifest's measurement is a single scalar,

    meas tran aerr_ok MAX v(ok_aerr) FROM=0.1u

over the whole 8.5 us run, so the record says *how big* the worst excursion
is and *nothing* about **when** it happens, **which bit** carries it, or
whether the code was still **settling** at that instant. This script is the
missing readout: it re-composes exactly the deck `sim/run_corners.py` would
compose for one PVT point (same `sim/harness` code path, same PDK
resolution, same corner sections, same committed testbench text), prints the
code register timepoint by timepoint, and then reports, per conversion:

  * the **instantaneous** worst `|code - exp|` inside the `drdy` window --
    the quantity `meas ... MAX` takes its maximum over;
  * the **settled** `|code - exp|` at the END of the same window, after the
    output register has finished updating -- the quantity a reader means by
    "did this conversion convert correctly";
  * the **register settling time**: how long after `drdy` crosses mid-rail
    the last `c<i>` bit stops moving.

Those three numbers separate the two readings of a large `abs_err_*`:

  instantaneous large + settled zero  -> the register was caught MID-UPDATE
                                          by the measurement's own `drdy`
                                          gate; the conversion is correct.
  instantaneous large + settled large -> the conversion really is wrong.

It writes nothing under `sim/<slug>/records|corners|netlist-snapshots/` --
it is a debugging instrument, not an evidence writer. Only
`sim/run_corners.py` writes evidence.

## Usage

    # the worst point of the grid (512 LSB), full ratified window
    python3 design/sar-logic/flow/probe_code_readout.py \
        sar-logic-timing-gates-ok --corner sf --temp 125 --vdd 3.30

    # a cheap cut: the first conversion only (the 1.125 us excursion that
    # 8 of the 10 failing points report)
    python3 design/sar-logic/flow/probe_code_readout.py \
        sar-logic-timing-gates-ok --corner ss --temp 125 --vdd 3.63 \
        --until 1.3u

    # per-bit detail around the worst instant
    python3 design/sar-logic/flow/probe_code_readout.py \
        sar-logic-timing-gates-ok --corner sf --temp 125 --vdd 3.30 --bits

`--until` shortens the transient stop time only; it never touches the
committed testbench, the manifest, or any bound. `--tag` selects the loop
when a deck carries more than one (the five-loop parent, or the functional
deck's `se`/`df`).

## What it measured (issue #320, `sar-logic-timing-gates-ok`)

    probe_code_readout.py sar-logic-timing-gates-ok \
        --corner sf --temp 125 --vdd 3.30 --bits
    -> conv #1: exp 507, settled code 479  (28 LSB -- a REAL wrong code)
       conv #2..#8: settled error 0 at every one
       conv #6: inst max 512 LSB, settled 0  (the 511->512 major carry,
                caught 0 s after the drdy rise, register settling 0.186 ns)
       guard sweep: 0.00 ns -> 512 LSB / 8 conversions flagged
                    0.25 ns ->  28 LSB / 1 conversion  flagged

Two mechanisms, neither of them the setup-time violation issue #320
hypothesised: the first conversion after power-up is genuinely invalid
(`start` seeds the `ph` ring and not the `eng`/`q`/`c` registers, so
conversion 1 searches against arbitrary already-engaged weights), and the
manifest's `drdy`-gated comparison samples the output register inside its
own clk->Q window. Full root cause, the 45-point correlation, the
`--ic-eng-zero` A/B and STA's verdict:
`sim/sar-logic-timing-gates-ok/investigations/20260919-issue-320-first-conversion-and-decode-transient.md`.
Disposition: `spec/decision-records/DR-0029-power-up-first-conversion-validity.md`.
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

#: Loop tags per deck, used only as a fallback when the composed testbench
#: carries no `* ---- loop <tag> ----` banners.
EXPERIMENTS = {
    "sar-logic-timing-gates": ("ok", "lt", "xl", "bad", "tie"),
    "sar-logic-timing-gates-ok": ("ok",),
    "sar-logic-timing-gates-lt": ("lt",),
    "sar-logic-timing-gates-xl": ("xl",),
    "sar-logic-timing-gates-bad": ("bad",),
    "sar-logic-timing-gates-tie": ("tie",),
    "sar-logic-timing": ("ok", "lt", "xl", "bad", "tie"),
    "sar-logic-functional-gates": ("se", "df"),
    "sar-logic-functional": ("se", "df"),
}

_LOOP_BANNER_RE = re.compile(r"^\* ---- loop (?P<tag>\w+) ----$", re.MULTILINE)
_ABORT_RE = re.compile(
    r"Timestep too small; time = (?P<t>[0-9.eE+-]+), "
    r"timestep = (?P<h>[0-9.eE+-]+): trouble with node \"(?P<node>[^\"]+)\""
)
_SECTION = "---READOUT"

#: The ten code-register outputs, MSB first, as `_loop` names them.
BITS = tuple(f"c{i}" for i in range(9, -1, -1))

#: The nine `engaged` flags inside the DUT, MSB weight first. `sar_ctrl.v`
#: clears them only at `endconv = ph[13]` -- `start` does NOT -- so their
#: POWER-UP value is carried through the whole of the first conversion's
#: sample and bit trials. `--ic-eng-zero` overrides exactly these.
ENG = tuple(f"eng{i}" for i in range(9, 0, -1))

#: Settling guards swept by the summary table: how long after `drdy`
#: crosses mid-rail the code comparison is suppressed. 0 ns is the
#: committed `b<tag>err` gate.
GUARDS_NS = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0)


def _control(tb: T.Testbench, tag: str, until: str | None,
             bits: bool, analog: bool) -> list[str]:
    """Our own control block: the manifest's `meas` lines are replaced by a
    raw print of the readout nodes, so nothing here can be mistaken for a
    scored measurement."""
    tran = next(a for a in tb.analyses if a.split()[0] == "tran")
    if until is not None:
        fields = tran.split()          # tran <step> <stop> <start> <max>
        fields[2] = until
        tran = " ".join(fields)
    core = [f"v({tag}_drdy)", f"v({tag}_code)", f"v({tag}_exp)"]
    bitv = [f"v({tag}_{b})" for b in BITS]
    anav = ["v(clk)", f"v({tag}_topp)", f"v({tag}_topn)", f"v({tag}_cmpo)"]
    save = core + (bitv if bits else []) + (anav if analog else [])
    lines = [".control", "set numdgt=10", "set noaskquit", "set num_threads=1",
             "set width=512", "set nobreak",
             "  save " + " ".join(save),
             f"  {tran}",
             f"  echo {_SECTION} core " + " ".join(core),
             "  print " + " ".join(core)]
    if bits:
        lines += [f"  echo {_SECTION} bits " + " ".join(bitv),
                  "  print " + " ".join(bitv)]
    if analog:
        lines += [f"  echo {_SECTION} analog " + " ".join(anav),
                  "  print " + " ".join(anav)]
    lines += ["  let n = length(time)", "  print n", ".endc", ".end", ""]
    return lines


def _tables(out: str) -> dict[str, list[tuple[float, ...]]]:
    """Parse every `---READOUT` table in the log into numeric rows."""
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
            except ValueError:          # a wrapped or malformed row -- skip
                continue
    return tables


def _windows(rows: list[tuple[float, ...]], vth: float
             ) -> list[tuple[int, int]]:
    """Index ranges [i0, i1] of each contiguous run of `drdy > vth`."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for i, row in enumerate(rows):
        high = row[1] > vth
        if high and start is None:
            start = i
        elif not high and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(rows) - 1))
    return spans


def _settle_time(bit_rows: list[tuple[float, ...]], t0: float, t1: float,
                 vth: float) -> float | None:
    """Last time in (t0, t1] at which ANY `c<i>` crosses `vth`, minus t0."""
    last: float | None = None
    prev: tuple[float, ...] | None = None
    for row in bit_rows:
        if prev is not None and t0 <= row[0] <= t1:
            for a, b in zip(prev[1:], row[1:]):
                if (a > vth) != (b > vth):
                    last = row[0]
                    break
        prev = row
    return None if last is None else last - t0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("experiment", choices=sorted(EXPERIMENTS))
    p.add_argument("--tag", default=None,
                   help="loop tag to read out (default: the deck's first)")
    p.add_argument("--corner", default="tt")
    p.add_argument("--temp", type=float, default=27.0)
    p.add_argument("--vdd", type=float, default=3.30)
    p.add_argument("--until", default=None,
                   help="shorten the transient stop time, e.g. 1.3u")
    p.add_argument("--bits", action="store_true",
                   help="also read out c9..c0 individually and report the "
                        "output register's settling time per conversion")
    p.add_argument("--analog", action="store_true",
                   help="also read out clk and the comparator's own inputs "
                        "and output, so a wrong bit can be attributed to the "
                        "decision (topp-topn had the wrong sign) or to its "
                        "capture (the sign was right but arrived late)")
    p.add_argument("--trials", metavar="T0,T1",
                   help="with --analog, dump every accepted timepoint in the "
                        "window [T0,T1] seconds -- the bit-trial detail")
    p.add_argument("--ic-eng-zero", action="store_true",
                   help="A/B knob: add `.ic v(x<tag>.eng<i>)=0` for all nine "
                        "engaged flags, i.e. start the run from the state a "
                        "power-on reset would leave them in. Writes NOTHING "
                        "-- neither the RTL, the netlist, the testbench nor "
                        "any bound changes; this only answers whether the "
                        "power-up value of those flags is what corrupts the "
                        "first conversion")
    p.add_argument("--rows", type=int, default=0, metavar="N",
                   help="print the N raw timepoints around each conversion's "
                        "worst instant (0 = none, the default)")
    p.add_argument("--timeout", type=int, default=86400)
    p.add_argument("--keep", metavar="DIR",
                   help="keep the composed deck and raw log in DIR")
    args = p.parse_args(argv)

    tb = T.load(REPO / "sim" / args.experiment)
    point = C.PvtPoint(corner=C.CORNERS[args.corner], temp_c=args.temp,
                       vdd=args.vdd)
    netlist_text = Path(tb.netlist).read_text()
    tags = tuple(m["tag"] for m in _LOOP_BANNER_RE.finditer(netlist_text)) \
        or EXPERIMENTS[args.experiment]
    tag = args.tag or tags[0]
    if tag not in tags:
        raise SystemExit(f"--tag {tag!r} not in this deck's loops: {tags}")
    vth = args.vdd / 2.0

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(args.keep) if args.keep else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        deck = R.compose_deck(tb, P.find_pdk(), point, num_threads=1)
        head = deck[: deck.index(".control")]
        if args.ic_eng_zero:
            head += "\n* --ic-eng-zero (issue #320 A/B, this run only)\n"
            head += "".join(f".ic v(x{tag}.{e})=0\n" for e in ENG)
            print("--ic-eng-zero: " + ", ".join(f"x{tag}.{e}" for e in ENG)
                  + " forced to 0 in the operating point (writes nothing)")
        deck = head + "\n".join(
            _control(tb, tag, args.until, args.bits, args.analog)
        )
        deck_path = work / f"readout_{point.corner_id}.spice"
        deck_path.write_text(deck)
        print(f"deck    : {deck_path}")
        print(f"point   : {point.corner_id}  loop={tag}  (stop="
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
            (work / f"readout_{point.corner_id}.log").write_text(out)

        abort = _ABORT_RE.search(out)
        if abort:
            print(f"RESULT  : ABORT at t = {abort['t']} s "
                  f"(timestep {abort['h']}), trouble node {abort['node']}")
            return 1

        tables = _tables(out)
        rows = tables.get("core", [])
        if not rows:
            print("RESULT  : no readout table in the log -- did the run "
                  "produce output?")
            return 1
        bit_rows = tables.get("bits", [])

        print()
        print(f"conversions read out on v({tag}_drdy) > {vth:g} V; "
              f"{len(rows)} accepted timepoints")
        print()
        head = (f"{'#':>2}  {'drdy rise (s)':>14}  {'exp':>5}  "
                f"{'settled code':>12}  {'settled |err|':>13}  "
                f"{'inst max |err|':>14}  {'at (s)':>14}  {'dt after rise':>13}")
        if args.bits:
            head += f"  {'reg settle':>11}"
        print(head)
        worst_inst = 0.0
        worst_settled = 0.0
        for n, (i0, i1) in enumerate(_windows(rows, vth), start=1):
            t0 = rows[i0][0]
            span = rows[i0:i1 + 1]
            inst = max(span, key=lambda r: abs(r[2] - r[3]))
            inst_err = abs(inst[2] - inst[3])
            settled = span[-1]
            settled_err = abs(settled[2] - settled[3])
            worst_inst = max(worst_inst, inst_err)
            worst_settled = max(worst_settled, settled_err)
            line = (f"{n:>2}  {t0:>14.6e}  {settled[3]:>5.0f}  "
                    f"{settled[2]:>12.0f}  {settled_err:>13.0f}  "
                    f"{inst_err:>14.0f}  {inst[0]:>14.6e}  "
                    f"{inst[0] - t0:>13.3e}")
            if args.bits:
                st = _settle_time(bit_rows, t0, rows[i1][0], vth)
                line += f"  {'n/a' if st is None else f'{st:.3e}':>11}"
            print(line)
            if args.rows:
                lo = max(i0, rows.index(inst) - args.rows // 2)
                for r in rows[lo:lo + args.rows]:
                    print(f"      t={r[0]:.6e}  drdy={r[1]:7.4f}  "
                          f"code={r[2]:6.0f}  exp={r[3]:6.0f}  "
                          f"|err|={abs(r[2] - r[3]):6.0f}")
        print()
        print(f"worst INSTANTANEOUS |code-exp| over all windows : "
              f"{worst_inst:.0f} LSB   <- what `meas MAX v({tag}_aerr)` reports")
        print(f"worst SETTLED       |code-exp| over all windows : "
              f"{worst_settled:.0f} LSB   <- what the conversions actually "
              f"produced")

        print()
        print("what `meas tran MAX v(%s_aerr)` would report if the drdy gate "
              "were held off" % tag)
        print("for a settling guard after each drdy rise (0 ns = the "
              "committed b%serr gate):" % tag)
        print(f"  {'guard (ns)':>10}  {'MAX |code-exp| (LSB)':>21}  "
              f"{'conversions still wrong':>23}")
        spans = _windows(rows, vth)
        for g in GUARDS_NS:
            worst = 0.0
            wrong = 0
            for i0, i1 in spans:
                t0 = rows[i0][0]
                kept = [r for r in rows[i0:i1 + 1] if r[0] - t0 >= g * 1e-9]
                if not kept:
                    continue
                m = max(abs(r[2] - r[3]) for r in kept)
                worst = max(worst, m)
                if m > 0.5:
                    wrong += 1
            print(f"  {g:>10.2f}  {worst:>21.0f}  {wrong:>23d}")

        if args.bits and bit_rows:
            print()
            print("output register at the END of each drdy window "
                  "(MSB c9 .. LSB c0):")
            for n, (_, i1) in enumerate(_windows(rows, vth), start=1):
                t1 = rows[i1][0]
                near = min(bit_rows, key=lambda r: abs(r[0] - t1))
                word = "".join("1" if v > vth else "0" for v in near[1:])
                print(f"  #{n:<2} t={near[0]:.6e}  c9..c0 = {word}  "
                      f"= {int(word, 2):>4}")

        if args.analog and args.trials:
            t0s, _, t1s = args.trials.partition(",")
            lo, hi = float(t0s), float(t1s)
            print()
            print(f"bit-trial detail over [{lo:g}, {hi:g}] s "
                  f"(clk / topp-topn / cmpo):")
            for r in tables.get("analog", []):
                if lo <= r[0] <= hi:
                    print(f"  t={r[0]:.7e}  clk={r[1]:7.4f}  "
                          f"topp-topn={(r[2] - r[3]) * 1e3:+11.6f} mV  "
                          f"cmpo={r[4]:7.4f}")
        print("RESULT  : completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
