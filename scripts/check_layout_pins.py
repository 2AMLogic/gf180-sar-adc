#!/usr/bin/env python3
"""Layout evidence integrity: re-derive every pinned hash in the layout
manifests, and keep the newest verdict in every layout records/ family honest.

Two guards, one stdlib-only script (no `klt`, no PDK, no network), so it
belongs on the headless CI path (`check:ci`):

1. Hash pins. ``layout/lvs/cells/cells.json``, ``layout/drc/cells/cells.json``
   and ``layout/adc-top/parasitics/cells.json`` pin the sha256 of every
   artifact they cite next to its path. Nothing else on the PR path re-derived
   those pins (issue #898: eight stale `reference` pins on PR #897, CI green),
   because the checks that do catch them (`run_lvs.py --check`, the ERC/power
   `--verify` stages) need `klt` or a PDK and run nightly, not on PRs. This
   guard re-hashes every committed artifact each manifest cites and fails on
   any drift, so a manifest can no longer describe files that are not in the
   tree.

   The path sibling of a pin key varies by manifest, so the pairing is
   explicit rather than guessed:

       netlist_sha256 -> netlist        request_sha256 -> request
       gds_sha256     -> gds            sha256         -> gds | reference

   Every path is relative to the manifest's own directory (the parasitics
   manifest reaches its blocks with ``../adc_top.gds``; the DRC cells list
   reaches block layouts with ``../../adc-top/cells/...``). The walk visits
   every object in every manifest, and FAILS CLOSED: a pin key without a
   recognised sibling, a pin whose file is missing, or an unhashable pin is an
   error, never a silent skip -- a new manifest shape cannot add a pin this
   check does not understand and keep CI green.

2. Record verdicts. The newest record in every ``layout/**/records/`` family
   carries the family's latest word. A record whose ``Overall`` line says
   FAIL used to merge as readily as a PASS one, because nothing on the PR
   path read records' verdicts (the LVS runner's own ``--check`` needs
   `klt`; `check:records` enforces append-only-ness, not content). This
   guard fails when a family's newest record asserts ``Overall — FAIL``. An
   ``ADJUDICATED`` follow-up is itself the then-newest record, so the two
   halves of the rule ("newest must not be FAIL"; "a FAIL must be followed
   by an ADJUDICATED record") are the same assertion under a total order:
   re-run the flow or mint an adjudication -- records are append-only
   evidence and are never edited to satisfy this. A newest record without an
   ``Overall`` line (provenance notes; the parasitics family has only those)
   asserts no verdict and passes.

Exit codes: 0 ok; 1 at least one pin mismatch, missing file, unrecognised
pin/sibling, or a FAIL verdict; 2 a manifest is unreadable or not valid JSON,
or the repo root is unusable -- fail closed, never a silent pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

CHUNK = 1 << 20

MANIFESTS = (
    "layout/lvs/cells/cells.json",
    "layout/drc/cells/cells.json",
    "layout/adc-top/parasitics/cells.json",
)

#: Pin key -> path key, for the pairings that are the same everywhere.
FIXED_PAIRS = {
    "netlist_sha256": "netlist",
    "request_sha256": "request",
    "gds_sha256": "gds",
}
#: The bare ``sha256`` key pairs with whichever of these siblings the object
#: carries: the extracted/DRC cell layouts name ``gds``, the LVS cases name
#: the reference netlist the case is compared against.
BARE_SHA_SIBLINGS = ("gds", "reference")

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

RECORDS_DIR = "records"
#: ``- **Overall** — PASS (...)`` and friends; the em/en dash and a plain
#: hyphen are all accepted after the bold key, and the bullet is optional.
OVERALL_RE = re.compile(r"^\s*(?:[-*]\s+)?\*\*Overall\*\*\s*[—–-]+\s*([A-Za-z]+)\b")
FAIL_STATUS = "FAIL"

EXIT_OK, EXIT_FAILED, EXIT_ERROR = 0, 1, 2


def iter_pins(node, path=""):
    """Yield ``(json_path, parent_dict, pin_key)`` for every hash pin key
    anywhere in a manifest, however deeply nested."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            if key == "sha256" or key.endswith("_sha256"):
                yield child, node, key
            yield from iter_pins(value, child)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from iter_pins(item, f"{path}[{i}]")


class RepoError(Exception):
    """Unreadable manifest or unusable root: exit 2, fail closed."""


def _hash_file(path: Path, cache: dict[Path, str]) -> str:
    cached = cache.get(path)
    if cached is None:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while chunk := fh.read(CHUNK):
                h.update(chunk)
        cached = h.hexdigest()
        cache[path] = cached
    return cached


