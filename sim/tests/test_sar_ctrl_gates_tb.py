#!/usr/bin/env python3
"""The committed gate-level SAR-sequencer replay testbenches must match a
fresh run of `design/sar-logic/flow/gen_sar_ctrl_gates_tb.py` (issue #273).

    python3 -m unittest discover -s sim/tests -v

Same "generator is the source of truth, diff a fresh run against the
committed artifact" discipline as `test_sar_logic_netlist.py` (rung-1 ideal
model) and `test_sar_ctrl_gate_netlist.py` (the gate netlist itself, issue
#272), applied to the gate-level replay testbenches this issue adds.

## Why this test SKIPS (not fails) without a PDK, but does NOT need `klt`

`gen_sar_ctrl_gates_tb.py` translates the already-committed gate netlist
(`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.mcu7t5v0.synth.v`) into
SPICE via `gate_netlist_to_spice.py` -- pure Python, no external tool. It
DOES need the gf180mcu PDK's own standard-cell SPICE library text
(`libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice`) as
an input, which `.github/workflows/ci.yml`'s default PR path does not
install (same constraint `test_sar_ctrl_gate_netlist.py`'s own docstring
explains). Unlike that sibling test, this one does NOT need `klt`/Yosys at
all -- so it is one step closer to running on the headless PR path than the
netlist-synthesis check is, and should move there first if/when the PDK
itself becomes CI-installable independently of `klt`.

## Per-loop timing decks (issue #311)

`gen_sar_ctrl_gates_tb.py` emits the gate-level timing deck in two
compositions: the original five-loop
`sim/sar-logic-timing-gates/testbench/tb_sar_logic_timing_gates.spice`, and
one single-loop deck per tag under
`sim/sar-logic-timing-gates-<tag>/testbench/`. The split exists because
ngspice advances one GLOBAL timestep per deck, so five clock-sharing
`sar_ctrl_a` instances in one file force each other's step down to the union
of their switching activity -- ~100x the per-simulated-ns cost of one loop
alone (`sim/sar-logic-timing-gates/investigations/
20260917-issue-303-five-loop-composition-cost.md`).

The whole point of that split is that it is a **composition** change and not
a modelling change, so the tests below assert exactly that, on the committed
artifacts and without a PDK:

- `PerLoopTimingDeckCompositionTests` -- each per-loop deck contains exactly
  one `* ---- loop <tag> ----` block and that block is **byte-identical** to
  the corresponding block of the five-loop deck, and the five-loop deck
  still carries all five.
- `PerLoopManifestBoundsTests` -- the five per-loop `tb.json` manifests
  partition the five-loop manifest's `measure`/`checks` exactly: same nine
  measurement names, same expressions, same numeric limits (descriptions may
  differ), same PVT axes and same `tran` line, with `bad` still the negative
  control whose check asserts the conversion IS wrong.

If either property is broken, the split has stopped being a re-composition
of the ratified deck and has become a different experiment.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "design" / "sar-logic" / "flow" / "gen_sar_ctrl_gates_tb.py"

#: Issue #311: the five loops of the gate-level timing deck, in emission
#: order. Mirrors `gen_sar_logic.TIMING_LOOP_TAGS` -- deliberately restated
#: here rather than imported, so the no-PDK half of this file (which never
#: execs the generator module) can use it too, and so a silent reordering or
#: renaming upstream shows up as a test failure rather than as a test that
#: quietly checks a different set.
TIMING_LOOP_TAGS = ("ok", "lt", "xl", "bad", "tie")
FIVE_LOOP_SLUG = "sar-logic-timing-gates"
FIVE_LOOP_DECK = f"sim/{FIVE_LOOP_SLUG}/testbench/tb_sar_logic_timing_gates.spice"


def _per_loop_slug(tag: str) -> str:
    return f"{FIVE_LOOP_SLUG}-{tag}"


def _per_loop_deck(tag: str) -> str:
    return (
        f"sim/{_per_loop_slug(tag)}/testbench/"
        f"tb_sar_logic_timing_gates_{tag}.spice"
    )


def _manifest(slug: str) -> dict:
    return json.loads((REPO / "sim" / slug / "testbench" / "tb.json").read_text())


def _loop_blocks(lines: list[str]) -> dict[str, list[str]]:
    """Split a timing deck's text into its `* ---- loop <tag> ----` blocks.

    A block runs from its own marker to the next marker, or -- for the last
    loop in the deck -- to the `.global vdd_gate` declaration (and the
    comment paragraph that introduces it) which separates the loop region
    from the standard-cell subckt library `_assemble()` appends after it.
    Trailing blank lines are dropped so the blocks of a five-loop and a
    one-loop deck are directly comparable.
    """
    starts = [
        (i, line.split()[3])
        for i, line in enumerate(lines)
        if line.startswith("* ---- loop ")
    ]
    blocks: dict[str, list[str]] = {}
    for n, (i, tag) in enumerate(starts):
        if n + 1 < len(starts):
            end = starts[n + 1][0]
        else:
            end = next(
                (
                    j
                    for j in range(i, len(lines))
                    if lines[j].startswith((".global", "* Externally-supplied"))
                ),
                len(lines),
            )
        block = lines[i:end]
        while block and not block[-1].strip():
            block.pop()
        blocks[tag] = block
    return blocks

_spec = importlib.util.spec_from_file_location("gen_sar_ctrl_gates_tb", GEN)
gen_gates = importlib.util.module_from_spec(_spec)
sys.modules["gen_sar_ctrl_gates_tb"] = gen_gates


def _pdk_available() -> bool:
    sys.path.insert(0, str(REPO))
    from sim.harness.pdk import PdkNotFound, find_pdk  # noqa: PLC0415

    try:
        find_pdk()
    except PdkNotFound:
        return False
    return True


class GateTbDriftTests(unittest.TestCase):
    """PDK-dependent -- see module docstring for why this SKIPS (not fails)
    without one."""

    @classmethod
    def setUpClass(cls):
        if not REPO.joinpath(
            "design", "sar-logic", "flow", "sar_ctrl", "netlist", "sar_ctrl.mcu7t5v0.synth.v"
        ).is_file():
            raise unittest.SkipTest("committed gate netlist missing -- run synth_sar_ctrl.py (issue #272)")
        if not _pdk_available():
            raise unittest.SkipTest(
                "gf180mcu PDK not resolvable -- see sim/harness/pdk.py and docs/environment-setup.md"
            )
        _spec.loader.exec_module(gen_gates)
        for name, (rel, _fn) in gen_gates.TARGETS.items():
            if not (REPO / rel).is_file():
                raise AssertionError(f"committed gate-level testbench missing for {name}: {rel}")

    def test_committed_testbenches_match_a_fresh_generation(self):
        for name, (rel, fn) in sorted(gen_gates.TARGETS.items()):
            with self.subTest(target=name):
                path = REPO / rel
                self.assertEqual(
                    path.read_text(),
                    fn(),
                    f"{rel} is stale -- run: python3 {GEN.relative_to(REPO)}",
                )

    def test_check_mode_agrees(self):
        self.assertEqual(gen_gates.main(["--check"]), 0)

    def test_targets_cover_the_five_loop_deck_and_every_per_loop_deck(self):
        """Issue #311: adding a loop tag upstream without giving it its own
        target would silently leave one fifth of the timing claim ungenerated
        (and, worse, unscored) -- so the target set is asserted exactly."""
        expected = {
            "functional-gates":
                "sim/sar-logic-functional-gates/testbench/"
                "tb_sar_logic_functional_gates.spice",
            "timing-gates": FIVE_LOOP_DECK,
        }
        for tag in TIMING_LOOP_TAGS:
            expected[f"timing-gates-{tag}"] = _per_loop_deck(tag)
        self.assertEqual(
            expected,
            {name: rel for name, (rel, _fn) in gen_gates.TARGETS.items()},
        )

    def test_default_loop_tags_reproduce_the_five_loop_deck(self):
        """The decomposition must be opt-in: `timing_gates()` with no
        `loop_tags` is still byte-for-byte the ratified five-loop deck."""
        self.assertEqual(
            (REPO / FIVE_LOOP_DECK).read_text(),
            gen_gates.timing_gates(loop_tags=TIMING_LOOP_TAGS),
        )
        self.assertEqual(
            gen_gates.timing_gates(),
            gen_gates.timing_gates(loop_tags=TIMING_LOOP_TAGS),
        )

    def test_rung1_ideal_timing_deck_is_unaffected(self):
        """`gen_sar_logic.timing()` shares `_timing_body` with the gate-level
        generator; issue #311 added a parameter to it, and the rung-1 ideal
        deck's committed text must not have moved by one byte."""
        sys.path.insert(0, str(REPO / "design" / "sar-logic"))
        import gen_sar_logic as gen  # noqa: PLC0415

        self.assertEqual(TIMING_LOOP_TAGS, gen.TIMING_LOOP_TAGS)
        rel = "sim/sar-logic-timing/testbench/tb_sar_logic_timing.spice"
        if not (REPO / rel).is_file():
            self.skipTest(f"{rel} not present")
        self.assertEqual((REPO / rel).read_text(), gen.timing())

    def test_unknown_or_empty_loop_tags_are_rejected(self):
        """A typo'd tag must not silently emit a deck with fewer loops than
        the caller asked for -- that would score a partial claim as a whole
        one."""
        sys.path.insert(0, str(REPO / "design" / "sar-logic"))
        import gen_sar_logic as gen  # noqa: PLC0415

        with self.assertRaises(ValueError):
            gen._timing_body(loop_tags=())
        with self.assertRaises(ValueError):
            gen._timing_body(loop_tags=("ok", "nosuchloop"))


