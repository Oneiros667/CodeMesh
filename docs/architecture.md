# CodeMesh Architecture

CodeMesh is organized around a write-side ingestion pipeline and a read-side Agent Access surface.

## High-Level Flow

1. A repository is selected through CLI options or configuration.
2. A parser worker emits code nodes, relationships, diagnostics, and source spans.
3. Ingestion writes graph records, source content, vector embeddings, generated summaries, repository registry records, and ingestion run records.
4. Agent Access reads those stores through REST, MCP tools, Python CLI commands, and the .NET client.
5. Agents consume context search results, context packages, symbols, nodes, neighbors, repository metadata, and ingestion history while editing code.

## Components

### Domain

`src/CodeMesh.Domain` contains shared contracts and stable records used across the solution:

- Parser contracts.
- Ingestion contracts.
- Agent Access contracts.
- Graph types.
- Health contracts.
- Hashing, fingerprinting, and repository alias utilities.
- A shared repository path policy for excluding generated, cache, virtual-environment, smoke, and temporary directories.

### Ingestion

`src/CodeMesh.Ingestion` coordinates repository ingestion:

- Calls parser workers.
- Handles dry-run and persistent ingestion modes.
- Writes graph, content, vector, summary, registry, and run data.
- Performs incremental skip logic for unchanged records.
- Removes stale records from previous runs.
- Supports local embedding providers plus local and online summary providers.
- Assigns versioned summary complexity tiers from node kind, source size,
  truncation, and available parser metadata; the selected token budgets are
  persisted with each generated summary.

### Parser Workers

`src/CodeMesh.Parser.CSharp` is the C# parser worker:

- Exposes `/health`, `/capabilities`, and `/parse`.
- Uses Roslyn to parse solutions and projects.
- Emits file, test file, namespace, declaration, type, member, test case, and relationship nodes.
- Represents partial types as logical symbols plus declaration nodes.
- Detects common .NET test attributes and CodeMesh-style `Test...` methods in test files as `TestCase` nodes.
- Emits local semantic relationships such as `Invokes`, `Reads`, and `Writes`.

`src/CodeMesh.Parser.Python` is the local Python parser:

- Parses `.py` files from a repository root.
- Emits file, class, function, and async function nodes.
- Emits containment relationships based on indentation.
- Uses the shared repository path policy to exclude generated/cache directories such as `.venv`, `.tmp`, `__pycache__`, `.pytest_cache`, smoke output, and build output.
- Does not yet emit Python call/import/type relationships.

`src/CodeMesh.Parser.Deployment` is the local deployment artifact parser:

- Parses Dockerfiles and Docker Compose files from a repository root.
- Emits Dockerfile, Dockerfile stage, Compose file, and Compose service nodes.
- Captures runtime metadata such as base images, build contexts, ports, environment keys, volumes, and service dependencies.
- Emits containment relationships and `depends_on` service relationships.
- Uses the shared repository path policy to avoid generated, cache, virtual-environment, smoke, and temporary directories.
- Does not yet parse Kubernetes manifests, Helm charts, CI/CD workflows, or Compose override merge semantics.

`src/CodeMesh.Parser.Markdown` is the local Markdown parser:

- Parses `.md` and `.markdown` files from a repository root.
- Emits document and section nodes.
- Emits containment relationships from documents to headings and from parent headings to child headings.
- Stores heading level, anchor, file path, and document kind metadata.
- Uses the shared repository path policy to exclude generated, cache, virtual-environment, smoke, and temporary directories.

### Storage

`src/CodeMesh.Storage` contains write and read adapters:

- Neo4j for graph nodes and relationships.
- MongoDB for content, repository registry, ingestion runs, and node summaries.
- Qdrant for vector embeddings.
- In-memory storage for tests.

### Control And CLI

`src/CodeMesh.Control` and `src/CodeMesh.Cli` provide operator-facing behavior:

- Environment file loading.
- Workspace/configuration helpers.
- Status and doctor checks.
- Typed Agent Access .NET client.
- Ingestion, repository, run, summary, and embedding verification commands.

### Agent Access

`agent-access` is the Python read surface for agents:

- FastAPI REST endpoints.
- MCP tool manifest and handlers.
- Python CLI commands.
- Store read paths for graph, content, summaries, vectors, repositories, and ingestion runs.
- Context ranking, formatting, and package generation.

## Main Data Stores

- Graph: code structure and relationships in Neo4j.
- Content: source snippets and content metadata in MongoDB.
- Vectors: semantic embeddings in Qdrant.
- Summaries: generated node summaries in MongoDB.
- Registry: repository metadata and ingestion run history in MongoDB.

## Current Extension Points

- Add parser workers for more languages and artifact types.
- Add storage adapters behind existing contracts.
- Add Agent Access tools for new query patterns.
- Add context package enrichers for documentation, deployment, test, and SDLC metadata.
- Add model providers for embeddings and summaries.

## Planning References

- `docs/next-steps.md` prioritizes the next features needed for effective MCP agent use.
- `docs/graph-intelligence-design.md` proposes relationship evidence, graph
  analysis, explicit agent outcome memory, parser tiers, and portable snapshots.
- `docs/sdlc-roadmap.md` describes broader SDLC intelligence goals.
