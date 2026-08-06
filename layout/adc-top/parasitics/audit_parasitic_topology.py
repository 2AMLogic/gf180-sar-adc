#!/usr/bin/env python3
"""Answer one structural question about a `klt extract --parasitics` netlist:
**is the extracted parasitic resistance in the signal path, or is it a stub?**

    python3 layout/adc-top/parasitics/audit_parasitic_topology.py            # every
                                                                            # committed
                                                                            # extraction
    python3 layout/adc-top/parasitics/audit_parasitic_topology.py <file.spice> ...
    python3 layout/adc-top/parasitics/audit_parasitic_topology.py --format json

WHY THIS EXISTS
---------------
`sim/extracted-delta-summary.md` SS6.3 blocks rate closure and the DR-0012/13
gain-error row on a post-layout re-take of the CDAC settling network's
resistance (`R_WORST_BIT_OHM`). Before spending a PVT campaign on that, it is
worth establishing *what the extraction can express at all*. This script
answers that from the committed netlists, mechanically, so the answer is
checkable rather than asserted from reading a few lines.

`klt extract --parasitics` has written two different topologies over this
repo's life, and this script reads BOTH -- `reports/` is append-only evidence,
so a netlist extracted at an older pin must keep auditing the same way it did
when its record was minted.

**Shunt-stub form** (every pin up to and including `af5791b`), one pair per net:

    R<net> <net> <net>__par <ohms>
    C<net> <net>__par <ground> <farads>

**Star-split form** (the `875eac3` pin, upstream `klayout-tools#593`), one leg
per device terminal plus one hub capacitance:

    R<net>_t<k> <net>__t<k> <net> <ohms>      (one per terminal on the net)
    C<net>      <net> <ground> <farads>
    ... and every device card names `<net>__t<k>`, never `<net>`, for that
    terminal.

Whether an `R` carries any signal current depends on which node the *devices*
sit on. Two possibilities:

  * **in-path** -- some device/cap terminal is on the resistor's far node
    (`<net>__par` in the shunt-stub form, `<net>__t<k>` in the star-split
    form), so current flowing between that terminal and the rest of the net
    goes through `R`. The extraction then models series/IR resistance, and a
    post-layout R_on or settling-resistance number can differ from the
    schematic one. The star-split form is in-path BY CONSTRUCTION -- every
    terminal gets its own leg -- which is the whole point of the `875eac3`
    pin; this script is what confirms that rather than assuming it.
  * **stub** -- every device/cap terminal is on `<net>` itself and the far
    node is reached only by the `C`. `R` then carries no signal current at
    all; it only puts the parasitic capacitance behind a small series
    resistance (a lossy load), and no DC or resistive measurement can see it.

This script classifies every parasitic net in a netlist into those two buckets
by looking at which node each non-parasitic card's terminals land on. It makes
no measurement and no spec-line claim -- it reports netlist topology.

Exit codes
----------
    0  audited successfully (the verdict is in the output, not the exit code)
    1  a file could not be read/parsed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORTS = HERE / "reports"

#: The suffix the SHUNT-STUB form gives the internal node of each net's
#: lumped RC pair (also reported as `parasitics.nets[].internal_node` in the
#: extractor's own JSON summary at those pins).
PAR_SUFFIX = "__par"

#: The per-terminal leg-node suffix the STAR-SPLIT form uses
#: (`parasitics.nets[].terminals[].leg_net` in the extractor's JSON summary
#: since `875eac3`). `<net>__t0`, `<net>__t1`, ...
_LEG_RE = re.compile(r"^(?P<hub>.+)__t\d+$")

_CONT = re.compile(r"^\s*\+")


def _cards(text: str) -> list[list[str]]:
    """Whitespace-split tokens of every non-comment, continuation-joined card."""
    joined: list[str] = []
    for line in text.splitlines():
        if _CONT.match(line):
            if joined:
                joined[-1] += " " + line.lstrip()[1:].strip()
            continue
        joined.append(line)
    out: list[list[str]] = []
    for line in joined:
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("."):
            continue
        out.append(s.split())
    return out


def _terminal_count(tokens: list[str]) -> int:
    """How many leading tokens after the name are node names, for this card."""
    head = tokens[0][0].upper()
    if head == "X":
        # subckt call: name n1 .. nk subckt [params] -- terminals are every
        # token up to the last non-`k=v` token (the subckt name).
        params = 0
        for tok in reversed(tokens):
            if "=" in tok:
                params += 1
            else:
                break
        return len(tokens) - params - 2  # drop the name and the subckt name
    if head in ("R", "C", "L", "V", "I"):
        return 2
    if head == "M":
        return 4
    if head == "B" or head == "E" or head == "G":
        return 2
    return 0


def audit(text: str, name: str = "") -> dict:
    """Classify every parasitic net of one extracted netlist."""
    cards = _cards(text)
    # net -> {far node -> ohms}. One entry for the shunt-stub form, one per
    # terminal leg for the star-split form.
    par_r: dict[str, dict[str, float]] = {}
    par_c: dict[str, float] = {}  # net -> farads
    forms: set[str] = set()
    for tok in cards:
        if len(tok) < 4:
            continue
        head = tok[0][0].upper()
        a, b = tok[1], tok[2]
        if head == "R" and b.endswith(PAR_SUFFIX):
            # shunt stub: R<net> <net> <net>__par
            try:
                par_r.setdefault(a, {})[b] = float(tok[3])
            except ValueError:
                continue
            forms.add("shunt-stub")
        elif head == "R" and _LEG_RE.match(a) and _LEG_RE.match(a).group("hub") == b:
            # star leg: R<net>_t<k> <net>__t<k> <net>
            try:
                par_r.setdefault(b, {})[a] = float(tok[3])
            except ValueError:
                continue
            forms.add("star-split")
        elif head == "C" and a.endswith(PAR_SUFFIX):
            try:
                par_c[a[: -len(PAR_SUFFIX)]] = float(tok[3])
            except ValueError:
                continue
        elif head == "C" and len(tok) >= 4 and not _LEG_RE.match(a):
            # star form puts the net's C on the HUB. Only counted for nets
            # that actually carry parasitic legs, so a real design capacitor
            # is never mistaken for one (checked below).
            try:
                par_c.setdefault(a, float(tok[3]))
            except ValueError:
                continue

    # Which nodes do the REAL (non-parasitic) cards touch?
    far_nodes = {node for legs in par_r.values() for node in legs}
    on_far: dict[str, int] = {}
    for tok in cards:
        head = tok[0][0].upper()
        # skip the parasitic elements themselves
        if head in ("R", "C") and any(
            t.endswith(PAR_SUFFIX) or _LEG_RE.match(t) for t in tok[1:3]
        ):
            continue
        n = _terminal_count(tok)
        for node in tok[1 : 1 + n]:
            if node in far_nodes:
                on_far[node] = on_far.get(node, 0) + 1

    nets = []
    for net, legs in sorted(par_r.items()):
        farads = par_c.get(net, 0.0)
        touching = sum(on_far.get(node, 0) for node in legs)
        nets.append(
            {
                "net": net,
                "internal_node": sorted(legs)[0] if len(legs) == 1 else sorted(legs),
                "leg_count": len(legs),
                "resistance_ohm": sum(legs.values()),
                "max_leg_resistance_ohm": max(legs.values()),
                "capacitance_f": farads,
                "device_terminals_on_internal_node": touching,
                "topology": "in-path" if touching else "stub",
            }
        )
    n_stub = sum(1 for n in nets if n["topology"] == "stub")
    return {
        "name": name,
        "topology_form": "+".join(sorted(forms)) if forms else "none",
        "parasitic_nets": len(nets),
        "stub_nets": n_stub,
        "in_path_nets": len(nets) - n_stub,
        "total_resistance_ohm": sum(n["resistance_ohm"] for n in nets),
        "max_resistance_ohm": max((n["resistance_ohm"] for n in nets), default=0.0),
        "total_capacitance_f": sum(n["capacitance_f"] for n in nets),
        "series_resistance_in_signal_path": (len(nets) - n_stub) > 0,
        "nets": nets,
    }


def _committed_netlists() -> list[Path]:
    """The newest committed `--pdk` extraction of each top cell."""
    latest: dict[str, Path] = {}
    for path in sorted(REPORTS.glob("*/*.para.spice")):
        if "pfet_03v3" not in path.read_text():
            continue  # not a --pdk extraction
        latest[path.name] = path  # sorted -> last wins
    return [latest[k] for k in sorted(latest)]


def _render(results: list[dict]) -> str:
    L: list[str] = []
    a = L.append
    a("| netlist | form | parasitic nets | in-path R | stub R | total R (Ω) | "
      "max R (Ω) | total C (fF) |")
    a("|---|---|---|---|---|---|---|---|")
    for r in results:
        a(
            f"| `{r['name']}` | {r['topology_form']} | {r['parasitic_nets']} | "
            f"{r['in_path_nets']} | "
            f"{r['stub_nets']} | {r['total_resistance_ohm']:.1f} | "
            f"{r['max_resistance_ohm']:.1f} | "
            f"{r['total_capacitance_f'] * 1e15:.3f} |"
        )
    a("")
    for r in results:
        verdict = (
            "SERIES RESISTANCE IS IN THE SIGNAL PATH"
            if r["series_resistance_in_signal_path"]
            else "every parasitic R is a STUB -- no signal current flows "
            "through any extracted resistance"
        )
        a(f"{r['name']}: {verdict}")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("netlist", nargs="*", help="extracted .para.spice files "
                                               "(default: every committed one)")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.netlist] or _committed_netlists()
    results: list[dict] = []
    for path in paths:
        try:
            results.append(audit(path.read_text(), path.name))
        except OSError as exc:
            print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
            return 1

    if args.format == "json":
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
