# CodeMesh Next Steps

Document type: planning and execution-order authority

Reviewed: 2026-08-31

This document is the canonical order for future CodeMesh work. It does not
describe implemented behavior; use [Project Status](../current/project-status.md),
[Architecture](../current/architecture.md), and
[Agent Access Contracts](../current/agent-access-contracts.md) for the current
system.

## Product Boundary

The initial wedge remains source-grounded implementation discovery, likely
change-impact navigation, and validation selection for C#/.NET coding agents.
Correctness, safety, freshness, and attributable agent outcomes take precedence
over broader feature coverage.

Owner direction has activated a bounded one|nine adoption priority alongside
that wedge. It adds the Rust and Python coverage needed to index one|nine,
repository-specific onboarding across its isolated checkouts, and a durable
feedback path from one|nine agents to CodeMesh development. This activation does
not authorize general parser expansion or make diagnostic feedback product-
benefit evidence.

Do not select broad parser, SDLC, UI, model-provider, summary, portability,
snapshot, shared-store, or agent-memory work merely because it is documented.
Activate it only when the ordered work below or explicit owner direction does
so.

## Current Execution Order

The checkout-safe integration, atomic Python-plus-Rust ingestion, Rust parser,
feedback loop, instance-owned onboarding, and frozen provider-free Primary
pilot gate are implemented. Priority 1 produced clean candidate `ee1d4d9` and
passed the full deterministic, summary-free live, and one|nine pilot gates. The
next three priorities are:

1. **Verify and measure configured/onboarded normal-host use.** The paired-agent
   evaluator now selects the reviewed checkout-local `normal` MCP installation
   unchanged and records configured integration, guidance, baseline MCP,
   profile, binding, plan, and probe identities. First run its provider-free
   preflight from a clean committed CodeMesh candidate against the exact pinned
   one|nine checkout, then rerun the frozen one|nine and YoutubeDownloader
   gates. Only after those pass, and with explicit model-spend authority, run
   pinned one|nine paired tasks through that exact configuration.
   Keep control and treatment task prompts identical; compare against ordinary
   repository exploration plus the checkout's existing permitted Graphify
   workflow. Report tool adoption, correctness, safety, elapsed time, tokens,
   fallback behavior, and validation selection.
2. **Turn measured feedback into bounded improvements.** Review validated
   one|nine feedback and controlled results, select the smallest correction for
   a recurring ranking, relationship, budget, binding, or validation failure,
   and rerun the frozen gates after every material change.
3. **Replicate and decide bounded expansion.** If the one|nine campaign is
   valid, repeat configured/onboarded evaluation on Config.Net. Expand
   onboarding to Secondary, Tertiary, Release, or Hotfix only with a separate
   exact binding and passing checkout-specific probe. Keep Run-only excluded
   pending a separate acceptance decision.

After those priorities, implement the summary-model qualification runner only
before summaries are considered for default retrieval, and complete default
secret-file exclusion plus configurable ingestion allow/deny policy before
broad artifact ingestion or shared proprietary workspace storage.

Defer method-load and retrieval-granularity analysis, Kubernetes/Helm, parser
breadth beyond the activated Python/Rust pilot, UI expansion, outcome memory,
portable snapshots, shared stores, and broader SDLC ingestion until
configured/onboarded product benefit is repeatable or explicit owner direction
reprioritizes them.

The evidence supporting this order is summarized in
[Project Status](../current/project-status.md). Exact evaluation commands and
evidence classification are in
[MCP Effectiveness Evaluation](../evaluation/mcp-effectiveness.md).

## Capability Map

This inventory preserves remaining requirements without overriding the
execution order above.

