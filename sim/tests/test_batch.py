#!/usr/bin/env python3
"""Unit tests for the `klt sim` batch exporter (harness/batch.py).

No ngspice, no PDK, no network, no klt: the exporter and the report -> record
conversion are pure functions over dicts, and the CLI routing is exercised with
`klt` and the local runner both mocked.

    python3 -m unittest discover -s sim/tests -p 'test_batch.py' -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import batch, cli, corners, report, runner, testbench  # noqa: E402
from harness.pdk import Pdk  # noqa: E402

PINNED_PDK = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"
PINS = {"open_pdks": PINNED_PDK, "ngspice_min_major": 46}


def make_pdk(root: Path) -> Pdk:
    (root / "libs.tech" / "ngspice").mkdir(parents=True, exist_ok=True)
    (root / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    (root / "libs.tech" / "ngspice" / "design.ngspice").write_text("* fake\n")
    (root / "SOURCES").write_text(f"open_pdks {PINNED_PDK}\n")
    return Pdk(path=root, variant="gf180mcuD", source="test")


def make_tb(root: Path, manifest: dict, netlist: str = "v1 out 0 dc {vdd_val}\n"):
    tb_dir = root / "exp" / "testbench"
    tb_dir.mkdir(parents=True, exist_ok=True)
    (tb_dir / "x.spice").write_text(netlist)
    body = {"name": "x", "netlist": "x.spice"}
    body.update(manifest)
    (tb_dir / "tb.json").write_text(json.dumps(body))
    return testbench.load(tb_dir)


TRAN_MANIFEST = {
    "analyses": [
        "tran 5n 1u",
        "meas tran a MAX v(out) FROM=0.1u",
        "meas tran b WHEN v(out)=1.4 RISE=2",
    ],
    "measure": {"amax": "a", "span_ns": "(b-a)*1e9", "vout_end": "v(out)[0]"},
}


class RoutingTests(unittest.TestCase):
    def test_dispatch_host_sends_a_multi_point_grid_to_klt(self):
        env = {"KLT_SIM_BACKEND": "batch"}
        self.assertEqual(batch.resolve_backend("auto", 45, env), "klt")

    def test_dispatch_host_keeps_a_single_point_local(self):
        env = {"KLT_SIM_BACKEND": "batch"}
        self.assertEqual(batch.resolve_backend("auto", 1, env), "local")

    def test_plain_host_stays_local(self):
        self.assertEqual(batch.resolve_backend("auto", 45, {}), "local")
        self.assertEqual(batch.resolve_backend("auto", 45, {"KLT_SIM_BACKEND": "local"}), "local")

    def test_explicit_backend_beats_the_environment(self):
        env = {"KLT_SIM_BACKEND": "batch"}
        self.assertEqual(batch.resolve_backend("local", 1, env), "local")
        self.assertEqual(batch.resolve_backend("local", 45, env, allow_local_grid=True), "local")
        self.assertEqual(batch.resolve_backend("batch", 2, {}), "klt")
        self.assertEqual(batch.resolve_backend("remote", 2, {}), "klt")

    def test_explicit_local_multipoint_grid_refused_on_dispatch_host(self):
        for host in ("batch", "remote"):
            with self.assertRaises(batch.BatchError):
                batch.resolve_backend("local", 45, {"KLT_SIM_BACKEND": host})
        # no dispatch-host marker: unchanged historical behaviour
        self.assertEqual(batch.resolve_backend("local", 45, {}), "local")

    def test_klt_flag_is_only_passed_when_explicit(self):
        """With no flag klt applies its own $KLT_SIM_BACKEND precedence."""
        self.assertEqual(batch.klt_backend_flag(""), [])
        self.assertEqual(batch.klt_backend_flag("batch"), ["--backend", "batch"])

    def test_unknown_backend_is_rejected(self):
        with self.assertRaises(batch.BatchError):
            batch.resolve_backend("fleet", 3, {})


class ExportabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_op_manifest_maps_to_a_single_op_analysis(self):
        tb = make_tb(self.root, {"analyses": ["op"], "measure": {"vout": "v(out)"}})
        plan = batch.check_exportable(tb)
        self.assertEqual((plan.kind, plan.args, plan.meas_cards), ("op", "", ()))

    def test_tran_meas_lines_become_meas_cards(self):
        tb = make_tb(self.root, TRAN_MANIFEST)
        plan = batch.check_exportable(tb)
        self.assertEqual(plan.kind, "tran")
        self.assertEqual(plan.args, "5n 1u")
        self.assertEqual(
            [card for _, card in plan.meas_cards],
            [".meas tran a MAX v(out) FROM=0.1u", ".meas tran b WHEN v(out)=1.4 RISE=2"],
        )

    def test_a_measure_that_is_a_meas_name_reads_that_meas_directly(self):
        plan = batch.check_exportable(make_tb(self.root, TRAN_MANIFEST))
        self.assertEqual(plan.value_names["amax"], "a")
        self.assertEqual(plan.value_names["span_ns"], "span_ns")

    def test_control_steps_klt_cannot_express_are_refused_not_approximated(self):
        for step in ("setseed 1", "let x = 2", "linearize v(out)", "alterparam c=1", "noise v(o) vin dec 10 1 1k"):
            with self.subTest(step=step):
                tb = make_tb(self.root, {"analyses": ["tran 1n 1u", step], "measure": {"m": "v(out)"}})
                with self.assertRaises(batch.NotExportable):
                    batch.check_exportable(tb)

    def test_a_non_analysis_first_line_is_refused(self):
        tb = make_tb(self.root, {"analyses": ["setseed 1", "op"], "measure": {"m": "v(out)"}})
        with self.assertRaises(batch.NotExportable):
            batch.check_exportable(tb)

    def test_temp_c_param_is_refused_because_klt_only_sets_dot_temp(self):
        tb = make_tb(self.root, {"analyses": ["op"], "measure": {"m": "v(out)"}},
                     netlist="v1 out 0 dc {temp_c/100}\n")
        with self.assertRaisesRegex(batch.NotExportable, "temp_c"):
            batch._fragment_text(tb)

    def test_temp_c_in_a_comment_is_not_a_reference(self):
        tb = make_tb(self.root, {"analyses": ["op"], "measure": {"m": "v(out)"}},
                     netlist="* uses temp_c? no\nv1 out 0 dc 1\n")
        self.assertIn("v1 out", batch._fragment_text(tb))

    def test_measure_name_colliding_with_a_different_meas_is_refused(self):
        tb = make_tb(self.root, {
            "analyses": ["tran 1n 1u", "meas tran a MAX v(out)"],
            "measure": {"a": "a*2"},
        })
        with self.assertRaises(batch.NotExportable):
            batch.check_exportable(tb)


class ParamExpressibleTests(unittest.TestCase):
    NAMES = {"a", "b"}

    def test_arithmetic_over_meas_results(self):
        for expr in ("(b-a)*1e9", "a*1e-3", "abs(a-b)*1e6", "max(a,b)", "1.5e3/a"):
            with self.subTest(expr=expr):
                self.assertTrue(batch.param_expressible(expr, self.NAMES))

    def test_vectors_and_unknown_names_need_expr(self):
        for expr in ("v(out)", "v(out)[0]", "i(vsup)*1e6", "c", "foo(a)", "a'b"):
            with self.subTest(expr=expr):
                self.assertFalse(batch.param_expressible(expr, self.NAMES))

    def test_request_uses_param_cards_where_possible_and_expr_otherwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tb = make_tb(root, TRAN_MANIFEST)
            plan = batch.check_exportable(tb)
            request = batch.build_request(
                tb, make_pdk(root / "pdk"), plan, corners.resolve_corners(["tt"]),
                [27.0], [3.3], "body.spice", 60,
            )
        by_name = {m["name"]: m for m in request["measurements"]}
        self.assertEqual(by_name["span_ns"]["spice"], ".meas tran span_ns param='(b-a)*1e9'")
        self.assertEqual(by_name["vout_end"], {"name": "vout_end", "expr": "v(out)[0]"})
        self.assertNotIn("amax", by_name)  # read straight off the 'a' card
        self.assertIn("a", by_name)


class RequestShapeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk = make_pdk(self.root / "pdk")
        self.tb = make_tb(self.root, TRAN_MANIFEST)
        self.plan = batch.check_exportable(self.tb)

    def _request(self, **kw):
        cl = corners.resolve_corners(["mos"])
        args = dict(netlist_name="body.spice", timeout_s=900)
        args.update(kw)
        return batch.build_request(
            self.tb, self.pdk, self.plan, cl, [-40.0, 27.0, 125.0], [2.97, 3.3, 3.63], **args
        )

    def test_grid_axes_match_the_local_grid(self):
        request = self._request()
        process = request["corners"]["process"]
        self.assertEqual([p["name"] for p in process], ["tt", "ff", "ss", "fs", "sf"])
        self.assertEqual(process[1]["sections"], list(corners.CORNERS["ff"].sections))
        self.assertEqual(request["corners"]["supply_v"], {"vdd_val": [2.97, 3.3, 3.63]})
        self.assertEqual(request["corners"]["temperature_c"], [-40.0, 27.0, 125.0])
        # 5 x 3 x 3 -- klt expands the same factorial grid.
        self.assertEqual(
            len(request["corners"]["process"]) * 3 * 3,
            len(corners.build_grid(corners.resolve_corners(["mos"]), [-40, 27, 125], [2.97, 3.3, 3.63])),
        )

    def test_per_point_timeout_is_the_timeout_flag(self):
        self.assertEqual(self._request(timeout_s=3000)["options"]["timeout_s"], 3000)

    def test_artifacts_are_kept_for_the_raw_log_and_the_abort_scan(self):
        self.assertTrue(self._request()["options"]["keep_artifacts"])

    def test_models_are_resolved_by_pdk_variant_on_the_runner(self):
        request = self._request()
        self.assertEqual(request["models"]["pdk"], "gf180mcuD")
        self.assertEqual(request["models"]["lib"], batch.MODEL_LIB_REL)

    def test_threads_and_save_list_are_opt_in(self):
        base = self._request()
        self.assertNotIn("save_mode", base["options"])
        self.assertEqual(base["options"]["ngspice_init"], ["set numdgt=10"])
        tuned = self._request(num_threads=1, save_measured=True)
        self.assertIn("set num_threads=1", tuned["options"]["ngspice_init"])
        self.assertEqual(tuned["options"]["save_mode"], "netlist")

    def test_version_check_override_rides_in_the_batch_block(self):
        request = self._request(batch={"runner_version_check": "warn"})
        self.assertEqual(request["batch"], {"runner_version_check": "warn"})

    def test_body_carries_the_harness_params_and_the_fragment(self):
        body = batch.build_body(self.tb, self.pdk, save_vectors=["v(out)"])
        self.assertIn(".param vdd_nom=3.3", body)
        self.assertIn(".param vdd_val=3.3", body)
        self.assertIn("design.ngspice", body)
        self.assertIn(".subckt mim_cap_2f0", body)
        self.assertIn(".save v(out)", body)
        self.assertIn("v1 out 0 dc {vdd_val}", body)
        for forbidden in (".control", ".endc", ".end\n", "\n.temp", "\n.lib "):
            self.assertNotIn(forbidden, body)


def klt_corner(process, temp, vdd, status="pass", measurements=None, diagnostics=None,
               artifacts=None, runtime=1.5):
    return {
        "corner_id": f"{process}/{vdd:.3f}V/{temp:g}C",
        "process": process,
        "supply_v": {"vdd_val": vdd},
        "temperature_c": float(temp),
        "status": status,
        "runtime_s": runtime,
        "measurements": [
            {"name": k, "value": v, "unit": None, "status": "pass", "margin": None}
            for k, v in (measurements or {}).items()
        ],
        "diagnostics": diagnostics or [],
        "artifacts": artifacts or {"log": None, "raw": None, "waveform": None, "deck": None},
        "monte_carlo": None,
    }


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tb = make_tb(self.root, {
            "analyses": ["tran 5n 1u", "meas tran a MAX v(out)", "meas tran b MAX v(o2)"],
            "measure": {"amax": "a", "bmax": "b"},
        })
        self.plan = batch.check_exportable(self.tb)
        self.points = corners.build_grid(corners.resolve_corners(["tt", "ss"]), [27.0], [3.3])
        self.work = self.root / "work"
        self.logs = self.root / "logs"

    def _artifacts(self, name, log_text):
        d = self.root / "art" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "corner.cir").write_text(f"* deck {name}\n")
        log = d / "ngspice.log"
        if log_text is not None:
            log.write_text(log_text)
        return {"log": str(log) if log_text is not None else None, "raw": None,
                "waveform": None, "deck": str(d / "corner.cir")}

    def _convert(self, corner_list, timeout=300):
        return batch.to_point_results(
            self.tb, self.plan, self.points, {"corners": corner_list},
            self.work, self.logs, timeout,
        )

    def test_clean_corner_is_ok_with_values_log_and_deck(self):
        res = self._convert([
            klt_corner("tt", 27, 3.3, measurements={"a": 1.5, "b": 2.5},
                       artifacts=self._artifacts("tt", "ngspice-46\nall fine\n")),
            klt_corner("ss", 27, 3.3, measurements={"a": 1.4, "b": 2.4},
                       artifacts=self._artifacts("ss", "ok\n")),
        ])
        self.assertEqual([r.status for r in res], ["ok", "ok"])
        self.assertEqual(res[0].measurements, {"amax": 1.5, "bmax": 2.5})
        self.assertEqual(res[0].seconds, 1.5)
        self.assertEqual(res[0].log, "tt_27c_3.30v.log")
        self.assertIn("all fine", (self.logs / "tt_27c_3.30v.log").read_text())
        self.assertEqual((self.work / "tt_27c_3.30v.spice").read_text(), "* deck tt\n")

    def test_results_come_back_in_grid_order_whatever_klt_returned(self):
        res = self._convert([
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "x")),
            klt_corner("tt", 27, 3.3, measurements={"a": 3, "b": 4}, artifacts=self._artifacts("tt", "x")),
        ])
        self.assertEqual([r.point.corner.name for r in res], ["tt", "ss"])
        self.assertEqual(res[0].measurements["amax"], 3)

    def test_timeout_is_an_error_point_that_states_the_budget(self):
        timeout = {"severity": "error", "code": "timeout", "message": "exceeded 300s"}
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout], runtime=300.0),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "x")),
        ], timeout=300)
        self.assertEqual(res[0].status, "error")
        self.assertEqual(res[0].message, "ngspice timed out after 300s")
        self.assertEqual((self.logs / "tt_27c_3.30v.log").read_text(), "TIMEOUT after 300s\n")

    def test_timeout_message_matches_the_local_runner_wording(self):
        """Same string runner.run_point writes, so the record reads alike."""
        with mock.patch.object(runner.subprocess, "run",
                               side_effect=runner.subprocess.TimeoutExpired("ngspice", 7)):
            local = runner.run_point(
                self.tb, make_pdk(self.root / "pdk"), self.points[0], self.root / "w", timeout_s=7
            )
        timeout = {"severity": "error", "code": "timeout", "message": "x"}
        remote = batch.to_point_results(
            self.tb, self.plan, self.points[:1],
            {"corners": [klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout])]},
            self.work, self.logs, 7,
        )[0]
        self.assertEqual((remote.status, remote.message), (local.status, local.message))

    def test_aborted_analysis_is_failed_even_if_every_value_parsed(self):
        """Issue #341, on the batch path: a truncated transient is never ok."""
        log = "doAnalyses: TRAN:  Timestep too small; time = 1.4e-06\ntran simulation(s) aborted\n"
        res = self._convert([
            klt_corner("tt", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("tt", log)),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "ok")),
        ])
        self.assertEqual(res[0].status, "failed")
        self.assertIn("truncated data", res[0].message)
        self.assertEqual(res[1].status, "ok")

    def test_missing_log_is_failed_not_trusted(self):
        res = self._convert([
            klt_corner("tt", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("tt", None)),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "ok")),
        ])
        self.assertEqual(res[0].status, "failed")
        self.assertIn("no ngspice log", res[0].message)

    def test_missing_measurement_is_failed_and_named(self):
        res = self._convert([
            klt_corner("tt", 27, 3.3, measurements={"a": 1}, artifacts=self._artifacts("tt", "ok")),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": None}, artifacts=self._artifacts("ss", "ok")),
        ])
        self.assertEqual([r.status for r in res], ["failed", "failed"])
        self.assertEqual(res[0].missing, ["bmax"])

    def test_a_point_klt_did_not_report_is_an_error_not_dropped(self):
        res = self._convert([
            klt_corner("tt", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("tt", "ok")),
        ])
        self.assertEqual(len(res), 2)
        self.assertEqual(res[1].status, "error")
        self.assertIn("no result", res[1].message)

    def test_job_level_failure_marks_every_point_error(self):
        diag = {"severity": "error", "code": "batch_job_failed", "message": "job exited 87"}
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", diagnostics=[diag]),
            klt_corner("ss", 27, 3.3, status="error", diagnostics=[diag]),
        ])
        self.assertEqual([r.status for r in res], ["error", "error"])
        self.assertIn("batch_job_failed", res[0].message)

    def test_converted_results_build_the_same_record_as_a_local_run(self):
        res = self._convert([
            klt_corner("tt", 27, 3.3, measurements={"a": 1.5, "b": 2.5}, artifacts=self._artifacts("tt", "ok")),
            klt_corner("ss", 27, 3.3, measurements={"a": 1.4, "b": 2.4}, artifacts=self._artifacts("ss", "ok")),
        ])
        klt_report = {
            "status": "not_checked",
            "environment": {"engine": "ngspice", "engine_version": "46", "netlist_sha256": "n",
                            "models_lib_sha256": "m",
                            "remote": {"provider": "aws-batch-fleet", "job_id": "klt-sim-1",
                                       "runner_compatibility": "match"}},
            "provenance": {"klt_version": "0.6.0", "pdk": {"name": "gf180mcuD", "version": PINNED_PDK}},
        }
        execution = batch.execution_summary(klt_report, "batch", self.root / "request.json", "b" * 64, "r" * 64)
        record = report.build_record(
            tb=self.tb, pdk=make_pdk(self.root / "pdk"), points=self.points, results=res,
            ngspice=batch.ngspice_label(klt_report), repo_root=SIM_DIR.parent,
            record_id="20260101-000000-abcdef0", started_utc="2026-01-01T00:00:00+00:00",
            wall_seconds=1.0, subset_reason="unit test", git={"commit": "c" * 40, "short": "ccccccc",
                                                              "branch": "b", "dirty": False},
            allow_unswept_axes=True, execution=execution,
        )
        local_keys = set(report.build_record.__code__.co_varnames)  # sanity: function importable
        self.assertTrue(local_keys)
        self.assertEqual(record["status"], "pass")
        self.assertEqual(record["grid"]["points_ok"], 2)
        for key in ("netlist_sha256", "manifest_sha256", "netlist_provenance"):
            self.assertIn(key, record["testbench"])
        env = record["environment"]
        for key in ("git", "pdk", "toolchain", "ngspice"):
            self.assertIn(key, env)
        self.assertEqual(env["execution"]["remote"]["job_id"], "klt-sim-1")
        self.assertEqual(env["execution"]["generated_body_sha256"], "b" * 64)
        md = report.render_record(record, "exp")
        self.assertIn("Executed via", md)
        self.assertIn("klt-sim-1", md)
        self.assertIn("Testbench netlist sha256", md)
        self.assertIn("ngspice-46 (run by aws-batch-fleet, job klt-sim-1)", md)

    def test_a_local_record_has_no_execution_block(self):
        res = [
            runner.PointResult(point=p, status="ok", measurements={"amax": 1.0, "bmax": 2.0})
            for p in self.points
        ]
        record = report.build_record(
            tb=self.tb, pdk=make_pdk(self.root / "pdk"), points=self.points, results=res,
            ngspice="ngspice-46", repo_root=SIM_DIR.parent, record_id="r",
            started_utc="t", wall_seconds=1.0, allow_unswept_axes=True,
            git={"commit": "c", "short": "c", "branch": "b", "dirty": False},
        )
        self.assertNotIn("execution", record["environment"])
        self.assertNotIn("Executed via", report.render_record(record, "exp"))


