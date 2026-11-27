#!/usr/bin/env python3
"""The decode banks' five shared-net ties go through `geo.stitch`, checked.

    python3 -m unittest discover -s sim/tests -p 'test_decode_bank_stitch.py' -v

Skipped when the pip `klayout` package is absent or is not the real one
(no `Layout`/`Box`/`Region`; `gen_adc_top.build` needs real geometry), like
`test_notched_guard_ring.py`.

Why this file exists. `gen_adc_top.build` ties `vdd`, `vss`, `vref`, `vcm`
and `sel_in` between the two decode banks with one Poly2 riser per net.
Until issue #1071 it drew those five by hand, keeping only each trunk's Y
span: the trunk's X extent was dropped before the contacts were placed, so
a trunk that stopped short of the stitch column got a contact in the air
-- DRC-clean, and silently leaving the two banks unconnected. `geo.stitch`,
the primitive every other top-level tie in that file already uses, asserts
the riser lies inside every trunk and that its corridor crosses no
diffusion and no other Poly2. The drawn stream is byte-identical either
way, so neither DRC, nor LVS, nor the byte-reproducibility check can tell
whether this tie is guarded. These tests can:

* each of the five nets is handed to `geo.stitch` exactly once, with the
  two banks' own trunk boxes moved to the banks' Y offsets, on one column
  pitch left to right in the generator's net order;
* a trunk that stops short of its column makes `build()` fail at that
  net's tie, in `geo.stitch`'s own words.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from _loadmod import load_module

try:
    import klayout.db as kdb
except ImportError:  # pragma: no cover
    kdb = None
else:
    # A `klayout.db` that imports but lacks the real geometry API (a stub or
    # a different package under the same name) must skip, not error in
    # setUpClass.
    if not all(  # pragma: no cover
        hasattr(kdb, n) for n in ("Layout", "Box", "Region")
    ):
        kdb = None

REPO = Path(__file__).resolve().parents[2]
ADC_TOP = REPO / "layout" / "adc-top"

#: The nets both decode banks carry as ONE shared net (`bank_shared` in
#: `gen_adc_top.build`), in the generator's own order -- the order that
#: assigns each its stitch column.
SHARED = ("vdd", "vss", "vref", "vcm", "sel_in")
BANK_CELLS = {"p": "ADC_DECODE_BANK_P", "n": "ADC_DECODE_BANK_N"}


def _boxes(boxes):
    return {(b.left, b.bottom, b.right, b.top) for b in boxes}


@unittest.skipIf(kdb is None, "needs the pip klayout package")
class DecodeBankStitch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ADC_TOP))
        cls.gen = load_module(
            "layout_gen_adc_top_bank_tie", ADC_TOP / "gen_adc_top.py"
        )
        design = cls.gen.nl.design_dir(str(ADC_TOP))
        cls.subckts = cls.gen.nl.parse(
            os.path.join(design, "adc-top", "adc_top.spice")
        )
        cls.gen.block_subckt(cls.subckts)
        cls.top = cls.gen.CELL_NAME

    def _build(self, shorten=None):
        """`gen.build` for the comparator-free `adc_top` stream, returned as
        `(layout, stitch calls, bank handles)`.

        `calls` is every `geo.stitch` invocation as `(x, trunk boxes)`;
        `handles` is the placer's own block per decode bank. Both are taken
        through `mock.patch.object`, so nothing outlives the call.

        `shorten = (tag, net)` cuts that bank's `net` trunk box back to its
        midpoint before anything reads it -- the handle a placer that stopped
        a trunk short of the escape corridor would hand back, with the drawn
        Metal1 exactly as placed.
        """
        gen = self.gen
        calls = []
        handles = {}
        real_stitch = gen.geo.stitch
        real_draw = gen.place.draw_devices

        def recording_stitch(cell, layers, x, trunks, *args, **kwargs):
            calls.append((x, list(trunks)))
            return real_stitch(cell, layers, x, trunks, *args, **kwargs)

        def capturing_draw(cell, layers, groups, *args, **kwargs):
            block = real_draw(cell, layers, groups, *args, **kwargs)
            for tag, name in BANK_CELLS.items():
                if cell.name == name:
                    handles[tag] = block
                    if shorten is not None and shorten[0] == tag:
                        box = block.trunks[shorten[1]]
                        block.trunks[shorten[1]] = kdb.Box(
                            box.left,
                            box.bottom,
                            (box.left + box.right) // 2,
                            box.top,
                        )
            return block

        with mock.patch.object(
            gen.geo, "stitch", recording_stitch
        ), mock.patch.object(
            gen.place, "draw_devices", capturing_draw
        ):
            layout, _info = gen.build(
                self.subckts, None, cell_name=self.top
            )
        return layout, calls, handles

    def _bank_y(self, layout):
        """Y offset at which the top cell instantiates each decode bank."""
        return {
            tag: inst.trans.disp.y
            for inst in layout.cell(self.top).each_inst()
            for tag, name in BANK_CELLS.items()
            if inst.cell.name == name
        }

    def test_each_shared_net_is_tied_by_stitch_with_both_banks_trunks(self):
        layout, calls, handles = self._build()
        bank_y = self._bank_y(layout)
        self.assertEqual(set(bank_y), {"p", "n"})
        columns = []
        for net in SHARED:
            expected = _boxes(
                handles[tag].trunks[net].moved(0, bank_y[tag])
                for tag in ("p", "n")
            )
            hits = [x for x, trunks in calls if _boxes(trunks) == expected]
            self.assertEqual(
                len(hits),
                1,
                f"{net}: {len(hits)} geo.stitch calls carry the two banks' "
                f"moved {net} trunks (expected exactly one)",
            )
            columns.append(hits[0])
        expected_columns = [
            handles["p"].row_x1 + 1500 + i * 1000 for i in range(len(SHARED))
        ]
        self.assertEqual(columns, expected_columns)

    def test_trunk_short_of_its_column_fails_at_that_nets_tie(self):
        for net in SHARED:
            with self.subTest(net=net), self.assertRaisesRegex(
                RuntimeError, r"stitch x=-?\d+ is outside trunk -?\d+\.\.-?\d+"
            ):
                self._build(shorten=("n", net))


if __name__ == "__main__":
    unittest.main()
