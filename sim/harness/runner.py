"""Deck composition and ngspice execution for one PVT point."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .corners import PvtPoint
from .pdk import MIM_DENSITIES, Pdk
from .testbench import Testbench

NGSPICE = "ngspice"
DEFAULT_TIMEOUT_S = 300

# `print` output for a length-1 vector: "m_vout = 6.9043645202e-01"
_MEAS_RE = re.compile(r"^\s*m_(\w+)\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)\s*$")
_ERROR_RE = re.compile(r"^\s*(?:Error|ERROR|Fatal|fatal error|doAnalyses:)", re.MULTILINE)

#: Lines that mark a HARD analysis failure: ngspice gave up on the analysis
#: before it reached the stop time the manifest asked for, so every vector in
#: the run holds truncated data.
#:
#:     doAnalyses: TRAN:  Timestep too small; time = 1.40244e-06, ...
#:     tran simulation(s) aborted
#:
#: This is deliberately a *separate* pattern from :data:`_ERROR_RE`, and not a
#: widening of it. ``_ERROR_RE`` matches any ``Error``/``Fatal`` line, which
#: ngspice also prints for recoverable, per-measurement complaints ("Error:
#: measure tdr_b when(WHEN) : out of interval") that legitimately leave the
#: rest of the run intact. These three markers instead say the *analysis*
#: stopped, which invalidates every number the run printed regardless of how
#: many of them parsed -- see :func:`analysis_aborted`.
_ABORT_RE = re.compile(
    r"^.*(?:doAnalyses:|Timestep too small|simulation\(s\) aborted).*$", re.MULTILINE
)

#: A node voltage reference inside an analysis line: ``v(ok_aerr)``. Only the
#: single-argument form is recognised -- see :func:`measured_vectors`.
_NODE_REF_RE = re.compile(r"\bv\s*\(\s*([^()\s,]+)\s*\)", re.IGNORECASE)
#: Any other vector-valued reference the save list would have to cover:
#: differential ``v(a,b)``, branch currents ``i(vsrc)``, device parameters
#: ``@m1[id]``. Their presence disables the save list rather than silently
#: dropping a vector a ``meas`` line needs.
_OTHER_REF_RE = re.compile(r"\bv\s*\([^()]*,|\bi\s*\(|@\w+\[", re.IGNORECASE)


class NgspiceMissing(RuntimeError):
    pass


class UnsupportedSaveList(RuntimeError):
    """``save_measured_only`` was asked for on a manifest that references
    something other than plain ``v(node)`` vectors."""


def measured_vectors(tb: Testbench) -> list[str]:
    """The ``v(node)`` vectors this testbench's own manifest reads.

    Scans both halves of the manifest that can name a vector -- the analysis
    lines (``meas tran ... v(ok_drdy) ...``) and the ``measure`` expressions
    (``let m_x = <expr>``) -- so a save list can never omit a node one of
    them needs. Order is first-seen, so the emitted line is stable for a
    given manifest.

    Used to build an ngspice ``save`` list, so the run stores only the nodes
    it actually measures instead of every node voltage and branch current in
    the deck (ngspice's default).

    Raises :class:`UnsupportedSaveList` if either half references a vector
    this function cannot express as a single-node ``v(...)`` -- a
    differential ``v(a,b)``, a branch current ``i(...)``, or a device
    parameter ``@dev[param]``. Refusing is deliberate: a save list that
    silently omitted such a vector would turn a measured value into a
    "vector not found" error at the far end of a long run.
    """
    vectors: list[str] = []
    sources = [(line, "analysis line") for line in tb.analyses]
    sources += [(expr, "measure expression") for expr in tb.measure.values()]
    for text, what in sources:
        if _OTHER_REF_RE.search(text):
            raise UnsupportedSaveList(
                f"{what} references a vector the save list cannot cover: {text!r}"
            )
        for node in _NODE_REF_RE.findall(text):
            expr = f"v({node})"
            if expr not in vectors:
                vectors.append(expr)
    return vectors


def ngspice_version() -> str:
    exe = shutil.which(NGSPICE)
    if not exe:
        raise NgspiceMissing(
            "ngspice not found on PATH.\n"
            "  macOS:  brew install ngspice\n"
            "  Debian: apt-get install ngspice\n"
            "See docs/environment-setup.md."
        )
    out = subprocess.run(
        [exe, "--version"], capture_output=True, text=True, check=False
    ).stdout
    for line in out.splitlines():
        if "ngspice-" in line:
            return line.strip().lstrip("* ").strip()
    return out.strip().splitlines()[0] if out.strip() else "unknown"


def mim_wrapper_subckts(pdk: Pdk) -> list[str]:
    """Stable ``mim_cap_<density>`` aliases for the resolved variant's stack.

    The PDK names its MIM subckts after the metal pair the capacitor sits
    between (``cap_mim_2f0_m4m5_noshield``), which is a *variant* property,
    not a device property. Testbenches therefore instantiate the stable name
    ``mim_cap_2f0`` and the harness binds it here, once, from
    :attr:`Pdk.mim_stack` -- so a CDAC testbench never hardcodes a
    metal-stack assumption and a variant switch cannot silently leave a
    testbench pointing at the wrong model.

    ``dtemp`` is forwarded (default 0, i.e. the deck's own ``.temp``) because
    the MiM temperature coefficient cannot otherwise be measured *within* one
    PVT point: ``.temp`` is global to a deck, so a single-deck tempco
    extraction needs a per-instance temperature offset. The PDK subckt already
    accepts ``dtemp``; this wrapper just stops hiding it.
    """
    lines = [
        "* ---- CDAC MIM unit-cap aliases (bound to this PDK variant's stack) --",
        f"* variant {pdk.variant} -> MIM between {pdk.mim_stack}",
    ]
    for density in sorted(MIM_DENSITIES):
        subckt = pdk.mim_subckt(density)
        lines += [
            f".subckt mim_cap_{density} 1 2 c_width=10u c_length=10u dtemp=0",
            f"Xmim 1 2 {subckt} c_width=c_width c_length=c_length dtemp=dtemp",
            ".ends",
        ]
    return lines


def compose_deck(tb: Testbench, pdk: Pdk, point: PvtPoint,
                 num_threads: int = 0, save_measured_only: bool = False) -> str:
    """Build the complete, self-contained ngspice deck for one PVT point.

    ``num_threads`` (0 = leave ngspice's default alone) emits ``set
    num_threads=N`` at the top of the control block. It is a **scheduling**
    knob, not a circuit one: an OpenMP-built ngspice defaults to one thread
    per processor, which on a busy host makes several concurrent points
    fight over the same cores and burn most of their CPU in OpenMP
    spin-waits. Measured on the extracted-core INL/DNL deck (issue #89,
    ~1300 devices): 239 s wall / 19 min CPU at the default against 71 s
    wall / 71 s CPU at ``num_threads=1`` on the same contended host --
    3.4x faster wall and 16x less CPU, for **bit-identical measurements**
    (``gain_err_lsb = -1.994219684`` either way). Grid throughput comes from
    ``-j``, not from ngspice's internal threads.

    ``save_measured_only`` emits an ngspice ``save`` line naming exactly the
    node voltages this manifest's own ``meas`` lines read (see
    :func:`measured_vectors`). It is a **data-retention** knob, not a circuit
    one: the solver still solves the identical network, but the output plot
    keeps only the measured nodes instead of every node voltage and branch
    current in the deck (ngspice's default). On a large deck that default
    retention, not CPU, is the binding constraint -- measured on
    ``sar-logic-timing-gates`` (five synthesized ~181-cell DUT instances):
    the resident set grows ~4.3 MB per simulated nanosecond, i.e. ~36 GB for
    that manifest's ratified 8.5 us run, on a 15.7 GB host. With the save
    list the same point holds a flat ~167 MB and runs ~1.3x faster (708 s ->
    549 s to an identical 0.25 us truncation), for identical ``meas`` output.
    """
    lines: list[str] = [
        f"* {tb.name} @ {point.corner_id} -- GENERATED by sim/harness, do not edit",
        f"* corner={point.corner.name} ({point.corner.description})",
        f"* temp={point.temp_c} C  vdd={point.vdd} V  pdk={pdk.variant}@{pdk.version}",
        "",
        "* ---- PVT parameters -------------------------------------------------",
        f".param vdd_nom={tb.nominal_supply_v!r}",
        f".param vdd_val={point.vdd!r}",
        f".param temp_c={point.temp_c!r}",
    ]
    for key, value in tb.params.items():
        lines.append(f".param {key}={value}")

    lines += [
        "",
        "* ---- gf180mcu models ------------------------------------------------",
        f'.include "{pdk.design_include}"',
    ]
    for section in point.corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')

    lines += ["", *mim_wrapper_subckts(pdk)]

    lines += [
        "",
        f".temp {point.temp_c!r}",
    ]
    for option in tb.options:
        lines.append(f".options {option}")

    lines += [
        "",
        "* ---- testbench ------------------------------------------------------",
        f'.include "{tb.netlist}"',
        "",
        "* ---- measurement ----------------------------------------------------",
        ".control",
        "set numdgt=10",
        "set noaskquit",
    ]
    if num_threads:
        lines.append(f"set num_threads={num_threads}")
    if save_measured_only:
        vectors = measured_vectors(tb)
        if vectors:
            lines.append("  save " + " ".join(vectors))
    lines += [f"  {analysis}" for analysis in tb.analyses]
    for name, expr in tb.measure.items():
        lines.append(f"  let m_{name} = {expr}")
    for name in tb.measure:
        lines.append(f"  print m_{name}")
    lines += [".endc", ".end", ""]
    return "\n".join(lines)


@dataclass
class PointResult:
    point: PvtPoint
    status: str                                   # "ok" | "failed" | "error"
    measurements: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    seconds: float = 0.0
    deck: str = ""
    log: str = ""
    message: str = ""

    def as_dict(self) -> dict:
        record = self.point.as_dict()
        record.update(
            {
                "status": self.status,
                "measurements": self.measurements,
                "seconds": round(self.seconds, 3),
                "deck": self.deck,
                "log": self.log,
            }
        )
        if self.missing:
            record["missing_measurements"] = self.missing
        if self.message:
            record["message"] = self.message
        return record


def parse_measurements(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for line in text.splitlines():
        match = _MEAS_RE.match(line)
        if match:
            try:
                found[match.group(1)] = float(match.group(2))
            except ValueError:  # pragma: no cover - regex already constrains this
                continue
    return found


def analysis_aborted(text: str) -> str:
    """The first line of ngspice output marking a hard analysis failure, or ``""``.

    A truncated transient is not self-announcing in the numbers. ngspice still
    prints every ``meas``/``print`` result it can compute from the data it got
    *before* giving up, so a manifest whose measurements all happen to parse
    off truncated data -- the single unbounded-right ``meas ... MAX ...
    FROM=...`` case is the worst offender, because it always yields a number --
    produces output indistinguishable from a completed run if you only look at
    what parsed. Issue #341: ten points of
    ``sim/sar-logic-timing-gates-lt/records/20260920-182006-2422cac.md``
    were scored as completed PASS/FAIL that way, each one a ``MAX`` over
    roughly 1.4 us of a ratified ``tran 5n 8.5u 0 5n``.

    So the abort has to be read off the *output*, not off the measurements.
    Callers must treat a non-empty return as disqualifying: the point did not
    complete, whatever it managed to print.
    """
    match = _ABORT_RE.search(text)
    return match.group(0).strip() if match else ""


def run_point(
    tb: Testbench,
    pdk: Pdk,
    point: PvtPoint,
    workdir: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    log_dir: Path | None = None,
    num_threads: int = 0,
    save_measured_only: bool = False,
) -> PointResult:
    """Simulate one PVT point. Never raises for simulation failure.

    ``workdir`` holds the generated deck (scratch, disposable). ``log_dir``
    -- when given -- is where the raw ngspice output lands as
    ``<corner-id>.log``; that is the ``sim/<slug>/corners/<record-id>/``
    directory from ``sim/README.md``. It defaults to ``workdir`` so a
    throwaway run does not touch the evidence tree.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    log_dir = workdir if log_dir is None else log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    deck_path = workdir / f"{point.corner_id}.spice"
    log_path = log_dir / f"{point.corner_id}.log"
    deck_path.write_text(compose_deck(
        tb, pdk, point, num_threads=num_threads,
        save_measured_only=save_measured_only,
    ))

    started = time.monotonic()
    try:
        proc = subprocess.run(
            [NGSPICE, "-b", str(deck_path)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=workdir,
            check=False,
        )
        output = proc.stdout + "\n" + proc.stderr
        returncode = proc.returncode
    except FileNotFoundError as exc:
        raise NgspiceMissing(str(exc)) from exc
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        log_path.write_text(f"TIMEOUT after {timeout_s}s\n")
        return PointResult(
            point=point,
            status="error",
            seconds=elapsed,
            deck=deck_path.name,
            log=log_path.name,
            message=f"ngspice timed out after {timeout_s}s",
        )
    elapsed = time.monotonic() - started
    log_path.write_text(output)

    measurements = parse_measurements(output)
    missing = [name for name in tb.measure if name not in measurements]

    if missing:
        errors = "; ".join(_ERROR_RE.findall(output)[:3])
        first_error = next(
            (line.strip() for line in output.splitlines() if _ERROR_RE.match(line)), ""
        )
        return PointResult(
            point=point,
            status="failed",
            measurements=measurements,
            missing=missing,
            seconds=elapsed,
            deck=deck_path.name,
            log=log_path.name,
            message=first_error or errors or f"ngspice exit {returncode}, no measurements parsed",
        )

    # Everything the manifest named parsed -- which is NOT the same as the run
    # having completed. Check the output for a hard analysis failure before
    # scoring anything `ok`, or a transient that gave up a sixth of the way
    # into its ratified stop time is recorded as a completed PASS/FAIL on the
    # strength of a `MAX` taken over the truncated part (issue #341).
    aborted = analysis_aborted(output)
    if aborted:
        return PointResult(
            point=point,
            status="failed",
            measurements=measurements,
            seconds=elapsed,
            deck=deck_path.name,
            log=log_path.name,
            message=(
                "ngspice aborted the analysis before its stop time; every "
                f"measurement it printed is over truncated data: {aborted}"
            ),
        )

    return PointResult(
        point=point,
        status="ok",
        measurements=measurements,
        seconds=elapsed,
        deck=deck_path.name,
        log=log_path.name,
    )


def run_grid(
    tb: Testbench,
    pdk: Pdk,
    points: list[PvtPoint],
    workdir: Path,
    jobs: int = 1,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    on_result=None,
    log_dir: Path | None = None,
    num_threads: int = 0,
    save_measured_only: bool = False,
) -> list[PointResult]:
    """Run every PVT point; results come back in grid order regardless of jobs."""
    results: list[PointResult | None] = [None] * len(points)

    def _one(index_point):
        index, point = index_point
        result = run_point(
            tb, pdk, point, workdir, timeout_s=timeout_s, log_dir=log_dir,
            num_threads=num_threads, save_measured_only=save_measured_only,
        )
        results[index] = result
        if on_result is not None:
            on_result(result)
        return result

    if jobs <= 1:
        for item in enumerate(points):
            _one(item)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(_one, enumerate(points)))

    return [r for r in results if r is not None]
