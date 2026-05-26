# CodeMesh

CodeMesh is a local-first code intelligence substrate for AI coding agents. Code ingestion writes graph, content, and vector intelligence; Agent Access reads that intelligence through REST and MCP tools; coding agents use the returned context while editing code in their normal environment.

## Current Scaffold

- `.NET 10` solution with `CodeMesh.Domain`, `CodeMesh.Ingestion`, `CodeMesh.Control`, `CodeMesh.Parser.CSharp`, `CodeMesh.Storage`, and `CodeMesh.Cli`.
- Shared records for code nodes, relationships, parser results, ingestion runs, agent context, and health checks.
- Ingestion orchestration with incremental graph/content/vector writes and repository/run registry records.
- C# parser worker API with `/health`, `/capabilities`, and `/parse`.
- Python Agent Access REST endpoints and MCP tools backed by Neo4j, MongoDB, and Qdrant read paths.
- Docker Compose for Neo4j, MongoDB, Qdrant, Agent Access, C# parser worker, and optional Ollama.

## Quick Start

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
dotnet run --project src/CodeMesh.Cli -- ingest --root C:\Users\developer\source\repos\YoutubeDownloader --solution C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- repos list
dotnet run --project src/CodeMesh.Cli -- runs list --limit 5
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
ollama pull nomic-embed-text:latest

dotnet run --project src/CodeMesh.Cli -- ingest `
  --root C:\Users\developer\source\repos\YoutubeDownloader `
  --solution C:\Users\developer\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --include-embeddings `
  --embedding-provider ollama `
  --embedding-model nomic-embed-text:latest
```

`--skip-embeddings` remains the fastest ingestion mode. Use `--include-embeddings` when you want semantic search data written to Qdrant.
Use `--force-embeddings` when graph/content are unchanged but Qdrant vectors should be regenerated for the selected provider and model.
The Ollama embedding input defaults to 1500 characters per node for compatibility with `nomic-embed-text:latest`; use `--embedding-max-chars` to tune this for another embedding model.

Each successful ingestion run stamps graph, content, and vector records with a repository id and ingestion run id. CodeMesh also writes repository/run registry records to MongoDB so users and agents can discover indexed repositories and recent ingestion history. Repository registry records include a generated alias, for example `YoutubeDownloader` becomes `youtube_downloader`, and read commands accept either the hash id or alias. Incremental ingestion skips unchanged graph/content/vector writes after parsing, then removes stale records from the same repository that were not seen in the current run. If `--skip-embeddings` is used, vector cleanup is skipped so existing embeddings are left untouched.

Query the registry:

```powershell
dotnet run --project src/CodeMesh.Cli -- repos list
dotnet run --project src/CodeMesh.Cli -- repo show <repository-id-or-alias>
dotnet run --project src/CodeMesh.Cli -- runs list --repository-id <repository-id-or-alias> --limit 10
dotnet run --project src/CodeMesh.Cli -- embeddings verify <repository-id-or-alias> --embedding-provider ollama --embedding-model nomic-embed-text:latest
```

Start the default local stores and services:

```powershell
copy .env.example .env
docker compose up -d neo4j mongodb qdrant csharp-parser agent-access
```

### Ollama Modes

Native Windows Ollama is the recommended mode when you want GPU acceleration on Windows. Use `http://127.0.0.1:11434` for the host .NET CLI to avoid intermittent Windows `localhost` IPv6 probe timeouts; Dockerized Agent Access reaches the same Windows Ollama service through `http://host.docker.internal:11434`.

In `.env`, use:

```text
CODEMESH_MODEL_PROVIDER=ollama
CODEMESH_OLLAMA_URL=http://127.0.0.1:11434
CODEMESH_AGENT_OLLAMA_URL=http://host.docker.internal:11434
CODEMESH_EMBEDDING_MODEL=nomic-embed-text:latest
```

Then recreate Agent Access:

```powershell
docker compose up -d --force-recreate agent-access
Invoke-RestMethod http://localhost:8088/status
```

Use the optional Ollama container only when you intentionally want Ollama isolated in Docker. Set the Agent Access URL to the compose service name:

```powershell
$env:CODEMESH_AGENT_OLLAMA_URL = 'http://ollama:11434'
docker compose --profile ollama up -d ollama
docker compose up -d --force-recreate agent-access
```

The Ollama container mounts `${CODEMESH_OLLAMA_HOME}` to `/root/.ollama`; set it to your Windows Ollama home, for example `C:/Users/developer/.ollama`, if you want the container to reuse the same local model files.

## Service Endpoints

- Agent Access REST: `http://localhost:8088`
- C# parser worker: `http://localhost:8091`
- Neo4j browser: `http://localhost:7474`
- Qdrant HTTP: `http://127.0.0.1:6333`
- MongoDB: `mongodb://127.0.0.1:27017`

