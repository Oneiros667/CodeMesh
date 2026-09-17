# Enrichment and evaluation internals

Document type: current implementation reference

Embeddings and generated summaries enrich a source index. Installation/probing
connects that index to a particular agent host, feedback records observations,
and evaluation measures specified behavior. These components do not replace
source evidence or turn implementation into demonstrated product benefit.
The [handbook](../guides/developer-handbook.md) explains the core workflow.

## Embedding generation and query embedding

Write-side embedding providers implement
[`IEmbeddingProvider`](../../src/CodeMesh.Ingestion/Embedding/IEmbeddingProvider.cs).
The CLI selects
[`OllamaEmbeddingProvider`](../../src/CodeMesh.Ingestion/Embedding/OllamaEmbeddingProvider.cs),
[`LmStudioEmbeddingProvider`](../../src/CodeMesh.Ingestion/Embedding/LmStudioEmbeddingProvider.cs),
or [`NoEmbeddingProvider`](../../src/CodeMesh.Ingestion/Embedding/NoEmbeddingProvider.cs).
The orchestrator gives the provider nodes plus a dictionary of **redacted**
content. Providers create bounded text inputs with node context and source,
batch requests, and attach provider/model/content provenance to returned vectors.

The embedding id includes provider, model, node id, and content hash; Qdrant's
point key additionally incorporates the storage namespace. The orchestrator's
incremental lookup checks provider/model and node/content identity, and rewrites
embeddings for rewritten nodes. `--force-embeddings` bypasses the unchanged-vector
skip and implies inclusion; it conflicts with `--skip-embeddings`.
[`EmbeddingVerifier.VerifyAsync`](../../src/CodeMesh.Ingestion/Embedding/EmbeddingVerifier.cs)
compares graph and vector state for the selected provider/model. It checks
coverage and stale/missing records, not embedding quality.

Ollama generation uses its batch embedding endpoint and falls back to the legacy
single-input endpoint only for HTTP 404/405. LM Studio uses the compatible
embedding response shape. A wrong vector count or malformed dimension batch is
an error, not a partially successful embedding result. The .NET tests
`TestOllamaEmbeddingProviderMapsResponses`,
`TestLmStudioEmbeddingProviderMapsResponses`,
`TestForcedEmbeddingIngestionRebuildsUnchangedEmbeddings`, and
`TestEmbeddingVerifierReportsMissingAndStaleVectors` in
[Program.cs](../../tests/CodeMesh.Tests/Program.cs) cover these seams.

Read-side
[`QueryEmbeddingProvider`](../../agent-access/codemesh_agent_access/embeddings.py)
is a separate Python adapter configured by `CODEMESH_MODEL_PROVIDER` and
`CODEMESH_EMBEDDING_MODEL`. It prefixes query text with `search_query:`, requests
one vector, and supplies it to Qdrant search. Provider health checks whether the
configured model is listed. Setting write-side flags does not configure the
Python process: model and vector dimensions must be compatible across both
sides. `test_query_embedding_provider_prefixes_queries` and provider-health
tests in [test_store_components.py](../../agent-access/tests/test_store_components.py)
cover mapping rather than live model quality.

## Summary selection, budgets, identity, and persistence

[`CodeSummaryGenerator.GenerateAsync`](../../src/CodeMesh.Ingestion/Summary/CodeSummaryGenerator.cs)
selects candidates using
[`CodeSummaryIdentity.IsCandidate`](../../src/CodeMesh.Ingestion/Summary/CodeSummaryIdentity.cs).
Eligible kinds include files/test files, types, methods/test cases, constructors,
properties, and events. Declaration nodes are not candidates. In particular,
a C# logical symbol's summary input can be signature-oriented; generation does
not automatically traverse to all its declaration bodies.

`GenerateAsync` derives a generation-configuration fingerprint, calculates
summary ids, loads existing summary state, and skips only matching **completed**
ids unless forced. An id binds the snapshot namespace, node/content, summary
kind, provider/model, prompt version, and generation fingerprint. Changing
configured generation behavior can regenerate summaries without changing the
core source snapshot. Matching alternate provider/model/prompt summaries can
remain retained for the same current content.

