#!/usr/bin/env python3
"""Shared `klt yield` document-emission mechanics for the `yield-evidence*/`
bundles under `sim/`.

Four experiments each publish a `klt yield` sample set and its spec window as
a pair of committed JSON documents (`mc-samples.json` + `spec-limits.json`),
the layout `docs/cli/yield.md`'s own worked example uses:

  - `sim/mc-cdac-mismatch/yield-evidence/`      (DNL/INL at code 256 + gain error)
  - `sim/mc-cdac-mismatch/yield-evidence-177/`  (resized-C_u gain error)
  - `sim/mc-cdac-mismatch/yield-evidence-656/`  (worst-over-all-codes DNL/INL)
  - `sim/comparator-offset-mc/yield-evidence/`  (offset error + CMRR)

Each had its own copy of the same five steps -- read a column of samples, read
the nominal/negative-control summary JSON, compose a negative-control
description, emit `{"measurements": [...]}`, emit `{"target_ci_halfwidth":
..., "measurements": {...}}`. This module is that one copy. The per-claim
*data* (which record, which columns, which limits, which analytic
cross-check) stays in each bundle's own script, together with its module
docstring: those docstrings are the per-claim evidence trail, not
boilerplate.

**The emitted bytes are a contract.** These documents are derived views of
already-committed `runs/`/`corners/`/`records/` evidence -- regenerable, and
regenerated in place -- but the committed bytes are what downstream records
and reviewers cite. `sim/tests/test_yield_evidence.py` re-runs all four
callers into a temp directory and asserts byte-equality against the committed
artifacts, so a change here that would move any bundle's bytes fails the
suite. That is deliberate: if a bundle's bytes would change, the emitter is
wrong for that bundle -- fix the emitter, do not re-baseline the artifact.

Key insertion order in every dict below is therefore load-bearing (`json.dumps`
preserves it); do not reorder.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

#: 3-sigma two-sided normal yield -- the "3 sigma" pass criterion
#: `spec/cdac-sizing-memo.md` SS3.1-3.3 states, expressed as the
#: `target_yield` fraction `klt yield --limits` wants.
TARGET_YIELD_3SIGMA = 0.9973002039367398

#: Confidence-interval half-width `klt yield` is asked to reach, the same
#: value every bundle's `spec-limits.json` has always carried.
TARGET_CI_HALFWIDTH = 0.01

#: Default tail of the negative-control description. `yield-evidence-656`
#: stops at the filename instead; see `negative_control_description`.
PROVENANCE_SUFFIX = " for full provenance."


def read_column(path: Path, column: str) -> list[float]:
    """Every value of one column of a trials CSV, in row (draw) order."""
    with path.open(newline="") as f:
        return [float(row[column]) for row in csv.DictReader(f)]


def sha256(path: Path) -> str:
    """Hex SHA-256 of a file's bytes, for the input-provenance lines."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_pct(value: str | float) -> str:
    """Render a sigma_u percentage for the description.

    A `str` is used verbatim -- `yield-evidence/` states each row's nominal
    sigma_u as the literal the record cites rather than re-reading it from a
    summary JSON. A float is rendered to six decimals, the form the bundles
    that do read it from the summary have always emitted.
    """
    return value if isinstance(value, str) else f"{value:.6f}"


def negative_control_description(
    neg_summary: dict,
    record_id: str,
    *,
    basis: str,
    nominal_pct: str | float,
    suffix: str = PROVENANCE_SUFFIX,
) -> str:
    """The one negative-control sentence all CDAC-mismatch bundles emit.

    `basis` names what the forced sigma is 3x OF, in that bundle's own terms
    ("the as-built value", "the RESIZED design's calibrated value", ...), and
    `suffix` closes the provenance pointer. Both are per-claim wording that
    differs between the committed bundles, so they are caller data rather
    than baked in here -- unifying the prose would move committed evidence
    bytes, which is a separate, deliberate re-baselining decision.
    """
    return (
        f"CDAC unit-cap mismatch sigma forced to 3x {basis} "
        f"(sigma_u={neg_summary['sigma_u_pct']:.6f}% vs "
        f"{_render_pct(nominal_pct)}% nominal), "
        f"N={neg_summary['n_trials']}, seed={neg_summary['seed']} -- same "
        f"behavioral model (mc_cdac_mismatch.py) and methodology as the "
        f"nominal campaign, a real (re-runnable) simulation, not a "
        f"synthetic offset. See runs/{record_id}/summary_n2000_3xsigma.json"
        f"{suffix}"
    )


def negative_control(samples: list[float], description: str, errored: int = 0) -> dict:
    """A measurement's `negative_control` block."""
    return {
        "samples": samples,
        "errored": errored,
        "description": description,
    }


def analytic_cross_check(sigma: float, mean: float = 0.0,
                         kind: str = "mismatch_offset") -> dict:
    """A measurement's closed-form `analytic_cross_check` block."""
    return {
        "kind": kind,
        "sigma": sigma,
        "mean": mean,
    }


def measurement(
    name: str,
    unit: str,
    samples: list[float],
    *,
    errored: int = 0,
    negative_control: dict | None = None,
    source_corners: list[str] | None = None,
    analytic_cross_check: dict | None = None,
) -> dict:
    """One `mc-samples.json` measurement entry.

    The two block parameters deliberately share the names of the helpers that
    build them, so a call site reads as the JSON it emits; nothing in this
    function calls them.

    Optional blocks are omitted entirely when `None` -- a bundle that has no
    negative control (the comparator campaign reuses single-corner draws) must
    not emit an empty one. Key order matches the committed documents.
    """
    entry: dict = {
        "name": name,
        "unit": unit,
        "samples": samples,
        "errored": errored,
    }
    if negative_control is not None:
        entry["negative_control"] = negative_control
    if source_corners is not None:
        entry["source_corners"] = source_corners
    if analytic_cross_check is not None:
        entry["analytic_cross_check"] = analytic_cross_check
    return entry


def symmetric_limit(limit: float, target_yield: float = TARGET_YIELD_3SIGMA) -> dict:
    """A `spec-limits.json` entry for a two-sided +/-`limit` spec window."""
    return {
        "min": -limit,
        "max": limit,
        "target_yield": target_yield,
    }


def write_bundle(
    out_dir: Path,
    measurements: list[dict],
    limits: dict,
    inputs: list[Path],
    *,
    rel_to: Path,
    limit_source: str | None = None,
    target_ci_halfwidth: float = TARGET_CI_HALFWIDTH,
) -> None:
    """Emit both documents into `out_dir` and report input provenance.

    Writes `mc-samples.json` and `spec-limits.json`, then prints the SHA-256
    of every file in `inputs` (displayed relative to `rel_to`) -- the
    provenance CLAUDE.md asks to travel with every number, which previously
    only `yield-evidence-656` emitted.

    `limit_source` is emitted FIRST in `spec-limits.json` when given, matching
    the committed document that carries it.
    """
    samples_doc = {"measurements": measurements}

    limits_doc: dict = {}
    if limit_source is not None:
        limits_doc["limit_source"] = limit_source
    limits_doc["target_ci_halfwidth"] = target_ci_halfwidth
    limits_doc["measurements"] = limits

    samples_path = out_dir / "mc-samples.json"
    limits_path = out_dir / "spec-limits.json"
    samples_path.write_text(json.dumps(samples_doc, indent=2) + "\n")
    limits_path.write_text(json.dumps(limits_doc, indent=2) + "\n")

    print(f"wrote {samples_path}")
    print(f"wrote {limits_path}")
    for p in inputs:
        print(f"  input sha256 {sha256(p)}  {p.relative_to(rel_to)}")
