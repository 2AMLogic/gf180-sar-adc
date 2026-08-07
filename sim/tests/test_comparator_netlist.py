"""The comparator netlist is duplicated into every testbench -- prove it matches.

`sim/harness/README.md` forbids `.include` inside a testbench fragment, so the
comparator's devices are physically copied into each
live testbench that instantiates it. A copy that silently drifts from
`design/comparator/comparator.spice` would produce an evidence record that
looks valid while measuring a circuit nobody designed -- exactly the class of
silent failure the rest of this harness is built to catch.

This test is the guard. It runs in `sim/selftest.sh` stage 1 (no PDK, no
ngspice needed). `sim/tools/sync_comparator_netlist.py` is the fixer.

The set of files to guard is imported from that fixer (`targets()`) rather
than re-globbed here. Before issue #118 the two carried *separate* copies of a
`comparator-*/testbench/*.spice` pattern, so neither the fixer nor this test
could see the canonical block embedded in `sim/adc-inl-dnl/`,
`sim/adc-enob-fft/` or `sim/adc-power/` -- three live decks kept declaring a
superseded load resistor through a full review cycle (PR #121). One
definition, imported, is what stops the guard and the fixer disagreeing about
what is guarded.
"""

import importlib.util
import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "design" / "comparator" / "comparator.spice"
BEGIN = "* --- COMPARATOR-NETLIST-BEGIN"
END = "* --- COMPARATOR-NETLIST-END ---"

_SYNC = REPO / "sim" / "tools" / "sync_comparator_netlist.py"
_spec = importlib.util.spec_from_file_location("sync_comparator_netlist", _SYNC)
sync = importlib.util.module_from_spec(_spec)
sys.modules["sync_comparator_netlist"] = sync
_spec.loader.exec_module(sync)


def extract(path):
    lines = path.read_text().splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if ln.startswith(BEGIN)]
    ends = [i for i, ln in enumerate(lines) if ln.startswith(END)]
    assert len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0], (
        f"{path}: expected exactly one marker-delimited block"
    )
    return "".join(lines[starts[0] : ends[0] + 1])


class ComparatorNetlistCopies(unittest.TestCase):
    def test_canonical_file_exists_and_has_one_block(self):
        self.assertTrue(CANONICAL.is_file(), f"missing {CANONICAL}")
        block = extract(CANONICAL)
        self.assertIn(".subckt comparator", block)
        self.assertIn(".subckt preamp", block)
        self.assertIn(".subckt sarlatch", block)

    def test_every_testbench_copy_is_byte_identical(self):
        block = extract(CANONICAL)
        copies = sync.targets()
        self.assertTrue(
            copies,
            "no comparator testbench embeds the canonical netlist -- either the "
            "testbenches are missing or the markers were renamed",
        )
        for path in copies:
            with self.subTest(testbench=str(path.relative_to(REPO))):
                self.assertEqual(
                    extract(path),
                    block,
                    "stale copy; run python3 sim/tools/sync_comparator_netlist.py",
                )

    def test_guarded_set_covers_the_converter_level_decks(self):
        """The guarded set must not silently narrow back to `comparator-*/`.

        `test_every_testbench_copy_is_byte_identical` above is vacuously green
        on whatever subset `targets()` happens to return -- that is precisely
        how three stale copies survived a review cycle (issue #118 / PR #121).
        Name the decks that are known to embed the block and are NOT under
        `sim/comparator-*/`, so re-narrowing the pattern fails loudly here
        instead of quietly shrinking what the guard above proves.
        """
        guarded = {str(p.relative_to(REPO)) for p in sync.targets()}
        for rel in (
            "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl.spice",
            "sim/adc-inl-dnl/testbench/tb_adc_inl_dnl_extracted.spice",
            "sim/adc-enob-fft/testbench/tb_adc_enob_fft.spice",
            "sim/adc-enob-fft/testbench/tb_adc_enob_fft_extracted.spice",
            "sim/adc-power/testbench/tb_adc_power.spice",
            "sim/adc-power/testbench/tb_adc_power_extracted.spice",
            "sim/dr0014-sampling/testbench/tb_dr0014_sampling.spice",
            "sim/dr0014-sampling/testbench-extracted/tb_dr0014_sampling_extracted.spice",
            "sim/top-plate-cpar/testbench/tb_top_plate_cpar.spice",
        ):
            with self.subTest(testbench=rel):
                self.assertTrue((REPO / rel).is_file(), f"{rel} is missing")
                self.assertIn(rel, guarded)

    def test_no_snapshot_is_ever_a_sync_target(self):
        """Frozen evidence is never rewritten to match today's design.

        `netlist-snapshots/` records what a given run actually simulated
        (CLAUDE.md: "sim/ results are append-only evidence"). Those files carry
        the same BEGIN/END markers, so a careless widening of `TESTBENCH_GLOB`
        would have the fixer overwrite them and destroy the provenance every
        record in `sim/*/records/` depends on.
        """
        for path in sync.targets():
            self.assertNotIn(
                "netlist-snapshots",
                path.parts,
                f"{path} is frozen evidence and must never be a sync target",
            )

    def test_no_fragment_directives_in_the_canonical_block(self):
        # The same rule the harness enforces on fragments (sim/harness/README.md):
        # the block gets pasted into a deck the harness owns, so it must not
        # carry its own includes, corner libs, temperature or control block.
        forbidden = (".include", ".lib", ".temp", ".control", ".endc", ".end ")
        for line in extract(CANONICAL).splitlines():
            stripped = line.strip().lower()
            for bad in forbidden:
                self.assertFalse(
                    stripped.startswith(bad),
                    f"canonical comparator netlist must not contain '{bad}': {line}",
                )


if __name__ == "__main__":
    unittest.main()
