# `manifests/artifacts/` — stored-evidence manifests

One file per stored run: `<bench>-<run-id>.manifest.json`, written by
`sim/run_corners.py` or `sim/run_store_evidence.py` (issue #636). Each entry
names one object in the fleet artifact store by its sha256, with `size`,
`kind` (`evidence`), `producer` (`tool`, `version`, `loom.repo`, `commit`),
`uri` (`artifact:<key>`, resolved only by the broker) and `name`, the repo
path the bytes would have had under `sim/` (or `layout/`, `signoff/`). The
format is klayout-tools' `docs/cli/artifact.md`.

Evidence bytes are private; these manifests are public. The run's Markdown
record is committed beside the bench (`sim/<bench>/records/<run-id>.md`) with a
"Stored evidence" table of the same names, sizes and sha256s.

Manifests are append-only evidence: never edit or delete one
(`sim/tools/check_append_only_records.py` fails CI if you do). CI also runs
`python3 scripts/check_artifact_manifests.py check --tree HEAD --base <base>`,
which checks the schema, that every `uri` is `artifact:<key>`, and that no
stored object's bytes are also committed. That check never contacts the broker;
to check the bytes, run `klt artifact verify <manifest>` (or
`python3 scripts/check_artifact_manifests.py verify <manifest>`) with
`KLT_ARTIFACT_BROKER` set. On HTTP 429, the script honors the broker's
`Retry-After` delay or date and uses capped backoff if the header is absent
or unusable. If the delay exceeds the remaining 180-second wait budget for
that broker call, the sweep stops immediately. The script paces entries one
second apart and ends each manifest with
`<manifest>: <verified>/<total> verified`, and a sweep a broker error cuts
short exits 2 with `FAIL: sweep incomplete: <verified> of <total> ...` and no
`OK:` line, so it cannot be mistaken for a complete one. See `sim/README.md`,
"Stored evidence".
