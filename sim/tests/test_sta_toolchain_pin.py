#!/usr/bin/env python3
"""Offline tests for design/sar-logic/flow/sta_toolchain_pin.py (issue #486).
A fake `klt` script stands in for the tool; nothing real is run.

    python3 -m unittest sim/tests/test_sta_toolchain_pin.py
"""

from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "design" / "sar-logic" / "flow"))

import sta_toolchain_pin as tp  # noqa: E402

PIN = {
    "klt_version": "klt 9.9.9",
    "klt_install": "klayout-tools==9.9.9",
    "klt_required_commands": ["extract", "sta"],
    "klt_required_extract_flags": ["--spef", "--def-pins"],
}


def fake_klt(d: Path, version="klt 9.9.9", verbs=("extract", "sta"), flags=("--spef", "--def-pins")) -> str:
    helptxt = "positional arguments:\n" + "".join(f"  {v}  does {v}\n" for v in verbs)
    script = (
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "{version}"; exit 0; fi\n'
        f'if [ "$1" = "extract" ]; then echo "{" ".join(flags)}"; exit 0; fi\n'
        f"cat <<'EOF'\n{helptxt}EOF\n"
    )
    p = d / "klt"
    p.write_text(script)
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return str(p)


class PinTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def test_match_passes(self):
        self.assertIsNone(tp.pin_error(fake_klt(self.d), PIN))

    def test_identity_mismatch_names_install(self):
        err = tp.pin_error(fake_klt(self.d, version="klt 0.8.1.dev1317+ga2804ab99263"), PIN)
        self.assertIn("does not match pin", err)
        self.assertIn('uvx --from "klayout-tools==9.9.9"', err)

    def test_missing_verb(self):
        err = tp.pin_error(fake_klt(self.d, verbs=("extract",)), PIN)
        self.assertIn("sta", err)

    def test_missing_flag(self):
        err = tp.pin_error(fake_klt(self.d, flags=("--spef",)), PIN)
        self.assertIn("--def-pins", err)

    def test_klt_absent(self):
        self.assertIn("not runnable", tp.pin_error(str(self.d / "nope"), PIN))

    def test_malformed_pin_is_error(self):
        bad = self.d / "bad.json"
        bad.write_text("{not json")
        self.assertIn("cannot read", tp.pin_error(fake_klt(self.d), pin_path=bad))
        bad.write_text(json.dumps({"klt_install": "x"}))
        self.assertIn("cannot read", tp.pin_error(fake_klt(self.d), pin_path=bad))

    def test_committed_pin_loads(self):
        pin = tp.load_pin()
        for k in ("klt_version", "klt_install", "klt_required_commands", "klt_required_extract_flags"):
            self.assertIn(k, pin)


if __name__ == "__main__":
    unittest.main()
