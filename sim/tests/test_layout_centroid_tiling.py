#!/usr/bin/env python3
"""`layout/adc-top/gen_adc_top.py`'s common-centroid tiling, checked.

    python3 -m unittest discover -s sim/tests -v

Why this file exists. Every matching decision in `layout/adc-top/README.md`
is backed by a check except one: `centroid_tiling()`'s claim about where the
unit capacitors of each binary weight actually land. The layout's whole
matching argument rests on that function -- if a future edit to the deal
order silently moves a weight's centroid off the array centre, nothing in
DRC or LVS would notice (both are blind to *which* unit position belongs to
which weight, only that the devices and nets match).

PR #62's review found the gap the hard way: the docstring claimed the two
ODD-count groups were "each displaced by half a pitch in opposite
directions ... the minimum possible asymmetry for an odd count", and the
measured behaviour is nothing of the sort -- the shared pair lands wherever
the bit-reversed deal puts it, 14.5 pitches off centre in the array this
block actually builds. The docstring is now corrected to describe what the
code does; these tests are what keeps the two in agreement.

So this module asserts, for the array `draw_cdac_array()` really tiles:

* every EVEN-count weight group has a centroid at *exactly* the array
  centre (the strong claim -- it holds, and must keep holding);
* the two ODD-count groups' *combined* centroid is exactly the array centre
  (the only guarantee the construction makes about them);
* each odd group's *individual* offset is the measured (14.5, 0.5) pitches
  (the weak claim -- pinned as a regression guard, deliberately hard-coded
  so improving it is a conscious edit to this file, not an accident);
* the docstring no longer carries the disproved "half a pitch" claim.

Needs neither ngspice nor the PDK, so it runs on the PDK-free CI path with
the rest of `sim/tests`. It does not need KLayout either: `centroid_tiling`
is pure integer arithmetic, and the `klayout.db` import its module makes at
top level is stubbed below when the package is absent (as it is in CI).
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "layout" / "adc-top" / "gen_adc_top.py"


def _load_generator():
    """Import `layout/adc-top/gen_adc_top.py` without KLayout installed.

    The generator (and its `lib.geometry` / `lib.place` helpers) do
    `import klayout.db as kdb` at module scope. `centroid_tiling` never
    touches it, so an empty placeholder module is enough to get the import
    through on a machine -- or a CI runner -- with no `klayout` wheel. The
    real package is preferred whenever it *is* installed, so this never
    shadows a working install.
    """
    try:
        import klayout.db  # noqa: F401, PLC0415
    except ImportError:
        klayout = types.ModuleType("klayout")
        klayout.__path__ = []  # mark as a package so `klayout.db` resolves
        db = types.ModuleType("klayout.db")
        klayout.db = db
        sys.modules.setdefault("klayout", klayout)
        sys.modules.setdefault("klayout.db", db)

    # Distinct module name: `sim/tests/test_adc_top_netlist.py` loads the
    # *design*-side `gen_adc_top.py` as "gen_adc_top" in the same process.
    spec = importlib.util.spec_from_file_location("layout_gen_adc_top", GEN)
    module = importlib.util.module_from_spec(spec)
    sys.modules["layout_gen_adc_top"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_generator()

#: The tiling `draw_cdac_array()` builds, restated here rather than imported
#: from inside it (it needs a KLayout `Layout` to run). Kept in sync by
#: `test_group_list_matches_the_array_builder`.
GROUPS = [(str(w), w) for w in gen.WEIGHT_ORDER] + [("term", 1)]

#: Measured behaviour of the odd (paired) groups, pinned as a regression
#: guard. See this module's docstring and `centroid_tiling`'s: the
#: construction guarantees only that these two positions are a
#: centro-symmetric pair, NOT that the pair is near the centre. If a
#: deliberate improvement moves them, update these two lines with it.
ODD_POSITIONS = {"1": (30, 7), "term": (1, 8)}
#: (col, row) offset of each odd group from the array centre, in pitches.
ODD_OFFSET_PITCHES = (Fraction(29, 2), Fraction(-1, 2))


def centroid(positions):
    """Exact (Fraction) centroid -- no float rounding in any assertion."""
    n = len(positions)
    return (
        Fraction(sum(c for c, _ in positions), n),
        Fraction(sum(r for _, r in positions), n),
    )


def by_group(assignment):
    out = defaultdict(list)
    for pos, name in assignment.items():
        out[name].append(pos)
    return out


class ArrayTilingTests(unittest.TestCase):
    """The tiling of the array `draw_cdac_array()` actually draws."""

    @classmethod
    def setUpClass(cls):
        cls.cols = gen.ARRAY_COLS
        cls.rows = gen.ARRAY_ROWS
        cls.centre = (
            Fraction(cls.cols - 1, 2),
            Fraction(cls.rows - 1, 2),
        )
        cls.assignment = gen.centroid_tiling(cls.cols, cls.rows, GROUPS)
        cls.groups = by_group(cls.assignment)

    def test_group_list_matches_the_array_builder(self):
        """Guard the restatement of `draw_cdac_array`'s group list above."""
        source = GEN.read_text()
        self.assertIn(
            'groups = [(str(w), w) for w in WEIGHT_ORDER] + [("term", 1)]',
            source,
            "draw_cdac_array's group list changed -- update GROUPS here",
        )

    def test_every_position_is_assigned_exactly_once(self):
        self.assertEqual(len(self.assignment), self.cols * self.rows)
        self.assertEqual(
            sorted(self.assignment),
            sorted(
                (c, r) for r in range(self.rows) for c in range(self.cols)
            ),
        )

    def test_each_group_gets_the_unit_count_it_asked_for(self):
        for name, count in GROUPS:
            with self.subTest(group=name):
                self.assertEqual(len(self.groups[name]), count)

    def test_even_count_groups_sit_exactly_on_the_array_centre(self):
        """The strong claim, and the one that carries the matching argument:
        every weight with an even unit count has zero first-order gradient
        term. Exact rational arithmetic, so "exactly" means exactly."""
        for name, count in GROUPS:
            if count % 2:
                continue
            with self.subTest(group=name, units=count):
                self.assertEqual(centroid(self.groups[name]), self.centre)

    def test_even_count_groups_are_built_from_centro_symmetric_pairs(self):
        """*Why* the centroid is exact: every position an even group owns has
        its own 180-degree rotation in the same group. A group could in
        principle hit the centre by luck; this says it cannot."""
        for name, count in GROUPS:
            if count % 2:
                continue
            positions = set(self.groups[name])
            with self.subTest(group=name):
                for c, r in positions:
                    partner = (self.cols - 1 - c, self.rows - 1 - r)
                    self.assertIn(
                        partner,
                        positions,
                        f"{name} owns {(c, r)} without its rotation {partner}",
                    )

    def test_the_two_odd_groups_share_one_centro_symmetric_pair(self):
        odd = [name for name, count in GROUPS if count % 2]
        self.assertEqual(sorted(odd), ["1", "term"])
        (first,) = self.groups[odd[0]]
        (second,) = self.groups[odd[1]]
        self.assertEqual(
            (self.cols - 1 - first[0], self.rows - 1 - first[1]),
            second,
            "the odd groups no longer occupy the two halves of one pair",
        )

    def test_combined_odd_group_centroid_is_exactly_the_array_centre(self):
        """The only guarantee the construction makes about the odd groups --
        and the half of the docstring's claim that was always true."""
        odd = [name for name, count in GROUPS if count % 2]
        combined = [pos for name in odd for pos in self.groups[name]]
        self.assertEqual(centroid(combined), self.centre)

    def test_individual_odd_group_offset_is_the_measured_one(self):
        """The regression guard PR #62's review asked for.

        NOT half a pitch: the shared pair is dealt like any other, so each
        odd group sits 14.5 pitches off centre in the column direction. The
        error is a `displacement x gradient x C_u` term against a ONE-unit
        weight (the LSB and DR-0011's terminating unit), which is why it is
        recorded rather than fixed -- but it is recorded, so shrinking or
        growing it can never happen silently.
        """
        dx_expect, dy_expect = ODD_OFFSET_PITCHES
        for name, expected_pos in ODD_POSITIONS.items():
            with self.subTest(group=name):
                self.assertEqual(self.groups[name], [expected_pos])
                cx, cy = centroid(self.groups[name])
                dx, dy = cx - self.centre[0], cy - self.centre[1]
                self.assertEqual((abs(dx), abs(dy)), (abs(dx_expect), abs(dy_expect)))

        # Restated in the units the docstring quotes, so the two cannot drift.
        offset_nm = abs(dx_expect) * gen.UNIT_PITCH
        self.assertEqual(round(float(offset_nm) / 1000.0, 1), 56.8)

    def test_docstring_no_longer_makes_the_disproved_claim(self):
        """PR #62's finding was a doc/code disagreement, not a code bug. The
        code is measured above; this measures the prose."""
        # Whitespace-normalised: the claim is a wrapped sentence, so a
        # literal substring search would miss it purely on line breaks.
        doc = " ".join(gen.centroid_tiling.__doc__.split())
        for disproved in (
            "displaced by half a pitch in opposite directions",
            "minimum possible asymmetry",
        ):
            self.assertNotIn(disproved, doc)
        # And it states the measured behaviour these tests assert.
        self.assertIn("(30, 7)", doc)
        self.assertIn("combined", doc)


