#!/usr/bin/env python3
"""The committed SAR-sequencer gate-level netlists must (a) still implement
`design/sar-logic/rtl/sar_ctrl.v` -- proven formally, on *any* synthesis
toolchain -- and (b) be byte-reproducible from a fresh `klt synthesize` run,
on the one pinned toolchain that produced them (issue #272, DR-0023 follow-on
(a); pinning and the split into two checks: issue #316).

    python3 -m unittest discover -s sim/tests -v

This is the same "generator is the source of truth, diff a fresh run against
the committed artifact" discipline `test_sar_logic_netlist.py` already
enforces for the rung-1 ideal-XSPICE model, applied to the rung-3 gate-level
netlist `design/sar-logic/flow/synth_sar_ctrl.py` produces -- with one
correction this generator needs and the rung-1 one does not: its output is
not a pure function of the repo's own sources. See "Two checks, not one"
below.

## Why this test SKIPS on the headless CI path, unlike its rung-1 sibling

Unlike `gen_sar_logic.py` (stdlib Python, no external tool), regenerating the
gate netlist needs `klt synthesize` (Yosys + bundled ABC) resolving a real
gf180mcu standard-cell liberty file -- i.e. `klt` on `$PATH` *and* an
installed PDK. `.github/workflows/ci.yml`'s own header is explicit that the
default PR path installs neither (`klt` has no PyPI release yet, same
constraint that already excludes `layout/drc/run_drc.py` and
`layout/lvs/run_lvs.py` from execution there), so the tool-dependent classes
below skip cleanly (not a failure) when either tool or the PDK is
unavailable, rather than either hanging the headless run or producing a false
failure that carries no signal about whether the netlist actually drifted.

Where they DO run: any environment with `klt`, `yosys`, and the gf180mcu PDK
on `$PATH` / resolvable (a contributor's machine per
`docs/environment-setup.md`, or a future CI job that installs `klt` --
tracked by the same follow-on issue that owns the gate-level corner-grid
replay `design/sar-logic/rtl/README.md`'s "Verification performed" section
points at). `sim/selftest.sh`'s stage 1 (this discovery command) already runs
in both places, so no new wiring is needed once `klt` becomes CI-installable.

`PinnedToolchainProvenanceTests` needs no tools at all and therefore runs
*everywhere*, including that headless path.

## Two checks, not one (issue #316)

`klt synthesize`'s output is a function of the RTL **and** of the exact
Yosys/ABC build that maps it. Two Yosys releases produce two different --
both correct, both fully mapped, both equivalent -- netlists from identical
RTL: measured on `sar_ctrl.v` with no RTL change at all, `mcu7t5v0` came out
as 181 cells / `area_um2` 4961.152 on Yosys 0.69+post and 189 cells /
`area_um2` 5051.1552 on Yosys 0.33. So "fresh bytes == committed bytes" is a
*reproducibility* claim about one pinned toolchain, and cannot be the *drift*
guard on its own: on any other build it reports a difference that has nothing
to do with the RTL, under remediation text ("run `synth_sar_ctrl.py`") whose
effect would be to overwrite correct goldens with version-skewed ones and
silently re-baseline every downstream artifact built on them (the STA / P&R
records under `design/sar-logic/flow/sar_ctrl/records/`). Issue #316 is that
failure mode.

So the two claims are tested separately, by what each one actually needs:

| Class | Claim | Runs when |
|---|---|---|
| `PinnedToolchainProvenanceTests` | the committed netlists name one pinned toolchain, and it is documented | always (no tools needed) |
| `GateNetlistEquivalenceTests` | the committed netlists still implement the current RTL (`klt equiv`, `yosys-sequential`) | `klt` + `yosys` + PDK, **any** versions |
| `GateNetlistDriftTests` | a fresh synthesis reproduces the committed bytes exactly | `klt` + `yosys` + PDK, **pinned** versions only |

`GateNetlistEquivalenceTests` is the version-independent drift guard: a
genuine RTL-vs-netlist drift (RTL edited without re-running the flow) breaks
the equivalence proof that was the committed netlist's whole warrant, and
`klt equiv` says so on whatever Yosys the host happens to have. Only
`"equivalent"` passes. Measured on the two drift injections in issue #316's
PR (a sequential one, `drdy = ph[15]` -> `ph[14]`, and a purely
combinational one, `samp_tp_n = ph[0]|ph[1]|ph[2]` -> `ph[0]|ph[1]`), both
libraries came back `"inconclusive"` rather than `"counterexample"` on `klt
0.4.0` / Yosys 0.67 -- the induction bound could not refute equivalence
either. That is still a failure here, and the failure text says which of the
two it was rather than overclaiming: losing a proof this netlist *had* when
it was committed is the signal, whether or not the engine can also exhibit
the divergence (the same distinction `synth_sar_ctrl.py`'s record renderer
draws between `counterexample` and `inconclusive`).

`GateNetlistDriftTests` adds, on the pinned toolchain only, the stronger
bit-exactness property -- and *skips* (with an explicit "do not regenerate"
warning) everywhere else, instead of failing dishonestly.

The pin itself is not written down twice: it is parsed out of the committed
netlist's own `/* Generated by Yosys <version> (git sha1 <sha>...) */`
preamble, which is the artifact's own provenance, so it cannot drift from the
artifact it describes. `PINNED_KLT_VERSION` below is the one value that has
no such in-artifact witness (`klt --version` is recorded only in the evidence
records), and `PinnedToolchainProvenanceTests` asserts both of them against
`docs/environment-setup.md` so the documented pin cannot drift either.

## Why re-running the driver IS the (bit-exactness) check

`design/sar-logic/flow/synth_sar_ctrl.py` normally writes its netlist to the
committed path (`design/sar-logic/flow/sar_ctrl/netlist/sar_ctrl.<lib>.
synth.v`). So on the pinned toolchain the reproducibility check is exactly:
re-run the driver against a fresh RTL read and diff the result against the
committed file. A real drift shows up as a changed file; a clean run
reproduces the committed bytes exactly, because `klt synthesize`'s Yosys/ABC
recipe and the PDK's liberty file are then both pinned inputs (see the
committed records under `design/sar-logic/flow/sar_ctrl/records/` for the
exact tool/PDK versions this was last generated against).

## Isolation from the committed tree (issue #287)

`GateNetlistDriftTests` invokes the driver with `--out-dir <tmp>` (a
`tempfile.TemporaryDirectory` outside the repo) and `--no-record`, so the
fresh synthesis run its comparison depends on never writes through the
driver's real, tracked `netlist/`/`reports/` output paths -- running this
test (or `npm run check:ci`, which includes it) cannot leave the working
tree dirty, regardless of whether the comparison passes or fails.

`GateNetlistEquivalenceTests` needs the same isolation, but cannot use
`/tmp`: `klt equiv` drops its Yosys scripts/logs in a `.klt/equiv/`
directory *next to the request file* (`docs/cli/equiv.md`), and a
WASI-sandboxed `yosys` (e.g. `yowasp-yosys`, a perfectly normal way to have
Yosys on Linux) cannot read a script under `/tmp` because its sandbox does
not preopen that path. So its scratch dir goes under `sim/.work/` -- already
gitignored as "derived artifacts: regenerated on every run, never evidence"
-- and is deleted on the way out. The working tree stays clean either way.

## Yosys-version-preamble tolerance (issue #287, AC #3, option (a))

The committed netlists embed the exact `yosys -V` string that produced them
as their first line (`/* Generated by Yosys <version> ... */`). The
bit-exactness comparison normalizes (strips) that one preamble line from both
sides before comparing, so it asserts the synthesized logic itself rather
than the banner. Note what this tolerance is *not*: it absorbs the banner
line only, never a mapping difference, which is why the version gate above it
exists at all (issue #316).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FLOW_SCRIPT = REPO / "design" / "sar-logic" / "flow" / "synth_sar_ctrl.py"
RTL_SOURCE = REPO / "design" / "sar-logic" / "rtl" / "sar_ctrl.v"
SETUP_DOC = REPO / "docs" / "environment-setup.md"
NETLIST_DIR = REPO / "design" / "sar-logic" / "flow" / "sar_ctrl" / "netlist"
NETLISTS = {
    "mcu7t5v0": NETLIST_DIR / "sar_ctrl.mcu7t5v0.synth.v",
    "mcu9t5v0": NETLIST_DIR / "sar_ctrl.mcu9t5v0.synth.v",
}

#: Scratch root for `klt equiv`'s own `.klt/equiv/` artifacts -- inside the
#: repo (a WASI-sandboxed `yosys` cannot read scripts under `/tmp`), but
#: gitignored, so the working tree stays clean. See the module docstring's
#: "Isolation from the committed tree" section.
SCRATCH_ROOT = REPO / "sim" / ".work"

#: The `klt` version the committed netlists were synthesized with, from
#: `design/sar-logic/flow/sar_ctrl/records/20260910-224930-2d1394f.<lib>.md`
#: ("`klt`: `klt 0.4.0`"). Unlike the Yosys pin -- which is parsed out of the
#: committed netlist's own preamble and so cannot drift from it -- `klt`
#: leaves no version stamp inside the netlist, so this is the one pin that
#: has to be a constant. `PinnedToolchainProvenanceTests` asserts it appears
#: in `docs/environment-setup.md`, so the two cannot disagree silently.
PINNED_KLT_VERSION = "0.4.0"

_YOSYS_PREAMBLE_RE = re.compile(r"^/\* Generated by Yosys .*\*/\n", re.MULTILINE)
#: `Yosys 0.69+post (git sha1 143eb14f..., Release, AppleClang ...)` -- as it
#: appears both in `yosys -V` output and in a written netlist's preamble.
_YOSYS_BUILD_RE = re.compile(r"Yosys (?P<version>[^\s(]+)(?:\s+\(git sha1 (?P<sha>[0-9a-f]+))?")
#: `klt 0.4.0` / `klt 0.4.0+g2f64ab88bfcc.dirty` -- the trailing local-version
#: segment identifies the checkout, not the release, and is not compared.
_KLT_VERSION_RE = re.compile(r"klt (?P<version>\d+\.\d+\.\d+)")


class YosysBuild(NamedTuple):
    """One Yosys build's identity: its release string plus, when the banner
    carries one, its git sha (abbreviated to a build-dependent width -- so
    compare shas by common prefix, never for equality)."""

    version: str
    sha: str = ""

    def describe(self) -> str:
        return f"Yosys {self.version}" + (f" (git sha1 {self.sha})" if self.sha else "")

    def matches(self, other: YosysBuild) -> bool:
        if self.version != other.version:
            return False
        if not self.sha or not other.sha:
            return True
        width = min(len(self.sha), len(other.sha))
        return self.sha[:width] == other.sha[:width]


def _normalize_yosys_preamble(text: str) -> str:
    """Strip the `/* Generated by Yosys <version> ... */` preamble line --
    see this module's "Yosys-version-preamble tolerance" docstring section."""
    return _YOSYS_PREAMBLE_RE.sub("", text, count=1)


