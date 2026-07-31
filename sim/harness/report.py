"""Summaries, spec checks, and append-only evidence records.

The output format here is the one ratified in ``sim/README.md``: a run
produces a Markdown summary record at

    sim/<experiment-slug>/records/<record-id>.md

alongside a frozen netlist at ``netlist-snapshots/<record-id>.spice`` and the
raw per-corner ngspice logs at ``corners/<record-id>/<corner-id>.log``.

``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``.

CLAUDE.md and ``sim/README.md``: "sim/ results are append-only evidence."
This module never overwrites an existing record -- on a collision it mints a
new (still conforming) record-id rather than clobbering, and corrections are
expected to reference the prior record via ``Supersedes``. Deleting evidence
is a human decision, not a script's.

Divergence from upstream gf180-bandgap: :func:`axis_sensitivity` and the
``*_spread_pct_by_axis`` checks. Upstream's grid-wide ``min_spread_pct``
only asserts that a measurement moved *somewhere* across the grid -- it
passes happily when the temperature axis moves and the process axis is stuck
on typical, which is precisely the silent failure this repo cannot afford.
Per-axis sensitivity pins each of process / temperature / supply separately.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import platform
import socket
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from . import HARNESS_VERSION, UPSTREAM_PATTERN
from .corners import (
    DEFAULT_SUPPLY_TOLERANCE,
    DEFAULT_TEMPERATURES_C,
    PvtPoint,
)
from .evidence import Extensions
from .pdk import Pdk
from .runner import PointResult
from .testbench import AXES, Testbench

#: Subdirectories of ``sim/<experiment-slug>/`` defined by ``sim/README.md``.
TESTBENCH_DIR = "testbench"
SNAPSHOT_DIR = "netlist-snapshots"
CORNERS_DIR = "corners"
RECORDS_DIR = "records"

#: Minimum number of distinct process corners for the matrix to count as
#: "full" without a written justification.
MIN_PROCESS_CORNERS = 3

#: How each axis slices the grid: the axis varies *within* a group, and the
#: other two axes are held fixed to form the group key.
_AXIS_GROUP_KEY = {
    "process": lambda p: (p["temp_c"], p["vdd"]),
    "temperature": lambda p: (p["corner"], p["vdd"]),
    "supply": lambda p: (p["corner"], p["temp_c"]),
}
_AXIS_LEVEL = {
    "process": lambda p: p["corner"],
    "temperature": lambda p: p["temp_c"],
    "supply": lambda p: p["vdd"],
}


def _git(*args: str, cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:  # pragma: no cover - git always present in this repo
        return ""


def git_provenance(repo_root: Path) -> dict:
    commit = _git("rev-parse", "HEAD", cwd=repo_root)
    dirty = bool(_git("status", "--porcelain", cwd=repo_root))
    return {
        "commit": commit or "unknown",
        "short": (commit[:7] if commit else "unknown"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root) or "unknown",
        "dirty": dirty,
    }


def format_record_id(short_sha: str, when: _dt.datetime) -> str:
    """``<YYYYMMDD>-<HHMMSS>-<short-git-sha>`` -- see ``sim/README.md``.

    The git sha is the *only* provenance carried in the id; a dirty tree is
    reported inside the record body instead, so the id keeps the exact shape
    the ratified convention specifies.
    """
    return f"{when.strftime('%Y%m%d-%H%M%S')}-{short_sha}"


def allocate_record_id(
    repo_root: Path,
    records_dir: Path,
    when: _dt.datetime | None = None,
    git: dict | None = None,
) -> str:
    """Mint a fresh, unused ``<record-id>``.

    Append-only: if a record with this id already exists (same second, same
    commit) we advance the timestamp until the id is free rather than
    overwriting or inventing a non-conforming suffix.
    """
    when = when or _dt.datetime.now(_dt.timezone.utc)
    short_sha = (git or git_provenance(repo_root))["short"]
    while True:
        record_id = format_record_id(short_sha, when)
        if not (records_dir / f"{record_id}.md").exists():
            return record_id
        when += _dt.timedelta(seconds=1)


def summarize(results: list[PointResult], measure_names: list[str]) -> dict:
    """Min / max / mean / spread of each measurement across the PVT grid."""
    summary: dict[str, dict] = {}
    ok = [r for r in results if r.status == "ok"]
    for name in measure_names:
        samples = [(r.measurements[name], r.point.corner_id) for r in ok if name in r.measurements]
        if not samples:
            summary[name] = {"n": 0}
            continue
        values = [v for v, _ in samples]
        lo_value, lo_at = min(samples, key=lambda s: s[0])
        hi_value, hi_at = max(samples, key=lambda s: s[0])
        mean = sum(values) / len(values)
        spread_pct = (hi_value - lo_value) / abs(mean) * 100.0 if mean else None
        summary[name] = {
            "n": len(values),
            "min": lo_value,
            "min_at": lo_at,
            "max": hi_value,
            "max_at": hi_at,
            "mean": mean,
            "spread_pct": spread_pct,
        }
    return summary


def _spread_pct(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if not mean:
        return None
    return (max(values) - min(values)) / abs(mean) * 100.0


def axis_sensitivity(results: list[PointResult], measure_names: list[str]) -> dict:
    """Per-axis spread: does *each* PVT axis move each measurement?

    For axis ``a``, the grid is sliced into groups in which the other two
    axes are held fixed, so the only thing varying inside a group is ``a``.
    The per-group spread is then reduced two ways:

    ``min_pct``  the *weakest* slice -- "every slice of the grid moved at
                 least this much when only this axis varied". This is what a
                 ``min_spread_pct_by_axis`` floor is checked against, so a
                 single stuck slice cannot hide behind the others.
    ``max_pct``  the *strongest* slice -- what a ``max_spread_pct_by_axis``
                 stability ceiling is checked against.

    ``levels`` is how many distinct values the axis actually took. Fewer than
    two means the axis was never swept, so **nothing** about it was verified;
    that is reported as ``spread unverifiable`` rather than as a pass.
    """
    ok = [r for r in results if r.status == "ok"]
    points = [(r.point.as_dict(), r.measurements) for r in ok]

    out: dict[str, dict] = {}
    for name in measure_names:
        per_axis: dict[str, dict] = {}
        rows = [(p, m[name]) for p, m in points if name in m]
        for axis in AXES:
            levels = {_AXIS_LEVEL[axis](p) for p, _ in rows}
            groups: dict[tuple, list[float]] = defaultdict(list)
            for point, value in rows:
                groups[_AXIS_GROUP_KEY[axis](point)].append(value)
            spreads = [s for s in (_spread_pct(v) for v in groups.values()) if s is not None]
            per_axis[axis] = {
                "levels": len(levels),
                "groups": len(groups),
                "min_pct": min(spreads) if spreads else None,
                "max_pct": max(spreads) if spreads else None,
            }
        out[name] = per_axis
    return out


def evaluate_checks(
    checks: dict[str, dict],
    results: list[PointResult],
    summary: dict,
    sensitivity: dict | None = None,
    allow_unswept_axes: bool = False,
) -> list[dict]:
    """Return a list of check failures (empty list == everything passed).

    ``allow_unswept_axes`` downgrades "this axis was never swept, so its
    sensitivity is unverifiable" from a failure to a silent skip. It is only
    ever set for runs that are already declared non-evidence (``--no-write``)
    or that carry a written subset justification, so a *recorded* run can
    never quietly skip an axis check.
    """
    sensitivity = sensitivity or {}
    failures: list[dict] = []
    for name, spec in checks.items():
        low = spec.get("min")
        high = spec.get("max")
        if low is not None or high is not None:
            for result in results:
                if result.status != "ok" or name not in result.measurements:
                    continue
                value = result.measurements[name]
                if low is not None and value < low:
                    failures.append(
                        {
                            "measurement": name,
                            "kind": "min",
                            "limit": low,
                            "value": value,
                            "at": result.point.corner_id,
                        }
                    )
                if high is not None and value > high:
                    failures.append(
                        {
                            "measurement": name,
                            "kind": "max",
                            "limit": high,
                            "value": value,
                            "at": result.point.corner_id,
                        }
                    )
        # Grid-level spread checks. max_spread_pct is the usual "this must be
        # stable over PVT" assertion; min_spread_pct is its inverse and exists
        # to prove the harness is actually *moving* the corner -- a measurement
        # that is supposed to be strongly PVT-sensitive but comes back flat
        # means .temp / .lib never took effect.
        for kind, limit in (
            ("max_spread_pct", spec.get("max_spread_pct")),
            ("min_spread_pct", spec.get("min_spread_pct")),
        ):
            if limit is None:
                continue
            observed = (summary.get(name) or {}).get("spread_pct")
            violated = (
                observed is None
                or (kind == "max_spread_pct" and observed > limit)
                or (kind == "min_spread_pct" and observed < limit)
            )
            if violated:
                failures.append(
                    {
                        "measurement": name,
                        "kind": kind,
                        "limit": limit,
                        "value": observed,
                        "at": "grid",
                    }
                )

        # Per-axis sensitivity. This is the guard against the *silent* failure
        # mode: a runner that appears to sweep PVT but pins one axis. A
        # grid-wide min_spread_pct passes as long as SOMETHING moved; these
        # require the named axis specifically to have moved.
        for kind, key, reduce_key in (
            ("min_spread_pct_by_axis", "min_spread_pct_by_axis", "min_pct"),
            ("max_spread_pct_by_axis", "max_spread_pct_by_axis", "max_pct"),
        ):
            for axis, limit in (spec.get(key) or {}).items():
                stats = (sensitivity.get(name) or {}).get(axis) or {}
                if stats.get("levels", 0) < 2:
                    if allow_unswept_axes:
                        continue
                    failures.append(
                        {
                            "measurement": name,
                            "kind": kind,
                            "axis": axis,
                            "limit": limit,
                            "value": None,
                            "at": f"axis:{axis}",
                            "note": "axis was never swept — sensitivity unverifiable",
                        }
                    )
                    continue
                observed = stats.get(reduce_key)
                violated = (
                    observed is None
                    or (kind == "min_spread_pct_by_axis" and observed < limit)
                    or (kind == "max_spread_pct_by_axis" and observed > limit)
                )
                if violated:
                    failures.append(
                        {
                            "measurement": name,
                            "kind": kind,
                            "axis": axis,
                            "limit": limit,
                            "value": observed,
                            "at": f"axis:{axis}",
                        }
                    )
    return failures


def environment(
    pdk: Pdk,
    ngspice: str,
    repo_root: Path,
    git: dict | None = None,
    toolchain: dict | None = None,
) -> dict:
    """Reproducibility provenance for the record.

    ``git`` should be sampled *before* the run starts. The harness writes its
    own per-corner logs into the tracked evidence tree, so sampling afterwards
    would report every record as taken against a dirty tree.

    ``toolchain`` is :func:`harness.toolchain.summary` — whether the versions
    that produced this record satisfied the repo's pins. Recording only what
    was *found* would leave a reader unable to tell a pinned run from a
    deliberately-drifted one.
    """
    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover - unusual environments
        user = "unknown"
    return {
        "harness_version": HARNESS_VERSION,
        "harness_upstream": UPSTREAM_PATTERN,
        "ngspice": ngspice,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "host": socket.gethostname(),
        "user": user,
        "pdk": pdk.provenance(),
        "git": git if git is not None else git_provenance(repo_root),
        "toolchain": toolchain or {},
    }


def matrix_conformance(tb: Testbench, points: list[PvtPoint]) -> dict:
    """Is this run the full PVT matrix CLAUDE.md mandates, or a subset?

    ``sim/README.md`` requires every record's *Corner matrix run* field to be
    the full matrix (-40/27/125 C, +/-10 % supply, process corners) "unless the
    record states why a subset was used". This returns what is missing so the
    CLI can insist on a written justification instead of quietly recording a
    thinner run.
    """
    temps = {round(p.temp_c, 6) for p in points}
    supplies = {round(p.vdd, 6) for p in points}
    process = {p.corner.name for p in points}

    required_temps = {round(t, 6) for t in DEFAULT_TEMPERATURES_C}
    nominal = tb.nominal_supply_v
    required_supplies = {
        round(nominal * (1.0 - DEFAULT_SUPPLY_TOLERANCE), 6),
        round(nominal, 6),
        round(nominal * (1.0 + DEFAULT_SUPPLY_TOLERANCE), 6),
    }

    missing: list[str] = []
    if not required_temps <= temps:
        missing.append(
            "temperature: missing "
            + ", ".join(f"{t:g} C" for t in sorted(required_temps - temps))
        )
    if not required_supplies <= supplies:
        missing.append(
            "supply: missing "
            + ", ".join(f"{v:.2f} V" for v in sorted(required_supplies - supplies))
        )
    if len(process) < MIN_PROCESS_CORNERS:
        missing.append(
            f"process: only {len(process)} corner(s) "
            f"({', '.join(sorted(process))}); at least {MIN_PROCESS_CORNERS} expected"
        )

    return {"full": not missing, "missing": missing}


def build_record(
    tb: Testbench,
    pdk: Pdk,
    points: list[PvtPoint],
    results: list[PointResult],
    ngspice: str,
    repo_root: Path,
    record_id: str,
    started_utc: str,
    wall_seconds: float,
    claim: str = "",
    supersedes: str = "",
    statistical_convention: str = "",
    subset_reason: str = "",
    git: dict | None = None,
    extensions: Extensions | None = None,
    allow_unswept_axes: bool = False,
    toolchain: dict | None = None,
) -> dict:
    measure_names = list(tb.measure)
    summary = summarize(results, measure_names)
    sensitivity = axis_sensitivity(results, measure_names)
    failures = evaluate_checks(
        tb.checks, results, summary, sensitivity, allow_unswept_axes=allow_unswept_axes
    )
    n_ok = sum(1 for r in results if r.status == "ok")
    extensions = extensions if extensions is not None else tb.evidence

    if n_ok != len(results):
        status = "error"
    elif failures:
        status = "fail"
    else:
        status = "pass"

    corners = []
    seen = set()
    for point in points:
        if point.corner.name not in seen:
            seen.add(point.corner.name)
            corners.append(
                {
                    "name": point.corner.name,
                    "sections": list(point.corner.sections),
                    "description": point.corner.description,
                }
            )

    return {
        "record_id": record_id,
        "experiment": tb.experiment,
        "status": status,
        "started_utc": started_utc,
        "wall_seconds": round(wall_seconds, 2),
        "claim": claim or tb.claim,
        "supersedes": supersedes,
        "statistical_convention": statistical_convention,
        "subset_reason": subset_reason,
        "matrix": matrix_conformance(tb, points),
        "testbench": tb.provenance(),
        "environment": environment(pdk, ngspice, repo_root, git, toolchain),
        "evidence": extensions.as_dict(),
        "grid": {
            "corners": corners,
            "temperatures_c": sorted({p.temp_c for p in points}),
            "supplies_v": sorted({p.vdd for p in points}),
            "points": len(points),
            "points_ok": n_ok,
        },
        "measure": dict(tb.measure),
        "checks": {
            "spec": tb.checks,
            "passed": not failures,
            "failures": failures,
        },
        "summary": summary,
        "sensitivity": sensitivity,
        "points": [r.as_dict() for r in results],
    }


def _fmt(value) -> str:
    """Human-readable scalar for the Markdown record."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
            return f"{value:.6e}"
        return f"{value:.6g}"
    return str(value)


