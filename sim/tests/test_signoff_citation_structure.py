#!/usr/bin/env python3
"""Citation shape is checked symmetrically, on both `--check` and `--regen` (issue #1149).

`signoff/freshness.json` declares one spec per manifest citation key: an
ordinary spec carries `file`/`manifest_pins`/... itself, a compound one
(item 11, item 5's digital row, item 6's `not_applicable` form) carries a
`parts` list of such specs. Before #1149 `check()`'s step 1 only looked at
the MANIFEST side of that distinction and `regen()` only at the FRESHNESS
side, so each path had a blind spot that ended in an unhandled exception
rather than a verdict:

  * `check()`: a compound manifest entry hand-edited to an ordinary one
    skipped the `isinstance(entry, list)` branch and died in
    `_check_citation_agreement` with `KeyError: 'file'`;
  * `regen()`: an ordinary manifest entry hand-edited to a list died with
    `TypeError` (two parts) or `ValueError` (one or three), a removed key
    died with `KeyError`, an added key was silently dropped -- and every one
    of those happened AFTER `signoff/reports/<record-id>/` had been written,
    leaving an orphan directory behind.

Both paths now share `_iter_citation_specs` (leaf traversal),
`_citation_shape_mismatch` (the symmetric shape comparison) and
`_preflight_citation_structure` (the pre-write refusal `regen()` raises).
This test pins each of them, plus the two other consolidations the issue
asked for: step 4b reports EVERY mismatched compound part (no `all()`
short-circuit), and the refresh loop reproduces the committed
`freshness.json` byte for byte on an untampered tree.

Each case runs against a scratch overlay built by the real `_overlay` from
the committed repo; `regen()` is driven with the pinned `klt` resolved to a
mock, so the test needs no `klt` and no PDK.

    python3 -m unittest sim/tests/test_signoff_citation_structure.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from _loadmod import load_module  # noqa: E402

mod = load_module("run_signoff_citation_structure_under_test",
                  REPO / "signoff" / "run_signoff.py")

#: A compound (erc, lvs, ...) citation and an ordinary one, as committed.
COMPOUND_KEY = "11.analog"
#: A three-part (erc, lvs, pnr) compound citation, as committed.
THREE_PART_KEY = "11.digital"
ORDINARY_KEY = "3.analog"
FAKE_RECORD = "20260101-000000-abcdef0"


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


#: How many parts the committed freshness.json declares for `COMPOUND_KEY`,
#: so the expected messages below follow the committed manifest.
COMPOUND_PARTS = len(
    _read_json(REPO / "signoff" / "freshness.json")["citations"][COMPOUND_KEY]["parts"]
)


def _mutate_json(path, mutate):
    doc = _read_json(path)
    mutate(doc)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


class Overlay:
    """A scratch repo root holding exactly the files `--check`/`regen()` read."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="signoff-citation-shape-")
        self.root = self._tmp.name
        mod._overlay(str(REPO), self.root)

    def close(self):
        self._tmp.cleanup()

    def path(self, rel):
        return os.path.join(self.root, rel)


class IterCitationSpecsTests(unittest.TestCase):
    """`_iter_citation_specs`: sorted key order, one leaf per compound part."""

    def test_order_and_labels_across_ordinary_and_compound_entries(self):
        erc, lvs, drc, sta = ({"role": r} for r in ("erc", "lvs", "drc", "sta"))
        unroled = {"file": "x.json"}
        # Inserted out of key order on purpose: the iterator must sort.
        citations = {
            "5.digital": {"parts": [sta, unroled]},
            "11.analog": {"parts": [erc, lvs]},
            "3.analog": drc,
        }
        got = list(mod._iter_citation_specs(citations))
        self.assertEqual(got, [
            ("11.analog", "item 11.analog part 0 (erc)", erc),
            ("11.analog", "item 11.analog part 1 (lvs)", lvs),
            ("3.analog", "item 3.analog", drc),
            ("5.digital", "item 5.digital part 0 (sta)", sta),
            ("5.digital", "item 5.digital part 1 (?)", unroled),
        ])

    def test_yields_the_spec_objects_themselves_so_callers_can_mutate_them(self):
        spec = {"file": "a.json"}
        part = {"file": "b.json"}
        got = list(mod._iter_citation_specs({"x": spec, "y": {"parts": [part]}}))
        self.assertIs(got[0][2], spec)
        self.assertIs(got[1][2], part)

    def test_empty_mapping_yields_nothing(self):
        self.assertEqual(list(mod._iter_citation_specs({})), [])