class FleetToolchainTests(unittest.TestCase):
    def _report(self, engine="46", pdk_version=f"open_pdks {PINNED_PDK}"):
        return {"environment": {"engine_version": engine},
                "provenance": {"pdk": {"name": "gf180mcuD", "version": pdk_version}}}

    def test_pinned_fleet_has_no_drift(self):
        self.assertEqual(batch.fleet_toolchain_drifts(self._report(), PINS), [])

    def test_older_fleet_ngspice_is_a_drift(self):
        drifts = batch.fleet_toolchain_drifts(self._report(engine="42"), PINS)
        self.assertEqual([d.tool for d in drifts], ["ngspice"])

    def test_different_or_unreported_fleet_pdk_is_a_drift(self):
        other = batch.fleet_toolchain_drifts(self._report(pdk_version="open_pdks deadbeef"), PINS)
        self.assertEqual([d.tool for d in other], ["open_pdks"])
        none = batch.fleet_toolchain_drifts({"environment": {"engine_version": "46"}}, PINS)
        self.assertEqual([d.tool for d in none], ["open_pdks"])

    def test_pdk_version_is_the_bare_hash_the_pin_compares_against(self):
        """klt reports 'open_pdks <hash>'; the pin is the bare hash."""
        self.assertEqual(batch.fleet_toolchain_drifts(self._report(), PINS), [])


