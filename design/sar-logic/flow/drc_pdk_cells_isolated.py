#!/usr/bin/env python3
"""Run `klt drc --deck gf180mcu` on single PDK standard cells in isolation
(issue #520), to classify the 208 `nplus.space.pcomp.1` /
`pplus.enclosing.comp.1` markers on the routed `sar_ctrl` macro
(`layout/adc-top/sar_ctrl/sar_ctrl.gds`) as real violations or deck artifacts.

Each of `endcap`, `filltie`, `fill_1`, `fill_2` of `gf180mcu_fd_sc_mcu7t5v0`
is copied out of the PDK library GDS into its own one-cell GDS (in a temp
directory; nothing is written to the PDK) and checked on its own. Outputs,
all new files (append-only evidence):

    design/sar-logic/flow/sar_ctrl/reports/<rid>.mcu7t5v0.cell_drc_<cell>.json
    design/sar-logic/flow/sar_ctrl/records/<rid>.mcu7t5v0.cell_drc.md

Usage: drc_pdk_cells_isolated.py [--pdk-gds PATH]   (default: ~/.volare gf180mcuD)
Single-unit, local `klt drc` runs only.
"""
import argparse
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import klayout.db as db

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "layout"))
from klt_env import sha256  # noqa: E402
FLOW = REPO / "design/sar-logic/flow/sar_ctrl"
MACRO_REPORT = FLOW / "reports/20261015-221946-0a0ab20b.mcu7t5v0.pnr_drc.json"
LIB = "gf180mcu_fd_sc_mcu7t5v0"
CELLS = ("endcap", "filltie", "fill_1", "fill_2")
DEFAULT_GDS = (Path.home() / ".volare/volare/gf180mcu/versions/"
               "c6d73a35f524070e85faff4a6a9eef49553ebc2b/gf180mcuD/libs.ref" /
               LIB / "gds" / f"{LIB}.gds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdk-gds", type=Path, default=DEFAULT_GDS)
    args = ap.parse_args()
    git = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short=8", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    now = datetime.datetime.now(datetime.timezone.utc)
    rid = f"{now:%Y%m%d-%H%M%S}-{git}"
    lib = db.Layout()
    lib.read(str(args.pdk_gds))
    macro = json.loads(MACRO_REPORT.read_text())
    macro_counts: dict = {}
    for v in macro["violations"]:
        macro_counts[v["source_cell"]] = macro_counts.get(v["source_cell"], 0) + 1
    rows = []
    prov = {}
    with tempfile.TemporaryDirectory() as tmp:
        for cell in CELLS:
            name = f"{LIB}__{cell}"
            one = db.Layout()
            one.dbu = lib.dbu
            one.create_cell(name).copy_tree(lib.cell(name))
            gds = Path(tmp) / f"{cell}.gds"
            one.write(str(gds))
            out = subprocess.run(["klt", "drc", str(gds), "--deck", "gf180mcu", "--top",
                                  name, "--format", "json"], capture_output=True, text=True)
            d = json.loads(out.stdout)
            d["file"] = f"<one-cell extract of {name} from the PDK library GDS>"
            (FLOW / f"reports/{rid}.mcu7t5v0.cell_drc_{cell}.json").write_text(
                json.dumps(d, indent=1) + "\n")
            prov = d["provenance"]
            rows.append((cell, d["status"], d["violation_count"], d["rule_counts"],
                         macro_counts.get(name, 0)))
    lines = [
        f"# Record {rid} (mcu7t5v0, isolated PDK-cell DRC)", "",
        f"- **Record ID**: {rid}.mcu7t5v0.cell_drc",
        "- **Claim**: classifies the macro's 208 DRC markers (issue #520); see README",
        "  `layout/adc-top/sar_ctrl/README.md` \"What is and is not claimed\".",
        f"- **Tool versions**: klt `{prov['klt_version']}`, klayout `{prov['klayout_version']}`",
        f"- **Deck**: gf180mcu, `{prov['deck']['content_hash']}`",
        f"- **PDK library GDS**: `{args.pdk_gds}` sha256 `{sha256(args.pdk_gds)}`",
        f"- **Macro report compared**: `{MACRO_REPORT.relative_to(REPO)}` (klt "
        f"{macro['provenance']['klt_version']}, same deck hash: "
        f"{macro['provenance']['deck']['content_hash'] == prov['deck']['content_hash']})",
        f"- **Commit**: `{git}`", "",
        "| cell | isolated status | isolated violations | isolated rules | markers attributed to this cell in macro |",
        "|---|---|---|---|---|",
    ]
    for cell, st, n, rc, m in rows:
        lines.append(f"| `{cell}` | {st} | {n} | {rc} | {m} |")
    lines += ["", "Reproduce: `python3 design/sar-logic/flow/drc_pdk_cells_isolated.py` "
              "(needs `klt` on PATH and the `klayout` module).", ""]
    (FLOW / f"records/{rid}.mcu7t5v0.cell_drc.md").write_text("\n".join(lines))
    print(rid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
