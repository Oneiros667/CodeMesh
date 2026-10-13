# Agent Access Contracts

Document type: current interface reference

For call order, algorithms, adapter behavior, and failure interpretation, use
[Retrieval Internals](retrieval-internals.md). This document remains the
canonical interface field and surface reference.

Agent Access exposes its repository read surface through REST, MCP tools, and
the typed .NET client in `CodeMesh.Control.AgentAccess.AgentAccessClient`.
Session-scoped feedback recording and maintainer intake are MCP/Python-only
local development controls; they are not added to REST or the .NET client.

It also serves a local read-only web UI at `/ui` for humans to inspect service health, repositories, repository freshness, ingestion runs, and context search results. The UI reuses the REST read store and is not a separate write surface.

Source-of-truth implementations:

- REST models: `agent-access/codemesh_agent_access/models.py`
- REST routes: `agent-access/codemesh_agent_access/rest.py`
- Local UI routes: `agent-access/codemesh_agent_access/web.py`
- MCP manifest: `agent-access/codemesh_agent_access/mcp.py`
- .NET contracts: `src/CodeMesh.Domain/Contracts/AgentAccessContracts.cs`

## Common Controls

Most read calls accept `repository_id`. This can be the stable project id, an
explicit snapshot id, a checkout/branch slot key, or the generated alias. Agent
Access resolves projects and aliases to their selected active snapshot before
querying stores and fails closed on ambiguous slot/alias matches. Repository
lookup accepts URL-encoded path characters in `repository_id`; generated aliases
remain slash-free and are retained with project identity across checkout moves
and linked-worktree ingestion.

The normal stdio MCP server can instead start with an exact
`project_id`/`checkout_id`/`repository_root` binding and optional
`source_view_hash`. A complete binding is required for that product profile.
Bound repository tools inject the project id, reject conflicting caller
selectors, resolve only that checkout's current slot, and reject packages when
the project, checkout, root, source view, commit, or dirty-state freshness check
is not accepted. The diagnostic profile may still run unbound for explicit
administrative investigation.

Filters are exact-match string filters. They can match top-level node fields or metadata fields. `kinds` filters by CodeMesh node kind names such as `Method`, `Class`, `File`, `TestFile`, `TestCase`, or `Declaration`.

## REST Endpoints

| Method | Path | Request | Response | .NET client |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | none | `HealthResponse` | `GetHealthAsync` |
| `GET` | `/status` | none | `HealthResponse` | `GetStatusAsync` |
| `POST` | `/context/search` | `ContextQuery` | `ContextResponse` | `SearchContextAsync` |
| `POST` | `/context/package` | `ContextPackageQuery` | `ContextPackageResponse` | `GetContextPackageAsync` |
| `POST` | `/symbols/search` | `SymbolQuery` | `SymbolSearchResponse` | `SearchSymbolsAsync` |
| `POST` | `/nodes/get` | `NodeLookup` | `NodeResponse` | `GetNodeAsync` |
| `POST` | `/graph/neighbors` | `NeighborQuery` | `NodeResponse` with `relationships` populated | `GetNeighborsAsync` |
| `GET` | `/repositories?limit=50` | query string | `RepositoryListResponse` | `ListRepositoriesAsync` |
| `GET` | `/repositories/{repository_id:path}` | route value | `RepositorySummary` or `null` | `GetRepositoryAsync` |
| `GET` | `/repositories/{repository_id}/summaries` | route value | `NodeSummaryCoverageResponse` | `GetSummaryCoverageAsync` |
| `GET` | `/repositories/{repository_id}/status` | route value | `RepositoryStatusResponse` | `GetRepositoryStatusAsync` |
| `DELETE` | `/repositories/{repository_id:path}` | route value | `RepositoryDeleteResponse` | `DeleteRepositoryAsync` |
| `GET` | `/ingestion-runs?repository_id=&limit=50` | query string | `IngestionRunListResponse` | `ListIngestionRunsAsync` |

## Local Web UI

