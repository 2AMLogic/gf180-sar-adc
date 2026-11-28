#!/usr/bin/env bash
# test-verify-proposal-refs.sh - Tests for verify-proposal-refs.sh (issue
# #7658), the pre-file reference verifier for Hermit/Architect proposals.
#
# Hermit and Architect proposals bypass Curator — the only other role with a
# cited-path existence check — so a false citation (a path from a sibling
# repo, a nonexistent file, a stale line range, a false "N tracked files"
# count) reaches Champion unfiltered. verify-proposal-refs.sh is meant to run
# on the drafted body BEFORE `create-issue.sh`, blocking filing on any miss.
#
# This is a black-box test: verify-proposal-refs.sh is a full CLI script (no
# BASH_SOURCE guard to source functions from), so each case builds a real,
# tiny git repo with a fake `origin/main` ref (a local `update-ref`, no
# network) and runs the real script as a subprocess against a body-file
# fixture, asserting on exit code and output. Hermetic: no network, no live
# forge, no tokens.
#
# Usage:
#   ./.loom/scripts/tests/test-verify-proposal-refs.sh

set -uo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(cd "$TEST_DIR/.." && pwd)"
VPR="$SCRIPTS_DIR/verify-proposal-refs.sh"

# shellcheck source=lib/assert.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/assert.sh"


if [[ ! -x "$VPR" ]]; then
    echo -e "${RED}FATAL${NC}: $VPR not found or not executable" >&2
    exit 2
fi

# Since #8656 the line-range check is `loom-daemon git-blob-lines --range`, so
# every range assertion below (fixtures 3 and 6) needs a BUILT binary. FATAL,
# not a skip: the whole point of #8656 is that the range check now follows a
# 120000 tree entry to the document it points at, and a suite that quietly
# skipped itself would report green while re-admitting exactly the bug.
# shellcheck source=lib/require-daemon-bin.sh
source "$TEST_DIR/lib/require-daemon-bin.sh"
loom_test_require_daemon_bin "$SCRIPTS_DIR" "git-blob-lines" "verify-output-decl"

# Two `..` reaches repo-root/.claude/commands/loom for an INSTALLED copy
# (SCRIPTS_DIR is .loom/scripts there); one `..` reaches defaults/.claude/
# commands/loom when running inside this source repo (SCRIPTS_DIR is
# defaults/scripts) — the two layouts differ in depth, so probe both rather
# than hard-coding one (#6725, mirroring test-detect-dependency-cycle.sh).
if [[ -d "$SCRIPTS_DIR/../../.claude/commands/loom" ]]; then
    PROMPT_DIR="$(cd "$SCRIPTS_DIR/../../.claude/commands/loom" && pwd)"
else
    PROMPT_DIR="$(cd "$SCRIPTS_DIR/../.claude/commands/loom" && pwd)"
fi
HERMIT_MD="$PROMPT_DIR/hermit.md"
ARCHITECT_MD="$PROMPT_DIR/architect.md"
CHAMPION_PROMO_MD="$PROMPT_DIR/champion-issue-promo.md"

FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT" 2>/dev/null || true' EXIT

# --- Build a tiny fixture repo with a fake origin/main ref (no network: a
# local `update-ref` pointing at HEAD stands in for a fetched remote branch).
FIXTURE_REPO="$FIXTURE_ROOT/repo"
mkdir -p "$FIXTURE_REPO/src" "$FIXTURE_REPO/docs"
(
    cd "$FIXTURE_REPO" || exit 1
    git init -q -b main .
    git config user.email "test@example.com"
    git config user.name "Test"
    seq 1 5 > src/foo.py            # 5 lines
    printf 'line1\nline2\n' > docs/bar.md   # 2 lines
    git add .
    git commit -qm "init" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)

BODY_DIR="$FIXTURE_ROOT/bodies"
mkdir -p "$BODY_DIR"

run_vpr() {
    LOOM_WORKSPACE="$FIXTURE_REPO" "$VPR" "$1" 2>&1
}

echo "=== Fixture 1: clean body (all references correct) ==="
CLEAN_BODY="$BODY_DIR/clean.md"
cat > "$CLEAN_BODY" <<'EOF'
This proposal cites `src/foo.py:3` and `docs/bar.md:1-2` as evidence, and
notes there are 0 tracked `.pyc` files in this fixture repo.
EOF
OUT="$(run_vpr "$CLEAN_BODY")"
RC=$?
assert_eq "0" "$RC" "clean body exits 0"
assert_contains "$OUT" "all references check out" "clean body reports success"

echo
echo "=== Fixture 2: missing file ==="
MISSING_BODY="$BODY_DIR/missing.md"
cat > "$MISSING_BODY" <<'EOF'
See `src/does-not-exist.py:10` and `verification/_repo_utils.py` for context —
neither exists in this repo (a sibling-checkout citation, #7658's motivating
incident).
EOF
OUT="$(run_vpr "$MISSING_BODY")"
RC=$?
assert_eq "1" "$RC" "missing file exits 1"
assert_contains "$OUT" "MISSING FILE" "missing-file miss is labeled"
assert_contains "$OUT" "src/does-not-exist.py" "the specific missing path is named"

