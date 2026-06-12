# CodeMesh Next Steps For Effective MCP Agent Use

CodeMesh already has an Agent Access surface with REST, MCP tools, CLI commands, repository registry records, context search, context packages, symbol search, node lookup, graph neighbors, summaries, and ingestion history.

This document prioritizes the features that would make CodeMesh effective as an MCP service used by AI agents, including agents analyzing CodeMesh itself.

## Current Project State Review

Review date: 2026-06-12.

Recent completed work:

- Local-first MCP readiness: self-ingestion, MCP setup docs, repository freshness/status, redaction, Python parsing, and Markdown parsing are implemented.
- Human inspection: Agent Access serves a local read-only UI at `/ui` for service health, repositories, repository status, ingestion runs, and context search.
- Agent packaging: `agent_text` context packages include stable item metadata, rationale, snippets before relationships, and budget-aware truncation.
- Agent guidance: `codemesh_get_tool_guidance` and `uv run python -m codemesh_agent_access tool-guidance "<task>"` recommend tool workflows for common agent tasks.
- Incremental ingestion internals exist for graph, content, vectors, and summaries, including skipped unchanged records and stale cleanup.

Current state:

- P0 baseline items are implemented enough for dependable local MCP use.
- P1 agent-usefulness items are implemented enough for active dogfooding, though Python and Markdown relationship richness can still improve.
- The largest remaining gap is operational freshness: agents can check stale status, and ingestion is incremental internally, but there is not yet a simple refresh/watch workflow that keeps the current repository current during normal development.

Current priority judgment:

1. Build an agent-friendly refresh workflow on top of existing incremental ingestion internals.
2. Start runtime/deployment artifact ingestion with Dockerfile and Docker Compose before Helm.
3. Add test and validation context so context packages can recommend relevant checks.
4. Add an MCP evaluation suite to prevent regressions in search, packages, freshness, and redaction.
5. Deepen parser relationships for Python imports/routes/MCP handlers and Markdown cross-links.
6. Strengthen secret-file exclusion and configurable allow/deny policy before broad SDLC artifact ingestion.

## P0 - Required For A Dependable MCP Baseline

### 1. Self-Ingestion Workflow

Add a first-class command or documented preset for indexing the CodeMesh repository itself.

Current implementation:

- `dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings`
- `dotnet run --project src/CodeMesh.Cli -- self ingest --dry-run --skip-embeddings`
- `dotnet run --project src/CodeMesh.Cli -- self smoke --skip-embeddings`

Expected outcome:

- A repeatable `codemesh self ingest` or equivalent documented command.
- Defaults for `D:\source\repos\CodeMesh` and `CodeMesh.sln` when run from the repository root.
- Clear support for dry-run, no-embedding, embedding, and summary modes.
- A smoke check that verifies CodeMesh appears in `repos list` and can answer at least one MCP context query.

Why it matters:

Dogfooding CodeMesh against itself is the fastest way to expose weak context packaging, stale index problems, missing parser coverage, and awkward MCP tool contracts.

### 2. MCP Client Configuration Guide

Add ready-to-use MCP configuration examples for common agent hosts.

Current implementation:

- `docs/mcp-setup.md` documents local stdio MCP startup through `uv run python -m codemesh_agent_access mcp`.
- It includes command/args examples, `mcpServers` JSON, a PowerShell wrapper for clients without `cwd`, required environment variables, model-provider variants, and troubleshooting.

Expected outcome:

- A doc covering how to run `codemesh_agent_access mcp` from the local `agent-access` project.
- Example configuration for stdio-based MCP clients.
- Required environment variables listed in one place.
- A troubleshooting section for store connectivity, Python environment issues, and model-provider failures.

Why it matters:

The service is only useful to agents if it is easy to attach reliably. MCP setup should not require reading implementation files.

### 3. Index Freshness And Repository Status

Expose freshness diagnostics directly through MCP.

Current implementation:

