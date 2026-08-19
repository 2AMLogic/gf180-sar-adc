# DR-0022: `layout/` post-layout tooling pinned to `gf180mcuD`

- **Status**: ratified
- **Date**: 2026-08-19
- **Decided by**: Builder agent, issue #228
- **Supersedes**: none — first record for this decision
- **Superseded by**: (none while this record stands)
- **Related**: #228, `2AMLogic/2am#350` (cross-repo fleet audit),
  `2AMLogic/gf180-tmds-tx#9` DR-0006 (fleet-wide precedent, amended
  2026-08-19), `sim/harness/pdk.py` (`DEFAULT_VARIANT = "gf180mcuD"`),
  `layout/adc-top/parasitics/run_pex_comparator.py` (in-repo reference
  implementation), DR-0004 (device flavor — cites gf180mcuD's installed
  model file directly)

## Context

`layout/adc-top/parasitics/run_extract_parasitics.py`'s `resolve_pdk()`
called `klt pdk find` with no `--pdk` argument at all, so it resolved
whichever `gf180mcu*` variant `klt` happened to find on the host running
it — not a fixed, ratified variant. On failure it returned `None` rather
than raising, letting extraction silently degrade to bare `M ... nfet`
device-class cards instead of failing the run.

This was observed live, on two different hosts, resolving the **wrong**
variant both times: `--pdk gf180mcuA --pdk-root /home/ubuntu/.ciel` in
`layout/adc-top/parasitics/records/20260817-204449-076d545.md`, and
`--pdk gf180mcuA --pdk-root /home/ubuntu/.volare` in
`records/20260806-140411-968d138.md` — variant **A**, never C or D, on
either host. Meanwhile `sim/harness/pdk.py`'s `DEFAULT_VARIANT` is
`gf180mcuD`, and every audited `sim/*/records/*.md` file in this repo
already cites `gf180mcuD` — so the SPICE-level simulation evidence in this
repo was already correctly aligned with the fleet ruling; only the
post-layout parasitics extraction path was unpinned and drifting.

This is a variant of the pattern `gf180-tmds-tx#9`'s Defect 1 first
surfaced (spec/sim evidence citing one PDK variant, layout evidence citing
another) — filed here by the same cross-repo audit
(`2AMLogic/2am#350`) that generalized that defect as a systemic fleet risk.
Unlike that defect, the layout-side citation here was not even a fixed
second variant: it silently tracked whatever the invoking host had
installed, which is worse — non-deterministic across hosts, not just
inconsistent between two fixed points.

A working reference implementation already existed in the same directory:
`run_pex_comparator.py`'s `resolve_pdk()` (module constant
`PDK_VARIANT = "gf180mcuD"`, `klt pdk find --pdk gf180mcuD --format json`,
raises `ToolingError` on failure) — this record ratifies that pattern as
the rule for this repo's `layout/` tree, not just documents one script's
fix.

## Decision

**Pin `gf180mcuD` as the required PDK variant for every `klt`-driven
resolver under `layout/`** — matching `sim/harness/pdk.py`'s
`DEFAULT_VARIANT` and the fleet-wide ruling in `gf180-tmds-tx#9` DR-0006.

Concretely: any `layout/` script that resolves a PDK install via
`klt pdk find` must pass `--pdk gf180mcuD` explicitly (never a
bare/unpinned `klt pdk find` that accepts whatever variant the host
happens to have), and must raise a tooling error — not silently degrade
or return `None` — when `gf180mcuD` fails to resolve. This repo's evidence
records under `layout/` (extraction summaries, LVS/DRC reports) are
therefore only ever minted against `gf180mcuD`; a record citing any other
variant is stale by definition and must not be treated as current
evidence.

This record ratifies the pattern `run_pex_comparator.py` already
implemented as the standing rule for this directory, and requires
`run_extract_parasitics.py` (issue #228) and any future `layout/` PDK
resolver to match it.

## Alternatives considered

- **Accept whatever variant `klt pdk find` returns (status quo)** — not
  chosen: non-deterministic across hosts by construction, already observed
  resolving a variant (A) that matches neither the fleet ruling (D) nor
  any other fixed convention. Evidence minted this way cannot be trusted to
  reproduce the same numbers on a different host, which directly
  contradicts CLAUDE.md's "provenance travels with every number."
- **Pin `layout/` to a different fixed variant than `sim/` (e.g. C, to
  match some other fleet canary)** — not chosen: this repo's own
  `sim/harness/pdk.py` and every audited `sim/` evidence record already
  cite `gf180mcuD`; pinning `layout/` to a different variant would
  reintroduce exactly the spec/sim-vs-layout mismatch `gf180-tmds-tx#9`
  Defect 1 first surfaced, just moved one level down.
- **Silently fall back to a bare, unbound extraction (`M ... nfet` cards)
  when `gf180mcuD` is unavailable, rather than failing loudly** — not
  chosen: this is the exact silent-degrade behavior this record closes.
  `run_pex_comparator.py` already established that a missing PDK should
  fail the run with a clear remediation message, not mint evidence against
  an unbound or wrong-variant PDK.

## Consequences

- Every `layout/` PDK resolver now fails loudly (raises) instead of
  degrading silently when `gf180mcuD` is not installed — a caller without
  a D install can no longer get a "valid but PDK-unbound" extraction; they
  must install `gf180mcuD` (via volare or ciel) or the run fails with a
  remediation message pointing at that.
- Evidence records under `layout/adc-top/parasitics/records/` (and any
  future `layout/` evidence directory using the same pattern) are now
  reproducible across hosts: any host with `gf180mcuD` installed resolves
  the identical variant, not whatever the host happens to have.
- **Bad consequence, stated plainly**: this is strictly less forgiving for
  a contributor whose host only has a non-D variant installed (e.g. a CI
  runner provisioned with only `gf180mcuA`) — their runs now fail instead
  of producing a degraded-but-valid result. That tradeoff is deliberate:
  a "valid" extraction against the wrong variant is worse than a loud
  failure, because it can be committed as evidence without anyone
  noticing the mismatch (as already happened twice — the two superseded
  gf180mcuA records this issue's evidence cites).
- The two pre-existing records citing `gf180mcuA`
  (`records/20260806-140411-968d138.md`,
  `records/20260817-204449-076d545.md`) remain in place, unedited, per
  this repo's append-only evidence rule (`sim/README.md`) — they are
  superseded in effect by the fresh `gf180mcuD` record #228's fix mints,
  not edited or annotated in place. A reader comparing record dates and
  PDK-binding fields can tell which is current without any record needing
  to be rewritten.

## Spec lines affected

- None — this is a tooling/process decision (PDK variant pinning for
  layout evidence generation), not a change to any `spec/adc.md` target
  parameter or row.
