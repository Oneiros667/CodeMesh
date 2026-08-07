# CodeMesh

CodeMesh is a local-first context and change-impact service for AI coding
agents. It turns a fresh repository index into compact, source-backed evidence
that helps an agent locate implementation code, trace likely impact, and choose
the right validation while editing in its normal environment.

The initial product wedge is C#/.NET repositories, where the Roslyn parser can
provide higher-fidelity semantic relationships. The product goal is not to
index every software artifact. It is to improve agent correctness, elapsed
time, or token use compared with normal repository exploration while preserving
freshness, source citations, repository boundaries, and local data control.

## Current Product Status

CodeMesh has a healthy technical baseline for ingestion, Agent Access, MCP,
freshness diagnostics, source-grounded context packages, and deterministic
evaluation. Repeatable product benefit is not established yet: retained agent
control/treatment evidence is insufficient or negative, and a current reviewed
baseline against a representative external C# repository is still required.

Generated summaries, embeddings, broader parser coverage, deployment
intelligence, and SDLC ingestion are supporting or experimental capabilities.
They must not displace the near-term evidence milestone. In particular, no
summary model is currently CodeMesh-qualified, so summaries are optional and
should not be treated as a default retrieval dependency.

## Current Scaffold

- `.NET 10` solution with `CodeMesh.Domain`, `CodeMesh.Ingestion`, `CodeMesh.Control`, parser projects, `CodeMesh.Storage`, and `CodeMesh.Cli`.
- Shared records for code nodes, relationships, parser results, ingestion runs, agent context, and health checks.
- Ingestion orchestration with incremental graph/content/vector/summary writes and repository/run registry records.
- C# parser worker API with `/health`, `/capabilities`, and `/parse`.
- Local deployment parser support for Dockerfiles, Docker Compose files, Dockerfile stages, Compose services, service ports, environment keys, volumes, and service dependencies.
- Local Markdown parser support for documents, headings, sections, anchors, and containment relationships.
- Local Python parser support for files, classes, functions, async functions, and containment relationships.
- Python Agent Access REST endpoints and MCP tools backed by Neo4j, MongoDB, and Qdrant read paths.
- Docker Compose for Neo4j, MongoDB, Qdrant, Agent Access, C# parser worker, and optional Ollama.

## Documentation

- [Agent Quickstart](docs/agent-quickstart.md): starting point for AI agents working in this repository.
- [Architecture](docs/architecture.md): current components, data flow, stores, and extension points.
- [Graph Intelligence Design](docs/graph-intelligence-design.md): proposed
  relationship evidence, graph analysis, agent outcome memory, and portability.
- [Testing Guide](docs/testing.md): verification commands and smoke-test guidance.
- [MCP Evaluation](docs/evaluation.md): deterministic, live stdio, agent A/B, and graded model-selection benchmarks.
- [Summary Model Qualification](docs/summary-model-qualification.md):
  provider-neutral procedure for qualifying local or online ingestion
  summarizers.
- [Agent Access Contracts](docs/agent-access-contracts.md): REST, MCP, CLI, and .NET client contracts.
- [MCP Setup](docs/mcp-setup.md): configure CodeMesh as an MCP service for AI agents.
- [CodeMesh Self-Analysis](docs/self-analysis.md): index and query CodeMesh with CodeMesh itself.
- [Security And Redaction](docs/security-and-redaction.md): secret-handling expectations for agent-facing context.
- [Agent Prompts](docs/agent-prompts.md): example prompts for agents using CodeMesh through MCP.
- [Next Steps](docs/next-steps.md): prioritized backlog for effective MCP agent use.
- [SDLC Roadmap](docs/sdlc-roadmap.md): longer-term SDLC intelligence goals.

