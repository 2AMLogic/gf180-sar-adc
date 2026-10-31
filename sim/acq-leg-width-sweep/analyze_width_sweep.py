#!/usr/bin/env python3
"""Collate the acquisition-leg width sweep (issue #429).

Reuses ``sim/dr0019-cu-sweep/analyze_sweep.py``'s record reader (raw per-corner
logs -> ``analyze_fft.py`` -> SFDR / composed ENOB, noise re-derived at this
point's ``C_side``), pointed at this experiment's records/corners.  Stdlib only.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "dr0019-cu-sweep" / "analyze_sweep.py"


# Newer klt prints the per-sample measurement as ``s000 = 7.32e2`` (the ``m_code_``
# prefix of the older runner is gone); accept both so committed (x1.0, pre-#636)
# and artifact-store logs collate with the same extractor arithmetic.
_SAMPLE_ANY = re.compile(
    r"^(?:m_code_)?s(\d+)\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)\s*$"
)


def _base():
    spec = importlib.util.spec_from_file_location("analyze_sweep_base", BASE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    orig = mod.load_analyze_fft

    def load():
        fft = orig()
        fft._SAMPLE_RE = _SAMPLE_ANY
        return fft

    mod.load_analyze_fft = load
    return mod


def _fetch_stored_logs(record_id: str, corners: Path) -> None:
    """Fetch a record's per-corner logs from the artifact store (DR-0041).

    Records taken after #636 commit only a manifest; the hash-verified bytes
    come back with ``klt artifact get`` (needs ``$KLT_ARTIFACT_BROKER``).
    """
    manifest = (
        HERE.parent.parent / "manifests" / "artifacts"
        / f"acq-leg-width-sweep-{record_id}.manifest.json"
    )
    if not manifest.is_file():
        return
    out = corners / record_id
    for entry in json.loads(manifest.read_text())["entries"]:
        name = entry["name"]
        if not (name.endswith(".log") and f"/corners/{record_id}/" in name):
            continue
        out.mkdir(parents=True, exist_ok=True)
        dest = out / Path(name).name
        res = subprocess.run(
            ["klt", "artifact", "get", f"{manifest}#{name}", "-o", str(dest)],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            print(f"warning: could not fetch {name}: {res.stderr.strip()}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base = _base()
    # Records whose harness verdict is ERROR (blocked batch submissions, kept as
    # append-only blocker evidence) carry no codes and must not be collated.
    with tempfile.TemporaryDirectory() as tmp:
        keep = Path(tmp) / "records"
        corners = Path(tmp) / "corners"
        keep.mkdir()
        corners.mkdir()
        for rec in sorted((HERE / "records").glob("*.md")):
            if re.search(r"\*\*Overall: ERROR\*\*", rec.read_text()):
                continue
            (keep / rec.name).write_text(rec.read_text())
            committed = HERE / "corners" / rec.stem
            if committed.is_dir():
                (corners / rec.stem).symlink_to(committed)
            else:
                _fetch_stored_logs(rec.stem, corners)
        points = base.read_points(keep, corners)
    if not points:
        print(f"error: no usable records under {HERE / 'records'}", file=sys.stderr)
        return 1
    if "--markdown" in argv:
        print("| acq-leg width | worst SFDR (dB) | at | worst composed ENOB (bits) | at | harness | max V_REF droop (mV) | record |")
        print("|---|---|---|---|---|---|---|---|")
        for p in points:
            droop = "-" if p["vref_droop_mv_max"] is None else f"{p['vref_droop_mv_max']:.3f}"
            print(
                f"| x{p['acq_switch_scale']:g} | {p['worst_sfdr_db']:.2f} | `{p['worst_sfdr_corner']}` | "
                f"{p['worst_enob_bits']:.3f} | `{p['worst_enob_corner']}` | {p['harness_verdict']} | "
                f"{droop} | `{p['record_id']}` |"
            )
    else:
        print(json.dumps({"points": points}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
