# Repository Identity And Snapshot Retention Requirements

Status: local profile implemented; shared service deferred

The local single-user identity, deterministic snapshot, slot publication,
explicit retention-slot, legacy migration, and reference-aware cleanup model is
implemented. Shared-service coordination, tenant isolation, authorization,
privacy controls, quotas, and auditability remain future requirements and are
not activated. The implemented decisions are recorded in
[ADR 0001](../decisions/0001-local-repository-identity-and-snapshot-publication.md).

## Purpose

CodeMesh must distinguish multiple checkouts of the same logical project
without retaining every intermediate working state. The design must support:

- separate folders, clones, and Git worktrees on different branches or commits;
- one useful current working state per active checkout;
- the latest successfully indexed head of each branch selected by policy;
- deduplication when several references resolve to the same indexed source;
- bounded cleanup across graph, content, vector, summary, and registry stores;
- local-first operation without requiring a shared service; and
- future organization-scoped stores used safely by multiple developers.

The core requirement is to retain named references to useful snapshots, rather
than treating every successful re-index as permanently valuable history.

## Current Behavior And Gap

Legacy records derived `repository_id` from the absolute repository root. New
local ingestion uses a stable random project id, worktree-specific checkout id,
and deterministic snapshot id while retaining origin, branch, commit, and dirty
state as observations. Agent Access resolves a project or alias to its active
snapshot namespace and compares recorded provenance with the accessible local
checkout.

The implemented local profile closes the folder/branch retention gaps, with the
following remaining limitations:

- a central Agent Access process cannot inspect a developer folder that is not
  mounted on the server; and
- direct concurrent writes from several clients cannot safely publish a
  coherent generation across all stores.

Separate clones require an explicit shared `--project-id`; remote URL text never
merges them automatically. Shared-mode requirements below remain planning
authority rather than implemented behavior.

## Terminology

| Term | Meaning | Expected lifetime |
| --- | --- | --- |
| Project | One logical source lineage within an owner or tenant boundary. | Long-lived |
| Checkout | One physical clone or Git worktree used by one installation. | While the checkout exists or remains registered |
| Source view | The exact included file contents observed by ingestion. | Content-addressed |
| Snapshot | A deterministic indexed representation of a source view under one ingestion profile. | While referenced |
| Index slot | A named pointer to the currently useful snapshot for a branch, checkout, or explicit pin. | Depends on slot type |
| Observation | Git and workspace provenance associated with a snapshot, such as commit, branch, dirty state, installation, and time. | Policy-controlled |
| Generation | Staged cross-store writes that are not queryable as active until publication succeeds. | Short-lived |

## Identity Requirements

### Project identity

- **RID-001:** `project_id` must identify the logical project independently of
  checkout folder, hostname, branch, commit, and working-tree state.
- **RID-002:** Shared deployments must scope project identity by tenant or
  organization. Identical content in unrelated tenants must not imply shared
  authorization or identity.
- **RID-003:** Normalized remote identities may help resolve a project, but
  remote URL text alone must not silently merge forks, mirrors, or unrelated
  repositories. Resolution must fail closed when ambiguous.
- **RID-004:** A shared service should issue or resolve the authoritative
  `project_id`. A local identity file may cache that value but is not sufficient
  to establish cross-developer identity on its own.
- **RID-005:** Projects without a remote must support an explicit locally
  generated identity and a later controlled attachment to a shared project.

### Checkout identity

- **RID-006:** `checkout_id` must be a persistent random identifier for one
  physical clone or Git worktree. It must not be derived solely from its path.
- **RID-007:** Moving a folder must preserve its checkout identity when the old
  location no longer exists.
- **RID-008:** If a copied identity marker appears in two simultaneously
  existing folders, CodeMesh must detect the collision and assign a new
  checkout identity rather than merging their working states.
- **RID-009:** Linked Git worktrees must receive different checkout identities
  even though they share a Git common directory.
- **RID-010:** Hostname and absolute folder may be captured as local
  observations, but they must not participate in `project_id`, `checkout_id`,
  or `snapshot_id`.

### Local identity marker

