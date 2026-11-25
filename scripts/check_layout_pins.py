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
   guard fails when a family's newest record asserts ``Overall — FAIL``, and
   it also recognises the sar_ctrl LVS sub-family's own schema,
   ``**Verdict (committed GDS vs golden)**: **`match`**`` -- only `match`
   is a pass there, so a sub-family recording `no match` fails too
   (issue #902: that verdict used to be invisible and the family merged
   green). An ``ADJUDICATED`` follow-up is itself the then-newest record, so
   the two halves of the rule ("newest must not be FAIL"; "a FAIL must be
   followed by an ADJUDICATED record") are the same assertion under a total
   order: re-run the flow or mint an adjudication -- records are
   append-only evidence and are never edited to satisfy this. A newest
   record without a recognised verdict line (provenance notes) asserts no
   verdict and passes.

   "Newest" is the lexically-last ``*.md`` whose *name is declared*
   (issue #902: ``README.md`` sorts after every ``2026…`` name, so an
   undeclared file used to silently become the newest record and stop the
   whole family being checked). Declared names are the timestamped
   ``YYYYMMDD-HHMMSS-<sha>.md`` convention (lexical order is then
   chronological); the pre-convention ``YYYYMMDD-<slug>.md`` records
   parasitics' earliest evidence used, declared by exact file name in
   ``DECLARED_SLUG_RECORDS`` -- declaring the shape instead would also
   admit new hand-written slug names, which sort after a canonical name
   of the same date and so can become "newest" ahead of it, hiding that
   record's verdict (issue #905); and ``DECLARED_NONRECORD_NAMES``, an
   explicit exemption list for a non-record
   file a family genuinely needs (never newest, never verdict-checked). Any
   other ``*.md`` in a records dir is an error naming the file -- declare it
   in this script rather than letting it drift in. The OK report prints
   every family's newest filename and parsed status, so a family dropping
   out of verdict checking is visible in CI output instead of only in a
   count.

Exit codes: 0 ok; 1 at least one pin mismatch, missing file, unrecognised
pin/sibling, an undeclared records-dir file, or a failing verdict; 2 a
manifest or record is unreadable or not valid JSON, or the repo root is
unusable -- fail closed, never a silent pass.
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
#: The canonical record name is ``YYYYMMDD-HHMMSS-<sha>.md``; lexical order
#: is then chronological. parasitics' earliest evidence predates that
#: convention and uses ``YYYYMMDD-<slug>.md``; those records are declared
#: by exact file name (see DECLARED_SLUG_RECORDS), only in the family whose
#: history used them -- declaring the shape instead would also admit any
#: new hand-written slug name, and within one date a slug name sorts after
#: a canonical name, so a slug file dated the newest canonical record's
#: date or later would become "newest" and stop that record's verdict
#: being asserted (issue #905; issue #902: an undeclared ``README.md``
#: sorts after every ``2026…`` name and used to silently become the newest
#: record, stopping the family being verdict-checked).
RECORD_NAME_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]+\.md$")
#: Exact file names of the pre-convention ``YYYYMMDD-<slug>.md`` records,
#: keyed by the only family whose history used that shape. Declared by file
#: name rather than by shape: a shape regex would also admit any new
#: hand-written slug name, which lexical order puts *after* a canonical
#: record of the same date -- a slug file dated the newest canonical
#: record's date or later would become "newest" and stop that record's
#: verdict being asserted (issue #905). Any other ``*.md`` in such a
#: family is an undeclared-file error.
DECLARED_SLUG_RECORDS: dict[str, frozenset[str]] = {
    "layout/adc-top/parasitics/records": frozenset({
        "20260805-extracted-core-mc.md",
        "20260805-extracted-core-smoke.md",
        "20260805-layout-pin-dc.md",
        "20260805-remediation-dc.md",
        "20260806-adc-block-comparator-input-float.md",
        "20260806-adc-block-comparator-smoke.md",
        "20260806-adc-block-resistor-markers-pass.md",
        "20260806-parasitic-topology-inpath.md",
        "20260806-parasitic-topology.md",
        "20260806-power-cmp-anomaly.md",
        "20260806-power-cmp-metastability.md",
    }),
}
#: Exact file names declared as non-records: allowed in a records dir but
#: exempt from the listing (never newest, never verdict-checked). Empty by
#: default; a README or scratch notes must be declared here explicitly or
#: the check fails closed.
DECLARED_NONRECORD_NAMES: frozenset[str] = frozenset()
#: sar_ctrl's LVS sub-family records its verdict in its own schema
#: (``- **Verdict (committed GDS vs golden)**: **`match`**``); only `match`
#: is a pass -- `no match`/`mismatch` fail like an Overall FAIL.
VERDICT_GDS_RE = re.compile(
    r"^\s*(?:[-*]\s+)?\*\*Verdict \(committed GDS vs golden\)\*\*\s*:\s*"
    r"\*\*`([^`]+)`\*\*")