## Quick Start

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- self smoke --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- refresh --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- watch --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- repos list
dotnet run --project src/CodeMesh.Cli -- runs list --limit 5
dotnet run --project tests/CodeMesh.Tests
cd agent-access; uv run python -m codemesh_agent_access eval
```

This core path intentionally omits generated summaries, embeddings, and
secondary parser modes. The sections below document those optional capabilities
for explicit experiments. Use the sample C# repository flow below when testing
beyond CodeMesh self-analysis.

## Sample Project

The local C# integration sample is `D:\source\repos\YoutubeDownloader`. It is listed in `codemesh.yaml` under `samples.youtube_downloader` and exposed through these environment variables:

```powershell
$env:CODEMESH_SAMPLE_CSHARP_ROOT = 'D:\source\repos\YoutubeDownloader'
$env:CODEMESH_SAMPLE_CSHARP_SOLUTION = 'D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx'
dotnet run --project tests/CodeMesh.Tests
```

The smoke test parses the sample with `CodeMesh.Parser.CSharp` in dry-run style. If the sample path is missing on another machine, the sample test is skipped.

Run a dry-run parse without writing stores:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --dry-run `
  --skip-embeddings
```

Persist the parsed graph/content to Neo4j and MongoDB:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --skip-embeddings
```

Persist graph/content and generate Qdrant embeddings with Ollama:

```powershell
ollama pull nomic-embed-text-v2-moe:latest

dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --include-embeddings `
  --embedding-provider ollama `
  --embedding-model nomic-embed-text-v2-moe:latest
```

`--skip-embeddings` remains the fastest ingestion mode. Use `--include-embeddings` when you want semantic search data written to Qdrant.
Use `--force-embeddings` when graph/content are unchanged but Qdrant vectors should be regenerated for the selected provider and model.
The embedding input defaults to 1500 characters per node for compatibility with `nomic-embed-text-v2-moe:latest`; use `--embedding-max-chars` to tune this for another embedding model. CodeMesh prefixes indexed node text with `search_document:` and Agent Access query text with `search_query:` for Nomic retrieval models.

You can also generate embeddings with LM Studio when the local server is running and an embedding model is loaded:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --include-embeddings `
  --embedding-provider lmstudio `
  --lm-studio-url http://127.0.0.1:1234/v1 `
  --embedding-model text-embedding-nomic-embed-text-v2-moe
```

Generate MongoDB node summaries with a local chat/code model:

```powershell
ollama pull qwen2.5-coder:14b

dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --skip-embeddings `
  --include-summaries `
  --summary-provider ollama `
  --summary-model qwen2.5-coder:14b
```

LM Studio summary generation uses its OpenAI-compatible chat API:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --skip-embeddings `
  --include-summaries `
  --summary-provider lmstudio `
  --lm-studio-url http://127.0.0.1:1234/v1 `
  --summary-model mistralai/ministral-3-3b
```

OpenAI summary generation uses the Responses API with strict Structured
Outputs. Authentication is read only from `OPENAI_API_KEY`; CodeMesh does not
accept the key as a command-line option. The configured OpenAI summary default
is `gpt-5.6-luna`. This is an experimental configuration default, not a
qualified or recommended deployment profile. It must be qualified against
representative CodeMesh nodes and downstream retrieval outcomes before
production use:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --skip-embeddings `
  --include-summaries `
  --summary-provider openai `
  --summary-model gpt-5.6-luna `
  --summary-reasoning-effort low
```

`CODEMESH_OPENAI_URL` or `--openai-url` may override the default
`https://api.openai.com/v1` endpoint for a compatible gateway. Never commit
`OPENAI_API_KEY`. OpenAI is an online provider: confirm that the repository is
approved for external processing and review
[Security And Redaction](docs/security-and-redaction.md) and
[Summary Model Qualification](docs/summary-model-qualification.md) before
sending source code. When returned by the provider, input, cached-input,
cache-write input, output, reasoning, and total token counts are stored in the
summary metadata for later qualification and cost analysis. Use
`--summary-reasoning-effort` or
`CODEMESH_OPENAI_REASONING_EFFORT` to select an explicit provider effort. When
omitted, CodeMesh leaves the field unset and the selected OpenAI model applies
its provider default. The requested setting, response-effective setting,
API-returned model identity, and service tier are stored with every successful
summary.

Summaries are stored in MongoDB `node_summaries` by default and are keyed by
repository, node, content hash, summary kind, provider, model, prompt version,
and a generation-configuration fingerprint. Incremental ingestion skips only
unchanged completed summaries generated with the same budget policy and
provider configuration. Use `--force-summaries` to regenerate summaries even
when all identity inputs are unchanged. On first summary-store access after this
upgrade, CodeMesh replaces the legacy MongoDB `node_summary_identity` index with
the generation-aware `node_summary_identity_v2` index.