CodeMesh may use an ignored local marker such as:

```json
{
  "format_version": 1,
  "project_id": "prj_01...",
  "checkout_id": "chk_01...",
  "created_at_utc": "2026-08-12T10:00:00Z"
}
```

- **RID-011:** A root marker must be ignored by Git, not merely left untracked,
  because an ordinary untracked file makes `git status --porcelain` dirty.
- **RID-012:** The marker must also be excluded from parsing and source-view
  fingerprinting.
- **RID-013:** For Git repositories, an implementation may prefer private Git
  storage: project cache under the common Git directory and checkout identity
  under the worktree-specific Git directory. A root marker remains a valid
  fallback when those locations are unavailable.
- **RID-014:** The marker must not contain credentials, server tokens, raw
  secrets, or other authentication material.
- **RID-015:** `snapshot_id`, hostname, folder, and branch must not be canonical
  marker fields. A last snapshot value may be cached for diagnostics, but the
  registry remains authoritative for active slot pointers.

### Snapshot identity

- **RID-016:** `snapshot_id` must be deterministic for the same project, source
  view, ingestion scope, parser/redaction profile, and graph schema version.
- **RID-017:** Re-indexing identical effective inputs must reuse the same
  snapshot identity and must not create duplicate retained graph state.
- **RID-018:** Checkout id, hostname, absolute folder, branch name, staging
  state, filesystem timestamps, and file ownership must not affect snapshot
  identity.
- **RID-019:** Git commit is provenance rather than source identity. Two commits
  with the same effective source view may refer to the same snapshot while
  retaining distinct commit observations.
- **RID-020:** Changes outside the selected ingestion scope or within excluded
  paths must not change the snapshot identity.
- **RID-021:** Embedding model and summary model configuration must identify
  derived artifact sets rather than force duplication of the underlying graph
  snapshot.

A candidate source snapshot formula is:

```text
snapshot_id = hash(
    identity_format_version
  + project_id
  + source_view_hash
  + ingestion_scope_fingerprint
  + parser_and_redaction_profile_fingerprint
  + graph_schema_version
)
```

Derived artifacts should use separate identities, for example:

```text
embedding_set_id = hash(snapshot_id + provider + model + chunking_profile)
summary_set_id   = hash(snapshot_id + provider + model + prompt_profile)
```

The exact canonical serialization and hash algorithm require an ADR before
implementation.

## Retention Model

### Index slots

CodeMesh should retain snapshots through named slots:

| Slot kind | Key | Normal policy |
| --- | --- | --- |
| Branch head | Project plus canonical Git ref | Retain the latest successfully indexed selected branch head |
| Checkout current | Checkout id | Retain exactly one current working state |
| Explicit pin | Project plus pin id | Retain until deliberately released |
| Evidence | Evidence record id | Retain while the evidence remains authoritative |
| Staging | Ingestion generation id | Retain only during bounded publication or failure handling |

- **RET-001:** A dirty checkout re-index must update only its checkout-current
  slot. It must not move a branch-head slot.
- **RET-002:** Re-indexing a changed checkout must replace its current slot
  pointer after successful publication rather than retaining every intermediate
  dirty state.
- **RET-003:** When a clean checkout matches an indexed branch head, its branch
  and checkout slots should point to the same snapshot.
- **RET-004:** Moving a branch head must make the old snapshot collectible once
  no checkout, branch, pin, evidence record, or staging generation references
  it.
- **RET-005:** CodeMesh must not index or retain every Git branch merely because
  the ref exists. Branch selection must be explicit or policy-controlled.
- **RET-006:** A local deployment may retain heads for locally indexed branches.
  A shared deployment should distinguish canonical remote branch heads from
  private or stale local branch observations.
- **RET-007:** Deleted branch slots and inactive checkout slots must have
  configurable grace periods before their unreferenced snapshots are removed.

The retained set is therefore:

```text
retained snapshots =
    branch-head targets
  + checkout-current targets
  + explicit pins
  + evidence references
  + active staging generations
```

### Atomic publication and cleanup

