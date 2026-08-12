# CodeMesh Project Status

Document type: current status snapshot

Reviewed: 2026-08-12

Source baseline: `cc234c8` before this documentation-path reorganization.

This document records current implementation and retained evidence. It does not
set execution order; use
[`docs/planning/next-steps.md`](../planning/next-steps.md) for that. Passing
tests or evaluation harnesses do not by themselves establish generalized agent
benefit, release readiness, deployment acceptance, or production fitness.

## Product Position

CodeMesh is a local-first context and likely change-impact service for coding
agents. The initial product wedge is C#/.NET implementation discovery, impact
navigation, and validation selection through compact source-backed context.

The current milestone is prompt-parity evidence that a normal agent host
discovers and uses the CodeMesh MCP workflow, then performs at least as safely
and correctly as normal repository exploration with attributable efficiency or
correctness benefit.

## Capability Status

| Area | Current status | Important boundary |
| --- | --- | --- |
| C# parsing | Implemented with Roslyn semantic relationships, declarations, test files, and test cases. | Strongest parser and current product wedge. |
| Python parsing | Files, classes, functions, async functions, and containment implemented. | Imports, calls, routes, tool handlers, and test links remain limited. |
| Markdown parsing | Documents, sections, anchors, source spans, and containment implemented. | Cross-links to code, commands, endpoints, and projects are not modeled. |
| Deployment parsing | Initial Dockerfile and Compose nodes, metadata, containment, and service dependencies implemented. | Helm, Kubernetes, CI/CD, overrides, and code-to-runtime links remain planned. |
| Ingestion | Dry-run, incremental writes, staged deterministic snapshots, compare-and-swap slot publication, reference-aware cleanup, refresh, watch, redaction, optional embeddings, and optional summaries implemented. | Watch is polling-based; provider-backed paths remain optional. |
| Storage | Snapshot-namespaced Neo4j graph, MongoDB content/registry/runs/summaries, Qdrant vectors, and in-memory test adapters implemented. | Publication is atomic at the registry slot boundary; normal service-backed operation requires configured stores. |
| Agent Access | REST, stdio MCP, Python CLI, typed .NET client, repository status, context search/packages, symbols, nodes, neighbors, and deletion implemented. | Returned relationships and rankings are navigation evidence, not runtime proof. |
| Context packaging | Agent-format packages, 12,000-character MCP cap, source spans, rationale, relationships, and validation recommendations implemented. | Source verification remains required for consequential conclusions. |
| Local UI | Read-only health, repository, run, freshness, and search views implemented. | It is a local inspection surface, not established product-benefit evidence. |
| Evaluation | Deterministic fixture, live MCP, paired agent, and model benchmark harnesses implemented. | Paid/model-backed runs require explicit authorization; fixtures prove contracts only. |
| Generated summaries | Complexity-aware prompts and local/online providers implemented. | No summary deployment profile is CodeMesh-qualified. |
| Security | Pre-persistence value redaction and generated/cache path exclusions implemented. | Known secret-file exclusion and configurable allow/deny policy remain open. |
| Repository identity | Stable project/checkout markers, deterministic source snapshots, checkout-current and clean branch-head slots, explicit retained slots, legacy migration, and richer local freshness implemented. | Separate clones attach with explicit `--project-id`; shared-service tenant/authorization/privacy controls remain deferred. |

Detailed current interfaces are in
[Agent Access Contracts](agent-access-contracts.md), and component boundaries
are in [Architecture](architecture.md).

## Retained Product Evidence

### Summary-free retrieval

- The pinned YoutubeDownloader live suite passed all six cases with complete
  expected target and relationship coverage.
- Two corrected three-repeat baseline agent campaigns completed all nine pairs
  with equal 100% task success but zero CodeMesh adoption.
- A separate complex output-container task reached 100% live recall after a
  focused ranking correction, while its spontaneous agent campaign still made
  zero CodeMesh calls.
- Overall timing or token differences from non-adopted treatments are retained
  as diagnostics and are not attributed to CodeMesh.

The sanitized live-gate manifest is
[`docs/evaluation/evidence/summary-free-baseline-e84b189.json`](../evaluation/evidence/summary-free-baseline-e84b189.json).

### Assisted utility

- The first valid onboarding-assisted complex campaign achieved full adoption
  and task success but regressed median elapsed time and tokens.
- After the MCP agent brief was capped at 12,000 characters and onboarding was
  focused on default packages plus targeted verification reads, the same
  three-pair task retained full adoption and correctness. Median elapsed time
  fell 34.7%, median tokens fell 64.5%, and treatments used 2 to 4 shell
  commands versus 14 to 18 for controls.
- The independent Config.Net summary-free live gate passed at clean CodeMesh
  commit `d764270`: all 18 calls succeeded, recall and MRR were 1.0, nDCG was
  0.93483, and no secret leaks were detected.
- The Config.Net assisted campaign produced two CodeMesh-attributable
  correctness wins, full treatment success and adoption, no safety violations,
  and 11.8% lower median elapsed time. Treatment median tokens were 3.0% higher.

These results replicate utility after explicit onboarding. They do not prove
prompt-parity discoverability, spontaneous adoption, or broad generalization.
The Config.Net transcription is
[`docs/evaluation/evidence/config-net-assisted-replication-d764270.json`](../evaluation/evidence/config-net-assisted-replication-d764270.json).

## Current Gap

The immediate evidence gap is normal-host discoverability. CodeMesh now
publishes canonical MCP initialization instructions for the efficient
context-package plus targeted-read workflow, and `config-net-cache-agent`
freezes the independent task without treatment-only guidance. The suite has not
yet established that a normal host presents and follows those instructions.

The campaign is model-cost-bearing and requires explicit authorization, a clean
committed CodeMesh tool checkout, a clean pinned Config.Net checkout, and a
fresh matching index. Unit and contract tests for the instructions do not
substitute for that evidence.

## Current Boundaries

- Generated summaries remain disabled in the core product-proof baseline.
- No summary model is qualified.
- Python, Markdown, and deployment parsers do not match Roslyn's semantic depth.
- Shared multi-user stores, portable snapshot artifacts, outcome memory,
  Kubernetes/Helm ingestion, and broader SDLC intelligence are not implemented.
- Current source redaction does not replace repository authorization or a
  configurable sensitive-file policy.
- The historical publication review is not evidence for commits after its
  recorded snapshot.

## Status Maintenance

Update this page when implemented capability, reviewed evidence, or the
immediate product gap changes. Keep detailed procedures in their canonical
guides and keep future execution order in `docs/planning/next-steps.md`.