def describe_failure(failure: dict) -> str:
    """One-line, human-readable rendering of a check failure."""
    axis = failure.get("axis")
    where = f" on the {axis} axis" if axis else ""
    note = failure.get("note")
    if note:
        return f"{failure['measurement']} {failure['kind']}{where}: {note}"
    return (
        f"{failure['measurement']} {failure['kind']}{where}="
        f"{_fmt(failure['limit'])} (got {_fmt(failure['value'])})"
    )


def _toolchain_banner(toolchain: dict) -> list[str]:
    """Lead the record with a warning when its toolchain was not the pinned one.

    A drifted run is only reachable via ``--allow-toolchain-drift``, but once
    the record is written nothing about the numbers themselves says so. The
    banner is what stops a later reader from comparing it against pinned
    records as if it were one.
    """
    if not toolchain or toolchain.get("conforms", True):
        return []
    drifts = toolchain.get("drift") or []
    lines = [
        "> **⚠ Toolchain drift — not comparable with pinned records.** This run was",
        "> taken with `--allow-toolchain-drift`; the tools below did not match",
        "> `sim/toolchain.json` / `docs/environment-setup.md` §1:",
        ">",
    ]
    for drift in drifts:
        lines.append(
            f"> - `{drift.get('tool')}`: {drift.get('detail')} "
            f"(pinned `{drift.get('pinned')}`, found `{drift.get('found')}`)"
        )
    lines.append("")
    return lines


