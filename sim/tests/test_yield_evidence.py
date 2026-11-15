#!/usr/bin/env python3
"""Byte-equality regression test for the four `yield-evidence*/` generators.

Each `build_yield_evidence.py` emits a `klt yield` sample set and spec window
as committed JSON documents that downstream records and reviewers cite. The
generators are regenerable derived views, but their *bytes* are the contract:
before this test existed, nothing re-ran them to confirm the committed JSON
still matched what the script produces.

So this test re-runs all four into a temp directory (by rebinding each
script's `HERE` output anchor; its input paths were resolved at import time
and still point at the real committed `runs/`/`corners/` evidence) and
asserts the emitted bytes equal the committed artifacts exactly. A change to
the shared `sim/tools/yield_evidence.py` emitter that would move any bundle's
bytes therefore fails here -- which is the point: fix the emitter, do not
re-baseline the artifact.

It also guards the de-duplication itself: the 3-sigma target yield must come
from the shared module, not be re-hardcoded into a caller.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import yield_evidence as ye  # noqa: E402
from _loadmod import load_module  # noqa: E402

SIM = Path(__file__).resolve().parents[1]

#: (module name, bundle directory relative to `sim/`)
BUNDLES = [
    ("build_yield_evidence_cdac_172", "mc-cdac-mismatch/yield-evidence"),
    ("build_yield_evidence_cdac_177", "mc-cdac-mismatch/yield-evidence-177"),
    ("build_yield_evidence_cdac_656", "mc-cdac-mismatch/yield-evidence-656"),
    ("build_yield_evidence_cmp_172", "comparator-offset-mc/yield-evidence"),
]

ARTIFACTS = ("mc-samples.json", "spec-limits.json")


def run_into(mod_name: str, bundle: Path, out_dir: Path) -> None:
    """Load one generator and run it with its output anchored at `out_dir`."""
    module = load_module(mod_name, bundle / "build_yield_evidence.py")
    module.HERE = out_dir
    with redirect_stdout(io.StringIO()):
        module.main()


class CommittedArtifactsReproduce(unittest.TestCase):
    """Every bundle's committed JSON is exactly what its script emits today."""

    def test_all_four_bundles_reproduce_byte_for_byte(self):
        for mod_name, rel in BUNDLES:
            with self.subTest(bundle=rel):
                bundle = SIM / rel
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp)
                    run_into(mod_name, bundle, out)
                    for artifact in ARTIFACTS:
                        emitted = (out / artifact).read_bytes()
                        committed = (bundle / artifact).read_bytes()
                        self.assertEqual(
                            emitted, committed,
                            f"{rel}/{artifact} would change: the shared emitter is "
                            f"wrong for this bundle -- fix the emitter, do not "
                            f"re-baseline the committed artifact",
                        )

    def test_every_bundle_reports_input_hashes(self):
        """Provenance travels with every number (CLAUDE.md), not just -656."""
        for mod_name, rel in BUNDLES:
            with self.subTest(bundle=rel):
                with tempfile.TemporaryDirectory() as tmp:
                    module = load_module(
                        mod_name + "_stdout", SIM / rel / "build_yield_evidence.py")
                    module.HERE = Path(tmp)
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        module.main()
                    out = buf.getvalue()
                self.assertIn("input sha256 ", out)
                # A hex digest, not a placeholder.
                digests = [ln.split("input sha256 ")[1].split()[0]
                           for ln in out.splitlines() if "input sha256 " in ln]
                self.assertTrue(digests)
                for d in digests:
                    self.assertEqual(len(d), 64, f"not a sha256 digest: {d!r}")
                    int(d, 16)  # raises if not hex


