#!/usr/bin/env python3
"""Run `klt extract` + `klt lvs` for this repo's LVS proof cell and mint an
append-only evidence record.

This is the reproducible invocation of `klt extract`/`klt lvs` for this
repository -- the LVS half of the flow `layout/drc/run_drc.py` stood up for
DRC (issue #15). The underlying commands are deliberately unremarkable --

    klt extract layout/lvs/cells/lvs_unit.gds --deck gf180mcu --format json
    klt lvs layout/lvs/cells/lvs_request_match.json --format json
    klt lvs layout/lvs/cells/lvs_request_mismatch.json --format json

-- and you can always run them by hand (each request document's own header
comment repeats its exact command). What this script adds is the part that
makes a run *evidence* rather than a screenful of output:

  * it runs `klt extract` live on every invocation (not only `--regen`), so
    a run proves the verb itself, not just its previously-cached output;
  * it **asserts** the extraction report's device/net/pin fields (crucially
    `devices[].nets`, which is what proves the Metal1 (34/10) pin labels
    actually named the nets) against `cells/cells.json`;
  * it **asserts** each `klt lvs` case's `status`/`mismatch_count`/
    `category_counts` against that manifest -- both the positive control
    (a genuine match) and the negative control (a genuine, seeded
    mismatch), so a run that silently stops catching the seeded defect
    fails instead of looking green;
  * it verifies every committed artifact's sha256 (GDS, extracted netlist,
    reference netlists, request documents), so a report provably belongs to
    the committed geometry and netlists, not something that happened to be
    lying around;
  * it probes `klt`'s own capabilities against `../toolchain.json`'s
    `klt_required_commands` before running anything -- see that file for
    why this is a capability probe and not a version-string comparison;
  * it stamps the toolchain (`klt` version and path, `klayout` package
    version, interpreter, platform) and the repo git sha into the record;
  * it writes into a fresh `<record-id>` directory and refuses to overwrite
    an existing one, per this repo's append-only evidence rule.

Usage
-----
    python3 layout/lvs/run_lvs.py            # run and mint a new record
    python3 layout/lvs/run_lvs.py --check    # run, assert, write nothing
    python3 layout/lvs/run_lvs.py --regen    # regenerate the GDS and the
                                              # extracted netlist first

Exit codes
----------
    0  every assertion matched
    1  tooling problem (klt missing/incomplete, klayout missing, bad
       manifest, ...)
    2  at least one assertion did not match (extraction fields, an LVS
       case's verdict, or a committed artifact's hash)

Note that exit 0 does NOT mean "everything matched" in the LVS sense: the
negative-control case is *expected* to report `status: "mismatch"`. It
means "klt reported exactly what this bring-up expects it to report" --
mirroring `run_drc.py`'s own exit-code discipline.

Requirements
------------
`klt` (2AMLogic/klayout-tools) on PATH with `extract`/`lvs` (see
../toolchain.json), and -- only for `--regen` -- an interpreter with the pip
`klayout` package. Both are headless; neither the KLayout GUI application
nor the gf180mcu PDK install is needed. See ../README.md.
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
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS_DIR = os.path.join(HERE, "cells")
MANIFEST = os.path.join(CELLS_DIR, "cells.json")
REPORTS_DIR = os.path.join(HERE, "reports")
RECORDS_DIR = os.path.join(HERE, "records")
REPO_ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
TOOLCHAIN_PIN_PATH = os.path.join(REPO_ROOT, "layout", "toolchain.json")

EXIT_OK = 0
EXIT_TOOLING = 1
EXIT_MISMATCH = 2


class ToolingError(Exception):
    """Something about the environment, not the netlists, is wrong."""


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #


def load_toolchain_pin() -> dict:
    with open(TOOLCHAIN_PIN_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def find_klt() -> str:
    klt = shutil.which("klt")
    if klt is None:
        raise ToolingError(
            "`klt` not found on PATH. Install klayout-tools "
            "(https://github.com/2AMLogic/klayout-tools), e.g.\n"
            "    uv tool install git+https://github.com/2AMLogic/klayout-tools"
        )
    return klt


def check_klt_capabilities(klt: str, pin: dict) -> None:
    """Check every entry in `pin`'s `klt_required_commands` is a command
    `klt` actually knows about -- the drift-detectable check for this
    toolchain pin (see ../toolchain.json's `_comment` for why a version
    string cannot do this job: `klt --version` does not change between a
    release that has `extract`/`lvs` and one that does not).

    A single `klt --help` call (not one probe per command): every `klt`
    invocation that touches `klayout.db` pays a real, multi-second
    process-lifecycle cost (importing the native module), so this avoids
    tripling it for a check that a single top-level `--help` answers just
    as well -- the top-level parser lists every registered subcommand by
    name (see `klt --help`'s "positional arguments" section) without
    dispatching into any of them.

    Raises ToolingError naming every missing command plus the install
    command from the pin, rather than failing on the first one, so a
    completely stale `klt` reports a complete, actionable picture at once.
    """
    import re

    probe = subprocess.run([klt, "--help"], capture_output=True, text=True)
    if probe.returncode != 0:
        raise ToolingError(f"`klt --help` failed (exit {probe.returncode}): {probe.stderr}")

    listed = probe.stdout
    required = pin.get("klt_required_commands", [])
    missing = [
        command
        for command in required
        if not re.search(rf"(?m)^\s+{re.escape(command)}\s", listed)
    ]
    if missing:
        raise ToolingError(
            f"installed `klt` is missing required command(s): {', '.join(missing)}. "
            f"This repo's layout/ pin ({os.path.relpath(TOOLCHAIN_PIN_PATH, REPO_ROOT)}) "
            f"needs all of {required!r}. Reinstall from source:\n"
            f"    uv tool install --force {pin['klt_install']}\n"
            "(`klt --version` will not change -- see the pin file's own note.)"
        )


def find_klayout_python() -> str:
    """Return an interpreter that can `import klayout.db`.

    Identical logic to `layout/drc/run_drc.py`'s own copy: try this
    interpreter, then the one `klt` itself runs under.
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
        "committed GDS/netlist."
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


def regenerate(manifest: dict, klt: str, python: str) -> None:
    extract_cell = manifest["extract"]
    script = os.path.join(CELLS_DIR, extract_cell["generator"])
    proc = subprocess.run([python, script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ToolingError(f"{extract_cell['generator']} failed:\n{proc.stdout}{proc.stderr}")
    print(f"  regenerated {extract_cell['gds']}")

    gds_path = os.path.join(CELLS_DIR, extract_cell["gds"])
    netlist_path = os.path.join(CELLS_DIR, extract_cell["netlist"])
    deck = manifest["deck"]
    extract_proc = subprocess.run(
        [klt, "extract", gds_path, "--deck", deck, "-o", netlist_path, "--format", "json"],
        capture_output=True,
        text=True,
    )
    if extract_proc.returncode != 0:
        raise ToolingError(
            f"klt extract failed while regenerating {extract_cell['netlist']} "
            f"(exit {extract_proc.returncode}):\n{extract_proc.stderr}"
        )
    print(f"  regenerated {extract_cell['netlist']}")


def check_file_hash(label: str, path: str, expected_sha256: str, failures: list[str]) -> None:
    if not os.path.exists(path):
        failures.append(f"{label} missing -- run with --regen to build it: {path}")
        return
    actual = sha256(path)
    if actual != expected_sha256:
        failures.append(
            f"{label} sha256 mismatch: manifest says {expected_sha256}, file is {actual}"
        )


def run_extract(klt: str, manifest: dict) -> tuple[dict, str, list[str]]:
    """Run `klt extract` live against the committed GDS, into a scratch
    directory (the report's own artifacts are written from the in-memory
    result afterward, not from this scratch copy -- see `main()`).

    Returns `(report, netlist_text, failures)`.
    """
    extract_cell = manifest["extract"]
    gds_path = os.path.join(CELLS_DIR, extract_cell["gds"])
    deck = manifest["deck"]
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="klt-extract-") as scratch:
        scratch_netlist = os.path.join(scratch, f"{extract_cell['name']}.spice")
        proc = subprocess.run(
            [klt, "extract", gds_path, "--deck", deck, "-o", scratch_netlist, "--format", "json"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise ToolingError(
                f"klt extract failed on {gds_path} (exit {proc.returncode}):\n{proc.stderr}"
            )
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ToolingError(f"klt extract emitted non-JSON: {exc}") from exc

        with open(scratch_netlist, encoding="utf-8") as fh:
            netlist_text = fh.read()

    expected = extract_cell["expect"]
    for field in ("dbu_um", "device_count", "net_count", "pin_count"):
        if report.get(field) != expected[field]:
            failures.append(
                f"extract {field} mismatch: expected {expected[field]}, got {report.get(field)}"
            )
    if report.get("device_counts") != expected["device_counts"]:
        failures.append(
            "extract device_counts mismatch: expected "
            f"{expected['device_counts']}, got {report.get('device_counts')}"
        )
    if report.get("top") != expected["top"]:
        failures.append(f"extract top mismatch: expected {expected['top']!r}, got {report.get('top')!r}")
    if report.get("devices") != expected["devices"]:
        failures.append(
            "extract devices[] mismatch (this is the Metal1 pin-label proof): "
            f"expected {expected['devices']}, got {report.get('devices')}"
        )
    if report.get("nets") != expected["nets"]:
        failures.append(f"extract nets[] mismatch: expected {expected['nets']}, got {report.get('nets')}")
    if report.get("status") != "extracted":
        failures.append(f"extract status mismatch: expected 'extracted', got {report.get('status')!r}")
    if report.get("warnings"):
        failures.append(f"extract reported unexpected warnings: {report['warnings']}")

    # The freshly-extracted netlist should reproduce the committed one
    # byte-for-byte -- extraction has no wall-clock/random content (verified
    # while implementing this bring-up). A drift here means either the
    # committed netlist is stale (needs --regen) or the tool's output
    # changed upstream.
    committed_netlist_path = os.path.join(CELLS_DIR, extract_cell["netlist"])
    if not os.path.exists(committed_netlist_path):
        failures.append(f"committed netlist missing -- run with --regen: {committed_netlist_path}")
    else:
        with open(committed_netlist_path, encoding="utf-8") as fh:
            committed_text = fh.read()
        if committed_text != netlist_text:
            failures.append(
                "fresh `klt extract` output does not match the committed "
                f"{extract_cell['netlist']} byte-for-byte -- run --regen if this "
                "is an intentional deck/tool change"
            )

    return report, netlist_text, failures


def run_lvs_case(klt: str, case: dict) -> tuple[dict, str, int, list[str]]:
    """Run `klt lvs` for one committed request document.

    Returns `(report, text, exit_code, failures)`.
    """
    request_path = os.path.join(CELLS_DIR, case["request"])
    json_proc = subprocess.run(
        [klt, "lvs", request_path, "--format", "json"],
        capture_output=True,
        text=True,
    )
    # klt's documented exit codes for `lvs`: 0 match, 3 mismatch found, 1 an
    # actual error. Only the last one means the tool could not answer.
    if json_proc.returncode not in (0, 3):
        raise ToolingError(
            f"klt lvs failed on {request_path} (exit {json_proc.returncode}):\n"
            f"{json_proc.stderr}"
        )
    try:
        report = json.loads(json_proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(f"klt lvs emitted non-JSON for {request_path}: {exc}") from exc

    text_proc = subprocess.run(
        [klt, "lvs", request_path, "--format", "text"],
        capture_output=True,
        text=True,
    )

    failures: list[str] = []
    if report.get("status") != case["expect_status"]:
        failures.append(
            f"status mismatch: expected {case['expect_status']!r}, got {report.get('status')!r}"
        )
    if report.get("mismatch_count") != case["expect_mismatch_count"]:
        failures.append(
            f"mismatch_count mismatch: expected {case['expect_mismatch_count']}, "
            f"got {report.get('mismatch_count')}"
        )
    if report.get("category_counts") != case["expect_category_counts"]:
        failures.append(
            f"category_counts mismatch: expected {case['expect_category_counts']}, "
            f"got {report.get('category_counts')}"
        )
    # The authoritative verdict is always the engine's own compare() result
    # (see klayout_tools/lvs.py's module docstring) -- `status` is derived
    # from it, never re-derived here from the category counts, so this
    # assertion is deliberately a second, independent read of the same
    # field rather than a re-computation.
    expected_exit = 0 if case["expect_status"] == "match" else 3
    if json_proc.returncode != expected_exit:
        failures.append(
            f"klt lvs exit code mismatch: expected {expected_exit}, got {json_proc.returncode}"
        )

    return report, text_proc.stdout, json_proc.returncode, failures


def record_id() -> str:
    sha = git("rev-parse", "--short", "HEAD") or "nogit"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{sha}"


def write_record(
    rec_id: str,
    manifest: dict,
    extract_report: dict,
    extract_netlist_text: str,
    extract_failures: list[str],
    lvs_results: list[dict],
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

    extract_cell = manifest["extract"]
    with open(os.path.join(report_dir, f"{extract_cell['name']}.extract.json"), "w", encoding="utf-8") as fh:
        json.dump(extract_report, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(report_dir, f"{extract_cell['name']}.extract.spice"), "w", encoding="utf-8") as fh:
        fh.write(extract_netlist_text)

    for result in lvs_results:
        base = os.path.join(report_dir, result["name"])
        with open(f"{base}.lvs.json", "w", encoding="utf-8") as fh:
            json.dump(result["report"], fh, indent=2)
            fh.write("\n")
        with open(f"{base}.lvs.txt", "w", encoding="utf-8") as fh:
            fh.write(result["text"])

    with open(os.path.join(report_dir, "toolchain.json"), "w", encoding="utf-8") as fh:
        json.dump(toolchain, fh, indent=2)
        fh.write("\n")

    lines = [
        f"# LVS record {rec_id}",
        "",
        "Append-only evidence record for the gf180mcu LVS flow "
        "(`layout/lvs/`). Generated by `layout/lvs/run_lvs.py`; never edited "
        "in place -- a re-run mints a new record.",
        "",
        f"- **Record ID** — `{rec_id}`",
        "- **Claim** — the `klt extract`/`klt lvs` gf180mcu flow runs "
        "headless in this repo; extracts a single-device proof cell's "
        "connectivity correctly (Metal1 pin labels included); reports "
        "`match` against a genuinely-matching reference; and reports a "
        "real, structured `mismatch` against a deliberately wrong one.",
        "- **Geometry provenance** — the synthetic `lvs_unit` proof cell "
        "built by `layout/lvs/cells/gen_lvs_unit.py`, via the `klayout.db` "
        "API. Not extracted from, and not representative of, this block's "
        "real layout.",
        f"- **Deck** — `{manifest['deck']}` (upstream-owned curated "
        "extraction deck; see the approximations note in `layout/README.md`)",
        "- **Overall** — "
        + (
            "PASS (extraction and both LVS cases matched their expectations)"
            if overall_ok
            else "FAIL (at least one assertion did not match)"
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
        "## Extraction result",
        "",
        "| Field | Expected | Reported | Match |",
        "|---|---|---|---|",
    ]
    expected = extract_cell["expect"]
    for field in ("top", "dbu_um", "device_count", "net_count", "pin_count", "device_counts"):
        actual = extract_report.get(field)
        lines.append(
            f"| `{field}` | `{json.dumps(expected[field])}` | `{json.dumps(actual)}` | "
            + ("yes" if actual == expected[field] else "**NO**")
            + " |"
        )
    devices_ok = extract_report.get("devices") == expected["devices"]
    lines.append(
        f"| `devices[]` (incl. Metal1 pin-label net names) | `{json.dumps(expected['devices'])}` | "
        f"`{json.dumps(extract_report.get('devices'))}` | " + ("yes" if devices_ok else "**NO**") + " |"
    )
    if extract_failures:
        lines += ["", "**Extraction failures:**", ""]
        for failure in extract_failures:
            lines.append(f"- {failure}")

    lines += [
        "",
        "## LVS result",
        "",
        "| Case | Role | Expected status | Reported status | Expected "
        "`category_counts` | Reported `category_counts` | `klt lvs` exit | Match |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in lvs_results:
        case = result["case"]
        lines.append(
            "| `{name}` | {role} | `{exp_status}` | `{act_status}` | `{exp_cats}` | "
            "`{act_cats}` | {code} | {ok} |".format(
                name=result["name"],
                role=case["role"],
                exp_status=case["expect_status"],
                act_status=result["report"].get("status"),
                exp_cats=json.dumps(case["expect_category_counts"]),
                act_cats=json.dumps(result["report"].get("category_counts", {})),
                code=result["exit_code"],
                ok="yes" if not result["failures"] else "**NO**",
            )
        )

    lines += [
        "",
        "`klt lvs` exit codes: `0` match, `3` mismatch found. The 'mismatch' "
        "case is *supposed* to exit 3 — a `0` there would mean the negative "
        "control stopped catching the seeded width error.",
        "",
        "## Artifacts",
        "",
        "| Artifact | Path | sha256 |",
        "|---|---|---|",
        f"| `{extract_cell['gds']}` (GDS) | `cells/{extract_cell['gds']}` | "
        f"`{sha256(os.path.join(CELLS_DIR, extract_cell['gds']))}` |",
        f"| `{extract_cell['netlist']}` (extracted netlist) | "
        f"`cells/{extract_cell['netlist']}` | "
        f"`{sha256(os.path.join(CELLS_DIR, extract_cell['netlist']))}` |",
        f"| extraction JSON report | `reports/{rec_id}/{extract_cell['name']}.extract.json` | — |",
    ]
    for result in lvs_results:
        case = result["case"]
        lines.append(
            f"| `{case['reference']}` (reference) | `cells/{case['reference']}` | "
            f"`{sha256(os.path.join(CELLS_DIR, case['reference']))}` |"
        )
        lines.append(
            f"| `{case['request']}` (request) | `cells/{case['request']}` | "
            f"`{sha256(os.path.join(CELLS_DIR, case['request']))}` |"
        )
        lines.append(
            f"| {result['name']} LVS JSON report | `reports/{rec_id}/{result['name']}.lvs.json` | — |"
        )

    all_failures = list(extract_failures)
    for result in lvs_results:
        all_failures.extend(f"{result['name']}: {failure}" for failure in result["failures"])
    if all_failures:
        lines += ["", "## Failures", ""]
        for failure in all_failures:
            lines.append(f"- {failure}")

    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 layout/lvs/run_lvs.py --check",
        "```",
        "",
        "`--check` runs the same assertions without minting a record. Each "
        "`klt lvs` request document under `cells/` also states its own "
        "stand-alone command in its header comment.",
        "",
        f"- **Timestamp** — {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "- **Author** — Loom Builder agent (issue #51)",
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
        help="run extraction+LVS and assert expectations, but write no record",
    )
    parser.add_argument(
        "--regen",
        action="store_true",
        help="regenerate the proof-cell GDS and its extracted netlist first "
        "(needs the pip `klayout` package)",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest()
        toolchain_pin = load_toolchain_pin()
        klt = find_klt()
        check_klt_capabilities(klt, toolchain_pin)
        klt_version = subprocess.run(
            [klt, "--version"], capture_output=True, text=True
        ).stdout.strip()

        if args.regen:
            print("regenerating proof cell:")
            regenerate(manifest, klt, find_klayout_python())

        klayout_py = None
        try:
            klayout_py = find_klayout_python()
        except ToolingError:
            pass  # only needed for --regen; recorded as unknown otherwise

        toolchain = {
            "klt_version": klt_version or "unknown",
            "klt_path": os.path.realpath(klt),
            "klt_required_commands": toolchain_pin.get("klt_required_commands", []),
            "klayout_package": (
                klayout_version(klayout_py) if klayout_py else "not installed"
            ),
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "repo_git_sha": git("rev-parse", "HEAD") or "unknown",
            "repo_dirty": bool(git("status", "--porcelain")),
        }

        print(f"deck: {manifest['deck']}   klt: {toolchain['klt_version']}")

        extract_cell = manifest["extract"]
        gds_path = os.path.join(CELLS_DIR, extract_cell["gds"])
        hash_failures: list[str] = []
        check_file_hash("lvs_unit.gds", gds_path, extract_cell["sha256"], hash_failures)

        extract_report, extract_netlist_text, extract_failures = run_extract(klt, manifest)
        extract_failures = hash_failures + extract_failures

        status = "ok" if not extract_failures else "FAIL"
        print(
            f"  extract {extract_cell['name']:<16} "
            f"devices={extract_report.get('device_count')} "
            f"nets={extract_report.get('net_count')} [{status}]"
        )
        for failure in extract_failures:
            print(f"      - {failure}")

        lvs_results = []
        overall_ok = not extract_failures
        for case in manifest["lvs_cases"]:
            case_hash_failures: list[str] = []
            check_file_hash(
                case["reference"],
                os.path.join(CELLS_DIR, case["reference"]),
                case["sha256"],
                case_hash_failures,
            )
            check_file_hash(
                case["request"],
                os.path.join(CELLS_DIR, case["request"]),
                case["request_sha256"],
                case_hash_failures,
            )

            report, text, exit_code, failures = run_lvs_case(klt, case)
            failures = case_hash_failures + failures
            if failures:
                overall_ok = False

            lvs_results.append(
                {
                    "name": case["name"],
                    "case": case,
                    "report": report,
                    "text": text,
                    "exit_code": exit_code,
                    "failures": failures,
                }
            )

            case_status = "ok" if not failures else "FAIL"
            print(
                f"  lvs {case['name']:<20} {report.get('status'):<10} "
                f"mismatches={report.get('mismatch_count')} [{case_status}]"
            )
            for failure in failures:
                print(f"      - {failure}")

        if args.check:
            print("--check: no record written")
        else:
            rec_id = record_id()
            path = write_record(
                rec_id,
                manifest,
                extract_report,
                extract_netlist_text,
                extract_failures,
                lvs_results,
                toolchain,
                overall_ok,
            )
            print(f"wrote {os.path.relpath(path, REPO_ROOT)}")

        return EXIT_OK if overall_ok else EXIT_MISMATCH

    except ToolingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_TOOLING


if __name__ == "__main__":
    raise SystemExit(main())