class TilingContractTests(unittest.TestCase):
    """`centroid_tiling` as a general routine, on arrays small enough to check
    by hand -- so its invariants are pinned independently of one 32x16 call."""

    def test_all_even_groups_land_on_centre(self):
        cols, rows = 8, 4
        centre = (Fraction(cols - 1, 2), Fraction(rows - 1, 2))
        groups = [("a", 16), ("b", 8), ("c", 4), ("d", 4)]
        assignment = gen.centroid_tiling(cols, rows, groups)
        for name, positions in by_group(assignment).items():
            with self.subTest(group=name):
                self.assertEqual(centroid(positions), centre)

    def test_two_odd_groups_combine_onto_centre(self):
        cols, rows = 8, 4
        centre = (Fraction(cols - 1, 2), Fraction(rows - 1, 2))
        groups = [("a", 16), ("b", 8), ("c", 6), ("d", 1), ("e", 1)]
        by = by_group(gen.centroid_tiling(cols, rows, groups))
        self.assertEqual(centroid(by["d"] + by["e"]), centre)
        for even in ("a", "b", "c"):
            with self.subTest(group=even):
                self.assertEqual(centroid(by[even]), centre)

    def test_odd_counts_greater_than_one_are_rejected(self):
        """A limitation worth pinning, found writing these tests: the shared
        pseudo-group is one pair wide, so an odd group contributes exactly
        one pair to the accounting no matter how many units it declares. An
        odd count above 1 therefore loses `count // 2` pairs and the routine
        refuses the tiling rather than mis-placing it. Fine for this block
        (both odd groups are single units), but a caller that grows one of
        them gets an error, not a silently broken centroid."""
        with self.assertRaises(ValueError):
            gen.centroid_tiling(8, 4, [("a", 16), ("b", 9), ("c", 6), ("d", 1)])

    def test_rejects_an_odd_sized_array(self):
        with self.assertRaises(ValueError):
            gen.centroid_tiling(3, 3, [("a", 9)])

    def test_rejects_counts_that_do_not_fill_the_array(self):
        with self.assertRaises(ValueError):
            gen.centroid_tiling(4, 2, [("a", 7)])

    def test_rejects_more_than_two_odd_groups(self):
        with self.assertRaises(ValueError):
            gen.centroid_tiling(4, 2, [("a", 3), ("b", 3), ("c", 1), ("d", 1)])


if __name__ == "__main__":
    unittest.main()
