#!/usr/bin/env python3
"""Audit what statistical / mismatch data the gf180mcu PDK actually ships.

Several of the findings in ``sim/device-characterization-report.md`` are
NEGATIVE: the PDK does not model capacitor mismatch, does not model junction
leakage, does not apply the MiM voltage coefficient. A negative claim needs
evidence just as much as a positive one, and a claim about a *model library*
cannot be substantiated by a testbench -- a simulation can only ever show that
some effect did not appear, never that the library does not contain it.

So this script is the evidence for those claims: it reads the installed PDK's
own model files and reports, per device class, exactly which statistical
constructs are present and which are absent, quoting the file and line where
each is (or is not) found.

It is also a REGRESSION GUARD. Each finding is asserted, so a PDK revision that
adds capacitor mismatch or junction leakage makes this script exit non-zero and
say which claim changed, rather than silently invalidating a report that has
already been consumed by four downstream design issues.

    python3 sim/tools/pdk_mismatch_audit.py            # audit + assert
    python3 sim/tools/pdk_mismatch_audit.py --report   # audit, never fail

Exit codes:  0 every finding still holds  ·  1 a finding changed
             ·  3 the PDK could not be resolved
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.pdk import PdkNotFound, find_pdk  # noqa: E402

EXIT_OK = 0
EXIT_FINDING_CHANGED = 1
EXIT_ENVIRONMENT = 3


@dataclass
class Finding:
    """One auditable statement about what the PDK does or does not model."""

    key: str
    question: str
    expected_present: bool
    #: Human-readable consequence for this block if the finding holds.
    consequence: str
    present: bool | None = None
    evidence: list[str] = field(default_factory=list)

    @property
    def holds(self) -> bool:
        return self.present is expected_bool(self.expected_present)

    def render(self) -> str:
        state = "PRESENT" if self.present else "ABSENT"
        verdict = "ok" if self.holds else "CHANGED"
        lines = [f"[{verdict:>7}] {self.key}: {state}", f"          {self.question}"]
        lines += [f"          | {line}" for line in self.evidence]
        lines.append(f"          -> {self.consequence}")
        return "\n".join(lines)


def expected_bool(value: bool) -> bool:
    return value


def _section(text: str, name: str) -> str:
    """Body of a ``.lib <name> ... .endl`` section, case-insensitively."""
    pattern = re.compile(
        rf"^\.lib\s+{re.escape(name)}\s*$(.*?)^\.endl(\s+{re.escape(name)})?\s*$",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


def _grep(text: str, pattern: str, path: Path, limit: int = 3) -> list[str]:
    out: list[str] = []
    regex = re.compile(pattern, re.IGNORECASE)
    for lineno, line in enumerate(text.splitlines(), start=1):
        if regex.search(line):
            out.append(f"{path.name}:{lineno}: {line.strip()[:110]}")
            if len(out) >= limit:
                break
    return out


def audit(models: Path, mim_models: Path) -> list[Finding]:
    text = models.read_text(errors="replace")
    mim_text = mim_models.read_text(errors="replace")

    findings: list[Finding] = []

    # -- 1. MOS local mismatch ------------------------------------------------
    fets_mm = _section(text, "fets_mm")
    f = Finding(
        key="mos-local-mismatch",
        question="Does the PDK model local (device-to-device) MOS threshold mismatch?",
        expected_present=True,
        consequence=(
            "A_Vt is available for #9 / #14. Measured back out of the models in "
            "sim/device-mismatch-mc/."
        ),
    )
    f.present = bool(re.search(r"par_vth\s*=", fets_mm)) and "sw_stat_mismatch" in fets_mm
    f.evidence = _grep(text, r"^\s*\+?\s*par_vth\s*=", models, limit=2)
    f.evidence += _grep(text, r"mis_vth\s*\*\s*sw_stat_mismatch", models, limit=1)
    findings.append(f)

    # -- 2. Capacitor local mismatch -- the one the CDAC needs ----------------
    mimcap_stat = _section(text, "mimcap_statistical")
    f = Finding(
        key="cap-local-mismatch",
        question=(
            "Does the PDK model local mismatch for ANY capacitor, i.e. anything "
            "gated on sw_stat_mismatch rather than sw_stat_global?"
        ),
        expected_present=False,
        consequence=(
            "sigma(dC/C) for the CDAC unit cap CANNOT be obtained from this PDK. "
            "#8 and #14 must use an external (literature or foundry) matching "
            "coefficient, explicitly flagged and derated."
        ),
    )
    cap_scopes = re.findall(r"mc_c_cox_\w+\s*=\s*'[^']*'", mimcap_stat)
    f.present = any("sw_stat_mismatch" in scope for scope in cap_scopes)
    f.evidence = [f"{models.name}: mimcap_statistical defines {len(cap_scopes)} mc_c_cox_* term(s)"]
    f.evidence += [f"{models.name}: {scope[:100]}" for scope in cap_scopes[:2]]
    f.evidence.append(
        f"{models.name}: every one is gated on sw_stat_global (die-global), "
        "which cancels in a capacitor RATIO and so contributes no CDAC DNL/INL"
        if cap_scopes and not f.present
        else f"{models.name}: no mc_c_cox_* terms found at all"
    )
    findings.append(f)

    # -- 3. MOS-cap statistics ------------------------------------------------
    f = Finding(
        key="moscap-statistics",
        question="Does the PDK ship ANY statistical section for the MOS capacitor?",
        expected_present=False,
        consequence=(
            "The MOS cap has process corners (moscap_ff/ss) but no statistical "
            "model of any kind, global or local."
        ),
    )
    f.present = bool(_section(text, "moscap_statistical"))
    f.evidence = [
        f"{models.name}: sections named *_statistical present: "
        + ", ".join(sorted(set(re.findall(r"^\.lib\s+(\w*statistical\w*)\s*$", text,
                                          re.IGNORECASE | re.MULTILINE))))
    ]
    findings.append(f)

    # -- 4. MoM / lateral-flux capacitor --------------------------------------
    f = Finding(
        key="mom-capacitor-model",
        question="Does the PDK ship a MoM / lateral-flux (finger) capacitor model?",
        expected_present=False,
        consequence=(
            "A MoM-based CDAC cannot be simulated from a model corner at all; it "
            "would have to be substantiated by parasitic extraction. This closes "
            "off the 'MoM alternative' half of the CDAC device question for #8."
        ),
    )
    f.present = bool(
        re.search(r"\.subckt\s+\S*(?:mom|fringe|finger|vpp|xcmvpp)\S*", text + mim_text, re.I)
    )
    subckts = re.findall(r"^\.subckt\s+(\S*cap\S*)", text + mim_text, re.IGNORECASE | re.MULTILINE)
    f.evidence = [
        f"capacitor subckts defined across {models.name} + {mim_models.name}: "
        + ", ".join(sorted({s.split("_m")[0] for s in subckts}))
    ]
    findings.append(f)

    # -- 5. MiM voltage coefficient in the SIMULATED path ---------------------
    f = Finding(
        key="mim-voltage-coefficient-active",
        question=(
            "Is the MiM capacitor's voltage coefficient (c_vcr1 / c_vcr2) actually "
            "wired into the simulated device, or only defined as a dead parameter?"
        ),
        expected_present=False,
        consequence=(
            "Simulated CDAC results contain NO MiM voltage-coefficient effect. The "
            "datasheet coefficients exist but must be applied by hand; "
            "sim/device-cdac-cap/ measures the simulated VCC as exactly zero."
        ),
    )
    active_cap_lines = [
        line.strip()
        for line in mim_text.splitlines()
        if re.match(r"^\s*c_cap\s", line, re.IGNORECASE)
    ]
    f.present = any("c_vcr" in line for line in active_cap_lines)
    f.evidence = [f"{mim_models.name}: {len(active_cap_lines)} active c_cap instance line(s)"]
    f.evidence += [f"{mim_models.name}: {line[:110]}" for line in active_cap_lines[:1]]
    f.evidence += _grep(mim_text, r"^\s*\*\s*c_cap\s.*c_vcr", mim_models, limit=1) or [
        f"{mim_models.name}: (no commented-out bias-dependent c_cap line found)"
    ]
    f.evidence += _grep(mim_text, r"c_vcr1\s*=", mim_models, limit=1)
    findings.append(f)

    # -- 6. Junction (drain-body diode) leakage -------------------------------
    f = Finding(
        key="mos-junction-leakage",
        question=(
            "Do the 3.3 V FET model cards define a junction saturation current "
            "density (JS / JSW / JSWG), i.e. drain-body diode leakage?"
        ),
        expected_present=False,
        consequence=(
            "Simulated off-state / hold-droop leakage is CHANNEL leakage only and "
            "is a lower bound at 125 C. sim/device-switch-leakage/ carries a "
            "null-control branch proving it in simulation."
        ),
    )
    fet_section = _section(text, "nfet_03v3_t") + _section(text, "pfet_03v3_t")
    f.present = bool(re.search(r"\bjs(w|wg)?\s*=", fet_section, re.IGNORECASE))
    present_jparams = sorted(
        set(re.findall(r"\b(cj|cjsw|pb|njs|js|jsw|jswg)\s*=", fet_section, re.IGNORECASE))
    )
    f.evidence = [
        f"{models.name}: junction-related params in nfet_03v3_t / pfet_03v3_t: "
        + (", ".join(p.lower() for p in present_jparams) or "(none)")
    ]
    findings.append(f)

    # -- 7. Flicker-noise corner switch ---------------------------------------
    f = Finding(
        key="flicker-noise-corner-switch",
        question="Does the PDK expose a worst-case flicker-noise corner switch?",
        expected_present=True,
        consequence=(
            "Any flicker-noise number from this PDK must state its fnoicor "
            "setting. sim/device-comparator-flicker-noise/ measures both."
        ),
    )
    noise_section = _section(text, "noise_corner")
    f.present = "fnoicor" in noise_section
    f.evidence = _grep(text, r"nfet_03v3_noia\s*=", models, limit=1)
    f.evidence += _grep(text, r"pfet_03v3_noia\s*=", models, limit=1)
    findings.append(f)

    # -- 8. Resistor local mismatch (contrast case) ---------------------------
    f = Finding(
        key="resistor-local-mismatch",
        question="Does the PDK model local mismatch for resistors?",
        expected_present=True,
        consequence=(
            "Contrast case: the PDK's authors DID model local mismatch where they "
            "had data (MOS and resistors), which is what makes its absence for "
            "capacitors a real data gap rather than an oversight of the whole "
            "statistical framework."
        ),
    )
    f.present = bool(re.search(r"mis_r\s*\*\s*sw_stat_mismatch", text))
    f.evidence = _grep(text, r"mis_r\s*\*\s*sw_stat_mismatch", models, limit=1)
    findings.append(f)

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the audit but always exit 0 (do not assert the findings)",
    )
    args = parser.parse_args(argv)

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT

    models = pdk.model_lib
    mim_models = models.parent / "sm141064_mim.ngspice"
    if not mim_models.is_file():
        print(f"error: MIM model file not found next to {models}", file=sys.stderr)
        return EXIT_ENVIRONMENT

    print(f"PDK      : {pdk.path} (open_pdks {pdk.version}, variant {pdk.variant})")
    print(f"models   : {models}")
    print(f"MIM      : {mim_models}")
    print()

    findings = audit(models, mim_models)
    for finding in findings:
        print(finding.render())
        print()

    changed = [f for f in findings if not f.holds]
    if changed:
        print(f"{len(changed)} finding(s) CHANGED against this PDK revision:")
        for finding in changed:
            print(f"  - {finding.key}: recorded as "
                  f"{'present' if finding.expected_present else 'absent'}, "
                  f"now {'present' if finding.present else 'absent'}")
        print()
        print("sim/device-characterization-report.md and the records that cite it")
        print("were written against the previous behaviour. Re-run the affected")
        print("experiments and append new records before trusting either.")
        return EXIT_OK if args.report else EXIT_FINDING_CHANGED

    print(f"all {len(findings)} findings hold against this PDK revision.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