class CitationShapeMismatchTests(unittest.TestCase):
    """`_citation_shape_mismatch`: the same verdict from either side."""

    def test_agreeing_shapes_return_none(self):
        compound = {"parts": [{"role": "erc"}, {"role": "lvs"}]}
        self.assertIsNone(mod._citation_shape_mismatch("k", compound, [("a", 1), ("b", 2)]))
        self.assertIsNone(mod._citation_shape_mismatch("k", {"file": "a"}, ("a", 1)))

    def test_manifest_compound_freshness_ordinary_keeps_check_wording(self):
        got = mod._citation_shape_mismatch("11.analog", {"file": "a"}, [("a", 1), ("b", 2)])
        self.assertEqual(
            got, "item 11.analog: manifest cites 2 compound parts, freshness declares no parts"
        )

    def test_part_count_disagreement_keeps_check_wording(self):
        spec = {"parts": [{"role": "erc"}, {"role": "lvs"}]}
        got = mod._citation_shape_mismatch("11.analog", spec, [("a", 1), ("b", 2), ("c", 3)])
        self.assertEqual(
            got, "item 11.analog: manifest cites 3 compound parts, freshness declares 2 parts"
        )

    def test_manifest_ordinary_freshness_compound_is_reported(self):
        spec = {"parts": [{"role": "erc"}, {"role": "lvs"}]}
        got = mod._citation_shape_mismatch("11.analog", spec, ("a", 1))
        self.assertEqual(
            got, "item 11.analog: manifest cites a single entry, freshness declares 2 parts"
        )

    def test_message_names_the_key_and_both_sides(self):
        spec = {"parts": [{}]}
        for entry in (("a", 1), [("a", 1), ("b", 2)]):
            msg = mod._citation_shape_mismatch("9.digital", spec, entry)
            self.assertIn("item 9.digital:", msg)
            self.assertIn("manifest cites", msg)
            self.assertIn("freshness declares 1 parts", msg)


class CheckShapeTests(unittest.TestCase):
    """`check()` records a shape disagreement as a failure, never a crash."""

    def setUp(self):
        ov = Overlay()
        self.addCleanup(ov.close)
        self.ov = ov
        self.manifest = ov.path(mod.MANIFEST_REL)

    def _manifest_entry(self, key):
        return _read_json(self.manifest)["evidence"][key]

    def test_compound_manifest_entry_made_ordinary_is_a_failure(self):
        first = self._manifest_entry(COMPOUND_KEY)[0]
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(
            COMPOUND_KEY, {"file": first["file"], "content_hash": first["content_hash"]}
        ))
        failures = mod.check(self.ov.root, verbose=False)
        self.assertEqual(failures, [
            f"item {COMPOUND_KEY}: manifest cites a single entry, "
            f"freshness declares {COMPOUND_PARTS} parts"
        ])

    def test_ordinary_manifest_entry_made_compound_is_a_failure(self):
        entry = self._manifest_entry(ORDINARY_KEY)
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(
            ORDINARY_KEY, [dict(entry), dict(entry)]
        ))
        failures = mod.check(self.ov.root, verbose=False)
        self.assertIn(
            "item 3.analog: manifest cites 2 compound parts, freshness declares no parts",
            failures,
        )

    def test_compound_part_count_disagreement_is_a_failure(self):
        parts = self._manifest_entry(COMPOUND_KEY)
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(
            COMPOUND_KEY, parts + [dict(parts[0])]
        ))
        failures = mod.check(self.ov.root, verbose=False)
        self.assertIn(
            f"item {COMPOUND_KEY}: manifest cites {COMPOUND_PARTS + 1} compound parts, "
            f"freshness declares {COMPOUND_PARTS} parts",
            failures,
        )

    def test_untampered_overlay_has_no_shape_failure(self):
        failures = mod.check(self.ov.root, verbose=False)
        self.assertEqual([m for m in failures if "freshness declares" in m], [])


