#!/usr/bin/env python3
"""Issue #1111: ONE two-stream block-emission loop for `layout/adc-top/
gen_adc_top.py` and both `candidates/` generators.

Why this file exists. The parse / build / assert / write sequence for the
`adc_top` and `adc_block` deliverables was copied into three scripts and the
copies drifted: the acquisition-leg candidate shipped without
`geo.assert_on_grid` and `geo.assert_contacts_exact`, and the bank-fold
candidate wrote `area.json` twice, once per stream. `gen_adc_top.
emit_deliverables` is now the only copy. This module pins that

* the helper asserts on-grid geometry and exact contacts on BOTH streams
  before each stream's GDS is written, forwards `expected_mos` to `build`,
  writes the six deliverables, prints the tally line and returns the
  `adc_block` tally;
* each candidate generator routes through the helper -- the acquisition-leg
  one at its own `expected_mos=350` -- and never calls `build` itself, so a
  re-inlined loop cannot quietly drop the assertions again;
* the bank-fold candidate writes `area.json` once, from the returned
  `adc_block` tally.

Needs neither ngspice, the PDK nor KLayout: `gen_adc_top.py`'s `klayout.db`
import is stubbed when the wheel is absent (as `test_lvs_request_writer.py`
does) and the drawing is replaced by fakes, so only the orchestration is
under test.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402


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
gen_top = load_module(
    "emit_deliverables_gen_adc_top", REPO / "layout/adc-top/gen_adc_top.py"
)
acq = load_module(
    "emit_deliverables_gen_acq_leg_candidate",
    REPO / "layout/adc-top/candidates/gen_acq_leg_candidate.py",
)
bank = load_module(
    "emit_deliverables_gen_bank_fold_candidate",
    REPO / "layout/adc-top/candidates/gen_bank_fold_candidate.py",
)
nl = gen_top.nl

#: The acquisition-leg candidate at `--scale 0.5`: the real generator's own
#: bounding boxes and tallies, so the summary lines below are its own.
BOXES_NM = {"ADC_TOP": (645900, 174800), "ADC_BLOCK": (671705, 174800)}
INFOS = {
    "ADC_TOP": {"transistor_count": 350, "cap_count": 1024},
    "ADC_BLOCK": {"transistor_count": 377, "cap_count": 1024},
}
SUMMARY = [
    "wrote adc_top.gds  transistors=350  caps=1024  645.9 x 174.8 um "
    "= 0.11290 mm^2",
    "wrote adc_block.gds  transistors=377  caps=1024  671.7 x 174.8 um "
    "= 0.11741 mm^2",
]
STREAMS = (("adc_top", "ADC_TOP"), ("adc_block", "ADC_BLOCK"))


class _FakeBox:
    def __init__(self, width_nm: int, height_nm: int) -> None:
        self._width = width_nm
        self._height = height_nm

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


class _FakeLayout:
    """What `build` hands back, seen only through the helper's eyes."""

    def __init__(self, events: list[str], dbu: float, box: _FakeBox) -> None:
        self.dbu = dbu
        self._events = events
        self._box = box
        self.written: list[tuple[str, object]] = []

    def cell(self, name: str):
        return types.SimpleNamespace(bbox=lambda: self._box)

    def write(self, path: str, options) -> None:
        self._events.append("write")
        self.written.append((path, options))
        Path(path).write_bytes(b"GDS bytes")


