#!/usr/bin/env python3
"""The ngspice probe mechanics shared by the two read-only probe scripts.

`probe_cmp_convergence.py` (#296/#310) and `probe_code_readout.py` (#320)
each compose exactly the deck `sim/run_corners.py` would compose for one PVT
point, replace the manifest's measurement `.control` block with their own
timepoint-printing one, run ngspice on it, and classify the run's outcome
from the log. #320 forked that harness before #343 hardened it, and the two
copies then drifted on two real failure modes (issue #973): a relative
`--keep` directory handed ngspice a deck path it could not reopen, and
truncated / OOM / fatal runs were reported as `RESULT  : completed`. Both
probes now take the control-block shell, the bannered-table parser, the
PVT/workspace CLI scaffolding and the run classifier from here, so a
hardening landed on one probe cannot fail to cross to the other again.

This module is a helper, not a driver: it mints no evidence records (it is
deliberately absent from `DRIVERS` in `sim/tests/test_flow_env.py`) and owns
no file hasher -- `flow_env.py` does (issues #801/#847).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

#: `gen_sar_logic._timing_body`/`_functional_body` emit one of these banners
#: ahead of every loop, and nothing else in the deck starts with it -- so the
#: composed testbench can be split into per-loop sections without reaching
#: back into the generator (issue #310's `--only-loops`).
_LOOP_BANNER_RE = re.compile(r"^\* ---- loop (?P<tag>\w+) ----$", re.MULTILINE)

#: The one abort this probe family exists to measure, with the fields its
#: verdict quotes: `doAnalyses: TRAN:  Timestep too small; time = ..., 
#: timestep = ...: trouble with node "..."` (ngspice prints the detail after
#: the `doAnalyses:` prefix; only the detail is matched here).
_ABORT_RE = re.compile(
    r"Timestep too small; time = (?P<t>[0-9.eE+-]+), "
    r"timestep = (?P<h>[0-9.eE+-]+): trouble with node \"(?P<node>[^\"]+)\""
)

#: Deaths that are NOT a step-control abort. Aligned with
#: `sim/harness/runner.py`'s `_ABORT_RE` markers (`doAnalyses:`,
#: `simulation(s) aborted`), so a transient ngspice gave up on by any path
#: other than `Timestep too small` -- a non-timestep `doAnalyses:` failure,
#: a `tran`/`run simulation(s) aborted` line, an out-of-memory kill
#: (`Error: memory required ...`, observed on issue #343's `lossy` arm), a
#: fatal banner -- is rejected instead of read as a completed run. That is
#: issue #341's defect class (a run that produced output is not a run that
#: finished), in the instrument rather than in the runner. The
#: timestep-abort line itself starts with `doAnalyses:` and is excluded here
#: so `_ABORT_RE`'s more specific verdict wins; `classify_run` checks the
#: abort first regardless.
_FATAL_RE = re.compile(
    r"^(?:ERROR: fatal error in ngspice[^\n]*"
    r"|Error: memory required[^\n]*"
    r"|\s*Fatal error:[^\n]*"
    r"|[^\n]*simulation\(s\) aborted[^\n]*"
    r"|doAnalyses:(?![^\n]*Timestep too small)[^\n]*)$",
    re.MULTILINE,
)

#: The control block's own last statement (`let n = length(time)`/`print n`).
#: Its absence means ngspice never reached the end of the script.
_STEPS_RE = re.compile(r"^n = ([0-9.eE+-]+)", re.MULTILINE)

#: ngspice's `set numdgt` for the probe tables. 10 is what #296 and #310 read
#: their evidence at, so it stays the default -- every table transcribed into
#: those documents is reproduced byte-for-byte by a run that passes nothing.
DEFAULT_NUMDGT = 10


def classify_run(out: str) -> tuple[str, int]:
    """Turn one ngspice log into (one-line verdict, process exit code).

    Three outcomes, deliberately distinct so a caller -- or a shell driving
    a matrix of arms -- can tell them apart:

    * ``0`` the transient reached its stop time,
    * ``1`` it aborted with `Timestep too small` (the thing the convergence
      probe exists to measure),
    * ``3`` it died some OTHER way and measured nothing. This one was added
      by issue #343: it used to be reported as ``0``/"completed", which is
      how that issue's `lossy` arm came within one reading of being written
      up as "the lossy line converges" on the strength of a run ngspice
      killed for want of memory a quarter of the way in.
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