class CheckStep4bTests(unittest.TestCase):
    """Step 4b must report every mismatched compound part, not just the first."""

    def setUp(self):
        ov = Overlay()
        self.addCleanup(ov.close)
        self.ov = ov
        self.manifest = ov.path(mod.MANIFEST_REL)
        self.freshness = ov.path(mod.FRESHNESS_REL)

    def _swap_parts(self, key, index_a, index_b):
        """Swap two parts of `key` in BOTH the manifest and freshness.json.

        Every repo-side pin then still agrees with itself, so steps 1-3 see
        nothing wrong -- only the committed report still remembers the order
        the grader actually read. That isolates step 4b."""
        def swap(seq):
            seq[index_a], seq[index_b] = seq[index_b], seq[index_a]

        _mutate_json(self.manifest, lambda m: swap(m["evidence"][key]))
        _mutate_json(self.freshness, lambda f: swap(f["citations"][key]["parts"]))

    def test_two_mismatched_parts_of_a_three_part_row_are_both_reported(self):
        # 11.digital is (erc, lvs, pnr); swapping parts 0 and 1 leaves part 2
        # agreeing, which must produce neither a failure nor an [ok] line.
        self._swap_parts(THREE_PART_KEY, 0, 1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            failures = mod.check(self.ov.root, verbose=True)
        self.assertEqual(len(failures), 2, failures)
        self.assertTrue(
            failures[0].startswith(f"row T1#{THREE_PART_KEY} part 0: report was graded on "),
            failures[0],
        )
        self.assertTrue(
            failures[1].startswith(f"row T1#{THREE_PART_KEY} part 1: report was graded on "),
            failures[1],
        )
        self.assertNotIn(f"row T1#{THREE_PART_KEY}", out.getvalue())

    def test_a_two_part_row_fully_swapped_reports_both_parts(self):
        self._swap_parts(COMPOUND_KEY, 0, 1)
        failures = mod.check(self.ov.root, verbose=False)
        self.assertEqual(len(failures), 2, failures)
        for idx, msg in enumerate(failures):
            self.assertIn(f"row T1#{COMPOUND_KEY} part {idx}: ", msg)

    def test_agreeing_compound_row_is_ok(self):
        n_parts = len(_read_json(self.freshness)["citations"][THREE_PART_KEY]["parts"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            failures = mod.check(self.ov.root, verbose=True)
        self.assertEqual(failures, [])
        self.assertIn(
            f"row T1#{THREE_PART_KEY}: report and manifest cite the same "
            f"{n_parts} compound parts",
            out.getvalue(),
        )


class RegenStructurePreflightTests(unittest.TestCase):
    """`regen()` refuses a shape disagreement before writing anything."""

    def setUp(self):
        ov = Overlay()
        self.addCleanup(ov.close)
        self.ov = ov
        self.manifest = ov.path(mod.MANIFEST_REL)
        self.freshness = ov.path(mod.FRESHNESS_REL)

    def _manifest_entry(self, key):
        return _read_json(self.manifest)["evidence"][key]

    def assertRegenRefused(self, *fragments):
        """Run `regen()` and require a `ToolingError` naming `fragments`, with
        no `klt` lookup, no mint, no grader run, and no byte written."""
        reports = self.ov.path(mod.REPORTS_REL)
        before = sorted(os.listdir(reports))
        untouched = {
            rel: _read_bytes(self.ov.path(rel))
            for rel in (mod.MANIFEST_REL, mod.FRESHNESS_REL)
        }
        out = io.StringIO()
        with mock.patch.object(mod, "resolve_klt") as resolve_klt, \
                mock.patch.object(mod, "record_id") as record_id, \
                mock.patch.object(mod, "mint_attestations") as mint, \
                mock.patch.object(mod.subprocess, "run") as run, \
                contextlib.redirect_stdout(out):
            with self.assertRaises(mod.ToolingError) as caught:
                mod.regen(self.ov.root, None)
        for tool in (resolve_klt, record_id, mint, run):
            tool.assert_not_called()
        message = str(caught.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(sorted(os.listdir(reports)), before)
        for rel, raw in untouched.items():
            self.assertEqual(_read_bytes(self.ov.path(rel)), raw, rel)
        return message

    def test_untampered_overlay_passes_the_structure_preflight(self):
        mod._preflight_citation_structure(self.ov.root)

    def test_ordinary_key_made_a_two_part_list_is_refused(self):
        a, b = self._manifest_entry(ORDINARY_KEY), self._manifest_entry("4.analog")
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(ORDINARY_KEY, [a, b]))
        self.assertRegenRefused(
            "item 3.analog: manifest cites 2 compound parts, freshness declares no parts"
        )

    def test_ordinary_key_made_a_one_part_list_is_refused(self):
        a = self._manifest_entry(ORDINARY_KEY)
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(ORDINARY_KEY, [a]))
        self.assertRegenRefused(
            "item 3.analog: manifest cites 1 compound parts, freshness declares no parts"
        )

    def test_ordinary_key_made_a_three_part_list_is_refused(self):
        a = self._manifest_entry(ORDINARY_KEY)
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(ORDINARY_KEY, [a, a, a]))
        self.assertRegenRefused(
            "item 3.analog: manifest cites 3 compound parts, freshness declares no parts"
        )

    def test_compound_key_made_ordinary_is_refused(self):
        first = self._manifest_entry(COMPOUND_KEY)[0]
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(
            COMPOUND_KEY, {"file": first["file"], "content_hash": first["content_hash"]}
        ))
        self.assertRegenRefused(
            f"item {COMPOUND_KEY}: manifest cites a single entry, "
            f"freshness declares {COMPOUND_PARTS} parts"
        )

    def test_compound_part_count_disagreement_is_refused(self):
        parts = self._manifest_entry(COMPOUND_KEY)
        _mutate_json(self.manifest, lambda m: m["evidence"].__setitem__(
            COMPOUND_KEY, parts + [dict(parts[1])]
        ))
        self.assertRegenRefused(
            f"item {COMPOUND_KEY}: manifest cites {COMPOUND_PARTS + 1} compound parts, "
            f"freshness declares {COMPOUND_PARTS} parts"
        )

    def test_removed_citation_key_is_refused(self):
        _mutate_json(self.manifest, lambda m: m["evidence"].pop(ORDINARY_KEY))
        message = self.assertRegenRefused("signoff/freshness.json declares citations")
        self.assertIn(f"'{ORDINARY_KEY}'", message)

    def test_added_citation_key_is_refused(self):
        _mutate_json(self.manifest, lambda m: m["evidence"].update({"9": "signoff/toolchain.json"}))
        message = self.assertRegenRefused("signoff/freshness.json declares citations")
        self.assertIn("'9'", message)

    def test_every_disagreement_is_named_in_one_refusal(self):
        first = self._manifest_entry(COMPOUND_KEY)[0]
        _mutate_json(self.manifest, lambda m: (
            m["evidence"].__setitem__(
                COMPOUND_KEY, {"file": first["file"], "content_hash": first["content_hash"]}
            ),
            m["evidence"].pop(ORDINARY_KEY),
        ))
        self.assertRegenRefused(
            f"item {COMPOUND_KEY}: manifest cites a single entry, "
            f"freshness declares {COMPOUND_PARTS} parts",
            "signoff/freshness.json declares citations",
        )