Summary generation assigns each eligible node a deterministic `compact`,
`standard`, `complex`, or `aggregate` budget from its node kind, source span,
input size, truncation state, and available parser complexity metadata. The
prompt varies from one concise sentence for compact nodes to 3-5 sentences for
aggregate nodes. Reasoning-capable models receive a 1,024-token ceiling for
compact and standard nodes and a 1,536-token ceiling for complex and aggregate
nodes by default; generation stops earlier when the model finishes.

Tune the shared policy for a provider or host from the CLI:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root D:\source\repos\YoutubeDownloader `
  --solution D:\source\repos\YoutubeDownloader\YoutubeDownloader.slnx `
  --skip-embeddings `
  --include-summaries `
  --summary-provider lmstudio `
  --summary-model ornith-1.0-9b@q4_k_s `
  --summary-max-input-chars 4000 `
  --summary-reasoning-token-reserve 768 `
  --summary-max-completion-tokens 1536
```

The selected tier, visible-token target, reasoning reserve, effective
completion ceiling, input size, truncation state, policy version, and generation
configuration fingerprint are stored with each generated summary. Changing the
prompt version, budget configuration, or provider generation configuration
regenerates summaries automatically.

Each successful ingestion run stamps graph, content, vector, and summary records with a repository id and ingestion run id. CodeMesh also writes repository/run registry records to MongoDB so users and agents can discover indexed repositories and recent ingestion history. Repository registry records include a generated alias, for example `YoutubeDownloader` becomes `youtube_downloader`, and read commands accept either the hash id or alias. Incremental ingestion skips unchanged graph/content/vector/summary writes after parsing, then removes stale records from the same repository that were not seen in the current run. If `--skip-embeddings` is used, vector cleanup is skipped so existing embeddings are left untouched.

Use `refresh` during normal development to re-run the same incremental ingestion path for the current repository:

```powershell
dotnet run --project src/CodeMesh.Cli -- refresh --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- refresh --include-summaries --skip-embeddings
```

`refresh` resolves the current CodeMesh workspace root when run from a nested directory, auto-selects a top-level C# solution when one is unambiguous, and accepts the same ingestion store, embedding, summary, language, project, and output options as `ingest`.

Use `watch` when you want CodeMesh to run an initial refresh and then refresh again after repository file changes:

```powershell
dotnet run --project src/CodeMesh.Cli -- watch --skip-embeddings
dotnet run --project src/CodeMesh.Cli -- watch --skip-embeddings --poll-seconds 2 --max-runs 3
dotnet run --project src/CodeMesh.Cli -- watch --dry-run --skip-embeddings --run-once
```

`watch` uses the same target resolution and ingestion options as `refresh`. It ignores common generated directories such as `.git`, `bin`, `obj`, `node_modules`, `.venv`, `dist`, and `build` when checking for file changes. Use `--run-once` or `--max-runs` for bounded automation.

Index runtime/deployment artifacts with:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest --root . --language deployment --skip-embeddings
```

The deployment parser currently handles `Dockerfile`, `*.Dockerfile`, `.dockerfile`, `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, and `compose.yaml`. It emits `Dockerfile`, `DockerfileStage`, `ComposeFile`, and `ComposeService` graph nodes with metadata for images/build contexts, ports, environment keys, volumes, and `depends_on` service relationships.

Query the registry:

```powershell
dotnet run --project src/CodeMesh.Cli -- repos list
dotnet run --project src/CodeMesh.Cli -- repo show <repository-id-or-alias>
dotnet run --project src/CodeMesh.Cli -- repo delete <repository-id-or-alias>
dotnet run --project src/CodeMesh.Cli -- runs list --repository-id <repository-id-or-alias> --limit 10
dotnet run --project src/CodeMesh.Cli -- summaries coverage <repository-id-or-alias>
dotnet run --project src/CodeMesh.Cli -- embeddings verify <repository-id-or-alias> --embedding-provider ollama --embedding-model nomic-embed-text-v2-moe:latest
dotnet run --project src/CodeMesh.Cli -- embeddings verify <repository-id-or-alias> --embedding-provider lmstudio --embedding-model text-embedding-nomic-embed-text-v2-moe
```

`repo delete` resolves aliases through the registry, then removes that repository's graph records from Neo4j, content and node summaries from MongoDB, vectors from Qdrant, and repository/run registry records from MongoDB.

Start the default local stores and services:

```powershell
copy .env.example .env
docker compose up -d neo4j mongodb qdrant csharp-parser agent-access
```

Run the end-to-end smoke script against live stores and Agent Access:

```powershell
.\scripts\e2e-smoke.ps1
```

Run deterministic MCP tool evaluations without live stores:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval
```

