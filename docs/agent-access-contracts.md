# Agent Access Contracts

Agent Access exposes the same read surface through REST, MCP tools, and the typed .NET client in `CodeMesh.Control.AgentAccess.AgentAccessClient`.

It also serves a local read-only web UI at `/ui` for humans to inspect service health, repositories, repository freshness, ingestion runs, and context search results. The UI reuses the REST read store and is not a separate write surface.

Source-of-truth implementations:

- REST models: `agent-access/codemesh_agent_access/models.py`
- REST routes: `agent-access/codemesh_agent_access/rest.py`
- Local UI routes: `agent-access/codemesh_agent_access/web.py`
- MCP manifest: `agent-access/codemesh_agent_access/mcp.py`
- .NET contracts: `src/CodeMesh.Domain/Contracts/AgentAccessContracts.cs`

## Common Controls

Most read calls accept `repository_id`. This can be either the repository hash id or the generated alias. Agent Access resolves aliases before querying stores. Repository lookup accepts URL-encoded path characters in `repository_id`; generated aliases remain slash-free.

Filters are exact-match string filters. They can match top-level node fields or metadata fields. `kinds` filters by CodeMesh node kind names such as `Method`, `Class`, `File`, or `Declaration`.

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

- `query`: the resolved query. If an alias was supplied, `repository_id` is rewritten to the hash id.
- `hits`: ranked `ContextHit` items.
- `diagnostics`: search execution metadata.
- `generated_at`: UTC timestamp.

`ContextHit` fields:

- `node_id`, `stable_key`, `kind`, `file_path`, `start_line`, `end_line`, `score`.
- `repository_id` and `content_hash` when available.
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

Agent Access merges vector hits, lexical graph hits, and MongoDB generated-summary hits, then dedupes by `node_id`.

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

Freshness fields include `indexed_commit`, `current_commit`, `current_branch`, `working_tree_dirty`, `is_stale`, `status`, and `detail` when available. If ingestion has not stored an indexed commit yet, `status` is `unknown` and `is_stale` is `null`; agents should treat the response as a useful warning rather than proof that the index is fresh.

Refresh fields include `status`, `is_running`, `changed`, `latest_run_id`, `stage`, `started_at`, `finished_at`, `diagnostic_count`, `error_diagnostic_count`, `warning_diagnostic_count`, `stats`, `detail`, and `recommended_action` when available. `status` is derived from the latest ingestion run and can be `no_run`, `running`, `completed`, `skipped`, `failed`, `dry_run`, or `unknown`.

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

`DELETE /repositories/{repository_id}` accepts a repository hash id or alias, resolves it through the registry, and removes that repository from the graph, content, vector, summary, run, and repository registry stores.

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

`ContextPackageQuery` fields:

- Core controls: `query`, `repository_id`, `limit`, `kinds`, `filters`, `vector`, `context_depth`.
- Content controls: `max_characters`, `include_content`.
- Relationship controls: `include_relationships`, `relationship_limit`, `caller_limit`, `callee_limit`, `read_limit`, `write_limit`, `contains_limit`, `definition_limit`, `uses_type_limit`.
- Registry control: `include_repository`.

`ContextPackageResponse` includes:

- `repository`: repository metadata when requested and available.
- `latest_run`: latest ingestion run metadata when requested and available.
- `items`: package items built from context hits.
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

MCP `codemesh_get_context_package` also accepts `output_format = "agent"`. In that mode the tool response includes `agent_text`, a concise text brief generated from the structured package. The brief includes each item's file span, node id, stable key, repository id, content hash, score, rank, and rationale details. It uses the package `max_characters` budget and adds a truncation marker when capped.

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

MCP tool names:

- `codemesh_status`
- `codemesh_get_tool_guidance`
- `codemesh_search_context`
- `codemesh_get_context_package`
- `codemesh_search_symbols`
- `codemesh_get_node`
- `codemesh_get_neighbors`
- `codemesh_list_repositories`
- `codemesh_get_repository`
- `codemesh_get_repository_status`
- `codemesh_delete_repository`
- `codemesh_get_summary_coverage`
- `codemesh_list_ingestion_runs`

`codemesh_get_tool_guidance` accepts optional `task` text and returns ranked workflows with recommended tool steps. Use it when an agent has not yet decided whether to search context, inspect freshness, look up a symbol, fetch neighbors, or build a package.

`codemesh_delete_repository` requires `repository_id` and a deliberate `confirm = true` argument before it will call the destructive cleanup path. Without confirmation it returns a failed tool result and leaves stores unchanged.

The manifest can be printed with:

```powershell
cd agent-access
uv run python -m codemesh_agent_access mcp-manifest
```

The manifest is covered by `agent-access/tests/test_mcp_contract.py`.

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
