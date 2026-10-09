#!/usr/bin/env python3
"""Issue #459: trace tp_inj_signal_dep_lsb between two committed dr0014-sampling runs.

Reads ONLY committed evidence -- the two records, their netlist snapshots and
their raw per-corner ngspice logs -- and prints a deterministic report. Runs
no simulation. Re-run from the repository root:

    python3 -I sim/dr0014-sampling/investigations/20261009-issue-459-trace.py

Default pair: governing record 20260923-104443-904af96 (A) against the issue
#393 ideal-supply control arm 20261007-071907-800bf53 (B). Pass two other
record IDs of this experiment to compare a different pair.

What it reports, per corner and in total:

* deck identity -- sha256 of each netlist snapshot with its 4-line
  "Frozen netlist snapshot" header removed, against the record's own
  "Testbench netlist sha256";
* front-end state ngspice printed -- its compatibility-mode note, any
  "Warning:" line, the "No. of Data Rows" (accepted timepoints kept in the
  output plot);
* the measurement trace -- tp_inj_signal_dep_lsb recomputed from the five
  m_tp_inj_p_l*_lsb values each log printed, the levels that set its max and
  min, the per-level B-A shift, its common-mode (mean) part and its residue;
* harness transcription -- whether every record cell equals the harness's own
  _fmt() of the log value it came from (so parsing/rounding is excluded or
  quantified).
"""
from __future__ import annotations

import hashlib
import re
import statistics
import sys
from pathlib import Path

EXP = Path("sim/dr0014-sampling")
DEFAULT_A = "20260923-104443-904af96"
DEFAULT_B = "20261007-071907-800bf53"
LEVELS = range(5)
MEAS_RE = re.compile(r"^\s*m_(\w+)\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)\s*$")
ROWS_RE = re.compile(r"No\. of Data Rows\s*:\s*(\d+)")
COMPAT_RE = re.compile(r"^Note: (No compatibility mode selected!|Compatibility modes selected:.*)$", re.M)
WARN_RE = re.compile(r"^Warning:.*$", re.M)


def fmt(value: float) -> str:
    """sim/harness/report.py::_fmt, copied so the check is self-contained."""
    if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
        return f"{value:.6e}"
    return f"{value:.6g}"


