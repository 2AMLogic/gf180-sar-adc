#!/usr/bin/env python3
"""Every `layout/` evidence record's self-description comes from one place
(issue #795).

    python3 -m unittest discover -s sim/tests -v

Why this file exists. `layout/{drc,erc,lvs,power}/run_*.py` each mint an
append-only evidence record, and each record ends with a line naming who
produced it:

    - **Author** — Loom Builder agent (issue #795)

The issue named there is the issue the *run* was minted for, not the issue
that stood the flow up. `run_erc.py` learned that the hard way -- it had
`#330` hard-coded, so every later re-run shipped a record claiming it
existed for a reason it did not -- and the fix was a per-run `--issue`
flag. That fix was copied to `run_power.py` and stopped there. `run_drc.py`
and `run_lvs.py` went on hard-coding `#15` and `#51`, which is why all 15
committed DRC records and all 16 committed LVS records misattribute
themselves. In a repository whose product is provenance, that is a
correctness defect, and it is one a fourth fork of the same two lines could
reintroduce silently.

So the Author line now has exactly one implementation,
`klt_env.author_line`, and this suite is what keeps it that way. The checks
split three ways by what they can prove:

| Class | Claim |
|---|---|
| `AuthorLineTests` / `WriteRecordTextTests` | the shared helpers produce the exact bytes a record carries |
| `ReportRunnerParserTests` | the CLI `run_erc.py` and `run_power.py` share is one parser, and its `--issue` help names no particular issue |
| `RunnerWiringTests` | all four runners route their Author line through `author_line(issue)` and feed it from `--issue` -- a fifth fork that re-hard-codes a number goes red here |
| `DrcRecordTextTests` | end-to-end: `run_drc.py`'s own `write_record()` stamps the `--issue` value, and omits the clause when unset |

Stdlib only, by construction: none of it runs `klt` or needs the pip
`klayout` package, so it runs on this repo's CI path (`.github/workflows/
ci.yml` installs neither) rather than only where a full layout environment
exists. The committed records under `layout/*/records/` are append-only and
are deliberately NOT rewritten by any of this -- what #795 closes is the
next record, not the 31 already on file.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]
LAYOUT = REPO / "layout"
KLT_ENV = LAYOUT / "klt_env.py"

RUNNERS = {
    "drc": LAYOUT / "drc" / "run_drc.py",
    "erc": LAYOUT / "erc" / "run_erc.py",
    "lvs": LAYOUT / "lvs" / "run_lvs.py",
    "power": LAYOUT / "power" / "run_power.py",
}

#: The literal prefix a record's Author line starts with. Asserted rather
#: than imported so a change to the wording has to be made deliberately
#: here too, not just in `klt_env`.
AUTHOR_PREFIX = "- **Author** — Loom Builder agent"


def load_klt_env():
    """Import `layout/klt_env.py` by path.

    `layout/` is a plain directory, not a package; the module is loaded by
    file path the same way the other layout-facing suites here load theirs.
    `klt_env` imports `toolchain_pin` from beside itself, so `layout/` goes
    on `sys.path` first.
    """
    if str(LAYOUT) not in sys.path:
        sys.path.insert(0, str(LAYOUT))
    return load_module("klt_env", KLT_ENV)


class AuthorLineTests(unittest.TestCase):
    """`author_line` is the only thing that decides what a record claims
    about its own authorship."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.klt_env = load_klt_env()

    def test_an_issue_is_stamped_as_a_parenthetical(self) -> None:
        self.assertEqual(
            self.klt_env.author_line("#795"),
            f"{AUTHOR_PREFIX} (issue #795)",
        )

    def test_no_issue_omits_the_clause_entirely(self) -> None:
        """An unstamped record must say *nothing* about which issue it was
        minted for, rather than something false -- this is the whole point
        of the flag being per-run."""
        self.assertEqual(self.klt_env.author_line(None), AUTHOR_PREFIX)
        self.assertNotIn("issue", self.klt_env.author_line(None))

    def test_an_empty_string_is_treated_as_unstamped(self) -> None:
        """`--issue ''` must not mint `(issue )`."""
        self.assertEqual(self.klt_env.author_line(""), AUTHOR_PREFIX)

    def test_the_issue_value_is_passed_through_verbatim(self) -> None:
        """No reformatting: the runner's caller owns the `#` convention, so
        a bare number stays a bare number rather than being silently
        prefixed into something the record did not say."""
        self.assertEqual(
            self.klt_env.author_line("795"), f"{AUTHOR_PREFIX} (issue 795)"
        )