| Capability | State | Remaining work or gate | Canonical detail |
| --- | --- | --- | --- |
| Self-ingestion and smoke | Implemented | Maintain source-free smoke and fresh-index behavior. | [Self-Analysis](../guides/self-analysis.md) |
| MCP client setup | Implemented | Maintain host examples and troubleshoot environment differences. | [MCP Setup](../guides/mcp-setup.md) |
| Repository status and freshness | Implemented locally | Older records remain unknown until re-ingested; shared freshness is future work. | [Agent Access Contracts](../current/agent-access-contracts.md) |
| Redaction and sensitive-file policy | Partial | Add known-secret-file exclusion, configurable allow/deny policy, and broader tests. | [Security and Redaction](../current/security-and-redaction.md) |
| Python parser | Implemented bounded pilot | Maintain imports, calls, tests, and PyO3 boundary relationships; keep unrelated breadth evidence-driven. | [one\|nine Priority](onenine-adoption-and-feedback.md) |
| Rust parser | Implemented bounded pilot | Maintain the heuristic structural, relationship, test, path-exclusion, and PyO3 contract; broaden only from measured gaps. | [one\|nine Priority](onenine-adoption-and-feedback.md) |
| Multi-language ingestion | Implemented | Maintain atomic language-set publication and language preservation during refresh and watch. | [one\|nine Priority](onenine-adoption-and-feedback.md) |
| Markdown parser | Partial | Add links from docs to commands, endpoints, projects, and source when justified. | [Architecture](../current/architecture.md) |
| Context packages | Implemented baseline | Maintain compact agent output, citations, rationale, and budget behavior. | [Agent Access Contracts](../current/agent-access-contracts.md) |
| Local web inspection | Implemented initial slice | Expand only when it serves a measured agent or audit need. | [Agent Access Contracts](../current/agent-access-contracts.md) |
| Tool guidance and onboarding | Clean candidate verified | Establish configured/onboarded normal-host outcome evidence with explicit model-spend authority. | [Agent Integration Contract](agent-integration-contract.md) |
| one\|nine agent feedback | Implemented bounded pilot | Review sanitized, provenance-bound packets and connect recurring findings to controlled evidence without automatic roadmap mutation. | [one\|nine Priority](onenine-adoption-and-feedback.md) |
| Refresh and watch | Implemented initial slice | Native file events and broader operational visibility remain optional. | [Self-Analysis](../guides/self-analysis.md) |
| Deployment parsing | Partial | Dockerfile and Compose exist; Helm, Kubernetes, CI/CD, and code-to-runtime links are deferred. | [SDLC Roadmap](sdlc-roadmap.md) |
| Test and validation context | Partial | Link tests and commands to implementation with source-backed confidence. | [Graph Intelligence Design](graph-intelligence-design.md) |
| Evaluation harnesses | Implemented for selected v1 contract | Fixture, live, spontaneous, assisted, configured/onboarded, and model paths are implemented; pass the configured clean-candidate preflight and frozen retrieval gates before requesting paid campaign authority. | [Evaluation](../evaluation/mcp-effectiveness.md) |
| Repository identity and snapshots | Local profile implemented | Maintain deterministic identity/slot/retention behavior; shared coordinator, tenant security, and private overlays remain deferred. | [Identity and Snapshot Requirements](repository-identity-and-snapshot-retention.md) |
| Summary-model qualification | Procedure proposed | Implement the runner and qualify a complete deployment profile before default use. | [Summary Model Qualification](summary-model-qualification.md) |
| Method load and retrieval granularity | Proposal | Calibrate human-maintainability, tokenizer-bound representation, and agent-context thresholds before exposing advisory findings. | [Method Load And Retrieval Granularity](method-load-and-retrieval-granularity.md) |
| Graph analysis and outcome memory | Proposal | Activate only when measured relationship or impact limitations justify it. | [Graph Intelligence Design](graph-intelligence-design.md) |
| Broader SDLC intelligence | Deferred roadmap | Add contract, persistence, operations, security, and ownership artifacts only after activation. | [SDLC Roadmap](sdlc-roadmap.md) |

## Work Selection Rules

- Reconcile this order with current Git state, implementation, and retained
  evidence before choosing work.
- Treat fixtures, unit tests, configured workflows, local smoke runs, and
  historical reports as their stated evidence types only.
- Prefer the smallest change that addresses a measured failure or overhead.
- Keep generated summaries optional and provider-free evaluation available.
- Preserve frozen control/treatment prompts, grading, pinned repositories, and
  negative evidence when comparing changes.
- Do not lower gates, alter frozen tasks, or add treatment-only guidance to
  manufacture a favorable prompt-parity result.
- Record consequential implemented architecture decisions in `docs/decisions/`;
  proposals alone do not require an ADR.

## Deferred Design References

- [Graph Intelligence and Agent Memory](graph-intelligence-design.md)
- [Method Load and Retrieval Granularity](method-load-and-retrieval-granularity.md)
- [Repository Identity and Snapshot Retention](repository-identity-and-snapshot-retention.md)
- [Summary Model Qualification](summary-model-qualification.md)
- [SDLC Roadmap](sdlc-roadmap.md)

These documents retain detailed future requirements. Their existence is not
implementation status or authority to begin them.
