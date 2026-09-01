# CodeMesh Documentation

This page is the documentation entry point. It separates current behavior,
current evidence, operating guides, engineering policy, and future proposals so
readers can tell what CodeMesh does from what it may do later.

## Start Here

| Reader | Read first | Then use |
| --- | --- | --- |
| Evaluating CodeMesh | [`README.md`](../README.md) | [MCP Setup](guides/mcp-setup.md), [Project Status](current/project-status.md) |
| Using CodeMesh through MCP | [MCP Setup](guides/mcp-setup.md) | [Agent Prompts](guides/agent-prompts.md), [Agent Access Contracts](current/agent-access-contracts.md) |
| Contributing | [`CONTRIBUTING.md`](../CONTRIBUTING.md) | [`COMMANDS.md`](../COMMANDS.md), [Testing](evaluation/testing.md), [Engineering Standards](engineering/standards.md) |
| Coding agent working in this repository | [Agent Quickstart](guides/agent-quickstart.md) | [`AGENTS.md`](../AGENTS.md), [Architecture](current/architecture.md) |
| Reviewing product direction | [Project Status](current/project-status.md) | [Next Steps](planning/next-steps.md), then the relevant proposal |

## Authority And Document Types

When documents overlap, use this order:

1. Source code and tests define implemented behavior.
2. [Agent Access Contracts](current/agent-access-contracts.md) and
   [Architecture](current/architecture.md) describe the current supported surfaces and
   component boundaries.
3. [`COMMANDS.md`](../COMMANDS.md) indexes supported repository invocations;
   [Testing](evaluation/testing.md), [MCP Setup](guides/mcp-setup.md), and
   [Security and Redaction](current/security-and-redaction.md) are current
   operating guides.
4. [Engineering Standards](engineering/standards.md) and the
   [Software Engineering Methodology](engineering/methodology.md) define
   contributor policy, evidence states, and authority boundaries.
5. [Project Status](current/project-status.md) records the latest reviewed
   implementation and evidence position.
6. [Next Steps](planning/next-steps.md) is the execution-order authority for future
   product work.
7. Proposal and roadmap documents describe unimplemented possibilities unless
   current source and contracts say otherwise.
8. Dated evidence and publication reviews describe only the commit and time
   they identify.

Document labels have these meanings:

- **Current reference:** intended to match current implemented behavior.
- **Operating guide:** commands and procedures for the current product.
- **Status snapshot:** reviewed implementation and evidence at a stated date.
- **Policy:** contributor, security, or engineering rules.
- **Proposal:** requirements or design that is not implemented.
- **Historical evidence:** immutable or retained evidence for an earlier
  commit; never a claim about current HEAD by itself.

## Folder Layout

| Folder | Purpose |
| --- | --- |
| `current/` | Implemented architecture, interfaces, security behavior, and current status. |
| `guides/` | Task-oriented setup, operation, self-analysis, and agent workflows. |
| `evaluation/` | Verification procedures, effectiveness evaluation, prompt assets, and retained evidence. |
| `planning/` | Execution order, proposals, qualification procedures, and deferred roadmaps. |
| `engineering/` | Contribution standards and repository-quality controls. |
| `decisions/` | Architecture decision records for consequential implemented choices. |
| `history/` | Dated reviews retained for provenance, not current status. |

## Documentation Index

### Product and current behavior

- [`README.md`](../README.md) — public product overview and local demonstration.
- [Project Status](current/project-status.md) — current capability and evidence summary.
- [Architecture](current/architecture.md) — implemented components, flow, and stores.
- [Agent Access Contracts](current/agent-access-contracts.md) — REST, MCP, CLI-facing,
  UI, and .NET client contracts.
- [Security and Redaction](current/security-and-redaction.md) — implemented redaction,
  known gaps, and safety constraints.

### Setup and use

- [MCP Setup](guides/mcp-setup.md) — services, ingestion, stdio MCP configuration, and
  troubleshooting.