def parse_yosys_build(text: str) -> YosysBuild | None:
    """Pull a :class:`YosysBuild` out of a `yosys -V` banner or a netlist
    preamble line; ``None`` when the text carries no Yosys banner at all."""
    match = _YOSYS_BUILD_RE.search(text)
    if match is None:
        return None
    return YosysBuild(match.group("version"), match.group("sha") or "")


def pinned_yosys_build(netlist_path: Path) -> YosysBuild | None:
    """The Yosys build that wrote a committed netlist, read from the netlist's
    own preamble -- the artifact's self-description, not a hand-kept pin."""
    with netlist_path.open() as handle:
        return parse_yosys_build(handle.readline())


def installed_yosys_build() -> YosysBuild | None:
    result = subprocess.run(["yosys", "-V"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return parse_yosys_build(result.stdout or result.stderr)


def installed_klt_version() -> str | None:
    """The installed `klt` release, with any `+g<sha>.dirty` local segment
    dropped; ``None`` if `klt --version` does not report a parseable one."""
    result = subprocess.run(["klt", "--version"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    match = _KLT_VERSION_RE.search(result.stdout or result.stderr)
    return match.group("version") if match else None


def _tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def _load_flow():
    """Load `design/sar-logic/flow/synth_sar_ctrl.py` as a module, to reuse
    its `klt equiv` invocation (`run_equiv`) and liberty-path resolution
    rather than re-implementing either here."""
    spec = importlib.util.spec_from_file_location("synth_sar_ctrl", FLOW_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: What to do about a non-`equivalent` verdict, shared by both non-pass
#: statuses. Deliberately NOT "re-run the flow": on a non-pinned toolchain
#: that re-baselines the goldens (issue #316), which is a decision, not a
#: test fix.
_EQUIV_REMEDIATION = (
    "Do not 'fix' this by committing a fresh synthesis unless you are on the pinned "
    "toolchain (docs/environment-setup.md §8) AND the RTL change was intended: "
    "regenerating re-baselines the committed netlists and every STA/P&R record "
    "derived from them (design/sar-logic/flow/sar_ctrl/records/), which needs a "
    "decision record."
)

#: Per-status wording for a non-`equivalent` `klt equiv` verdict. `klt equiv`
#: distinguishes a *proven* divergence from a failure to prove either way,
#: and so does this message -- `inconclusive` is not a pass, but it is also
#: not proof of drift (the same distinction `synth_sar_ctrl.py`'s own record
#: renderer draws).
_EQUIV_VERDICTS = {
    "counterexample": (
        "`klt equiv` PROVED a divergence (and confirmed it by simulation): the "
        "committed gate netlist no longer implements the RTL. Unlike a byte "
        "difference this verdict is toolchain-independent, so it is real drift, not "
        "a mapping difference."
    ),
    "inconclusive": (
        "`klt equiv` could neither prove nor refute equivalence within its "
        "induction bound/timeout. This is NOT a pass: on a netlist that was proven "
        "`equivalent` when it was committed, losing the proof is itself the signal "
        "-- either the RTL and the netlist have drifted apart, or the engine's "
        "bound no longer suffices for this design. Investigate before trusting the "
        "committed netlist."
    ),
}


def _equiv_failure_message(netlist: Path, response: dict) -> str:
    status = response.get("status")
    verdict = _EQUIV_VERDICTS.get(
        status, f"`klt equiv` returned an unknown status {status!r} -- investigate."
    )
    return (
        f"{netlist.relative_to(REPO)} vs {RTL_SOURCE.relative_to(REPO)}: {verdict} "
        f"{_EQUIV_REMEDIATION} counterexample: {response.get('counterexample')!r}, "
        f"diagnostics: {response.get('diagnostics')!r}"
    )


def _require_toolchain():
    """Skip unless `klt`, `yosys` and a resolvable PDK are all present, and
    the committed netlists this module compares against exist. Returns the
    resolved :class:`sim.harness.pdk.Pdk`."""
    for tool in ("klt", "yosys"):
        if not _tool_available(tool):
            raise unittest.SkipTest(
                f"{tool!r} not found on $PATH -- see "
                "design/sar-logic/flow/synth_sar_ctrl.py's module docstring "
                "and docs/environment-setup.md"
            )
    from sim.harness.pdk import PdkNotFound, find_pdk  # noqa: PLC0415

    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        raise unittest.SkipTest(str(exc)) from exc

    for lib, path in NETLISTS.items():
        if not path.is_file():
            raise AssertionError(f"committed netlist missing for {lib}: {path}")
    return pdk


class YosysBuildParsingTests(unittest.TestCase):
    """Unit coverage for the version gate's own logic.

    The gate below decides whether the byte comparison runs at all, so its
    banner parsing and its deliberately prefix-tolerant sha comparison are
    verified here directly rather than being taken on trust from whichever
    single Yosys the host happens to have installed. No tools needed.
    """

    #: Verbatim first line of `design/sar-logic/flow/sar_ctrl/netlist/
    #: sar_ctrl.mcu7t5v0.synth.v` (the pinned build; full 40-char sha).
    PREAMBLE = (
        "/* Generated by Yosys 0.69+post (git sha1 "
        "143eb14f9cc55d6f8927e68523b0c9d2166ed02c, Release, AppleClang "
        "clang++ 21.0.0.21000101) */"
    )
    #: Verbatim `yosys -V` from a yowasp-yosys 0.67 build -- note the sha is
    #: abbreviated to 9 chars, which is why `matches` compares by prefix.
    BANNER_0_67 = (
        "Yosys 0.67 (git sha1 2d1509d1b, Release, Clang "
        "/workspace/YoWASP/yosys/wasi-sdk-33.0-x86_64-linux/share/cmake/../..//bin/"
        "clang++ 22.1.0)"
    )

    def test_a_netlist_preamble_parses_to_version_and_full_sha(self):
        build = parse_yosys_build(self.PREAMBLE)
        self.assertEqual(
            build, YosysBuild("0.69+post", "143eb14f9cc55d6f8927e68523b0c9d2166ed02c")
        )

    def test_a_yosys_v_banner_parses_to_version_and_abbreviated_sha(self):
        self.assertEqual(parse_yosys_build(self.BANNER_0_67), YosysBuild("0.67", "2d1509d1b"))

    def test_a_banner_without_a_sha_parses_to_a_version_only_build(self):
        self.assertEqual(parse_yosys_build("Yosys 0.33 (Release)"), YosysBuild("0.33", ""))

    def test_text_with_no_yosys_banner_parses_to_none(self):
        self.assertIsNone(parse_yosys_build("module sar_ctrl_a(clk, start);\n"))

    def test_the_same_build_matches_across_sha_abbreviation_widths(self):
        full = YosysBuild("0.69+post", "143eb14f9cc55d6f8927e68523b0c9d2166ed02c")
        short = YosysBuild("0.69+post", "143eb14f9")
        self.assertTrue(full.matches(short))
        self.assertTrue(short.matches(full))

    def test_a_different_sha_at_the_same_version_does_not_match(self):
        """A rebuilt/patched Yosys claiming the same release string is still
        a different build, and byte reproducibility is not claimed for it."""
        self.assertFalse(
            YosysBuild("0.69+post", "143eb14f9").matches(YosysBuild("0.69+post", "deadbeef1"))
        )

    def test_a_different_version_does_not_match(self):
        self.assertFalse(
            parse_yosys_build(self.PREAMBLE).matches(parse_yosys_build(self.BANNER_0_67))
        )

    def test_a_missing_sha_falls_back_to_the_version_alone(self):
        """A build whose banner carries no sha can only be compared by
        version -- refusing everything would skip the byte check on hosts
        where it would in fact be valid."""
        self.assertTrue(YosysBuild("0.69+post", "143eb14f9").matches(YosysBuild("0.69+post")))
        self.assertFalse(YosysBuild("0.69+post", "143eb14f9").matches(YosysBuild("0.67")))


class PinnedToolchainProvenanceTests(unittest.TestCase):
    """The committed netlists' own provenance, and its documentation.

    Needs no tools and no PDK, so unlike the two tool-dependent classes in
    this module it runs everywhere -- including the headless CI path. It is
    what makes the pin the *repo's* pin rather than one machine's folklore
    (issue #316).
    """

    def test_both_committed_netlists_name_one_pinned_yosys_build(self):
        builds = {}
        for lib, path in NETLISTS.items():
            self.assertTrue(path.is_file(), f"committed netlist missing for {lib}: {path}")
            build = pinned_yosys_build(path)
            self.assertIsNotNone(
                build,
                f"{path} has no `/* Generated by Yosys <version> ... */` preamble -- "
                "the netlists' Yosys pin is read from that line "
                "(sim/tests/test_sar_ctrl_gate_netlist.py, issue #316)",
            )
            builds[lib] = build
        first_lib, first_build = next(iter(builds.items()))
        for lib, build in builds.items():
            self.assertTrue(
                first_build.matches(build),
                "the committed netlists disagree about which Yosys built them: "
                f"{first_lib} says {first_build.describe()}, {lib} says "
                f"{build.describe()}. Both are written by one `synth_sar_ctrl.py` run "
                "and must come from one build -- re-run the flow (whole, not "
                "per-library) on the pinned toolchain, see "
                "docs/environment-setup.md §8.",
            )

    def test_the_pinned_toolchain_is_documented_in_environment_setup(self):
        """`docs/environment-setup.md` must state the pin the committed
        netlists actually carry -- the fix for issue #316's "discoverable only
        from an evidence record" half. Enforced, not merely requested: the
        expected values come from the artifacts/constant, not from the doc."""
        build = pinned_yosys_build(NETLISTS["mcu7t5v0"])
        self.assertIsNotNone(build, "committed netlist carries no Yosys preamble")
        doc = SETUP_DOC.read_text()
        fix = (
            ' -- update docs/environment-setup.md §8 ("Digital synthesis toolchain") '
            "to match the committed netlists under "
            "design/sar-logic/flow/sar_ctrl/netlist/. A pin nobody can look up is "
            "how issue #316 happened."
        )
        # `assertTrue(x in doc)` rather than `assertIn(x, doc)`: the latter
        # dumps this entire ~20 kB document into the failure output, burying
        # the one line that says what to do about it.
        self.assertTrue(
            build.version in doc,
            "docs/environment-setup.md does not record the pinned Yosys version "
            f"{build.version!r}{fix}",
        )
        if build.sha:
            self.assertTrue(
                build.sha in doc,
                "docs/environment-setup.md does not record the pinned Yosys git sha "
                f"{build.sha!r}{fix}",
            )
        self.assertTrue(
            PINNED_KLT_VERSION in doc,
            "docs/environment-setup.md does not record the pinned klt version "
            f"{PINNED_KLT_VERSION!r} (PINNED_KLT_VERSION in "
            f"sim/tests/test_sar_ctrl_gate_netlist.py){fix}",
        )


class GateNetlistEquivalenceTests(unittest.TestCase):
    """The version-INDEPENDENT drift guard: each committed gate netlist must
    still be formally equivalent to the current `sar_ctrl.v`.

    This is the check that catches a genuine drift -- RTL edited without
    re-running the flow -- and it does so on *any* `klt`/`yosys` build,
    because "implements the same sequential function" is a property of the
    netlist, not of whoever mapped it. PDK/`klt`/`yosys`-dependent; see the
    module docstring for why it SKIPS (not fails) when the toolchain is
    unavailable.
    """

    @classmethod
    def setUpClass(cls):
        cls.pdk = _require_toolchain()
        cls.flow = _load_flow()
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)

    def test_committed_netlists_still_implement_the_rtl(self):
        flow = self.flow
        with tempfile.TemporaryDirectory(
            prefix="sar_ctrl_gate_netlist_equiv_", dir=SCRATCH_ROOT
        ) as tmp:
            for lib, path in NETLISTS.items():
                cell_library = f"gf180mcu_fd_sc_{lib}"
                with self.subTest(library=lib):
                    liberty = flow._liberty_path(self.pdk, cell_library, flow.CORNER)
                    response = flow.run_equiv(
                        self.pdk,
                        cell_library,
                        path,
                        liberty,
                        Path(tmp) / f"{lib}.equiv_request.json",
                    )
                    status = response.get("status")
                    self.assertEqual(
                        status, "equivalent", _equiv_failure_message(path, response)
                    )


class GateNetlistDriftTests(unittest.TestCase):
    """The bit-exactness check, on the pinned toolchain ONLY.

    PDK/`klt`/`yosys`-dependent -- see the module docstring for why this
    SKIPS (not fails) when the toolchain is unavailable, and why a
    version-mismatched toolchain is one of those "unavailable" cases rather
    than a drift report (issue #316).
    """

    @classmethod
    def setUpClass(cls):
        cls.pdk = _require_toolchain()
        cls._require_pinned_toolchain()

    @classmethod
    def _require_pinned_toolchain(cls):
        """Skip -- loudly, and with an explicit "do not regenerate" -- unless
        the installed `klt`/`yosys` are the builds that wrote the committed
        netlists. A byte diff across two Yosys releases measures ABC/mapping
        differences, not RTL drift (issue #316)."""
        do_not = (
            "DO NOT re-run design/sar-logic/flow/synth_sar_ctrl.py to 'fix' this: on a "
            "differently-versioned toolchain that overwrites correct goldens with "
            "version-skewed ones and silently re-baselines every STA/P&R record built "
            "on them. GateNetlistEquivalenceTests is the toolchain-independent drift "
            "guard, and it does run here. See docs/environment-setup.md §8."
        )
        pinned = pinned_yosys_build(NETLISTS["mcu7t5v0"])
        if pinned is None:
            raise AssertionError(
                f"{NETLISTS['mcu7t5v0']} has no `/* Generated by Yosys ... */` preamble "
                "-- cannot tell which toolchain to compare bytes against (issue #316)"
            )
        installed = installed_yosys_build()
        if installed is None or not pinned.matches(installed):
            found = installed.describe() if installed else "an unparseable `yosys -V` banner"
            raise unittest.SkipTest(
                "byte-level reproducibility of the committed gate netlists is pinned to "
                f"one Yosys build: they were written by {pinned.describe()}, this host "
                f"has {found}. {do_not}"
            )
        klt_version = installed_klt_version()
        if klt_version != PINNED_KLT_VERSION:
            raise unittest.SkipTest(
                "byte-level reproducibility of the committed gate netlists is pinned to "
                f"klt {PINNED_KLT_VERSION}, this host has "
                f"{klt_version or 'an unparseable `klt --version`'}. {do_not}"
            )

    def test_committed_netlists_match_a_fresh_synthesis(self):
        committed = {lib: path.read_text() for lib, path in NETLISTS.items()}
        with tempfile.TemporaryDirectory(prefix="sar_ctrl_gate_netlist_drift_") as tmp:
            out_dir = Path(tmp) / "out"
            result = subprocess.run(
                [
                    sys.executable,
                    str(FLOW_SCRIPT),
                    "--no-record",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"synth_sar_ctrl.py exited {result.returncode}:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            for lib, path in NETLISTS.items():
                with self.subTest(library=lib):
                    fresh_path = out_dir / "netlist" / path.name
                    self.assertTrue(
                        fresh_path.is_file(),
                        f"fresh synthesis did not write {fresh_path}",
                    )
                    self.assertEqual(
                        _normalize_yosys_preamble(fresh_path.read_text()),
                        _normalize_yosys_preamble(committed[lib]),
                        f"{path} is stale relative to design/sar-logic/rtl/sar_ctrl.v -- "
                        f"run: python3 {FLOW_SCRIPT.relative_to(REPO)}\n"
                        "(this host IS the pinned toolchain -- see "
                        "docs/environment-setup.md §8 -- so a difference here is a real "
                        "drift, not a mapping difference.)",
                    )


if __name__ == "__main__":
    unittest.main()