def parse_section_tables(out: str,
                         section: str) -> dict[str, list[tuple[float, ...]]]:
    """Parse every `<section>`-bannered table in the log into numeric rows.

    Returns banner-suffix -> [(time, col0, col1, ...), ...]. ngspice's own
    `Index` header line and the index column itself are dropped; a wrapped or
    malformed row is skipped rather than allowed to kill the table.
    """
    tables: dict[str, list[tuple[float, ...]]] = {}
    key: str | None = None
    for line in out.splitlines():
        if line.startswith(section):
            key = line[len(section):].split()[0]
            tables.setdefault(key, [])
        elif key is not None and re.match(r"^\d+\t", line):
            fields = line.split("\t")[1:]
            try:
                tables[key].append(tuple(float(f) for f in fields if f != ""))
            except ValueError:      # a wrapped or malformed row -- skip it
                continue
    return tables


def tran_with_stop(tb, until: str | None) -> str:
    """The manifest's `tran` line, with the stop time rewritten when a probe
    shortens the window (`--until`). `fields[2]` is `tran <step> <stop>
    <start> <max>`'s stop time; nothing else on the line moves."""
    tran = next(a for a in tb.analyses if a.split()[0] == "tran")
    if until is not None:
        fields = tran.split()
        fields[2] = until               # tran <step> <stop> <start> <max>
        tran = " ".join(fields)
    return tran


def build_control_block(tb, *, until: str | None, section: str,
                        prints: list[tuple[str, str]],
                        save: list[str] | None = None,
                        numdgt: int = DEFAULT_NUMDGT) -> list[str]:
    """The `.control` shell both probes compose in place of the manifest's
    measurement block, so nothing a probe prints can be mistaken for a
    scored measurement.

    `prints` is a list of `(key, expressions)` pairs; each becomes its own
    `echo <section> <key> <expressions>` / `print <expressions>` pair, so
    one unresolvable name cannot empty another table's print (issue #911).
    `save`, when given, is emitted ahead of the analysis -- ngspice's `save`
    only takes effect for an analysis that has not run yet, and the list is
    what keeps a long transient inside memory (issue #343's `lossy` arm OOM
    without it). The `let n = length(time)` / `print n` tail is the
    end-of-control sentinel `_STEPS_RE` classifies on: a log missing it is a
    run that never finished.
    """
    lines = [".control", f"set numdgt={numdgt}", "set noaskquit",
             "set num_threads=1", "set width=512", "set nobreak"]
    if save is not None:
        lines.append("  save " + " ".join(save))
    lines.append(f"  {tran_with_stop(tb, until)}")
    for key, exprs in prints:
        lines.append(f"  echo {section} {key} {exprs}")
        lines.append(f"  print {exprs}")
    lines += ["  let n = length(time)", "  print n", ".endc", ".end", ""]
    return lines


def add_pvt_args(p: argparse.ArgumentParser, until_example: str) -> None:
    """The PVT-point flags every probe shares (`--corner`, `--temp`,
    `--vdd`, `--until`)."""
    p.add_argument("--corner", default="tt")
    p.add_argument("--temp", type=float, default=27.0)
    p.add_argument("--vdd", type=float, default=3.30)
    p.add_argument("--until", default=None,
                   help="shorten the transient stop time, e.g. "
                        f"{until_example}")


def add_workspace_args(p: argparse.ArgumentParser, timeout: int) -> None:
    """The workspace flags every probe shares (`--timeout`, `--keep`)."""
    p.add_argument("--timeout", type=int, default=timeout)
    p.add_argument("--keep", metavar="DIR",
                   help="keep the composed deck and raw log in DIR")


def resolve_workspace(keep: str | None, tmp: str | Path) -> Path:
    """The probe's workspace dir, ABSOLUTE.

    `.resolve()` matters: ngspice is launched with `cwd=work`, so a RELATIVE
    `--keep` would compose `deck_path` relative to the invocation directory
    and then hand that same relative string to a process whose cwd is the
    keep directory itself -- "No such file or directory", with the deck
    sitting right there (`probe_cmp_convergence.py`'s #343 fix, which
    `probe_code_readout.py`'s fork never received; issue #973 drift bug 1).
    """
    return Path(keep).resolve() if keep else Path(tmp)


def run_deck(ngspice: str, deck_path: Path, work: Path,
             timeout: int) -> tuple[str, bool]:
    """Run one composed deck in `work`; returns (combined output, timed_out)."""
    try:
        proc = subprocess.run([ngspice, "-b", str(deck_path)],
                              capture_output=True, text=True,
                              timeout=timeout, cwd=work, check=False)
    except subprocess.TimeoutExpired:
        return "", True
    return proc.stdout + "\n" + proc.stderr, False