- **RET-008:** A new generation must remain inactive while its required graph,
  content, registry, and configured derived artifacts are written and checked.
- **RET-009:** Slot publication must be an atomic compare-and-swap or equivalent
  operation so an older client cannot silently replace a newer branch head.
- **RET-010:** A failed generation must leave the previous active slot usable
  and must not be reported as current evidence.
- **RET-011:** Garbage collection must be reference-aware across every store and
  must be retryable after partial infrastructure failure.
- **RET-012:** Deleting a project, checkout, branch slot, pin, or snapshot must
  have explicit authorization and an auditable result in shared mode.
- **RET-013:** Graph, content, vector, summary, and registry counts must expose
  staging, active, and collectible state separately where useful for diagnosis.

## Persistence Classification

### Persist while referenced

- Project identity, approved remote aliases, ownership, and tenant boundary.
- Selected canonical branch slots and their observed Git heads.
- Active checkout registration and its current slot in local mode.
- Snapshot identity, source-view and ingestion-profile fingerprints, and schema
  version.
- Git commit, branch, dirty-state, producer-version, and ingestion-time
  provenance.
- Redacted content, graph records, embeddings, and summaries required by active
  slots or pins.
- Explicit evaluation, release, or other evidence pins.
- Shared-mode authorization and publication audit records.

### Keep only for a bounded period

- In-progress staging generations.
- A previous active generation during a short rollback or cleanup grace period.
- Failed-run diagnostics and retry information.
- Inactive checkout registrations.
- Private shared-mode working snapshots when explicitly enabled.
- Operational health, cost, and query caches.

### Ignore or collect

- Superseded intermediate dirty snapshots.
- Staged-versus-unstaged Git state when the files visible to ingestion are
  identical.
- File timestamps, ownership, hostname changes, or folder moves.
- Changes to ignored or parser-excluded files.
- Unreferenced old branch heads after their grace period.
- Branches that have never been selected and successfully indexed.
- Duplicate redacted content or derived artifacts with the same effective
  identity.
- Raw hostname and absolute developer paths in shared storage by default.

## Local And Shared Deployment Profiles

The identity and slot model should remain common. Deployment policy should
differ rather than creating two incompatible data models.

| Concern | Single-user local profile | Shared service profile |
| --- | --- | --- |
| Project resolution | Local identity with optional remote evidence | Tenant-scoped server registration |
| Current dirty state | One retained snapshot per active checkout | Local overlay by default; private upload only when enabled |
| Branch authority | Locally observed selected branch | Trusted remote, CI, or authorized publication source |
| Path and host | Available to the local user | Omitted or pseudonymized by default |
| Writes | Locally coordinated store writes | Server-mediated staged ingestion |
| Access control | Local process boundary | Tenant, project, role, and owner authorization |
| Freshness | Agent Access may inspect the checkout directly | Local client attestation compared with central snapshot |
| Retention | User-configurable | Enforced quotas, TTLs, pins, and audit policy |

### Shared-service requirements

- **SHR-001:** Developer clients must not write independently and directly to
  each backing database. A coordinator must publish coherent generations.
- **SHR-002:** A normal developer checkout must not update an authoritative
  shared branch-head slot unless the server verifies its authority and expected
  previous state.
- **SHR-003:** Uncommitted working state must remain local by default. If shared,
  it must be owner-scoped, opt-in, encrypted in transit and at rest, and
  protected by a bounded retention policy.
- **SHR-004:** Central records must use repository-relative source paths. Raw
  hostname and absolute checkout root must not be returned to other users.
- **SHR-005:** Content hashes and deduplication must not create cross-tenant
  information leaks. Cross-project deduplication requires an explicit security
  decision rather than being an incidental storage optimization.
- **SHR-006:** Shared queries must select a project, canonical branch snapshot,
  or authorized checkout overlay explicitly when more than one match exists.
- **SHR-007:** Store access, ingestion publication, pinning, deletion, and
  retention-policy changes require authorization and auditability.
- **SHR-008:** Broader sensitive-file exclusion, configurable allow/deny policy,
  and deletion verification are release gates before centrally storing
  proprietary developer workspaces.

