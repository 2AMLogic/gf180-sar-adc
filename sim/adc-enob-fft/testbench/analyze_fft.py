#!/usr/bin/env python3
"""Coherent-sampling FFT of the code sequence ``tb_adc_enob_fft.spice`` exports.

``sim/adc-enob-fft/testbench/tb.json`` measures one output code per conversion
(``m_code_s000 ... m_code_s063``), because a spectral figure of merit is not a
scalar an ngspice ``meas`` can produce.  This script is the post-processor: it
reads the corner runner's **own raw logs** -- nothing is hand-entered -- and
computes SFDR, THD, SNDR and ENOB per PVT point.  Same pattern, and the same
reason, as ``sim/comparator-offset-gof/testbench/analyze_gof.py``.

Usage::

    python3 analyze_fft.py sim/adc-enob-fft/corners/<record-id>/          # all points
    python3 analyze_fft.py .../corners/<record-id>/tt_27c_3.30v.log       # one point
    python3 analyze_fft.py <dir> --sigma-extra-lsb 0.0488 --markdown

**Standard library only.**  ``sim/harness`` is stdlib-only on purpose (see
``.github/workflows/ci.yml``: there is no dependency install step, so a check
that needs numpy cannot run on the PDK-free CI path).  The transform below is a
40-line iterative radix-2 FFT; at N = 64 the whole suite of corner logs is
transformed in milliseconds, so a dependency would buy nothing and would cost
the ability to re-run this evidence from a bare CPython.

WHY ``window = none`` IS VALID HERE, AND WHY THIS SCRIPT RE-CHECKS IT.
The deck captures M = 31 whole input cycles in N = 64 samples, and
``gcd(31, 64) = 1``.  An integer number of periods leaves no discontinuity at
the record boundary, so there is nothing for a window to repair and the signal
occupies exactly one bin.  That is an arithmetic property of two integers, so
this script asserts it (``--n``/``--bin`` default to the deck's values and
``gcd`` is checked) rather than trusting the manifest's ``fft_window: none``
declaration.  A windowed capture would spread the signal over three bins and
understate SFDR.

WHAT THIS FFT DOES *NOT* CONTAIN.  ngspice injects no device noise into a
transient analysis -- noise enters only through explicit ``trnoise`` /
``trrandom`` sources, and this deck has none.  The non-signal bins therefore
hold **distortion, settling error and quantization**, and no thermal or flicker
noise at all.  Reporting the ENOB straight off this FFT would overstate it by
omitting every noise term in the ratified budget.  ``--sigma-extra-lsb``
composes the separately-measured noise terms back in (comparator input-referred
noise from ``sim/comparator-preamp-noise/``, sampling ``kT/C`` from
``spec/cdac-sizing-memo.md`` Sec 1) and the composed number is the one
``spec/testbench-suite-memo.md`` reports as the ENOB claim.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import re
import sys
from pathlib import Path

#: Defaults mirror ``design/adc-top/gen_adc_top.py``'s FFT_N / FFT_CYCLES.
DEFAULT_N = 64
DEFAULT_BIN = 31
#: Harmonics folded back into the first Nyquist zone and reported individually.
HARMONICS = tuple(range(2, 10))
#: The converter's resolution, for the dBFS reference only.
N_BITS = 10

_SAMPLE_RE = re.compile(r"^m_code_s(\d+)\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)\s*$")


def fft(samples: list[complex]) -> list[complex]:
    """Iterative radix-2 decimation-in-time FFT. ``len(samples)`` must be 2^k.

    Uses the same sign convention and (unnormalised) scaling as
    ``numpy.fft.fft``, so Parseval reads ``sum|X|^2 = N * sum|x|^2`` -- the
    normalisation ``analyze()``'s noise composition depends on.
    """
    n = len(samples)
    if n & (n - 1):
        raise ValueError(f"record length {n} is not a power of two")
    # bit-reversal permutation
    out = list(samples)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    size = 2
    while size <= n:
        step = cmath.exp(-2j * math.pi / size)
        half = size // 2
        for start in range(0, n, size):
            w = 1 + 0j
            for k in range(half):
                a = out[start + k]
                b = out[start + k + half] * w
                out[start + k] = a + b
                out[start + k + half] = a - b
                w *= step
        size <<= 1
    return out


def extract_codes(log_text: str, n: int) -> list[float]:
    """The ``m_code_sNNN`` sequence, in sample order, from one corner log."""
    found: dict[int, float] = {}
    for line in log_text.splitlines():
        m = _SAMPLE_RE.match(line.strip())
        if m:
            found[int(m.group(1))] = float(m.group(2))
    missing = [i for i in range(n) if i not in found]
    if missing:
        raise ValueError(
            f"log is missing {len(missing)} of {n} samples "
            f"(first missing index {missing[0]})"
        )
    return [found[i] for i in range(n)]


def fold(k: int, n: int) -> int:
    """Bin index of frequency ``k * f_s / n`` after aliasing into 0..n/2."""
    k %= n
    return n - k if k > n // 2 else k


def _db(ratio: float) -> float:
    return 10.0 * math.log10(ratio) if ratio > 0 else float("-inf")


def analyze(
    codes: list[float],
    bin_signal: int,
    n_bits: int = N_BITS,
    sigma_extra_lsb: float | None = None,
) -> dict:
    n = len(codes)
    if math.gcd(bin_signal, n) != 1:
        raise ValueError(
            f"gcd({bin_signal}, {n}) = {math.gcd(bin_signal, n)} != 1: the capture "
            "is NOT coherent, so window=none is invalid and this analysis would "
            "report leakage as distortion"
        )
    if bin_signal >= n // 2:
        raise ValueError(f"signal bin {bin_signal} is above Nyquist for N = {n}")

    spectrum = fft([complex(c, 0.0) for c in codes])
    # One-sided power, bins 0..N/2. DC is zeroed: it carries offset, which the
    # ratified Offset row owns and which is not an ENOB term.
    power = [abs(spectrum[k]) ** 2 for k in range(n // 2 + 1)]
    power[0] = 0.0

    p_signal = power[bin_signal]
    if p_signal <= 0.0:
        raise ValueError(f"no signal power in bin {bin_signal}")

    harmonic_bins: dict[int, int] = {}
    for h in HARMONICS:
        b = fold(h * bin_signal, n)
        if b == 0 or b == bin_signal:
            continue  # folded onto DC or onto the fundamental: not resolvable
        harmonic_bins[h] = b

    p_harmonics = sum(power[b] for b in set(harmonic_bins.values()))
    # Everything that is neither DC nor the fundamental: distortion + settling
    # error + quantization. There is no device noise in it (see module docstring).
    p_noise_dist = sum(power) - p_signal

    worst_bin, worst_power = max(
        ((b, power[b]) for b in range(1, n // 2 + 1) if b != bin_signal),
        key=lambda kv: kv[1],
    )

    sfdr_db = _db(p_signal / worst_power) if worst_power > 0 else float("inf")
    thd_db = _db(p_harmonics / p_signal) if p_harmonics > 0 else float("-inf")
    sndr_db = _db(p_signal / p_noise_dist) if p_noise_dist > 0 else float("inf")

    # Amplitude of the fundamental in LSB (single-sided): |X[k]| * 2 / N.
    amp_lsb = 2.0 * abs(spectrum[bin_signal]) / n
    full_scale_lsb = float(2**n_bits)
    # An FFT taken on a less-than-full-scale sine understates SNDR against the
    # ratified row, which is specified at full scale. Report the shortfall so a
    # reader can see whether it matters rather than having to assume.
    amp_dbfs = 20.0 * math.log10(2.0 * amp_lsb / full_scale_lsb)

    out = {
        "n_samples": n,
        "signal_bin": int(bin_signal),
        "coherent": True,
        "window": "none",
        "code_min": min(codes),
        "code_max": max(codes),
        "amplitude_lsb": amp_lsb,
        "amplitude_dbfs": amp_dbfs,
        "sfdr_db": sfdr_db,
        "sfdr_worst_bin": int(worst_bin),
        "thd_db": thd_db,
        "sndr_db": sndr_db,
        "enob_bits": (sndr_db - 1.76) / 6.02,
        "harmonic_bins": {str(h): int(b) for h, b in harmonic_bins.items()},
        "harmonic_dbc": {
            str(h): _db(power[b] / p_signal) for h, b in harmonic_bins.items()
        },
    }

    if sigma_extra_lsb is not None:
        # Compose the separately-measured noise terms back in. Powers add, so
        # the only care needed is putting the extra rms into the SAME
        # normalisation the one-sided |FFT|^2 array above uses.
        #
        # Parseval for this transform: sum_k |X_full[k]|^2 = N * sum_n x[n]^2.
        # A signal of rms sigma therefore carries N^2 * sigma^2 of
        # full-spectrum power, of which half lands in the one-sided (0..N/2)
        # array `power` holds. Self-check: sigma = 1/sqrt(12) LSB (ideal
        # quantization) against a 512 LSB-amplitude sine must reproduce
        # 61.96 dB = the textbook 10-bit SNR; sim/tests/test_analyze_fft.py
        # asserts exactly that.
        p_extra = (sigma_extra_lsb**2) * (n**2) / 2.0
        sndr_total = _db(p_signal / (p_noise_dist + p_extra))
        out.update(
            {
                "sigma_extra_lsb": sigma_extra_lsb,
                "sndr_composed_db": sndr_total,
                "enob_composed_bits": (sndr_total - 1.76) / 6.02,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "target",
        type=Path,
        help="a corners/<record-id>/ directory, or a single <corner-id>.log",
    )
    p.add_argument("--n", type=int, default=DEFAULT_N)
    p.add_argument("--bin", dest="bin_signal", type=int, default=DEFAULT_BIN)
    p.add_argument(
        "--sigma-extra-lsb",
        type=float,
        default=None,
        help=(
            "rms of the noise terms this transient cannot contain (comparator "
            "input-referred noise + sampling kT/C), in LSB; composes them into "
            "a total SNDR/ENOB"
        ),
    )
    p.add_argument("--out-json", type=Path, default=None)
    p.add_argument("--markdown", action="store_true", help="emit a summary table")
    args = p.parse_args(argv)

    logs = (
        sorted(args.target.glob("*.log")) if args.target.is_dir() else [args.target]
    )
    if not logs:
        print(f"error: no .log files under {args.target}", file=sys.stderr)
        return 1

    results: dict[str, dict] = {}
    failures: list[str] = []
    for log in logs:
        try:
            results[log.stem] = analyze(
                extract_codes(log.read_text(), args.n),
                args.bin_signal,
                sigma_extra_lsb=args.sigma_extra_lsb,
            )
        except ValueError as exc:
            failures.append(f"{log.stem}: {exc}")

    if not results:
        for f in failures:
            print(f"error: {f}", file=sys.stderr)
        return 1

    key = "enob_composed_bits" if args.sigma_extra_lsb is not None else "enob_bits"
    worst_enob = min(results.items(), key=lambda kv: kv[1][key])
    worst_sfdr = min(results.items(), key=lambda kv: kv[1]["sfdr_db"])
    summary = {
        "n_corners": len(results),
        "worst_enob_corner": worst_enob[0],
        "worst_enob_bits": worst_enob[1][key],
        "worst_sfdr_corner": worst_sfdr[0],
        "worst_sfdr_db": worst_sfdr[1]["sfdr_db"],
        "per_corner": results,
        "unreadable": failures,
    }

    if args.markdown:
        cols = ["sndr_db", "enob_bits", "sfdr_db", "thd_db", "amplitude_dbfs"]
        if args.sigma_extra_lsb is not None:
            cols += ["sndr_composed_db", "enob_composed_bits"]
        print("| corner-id | " + " | ".join(cols) + " |")
        print("|---" * (len(cols) + 1) + "|")
        for corner_id in sorted(results):
            row = results[corner_id]
            print(
                f"| `{corner_id}` | "
                + " | ".join(f"{row[c]:.4g}" for c in cols)
                + " |"
            )
        for f in failures:
            print(f"| `{f.split(':')[0]}` | (unreadable: {f.split(': ', 1)[1]}) |")
    else:
        print(json.dumps(summary, indent=2))

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