class GateTbFragmentRuleTests(unittest.TestCase):
    """The generated fragments must stay loadable by the corner runner --
    same guard `test_sar_logic_netlist.py`'s `NetlistFragmentRuleTests`
    applies to the rung-1 fragments, applied here to the gate-level ones.
    This half needs no PDK: it only inspects the already-committed files."""

    def test_fragments_contain_no_forbidden_directives(self):
        sys.path.insert(0, str(REPO / "sim"))
        from harness.testbench import FORBIDDEN_DIRECTIVES  # noqa: PLC0415

        decks = [
            "sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice",
            FIVE_LOOP_DECK,
            *(_per_loop_deck(tag) for tag in TIMING_LOOP_TAGS),
        ]
        for rel in decks:
            path = REPO / rel
            if not path.is_file():
                self.skipTest(f"{rel} not committed yet")
            with self.subTest(target=rel):
                for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
                    directive = raw.strip().split()[0].lower() if raw.strip() else ""
                    self.assertNotIn(
                        directive,
                        FORBIDDEN_DIRECTIVES,
                        f"{rel}:{lineno} uses {directive}, which the harness rejects",
                    )

    def test_manifests_load_cleanly(self):
        sys.path.insert(0, str(REPO))
        from sim.harness.testbench import load  # noqa: PLC0415

        slugs = [
            "sar-logic-functional-gates",
            FIVE_LOOP_SLUG,
            *(_per_loop_slug(tag) for tag in TIMING_LOOP_TAGS),
        ]
        for slug in slugs:
            with self.subTest(slug=slug):
                tb = load(REPO / "sim" / slug)
                self.assertEqual(tb.corners, ("mos",))
                self.assertEqual(tb.temperatures_c, (-40.0, 27.0, 125.0))