## Query And Freshness Requirements

- **QRY-001:** Agent Access responses must identify the selected `project_id`,
  `snapshot_id`, slot kind, indexed source fingerprint, and relevant Git
  provenance.
- **QRY-002:** A local client should resolve the current checkout id before
  falling back to a project alias or folder name.
- **QRY-003:** Ambiguous project, checkout, branch, or alias resolution must
  return candidates and fail closed rather than selecting the most recently
  seen repository.
- **QRY-004:** Freshness must distinguish commit mismatch, source-view mismatch,
  dirty working state, inaccessible checkout, and unknown provenance.
- **QRY-005:** In shared mode, the server must not claim live checkout freshness
  from a historical path. Freshness must come from a current client attestation
  or be reported as unavailable.
- **QRY-006:** Queries without a checkout context should default only to a
  configured canonical branch, not to another developer's private working slot.

## Acceptance Criteria

This feature is not complete until automated and integration evidence shows:

1. Two folders for one project can index different commits without graph,
   content, vector, summary, or registry collisions.
2. Re-indexing identical effective inputs reuses the same snapshot and derived
   artifacts where their configurations match.
3. Repeated dirty re-indexing retains only the latest checkout-current state,
   plus bounded staging or rollback generations.
4. Dirty checkout indexing does not move a branch-head slot.
5. A clean checkout and matching branch head reuse one snapshot.
6. Branch movement, deletion, checkout expiry, and explicit unpinning make only
   unreferenced data collectible.
7. Publication failure in any required store leaves the previous active
   generation queryable and reports the new generation as failed.
8. A root identity marker neither dirties the checkout nor changes source or
   snapshot fingerprints.
9. Folder moves preserve checkout identity, while simultaneous copied markers
   fail closed and receive separate checkout ids.
10. Shared branch-head publication rejects unauthorized or stale writers.
11. Shared queries cannot discover another tenant's project, content hashes,
    paths, snapshots, or derived artifacts.
12. Raw hostname and absolute checkout path remain local unless an administrator
    explicitly enables restricted diagnostic collection.
13. Garbage collection and explicit deletion produce consistent, retryable
    results across every configured store.
14. Current behavior and migration status remain accurately documented throughout
    staged rollout.

## Non-Goals

This proposal does not require:

- retaining every commit or every local branch;
- preserving every intermediate dirty working state;
- automatically uploading uncommitted files to a shared server;
- treating a branch name, remote URL, folder name, or alias as sufficient
  identity;
- sharing raw paths or hostnames between developers;
- deduplicating proprietary content across tenants;
- making embeddings or summaries mandatory for a snapshot; or
- presenting a portable snapshot artifact as the canonical live-store model.

## Decisions Required Before Shared-Service Implementation

An ADR must decide:

1. Server project registration and remote-identity normalization rules.
2. Canonical remote branch authority, deletion, and quota policies.
3. Cross-service coordinator recovery and audit semantics.
4. Local-overlay behavior and whether private dirty snapshots may enter a
   shared service.
5. Tenant isolation, encryption, audit, quota, and verified-deletion controls.

## Proposed Delivery Sequence

1. Completed: record local identity, snapshot, publication, and migration
   decisions in an ADR.
2. Completed: add contracts and registry persistence for projects, checkouts,
   snapshots, observations, slots, and generations.
3. Completed: add local Git-private identity discovery, move preservation, and
   copied-marker collision handling.
4. Completed: add staged snapshot namespaces, compare-and-swap slot publication,
   explicit retained slots, and reference-aware local cleanup.
5. Completed: resolve Agent Access project/alias queries to active snapshots and
   expose snapshot/source-view freshness metadata.
6. Completed locally: automated clean, dirty, identical-input, move, copied
   marker, linked-worktree, pin/unpin, deletion, and cleanup coverage.
7. Deferred: add a shared ingestion coordinator, tenant authorization, privacy
   controls, quotas, and local working-state overlay only after the local model
   is stable.

Shared deployment or production activation still requires separate
authorization and evidence. The local implementation does not grant either.
