#!/usr/bin/env python3
"""Issue #1114: the generated leaf-cell LVS reference headers narrate no
device, and say what the cards under them say.

    python3 -m unittest discover -s sim/tests -v

Why this file exists. `gen_adc_cells.write_reference` prefaced each of the
five `layout/adc-top/cells/*.ref.spice` references with a description of
the circuit that had drifted from the cards below it. Every header said the
PMOS bodies sat on an unnamed well net while each `pfet` card named `vdd`
(issue #356 drew the taps), and four headers announced absent MiM
capacitors in cells whose `.subckt` has none. Nothing could see it: `klt
lvs` compares statements and ignores comments, so `run_lvs.py --check`
stayed green; `test_lvs_request_writer.py` replays the `*.lvs.json`
request documents, not the references; and the manifest's sha256 pins only
prove a reference is the file that was hashed.

The guard is structural, the way the fix is -- a header that narrates no
device cannot contradict one. For every leaf cell this module asserts that

* the header names no transistor, so no body-terminal claim can drift from
  the cards again;
* the header speaks of a MiM capacitor exactly when the reference states
  one, which is exactly when the source subcircuit does, and where it does
  the fF figure it quotes is the card's own value;
* the one thing the header still explains is the substrate, and it names
  the net every NMOS card's body terminal carries -- the deck's `vsubs`
  global, a pin of the `.SUBCKT`, where the cell has no `vss` port, else
  the cell's labelled `vss` rail;
* the header keeps its provenance: source subcircuit, generator, the
  runnable `klt lvs` command and the layout README;
* the committed header is line for line what `gen_adc_cells.
  write_reference` writes for that substrate net today, so a generator edit
  that is not regenerated -- or a hand edit to a committed reference --
  fails here rather than at the next LVS run.

Needs neither ngspice, the PDK nor KLayout: the generator's `klayout.db`
import is stubbed when the package is absent (as `test_layout_centroid_
tiling.py` does), the source devices come from the parsed design netlist,
and `netlist.write_reference` is intercepted, so nothing is drawn or
written.
"""

from __future__ import annotations

import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from _loadmod import load_module

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CELLS = REPO / "layout" / "adc-top" / "cells"
DESIGN = REPO / "design" / "adc-top" / "adc_top.spice"


def _load_generator():
    """Import `layout/adc-top/cells/gen_adc_cells.py` without KLayout
    installed -- the same placeholder `test_layout_centroid_tiling.py`
    installs. The real package is preferred whenever it is installed."""
    try:
        import klayout.db  # noqa: F401, PLC0415
    except ImportError:
        klayout = types.ModuleType("klayout")
        klayout.__path__ = []  # mark as a package so `klayout.db` resolves
        db = types.ModuleType("klayout.db")
        klayout.db = db
        sys.modules.setdefault("klayout", klayout)
        sys.modules.setdefault("klayout.db", db)
    return load_module("refhdr_gen_adc_cells", CELLS / "gen_adc_cells.py")


gen_cells = _load_generator()
nl = gen_cells.nl

#: A transistor named in a header is a body-terminal claim waiting to
#: drift from the cards under it.
TRANSISTOR_RE = re.compile(r"\b(?:NMOS|PMOS|nfet|pfet)\b")
MIM_RE = re.compile(r"\bMiM\b")


def split_reference(text: str) -> tuple[list[str], list[str]]:
    """`(header, statements)`: the `*` comment block, and the non-blank
    lines `klt lvs` actually compares."""
    lines = text.split("\n")
    header = [line for line in lines if line.startswith("*")]
    statements = [
        line for line in lines if line.strip() and not line.startswith("*")
    ]
    return header, statements


def cards(statements: list[str], kind: str) -> list[list[str]]:
    """The whitespace-split fields of every `M` card of `kind`
    (`"nfet"`/`"pfet"`), or of every `C` card when `kind` is `"cap"`."""
    if kind == "cap":
        return [s.split() for s in statements if s.startswith("C")]
    return [s.split() for s in statements if s.startswith("M") and s.split()[5] == kind]


def subckt_pins(statements: list[str]) -> list[str]:
    """The `.SUBCKT` card's pin list."""
    line = next(s for s in statements if s.startswith(".SUBCKT"))
    return line.split()[2:]


