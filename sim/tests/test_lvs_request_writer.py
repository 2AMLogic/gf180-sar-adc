#!/usr/bin/env python3
"""Issue #1094: the layout generators' `klt lvs` request documents come from
ONE writer, `layout/adc-top/lib/netlist.py`'s `write_lvs_request`, and that
writer keeps every committed request document byte for byte what it was.

Why this file exists. `gen_adc_cells.py`, `gen_adc_top.py` and
`gen_comparator.py` each hand-rolled the same JSON writer side by side, and in
issue #804 all three drifted the same way: each hardcoded the production
invocation path instead of deriving it from the file it was writing, so a
candidate-geometry request document told a reader to run the production
request. `sim/tools/check_lvs_request_invocations.py` guards the COMMITTED
files against that shape; this module guards the WRITERS:

* the documented invocation is derived from the path written, never taken
  from the comment (two documents with identical prose and different paths
  document different invocations, each resolving to its own file);
* each generator delegates to the shared writer, and passes it prose only --
  the blank separator and the invocation line are the writer's to append;
* the shared writer reproduces every committed request document under
  `layout/adc-top/` exactly, through each generator's own wrapper and its own
  comment text, so a generator whose prose drifts from its committed
  documents fails here rather than at the next LVS run.

Needs neither ngspice nor the PDK, and not KLayout either: the generators'
`klayout.db` import is stubbed below when the package is absent (as in CI),
the same way `test_layout_centroid_tiling.py` loads `gen_adc_top.py`. Only the
request writing is exercised; the geometry assertions and GDS save options
`gen_comparator.write_outputs` wraps around it are stubbed per test.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402

sys.path.insert(0, str(REPO / "sim" / "tools"))
import check_lvs_request_invocations as chk  # noqa: E402


def _stub_klayout() -> None:
    """Make `import klayout.db` resolve to an empty placeholder when the
    wheel is absent. The real package is preferred whenever it is installed,
    so this never shadows a working install."""
    try:
        import klayout.db  # noqa: F401, PLC0415
    except ImportError:
        klayout = types.ModuleType("klayout")
        klayout.__path__ = []  # mark as a package so `klayout.db` resolves
        db = types.ModuleType("klayout.db")
        klayout.db = db
        sys.modules.setdefault("klayout", klayout)
        sys.modules.setdefault("klayout.db", db)


_stub_klayout()
gen_cells = load_module(
    "lvs_req_gen_adc_cells", REPO / "layout/adc-top/cells/gen_adc_cells.py"
)
gen_top = load_module("lvs_req_gen_adc_top", REPO / "layout/adc-top/gen_adc_top.py")
gen_cmp = load_module(
    "lvs_req_gen_comparator", REPO / "layout/adc-top/gen_comparator.py"
)
nl = gen_top.nl

COMMENT = [
    "klt lvs request for a cell.",
    "Paths resolve against THIS file's directory.",
]

#: The byte contract: UTF-8, `indent=2`, the caller's prose, a blank line,
#: a 4-space-indented invocation naming THIS file relative to `root`, then
#: the `layout`/`reference` pair, and one trailing newline.
GOLDEN = b"""\
{
  "_comment": [
    "klt lvs request for a cell.",
    "Paths resolve against THIS file's directory.",
    "",
    "    klt lvs layout/adc-top/cells/adc_drv.lvs.json --format json"
  ],
  "layout": {
    "netlist": "adc_drv.spice",
    "top": "ADC_DRV"
  },
  "reference": {
    "netlist": "adc_drv.ref.spice",
    "top": "ADC_DRV"
  }
}
"""


def documented_invocation(path: Path) -> str:
    """The `<path>.lvs.json` the request document at `path` tells a reader
    to run."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    lines = [m.group(1) for m in map(chk.INVOCATION_RE.match, doc["_comment"]) if m]
    if len(lines) != 1:
        raise AssertionError(f"{path}: expected exactly one invocation, got {lines}")
    return lines[0]


class WriteLvsRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()

    def _path(self, rel: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_explicit_root_writes_the_byte_contract(self):
        rel = "layout/adc-top/cells/adc_drv.lvs.json"
        path = self._path(rel)
        nl.write_lvs_request(str(path), "ADC_DRV", "adc_drv", COMMENT, root=str(self.root))
        self.assertEqual(path.read_bytes(), GOLDEN)
        self.assertEqual(chk.find_violations(self.root, [rel]), [])

    def test_top_and_key_are_independent(self):
        path = self._path("layout/adc-top/renamed.lvs.json")
        nl.write_lvs_request(str(path), "ADC_TOP", "adc_top", COMMENT, root=str(self.root))
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            doc["layout"], {"netlist": "adc_top.spice", "top": "ADC_TOP"}
        )
        self.assertEqual(
            doc["reference"], {"netlist": "adc_top.ref.spice", "top": "ADC_TOP"}
        )

    def test_default_root_is_the_repo_the_writer_lives_in(self):
        # No `root=`: the anchor is `repo_root()` of this module's own
        # directory, so an `--outdir` outside the repo still documents a
        # path that resolves to the written file.
        path = Path(self._tmp.name) / "scratch" / "adc_top.lvs.json"
        path.parent.mkdir()
        nl.write_lvs_request(str(path), "ADC_TOP", "adc_top", COMMENT)
        repo_root = nl.repo_root(os.path.dirname(os.path.abspath(nl.__file__)))
        self.assertEqual(
            (Path(repo_root) / "design").is_dir(), True, "repo_root() is not this repo"
        )
        documented = documented_invocation(path)
        self.assertEqual(documented, os.path.relpath(str(path), repo_root))
        self.assertEqual(
            os.path.normpath(os.path.join(repo_root, documented)),
            os.path.normpath(str(path)),
        )

    def test_invocation_is_derived_from_the_written_path(self):
        # Issue #804's shape, inverted: identical prose written to a
        # production path and to a candidate path must document two
        # DIFFERENT invocations, each resolving to its own file -- a writer
        # that copied a production path into the candidate cannot pass.
        rels = (
            "layout/adc-top/adc_top.lvs.json",
            "layout/adc-top/candidates/acq-leg-1x/adc_top.lvs.json",
        )
        for rel in rels:
            nl.write_lvs_request(
                str(self._path(rel)), "ADC_TOP", "adc_top", COMMENT, root=str(self.root)
            )
        self.assertEqual(
            [documented_invocation(self.root / rel) for rel in rels], list(rels)
        )
        self.assertEqual(chk.find_violations(self.root, list(rels)), [])

    def test_callers_comment_list_is_left_unmodified(self):
        comment = list(COMMENT)
        nl.write_lvs_request(
            str(self._path("layout/adc-top/adc_top.lvs.json")),
            "ADC_TOP",
            "adc_top",
            comment,
            root=str(self.root),
        )
        self.assertEqual(comment, COMMENT)


