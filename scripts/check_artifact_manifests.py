#!/usr/bin/env python3
"""Stored-evidence manifests: schema guard and hash verifier (issue #636).

New simulation evidence no longer lands in git. Its bytes go to the fleet
artifact store through ``klt artifact put`` (``sim/harness/evidence_store.py``,
``sim/run_store_evidence.py``) and git keeps a **manifest** per run under
``manifests/artifacts/<bench>-<run-id>.manifest.json`` plus the run's Markdown
summary under ``sim/<bench>/``. Evidence bytes are private; manifests are
public (operator decision 1.1, 2026-10-22). This script is the git-side check
of that contract. Two subcommands:

``check --tree REV``
    Reads every manifest committed in ``REV`` (blob contents via git, so a
    sparse working tree does not matter) and fails if one is malformed: wrong
    schema, an unknown or missing field, a ``uri`` that is not the logical
    ``artifact:<key>`` (an ``s3`` bucket uri or any other scheme is refused),
    a key that does not end in the entry's sha256, a ``name`` that is not a
    canonical ``sim/``, ``layout/`` or ``signoff/`` path, or a duplicate
    name. It also fails if any entry's ``name`` is a tracked path in ``REV``,
    or if any tracked file has the sha256 and size of a stored object under
    another name: the point of a manifest is that the bytes are *not*
    committed, so a blob beside its own manifest is the fallback this repo
    forbids. With ``--base REF`` it also fails on any file ADDED since the
    merge base under ``sim/<bench>/corners/``: new raw per-corner output goes
    to the store, and those paths are git-ignored. ``check`` never contacts
    the broker and says so: schema-valid is not hash-verified.

``verify MANIFEST...``
    Fetches every entry through the broker named by ``$KLT_ARTIFACT_BROKER``
    and recomputes its sha256 and size against the manifest and against the
    digest the broker's object key names (the same rules as
    ``klt artifact verify``; this is a stdlib twin so CI and the guard tests
    need no ``klt`` install). Each entry is ``ok``, ``missing``,
    ``size_mismatch``, ``hash_mismatch`` or ``key_mismatch``.

Fail closed. No broker configured, an unreachable broker or a broker refusal
other than "not found" is exit 2, never success and never a schema-only pass.

The broker hands out short-lived presigned URLs. They are bearer credentials:
this script keeps them in memory, never prints, logs or writes them, and
reports a failed transfer by HTTP status only. No URL, host name or bucket is
configured in this repository; the broker URL comes from the environment.

Exit codes: 0 ok; 1 a manifest is invalid or names a committed blob
(``check``) or is unreadable (``verify``); 2 usage, git or broker error;
3 ``verify`` ran and at least one entry is missing or mismatched.

Stdlib only; ``check`` needs ``git`` on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import urlsplit

MANIFEST_DIR = "manifests/artifacts/"
MANIFEST_RE = re.compile(r"^manifests/artifacts/[A-Za-z0-9][A-Za-z0-9._-]*\.manifest\.json$")
RAW_OUTPUT_RE = re.compile(r"^sim/[^/]+/corners/.+")
DIR_FILES_ALLOWED = {"manifests/artifacts/README.md"}
ENV_BROKER = "KLT_ARTIFACT_BROKER"

SCHEMA_VERSION = 1
KIND = "evidence"
REQUIRED = ("sha256", "size", "kind", "producer", "uri")
OPTIONAL = ("name", "media_type")
PRODUCER_FIELDS = ("tool", "version", "loom.repo", "commit")

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
#: The manifest ``uri`` is a logical name only the broker resolves,
#: ``artifact:<key>`` (operator ruling H1, 2AMLogic/2am#5553; klayout-tools
#: ``7e3561f``). It names no storage location; any other scheme is refused.
URI_RE = re.compile(r"^artifact:([^/\s]\S*)$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

BROKER_TIMEOUT_S = 60
TRANSFER_TIMEOUT_S = 600
CHUNK = 1 << 20
MAX_BROKER_BODY = 1 << 20

EXIT_OK, EXIT_INVALID, EXIT_ERROR, EXIT_FAILED = 0, 1, 2, 3


class ToolError(Exception):
    """Git or broker failure: exit 2, fail closed."""


# --------------------------------------------------------------------------
# Manifest schema (mirrors klayout_tools.artifact_store.entry_problems, plus
# this repo's own rules: evidence kind only, a canonical sim/ name, unique
# names, and a uri key that names the producer's repo)
# --------------------------------------------------------------------------


def uri_key(uri: str) -> str | None:
    """The broker key of an ``artifact:<key>`` uri, else ``None``."""
    m = URI_RE.match(uri) if isinstance(uri, str) else None
    return m.group(1) if m else None


def repo_from_key(key: str) -> str | None:
    """``owner/name`` from an ``evidence/<owner>__<name>/...`` key."""
    parts = key.split("/")
    if len(parts) < 3 or parts[0] != "evidence" or parts[1].count("__") != 1:
        return None
    return parts[1].replace("__", "/")


NAME_ROOTS = ("sim/", "layout/", "signoff/")


def canonical_name(name) -> bool:
    return (isinstance(name, str) and name.startswith(NAME_ROOTS)
            and "\\" not in name and "\0" not in name
            and posixpath.normpath(name) == name
            and not {"", ".", ".."} & set(name.split("/")))


def entry_problems(entry) -> list[str]:
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    problems = []
    missing = [f for f in REQUIRED if f not in entry]
    extra = sorted(set(entry) - set(REQUIRED) - set(OPTIONAL))
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if extra:
        problems.append(f"unknown field(s) {', '.join(extra)}")
    sha = entry.get("sha256")
    if not isinstance(sha, str) or not SHA256_RE.match(sha):
        problems.append("sha256 must be 64 lowercase hex digits")
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        problems.append("size must be a positive integer")
    if entry.get("kind") != KIND:
        problems.append(f"kind must be {KIND!r}")
    producer = entry.get("producer")
    if not isinstance(producer, dict) or set(producer) != set(PRODUCER_FIELDS):
        problems.append(f"producer must carry exactly {', '.join(PRODUCER_FIELDS)}")
    else:
        for f in ("tool", "version", "loom.repo"):
            if not isinstance(producer.get(f), str) or not producer[f]:
                problems.append(f"producer.{f} must be a non-empty string")
        if producer.get("commit") is not None and not isinstance(producer["commit"], str):
            problems.append("producer.commit must be a string or null")
    key = uri_key(entry.get("uri"))
    if key is None:
        problems.append("uri must be artifact:<key> (no other scheme)")
    else:
        if key.rsplit("/", 1)[-1] != sha:
            problems.append("uri key does not end in the entry's sha256")
        key_repo = repo_from_key(key)
        if key_repo is None:
            problems.append("uri key is not evidence/<owner>__<name>/...")
        elif isinstance(producer, dict) and producer.get("loom.repo") not in (None, key_repo):
            problems.append("uri key names a different repo than producer.loom.repo")
    if "name" not in entry:
        problems.append("name is required here (the logical repo path of the bytes)")
    elif not canonical_name(entry["name"]):
        problems.append("name must be a canonical relative sim/, layout/ or signoff/ path")
    if "media_type" in entry and not isinstance(entry["media_type"], str):
        problems.append("media_type must be a string")
    return problems


def manifest_problems(manifest) -> list[str]:
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "entries"} \
            or manifest.get("schema_version") != SCHEMA_VERSION \
            or not isinstance(manifest.get("entries"), list):
        return [f"not {{schema_version: {SCHEMA_VERSION}, entries: [...]}}"]
    if not manifest["entries"]:
        return ["has no entries"]
    problems = []
    seen = set()
    for i, entry in enumerate(manifest["entries"]):
        for p in entry_problems(entry):
            problems.append(f"entry {i}: {p}")
        name = entry.get("name") if isinstance(entry, dict) else None
        if isinstance(name, str):
            if name in seen:
                problems.append(f"entry {i}: duplicate name {name!r}")
            seen.add(name)
    return problems


# --------------------------------------------------------------------------
# check: committed manifests in a tree
# --------------------------------------------------------------------------


def git(repo: str, *args: str) -> bytes:
    try:
        p = subprocess.run(["git", "-C", repo, *args], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=False,
                           env={**os.environ, "GIT_NO_LAZY_FETCH": "1"})
    except OSError as exc:
        raise ToolError(f"cannot run git: {exc}") from exc
    if p.returncode != 0:
        raise ToolError(f"git {' '.join(args)} failed: "
                        f"{p.stderr.decode('utf-8', 'replace').strip()}")
    return p.stdout


def tracked_paths(repo: str, tree: str) -> dict[str, tuple[str, str, int]]:
    """``{path: (mode, type, size)}`` of every entry in ``tree`` (recursive)."""
    out = {}
    for rec in git(repo, "ls-tree", "-r", "-l", "-z", tree).split(b"\0"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        mode, typ, _oid, size = meta.decode().split()
        out[name.decode("utf-8", "surrogateescape")] = (
            mode, typ, int(size) if size.isdigit() else -1)
    return out


def added_raw_outputs(repo: str, base: str, rev: str) -> list[str]:
    """Files added since the merge base of ``base`` and ``rev`` that are raw
    per-corner output, which must go to the store instead."""
    if base.startswith("-"):
        raise ToolError(f"invalid revision {base!r}")
    out = git(repo, "diff", "--name-only", "--diff-filter=A", "-z",
              f"{base}...{rev}", "--").decode("utf-8", "surrogateescape")
    return sorted(p for p in out.split("\0") if RAW_OUTPUT_RE.match(p))


def check(repo: str, rev: str, base: str | None = None) -> int:
    if rev.startswith("-"):
        raise ToolError(f"invalid revision {rev!r}")
    tree = git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options",
               f"{rev}^{{tree}}").decode().strip()
    if not tree:
        raise ToolError(f"revision {rev!r} is unavailable")
    paths = tracked_paths(repo, tree)
    errors: list[str] = []
    manifests = 0
    entries = 0
    stored: dict[tuple[str, int], tuple[str, str]] = {}
    for path in sorted(p for p in paths if p.startswith(MANIFEST_DIR)):
        mode, typ, _size = paths[path]
        if path in DIR_FILES_ALLOWED:
            continue
        if not MANIFEST_RE.match(path) or typ != "blob" or mode == "120000":
            errors.append(f"{path}: only <bench>-<run-id>.manifest.json files (and "
                          "README.md) belong in manifests/artifacts/")
            continue
        try:
            manifest = json.loads(git(repo, "show", f"{tree}:{path}").decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            errors.append(f"{path}: not valid JSON: {exc}")
            continue
        problems = manifest_problems(manifest)
        errors += [f"{path}: {p}" for p in problems]
        if problems:
            continue
        manifests += 1
        for entry in manifest["entries"]:
            entries += 1
            stored[(entry["sha256"], entry["size"])] = (path, entry["name"])
            if entry["name"] in paths:
                errors.append(
                    f"{path}: {entry['name']} is committed in the tree; stored "
                    "evidence bytes must not also be committed (no blob fallback)")
    # The same bytes under another name: only files of a stored object's exact
    # size are read, so this stays cheap on a large evidence tree.
    sizes = {size for _, size in stored}
    for tpath in sorted(paths):
        mode, typ, size = paths[tpath]
        if typ != "blob" or mode == "120000" or size not in sizes \
                or tpath.startswith(MANIFEST_DIR):
            continue
        digest = hashlib.sha256(git(repo, "show", f"{tree}:{tpath}")).hexdigest()
        hit = stored.get((digest, size))
        if hit and tpath != hit[1]:
            errors.append(
                f"{hit[0]}: the bytes of {hit[1]} are also committed as {tpath} "
                "(same sha256); stored evidence must not also be committed")
    if base is not None:
        errors += [f"{p}: new raw per-corner output is committed; store it "
                   "(sim/README.md, \"Stored evidence\") instead"
                   for p in added_raw_outputs(repo, base, rev)]
    if errors:
        print(f"FAIL: {len(errors)} stored-evidence manifest problem(s) in {rev}:",
              file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return EXIT_INVALID
    print(f"OK: {manifests} manifest(s), {entries} entr{'y' if entries == 1 else 'ies'} "
          f"in {MANIFEST_DIR} of {rev}: schema valid, no stored bytes committed. "
          "Bytes NOT hash-verified here (no broker contact); run "
          f"`{posixpath.basename(__file__)} verify <manifest>` with ${ENV_BROKER} set.")
    return EXIT_OK


# --------------------------------------------------------------------------
# verify: fetch through the broker and re-hash
# --------------------------------------------------------------------------


def _http_parts(url: str, what: str):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname \
            or parts.username is not None or parts.password is not None:
        # Never echo the URL: a presigned one is a credential.
        raise ToolError(f"{what} is not a plain http(s) URL")
    return parts


def _conn(parts, timeout):
    cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    return cls(parts.netloc, timeout=timeout)


class Broker:
    """``POST <base>/v1/<op>`` with a JSON body. Holds no credential: the broker
    identifies callers by network identity."""

    def __init__(self, base: str):
        self.parts = _http_parts(base, f"${ENV_BROKER}")
        if self.parts.query or self.parts.fragment:
            raise ToolError(f"${ENV_BROKER} must not carry a query or fragment")

    def call(self, op: str, body: dict) -> tuple[int, dict]:
        conn = _conn(self.parts, BROKER_TIMEOUT_S)
        try:
            conn.request("POST", self.parts.path.rstrip("/") + "/v1/" + op,
                         body=json.dumps(body).encode(),
                         headers={"Content-Type": "application/json",
                                  "Accept": "application/json"})
            resp = conn.getresponse()
            status, raw = resp.status, resp.read(MAX_BROKER_BODY)
        except (OSError, http.client.HTTPException) as exc:
            raise ToolError(f"cannot reach the artifact broker ({type(exc).__name__}); "
                            "failing closed") from None
        finally:
            conn.close()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            payload = {}
        return status, payload


def _refused(op: str, status: int, payload: dict) -> ToolError:
    err = payload.get("error") if isinstance(payload.get("error"), str) else f"http_{status}"
    msg = payload.get("message") if isinstance(payload.get("message"), str) else ""
    return ToolError(f"artifact broker refused {op} (HTTP {status}): {err}: {msg}")


def _fetch_hash(url: str) -> tuple[str, int]:
    """GET a presigned URL and return (sha256, size) of the body. The URL is
    never named in any message."""
    parts = _http_parts(url, "the presigned URL")
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    conn = _conn(parts, TRANSFER_TIMEOUT_S)
    h = hashlib.sha256()
    n = 0
    try:
        conn.request("GET", target)
        resp = conn.getresponse()
        if resp.status != 200:
            resp.read(64 << 10)
            raise ToolError(f"presigned GET was rejected: HTTP {resp.status}")
        while chunk := resp.read(CHUNK):
            h.update(chunk)
            n += len(chunk)
    except (OSError, http.client.HTTPException) as exc:
        raise ToolError(f"presigned GET failed: {type(exc).__name__}") from None
    finally:
        conn.close()
    return h.hexdigest(), n


def verify_entry(broker: Broker, entry: dict) -> dict:
    key = uri_key(entry["uri"])
    repo = repo_from_key(key) or entry["producer"]["loom.repo"]
    if not REPO_RE.match(repo):
        raise ToolError(f"entry {entry['sha256']}: repo {repo!r} is not owner/name")
    result = {"sha256": entry["sha256"], "name": entry.get("name"), "size": entry["size"]}
    req = {"kind": entry["kind"], "repo": repo, "sha256": entry["sha256"]}
    status, stat = broker.call("stat", req)
    if status == 404:
        return {**result, "status": "missing"}
    if status != 200:
        raise _refused("stat", status, stat)
    if stat.get("exists") is not True:
        return {**result, "status": "missing"}
    if isinstance(stat.get("size"), int) and stat["size"] != entry["size"]:
        return {**result, "status": "size_mismatch", "stored_size": stat["size"]}
    status, got = broker.call("get", req)
    if status == 404:
        return {**result, "status": "missing"}
    if status != 200:
        raise _refused("get", status, got)
    answer_key = got.get("key")
    if not isinstance(answer_key, str) or answer_key != key \
            or answer_key.rsplit("/", 1)[-1] != entry["sha256"]:
        return {**result, "status": "key_mismatch"}
    url = got.get("url")
    if not isinstance(url, str) or not url:
        raise ToolError(f"the broker's get answer for {entry['sha256']} carries no URL")
    sha, size = _fetch_hash(url)
    if sha != entry["sha256"]:
        return {**result, "status": "hash_mismatch", "observed_sha256": sha}
    if size != entry["size"]:
        return {**result, "status": "size_mismatch", "observed_size": size}
    return {**result, "status": "ok"}


def verify(paths: list[str], env=None) -> int:
    env = os.environ if env is None else env
    base = env.get(ENV_BROKER)
    if not base:
        raise ToolError(f"no artifact broker configured: set ${ENV_BROKER}. Hash "
                        "verification needs the broker; this is not a pass")
    broker = Broker(base)
    loaded = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"FAIL: {path}: unreadable manifest: {exc}", file=sys.stderr)
            return EXIT_INVALID
        problems = manifest_problems(manifest)
        if problems:
            print(f"FAIL: {path}: " + "; ".join(problems), file=sys.stderr)
            return EXIT_INVALID
        loaded.append((path, manifest))
    failed = 0
    for path, manifest in loaded:
        for entry in manifest["entries"]:
            r = verify_entry(broker, entry)
            print(f"{r['status']:<14} {r['sha256']}  {r.get('name') or ''}")
            failed += r["status"] != "ok"
    total = sum(len(m["entries"]) for _, m in loaded)
    if failed:
        print(f"FAIL: {failed} of {total} stored object(s) missing or mismatched",
              file=sys.stderr)
        return EXIT_FAILED
    print(f"OK: {total} stored object(s) fetched and re-hashed; all match")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="schema + no-committed-blob guard for a tree")
    c.add_argument("--tree", required=True, help="commit or tree (e.g. HEAD)")
    c.add_argument("--base", help="also fail on raw per-corner output added since "
                   "the merge base with this ref")
    c.add_argument("--repo", default=".", help="repository path (default .)")
    v = sub.add_parser("verify", help="fetch through the broker and re-hash")
    v.add_argument("manifests", nargs="+", metavar="MANIFEST")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "check":
            return check(args.repo, args.tree, args.base)
        return verify(args.manifests)
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
