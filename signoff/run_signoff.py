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
  * the committed report agrees with the manifest (same block/kind, and --
    row by row -- the same cited file and the same pinned hash the grader
    actually read) and with the toolchain pin (same `klt` build, same
    checklist-document hash);
  * every rendered row's `status`/`reason` matches the expectation recorded
    beside it -- including the UNMET ones. A row silently flipping to `met`
    is as much a drift signal as one flipping to `unmet`;
  * every citation tagged as naming the CURRENT record, in `signoff/README.md`
    AND in the repo-root `README.md` (`README_CURRENT_RECORD_FILES`), really
    names the record the committed report belongs to, and that record is the
    tip of the `Supersedes` chain -- so a "Current verdict" pointer cannot
    quietly lag a re-grade (issue #397, where `signoff/README.md`'s lagged
    two; issue #399, where the repo-root README named the same drift one
    file over).

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

#: Every file whose "Current verdict" pointer `--check` step 6 machine-checks
#: against `signoff/freshness.json`'s `report.record_id`. Started as just
#: `signoff/README.md` (issue #397); the repo-root `README.md` cites the same
#: record one file over and drifted the same way, unnoticed for the same
#: reason (issue #399) -- so this is a tuple, not a single constant, and step
#: 6 below loops over it rather than re-deriving a second bespoke check.
README_CURRENT_RECORD_FILES = ("signoff/README.md", "README.md")

#: Tags a citation, in any file listed in `README_CURRENT_RECORD_FILES`, that
#: must name the CURRENT record -- the one the committed report belongs to.
#: `--check` asserts every tagged citation against `signoff/freshness.json`'s
#: `report.record_id`, so each "Current verdict" pointer is machine-checked
#: instead of hand-maintained (issue #397: `signoff/README.md`'s had lagged
#: two re-grades, and stayed accidentally true only because neither re-grade
#: moved a row; issue #399: the repo-root README named the same stale record
#: one file over). An HTML comment renders as
#: nothing, so it costs a reader nothing; put it at the END of the line
#: BEFORE the citation -- a comment on a line of its own would interrupt the
#: paragraph it sits in.
#:
#: Only an occurrence that ENDS a line counts (`_README_MARKER_RE`): the
#: README has to document the marker in prose as well as use it, and a
#: sentence that names it mid-line is documentation, not a tagged citation.
README_CURRENT_MARKER = "<!-- signoff:current-record -->"
_README_MARKER_RE = re.compile(re.escape(README_CURRENT_MARKER) + r"[ \t]*\n")

#: How many such markers each of `README_CURRENT_RECORD_FILES` must carry.
#: Without a floor the check goes vacuous the moment a marker is dropped.
#: `signoff/README.md` carries two: the "Current verdict" block at the top
#: and the per-row-reasoning paragraph that names the same record again.
#: `README.md` carries one: the "Evidence tier" section's single citation.
#: A per-file floor, not one global count, because the two files' citation
#: counts are independent facts about each file's own prose -- one file
#: dropping a paragraph must not silently lower the other's bar. Changing
#: either number is a reviewed change, exactly like removing one of the
#: `--selftest` controls below.
README_CURRENT_MARKER_MIN = {
    "signoff/README.md": 2,
    "README.md": 1,
}

#: A record id: `<YYYYmmdd-HHMMSS>-<short sha>`, as minted by `record_id()`.
_RECORD_ID_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{7,40}")

#: A `records/<record-id>.md` link target, as `signoff/README.md` writes it.
_RECORD_CITATION_RE = re.compile(r"records/(\d{8}-\d{6}-[0-9a-f]{7,40})\.md")

#: A record's `**Supersedes:**` header line. Anchored at line start so the
#: prose `**Supersedes**.` every record closes with (no colon, no link) is
#: not mistaken for a claim about the chain.
_SUPERSEDES_RE = re.compile(
    r"^\*\*Supersedes:\*\*\s*\[`(\d{8}-\d{6}-[0-9a-f]{7,40})`\]", re.MULTILINE
)


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