echo
echo "=== Fixture 2b: existing directory citations are not MISSING FILE (#10191) ==="
mkdir -p "$FIXTURE_REPO/tools/probes"
(
    cd "$FIXTURE_REPO" || exit 1
    printf 'x\n' > tools/probes/p.py
    git add tools
    git commit -qm "add tools/probes" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
DIR_BODY="$BODY_DIR/dir.md"
cat > "$DIR_BODY" <<'EOF'
Scope: tools/probes and `src/foo.py:3`.
EOF
OUT="$(run_vpr "$DIR_BODY")"
RC=$?
assert_eq "0" "$RC" "an existing directory citation exits 0"
assert_contains "$OUT" "all references check out" "an existing directory is not reported as a miss"

DIR_MISSING_BODY="$BODY_DIR/dir-missing.md"
cat > "$DIR_MISSING_BODY" <<'EOF'
Scope: tools/nonexistent-dir and tools/probes.
EOF
OUT="$(run_vpr "$DIR_MISSING_BODY")"
RC=$?
assert_eq "1" "$RC" "a nonexistent directory citation still exits 1"
assert_contains "$OUT" "tools/nonexistent-dir" "the nonexistent directory is named as a miss"

echo
echo "=== Fixture 2c: trailing-punctuation shapes on directory citations (#13901) ==="
# PATH_RE includes '.' in its class, so a prose `rtl-sketch/...` extracts
# whole and the dot-stripper leaves `rtl-sketch/` -- but `git ls-tree` emits
# tree entries with NO trailing slash, so the membership test false-missed an
# existing directory (#13901, third input of the #10191/#11338 class). The
# general shape is anything the extractor can leave on the end of a directory
# path that ls-tree does not emit; the sibling fixtures below assert the
# OBSERVED outcome of each shape against the extractor first: `dir/*`,
# `dir/**` and `dir/` leave the `*`/trailing slash unconsumed (`*` is not in
# the class and a trailing `/` has no component after it), so they yield
# `dir` -- or nothing for a one-component `model/` -- and cannot false-miss;
# only `dir/...` yields the slash-suffixed candidate.
(
    cd "$FIXTURE_REPO" || exit 1
    mkdir -p rtl-sketch
    printf 'x\n' > rtl-sketch/top.v
    git add rtl-sketch
    git commit -qm "add rtl-sketch" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
# The reproducer from #13901 includes single-component directory names and
# an ellipsis after `rtl-sketch/`.
ELLIPSIS_BODY="$BODY_DIR/ellipsis.md"
cat > "$ELLIPSIS_BODY" <<'EOF'
(`model/ spec/ tools/ fpga/ pnr/ rtl-sketch/...`) — the two repairs widen
EOF
OUT="$(run_vpr "$ELLIPSIS_BODY")"
RC=$?
assert_eq "0" "$RC" "an existing dir cited with a prose ellipsis (rtl-sketch/...) exits 0"
assert_contains "$OUT" "all references check out" "an ellipsis-suffixed directory citation is not a miss"

GLOB_BODY="$BODY_DIR/glob.md"
cat > "$GLOB_BODY" <<'EOF'
Scope: `tools/probes/*`, `tools/probes/**`, `tools/probes/`, and the
sentence-final `tools/probes.` plus `src/foo.py:3.` — every other trailing
shape of an existing-path citation.
EOF
OUT="$(run_vpr "$GLOB_BODY")"
RC=$?
assert_eq "0" "$RC" "glob, bare-slash and sentence-final dir citations produce no false miss"

NODIR_BODY="$BODY_DIR/nodir.md"
cat > "$NODIR_BODY" <<'EOF'
See `spec/nodir/...` for the directory the proposal plans to create.
EOF
OUT="$(run_vpr "$NODIR_BODY")"
RC=$?
assert_eq "1" "$RC" "a nonexistent dir cited with a prose ellipsis still exits 1"
assert_contains "$OUT" "MISSING FILE" "the nonexistent-ellipsis miss is labeled"
assert_contains "$OUT" "spec/nodir" "the nonexistent directory is named as a miss"

echo
echo "=== Fixture 3: bad line range ==="
BADRANGE_BODY="$BODY_DIR/badrange.md"
cat > "$BADRANGE_BODY" <<'EOF'
See `src/foo.py:9999` — this line range runs well past the end of the file.
EOF
OUT="$(run_vpr "$BADRANGE_BODY")"
RC=$?
assert_eq "1" "$RC" "bad line range exits 1"
assert_contains "$OUT" "BAD LINE RANGE" "bad-line-range miss is labeled"
assert_contains "$OUT" "src/foo.py:9999" "the specific bad range is named"

echo
echo "=== Fixture 4: false tracked claim ==="
TRACKED_BODY="$BODY_DIR/tracked.md"
cat > "$TRACKED_BODY" <<'EOF'
There are six tracked `.pyc` files in this repo (there are actually none).
EOF
OUT="$(run_vpr "$TRACKED_BODY")"
RC=$?
assert_eq "1" "$RC" "false tracked claim exits 1"
assert_contains "$OUT" "FALSE TRACKED CLAIM" "false-tracked-claim miss is labeled"
assert_contains "$OUT" "git ls-files shows 0" "the actual git ls-files count is reported"

echo
echo "=== Fixture 5: a true tracked claim does NOT miss ==="
TRUE_TRACKED_BODY="$BODY_DIR/true-tracked.md"
cat > "$TRUE_TRACKED_BODY" <<'EOF'
There are two tracked `*.md` files in this fixture repo.
EOF
(
    cd "$FIXTURE_REPO" || exit 1
    printf 'x\n' > docs/second.md
    git add docs/second.md
    git commit -qm "add second md" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
OUT="$(run_vpr "$TRUE_TRACKED_BODY")"
RC=$?
assert_eq "0" "$RC" "a correct tracked-file count does not miss"

echo
echo "=== Fixture 6: .loom/docs symlinks (#8656) ==="
# Since #7842 every `.loom/docs/*.md` with a `defaults/docs/` counterpart is a
# SYMLINK on origin/main (tree mode 120000, target relative to the link's own
# directory). Reading such a path with `git show <rev>:<path> | wc -l` — what
# this script did before #8656 — measures the LINK-TARGET STRING, so every
# in-range citation under `.loom/docs/` was reported as a miss and the script
# BLOCKS FILING on it. This fixture reproduces that exact tree shape.
(
    cd "$FIXTURE_REPO" || exit 1
    mkdir -p defaults/docs .loom/docs
    seq 1 300 > defaults/docs/longdoc.md            # 300 lines, the real document
    ln -sf ../../defaults/docs/longdoc.md .loom/docs/longdoc.md
    ln -sf ../../defaults/docs/gone.md .loom/docs/dangling.md   # points at nothing
    git add -A
    git commit -qm "symlinked installed docs" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
# Guard the fixture itself: if these stop being 120000 entries the three cases
# below would pass for the wrong reason.
assert_eq "120000" \
    "$(git -C "$FIXTURE_REPO" ls-tree origin/main .loom/docs/longdoc.md | awk '{print $1}')" \
    "fixture: .loom/docs/longdoc.md is a symlink tree entry, as on real origin/main"

IN_RANGE_BODY="$BODY_DIR/symlink-in-range.md"
cat > "$IN_RANGE_BODY" <<'EOF'
See `.loom/docs/longdoc.md:100-200` — an in-range span of a 300-line document
reached through its installed symlink path.
EOF
OUT="$(run_vpr "$IN_RANGE_BODY")"
RC=$?
assert_eq "0" "$RC" "an in-range span under .loom/docs/ exits 0 (the symlink is followed)"
assert_contains "$OUT" "all references check out" "the in-range symlink citation is not reported as a miss"

OUT_OF_RANGE_BODY="$BODY_DIR/symlink-out-of-range.md"
cat > "$OUT_OF_RANGE_BODY" <<'EOF'
See `.loom/docs/longdoc.md:250-9999` — genuinely past the end of the document.
EOF
OUT="$(run_vpr "$OUT_OF_RANGE_BODY")"
RC=$?
assert_eq "1" "$RC" "a genuinely out-of-range span under .loom/docs/ still misses"
assert_contains "$OUT" "BAD LINE RANGE" "the out-of-range symlink citation is labeled"
assert_contains "$OUT" ".loom/docs/longdoc.md:250-9999" "the citation is quoted as the body wrote it"
assert_contains "$OUT" "defaults/docs/longdoc.md" "the message names the RESOLVED path, not the link"
assert_contains "$OUT" "has only 300 lines" "the message reports the resolved document's real line count"

DANGLING_BODY="$BODY_DIR/symlink-dangling.md"
cat > "$DANGLING_BODY" <<'EOF'
See `.loom/docs/dangling.md:1-5` — the link exists in the tree but its target
does not.
EOF
OUT="$(run_vpr "$DANGLING_BODY")"
RC=$?
assert_eq "0" "$RC" "a dangling symlink does not block filing — unreadable is inconclusive, not a disproof"
assert_contains "$OUT" "BROKEN SYMLINK" "a dangling symlink is reported as unreadable"
if [[ "$OUT" == *"has only 0 lines"* ]]; then
    TESTS_RUN=$((TESTS_RUN + 1)); TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "  ${RED}FAIL${NC}: a dangling symlink must NOT be reported as a 0-line file"
else
    TESTS_RUN=$((TESTS_RUN + 1)); TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "  ${GREEN}PASS${NC}: a dangling symlink is never reported as a 0-line file"
fi

echo
echo "=== Fixture 7: generated-output declarations (#15387) ==="
# The `make verify-fast` target passes the gitignored output path
# build/verification/verify-fast.json to `--json` in the tracked Makefile.
# Citing the report in a test plan was a plain MISSING FILE miss that a
# Champion had to hand-verify against the recipe. An inline declaration
# "(generated by `Makefile:5')" hands the miss decision to
# `loom-daemon verify-output-decl`, which reads the CITED line of the TRACKED
# producer from origin/main — never the working tree, and never the locally
# generated report. The declaration must sit on one line, immediately after
# the citation it annotates.
(
    cd "$FIXTURE_REPO" || exit 1
    mkdir -p build/verification          # working-tree only; gitignored
    printf 'build/\n' > .gitignore
    cat > Makefile <<'MF'
all:
	@echo hi

verify-fast:
	@$(RUN) --timeout 600 --json build/verification/verify-fast.json \
	  "$(PY) -m pytest -q"
	tool --json artifacts/report.json --summary summary.json
	tool --json build/report.json+debug
	tool --json build/report.json$(SUFFIX)
	@# tool --json build/report.json
	-# tool --json build/report.json
	+# tool --json build/report.json
	@(tool --json build/report.json)
	@(tool --json "build/report.json")
inline-at: ; @# tool --json build/report.json
inline-dash: ; -# tool --json build/report.json
inline-plus: ; +# tool --json build/report.json
inline-command: ; @tool --json build/report.json
build/report.json: dep
	@tool --json $@
build/report.json.bak: dep
	@tool --json $@
copy:
	@cp seed \
    build/report.json:backup
include tools/report.rules
MF
    mkdir -p 'tools"reports'
    for producer in 'tools/build reports.sh' 'tools/report+rules.mk' 'tools/a:b.mk' 'tools"reports/rules.mk' '-rules.mk'; do
        printf 'tool --json build/report.json\n' > "$producer"
    done
    printf 'tool --json build/report.json' > tools/last.sh
    printf '#!/bin/sh\ncp seed build/report.json:backup\n' > tools/copy
    printf 'cp seed build/report.json:backup\n' > tools/copy.sh
    for producer in tools/copy-upper.SH tools/copy-mixed.Sh; do
        printf 'cp seed build/report.json:backup\ncp seed build/report.json\n' > "$producer"
    done
    printf 'other build/report.json: seed\n\t@cp seed $@\n' > tools/report.rules
    ln -s ../Makefile tools/in-tree.mk
    ln -s ../Makefile above-tree.mk
    ln -s /Makefile absolute.mk
    ln -s /Makefile tools/absolute.mk
    # This decoy would satisfy a nested absolute link resolved as relative.
    cp Makefile tools/Makefile
    git add -- Makefile .gitignore tools 'tools"reports' -rules.mk above-tree.mk absolute.mk
    git commit -qm "add verify-fast recipe" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
# Line 5 of that Makefile is the recipe line naming the report.

DECL_OK_BODY="$BODY_DIR/decl-ok.md"
cat > "$DECL_OK_BODY" <<'EOF'
Record timings from `build/verification/verify-fast.json` (generated by `Makefile:5`) after running make verify-fast.
EOF
OUT="$(run_vpr "$DECL_OK_BODY")"
RC=$?
assert_eq "0" "$RC" "a valid generated-output declaration exits 0"
assert_contains "$OUT" "all references check out" "the declared absent report is not reported as a miss"

DECL_TYPO_BODY="$BODY_DIR/decl-typo.md"
cat > "$DECL_TYPO_BODY" <<'EOF'
Record timings from `build/verification/verify-fast.jso` (generated by `Makefile:5`) after running make verify-fast.
EOF
OUT="$(run_vpr "$DECL_TYPO_BODY")"
RC=$?
assert_eq "1" "$RC" "a misspelled output path (prefix of the real filename) with a declaration exits 1"
assert_contains "$OUT" "BAD OUTPUT DECL" "the failed declaration is labeled"
assert_contains "$OUT" "build/verification/verify-fast.jso" "the misspelled citation is named"

# An older daemon reports an unknown subcommand with clap's usage exit code.
OLD_DAEMON="$FIXTURE_ROOT/old-daemon"
cat > "$OLD_DAEMON" <<'EOF'
#!/usr/bin/env bash
echo "error: unrecognized subcommand '$1'" >&2
exit 2
EOF
chmod +x "$OLD_DAEMON"
OUT="$(LOOM_DAEMON_SELF_BIN="$OLD_DAEMON" run_vpr "$DECL_TYPO_BODY")"
RC=$?
assert_eq "0" "$RC" "a daemon without verify-output-decl leaves the declaration inconclusive"
assert_contains "$OUT" "unrecognized subcommand 'verify-output-decl'" "the unavailable check is visible"

DECL_NOPROD_BODY="$BODY_DIR/decl-noprod.md"
cat > "$DECL_NOPROD_BODY" <<'EOF'
Record timings from `build/verification/verify-fast.json` (generated by `Recipe.md:5`) after running make verify-fast.
EOF
OUT="$(run_vpr "$DECL_NOPROD_BODY")"
RC=$?
assert_eq "1" "$RC" "a declaration naming a missing producer exits 1"
assert_contains "$OUT" "BAD OUTPUT DECL" "the failed declaration is labeled"
assert_contains "$OUT" "Recipe.md" "the missing producer is named"

DECL_WRONGLINE_BODY="$BODY_DIR/decl-wrongline.md"
cat > "$DECL_WRONGLINE_BODY" <<'EOF'
Record timings from `build/verification/verify-fast.json` (generated by `Makefile:2`) after running make verify-fast.
EOF
OUT="$(run_vpr "$DECL_WRONGLINE_BODY")"
RC=$?
assert_eq "1" "$RC" "a producer line that lacks the output exits 1"
assert_contains "$OUT" "BAD OUTPUT DECL" "the failed declaration is labeled"
assert_contains "$OUT" "Makefile:2" "the failing producer line is named"

DECL_MIXED_BODY="$BODY_DIR/decl-mixed.md"
cat > "$DECL_MIXED_BODY" <<'EOF'
Record `build/verification/verify-fast.json` (generated by `Makefile:5`), then see `src/nope.py` for the helper.
EOF
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "1" "$RC" "a missing source beside a valid declaration still exits 1"
assert_contains "$OUT" "MISSING FILE" "the unannotated missing source is still labeled"
assert_contains "$OUT" "src/nope.py" "the missing source is named"
assert_not_contains "$OUT" "BAD OUTPUT DECL" "the valid declaration is not itself a miss"

# Each citation owns its annotation, even on the same line as another
# citation of the same output.
REPORT='`build/verification/verify-fast.json`'
VALID="$REPORT (generated by \`Makefile:5\`)"
INVALID="$REPORT (generated by \`Makefile:2\`)"
for pair in "$VALID and $INVALID" "$INVALID and $VALID"; do
    printf '%s\n' "$pair" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "repeated declarations with one bad producer line exit 1"
    assert_contains "$OUT" "Makefile:2" "the incorrect citation is diagnosed in either order"
done

for pair in "$VALID and $REPORT" "$REPORT and $VALID"; do
    printf '%s\n' "$pair" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "an unannotated occurrence beside a declaration exits 1"
    assert_contains "$OUT" "MISSING FILE: $REPORT" "the unannotated occurrence is diagnosed in either order"
done

for producer_line in 8 9; do
    printf '`build/report.json` (generated by `Makefile:%s`)\n' "$producer_line" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "a recipe extending the filename on line $producer_line exits 1"
    assert_contains "$OUT" "BAD OUTPUT DECL" "the prefix is reported as a failed declaration"
done

for producer_line in 10 11 12 15 16 17; do
    printf '`build/report.json` (generated by `Makefile:%s`)\n' "$producer_line" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "a commented recipe on line $producer_line cannot declare the output"
    assert_contains "$OUT" "BAD OUTPUT DECL" "the commented recipe is diagnosed"
done

for producer_line in 13 14 18; do
    printf '`build/report.json` (generated by `Makefile:%s`)\n' "$producer_line" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "0" "$RC" "the command on line $producer_line declares the output"
    assert_contains "$OUT" "checked 1 path ref" "the command's declaration was checked"
done

printf '%s\n' '`src/foo.py` (generated by `docs/bar.md:99`)' > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "1" "$RC" "a nested producer still gets its range checked on a tracked output"
assert_contains "$OUT" "BAD LINE RANGE" "the existing producer range check is preserved"

# Read the entire backticked producer. The final colon introduces its line.
for producer in 'tools/build reports.sh' 'tools/report+rules.mk' 'tools/a:b.mk' '-rules.mk' 'tools/last.sh'; do
    printf '`build/report.json` (generated by `%s:1`)\n' "$producer" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "0" "$RC" "valid declaration from $producer exits 0"
    assert_contains "$OUT" "checked 1 path ref" "the declaration from $producer is checked once"
done

for producer in 'Missing Rules.mk' '-missing.mk'; do
    printf '`report.jso` (generated by `%s:1`)\n' "$producer" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "missing quoted producer $producer exits 1"
    assert_contains "$OUT" "producer \`$producer\` does not exist" "the complete missing filename is diagnosed"
done

for producer in '../Missing.mk' '/Missing.mk' 'missing-dir/../Makefile'; do
    printf '%s (generated by `%s:5`)\n' "$REPORT" "$producer" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "a producer absent at the cited path $producer exits 1"
    assert_contains "$OUT" "BAD OUTPUT DECL" "the declaration is disproved"
    assert_contains "$OUT" "producer \`$producer\` does not exist" "the cited producer path is named"
done

# On a tracked output the ordinary producer range check must use its literal
# filename, even when Git quotes that name in a tree listing.
printf '%s\n' '`src/foo.py` (generated by `tools"reports/rules.mk:2`)' > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "1" "$RC" "a tracked output retains the quoted producer range check"
assert_contains "$OUT" 'BAD LINE RANGE: `tools"reports/rules.mk:2`' "the full filename is range-checked"

# With the optional command unavailable, an independently missing nested
# producer remains an ordinary missing reference.
printf '%s\n' '`report.jso` (generated by `tools/missing recipe.mk:1`)' > "$DECL_MIXED_BODY"
OUT="$(LOOM_DAEMON_SELF_BIN="$OLD_DAEMON" run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "1" "$RC" "an unavailable declaration check keeps the ordinary producer check"
assert_contains "$OUT" 'MISSING FILE: `tools/missing recipe.mk`' "the unchecked producer is named"

# An ordinary citation beside a declaration has its own range check. Line 1 of
# tools/last.sh is real but has no newline after it (#15467): the declaration
# above reads it, and the ordinary citation to it must pass as well.
printf '%s\n' '`build/report.json` (generated by `tools/last.sh:1`), see `tools/last.sh:1`.' > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "0" "$RC" "the ordinary citation to an unterminated final line beside a declaration exits 0"
assert_contains "$OUT" "all references check out" "an unterminated final line beside a declaration is not a miss"
assert_contains "$OUT" "checked 2 path ref" "both the declaration and the ordinary citation were checked"

# One line past it is still an ordinary range miss beside a valid declaration.
printf '%s\n' '`build/report.json` (generated by `tools/last.sh:1`), see `tools/last.sh:2`.' > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "1" "$RC" "the ordinary citation one past an unterminated final line beside a declaration exits 1"
assert_contains "$OUT" "1 miss(es)" "only the ordinary citation fails"
assert_contains "$OUT" "BAD LINE RANGE: \`tools/last.sh:2\`" "the out-of-range ordinary citation is named"
assert_contains "$OUT" "has only 1 lines" "the diagnostic counts the unterminated final line"

# The declaration's own diagnostic counts the unterminated final line too
# (#15471): tools/last.sh has one line, not zero.
OUT="$("$LOOM_DAEMON_SELF_BIN" verify-output-decl --workspace "$FIXTURE_REPO" --producer=tools/last.sh:2 build/report.json 2>&1)"
RC=$?
assert_eq "1" "$RC" "a declaration citing one line past an unterminated final line exits 1"
assert_contains "$OUT" "has only 1 lines, no line 2" "the declaration diagnostic counts the unterminated final line"

for producer in above-tree.mk absolute.mk tools/absolute.mk; do
    OUT="$("$LOOM_DAEMON_SELF_BIN" verify-output-decl --workspace "$FIXTURE_REPO" --producer="$producer:5" build/verification/verify-fast.json 2>&1)"
    RC=$?
    assert_eq "10" "$RC" "out-of-tree producer link $producer is inconclusive"
    assert_contains "$OUT" "UNREADABLE PRODUCER" "the link $producer is reported as unreadable"
done

printf '%s\n' "$REPORT (generated by \`tools/in-tree.mk:5\`)" > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "0" "$RC" "a producer link within the pinned tree still verifies"
assert_not_contains "$OUT" "UNREADABLE" "the relative link resolved to the tracked producer"

# Explicit outputs can be at the root or under an entirely untracked directory.
for output in artifacts/report.json summary.json; do
    printf '`%s` (generated by `Makefile:7`)\n' "$output" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "0" "$RC" "valid declaration of $output exits 0"
    assert_contains "$OUT" "checked 1 path ref" "the explicit declaration of $output was checked"

    printf '`%s` (generated by `Makefile:7`)\n' "${output%.json}.jso" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "a misspelled $output exits 1"
    assert_contains "$OUT" "BAD OUTPUT DECL" "the misspelling is reported as a failed declaration"

    printf '`%s` (generated by `Missing:1`)\n' "$output" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "a missing producer for $output exits 1"
    assert_contains "$OUT" "Missing" "the absent producer is identified"
done

# A Make rule's target line is the canonical declaration of a generated file
# (#15466): an idiomatic recipe names its output only as `$@`, so the target
# is the one line that spells the path out. The rule is cited by its target
# line (19); its `$@` recipe line (20) and a target that merely extends the
# name (21) declare nothing.
printf '`build/report.json` (generated by `Makefile:19`)\n' > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "0" "$RC" "a Make target line declares the output"
assert_contains "$OUT" "checked 1 path ref" "the target-line declaration was checked"

printf '`build/report.json` (generated by `tools/report.rules:1`)\n' > "$DECL_MIXED_BODY"
OUT="$(run_vpr "$DECL_MIXED_BODY")"
RC=$?
assert_eq "0" "$RC" "a target in an included Make fragment with an arbitrary name declares the output"
assert_contains "$OUT" "checked 1 path ref" "the included target-line declaration was checked"

# Line 25 continues the tab-prefixed recipe. In both shell producers and
# this continuation, the colon is part of the destination argument.
for producer in Makefile:20 Makefile:21 Makefile:25 tools/copy:2 tools/copy.sh:1; do
    printf '`build/report.json` (generated by `%s`)\n' "$producer" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "$producer cannot declare the output"
    assert_contains "$OUT" "BAD OUTPUT DECL" "the citation of $producer is diagnosed"
    assert_contains "$OUT" "$producer" "the failing producer line is named"
done

# The shell suffix is matched ASCII case-insensitively (#15500): a producer
# with an upper-case or mixed-case shell suffix is a script like `copy.sh`,
# so the colon-extended destination on its line 1 declares nothing. Line 2 of
# the same producer is a complete argument and verifies, so line 1 failed on
# its content, not because the producer was missing.
for producer in tools/copy-upper.SH tools/copy-mixed.Sh; do
    printf '`build/report.json` (generated by `%s:1`)\n' "$producer" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "1" "$RC" "$producer:1 cannot declare the output"
    assert_contains "$OUT" "BAD OUTPUT DECL" "the citation of $producer:1 is diagnosed"
    assert_contains "$OUT" "does not name \`build/report.json\` as a complete argument" "the cited line, not the producer, is disproved"

    printf '`build/report.json` (generated by `%s:2`)\n' "$producer" > "$DECL_MIXED_BODY"
    OUT="$(run_vpr "$DECL_MIXED_BODY")"
    RC=$?
    assert_eq "0" "$RC" "$producer:2 declares the output"
    assert_contains "$OUT" "checked 1 path ref" "the declaration from $producer:2 is checked once"
done

# A local edit and a locally generated report cannot satisfy the declaration:
# the producer is read from the PINNED origin/main tree. Edit the working-tree
# Makefile to name the misspelled output and create that report locally —
# the same citation must still fail.
(
    cd "$FIXTURE_REPO" || exit 1
    sed -i 's/verify-fast\.json/verify-fast.jso/' Makefile
    printf '{}\n' > build/verification/verify-fast.jso
)
OUT="$(run_vpr "$DECL_TYPO_BODY")"
RC=$?
assert_eq "1" "$RC" "a working-tree edit naming the misspelled output still fails"
assert_contains "$OUT" "BAD OUTPUT DECL" "the declaration still fails against the pinned tree"
assert_contains "$OUT" "build/verification/verify-fast.jso" "the misspelled citation is still named"
(
    cd "$FIXTURE_REPO" || exit 1
    git checkout -- Makefile
    rm -f build/verification/verify-fast.jso
)

echo
echo "=== Fixture 8: unterminated final line (#15467) ==="
# The range check used the `wc -l` count as its upper bound, so a citation to
# a tracked file's final line was refused whenever that line had no newline
# after it -- "has only 0 lines" for a one-line file -- on a script that
# BLOCKS FILING. That line, and a span ending on it, are real; only report
# mode keeps the `wc -l` count.
(
    cd "$FIXTURE_REPO" || exit 1
    printf 'first\nlast' > docs/unterminated.md
    : > docs/empty.md
    printf '\n' > docs/blank.md
    git add docs
    git commit -qm "unterminated final-line fixtures" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
# Guard the fixture itself: `first\nlast` is 10 bytes only with no newline.
assert_eq "10" "$(git -C "$FIXTURE_REPO" cat-file -s origin/main:docs/unterminated.md)" \
    "fixture: docs/unterminated.md has no trailing newline"

UNTERMINATED_BODY="$BODY_DIR/unterminated.md"
cat > "$UNTERMINATED_BODY" <<'EOF'
See `tools/last.sh:1`, `docs/unterminated.md:2` and `docs/unterminated.md:1-2`
as evidence.
EOF
OUT="$(run_vpr "$UNTERMINATED_BODY")"
RC=$?
assert_eq "0" "$RC" "a final line with no newline after it is citable, alone and as the end of a span"
assert_contains "$OUT" "all references check out" "citations to an unterminated final line are not misses"

PAST_EOF_BODY="$BODY_DIR/past-eof.md"
cat > "$PAST_EOF_BODY" <<'EOF'
See `docs/unterminated.md:3` — one line past the unterminated final line.
EOF
OUT="$(run_vpr "$PAST_EOF_BODY")"
RC=$?
assert_eq "1" "$RC" "one line past an unterminated final line exits 1"
assert_contains "$OUT" "BAD LINE RANGE: \`docs/unterminated.md:3\`" "the out-of-range citation is named"
assert_contains "$OUT" "has only 2 lines" "the diagnostic counts the unterminated final line"

# An empty file has no citable line; a blank line is one, and a trailing
# newline adds none.
for cite in 'docs/empty.md:1' 'docs/blank.md:2'; do
    printf 'See `%s`.\n' "$cite" > "$BODY_DIR/edge.md"
    OUT="$(run_vpr "$BODY_DIR/edge.md")"
    RC=$?
    assert_eq "1" "$RC" "$cite is past the end of the file"
    assert_contains "$OUT" "BAD LINE RANGE: \`$cite\`" "$cite is labeled"
done
printf 'See `docs/blank.md:1`.\n' > "$BODY_DIR/edge.md"
OUT="$(run_vpr "$BODY_DIR/edge.md")"
RC=$?
assert_eq "0" "$RC" "a blank line is citable"

# Report mode keeps the `wc -l` count and its tab-separated output.
assert_eq "$(printf 'docs/unterminated.md\t1')" \
    "$("$LOOM_DAEMON_SELF_BIN" git-blob-lines docs/unterminated.md --rev origin/main --workspace "$FIXTURE_REPO")" \
    "report mode counts newline bytes, not the unterminated final line"
assert_eq "$(printf 'tools/last.sh\t0')" \
    "$("$LOOM_DAEMON_SELF_BIN" git-blob-lines tools/last.sh --rev origin/main --workspace "$FIXTURE_REPO")" \
    "report mode reports 0 for a one-line file that has no newline"

echo
echo "=== Usage / prerequisite errors ==="
OUT="$("$VPR" 2>&1)"
RC=$?
assert_eq "2" "$RC" "no body-file argument exits 2"

OUT="$(LOOM_WORKSPACE="$FIXTURE_REPO" "$VPR" "$BODY_DIR/does-not-exist.md" 2>&1)"
RC=$?
assert_eq "2" "$RC" "nonexistent body-file exits 2"

NOT_A_REPO="$(mktemp -d)"
OUT="$(LOOM_WORKSPACE="$NOT_A_REPO" "$VPR" "$CLEAN_BODY" 2>&1)"
RC=$?
assert_eq "2" "$RC" "workspace that is not a git repo exits 2"
rm -rf "$NOT_A_REPO"

echo
echo "--- Workspace rooting (#7658 Ask item 4): never a sibling checkout ---"
# A second, unrelated fixture repo (the "sibling checkout") that DOES contain
# the path the body cites. Pointing LOOM_WORKSPACE at the FIRST repo (which
# does not have it) must still miss — proving the script checks the
# dispatched workspace, not any path-matching sibling it could have found.
SIBLING_REPO="$FIXTURE_ROOT/sibling"
mkdir -p "$SIBLING_REPO/verification"
(
    cd "$SIBLING_REPO" || exit 1
    git init -q -b main .
    git config user.email "test@example.com"
    git config user.name "Test"
    echo "x" > verification/_repo_utils.py
    git add .
    git commit -qm "init" >/dev/null
    git update-ref refs/remotes/origin/main refs/heads/main
)
SIBLING_BODY="$BODY_DIR/sibling.md"
cat > "$SIBLING_BODY" <<'EOF'
See `verification/_repo_utils.py` for the shared helper.
EOF
OUT="$(run_vpr "$SIBLING_BODY")"
RC=$?
assert_eq "1" "$RC" "a path that only exists in a sibling checkout still misses against the real workspace"
assert_contains "$OUT" "verification/_repo_utils.py" "the sibling-only path is named as a miss"

echo
echo "--- Doc pins: Hermit / Architect / Champion wiring ---"
assert_doc_contains "$HERMIT_MD" "verify-proposal-refs.sh" \
    "hermit.md's pre-file step invokes the verifier"
assert_doc_contains "$HERMIT_MD" "Any miss blocks filing" \
    "hermit.md states the blocks-filing rule"
assert_doc_contains "$HERMIT_MD" "not present in this repo" \
    "hermit.md gives the 'not present in this repo' rewrite escape hatch"
assert_doc_contains "$ARCHITECT_MD" "verify-proposal-refs.sh" \
    "architect.md's pre-file step invokes the verifier"
assert_doc_contains "$ARCHITECT_MD" "Any miss blocks filing" \
    "architect.md states the blocks-filing rule"
assert_doc_contains "$ARCHITECT_MD" "not present in this repo" \
    "architect.md gives the 'not present in this repo' rewrite escape hatch"
assert_doc_contains "$CHAMPION_PROMO_MD" "verify-proposal-refs.sh" \
    "champion-issue-promo.md's criteria cite the verifier"

echo
echo "Results: $TESTS_PASSED/$TESTS_RUN passed, $TESTS_FAILED failed"
[[ $TESTS_FAILED -eq 0 ]] || exit 1
