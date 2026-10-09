#!/usr/bin/env python3
"""Exit-status controls for the V_CM sweep driver and its characterize.sh caller.

    python3 -m unittest discover -s sim/tests -t sim/tests

Issue #456: `sim/characterize.sh` once classified the V_CM full sweep by
grepping for `exit=0`, so an ideal point that passed followed by an aborted
variant generation (or a failed `tee`) was reported as a successful sweep.
These controls drive the real shell scripts with stub `python3` / `tee`
executables on PATH. No ngspice, no PDK, no simulation: the scripts are copied
into a throwaway tree so nothing is written under the repo's sim/ evidence or
`sim/.work`.

Stub `python3` behaviour is chosen per sweep point through environment
variables: GEN_FAIL=<tag> fails variant generation for that point;
RUN_FAIL=<tag>[:code] makes that point's `run_corners.py` exit non-zero.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]

PY_STUB = r"""#!/usr/bin/env bash
# Stub python3: never simulates anything.
args="$*"
case "$args" in
  # run_corners.py args cite gen_vcm_variant.py in --netlist-provenance, so
  # match the generator by its own argv[1] instead.
  "sim/vcm-drive-impedance/gen_vcm_variant.py "*)
    if [[ "$args" == *"--out "*"tb_vcm_${GEN_FAIL:-@none@}.spice"* ]]; then
      echo "stub: variant generation failed" >&2; exit 3
    fi
    exit 0;;
  *run_corners.py*vcm-drive-impedance*)
    tag=ideal
    for t in budget 5x-over-budget; do
      [[ "$args" == *"tb_vcm_${t}.spice"* ]] && tag=$t
    done
    spec="${RUN_FAIL:-}"
    if [ -n "$spec" ] && [ "${spec%%:*}" = "$tag" ]; then
      code="${spec#*:}"; [ "$code" = "$spec" ] && code=1
      exit "$code"
    fi
    exit 0;;
esac
exit 0
"""

TEE_FAIL_STUB = "#!/usr/bin/env bash\ncat >/dev/null\nexit 1\n"


def _exe(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class _Tree(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        sim = self.root / "sim"
        (sim / "vcm-drive-impedance").mkdir(parents=True)
        shutil.copy(SIM / "characterize.sh", sim / "characterize.sh")
        shutil.copy(
            SIM / "vcm-drive-impedance" / "run_sweep.sh",
            sim / "vcm-drive-impedance" / "run_sweep.sh",
        )
        self.bin = self.root / "bin"
        self.bin.mkdir()
        _exe(self.bin / "python3", PY_STUB)

    def _env(self, **extra: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k not in ("GEN_FAIL", "RUN_FAIL")}
        env["PATH"] = f"{self.bin}:{env['PATH']}"
        env["CHARACTERIZE_WORK"] = str(self.root / "work")
        env["JOBS"] = "1"
        env.update(extra)
        return env

    def sweep(self, *argv: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim/vcm-drive-impedance/run_sweep.sh"), *argv],
            capture_output=True, text=True, env=self._env(**env), cwd=self.root,
        )

    def characterize(self, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim/characterize.sh"), "characterize"],
            capture_output=True, text=True, env=self._env(**env), cwd=self.root,
        )


class RunSweepExitStatus(_Tree):
    def test_all_points_ok(self) -> None:
        r = self.sweep()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for tag in ("ideal", "budget", "5x-over-budget"):
            self.assertIn(f"  {tag} exit=0", r.stdout)

    def test_generation_failure_continues_and_fails(self) -> None:
        r = self.sweep(GEN_FAIL="budget")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("  ideal exit=0", r.stdout)
        self.assertIn("  budget exit=3", r.stdout)
        self.assertIn("  5x-over-budget exit=0", r.stdout)

    def test_nonzero_point_continues_and_fails(self) -> None:
        r = self.sweep(RUN_FAIL="ideal:7")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("  ideal exit=7", r.stdout)
        self.assertIn("  5x-over-budget exit=0", r.stdout)

    def test_unknown_selector_rejected(self) -> None:
        r = self.sweep("bogus")
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown point", r.stderr)
        self.assertNotIn("sweep point", r.stdout)

    def test_single_point_selector(self) -> None:
        r = self.sweep("budget")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("  budget exit=0", r.stdout)
        self.assertNotIn("ideal exit", r.stdout)


class CharacterizeVcmClassification(_Tree):
    def assert_sweep_failed(self, r: subprocess.CompletedProcess) -> None:
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("FAIL  vcm-drive-impedance full sweep", r.stdout)
        # Later campaigns still ran and are reported.
        self.assertIn("OK    mc-cdac-mismatch N=20000", r.stdout)
        self.assertIn("OK    comparator-regeneration extracted", r.stdout)

    def test_all_three_ok_is_success(self) -> None:
        r = self.characterize()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK    vcm-drive-impedance full sweep", r.stdout)

    def test_generation_failure_after_ideal(self) -> None:
        self.assert_sweep_failed(self.characterize(GEN_FAIL="budget"))

    def test_nonzero_point(self) -> None:
        self.assert_sweep_failed(self.characterize(RUN_FAIL="5x-over-budget:2"))

    def test_truncated_summary_with_zero_driver_status(self) -> None:
        fake = self.root / "fake_sweep.sh"
        _exe(fake, "#!/usr/bin/env bash\necho '  ideal exit=0'\nexit 0\n")
        self.assert_sweep_failed(self.characterize(VCM_SWEEP_SCRIPT=str(fake)))

    def test_missing_summary(self) -> None:
        fake = self.root / "fake_sweep.sh"
        _exe(fake, "#!/usr/bin/env bash\necho 'nothing useful'\nexit 0\n")
        self.assert_sweep_failed(self.characterize(VCM_SWEEP_SCRIPT=str(fake)))

    def test_tee_failure_after_good_output(self) -> None:
        _exe(self.bin / "tee", TEE_FAIL_STUB)
        self.assert_sweep_failed(self.characterize())

    def test_driver_abort_after_ideal(self) -> None:
        fake = self.root / "fake_sweep.sh"
        _exe(fake, "#!/usr/bin/env bash\necho '  ideal exit=0'\nexit 1\n")
        self.assert_sweep_failed(self.characterize(VCM_SWEEP_SCRIPT=str(fake)))


if __name__ == "__main__":
    unittest.main()
