#!/usr/bin/env python3
"""Mint an append-only evidence record from this experiment's `klt sim` reports.

Issue #386. ``gen_requests.py`` writes three requests (one per supply rail);
each is run with ``klt sim request_<tag>.json --backend batch -o <dir>
--format json > <report>.json``. This script reads the three reports and
their per-corner ngspice logs and writes, per sim/README.md:

    netlist-snapshots/<record-id>.spice   shared netlist + the 3 wrapper bodies
    corners/<record-id>/<corner-id>.log   raw ngspice log per PVT point
    corners/<record-id>/klt-sim-<tag>.json  the raw `klt sim` report per rail
    records/<record-id>.md                the summary record

It refuses to overwrite an existing record-id (append-only).

Every number in the record is derived here from the reports' raw `.meas` /
`expr` values -- the derivation is the code below, not prose. Sign
convention: i(vddX) is the current INTO the source, so a delivered current
or charge reads negative in the report and is negated here.

Usage::

    python3 make_record.py --record-id 20261007-024742-5c211cb \\
        --report 2v97=/path/2v97.json --report 3v30=... --report 3v63=... \\
        --author "<who>" [--note "..."]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent.parent
sys.path.insert(0, str(HERE))
import gen_requests as G  # noqa: E402

T_W = G.BIT_NS * 1e-9                     # every event window is one bit cycle
EVENT_NAMES = {"a": "A", "b": "B", "c": "C"}
SUPPLY_BY_TAG = {f"{v:.2f}".replace(".", "v"): v for v in G.SUPPLIES_V}

#: The prior record this experiment is read against (read-only; never edited).
RAIL_RECORD = REPO / "sim/adc-rail-current/records/20260923-002945-1cefe83.md"

#: Sanity checks graded per corner. Bounds are rails against a broken deck,
#: not a budget -- this experiment has no spec row of its own (DR-0036 does).
CHECKS = {
    "dq_event_pc": (0.1, 40.12,
                    "largest baseline-subtracted event charge; upper rail is "
                    "DR-0036 route A's own bound (40.120 pC), which a measured "
                    "single-event charge cannot legitimately exceed"),
    "t_eq_ns": (0.005, 2.0,
                "equivalent width of the peak event; upper rail is the 2 ns "
                "timestep cap of the earlier deck -- a width at or above it "
                "would mean this run did not resolve anything that one could not"),
    "i_pk_ma": (1.0, 200.0, "peak of the summed vdd current (same sanity rails as sim/adc-rail-current/)"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corner_id(process: str, temp_c: float, vdd: float) -> str:
    return f"{process}_{temp_c:g}c_{vdd:.2f}v"


def load_rail_record() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not RAIL_RECORD.is_file():
        return out
    for line in RAIL_RECORD.read_text().splitlines():
        m = re.match(r"\| `([a-z]+_-?\d+c_[\d.]+v)` \|(.*)\|\s*PASS \|", line)
        if m:
            cells = [c.strip() for c in m.group(2).split("|")]
            out[m.group(1)] = {"i_vdd_peak_ua": float(cells[3]), "i_vdd_avg_ua": float(cells[7])}
    return out


def derive(meas: dict[str, float]) -> dict:
    """Per-corner derived quantities from the raw measurement dict."""
    events = []
    for k in G.CONVERSIONS:
        ib = {b: meas[f"ib{b}_{k:02d}"] for b in G.BRANCHES}
        ibase = sum(ib.values())
        for e in G.EVENTS:
            q = {b: meas[f"q{b}_{e}{k:02d}"] for b in G.BRANCHES}
            dq = -sum(q.values()) + ibase * T_W
            dq_cdac = -q["d"] + ib["d"] * T_W
            ipk = -meas[f"ipk_{e}{k:02d}"]
            events.append({
                "k": k, "e": e, "dq": dq, "dq_cdac": dq_cdac,
                "q_raw": -sum(q.values()), "ipk": ipk,
                "t_eq": dq / ipk if ipk > 0 else float("nan"),
            })
    peak_ev = max(events, key=lambda ev: ev["ipk"])
    big_ev = max(events, key=lambda ev: ev["dq"])
    per_type = {e: max((ev for ev in events if ev["e"] == e), key=lambda ev: ev["dq"]) for e in G.EVENTS}
    per_conv = {}
    for ev in events:
        per_conv[ev["k"]] = per_conv.get(ev["k"], 0.0) + ev["dq"]
    conv_k = max(per_conv, key=per_conv.get)
    iavg = -sum(meas[f"iavg_{b}"] for b in G.BRANCHES)
    return {
        "events": events,
        "peak": peak_ev, "big": big_ev, "per_type": per_type,
        "conv_k": conv_k, "conv_dq": per_conv[conv_k],
        "i_pk": -meas["isum_min"],
        "i_max": meas["isum_max"],
        "i_max_branch": {b: meas[f"imax_{b}"] for b in G.BRANCHES},
        "i_avg": iavg,
        "supply_v": meas["vddm"],
    }


def fmt(x: float, digits: int = 4) -> str:
    return f"{x:.{digits}g}"


def find_log(outdir: Path, artifacts_log: str | None, slug_hint: str) -> Path | None:
    if artifacts_log:
        p = Path(artifacts_log)
        if p.is_file():
            return p
        # a batch report names the fleet-side path; re-root it under outdir
        parts = p.parts
        for i in range(len(parts)):
            cand = outdir.joinpath(*parts[i:])
            if cand.is_file():
                return cand
    hits = sorted(outdir.rglob(f"{slug_hint}*/ngspice.log"))
    return hits[0] if hits else None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record-id", required=True)
    ap.add_argument("--report", action="append", required=True,
                    help="<tag>=<klt sim JSON report>, tag one of 2v97/3v30/3v63; "
                         "per-corner logs are looked up under the report's sibling "
                         "directory named <tag> (the -o dir) unless --outdir-<tag> is given")
    ap.add_argument("--outdir", action="append", default=[],
                    help="<tag>=<klt sim -o dir> (default: <report dir>/<tag>)")
    ap.add_argument("--author", required=True)
    ap.add_argument("--timestamp", required=True, help="ISO-8601 run start")
    ap.add_argument("--note", action="append", default=[])
    args = ap.parse_args(argv)

    rid = args.record_id
    rec_path = EXP / "records" / f"{rid}.md"
    if rec_path.exists():
        print(f"refusing to overwrite {rec_path} (append-only)", file=sys.stderr)
        return 2
    reports = dict(r.split("=", 1) for r in args.report)
    outdirs = dict(o.split("=", 1) for o in args.outdir)
    corners_dir = EXP / "corners" / rid
    corners_dir.mkdir(parents=True, exist_ok=True)

    rows = []           # (corner_id, derived, status, supply)
    envs = {}
    problems = []
    for tag in sorted(reports, key=lambda t: SUPPLY_BY_TAG[t]):
        rpath = Path(reports[tag])
        report = json.loads(rpath.read_text())
        shutil.copyfile(rpath, corners_dir / f"klt-sim-{tag}.json")
        envs[tag] = {"environment": report.get("environment", {}),
                     "provenance": report.get("provenance", {}),
                     "status": report.get("status")}
        outdir = Path(outdirs.get(tag, rpath.parent / tag))
        vdd = SUPPLY_BY_TAG[tag]
        for c in report.get("corners", []):
            cid = corner_id(c["process"], c["temperature_c"], vdd)
            meas = {m["name"]: m.get("value") for m in c.get("measurements", [])}
            missing = [n for n, v in meas.items() if v is None]
            slug = c["corner_id"].split("/")[0]
            log = find_log(outdir, (c.get("artifacts") or {}).get("log"),
                           f"{slug}_novdd_{str(c['temperature_c']).replace('-', 'n')}C")
            if log:
                shutil.copyfile(log, corners_dir / f"{cid}.log")
            else:
                problems.append(f"{cid}: no ngspice log found")
            if c.get("status") != "pass" or missing:
                problems.append(f"{cid}: klt status {c.get('status')}, {len(missing)} missing measurement(s)")
                rows.append((cid, None, "ERROR", vdd))
                continue
            rows.append((cid, derive(meas), "ok", vdd))

    order = {p: i for i, p in enumerate(G.PROCESS)}
    rows.sort(key=lambda r: (order[r[0].split("_")[0]], float(r[0].split("_")[1][:-1]), r[3]))

    # ---- frozen netlist snapshot -------------------------------------------
    shared = (HERE / G.SHARED_NETLIST).resolve()
    snap = EXP / "netlist-snapshots" / f"{rid}.spice"
    snap.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"* Frozen netlist snapshot for record {rid}",
             "* This is a verbatim copy taken at record time. Do not edit.",
             "* Part 1..3: the per-rail wrapper bodies; part 4: the shared netlist they .include."]
    for tag in sorted(SUPPLY_BY_TAG, key=SUPPLY_BY_TAG.get):
        w = HERE / f"tb_vdd_event_{tag}.spice"
        parts += ["", f"* ==== {w.relative_to(REPO)}  sha256 {sha256(w)}", w.read_text()]
    parts += ["", f"* ==== {shared.relative_to(REPO)}  sha256 {sha256(shared)}", shared.read_text()]
    snap.write_text("\n".join(parts))

    rail = load_rail_record()
    record = render(rid, rows, envs, problems, rail, shared, args)
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(record)
    print(f"wrote {rec_path.relative_to(REPO)}")
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems), file=sys.stderr)
    return 0


def grade(d: dict) -> tuple[str, list[str]]:
    vals = {"dq_event_pc": d["big"]["dq"] * 1e12, "t_eq_ns": d["peak"]["t_eq"] * 1e9,
            "i_pk_ma": d["i_pk"] * 1e3}
    bad = [f"{k}={fmt(v)} outside [{lo}, {hi}]" for k, (lo, hi, _) in CHECKS.items()
           for v in [vals[k]] if not lo <= v <= hi]
    return ("FAIL" if bad else "PASS"), bad


def ev_label(ev: dict) -> str:
    return f"{EVENT_NAMES[ev['e']]}{ev['k']}"


def render(rid, rows, envs, problems, rail, shared, args) -> str:
    ok = [(cid, d) for cid, d, s, _ in rows if d is not None]
    L: list[str] = []
    A = L.append
    A(f"# Record {rid}")
    A("")
    A(f"- **Record ID**: {rid}")
    A("- **Claim**: issue #386 -- DR-0036 Open question 1. A direct measurement, per PVT point, "
      "of the charge `ΔQ_event` the `vdd` island (vddc + vddd + vddt, one net in adc_block.gds) "
      "delivers in each array-wide CDAC switching event, the event's peak current and its "
      "equivalent width, and a `MAX` measure on the same branches that tests DR-0036 step 1's "
      "stated assumption that the rail never absorbs current. Not a ratified-spec row: an input "
      "to DR-0036's derived results.")
    A("- **Netlist provenance**: schematic (`sim/adc-power/testbench/tb_adc_power.spice`, unmodified, "
      "behind the per-rail wrapper bodies `sim/vdd-switching-event/testbench/tb_vdd_event_<rail>.spice`)")
    A("- **Corner matrix run**:")
    A("  - Process: tt, ss, ff")
    A("  - Temperature: -40 °C, 27 °C, 125 °C")
    A("  - Supply: 2.97 V, 3.30 V, 3.63 V")
    A(f"  - 27 point full-factorial grid (process × temperature × supply), {len(ok)} completed")
    A("  - Full PVT matrix per CLAUDE.md (−40/27/125 °C, ±10 % supply, process corners) -- the same "
      "grid as `sim/adc-rail-current/` record `20260923-002945-1cefe83`.")
    A("- **Statistical convention**: N/A (corner-matrix claim, not a distribution claim)")
    A("")
    A("## What was measured, exactly")
    A("")
    A("Same circuit, same stimulus, same 17 µs run and same 3 → 17 µs window as "
      "`sim/adc-rail-current/`; the **only** analysis change is the maximum timestep, "
      f"`tran {G.ANALYSIS_ARGS}` (was `tran 1n 17.000u 0 2n`). For each of the 14 conversions "
      "k = 3 … 16 (conversion k starts on the clock edge at t = k µs) the deck integrates each "
      "branch current over a one-bit-cycle (62.5 ns) window opening 1 ns before each of the three "
      "array-wide bottom-plate switching edges:")
    A("")
    for e, (off, desc) in G.EVENTS.items():
        A(f"- **{EVENT_NAMES[e]}** -- edge at t_k + {off:g} ns, {desc}.")
    A("")
    A("Between those edges only one cell per side switches per bit trial; on the 2 ns-cap probe of "
      "the peak corner no other excursion of the summed current exceeds 3 mA "
      "(`investigations/20261007-issue-386-timestep-convergence.md`).")
    A("")
    A("Derived per event (code: `testbench/make_record.py::derive`):")
    A("")
    A("```")
    A("ΔQ_event = −∫window (i_vddc + i_vddd + i_vddt) dt  −  I_static × 62.5 ns")
    A("I_static = −avg(i_vddc + i_vddd + i_vddt) over ph1..ph2 of the same conversion (2 bit cycles,")
    A("           no array switching, comparator still clocked -- so its per-cycle latch charge is")
    A("           in the baseline and subtracts out of the event, on average)")
    A("ΔQ_cdac  = the same on i_vddd alone (the CDAC driver branch)")
    A("I_pk     = −min(i_vddc + i_vddd + i_vddt) inside the window")
    A("t_eq     = ΔQ_event / I_pk     (DR-0036 step 2's equivalent rectangular width, now from a")
    A("                                measured charge and a resolved peak)")
    A("```")
    A("")
    A("`ΔQ_event` is a NET charge over the window: where the rail absorbs current inside the window "
      "(see the MAX result below) that charge is netted against what it delivers, which is what a "
      "decoupling capacitor sees.")
    A("")
    A("## Result")
    A("")
    A("Per PVT point. *Peak event* = the event with the largest `I_pk` among all 42 "
      "(DR-0036's width is the width of the peak); *largest-charge event* = the event with the "
      "largest `ΔQ_event`. `i_max` is the most positive summed current over 3 → 17 µs, i.e. the "
      "largest current the rail **absorbs** (positive = into the source).")
    A("")
    A("| corner-id | I_pk (mA) | peak event | ΔQ_event @ peak (pC) | ΔQ_cdac @ peak (pC) | t_eq @ peak (ns) "
      "| largest ΔQ_event (pC) [event] | ΣΔQ one conversion (pC) [k] | i_max absorbed (mA) | supply_v | pass/fail |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    fails = []
    for cid, d, status, _ in rows:
        if d is None:
            A(f"| `{cid}` | — | — | — | — | — | — | — | — | — | ERROR |")
            fails.append(cid)
            continue
        g, bad = grade(d)
        if g != "PASS":
            fails.append(f"{cid}: " + "; ".join(bad))
        p, b = d["peak"], d["big"]
        A(f"| `{cid}` | {fmt(d['i_pk']*1e3, 5)} | {ev_label(p)} | {fmt(p['dq']*1e12)} | {fmt(p['dq_cdac']*1e12)} "
          f"| {fmt(p['t_eq']*1e9, 3)} | {fmt(b['dq']*1e12)} [{ev_label(b)}] | {fmt(d['conv_dq']*1e12)} [{d['conv_k']}] "
          f"| {fmt(d['i_max']*1e3)} | {fmt(d['supply_v'])} | {g} |")
    A("")
    if ok:
        def span(key, scale, digits=4):
            vals = [(key(d) * scale, cid) for cid, d in ok]
            lo, hi = min(vals), max(vals)
            return f"{fmt(lo[0], digits)} (`{lo[1]}`) … {fmt(hi[0], digits)} (`{hi[1]}`)"
        A("Grid summary:")
        A("")
        A("| quantity | min … max over the 27 points |")
        A("|---|---|")
        A(f"| `I_pk` (mA) | {span(lambda d: d['i_pk'], 1e3, 5)} |")
        A(f"| `ΔQ_event` of the peak event (pC) | {span(lambda d: d['peak']['dq'], 1e12)} |")
        A(f"| `ΔQ_cdac` of the peak event (pC) | {span(lambda d: d['peak']['dq_cdac'], 1e12)} |")
        A(f"| `t_eq` of the peak event (ns) | {span(lambda d: d['peak']['t_eq'], 1e9, 3)} |")
        A(f"| largest single `ΔQ_event` (pC) | {span(lambda d: d['big']['dq'], 1e12)} |")
        for e in G.EVENTS:
            A(f"| largest `ΔQ_event` of type {EVENT_NAMES[e]} (pC) | {span(lambda d, e=e: d['per_type'][e]['dq'], 1e12)} |")
            A(f"| `t_eq` of that type-{EVENT_NAMES[e]} event (ns) | {span(lambda d, e=e: d['per_type'][e]['t_eq'], 1e9, 3)} |")
        A(f"| ΣΔQ over one conversion's three events (pC) | {span(lambda d: d['conv_dq'], 1e12)} |")
        A(f"| `i_max`, summed, absorbed (mA) | {span(lambda d: d['i_max'], 1e3)} |")
        for b, src in G.BRANCHES.items():
            A(f"| `i_max` on `{src}` alone (mA) | {span(lambda d, b=b: d['i_max_branch'][b], 1e3)} |")
        A("")
        absorbing = [cid for cid, d in ok if d["i_max"] > 0]
        A("### Does the rail ever absorb current? (DR-0036 step 1's assumption)")
        A("")
        if absorbing:
            A(f"**Yes, at {len(absorbing)} of {len(ok)} PVT points** (`i_max > 0` -- current flowing INTO "
              "a supply source). DR-0036 step 1 stated as an assumption, not a measurement, that the rail "
              "only ever delivers charge; that assumption is **not** borne out by this deck. The "
              "absorption is a real circuit current, not trapezoidal ringing: it survives at 25 ps and "
              "under Gear integration (investigation note). The per-branch rows above say which source "
              "takes it. DR-0036's route-A bound (`ΔQ_event ≤ ΔQ_conv`) depended on that assumption; "
              "this record replaces the bound with a measured `ΔQ_event`, so the dependency is now moot "
              "for the charge -- but it means `V_DD` sees a bidirectional transient (a brief overshoot "
              "as well as a droop), which a decoupling budget built only on droop does not describe.")
        else:
            A("**No** -- `i_max ≤ 0` at every PVT point: the rail only ever delivers current, so "
              "DR-0036 step 1's assumption holds on this deck.")
        A("")
        if rail:
            A("### Against `sim/adc-rail-current/` (2 ns timestep cap), same grid")
            A("")
            A("Same 3 → 17 µs window, same summed branch current, the only change being the timestep cap. "
              "The rail-current record's peak was stated to be a resolution-limited lower bound.")
            A("")
            A("| corner-id | I_pk @ 2 ns cap (mA) | I_pk @ 25 ps cap (mA) | Δ % | I_avg @ 2 ns (µA) | I_avg @ 25 ps (µA) | Δ % |")
            A("|---|---|---|---|---|---|---|")
            for cid, d in ok:
                r = rail.get(cid)
                if not r:
                    continue
                pk0, pk1 = r["i_vdd_peak_ua"] / 1e3, d["i_pk"] * 1e3
                av0, av1 = r["i_vdd_avg_ua"], d["i_avg"] * 1e6
                A(f"| `{cid}` | {fmt(pk0, 6)} | {fmt(pk1, 6)} | {100*(pk1-pk0)/pk0:+.2f} | {fmt(av0, 6)} | {fmt(av1, 6)} | {100*(av1-av0)/av0:+.2f} |")
            A("")
    A("### Sanity checks (graded per point)")
    A("")
    for k, (lo, hi, desc) in CHECKS.items():
        A(f"- `{k}` in [{lo}, {hi}] -- {desc}.")
    A("")
    A(f"- **Overall: {'PASS' if not fails and len(ok) == 27 else 'FAIL'}**"
      + ("" if not fails else " -- " + "; ".join(fails)))
    if problems:
        A("- Harness problems: " + "; ".join(problems))
    A("")
    A("## What this deck still does NOT measure")
    A("")
    A("Restated from `sim/adc-power/` and `sim/adc-rail-current/`, because it is still true here and "
      "is a separate reason every current above is a **lower** bound: the SAR sequencer and output "
      "register are DR-0010 rung-1 ideal XSPICE event-driven primitives and draw **no supply "
      "current** -- they contain no devices -- so the sequencer's own flip-flop and decode current "
      "is absent from every `I_pk`, `ΔQ_event` and `t_eq` in this record. The dominant digital term, "
      "driving the array's 72 bottom-plate T-gate legs, IS measured (those drivers are real devices "
      "on `vddd`). Closing the gap needs DR-0010 rung 3, which DR-0010 records as blocked on the open "
      "gf180mcu PDK shipping no 3.3 V standard-cell library. The timestep reason the earlier record "
      "gave for its peak being a lower bound is the one this record removes.")
    A("")
    A("Also unchanged from the shared deck: `V_REF` is a modelled external network and `V_cm` an ideal "
      "source, both outside the `vdd` island and not part of any number here; the `vdd` sources "
      "themselves are ideal (zero impedance), so this is the charge the circuit draws, not the droop "
      "any particular decoupling network would develop.")
    A("")
    A("## Tool gaps hit while producing this record (friction protocol)")
    A("")
    A("- The supply axis could not be a `corners.supply_v` axis: the shared deck takes its supply as a "
      "`.param` that also sets V_REF, V_cm, the clocks and the input, and `alter` cannot re-evaluate a "
      "`.param` (ngspice 46: `Error: no such device or model name vdd_val`, run continues at the old "
      "value). Hence three wrapper bodies and three requests. 2AMLogic/klayout-tools#2725.")
    A("- The batch fleet's `klt` rejected the first submission's `measurements[].expr` entries "
      "(`each request.measurements[] entry requires 'name' and 'spice'`) that the submitting `klt` had "
      "accepted; the report carried only `batch_job_failed: job command exited 1`, and the cause was "
      "visible only in the job's `harness.log` in the job bucket. Reworked to plain `.meas` cards "
      "(`par('...')` for the summed current). 2AMLogic/klayout-tools#2719 (version skew), #2733 "
      "(failed-job error envelope).")
    A("- `klt sim` forces `save all`, so a 25 ps-cap 17 µs run of this deck holds every node and branch "
      "(~1.75 GB resident at 7.4 µs on the local probe); each request was sharded across 3 hosts "
      "(`--hosts 3`) to keep a fleet instance's memory bounded. 2AMLogic/klayout-tools#2732.")
    A("- The report's `netlist_sha256` covers only the wrapper body, not the shared netlist it "
      "`.include`s, so this record stamps the shared netlist's hash itself (Environment below). "
      "2AMLogic/klayout-tools#2799.")
    A("- `provenance.klt_version` in each report is the SUBMITTING host's `klt`; the fleet image's own "
      "`klt` version is not reported (#2719).")
    A("")
    A("## Links")
    A("")
    A("- Testbench: `sim/vdd-switching-event/testbench/gen_requests.py` (generator, single source of truth), "
      "`request_{2v97,3v30,3v63}.json`, `tb_vdd_event_{2v97,3v30,3v63}.spice`, `make_record.py` (this record's derivation)")
    A("- Shared circuit: `sim/adc-power/testbench/tb_adc_power.spice`")
    A(f"- Netlist snapshot: `sim/vdd-switching-event/netlist-snapshots/{rid}.spice`")
    A(f"- Raw logs: `sim/vdd-switching-event/corners/{rid}/` (`<corner-id>.log`, plus the raw `klt sim` "
      "report per rail, `klt-sim-<rail>.json`, which carries every one of the 219 measurements per point)")
    A("- Timestep-convergence control: `sim/vdd-switching-event/investigations/20261007-issue-386-timestep-convergence.md`")
    A(f"- Read against: `sim/adc-rail-current/records/20260923-002945-1cefe83.md` (not superseded -- different claim)")
    A(f"- **Timestamp / author**: {args.timestamp}, {args.author}")
    A("- **Supersedes**: (none) -- a distinct claim (event charge and width), not a correction of "
      "`sim/adc-rail-current/`'s peak/average record, which stands as committed.")
    for n in args.note:
        A(f"- Note: {n}")
    A("")
    A("## Environment")
    A("")
    A("Everything needed to re-run this record:")
    A("")
    for tag in sorted(envs, key=lambda t: SUPPLY_BY_TAG[t]):
        env = envs[tag]["environment"]
        prov = envs[tag]["provenance"]
        remote = env.get("remote") or {}
        shards = remote.get("fleet") or ([remote] if remote else [])
        if shards:
            remote = {
                "job_id": ", ".join(str(s.get("job_id")) for s in shards),
                "instance_type": ", ".join(str(s.get("instance_type")) for s in shards),
                "lifecycle": ", ".join(sorted({str(s.get("lifecycle")) for s in shards})),
                "availability_zone": ", ".join(str(s.get("availability_zone")) for s in shards),
                "elapsed_seconds": ", ".join(str(s.get("elapsed_seconds")) for s in shards),
            }
        A(f"- Rail {SUPPLY_BY_TAG[tag]:.2f} V (`request_{tag}.json`): report status `{envs[tag]['status']}`; "
          f"engine {env.get('engine')} {env.get('engine_version')}; submitting klt {prov.get('klt_version')}; "
          f"PDK {(prov.get('pdk') or {}).get('name')} {(prov.get('pdk') or {}).get('version')}; "
          f"models sha256 `{env.get('models_lib_sha256')}`"
          + (f"; backend batch job `{remote.get('job_id')}` on {remote.get('instance_type')} "
             f"({remote.get('lifecycle')}, {remote.get('availability_zone')}), {remote.get('elapsed_seconds')} s"
             if remote else "; backend local"))
    A(f"- Shared netlist sha256: `{sha256(shared)}`")
    for tag in sorted(SUPPLY_BY_TAG, key=SUPPLY_BY_TAG.get):
        A(f"- `tb_vdd_event_{tag}.spice` sha256 `{sha256(HERE / f'tb_vdd_event_{tag}.spice')}`, "
          f"`request_{tag}.json` sha256 `{sha256(HERE / f'request_{tag}.json')}`")
    A(f"- Toolchain pins (`sim/toolchain.json`): open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b, ngspice ≥ 46")
    A(f"- Submitting host: `{subprocess.run(['klt', '--version'], capture_output=True, text=True).stdout.strip()}`")
    A(f"- git: `{git('rev-parse', 'HEAD')}` on `{git('rev-parse', '--abbrev-ref', 'HEAD')}`")
    A("")
    A("Per-corner model sections (`gen_requests.PROCESS`, the harness's own bundles):")
    A("")
    for n, s in G.PROCESS.items():
        A(f"- `{n}`: {' '.join(s)}")
    A("")
    A("Re-run:")
    A("")
    A("```")
    A("cd sim/vdd-switching-event/testbench")
    A("python3 gen_requests.py --check")
    A("for r in 2v97 3v30 3v63; do   # three requests; each is a 9-point grid")
    A("  klt sim request_$r.json --backend batch -o out/$r --format json > out/$r.json")
    A("done")
    A("python3 make_record.py --record-id <new-id> --report 2v97=out/2v97.json \\")
    A("  --report 3v30=out/3v30.json --report 3v63=out/3v63.json --author <you> --timestamp <iso>")
    A("```")
    A("")
    A("---")
    A("")
    A("Written by `sim/vdd-switching-event/testbench/make_record.py`. Append-only: never edit or delete "
      "this file — a re-run or correction mints a new record-id and points back here via "
      "**Supersedes** (see `sim/README.md`).")
    A("")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
