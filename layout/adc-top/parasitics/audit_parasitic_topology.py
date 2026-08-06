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

The `--parasitics` netlist writes, per net it covers, exactly one pair:

    R<net> <net> <net>__par <ohms>
    C<net> <net>__par <ground> <farads>

Whether that `R` carries any signal current depends on which node the *devices*
sit on. Two possibilities:

  * **in-path** -- some device/cap terminal is on `<net>__par`, so current
    flowing between that terminal and the rest of the net goes through `R`. The
    extraction then models series/IR resistance, and a post-layout R_on or
    settling-resistance number can differ from the schematic one.
  * **stub** -- every device/cap terminal is on `<net>` itself and `<net>__par`
    is reached only by the `C`. `R` then carries no signal current at all; it
    only puts the parasitic capacitance behind a small series resistance (a
    lossy load), and no DC or resistive measurement can see it.

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

#: The suffix `klt extract --parasitics` gives the internal node of each
#: net's lumped RC pair (also reported as `parasitics.nets[].internal_node`
#: in the extractor's own JSON summary).
PAR_SUFFIX = "__par"

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
    par_r: dict[str, tuple[str, float]] = {}  # net -> (internal node, ohms)
    par_c: dict[str, tuple[str, float]] = {}  # net -> (internal node, farads)
    for tok in cards:
        if len(tok) < 4:
            continue
        head = tok[0][0].upper()
        a, b = tok[1], tok[2]
        if head == "R" and b.endswith(PAR_SUFFIX):
            try:
                par_r[a] = (b, float(tok[3]))
            except ValueError:
                continue
        elif head == "C" and a.endswith(PAR_SUFFIX):
            try:
                par_c[a[: -len(PAR_SUFFIX)]] = (a, float(tok[3]))
            except ValueError:
                continue

    # Which nodes do the REAL (non-parasitic) cards touch?
    internal_nodes = {v[0] for v in par_r.values()}
    on_internal: dict[str, int] = {}
    for tok in cards:
        head = tok[0][0].upper()
        # skip the parasitic pair itself
        if head in ("R", "C") and any(t.endswith(PAR_SUFFIX) for t in tok[1:3]):
            continue
        n = _terminal_count(tok)
        for node in tok[1 : 1 + n]:
            if node in internal_nodes:
                on_internal[node] = on_internal.get(node, 0) + 1

    nets = []
    for net, (node, ohms) in sorted(par_r.items()):
        farads = par_c.get(net, ("", 0.0))[1]
        touching = on_internal.get(node, 0)
        nets.append(
            {
                "net": net,
                "internal_node": node,
                "resistance_ohm": ohms,
                "capacitance_f": farads,
                "device_terminals_on_internal_node": touching,
                "topology": "in-path" if touching else "stub",
            }
        )
    n_stub = sum(1 for n in nets if n["topology"] == "stub")
    return {
        "name": name,
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
    a("| netlist | parasitic nets | in-path R | stub R | total R (Ω) | "
      "max R (Ω) | total C (fF) |")
    a("|---|---|---|---|---|---|---|")
    for r in results:
        a(
            f"| `{r['name']}` | {r['parasitic_nets']} | {r['in_path_nets']} | "
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
