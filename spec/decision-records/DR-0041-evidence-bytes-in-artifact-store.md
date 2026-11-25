# DR-0041: new run evidence goes to the fleet artifact store; git keeps a manifest and the record

- **Status**: proposed — for operator ratification. Nothing below relaxes a
  spec limit or touches existing evidence; it changes where the bytes of
  *new* runs live and what a record's **Links** point at.
- **Date**: 2026-10-23
- **Decided by**: Builder agent, issue #636 (fleet adoption of
  2AMLogic/2am#5553; operator rulings H1 and 1.1 recorded there)
- **Supersedes**: none — first record for this decision. It narrows, going
  forward only, the "raw per-corner logs are tracked evidence" premise that
  DR-0039 (proposed) sets out to manage by compression.
- **Superseded by**: (none while this record stands)
- **Related**: #636, DR-0039, `sim/README.md` ("Stored evidence", "Append-only
  rule"), `scripts/check_artifact_manifests.py`,
  `sim/harness/evidence_store.py`, `sim/run_store_evidence.py`, klayout-tools
  `docs/cli/artifact.md`, reference implementation
  2AMLogic/sg13g2-comparator#319 and #321

## Context

`sim/` and the layout/signoff evidence trees hold about 803 MB of committed
run output (`sim/dr0014-sampling/` 354 MB, `sim/adc-inl-dnl/` 102 MB,
`layout/adc-top/` 67 MB, `layout/power/` 62 MB, `sim/adc-power/` 50 MB,
measured with `du` on `a9190e8e`). `.gitignore` deliberately re-admitted
`sim/*/corners/*/*.log` so a record's "Raw logs" link resolves, so every new
campaign grew a public repository permanently. The fleet now has a common
artifact store reached through a broker (`$KLT_ARTIFACT_BROKER`,
`klt artifact put|get|verify`). Evidence bytes there are private; a manifest
naming each object by sha256 is public and safe to commit.

## Decision

From this record on, the bytes of a **new** evidence-writing run are stored with
`klt artifact put`, not committed. Git keeps exactly two things per run:

1. `manifests/artifacts/<bench>-<run-id>.manifest.json` — one entry per stored
   object (`sha256`, `size`, `kind: evidence`, `producer`, a logical
   `artifact:<key>` `uri`, and the repo path the bytes would have had as
   `name`). No bucket, account or broker URL appears in it.
2. The run's Markdown record, with a "Stored evidence" table (name, size,
   sha256 per object) appended. Its **Raw logs** and **Netlist snapshot**
   links name the manifest instead of a directory.

The writer **fails closed**: with `$KLT_ARTIFACT_BROKER` unset, a `klt` that
lacks `artifact put` or predates klayout-tools `7e3561f`, or an unreachable or
refusing broker, `sim/run_corners.py` exits 10 *before simulating* and
`sim/run_store_evidence.py` exits 10 before touching the repo. There is no
flag that commits the bytes instead. `--no-write` runs need no store.

CI (`scripts/check_artifact_manifests.py check`, stdlib only) validates every
manifest's schema, accepts only `artifact:` URIs, fails if a stored object's
bytes (same sha256) are also committed under any name, and fails if a PR adds
new raw per-corner output under `sim/*/corners/`. Manifests are append-only
(`sim/tools/check_append_only_records.py`). `.gitignore` no longer re-admits
corner logs.

**Manifest-forward only.** Already-committed evidence stays where it is;
history is not rewritten.

## Alternatives considered

- **Keep committing bytes, compress them (DR-0039)** — still grows a public
  repository without bound and every CI/agent checkout pays for it; it
  manages the growth instead of stopping it. Not exclusive of this record for
  the existing 803 MB, which is out of scope here.
- **A fallback flag that commits bytes when the store is down** — silently
  reintroduces the growth and makes "stored" unverifiable from the record;
  rejected to keep the failure loud and the run re-runnable.
- **Rewrite history or migrate old evidence to the store** — breaks the
  append-only guarantee and every cited path/sha; explicitly out of scope.
- **Store evidence in a second git repo or LFS** — a second place to host
  and permission bytes the fleet already has a broker for.

## Consequences

- **Bad**: a record's raw logs can no longer be read from a plain clone. Only
  callers the broker admits (fleet workers) can `klt artifact get` them; an
  outside reader re-runs the cited command or checks the sha256s in the
  table. The manifest and table keep the claim checkable by hash.
- **Bad**: evidence-writing runs now depend on broker availability; an outage
  blocks new recorded runs (staged bytes are kept under `sim/.work/.stage/` and
  can be stored later with `run_store_evidence.py`; the id is not reused).
- **Bad**: `sim/selftest.sh --record` and other recorded runs need the broker.
- Good: no further growth of the committed evidence tree; record, manifest and
  sha256 table are small and reviewable.
- Layout/signoff runners with committed `--verify` freshness baselines
  (`layout/erc`, `layout/power`, `signoff`) keep their current outputs; only new
  campaign output uses `run_store_evidence.py --under <dir>`.
- Existing generators that write `sim/<bench>/corners/` directly (outside
  `run_corners.py`) are caught by the CI check on their next new run and must
  move to the store path.

## Spec lines affected

none — this is an evidence-handling and process decision; no
`README.md#target-specification` row or spec limit changes. It changes the
`sim/README.md` record shape (the **Raw logs** and **Netlist snapshot** links),
which that file documents.
