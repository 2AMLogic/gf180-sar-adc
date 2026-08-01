#!/usr/bin/env python3
"""Run the gf180mcu DRC deck over this repo's proof cells and mint an
append-only evidence record.

This is the reproducible invocation of `klt drc` for this repository. The
underlying command is deliberately unremarkable --

    klt drc <file> --deck gf180mcu --format json

-- and you can always run that by hand. What this script adds is the part
that makes a run *evidence* rather than a screenful of output:

  * it runs every proof cell in `cells/cells.json`, both the positive
    control (seeded violations) and the negative control (illegal geometry
    on layers the deck does not cover);
  * it **asserts** each cell's reported `rule_counts` against the expected
    mapping in that manifest, so a run that silently stops catching the
    seeded violations fails instead of looking green;
  * it verifies the committed GDS hashes, so the report provably belongs to
    the committed geometry;
  * it stamps the toolchain (klt version and path, klayout package version,
    interpreter, platform) and the repo's git sha into the record, because a
    DRC report means nothing without the deck version that produced it --
    the deck is upstream-owned and grows;
  * it writes into a fresh `<record-id>` directory and refuses to overwrite
    an existing one, per this repo's append-only evidence rule.

Usage
-----
    python3 layout/drc/run_drc.py            # run and mint a new record
    python3 layout/drc/run_drc.py --check    # run, assert, write nothing
    python3 layout/drc/run_drc.py --regen    # regenerate the GDS first

Exit codes
----------
    0  every cell matched its expectation
    1  tooling problem (klt missing, klayout missing, bad manifest, ...)
    2  at least one cell's report did not match its expectation, or a
       committed GDS hash did not match

Note that exit 0 does NOT mean "no violations": the positive-control cell is
*expected* to report violations. It means "the deck reported exactly what it
was supposed to report". `klt drc`'s own exit code (0 clean / 3 violations)
is recorded per cell but is not this script's exit code.

Requirements
------------
`klt` (2AMLogic/klayout-tools) on PATH, and -- only for `--regen` -- an
interpreter with the pip `klayout` package. Both are headless; neither the
KLayout GUI application nor the gf180mcu PDK install is needed. See
../README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS_DIR = os.path.join(HERE, "cells")
MANIFEST = os.path.join(CELLS_DIR, "cells.json")
REPORTS_DIR = os.path.join(HERE, "reports")
RECORDS_DIR = os.path.join(HERE, "records")
REPO_ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))

EXIT_OK = 0
EXIT_TOOLING = 1
EXIT_MISMATCH = 2


class ToolingError(Exception):
    """Something about the environment, not the layout, is wrong."""


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #


def find_klt() -> str:
    klt = shutil.which("klt")
    if klt is None:
        raise ToolingError(
            "`klt` not found on PATH. Install klayout-tools "
            "(https://github.com/2AMLogic/klayout-tools), e.g.\n"
            "    uv tool install git+https://github.com/2AMLogic/klayout-tools"
        )
    return klt


def find_klayout_python() -> str:
    """Return an interpreter that can `import klayout.db`.

    Tries this interpreter first, then the one `klt` itself runs under --
    klayout-tools depends on the pip `klayout` package, so its environment
    always has it, and reusing it means the GDS is regenerated against the
    same KLayout build that will then check it.
    """
    candidates = [sys.executable]

    klt = shutil.which("klt")
    if klt is not None:
        try:
            with open(os.path.realpath(klt), "rb") as fh:
                first = fh.readline().decode("utf-8", "replace").strip()
            if first.startswith("#!"):
                candidates.append(first[2:].strip().split()[0])
        except OSError:
            pass

    for candidate in candidates:
        if not candidate:
            continue
        probe = subprocess.run(
            [candidate, "-c", "import klayout.db"],
            capture_output=True,
        )
        if probe.returncode == 0:
            return candidate

    raise ToolingError(
        "no interpreter with the pip `klayout` package found "
        f"(tried: {', '.join(c for c in candidates if c)}). "
        "Install it with `pip install klayout`, or drop --regen and use the "
        "committed GDS."
    )


def klayout_version(python: str) -> str:
    probe = subprocess.run(
        [python, "-c", "import klayout; print(klayout.__version__)"],
        capture_output=True,
        text=True,
    )
    return probe.stdout.strip() if probe.returncode == 0 else "unknown"


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", REPO_ROOT, *args], capture_output=True, text=True
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def load_manifest() -> dict:
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def regenerate(manifest: dict, python: str) -> None:
    for cell in manifest["cells"]:
        script = os.path.join(CELLS_DIR, cell["generator"])
        proc = subprocess.run([python, script], capture_output=True, text=True)
        if proc.returncode != 0:
            raise ToolingError(
                f"{cell['generator']} failed:\n{proc.stdout}{proc.stderr}"
            )
        print(f"  regenerated {cell['gds']}")


def run_cell(klt: str, gds_path: str, deck: str) -> tuple[dict, str, int]:
    """Run `klt drc` twice: JSON (the contract) and text (a courtesy view)."""
    json_proc = subprocess.run(
        [klt, "drc", gds_path, "--deck", deck, "--format", "json"],
        capture_output=True,
        text=True,
    )
    # klt's documented exit codes for `drc`: 0 clean, 3 violations found,
    # 1 an actual error. Only the last one means the tool could not answer.
    if json_proc.returncode not in (0, 3):
        raise ToolingError(
            f"klt drc failed on {gds_path} (exit {json_proc.returncode}):\n"
            f"{json_proc.stderr}"
        )
    try:
        report = json.loads(json_proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(f"klt drc emitted non-JSON for {gds_path}: {exc}") from exc

    text_proc = subprocess.run(
        [klt, "drc", gds_path, "--deck", deck, "--format", "text"],
        capture_output=True,
        text=True,
    )
    return report, text_proc.stdout, json_proc.returncode


def check_cell(cell: dict, report: dict) -> list[str]:
    """Return a list of failure strings; empty means the cell matched."""
    failures = []

    expected_counts = cell["expect"]
    actual_counts = report.get("rule_counts", {})
    if actual_counts != expected_counts:
        failures.append(
            f"rule_counts mismatch: expected {expected_counts}, got {actual_counts}"
        )

    expected_status = cell["expect_status"]
    if report.get("status") != expected_status:
        failures.append(
            f"status mismatch: expected {expected_status!r}, "
            f"got {report.get('status')!r}"
        )

    expected_total = sum(expected_counts.values())
    if report.get("violation_count") != expected_total:
        failures.append(
            f"violation_count mismatch: expected {expected_total}, "
            f"got {report.get('violation_count')}"
        )

    # The deck this bring-up pins authors its thresholds in nanometres and
    # (in that release) does not rescale them by the stream's dbu, so a dbu
    # drift would silently redefine every threshold.
    if report.get("dbu_um") != 0.001:
        failures.append(f"unexpected dbu_um {report.get('dbu_um')} (want 0.001)")

    return failures


def record_id() -> str:
    sha = git("rev-parse", "--short", "HEAD") or "nogit"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{sha}"


def write_record(
    rec_id: str,
    manifest: dict,
    results: list[dict],
    toolchain: dict,
    overall_ok: bool,
) -> str:
    report_dir = os.path.join(REPORTS_DIR, rec_id)
    record_path = os.path.join(RECORDS_DIR, f"{rec_id}.md")
    if os.path.exists(report_dir) or os.path.exists(record_path):
        raise ToolingError(
            f"record {rec_id} already exists -- refusing to overwrite "
            "(layout/ evidence is append-only). Wait a second and re-run."
        )
    os.makedirs(report_dir)
    os.makedirs(RECORDS_DIR, exist_ok=True)

    for result in results:
        base = os.path.join(report_dir, result["name"])
        with open(f"{base}.drc.json", "w", encoding="utf-8") as fh:
            json.dump(result["report"], fh, indent=2)
            fh.write("\n")
        with open(f"{base}.drc.txt", "w", encoding="utf-8") as fh:
            fh.write(result["text"])

    with open(os.path.join(report_dir, "toolchain.json"), "w", encoding="utf-8") as fh:
        json.dump(toolchain, fh, indent=2)
        fh.write("\n")

    lines = [
        f"# DRC record {rec_id}",
        "",
        "Append-only evidence record for the gf180mcu DRC flow "
        "(`layout/drc/`). Generated by `layout/drc/run_drc.py`; never edited "
        "in place -- a re-run mints a new record.",
        "",
        f"- **Record ID** — `{rec_id}`",
        "- **Claim** — the `klt drc` gf180mcu flow runs headless in this repo "
        "and reports exactly the violations its proof cells seed (and nothing "
        "on the layers it does not cover).",
        "- **Geometry provenance** — synthetic proof cells built by the "
        "committed generators under `layout/drc/cells/`, via the `klayout.db` "
        "API. Not extracted from, and not representative of, this block's "
        "real layout.",
        f"- **Deck** — `{manifest['deck']}` (upstream-owned curated subset; "
        "see the deck-coverage note in `layout/README.md`)",
        "- **Overall** — "
        + (
            "PASS (every cell's report matched its expected `rule_counts`)"
            if overall_ok
            else "FAIL (at least one cell's report did not match its expectation)"
        ),
        "",
        "## Toolchain",
        "",
        "| Component | Value |",
        "|---|---|",
    ]
    for key, value in toolchain.items():
        lines.append(f"| `{key}` | `{value}` |")

    lines += [
        "",
        "## Result",
        "",
        "| Cell | Role | Expected `rule_counts` | Reported `rule_counts` | "
        "`klt drc` exit | Match |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        cell = result["cell"]
        lines.append(
            "| `{name}` | {role} | `{exp}` | `{act}` | {code} | {ok} |".format(
                name=result["name"],
                role=cell["role"],
                exp=json.dumps(cell["expect"]),
                act=json.dumps(result["report"].get("rule_counts", {})),
                code=result["exit_code"],
                ok="yes" if not result["failures"] else "**NO**",
            )
        )

    lines += [
        "",
        "`klt drc` exit codes: `0` clean, `3` violations found. The positive "
        "control is *supposed* to exit 3 — a `0` there would mean the deck "
        "stopped catching the seeded violations.",
        "",
        "## Artifacts",
        "",
        "| Cell | GDS | sha256 | JSON report | text report |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        cell = result["cell"]
        lines.append(
            "| `{name}` | `cells/{gds}` | `{sha}` | "
            "`reports/{rid}/{name}.drc.json` | `reports/{rid}/{name}.drc.txt` |".format(
                name=result["name"],
                gds=cell["gds"],
                sha=result["sha256"],
                rid=rec_id,
            )
        )

    failed = [r for r in results if r["failures"]]
    if failed:
        lines += ["", "## Failures", ""]
        for result in failed:
            for failure in result["failures"]:
                lines.append(f"- `{result['name']}`: {failure}")

    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 layout/drc/run_drc.py --check",
        "```",
        "",
        "`--check` runs the same assertions without minting a record. The "
        "JSON report is the stable contract; the `.txt` capture beside it is "
        "a courtesy view, not the source of truth.",
        "",
        f"- **Timestamp** — {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "- **Author** — Loom Builder agent (issue #15)",
        "",
    ]

    with open(record_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return record_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the cells and assert expectations, but write no record",
    )
    parser.add_argument(
        "--regen",
        action="store_true",
        help="regenerate the proof-cell GDS from its generators first "
        "(needs the pip `klayout` package)",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest()
        klt = find_klt()
        klt_version = subprocess.run(
            [klt, "--version"], capture_output=True, text=True
        ).stdout.strip()

        if args.regen:
            print("regenerating proof cells:")
            regenerate(manifest, find_klayout_python())

        klayout_py = None
        try:
            klayout_py = find_klayout_python()
        except ToolingError:
            pass  # only needed for --regen; recorded as unknown otherwise

        toolchain = {
            "klt_version": klt_version or "unknown",
            "klt_path": os.path.realpath(klt),
            "klayout_package": (
                klayout_version(klayout_py) if klayout_py else "not installed"
            ),
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "repo_git_sha": git("rev-parse", "HEAD") or "unknown",
            "repo_dirty": bool(git("status", "--porcelain")),
        }

        results = []
        overall_ok = True
        deck = manifest["deck"]

        print(f"deck: {deck}   klt: {toolchain['klt_version']}")
        for cell in manifest["cells"]:
            gds_path = os.path.join(CELLS_DIR, cell["gds"])
            if not os.path.exists(gds_path):
                raise ToolingError(
                    f"{gds_path} missing -- run with --regen to build it"
                )

            digest = sha256(gds_path)
            report, text, exit_code = run_cell(klt, gds_path, deck)
            failures = check_cell(cell, report)
            if digest != cell["sha256"]:
                failures.append(
                    f"GDS sha256 mismatch: manifest says {cell['sha256']}, "
                    f"file is {digest}"
                )
            if failures:
                overall_ok = False

            results.append(
                {
                    "name": cell["name"],
                    "cell": cell,
                    "report": report,
                    "text": text,
                    "exit_code": exit_code,
                    "sha256": digest,
                    "failures": failures,
                }
            )

            status = "ok" if not failures else "FAIL"
            print(
                f"  {cell['name']:<24} {report['status']:<10} "
                f"{json.dumps(report.get('rule_counts', {})):<40} [{status}]"
            )
            for failure in failures:
                print(f"      - {failure}")

        if args.check:
            print("--check: no record written")
        else:
            rec_id = record_id()
            path = write_record(rec_id, manifest, results, toolchain, overall_ok)
            print(f"wrote {os.path.relpath(path, REPO_ROOT)}")

        return EXIT_OK if overall_ok else EXIT_MISMATCH

    except ToolingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_TOOLING


if __name__ == "__main__":
    raise SystemExit(main())