class RunnerSkewTests(unittest.TestCase):
    def _report(self, compat):
        return {"environment": {"remote": {
            "runner_compatibility": compat, "runner_klt_version": "0.5.0",
            "client_klt_version": "0.6.0"}}}

    def test_match_adds_no_caveat(self):
        execution: dict = {}
        batch.apply_runner_caveats(execution, self._report("match"), needs_honored_options=True)
        self.assertNotIn("caveats", execution)

    def test_skew_is_stamped_into_the_record(self):
        execution: dict = {}
        batch.apply_runner_caveats(execution, self._report("mismatch"), needs_honored_options=False)
        self.assertIn("numdgt", execution["caveats"][0])
        self.assertIn("0.5.0", execution["caveats"][0])

    def test_skew_with_options_the_runner_may_ignore_refuses_to_record(self):
        with self.assertRaises(batch.BatchError):
            batch.apply_runner_caveats({}, self._report("mismatch"), needs_honored_options=True)


class SubmitTests(unittest.TestCase):
    def _proc(self, stdout="", stderr="", returncode=0):
        return mock.Mock(stdout=stdout, stderr=stderr, returncode=returncode)

    def test_report_is_read_even_on_exit_4(self):
        """Gate on the payload, not the exit code (klt's documented rule)."""
        payload = json.dumps({"status": "error", "corners": []})
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run", return_value=self._proc(payload, "", 4)) as run:
            got, _ = batch.submit(Path("r.json"), Path("out"), "batch")
        self.assertEqual(got["status"], "error")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], ["klt", "sim", "r.json"])
        self.assertIn("--format", cmd)
        self.assertEqual(cmd[cmd.index("--backend") + 1], "batch")

    def test_no_backend_flag_without_an_explicit_backend(self):
        payload = json.dumps({"corners": []})
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run", return_value=self._proc(payload)) as run:
            batch.submit(Path("r.json"), Path("out"), "")
        self.assertNotIn("--backend", run.call_args.args[0])

    def test_a_rejected_submit_raises_with_klts_message_and_never_runs_locally(self):
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run",
                                  return_value=self._proc("", "klt sim: no capacity", 1)), \
                mock.patch.object(runner, "run_grid") as run_grid:
            with self.assertRaisesRegex(batch.BatchError, "no capacity"):
                batch.submit(Path("r.json"), Path("out"), "batch")
        run_grid.assert_not_called()

    def test_klt_cmd_may_be_a_throwaway_uvx_invocation(self):
        with mock.patch.object(batch.shutil, "which", return_value="/usr/bin/uvx"):
            self.assertEqual(
                batch.klt_available("uvx --from klayout-tools==0.5.0 klt"),
                ["uvx", "--from", "klayout-tools==0.5.0", "klt"],
            )
        with mock.patch.object(batch.shutil, "which", return_value=None):
            with self.assertRaises(batch.BatchError):
                batch.klt_available("klt")


