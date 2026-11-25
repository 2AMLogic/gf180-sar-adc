# manifests/

Machine-checked manifests that point at evidence instead of containing it.

| Path | What it is |
|---|---|
| [`artifacts/`](artifacts/README.md) | One stored-evidence manifest per recorded run: the sha256, size and `artifact:<key>` URI of every object the run put in the fleet artifact store (issue #636, [DR-0041](../spec/decision-records/DR-0041-evidence-bytes-in-artifact-store.md)). |

Evidence bytes are private and manifests are public, so a manifest is safe to
commit here. Nothing in this directory names a storage bucket, cloud account or
broker URL (a grep of this directory for a bucket scheme or an account ARN
finds nothing), and CI refuses any `uri` that is not `artifact:<key>`.
