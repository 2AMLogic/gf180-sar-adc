#!/usr/bin/env python3
"""Unit tests for the `klt sim` batch exporter (harness/batch.py).

No ngspice, no PDK, no network, no klt: the exporter and the report -> record
conversion are pure functions over dicts, and the CLI routing is exercised with
`klt` and the local runner both mocked.

    python3 -m unittest discover -s sim/tests -p 'test_batch.py' -v
"""

from __future__ import annotations

import contextlib
import hashlib
import io
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

PINNED_PDK = json.loads((SIM_DIR / "toolchain.json").read_text())["open_pdks"]
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

    def test_auto_resolves_the_env_backend_to_an_explicit_name(self):
        """Old klt releases ignore $KLT_SIM_BACKEND and would run locally."""
        self.assertEqual(batch.klt_backend_name("auto", {"KLT_SIM_BACKEND": "batch"}), "batch")
        self.assertEqual(batch.klt_backend_name("remote", {"KLT_SIM_BACKEND": "batch"}), "remote")
        self.assertEqual(batch.klt_backend_name("auto", {}), "")

    def test_klt_flag_is_only_passed_when_explicit(self):
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
        for step in ("setseed 1", "linearize v(out)", "alterparam c=1", "noise v(o) vin dec 10 1 1k"):
            with self.subTest(step=step):
                tb = make_tb(self.root, {"analyses": ["tran 1n 1u", step], "measure": {"m": "v(out)"}})
                with self.assertRaises(batch.NotExportable):
                    batch.check_exportable(tb)

    def test_linearize_and_lets_map_onto_klt_fields(self):
        manifest = {
            "analyses": ["tran 1n 1u", "linearize", "let ph = 2*pi*1e6*time",
                         "let a1 = 2*mean(v(out)*cos(ph))", "let b1 = 2*mean(v(out)*sin(ph))"],
            "measure": {"amp": "sqrt(a1*a1+b1*b1)"},
        }
        tb = make_tb(self.root, manifest)
        plan = batch.check_exportable(tb)
        self.assertTrue(plan.linearize)
        self.assertEqual([n for n, _ in plan.lets], ["a1", "b1"])
        self.assertIn("(2*pi*1e6*time)", plan.lets[0][1])
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan, corners.resolve_corners(["tt"]),
            [27.0], netlist_name="x.spice", timeout_s=60,
        )
        self.assertTrue(request["analysis"]["linearize"])
        names = [m["name"] for m in request["measurements"]]
        self.assertEqual(names, ["a1", "b1", "amp"])
        self.assertIn("expr", request["measurements"][0])

    def test_a_let_over_meas_results_becomes_a_meas_param_card(self):
        manifest = {
            "analyses": ["tran 1n 1u", "meas tran vm FIND v(out) AT=0.5u", "let lsb = vm/1024"],
            "measure": {"m": "lsb"},
        }
        tb = make_tb(self.root, manifest)
        plan = batch.check_exportable(tb)
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan, corners.resolve_corners(["tt"]),
            [27.0], netlist_name="x.spice", timeout_s=60,
        )
        lsb = [m for m in request["measurements"] if m["name"] == "lsb"][0]
        self.assertEqual(lsb["spice"], ".meas tran lsb param='vm/1024'")
        self.assertNotIn("expr", lsb)

    def test_m_aliased_sibling_references_are_rewritten_for_the_runner(self):
        # The local runner aliases each measure entry to an m_<name> vector
        # (sim/harness/runner.py) and manifests reference siblings through
        # that alias; klt's runner names the same vectors unprefixed, so the
        # exported expressions must carry the unprefixed names (regression:
        # device-switch-ron's ron_t_max, batch record 20261123-071924-3703e3a).
        manifest = {
            "analyses": ["op"],
            "measure": {
                "ron_a": "10e-3/abs(i(vd_a))",
                "ron_b": "10e-3/abs(i(vd_b))",
                "ron_max": "max(m_ron_a, m_ron_b)",
                "ron_flat": "m_ron_max/m_ron_a",
            },
        }
        tb = make_tb(self.root, manifest)
        plan = batch.check_exportable(tb)
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan, corners.resolve_corners(["tt"]),
            [27.0], netlist_name="x.spice", timeout_s=60,
        )
        by_name = {m["name"]: m for m in request["measurements"]}
        self.assertEqual(by_name["ron_max"]["expr"], "max(ron_a, ron_b)")
        self.assertEqual(by_name["ron_flat"]["expr"], "ron_max/ron_a")

    def test_unknown_m_references_are_left_alone_not_renamed(self):
        # m_<x> where <x> is not a sibling of this manifest is not an alias
        # reference; renaming it would silently repoint the expression.
        tb = make_tb(self.root, {
            "analyses": ["op"],
            "measure": {"m": "m_stranger + 1", "m_keep": "m_m_keep*2"},
        })
        plan = batch.check_exportable(tb)
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan, corners.resolve_corners(["tt"]),
            [27.0], netlist_name="x.spice", timeout_s=60,
        )
        by_name = {m["name"]: m for m in request["measurements"]}
        self.assertEqual(by_name["m"]["expr"], "m_stranger + 1")
        self.assertEqual(by_name["m_keep"]["expr"], "m_keep*2")

    def test_linearize_on_a_non_tran_analysis_is_refused(self):
        tb = make_tb(self.root, {"analyses": ["op", "linearize"], "measure": {"m": "v(out)"}})
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


STEPS_MANIFEST = {
    "analyses": ["op", "noise v(o) vin dec 10 1 1k", "ac dec 10 1 1k"],
    "measure": {"vn": "x", "gain": "y"},
    "klt_sim": {
        "analysis_steps": [
            {"name": "n", "analysis": {"kind": "noise", "args": "v(o) vin dec 10 1 1k"},
             "measurements": [{"name": "tot", "expr": "onoise_total"}]},
            {"name": "g", "analysis": {"kind": "ac", "args": "dec 10 1 1k"},
             "measurements": [{"name": "av", "expr": "mag(v(o))[0]"}]},
        ],
        "measurements": [
            {"name": "vn", "expr": "n.tot/g.av"},
            {"name": "gain", "expr": "g.av"},
        ],
    },
    # klt_sim_pin_digest over the three keys above. An edit to any of them
    # must re-take this pin -- the guard test below fails naming the new one.
    "klt_sim_pin": "558a08817ad171fabd4680e72595fa0c2715b52cbe73ba53ba37569d36a58631",
}


class KltSimStepsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_klt_sim_block_exports_as_analysis_steps_not_a_refusal(self):
        tb = make_tb(self.root, STEPS_MANIFEST)
        plan = batch.check_exportable(tb)
        self.assertEqual(plan.kind, "steps")
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan, corners.resolve_corners(["tt"]),
            [27.0], netlist_name="body.spice", timeout_s=60,
        )
        self.assertNotIn("analysis", request)
        self.assertEqual([s["name"] for s in request["analysis_steps"]], ["n", "g"])
        self.assertEqual([m["name"] for m in request["measurements"]], ["vn", "gain"])

    def test_a_measure_the_steps_do_not_produce_is_refused(self):
        manifest = json.loads(json.dumps(STEPS_MANIFEST))
        manifest["measure"]["extra"] = "z"
        del manifest["klt_sim_pin"]  # edit re-taken: the pin now covers the edited pair
        manifest["klt_sim_pin"] = batch.klt_sim_pin_digest(make_tb(self.root, manifest))
        with self.assertRaisesRegex(batch.NotExportable, "extra"):
            batch.check_exportable(make_tb(self.root, manifest))

    def test_malformed_klt_sim_block_is_rejected_at_load(self):
        for bad in ({"analysis_steps": []}, {"analysis_steps": [], "measurements": []},
                    {"analysis_steps": [{}], "measurements": {}}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    make_tb(self.root, {**STEPS_MANIFEST, "klt_sim": bad})

    def test_without_the_block_a_noise_line_is_still_refused(self):
        manifest = {k: v for k, v in STEPS_MANIFEST.items() if k != "klt_sim"}
        with self.assertRaises(batch.NotExportable):
            batch.check_exportable(make_tb(self.root, manifest))

    def test_steps_manifest_pin_matches_its_own_content(self):
        tb = make_tb(self.root, {k: v for k, v in STEPS_MANIFEST.items() if k != "klt_sim_pin"})
        self.assertEqual(batch.klt_sim_pin_digest(tb), STEPS_MANIFEST["klt_sim_pin"])

    def test_missing_pin_is_refused_naming_manifest_and_expected_digest(self):
        manifest = {k: v for k, v in STEPS_MANIFEST.items() if k != "klt_sim_pin"}
        tb = make_tb(self.root, manifest)
        with self.assertRaisesRegex(batch.NotExportable, "klt_sim_pin") as ctx:
            batch.check_exportable(tb)
        message = str(ctx.exception)
        self.assertIn(str(tb.directory / "tb.json"), message)
        self.assertIn(STEPS_MANIFEST["klt_sim_pin"], message)

    def test_stale_pin_is_refused_whenever_either_side_edited_alone(self):
        edits = (
            ("analyses", lambda m: m["analyses"].__setitem__(0, "op2")),
            ("measure", lambda m: m["measure"].__setitem__("vn", "x2")),
            ("klt_sim", lambda m: m["klt_sim"]["measurements"][0].__setitem__("expr", "n.tot*2")),
        )
        for field, edit in edits:
            with self.subTest(field=field):
                manifest = json.loads(json.dumps(STEPS_MANIFEST))
                edit(manifest)
                tb = make_tb(self.root, manifest)
                with self.assertRaisesRegex(batch.NotExportable, "stale"):
                    batch.check_exportable(tb)

    def test_key_order_and_whitespace_only_edits_do_not_change_the_digest(self):
        reordered = json.loads(json.dumps(STEPS_MANIFEST, sort_keys=True))
        self.assertEqual(
            batch.klt_sim_pin_digest(make_tb(self.root / "a", STEPS_MANIFEST)),
            batch.klt_sim_pin_digest(make_tb(self.root / "b", reordered)),
        )
        # and the reordered file still exports: same canonical pair, same pin
        plan = batch.check_exportable(make_tb(self.root / "b", reordered))
        self.assertEqual(plan.kind, "steps")

    def test_malformed_pin_is_rejected_at_load(self):
        bad_pins = (
            "", "abc",
            STEPS_MANIFEST["klt_sim_pin"][:-1],                      # 63 chars
            STEPS_MANIFEST["klt_sim_pin"].upper(),                   # not lowercase hex
            "0" * 64 + "0",                                          # 65 chars
        )
        for bad in bad_pins:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    make_tb(self.root, {**STEPS_MANIFEST, "klt_sim_pin": bad})

    def test_a_pin_without_klt_sim_is_carried_but_ignored(self):
        tb = make_tb(self.root, {
            "analyses": ["op"],
            "measure": {"m": "v(out)"},
            "klt_sim_pin": STEPS_MANIFEST["klt_sim_pin"],
        })
        self.assertEqual(tb.klt_sim_pin, STEPS_MANIFEST["klt_sim_pin"])
        self.assertIsNone(tb.klt_sim)
        self.assertEqual(batch.check_exportable(tb).kind, "op")

    def test_every_committed_klt_sim_manifest_carries_a_current_pin(self):
        pinned = 0
        for directory in testbench.discover(SIM_DIR):
            tb = testbench.load(directory)
            if tb.klt_sim is None:
                continue
            pinned += 1
            with self.subTest(manifest=str(directory)):
                self.assertEqual(batch.check_exportable(tb).kind, "steps")
        self.assertGreater(pinned, 0, "no committed manifest carries a klt_sim block")


class ParamExpressibleTests(unittest.TestCase):
    NAMES = {"a", "b"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_arithmetic_over_meas_results(self):
        for expr in ("(b-a)*1e9", "a*1e-3", "abs(a-b)*1e6", "max(a,b)", "1.5e3/a"):
            with self.subTest(expr=expr):
                self.assertTrue(batch.param_expressible(expr, self.NAMES))

    def test_vectors_and_unknown_names_need_expr(self):
        for expr in ("v(out)", "v(out)[0]", "i(vsup)*1e6", "c", "foo(a)", "a'b"):
            with self.subTest(expr=expr):
                self.assertFalse(batch.param_expressible(expr, self.NAMES))
        self.assertFalse(batch.param_expressible("V(a)", {"v", "a"}))

    def test_request_uses_param_cards_where_possible_and_expr_otherwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tb = make_tb(root, TRAN_MANIFEST)
            plan = batch.check_exportable(tb)
            request = batch.build_request(
                tb, make_pdk(root / "pdk"), plan, corners.resolve_corners(["tt"]),
                [27.0], "body.spice", 60,
            )
        by_name = {m["name"]: m for m in request["measurements"]}
        self.assertEqual(by_name["span_ns"]["spice"], ".meas tran span_ns param='(b-a)*1e9'")
        self.assertEqual(by_name["vout_end"], {"name": "vout_end", "expr": "v(out)[0]"})
        self.assertNotIn("amax", by_name)  # read straight off the 'a' card
        self.assertIn("a", by_name)

    CHAINED_MANIFEST = {
        "analyses": ["tran 200p 1.5u", "meas tran pre FIND v(h) AT=1u",
                     "meas tran post FIND v(h) AT=1.5u"],
        # `share` reads `ped_small_mv`, which the manifest declares AFTER it.
        "measure": {
            "ped_mv": "(post-pre)*1e3",
            "ped_small_mv": "(post-pre)*1e2",
            "share": "m_ped_mv/m_ped_small_mv",
            "spread_mv": "max(m_ped_mv, m_ped_small_mv)-min(m_ped_mv, m_ped_small_mv)",
            "v_end": "v(h)[0]",
        },
    }

    def _measurements(self, manifest):
        tb = make_tb(self.root, manifest)
        plan = batch.check_exportable(tb)
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan, corners.resolve_corners(["tt"]),
            [27.0], "body.spice", 60,
        )
        return request["measurements"]

    def test_vector_reads_preserve_node_names_in_both_expression_sources(self):
        measurements = self._measurements({
            "analyses": ["tran 1n 1u", "meas tran sample FIND v(sample) AT=0",
                         "let phase = 2*time", "let first = V(sample)[0] + V(phase)[0]"],
            "measure": {"pre": "sample", "start": "V(sample)[0] + v(m_pre)[0]"},
        })
        by_name = {m["name"]: m for m in measurements}
        self.assertEqual(by_name["first"]["expr"], "V(sample)[0] + V(phase)[0]")
        self.assertEqual(by_name["start"]["expr"], "V(sample)[0] + v(m_pre)[0]")

    def test_bare_indexed_vector_can_share_a_derived_measurement_name(self):
        tb = testbench.load(SIM_DIR / "device-switch-charge-injection")
        tb.measure = {"nhn_f50": "(vpre_n_f50+vpost_n_f50)/2", "start": "nhn_f50[0]"}

        def export():
            member, = batch.build_supply_set(
                tb, make_pdk(self.root / "pdk"), batch.check_exportable(tb),
                corners.resolve_corners(["tt"]), [27.0], [3.3], timeout_s=60,
            )
            return {m["name"]: m for m in member.request["measurements"]}

        by_name = export()
        self.assertEqual(by_name["nhn_f50"]["spice"],
                         ".meas tran nhn_f50 param='(vpre_n_f50+vpost_n_f50)/2'")
        self.assertEqual(by_name["start"]["expr"], "nhn_f50[0]")

        # The sibling really is file-scope, even when used inside an index.
        tb.measure["start"] = "nhn_f50[m_nhn_f50]"
        with self.assertRaisesRegex(batch.NotExportable, "start.*nhn_f50"):
            export()

    def test_analysis_let_reads_the_circuit_before_manifest_aliases_exist(self):
        manifest = {
            "analyses": ["tran 1n 1u", "meas tran sample FIND v(out) AT=0",
                         "let first = m_pre[0]"],
            "measure": {"pre": "sample", "start": "first"},
        }
        by_name = {m["name"]: m for m in self._measurements(manifest)}
        self.assertEqual(by_name["first"]["expr"], "m_pre[0]")

        manifest["analyses"][-1] = "let first = m_pre[sample]"
        with self.assertRaisesRegex(batch.NotExportable, "first.*sample"):
            self._measurements(manifest)

    def test_sibling_references_use_the_exported_name_of_a_direct_alias(self):
        measurements = self._measurements({
            "analyses": ["tran 1n 1u", "meas tran vpre FIND v(out) AT=0",
                         "let first = v(out)[0]"],
            "measure": {"pre": "vpre", "scaled": "2*m_pre",
                        "start": "first", "twice_start": "2*M_START"},
        })
        by_name = {m["name"]: m for m in measurements}
        self.assertNotIn("pre", by_name)
        self.assertEqual(by_name["scaled"]["spice"], ".meas tran scaled param='2*vpre'")
        self.assertEqual(by_name["twice_start"]["expr"], "2*first")

    def test_a_derived_measurement_over_param_cards_is_itself_a_param_card(self):
        """device-switch-charge-injection on the fleet (PR #1005): the spreads
        went out as `expr`s over file-scope `.meas ... param` results, which a
        control-block `let` cannot see, so every point "produced no value"
        (klayout-tools#7659). A chain of file-scope results stays file-scope."""
        measurements = self._measurements(self.CHAINED_MANIFEST)
        by_name = {m["name"]: m for m in measurements}
        for name in ("ped_mv", "ped_small_mv", "share", "spread_mv"):
            with self.subTest(measurement=name):
                self.assertIn("spice", by_name[name], by_name[name])
                self.assertNotIn("expr", by_name[name])
        self.assertEqual(by_name["spread_mv"]["spice"],
                         ".meas tran spread_mv param='max(ped_mv, ped_small_mv)"
                         "-min(ped_mv, ped_small_mv)'")

    def test_a_card_never_reads_a_name_declared_later_in_the_manifest(self):
        """Dependency order, not manifest order: ngspice evaluates the cards
        as written, so a dependent card must follow the cards it reads."""
        measurements = self._measurements(self.CHAINED_MANIFEST)
        plain = [m for m in measurements if "param='" not in m.get("spice", "")]
        seen = {m["name"].lower() for m in plain}  # the analysis's own cards come first
        for entry in measurements:
            if "param='" not in entry.get("spice", ""):
                continue  # the analysis's own FIND/MAX cards read vectors, not results
            expr = entry["spice"].split("param='", 1)[1].rstrip("'")
            refs = {i.lower() for i in batch._IDENT_RE.findall(batch._NUMBER_RE.sub("0", expr))}
            refs -= batch._PARAM_FUNCS
            self.assertFalse(refs - seen, f"{entry['name']} reads {refs - seen} too early")
            seen.add(entry["name"].lower())

    def test_an_expr_over_a_file_scope_result_is_refused_before_the_fleet_round_trip(self):
        """An `expr` cannot read a `.meas` result on any backend, so a chain
        that mixes the two scopes is refused here, naming both ends, instead
        of coming back from the fleet as 45 error points."""
        tb = make_tb(self.root, {
            "analyses": ["tran 1n 1u", "meas tran a MAX v(out)"],
            "measure": {"x": "a*2", "y": "v(out)[0]+m_x", "z": "v(y)*2"},
        })
        with self.assertRaisesRegex(batch.NotExportable, "y.*x") as ctx:
            batch.build_request(
                tb, make_pdk(self.root / "pdk"), batch.check_exportable(tb),
                corners.resolve_corners(["tt"]), [27.0], "body.spice", 60,
            )
        # `y` is an expr, so `z` reading it is the allowed expr -> expr chain.
        self.assertNotIn("'z'", str(ctx.exception))

    def test_committed_charge_injection_spreads_are_param_cards(self):
        tb = testbench.load(SIM_DIR / "device-switch-charge-injection")
        plan = batch.check_exportable(tb)
        request = batch.build_request(
            tb, make_pdk(self.root / "pdk"), plan,
            corners.resolve_corners(["tt"]), [27.0], "body.spice", 60,
        )
        by_name = {m["name"]: m for m in request["measurements"]}
        self.assertEqual(len(by_name), len(plan.meas_cards) + len(tb.measure))
        for name in tb.measure:
            with self.subTest(measurement=name):
                self.assertIn("param='", by_name[name]["spice"], by_name[name])

    def test_every_committed_corner_exportable_manifest_builds_a_request(self):
        """No committed manifest trips the mixed-scope refusal."""
        built = 0
        for directory in testbench.discover(SIM_DIR):
            tb = testbench.load(directory)
            try:
                plan = batch.check_exportable(tb)
                batch._fragment_text(tb)
            except batch.NotExportable:
                continue  # a deck the corner engine cannot express: refused, as before
            if plan.steps is not None:
                continue
            with self.subTest(manifest=str(directory)):
                batch.build_request(
                    tb, make_pdk(self.root / "pdk" / directory.name), plan,
                    corners.resolve_corners(["tt"]), [27.0], "body.spice", 60,
                )
            built += 1
        self.assertGreater(built, 20)


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
            self.tb, self.pdk, self.plan, cl, [-40.0, 27.0, 125.0], **args
        )

    def _set(self, supplies=(2.97, 3.3, 3.63), **kw):
        return batch.build_supply_set(
            self.tb, self.pdk, self.plan, corners.resolve_corners(["mos"]),
            [-40.0, 27.0, 125.0], list(supplies), timeout_s=900, **kw
        )

    def test_grid_axes_match_the_local_grid(self):
        request = self._request()
        process = request["corners"]["process"]
        self.assertEqual([p["name"] for p in process], ["tt", "ff", "ss", "fs", "sf"])
        self.assertEqual(process[1]["sections"], list(corners.CORNERS["ff"].sections))
        self.assertEqual(request["corners"]["temperature_c"], [-40.0, 27.0, 125.0])

    def test_one_request_per_supply_and_no_supply_v_axis(self):
        """Issue #505: vdd_val is a .param; klt's supply_v can only alter a source."""
        members = self._set()
        self.assertEqual([m.supply_v for m in members], [2.97, 3.3, 3.63])
        stems = [m.stem for m in members]
        self.assertEqual(len(set(stems)), 3)
        for member in members:
            with self.subTest(supply=member.supply_v):
                self.assertNotIn("supply_v", member.request["corners"])
                self.assertNotIn("supply_v", json.dumps(member.request))
                self.assertEqual(member.request["netlist"], member.body_name)
                self.assertNotIn(".", member.stem)  # --batch-set names out dirs by stem
        # 3 requests x (5 process x 3 temperatures) == the local factorial grid.
        self.assertEqual(
            sum(len(m.request["corners"]["process"]) * len(m.request["corners"]["temperature_c"])
                for m in members),
            len(corners.build_grid(corners.resolve_corners(["mos"]), [-40, 27, 125], [2.97, 3.3, 3.63])),
        )

    def test_each_body_binds_vdd_val_to_its_own_supply(self):
        """Every supply-derived quantity (rails, clocks, vref, thresholds) reads the .param."""
        for member in self._set():
            with self.subTest(supply=member.supply_v):
                params = [ln for ln in member.body.splitlines() if ln.startswith(".param vdd_val=")]
                self.assertEqual(params, [f".param vdd_val={member.supply_v!r}"])
                self.assertIn(".param vdd_nom=3.3", member.body)
                self.assertIn("v1 out 0 dc {vdd_val}", member.body)

    def test_single_supply_is_one_request_and_repeats_collapse(self):
        self.assertEqual(len(self._set(supplies=[3.3])), 1)
        self.assertEqual([m.supply_v for m in self._set(supplies=[3.3, 3.3000000001])], [3.3])

    def test_set_members_share_everything_but_the_body(self):
        a, b, _ = self._set(num_threads=1, save_vectors=["v(out)"], batch={"runner_version_check": "warn"})
        strip = lambda r: {k: v for k, v in r.items() if k != "netlist"}  # noqa: E731
        self.assertEqual(strip(a.request), strip(b.request))
        self.assertEqual(a.request["options"]["save_mode"], "netlist")
        self.assertEqual(a.request["batch"], {"runner_version_check": "warn"})

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

    def test_batch_block_is_absent_when_every_knob_is_default(self):
        """No ``batch`` key at all, so klt resolves every setting from the fleet."""
        self.assertIsNone(batch.batch_block())
        self.assertNotIn("batch", self._request(batch=batch.batch_block()))

    def test_batch_block_carries_only_the_knobs_that_were_asked_for(self):
        self.assertEqual(batch.batch_block(max_units_per_job=5),
                         {"max_units_per_job": 5})
        self.assertEqual(batch.batch_block(max_concurrent_jobs=3),
                         {"max_concurrent_jobs": 3})
        self.assertEqual(
            batch.batch_block("warn", max_units_per_job=5, max_concurrent_jobs=3),
            {"runner_version_check": "warn",
             "max_units_per_job": 5, "max_concurrent_jobs": 3},
        )

    def test_job_split_knobs_reach_every_member_of_the_supply_set(self):
        """The ceiling knob has to be on each per-supply request, not the set."""
        block = batch.batch_block(max_units_per_job=5, max_concurrent_jobs=3)
        for member in self._set(batch=block):
            with self.subTest(supply=member.supply_v):
                self.assertEqual(member.request["batch"], block)

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
    """A klt report corner. ``vdd`` only labels it: the per-supply requests carry
    no supply_v axis, so klt reports ``supply_v: {}`` (issue #505)."""
    return {
        "corner_id": f"{process}/{temp:g}C",
        "process": process,
        "supply_v": {},
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


def outcomes(corner_list, supply=3.3):
    """Wrap one supply's klt corners as the per-supply outcome list."""
    return [batch.SupplyOutcome(supply, f"vdd-{supply}.json", report={"corners": corner_list})]


class ThreeSupplyMatchingTests(unittest.TestCase):
    """Issue #505: results map back by (process, temp, the request's supply)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tb = make_tb(self.root, {
            "analyses": ["tran 5n 1u", "meas tran a MAX v(out)"],
            "measure": {"amax": "a"},
        })
        self.plan = batch.check_exportable(self.tb)
        self.supplies = corners.supply_points(3.3, 0.1)
        self.points = corners.build_grid(corners.resolve_corners(["tt", "ss"]), [27.0], self.supplies)

    def _art(self, tag):
        d = self.root / "art" / tag
        d.mkdir(parents=True, exist_ok=True)
        (d / "ngspice.log").write_text("ok\n")
        (d / "corner.cir").write_text(f"* {tag}\n")
        return {"log": str(d / "ngspice.log"), "deck": str(d / "corner.cir"), "raw": None,
                "waveform": None}

    def _supply_outcome(self, vdd, status="pass"):
        # Value = the supply, so a mis-mapping is visible in the result.
        return batch.SupplyOutcome(vdd, f"vdd-{vdd}.json", report={"status": status, "corners": [
            klt_corner(p, 27, vdd, measurements={"a": vdd}, artifacts=self._art(f"{p}{vdd}"))
            for p in ("ss", "tt")
        ]})

    def _convert(self, outs):
        return batch.to_point_results(
            self.tb, self.plan, self.points, outs, self.root / "w", self.root / "l", 60
        )

    def test_each_point_reads_the_report_of_its_own_supply(self):
        # Reports arrive in a different order than the grid.
        res = self._convert([self._supply_outcome(v) for v in reversed(self.supplies)])
        self.assertEqual(len(res), 6)
        for r in res:
            with self.subTest(point=r.point.corner_id):
                self.assertEqual(r.status, "ok")
                self.assertEqual(r.measurements["amax"], r.point.vdd)
                self.assertIn(f"{r.point.corner.name}{r.point.vdd}",
                              (self.root / "w" / f"{r.point.corner_id}.spice").read_text())

    def test_nominal_supply_matches_despite_float_noise(self):
        outs = [self._supply_outcome(v) for v in self.supplies]
        outs[1] = self._supply_outcome(3.3000000000001)
        self.assertEqual([r.status for r in self._convert(outs)], ["ok"] * 6)

    def test_a_supply_whose_request_failed_is_error_points_not_dropped_or_ok(self):
        outs = [self._supply_outcome(v) for v in self.supplies]
        outs[2] = batch.SupplyOutcome(self.supplies[2], "vdd2.json", error="capacity: refused")
        res = self._convert(outs)
        self.assertEqual(len(res), 6)
        by_vdd = {}
        for r in res:
            by_vdd.setdefault(r.point.vdd, set()).add(r.status)
        self.assertEqual(by_vdd[self.supplies[0]], {"ok"})
        self.assertEqual(by_vdd[self.supplies[2]], {"error"})
        failed = [r for r in res if r.status == "error"]
        self.assertTrue(all("capacity: refused" in r.message for r in failed))
        self.assertTrue(all("vdd2.json" in r.message for r in failed))

    def test_a_failed_unit_inside_one_request_is_an_error_point(self):
        outs = [self._supply_outcome(v) for v in self.supplies]
        diag = {"severity": "error", "code": "ngspice_failed", "message": "exit 1"}
        outs[0].report["corners"][0] = klt_corner("ss", 27, self.supplies[0], status="error",
                                                  diagnostics=[diag])
        res = self._convert(outs)
        bad = [r for r in res if r.status != "ok"]
        self.assertEqual([(r.point.corner.name, r.point.vdd, r.status) for r in bad],
                         [("ss", self.supplies[0], "error")])


class SubmitSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        tb = make_tb(self.root, {"analyses": ["op"], "measure": {"vout": "v(out)"}})
        self.members = batch.build_supply_set(
            tb, make_pdk(self.root / "pdk"), batch.check_exportable(tb),
            corners.resolve_corners(["tt"]), [27.0], [2.97, 3.3, 3.63], timeout_s=60,
        )

    def _write_report(self, stem, status="pass"):
        path = self.root / "out" / stem / "report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"status": status, "corners": []}))
        return str(path)

    def _envelope(self, entries):
        return json.dumps({"schema_version": 1, "status": "error", "requests": entries})

    def _run(self, stdout, returncode=0, backend="batch"):
        proc = mock.Mock(stdout=stdout, stderr="", returncode=returncode)
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run", return_value=proc) as run, \
                mock.patch.object(runner, "run_grid", side_effect=AssertionError("local")):
            got = batch.submit_set(self.members, self.root, self.root / "out", backend)
        return got, run.call_args.args[0]

    def test_one_batch_set_invocation_carries_every_supply_request(self):
        entries = [{"index": i, "status": "pass", "report": self._write_report(m.stem),
                    "error": None, "job_ids": [f"j{i}"]} for i, m in enumerate(self.members)]
        (outs, envelope), cmd = self._run(self._envelope(entries))
        self.assertEqual(cmd[:3], ["klt", "sim", "--batch-set"])
        self.assertEqual(cmd[3:6], [str(self.root / m.request_name) for m in self.members])
        self.assertNotIn("--backend", cmd)  # --batch-set is always batch
        self.assertEqual([o.supply_v for o in outs], [2.97, 3.3, 3.63])
        self.assertTrue(all(o.report is not None and o.error is None for o in outs))
        self.assertEqual(envelope["schema_version"], 1)

    def test_partial_set_failure_is_an_error_outcome_and_never_ok(self):
        entries = [
            {"index": 0, "status": "pass", "report": self._write_report(self.members[0].stem),
             "error": None},
            {"index": 1, "status": "error", "report": None,
             "error": {"message": "fleet at capacity", "code": "capacity"}},
            {"index": 2, "status": "pass", "report": self._write_report(self.members[2].stem),
             "error": None},
        ]
        (outs, _), _ = self._run(self._envelope(entries), returncode=4)
        self.assertIsNone(outs[1].report)
        self.assertEqual(outs[1].error, "capacity: fleet at capacity")
        self.assertEqual(batch._set_status(outs), "error")
        execution = batch.execution_summary(outs, self.members, "batch")
        self.assertEqual(execution["klt_status"], "error")
        self.assertEqual(execution["requests"][1]["klt_status"], "error")
        self.assertIn("capacity", execution["requests"][1]["error"])

    def test_a_set_with_no_report_at_all_raises_and_runs_nothing_locally(self):
        entries = [{"index": i, "status": "error", "report": None,
                    "error": {"message": "rejected", "code": None}} for i in range(3)]
        with self.assertRaisesRegex(batch.BatchError, "rejected"):
            self._run(self._envelope(entries), returncode=4)
        with self.assertRaisesRegex(batch.BatchError, "no set report"):
            self._run("", returncode=1)

    def test_remote_backend_submits_each_request_explicitly(self):
        with mock.patch.object(batch, "submit", side_effect=[
            ({"status": "pass", "corners": []}, ""), batch.BatchError("boom"),
            ({"status": "pass", "corners": []}, ""),
        ]) as sub:
            outs, envelope = batch.submit_set(self.members, self.root, self.root / "out", "remote")
        self.assertIsNone(envelope)
        self.assertEqual([c.args[2] for c in sub.call_args_list], ["remote"] * 3)
        self.assertEqual(outs[1].error, "boom")

    def test_in_flight_and_capacity_retries_bound_what_the_set_occupies(self):
        entries = [{"index": i, "status": "pass", "report": self._write_report(m.stem),
                    "error": None} for i, m in enumerate(self.members)]
        proc = mock.Mock(stdout=self._envelope(entries), stderr="", returncode=0)
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run", return_value=proc) as run, \
                mock.patch.object(runner, "run_grid", side_effect=AssertionError("local")):
            batch.submit_set(self.members, self.root, self.root / "out", "batch",
                             max_in_flight=1, capacity_retries=2)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[-4:], ["--max-in-flight", "1", "--capacity-retries", "2"])

    def test_capacity_retries_is_only_passed_when_asked_for(self):
        entries = [{"index": i, "status": "pass", "report": self._write_report(m.stem),
                    "error": None} for i, m in enumerate(self.members)]
        _, cmd = self._run(self._envelope(entries))
        self.assertNotIn("--capacity-retries", cmd)

    def test_capacity_retries_rides_on_the_batch_set_invocation(self):
        entries = [{"index": i, "status": "pass", "report": self._write_report(m.stem),
                    "error": None} for i, m in enumerate(self.members)]
        proc = mock.Mock(stdout=self._envelope(entries), stderr="", returncode=0)
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run", return_value=proc) as run, \
                mock.patch.object(runner, "run_grid", side_effect=AssertionError("local")):
            batch.submit_set(self.members, self.root, self.root / "out", "batch",
                             capacity_retries=2)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[-2:], ["--capacity-retries", "2"])
        self.assertIn("--wait-for-capacity", cmd)

    def test_set_refuses_an_implicit_backend(self):
        with self.assertRaises(batch.BatchError):
            batch.submit_set(self.members, self.root, self.root / "out", "")


#: A manifest the corner engine cannot express (a seeded control-script
#: loop, as sim/device-mismatch-mc carries) that opts into deck transport.
DECK_MANIFEST = {
    "analyses": ["setseed 20260731", "let n = 0", "dowhile n < 3", "  reset", "  op",
                 "  let n = n + 1", "end"],
    "measure": {"n": "n", "vout_mv": "v(out)[0]*1e3"},
    "klt_decks": True,
}


def deck_unit(outdir: Path, unit_id: str, deck_text: str, stdout: str, stderr: str = "",
              status: str = "pass", exit_code=0, deck_sha256: str | None = None,
              inputs: dict | None = None, timed_out: bool = False):
    """Write one deck-transport unit the way klt collects it -- streams, the
    worker's ``unit.json`` (when ``inputs`` is given: staged name -> sha256)
    -- and return its ``units[]`` entry."""
    unit_dir = outdir / unit_id
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / "stdout.bin").write_text(stdout)
    (unit_dir / "stderr.bin").write_text(stderr)
    digest = deck_sha256 or hashlib.sha256(deck_text.encode()).hexdigest()
    if inputs is not None:
        (unit_dir / "unit.json").write_text(json.dumps({
            "record_version": 1,
            "key": {"deck_sha256": digest, "inputs": inputs},
        }))
    return {
        "id": unit_id, "status": status, "exit_code": exit_code, "timed_out": timed_out,
        "duration_s": 1.25, "engine_version": "46", "deck": f"{unit_id}.spice",
        "deck_sha256": digest,
        "stdout": f"{unit_id}/stdout.bin", "stderr": f"{unit_id}/stderr.bin",
        "outputs": [], "missing_outputs": [], "diagnostics": [],
    }


def deck_report(units, engine_version="46", remote=None):
    report = {
        "schema_version": 3, "mode": "decks", "status": "pass", "backend": "batch",
        "engine": "ngspice", "unit_count": len(units), "passed": len(units),
        "errored": 0, "timed_out": 0,
        "units": units,
        "environment": {"engine": "ngspice", "engine_version": engine_version,
                        "klt_version": "0.9.3.dev1"},
    }
    if remote is not None:
        report["environment"]["remote"] = remote
    return report


FLEET_JOB = {"provider": "aws-batch-fleet", "job_id": "klt-sim-deckjob01",
             "instance_type": "m7i.4xlarge", "availability_zone": "us-east-1a",
             "lifecycle": "spot", "state": "done",
             "runner_klt_version": "0.9.0", "client_klt_version": "0.9.3.dev1",
             "runner_compatibility": "match"}


class DeckTransportTests(unittest.TestCase):
    """``klt_decks``: the grid as a ``klt sim`` deck-list request.

    The corner engine cannot express a ``setseed`` loop, an ``alterparam`` +
    ``reset`` between analyses or a ``.param`` the harness rebinds per point.
    Deck transport does not re-express them: each PVT point's deck is the one
    ``runner.compose_deck`` renders for the local runner, run verbatim off
    host, with its model files staged beside it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk = make_pdk(self.root / "pdk")
        # The reference structure of the real gf180mcu deck: the corner
        # library pulls device sections out of a second file by a relative,
        # quoted name, and the capacitor sections out of a third.
        ng = self.pdk.ngspice_dir
        (ng / "sm141064.ngspice").write_text(
            ".lib typical\n.lib 'sm141064.spice' nfet_03v3_t\n.endl typical\n"
            ".lib mimcap_typical\n.lib sm141064_mim.spice cap_mim_new\n.endl mimcap_typical\n")
        (ng / "sm141064.spice").write_text(
            ".include smbb000149.spice\n.lib nfet_03v3_t\n.endl nfet_03v3_t\n")
        (ng / "sm141064_mim.spice").write_text("* mim\n")
        (ng / "smbb000149.spice").write_text("* bjt\n")
        self.tb = make_tb(self.root, DECK_MANIFEST)
        self.points = corners.build_grid(corners.resolve_corners(["tt", "ss"]), [-40.0], [3.3])
        self.work = self.root / "work"
        self.logs = self.root / "logs"

    def _build(self, **kw):
        kw.setdefault("timeout_s", 60)
        return batch.build_deck_request(self.tb, self.pdk, self.points, **kw)

    def _local_deck(self, point):
        return runner.compose_deck(self.tb, self.pdk, point)

    def test_the_decks_flag_is_a_boolean_exclusive_with_klt_sim(self):
        self.assertFalse(make_tb(self.root, {"analyses": ["op"], "measure": {"m": "v(out)"}}).klt_decks)
        for bad in ("true", 1, None, "decks"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "klt_decks"):
                make_tb(self.root, {"analyses": ["op"], "measure": {"m": "v(out)"}, "klt_decks": bad})
        with self.assertRaisesRegex(ValueError, "klt_sim"):
            make_tb(self.root, {**STEPS_MANIFEST, "klt_decks": True})

    def test_a_deck_request_is_one_local_deck_per_point(self):
        build = self._build()
        request = build.request
        self.assertEqual([d["id"] for d in request["decks"]], [p.corner_id for p in self.points])
        for banned in ("netlist", "corners", "analysis", "analysis_steps", "measurements",
                       "monte_carlo", "exclude"):
            self.assertNotIn(banned, request)
        self.assertEqual(request["engine"], "ngspice")
        self.assertEqual(request["models"], {"pdk": "gf180mcuD"})  # image selection only
        self.assertEqual(request["options"], {"timeout_s": 60})
        for entry in request["decks"]:
            self.assertEqual(entry["deck"], f"{entry['id']}.spice")
            self.assertEqual(entry["timeout_s"], 60)
        self.assertEqual(sorted(build.decks), sorted(p.corner_id for p in self.points))

    def test_each_deck_is_the_local_runners_deck_with_staged_file_refs(self):
        """Only the spelling of the three file references differs from the
        deck ``ngspice -b`` would have read on this host."""
        build = self._build()
        for point in self.points:
            with self.subTest(corner=point.corner_id):
                expected = (
                    self._local_deck(point)
                    .replace(f'"{self.pdk.design_include}"', '"pdk/design.ngspice"')
                    .replace(f'"{self.pdk.model_lib}"', '"pdk/sm141064.ngspice"')
                    .replace(f'.include "{self.tb.netlist}"', '.include "tb.spice"')
                )
                self.assertEqual(build.decks[point.corner_id], expected)
                deck = build.decks[point.corner_id]
                self.assertIn(f"pdk=gf180mcuD@{PINNED_PDK}", deck)      # revision named in the deck
                self.assertIn(f".temp {point.temp_c!r}", deck)          # the point's own PVT
                self.assertIn("setseed 20260731", deck)                  # the control script verbatim
                for path in (str(self.pdk.path), str(self.root), "$PDK_ROOT"):
                    self.assertNotIn(path, deck)

    def test_thread_and_save_flags_reach_the_deck(self):
        plain = self._build().decks[self.points[0].corner_id]
        tuned = self._build(num_threads=1).decks[self.points[0].corner_id]
        self.assertNotIn("set num_threads", plain)
        self.assertIn("set num_threads=1", tuned)

    def test_every_input_the_deck_reads_is_staged_and_listed(self):
        build = self._build()
        staged = {name: path for name, path in build.staged.items()}
        self.assertEqual(
            sorted(staged),
            sorted(["tb.spice", "pdk/design.ngspice", "pdk/sm141064.ngspice",
                    "pdk/sm141064.spice", "pdk/sm141064_mim.spice", "pdk/smbb000149.spice"]),
        )
        self.assertEqual(staged["tb.spice"], self.tb.netlist)
        self.assertEqual(staged["pdk/design.ngspice"], self.pdk.design_include)
        self.assertEqual(staged["pdk/sm141064.ngspice"], Path(self.pdk.model_lib))
        inputs = sorted(i["name"] for i in build.request["decks"][0]["inputs"])
        self.assertEqual(inputs, sorted(staged))
        for entry in build.request["decks"]:
            self.assertEqual(sorted(i["name"] for i in entry["inputs"]), inputs)

    def test_the_model_closure_is_followed_from_the_pdk_not_listed_by_name(self):
        ng = self.pdk.ngspice_dir
        (ng / "sm141064.ngspice").write_text(
            (ng / "sm141064.ngspice").read_text()
            + "* a commented reference is not one: .include 'never.spice'\n"
            "+ a continuation line is not a card either\n")
        (ng / "sm141064.spice").write_text(
            (ng / "sm141064.spice").read_text() + '.inc "nested/deep.spice"\n')
        (ng / "nested").mkdir()
        (ng / "nested" / "deep.spice").write_text("* reached through a quoted .inc\n")
        for decoy in ("sm141064_mim.ngspice", "never.spice", "unreferenced.spice"):
            (ng / decoy).write_text("* must not be staged\n")
        build = self._build()
        self.assertEqual(
            sorted(n for n in build.staged if n.startswith("pdk/")),
            ["pdk/design.ngspice", "pdk/nested/deep.spice", "pdk/sm141064.ngspice",
             "pdk/sm141064.spice", "pdk/sm141064_mim.spice", "pdk/smbb000149.spice"],
        )

    def test_a_model_reference_that_leaves_the_pdk_directory_is_refused(self):
        (self.pdk.ngspice_dir / "sm141064.ngspice").write_text(
            ".lib '../../outside.spice' typical\n")
        with self.assertRaisesRegex(batch.BatchError, "outside.spice"):
            self._build()

    def test_a_model_reference_that_resolves_nowhere_is_refused(self):
        (self.pdk.ngspice_dir / "sm141064.spice").write_text(
            (self.pdk.ngspice_dir / "sm141064.spice").read_text()
            + ".include 'missing_model.spice'\n")
        with self.assertRaisesRegex(batch.BatchError, "missing_model.spice"):
            self._build()

    def test_writing_the_request_lays_out_the_staging_tree(self):
        build = self._build()
        directory = self.work / "klt-decks"
        path = batch.write_deck_request(build, directory)
        self.assertEqual(path, directory / "decks.json")
        written = json.loads(path.read_text())
        self.assertEqual(written, build.request)
        for point in self.points:
            self.assertEqual((directory / f"{point.corner_id}.spice").read_text(),
                             build.decks[point.corner_id])
        for name, source in build.staged.items():
            self.assertEqual((directory / name).read_bytes(), source.read_bytes(), name)
        self.assertEqual(build.request_sha256, batch._sha256(batch.request_text(build.request)))

    def test_submit_calls_klt_sim_once_with_an_explicit_offhost_backend(self):
        directory = self.work / "klt-decks"
        path = batch.write_deck_request(self._build(batch={"max_units_per_job": 5}), directory)
        report = deck_report([deck_unit(self.root / "out", "x", "d", "m_n = 3\n")])
        proc = mock.Mock(stdout=json.dumps(report), stderr="", returncode=4)
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run", return_value=proc) as run:
            got = batch.submit_decks(path, self.root / "out", "batch")
        self.assertEqual(got, report)  # exit 4 still carries every unit: gate on the payload
        self.assertEqual(run.call_args.args[0], [
            "klt", "sim", str(path), "--outdir", str(self.root / "out"), "--format", "json",
            "--wait-for-capacity", str(batch.CAPACITY_WAIT_S), "--backend", "batch",
        ])
        self.assertEqual(json.loads(path.read_text())["batch"], {"max_units_per_job": 5})

    def test_submit_decks_refuses_an_implicit_backend_and_a_corner_report(self):
        path = batch.write_deck_request(self._build(), self.work / "klt-decks")
        with self.assertRaises(batch.BatchError):
            batch.submit_decks(path, self.root / "out", "")
        corner = mock.Mock(stdout=json.dumps({"corners": []}), stderr="", returncode=0)
        nothing = mock.Mock(stdout="", stderr="klt: batch_no_capacity", returncode=1)
        for proc in (corner, nothing):
            with self.subTest(stdout=proc.stdout), \
                    mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                    mock.patch.object(batch.subprocess, "run", return_value=proc), \
                    self.assertRaisesRegex(batch.BatchError, "nothing was simulated locally"):
                batch.submit_decks(path, self.root / "out", "batch")

    def _deck_results(self, build, units, timeout=60, outdir=None):
        report = deck_report(units)
        return batch.deck_results(self.tb, self.points, build, report,
                                  outdir or self.root / "out", self.logs, timeout), report

    def _unit(self, point, stdout, **kw):
        """A collected unit for ``point``; ``record`` True/False/dict sets the
        worker's ``unit.json`` (the true hashes, none, or a given map)."""
        build = kw.pop("build", None) or self._build()
        record = kw.pop("record", True)
        if record is True:
            kw["inputs"] = self._record(build)
        elif record is False:
            kw["inputs"] = None
        else:
            kw["inputs"] = record
        return deck_unit(self.root / "out", point.corner_id, build.decks[point.corner_id], stdout, **kw)

    @staticmethod
    def _record(build):
        return {name: batch._sha256_raw(path.read_bytes()) for name, path in build.staged.items()}

    def test_a_passing_unit_scores_from_its_streams_like_a_local_run(self):
        """stdout and stderr are concatenated exactly as ``runner.run_point``
        does, then scored by the same code."""
        build = self._build()
        tt, ss = self.points
        units = [
            self._unit(tt, "m_n = 3.0000000000e+00\n", stderr="m_vout_mv = 1.2345678901e+03\n",
                       build=build),
            self._unit(ss, "m_n = 3\nm_vout_mv = 1.1\n", build=build),
        ]
        results, _report = self._deck_results(build, units)
        self.assertEqual([r.status for r in results], ["ok", "ok"])
        self.assertEqual(results[0].measurements, {"n": 3.0, "vout_mv": 1234.5678901})
        self.assertEqual(results[0].seconds, 1.25)
        self.assertEqual(results[0].deck, "tt_-40c_3.30v.spice")
        log = self.logs / "tt_-40c_3.30v.log"
        self.assertEqual(results[0].log, log.name)
        self.assertEqual(log.read_text(), "m_n = 3.0000000000e+00\n\nm_vout_mv = 1.2345678901e+03\n")

    def test_deck_and_local_scoring_agree_on_the_same_transcript(self):
        build = self._build()
        transcript = ("No compatibility mode selected!\nm_n = 3.0\nm_vout_mv = 1.5\n"
                      "Error: measure something : out of interval\n")
        unit = self._unit(self.points[0], transcript, build=build, exit_code=1, status="error")
        remote = self._deck_results(build, [unit])[0][0]
        proc = mock.Mock(stdout=transcript, stderr="", returncode=1)
        with mock.patch.object(runner.subprocess, "run", return_value=proc):
            local = runner.run_point(self.tb, self.pdk, self.points[0], self.root / "w", timeout_s=60)
        for attr in ("status", "measurements", "missing", "message", "compat_note"):
            self.assertEqual(getattr(remote, attr), getattr(local, attr), attr)

    def test_a_timed_out_unit_is_an_error_point_stating_the_budget(self):
        build = self._build()
        unit = self._unit(self.points[0], "partial transcript\n", build=build, status="timeout",
                          timed_out=True, exit_code=None)
        results = self._deck_results(build, [unit])[0]
        self.assertEqual(results[0].status, "error")
        self.assertEqual(results[0].message, "ngspice timed out after 60s")
        log = (self.logs / "tt_-40c_3.30v.log").read_text()
        self.assertTrue(log.startswith("TIMEOUT after 60s\n"))
        self.assertIn("partial transcript", log)

    def test_a_point_klt_reported_no_unit_for_is_an_error_not_dropped(self):
        results = self._deck_results(self._build(), [])[0]
        self.assertEqual([r.status for r in results], ["error", "error"])
        self.assertIn("no result", results[0].message)
        self.assertTrue((self.logs / results[0].log).is_file())

    def test_a_unit_that_ran_a_different_deck_is_an_error_not_a_measurement(self):
        build = self._build()
        unit = self._unit(self.points[0], "m_n = 3\nm_vout_mv = 1.5\n", build=build,
                          deck_sha256="f" * 64)
        results = self._deck_results(build, [unit])[0]
        self.assertEqual(results[0].status, "error")
        self.assertEqual(results[0].measurements, {})
        self.assertIn("f" * 64, results[0].message)
        self.assertIn(batch._sha256(build.decks[self.points[0].corner_id]), results[0].message)

    def test_a_unit_whose_worker_record_names_other_include_bytes_is_an_error(self):
        build = self._build()
        point = self.points[0]
        good = self._record(build)
        unit = self._unit(point, "m_n = 3\nm_vout_mv = 1.5\n", build=build,
                          record={**good, "pdk/sm141064.ngspice": "e" * 64})
        results = self._deck_results(build, [unit])[0]
        self.assertEqual(results[0].status, "error")
        self.assertIn("pdk/sm141064.ngspice", results[0].message)

    def test_a_unit_with_no_transcript_is_an_error_naming_the_diagnostic(self):
        build = self._build()
        point = self.points[0]
        unit = self._unit(point, "never read", build=build, status="error", exit_code=None)
        (self.root / "out" / point.corner_id / "stdout.bin").unlink()
        unit["diagnostics"] = [{"severity": "error", "code": "engine_not_found",
                                "message": "ngspice: not found"}]
        results = self._deck_results(build, [unit])[0]
        self.assertEqual(results[0].status, "error")
        self.assertIn("engine_not_found", results[0].message)
        self.assertIn("no transcript", results[0].message)

    def test_a_truncated_analysis_is_failed_even_if_every_value_parsed(self):
        build = self._build()
        unit = self._unit(self.points[0], "m_n = 3\nm_vout_mv = 1.5\n"
                          "doAnalyses: TRAN:  Timestep too small; time = 1.4e-06\n"
                          "tran simulation(s) aborted\n", build=build)
        results = self._deck_results(build, [unit])[0]
        self.assertEqual(results[0].status, "failed")
        self.assertIn("truncated data", results[0].message)

    def test_a_unit_that_never_launched_the_engine_is_an_error(self):
        build = self._build()
        unit = self._unit(self.points[0], "", build=build, status="error", exit_code=None)
        results = self._deck_results(build, [unit])[0]
        self.assertEqual(results[0].status, "error")

    def test_execution_summary_names_the_job_the_staged_models_and_the_engine(self):
        build = self._build()
        units = [self._unit(p, "m_n = 3\nm_vout_mv = 1.5\n", build=build) for p in self.points]
        results, klt_report = self._deck_results(build, units)
        klt_report["environment"]["remote"] = dict(FLEET_JOB)
        execution = batch.deck_execution_summary(
            build, klt_report, self.root / "out", self.pdk, "batch")
        self.assertEqual(execution["transport"], "decks")
        self.assertEqual(execution["backend"], "aws-batch-fleet")
        self.assertEqual(execution["engine_version"], "46")
        self.assertEqual(execution["pdk"]["version"], f"open_pdks {PINNED_PDK}")
        staged = {s["name"]: s["sha256"] for s in execution["staged_models"]}
        self.assertEqual(staged["pdk/design.ngspice"],
                         batch._sha256_raw(self.pdk.design_include.read_bytes()))
        self.assertEqual(execution["units"], {
            "decks": 2, "reported": 2, "with_transcript": 2, "deck_sha256_match": 2,
            "worker_record": 2, "worker_record_match": 2})
        self.assertEqual([b["job_id"] for b in batch.fleet_blocks(execution["remote"])],
                         ["klt-sim-deckjob01"])
        self.assertEqual(batch.ngspice_label(klt_report),
                         "ngspice-46 (run by aws-batch-fleet, job klt-sim-deckjob01)")
        record = report_mod_record(self.tb, self.pdk, self.points, results, execution,
                                   ngspice=batch.ngspice_label(klt_report))
        md = report.render_record(record, "exp")
        self.assertIn("deck transport", md)
        self.assertIn("klt-sim-deckjob01", md)
        self.assertIn(f"`open_pdks {PINNED_PDK}`", md)
        self.assertIn(staged["pdk/sm141064.ngspice"], md)
        self.assertIn("fleet image's own PDK is not read", md)
        self.assertIn("ngspice-46 (run by aws-batch-fleet, job klt-sim-deckjob01)", md)
        environment = md.split("## Environment")[1]
        for absent in ("runner PDK as reported by klt", "vdd_val=", "None"):
            self.assertNotIn(absent, environment)
        self.assertIn("deck sha256 the runner executed equals the composed one for 2", environment)

    def test_the_engine_pin_is_checked_on_what_the_fleet_reported(self):
        """The PDK is the launcher's own bytes, pin-checked before the run, so
        only the engine can differ from what was checked on this host."""
        self.assertEqual(batch.deck_toolchain_drifts(deck_report([], engine_version="46"), PINS), [])
        old = deck_report([], engine_version="42")
        self.assertEqual([d.tool for d in batch.deck_toolchain_drifts(old, PINS)], ["ngspice"])
        silent = deck_report([], engine_version="")
        self.assertEqual([d.tool for d in batch.deck_toolchain_drifts(silent, PINS)], ["ngspice"])

    def test_only_scored_units_supply_the_engine_identity_including_failed_scores(self):
        build = self._build()
        units = [self._unit(self.points[0], "", build=build, record=False),
                 self._unit(self.points[1], "m_n = 3\n", build=build)]
        units[0]["engine_version"] = "42"
        results, klt_report = self._deck_results(build, units)
        klt_report["environment"]["engine_version"] = "42"
        self.assertEqual([r.status for r in results], ["error", "failed"])
        self.assertEqual(batch.deck_toolchain_drifts(klt_report, PINS, results), [])
        execution = batch.deck_execution_summary(build, klt_report, self.root / "out",
                                                 self.pdk, "batch", results)
        self.assertEqual(execution["engine_version"], "46")
        del units[1]["engine_version"]
        drift, = batch.deck_toolchain_drifts(klt_report, PINS, results)
        self.assertEqual(drift.found, "unknown")
        self.assertIn(self.points[1].corner_id, drift.detail)

    def test_missing_or_invalid_worker_evidence_prevents_scoring_only_its_point(self):
        build = self._build()
        transcript = "m_n = 3\nm_vout_mv = 1.5\n"
        units = [self._unit(p, transcript, build=build) for p in self.points]
        path = self.root / "out" / units[0]["id"] / "unit.json"
        key = json.loads(path.read_text())["key"]
        staged = dict(key["inputs"])
        fragment = staged.pop("tb.spice")
        # klt can place file hashes in either part of its worker key.
        key.update(inputs=staged, includes={"tb.spice": fragment})
        path.write_text(json.dumps({"key": key}))
        self.assertEqual([r.status for r in self._deck_results(build, units)[0]], ["ok", "ok"])
        for case, contents, diagnostic in (
            ("absent file", None, "unit.json"),
            ("invalid JSON", "{", "unit.json"),
            ("absent key", "{}", "unit.json"),
            ("missing deck hash", {"inputs": self._record(build)}, "deck_sha256"),
            ("wrong deck hash", dict(key, deck_sha256="0" * 64), "deck_sha256"),
            ("malformed inputs", dict(key, inputs=["tb.spice"]), "inputs"),
            ("malformed includes", dict(key, includes="tb.spice"), "includes"),
            ("missing file hash", dict(key, includes={}), "tb.spice"),
            ("conflicting file hash", dict(key, inputs={**staged, "tb.spice": "bad"}), "tb.spice"),
        ):
            with self.subTest(case=case):
                if contents is None:
                    path.unlink()
                elif isinstance(contents, str):
                    path.write_text(contents)
                else:
                    path.write_text(json.dumps({"key": contents}))
                results, klt_report = self._deck_results(build, units)
                self.assertEqual([r.status for r in results], ["error", "ok"])
                self.assertEqual(results[0].measurements, {})
                self.assertIn(diagnostic, results[0].message)
                self.assertIn(transcript, (self.logs / results[0].log).read_text())
                counts = batch.deck_execution_summary(
                    build, klt_report, self.root / "out", self.pdk, "batch")["units"]
                self.assertEqual(counts["worker_record_match"], 1)

    def test_committed_decks_manifests_are_ones_the_corner_engine_refuses(self):
        """Deck transport is for decks a corner request cannot carry. An
        exportable manifest that set the flag would bypass the corner path
        (its ``klt_sim`` pin, its smaller fleet job) for nothing."""
        flagged = []
        for directory in testbench.discover(SIM_DIR):
            tb = testbench.load(directory)
            if not tb.klt_decks:
                continue
            flagged.append(tb.experiment)
            with self.subTest(experiment=tb.experiment), self.assertRaises(batch.NotExportable):
                batch.check_exportable(tb)
                batch._fragment_text(tb)
        self.assertEqual(sorted(flagged), ["device-cdac-cap",
                                           "device-comparator-flicker-noise",
                                           "device-mismatch-mc"])

    def test_runner_skew_caveats_apply_to_deck_transport_too(self):
        skewed = dict(FLEET_JOB, runner_compatibility="mismatch", runner_klt_version="0.5.0")
        execution: dict = {}
        batch.apply_runner_caveats(execution, deck_report([], remote=skewed), needs_honored_options=False)
        self.assertIn("0.5.0", execution["caveats"][0])
        with self.assertRaises(batch.BatchError):
            batch.apply_runner_caveats({}, deck_report([], remote=skewed), needs_honored_options=True)
        matched: dict = {}
        batch.apply_runner_caveats(matched, deck_report([], remote=FLEET_JOB), needs_honored_options=True)
        self.assertNotIn("caveats", matched)


def report_mod_record(tb, pdk, points, results, execution, ngspice="ngspice-46"):
    return report.build_record(
        tb=tb, pdk=pdk, points=points, results=results, ngspice=ngspice,
        repo_root=SIM_DIR.parent, record_id="20260101-000000-abcdef0",
        started_utc="2026-01-01T00:00:00+00:00", wall_seconds=1.0,
        subset_reason="unit test", git={"commit": "c" * 40, "short": "ccccccc", "branch": "b", "dirty": False},
        allow_unswept_axes=True, execution=execution,
    )


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
            self.tb, self.plan, self.points, outcomes(corner_list),
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
        """No log artifact came back: the wording says no transcript was
        retained, and the log is a status note -- not a stub that reads as a
        transcript in the record's log column (issue #879)."""
        timeout = {"severity": "error", "code": "timeout", "message": "exceeded 300s"}
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout], runtime=300.0),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "x")),
        ], timeout=300)
        self.assertEqual(res[0].status, "error")
        self.assertEqual(
            res[0].message,
            "ngspice timed out after 300s; no transcript retained: "
            "the runner returns no log for a timed-out point",
        )
        self.assertEqual(
            (self.logs / "tt_27c_3.30v.log").read_text(),
            "TIMEOUT after 300s\n"
            "NO TRANSCRIPT: the runner returns no log for a timed-out point\n",
        )

    def test_timeout_with_a_log_artifact_keeps_the_partial_transcript(self):
        """klt's engine writes its own log (`ngspice -o`), so a timed-out
        corner still reports a `log` artifact -- measured against klt
        0.9.3.dev472: a `timeout` corner at runtime == budget carries the
        partial `ngspice.log`. Copy it; `TIMEOUT after Ns` stays the
        greppable first line, ahead of the partial transcript, and the
        message wording is unchanged from the plain-budget form."""
        timeout = {"severity": "error", "code": "timeout", "message": "exceeded 300s"}
        partial = (
            "banner\nDoing analysis at TEMP = 27\n"
            "doAnalyses: TRAN: Timestep too small; time = 1.4e-06\n"
        )
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout], runtime=300.0,
                       artifacts=self._artifacts("tt", partial)),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "x")),
        ], timeout=300)
        self.assertEqual(res[0].status, "error", "a timed-out point is never reclassified")
        self.assertEqual(res[0].message, "ngspice timed out after 300s")
        text = (self.logs / "tt_27c_3.30v.log").read_text()
        self.assertTrue(text.startswith("TIMEOUT after 300s\n"))
        self.assertIn("Timestep too small", text)
        self.assertEqual(text[len("TIMEOUT after 300s\n"):], partial,
                         "the transcript is copied verbatim under the status line")

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
            outcomes([klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout],
                                 artifacts=self._artifacts("tt", "partial\n"))]),
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

    def test_error_corner_without_values_reports_the_abort_line(self):
        """Issue #585: klt's generic error text must not hide ngspice's abort."""
        log = ('doAnalyses: TRAN:  Timestep too small; time = 1.4e-06, '
               'trouble with node "vvdd_gate#branch"\ntran simulation(s) aborted\n')
        diag = {"severity": "error", "code": "no_measurements", "message": "klt generic"}
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", diagnostics=[diag],
                       artifacts=self._artifacts("tt", log)),
            klt_corner("ss", 27, 3.3, status="error", diagnostics=[diag],
                       artifacts=self._artifacts("ss", "plain log")),
        ])
        self.assertEqual(res[0].status, "error")
        self.assertIn("vvdd_gate#branch", res[0].message)
        self.assertNotIn("klt generic", res[0].message)
        self.assertEqual(res[1].status, "error")
        self.assertIn("klt generic", res[1].message)

    def test_error_corner_without_log_does_not_crash_the_abort_scan(self):
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", artifacts=self._artifacts("tt", None)),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "ok")),
        ])
        self.assertEqual(res[0].status, "error")
        self.assertTrue((self.logs / res[0].log).is_file())

    def test_deck_is_retained_beside_the_log_for_non_ok_points_only(self):
        timeout = {"severity": "error", "code": "timeout", "message": "x"}
        res = self._convert([
            klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout],
                       artifacts=self._artifacts("tt", None)),
            klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2}, artifacts=self._artifacts("ss", "ok")),
        ])
        self.assertEqual(res[0].status, "error")
        self.assertTrue((self.logs / res[0].deck).is_file())
        self.assertEqual(res[1].status, "ok")
        self.assertFalse((self.logs / res[1].deck).exists())

    def test_non_ok_deck_is_left_alone_when_log_dir_is_the_workdir(self):
        """Issue #783: ``--no-write`` passes ``log_dir or workdir``, so the two
        are one directory and the deck is already where it belongs; copying it
        onto itself used to raise ``shutil.SameFileError`` and discard a fleet
        run that had already been paid for."""
        timeout = {"severity": "error", "code": "timeout", "message": "x"}
        res = batch.to_point_results(
            self.tb, self.plan, self.points,
            outcomes([
                klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout],
                           artifacts=self._artifacts("tt", None)),
                klt_corner("ss", 27, 3.3, measurements={"a": 1, "b": 2},
                           artifacts=self._artifacts("ss", "ok")),
            ]),
            self.work, self.work, 300,
        )
        self.assertEqual([r.status for r in res], ["error", "ok"])
        self.assertEqual(res[0].deck, "tt_27c_3.30v.spice")
        self.assertEqual((self.work / res[0].deck).read_text(), "* deck tt\n")

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
        klt_report["corners"] = []
        members = batch.build_supply_set(
            self.tb, make_pdk(self.root / "pdk"), self.plan, corners.resolve_corners(["tt", "ss"]),
            [27.0], [3.3], timeout_s=60,
        )
        execution = batch.execution_summary(
            [batch.SupplyOutcome(3.3, members[0].request_name, report=klt_report)], members, "batch"
        )
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
        self.assertEqual(len(env["execution"]["requests"]), 1)
        self.assertEqual(len(env["execution"]["requests"][0]["generated_body_sha256"]), 64)
        self.assertEqual(env["execution"]["requests"][0]["remote"]["job_id"], "klt-sim-1")
        md = report.render_record(record, "exp")
        self.assertIn("Executed via", md)
        self.assertIn("klt-sim-1", md)
        self.assertIn("Testbench netlist sha256", md)
        self.assertIn("vdd_val=3.3 V", md)
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

    def test_a_scored_member_reporting_no_engine_is_still_a_drift(self):
        """Issue #760 narrows *which* members are checked, not what counts as drift."""
        unidentifiable = {"provenance": {"pdk": {"version": f"open_pdks {PINNED_PDK}"}}}
        drifts = batch.fleet_toolchain_drifts(unidentifiable, PINS)
        self.assertEqual([d.tool for d in drifts], ["ngspice"])


