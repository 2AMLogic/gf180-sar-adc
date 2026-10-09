# DR-0039: retain raw per-corner logs as manifest-verified compressed archives once superseded, keeping append-only provable

- **Status**: proposed — for operator ratification. Nothing below is in force
  until the operator ratifies it; agents do not pre-empt it, and no existing
  evidence under `sim/` is touched by this record's PR.
- **Date**: 2026-10-09
- **Decided by**: Builder agent drafting for the operator, issue #476
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #476, [`sim/README.md`](../../sim/README.md) "Append-only
  rule", `.gitignore` (re-admits `!sim/*/corners/*/*.log`),
  [`sim/tools/check_append_only_records.py`](../../sim/tools/check_append_only_records.py),
  [`sim/tools/evidence_footprint.py`](../../sim/tools/evidence_footprint.py),
  open re-take issues #429, #430, #439, #460

## Context

Raw per-corner logs are deliberately tracked evidence, and every re-take of a
campaign adds a full new set. Nothing states what size is acceptable.
Measured with `python3 sim/tools/evidence_footprint.py --records` at commit
`e40a353e` (working-tree bytes of `git ls-files sim`):

- all tracked files under `sim/<experiment>/`: **491,075,333 B (468.3 MiB)**;
- of which `*.log`: **440,490,865 B in 5,237 files** (the issue's ~440 MB),
  and everything under `corners/`: 446,049,401 B across 164 record
  directories;
- largest experiments: `dr0014-sampling` 219.5 MB (44.7 %), `adc-inl-dnl`
  91.6 MB, `adc-power` 52.2 MB, `adc-enob-fft` 30.6 MB; the other 44 of 48 experiments are
  each under 12.3 MB;
- single largest records are 33–35 MB each (`dr0014-sampling`
  `20261007-072143-800bf53`, `20261007-071907-800bf53`,
  `20260923-104443-904af96`) — near-duplicate re-takes of the same grid;
- packed object store: 71.98 MiB (`git count-objects -vH`, `size-pack`), so
  git already compresses well but a working-tree checkout pays the full
  ~468 MiB, on every CI checkout and every agent worktree.

Compressibility (read-only experiment): gzip -6 of every 10th `*.log` in
`git ls-files` order (524 files, 43,736,807 B) gave 4,565,702 B, a ratio of
**0.104**. Extrapolated, the 440 MB of logs would be ~46 MB as `.gz`.
Reproduce: the footprint command above, plus `gzip.compress(data, 6)` over
`sorted(git ls-files sim)` filtered to `*.log`, slice `[::10]`.

## Decision

Proposed: **keep the logs, change their at-rest form, and keep the guard
mechanical.**

1. A corner log in a record that is *superseded* (named by a later record's
   `Supersedes:`) may be replaced by a single `corners/<record-id>.tar.gz`
   plus `corners/<record-id>.manifest.sha256` listing the SHA-256 and size of
   every original `*.log`. Records themselves (`records/*.md`) stay as-is and
   are never compressed.
2. `check_append_only_records.py` is extended (a separate issue) so that a
   change of the `corners/<id>/` directory to the archive form passes only
   when the manifest hashes match the files inside the archive **and** match
   the blob hashes of the logs at the merge base. Nothing can be altered under
   cover of compression.
3. The most recent record per experiment/claim keeps raw logs.
4. `sim/tools/evidence_footprint_budget.json` becomes the ratified ceiling;
   `--strict` is switched on in CI only after the conversion lands.

Conversion itself is a later, separately reviewed PR; this record only
chooses the approach.

## Alternatives considered

- **Do nothing; just keep measuring.** Zero risk, but growth is unbounded
  (each re-take adds ~35 MB for the largest grids, and four re-take issues
  are open); no limit is ever defined.
- **Delete superseded logs, keep records.** Largest saving, but destroys
  re-derivable evidence and breaks the public "check it yourself" promise.
- **Git LFS.** Moves bytes off the clone but needs LFS storage on a public
  repo, a host-side tool the workers do not have, and an outside reader can
  no longer verify with plain `git`. Reversal is also awkward.
- **History rewrite / shallow-history policy.** Does not shrink the working
  tree, and invalidates every commit hash cited in records.
- **Stop tracking logs (re-ignore).** Records cite logs as proof; a number
  with no log is a claim without provenance.
- **Compress in place with no manifest.** Smaller, but check:records could
  no longer tell compression from tampering.

## Consequences

- Expected saving about 90 % of superseded log bytes (gzip ratio 0.104 on
  the sample), bringing the working tree from ~468 MiB toward the order of
  100–150 MiB depending on how many records count as superseded; this
  estimate is from a 10 % sample and is not yet a measurement of the real
  conversion.
- Git history keeps the old blobs, so `.git` does not shrink (it may grow
  slightly: compressed archives do not delta against earlier logs).
- Reading an old log needs an extract step; links in records pointing to
  `corners/<id>/x.log` break unless rewritten, and records are immutable, so
  the markdown link check needs an allowlist or a stub convention. This is
  the main cost and needs the operator's view.
- The append-only checker gains complexity and must itself be negative-
  controlled.
- Archive determinism (tar ordering, gzip mtime) must be pinned so the
  conversion is reproducible.

## Spec lines affected

none — a repository-process decision about evidence storage; it changes no
ratified spec row. (It does amend the sim/README.md "Append-only rule"
procedure if ratified, in the implementing PR.)
