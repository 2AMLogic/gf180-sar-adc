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
3. **One hasher, one mechanism** (issue #847): beyond the name-keyed check
   above, no module under `design/sar-logic/flow/` may import or reference
   `hashlib` at all -- an inline `hashlib.sha256(...)` expression has no
   `def` to name and would slip past a name-shaped net, exactly the shape
   issue #808 caught on the `layout/` side.

No PDK, no `klt`, no ngspice needed:

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import ast
import contextlib
import datetime as dt
import hashlib
import io
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from _loadmod import load_module
from test_klt_env import _hashlib_uses

REPO = Path(__file__).resolve().parents[2]
FLOW_DIR = REPO / "design" / "sar-logic" / "flow"
FLOW_ENV = FLOW_DIR / "flow_env.py"

flow_env = load_module("flow_env", FLOW_ENV)

#: The helpers `flow_env` owns. No driver in `design/sar-logic/flow/` may
#: define any of these -- under either the public name or the leading-
#: underscore name the pre-#352 copies used.
SHARED_NAMES = ("run", "git", "git_status_porcelain", "klt_version", "record_id", "sha256")
#: Added by issue #537: the `klt` runner and STA result pieces the STA drivers share.
#: Extended by issue #1133: the `klt.sta.request/1` builder, the corner-pass
#: predicate and the slack table cell the post-route STA drivers share.
STA_SHARED_NAMES = (
    "pdk_env", "run_klt_json", "StaError", "CornerResult", "verdict_table",
    "sta_request", "corner_timing_ok", "fmt_slack",
)
#: Added by issue #569: the sar_ctrl design-point constants the drivers share.
DESIGN_POINT_NAMES = (
    "TOP", "CELL_LIBRARY", "LIB_TAG", "CLOCK_PORT", "CLOCK_PERIOD_NS", "CORNERS",
    "OUT_DIR", "REPORTS_DIR", "RECORDS_DIR",
)
#: Added by issue #646: formerly copy-pasted per driver. Extended by issue
#: #1148: the append-only record writer, open-coded at eight sites. Deliberately
#: not in `SHARED_NAMES`: pinned `synth_sar_ctrl.py` still carries its own copy.
DEDUPED_NAMES = ("liberty_path", "working_tree_dirty", "write_record")
ALLOWED_IMPORTS = (
    set(SHARED_NAMES) | set(STA_SHARED_NAMES) | set(DESIGN_POINT_NAMES) | set(DEDUPED_NAMES)
)
FORBIDDEN_DEFS = set(SHARED_NAMES) | set(DEDUPED_NAMES) | {f"_{name}" for name in SHARED_NAMES}
#: Issue #801: an underscore-delimited name part that reads as a SHA digest.
#: Matching on *parts* rather than a bare `sha` substring keeps innocent names
#: (`shared_inputs`) out of the net while catching every spelling the copies
#: actually used: `sha256_file`, `_sha256`, `sha256`.
_SHA_NAME_PART = re.compile(r"^sha\d*$")
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
    "drc_pdk_cells_isolated.py",  # issue #520; migrated onto flow_env by #960
    "prove_no_net_sar_ctrl.py",  # issue #548; migrated onto flow_env by #960
    "sdf_sar_ctrl.py",  # issue #645 (T1 item 7); the per-corner SDF record
)

FLOW_REPORTS = FLOW_DIR / "sar_ctrl" / "reports"
ROUTED_DEF = REPO / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.def"
QUALIFIED_SPEF = FLOW_REPORTS / "20261104-212437-9cde5a64.mcu7t5v0.sar_ctrl.spef"

