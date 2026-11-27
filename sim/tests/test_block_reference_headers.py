#!/usr/bin/env python3
"""Issue #1117: the three block-level LVS reference headers make no
body-terminal claim the cards under them contradict.

    python3 -m unittest discover -s sim/tests -v

Why this file exists. `gen_adc_top.write_reference` prefaced both block
references with "NMOS bodies are on the deck's `vsubs` global" and "PMOS
bodies are on their own Nwell island's net ... not on `vdd`", and
`gen_comparator.write_outputs` repeated the PMOS claim -- while every
`nfet` card under them names `vss`, every `pfet` card names `vdd` and no
`.SUBCKT` has a `vsubs` pin. Issue #356 drew the taps; the prose never
followed. Nothing could see it: `klt lvs` compares statements and ignores
comments, so `run_lvs.py --check` stayed green, and the manifest's sha256
pins only prove a reference is the file that was hashed. The leaf cells
got the same guard in issue #1114 (`test_leaf_reference_headers.py`).

The rule is structural, the way the fix is: a header line that names a
transistor kind must name the net that kind's cards carry their bodies on.
The retired lines fail it and the survivor passes it -- the comparator's
substrate bullet, which says its NMOS bodies are on the drawn `vss` rail,
exactly what its `nfet` cards say. For every block reference this module
asserts that

* no header line names a transistor kind without naming its cards' body
  net, over cards that really do sit on `vss`/`vdd`, and the lines issue
  #1117 retired are rejected by that rule;
* the header keeps its provenance: source subcircuit, generator, the
  runnable `klt lvs` command and the layout README;
* the header speaks of the MiM capacitors and the load resistors exactly
  where the reference states them, quoting the cards' own values;
* the committed header is line for line what its generator writes today,
  so a generator edit that is not regenerated -- or a hand edit to a
  committed reference -- fails here rather than at the next LVS run;
* the comparator's substrate bullet follows the net its stream ties to, for
  both substrate nets the generator can be handed.

Needs neither ngspice, the PDK nor KLayout: the generators' `klayout.db`
import is stubbed when the package is absent (as `test_lvs_request_writer.py`
does), and `netlist.write_reference` is intercepted, so nothing is drawn or
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
ADC_TOP = REPO / "layout" / "adc-top"


def _stub_klayout() -> None:
    """Make `import klayout.db` resolve to an empty placeholder when the
    wheel is absent. The real package is preferred whenever it is installed,
    so this never shadows a working install."""
    try:
        import klayout.db  # noqa: F401, PLC0415
    except ImportError:
        klayout = types.ModuleType("klayout")
        klayout.__path__ = []  # mark as a package so `klayout.db` resolves
        db = types.ModuleType("klayout.db")
        klayout.db = db
        sys.modules.setdefault("klayout", klayout)
        sys.modules.setdefault("klayout.db", db)


_stub_klayout()
gen_top = load_module("refhdr_gen_adc_top", ADC_TOP / "gen_adc_top.py")
gen_cmp = load_module("refhdr_gen_comparator", ADC_TOP / "gen_comparator.py")
nl = gen_top.nl

#: Committed block reference stem -> the generator module that writes it.
BLOCK_REFERENCES = {
    "comparator": gen_cmp,
    "adc_top": gen_top,
    "adc_block": gen_top,
}

#: The design subcircuit each header names as its source.
SOURCE = {
    "comparator": "design/comparator/comparator.spice's `.subckt comparator`",
    "adc_top": "design/adc-top/adc_top.spice's `adc_cdac_side` and `adc_tp_sw`",
    "adc_block": "design/adc-top/adc_top.spice's `adc_cdac_side` and `adc_tp_sw`",
}

#: The bullets issue #1117 retired, verbatim: the negative control. Each
#: bullet's head line names a transistor kind without naming its cards'
#: body net, so `contradicted_lines` must reject exactly that line.
_PMOS_ISLAND = [
    "*   - PMOS bodies on their own Nwell island's net, one per placed",
    "*     group, not on `vdd` (the deck never connects `nwell` to",
    "*     `contact`);",
]
_VSUBS_THEN_ISLAND = [
    [
        "*   - NMOS bodies are on the deck's `vsubs` global (no tap layer);",
    ],
    [
        "*   - PMOS bodies are on their own Nwell island's net -- one island per",
        "*     placed CDAC cell, one per top-plate switch side, and one per",
        "*     comparator group -- not on `vdd`: the deck never connects `nwell`",
        "*     to `contact`;",
    ],
]
RETIRED_BULLETS = {
    "comparator": [_PMOS_ISLAND],
    "adc_top": _VSUBS_THEN_ISLAND,
    "adc_block": _VSUBS_THEN_ISLAND,
}

#: The comparator's substrate bullet, by the net its stream ties the
#: substrate to -- the one transistor narrative issue #1117 kept, because
#: it says what the cards say for either net.
COMPARATOR_BULLET = {
    "vss": "NMOS bodies on the cell's own drawn `vss` rail",
    nl.SUBSTRATE_NET: "NMOS bodies on the deck's `vsubs` global",
}

_KIND_WORD = (("nfet", "NMOS"), ("pfet", "PMOS"))


class _FakeLayout:
    """Stands in for the KLayout `Layout` `gen_comparator.write_outputs`
    writes a GDS from; GDS emission is not under test."""

    def write(self, path, options):
        pass


def split_reference(text: str) -> tuple[list[str], list[str]]:
    """`(header, statements)`: the `*` comment block, and the non-blank
    lines `klt lvs` actually compares."""
    lines = text.split("\n")
    header = [line for line in lines if line.startswith("*")]
    statements = [line for line in lines if line.strip() and not line.startswith("*")]
    return header, statements


def cards(statements: list[str], kind: str) -> list[list[str]]:
    """The whitespace-split fields of every card of `kind`: `"nfet"` and
    `"pfet"` select `M` cards by model, `"cap"` and `"res"` select `C` and
    `R` cards."""
    if kind == "cap":
        return [s.split() for s in statements if s.startswith("C")]
    if kind == "res":
        return [s.split() for s in statements if s.startswith("R")]
    return [s.split() for s in statements if s.startswith("M") and s.split()[5] == kind]


def body_nets(statements: list[str], kind: str) -> set[str]:
    """The nets the `kind` cards' body terminals (the fourth node) carry."""
    return {c[4] for c in cards(statements, kind)}