By default the script creates a tiny C# fixture repository under a unique `.codemesh-smoke` run directory, starts Neo4j, MongoDB, Qdrant, and Agent Access, ingests the fixture without embeddings, verifies `/repositories`, `/context/search`, `/symbols/search`, and `/context/package`, then deletes the indexed fixture through `DELETE /repositories/{repository_id}` and verifies the registry, runs, summaries, and search hits are gone. The context search check also validates response diagnostics, including search mode, vector hit count, and fallback status. To include embeddings, start your local model provider first and run, for example:

```powershell
.\scripts\e2e-smoke.ps1 -IncludeEmbeddings -EmbeddingProvider ollama -EmbeddingModel nomic-embed-text-v2-moe:latest
```

To run the same smoke checks against the configured sample repository from `CODEMESH_SAMPLE_CSHARP_ROOT` and `CODEMESH_SAMPLE_CSHARP_SOLUTION`, use:

```powershell
.\scripts\e2e-smoke.ps1 -UseConfiguredSample
```

To validate only the generated fixture path and cleanup behavior without starting Docker or ingesting code, use:

```powershell
.\scripts\e2e-smoke.ps1 -FixtureOnly
```

For LM Studio embeddings, start the LM Studio local server, load an embedding model, and run:

```powershell
.\scripts\e2e-smoke.ps1 `
  -IncludeEmbeddings `
  -EmbeddingProvider lmstudio `
  -EmbeddingModel text-embedding-nomic-embed-text-v2-moe `
  -LmStudioUrl http://127.0.0.1:1234/v1
```

To validate summary generation as well, load a local chat/code model and add the summary options:

```powershell
.\scripts\e2e-smoke.ps1 `
  -IncludeSummaries `
  -SummaryProvider lmstudio `
  -SummaryModel mistralai/ministral-3-3b `
  -LmStudioUrl http://127.0.0.1:1234/v1
```

To exercise the same smoke path with OpenAI, set `OPENAI_API_KEY` and use an
approved synthetic or non-sensitive fixture. This makes billable online API
requests:

```powershell
.\scripts\e2e-smoke.ps1 `
  -IncludeSummaries `
  -SummaryProvider openai `
  -SummaryModel gpt-5.6-luna `
  -OpenAiReasoningEffort low
```

### Ollama Modes

Native Windows Ollama is the recommended mode when you want GPU acceleration on Windows. Use `http://127.0.0.1:11434` for the host .NET CLI to avoid intermittent Windows `localhost` IPv6 probe timeouts; Dockerized Agent Access reaches the same Windows Ollama service through `http://host.docker.internal:11434`.

In `.env`, use:

```text
CODEMESH_MODEL_PROVIDER=ollama
CODEMESH_OLLAMA_URL=http://127.0.0.1:11434
CODEMESH_AGENT_OLLAMA_URL=http://host.docker.internal:11434
CODEMESH_EMBEDDING_MODEL=nomic-embed-text-v2-moe:latest
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

### LM Studio Mode

LM Studio uses the OpenAI-compatible local server. Start LM Studio's local server, load an embedding model such as `text-embedding-nomic-embed-text-v2-moe`, and confirm the model is listed:

```powershell
Invoke-RestMethod http://127.0.0.1:1234/v1/models
```

In `.env`, use:

```text
CODEMESH_MODEL_PROVIDER=lmstudio
CODEMESH_LM_STUDIO_URL=http://127.0.0.1:1234/v1
CODEMESH_AGENT_LM_STUDIO_URL=http://host.docker.internal:1234/v1
CODEMESH_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v2-moe
```

`CODEMESH_LM_STUDIO_URL` is used by the host .NET CLI. `CODEMESH_AGENT_LM_STUDIO_URL` is used by Dockerized Agent Access, where `host.docker.internal` points back to the Windows host running LM Studio. Leave `CODEMESH_EMBEDDING_MODEL` blank to use the provider default, or set it to the exact model listed by LM Studio. `text-embedding-nomic-embed-text-v1.5` is also valid if that is the embedding model loaded in LM Studio.

## Service Endpoints

- Agent Access REST: `http://localhost:8088`
- Agent Access local UI: `http://localhost:8088/ui`
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
- `POST /symbols/search`
- `POST /nodes/get`
- `POST /graph/neighbors`
- `GET /repositories`
- `GET /repositories/{repository_id}/summaries`
- `GET /repositories/{repository_id}`
- `GET /repositories/{repository_id}/status`
- `DELETE /repositories/{repository_id}`
- `GET /ingestion-runs`

