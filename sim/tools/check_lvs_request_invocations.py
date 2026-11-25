#!/usr/bin/env python3
"""Keep every committed `klt lvs` invocation self-describing (issue #804):
both the invocation a request document's `_comment` tells a reader to run
and the invocation a `.ref.spice` header names must point at THAT request
document, not some other one.

The generators that write `*.lvs.json` request documents
(layout/adc-top/gen_adc_top.py, layout/adc-top/gen_comparator.py,
layout/adc-top/cells/gen_adc_cells.py, and
layout/adc-top/candidates/gen_acq_leg_candidate.py through the first one's
writers) each document the runnable invocation in a `_comment` line. Three
of them used to interpolate a hardcoded production path instead of deriving
it from the `path` they were actually writing, so every candidate-geometry
request document under layout/adc-top/candidates/acq-leg-*/ told a reader
to run the PRODUCTION request -- a copy-pasted re-run reported the
production LVS verdict while the candidate's own LVS never ran. The
provenance rule ("provenance travels with every number", CLAUDE.md) is
enforced here mechanically instead of by convention.

The same generators write the `.ref.spice` flat LVS reference headers
(* Flat LVS reference ... Runnable by hand: klt lvs <sibling> --format
json), which document the same invocation for hand re-runs. A header
naming a non-sibling request is the same regression, so every committed
`*.ref.spice` must document exactly one invocation and it must resolve to
its sibling `<stem>.lvs.json` in the same directory.

`klt lvs --format json` OUTPUT reports (layout/lvs/reports/,
layout/adc-top/candidates/*/reports/, layout/lvs/sar_ctrl/reports/) share
the *.lvs.json suffix but are told apart from request documents by a
report-only key (`schema_version`, `status`, `engine`): every committed
report carries one, no request document does, and shape keys like
`layout`/`reference` do NOT separate the two (all 191 committed reports
have them too). A *.lvs.json that is neither -- no `_comment` to document
an invocation and no report-only key to identify it as a report -- fails:
a writer that silently drops the `_comment` entirely is the same
regression as one that drops the line inside it.

Stdlib-only, no PDK / ngspice / klt, so it belongs on the headless CI path
(package.json `check:ci`) alongside check_append_only_records.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVOCATION_RE = re.compile(r"^\s*klt lvs (\S+\.lvs\.json) --format json\s*$")
# Header comment lines come in two spellings ("*   klt lvs ..." and
# "* Runnable by hand:  klt lvs ..."), so anchor the tail, not the indent.
HEADER_INVOCATION_RE = re.compile(r"^\*.*\bklt lvs (\S+\.lvs\.json) --format json\s*$")
# Report-only keys: present in every committed `klt lvs --format json`
# output report, present in no request document. NOT layout/reference --
# every committed report carries those shape keys too.
REPORT_KEYS = ("schema_version", "status", "engine")


def committed_files(repo: Path, pattern: str) -> list[str]:
    """Repo-relative paths of every committed file matching `pattern`,
    tracked files only (git ls-files reads the index), so a stale sibling
    worktree or an untracked scratch outdir cannot fail this check."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", pattern],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"error: git ls-files failed: {proc.stderr.strip()}")
    return [p for p in proc.stdout.split("\0") if p]


def is_report(doc: dict) -> bool:
    return any(key in doc for key in REPORT_KEYS)


def find_violations(repo: Path, rels: list[str]) -> list[str]:
    """Return one message per request document whose documented `klt lvs`
    invocation does not resolve to that same file."""
    violations: list[str] = []
    for rel in rels:
        try:
            doc = json.loads((repo / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            violations.append(f"{rel}: not readable JSON ({exc})")
            continue
        if not isinstance(doc, dict):
            violations.append(f"{rel}: not a JSON object")
            continue
        if "_comment" not in doc:
            if is_report(doc):
                continue  # a `klt lvs --format json` output report
            violations.append(
                f"{rel}: neither a request document (no _comment) nor a "
                "recognizable report (no schema_version/status/engine key)"
            )
            continue
        comment = doc["_comment"]
        if not (
            isinstance(comment, list)
            and all(isinstance(line, str) for line in comment)
        ):
            violations.append(f"{rel}: _comment is not a list of strings")
            continue
        documented = [m.group(1) for m in map(INVOCATION_RE.match, comment) if m]
        if not documented:
            violations.append(
                f'{rel}: request document documents no "klt lvs <path> '
                '--format json" invocation'
            )
            continue
        actual = os.path.normpath(os.path.join(str(repo), rel))
        for path in documented:
            if os.path.normpath(os.path.join(str(repo), path)) != actual:
                violations.append(
                    f"{rel}: documented invocation runs {path}, not this file"
                )
    return violations


def find_ref_spice_violations(repo: Path, rels: list[str]) -> list[str]:
    """Return one message per `.ref.spice` header whose documented `klt
    lvs` invocation does not resolve to that reference's sibling request
    document (`<dirname>/<stem>.lvs.json`)."""
    violations: list[str] = []
    for rel in rels:
        try:
            lines = (repo / rel).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            violations.append(f"{rel}: not readable ({exc})")
            continue
        documented = [m.group(1) for m in map(HEADER_INVOCATION_RE.match, lines) if m]
        stem = os.path.basename(rel)[: -len(".ref.spice")]
        sibling = os.path.normpath(os.path.join(os.path.dirname(rel), f"{stem}.lvs.json"))
        if not documented:
            violations.append(
                f'{rel}: header documents no "klt lvs <path> --format json" '
                "invocation"
            )
            continue
        for path in documented:
            if os.path.normpath(path) != sibling:
                violations.append(
                    f"{rel}: header invocation runs {path}, not its sibling "
                    f"request {sibling}"
                )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    rels = committed_files(args.repo, "*.lvs.json")
    ref_rels = committed_files(args.repo, "*.ref.spice")
    violations = find_violations(args.repo, rels)
    violations += find_ref_spice_violations(args.repo, ref_rels)
    if violations:
        print(
            f"FAIL: {len(violations)} committed klt lvs invocation(s) "
            "do not document their own request document:"
        )
        for v in violations:
            print(f"  {v}")
        print(
            "The documented invocation must resolve to the request document "
            "itself (issue #804): the generator derives it from the path it "
            "writes, via os.path.relpath(path, repo_root)."
        )
        return 1
    print(
        f"ok: {len(rels)} committed *.lvs.json and {len(ref_rels)} "
        "*.ref.spice checked; every documented klt lvs invocation names "
        "its own request document"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
