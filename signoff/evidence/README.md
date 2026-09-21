# `signoff/evidence/` — the only evidence this repo writes *for* the grader

Every other citation in
[`../gf180-sar-adc.manifest.json`](../gf180-sar-adc.manifest.json) points at
a JSON envelope some `klt` verb produced as a by-product of doing real work:
a DRC run, an LVS compare, a Monte-Carlo yield report, a `klt pex` attempt.
Those files live where their own flow records them (`layout/`, `sim/`,
`design/sar-logic/flow/`), and `signoff/` only cites them.

**This directory is the one exception, and it exists for exactly one T1
item.** T1 item 8 ("Characterization report") is the only checklist item that
names no `klt` verb — there is no command whose own JSON output could satisfy
it structurally, because what it asks for is a *hand-assembled aggregation*.
`klt signoff` ingests that through an opt-in **generic evidence envelope**
(`"kind": "generic"`, klayout-tools#1152): a small JSON wrapper a project
writes itself, asserting `status: "pass"|"fail"` over whatever record backs
it. Item 8 is the **only** item that accepts one — a `generic` citation for
any other item renders `unmet`/`wrong_kind`, deliberately, so a hand-rolled
"yep, it's fine" can never stand in for DRC/LVS/corner/Monte-Carlo evidence
it never proved. (Since klayout-tools#2044, item 8 accepts `generic` and
*nothing else*.)

## What is here

| File | Asserts |
|---|---|
| `characterization-summary.analog.json` | The analog partition's half of [`sim/characterization-summary.md`](../../sim/characterization-summary.md): the per-spec-row table. |
| `characterization-summary.digital.json` | The digital partition's half of the same document: the `sar_ctrl_a` section's Fmax / area / power across the corner set. |

Both wrap the **same** document and both pin its sha256. They are two files
rather than one because the manifest keys every citation per partition (see
its own `_comment` for why), and because the two halves assert different
things about different silicon — a single shared envelope would make the
digital row's verdict a restatement of the analog row's.

## What a `pass` here does and does not mean

**It means: an aggregated, current characterization artifact exists, and a
human re-read it against the commit named in its own Freshness section.**

**It does not mean the design meets its spec.** Three ratified rows FAIL in
that document today — ENOB, SFDR and Area — and the digital partition's
rung-2 gate-level replay is not passing either. That is what T1 item **5**
("Full corner verification vs a ratified spec") grades, and item 5 is
`unmet` in the committed report, on both partitions. The checklist separates
"is there a current characterization report" from "does the block pass" on
purpose; conflating them here would be the single easiest way to make this
directory dishonest.

## Writing or re-asserting one of these

An envelope is a **claim**, not a manifest edit. Re-asserting it means
re-reading the document it wraps — which is the work; the JSON is the
receipt. The order is:

1. Re-read `sim/characterization-summary.md` against the current tree and
   fix what has drifted (its own Freshness section records the re-read).
2. Update this envelope's `status`, `summary`, `provenance.input.content_hash`
   (the document's fresh sha256) and `assertion.*` fields.
3. `python3 ../run_signoff.py --regen`, then write the new
   `../records/<record-id>.md` saying what moved.

`--check` re-hashes `sim/characterization-summary.md` on every pull request,
so editing that document without re-running `--regen` turns CI red. That
check proves **the bytes graded are the bytes committed** — it cannot prove
the bytes are still *true*. Only the re-read does that, which is why step 1
is first and why `assertion.reread_commit` is recorded.

**`status: "fail"` is a legitimate value here**, not a failure of process. An
envelope that says "this report has gone stale and nobody has re-read it" is
a more useful artifact than a `met` row resting on a re-read nobody did.

## Why `input_verified` is `null` on these citations

`klt signoff` re-hashes the input artifact an envelope names, for the kinds
whose input field it knows (`drc`/`extract`/`erc` → `file`, `lvs` →
`layout`, `sim` → `netlist`, `sta` → `def_path`, `yield` → `samples`). A
`generic` envelope's author chooses their own field names, so the grader
cannot know which key to re-hash and reports `input_verified: null` — the
pinned hash was only ever compared against this envelope's own claim about
it. **`run_signoff.py --check` closes that gap from the repo side**: it
pins `sim/characterization-summary.md` under the citation's `artifacts` and
re-hashes the committed file directly. As with the digital DRC citation, the
repo-side check is strictly stronger than the grader's here.