## Agent Access

REST endpoints:

- `GET /health`
- `GET /status`
- `POST /context/search`
- `POST /context/package`
- `POST /nodes/get`
- `POST /graph/neighbors`
- `GET /repositories`
- `GET /repositories/{repository_id}`
- `GET /ingestion-runs`

MCP tools:

- `codemesh_status`
- `codemesh_search_context`
- `codemesh_get_context_package`
- `codemesh_get_node`
- `codemesh_get_neighbors`
- `codemesh_list_repositories`
- `codemesh_get_repository`
- `codemesh_list_ingestion_runs`

PowerShell examples:

```powershell
Invoke-RestMethod http://127.0.0.1:8088/health
Invoke-RestMethod http://127.0.0.1:8088/repositories
Invoke-RestMethod 'http://127.0.0.1:8088/ingestion-runs?limit=5'

$nodeBody = @{
  node_id = 'csharp:type:CodeMesh.Tests.Neo4jSmokeSource'
  repository_id = 'repo:neo4j-smoke'
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

$packageBody = @{
  query = 'download video with subtitles'
  repository_id = 'repo:youtube-downloader'
  limit = 5
  max_characters = 12000
  include_relationships = $true
  relationship_limit = 12
  caller_limit = 3
  callee_limit = 3
  read_limit = 2
  write_limit = 2
} | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:8088/context/package -Method Post -ContentType 'application/json' -Body $packageBody
```

Direct CLI examples:

```powershell
cd agent-access
uv run python -m codemesh_agent_access status
uv run python -m codemesh_agent_access search "download video with subtitles" --repository-id repo:youtube-downloader --limit 5 --kind Class
uv run python -m codemesh_agent_access package "download video with subtitles" --repository-id repo:youtube-downloader --limit 5 --max-characters 12000 --caller-limit 3 --callee-limit 3 --read-limit 2 --write-limit 2
uv run python -m codemesh_agent_access package "download video with subtitles" --repository-id repo:youtube-downloader --limit 3 --max-characters 6000 --caller-limit 2 --callee-limit 2 --read-limit 1 --write-limit 1 --output agent
uv run python -m codemesh_agent_access get-node csharp:type:CodeMesh.Tests.Neo4jSmokeSource --repository-id repo:neo4j-smoke --no-content
uv run python -m codemesh_agent_access neighbors csharp:type:CodeMesh.Tests.Neo4jSmokeSource --repository-id repo:neo4j-smoke
uv run python -m codemesh_agent_access repos --limit 10
uv run python -m codemesh_agent_access runs --repository-id <repository-id> --limit 5
```

Set `CODEMESH_MODEL_PROVIDER=ollama` for Agent Access when you want text queries embedded automatically before Qdrant search. If Ollama or Qdrant vectors are unavailable, Agent Access falls back to lexical Neo4j search.

Pass `repository_id` in REST/MCP context, node, and neighbor queries to constrain lookups to one ingested repository. The value can be the repository hash id or its generated alias. CLI commands accept the equivalent `--repository-id` option.

Context search results are ranked for agent usefulness. Low-level matches such as parameter declarations are expanded to their defining symbol or containing method/type before they are returned, and each hit includes `repository_id`, `content_hash`, `score_components`, and `expanded_context` when expansion occurred. Use `expand_context=false` in REST/MCP or `--no-expand-context` in the CLI for compact raw hits. Use `include_context_relationships=true` or `--include-context-relationships` when each hit should include a small immediate relationship summary.

Context packages build on search results and return an agent-ready bundle with selected hits, normalized node metadata, budgeted source snippets, immediate relationship summaries, repository metadata, and the latest ingestion run. Each item includes the flat `relationships` list plus `relationship_groups` for `callers`, `callees`, `reads`, `writes`, `contains`, `defines`, and `uses_types`. Relationship summaries are ordered for agent usefulness, prioritizing the primary declaration, enclosing owner, callers, callees, writes, reads, and type relationships before low-signal edges. Use `max_characters` / `--max-characters` to keep snippet output within a rough context budget, and use `caller_limit`, `callee_limit`, `read_limit`, `write_limit`, `contains_limit`, `definition_limit`, and `uses_type_limit` to cap noisy relationship groups inside the total `relationship_limit`. The package CLI defaults to JSON; pass `--output agent` for a concise text brief.

## Development Notes

The old HelioGraph repository is reference-only. CodeMesh starts with clean contracts and intentionally thin adapters so the graph, content, vector, parser, and agent-access boundaries can harden independently.

The C# parser emits file, namespace, declaration, type, member, and relationship nodes using Roslyn. Partial types are represented as one logical symbol node plus separate declaration nodes. Method and member bodies also emit local semantic relationships such as `Invokes`, `Reads`, and `Writes` when the target symbol is part of the indexed code graph.