class PerLoopTimingDeckCompositionTests(unittest.TestCase):
    """Issue #311: the per-loop timing decks are a RE-COMPOSITION of the
    ratified five-loop deck, not a re-modelling of it.

    That distinction is the entire licence for scoring the split decks
    against the five-loop deck's ratified bounds, so it is asserted on the
    committed text rather than argued in a comment: each per-loop deck holds
    exactly one loop, and that loop's SPICE is byte-identical to the same
    loop in the five-loop deck. No PDK needed -- committed files only.
    """

    @classmethod
    def setUpClass(cls):
        missing = [
            rel
            for rel in (FIVE_LOOP_DECK, *(_per_loop_deck(t) for t in TIMING_LOOP_TAGS))
            if not (REPO / rel).is_file()
        ]
        if missing:
            raise unittest.SkipTest(f"timing deck(s) not committed yet: {missing}")
        cls.five = _loop_blocks((REPO / FIVE_LOOP_DECK).read_text().splitlines())

    def test_the_five_loop_deck_still_holds_all_five_loops(self):
        self.assertEqual(list(TIMING_LOOP_TAGS), list(self.five))

    def test_each_per_loop_deck_instantiates_exactly_one_loop(self):
        for tag in TIMING_LOOP_TAGS:
            with self.subTest(tag=tag):
                lines = (REPO / _per_loop_deck(tag)).read_text().splitlines()
                self.assertEqual([tag], list(_loop_blocks(lines)))
                for other in TIMING_LOOP_TAGS:
                    if other == tag:
                        continue
                    self.assertNotIn(
                        f"{other}_drdy", "\n".join(lines),
                        f"{_per_loop_deck(tag)} still references loop {other}'s "
                        "nodes -- the split leaked a second loop into this deck",
                    )

    def test_each_loop_block_is_byte_identical_to_the_five_loop_deck(self):
        for tag in TIMING_LOOP_TAGS:
            with self.subTest(tag=tag):
                lines = (REPO / _per_loop_deck(tag)).read_text().splitlines()
                self.assertEqual(
                    self.five[tag],
                    _loop_blocks(lines)[tag],
                    f"loop {tag} differs between {FIVE_LOOP_DECK} and "
                    f"{_per_loop_deck(tag)} -- the per-loop split has stopped "
                    "being a pure re-composition, so the five-loop deck's "
                    "ratified bounds no longer transfer to it",
                )

    def test_the_shared_pvt_preamble_and_clock_are_unchanged(self):
        """Everything ahead of the first loop (`.param` block, `.model`, the
        clock source) is the loops' shared environment; a per-loop deck that
        drifted here would be simulating a different stimulus."""
        five = (REPO / FIVE_LOOP_DECK).read_text().splitlines()
        head = five[: next(i for i, l in enumerate(five) if l.startswith("* ---- loop "))]
        preamble = [l for l in head if l.startswith((".param", ".model", "vclk "))]
        self.assertTrue(preamble, "five-loop deck preamble not found")
        for tag in TIMING_LOOP_TAGS:
            with self.subTest(tag=tag):
                lines = (REPO / _per_loop_deck(tag)).read_text().splitlines()
                self.assertEqual(
                    preamble,
                    [l for l in lines if l.startswith((".param", ".model", "vclk "))],
                )


