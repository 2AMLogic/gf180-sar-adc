#!/usr/bin/env python3
"""Regression tests for `design/sar-logic/flow/flow_env.py` (issue #352).

`flow_env.py` is the single implementation of the git/`klt` provenance
plumbing every `design/sar-logic/flow/` driver uses to stamp its append-only
evidence records -- previously five helpers copied byte-for-byte between
`synth_sar_ctrl.py` and `pnr_sar_ctrl.py`. Two things are tested here:

1. **Behavior**: `git`/`git_status_porcelain`/`record_id`/`run` are exercised
   against a throwaway git repo built in a temp directory, so the record ID
   grammar, the clean/dirty status read, and the failure fallbacks are
   asserted rather than assumed. (This is why those functions take
   `repo_root` as a parameter instead of closing over a module constant.)
2. **Non-recurrence**: the drivers are parsed and checked to define none of
   the shared names themselves. That is the check that actually keeps this
   issue fixed -- a future edit re-forking one of these helpers into one
   driver (the exact drift `layout/klt_env.py` was created to stop in
   `layout/`) fails here instead of silently shipping two divergent
   provenance implementations.

No PDK, no `klt`, no ngspice needed:

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FLOW_DIR = REPO / "design" / "sar-logic" / "flow"
FLOW_ENV = FLOW_DIR / "flow_env.py"

_spec = importlib.util.spec_from_file_location("flow_env", FLOW_ENV)
flow_env = importlib.util.module_from_spec(_spec)
sys.modules["flow_env"] = flow_env
_spec.loader.exec_module(flow_env)

#: The helpers `flow_env` owns. No driver in `design/sar-logic/flow/` may
#: define any of these -- under either the public name or the leading-
#: underscore name the pre-#352 copies used.
SHARED_NAMES = ("run", "git", "git_status_porcelain", "klt_version", "record_id")
FORBIDDEN_DEFS = set(SHARED_NAMES) | {f"_{name}" for name in SHARED_NAMES}

#: Every driver in `design/sar-logic/flow/` that mints evidence records.
DRIVERS = (
    "synth_sar_ctrl.py",
    "pnr_sar_ctrl.py",
    "sta_sar_ctrl.py",
    "sta_sar_ctrl_postroute.py",
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class TempRepo:
    """A throwaway git repo with one commit, for the behavior tests below."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        _git(self.path, "init", "-q", "-b", "main")
        _git(self.path, "config", "user.email", "test@example.invalid")
        _git(self.path, "config", "user.name", "Test")
        (self.path / "tracked.txt").write_text("hello\n")
        _git(self.path, "add", "tracked.txt")
        _git(self.path, "commit", "-qm", "initial")

    def cleanup(self) -> None:
        self._tmp.cleanup()


class GitHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = TempRepo()

    @classmethod
    def tearDownClass(cls):
        cls.repo.cleanup()

    def test_git_returns_stripped_stdout(self):
        head = flow_env.git(self.repo.path, "rev-parse", "HEAD")
        self.assertRegex(head, r"^[0-9a-f]{40}$")

    def test_git_runs_in_the_repo_it_is_given_not_the_cwd(self):
        """`repo_root` is what selects the repo -- not the process cwd."""
        with tempfile.TemporaryDirectory() as elsewhere:
            cwd = os.getcwd()
            os.chdir(elsewhere)
            try:
                head = flow_env.git(self.repo.path, "rev-parse", "HEAD")
            finally:
                os.chdir(cwd)
        self.assertRegex(head, r"^[0-9a-f]{40}$")

    def test_git_returns_empty_string_on_a_failing_command(self):
        self.assertEqual(flow_env.git(self.repo.path, "rev-parse", "no-such-ref"), "")

    def test_git_returns_empty_string_outside_a_repo(self):
        with tempfile.TemporaryDirectory() as not_a_repo:
            self.assertEqual(flow_env.git(Path(not_a_repo), "rev-parse", "HEAD"), "")

    def test_status_porcelain_is_empty_on_a_clean_tree(self):
        self.assertEqual(flow_env.git_status_porcelain(self.repo.path), "")

    def test_status_porcelain_keeps_the_column_significant_status_prefix(self):
        """`working_tree_dirty()` slices `line[3:]` for the path, so the two
        leading status columns must survive verbatim -- this is why
        `git_status_porcelain` exists separately from `git()`, which strips."""
        scratch = self.repo.path / "scratch.txt"
        scratch.write_text("dirty\n")
        try:
            status = flow_env.git_status_porcelain(self.repo.path)
            self.assertEqual(status, "?? scratch.txt")
            self.assertEqual(status[3:], "scratch.txt")
        finally:
            scratch.unlink()

    def test_record_id_matches_the_ratified_grammar(self):
        when = dt.datetime(2026, 9, 21, 15, 30, 0, tzinfo=dt.timezone.utc)
        rid = flow_env.record_id(self.repo.path, when)
        self.assertRegex(rid, r"^\d{8}-\d{6}-[0-9a-f]{7,}$")
        self.assertTrue(rid.startswith("20260921-153000-"), rid)

    def test_record_id_uses_the_passed_instant_not_the_wall_clock(self):
        """One driver run names several artifacts under a single record ID."""
        when = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
        first = flow_env.record_id(self.repo.path, when)
        second = flow_env.record_id(self.repo.path, when)
        self.assertEqual(first, second)

    def test_record_id_degrades_to_nogit_without_a_repo(self):
        when = dt.datetime(2026, 9, 21, 15, 30, 0, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as not_a_repo:
            self.assertEqual(
                flow_env.record_id(Path(not_a_repo), when), "20260921-153000-nogit"
            )

    def test_run_captures_both_streams_and_never_raises_on_nonzero(self):
        result = flow_env.run(
            self.repo.path,
            [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)"],
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout.strip(), "out")
        self.assertEqual(result.stderr.strip(), "err")

    def test_run_executes_in_the_given_repo_root(self):
        result = flow_env.run(self.repo.path, [sys.executable, "-c", "import os; print(os.getcwd())"])
        self.assertEqual(
            Path(result.stdout.strip()).resolve(), self.repo.path.resolve()
        )


class NoDriverRedefinesTheSharedHelpersTests(unittest.TestCase):
    """The anti-drift check: parse each driver, assert it defines none of the
    shared names and imports them from `flow_env` instead."""

    def _module_ast(self, name: str) -> ast.Module:
        return ast.parse((FLOW_DIR / name).read_text(), filename=name)

    def test_no_driver_defines_a_shared_helper(self):
        for name in DRIVERS:
            with self.subTest(driver=name):
                defined = {
                    node.name
                    for node in self._module_ast(name).body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                clashes = sorted(defined & FORBIDDEN_DEFS)
                self.assertEqual(
                    clashes,
                    [],
                    f"{name} defines {clashes} itself -- import them from "
                    "design/sar-logic/flow/flow_env.py instead (issue #352: two "
                    "copies of this provenance plumbing drift apart silently).",
                )

    def test_every_driver_imports_from_flow_env(self):
        for name in DRIVERS:
            with self.subTest(driver=name):
                imported = {
                    alias.name
                    for node in self._module_ast(name).body
                    if isinstance(node, ast.ImportFrom) and node.module == "flow_env"
                    for alias in node.names
                }
                self.assertTrue(
                    imported,
                    f"{name} imports nothing from flow_env -- it mints evidence "
                    "records, so its provenance plumbing must be the shared one.",
                )
                self.assertTrue(
                    imported <= set(SHARED_NAMES),
                    f"{name} imports unexpected names from flow_env: "
                    f"{sorted(imported - set(SHARED_NAMES))}",
                )

    def test_flow_env_defines_every_shared_name(self):
        for name in SHARED_NAMES:
            with self.subTest(helper=name):
                self.assertTrue(callable(getattr(flow_env, name, None)))


class SynthDriverUsesTheSharedObjectsTests(unittest.TestCase):
    """The AST checks above are structural; this one is live -- it loads
    `synth_sar_ctrl.py` (no PDK/`klt` touched at import time) and asserts the
    names it exposes are `flow_env`'s own function objects, not look-alikes.

    `pnr_sar_ctrl.py` is deliberately NOT imported here: it pulls in
    `layout/adc-top/gen_adc_top.py`, which needs the pip `klayout` package,
    and this suite must stay runnable without it. The AST checks above cover
    it instead.
    """

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "synth_sar_ctrl", FLOW_DIR / "synth_sar_ctrl.py"
        )
        cls.synth = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.synth)

    def test_shared_helpers_are_the_same_objects(self):
        for name in SHARED_NAMES:
            with self.subTest(helper=name):
                self.assertIs(getattr(self.synth, name), getattr(flow_env, name))

    def test_working_tree_dirty_still_reads_this_checkout(self):
        """`working_tree_dirty()` stays per-driver (each excludes its own
        output tree), but it now reads status through the shared helper --
        assert it still returns a bool for the real repo rather than raising."""
        self.assertIsInstance(self.synth.working_tree_dirty(), bool)

    def test_record_id_of_this_repo_carries_the_current_short_sha(self):
        when = dt.datetime(2026, 9, 21, 15, 30, 0, tzinfo=dt.timezone.utc)
        rid = self.synth.record_id(self.synth.REPO_ROOT, when)
        self.assertRegex(rid, r"^20260921-153000-(?:[0-9a-f]{7,}|nogit)$")


class NoDuplicateProvenancePlumbingLeftTests(unittest.TestCase):
    """Belt-and-braces on the textual level: the pre-#352 bodies are gone."""

    #: The `cwd=REPO_ROOT` subprocess idiom the duplicated copies shared.
    _OLD_BODY = re.compile(r"subprocess\.run\(\s*\[\s*\"git\"")

    def test_no_driver_shells_out_to_git_directly(self):
        for name in DRIVERS:
            with self.subTest(driver=name):
                self.assertIsNone(
                    self._OLD_BODY.search((FLOW_DIR / name).read_text()),
                    f"{name} shells out to git itself -- use flow_env.git()/"
                    "flow_env.git_status_porcelain() (issue #352).",
                )


if __name__ == "__main__":
    unittest.main()
