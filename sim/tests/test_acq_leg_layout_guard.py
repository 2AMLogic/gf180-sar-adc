"""DR-0050 layout guard for the acquisition-leg candidate generator (#1080).

The widened `Xsi` PMOS is one unfolded device; `place.draw_devices` rejects
an unpaired PMOS wider than `FOLD_ROW_MAX_W`. The generator must fail fast
with one message at the six sweep scales and still build at 0.5.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from _loadmod import load_module

REPO = Path(__file__).resolve().parents[2]
SWEEP_SCALES = (1.0, 1.1, 1.25, 1.5, 1.75, 2.068)

CAND = load_module(
    "gen_acq_leg_candidate_guard_t",
    REPO / "layout/adc-top/candidates/gen_acq_leg_candidate.py",
)


class LayoutGuardTests(unittest.TestCase):
    def test_sweep_scales_are_refused(self):
        for scale in SWEEP_SCALES:
            with self.subTest(scale=scale):
                msg = CAND.layout_buildable_error(scale)
                self.assertIsNotNone(msg)
                self.assertIn("DR-0050", msg)

    def test_limit_is_read_from_place_source(self):
        src = (REPO / "layout/adc-top/lib/place.py").read_text()
        self.assertIn(f"FOLD_ROW_MAX_W = {CAND.fold_row_max_w_nm()}", src)

    def test_half_scale_is_allowed(self):
        self.assertIsNone(CAND.layout_buildable_error(0.5))

    def test_boundary_matches_place_comparison(self):
        """place.py uses `>`: wp exactly at the limit passes."""
        at_limit = CAND.fold_row_max_w_nm() / 1000 / CAND.RATIFIED_WP_UM
        self.assertIsNone(CAND.layout_buildable_error(at_limit))
        self.assertIsNotNone(CAND.layout_buildable_error(at_limit * 1.001))

    def test_main_exits_before_layout_work(self):
        with self.assertRaises(SystemExit) as cm:
            CAND.main(["--scale", "1", "--outdir", str(CAND.HERE) + "/acq-leg-guard-unused"])
        self.assertIn("DR-0050", str(cm.exception))
        self.assertFalse(Path(CAND.HERE, "acq-leg-guard-unused").exists())


if __name__ == "__main__":
    unittest.main()