def record_rows(record: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    header: list[str] = []
    rows: dict[str, dict[str, str]] = {}
    for line in record.read_text().splitlines():
        line = line.strip()
        if line.startswith("| corner-id |"):
            header = [c.strip() for c in line.strip("|").split("|")]
        elif header and line.startswith("| `"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == len(header):
                rows[cells[0].strip("`")] = dict(zip(header, cells))
        elif header and rows and not line.startswith("|"):
            break
    return header, rows


def snapshot_sha(snapshot: Path) -> str:
    lines = snapshot.read_bytes().split(b"\n")
    assert lines[0].startswith(b"* Frozen netlist snapshot"), snapshot
    return hashlib.sha256(b"\n".join(lines[4:])).hexdigest()


def recorded(record: Path, label: str) -> str:
    m = re.search(rf"^- {re.escape(label)}: (.*)$", record.read_text(), re.M)
    return m.group(1).strip("`") if m else "n/a"


def parse_log(log: Path) -> dict:
    text = log.read_text()
    meas = {}
    for line in text.splitlines():
        m = MEAS_RE.match(line)
        if m:
            meas[m.group(1)] = float(m.group(2))
    rows = ROWS_RE.findall(text)
    compat = COMPAT_RE.search(text)
    # The t = 0 operating point ngspice prints before the transient:
    # "name value" lines between the "Initial Transient Solution" banner and
    # the first progress line.
    op: dict[str, float] = {}
    start = text.find("Initial Transient Solution")
    stop = text.find("Reference value", start)
    for line in text[start:stop].splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                op[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return {
        "op": op,
        "meas": meas,
        "data_rows": int(rows[-1]) if rows else None,
        "compat": compat.group(1) if compat else "n/a",
        "warnings": sorted(set(WARN_RE.findall(text))),
        "sha": hashlib.sha256(text.encode()).hexdigest(),
    }


def signal_dep(meas: dict) -> tuple[float, int, int]:
    vals = [meas[f"tp_inj_p_l{i}_lsb"] for i in LEVELS]
    hi = max(LEVELS, key=lambda i: vals[i])
    lo = min(LEVELS, key=lambda i: vals[i])
    return vals[hi] - vals[lo], hi, lo


def main(a_id: str, b_id: str) -> int:
    recs = {k: EXP / "records" / f"{v}.md" for k, v in (("A", a_id), ("B", b_id))}
    print(f"# issue #459 trace: A={a_id}  B={b_id}\n")
    print("## Deck identity and recorded environment")
    for k, rid in (("A", a_id), ("B", b_id)):
        rec = recs[k]
        snap = EXP / "netlist-snapshots" / f"{rid}.spice"
        print(f"{k} record              : {rec}")
        print(f"{k} recorded deck sha256: {recorded(rec, 'Testbench netlist sha256')}")
        print(f"{k} snapshot body sha256: {snapshot_sha(snap)}")
        print(f"{k} manifest sha256     : {recorded(rec, 'Manifest sha256')}")
        print(f"{k} ngspice             : {recorded(rec, 'ngspice')}")
        print(f"{k} harness             : {recorded(rec, 'Harness')}")
        print(f"{k} git                 : {recorded(rec, 'git')}")
        print(f"{k} PDK                 : {recorded(rec, 'PDK')}")
        print(f"{k} wall time           : {recorded(rec, 'Wall time')}")
    print()

    header, rows = {}, {}
    for k in ("A", "B"):
        header[k], rows[k] = record_rows(recs[k])
    corners = list(rows["A"])

    print("## Per corner")
    print("corner | compat A | compat B | rows A | rows B | sig_dep A | sig_dep B | "
          "d sig_dep | hi/lo A | hi/lo B | mean d tp_inj_p | residue span | max|d| hold_l*")
    worst = {}
    transcription_mismatch = 0
    cm_shifts = []
    op_stats = []
    for corner in corners:
        logs = {k: parse_log(EXP / "corners" / (a_id if k == "A" else b_id) / f"{corner}.log")
                for k in ("A", "B")}
        # harness transcription: every record cell vs _fmt(log value)
        for k in ("A", "B"):
            for col in header[k][1:-1]:
                v = logs[k]["meas"].get(col)
                if v is None or fmt(v) != rows[k][corner][col]:
                    transcription_mismatch += 1
        sd, hl = {}, {}
        for k in ("A", "B"):
            sd[k], hi, lo = signal_dep(logs[k]["meas"])
            hl[k] = f"l{hi}/l{lo}"
            printed = logs[k]["meas"]["tp_inj_signal_dep_lsb"]
            assert abs(sd[k] - printed) <= 1e-9 * max(1.0, abs(printed)) + 1e-12, (corner, k, sd[k], printed)
        shifts = [logs["B"]["meas"][f"tp_inj_p_l{i}_lsb"] - logs["A"]["meas"][f"tp_inj_p_l{i}_lsb"]
                  for i in LEVELS]
        cm = statistics.fmean(shifts)
        cm_shifts.append(cm)
        resid = max(shifts) - min(shifts)
        dhold = max(abs(logs["B"]["meas"][f"hold_l{i}_lsb"] - logs["A"]["meas"][f"hold_l{i}_lsb"])
                    for i in LEVELS)
        opa, opb = logs["A"]["op"], logs["B"]["op"]
        assert opa.keys() == opb.keys(), corner
        op_diff = [k for k in opa if opa[k] != opb[k]]
        op_v = max((abs(opa[k] - opb[k]) for k in op_diff if "#branch" not in k), default=0.0)
        op_stats.append((corner, len(opa), len(op_diff), op_v))
        print(f"{corner} | {logs['A']['compat']} | {logs['B']['compat']} | "
              f"{logs['A']['data_rows']} | {logs['B']['data_rows']} | {sd['A']:.10e} | {sd['B']:.10e} | "
              f"{sd['B'] - sd['A']:+.3e} | {hl['A']} | {hl['B']} | {cm:+.4e} | {resid:.3e} | {dhold:.3e}")
        for k in ("A", "B"):
            for w in logs[k]["warnings"]:
                worst.setdefault((k, w), 0)
                worst[(k, w)] += 1
        if corner == "ff_-40c_3.63v":
            focus = (logs, shifts, sd)
    print()
    print("## t = 0 operating point printed by each log (node voltages + branch currents)")
    print("corner | printed OP values | values differing A vs B | max|d| over node voltages")
    for corner, n, nd, dv in op_stats:
        print(f"{corner} | {n} | {nd} | {dv:.3e}")
    print()
    print("## Warnings printed (count of corners)")
    for (k, w), n in sorted(worst.items()):
        print(f"{k}: {n:2d} x {w}")
    if not worst:
        print("none")
    print()
    print(f"## Harness transcription: {transcription_mismatch} record cells differ from _fmt(log value)")
    print()
    print("## Grid summary")
    for k in ("A", "B"):
        vals = {c: float(rows[k][c]["tp_inj_signal_dep_lsb"]) for c in corners}
        wc = max(vals, key=vals.get)
        print(f"{k} worst tp_inj_signal_dep_lsb: {vals[wc]} at {wc}")
    print(f"common-mode tp_inj_p shift B-A over 27 corners: min {min(cm_shifts):+.4e}, "
          f"max {max(cm_shifts):+.4e} LSB")
    print()
    logs, shifts, sd = focus
    print("## Focus corner ff_-40c_3.63v")
    for i in LEVELS:
        a = logs["A"]["meas"][f"tp_inj_p_l{i}_lsb"]
        b = logs["B"]["meas"][f"tp_inj_p_l{i}_lsb"]
        print(f"tp_inj_p_l{i}_lsb  A {a:.10e}  B {b:.10e}  B-A {b - a:+.10e}")
    print(f"signal_dep A {sd['A']:.10e}  B {sd['B']:.10e}  B-A {sd['B'] - sd['A']:+.10e}")
    print(f"log sha256 A {logs['A']['sha']}")
    print(f"log sha256 B {logs['B']['sha']}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main(*(args if len(args) == 2 else (DEFAULT_A, DEFAULT_B))))
