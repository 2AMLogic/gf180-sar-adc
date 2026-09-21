#!/usr/bin/env python3
"""Grade this block's T1 state with `klt signoff --manifest`, and keep the
committed verdict from rotting.

Issue #331. Two entry points, deliberately split by what they need:

  python3 signoff/run_signoff.py --check    # stdlib only. No `klt`, no PDK.
  python3 signoff/run_signoff.py --regen    # needs the pinned `klt`.

WHY THE SPLIT. The verdict of record for "how far is this block from T1" is
`klt signoff --manifest signoff/gf180-sar-adc.manifest.json`'s own output,
committed under `signoff/reports/`. Minting it needs `klt`, which this
repo's CI cannot install on the pull-request path (see
`.github/workflows/ci.yml`'s inventory: `layout/`'s DRC/LVS runners are
excluded for exactly this reason). A verdict CI cannot re-derive is a
verdict that goes stale silently -- which is the failure mode the manifest
exists to end, so shipping one would be self-defeating.

`--check` is the answer: it re-derives, with nothing but CPython, every
input the committed verdict rests on.

  * every cited evidence envelope still says what the report says it said
    (`status`, and the provenance/environment hash fields the envelope
    carries about ITS OWN input);
  * every repo artifact behind a citation still hashes to the value pinned
    in `signoff/freshness.json` -- so editing `layout/adc-top/adc_block.gds`
    without re-running DRC turns CI red on the next pull request, which is
    the whole point;
  * the committed report agrees with the manifest (same citations, same
    pins, same block/kind) and with the toolchain pin (same `klt` build,
    same checklist-document hash);
  * every rendered row's `status`/`reason` matches the expectation recorded
    beside it -- including the UNMET ones. A row silently flipping to `met`
    is as much a drift signal as one flipping to `unmet`.

What `--check` CANNOT do is re-run the grader, so it cannot catch a change
in `klt`'s own grading RULES. That is what `signoff/toolchain.json`'s
`grading_ruleset_id` and `source_doc_content_hash` pins are for: they name
the rules and the checklist text the committed report was graded under, and
a bump is a reviewed change with a new evidence record, never a silent
re-grade.

`--selftest` is the negative control for all of the above, in the same
spirit as `sim/selftest.sh` stage 4: it proves `--check` actually fails on a
tampered input rather than passing vacuously. It runs in CI beside
`--check`.

PROVENANCE HYGIENE. Nothing this script writes records a hostname, a login,
or an absolute path -- see `design-evidence-tiers.md`'s "Provenance hygiene
in evidence records". Paths in the report and in `signoff/freshness.json`
are repo-root-relative; the grader's identity is pinned by commit, not by
where it happens to be installed.

WHY NOT IMPORT `layout/klt_env.py`. That module is the shared implementation
for the two `layout/` runners that sit beside it, and every function in it
that this script would want (`find_klt`, `check_klt_capabilities`,
`record_id`) presumes `layout/toolchain.json`'s pin and a `klt` on the path.
`--check` must run with no `klt` at all, and `signoff/` pins a DIFFERENT,
newer `klt` than `layout/` does (see `signoff/toolchain.json`: item 11 needs
a build past klayout-tools#2025, which `layout/toolchain.json`'s `85b8125`
is far behind). Sharing the module would couple two pins that must be free
to move independently; the ~20 duplicated lines are the cheaper half of that
trade, and are marked where they occur.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

#: `klt signoff --format text` colours met/unmet rows with ANSI escapes and
#: emits them unconditionally -- deliberately not gated on `isatty()`, and
#: with no `--no-color`/`$NO_COLOR` opt-out (verified against the pinned
#: build; its own source comment calls the colouring a "terminal-first
#: courtesy rendering"). Raw escapes do not belong in a committed evidence
#: artifact that reviewers read as a diff, so the text rendering is stripped
#: on the way in. The JSON report beside it is the artifact of record and is
#: byte-identical to what the grader emitted; filed upstream as
#: klayout-tools#2227 per CLAUDE.md's friction protocol.
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

EXIT_OK = 0
EXIT_TOOLING = 1
EXIT_MISMATCH = 2

SIGNOFF_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SIGNOFF_DIR)

MANIFEST_REL = "signoff/gf180-sar-adc.manifest.json"
FRESHNESS_REL = "signoff/freshness.json"
TOOLCHAIN_REL = "signoff/toolchain.json"
REPORTS_REL = "signoff/reports"
RECORDS_REL = "signoff/records"


class ToolingError(Exception):
    """A problem with the environment, not with the evidence."""


# --------------------------------------------------------------------------
# small helpers (the `layout/klt_env.py` duplication the docstring names)
# --------------------------------------------------------------------------


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def git(repo_root: str, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", repo_root, *args], capture_output=True, text=True
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def record_id(repo_root: str) -> str:
    """`<timestamp>-<short sha>`, the same record naming `layout/` uses."""
    sha = git(repo_root, "rev-parse", "--short", "HEAD") or "nogit"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{sha}"


def load_json(root: str, rel: str) -> dict:
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return json.load(fh)


def dotted(doc, path: str):
    """Resolve `a.b.c` in a decoded JSON document; `KeyError` if absent.

    Deliberately strict: a missing field is a failed assertion, never a
    silently-None one. An envelope that stopped carrying the field a pin is
    written against has changed shape, and that is exactly what a freshness
    check is for.
    """
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
    return cur


def manifest_citations(manifest: dict) -> dict:
    """`{item key: (file, content_hash or None)}` from a block manifest.

    Only the file-backed entry shapes `klt signoff` documents are handled --
    a bare path string, or `{"file": ..., "content_hash": ...}`. This repo
    cites no command-backed entries (they would re-run a tool `--check` has
    no way to re-run), and an unrecognised shape is an error rather than
    something to skip past.
    """
    out = {}
    for key, entry in (manifest.get("evidence") or {}).items():
        if isinstance(entry, str):
            out[key] = (entry, None)
        elif isinstance(entry, dict) and "file" in entry:
            out[key] = (entry["file"], entry.get("content_hash"))
        else:
            raise ToolingError(
                f"manifest evidence entry {key!r} is not a file-backed entry; "
                "signoff/run_signoff.py only understands the shapes this "
                "repo actually uses (see manifest_citations())"
            )
    return out


# --------------------------------------------------------------------------
# --check
# --------------------------------------------------------------------------


def check(root: str, verbose: bool = True) -> list:
    """Re-derive everything the committed verdict rests on. Returns failures."""
    failures: list = []

    def fail(msg: str) -> None:
        failures.append(msg)

    def ok(msg: str) -> None:
        if verbose:
            print(f"  [ok] {msg}")

    manifest = load_json(root, MANIFEST_REL)
    freshness = load_json(root, FRESHNESS_REL)
    toolchain = load_json(root, TOOLCHAIN_REL)
    cites = manifest_citations(manifest)

    # 1. manifest <-> freshness agreement -------------------------------
    declared = freshness["citations"]
    if set(declared) != set(cites):
        fail(
            "signoff/freshness.json declares citations "
            f"{sorted(declared)} but the manifest cites {sorted(cites)}"
        )
    for key in sorted(set(declared) & set(cites)):
        path, pin = cites[key]
        spec = declared[key]
        if spec["file"] != path:
            fail(f"item {key}: manifest cites {path}, freshness declares {spec['file']}")
            continue
        if spec.get("manifest_pins") != pin:
            fail(
                f"item {key}: manifest pins content_hash {pin!r}, "
                f"freshness declares {spec.get('manifest_pins')!r}"
            )
        if spec.get("manifest_pins") is None and not spec.get("manifest_pin_note"):
            fail(
                f"item {key}: citation carries no content_hash and no "
                "manifest_pin_note saying why -- an unpinned citation is only "
                "acceptable with a recorded reason"
            )
        ok(f"item {key}: manifest and freshness agree on {path}")

    # 2. every cited envelope still says what it said --------------------
    for key in sorted(declared):
        spec = declared[key]
        envelope_path = os.path.join(root, spec["file"])
        if not os.path.exists(envelope_path):
            fail(f"item {key}: cited envelope is missing: {spec['file']}")
            continue
        try:
            envelope = json.load(open(envelope_path, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fail(f"item {key}: cited envelope is unreadable: {spec['file']} ({exc})")
            continue
        for field, expected in (spec.get("envelope_asserts") or {}).items():
            try:
                actual = dotted(envelope, field)
            except KeyError:
                fail(f"item {key}: {spec['file']} no longer carries `{field}`")
                continue
            if actual != expected:
                fail(
                    f"item {key}: {spec['file']} `{field}` is {actual!r}, "
                    f"pinned as {expected!r}"
                )
        ok(f"item {key}: envelope fields match ({len(spec.get('envelope_asserts') or {})} pinned)")

        # 3. the repo artifacts behind the citation still hash the same ---
        for artifact, expected_hash in (spec.get("artifacts") or {}).items():
            artifact_path = os.path.join(root, artifact)
            if not os.path.exists(artifact_path):
                fail(f"item {key}: pinned artifact is missing: {artifact}")
                continue
            actual_hash = sha256(artifact_path)
            if actual_hash != expected_hash:
                fail(
                    f"item {key}: {artifact} has changed since this evidence "
                    f"was recorded ({actual_hash} != pinned {expected_hash}) -- "
                    "re-run the flow that produced "
                    f"{spec['file']}, then `signoff/run_signoff.py --regen`"
                )
            else:
                ok(f"item {key}: {artifact} unchanged")

    # 4. the committed report agrees with manifest + toolchain -----------
    report_spec = freshness["report"]
    report_path = os.path.join(root, report_spec["json"])
    if not os.path.exists(report_path):
        fail(f"committed report is missing: {report_spec['json']}")
        return failures
    if sha256(report_path) != report_spec["sha256"]:
        fail(
            f"{report_spec['json']} has been edited since it was minted "
            "(sha256 mismatch) -- a tier report is `--regen` output, never "
            "hand-edited"
        )
    report = json.load(open(report_path, encoding="utf-8"))

    for field, expected in (
        ("block", manifest["block"]),
        ("kind", manifest["kind"]),
    ):
        if report.get(field) != expected:
            fail(f"report {field} is {report.get(field)!r}, manifest says {expected!r}")

    if report.get("build", {}).get("git_commit") != toolchain["klt_git_commit"]:
        fail(
            "report was graded by klt "
            f"{report.get('build', {}).get('git_commit')!r}, "
            f"signoff/toolchain.json pins {toolchain['klt_git_commit']!r}"
        )
    if report.get("build", {}).get("grading_ruleset_id") != toolchain["grading_ruleset_id"]:
        fail(
            "report's grading_ruleset_id "
            f"{report.get('build', {}).get('grading_ruleset_id')!r} is not the "
            f"pinned {toolchain['grading_ruleset_id']!r}"
        )
    if report.get("source_doc_content_hash") != toolchain["source_doc_content_hash"]:
        fail(
            "report graded a checklist document hashing "
            f"{report.get('source_doc_content_hash')!r}; "
            f"signoff/toolchain.json pins {toolchain['source_doc_content_hash']!r} "
            "-- upstream's T1 checklist has moved, so this block's verdict is "
            "due a re-read"
        )
    for field in ("t1_item_count", "t1_met_count", "tier"):
        if report.get(field) != report_spec[field]:
            fail(
                f"report {field} is {report.get(field)!r}, "
                f"freshness records {report_spec[field]!r}"
            )
    ok(
        f"report: {report_spec['t1_met_count']}/{report_spec['t1_item_count']} "
        f"T1 rows met, tier={report_spec['tier']!r}, graded by "
        f"{toolchain['klt_version']}"
    )

    # 5. every rendered row matches its recorded expectation -------------
    expected_rows = freshness["expected_rows"]
    seen = set()
    for item in report.get("items", []):
        row = row_key(item)
        seen.add(row)
        if row not in expected_rows:
            fail(f"report row {row} has no recorded expectation in freshness.json")
            continue
        want = expected_rows[row]
        got = {"status": item.get("status"), "reason": item.get("reason")}
        if got != want:
            fail(
                f"row {row}: report says {got}, freshness expects {want} -- if "
                "this is a real change, re-run `--regen` and say what moved in "
                "a new signoff/records/ entry"
            )
    for row in sorted(set(expected_rows) - seen):
        fail(f"freshness.json expects row {row}, which the report does not render")
    ok(f"rows: {len(seen)} rendered rows match their recorded status/reason")

    return failures


def row_key(item: dict) -> str:
    """`T1#3.analog` / `T2` -- the stable name of one rendered report row."""
    tier = item.get("tier")
    if item.get("id") is None:
        return str(tier)
    partition = item.get("partition")
    base = f"{tier}#{item['id']}"
    return f"{base}.{partition}" if partition else base


# --------------------------------------------------------------------------
# --regen
# --------------------------------------------------------------------------


def klt_identity(klt: str) -> dict:
    proc = subprocess.run(
        [klt, "version", "--format", "json"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise ToolingError(f"`{klt} version --format json` failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def resolve_klt(root: str, klt: str | None) -> str:
    """Locate a `klt` and refuse one that is not the pinned build."""
    toolchain = load_json(root, TOOLCHAIN_REL)
    found = klt or shutil.which("klt")
    if not found:
        raise ToolingError(
            "no `klt` on PATH. Install the pinned build:\n"
            f"    pip install '{toolchain['klt_install']}'\n"
            "(or pass --klt /path/to/klt)"
        )
    identity = klt_identity(found)
    problems = []
    for field, pinned in (
        ("git_commit", toolchain["klt_git_commit"]),
        ("version", toolchain["klt_version"]),
        ("grading_ruleset_id", toolchain["grading_ruleset_id"]),
    ):
        if identity.get(field) != pinned:
            problems.append(f"  {field}: {identity.get(field)!r} != pinned {pinned!r}")
    if problems:
        raise ToolingError(
            "`klt` is not the build signoff/toolchain.json pins:\n"
            + "\n".join(problems)
            + "\nInstall the pinned build:\n"
            f"    pip install '{toolchain['klt_install']}'\n"
            "A released wheel is NOT interchangeable here -- see that file's "
            "_comment on why the item-11 row needs this commit."
        )
    return found


def regen(root: str, klt: str | None) -> int:
    klt_bin = resolve_klt(root, klt)
    rec_id = record_id(root)
    report_dir_rel = os.path.join(REPORTS_REL, rec_id)
    report_dir = os.path.join(root, report_dir_rel)
    if os.path.exists(report_dir):
        raise ToolingError(
            f"{report_dir_rel} already exists -- signoff/reports/ is "
            "append-only, like sim/ and layout/*/reports/"
        )

    # Run from the repo root: a manifest's file-backed evidence paths resolve
    # against the INVOKING process's working directory, with no
    # manifest-relative anchoring (klayout-tools' examples/signoff/README.md
    # says so explicitly). Anywhere else and every citation misses.
    def run(fmt: str) -> str:
        proc = subprocess.run(
            [klt_bin, "signoff", "--manifest", MANIFEST_REL, "--format", fmt],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "NO_COLOR": "1", "KLT_TIERS_DOC": ""},
        )
        # exit 3 == "rendered fine, block is not at a tier yet", which is this
        # block's expected state; only 0 and 3 are reports.
        if proc.returncode not in (0, 3):
            raise ToolingError(
                f"`klt signoff --format {fmt}` exited {proc.returncode}: "
                f"{proc.stderr.strip()}"
            )
        return proc.stdout

    report_json_text = run("json")
    report_text = _ANSI_RE.sub("", run("text"))
    report = json.loads(report_json_text)

    os.makedirs(report_dir)
    json_rel = os.path.join(report_dir_rel, "signoff.json")
    text_rel = os.path.join(report_dir_rel, "signoff.txt")
    with open(os.path.join(root, json_rel), "w", encoding="utf-8") as fh:
        fh.write(report_json_text if report_json_text.endswith("\n") else report_json_text + "\n")
    with open(os.path.join(root, text_rel), "w", encoding="utf-8") as fh:
        fh.write(report_text if report_text.endswith("\n") else report_text + "\n")

    # Re-derive freshness.json's values in place, preserving every hand-written
    # `_comment`/`note` -- same shape as layout/lvs/run_lvs.py --regen-manifest.
    freshness = load_json(root, FRESHNESS_REL)
    cites = manifest_citations(load_json(root, MANIFEST_REL))
    for key, spec in freshness["citations"].items():
        path, pin = cites[key]
        spec["file"] = path
        spec["manifest_pins"] = pin
        envelope = json.load(open(os.path.join(root, path), encoding="utf-8"))
        spec["envelope_asserts"] = {
            field: dotted(envelope, field) for field in spec.get("envelope_asserts", {})
        }
        spec["artifacts"] = {
            artifact: sha256(os.path.join(root, artifact))
            for artifact in spec.get("artifacts", {})
        }
    freshness["expected_rows"] = {
        row_key(item): {"status": item.get("status"), "reason": item.get("reason")}
        for item in report["items"]
    }
    freshness["report"] = {
        "record_id": rec_id,
        "json": json_rel,
        "text": text_rel,
        "sha256": sha256(os.path.join(root, json_rel)),
        "tier": report.get("tier"),
        "t1_item_count": report.get("t1_item_count"),
        "t1_met_count": report.get("t1_met_count"),
        "graded_by": report.get("build", {}).get("version"),
    }
    with open(os.path.join(root, FRESHNESS_REL), "w", encoding="utf-8") as fh:
        json.dump(freshness, fh, indent=2)
        fh.write("\n")

    print(f"wrote {json_rel}")
    print(f"wrote {text_rel}")
    print(f"updated {FRESHNESS_REL}")
    print(
        f"T1: {report.get('t1_met_count')}/{report.get('t1_item_count')} rows met, "
        f"tier={report.get('tier')!r}"
    )
    print(
        f"\nNow write the evidence record: {RECORDS_REL}/{rec_id}.md "
        "(see signoff/README.md for what a record must state)."
    )
    return EXIT_OK


# --------------------------------------------------------------------------
# --selftest (the negative control)
# --------------------------------------------------------------------------


def _overlay(root: str, dest: str) -> None:
    """Copy exactly the files `--check` reads into a scratch repo root."""
    manifest = load_json(root, MANIFEST_REL)
    freshness = load_json(root, FRESHNESS_REL)
    wanted = [MANIFEST_REL, FRESHNESS_REL, TOOLCHAIN_REL, freshness["report"]["json"]]
    for spec in freshness["citations"].values():
        wanted.append(spec["file"])
        wanted.extend(spec.get("artifacts", {}))
    wanted.extend(path for path, _ in manifest_citations(manifest).values())
    for rel in sorted(set(wanted)):
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(root, rel), target)


def _mutate_json(path: str, mutate) -> None:
    doc = json.load(open(path, encoding="utf-8"))
    mutate(doc)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)


def selftest(root: str) -> int:
    """Prove `--check` fails on a tampered input instead of passing vacuously.

    `sim/selftest.sh` stage 4 makes the same argument for the corner sweeps:
    a check nobody has ever seen fail is not evidence that it can.
    """
    freshness = load_json(root, FRESHNESS_REL)
    first_key = sorted(freshness["citations"])[0]
    first = freshness["citations"][first_key]
    first_artifact = sorted(first.get("artifacts", {}))[0]

    cases = []

    def case(name, apply):
        cases.append((name, apply))

    case(
        "a cited artifact's bytes changed (the DRC/LVS-rot case)",
        lambda d: open(os.path.join(d, first_artifact), "ab").write(b"\x00"),
    )
    case(
        "a cited envelope's own status changed",
        lambda d: _mutate_json(
            os.path.join(d, first["file"]), lambda doc: doc.update({"status": "tampered"})
        ),
    )
    case(
        "the committed report's row verdict changed",
        lambda d: _mutate_json(
            os.path.join(d, freshness["report"]["json"]),
            lambda doc: doc["items"][0].update({"status": "met", "reason": None}),
        ),
    )
    case(
        "the manifest cites a different file than the report was graded on",
        lambda d: _mutate_json(
            os.path.join(d, MANIFEST_REL),
            lambda doc: doc["evidence"].update({"9": "signoff/toolchain.json"}),
        ),
    )
    case(
        "upstream's T1 checklist text moved (source_doc_content_hash)",
        lambda d: _mutate_json(
            os.path.join(d, TOOLCHAIN_REL),
            lambda doc: doc.update({"source_doc_content_hash": "sha256:moved"}),
        ),
    )

    failures = []
    with tempfile.TemporaryDirectory(prefix="signoff-selftest-") as tmp:
        clean = os.path.join(tmp, "clean")
        _overlay(root, clean)
        if check(clean, verbose=False):
            failures.append("control: an untampered overlay must PASS --check, and did not")
        else:
            print("  [ok] control: untampered overlay passes --check")
        for name, apply in cases:
            sandbox = os.path.join(tmp, f"case{len(failures)}-{abs(hash(name)) % 10**6}")
            _overlay(root, sandbox)
            apply(sandbox)
            if not check(sandbox, verbose=False):
                failures.append(f"NOT CAUGHT: {name}")
            else:
                print(f"  [ok] caught: {name}")

    if failures:
        for line in failures:
            print(f"  [FAIL] {line}")
        print("\nsignoff --selftest FAILED: --check does not catch what it claims to")
        return EXIT_MISMATCH
    print(f"\nsignoff --selftest OK: {len(cases)} tampered inputs, all caught")
    return EXIT_OK


# --------------------------------------------------------------------------


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Grade this block against the T1 evidence checklist and keep the "
            "committed verdict honest. See signoff/README.md."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="re-derive the committed verdict's inputs (stdlib only; what CI runs)",
    )
    mode.add_argument(
        "--regen",
        action="store_true",
        help="re-run the pinned `klt signoff` and mint a new committed report",
    )
    mode.add_argument(
        "--selftest",
        action="store_true",
        help="prove --check fails on tampered inputs (negative control)",
    )
    parser.add_argument("--klt", help="path to the pinned `klt` (default: $PATH)")
    args = parser.parse_args(argv)

    try:
        if args.regen:
            return regen(REPO_ROOT, args.klt)
        if args.selftest:
            return selftest(REPO_ROOT)
        print("signoff --check: re-deriving the committed T1 verdict's inputs")
        failures = check(REPO_ROOT)
        if failures:
            print("")
            for line in failures:
                print(f"  [FAIL] {line}")
            print(f"\nsignoff --check FAILED ({len(failures)} problems)")
            return EXIT_MISMATCH
        print("\nsignoff --check OK")
        return EXIT_OK
    except ToolingError as exc:
        print(f"tooling error: {exc}", file=sys.stderr)
        return EXIT_TOOLING


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
