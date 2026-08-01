"""The comparator netlist is duplicated into every testbench -- prove it matches.

`sim/harness/README.md` forbids `.include` inside a testbench fragment, so the
comparator's devices are physically copied into each
`sim/comparator-*/testbench/*.spice`. A copy that silently drifts from
`design/comparator/comparator.spice` would produce an evidence record that
looks valid while measuring a circuit nobody designed -- exactly the class of
silent failure the rest of this harness is built to catch.

This test is the guard. It runs in `sim/selftest.sh` stage 1 (no PDK, no
ngspice needed). `sim/tools/sync_comparator_netlist.py` is the fixer.
"""

import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "design" / "comparator" / "comparator.spice"
BEGIN = "* --- COMPARATOR-NETLIST-BEGIN"
END = "* --- COMPARATOR-NETLIST-END ---"


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
        copies = [
            p
            for p in sorted((REPO / "sim").glob("comparator-*/testbench/*.spice"))
            if BEGIN in p.read_text()
        ]
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