class WriteRecordTextTests(unittest.TestCase):
    """`write_record_text` defines the bytes a record is made of."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.klt_env = load_klt_env()

    def test_lines_are_joined_with_single_newlines_and_nothing_appended(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rec.md"
            returned = self.klt_env.write_record_text(
                str(path), ["# Record", "", "body"]
            )
            self.assertEqual(returned, str(path))
            self.assertEqual(path.read_bytes(), b"# Record\n\nbody")

    def test_the_record_is_written_utf8(self) -> None:
        """The Author line's em dash is non-ASCII, so the encoding is not
        incidental -- a platform default of cp1252 would mangle every
        record this repo mints."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rec.md"
            self.klt_env.write_record_text(
                str(path), [self.klt_env.author_line("#795")]
            )
            self.assertEqual(
                path.read_bytes(),
                f"{AUTHOR_PREFIX} (issue #795)".encode("utf-8"),
            )


class ReportRunnerParserTests(unittest.TestCase):
    """`run_erc.py` and `run_power.py` share one CLI."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.klt_env = load_klt_env()

    def test_the_shared_parser_offers_exactly_the_erc_power_flag_set(self) -> None:
        parser = self.klt_env.report_runner_parser("a flow")
        flags = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertEqual(
            flags,
            {"-h", "--help", "--check", "--verify", "--record", "--klt", "--issue"},
        )

    def test_the_runner_description_is_preserved(self) -> None:
        """One parser for two flows still has to say which flow `--help` is
        describing."""
        self.assertEqual(
            self.klt_env.report_runner_parser("run klt erc over X").description,
            "run klt erc over X",
        )

    def test_issue_parses_into_the_value_author_line_stamps(self) -> None:
        args = self.klt_env.report_runner_parser("a flow").parse_args(
            ["--issue", "#795"]
        )
        self.assertEqual(args.issue, "#795")
        self.assertEqual(
            self.klt_env.author_line(args.issue), f"{AUTHOR_PREFIX} (issue #795)"
        )

    def test_issue_defaults_to_none(self) -> None:
        args = self.klt_env.report_runner_parser("a flow").parse_args([])
        self.assertIsNone(args.issue)

    def test_the_issue_help_names_no_particular_issue(self) -> None:
        """The two forked copies of this block differed on exactly one line:
        the example issue number. A real issue number in shared help is a
        claim about one flow made in a place both flows read."""
        parser = self.klt_env.report_runner_parser("a flow")
        help_text = next(
            action.help
            for action in parser._actions
            if "--issue" in action.option_strings
        )
        for stale in ("#330", "#340", "#346", "#15", "#51"):
            self.assertNotIn(stale, help_text)


class RunnerWiringTests(unittest.TestCase):
    """All four runners route their Author line through the one helper.

    These are source-level assertions on purpose. The failure mode #795
    fixes is not a wrong value at runtime -- each fork worked -- it is a
    *fifth fork*: someone adding a runner, or editing one, by copying the
    two lines next door instead of calling the helper. That is visible in
    the source and nowhere else, because a hard-coded record is perfectly
    self-consistent once written.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {
            name: path.read_text(encoding="utf-8")
            for name, path in RUNNERS.items()
        }
        cls.trees = {
            name: ast.parse(src, filename=str(RUNNERS[name]))
            for name, src in cls.sources.items()
        }

    @staticmethod
    def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise AssertionError(f"no {name}() found")

    def test_no_runner_hard_codes_an_issue_into_its_author_line(self) -> None:
        for name, src in self.sources.items():
            with self.subTest(runner=name):
                self.assertNotIn(
                    f"{AUTHOR_PREFIX} (issue",
                    src,
                    f"layout/{name}/run_{name}.py hard-codes an issue number "
                    "into its Author line. That is the #795 defect: the "
                    "record must name the issue the run was minted FOR, via "
                    "klt_env.author_line(issue) and the --issue flag.",
                )

    def test_every_runner_imports_author_line_from_klt_env(self) -> None:
        for name, tree in self.trees.items():
            with self.subTest(runner=name):
                imported = {
                    alias.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module == "klt_env"
                    for alias in node.names
                }
                self.assertIn("author_line", imported)
                self.assertIn("write_record_text", imported)

    def test_write_record_takes_an_issue_and_hands_it_to_author_line(self) -> None:
        for name, tree in self.trees.items():
            with self.subTest(runner=name):
                func = self._function(tree, "write_record")
                params = [a.arg for a in func.args.args] + [
                    a.arg for a in func.args.kwonlyargs
                ]
                self.assertIn("issue", params)

                calls = [
                    node
                    for node in ast.walk(func)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "author_line"
                ]
                self.assertEqual(
                    len(calls), 1, "exactly one Author line per record"
                )
                self.assertEqual(
                    [a.id for a in calls[0].args if isinstance(a, ast.Name)],
                    ["issue"],
                    "author_line() must be handed write_record()'s own "
                    "issue parameter, not a literal",
                )

    def test_write_record_delegates_its_write_to_write_record_text(self) -> None:
        for name, tree in self.trees.items():
            with self.subTest(runner=name):
                func = self._function(tree, "write_record")
                called = {
                    node.func.id
                    for node in ast.walk(func)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                }
                self.assertIn("write_record_text", called)

    def test_main_feeds_write_record_from_the_issue_flag(self) -> None:
        for name, tree in self.trees.items():
            with self.subTest(runner=name):
                func = self._function(tree, "main")
                wired = False
                for node in ast.walk(func):
                    if not (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "write_record"
                    ):
                        continue
                    for arg in list(node.args) + [
                        kw.value for kw in node.keywords
                    ]:
                        if (
                            isinstance(arg, ast.Attribute)
                            and arg.attr == "issue"
                            and isinstance(arg.value, ast.Name)
                            and arg.value.id == "args"
                        ):
                            wired = True
                self.assertTrue(
                    wired,
                    f"layout/{name}/run_{name}.py's main() must pass "
                    "args.issue into write_record(); otherwise --issue is "
                    "accepted and silently dropped.",
                )

    def test_every_runner_advertises_issue_on_its_cli(self) -> None:
        """Behavioural, not source-level: `--help` exits before any `klt`
        call, so this is the one end-to-end CLI check that runs without a
        layout toolchain installed."""
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                proc = subprocess.run(
                    [sys.executable, str(path), "--help"],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO),
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("--issue", proc.stdout)


