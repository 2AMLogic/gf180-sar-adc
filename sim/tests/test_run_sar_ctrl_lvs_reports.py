"""Exercise the SAR macro's extract and LVS report paths without klt or a PDK."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _loadmod import load_module

mod = load_module("sar_ctrl_reports_under_test", HERE.parents[1] / "layout/lvs/run_sar_ctrl_lvs.py")
EXTRACTS = {
    "sar_ctrl": mod.GDS,
    "gatelevel": mod.GDS,
    "sar_ctrl.nosupplystrap": "sar_ctrl.nosupplystrap.gds",
    "negctrl_supply_gatelevel": "sar_ctrl.nosupplystrap.gds",
}
COMPARES = ("committed", "gatelevel", "negctrl_supply", "negctrl_supply_gatelevel",
            "negctrl_wire", "negctrl_width")
STDOUT = '{ "source": "/test/pdk/library" }\n'


class SarCtrlReportsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        lib = self.root / mod.LIBRARY / "spice" / f"{mod.LIBRARY}.spice"
        lib.parent.mkdir(parents=True)
        lib.touch()
        pdk = {"root": "/test/pdk", "assets": {"libs_ref": str(self.root)}}
        for obj, name, value in (
            (mod.klt_env, "find_klt", "klt"),
            (mod.klt_env, "resolve_pdk", pdk),
            (mod.klt_env, "check_klt_capabilities", None),
            (mod, "build_golden", ("golden", {})),
            (mod, "strip_supply_straps", {}),
            (mod, "wrong_wire", ("wrong wire", "")),
            (mod, "wrong_width", ("wrong width", "")),
        ):
            stub = patch.object(obj, name, return_value=value)
            stub.start()
            self.addCleanup(stub.stop)

    def execute(self, wd, responses):
        def fake_klt(cmd, *, cwd, **kwargs):
            self.assertEqual(Path(cwd), wd)
            if cmd[1] == "extract":
                netlist = wd / cmd[cmd.index("-o") + 1]
                netlist.touch()
                report = netlist.with_suffix(".json").name
            else:
                self.assertEqual(cmd[1], "lvs")
                report = cmd[2].replace(".lvs_request.json", ".lvs.json")
            code, stdout = responses.get(report, (0, STDOUT))
            return subprocess.CompletedProcess(cmd, code, stdout, "klt diagnostic")

        with patch.object(mod.subprocess, "run", side_effect=fake_klt) as run:
            result = mod.execute(str(wd))
        return result, [call.args[0] for call in run.call_args_list]

    def test_failed_steps_raise_before_writing_the_report(self):
        for kind, names, bad_exits, json_exits in (
            ("extract", EXTRACTS, (3,), (0,)),
            ("lvs", COMPARES, (2,), (0, 3)),
        ):
            for name in names:
                report = f"{name}.{kind}.json"
                for code in (*bad_exits, *json_exits):
                    with self.subTest(report=report, exit=code):
                        wd = Path(tempfile.mkdtemp(dir=self.root))
                        stdout = STDOUT if code in bad_exits else "invalid"
                        with self.assertRaises(mod.klt_env.ToolingError) as error:
                            self.execute(wd, {report: (code, stdout)})
                        message = str(error.exception)
                        target = Path(EXTRACTS[name]).name if kind == "extract" else name
                        self.assertIn(f"klt {kind}", message)
                        self.assertIn(target, message)
                        if code in bad_exits:
                            self.assertIn(f"exit {code}", message)
                            self.assertIn("klt diagnostic", message)
                        self.assertFalse((wd / report).exists())

    def test_valid_reports_preserve_commands_requests_and_output(self):
        wd = self.root
        rel = os.path.relpath(mod.REPO_ROOT, wd)
        result, commands = self.execute(wd, {f"{n}.lvs.json": (3, STDOUT) for n in COMPARES})
        for name, gds in EXTRACTS.items():
            gatelevel = "gatelevel" in name
            if gds == mod.GDS:
                gds = os.path.join(rel, gds)
            flags = (["--pdk", mod.klt_env.PDK_VARIANT, "--abstract-cells", f"{mod.LIBRARY}__*"]
                     if gatelevel else [])
            self.assertIn(["klt", "extract", gds, "--deck", "gf180mcu", *flags, "--def-net-names",
                           "--def-pins", os.path.join(rel, mod.DEF), "-o", f"{name}.extract.spice",
                           "--format", "json"], commands)
        for name in COMPARES:
            request = f"{name}.lvs_request.json"
            self.assertIn(["klt", "lvs", request, "--format", "json"], commands)
            doc = json.loads((wd / request).read_text(encoding="utf-8"))
            if "gatelevel" in name:
                self.assertEqual(doc["reference"], {
                    "netlist": os.path.join(rel, mod.VERILOG), "top": mod.TOP,
                    "form": "gate-level-verilog", "library": mod.LIBRARY, "pdk": mod.klt_env.PDK_VARIANT,
                })
                self.assertEqual(doc["layout"], {"netlist": f"{name}.extract.spice", "top": mod.TOP})
            else:
                self.assertEqual(doc["reference"]["form"], "subckt-call")
                self.assertEqual(doc["options"], mod.LVS_OPTIONS)
            self.assertEqual(result[name], json.loads(STDOUT))
        for kind, names in (("extract", EXTRACTS), ("lvs", COMPARES)):
            for name in names:
                expected = STDOUT.replace("/test/pdk", "<PDK_ROOT>") if "gatelevel" in name else STDOUT
                self.assertEqual((wd / f"{name}.{kind}.json").read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
