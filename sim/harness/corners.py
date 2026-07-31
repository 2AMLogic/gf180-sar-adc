"""Process / voltage / temperature corner definitions for gf180mcu.

The gf180mcu ngspice model library (``sm141064.ngspice``) does not ship a
single "ss" switch that skews every device. Each device family carries its
own ``.lib`` section:

    MOS      typical | ff | ss | fs | sf
    BJT      bjt_typical | bjt_ff | bjt_ss
    diode    diode_typical | diode_ff | diode_ss
    resistor res_typical | res_ff | res_ss
    MOS cap  moscap_typical | moscap_ff | moscap_ss
    MIM cap  mimcap_typical | mimcap_ff | mimcap_ss

A *named corner* here is therefore a bundle of exactly one section per
device family. Section ordering follows the PDK's own xschem testbenches
(MOS first, then passives), and ``design.ngspice`` is always included ahead
of them because it defines the global switch params (``sw_stat_global``,
``mc_skew``, ...) the sections reference.

**Adaptation for this block (a 10-bit SAR ADC).** Upstream gf180-bandgap
adds *resistor*- and *BJT*-dominated corners on top of the five MOS corners,
because a bandgap's output rides on the resistor sheet rho and the BJT
Is/beta. A SAR ADC has no BJT and its accuracy rides on the **CDAC** and the
**3.3 V MOS** analog path instead, so the passive-dominated corners here are
capacitor corners: MiM (the CDAC unit cap), MOS-cap (sampling / parasitic
cap), and a combined "both capacitor families skewed" corner. Resistor
corners are retained for the bias/reference network. See
``sim/harness/README.md`` for the full divergence list.

**MoM capacitors**: the open gf180mcu PDK ships **no** MoM / lateral-flux
capacitor model (no such subckt exists in ``sm141064.ngspice`` or
``sm141064_mim.ngspice``), so there is no MoM ``.lib`` section to sweep. A
MoM-based CDAC would need parasitic extraction rather than a model corner;
that is recorded in ``sim/harness/README.md`` and is an input to the CDAC
topology decision, not something this harness can paper over.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

# Default PVT axes. CLAUDE.md mandates PVT corners on every recorded result;
# sim/README.md leaves the numeric matrix to the corner runner (this module).
DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 27.0, 125.0)
DEFAULT_SUPPLY_TOLERANCE: float = 0.10  # +/-10 %
DEFAULT_NOMINAL_SUPPLY_V: float = 3.3   # gf180mcu 3.3 V flavor (README input range)

#: Device families in the order their ``.lib`` sections are included.
FAMILIES: tuple[str, ...] = ("mos", "res", "bjt", "diode", "moscap", "mimcap")

_MOS, _RES, _BJT, _DIODE, _MOSCAP, _MIMCAP = range(len(FAMILIES))


def _bundle(mos: str, bjt: str, diode: str, res: str, moscap: str, mimcap: str) -> tuple[str, ...]:
    return (mos, res, bjt, diode, moscap, mimcap)


@dataclass(frozen=True)
class Corner:
    """A named process corner: an ordered list of model ``.lib`` sections."""

    name: str
    sections: tuple[str, ...]
    description: str = ""


_TYPICAL = _bundle(
    mos="typical",
    bjt="bjt_typical",
    diode="diode_typical",
    res="res_typical",
    moscap="moscap_typical",
    mimcap="mimcap_typical",
)


def _all(skew: str, description: str) -> Corner:
    """Global corner: every device family skewed the same direction."""
    if skew not in ("ff", "ss"):  # pragma: no cover - programming error
        raise ValueError(f"no global {skew!r} bundle exists in the PDK")
    return Corner(
        name=skew,
        sections=_bundle(
            mos=skew,
            bjt=f"bjt_{skew}",
            diode=f"diode_{skew}",
            res=f"res_{skew}",
            moscap=f"moscap_{skew}",
            mimcap=f"mimcap_{skew}",
        ),
        description=description,
    )


def _mos_only(name: str, mos_section: str, description: str) -> Corner:
    """MOS skewed, passives at typical."""
    return Corner(name=name, sections=(mos_section,) + _TYPICAL[1:], description=description)


def _skew(name: str, overrides: dict[int, str], description: str) -> Corner:
    """Typical everywhere except the named family indices."""
    sections = list(_TYPICAL)
    for index, section in overrides.items():
        sections[index] = section
    return Corner(name=name, sections=tuple(sections), description=description)


CORNERS: dict[str, Corner] = {
    "tt": Corner("tt", _TYPICAL, "all device families typical"),
    "ff": _all("ff", "all device families fast"),
    "ss": _all("ss", "all device families slow"),
    "fs": _mos_only("fs", "fs", "fast NMOS / slow PMOS, passives typical"),
    "sf": _mos_only("sf", "sf", "slow NMOS / fast PMOS, passives typical"),
    # Capacitor-dominated corners. A SAR ADC's linearity and its sampled
    # charge ride on the CDAC far more than on the MOS skew, and the MOS
    # corners above leave both capacitor families at typical -- so without
    # these the cap models would never be exercised off-typical.
    "cap_ff": _skew(
        "cap_ff",
        {_MOSCAP: "moscap_ff", _MIMCAP: "mimcap_ff"},
        "both capacitor families fast (low C), rest typical",
    ),
    "cap_ss": _skew(
        "cap_ss",
        {_MOSCAP: "moscap_ss", _MIMCAP: "mimcap_ss"},
        "both capacitor families slow (high C), rest typical",
    ),
    "mim_ff": _skew("mim_ff", {_MIMCAP: "mimcap_ff"}, "MiM caps fast (low C), rest typical"),
    "mim_ss": _skew("mim_ss", {_MIMCAP: "mimcap_ss"}, "MiM caps slow (high C), rest typical"),
    "moscap_ff": _skew(
        "moscap_ff", {_MOSCAP: "moscap_ff"}, "MOS caps fast (low C), rest typical"
    ),
    "moscap_ss": _skew(
        "moscap_ss", {_MOSCAP: "moscap_ss"}, "MOS caps slow (high C), rest typical"
    ),
    # Reference ladder / bias network.
    "res_ff": _skew("res_ff", {_RES: "res_ff"}, "resistors fast (low rho), rest typical"),
    "res_ss": _skew("res_ss", {_RES: "res_ss"}, "resistors slow (high rho), rest typical"),
}

CORNER_SETS: dict[str, tuple[str, ...]] = {
    # Minimum bar for a quick smoke run. Not a valid evidence matrix on its own.
    "tt": ("tt",),
    # The five classic MOS corners -- the default.
    "mos": ("tt", "ff", "ss", "fs", "sf"),
    # CDAC-facing: the capacitor families this block's accuracy rides on.
    "cdac": ("tt", "cap_ff", "cap_ss", "mim_ff", "mim_ss", "moscap_ff", "moscap_ss"),
    # Everything: MOS corners plus capacitor and resistor skews.
    "full": (
        "tt", "ff", "ss", "fs", "sf",
        "cap_ff", "cap_ss", "mim_ff", "mim_ss", "moscap_ff", "moscap_ss",
        "res_ff", "res_ss",
    ),
}
DEFAULT_CORNER_SET = "mos"


def resolve_corners(names: list[str] | tuple[str, ...] | None) -> list[Corner]:
    """Turn a list of corner *or* corner-set names into Corner objects."""
    if not names:
        names = [DEFAULT_CORNER_SET]
    resolved: list[Corner] = []
    seen: set[str] = set()
    for name in names:
        expanded = CORNER_SETS.get(name, (name,))
        for corner_name in expanded:
            if corner_name in seen:
                continue
            if corner_name not in CORNERS:
                raise KeyError(
                    f"unknown corner {corner_name!r}; "
                    f"known corners: {', '.join(sorted(CORNERS))}; "
                    f"known sets: {', '.join(sorted(CORNER_SETS))}"
                )
            seen.add(corner_name)
            resolved.append(CORNERS[corner_name])
    return resolved


def sabotage(corner_list: list[Corner]) -> list[Corner]:
    """Return the same corner *names* with every section forced to typical.

    This is the harness's **negative control**, not a feature: it reproduces
    the exact silent failure mode this repo is most exposed to -- a runner
    that appears to sweep process corners but actually simulates typical
    everywhere (wrong model include, ignored parameter, wrong section name).

    ``sim/selftest.sh`` runs the acceptance testbench once normally and once
    sabotaged; the sabotaged run **must fail** its per-axis sensitivity
    checks. If it passes, corner switching is not taking effect and every
    downstream evidence record is worthless. The CLI forces ``--no-write``
    whenever this is used, so a sabotaged run can never enter ``sim/`` as
    evidence.
    """
    return [
        Corner(name=corner.name, sections=_TYPICAL, description=f"SABOTAGED ({corner.description})")
        for corner in corner_list
    ]


def supply_points(
    nominal_v: float = DEFAULT_NOMINAL_SUPPLY_V,
    tolerance: float = DEFAULT_SUPPLY_TOLERANCE,
) -> list[float]:
    """Nominal supply and its +/- tolerance rails, low to high."""
    if tolerance <= 0:
        return [round(nominal_v, 6)]
    return [
        round(nominal_v * (1.0 - tolerance), 6),
        round(nominal_v, 6),
        round(nominal_v * (1.0 + tolerance), 6),
    ]


@dataclass(frozen=True)
class PvtPoint:
    """One point in the PVT grid -- exactly one ngspice invocation."""

    corner: Corner
    temp_c: float
    vdd: float
    index: int = field(default=0, compare=False)

    @property
    def corner_id(self) -> str:
        """The ``<process>_<temp>c_<supply>v`` id from ``sim/README.md``.

        This is the ratified corner naming for evidence records: the raw log
        for this point is ``corners/<record-id>/<corner-id>.log`` (e.g.
        ``ss_-40c_2.97v.log``, ``tt_27c_3.30v.log``).
        """
        return f"{self.corner.name}_{self.temp_c:g}c_{self.vdd:.2f}v"

    def as_dict(self) -> dict:
        return {
            "corner": self.corner.name,
            "corner_sections": list(self.corner.sections),
            "temp_c": self.temp_c,
            "vdd": self.vdd,
            "corner_id": self.corner_id,
        }


def build_grid(
    corners: list[Corner],
    temperatures: list[float] | tuple[float, ...],
    supplies: list[float],
) -> list[PvtPoint]:
    """Full factorial P x V x T grid, in a stable, reproducible order."""
    return [
        PvtPoint(corner=corner, temp_c=float(temp), vdd=float(vdd), index=i)
        for i, (corner, temp, vdd) in enumerate(
            itertools.product(corners, temperatures, supplies)
        )
    ]
