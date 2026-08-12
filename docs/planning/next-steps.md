# CodeMesh Next Steps

Document type: planning and execution-order authority

Reviewed: 2026-08-12

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

Do not select broad parser, SDLC, UI, model-provider, summary, portability,
snapshot, shared-store, or agent-memory work merely because it is documented.
Activate it only when the ordered work below or explicit owner direction does
so.

## Current Execution Order

1. Keep the clean CodeMesh and pinned YoutubeDownloader summary-free live
   baselines passing after material retrieval, packaging, relationship, or MCP
   changes.
2. Preserve the spontaneous YoutubeDownloader and prompt-parity Config.Net
   zero-adoption campaigns as negative evidence; never attribute their overall
   timing or token variance to CodeMesh.
3. Preserve the focused YoutubeDownloader and independent Config.Net assisted
   campaigns as replicated utility-after-onboarding evidence, with their
   prompt-parity and task-family limitations explicit.
4. Complete the selected explicit-onboarding v1 contract in
   [Agent Integration Contract](agent-integration-contract.md): implement the
   normal-user tool profile, unambiguous checkout binding, fail-closed freshness
   behavior, provider-free live runtime probe, and reviewable installation flow.
   The canonical manual repository guidance is already documented.
5. Extend evaluation reporting to distinguish configured/onboarded product use
   from spontaneous and evaluator-assisted modes. Then repeat the frozen live
   gate and, with explicit model-spend authority, the Config.Net task using the
   exact integration shipped to normal users and identical control/treatment
   task prompts. Do not relabel this as spontaneous discovery.
6. Repeat the same frozen live and configured/onboarded agent evaluations after
   each material tool-selection, ranking, packaging, or relationship change.
   Correctness and safety win; efficiency counts only for adopted matched pairs.
   Agent runs are model-cost-bearing and require explicit authorization, clean
   committed checkouts, and a fresh matching index.
7. Implement the summary-model qualification runner only before summaries are
   considered for default retrieval. Require factual, reliability, safety, and
   no-summary retrieval comparisons.
8. Complete default secret-file exclusion and configurable ingestion
   allow/deny policy before broad artifact ingestion or shared proprietary
   workspace storage.
9. Defer method-load and retrieval-granularity analysis, Kubernetes/Helm,
   additional parser breadth, UI expansion, outcome memory, portable snapshots,
   multi-checkout snapshot retention, shared stores, and broader SDLC ingestion
   until configured/onboarded product benefit is repeatable or explicit owner
   direction reprioritizes them.

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
| Python parser | Partial | Add imports, calls, routes, MCP handlers, and test relationships after activation. | [Architecture](../current/architecture.md) |
| Markdown parser | Partial | Add links from docs to commands, endpoints, projects, and source when justified. | [Architecture](../current/architecture.md) |
| Context packages | Implemented baseline | Maintain compact agent output, citations, rationale, and budget behavior. | [Agent Access Contracts](../current/agent-access-contracts.md) |
| Local web inspection | Implemented initial slice | Expand only when it serves a measured agent or audit need. | [Agent Access Contracts](../current/agent-access-contracts.md) |
| Tool guidance and onboarding | Server instructions and manual guidance implemented; v1 contract selected | Implement the normal-user profile, checkout binding, live probe, and reviewable installation; then establish configured/onboarded evidence. | [Agent Integration Contract](agent-integration-contract.md) |
| Refresh and watch | Implemented initial slice | Native file events and broader operational visibility remain optional. | [Self-Analysis](../guides/self-analysis.md) |
| Deployment parsing | Partial | Dockerfile and Compose exist; Helm, Kubernetes, CI/CD, and code-to-runtime links are deferred. | [SDLC Roadmap](sdlc-roadmap.md) |
| Test and validation context | Partial | Link tests and commands to implementation with source-backed confidence. | [Graph Intelligence Design](graph-intelligence-design.md) |
| Evaluation harnesses | Implemented | Maintain fixtures and live gates; run paid agent/model campaigns only with authority. | [Evaluation](../evaluation/mcp-effectiveness.md) |
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
