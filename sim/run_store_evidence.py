#!/usr/bin/env python3
"""Store a staged campaign's evidence; commit only its manifest and summary.

Issue #636. The corner runner (``sim/run_corners.py``) stores its own records.
Everything else that produces new evidence -- a ``klt sim`` campaign, a PEX
batch, a layout-side run, a derived report set -- writes its outputs into a
git-ignored scratch
directory (``sim/.work/...`` or anywhere outside the repo) and then runs::

    python3 sim/run_store_evidence.py <bench> <run-id> <staged-dir> --summary <summary.md>

Every regular file under ``<staged-dir>`` is put through ``klt artifact put``
under the logical name ``<home>/<kind>/<run-id>/<relative path>``, where
``<home>`` is ``sim/<bench>`` or the directory given by ``--under`` (e.g.
``layout/adc-top/economy`` for a layout-side run; ``--kind`` is ``campaigns``
by default). The repo then gains exactly two files:
``manifests/artifacts/<bench>-<run-id>.manifest.json`` and the summary,
committed as ``<home>/<kind>/<run-id>.md`` with a "Stored evidence" table
appended. Nothing under ``<staged-dir>`` is copied into the tree.

Fail closed: no broker (``$KLT_ARTIFACT_BROKER``), no ``klt`` with the
``artifact`` verb, an unreachable or refusing broker, or any failed put exits
10 with nothing committed; the staged files are left where they are.

Exit codes: 0 stored; 1 usage / bad staged directory; 10 not stored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "sim"))

from harness import evidence_store as store_mod  # noqa: E402

KINDS = ("campaigns", "records", "corners", "reports")
HOME_ROOTS = ("sim", "layout", "signoff")


def _staged_dir_problem(staged: Path, bench: str) -> str | None:
    if not staged.is_dir():
        return f"{staged} is not a directory"
    try:
        rel = staged.relative_to(REPO_ROOT)
    except ValueError:
        return None  # outside the repo: fine
    if rel.parts[:2] == ("sim", ".work"):
        return None  # git-ignored scratch
    return ("the staged directory is inside the repo but not under sim/.work/; "
            "stage evidence in git-ignored scratch so its bytes are never committed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bench", help="bench directory name under sim/ (names the manifest)")
    ap.add_argument("run_id", help="campaign/run identity, e.g. 20261022-abc1234")
    ap.add_argument("staged", type=Path, help="directory holding the evidence bytes")
    ap.add_argument("--summary", type=Path, required=True,
                    help="Markdown summary to commit (results, method, reproduce)")
    ap.add_argument("--kind", choices=KINDS, default="campaigns",
                    help="protected evidence directory the run belongs to")
    ap.add_argument("--under", metavar="DIR",
                    help="repo-relative directory the run's name and summary live "
                         "under instead of sim/<bench> (sim/, layout/ or signoff/)")
    args = ap.parse_args(argv)

    try:
        store_mod.manifest_path(REPO_ROOT, args.bench, args.run_id)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    home = Path(args.under) if args.under else Path("sim") / args.bench
    if home.is_absolute() or ".." in home.parts or home.parts[0] not in HOME_ROOTS \
            or len(home.parts) < 2:
        print(f"ERROR: --under must be a repo-relative directory below sim/, "
              f"layout/ or signoff/, not {home}", file=sys.stderr)
        return 1
    if not (REPO_ROOT / home).is_dir():
        print(f"ERROR: no directory {home}", file=sys.stderr)
        return 1
    staged = args.staged.resolve()
    problem = _staged_dir_problem(staged, args.bench)
    if problem:
        print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    try:
        summary_text = args.summary.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read summary: {exc}", file=sys.stderr)
        return 1

    prefix = f"{home.as_posix()}/{args.kind}/{args.run_id}"
    summary_path = REPO_ROOT / home / args.kind / f"{args.run_id}.md"
    try:
        store_mod.preflight(REPO_ROOT)
        files = store_mod.stage_files(staged, prefix, exclude=[args.summary])
        manifest = store_mod.store_files(
            files, repo_root=REPO_ROOT, bench=args.bench, rid=args.run_id,
            summary_text=summary_text, summary_path=summary_path)
    except store_mod.StoreError as exc:
        print(f"EVIDENCE NOT STORED -- nothing committed (fail closed): {exc}",
              file=sys.stderr)
        return 10
    print(f"stored {len(files)} file(s) from {args.staged}")
    print(f"  manifest: {manifest.relative_to(REPO_ROOT)}")
    print(f"  summary:  {summary_path.relative_to(REPO_ROOT)}")
    print("commit both; the staged directory can be deleted once "
          f"`python3 scripts/check_artifact_manifests.py verify {manifest.relative_to(REPO_ROOT)}` "
          "passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