#: Committed `klt sta` requests (issue #1133), each written before the
#: consolidation by one of the four per-driver builders `sta_request`
#: replaces -- one per builder and request shape, relative-path mode only (the
#: baseline driver writes this host's absolute DEF path, so its files are not
#: portable oracles). They are the byte-level evidence that the shared builder
#: emits what the inline copies emitted: same keys, same order, same values.
COMMITTED_STA_REQUESTS = (
    (
        "20261027-011416-812549af.mcu7t5v0.sta_postroute_multicorner.sta_request.json",
        "sta_sar_ctrl_postroute.build_multicorner_request",
        {"request_dir": FLOW_REPORTS},
    ),
    (
        "20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_ref_tt_025C_3v30.sta_request.json",
        "sta_postroute_spef.build_request(corner, None)",
        {"corner": "tt_025C_3v30", "request_dir": FLOW_REPORTS},
    ),
    (
        "20261104-212437-9cde5a64.mcu7t5v0.sta_postroute_spef_tt_025C_3v30.sta_request.json",
        "sta_postroute_spef.build_request(corner, spef)",
        {"corner": "tt_025C_3v30", "request_dir": FLOW_REPORTS, "spef": QUALIFIED_SPEF},
    ),
    (
        "20261123-084121-ef8cc306.mcu7t5v0.sta_sdf.sta_request.json",
        "sdf_sar_ctrl.build_request",
        {"request_dir": FLOW_REPORTS, "spef": QUALIFIED_SPEF, "sdf": True},
    ),
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


def _is_file_hasher_name(name: str) -> bool:
    """True if `name` reads as a SHA-digest helper (`sha256_file`, `_sha256`).

    Underscore-part matching, not a substring search: `shared_inputs` is not a
    hasher.
    """
    return any(_SHA_NAME_PART.match(part) for part in name.lower().strip("_").split("_"))


class NoFlowModuleDefinesItsOwnFileHasherTests(unittest.TestCase):
    r"""The invariant that closes issue #801's gap, and it is deliberately wider
    than the `FORBIDDEN_DEFS` check above.

    `FORBIDDEN_DEFS` is an **exact-name** check over **`DRIVERS` only**, and
    that is exactly why two copies of the file hasher survived #589's
    consolidation. Its evidence grep was
    ``^def \(git\|record_id\|klt_version\|sha256\)(`` -- so
    `spef_audit.sha256_file` was invisible to it twice over: the name is not
    `sha256`, and `spef_audit.py` is not a driver (it parses SPEF/DEF/Verilog
    and mints no records, so it is correctly absent from `DRIVERS`). It had
    nonetheless become the flow tree's de-facto shared provenance hasher,
    reached as `audit.sha256_file` from eight call sites in
    `sta_postroute_spef.py` and `prove_no_net_sar_ctrl.py`.

    So this check scans **every** module in `FLOW_DIR` -- drivers and the
    helper modules they import alike -- and matches on the *shape* of the name
    rather than a fixed list, including nested and method definitions
    (`ast.walk`, not just `tree.body`). A third copy therefore cannot hide
    behind a new spelling or a non-driver filename the way the last two did.
    `flow_env.py` is the single exemption: owning this helper is its job.
    """

    def test_flow_env_is_the_only_flow_module_defining_a_file_hasher(self):
        offenders: dict[str, list[str]] = {}
        for path in sorted(FLOW_DIR.glob("*.py")):
            if path.name == "flow_env.py":
                continue
            tree = ast.parse(path.read_text(), filename=path.name)
            hashers = sorted(
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _is_file_hasher_name(node.name)
            )
            if hashers:
                offenders[path.name] = hashers
        self.assertEqual(
            offenders,
            {},
            f"these design/sar-logic/flow/ modules define their own file "
            f"hasher: {offenders} -- import `sha256` from flow_env instead "
            "(issue #801: one domain concept, one implementation; a hasher in "
            "a parsing module is how the last copy went unnoticed).",
        )

    def test_the_name_predicate_catches_the_spellings_that_slipped_through(self):
        """Guards the predicate itself: if it stopped matching these, the check
        above would pass vacuously and #801 could recur silently."""
        for name in ("sha256", "_sha256", "sha256_file", "sha1", "file_sha", "SHA256"):
            with self.subTest(name=name):
                self.assertTrue(_is_file_hasher_name(name))
        for name in ("shared_inputs", "parse_liberty_pins", "shape", "audit_agreement"):
            with self.subTest(name=name):
                self.assertFalse(_is_file_hasher_name(name))


def _hashlib_offenders(root: Path) -> dict[str, list[str]]:
    """Every module under `root` (recursively) that imports or references
    `hashlib`, as {relative path: ["line N: spelling", ...]}.

    The scan half of the mechanism-keyed net, factored out of the test below
    so `FlowHashlibNetDetectorTests` can run it over a synthetic tree --
    including a nested subdirectory, the `rglob`-vs-`glob` edge the name-keyed
    guard's `glob("*.py")` would miss -- without writing anything into the
    repository. The detection half is `_hashlib_uses`, imported from
    `test_klt_env` (#846) so there is exactly one AST walk for this invariant.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        uses = [f"line {line}: {what}" for line, what in _hashlib_uses(tree)]
        if uses:
            offenders[str(path.relative_to(root))] = uses
    return offenders


class NoFlowModuleUsesHashlibDirectlyTests(unittest.TestCase):
    r"""The mechanism-keyed half of the same invariant (issue #847), the
    `design/sar-logic/flow/` counterpart of
    `test_klt_env.NoLayoutModuleUsesHashlibDirectlyTests`.

    The name-keyed guard above matches *definitions*, and that is exactly its
    blind spot: an inline
    `hashlib.sha256(open(p, "rb").read()).hexdigest()` -- the shape issue #808
    found on the `layout/` side (`array_edge_margin.py:210`) -- has no `def`
    to name and would pass it silently. So this net is keyed on the
    mechanism: **no module under `design/sar-logic/flow/` may import or
    reference `hashlib`.** Both nets stay: they catch different shapes.

    No exemption is carved out for `flow_env.py`: measured, it contains zero
    `hashlib` hits -- `flow_env.sha256` delegates to `klt_env.sha256`
    (pinned by `SharedFileHasherTests.test_delegates_to_klt_env_...`) --
    so an exemption would guard nothing, unlike `klt_env.py` where it is
    load-bearing. The scan uses `rglob` for the same reason the `layout/`
    net does: a future flow subdirectory must be scanned too.
    """

    def test_no_flow_module_uses_hashlib(self):
        offenders = _hashlib_offenders(FLOW_DIR)
        self.assertEqual(
            offenders,
            {},
            "these design/sar-logic/flow/ modules import or reference "
            f"hashlib directly: {offenders} -- flow_env owns the file hasher "
            "(delegating to layout/klt_env.sha256); import `sha256` from "
            "flow_env instead (issues #801/#847: one domain concept, one "
            "implementation).",
        )

    def test_flow_env_exemption_is_genuinely_unneeded(self):
        """Pins the measurement behind omitting the `flow_env.py` exemption:
        the module must reach its hasher by delegation, not by importing
        `hashlib` itself. If this ever fails, the maintainer must choose --
        route through `klt_env` again, or carve an exemption explicitly the
        way `test_klt_env` does for `klt_env.py` -- rather than let the scan
        above start matching the one module it exists to route around."""
        self.assertEqual(_hashlib_uses(ast.parse(FLOW_ENV.read_text())), [])


class FlowHashlibNetDetectorTests(unittest.TestCase):
    """Guards the detector itself: if it stopped matching these shapes, the
    scan above would pass vacuously and #808's layout-side shape could recur
    in the flow tree silently."""

    def test_flags_the_inline_expression_the_name_net_is_blind_to(self):
        # The shape issue #808 found on the layout side -- an expression, not
        # a definition, so there is no `def` for the name-keyed guard to see.
        synthetic = (
            "import hashlib\n"
            'result = {"record_sha256": hashlib.sha256(open(REC, "rb").read()).hexdigest()}\n'
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

    def test_scan_reaches_a_nested_subdirectory(self):
        """The `rglob` half of the net: an offender in a flow subdirectory
        (none exists today -- all 15 modules are top-level) must still be
        reported, with its path relative to the scanned root."""
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "audit" / "deep"
            nested.mkdir(parents=True)
            (nested / "inline_hash.py").write_text(
                "import hashlib\n"
                '{"sha256": hashlib.sha256(open(P, "rb").read()).hexdigest()}\n'
            )
            (Path(tmp) / "clean.py").write_text(
                "import flow_env\n\n"
                "def record_sha256(path):\n"
                "    return flow_env.sha256(path)\n"
            )
            offenders = _hashlib_offenders(Path(tmp))
        self.assertEqual(sorted(offenders), ["audit/deep/inline_hash.py"])

    def test_does_not_flag_a_delegating_flow_module(self):
        # The correct consumer pattern: route through the shared hasher,
        # exactly what `flow_env.sha256` itself does via `klt_env`.
        delegating = (
            "import flow_env\n"
            "\n"
            "def record_sha256(path):\n"
            "    return flow_env.sha256(path)\n"
        )
        self.assertEqual(_hashlib_uses(ast.parse(delegating)), [])


class SharedFileHasherTests(unittest.TestCase):
    """Behavior of `flow_env.sha256`, the one hasher the flow drivers now use.

    These pin the property that made issue #801's consolidation safe to land
    with **no evidence regenerated**: the three implementations it replaced read
    the file in different chunk sizes (`1 << 20` in `spef_audit.sha256_file`,
    65536 in `run_extract_parasitics._sha256` and `klt_env.sha256`), but
    SHA-256 is defined over the byte stream, so the digest is independent of
    chunking. Every `*_sha256` value already committed to an evidence record
    therefore stays valid, and a reader re-deriving one with `sha256sum` gets
    the same answer.
    """

    #: Larger than the biggest chunk size any replaced copy used (`1 << 20`),
    #: so a multi-chunk read is actually exercised rather than assumed.
    PAYLOAD = (b"sar_ctrl provenance payload \x00\xff" * 70_000)

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls._tmp.name) / "artifact.bin"
        cls.path.write_bytes(cls.PAYLOAD)
        cls.empty = Path(cls._tmp.name) / "empty.bin"
        cls.empty.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_digest_matches_a_whole_file_hashlib_read(self):
        self.assertEqual(flow_env.sha256(self.path), hashlib.sha256(self.PAYLOAD).hexdigest())

    def test_digest_is_independent_of_read_chunk_size(self):
        """The claim #801 rests on: `1 << 20` and 65536 chunking agree."""
        self.assertGreater(len(self.PAYLOAD), 1 << 20, "payload must span several chunks")
        for chunk in (1, 1024, 65536, 1 << 20):
            with self.subTest(chunk=chunk):
                digest = hashlib.sha256()
                with open(self.path, "rb") as fh:
                    for block in iter(lambda: fh.read(chunk), b""):
                        digest.update(block)
                self.assertEqual(flow_env.sha256(self.path), digest.hexdigest())

    def test_digest_of_an_empty_file(self):
        self.assertEqual(flow_env.sha256(self.empty), hashlib.sha256(b"").hexdigest())

    def test_accepts_a_str_path_as_well_as_a_path(self):
        """Call sites pass both: `Path` in the flow drivers, `str` in
        `run_extract_parasitics.py`."""
        self.assertEqual(flow_env.sha256(str(self.path)), flow_env.sha256(self.path))

    def test_delegates_to_klt_env_rather_than_reimplementing(self):
        """The anti-drift assertion, same argument as `git` and `record_id`:
        `flow_env.sha256` must *route to* `klt_env.sha256`, not carry a second
        hashing loop that could drift from the `layout/` runners' own."""
        with mock.patch.object(
            flow_env.klt_env, "sha256", return_value="sentinel"
        ) as shared:
            self.assertEqual(flow_env.sha256(self.path), "sentinel")
        shared.assert_called_once_with(self.path)

    def test_missing_file_raises_rather_than_returning_a_digest(self):
        """A hasher that quietly returned a digest for a missing artifact would
        stamp a record with a hash of nothing."""
        with self.assertRaises(OSError):
            flow_env.sha256(Path(self._tmp.name) / "does-not-exist.bin")


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

    #: Shared names this particular driver has no use for, so `assertIs` has
    #: nothing to compare. `run`: both its `klt` calls go through
    #: `run_klt_json`. `sha256` (#801): it hashes no input files -- the
    #: `*_sha256` fields in its records come from `klt`'s own response. The AST
    #: checks above still forbid it defining either one locally.
    NOT_IMPORTED_HERE = ("run", "sha256")

    def test_shared_helpers_are_the_same_objects(self):
        for name in (*(n for n in SHARED_NAMES if n not in self.NOT_IMPORTED_HERE), "run_klt_json"):
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

    #: driver -> {alias: module file it aliases}. The STA drivers reach
    #: `datetime` through their own import (issue #1108), so the one real
    #: cross-driver import left is `--spef` mode's `base`.
    ALIASES = {
        "sta_postroute_spef.py": {"base": "sta_sar_ctrl_postroute.py"},
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

    def test_every_configured_alias_is_actually_imported(self):
        """A configured alias the driver never imports passes the attribute
        subtest above vacuously (`used` is empty) -- exactly what the stale
        `synth` entry for `sta_postroute_spef.py` did until #960 removed it."""
        for driver, aliases in self.ALIASES.items():
            tree = ast.parse((FLOW_DIR / driver).read_text())
            imported = {
                alias.name.split(".")[0]
                for node in tree.body
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            for alias, target in aliases.items():
                with self.subTest(driver=driver, alias=alias):
                    self.assertIn(
                        Path(target).stem,
                        imported,
                        f"{driver} configures alias `{alias}` for {target} but "
                        f"never imports that module",
                    )


class NoDuplicateProvenancePlumbingLeftTests(unittest.TestCase):
    """Belt-and-braces on the textual level: the pre-#352 bodies are gone.

    Issue #960 widened this from `DRIVERS` to every module under
    `design/sar-logic/flow/` (exempting `flow_env.py`, the owner -- same
    shape as `NoFlowModuleUsesHashlibDirectlyTests`): the last direct `git`
    subprocess (`drc_pdk_cells_isolated.py`) escaped the check only because
    it landed after #352 froze `DRIVERS`, and a future module must not be
    able to hide outside that list the same way.
    """

    #: The `cwd=REPO_ROOT` subprocess idiom the duplicated copies shared.
    _OLD_BODY = re.compile(r"subprocess\.run\(\s*\[\s*\"git\"")

    def test_no_flow_module_shells_out_to_git_directly(self):
        offenders: dict[str, int] = {}
        for path in sorted(FLOW_DIR.rglob("*.py")):
            if path.name == "flow_env.py":
                continue
            hits = self._OLD_BODY.findall(path.read_text())
            if hits:
                offenders[str(path.relative_to(FLOW_DIR))] = len(hits)
        self.assertEqual(
            offenders,
            {},
            "these design/sar-logic/flow/ modules shell out to git directly: "
            f"{offenders} -- use flow_env.git()/flow_env.git_status_porcelain() "
            "(issue #352).",
        )


class ProveNoNetImportsWithoutTheStaDriversTests(unittest.TestCase):
    """Issue #960: `prove_no_net_sar_ctrl.py` is an offline connectivity
    prover -- it must reach its constants via `flow_env`, not by importing
    `sta_sar_ctrl_postroute` (and transitively `synth_sar_ctrl`, ~1,100
    lines of STA/synthesis drivers). Checked in a subprocess so this
    suite's own imports cannot pollute `sys.modules`."""

    _MUST_NOT_LOAD = ("sta_sar_ctrl_postroute", "synth_sar_ctrl")

    def test_imports_without_the_sta_or_synth_drivers(self):
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(FLOW_DIR)!r})\n"
            "import prove_no_net_sar_ctrl\n"
            f"leaked = [m for m in {self._MUST_NOT_LOAD!r} if m in sys.modules]\n"
            "sys.stderr.write(','.join(leaked))\n"
            "sys.exit(1 if leaked else 0)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        self.assertEqual(
            result.returncode,
            0,
            f"importing prove_no_net_sar_ctrl loaded: {result.stderr.strip()}",
        )


class StaDriversImportWithoutTheSynthDriverTests(unittest.TestCase):
    """Issue #1108: the STA drivers reach `datetime` through their own
    `import datetime as _dt`, like every other driver here -- they must not
    import `synth_sar_ctrl` (~550 lines of synthesis driver) just to borrow
    its private `_dt` alias. Checked in a subprocess so this suite's own
    imports cannot pollute `sys.modules`."""

    #: Each driver gets its own interpreter, so one driver's leak can never
    #: be masked by another's having loaded the module first
    #: (`sta_postroute_spef` imports `sta_sar_ctrl_postroute`).
    _DRIVERS = ("sta_sar_ctrl", "sta_sar_ctrl_postroute", "sta_postroute_spef")
    _MUST_NOT_LOAD = ("synth_sar_ctrl",)

    def test_imports_without_the_synthesis_driver(self):
        for module in self._DRIVERS:
            with self.subTest(module=module):
                code = (
                    "import sys\n"
                    f"sys.path.insert(0, {str(FLOW_DIR)!r})\n"
                    f"import {module}\n"
                    f"leaked = [m for m in {self._MUST_NOT_LOAD!r} if m in sys.modules]\n"
                    "sys.stderr.write(','.join(leaked))\n"
                    "sys.exit(1 if leaked else 0)\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", code], capture_output=True, text=True
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"importing {module} loaded: {result.stderr.strip()}",
                )


