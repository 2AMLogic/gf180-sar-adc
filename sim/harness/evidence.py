"""The ``sim/README.md`` evidence-record schema, in code.

``sim/README.md`` (ratified locally as #5) defines the record every run must
write. It has a **base** field set ported unchanged from gf180-bandgap, plus
**five ADC-specific extension groups** that have no upstream equivalent:

    dynamic-test (FFT) metadata   ENOB / SNDR / SFDR / THD claims
    linearity methodology         INL / DNL claims
    Monte Carlo convention        seed handling + mismatch scope + sigma
    noise methodology             noise-budget claims
    characterization variant      "Measured value(s)" + "Data provenance"
                                  instead of a pass/fail "Result"

Upstream gf180-bandgap's harness knows only the base fields -- its own PR had
to be reworked because the writer was built before the format was ratified.
This module exists so that does not repeat here: the extension fields are
first-class, **validated** (an unknown methodology tag is an error, not a
free-text footgun), and rendered into the record in the ratified order.

Every field is optional except where a rule in ``sim/README.md`` makes it
mandatory:

- a ``characterization`` record **must** carry ``data_provenance``
  (README: "Data provenance (new, required)");
- an FFT record's window **must** be ``none`` (coherent sampling) or state
  why coherent sampling was not used;
- a ``transient-noise`` record **must** state seed and duration
  justification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

#: ``Result`` (pass/fail vs a ratified spec line) vs the characterization
#: variant's ``Measured value(s)`` + ``Data provenance``.
RECORD_KINDS: tuple[str, ...] = ("corner-matrix", "characterization")

#: sim/README.md § "Linearity methodology".
LINEARITY_METHODS: tuple[str, ...] = (
    "full-1024-code-ramp",
    "reduced-code-set-major-carry",
    "code-density",
    "behavioral-accelerated",
)

#: sim/README.md § "Noise methodology".
NOISE_METHODS: tuple[str, ...] = ("transient-noise", "ac-based", "both")

#: sim/README.md § "Monte Carlo convention" -> Scope.
MC_SCOPES: tuple[str, ...] = ("mismatch-only", "mismatch+process")

#: sim/README.md § "Characterization-record variant" -> Data provenance.
DATA_PROVENANCE_TAGS: tuple[str, ...] = (
    "model-card-monte-carlo",
    "foundry-documentation",
    "literature-assumption-with-derating",
    "simulated",
)


class EvidenceFormatError(ValueError):
    """A record would not conform to ``sim/README.md``."""


def _tagged(value: str) -> str:
    """The leading tag of a ``<tag> -- free text`` field."""
    return value.strip().split()[0] if value.strip() else ""


@dataclass
class Extensions:
    """ADC-specific extension fields for one evidence record."""

    record_kind: str = "corner-matrix"

    # -- Dynamic-test (FFT) metadata -------------------------------------
    fft_n: int | None = None
    fft_input_hz: float | None = None
    fft_bin: int | None = None
    fft_window: str = ""
    fft_fs_hz: float | None = None

    # -- Linearity methodology -------------------------------------------
    linearity_method: str = ""

    # -- Monte Carlo convention (extends the base statistical convention) --
    mc_seed: str = ""
    mc_scope: str = ""
    mc_sigma: str = ""

    # -- Noise methodology ------------------------------------------------
    noise_method: str = ""
    noise_seed: str = ""
    noise_duration_justification: str = ""

    # -- Characterization-record variant ----------------------------------
    data_provenance: str = ""

    #: Free-text notes carried verbatim into the record.
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #

    @property
    def is_characterization(self) -> bool:
        return self.record_kind == "characterization"

    @property
    def has_fft(self) -> bool:
        return any(
            v not in (None, "")
            for v in (self.fft_n, self.fft_input_hz, self.fft_bin, self.fft_window, self.fft_fs_hz)
        )

    @property
    def has_mc(self) -> bool:
        return any(v for v in (self.mc_seed, self.mc_scope, self.mc_sigma))

    def validate(self) -> None:
        """Raise :class:`EvidenceFormatError` if the record would not conform."""
        problems: list[str] = []

        if self.record_kind not in RECORD_KINDS:
            problems.append(
                f"record kind {self.record_kind!r} is not one of {', '.join(RECORD_KINDS)}"
            )

        if self.linearity_method and _tagged(self.linearity_method) not in LINEARITY_METHODS:
            problems.append(
                f"linearity methodology must start with one of {', '.join(LINEARITY_METHODS)}; "
                f"got {self.linearity_method!r}"
            )

        if self.noise_method:
            tag = _tagged(self.noise_method)
            if tag not in NOISE_METHODS:
                problems.append(
                    f"noise methodology must start with one of {', '.join(NOISE_METHODS)}; "
                    f"got {self.noise_method!r}"
                )
            if tag in ("transient-noise", "both"):
                if not self.noise_seed:
                    problems.append(
                        "a transient-noise record must state its seed "
                        "(sim/README.md § Noise methodology)"
                    )
                if not self.noise_duration_justification:
                    problems.append(
                        "a transient-noise record must justify its duration "
                        "(sim/README.md § Noise methodology)"
                    )

        if self.mc_scope and self.mc_scope not in MC_SCOPES:
            problems.append(
                f"Monte Carlo scope must be one of {', '.join(MC_SCOPES)}; got {self.mc_scope!r}"
            )
        if self.has_mc:
            missing = [
                label
                for label, value in (
                    ("seed handling", self.mc_seed),
                    ("scope", self.mc_scope),
                    ("sigma level", self.mc_sigma),
                )
                if not value
            ]
            if missing:
                problems.append(
                    "a Monte Carlo record must state seed handling, scope and sigma level; "
                    f"missing: {', '.join(missing)}"
                )

        if self.has_fft:
            missing = [
                label
                for label, value in (
                    ("N samples", self.fft_n),
                    ("input frequency", self.fft_input_hz),
                    ("coherent bin", self.fft_bin),
                    ("window", self.fft_window),
                    ("sampling rate", self.fft_fs_hz),
                )
                if value in (None, "")
            ]
            if missing:
                problems.append(
                    "an FFT-derived record must state N samples, input frequency, coherent "
                    f"bin, window and sampling rate; missing: {', '.join(missing)}"
                )
            elif self.fft_window.strip().lower() != "none" and len(self.fft_window.split()) < 2:
                problems.append(
                    "a windowed FFT record must say why coherent sampling was not used "
                    "(sim/README.md § Dynamic-test (FFT) metadata); "
                    f"got window={self.fft_window!r}"
                )

        if self.is_characterization and not self.data_provenance:
            problems.append(
                "a characterization record must state Data provenance "
                f"(one of {', '.join(DATA_PROVENANCE_TAGS)})"
            )
        if self.data_provenance and _tagged(self.data_provenance) not in DATA_PROVENANCE_TAGS:
            problems.append(
                f"data provenance must start with one of {', '.join(DATA_PROVENANCE_TAGS)}; "
                f"got {self.data_provenance!r}"
            )

        if problems:
            raise EvidenceFormatError(
                "record would not conform to sim/README.md:\n  - " + "\n  - ".join(problems)
            )

    def as_dict(self) -> dict:
        return asdict(self)

    # ------------------------------------------------------------------ #

    def render_statistical_sublines(self) -> list[str]:
        """Monte Carlo sub-bullets, which hang off ``Statistical convention``.

        ``sim/README.md``: the Monte Carlo convention "extends the base
        'Statistical convention' field", so these are nested under it rather
        than being a sibling bullet.
        """
        if not self.has_mc:
            return []
        return [
            f"  - **Seed handling**: {self.mc_seed}",
            f"  - **Scope**: {self.mc_scope}",
            f"  - **Sigma level**: {self.mc_sigma}",
        ]

    def render_lines(self) -> list[str]:
        """The extension fields, as record bullets in ``sim/README.md`` order.

        Ordered to sit between ``Statistical convention`` and
        ``Result`` / ``Measured value(s)``, matching the worked examples in
        ``sim/README.md``. Monte Carlo fields are *not* here -- see
        :meth:`render_statistical_sublines`.
        """
        lines: list[str] = []
        if self.has_fft:
            lines += [
                "- **Dynamic-test (FFT) metadata**:",
                f"  - N samples: {self.fft_n}",
                f"  - Input frequency / coherent bin: {self.fft_input_hz} Hz, bin {self.fft_bin}",
                f"  - Window: {self.fft_window}",
                f"  - Sampling rate: {self.fft_fs_hz} Hz",
            ]
        if self.linearity_method:
            lines.append(f"- **Linearity methodology**: `{_tagged(self.linearity_method)}`"
                         + _rest(self.linearity_method))
        if self.noise_method:
            lines.append(f"- **Noise methodology**: `{_tagged(self.noise_method)}`"
                         + _rest(self.noise_method))
            if self.noise_seed:
                lines.append(f"  - Seed: {self.noise_seed}")
            if self.noise_duration_justification:
                lines.append(f"  - Duration justification: {self.noise_duration_justification}")
        if self.data_provenance:
            lines.append(f"- **Data provenance**: `{_tagged(self.data_provenance)}`"
                         + _rest(self.data_provenance))
        for note in self.notes:
            lines.append(f"- **Note**: {note}")
        return lines


def _rest(value: str) -> str:
    remainder = value.strip().split(" ", 1)
    return f" — {remainder[1].strip()}" if len(remainder) > 1 and remainder[1].strip() else ""


#: Manifest (``tb.json``) key -> :class:`Extensions` attribute.
MANIFEST_KEYS: dict[str, str] = {
    "record_kind": "record_kind",
    "fft_n": "fft_n",
    "fft_input_hz": "fft_input_hz",
    "fft_bin": "fft_bin",
    "fft_window": "fft_window",
    "fft_fs_hz": "fft_fs_hz",
    "linearity_method": "linearity_method",
    "mc_seed": "mc_seed",
    "mc_scope": "mc_scope",
    "mc_sigma": "mc_sigma",
    "noise_method": "noise_method",
    "noise_seed": "noise_seed",
    "noise_duration_justification": "noise_duration_justification",
    "data_provenance": "data_provenance",
    "notes": "notes",
}


def from_manifest(block: dict | None) -> Extensions:
    """Build :class:`Extensions` from a ``tb.json`` ``evidence`` block."""
    block = dict(block or {})
    unknown = sorted(set(block) - set(MANIFEST_KEYS))
    if unknown:
        raise EvidenceFormatError(
            f"unknown key(s) in the manifest's 'evidence' block: {', '.join(unknown)}; "
            f"known: {', '.join(sorted(MANIFEST_KEYS))}"
        )
    kwargs = {MANIFEST_KEYS[key]: value for key, value in block.items()}
    if "notes" in kwargs and isinstance(kwargs["notes"], str):
        kwargs["notes"] = [kwargs["notes"]]
    return Extensions(**kwargs)
