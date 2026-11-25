#!/usr/bin/env python3
"""Regression controls for `sim/tools/check_markdown_links.py` (issue #472).

    python3 -m unittest discover -s sim/tests -v

Stdlib only; builds throwaway git repos as fixtures.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim" / "tools"))
import check_markdown_links as C  # noqa: E402


def make_repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


class LinkTests(unittest.TestCase):
    def run_main(self, files, allow=None):
        root = make_repo(files)
        args = ["--repo", str(root)]
        if allow is not None:
            f = root / "allow.txt"
            f.write_text(allow, encoding="utf-8")
            args += ["--allowlist", str(f)]
        return C.main(args)

    def test_good_links_pass(self):
        self.assertEqual(self.run_main({
            "a.md": "[b](sub/b.md) [frag](sub/b.md#x) [web](https://x.y/z) "
                    "[m](mailto:a@b.c) [self](#top)\n",
            "sub/b.md": "[up](../a.md)\n",
        }), 0)

    def test_broken_link_fails(self):
        self.assertEqual(self.run_main({"a.md": "[x](missing.md)\n"}), 1)

    def test_relative_to_containing_file(self):
        # root-relative spelling from inside a subdir is broken.
        self.assertEqual(self.run_main({
            "a.md": "x\n", "sub/b.md": "[a](sub/b.md)\n"}), 1)

    def test_fenced_and_inline_code_ignored(self):
        self.assertEqual(self.run_main({
            "a.md": "```\n[x](nope.md)\n```\n~~~\n[y](nope2.md)\n~~~\n`[z](nope3.md)`\n"}), 0)

    def test_after_fence_is_checked_again(self):
        self.assertEqual(self.run_main({
            "a.md": "```\nx\n```\n[x](nope.md)\n"}), 1)

    def test_skipped_dirs(self):
        self.assertEqual(self.run_main({
            ".claude/s.md": "[x](nope.md)\n", ".loom/s.md": "[x](nope.md)\n",
            ".agents/s.md": "[x](nope.md)\n"}), 0)

    def test_allowlist_exempts_exact_entry(self):
        files = {"a.md": "[x](missing.md)\n"}
        self.assertEqual(self.run_main(files, "a.md -> missing.md  # reason\n"), 0)
        self.assertEqual(self.run_main(files, "a.md -> other.md  # reason\n"), 1)

    def test_allowlist_requires_reason(self):
        with self.assertRaises(SystemExit):
            C.load_allowlist("a.md -> missing.md\n")

    def test_real_tree_is_clean(self):
        self.assertEqual(C.main([]), 0)


if __name__ == "__main__":
    unittest.main()
