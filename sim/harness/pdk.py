"""gf180mcu PDK discovery.

No PDK path is ever hardcoded into a netlist or a testbench. Everything
resolves through this module so that the harness runs unchanged on a
developer box, a CI runner, or a fresh agent container.

Resolution order (first hit wins):

1. ``GF180_PDK_PATH``   -- absolute path to the *variant* directory
                           (the one containing ``libs.tech/``), e.g.
                           ``~/.volare/gf180mcuD``.
2. ``PDK_ROOT`` (+ ``PDK``, default ``gf180mcuD``) -- the conventional
                           open_pdks / volare / OpenLane environment.
3. ``sim/pdk.local.json`` -- machine-local override, git-ignored.
4. ``sim/pdk.json``      -- committed defaults: variant + search roots.
5. Built-in search roots -- volare store, open_pdks install prefixes.

Ported from ``2AMLogic/gf180-bandgap@58024be``. The one addition is
:attr:`Pdk.mim_stack` / :meth:`Pdk.mim_subckt` -- see below.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"

DEFAULT_VARIANT = "gf180mcuD"

# Search roots used when nothing else pins the PDK down. Each is a directory
# that is expected to *contain* variant directories (gf180mcuA..D).
BUILTIN_SEARCH_ROOTS = (
    "~/.volare",
    "~/.ciel",
    "/usr/share/pdk",
    "/usr/local/share/pdk",
    "~/share/pdk",
    "/opt/pdk",
)

#: gf180mcu variant -> the metal pair the MIM capacitor sits between.
#:
#: The MIM model library (``sm141064_mim.ngspice``, section ``cap_mim_new``)
#: defines one subckt per metal-stack option -- ``cap_mim_2f0_m4m5_noshield``
#: and friends -- so the *stack* determines the subckt name a CDAC testbench
#: must instantiate. That mapping is nowhere in the ngspice models; it comes
#: from the PDK's own DRC variant table
#: (``libs.tech/klayout/drc/README.md``: ``variant=A`` -> ``metal_level=3LM``,
#: ``B`` -> ``4LM``, ``C``/``D`` -> ``5LM``), cross-referenced against the
#: ``OPTION-A [3LM]`` / ``OPTION-B [4LM|5LM|6LM]`` banners in the MIM library.
#:
#: This exists so that no testbench in this repo hardcodes a metal-stack
#: assumption: the harness emits ``mim_cap_1f0`` / ``mim_cap_1f5`` /
#: ``mim_cap_2f0`` wrapper subckts bound to the resolved variant's stack, and
#: an unknown variant is a loud error rather than a silent wrong stack.
MIM_STACK_BY_VARIANT: dict[str, str] = {
    "gf180mcuA": "m2m3",   # 3LM
    "gf180mcuB": "m3m4",   # 4LM
    "gf180mcuC": "m4m5",   # 5LM (metal_top 9K)
    "gf180mcuD": "m4m5",   # 5LM (metal_top 11K) -- the variant this repo targets
}

#: MIM densities the PDK models, in fF/um^2, and their subckt stem.
MIM_DENSITIES: dict[str, str] = {
    "1f0": "cap_mim_1f0",
    "1f5": "cap_mim_1f5",
    "2f0": "cap_mim_2f0",
}

INSTALL_HINT = """\
gf180mcu PDK not found.

Install it with volare (recommended, ~5 GB):

    pip install volare
    volare enable --pdk gf180mcu <version-hash>     # see: volare ls-remote --pdk gf180mcu

volare installs into ~/.volare/<variant> and this harness finds it there
automatically. If your PDK lives somewhere else, point the harness at it:

    export GF180_PDK_PATH=/path/to/gf180mcuD        # variant dir, contains libs.tech/
    # or the conventional pair:
    export PDK_ROOT=/path/to/pdk-root
    export PDK=gf180mcuD

...or commit-free machine-local config in sim/pdk.local.json:

    {"variant": "gf180mcuD", "search_roots": ["/my/pdks"]}

