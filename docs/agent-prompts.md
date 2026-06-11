# Agent Prompts

These prompts are examples for agents using CodeMesh through MCP or REST. They are phrased as tasks that map to existing or planned CodeMesh tools.

## Find Implementation Context

```text
Use CodeMesh to search context for the ingestion path that writes repository registry records. Return the most relevant files, node ids, and line ranges.
```

Likely tools:

- `codemesh_search_context`
- `codemesh_get_context_package`

## Inspect A Symbol

```text
Use CodeMesh to find the AgentAccessClient symbol, then inspect its neighboring relationships and summarize what REST endpoints it wraps.
```

Likely tools:

- `codemesh_search_symbols`
- `codemesh_get_neighbors`
- `codemesh_get_context_package`

## Package Context For A Change

```text
Use CodeMesh to build an agent context package for changing repository deletion behavior. Include callers, callees, reads, writes, tests, and relevant summaries when available.
```

Likely tools:

- `codemesh_get_context_package`
- `codemesh_search_symbols`
- `codemesh_list_ingestion_runs`

## Check Repository Freshness

```text
Use CodeMesh to list indexed repositories and recent ingestion runs for the CodeMesh repository. Report whether the index appears recent enough for implementation work.
```

Likely tools:

- `codemesh_list_repositories`
- `codemesh_list_ingestion_runs`
- `codemesh_status`
- `codemesh_get_repository_status`

## Understand A Component

```text
Use CodeMesh to explain how context package generation works. Include the ranking inputs, store reads, response shape, and tests that cover the behavior.
```

Likely tools:

- `codemesh_search_context`
- `codemesh_get_context_package`
- `codemesh_search_symbols`

## Investigate Validation

```text
Use CodeMesh to find tests related to summary coverage and summary ingestion stats. Return the test names and the implementation nodes they exercise.
```

Likely tools:

- `codemesh_search_context`
- `codemesh_search_symbols`
- `codemesh_get_context_package`

## Runtime Impact Prompt

This prompt depends on future deployment artifact ingestion from `docs/sdlc-roadmap.md`.

```text
Use CodeMesh to identify which Docker, Compose, Helm, and environment configuration artifacts are affected by changing this service port.
```

Likely tools:

- `codemesh_search_context`
- `codemesh_get_context_package`
- deployment-artifact tools when implemented

## Prompt Quality Rules

- Include the repository alias when known.
- Ask for node ids, file paths, and line ranges.
- Ask for context packages when implementation work is likely.
- Ask for freshness and recent ingestion runs before trusting context for edits.
- Ask for relationships when call flow or ownership matters.
