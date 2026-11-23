#!/usr/bin/env python3
"""Issue #943: build the per-corner `klt sim` requests (and bodies) the record ran.

Run order (from the repo root, with sim/.work/issue-943/ as the work tree and
the pinned PDK on PDK_ROOT / GF180_PDK_PATH):
  python3 sim/adc-enob-fft/investigations/20261123-issue-943-data/setup_variants.py
  python3 sim/adc-enob-fft/investigations/20261123-issue-943-data/build_requests.py [OUT]
then submit each request with
  klt sim <request.json> --backend batch --submit-only --wait-for-capacity 600 --format json
and collect with
  klt sim <request.json> --backend batch --attach <job_id> -o <outdir> --format json

Both legs are extracted 256-sample captures on the four 2.97 V governing
points, one corner per request, timeout 3300 s (a 256-sample extracted corner
took 1144-1253 s / 18.7 GB peak RSS on #935's fleet run):
  c1-*   bin 125, named exactly as #935's C1 requests so the emitted JSONs
         reproduce #935's committed requests byte-for-byte (diff them).
  t115-* bin 115, the second tone.
"""
import hashlib
import json
import pathlib
import sys

SIM = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SIM))
from harness import batch as B, corners as C, pdk as P, testbench as T  # noqa: E402

WORK = SIM / ".work" / "issue-943"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORK / "req"
pdk = P.find_pdk()
POINTS = (("ss", -40), ("ss", 27), ("ss", 125), ("ff", 125))


def emit(sub, name, tb, plan, proc, temps, supply, timeout):
    req = B.build_request(tb, pdk, plan, C.resolve_corners(proc), temps,
                          netlist_name=name + ".spice", timeout_s=timeout)
    d = OUT / sub
    d.mkdir(parents=True, exist_ok=True)
    body = B.build_body(tb, pdk, supply_v=supply)
    (d / f"{name}.json").write_text(json.dumps(req, indent=1, sort_keys=True))
    (d / f"{name}.spice").write_text(body)
    print(name, hashlib.sha256(body.encode()).hexdigest())


tb = T.load(WORK / "t125" / "testbench")
plan = B.check_exportable(tb)
for p, t in POINTS:
    emit("t125", f"c1-{p}-{t}c-2p97v", tb, plan, [p], [t], 2.97, 3300)
tb = T.load(WORK / "t115" / "testbench")
plan = B.check_exportable(tb)
for p, t in POINTS:
    emit("t115", f"t115-{p}-{t}c-2p97v", tb, plan, [p], [t], 2.97, 3300)
