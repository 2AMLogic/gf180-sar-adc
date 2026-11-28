#!/usr/bin/env python3
"""`lib/geometry.py`'s one contacted tap/tie strip primitive (issue #1139),
checked.

    python3 -m unittest discover -s sim/tests -v

Skipped when the pip `klayout` package is absent or is not the real one
(no `Box`/`Region`; it needs real regions).

The two straight contacted diffusion strips this library draws -- the
Nwell tap `draw_shared_nwell` draws (its top strip and every DF.13 extra
strip) and the per-row substrate tie `place._draw_substrate_tie_strip`
draws -- are both `geometry.draw_tap_strip`, differing only in the implant
marker and in whether the `Metal1` bar is the strip's own. Pinned here:

* the primitive's shapes and return value, with and without the `Metal1`
  bar, and the `Nplus`/`Pplus` marker going where it is told;
* a strip that cannot hold one contact is refused BEFORE anything is
  inserted, at exactly `contact_array`'s own minimum;
* a `trunk`-mode substrate tie drops a sub-contact sliver on one side of
  its stitch column, keeps a segment exactly one cut wide, and still
  refuses a row where neither side can hold a contact -- none of them
  leaving orphan diffusion behind.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

try:
    import klayout.db as kdb
except ImportError:  # pragma: no cover
    kdb = None
else:
    # A `klayout.db` that imports but lacks the real geometry API (a stub or a
    # different package under the same name) must skip, not error in setUpClass.
    if not all(hasattr(kdb, n) for n in ("Box", "Region")):  # pragma: no cover
        kdb = None

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "layout" / "adc-top" / "lib"


def _load_lib():
    """Import `lib.geometry` / `lib.place` as the generators do: the package
    path, because `place` imports `geometry` relatively."""
    if str(LIB.parent) not in sys.path:
        sys.path.insert(0, str(LIB.parent))
    from lib import geometry, netlist, place  # noqa: PLC0415

    return geometry, netlist, place


def _boxes(cell, layers, spec):
    """Every box on layer `spec` drawn in `cell`, sorted."""
    return sorted(s.box for s in cell.shapes(layers[spec]).each() if s.is_box())


def _cuts(geo, layout, layers, band, name):
    """What `contact_array` alone tiles into a fresh cell: `(count, boxes)`."""
    ref = layout.create_cell(name)
    count = geo.contact_array(ref, layers, band, along_x=True)
    return count, _boxes(ref, layers, geo.L_CONTACT)


def _grown(geo, box):
    return box.enlarged(geo.IMPLANT_MARGIN, geo.IMPLANT_MARGIN)


@unittest.skipIf(kdb is None, "needs the pip klayout package")
class DrawTapStrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo, _, _ = _load_lib()
        #: `contact_array`'s minimum: one cut inside its enclosure at both ends.
        cls.ONE_CUT_W = cls.geo.CO_SIDE + 2 * cls.geo.CO_ENCLOSURE

    def setUp(self):
        self.layout, self.layers = self.geo.make_layout()
        self.cell = self.layout.create_cell("T")
        self.strip = kdb.Box(0, 0, 3000, self.geo.TAP_COMP_H)

    def _draw(self, box, implant=None, **kwargs):
        return self.geo.draw_tap_strip(
            self.cell, self.layers, box, implant or self.geo.L_NPLUS, **kwargs
        )

    def _shapes(self, spec):
        return _boxes(self.cell, self.layers, spec)

    def _assert_nothing_drawn(self):
        for spec in (
            self.geo.L_COMP, self.geo.L_NPLUS, self.geo.L_CONTACT, self.geo.L_METAL1
        ):
            self.assertEqual(self._shapes(spec), [], spec)

    def test_draws_comp_implant_contacts_and_metal1(self):
        cuts = self._draw(self.strip)
        self.assertEqual(self._shapes(self.geo.L_COMP), [self.strip])
        self.assertEqual(self._shapes(self.geo.L_NPLUS), [_grown(self.geo, self.strip)])
        self.assertEqual(self._shapes(self.geo.L_METAL1), [self.strip])
        self.assertEqual(self._shapes(self.geo.L_PPLUS), [])
        # The cuts are exactly what `contact_array` tiles for this band: CO.1
        # squares, all inside the strip, and the return value is their count.
        expected, ref_cuts = _cuts(
            self.geo, self.layout, self.layers, self.strip, "REF"
        )
        self.assertGreater(expected, 0)
        self.assertEqual(cuts, expected)
        self.assertEqual(self._shapes(self.geo.L_CONTACT), ref_cuts)
        for c in ref_cuts:
            self.assertEqual((c.width(), c.height()), (self.geo.CO_SIDE,) * 2)
            self.assertTrue(c.inside(self.strip))

    def test_draw_metal1_false_omits_the_bar(self):
        cuts = self._draw(self.strip, draw_metal1=False)
        self.assertGreater(cuts, 0)
        self.assertEqual(self._shapes(self.geo.L_METAL1), [])
        self.assertEqual(self._shapes(self.geo.L_COMP), [self.strip])
        self.assertEqual(len(self._shapes(self.geo.L_CONTACT)), cuts)

    def test_pplus_marker_goes_on_pplus_only(self):
        self._draw(self.strip, implant=self.geo.L_PPLUS)
        self.assertEqual(self._shapes(self.geo.L_PPLUS), [_grown(self.geo, self.strip)])
        self.assertEqual(self._shapes(self.geo.L_NPLUS), [])

    def test_rejects_a_sliver_before_inserting_anything(self):
        sliver = kdb.Box(0, 0, self.ONE_CUT_W - 1, self.geo.TAP_COMP_H)
        with self.assertRaisesRegex(RuntimeError, "sliver tap strip .*enclosure"):
            self._draw(sliver, strip_name="sliver tap strip")
        self._assert_nothing_drawn()

    def test_rejects_a_strip_too_narrow_across_before_inserting_anything(self):
        # Long enough along X, but one nm short of a cut plus its enclosure
        # across it: `contact_array` tiles zero cuts for that too.
        thin = kdb.Box(0, 0, 3000, self.ONE_CUT_W - 1)
        with self.assertRaisesRegex(RuntimeError, "thin tap strip"):
            self._draw(thin, strip_name="thin tap strip")
        self._assert_nothing_drawn()

    def test_minimum_width_is_exactly_one_cut(self):
        exact = kdb.Box(0, 0, self.ONE_CUT_W, self.geo.TAP_COMP_H)
        self.assertEqual(self._draw(exact), 1)
        self.assertEqual(len(self._shapes(self.geo.L_CONTACT)), 1)


@unittest.skipIf(kdb is None, "needs the pip klayout package")
class SharedNwell(unittest.TestCase):
    """`draw_shared_nwell` draws its top tap strip and every extra strip
    through the same primitive."""

    @classmethod
    def setUpClass(cls):
        cls.geo, _, _ = _load_lib()

    def _shapes(self, spec):
        return _boxes(self.cell, self.layers, spec)

    def test_top_tap_and_extra_tap_are_draw_tap_strips(self):
        geo = self.geo
        self.layout, self.layers = geo.make_layout()
        self.cell = self.layout.create_cell("T")
        # One tall and one short PMOS column: the short one's top is beyond the
        # top strip's DF.13 reach, so a second strip is drawn over it.
        tall = kdb.Box(0, 0, 1000, 80000)
        short = kdb.Box(2000, 0, 3000, 35000)
        info = geo.draw_shared_nwell(self.cell, self.layers, [tall, short])

        def assert_is_tap_strip(comp, ref_name):
            ref = self.layout.create_cell(ref_name)
            n_cuts = geo.contact_array(ref, self.layers, comp, along_x=True)
            self.assertGreater(n_cuts, 0)
            self.assertIn(comp, self._shapes(geo.L_COMP))
            self.assertIn(_grown(geo, comp), self._shapes(geo.L_NPLUS))
            self.assertIn(comp, self._shapes(geo.L_METAL1))
            # Every cut inside the strip is one `contact_array` tiled for it,
            # and that is all of the cuts in the strip.
            self.assertEqual(
                [c for c in self._shapes(geo.L_CONTACT) if c.inside(comp)],
                _boxes(ref, self.layers, geo.L_CONTACT),
            )
            return n_cuts

        self.assertEqual(
            assert_is_tap_strip(info.tap_comp, "REF_top"), info.tap_contacts
        )
        self.assertEqual(info.tap_metal1, info.tap_comp)
        self.assertEqual(len(info.extra_taps), 1)
        extra_comp, extra_metal1, extra_cuts = info.extra_taps[0]
        y0 = short.top + geo.TAP_ACTIVE_GAP
        self.assertEqual(
            extra_comp, kdb.Box(short.left, y0, short.right, y0 + geo.TAP_COMP_H)
        )
        self.assertEqual(extra_metal1, extra_comp)
        self.assertEqual(assert_is_tap_strip(extra_comp, "REF_extra"), extra_cuts)
        # Nothing but the two strips is drawn on these layers by this call.
        self.assertEqual(len(self._shapes(geo.L_COMP)), 2)
        self.assertEqual(len(self._shapes(geo.L_METAL1)), 2)

    def test_union_box_matches_the_inline_loop(self):
        geo = self.geo
        boxes = [kdb.Box(0, 0, 10, 10), kdb.Box(-5, 3, 4, 20), kdb.Box(100, -2, 120, 7)]
        out = boxes[0]
        for a in boxes[1:]:
            out = out + a
        self.assertEqual(geo._union_box(boxes), out)
        self.assertEqual(geo._union_box(boxes[:1]), boxes[0])


@unittest.skipIf(kdb is None, "needs the pip klayout package")
class SubstrateTieStrip(unittest.TestCase):
    """`place._draw_substrate_tie_strip` on a hand-built row."""

    @classmethod
    def setUpClass(cls):
        cls.geo, cls.nl, cls.place = _load_lib()
        cls.ONE_CUT_W = cls.geo.CO_SIDE + 2 * cls.geo.CO_ENCLOSURE

    def _block(self, row_x0, row_x1, *, riser_x=None, via="trunk"):
        """A placed row `[row_x0, row_x1]` with one NMOS column (so the row
        wants a tie strip) and a `vss` trunk that carries the stitch corridor
        at `riser_x` without a drop riser of its own in that column."""
        geo = self.geo
        self.layout, self.layers = geo.make_layout()
        cell = self.layout.create_cell("T")
        channel = geo.Channel(cell, self.layers, 0)
        if riser_x is None:
            channel.extend("vss", (row_x0 + row_x1) // 2)
        else:
            channel.extend("vss", riser_x - 200)
            channel.extend("vss", riser_x + 200)
        trunks = channel.finish()
        nfet = self.nl.Device(
            kind="nfet", path="XM", nets=("a", "b", "c"),
            params={"w": 1e-6, "l": 5e-7},
        )
        return self.place.PlacedBlock(
            channel=channel, trunks=trunks, devices=[(nfet, None)],
            nwell=[], taps=[], body_net={},
            row_x0=row_x0, row_x1=row_x1, row_y0=0,
            substrate_net=self.nl.SUBSTRATE_NET, subtie_via=via,
            subtie_riser_x=riser_x, subtie_fallback_x=None,
        )

    def _shapes(self, block, spec):
        return _boxes(block.channel.cell, block.channel.layers, spec)

    def _strip_y(self, block):
        y1 = block.channel.y_bottom - self.geo.SUBTIE_M1_GAP
        return y1 - self.geo.TAP_COMP_H, y1

    def _right_segment(self, block, riser_x, row_x1):
        y0, y1 = self._strip_y(block)
        return kdb.Box(riser_x + self.geo.SUBTIE_RISER_COMP_CLEAR, y0, row_x1, y1)

    def test_drops_a_sub_contact_sliver_beside_a_contactable_segment(self):
        geo = self.geo
        # The stitch column leaves 200 nm of Comp inside the row on its left
        # -- under one cut plus its enclosure -- and 8640 nm on its right.
        riser_x = geo.SUBTIE_RISER_COMP_CLEAR + 200
        block = self._block(0, 10000, riser_x=riser_x)
        self.place._draw_substrate_tie_strip(block)  # must not raise
        y0, y1 = self._strip_y(block)
        sliver = kdb.Box(0, y0, riser_x - geo.SUBTIE_RISER_COMP_CLEAR, y1)
        self.assertEqual(sliver.width(), 200)
        kept = self._right_segment(block, riser_x, 10000)
        self.assertEqual(self._shapes(block, geo.L_COMP), [kept])
        self.assertEqual(self._shapes(block, geo.L_PPLUS), [_grown(geo, kept)])
        # The dropped sliver carries no cut; the kept segment is contacted.
        cuts = self._shapes(block, geo.L_CONTACT)
        self.assertFalse(any(c.overlaps(sliver) for c in cuts))
        n_cuts, ref_cuts = _cuts(geo, self.layout, self.layers, kept, "REF")
        self.assertGreater(n_cuts, 0)
        self.assertEqual([c for c in cuts if c.inside(kept)], ref_cuts)
        # The one Metal1 bar still spans the whole row and carries the stitch
        # down to the trunk.
        bar = kdb.Box(0, y0, 10000, y1)
        self.assertEqual(block.subtie_metal1, bar)
        self.assertIn(bar, self._shapes(block, geo.L_METAL1))
        poly2 = self._shapes(block, geo.L_POLY2)
        self.assertEqual(len(poly2), 1)
        self.assertEqual(poly2[0].center().x, riser_x)

    def test_keeps_a_segment_exactly_one_cut_wide(self):
        geo = self.geo
        riser_x = geo.SUBTIE_RISER_COMP_CLEAR + self.ONE_CUT_W
        block = self._block(0, 10000, riser_x=riser_x)
        self.place._draw_substrate_tie_strip(block)
        y0, y1 = self._strip_y(block)
        exact = kdb.Box(0, y0, self.ONE_CUT_W, y1)
        self.assertEqual(
            self._shapes(block, geo.L_COMP),
            [exact, self._right_segment(block, riser_x, 10000)],
        )
        self.assertEqual(
            sum(c.inside(exact) for c in self._shapes(block, geo.L_CONTACT)), 1
        )

    def test_keeps_both_segments_when_both_hold_contacts(self):
        geo = self.geo
        block = self._block(0, 10000, riser_x=5000)
        self.place._draw_substrate_tie_strip(block)
        y0, y1 = self._strip_y(block)
        left = kdb.Box(0, y0, 5000 - geo.SUBTIE_RISER_COMP_CLEAR, y1)
        right = self._right_segment(block, 5000, 10000)
        self.assertEqual(self._shapes(block, geo.L_COMP), [left, right])
        self.assertEqual(block.subtie_metal1, kdb.Box(0, y0, 10000, y1))

    def test_raises_without_orphans_when_neither_side_holds_a_contact(self):
        geo = self.geo
        # 320 nm of Comp on each side of the column: inside the row, but under
        # one cut plus its enclosure.
        block = self._block(0, 1800, riser_x=900)
        with self.assertRaisesRegex(RuntimeError, "no room for a contacted segment"):
            self.place._draw_substrate_tie_strip(block)
        self.assertEqual(self._shapes(block, geo.L_COMP), [])
        self.assertEqual(self._shapes(block, geo.L_PPLUS), [])
        self.assertEqual(self._shapes(block, geo.L_POLY2), [])
        self.assertIsNone(block.subtie_metal1)

    def test_ring_mode_spans_the_whole_row(self):
        geo = self.geo
        block = self._block(0, 10000, via="ring")
        self.place._draw_substrate_tie_strip(block)
        y0, y1 = self._strip_y(block)
        comp = kdb.Box(0, y0, 10000, y1)
        self.assertEqual(self._shapes(block, geo.L_COMP), [comp])
        self.assertEqual(self._shapes(block, geo.L_PPLUS), [_grown(geo, comp)])
        self.assertEqual(block.subtie_metal1, comp)
        self.assertIn(comp, self._shapes(block, geo.L_METAL1))
        n_cuts, ref_cuts = _cuts(geo, self.layout, self.layers, comp, "REF")
        self.assertGreater(n_cuts, 0)
        self.assertEqual(self._shapes(block, geo.L_CONTACT), ref_cuts)


if __name__ == "__main__":
    unittest.main()