- `GET /repositories/{repository_id}/status` returns registry metadata, latest run, counts, summary coverage, and local git freshness diagnostics.
- `codemesh_get_repository_status` exposes the same status bundle through MCP.
- `uv run python -m codemesh_agent_access repo-status <repository-id-or-alias>` exposes it through the Python CLI.
- `AgentAccessClient.GetRepositoryStatusAsync` exposes it to .NET callers.
- Current freshness is conservative: when ingestion has not stored an indexed commit, status is `unknown` even if local git state is readable.

Expected outcome:

- A tool or status field that reports latest ingestion run, indexed commit SHA when available, current working tree commit when available, and whether the index appears stale.
- Repository-level counts for graph nodes, content documents, vectors, and summaries.
- Clear diagnostics when vectors or summaries are missing for a repository.

Why it matters:

Agents need to know whether returned context reflects the code they are editing. Stale context is worse than no context when making changes.

### 4. Secret And Sensitive-File Redaction

Add explicit guardrails before broadening MCP access to repository content.

Current implementation:

- Ingestion redacts sensitive-looking values before persistence, embeddings, and summaries.
- Redacted content is stored under a new content hash, and graph nodes are remapped to that hash.
- Ingestion emits `CMSEC001` when redaction changes content.
- Current redaction covers private key blocks, environment-style key/value secrets, JSON secret values, C# string assignments with sensitive names, and connection-string password fragments.
- Known secret-file exclusion and configurable allow/deny lists remain future work, especially for Markdown, deployment, and SDLC artifact ingestion.

Expected outcome:

- Default exclusion or redaction for `.env`, secret files, private keys, tokens, certificates, and common credential formats.
- A documented allowlist/denylist model for ingestion.
- MCP responses that never emit known secret values.
- Tests covering representative secret patterns.

Why it matters:

An MCP context service will put repository content directly in front of agents. Redaction needs to be boring, predictable, and on by default.

## P1 - High-Impact Agent Usefulness

### 5. Python Parser Support

Add structured Python ingestion for the `agent-access` project.

Current implementation:

- `src/CodeMesh.Parser.Python` parses `.py` files locally.
- It emits file, class, method/function, async function, and containment graph records.
- `dotnet run --project src/CodeMesh.Cli -- ingest --root .\agent-access --language python --dry-run --skip-embeddings` validates the Agent Access tree.
- Current parser scope is syntax-light and indentation-based; import, call, route-handler, MCP-handler, and test-coverage relationships remain future work.

Expected outcome:

- Python modules, classes, functions, imports, routes, CLI commands, MCP tools, and tests represented as typed graph nodes.
- Relationships for imports, calls where practical, route handlers, tool handlers, and test coverage links.
- CodeMesh self-analysis covers both the .NET ingestion/control code and the Python Agent Access service.

Why it matters:

CodeMesh currently includes important Python implementation code. Without Python parsing, self-analysis is incomplete and agents miss the MCP service internals.

### 6. Documentation And Markdown Ingestion

Index repository documentation as first-class context.

Current implementation:

- `src/CodeMesh.Parser.Markdown` parses `.md` and `.markdown` files locally.
- It emits `Document` and `Section` nodes, heading anchors, heading levels, source spans, and `Contains` relationships.
- `dotnet run --project src/CodeMesh.Cli -- ingest --root . --language markdown --dry-run --skip-embeddings` validates repository documentation parsing.
- Current parser scope is Markdown structure only; cross-links from docs to commands, endpoints, tools, source files, and projects remain future work.

Expected outcome:

- README, roadmap, next-step, contract, and architecture docs ingested as document nodes with headings, anchors, and source spans.
- Relationships from docs to referenced projects, commands, endpoints, tools, and files where detectable.
- Context packages that can include both implementation code and relevant documentation.

Why it matters:

Agents need project intent, usage contracts, and operational instructions, not only code symbols.

### 7. Context Package Quality Gates

Harden context packages for direct use in agent prompts.

Current implementation:

- MCP `output_format = "agent"` and CLI `--output agent` produce compact `agent_text`.
- Agent text now includes each item's file span, node id, stable key, repository id, content hash, score, rank, and rationale details.
- Agent text applies the context package `max_characters` budget for MCP and CLI output and emits an explicit truncation marker when capped.
- Snippets are emitted before relationship detail so the most directly actionable content is preserved first under tight budgets.

Expected outcome:

- Stable, compact `agent_text` output optimized for MCP callers.
- Clear file paths, line ranges, node ids, repository ids, and content hashes on every item.
- Budget controls that preserve high-value snippets before lower-value relationship detail.
- Rationale explaining why each item was included.
- Tests that snapshot package shape for representative queries.

Why it matters:

Search is useful for discovery, but agents need packaged context that can be trusted and pasted into reasoning without manual cleanup.

### 8. Local Web Inspection UI

Add a local, read-only web interface for humans to inspect CodeMesh state without switching between CLI, REST JSON, and MCP clients.

Current implementation:

- `/ui` shows service health, repository summaries, recent ingestion runs, and a search form.
- `/ui/repositories` lists indexed repositories.
- `/ui/repositories/{repository_id}` shows repository freshness, counts, metadata, and recent runs.
- `/ui/runs` shows ingestion history with optional repository filtering.
- `/ui/search` provides read-only context search over the existing Agent Access store.

Expected outcome:

- A local-first dashboard served by the Agent Access FastAPI service.
- Clear visibility into ingestion state, freshness, repository counts, and recent failures.
- Search and inspection workflows that help humans validate what agents will see through MCP.
- Future write actions, such as triggering ingestion or deleting repositories, gated behind explicit local controls and stronger access rules if exposed remotely.

Why it matters:

Agents need reliable context, and humans need a quick way to audit whether that context is fresh, complete, and safe before delegating work.

### 9. Query Planning And Tool Guidance

Help agents choose the right CodeMesh tool for a task.

Current implementation:

- `codemesh_get_tool_guidance` recommends tool workflows for optional natural-language task text.
- `uv run python -m codemesh_agent_access tool-guidance "<task>"` exposes the same guidance through the Python CLI.
- The MCP manifest descriptions now say when to use search, context packages, symbol search, node lookup, neighbors, repository listing, freshness status, and ingestion runs.
- Current guidance covers freshness checks, implementation discovery, symbol lookup, relationship inspection, agent context package preparation, operational checks, and explicit repository deletion.

Expected outcome:

- A lightweight MCP tool or doc section that describes when to use context search, context package, symbol search, node lookup, neighbors, repository list, and ingestion runs.
- Better tool descriptions in the MCP manifest.
- Example task-to-tool mappings, such as "find implementation", "inspect callers", "check freshness", and "summarize a component".

Why it matters:

MCP tools are most effective when agents can select them without trial and error.

## P2 - Production-Grade MCP Reliability

### 10. Watch Or Incremental Refresh Mode

Add a convenient way to keep an indexed repository close to current.

Current implementation:

- Ingestion already performs incremental graph, content, vector, and summary writes where supported.
- Existing tests cover unchanged-record skips, forced embedding rebuilds, unchanged-summary skips, and stale cleanup.
- Ingestion result stats report parsed, written, skipped, and summary counts.
- There is no first-class `refresh` command, watch loop, or Agent Access-visible refresh activity state yet.

Expected outcome:

- A cheap `refresh` command for the current repository that reuses existing incremental ingestion behavior.
- A watch command after refresh semantics are stable.
- Incremental parse/write behavior that is fast enough for normal development loops.
- Status diagnostics showing when a refresh is running, completed, failed, or skipped.

Why it matters:

Agents work against changing files. Manual full ingestion before every useful query is too heavy.

### 11. Runtime And Deployment Artifact Ingestion

Implement the first slice of the SDLC roadmap for production-aware context.

Current implementation:

