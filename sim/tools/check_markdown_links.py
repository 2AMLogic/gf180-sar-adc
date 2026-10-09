#!/usr/bin/env python3
"""Fail if a tracked markdown file has an inline relative link that does not
resolve to an existing path (issue #472).

    python3 sim/tools/check_markdown_links.py [--repo DIR] [--allowlist FILE]

Walks `git ls-files '*.md'`, skipping `.claude/`, `.loom/`, `.agents/`. For
each inline `[text](target)` outside fenced code blocks and inline code spans,
with no URI scheme (http:, mailto:, ...), the target (fragment and query
stripped) is resolved relative to the containing file; a missing path fails.
Anchors are not checked. No network access.

Exceptions live in `sim/tools/markdown_links_allowlist.txt`, one per line:

    <file> -> <link target as written>  # <justification, mandatory>

Stdlib-only, PDK-free: runs on the headless CI path.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SKIP_PREFIXES = (".claude/", ".loom/", ".agents/")
ALLOWLIST_REL = "sim/tools/markdown_links_allowlist.txt"

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
# [text](target) -- target optionally <...>-wrapped, optional "title".
_LINK = re.compile(r"\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]*>|[^()\s]*(?:\([^()\s]*\)[^()\s]*)*)(?:\s+[\"'][^)]*)?\)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def tracked_markdown(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "*.md"],
        check=True, capture_output=True, text=True,
    ).stdout
    return sorted(p for p in out.split("\0") if p and not p.startswith(SKIP_PREFIXES))


def extract_links(text: str):
    """Yield (lineno, target) for inline links outside fenced code."""
    fence = None
    for lineno, line in enumerate(text.splitlines(), 1):
        m = _FENCE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0], len(marker)
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue
        line = _CODE_SPAN.sub("", line)
        for lm in _LINK.finditer(line):
            target = lm.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1].strip()
            yield lineno, target


def resolves(repo: Path, rel_file: str, target: str) -> bool | None:
    """None if the target is not a checkable relative path."""
    if not target or target.startswith("#") or _SCHEME.match(target) or target.startswith("//"):
        return None
    path = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path:
        return None
    base = repo if path.startswith("/") else (repo / rel_file).parent
    return (base / path.lstrip("/")).exists()


def load_allowlist(text: str) -> set[tuple[str, str]]:
    allowed: set[tuple[str, str]] = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entry, sep, why = line.partition(" # ")
        if not sep or not why.strip() or "->" not in entry:
            raise SystemExit(
                f"error: {ALLOWLIST_REL}:{lineno}: expected "
                "'<file> -> <target>  # <justification>'"
            )
        f, _, t = entry.partition("->")
        allowed.add((f.strip(), t.strip()))
    return allowed


def find_broken(repo: Path, allowlist: set[tuple[str, str]]) -> list[str]:
    broken = []
    for rel in tracked_markdown(repo):
        p = repo / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for lineno, target in extract_links(text):
            if resolves(repo, rel, target) is False and (rel, target) not in allowlist:
                broken.append(f"{rel}:{lineno}: broken link -> {target}")
    return broken


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--allowlist", type=Path, default=None)
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    allow_file = args.allowlist or repo / ALLOWLIST_REL
    allowlist = load_allowlist(allow_file.read_text(encoding="utf-8")) if allow_file.exists() else set()
    broken = find_broken(repo, allowlist)
    if broken:
        print("\n".join(broken))
        print(f"\nFAIL: {len(broken)} relative markdown link(s) do not resolve "
              f"(fix the path, or add a reasoned entry to {ALLOWLIST_REL})")
        return 1
    print("ok: all relative markdown links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
