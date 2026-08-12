# ADR 0001: Local Repository Identity And Snapshot Publication

Status: accepted

Date: 2026-08-12

## Context

CodeMesh previously derived `repository_id` from the absolute checkout root and
stored one mutable namespace per folder. Re-indexing after a branch switch or
working-tree change removed the prior graph, content, vector, and summary data.
Separate clones of one project could not deliberately share an identity.

The local implementation needs stable project and checkout identities,
deterministic source snapshots, bounded retention, and fail-closed publication.
Shared-service tenant, authorization, encryption, quota, and audit controls do
not yet exist and must not be implied by this decision.

## Decision

- `project_id` is a random `prj_` identifier. Linked worktrees cache it in the
  Git common directory; separate clones attach deliberately with
  `--project-id`. A remote URL remains provenance and never silently merges
  projects.
- `checkout_id` is a random `chk_` identifier stored under the worktree-specific
  Git directory. Non-Git roots use ignored `.codemesh` marker files. Moving a
  checkout preserves it; a concurrently live copied marker receives a new id.
- `snapshot_id` is `snp_` plus SHA-256 over a versioned canonical sequence of
  project id, redacted source-view hash, ingestion scope, parser/redaction
  profile, and graph schema version. Git commit, branch, checkout, path, host,
  timestamps, embeddings, and summaries are excluded.
- Snapshot graph, content, vector, and summary data use `snapshot_id` as their
  internal repository namespace. The public registry continues to expose the
  stable project id and records its currently selected snapshot.
- Every ingest stages a generation. It publishes checkout-current and, only for
  clean named branches, branch-head slots through registry compare-and-swap.
  Store writes are inactive until that slot update succeeds.
- Explicit pin/evidence slots are registry operations. A snapshot becomes
  collectible only when no slot references it. Cleanup is retryable and removes
  the snapshot namespace from every configured store before deleting its
  registry record.
- The default unreferenced grace period is 86,400 seconds and can be changed for
  ingestion with `--snapshot-retention-grace-seconds`.
- Existing absolute-path namespaces are registered as collectible legacy
  snapshots when the checkout is next successfully ingested under the new
  identity. They are not deleted during migration.

## Consequences

Identical effective inputs reuse one snapshot across linked worktrees and
commits. Dirty ingestion cannot move a branch head, and repeated dirty ingestion
retains only checkout-current plus referenced or grace-period snapshots.
Repository deletion expands to every retained namespace.

Publication is atomic at the registry slot boundary, not as one distributed
transaction across Neo4j, MongoDB, and Qdrant. A failed/stale generation leaves
the previous slots queryable and its unreferenced data collectible. Shared
deployment requires a server coordinator and a separate security/authorization
decision before activation.
