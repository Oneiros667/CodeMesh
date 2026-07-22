# AGENTS.md

## Codebase Memory MCP

**MANDATORY: use Codebase Memory MCP graph tools FIRST — before reading files or making code changes.**

This rule applies to every request involving this codebase.

Always call `list_projects` first when you do not already know the project name, then use the `display_name` or exact `name` returned by that tool.

```json
// Step 0 — discover project names
mcp_codebase-memo_list_projects()

// Step 1 — use the project identifier returned above
mcp_codebase-memo_get_architecture({ "project": "<display_name>" })
```

### Workflow

1. Call `list_projects` to discover the correct project name.
2. Call `get_architecture(project)` to understand the codebase structure.
3. Use `search_graph` to find relevant symbols, `trace_call_path` for call chains.
4. Use `get_code_snippet` to read specific function implementations.
5. Only use `read_file` when you need exact raw content to edit a specific line.

### Available Tools (14 MCP tools)

**Indexing:**
- `index_repository(repo_path)` — Index a repository into the knowledge graph
- `list_projects` — List all indexed projects with node/edge counts
- `delete_project(project)` — Remove a project and all its graph data
- `index_status(project)` — Check indexing status

**Querying:**
- `search_graph(name_pattern, name_scope, label, file_pattern, exclude_file_pattern)` — Structured search by label, name/qualified_name, include/exclude file globs
- `trace_call_path(function_name, direction, depth)` — BFS call chain traversal
- `detect_changes(project)` — Map git diff to affected symbols + risk
- `query_graph(query)` — Execute Cypher-like graph queries (read-only)
- `get_graph_schema(project)` — Node/edge counts, relationship patterns
- `get_code_snippet(qualified_name)` — Read source code for a function
- `get_architecture(project)` — Codebase overview: languages, packages, routes, hotspots
- `search_code(pattern, project)` — Grep-like text search within indexed files
- `manage_adr(action)` — CRUD for Architecture Decision Records
- `ingest_traces(traces)` — Ingest runtime traces to validate HTTP edges

## Project Context

Before planning larger CodeMesh work, review these repository notes:

- `docs/agent-quickstart.md` is the preferred starting point for AI agents working in this repository.
- `docs/architecture.md` explains the current component boundaries and data flow.
- `docs/testing.md` explains verification commands and when to use the end-to-end smoke script.
- `docs/mcp-setup.md` explains how to run CodeMesh as an MCP service.
- `docs/self-analysis.md` explains how to index and query CodeMesh itself.
- `docs/security-and-redaction.md` records secret-handling expectations for agent-facing context.
- `docs/agent-prompts.md` contains example prompts for agents using CodeMesh through MCP.
- `docs/next-steps.md` tracks the prioritized backlog for making CodeMesh effective as an MCP service for AI agents.
- `docs/sdlc-roadmap.md` tracks longer-term SDLC intelligence goals beyond implementation-code indexing.

Treat `docs/next-steps.md` and `docs/sdlc-roadmap.md` as planning context, not implemented behavior.

## Agent Defaults

- Do not print `.env` contents, credentials, tokens, private keys, certificates, or local secret values.
- For implementation changes, run `dotnet run --project tests/CodeMesh.Tests` from the repo root unless clearly irrelevant.
- For Python Agent Access changes, also run `uv run pytest` from `agent-access`.
- Use `.\scripts\e2e-smoke.ps1` when changes affect live store wiring, Docker services, repository lifecycle, cleanup, or Agent Access integration.
- Documentation-only changes usually do not require tests; check links and formatting manually.

## Environment

This repo is usually worked on from JetBrains Rider on Windows with PowerShell.

Available CLI tools:

- `rg`
- `git`
- `dotnet` with .NET 10 SDK
- `python` 3.14
- `uv`
- `ruff`
- `pytest`
- `jq`
- `gh`
- `docker`
- `docker compose`
- `7z`

Notes:

- If a newly installed command is not visible, refresh PATH from persisted values:

  ```powershell
  $env:Path = "$([Environment]::GetEnvironmentVariable('Path', 'Machine'));$([Environment]::GetEnvironmentVariable('Path', 'User'))"
  ```