def _toolchain_lines(toolchain: dict) -> list[str]:
    """The Environment-section line describing pin conformance."""
    if not toolchain or not toolchain.get("pinned"):
        return ["- Toolchain pins: none configured (`sim/toolchain.json` absent or empty)"]
    pins = toolchain.get("pins") or {}
    rendered = ", ".join(f"{k}={v}" for k, v in pins.items())
    if toolchain.get("conforms"):
        return [f"- Toolchain pins: **satisfied** ({rendered})"]
    drifts = "; ".join(
        f"{d.get('tool')} pinned {d.get('pinned')}, found {d.get('found')}"
        for d in (toolchain.get("drift") or [])
    )
    return [
        f"- Toolchain pins: **DRIFTED** ({rendered}) — {drifts}. "
        "Recorded under `--allow-toolchain-drift`; see the banner at the top of "
        "this record."
    ]


class RecordExists(RuntimeError):
    """Refused to overwrite an existing append-only record."""


def write_netlist_snapshot(tb: Testbench, experiment_dir: Path, record_id: str) -> Path:
    """Freeze the DUT netlist for this record.

    ``sim/README.md``: ``netlist-snapshots/<record-id>.spice`` is "the frozen
    DUT netlist used for this record", so later edits to ``testbench/`` never
    change what an existing record refers to.
    """
    out_dir = experiment_dir / SNAPSHOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record_id}.spice"
    if path.exists():
        raise RecordExists(f"{path} already exists; append-only evidence is never rewritten")
    header = "\n".join(
        [
            f"* Frozen netlist snapshot for record {record_id}",
            f"* source     : {tb.netlist.relative_to(experiment_dir.parent.parent)}",
            f"* sha256     : {tb.netlist_sha256}",
            "* This is a verbatim copy taken at record time. Do not edit.",
            "",
        ]
    )
    path.write_text(header + tb.netlist.read_text())
    return path


