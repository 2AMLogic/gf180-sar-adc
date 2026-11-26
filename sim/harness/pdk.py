"""gf180mcu PDK discovery.

No PDK path is ever hardcoded into a netlist or a testbench. Everything
resolves through this module so that the harness runs unchanged on a
developer box, a CI runner, or a fresh agent container.

Resolution order (first hit wins):

1. ``GF180_PDK_PATH``   -- absolute path to the *variant* directory
                           (the one containing ``libs.tech/``), e.g.
                           ``~/.ciel/gf180mcuD``.
2. ``PDK_ROOT`` (+ ``PDK``, default ``gf180mcuD``) -- the conventional
                           open_pdks / ciel / OpenLane environment.
3. ``sim/pdk.local.json`` -- machine-local override, git-ignored.
4. ``sim/pdk.json``      -- committed defaults: variant + search roots.
5. Built-in search roots -- ciel store (``~/.ciel``), the legacy volare
                           store (``~/.volare``, lower priority), open_pdks
                           install prefixes. Among the *search-root* hits, a
                           tree whose open_pdks revision equals the
                           ``sim/toolchain.json`` pin wins over an earlier hit
                           that does not, so a stray old tree cannot shadow
                           the pinned one. If no hit matches the pin, the
                           first hit is returned and the mismatch is visible
                           via :attr:`Pdk.pin_status` (and fatal in
                           ``toolchain.check`` unless drift is allowed).

Ported from ``2AMLogic/gf180-bandgap@58024be``. The one addition is
:attr:`Pdk.mim_stack` / :meth:`Pdk.mim_subckt` -- see below.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"

DEFAULT_VARIANT = "gf180mcuD"

STORE_MARKER = ".pdk-store.json"
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
INSTALLER_TOOLS = ("ciel",)
TOOL_VERSION_TIMEOUT_S = 10

# Search roots used when nothing else pins the PDK down. Each is a directory
# that is expected to *contain* variant directories (gf180mcuA..D).
BUILTIN_SEARCH_ROOTS = (
    "~/.ciel",
    "~/.volare",   # legacy store: kept as a lower-priority, pin-checked fallback
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

Install it with ciel (recommended, ~3.6 GB on disk for all four variants),
at the open_pdks revision pinned in sim/toolchain.json:

    pip install ciel==2.6.1
    ciel enable --pdk-family gf180mcu \\
      -l default -l gf180mcu_osu_sc_gp9t3v3 -l gf180mcu_osu_sc_gp12t3v3 \\
      <open_pdks-hash>

-l SELECTS the library set rather than adding to it, and the two OSU 3.3 V
libraries are outside ciel's gf180mcu default set; this selection is the one
the repository's committed evidence was taken on (docs/environment-setup.md
section 3).

ciel installs into ~/.ciel/<variant> and this harness finds it there
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
    #: Installer captured by :meth:`capture_installer`; when set, it is what
    #: :attr:`installer` reports, so a record names the install the run
    #: actually used even if the variant symlink is repointed mid-run.
    captured_installer: dict | None = field(default=None, repr=False, compare=False)

    @property
    def ngspice_dir(self) -> Path:
        return self.path / "libs.tech" / "ngspice"

    @property
    def xschem_dir(self) -> Path:
        return self.path / "libs.tech" / "xschem"

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
        """open_pdks commit recorded in the install's ``SOURCES``, or 'unknown'."""
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

    @property
    def pin_status(self) -> str:
        """``"match"``, ``"unpinned"``, ``"unknown"`` or ``"mismatch"`` vs the pin.

        ``unknown`` (no parseable ``SOURCES``) is deliberately not a pass.
        """
        return pin_status(self.version)

    @property
    def installer(self) -> dict:
        """What placed this PDK tree, as the tree itself records it.

        ``kind`` is ``"pdk-store"`` when the PDK store's marker names this
        tree: the bundle sha256 in it identifies every byte of the install,
        and ``via`` / ``synced`` say how and when it was placed. Otherwise
        ``"unrecorded"``: ``ciel enable``, volare and a hand copy all leave
        no per-install record, so no installer version exists to report. The
        ``ciel`` found on PATH (:func:`installer_tools`) is a separate
        observation and never a substitute. Nothing here is inferred.
        """
        if self.captured_installer is not None:
            return self.captured_installer
        return self._read_installer()

    def capture_installer(self) -> "Pdk":
        """A copy whose :attr:`installer` is read now and held fixed.

        Call before any model file is staged or read: the variant path is
        often a symlink that the launcher can repoint while a run is in
        flight, and the record must name the bytes the run was given.
        """
        return replace(self, captured_installer=self._read_installer())

    def _read_installer(self) -> dict:
        marker, path, reason = _store_marker(self.path.resolve(), self.variant, self.version)
        if marker is None:
            return {"kind": "unrecorded", "reason": reason}
        return {
            "kind": "pdk-store",
            "via": str(marker.get("via") or marker.get("bucket") or "unknown"),
            "bundle_sha256": marker["sha256"],
            "synced": str(marker.get("synced") or "unknown"),
            "marker": str(path),
        }

    def provenance(self) -> dict:
        record = {
            "path": str(self.path),
            "variant": self.variant,
            "open_pdks_version": self.version,
            "pin_status": self.pin_status,
            "discovered_via": self.source,
            "installer": self.installer,
        }
        try:
            record["mim_stack"] = self.mim_stack
        except UnknownVariant:
            record["mim_stack"] = "unknown"
        return record