These routes return HTML for human inspection and reuse the same read paths as the REST API:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/ui` | Dashboard with service health, repository summaries, recent runs, and search controls. |
| `GET` | `/ui/repositories` | Repository list. |
| `GET` | `/ui/repositories/{repository_id:path}` | Repository freshness, counts, metadata, and recent runs. |
| `GET` | `/ui/runs?repository_id=` | Ingestion run history with optional repository filtering. |
| `GET` | `/ui/search?query=&repository_id=&limit=12` | Read-only context search results. |

## Context Search

`ContextQuery` fields:

- `query`: required text query.
- `repository_id`: optional repository id or alias.
- `limit`: default `8`.
- `kinds`: optional node kind filters.
- `filters`: optional exact-match filters.
- `vector`: optional explicit query vector.
- `expand_context`: default `true`.
- `context_depth`: default `4`.
- `include_context_relationships`: default `false`.
- `context_relationship_limit`: default `8`.

`ContextResponse` includes:

- `query`: the resolved query. If a project or alias was supplied,
  `repository_id` is rewritten to the active snapshot namespace.
- `hits`: ranked `ContextHit` items.
- `diagnostics`: search execution metadata.
- `generated_at`: UTC timestamp.

`ContextHit` fields:

- `node_id`, `stable_key`, `kind`, `file_path`, `start_line`, `end_line`, `score`.
- `repository_id` (stable project), `snapshot_id`, and `content_hash` when available.
- `score_components`, including values such as `vector_score`, `lexical_score`, `summary_score`, `kind_weight`, and `expansion_bonus`.
- `expanded_context` when a low-level match was expanded or a declaration was attached.
- `preview` when a snippet preview is available.

Search diagnostics:

- `mode`: `vector`, `lexical`, `summary`, `hybrid`, or `none`.
- `embedding_attempted`: true when Agent Access attempted to embed the text query.
- `embedding_source`: `provided`, `model_provider`, or `none`.
- `model_provider`: normalized configured provider, such as `none`, `ollama`, or `lmstudio`.
- `vector_available`: true when an explicit or generated vector was available.
- `vector_hit_count`: returned hit count with vector contribution after dedupe/ranking.
- `lexical_hit_count`: returned hit count with lexical contribution after dedupe/ranking.
- `summary_hit_count`: returned hit count with generated-summary contribution after dedupe/ranking.
- `vector_candidate_count`: raw vector candidate count before dedupe/ranking.
- `lexical_candidate_count`: raw lexical candidate count before dedupe/ranking.
- `summary_candidate_count`: raw generated-summary candidate count before dedupe/ranking.
- `lexical_fallback`: true when a vector was available but produced no vector hits.
- `hit_count`: final returned hit count after dedupe/ranking.
- `selected_project_id` and `selected_snapshot_id`: the project provenance and
  exact snapshot namespace selected for the response when available.

Repository-scoped lexical search filters the initial graph match before
loading and matching searchable properties. Unbound administrative search
retains its cross-repository behavior. The change preserves lexical scoring,
candidate limits, ordering, filters, and parameterized query values.

Agent Access merges vector hits, lexical graph hits, and MongoDB generated-summary
hits, then dedupes by `node_id`. When final scores tie, raw vector, lexical, and
summary relevance break the tie before kind and source-line ordering. Context
package selection covers distinct files before taking repeated items from the
same file when eligible alternatives remain.

## Summary Coverage

`GET /repositories/{repository_id}/summaries` accepts a repository hash id or alias and returns summary pipeline coverage for that repository.

## Repository Status And Freshness

`GET /repositories/{repository_id}/status` accepts a repository hash id or alias and returns an agent-facing repository status bundle. It includes:

- `repository`: registry metadata when the repository exists.
- `latest_run`: the latest ingestion run when available.
- `summary_coverage`: summary coverage for the repository.
- `counts`: graph node, relationship, content document, vector, and summary counts.
- `freshness`: local git diagnostics when the repository path is accessible to Agent Access.
- `refresh`: derived latest-refresh activity and outcome from the latest ingestion run.

Freshness fields include `indexed_commit`, `current_commit`, `current_branch`,
`working_tree_dirty`, `is_stale`, `status`, and `detail` when available. Bound
responses also include a binding assessment with `accepted` or `rejected`
status and exact issues. Missing provenance remains `unknown` for unbound
administrative reads but is rejected by bound normal-profile package access.

Snapshot-aware fields include `selected_snapshot_id`,
`indexed_source_view_hash`, `commit_mismatch`, `source_view_mismatch`, and
`provenance_status`. A clean commit match is not substituted for a source-view
match. If the checkout path is inaccessible, provenance remains recorded but
live checkout freshness is unavailable.

Refresh fields include `status`, `is_running`, `changed`, `latest_run_id`, `stage`, `started_at`, `finished_at`, `diagnostic_count`, `error_diagnostic_count`, `warning_diagnostic_count`, `stats`, `detail`, and `recommended_action` when available. `status` is derived from the latest ingestion run and can be `no_run`, `running`, `completed`, `skipped`, `failed`, `dry_run`, or `unknown`.

The MCP status result adds `codemesh_next_action`. A fresh, accepted checkout
binding directs the agent to continue immediately with one agent-format
`codemesh_get_context_package` request using a concise task-shaped query and
default limits. If that package covers every required facet, retrieval stops.
Only a specific unresolved implementation or test facet justifies one focused
follow-up; the task budget is at most three non-overlapping packages. Every
other state directs the agent to stop CodeMesh discovery and fall back to
direct source inspection. Status remains an explicit diagnostic operation
rather than a required first hop. This presentation-only field is not part of
the REST status model.

`NodeSummaryCoverageResponse` fields:

- `repository_id`: resolved repository id.
- `total_count`, `completed_count`, `failed_count`.
- `status_counts`: summary counts grouped by status.
- `kind_counts`: summary counts grouped by CodeMesh node kind.
- `provider_model_counts`: counts grouped by provider, model, and prompt version.
- `provider_model_count_details`: structured provider/model/prompt count records for clients that should not parse the compatibility keys in `provider_model_counts`.
- `recent_failures`: up to ten recent failed summary records with error metadata.
- `generated_at`: UTC timestamp.

## Repository Delete

`DELETE /repositories/{repository_id}` accepts a project id or alias, resolves
it through the registry, and removes every retained snapshot namespace from the
graph, content, vector, and summary stores before removing run, project,
checkout, slot, generation, observation, and repository registry records.

The Python CLI exposes the same operation:

```powershell
cd agent-access
uv run python -m codemesh_agent_access delete-repo <repository-id-or-alias>
```

`RepositoryDeleteResponse` fields:

- `repository_id`: resolved repository id, or the supplied value when the registry had no match.
- `deleted`: true when a registry entry was found and cleanup was attempted.
- `registry_entry_existed`: true when the repository existed in the registry.
- `graph_cleaned`, `content_cleaned`, `embeddings_cleaned`, `summaries_cleaned`: true when the corresponding store cleanup completed.

For unknown repositories, the response is non-failing and returns `deleted = false`.

## Ingestion Runs

`GET /ingestion-runs` returns recent ingestion runs, optionally filtered by `repository_id` hash id or alias.

Each `IngestionRunSummary` includes:

- Repository, parser, solution/project, stage, timing, diagnostic, embedding provider/model, and count metadata.
- `stats`: normalized incremental write counts when available. Summary-specific keys are `summary_candidate_count`, `written_summary_count`, `skipped_summary_count`, and `failed_summary_count`.

## Context Package

Optional `CODEMESH_CONTEXT_PACKAGE_TIMINGS` diagnostics write sanitized stage,
search-operation, and hydration-operation timings to stderr. They preserve
the package response and formatting contracts. Search timings include nested
pipeline totals and per-operation call counts, are isolated per request, and
must not be summed as wall-clock latency. See the
[evaluation timing contract](../evaluation/mcp-effectiveness.md) for capture
and interpretation.

`ContextPackageQuery` fields:

- Core controls: `query`, `repository_id`, `limit`, `kinds`, `filters`, `vector`, `context_depth`.
- Content controls: `max_characters`, `include_content`.
- Relationship controls: `include_relationships`, `relationship_limit`, `caller_limit`, `callee_limit`, `read_limit`, `write_limit`, `contains_limit`, `definition_limit`, `uses_type_limit`.
- Registry control: `include_repository`.

`ContextPackageResponse` includes:

- `repository`: repository metadata when requested and available.
- `latest_run`: latest ingestion run metadata when requested and available.
- `items`: package items built from context hits.
- `validation_recommendations`: local validation commands inferred from packaged file paths.
- `total_snippet_characters`: total emitted snippet characters.

Each package item includes:

- `hit`: the ranked `ContextHit`.
- `node`: normalized node metadata.
- `content`: content document metadata.
- `summary`: generated node summary metadata when a completed summary exists in MongoDB.
- `snippet`: budgeted source text when available.
- `relationships`: flat relationship summaries.
- `relationship_groups`: grouped summaries for `callers`, `callees`, `reads`, `writes`, `contains`, `defines`, and `uses_types`.
- `rationale`: ranking and expansion metadata.

Validation recommendations currently cover the .NET harness, Agent Access
Python tests/lint, Cargo formatting/Clippy/tests, deployment parser dry-runs,
end-to-end smoke checks for Docker/service changes, and Markdown dry-runs.

MCP `codemesh_get_context_package` is the configured normal-host entry action
and also accepts `output_format = "agent"`. The bound package path validates
the exact binding and freshness before search and fails closed when either is
not accepted, so a separate status call is not required before retrieval. In
agent mode the tool returns the brief directly as one text content block and
intentionally omits structured content, avoiding MCP's duplicate text-plus-
structured serialization. MCP agent output is capped at 12,000 characters even
when a larger package budget is requested; the CLI continues to honor its
explicit output budget. The brief includes validation recommendations plus each
item's file span, node id, stable key, repository id, content hash, score, rank,
and rationale details and adds a truncation marker when capped. Use the default
`json` format when a caller needs the complete structured package.

## Symbols, Nodes, And Neighbors

`SymbolQuery` fields:

- `query`: required text query.
- `repository_id`, `limit`, `kinds`, `filters`.
- `include_declarations`: default `true`.

`SymbolSearchResponse` returns `symbols`, each with `node`, optional `declaration`, `score`, and `score_components`.

`NodeLookup` fields:

- `node_id`: required.
- `repository_id`: optional repository id or alias.
- `include_content`: default `true`.
- `include_neighbors`: default `true`.

`NodeResponse` returns `node`, `content`, and `relationships`. `/graph/neighbors` reuses this response shape and returns relationship rows in `relationships`; `node` and `content` are normally null.

`NeighborQuery` fields:

- `node_id`: required.
- `repository_id`: optional repository id or alias.
- `depth`: default `1`.
- `relationship_kinds`: optional relationship-kind filter.

## MCP Tools

MCP exposes named tool profiles. The default `normal` profile is the supported
product surface:

- `codemesh_get_context_package`
- `codemesh_get_repository_status`
- `codemesh_list_repositories`
- `codemesh_get_node`

The `diagnostic` profile adds these non-destructive inspection tools:

- `codemesh_status`
- `codemesh_get_tool_guidance`
- `codemesh_search_context`
- `codemesh_search_symbols`
- `codemesh_get_neighbors`
- `codemesh_get_repository`
- `codemesh_get_summary_coverage`
- `codemesh_list_ingestion_runs`

Two explicitly activated local development-session profiles are also
implemented:

- `development-feedback` contains the four normal tools plus
  `codemesh_get_feedback_session` and `codemesh_record_feedback`.
- `feedback-maintainer` contains the four normal tools plus
  `codemesh_list_feedback`, `codemesh_get_feedback`, and
  `codemesh_prepare_feedback_resolution`.

Select a profile with `mcp --profile PROFILE`. Unknown profile names fail before
the MCP server starts. Both feedback profiles additionally require a complete
repository binding, `--feedback-session`, and
`--feedback-session-sha256`; startup and every feedback call revalidate the
immutable manifest, expiry, revocation record, exact binding, and allowlist.
The manifest records the selected `profile` and includes only that profile's
tools and contracts. Repository deletion remains an explicitly invoked
administrative REST or Python CLI operation outside every MCP profile.

The MCP initialize result includes canonical server instructions for normal-host
onboarding. For implementation discovery, likely change impact, and validation
selection, they direct agents to start with an agent-format context package at
default limits and use its ranked spans for targeted verification reads. The
same text is exposed as the top-level `instructions` field in the stable
manifest. A bound server's instructions also name its exact project, checkout,
and root.

Those initialization instructions are defense in depth rather than proof that
every host presents or follows them. The implemented selected contract combines
repository-owned guidance, an exact bound normal profile, hashed installation,
and a live provider-free probe. See [MCP Setup](../guides/mcp-setup.md).

`codemesh_get_tool_guidance` accepts optional `task` text and returns ranked workflows with recommended tool steps. Use it when an agent has not yet decided whether to search context, inspect freshness, look up a symbol, fetch neighbors, or build a package.

Repository deletion remains documented under [Repository Delete](#repository-delete)
and is not an MCP tool in either implemented profile.

The manifest can be printed with:

```powershell
cd agent-access
uv run python -m codemesh_agent_access mcp-manifest
```

Pass `--profile diagnostic` to inspect that profile's manifest. Omitting the
option prints the default `normal` profile.

The manifest is covered by `agent-access/tests/test_mcp_contract.py`.

## Installation, Probe, And Feedback CLI

`install plan` produces a complete JSON plan containing the exact MCP launch,
binding, target-file hashes, full new content, diffs, and a plan hash without
changing the target. The current `codemesh-installation-plan-v2` adds an
optional pinned session path and hash; it is required for feedback profiles and
rejected for other profiles. The loader remains compatible with reviewed v1
normal plans. `install apply` requires the exact reviewed hash and rejects
target drift. `--configuration-only` leaves repository guidance to an external
instance manager.

`mcp-probe --plan PLAN` verifies that the reviewed plan is applied, launches
its exact stdio command with `CODEMESH_MODEL_PROVIDER=none`, checks the normal
four-tool surface, exact one-repository listing, accepted/fresh binding, and a
non-empty context package. `--query` and repeated `--expected-path` options turn
that package into a repository-specific retrieval gate.

For a feedback-profile plan, the same command checks the exact session pins,
binding, initialization instructions, and profile tool surface. The client
probe calls session discovery without writing a packet; the maintainer probe
performs a bounded allowlisted list operation. Altered, expired, revoked, and
wrong-binding sessions fail closed before a feedback server becomes usable.

`eval live --capture-context-package-timings` opts into a sanitized sideband
record for each context-package call. Records contain only fixed stage and
operation names, elapsed times, counts, and success state. They exclude queries,
paths, content, credentials, environment values, and repository, snapshot, or
node identifiers. The evaluator aggregates measured calls by case and excludes
warm-ups from the reported p50s. This instrumentation does not alter MCP tool
arguments, JSON responses, agent text, ranking, safety behavior, or character
budgets.

`eval agent --preflight-only --configured-plan PLAN
--max-reported-tokens CAP` adds the paired-evaluation gate without invoking a
model. A configured suite must pin its repository commit. Before repository
preparation or any model call, the preflight requires the selected runner to
declare a hard reported-token cap using accounting identity
`input-output-reasoning-v1`. Reported tokens add `input_tokens`,
`output_tokens`, and `reasoning_output_tokens`; `cached_input_tokens` is a
subset of `input_tokens` and is not added again. Missing, negative, non-integer,
or internally inconsistent usage fails closed.

Each scheduled execution receives the campaign's remaining allowance. A runner
claiming the capability must guarantee that the complete invocation, including
any internal provider activity, cannot report more than that allowance. The
evaluator stops before the next execution when the allowance reaches zero,
stops after an incomplete execution, never retries automatically, and records
the ceiling, aggregate, remainder, accounting identity, stop state, and
per-execution limit. A runner that exceeds its declared limit is an
infrastructure failure.

The default `--runner codex` reports usage only after completion and the current
Codex CLI has no compatible hard-limit option, so both `--preflight-only` and
model-backed agent evaluation refuse it before any model call. Post-run
observation, a fixed repetition count, and operator intent are not enforcement
substitutes.

Explicit `--runner capped-codex` starts a new loopback Responses proxy for each
agent execution. It counts the complete submitted input through
`/responses/input_tokens`, reserves input plus twice the admitted
generated-token envelope before forwarding, clamps `max_output_tokens`, and
sets Codex custom provider request and SSE retries to zero. The doubled envelope
is required because the committed accounting adds reasoning output to Codex's
already-inclusive output count. Only foreground `/responses` calls
with local function/custom tools are supported. Background calls, compaction,
other or cost-bearing endpoints and tools, insufficient allowance, missing
usage, duplicate or declared retries, and accounting disagreement fail closed.
Interrupted responses retain their reservations. Completion additionally
requires exact agreement between cumulative proxy usage and Codex final usage.
The execution report's `hard_cap_ledger` contains sanitized totals, request
counts, retry settings, and fixed failures; request content, credentials, and
provider response text are excluded.

The runner also requires the selected model to exist in the chosen Codex
executable's bundled catalog. It writes that one exact entry to an ephemeral
`model_catalog_json` so shell and MCP tool definitions remain model-compatible,
then removes it after the execution. The proxy answers Codex's cost-free model
discovery locally and never forwards it upstream.

After a compatible runner passes that capability gate, the remaining configured
preflight still requires clean target and CodeMesh checkouts, exact
source/index/plan/binding agreement, committed guidance, the normal four-tool
surface, a passing context probe, and a passing wrong-checkout rejection probe.
Its report retains hashes and stable identities rather than raw guidance or MCP
payloads.

Configured suites may declare `baseline_mcp_servers`. Those servers must exist
in the reviewed checkout-local configuration and are supplied identically to
control and treatment; treatment then adds CodeMesh. Inline environment values
are rejected for baseline servers, while declared `env_vars` names may be
forwarded. Spontaneous and evaluator-assisted suites retain their historical
isolated diagnostic-profile behavior.

`feedback record` continues to write `codemesh-feedback/v1` packets only to an ignored
`.codemesh-feedback/` outbox inside the checkout. Linked outboxes are rejected,
and packet files are created exclusively so an existing file or link cannot be
overwritten. Packets contain commit, dirty-state hash, binding,
snapshot, languages, parser profile, categorized paths, validation result,
confidence, and bounded sanitized descriptions; they exclude raw prompts, MCP
payloads, source excerpts, and environment values. `feedback validate` checks
the strict schema and content id. `feedback summarize` groups validated packets,
preserves exact provenance, prioritizes open failures, and recognizes passing
rechecks that explicitly supersede earlier failures.

`feedback session plan` creates a reviewable
`codemesh-development-feedback-session-plan/v1` artifact for an exact CodeMesh
checkout and one or more client checkouts. The plan pins an immutable manifest,
expiry of no more than seven days, exact profile tool lists, local/provider-free
declarations, reporter identities, and packet, request, text, and path bounds.
It verifies that every client outbox is ignored and unlinked.
`feedback session activate` requires the reviewed plan hash and creates the
manifest exclusively. `inspect` reports bounded status without client roots;
`revoke` requires the manifest hash and creates a separate immutable revocation
record. Neither close nor expiry removes retained packets.

`codemesh_record_feedback` accepts only bounded observation fields. It fixes
classification to `diagnostic` and derives the session, reporter role,
repository Git state, binding, snapshot/parser availability, and CodeMesh Git
state on the server. Accepted snapshot/parser provenance comes from the most
recent successful status or context-package call in the same stdio process;
the recording endpoint does not issue a new store request. Setup, binding, and freshness failures may record a
bounded unavailable-provenance code. Content, ranking, language, relationship,
budget, and validation reports require an accepted fresh snapshot and parser
provenance. The resulting strict `codemesh-feedback/v2` packet is
content-addressed and append-only. Validation and summarization accept both v1
and v2.

The maintainer tools enumerate only roots in the active manifest. By default
they expose only v2 packets from that session; `include_legacy=true` may expose
valid v1 packets as `legacy_unscoped`. Resolution preparation validates an
agent-authored draft and returns a stable hash with
`human_review_required=true` and `human_approved=false`. It never writes the
plan, changes CodeMesh, records approval, invokes a provider, or transmits
feedback.

A v2 packet may name superseded feedback only when it is a passing recheck.
Maintainer status derives an earlier report as resolved only when the recheck
comes from the same checkout and matches its issue category and task family.

## .NET Client

Use `CodeMesh.Control.AgentAccess.AgentAccessClient` for typed .NET calls:

```csharp
using CodeMesh.Control.AgentAccess;
using CodeMesh.Domain.Contracts;

using var client = new AgentAccessClient(new AgentAccessClientOptions("http://127.0.0.1:8088"));

var result = await client.SearchContextAsync(new AgentContextQuery(
    "DownloadAsync",
    RepositoryId: "youtube_downloader",
    Kinds: ["Method"],
    IncludeContextRelationships: true));
```

The client wraps context search, context package, symbol search, node lookup, neighbor lookup, repository listing, repository lookup/deletion, summary coverage, and ingestion-run listing.
It also exposes repository status and freshness through `GetRepositoryStatusAsync`.
