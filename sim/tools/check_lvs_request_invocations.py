#!/usr/bin/env python3
"""Keep every committed `klt lvs` request document self-describing (issue
#804): the `_comment` invocation it tells a reader to run must name THAT
file, not some other request document.

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

`klt lvs --format json` OUTPUT reports (layout/lvs/reports/,
layout/adc-top/candidates/*/reports/, layout/lvs/sar_ctrl/reports/) share
the *.lvs.json suffix but carry no `_comment`; they are skipped. A request
document that documents no invocation at all fails too -- a writer that
silently drops the line is the same regression.

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


def committed_lvs_json(repo: Path) -> list[str]:
    """Repo-relative paths of every committed `*.lvs.json`, tracked files
    only (git ls-files reads the index), so a stale sibling worktree or an
    untracked scratch outdir cannot fail this check."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", "*.lvs.json"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"error: git ls-files failed: {proc.stderr.strip()}")
    return [p for p in proc.stdout.split("\0") if p]


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
        if not isinstance(doc, dict) or "_comment" not in doc:
            continue  # a `klt lvs --format json` output report, not a request
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    rels = committed_lvs_json(args.repo)
    violations = find_violations(args.repo, rels)
    if violations:
        print(
            f"FAIL: {len(violations)} committed *.lvs.json request document(s) "
            "do not document their own invocation:"
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
        f"ok: {len(rels)} committed *.lvs.json checked; every documented "
        "klt lvs invocation names its own file"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
