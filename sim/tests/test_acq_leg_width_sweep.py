"""Guards for the acquisition-leg width sweep (issue #429).

* the layout candidate generator and the schematic variant generator emit the
  SAME `Xsi` widths at every swept scale (the pairing is only valid if so);
* the default 2.068x path still reproduces the literal rejected candidate;
* candidate outputs cannot land outside layout/adc-top/candidates/;
* the sweep manifest's measurement blocks equal the dr0019-cu-sweep ones.
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCALES = (1.0, 1.1, 1.25, 1.5, 1.75, 2.068)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAND = _load("gen_acq_leg_candidate_t", REPO / "layout/adc-top/candidates/gen_acq_leg_candidate.py")
VAR = _load("gen_cu_variant_t", REPO / "sim/dr0019-cu-sweep/gen_cu_variant.py")


def _widths(line: str) -> tuple[float, float]:
    m = re.search(r"wn=([0-9.]+)u wp=([0-9.]+)u", line)
    return float(m.group(1)), float(m.group(2))


class WidthSweepTests(unittest.TestCase):
    def test_default_scale_is_the_rejected_candidate(self):
        self.assertEqual(CAND.candidate_line(2.068), CAND.ACQ_LEG_CANDIDATE)

    def test_control_is_the_ratified_line(self):
        self.assertEqual(CAND.candidate_line(1.0), CAND.ACQ_LEG_LINE)

    def test_layout_and_schematic_widths_agree(self):
        for s in SCALES:
            deck = VAR.variant_deck(35.6528, s)
            line = next(l for l in deck.splitlines() if l.startswith("Xsi vin"))
            for a, b in zip(_widths(line), _widths(CAND.candidate_line(s))):
                self.assertAlmostEqual(a, b, places=4, msg=f"scale {s}")

    def test_default_outdir_is_under_candidates(self):
        for s in SCALES:
            out = Path(CAND.default_outdir(s))
            self.assertEqual(out.parent, Path(CAND.HERE))

    def test_manifest_measurement_blocks_match_cu_sweep(self):
        a = json.loads((REPO / "sim/dr0019-cu-sweep/testbench/tb.json").read_text())
        b = json.loads((REPO / "sim/acq-leg-width-sweep/testbench/tb.json").read_text())
        for key in ("analyses", "measure", "checks", "netlist", "temperatures_c", "corners"):
            self.assertEqual(a[key], b[key], key)
        for key in ("fft_n", "fft_input_hz", "fft_bin", "fft_window", "fft_fs_hz"):
            self.assertEqual(a["evidence"][key], b["evidence"][key], key)


if __name__ == "__main__":
    unittest.main()