Human-facing local UI routes:

- `GET /ui`
- `GET /ui/repositories`
- `GET /ui/repositories/{repository_id}`
- `GET /ui/runs`
- `GET /ui/search`

MCP tools:

- `codemesh_status`
- `codemesh_get_tool_guidance`
- `codemesh_search_context`
- `codemesh_get_context_package`
- `codemesh_search_symbols`
- `codemesh_get_node`
- `codemesh_get_neighbors`
- `codemesh_list_repositories`
- `codemesh_get_repository`
- `codemesh_get_repository_status`
- `codemesh_delete_repository` (requires `confirm = true`)
- `codemesh_get_summary_coverage`
- `codemesh_list_ingestion_runs`

`codemesh_get_tool_guidance` recommends which CodeMesh tools to use for common agent tasks such as freshness checks, implementation discovery, symbol lookup, relationship inspection, and package building. `codemesh_search_context` and `codemesh_get_context_package` accept the same core query controls as REST: `repository_id`, `kinds`, `filters`, explicit `vector` values, and context expansion limits. `codemesh_get_context_package` also accepts `output_format = "agent"` to return one compact text brief without duplicating the complete structured package. `codemesh_search_symbols` searches indexed symbols by name, id, display signature, namespace, or file path, and can include each symbol's primary declaration node. `codemesh_get_neighbors` accepts `relationship_kinds` when callers need to limit the relationship types returned.

See [Agent Access Contracts](docs/agent-access-contracts.md) for the REST, MCP, and .NET client contract reference.

PowerShell examples:

```powershell
Invoke-RestMethod http://127.0.0.1:8088/health
Invoke-RestMethod http://127.0.0.1:8088/repositories
Invoke-RestMethod http://127.0.0.1:8088/repositories/<repository-id-or-alias>/status
Invoke-RestMethod http://127.0.0.1:8088/repositories/<repository-id-or-alias>/summaries
Invoke-RestMethod -Method Delete http://127.0.0.1:8088/repositories/<repository-id-or-alias>
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

$symbolBody = @{
  query = 'DownloadAsync'
  repository_id = 'youtube_downloader'
  limit = 10
  kinds = @('Method')
  include_declarations = $true
} | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:8088/symbols/search -Method Post -ContentType 'application/json' -Body $symbolBody

$packageBody = @{
  query = 'download video with subtitles'
  repository_id = 'youtube_downloader'
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

For .NET callers, `CodeMesh.Control.AgentAccess.AgentAccessClient` provides typed methods for context search, context packages, symbol search, node lookup, neighbor lookup, repository listing, repository lookup/deletion, summary coverage, and ingestion-run listing using the contracts in `CodeMesh.Domain.Contracts`.

Direct CLI examples:

```powershell
cd agent-access
uv run python -m codemesh_agent_access status
uv run python -m codemesh_agent_access search "download video with subtitles" --repository-id youtube_downloader --limit 5 --kind Class
uv run python -m codemesh_agent_access search "download video with subtitles" --repository-id youtube_downloader --filter project=YoutubeDownloader --include-context-relationships
uv run python -m codemesh_agent_access symbols DownloadAsync --repository-id youtube_downloader --limit 10 --kind Method
uv run python -m codemesh_agent_access package "download video with subtitles" --repository-id youtube_downloader --limit 5 --max-characters 12000 --caller-limit 3 --callee-limit 3 --read-limit 2 --write-limit 2
uv run python -m codemesh_agent_access package "download video with subtitles" --repository-id youtube_downloader --filter filePath=YoutubeDownloader/Program.cs --no-repository
uv run python -m codemesh_agent_access package "download video with subtitles" --repository-id youtube_downloader --limit 3 --max-characters 6000 --caller-limit 2 --callee-limit 2 --read-limit 1 --write-limit 1 --output agent
uv run python -m codemesh_agent_access get-node csharp:type:CodeMesh.Tests.Neo4jSmokeSource --repository-id repo:neo4j-smoke --no-content
uv run python -m codemesh_agent_access neighbors csharp:type:CodeMesh.Tests.Neo4jSmokeSource --repository-id repo:neo4j-smoke --relationship-kind Contains
uv run python -m codemesh_agent_access repos --limit 10
uv run python -m codemesh_agent_access delete-repo <repository-id-or-alias>
uv run python -m codemesh_agent_access summaries <repository-id-or-alias>
uv run python -m codemesh_agent_access runs --repository-id <repository-id-or-alias> --limit 5
```

Set `CODEMESH_MODEL_PROVIDER=ollama` or `CODEMESH_MODEL_PROVIDER=lmstudio` for Agent Access when you want text queries embedded automatically before Qdrant search. Agent Access health and `codemesh status` validate that the configured embedding model is listed by the selected provider. If the configured model provider or Qdrant vectors are unavailable, Agent Access falls back to lexical Neo4j search. `/context/search` responses include `diagnostics` metadata with the selected mode (`vector`, `lexical`, or `hybrid`), returned vector/lexical hit counts, raw vector/lexical candidate counts, embedding source, and lexical fallback status.

Pass `repository_id` in REST/MCP context, node, and neighbor queries to constrain lookups to one ingested repository. The value can be the repository hash id or its generated alias. CLI commands accept the equivalent `--repository-id` option.

Context search results are ranked for agent usefulness. Agent Access merges vector hits, lexical graph hits, and generated-summary hits from MongoDB before deduping and ranking. Low-level matches such as parameter declarations are expanded to their defining symbol or containing method/type before they are returned, and each hit includes `repository_id`, `content_hash`, `score_components`, and `expanded_context` when expansion occurred. Use `expand_context=false` in REST/MCP or `--no-expand-context` in the CLI for compact raw hits. Use `include_context_relationships=true` or `--include-context-relationships` when each hit should include a small immediate relationship summary.

Context packages build on search results and return an agent-ready bundle with selected hits, normalized node metadata, generated node summaries when available, budgeted source snippets, immediate relationship summaries, repository metadata, and the latest ingestion run. Each item includes the flat `relationships` list plus `relationship_groups` for `callers`, `callees`, `reads`, `writes`, `contains`, `defines`, and `uses_types`. Relationship summaries are ordered for agent usefulness, prioritizing the primary declaration, enclosing owner, callers, callees, writes, reads, and type relationships before low-signal edges. Use `max_characters` / `--max-characters` to keep snippet output within a rough context budget, and use `caller_limit`, `callee_limit`, `read_limit`, `write_limit`, `contains_limit`, `definition_limit`, and `uses_type_limit` to cap noisy relationship groups inside the total `relationship_limit`. The package CLI defaults to JSON; pass `--output agent` for a concise text brief. MCP package calls default to structured JSON and can pass `output_format = "agent"` to return the same concise brief as one text content block without structured duplication.

Symbol search is for precise code navigation before requesting a full package. Use `/symbols/search`, `codemesh_search_symbols`, or the `symbols` CLI command when an agent already has a likely type/member name and needs the canonical node id, display metadata, location, and primary declaration.

## Development Notes

The old HelioGraph repository is reference-only. CodeMesh starts with clean contracts and intentionally thin adapters so the graph, content, vector, parser, and agent-access boundaries can harden independently.

The C# parser emits file, test file, namespace, declaration, type, member, test case, and relationship nodes using Roslyn. Partial types are represented as one logical symbol node plus separate declaration nodes. Method and member bodies also emit local semantic relationships such as `Invokes`, `Reads`, and `Writes` when the target symbol is part of the indexed code graph. Common .NET test attributes and CodeMesh-style `Test...` methods in test files are represented as `TestCase` nodes.