- `docs/sdlc-roadmap.md` defines target runtime/deployment artifacts and graph concepts.
- CodeMesh has Docker Compose and Dockerfile assets for its own runtime, but they are not yet parsed as first-class graph nodes.
- Existing Markdown ingestion can index deployment docs structurally, but it does not extract Docker, Compose, Kubernetes, or Helm semantics.

Expected outcome:

- Structured ingestion for Dockerfiles and Docker Compose first, then Helm charts and Kubernetes manifests.
- Nodes and relationships for images, services, ports, environment variables, volumes, deployments, services, ingress, and dependencies.
- Agent queries that connect code to runtime configuration and deployment files.

Why it matters:

Many agent tasks involve changing behavior that is controlled by container, environment, or deployment configuration.

### 12. Test And Validation Context

Connect implementation nodes to the tests and commands that validate them.

Current implementation:

- `docs/testing.md` documents the main .NET, Python, and smoke verification commands.
- The repository has broad .NET and Python tests, but test files and validation commands are not represented as graph context.
- Context packages do not yet recommend validation commands for touched code.

Expected outcome:

- Test projects, test files, test cases, and test commands represented in the graph.
- Relationships between tests and implementation nodes where naming, references, or coverage data supports it.
- MCP context packages that recommend relevant validation commands.

Why it matters:

Agents should not only modify code; they should know how to verify the change.

### 13. Evaluation Suite For MCP Use Cases

Add repeatable scenarios that measure whether CodeMesh helps agents.

Current implementation:

- Unit and contract tests cover store behavior, ranking, MCP contracts, REST contracts, CLI output, parsers, redaction, and ingestion.
- There is no small benchmark set that asserts minimum useful results for representative agent tasks against CodeMesh itself.

Expected outcome:

- A small set of benchmark queries against CodeMesh itself and one sample repository.
- Expected tool behavior and minimum useful results for each scenario.
- Regression tests for search ranking, package content, freshness diagnostics, and redaction.

Why it matters:

Agent usefulness is easy to degrade accidentally. Evaluation keeps the MCP service focused on practical outcomes.

## P3 - Broader SDLC Intelligence

### 14. API Contract And Database Migration Ingestion

Add structured parsers for compatibility-critical artifacts.

Expected outcome:

- OpenAPI, AsyncAPI, GraphQL, protobuf, and migration files represented as typed nodes.
- Relationships from handlers, clients, models, and migrations to public contracts and persisted data structures.

Why it matters:

Agents need to understand compatibility boundaries before changing public APIs or persisted data.

### 15. Observability And Runbook Context

Index operational diagnostics and support artifacts.

Expected outcome:

- Metrics, alerts, dashboards, runbooks, and SLOs represented as searchable context.
- Relationships from services or code paths to operational signals where detectable.

Why it matters:

Production-aware agents should know how a change is monitored and how failures are diagnosed.

### 16. Ownership And Review Metadata

Index collaboration rules that shape safe changes.

Expected outcome:

- CODEOWNERS, contribution docs, PR templates, and review conventions represented as context.
- Agent packages can include relevant ownership and review expectations for a touched area.

Why it matters:

Useful agents need to follow local engineering process, not only compile code.

## Near-Term Recommended Order

1. Add a `refresh` command or documented preset for the current repository using existing incremental ingestion internals.
2. Surface refresh activity and last refresh outcome through repository status and the local UI.
3. Start runtime/deployment ingestion with Dockerfile and Docker Compose.
4. Add test and validation context, including graph nodes for test files/cases and context-package validation recommendations.
5. Add an MCP evaluation suite with representative self-analysis scenarios and minimum useful-result assertions.
6. Deepen Python and Markdown relationship extraction where it improves self-analysis and MCP packages.
7. Add configurable sensitive-file exclusion and allow/deny policy before broadening SDLC artifact ingestion.
8. Continue runtime/deployment ingestion into Helm and Kubernetes manifests.

This order keeps CodeMesh useful as a local MCP service while moving from basic context access toward production-aware, validation-aware agent workflows.
