# CodeMesh Next Steps For Effective MCP Agent Use

CodeMesh already has an Agent Access surface with REST, MCP tools, CLI commands, repository registry records, context search, context packages, symbol search, node lookup, graph neighbors, summaries, and ingestion history.

This document prioritizes the features that would make CodeMesh effective as an MCP service used by AI agents, including agents analyzing CodeMesh itself.

`docs/graph-intelligence-design.md` records a planning-only design for
relationship evidence, deterministic graph analysis, explicit agent outcome
memory, parser tiers, portable snapshots, and graph-derived reports.

`docs/summary-model-qualification.md` records a planning-only procedure for
qualifying local or online ingestion summary models using accuracy, reliability,
speed, token efficiency, privacy, cost, and downstream retrieval evidence.

## Current Project State Review

Review date: 2026-08-12.

Recent completed work:

- Local-first MCP readiness: self-ingestion, MCP setup docs, repository freshness/status, redaction, Python parsing, and Markdown parsing are implemented.
- Human inspection: Agent Access serves a local read-only UI at `/ui` for service health, repositories, repository status, ingestion runs, and context search.
- Agent packaging: `agent_text` context packages include stable item metadata, rationale, snippets before relationships, and budget-aware truncation.
- Agent guidance: `codemesh_get_tool_guidance` and `uv run python -m codemesh_agent_access tool-guidance "<task>"` recommend tool workflows for common agent tasks.
- Incremental ingestion internals exist for graph, content, vectors, and summaries, including skipped unchanged records and stale cleanup.
- `codemesh refresh` provides a first-class local command over the existing incremental ingestion path for the current repository.
- `codemesh watch` runs an initial refresh, polls the repository for file changes, and refreshes again when source files change.
- Repository status and the local repository detail UI show a derived latest refresh outcome, including skipped, completed, failed, dry-run, running, no-run, and recommended-action states.
- `src/CodeMesh.Parser.Deployment` provides first-slice Dockerfile and Docker Compose ingestion for stages, services, ports, environment keys, volumes, and service dependencies.
- Context packages include validation recommendations inferred from packaged file paths, covering .NET tests, Agent Access Python tests/lint, deployment dry-runs, smoke checks, and Markdown dry-runs.
- `uv run python -m codemesh_agent_access eval` runs deterministic MCP fixture evaluations for tool guidance, search diagnostics, context packages, freshness, and redaction leakage.
- `uv run python -m codemesh_agent_access eval live` exercises real MCP stdio transport and scores CodeMesh self-analysis retrieval, freshness, reliability, latency, and redaction.
- `uv run python -m codemesh_agent_access eval agent --model <model-id>` runs an opt-in isolated control/treatment comparison with a Codex adapter and versioned agent tasks.
- C# ingestion emits first-class `TestFile` and `TestCase` nodes for common .NET test attributes and convention-based CodeMesh test methods.
- Parsers and watch mode share a default repository path policy that excludes generated, cache, virtual-environment, smoke, and temporary directories.
- Agent Access declares `pytest` and `ruff` as development dependencies, making documented verification commands reproducible after `uv sync`.
- The versioned `codemesh-model` benchmark adds graded repository questions,
  paired repair scenarios, review packets, and control/treatment comparison.
- Summary generation now supports complexity-aware budgets, local providers, an
  OpenAI provider, generation-configuration identity, and provider-reported
  usage metadata where available.
- The `youtube-downloader-live` and `youtube-downloader-agent` suites pin a
  representative external C# repository and fail closed when the indexed commit
  does not match the suite commit.
- Explicit CLI solution and project paths resolve from either the repository
  root or caller directory and fail fast when missing, preventing an explicit
  semantic-ingestion target from silently degrading to filesystem parsing.
- The `config-net-cache-live` and `config-net-cache-assisted-agent` suites pin
  an independent MIT-licensed C# repository and cache-coherence impact task for
  the next assisted product-proof replication.
- MCP initialization now publishes the efficient default-package plus targeted-
  read workflow as canonical server instructions, and
  `config-net-cache-agent` freezes the same independent task without
  treatment-only guidance for normal-host discoverability evaluation.
- The C# parser resolves cross-project invocations through Roslyn documentation
  ids as well as CodeMesh stable keys, while preserving ambiguity fail-closed
  behavior.
- Agent citation grading preserves hidden paths such as `.github` and safely
  normalizes absolute citations inside isolated evaluation workspaces.
