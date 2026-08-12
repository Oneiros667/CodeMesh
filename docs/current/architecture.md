# CodeMesh Architecture

Document type: current implementation reference

CodeMesh is organized around a write-side ingestion pipeline and a read-side Agent Access surface.

## Product Boundary

The architecture is service-capable, but the initial product wedge is narrower:
source-grounded context and change-impact support for agents working in C#/.NET
repositories. The primary agent questions are:

- Where is the relevant implementation?
- What code and behavior are likely affected by this change?
- Which tests and validation commands provide the best evidence?

Freshness, repository scoping, source spans, and compact context packages are
part of the core product. Generated summaries, embeddings, additional parser
languages, deployment intelligence, UI expansion, and broader SDLC artifacts
are optional enrichments until controlled evaluation shows that they improve
agent outcomes. Graph paths and generated summaries remain navigation evidence,
not source truth.

## High-Level Flow

1. A repository is selected through CLI options or configuration.
2. A parser worker emits code nodes, relationships, diagnostics, and source spans.
3. Ingestion computes a deterministic snapshot id, stages graph records, source content, vector embeddings, generated summaries, repository registry records, and ingestion run records under that snapshot namespace.
4. The registry atomically publishes checkout-current and eligible clean branch-head slots; failed or stale generations do not replace active slots.
5. Agent Access resolves a project, alias, or snapshot reference to an active snapshot and reads the stores through REST, MCP tools, Python CLI commands, and the .NET client.
6. Agents consume context search results, context packages, symbols, nodes, neighbors, repository metadata, and ingestion history while editing code.

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
- Resolves persistent project and checkout identity from private Git/local markers.
- Computes deterministic source snapshots and stages cross-store generations.
- Publishes checkout-current and clean branch-head slots with compare-and-swap semantics.
- Writes graph, content, vector, summary, registry, and run data.
- Performs incremental skip logic for unchanged records.
- Removes stale records from previous runs.
- Marks unreferenced snapshots collectible and supports retryable cross-store garbage collection.
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

- Graph: snapshot-namespaced code structure and relationships in Neo4j.
- Content: content-addressed source snippets with snapshot references in MongoDB.
- Vectors: snapshot-namespaced semantic embeddings in Qdrant.
- Summaries: snapshot-namespaced generated node summaries in MongoDB.
- Registry: projects, checkouts, snapshots, observations, slots, generations,
  repository metadata, and ingestion run history in MongoDB.

## Current Extension Points

- Add parser workers for more languages and artifact types.
- Add storage adapters behind existing contracts.
- Add Agent Access tools for new query patterns.
- Add context package enrichers for documentation, deployment, test, and SDLC metadata.
- Add model providers for embeddings and summaries.

## Planning References

- [Project Status](project-status.md) records the current implementation and
  evidence snapshot without changing this architecture reference.
- [Next Steps](../planning/next-steps.md) prioritizes future product work.
- [Graph Intelligence and Agent Memory](../planning/graph-intelligence-design.md) proposes
  relationship evidence, graph analysis, explicit agent outcome memory, parser
  tiers, and portable snapshots.
- [Repository Identity and Snapshot Retention](../planning/repository-identity-and-snapshot-retention.md)
  records implemented local multi-checkout identity and bounded retention plus
  future shared-store requirements.
- [SDLC Roadmap](../planning/sdlc-roadmap.md) describes broader SDLC intelligence goals.
