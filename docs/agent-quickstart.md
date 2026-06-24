# Agent Quickstart

This page is the preferred starting point for AI agents working in the CodeMesh repository.

## Read Order

1. `Agents.md` for repository operating rules and local environment assumptions.
2. `README.md` for current product purpose, commands, services, and examples.
3. `docs/agent-access-contracts.md` when changing REST, MCP, CLI, or .NET Agent Access behavior.
4. `docs/next-steps.md` when choosing near-term implementation work.
5. `docs/sdlc-roadmap.md` when planning broader SDLC intelligence features.

Use `docs/mcp-setup.md` and `docs/self-analysis.md` when configuring CodeMesh as an MCP service or dogfooding it against this repository.

## What CodeMesh Is

CodeMesh is a local-first code intelligence substrate for AI coding agents. It ingests repositories into graph, content, vector, summary, and registry stores, then exposes agent-ready context through REST, MCP tools, CLI commands, and a .NET client.

## Repository Shape

- `src/CodeMesh.Domain`: shared contracts, graph types, health contracts, and utility records.
- `src/CodeMesh.Ingestion`: parsing orchestration, repository cleanup, embedding, and summary generation.
- `src/CodeMesh.Parser.CSharp`: C# parser worker backed by Roslyn.
- `src/CodeMesh.Parser.Deployment`: local deployment parser for Dockerfiles, Compose files, stages, services, and service dependencies.
- `src/CodeMesh.Parser.Markdown`: local Markdown parser for documents, sections, anchors, and heading containment.
- `src/CodeMesh.Parser.Python`: local Python parser for files, classes, functions, async functions, and containment.
- `src/CodeMesh.Storage`: Neo4j, MongoDB, Qdrant, and in-memory storage adapters.
- `src/CodeMesh.Control`: status checks, environment loading, and Agent Access .NET client.
- `src/CodeMesh.Cli`: command-line entry point.
- `agent-access`: Python REST, MCP, CLI, ranking, formatting, and store read paths.
- `tests/CodeMesh.Tests`: .NET integration and contract test harness.
- `agent-access/tests`: Python unit and contract tests.

## Default Verification

Run these after implementation changes unless the task is documentation-only:

```powershell
dotnet run --project tests/CodeMesh.Tests
cd agent-access
uv run pytest
```

Use `.\scripts\e2e-smoke.ps1` when a change affects live store wiring, Docker services, ingestion cleanup, Agent Access REST behavior, or end-to-end repository lifecycle.

## Agent Working Rules

- Prefer small, scoped changes that match existing patterns.
- Treat `README.md`, `docs/agent-access-contracts.md`, tests, and source contracts as the source of current behavior.
- Treat `docs/next-steps.md` and `docs/sdlc-roadmap.md` as planning context, not implemented behavior.
- Do not print `.env` values, secrets, tokens, keys, certificates, or local credentials in responses.
- Avoid broad refactors unless the current task requires them.
- If stores are unavailable, distinguish skipped integration checks from failed code behavior.

## Common Task Routing

- REST, MCP, Python CLI, ranking, formatting, or context packages: start in `agent-access/codemesh_agent_access`.
- .NET Agent Access client contracts: start in `src/CodeMesh.Domain/Contracts` and `src/CodeMesh.Control/AgentAccess`.
- Ingestion behavior: start in `src/CodeMesh.Ingestion`.
- C# parse graph behavior: start in `src/CodeMesh.Parser.CSharp`.
- Dockerfile and Compose parse graph behavior: start in `src/CodeMesh.Parser.Deployment`.
- Store writes and cleanup: start in `src/CodeMesh.Storage`.
- Product direction or future features: start in `docs/next-steps.md` and `docs/sdlc-roadmap.md`.
