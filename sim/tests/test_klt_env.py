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
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LAYOUT_DIR = REPO / "layout"
KLT_ENV = LAYOUT_DIR / "klt_env.py"
RUN_EXTRACT_PARASITICS = (
    LAYOUT_DIR / "adc-top" / "parasitics" / "run_extract_parasitics.py"
)


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


class RunExtractParasiticsDelegationTests(unittest.TestCase):
    """Issue #955: `run_extract_parasitics.py` delegates provenance, manifest
    loading, append-only slot reservation, and record writing to `klt_env`,
    and carries no dead `pdk=None` fallback path."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(
            "run_extract_parasitics_under_test", RUN_EXTRACT_PARASITICS
        )
        cls.klt_env = sys.modules["klt_env"]

    def _setup_fixture(self, root: Path, *, bad_device_count: bool = False) -> dict:
        here = root / "layout" / "adc-top" / "parasitics"
        (here / "cells").mkdir(parents=True)
        gds = here / "cells" / "adc_tgate.gds"
        gds.write_bytes(b"FAKEGDS")
        gds_sha = hashlib.sha256(b"FAKEGDS").hexdigest()
        toolchain_path = root / "layout" / "toolchain.json"
        toolchain_path.write_text(
            json.dumps(
                {"klt_last_verified_commit": "abc1234", "klt_required_commands": []}
            ),
            encoding="utf-8",
        )
        netlist_text = (
            ".SUBCKT ADC_TGATE gn gp vdd vin vout vsubs\n"
            "X$1 vin gn vout vsubs nfet_03v3 L=0.28U W=10U\n"
            "X$2 vin gp vout vdd pfet_03v3 L=0.28U W=20U\n"
            ".ENDS\n"
        )
        netlist_sha = hashlib.sha256(netlist_text.encode("utf-8")).hexdigest()
        manifest = {
            "blocks": {
                "adc_tgate": {
                    "gds": "cells/adc_tgate.gds",
                    "top": "ADC_TGATE",
                    "gds_sha256": gds_sha,
                    "expect": {
                        "device_count": 999 if bad_device_count else 2,
                        "net_count": 6,
                        "pin_count": 6,
                        "device_counts": {"nfet": 1, "pfet": 1},
                        "parasitics": {
                            "r_count": 7,
                            "c_count": 5,
                            "total_resistance_ohm": 757.833,
                            "total_capacitance_ff": 13.607496,
                        },
                    },
                }
            }
        }
        manifest_path = here / "cells.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        real_run = self.mod.subprocess.run

        def fake_subprocess_run(cmd, *args, **kwargs):
            if not (isinstance(cmd, list) and len(cmd) >= 2 and cmd[1] == "extract"):
                return real_run(cmd, *args, **kwargs)
            out_idx = cmd.index("-o") + 1
            Path(cmd[out_idx]).write_text(netlist_text, encoding="utf-8")
            summary = {
                "top": "ADC_TGATE",
                "pdk": "gf180mcuD",
                "netlist_sha256": netlist_sha,
                "device_count": 2,
                "net_count": 6,
                "pin_count": 6,
                "device_counts": {"nfet": 1, "pfet": 1},
                "parasitics": {
                    "r_count": 7,
                    "c_count": 5,
                    "total_resistance_ohm": 757.833,
                    "total_capacitance_ff": 13.607496,
                },
            }
            return mock.Mock(returncode=0, stdout=json.dumps(summary), stderr="")

        return {
            "here": here,
            "layout_dir": root / "layout",
            "repo_root": root,
            "manifest_path": manifest_path,
            "reports_dir": here / "reports",
            "records_dir": here / "records",
            "fake_run": fake_subprocess_run,
            "pdk": {"variant": "gf180mcuD", "version": "open_pdks pin", "root": "/pdk"},
        }

    def test_delegates_provenance_and_slot_helpers_to_klt_env(self):
        mod = self.mod
        ke = self.klt_env
        self.assertFalse(hasattr(mod, "_git_sha"))
        self.assertFalse(hasattr(mod, "_load_manifest"))
        for attr in (
            "EXIT_OK",
            "EXIT_TOOLING",
            "EXIT_MISMATCH",
            "git",
            "load_manifest",
            "record_id",
            "reserve_record_slot",
            "write_record_text",
        ):
            with self.subTest(attr=attr):
                self.assertIs(getattr(mod, attr, None), getattr(ke, attr))

        source = RUN_EXTRACT_PARASITICS.read_text(encoding="utf-8")
        self.assertNotIn("PDK binding**: none", source)
        self.assertNotIn("dict | None", source)

    def test_occupied_slot_is_refused_without_touching_existing_files(self):
        mod = self.mod
        rec_id = "20261122-120000-deadbeef"
        for scenario in (
            "report_dir_only",
            "record_and_report",
            "mismatch_with_existing_report",
        ):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as td:
                fx = self._setup_fixture(
                    Path(td),
                    bad_device_count=(scenario == "mismatch_with_existing_report"),
                )
                occupied_report = fx["reports_dir"] / rec_id
                occupied_report.mkdir(parents=True)
                old_spice = occupied_report / "adc_tgate.para.spice"
                old_spice.write_text("OLD SPICE\n", encoding="utf-8")
                sentinel = occupied_report / "sentinel.txt"
                sentinel.write_text("KEEP\n", encoding="utf-8")
                record_file = fx["records_dir"] / f"{rec_id}.md"
                if scenario == "record_and_report":
                    fx["records_dir"].mkdir(parents=True)
                    record_file.write_text("OLD RECORD\n", encoding="utf-8")

                with (
                    mock.patch.multiple(
                        mod,
                        HERE=str(fx["here"]),
                        LAYOUT_DIR=str(fx["layout_dir"]),
                        REPO_ROOT=str(fx["repo_root"]),
                        MANIFEST_PATH=str(fx["manifest_path"]),
                        REPORTS_DIR=str(fx["reports_dir"]),
                        RECORDS_DIR=str(fx["records_dir"]),
                    ),
                    mock.patch.object(mod, "_require_klt", return_value="/bin/klt"),
                    mock.patch.object(mod, "resolve_pdk", return_value=fx["pdk"]),
                    mock.patch.object(mod, "record_id", return_value=rec_id),
                    mock.patch.object(
                        mod.subprocess, "run", side_effect=fx["fake_run"]
                    ),
                    redirect_stdout(io.StringIO()),
                    redirect_stderr(io.StringIO()),
                ):
                    rc = mod.run(check_only=False)

                expected_rc = (
                    self.klt_env.EXIT_MISMATCH
                    if scenario == "mismatch_with_existing_report"
                    else self.klt_env.EXIT_TOOLING
                )
                self.assertEqual(rc, expected_rc)
                self.assertEqual(old_spice.read_text(encoding="utf-8"), "OLD SPICE\n")
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "KEEP\n")
                if scenario == "record_and_report":
                    self.assertEqual(
                        record_file.read_text(encoding="utf-8"), "OLD RECORD\n"
                    )
                else:
                    self.assertFalse(record_file.exists())

    def test_corrupt_manifest_returns_exit_tooling(self):
        mod = self.mod
        with tempfile.TemporaryDirectory() as td:
            bad_manifest = Path(td) / "cells.json"
            bad_manifest.write_text("{not valid json", encoding="utf-8")
            with (
                mock.patch.object(mod, "MANIFEST_PATH", str(bad_manifest)),
                mock.patch.object(mod, "_require_klt", return_value="/bin/klt"),
                redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(mod.run(check_only=True), self.klt_env.EXIT_TOOLING)
                self.assertEqual(mod.regen_manifest(), self.klt_env.EXIT_TOOLING)

    def test_happy_path_mints_record_via_klt_env(self):
        mod = self.mod
        rec_id = "20261122-120001-cafebabe"
        full_sha = "cafebabe" * 5
        with tempfile.TemporaryDirectory() as td:
            fx = self._setup_fixture(Path(td))
            with (
                mock.patch.multiple(
                    mod,
                    HERE=str(fx["here"]),
                    LAYOUT_DIR=str(fx["layout_dir"]),
                    REPO_ROOT=str(fx["repo_root"]),
                    MANIFEST_PATH=str(fx["manifest_path"]),
                    REPORTS_DIR=str(fx["reports_dir"]),
                    RECORDS_DIR=str(fx["records_dir"]),
                ),
                mock.patch.object(mod, "_require_klt", return_value="/bin/klt"),
                mock.patch.object(mod, "resolve_pdk", return_value=fx["pdk"]),
                mock.patch.object(mod, "record_id", return_value=rec_id),
                mock.patch.object(mod, "git", return_value=full_sha),
                mock.patch.object(mod, "klt_version", return_value="klt 0.8.0"),
                mock.patch.object(mod.subprocess, "run", side_effect=fx["fake_run"]),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                rc = mod.run(check_only=False)

            self.assertEqual(rc, self.klt_env.EXIT_OK)
            report_dir = fx["reports_dir"] / rec_id
            self.assertTrue((report_dir / "adc_tgate.para.spice").is_file())
            self.assertTrue((report_dir / "adc_tgate.extract.json").is_file())
            self.assertTrue((report_dir / "toolchain.json").is_file())
            rec_text = (fx["records_dir"] / f"{rec_id}.md").read_text(encoding="utf-8")
            self.assertTrue(rec_text.endswith("\n"))
            self.assertIn(f"- **Repo git sha**: `{full_sha}`", rec_text)
            self.assertIn("--pdk gf180mcuD --pdk-root /pdk", rec_text)
            self.assertIn("| `adc_tgate` | `vdd` x1 | `vsubs` x1 | 0 | 0 |", rec_text)


class ToolchainRecordTests(unittest.TestCase):
    """`toolchain_record` is the one eight-field provenance schema (#999)."""

    KEYS = [
        "klt_version",
        "klt_path",
        "klt_required_commands",
        "klayout_package",
        "python",
        "platform",
        "repo_git_sha",
        "repo_dirty",
    ]

    def _record(self, py, ver, sha="", status=""):
        mod = load_module("klt_env_toolchain_record", KLT_ENV)
        find = (
            mock.Mock(side_effect=mod.ToolingError("no klayout"))
            if py is None
            else mock.Mock(return_value=py)
        )
        with (
            mock.patch.object(mod, "find_klayout_python", find),
            mock.patch.object(mod, "klayout_version", return_value="0.30.1"),
            mock.patch.object(mod, "git", side_effect=[sha, status]),
        ):
            return mod.toolchain_record("/bin/true", {}, REPO, ver)

    def test_key_order_and_values(self):
        rec = self._record("/py", "klt 1", "abc", " M x")
        self.assertEqual(list(rec), self.KEYS)
        self.assertEqual(rec["klt_version"], "klt 1")
        self.assertEqual(rec["klayout_package"], "0.30.1")
        self.assertEqual(rec["klt_required_commands"], [])
        self.assertEqual(rec["repo_git_sha"], "abc")
        self.assertIs(rec["repo_dirty"], True)

    def test_fallbacks(self):
        rec = self._record(None, "")
        self.assertEqual(list(rec), self.KEYS)
        self.assertEqual(rec["klt_version"], "unknown")
        self.assertEqual(rec["klayout_package"], "not installed")
        self.assertEqual(rec["repo_git_sha"], "unknown")
        self.assertIs(rec["repo_dirty"], False)


if __name__ == "__main__":
    unittest.main()
