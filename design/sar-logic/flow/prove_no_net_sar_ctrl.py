#!/usr/bin/env python3
"""Offline no-net prover run on the committed `sar_ctrl` inputs (issue #548).

Runs `spef_audit.prove_no_net_outputs` (DR-0040's independent no-net proof)
on the committed routed `layout/adc-top/sar_ctrl/sar_ctrl.def` / `.v` against
the Liberty of each of the five library corners `sta_postroute_spef.py` uses
(`base.CORNERS`), and writes a dated, append-only evidence record under
`design/sar-logic/flow/sar_ctrl/records/`.

Offline only: no `klt`, no extraction, no STA, no timing numbers, no closure
claim. It reads the committed inputs and the PDK Liberty and changes neither.

    python3 design/sar-logic/flow/prove_no_net_sar_ctrl.py [--no-record]

Needs the gf180mcu PDK (`GF180_PDK_PATH` / `PDK_ROOT`, see
`sim/harness/pdk.py`). `prove_all_corners` is also what
`sim/tests/test_spef_audit.py` calls, so the record and the regression test
cannot drift apart.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "design" / "sar-logic" / "flow"))

import spef_audit as audit  # noqa: E402
import sta_sar_ctrl_postroute as base  # noqa: E402
from flow_env import git, klt_version, record_id  # noqa: E402,F401
from sim.harness.pdk import PdkNotFound, find_pdk  # noqa: E402

ROUTED_DEF = base.ROUTED_DEF
ROUTED_V = REPO_ROOT / "layout" / "adc-top" / "sar_ctrl" / "sar_ctrl.v"

#: The exempt set the prover is expected to return at every corner: the two
#: `clkload` dummy-load cells whose outputs are unconnected in both views.
EXPECTED_NO_NET = ["clkload0/Z", "clkload1/ZN"]


def liberty_path(pdk, corner: str) -> Path:
    return pdk.path / "libs.ref" / base.CELL_LIBRARY / "lib" / f"{base.CELL_LIBRARY}__{corner}.lib"


def prove_all_corners(pdk) -> dict:
    """Prove no-net outputs at every `base.CORNERS` Liberty. Reports, and
    does not tune: `signal_pins_agree` and `exempt_set_equal` are computed,
    never assumed."""
    def_ = audit.parse_def(ROUTED_DEF.read_text())
    ver = audit.parse_verilog(ROUTED_V.read_text())
    cells = set(def_.components.values())
    inputs = {
        "def_sha256": audit.sha256_file(ROUTED_DEF),
        "verilog_sha256": audit.sha256_file(ROUTED_V),
    }
    corners = []
    pinsets = {}
    for corner, _desc in base.CORNERS:
        lib = liberty_path(pdk, corner)
        pins = audit.parse_liberty_pins(lib.read_text(), cells)
        pinsets[corner] = {c: dict(p) for c, p in pins.items()}
        proof = audit.prove_no_net_outputs(def_, ver, pins, {**inputs, "liberty_sha256": audit.sha256_file(lib)})
        corners.append({"corner": corner, "liberty": lib.name, "proof": proof})
    first = base.CORNERS[0][0]
    return {
        "inputs": inputs,
        "corners": corners,
        "signal_pins_agree": all(pinsets[c] == pinsets[first] for c in pinsets),
        "exempt_set_equal": all(c["proof"]["no_net"] == EXPECTED_NO_NET for c in corners),
    }


def render(result: dict, rid: str, pdk) -> str:
    rows = "\n".join(
        f"| `{c['corner']}` | {c['proof']['outputs_examined']} | `{', '.join(c['proof']['no_net'])}` "
        f"| {sum(1 for s in c['proof']['outputs'].values() if s != 'has_net' and s != 'no_net')} "
        f"| `{c['proof']['inputs']['liberty_sha256']}` |"
        for c in result["corners"]
    )
    agree, equal = result["signal_pins_agree"], result["exempt_set_equal"]
    verdict = (
        f"exempt set equals {{{', '.join(EXPECTED_NO_NET)}}} at all {len(result['corners'])} corners"
        if equal
        else "**DIVERGENCE**: the exempt set differs from the expected set at one or more corners (see table)"
    )
    return f"""# Record {rid}.{base.LIB_TAG}.no_net_prover

- **Record ID**: {rid}.{base.LIB_TAG}.no_net_prover
- **Claim under test**: `spef_audit.prove_no_net_outputs` (DR-0040), run on the
  committed routed `sar_ctrl` DEF/Verilog, proves exactly {{{', '.join(EXPECTED_NO_NET)}}} to have
  no net, at every one of the five library corners. Issue #548 (part of #486).
- **Verdict**: {verdict}. Liberty signal pins {'agree' if agree else '**DISAGREE**'} across corners
  ({'the single-corner proof is valid' if agree else 'the proof is NOT valid; per-corner results are reported as found'}).
- **Scope**: offline connectivity proof only. No `klt extract`/`klt sta` run, no SPEF,
  no timing number, no closure claim; README/signoff timing claims are unchanged.

## Provenance

- **Commit**: `{git(REPO_ROOT, 'rev-parse', 'HEAD') or 'unknown'}`
- **Inputs (sha256)**:
  - `layout/adc-top/sar_ctrl/sar_ctrl.def`: `{result['inputs']['def_sha256']}`
  - `layout/adc-top/sar_ctrl/sar_ctrl.v`: `{result['inputs']['verilog_sha256']}`
- **PDK**: variant `{pdk.variant}`, open_pdks `{pdk.version}`, cell library `{base.CELL_LIBRARY}`
- **Command** (from the repo root, PDK discoverable):
  `python3 design/sar-logic/flow/prove_no_net_sar_ctrl.py`

## Result per corner

| Corner | Outputs examined | `no_net` | Outputs neither `has_net` nor `no_net` | Liberty sha256 |
|---|---|---|---|---|
{rows}

- Liberty signal pins identical across the five corners: **{agree}**.
- Exempt set equals the expected set at every corner: **{equal}**.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-record", action="store_true", help="print the record instead of writing it")
    args = ap.parse_args()
    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    result = prove_all_corners(pdk)
    rid = record_id(REPO_ROOT, _dt.datetime.now())
    text = render(result, rid, pdk)
    if args.no_record:
        print(text)
    else:
        path = base.RECORDS_DIR / f"{rid}.{base.LIB_TAG}.no_net_prover.md"
        path.write_text(text)
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0 if result["signal_pins_agree"] and result["exempt_set_equal"] else 2


if __name__ == "__main__":
    sys.exit(main())
