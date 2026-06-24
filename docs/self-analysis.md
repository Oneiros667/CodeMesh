# CodeMesh Self-Analysis

CodeMesh can be indexed and queried by its own Agent Access MCP service. This dogfooding path is useful for testing context quality, repository freshness, MCP tool ergonomics, and parser coverage.

## Index CodeMesh

Start stores and services:

```powershell
docker compose up -d neo4j mongodb qdrant csharp-parser agent-access
```

Ingest the repository without embeddings:

```powershell
dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings
```

Or ingest with local embeddings when a provider is running:

```powershell
dotnet run --project src/CodeMesh.Cli -- self ingest `
  --include-embeddings `
  --embedding-provider lmstudio `
  --embedding-model text-embedding-nomic-embed-text-v2-moe
```

Run a dry-run parse without writing stores:

```powershell
dotnet run --project src/CodeMesh.Cli -- self ingest --dry-run --skip-embeddings
```

Index CodeMesh runtime/deployment artifacts:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest --root . --language deployment --skip-embeddings
```

Run the self-ingestion smoke check after Agent Access is available:

```powershell
dotnet run --project src/CodeMesh.Cli -- self smoke --skip-embeddings
```

The smoke command indexes CodeMesh, checks that Agent Access can list the repository and recent runs, then verifies that a context query returns hits.

Verify registry and runs manually:

```powershell
dotnet run --project src/CodeMesh.Cli -- repos list
dotnet run --project src/CodeMesh.Cli -- runs list --repository-id code_mesh --limit 5
```

The generated alias may differ. Use the value shown by `repos list`.

## Run MCP

```powershell
cd D:\source\repos\CodeMesh\agent-access
uv run python -m codemesh_agent_access mcp
```

See `docs/mcp-setup.md` for MCP client configuration.

## Useful Self-Analysis Questions

- How does ingestion write graph, content, vector, summary, and registry records?
- Which components participate in repository cleanup?
- Where is context package generation implemented?
- Which contracts define Agent Access REST and MCP payloads?
- How does the C# parser emit invocation, read, and write relationships?
- Which tests cover summary generation and summary coverage?
- What changed recently around repository deletion?

## Known Limitations

- Structured C# parsing is richer than Python parsing.
- The Python `agent-access` implementation can be ingested with `--language python`, but current Python support is limited to file, class, function, async function, and containment relationships.
- Markdown documents can be ingested with `--language markdown`, but current support is limited to document, section, anchor, heading-level, and containment structure.
- Deployment artifacts can be ingested with `--language deployment`, but current support is limited to Dockerfiles, Docker Compose files, stages, services, selected runtime metadata, and Compose service dependencies.
- Freshness and latest refresh outcome should be checked through `codemesh_get_repository_status`, `GET /repositories/{repository_id}/status`, or the local repository detail UI.

## Expected Dogfooding Improvements

The highest-value improvements are tracked in `docs/next-steps.md`:

- Self-ingestion workflow.
- MCP setup guide.
- Index freshness diagnostics.
- Secret redaction.
- Python parser support.
- Markdown documentation ingestion.
- Runtime/deployment artifact ingestion.
- Context package quality gates.
