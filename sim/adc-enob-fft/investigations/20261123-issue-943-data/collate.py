#!/usr/bin/env python3
"""Issue #943: collate the collected batch outputs into points.json / points.md.

Reads sim/.work/issue-943/{jobs,out,req}/ (the klt --submit-only / --attach layout),
copies each corner's ngspice.log into <DATA>/logs/<leg>/<corner-id>.log (git-ignored;
stored in the artifact store, see the record's Stored evidence section) and runs
sim/adc-enob-fft/testbench/analyze_fft.py's analyze() over it at the leg's bin.
Composed ENOB uses the same noise terms as compose_enob_by_corner.py (same-corner
comparator noise record + same-temperature kT/C at C_side 8.827 pF).

Comparison columns (not claims re-measured here):
  sfdr_db_935_bin125 -- the #935 C1 leg's bin-125 figure for the same corner,
      read from the committed 20261121-issue-935-data/points.json.
  sfdr_db_430_n64    -- the #430 baseline (N = 64, bin 31) figure, from the
      #935 record's Sec 3 table (which itself cites the #430 record).
"""
import hashlib
import json
import math
import pathlib
import shutil
import sys

DATA = pathlib.Path(__file__).resolve().parent
SIM = DATA.parents[2]
WORK = SIM / ".work" / "issue-943"
REF935 = DATA.parent / "20261121-issue-935-data"
sys.path.insert(0, str(SIM / "adc-enob-fft" / "testbench"))
import analyze_fft as af  # noqa: E402
import compose_enob_by_corner as ce  # noqa: E402

noise = ce.read_noise_rows(ce.DEFAULT_NOISE)
LSB_UV = 3.3 / 1024 * 1e6
# #430 baseline SFDR (N=64, bin 31), 20261105-125230-b281aa8, as tabulated by
# the #935 record Sec 3 (its "#430, N=64" column).
SFDR_430 = {"ss_-40c_2.97v": 57.96, "ss_27c_2.97v": 59.53,
            "ss_125c_2.97v": 61.09, "ff_125c_2.97v": 60.41}
ref935 = {}
for row in json.loads((REF935 / "points.json").read_text()):
    if row["leg"] == "c1":
        ref935[row["corner_id"]] = row["sfdr_db"]

LEG_BIN = {"c1": 125, "t115": 115}
rows = []
for sub in sorted((DATA / "jobs").glob("*.submit.json")):
    name = sub.name[: -len(".submit.json")]
    leg = name.split("-")[0]
    submit = json.loads(sub.read_text())
    rep = json.loads((WORK / "out" / name / "report.json").read_text())
    env = rep["environment"]
    rem = env["remote"]
    n, b = 256, LEG_BIN[leg]
    req_path = next(WORK.joinpath("req").glob(f"*/{name}.json"))
    body_path = req_path.with_suffix(".spice")
    for c in rep["corners"]:
        proc, _, tdir = c["corner_id"].split("/")
        temp = int(tdir.replace("C", ""))
        cid = f"{proc}_{temp}c_2.97v"
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
            "sfdr_db_935_bin125": ref935.get(cid),
            "sfdr_db_430_n64": SFDR_430.get(cid),
            "delta_vs_935_bin125": (None if ref935.get(cid) is None
                                    else round(r["sfdr_db"] - ref935[cid], 2)),
            "delta_vs_430_n64": (None if SFDR_430.get(cid) is None
                                 else round(r["sfdr_db"] - SFDR_430[cid], 2)),
            "gmin_stepping_failed": "gmin stepping failed" in text.lower(),
            "klt_status": c["status"], "runtime_s": c.get("runtime_s"),
            "job_id": submit["job_id"], "request_sha256": submit["request_sha256"],
            "body_sha256": hashlib.sha256(body_path.read_bytes()).hexdigest(),
            "log_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
            "netlist_identity": env.get("netlist_identity"),
            "models_lib_sha256": env.get("models_lib_sha256"),
            "ngspice": env.get("engine_version"),
            "runner_klt": rem.get("runner_klt_version"),
            "client_klt": rem.get("client_klt_version"),
            "instance_type": rem.get("instance_type"),
        })
(DATA / "points.json").write_text(json.dumps(rows, indent=1) + "\n")
with open(DATA / "points.md", "w") as f:
    f.write("| leg | corner-id | N/bin | SFDR dB | THD dB | dist-only ENOB | composed ENOB | #935 bin125 | delta | #430 N=64 | delta | gmin failed | job id | log sha256 |\n")
    f.write("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|\n")
    for x in rows:
        ec = "n/a" if x["enob_composed"] is None else f"{x['enob_composed']:.3f}"
        f.write(f"| {x['leg']} | `{x['corner_id']}` | {x['n']}/{x['bin']} | {x['sfdr_db']:.2f} | {x['thd_db']:.2f} | "
                f"{x['enob_distortion_only']:.3f} | {ec} | {x['sfdr_db_935_bin125']:.2f} | "
                f"{x['delta_vs_935_bin125']:+.2f} | {x['sfdr_db_430_n64']:.2f} | {x['delta_vs_430_n64']:+.2f} | "
                f"{'yes' if x['gmin_stepping_failed'] else 'no'} | `{x['job_id']}` | `{x['log_sha256'][:12]}` |\n")
print(len(rows), "points")