def describe_installer(installer: dict) -> str:
    """One-line rendering of :attr:`Pdk.installer` for ``--check-env``."""
    if installer.get("kind") == "pdk-store":
        return (
            f"PDK store (via {installer.get('via')}), "
            f"bundle sha256 {installer.get('bundle_sha256')}, "
            f"synced {installer.get('synced')}"
        )
    return f"unrecorded ({installer.get('reason')})"


def installer_tools(
    names: tuple[str, ...] = INSTALLER_TOOLS,
    which=shutil.which,
    run=subprocess.run,
) -> dict[str, str]:
    """``{tool: version}`` for the PDK installer tools on this host's PATH.

    A tool that is not on PATH is absent from the dict; one that is on PATH
    but printed no version for ``--version`` maps to ``"unavailable"``. This
    is what is installed *now*. It is never evidence of what placed a PDK
    tree -- only the tree's own store marker (:attr:`Pdk.installer`) is --
    so a record reports it as an observation beside the installer, not as it.
    """
    tools: dict[str, str] = {}
    for name in names:
        found = which(name)
        if not found:
            continue
        try:
            proc = run(
                [found, "--version"],
                capture_output=True,
                text=True,
                timeout=TOOL_VERSION_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            tools[name] = "unavailable"
            continue
        lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        tools[name] = lines[0] if proc.returncode == 0 and lines else "unavailable"
    return tools


def _store_marker(
    resolved: Path, variant: str, version: str
) -> tuple[dict | None, Path | None, str]:
    """``(marker, marker path, reason)`` for the store marker that names a tree.

    ``resolved`` is the variant directory with every symlink followed. Only
    two places are looked at, the tree itself and the directory holding it,
    because a marker anywhere higher up describes another tree. A marker
    counts only if it names this tree's family and the revision the tree's
    own ``SOURCES`` records; anything else comes back as ``None`` with the
    reason it was not adopted.
    """
    for path in (resolved / STORE_MARKER, resolved.parent / STORE_MARKER):
        if not path.is_file():
            continue
        try:
            marker = json.loads(path.read_text())
        except (OSError, ValueError):
            return None, path, f"the PDK-store marker `{path}` is not readable JSON"
        if not isinstance(marker, dict):
            return None, path, f"the PDK-store marker `{path}` is not a JSON object"
        name = str(marker.get("name") or "")
        # The family is the variant minus its trailing letter (gf180mcuD ->
        # gf180mcu); anything but that exact string is another family.
        family = variant[:-1] if variant in MIM_STACK_BY_VARIANT else variant
        if name != family:
            return None, path, (
                f"the PDK-store marker `{path}` names family {name or 'none'!r}, "
                f"not the `{family}` family of the `{variant}` tree"
            )
        if version == "unknown" or marker.get("version") != version:
            return None, path, (
                f"the PDK-store marker `{path}` names revision {marker.get('version')!r}; "
                f"this tree's SOURCES says `{version}`"
            )
        digest = marker.get("sha256")
        if not isinstance(digest, str) or not _SHA256_HEX.fullmatch(digest):
            return None, path, (
                f"the PDK-store marker `{path}` carries bundle sha256 {digest!r}, "
                "which is not a 64-character lowercase hex digest"
            )
        return marker, path, ""
    return None, None, "no PDK-store marker in this tree or in the directory holding it"


def pinned_open_pdks() -> str | None:
    """The ``open_pdks`` revision pinned in ``sim/toolchain.json``, if any."""
    path = SIM_DIR / "toolchain.json"
    if not path.is_file():
        return None
    try:
        pin = json.loads(path.read_text()).get("open_pdks")
    except (json.JSONDecodeError, AttributeError):
        return None
    return pin or None


def pin_status(version: str) -> str:
    """Compare an open_pdks revision with the ``toolchain.json`` pin."""
    pin = pinned_open_pdks()
    if not pin:
        return "unpinned"
    if version == "unknown":
        return "unknown"
    return "match" if version == pin else "mismatch"


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
    hits: list[Pdk] = []
    for root in roots:
        path = _expand(root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            hits.append(Pdk(path=path, variant=variant, source=f"search_root:{root}"))
    if hits:
        # Prefer a tree at the pinned revision over an earlier stray one;
        # with no match, return the first so the mismatch is reported
        # (never silently used) by the toolchain gate.
        return next((h for h in hits if h.pin_status == "match"), hits[0])

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
