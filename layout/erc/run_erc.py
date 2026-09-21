#!/usr/bin/env python3
"""Run `klt erc` over ADC_BLOCK's supply spec and its controls, and mint an
append-only evidence record.

This is the reproducible invocation of `klt erc` for this repository -- the
structural power-delivery read T1 item 11 grades (klayout-tools#2025, issue
#330). The underlying command is deliberately unremarkable --

    klt erc layout/adc-top/adc_block.gds \\
      layout/erc/adc_block.supply-spec.json --format json

-- and you can always run that by hand. What this script adds is the part
that makes a run *evidence* rather than a screenful of output:

  * it runs every case in `cases.json` -- the supply spec itself, the
    negative control that proves the `erc.unconnected_net` rule was live,
    and the three known-gap reproductions the supply spec's `devices[]`
    block and `ties[]` omission are justified by;
  * it **asserts** each case against its expected `status`/`erc_status`,
    exit code, per-rule finding counts, coverage skips and carved device
    areas, so a run that silently stops reproducing a known gap fails
    instead of looking green;
  * it verifies the committed GDS hash against `cases.json` AND against
    each report's own `provenance.input.content_hash`, so a report provably
    belongs to the committed geometry;
  * it refuses to run under a `klt` that is not the build `toolchain.json`
    pins, because `klt erc`'s spec schema and its finding semantics both
    moved several times across the upstream issues that pin names;
  * it stamps the toolchain and the repo's git sha into the record;
  * it writes into a fresh `<record-id>` directory and refuses to overwrite
    an existing one, per this repo's append-only evidence rule.

Usage
-----
    python3 layout/erc/run_erc.py            # run, assert, mint a record
    python3 layout/erc/run_erc.py --check    # run, assert, write nothing
    python3 layout/erc/run_erc.py --verify   # re-derive the COMMITTED
                                             # reports, stdlib only, no klt

Exit codes
----------
    0  every case matched its expectation
    1  tooling problem (klt missing or not the pinned build, bad manifest)
    2  at least one case did not match its expectation, or a hash mismatch

Exit 0 does NOT mean "the layout is ERC-clean": three of the five cases are
*expected* to report findings or a partial status. It means "`klt erc`
reported exactly what it was supposed to report". `klt erc`'s own exit code
(0 clean / 3 violations / 4 no antenna check possible) is recorded per case
but is not this script's exit code.

`--verify` is the stdlib-only half, for CI: it re-reads the committed
reports under `reports/<record-id>/` and re-asserts every expectation in
`cases.json` against them, plus the committed GDS hash. It cannot re-run the
tool, so it cannot catch an upstream behaviour change -- that is what a
re-run under the pinned build is for -- but it does catch a committed report
drifting away from the geometry or the expectations it claims to describe.
It is the same division of labour `signoff/run_signoff.py --check` draws.

Requirements
------------
`klt` (2AMLogic/klayout-tools) on PATH at the exact commit `toolchain.json`
pins. Headless: neither the KLayout GUI application nor the gf180mcu PDK
install is needed. See ./README.md.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "cases.json")
TOOLCHAIN = os.path.join(HERE, "toolchain.json")
REPORTS_DIR = os.path.join(HERE, "reports")
RECORDS_DIR = os.path.join(HERE, "records")
LAYOUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(LAYOUT_DIR, os.pardir))

# `layout/` is a plain directory, not an installed package, and this script
# is run as `python3 layout/erc/run_erc.py` (sys.path[0] is layout/erc), so
# the shared helper module has to be put on the path explicitly -- the same
# two lines layout/drc/run_drc.py and layout/lvs/run_lvs.py use.
if LAYOUT_DIR not in sys.path:
    sys.path.insert(0, LAYOUT_DIR)

from klt_env import (  # noqa: E402  (import follows the sys.path setup above)
    EXIT_MISMATCH,
    EXIT_OK,
    EXIT_TOOLING,
    ToolingError,
    git,
    load_manifest,
    record_id,
    reserve_record_slot,
    sha256,
)

# `klt erc`'s documented exit codes: 0 clean / clean_partial, 3 violations,
# 4 nothing gradeable on the antenna side. 1 and 2 mean the tool could not
# answer at all.
ERC_REPORT_EXITS = (0, 3, 4)


# --------------------------------------------------------------------------- #
# toolchain
# --------------------------------------------------------------------------- #


def klt_identity(klt: str) -> dict:
    proc = subprocess.run(
        [klt, "version", "--format", "json"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise ToolingError(
            f"`{klt} version --format json` failed: {proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(f"`klt version` emitted non-JSON: {exc}") from exc


def resolve_klt(pin: dict, override: str | None) -> tuple[str, dict]:
    """Locate a `klt` and refuse one that is not the pinned build."""
    found = override or shutil.which("klt")
    if not found:
        raise ToolingError(
            "no `klt` on PATH. Install the pinned build:\n"
            f"    pip install '{pin['klt_install']}'\n"
            "(or pass --klt /path/to/klt)"
        )
    identity = klt_identity(found)
    problems = [
        f"  {field}: {identity.get(field)!r} != pinned {pinned!r}"
        for field, pinned in (
            ("git_commit", pin["klt_git_commit"]),
            ("version", pin["klt_version"]),
        )
        if identity.get(field) != pinned
    ]
    if problems:
        raise ToolingError(
            "`klt` is not the build layout/erc/toolchain.json pins:\n"
            + "\n".join(problems)
            + "\nInstall the pinned build:\n"
            f"    pip install '{pin['klt_install']}'\n"
            "See that file's _comment for why an older `klt` -- including the "
            "one layout/toolchain.json pins for DRC/LVS -- cannot produce "
            "item-11 evidence."
        )
    return found, identity


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def run_case(klt: str, layout_rel: str, spec_rel: str) -> tuple[dict, str, int]:
    """Run `klt erc` twice: JSON (the contract) and text (a courtesy view).

    Invoked from the repo root with repo-relative paths, so the report's own
    `file`/`spec` fields are portable: an absolute path would bake this
    machine's checkout location into committed evidence.
    """
    argv = [klt, "erc", layout_rel, spec_rel, "--format", "json"]
    json_proc = subprocess.run(argv, capture_output=True, text=True, cwd=REPO_ROOT)
    if json_proc.returncode not in ERC_REPORT_EXITS:
        raise ToolingError(
            f"klt erc failed on {spec_rel} (exit {json_proc.returncode}):\n"
            f"{json_proc.stderr}"
        )
    try:
        report = json.loads(json_proc.stdout)
    except json.JSONDecodeError as exc:
        raise ToolingError(f"klt erc emitted non-JSON for {spec_rel}: {exc}") from exc

    text_proc = subprocess.run(
        [klt, "erc", layout_rel, spec_rel, "--format", "text"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "NO_COLOR": "1"},
    )
    return report, text_proc.stdout, json_proc.returncode


def finding_counts(report: dict) -> dict:
    counts: dict = {}
    for finding in report.get("erc_findings") or []:
        counts[finding["rule"]] = counts.get(finding["rule"], 0) + 1
    return counts


def skipped_reasons(report: dict) -> dict:
    counts: dict = {}
    for entry in (report.get("erc_coverage") or {}).get("skipped") or []:
        counts[entry["reason"]] = counts.get(entry["reason"], 0) + 1
    return counts


def check_case(
    case: dict, report: dict, exit_code: int, spec: dict, layout_sha: str
) -> list[str]:
    """Return a list of failure strings; empty means the case matched."""
    failures: list[str] = []
    expect = case["expect"]

    def cmp(name: str, actual) -> None:
        if name in expect and actual != expect[name]:
            failures.append(f"{name}: expected {expect[name]!r}, got {actual!r}")

    cmp("exit_code", exit_code)
    cmp("status", report.get("status"))
    cmp("erc_status", report.get("erc_status"))
    cmp("gate_count", report.get("gate_count"))
    cmp("erc_finding_counts", finding_counts(report))
    cmp("erc_coverage_skipped_reasons", skipped_reasons(report))

    if "device_body_area_um2" in expect:
        actual = {
            entry["name"]: entry["body_area_um2"]
            for entry in (report.get("provenance") or {}).get("devices") or []
        }
        if actual != expect["device_body_area_um2"]:
            failures.append(
                f"device_body_area_um2: expected {expect['device_body_area_um2']}, "
                f"got {actual}"
            )

    for net in expect.get("finding_nets", []):
        if not any(f.get("net") == net for f in report.get("erc_findings") or []):
            failures.append(f"no finding names net {net!r}")

    for net in expect.get("gate_nets_present", []):
        if not any(g.get("net") == net for g in report.get("gates") or []):
            failures.append(f"no gates[] entry carries net {net!r}")

    if "spec_declares_ties" in expect:
        declares = bool(spec.get("ties"))
        if declares != expect["spec_declares_ties"]:
            failures.append(
                f"spec_declares_ties: expected {expect['spec_declares_ties']}, "
                f"got {declares}"
            )

    # The report must describe the committed geometry, not some other stream.
    reported = ((report.get("provenance") or {}).get("input") or {}).get(
        "content_hash"
    )
    if reported != f"sha256:{layout_sha}":
        failures.append(
            f"provenance.input.content_hash {reported!r} != committed layout "
            f"sha256:{layout_sha}"
        )

    # ... and the declarations it was actually run with.
    spec_hash = ((report.get("provenance") or {}).get("spec") or {}).get("content_hash")
    if not spec_hash:
        failures.append(
            "report carries no provenance.spec.content_hash "
            "(klayout-tools#2036) -- it cannot be re-verified against its spec"
        )

    return failures


# --------------------------------------------------------------------------- #
# --verify (stdlib only: re-read the committed reports)
# --------------------------------------------------------------------------- #


def latest_record() -> str:
    if not os.path.isdir(REPORTS_DIR):
        raise ToolingError(f"{REPORTS_DIR} does not exist -- nothing to verify")
    slots = sorted(
        name
        for name in os.listdir(REPORTS_DIR)
        if os.path.isdir(os.path.join(REPORTS_DIR, name))
    )
    if not slots:
        raise ToolingError(f"{REPORTS_DIR} is empty -- nothing to verify")
    return slots[-1]


def verify(manifest: dict, rec_id: str | None) -> int:
    rec_id = rec_id or latest_record()
    report_dir = os.path.join(REPORTS_DIR, rec_id)
    layout_path = os.path.join(REPO_ROOT, manifest["layout"])
    expected_sha = manifest["layout_sha256"]

    print(f"verifying committed reports in reports/{rec_id} (no klt needed)")
    failures: list[str] = []

    actual_sha = sha256(layout_path)
    if actual_sha != expected_sha:
        failures.append(
            f"{manifest['layout']}: sha256 {actual_sha} != cases.json "
            f"{expected_sha} -- re-run layout/erc/run_erc.py"
        )
    else:
        print(f"  [ok] {manifest['layout']} sha256 matches cases.json")

    for case in manifest["cases"]:
        path = os.path.join(report_dir, f"{case['name']}.erc.json")
        if not os.path.exists(path):
            failures.append(f"{case['name']}: no committed report at {path}")
            continue
        with open(path, encoding="utf-8") as fh:
            report = json.load(fh)
        spec_path = os.path.join(HERE, case["spec"])
        with open(spec_path, encoding="utf-8") as fh:
            spec = json.load(fh)
        exit_code = report.pop("_klt_exit_code", None)
        case_failures = check_case(case, report, exit_code, spec, expected_sha)
        # The spec on disk must still be the one the report was run against.
        spec_hash = ((report.get("provenance") or {}).get("spec") or {}).get(
            "content_hash"
        )
        actual_spec_hash = f"sha256:{sha256(spec_path)}"
        if spec_hash != actual_spec_hash:
            case_failures.append(
                f"spec {case['spec']} has changed since the report was minted "
                f"({actual_spec_hash} != {spec_hash})"
            )
        if case_failures:
            failures.extend(f"{case['name']}: {f}" for f in case_failures)
            print(f"  [FAIL] {case['name']}")
            for failure in case_failures:
                print(f"      - {failure}")
        else:
            print(f"  [ok] {case['name']}")

    if failures:
        print(f"\n{len(failures)} failure(s)", file=sys.stderr)
        return EXIT_MISMATCH
    print("\nall committed ERC reports still describe the committed geometry "
          "and match cases.json")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# the record
# --------------------------------------------------------------------------- #


def write_record(
    rec_id: str,
    manifest: dict,
    results: list[dict],
    toolchain: dict,
    overall_ok: bool,
    issue: str | None = None,
) -> str:
    report_dir = reserve_record_slot(rec_id, REPORTS_DIR, RECORDS_DIR)
    record_path = os.path.join(RECORDS_DIR, f"{rec_id}.md")

    for result in results:
        base = os.path.join(report_dir, result["name"])
        payload = dict(result["report"])
        payload["_klt_exit_code"] = result["exit_code"]
        with open(f"{base}.erc.json", "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        with open(f"{base}.erc.txt", "w", encoding="utf-8") as fh:
            fh.write(result["text"])

    with open(os.path.join(report_dir, "toolchain.json"), "w", encoding="utf-8") as fh:
        json.dump(toolchain, fh, indent=2)
        fh.write("\n")

    supply = next(r for r in results if r["name"] == "adc_block.supply")
    lines = [
        f"# ERC record {rec_id}",
        "",
        "Append-only evidence record for the `klt erc` structural "
        "power-delivery flow (`layout/erc/`). Generated by "
        "`layout/erc/run_erc.py`; never edited in place -- a re-run mints a "
        "new record.",
        "",
        f"- **Record ID** — `{rec_id}`",
        "- **Claim** — every supply `layout/erc/adc_block.supply-spec.json` "
        "declares resolves to exactly one electrical island in "
        f"`{manifest['layout']}`: zero `erc.unconnected_net`, zero "
        "`erc.supply_short`.",
        "- **Not claimed** — `erc.missing_tie`. The supply spec declares no "
        "`ties[]`, so that check was **not computed**; its zero count below "
        "is an absence of evidence, not evidence of absence. See "
        "`layout/erc/README.md` for why, and for the well-tie evidence that "
        "stands in.",
        f"- **Geometry** — `{manifest['layout']}` "
        f"(sha256 `{manifest['layout_sha256']}`), top cell "
        f"`{manifest['layout_top']}`.",
        "- **Overall** — "
        + (
            "PASS (every case reported exactly what it was expected to)"
            if overall_ok
            else "FAIL (at least one case did not match its expectation)"
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
        "| Case | Role | `status` | `erc_status` | findings | `klt erc` exit "
        "| Match |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        report = result["report"]
        lines.append(
            "| `{name}` | {role} | `{status}` | `{erc_status}` | `{counts}` | "
            "{code} | {ok} |".format(
                name=result["name"],
                role=result["case"]["role"],
                status=report.get("status"),
                erc_status=report.get("erc_status"),
                counts=json.dumps(finding_counts(report)) or "{}",
                code=result["exit_code"],
                ok="yes" if not result["failures"] else "**NO**",
            )
        )

    lines += [
        "",
        "`klt erc` exit codes: `0` clean/clean_partial, `3` violations, `4` "
        "no antenna level could be graded (`status: \"not_checked\"`). Exit "
        "`4` is the expected code for **every** gf180mcu run: `klt erc` "
        "ships an antenna-ratio table for sky130 only, so no level on this "
        "PDK is ever compared against a limit. That is a statement about "
        "the antenna half of the envelope and says nothing about the "
        "connectivity half, whose verdict is `erc_status`. Item 11 grades "
        "the supply-continuity rules directly, not this `status`.",
        "",
        "## What the supply case actually says",
        "",
        f"- `erc_status`: `{supply['report'].get('erc_status')}` — no "
        "connectivity rule fired and no connectivity work was skipped.",
        f"- `gate_count`: {supply['report'].get('gate_count')} gate nets, "
        "identified as `poly ∩ diff` (`stackup[0].active_layer`).",
        "- `vdd`: one island, carrying all four `vdd` labels "
        "(`ADC_DECODE_BANK_N`, `ADC_DECODE_BANK_P`, `ADC_TOP_SW`, "
        "`COMPARATOR`).",
        "- `vss`: one island, carrying all four `vss` labels, and **not** "
        "the same island as `vdd`.",
        "",
        "## Artifacts",
        "",
        "| Case | Spec | JSON report | text report |",
        "|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| `{name}` | `layout/erc/{spec}` | "
            "`reports/{rid}/{name}.erc.json` | "
            "`reports/{rid}/{name}.erc.txt` |".format(
                name=result["name"], spec=result["case"]["spec"], rid=rec_id
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
        f"pip install '{toolchain['klt_install']}'",
        "python3 layout/erc/run_erc.py --check    # re-run and assert",
        "python3 layout/erc/run_erc.py --verify   # re-read this record, no klt",
        "```",
        "",
        "The JSON report is the stable contract; the `.txt` capture beside "
        "it is a courtesy view, not the source of truth. Each committed "
        "JSON carries one added key, `_klt_exit_code`, which is this "
        "runner's record of the process exit status rather than part of "
        "`klt erc`'s own envelope — `--verify` strips it before asserting.",
        "",
        f"- **Timestamp** — {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        # The issue this run was minted FOR, not the issue that stood the
        # flow up: #330 built it, and every later re-run has its own reason.
        # Hard-coding #330 here made each new record misattribute itself.
        "- **Author** — Loom Builder agent"
        + (f" (issue {issue})" if issue else ""),
        "",
    ]

    with open(record_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return record_path


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the cases and assert expectations, but write no record",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="re-derive the committed reports with the stdlib only (no klt)",
    )
    parser.add_argument(
        "--record",
        help="with --verify: the reports/<record-id> to verify (default: latest)",
    )
    parser.add_argument("--klt", help="path to the pinned klt binary")
    parser.add_argument(
        "--issue",
        help="issue this run is minted for, stamped into the record's "
        "Author line (e.g. '#340'); omitted from the record when unset",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest(CASES)

        if args.verify:
            return verify(manifest, args.record)

        pin = load_manifest(TOOLCHAIN)
        klt, identity = resolve_klt(pin, args.klt)

        layout_rel = manifest["layout"]
        layout_path = os.path.join(REPO_ROOT, layout_rel)
        layout_sha = sha256(layout_path)
        if layout_sha != manifest["layout_sha256"]:
            raise ToolingError(
                f"{layout_rel} sha256 {layout_sha} != cases.json "
                f"{manifest['layout_sha256']}. The geometry moved; update "
                "cases.json deliberately and mint a new record -- do not "
                "leave a report describing a GDS this repo no longer holds."
            )

        toolchain = {
            "klt_version": identity.get("version", "unknown"),
            "klt_git_commit": identity.get("git_commit", "unknown"),
            "klt_install": pin["klt_install"],
            "klt_path": os.path.realpath(klt),
            "klayout_package": identity.get("klayout_version", "unknown"),
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "repo_git_sha": git(REPO_ROOT, "rev-parse", "HEAD") or "unknown",
            "repo_dirty": bool(git(REPO_ROOT, "status", "--porcelain")),
        }

        print(f"layout: {layout_rel}   klt: {toolchain['klt_version']}")
        results = []
        overall_ok = True
        for case in manifest["cases"]:
            spec_rel = os.path.join("layout", "erc", case["spec"])
            spec_path = os.path.join(HERE, case["spec"])
            with open(spec_path, encoding="utf-8") as fh:
                spec = json.load(fh)

            report, text, exit_code = run_case(klt, layout_rel, spec_rel)
            failures = check_case(case, report, exit_code, spec, layout_sha)
            if failures:
                overall_ok = False

            results.append(
                {
                    "name": case["name"],
                    "case": case,
                    "report": report,
                    "text": text,
                    "exit_code": exit_code,
                    "failures": failures,
                }
            )
            print(
                f"  {case['name']:<34} {str(report.get('status')):<13}"
                f"{str(report.get('erc_status')):<15}"
                f"{json.dumps(finding_counts(report)):<32}"
                f"[{'ok' if not failures else 'FAIL'}]"
            )
            for failure in failures:
                print(f"      - {failure}")

        if args.check:
            print("--check: no record written")
        else:
            rec_id = record_id(REPO_ROOT)
            path = write_record(
                rec_id, manifest, results, toolchain, overall_ok, args.issue
            )
            print(f"wrote {os.path.relpath(path, REPO_ROOT)}")

        return EXIT_OK if overall_ok else EXIT_MISMATCH

    except ToolingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_TOOLING


if __name__ == "__main__":
    raise SystemExit(main())
