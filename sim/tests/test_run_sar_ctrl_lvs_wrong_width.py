"""Issue #757: `run_sar_ctrl_lvs.wrong_width()` -- the LVS wrong-device-width
negative control -- must keep matching the PDK `__nor2_1` text after the
open_pdks `c6d73a3` -> `f6eeac7` re-pin renamed the bound device subcircuit
from `pfet_06v0` to `pfet_05v0`, and must still fail loudly when the cell it
perturbs is absent.

Why this test exists: `wrong_width()` is one of the two DIAGNOSTIC negative
controls that make a clean `committed` LVS verdict meaningful. It raises
`RuntimeError` on a non-match, so a stale device-name anchor does not silently
weaken the compare -- it crashes the whole runner. Nothing here runs `klt`,
reads the PDK, or needs a GDS: the function is a pure text rewrite.

The `__nor2_1` snippets below are copied VERBATIM out of the two library
revisions (the `f6eeac7` one from
`$PDK_ROOT/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/`); only the
device-flavor token differs between them.

Stdlib only.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402

mod = load_module("run_sar_ctrl_lvs_under_test", REPO / "layout/lvs/run_sar_ctrl_lvs.py")
LIB = mod.LIBRARY


def nor2_1(flavor_n: str, flavor_p: str) -> str:
    """The `__nor2_1` subckt as the PDK library writes it, device flavor
    parameterised. `f6eeac7` emits ("nfet_05v0", "pfet_05v0"); `c6d73a3`
    emitted ("nfet_06v0", "pfet_06v0")."""
    return (
        f".SUBCKT {LIB}__nor2_1 A1 A2 ZN VDD VNW VPW VSS\n"
        f"X_i_1 ZN A2 VSS VPW {flavor_n} W=5.65e-07 L=6e-07\n"
        f"X_i_0 VSS A1 ZN VPW {flavor_n} W=5.65e-07 L=6e-07\n"
        f"X_i_3 net_0 A2 VDD VNW {flavor_p} W=1.22e-06 L=5e-07\n"
        f"X_i_2 ZN A1 net_0 VNW {flavor_p} W=1.22e-06 L=5e-07\n"
        ".ENDS\n"
    )


#: A second cell that also carries a 1.22e-06 pfet, to prove the rewrite is
#: anchored on `__nor2_1` and does not wander into a neighbouring subckt.
OTHER_CELL = (
    f".SUBCKT {LIB}__nor2_2 A1 A2 ZN VDD VNW VPW VSS\n"
    "X_i_3 net_0 A2 VDD VNW pfet_05v0 W=1.22e-06 L=5e-07\n"
    ".ENDS\n"
)

PINNED = nor2_1("nfet_05v0", "pfet_05v0")   # open_pdks f6eeac7 (the pinned PDK)
LEGACY = nor2_1("nfet_06v0", "pfet_06v0")   # open_pdks c6d73a3 (pre-re-pin)


class WrongWidthRewrite(unittest.TestCase):
    def assert_rewritten_once(self, golden: str) -> str:
        out, what = mod.wrong_width(golden)
        self.assertNotEqual(out, golden, "the golden text was not perturbed at all")
        self.assertIn("1.22u -> 1.00u", what)
        # Exactly one width moved, and it is X_i_3's.
        self.assertEqual(out.count("W=1.00e-06"), 1, out)
        self.assertEqual(
            golden.count("W=1.22e-06") - out.count("W=1.22e-06"), 1, out)
        self.assertRegex(
            out, r"X_i_3 net_0 A2 VDD VNW pfet_[0-9a-z_]+ W=1\.00e-06 L=5e-07")
        return out

    def test_matches_the_pinned_f6eeac7_text(self):
        """The regression this issue exists for: the pinned library says
        `pfet_05v0`, and the control must still perturb it."""
        self.assert_rewritten_once(PINNED)

    def test_still_matches_the_pre_repin_text(self):
        """Flavor-agnostic, not flavor-swapped: the old `pfet_06v0` spelling
        keeps working, so this control does not break again on the next
        re-pin in either direction."""
        self.assert_rewritten_once(LEGACY)

    def test_perturbs_only_the_nor2_1_cell(self):
        out = self.assert_rewritten_once(PINNED + OTHER_CELL)
        self.assertIn(OTHER_CELL, out, "a neighbouring cell was rewritten too")

    def test_x_i_2_is_left_alone(self):
        """`count=1`: the sibling pfet in the same cell keeps its width."""
        out = self.assert_rewritten_once(PINNED)
        self.assertIn("X_i_2 ZN A1 net_0 VNW pfet_05v0 W=1.22e-06 L=5e-07", out)


class WrongWidthFailsLoudly(unittest.TestCase):
    def assert_raises_on(self, golden: str):
        with self.assertRaises(RuntimeError) as cm:
            mod.wrong_width(golden)
        self.assertIn("nor2_1 pfet X_i_3 not found", str(cm.exception))

    def test_raises_when_the_cell_is_absent(self):
        """No `__nor2_1` at all -- the control must crash, never silently
        return an unperturbed golden that would compare clean."""
        self.assert_raises_on(OTHER_CELL)

    def test_raises_on_empty_text(self):
        self.assert_raises_on("")

    def test_raises_when_the_width_is_not_the_expected_one(self):
        """The anchor is the exact 1.22u width; if the library re-sizes the
        cell, that is a real change to look at, not something to paper over."""
        self.assert_raises_on(PINNED.replace("W=1.22e-06", "W=1.30e-06"))

    def test_raises_when_the_instance_line_changes_shape(self):
        """Port order / net naming is part of the anchor."""
        self.assert_raises_on(
            PINNED.replace("X_i_3 net_0 A2 VDD VNW", "X_i_3 net_0 A1 VDD VNW"))


if __name__ == "__main__":
    unittest.main()
