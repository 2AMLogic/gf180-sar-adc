#!/usr/bin/env python3
"""`--check` must not launch the record-only provenance probes (issue #1007).

The four `layout/` signoff runners (DRC, LVS, ERC, power) stamp a toolchain
provenance block into the record they mint.  `--check` writes no record, so
the probes that only feed that block -- the `git` launches (ERC/power inline,
DRC/LVS inside `klt_env.toolchain_record`) and the interpreter probes for the
`klayout` package (DRC/LVS `toolchain_record`) -- are guarded by `if
args.check` (#1001, #1004).  Nothing else pins those guards, so moving a probe
back above its guard would silently regress `--check` latency.

The test is hermetic: `subprocess.run` is replaced by a recorder that never
launches anything, so no `klt`, `git` or network is needed.  Each runner's
`main()` is driven with the tool-resolution stubs it needs and is stopped by a
sentinel exception raised from the first per-case call, which proves the
pre-loop section (where the guards live) was fully executed.  Every runner is
also run without `--check` as a control: the same probes must appear there, so
the `--check` assertion cannot pass vacuously.

NOT asserted: "zero subprocesses".  DRC/LVS legitimately run `klt --version`
before the guard; only record-only probes are counted.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loadmod import load_module  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LAYOUT = REPO / "layout"


class CaseLoopReached(Exception):
    """Raised from the first per-case call: the pre-loop section completed."""


def _reach(*_args, **_kwargs):
    raise CaseLoopReached


def _is_record_probe(argv) -> bool:
    argv = [str(a) for a in argv]
    if argv and argv[0] == "git":
        return True
    # klt_env.find_klayout_python / klayout_version: `<python> -c <klayout ...>`
    return len(argv) >= 3 and argv[1] == "-c" and "klayout" in argv[2]


def _stub_klt_pin(mod, monkeypatch):
    monkeypatch.setattr(mod.toolchain_pin, "load_toolchain_pin",
                        lambda *a, **k: {"klt_required_commands": []})
    monkeypatch.setattr(mod, "find_klt", lambda: "/nonexistent/klt")
    monkeypatch.setattr(mod, "check_klt_capabilities", lambda *a, **k: None)
    monkeypatch.setattr(mod, "find_klayout_python", lambda: "/nonexistent/python")


def _stub_drc(mod, monkeypatch):
    _stub_klt_pin(mod, monkeypatch)
    monkeypatch.setattr(mod, "run_cell", _reach)


def _stub_lvs(mod, monkeypatch):
    _stub_klt_pin(mod, monkeypatch)
    monkeypatch.setattr(mod, "run_extract", _reach)


def _stub_report_runner(mod, monkeypatch):
    monkeypatch.setattr(mod, "resolve_klt", lambda pin, override: ("/nonexistent/klt", {}))
    monkeypatch.setattr(mod, "run_case", _reach)


RUNNERS = {
    "drc": ("run_drc.py", _stub_drc),
    "lvs": ("run_lvs.py", _stub_lvs),
    "erc": ("run_erc.py", _stub_report_runner),
    "power": ("run_power.py", _stub_report_runner),
}
_loaded: dict = {}


def _module(name: str):
    if name not in _loaded:
        script = RUNNERS[name][0]
        _loaded[name] = load_module(
            f"_check_guard_{name}", LAYOUT / name / script
        )
    return _loaded[name]


def _run_main(name, argv, monkeypatch, tmp_path):
    mod = _module(name)
    RUNNERS[name][1](mod, monkeypatch)
    # Keep `klt_env.toolchain_record`'s own interpreter probe hermetic too.
    monkeypatch.setattr(sys.modules["klt_env"], "find_klayout_python",
                        lambda: "/nonexistent/python")
    if name == "power":
        # Control run reserves a record slot before the loop: keep it off the repo.
        monkeypatch.setattr(mod, "reserve_record_slot",
                            lambda *a, **k: str(tmp_path))
        monkeypatch.setattr(mod, "record_id", lambda *a, **k: "test-id")

    launched: list = []

    def fake_run(argv_, *a, **k):
        launched.append([str(x) for x in argv_])
        return subprocess.CompletedProcess(argv_, 1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", [RUNNERS[name][0], *argv])
    with pytest.raises(CaseLoopReached):
        mod.main()
    return [a for a in launched if _is_record_probe(a)]


@pytest.mark.parametrize("name", sorted(RUNNERS))
def test_check_skips_record_only_probes(name, monkeypatch, tmp_path):
    probes = _run_main(name, ["--check"], monkeypatch, tmp_path)
    assert probes == [], f"{name} --check launched record-only probes: {probes}"


@pytest.mark.parametrize("name", sorted(RUNNERS))
def test_non_check_control_launches_probes(name, monkeypatch, tmp_path):
    probes = _run_main(name, [], monkeypatch, tmp_path)
    assert any(p[0] == "git" for p in probes), (
        f"{name} control launched no git probe; the --check assertion would "
        f"be vacuous: {probes}"
    )
    if name in ("drc", "lvs"):
        assert any(p[1:2] == ["-c"] for p in probes), (
            f"{name} control launched no interpreter probe: {probes}"
        )