[`SummaryBudgetPolicy.CreateRequest`](../../src/CodeMesh.Ingestion/Summary/SummaryBudgetPolicy.cs)
chooses the maximum of kind, source-size/span, and parser-metadata tiers.
Truncated or large source promotes the tier. The current tiers are Compact,
Standard, Complex, and Aggregate, with visible summary budgets of 128, 192, 320,
and 448 tokens. The request separately records input-character allowance,
reasoning reserve, and maximum completion budget; these fields serve different
purposes. Input size is a character count, not an exact tokenizer measurement.

[`SummaryPrompt`](../../src/CodeMesh.Ingestion/Summary/SummaryPrompt.cs) owns
prompt construction, version/hash, structured response parsing, and supported
confidence normalization. Provider adapters implement
[`ICodeSummaryProvider`](../../src/CodeMesh.Ingestion/Summary/ICodeSummaryProvider.cs)
for Ollama, LM Studio, and OpenAI. The latter's implementation is in
[OpenAiCodeSummaryProvider.cs](../../src/CodeMesh.Ingestion/Summary/OpenAiCodeSummaryProvider.cs);
it maps request options and response usage to the shared result, including
requested/effective generation metadata. This is the inspected adapter contract,
not a current external model availability recommendation.

Generation is sequential per candidate. `CreateSummaryAsync` catches individual
non-cancellation provider exceptions and writes a failed summary with error
metadata. `GenerateAsync` upserts both successful and failed records, cleans
obsolete identities, and reports completed/failed/skipped counts. Cancellation
propagates; a summary-store write failure also escapes to ingestion.

The [Mongo summary adapter](../../src/CodeMesh.Storage/Mongo/MongoNodeSummaryStore.cs)
migrates the old unique identity index to `node_summary_identity_v2` so generation
fingerprints can coexist correctly. Python
[summary_store.py](../../agent-access/codemesh_agent_access/summary_store.py)
searches completed records and exposes coverage. Node lookup first seeks the
requested content hash, then can fall back to a completed summary for that node
in the namespace; consumers should retain the returned summary's own provenance.

Tests in the [.NET harness](../../tests/CodeMesh.Tests/Program.cs) cover
`TestSummaryBudgetsScaleWithNodeComplexity`,
`TestSummaryGeneratorPersistsBudgetMetadata`,
`TestSummaryGeneratorRegeneratesWhenConfigurationChanges`, and
`TestMongoSummaryStoreMigratesGenerationIdentity`. Python's
`test_node_summary_lookup_falls_back_when_content_hash_differs` in
[store tests](../../agent-access/tests/test_store_components.py) documents the
read-side fallback explicitly.

## Disabled and failed capabilities

| Condition | Implemented consequence |
| --- | --- |
| Ingest without inclusion flags | CLI supplies no-op providers and skips embedding/summary generation; source parsing and persistence proceed. |
| Python provider mode `none` | No query embedding call. Lexical graph search and stored-summary search remain available. |
| No stored summaries | Packages still contain source hits and snippets; `summary` can be null. |
| Query embedding HTTP failure | Python adapter returns an empty vector for caught HTTP errors; text search can continue. Malformed response values are not all caught. |
| Write-side embedding failure | Normally throws through the orchestrator and prevents the new slot publication. |
| Individual summary-provider failure | Failed summary record/counter; source ingestion can complete. A completed source run does not mean complete summaries. |
| Summary-store or core-store write failure | Escapes and fails the staged generation; already completed writes are not rolled back. |

These branches are implemented in the
[CLI factories](../../src/CodeMesh.Cli/Program.cs),
[orchestrator](../../src/CodeMesh.Ingestion/IngestionOrchestrator.cs), and provider
modules linked above. Provider mode `none` does not erase prior enrichment or
eliminate store dependencies. Use isolated no-summary indexes when an evaluation
requires a genuine no-summary baseline.

## Summary-model qualification

