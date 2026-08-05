"""Command line front end: ``python3 sim/run_corners.py <testbench> [...]``."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import os
import sys
import time
from pathlib import Path

from . import HARNESS_VERSION, corners as corners_mod, evidence as evidence_mod
from . import report, runner, testbench as tb_mod, toolchain as toolchain_mod
from .evidence import (
    DATA_PROVENANCE_TAGS,
    EvidenceFormatError,
    LINEARITY_METHODS,
    MC_SCOPES,
    NOISE_METHODS,
    RECORD_KINDS,
)
from .pdk import PdkNotFound, UnknownVariant, find_pdk
from .runner import NgspiceMissing

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"
WORK_DIR = SIM_DIR / ".work"

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_SIM_ERROR = 2
EXIT_ENVIRONMENT = 3


def _has_manifest(candidate: Path) -> bool:
    if candidate.is_file() and candidate.name == tb_mod.MANIFEST_NAME:
        return True
    if (candidate / tb_mod.MANIFEST_NAME).is_file():
        return True
    return (candidate / tb_mod.TESTBENCH_DIRNAME / tb_mod.MANIFEST_NAME).is_file()


def _resolve_tb_path(argument: str) -> Path:
    """Accept an experiment slug, an experiment dir, or a testbench dir."""
    candidates = [Path(argument), SIM_DIR / argument]
    for candidate in candidates:
        if _has_manifest(candidate):
            return candidate
    raise FileNotFoundError(
        f"no experiment {argument!r}; tried: "
        + ", ".join(str(c) for c in candidates)
        + ".\nAvailable: "
        + ", ".join(p.name for p in tb_mod.discover(SIM_DIR))
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_corners.py",
        description="Run a testbench across the gf180mcu PVT corner grid.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 sim/run_corners.py smoke-sar-bias\n"
            "  python3 sim/run_corners.py smoke-sar-bias --corners tt --temps 27 \\\n"
            "      --subset-reason 'debugging convergence, not evidence'\n"
            "  python3 sim/run_corners.py smoke-sar-bias --corner-set full -j 8\n"
            "  python3 sim/run_corners.py --list\n"
            "  python3 sim/run_corners.py --check-env\n"
        ),
    )
    parser.add_argument(
        "testbench",
        nargs="?",
        metavar="EXPERIMENT",
        help="experiment slug under sim/ (i.e. sim/<slug>/testbench/tb.json)",
    )
    parser.add_argument("--list", action="store_true", help="list testbenches and corners")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="report ngspice / PDK availability and exit",
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="print shell exports for the resolved PDK (used by sim/env.sh)",
    )
    parser.add_argument(
        "--corners",
        nargs="+",
        metavar="NAME",
        help="explicit corner or corner-set names (overrides the manifest)",
    )
    parser.add_argument(
        "--corner-set",
        choices=sorted(corners_mod.CORNER_SETS),
        help="shorthand for --corners <set>",
    )
    parser.add_argument(
        "--temps",
        nargs="+",
        type=float,
        metavar="C",
        help="temperatures in degrees C (overrides the manifest)",
    )
    parser.add_argument(
        "--supply",
        type=float,
        metavar="V",
        help="nominal supply in volts (overrides the manifest)",
    )
    parser.add_argument(
        "--supply-tol",
        type=float,
        metavar="FRAC",
        help="supply tolerance as a fraction, e.g. 0.10 (0 disables the V axis)",
    )
    parser.add_argument("-j", "--jobs", type=int, default=0, help="parallel ngspice runs")
    parser.add_argument(
        "--ngspice-threads",
        type=int,
        default=0,
        metavar="N",
        help="cap ngspice's OWN OpenMP thread count per point ('set num_threads=N'); "
        "0 leaves its default (one thread per processor). A scheduling knob only -- "
        "measured bit-identical results, and on a contended host 3.4x faster wall / "
        "16x less CPU at N=1 for a ~1300-device deck, because the default makes "
        "concurrent -j points fight for cores and spin. Grid throughput comes from "
        "-j; this stops each point from oversubscribing the machine.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=runner.DEFAULT_TIMEOUT_S,
        help="per-point ngspice timeout in seconds",
    )
    parser.add_argument(
        "--sabotage-corners",
        action="store_true",
        help="NEGATIVE CONTROL (self-test only): keep the corner names but force every "
        "model section to typical, reproducing a runner that only *looks* like it "
        "sweeps process corners. A healthy testbench MUST fail its per-axis "
        "sensitivity checks under this flag. Implies --no-write.",
    )

    record = parser.add_argument_group(
        "evidence record (sim/README.md)",
        "Fields written into records/<record-id>.md. Manifest 'evidence' block "
        "values are used when the flag is omitted.",
    )
    record.add_argument(
        "--claim",
        default="",
        help="spec line this run substantiates, e.g. 'spec/adc.md#inl-dnl' "
        "(overrides the manifest's 'claim')",
    )
    record.add_argument(
        "--supersedes",
        default="",
        metavar="RECORD_ID",
        help="prior record-id this record corrects or replaces",
    )
    record.add_argument(
        "--statistical-convention",
        default="",
        metavar="TEXT",
        help="N samples / sigma level, for distribution (Monte Carlo) claims",
    )
    record.add_argument(
        "--subset-reason",
        default="",
        metavar="TEXT",
        help="why this run is not the full mandated PVT matrix; required before "
        "a subset run may be recorded as evidence",
    )
    record.add_argument(
        "--record-kind",
        choices=RECORD_KINDS,
        help="'characterization' reports Measured value(s) + Data provenance instead "
        "of a spec pass/fail Result (sim/README.md)",
    )
    record.add_argument("--fft-n", type=int, help="FFT record length (dynamic-test records)")
    record.add_argument("--fft-input-hz", type=float, help="analog input frequency")
    record.add_argument("--fft-bin", type=int, help="coherent-sampling FFT bin of the input")
    record.add_argument(
        "--fft-window",
        metavar="TEXT",
        help="'none' for coherent sampling, else '<window> <why coherent was not used>'",
    )
    record.add_argument("--fft-fs-hz", type=float, help="sampling rate f_s in Hz")
    record.add_argument(
        "--linearity-method",
        metavar="TEXT",
        help="'<tag> <free text>' where <tag> is one of: " + ", ".join(LINEARITY_METHODS),
    )
    record.add_argument("--mc-seed", metavar="TEXT", help="Monte Carlo seed value(s) or policy")
    record.add_argument("--mc-scope", choices=MC_SCOPES, help="Monte Carlo variation scope")
    record.add_argument("--mc-sigma", metavar="TEXT", help="sigma level of the pass/fail criterion")
    record.add_argument(
        "--noise-method",
        metavar="TEXT",
        help="'<tag> <free text>' where <tag> is one of: " + ", ".join(NOISE_METHODS),
    )
    record.add_argument("--noise-seed", metavar="TEXT", help="transient-noise seed")
    record.add_argument(
        "--noise-duration-justification",
        metavar="TEXT",
        help="why the transient-noise run is long enough to be defensible",
    )
    record.add_argument(
        "--data-provenance",
        metavar="TEXT",
        help="'<tag> <free text>' where <tag> is one of: " + ", ".join(DATA_PROVENANCE_TAGS),
    )
    record.add_argument(
        "--note",
        action="append",
        default=[],
        metavar="TEXT",
        help="free-text note carried verbatim into the record (repeatable)",
    )

    parser.add_argument(
        "--netlist",
        metavar="PATH",
        help="run the manifest's measure/check/analyses machinery against an "
        "ALTERNATE netlist fragment instead of the one named in tb.json -- "
        "e.g. a post-layout extracted core wired with the same tag convention "
        "(sim/README.md 'Extracted vs schematic semantics': the extracted "
        "record lives in the SAME experiment directory as the schematic one, "
        "so this reuses the schematic manifest's methodology byte-for-byte "
        "rather than hand-duplicating it). Re-validated against the same "
        "forbidden-directive rule as the manifest's own netlist.",
    )
    parser.add_argument(
        "--netlist-provenance",
        metavar="TEXT",
        help="override the manifest's netlist_provenance ('schematic' by default) -- "
        "'extracted' or 'extracted (<detail>)'. Required in practice whenever "
        "--netlist points at a post-layout netlist, so the record's 'Netlist "
        "provenance' field is not silently wrong.",
    )
    parser.add_argument(
        "--allow-toolchain-drift",
        action="store_true",
        help="proceed even though the installed ngspice / PDK revision does not match "
        "sim/toolchain.json. The drift is stamped into every record written under "
        "this flag; without it, a drifted toolchain is a hard error and nothing is "
        "simulated.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="run but do not record evidence (debugging only)",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    parser.add_argument(
        "--version", action="version", version=f"gf180-sar-adc harness {HARNESS_VERSION}"
    )
    return parser


def cmd_list() -> int:
    print("Experiments (sim/<slug>/testbench/tb.json):")
    for directory in tb_mod.discover(SIM_DIR):
        try:
            tb = tb_mod.load(directory)
            print(f"  {directory.name:<20} {tb.description or tb.name}")
        except Exception as exc:  # noqa: BLE001 - surface bad manifests, keep listing
            print(f"  {directory.name:<20} !! {exc}")
    print("\nCorner sets:")
    for name, members in sorted(corners_mod.CORNER_SETS.items()):
        print(f"  {name:<20} {', '.join(members)}")
    print("\nCorners:")
    for name, corner in corners_mod.CORNERS.items():
        print(f"  {name:<20} {corner.description}")
        print(f"  {'':<20} sections: {' '.join(corner.sections)}")
    return EXIT_OK


def cmd_check_env() -> int:
    """Report the resolved toolchain.

    Two distinct failure exit codes, because the callers need to tell them
    apart: ``3`` means something is **missing** (install it), ``1`` means
    everything is present but a pinned version **drifted** (a real problem
    that must not be reported as "tools unavailable, skipping").
    """
    status = EXIT_OK
    ngspice_version = ""
    pdk_version = ""
    try:
        ngspice_version = runner.ngspice_version()
        print(f"ngspice : OK   {ngspice_version}")
    except NgspiceMissing as exc:
        print(f"ngspice : MISSING\n{exc}")
        status = EXIT_ENVIRONMENT
    try:
        pdk = find_pdk()
        pdk_version = pdk.version
        print(f"PDK     : OK   {pdk.path} (open_pdks {pdk_version}, via {pdk.source})")
        print(f"  models: {pdk.model_lib}")
        print(f"  xschem: {pdk.xschem_dir}")
        try:
            print(f"  MIM   : stack {pdk.mim_stack}, unit cap {pdk.mim_subckt('2f0')}")
        except UnknownVariant as exc:
            print(f"  MIM   : UNKNOWN\n{exc}")
            status = EXIT_ENVIRONMENT
    except PdkNotFound as exc:
        print(f"PDK     : MISSING\n{exc}")
        status = EXIT_ENVIRONMENT

    pins = toolchain_mod.load_pins()
    if not pins:
        print("pins    : NONE  (sim/toolchain.json absent or empty — nothing is pinned)")
        return status
    if status == EXIT_ENVIRONMENT:
        print("pins    : SKIPPED (install the missing tool above first)")
        return status
    drifts = toolchain_mod.check(
        pdk_version, ngspice_version, sys.version.split()[0], pins=pins
    )
    if not drifts:
        print(
            "pins    : OK   " + ", ".join(f"{k}={v}" for k, v in pins.items())
        )
        return status
    print("pins    : DRIFT")
    print(toolchain_mod.format_drifts(drifts))
    return EXIT_CHECK_FAILED


def cmd_print_env() -> int:
    """Emit shell exports so xschem/ngspice see the same PDK the harness picked."""
    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(f"# gf180mcu PDK not found\n# {exc.args[0].splitlines()[0]}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    library_path = ":".join(
        str(p)
        for p in [REPO_ROOT / "design"]
        + [d / tb_mod.TESTBENCH_DIRNAME for d in tb_mod.discover(SIM_DIR)]
    )
    print(f'export PDK_ROOT="{pdk.path.parent}"')
    print(f'export PDK="{pdk.variant}"')
    print(f'export GF180_PDK_PATH="{pdk.path}"')
    print(f'export GF180_MODELS="{pdk.ngspice_dir}"')
    print(f'export XSCHEM_USER_LIBRARY_PATH="{library_path}"')
    return EXIT_OK


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
            return f"{value:.6e}"
        return f"{value:.6g}"
    return str(value)


def merge_extensions(
    manifest_extensions: evidence_mod.Extensions, args: argparse.Namespace
) -> evidence_mod.Extensions:
    """CLI flags override the manifest's ``evidence`` block, field by field."""
    merged = dataclasses.replace(manifest_extensions)
    for attr in (
        "record_kind", "fft_n", "fft_input_hz", "fft_bin", "fft_window", "fft_fs_hz",
        "linearity_method", "mc_seed", "mc_scope", "mc_sigma",
        "noise_method", "noise_seed", "noise_duration_justification", "data_provenance",
    ):
        value = getattr(args, attr, None)
        if value not in (None, ""):
            setattr(merged, attr, value)
    if getattr(args, "note", None):
        merged.notes = list(merged.notes) + list(args.note)
    merged.validate()
    return merged


