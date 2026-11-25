#!/usr/bin/env python3
"""Append-only record writer for the ADC_BLOCK offset-MC estimator (issue #454,
sim/adc-offset-mc/README.md sections 6.4, 6.6, 6.7 item 5).

Turns one or more `klt sim` reports (one per PVT point / population) into a
machine record (`<record-id>.json`, schema below) and a human record
(`<record-id>.md`) that carry the provenance every other recorded campaign
carries: netlist hash and closure, model deck hash, corners, toolchain
versions, backend/job, base seed and every per-sample seed.

    record_writer.py --record-id ID --out-dir DIR [--kind qualification|campaign]
                     --population LABEL=REPORT.json[:null] ... [--note TEXT]

Rules enforced here, each with a negative control in sim/tests/test_adc_offset_mc_record.py:

* APPEND-ONLY: files are created exclusively; an existing record id is never
  overwritten (a correction is a new id with `supersedes`).
* DUPLICATE SEEDS ARE REJECTED, not averaged: a per-sample seed that appears twice
  among mismatch-on draws anywhere in the record, or a draw with no seed, raises
  RecordError and nothing is written.
* ALL-IDENTICAL SAMPLES ARE A PATH FAILURE: a mismatch-on population with >= 2 valid
  draws and a single distinct value is flagged `path_failure`, never summarised as a
  "tight distribution" (the record status becomes `path_failure`, exit code 1).
* FAILED / CENSORED draws are listed with seed and reason and counted; never dropped.
* LAG-1 AUTOCORRELATION of the sample_index-ordered offsets is reported with the
  +/- 2/sqrt(n) band (sanity check on the seed generator).

A `qualification` record is explicitly not a claim: `claim` is null, no spec row is
evaluated, and `offset_row_touched` is false. No verdict is computed anywhere here;
the offset definition is DR-0038's decision, not this tool's.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_pilot as A  # noqa: E402
import gen_pilot as G  # noqa: E402

SCHEMA = "gf180-sar-adc/adc-offset-mc-record/1"
KINDS = ("qualification", "campaign")
FAILURE_RATE_LIMIT = 0.01      # README 6.6: no verdict above a 1 % failure rate
MIN_N_AUTOCORR = 3


class RecordError(ValueError):
    """The inputs cannot be written as a valid record (nothing is written)."""


REPO_ROOT = Path(__file__).resolve().parents[3]


def repo_rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lag1_autocorrelation(xs: list[float]) -> float | None:
    """r1 = sum (x_i - m)(x_{i+1} - m) / sum (x_i - m)^2; None if undefined (n < 3 or zero variance)."""
    n = len(xs)
    if n < MIN_N_AUTOCORR:
        return None
    m = sum(xs) / n
    den = sum((x - m) ** 2 for x in xs)
    if den == 0.0:
        return None
    return sum((xs[i] - m) * (xs[i + 1] - m) for i in range(n - 1)) / den


def population_summary(samples: list[dict], mismatch_on: bool, n_requested: int) -> dict:
    """Per-population statistics. Failed draws stay in `failed`; nothing is filtered silently."""
    valid = sorted((s for s in samples if s.get("vos_v") is not None), key=lambda s: s["sample_index"] if s["sample_index"] is not None else -1)
    failed = [{"sample_index": s.get("sample_index"), "seed": s.get("seed"), "corner_id": s.get("corner_id"),
               "reason": s.get("failure") or "no value"} for s in samples if s.get("vos_v") is None]
    vals = [s["vos_v"] for s in valid]
    st = A.stats(vals)
    distinct = len({round(v, 9) for v in vals})
    path_failure = None
    if mismatch_on and len(vals) >= 2 and distinct == 1:
        path_failure = (f"all {len(vals)} valid draws read the identical value {vals[0] * 1e3:.3f} mV: "
                        "a failure of the path (seed not applied / mismatch inactive), not a tight distribution")
    r1 = lag1_autocorrelation(vals)
    bound = 2 / math.sqrt(len(vals)) if vals else None
    hyst = [s["hysteresis_v"] for s in valid if "hysteresis_v" in s]
    hyst_out = None
    if hyst:
        hyst_out = {
            "definition": "hysteresis = up_threshold - down_threshold (ascending minus descending staircase)",
            "n": len(hyst), "mean_mv": statistics.fmean(hyst) * 1e3,
            "min_mv": min(hyst) * 1e3, "max_mv": max(hyst) * 1e3,
            "n_exceeding_one_step": sum(1 for s in valid if s.get("hysteresis_flag")),
        }
    n_ret = len(samples)
    return {
        "mismatch_on": mismatch_on,
        "n_requested": n_requested, "n_returned": n_ret, "n_valid": len(vals), "n_failed": len(failed),
        "n_missing": max(n_requested - n_ret, 0),
        "failure_rate": (len(failed) + max(n_requested - n_ret, 0)) / n_requested if n_requested else None,
        "failed": failed,
        "n_censored": sum(1 for f in failed if "censored" in f["reason"]),
        "stats": st,
        "distinct_values": distinct,
        "path_failure": path_failure,
        "lag1_autocorrelation": {
            "r1": r1, "bound_2_over_sqrt_n": bound,
            "within_bound": (abs(r1) <= bound) if (r1 is not None and bound is not None) else None,
            "n": len(vals),
        },
        "hysteresis": hyst_out,
        "draws": [{k: s.get(k) for k in ("sample_index", "seed", "mismatch_seed", "corner_id", "vos_v", "vos_up_v",
                                          "vos_down_v", "hysteresis_v", "bits", "bits_down")
                   if k in s} for s in sorted(samples, key=lambda s: (s.get("sample_index") is None, s.get("sample_index")))],
    }


def population_provenance(rep: dict, report_path: Path) -> dict:
    env = rep.get("environment", {})
    prov = rep.get("provenance", {})
    remote = env.get("remote") or {}
    corners = rep.get("corners", [])
    return {
        "report_path": repo_rel(report_path),
        "report_sha256": sha256_file(report_path),
        "report_status": rep.get("status"),
        "netlist": rep.get("netlist"),
        "netlist_sha256": env.get("netlist_sha256"),
        "netlist_closure": env.get("netlist_closure"),
        "models_lib_sha256": env.get("models_lib_sha256"),
        "klt_version": prov.get("klt_version"),
        "klayout_version": prov.get("klayout_version"),
        "pdk": prov.get("pdk"),
        "engine": env.get("engine"), "engine_version": env.get("engine_version"),
        "backend": remote.get("provider", "local") if remote else "local",
        "job_id": remote.get("job_id"),
        "runner_klt_version": remote.get("runner_klt_version"),
        "runner_compatibility": remote.get("runner_compatibility"),
        "elapsed_seconds": remote.get("elapsed_seconds"),
        "monte_carlo": {k: v for k, v in (env.get("monte_carlo") or {}).items() if k in ("n", "seed", "vary")},
        "corner_grid": sorted({(c.get("process"), json.dumps(c.get("supply_v"), sort_keys=True), c.get("temperature_c"))
                               for c in corners}, key=str),
    }


def load_population(label: str, report_path: Path, mismatch_on: bool = True) -> dict:
    rep = json.loads(Path(report_path).read_text())
    samples = [A.sample_from_corner(c) for c in rep.get("corners", [])]
    mc = (rep.get("environment", {}).get("monte_carlo") or {})
    n_req = mc.get("n") or len(samples)
    prov = population_provenance(rep, Path(report_path))
    prov["corner_grid"] = [list(g) for g in prov["corner_grid"]]
    return {"label": label, "mismatch_on": mismatch_on, "provenance": prov,
            "summary": population_summary(samples, mismatch_on, n_req)}


def check_seeds(populations: list[dict]) -> None:
    """Reject duplicate / missing per-sample seeds among mismatch-on draws, across the whole record."""
    seen: dict[int, str] = {}
    for p in populations:
        if not p["mismatch_on"]:
            continue
        for d in p["summary"]["draws"]:
            s = d.get("seed")
            where = f"{p['label']}[{d.get('sample_index')}]"
            if s is None:
                raise RecordError(f"draw {where} has no per-sample seed; provenance incomplete, record rejected")
            if s in seen:
                raise RecordError(f"duplicate seed {s}: {seen[s]} and {where}; duplicated draws are rejected, not averaged")
            seen[s] = where


def build_record(populations: list[dict], record_id: str, kind: str = "qualification", note: str = "",
                 supersedes: str | None = None, timestamp: str = "") -> dict:
    if kind not in KINDS:
        raise RecordError(f"kind must be one of {KINDS}")
    if not populations:
        raise RecordError("no populations")
    check_seeds(populations)
    flags = []
    for p in populations:
        s = p["summary"]
        if s["path_failure"]:
            flags.append(f"{p['label']}: PATH FAILURE: {s['path_failure']}")
        if s["failure_rate"] and s["failure_rate"] > FAILURE_RATE_LIMIT:
            flags.append(f"{p['label']}: failure rate {s['failure_rate']:.1%} exceeds {FAILURE_RATE_LIMIT:.0%} "
                         "(no campaign verdict may be given, README 6.6)")
        if p["provenance"].get("runner_compatibility") == "mismatch":
            flags.append(f"{p['label']}: fleet runner klt {p['provenance'].get('runner_klt_version')} != client "
                         f"{p['provenance'].get('klt_version')} (README 6.7 item 2)")
    status = "path_failure" if any(p["summary"]["path_failure"] for p in populations) else "recorded"
    return {
        "schema": SCHEMA,
        "record_id": record_id,
        "kind": kind,
        "status": status,
        "claim": None if kind == "qualification" else "per-corner offset population (no verdict computed by this tool)",
        "claim_note": ("QUALIFICATION, NOT A CLAIM: exercises the estimator and record path; no spec row is "
                       "evaluated, no pass/fail is given, the Offset row stays Unmeasured.")
        if kind == "qualification" else
        "Statistics only; the verdict definition is DR-0038's, not this tool's.",
        "offset_row_touched": False,
        "supersedes": supersedes,
        "timestamp": timestamp,
        "estimator": {
            "step_mv": G.STEP_V * 1e3, "lsb_se_mv": A.LSB_SE_V * 1e3,
            "quantisation_sigma_mv": G.STEP_V / math.sqrt(12) * 1e3,
            "pilot_range_mv": [G.diffs()[0] * 1e3, G.diffs()[-1] * 1e3],
            "screening_range_mv": [G.screen_up()[0] * 1e3, G.screen_up()[-1] * 1e3],
        },
        "flags": flags,
        "note": note,
        "populations": populations,
    }


def validate_record(rec: dict) -> list[str]:
    """Schema check; returns a list of problems (empty = valid)."""
    bad = []
    req = {"schema": str, "record_id": str, "kind": str, "status": str, "offset_row_touched": bool,
           "estimator": dict, "flags": list, "populations": list}
    for k, t in req.items():
        if k not in rec:
            bad.append(f"missing {k}")
        elif not isinstance(rec[k], t):
            bad.append(f"{k} has wrong type")
    if bad:
        return bad
    if rec["schema"] != SCHEMA:
        bad.append("unknown schema")
    if rec["kind"] not in KINDS:
        bad.append("bad kind")
    if rec["offset_row_touched"]:
        bad.append("a record must not touch the Offset row")
    if rec["kind"] == "qualification" and rec.get("claim") is not None:
        bad.append("a qualification record carries no claim")
    if not rec["populations"]:
        bad.append("no populations")
    for p in rec["populations"]:
        pr, sm = p.get("provenance", {}), p.get("summary", {})
        for k in ("netlist_sha256", "models_lib_sha256", "klt_version", "engine_version", "corner_grid", "monte_carlo"):
            if not pr.get(k):
                bad.append(f"{p.get('label')}: provenance missing {k}")
        for k in ("n_requested", "n_returned", "n_valid", "failed", "lag1_autocorrelation", "draws"):
            if k not in sm:
                bad.append(f"{p.get('label')}: summary missing {k}")
        if p.get("mismatch_on") and any(d.get("seed") is None for d in sm.get("draws", [])):
            bad.append(f"{p.get('label')}: draw without seed")
        if sm.get("n_valid", 0) + sm.get("n_failed", 0) != sm.get("n_returned"):
            bad.append(f"{p.get('label')}: valid + failed != returned (a draw was dropped)")
    return bad


def _fmt(x, spec=".3f"):
    return "n/a" if x is None else format(x, spec)


def render_markdown(rec: dict) -> str:
    L = [f"# Record {rec['record_id']}", "",
         f"- **Record ID**: {rec['record_id']}",
         f"- **Kind**: `{rec['kind']}`; **status**: `{rec['status']}`",
         f"- **Claim**: {rec['claim'] or 'none'}",
         f"- **Claim note**: {rec['claim_note']}",
         "- **Offset row touched**: no (`spec/` row, README spec row and `sim/characterization-summary.md` unchanged)",
         f"- **Supersedes**: {rec['supersedes'] or 'none'}",
         f"- **Timestamp / author**: {rec['timestamp'] or 'deterministic (fixture)'} / agent (loom builder)",
         f"- **Estimator**: step {rec['estimator']['step_mv']:.2f} mV, LSB_se {rec['estimator']['lsb_se_mv']:.4f} mV, "
         f"quantisation sigma {rec['estimator']['quantisation_sigma_mv']:.4f} mV", ""]
    if rec["note"]:
        L += [rec["note"], ""]
    L += ["## Flags", ""] + ([f"- {f}" for f in rec["flags"]] or ["- none"]) + [""]
    for p in rec["populations"]:
        pr, sm = p["provenance"], p["summary"]
        st = sm["stats"]
        L += [f"## Population `{p['label']}` ({'mismatch on' if p['mismatch_on'] else 'mismatch OFF (null control)'})", "",
              f"- Report: `{pr['report_path']}` (sha256 `{pr['report_sha256']}`), klt status `{pr['report_status']}`",
              f"- Netlist: `{(pr['netlist'] or {}).get('path')}` sha256 `{pr['netlist_sha256']}`",
              "- Netlist closure: " + "; ".join(f"`{c['path']}` `{c['sha256'][:12]}`" for c in (pr['netlist_closure'] or [])),
              f"- Model deck sha256: `{pr['models_lib_sha256']}`",
              f"- Toolchain: klt `{pr['klt_version']}`, KLayout `{pr['klayout_version']}`, "
              f"{pr['engine']} `{pr['engine_version']}`, PDK `{(pr['pdk'] or {}).get('name')}` "
              f"({(pr['pdk'] or {}).get('version')})",
              f"- Backend: `{pr['backend']}`, job `{pr['job_id']}`, runner klt `{pr['runner_klt_version']}` "
              f"(compatibility `{pr['runner_compatibility']}`), {pr['elapsed_seconds']} s",
              f"- Corners: {pr['corner_grid']}",
              f"- Monte Carlo: `{json.dumps(pr['monte_carlo'])}` (base seed `{pr['monte_carlo'].get('seed')}`)", "",
              f"Draws: requested {sm['n_requested']}, returned {sm['n_returned']}, valid {sm['n_valid']}, "
              f"failed {sm['n_failed']} (censored {sm['n_censored']}), missing {sm['n_missing']}.", ""]
        if st.get("n_valid"):
            L += [f"Offset (ascending threshold): mean {st['mean_mv']:.3f} mV, sd {st['sd_mv']:.3f} mV "
                  f"(Sheppard-corrected {st['sd_quantisation_corrected_mv']:.3f} mV), range "
                  f"{st['min_mv']:.3f} .. {st['max_mv']:.3f} mV, {sm['distinct_values']} distinct values.", ""]
        ac = sm["lag1_autocorrelation"]
        L += [f"Lag-1 autocorrelation (n={ac['n']}): r1 = {_fmt(ac['r1'])}, band +/- {_fmt(ac['bound_2_over_sqrt_n'])}, "
              f"within band: {ac['within_bound']}.", ""]
        if sm["hysteresis"]:
            h = sm["hysteresis"]
            L += [f"Hysteresis (up - down threshold): mean {h['mean_mv']:.3f} mV, {h['min_mv']:.3f} .. {h['max_mv']:.3f} mV; "
                  f"{h['n_exceeding_one_step']} draw(s) exceed one step.", ""]
        else:
            L += ["Hysteresis: not measured (ascending-only staircase).", ""]
        if sm["path_failure"]:
            L += [f"**PATH FAILURE**: {sm['path_failure']}", ""]
        L += ["Failed / censored draws (reported, never dropped): " + (
            "none" if not sm["failed"] else "; ".join(f"[{f['sample_index']}] seed {f['seed']}: {f['reason']}" for f in sm["failed"])), "",
            "| idx | seed | mismatch_seed | offset (mV) |", "|---|---|---|---|"]
        L += [f"| {d.get('sample_index')} | {d.get('seed')} | {d.get('mismatch_seed')} | "
              f"{_fmt(None if d.get('vos_v') is None else d['vos_v'] * 1e3, '.2f')} |" for d in sm["draws"]]
        L += [""]
    return "\n".join(L) + "\n"


def write_record(rec: dict, out_dir: Path) -> list[Path]:
    """Append-only: exclusive create. Raises FileExistsError rather than overwrite."""
    problems = validate_record(rec)
    if problems:
        raise RecordError("record fails schema validation: " + "; ".join(problems))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, mp = out_dir / f"{rec['record_id']}.json", out_dir / f"{rec['record_id']}.md"
    if jp.exists() or mp.exists():
        raise FileExistsError(f"record {rec['record_id']} already exists; mint a new id (append-only)")
    with open(jp, "x") as f:
        f.write(json.dumps(rec, indent=2, sort_keys=True, default=str) + "\n")
    with open(mp, "x") as f:
        f.write(render_markdown(rec))
    return [jp, mp]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record-id", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--kind", choices=KINDS, default="qualification")
    ap.add_argument("--population", action="append", required=True, metavar="LABEL=REPORT[:null]",
                    help="a klt report; suffix ':null' marks a mismatch-off control")
    ap.add_argument("--note", default="")
    ap.add_argument("--supersedes")
    ap.add_argument("--timestamp", default="")
    a = ap.parse_args(argv)
    pops = []
    for spec in a.population:
        label, _, path = spec.partition("=")
        null = path.endswith(":null")
        pops.append(load_population(label, Path(path[:-5] if null else path), mismatch_on=not null))
    try:
        rec = build_record(pops, a.record_id, a.kind, a.note, a.supersedes, a.timestamp)
        paths = write_record(rec, a.out_dir)
    except (RecordError, FileExistsError) as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 2
    for p in paths:
        print(f"wrote {p}")
    for f in rec["flags"]:
        print("FLAG", f)
    return 1 if rec["status"] == "path_failure" else 0


if __name__ == "__main__":
    sys.exit(main())
