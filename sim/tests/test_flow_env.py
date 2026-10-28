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
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]
FLOW_DIR = REPO / "design" / "sar-logic" / "flow"
FLOW_ENV = FLOW_DIR / "flow_env.py"

flow_env = load_module("flow_env", FLOW_ENV)

#: The helpers `flow_env` owns. No driver in `design/sar-logic/flow/` may
#: define any of these -- under either the public name or the leading-
#: underscore name the pre-#352 copies used.
SHARED_NAMES = ("run", "git", "git_status_porcelain", "klt_version", "record_id")
#: Added by issue #537: the `klt` runner and STA result pieces the STA drivers share.
STA_SHARED_NAMES = ("pdk_env", "run_klt_json", "StaError", "CornerResult", "verdict_table")
#: Added by issue #569: the sar_ctrl design-point constants the drivers share.
DESIGN_POINT_NAMES = (
    "TOP", "CELL_LIBRARY", "LIB_TAG", "CLOCK_PORT", "CLOCK_PERIOD_NS", "CORNERS",
    "OUT_DIR", "REPORTS_DIR", "RECORDS_DIR",
)
#: Added by issue #646: formerly copy-pasted per driver.
DEDUPED_NAMES = ("liberty_path", "working_tree_dirty")
ALLOWED_IMPORTS = (
    set(SHARED_NAMES) | set(STA_SHARED_NAMES) | set(DESIGN_POINT_NAMES) | set(DEDUPED_NAMES)
)
FORBIDDEN_DEFS = set(SHARED_NAMES) | set(DEDUPED_NAMES) | {f"_{name}" for name in SHARED_NAMES}
#: Local definitions tolerated because the driver's bytes are pinned by
#: `signoff/freshness.json` (item 1.digital): editing it would invalidate the
#: recorded evidence, so its copy stays until the next re-pin of that item.
PINNED_LOCAL_DEFS = {"synth_sar_ctrl.py": {"working_tree_dirty"}}

#: Every driver in `design/sar-logic/flow/` that mints evidence records.
DRIVERS = (
    "synth_sar_ctrl.py",
    "pnr_sar_ctrl.py",
    "sta_sar_ctrl.py",
    "sta_sar_ctrl_postroute.py",
    "sta_postroute_spef.py",  # the --spef mode of the driver above (issue #481)
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

    def test_working_tree_dirty_ignores_own_prefix_only(self):
        own = ("out/",)
        self.assertFalse(flow_env.working_tree_dirty(self.repo.path, own))
        (self.repo.path / "out").mkdir()
        mine = self.repo.path / "out" / "a.txt"
        mine.write_text("x\n")
        other = self.repo.path / "other.txt"
        try:
            self.assertFalse(flow_env.working_tree_dirty(self.repo.path, own))
            other.write_text("x\n")
            self.assertTrue(flow_env.working_tree_dirty(self.repo.path, own))
        finally:
            mine.unlink()
            (self.repo.path / "out").rmdir()
            other.unlink(missing_ok=True)

    def test_liberty_path_layout(self):
        class _Pdk:
            path = Path("/pdk")

        lib = flow_env.liberty_path(_Pdk, "tt_025C_5v00")
        cl = flow_env.CELL_LIBRARY
        self.assertEqual(lib, Path("/pdk/libs.ref") / cl / "lib" / f"{cl}__tt_025C_5v00.lib")

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
                clashes = sorted((defined & FORBIDDEN_DEFS) - PINNED_LOCAL_DEFS.get(name, set()))
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
                    imported <= ALLOWED_IMPORTS,
                    f"{name} imports unexpected names from flow_env: "
                    f"{sorted(imported - ALLOWED_IMPORTS)}",
                )

    def test_flow_env_defines_every_shared_name(self):
        for name in (*SHARED_NAMES, *STA_SHARED_NAMES, *DEDUPED_NAMES):
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
        cls.synth = load_module("synth_sar_ctrl", FLOW_DIR / "synth_sar_ctrl.py")

    def test_shared_helpers_are_the_same_objects(self):
        for name in SHARED_NAMES:
            with self.subTest(helper=name):
                self.assertIs(getattr(self.synth, name), getattr(flow_env, name))

    def test_working_tree_dirty_reads_this_checkout(self):
        """The driver's pinned local helper returns a bool for the real repo
        rather than raising."""
        self.assertIsInstance(self.synth.working_tree_dirty(), bool)

    def test_record_id_of_this_repo_carries_the_current_short_sha(self):
        when = dt.datetime(2026, 9, 21, 15, 30, 0, tzinfo=dt.timezone.utc)
        rid = self.synth.record_id(self.synth.REPO_ROOT, when)
        self.assertRegex(rid, r"^20260921-153000-(?:[0-9a-f]{7,}|nogit)$")


