#!/usr/bin/env python3
"""Does the extracted post-layout netlist support Monte Carlo at all, and if
so on which devices? -- issue #89 **Scope item 2**:

    "Monte Carlo re-run (#14's bench) on the extracted netlist, if the
    extraction flow's parasitic/mismatch models support statistical
    variation -- state explicitly if not, rather than silently skipping."

That sentence has two halves and they get different answers, so neither an
unqualified "ran it" nor an unqualified "not supported" would be true. This
script measures both halves instead of asserting either:

**MOS devices: SUPPORTED, and demonstrated here.** `klt extract --pdk
gf180mcuD` writes every FET as a real PDK subcircuit call (`X$149 ... vdd
pfet_03v3 L=... W=...`), the same `fets_mm`-wrapped subckt the schematic
deck instantiates. So the PDK's own `sw_stat_mismatch` switch reaches every
one of the extracted core's ~296 FETs exactly as it reaches the schematic
core's. This script turns that switch on, runs a real Monte Carlo population
of full transistor-level conversions on the **extracted** core, and reports
sigma of the transition error at the array's worst carry.

**CDAC capacitors: NOT SUPPORTED -- on EITHER netlist, and not because of
the extraction.** `sim/tools/pdk_mismatch_audit.py`'s `cap-local-mismatch`
finding (re-asserted by this script before it runs anything) is that
gf180mcu models capacitor statistics only through `sw_stat_global`, which is
die-global and therefore cancels exactly in a capacitor RATIO -- so it
contributes no CDAC DNL/INL by construction. The extracted MiM caps bind to
the same `cap_mim_2f0_m4m5_noshield` subckt with the same absent local
term. `sim/mc-cdac-mismatch/` consequently runs the dominant #14 term
behaviorally off a literature matching coefficient, and a post-layout re-run
of *that* deck would resimulate the same behavioral coefficient against a
netlist whose capacitors still have no statistical model. Extraction changes
nothing about it, so re-running it would produce a new record with no new
information -- which is why this script reports the finding instead.

    python3 layout/adc-top/parasitics/mc_extracted_core.py --samples 40
    python3 layout/adc-top/parasitics/mc_extracted_core.py --samples 8 --json out.json

**The null control is not optional.** `sim/device-mismatch-mc/`'s own header
records three ways an ngspice Monte Carlo silently collapses to a frozen
draw and reports sigma ~ 0 while looking healthy. So every run here also
executes the identical population with `sw_stat_mismatch=0` and asserts the
mismatch-on sigma is at least `--min-sigma-ratio` times the mismatch-off
sigma. A run whose "Monte Carlo" was not varying anything fails instead of
being recorded.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness import corners as C  # noqa: E402
from harness import pdk as PDK  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "gen_extracted_core_tb", HERE / "gen_extracted_core_tb.py"
)
G = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("gen_extracted_core_tb", G)
_spec.loader.exec_module(G)  # type: ignore[union-attr]

gtop = G.gtop
NGSPICE = "ngspice"

#: The probed transition this population is taken at. 255->256 is the
#: weight-256 sub-array MSB carry: the largest charge-division ratio this
#: array forms, independently the slowest-settling trial
#: (`sim/cdac-bit-settling/`) and the analytically worst code for mismatch
#: (`sim/mc-cdac-mismatch/`). `sim/adc-inl-dnl/`'s deck header derives that
#: choice at length; it is not re-derived here.
TRANSITION = 256

#: Seed for the mismatch-on population. `setseed` is the ONE ngspice seeding
#: control `sim/device-mismatch-mc/` verified actually works (`set rndseed`
#: is silently ignored; `.options seed` freezes the draw).
SEED = 20260805

#: Conversions of settling before the measured one -- same convention as
#: `gen_adc_top.INL_WARMUP_CONV`, imported rather than restated.
WARMUP = None  # resolved from gtop at composition time


def _decision_ns() -> tuple[float, float]:
    """`(measured-conversion start, its deciding strobe)` in ns."""
    t0 = gtop.INL_WARMUP_CONV * gtop.CONV_NS
    trial = gtop._inl_trial(TRANSITION)
    return t0, t0 + gtop.trial_decision_ns(trial) - 0.05


def compose_deck(top: str, pdk: PDK.Pdk, corner: C.Corner, temp_c: float,
                 vdd: float, samples: int, mismatch: bool, seed: int,
                 num_threads: int = 0) -> str:
    """The complete Monte Carlo deck for one (corner, mismatch) population.

    ``num_threads`` (0 = leave ngspice's default) emits ``set num_threads=N``,
    the same scheduling knob ``sim/harness/runner.compose_deck`` documents: an
    OpenMP-built ngspice defaults to one thread per processor, which on a
    shared/contended host makes this ~1300-device deck burn most of its CPU in
    spin-waits. It changes no circuit and no measured value.
    """
    tag = G.TAG
    t0, tdec = _decision_ns()
    end_ns = (gtop.INL_WARMUP_CONV + 1) * gtop.CONV_NS

    lines = [
        "* Monte Carlo on the EXTRACTED post-layout core -- issue #89 Scope item 2",
        f"* corner={corner.name} temp={temp_c}C vdd={vdd}V pdk={pdk.variant}",
        f"* population={samples}  sw_stat_mismatch={int(mismatch)}  seed={seed}",
        f".param vdd_val={vdd!r}",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    lines += [
        "",
        "* ---- the PDK's own statistical switches ------------------------------",
        "* These MUST come AFTER the includes above. design.ngspice sets",
        "*   sw_stat_global = 0 / sw_stat_mismatch = 0",
        "* and ngspice's .param is last-wins, so setting them ahead of the",
        "* include is silently overridden by the PDK default and the whole Monte",
        "* Carlo collapses to sigma = 0 while still printing a plausible mean --",
        "* observed directly on this deck before the ordering was fixed. That is",
        "* why sim/device-mismatch-mc/testbench/tb_mismatch_mc.spice puts them in",
        "* the netlist FRAGMENT (which the harness emits after its includes)",
        "* rather than in the manifest params; this deck composes its own",
        "* preamble, so it has to place them by hand.",
        "* sw_stat_global is held at 0: this is a mismatch-only population, not",
        "* mismatch + global process spread (the PVT axes own that).",
        f".param sw_stat_mismatch={int(mismatch)}",
        ".param sw_stat_global=0",
    ]
    lines.append(f".temp {temp_c!r}")
    lines.append("")

    lines += gtop._preamble("{vdd_val/1024}")
    lines.append("")
    lines.append(
        f"* ---- input held at transition {TRANSITION} + 0.25 LSB "
        "-------------------------"
    )
    lines.append(
        f"v{tag}vinp {tag}_vinp 0 dc {{({TRANSITION}+0.25)*lsb}}"
    )
    lines.append(f"v{tag}vinn {tag}_vinn 0 dc {{vcm}}")
    lines.append("")

    pins, core_text = G.core_pins(top)
    lines.append(gtop.comparator_block())
    lines.append(gtop.sar.library())
    lines.append(core_text)
    lines += G._core_extracted(tag, "0", pins, top)
    lines += G.shadow_dac_and_error(tag)

    lines += [
        "",
        ".control",
        "set numdgt=10",
        "set noaskquit",
    ]
    if num_threads:
        lines.append(f"set num_threads={num_threads}")
    lines += [
        f"setseed {seed}",
        "let n = 0",
        f"let nmax = {samples}",
        "let s = 0",
        "let s2 = 0",
        "dowhile n < nmax",
        "  reset",
        f"  tran 1n {end_ns / 1000:.3f}u 0 2n",
        f"  meas tran e FIND v({tag}_err) AT={tdec:.3f}n",
        "  let s = s + e",
        "  let s2 = s2 + e*e",
        # `meas` echoes its own result at 6 significant figures regardless of
        # numdgt, so a `print e` here yields TWO differently-rounded lines per
        # draw and any `^e =` parser silently reports 2N samples. Copy into a
        # distinctly-named vector and print that: one line per draw, at the
        # deck's own numdgt.
        "  let esamp = e",
        "  print esamp",
        "  let n = n + 1",
        "end",
        "let mc_mean = s/nmax",
        # Clamped: for a frozen population the two terms cancel to a tiny
        # NEGATIVE radicand and sqrt() returns NaN. See population_stats().
        "let mc_sigma = sqrt(max(s2/nmax - (s/nmax)^2, 0))",
        "print mc_mean",
        "print mc_sigma",
        ".endc",
        ".end",
    ]
    return "\n".join(lines) + "\n"


_SCALAR = r"^\s*{name}\s*=\s*([-\d.eE+]+)\s*$"
_SAMPLE = re.compile(r"^\s*esamp\s*=\s*([-\d.eE+]+)\s*$", re.MULTILINE)


def _scalar(out: str, name: str) -> float:
    m = re.search(_SCALAR.format(name=name), out, re.MULTILINE)
    return float(m.group(1)) if m else float("nan")


def population_stats(values: list[float]) -> tuple[float, float]:
    """`(mean, population sigma)` of the parsed draws.

    Computed here rather than read off the deck's own `mc_sigma`, because the
    deck computes sigma as ``sqrt(s2/n - (s/n)^2)`` and that form is
    catastrophically cancelling: for the **null control**, where every draw is
    bit-identical, the two terms differ only in floating-point noise and the
    radicand comes out very slightly NEGATIVE, so ngspice returns NaN. A NaN
    there propagates into the on/off sigma ratio and fails the run for
    "not varying" -- the exact opposite of what an exactly-frozen control
    means, and it happened on the first full 120-draw population. Python's
    two-pass form returns a clean 0.0, which is both correct and the value the
    null-control assertion is written against.
    """
    n = len(values)
    if n == 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return mean, math.sqrt(max(var, 0.0))


def run_population(top: str, pdk: PDK.Pdk, corner_name: str, temp_c: float,
                   vdd: float, samples: int, mismatch: bool, seed: int,
                   timeout_s: int, log_path: Path | None = None,
                   num_threads: int = 0) -> dict:
    corner = C.CORNERS[corner_name]
    deck = compose_deck(top, pdk, corner, temp_c, vdd, samples, mismatch, seed,
                        num_threads=num_threads)
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        path = work / "mc_extracted_core.spice"
        path.write_text(deck)
        proc = subprocess.run([NGSPICE, "-b", str(path)], capture_output=True,
                              text=True, cwd=work, timeout=timeout_s, check=False)
        out = proc.stdout + "\n" + proc.stderr
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(out)
    values = [float(v) for v in _SAMPLE.findall(out)]
    mean, sigma = population_stats(values)
    return {
        "corner_id": f"{corner_name}_{temp_c:g}c_{vdd:.2f}v",
        "corner": corner_name,
        "temp_c": temp_c,
        "vdd": vdd,
        "mismatch": bool(mismatch),
        "seed": seed,
        "n_requested": samples,
        "n_parsed": len(values),
        "terr_lsb": values,
        "mean_lsb": mean,
        "sigma_lsb": sigma,
        # The deck's own scalars, kept as an independent cross-check of the
        # numbers above rather than as their source -- see population_stats().
        "deck_mean_lsb": _scalar(out, "mc_mean"),
        "deck_sigma_lsb": _scalar(out, "mc_sigma"),
        "wall_s": round(time.monotonic() - t0, 2),
    }


def audit_cap_finding() -> dict:
    """Re-assert the PDK capacitor-mismatch finding this script reports.

    Imported from `sim/tools/pdk_mismatch_audit.py` rather than restated, so
    a PDK revision that starts modelling capacitor local mismatch changes
    this script's answer instead of leaving a stale sentence behind.
    """
    spec = importlib.util.spec_from_file_location(
        "pdk_mismatch_audit", REPO / "sim" / "tools" / "pdk_mismatch_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Must be registered in sys.modules BEFORE exec_module: pdk_mismatch_audit
    # defines @dataclass classes, and dataclass's own field-type resolution
    # does `sys.modules.get(cls.__module__)` -- skipping this raises
    # AttributeError: 'NoneType' object has no attribute '__dict__' the first
    # time a dataclass is defined. Same fix already applied to every other
    # dynamic import in this directory (see gen_extracted_core_tb.py's
    # `sys.modules["gen_adc_top"] = gtop`).
    sys.modules.setdefault("pdk_mismatch_audit", mod)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    models = mod.find_pdk().model_lib
    findings = {
        f.key: f
        for f in mod.audit(models, models.parent / "sm141064_mim.ngspice")
    }
    cap = findings["cap-local-mismatch"]
    mos = findings["mos-local-mismatch"]
    return {
        "cap_local_mismatch_present": bool(cap.present),
        "cap_finding_holds": bool(cap.holds),
        "cap_evidence": list(cap.evidence),
        "mos_local_mismatch_present": bool(mos.present),
        "mos_finding_holds": bool(mos.holds),
        "mos_evidence": list(mos.evidence),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--top", default="ADC_TOP", choices=["ADC_TOP"])
    ap.add_argument("--corner", default="tt")
    ap.add_argument("--temp", type=float, default=27.0)
    ap.add_argument("--vdd", type=float, default=3.3)
    ap.add_argument("--samples", type=int, default=40,
                    help="mismatch-on population size")
    ap.add_argument("--control-samples", type=int, default=6,
                    help="mismatch-OFF null-control population size (its sigma "
                         "must collapse; see the module docstring)")
    ap.add_argument("--min-sigma-ratio", type=float, default=100.0,
                    help="mismatch-on sigma must exceed the null control's by "
                         "at least this factor, else the run is not a Monte "
                         "Carlo and exits non-zero")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--ngspice-threads", type=int, default=0, metavar="N",
                    help="cap ngspice's own OpenMP thread count ('set "
                         "num_threads=N'); 0 leaves its default. Scheduling "
                         "only -- changes no measured value.")
    ap.add_argument("--json", help="write the full result JSON here")
    ap.add_argument("--log-dir", help="write raw ngspice logs here")
    args = ap.parse_args(argv)

    if not PDK.pdk_available():
        print("SKIP: no gf180mcu PDK found (see sim/harness/pdk.py).", file=sys.stderr)
        return 0
    pdk = PDK.find_pdk()

    audit = audit_cap_finding()
    print("PDK statistical support (sim/tools/pdk_mismatch_audit.py):")
    print(f"  MOS local mismatch : "
          f"{'PRESENT' if audit['mos_local_mismatch_present'] else 'ABSENT'} "
          f"(finding {'holds' if audit['mos_finding_holds'] else 'CHANGED'})")
    print(f"  cap local mismatch : "
          f"{'PRESENT' if audit['cap_local_mismatch_present'] else 'ABSENT'} "
          f"(finding {'holds' if audit['cap_finding_holds'] else 'CHANGED'})")
    if not (audit["mos_finding_holds"] and audit["cap_finding_holds"]):
        print("error: a PDK statistical finding this script reports has changed; "
              "re-read sim/tools/pdk_mismatch_audit.py before recording anything.",
              file=sys.stderr)
        return 1
    print()

    log_dir = Path(args.log_dir) if args.log_dir else None

    populations = []
    for mismatch, n in ((True, args.samples), (False, args.control_samples)):
        label = "mismatch-on" if mismatch else "null-control (mismatch-off)"
        print(f"running {label}: {n} conversions of the extracted core ...")
        pop = run_population(
            args.top, pdk, args.corner, args.temp, args.vdd, n, mismatch,
            args.seed, args.timeout,
            log_path=(log_dir / f"{'mm_on' if mismatch else 'mm_off'}.log")
            if log_dir else None,
            num_threads=args.ngspice_threads,
        )
        populations.append(pop)
        print(f"  n={pop['n_parsed']}/{pop['n_requested']}  "
              f"mean={pop['mean_lsb']:+.6f} LSB  sigma={pop['sigma_lsb']:.6e} LSB  "
              f"({pop['wall_s']:.0f}s)")

    on, off = populations
    ok = on["n_parsed"] == on["n_requested"] and off["n_parsed"] == off["n_requested"]
    ratio = (on["sigma_lsb"] / off["sigma_lsb"]) if off["sigma_lsb"] else float("inf")
    varying = ratio >= args.min_sigma_ratio
    print()
    print(f"sigma ratio on/off : {ratio:.3g} (must be >= {args.min_sigma_ratio:g})")
    print(f"population complete: {ok}")

    result = {
        "claim": "issue #89 Scope item 2: whether the parasitic-extracted "
                 "post-layout netlist supports statistical (Monte Carlo) "
                 "variation, measured rather than asserted. MOS local "
                 "mismatch reaches every extracted FET (demonstrated by the "
                 "population below); CDAC capacitor local mismatch is absent "
                 "from the PDK on BOTH netlists (audited, not simulated -- a "
                 "simulation cannot prove a model library lacks a construct).",
        "netlist_provenance": "extracted (remediated: PMOS bodies -> vdd, "
                              "input rails promoted to vinp/vinn pins, MiM "
                              "caps on the native PDK subckt) wired to a "
                              "schematic comparator + rung-1 SAR controller + "
                              "DR-0013 input network",
        "transition": TRANSITION,
        "pdk": pdk.provenance(),
        "pdk_statistical_audit": audit,
        "populations": populations,
        "sigma_ratio_on_off": ratio,
        "null_control_passed": bool(varying),
        "populations_complete": bool(ok),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")

    if not ok:
        print("FAIL: a population did not return every requested sample.",
              file=sys.stderr)
        return 1
    if not varying:
        print("FAIL: the mismatch-on population is not varying -- this is the "
              "frozen-draw failure sim/device-mismatch-mc/ documents, not a "
              "result.", file=sys.stderr)
        return 1
    print("PASS: the extracted netlist accepts MOS-mismatch Monte Carlo and "
          "the population varies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