- Agent comparison reports retain overall timing and token medians but attribute
  correctness and efficiency only to matched pairs that actually called a
  CodeMesh tool.
- Lexical task retrieval removes grammatical noise, prioritizes terms in symbol
  and file names, and diversifies the pre-expansion candidate pool across files.

Current state:

- The ingestion and Agent Access baseline is implemented enough for active local
  dogfooding, but that is a technical-readiness statement rather than proof of
  agent benefit.
- The strongest current parser and initial product wedge is C#/.NET. Python,
  Markdown, and deployment parsing provide useful supporting context but do not
  yet offer comparable semantic relationship depth.
- Operational freshness is covered for local development by manual refresh and a local watch command.
- MCP evaluation includes deterministic fixtures, live self-analysis and pinned
  external C# golden queries, and opt-in agent A/B and model harnesses.
  Deterministic success proves contracts, not usefulness.
- The summary-free pinned YoutubeDownloader live suite passes all six cases with
  complete expected target and relationship coverage. Two corrected
  three-repeat agent campaigns completed all nine pairs with equal 100% task
  success but zero CodeMesh adoption, including after task-oriented MCP
  descriptions were made canonical across the server and stable manifest.
  Their overall timing and token variation cannot be attributed to CodeMesh.
- The separate complex output-container live task improved from 50% to 100%
  recall after the smallest measured ranking change, while the original external
  and CodeMesh live suites remained fully green. Its three-repeat spontaneous
  agent campaign also passed every pair but still made zero CodeMesh calls,
  despite median runs consuming roughly 600,000 tokens. Complexity within this
  two-project repository did not solve discovery.
- The first valid onboarding-assisted complex campaign achieved 100% CodeMesh
  adoption and 100% task success after the non-interactive MCP approval gate was
  corrected, but regressed median elapsed time by 56.3% and tokens by 57.4%.
  Treatments requested a 30,000-character package and still ran 20 to 32 shell
  commands, so adoption and correctness did not establish efficiency or benefit.
- After capping MCP agent briefs at 12,000 characters and focusing onboarding on
  default limits plus targeted batched citation reads, the same three-pair suite
  retained 100% adoption and task success and produced an `improved` verdict.
  Median elapsed time fell 34.7%, median tokens fell 64.5%, and treatments used
  2 to 4 shell commands versus 14 to 18 for controls. This is attributable
  best-case utility evidence for one assisted task, not prompt-parity,
  spontaneous-adoption, or cross-task generalization evidence.
- No summary model is CodeMesh-qualified. Existing manual results are research
  evidence and generated summaries remain optional.
- The independent Config.Net summary-free live gate passed comparably at clean
  CodeMesh commit `d764270`: all 18 calls succeeded, recall and MRR were 1.0,
  nDCG was 0.93483, and no secret leaks were detected.
- The three-pair Config.Net assisted campaign also produced an `improved`
  verdict. All treatments passed versus one of three controls, yielding two
  CodeMesh-attributable correctness wins, 100% adoption, no safety violations,
  and 11.8% lower median elapsed time. Treatment median tokens were 3.0% higher.
  This independently replicates assisted utility, but still does not establish
  prompt-parity discovery or broad generalization.
- The immediate product gap is now discoverability evidence that a normal agent
  host consumes the canonical MCP initialization instructions and selects the
  efficient workflow without evaluator-only guidance.

Current priority judgment:

1. Keep the clean CodeMesh and pinned YoutubeDownloader live baselines passing
   without generated summaries.
2. Retain the spontaneous zero-adoption results without crediting run variance
   to CodeMesh.
3. Retain the focused onboarding-assisted complex result as first product-proof
   evidence, with its one-task and prompt-parity limitations explicit.
4. Retain the improved independent Config.Net assisted campaign as replicated
   product-proof evidence, with its prompt-parity and one-task limits explicit.
5. Evaluate canonical MCP initialization instructions through the frozen
   prompt-parity `config-net-cache-agent` suite. Do not count implementation or
   fixture tests as normal-host adoption evidence.
6. Repeat the same frozen evaluations after each material tool-selection,
   ranking, packaging, or relationship change. Correctness and safety win; time
   and token improvement count only when correctness is preserved.
7. Implement the summary-model qualification runner only before summaries are
   considered for default retrieval. Require factual, reliability, safety, and
   no-summary retrieval comparisons.