The production generation path is also used by
[`SummaryQualificationRunner`](../../src/CodeMesh.Ingestion/Summary/Qualification/SummaryQualification.cs).
The runner validates a frozen suite/profile and clean source identity, redacts
input, performs warm-up and measured repetitions, and emits a private archive
plus model-blinded review packet. The example
[suite](../evaluation/assets/summary-qualification-suite.example.json) is
synthetic wiring evidence, not a sufficient quality corpus.

The CLI's `summaries qualify bind-retrieval` binds distinct no-summary/candidate
live reports, matching suite/repository/commit, a shared ranking identity, and a
reviewed query-level assessment to that archive. `SummaryQualificationCompiler`
requires complete compatible reviews, retrieval evidence, and resource/cost
evidence before producing a sanitized result. Missing evidence means an invalid
run, not a passing candidate. `TestSummaryQualificationRunnerAndCompiler` in
[Program.cs](../../tests/CodeMesh.Tests/Program.cs) uses controlled providers and
artifacts to exercise these gates.

[ADR 0002](../decisions/0002-summary-qualification-evidence-boundary.md) records
why generation/compilation stays in .NET and retrieval measurement stays in the
existing Python evaluator. Operating commands remain in
[COMMANDS.md](../../COMMANDS.md#summary-model-qualification), with the full
qualification requirements in
[Summary Model Qualification](../planning/summary-model-qualification.md).
No deployment profile is established as qualified merely by this implementation.

## Installation, probing, and feedback

[`create_installation_plan`](../../agent-access/codemesh_agent_access/installer.py)
binds the target checkout to an exact launch and optional onboarding text. A
plan contains complete intended file bytes, previous/new hashes, diffs, and a
plan hash. Application checks the reviewed hash and target drift. Managed blocks
preserve unrelated configuration/guidance. The config names environment
variables to forward rather than embedding their secret values; the generated
launch selects the exact CodeMesh package path and binding.

[`run_runtime_probe`](../../agent-access/codemesh_agent_access/probe.py)
verifies the plan is applied, starts its stdio command with provider mode `none`,
checks initialization instructions and the normal four-tool manifest, checks
the one bound repository and fresh status, then retrieves a nonempty package.
Expected paths can turn it into a focused retrieval gate.
`run_runtime_rejection_probe` deliberately overrides a binding dimension and
checks rejection. These launch real read processes and use stores; they are
provider-free but not offline unit tests.

[`record_feedback`](../../agent-access/codemesh_agent_access/feedback.py)
requires an exact Git root and ignored `.codemesh-feedback/` outbox. Its strict
versioned packet records repository and CodeMesh commits, dirty-state hash,
binding/snapshot/languages/parser profile, task family, tool usage, categorized
paths, validation outcome, confidence, and bounded descriptions. Sanitizers
reject unsafe text/path shapes; the content id binds the normalized packet.
`validate_feedback` checks schema and id, and `summarize_feedback` groups evidence,
prioritizes unresolved failures, and recognizes explicit superseding rechecks.

Feedback does not change ranking, trigger ingestion, transmit itself externally,
or automatically modify the roadmap. Operator-supplied classifications are
observations whose provenance must be reviewed. Tests live in
[test_installer_probe.py](../../agent-access/tests/test_installer_probe.py) and
[test_feedback.py](../../agent-access/tests/test_feedback.py). The canonical
installation and feedback procedure remains [MCP Setup](../guides/mcp-setup.md).

## Evaluation data flow and evidence classes

| Harness | Mechanism | What a pass supports |
| --- | --- | --- |
| [fixture.py](../../agent-access/codemesh_agent_access/evaluation/fixture.py) | `run_mcp_evaluations` substitutes `FixtureEvaluationStore`, constructs diagnostic MCP, and calls tools in process. Restores the original store hook in `finally`. | Deterministic tool/format/guidance/redaction-fixture behavior. No network, live-store, or agent-benefit conclusion. |
| [live.py](../../agent-access/codemesh_agent_access/evaluation/live.py) | `McpEvaluationClient` starts stdio; `run_live_evaluation` checks tool-source identity, health, repository and freshness, then warm-up/measured suite cases. | Retrieval, relationships, budgets, timing, and leak checks for that exact suite/index/tool candidate. |
| [agent.py](../../agent-access/codemesh_agent_access/evaluation/agent.py) | `run_agent_evaluation` prepares pinned source, runs randomized control/treatment order per repetition, validates outputs and command policy, and records adoption, correctness, time, and tokens. | A paired outcome in its recorded integration mode and authority envelope. |
| [benchmark.py](../../agent-access/codemesh_agent_access/evaluation/benchmark.py) | `run_model_benchmark` checks clean source/index identity, runs a live gate, then graded query/change tiers with evidence and review artifacts. | Model performance on that benchmark, subject to qualification/review gates. It is a separate runner path from the capped agent campaign. |

[models.py](../../agent-access/codemesh_agent_access/evaluation/models.py) owns
suite/report schemas. Checked-in [suites](../../agent-access/codemesh_agent_access/evaluation/suites/)
freeze targets, repository commits, thresholds, and tasks.
[`metrics.ranking_metrics`](../../agent-access/codemesh_agent_access/evaluation/metrics.py)
matches normalized target paths/ids/keys, calculates recall and precision at k,
reciprocal rank, and relevance-weighted nDCG, with each target contributing at
most once to ranked gain. A high recall can coexist with poor latency or agent
non-adoption; these are separate measurements.

Configured agent evaluation verifies reviewed installation, identical relevant
guidance, fresh binding, baseline MCP identities, and positive/rejection probes.
Spontaneous and evaluator-assisted suites retain their own historical diagnostic
profiles and onboarding conditions. Treatment-only assistance changes the
comparison class; it cannot be presented as configured prompt-parity evidence.
Raw traces are optional sensitive artifacts; sanitized retained reports belong
under the existing evidence discipline, not copied into source documentation.

The actual harness tests are
[test_evaluation.py](../../agent-access/tests/test_evaluation.py),
[test_effectiveness_evaluation.py](../../agent-access/tests/test_effectiveness_evaluation.py),
and [test_model_benchmark.py](../../agent-access/tests/test_model_benchmark.py).
They use test runners and fixtures to validate orchestration without requiring
paid model execution. See [Testing](../evaluation/testing.md) for check selection
and [MCP Effectiveness Evaluation](../evaluation/mcp-effectiveness.md) for live
procedures and verdict interpretation.

## Hard-capped agent runner

Before an agent campaign prepares repository work or calls a model,
`require_reported_token_hard_cap` requires a positive integer allowance and a
runner declaring `input-output-reasoning-v1` accounting. Each execution receives
only the remaining allowance. The campaign stops at zero, after incomplete
execution, or on inconsistent/over-limit accounting; it does not automatically
retry. The default `CodexRunner` does not declare compatible enforcement and is
refused. Explicit `CappedCodexRunner` implements the separate bounded path.

[`capped_codex.py`](../../agent-access/codemesh_agent_access/evaluation/capped_codex.py)
contains `HardCapLedger`, `CappedResponsesProxy`, and `CappedCodexRunner`. The
proxy counts submitted input before generation. `reserve` commits input plus
twice the admitted generated-token allowance because this repository's reported
accounting adds reasoning output to already-inclusive output. `settle` releases
unused allowance only after complete, validated usage agrees with counted input.
Interrupted calls retain their full reservation and stop further admission.

The runner uses an ephemeral loopback proxy, zero request/stream retries, an
exact bundled model catalog entry, and final agreement between proxy and runner
usage. It rejects unsupported cost-bearing request shapes rather than guessing
their accounting. The sanitized ledger excludes request content and credentials.
Do not assume the separate `eval model` benchmark automatically inherits this
agent-campaign control.

[ADR 0003](../decisions/0003-hard-capped-codex-evaluation-runner.md) records the
design rationale; [test_capped_codex.py](../../agent-access/tests/test_capped_codex.py)
tests admission, interruption, unsupported activity, retry rejection, and
reconciliation. These are enforcement tests. They do not authorize model spend
or establish that a particular provider-backed campaign completed.