class DrcRecordTextTests(unittest.TestCase):
    """End-to-end on the cheapest of the four: `run_drc.py`'s own
    `write_record()` really does stamp what `--issue` was given.

    `run_drc.py` is one of the two runners that carried the bug, and its
    `write_record()` needs no `klt` and no real geometry -- only a manifest
    and a results list -- so the whole record text can be minted into a
    temp directory from synthetic input. `REPORTS_DIR`/`RECORDS_DIR` are
    redirected there: the committed `layout/drc/records/` tree is
    append-only evidence and this suite must never add to it.
    """

    MANIFEST = {"deck": "gf180mcu.drc"}
    TOOLCHAIN = {"klt_version": "0.0.0-test"}
    RESULTS = [
        {
            "name": "probe",
            "cell": {
                "role": "positive control",
                "expect": {},
                "gds": "probe.gds",
                "sha256": "0" * 64,
            },
            "report": {"rule_counts": {}},
            "text": "probe text\n",
            "exit_code": 0,
            "sha256": "0" * 64,
            "failures": [],
        }
    ]

    def _mint(self, issue: "str | None") -> str:
        if str(LAYOUT) not in sys.path:
            sys.path.insert(0, str(LAYOUT))
        run_drc = load_module("run_drc", RUNNERS["drc"])
        with tempfile.TemporaryDirectory() as tmp:
            run_drc.REPORTS_DIR = str(Path(tmp) / "reports")
            run_drc.RECORDS_DIR = str(Path(tmp) / "records")
            Path(run_drc.REPORTS_DIR).mkdir()
            path = run_drc.write_record(
                "19700101-000000-testsha",
                self.MANIFEST,
                self.RESULTS,
                self.TOOLCHAIN,
                True,
                issue,
            )
            return Path(path).read_text(encoding="utf-8")

    def test_the_issue_reaches_the_minted_record(self) -> None:
        self.assertIn(f"{AUTHOR_PREFIX} (issue #795)", self._mint("#795"))

    def test_an_unstamped_run_mints_no_issue_claim(self) -> None:
        text = self._mint(None)
        self.assertIn(AUTHOR_PREFIX, text)
        self.assertNotIn("(issue", text)

    def test_the_old_hard_coded_issue_is_gone(self) -> None:
        """`run_drc.py` stamped `#15` into every record it ever minted; the
        regression this guards is that number coming back."""
        self.assertNotIn("issue #15", self._mint("#795"))


if __name__ == "__main__":
    unittest.main()
