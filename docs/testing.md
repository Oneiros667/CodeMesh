# Testing Guide

Use this guide to choose the right verification path after CodeMesh changes.

## Default Test Commands

From the repository root:

```powershell
dotnet run --project tests/CodeMesh.Tests
```

From `agent-access`:

```powershell
uv sync
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
- MCP evaluation scenarios.
- Formatting.
- MCP contracts.
- REST contracts.
- Store read components.

Use these tests when changing `agent-access/codemesh_agent_access`.

The Agent Access development dependency group includes `pytest` and `ruff`, so
`uv sync` is sufficient for a clean checkout. No global Python test or lint
packages are required.

Run lint and formatting checks after Python changes:

```powershell
uv run ruff check .
uv run ruff format --check .
```

Run the deterministic MCP evaluation suite directly when changing tool guidance,
context search, context packages, freshness, or redaction behavior:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval
```

The current evaluation suite uses an in-process fixture store, so it does not
require Docker services or a model provider. Use the end-to-end smoke script for
live-store lifecycle checks.

Run the live MCP stdio benchmark after self-ingesting a clean CodeMesh checkout:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval live
```

The pinned YoutubeDownloader suite is the representative external C# baseline.
Prepare and ingest the exact checkout as described in `docs/evaluation.md`, then
run:

```powershell
uv run python -m codemesh_agent_access eval live `
  --suite youtube-downloader-live `
  --output ..\.codemesh-evals\youtube-downloader-live\report.json
```

Run the opt-in Codex A/B benchmark only when live stores, a fresh index, Codex
authentication, time, and model budget are available:

```powershell
uv run python -m codemesh_agent_access eval agent --model <model-id>
```

Use `--suite youtube-downloader-agent` and point `--repository-root` at the
pinned external checkout for its implementation-discovery, change-impact, and
validation-selection comparison.

After the live suite passes, run the opt-in model selection benchmark. Tier 1
uses 72 executions per model and is the qualification gate before paired repair
testing:

```powershell
uv run python -m codemesh_agent_access eval model --model <model-id> --tier query
uv run python -m codemesh_agent_access eval model --model <model-id> --tier change
```

These model-backed commands are intentionally excluded from normal `pytest`
execution. Suite validation, scoring, proxy enforcement, review handling, and
orchestration tests remain in normal CI. See
`docs/evaluation.md` for metrics, suite formats, artifact handling, and exit codes.

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