def _corner_matrix_lines(record: dict) -> list[str]:
    grid = record["grid"]
    lines = [
        "- **Corner matrix run**:",
        "  - Process: " + ", ".join(c["name"] for c in grid["corners"]),
        "  - Temperature: " + ", ".join(f"{t:g} °C" for t in grid["temperatures_c"]),
        "  - Supply: " + ", ".join(f"{v:.2f} V" for v in grid["supplies_v"]),
        f"  - {grid['points']} point full-factorial grid "
        f"(process × temperature × supply), {grid['points_ok']} completed",
    ]
    if record["matrix"]["full"]:
        lines.append(
            "  - Full PVT matrix per CLAUDE.md (−40/27/125 °C, ±10 % supply, "
            "process corners)."
        )
    else:
        lines.append("  - **Subset of the mandated PVT matrix.** Gaps: "
                     + "; ".join(record["matrix"]["missing"]) + ".")
        lines.append("  - Justification: " + (record["subset_reason"] or "(none given)"))
    return lines


def _sensitivity_lines(record: dict) -> list[str]:
    """The per-axis corner-sensitivity table.

    Present on every record, checked or not: it is the reader's evidence that
    the PVT axes actually moved the circuit in *this* run, rather than a
    claim that the harness swept them.
    """
    lines = [
        "",
        "  Per-axis corner sensitivity (spread observed when only that axis varies,",
        "  weakest → strongest slice of the grid):",
        "",
        "  | measurement | process | temperature | supply |",
        "  |---|---|---|---|",
    ]
    for name, axes in record["sensitivity"].items():
        cells = []
        for axis in AXES:
            stats = axes.get(axis) or {}
            if stats.get("levels", 0) < 2:
                cells.append("not swept")
            elif stats.get("min_pct") is None:
                cells.append("n/a")
            else:
                cells.append(f"{_fmt(stats['min_pct'])} … {_fmt(stats['max_pct'])} %")
        lines.append(f"  | `{name}` | " + " | ".join(cells) + " |")
    return lines


