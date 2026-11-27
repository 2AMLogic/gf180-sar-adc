"""Exercise overlapping power checks while replaying committed klt reports."""

import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _loadmod import load_module

POWER = Path(__file__).resolve().parents[2] / "layout" / "power"
power = load_module("power_check_overlap", POWER / "run_power.py")


class PowerCheckOverlapTest(unittest.TestCase):
    def test_inner_check_cleans_up_only_its_own_specs(self):
        parent = Path(self.enterContext(tempfile.TemporaryDirectory()))
        manifest = power.load_manifest(power.CASES)
        base_spec = parent / manifest["base_spec"]
        shutil.copy(POWER / manifest["base_spec"], base_spec)
        reports = Path(power.REPORTS_DIR) / power.latest_record(power.REPORTS_DIR)
        checked = {}

        def replay_report(_klt, _layout, spec_path):
            spec = Path(spec_path)
            self.assertEqual(spec.parent.parent, parent)
            first_call = not checked
            checked.setdefault(spec.parent, []).append(spec.name)
            if first_call:
                # Finish the inner check before the outer tool reads its first spec.
                self.assertEqual(power.main(), power.EXIT_OK)
                self.assertTrue(spec.is_file(), "inner check removed the outer spec")
                self.assertEqual({d for d in checked if d.exists()}, {spec.parent})

            self.assertEqual(
                power.load_manifest(spec_path), power.load_manifest(reports / spec.name)
            )
            case = spec.name.removesuffix(".power-spec.json")
            report = power.load_manifest(reports / f"{case}.power.json")
            exit_code = report.pop("_klt_exit_code")
            return report, "", exit_code

        with (
            mock.patch.object(power, "HERE", str(parent)),
            mock.patch.object(power, "resolve_klt", return_value=("klt", {})),
            mock.patch.object(power, "run_case", replay_report),
            mock.patch.object(sys, "argv", ["run_power.py", "--check"]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(power.main(), power.EXIT_OK)

        expected_specs = [
            f"{case['name']}.power-spec.json" for case in manifest["cases"]
        ]
        self.assertEqual(len(checked), 2)
        for specs in checked.values():
            self.assertEqual(specs, expected_specs)
        self.assertEqual(list(parent.iterdir()), [base_spec])
