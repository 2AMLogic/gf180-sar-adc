#!/usr/bin/env python3
"""Unit tests for the coherent-sampling FFT post-processor.

    python3 -m unittest discover -s sim/tests -v

`sim/adc-enob-fft/testbench/analyze_fft.py` turns a code sequence into the
SFDR / THD / SNDR / ENOB numbers `spec/testbench-suite-memo.md` reports. A
spectral post-processor is exactly the kind of code that produces a plausible
number from a wrong normalisation and is never caught -- there is no second
measurement to disagree with it. These tests pin it against cases whose answer
is known in closed form:

* an ideal 10-bit quantizer must reproduce the textbook 6.02N + 1.76 dB;
* a synthesised harmonic must land in the bin the folding arithmetic predicts,
  at the amplitude it was injected with;
* the `--sigma-extra-lsb` composition must reproduce quantization itself when
  handed 1/sqrt(12) LSB against an unquantized sine -- the direct check of the
  Parseval normalisation the composition depends on.

No ngspice and no PDK are required, so these run on the PDK-free CI path.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "sim" / "adc-enob-fft" / "testbench" / "analyze_fft.py"

_spec = importlib.util.spec_from_file_location("analyze_fft", SCRIPT)
afft = importlib.util.module_from_spec(_spec)
sys.modules["analyze_fft"] = afft
_spec.loader.exec_module(afft)

N = afft.DEFAULT_N       # 64
BIN = afft.DEFAULT_BIN   # 31
FS_CODES = 1024.0


def sine(n_samples: int, bin_signal: int, amp_lsb: float, phase: float = 0.1):
    return [
        amp_lsb * math.sin(2 * math.pi * bin_signal * t / n_samples + phase)
        for t in range(n_samples)
    ]


def add(*seqs):
    return [sum(v) for v in zip(*seqs)]


def offset(seq, dc):
    return [v + dc for v in seq]


class NormalisationTests(unittest.TestCase):
    def test_ideal_quantizer_reproduces_the_textbook_snr(self):
        """A full-scale sine through an ideal 10-bit quantizer must measure
        6.02*10 + 1.76 = 61.96 dB, i.e. ENOB = 10.00. Any normalisation error
        in the FFT shows up here as a bias of whole dB."""
        x = offset(sine(N, BIN, FS_CODES / 2 - 1), FS_CODES / 2)
        codes = [math.floor(v) for v in x]  # the quantizer, exactly
        out = afft.analyze(codes, BIN)
        self.assertAlmostEqual(out["sndr_db"], 61.96, delta=1.2)
        self.assertAlmostEqual(out["enob_bits"], 10.0, delta=0.2)

    def test_composition_reproduces_quantization_from_first_principles(self):
        """Hand an UNQUANTIZED full-scale sine to the composer with
        sigma = 1/sqrt(12) LSB -- the rms of ideal quantization error -- and it
        must land back on the same 61.96 dB. This is the direct check of the
        Parseval normalisation `--sigma-extra-lsb` rests on."""
        codes = offset(sine(N, BIN, FS_CODES / 2), FS_CODES / 2)
        out = afft.analyze(codes, BIN, sigma_extra_lsb=1.0 / math.sqrt(12.0))
        self.assertAlmostEqual(out["sndr_composed_db"], 61.96, delta=0.05)
        self.assertAlmostEqual(out["enob_composed_bits"], 10.0, delta=0.01)

    def test_composition_only_ever_lowers_sndr(self):
        codes = [
            math.floor(v)
            for v in offset(sine(N, BIN, FS_CODES / 2 - 1), FS_CODES / 2)
        ]
        out = afft.analyze(codes, BIN, sigma_extra_lsb=0.0488)
        self.assertLess(out["sndr_composed_db"], out["sndr_db"])
        self.assertLess(out["enob_composed_bits"], out["enob_bits"])

    def test_amplitude_in_dbfs_is_zero_for_a_full_scale_sine(self):
        codes = offset(sine(N, BIN, FS_CODES / 2), FS_CODES / 2)
        out = afft.analyze(codes, BIN)
        self.assertAlmostEqual(out["amplitude_dbfs"], 0.0, delta=0.01)


class HarmonicFoldingTests(unittest.TestCase):
    def test_fold_matches_hand_arithmetic(self):
        # 2nd harmonic of bin 31 in a 64-point record: 62 -> folds to 2.
        self.assertEqual(afft.fold(2 * 31, 64), 2)
        # 3rd: 93 mod 64 = 29, already below Nyquist.
        self.assertEqual(afft.fold(3 * 31, 64), 29)
        # 4th: 124 mod 64 = 60 -> folds to 4.
        self.assertEqual(afft.fold(4 * 31, 64), 4)

    def test_injected_third_harmonic_is_found_at_its_injected_level(self):
        """-40 dBc of 3rd harmonic must be reported as SFDR = 40 dB in the bin
        the folding arithmetic predicts."""
        fundamental = sine(N, BIN, 400.0)
        h3 = sine(N, afft.fold(3 * BIN, N), 4.0, phase=0.7)
        out = afft.analyze(offset(add(fundamental, h3), 512.0), BIN)
        self.assertEqual(out["sfdr_worst_bin"], afft.fold(3 * BIN, N))
        self.assertAlmostEqual(out["sfdr_db"], 40.0, delta=0.5)
        self.assertAlmostEqual(out["harmonic_dbc"]["3"], -40.0, delta=0.5)

    def test_thd_sums_the_harmonics_it_reports(self):
        x = offset(sine(N, BIN, 400.0), 512.0)
        for h, amp in ((2, 4.0), (3, 4.0)):
            x = add(x, sine(N, afft.fold(h * BIN, N), amp, phase=0.3 * h))
        out = afft.analyze(x, BIN)
        # two equal -40 dBc harmonics -> THD = -37 dB
        self.assertAlmostEqual(out["thd_db"], -37.0, delta=0.5)


class CoherenceGuardTests(unittest.TestCase):
    def test_a_non_coprime_bin_is_rejected_not_silently_analysed(self):
        """window=none is only valid while gcd(M, N) = 1. If the deck's
        parameters ever drift to a non-coprime pair, leakage would be reported
        as distortion -- so the analyser must refuse, not report."""
        codes = offset(sine(N, 32, 400.0), 512.0)
        with self.assertRaises(ValueError):
            afft.analyze(codes, 32)

    def test_a_bin_above_nyquist_is_rejected(self):
        codes = offset(sine(N, BIN, 400.0), 512.0)
        with self.assertRaises(ValueError):
            afft.analyze(codes, N // 2 + 1)

    def test_the_committed_deck_parameters_are_coherent(self):
        self.assertEqual(math.gcd(afft.DEFAULT_BIN, afft.DEFAULT_N), 1)


class LogParsingTests(unittest.TestCase):
    def test_extracts_the_sequence_in_sample_order(self):
        lines = ["Circuit: whatever", "some noise"]
        # deliberately shuffled in the log, as ngspice interleaves output
        for i in (3, 0, 2, 1):
            lines.append(f"m_code_s{i:03d} = {100 + i}.0000000000e+00")
        codes = afft.extract_codes("\n".join(lines), 4)
        self.assertEqual(codes, [100.0, 101.0, 102.0, 103.0])

    def test_a_truncated_log_is_an_error_not_a_short_record(self):
        """A timed-out corner leaves a partial log. Analysing it as if it were
        a complete capture would report a fabricated spectrum."""
        text = "\n".join(f"m_code_s{i:03d} = 1.0e+00" for i in range(N - 1))
        with self.assertRaises(ValueError):
            afft.extract_codes(text, N)


if __name__ == "__main__":
    unittest.main()
