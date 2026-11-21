#!/usr/bin/env python3
"""Issue #935: collate the collected batch outputs into points.json / points.md.

Reads sim/.work/issue-935/{jobs,out,req}/ (the klt --submit-only / --attach layout),
copies each corner's ngspice.log into <DATA>/logs/<leg>/<corner-id>.log and runs
sim/adc-enob-fft/testbench/analyze_fft.py's analyze() over it. Composed ENOB uses the
same noise terms as compose_enob_by_corner.py (same-corner comparator noise record +
same-temperature kT/C at C_side 8.827 pF); the width legs are schematic and 125 C only.
"""
import hashlib
import json
import math
import pathlib
import re
import shutil
import sys

DATA = pathlib.Path(__file__).resolve().parent
SIM = DATA.parents[2]
WORK = SIM / ".work" / "issue-935"
sys.path.insert(0, str(SIM / "adc-enob-fft" / "testbench"))
import analyze_fft as af  # noqa: E402
import compose_enob_by_corner as ce  # noqa: E402

noise = ce.read_noise_rows(ce.DEFAULT_NOISE)
LSB_UV = 3.3 / 1024 * 1e6
VOLT = {"2p97v": "2.97v", "3p3v": "3.30v", "3p63v": "3.63v"}
rows = []
for sub in sorted(WORK.joinpath("jobs").glob("*.submit.json")):
    name = sub.name[: -len(".submit.json")]
    leg = name.split("-")[0]
    submit = json.loads(sub.read_text())
    rep = json.loads((WORK / "out" / name / "report.json").read_text())
    env = rep["environment"]
    rem = env["remote"]
    n, b = (64, 31) if leg.startswith("c2") else (256, 125)
    req_path = next(WORK.joinpath("req").glob(f"*/{name}.json"))
    body_path = req_path.with_suffix(".spice")
    volt = VOLT[name.split("-")[-1]]
    for c in rep["corners"]:
        proc, _, tdir = c["corner_id"].split("/")
        temp = int(tdir.replace("C", ""))
        cid = f"{proc}_{temp}c_{volt}"
        src = next((WORK / "out" / name).glob(f"{proc}_novdd_{'n' if temp < 0 else ''}{abs(temp)}C/ngspice.log"))
        dst = DATA / "logs" / leg / f"{cid}.log"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        text = dst.read_text()
        r = af.analyze(af.extract_codes(text, n), b)
        sig_lsb = None
        enob_c = None
        if cid in noise:
            ktc = math.sqrt(2 * ce.K_B * (temp + 273.15) / (8.827e-12)) * 1e6
            sig_lsb = math.hypot(noise[cid], ktc) / LSB_UV
            enob_c = af.analyze(af.extract_codes(text, n), b, sigma_extra_lsb=sig_lsb)["enob_composed_bits"]
        rows.append({
            "leg": leg, "corner_id": cid, "n": n, "bin": b,
            "sfdr_db": r["sfdr_db"], "thd_db": r["thd_db"], "sndr_db": r["sndr_db"],
            "enob_distortion_only": r["enob_bits"], "enob_composed": enob_c,
            "gmin_stepping_failed": "gmin stepping failed" in text.lower(),
            "klt_status": c["status"], "runtime_s": c.get("runtime_s"),
            "job_id": submit["job_id"], "request_sha256": submit["request_sha256"],
            "body_sha256": hashlib.sha256(body_path.read_bytes()).hexdigest(),
            "netlist_identity": env.get("netlist_identity"),
            "models_lib_sha256": env.get("models_lib_sha256"),
            "ngspice": env.get("engine_version"),
            "runner_klt": rem.get("runner_klt_version"),
            "client_klt": rem.get("client_klt_version"),
            "instance_type": rem.get("instance_type"),
            "ngspice_options": env.get("ngspice_options"),
        })
(DATA / "points.json").write_text(json.dumps(rows, indent=1) + "\n")
with open(DATA / "points.md", "w") as f:
    f.write("| leg | corner-id | N/bin | SFDR dB | THD dB | dist-only ENOB | composed ENOB | gmin failed | job id | body sha256 |\n")
    f.write("|---|---|---|---:|---:|---:|---:|---|---|---|\n")
    for x in rows:
        ec = "n/a" if x["enob_composed"] is None else f"{x['enob_composed']:.3f}"
        f.write(f"| {x['leg']} | `{x['corner_id']}` | {x['n']}/{x['bin']} | {x['sfdr_db']:.2f} | {x['thd_db']:.2f} | "
                f"{x['enob_distortion_only']:.3f} | {ec} | {'yes' if x['gmin_stepping_failed'] else 'no'} | "
                f"`{x['job_id']}` | `{x['body_sha256'][:12]}` |\n")
print(len(rows), "points")
