#!/usr/bin/env python3
"""Issue #943 diagnostic tree: the two-tone 256-sample capture on the four
governing extracted points.

Everything lands under sim/.work/issue-943/ (git-ignored). The variant decks
are not committed; the record carries their hashes and this script rebuilds
them from git commit b281aa8 -- the same base the #935 C1 leg used, so the
bin-125 leg here is byte-identical to #935's c1-ext deck and its requests
reproduce #935's committed request JSONs byte-for-byte (checked by
build_requests.py's caller; see the record).

Legs (both extracted, 2.97 V, N = 256):
  t125/testbench  bin 125 (488281.25 Hz) -- #935's C1 tone, re-run as the
                  same-tone repeat leg. Deck bytes = #935's tb_extracted256.
  t115/testbench  bin 115 (449218.75 Hz) -- the second tone. Odd, gcd(115,
                  256) = 1 (115 = 5*23, 256 = 2^8), and its harmonic bins
                  h*115 mod 256 (h = 2..12: 230, 89, 204, 63, 178, 37, 152,
                  11, 241, 100 ...) and their mirrors are disjoint from bin
                  125's (250, 119, 244, 113, 238, 107, 232, 101, 226, 95,
                  220 ...) and from the N=64 tone's 256-equivalent (bin 124:
                  248, 116, 240, 108, 232, 96, 224, 92, 216, 84 ...), so the
                  two tones' SFDR figures read different aliased distortion
                  products instead of re-reading the same ones.
"""
import hashlib
import json
import subprocess
from pathlib import Path

WT = Path(__file__).resolve().parents[4]
SIM = WT / "sim"
BASE = SIM / ".work" / "issue-943"

BASE_COMMIT = "b281aa8"
DECK_REL = "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice"
MANIFEST_REL = "sim/adc-enob-fft/testbench/tb.json"
DECK_SHA = "b0baf1325167d110677bf5f5d8ce4156c8b138ba9d6c9f64fe1846ef5c04ef75"
MANIFEST_SHA = "4be757c33797e8bc5d6553c2e5a8239d806382e5d2ca2729af34bc3042677961"

FREQ_OLD = "484375.000000"
TRAN_64 = "tran 1n 66.000u 0 2n"
TRAN_256 = "tran 1n 258.000u 0 2n"  # last sample s255 at 257950n + 50n margin

TONES = {
    "t125": {
        "freq": "488281.250000",   # bin 125 of 256 at 1 MS/s; gcd(125, 256) = 1
        "bin": 125,
        "hz": 488281.25,
        "netlist": "tb_extracted256_t125.spice",
        "name": "issue943-t125-bin125",
    },
    "t115": {
        "freq": "449218.750000",   # bin 115 of 256 at 1 MS/s; gcd(115, 256) = 1
        "bin": 115,
        "hz": 449218.75,
        "netlist": "tb_extracted256_t115.spice",
        "name": "issue943-t115-bin115",
    },
}


def git_show(rel: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(WT), "show", f"{BASE_COMMIT}:{rel}"],
        check=True, capture_output=True,
    ).stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def retone(deck_text: str, freq_new: str) -> str:
    assert deck_text.count(FREQ_OLD) == 1, "expected exactly one stimulus frequency line"
    return deck_text.replace(FREQ_OLD, freq_new)


def sample_meas(i: int) -> str:
    return f"meas tran s{i:03d} FIND v(se_code) AT={2950.0 + 1000.0 * i}n"


def build_256_manifest(base: dict, tone: dict) -> dict:
    m = dict(base)
    m["name"] = tone["name"]
    m["description"] = (
        "Issue #943 re-sizing diagnostic: 256-sample capture of the baseline "
        "record 20261105-125230-b281aa8 extracted deck at bin "
        f"{tone['bin']} ({tone['hz']} Hz), for the four 2.97 V governing points."
    )
    m["netlist"] = tone["netlist"]
    m["netlist_provenance"] = (
        "extracted (issue #943 re-sizing diagnostic: baseline record "
        "20261105-125230-b281aa8 deck, sole delta the input tone re-derived for "
        f"N=256 bin {tone['bin']}; 484375 -> {tone['hz']} Hz)"
    )

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
    ev["fft_input_hz"] = tone["hz"]
    ev["fft_bin"] = tone["bin"]
    ev["fft_window"] = "none"
    ev["fft_fs_hz"] = 1000000.0
    ev["data_provenance"] = (
        "simulated -- issue #943 re-sizing diagnostic on the baseline b281aa8 "
        "extracted deck; not a campaign record"
    )
    ev["notes"] = [
        "ISSUE #943 RE-SIZING DIAGNOSTIC: two-tone 256-sample capture that "
        "re-sizes the class-A/B deciding measurements after #935's C1 leg "
        "failed two of three pass conditions. #867/#886 re-mint the production "
        "evidence.",
        "COHERENCE: N = 256 samples capture exactly M = "
        f"{tone['bin']} whole input cycles; gcd({tone['bin']}, 256) = 1, so the "
        "samples land on 256 distinct input phases and window = none stays "
        "valid. N is a power of two; no zero padding.",
        "TONE SEPARATION: bin 125 is #935's C1 tone re-run (same-tone repeat "
        "leg); bin 115 is the second tone. The two tones' harmonic bins (and "
        "their mirrors) are disjoint through the 12th harmonic, so a "
        "tone-to-tone SFDR difference measures the phase-set/frequency scatter "
        "of the capture rather than re-reading the same aliased products.",
        "Sample timing, amplitude (vref/2*0.94), initial phase (0) and the 2 us "
        "stimulus delay are unchanged from the 64-sample capture; the transient "
        "and the coverage-witness windows extend through sample 255 (258 us).",
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

    for leg, tone in TONES.items():
        d = BASE / leg / "testbench"
        d.mkdir(parents=True, exist_ok=True)
        deck256 = retone(deck.decode(), tone["freq"])
        (d / tone["netlist"]).write_text(deck256)
        m256 = build_256_manifest(base, tone)
        (d / "tb.json").write_text(json.dumps(m256, indent=2) + "\n")
        print(f"{leg}: deck sha256 {sha256(deck256.encode())}  "
              f"bin {tone['bin']}  {tone['hz']} Hz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
