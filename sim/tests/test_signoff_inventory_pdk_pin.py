#!/usr/bin/env python3
"""The testbench inventories' PDK pin must match sim/toolchain.json (issue #762).

`signoff/testbench-inventory.{digital,analog}.json` each restate the PDK
revision in `pins.pdk.revision`, but the source of truth is `open_pdks` in
`sim/toolchain.json`. `klt signoff --attest 9` checks the pin against whatever
the inventory itself declares, so a stale inventory still reports
`[PASS] pin pdk`: after the #514/#517 re-pin both inventories kept declaring
`c6d73a3` and T1 item 9 kept reading `met` until PR #756 corrected them by
hand. This test is what makes the next re-pin fail loudly instead.

Three committed JSON files are compared; no PDK and no tool are needed, so it
runs in PR CI (`python3 -m unittest discover -s sim/tests -t sim/tests`, stage
1 of `sim/selftest.sh`, before the ngspice/PDK availability check).

    python3 -m unittest sim/tests/test_signoff_inventory_pdk_pin.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLCHAIN = REPO / "sim" / "toolchain.json"
INVENTORIES = (
    REPO / "signoff" / "testbench-inventory.digital.json",
    REPO / "signoff" / "testbench-inventory.analog.json",
)


def _rel(path: Path) -> str:
    """Repo-relative path when possible, so messages read like the issue does."""
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def _load(path: Path) -> tuple[object, str]:
    """Return (parsed JSON, "") or (None, reason) -- never raise."""
    try:
        return json.loads(Path(path).read_text()), ""
    except FileNotFoundError:
        return None, f"{_rel(path)}: missing"
    except (OSError, ValueError) as exc:
        return None, f"{_rel(path)}: cannot read ({exc})"


def pin_mismatches(toolchain_path: Path, inventory_paths) -> list[str]:
    """Report every way the inventories' PDK pin disagrees with the toolchain.

    Returns a list of human-readable messages, each naming the file at fault;
    an empty list means every inventory restates `open_pdks` exactly.

    A missing/malformed file, a missing or non-string `pins.pdk.revision`, and
    a null `open_pdks` are all reported rather than passed over: `open_pdks`
    may be set to null to disable the *runtime* environment check, but a null
    leaves the inventories' attested revision with nothing to be checked
    against, which is the same silent-staleness this guard exists to catch.
    """
    problems: list[str] = []

    toolchain, err = _load(toolchain_path)
    if err:
        return [err]
    if not isinstance(toolchain, dict):
        return [f"{_rel(toolchain_path)}: expected a JSON object"]

    expected = toolchain.get("open_pdks")
    if not isinstance(expected, str) or not expected:
        problems.append(
            f"{_rel(toolchain_path)}: open_pdks is {expected!r}, expected a commit hash "
            "string -- the inventories' attested pins.pdk.revision has nothing to be "
            "checked against"
        )
        expected = None

    for inventory_path in inventory_paths:
        inventory, err = _load(inventory_path)
        if err:
            problems.append(err)
            continue
        if not isinstance(inventory, dict):
            problems.append(f"{_rel(inventory_path)}: expected a JSON object")
            continue

        pins = inventory.get("pins")
        pdk = pins.get("pdk") if isinstance(pins, dict) else None
        revision = pdk.get("revision") if isinstance(pdk, dict) else None

        if not isinstance(revision, str) or not revision:
            problems.append(
                f"{_rel(inventory_path)}: pins.pdk.revision is {revision!r}, "
                "expected a commit hash string"
            )
            continue
        if expected is not None and revision != expected:
            problems.append(
                f"{_rel(inventory_path)}: pins.pdk.revision is {revision} but "
                f"{_rel(toolchain_path)} open_pdks is {expected} -- re-pin the "
                "inventory to the toolchain's revision"
            )

    return problems


class CommittedPinTest(unittest.TestCase):
    """The real, committed files must agree."""

    def test_committed_pins_match_toolchain(self):
        self.assertEqual([], pin_mismatches(TOOLCHAIN, INVENTORIES))

    def test_both_inventories_are_checked(self):
        # Guards against the list above silently losing an entry.
        for path in INVENTORIES:
            self.assertTrue(path.is_file(), f"{_rel(path)} is missing")
        self.assertEqual(2, len(INVENTORIES))


# A copy of the real files is normalized onto BASE_REV before each negative
# case, so the tampered-copy tests prove what they claim no matter what the
# committed files currently say -- real drift must fail CommittedPinTest
# alone, with one legible message, not every case at once.
BASE_REV = "1111111111111111111111111111111111111111"
STALE_REV = "c6d73a3f9a7b5e2c1d0f4a8b6e3c9d7f2a5b8c1e"


class TamperedCopyTest(unittest.TestCase):
    """The check must actually bite: tamper a copy and watch it fail."""

    @staticmethod
    def _patch(path: Path, mutate):
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data, indent=2) + "\n")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.toolchain = root / TOOLCHAIN.name
        shutil.copyfile(TOOLCHAIN, self.toolchain)
        self.inventories = []
        for src in INVENTORIES:
            dst = root / src.name
            shutil.copyfile(src, dst)
            self.inventories.append(dst)
        self.digital, self.analog = self.inventories

        self._patch(self.toolchain, lambda d: d.update(open_pdks=BASE_REV))
        for inventory in self.inventories:
            self._patch(inventory, lambda d: d["pins"]["pdk"].update(revision=BASE_REV))

    def test_clean_copy_passes(self):
        self.assertEqual([], pin_mismatches(self.toolchain, self.inventories))

    def test_stale_digital_inventory_is_named(self):
        self._patch(self.digital, lambda d: d["pins"]["pdk"].update(revision=STALE_REV))
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertEqual(1, len(problems), problems)
        self.assertIn(self.digital.name, problems[0])
        self.assertNotIn(self.analog.name, problems[0])
        self.assertIn(STALE_REV, problems[0])
        self.assertIn(BASE_REV, problems[0])

    def test_stale_analog_inventory_is_named(self):
        self._patch(self.analog, lambda d: d["pins"]["pdk"].update(revision=STALE_REV))
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertEqual(1, len(problems), problems)
        self.assertIn(self.analog.name, problems[0])
        self.assertNotIn(self.digital.name, problems[0])

    def test_toolchain_repin_names_every_stale_inventory(self):
        # The real-world case: sim/toolchain.json is re-pinned and the
        # inventories are left behind -- exactly the #514/#517 -> PR #756 drift.
        self._patch(self.toolchain, lambda d: d.update(open_pdks=STALE_REV))
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertEqual(2, len(problems), problems)
        self.assertTrue(any(self.digital.name in p for p in problems), problems)
        self.assertTrue(any(self.analog.name in p for p in problems), problems)

    def test_missing_revision_key_is_reported(self):
        self._patch(self.digital, lambda d: d["pins"]["pdk"].pop("revision"))
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertEqual(1, len(problems), problems)
        self.assertIn(self.digital.name, problems[0])
        self.assertIn("pins.pdk.revision", problems[0])

    def test_null_open_pdks_is_reported(self):
        self._patch(self.toolchain, lambda d: d.update(open_pdks=None))
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertTrue(any("open_pdks" in p for p in problems), problems)
        self.assertTrue(any(self.toolchain.name in p for p in problems), problems)

    def test_unreadable_file_is_reported_not_raised(self):
        self.digital.write_text("{not json")
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertEqual(1, len(problems), problems)
        self.assertIn(self.digital.name, problems[0])
        self.assertIn("cannot read", problems[0])

    def test_missing_inventory_is_reported(self):
        self.analog.unlink()
        problems = pin_mismatches(self.toolchain, self.inventories)
        self.assertEqual(1, len(problems), problems)
        self.assertIn(self.analog.name, problems[0])
        self.assertIn("missing", problems[0])


if __name__ == "__main__":
    unittest.main()
