# CodeMesh

CodeMesh is a local-first, C#/.NET-focused context and change-impact service
that helps coding agents locate implementation, trace likely impact, and select
validation using compact, source-backed evidence.

The current milestone is evidence that this workflow improves agent outcomes
over normal repository exploration. CodeMesh is not presented as
production-ready. The CodeMesh source is available under the
[MIT License](LICENSE).

## Product status

| Status | Capability |
| --- | --- |
| Implemented and locally verified | C# ingestion through Roslyn; graph/content persistence; repository freshness; REST, MCP, CLI, and .NET Agent Access; source spans; relationship-aware context packages; deterministic fixture evaluation; security redaction tests. |
| Optional and environment-dependent | Neo4j, MongoDB, and Qdrant stores; Docker Compose; embeddings through a configured local provider; Python, Markdown, and deployment-artifact parsing with narrower relationships than C#. |
| Experimental or unqualified | Generated summaries, online model providers, model-selection benchmarks, assisted agent-efficiency evidence, and the read-only local web UI as a product surface. No summary model is CodeMesh-qualified. |
| Planned | Repeatable independent agent-outcome evidence, configurable ingestion allow/deny policy, broader parser and SDLC coverage, portable snapshots, and expanded presentation surfaces. |

Passing tests establish the covered local behavior. They do not establish
hosted CI success, generalized agent benefit, release readiness, deployment
acceptance, or production fitness. See [Next Steps](docs/next-steps.md) for the
prioritized evidence milestone.

## Architecture

```mermaid
flowchart LR
    Repo[Repository ingestion] --> Parsers[Roslyn and local parsers]
    Parsers --> Graph[(Neo4j graph)]
    Parsers --> Content[(MongoDB content)]
    Parsers --> Vector[(Qdrant vectors)]
    Graph --> Access[Agent Access REST and MCP]
    Content --> Access
    Vector --> Access
    Access --> Agent[Coding agent]
```

Graph paths, generated summaries, and search rankings are navigation evidence.
The cited repository source remains authoritative.

## Five-minute local demonstration

Prerequisites are the .NET 10 SDK, Docker Compose, Python 3.12 or newer, and
[`uv`](https://docs.astral.sh/uv/). The demonstration indexes this checkout, so
it needs no external sample repository or model provider.

1. Create local configuration and set a unique development password:

   ```powershell
   Copy-Item .env.example .env
   # Edit .env and set CODEMESH_NEO4J_AUTH=neo4j/<random-local-password>
   ```

   On Unix-like shells, use `cp .env.example .env` instead. `.env` is ignored by
   Git. The example keeps model and summary providers disabled.

2. Start the local stores and parser, then ingest CodeMesh without embeddings or
   generated summaries:

   ```powershell
   docker compose up -d neo4j mongodb qdrant csharp-parser agent-access
   dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings
   ```

3. Query the repository through Agent Access:

   ```powershell
   Set-Location agent-access
   uv sync --locked
   uv run python -m codemesh_agent_access package `
     "How does self ingestion reach the stores?" `
     --repository-id code_mesh `
     --output agent
   ```

The generated alias is normally `code_mesh`; confirm it with
`dotnet run --project src/CodeMesh.Cli -- repos list` if needed. For a
store-free contract demonstration, run
`uv run python -m codemesh_agent_access eval` from `agent-access`; that suite
uses synthetic in-process fixtures and proves tool behavior, not retrieval from
a live index.

## What this demonstrates

- .NET 10 and Roslyn-based semantic parsing for C# implementation and local
  relationships.
- Python FastAPI, MCP, CLI, ranking, formatting, and store read paths.
- Neo4j graph, MongoDB content/registry, and optional Qdrant vector storage.
- Docker Compose service wiring with host ports restricted to loopback by
  default.
- Source-scoped MCP context packages with freshness and redaction diagnostics.
- Deterministic fixture, live retrieval, and opt-in agent/model evaluation
  layers with explicit evidence boundaries.
- Local-first processing by default; generated summaries and external model
  providers are opt-in and unqualified.

## Verification

These commands ran successfully against the local diff on 2026-08-11:

```powershell
dotnet restore CodeMesh.sln --locked-mode
dotnet build CodeMesh.sln --no-restore
dotnet run --project tests/CodeMesh.Tests --no-restore
dotnet format CodeMesh.sln --verify-no-changes --no-restore

Set-Location agent-access
uv sync --locked
uv run --no-sync pytest
uv run --no-sync ruff check . ../tools
uv run --no-sync ruff format --check . ../tools
$env:CODEMESH_MODEL_PROVIDER = "none"
uv run --no-sync python -m codemesh_agent_access eval
Set-Location ..

dotnet run --project src/CodeMesh.Cli --no-restore -- `
  self ingest --skip-embeddings
python tools/check_publication_safety.py
python tools/check_markdown_links.py
npx --yes markdownlint-cli2@0.23.1 "**/*.md"
```

The .NET harness passed 53 tests and skipped one unconfigured external sample;
Python passed 92 tests. The provider-free fixture suite, locked Docker image
builds, and synthetic end-to-end smoke also passed. Full evidence, corrected
intermediate failures, and unavailable hosted checks are recorded in
[Publication Readiness](docs/publication-readiness.md).

## Repository map

- `src/CodeMesh.Parser.CSharp`: Roslyn parser worker.
- `src/CodeMesh.Ingestion`: ingestion, cleanup, redaction, embeddings, and
  optional summary generation.
- `src/CodeMesh.Storage`: Neo4j, MongoDB, Qdrant, and in-memory adapters.
- `src/CodeMesh.Control` and `src/CodeMesh.Cli`: configuration, lifecycle, and
  operator commands.
- `agent-access`: Python REST, MCP, CLI, ranking, and evaluation surfaces.
- `tests/CodeMesh.Tests` and `agent-access/tests`: .NET and Python verification.

Start with [Agent Quickstart](docs/agent-quickstart.md) when working in the
repository. Detailed references are kept in:

- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [MCP Setup](docs/mcp-setup.md)
- [Agent Access Contracts](docs/agent-access-contracts.md)
- [Evaluation](docs/evaluation.md)
- [Security and Redaction](docs/security-and-redaction.md)
- [Summary Model Qualification](docs/summary-model-qualification.md)
- [Self-Analysis](docs/self-analysis.md)

## Security, contribution, and licence

Read [SECURITY.md](SECURITY.md) before reporting a suspected secret or
vulnerability, and [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.

CodeMesh is licensed under the [MIT License](LICENSE). Third-party packages,
services, and referenced evaluation repositories retain their own licences; see
[Third-party Notices](THIRD_PARTY_NOTICES.md). The remaining privacy,
dependency, hosted-CI, and visibility gates are recorded in
[Publication Readiness](docs/publication-readiness.md).
