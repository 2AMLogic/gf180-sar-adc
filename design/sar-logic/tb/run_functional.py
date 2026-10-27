#!/usr/bin/env python3
"""Run `sar_ctrl.fv_request.json` through `klt functional-verification` and
write the committed evidence (issue #642, T1 item 5 digital, bit-exact
functional suite).

    python3 design/sar-logic/tb/run_functional.py

Needs a `klt` on PATH whose interpreter has cocotb (`pip install
"klayout-tools[functional-verification] @ <signoff/toolchain.json
klt_install>"` in a venv -- never `pip install --user`) plus `iverilog`.
Writes, under `design/sar-logic/tb/reports/<rid>/`:

  - `fv_response.json`      the unedited `klt functional-verification` response
  - `results_icarus.xml`    cocotb's own results file the verdict derives from
  - `mutation_response.json` the same request with `--mutations`
                             (`sar_ctrl.mutation_proposals.json`): every mutant
                             must be killed, proving the suite can fail
  - `record.md`             the evidence record (per-test results, provenance)

Exits 1 if the baseline fails or any mutant survives.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "design" / "sar-logic" / "flow"))

from flow_env import git, klt_version, record_id  # noqa: E402

TB_DIR = REPO_ROOT / "design" / "sar-logic" / "tb"
REQUEST = TB_DIR / "sar_ctrl.fv_request.json"
PROPOSALS = TB_DIR / "sar_ctrl.mutation_proposals.json"


def run_fv(outdir: Path, *extra: str) -> dict:
    proc = subprocess.run(
        ["klt", "functional-verification", str(REQUEST), "-o", str(outdir), "--format", "json", *extra],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"klt functional-verification printed no JSON (exit {proc.returncode}):\n{proc.stderr}")


def main() -> int:
    when = dt.datetime.now(dt.timezone.utc)
    rid = record_id(REPO_ROOT, when)
    out = TB_DIR / "reports" / rid
    if out.exists():
        sys.exit(f"{out} exists -- refusing to overwrite append-only evidence")
    out.mkdir(parents=True)

    base = run_fv(out / "run")
    (out / "fv_response.json").write_text(json.dumps(base, indent=2) + "\n")
    shutil.copy(out / "run" / "results_icarus.xml", out / "results_icarus.xml")
    mut = run_fv(out / "mut", "--mutations", str(PROPOSALS))
    (out / "mutation_response.json").write_text(json.dumps(mut, indent=2) + "\n")
    shutil.rmtree(out / "run")
    shutil.rmtree(out / "mut")

    mt = mut.get("mutation_testing") or {}
    rows = "\n".join(
        f"| `{t['name']}` | {t['status']} | {t['sim_time_ns']:.0f} |" for t in base.get("tests", [])
    )
    env = base.get("environment") or {}
    ok = base.get("status") == "pass" and mt.get("survived_count") == 0 and mt.get("killed_count", 0) > 0
    rel = out.relative_to(REPO_ROOT)
    (out / "record.md").write_text(
        f"""\
# Record {rid} (sar_ctrl functional verification)

- **Record ID**: {rid}.sar_ctrl.functional_verification
- **Claim**: `design/sar-logic/rtl/sar_ctrl.v` (`sar_ctrl_a`) returns the bit-exact expected code for every
  input code 0..1023 in differential and single-ended mode, and every output (sampling window, drdy, all 54
  switch legs, c9..c0) matches an independent cycle-accurate model on every cycle. Cited as `5.digital` in
  `signoff/gf180-sar-adc.manifest.json` (issue #642), next to the multi-corner `klt sta` record.
- **Verdict**: **{"PASS" if ok else "FAIL"}** -- {base.get("passed_count")}/{base.get("test_count")} tests passed;
  mutation testing killed {mt.get("killed_count")}/{mt.get("valid_count")} valid mutants (score {mt.get("mutation_score")}).

| Test | Status | Sim time (ns) |
| --- | --- | --- |
{rows}

- **Why the suite can fail**: `{PROPOSALS.relative_to(REPO_ROOT)}` mutates the RTL nine ways (restart clear,
  sample window, comparator polarity, drdy, a stuck bit, LSB timing, an n-side leg, a gating term, an output
  wiring); every mutant is killed (`mutation_response.json`).
- **Scope**: zero-delay RTL only. The gate-level / SDF re-run is item 7 (#645) and reuses `test_sar_ctrl.py`
  with a different `sources` list.
- **Tool versions**: `klt` `{klt_version(REPO_ROOT)}`; {env.get("engine")} {env.get("engine_version")};
  cocotb {env.get("cocotb_version")}; random seed {env.get("random_seed")}.
- **Reproducibility**: commit `{git(REPO_ROOT, "rev-parse", "HEAD") or "unknown"}`; re-run with
  `python3 design/sar-logic/tb/run_functional.py` (response `environment` paths are the run host's).
- **Links**: `{rel}/fv_response.json`, `{rel}/results_icarus.xml`, `{rel}/mutation_response.json`;
  request `design/sar-logic/tb/sar_ctrl.fv_request.json`; bench `design/sar-logic/tb/test_sar_ctrl.py`.
- **Timestamp / author**: {when.strftime("%Y-%m-%d %H:%M:%S UTC")}, `design/sar-logic/tb/run_functional.py` (agent-run)
"""
    )
    print(f"{'PASS' if ok else 'FAIL'}: evidence in {rel}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