def subckt_pin_names(statements: list[str]) -> list[str]:
    """The `.SUBCKT` card's name and pin list."""
    return next(s for s in statements if s.startswith(".SUBCKT")).split()[1:]


def contradicted_lines(header: list[str], statements: list[str]) -> list[str]:
    """Every header line that names a transistor kind (`NMOS`/`PMOS`) but
    not every net that kind's cards carry their bodies on."""
    contradicted = []
    for kind, word in _KIND_WORD:
        bulks = body_nets(statements, kind)
        for line in header:
            if re.search(rf"\b{word}\b", line) and not all(
                f"`{net}`" in line for net in bulks
            ):
                contradicted.append(line)
    return contradicted


def comparator_header(substrate_net: str) -> list[str]:
    """The header `gen_comparator.write_outputs` hands
    `netlist.write_reference` for a stream whose substrate tie lands on
    `substrate_net` -- the one value of the drawn geometry a comparator
    header reads. Nothing is drawn or written."""
    info = {
        "name": gen_cmp.CELL_NAME,
        "devices": [],
        "pins": [],
        "body_net": {},
        "substrate_net": substrate_net,
    }
    with mock.patch.object(nl, "write_reference") as writer:
        with (
            mock.patch.multiple(
                gen_cmp.geo,
                assert_on_grid=mock.DEFAULT,
                assert_contacts_exact=mock.DEFAULT,
                save_options=mock.DEFAULT,
            ),
            mock.patch.object(nl, "write_lvs_request"),
        ):
            gen_cmp.write_outputs(str(ADC_TOP), _FakeLayout(), info, "comparator")
    return writer.call_args.args[5]