def _result_lines(record: dict) -> list[str]:
    measure_names = list(record["measure"])
    characterization = record["evidence"].get("record_kind") == "characterization"
    failures_at: dict[str, list[str]] = {}
    for failure in record["checks"]["failures"]:
        failures_at.setdefault(failure["at"], []).append(describe_failure(failure))

    heading = "Measured value(s)" if characterization else "Result"
    lines = [f"- **{heading}**:", ""]
    lines.append("  | corner-id | " + " | ".join(measure_names) + " | pass/fail |")
    lines.append("  |---|" + "---|" * (len(measure_names) + 1))
    for point in record["points"]:
        cells = [_fmt(point["measurements"].get(name)) for name in measure_names]
        problems = failures_at.get(point["corner_id"], [])
        if point["status"] != "ok":
            verdict = f"ERROR — {point.get('message', point['status'])}"
        elif problems:
            verdict = "FAIL — " + "; ".join(problems)
        else:
            verdict = "PASS"
        lines.append(f"  | `{point['corner_id']}` | " + " | ".join(cells) + f" | {verdict} |")

    grid_failures = failures_at.get("grid", [])
    axis_failures = [
        describe_failure(f)
        for f in record["checks"]["failures"]
        if str(f.get("at", "")).startswith("axis:")
    ]
    if grid_failures:
        lines.append("")
        lines.append("  Grid-level check failures: " + "; ".join(grid_failures) + ".")
    if axis_failures:
        lines.append("")
        lines.append(
            "  **Per-axis sensitivity failures** (the corner runner did not demonstrably "
            "move this axis): " + "; ".join(axis_failures) + "."
        )

    lines.append("")
    lines.append("  Spread across the grid:")
    lines.append("")
    lines.append("  | measurement | min | max | mean | spread % | limits |")
    lines.append("  |---|---|---|---|---|---|")
    for name, stats in record["summary"].items():
        spec = record["checks"]["spec"].get(name, {})
        limit_bits = [
            f"{key}={_fmt(spec[key])}"
            for key in ("min", "max", "max_spread_pct", "min_spread_pct")
            if key in spec
        ]
        for key in ("min_spread_pct_by_axis", "max_spread_pct_by_axis"):
            for axis, limit in (spec.get(key) or {}).items():
                limit_bits.append(f"{key}[{axis}]={_fmt(limit)}")
        limits = ", ".join(limit_bits) or "—"
        if not stats.get("n"):
            lines.append(f"  | `{name}` | no data | | | | {limits} |")
            continue
        lines.append(
            f"  | `{name}` | {_fmt(stats['min'])} (`{stats['min_at']}`) "
            f"| {_fmt(stats['max'])} (`{stats['max_at']}`) "
            f"| {_fmt(stats['mean'])} | {_fmt(stats['spread_pct'])} | {limits} |"
        )

    lines += _sensitivity_lines(record)

    verdict = {"pass": "PASS", "fail": "FAIL", "error": "ERROR"}[record["status"]]
    lines.append("")
    if characterization:
        lines.append(
            f"  - **Overall: {verdict}** (characterization record — the verdict is the "
            "harness's own sanity/sensitivity checks, not a spec pass/fail; see "
            "`sim/README.md` § Characterization-record variant)"
        )
    else:
        lines.append(f"  - **Overall: {verdict}**")
    return lines


