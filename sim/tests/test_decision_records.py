#!/usr/bin/env python3
"""Unit tests enforcing spec/decision-records/README.md's numbering rule.

    python3 -m unittest discover -s sim/tests -v

spec/decision-records/README.md § "Numbering" states the invariant precisely:
"Two records must never share a number, even when one of them is
superseded." Nothing mechanically enforced this until now -- two branches
concurrently claimed `DR-0029` on 2026-09-19 and the collision sat on `main`
for two days before being noticed and filed as #335 (fixed by PR #354,
renumbering the duplicate to `DR-0031`). This module is the mechanical check
that would have caught it at commit time instead.
"""

from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
DR_DIR = SIM_DIR.parent / "spec" / "decision-records"

DR_PREFIX_RE = re.compile(r"DR-\d{4}")


class DrNumberUniquenessTests(unittest.TestCase):
    """spec/decision-records/README.md: 'Two records must never share a
    number, even when one of them is superseded.'"""

    def test_every_dr_prefix_is_claimed_by_exactly_one_file(self):
        files = sorted(DR_DIR.glob("DR-*.md"))
        self.assertTrue(files, f"no DR-*.md files found under {DR_DIR}")

        by_prefix: dict[str, list[str]] = {}
        for path in files:
            match = DR_PREFIX_RE.match(path.name)
            if not match:
                continue
            by_prefix.setdefault(match.group(0), []).append(path.name)

        prefixes = [name for names in by_prefix.values() for name in names]
        counts = Counter(DR_PREFIX_RE.match(name).group(0) for name in prefixes)
        dupes = sorted(prefix for prefix, count in counts.items() if count > 1)

        if dupes:
            details = "; ".join(
                f"{prefix} claimed by {sorted(by_prefix[prefix])}" for prefix in dupes
            )
            self.fail(
                "Duplicate DR-NNNN prefix(es) found: "
                f"{details}. Per spec/decision-records/README.md § "
                "'Numbering', two records must never share a number -- "
                "renumber the LATER-MERGED file to the next unused DR-NNNN "
                "(filename, its '# DR-NNNN:' heading, and every "
                "cross-reference to it) before merge."
            )


if __name__ == "__main__":
    unittest.main()