class PerLoopManifestBoundsTests(unittest.TestCase):
    """Issue #311: the five per-loop `tb.json` manifests must PARTITION the
    five-loop manifest's measurements -- same names, same expressions, same
    numeric limits -- with nothing dropped, duplicated, widened or tightened.

    Issue #311 forbids changing any bound; this is the check that makes that
    prohibition enforceable rather than a promise. Descriptions are allowed
    to differ (each split manifest explains its own loop), numbers are not.
    No PDK needed -- committed files only.
    """

    @classmethod
    def setUpClass(cls):
        missing = [
            slug
            for slug in (FIVE_LOOP_SLUG, *(_per_loop_slug(t) for t in TIMING_LOOP_TAGS))
            if not (REPO / "sim" / slug / "testbench" / "tb.json").is_file()
        ]
        if missing:
            raise unittest.SkipTest(f"manifest(s) not committed yet: {missing}")
        cls.base = _manifest(FIVE_LOOP_SLUG)
        cls.split = {t: _manifest(_per_loop_slug(t)) for t in TIMING_LOOP_TAGS}

    @staticmethod
    def _limits(check: dict) -> dict:
        return {k: v for k, v in check.items() if k != "description"}

    def test_the_split_manifests_partition_the_measurements(self):
        seen: dict[str, str] = {}
        for tag, man in self.split.items():
            for name in man["measure"]:
                self.assertNotIn(
                    name, seen,
                    f"{name} is measured by both {seen.get(name)} and {tag} -- "
                    "the split must partition the measurements, not duplicate them",
                )
                seen[name] = tag
        self.assertEqual(sorted(self.base["measure"]), sorted(seen))

    def test_every_measurement_expression_is_carried_over_unchanged(self):
        for tag, man in self.split.items():
            for name, expr in man["measure"].items():
                with self.subTest(tag=tag, measurement=name):
                    self.assertEqual(self.base["measure"][name], expr)

    def test_every_bound_is_carried_over_unchanged(self):
        union = {}
        for man in self.split.values():
            for name, check in man["checks"].items():
                union[name] = self._limits(check)
        self.assertEqual(
            {n: self._limits(c) for n, c in self.base["checks"].items()},
            union,
            "issue #311 explicitly forbids changing any tb.json bound; a limit "
            "moved between the five-loop deck and the per-loop split",
        )

    def test_bad_stays_the_negative_control(self):
        check = self.split["bad"]["checks"]["abs_err_delay_70ns"]
        self.assertEqual({"min": 0.9}, self._limits(check))
        self.assertNotIn(
            "max", check,
            "`bad` must assert the conversion IS wrong -- a max bound here "
            "would turn the family's only negative control into a pass case",
        )

    def test_each_manifest_only_reads_its_own_loops_nodes(self):
        for tag, man in self.split.items():
            others = [t for t in TIMING_LOOP_TAGS if t != tag]
            for line in man["analyses"]:
                with self.subTest(tag=tag, analysis=line):
                    for other in others:
                        self.assertNotIn(
                            f"v({other}_", line,
                            f"{_per_loop_slug(tag)} measures loop {other}'s nodes, "
                            "which its own deck does not instantiate",
                        )

    def test_the_tran_line_and_pvt_axes_are_unchanged(self):
        for tag, man in self.split.items():
            with self.subTest(tag=tag):
                self.assertEqual(self.base["analyses"][0], man["analyses"][0])
                self.assertTrue(man["analyses"][0].startswith("tran "))
                for field in (
                    "nominal_supply_v",
                    "supply_tolerance",
                    "temperatures_c",
                    "corners",
                ):
                    self.assertEqual(self.base[field], man[field], field)

    def test_each_analysis_meas_name_is_used_and_each_measure_name_defined(self):
        for tag, man in self.split.items():
            defined = {
                line.split()[2]
                for line in man["analyses"]
                if line.lower().startswith("meas ")
            }
            used = set()
            for expr in man["measure"].values():
                used.update(n for n in defined if n in expr)
            with self.subTest(tag=tag):
                self.assertEqual(
                    defined, used,
                    f"{_per_loop_slug(tag)} runs meas lines no measurement reads "
                    "(or reads one it does not run) -- dead simulated time",
                )


