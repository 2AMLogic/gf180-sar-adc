#!/usr/bin/env python3
"""Controls for `sim/tools/check_characterization_summary.py` (issue #437).

    python3 -m unittest discover -s sim/tests -t sim/tests

Every test builds a throwaway repo with a tiny summary table, a few record
files and an exception file, then asserts the checker's verdict. Each
negative control is paired with a passing fix where the issue asks for one,
because a guard that cannot go red (or cannot go green again) is not a guard.
Stdlib only.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim" / "tools"))
import check_characterization_summary as C  # noqa: E402

HEADER = (
    "| Spec row (README target) | Target | Latest verified value | Verdict | Source (dated) |\n"
    "|---|---|---|---|---|\n"
)

# Campaign `exp`: extracted chain E1 <- E2 <- E3 (multihop), schematic S1, S2
# (S2 is unlinked to S1), and a candidate-design schematic record CAND.
E1 = "20260801-000000-aaaaaaa"
E2 = "20260802-000000-bbbbbbb"
E3 = "20260803-000000-ccccccc"
S1 = "20260801-120000-ddddddd"
S2 = "20260805-000000-eeeeeee"


def rec(prov: str, supersedes: str = "(none)") -> str:
    return (
        "# Record\n\n"
        f"- **Netlist provenance**: {prov} (deck)\n"
        f"- **Supersedes**: {supersedes}\n"
        "- **Result**: x\n"
    )


def link(campaign: str, rid: str, role: str | None, mode: str | None, dest: str | None = None) -> str:
    d = dest if dest is not None else f"{campaign}/records/{rid}.md"
    s = f"[`sim/{campaign}/records/{rid}.md`]({d})"
    if role is not None:
        s += f" <!-- evidence role={role} mode={mode} -->"
    return s + " (note)"


def row(label: str, source: str, value: str = "v") -> str:
    return f"| {label} | t | {value} | **PASS** | {source} |\n"


def summary(*rows: str, heading: str = "## Per-spec-row status", header: str = HEADER) -> str:
    return "# Doc\n\n" + heading + "\n\n" + header + "".join(rows) + "\n## Next\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.write_rec("exp", E1, rec("extracted"))
        self.write_rec("exp", E2, rec("extracted", E1))
        self.write_rec("exp", E3, rec("**extracted**", f"`{E2}` — re-take"))
        self.write_rec("exp", S1, rec("schematic"))
        self.write_rec("exp", S2, rec("schematic"))
        self.exc: list[dict] = []

    def write_rec(self, campaign: str, rid: str, text: str) -> None:
        p = self.repo / "sim" / campaign / "records" / f"{rid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def path(self, campaign: str, rid: str) -> str:
        return f"sim/{campaign}/records/{rid}.md"

    def add_exc(self, row_label, mode, cited, newer, reason="not comparable: different scope"):
        self.exc.append({"row": row_label, "mode": mode, "cited": cited, "newer": newer, "reason": reason})

    def problems(self, text: str, exc=None) -> list[str]:
        data = {"exceptions": self.exc} if exc is None else exc
        return C.check(self.repo, text, data)

    def assertClean(self, text: str, exc=None):
        p = self.problems(text, exc)
        self.assertEqual(p, [], "\n".join(p))

    def assertFails(self, text: str, *needles: str, exc=None) -> list[str]:
        p = self.problems(text, exc)
        self.assertTrue(p, "expected failure, checker returned green")
        joined = "\n".join(p)
        for n in needles:
            self.assertIn(n, joined)
        return p


class FreshnessTests(Fixture):
    def test_stale_governing_extracted_fails_naming_both_then_fix_passes(self):
        # E1 is two hops behind E3: the head of the chain is reported.
        stale = summary(row("ENOB", link("exp", E1, "governing", "extracted") + "; "
                                    + link("exp", S2, "current", "schematic")))
        p = self.assertFails(stale, "STALE", self.path("exp", E1), self.path("exp", E3))
        self.assertTrue(any(f"{E1} -> {E2} -> {E3}" in x for x in p), p)
        fixed = summary(row("ENOB", link("exp", E3, "governing", "extracted") + "; "
                                    + link("exp", E1, "historical", "extracted") + "; "
                                    + link("exp", S2, "current", "schematic")))
        self.assertClean(fixed)

    def test_historical_older_records_pass(self):
        text = summary(row("R", link("exp", E3, "governing", "extracted") + "; "
                                + link("exp", E1, "historical", "extracted") + "; "
                                + link("exp", E2, "historical", "extracted") + "; "
                                + link("exp", S1, "historical", "schematic") + "; "
                                + link("exp", S2, "current", "schematic")))
        self.assertClean(text)

    def test_modes_are_checked_independently(self):
        # A newer *extracted* record never stales a schematic citation, and
        # vice versa: S2 (schematic, newest of its mode) passes even though
        # E3 is newer than nothing schematic; E3 passes despite S2 being newer.
        self.write_rec("exp", "20260901-000000-fffffff", rec("extracted", E3))
        text = summary(row("R", link("exp", S2, "current", "schematic") + "; "
                                + link("exp", "20260901-000000-fffffff", "governing", "extracted")))
        self.assertClean(text)
        # ...but a newer same-mode schematic record is caught for the schematic citation.
        self.write_rec("exp", "20260902-000000-1111111", rec("schematic"))
        self.assertFails(text, "UNCLASSIFIED", "20260902-000000-1111111")

    def test_cross_mode_successor_does_not_stale(self):
        # An extracted record that declares Supersedes on a schematic record
        # (the sim/README "pointer, not overwrite" convention) does not make
        # the schematic citation stale.
        self.write_rec("exp", "20260806-000000-2222222", rec("extracted", S2))
        text = summary(row("R", link("exp", S2, "current", "schematic") + "; "
                                + link("exp", E3, "historical", "extracted")))
        self.assertClean(text)

    def test_newer_unlinked_candidate_requires_exact_exception(self):
        text = summary(row("R", link("exp", S1, "current", "schematic")),
                       row("Other", link("exp", E3, "governing", "extracted")))
        self.assertFails(text, "UNCLASSIFIED", self.path("exp", S2), self.path("exp", S1))
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2))
        self.assertClean(text)

    def test_exception_cannot_authorize_other_row_mode_citation_or_candidate(self):
        text = summary(row("R", link("exp", S1, "current", "schematic")),
                       row("Other", link("exp", S1, "current", "schematic")))
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2))
        # The same citation in another row is still unclassified.
        p = self.assertFails(text, "[Other]", "UNCLASSIFIED")
        self.assertFalse(any("[R]" in x for x in p), p)
        # Wrong mode for the same tuple: unused + the original still fails.
        self.exc = []
        self.add_exc("R", "extracted", self.path("exp", S1), self.path("exp", S2))
        self.assertFails(summary(row("R", link("exp", S1, "current", "schematic"))),
                         "unused exception", "UNCLASSIFIED")
        # Exception on a different citation does not cover this one.
        self.exc = []
        self.add_exc("R", "extracted", self.path("exp", E1), self.path("exp", E3))
        self.assertFails(summary(row("R", link("exp", S1, "current", "schematic"))),
                         "unused exception", "UNCLASSIFIED")
        # A subsequent newer candidate is not covered by the existing entry.
        self.exc = []
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2))
        one = summary(row("R", link("exp", S1, "current", "schematic")))
        self.assertClean(one)
        self.write_rec("exp", "20260910-000000-3333333", rec("schematic"))
        self.assertFails(one, "UNCLASSIFIED", "20260910-000000-3333333")

    def test_exception_does_not_cover_a_successor_chain_moving_on(self):
        text = summary(row("R", link("exp", E2, "governing", "extracted")))
        self.add_exc("R", "extracted", self.path("exp", E2), self.path("exp", E3))
        self.assertClean(text)
        self.write_rec("exp", "20260920-000000-4444444", rec("extracted", E3))
        self.assertFails(text, "STALE", "20260920-000000-4444444", "unused exception")

    def test_newer_record_linked_in_same_row_is_classified_by_its_marker(self):
        text = summary(row("Pair", link("exp", S1, "governing", "schematic") + " / "
                                   + link("exp", S2, "governing", "schematic")))
        self.assertClean(text)

    def test_superseded_newer_candidate_reports_only_chain_head(self):
        # S2 superseded by S3 (schematic): only S3 is the candidate for S1.
        s3 = "20260807-000000-5555555"
        self.write_rec("exp", s3, rec("schematic", S2))
        p = self.assertFails(summary(row("R", link("exp", S1, "current", "schematic"))), s3)
        self.assertFalse(any(S2 in x for x in p), p)


class ExceptionFileTests(Fixture):
    TEXT = summary(row("R", link("exp", S1, "current", "schematic")))

    def test_empty_reason_fails(self):
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2), reason="  ")
        self.assertFails(self.TEXT, "empty reason")

    def test_duplicate_fails(self):
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2))
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2), reason="again")
        self.assertFails(self.TEXT, "duplicate exception")

    def test_unused_fails(self):
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", S2))
        self.add_exc("R", "extracted", self.path("exp", E1), self.path("exp", E2))
        self.assertFails(self.TEXT, "unused exception")

    def test_missing_path_fails(self):
        self.add_exc("R", "schematic", self.path("exp", S1), self.path("exp", "20261231-000000-9999999"))
        self.assertFails(self.TEXT, "does not exist")

    def test_wildcard_and_unknown_row_and_bad_keys_fail(self):
        self.add_exc("R", "schematic", self.path("exp", S1), "sim/exp/records/*.md")
        self.assertFails(self.TEXT, "wildcard")
        self.exc = []
        self.add_exc("No such row", "schematic", self.path("exp", S1), self.path("exp", S2))
        self.assertFails(self.TEXT, "not a spec-row label")
        self.assertFails(self.TEXT, "top level", exc={"allow": []})
        self.assertFails(self.TEXT, "exactly the keys",
                         exc={"exceptions": [{"row": "R", "campaign": "exp", "reason": "all old"}]})


class MarkdownTests(Fixture):
    GOOD = link("exp", E3, "governing", "extracted")

    def test_missing_heading_fails(self):
        self.assertFails(summary(row("R", self.GOOD), heading="## Per spec row"), "not found")

    def test_duplicate_heading_fails(self):
        text = summary(row("R", self.GOOD)) + "\n## Per-spec-row status\n\n" + HEADER + row("Q", self.GOOD)
        self.assertFails(text, "more than once")

    def test_duplicate_or_wrong_column_header_fails(self):
        dup = HEADER.replace("| Target |", "| Verdict |")
        self.assertFails(summary(row("R", self.GOOD), header=dup), "duplicate column header")
        wrong = HEADER.replace("Source (dated)", "Source")
        self.assertFails(summary(row("R", self.GOOD), header=wrong), "expected")

    def test_zero_rows_fails(self):
        self.assertFails(summary(), "zero rows")

    def test_malformed_row_width_fails(self):
        self.assertFails(summary(row("R", self.GOOD), "| short | row |\n"), "row has 2 cells")
        # An unescaped pipe in prose silently adds cells (the Supply-row defect).
        self.assertFails(summary(row("R", self.GOOD, value="max |d| 2e-5")), "row has 7 cells")

    def test_escaped_pipe_passes(self):
        self.assertClean(summary(row("R", self.GOOD, value=r"worst \|INL\| 0.5 and `a \| b`")))

    def test_inline_code_pipe_is_rejected(self):
        self.assertFails(summary(row("R", self.GOOD, value="code `a | b` here")), "inside inline code")

    def test_split_table_fails(self):
        text = summary(row("R", self.GOOD)).replace("\n## Next", "\n" + row("Late", self.GOOD) + "\n## Next")
        self.assertFails(text, "table-like line")

    def test_multiple_links_in_a_cell_each_need_a_marker(self):
        two = self.GOOD + "; " + link("exp", E1, None, None) + "; [`DR`](../spec/dr.md)"
        self.assertFails(summary(row("R", two)), "missing", self.path("exp", E1))
        two_ok = self.GOOD + "; " + link("exp", E1, "historical", "extracted") + "; [`DR`](../spec/dr.md)"
        self.assertClean(summary(row("R", two_ok)))

    def test_row_without_record_links_is_valid(self):
        self.assertClean(summary(row("R", self.GOOD), row("Area", "[`DR-0024`](../spec/DR-0024.md); `layout/x`")))

    def test_relative_destinations_must_be_canonical(self):
        for dest in (f"./exp/records/{E3}.md", f"../sim/exp/records/{E3}.md",
                     f"exp/records/{E3}.md#result", f"exp/../exp/records/{E3}.md"):
            with self.subTest(dest=dest):
                bad = link("exp", E3, "governing", "extracted", dest=dest)
                self.assertFails(summary(row("R", bad)), "non-canonical destination")
        url = link("exp", E3, "governing", "extracted",
                   dest=f"https://github.com/o/r/blob/main/sim/exp/records/{E3}.md")
        self.assertFails(summary(row("R", url)), "unsupported destination")

    def test_missing_invalid_and_malformed_markers_fail(self):
        self.assertFails(summary(row("R", link("exp", E3, None, None))), "missing")
        self.assertFails(summary(row("R", link("exp", E3, "primary", "extracted"))), "unknown role")
        self.assertFails(summary(row("R", link("exp", E3, "governing", "layout"))), "unknown mode")
        bad = f"[`x`](exp/records/{E3}.md) <!-- evidence mode=extracted role=governing -->"
        self.assertFails(summary(row("R", bad)), "malformed evidence marker")

    def test_marker_mode_must_match_record_provenance(self):
        self.assertFails(summary(row("R", link("exp", E3, "governing", "schematic"))),
                         "Netlist provenance says extracted")

    def test_orphan_duplicate_and_contradictory_markers_fail(self):
        orphan = self.GOOD + " and <!-- evidence role=current mode=schematic -->"
        self.assertFails(summary(row("R", orphan)), "orphan")
        dup = self.GOOD.replace(" (note)", " <!-- evidence role=historical mode=extracted --> (note)")
        self.assertFails(summary(row("R", dup)), "orphan or duplicate")
        contra = self.GOOD + "; " + link("exp", E3, "historical", "extracted")
        self.assertFails(summary(row("R", contra)), "contradictory")

    def test_unparseable_links_fail(self):
        self.assertFails(summary(row("R", self.GOOD + f"; [x][ref]")), "unparseable")
        self.assertFails(summary(row("R", self.GOOD + f"; [a [b]](exp/records/{E1}.md)")), "unparseable")

    def test_missing_record_and_malformed_name_fail(self):
        self.assertFails(summary(row("R", link("exp", "20261231-000000-9999999", "governing", "extracted"))),
                         "does not exist")
        bad = "[`x`](exp/records/notes.md) <!-- evidence role=historical mode=other -->"
        self.assertFails(summary(row("R", bad)), "malformed record filename")
        self.write_rec("exp", "README", "x")
        self.assertFails(summary(row("R", self.GOOD)), "malformed record filename")

    def test_duplicate_row_label_fails(self):
        self.assertFails(summary(row("R", self.GOOD), row("R", self.GOOD)), "duplicate spec-row label")


class GraphTests(Fixture):
    def test_dangling_supersedes_fails(self):
        self.write_rec("exp", "20260810-000000-6666666", rec("schematic", "20260101-000000-0000000"))
        self.assertFails(summary(row("R", link("exp", E3, "governing", "extracted"))), "dangling")

    def test_no_cross_campaign_guessing(self):
        # E1 exists only in `exp`; a record in `other` naming it is dangling,
        # not silently resolved across campaigns.
        o1 = "20260801-000000-7777777"
        self.write_rec("other", o1, rec("schematic"))
        self.write_rec("other", "20260802-000000-8888888", rec("schematic", E1))
        self.assertFails(summary(row("R", link("other", o1, "governing", "schematic"))), "dangling")

    def test_ambiguous_id_fails(self):
        self.write_rec("exp", "20260801-000000-abcdef0", rec("schematic"))
        self.write_rec("exp", "20260811-000000-1212121", rec("schematic", "20260801-000000"))
        self.assertFails(summary(row("R", link("exp", E3, "governing", "extracted"))), "ambiguous")

    def test_unparseable_supersedes_value_fails(self):
        self.write_rec("exp", "20260812-000000-1313131", rec("schematic", "the previous one"))
        self.assertFails(summary(row("R", link("exp", E3, "governing", "extracted"))), "unparseable Supersedes")

    def test_cycle_fails(self):
        a, b = "20260813-000000-1414141", "20260814-000000-1515151"
        self.write_rec("exp", a, rec("schematic", b))
        self.write_rec("exp", b, rec("schematic", a))
        self.assertFails(summary(row("R", link("exp", E3, "governing", "extracted"))), "cycle")

    def test_multihop_chain_reports_head(self):
        p = self.assertFails(summary(row("R", link("exp", E1, "current", "extracted"))), "STALE")
        self.assertEqual(len([x for x in p if "STALE" in x]), 1, p)
        self.assertIn(self.path("exp", E3), p[0])

    def test_supersedes_value_forms(self):
        self.assertEqual(C.parse_supersedes_value("(none — first record)"), [])
        self.assertEqual(C.parse_supersedes_value(E1), [E1])
        self.assertEqual(C.parse_supersedes_value(f"`{E1}` — **for its gain result"), [E1])
        self.assertEqual(C.parse_supersedes_value(f"{E1}, {E2}"), [E1, E2])
        self.assertIsNone(C.parse_supersedes_value("see the other record"))


class CommittedStateTests(unittest.TestCase):
    def test_committed_summary_is_clean(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = C.main(["--repo", str(REPO)])
        self.assertEqual(rc, 0, buf.getvalue())

    def test_committed_summary_actually_has_citations(self):
        text = (REPO / C.SUMMARY_REL).read_text(encoding="utf-8")
        cites = C.parse_citations(C.parse_table(text), [])
        self.assertGreater(len(cites), 20)
        self.assertTrue(any(c.role == "governing" for c in cites))

    def test_exception_file_is_valid_json_with_reasons(self):
        data = json.loads((REPO / C.EXCEPTIONS_REL).read_text(encoding="utf-8"))
        for e in data["exceptions"]:
            self.assertTrue(e["reason"].strip())


if __name__ == "__main__":
    unittest.main()
