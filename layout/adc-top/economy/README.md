# ADC top economy studies

Evidence records live in [`records/`](records/) and are append-only (see
[`sim/README.md`](../../../sim/README.md) "Append-only rule"). A record cannot
be edited to point at its replacement, so superseded records are listed here.
This file is an ordinary editable file, not a record; add a row when a new
record supersedes an older one.

## Superseded records

| Superseded | Superseded by | What changed |
|---|---|---|
| [`20261030-223000-be1c350`](records/20261030-223000-be1c350.md) | [`20261030-233000-809ed2c`](records/20261030-233000-809ed2c.md) | One figure in the Part 2 analysis paragraph: the 10 µm fold point is +5.3 % `ADC_TOP`, not +7 %. Sign and conclusion unchanged. |

## Stale decision-record citations

A record is minted at a HEAD hash and never edited afterwards, so when a
decision record is renumbered (two branches colliding on a number; see
`spec/decision-records/README.md` "If two records collide anyway"), a record
minted before the renumber can cite a number that now resolves to a different
record. Those citations are listed here rather than edited in place:

| Record | Cites | Means | Why |
|---|---|---|---|
| [`20261117-203922-0986aeb`](records/20261117-203922-0986aeb.md) | `DR-0048` | [`DR-0049`](../../../spec/decision-records/DR-0049-latch-up-tap-lattice.md) — the latch-up tap lattice | Minted during #897's review, before that record was renumbered `DR-0048` → `DR-0049`; `DR-0048` now resolves to the unrelated `DR-0048-nside-witness-above-rail-attribution.md`. Read both `DR-0048` tokens in the record's opening question as `DR-0049`. |