class DriverCrossModuleAttributesExistTests(unittest.TestCase):
    """Every `synth.<name>` / `base.<name>` a driver reaches for must exist on
    the module it aliases. The record-writing paths need the PDK and tools, so
    nothing else exercises them; a dangling attribute (or a call of a pinned
    zero-arg helper with the shared two-arg signature) would only surface at
    the end of a real run."""

    #: driver -> {alias: module file it aliases}
    ALIASES = {
        "sta_sar_ctrl.py": {"synth": "synth_sar_ctrl.py"},
        "sta_sar_ctrl_postroute.py": {"synth": "synth_sar_ctrl.py"},
        "sta_postroute_spef.py": {"base": "sta_sar_ctrl_postroute.py", "synth": "synth_sar_ctrl.py"},
    }

    @staticmethod
    def _top_level_names(path: Path) -> set[str]:
        names: set[str] = set()
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        return names

    def test_aliased_module_attributes_exist(self):
        for driver, aliases in self.ALIASES.items():
            tree = ast.parse((FLOW_DIR / driver).read_text())
            for alias, target in aliases.items():
                available = self._top_level_names(FLOW_DIR / target)
                used = {
                    n.attr
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == alias
                }
                with self.subTest(driver=driver, alias=alias):
                    self.assertEqual(
                        sorted(used - available),
                        [],
                        f"{driver} uses {alias}.<name> attributes missing from {target}",
                    )


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


class KltRunnerAndStaSharedPiecesTests(unittest.TestCase):
    """`pdk_env`/`run_klt_json`/`StaError`/`CornerResult`/`verdict_table`
    (issue #537): one implementation for both STA drivers."""

    PDK = type("P", (), {"variant": "gf180mcuD", "path": Path("/pdks/gf180mcuD")})()
    RESP = {
        "worst_slack_ns": 1.5,
        "total_negative_slack_ns": 0.0,
        "setup_violation_count": 0,
        "hold_violation_count": 2,
        "fmax_mhz": 70.0,
        "estimated_power_mw": 1.0,
    }

    def test_pdk_env_points_at_the_pdk_install(self):
        env = flow_env.pdk_env(self.PDK)
        self.assertEqual((env["PDK_ROOT"], env["PDK"]), ("/pdks", "gf180mcuD"))

    def test_run_klt_json_reports_each_failure_mode_with_the_label(self):
        class Boom(RuntimeError):
            pass

        def fake(stdout, rc):
            return subprocess.CompletedProcess([], rc, stdout, "err")

        cases = (("not json", 1, "did not print JSON"), ('{"error": {"message": "m"}}', 1, "failed: m"),
                 ("{}", 2, "exited 2 with no error envelope"))
        for stdout, rc, needle in cases:
            with self.subTest(needle=needle), mock.patch.object(subprocess, "run", return_value=fake(stdout, rc)):
                with self.assertRaises(Boom) as cm:
                    flow_env.run_klt_json(Path("."), self.PDK, ["sta", "r.json"], error_cls=Boom, label="klt sta (corner c)")
                self.assertTrue(str(cm.exception).startswith("klt sta (corner c) "), str(cm.exception))
                self.assertIn(needle, str(cm.exception))

    def test_run_klt_json_returns_the_parsed_response(self):
        with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"a": 1}', "")) as run:
            out = flow_env.run_klt_json(Path("."), self.PDK, ["sta", "r.json"], error_cls=RuntimeError, label="x")
        self.assertEqual(out, {"a": 1})
        self.assertEqual(run.call_args.args[0], ["klt", "sta", "r.json", "--pdk", "gf180mcuD", "--format", "json"])

    def test_run_klt_json_ok_codes_and_pass_pdk(self):
        fake = subprocess.CompletedProcess([], 3, '{"v": 1}', "")
        with mock.patch.object(subprocess, "run", return_value=fake) as run:
            out = flow_env.run_klt_json(
                Path("."), self.PDK, ["drc", "g.gds"], error_cls=RuntimeError, label="x", ok_codes=(0, 3), pass_pdk=False
            )
        self.assertEqual(out, {"v": 1})
        self.assertEqual(run.call_args.args[0], ["klt", "drc", "g.gds", "--format", "json"])
        with mock.patch.object(subprocess, "run", return_value=fake):
            with self.assertRaises(RuntimeError):
                flow_env.run_klt_json(Path("."), self.PDK, ["drc", "g.gds"], error_cls=RuntimeError, label="x")

    def test_corner_result_and_verdict_table(self):
        r = flow_env.CornerResult("tt", "d", self.RESP)
        self.assertTrue(r.setup_pass)
        self.assertFalse(r.hold_pass)
        table = flow_env.verdict_table([r], [("Hold violators", lambda x: str(x.hold_violations))])
        head, sep, row = table.splitlines()
        self.assertEqual(head.count("|"), sep.count("|"))
        self.assertEqual(head.count("|"), row.count("|"))
        self.assertIn("| `tt` | PASS +1.5000 | +0.0000 | 2 | 70.00 | 1.0000 |", row)

    def test_sta_drivers_do_not_redefine_the_shared_pieces(self):
        shared = {"StaError", "run_klt_json", "pdk_env", "verdict_table", "_env"}
        for name in DRIVERS:
            with self.subTest(driver=name):
                tree = ast.parse((FLOW_DIR / name).read_text())
                defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
                self.assertFalse(defined & shared, f"{name} re-defines {sorted(defined & shared)}")


if __name__ == "__main__":
    unittest.main()
