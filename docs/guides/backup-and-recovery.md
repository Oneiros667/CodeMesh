# Local Backup And Recovery Rehearsal

Document type: verified local operating guide

This procedure was exercised with disposable, single-node Linux Docker stores
at application candidate `f314043`. It restored a summary-free indexed
repository and synthetic vector fixtures into new volumes using the same image
identities. A separate development-baseline upgrade rehearsal is recorded below. Neither
rehearsal establishes supported-version upgrades, Windows acceptance, online backups,
cluster recovery, or permission to stop or replace an existing user environment.

## Preconditions And Evidence

Record the exact source and restore Compose project names, source SHA, store
and Agent Access image IDs, logical volume names, and selected repository
identity. Inspect volume ownership labels. Refuse a destination project or
volume that already exists. Keep the source volumes intact.

Capture complete graph-node and relationship digests, Neo4j index definitions,
MongoDB document digests for every CodeMesh collection, vector points and
payloads, repository metadata, and representative context-package items.
Require actual data in every store being claimed as verified; the vector
fixture here contains three explicitly synthetic points and uses no model.

The private archive directory must restrict access to its owner. Volume backups
contain repository content and may contain database authentication material.
Keep archives and raw manifests outside Git. Publish only sanitized evidence.

## Quiesce And Copy

From the selected application checkout, with its authorized local configuration:

```powershell
docker compose -p <source-project> stop
docker ps -q --filter label=com.docker.compose.project=<source-project>
```

The second command must return no running containers. Also wait for any
independent ingestor or writer to stop. Do not archive an online store or mix
volumes copied across different write states.

Copy all four volumes as one stopped set: `neo4j_data`, `neo4j_logs`,
`mongodb_data`, and `qdrant_data`. For each verified source volume:

```powershell
docker run --rm --network none --read-only `
  --mount type=volume,src=<source-volume>,dst=/data,readonly `
  --mount type=bind,src=<private-archive-directory>,dst=/backup `
  --entrypoint /bin/tar <verified-helper-image-id> `
  -czf /backup/<logical-volume>.tar.gz -C /data .
```

Record each archive's size and SHA-256 checksum, then verify the checksum before
restoration. This uses Docker's documented
[volume copy mechanism](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes).
The database consistency claim comes from the stopped set and the specific
restoration evidence, not from `tar` alone.

## Restore Into New Volumes

Create distinct, initially absent volumes with the restore project's ownership
labels. For each volume:

```powershell
docker volume create `
  --label com.docker.compose.project=<restore-project> `
  --label com.docker.compose.volume=<logical-volume> `
  <new-restore-volume>

docker run --rm --network none --read-only `
  --mount type=volume,src=<new-restore-volume>,dst=/data `
  --mount type=bind,src=<private-archive-directory>,dst=/backup,readonly `
  --entrypoint /bin/tar <verified-helper-image-id> `
  -xzf /backup/<logical-volume>.tar.gz -C /data
```

Create a private Compose override that binds each store and Agent Access to its
recorded source image ID and sets `pull_policy: never`. Start the restored
project with `--no-build`, using free loopback ports or keeping the source
project stopped. Recheck actual image IDs after startup. Do not use mutable tags
as proof of version equality.

## Validate And Retain

Wait for store and Agent Access health, then reproduce the complete pre-backup
digests. Require identical graph nodes, edges, index definitions, MongoDB
records, vector points/payloads, repository metadata, and ordered context items.
A startup success or matching counts alone is insufficient.

The [retained rehearsal](../evaluation/evidence/local-recovery-rehearsal-f314043.json)
matched all of these checks for 1,685 nodes, 3,634 relationships, 1,310 content
documents, the snapshot/registry records, three synthetic vectors, and eight
context-package items. No model provider was invoked. The source and restored
volumes remain separate; no existing user store was replaced.

Stop and remove only the disposable project containers after verification.
Preserve the private archive and evidence; volume deletion is a separate,
explicitly scoped cleanup. A future upgrade must separately name the supported
old and new versions and demonstrate migration and rollback. Select the
appropriate vendor backup method for other versions or deployment profiles.

## Development-Baseline Upgrade And Rollback

The [retained upgrade rehearsal](../evaluation/evidence/local-development-upgrade-ce23f2e.json)
uses published development source `8e9c0da` and candidate `ce23f2e`, with a
separate clean clone of the frozen YoutubeDownloader sample. The old software
indexed the sample; its stopped store set was backed up and restored into new
volumes with identical data and retrieval digests. The candidate reader left
stored data unchanged, then re-ingestion preserved project and checkout
identity while publishing new snapshots. Eight candidate citations passed
source-span, snapshot, and content-identity checks.

The initial retrieval gate failed cross-project relationship coverage because
the fresh sample had no restored dependency assets. Its locked restore failed
on the frozen AngleSharp advisory `GHSA-pgww-w46g-26qg`; no audit or warning gate
was disabled. Assets produced by that restore enabled the missing relationships
on re-ingestion. The unchanged six-case, 18-call retrieval suite then passed,
with two parser advisory warnings retained. The failed restore remains a failed
dependency check, so this result does not establish complete sample or supported
upgrade acceptance.

Scoped deletion removed the isolated repository's graph, content, and registry
state while preserving the unrelated synthetic vector fixture. Rollback then
restored the original software and complete original backup into another new
volume set. Every original data, metadata, and ordered context-item digest
matched. All rehearsal containers and networks were removed; the private
backups and all volume sets remain preserved.

Across reader revisions, package order and scoring differed even before
re-ingestion; do not require cross-version response equality as an upgrade
contract. Require grounded citations and the unchanged retrieval gates. Exact
response equality was required and passed for restoration of the same original
software and data.
