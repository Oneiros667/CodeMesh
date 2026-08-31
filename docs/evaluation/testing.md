# Testing Guide

Document type: current operating guide

Use this guide to choose the right verification path after CodeMesh changes.

## Default Verification Commands

From the repository root:

```powershell
dotnet restore CodeMesh.sln --locked-mode
dotnet build CodeMesh.sln --no-restore
dotnet run --project tests/CodeMesh.Tests --no-restore
dotnet format CodeMesh.sln --verify-no-changes --no-restore
```

Run these .NET commands serially because projects share intermediate output
directories.

From `agent-access`:

```powershell
uv sync --locked
uv run --no-sync pytest
uv run --no-sync ruff check . ../tools
uv run --no-sync ruff format --check . ../tools
```

Run both after most implementation changes.

## .NET Tests

The .NET test harness covers:

- Domain utilities.
- Environment loading.
- Agent Access contract mapping.
- Agent Access .NET client behavior.
- Ingestion orchestration.
- Incremental writes, deterministic project/checkout/snapshot identity,
  compare-and-swap slot retention, pins, and cleanup.
- Embedding and summary providers.
- MongoDB, Neo4j, and Qdrant storage adapters.
- C#, Python, Rust, and atomic multi-language parser behavior.
- Optional configured sample parsing.

Some tests skip when required live services or sample paths are unavailable.

## Python Tests

The Python tests under `agent-access/tests` cover:

- CLI output.
- Context ranking.
- MCP evaluation scenarios.
- Formatting.
- MCP contracts.
- Exact checkout binding, reviewable installation, provider-free probing, and
  versioned feedback recording/summarization.
- REST contracts.
- Store read components.

Use these tests when changing `agent-access/codemesh_agent_access`.

The Agent Access development dependency group includes `pytest` and `ruff`, so
`uv sync --locked` is sufficient for a clean checkout and rejects lock drift.
No global Python test or lint packages are required.

Run lint and formatting checks after Python changes:

```powershell
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
```

Run the deterministic MCP evaluation suite directly when changing tool guidance,
context search, context packages, freshness, or redaction behavior:

```powershell
cd agent-access
uv run --no-sync python -m codemesh_agent_access eval
```

The current evaluation suite uses an in-process fixture store and explicitly
selects the non-destructive diagnostic MCP profile, so it does not require
Docker services or a model provider. Profile contract tests separately assert
the four-tool normal default and deletion exclusion. Use the end-to-end smoke
script for live-store lifecycle checks.

Run the live MCP stdio benchmark after self-ingesting a clean CodeMesh checkout:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval live
```

The retained live and existing spontaneous/evaluator-assisted agent suites
select the `diagnostic` profile explicitly to preserve their frozen tool surface.
That does not make them configured/onboarded product evidence. The implemented
configured mode selects the shipped `normal` profile and records that identity
separately in its installation plan and runtime probe.

For an installed configured checkout, run the reviewed plan's normal-profile
probe instead. It verifies the exact launch and binding and can gate real target
paths:

```powershell
uv run python -m codemesh_agent_access mcp-probe `
  --plan C:\temp\codemesh-install-plan.json `
  --query "Python to Rust native replay implementation and tests" `
  --expected-path native/feed_hub_replay/src/lib.rs
```

This is configured retrieval evidence, not a model-backed agent comparison.
Record misses through the feedback workflow and retain passing rechecks with an
explicit superseded feedback id.

The pinned YoutubeDownloader suite is the representative external C# baseline.
Prepare and ingest the exact checkout as described in
[MCP Effectiveness Evaluation](mcp-effectiveness.md), then run:

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

Use `--suite youtube-downloader-impact-agent` with the same checkout for the
separate complex impact-analysis calibration task. It runs six executions at
the default three repetitions and does not alter the original frozen suite.
Run `eval live --suite youtube-downloader-impact-live` first to retain its
retrieval and relationship baseline.

Use `--suite youtube-downloader-impact-assisted-agent` only after a spontaneous
campaign records zero adoption. Its treatment-only onboarding deliberately
breaks prompt parity and is reported as assisted utility evidence.

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
[MCP Effectiveness Evaluation](mcp-effectiveness.md) for metrics, suite formats,
artifact handling, and exit codes.

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

Tests are usually not required for documentation-only changes. Run:

```powershell
npx --yes markdownlint-cli2@0.23.1 "**/*.md"
python tools/check_markdown_links.py
python tools/check_publication_safety.py
git diff --check
```

The link and publication-safety checks are local-only and do not print secret
values.

## Dependency Advisory Checks

Before publication or a dependency update, query the current NuGet and OSV
advisory data:

```powershell
dotnet list CodeMesh.sln package --vulnerable --include-transitive
Set-Location agent-access
uv audit --locked
```

These checks use external advisory services and can become unavailable or
change as advisories are published. Record the date and do not place them in the
deterministic baseline workflow.

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