class ComparatorOutputSlewTests(unittest.TestCase):
    """Issue #296: the UNDELAYED comparators in the gate-level decks must not
    drive a real standard-cell gate input from a zero-time ideal step.

    This is the structural half of #296's fix and it is asserted here, on the
    committed artifacts, because the failure it prevents is silent in code
    review: reverting the network re-introduces an ngspice
    `Timestep too small ... trouble with node "b<tag>cmp#branch"` abort that
    only shows up hours into a corner run. No PDK needed -- this only reads
    files that are already committed.

    Three separate properties, each of which #296 depends on:

    1. Every undelayed gate-level comparator reaches the DUT through the
       first-order network (`b...cmp -> <tag>_cmpd`, `r...cmps`, `c...cmpl`),
       never straight onto `<tag>_cmpo`.
    2. The DECISION is still the original hard ternary. A soft/high-gain
       comparator was measured and rejected (it holds real cell inputs at
       mid-rail and aborts on `vvdd_gate#branch` instead) -- and it would also
       quietly invalidate the timing deck's `tie` loop, whose claim
       presupposes a comparator that always resolves to a rail.
    3. The rung-1 IDEAL decks are NOT changed: they drive an XSPICE bridge
       with no analog load, so they keep the original single-line form and
       stay byte-identical to their committed, already-ratified text.

    Issue #311 note: the per-loop split decks are covered here too. The
    split re-emits the same loop blocks, so #296's fix travels with them for
    free -- but a regression in the split's composition could drop it
    silently on decks nobody had asserted anything about, and those are
    precisely the decks the 45-point grid now runs.
    """

    GATE_DECKS = (
        ("sim/sar-logic-functional-gates/testbench/tb_sar_logic_functional_gates.spice",
         ("se", "df")),
        (FIVE_LOOP_DECK, ("ok", "tie")),
        (_per_loop_deck("ok"), ("ok",)),
        (_per_loop_deck("tie"), ("tie",)),
    )
    #: loops whose comparator drives a matched 50 ohm terminated T-line
    #: instead of a bare gate input -- deliberately left alone by #296.
    DELAYED_TAGS = ("lt", "xl", "bad")
    IDEAL_DECKS = (
        "design/sar-logic/sar_ctrl.spice",
        "sim/sar-logic-functional/testbench/tb_sar_logic_functional.spice",
        "sim/sar-logic-timing/testbench/tb_sar_logic_timing.spice",
    )

    @staticmethod
    def _decision(tag: str, out: str) -> str:
        return f"b{tag}cmp {out} 0 V = v({tag}_topp) > v({tag}_topn) ? vdd_val : 0"

    def test_undelayed_gate_level_comparators_drive_through_an_rc(self):
        for rel, tags in self.GATE_DECKS:
            lines = (REPO / rel).read_text().splitlines()
            for tag in tags:
                with self.subTest(deck=rel, tag=tag):
                    self.assertIn(
                        self._decision(tag, f"{tag}_cmpd"), lines,
                        f"{rel}: {tag} comparator decision line missing or altered",
                    )
                    self.assertNotIn(
                        self._decision(tag, f"{tag}_cmpo"), lines,
                        f"{rel}: {tag} comparator drives the DUT gate input directly "
                        "again -- issue #296's zero-time-step abort is back",
                    )
                    series = [l for l in lines if l.startswith(f"r{tag}cmps ")]
                    shunt = [l for l in lines if l.startswith(f"c{tag}cmpl ")]
                    self.assertEqual(len(series), 1, f"{rel}: {tag} series R missing")
                    self.assertEqual(len(shunt), 1, f"{rel}: {tag} shunt C missing")
                    self.assertTrue(
                        series[0].startswith(f"r{tag}cmps {tag}_cmpd {tag}_cmpo "),
                        f"{rel}: {tag} series R is not between the decision node and "
                        f"the DUT-facing net: {series[0]!r}",
                    )
                    self.assertTrue(
                        shunt[0].startswith(f"c{tag}cmpl {tag}_cmpo 0 "),
                        f"{rel}: {tag} shunt C is not on the DUT-facing net: {shunt[0]!r}",
                    )

    def test_delayed_timing_loops_are_untouched(self):
        for rel, tag in (
            *((FIVE_LOOP_DECK, t) for t in self.DELAYED_TAGS),
            *((_per_loop_deck(t), t) for t in self.DELAYED_TAGS),
        ):
            self._assert_delayed_loop_untouched(rel, tag)

    def _assert_delayed_loop_untouched(self, rel: str, tag: str):
        lines = (REPO / rel).read_text().splitlines()
        with self.subTest(deck=rel, tag=tag):
            self.assertIn(self._decision(tag, f"{tag}_cmpi"), lines)
            self.assertTrue(
                any(l.startswith(f"t{tag}d {tag}_cmpi 0 {tag}_cmpo 0 z0=50 td=")
                    for l in lines),
                f"{rel}: {tag}'s delay T-line changed -- the 50 ohm termination is "
                "what makes this loop immune to #296 in the first place",
            )
            self.assertIn(f"r{tag}term {tag}_cmpo 0 50", lines)
            self.assertEqual(
                [], [l for l in lines if l.startswith((f"r{tag}cmps ", f"c{tag}cmpl "))],
                f"{rel}: {tag} gained a #296 output network it does not need",
            )

    def test_ideal_rung1_decks_keep_the_original_single_line_comparator(self):
        for rel in self.IDEAL_DECKS:
            path = REPO / rel
            if not path.is_file():
                self.skipTest(f"{rel} not present")
            text = path.read_text()
            with self.subTest(deck=rel):
                self.assertNotIn(
                    "cmps ", text,
                    f"{rel}: a #296 comparator output network leaked into a rung-1 "
                    "ideal deck, whose committed text must stay byte-identical",
                )
                self.assertNotIn("cmpl ", text)
                self.assertNotIn("_cmpd ", text)


if __name__ == "__main__":
    unittest.main()