class EmitDeliverables(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.outdir = os.path.join(self._tmp.name, "out")
        os.mkdir(self.outdir)
        self.netlist = str(REPO / "design" / "adc-top" / "adc_top.spice")
        self.dbu = gen_top.geo.DBU_UM
        self.events: list[str] = []
        self.layouts: list[_FakeLayout] = []
        self.infos: list[dict] = []
        self.build_calls: list[dict] = []
        self.stdout = io.StringIO()

    def _build(self, subckts, cmp_subckts, cell_name, expected_mos):
        self.events.append(f"build:{cell_name}")
        self.build_calls.append(
            {
                "subckts": subckts,
                "cmp": cmp_subckts,
                "cell_name": cell_name,
                "expected_mos": expected_mos,
            }
        )
        layout = _FakeLayout(self.events, self.dbu, _FakeBox(*BOXES_NM[cell_name]))
        self.layouts.append(layout)
        info = dict(INFOS[cell_name])
        self.infos.append(info)
        return layout, info

    def _emit(self, *, on_grid=None, contacts=None, **kwargs):
        def record(name):
            def assert_(layout):
                self.events.append(f"{name}:{self.layouts.index(layout)}")

            return assert_

        def write_reference(path, info, cell_name, key):
            self.events.append("write_reference")
            Path(path).write_text(f"ref {key}\n", encoding="utf-8")

        patches = [
            mock.patch.object(gen_top, "build", self._build),
            mock.patch.object(gen_top, "write_reference", write_reference),
            mock.patch.object(
                gen_top.geo, "assert_on_grid", on_grid or record("on_grid")
            ),
            mock.patch.object(
                gen_top.geo, "assert_contacts_exact", contacts or record("contacts")
            ),
            mock.patch.object(gen_top.geo, "save_options", lambda: "SAVE_OPTIONS"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        with redirect_stdout(self.stdout):
            return gen_top.emit_deliverables(self.netlist, self.outdir, **kwargs)

    def test_builds_both_streams_and_forwards_the_count(self):
        self._emit(expected_mos=350)
        self.assertEqual(
            [(c["cell_name"], c["expected_mos"]) for c in self.build_calls],
            [("ADC_TOP", 350), ("ADC_BLOCK", 350)],
        )
        self.assertIsNone(self.build_calls[0]["cmp"])
        self.assertIn("comparator", self.build_calls[1]["cmp"])
        for call in self.build_calls:
            self.assertIn("adc_top", call["subckts"])

    def test_ratified_count_is_the_default(self):
        self._emit()
        self.assertEqual([c["expected_mos"] for c in self.build_calls], [368, 368])

    def test_asserts_before_each_stream_is_written(self):
        self._emit()
        self.assertEqual(
            self.events,
            [
                "build:ADC_TOP",
                "on_grid:0",
                "contacts:0",
                "write",
                "write_reference",
                "build:ADC_BLOCK",
                "on_grid:1",
                "contacts:1",
                "write",
                "write_reference",
            ],
        )

    def test_writes_the_six_deliverables(self):
        self._emit()
        self.assertEqual(
            sorted(os.listdir(self.outdir)),
            sorted(
                f"{key}{suffix}"
                for key, _ in STREAMS
                for suffix in (".gds", ".ref.spice", ".lvs.json")
            ),
        )
        for layout, (key, _) in zip(self.layouts, STREAMS):
            self.assertEqual(
                layout.written,
                [(os.path.join(self.outdir, f"{key}.gds"), "SAVE_OPTIONS")],
            )
        for key, _ in STREAMS:
            self.assertEqual(
                Path(self.outdir, f"{key}.ref.spice").read_text(encoding="utf-8"),
                f"ref {key}\n",
            )
            request = json.loads(Path(self.outdir, f"{key}.lvs.json").read_text())
            self.assertEqual(request["layout"]["top"], dict(STREAMS)[key])

    def test_prints_the_tally_line_and_returns_the_block_tally(self):
        result = self._emit(expected_mos=350)
        self.assertEqual(self.stdout.getvalue().splitlines(), SUMMARY)
        self.assertIs(result, self.infos[1])

    def test_dbu_drift_is_refused(self):
        self.dbu = 0.01
        with self.assertRaisesRegex(AssertionError, "dbu drifted"):
            self._emit()
        self.assertEqual(os.listdir(self.outdir), [])

    def test_off_grid_stream_is_refused_before_its_gds_is_written(self):
        def refuse(layout):
            raise AssertionError("off-grid vertex")

        with self.assertRaisesRegex(AssertionError, "off-grid"):
            self._emit(on_grid=refuse)
        self.assertEqual(os.listdir(self.outdir), [])

    def test_bad_block_contact_leaves_no_block_gds(self):
        def refuse(layout):
            if self.layouts.index(layout) == 1:
                raise AssertionError("contact is not a square")

        with self.assertRaisesRegex(AssertionError, "not a square"):
            self._emit(contacts=refuse)
        self.assertEqual(
            sorted(os.listdir(self.outdir)),
            ["adc_top.gds", "adc_top.lvs.json", "adc_top.ref.spice"],
        )


def _candidate_outdir(module) -> str:
    """A fresh directory the candidates' outdir guard accepts (strictly
    under `layout/adc-top/candidates/`); the caller removes it."""
    return tempfile.mkdtemp(dir=module.HERE, prefix="emit-test-")


def _fake_generator(tally: dict) -> mock.Mock:
    """Stand-in for the imported `gen_adc_top` module: the real pure-Python
    `netlist` module, so the candidate netlist substitution runs for real,
    and an `emit_deliverables` that returns `tally`."""
    g = mock.Mock()
    g.nl = nl
    g.ARRAY_COLS = 32
    g.ARRAY_ROWS = 16
    g.emit_deliverables.return_value = tally
    return g


ACQ_TALLY = {
    "assignment": {"u0": "256", "u1": "256", "u8": "1", "u9": "term"},
    "areas": {"block_total": 117414.034},
    "dimensions_um": {"block": [671.705, 174.8]},
    "transistor_count": 377,
    "cap_count": 1024,
}

BANK_INFO = {
    "areas": {"block_total": 117414.034},
    "dimensions_um": {"block": [671.705, 174.8]},
    "transistor_count": 395,
    "cap_count": 1024,
}
BANK_AREA = {
    "_comment": [
        "As-drawn area tally for the bank-fold candidate layout,",
        "written by gen_bank_fold_candidate.py (same schema as",
        "layout/adc-top/area.json, which this does not replace).",
    ],
    "areas_um2": {"block_total": 117414.034},
    "dimensions_um": {"block": [671.705, 174.8]},
    "transistor_count": 395,
    "unit_cap_device_count": 1024,
}


class AcquisitionLegCandidate(unittest.TestCase):
    def test_emits_through_the_shared_helper_at_its_own_count(self):
        outdir = _candidate_outdir(acq)
        self.addCleanup(shutil.rmtree, outdir, ignore_errors=True)
        g = _fake_generator(ACQ_TALLY)
        with mock.patch.object(
            acq, "_load_layout_generator", return_value=g
        ), redirect_stdout(io.StringIO()):
            rc = acq.main(["--scale", "0.5", "--outdir", outdir])
        self.assertEqual(rc, 0)
        candidate = os.path.join(outdir, "adc_top.candidate.spice")
        g.emit_deliverables.assert_called_once_with(candidate, outdir, expected_mos=350)
        g.build.assert_not_called()
        self.assertIn(
            "Xsi vin  bp gn_in  gp_in  vdd adc_tgate wn=5u wp=10u\n",
            Path(candidate).read_text(encoding="utf-8"),
        )
        area = json.loads(Path(outdir, "area.json").read_text(encoding="utf-8"))
        self.assertEqual(area["acq_leg_scale"], 0.5)
        self.assertEqual(area["areas_um2"], ACQ_TALLY["areas"])
        self.assertEqual(area["transistor_count"], 377)
        self.assertEqual(area["unit_cap_positions_per_side"], 512)
        self.assertEqual(
            area["unit_cap_census_per_side"], {"256": 2, "1": 1, "term": 1}
        )


class BankFoldCandidate(unittest.TestCase):
    def test_emits_through_the_shared_helper_at_the_ratified_count(self):
        outdir = _candidate_outdir(bank)
        self.addCleanup(shutil.rmtree, outdir, ignore_errors=True)
        g = _fake_generator(BANK_INFO)
        with mock.patch.object(
            bank, "_load_layout_generator", return_value=g
        ), redirect_stdout(io.StringIO()):
            rc = bank.main(["--outdir", outdir])
        self.assertEqual(rc, 0)
        g.emit_deliverables.assert_called_once_with(
            os.path.join(outdir, "adc_top.candidate.spice"), outdir
        )
        g.build.assert_not_called()

    def test_writes_area_json_once_from_the_block_tally(self):
        outdir = _candidate_outdir(bank)
        self.addCleanup(shutil.rmtree, outdir, ignore_errors=True)
        g = _fake_generator(BANK_INFO)
        with mock.patch.object(
            bank, "_load_layout_generator", return_value=g
        ), mock.patch.object(json, "dump", wraps=json.dump) as dump, redirect_stdout(
            io.StringIO()
        ):
            rc = bank.main(["--outdir", outdir])
        self.assertEqual(rc, 0)
        self.assertEqual(dump.call_count, 1)
        self.assertEqual(
            json.loads(Path(outdir, "area.json").read_text(encoding="utf-8")),
            BANK_AREA,
        )


if __name__ == "__main__":
    unittest.main()