8. Defer Kubernetes/Helm, additional parser breadth, outcome memory, UI
   expansion, portable snapshots, and broader SDLC ingestion until the initial
   C# agent workflow shows repeatable benefit.
9. Keep secret-file exclusion and configurable allow/deny policy as a release
   gate before any future broad artifact ingestion.

## P0 - Technical MCP Baseline

These capabilities make CodeMesh operable and testable as a local MCP service.
They do not by themselves establish that an agent performs better with CodeMesh.

### 1. Self-Ingestion Workflow

Add a first-class command or documented preset for indexing the CodeMesh repository itself.

Current implementation:

- `dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings`
- `dotnet run --project src/CodeMesh.Cli -- self ingest --dry-run --skip-embeddings`
- `dotnet run --project src/CodeMesh.Cli -- self smoke --skip-embeddings`
- `self smoke` validates live Agent Access through the typed .NET REST client; it does not validate MCP stdio transport.

Expected outcome:

- A repeatable `codemesh self ingest` or equivalent documented command.
- Automatic discovery of the repository root and `CodeMesh.sln` when run from
  anywhere inside the checkout.
- Clear support for dry-run, no-embedding, embedding, and summary modes.
- A smoke check that verifies CodeMesh appears in `repos list` and can answer at least one Agent Access context query.

Why it matters:

Dogfooding CodeMesh against itself is the fastest way to expose weak context packaging, stale index problems, missing parser coverage, and awkward MCP tool contracts.

### 2. MCP Client Configuration Guide

Add ready-to-use MCP configuration examples for common agent hosts.

Current implementation:

- `docs/mcp-setup.md` documents local stdio MCP startup through `uv run python -m codemesh_agent_access mcp`.
- It includes command/args examples, `mcpServers` JSON, a PowerShell wrapper for clients without `cwd`, required environment variables, model-provider variants, and troubleshooting.

Expected outcome:

- A doc covering how to run `codemesh_agent_access mcp` from the local `agent-access` project.
- Example configuration for stdio-based MCP clients.
- Required environment variables listed in one place.
- A troubleshooting section for store connectivity, Python environment issues, and model-provider failures.

Why it matters:

The service is only useful to agents if it is easy to attach reliably. MCP setup should not require reading implementation files.

### 3. Index Freshness And Repository Status

Expose freshness diagnostics directly through MCP.

Current implementation:

- `GET /repositories/{repository_id}/status` returns registry metadata, latest run, counts, summary coverage, and local git freshness diagnostics.
- `codemesh_get_repository_status` exposes the same status bundle through MCP.
- `uv run python -m codemesh_agent_access repo-status <repository-id-or-alias>` exposes it through the Python CLI.
- `AgentAccessClient.GetRepositoryStatusAsync` exposes it to .NET callers.
- Ingestion stamps the current Git commit, branch, and origin URL into repository registry records when the source root is a Git checkout. Older records without a commit remain `unknown` until they are re-ingested.

Expected outcome:

- Repository status reports the latest ingestion run, indexed commit SHA when available, current working tree commit when available, and whether the index appears stale.
- Repository-level counts for graph nodes, content documents, vectors, and summaries.
- Clear diagnostics when vectors or summaries are missing for a repository.

Why it matters:

Agents need to know whether returned context reflects the code they are editing. Stale context is worse than no context when making changes.

### 4. Secret And Sensitive-File Redaction

Add explicit guardrails before broadening MCP access to repository content.

Current implementation:

- Ingestion redacts sensitive-looking values before persistence, embeddings, and summaries.
- Redacted content is stored under a new content hash, and graph nodes are remapped to that hash.
- Ingestion emits `CMSEC001` when redaction changes content.
- Supported parsers share default exclusions for generated, cache, virtual-environment, smoke, and temporary directories.
- Current redaction covers private key blocks, environment-style key/value secrets, JSON secret values, C# string assignments with sensitive names, and connection-string password fragments.
- Known secret-file exclusion and configurable allow/deny lists remain future work, especially for Markdown, deployment, and SDLC artifact ingestion.

Expected outcome:

- Default exclusion or redaction for `.env`, secret files, private keys, tokens, certificates, and common credential formats.
- A documented allowlist/denylist model for ingestion.
- MCP responses that never emit known secret values.
- Tests covering representative secret patterns.

Why it matters:

An MCP context service will put repository content directly in front of agents. Redaction needs to be boring, predictable, and on by default.

## P1 - High-Impact Agent Usefulness

The numbered capability inventory below preserves implemented behavior and
longer-lived backlog context. It is not the current execution order; use the
priority judgment and near-term recommended order above and below.

### 5. Python Parser Support

Add structured Python ingestion for the `agent-access` project.

Current implementation:

- `src/CodeMesh.Parser.Python` parses `.py` files locally.
- It emits file, class, method/function, async function, and containment graph records.
- `dotnet run --project src/CodeMesh.Cli -- ingest --root .\agent-access --language python --dry-run --skip-embeddings` validates the Agent Access tree.
- Current parser scope is syntax-light and indentation-based; import, call, route-handler, MCP-handler, and test-coverage relationships remain future work.

Expected outcome:

- Python modules, classes, functions, imports, routes, CLI commands, MCP tools, and tests represented as typed graph nodes.
- Relationships for imports, calls where practical, route handlers, tool handlers, and test coverage links.
- CodeMesh self-analysis covers both the .NET ingestion/control code and the Python Agent Access service.

Why it matters:

CodeMesh currently includes important Python implementation code. Without Python parsing, self-analysis is incomplete and agents miss the MCP service internals.

### 6. Documentation And Markdown Ingestion

Index repository documentation as first-class context.

Current implementation:

- `src/CodeMesh.Parser.Markdown` parses `.md` and `.markdown` files locally.
- It emits `Document` and `Section` nodes, heading anchors, heading levels, source spans, and `Contains` relationships.
- It uses the shared repository path policy to avoid indexing generated and vendored documentation under directories such as `.venv` and `.tmp`.
- `dotnet run --project src/CodeMesh.Cli -- ingest --root . --language markdown --dry-run --skip-embeddings` validates repository documentation parsing.
- Current parser scope is Markdown structure only; cross-links from docs to commands, endpoints, tools, source files, and projects remain future work.

Expected outcome:

- README, roadmap, next-step, contract, and architecture docs ingested as document nodes with headings, anchors, and source spans.
- Relationships from docs to referenced projects, commands, endpoints, tools, and files where detectable.
- Context packages that can include both implementation code and relevant documentation.

Why it matters:

Agents need project intent, usage contracts, and operational instructions, not only code symbols.

### 7. Context Package Quality Gates

Harden context packages for direct use in agent prompts.

Current implementation:

- MCP `output_format = "agent"` and CLI `--output agent` produce compact agent text; MCP agent mode returns one text content block without redundant structured serialization and caps the brief at 12,000 characters.
- Agent text now includes each item's file span, node id, stable key, repository id, content hash, score, rank, and rationale details.
- Agent text applies the context package `max_characters` budget for MCP and CLI output and emits an explicit truncation marker when capped.
- Snippets are emitted before relationship detail so the most directly actionable content is preserved first under tight budgets.

Expected outcome:

- Stable, compact `agent_text` output optimized for MCP callers.
- Clear file paths, line ranges, node ids, repository ids, and content hashes on every item.
- Budget controls that preserve high-value snippets before lower-value relationship detail.
- Rationale explaining why each item was included.
- Tests that snapshot package shape for representative queries.

Why it matters:

Search is useful for discovery, but agents need packaged context that can be trusted and pasted into reasoning without manual cleanup.

### 8. Local Web Inspection UI

Add a local, read-only web interface for humans to inspect CodeMesh state without switching between CLI, REST JSON, and MCP clients.

Current implementation:

- `/ui` shows service health, repository summaries, recent ingestion runs, and a search form.
- `/ui/repositories` lists indexed repositories.
- `/ui/repositories/{repository_id}` shows repository freshness, counts, metadata, and recent runs.
- `/ui/runs` shows ingestion history with optional repository filtering.
- `/ui/search` provides read-only context search over the existing Agent Access store.

Expected outcome:

- A local-first dashboard served by the Agent Access FastAPI service.
- Clear visibility into ingestion state, freshness, repository counts, and recent failures.
- Search and inspection workflows that help humans validate what agents will see through MCP.
- Future write actions, such as triggering ingestion or deleting repositories, gated behind explicit local controls and stronger access rules if exposed remotely.

Why it matters:

Agents need reliable context, and humans need a quick way to audit whether that context is fresh, complete, and safe before delegating work.

### 9. Query Planning And Tool Guidance