def run(args: argparse.Namespace) -> int:
    tb_path = _resolve_tb_path(args.testbench)
    tb = tb_mod.load(tb_path)

    if args.netlist:
        netlist_override = Path(args.netlist).resolve()
        if not netlist_override.is_file():
            print(f"error: --netlist {args.netlist!r} does not exist", file=sys.stderr)
            return EXIT_ENVIRONMENT
        tb = dataclasses.replace(tb, netlist=netlist_override)
        tb_mod.validate_netlist(tb)
    if args.netlist_provenance:
        netlist_provenance = args.netlist_provenance
        if not (netlist_provenance == "schematic" or netlist_provenance.startswith("extracted")):
            print(
                "error: --netlist-provenance must be 'schematic' or start with "
                f"'extracted'; got {netlist_provenance!r}",
                file=sys.stderr,
            )
            return EXIT_ENVIRONMENT
        tb = dataclasses.replace(tb, netlist_provenance=netlist_provenance)
    if args.netlist and tb.netlist_provenance == "schematic":
        print(
            "error: --netlist points at an alternate netlist but "
            "netlist_provenance is still 'schematic' -- pass --netlist-provenance "
            "explicitly (sim/README.md 'Netlist provenance' is required so "
            "post-layout re-runs are distinguishable from the schematic record)",
            file=sys.stderr,
        )
        return EXIT_ENVIRONMENT

    extensions = merge_extensions(tb.evidence, args)

    try:
        pdk = find_pdk()
        pdk.mim_stack  # fail loudly here, not mid-grid  # noqa: B018
        ngspice = runner.ngspice_version()
    except (PdkNotFound, NgspiceMissing, UnknownVariant) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT

    # Pinned-toolchain gate. Checked here -- before a single point is
    # simulated -- so a drifted toolchain can never emit partial results or
    # bank numbers that are not comparable with the existing records.
    try:
        pins = toolchain_mod.load_pins()
    except toolchain_mod.PinsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    drifts = toolchain_mod.check(
        pdk.version, ngspice, sys.version.split()[0], pins=pins
    )
    if drifts and not args.allow_toolchain_drift:
        print("error: " + toolchain_mod.format_drifts(drifts), file=sys.stderr)
        return EXIT_ENVIRONMENT
    toolchain_summary = toolchain_mod.summary(
        drifts, pins, allowed=bool(args.allow_toolchain_drift)
    )

    corner_names = args.corners or ([args.corner_set] if args.corner_set else list(tb.corners))
    corner_list = corners_mod.resolve_corners(corner_names)

    # The negative control must never be able to enter the evidence tree.
    no_write = args.no_write or args.sabotage_corners
    if args.sabotage_corners:
        corner_list = corners_mod.sabotage(corner_list)

    temperatures = args.temps if args.temps is not None else list(tb.temperatures_c)
    nominal = args.supply if args.supply is not None else tb.nominal_supply_v
    tolerance = args.supply_tol if args.supply_tol is not None else tb.supply_tolerance
    supplies = corners_mod.supply_points(nominal, tolerance)
    points = corners_mod.build_grid(corner_list, temperatures, supplies)

    # sim/README.md: an evidence record must cover the full mandated PVT
    # matrix unless it states why a subset was used. Refuse to record a thin
    # run without that justification rather than quietly banking weak evidence.
    conformance = report.matrix_conformance(tb, points)
    if not no_write and not conformance["full"] and not args.subset_reason:
        print(
            "error: this run is a subset of the PVT matrix CLAUDE.md mandates:\n  - "
            + "\n  - ".join(conformance["missing"])
            + "\nRecord it with --subset-reason '<why>', or re-run the full matrix,"
            "\nor use --no-write if this is just a debugging run.",
            file=sys.stderr,
        )
        return EXIT_ENVIRONMENT

    # A run that is already declared non-evidence, or that carries a written
    # subset justification, may leave an axis unswept; a recorded full-matrix
    # run may not.
    allow_unswept_axes = no_write or bool(args.subset_reason)

    experiment_dir = tb.experiment_dir
    records_dir = experiment_dir / report.RECORDS_DIR

    jobs = args.jobs or min(8, (os.cpu_count() or 2))
    started = _dt.datetime.now(_dt.timezone.utc)
    # Sample git state *before* the run: the harness writes its own per-corner
    # logs into the tracked evidence tree, so sampling afterwards would mark
    # every record as taken against a dirty tree.
    git = report.git_provenance(REPO_ROOT)
    record_id = report.allocate_record_id(REPO_ROOT, records_dir, started, git=git)
    workdir = WORK_DIR / tb.experiment / record_id
    log_dir = None if no_write else experiment_dir / report.CORNERS_DIR / record_id

    if not args.quiet:
        print(f"experiment: {tb.experiment}"
              + (f"  ({tb.description})" if tb.description else ""))
        print(f"pdk       : {pdk.variant} @ {pdk.version}  ({pdk.path}, MIM {pdk.mim_stack})")
        print(f"ngspice   : {ngspice}")
        print(f"corners   : {', '.join(c.name for c in corner_list)}")
        print(f"temps (C) : {', '.join(_fmt(t) for t in temperatures)}")
        print(f"supply (V): {', '.join(_fmt(v) for v in supplies)} "
              f"(nominal {_fmt(nominal)} +/-{tolerance * 100:g}%)")
        print(f"points    : {len(points)}  (jobs={jobs})")
        print(f"record id : {record_id}")
        if drifts:
            print()
            print("*** TOOLCHAIN DRIFT accepted via --allow-toolchain-drift: ***")
            for drift in drifts:
                print(f"***   {drift}")
            print("*** Any record written below is stamped as not comparable with  ***")
            print("*** records taken against the pinned toolchain.                 ***")
        if args.sabotage_corners:
            print()
            print("*** NEGATIVE CONTROL: every corner forced to the typical sections. ***")
            print("*** A healthy testbench MUST report FAIL below. Nothing is recorded. ***")
        print()

    completed = 0

    def progress(result):
        nonlocal completed
        completed += 1
        if args.quiet:
            return
        flag = {"ok": "ok  ", "failed": "FAIL", "error": "ERR "}[result.status]
        if result.status == "ok":
            detail = "  ".join(
                f"{name}={_fmt(result.measurements[name])}" for name in tb.measure
                if name in result.measurements
            )
        else:
            detail = result.message
        print(f"[{completed:>3}/{len(points)}] {flag} {result.point.corner_id:<26} {detail}")

    wall_start = time.monotonic()
    try:
        results = runner.run_grid(
            tb,
            pdk,
            points,
            workdir,
            jobs=jobs,
            timeout_s=args.timeout,
            on_result=progress,
            log_dir=log_dir,
            num_threads=args.ngspice_threads,
        )
    except NgspiceMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    wall = time.monotonic() - wall_start

    record = report.build_record(
        tb=tb,
        pdk=pdk,
        points=points,
        results=results,
        ngspice=ngspice,
        repo_root=REPO_ROOT,
        record_id=record_id,
        started_utc=started.isoformat(timespec="seconds"),
        wall_seconds=wall,
        claim=args.claim,
        supersedes=args.supersedes,
        statistical_convention=args.statistical_convention,
        subset_reason=args.subset_reason,
        git=git,
        extensions=extensions,
        allow_unswept_axes=allow_unswept_axes,
        toolchain=toolchain_summary,
    )

    print()
    print(f"summary ({record['grid']['points_ok']}/{len(points)} points ok, {wall:.1f}s):")
    header = f"  {'measurement':<16}{'min':>16}{'max':>16}{'mean':>16}{'spread %':>12}"
    print(header)
    for name, stats in record["summary"].items():
        if not stats.get("n"):
            print(f"  {name:<16}{'no data':>16}")
            continue
        print(
            f"  {name:<16}{_fmt(stats['min']):>16}{_fmt(stats['max']):>16}"
            f"{_fmt(stats['mean']):>16}{_fmt(stats['spread_pct']):>12}"
        )

    print()
    print("per-axis sensitivity (weakest .. strongest slice, % spread):")
    print(f"  {'measurement':<16}{'process':>22}{'temperature':>22}{'supply':>22}")
    for name, axes in record["sensitivity"].items():
        cells = []
        for axis in tb_mod.AXES:
            stats = axes.get(axis) or {}
            if stats.get("levels", 0) < 2:
                cells.append("not swept")
            elif stats.get("min_pct") is None:
                cells.append("n/a")
            else:
                cells.append(f"{_fmt(stats['min_pct'])} .. {_fmt(stats['max_pct'])}")
        print(f"  {name:<16}" + "".join(f"{c:>22}" for c in cells))

    for failure in record["checks"]["failures"]:
        print("  CHECK FAIL " + report.describe_failure(failure) + f" at {failure['at']}")

    if not no_write:
        snapshot = report.write_netlist_snapshot(tb, experiment_dir, record_id)
        record_path = report.write_record(record, experiment_dir)
        print()
        print(f"record    : {record_path}")
        print(f"snapshot  : {snapshot}")
        print(f"raw logs  : {log_dir}")
    else:
        print()
        reason = "--sabotage-corners" if args.sabotage_corners else "--no-write"
        print(f"evidence  : not recorded ({reason})")
    print(f"work dir  : {workdir}")
    print(f"status    : {record['status'].upper()}")

    if record["status"] == "error":
        return EXIT_SIM_ERROR
    if record["status"] == "fail":
        return EXIT_CHECK_FAILED
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list()
    if args.check_env:
        return cmd_check_env()
    if args.print_env:
        return cmd_print_env()
    if not args.testbench:
        parser.print_help()
        return EXIT_ENVIRONMENT
    try:
        return run(args)
    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        EvidenceFormatError,
        report.RecordExists,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT
