#!/usr/bin/env python3
"""`lib/geometry.py`'s L-shaped guard ring (issue #667, DR-0042), checked.

    python3 -m unittest discover -s sim/tests -v

Skipped when the pip `klayout` package is absent (it needs real regions).
Asserts the shape, closure and width of the ring the SAR-reserve notch needs.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from _loadmod import load_module

try:
    import klayout.db as kdb
except ImportError:  # pragma: no cover
    kdb = None

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "layout" / "adc-top" / "lib"


@unittest.skipIf(kdb is None, "needs the pip klayout package")
class NotchedGuardRing(unittest.TestCase):
    W = 1400
    BOX = None
    NOTCH = None

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(LIB.parent))
        cls.geo = load_module("layout_geometry_notch", LIB / "geometry.py")
        cls.BOX = kdb.Box(0, 0, 100000, 60000)
        cls.NOTCH = kdb.Box(60000, 30000, 100000, 60000)

    def _ring_region(self):
        r = kdb.Region()
        for b in self.geo.notched_ring_bars(self.BOX, self.NOTCH, self.W):
            r.insert(b)
        r.merge()
        return r

    def test_ring_is_one_closed_annulus(self):
        ring = self._ring_region()
        self.assertEqual(ring.count(), 1)
        self.assertEqual(ring.holes().count(), 1)

    def test_ring_area_matches_l_shape(self):
        l_shape = kdb.Region(self.BOX) - kdb.Region(self.NOTCH)
        expected = l_shape.sized(self.W, 2) - l_shape  # square corners
        self.assertEqual((self._ring_region() ^ expected).area(), 0)

    def test_ring_width_is_uniform(self):
        ring = self._ring_region()
        # eroding by half the width must leave a non-empty centreline, and by
        # a full width nothing
        self.assertFalse(ring.sized(-(self.W // 2 - 1)).is_empty())
        self.assertTrue(ring.sized(-(self.W // 2)).is_empty())

    def test_inner_region_is_the_l_shape(self):
        ring = self._ring_region()
        l_shape = kdb.Region(self.BOX) - kdb.Region(self.NOTCH)
        self.assertEqual((ring.holes() ^ l_shape).area(), 0)

    def test_draw_closes_metal1_and_contacts(self):
        layout, layers = self.geo.make_layout()
        cell = layout.create_cell("T")
        outer = self.geo.draw_notched_guard_ring(
            cell, layers, self.BOX, self.NOTCH, self.W, label_net="vss"
        )
        self.assertEqual(outer, self.BOX.enlarged(self.W, self.W))
        m1 = kdb.Region(cell.shapes(layers[self.geo.L_METAL1])).merged()
        self.assertEqual(m1.count(), 1)
        self.assertEqual(m1.holes().count(), 1)
        floor = self.geo.notched_ring_floor_metal1(self.NOTCH, self.W)
        self.assertTrue((m1 & kdb.Region(floor)).area() > 0)
        self.assertEqual((kdb.Region(floor) - m1).area(), 0)
        self.assertGreater(cell.shapes(layers[self.geo.L_CONTACT]).size(), 0)

    def test_rejects_non_corner_notch(self):
        with self.assertRaises(ValueError):
            self.geo.notched_ring_bars(self.BOX, kdb.Box(10, 10, 20, 20), self.W)


if __name__ == "__main__":
    unittest.main()
