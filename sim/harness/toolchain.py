"""Pinned toolchain versions, and the loud check that they still hold.

``docs/environment-setup.md`` §1 pins the exact tool versions this repo's
evidence was validated against, and every record already copies what it
*found* into its Environment section. Recording is not enough. The gf180mcu
open_pdks hash **is** the device model set: a run against a different hash
produces numbers that are not comparable with any other record under
``sim/`` -- and it produces them silently, with no error and no obviously
wrong value. That is the same class of failure as a corner runner that
simulates typical everywhere, which is precisely what this harness exists to
make impossible.

So the pins are *checked* before any point is simulated:

- **open_pdks hash** -- exact match. A different PDK revision is different
  silicon as far as the models are concerned.
- **ngspice major version** -- a floor, not an exact match. Newer is allowed
  (and recorded); older is refused, because a run whose engine predates the
  validated one is not something this repo has ever verified.
- **python** -- a floor.

A drift is fatal by default: the CLI exits ``3`` having simulated nothing,
rather than emitting a partial or incomparable result.
``--allow-toolchain-drift`` overrides it for the deliberate case (validating
the repo against a newer PDK), and every record written under that flag
carries the drift verbatim in its Environment section -- so evidence taken
against an unpinned toolchain can never be mistaken for evidence taken
against the pinned one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"

PINS_FILENAME = "toolchain.json"

#: ``ngspice-46 : Circuit level simulation program`` -> ``46``
_NGSPICE_RE = re.compile(r"ngspice-(\d+)")


class PinsError(RuntimeError):
    """The pins file exists but cannot be used."""


@dataclass(frozen=True)
class Drift:
    """One pinned tool whose installed version does not satisfy the pin."""

    tool: str
    pinned: str
    found: str
    detail: str

    def as_dict(self) -> dict:
        return {
            "tool": self.tool,
            "pinned": self.pinned,
            "found": self.found,
            "detail": self.detail,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.tool}: {self.detail} (pinned {self.pinned}, found {self.found})"


def load_pins(sim_dir: Path | None = None) -> dict:
    """Read ``sim/toolchain.json``.

    A missing file means "nothing is pinned" and is reported as such rather
    than silently behaving like a passing check.
    """
    path = (sim_dir or SIM_DIR) / PINS_FILENAME
    if not path.is_file():
        return {}
    try:
        pins = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PinsError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(pins, dict):
        raise PinsError(f"{path} must contain a JSON object")
    return {k: v for k, v in pins.items() if not k.startswith("_")}


def parse_ngspice_major(version: str) -> int | None:
    """Major version from an ngspice banner, or ``None`` if unrecognisable."""
    match = _NGSPICE_RE.search(version or "")
    return int(match.group(1)) if match else None


def _version_tuple(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(text).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def check(
    pdk_version: str,
    ngspice_version: str,
    python_version: str,
    pins: dict | None = None,
) -> list[Drift]:
    """Compare the resolved toolchain against the pins. Empty list == OK."""
    pins = load_pins() if pins is None else pins
    drifts: list[Drift] = []

    pinned_pdk = pins.get("open_pdks")
    if pinned_pdk:
        if pdk_version == "unknown":
            drifts.append(
                Drift(
                    tool="open_pdks",
                    pinned=pinned_pdk,
                    found="unknown",
                    detail="this PDK install records no open_pdks revision, so the "
                    "models it ships cannot be identified",
                )
            )
        elif pdk_version != pinned_pdk:
            drifts.append(
                Drift(
                    tool="open_pdks",
                    pinned=pinned_pdk,
                    found=pdk_version,
                    detail="different PDK revision — the device models, and therefore "
                    "every measured value, differ from the pinned ones",
                )
            )

    pinned_ngspice = pins.get("ngspice_min_major")
    if pinned_ngspice is not None:
        major = parse_ngspice_major(ngspice_version)
        if major is None:
            drifts.append(
                Drift(
                    tool="ngspice",
                    pinned=f">= {pinned_ngspice}",
                    found=ngspice_version or "unknown",
                    detail="could not parse an ngspice version from the banner",
                )
            )
        elif major < int(pinned_ngspice):
            drifts.append(
                Drift(
                    tool="ngspice",
                    pinned=f">= {pinned_ngspice}",
                    found=str(major),
                    detail="older than the validated engine",
                )
            )

    pinned_python = pins.get("python_min")
    if pinned_python:
        if _version_tuple(python_version) < _version_tuple(pinned_python):
            drifts.append(
                Drift(
                    tool="python",
                    pinned=f">= {pinned_python}",
                    found=python_version,
                    detail="older than the minimum the harness is written against",
                )
            )

    return drifts


def summary(drifts: list[Drift], pins: dict, allowed: bool = False) -> dict:
    """The block recorded in a record's ``environment.toolchain``."""
    return {
        "pins": dict(pins),
        "pinned": bool(pins),
        "conforms": not drifts,
        "drift_allowed": bool(allowed),
        "drift": [d.as_dict() for d in drifts],
    }


def format_drifts(drifts: list[Drift]) -> str:
    """The loud, actionable message printed before refusing to simulate."""
    lines = [
        "toolchain drift: the installed tools do not match the versions this",
        "repo's evidence is pinned to (sim/toolchain.json, docs/environment-setup.md §1):",
        "",
    ]
    lines += [f"  - {drift}" for drift in drifts]
    lines += [
        "",
        "Nothing was simulated. A record taken against a drifted toolchain is not",
        "comparable with the existing records under sim/, so the run is refused",
        "rather than banked as evidence. Either:",
        "",
        "  - install the pinned versions (docs/environment-setup.md), or",
        "  - re-validate deliberately with --allow-toolchain-drift, which records",
        "    the drift in the record's Environment section, then update",
        "    sim/toolchain.json and docs/environment-setup.md §1 in the same change.",
    ]
    return "\n".join(lines)
