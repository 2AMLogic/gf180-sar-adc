#!/usr/bin/env python3
"""Anti-drift tests for `layout/klt_env.py`, the `layout/` tree's shared
helper module (issue #808).

`layout/klt_env.py` owns the provenance plumbing every `layout/` runner and
generator uses to stamp its evidence records -- most importantly `sha256`,
the one file hasher the tree's committed `gds_sha256` digests may come from.
Its `design/sar-logic/flow/` counterpart has been guarded since #801/#802
(`test_flow_env.NoFlowModuleDefinesItsOwnFileHasherTests`), but that guard
matches on *definition names*, and the one real `layout/`-side copy it needs
to catch is not a definition at all: `array_edge_margin.py` minted its
`gds_sha256` with an inline `hashlib.sha256(open(GDS, "rb").read())`
expression -- invisible to any name predicate, however wide, because there
is no `def` to name (the measured refutation of the name-shaped net this
issue was filed with: 2 false positives, 0 true positives).

So the net here is keyed on the mechanism, not the name: **no module under
`layout/` other than `klt_env.py` itself may import or reference
`hashlib`.** Every reimplementation of a file hasher needs `hashlib` under
some spelling -- `_sha256`, `_gds_sha`, or a nameless inline expression --
so the net cannot be evaded by naming, while every measured legitimate
pattern passes untouched: a delegating wrapper
(`run_sar_ctrl_lvs.py`'s `sha()`), a git-commit helper whose name merely
contains "sha" (`run_extract_parasitics.py`'s `_git_sha`), and per-runner
partial applications (`run_erc.py`/`run_power.py`'s `resolve_klt`). No
`PINNED_LOCAL_DEFS` analogue is needed: no `layout/**.py` is byte-pinned by
`signoff/*.json` (verified at curation, issue #808).

The detector tests pin the detector itself against both measured shapes --
the inline expression that slipped through, and the delegating wrapper that
must keep passing -- so the scan above cannot pass vacuously.

No PDK, no `klt`, no ngspice needed:

    python3 -m unittest discover -s sim/tests -t sim/tests -v
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAYOUT_DIR = REPO / "layout"
KLT_ENV = LAYOUT_DIR / "klt_env.py"


def _hashlib_uses(tree: ast.AST) -> list[tuple[int, str]]:
    """Every way a module can bring `hashlib` in, as (line, spelling) pairs.

    The import statements catch `import hashlib`, `import hashlib as h`,
    `from hashlib import sha256` and `from hashlib import *` at the line the
    module acquires the dependency; the attribute net additionally catches a
    bare `hashlib.sha256(...)` reference even if the module object reached
    the code some other way than its own import statement.
    """
    uses: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "hashlib":
                    bound = alias.asname or alias.name
                    uses.append((node.lineno, f"import hashlib as {bound}"))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "hashlib":
                names = ", ".join(alias.name for alias in node.names)
                uses.append((node.lineno, f"from hashlib import {names}"))
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "hashlib"
        ):
            uses.append((node.lineno, f"hashlib.{node.attr}"))
    return uses


class NoLayoutModuleUsesHashlibDirectlyTests(unittest.TestCase):
    r"""The `layout/`-side half of the invariant #802 closed for
    `design/sar-logic/flow/`: one file hasher, one implementation.

    `klt_env.py` is the single exemption because owning `sha256` is its job;
    the test pins that it actually uses `hashlib`, so the exemption cannot
    mask a broken detector.
    """

    def test_klt_env_is_the_only_layout_module_using_hashlib(self):
        offenders: dict[str, list[str]] = {}
        for path in sorted(LAYOUT_DIR.rglob("*.py")):
            if path == KLT_ENV:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            uses = [f"line {line}: {what}" for line, what in _hashlib_uses(tree)]
            if uses:
                offenders[str(path.relative_to(REPO))] = uses
        self.assertEqual(
            offenders,
            {},
            "these layout/ modules import or reference hashlib directly: "
            f"{offenders} -- layout/klt_env.py owns the file hasher; import "
            "`sha256` from it instead (issue #808: the digest an evidence "
            "record stamps must come from the audited shared implementation).",
        )

    def test_klt_env_itself_uses_hashlib(self):
        """The exemption is load-bearing: the exempted module is a real
        `hashlib` user, so this scan can never pass by matching nothing."""
        self.assertTrue(_hashlib_uses(ast.parse(KLT_ENV.read_text())))


class HashlibNetDetectorTests(unittest.TestCase):
    """Guards the detector itself: if it stopped matching these shapes, the
    scan above would pass vacuously and #801 could recur silently."""

    def test_flags_the_inline_expression_that_slipped_through(self):
        # `layout/adc-top/array_edge_margin.py:210` as it was before this
        # issue's fix -- an inline expression, not a definition, which is
        # exactly what the name-shaped alternative was blind to.
        synthetic = (
            "import hashlib\n"
            'result = {"gds_sha256": hashlib.sha256(open(GDS, "rb").read()).hexdigest()}\n'
        )
        self.assertTrue(_hashlib_uses(ast.parse(synthetic)))

    def test_flags_every_import_spelling(self):
        for spelling in (
            "import hashlib\n",
            "import hashlib as h\nh.sha256(b'').hexdigest()\n",
            "from hashlib import sha256\nsha256(b'').hexdigest()\n",
            "from hashlib import sha256 as digest\ndigest(b'')\n",
            "from hashlib import *\nsha256(b'')\n",
        ):
            with self.subTest(first_line=spelling.splitlines()[0]):
                self.assertTrue(_hashlib_uses(ast.parse(spelling)))

    def test_flags_a_hashlib_reference_without_an_import(self):
        synthetic = 'digest = hashlib.sha256(open(path, "rb").read()).hexdigest()\n'
        self.assertTrue(_hashlib_uses(ast.parse(synthetic)))

    def test_does_not_flag_delegating_consumers(self):
        # `layout/lvs/run_sar_ctrl_lvs.py`'s `sha()`: a thin path-joining
        # wrapper delegating to the shared hasher is the *correct* consumer
        # pattern this net exists to leave alone.
        delegating = (
            "import os\n"
            "import klt_env\n"
            "\n"
            'REPO_ROOT = "/repo"\n'
            "\n"
            "def sha(path: str) -> str:\n"
            "    return klt_env.sha256(os.path.join(REPO_ROOT, path))\n"
        )
        self.assertEqual(_hashlib_uses(ast.parse(delegating)), [])

    def test_does_not_flag_sha_sounding_names_without_hashlib(self):
        # `layout/adc-top/parasitics/run_extract_parasitics.py`'s `_git_sha`:
        # a git-commit helper that matched the name-shaped net only because
        # "sha" is one of its underscore parts (a measured false positive of
        # the rejected alternative, recorded in issue #808).
        git_sha = (
            "import subprocess\n"
            "\n"
            "def _git_sha() -> str:\n"
            "    return subprocess.run(\n"
            '        ["git", "rev-parse", "HEAD"], capture_output=True, text=True\n'
            "    ).stdout.strip()\n"
        )
        self.assertEqual(_hashlib_uses(ast.parse(git_sha)), [])


if __name__ == "__main__":
    unittest.main()
