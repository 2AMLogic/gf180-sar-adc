"""Write simulation evidence through the fleet artifact store (issue #636).

Evidence bytes (JSON twins, netlist snapshots, per-corner logs, campaign
artifacts) no longer land in git. They go to the artifact store through
``klt artifact put`` (klayout-tools, ``docs/cli/artifact.md``), and git keeps:

* a manifest, ``manifests/artifacts/<bench>-<run-id>.manifest.json``, one
  entry per stored file (``sha256``, ``size``, ``kind=evidence``,
  ``producer``, ``uri`` plus the logical ``name`` the file would have had
  under ``sim/``). The ``uri`` is the logical ``artifact:<key>`` that only
  the broker resolves (operator ruling H1, 2AMLogic/2am#5553), so a manifest
  names no storage location;
* the run's Markdown summary under ``sim/<bench>/``.

Evidence bytes are private and manifests are public (operator decision 1.1,
2026-10-22): a manifest is safe in this public repo, and only callers the
broker admits can resolve its ``uri``s.

**Fail closed.** Every failure here raises :class:`StoreError`: no broker
configured, no ``klt`` with the ``artifact`` verb, a ``klt`` older than
klayout-tools ``7e3561f`` (it would write bucket-naming ``s3`` uris), a
broker that cannot be reached or refuses, a put that fails part-way, a
manifest that does not match the bytes it claims. Nothing is then installed
under ``manifests/`` or ``sim/``; the staged bytes stay in the git-ignored
scratch tree so the run is not lost, and the caller reports the failure.
There is no fallback that commits the bytes instead.

Configuration comes from the environment only (``KLT_ARTIFACT_BROKER``,
optionally ``KLT_ARTIFACT_REPO``), read by ``klt`` itself. There is no bucket
setting: the broker resolves the key. This module never puts the broker URL
in argv, a record or a message, and holds no credential: the broker
identifies callers by network identity.

Stdlib only.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ENV_BROKER = "KLT_ARTIFACT_BROKER"
ENV_REPO = "KLT_ARTIFACT_REPO"
MANIFEST_DIR = Path("manifests") / "artifacts"
#: klayout-tools merge commit (PR #4070) from which ``klt artifact`` writes
#: logical ``artifact:<key>`` uris and has no bucket setting. The writer needs
#: a ``klt`` at or after it (:func:`check_klt_uri_scheme`); the signoff/layout
#: pin in ``layout/toolchain.json`` is a separate build and is not moved by this.
KLT_ARTIFACT_MIN_COMMIT = "7e3561f932145870b6fad917b487b468be12f3c3"
PROBE_TIMEOUT_S = 30
PUT_TIMEOUT_S = 900

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
#: Same grammar as ``klayout_tools.artifact_store``: ``artifact:<key>``, no
#: other scheme.
_URI_RE = re.compile(r"^artifact:([^/\s]\S*)$")
#: An unroutable broker for the scheme probe: a klt that gets as far as the
#: network has already accepted the probe's legacy-scheme uri, i.e. is too old.
_PROBE_BROKER = "http://127.0.0.1:9"
#: The scheme klt wrote before ``7e3561f``. Only the probe uses it, to build a
#: uri a current klt must refuse; nothing in this repo writes one.
LEGACY_URI_SCHEME = "s3"
_RID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REMOTE_RE = re.compile(r"[:/]([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class StoreError(RuntimeError):
    """Evidence could not be stored; nothing was committed (fail closed)."""


def manifest_path(repo_root: Path, bench: str, rid: str) -> Path:
    for part in (bench, rid):
        if not _RID_RE.match(part):
            raise ValueError(f"invalid bench or run id {part!r}")
    return repo_root / MANIFEST_DIR / f"{bench}-{rid}.manifest.json"


def sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


# --------------------------------------------------------------------------
# Preflight: refuse to start an evidence-writing run that could not be stored
# --------------------------------------------------------------------------


def _repo_name(repo_root: Path, env, run) -> str:
    repo = env.get(ENV_REPO)
    if not repo:
        try:
            p = run(["git", "-C", str(repo_root), "remote", "get-url", "origin"],
                    capture_output=True, text=True, timeout=30, check=False)
            remote = p.stdout.strip() if p.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            remote = ""
        m = _REMOTE_RE.search(remote)
        if m is None:
            raise StoreError(f"cannot tell which repo to store under: set ${ENV_REPO}")
        repo = f"{m.group(1)}/{m.group(2)}"
    return repo


def probe_broker(base: str, repo: str, timeout: float = PROBE_TIMEOUT_S) -> None:
    """One ``stat`` of the empty digest: proves the broker is reachable and
    admits this caller for ``repo`` before any simulation time is spent. A
    ``200`` (present or not) or ``404`` passes; anything else raises."""
    parts = urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.hostname \
            or parts.username is not None or parts.password is not None \
            or parts.query or parts.fragment:
        raise StoreError(f"${ENV_BROKER} is not a plain http(s) base URL")
    cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    conn = cls(parts.netloc, timeout=timeout)
    body = {"kind": "evidence", "repo": repo, "sha256": _EMPTY_SHA256}
    try:
        conn.request("POST", parts.path.rstrip("/") + "/v1/stat",
                     body=json.dumps(body).encode(),
                     headers={"Content-Type": "application/json",
                              "Accept": "application/json"})
        resp = conn.getresponse()
        status, raw = resp.status, resp.read(64 << 10)
    except (OSError, http.client.HTTPException) as exc:
        raise StoreError(f"artifact broker unreachable ({type(exc).__name__})") from None
    finally:
        conn.close()
    if status in (200, 404):
        return
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {}
    err = payload.get("error") if isinstance(payload, dict) else None
    raise StoreError(f"artifact broker refused this caller (HTTP {status}"
                     f"{': ' + err if isinstance(err, str) else ''})")


def preflight(repo_root: Path, *, klt: str = "klt", env=None,
              which=shutil.which, run=subprocess.run, probe=probe_broker) -> None:
    """Raise :class:`StoreError` unless an evidence run could be stored."""
    env = os.environ if env is None else env
    base = env.get(ENV_BROKER)
    if not base:
        raise StoreError(f"no artifact broker configured (${ENV_BROKER} is unset)")
    exe = which(klt)
    if exe is None:
        raise StoreError(f"`{klt}` is not on PATH")
    try:
        p = run([exe, "artifact", "put", "--help"], capture_output=True, text=True,
                timeout=60, check=False)
        ok = p.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    if not ok:
        raise StoreError(f"`{klt}` has no `artifact put` verb; install klayout-tools "
                         f"at or after {KLT_ARTIFACT_MIN_COMMIT[:12]}")
    check_klt_uri_scheme(exe, run=run)
    probe(base, _repo_name(repo_root, env, run))


def check_klt_uri_scheme(exe: str, *, run=subprocess.run) -> None:
    """Raise :class:`StoreError` unless ``exe`` is a ``klt`` at or after
    :data:`KLT_ARTIFACT_MIN_COMMIT`, i.e. one that writes ``artifact:<key>``.

    ``klt`` carries no commit in its version string, so this tests the
    behaviour that changed rather than a number. It hands ``klt artifact
    verify`` a manifest that is valid except for a :data:`LEGACY_URI_SCHEME`
    uri (the bucket-naming form klt wrote before ``7e3561f``). A current
    ``klt`` rejects it offline as ``invalid_manifest`` with an ``artifact:``
    problem, before any broker contact. An older ``klt`` accepts the
    legacy uri and goes on to the (unroutable) probe broker; a ``klt``
    without ``verify`` fails on usage. Every outcome except the current one
    refuses (fail closed).
    """
    sha = hashlib.sha256(b"klt uri-scheme probe").hexdigest()
    entry = {"sha256": sha, "size": 1, "kind": "evidence",
             "producer": {"tool": "probe", "version": "0", "loom.repo": "probe/probe",
                          "commit": None},
             "uri": f"{LEGACY_URI_SCHEME}://probe/evidence/probe__probe/{sha[:2]}/{sha}",
             "name": "sim/probe"}
    with tempfile.TemporaryDirectory(prefix="klt-scheme-probe-") as tmp:
        mpath = os.path.join(tmp, "probe.manifest.json")
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump({"schema_version": 1, "entries": [entry]}, fh)
        try:
            p = run([exe, "artifact", "verify", mpath, "--broker", _PROBE_BROKER,
                     "--format", "json"], capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT_S, check=False, cwd=tmp)
            rc, stderr = p.returncode, p.stderr or ""
        except subprocess.TimeoutExpired:
            raise StoreError(f"`klt` uri-scheme probe timed out after {PROBE_TIMEOUT_S}s; "
                             "cannot confirm klt writes artifact:<key> uris") from None
        except OSError as exc:
            raise StoreError(f"`klt` uri-scheme probe failed to start ({exc}); "
                             "cannot confirm klt writes artifact:<key> uris") from None
    try:
        err = json.loads(stderr)["error"]
        problems = err.get("problems")
        current = (rc == 1 and err.get("code") == "invalid_manifest"
                   and isinstance(problems, list) and bool(problems)
                   and all(isinstance(x, str) and "artifact:" in x for x in problems))
    except (ValueError, KeyError, TypeError, AttributeError):
        current = False
    if not current:
        raise StoreError(f"`klt` is older than klayout-tools {KLT_ARTIFACT_MIN_COMMIT[:12]} "
                         f"(it would write {LEGACY_URI_SCHEME} manifest uris, not "
                         "artifact:<key>); "
                         "upgrade klayout-tools")


# --------------------------------------------------------------------------
# Put
# --------------------------------------------------------------------------


def _klt_error(stderr: str) -> str:
    """``code: message`` from klt's JSON error envelope (never a URL: klt
    keeps presigned URLs out of every message), else the last stderr line."""
    try:
        err = json.loads(stderr)["error"]
        return f"{err.get('code', 'error')}: {err.get('message', '')}".strip()
    except (ValueError, KeyError, TypeError):
        lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
        return lines[-1][:300] if lines else "no diagnostic"


def _entry_problem(entry) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    if not (isinstance(entry.get("sha256"), str) and _SHA_RE.match(entry["sha256"])):
        return "bad sha256"
    if entry.get("kind") != "evidence":
        return "kind is not evidence"
    uri = entry.get("uri")
    m = _URI_RE.match(uri) if isinstance(uri, str) else None
    if m is None:
        return "uri is not artifact:<key> (klt older than klayout-tools 7e3561f?)"
    if m.group(1).rsplit("/", 1)[-1] != entry["sha256"]:
        return "uri key does not name the sha256"
    if not isinstance(entry.get("producer"), dict):
        return "no producer"
    return None


def put_files(files: list[tuple[Path, str]], repo_root: Path, *,
              klt: str = "klt", run=subprocess.run) -> tuple[dict, list[str]]:
    """Store every ``(path, name)`` and return ``(manifest, empty_names)``.

    One ``klt artifact put --name NAME`` per file, merged into a manifest in a
    private temporary directory (never in the repo). Zero-byte files cannot be
    stored (the store's minimum object is one byte); their names are returned
    so the summary can list them -- their content is fully known. After the
    puts, every entry is cross-checked against a local re-hash of its file.
    Any failure raises :class:`StoreError`; the manifest is then discarded.
    """
    names = [n for _, n in files]
    if len(set(names)) != len(names):
        raise StoreError("two staged files map to the same evidence name")
    expected: dict[str, tuple[str, int]] = {}
    empty: list[str] = []
    with tempfile.TemporaryDirectory(prefix="evidence-manifest-") as tmp:
        tmp_manifest = os.path.join(tmp, "manifest.json")
        for path, name in files:
            sha, size = sha256_file(path)
            if size == 0:
                empty.append(name)
                continue
            expected[name] = (sha, size)
            cmd = [klt, "artifact", "put", str(path), "--name", name,
                   "--manifest", tmp_manifest, "--format", "json"]
            try:
                p = run(cmd, cwd=str(repo_root), capture_output=True, text=True,
                        timeout=PUT_TIMEOUT_S, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise StoreError(f"klt artifact put {name}: {type(exc).__name__}") from None
            if p.returncode != 0:
                raise StoreError(f"klt artifact put {name} failed "
                                 f"(exit {p.returncode}): {_klt_error(p.stderr)}")
        if not expected:
            raise StoreError("nothing to store: every staged file is empty")
        try:
            with open(tmp_manifest, encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, ValueError) as exc:
            raise StoreError(f"klt wrote no readable manifest: {exc}") from None
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list) or manifest.get("schema_version") != 1:
        raise StoreError("klt manifest is not {schema_version: 1, entries: [...]}")
    by_name = {}
    for e in entries:
        problem = _entry_problem(e)
        if problem:
            raise StoreError(f"klt manifest entry invalid: {problem}")
        by_name[e.get("name")] = e
    if set(by_name) != set(expected):
        raise StoreError("klt manifest entries do not match the staged files")
    for name, (sha, size) in expected.items():
        if (by_name[name]["sha256"], by_name[name]["size"]) != (sha, size):
            raise StoreError(f"klt manifest entry for {name} does not match the file's "
                             "local sha256/size")
    manifest["entries"] = sorted(entries, key=lambda e: e["name"])
    return manifest, sorted(empty)


def install_manifest(manifest: dict, path: Path) -> None:
    """Create ``path`` exclusively: an existing manifest is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")
    except FileExistsError as exc:
        raise StoreError(f"{path.name} already exists; refusing to overwrite") from exc


def stage_files(stage_dir: Path, name_prefix: str, *, exclude=()) -> list[tuple[Path, str]]:
    """Every regular file under ``stage_dir`` as ``(path, name_prefix/rel)``,
    sorted; symlinks are refused (their bytes are not what is stored)."""
    out = []
    excluded = {Path(p).resolve() for p in exclude}
    for path in sorted(stage_dir.rglob("*")):
        if path.is_symlink():
            raise StoreError(f"staged evidence contains a symlink: {path.name}")
        if not path.is_file() or path.resolve() in excluded:
            continue
        rel = path.relative_to(stage_dir).as_posix()
        out.append((path, f"{name_prefix}/{rel}"))
    return out


def summary_section(manifest_rel: str, manifest: dict, empty: list[str]) -> str:
    """Markdown appended to a run's committed summary: where its bytes are."""
    total = sum(e["size"] for e in manifest["entries"])
    lines = [
        "",
        "## Stored evidence",
        "",
        f"The bytes of this run are in the fleet artifact store, not in git "
        f"(issue #636). Manifest: `{manifest_rel}` "
        f"({len(manifest['entries'])} objects, {total} B). Paths above are the "
        "manifest `name`s. Fetch one, hash-verified, with:",
        "",
        "```",
        f"klt artifact get {manifest_rel}#<name> -o <out>",
        f"python3 scripts/check_artifact_manifests.py verify {manifest_rel}",
        "```",
        "",
        "| name | size (B) | sha256 |",
        "|---|---:|---|",
    ]
    for e in manifest["entries"]:
        lines.append(f"| `{e['name']}` | {e['size']} | `{e['sha256']}` |")
    for name in empty:
        lines.append(f"| `{name}` | 0 | `{_EMPTY_SHA256}` (empty, not stored) |")
    return "\n".join(lines) + "\n"


def store_files(files: list[tuple[Path, str]], *, repo_root: Path, bench: str,
                rid: str, summary_text: str, summary_path: Path,
                put=None) -> Path:
    """Store ``files``; commit only their manifest and the run's summary.

    Order matters for fail-closed: (1) refuse if the manifest or summary
    already exists; (2) put every file; (3) install the manifest exclusively;
    (4) write the summary exclusively, with a "Stored evidence" section that
    lists every object. A failure in (1)-(2) leaves nothing in the repo.
    Returns the manifest path.
    """
    mpath = manifest_path(repo_root, bench, rid)
    for p in (mpath, summary_path):
        if os.path.lexists(p):
            raise StoreError(f"{p.relative_to(repo_root)} already exists; refusing "
                             "to overwrite evidence")
    if not files:
        raise StoreError("nothing staged to store")
    manifest, empty = (put or put_files)(files, repo_root)
    mrel = mpath.relative_to(repo_root).as_posix()
    install_manifest(manifest, mpath)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(summary_path, "x", encoding="utf-8") as fh:
            fh.write(summary_text.rstrip("\n") + "\n" + summary_section(mrel, manifest, empty))
    except FileExistsError as exc:
        raise StoreError(f"{summary_path.name} appeared concurrently") from exc
    return mpath
