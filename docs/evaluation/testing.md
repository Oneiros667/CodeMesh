# Testing Guide

Document type: current operating guide

Use this guide to choose the right verification path after CodeMesh changes.
The supported invocations are indexed in [`COMMANDS.md`](../../COMMANDS.md);
this guide defines when to use them, plus the gates around end-to-end and
evaluation procedures.

## Default Verification Commands

Run the [deterministic .NET commands](../../COMMANDS.md#net) from the repository
root.

Run these .NET commands serially because projects share intermediate output
directories.

Run the [Python Agent Access commands](../../COMMANDS.md#python-agent-access)
from `agent-access`.

Run both after changes that cross .NET/Python contracts, serialization,
lifecycle, integration, or end-to-end boundaries. For a focused change, run
the affected surface and report why the other suite was not required.

## .NET Tests

The .NET test harness covers:

- Domain utilities.
- Environment loading.
- Agent Access contract mapping.
- Agent Access .NET client behavior.
- Ingestion orchestration.
- Default secret-file exclusion, linked-path containment, configurable path
  filters, watch filtering, and path-policy snapshot identity.
- Incremental writes, deterministic project/checkout/snapshot identity,
  compare-and-swap slot retention, pins, and cleanup.
- Embedding and summary providers.
- Summary qualification input redaction, held-out partition enforcement,
  immutable evidence binding, typed reviewer aggregation, mandatory
  query-level retrieval assessment, resource/cost evidence, gate enforcement,
  and fail-closed report comparison.
- MongoDB, Neo4j, and Qdrant storage adapters.
- C#, Python, Rust, and atomic multi-language parser behavior.
- Parser-container design-time output isolation, compiler-visible metadata,
  concurrent same-named projects, project failure cleanup, and cross-project
  invocation preservation.
- Optional configured sample parsing.

Some tests skip when required live services or sample paths are unavailable.

## Python Tests

The Python tests under `agent-access/tests` cover:

- CLI output.
- Context ranking.
- MCP evaluation scenarios.
- Formatting.
- MCP contracts.
- Exact checkout binding, reviewable installation, provider-free probing, and
  versioned feedback recording/summarization.
- REST contracts.
- Store read components.

Use these tests when changing `agent-access/codemesh_agent_access`.

The Agent Access development dependency group includes `pytest` and `ruff`, so
`uv sync --locked` is sufficient for a clean checkout and rejects lock drift.
No global Python test or lint packages are required.

Run lint and formatting checks after Python changes:

```powershell
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
```

Run the deterministic MCP evaluation suite directly when changing tool guidance,
context search, context packages, freshness, or redaction behavior:

```powershell
cd agent-access
uv run --no-sync python -m codemesh_agent_access eval
```

The current evaluation suite uses an in-process fixture store and explicitly
selects the non-destructive diagnostic MCP profile, so it does not require
Docker services or a model provider. Profile contract tests separately assert
the four-tool normal default and deletion exclusion. Use the end-to-end smoke
script for live-store lifecycle checks.

Run the live MCP stdio benchmark after self-ingesting a clean CodeMesh checkout:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval live
```

Add `--capture-context-package-timings` when attributing context-package
latency. The opt-in report contains sanitized per-case stage p50s from a
sideband stream; tool responses and character budgets remain unchanged. Treat
those timings as performance evidence separate from retrieval-quality claims.

The retained live and existing spontaneous/evaluator-assisted agent suites
select the `diagnostic` profile explicitly to preserve their frozen tool surface.
That does not make them configured/onboarded product evidence. The implemented
configured mode selects the shipped `normal` profile and records that identity
separately in its installation plan and runtime probe. It also runs an
automatic wrong-checkout rejection probe before a paired run.

For an installed configured checkout, run the reviewed plan's normal-profile
probe instead. It verifies the exact launch and binding and can gate real target
paths:

```powershell
uv run python -m codemesh_agent_access mcp-probe `
  --plan C:\temp\codemesh-install-plan.json `
  --query "Python to Rust native replay implementation and tests" `
  --expected-path native/feed_hub_replay/src/lib.rs
```

This is configured retrieval evidence, not a model-backed agent comparison.
Record misses through the feedback workflow and retain passing rechecks with an
explicit superseded feedback id.

Before requesting model-spend authority, run the configured agent preflight
with the pinned configured suite and reviewed plan. It invokes no model:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --runner capped-codex `
  --suite <configured-suite.json> `
  --repository-root <pinned-checkout> `
  --max-reported-tokens <authorized-hard-cap> `
  --configured-plan <reviewed-plan.json> `
  --configured-guidance-path AGENTS.override.md `
  --configured-expected-path <expected-path> `
  --preflight-only `
  --preflight-output <preflight-report.json>
```

The suite must declare `integration_mode` as `configured`, pin
`repository_commit`, and may name reviewed `baseline_mcp_servers` that both
conditions receive. Guidance may be committed or an explicitly installed
ignored file such as instance-generated `AGENTS.override.md`; both temporary
conditions receive identical reviewed bytes, while the report retains its path,
source classification, and hash rather than raw content. A preflight pass is
provider-free configuration and runtime evidence only.

The pinned YoutubeDownloader suite is the representative external C# baseline.
Prepare and ingest the exact checkout as described in
[MCP Effectiveness Evaluation](mcp-effectiveness.md), then run:

```powershell
uv run python -m codemesh_agent_access eval live `
  --suite youtube-downloader-live `
  --output ..\.codemesh-evals\youtube-downloader-live\report.json
```

Run the opt-in Codex A/B benchmark only when live stores, a fresh index, Codex
authentication, time, and model budget are available:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --runner capped-codex `
  --model <model-id> `
  --max-reported-tokens <authorized-hard-cap>
```

The agent evaluator now requires a positive hard cap and a selected runner that
declares compatible hard-cap enforcement before repository preflight or any
model call. Reported tokens are input plus output plus reasoning-output tokens;
cached input is already included in input and is not counted twice. Every run
receives only the remaining campaign allowance. The campaign stops at zero or
after an incomplete run without retry. Missing or inconsistent usage and a
runner cap violation fail as infrastructure errors.

The default `--runner codex` subprocess mode cannot guarantee this cap because
the Codex CLI reports usage only after a turn and exposes no compatible
hard-limit option, so provider-free capability preflight refuses it. Select
`--runner capped-codex` explicitly for the implemented loopback Responses proxy.
Provider-free preflight verifies its declared accounting without using a model
or requiring a credential. A model-backed run additionally requires an
`OPENAI_API_KEY`; its value is forwarded only to the upstream API and is never
included in reports or logs.

The capped runner counts each complete input before generation, reserves input
plus twice the admitted generated-token envelope as the worst case under the
committed output-plus-reasoning accounting, clamps generated output to the
smaller of the remaining allowance and the model's documented output maximum,
and configures zero request and stream retries. It rejects background,
compaction, unreviewed parameters outside the input-counting contract,
unsupported cost-bearing endpoints and tools, retry activity, missing usage,
and accounting disagreement. Interrupted calls retain their reservation and
stop the campaign as incomplete. Per-execution reports contain a sanitized
hard-cap ledger for auditing this behavior.

Use `--suite youtube-downloader-agent` and point `--repository-root` at the
pinned external checkout for its implementation-discovery, change-impact, and
validation-selection comparison.

Use `--suite youtube-downloader-impact-agent` with the same checkout for the
separate complex impact-analysis calibration task. It runs six executions at
the default three repetitions and does not alter the original frozen suite.
Run `eval live --suite youtube-downloader-impact-live` first to retain its
retrieval and relationship baseline.

Use `eval live --suite youtube-downloader-impact-adaptive-live` for the
provider-free task-adaptive gate. It preserves the same repository commit, six
targets, and thresholds while comparing one task-shaped package with three
bounded focused facets. Run it with the configured preflight, unchanged impact
suite, and unchanged canonical suite before requesting authority for another
paired campaign. A passing adaptive suite proves retrieval and package-budget
readiness only; it does not prove agent compliance or benefit.

Use `--suite youtube-downloader-impact-assisted-agent` only after a spontaneous
campaign records zero adoption. Its treatment-only onboarding deliberately
breaks prompt parity and is reported as assisted utility evidence.

After the live suite passes, run the opt-in model selection benchmark. Tier 1
uses 72 executions per model and is the qualification gate before paired repair
testing:

```powershell
uv run python -m codemesh_agent_access eval model --model <model-id> --tier query
uv run python -m codemesh_agent_access eval model --model <model-id> --tier change
```

These model-backed commands are intentionally excluded from normal `pytest`
execution. Suite validation, scoring, proxy enforcement, review handling, and
orchestration tests remain in normal CI. See
[MCP Effectiveness Evaluation](mcp-effectiveness.md) for metrics, suite formats,
artifact handling, and exit codes.

## End-To-End Smoke

Use the smoke script when a change affects live service wiring, Docker Compose behavior, repository lifecycle, cleanup, REST endpoints, or Agent Access integration.

```powershell
.\scripts\e2e-smoke.ps1
```

Common variants:

```powershell
.\scripts\e2e-smoke.ps1 -FixtureOnly
.\scripts\e2e-smoke.ps1 -UseConfiguredSample
.\scripts\e2e-smoke.ps1 -IncludeEmbeddings -EmbeddingProvider ollama -EmbeddingModel nomic-embed-text-v2-moe:latest
```

## Documentation-Only Changes

Tests are usually not required for documentation-only changes. Run:
the [repository standards checks](../../COMMANDS.md#repository-standards).

The link and publication-safety checks are local-only and do not print secret
values.

## Dependency Advisory Checks

Before publication or a dependency update, query the current NuGet and OSV
advisory data:

```powershell
dotnet list CodeMesh.sln package --vulnerable --include-transitive
Set-Location agent-access
uv audit --locked
```

These checks use external advisory services and can become unavailable or
change as advisories are published. Record the date and do not place them in the
deterministic baseline workflow.

## Interpreting Results

- Passing tests indicate the local code path is healthy for covered behavior.
- Skipped integration tests usually mean a store or sample repository is unavailable.
- Failed integration tests may be service setup issues or code regressions; check service health before changing code.

## Harness Implementation and Invariant Map

For the human reading path, see the
[Developer handbook](../guides/developer-handbook.md). The following map helps
maintainers locate relevant test machinery without replacing the risk-based
check selection above.

### How the harnesses run

The [.NET harness](../../tests/CodeMesh.Tests/Program.cs) is a console program
with a table of `(Name, Func<Task>)` entries. It awaits them sequentially,
prints pass/skip/fail records, catches `SkipTestException` separately, and exits
nonzero for failures. New harness tests must be registered in that table.
`dotnet test` is not a substitute for its supported `dotnet run` invocation.

Many fixtures are embedded source strings written to temporary directories;
some initialize Git repositories to exercise commits, worktrees, markers, and
retention. Fake parser/store/provider implementations isolate orchestration.
Live adapter tests probe configured stores and use disposable database,
collection, or repository identities; they skip when the required service is
unavailable. Therefore a successful harness exit with skips does not establish
live-store correctness. The optional YoutubeDownloader parser test also needs
its configured sample path.

The [Python suite](../../agent-access/tests/) uses pytest. Async paths are often
driven with `asyncio.run`; monkeypatches, stub facades, controlled clocks, mock
transports, temporary checkouts, and in-process ASGI/MCP calls keep normal
tests deterministic. The separate
[`run_mcp_evaluations`](../../agent-access/codemesh_agent_access/evaluation/fixture.py)
temporarily replaces the store used by tools and invokes the diagnostic MCP
surface in process. It does not test a fresh external stdio launch, real database
state, or a model's decision to adopt a tool.

[`e2e-smoke.ps1`](../../scripts/e2e-smoke.ps1) creates a small committed C# fixture,
starts services unless told otherwise, ingests it, checks REST/client-visible
context and lifecycle behavior, and cleans its generated fixture/index when
configured to do so. Its `-FixtureOnly` branch returns before service startup
and ingestion; that branch is fixture preparation evidence only. The
[live evaluator](../../agent-access/codemesh_agent_access/evaluation/live.py)
separately owns real MCP stdio retrieval checks.

### Invariants and representative tests

All C# test symbols in this table are in
[Program.cs](../../tests/CodeMesh.Tests/Program.cs).

| Invariant or risk | Representative test or file | Evidence boundary |
| --- | --- | --- |
| Files cannot escape selection via linked paths | `TestRepositoryPathPolicyRejectsLinkedPaths`, `TestCSharpParserAppliesRepositoryPathFilters` | Synthetic path/parser cases; not an exhaustive secret detector. |
| Redaction precedes persistence and models | `TestIngestionRedactsSensitiveContentBeforeStoresAndEmbeddings` | Asserts controlled values and provider input. |
| Multi-language output publishes together | `TestMultiLanguageIngestionPublishesOneDeterministicSnapshot` | Composite success and parser-error behavior with controlled collaborators. |
| Dirty source does not move clean branch-head | `TestSnapshotSlotsRetainCleanHeadsAndBoundDirtyHistory` | Temporary Git plus in-memory registry; not every Mongo crash interleaving. |
| Failed writes preserve previous slots | `TestFailedSnapshotGenerationPreservesActiveSlots` | Injected graph failure after staging. |
| Pins prevent collection until released | `TestExplicitPinsProtectSnapshotsUntilReleased` | Sequential retention behavior; no shared-service coordinator proof. |
| C# logical symbols retain separate source declarations | `TestCSharpParserSeparatesPartialDeclarations` | Representative partial-source fixture. |
| Local semantic calls cross projects | `TestCSharpParserEmitsCrossProjectInvocationRelationships` | Loaded test projects, not all runtime dispatch. |
| Python/Rust native edges remain bounded | `TestCompositeParserLinksPythonCallsToRustPyO3Exports` | Static import/export names, not a running native module. |
| Store schema and payloads round-trip | `TestMongoContentStoreRoundTripsContent`, `TestMongoRegistryStoreRoundTripsRepositoriesAndRuns`, `TestNeo4jGraphStoreRoundTripsGraph`, `TestQdrantVectorStoreRoundTripsEmbeddings` | Live only when prerequisites are available; inspect skips. |
| Binding rejects before retrieval | [test_store_components.py](../../agent-access/tests/test_store_components.py), `test_context_package_rejects_unaccepted_binding_before_search` | Controlled binding/store failure, complemented by the live rejection probe. |
| Ranking covers files and resolves saturated ties | [test_context_ranking.py](../../agent-access/tests/test_context_ranking.py) | Deterministic synthetic relevance invariants. |
| Package namespaces and budgets stay coherent | [test_context_ranking.py](../../agent-access/tests/test_context_ranking.py), [test_formatting.py](../../agent-access/tests/test_formatting.py), [test_cli_output.py](../../agent-access/tests/test_cli_output.py) | Snippet/format contracts; not a tokenizer or product-benefit benchmark. |
| REST/MCP/.NET schemas align | [test_rest_contract.py](../../agent-access/tests/test_rest_contract.py), [test_mcp_contract.py](../../agent-access/tests/test_mcp_contract.py), `TestAgentAccessContractsMapRestJson`, `TestAgentAccessClientCallsRestEndpoints` | Serialization and transport mapping. |
| Installation rejects drift; feedback preserves provenance | [test_installer_probe.py](../../agent-access/tests/test_installer_probe.py), [test_feedback.py](../../agent-access/tests/test_feedback.py) | Plan/packet checks with controlled inputs. |
| Evaluation stops and reports truthfully | [test_effectiveness_evaluation.py](../../agent-access/tests/test_effectiveness_evaluation.py), [test_model_benchmark.py](../../agent-access/tests/test_model_benchmark.py), [test_capped_codex.py](../../agent-access/tests/test_capped_codex.py) | Harness/accounting behavior, not a completed live model campaign. |

### Select checks by changed boundary

| Change | Required direction |
| --- | --- |
| Documentation/navigation only | Repository standards; validate referenced examples and diagrams without starting services. |
| Parser-only implementation | .NET restore/build/harness/format; add a source fixture for the actual semantic or structural failure. |
| Python ranking/formatting only | Python tests and lint/format; deterministic MCP fixtures for search/package/guidance changes. |
| Shared request/response or persisted serialization | Both language suites; verify producer and consumer field/default/null behavior. |
| Lifecycle, cleanup, Docker, live wiring, or REST integration | Both language suites and the authorized PowerShell smoke path described above. |
| Product-benefit claim | The separately authorized, identity-bound evaluation procedure; unit and smoke tests cannot supply this evidence. |

The [change walkthroughs](../guides/making-changes.md) give concrete examples of
these selections. The [evaluation internals reference](../current/enrichment-and-evaluation.md)
explains how fixtures, live retrieval, configured campaigns, and model benchmarks
differ. Historical results do not automatically transfer to the current source.

## Useful Health Checks

Use the [local product health commands](../../COMMANDS.md#local-product-health).