MATCH_STATUS = "match"

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


def _declared_record_name(family_rel: Path, name: str) -> bool:
    """True when *name* is a declared record name in this family: the
    timestamped convention anywhere, or one of the exact pre-convention
    file names the family declared (see DECLARED_SLUG_RECORDS)."""
    if RECORD_NAME_RE.match(name):
        return True
    return name in DECLARED_SLUG_RECORDS.get(str(family_rel), frozenset())


def _parse_verdict(text: str) -> tuple[str, bool, bool] | None:
    """A record's asserted verdict as ``(word, asserts_fail, is_overall)``,
    or None when it asserts no verdict. First recognised line wins. The
    canonical ``**Overall**`` schema fails only on FAIL; sar_ctrl's
    ``**Verdict (committed GDS vs golden)**`` schema passes only on
    `match`."""
    for line in text.splitlines():
        m = OVERALL_RE.match(line)
        if m is not None:
            word = m.group(1).upper()
            return word, word == FAIL_STATUS, True
        m = VERDICT_GDS_RE.match(line)
        if m is not None:
            word = m.group(1).strip().lower()
            return word, word != MATCH_STATUS, False
    return None


def record_problems(repo: Path) -> tuple[list[str],
                                         list[tuple[str, str, str | None]]]:
    """Every records-family violation, plus a per-family report line for the
    OK output: ``(family, newest record name, status or None)`` for each
    family with at least one declared record. The newest record must not
    assert a failing verdict (``Overall — FAIL``; sar_ctrl's GDS verdict must
    be `match`), and every ``*.md`` in a records dir must be a declared
    record name or a declared non-record -- fail closed, never a silent
    "this family stopped being checked"."""
    problems: list[str] = []
    report: list[tuple[str, str, str | None]] = []
    layout = repo / "layout"
    families = sorted(layout.rglob(RECORDS_DIR)) if layout.is_dir() else []
    for family in families:
        if not family.is_dir():
            continue
        rel = family.relative_to(repo)
        records = []
        for p in sorted(family.glob("*.md")):
            if not p.is_file():
                continue
            if p.name in DECLARED_NONRECORD_NAMES:
                continue
            if not _declared_record_name(rel, p.name):
                problems.append(
                    f"{rel / p.name}: not a declared record name (timestamped "
                    "YYYYMMDD-HHMMSS-<sha>.md; parasitics' pre-convention "
                    "records by exact name in DECLARED_SLUG_RECORDS; a "
                    "non-record must be in DECLARED_NONRECORD_NAMES) -- "
                    "declare it in this script rather than letting it "
                    "silently become the family's newest record")
                continue
            records.append(p)
        if not records:
            continue
        newest = records[-1]
        try:
            text = newest.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise RepoError(f"{newest}: unreadable record: {exc}") from None
        verdict = _parse_verdict(text)
        status = None if verdict is None else verdict[0]
        report.append((str(rel), newest.name, status))
        if verdict is None:
            continue
        word, fails, is_overall = verdict
        if not fails:
            continue
        if is_overall:
            problems.append(
                f"{newest.relative_to(repo)}: the family's newest record "
                "asserts 'Overall — FAIL' (no later record supersedes it). "
                "Re-run the flow to mint a passing record, or add an "
                "ADJUDICATED record after it -- records are append-only and "
                "are never edited in place")
        else:
            problems.append(
                f"{newest.relative_to(repo)}: the family's newest record "
                "asserts 'Verdict (committed GDS vs golden) — "
                f"{word}' (only 'match' is a pass). Re-run the LVS flow to "
                "mint a match record -- records are append-only and are "
                "never edited in place")
    return problems, report


def check(repo: Path) -> int:
    cache: dict[Path, str] = {}
    errors: list[str] = []
    for rel in MANIFESTS:
        errors += manifest_problems(repo, rel, cache)
    pin_count = 0
    for rel in MANIFESTS:
        with (repo / rel).open(encoding="utf-8") as fh:
            pin_count += sum(1 for _ in iter_pins(json.load(fh)))
    v_errors, families_report = record_problems(repo)
    errors += v_errors
    if errors:
        print(f"FAIL: {len(errors)} layout-evidence problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return EXIT_FAILED
    verdicts = sum(1 for _, _, status in families_report if status is not None)
    verdict_less = len(families_report) - verdicts
    print(f"OK: {pin_count} hash pin(s) across {len(MANIFESTS)} manifest(s) "
          "re-derived from the committed bytes; newest record per "
          f"layout/**/records/ family ({len(families_report)} families, "
          f"{verdicts} verdict(s) checked, {verdict_less} asserting none):")
    for family, newest, status in families_report:
        print(f"  {family}: newest={newest} status={status or 'none'}")
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
