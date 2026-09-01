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

For one atomic Python/Rust snapshot, select both languages in one ingestion;
do not run separate replacement ingestions:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root $repositoryRoot `
  --languages python,rust `
  --skip-embeddings
```

Known secret files are excluded by default. To restrict a repository further,
repeat repository-relative allow or deny globs; deny patterns take precedence:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root $repositoryRoot `
  --languages python,rust `
  --allow-path "app/**" `
  --allow-path "native/**" `
  --deny-path "app/generated/**" `
  --skip-embeddings
```

Use `--include-known-secret-files` only after reviewing the broadened scope. It
does not disable value redaction, configured deny patterns, or generated/cache
directory exclusions. See [Security and Redaction](../current/security-and-redaction.md).

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
uv run python -m codemesh_agent_access mcp --profile normal
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
    "mcp",
    "--profile",
    "normal"
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
        "mcp",
        "--profile",
        "normal"
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
    "Set-Location 'C:\\path\\to\\CodeMesh\\agent-access'; uv run python -m codemesh_agent_access mcp --profile normal"
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

The `normal` profile is the default and exposes only the context-package,
repository-status, repository-listing, and node-read tools. Use
`--profile diagnostic` for non-destructive operational investigation. Unknown
profile names fail before server startup, and neither profile exposes repository
deletion.

## Repository Agent Onboarding

Explicit repository onboarding is the selected v1 product contract. MCP server
instructions remain defense in depth because hosts differ in whether and how
they present those instructions to an agent. Generate a reviewable exact-
checkout plan after ingestion reports the project, checkout, snapshot, and
source-view identities:

```powershell
Set-Location agent-access
uv run python -m codemesh_agent_access install plan `
  --target-root C:\path\to\checkout `
  --codemesh-root C:\path\to\CodeMesh `
  --project-id prj_EXACT `
  --checkout-id chk_EXACT `
  --source-view-hash HASH_FROM_INGESTION `
  --output C:\temp\codemesh-install-plan.json
```

Review the plan's exact launch, binding, complete file contents, diffs, target
hashes, forwarded environment names, and `plan_hash`. Apply only that unchanged
plan and hash, then run the live provider-free probe:

```powershell
uv run python -m codemesh_agent_access install apply `
  C:\temp\codemesh-install-plan.json `
  --approve-plan-hash REVIEWED_HASH
uv run python -m codemesh_agent_access mcp-probe `
  --plan C:\temp\codemesh-install-plan.json
```

The default plan manages `.codex/config.toml` and a marked onboarding block in
`AGENTS.md` while preserving other content. Use `--configuration-only` only when
an external instance manager owns repository guidance. Apply rejects a changed
target or plan. The generated config forwards secret variable names, never
their values, and forces provider mode to `none`.

The bound normal server requires an exact project, checkout, and root. Its tools
inject that project selector and reject caller overrides. Start with
`codemesh_get_context_package` using concise implementation concepts and exact
identifiers from the task with agent output. For multi-part impact work, use a
small set of focused package queries for distinct implementation and test
facets rather than one long full-task query. The package validates the binding
and freshness before search; dirty, moved, stale, missing, or source-view-
mismatched checkouts fail closed. Use repository status only for explicit
ingestion, count, or freshness diagnostics.

## Agent Feedback

Participating repositories must ignore `/.codemesh-feedback/` before recording.
Agents can then write a bounded diagnostic packet with explicit path categories
and the accepted status provenance:

```powershell
uv run python -m codemesh_agent_access feedback record `
  --repository-root C:\path\to\checkout `
  --role primary `
  --classification diagnostic `
  --confidence high `
  --project-id prj_EXACT `
  --checkout-id chk_EXACT `
  --snapshot-id snp_EXACT `
  --language python --language rust `
  --parser-profile python-rust-v1 `
  --task-family test-selection `
  --issue-category ranking `
  --validation-outcome failed `
  --missed-path tests/test_expected.py
```

Use `feedback validate PACKET` before review. CodeMesh maintainers run
`feedback summarize CHECKOUT... --output SUMMARY.json` to group open failures
without losing commit/snapshot provenance. A passing recheck may use
`--supersedes-feedback-id` to resolve an exact earlier failure. Never store raw
prompts, MCP payloads, source excerpts, secrets, or environment values in a
packet.

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

The default `normal` profile exposes:

- `codemesh_list_repositories`: find indexed repositories and aliases.
- `codemesh_get_repository_status`: inspect latest run, counts, summary coverage, and freshness diagnostics.
- `codemesh_get_context_package`: return an agent-ready bundle of code, summaries, relationships, and repository metadata.
- `codemesh_get_node`: retrieve a known node and optional content.

The `diagnostic` profile additionally exposes:

- `codemesh_status`: check service and store health.
- `codemesh_get_tool_guidance`: recommend which CodeMesh tools to use for a natural-language agent task.
- `codemesh_search_context`: search for relevant implementation context.
- `codemesh_search_symbols`: find precise symbols before expanding context.
- `codemesh_get_neighbors`: inspect graph relationships around a node.
- `codemesh_get_repository`: inspect one repository registry record.
- `codemesh_get_summary_coverage`: inspect generated-summary coverage.
- `codemesh_list_ingestion_runs`: inspect recent indexing runs.

## Troubleshooting

- If MCP starts but returns no useful context, confirm the repository was ingested with `repos list`.
- If the MCP client says the server exited immediately, run `cd agent-access; uv run python -m codemesh_agent_access mcp --profile normal` in a terminal to see import, profile, or environment errors.
- If vector search is unavailable, check `status`; Agent Access should fall back to lexical search when possible.
- If context search fails with request validation errors, confirm the MCP client is sending arrays for `kinds`, `filters`, and `vector` only when values are present.
- If store connection checks fail from MCP but Docker services are running, confirm the MCP environment uses `127.0.0.1` store URLs rather than Docker service names such as `mongodb` or `qdrant`.
- If Python import errors occur, run the MCP command from `agent-access` with `uv run`.
- If Dockerized Agent Access cannot reach host model providers, use `host.docker.internal` URLs in `.env`.
- If a repository looks stale, run ingestion again and check `runs list`.
- Do not paste `.env` contents into chat or issue logs. Report variable names and redacted values only.