def render_record(record: dict, experiment: str) -> str:
    """Render the ratified ``records/<record-id>.md`` summary.

    Field set and order follow ``sim/README.md``: Record ID, Claim, Netlist
    provenance, Corner matrix run, Statistical convention (+ Monte Carlo
    sub-fields), the applicable ADC-specific extension fields, Result (or
    Measured value(s)), Links, Timestamp / author, Supersedes.
    """
    record_id = record["record_id"]
    env = record["environment"]
    tb = record["testbench"]
    git = env["git"]
    pdk = env["pdk"]
    extensions = Extensions(**record["evidence"])

    provenance = f"schematic (`sim/{experiment}/{TESTBENCH_DIR}/{tb['netlist']}`)"
    if git["dirty"]:
        provenance += (
            f" — **taken against a dirty working tree** at commit `{git['commit']}`; "
            "not citable as a clean-tree result"
        )

    lines = [f"# Record {record_id}", ""]
    lines += _toolchain_banner(env.get("toolchain") or {})
    lines += [
        f"- **Record ID**: {record_id}",
        f"- **Claim**: {record['claim'] or 'harness self-verification — no spec claim'}",
        f"- **Netlist provenance**: {provenance}",
    ]
    lines += _corner_matrix_lines(record)
    lines.append(
        "- **Statistical convention**: "
        + (record["statistical_convention"]
           or "N/A (corner-matrix claim, not a distribution claim)")
    )
    lines += extensions.render_statistical_sublines()
    lines += extensions.render_lines()
    lines += _result_lines(record)
    lines += [
        "- **Links**:",
        f"  - Testbench: `sim/{experiment}/{TESTBENCH_DIR}/{tb['netlist']}`, "
        f"`sim/{experiment}/{TESTBENCH_DIR}/tb.json`",
        f"  - Netlist snapshot: `sim/{experiment}/{SNAPSHOT_DIR}/{record_id}.spice`",
        f"  - Raw logs: `sim/{experiment}/{CORNERS_DIR}/{record_id}/`",
        f"- **Timestamp / author**: {record['started_utc']}, {env['user']}",
        f"- **Supersedes**: {record['supersedes'] or '(none)'}",
        "",
        "## Environment",
        "",
        "Everything needed to re-run this record:",
        "",
        f"- PDK: {pdk.get('variant')} @ open_pdks `{pdk.get('open_pdks_version')}`"
        f" ({pdk.get('path')}, found via {pdk.get('discovered_via')})",
        f"- MIM metal stack for this variant: `{pdk.get('mim_stack')}` "
        "(binds the `mim_cap_*` CDAC unit-cap aliases)",
        f"- ngspice: {env['ngspice']}",
        *_toolchain_lines(env.get("toolchain") or {}),
        f"- Harness: sim/harness {env['harness_version']} "
        f"(ported from {env.get('harness_upstream', 'n/a')}), python {env['python']}",
        f"- git: `{git['commit']}` on `{git['branch']}`"
        + (" (dirty)" if git["dirty"] else " (clean)"),
        f"- Testbench netlist sha256: `{tb['netlist_sha256']}`",
        f"- Manifest sha256: `{tb['manifest_sha256']}`",
        f"- Wall time: {record['wall_seconds']} s",
        "",
        "Per-corner model sections used:",
        "",
    ]
    for corner in record["grid"]["corners"]:
        lines.append(f"- `{corner['name']}`: {' '.join(corner['sections'])}")
    lines += [
        "",
        "---",
        "",
        "Written by `sim/run_corners.py`. Append-only: never edit or delete this",
        "file — a re-run or correction mints a new record-id and points back here",
        "via **Supersedes** (see `sim/README.md`).",
        "",
    ]
    return "\n".join(lines)


def write_record(record: dict, experiment_dir: Path) -> Path:
    """Write ``records/<record-id>.md``; never overwrite an existing record."""
    out_dir = experiment_dir / RECORDS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record['record_id']}.md"
    if path.exists():
        raise RecordExists(
            f"{path} already exists; records are append-only -- mint a new record-id"
        )
    path.write_text(render_record(record, experiment_dir.name))
    return path