class KltRunnerAndStaSharedPiecesTests(unittest.TestCase):
    """`pdk_env`/`run_klt_json`/`StaError`/`CornerResult`/`verdict_table`
    (issue #537) and `sta_request`/`corner_timing_ok`/`fmt_slack` (issue
    #1133): one implementation for the post-route STA drivers."""

    PDK = type("P", (), {"variant": "gf180mcuD", "path": Path("/pdks/gf180mcuD")})()
    RESP = {
        "worst_slack_ns": 1.5,
        "total_negative_slack_ns": 0.0,
        "setup_violation_count": 0,
        "hold_violation_count": 2,
        "fmax_mhz": 70.0,
        "estimated_power_mw": 1.0,
    }
    #: The keys every `klt.sta.request/1` carries, in the order each
    #: per-driver builder emitted them: key order is part of what keeps the
    #: committed request JSON byte-identical under `json.dumps(indent=2)`.
    REQUEST_KEYS = ("schema", "def", "hdl_toplevel", "pdk", "constraints", "geometry_source")
    REQUESTS = Path("/repo/design/sar-logic/flow/sar_ctrl/reports")
    DEF = Path("/repo/layout/adc-top/sar_ctrl/sar_ctrl.def")
    SPEF = REQUESTS / "x.mcu7t5v0.sar_ctrl.spef"
    ALL_CORNERS = [c for c, _ in flow_env.CORNERS]

    def entry(self, **changes) -> dict:
        """A passing corner entry carrying every field a predicate reads."""
        return {
            "timing_status": "constrained",
            "worst_slack_ns": 1.0,
            "worst_hold_slack_ns": 0.1,
            "spef_annotation": {"annotation_complete": True},
            **changes,
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

    def test_sta_request_single_corner_keeps_the_absolute_def(self):
        req = flow_env.sta_request(self.DEF, corner="tt_025C_3v30")
        self.assertEqual(list(req), list(self.REQUEST_KEYS))
        self.assertEqual(
            req,
            {
                "schema": "klt.sta.request/1",
                "def": str(self.DEF),
                "hdl_toplevel": flow_env.TOP,
                "pdk": {"cell_library": flow_env.CELL_LIBRARY, "corner": "tt_025C_3v30"},
                "constraints": {"clock_port": flow_env.CLOCK_PORT, "clock_period_ns": flow_env.CLOCK_PERIOD_NS},
                "geometry_source": "routed",
            },
        )

    def test_sta_request_sweeps_every_corner_unless_told_otherwise(self):
        self.assertEqual(len(self.ALL_CORNERS), 5)
        for kwargs in ({}, {"corners": None}):
            with self.subTest(kwargs=kwargs):
                req = flow_env.sta_request(self.DEF, **kwargs)
                self.assertEqual(list(req), list(self.REQUEST_KEYS))
                self.assertEqual(req["pdk"], {"cell_library": flow_env.CELL_LIBRARY, "corners": self.ALL_CORNERS})
        for corners in (["ss_n40C_3v00"], ["ff_125C_3v60", "tt_025C_3v30"]):
            with self.subTest(corners=corners):
                req = flow_env.sta_request(self.DEF, corners=corners)
                self.assertEqual(req["pdk"], {"cell_library": flow_env.CELL_LIBRARY, "corners": corners})

    def test_sta_request_copies_the_callers_corner_list(self):
        mine = ["ff_125C_3v60", "tt_025C_3v30"]
        req = flow_env.sta_request(self.DEF, corners=mine)
        self.assertIsNot(req["pdk"]["corners"], mine)
        mine.append("ss_125C_3v00")
        self.assertEqual(req["pdk"]["corners"], ["ff_125C_3v60", "tt_025C_3v30"])

    def test_sta_request_rejects_corner_and_corners_together(self):
        with self.assertRaises(ValueError):
            flow_env.sta_request(self.DEF, corner="tt_025C_3v30", corners=self.ALL_CORNERS)

    def test_sta_request_relativizes_both_paths_to_request_dir_only_when_given(self):
        relative = flow_env.sta_request(self.DEF, corner="c", request_dir=self.REQUESTS, spef=self.SPEF)
        self.assertEqual(relative["def"], os.path.relpath(self.DEF, self.REQUESTS))
        self.assertEqual(relative["spef"], "x.mcu7t5v0.sar_ctrl.spef")
        absolute = flow_env.sta_request(self.DEF, corner="c", spef=self.SPEF)
        self.assertEqual((absolute["def"], absolute["spef"]), (str(self.DEF), str(self.SPEF)))

    def test_sta_request_optional_keys_follow_geometry_source_in_order(self):
        for kwargs, keys in (
            ({}, list(self.REQUEST_KEYS)),
            ({"spef": self.SPEF}, [*self.REQUEST_KEYS, "spef"]),
            ({"sdf": True}, [*self.REQUEST_KEYS, "sdf"]),
            ({"spef": self.SPEF, "sdf": True}, [*self.REQUEST_KEYS, "spef", "sdf"]),
        ):
            with self.subTest(kwargs=kwargs):
                req = flow_env.sta_request(self.DEF, **kwargs)
                self.assertEqual(list(req), keys)
                self.assertEqual(req.get("sdf"), True if kwargs.get("sdf") else None)

    def test_sta_request_reproduces_each_committed_request_byte_for_byte(self):
        for name, _, kwargs in COMMITTED_STA_REQUESTS:
            with self.subTest(request=name):
                text = json.dumps(flow_env.sta_request(ROUTED_DEF, **kwargs), indent=2) + "\n"
                self.assertEqual(text, (FLOW_REPORTS / name).read_text())

    def test_corner_timing_ok_passes_a_constrained_corner_that_meets_both_budgets(self):
        ok = flow_env.corner_timing_ok
        for kwargs in ({}, {"require_spef_annotation": True}):
            with self.subTest(kwargs=kwargs):
                self.assertTrue(ok(self.entry(), **kwargs))
                self.assertTrue(ok(self.entry(worst_slack_ns=0, worst_hold_slack_ns=0), **kwargs), "zero slack meets the budget")

    def test_corner_timing_ok_fails_a_violating_or_unconstrained_corner(self):
        ok = flow_env.corner_timing_ok
        for changes in (
            {"worst_slack_ns": -0.01},
            {"worst_hold_slack_ns": -0.01},
            {"timing_status": "unconstrained"},
            {"timing_status": None},
        ):
            for kwargs in ({}, {"require_spef_annotation": True}):
                with self.subTest(changes=changes, kwargs=kwargs):
                    self.assertFalse(ok(self.entry(**changes), **kwargs))

    def test_corner_timing_ok_fails_unreported_slack_without_raising(self):
        ok = flow_env.corner_timing_ok
        unreported = [
            {"timing_status": "constrained"},
            self.entry(worst_slack_ns=None, worst_hold_slack_ns=None),
            self.entry(timing_status="unconstrained", worst_slack_ns=None, worst_hold_slack_ns=None),
        ]
        for field in ("worst_slack_ns", "worst_hold_slack_ns"):
            unreported.append(self.entry(**{field: None}))
            absent = self.entry()
            del absent[field]
            unreported.append(absent)
        for entry in unreported:
            for kwargs in ({}, {"require_spef_annotation": True}):
                with self.subTest(entry=entry, kwargs=kwargs):
                    self.assertIs(ok(entry, **kwargs), False)

    def test_corner_timing_ok_reads_the_annotation_block_only_when_asked(self):
        ok = flow_env.corner_timing_ok
        for annotation in ({"annotation_complete": False}, {}, None, "absent"):
            entry = self.entry()
            if annotation == "absent":
                del entry["spef_annotation"]
            else:
                entry["spef_annotation"] = annotation
            with self.subTest(annotation=annotation):
                self.assertTrue(ok(entry), "the multi-corner rule does not read the annotation block")
                self.assertFalse(ok(entry, require_spef_annotation=True))

    def test_fmt_slack_keeps_the_record_format_and_marks_unreported_slack(self):
        for value, text in ((1.14644, "+1.1464"), (0, "+0.0000"), (-0.25, "-0.2500")):
            with self.subTest(value=value):
                self.assertEqual(flow_env.fmt_slack(value), text)
        self.assertEqual(flow_env.fmt_slack(None), "n/a")
        self.assertEqual(flow_env.fmt_slack({}.get("worst_slack_ns")), "n/a", "an absent key reads as None through .get()")

    def test_sta_drivers_do_not_redefine_the_shared_pieces(self):
        shared = {
            "StaError", "run_klt_json", "pdk_env", "verdict_table", "_env",
            "sta_request", "corner_timing_ok", "fmt_slack",
        }
        for name in DRIVERS:
            with self.subTest(driver=name):
                tree = ast.parse((FLOW_DIR / name).read_text())
                defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
                self.assertFalse(defined & shared, f"{name} re-defines {sorted(defined & shared)}")


class StaDriversDelegateTheRequestAndVerdictTests(unittest.TestCase):
    """Issue #1133, the live half: the four per-driver `klt.sta.request/1`
    builders and the two corner predicates are one-line delegates to
    `flow_env.sta_request` / `flow_env.corner_timing_ok`.

    The AST nets above forbid a driver redefining those names, but cannot see
    a delegate that quietly drifts -- a default swapped, a key added. So the
    three drivers are loaded and each builder is asked to reproduce, byte for
    byte, a request it committed before the consolidation, and each predicate
    is compared with its pre-consolidation body (restated verbatim below)
    over every `timing_status` x setup x hold x annotation combination.
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(FLOW_DIR))  # `sta_postroute_spef` imports its sibling modules by bare name
        cls.base = load_module("sta_sar_ctrl_postroute", FLOW_DIR / "sta_sar_ctrl_postroute.py")
        cls.spef = load_module("sta_postroute_spef", FLOW_DIR / "sta_postroute_spef.py")
        cls.sdf = load_module("sdf_sar_ctrl", FLOW_DIR / "sdf_sar_ctrl.py")

    def _built(self) -> list[tuple[str, dict, dict]]:
        """(builder, what the driver's delegate emits, what `sta_request`
        emits for the same request): every builder, in every shape it is
        called. `build_sta_request` has no committed oracle -- it writes this
        host's absolute DEF path -- so it is checked against `sta_request`
        and the literal dict in `KltRunnerAndStaSharedPiecesTests` only."""
        reports, spef, routed = self.base.REPORTS_DIR, self.sdf.QUALIFIED_SPEF, self.base.ROUTED_DEF
        corner = flow_env.CORNERS[0][0]
        return [
            ("sta_sar_ctrl_postroute.build_sta_request",
             self.base.build_sta_request(corner), flow_env.sta_request(routed, corner=corner)),
            ("sta_sar_ctrl_postroute.build_multicorner_request",
             self.base.build_multicorner_request(reports), flow_env.sta_request(routed, request_dir=reports)),
            ("sta_postroute_spef.build_request(corner, None)",
             self.spef.build_request(corner, None), flow_env.sta_request(routed, corner=corner, request_dir=reports)),
            ("sta_postroute_spef.build_request(corner, spef)",
             self.spef.build_request(corner, spef),
             flow_env.sta_request(routed, corner=corner, request_dir=reports, spef=spef)),
            ("sdf_sar_ctrl.build_request",
             self.sdf.build_request(reports), flow_env.sta_request(routed, request_dir=reports, spef=spef, sdf=True)),
        ]

    def test_every_builder_emits_what_sta_request_emits(self):
        for builder, got, want in self._built():
            with self.subTest(builder=builder):
                self.assertEqual(list(got), list(want))
                self.assertEqual(json.dumps(got, indent=2), json.dumps(want, indent=2))

    def test_every_builder_still_writes_the_request_it_committed(self):
        built = {builder: got for builder, got, _ in self._built()}
        for name, builder, _ in COMMITTED_STA_REQUESTS:
            with self.subTest(request=name):
                self.assertEqual(json.dumps(built[builder], indent=2) + "\n", (FLOW_REPORTS / name).read_text())

    @staticmethod
    def _reported_slack_entries() -> list[dict]:
        """Every `timing_status` x setup x hold x annotation combination a
        `klt sta` response carries when it reports both slacks."""
        return [
            {"timing_status": status, "worst_slack_ns": setup, "worst_hold_slack_ns": hold, "spef_annotation": ann}
            for status, setup, hold, ann in itertools.product(
                ("constrained", "unconstrained", None),
                (1.0, 0.0, -0.5),
                (0.1, 0.0, -0.5),
                ({"annotation_complete": True}, {"annotation_complete": False}, {}, None),
            )
        ]

    @staticmethod
    def _pre_1133_corner_ok(entry: dict) -> bool:
        """`sdf_sar_ctrl.corner_ok` exactly as written before #1133."""
        annotation = entry.get("spef_annotation") or {}
        return (
            entry.get("timing_status") == "constrained"
            and entry.get("worst_slack_ns") is not None
            and entry["worst_slack_ns"] >= 0
            and entry.get("worst_hold_slack_ns") is not None
            and entry["worst_hold_slack_ns"] >= 0
            and annotation.get("annotation_complete") is True
        )

    @staticmethod
    def _pre_1133_multicorner_corner_ok(entry: dict) -> bool:
        """`sta_sar_ctrl_postroute._corner_ok` exactly as written before #1133."""
        return (
            entry.get("timing_status") == "constrained"
            and entry["worst_slack_ns"] >= 0
            and entry["worst_hold_slack_ns"] >= 0
        )

    def test_corner_predicates_keep_their_verdicts_on_reported_slack(self):
        entries = self._reported_slack_entries()
        self.assertEqual(len(entries), 3 * 3 * 3 * 4)
        for pre_1133 in (self._pre_1133_corner_ok, self._pre_1133_multicorner_corner_ok):
            self.assertEqual(sorted({pre_1133(e) for e in entries}), [False, True], "the oracle must not be vacuous")
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertEqual(self.sdf.corner_ok(entry), self._pre_1133_corner_ok(entry))
                self.assertEqual(self.base._corner_ok(entry), self._pre_1133_multicorner_corner_ok(entry))

    def test_corner_predicates_are_corner_timing_ok(self):
        for entry in self._reported_slack_entries():
            with self.subTest(entry=entry):
                self.assertIs(self.sdf.corner_ok(entry), flow_env.corner_timing_ok(entry, require_spef_annotation=True))
                self.assertIs(self.base._corner_ok(entry), flow_env.corner_timing_ok(entry))

    def test_corner_predicates_fail_unreported_slack_without_raising(self):
        passing = {
            "timing_status": "constrained", "worst_slack_ns": 1.0, "worst_hold_slack_ns": 0.1,
            "spef_annotation": {"annotation_complete": True},
        }
        unreported = [{"timing_status": "constrained"}]
        for field in ("worst_slack_ns", "worst_hold_slack_ns"):
            unreported.append({**passing, field: None})
            absent = dict(passing)
            del absent[field]
            unreported.append(absent)
        for entry in unreported:
            with self.subTest(entry=entry):
                self.assertIs(self.base._corner_ok(entry), False)
                self.assertIs(self.sdf.corner_ok(entry), False)


class WriteRecordTests(unittest.TestCase):
    """`flow_env.write_record` (issue #1148): the one append-only record
    writer for the `design/sar-logic/flow/` drivers.

    It was eight copies of one three-step sequence -- create the directory,
    refuse an existing path, write -- and the last two steps were separate,
    so a record created between them was overwritten. The refusal is now the
    open call itself (``"x"``, exclusive creation). The wording is pinned
    because five drivers print the exception as their own ``ERROR:`` line
    (six sites) and `pnr_sar_ctrl.py` raises it as `PnrError`: every copy
    said exactly this.
    """

    TEXT = "# Record 20261128-011203-abcdef12.mcu7t5v0.sta\n\n- **Corner**: `tt_025C_3v30` (25 °C) — ±0.0 µm² ✓\n"
    SENTINEL = b"the record an earlier run minted\n"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        #: Under a `records/` directory that does not exist yet, as on a
        #: driver's first run into a fresh checkout.
        self.path = Path(tmp.name) / "records" / "20261128-011203-abcdef12.mcu7t5v0.sta.md"

    def _minted(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.SENTINEL)

    def test_creates_the_record_directory_and_writes_the_text(self):
        self.assertFalse(self.path.parent.exists())
        returned = flow_env.write_record(self.path, self.TEXT)
        self.assertEqual(returned, self.path)
        self.assertEqual(self.path.read_bytes(), self.TEXT.encode("utf-8"))

    def test_opens_exclusively_as_utf8_whatever_the_locale(self):
        with mock.patch("builtins.open", mock.mock_open()) as opened:
            flow_env.write_record(self.path, self.TEXT)
        opened.assert_called_once_with(self.path, "x", encoding="utf-8")
        opened().write.assert_called_once_with(self.TEXT)

    def test_refuses_an_existing_record_with_the_wording_every_copy_used(self):
        self._minted()
        with self.assertRaises(FileExistsError) as cm:
            flow_env.write_record(self.path, self.TEXT)
        self.assertEqual(str(cm.exception), f"record {self.path} already exists -- refusing to overwrite")
        self.assertEqual(self.path.read_bytes(), self.SENTINEL)

    def test_error_cls_names_the_refusal_and_nothing_else(self):
        """`pnr_sar_ctrl.py` passes `error_cls` on every write, so a fresh
        record is still written and only the refusal carries the type."""
        class PnrError(RuntimeError):
            pass

        self.assertEqual(flow_env.write_record(self.path, self.TEXT, error_cls=PnrError), self.path)
        self.assertEqual(self.path.read_bytes(), self.TEXT.encode("utf-8"))
        with self.assertRaises(PnrError) as cm:
            flow_env.write_record(self.path, self.TEXT, error_cls=PnrError)
        self.assertNotIsInstance(cm.exception, FileExistsError)
        self.assertEqual(str(cm.exception), f"record {self.path} already exists -- refusing to overwrite")
        self.assertEqual(self.path.read_bytes(), self.TEXT.encode("utf-8"))

    @staticmethod
    def _pre_1148_copy(path: Path, text: str) -> None:
        """The sequence every driver carried before #1148, verbatim."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"record {path} already exists -- refusing to overwrite")
        path.write_text(text)

    def test_the_pre_1148_copy_overwrote_a_record_created_after_its_check(self):
        """The control for the test below, and the defect in one line: with
        `exists()` answering False for a file that is there -- the window
        between the check and the write, closed the other way -- the old
        sequence overwrote the record."""
        self._minted()
        with mock.patch.object(Path, "exists", return_value=False):
            self._pre_1148_copy(self.path, self.TEXT)
        self.assertEqual(self.path.read_bytes(), self.TEXT.encode("utf-8"))

    def test_write_record_refuses_that_same_record(self):
        self._minted()
        with mock.patch.object(Path, "exists", return_value=False):
            with self.assertRaises(FileExistsError):
                flow_env.write_record(self.path, self.TEXT)
        self.assertEqual(self.path.read_bytes(), self.SENTINEL)

    def test_every_committed_record_round_trips_byte_for_byte(self):
        """No record already committed changes under the new writer: its text,
        written again by `write_record`, is the committed bytes. The records
        minted before #1148 were written by `write_text` under the locale
        default; measured at `03f0f516` (17 records), all are pure ASCII with
        LF newlines, so the explicit UTF-8 here cannot differ from that
        default on any host."""
        records = sorted((FLOW_DIR / "sar_ctrl" / "records").glob("*.md"))
        self.assertTrue(records)
        for record in records:
            with self.subTest(record=record.name):
                out = self.path.parent / record.name
                flow_env.write_record(out, record.read_text())
                self.assertEqual(out.read_bytes(), record.read_bytes())


class NoFlowModuleKeepsItsOwnCopyOfTheRecordGuardTests(unittest.TestCase):
    """Issue #1148's non-recurrence net: the refusal every open-coded copy
    carried -- ``record <path> already exists -- refusing to overwrite`` --
    lives in `flow_env.py` alone, with two deliberate exceptions.

    Same shape as `NoDuplicateProvenancePlumbingLeftTests`: a text-level scan
    over every module under `design/sar-logic/flow/`, not only `DRIVERS`, so
    a new module cannot re-fork the guard outside the list.
    `synth_sar_ctrl.py` is exempt for the reason `PINNED_LOCAL_DEFS` gives:
    its bytes are pinned by `signoff/freshness.json`, so its copy stays until
    the next re-pin. `drc_pdk_cells_isolated.py` is the one driver that still
    says it: it checks before it runs four `klt drc` jobs, so a re-run under a
    taken record ID fails fast instead of after the runs. Its record is still
    written through the shared writer, and the last test here holds it to
    exactly that.
    """

    _GUARD = "already exists -- refusing to overwrite"
    _FAIL_FAST_ONLY = {"drc_pdk_cells_isolated.py"}

    def test_flow_env_is_the_only_unpinned_module_carrying_the_guard(self):
        exempt = {"flow_env.py", *PINNED_LOCAL_DEFS, *self._FAIL_FAST_ONLY}
        offenders = [
            str(path.relative_to(FLOW_DIR))
            for path in sorted(FLOW_DIR.rglob("*.py"))
            if path.name not in exempt and self._GUARD in path.read_text()
        ]
        self.assertEqual(
            offenders,
            [],
            "these design/sar-logic/flow/ modules carry their own copy of the "
            f"append-only guard: {offenders} -- write through "
            "flow_env.write_record() instead (issue #1148: eight copies of one "
            "check-then-write sequence, with a window in each).",
        )

    def test_the_pinned_exemption_is_load_bearing(self):
        """If this fails, `synth_sar_ctrl.py` no longer carries the guard:
        drop it from the exemption above rather than leave it guarding nothing."""
        self.assertIn(self._GUARD, (FLOW_DIR / "synth_sar_ctrl.py").read_text())

    def test_the_isolated_drc_driver_keeps_only_its_fail_fast_check(self):
        """The other exemption, as narrow as it reads: the wording once (the
        check before the `klt drc` runs), and the record itself created by the
        shared writer -- not `write_text`, which would reopen the window."""
        text = (FLOW_DIR / "drc_pdk_cells_isolated.py").read_text()
        self.assertEqual(text.count(self._GUARD), 1)
        self.assertNotIn("rec_path.write_text(", text)
        self.assertIn("write_record(rec_path, ", text)
        self.assertLess(text.index(self._GUARD), text.index('subprocess.run(["klt", "drc"'))


class DriversDelegateTheRecordWriteTests(unittest.TestCase):
    """Issue #1148, the driver half: the seven unpinned drivers write their
    records through `flow_env.write_record`, under the name each imported.

    Two of them -- `sta_sar_ctrl_postroute.py` and `sta_postroute_spef.py` --
    take a ``write_record: bool`` mode flag in the very function that writes
    the record, so the bare name is a bool there; they import the helper as
    `_write_record`. The AST checks see that each call site uses the name the
    module imported (a swap is a `NameError`, or ``'bool' object is not
    callable``, at the end of a real run), and the live ones, that the name
    is `flow_env`'s own function.
    """

    #: module file -> the name its record writer is bound to. `pnr_sar_ctrl.py`
    #: (pulls in `gen_adc_top`, which needs the pip `klayout` package) and
    #: `drc_pdk_cells_isolated.py` (imports `klayout.db`) are covered by the
    #: AST checks only, as in `SynthDriverUsesTheSharedObjectsTests`.
    LOADABLE = {
        "prove_no_net_sar_ctrl.py": "write_record",
        "sdf_sar_ctrl.py": "write_record",
        "sta_sar_ctrl.py": "write_record",
        "sta_sar_ctrl_postroute.py": "_write_record",
        "sta_postroute_spef.py": "_write_record",  # imports the module above by bare name
    }
    UNPINNED = tuple(name for name in DRIVERS if name not in PINNED_LOCAL_DEFS)

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(FLOW_DIR))  # `sta_postroute_spef` imports its sibling modules by bare name
        cls.addClassCleanup(cls._drop_flow_dir)

    @classmethod
    def _drop_flow_dir(cls) -> None:
        sys.path.remove(str(FLOW_DIR))

    @staticmethod
    def _record_writer_aliases(name: str) -> dict[str, str]:
        """{the name `name` binds the record writer to: its name in `flow_env`}."""
        tree = ast.parse((FLOW_DIR / name).read_text(), filename=name)
        return {
            alias.asname or alias.name: alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "flow_env"
            for alias in node.names
            if alias.name == "write_record"
        }

    @staticmethod
    def _record_writer_calls(name: str) -> set[str]:
        """The names `name` calls a record writer by -- the bare name or the alias."""
        tree = ast.parse((FLOW_DIR / name).read_text(), filename=name)
        return {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ("write_record", "_write_record")
        }

    def test_every_unpinned_driver_imports_the_shared_writer(self):
        self.assertEqual(len(self.UNPINNED), 7)
        for name in self.UNPINNED:
            with self.subTest(driver=name):
                self.assertEqual(sorted(self._record_writer_aliases(name).values()), ["write_record"])

    def test_every_unpinned_driver_calls_the_writer_under_the_name_it_imported(self):
        for name in self.UNPINNED:
            with self.subTest(driver=name):
                bound = set(self._record_writer_aliases(name))
                called = self._record_writer_calls(name)
                self.assertTrue(called, f"{name} imports the record writer but never calls it")
                self.assertEqual(called, bound)

    def test_the_record_writer_each_loadable_driver_holds_is_flow_envs(self):
        for name, attr in self.LOADABLE.items():
            with self.subTest(driver=name):
                driver = load_module(Path(name).stem, FLOW_DIR / name)
                self.assertIs(getattr(driver, attr), flow_env.write_record)

    def test_prove_no_net_main_writes_then_refuses_through_the_shared_writer(self):
        """`prove_no_net_sar_ctrl.main()` end to end with the prover stubbed:
        the record directory does not exist before the first run and the
        record is the renderer's text afterwards; a second run under the same
        record ID reports the refusal the driver always printed and exits 1
        with the first record's bytes untouched."""
        driver = load_module("prove_no_net_sar_ctrl", FLOW_DIR / "prove_no_net_sar_ctrl.py")
        pdk = type("P", (), {"variant": "gf180mcuD", "version": "open_pdks-unit-test"})()
        result = {
            "inputs": {"def_sha256": "d" * 64, "verilog_sha256": "v" * 64},
            "corners": [
                {
                    "corner": corner,
                    "liberty": f"{corner}.lib",
                    "proof": {
                        "outputs_examined": 1,
                        "no_net": list(driver.EXPECTED_NO_NET),
                        "outputs": {},
                        "inputs": {"liberty_sha256": "1" * 64},
                    },
                }
                for corner, _ in flow_env.CORNERS
            ],
            "signal_pins_agree": True,
            "exempt_set_equal": True,
        }
        rid = "20261128-011203-abcdef12"
        sha = "c0ffee0000000000000000000000000000000000"

        def run(root: Path) -> tuple[int, str, str, str]:
            """`main()` once under `root`: (exit code, stderr, stdout, the
            record text the renderer produced in that run)."""
            out, err = io.StringIO(), io.StringIO()
            with (
                mock.patch.object(sys, "argv", ["prove_no_net_sar_ctrl.py"]),
                mock.patch.object(driver, "REPO_ROOT", root),  # the success message is relative to it
                mock.patch.object(driver, "RECORDS_DIR", root / "records"),
                mock.patch.object(driver, "find_pdk", return_value=pdk),
                mock.patch.object(driver, "record_id", return_value=rid),
                mock.patch.object(driver, "git", return_value=sha),
                mock.patch.object(driver, "prove_all_corners", return_value=result),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                rc = driver.main()
                expected = driver.render(result, rid, pdk)
            return rc, err.getvalue(), out.getvalue(), expected

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = root / "records" / f"{rid}.{driver.LIB_TAG}.no_net_prover.md"
            self.assertFalse(record.parent.exists())

            rc, err, out, expected = run(root)
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(record.read_text(), expected)
            self.assertIn(f"wrote records/{record.name}", out)

            record.write_bytes(b"minted by an earlier run\n")
            rc, err, _, _ = run(root)
            kept = record.read_bytes()
        self.assertEqual(rc, 1)
        self.assertEqual(err, f"ERROR: record {record} already exists -- refusing to overwrite\n")
        self.assertEqual(kept, b"minted by an earlier run\n")


if __name__ == "__main__":
    unittest.main()