Help agents choose the right CodeMesh tool for a task.

Current implementation:

- `codemesh_get_tool_guidance` recommends tool workflows for optional natural-language task text.
- `uv run python -m codemesh_agent_access tool-guidance "<task>"` exposes the same guidance through the Python CLI.
- The MCP manifest descriptions now say when to use search, context packages, symbol search, node lookup, neighbors, repository listing, freshness status, and ingestion runs.
- Current guidance covers freshness checks, implementation discovery, symbol lookup, relationship inspection, agent context package preparation, operational checks, and explicit repository deletion.

Expected outcome:

- A lightweight MCP tool or doc section that describes when to use context search, context package, symbol search, node lookup, neighbors, repository list, and ingestion runs.
- Better tool descriptions in the MCP manifest.
- Example task-to-tool mappings, such as "find implementation", "inspect callers", "check freshness", and "summarize a component".

Why it matters:

MCP tools are most effective when agents can select them without trial and error.

## P2 - Production-Grade MCP Reliability

These items remain relevant to product quality, but only test/validation,
evaluation, or operational work required by the current product-proof campaign
should interrupt that campaign.

### 10. Watch Or Incremental Refresh Mode

Add a convenient way to keep an indexed repository close to current.

Current implementation:

- Ingestion already performs incremental graph, content, vector, and summary writes where supported.
- Existing tests cover unchanged-record skips, forced embedding rebuilds, unchanged-summary skips, and stale cleanup.
- Ingestion result stats report parsed, written, skipped, and summary counts.
- `dotnet run --project src/CodeMesh.Cli -- refresh --skip-embeddings` reuses the incremental ingestion path for the current repository.
- `refresh` resolves the current CodeMesh workspace root when run from nested directories and auto-selects a top-level C# solution when one is unambiguous.
- `dotnet run --project src/CodeMesh.Cli -- watch --skip-embeddings` runs an initial refresh and then refreshes again after repository file changes.
- `watch` supports `--poll-seconds`, `--max-runs`, and `--run-once` for local use and bounded automation.
- Watch snapshots use the same generated/cache directory exclusions as parser enumeration.
- `GET /repositories/{repository_id}/status`, `codemesh_get_repository_status`, and `/ui/repositories/{repository_id}` show a derived `refresh` block for the latest run.
- The current watch loop is CLI-local and polling-based; native file-system events and UI visibility remain future improvements.

Expected outcome:

- A cheap `refresh` command for the current repository that reuses existing incremental ingestion behavior.
- A local watch command after refresh semantics are stable.
- Incremental parse/write behavior that is fast enough for normal development loops.
- Status diagnostics showing when a refresh is running, completed, failed, or skipped.

Why it matters:

Agents work against changing files. Manual full ingestion before every useful query is too heavy.

### 11. Runtime And Deployment Artifact Ingestion

Implement the first slice of the SDLC roadmap for production-aware context.

Current implementation:

- `docs/sdlc-roadmap.md` defines target runtime/deployment artifacts and graph concepts.
- CodeMesh has Docker Compose and Dockerfile assets for its own runtime.
- `src/CodeMesh.Parser.Deployment` parses Dockerfiles and common Docker Compose file names as first-class graph nodes.
- `dotnet run --project src/CodeMesh.Cli -- ingest --root . --language deployment --dry-run --skip-embeddings` validates deployment parsing for the repository.
- Current deployment parser scope covers Dockerfile stages, base images, selected Dockerfile instructions, Compose services, images/build contexts, ports, environment keys, volumes, and `depends_on` relationships.
- Existing Markdown ingestion can index deployment docs structurally, but it does not extract Kubernetes, Helm, CI/CD, or code-to-runtime semantics.

Expected outcome:

- Structured ingestion for Dockerfiles and Docker Compose first, then Helm charts and Kubernetes manifests.
- Nodes and relationships for images, services, ports, environment variables, volumes, deployments, services, ingress, and dependencies.
- Agent queries that connect code to runtime configuration and deployment files.

Why it matters:

Many agent tasks involve changing behavior that is controlled by container, environment, or deployment configuration.

### 12. Test And Validation Context

Connect implementation nodes to the tests and commands that validate them.

Current implementation:

- `docs/testing.md` documents the main .NET, Python, and smoke verification commands.
- Context package responses include `validation_recommendations` inferred from packaged file paths.
- MCP `output_format = "agent"` includes those recommendations in the agent text brief.
- The repository has broad .NET and Python tests.
- C# ingestion emits `TestFile` nodes for test files and `TestCase` nodes for methods with common .NET test attributes or CodeMesh-style `Test...` naming in test files.
- Validation commands are not yet represented as graph context.
- Test cases are not yet linked to implementation nodes.

Expected outcome:

- Test projects, test files, test cases, and test commands represented in the graph.
- Relationships between tests and implementation nodes where naming, references, or coverage data supports it.
- MCP context packages that recommend relevant validation commands.

Why it matters:

Agents should not only modify code; they should know how to verify the change.

### 13. Evaluation Suite For MCP Use Cases

Add repeatable scenarios that measure whether CodeMesh helps agents.

Current implementation:

- Unit and contract tests cover store behavior, ranking, MCP contracts, REST contracts, CLI output, parsers, redaction, and ingestion.
- `uv run python -m codemesh_agent_access eval` runs deterministic MCP fixture scenarios through the same `FastMCP` tool-call path used by contract tests.
- Current fixture scenarios assert minimum behavior for tool guidance, search diagnostics, context package metadata, freshness guidance, and redaction leakage.
- `eval live` launches Agent Access through real MCP stdio, requires fresh indexed data by default, and scores versioned CodeMesh self-analysis cases using Recall@k, MRR, nDCG, stability, relationship coverage, latency, and safety gates.
- `eval agent` uses isolated temporary clones and a Codex runner adapter to compare identical answer and repair tasks with and without CodeMesh; paid/model-backed runs remain explicit rather than part of normal CI.
- Custom live and agent suites use versioned JSON formats exposed through `eval schema` and `eval validate`.
- The self-ingestion smoke path remains the live REST lifecycle check; the live evaluator owns MCP stdio effectiveness checks.

Expected outcome:

- A deterministic fixture suite for MCP tool behavior that runs without stores or model providers.
- A small set of live benchmark queries against CodeMesh itself and one sample repository.
- Expected tool behavior and minimum useful results for each scenario.
- Regression tests for search ranking, package content, freshness diagnostics, and redaction.

Why it matters:

Agent usefulness is easy to degrade accidentally. Evaluation keeps the MCP service focused on practical outcomes.

## P3 - Broader SDLC Intelligence

### 14. API Contract And Database Migration Ingestion

Add structured parsers for compatibility-critical artifacts.

Expected outcome:

- OpenAPI, AsyncAPI, GraphQL, protobuf, and migration files represented as typed nodes.
- Relationships from handlers, clients, models, and migrations to public contracts and persisted data structures.

Why it matters:

Agents need to understand compatibility boundaries before changing public APIs or persisted data.

### 15. Observability And Runbook Context

Index operational diagnostics and support artifacts.

Expected outcome:

- Metrics, alerts, dashboards, runbooks, and SLOs represented as searchable context.
- Relationships from services or code paths to operational signals where detectable.

Why it matters:

Production-aware agents should know how a change is monitored and how failures are diagnosed.

### 16. Ownership And Review Metadata

Index collaboration rules that shape safe changes.

Expected outcome:

- CODEOWNERS, contribution docs, PR templates, and review conventions represented as context.
- Agent packages can include relevant ownership and review expectations for a touched area.

Why it matters:

Useful agents need to follow local engineering process, not only compile code.

## Near-Term Recommended Order

1. Keep the summary-free CodeMesh and pinned external C# live baselines green.
2. Retain the spontaneous zero-adoption campaigns and the first regressed
   assisted campaign as immutable diagnostics.
3. Retain the focused assisted campaign as first attributable product-proof
   evidence: equal correctness with 34.7% lower median time and 64.5% lower
   median tokens on one complex task.
4. Retain the independent Config.Net result: two attributable correctness wins,
   100% treatment success and adoption, no safety violations, and 11.8% lower
   median elapsed time in the three-pair assisted campaign.
5. Commit and freshly index the canonical MCP initialization instructions, then
   run the frozen `config-net-cache-agent` suite without treatment-only guidance
   when model spend is explicitly authorized.
6. Re-run the same frozen live and agent baselines after any material change.
7. Only after replication and discoverability evidence resume summary
   qualification, broader language/SDLC coverage,
   deployment expansion, UI work, portability, or experiential memory.

This order moves CodeMesh from a credible technical system to a proven agent
tool before expanding its surface area.