def manifest_problems(repo: Path, rel: str, cache: dict[Path, str]) -> list[str]:
    """Every bad pin in one manifest: unrecognised pairing, unresolvable or
    missing sibling path, malformed pin, or a pin that does not match the
    committed bytes."""
    path = repo / rel
    try:
        with path.open(encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        raise RepoError(f"{rel}: unreadable manifest: {exc}") from None
    manifest_dir = path.parent
    problems = []
    for json_path, parent, key in iter_pins(manifest):
        label = f"{rel}: {json_path}"
        if key == "sha256":
            sibling = next((s for s in BARE_SHA_SIBLINGS if s in parent), None)
            if sibling is None:
                problems.append(
                    f"{label}: bare 'sha256' pin has no recognised sibling path "
                    f"(expected one of: {', '.join(BARE_SHA_SIBLINGS)})")
                continue
        else:
            sibling = FIXED_PAIRS.get(key)
            if sibling is None:
                problems.append(
                    f"{label}: unrecognised pin key (no known path sibling); "
                    "extend the pairing map in this script rather than letting "
                    "the pin skip verification")
                continue
        target = parent.get(sibling)
        usable = (isinstance(target, str) and target
                  and not target.startswith("/")
                  and "\\" not in target and "\0" not in target)
        if not usable:
            problems.append(f"{label}: sibling '{sibling}' is not a usable "
                            "manifest-relative path")
            continue
        pin = parent[key]
        if not isinstance(pin, str) or not SHA256_RE.match(pin):
            problems.append(f"{label}: pin is not 64 lowercase hex digits")
            continue
        artifact = (manifest_dir / target).resolve()
        if not artifact.is_relative_to(repo.resolve()):
            problems.append(f"{label}: '{target}' resolves outside the repository")
            continue
        if not artifact.is_file():
            problems.append(f"{label}: pinned file '{target}' is missing from the tree")
            continue
        actual = _hash_file(artifact, cache)
        if actual != pin:
            problems.append(
                f"{label}: pinned sha256 {pin} != actual {actual} "
                f"for '{target}' (re-run the flow that mints this manifest "
                "with its --regen, or fix the pin)")
    return problems


def record_problems(repo: Path) -> tuple[list[str], int, int]:
    """Newest record per ``layout/**/records/`` family must not assert
    ``Overall — FAIL``. Returns (problems, checked, verdict-less)."""
    problems: list[str] = []
    checked = skipped = 0
    layout = repo / "layout"
    families = sorted(layout.rglob(RECORDS_DIR)) if layout.is_dir() else []
    for family in families:
        if not family.is_dir():
            continue
        records = sorted(p for p in family.glob("*.md") if p.is_file())
        if not records:
            continue
        newest = records[-1]
        status = None
        try:
            text = newest.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise RepoError(f"{newest}: unreadable record: {exc}") from None
        for line in text.splitlines():
            m = OVERALL_RE.match(line)
            if m is not None:
                status = m.group(1).upper()
                break
        rel = newest.relative_to(repo)
        if status is None:
            skipped += 1
            continue
        checked += 1
        if status == FAIL_STATUS:
            problems.append(
                f"{rel}: the family's newest record asserts 'Overall — FAIL' "
                "(no later record supersedes it). Re-run the flow to mint a "
                "passing record, or add an ADJUDICATED record after it -- "
                "records are append-only and are never edited in place")
    return problems, checked, skipped


def check(repo: Path) -> int:
    cache: dict[Path, str] = {}
    errors: list[str] = []
    for rel in MANIFESTS:
        errors += manifest_problems(repo, rel, cache)
    pin_count = 0
    for rel in MANIFESTS:
        with (repo / rel).open(encoding="utf-8") as fh:
            pin_count += sum(1 for _ in iter_pins(json.load(fh)))
    v_errors, verdicts, verdict_less = record_problems(repo)
    errors += v_errors
    if errors:
        print(f"FAIL: {len(errors)} layout-evidence problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return EXIT_FAILED
    print(f"OK: {pin_count} hash pin(s) across {len(MANIFESTS)} manifest(s) "
          "re-derived from the committed bytes; newest record per "
          f"layout/**/records/ family: {verdicts} verdict(s) checked, "
          f"{verdict_less} without an Overall line (no verdict asserted)")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]),
                    help="repository root (default: the checkout this script lives in)")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"ERROR: {repo} is not a directory", file=sys.stderr)
        return EXIT_ERROR
    try:
        return check(repo)
    except RepoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
