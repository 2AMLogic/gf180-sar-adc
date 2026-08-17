"""Testbench manifests.

Testbenches follow the directory convention ratified in ``sim/README.md``:
each experiment gets ``sim/<experiment-slug>/`` and its testbench lives in
that experiment's ``testbench/`` subdirectory:

    sim/<experiment-slug>/testbench/tb.json            the manifest (this module)
    sim/<experiment-slug>/testbench/<something>.spice  a *netlist fragment*

The fragment must NOT contain ``.include`` of models, ``.lib``, ``.temp``,
``.control`` or ``.end``: the harness owns all of those so that one netlist
can be swept across the whole PVT grid without editing. The harness hands
the fragment these parameters:

    vdd_val   the supply for this PVT point (nominal, +tol or -tol)
    vdd_nom   the nominal supply, for ratio-style measurements
    temp_c    the temperature for this PVT point (also set via .temp)

plus anything in the manifest's ``params`` map, and the PDK-variant-bound
``mim_cap_1f0`` / ``mim_cap_1f5`` / ``mim_cap_2f0`` wrapper subckts (see
``runner.compose_deck``).

Because ``sim/README.md`` requires every record to name the claim it
substantiates and, for ADC claims, the methodology behind it, a manifest may
also carry an ``evidence`` block -- see ``harness/evidence.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import evidence as evidence_mod
from .corners import (
    DEFAULT_CORNER_SET,
    DEFAULT_NOMINAL_SUPPLY_V,
    DEFAULT_SUPPLY_TOLERANCE,
    DEFAULT_TEMPERATURES_C,
)

MANIFEST_NAME = "tb.json"

#: Name of the per-experiment subdirectory that holds the testbench, per
#: the directory convention in ``sim/README.md``.
TESTBENCH_DIRNAME = "testbench"

FORBIDDEN_DIRECTIVES = (".control", ".endc", ".end", ".lib", ".temp", ".include")

#: Keys a ``checks`` entry may carry. Anything else is a typo that would
#: otherwise be silently ignored -- and a silently-ignored ``min_spread_pct``
#: is exactly the failure this harness exists to prevent.
CHECK_KEYS = (
    "min",
    "max",
    "max_spread_pct",
    "min_spread_pct",
    "min_spread_pct_by_axis",
    "max_spread_pct_by_axis",
    "description",
)

#: Axis names accepted by the per-axis sensitivity checks.
AXES = ("process", "temperature", "supply")

#: Stated once so the manifest loader and ``run_corners.py --netlist-provenance``
#: reject the same set of strings with the same message.
PROVENANCE_RULE = (
    "netlist_provenance must be 'schematic', 'schematic (<detail>)' or start with "
    "'extracted' (sim/README.md 'Extracted vs schematic semantics')"
)


def valid_netlist_provenance(value: str) -> bool:
    """Is ``value`` an acceptable ``Netlist provenance`` field?

    Three forms, and the middle one is not cosmetic. ``sim/README.md`` splits
    provenance into ``schematic`` (``design/...``) and ``extracted``
    (post-layout, ``layout/...``) so that a post-layout re-run is never
    mistaken for the pre-layout record. A **parametric variant of the
    schematic netlist** -- the same generator run at a deliberately different
    device value, as ``sim/dr0019-cu-sweep/`` does to isolate what a sizing
    decision costs -- is neither. It is not the ratified schematic deck, so
    calling it bare ``schematic`` would silently overstate it; and it has
    never been through layout, so calling it ``extracted`` would be simply
    false. Without the ``schematic (<detail>)`` form the only way to record
    such a run through this harness is to mislabel it, which is exactly the
    failure the check exists to prevent -- so the form is admitted, and the
    parenthesised detail (which the record prints verbatim) is what states
    the deviation.
    """
    return (
        value == "schematic"
        or value.startswith("schematic (")
        or value.startswith("extracted")
    )


@dataclass
class Testbench:
    directory: Path
    name: str
    netlist: Path
    description: str = ""
    claim: str = ""
    #: "schematic" (default), "schematic (<detail>)" for a parametric variant
    #: of the schematic deck, or "extracted" (post-layout) -- sim/README.md
    #: "Extracted vs schematic semantics", and `valid_netlist_provenance`
    #: below for why the middle form exists. A manifest may state "extracted"
    #: directly (a testbench that is ALWAYS run against a post-layout
    #: netlist); `run_corners.py --netlist-provenance` overrides it per-run,
    #: for the more common case of one manifest's measure/check machinery
    #: reused against an alternate netlist file via `--netlist`.
    netlist_provenance: str = "schematic"
    nominal_supply_v: float = DEFAULT_NOMINAL_SUPPLY_V
    supply_tolerance: float = DEFAULT_SUPPLY_TOLERANCE
    temperatures_c: tuple[float, ...] = DEFAULT_TEMPERATURES_C
    corners: tuple[str, ...] = (DEFAULT_CORNER_SET,)
    analyses: tuple[str, ...] = ("op",)
    measure: dict[str, str] = field(default_factory=dict)
    params: dict[str, str | float] = field(default_factory=dict)
    checks: dict[str, dict] = field(default_factory=dict)
    options: tuple[str, ...] = ()
    evidence: evidence_mod.Extensions = field(default_factory=evidence_mod.Extensions)

    @property
    def experiment(self) -> str:
        """The ``<experiment-slug>`` this testbench belongs to.

        ``sim/<experiment-slug>/testbench/tb.json`` -> ``<experiment-slug>``.
        """
        return self.directory.parent.name

    @property
    def experiment_dir(self) -> Path:
        """``sim/<experiment-slug>/`` -- where records/corners/snapshots live."""
        return self.directory.parent

    @property
    def netlist_sha256(self) -> str:
        return hashlib.sha256(self.netlist.read_bytes()).hexdigest()

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256((self.directory / MANIFEST_NAME).read_bytes()).hexdigest()

    def provenance(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "claim": self.claim,
            "experiment": self.experiment,
            "directory": self.directory.name,
            "netlist": self.netlist.name,
            "netlist_sha256": self.netlist_sha256,
            "netlist_provenance": self.netlist_provenance,
            "manifest_sha256": self.manifest_sha256,
            "nominal_supply_v": self.nominal_supply_v,
            "supply_tolerance": self.supply_tolerance,
        }


def _require(manifest: dict, key: str, path: Path):
    if key not in manifest:
        raise ValueError(f"{path}: missing required key {key!r}")
    return manifest[key]


def _validate_checks(checks: dict[str, dict], measure: dict[str, str], path: Path) -> None:
    for name, spec in checks.items():
        if name not in measure:
            raise ValueError(
                f"{path}: check {name!r} does not name a measurement "
                f"(known: {', '.join(sorted(measure))})"
            )
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: check {name!r} must be an object, got {type(spec).__name__}")
        unknown = sorted(set(spec) - set(CHECK_KEYS))
        if unknown:
            raise ValueError(
                f"{path}: check {name!r} has unknown key(s) {', '.join(unknown)}; "
                f"known: {', '.join(CHECK_KEYS)}"
            )
        for axis_key in ("min_spread_pct_by_axis", "max_spread_pct_by_axis"):
            axes = spec.get(axis_key)
            if axes is None:
                continue
            if not isinstance(axes, dict):
                raise ValueError(f"{path}: check {name!r}: {axis_key} must be an object")
            unknown_axes = sorted(set(axes) - set(AXES))
            if unknown_axes:
                raise ValueError(
                    f"{path}: check {name!r}: unknown axis/axes {', '.join(unknown_axes)} in "
                    f"{axis_key}; known: {', '.join(AXES)}"
                )


def load(directory: str | Path) -> Testbench:
    """Load a testbench manifest into a :class:`Testbench`.

    Accepts the experiment directory (``sim/<slug>/``), its ``testbench/``
    subdirectory, or the ``tb.json`` path itself.
    """
    directory = Path(directory).resolve()
    if directory.is_file() and directory.name == MANIFEST_NAME:
        directory = directory.parent
    if (directory / TESTBENCH_DIRNAME / MANIFEST_NAME).is_file():
        directory = directory / TESTBENCH_DIRNAME
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"no {MANIFEST_NAME} in {directory}")

    manifest = json.loads(manifest_path.read_text())

    netlist = directory / _require(manifest, "netlist", manifest_path)
    if not netlist.is_file():
        raise FileNotFoundError(f"{manifest_path}: netlist {netlist} does not exist")

    measure = dict(_require(manifest, "measure", manifest_path))
    if not measure:
        raise ValueError(f"{manifest_path}: 'measure' must define at least one measurement")
    for key in measure:
        if not key.replace("_", "").isalnum():
            raise ValueError(
                f"{manifest_path}: measurement name {key!r} must be alphanumeric/underscore "
                "(it becomes an ngspice vector name)"
            )
        if key != key.lower():
            # ngspice folds vector names to lower case, so `let m_hold_L0 = ...`
            # prints back as `m_hold_l0` and the runner's exact-name match never
            # finds it -- every point fails with "no measurements parsed" after
            # the whole grid has already been simulated. Refuse at load time
            # instead of discovering it hours in.
            raise ValueError(
                f"{manifest_path}: measurement name {key!r} must be lower case "
                "(ngspice folds vector names, so an upper-case name is printed "
                f"back as {key.lower()!r} and never matches)"
            )

    checks = dict(manifest.get("checks", {}))
    _validate_checks(checks, measure, manifest_path)

    extensions = evidence_mod.from_manifest(manifest.get("evidence"))
    extensions.validate()

    netlist_provenance = str(manifest.get("netlist_provenance", "schematic"))
    if not valid_netlist_provenance(netlist_provenance):
        raise ValueError(
            f"{manifest_path}: {PROVENANCE_RULE}; got {netlist_provenance!r}"
        )

    tb = Testbench(
        directory=directory,
        name=manifest.get("name", directory.parent.name),
        netlist=netlist,
        description=manifest.get("description", ""),
        claim=manifest.get("claim", ""),
        netlist_provenance=netlist_provenance,
        nominal_supply_v=float(manifest.get("nominal_supply_v", DEFAULT_NOMINAL_SUPPLY_V)),
        supply_tolerance=float(manifest.get("supply_tolerance", DEFAULT_SUPPLY_TOLERANCE)),
        temperatures_c=tuple(
            float(t) for t in manifest.get("temperatures_c", DEFAULT_TEMPERATURES_C)
        ),
        corners=tuple(manifest.get("corners", (DEFAULT_CORNER_SET,))),
        analyses=tuple(manifest.get("analyses", ("op",))),
        measure=measure,
        params={k: v for k, v in manifest.get("params", {}).items()},
        checks=checks,
        options=tuple(manifest.get("options", ())),
        evidence=extensions,
    )
    validate_netlist(tb)
    return tb


def validate_netlist(tb: Testbench) -> None:
    """Reject fragments that try to own what the harness owns.

    Catching this here is much friendlier than debugging a duplicated
    ``.end`` or a hardcoded ``.temp 27`` that silently pins every corner to
    room temperature.
    """
    problems: list[str] = []
    for lineno, raw in enumerate(tb.netlist.read_text().splitlines(), start=1):
        line = raw.strip().lower()
        if not line.startswith("."):
            continue
        directive = line.split()[0]
        if directive in FORBIDDEN_DIRECTIVES:
            problems.append(f"  line {lineno}: {raw.strip()}")
    if problems:
        raise ValueError(
            f"{tb.netlist}: netlist fragments must not contain "
            f"{', '.join(FORBIDDEN_DIRECTIVES)} -- the harness supplies the models, "
            "corner libs, temperature and control block:\n" + "\n".join(problems)
        )


def discover(root: str | Path) -> list[Path]:
    """Every experiment directory under ``root`` that owns a testbench.

    Looks for ``<root>/<experiment-slug>/testbench/tb.json`` and returns the
    ``<experiment-slug>`` directories, sorted.
    """
    root = Path(root)
    return sorted(
        p.parent.parent for p in root.glob(f"*/{TESTBENCH_DIRNAME}/{MANIFEST_NAME}")
    )