def block_header(key: str, statements: list[str]) -> list[str]:
    """The header `gen_adc_top.write_reference` hands
    `netlist.write_reference` for the circuit the committed `statements`
    state. The drawn geometry reaches a block header through two values,
    the unit-capacitor count and whether a comparator is assembled in;
    nothing is drawn or written."""
    info = {
        "cap_count": len(cards(statements, "cap")),
        "comparator": object() if cards(statements, "res") else None,
        "devices": [],
        "pins": [],
        "body_net": {},
    }
    with mock.patch.object(nl, "write_reference") as writer:
        gen_top.write_reference(
            str(ADC_TOP / f"{key}.ref.spice"),
            info,
            subckt_pin_names(statements)[0],
            key,
        )
    return writer.call_args.args[5]


class BlockReferenceHeaders(unittest.TestCase):
    def reference(self, key: str) -> tuple[list[str], list[str]]:
        """`(header, statements)` of the committed reference."""
        header, statements = split_reference(
            (ADC_TOP / f"{key}.ref.spice").read_text(encoding="utf-8")
        )
        return header, statements

    def test_every_block_reference_is_under_test(self):
        self.assertEqual(
            set(BLOCK_REFERENCES),
            {p.name[: -len(".ref.spice")] for p in ADC_TOP.glob("*.ref.spice")},
        )

    def test_no_line_naming_a_transistor_contradicts_its_cards(self):
        for key in BLOCK_REFERENCES:
            with self.subTest(reference=key):
                header, statements = self.reference(key)
                # The rule reads real cards, and they sit where issue #356
                # routed the taps -- on the supply rails, not on `vsubs`.
                self.assertEqual(body_nets(statements, "nfet"), {"vss"})
                self.assertEqual(body_nets(statements, "pfet"), {"vdd"})
                self.assertNotIn(nl.SUBSTRATE_NET, subckt_pin_names(statements))
                self.assertEqual(contradicted_lines(header, statements), [])

    def test_the_retired_lines_fail_the_rule(self):
        for key, bullets in RETIRED_BULLETS.items():
            _, statements = self.reference(key)
            for bullet in bullets:
                with self.subTest(reference=key, head=bullet[0]):
                    self.assertEqual(
                        contradicted_lines(bullet, statements), [bullet[0]]
                    )

    def test_header_keeps_its_provenance(self):
        for key, gen in BLOCK_REFERENCES.items():
            with self.subTest(reference=key):
                header, _ = self.reference(key)
                text = "\n".join(header)
                self.assertIn(SOURCE[key], text)
                self.assertIn(f"layout/adc-top/{Path(gen.__file__).name}", text)
                self.assertIn(
                    f"klt lvs layout/adc-top/{key}.lvs.json --format json", text
                )
                self.assertIn("layout/adc-top/README.md", text)

    def test_header_speaks_of_passives_exactly_where_they_are_stated(self):
        for key in BLOCK_REFERENCES:
            with self.subTest(reference=key):
                header, statements = self.reference(key)
                text = "\n".join(header)
                caps = cards(statements, "cap")
                res = cards(statements, "res")
                self.assertEqual("cap_mim_2f0_m4m5_noshield" in text, bool(caps))
                self.assertEqual("load resistors" in text, bool(res))
                if caps:
                    self.assertIn(f"{float(caps[0][3]) * 1e15:.4f} fF", text)
                    self.assertIn(f"{len(caps)} unit-size", text)
                if res:
                    self.assertIn(f"{int(res[0][4]) // 1000} kohm", text)
                    self.assertIn(res[0][5], text)

    def test_committed_header_is_what_the_generator_writes(self):
        for key in BLOCK_REFERENCES:
            with self.subTest(reference=key):
                header, statements = self.reference(key)
                if key == "comparator":
                    emitted = comparator_header(
                        next(iter(body_nets(statements, "nfet")))
                    )
                else:
                    emitted = block_header(key, statements)
                self.assertEqual(emitted, header)

    def test_comparator_substrate_bullet_follows_its_stream(self):
        for substrate_net, bullet in COMPARATOR_BULLET.items():
            with self.subTest(substrate_net=substrate_net):
                header = comparator_header(substrate_net)
                naming = [line for line in header if "NMOS" in line]
                self.assertEqual(len(naming), 1, naming)
                self.assertTrue(naming[0].startswith("*   - " + bullet), naming[0])
                self.assertEqual([line for line in header if "PMOS" in line], [])


if __name__ == "__main__":
    unittest.main()