def record_successors(root: str) -> dict:
    """`{superseded record id: [ids of the records that supersede it]}`.

    Read from the `**Supersedes:**` header line of every
    `signoff/records/<record-id>.md`. A record absent from this mapping is a
    TIP of the chain: nothing on file claims to replace it. `records/` is
    append-only, so this is the only place the ordering is written down --
    filenames sort by mint time, which is not the same thing (records minted
    on parallel branches fork the chain, and two of this repo's early
    records are still leaves of such a fork).
    """
    records_dir = os.path.join(root, RECORDS_REL)
    out: dict = {}
    for name in sorted(os.listdir(records_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(records_dir, name), encoding="utf-8") as fh:
            text = fh.read()
        for match in _SUPERSEDES_RE.finditer(text):
            out.setdefault(match.group(1), []).append(name[: -len(".md")])
    return out


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
    """`{item key: citation}` from a block manifest, where `citation` is
    `(file, content_hash or None)` for an ordinary item, or a *list* of that
    same per-part shape for a **compound** item -- today, only T1 item 11's
    per-partition entries, which `klt signoff --manifest` accepts as a JSON
    array of ordinary evidence entries rather than a single one
    (`_normalize_evidence_parts`, klayout-tools issue #2025): the `klt erc`
    supply run, the LVS report item 4 also cites, and (for an RTL-flow
    digital partition) the `klt place-and-route` response.

    Only the file-backed entry shapes `klt signoff` documents are handled --
    a bare path string, or `{"file": ..., "content_hash": ...}`, either bare
    or as an element of a compound item's list. This repo cites no
    command-backed entries (they would re-run a tool `--check` has no way to
    re-run), and an unrecognised shape is an error rather than something to
    skip past.
    """
    out = {}
    for key, entry in (manifest.get("evidence") or {}).items():
        if isinstance(entry, list):
            if not entry:
                raise ToolingError(
                    f"manifest evidence entry {key!r} is an empty list -- a "
                    "compound citation (item 11) must name at least one part"
                )
            out[key] = [_manifest_citation_part(key, part) for part in entry]
        else:
            out[key] = _manifest_citation_part(key, entry)
    return out


def _manifest_citation_part(key: str, entry) -> tuple:
    """One element of `manifest_citations()`'s output -- `(file, content_hash
    or None)` for a single file-backed manifest entry. Split out so a
    compound item's list can normalize each part through exactly the same
    rule an ordinary item's bare entry goes through.
    """
    if isinstance(entry, str):
        return (entry, None)
    if isinstance(entry, dict) and "file" in entry:
        return (entry["file"], entry.get("content_hash"))
    raise ToolingError(
        f"manifest evidence entry {key!r} is not a file-backed entry; "
        "signoff/run_signoff.py only understands the shapes this repo "
        "actually uses (see manifest_citations())"
    )


def _check_citation_agreement(
    label: str, path: str, pin: str | None, spec: dict, fail, ok
) -> None:
    """Step 1 of `check()` for one `(file, content_hash)` citation against
    the freshness entry declared for it -- shared between an ordinary item's
    single citation and one part of a compound item's list, so the two paths
    can never drift apart on what "agrees" means.
    """
    if spec["file"] != path:
        fail(f"{label}: manifest cites {path}, freshness declares {spec['file']}")
        return
    if spec.get("manifest_pins") != pin:
        fail(
            f"{label}: manifest pins content_hash {pin!r}, "
            f"freshness declares {spec.get('manifest_pins')!r}"
        )
    if spec.get("manifest_pins") is None and not spec.get("manifest_pin_note"):
        fail(
            f"{label}: citation carries no content_hash and no "
            "manifest_pin_note saying why -- an unpinned citation is only "
            "acceptable with a recorded reason"
        )
    # The symmetric guard to the one above: `artifacts` is the rot
    # detector, and `_check_envelope_and_artifacts` iterates whatever is
    # there -- so a citation added with `"artifacts": {}` would get zero
    # hash coverage while still printing `[ok]`. Make the absence declared,
    # never silent.
    if not spec.get("artifacts") and not spec.get("artifacts_note"):
        fail(
            f"{label}: citation pins no artifacts and carries no "
            "artifacts_note saying why -- a citation whose evidence rests "
            "on no repo bytes is only acceptable with a recorded reason"
        )
    ok(f"{label}: manifest and freshness agree on {path}")


def _check_envelope_and_artifacts(root: str, label: str, spec: dict, fail, ok) -> None:
    """Steps 2-3 of `check()` for one citation spec: the cited envelope still
    says what it said, and every repo artifact behind it still hashes the
    same. Shared between an ordinary item's single spec and one part of a
    compound item's list, for the same reason `_check_citation_agreement` is.
    """
    envelope_path = os.path.join(root, spec["file"])
    if not os.path.exists(envelope_path):
        fail(f"{label}: cited envelope is missing: {spec['file']}")
        return
    try:
        envelope = json.load(open(envelope_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"{label}: cited envelope is unreadable: {spec['file']} ({exc})")
        return
    for field, expected in (spec.get("envelope_asserts") or {}).items():
        try:
            actual = dotted(envelope, field)
        except KeyError:
            fail(f"{label}: {spec['file']} no longer carries `{field}`")
            continue
        if actual != expected:
            fail(
                f"{label}: {spec['file']} `{field}` is {actual!r}, "
                f"pinned as {expected!r}"
            )
    ok(f"{label}: envelope fields match ({len(spec.get('envelope_asserts') or {})} pinned)")

    for artifact, expected_hash in (spec.get("artifacts") or {}).items():
        artifact_path = os.path.join(root, artifact)
        if not os.path.exists(artifact_path):
            fail(f"{label}: pinned artifact is missing: {artifact}")
            continue
        actual_hash = sha256(artifact_path)
        if actual_hash != expected_hash:
            fail(
                f"{label}: {artifact} has changed since this evidence "
                f"was recorded ({actual_hash} != pinned {expected_hash}) -- "
                "re-run the flow that produced "
                f"{spec['file']}, then `signoff/run_signoff.py --regen`"
            )
        else:
            ok(f"{label}: {artifact} unchanged")


def _find_citation_span(readme: str, pos: int):
    """The `(start, end)` span of the citation immediately after a
    current-record marker at `readme[pos]`, or `None` if there is none.

    Two shapes are accepted: `signoff/README.md` links the record
    (`` [`<id>`](records/<id>.md) ``); the repo-root `README.md` names it as a
    bare `` `<id>` `` with no link (issue #399). Whichever pattern's match
    starts first, from `pos` onward, is the citation -- so a bare id that
    happens to precede a later link on the same line is not skipped past.
    """
    cite = _RECORD_CITATION_RE.search(readme, pos)
    bare = _RECORD_ID_RE.search(readme, pos)
    if cite and (not bare or cite.start() <= bare.start()):
        return (cite.start(), cite.end())
    if bare:
        return (bare.start(), bare.end())
    return None


def _check_readme_current_record(root: str, freshness: dict, fail, ok) -> None:
    """Step 6 of `check()`: every file in `README_CURRENT_RECORD_FILES`
    points a human at the record that is actually current.

    Steps 1-5 re-derive the committed report; none of them reads the files a
    human reads first. Issue #397 is what that costs: `signoff/README.md`'s
    "Current verdict" pointer named a record TWO re-grades old, and nothing
    failed -- it stayed accidentally true only because neither intervening
    re-grade moved a row. Issue #399 found the same defect one file over, in
    the repo-root `README.md`, for the same reason: a directory whose whole
    argument is "provenance travels with every number" cannot have either of
    its front doors hand-maintained.

    Two assertions, because either alone can be satisfied by a wrong answer:

      * every citation tagged `README_CURRENT_MARKER`, in every file listed
        in `README_CURRENT_RECORD_FILES`, names `freshness.json`'s
        `report.record_id` -- the record the committed report (the one steps
        1-5 just re-derived) belongs to; and
      * that record is a TIP of the `Supersedes` chain, i.e. no other record
        claims to supersede it. This catches the inverse mistake: a `--regen`
        whose record was written but whose `freshness.json` was not refreshed
        would otherwise agree with a README that names the same stale record.

    The second assertion is a fact about the committed report, not about any
    one file, so it is checked once rather than once per file.
    """
    current = (freshness.get("report") or {}).get("record_id")
    if not current:
        fail(
            "signoff/freshness.json's `report` block records no `record_id`, "
            "so there is nothing to check the current-record pointer(s) "
            "against -- re-run `--regen`"
        )
        return

    record_rel = f"{RECORDS_REL}/{current}.md"
    if not os.path.exists(os.path.join(root, record_rel)):
        fail(
            f"the committed report is record {current}, but {record_rel} does "
            "not exist -- a `--regen` without a record is half a change (see "
            "signoff/README.md's \"Changing the verdict\")"
        )
        return

    superseded_by = record_successors(root).get(current) or []
    if superseded_by:
        fail(
            f"signoff/freshness.json's committed report is record {current}, "
            f"which {', '.join(sorted(superseded_by))} already supersedes -- "
            "the committed verdict is behind the records on file; re-run "
            "`--regen` (and write its record) rather than editing either"
        )
    else:
        ok(f"record {current}: tip of the Supersedes chain (nothing supersedes it)")

    for readme_rel in README_CURRENT_RECORD_FILES:
        readme_path = os.path.join(root, readme_rel)
        if not os.path.exists(readme_path):
            fail(f"{readme_rel} is missing -- it is the verdict's front door")
            continue
        with open(readme_path, encoding="utf-8") as fh:
            readme = fh.read()

        marker_min = README_CURRENT_MARKER_MIN[readme_rel]
        marks = [m.end() for m in _README_MARKER_RE.finditer(readme)]
        if len(marks) < marker_min:
            fail(
                f"{readme_rel} carries {len(marks)} line-ending "
                f"`{README_CURRENT_MARKER}` marker(s), fewer than the "
                f"{marker_min} it must "
                "have -- a dropped marker silently un-checks the citation it "
                "tagged. If a citation was deliberately removed, lower "
                f"README_CURRENT_MARKER_MIN[{readme_rel!r}] in the same change"
            )
        for pos in marks:
            span = _find_citation_span(readme, pos)
            if not span:
                line = readme.count("\n", 0, pos) + 1
                fail(
                    f"{readme_rel}:{line}: a `{README_CURRENT_MARKER}` marker "
                    "is followed by no `records/<record-id>.md` link and no "
                    "bare `<record-id>` citation -- the marker must sit on "
                    "the line before the citation it tags"
                )
                continue
            start, end = span
            line = readme.count("\n", 0, start) + 1
            # Everything between the marker and the end of the citation: the
            # display text `[`<id>`]` as well as the link target (or, for a
            # bare citation, just the id itself), so a citation whose visible
            # id and link disagree fails too.
            named = sorted(set(_RECORD_ID_RE.findall(readme[pos:end])))
            wrong = [rid for rid in named if rid != current]
            if wrong:
                fail(
                    f"{readme_rel}:{line} names record(s) {', '.join(wrong)} "
                    f"as current, but the committed report is {current} -- "
                    "re-point the citation (this is the drift issue #397 "
                    "recorded, and issue #399 for the repo-root README)"
                )
            else:
                ok(f"{readme_rel}:{line}: current-record citation names {current}")


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
        entry = cites[key]
        spec = declared[key]
        if isinstance(entry, list):
            parts_spec = spec.get("parts")
            if not isinstance(parts_spec, list) or len(parts_spec) != len(entry):
                fail(
                    f"item {key}: manifest cites {len(entry)} compound parts, "
                    "freshness declares "
                    f"{len(parts_spec) if isinstance(parts_spec, list) else 'no'} "
                    "parts"
                )
                continue
            for idx, (path, pin) in enumerate(entry):
                _check_citation_agreement(
                    f"item {key} part {idx} ({parts_spec[idx].get('role', '?')})",
                    path,
                    pin,
                    parts_spec[idx],
                    fail,
                    ok,
                )
        else:
            path, pin = entry
            _check_citation_agreement(f"item {key}", path, pin, spec, fail, ok)

    # 2. every cited envelope still says what it said, and (3.) the repo
    #    artifacts behind it still hash the same ---------------------------
    for key in sorted(declared):
        spec = declared[key]
        parts_spec = spec.get("parts")
        if isinstance(parts_spec, list):
            for idx, part_spec in enumerate(parts_spec):
                _check_envelope_and_artifacts(
                    root,
                    f"item {key} part {idx} ({part_spec.get('role', '?')})",
                    part_spec,
                    fail,
                    ok,
                )
        else:
            _check_envelope_and_artifacts(root, f"item {key}", spec, fail, ok)

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

    # The text rendering beside it is committed for humans to read as a diff,
    # so it is pinned for the same reason the JSON is: an edited `signoff.txt`
    # is a hand-written verdict wearing the grader's voice.
    text_path = os.path.join(root, report_spec["text"])
    if not os.path.exists(text_path):
        fail(f"committed text rendering is missing: {report_spec['text']}")
    elif sha256(text_path) != report_spec["text_sha256"]:
        fail(
            f"{report_spec['text']} has been edited since it was minted "
            "(sha256 mismatch) -- it is the `--regen` rendering of "
            f"{report_spec['json']}, never hand-edited"
        )

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

    # 4b. the report was graded on the citations the manifest names NOW --
    #
    # Steps 1-3 assert the manifest against the repo-side pins, and step 4
    # asserts the report against the manifest's block/kind and the toolchain
    # pin. None of them asks the question a reader assumes is asked: is the
    # committed verdict about the SAME FILES this manifest cites today?
    #
    # Without this, the one hand-edit the manifest's `_comment` warns
    # against -- re-point a citation, update freshness.json to match, skip
    # `--regen` -- passes `--check` while the committed report still shows
    # that row graded on the file that was replaced. On a per-partition
    # manifest that is worse than a stale number: it lets the DIGITAL
    # partition's DRC envelope stand as the ANALOG partition's evidence,
    # the exact conflation the per-partition keying exists to prevent.
    #
    # Nothing new has to be recorded to close it. Every graded row in the
    # report already carries the `citation.file` and `citation.content_hash`
    # the grader read at grading time; this compares them.
    graded = set()
    for item in report.get("items", []):
        cit = item.get("citation")
        if not cit or not cit.get("file"):
            continue
        row = row_key(item)
        key = row.split("#", 1)[1] if "#" in row else row
        graded.add(key)
        if key not in cites:
            fail(
                f"row {row}: report was graded on {cit['file']}, which the "
                "manifest no longer cites at all"
            )
            continue
        want = cites[key]
        if isinstance(want, list):
            # A compound item's `citation` leads with its first part (see
            # klayout-tools' `_grade_power_delivery`) and carries every part
            # under `citation["parts"]`, in the same `(erc, lvs,
            # place-and-route)` order the manifest's list must follow for
            # this comparison to be meaningful part-by-part.
            cit_parts = cit.get("parts")
            if not isinstance(cit_parts, list) or len(cit_parts) != len(want):
                fail(
                    f"row {row}: report's citation carries "
                    f"{len(cit_parts) if isinstance(cit_parts, list) else 'no'} "
                    f"compound parts, manifest names {len(want)} for {key}"
                )
                continue
            mismatched = False
            for idx, (want_file, want_pin) in enumerate(want):
                part_cit = cit_parts[idx]
                if part_cit.get("file") != want_file:
                    fail(
                        f"row {row} part {idx}: report was graded on "
                        f"{part_cit.get('file')}, manifest now cites "
                        f"{want_file} -- a citation was re-pointed without "
                        "`--regen`, so the committed verdict describes a "
                        "different file"
                    )
                    mismatched = True
                elif part_cit.get("content_hash") != want_pin:
                    fail(
                        f"row {row} part {idx}: report's citation pins "
                        f"{part_cit.get('content_hash')!r}, manifest pins "
                        f"{want_pin!r} for the same file"
                    )
                    mismatched = True
            if not mismatched:
                ok(f"row {row}: report and manifest cite the same {len(want)} compound parts")
            continue
        want_file, want_pin = want
        if cit["file"] != want_file:
            fail(
                f"row {row}: report was graded on {cit['file']}, manifest now "
                f"cites {want_file} -- a citation was re-pointed without "
                "`--regen`, so the committed verdict describes a different file"
            )
        elif cit.get("content_hash") != want_pin:
            fail(
                f"row {row}: report's citation pins "
                f"{cit.get('content_hash')!r}, manifest pins {want_pin!r} for "
                "the same file"
            )
        else:
            ok(f"row {row}: report and manifest cite the same {want_file}")

    # A manifest citation whose row renders NO citation cannot be compared
    # this way. Item 7 is the live case: the grader renders
    # `unmet`/`check_failed` with `citation: null`, so the report never
    # records which file it read, and re-pointing that citation is invisible
    # here. The hole is real, so it is declared rather than skipped in
    # silence -- same discipline as `manifest_pin_note` above.
    for key in sorted(set(cites) - graded):
        if not (declared.get(key) or {}).get("report_citation_note"):
            fail(
                f"item {key}: the manifest cites it, but the committed report "
                "renders no citation for that row, so the two cannot be "
                "compared -- freshness.json must carry a report_citation_note "
                "saying why"
            )
        else:
            ok(
                f"item {key}: report renders no citation for this row "
                "(uncomparable, declared)"
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

    # 6. the README points a human at the record that is actually current ---
    _check_readme_current_record(root, freshness, fail, ok)

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
        entry = cites[key]
        parts_spec = spec.get("parts")
        if isinstance(parts_spec, list):
            if not isinstance(entry, list) or len(entry) != len(parts_spec):
                raise ToolingError(
                    f"signoff/freshness.json citation {key!r} declares "
                    f"{len(parts_spec)} parts, but the manifest now cites "
                    f"{len(entry) if isinstance(entry, list) else 'a single'} "
                    "-- the manifest and freshness.json structures must "
                    "agree (by hand) before --regen can refresh their hashes"
                )
            for part_spec, (path, pin) in zip(parts_spec, entry):
                part_spec["file"] = path
                part_spec["manifest_pins"] = pin
                envelope = json.load(open(os.path.join(root, path), encoding="utf-8"))
                part_spec["envelope_asserts"] = {
                    field: dotted(envelope, field)
                    for field in part_spec.get("envelope_asserts", {})
                }
                part_spec["artifacts"] = {
                    artifact: sha256(os.path.join(root, artifact))
                    for artifact in part_spec.get("artifacts", {})
                }
            continue
        path, pin = entry
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
        "text_sha256": sha256(os.path.join(root, text_rel)),
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
    wanted = [
        MANIFEST_REL,
        FRESHNESS_REL,
        TOOLCHAIN_REL,
        # `check()`'s step 6 reads each README's current-record pointer and
        # every record's `Supersedes:` line, so the overlay must carry them
        # or the untampered control below would fail for the wrong reason.
        *README_CURRENT_RECORD_FILES,
        freshness["report"]["json"],
        freshness["report"]["text"],
    ]
    wanted.extend(
        f"{RECORDS_REL}/{name}"
        for name in os.listdir(os.path.join(root, RECORDS_REL))
        if name.endswith(".md")
    )
    for spec in freshness["citations"].values():
        parts_spec = spec.get("parts")
        if isinstance(parts_spec, list):
            for part_spec in parts_spec:
                wanted.append(part_spec["file"])
                wanted.extend(part_spec.get("artifacts", {}))
        else:
            wanted.append(spec["file"])
            wanted.extend(spec.get("artifacts", {}))
    for entry in manifest_citations(manifest).values():
        if isinstance(entry, list):
            wanted.extend(path for path, _ in entry)
        else:
            wanted.append(entry[0])
    for rel in sorted(set(wanted)):
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(root, rel), target)


def _rewrite_readme(root: str, readme_rel: str, transform) -> None:
    """Rewrite a scratch overlay's `readme_rel` (one of
    `README_CURRENT_RECORD_FILES`) through `transform`."""
    path = os.path.join(root, readme_rel)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(transform(text))


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
    # Skip a compound (list-shaped, "11.analog"-style) citation here -- it
    # carries no top-level `artifacts`/`file` of its own (see `parts`
    # below), and it can sort before an ordinary key ("11.analog" < "3.analog"
    # as a string). The compound shape gets its own dedicated tamper case
    # further down.
    first_key = next(
        k for k in sorted(freshness["citations"]) if "artifacts" in freshness["citations"][k]
    )
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
        "the committed text rendering was hand-edited (signoff.txt)",
        lambda d: open(
            os.path.join(d, freshness["report"]["text"]), "a", encoding="utf-8"
        ).write("T1: 22/22 items met\n"),
    )
    case(
        "the manifest grew a citation freshness.json does not declare",
        lambda d: _mutate_json(
            os.path.join(d, MANIFEST_REL),
            lambda doc: doc["evidence"].update({"9": "signoff/toolchain.json"}),
        ),
    )

    # The case the #331 review found `--check` could not catch: re-point an
    # EXISTING citation at the other partition's envelope and update
    # freshness.json consistently, exactly as the manifest's `_comment`
    # warns against. Every repo-side pin then agrees with itself, so steps
    # 1-3 see nothing wrong; only the committed report still remembers what
    # the row was actually graded on. Deliberately distinct from the case
    # above, which is a citation-SET mismatch rather than a same-item swap.
    swap_from, swap_to = "3.analog", "3.digital"
    copied = ("file", "manifest_pins", "envelope_asserts", "artifacts")

    def _repoint_citation(d):
        _mutate_json(
            os.path.join(d, MANIFEST_REL),
            lambda doc: doc["evidence"].update(
                {swap_from: dict(doc["evidence"][swap_to])}
            ),
        )
        _mutate_json(
            os.path.join(d, FRESHNESS_REL),
            lambda doc: doc["citations"][swap_from].update(
                {k: dict(doc["citations"][swap_to][k])
                 if isinstance(doc["citations"][swap_to][k], dict)
                 else doc["citations"][swap_to][k]
                 for k in copied}
            ),
        )

    case(
        f"an existing citation ({swap_from}) re-pointed at the other "
        f"partition's envelope ({swap_to}), with freshness.json updated to "
        "match",
        _repoint_citation,
    )
    case(
        "upstream's T1 checklist text moved (source_doc_content_hash)",
        lambda d: _mutate_json(
            os.path.join(d, TOOLCHAIN_REL),
            lambda doc: doc.update({"source_doc_content_hash": "sha256:moved"}),
        ),
    )

    # Item 8's generic envelope is the one citation `klt signoff` CANNOT
    # freshness-check for itself (issue #339). For every native kind the
    # grader knows which field names the input it consumed, so it re-hashes
    # the artifact and reports `input_verified: true|false`. A `generic`
    # envelope's author picks their own field names -- so the grader reports
    # `input_verified: null` and the manifest's pinned hash is only ever
    # compared against the envelope's OWN claim about the document.
    #
    # That makes "edit sim/characterization-summary.md, leave the envelope
    # and the manifest alone" the one rot path where the grader would go on
    # rendering `met` indefinitely. `--check`'s `artifacts` re-hash is what
    # closes it, and signoff/evidence/README.md plus the wrapped document
    # both state outright that editing it without `--regen` turns CI red.
    # THAT IS A CLAIM, so it gets a control: no claim without a testbench
    # (CLAUDE.md). Deliberately distinct from the first case above, which
    # tampers with whatever citation sorts first (a DRC/LVS-rot case with a
    # native envelope behind it); this one is keyed on the generic citation
    # specifically and fails loudly if item 8 ever stops pinning a document.
    generic_keys = sorted(
        k
        for k, spec in freshness["citations"].items()
        if (spec.get("envelope_asserts") or {}).get("kind") == "generic"
    )
    if not generic_keys:
        raise ToolingError(
            "no `generic`-kind citation found in signoff/freshness.json -- "
            "this selftest's item-8 control has nothing to tamper with. If "
            "item 8's citation was deliberately removed, remove this control "
            "in the same change rather than leaving it silently vacuous."
        )
    for gkey in generic_keys:
        gdoc = sorted((freshness["citations"][gkey].get("artifacts") or {}))
        if not gdoc:
            raise ToolingError(
                f"generic citation {gkey!r} pins no artifacts -- the record it "
                "wraps is exactly what `--check` has to re-hash, since the "
                "grader cannot"
            )
        case(
            f"the record behind generic citation {gkey} ({gdoc[0]}) was "
            "edited without `--regen`",
            lambda d, _p=gdoc[0]: open(os.path.join(d, _p), "a", encoding="utf-8").write(
                "\n<!-- tampered by --selftest -->\n"
            ),
        )

    # Item 11's compound (list-shaped) citation control (issue #347). Every
    # tamper case above corrupts a single-artifact citation; none of them
    # exercises the list-decoding path `manifest_citations()`/`check()` gained
    # for a compound item, so a bug specific to that path -- e.g. comparing
    # only the first part's pin, or silently dropping a part -- could pass
    # every case above. This corrupts one part's `content_hash` IN THE
    # MANIFEST while leaving `signoff/freshness.json`'s own declared pin for
    # that same part untouched, which only the per-part comparison added in
    # `check()`'s step 1 can catch (mirrors the generic-envelope control
    # above: keyed on the compound shape specifically, not on whatever
    # citation happens to sort first).
    compound_keys = sorted(
        k for k, spec in freshness["citations"].items() if isinstance(spec.get("parts"), list)
    )
    if not compound_keys:
        raise ToolingError(
            "no compound (list-shaped) citation found in signoff/freshness.json "
            "-- this selftest's item-11 control has nothing to tamper with. If "
            "item 11's compound citation was deliberately removed, remove this "
            "control in the same change rather than leaving it silently vacuous."
        )
    for ckey in compound_keys:
        parts_spec = freshness["citations"][ckey]["parts"]
        pinned_idx = next(
            (i for i, p in enumerate(parts_spec) if p.get("manifest_pins")), None
        )
        if pinned_idx is None:
            raise ToolingError(
                f"compound citation {ckey!r} pins no content_hash on any part "
                "-- this selftest's compound-tamper control needs at least "
                "one pinned part to corrupt"
            )
        role = parts_spec[pinned_idx].get("role", f"part {pinned_idx}")
        case(
            f"compound citation {ckey} part {pinned_idx} ({role}): "
            "content_hash tampered in the manifest, freshness.json left as "
            "committed",
            lambda d, _k=ckey, _i=pinned_idx: _mutate_json(
                os.path.join(d, MANIFEST_REL),
                lambda doc: doc["evidence"][_k].__setitem__(
                    _i,
                    {**doc["evidence"][_k][_i], "content_hash": "sha256:" + "0" * 64},
                ),
            ),
        )

    # The stale "Current verdict" pointer (issue #397), and its repeat one
    # file over in the repo-root `README.md` (issue #399). Every case above
    # tampers with a machine-written input; these tamper with the files a
    # human reads FIRST, which is how the defect actually occurred both
    # times: a re-grade landed, minted a record and refreshed
    # `freshness.json`, and nobody re-pointed the README. Neither re-grade
    # moved a row, so the stale pointer stayed accidentally true and no
    # check -- not one of the ten above -- had anything to say about it.
    current_record = freshness["report"]["record_id"]
    successors = record_successors(root)
    stale_records = sorted(
        rid for rid, by in successors.items() if current_record in by
    )
    if not stale_records:
        raise ToolingError(
            f"the committed report's record {current_record} supersedes "
            "nothing, so this selftest's stale-pointer control has no stale "
            "record to point at. That is only true of the FIRST record ever "
            "minted; if the chain was deliberately restarted, rewrite this "
            "control rather than leaving it silently vacuous."
        )
    stale_record = stale_records[0]
    for readme_rel in README_CURRENT_RECORD_FILES:
        case(
            f"{readme_rel}'s current-record pointer left on the superseded "
            f"{stale_record} after a re-grade minted {current_record}",
            lambda d, _r=readme_rel, _s=stale_record, _c=current_record: _rewrite_readme(
                d, _r, lambda text: text.replace(_c, _s)
            ),
        )
        case(
            f"{readme_rel}'s current-record marker deleted, leaving a "
            "citation nothing checks",
            lambda d, _r=readme_rel: _rewrite_readme(
                d, _r, lambda text: text.replace(README_CURRENT_MARKER, "", 1)
            ),
        )
    # The inverse of the two cases above, and the control for the second of
    # step 6's two assertions: a README is re-pointed but `freshness.json`
    # still claims a superseded record as the committed report. Without the
    # chain-tip assertion that half of step 6 would be vacuous -- the two
    # files would simply disagree, and only the one being blamed would move.
    # A fact about `freshness.json` alone, not about either README, so one
    # case covers both files' worth of step 6.
    case(
        f"signoff/freshness.json's report.record_id left on the superseded "
        f"{stale_record}",
        lambda d, _s=stale_record: _mutate_json(
            os.path.join(d, FRESHNESS_REL),
            lambda doc: doc["report"].update({"record_id": _s}),
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
