#!/usr/bin/env python3
"""`layout/erc/well_tap_audit.py`'s committed finding must keep describing
the committed geometry (issue #340, DR-0032).

    python3 -m unittest discover -s sim/tests -v

Why this file exists. `spec/decision-records/DR-0032-implant-layers-not-
drawn.md` decides *not* to draw implant layers in `adc_block.gds`, and the
whole of its rationale rests on two measured facts about the drawn layout:
**no n-well tap is drawn in any of the 25 wells**, and the two substrate-tie
guard rings that *are* drawn reach no supply. Those facts are committed in
`layout/erc/well-tap-audit.json`. Without a check, a later layout edit could
make either of them false while the decision record that cites them stayed
on file, unchanged and now wrong -- the same rot `run_erc.py --verify` and
`signoff/run_signoff.py --check` exist to prevent for their own artifacts.

## Two classes, split by what each one needs

| Class | Claim | Runs when |
|---|---|---|
| `WellTapAuditFreshnessTests` | the committed audit still describes the committed GDS bytes, and the tamper check that says so can go red | always (stdlib only) |
| `WellTapAuditMeasurementTests` | every measurement in the audit re-derives from the geometry | pip `klayout` present |

The split matters on this repo's CI path, which installs neither `klt` nor
the pip `klayout` package (`.github/workflows/ci.yml`'s own header says so).
The freshness half is stdlib-only by construction and therefore runs
*everywhere*, including headless CI: it is what makes an edit to
`adc_block.gds` go red here rather than silently orphaning DR-0032. The
measuring half needs `klayout.db` and skips cleanly without it -- the same
skip-don't-fail discipline `test_sar_ctrl_gate_netlist.py` applies to its
`klt`-dependent classes.

Note what the freshness half does *not* claim: identical bytes cannot prove
the measurements were taken correctly, only that they were taken on this
geometry. Correctness is `WellTapAuditMeasurementTests`' job, wherever
`klayout` is installed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT_JSON = REPO / "layout" / "erc" / "well-tap-audit.json"
AUDIT_PY = REPO / "layout" / "erc" / "well_tap_audit.py"
DR = REPO / "spec" / "decision-records" / "DR-0032-implant-layers-not-drawn.md"
ERC_README = REPO / "layout" / "erc" / "README.md"


def load_audit_module():
    """Import `layout/erc/well_tap_audit.py` by path.

    `layout/` is a plain directory, not a package, and the module puts it on
    `sys.path` itself so its own `from klt_env import ...` resolves -- the
    same import-by-path pattern the other layout-facing tests here use.
    """
    spec = importlib.util.spec_from_file_location("well_tap_audit", AUDIT_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules["well_tap_audit"] = module
    spec.loader.exec_module(module)
    return module


class WellTapAuditFreshnessTests(unittest.TestCase):
    """Stdlib only: the committed finding still describes the committed GDS."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        cls.gds = REPO / cls.manifest["layout"]

    def test_gds_hash_matches_the_committed_audit(self) -> None:
        digest = hashlib.sha256(self.gds.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            self.manifest["layout_sha256"],
            f"{self.manifest['layout']} has changed since the well/substrate "
            "tap audit was taken. Re-run `python3 layout/erc/"
            "well_tap_audit.py` and re-read DR-0032 before re-baselining -- "
            "its decision rests on those numbers.",
        )

    def test_audit_agrees_with_the_erc_cases_manifest(self) -> None:
        """The audit and `cases.json` must pin the SAME geometry.

        Two independent records of item-11 evidence that disagree about
        which bytes they describe would let one of them be re-baselined
        without the other.
        """
        cases = json.loads(
            (REPO / "layout" / "erc" / "cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(cases["layout"], self.manifest["layout"])
        self.assertEqual(cases["layout_sha256"], self.manifest["layout_sha256"])

    def test_headline_findings_are_the_ones_dr0032_rests_on(self) -> None:
        """Pin the two numbers DR-0032 cites, by name, in this file.

        Hard-coded deliberately: relaxing either of them has to be a
        conscious edit here, with DR-0032 re-read, rather than a quiet
        `--regen`.
        """
        measured = self.manifest["measured"]
        self.assertEqual(
            measured["well_tap_candidates"],
            0,
            "DR-0032 rests on ADC_BLOCK drawing NO n-well tap. If a tap is "
            "now drawn, that decision needs revisiting, not re-baselining.",
        )
        self.assertEqual(measured["substrate_tie_candidates"], 2)
        self.assertEqual(measured["nwell_islands"], 25)
        self.assertFalse(any(measured["implant_layers_present"].values()))
        for ring in measured["substrate_tie_rings"]:
            self.assertEqual(
                ring["metal1_label_texts"],
                0,
                f"{ring['name']} now carries a Metal1 label; the "
                "`drawn but strapped to nothing` finding has changed.",
            )

    def test_the_freshness_check_can_go_red(self) -> None:
        """Negative control for the check above.

        A green tick on `test_gds_hash_matches_the_committed_audit` is only
        worth something if a changed GDS would fail it -- so tamper with the
        recorded hash in a scratch copy of the manifest and assert
        `--verify` exits `EXIT_MISMATCH` rather than passing.
        """
        module = load_audit_module()
        tampered = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        tampered["layout_sha256"] = "0" * 64
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "well-tap-audit.json"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            original = module.AUDIT
            try:
                module.AUDIT = str(path)
                self.assertEqual(
                    module.main(["--verify"]),
                    module.EXIT_MISMATCH,
                    "--verify accepted a manifest whose recorded hash does "
                    "not match the committed GDS",
                )
            finally:
                module.AUDIT = original

    def test_the_finding_is_reachable_from_where_item_11_is_graded(self) -> None:
        """A future item-11 grader reads `layout/erc/README.md`; the reason
        `erc.missing_tie` stays uncomputed must be findable from there."""
        readme = ERC_README.read_text(encoding="utf-8")
        self.assertIn("well_tap_audit.py", readme)
        self.assertIn("DR-0032", readme)
        self.assertTrue(DR.exists(), f"{DR} is missing")


class WellTapAuditMeasurementTests(unittest.TestCase):
    """Re-derive every committed measurement from the geometry itself."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import klayout.db  # noqa: F401
        except ImportError:
            raise unittest.SkipTest(
                "the pip `klayout` package is not installed -- the geometric "
                "half of the well-tap audit cannot run here (the freshness "
                "half above still does). See docs/environment-setup.md."
            )
        cls.module = load_audit_module()
        cls.manifest = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))

    def test_every_measurement_re_derives(self) -> None:
        measured = self.module.measure(
            str(REPO / self.manifest["layout"]), self.manifest
        )
        diffs = self.module.compare(self.manifest["measured"], measured)
        self.assertEqual(diffs, [], "\n".join(diffs))

    def test_the_measurement_check_can_go_red(self) -> None:
        """Negative control: a seeded well tap must be reported."""
        measured = self.module.measure(
            str(REPO / self.manifest["layout"]), self.manifest
        )
        seeded = json.loads(json.dumps(self.manifest["measured"]))
        seeded["well_tap_candidates"] = 1
        diffs = self.module.compare(seeded, measured)
        self.assertTrue(
            any("well_tap_candidates" in d for d in diffs),
            "compare() did not notice a changed well-tap count",
        )

    def test_audit_exits_zero_end_to_end(self) -> None:
        self.assertEqual(self.module.main([]), self.module.EXIT_OK)


if __name__ == "__main__":
    unittest.main()