- [Self-Analysis](guides/self-analysis.md) — index and query CodeMesh itself.
- [Agent Prompts](guides/agent-prompts.md) — source-grounded example tasks.
- [Agent Quickstart](guides/agent-quickstart.md) — repository navigation for coding
  agents.

### Verification and evaluation

- [Testing](evaluation/testing.md) — canonical risk-scaled validation commands.
- [MCP Effectiveness Evaluation](evaluation/mcp-effectiveness.md) — fixture, live, agent, and
  model evaluation procedures.
- [Evidence manifests](evaluation/evidence/) — sanitized, commit-bound evidence retained
  in Git.
- [Evaluation prompt assets](evaluation/assets/) — pinned chat templates used by
  explicitly authorized model-backed evaluation.
- [Publication Readiness Review](history/publication-readiness-2026-08-11.md) — historical
  2026-08-11 publication-preparation evidence, not current readiness status.

### Planning and requirements

- [Next Steps](planning/next-steps.md) — canonical execution order and capability map.
- [Agent Integration Contract](planning/agent-integration-contract.md) — selected
  explicit-onboarding contract, implemented checkout binding, freshness
  enforcement, tool profiles, runtime probes, reviewable installation, and
  evaluation classification.
- [one|nine Adoption and Feedback Priority](planning/onenine-adoption-and-feedback.md)
  — owner-activated plan and passed local pilot gate for safe checkout-bound
  adoption, atomic Python/Rust ingestion, a Rust parser, agent feedback
  artifacts, and controlled evaluation.
- [Graph Intelligence and Agent Memory](planning/graph-intelligence-design.md) —
  relationship evidence, graph analysis, parser tiers, memory, and portability
  proposal.
- [Method Load and Retrieval Granularity](planning/method-load-and-retrieval-granularity.md)
  — proposed human-maintainability, model-representation, token-accounting, and
  method-decomposition evaluation.
- [Repository Identity and Snapshot Retention](planning/repository-identity-and-snapshot-retention.md)
  — implemented local multi-checkout retention and future shared-store requirements.
- [Summary Model Qualification](planning/summary-model-qualification.md) — implemented
  runner and operating procedure; no deployment profile is currently qualified.
- [SDLC Roadmap](planning/sdlc-roadmap.md) — deferred broader artifact coverage.

### Engineering policy

- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution entry point.
- [`COMMANDS.md`](../COMMANDS.md) — canonical supported command index.
- [`SECURITY.md`](../SECURITY.md) — vulnerability reporting and safe operation.
- [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) — third-party and
  distribution boundaries.
- [Engineering Standards](engineering/standards.md) — change discipline,
  verification, documentation, and definition of done.
- [Software Engineering Methodology](engineering/methodology.md) — evidence,
  authority, guidance placement, and reusable-control admission boundaries.
- [Conventional Commit Validation](engineering/conventional-commits.md) — local
  commit-message checker.
- [GitHub Actions Baseline](engineering/github-actions.md) — exact workflow
  scope and evidence boundary.
- [Markdown Link Checking](engineering/link-checking.md) — deterministic local
  link validation.
- [Release Notes Template](engineering/release-notes-template.md) — prepared,
  tagged, published, deployed, and stable-state separation for a future release.
- [Decision Record Template](decisions/0000-decision-record-template.md) — ADR
  format for implemented architecture decisions.

## Maintenance Rules

- Keep supported contributor and agent invocations in the root `COMMANDS.md`;
  keep ordered operational and evaluation procedures in their controlling
  guides and link between them.
- Keep current implementation and evidence in `current/project-status.md`; keep
  future execution order in `planning/next-steps.md`.
- Mark proposals and historical reviews explicitly near the title.
- Update contracts and architecture when implemented behavior changes.
- Bind measurements to a date and commit, and retain negative evidence.
- Do not convert a passing fixture, local test, or configured workflow into a
  hosted, production, release, or product-benefit claim.
- Preserve stable documentation paths when practical. When an approved
  reorganization moves them, update tests, suites, prompts, and repository links
  in the same change.
