#!/usr/bin/env python3
"""`layout/erc/well_tap_audit.py`'s committed finding must keep describing
the committed geometry (issue #356, DR-0035; originally #340, DR-0032).

    python3 -m unittest discover -s sim/tests -v

Why this file exists. `spec/decision-records/DR-0035-well-taps-and-tie-
straps.md` draws and routes a well tap inside every one of `adc_block.gds`'s
25 `Nwell` islands and straps both substrate-tie guard rings to `vss`, and
the whole of its rationale rests on measured facts about the drawn layout:
**25 well taps in 25 wells**, both implants drawn, and each ring's `Metal1`
closed into ONE annulus carrying a label. Those facts are committed in
`layout/erc/well-tap-audit.json`. Without a check, a later layout edit could
make any of them false while the decision record that cites them stayed
on file, unchanged and now wrong -- the same rot `run_erc.py --verify` and
`signoff/run_signoff.py --check` exist to prevent for their own artifacts.

This file is the direction-reversing half of that guard, and it has now
reversed once: it used to pin `well_tap_candidates == 0` by hand, so that
the day a tap was drawn DR-0032 would be named rather than quietly orphaned.
That is exactly what happened -- #356 drew the taps, this suite went red,
and DR-0032 was superseded instead of re-baselined. The hard-coded numbers
below are the same mechanism pointing the other way: undoing the taps has to
be a conscious edit here, with DR-0035 re-read.

## Two classes, split by what each one needs

| Class | Claim | Runs when |
|---|---|---|
| `WellTapAuditFreshnessTests` | the committed audit still describes the committed GDS bytes, and the tamper check that says so can go red | always (stdlib only) |
| `WellTapAuditMeasurementTests` | every measurement in the audit re-derives from the geometry | pip `klayout` present |

The split matters on this repo's CI path, which installs neither `klt` nor
the pip `klayout` package (`.github/workflows/ci.yml`'s own header says so).
The freshness half is stdlib-only by construction and therefore runs
*everywhere*, including headless CI: it is what makes an edit to
`adc_block.gds` go red here rather than silently orphaning DR-0035. The
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
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT_JSON = REPO / "layout" / "erc" / "well-tap-audit.json"
AUDIT_PY = REPO / "layout" / "erc" / "well_tap_audit.py"
DR = REPO / "spec" / "decision-records" / "DR-0035-well-taps-and-tie-straps.md"
SUPERSEDED_DR = (
    REPO / "spec" / "decision-records" / "DR-0032-implant-layers-not-drawn.md"
)
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
            "well_tap_audit.py` and re-read DR-0035 before re-baselining -- "
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

    def test_headline_findings_are_the_ones_dr0035_rests_on(self) -> None:
        """Pin the numbers DR-0035 cites, by name, in this file.

        Hard-coded deliberately: relaxing any of them has to be a conscious
        edit here, with DR-0035 re-read, rather than a quiet `--regen`.
        """
        measured = self.manifest["measured"]
        self.assertEqual(
            measured["nwell_islands"],
            25,
            "the number of wells changed; the one-tap-per-well claim below "
            "is stated against 25 of them.",
        )
        self.assertEqual(
            measured["well_tap_candidates"],
            measured["nwell_islands"],
            "DR-0035 rests on EVERY Nwell island carrying a tap -- diffusion "
            "inside the well that is not part of a transistor. A count that "
            "is not one per well means a well went untapped, which is the "
            "defect #356 fixed, not a re-baselining matter.",
        )
        self.assertEqual(measured["substrate_tie_candidates"], 2)
        self.assertTrue(
            all(measured["implant_layers_present"].values()),
            "both implants (Pplus 31/0, Nplus 32/0) must be drawn: Nplus is "
            "what the supply spec's `tap_requires` narrows the tap region "
            "to, so an undrawn implant makes that check vacuous again "
            "(DR-0032, superseded).",
        )
        for ring in measured["substrate_tie_rings"]:
            self.assertEqual(
                ring["metal1_bars"],
                1,
                f"{ring['name']}'s Metal1 is no longer ONE merged polygon. "
                "Before #356 it was four bars with 0 touching pairs -- open "
                "at all four corners -- so strapping one bar strapped a "
                "quarter of a ring. Note that `metal1_bar_pairs_touching` "
                "is 0 in BOTH states and cannot tell them apart; the bar "
                "count is what does.",
            )
            self.assertGreater(
                ring["metal1_label_texts"],
                0,
                f"{ring['name']} carries no Metal1 label, so `klt erc` "
                "cannot resolve it into a supply island -- the `drawn but "
                "strapped to nothing` defect #356 fixed.",
            )
            self.assertEqual(
                (ring["contact_min_dim_um"], ring["contact_max_dim_um"]),
                (0.22, 0.22),
                f"{ring['name']}'s contacts are not the exact 0.22 um "
                "squares gf180mcu's CO.1 asks for. The pinned deck's "
                "`contact.width.1` is a MINIMUM-width approximation and "
                "passes long bars, which is why this is pinned here rather "
                "than left to DRC.",
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

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "well-tap-audit.json"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            original = module.AUDIT
            sink = io.StringIO()
            try:
                module.AUDIT = str(path)
                # The expected failure text goes to a sink, not the test
                # log: a real `FAIL:` line printed by a *passing* negative
                # control is indistinguishable from a broken suite when
                # someone skims CI output.
                with redirect_stdout(sink), redirect_stderr(sink):
                    rc = module.main(["--verify"])
                self.assertEqual(
                    rc,
                    module.EXIT_MISMATCH,
                    "--verify accepted a manifest whose recorded hash does "
                    "not match the committed GDS",
                )
                self.assertIn("FAIL", sink.getvalue())
            finally:
                module.AUDIT = original

    def test_the_finding_is_reachable_from_where_item_11_is_graded(self) -> None:
        """A future item-11 grader reads `layout/erc/README.md`; the tie
        evidence and the record that decided it must be findable there."""
        readme = ERC_README.read_text(encoding="utf-8")
        self.assertIn("well_tap_audit.py", readme)
        self.assertIn("DR-0035", readme)
        self.assertTrue(DR.exists(), f"{DR} is missing")

    def test_the_superseded_record_carries_its_back_pointer(self) -> None:
        """DR-0032 is append-only and stays on file; the one edit a ratified
        record ever takes is the `Superseded by` back-pointer, and without it
        a reader lands on a decision this layout has already reversed."""
        superseded = SUPERSEDED_DR.read_text(encoding="utf-8")
        self.assertIn("superseded-by DR-0035", superseded)
        self.assertIn("DR-0035-well-taps-and-tie-straps.md", superseded)


class WellTapAuditMeasurementTests(unittest.TestCase):
    """Re-derive every committed measurement from the geometry itself."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_audit_module()
        # NOT a bare `import klayout.db`: test_layout_centroid_tiling.py
        # installs an empty stub at sys.modules["klayout.db"] so its own
        # module-scope import survives a runner with no `klayout` wheel, and
        # that stub is process-wide. Importing it here succeeds and then
        # explodes on `kdb.Layout()` -- which is how this class first broke
        # CI. `klayout_db()` probes for a real symbol instead.
        if cls.module.klayout_db() is None:
            raise unittest.SkipTest(
                "the pip `klayout` package is not installed (or is the "
                "sibling test's stub) -- the geometric half of the well-tap "
                "audit cannot run here; the freshness half above still "
                "does. See docs/environment-setup.md."
            )
        cls.manifest = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))

    def test_every_measurement_re_derives(self) -> None:
        measured = self.module.measure(
            str(REPO / self.manifest["layout"]), self.manifest
        )
        diffs = self.module.compare(self.manifest["measured"], measured)
        self.assertEqual(diffs, [], "\n".join(diffs))

    def test_the_measurement_check_can_go_red(self) -> None:
        """Negative control: a seeded change to the well-tap count must be
        reported. `+ 1` rather than a literal, so this stays a control on
        `compare()` and not a second copy of the expected value."""
        measured = self.module.measure(
            str(REPO / self.manifest["layout"]), self.manifest
        )
        seeded = json.loads(json.dumps(self.manifest["measured"]))
        seeded["well_tap_candidates"] += 1
        diffs = self.module.compare(seeded, measured)
        self.assertTrue(
            any("well_tap_candidates" in d for d in diffs),
            "compare() did not notice a changed well-tap count",
        )

    def test_audit_exits_zero_end_to_end(self) -> None:
        sink = io.StringIO()
        with redirect_stdout(sink):
            rc = self.module.main([])
        self.assertEqual(rc, self.module.EXIT_OK, sink.getvalue())
        self.assertIn("all measurements match", sink.getvalue())


if __name__ == "__main__":
    unittest.main()