class SharedConstantsAreNotRehardcoded(unittest.TestCase):
    """The de-duplication itself, guarded."""

    def test_target_yield_literal_appears_in_no_caller(self):
        literal = repr(ye.TARGET_YIELD_3SIGMA)
        for _mod_name, rel in BUNDLES:
            with self.subTest(bundle=rel):
                src = (SIM / rel / "build_yield_evidence.py").read_text()
                self.assertNotIn(
                    literal, src,
                    f"{rel}/build_yield_evidence.py re-hardcodes the 3-sigma "
                    f"target yield; use yield_evidence.TARGET_YIELD_3SIGMA",
                )

    def test_ci_halfwidth_literal_appears_in_no_caller(self):
        for _mod_name, rel in BUNDLES:
            with self.subTest(bundle=rel):
                src = (SIM / rel / "build_yield_evidence.py").read_text()
                self.assertNotIn(
                    '"target_ci_halfwidth"', src,
                    f"{rel}/build_yield_evidence.py hand-writes the "
                    f"target_ci_halfwidth schema key; emit it via write_bundle",
                )


class EmitterKeyOrder(unittest.TestCase):
    """`json.dumps` preserves insertion order, so key order is a contract."""

    def test_measurement_key_order_and_optional_blocks(self):
        bare = ye.measurement("m", "LSB", [1.0])
        self.assertEqual(list(bare), ["name", "unit", "samples", "errored"])

        full = ye.measurement(
            "m", "LSB", [1.0],
            negative_control=ye.negative_control([2.0], "desc"),
            analytic_cross_check=ye.analytic_cross_check(0.5),
        )
        self.assertEqual(
            list(full),
            ["name", "unit", "samples", "errored", "negative_control",
             "analytic_cross_check"],
        )
        self.assertEqual(list(full["negative_control"]),
                         ["samples", "errored", "description"])
        self.assertEqual(list(full["analytic_cross_check"]),
                         ["kind", "sigma", "mean"])

        corners = ye.measurement(
            "m", "LSB", [1.0],
            source_corners=["tt_27c_3.30v"],
            analytic_cross_check=ye.analytic_cross_check(0.5),
        )
        self.assertEqual(
            list(corners),
            ["name", "unit", "samples", "errored", "source_corners",
             "analytic_cross_check"],
        )

    def test_limit_source_is_emitted_first_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            probe = out / "probe.txt"
            probe.write_bytes(b"x")

            with redirect_stdout(io.StringIO()):
                ye.write_bundle(out, [], {}, [probe], rel_to=out)
            import json
            self.assertEqual(
                list(json.loads((out / "spec-limits.json").read_text())),
                ["target_ci_halfwidth", "measurements"],
            )

            with redirect_stdout(io.StringIO()):
                ye.write_bundle(out, [], {}, [probe], rel_to=out,
                                limit_source="README.md row")
            self.assertEqual(
                list(json.loads((out / "spec-limits.json").read_text())),
                ["limit_source", "target_ci_halfwidth", "measurements"],
            )

    def test_symmetric_limit_is_two_sided(self):
        self.assertEqual(
            ye.symmetric_limit(1.0),
            {"min": -1.0, "max": 1.0, "target_yield": ye.TARGET_YIELD_3SIGMA},
        )


class NegativeControlDescription(unittest.TestCase):
    """One template; the per-claim wording stays caller data."""

    SUMMARY = {"sigma_u_pct": 1.5, "n_trials": 2000, "seed": 99109901}

    def test_float_nominal_is_rendered_to_six_decimals(self):
        desc = ye.negative_control_description(
            self.SUMMARY, "rec", basis="the as-built value", nominal_pct=0.5,
            suffix=".",
        )
        self.assertIn("(sigma_u=1.500000% vs 0.500000% nominal)", desc)
        self.assertIn("3x the as-built value", desc)
        self.assertTrue(desc.endswith("summary_n2000_3xsigma.json."), desc)

    def test_string_nominal_is_used_verbatim(self):
        desc = ye.negative_control_description(
            self.SUMMARY, "rec",
            basis="the chosen design's calibrated value", nominal_pct="0.5000",
        )
        self.assertIn("vs 0.5000% nominal", desc)
        self.assertTrue(desc.endswith(".json for full provenance."), desc)

    def test_n_and_seed_come_from_the_summary(self):
        desc = ye.negative_control_description(
            self.SUMMARY, "rec", basis="b", nominal_pct="0",
        )
        self.assertIn("N=2000, seed=99109901", desc)


if __name__ == "__main__":
    unittest.main()