class _FakeLayout:
    """Stands in for the KLayout `Layout` `gen_comparator.write_outputs`
    writes a GDS from; GDS emission is not under test."""

    def write(self, path, options):
        pass


def _comparator_info() -> dict:
    return {
        "name": gen_cmp.CELL_NAME,
        "devices": [],
        "pins": [],
        "body_net": {},
        "substrate_net": nl.SUBSTRATE_NET,
    }


def _no_geometry_side_effects():
    """`write_outputs` asserts grid/contacts and builds GDS save options for a
    real KLayout layout; neither is reachable without the package."""
    return mock.patch.multiple(
        gen_cmp.geo,
        assert_on_grid=mock.DEFAULT,
        assert_contacts_exact=mock.DEFAULT,
        save_options=mock.DEFAULT,
    )


class GeneratorsShareTheRequestWriter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        patcher = mock.patch.object(nl, "repo_root", return_value=str(self.root))
        patcher.start()
        self.addCleanup(patcher.stop)

    def committed_requests(self) -> list[str]:
        """Every committed `*.lvs.json` REQUEST document under
        `layout/adc-top/` (`klt lvs` output reports share the suffix; they
        carry no `_comment`)."""
        requests = []
        for rel in chk.committed_files(REPO, "*.lvs.json"):
            if not rel.startswith("layout/adc-top/"):
                continue
            if "_comment" in json.loads((REPO / rel).read_text(encoding="utf-8")):
                requests.append(rel)
        return requests

    def regenerate(self, rel: str) -> Path:
        """Run the generator that owns `rel`'s request, writing into the temp
        tree at the same repo-relative location."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        stem = path.name[: -len(".lvs.json")]
        if stem in gen_cells.LEAF_CELLS:
            gen_cells.write_request(str(path), gen_cells.LEAF_CELLS[stem])
        elif stem == "comparator":
            with _no_geometry_side_effects():
                gen_cmp.write_outputs(
                    str(path.parent), _FakeLayout(), _comparator_info(), stem
                )
        else:
            cell_name = {
                "adc_top": gen_top.CELL_NAME,
                "adc_block": gen_top.BLOCK_CELL_NAME,
            }[stem]
            gen_top.write_request(str(path), cell_name, stem)
        return path

    def test_one_shared_netlist_module(self):
        self.assertIs(gen_top.nl, gen_cells.nl)
        self.assertIs(gen_top.nl, gen_cmp.nl)

    def test_every_committed_request_is_reproduced_byte_for_byte(self):
        rels = self.committed_requests()
        for rel in (
            "layout/adc-top/adc_top.lvs.json",
            "layout/adc-top/adc_block.lvs.json",
            "layout/adc-top/comparator.lvs.json",
            "layout/adc-top/cells/adc_drv.lvs.json",
        ):
            self.assertIn(rel, rels)
        for rel in rels:
            with self.subTest(rel=rel):
                self.assertEqual(
                    self.regenerate(rel).read_bytes(), (REPO / rel).read_bytes()
                )

    def test_each_generator_delegates_to_the_shared_writer(self):
        outdir = self.root / "nowhere"
        outdir.mkdir()
        with mock.patch.object(nl, "write_lvs_request") as shared:
            gen_cells.write_request(
                str(outdir / "adc_drv.lvs.json"), gen_cells.LEAF_CELLS["adc_drv"]
            )
            gen_top.write_request(str(outdir / "adc_top.lvs.json"), "ADC_TOP", "adc_top")
            with _no_geometry_side_effects():
                gen_cmp.write_outputs(
                    str(outdir), _FakeLayout(), _comparator_info(), "comparator"
                )
        self.assertEqual(
            [(c.args[0], c.args[1], c.args[2]) for c in shared.call_args_list],
            [
                (str(outdir / "adc_drv.lvs.json"), "ADC_DRV", "adc_drv"),
                (str(outdir / "adc_top.lvs.json"), "ADC_TOP", "adc_top"),
                (str(outdir / "comparator.lvs.json"), "COMPARATOR", "comparator"),
            ],
        )
        for call in shared.call_args_list:
            comment = call.args[3]
            with self.subTest(path=call.args[0]):
                self.assertTrue(comment and all(isinstance(ln, str) for ln in comment))
                # Prose only: the trailing separator and the invocation are
                # the shared writer's to append.
                self.assertTrue(comment[-1])
                self.assertFalse(any(chk.INVOCATION_RE.match(ln) for ln in comment))
                self.assertNotIn("root", call.kwargs)


if __name__ == "__main__":
    unittest.main()
