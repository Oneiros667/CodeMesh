# Testing Guide

Use this guide to choose the right verification path after CodeMesh changes.

## Default Test Commands

From the repository root:

```powershell
dotnet run --project tests/CodeMesh.Tests
```

From `agent-access`:

```powershell
uv run pytest
```

Run both after most implementation changes.

## .NET Tests

The .NET test harness covers:

- Domain utilities.
- Environment loading.
- Agent Access contract mapping.
- Agent Access .NET client behavior.
- Ingestion orchestration.
- Incremental writes and cleanup.
- Embedding and summary providers.
- MongoDB, Neo4j, and Qdrant storage adapters.
- C# parser behavior.
- Optional configured sample parsing.

Some tests skip when required live services or sample paths are unavailable.

## Python Tests

The Python tests under `agent-access/tests` cover:

- CLI output.
- Context ranking.
- Formatting.
- MCP contracts.
- REST contracts.
- Store read components.

Use these tests when changing `agent-access/codemesh_agent_access`.

## End-To-End Smoke

Use the smoke script when a change affects live service wiring, Docker Compose behavior, repository lifecycle, cleanup, REST endpoints, or Agent Access integration.

```powershell
.\scripts\e2e-smoke.ps1
```

Common variants:

```powershell
.\scripts\e2e-smoke.ps1 -FixtureOnly
.\scripts\e2e-smoke.ps1 -UseConfiguredSample
.\scripts\e2e-smoke.ps1 -IncludeEmbeddings -EmbeddingProvider ollama -EmbeddingModel nomic-embed-text-v2-moe:latest
```

## Documentation-Only Changes

Tests are usually not required for documentation-only changes. Still check formatting manually and make sure links point to existing files.

## Interpreting Results

- Passing tests indicate the local code path is healthy for covered behavior.
- Skipped integration tests usually mean a store or sample repository is unavailable.
- Failed integration tests may be service setup issues or code regressions; check service health before changing code.

## Useful Health Checks

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
docker compose ps
Invoke-RestMethod http://127.0.0.1:8088/health
```
