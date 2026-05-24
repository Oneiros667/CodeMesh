# CodeMesh

CodeMesh is a local-first code intelligence substrate for AI coding agents. Code ingestion writes graph, content, and vector intelligence; Agent Access reads that intelligence through REST and MCP tools; coding agents use the returned context while editing code in their normal environment.

## Current Scaffold

- `.NET 10` solution with `CodeMesh.Domain`, `CodeMesh.Ingestion`, `CodeMesh.Control`, `CodeMesh.Parser.CSharp`, `CodeMesh.Storage`, and `CodeMesh.Cli`.
- Shared records for code nodes, relationships, parser results, ingestion runs, agent context, and health checks.
- Ingestion orchestration skeleton that calls a parser client and writes through graph/content/vector storage interfaces.
- C# parser worker API with `/health`, `/capabilities`, and `/parse`.
- Python Agent Access REST endpoints and MCP tools backed by Neo4j, MongoDB, and Qdrant read paths.
- Docker Compose for Neo4j, MongoDB, Qdrant, Agent Access, C# parser worker, and optional Ollama.

## Quick Start

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
dotnet run --project src/CodeMesh.Cli -- ingest --root C:\Users\developer\source\repos\YoutubeDownloader --solution C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx --skip-embeddings
dotnet run --project tests/CodeMesh.Tests
```

## Sample Project

The local C# integration sample is `C:\Users\developer\source\repos\YoutubeDownloader`. It is listed in `codemesh.yaml` under `samples.youtube_downloader` and exposed through these environment variables:

```powershell
$env:CODEMESH_SAMPLE_CSHARP_ROOT = 'C:\Users\developer\source\repos\YoutubeDownloader'
$env:CODEMESH_SAMPLE_CSHARP_SOLUTION = 'C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx'
dotnet run --project tests/CodeMesh.Tests
```

The smoke test parses the sample with `CodeMesh.Parser.CSharp` in dry-run style. If the sample path is missing on another machine, the sample test is skipped.

Run a dry-run parse without writing stores:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root C:\Users\developer\source\repos\YoutubeDownloader `
  --solution C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --dry-run `
  --skip-embeddings
```

Persist the parsed graph/content to Neo4j and MongoDB:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root C:\Users\developer\source\repos\YoutubeDownloader `
  --solution C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --skip-embeddings
```

Persist graph/content and generate Qdrant embeddings with Ollama:

```powershell
docker compose --profile ollama up -d ollama

dotnet run --project src/CodeMesh.Cli -- ingest `
  --root C:\Users\developer\source\repos\YoutubeDownloader `
  --solution C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --include-embeddings `
  --embedding-provider ollama `
  --embedding-model nomic-embed-text:latest
```

`--skip-embeddings` remains the fastest ingestion mode. Use `--include-embeddings` when you want semantic search data written to Qdrant.

Start the default local stores and services:

```powershell
copy .env.example .env
docker compose up -d neo4j mongodb qdrant csharp-parser agent-access
```

Enable Ollama only when you want a local model provider:

```powershell
docker compose --profile ollama up -d ollama
```

## Service Endpoints

- Agent Access REST: `http://localhost:8088`
- C# parser worker: `http://localhost:8091`
- Neo4j browser: `http://localhost:7474`
- Qdrant HTTP: `http://localhost:6333`
- MongoDB: `mongodb://localhost:27017`

## Agent Access

REST endpoints:

- `GET /health`
- `GET /status`
- `POST /context/search`
- `POST /nodes/get`
- `POST /graph/neighbors`

MCP tools:

- `codemesh_status`
- `codemesh_search_context`
- `codemesh_get_node`
- `codemesh_get_neighbors`

PowerShell examples:

```powershell
Invoke-RestMethod http://127.0.0.1:8088/health

$nodeBody = @{
  node_id = 'csharp:type:CodeMesh.Tests.Neo4jSmokeSource'
  include_content = $false
  include_neighbors = $true
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8088/nodes/get -Method Post -ContentType 'application/json' -Body $nodeBody

$searchBody = @{
  query = 'download video with subtitles'
  limit = 5
  kinds = @('Class', 'Method')
  filters = @{}
} | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:8088/context/search -Method Post -ContentType 'application/json' -Body $searchBody
```

Direct CLI examples:

```powershell
cd agent-access
uv run python -m codemesh_agent_access status
uv run python -m codemesh_agent_access search "download video with subtitles" --limit 5 --kind Class
uv run python -m codemesh_agent_access get-node csharp:type:CodeMesh.Tests.Neo4jSmokeSource --no-content
uv run python -m codemesh_agent_access neighbors csharp:type:CodeMesh.Tests.Neo4jSmokeSource
```

Set `CODEMESH_MODEL_PROVIDER=ollama` for Agent Access when you want text queries embedded automatically before Qdrant search. If Ollama or Qdrant vectors are unavailable, Agent Access falls back to lexical Neo4j search.

## Development Notes

The old HelioGraph repository is reference-only. CodeMesh starts with clean contracts and intentionally thin adapters so the graph, content, vector, parser, and agent-access boundaries can harden independently.

The C# parser emits file, namespace, declaration, type, member, and relationship nodes using Roslyn. Partial types are represented as one logical symbol node plus separate declaration nodes.