class RegenRefreshTests(unittest.TestCase):
    """The collapsed refresh loop reproduces the committed freshness.json.

    `regen()` runs for real against a scratch overlay with the pinned `klt`
    mocked: `mint_attestations` is a no-op and `klt signoff` replays the
    committed report's own stdout, so the refresh loop is the only thing
    under test. Shape is all the preflight checks, so stale PINS in
    freshness.json are exactly the state `--regen` exists to repair.
    """

    STALE = "sha256:" + "0" * 64

    def setUp(self):
        self.committed = _read_json(REPO / mod.FRESHNESS_REL)

        def grader_stdout(rel):
            with open(REPO / rel, encoding="utf-8") as fh:
                return fh.read()

        self.report_json = grader_stdout(self.committed["report"]["json"])
        self.report_text = grader_stdout(self.committed["report"]["text"])

    def _fake_run(self, args, **_kwargs):
        fmt = args[args.index("--format") + 1]
        return mock.Mock(returncode=3, stdout=self.report_json if fmt == "json" else self.report_text)

    def _regen(self, ov):
        with mock.patch.object(mod, "resolve_klt", return_value="klt"), \
                mock.patch.object(mod, "record_id", return_value=FAKE_RECORD), \
                mock.patch.object(mod, "mint_attestations"), \
                mock.patch.object(mod.subprocess, "run", side_effect=self._fake_run), \
                contextlib.redirect_stdout(io.StringIO()):
            return mod.regen(ov.root, None)

    @staticmethod
    def _leaves(spec):
        parts = spec.get("parts")
        return parts if isinstance(parts, list) else [spec]

    def _assert_refreshed_to_committed(self, ov):
        after = _read_json(ov.path(mod.FRESHNESS_REL))
        self.assertEqual(after["citations"], self.committed["citations"])
        self.assertEqual(after["expected_rows"], self.committed["expected_rows"])
        for field in ("sha256", "text_sha256", "tier", "t1_item_count", "t1_met_count",
                      "t1_not_applicable_count", "graded_by"):
            self.assertEqual(after["report"][field], self.committed["report"][field], field)
        self.assertEqual(after["report"]["record_id"], FAKE_RECORD)
        # `--check` pins nothing about formatting, but the committed file is
        # `indent=2` plus a trailing newline and `--regen` must keep writing
        # exactly that, through `_write_json`.
        with open(ov.path(mod.FRESHNESS_REL), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), json.dumps(after, indent=2) + "\n")
        self.assertEqual(
            sorted(os.listdir(ov.path(mod.REPORTS_REL))),
            sorted([FAKE_RECORD, self.committed["report"]["record_id"]]),
        )
        self.assertEqual(_read_bytes(ov.path(mod.MANIFEST_REL)),
                         _read_bytes(REPO / mod.MANIFEST_REL))

    def test_untampered_overlay_refreshes_to_the_committed_pins(self):
        ov = Overlay()
        self.addCleanup(ov.close)
        self.assertEqual(self._regen(ov), mod.EXIT_OK)
        self._assert_refreshed_to_committed(ov)

    def test_every_leaf_is_re_derived_including_later_compound_parts(self):
        # On an untouched overlay a refresh that skipped a part would be
        # invisible (nothing moves), so every pin is staled first -- in every
        # leaf of every citation, not only the first part of a compound one.
        ov = Overlay()
        self.addCleanup(ov.close)
        staled = 0

        def stale(doc):
            nonlocal staled
            for spec in doc["citations"].values():
                for leaf in self._leaves(spec):
                    leaf["file"] = "stale/overlay-only.json"
                    leaf["manifest_pins"] = self.STALE
                    leaf["envelope_asserts"] = {
                        field: "stale" for field in leaf.get("envelope_asserts", {})
                    }
                    leaf["artifacts"] = {
                        artifact: self.STALE for artifact in leaf.get("artifacts", {})
                    }
                    staled += 1

        _mutate_json(ov.path(mod.FRESHNESS_REL), stale)
        self.assertGreater(staled, len(self.committed["citations"]),
                           "the committed citations must include compound ones")
        self.assertEqual(self._regen(ov), mod.EXIT_OK)
        self._assert_refreshed_to_committed(ov)


if __name__ == "__main__":
    unittest.main()