class ScoredOutcomeScopingTests(unittest.TestCase):
    """Issue #760: the pin check sees only the members whose points are banked."""

    SUPPLIES = (2.97, 3.3, 3.63)

    def _outcomes(self):
        return [
            batch.SupplyOutcome(v, f"vdd-{v}.json", report={
                "environment": {"engine_version": "46" if v != 2.97 else None},
                "provenance": {"pdk": {"version": f"open_pdks {PINNED_PDK}"}},
            })
            for v in self.SUPPLIES
        ]

    def _results(self, statuses):
        """One result per supply, in supply order, with the given status."""
        corner = corners.resolve_corners(["tt"])[0]
        return [
            runner.PointResult(point=corners.PvtPoint(corner, 27.0, v), status=status)
            for v, status in zip(self.SUPPLIES, statuses)
        ]

    def test_an_unscored_member_is_dropped_from_the_pin_check(self):
        outs = batch.scored_outcomes(
            self._outcomes(), self._results(["error", "ok", "ok"])
        )
        self.assertEqual([o.supply_v for o in outs], [3.3, 3.63])
        self.assertEqual(batch.fleet_toolchain_drifts(outs, PINS), [])

    def test_a_failed_point_still_counts_as_scored(self):
        """``failed`` is a measured out-of-bound number -- it is banked evidence."""
        outs = batch.scored_outcomes(
            self._outcomes(), self._results(["failed", "ok", "ok"])
        )
        self.assertEqual([o.supply_v for o in outs], list(self.SUPPLIES))
        self.assertEqual([d.tool for d in batch.fleet_toolchain_drifts(outs, PINS)], ["ngspice"])

    def test_position_in_the_set_does_not_matter(self):
        """The unreportable member last in supply order is scoped out just the same."""
        outs = list(reversed(self._outcomes()))
        kept = batch.scored_outcomes(outs, self._results(["error", "ok", "ok"]))
        self.assertEqual([o.supply_v for o in kept], [3.63, 3.3])

    def test_no_member_scored_keeps_every_outcome(self):
        outs = self._outcomes()
        self.assertEqual(batch.scored_outcomes(outs, self._results(["error"] * 3)), outs)
        self.assertEqual(batch.scored_outcomes(outs, []), outs)

    def test_float_noise_in_the_reported_supply_still_matches(self):
        outs = self._outcomes()
        outs[1] = batch.SupplyOutcome(3.3000000000001, "vdd-nom.json", report=outs[1].report)
        kept = batch.scored_outcomes(outs, self._results(["error", "ok", "error"]))
        self.assertEqual([o.request for o in kept], ["vdd-nom.json"])

    def test_identity_comes_from_a_member_that_reported_one(self):
        """A reclaimed member first in supply order must not stamp ngspice-unknown."""
        outs = self._outcomes()
        outs[0].report["environment"]["remote"] = {"provider": "aws-batch-fleet", "job_id": "j0"}
        outs[1].report["environment"]["remote"] = {"provider": "aws-batch-fleet", "job_id": "j1"}
        label = batch.ngspice_label(outs)
        self.assertNotIn("unknown", label)
        self.assertIn("ngspice-46", label)
        # Every job that ran is still named, including the interrupted one.
        self.assertIn("j0", label)
        self.assertIn("j1", label)

    def test_execution_summary_identity_skips_the_unreportable_member(self):
        outs = self._outcomes()
        members = [
            batch.SupplyRequest(v, batch.supply_stem(i, v), "*\n", {})
            for i, v in enumerate(self.SUPPLIES)
        ]
        execution = batch.execution_summary(outs, members, "batch")
        self.assertEqual(execution["engine_version"], "46")
        # The per-request rows still show every member, in supply order.
        self.assertEqual([r["supply_v"] for r in execution["requests"]], list(self.SUPPLIES))

    def test_identity_falls_back_to_the_first_report_when_none_states_one(self):
        outs = self._outcomes()
        for outcome in outs:
            outcome.report["environment"]["engine_version"] = None
        self.assertIn("ngspice-unknown", batch.ngspice_label(outs))