def substrate_net(pins: list[str]) -> str:
    """The net the substrate ties were routed to, as the reference states
    it: the deck's `vsubs` global where that is a pin, else the cell's
    labelled `vss` rail."""
    return nl.SUBSTRATE_NET if nl.SUBSTRATE_NET in pins else "vss"


def source_devices(spec: dict) -> list:
    """The leaf cell's devices as `build` flattens them out of the design
    netlist, before anything is drawn."""
    return nl.flatten(
        nl.parse(str(DESIGN)),
        spec["subckt"],
        spec["ports"],
        spec.get("params"),
        prefix="",
    )


class LeafReferenceHeaders(unittest.TestCase):
    def reference(self, key: str) -> tuple[dict, list[str], list[str]]:
        """`(spec, header, statements)` of the committed reference."""
        text = (CELLS / f"{key}.ref.spice").read_text(encoding="utf-8")
        header, statements = split_reference(text)
        return gen_cells.LEAF_CELLS[key], header, statements

    def test_every_leaf_cell_is_under_test(self):
        self.assertEqual(
            sorted(gen_cells.LEAF_CELLS),
            sorted(p.name[: -len(".ref.spice")] for p in CELLS.glob("*.ref.spice")),
        )

    def test_header_names_no_transistor(self):
        for key in gen_cells.LEAF_CELLS:
            with self.subTest(cell=key):
                _, header, _ = self.reference(key)
                narrative = [line for line in header if TRANSISTOR_RE.search(line)]
                self.assertEqual(narrative, [])

    def test_header_speaks_of_a_mim_capacitor_only_where_one_is_stated(self):
        for key, spec in gen_cells.LEAF_CELLS.items():
            with self.subTest(cell=key):
                _, header, statements = self.reference(key)
                stated = cards(statements, "cap")
                in_source = [d for d in source_devices(spec) if d.kind == "cap"]
                self.assertEqual(len(stated), len(in_source))
                narrative = [line for line in header if MIM_RE.search(line)]
                self.assertEqual(bool(narrative), bool(stated), narrative)

    def test_the_mim_model_figure_is_the_cards_own_value(self):
        spec, header, statements = self.reference("adc_cdac_cell")
        self.assertTrue(spec.get("draw_cap"))
        text = "\n".join(header)
        self.assertIn("DECK_MIM_AREA_CAP_F_UM2", text)
        self.assertIn("DECK_MIM_PERIM_CAP_F_UM", text)
        (cap,) = cards(statements, "cap")
        self.assertIn(f"({float(cap[3]) * 1e15:.4f} fF", text)

    def test_header_explains_the_substrate_net_the_cards_carry(self):
        for key in gen_cells.LEAF_CELLS:
            with self.subTest(cell=key):
                _, header, statements = self.reference(key)
                text = "\n".join(header)
                pins = subckt_pins(statements)
                substrate = substrate_net(pins)
                self.assertEqual({c[4] for c in cards(statements, "nfet")}, {substrate})
                self.assertIn(substrate, pins)
                self.assertIn(f"`{substrate}`", text)
                self.assertIn("substrate", text.lower())
                if substrate == nl.SUBSTRATE_NET:
                    self.assertNotIn("vss", pins)

    def test_header_keeps_its_provenance(self):
        for key, spec in gen_cells.LEAF_CELLS.items():
            with self.subTest(cell=key):
                _, header, _ = self.reference(key)
                text = "\n".join(header)
                self.assertIn(f"`.subckt {spec['subckt']}`", text)
                self.assertIn("layout/adc-top/cells/gen_adc_cells.py", text)
                self.assertIn(
                    f"klt lvs layout/adc-top/cells/{key}.lvs.json --format json", text
                )
                self.assertIn("layout/adc-top/README.md", text)

    def test_committed_header_is_what_the_generator_writes(self):
        for key in gen_cells.LEAF_CELLS:
            with self.subTest(cell=key):
                spec, header, statements = self.reference(key)
                # The drawn geometry reaches the header through one value,
                # `block.substrate_net`; nothing else of `build` is needed.
                block = types.SimpleNamespace(
                    substrate_net=substrate_net(subckt_pins(statements)), body_net={}
                )
                with mock.patch.object(nl, "write_reference") as writer:
                    gen_cells.write_reference(
                        str(CELLS / f"{key}.ref.spice"),
                        spec,
                        {"devices": [], "block": block},
                    )
                self.assertEqual(writer.call_args.args[5], header)


if __name__ == "__main__":
    unittest.main()