See docs/environment-setup.md for the full bootstrap.
"""


class PdkNotFound(RuntimeError):
    """Raised when no usable gf180mcu install can be located."""


class UnknownVariant(RuntimeError):
    """Raised when a located variant has no known MIM metal stack."""


@dataclass(frozen=True)
class Pdk:
    """A located gf180mcu install."""

    path: Path          # .../gf180mcuD
    variant: str        # gf180mcuD
    source: str         # how we found it (for provenance in results)

    @property
    def ngspice_dir(self) -> Path:
        return self.path / "libs.tech" / "ngspice"

    @property
    def xschem_dir(self) -> Path:
        return self.path / "libs.tech" / "xschem"

    @property
    def klayout_dir(self) -> Path:
        return self.path / "libs.tech" / "klayout"

    @property
    def design_include(self) -> Path:
        """Global switches / corner params. Must be included before models."""
        return self.ngspice_dir / "design.ngspice"

    @property
    def model_lib(self) -> Path:
        """Main device model library (``.lib <section>`` sections)."""
        return self.ngspice_dir / "sm141064.ngspice"

    @property
    def mim_stack(self) -> str:
        """Metal pair the MIM cap sits between for this variant, e.g. ``m4m5``.

        Raises :class:`UnknownVariant` rather than guessing: silently
        instantiating the wrong MIM subckt would produce a plausible but
        wrong CDAC unit capacitance in every record.
        """
        try:
            return MIM_STACK_BY_VARIANT[self.variant]
        except KeyError:
            raise UnknownVariant(
                f"no known MIM metal stack for gf180mcu variant {self.variant!r}. "
                f"Known variants: {', '.join(sorted(MIM_STACK_BY_VARIANT))}. "
                "Add the variant to MIM_STACK_BY_VARIANT (sim/harness/pdk.py) with "
                "its metal_level from the PDK's libs.tech/klayout/drc/README.md "
                "variant table -- do not guess."
            ) from None

    def mim_subckt(self, density: str) -> str:
        """PDK subckt name for a MIM unit cap of ``density`` fF/um^2."""
        try:
            stem = MIM_DENSITIES[density]
        except KeyError:
            raise KeyError(
                f"unknown MIM density {density!r}; known: {', '.join(sorted(MIM_DENSITIES))}"
            ) from None
        return f"{stem}_{self.mim_stack}_noshield"

    @property
    def version(self) -> str:
        """open_pdks commit recorded by volare, or 'unknown'."""
        sources = self.path / "SOURCES"
        if sources.is_file():
            for line in sources.read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "open_pdks":
                    return parts[1]
            text = sources.read_text().strip()
            if text:
                return text.splitlines()[0].strip()
        return "unknown"

    def provenance(self) -> dict:
        record = {
            "path": str(self.path),
            "variant": self.variant,
            "open_pdks_version": self.version,
            "discovered_via": self.source,
        }
        try:
            record["mim_stack"] = self.mim_stack
        except UnknownVariant:
            record["mim_stack"] = "unknown"
        return record


def _is_valid_variant_dir(path: Path) -> bool:
    return (path / "libs.tech" / "ngspice" / "sm141064.ngspice").is_file()


def _load_config() -> dict:
    """Merge sim/pdk.json with sim/pdk.local.json (local wins)."""
    config: dict = {}
    for name in ("pdk.json", "pdk.local.json"):
        candidate = SIM_DIR / name
        if candidate.is_file():
            try:
                config.update(json.loads(candidate.read_text()))
            except json.JSONDecodeError as exc:  # pragma: no cover - config typo
                raise RuntimeError(f"{candidate} is not valid JSON: {exc}") from exc
    return config


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def find_pdk(variant: str | None = None) -> Pdk:
    """Locate a gf180mcu install, or raise :class:`PdkNotFound`."""
    config = _load_config()
    variant = variant or os.environ.get("PDK") or config.get("variant") or DEFAULT_VARIANT

    direct = os.environ.get("GF180_PDK_PATH")
    if direct:
        path = _expand(direct)
        if not _is_valid_variant_dir(path):
            raise PdkNotFound(
                f"GF180_PDK_PATH={direct} does not look like a gf180mcu variant "
                f"directory (expected {path}/libs.tech/ngspice/sm141064.ngspice).\n\n"
                + INSTALL_HINT
            )
        return Pdk(path=path, variant=path.name, source="GF180_PDK_PATH")

    tried: list[str] = []

    pdk_root = os.environ.get("PDK_ROOT")
    if pdk_root:
        path = _expand(pdk_root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            return Pdk(path=path, variant=variant, source="PDK_ROOT")

    roots = list(config.get("search_roots") or ()) + list(BUILTIN_SEARCH_ROOTS)
    for root in roots:
        path = _expand(root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            return Pdk(path=path, variant=variant, source=f"search_root:{root}")

    raise PdkNotFound(
        "Looked for gf180mcu variant %r in:\n  %s\n\n%s"
        % (variant, "\n  ".join(tried), INSTALL_HINT)
    )


def pdk_available(variant: str | None = None) -> bool:
    try:
        find_pdk(variant)
    except PdkNotFound:
        return False
    return True
