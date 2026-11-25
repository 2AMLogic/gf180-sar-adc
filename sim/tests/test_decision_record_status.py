#!/usr/bin/env python3
"""Unit tests for sim/tools/generate_decision_record_status.py (issue #438).

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import generate_decision_record_status as g  # noqa: E402

D = dt.date


def record(num="0001", title="Thing", status="proposed", date="2026-01-01",
           supersedes="none", superseded_by="none", spec="- `x.md` — y\n",
           drop=(), dup=()):
    fields = {"Status": status, "Date": date, "Supersedes": supersedes,
              "Superseded by": superseded_by}
    head = [f"# DR-{num}: {title}", ""]
    for k, v in fields.items():
        if k in drop:
            continue
        head.append(f"- **{k}**: {v}")
        if k in dup:
            head.append(f"- **{k}**: {v}")
    text = "\n".join(head) + "\n\n## Context\n\nblah\n\n"
    if spec is not None:
        text += "## Spec lines affected\n\n" + spec
    return text


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def put(self, text, num="0001"):
        (self.dir / f"DR-{num}-x.md").write_text(text, encoding="utf-8")

    def parse(self, as_of=D(2026, 10, 9)):
        return g.load_records(self.dir, as_of)

    def assertRejects(self, text, *needles):
        self.put(text)
        with self.assertRaises(g.RecordError) as cm:
            self.parse()
        for n in needles:
            self.assertIn(n, str(cm.exception))


class ParseTests(Base):
    def test_multiline_values(self):
        self.put(record(
            status="superseded-by DR-0002 (was: ratified —\n  sign-off)",
            superseded_by="[DR-0002](a.md) (#3) — wrapped\n  second line\n  third",
            supersedes="DR-0000 and\n  more",
            spec="- first entry\n  continued\n- second\n"))
        (r,) = self.parse()
        self.assertEqual(r.status_token, "superseded-by")
        self.assertEqual(r.status_text,
                         "superseded-by DR-0002 (was: ratified — sign-off)")
        self.assertEqual(r.superseded_by,
                         "[DR-0002](a.md) (#3) — wrapped second line third")
        self.assertEqual(r.supersedes, "DR-0000 and more")
        self.assertEqual(r.spec_lines, ("first entry continued", "second"))

    def test_extra_fields_ignored(self):
        self.put(record().replace("- **Date**", "- **Related**: #1\n- **Date**"))
        self.assertEqual(len(self.parse()), 1)

    def test_leap_day(self):
        self.put(record(date="2028-02-29"))
        (r,) = self.parse(D(2028, 3, 1))
        self.assertEqual(r.date, D(2028, 2, 29))
        self.assertRejects(record(date="2026-02-29"), "Date", "DR-0001-x.md")

    def test_invalid_date_forms(self):
        self.assertRejects(record(date="2026-1-5"), "Date")

    def test_future_date(self):
        self.assertRejects(record(date="2026-10-10"), "Date", "after the as-of")

    def test_same_day_ok(self):
        self.put(record(date="2026-10-09"))
        self.assertEqual(self.parse()[0].date, D(2026, 10, 9))

    def test_missing_fields(self):
        for f in g.REQUIRED_FIELDS:
            with self.subTest(field=f):
                self.assertRejects(record(drop=(f,)), f, "missing")

    def test_duplicate_fields(self):
        for f in g.REQUIRED_FIELDS:
            with self.subTest(field=f):
                self.assertRejects(record(dup=(f,)), f, "duplicate")

    def test_unknown_status(self):
        self.assertRejects(record(status="draft — maybe"), "Status", "draft")

    def test_malformed_title(self):
        for bad in ("# DR-1: short", "# DR-0001 no colon", "# Something"):
            with self.subTest(title=bad):
                text = record().replace("# DR-0001: Thing", bad)
                self.assertRejects(text, "title")

    def test_missing_spec_section(self):
        self.assertRejects(record(spec=None), "Spec lines affected", "missing")

    def test_empty_spec_section(self):
        self.assertRejects(record(spec="\n\n"), "Spec lines affected", "empty")
        self.assertRejects(record(spec="\n## Next\n- x\n"),
                           "Spec lines affected", "empty")

    def test_sorted_by_number(self):
        self.put(record(num="0010"), "0010")
        self.put(record(num="0002"), "0002")
        self.assertEqual([r.number for r in self.parse()], ["DR-0002", "DR-0010"])


class AgedTests(Base):
    AS_OF = D(2026, 10, 15)

    def aged_section(self, days, status="proposed"):
        date = (self.AS_OF - dt.timedelta(days=days)).isoformat()
        self.put(record(date=date, status=status))
        out = g.generate(self.dir, self.AS_OF)
        return out.split("## Aged proposed records")[1]

    def test_boundary_13_14_15(self):
        self.assertIn("None.", self.aged_section(13))
        self.assertIn("| DR-0001 |", self.aged_section(14))
        self.assertIn("| DR-0001 |", self.aged_section(15))

    def test_only_proposed_counts(self):
        self.assertIn("None.", self.aged_section(30, "ratified"))

    def test_threshold_configurable(self):
        self.put(record(date="2026-10-10"))
        out = g.generate(self.dir, self.AS_OF, threshold_days=5)
        self.assertIn("| DR-0001 |", out.split("## Aged proposed records")[1])

    def test_no_load_bearing_claim(self):
        self.put(record())
        self.assertNotIn("load-bearing", g.generate(self.dir, self.AS_OF).lower().replace(
            "dependency list", ""))

    def test_age_column(self):
        self.put(record(date="2026-10-01"))
        self.assertIn("| 2026-10-01 | 14 |", g.generate(self.dir, self.AS_OF))


class CheckTests(Base):
    def setUp(self):
        super().setUp()
        self.put(record())
        self.status = self.dir / "STATUS.md"

    def gen(self, as_of):
        self.status.write_text(g.generate(self.dir, as_of), encoding="utf-8")

    def test_deterministic(self):
        self.assertEqual(g.generate(self.dir, D(2026, 5, 1)),
                         g.generate(self.dir, D(2026, 5, 1)))

    def test_check_passes_and_is_independent_of_today(self):
        self.gen(D(2026, 1, 10))
        # Record is 9 days old at snapshot; 'today' would make it aged.
        for _ in range(2):
            self.assertIsNone(g.check(self.dir, self.status))
        self.assertEqual(g.committed_as_of(self.status), D(2026, 1, 10))

    def test_check_main_never_uses_wall_clock(self):
        self.gen(D(2026, 1, 10))
        argv = ["--dr-dir", str(self.dir), "--check"]
        self.assertEqual(g.main(argv), 0)

    def test_check_detects_header_edit(self):
        self.gen(D(2026, 1, 10))
        self.put(record(status="ratified"))
        diff = g.check(self.dir, self.status)
        self.assertIsNotNone(diff)
        self.assertIn("-| DR-0001", diff)

    def test_check_missing_or_bad_asof(self):
        with self.assertRaises(g.RecordError):
            g.check(self.dir, self.status)
        self.status.write_text("no date here\n", encoding="utf-8")
        with self.assertRaises(g.RecordError):
            g.check(self.dir, self.status)

    def test_cli_generate_with_as_of_then_check(self):
        self.assertEqual(g.main(["--dr-dir", str(self.dir), "--as-of", "2026-03-01"]), 0)
        self.assertIn("As of: 2026-03-01", self.status.read_text())
        self.assertEqual(g.main(["--dr-dir", str(self.dir), "--check"]), 0)

    def test_cli_bad_record_nonzero(self):
        self.put(record(status="bogus"))
        self.assertEqual(g.main(["--dr-dir", str(self.dir), "--as-of", "2026-03-01"]), 1)


class CommittedTreeTests(unittest.TestCase):
    def test_committed_status_is_fresh(self):
        self.assertIsNone(g.check(g.DR_DIR, g.STATUS_FILE))


if __name__ == "__main__":
    unittest.main()
