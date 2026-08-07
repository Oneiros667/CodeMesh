# Agent Prompts

These prompts are examples for agents using CodeMesh through MCP or REST. They are phrased as tasks that map to existing or planned CodeMesh tools.

The first prompts cover the initial C#/.NET product wedge: implementation
discovery, likely impact, validation selection, and freshness. Prompts for
broader runtime or SDLC intelligence are explicitly deferred examples.

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
Use CodeMesh to build an agent context package for changing repository
deletion behavior. Include source spans, callers, callees, reads, writes, and
tests. Treat relationships as navigation evidence and identify the source that
supports important conclusions.
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
Use CodeMesh to find tests related to repository cleanup. Return the test names,
the implementation nodes they exercise, and the documented validation command.
```

Likely tools:

- `codemesh_search_context`
- `codemesh_search_symbols`
- `codemesh_get_context_package`

## Trace Likely Change Impact

```text
Use CodeMesh to find the C# implementation of repository cleanup, inspect its
callers and store dependencies, and identify the tests most likely to validate a
change. Verify important relationship conclusions against the returned source
spans.
```

Likely tools:

- `codemesh_search_symbols`
- `codemesh_get_neighbors`
- `codemesh_get_context_package`

## Deferred Runtime Impact Prompt

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
