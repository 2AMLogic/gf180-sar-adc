#!/usr/bin/env python3
"""Issue #935: build the per-corner `klt sim` requests (and bodies) the record ran.

Run order (from the repo root, with sim/.work/issue-935/ as the work tree):
  python3 sim/adc-enob-fft/investigations/20261121-issue-935-data/setup_variants.py
  python3 sim/adc-enob-fft/investigations/20261121-issue-935-data/build_requests.py [OUT]
then submit each request with
  klt sim <request.json> --backend batch --submit-only --wait-for-capacity 600 --format json
and collect with
  klt sim <request.json> --backend batch --attach <job_id> -o <outdir> --format json

C1 (256-sample extracted, 4 requests, one corner each, timeout 3300 s), C2 (64-sample
baseline deck + options.ngspice_options, 4 requests, timeout 3300 s) and the three
schematic width legs (256-sample, one request per supply x tt/ss/ff @125 C, 1000 s).
"""
import hashlib
import json
import pathlib
import sys

SIM = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SIM))
from harness import batch as B, corners as C, pdk as P, testbench as T  # noqa: E402

WORK = SIM / ".work" / "issue-935"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORK / "req"
C2_OPTS = {"reltol": 1e-4, "abstol": 1e-13, "vntol": 1e-8,
           "gminsteps": 200, "srcsteps": 200, "itl4": 100}
pdk = P.find_pdk()


def emit(sub, name, tb, plan, proc, temps, supply, timeout, opts=None):
    req = B.build_request(tb, pdk, plan, C.resolve_corners(proc), temps,
                          netlist_name=name + ".spice", timeout_s=timeout)
    if opts:
        req["options"]["ngspice_options"] = opts
    d = OUT / sub
    d.mkdir(parents=True, exist_ok=True)
    body = B.build_body(tb, pdk, supply_v=supply)
    (d / f"{name}.json").write_text(json.dumps(req, indent=1))
    (d / f"{name}.spice").write_text(body)
    print(name, hashlib.sha256(body.encode()).hexdigest())


def load(leg):
    tb = T.load(WORK / leg / "testbench")
    return tb, B.check_exportable(tb)


tb, plan = load("c1-ext")
for p, t in (("ss", -40), ("ss", 27), ("ss", 125), ("ff", 125)):
    emit("c1", f"c1-{p}-{t}c-2p97v", tb, plan, [p], [t], 2.97, 3300)
tb, plan = load("c2-tight")
for p, t in (("tt", -40), ("tt", 27), ("ff", -40), ("ff", 27)):
    emit("c2", f"c2-{p}-{t}c-2p97v", tb, plan, [p], [t], 2.97, 3300, C2_OPTS)
for w in ("w15", "w175", "w2068"):
    tb, plan = load(w)
    for v, s in ((2.97, "2p97v"), (3.30, "3p3v"), (3.63, "3p63v")):
        emit(w, f"{w}-125c-{s}", tb, plan, ["tt", "ss", "ff"], [125], v, 1000)