class CliBatchTests(unittest.TestCase):
    """End-to-end through cli.run with the PDK, klt and the local runner mocked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk = make_pdk(self.root / "gf180mcuD")
        make_tb(self.root, {"analyses": ["op"], "measure": {"vout": "v(out)"},
                            "temperatures_c": [27], "supply_tolerance": 0.0, "corners": ["tt", "ss"]})
        self.experiment = self.root / "exp"

    def _args(self, extra):
        return cli.build_parser().parse_args(
            [str(self.experiment), "--no-write", "--subset-reason", "test", "--quiet"] + extra
        )

    def _run(self, extra, env, submit_effect):
        patches = [
            mock.patch.object(cli, "find_pdk", return_value=self.pdk),
            mock.patch.object(cli.runner, "ngspice_version", return_value="ngspice-46"),
            mock.patch.object(cli.toolchain_mod, "load_pins", return_value=PINS),
            mock.patch.object(cli.batch_mod, "klt_available", return_value=["klt"]),
            mock.patch.object(cli.batch_mod, "submit", side_effect=submit_effect),
            mock.patch.object(cli.runner, "run_grid", side_effect=AssertionError("ran locally")),
            mock.patch.object(cli, "WORK_DIR", self.root / "work"),
            mock.patch.dict(cli.os.environ, env, clear=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return cli.run(self._args(extra))

    def test_dispatch_host_never_falls_back_to_local_when_submit_fails(self):
        code = self._run([], {"KLT_SIM_BACKEND": "batch"}, batch.BatchError("no capacity"))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        cli.runner.run_grid.assert_not_called()

    def test_dispatch_host_routes_the_grid_through_submit(self):
        def fake_submit(request_path, outdir, requested, klt_cmd="klt"):
            request = json.loads(request_path.read_text())
            self.assertEqual([p["name"] for p in request["corners"]["process"]], ["tt", "ss"])
            self.assertEqual(requested, "")
            return {
                "status": "not_checked",
                "corners": [klt_corner(p, 27, 3.3, measurements={"vout": 1.0},
                                       artifacts=self._art(p)) for p in ("tt", "ss")],
                "environment": {"engine_version": "46", "remote": {
                    "provider": "aws-batch-fleet", "job_id": "j", "runner_compatibility": "match"}},
                "provenance": {"klt_version": "0.6.0",
                               "pdk": {"name": "gf180mcuD", "version": f"open_pdks {PINNED_PDK}"}},
            }, ""

        code = self._run([], {"KLT_SIM_BACKEND": "batch"}, fake_submit)
        self.assertEqual(code, cli.EXIT_OK)

    def _art(self, name):
        d = self.root / "art" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "corner.cir").write_text("*\n")
        (d / "ngspice.log").write_text("fine\n")
        return {"log": str(d / "ngspice.log"), "deck": str(d / "corner.cir"),
                "raw": None, "waveform": None}

    def test_fleet_toolchain_drift_blocks_the_record(self):
        def old_fleet(request_path, outdir, requested, klt_cmd="klt"):
            return {"status": "not_checked",
                    "corners": [klt_corner(p, 27, 3.3, measurements={"vout": 1.0},
                                           artifacts=self._art(p)) for p in ("tt", "ss")],
                    "environment": {"engine_version": "42"},
                    "provenance": {"pdk": {"version": f"open_pdks {PINNED_PDK}"}}}, ""

        self.assertEqual(self._run([], {"KLT_SIM_BACKEND": "batch"}, old_fleet), cli.EXIT_ENVIRONMENT)
        # ... unless the drift is deliberately accepted, in which case it is stamped.
        self.assertEqual(
            cli.run(self._args(["--allow-toolchain-drift"])), cli.EXIT_OK
        )

    def test_explicit_local_backend_runs_the_local_runner(self):
        with self.assertRaisesRegex(AssertionError, "ran locally"):
            self._run(["--backend", "local", "--allow-local-grid"],
                      {"KLT_SIM_BACKEND": "batch"}, AssertionError("no"))
        cli.batch_mod.submit.assert_not_called()

    def test_explicit_local_multipoint_refused_without_override(self):
        code = self._run(["--backend", "local"], {"KLT_SIM_BACKEND": "batch"},
                         AssertionError("no"))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        cli.batch_mod.submit.assert_not_called()

    def test_unexportable_manifest_is_refused_with_a_named_reason_and_runs_nothing(self):
        tb_json = self.experiment / "testbench" / "tb.json"
        manifest = json.loads(tb_json.read_text())
        manifest["analyses"] = ["tran 1n 1u", "setseed 3"]
        tb_json.write_text(json.dumps(manifest))
        code = self._run([], {"KLT_SIM_BACKEND": "batch"}, AssertionError("must not submit"))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)

    def test_backend_flag_defaults_to_auto(self):
        self.assertEqual(cli.build_parser().parse_args(["x"]).backend, "auto")
        self.assertEqual(cli.build_parser().parse_args(["x"]).runner_version_check, "enforce")


if __name__ == "__main__":
    unittest.main()
