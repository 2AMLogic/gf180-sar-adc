#!/usr/bin/env python3
"""Issue #935 diagnostic tree: 256-sample captures (C1) + tightened-solver re-runs (C2).

Everything lands under sim/.work/issue-935/ (git-ignored). The variant decks are
not committed; the record carries their hashes and this script rebuilds them
from git commit b281aa8.

Legs:
  c1-ext/testbench    256-sample variant of the b281aa8 extracted deck
                      (sole deck delta: input tone 484375 -> 488281.25 Hz,
                      bin 125 of 256 at 1 MS/s).
  c2-tight/testbench  the b281aa8 extracted deck bytes VERBATIM, 64-sample
                      capture unchanged, tightened solver options via the
                      manifest "options" key.
  w15/ w175/ w2068/   schematic width variants (gen_cu_variant.py at the
                      ratified C_u) with the same 256-sample re-tone.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[4]
SIM = WT / "sim"
BASE = SIM / ".work" / "issue-935"

BASE_COMMIT = "b281aa8"
DECK_REL = "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice"
MANIFEST_REL = "sim/adc-enob-fft/testbench/tb.json"
DECK_SHA = "b0baf1325167d110677bf5f5d8ce4156c8b138ba9d6c9f64fe1846ef5c04ef75"
MANIFEST_SHA = "4be757c33797e8bc5d6553c2e5a8239d806382e5d2ca2729af34bc3042677961"

FREQ_OLD = "484375.000000"
FREQ_NEW = "488281.250000"          # bin 125 of 256 at 1 MS/s; gcd(125, 256) = 1
TRAN_64 = "tran 1n 66.000u 0 2n"
TRAN_256 = "tran 1n 258.000u 0 2n"  # last sample s255 at 257950n + 50n margin
C2_OPTIONS = ["reltol=1e-4 abstol=1e-13 vntol=1e-8 gmin_steps=200 src_steps=200 itl4=100"]


def git_show(rel: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(WT), "show", f"{BASE_COMMIT}:{rel}"],
        check=True, capture_output=True,
    ).stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def retoned(deck_text: str) -> str:
    assert deck_text.count(FREQ_OLD) == 1, "expected exactly one stimulus frequency line"
    return deck_text.replace(FREQ_OLD, FREQ_NEW)


def sample_meas(i: int) -> str:
    return f"meas tran s{i:03d} FIND v(se_code) AT={2950.0 + 1000.0 * i}n"


def build_256_manifest(base: dict, name: str, description: str, netlist: str,
                       provenance: str, data_provenance: str) -> dict:
    m = dict(base)
    m["name"] = name
    m["description"] = description
    m["netlist"] = netlist
    m["netlist_provenance"] = provenance

    old = list(base["analyses"])
    assert old[0] == TRAN_64
    decerr = [a for a in old if " se_aerrh " in a]
    tail_old = [a for a in old if a.startswith("meas tran cmax")
                or a.startswith("meas tran cmin")
                or a.startswith("meas tran vrefhi")
                or a.startswith("meas tran vreflo")]
    assert len(tail_old) == 4
    analyses = ([TRAN_256]
                + [sample_meas(i) for i in range(256)]
                + [a.replace("66000.0n", "258000.0n") for a in tail_old]
                + decerr)
    m["analyses"] = analyses

    measure = {f"code_s{i:03d}": f"s{i:03d}" for i in range(256)}
    for k, v in base["measure"].items():
        if not k.startswith("code_s"):
            measure[k] = v
    m["measure"] = measure

    checks = {k: dict(v) for k, v in base["checks"].items()}
    checks.get("vref_droop_mv", {}).pop("min_spread_pct_by_axis", None)
    m["checks"] = checks

    ev = dict(base["evidence"])
    ev["record_kind"] = "characterization"
    ev["fft_n"] = 256
    ev["fft_input_hz"] = 488281.25
    ev["fft_bin"] = 125
    ev["fft_window"] = "none"
    ev["fft_fs_hz"] = 1000000.0
    ev["data_provenance"] = data_provenance
    ev["notes"] = [
        "ISSUE #935 DIAGNOSTIC (C1): candidate/measurement-validity capture, NOT a "
        "campaign record -- #867/#886 re-mint the production evidence. 256 samples, "
        "one 256-point bin above the 64-sample tone (bin 125 vs bin 31), so the 64 "
        "input phases are not repeated four times.",
        "COHERENCE: N = 256 samples capture exactly M = 125 whole input cycles; "
        "gcd(125, 256) = 1 (125 = 5^3, 256 = 2^8), so the samples land on 256 "
        "distinct input phases and window = none stays valid. N is a power of two; "
        "no zero padding.",
        "Sample timing, amplitude (vref/2*0.94), initial phase (0) and the 2 us "
        "stimulus delay are unchanged from the 64-sample capture; the transient and "
        "the coverage-witness windows extend through sample 255 (258 us).",
    ]
    m["evidence"] = ev
    return m


def build_64_c2_manifest(base: dict) -> dict:
    m = dict(base)
    m["name"] = "issue935-c2-tight"
    m["description"] = (
        "Issue #935 C2 solver-sensitivity diagnostic: the baseline record "
        "20261105-125230-b281aa8 capture (64 samples, bin 31) re-run with tightened "
        "ngspice solver options on the four 2.97 V points that carried the 'Dynamic "
        "gmin stepping failed' warning."
    )
    m["netlist"] = "tb_extracted_c2.spice"
    m["netlist_provenance"] = (
        "extracted (issue #935 C2 diagnostic: baseline record 20261105-125230-b281aa8 "
        "deck bytes verbatim; the ONLY delta is the tightened solver options carried "
        "in this manifest's options key)"
    )
    m["options"] = list(C2_OPTIONS)
    checks = {k: dict(v) for k, v in base["checks"].items()}
    checks.get("vref_droop_mv", {}).pop("min_spread_pct_by_axis", None)
    m["checks"] = checks
    ev = dict(base["evidence"])
    ev["record_kind"] = "characterization"
    ev["data_provenance"] = (
        "simulated -- issue #935 C2 solver-sensitivity diagnostic on the baseline "
        "b281aa8 extracted deck; not a campaign record"
    )
    ev["notes"] = [
        "ISSUE #935 DIAGNOSTIC (C2): the 64-sample capture and bin 31 are kept "
        "IDENTICAL to the baseline; the only change is the tightened solver set "
        "'reltol=1e-4 abstol=1e-13 vntol=1e-8 gmin_steps=200 src_steps=200 "
        "itl4=100' (ngspice defaults: reltol=1e-3 abstol=1e-12 vntol=1e-6 "
        "gmin_steps=10 src_steps=10 itl4=10) vs the baseline's pure defaults.",
    ]
    m["evidence"] = ev
    return m


def main() -> int:
    deck = git_show(DECK_REL)
    manifest = git_show(MANIFEST_REL)
    assert sha256(deck) == DECK_SHA, "recovered deck hash mismatch"
    assert sha256(manifest) == MANIFEST_SHA, "recovered manifest hash mismatch"
    base = json.loads(manifest)

    (BASE / "recovered").mkdir(parents=True, exist_ok=True)
    (BASE / "recovered" / "tb_adc_enob_fft_extracted.spice").write_bytes(deck)
    (BASE / "recovered" / "tb.json").write_bytes(manifest)

    legs = {}

    # --- C1 extracted 256 -------------------------------------------------
    d = BASE / "c1-ext" / "testbench"
    d.mkdir(parents=True, exist_ok=True)
    deck256 = retoned(deck.decode())
    (d / "tb_extracted256.spice").write_text(deck256)
    m256 = build_256_manifest(
        base,
        name="issue935-c1-ext256",
        description=(
            "Issue #935 C1 diagnostic: 256-sample re-capture of the baseline record "
            "20261105-125230-b281aa8 extracted deck at bin 125 (488.28125 kHz), for "
            "the four 2.97 V governing points."
        ),
        netlist="tb_extracted256.spice",
        provenance=(
            "extracted (issue #935 C1 diagnostic: baseline record "
            "20261105-125230-b281aa8 deck, sole delta the input tone re-derived for "
            "N=256 bin 125; 484375 -> 488281.25 Hz)"
        ),
        data_provenance=(
            "simulated -- issue #935 C1 256-sample diagnostic on the baseline "
            "b281aa8 extracted deck; not a campaign record"
        ),
    )
    (d / "tb.json").write_text(json.dumps(m256, indent=2) + "\n")
    legs["c1-ext"] = d

    # --- C2 tightened 64 --------------------------------------------------
    d = BASE / "c2-tight" / "testbench"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tb_extracted_c2.spice").write_bytes(deck)
    mc2 = build_64_c2_manifest(base)
    (d / "tb.json").write_text(json.dumps(mc2, indent=2) + "\n")
    legs["c2-tight"] = d

    # --- width legs (schematic, gen_cu_variant at ratified C_u) -----------
    for scale, dirname in (("1.5", "w15"), ("1.75", "w175"), ("2.068", "w2068")):
        d = BASE / dirname / "testbench"
        d.mkdir(parents=True, exist_ok=True)
        out = d / f"tb_sw{scale}.spice"
        subprocess.run(
            [sys.executable, str(SIM / "dr0019-cu-sweep" / "gen_cu_variant.py"),
             "--c-unit-ff", "35.6528", "--acq-switch-scale", scale,
             "--out", str(out)],
            check=True, capture_output=True,
        )
        variant = out.read_text()
        variant = retoned(variant)
        out.write_text(variant)
        m = build_256_manifest(
            base,
            name=f"issue935-{dirname}-256",
            description=(
                f"Issue #935 C1 width-ordering diagnostic: 256-sample re-capture of "
                f"the schematic deck at acquisition-leg width x{scale} (issue #429 "
                f"series), bin 125, over the nine 125 C hot corners."
            ),
            netlist=out.name,
            provenance=(
                f"schematic (issue #935 diagnostic: acquisition-leg width x{scale} "
                f"from gen_cu_variant.py at ratified C_u = 35.6528 fF, input tone "
                f"re-derived for N=256 bin 125)"
            ),
            data_provenance=(
                f"simulated -- issue #935 256-sample width diagnostic x{scale}; not "
                f"a campaign record"
            ),
        )
        (d / "tb.json").write_text(json.dumps(m, indent=2) + "\n")
        legs[dirname] = d

    # --- validate every manifest through the harness loader ---------------
    sys.path.insert(0, str(SIM))
    from harness import testbench as tb_mod  # noqa: E402

    for name, d in legs.items():
        tb = tb_mod.load(d)
        print(f"{name:10s} manifest OK  experiment={tb.experiment}  "
              f"netlist={tb.netlist.name}")
        for p in sorted(d.iterdir()):
            print(f"           {p.name:34s} sha256={sha256(p.read_bytes())}")
    print("\nparent deck sha256      :", sha256(deck))
    print("parent manifest sha256  :", sha256(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
