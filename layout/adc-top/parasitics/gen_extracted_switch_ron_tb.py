#!/usr/bin/env python3
"""The switch-R_on testbench with its transmission-gate branch wired against
the **extracted, PMOS-body-remediated `adc_tgate` leaf cell** -- the one piece
of `sim/extracted-delta-summary.md` SS6.3 that is tractable without drawing new
geometry.

    python3 layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py
    python3 layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py --check

Writes ONE file:

    sim/device-switch-ron/testbench/tb_switch_ron_extracted.spice

into the SAME experiment directory as the schematic-level deck, per
sim/README.md "Extracted vs schematic semantics", and deliberately does NOT
write a second `tb.json`: the run is
`sim/run_corners.py device-switch-ron --netlist <this file's output>
--netlist-provenance 'extracted (...)'`, i.e. the UNMODIFIED manifest, the same
`op` analyses, the same `ron_*` measure expressions and the same checks.

## Why this deck, and what it is for

SS6.3 blocks rate closure and the DR-0012/13 gain-error row on a post-layout
re-take of two settling-network inputs. Its own accounting names exactly one
tractable piece:

    "Group D (the Input-structure R_on re-take) is the one piece of this deck
     that is structurally tractable without new layout ... `adc_tgate.gds`
     **is** a standalone drawn leaf cell ... a new forced-voltage/measured-
     current deck against it on `sim/device-switch-ron/`'s own method."

This is that deck. It answers: **does the drawn, extracted transmission gate's
on-resistance differ from the schematic T-gate the R_on characterization was
taken against?**

## How the two decks are held like-for-like

The extracted deck is not re-written from scratch -- it is the committed
schematic deck `tb_switch_ron.spice`, spliced: everything up to the
transmission-gate section (the supply, the seven supply-tracking input points,
and the entire NMOS-only and PMOS-only branches) is copied **verbatim**, and
only the T-gate branch is replaced with instances of the extracted cell. So:

  * `ron_n_*` and `ron_p_*` are a **built-in control**: those branches are
    byte-identical between the two decks, so any nonzero delta on them would
    mean the comparison itself is broken, not that the layout changed
    something;
  * `ron_t_*` is the measurement: same forced 10 mV, same supply-tracking input
    ladder, same body connections, with the drawn cell in place of the two
    inline devices.

The splice asserts that the schematic T-gate branch's device geometry and the
extracted cell's device geometry agree (W = 10 um NMOS / 20 um PMOS, L =
0.28 um) before emitting anything. If the drawn cell is ever re-sized, this
generator fails rather than quietly comparing two different transistors.

## The one deliberate difference, stated

The extracted cell's PMOS body lands on an anonymous Nwell net that `klt
extract`'s gf180mcu deck cannot name (upstream klayout-tools#555).
`remediate_extracted.remediate_leaf()` promotes it to a `vnw` pin -- it does
NOT tie it inside the cell -- and this deck wires that pin to `vdd`, which is
exactly the single-well convention `tb_switch_ron.spice`'s own header states
("NMOS body to ground, PMOS body to vdd"). The bias is therefore visible at the
instance, in this file, rather than baked into the extracted netlist.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import remediate_extracted as R  # noqa: E402  (same directory)

TOP = "ADC_TGATE"
SCHEMATIC_TB = REPO / "sim" / "device-switch-ron" / "testbench" / "tb_switch_ron.spice"
OUT_PATH = (
    REPO / "sim" / "device-switch-ron" / "testbench" / "tb_switch_ron_extracted.spice"
)

#: The comment line that opens the schematic deck's transmission-gate branch.
#: Everything before it is copied verbatim; everything from it on is replaced.
TGATE_MARKER = "* Transmission gate: the same two devices in parallel"

#: The seven input points the schematic deck sweeps, in its own order. Read
#: from the deck rather than hardcoded -- see `_fractions`.
_VDT = re.compile(r"^vdt_(f\d+)\s+ndt_\1\s+n\1\s+dc\s+10m\s*$", re.M)

#: Device geometry, as the schematic branch writes it and as `klt extract`
#: writes it (case/format differ; the numbers must not).
_SCHEM_DEV = re.compile(r"^X(TN|TP)_f\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+"
                        r"(nfet_03v3|pfet_03v3)\s+w=(\S+)\s+l=(\S+)\s*$", re.M)
_EXTRACT_DEV = re.compile(r"^X\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+"
                          r"(nfet_03v3|pfet_03v3)\s+L=(\S+)\s+W=(\S+)\s*$", re.M)


def _um(text: str) -> float:
    """`10u` / `10U` / `0.28U` -> microns, as a float."""
    t = text.strip().lower()
    if not t.endswith("u"):
        raise ValueError(f"unexpected geometry token {text!r} (expected microns)")
    return float(t[:-1])


def _geometry(pairs: list[tuple[str, str, str]]) -> dict[str, tuple[float, float]]:
    """`{'nfet_03v3': (w_um, l_um), ...}`, asserting one geometry per model."""
    out: dict[str, tuple[float, float]] = {}
    for model, w, l in pairs:
        wl = (_um(w), _um(l))
        if model in out and out[model] != wl:
            raise ValueError(
                f"{model}: two different geometries in one branch, "
                f"{out[model]} and {wl} -- refusing to guess which one the "
                "comparison is against."
            )
        out[model] = wl
    return out


def _fractions(tgate_section: str) -> list[str]:
    frs = [m.group(1) for m in _VDT.finditer(tgate_section)]
    if not frs:
        raise ValueError(
            "no `vdt_<f> ndt_<f> n<f> dc 10m` forcing sources found in the "
            "schematic deck's transmission-gate section -- the splice point or "
            "the deck's own naming changed; refusing to emit a deck whose "
            "measure expressions would not resolve."
        )
    return frs


def _move_devices_onto_internal_nodes(core_text: str) -> tuple[str, list[str]]:
    """POSITIVE CONTROL: re-attach every device terminal to its net's `__par`
    node, so each extracted parasitic R sits in series with the channel.

    A null result ("the extracted cell's R_on equals the schematic one") is
    only worth something if the measurement could have detected a difference.
    This transform produces the netlist the extraction would have written if
    its parasitic resistance were in the signal path instead of a stub
    (`audit_parasitic_topology.py`), so running the same deck against it must
    move R_on by the sum of the series resistances -- and if it does not, the
    deck, not the layout, is what is insensitive.

    Deliberately NOT written to `sim/`: this is a control netlist, not
    evidence of the drawn cell. It is emitted on demand
    (`--in-path-control --stdout`) so the check is reproducible without
    committing a netlist that describes a circuit nobody drew.
    """
    r_nets = {
        m.group(1): m.group(2)
        for m in re.finditer(r"^R\S+\s+(\S+)\s+(\S+__par)\s+\S+\s*$", core_text, re.M)
    }
    if not r_nets:
        raise ValueError("no parasitic R cards found -- nothing to move in-path")
    out: list[str] = []
    moved: list[str] = []
    for line in core_text.splitlines():
        tok = line.split()
        if tok and tok[0].startswith("X") and any("fet_03v3" in t for t in tok):
            new = [tok[0]] + [r_nets.get(t, t) for t in tok[1:5]] + tok[5:]
            moved += [t for t in tok[1:5] if t in r_nets]
            out.append(" ".join(new))
            continue
        out.append(line)
    return "\n".join(out) + "\n", sorted(set(moved))


def extracted_switch_ron_netlist(top: str = TOP, in_path_control: bool = False) -> str:
    src = SCHEMATIC_TB.read_text()
    head, marker, tail = src.partition(TGATE_MARKER)
    if not marker:
        raise ValueError(
            f"splice marker not found in {SCHEMATIC_TB.relative_to(REPO)}:\n"
            f"  {TGATE_MARKER!r}\n"
            "The schematic deck changed shape; update this generator "
            "deliberately rather than emitting a differently-structured deck."
        )
    # `head` ends with the `* ====` rule line that opens the T-gate block --
    # drop it (and any trailing blank line) so the replacement section can
    # write its own.
    head_lines = head.rstrip("\n").splitlines()
    while head_lines and (
        not head_lines[-1].strip() or re.fullmatch(r"\*\s*=+", head_lines[-1].strip())
    ):
        head_lines.pop()
    head = "\n".join(head_lines)

    schem_geom = _geometry([(m.group(2), m.group(3), m.group(4))
                            for m in _SCHEM_DEV.finditer(marker + tail)])

    core_src = R._latest_report(top)
    core_text, rem = R.remediate_leaf(core_src.read_text(), top)
    if rem.n_pmos_rewritten < 1:
        raise ValueError(f"{top}: leaf remediation rewrote no PMOS body terminal")
    extract_geom = _geometry([(m.group(1), m.group(3), m.group(2))
                              for m in _EXTRACT_DEV.finditer(core_text)])
    if schem_geom != extract_geom:
        raise ValueError(
            "the schematic T-gate branch and the drawn cell are not the same "
            f"devices -- schematic {schem_geom} vs extracted {extract_geom}. "
            "A post-layout R_on delta between two different geometries is not "
            "a layout finding; re-size one side deliberately, or drop the "
            "comparison."
        )

    pins = R.parse(core_text, top).pins
    expected_pins = ["gn", "gp", "vin", "vout", "vsubs", R.NWELL_PIN]
    if pins != expected_pins:
        raise ValueError(
            f"{top}: unexpected remediated pin order {pins} (expected "
            f"{expected_pins}); the wiring below is positional."
        )

    fractions = _fractions(marker + tail)

    L: list[str] = []
    a = L.append
    a("* ==================================================================")
    a("* tb_switch_ron_extracted -- the switch-R_on testbench with its")
    a("* transmission-gate branch wired against the EXTRACTED, PMOS-body-")
    a("* remediated `adc_tgate` leaf cell (sim/extracted-delta-summary.md")
    a("* SS6.3's Input-structure R_on re-take). GENERATED by")
    a("* layout/adc-top/parasitics/gen_extracted_switch_ron_tb.py -- do not")
    a("* edit.")
    a("*")
    a("* Runs sim/device-switch-ron/testbench/tb.json UNMODIFIED, via")
    a("* `run_corners.py device-switch-ron --netlist <this file>`. Everything")
    a("* above the transmission-gate section below -- the supply, the seven")
    a("* supply-tracking input points, and the whole NMOS-only and PMOS-only")
    a("* branches -- is copied VERBATIM from tb_switch_ron.spice, so ron_n_*")
    a("* and ron_p_* are a built-in control (they must come back bit-")
    a("* identical) and ron_t_* is the only measurement that can move.")
    a("* ==================================================================")
    a(head)
    a("")
    a("* " + "=" * 75)
    a("* The DRAWN transmission gate, extracted with its parasitics.")
    a("*")
    a(f"* Source: {core_src.relative_to(REPO)}")
    a("* (`klt extract --deck gf180mcu --parasitics --pdk`, asserted against")
    a("* layout/adc-top/parasitics/cells.json by run_extract_parasitics.py),")
    a("* post-processed by remediate_extracted.py --leaf, which promotes the")
    a("* anonymous Nwell net every PMOS body lands on to a `vnw` pin instead")
    a("* of tying it inside the cell. This deck wires that pin to vdd below --")
    a("* the single-well convention tb_switch_ron.spice's own header states.")
    a("*")
    a("* Device geometry is asserted equal on both sides before this file is")
    a(f"* written: {', '.join(f'{k} W={v[0]}u L={v[1]}u' for k, v in sorted(schem_geom.items()))}.")
    a("* " + "=" * 75)
    if in_path_control:
        core_text, moved = _move_devices_onto_internal_nodes(core_text)
        a("* !! POSITIVE CONTROL -- NOT THE DRAWN CELL !!")
        a("* Every device terminal on " + ", ".join(moved) + " has been moved")
        a("* onto that net's `__par` node, putting the extracted parasitic")
        a("* resistance in series with the channel. See")
        a("* gen_extracted_switch_ron_tb._move_devices_onto_internal_nodes().")
        a("* " + "=" * 75)
    a(core_text.rstrip("\n"))
    a("")
    a("* " + "=" * 75)
    a("* Transmission gate: one extracted-cell instance per input point.")
    a("* Same forcing method as the schematic branch it replaces -- a 10 mV")
    a("* source from the forced node to the input point, so its current IS the")
    a("* channel current and R_on = 10 mV / |I| at that input.")
    a(f"* Pin order: {' '.join(pins)}  (gn = vdd, gp = 0: both devices hard on;")
    a("* vin = the forced node, vout = the input point, vsubs = 0, vnw = vdd.)")
    for fr in fractions:
        a(f"vdt_{fr}  ndt_{fr}  n{fr}  dc 10m")
        a(f"Xtg_{fr}  vdd 0 ndt_{fr} n{fr} 0 vdd {top}")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    ap.add_argument("--stdout", action="store_true", help="write to stdout instead")
    ap.add_argument(
        "--in-path-control",
        action="store_true",
        help="POSITIVE CONTROL: emit the same deck with every device terminal "
             "moved onto its net's `__par` node, so the extracted parasitic "
             "resistance sits in series with the channel. Requires --stdout: "
             "this describes a circuit nobody drew and must not be committed "
             "as evidence.",
    )
    args = ap.parse_args(argv)

    if args.in_path_control and not args.stdout:
        print(
            "error: --in-path-control is a control netlist, not evidence; "
            "pass --stdout (it is never written into sim/).",
            file=sys.stderr,
        )
        return 2

    text = extracted_switch_ron_netlist(in_path_control=args.in_path_control)
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if args.check:
        if not OUT_PATH.is_file() or OUT_PATH.read_text() != text:
            print(f"STALE: {OUT_PATH.relative_to(REPO)}", file=sys.stderr)
            return 1
        print(f"OK: {OUT_PATH.relative_to(REPO)} is current")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.is_file() and OUT_PATH.read_text() == text:
        print(f"  unchanged  {OUT_PATH.relative_to(REPO)}")
        return 0
    OUT_PATH.write_text(text)
    print(f"  wrote      {OUT_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