class ShardedFleetBlockTests(unittest.TestCase):
    """A request klt split into shard jobs reports `remote.fleet` as a list."""

    FLAT = {"provider": "aws-batch-fleet", "job_id": "j-flat",
            "instance_type": "m6i.4xlarge", "runner_compatibility": "match"}
    SHARDED = {"fleet": [
        {"provider": "aws-batch-fleet", "job_id": "j-0", "instance_type": "c7i.8xlarge",
         "availability_zone": "us-east-1a", "lifecycle": "spot",
         "runner_klt_version": "0.9.0", "runner_compatibility": "match", "state": "done"},
        {"provider": "aws-batch-fleet", "job_id": "j-1", "instance_type": "c7i.8xlarge",
         "availability_zone": "us-east-1a", "lifecycle": "spot",
         "runner_klt_version": "0.9.0", "runner_compatibility": "match", "state": "done"},
    ]}

    def test_both_shapes_normalise_to_a_list_of_job_blocks(self):
        self.assertEqual(batch.fleet_blocks(self.FLAT), [self.FLAT])
        self.assertEqual(
            [b["job_id"] for b in batch.fleet_blocks(self.SHARDED)], ["j-0", "j-1"])
        self.assertEqual(batch.fleet_blocks(None), [])
        self.assertEqual(batch.fleet_blocks({}), [])

    def _report(self, remote):
        return {"environment": {"engine_version": "47", "remote": remote},
                "provenance": {}}

    def test_every_shard_job_is_named_in_the_engine_label(self):
        label = batch.ngspice_label(self._report(self.SHARDED))
        self.assertIn("j-0", label)
        self.assertIn("j-1", label)
        self.assertIn("aws-batch-fleet", label)
        self.assertIn("jobs", label)

    def test_a_single_job_report_still_reads_flat(self):
        self.assertIn("j-flat", batch.ngspice_label(self._report(self.FLAT)))

    def test_execution_summary_finds_the_provider_behind_the_shards(self):
        member = batch.SupplyRequest(3.3, "vdd0-3p3v", "*\n", {})
        execution = batch.execution_summary(
            [batch.SupplyOutcome(3.3, "vdd0-3p3v.json", report=self._report(self.SHARDED))],
            [member], "batch",
        )
        self.assertEqual(execution["backend"], "aws-batch-fleet")

    def test_skew_on_one_shard_is_not_lost(self):
        """Pre-fix this read runner_compatibility off the wrapper and saw None."""
        remote = {"fleet": [
            dict(self.SHARDED["fleet"][0]),
            {**self.SHARDED["fleet"][1], "runner_compatibility": "mismatch",
             "client_klt_version": "0.9.2"},
        ]}
        execution: dict = {}
        batch.apply_runner_caveats(
            execution, self._report(remote), needs_honored_options=False)
        self.assertIn("numdgt", execution["caveats"][0])
        with self.assertRaises(batch.BatchError):
            batch.apply_runner_caveats({}, self._report(remote), needs_honored_options=True)

    def test_the_record_names_every_shard_job(self):
        lines = report._fleet_job_lines(self.SHARDED, "  - ")
        self.assertEqual(len(lines), 2)
        self.assertIn("`j-0`", lines[0])
        self.assertIn("`j-1`", lines[1])
        self.assertNotIn("None", "".join(lines))


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
        # Host rule: every batch submit waits for fleet capacity (backoff)
        # rather than failing the step on batch_no_capacity.
        self.assertEqual(cmd[cmd.index("--wait-for-capacity") + 1], str(batch.CAPACITY_WAIT_S))

    def test_submit_refuses_an_implicit_backend(self):
        with mock.patch.object(batch, "klt_available", return_value=["klt"]), \
                mock.patch.object(batch.subprocess, "run") as run:
            with self.assertRaises(batch.BatchError):
                batch.submit(Path("r.json"), Path("out"), "")
        run.assert_not_called()

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

    def _args(self, extra, quiet=True):
        return cli.build_parser().parse_args(
            [str(self.experiment), "--no-write", "--subset-reason", "test"]
            + (["--quiet"] if quiet else []) + extra
        )

    def _run(self, extra, env, submit_effect, quiet=True):
        patches = [
            mock.patch.object(cli, "find_pdk", return_value=self.pdk),
            mock.patch.object(cli.runner, "ngspice_version", return_value="ngspice-46"),
            mock.patch.object(cli.toolchain_mod, "load_pins", return_value=PINS),
            mock.patch.object(cli.batch_mod, "klt_available", return_value=["klt"]),
            mock.patch.object(cli.batch_mod, "submit_set", side_effect=submit_effect),
            mock.patch.object(cli.runner, "run_grid", side_effect=AssertionError("ran locally")),
            mock.patch.object(cli, "WORK_DIR", self.root / "work"),
            mock.patch.dict(cli.os.environ, env, clear=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return cli.run(self._args(extra, quiet=quiet))

    def test_dispatch_host_never_falls_back_to_local_when_submit_fails(self):
        code = self._run([], {"KLT_SIM_BACKEND": "batch"}, batch.BatchError("no capacity"))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        cli.runner.run_grid.assert_not_called()

    def test_dispatch_host_routes_the_grid_through_submit(self):
        def fake_submit(members, request_dir, outdir, requested, klt_cmd="klt", max_in_flight=None, capacity_retries=0):
            self.assertEqual(requested, "batch")
            self.assertEqual(len(members), 1)
            request = json.loads((request_dir / members[0].request_name).read_text())
            self.assertEqual([p["name"] for p in request["corners"]["process"]], ["tt", "ss"])
            self.assertNotIn("supply_v", request["corners"])
            body = (request_dir / request["netlist"]).read_text()
            self.assertIn(".param vdd_val=3.3", body)
            return [batch.SupplyOutcome(3.3, members[0].request_name, report={
                "status": "not_checked",
                "corners": [klt_corner(p, 27, 3.3, measurements={"vout": 1.0},
                                       artifacts=self._art(p)) for p in ("tt", "ss")],
                "environment": {"engine_version": "46", "remote": {
                    "provider": "aws-batch-fleet", "job_id": "j", "runner_compatibility": "match"}},
                "provenance": {"klt_version": "0.6.0",
                               "pdk": {"name": "gf180mcuD", "version": f"open_pdks {PINNED_PDK}"}},
            })], {"schema_version": 1, "status": "pass", "requests": []}

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
        def old_fleet(members, request_dir, outdir, requested, klt_cmd="klt", max_in_flight=None, capacity_retries=0):
            return [batch.SupplyOutcome(3.3, members[0].request_name, report={
                "status": "not_checked",
                "corners": [klt_corner(p, 27, 3.3, measurements={"vout": 1.0},
                                       artifacts=self._art(p)) for p in ("tt", "ss")],
                "environment": {"engine_version": "42"},
                "provenance": {"pdk": {"version": f"open_pdks {PINNED_PDK}"}}})], None

        self.assertEqual(self._run([], {"KLT_SIM_BACKEND": "batch"}, old_fleet), cli.EXIT_ENVIRONMENT)
        # ... unless the drift is deliberately accepted, in which case it is stamped.
        self.assertEqual(
            cli.run(self._args(["--allow-toolchain-drift"])), cli.EXIT_OK
        )

    def test_no_write_run_with_a_timed_out_point_summarises_instead_of_raising(self):
        """Issue #783: the probe path a fleet timeout actually lands on.

        ``--no-write`` leaves ``log_dir`` unset, so the harness used to copy the
        timed-out point's deck onto itself and die with ``SameFileError`` --
        discarding the summary of fleet work already paid for.
        """
        timeout = {"severity": "error", "code": "timeout", "message": "exceeded"}

        def timed_out_fleet(members, request_dir, outdir, requested, klt_cmd="klt", max_in_flight=None, capacity_retries=0):
            return [batch.SupplyOutcome(3.3, members[0].request_name, report={
                "status": "not_checked",
                "corners": [
                    klt_corner("tt", 27, 3.3, status="error", diagnostics=[timeout],
                               artifacts=self._art("tt")),
                    klt_corner("ss", 27, 3.3, measurements={"vout": 1.0},
                               artifacts=self._art("ss")),
                ],
                "environment": {"engine_version": "46", "remote": {
                    "provider": "aws-batch-fleet", "job_id": "klt-sim-04a1623057ab",
                    "runner_compatibility": "match"}},
                "provenance": {"klt_version": "0.6.0",
                               "pdk": {"name": "gf180mcuD", "version": f"open_pdks {PINNED_PDK}"}},
            })], {"schema_version": 1, "status": "pass", "requests": []}

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self._run([], {"KLT_SIM_BACKEND": "batch"}, timed_out_fleet, quiet=False)
        printed = out.getvalue()
        self.assertEqual(code, cli.EXIT_SIM_ERROR)
        self.assertIn("ngspice timed out", printed)
        self.assertIn("summary (1/2 points ok", printed)
        self.assertIn("not recorded (--no-write)", printed)

    def test_explicit_local_backend_runs_the_local_runner(self):
        with self.assertRaisesRegex(AssertionError, "ran locally"):
            self._run(["--backend", "local", "--allow-local-grid"],
                      {"KLT_SIM_BACKEND": "batch"}, AssertionError("no"))
        cli.batch_mod.submit_set.assert_not_called()

    def test_explicit_local_multipoint_refused_without_override(self):
        code = self._run(["--backend", "local"], {"KLT_SIM_BACKEND": "batch"},
                         AssertionError("no"))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        cli.batch_mod.submit_set.assert_not_called()

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


class CliDeckTests(unittest.TestCase):
    """``klt_decks`` end to end through ``cli.run`` with the PDK, klt and the
    local runner mocked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk = make_pdk(self.root / "gf180mcuD")
        make_tb(self.root, {**DECK_MANIFEST, "temperatures_c": [27], "supply_tolerance": 0.0,
                            "corners": ["tt", "ss"]})
        self.experiment = self.root / "exp"

    def _run(self, extra, submit_effect, export="never"):
        """``export="never"`` makes the corner export fail the test if it is
        consulted (a ``klt_decks`` manifest must not need it); ``"real"``
        leaves it in place."""
        args = cli.build_parser().parse_args(
            [str(self.experiment), "--no-write", "--subset-reason", "test", "--backend", "batch",
             "--quiet"] + extra
        )
        export_patch = (
            mock.patch.object(cli.batch_mod, "check_exportable",
                              side_effect=AssertionError("the corner export was consulted"))
            if export == "never" else
            mock.patch.object(cli.batch_mod, "check_exportable",
                              wraps=batch.check_exportable)
        )
        patches = [
            mock.patch.object(cli, "find_pdk", return_value=self.pdk),
            mock.patch.object(cli.runner, "ngspice_version", return_value="ngspice-46"),
            mock.patch.object(cli.toolchain_mod, "load_pins", return_value=PINS),
            mock.patch.object(cli.batch_mod, "klt_available", return_value=["klt"]),
            mock.patch.object(cli.batch_mod, "submit_decks", side_effect=submit_effect),
            mock.patch.object(cli.batch_mod, "submit_set", side_effect=AssertionError("corner path")),
            export_patch,
            mock.patch.object(cli.runner, "run_grid", side_effect=AssertionError("ran locally")),
            mock.patch.object(cli, "WORK_DIR", self.root / "work"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return cli.run(args)

    def _fleet(self, versions=("46", "46")):
        """A submit_decks stand-in: collect each deck the way klt does."""
        def submit(request_path, outdir, requested, klt_cmd="klt"):
            self.assertEqual(requested, "batch")
            request = json.loads(request_path.read_text())
            self.assertNotIn("corners", request)
            build = batch.DeckRequest(
                request, {d["id"]: (request_path.parent / d["deck"]).read_text()
                          for d in request["decks"]},
                {i["name"]: request_path.parent / i["name"] for i in request["decks"][0]["inputs"]},
                "0" * 64,
            )
            units = [
                deck_unit(outdir, d["id"], build.decks[d["id"]], "m_n = 3\nm_vout_mv = 1.5\n",
                          inputs={name: batch._sha256_raw(path.read_bytes())
                                  for name, path in build.staged.items()})
                for d in request["decks"]
            ]
            self.assertEqual(len(units), len(versions))
            for unit, version in zip(units, versions):
                unit["engine_version"] = version
            return deck_report(units, engine_version=versions[0], remote=dict(FLEET_JOB))
        return submit

    def test_dispatch_host_routes_a_decks_manifest_through_deck_transport(self):
        code = self._run([], self._fleet())
        self.assertEqual(code, cli.EXIT_OK)
        cli.runner.run_grid.assert_not_called()

    def test_the_corner_export_is_not_consulted_for_a_decks_manifest(self):
        """The analyses here begin with `setseed`; the corner engine would
        refuse them, and deck transport has nothing to re-express."""
        self.assertEqual(self._run([], self._fleet()), cli.EXIT_OK)

    def test_without_the_flag_the_same_manifest_is_refused_by_the_corner_export(self):
        tb_json = self.experiment / "testbench" / "tb.json"
        manifest = json.loads(tb_json.read_text())
        del manifest["klt_decks"]
        tb_json.write_text(json.dumps(manifest))
        cli.batch_mod.submit_decks.side_effect = None
        self.assertEqual(self._run([], AssertionError("must not submit"), export="real"),
                         cli.EXIT_ENVIRONMENT)

    def test_a_failed_deck_submit_never_falls_back_to_local(self):
        code = self._run([], batch.BatchError("no capacity"))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        cli.runner.run_grid.assert_not_called()

    def test_mixed_fleet_engines_require_an_explicit_override_naming_the_corner(self):
        for second, found in (("42", "42"), (None, "unknown")):
            fleet = self._fleet(("46", second))
            with self.subTest(version=second), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self._run([], fleet), cli.EXIT_ENVIRONMENT)
                self.assertIn("ss_27c_3.30v", err.getvalue())
                with mock.patch.object(report, "build_record", wraps=report.build_record) as record:
                    self.assertEqual(self._run(["--allow-toolchain-drift"], fleet), cli.EXIT_OK)
                summary = record.call_args.kwargs["toolchain"]
                self.assertTrue(summary["drift_allowed"])
                self.assertEqual([d["found"] for d in summary["drift"]], [found])
                self.assertIn("ss_27c_3.30v", summary["drift"][0]["detail"])
                versions = record.call_args.kwargs["execution"]["engine_version"]
                self.assertEqual(set(versions.split(", ")), {"46", found})
                self.assertIn(f"ngspice-{versions}", record.call_args.kwargs["ngspice"])

    def test_a_recording_run_files_the_decks_as_snapshots_and_the_report_beside_the_logs(self):
        """The evidence-writing path (no ``--no-write``). Regression: a local
        name shadowed the ``report`` module here, after the fleet run had
        already been paid for, and no test ran this path."""
        args = cli.build_parser().parse_args(
            [str(self.experiment), "--subset-reason", "test", "--backend", "batch", "--quiet"])
        tb = testbench.load(self.experiment)
        points = corners.build_grid(corners.resolve_corners(["tt", "ss"]), [27.0], [3.3])
        workdir = self.root / "work" / "rid"
        log_dir = self.root / "stage" / "exp" / "corners" / "rid"
        stage_exp = self.root / "stage" / "exp"
        with mock.patch.object(cli.batch_mod, "submit_decks", side_effect=self._fleet()), \
                mock.patch.object(cli, "WORK_DIR", self.root / "work"):
            results, execution, label, drifts = cli._run_decks_through_klt(
                args, tb, self.pdk, points, workdir, log_dir, stage_exp, "rid",
                False, lambda result: None, PINS,
            )
        self.assertEqual([r.status for r in results], ["ok", "ok"])
        snap = stage_exp / report.SNAPSHOT_DIR
        self.assertEqual(
            sorted(p.name for p in snap.iterdir()),
            sorted(f"rid.deck.{p.corner_id}.spice" for p in points),
        )
        self.assertIn("setseed 20260731", (snap / f"rid.deck.{points[0].corner_id}.spice").read_text())
        stored = sorted(p.name for p in log_dir.iterdir())
        self.assertEqual(
            stored,
            sorted(["klt-request.json", "klt-report.json"] + [f"{p.corner_id}.log" for p in points]),
        )
        self.assertEqual(len(json.loads((log_dir / "klt-request.json").read_text())["decks"]), 2)
        self.assertEqual(json.loads((log_dir / "klt-report.json").read_text())["unit_count"], 2)
        self.assertIn("m_n = 3", (log_dir / f"{points[0].corner_id}.log").read_text())
        self.assertEqual(label, "ngspice-46 (run by aws-batch-fleet, job klt-sim-deckjob01)")
        self.assertEqual(drifts, [])

    def test_the_split_knobs_ride_in_the_requests_batch_block(self):
        seen = {}

        def submit(request_path, outdir, requested, klt_cmd="klt"):
            seen["batch"] = json.loads(request_path.read_text()).get("batch")
            return deck_report([], engine_version="46")

        self._run(["--max-units-per-job", "5", "--max-concurrent-jobs", "2"], submit)
        self.assertEqual(seen["batch"], {"max_units_per_job": 5, "max_concurrent_jobs": 2})


class SpotInterruptedMemberCliTests(unittest.TestCase):
    """Issue #760: one unreportable member must not discard the whole set.

    A three-member set through ``cli.run`` with klt and the PDK mocked. The
    record is captured from ``report.build_record`` rather than written: these
    tests must never touch the append-only evidence tree under ``sim/``.
    """

    PINNED_ENV = {"engine_version": "46", "remote": {
        "provider": "aws-batch-fleet", "job_id": "j-ok", "runner_compatibility": "match"}}
    PINNED_PROV = {"klt_version": "0.6.0",
                   "pdk": {"name": "gf180mcuD", "version": f"open_pdks {PINNED_PDK}"}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk = make_pdk(self.root / "gf180mcuD")
        make_tb(self.root, {"analyses": ["op"], "measure": {"vout": "v(out)"},
                            "temperatures_c": [27], "supply_tolerance": 0.1,
                            "corners": ["tt", "ss"]})
        self.experiment = self.root / "exp"
        self.supplies = corners.supply_points(3.3, 0.1)
        self.records = []

    def _art(self, tag):
        d = self.root / "art" / tag
        d.mkdir(parents=True, exist_ok=True)
        (d / "corner.cir").write_text("*\n")
        (d / "ngspice.log").write_text("fine\n")
        return {"log": str(d / "ngspice.log"), "deck": str(d / "corner.cir"),
                "raw": None, "waveform": None}

    def _ok_member(self, vdd, engine="46"):
        env = dict(self.PINNED_ENV)
        env["engine_version"] = engine
        return {
            "status": "pass",
            "corners": [klt_corner(p, 27, vdd, measurements={"vout": 1.0},
                                   artifacts=self._art(f"{p}-{vdd}")) for p in ("tt", "ss")],
            "environment": env,
            "provenance": self.PINNED_PROV,
        }

    def _interrupted_member(self, vdd):
        """What a Spot reclaim leaves behind: error corners, and no engine banner.

        Inferred shape (the #753 report was not kept): ``corners`` present and
        all ``error``, a pinned ``provenance.pdk``, and no
        ``environment.engine_version``, which is what makes only the ngspice
        pin fire.
        """
        diag = {"severity": "error", "code": "batch_job_interrupted",
                "message": "the Spot instance running this unit was reclaimed"}
        return {
            "status": "error",
            "corners": [klt_corner(p, 27, vdd, status="error", diagnostics=[diag])
                        for p in ("tt", "ss")],
            "environment": {"remote": {"provider": "aws-batch-fleet",
                                       "job_id": "klt-sim-c84442dd528a"}},
            "provenance": self.PINNED_PROV,
        }

    def _run(self, reports_by_supply, extra=()):
        """Run the grid with one stubbed report per supply; capture the record."""
        def fake_submit(members, request_dir, outdir, requested, klt_cmd="klt", max_in_flight=None, capacity_retries=0):
            self.assertEqual([m.supply_v for m in members], self.supplies)
            return [
                batch.SupplyOutcome(m.supply_v, m.request_name,
                                    report=reports_by_supply[m.supply_v])
                for m in members
            ], None

        real_build = report.build_record

        def spy(**kwargs):
            record = real_build(**kwargs)
            self.records.append(record)
            return record

        patches = [
            mock.patch.object(cli, "find_pdk", return_value=self.pdk),
            mock.patch.object(cli.runner, "ngspice_version", return_value="ngspice-46"),
            mock.patch.object(cli.toolchain_mod, "load_pins", return_value=PINS),
            mock.patch.object(cli.batch_mod, "klt_available", return_value=["klt"]),
            mock.patch.object(cli.batch_mod, "submit_set", side_effect=fake_submit),
            mock.patch.object(cli.runner, "run_grid", side_effect=AssertionError("ran locally")),
            mock.patch.object(cli.report, "build_record", side_effect=spy),
            mock.patch.object(cli, "WORK_DIR", self.root / "work"),
            mock.patch.dict(cli.os.environ, {"KLT_SIM_BACKEND": "batch"}, clear=False),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        args = cli.build_parser().parse_args(
            [str(self.experiment), "--no-write", "--subset-reason", "test", "--quiet"]
            + list(extra)
        )
        return cli.run(args)

    def _mixed_set(self, interrupted=0, engines=("46", "46", "46")):
        """The three reports, with ``interrupted`` as the reclaimed member."""
        out = {}
        for index, vdd in enumerate(self.supplies):
            out[vdd] = (self._interrupted_member(vdd) if index == interrupted
                        else self._ok_member(vdd, engine=engines[index]))
        return out

    def test_an_interrupted_member_no_longer_discards_the_set(self):
        code = self._run(self._mixed_set(interrupted=0))
        # The run is NOT refused as toolchain drift: it reaches the record and
        # exits on the four error points it genuinely has, not EXIT_ENVIRONMENT.
        self.assertEqual(code, cli.EXIT_SIM_ERROR)
        record = self.records[-1]
        self.assertEqual(record["grid"]["points_ok"], 4)
        by_vdd = {}
        for point in record["points"]:
            by_vdd.setdefault(point["vdd"], set()).add(point["status"])
        self.assertEqual(by_vdd[self.supplies[0]], {"error"})
        self.assertEqual(by_vdd[self.supplies[1]], {"ok"})
        self.assertEqual(by_vdd[self.supplies[2]], {"ok"})

    def test_the_banked_record_conforms_and_is_not_labelled_unknown(self):
        self._run(self._mixed_set(interrupted=0))
        env = self.records[-1]["environment"]
        self.assertTrue(env["toolchain"]["conforms"])
        self.assertEqual(env["toolchain"]["drift"], [])
        self.assertEqual(env["execution"]["engine_version"], "46")
        self.assertNotIn("ngspice-unknown", env["ngspice"])
        self.assertIn("ngspice-46", env["ngspice"])

    def test_the_interrupted_members_reason_survives_into_the_record(self):
        self._run(self._mixed_set(interrupted=0))
        errors = [p for p in self.records[-1]["points"] if p["status"] == "error"]
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("reclaimed" in p["message"] for p in errors))

    def test_the_interrupted_member_may_be_last_in_supply_order(self):
        code = self._run(self._mixed_set(interrupted=2))
        self.assertEqual(code, cli.EXIT_SIM_ERROR)
        env = self.records[-1]["environment"]
        self.assertTrue(env["toolchain"]["conforms"])
        self.assertIn("ngspice-46", env["ngspice"])

    def test_an_unscored_members_banner_does_not_stamp_the_record(self):
        """AC 2: the identity comes from the subset the pin check covers.

        The interrupted member sorts first (2.97 V is index 0) and reports an
        off-pin ``42``. All four of its points are errors, so it is exempt
        from the pin check -- an off-pin engine is a plausible reason every
        one of them errored. If it could still name the engine, the record
        would read ``conforms: true``, carry no drift and be labelled
        ``ngspice-42`` while all four banked points ran on 46. ``sim/``
        records are append-only, so that label could never be corrected.
        """
        reports = self._mixed_set(interrupted=0)
        reports[self.supplies[0]]["environment"]["engine_version"] = "42"
        code = self._run(reports)
        self.assertEqual(code, cli.EXIT_SIM_ERROR)
        env = self.records[-1]["environment"]
        self.assertTrue(env["toolchain"]["conforms"])
        self.assertEqual(env["toolchain"]["drift"], [])
        self.assertEqual(env["execution"]["engine_version"], "46")
        self.assertIn("ngspice-46", env["ngspice"])
        self.assertNotIn("ngspice-42", env["ngspice"])
        # the unscored member's job id is still listed, as before
        self.assertIn("klt-sim-c84442dd528a", env["ngspice"])

    def test_an_unscored_members_provenance_does_not_stamp_the_record(self):
        """The top-level klt/PDK fields follow the same identity report."""
        reports = self._mixed_set(interrupted=0)
        reports[self.supplies[0]]["environment"]["engine_version"] = "42"
        reports[self.supplies[0]]["provenance"] = {
            "klt_version": "0.0.1",
            "pdk": {"name": "gf180mcuD", "version": "open_pdks deadbeef"},
        }
        self._run(reports)
        execution = self.records[-1]["environment"]["execution"]
        self.assertEqual(execution["klt_version"], "0.6.0")
        self.assertEqual(execution["pdk"]["version"], f"open_pdks {PINNED_PDK}")
        # the per-request block still reports what each member itself said
        by_supply = {r["supply_v"]: r for r in execution["requests"]}
        self.assertEqual(by_supply[self.supplies[0]]["klt_version"], "0.0.1")
        self.assertEqual(by_supply[self.supplies[1]]["klt_version"], "0.6.0")

    def test_a_scored_member_on_an_off_pin_ngspice_still_refuses_the_run(self):
        code = self._run(self._mixed_set(interrupted=0, engines=("46", "42", "46")))
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        self.assertEqual(self.records, [])

    def test_a_scored_member_with_no_engine_identity_still_refuses_the_run(self):
        """AC 4: results that would be banked must be identifiable."""
        reports = self._mixed_set(interrupted=0)
        reports[self.supplies[1]]["environment"] = {
            "remote": dict(self.PINNED_ENV["remote"])}
        code = self._run(reports)
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        self.assertEqual(self.records, [])

    def test_every_member_unscored_keeps_the_unchanged_note_path(self):
        """AC 5: nothing scored -> the drift is noted, not applied as a refusal."""
        reports = {v: self._interrupted_member(v) for v in self.supplies}
        code = self._run(reports)
        self.assertEqual(code, cli.EXIT_SIM_ERROR)
        env = self.records[-1]["environment"]
        self.assertFalse(env["toolchain"]["conforms"])
        self.assertEqual([d["tool"] for d in env["toolchain"]["drift"]], ["ngspice"])

    def test_allow_toolchain_drift_still_records_through_a_scored_drift(self):
        code = self._run(self._mixed_set(interrupted=0, engines=("46", "42", "46")),
                         extra=["--allow-toolchain-drift"])
        self.assertEqual(code, cli.EXIT_SIM_ERROR)
        toolchain = self.records[-1]["environment"]["toolchain"]
        self.assertTrue(toolchain["drift_allowed"])
        self.assertEqual([d["tool"] for d in toolchain["drift"]], ["ngspice"])


if __name__ == "__main__":
    unittest.main()
