"""Export a harness experiment as a ``klt sim`` request, and read the result back.

Why this exists
---------------
``runner.run_grid`` launches ``ngspice -b`` locally, one process per PVT point.
The Loom dispatch workers are shared 8-vCPU hosts that must not run
multi-corner SPICE grids themselves: they export ``KLT_SIM_BACKEND=batch`` so
that ``klt sim`` ships the grid to the Spot batch fleet. Nothing in this
harness used to emit a ``klt sim`` request, so a grid on such a host had
nowhere to go (issues #303, #392).

This module is the missing seam. It turns ``(Testbench, corners, temperatures,
supplies)`` into a ``klt sim`` request plus a generated circuit-body netlist,
and turns the JSON report ``klt sim`` returns back into the same
:class:`~harness.runner.PointResult` list the local runner produces -- so the
append-only evidence record (``report.build_record``) is built by the *same*
code on both paths and its format does not change. What the batch path adds
is an ``environment.execution`` block recording what actually ran the points
(fleet job id, runner ngspice/klt versions, the netlist and model hashes
``klt`` computed); nothing the local record carries is dropped.

Fidelity rules (the record must not get weaker)
-----------------------------------------------
* **No silent partial export.** ``klt sim`` owns the ``.control`` block, so it
  runs exactly one analysis followed by ``.meas`` cards and ``let`` expressions.
  A manifest that needs more (``setseed``/``alterparam``/``linearize``/a
  ``let`` between analyses, a ``temp_c`` .param that must follow the
  temperature axis) is refused with a named reason by
  :func:`check_exportable` -- it is never approximated.
* **A truncated transient is never ``ok``.** The local runner scans the
  ngspice output for ``Timestep too small`` & co. (issue #341). The batch path
  applies the same :func:`runner.analysis_aborted` scan to the per-corner log
  ``klt`` retrieves, and a corner whose log could not be retrieved is
  ``failed`` rather than trusted.
* **Per-point timeouts stay honest.** ``options.timeout_s`` carries
  ``--timeout``; a corner ``klt`` reports with the ``timeout`` diagnostic
  becomes an ``error`` point whose message states the budget, and its raw log
  says ``TIMEOUT after <n>s`` exactly as the local runner writes it.
* **No local fallback.** :func:`resolve_backend` sends any multi-point grid to
  ``klt sim`` when ``KLT_SIM_BACKEND`` names an off-host backend. A failed
  submit is an error, never a quiet retry on this host's cores.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import runner, toolchain as toolchain_mod
from .corners import Corner, PvtPoint
from .pdk import Pdk
from .runner import PointResult
from .testbench import Testbench

KLT = "klt"

#: Backends ``klt sim`` runs away from this host.
OFFHOST_BACKENDS = ("batch", "remote")

#: Values of ``--backend`` / the resolved route.
BACKEND_CHOICES = ("auto", "local", "batch", "remote")

#: The supply ``.param`` the generated netlist body defines -- the same name
#: ``compose_deck`` uses. It is a ``.param``, not a source, so ``klt sim``'s
#: ``corners.supply_v`` axis (an ngspice ``alter`` on a source) cannot move it:
#: the supply axis is exported as one request per supply value instead, each
#: body binding ``.param vdd_val=<V>`` (issue #505, see :func:`build_supply_set`).
SUPPLY_PARAM = "vdd_val"

#: The model library the corner ``.lib`` sections are read from, relative to
#: the PDK variant directory (``Pdk.model_lib``).
MODEL_LIB_REL = "libs.tech/ngspice/sm141064.ngspice"

_ANALYSIS_KINDS = ("op", "dc", "ac", "tran")
_MEAS_TYPES = ("tran", "ac", "dc")
_TEMP_C_RE = re.compile(r"\btemp_c\b", re.IGNORECASE)
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBER_RE = re.compile(r"(?<![A-Za-z_0-9.])\d+\.?\d*(?:[eE][-+]?\d+)?|(?<![A-Za-z_0-9])\.\d+(?:[eE][-+]?\d+)?")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
#: Functions ngspice's ``.meas ... param='...'`` expression evaluator knows and
#: the manifests use. Anything else makes a measurement an ``expr`` one.
_PARAM_FUNCS = frozenset({"abs", "max", "min", "sqrt", "ln", "log", "exp", "pow"})
_PARAM_CHARS_RE = re.compile(r"^[\s0-9A-Za-z_.+\-*/(),]*$")


def param_expressible(expr: str, meas_names: set[str]) -> bool:
    """Can ``expr`` be a ``.meas <type> NAME param='expr'`` card?

    True when it only combines earlier ``.meas`` results with numbers,
    arithmetic and a few scalar functions. Such a measurement is carried as a
    plain ``spice`` card, which every ``klt`` version -- including an older
    fleet runner that predates ``measurements[].expr`` -- can run. Anything
    that touches a vector (``v(out)``, ``i(vsrc)``) or an operating point needs
    ``expr`` and a runner that has it.
    """
    if "'" in expr or not _PARAM_CHARS_RE.match(expr):
        return False
    stripped = _NUMBER_RE.sub("0", expr)
    idents = {i.lower() for i in _IDENT_RE.findall(stripped)}
    # a function name must be followed by '(' ; a bare identifier must be a meas name
    for ident in idents:
        if ident in meas_names:
            continue
        if ident in _PARAM_FUNCS and re.search(rf"\b{ident}\s*\(", stripped, re.IGNORECASE):
            continue
        return False
    return True


class BatchError(RuntimeError):
    """The grid could not be exported, submitted, or read back."""


class NotExportable(BatchError):
    """The manifest uses something ``klt sim`` cannot express faithfully."""


# --------------------------------------------------------------------------
# Backend selection
# --------------------------------------------------------------------------


def resolve_backend(
    requested: str, n_points: int, environ=None, allow_local_grid: bool = False
) -> str:
    """Decide ``"local"`` (this harness's ngspice runner) or ``"klt"``.

    * ``--backend batch|remote`` -> ``klt`` with that backend, explicitly.
    * ``--backend local`` -> the local runner, explicitly -- but a multi-point
      grid is refused while ``KLT_SIM_BACKEND`` marks a dispatch host, unless
      ``allow_local_grid`` (``--allow-local-grid``) is given.
    * ``--backend auto`` (default) -> follow ``KLT_SIM_BACKEND``: when it names
      an off-host backend and the grid has more than one point, hand the grid
      to ``klt`` with that backend passed explicitly (see
      :func:`klt_backend_name`). Otherwise local, which is what every
      pre-existing invocation did.
    """
    environ = os.environ if environ is None else environ
    if requested not in BACKEND_CHOICES:
        raise BatchError(f"unknown backend {requested!r}; choose from {BACKEND_CHOICES}")
    host = (environ.get("KLT_SIM_BACKEND") or "").strip()
    if requested == "local":
        if host in OFFHOST_BACKENDS and n_points > 1 and not allow_local_grid:
            raise BatchError(
                f"refusing to run a {n_points}-point grid locally: KLT_SIM_BACKEND={host} "
                "marks this as a dispatch host that must not run multi-corner ngspice "
                "grids. Drop --backend local so the grid goes through `klt sim`, or pass "
                "--allow-local-grid if this host really is a simulation box."
            )
        return "local"
    if requested in OFFHOST_BACKENDS:
        return "klt"
    if host in OFFHOST_BACKENDS and n_points > 1:
        return "klt"
    return "local"


def klt_backend_name(requested: str, environ=None) -> str:
    """The off-host backend to pass ``klt sim`` explicitly -- always, never implicit.

    ``--backend batch|remote`` -> that. ``auto`` -> the ``$KLT_SIM_BACKEND``
    value. The flag is passed explicitly because klt releases that predate
    ``$KLT_SIM_BACKEND`` (0.5.x, e.g. a ``--klt-cmd`` pinned to match the
    fleet runner) ignore the variable and would run the grid *locally*; an
    explicit ``--backend batch`` is understood by every release that has the
    batch backend and fails loudly on one that does not.
    """
    environ = os.environ if environ is None else environ
    if requested in OFFHOST_BACKENDS:
        return requested
    host = (environ.get("KLT_SIM_BACKEND") or "").strip()
    return host if host in OFFHOST_BACKENDS else ""


def klt_backend_flag(requested: str) -> list[str]:
    """The ``--backend`` argv for ``klt sim`` (empty == let klt/$KLT_SIM_BACKEND decide)."""
    return ["--backend", requested] if requested in OFFHOST_BACKENDS else []


# --------------------------------------------------------------------------
# Manifest -> klt request
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisPlan:
    kind: str
    args: str
    #: (name, ".meas ..." card) in manifest order.
    meas_cards: tuple[tuple[str, str], ...]
    #: harness measurement name -> klt measurement name that carries its value.
    value_names: dict


def check_exportable(tb: Testbench) -> AnalysisPlan:
    """Map ``tb.analyses`` / ``tb.measure`` onto a ``klt sim`` analysis, or refuse.

    Raises :class:`NotExportable` naming the first thing that cannot be
    expressed. The refusal is the feature: a thinner export would put numbers
    in an evidence record that the local runner would not have produced.
    """
    if not tb.analyses:
        raise NotExportable("manifest has no analysis")
    first = tb.analyses[0].split()
    if not first or first[0].lower() not in _ANALYSIS_KINDS:
        raise NotExportable(
            f"first analysis line {tb.analyses[0]!r} is not one of "
            f"{', '.join(_ANALYSIS_KINDS)}; klt sim runs a single analysis per corner"
        )
    kind = first[0].lower()
    args = " ".join(first[1:])

    cards: list[tuple[str, str]] = []
    for line in tb.analyses[1:]:
        tokens = line.split()
        head = tokens[0].lower() if tokens else ""
        if head != "meas" or len(tokens) < 4 or tokens[1].lower() not in _MEAS_TYPES:
            raise NotExportable(
                f"analysis line {line!r} is not a 'meas <tran|ac|dc> <name> ...' line; "
                f"klt sim cannot reproduce a '{head}' control step (single analysis, "
                "then .meas cards and expressions)"
            )
        name = tokens[2]
        if not _NAME_RE.match(name):
            raise NotExportable(f"meas name {name!r} is not a plain identifier")
        cards.append((name, "." + line.strip()))
    meas_names = [n.lower() for n, _ in cards]
    if len(set(meas_names)) != len(meas_names):
        raise NotExportable("duplicate meas names; klt sim would read back an ambiguous value")

    value_names: dict[str, str] = {}
    for measure_name, expr in tb.measure.items():
        if not _NAME_RE.match(measure_name):
            raise NotExportable(
                f"measurement name {measure_name!r} is not an identifier klt sim can "
                "emit as a vector name"
            )
        if "\n" in expr:
            raise NotExportable(f"measurement {measure_name!r}: expression spans lines")
        bare = expr.strip().lower()
        if bare in meas_names and measure_name.lower() != bare:
            # The measurement IS a .meas result: read that card's value directly.
            value_names[measure_name] = bare
        else:
            value_names[measure_name] = measure_name
    # An expression-measurement must not shadow a .meas name with another meaning.
    for measure_name, expr in tb.measure.items():
        if value_names[measure_name] == measure_name and measure_name.lower() in meas_names:
            raise NotExportable(
                f"measurement {measure_name!r} has the same name as a .meas card but "
                "a different expression"
            )
    return AnalysisPlan(kind, args, tuple(cards), value_names)


def _fragment_text(tb: Testbench) -> str:
    text = tb.netlist.read_text()
    if _TEMP_C_RE.search(re.sub(r"(?m)^\s*\*.*$", "", text)):
        raise NotExportable(
            f"{tb.netlist.name} reads the 'temp_c' .param, which the harness rebinds per "
            "point; klt sim's temperature axis sets .temp only, so the exported grid "
            "would silently hold temp_c at one value"
        )
    return text


def build_body(
    tb: Testbench,
    pdk: Pdk,
    save_vectors: list[str] | None = None,
    supply_v: float | None = None,
) -> str:
    """The circuit-body netlist ``klt sim`` ``.include``s for every corner of one request.

    Everything ``compose_deck`` puts above ``.control`` except what the klt
    request carries itself (corner ``.lib`` cards, ``.temp``, the analysis and
    the measurements). ``vdd_val`` is bound here, at parse time, to
    ``supply_v`` (default: the nominal supply) -- exactly as ``compose_deck``
    binds it per point -- so every quantity the testbench derives from it
    (rails, clock pulse amplitudes, ``.param`` references, XSPICE bridge
    thresholds, ``.meas`` expressions) follows the supply. One body per supply
    value; see :func:`build_supply_set`.
    """
    fragment = _fragment_text(tb)
    supply = tb.nominal_supply_v if supply_v is None else float(supply_v)
    lines = [
        f"* {tb.name} -- circuit body GENERATED by sim/harness/batch.py for klt sim,",
        "* do not edit. Same parameters/aliases compose_deck() emits; klt sim adds",
        "* the corner .lib cards, .temp, the analysis and the measurements.",
        "",
        "* ---- PVT parameters (one klt request per vdd_val; issue #505) -------",
        f".param vdd_nom={tb.nominal_supply_v!r}",
        f".param {SUPPLY_PARAM}={supply!r}",
    ]
    for key, value in tb.params.items():
        lines.append(f".param {key}={value}")
    lines += [
        "",
        "* ---- gf180mcu global switch params (design.ngspice) ----------------",
        f'.include "{pdk.design_include}"',
        "",
        *runner.mim_wrapper_subckts(pdk),
        "",
    ]
    for option in tb.options:
        lines.append(f".options {option}")
    if save_vectors:
        lines.append(".save " + " ".join(save_vectors))
    lines += ["", "* ---- testbench fragment ---------------------------------------------", fragment]
    if not fragment.endswith("\n"):
        lines.append("")
    return "\n".join(lines)


def corner_bundle(corner: Corner) -> dict:
    return {"name": corner.name, "sections": list(corner.sections)}


def build_request(
    tb: Testbench,
    pdk: Pdk,
    plan: AnalysisPlan,
    corner_list: list[Corner],
    temperatures: list[float],
    netlist_name: str,
    timeout_s: int,
    num_threads: int = 0,
    save_measured: bool = False,
    batch: dict | None = None,
) -> dict:
    """The ``klt sim`` request document for one supply value of this grid.

    ``corners`` is the process x temperature factorial the local runner would
    build at that supply. There is deliberately **no** ``corners.supply_v``
    key: the supply is the ``vdd_val`` ``.param`` baked into ``netlist_name``
    (see :func:`build_body`), and klt's ``supply_v`` axis can only ``alter`` a
    source -- re-keying it onto the DC rails would leave the clocks, references
    and thresholds at nominal (issue #505). klt's expansion order is
    irrelevant: results are matched back to points by value, see
    :func:`point_key`.
    """
    measurements = [{"name": name, "spice": card} for name, card in plan.meas_cards]
    meas_lower = {n.lower() for n, _ in plan.meas_cards}
    for name, expr in tb.measure.items():
        if plan.value_names[name].lower() in meas_lower:
            continue
        if plan.kind in _MEAS_TYPES and param_expressible(expr, meas_lower):
            measurements.append({
                "name": name,
                "spice": f".meas {plan.kind} {name} param='{expr}'",
            })
        else:
            measurements.append({"name": name, "expr": expr})
    options: dict = {
        "timeout_s": timeout_s,
        # Per-corner deck + ngspice log come back through klt: they are the raw
        # evidence (corners/<record-id>/<corner-id>.log) and the abort scan.
        "keep_artifacts": True,
    }
    init = ["set numdgt=10"]
    if num_threads:
        init.append(f"set num_threads={num_threads}")
    options["ngspice_init"] = init
    if save_measured:
        options["save_mode"] = "netlist"
    request: dict = {
        "netlist": netlist_name,
        "engine": "ngspice",
        "models": {"pdk": pdk.variant, "lib": MODEL_LIB_REL},
        "corners": {
            "process": [corner_bundle(c) for c in corner_list],
            "temperature_c": [float(t) for t in temperatures],
        },
        "analysis": {"kind": plan.kind, "args": plan.args},
        "measurements": measurements,
        "options": options,
    }
    if batch:
        request["batch"] = dict(batch)
    return request


def point_key(process: str, temp_c: float, vdd: float) -> tuple:
    return (process, round(float(temp_c), 6), round(float(vdd), 6))


def supply_stem(index: int, supply_v: float) -> str:
    """File stem of one supply's request/body, e.g. ``vdd0-2p97v``.

    Unique per set (the index), readable (the value), and free of ``.`` so
    ``klt sim --batch-set`` -- which names each request's output directory by
    its file stem -- gives every supply its own directory.
    """
    value = f"{float(supply_v):.6g}".replace(".", "p").replace("-", "m")
    return f"vdd{index}-{value}v"


@dataclass(frozen=True)
class SupplyRequest:
    """One member of the per-supply request set: the body and request for ``supply_v``."""

    supply_v: float
    stem: str
    body: str
    request: dict

    @property
    def body_name(self) -> str:
        return f"{self.stem}.spice"

    @property
    def request_name(self) -> str:
        return f"{self.stem}.json"


def unique_supplies(supplies: list[float]) -> list[float]:
    """``supplies`` in order with repeats (after :func:`point_key` rounding) dropped."""
    seen: set[float] = set()
    out: list[float] = []
    for value in supplies:
        key = round(float(value), 6)
        if key not in seen:
            seen.add(key)
            out.append(float(value))
    return out


def build_supply_set(
    tb: Testbench,
    pdk: Pdk,
    plan: AnalysisPlan,
    corner_list: list[Corner],
    temperatures: list[float],
    supplies: list[float],
    timeout_s: int,
    num_threads: int = 0,
    save_vectors: list[str] | None = None,
    batch: dict | None = None,
) -> list[SupplyRequest]:
    """The grid as one ``klt sim`` request per supply value (issue #505).

    Each member's body binds ``.param vdd_val=<V>`` and its request sweeps
    process x temperature with no ``corners.supply_v`` key. Together they
    cover the same process x supply x temperature factorial the local runner
    builds. Submitted together with ``klt sim --batch-set`` (:func:`submit_set`).
    """
    members: list[SupplyRequest] = []
    for index, supply in enumerate(unique_supplies(supplies)):
        stem = supply_stem(index, supply)
        members.append(SupplyRequest(
            supply_v=supply,
            stem=stem,
            body=build_body(tb, pdk, save_vectors=save_vectors, supply_v=supply),
            request=build_request(
                tb, pdk, plan, corner_list, temperatures,
                netlist_name=f"{stem}.spice",
                timeout_s=timeout_s,
                num_threads=num_threads,
                save_measured=bool(save_vectors),
                batch=batch,
            ),
        ))
    return members


# --------------------------------------------------------------------------
# Submit
# --------------------------------------------------------------------------


def klt_available(klt_cmd: str = KLT) -> list[str]:
    """The ``klt`` argv prefix (``--klt-cmd`` may be e.g. ``uvx --from ... klt``)."""
    argv = shlex.split(klt_cmd)
    if not argv or not shutil.which(argv[0]):
        raise BatchError(
            f"{klt_cmd!r} not found on PATH; the batch path needs `klt sim` "
            "(klayout-tools, see docs/environment-setup.md)."
        )
    return argv


def submit(
    request_path: Path, outdir: Path, requested_backend: str, klt_cmd: str = KLT
) -> tuple[dict, str]:
    """Run ``klt sim`` on the request; return ``(report, stderr)``.

    Gates on the JSON payload, not the exit code (klt's documented rule): exit
    3 (a limit failed) and 4 (an error/not_checked rollup) both still carry a
    full per-corner report that is read point by point. Anything that yields no
    report -- a rejected request (exit 1), a submit that failed -- raises
    :class:`BatchError` with klt's own message. There is deliberately no
    fallback to a local run here.
    """
    if requested_backend not in OFFHOST_BACKENDS:
        raise BatchError(
            f"refusing to call `klt sim` without an explicit off-host backend "
            f"(got {requested_backend!r}); an implicit backend could run the grid here"
        )
    cmd = [
        *klt_available(klt_cmd), "sim", str(request_path),
        "--outdir", str(outdir), "--format", "json",
        *klt_backend_flag(requested_backend),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        report = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        report = None
    if not isinstance(report, dict) or "corners" not in report:
        message = (proc.stderr or proc.stdout or "").strip()
        raise BatchError(
            f"`klt sim` returned no corner report (exit {proc.returncode}); "
            f"nothing was simulated locally. klt said:\n{message[-4000:]}"
        )
    return report, proc.stderr


@dataclass
class SupplyOutcome:
    """What came back for one supply's request: its klt report, or why there is none."""

    supply_v: float
    request: str
    report: dict | None = None
    error: str | None = None


def submit_set(
    members: list[SupplyRequest],
    request_dir: Path,
    outdir: Path,
    requested_backend: str,
    klt_cmd: str = KLT,
    max_in_flight: int | None = None,
) -> tuple[list[SupplyOutcome], dict | None]:
    """Submit the per-supply request set; return one outcome per member, in order.

    ``batch``: one ``klt sim --batch-set`` invocation (always the batch
    backend, never local ngspice -- klt's own contract). ``remote``: one
    ``klt sim --backend remote`` per member through :func:`submit`.

    A member whose request klt refused or whose job yielded no report becomes
    an outcome with ``error`` set and no report -- its points are then
    ``error`` points (:func:`to_point_results`), never dropped and never
    ``ok``. Only when *no* member produced a report, or the set itself could
    not start, is :class:`BatchError` raised. The second value is the
    ``--batch-set`` aggregate envelope (``None`` for ``remote``).
    """
    if requested_backend not in OFFHOST_BACKENDS:
        raise BatchError(
            f"refusing to call `klt sim` without an explicit off-host backend "
            f"(got {requested_backend!r}); an implicit backend could run the grid here"
        )
    paths = [request_dir / m.request_name for m in members]
    outcomes: list[SupplyOutcome] = []
    envelope: dict | None = None
    if requested_backend == "remote":
        for member, path in zip(members, paths):
            try:
                report, _ = submit(path, outdir / member.stem, "remote", klt_cmd=klt_cmd)
                outcomes.append(SupplyOutcome(member.supply_v, path.name, report=report))
            except BatchError as exc:
                outcomes.append(SupplyOutcome(member.supply_v, path.name, error=str(exc)))
    else:
        cmd = [
            *klt_available(klt_cmd), "sim", "--batch-set", *[str(p) for p in paths],
            "--outdir", str(outdir), "--format", "json",
        ]
        if max_in_flight:
            cmd += ["--max-in-flight", str(max_in_flight)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        try:
            envelope = json.loads(proc.stdout) if proc.stdout.strip() else None
        except json.JSONDecodeError:
            envelope = None
        entries = envelope.get("requests") if isinstance(envelope, dict) else None
        if not isinstance(entries, list):
            message = (proc.stderr or proc.stdout or "").strip()
            raise BatchError(
                f"`klt sim --batch-set` returned no set report (exit {proc.returncode}); "
                f"nothing was simulated locally. klt said:\n{message[-4000:]}"
            )
        by_index = {e.get("index"): e for e in entries if isinstance(e, dict)}
        for index, (member, path) in enumerate(zip(members, paths)):
            entry = by_index.get(index)
            if entry is None:
                outcomes.append(SupplyOutcome(
                    member.supply_v, path.name,
                    error="klt sim --batch-set reported nothing for this request",
                ))
                continue
            outcomes.append(_outcome_from_entry(member, path, entry))
    if not any(o.report for o in outcomes):
        detail = "; ".join(f"vdd={o.supply_v:g}: {o.error}" for o in outcomes)
        raise BatchError(
            "no request of the per-supply set produced a corner report; nothing was "
            f"simulated locally. klt said: {detail[-4000:]}"
        )
    return outcomes, envelope


def _outcome_from_entry(member: SupplyRequest, path: Path, entry: dict) -> SupplyOutcome:
    error = entry.get("error") or None
    report_path = entry.get("report")
    report = None
    if report_path:
        try:
            report = json.loads(Path(report_path).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            error = {"message": f"could not read klt's report {report_path}: {exc}"}
    if not isinstance(report, dict) or "corners" not in report:
        if error is None:
            error = {"message": f"klt sim --batch-set status {entry.get('status')!r} with no report"}
        code = error.get("code") if isinstance(error, dict) else None
        message = error.get("message") if isinstance(error, dict) else str(error)
        return SupplyOutcome(
            member.supply_v, path.name,
            error=(f"{code}: {message}" if code else str(message)),
        )
    return SupplyOutcome(member.supply_v, path.name, report=report)


# --------------------------------------------------------------------------
# klt report -> PointResult / provenance
# --------------------------------------------------------------------------


def _diag_text(corner: dict) -> tuple[str, bool]:
    """(first error message, timed_out)."""
    timed_out = False
    message = ""
    for diag in corner.get("diagnostics") or []:
        if diag.get("severity") != "error" and diag.get("code") != "timeout":
            continue
        if diag.get("code") == "timeout":
            timed_out = True
        if not message:
            message = f"{diag.get('code')}: {diag.get('message', '')}".strip()
    return message, timed_out


def _copy_artifact(source, destination: Path) -> bool:
    if not source:
        return False
    src = Path(source)
    if not src.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, destination)
    return True


def to_point_results(
    tb: Testbench,
    plan: AnalysisPlan,
    points: list[PvtPoint],
    outcomes: list[SupplyOutcome],
    workdir: Path,
    log_dir: Path,
    timeout_s: int,
) -> list[PointResult]:
    """One :class:`PointResult` per grid point, in grid order.

    ``outcomes`` is one entry per supply request (:func:`submit_set`). A
    corner's supply is the supply *of the request that produced it* -- the
    requests carry no ``supply_v`` axis, so klt's corners do not name one. A
    point whose supply request failed, or that klt did not report, is an
    ``error`` point (never dropped); a point whose log is missing or shows an
    aborted analysis is ``failed`` (never ``ok``), mirroring
    :func:`runner.run_point`.
    """
    by_key: dict[tuple, dict] = {}
    failed_supplies: dict[float, SupplyOutcome] = {}
    for outcome in outcomes:
        if outcome.report is None:
            failed_supplies[round(float(outcome.supply_v), 6)] = outcome
            continue
        for corner in outcome.report.get("corners", []):
            if corner.get("process") is None or corner.get("temperature_c") is None:
                continue
            by_key[point_key(corner["process"], corner["temperature_c"], outcome.supply_v)] = corner

    workdir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    results: list[PointResult] = []
    for point in points:
        corner = by_key.get(point_key(point.corner.name, point.temp_c, point.vdd))
        deck_name = f"{point.corner_id}.spice"
        log_name = f"{point.corner_id}.log"
        log_path = log_dir / log_name
        failed = failed_supplies.get(round(float(point.vdd), 6))
        if corner is None and failed is not None:
            message = (
                f"klt sim request {failed.request} (vdd_val={failed.supply_v:g}) "
                f"produced no report: {failed.error}"
            )
            log_path.write_text(f"NO RESULT: {message}\n")
            results.append(PointResult(point=point, status="error", log=log_name, message=message))
            continue
        if corner is None:
            log_path.write_text("NO RESULT: klt sim's report contains no corner for this point\n")
            results.append(PointResult(
                point=point, status="error", log=log_name,
                message="klt sim returned no result for this point",
            ))
            continue

        seconds = float(corner.get("runtime_s") or 0.0)
        artifacts = corner.get("artifacts") or {}
        has_deck = _copy_artifact(artifacts.get("deck"), workdir / deck_name)
        deck = deck_name if has_deck else ""
        message, timed_out = _diag_text(corner)

        if timed_out:
            log_path.write_text(f"TIMEOUT after {timeout_s}s\n")
            results.append(PointResult(
                point=point, status="error", seconds=seconds, deck=deck, log=log_name,
                message=f"ngspice timed out after {timeout_s}s",
            ))
            continue

        has_log = _copy_artifact(artifacts.get("log"), log_path)
        log_text = log_path.read_text(errors="replace") if has_log else ""

        values: dict[str, float] = {}
        by_name = {m.get("name", "").lower(): m for m in corner.get("measurements") or []}
        for measure_name in tb.measure:
            entry = by_name.get(plan.value_names[measure_name].lower())
            value = None if entry is None else entry.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[measure_name] = float(value)
        missing = [name for name in tb.measure if name not in values]

        if corner.get("status") == "error" and not values:
            if not has_log:
                log_path.write_text(f"klt sim reported this corner as error: {message}\n")
            # An aborted analysis is the cause even when klt's own diagnostic is
            # a generic "no measurements"; say so, as the has-values path does.
            aborted = runner.analysis_aborted(log_text)
            results.append(PointResult(
                point=point, status="error", seconds=seconds, deck=deck, log=log_name,
                message=(
                    f"ngspice aborted the analysis before its stop time: {aborted}"
                    if aborted
                    else message or "klt sim reported this corner as error"
                ),
            ))
            continue
        if missing:
            results.append(PointResult(
                point=point, status="failed", measurements=values, missing=missing,
                seconds=seconds, deck=deck, log=log_name,
                message=message or "klt sim returned no value for: " + ", ".join(missing),
            ))
            continue
        if not has_log:
            log_path.write_text("klt sim retrieved no ngspice log for this corner\n")
            results.append(PointResult(
                point=point, status="failed", measurements=values, seconds=seconds,
                deck=deck, log=log_name,
                message="klt sim retrieved no ngspice log for this corner, so a "
                "truncated analysis cannot be ruled out; not scoring it ok",
            ))
            continue
        aborted = runner.analysis_aborted(log_text)
        if aborted:
            results.append(PointResult(
                point=point, status="failed", measurements=values, seconds=seconds,
                deck=deck, log=log_name,
                message=(
                    "ngspice aborted the analysis before its stop time; every "
                    f"measurement it printed is over truncated data: {aborted}"
                ),
            ))
            continue
        if corner.get("status") == "error":
            results.append(PointResult(
                point=point, status="failed", measurements=values, seconds=seconds,
                deck=deck, log=log_name, message=message or "klt sim reported error",
            ))
            continue
        results.append(PointResult(
            point=point, status="ok", measurements=values, seconds=seconds,
            deck=deck, log=log_name,
        ))
    # The deck ngspice ran is the re-runnable evidence for a point that did not
    # score ok; keep it next to the committed log (``workdir`` is disposable).
    # ok points keep only the disposable copy: their decks are large and the
    # record's netlist/request hashes already reproduce them.
    for result in results:
        if result.status != "ok" and result.deck:
            shutil.copyfile(workdir / result.deck, log_dir / result.deck)
    return results


def request_text(request: dict) -> str:
    """The exact bytes written for a request file (and hashed into the record)."""
    return json.dumps(request, indent=2, sort_keys=True) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _reports(reports) -> list[dict]:
    """A single report, or the reports of a per-supply set (outcomes or dicts)."""
    if isinstance(reports, dict):
        return [reports]
    out = []
    for item in reports or []:
        report = item.report if isinstance(item, SupplyOutcome) else item
        if isinstance(report, dict):
            out.append(report)
    return out


def _set_status(outcomes: list[SupplyOutcome]) -> str:
    """Roll the per-request klt statuses up; a request with no report is ``error``."""
    if any(o.report is None for o in outcomes):
        return "error"
    statuses = sorted({str(o.report.get("status")) for o in outcomes})
    if "error" in statuses:
        return "error"
    return "+".join(statuses)


def execution_summary(
    outcomes: list[SupplyOutcome],
    members: list[SupplyRequest],
    requested_backend: str,
) -> dict:
    """What actually ran the points -- the ``environment.execution`` record block.

    One ``requests`` entry per supply request (supply, request file, the
    generated body / request hashes, klt status, fleet job, or the error that
    left it without a report). The top-level engine/PDK/klt fields are the
    first reporting request's; ``remote`` is kept for single-job readers.
    """
    reports = _reports(outcomes)
    first = reports[0] if reports else {}
    env = first.get("environment") or {}
    prov = first.get("provenance") or {}
    remote = env.get("remote")
    per_request = []
    for member, outcome in zip(members, outcomes):
        report = outcome.report or {}
        renv = report.get("environment") or {}
        per_request.append({
            "supply_v": member.supply_v,
            "request": member.request_name,
            "generated_body_sha256": _sha256(member.body),
            "request_sha256": _sha256(request_text(member.request)),
            "klt_netlist_sha256": renv.get("netlist_sha256"),
            "klt_status": report.get("status") if outcome.report is not None else "error",
            "klt_version": (report.get("provenance") or {}).get("klt_version"),
            "remote": renv.get("remote"),
            "error": outcome.error,
        })
    return {
        "backend": (remote or {}).get("provider") or requested_backend or "klt-default",
        "requested_backend": requested_backend or "(KLT_SIM_BACKEND)",
        "submission": (
            "klt sim --batch-set" if requested_backend == "batch" else "klt sim per request"
        ) + f", one request per {SUPPLY_PARAM} value",
        "klt_status": _set_status(outcomes),
        "klt_version": prov.get("klt_version"),
        "engine": env.get("engine"),
        "engine_version": env.get("engine_version"),
        "pdk": prov.get("pdk"),
        "models_lib_sha256": env.get("models_lib_sha256"),
        "remote": remote,
        "requests": per_request,
    }


def fleet_toolchain_drifts(reports, pins: dict) -> list:
    """Check the pins against what the *runner* reported, not this host.

    ``toolchain.check`` compares the open_pdks hash and the ngspice major. On
    the batch path those are the fleet's. When the report does not state a
    value the pin needs, that is a drift ("unknown"), exactly as an
    unidentifiable local PDK is. ``reports`` is one report or the outcomes of
    a per-supply set; every reporting request is checked (the jobs may have
    landed on different runners) and the drifts are de-duplicated.
    """
    drifts: list = []
    seen: set[str] = set()
    for report in _reports(reports) or [{}]:
        for drift in _fleet_drifts_one(report, pins):
            if str(drift) not in seen:
                seen.add(str(drift))
                drifts.append(drift)
    return drifts


def _fleet_drifts_one(report: dict, pins: dict) -> list:
    env = report.get("environment") or {}
    prov = report.get("provenance") or {}
    engine_version = str(env.get("engine_version") or "")
    ngspice_banner = (
        engine_version if "ngspice-" in engine_version
        else (f"ngspice-{engine_version}" if engine_version else "")
    )
    pdk_info = prov.get("pdk") or {}
    pdk_version = str(pdk_info.get("version") or "unknown")
    # klt reports "open_pdks <hash>"; the pin (and Pdk.version) is the bare hash.
    if pdk_version.startswith("open_pdks "):
        pdk_version = pdk_version[len("open_pdks "):].strip()

    return toolchain_mod.check(pdk_version, ngspice_banner, sys.version.split()[0], pins=pins)


def ngspice_label(reports) -> str:
    reports = _reports(reports)
    first = reports[0] if reports else {}
    env = first.get("environment") or {}
    remote = env.get("remote") or {}
    version = env.get("engine_version") or "unknown"
    where = remote.get("provider") or "klt sim"
    jobs = [
        ((r.get("environment") or {}).get("remote") or {}).get("job_id") for r in reports
    ]
    jobs = [j for j in jobs if j]
    label = "job" if len(jobs) == 1 else "jobs"
    return f"ngspice-{version} (run by {where}" + (
        f", {label} {', '.join(jobs)}" if jobs else ""
    ) + ")"


def apply_runner_caveats(
    execution: dict, reports, needs_honored_options: bool
) -> None:
    """Stamp runner/client skew into the record, or refuse to record through it.

    ``klt sim`` documents that an older fleet runner "silently ignores" newer
    request fields (``options.ngspice_init``, ``options.save_mode``). Under
    ``batch.runner_version_check: enforce`` that cannot happen (the job is
    refused). Under ``warn`` it can, so:

    * any non-``match`` skew is written into ``execution['caveats']`` and
      printed in the record, along with the one consequence that always applies
      (the ``numdgt=10`` print precision the local runner sets may not have
      been applied);
    * a run that *depends* on an ignored option (``--ngspice-threads``,
      ``--save-measured-vectors``) raises :class:`BatchError` -- its numbers
      would not be the numbers that were asked for.
    """
    caveats: list[str] = []
    skewed = None
    for report in _reports(reports):
        remote = (report.get("environment") or {}).get("remote") or {}
        compat = remote.get("runner_compatibility")
        if compat in (None, "match"):
            continue
        skewed = remote
        caveat = (
            f"runner/client klt skew: runner {remote.get('runner_klt_version')} vs client "
            f"{remote.get('client_klt_version')} ({compat}); request options newer than the "
            "runner (options.ngspice_init -> set numdgt=10 print precision) may have been "
            "silently ignored, so measured values may carry ngspice's default print precision "
            "rather than the 10 digits the local runner prints"
        )
        if caveat not in caveats:
            caveats.append(caveat)
    if not caveats:
        return
    remote = skewed
    execution["caveats"] = caveats
    if needs_honored_options:
        raise BatchError(
            "the fleet runner's klt differs from the client's "
            f"({remote.get('runner_klt_version')} vs {remote.get('client_klt_version')}) "
            "and this run used --ngspice-threads / --save-measured-vectors, which an "
            "older runner silently ignores; the results were NOT recorded. Use a "
            "client matching the runner (--klt-cmd) with --runner-version-check enforce."
        )
