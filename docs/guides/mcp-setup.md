# MCP Setup

Document type: current operating guide

CodeMesh Agent Access can run as an MCP server so AI agents can query indexed repository context.

## Prerequisites

- Local stores are running: Neo4j, MongoDB, and Qdrant.
- Agent Access Python dependencies are available through `uv`.
- At least one repository has been ingested.
- Optional: a local embedding provider is running when vector search is required.

## Start Services

From the repository root:

```powershell
Copy-Item .env.example .env
# Set CODEMESH_NEO4J_AUTH=neo4j/<random-local-password> in .env first.
docker compose up -d neo4j mongodb qdrant csharp-parser agent-access
```

Check service health:

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
Invoke-RestMethod http://127.0.0.1:8088/health
```

## Ingest A Repository

For CodeMesh itself:

```powershell
dotnet restore CodeMesh.sln --locked-mode
dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings
```

After the first ingestion, refresh the current repository during normal development with:

```powershell
dotnet run --project src/CodeMesh.Cli -- refresh --skip-embeddings
```

For an optional external sample, use paths from the current machine:

```powershell
$repositoryRoot = "C:\path\to\sample-repository"
$solutionPath = Join-Path $repositoryRoot "Sample.sln"
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root $repositoryRoot `
  --solution $solutionPath `
  --skip-embeddings
```

Verify repository discovery:

```powershell
dotnet run --project src/CodeMesh.Cli -- repos list
dotnet run --project src/CodeMesh.Cli -- runs list --limit 5
```

For CodeMesh self-analysis, use the smoke check when Agent Access is running:

```powershell
dotnet run --project src/CodeMesh.Cli -- self smoke --skip-embeddings
```

## Run The MCP Server

Use the Python package from `agent-access`:

```powershell
Set-Location agent-access
uv run python -m codemesh_agent_access mcp
```

For an MCP client that accepts a command plus arguments, configure the server as:

```json
{
  "name": "codemesh",
  "command": "uv",
  "args": [
    "run",
    "python",
    "-m",
    "codemesh_agent_access",
    "mcp"
  ],
  "cwd": "/absolute/path/to/CodeMesh/agent-access"
}
```

For clients that expect a `mcpServers` object, use:

```json
{
  "mcpServers": {
    "codemesh": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "codemesh_agent_access",
        "mcp"
      ],
      "cwd": "/absolute/path/to/CodeMesh/agent-access"
    }
  }
}
```

If the client does not support `cwd`, wrap the command in PowerShell:

```json
{
  "command": "powershell",
  "args": [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "Set-Location 'C:\\path\\to\\CodeMesh\\agent-access'; uv run python -m codemesh_agent_access mcp"
  ]
}
```

Do not run the MCP server through `docker compose exec` unless the client explicitly supports interactive stdio correctly. The local `uv run` command is the preferred stdio path.

During MCP initialization, CodeMesh publishes a concise default workflow for
implementation discovery, change-impact analysis, and validation selection. It
directs capable hosts to start with an agent-format context package, use default
limits, and verify returned spans with targeted reads. Host support for exposing
server instructions varies; the same behavior remains explicit in the tool
descriptions and printable stable manifest.

## Required Environment

The MCP server reads the same store and model-provider environment variables as Agent Access. For local stdio MCP, these values should point at host-accessible endpoints, not Docker service names.

Minimum local values:

```text
CODEMESH_NEO4J_URI=bolt://127.0.0.1:7687
CODEMESH_NEO4J_AUTH=neo4j/codemesh
CODEMESH_NEO4J_DATABASE=neo4j
CODEMESH_MONGO_URI=mongodb://127.0.0.1:27017
CODEMESH_MONGO_DATABASE=codemesh
CODEMESH_MONGO_CONTENT_COLLECTION=content
CODEMESH_MONGO_REPOSITORIES_COLLECTION=repositories
CODEMESH_MONGO_INGESTION_RUNS_COLLECTION=ingestion_runs
CODEMESH_MONGO_NODE_SUMMARIES_COLLECTION=node_summaries
CODEMESH_QDRANT_URL=http://127.0.0.1:6333
CODEMESH_QDRANT_COLLECTION=codemesh-code
CODEMESH_MODEL_PROVIDER=none
```

For local Ollama-backed semantic query embeddings:

```text
CODEMESH_MODEL_PROVIDER=ollama
CODEMESH_OLLAMA_URL=http://127.0.0.1:11434
CODEMESH_EMBEDDING_MODEL=nomic-embed-text-v2-moe:latest
```

For LM Studio:

```text
CODEMESH_MODEL_PROVIDER=lmstudio
CODEMESH_LM_STUDIO_URL=http://127.0.0.1:1234/v1
CODEMESH_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v2-moe
```

When Agent Access runs inside Docker, use the `CODEMESH_AGENT_*` values from `.env.example` for container-to-container or container-to-host access. When MCP runs through local stdio, use the non-agent host values above.

## Useful MCP Tools

- `codemesh_status`: check service and store health.
- `codemesh_get_tool_guidance`: recommend which CodeMesh tools to use for a natural-language agent task.
- `codemesh_list_repositories`: find indexed repositories and aliases.
- `codemesh_get_repository_status`: inspect latest run, counts, summary coverage, and freshness diagnostics.
- `codemesh_search_context`: search for relevant implementation context.
- `codemesh_get_context_package`: return an agent-ready bundle of code, summaries, relationships, and repository metadata.
- `codemesh_search_symbols`: find precise symbols before expanding context.
- `codemesh_get_node`: retrieve a known node and optional content.
- `codemesh_get_neighbors`: inspect graph relationships around a node.
- `codemesh_list_ingestion_runs`: inspect recent indexing runs.

## Troubleshooting

- If MCP starts but returns no useful context, confirm the repository was ingested with `repos list`.
- If the MCP client says the server exited immediately, run `cd agent-access; uv run python -m codemesh_agent_access mcp` in a terminal to see import or environment errors.
- If vector search is unavailable, check `status`; Agent Access should fall back to lexical search when possible.
- If context search fails with request validation errors, confirm the MCP client is sending arrays for `kinds`, `filters`, and `vector` only when values are present.
- If store connection checks fail from MCP but Docker services are running, confirm the MCP environment uses `127.0.0.1` store URLs rather than Docker service names such as `mongodb` or `qdrant`.
- If Python import errors occur, run the MCP command from `agent-access` with `uv run`.
- If Dockerized Agent Access cannot reach host model providers, use `host.docker.internal` URLs in `.env`.
- If a repository looks stale, run ingestion again and check `runs list`.
- Do not paste `.env` contents into chat or issue logs. Report variable names and redacted values only.
